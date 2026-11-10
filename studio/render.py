"""FFmpeg assembly: clips -> clean picture + mixed audio, with Arabic overlays
and the logo kept as SEPARATE layers (ASS subtitle file + JSON for the editor).
Burning overlays into the picture is a separate, explicit step.
"""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from .model import Project, save_json, to_ms, video_fps

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
        if shot.get("vo_ar") and video.get("subtitles", True) and shot.get("subtitles", True):
            events.append({"shot_id": shot["id"], "kind": "subtitle",
                           "text": shot.get("subtitle_ar", shot["vo_ar"]),
                           "start_s": shot.get("vo_start_s", shot["start_s"]),
                           "end_s": shot.get("vo_end_s", shot["end_s"]),
                           "position": "bottom", "style": "subtitle"})
    return events


def font_family(project: Project) -> tuple[str, Path]:
    """(family name, fonts dir): licensed brand font if supplied, else the approved draft font."""
    brand = project.campaign.get("brand", {})
    if brand.get("font_licensed") and (project.root / brand.get("font_path", "")).is_file():
        p = project.root / brand["font_path"]
        return brand.get("font_family", p.stem), p.parent
    p = project.root / brand.get("draft_font_path", "")
    return brand.get("draft_font_family", "Arial"), p.parent if p.is_file() else project.root / "assets" / "brand"


def write_ass(project: Project, video: dict, ratio: str, dest: Path, font_name: str | None = None) -> Path:
    w, h = project.campaign["output_targets"][ratio]
    font_name = font_name or font_family(project)[0]
    safe = project.campaign.get("safe_area_px", {}).get(ratio, {})
    top, bottom = int(safe.get("top", h * 0.06)), int(safe.get("bottom", h * 0.06))
    roles = project.campaign.get("brand", {}).get("roles", {})
    light, primary, accent = roles.get("light", "#FFFFFF"), roles.get("primary", "#000000"), roles.get("accent", "#FFFFFF")
    base = max(36, int(h * 0.032))
    lines = [
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {w}", f"PlayResY: {h}", "WrapStyle: 0", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Alignment, MarginL, MarginR, MarginV, BorderStyle, Outline, Shadow, Encoding",
        f"Style: headline,{font_name},{int(base*1.6)},{_ass_color(light)},{_ass_color(primary)},&H64000000,1,8,80,80,{top},1,3,0,178",
        f"Style: body,{font_name},{base},{_ass_color(light)},{_ass_color(primary)},&H64000000,0,2,80,80,{bottom + int(h*0.08)},1,2,0,178",
        f"Style: subtitle,{font_name},{int(base*0.9)},&H00FFFFFF,&H00000000,&H80000000,0,2,80,80,{bottom},3,1,0,178",
        f"Style: cta,{font_name},{int(base*1.2)},{_ass_color(accent)},{_ass_color(primary)},&H64000000,1,2,80,80,{bottom},1,2,0,178",
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    for ev in overlay_events(video):
        style = ev.get("style", "body")
        if style not in ("headline", "body", "subtitle", "cta"):
            style = "body"
        align = ASS_ALIGN.get(ev.get("position", "lower_third"), 2)
        text = ev["text"].replace("\n", "\\N")
        # U+202B RIGHT-TO-LEFT EMBEDDING keeps punctuation on the correct side.
        pos = ev.get("position", "lower_third")
        # Explicit per-event vertical margin, measured from the safe area (9:16: 250px top / 420px bottom).
        margin_v = {"top": top, "center": 0, "end_card": 0, "bottom": bottom,
                    "lower_third": bottom + int(h * 0.07)}.get(pos, bottom)
        if ev["kind"] == "subtitle":
            margin_v = bottom
        elif pos == "bottom" and style == "cta":
            margin_v = bottom
        lines.append(
            f"Dialogue: {1 if ev['kind']=='overlay' else 0},{_ass_time(to_ms(ev['start_s']))},{_ass_time(to_ms(ev['end_s']))},"
            f"{style},{ev['kind']},0,0,{margin_v},,{{\\an{align}}}‫{text}‬")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest


def build_command(project: Project, vid: str, ratio: str, out: Path, allow_silent: bool = False,
                  allow_reframe: bool = False) -> list[str]:
    from .qc import probe
    video = project.video(vid)
    shots = video.get("shots", [])
    if not shots:
        raise RenderError(f"{vid}: no shots planned")
    w, h = project.campaign["output_targets"][ratio]
    fps = video_fps(project, video)
    total = to_ms(video["duration_s"]) / 1000
    cmd = [ffmpeg_bin(), "-y", "-hide_banner", "-loglevel", "error"]
    sources, missing = [], []
    for i, _ in enumerate(shots, start=1):
        p, used = project.source_clip(vid, i, ratio)
        sources.append((p, used))
        if not p.exists():
            missing.append(str(p.relative_to(project.root)))
        cmd += ["-i", str(p)]
    if missing:
        raise RenderError("Missing clips: " + ", ".join(missing))

    n = len(shots)
    filters, bad = [], []
    for i, (shot, (p, used)) in enumerate(zip(shots, sources)):
        d = (to_ms(shot["end_s"]) - to_ms(shot["start_s"])) / 1000
        v = next((s for s in probe(p)["streams"] if s["codec_type"] == "video"), {})
        src_ar = v.get("width", w) / max(1, v.get("height", h))
        native = abs(src_ar - w / h) <= 0.01
        planned_reframe = used != ratio  # the plan says: generate once, reframe in the edit
        if not native and not planned_reframe and not allow_reframe:
            bad.append(f"{p.name} ({v.get('width')}x{v.get('height')})")
        head = f"[{i}:v]trim=duration={d:.3f},setpts=PTS-STARTPTS,fps={fps},setsar=1"
        if native or src_ar > w / h:
            # same shape, or wider source -> centre crop (16:9 master cut to 9:16)
            filters.append(f"{head},scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,format=yuv420p[v{i}]")
        else:
            # narrower source (vertical phone close-up in a 16:9 cut) -> blurred pillarbox, no cropping
            filters.append(f"{head},split=2[bg{i}][fg{i}];"
                           f"[bg{i}]scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},gblur=sigma=40,eq=brightness=-0.08[bgb{i}];"
                           f"[fg{i}]scale=-2:{h}[fgs{i}];[bgb{i}][fgs{i}]overlay=(W-w)/2:0,setsar=1,format=yuv420p[v{i}]")
    if bad:
        raise RenderError(f"Clips not native {ratio} (would be cropped): " + ", ".join(bad)
                          + " — generate a native take, set generation.source_ratios, or pass --allow-reframe")
    filters.append("".join(f"[v{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[vout]")

    audio_dir = project.root / "assets" / "audio"
    voice, music = audio_dir / f"{vid}_voice.wav", audio_dir / f"{vid}_music.wav"
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
        "logo_dark_bg": project.campaign.get("brand", {}).get("logo_dark_bg_path"),
        "logo_rule": project.campaign.get("brand", {}).get("logo_rule"),
        "font_licensed": project.campaign.get("brand", {}).get("font_licensed", False),
        "events": overlay_events(video),
    })
    return {"clean": clean, "ass": ass, "layers": layers}


