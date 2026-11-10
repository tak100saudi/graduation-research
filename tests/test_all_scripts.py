"""All 22 scripts: PDF durations and beats, owner corrections, honest CTAs."""
import pytest

from conftest import REPO
from studio.model import Project, count_words, normalize, to_ms, validate_project, validate_video

P = Project.load(REPO)
IDS = P.campaign["video_ids"]
# source_campaign.pdf: duration and the beat boundaries of each shot table
PDF = {
    "HERO42": (42, [0, 3, 7, 11, 14, 17, 22, 27, 31, 37]), "HERO15": (15, [0, 3, 8, 12]),
    "T1": (15, [0, 3, 6, 11]), "T2": (18, [0, 3, 6, 12, 16]), "T3": (15, [0, 4, 7, 12]), "T4": (16, [0, 3, 7, 12]),
    "T5": (15, [0, 3, 7, 12]), "S1": (15, [0, 3, 8, 12]), "S2": (15, [0, 4, 7, 12]), "S3": (15, [0, 3, 9, 12]),
    "S4": (15, [0, 4, 6, 12]), "S5": (18, [0, 3, 9, 14]), "X1": (15, [0, 4, 8, 12]), "X2": (20, [0, 2, 14, 18]),
    "X3": (18, [0, 4, 10, 15]), "X4": (15, [0, 3, 11]), "X5": (18, [0, 4, 10, 15]), "Y1": (18, [0, 3, 9, 14]),
    "Y2": (20, [0, 4, 10, 16]), "Y3": (20, [0, 3, 14, 17]), "Y4": (16, [0, 3, 7, 12]), "Y5": (15, [0, 3, 10, 12]),
}


def copy_of(v):
    return [s["vo_ar"] for s in v["shots"]] + [o["text"] for s in v["shots"] for o in s["overlay_ar"]]


def test_all_22_scripted_with_no_errors():
    assert set(IDS) == set(PDF) and len(IDS) == 22
    assert validate_project(P).errors == []
    assert all(P.video(i)["source_status"] == "scripted" and P.video(i)["shots"] for i in IDS)


@pytest.mark.parametrize("vid", IDS)
def test_pdf_duration_and_beats_preserved(vid):
    v = P.video(vid)
    dur, beats = PDF[vid]
    assert v["duration_s"] == dur
    starts = {to_ms(s["start_s"]) for s in v["shots"]}
    assert all(b * 1000 in starts for b in beats), (vid, beats)
    assert to_ms(v["shots"][-1]["end_s"]) == dur * 1000


@pytest.mark.parametrize("vid", IDS)
def test_vo_pacing_and_claims(vid):
    v = P.video(vid)
    assert validate_video(P, v).errors == []
    for s in v["shots"]:
        if s["vo_ar"]:
            assert count_words(s["vo_ar"]) / (s["vo_end_s"] - s["vo_start_s"]) <= 2.6, s["id"]


@pytest.mark.parametrize("vid", IDS)
def test_end_card_is_coming_soon_with_real_logo(vid):
    last = P.video(vid)["shots"][-1]
    assert last["generation"]["mode"] == "graphics" and last.get("logo")
    assert any(o["text"] == "قريبًا" for o in last["overlay_ar"])
    text = normalize(" ".join(copy_of(P.video(vid))))
    for bad in ("اسحب للأعلى", "احجز الآن", "احجز الليلة", "زر الموقع", "demo.wady"):
        assert normalize(bad) not in text, (vid, bad)


def test_family_concepts_stay_distinct():
    hooks = [normalize(P.video(i)["shots"][0]["vo_ar"] + P.video(i)["concept"]) for i in IDS]
    assert len(set(hooks)) == 22
    assert len({P.video(i)["title_ar"] for i in IDS}) == 22


def test_owner_corrections_applied():
    assert "ست خطوات" in P.video("Y3")["title_ar"] and "نوثّق" not in P.video("Y3")["title_ar"]
    assert "بدون ولا مكالمة" not in P.video("X4")["title_ar"]
    x5 = normalize(" ".join(copy_of(P.video("X5"))))
    assert normalize("بدون عمولة في فترة الإثبات") in x5 and normalize("ثلاثة أشهر أو عشرة حجوزات") in x5
    assert normalize("مؤكدة ومدفوعة") not in x5 and normalize("مجانًا") not in x5
    y5 = normalize(" ".join(copy_of(P.video("Y5"))))
    for must in ("جهات تمويل مرخصة من ساما", "الموافقة والشروط تعود لجهة التمويل", "لا تقدّم تمويلاً", "اختياري"):
        assert normalize(must) in y5, must


def test_ui_is_only_the_real_request_form():
    steps = {s["id"] for s in P.product_flow["steps"]}
    n = 0
    for vid in IDS:
        for s in P.video(vid)["shots"]:
            rec = s.get("screen_insert") or (s["generation"] if s["generation"]["mode"] == "screen_recording" else None)
            if s.get("shows_product_ui"):
                assert rec, s["id"]
            if rec:
                n += 1
                assert set(rec.get("flow_steps", [])) <= steps and rec["flow_steps"], s["id"]
                assert rec["source_path"].startswith("assets/screen_recordings/")
    assert n >= 12


def test_reuse_follows_the_pdf_edit_plan():
    s4 = [s["generation"].get("reuse") for s in P.video("S4")["shots"][:4]]
    assert s4 == ["HERO42_01", "HERO42_02", "HERO42_05", "HERO42_04"]
    assert P.video("T5")["shots"][0]["generation"]["reuse"] == "HERO42_05"
    clip, used = P.source_clip("S4", 1, "9x16")
    assert clip.name == "HERO42_01_16x9.mp4" and used == "16x9"


def test_local_graphics_render(tmp_path):
    import shutil
    if not shutil.which("ffmpeg"):
        pytest.skip("ffmpeg")
    from studio import graphics
    from studio.qc import probe
    for kind in graphics.SUPPORTED:
        out = graphics.render_clip(kind, tmp_path / f"{kind}.mp4", 320, 180, 24, 1.0, "#33650C")
        info = probe(out)
        v = next(s for s in info["streams"] if s["codec_type"] == "video")
        assert (v["width"], v["height"]) == (320, 180) and abs(float(info["format"]["duration"]) - 1.0) < 0.05
    with pytest.raises(graphics.RenderError):
        graphics.render_clip("kinetic_text", tmp_path / "x.mp4", 320, 180, 24, 1.0, "#33650C")
