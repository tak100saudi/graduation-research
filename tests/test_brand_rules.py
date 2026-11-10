"""Owner corrections from brand_facts.md, enforced in plans."""
import copy
import json

from conftest import CAMPAIGN, REPO, VIDEO, write_project
from studio.model import Project, normalize, validate_project, validate_video


def check(tmp_path, video, **kw):
    p = write_project(tmp_path, video=video, **kw)
    return validate_video(p, p.video(video["id"]))


def test_banned_phrase_is_caught_despite_diacritics_and_alef_forms(tmp_path):
    v = copy.deepcopy(VIDEO); v["shots"][0]["overlay_ar"][0]["text"] = "تأكيدٌ فوري"
    assert any("banned phrase “تأكيد فوري”" in e for e in check(tmp_path / "a", v).errors)
    v = copy.deepcopy(VIDEO); v["shots"][1]["vo_ar"] = "المكانُ موثّق"
    assert any("المكان موثق" in e and "استراحات شريكة" in e for e in check(tmp_path / "b", v).errors)
    assert normalize("أإآ موثّق") == "ااا موثق"


def test_banned_phrase_in_english_prompt_action(tmp_path):
    v = copy.deepcopy(VIDEO); v["shots"][0]["action"] = "hand taps a Tabby button"
    assert any("banned phrase “tabby”" in e for e in check(tmp_path, v).errors)


def test_forbidden_ui_feature(tmp_path):
    v = copy.deepcopy(VIDEO); v["shots"][1]["ui_notes"] = "phone shows an invoice screen"
    assert any("'invoice'" in e for e in check(tmp_path, v).errors)


def test_flex_pay_requires_on_screen_disclosure(tmp_path):
    c = copy.deepcopy(CAMPAIGN)
    c["claims_evidence"] = [{"id": "CLM_FLEX_PAY", "approved": True}]
    v = copy.deepcopy(VIDEO)
    v["shots"][0]["overlay_ar"][0]["text"] = "دفع مرن اختياري"
    assert any("DSC_FLEX_PAY" in e for e in check(tmp_path / "a", v, campaign=c).errors)
    v["shots"][1]["overlay_ar"] = [{"text": "عبر جهات تمويل مرخصة من ساما. Season Venue لا تقدّم تمويلاً.",
                                   "start_s": 1.6, "end_s": 2.9, "position": "bottom", "style": "body"}]
    v["shots"][1]["claims"] = ["CLM_FLEX_PAY"]
    assert check(tmp_path / "b", v, campaign=c).errors == []


def test_screen_recording_needs_known_flow_step_and_verified_flow(tmp_path):
    v = copy.deepcopy(VIDEO)
    v["shots"][1]["shows_product_ui"] = True
    v["shots"][1]["generation"] = {"mode": "screen_recording", "source_path": "rec.mp4", "flow_step": "STEP9"}
    r = check(tmp_path / "a", v)
    assert any("flow_step" in e for e in r.errors)
    v["shots"][1]["generation"]["flow_step"] = "STEP1_EVENT_TYPE"
    r = check(tmp_path / "b", v)
    assert r.errors == [] and any("not yet verified on the live demo" in b for b in r.blockers)


def test_cta_placeholder_blocks_production(tmp_path):
    v = copy.deepcopy(VIDEO); v["shots"][1]["overlay_ar"] = [
        {"text": "[الموقع الإلكتروني]", "start_s": 2, "end_s": 2.9, "position": "end_card", "style": "cta"}]
    assert any("placeholder" in b for b in check(tmp_path, v).blockers)


# ---- real repository brand data -------------------------------------------------

def test_repo_brand_matches_owner_kit():
    p = Project.load(REPO)
    b = p.campaign["brand"]
    kit = json.loads((REPO / "assets" / "brand" / "brand.json").read_text())
    assert b["official_tagline"] == kit["official_tagline"] == "طلب واحد.. عرض واحد.. مناسبة أسهل"
    assert b["roles"]["primary"] == kit["colors"]["logo_green"] and b["roles"]["accent"] == kit["colors"]["logo_gold"]
    for k in ("logo_path", "logo_dark_bg_path", "logo_original_path"):
        assert (REPO / b[k]).is_file()
    assert b["font_licensed"] is False and b["green_system_decision"] == "#33650C"
    assert b["cta_text"] == "قريبًا" and (REPO / b["draft_font_path"]).is_file()
    assert (REPO / "assets/brand/fonts/OFL.txt").is_file()


def test_repo_rules_cover_every_brand_facts_correction():
    phrases = {normalize(x["phrase"]) for x in Project.load(REPO).campaign["banned_phrases"]}
    for must in ("السعر قدامك", "احجز في دقائق", "تأكيد فوري", "بدون ولا مكالمة", "الدفع داخل المنصة",
                 "المكان موثّق", "تابي", "تمارا", "حجوزات مؤكدة ومدفوعة", "كيف نوثّق", "demo.wady.sa"):
        assert normalize(must) in phrases, must


def test_repo_claims_evidence_wording_passes_its_own_rules():
    p = Project.load(REPO)
    from studio.model import banned_hits
    for e in p.campaign["claims_evidence"]:
        assert banned_hits(p, e["wording"]) == [], e["id"]


def test_repo_product_flow_has_six_steps_plus_confirmation_and_is_unverified():
    flow = Project.load(REPO).product_flow
    assert [s["order"] for s in flow["steps"]] == list(range(1, 8))
    assert flow["verified_against_demo"] is False
    assert any("404" in x["result"] for x in flow["verification_log"])


def test_repo_x5_y3_carry_mandatory_corrections():
    p = Project.load(REPO)
    assert "عمولة" in p.video("X5")["mandatory_corrections"][0]["with"]
    assert "6 خطوات" in p.video("Y3")["mandatory_corrections"][0]["with"]
    assert validate_project(p).errors == []
