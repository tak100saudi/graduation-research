"""Per-video production plan: second-by-second timeline, shots, VO, overlays, prompts."""
from __future__ import annotations

from pathlib import Path

from .model import Project, count_words, save_json, to_ms, validate_video
from .prompts import build_video_packages


def write(project: Project, vid: str) -> dict:
    video = project.video(vid)
    rep = validate_video(project, video)
    packages = build_video_packages(project, vid)
    outdir = project.root / "output" / "storyboards"
    outdir.mkdir(parents=True, exist_ok=True)
    save_json(project.root / "output" / "prompts" / f"{vid}.json", packages)

    L = [f"# {vid} — production plan", ""]
    L.append(f"- Duration: **{video.get('duration_s', '?')} s** ({video.get('duration_source', '')})")
    L.append(f"- Source status: `{video.get('source_status')}`  ·  Ratios: {', '.join(video.get('aspect_ratios', []))}")
    L.append(f"- Concept: {video.get('concept') or '_pending source_campaign.pdf_'}")
    L.append("")
    for k, title in (("errors", "Errors"), ("blockers", "Blockers"), ("warnings", "Warnings")):
        items = getattr(rep, k)
        if items:
            L.append(f"**{title}**")
            L += [f"- {m}" for m in items]
            L.append("")
    shots = video.get("shots", [])
    if not shots:
        L.append("_No shots planned yet._")
    else:
        dur = to_ms(video["duration_s"]) // 1000 if video.get("duration_s") else 0
        L.append("## Timeline (1 char = 1 s)")
        bar = []
        for i, s in enumerate(shots, start=1):
            n = max(1, round((to_ms(s["end_s"]) - to_ms(s["start_s"])) / 1000))
            bar.append(str(i % 10) * n)
        L.append("```")
        L.append("".join(bar))
        L.append("".join(str((t // 10) % 10) if t % 10 == 0 else "." for t in range(dur)))
        L.append("```")
        L.append("")
        L.append("| Shot | Time | Dur | Beat | Mode | VO (ar) | Words/s | Overlays (ar) |")
        L.append("|---|---|---|---|---|---|---|---|")
        for s in shots:
            d = (to_ms(s["end_s"]) - to_ms(s["start_s"])) / 1000
            vo = s.get("vo_ar", "")
            vs = s.get("vo_start_s", s["start_s"]); ve = s.get("vo_end_s", s["end_s"])
            wps = f"{count_words(vo)/max(0.001, ve - vs):.2f}" if vo else "—"
            ov = " / ".join(f"{o['text']} ({o['start_s']}–{o['end_s']})" for o in s.get("overlay_ar", []))
            L.append(f"| {s['id']} | {s['start_s']}–{s['end_s']} | {d:g}s | {s.get('beat','')} | "
                     f"{s.get('generation',{}).get('mode','')} | {vo or '—'} | {wps} | {ov or '—'} |")
        L.append("")
        L.append("## Prompts")
        for p in packages:
            L += [f"### {p['shot_id']} · {p['ratio']} · {p['duration_s']}s · `{p['prompt_hash']}`", "",
                  f"**Prompt (EN):** {p['prompt_en']}", "", f"**Negative:** {p['negative_prompt']}", ""]
    path = outdir / f"{vid}.md"
    path.write_text("\n".join(L) + "\n", encoding="utf-8")
    return {"storyboard": path, "prompts": project.root / "output" / "prompts" / f"{vid}.json", "report": rep}
