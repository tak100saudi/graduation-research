import base64
import copy
import hashlib
import hmac
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest

from conftest import VERIFIED_SPEC, make_clip, needs_ffmpeg, write_project
from studio import cost, generate
from studio.providers import (MissingCredentials, ProviderError, ProviderNotVerified, VideoProvider,
                              active_provider_name, get_provider, jwt_hs256, render_template)
from studio.prompts import build_video_packages
from studio.state import load_status


def spec(**over):
    s = copy.deepcopy(VERIFIED_SPEC); s.update(over); return s


def test_provider_selection_from_env():
    specs = {"active_provider_env": "SV_VIDEO_PROVIDER"}
    assert active_provider_name(specs, {"SV_VIDEO_PROVIDER": "Runway"}) == "runway"
    with pytest.raises(ProviderError):
        active_provider_name(specs, {})
    with pytest.raises(ProviderError):
        active_provider_name(specs, {"SV_VIDEO_PROVIDER": "sora"})


def test_unverified_spec_refuses_to_submit(proj):
    p = VideoProvider("veo", spec(verified=False), env={"SV_FIXTURE_KEY": "k"},
                      transport=lambda *a: pytest.fail("network must not be touched"))
    with pytest.raises(ProviderNotVerified):
        p.submit(build_video_packages(proj, "DEMO1")[0])


def test_missing_key_is_reported_not_sent():
    st = VideoProvider("fixture", spec(), env={}).readiness()
    assert not st["ready"] and any("SV_FIXTURE_KEY" in x for x in st["problems"])


def test_billed_duration_rounds_up_and_rejects_too_long():
    p = VideoProvider("fixture", spec(), env={})
    assert p.billed_duration(1.5) == 2 and p.billed_duration(4) == 4 and p.billed_duration(4.01) == 8
    with pytest.raises(ProviderError):
        p.billed_duration(9)


def test_template_drops_unsupported_optional_fields(proj):
    p = VideoProvider("fixture", spec(supports_negative_prompt=False), env={})
    body = p.build_request(build_video_packages(proj, "DEMO1")[0])["body"]
    assert "negative" not in body and body["seconds"] == 2 and body["ratio"] == "9:16" and body["seed"] == 7
    assert render_template({"a": "{x}", "b": "pre-{x}"}, {"x": 3}) == {"a": 3, "b": "pre-3"}


def test_jwt_hs256_signature_is_valid():
    tok = jwt_hs256({"iss": "ak", "exp": 10}, "secret")
    h, c, sig = tok.split(".")
    expect = base64.urlsafe_b64encode(hmac.new(b"secret", f"{h}.{c}".encode(), hashlib.sha256).digest()).rstrip(b"=")
    assert sig.encode() == expect
    assert json.loads(base64.urlsafe_b64decode(c + "==")) == {"iss": "ak", "exp": 10}


def test_jwt_auth_requires_both_keys():
    s = spec(auth={"type": "jwt_hs256", "header": "Authorization", "prefix": "Bearer",
                   "access_key_env": "AK", "secret_key_env": "SK", "claims_template": {"iss": "{access_key}", "exp": "{exp}"}})
    with pytest.raises(MissingCredentials):
        VideoProvider("kling", s, env={"AK": "a"})._auth_headers()
    h = VideoProvider("kling", s, env={"AK": "a", "SK": "b"})._auth_headers()
    assert h["Authorization"].startswith("Bearer ") and h["Authorization"].count(".") == 2


# ---------------- cost + approval ---------------------------------------------------

def set_price(root, usd=0.5):
    p = root / "config" / "pricing.json"
    d = json.loads(p.read_text())
    d["rates"]["fixture"] = {"usd_per_second": usd, "source_url": "http://fixture/pricing", "checked_on": "2026-01-01"}
    p.write_text(json.dumps(d))


def test_estimate_refuses_null_price(proj):
    p = VideoProvider("fixture", spec(), env={})
    with pytest.raises(cost.CostError):
        cost.estimate(p, build_video_packages(proj, "DEMO1"), "batch", root=proj.root)


def test_estimate_math(proj):
    set_price(proj.root, 0.5)
    p = VideoProvider("fixture", spec(), env={})
    est = cost.estimate(p, build_video_packages(proj, "DEMO1"), "batch", root=proj.root)
    assert est["billed_seconds"] == 8 and est["base_usd"] == 4.0 and est["max_usd_with_retakes"] == 6.0


