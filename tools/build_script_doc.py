#!/usr/bin/env python3
"""docs/scripts_ar.md: every video's script in Arabic, for owner review."""
import json
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
c = json.loads((ROOT / "plans/campaign.json").read_text(encoding="utf-8"))
L = ["# Season Venue — سكربتات الحملة (22 مقطعًا)", "",
     "المصدر: `source_campaign.pdf` مع تطبيق تصحيحات `brand_facts.md`. كل السكربتات **بانتظار اعتماد المالك**.",
     "كل بطاقات النهاية تحمل «قريبًا» إلى أن يصل الرابط ورقم التواصل، وعندها تعود عبارات الدعوة (اطلب الآن / اسحب للأعلى).", ""]
for vid in c["video_ids"]:
    v = json.loads((ROOT / f"plans/videos/{vid}.json").read_text(encoding="utf-8"))
    L += [f"## {vid} — {v.get('title_ar', '')} · {v['duration_s']} ث · {v.get('platform', '')}", ""]
    if v.get("title_pdf"):
        L += [f"*عنوان الـPDF الأصلي: {v['title_pdf']}*", ""]
    L += [f"**الفكرة:** {v.get('concept', '')}", "", "| الثواني | المشهد | التعليق / الحوار | النص على الشاشة |", "|---|---|---|---|"]
    for s in v["shots"]:
        ovs = " / ".join(o["text"].replace("\n", " ") for o in s["overlay_ar"] if o.get("kind") != "disclosure") or "—"
        mode = {"graphics": "موشن جرافيك", "reuse": f"إعادة استخدام {s['generation'].get('reuse', '')}",
                "screen_recording": "تسجيل شاشة حقيقي"}.get(s["generation"]["mode"], "توليد")
        if s.get("screen_insert"):
            mode += " + تسجيل شاشة حقيقي"
        vo = s["vo_ar"] or "—"
        if s.get("vo_speaker"):
            vo += f" *({s['vo_speaker'].split(' ')[0]})*"
        L.append(f"| {s['start_s']}–{s['end_s']} | {s['beat']} ({mode}) | {vo} | {ovs} |")
    disc = [o["text"] for s in v["shots"] for o in s["overlay_ar"] if o.get("kind") == "disclosure"]
    if disc:
        L += ["", f"**إفصاح إلزامي على الشاشة:** {disc[0]}"]
    L += ["", "**ما تغيّر عن الـPDF:**"] + [f"- {r['pdf_shot']}: {r['change']}" for r in v.get("reconciliation", [])]
    for k, label in (("tweet_ar", "نص التغريدة"), ("caution", "تنبيه"), ("production_note", "ملاحظة إنتاج")):
        if v.get(k):
            L += ["", f"**{label}:** {v[k]}"]
    L.append("")
(ROOT / "docs/scripts_ar.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("docs/scripts_ar.md")
