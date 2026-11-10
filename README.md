# Season Venue — استوديو الإنتاج الإعلاني

استوديو إنتاج محلي يعمل عبر Claude Code لتخطيط وتوليد ومونتاج وفحص 22 مقطعًا إعلانيًا
(الفيديو البطل `HERO42` + 20 إعلان أداء T1–T5 / S1–S5 / X1–X5 / Y1–Y5 + مقطع غير محدد بعد).
الملف المرجعي هو `source/source_campaign.pdf`، وتعليمات المشروع في `CLAUDE.md`.

> **الحالة الحالية:** ملف `source_campaign.pdf` ومجلدات `plans`/`scripts` الأصلية لم تكن موجودة في المستودع.
> لذلك بُني النظام كاملًا، لكن **كل المحتوى الإبداعي فارغ ومعلَّم `pending_source`** إلى حين رفع الـPDF. لم يُخترع أي سكربت أو مدة أو سعر.

## التشغيل السريع

```bash
pip install -r requirements-dev.txt     # pytest + pypdf (الأداة نفسها تعمل بمكتبة بايثون القياسية)
python scripts/studio.py validate        # فحص المدد، الاستمرارية، الادعاءات، سرعة التعليق الصوتي
python scripts/studio.py validate --production   # يفشل حتى تُحل كل العوائق
python scripts/studio.py storyboard --all         # output/storyboards/*.md + output/prompts/*.json
python scripts/studio.py serve           # لوحة الإدارة: http://127.0.0.1:8765
python -m pytest -q                      # الاختبارات
```

## خط الإنتاج

| الخطوة | الأمر | البوابة |
|---|---|---|
| 1. استخراج الـPDF ومطابقة الـ22 مقطعًا | `ingest` | يتطلب `source/source_campaign.pdf` |
| 2. كتابة السكربت والتوقيت لكل لقطة | تحرير `plans/videos/<ID>.json` | `validate` بلا أخطاء |
| 3. برومبت إنجليزي + Negative + VO سعودي + نصوص عربية منفصلة | `storyboard --video ID` | — |
| 4. جاهزية المزود | `providers` | مواصفات موثّقة + مفتاح في متغير بيئة |
| 5. تقدير التكلفة | `estimate --video HERO42 --test` | أسعار رسمية في `config/pricing.json` |
| 6. موافقتك | `approve --video HERO42 --test` | تكتب `APPROVE <المبلغ>` بنفسك في الطرفية |
| 7. لقطة الاختبار | `generate --video HERO42 --test` | يرفض بدون موافقة مطابقة للتقدير |
| 8. المونتاج | `render --video HERO42 --ratio 9x16 16x9` | كل اللقطات + الصوت موجودة وبمقاس أصلي |
| 9. النصوص والشعار | `burn --video HERO42 --ratio 9x16` | الشعار والخط الرسميان (أو `--draft`) |
| 10. الجودة | `qc --video HERO42 --ratio 9x16 16x9` | فحص آلي + قائمة مراجعة بشرية |

## هيكل الملفات

```
plans/campaign.json        إعدادات الحملة، الهوية، الصوت، سرعة التعليق، أدلة الادعاءات (claims_evidence)
plans/continuity.json      دليل الثبات: الشخصيات، المواقع، الألوان، Negative العام
plans/videos/<ID>.json     خطة كل مقطع ولقطاته (22 ملفًا)
config/providers.json      مواصفات Veo / Runway / Kling — فارغة وغير موثقة عمدًا
config/pricing.json        الأسعار — null حتى تُنسخ من صفحة الأسعار الرسمية
studio/                    الكود (model, prompts, providers, cost, generate, render, qc, ui, ingest)
scripts/studio.py          واجهة الأوامر
ui/index.html              لوحة الإدارة (عربية RTL)
assets/clips/<ID>_<NN>.mp4  (9:16)   assets/clips/<ID>_<NN>_16x9.mp4 (16:9)
assets/audio/<ID>_voice.wav  assets/audio/<ID>_music.wav
assets/brand/logo.png  assets/brand/font.ttf   (الهوية الرسمية)
output/<ID>/               clean.mp4 + overlays_ar.ass + layers.json + qc.json
```

## مخطط اللقطة (Shot schema)

```json
{
  "id": "HERO42_01", "start_s": 0, "end_s": 4.0, "beat": "hook", "scene": "SC1",
  "characters": ["CHAR_..."], "wardrobe": {"CHAR_...": "W1"}, "location": "LOC_...",
  "action": "English description of the action",
  "camera": {"shot_size": "MCU", "angle": "eye-level", "lens_mm": 50, "aperture": 2.8, "movement": "slow dolly-in"},
  "lighting": "soft window key, warm practicals",
  "vo_ar": "سطر التعليق الصوتي باللهجة السعودية", "vo_start_s": 0.3, "vo_end_s": 3.6, "vo_speaker": "VO_MAIN",
  "overlay_ar": [{"text": "نص على الشاشة", "start_s": 0.5, "end_s": 3.5, "position": "lower_third", "style": "headline"}],
  "claims": [], "sfx": "", "shows_product_ui": false,
  "negative_extra": [],
  "generation": {"mode": "text_to_video | image_to_video | screen_recording | graphics | live_action", "seed": null, "source_path": null}
}
```

## قواعد مفروضة برمجيًا

- **المدد:** اللقطات متتالية بلا فجوات أو تداخل، ومجموعها = مدة المقطع بالمللي ثانية.
- **التعليق الصوتي:** حد أقصى 2.6 كلمة/ثانية (مريح 2.2) — افتراض عمل يُعاد ضبطه بعد قراءة اختبارية للمعلّق المرخّص.
- **الادعاءات:** أي سعر، رقم، ضمان، توثيق، تمويل/تقسيط، حماية دفع، شهادة عميل أو صيغة تفضيل يُرفض ما لم يرتبط بدليل معتمد في `campaign.claims_evidence`.
- **الواجهات:** أي لقطة تعرض واجهة المنتج يجب أن تكون تسجيل شاشة حقيقيًا (`screen_recording`).
- **الوجوه:** لا توليد لشخصية بدون موافقة موقّعة (`consent.status = signed`) وصور مرجعية.
- **الثبات:** وصف الشخصية/الموقع يُحقن حرفيًا في كل برومبت؛ تغيير الملابس داخل المشهد نفسه خطأ.
- **النص العربي لا يُرسل لنموذج الفيديو أبدًا** — يُضاف كطبقة ASS منفصلة بالخط الرسمي.
- **الصوت:** لا نغمات تنبيه ولا قص شريط؛ الهدف ‎-14 LUFS وذروة ≤ ‎-1 dBTP.
- **التكلفة:** لا طلب مدفوع بدون تقدير من أسعار رسمية وموافقة بشرية مطابقة لبصمة التقدير، مع سقف إنفاق.

## ربط مزود الفيديو

المزودات (Veo / Runway / Kling) تُعرَّف في `config/providers.json` بالكامل من التوثيق الرسمي:
`base_url`, `model`, `auth`, `submit.url`, `submit.body_template` (متغيرات: `{model} {prompt} {negative_prompt} {duration_s} {aspect_ratio} {seed} {image_uri} {base}`),
`job_id_path`, `poll.url` (`{job_id}`), `status_path`, `done_values`, `video_url_path`, `allowed_durations_s`, `allowed_aspect_ratios`.
بعد مطابقة كل حقل مع الصفحة الرسمية: `"verified": true` و`verified_on`.
المفاتيح في متغيرات البيئة فقط (`.env` مستثنى من git) — انظر `.env.example`.
