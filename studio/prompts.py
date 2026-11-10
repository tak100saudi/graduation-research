"""Per-shot prompt packages.

A package keeps four things strictly separate:
  * prompt_en         - what the video model sees (English, cinematic, NO text)
  * negative_prompt   - global + shot-specific exclusions
  * vo_ar             - Saudi-dialect voice-over line (goes to the licensed VO talent / TTS)
  * overlays_ar       - Arabic on-screen text, rendered later as a separate layer
Arabic text is never sent to the video model: generative models garble script,
and overlays must use the official typography.
"""
from __future__ import annotations

import hashlib
import json

from .model import Project, to_ms

CAMERA_ORDER = ["shot_size", "angle", "lens_mm", "movement", "focus"]
SHOT_SIZE_NAMES = {
    "ECU": "extreme close-up", "CU": "close-up", "MCU": "medium close-up",
    "MS": "medium shot", "MWS": "medium wide shot", "WS": "wide shot", "EWS": "extreme wide shot",
    "OTS": "over-the-shoulder shot", "POV": "point-of-view shot", "INSERT": "insert detail shot",
}


def _camera_phrase(cam: dict) -> str:
    parts = []
    if cam.get("shot_size"):
        parts.append(SHOT_SIZE_NAMES.get(cam["shot_size"], cam["shot_size"]))
    if cam.get("angle"):
        parts.append(f"{cam['angle']} angle")
    if cam.get("lens_mm"):
        parts.append(f"{cam['lens_mm']}mm lens")
    if cam.get("aperture"):
        parts.append(f"f/{cam['aperture']}")
    if cam.get("movement"):
        parts.append(cam["movement"])
    if cam.get("focus"):
        parts.append(cam["focus"])
    return ", ".join(parts)


def build_package(project: Project, video: dict, shot: dict, ratio: str) -> dict:
    chars = project.characters()
    locs = project.locations()
    look = project.continuity.get("global_look", {})

    segments: list[str] = []
    cam = _camera_phrase(shot.get("camera", {}))
    if cam:
        segments.append(cam[0].upper() + cam[1:])
    for cid in shot.get("characters", []):
        c = chars.get(cid, {})
        anchor = c.get("anchor_description", "").strip()
        wardrobe_id = shot.get("wardrobe", {}).get(cid)
        wardrobe = c.get("wardrobe", {}).get(wardrobe_id, "") if wardrobe_id else ""
        if anchor:
            segments.append(anchor + (f", wearing {wardrobe}" if wardrobe else ""))
    if shot.get("action"):
        segments.append(shot["action"].strip())
    loc = locs.get(shot.get("location", ""), {})
    if loc.get("anchor_description"):
        tod = f", {loc['time_of_day']}" if loc.get("time_of_day") else ""
        segments.append("Setting: " + loc["anchor_description"] + tod)
    if shot.get("lighting"):
        segments.append("Lighting: " + shot["lighting"].strip())
    if look.get("anchor_description"):
        segments.append("Look: " + look["anchor_description"])
    framing = "vertical 9:16 composition" if ratio == "9x16" else "horizontal 16:9 composition"
    segments.append(f"{framing}, {project.campaign.get('fps', 24)}fps, no on-screen text")
    prompt_en = ". ".join(s.rstrip(". ") for s in segments if s) + "."

    negative = list(project.continuity.get("negative_prompt_global", []))
    negative += shot.get("negative_extra", [])
    dur_s = (to_ms(shot["end_s"]) - to_ms(shot["start_s"])) / 1000

    overlays = []
    for ov in shot.get("overlay_ar", []):
        overlays.append({
            "text": ov.get("text", ""),
            "start_s": ov.get("start_s"), "end_s": ov.get("end_s"),
            "position": ov.get("position", "lower_third"),
            "style": ov.get("style", "body"),
            "direction": "rtl",
            "font": project.campaign.get("brand", {}).get("font_path"),
            "color": ov.get("color", project.campaign.get("brand", {}).get("roles", {}).get("light")),
        })

    gen = shot.get("generation", {})
    pkg = {
        "video_id": video["id"],
        "shot_id": shot["id"],
        "ratio": ratio,
        "duration_s": round(dur_s, 3),
        "timecode": {"start_s": shot["start_s"], "end_s": shot["end_s"]},
        "mode": gen.get("mode"),
        "prompt_en": prompt_en,
        "negative_prompt": ", ".join(negative),
        "reference_images": _reference_images(project, shot),
        "seed": gen.get("seed"),
        "vo_ar": shot.get("vo_ar", ""),
        "vo_speaker": shot.get("vo_speaker", ""),
        "subtitle_ar": shot.get("subtitle_ar", shot.get("vo_ar", "")),
        "overlays_ar": overlays,
        "sfx": shot.get("sfx", ""),
        "send_to_video_model": gen.get("mode") in ("text_to_video", "image_to_video"),
    }
    pkg["prompt_hash"] = hashlib.sha256(
        json.dumps([pkg["prompt_en"], pkg["negative_prompt"], pkg["reference_images"], pkg["seed"], ratio],
                   ensure_ascii=False).encode()
    ).hexdigest()[:16]
    return pkg


def _reference_images(project: Project, shot: dict) -> list[str]:
    refs: list[str] = []
    chars = project.characters()
    for cid in shot.get("characters", []):
        refs += chars.get(cid, {}).get("reference_images", [])
    loc = project.locations().get(shot.get("location", ""), {})
    refs += loc.get("reference_images", [])
    refs += shot.get("generation", {}).get("reference_images", [])
    seen, out = set(), []
    for r in refs:
        if r not in seen:
            seen.add(r)
            out.append(r)
    return out


def build_video_packages(project: Project, vid: str) -> list[dict]:
    video = project.video(vid)
    out = []
    for ratio in video.get("aspect_ratios", []):
        for shot in video.get("shots", []):
            out.append(build_package(project, video, shot, ratio))
    return out
