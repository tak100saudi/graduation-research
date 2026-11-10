"""Cost estimation and the human approval gate for paid generation.

Rates come only from config/pricing.json, which must be copied from the
provider's official pricing page. With a null rate, estimation refuses.
Approval must be typed by a person at an interactive terminal; the generator
refuses any paid call whose estimate hash has no matching approval.
"""
from __future__ import annotations

import hashlib
import json
import math
import sys
import time
from pathlib import Path
from typing import Callable

from .model import ROOT, load_json, save_json
from .providers import VideoProvider


class CostError(RuntimeError):
    pass


def load_pricing(root: Path = ROOT) -> dict:
    return load_json(root / "config" / "pricing.json")


def estimate(provider: VideoProvider, packages: list[dict], scope: str, root: Path = ROOT,
             include_retakes: bool = True) -> dict:
    pricing = load_pricing(root)
    rate_info = pricing.get("rates", {}).get(provider.name, {})
    rate = rate_info.get("usd_per_second")
    if rate is None:
        raise CostError(
            f"No verified price for {provider.name} in config/pricing.json — copy it from the official pricing page "
            f"(with source_url and checked_on) before estimating")
    if not rate_info.get("source_url") or not rate_info.get("checked_on"):
        raise CostError(f"Price for {provider.name} lacks source_url/checked_on")
    gen = [p for p in packages if p.get("send_to_video_model")]
    lines = []
    total_s = 0
    for p in gen:
        billed = provider.billed_duration(p["duration_s"])
        total_s += billed
        lines.append({"shot_id": p["shot_id"], "ratio": p["ratio"], "plan_s": p["duration_s"],
                      "billed_s": billed, "usd": round(billed * rate, 4), "prompt_hash": p["prompt_hash"]})
    base = total_s * rate
    retake = pricing.get("retake_factor", 0.5) if include_retakes else 0.0
    est = {
        "scope": scope,
        "provider": provider.name,
        "model": provider.spec.get("model"),
        "currency": pricing.get("currency", "USD"),
        "usd_per_second": rate,
        "rate_source": rate_info.get("source_url"),
        "rate_checked_on": rate_info.get("checked_on"),
        "shots": lines,
        "billed_seconds": total_s,
        "base_usd": round(base, 2),
        "retake_factor": retake,
        "max_usd_with_retakes": round(math.ceil(base * (1 + retake) * 100) / 100, 2),
        "skipped_non_generative": [p["shot_id"] for p in packages if not p.get("send_to_video_model")],
    }
    est["hash"] = hashlib.sha256(json.dumps(
        [est["provider"], est["model"], rate, [(l["shot_id"], l["ratio"], l["billed_s"], l["prompt_hash"]) for l in lines]]
    ).encode()).hexdigest()[:16]
    return est


def approvals_path(root: Path = ROOT) -> Path:
    return root / "state" / "approvals.json"


def load_approvals(root: Path = ROOT) -> list[dict]:
    p = approvals_path(root)
    return load_json(p) if p.exists() else []


def request_approval(est: dict, root: Path = ROOT, input_fn: Callable[[str], str] = input,
                     isatty: Callable[[], bool] = lambda: sys.stdin.isatty()) -> dict:
    if not isatty():
        raise CostError("Approval must be typed by a person in an interactive terminal")
    cap = est["max_usd_with_retakes"]
    expected = f"APPROVE {cap:.2f}"
    answer = input_fn(f'Type "{expected}" to approve up to {cap:.2f} {est["currency"]} on {est["provider"]}: ').strip()
    if answer != expected:
        raise CostError("Not approved")
    rec = {"hash": est["hash"], "scope": est["scope"], "provider": est["provider"], "model": est["model"],
           "cap_usd": cap, "spent_usd": 0.0, "approved_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
           "shots": [(l["shot_id"], l["ratio"]) for l in est["shots"]]}
    approvals = load_approvals(root)
    approvals.append(rec)
    save_json(approvals_path(root), approvals)
    return rec


def find_approval(est: dict, root: Path = ROOT) -> dict | None:
    for rec in load_approvals(root):
        if rec["hash"] == est["hash"]:
            return rec
    return None


def record_spend(approval_hash: str, usd: float, root: Path = ROOT) -> dict:
    approvals = load_approvals(root)
    for rec in approvals:
        if rec["hash"] == approval_hash:
            if rec["spent_usd"] + usd > rec["cap_usd"] + 1e-9:
                raise CostError(f"Spending {usd:.2f} would exceed the approved cap {rec['cap_usd']:.2f}")
            rec["spent_usd"] = round(rec["spent_usd"] + usd, 4)
            save_json(approvals_path(root), approvals)
            return rec
    raise CostError("No approval found for this estimate")
