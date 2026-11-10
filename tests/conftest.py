"""Fixture project: a tiny, clearly fake campaign used only to exercise the tooling.
Nothing here is Season Venue creative content."""
from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from studio.model import Project  # noqa: E402

CAMPAIGN = {
    "campaign": "TEST FIXTURE",
    "source_document": "source/source_campaign.pdf",
    "source_status": "reconciled",
    "expected_video_count": 1,
    "video_ids": ["DEMO1"],
    "output_targets": {"9x16": [180, 320], "16x9": [320, 180]},
    "fps": 24,
    "brand": {"official_assets_present": False, "logo_path": "assets/brand/logo.png", "font_path": "assets/brand/font.ttf",
              "colors": {"green": "#0F5132", "beige": "#EFE6D8", "muted_gold": "#C2A15A"}},
    "audio": {"loudness_target_lufs": -14.0, "true_peak_max_dbtp": -1.0, "forbidden_sfx": ["alert chime", "ribbon cutting"]},
    "vo_pacing": {"comfortable_words_per_second": 2.2, "max_words_per_second": 2.6, "tail_silence_s": 0.3},
    "claims_evidence": [],
}
CONTINUITY = {
    "global_look": {"anchor_description": "FIXTURE LOOK warm daylight", "palette_tokens": ["#0F5132"]},
    "characters": [{"id": "CHAR_A", "defined": True, "anchor_description": "FIXTURE ANCHOR A, a man in his thirties",
                    "wardrobe": {"W1": "white thobe", "W2": "navy bisht"},
                    "reference_images": ["assets/references/char_a.png"],
                    "consent": {"status": "signed", "record_path": "x"}, "seed": 7}],
    "locations": [{"id": "LOC_A", "defined": True, "anchor_description": "FIXTURE COURTYARD", "time_of_day": "golden hour",
                   "reference_images": ["assets/references/loc_a.png"], "licence": {"status": "signed"}}],
    "negative_prompt_global": ["on-screen text", "logos"],
}
SHOTS = [
    {"id": "DEMO1_01", "start_s": 0, "end_s": 1.5, "beat": "hook", "scene": "SC1",
     "characters": ["CHAR_A"], "wardrobe": {"CHAR_A": "W1"}, "location": "LOC_A",
     "action": "walks into frame and smiles", "lighting": "soft key from window",
     "camera": {"shot_size": "MS", "angle": "eye-level", "lens_mm": 35, "movement": "slow push-in"},
     "vo_ar": "حياكم الله", "overlay_ar": [{"text": "عنوان تجريبي", "start_s": 0.2, "end_s": 1.4, "position": "top", "style": "headline"}],
     "generation": {"mode": "text_to_video", "seed": 7}, "status": "prompt_ready"},
    {"id": "DEMO1_02", "start_s": 1.5, "end_s": 3.0, "beat": "end", "scene": "SC1",
     "characters": ["CHAR_A"], "wardrobe": {"CHAR_A": "W1"}, "location": "LOC_A",
     "action": "looks toward the courtyard", "camera": {"shot_size": "WS", "lens_mm": 24, "movement": "static"},
     "vo_ar": "", "overlay_ar": [], "generation": {"mode": "image_to_video"}, "status": "prompt_ready"},
]
VIDEO = {"id": "DEMO1", "kind": "hero", "duration_s": 3.0, "duration_source": "pdf", "concept": "fixture",
         "source_status": "reconciled", "aspect_ratios": ["9x16", "16x9"], "shots": SHOTS}

VERIFIED_SPEC = {
    "doc_url": "http://fixture/docs", "verified": True, "verified_on": "2026-01-01", "model": "fixture-model",
    "auth": {"type": "header", "header": "X-Fixture-Key", "prefix": "", "key_env": "SV_FIXTURE_KEY"},
    "submit": {"method": "POST", "url": "{base}/submit",
               "body_template": {"model": "{model}", "prompt": "{prompt}", "negative": "{negative_prompt}",
                                 "seconds": "{duration_s}", "ratio": "{aspect_ratio}", "seed": "{seed}"}},
    "job_id_path": "job.id",
    "poll": {"method": "GET", "url": "{base}/jobs/{job_id}", "interval_s": 0, "timeout_s": 10},
    "status_path": "state", "done_values": ["done"], "failed_values": ["failed"],
    "video_url_path": "result.videos.0.url",
    "allowed_durations_s": [2, 4, 8], "allowed_aspect_ratios": {"9x16": "9:16", "16x9": "16:9"},
    "supports_negative_prompt": True, "supports_reference_images": False,
}


def write_project(root: Path, video=None, campaign=None, continuity=None) -> Project:
    (root / "plans" / "videos").mkdir(parents=True, exist_ok=True)
    for d in ("config", "state", "assets/clips", "assets/audio", "assets/brand", "source"):
        (root / d).mkdir(parents=True, exist_ok=True)
    (root / "source" / "source_campaign.pdf").write_bytes(b"%PDF-fixture")
    c = copy.deepcopy(campaign or CAMPAIGN)
    v = copy.deepcopy(video or VIDEO)
    (root / "plans" / "campaign.json").write_text(json.dumps(c, ensure_ascii=False))
    (root / "plans" / "continuity.json").write_text(json.dumps(continuity or CONTINUITY, ensure_ascii=False))
    (root / "plans" / "videos" / f"{v['id']}.json").write_text(json.dumps(v, ensure_ascii=False))
    shutil.copy(REPO / "config" / "pricing.json", root / "config" / "pricing.json")
    providers = json.loads((REPO / "config" / "providers.json").read_text())
    providers["providers"]["fixture"] = copy.deepcopy(VERIFIED_SPEC)
    (root / "config" / "providers.json").write_text(json.dumps(providers))
    return Project.load(root)


@pytest.fixture
def proj(tmp_path):
    return write_project(tmp_path)


@pytest.fixture
def video():
    return copy.deepcopy(VIDEO)


def ffmpeg(*args):
    subprocess.run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", *args], check=True)


def make_clip(path: Path, w: int, h: int, seconds: float = 2.0):
    path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg("-f", "lavfi", "-i", f"testsrc2=size={w}x{h}:rate=24:duration={seconds}",
           "-c:v", "libx264", "-pix_fmt", "yuv420p", str(path))


def make_wav(path: Path, freq: int, seconds: float = 3.0, volume: float = 0.3):
    path.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg("-f", "lavfi", "-i", f"sine=frequency={freq}:duration={seconds}:sample_rate=48000",
           "-af", f"volume={volume}", "-ac", "2", str(path))


needs_ffmpeg = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="ffmpeg not installed")
