import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

from conftest import make_clip, make_wav, needs_ffmpeg
from studio import qc, render
from studio.ui import build_state, make_handler


def media(proj, ratio_sizes=((180, 320),), voice=True, music=True):
    for i in (1, 2):
        for w, h in ratio_sizes:
            suffix = "" if h > w else "_16x9"
            make_clip(proj.root / "assets" / "clips" / f"DEMO1_{i:02d}{suffix}.mp4", w, h, 2.0)
    if voice:
        make_wav(proj.root / "assets" / "audio" / "DEMO1_voice.wav", 440, 3.0, 0.5)
    if music:
        make_wav(proj.root / "assets" / "audio" / "DEMO1_music.wav", 220, 4.0, 0.3)


@needs_ffmpeg
def test_render_both_ratios_and_qc(proj):
    media(proj, ((180, 320), (320, 180)))
    for ratio, (w, h) in (("9x16", (180, 320)), ("16x9", (320, 180))):
        out = render.render(proj, "DEMO1", ratio)
        info = qc.probe(out["clean"])
        v = next(s for s in info["streams"] if s["codec_type"] == "video")
        assert (v["width"], v["height"]) == (w, h)
        assert abs(float(info["format"]["duration"]) - 3.0) < 0.1
        rep = qc.check_deliverable(proj, "DEMO1", ratio, out["clean"])
        failed = [c for c in rep["checks"] if not c["pass"]]
        assert failed == [], failed
        assert rep["approved"] is False and len(rep["human_checklist"]) >= 8
        layers = json.loads(out["layers"].read_text())
        assert layers["clean_picture"].endswith("_clean.mp4") and layers["events"]


@needs_ffmpeg
def test_overlay_layer_is_separate_rtl_ass(proj):
    media(proj)
    out = render.render(proj, "DEMO1", "9x16")
    ass = out["ass"].read_text(encoding="utf-8")
    assert "‫عنوان تجريبي‬" in ass and "‫حياكم الله‬" in ass
    assert "Dialogue: 1,0:00:00.20,0:00:01.40,headline" in ass


@needs_ffmpeg
def test_render_refuses_missing_clips_audio_and_reframing(proj):
    with pytest.raises(render.RenderError, match="Missing clips"):
        render.render(proj, "DEMO1", "9x16")
    media(proj, voice=False, music=False)
    with pytest.raises(render.RenderError, match="allow-silent"):
        render.render(proj, "DEMO1", "9x16")
    with pytest.raises(render.RenderError, match="not native 16x9"):
        render.render(proj, "DEMO1", "16x9", allow_silent=True)
    out = render.render(proj, "DEMO1", "9x16", allow_silent=True)
    rep = qc.check_deliverable(proj, "DEMO1", "9x16", out["clean"])
    assert not rep["automated_pass"] and any("silent" in w for w in rep["warnings"])


@needs_ffmpeg
def test_burn_requires_official_brand_unless_draft(proj):
    media(proj)
    render.render(proj, "DEMO1", "9x16")
    with pytest.raises(render.RenderError, match="Official"):
        render.burn(proj, "DEMO1", "9x16")
    out = render.burn(proj, "DEMO1", "9x16", draft=True)
    assert out.name == "DEMO1_9x16_DRAFT.mp4" and out.stat().st_size > 1000


@needs_ffmpeg
def test_clip_qc_detects_wrong_aspect(proj):
    p = proj.root / "wrong.mp4"; make_clip(p, 320, 180, 2.0)
    assert not qc.check_clip(proj, p, 1.5, "9x16")["pass"]
    assert not qc.check_clip(proj, p, 3.0, "16x9")["pass"]  # too short


def test_dashboard_state_and_review_api(proj):
    st = build_state(proj)
    assert st["videos"][0]["id"] == "DEMO1" and len(st["videos"][0]["shots"]) == 2
    assert {p["provider"] for p in st["providers"]} == {"veo", "runway", "kling"}
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(proj.root))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}"
    try:
        assert b"Season Venue" in urllib.request.urlopen(base + "/").read()
        data = json.loads(urllib.request.urlopen(base + "/api/state").read())
        assert data["videos"][0]["shots"][0]["vo_ar"] == "حياكم الله"
        req = urllib.request.Request(base + "/api/review", method="POST",
                                     data=json.dumps({"shot_id": "DEMO1_01", "decision": "approved", "note": "ok"}).encode())
        assert json.loads(urllib.request.urlopen(req).read())["status"] == "approved"
        bad = urllib.request.Request(base + "/api/review", method="POST",
                                     data=json.dumps({"shot_id": "NOPE", "decision": "approved"}).encode())
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(bad)
    finally:
        httpd.shutdown()