def logo_cues(video: dict) -> list[dict]:
    out = []
    for shot in video.get("shots", []):
        lg = shot.get("logo")
        if lg:
            out.append({"start_s": lg.get("start_s", shot["start_s"]), "end_s": lg.get("end_s", shot["end_s"]),
                        "width_frac": float(lg.get("width_frac", 0.30)), "fade_s": float(lg.get("fade_s", 0.5)),
                        "variant": lg.get("variant", "primary")})
    return out


def final_blockers(project: Project) -> list[str]:
    brand = project.campaign.get("brand", {})
    out = []
    if not brand.get("logo_supplied"):
        out.append("official logo not supplied")
    if not (brand.get("font_licensed") and (project.root / brand.get("font_path", "")).is_file()):
        out.append("licensed brand font not supplied")
    if brand.get("green_system_decision", "pending") == "pending":
        out.append("owner has not chosen the green system")
    return out


def burn(project: Project, vid: str, ratio: str, draft: bool = False, logo_variant: str = "primary") -> Path:
    """Burn the overlay layer (and official logo) into a delivery file."""
    brand = project.campaign.get("brand", {})
    outdir = project.root / "output" / vid
    clean = outdir / f"{vid}_{ratio}_clean.mp4"
    ass = outdir / f"{vid}_{ratio}_overlays_ar.ass"
    if not clean.exists() or not ass.exists():
        raise RenderError("Run render first")
    font = project.root / brand.get("font_path", "")
    cues = logo_cues(project.video(vid))
    if cues and logo_variant == "primary":
        logo_variant = cues[0]["variant"]
    logo_key = "logo_dark_bg_path" if logo_variant == "dark" else "logo_path"
    logo = project.root / brand.get(logo_key, "")
    blockers = final_blockers(project)
    if blockers and not draft:
        raise RenderError("Cannot make a final: " + "; ".join(blockers) + ". Use --draft for an internal review copy")
    final = not blockers and not draft
    out = outdir / f"{vid}_{ratio}_{'final' if final else 'DRAFT'}.mp4"
    vf = f"ass={ass}:fontsdir={font_family(project)[1]}"
    cmd = [ffmpeg_bin(), "-y", "-hide_banner", "-loglevel", "error", "-i", str(clean)]
    cues = logo_cues(project.video(vid))
    if cues and not logo.is_file():
        raise RenderError(f"Plan places the logo but {logo.relative_to(project.root)} is missing")
    if cues:
        # Official logo, used as-is (scaled only, never recoloured or regenerated), only where the plan places it.
        w, h = project.campaign["output_targets"][ratio]
        chain, last = [f"[0:v]{vf}[t0]"], "t0"
        for k, c in enumerate(cues):
            lw = int(w * c["width_frac"]) if ratio == "16x9" else int(w * min(0.6, c["width_frac"] * 1.8))
            y = f"(H-h)/2-{int(h*0.06)}"
            chain.append(f"[1:v]scale={lw}:-1,format=rgba,fade=t=in:st={c['start_s']}:d={c['fade_s']}:alpha=1[lg{k}]")
            chain.append(f"[{last}][lg{k}]overlay=(W-w)/2:{y}:enable='between(t,{c['start_s']},{c['end_s']})'[t{k+1}]")
            last = f"t{k+1}"
        cmd += ["-loop", "1", "-i", str(logo), "-filter_complex", ";".join(chain),
                "-map", f"[{last}]", "-map", "0:a", "-shortest"]
    else:
        cmd += ["-vf", vf, "-map", "0:v", "-map", "0:a"]
    cmd += ["-c:v", "libx264", "-crf", "18", "-pix_fmt", "yuv420p", "-c:a", "copy", "-movflags", "+faststart", str(out)]
    res = subprocess.run(cmd, capture_output=True, text=True)
    if res.returncode != 0:
        raise RenderError(res.stderr.strip()[-2000:])
    return out