def test_approval_requires_human_terminal_and_exact_phrase(proj):
    set_price(proj.root)
    est = cost.estimate(VideoProvider("fixture", spec(), env={}), build_video_packages(proj, "DEMO1")[:1], "test", root=proj.root)
    with pytest.raises(cost.CostError):
        cost.request_approval(est, root=proj.root, input_fn=lambda _: "APPROVE 1.50", isatty=lambda: False)
    with pytest.raises(cost.CostError):
        cost.request_approval(est, root=proj.root, input_fn=lambda _: "yes", isatty=lambda: True)
    rec = cost.request_approval(est, root=proj.root, input_fn=lambda _: "APPROVE 1.50", isatty=lambda: True)
    assert cost.find_approval(est, root=proj.root)["cap_usd"] == rec["cap_usd"] == 1.5
    cost.record_spend(rec["hash"], 1.0, root=proj.root)
    with pytest.raises(cost.CostError):
        cost.record_spend(rec["hash"], 1.0, root=proj.root)


# ---------------- end-to-end against a local mock provider --------------------------

class MockProvider:
    def __init__(self, clip_bytes):
        self.calls = []
        mock = self

        class H(BaseHTTPRequestHandler):
            def _json(self, obj, code=200):
                b = json.dumps(obj).encode(); self.send_response(code)
                self.send_header("Content-Type", "application/json"); self.end_headers(); self.wfile.write(b)

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                mock.calls.append(("POST", self.path, dict(self.headers), body))
                if self.headers.get("X-Fixture-Key") != "secret-key":
                    return self._json({"error": "auth"}, 401)
                self._json({"job": {"id": "job-1"}})

            def do_GET(self):
                mock.calls.append(("GET", self.path, dict(self.headers), None))
                if self.path == "/jobs/job-1":
                    n = sum(1 for c in mock.calls if c[1] == "/jobs/job-1")
                    st = "running" if n < 2 else "done"
                    return self._json({"state": st, "result": {"videos": [{"url": f"{mock.base}/file.mp4"}]}})
                if self.path == "/file.mp4":
                    self.send_response(200); self.end_headers(); self.wfile.write(clip_bytes); return
                self._json({}, 404)

            def log_message(self, *a):
                pass

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.base = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    def close(self):
        self.httpd.shutdown()


@needs_ffmpeg
def test_generate_end_to_end_with_mock_provider(tmp_path):
    proj = write_project(tmp_path)
    src = tmp_path / "src.mp4"; make_clip(src, 180, 320, 2.0)
    mock = MockProvider(src.read_bytes())
    try:
        s = spec(base_url=mock.base)
        prov = VideoProvider("fixture", s, env={"SV_FIXTURE_KEY": "secret-key"}, sleep=lambda _: None)
        set_price(tmp_path, 0.5)
        # blocked without approval, and nothing sent
        with pytest.raises(generate.GenerationBlocked, match="No approval"):
            generate.run(proj, "DEMO1", [1], ["9x16"], "test", provider=prov)
        assert mock.calls == []
        est = cost.estimate(prov, generate.select_packages(proj, "DEMO1", [1], ["9x16"]), "test", root=tmp_path)
        cost.request_approval(est, root=tmp_path, input_fn=lambda _: f"APPROVE {est['max_usd_with_retakes']:.2f}", isatty=lambda: True)
        res = generate.run(proj, "DEMO1", [1], ["9x16"], "test", provider=prov)
        assert res[0]["qc"]["pass"]
        assert (tmp_path / "assets" / "clips" / "DEMO1_01.mp4").stat().st_size > 1024
        post = [c for c in mock.calls if c[0] == "POST"][0]
        assert post[3]["model"] == "fixture-model" and post[3]["seconds"] == 2 and post[3]["ratio"] == "9:16"
        assert "FIXTURE ANCHOR A" in post[3]["prompt"] and "حياكم" not in post[3]["prompt"]
        assert load_status(tmp_path)["DEMO1_01"]["status"] == "test_generated"
        assert cost.find_approval(est, root=tmp_path)["spent_usd"] == 1.0
    finally:
        mock.close()


def test_generation_blocked_by_plan_errors(tmp_path):
    from conftest import VIDEO
    v = copy.deepcopy(VIDEO); v["shots"][0]["overlay_ar"][0]["text"] = "ضمان استرداد"
    proj = write_project(tmp_path, video=v)
    prov = VideoProvider("fixture", spec(), env={"SV_FIXTURE_KEY": "k"}, transport=lambda *a: pytest.fail("no network"))
    with pytest.raises(generate.GenerationBlocked, match="possible claim"):
        generate.run(proj, "DEMO1", [1], ["9x16"], "test", provider=prov)
