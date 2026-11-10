#!/usr/bin/env python3
"""Season Venue production studio CLI.

  validate [--production] [--json]      plan/timing/claims/continuity checks
  ingest                                extract source_campaign.pdf + reconciliation report
  storyboard (--video ID | --all)       production plan + prompt packages per video
  providers                             readiness of veo / runway / kling adapters
  estimate  --video ID [--shots N..] [--ratio R..] [--test]
  approve   (same args)                 interactive human approval of the estimate
  generate  (same args)                 paid generation — requires a matching approval
  render    --video ID --ratio R [--allow-silent] [--allow-reframe]
  burn      --video ID --ratio R [--draft]   burn Arabic overlay layer + official logo
  animatic  --video ID --ratio R         timing animatic: slates + Arabic overlay layer + logo cue (not footage)
  qc        --video ID --ratio R [--file PATH]
  serve     [--port 8765]               local dashboard
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from studio import cost, generate, ingest, qc, render, storyboard  # noqa: E402
from studio.model import Project, validate_project  # noqa: E402
from studio.providers import SUPPORTED, ProviderError, get_provider  # noqa: E402


def _load_env_file() -> None:
    """Load KEY=VALUE pairs from a git-ignored .env without overriding the real environment."""
    import os
    p = ROOT / ".env"
    if not p.exists():
        return
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if "=" in line:
            k, v = line.split("=", 1)
            if v.strip():
                os.environ.setdefault(k.strip(), v.strip())


def cmd_validate(a, project):
    rep = validate_project(project)
    if a.json:
        print(json.dumps(rep.as_dict(), ensure_ascii=False, indent=2))
    else:
        for k, tag in (("errors", "ERROR"), ("blockers", "BLOCKER"), ("warnings", "WARN")):
            for m in getattr(rep, k):
                print(f"[{tag}] {m}")
        print(f"\n{len(project.videos)} videos · {len(rep.errors)} errors · {len(rep.blockers)} blockers · {len(rep.warnings)} warnings")
    return 0 if rep.ok(production=a.production) else 1


def cmd_ingest(a, project):
    r = ingest.ingest(project)
    print(f"{r['pages']} pages. IDs found: {', '.join(r['ids_found_in_pdf']) or 'none'}")
    print(f"Planned but not found: {', '.join(r['planned_not_in_pdf']) or 'none'}")
    print(f"In PDF but not planned: {', '.join(r['ids_in_pdf_not_planned']) or 'none'}")
    print("Wrote source/extracted/source_campaign.txt and output/reconciliation.json")
    return 0


def cmd_storyboard(a, project):
    ids = project.campaign["video_ids"] if a.all else [a.video]
    for vid in ids:
        out = storyboard.write(project, vid)
        print(f"{vid}: {out['storyboard'].relative_to(ROOT)}  ({len(out['report'].errors)} errors, {len(out['report'].blockers)} blockers)")
    return 0


def cmd_providers(a, project):
    for name in SUPPORTED:
        st = get_provider(name, root=ROOT).readiness()
        print(f"{name:7} {'READY' if st['ready'] else 'NOT READY'}")
        for p in st["problems"]:
            print(f"   - {p}")
    return 0


def _gen_args(a):
    ratios = a.ratio or ["9x16"]
    shots = a.shots
    scope = "test" if a.test else "batch"
    if a.test:
        shots = shots or [1]
        if len(shots) != 1 or len(ratios) != 1:
            raise SystemExit("--test means exactly one shot and one ratio")
    return shots, ratios, scope


def cmd_estimate(a, project, show=True):
    shots, ratios, scope = _gen_args(a)
    prov = get_provider(root=ROOT)
    pk = generate.select_packages(project, a.video, shots, ratios)
    est = cost.estimate(prov, pk, scope, root=ROOT)
    if show:
        print(json.dumps(est, ensure_ascii=False, indent=2))
    return est


def cmd_approve(a, project):
    est = cmd_estimate(a, project)
    rec = cost.request_approval(est, root=ROOT)
    print(f"Approved {rec['hash']} up to {rec['cap_usd']:.2f} {est['currency']}")
    return 0


def cmd_generate(a, project):
    shots, ratios, scope = _gen_args(a)
    res = generate.run(project, a.video, shots, ratios, scope)
    for r in res:
        print(f"{r['shot_id']} {r['ratio']} -> {r['file']}  QC {'PASS' if r['qc']['pass'] else 'FAIL'}")
    return 0 if all(r["qc"]["pass"] for r in res) else 1


def cmd_render(a, project):
    for ratio in a.ratio:
        out = render.render(project, a.video, ratio, allow_silent=a.allow_silent, allow_reframe=a.allow_reframe)
        print(f"{ratio}: {out['clean'].relative_to(ROOT)} + overlay layer {out['ass'].name}")
    return 0


def cmd_burn(a, project):
    for ratio in a.ratio:
        print(render.burn(project, a.video, ratio, draft=a.draft, logo_variant=a.logo).relative_to(ROOT))
    return 0


def cmd_animatic(a, project):
    from studio import animatic
    for ratio in a.ratio:
        print(animatic.build(project, a.video, ratio).relative_to(ROOT))
    return 0


def cmd_qc(a, project):
    code = 0
    for ratio in a.ratio:
        f = Path(a.file) if a.file else ROOT / "output" / a.video / f"{a.video}_{ratio}_clean.mp4"
        rep = qc.check_deliverable(project, a.video, ratio, f)
        for c in rep["checks"]:
            print(f"  [{'PASS' if c['pass'] else 'FAIL'}] {c['check']}: {c.get('detail', '')}")
        for w in rep["warnings"]:
            print(f"  [WARN] {w}")
        print(f"{a.video} {ratio}: automated {'PASS' if rep['automated_pass'] else 'FAIL'}; "
              f"{len(rep['human_checklist'])} human checks pending")
        code |= 0 if rep["automated_pass"] else 1
    return code


def cmd_serve(a, project):
    from studio.ui import serve
    serve(ROOT, port=a.port)


def main(argv=None):
    _load_env_file()
    ap = argparse.ArgumentParser(description="Season Venue studio")
    sub = ap.add_subparsers(dest="cmd", required=True)
    v = sub.add_parser("validate"); v.add_argument("--production", action="store_true"); v.add_argument("--json", action="store_true")
    sub.add_parser("ingest")
    s = sub.add_parser("storyboard"); g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--video"); g.add_argument("--all", action="store_true")
    sub.add_parser("providers")
    for name in ("estimate", "approve", "generate"):
        p = sub.add_parser(name)
        p.add_argument("--video", required=True); p.add_argument("--shots", type=int, nargs="+")
        p.add_argument("--ratio", nargs="+", choices=["9x16", "16x9"]); p.add_argument("--test", action="store_true")
    r = sub.add_parser("render"); r.add_argument("--video", required=True)
    r.add_argument("--ratio", nargs="+", choices=["9x16", "16x9"], required=True)
    r.add_argument("--allow-silent", action="store_true"); r.add_argument("--allow-reframe", action="store_true")
    b = sub.add_parser("burn"); b.add_argument("--video", required=True)
    b.add_argument("--ratio", nargs="+", choices=["9x16", "16x9"], required=True); b.add_argument("--draft", action="store_true")
    b.add_argument("--logo", choices=["primary", "dark"], default="primary", help="dark = logo variant for dark backgrounds")
    q = sub.add_parser("qc"); q.add_argument("--video", required=True)
    q.add_argument("--ratio", nargs="+", choices=["9x16", "16x9"], required=True); q.add_argument("--file")
    an = sub.add_parser("animatic"); an.add_argument("--video", required=True)
    an.add_argument("--ratio", nargs="+", choices=["9x16", "16x9"], required=True)
    sv = sub.add_parser("serve"); sv.add_argument("--port", type=int, default=8765)
    a = ap.parse_args(argv)
    project = Project.load(ROOT)
    handler = {"validate": cmd_validate, "ingest": cmd_ingest, "storyboard": cmd_storyboard, "providers": cmd_providers,
               "estimate": lambda a, p: (cmd_estimate(a, p), 0)[1], "approve": cmd_approve, "generate": cmd_generate,
               "render": cmd_render, "animatic": cmd_animatic, "burn": cmd_burn, "qc": cmd_qc, "serve": cmd_serve}[a.cmd]
    try:
        return handler(a, project) or 0
    except (ProviderError, cost.CostError, generate.GenerationBlocked, render.RenderError, qc.QCError,
            FileNotFoundError, KeyError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
