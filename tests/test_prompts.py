import re

from studio.prompts import build_package, build_video_packages

ARABIC = re.compile(r"[؀-ۿ]")


def test_prompt_contains_anchors_camera_and_framing(proj):
    v = proj.video("DEMO1")
    p = build_package(proj, v, v["shots"][0], "9x16")
    for s in ("FIXTURE ANCHOR A", "white thobe", "FIXTURE COURTYARD", "golden hour", "FIXTURE LOOK",
              "35mm lens", "slow push-in", "Medium shot", "vertical 9:16", "soft key from window"):
        assert s in p["prompt_en"], s
    assert "16:9" in build_package(proj, v, v["shots"][0], "16x9")["prompt_en"]


def test_arabic_is_kept_out_of_the_video_prompt(proj):
    for p in build_video_packages(proj, "DEMO1"):
        assert not ARABIC.search(p["prompt_en"]) and not ARABIC.search(p["negative_prompt"])
    p = build_video_packages(proj, "DEMO1")[0]
    assert p["vo_ar"] == "حياكم الله" and p["overlays_ar"][0]["text"] == "عنوان تجريبي"
    assert p["overlays_ar"][0]["direction"] == "rtl"


def test_negative_prompt_and_references(proj):
    p = build_video_packages(proj, "DEMO1")[0]
    assert "on-screen text" in p["negative_prompt"] and "logos" in p["negative_prompt"]
    assert p["reference_images"] == ["assets/references/char_a.png", "assets/references/loc_a.png"]


def test_prompt_hash_is_stable_and_sensitive(proj):
    v = proj.video("DEMO1")
    a = build_package(proj, v, v["shots"][0], "9x16")["prompt_hash"]
    assert a == build_package(proj, v, v["shots"][0], "9x16")["prompt_hash"]
    v["shots"][0]["action"] = "different"
    assert a != build_package(proj, v, v["shots"][0], "9x16")["prompt_hash"]


def test_package_count_and_durations(proj):
    pk = build_video_packages(proj, "DEMO1")
    assert len(pk) == 4 and sum(p["duration_s"] for p in pk if p["ratio"] == "9x16") == 3.0
