"""Plan loading and validation for the Season Venue studio.

All timing is handled in integer milliseconds internally to avoid float drift.
Validation issues are split into:
  * errors    - the plan is structurally wrong (always fail)
  * blockers  - the plan is incomplete for production (fail with --production)
  * warnings  - worth a human look
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

SHOT_STATUSES = [
    "pending_source",   # waiting for the PDF
    "scripted",         # VO/timing reconciled with PDF
    "prompt_ready",     # prompt reviewed
    "test_generated",   # one provider take exists
    "generated",        # final take exists
    "approved",         # creative sign-off
    "qc_passed",
    "rejected",
]
GEN_MODES = {"text_to_video", "image_to_video", "screen_recording", "graphics", "live_action"}
OVERLAY_POSITIONS = {"top", "center", "lower_third", "bottom", "end_card"}

# Claims that must never appear without approved evidence (CLAUDE.md rules).
CLAIM_PATTERNS: list[tuple[str, str]] = [
    ("price", r"(ريال|ر\.س|SAR|\bUSD\b|\$|﷼|سعر|أسعار|price|\bfree\b|مجان)"),
    ("number", r"[0-9٠-٩]+"),
    ("guarantee", r"(ضمان|مضمون|نضمن|guarantee|guaranteed)"),
    ("verification", r"(موثق|موثّق|معتمد|verified|certified)"),
    ("financing", r"(تقسيط|تمويل|أقساط|financing|instal?ments?|BNPL)"),
    ("payment_protection", r"(دفع آمن|حماية الدفع|استرداد|secure payment|refund)"),
    ("testimonial", r"(\b(قال|قالت|يقول|تقول)\b|review|testimonial|★)"),
    ("superlative", r"(\b(الأفضل|الأول|الأكبر)\b|رقم واحد|\bbest\b|#1|number one|largest)"),
]

ARABIC_DIACRITICS = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭـ]")
WORD_RE = re.compile(r"[\w؀-ۿ]+", re.UNICODE)


def to_ms(seconds: float | int | None) -> int | None:
    if seconds is None:
        return None
    return int(round(float(seconds) * 1000))


def count_words(text: str) -> int:
    return len(WORD_RE.findall(ARABIC_DIACRITICS.sub("", text or "")))


def load_json(path: Path) -> Any:
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(data, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


@dataclass
class Project:
    root: Path
    campaign: dict
    continuity: dict
    videos: dict[str, dict]

    @classmethod
    def load(cls, root: Path | str = ROOT) -> "Project":
        root = Path(root)
        campaign = load_json(root / "plans" / "campaign.json")
        continuity = load_json(root / "plans" / "continuity.json")
        videos = {}
        for p in sorted((root / "plans" / "videos").glob("*.json")):
            v = load_json(p)
            videos[v.get("id", p.stem)] = v
        return cls(root, campaign, continuity, videos)

    def characters(self) -> dict[str, dict]:
        return {c["id"]: c for c in self.continuity.get("characters", [])}

    def locations(self) -> dict[str, dict]:
        return {c["id"]: c for c in self.continuity.get("locations", [])}

    def video(self, vid: str) -> dict:
        if vid not in self.videos:
            raise KeyError(f"Unknown video id {vid!r}. Known: {', '.join(self.videos)}")
        return self.videos[vid]

    def clip_path(self, vid: str, shot_index: int, ratio: str | None = None) -> Path:
        base = self.root / "assets" / "clips"
        if ratio:
            specific = base / f"{vid}_{shot_index:02d}_{ratio}.mp4"
            if specific.exists():
                return specific
        return base / f"{vid}_{shot_index:02d}.mp4"


@dataclass
class Report:
    errors: list[str] = field(default_factory=list)
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def ok(self, production: bool = False) -> bool:
        return not self.errors and (not production or not self.blockers)

    def extend(self, other: "Report") -> None:
        self.errors += other.errors
        self.blockers += other.blockers
        self.warnings += other.warnings

    def as_dict(self) -> dict:
        return {"errors": self.errors, "blockers": self.blockers, "warnings": self.warnings}


def scan_claims(text: str) -> list[str]:
    hits = []
    for name, pat in CLAIM_PATTERNS:
        if re.search(pat, text or "", flags=re.IGNORECASE):
            hits.append(name)
    return hits


def shot_texts(shot: dict) -> list[str]:
    out = [shot.get("vo_ar", "")]
    out += [o.get("text", "") for o in shot.get("overlay_ar", [])]
    return [t for t in out if t]


def validate_video(project: Project, video: dict) -> Report:
    r = Report()
    vid = video.get("id", "?")
    pacing = project.campaign.get("vo_pacing", {})
    max_wps = float(pacing.get("max_words_per_second", 2.6))
    comfy_wps = float(pacing.get("comfortable_words_per_second", 2.2))
    tail_ms = to_ms(pacing.get("tail_silence_s", 0.3))
    chars = project.characters()
    locs = project.locations()
    evidence = {e["id"]: e for e in project.campaign.get("claims_evidence", [])}

    status = video.get("source_status")
    if status in ("pending_source", "unidentified"):
        r.blockers.append(f"{vid}: source_status={status} — reconcile with source_campaign.pdf")
    if not video.get("concept"):
        r.blockers.append(f"{vid}: concept is empty")

    dur_ms = to_ms(video.get("duration_s"))
    if dur_ms is None:
        r.blockers.append(f"{vid}: duration_s unknown")
    elif dur_ms <= 0:
        r.errors.append(f"{vid}: duration_s must be > 0")
    if video.get("duration_source") == "inferred_from_id":
        r.warnings.append(f"{vid}: duration inferred from the ID; confirm against PDF")

    for ratio in video.get("aspect_ratios", []):
        if ratio not in project.campaign.get("output_targets", {}):
            r.errors.append(f"{vid}: unknown aspect ratio {ratio}")

    shots = video.get("shots", [])
    if not shots:
        r.blockers.append(f"{vid}: no shots planned")
        return r

    cursor = 0
    seen_ids = set()
    wardrobe_by_char_scene: dict[tuple[str, str], str] = {}
    for i, shot in enumerate(shots, start=1):
        sid = shot.get("id", f"#{i}")
        expected_id = f"{vid}_{i:02d}"
        if sid != expected_id:
            r.errors.append(f"{sid}: shot id should be {expected_id} (sequential, zero-padded)")
        if sid in seen_ids:
            r.errors.append(f"{sid}: duplicate shot id")
        seen_ids.add(sid)

        s, e = to_ms(shot.get("start_s")), to_ms(shot.get("end_s"))
        if s is None or e is None:
            r.errors.append(f"{sid}: start_s/end_s required")
            continue
        if e <= s:
            r.errors.append(f"{sid}: end_s must be after start_s")
        if s != cursor:
            kind = "gap" if s > cursor else "overlap"
            r.errors.append(f"{sid}: timing {kind} — starts at {s/1000:.3f}s, previous shot ended {cursor/1000:.3f}s")
        cursor = max(cursor, e)

        st = shot.get("status", "pending_source")
        if st not in SHOT_STATUSES:
            r.errors.append(f"{sid}: unknown status {st!r}")
        mode = shot.get("generation", {}).get("mode")
        if mode not in GEN_MODES:
            r.errors.append(f"{sid}: generation.mode must be one of {sorted(GEN_MODES)}")

        # Continuity references
        for cid in shot.get("characters", []):
            c = chars.get(cid)
            if not c:
                r.errors.append(f"{sid}: unknown character {cid}")
                continue
            if not c.get("defined") or not c.get("anchor_description"):
                r.blockers.append(f"{sid}: character {cid} not defined in continuity bible")
            if mode in ("text_to_video", "image_to_video"):
                if c.get("consent", {}).get("status") != "signed":
                    r.blockers.append(f"{sid}: character {cid} has no signed consent record")
                if not c.get("reference_images"):
                    r.blockers.append(f"{sid}: character {cid} has no reference images for identity lock")
            scene = shot.get("scene", "")
            wd = shot.get("wardrobe", {}).get(cid)
            if scene and wd:
                prev = wardrobe_by_char_scene.setdefault((cid, scene), wd)
                if prev != wd:
                    r.errors.append(f"{sid}: wardrobe for {cid} changes inside scene {scene} ({prev} -> {wd})")
        loc = shot.get("location")
        if loc:
            l = locs.get(loc)
            if not l:
                r.errors.append(f"{sid}: unknown location {loc}")
            elif not l.get("defined") or not l.get("anchor_description"):
                r.blockers.append(f"{sid}: location {loc} not defined in continuity bible")

        # Screens must be authentic recordings, never generated
        if shot.get("shows_product_ui") and mode != "screen_recording":
            r.errors.append(f"{sid}: product UI must use an authentic screen recording (mode=screen_recording)")
        if mode == "screen_recording":
            rec = shot.get("generation", {}).get("source_path")
            if not rec or not (project.root / rec).exists():
                r.blockers.append(f"{sid}: authentic screen recording missing ({rec or 'no source_path'})")

        # VO pacing
        vo = shot.get("vo_ar", "")
        if vo:
            vs = to_ms(shot.get("vo_start_s", shot.get("start_s")))
            ve = to_ms(shot.get("vo_end_s", shot.get("end_s")))
            window = (ve - vs) / 1000 if ve and vs is not None else 0
            words = count_words(vo)
            if window <= 0:
                r.errors.append(f"{sid}: VO window is empty")
            else:
                wps = words / window
                if wps > max_wps:
                    r.errors.append(f"{sid}: Arabic VO too fast — {words} words in {window:.2f}s = {wps:.2f} w/s (max {max_wps})")
                elif wps > comfy_wps:
                    r.warnings.append(f"{sid}: Arabic VO tight — {wps:.2f} w/s (comfortable {comfy_wps})")
            if dur_ms is not None and ve is not None and ve > dur_ms - tail_ms:
                r.warnings.append(f"{sid}: VO ends within {tail_ms}ms of video end")

        # Overlays inside shot/video
        for j, ov in enumerate(shot.get("overlay_ar", []), start=1):
            os_, oe = to_ms(ov.get("start_s")), to_ms(ov.get("end_s"))
            if os_ is None or oe is None or oe <= os_:
                r.errors.append(f"{sid}: overlay {j} needs valid start_s/end_s")
            elif dur_ms is not None and oe > dur_ms:
                r.errors.append(f"{sid}: overlay {j} runs past the end of the video")
            if ov.get("position") and ov["position"] not in OVERLAY_POSITIONS:
                r.errors.append(f"{sid}: overlay {j} position must be one of {sorted(OVERLAY_POSITIONS)}")
            if not ov.get("text"):
                r.errors.append(f"{sid}: overlay {j} has no text")

        # Claim guard
        for text in shot_texts(shot):
            hits = scan_claims(text)
            if hits:
                refs = shot.get("claims", [])
                approved = [c for c in refs if evidence.get(c, {}).get("approved")]
                if not approved:
                    r.errors.append(
                        f"{sid}: possible claim ({', '.join(hits)}) in “{text}” without approved evidence in campaign.claims_evidence"
                    )

        # SFX guard
        sfx = (shot.get("sfx") or "").lower()
        for bad in project.campaign.get("audio", {}).get("forbidden_sfx", []):
            if bad in sfx:
                r.errors.append(f"{sid}: forbidden SFX '{bad}'")

    if dur_ms is not None and cursor != dur_ms:
        r.errors.append(f"{vid}: shots total {cursor/1000:.3f}s but video duration is {dur_ms/1000:.3f}s")
    return r


def validate_project(project: Project) -> Report:
    r = Report()
    c = project.campaign
    expected = c.get("expected_video_count")
    ids = c.get("video_ids", [])
    if expected is not None and len(ids) != expected:
        r.errors.append(f"campaign: expected {expected} videos, video_ids lists {len(ids)}")
    if len(set(ids)) != len(ids):
        r.errors.append("campaign: duplicate video ids")
    for vid in ids:
        if vid not in project.videos:
            r.errors.append(f"campaign: plans/videos/{vid}.json missing")
    for vid in project.videos:
        if vid not in ids:
            r.errors.append(f"campaign: plans/videos/{vid}.json not listed in video_ids")
    src = project.root / c.get("source_document", "source/source_campaign.pdf")
    if not src.exists():
        r.blockers.append(f"campaign: source document not found at {src.relative_to(project.root)}")
    brand = c.get("brand", {})
    if not brand.get("official_assets_present"):
        r.blockers.append("brand: official Season Venue logo/font not supplied — using suggested palette only")
    for vid in ids:
        if vid in project.videos:
            r.extend(validate_video(project, project.videos[vid]))
    return r
