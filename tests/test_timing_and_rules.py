import copy

from conftest import write_project
from studio.model import count_words, scan_claims, validate_video


def errs(tmp_path, video, **kw):
    p = write_project(tmp_path, video=video, **kw)
    return validate_video(p, p.video(video["id"]))


def test_fixture_is_clean(tmp_path, video):
    r = errs(tmp_path, video)
    assert r.errors == [] and r.blockers == []


def test_gap_overlap_and_total_mismatch(tmp_path, video):
    v = copy.deepcopy(video); v["shots"][1]["start_s"] = 1.6
    assert any("timing gap" in e for e in errs(tmp_path / "a", v).errors)
    v = copy.deepcopy(video); v["shots"][1]["start_s"] = 1.4
    assert any("timing overlap" in e for e in errs(tmp_path / "b", v).errors)
    v = copy.deepcopy(video); v["duration_s"] = 3.5
    assert any("shots total 3.000s" in e for e in errs(tmp_path / "c", v).errors)


def test_float_durations_do_not_drift(tmp_path, video):
    v = copy.deepcopy(video)
    v["duration_s"] = 0.3
    v["shots"] = [dict(copy.deepcopy(video["shots"][1]), id=f"DEMO1_{i+1:02d}", start_s=round(i * 0.1, 1),
                       end_s=round((i + 1) * 0.1, 1), characters=[], wardrobe={}) for i in range(3)]
    assert errs(tmp_path, v).errors == []


def test_shot_ids_must_be_sequential(tmp_path, video):
    v = copy.deepcopy(video); v["shots"][1]["id"] = "DEMO1_05"
    assert any("should be DEMO1_02" in e for e in errs(tmp_path, v).errors)


def test_arabic_vo_pacing(tmp_path, video):
    v = copy.deepcopy(video)
    v["shots"][0]["vo_ar"] = "هذا نص طويل جدا لا يمكن قراءته في ثانية ونصف أبدا"
    assert any("VO too fast" in e for e in errs(tmp_path, v).errors)


def test_word_count_ignores_diacritics_and_tatweel():
    assert count_words("مَوْسِمُ الـــفعاليات، أهلاً!") == 3


def test_overlay_must_stay_inside_video(tmp_path, video):
    v = copy.deepcopy(video); v["shots"][0]["overlay_ar"][0]["end_s"] = 9
    assert any("past the end" in e for e in errs(tmp_path, v).errors)


def test_wardrobe_continuity_inside_scene(tmp_path, video):
    v = copy.deepcopy(video); v["shots"][1]["wardrobe"]["CHAR_A"] = "W2"
    assert any("wardrobe for CHAR_A changes" in e for e in errs(tmp_path, v).errors)


def test_unknown_character_and_location(tmp_path, video):
    v = copy.deepcopy(video); v["shots"][0]["characters"] = ["NOBODY"]; v["shots"][0]["location"] = "NOWHERE"
    e = errs(tmp_path, v).errors
    assert any("unknown character NOBODY" in x for x in e) and any("unknown location NOWHERE" in x for x in e)


def test_generative_faces_need_consent_and_references(tmp_path, video):
    from conftest import CONTINUITY
    c = copy.deepcopy(CONTINUITY)
    c["characters"][0]["consent"]["status"] = "missing"; c["characters"][0]["reference_images"] = []
    b = errs(tmp_path, video, continuity=c).blockers
    assert any("signed consent" in x for x in b) and any("reference images" in x for x in b)


def test_claim_guard_patterns():
    assert "price" in scan_claims("ابتداءً من 500 ريال")
    assert "number" in scan_claims("أكثر من ١٠٠ مكان")
    assert "guarantee" in scan_claims("حجزك مضمون")
    assert "financing" in scan_claims("تقسيط بدون فوائد")
    assert "verification" in scan_claims("أماكن موثقة")
    assert "testimonial" in scan_claims("قالت سارة إن التجربة رائعة")
    assert scan_claims("انتقال سلس إلى المكان") == []  # 'قال' inside a word is not a testimonial
    assert scan_claims("حياكم الله") == []


def test_claims_block_without_evidence_and_pass_with_approved_evidence(tmp_path, video):
    from conftest import CAMPAIGN
    v = copy.deepcopy(video)
    v["shots"][0]["overlay_ar"][0]["text"] = "أسعار تبدأ من 99"
    assert any("possible claim" in e for e in errs(tmp_path / "a", v).errors)
    v["shots"][0]["claims"] = ["CLM1"]
    c = copy.deepcopy(CAMPAIGN); c["claims_evidence"] = [{"id": "CLM1", "approved": True, "source": "signed price sheet"}]
    assert errs(tmp_path / "b", v, campaign=c).errors == []


def test_forbidden_sfx(tmp_path, video):
    v = copy.deepcopy(video); v["shots"][0]["sfx"] = "Alert Chime on reveal"
    assert any("forbidden SFX" in e for e in errs(tmp_path / "a", v).errors)
    v["shots"][0]["sfx"] = "soft vibration, no alert chime"
    assert not any("forbidden SFX" in e for e in errs(tmp_path / "b", v).errors)


def test_product_ui_must_be_authentic_recording(tmp_path, video):
    v = copy.deepcopy(video); v["shots"][1]["shows_product_ui"] = True
    assert any("authentic screen recording" in e for e in errs(tmp_path / "a", v).errors)
    v["shots"][1]["generation"] = {"mode": "screen_recording", "source_path": "assets/screen_recordings/x.mp4"}
    assert any("screen recording missing" in b for b in errs(tmp_path / "b", v).blockers)
