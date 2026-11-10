"""Runtime shot status (takes, reviews). Creative content lives in plans/; this file
only tracks production progress so plans stay clean diffs."""
from __future__ import annotations

import time
from pathlib import Path

from .model import ROOT, SHOT_STATUSES, Project, load_json, save_json


def status_path(root: Path = ROOT) -> Path:
    return root / "state" / "status.json"


def load_status(root: Path = ROOT) -> dict:
    p = status_path(root)
    return load_json(p) if p.exists() else {}


def effective_status(project: Project, shot: dict) -> str:
    return load_status(project.root).get(shot["id"], {}).get("status") or shot.get("status", "pending_source")


def set_status(root: Path, shot_id: str, status: str, **extra) -> dict:
    if status not in SHOT_STATUSES:
        raise ValueError(f"unknown status {status}")
    data = load_status(root)
    rec = data.setdefault(shot_id, {})
    rec["status"] = status
    rec["updated_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    for k, v in extra.items():
        if k == "take":
            rec.setdefault("takes", []).append(v)
        else:
            rec[k] = v
    save_json(status_path(root), data)
    return rec
