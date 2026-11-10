"""Gated generation: readiness -> plan validation -> estimate -> approval -> submit/poll/download -> clip QC."""
from __future__ import annotations

import time
from pathlib import Path

from . import cost
from .model import Project, save_json, source_ratios, validate_video
from .prompts import build_package
from .providers import VideoProvider, get_provider
from .qc import check_clip
from .state import set_status


class GenerationBlocked(RuntimeError):
    pass


def select_packages(project: Project, vid: str, shots: list[int] | None, ratios: list[str]) -> list[dict]:
    video = project.video(vid)
    all_shots = video.get("shots", [])
    if not all_shots:
        raise GenerationBlocked(f"{vid} has no shots yet — reconcile the plan with source_campaign.pdf first")
    chosen = [all_shots[i - 1] for i in shots] if shots else all_shots
    return [build_package(project, video, s, r) for r in ratios for s in chosen if r in source_ratios(video, s)]


def preflight(project: Project, vid: str, packages: list[dict]) -> None:
    rep = validate_video(project, project.video(vid))
    if rep.errors:
        raise GenerationBlocked("Plan has errors:\n  " + "\n  ".join(rep.errors))
    ids = {p["shot_id"] for p in packages}
    shot_blockers = [b for b in rep.blockers if b.split(":")[0] in ids]
    if shot_blockers:
        raise GenerationBlocked("Shot blockers:\n  " + "\n  ".join(shot_blockers))


def clip_dest(project: Project, pkg: dict) -> Path:
    n = int(pkg["shot_id"].rsplit("_", 1)[1])
    suffix = "" if pkg["ratio"] == "9x16" else f"_{pkg['ratio']}"
    return project.root / "assets" / "clips" / f"{pkg['video_id']}_{n:02d}{suffix}.mp4"


def run(project: Project, vid: str, shots: list[int] | None, ratios: list[str], scope: str,
        provider: VideoProvider | None = None) -> list[dict]:
    provider = provider or get_provider(root=project.root)
    provider.require_ready()
    packages = select_packages(project, vid, shots, ratios)
    preflight(project, vid, packages)
    est = cost.estimate(provider, packages, scope, root=project.root)
    approval = cost.find_approval(est, root=project.root)
    if not approval:
        raise GenerationBlocked(
            f"No approval for estimate {est['hash']} (max {est['max_usd_with_retakes']} {est['currency']}). "
            f"Run: python scripts/studio.py approve {_cli_args(vid, shots, ratios, scope)}")
    rate = est["usd_per_second"]
    results = []
    for pkg in packages:
        if not pkg["send_to_video_model"]:
            continue
        billed = provider.billed_duration(pkg["duration_s"])
        cost.record_spend(approval["hash"], billed * rate, root=project.root)  # reserve before submit
        job = provider.submit(pkg)
        jobrec = {"provider": provider.name, "model": provider.spec.get("model"), "job_id": job,
                  "prompt_hash": pkg["prompt_hash"], "submitted_at": time.strftime("%Y-%m-%dT%H:%M:%S")}
        save_json(project.root / "state" / "jobs" / f"{pkg['shot_id']}_{pkg['ratio']}.json", jobrec)
        final = provider.poll(job)
        dest = clip_dest(project, pkg)
        provider.download(final, dest)
        qc = check_clip(project, dest, pkg["duration_s"], pkg["ratio"])
        status = ("test_generated" if scope == "test" else "generated") if qc["pass"] else "rejected"
        set_status(project.root, pkg["shot_id"], status,
                   take={**jobrec, "file": str(dest.relative_to(project.root)), "ratio": pkg["ratio"], "qc": qc})
        results.append({"shot_id": pkg["shot_id"], "ratio": pkg["ratio"], "file": str(dest), "qc": qc})
    return results


def _cli_args(vid, shots, ratios, scope) -> str:
    s = f"--video {vid} --ratio {' '.join(ratios)}"
    if shots:
        s += " --shots " + " ".join(map(str, shots))
    if scope == "test":
        s += " --test"
    return s
