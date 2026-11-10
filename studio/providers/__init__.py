"""Video provider adapters (Google Veo, Runway, Kling).

No endpoint, model id or request field is hard-coded here. Every provider is
described by a spec in config/providers.json that a human copies from the
provider's official documentation and marks verified. Until then the adapter
refuses to send anything.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Callable

from ..model import ROOT, load_json

SUPPORTED = ("veo", "runway", "kling")

REQUIRED_FIELDS = [
    "doc_url", "verified_on", "model", "submit.url", "submit.body_template",
    "job_id_path", "poll.url", "status_path", "done_values", "video_url_path",
    "allowed_durations_s",
]


class ProviderError(RuntimeError):
    pass


class ProviderNotVerified(ProviderError):
    pass


class MissingCredentials(ProviderError):
    pass


def get_path(data: Any, path: str) -> Any:
    """Tiny dotted-path reader: 'response.videos.0.uri'."""
    cur = data
    for part in [p for p in path.split(".") if p]:
        if isinstance(cur, list):
            cur = cur[int(part)]
        elif isinstance(cur, dict):
            if part not in cur:
                raise ProviderError(f"path {path!r}: key {part!r} not in response")
            cur = cur[part]
        else:
            raise ProviderError(f"path {path!r}: cannot descend into {type(cur).__name__}")
    return cur


def render_template(obj: Any, values: dict) -> Any:
    """Replace "{name}" strings. A value that is exactly "{name}" keeps the value's type;
    keys whose value resolves to None are dropped (optional fields)."""
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            rv = render_template(v, values)
            if rv is not None:
                out[k] = rv
        return out
    if isinstance(obj, list):
        return [x for x in (render_template(v, values) for v in obj) if x is not None]
    if isinstance(obj, str):
        if obj.startswith("{") and obj.endswith("}") and obj[1:-1] in values:
            return values[obj[1:-1]]
        try:
            return obj.format(**{k: ("" if v is None else v) for k, v in values.items()})
        except (KeyError, IndexError, ValueError):
            return obj
    return obj


def load_specs(root: Path = ROOT) -> dict:
    return load_json(root / "config" / "providers.json")


def active_provider_name(specs: dict, env: dict | None = None) -> str:
    env = os.environ if env is None else env
    name = env.get(specs.get("active_provider_env", "SV_VIDEO_PROVIDER"), "").strip().lower()
    if not name:
        raise ProviderError("No provider selected: set SV_VIDEO_PROVIDER to veo, runway or kling")
    if name not in SUPPORTED:
        raise ProviderError(f"Unsupported provider {name!r}; choose one of {SUPPORTED}")
    return name


def missing_fields(spec: dict) -> list[str]:
    missing = []
    for f in REQUIRED_FIELDS:
        try:
            v = get_path(spec, f)
        except ProviderError:
            v = None
        if v in (None, "", [], {}):
            missing.append(f)
    auth = spec.get("auth", {})
    if not auth.get("header"):
        missing.append("auth.header")
    return missing


def _b64url(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).rstrip(b"=").decode()


def jwt_hs256(claims: dict, secret: str) -> str:
    header = {"alg": "HS256", "typ": "JWT"}
    signing = f"{_b64url(json.dumps(header, separators=(',', ':')).encode())}.{_b64url(json.dumps(claims, separators=(',', ':')).encode())}"
    sig = hmac.new(secret.encode(), signing.encode(), hashlib.sha256).digest()
    return f"{signing}.{_b64url(sig)}"


Transport = Callable[[str, str, dict, bytes | None], tuple[int, bytes]]


def urllib_transport(method: str, url: str, headers: dict, body: bytes | None) -> tuple[int, bytes]:
    req = urllib.request.Request(url, data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


class VideoProvider:
    def __init__(self, name: str, spec: dict, env: dict | None = None,
                 transport: Transport = urllib_transport, sleep: Callable[[float], None] = time.sleep):
        self.name = name
        self.spec = spec
        self.env = os.environ if env is None else env
        self.transport = transport
        self.sleep = sleep

    # ---- readiness -------------------------------------------------------
    def readiness(self) -> dict:
        problems = []
        if not self.spec.get("verified"):
            problems.append("spec not marked verified against official docs")
        problems += [f"missing spec field: {f}" for f in missing_fields(self.spec)]
        try:
            self._auth_headers()
        except MissingCredentials as e:
            problems.append(str(e))
        return {"provider": self.name, "ready": not problems, "problems": problems}

    def require_ready(self) -> None:
        state = self.readiness()
        if not state["ready"]:
            raise ProviderNotVerified(f"{self.name} not ready: " + "; ".join(state["problems"]))

    # ---- auth ------------------------------------------------------------
    def _auth_headers(self) -> dict:
        auth = self.spec.get("auth", {})
        kind = auth.get("type", "header")
        if kind == "header":
            env_name = auth.get("key_env", "")
            key = self.env.get(env_name, "")
            if not key:
                raise MissingCredentials(f"environment variable {env_name} is not set")
            token = key
        elif kind == "jwt_hs256":
            ak = self.env.get(auth.get("access_key_env", ""), "")
            sk = self.env.get(auth.get("secret_key_env", ""), "")
            if not ak or not sk:
                raise MissingCredentials(
                    f"environment variables {auth.get('access_key_env')} / {auth.get('secret_key_env')} are not set")
            now = int(time.time())
            claims = render_template(auth.get("claims_template", {}),
                                     {"access_key": ak, "now": now, "exp": now + int(auth.get("ttl_s", 1800)),
                                      "nbf": now - 5})
            token = jwt_hs256(claims, sk)
        else:
            raise ProviderError(f"unknown auth type {kind!r}")
        if not auth.get("header"):
            return {}
        prefix = auth.get("prefix", "")
        return {auth["header"]: f"{prefix} {token}".strip() if prefix else token}

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        h.update(self.spec.get("extra_headers", {}))
        h.update(self._auth_headers())
        return h

    # ---- request building -----------------------------------------------
    def billed_duration(self, seconds: float) -> int:
        allowed = sorted(self.spec.get("allowed_durations_s", []))
        if not allowed:
            raise ProviderNotVerified(f"{self.name}: allowed_durations_s not configured")
        for a in allowed:
            if a >= seconds - 1e-6:
                return a
        raise ProviderError(
            f"{self.name}: shot of {seconds:.2f}s exceeds the longest single generation ({allowed[-1]}s); split the shot")

    def build_request(self, pkg: dict) -> dict:
        ratio_value = self.spec.get("allowed_aspect_ratios", {}).get(pkg["ratio"])
        if not ratio_value:
            raise ProviderNotVerified(f"{self.name}: no aspect-ratio value configured for {pkg['ratio']}")
        values = {
            "base": self.spec.get("base_url", ""),
            "model": self.spec.get("model"),
            "prompt": pkg["prompt_en"],
            "negative_prompt": pkg["negative_prompt"] if self.spec.get("supports_negative_prompt") else None,
            "duration_s": self.billed_duration(pkg["duration_s"]),
            "aspect_ratio": ratio_value,
            "seed": pkg.get("seed"),
            "image_uri": (pkg.get("reference_images") or [None])[0] if self.spec.get("supports_reference_images") else None,
        }
        body = render_template(self.spec["submit"]["body_template"], values)
        return {"method": self.spec["submit"].get("method", "POST"),
                "url": render_template(self.spec["submit"]["url"], values),
                "body": body}

    # ---- calls -----------------------------------------------------------
    def _call(self, method: str, url: str, body: dict | None = None) -> dict:
        data = json.dumps(body).encode() if body is not None else None
        status, raw = self.transport(method, url, self._headers(), data)
        if status >= 400:
            raise ProviderError(f"{self.name} HTTP {status}: {raw[:500].decode(errors='replace')}")
        try:
            return json.loads(raw or b"{}")
        except json.JSONDecodeError as e:
            raise ProviderError(f"{self.name}: non-JSON response") from e

    def submit(self, pkg: dict) -> str:
        self.require_ready()
        req = self.build_request(pkg)
        resp = self._call(req["method"], req["url"], req["body"])
        return str(get_path(resp, self.spec["job_id_path"]))

    def poll(self, job_id: str) -> dict:
        poll = self.spec["poll"]
        url = render_template(poll["url"], {"job_id": job_id, "base": self.spec.get("base_url", "")})
        deadline = time.monotonic() + float(poll.get("timeout_s", 900))
        while True:
            resp = self._call(poll.get("method", "GET"), url)
            status = get_path(resp, self.spec["status_path"])
            if status in self.spec["done_values"]:
                return resp
            if status in self.spec.get("failed_values", []):
                raise ProviderError(f"{self.name} job {job_id} failed: {json.dumps(resp)[:500]}")
            if time.monotonic() > deadline:
                raise ProviderError(f"{self.name} job {job_id} timed out (last status {status!r})")
            self.sleep(float(poll.get("interval_s", 10)))

    def download(self, final_resp: dict, dest: Path) -> Path:
        url = get_path(final_resp, self.spec["video_url_path"])
        headers = self._auth_headers() if self.spec.get("download_auth") else {}
        status, raw = self.transport("GET", url, headers, None)
        if status >= 400:
            raise ProviderError(f"{self.name} download HTTP {status}")
        if len(raw) < 1024:
            raise ProviderError(f"{self.name}: downloaded file is suspiciously small ({len(raw)} bytes)")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
        return dest


def get_provider(name: str | None = None, root: Path = ROOT, env: dict | None = None, **kw) -> VideoProvider:
    specs = load_specs(root)
    name = name or active_provider_name(specs, env)
    if name not in specs.get("providers", {}):
        raise ProviderError(f"provider {name!r} has no spec in config/providers.json")
    return VideoProvider(name, specs["providers"][name], env=env, **kw)
