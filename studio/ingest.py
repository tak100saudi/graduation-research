"""Extract text from source_campaign.pdf and build a reconciliation report
that maps each planned video id to where it appears in the PDF.
It does NOT write creative content: scripts are transcribed from the PDF by a
person (or Claude Code) and reviewed, then committed to plans/videos/*.json."""
from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path

from .model import Project, save_json

DURATION_RE = re.compile(r"(\d{1,3}(?:\.\d)?)\s*(?:s\b|sec|secs|seconds|ث\b|ثانية|ثوان|ثواني)", re.IGNORECASE)


def extract_pages(pdf: Path) -> list[str]:
    try:
        from pypdf import PdfReader  # optional dependency
        return [(p.extract_text() or "") for p in PdfReader(str(pdf)).pages]
    except ImportError:
        pass
    if shutil.which("pdftotext"):
        res = subprocess.run(["pdftotext", "-layout", str(pdf), "-"], capture_output=True, text=True)
        if res.returncode == 0:
            return res.stdout.split("\f")
    raise RuntimeError("Install pypdf (pip install -r requirements-dev.txt) or poppler pdftotext")


def ingest(project: Project) -> dict:
    pdf = project.root / project.campaign["source_document"]
    if not pdf.exists():
        raise FileNotFoundError(f"Put the brief at {pdf.relative_to(project.root)} first")
    pages = extract_pages(pdf)
    outdir = project.root / "source" / "extracted"
    outdir.mkdir(parents=True, exist_ok=True)
    (outdir / "source_campaign.txt").write_text(
        "".join(f"\n\n===== PAGE {i} =====\n{t}" for i, t in enumerate(pages, start=1)), encoding="utf-8")

    found_ids = sorted(set(re.findall(r"\b(HERO\d+|[TSXY][1-5])\b", "\n".join(pages))))
    report = {"pages": len(pages), "ids_found_in_pdf": found_ids, "videos": {}}
    for vid in project.campaign["video_ids"]:
        hits = []
        for i, text in enumerate(pages, start=1):
            for m in re.finditer(rf"\b{re.escape(vid)}\b", text):
                window = text[m.start(): m.start() + 400]
                durs = DURATION_RE.findall(window)
                hits.append({"page": i, "context": window[:200].replace("\n", " "), "durations_nearby": durs[:5]})
        report["videos"][vid] = {"occurrences": len(hits), "hits": hits[:10]}
    report["ids_in_pdf_not_planned"] = [i for i in found_ids if i not in project.campaign["video_ids"]]
    report["planned_not_in_pdf"] = [v for v, r in report["videos"].items() if r["occurrences"] == 0]
    save_json(project.root / "output" / "reconciliation.json", report)
    return report
