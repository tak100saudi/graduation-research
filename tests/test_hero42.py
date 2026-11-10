"""HERO42 script: reconciled with source_campaign.pdf, corrected by brand_facts.md."""
import re

from conftest import REPO
from studio.model import Project, count_words, normalize, scan_claims, to_ms, validate_video
from studio.prompts import build_video_packages

P = Project.load(REPO)
V = P.video("HERO42")
S = V["shots"]
ARABIC = re.compile(r"[؀-ۿ]")


def test_exact_42s_and_pdf_beat_boundaries_preserved():
    assert V["duration_s"] == 42 and V["fps"] == 24
    starts = {to_ms(s["start_s"]) for s in S} | {42000}
    for t in (0, 3, 7, 11, 14, 17, 22, 27, 31, 37, 42):   # PDF shot table, p4-5
        assert t * 1000 in starts, t
    assert to_ms(S[-1]["end_s"]) == 42000


def test_no_structural_errors_and_pacing_within_limit():
    r = validate_video(P, V)
    assert r.errors == []
    for s in S:
        if s["vo_ar"]:
            w = count_words(s["vo_ar"]) / (s["vo_end_s"] - s["vo_start_s"])
            assert w <= 2.6, (s["id"], w)
            assert s["vo_end_s"] <= 42 - 0.3


def test_real_customer_journey_in_order():
    vo = [normalize(s["vo_ar"]) for s in S]
    def first(snippet):
        return next(i for i, t in enumerate(vo) if normalize(snippet) in t)
    order = [first("طلب واحد"), first("نتواصل معك"), first("بعرض واحد"), first("وعقد وعربون"), first("تعيش مناسبتك")]
    assert order == sorted(order) and len(set(order[:2])) == 2


def test_banned_pdf_claims_are_gone():
    copy = normalize(" ".join([s["vo_ar"] for s in S] + [o["text"] for s in S for o in s["overlay_ar"]]))
    for banned in ("السعر قدامك", "موثّق", "الدفع داخل المنصة", "محفوظ ومضمون", "دفع آمن", "تنظّم سوق", "احجز"):
        assert normalize(banned) not in copy, banned


def test_every_claim_trigger_has_evidence():
    ev = {e["id"] for e in P.campaign["claims_evidence"] if e["approved"]}
    for s in S:
        for t in [s["vo_ar"]] + [o["text"] for o in s["overlay_ar"]]:
            if scan_claims(t):
                assert set(s["claims"]) & ev, (s["id"], t)


def test_ui_only_via_real_recording_of_request_flow():
    ui = [s for s in S if s.get("shows_product_ui")]
    assert [s["id"] for s in ui] == ["HERO42_07"]
    steps = {st["id"] for st in P.product_flow["steps"]}
    assert set(ui[0]["screen_insert"]["flow_steps"]) <= steps
    for s in S:
        if "phone" in s["action"] and s["generation"]["mode"] != "graphics":
            assert "blank green screen" in s["action"] or "screen is not visible" in s["action"], s["id"]


def test_end_card_logo_and_cta():
    assert [s["id"] for s in S if s.get("logo")] == ["HERO42_12"]
    assert S[-1]["logo"]["width_frac"] == 0.30
    assert any(o["text"] == "قريبًا" for o in S[-1]["overlay_ar"])
    assert S[-1]["generation"]["color"] == "#33650C"


def test_prompts_english_only_with_character_anchor_and_ratio_plan():
    pk = build_video_packages(P, "HERO42")
    gen = [p for p in pk if p["send_to_video_model"]]
    for p in gen:
        assert not ARABIC.search(p["prompt_en"]) and not ARABIC.search(p["negative_prompt"])
    c1 = next(c for c in P.continuity["characters"] if c["id"] == "C1")["anchor_description"]
    with_c1 = {s["id"] for s in S if "C1" in s["characters"]}
    assert with_c1 == {"HERO42_02", "HERO42_03", "HERO42_04", "HERO42_05", "HERO42_07", "HERO42_08", "HERO42_10", "HERO42_11"}
    assert all(c1.lower() in p["prompt_en"].lower() for p in gen if p["shot_id"] in with_c1)
    ratios = {(p["shot_id"], p["ratio"]) for p in gen}
    assert ("HERO42_03", "9x16") in ratios and ("HERO42_03", "16x9") not in ratios   # phone close-up: vertical only
    assert ("HERO42_01", "16x9") in ratios and ("HERO42_01", "9x16") not in ratios   # 16:9 master, cropped later
    assert "smiling" in next(p for p in gen if p["shot_id"] == "HERO42_02")["negative_prompt"]
    assert "smiling" not in next(p for p in gen if p["shot_id"] == "HERO42_10")["negative_prompt"]


def test_overlay_layer_respects_9x16_safe_area(tmp_path):
    from studio.render import write_ass
    ass = write_ass(P, V, "9x16", tmp_path / "h.ass").read_text(encoding="utf-8")
    for line in ass.splitlines():
        if line.startswith("Dialogue:"):
            f = line.split(",", 9)
            margin_v, text = int(f[7]), f[9]
            if "\\an2" in text:
                assert margin_v >= 420, line      # bottom safe area
            if "\\an8" in text:
                assert margin_v >= 250, line      # top safe area
    assert "Tajawal" in ass


def test_animatic_is_exactly_42s_in_both_ratios():
    import shutil
    if not shutil.which("ffmpeg"):
        return
    from studio import animatic
    from studio.qc import probe
    for ratio, size in (("9x16", (1080, 1920)), ("16x9", (1920, 1080))):
        out = animatic.build(P, "HERO42", ratio)
        info = probe(out)
        v = next(s for s in info["streams"] if s["codec_type"] == "video")
        assert (v["width"], v["height"]) == size and v["r_frame_rate"] == "24/1"
        assert abs(float(info["format"]["duration"]) - 42.0) < 0.05
