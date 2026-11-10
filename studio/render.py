"""FFmpeg assembly: clips -> clean picture + mixed audio, with Arabic overlays
and the logo kept as SEPARATE layers (ASS subtitle file + JSON for the editor).
Burning overlays into the picture is a separate, explicit step.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .model import Project, save_json, to_ms

ASS_ALIGN = {"top": 8, "center": 5, "lower_third": 2, "bottom": 2, "end_card": 5}


class RenderError(RuntimeError):
    pass


def ffmpeg_bin() -> str:
    b = shutil.which("ffmpeg")
    if not b:
        raise RenderError("ffmpeg not found on PATH")
    return b


def _ass_time(ms: int) -> str:
    cs = ms // 10
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _ass_color(hex_color: str | None) -> str:
    h = (hex_color or "#FFFFFF").lstrip("#")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H00{b}{g}{r}".upper()


def overlay_events(video: dict) -> list[dict]:
    events = []
    for shot in video.get("shots", []):
        for ov in shot.get("overlay_ar", []):
            events.append({"shot_id": shot["id"], "kind": "overlay", **ov})
        if shot.get("vo_ar") and shot.get("subtitles", True):
            events.append({"shot_id": shot["id"], "kind": "subtitle",
                           "text": shot.get("subtitle_ar", shot["vo_ar"]),
                           "start_s": shot.get("vo_start_s", shot["start_s"]),
                           "end_s": shot.get("vo_end_s", shot["end_s"]),
                           "position": "bottom", "style": "subtitle"})
    return events


def write_ass(project: Project, video: dict, ratio: str, dest: Path, font_name: str = "Arial") -> Path:
    w, h = project.campaign["output_targets"][ratio]
    colors = project.campaign.get("brand", {}).get("colors", {})
    base = max(36, int(h * 0.032))
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {w}", f"PlayResY: {h}", "WrapStyle: 0", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Alignment, MarginL, MarginR, MarginV, BorderStyle, Outline, Shadow, Encoding",
        f"Style: headline,{font_name},{int(base*1.6)},{_ass_color(colors.get('beige'))},{_ass_color(colors.get('green'))},&H64000000,1,5,80,80,{int(h*0.12)},1,3,0,178",
        f"Style: body,{font_name},{base},{_ass_color(colors.get('beige'))},{_ass_color(colors.get('green'))},&H64000000,0,2,80,80,{int(h*0.18)},1,2,0,178",
        f"Style: subtitle,{font_name},{int(base*0.9)},&H00FFFFFF,&H00000000,&H80000000,0,2,80,80,{int(h*0.06)},3,1,0,178",
        f"Style: cta,{font_name},{int(base*1.2)},{_ass_color(colors.get('muted_gold'))},{_ass_color(colors.get('green'))},&H64000000,1,2,80,80,{int(h*0.10)},1,2,0,178",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for ev in overlay_events(video):
        style = ev.get("style", "body")
        if style not in ("headline", "body", "subtitle", "cta"):
            style = "body"
        align = ASS_ALIGN.get(ev.get("position", "lower_third"), 2)
        text = ev["text"].replace("\n", "\\N")
        # U+202B RIGHT-TO-LEFT EMBEDDING keeps punctuation on the correct side.
        lines.append(
            f"Dialogue: {1 if ev['kind']=='overlay' else 0},{_ass_time(to_ms(ev['start_s']))},{_ass_time(to_ms(ev['end_s']))},"
            f"{style},{ev['kind']},0,0,0,,{{\\an{align}}}‫{text}‬")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest


def build_command(project: Project, vid: str, ratio: str, out: Path, allow_silent: bool = False,
                  allow_reframe: bool = False) -> list[str]:
    video = project.video(vid)
    shots = video.get("shots", [])
    if not shots:
        raise RenderError(f"{vid}: no shots planned")
    w, h = project.campaign["output_targets"][ratio]
    fps = project.campaign.get("fps", 24)
    total = to_ms(video["duration_s"]) / 1000
    cmd = [ffmpeg_bin(), "-y", "-hide_banner", "-loglevel", "error"]
    missing = []
    for i, _ in enumerate(shots, start=1):
        p = project.clip_path(vid, i, ratio)
        if not p.exists():
            missing.append(str(p.relative_to(project.root)))
        cmd += ["-i", str(p)]
    if missing:
        raise RenderError("Missing clips: " + ", ".join(missing))
    if not allow_reframe:
        from .qc import probe
        bad = []
        for i, _ in enumerate(shots, start=1):
            p = project.clip_path(vid, i, ratio)
            v = next((s for s in probe(p)["streams"] if s["codec_type"] == "video"), None)
            if v and abs(v["width"] / v["height"] - w / h) > 0.01:
                bad.append(f"{p.name} ({v['width']}x{v['height']})")
        if bad:
            raise RenderError(f"Clips not native {ratio} (would be cropped): " + ", ".join(bad)
                              + " — generate a native take or pass --allow-reframe")

    audio_dir = project.root / "assets" / "audio"
    voice, music = audio_dir / f"{vid}_voice.wav", audio_dir / f"{vid}_music.wav"
    n = len(shots)
    filters = []
    for i, shot in enumerate(shots):
        d = (to_ms(shot["end_s"]) - to_ms(shot["start_s"])) / 1000
        filters.append(
            f"[{i}:v]trim=duration={d:.3f},setpts=PTS-STARTPTS,fps={fps},"
            f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,format=yuv420p[v{i}]")
    filters.append("".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[vout]")

    audio_inputs = []
    if voice.exists():
        cmd += ["-i", str(voice)]
        audio_inputs.append(("voice", n + len(audio_inputs)))
    if music.exists():
        cmd += ["-i", str(music)]
        audio_inputs.append(("music", n + len(audio_inputs)))
    a = project.campaign.get("audio", {})
    lufs, tp = a.get("loudness_target_lufs", -14), a.get("true_peak_max_dbtp", -1)
    idx = dict(audio_inputs)
    if not audio_inputs:
        if not allow_silent:
            raise RenderError(f"Missing {voice.name} and {music.name} (use --allow-silent for a picture-only draft)")
        filters.append(f"anullsrc=r=48000:cl=stereo,atrim=duration={total:.3f}[aout]")
    else:
        if "voice" in idx:
            filters.append(f"[{idx['voice']}:a]aresample=48000,aformat=channel_layouts=stereo,apad,atrim=duration={total:.3f}[vo]")
        if "music" in idx:
            filters.append(f"[{idx['music']}:a]aresample=48000,aformat=channel_layouts=stereo,apad,atrim=duration={total:.3f},"
                           f"afade=t=out:st={max(0, total-1.0):.3f}:d=1.0[mu]")
        if "voice" in idx and "music" in idx:
            filters.append("[vo]asplit=2[vo1][vo2]")
            filters.append("[mu][vo1]sidechaincompress=threshold=0.05:ratio=8:attack=20:release=400[duck]")
            filters.append("[vo2][duck]amix=inputs=2:normalize=0[mix]")
            last = "mix"
        else:
            last = "vo" if "voice" in idx else "mu"
        filters.append(f"[{last}]loudnorm=I={lufs}:TP={tp}:LRA=11,aresample=48000,atrim=duration={total:.3f}[aout]")

    cmd += ["-filter_complex", ";".join(filters), "-map", "[vout]", "-map", "[aout]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(fps),
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{total:.3f}", "-movflags", "+faststart", str(out)]
    return cmd


def render(project: Project, vid: str, ratio: str, allow_silent: bool = False, allow_reframe: bool = False) -> dict:
    video = project.video(vid)
    if ratio not in video.get("aspect_ratios", []):
        raise RenderError(f"{vid} is not planned for {ratio}")
    outdir = project.root / "output" / vid
    outdir.mkdir(parents=True, exist_ok=True)
    clean = outdir / f"{vid}_{ratio}_clean.mp4"
    cmd = build_command(project, vid, ratio, clean, allow_silent=allow_silent, allow_reframe=allow_reframe)
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RenderError(res.stderr.strip()[-2000:])
    ass = write_ass(project, video, ratio, outdir / f"{vid}_{ratio}_overlays_ar.ass")
    layers = outdir / f"{vid}_{ratio}_layers.json"
    save_json(layers, {
        "video_id": vid, "ratio": ratio, "clean_picture": clean.name, "overlays_ass": ass.name,
        "logo": project.campaign.get("brand", {}).get("logo_path"),
        "official_brand_assets": project.campaign.get("brand", {}).get("official_assets_present", False),
        "events": overlay_events(video),
    })
    return {"clean": clean, "ass": ass, "layers": layers}


def burn(project: Project, vid: str, ratio: str, draft: bool = False) -> Path:
    """Burn the overlay layer (and official logo) into a delivery file."""
    brand = project.campaign.get("brand", {})
    outdir = project.root / "output" / vid
    clean = outdir / f"{vid}_{ratio}_clean.mp4"
    ass = outdir / f"{vid}_{ratio}_overlays_ar.ass"
    if not clean.exists() or not ass.exists():
        raise RenderError("Run render first")
    font = project.root / brand.get("font_path", "")
    logo = project.root / brand.get("logo_path", "")
    official = brand.get("official_assets_present") and font.is_file() and logo.is_file()
    if not official and not draft:
        raise RenderError("Official Season Venue font/logo not supplied; use --draft for an internal review copy")
    out = outdir / f"{vid}_{ratio}_{'final' if official and not draft else 'DRAFT'}.mp4"
    fontsdir = str(font.parent) if font.is_file() else str(project.root / "assets" / "brand")
    vf = f"ass={ass}:fontsdir={fontsdir}"
    cmd = [ffmpeg_bin(), "-y", "-hide_banner", "-loglevel", "error", "-i", str(clean)]
    if official:
        w, _ = project.campaign["output_targets"][ratio]
        cmd += ["-i", str(logo), "-filter_complex",
                f"[0:v]{vf}[t];[1:v]scale={int(w*0.22)}:-1[lg];[t][lg]overlay=W-w-{int(w*0.05)}:{int(w*0.05)}[v]",
                "-map", "[v]", "-map", "0:a"]
    else:
        cmd += ["-vf", vf, "-map", "0:v", "-map", "0:a"]
    cmd += ["-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", str(out)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RenderError(res.stderr.strip()[-2000:])
    return out
