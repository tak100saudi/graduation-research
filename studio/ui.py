"""Local production dashboard (stdlib only). Binds to 127.0.0.1 by default."""
from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .model import Project, to_ms, validate_project
from .prompts import build_package
from .providers import SUPPORTED, get_provider
from .state import effective_status, load_status, set_status

UI_FILE = Path(__file__).resolve().parent.parent / "ui" / "index.html"


def build_state(project: Project) -> dict:
    rep = validate_project(project)
    status = load_status(project.root)
    videos = []
    for vid in project.campaign["video_ids"]:
        v = project.videos.get(vid, {"id": vid, "shots": []})
        issues = {k: [m for m in getattr(rep, k) if m.startswith(vid)] for k in ("errors", "blockers", "warnings")}
        shots = []
        for i, s in enumerate(v.get("shots", []), start=1):
            assets = {r: project.clip_path(vid, i, r).exists() for r in v.get("aspect_ratios", [])}
            pkg = build_package(project, v, s, (v.get("aspect_ratios") or ["9x16"])[0])
            shots.append({
                "id": s["id"], "start_s": s["start_s"], "end_s": s["end_s"],
                "duration_s": (to_ms(s["end_s"]) - to_ms(s["start_s"])) / 1000,
                "beat": s.get("beat", ""), "mode": s.get("generation", {}).get("mode"),
                "status": effective_status(project, s), "assets": assets,
                "characters": s.get("characters", []), "location": s.get("location", ""),
                "vo_ar": s.get("vo_ar", ""), "overlays_ar": s.get("overlay_ar", []),
                "prompt_en": pkg["prompt_en"], "negative_prompt": pkg["negative_prompt"],
                "review": status.get(s["id"], {}).get("review"),
            })
        audio = {k: (project.root / "assets" / "audio" / f"{vid}_{k}.wav").exists() for k in ("voice", "music")}
        videos.append({
            "id": vid, "kind": v.get("kind"), "duration_s": v.get("duration_s"),
            "source_status": v.get("source_status"), "concept": v.get("concept", ""),
            "aspect_ratios": v.get("aspect_ratios", []), "shots": shots, "audio": audio, "issues": issues,
        })
    providers = []
    for name in SUPPORTED:
        try:
            providers.append(get_provider(name, root=project.root).readiness())
        except Exception as e:  # noqa: BLE001 - surface any config problem in the UI
            providers.append({"provider": name, "ready": False, "problems": [str(e)]})
    return {
        "campaign": {k: project.campaign.get(k) for k in ("campaign", "source_status", "source_note", "expected_video_count", "brand", "source_precedence")},
        "summary": {"errors": len(rep.errors), "blockers": len(rep.blockers), "warnings": len(rep.warnings)},
        "global_issues": {k: [m for m in getattr(rep, k) if m.split(":")[0] in ("campaign", "brand")]
                          for k in ("errors", "blockers", "warnings")},
        "videos": videos,
        "providers": providers,
        "continuity": project.continuity,
        "product_flow": project.product_flow,
        "banned_phrases": project.campaign.get("banned_phrases", []),
    }


def make_handler(root: Path):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):  # noqa: N802
            if self.path in ("/", "/index.html"):
                self._send(200, UI_FILE.read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/brand/logo":
                project = Project.load(root)
                logo = root / project.campaign.get("brand", {}).get("logo_path", "")
                if logo.is_file():
                    self._send(200, logo.read_bytes(), "image/png")
                else:
                    self._send(404, b"no logo", "text/plain")
            elif self.path == "/api/state":
                data = build_state(Project.load(root))
                self._send(200, json.dumps(data, ensure_ascii=False).encode(), "application/json; charset=utf-8")
            else:
                self._send(404, b"not found", "text/plain")

        def do_POST(self):  # noqa: N802
            if self.path != "/api/review":
                return self._send(404, b"not found", "text/plain")
            try:
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))) or b"{}")
                decision = body["decision"]
                if decision not in ("approved", "rejected"):
                    raise ValueError("decision must be approved or rejected")
                project = Project.load(root)
                shot_ids = {s["id"] for v in project.videos.values() for s in v.get("shots", [])}
                if body["shot_id"] not in shot_ids:
                    raise ValueError("unknown shot")
                rec = set_status(root, body["shot_id"], decision,
                                 review={"decision": decision, "note": str(body.get("note", ""))[:2000]})
                self._send(200, json.dumps(rec, ensure_ascii=False).encode(), "application/json")
            except (KeyError, ValueError, json.JSONDecodeError) as e:
                self._send(400, json.dumps({"error": str(e)}).encode(), "application/json")

        def log_message(self, *args):
            pass

    return Handler


def serve(root: Path, host: str = "127.0.0.1", port: int = 8765) -> None:
    httpd = ThreadingHTTPServer((host, port), make_handler(root))
    print(f"Season Venue studio dashboard: http://{host}:{port}")
    httpd.serve_forever()
