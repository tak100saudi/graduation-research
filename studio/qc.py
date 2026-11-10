"""Automated visual/audio QC with ffprobe/ffmpeg, plus the human checklist.

A deliverable is approved only when every automated check passes AND every
human checklist item is signed off in the QC report.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from .model import Project, save_json, to_ms, video_fps

HUMAN_CHECKLIST = [
    "Every frame reviewed: no artefacts, warped hands/faces, or identity drift between shots",
    "Characters, wardrobe, locations and palette consistent with plans/continuity.json",
    "Arabic overlays: spelling, RTL order, diacritics and line breaks correct; official font",
    "Subtitles match the recorded VO word-for-word and are in sync",
    "VO is the licensed Saudi voice; licence on file",
    "Music licence on file; no alert chimes or ribbon-cutting",
    "Logo is the official Season Venue asset, correct clear-space and placement",
    "No invented prices, venue counts, testimonials, guarantees, verification, financing or payment protection",
    "Any product UI shown is an authentic screen recording",
    "All faces are consented talent",
]


class QCError(RuntimeError):
    pass


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True)


def probe(path: Path) -> dict:
    if not shutil.which("ffprobe"):
        raise QCError("ffprobe not found")
    res = _run(["ffprobe", "-v", "error", "-print_format", "json", "-show_streams", "-show_format", str(path)])
    if res.returncode != 0:
        raise QCError(f"ffprobe failed on {path}: {res.stderr.strip()}")
    return json.loads(res.stdout)


def _fps(stream: dict) -> float:
    num, den = stream.get("r_frame_rate", "0/1").split("/")
    return float(num) / float(den or 1)


def loudness(path: Path) -> dict:
    res = _run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"])
    tail = res.stderr[res.stderr.rfind("Summary:"):] if "Summary:" in res.stderr else ""
    i = re.search(r"I:\s*(-?[\d.]+|-inf) LUFS", tail)
    p = re.search(r"Peak:\s*(-?[\d.]+|-inf) dBFS", tail)
    f = lambda m: (float("-inf") if m.group(1) == "-inf" else float(m.group(1))) if m else None
    return {"integrated_lufs": f(i), "true_peak_dbtp": f(p)}


def detect(path: Path, vf: str, key: str) -> list[str]:
    res = _run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-vf", vf, "-an", "-f", "null", "-"])
    return [l.strip() for l in res.stderr.splitlines() if key in l]


def check_clip(project: Project, path: Path, planned_s: float, ratio: str | None = None) -> dict:
    """QC for a single generated clip before it is accepted."""
    info = probe(path)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    checks = []
    checks.append({"check": "has_video", "pass": v is not None})
    if v:
        dur = float(info["format"].get("duration", 0))
        checks.append({"check": "long_enough", "pass": dur + 1e-3 >= planned_s,
                       "detail": f"{dur:.3f}s >= {planned_s:.3f}s planned"})
        if ratio:
            w, h = project.campaign["output_targets"][ratio]
            same = abs(v["width"] / v["height"] - w / h) < 0.01
            checks.append({"check": "aspect_ratio", "pass": same,
                           "detail": f"{v['width']}x{v['height']} vs target {w}x{h}"})
            checks.append({"check": "min_resolution", "pass": min(v["width"], v["height"]) >= min(w, h) * 0.66,
                           "detail": "short side >= 2/3 of target (upscale limit)"})
    return {"path": str(path), "pass": all(c["pass"] for c in checks), "checks": checks}


def check_deliverable(project: Project, vid: str, ratio: str, path: Path) -> dict:
    video = project.video(vid)
    w, h = project.campaign["output_targets"][ratio]
    fps = video_fps(project, video)
    planned = to_ms(video["duration_s"]) / 1000
    info = probe(path)
    v = next((s for s in info["streams"] if s["codec_type"] == "video"), {})
    a = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    dur = float(info["format"].get("duration", 0))
    frame = 1 / fps
    checks = [
        {"check": "resolution", "pass": (v.get("width"), v.get("height")) == (w, h),
         "detail": f"{v.get('width')}x{v.get('height')} (target {w}x{h})"},
        {"check": "fps", "pass": abs(_fps(v) - fps) < 0.01 if v else False, "detail": f"{_fps(v) if v else 0:.3f}"},
        {"check": "duration", "pass": abs(dur - planned) <= frame + 0.03,
         "detail": f"{dur:.3f}s vs planned {planned:.3f}s"},
        {"check": "codec", "pass": v.get("codec_name") == "h264" and v.get("pix_fmt") == "yuv420p",
         "detail": f"{v.get('codec_name')}/{v.get('pix_fmt')}"},
        {"check": "audio_stream", "pass": a is not None and a.get("sample_rate") == "48000",
         "detail": f"{a.get('codec_name') if a else None} {a.get('sample_rate') if a else ''}"},
    ]
    warnings = []
    if a is not None:
        aud = project.campaign.get("audio", {})
        loud = loudness(path)
        target, tp_max = aud.get("loudness_target_lufs", -14), aud.get("true_peak_max_dbtp", -1)
        il, tp = loud["integrated_lufs"], loud["true_peak_dbtp"]
        silent = il is None or il == float("-inf") or il < -60
        if silent:
            warnings.append("Audio is silent (draft without VO/music) — not deliverable")
        checks.append({"check": "loudness", "pass": (not silent) and abs(il - target) <= 1.0,
                       "detail": f"{il} LUFS (target {target}±1)"})
        checks.append({"check": "true_peak", "pass": tp is not None and tp <= tp_max + 0.1,
                       "detail": f"{tp} dBTP (max {tp_max})"})
    black = detect(path, "blackdetect=d=0.25:pix_th=0.10", "black_start")
    if black:
        checks.append({"check": "no_black_frames", "pass": False, "detail": black[:5]})
    else:
        checks.append({"check": "no_black_frames", "pass": True})
    freeze = detect(path, "freezedetect=n=-60dB:d=1.5", "freeze_start")
    if freeze:
        warnings.append(f"Frozen segments (check whether intentional): {freeze[:5]}")
    report = {
        "video_id": vid, "ratio": ratio, "file": str(path.relative_to(project.root)) if path.is_relative_to(project.root) else str(path),
        "automated_pass": all(c["pass"] for c in checks),
        "checks": checks, "warnings": warnings,
        "human_checklist": [{"item": i, "signed_off_by": "", "pass": None} for i in HUMAN_CHECKLIST],
    }
    report["approved"] = False  # only a human sign-off flips this
    save_json(project.root / "output" / vid / f"{vid}_{ratio}_qc.json", report)
    return report
