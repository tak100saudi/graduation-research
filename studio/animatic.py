"""Timing animatic: one labelled slate per shot + the real Arabic overlay layer and logo cue.
It is a review tool for timing, pacing and text placement — NOT generated footage."""
from __future__ import annotations

import subprocess
from pathlib import Path

from .model import Project, to_ms, video_fps
from .render import RenderError, ffmpeg_bin, font_family, logo_cues, write_ass

CHAOS, SYSTEM, GRAPHIC = "0x3a3d40", "0x2a3a1c", "0x33650C"


def _slate_color(shot: dict) -> str:
    if shot.get("generation", {}).get("mode") == "graphics":
        return "black" if "black" in shot.get("action", "").lower() else GRAPHIC
    return CHAOS if "CHAOS" in shot.get("scene", "") else SYSTEM


def _esc(t: str) -> str:
    return t.replace("\\", "\\\\").replace(":", "\\:").replace("'", "’").replace("%", "\\%")


def build(project: Project, vid: str, ratio: str) -> Path:
    video = project.video(vid)
    shots = video["shots"]
    if not shots:
        raise RenderError(f"{vid}: no shots")
    w, h = project.campaign["output_targets"][ratio]
    fps = video_fps(project, video)
    out_dir = project.root / "output" / vid
    out_dir.mkdir(parents=True, exist_ok=True)
    ass = write_ass(project, video, ratio, out_dir / f"{vid}_{ratio}_overlays_ar.ass")
    fam, fontsdir = font_family(project)
    mono = "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf"
    fs = max(14, int(min(w, h) * 0.028))
    parts, inputs = [], []
    for i, s in enumerate(shots):
        d = (to_ms(s["end_s"]) - to_ms(s["start_s"])) / 1000
        clip, _ = project.source_clip(vid, i + 1, ratio)
        if clip.exists():
            # A real asset exists (local motion graphics or an approved take): show it, with a small tag.
            inputs += ["-i", str(clip)]
            tag = f"drawtext=fontfile={mono}:text='{_esc(s['id'])}':fontcolor=white@0.5:fontsize={int(fs*0.8)}:x=24:y=24"
            parts.append(f"[{i}:v]trim=duration={d:.3f},setpts=PTS-STARTPTS,fps={fps},"
                         f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},{tag},setsar=1,format=yuv420p[s{i}]")
            continue
        inputs += ["-f", "lavfi", "-i", f"color=c={_slate_color(s)}:s={w}x{h}:r={fps}:d={d:.3f}"]
        gen = s.get("generation", {})
        src = gen.get("reuse") or ",".join(gen.get("source_ratios", []))
        lines = ["ANIMATIC - NOT FINAL FOOTAGE", f"{s['id']}  (PDF {s.get('pdf_ref', '')})  {s['start_s']}-{s['end_s']}s",
                 f"{s.get('beat', '')}", f"mode: {gen.get('mode')}  src: {src}"]
        y0 = int(h * 0.30)
        dt = ",".join(
            f"drawtext=fontfile={mono}:text='{_esc(t)}':fontcolor=white@0.85:fontsize={fs}:x=(w-tw)/2:y={y0 + k * int(fs * 1.6)}"
            for k, t in enumerate(lines))
        parts.append(f"[{i}:v]{dt},setsar=1,format=yuv420p[s{i}]")
    n = len(shots)
    total = to_ms(video["duration_s"]) / 1000
    chain = ";".join(parts) + ";" + "".join(f"[s{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[c]"
    chain += f";[c]ass={ass}:fontsdir={fontsdir}[t0]"
    last = "t0"
    cues = logo_cues(video)
    logo_in = []
    if cues:
        brand = project.campaign["brand"]
        key = "logo_dark_bg_path" if cues[0]["variant"] == "dark" else "logo_path"
        logo_in = ["-loop", "1", "-i", str(project.root / brand[key])]
        for k, c in enumerate(cues):
            lw = int(w * c["width_frac"]) if ratio == "16x9" else int(w * min(0.6, c["width_frac"] * 1.8))
            chain += (f";[{n}:v]scale={lw}:-1,format=rgba,fade=t=in:st={c['start_s']}:d={c['fade_s']}:alpha=1[lg{k}]"
                      f";[{last}][lg{k}]overlay=(W-w)/2:(H-h)/2-{int(h*0.06)}:enable='between(t,{c['start_s']},{c['end_s']})'[t{k+1}]")
            last = f"t{k+1}"
    out = out_dir / f"{vid}_{ratio}_ANIMATIC.mp4"
    cmd = [ffmpeg_bin(), "-y", "-hide_banner", "-loglevel", "error", *inputs, *logo_in,
           "-f", "lavfi", "-i", f"anullsrc=r=48000:cl=stereo",
           "-filter_complex", chain, "-map", f"[{last}]", "-map", f"{n + (1 if logo_in else 0)}:a",
           "-c:v", "libx264", "-crf", "23", "-pix_fmt", "yuv420p", "-r", str(fps), "-c:a", "aac",
           "-t", f"{total:.3f}", "-movflags", "+faststart", str(out)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RenderError(res.stderr.strip()[-2000:])
    return out
