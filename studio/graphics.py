"""Locally rendered motion graphics (no AI generation): the campaign's green line
and the olive end-card background. The PDF specifies these as motion graphics made
in the edit; these are first-pass versions a motion designer can replace.
The logo and Arabic text are NOT baked in — they stay separate layers.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from .model import Project, source_ratios, to_ms, video_fps
from .render import RenderError, ffmpeg_bin

SUPPORTED = ("green_line", "end_card")


def _rgb(hex_color: str) -> tuple[int, int, int]:
    h = hex_color.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)


def _ease(t: float) -> float:
    t = min(1.0, max(0.0, t))
    return t * t * (3 - 2 * t)


def _green_line_frames(w, h, n, color):
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter
    rng = np.random.default_rng(7)                    # fixed seed: identical on every render
    pts = 9
    xs = np.linspace(w * 0.12, w * 0.88, pts)
    offs = rng.uniform(-1, 1, pts) * h * 0.07
    offs[0] = offs[-1] = 0
    cy = h / 2
    lw = max(6, int(min(w, h) * 0.012))
    for i in range(n):
        t = i / max(1, n - 1)
        draw_p = _ease(t / 0.38)                      # 0-38%: the crooked line draws itself
        straight = _ease((t - 0.42) / 0.36)           # 42-78%: it straightens
        glow = _ease((t - 0.70) / 0.30)               # 70-100%: it lights up
        end_x = xs[0] + (xs[-1] - xs[0]) * draw_p
        line = [(float(x), float(cy + o * (1 - straight))) for x, o in zip(xs, offs) if x <= end_x]
        if len(line) < pts and line:
            k = len(line)
            f = (end_x - xs[k - 1]) / (xs[k] - xs[k - 1])
            y = cy + (offs[k - 1] + (offs[k] - offs[k - 1]) * f) * (1 - straight)
            line.append((float(end_x), float(y)))
        layer = Image.new("RGB", (w, h), (0, 0, 0))
        if len(line) >= 2:
            ImageDraw.Draw(layer).line(line, fill=color, width=lw, joint="curve")
        if glow > 0:
            halo = layer.filter(ImageFilter.GaussianBlur(lw * 2.5))
            arr = np.asarray(layer, dtype=np.float32) + np.asarray(halo, dtype=np.float32) * (1.6 * glow)
            layer = Image.fromarray(np.clip(arr, 0, 255).astype("uint8"))
        yield layer.tobytes()


def _end_card_frames(w, h, n, color):
    import numpy as np
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    r = np.sqrt(((xx - w / 2) / w) ** 2 + ((yy - h * 0.45) / h) ** 2)
    base = 1.0 - 0.38 * np.clip(r / 0.75, 0, 1) ** 1.5              # soft vignette
    diag = (xx / w + yy / h) / 2
    col = np.array(color, dtype=np.float32)
    for i in range(n):
        t = i / max(1, n - 1)
        band = np.exp(-((diag - (-0.2 + 1.4 * t)) ** 2) / (2 * 0.07 ** 2)) * 0.10   # slow light shimmer
        fade = _ease(t / 0.12)
        frame = (base + band)[..., None] * col[None, None, :] * fade
        yield np.clip(frame, 0, 255).astype("uint8").tobytes()


def render_clip(kind: str, dest: Path, w: int, h: int, fps: int, seconds: float, color: str) -> Path:
    if kind not in SUPPORTED:
        raise RenderError(f"graphic {kind!r} is not rendered locally (supported: {SUPPORTED})")
    n = int(round(seconds * fps))
    frames = (_green_line_frames if kind == "green_line" else _end_card_frames)(w, h, n, _rgb(color))
    dest.parent.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen(
        [ffmpeg_bin(), "-y", "-hide_banner", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24",
         "-s", f"{w}x{h}", "-r", str(fps), "-i", "-", "-c:v", "libx264", "-crf", "16", "-pix_fmt", "yuv420p",
         "-movflags", "+faststart", str(dest)], stdin=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        for f in frames:
            proc.stdin.write(f)
        proc.stdin.close()
    except BrokenPipeError:
        pass
    if proc.wait() != 0:
        raise RenderError(proc.stderr.read().decode()[-1500:])
    return dest


def build_for_video(project: Project, vid: str) -> list[Path]:
    """Render every locally supported graphics shot of a video, in each ratio it is needed."""
    video = project.video(vid)
    fps = video_fps(project, video)
    out = []
    for i, shot in enumerate(video.get("shots", []), start=1):
        gen = shot.get("generation", {})
        kind = gen.get("graphic")
        if gen.get("mode") != "graphics" or kind not in SUPPORTED:
            continue
        if kind == "green_line" and "black screen" not in shot.get("action", "").lower():
            continue   # line over other artwork (split-screen divider, list strike) is a designer job
        seconds = (to_ms(shot["end_s"]) - to_ms(shot["start_s"])) / 1000
        for ratio in source_ratios(video, shot):
            w, h = project.campaign["output_targets"][ratio]
            dest = project.clip_path(vid, i, ratio)
            if ratio == "9x16":
                dest = project.root / "assets" / "clips" / f"{vid}_{i:02d}.mp4"
            out.append(render_clip(kind, dest, w, h, fps, seconds, gen.get("color", project.campaign["brand"]["roles"]["primary"])))
    return out
