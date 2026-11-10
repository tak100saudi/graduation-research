# Season Venue — استوديو الإنتاج الإعلاني

استوديو إنتاج محلي يعمل عبر Claude Code لتخطيط وتوليد ومونتاج وفحص 22 مقطعًا إعلانيًا
(الفيديو البطل `HERO42` + 20 إعلان أداء T1–T5 / S1–S5 / X1–X5 / Y1–Y5 + مقطع غير محدد بعد).
الملف المرجعي هو `source/source_campaign.pdf`، وتعليمات المشروع في `CLAUDE.md`.

> **الحالة الحالية:** السكربتات الـ22 كلها مكتوبة (HERO42 وHERO15 و20 إعلانًا) من `source_campaign.pdf` مع تصحيحات brand_facts.md، وهي **بانتظار اعتماد المالك**: `docs/scripts_ar.md`.
> أُنتج محليًا: أنيماتك توقيت لكل مقطع، والخط الأخضر وخلفيات بطاقات النهاية (موشن جرافيك). **لم يُولَّد أي فيديو بالذكاء الاصطناعي** لعدم ربط مزوّد بعد.

## مراجع المالك (حزمة season_venue_kit)

ترتيب المرجعية: `source/owner/brand_facts.md` ← البوسترات وعرض الشركاء وموقع الديمو ← `source_campaign.pdf`.
هذه الحقائق مُرمَّزة في `plans/campaign.json` وتُفرض آليًا:

- **`banned_phrases`**: كل تصحيحات brand_facts (السعر قدامك، تأكيد فوري، الدفع داخل المنصة، موثّق، تابي/تمارا، …) مع البديل المعتمد. تُفحص في التعليق الصوتي والنصوص والبرومبت الإنجليزي، مع تجاهل التشكيل واختلاف الألف.
- **`claims_evidence`**: الادعاءات المعتمدة فقط بصياغتها ومصدرها (عرض واحد، شروط مكتوبة قبل التأكيد، عقد وعربون، 6 خطوات، فترة إثبات الشركاء…).
- **`required_disclosures`**: أي ذكر للدفع المرن أو التمويل يتطلب إفصاحًا ظاهرًا على الشاشة: «جهات تمويل مرخصة من ساما… Season Venue لا تقدّم تمويلاً».
- **`forbidden_ui_features`**: فلتر التاريخ، التذكير، الفاتورة، تقويم المالك، الحجز الفوري.
- **`plans/product_flow.json`**: خطوات نموذج الطلب الست + تأكيد الاستلام. أي لقطة واجهة يجب أن تكون تسجيل شاشة حقيقيًا مرتبطًا بخطوة منه، وتبقى معلّقة حتى يُتحقق من الموقع.
- **الهوية**: الشعار الرسمي في `assets/brand/` (يُستخدم كما هو، لا يُعاد رسمه أو توليده). الأخضر المعتمد `#33650C` مع ذهبي `#CBA401` وكريمي `#FAF6ED`. الخط في المسودات Tajawal (`assets/brand/fonts/`، رخصة OFL) إلى أن يُرخَّص 29LT Bukra.
- **CTA**: «قريبًا» إلى أن يرسل المالك الرابط ورقم التواصل. رابط الديمو محظور في الإعلانات.
- **الشخصيات والمواقع**: C1–C5 وL1–L5 من الـPDF في `plans/continuity.json`. كلها مولّدة (`synthetic_ai`)، وكل واحدة تحتاج صورة مرجعية معتمدة قبل أي فيديو.

> مستندات المالك وملف الحملة مستثناة من git (`source/owner/`، `source/source_campaign.pdf`) لأن المستودع **عام**.

## التشغيل السريع

```bash
pip install -r requirements-dev.txt     # pytest + pypdf (الأداة نفسها تعمل بمكتبة بايثون القياسية)
python scripts/studio.py validate        # فحص المدد، الاستمرارية، الادعاءات، سرعة التعليق الصوتي
python scripts/studio.py validate --production   # يفشل حتى تُحل كل العوائق
python scripts/studio.py storyboard --all         # output/storyboards/*.md + output/prompts/*.json
python scripts/studio.py graphics --all             # موشن جرافيك محلي: الخط الأخضر + خلفية بطاقة النهاية
python scripts/studio.py animatic --video all        # أنيماتك توقيت لكل المقاطع (شرائح + نصوص عربية + شعار) — ليس لقطات
python tools/build_scripts.py && python tools/build_script_doc.py   # إعادة بناء سكربتات الإعلانات ووثيقة المراجعة
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
