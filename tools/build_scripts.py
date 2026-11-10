#!/usr/bin/env python3
"""Writes plans/videos/*.json for HERO15 + the 20 performance ads.

Source: source_campaign.pdf pp7-22 (beats, durations, visuals), corrected per
source/owner/brand_facts.md. Every end card says «قريبًا» (owner instruction):
action CTAs (اطلب الآن / اسحب للأعلى / زر الموقع) come back once the owner
supplies the public URL. Scripts are status 'scripted' = awaiting owner approval.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REC = "assets/screen_recordings/request_flow_9x16.mp4"
COLD = "cool flat daylight, desaturated cool grade"
WARM = "warm golden light, olive green, sand beige and calm gold palette"
TAG = "طلب واحد.. عرض واحد.. مناسبة أسهل"
BRAND_VO = "سيزون فينيو… قريبًا."


class V:
    def __init__(self, vid):
        self.vid = vid
        self.path = ROOT / "plans" / "videos" / f"{vid}.json"
        self.d = json.loads(self.path.read_text(encoding="utf-8"))
        self.d["shots"] = []
        self.primary = self.d["aspect_ratios"][0]

    def shot(self, s, e, beat, pdf="", scene="SYSTEM", mode="image_to_video", ratios=None, **kw):
        n = len(self.d["shots"]) + 1
        gen = {"mode": mode, "seed": None, "source_ratios": ratios or [self.primary]}
        gen.update(kw.pop("generation", {}))
        d = {"id": f"{self.vid}_{n:02d}", "pdf_ref": pdf, "start_s": s, "end_s": e, "beat": beat, "scene": scene,
             "characters": [], "location": "", "action": "", "camera": {}, "lighting": "",
             "vo_ar": "", "overlay_ar": [], "claims": [], "sfx": "", "negative_extra": [],
             "generation": gen, "status": "scripted"}
        if "vo" in kw:
            text, vs, ve = kw.pop("vo")
            d.update(vo_ar=text, vo_start_s=vs, vo_end_s=ve)
        d.update(kw)
        self.d["shots"].append(d)
        return d

    def card(self, s, e, vo=BRAND_VO, headline=TAG, pdf="", extra=None, claims=None):
        ov = [{"text": headline, "start_s": round(s + 0.5, 2), "end_s": e, "position": "lower_third", "style": "headline"},
              {"text": "قريبًا", "start_s": round(s + 0.9, 2), "end_s": e, "position": "bottom", "style": "cta"}]
        return self.shot(s, e, "end card", pdf, "END", "graphics", ratios=list(self.d["aspect_ratios"]),
                         action="Motion graphics: olive-green background with a soft light shimmer; the official logo fades in",
                         vo=(vo, round(s + 0.3, 2), round(min(e - 0.4, s + 0.3 + max(1.4, len(vo.split()) / 2.0)), 2)),
                         overlay_ar=ov + (extra or []), claims=claims or ["CLM_ONE_OFFER"],
                         logo={"start_s": round(s + 0.2, 2), "end_s": e, "width_frac": 0.30, "variant": "dark", "fade_s": 0.4},
                         generation={"graphic": "end_card", "color": "#33650C"}, sfx="music resolves, no bells")

    def save(self, concept, changes, **meta):
        self.d.update(concept=concept, source_status="scripted", reconciliation=changes, **meta)
        self.path.write_text(json.dumps(self.d, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def insert(steps, note="Real recording of the request form only; test data, never a real customer's details."):
    return {"flow_steps": steps, "source_path": REC, "method": "tracked screen replace onto the green phone screen", "note": note}


def ov(text, s, e, pos="lower_third", style="headline", **kw):
    return dict({"text": text, "start_s": s, "end_s": e, "position": pos, "style": style}, **kw)


PHONE_HAND = ("Close-up of his hand holding a smartphone with a blank green screen, thumb scrolling and tapping smoothly, "
              "white thobe sleeve and silver wristwatch visible")
PHONE_CAM = {"shot_size": "CU", "lens_mm": 50, "movement": "static with slight natural hand motion", "focus": "shallow depth of field"}

# ------------------------------------------------------------------ HERO15
v = V("HERO15")
v.shot(0, 3, "hook · last time", "1", "CHAOS", characters=["C1"], location="L1",
       action="Tight close-up, he looks up from his phone with a frustrated, unimpressed expression directly toward camera, the screen is not visible",
       camera={"shot_size": "CU", "lens_mm": 50, "movement": "quick subtle push-in"}, lighting=COLD,
       vo=("آخر مرة تسمع: «كلّمني خاص».", 0.3, 2.8),
       overlay_ar=[ov("«كلّمني خاص»؟ خلاص.", 0.3, 2.9, "center", "headline", kind="chat_bubble")],
       sfx="phone vibration in the first second", negative_extra=["smiling", "empty frame at start", "slow pacing"])
v.shot(3, 8, "one request", "2", characters=["C1"], action=PHONE_HAND, camera=PHONE_CAM,
       lighting="warm golden interior light, cinematic product-style shot",
       vo=("مع سيزون فينيو… طلب واحد، ونرجع لك بعرض واحد.", 3.2, 7.6),
       subtitle_ar="مع Season Venue… طلب واحد، ونرجع لك بعرض واحد.",
       overlay_ar=[ov("طلب واحد · عرض واحد", 3.4, 7.8)], claims=["CLM_ONE_OFFER"], shows_product_ui=True,
       screen_insert=insert(["STEP1_EVENT_TYPE", "STEP3_GUESTS_BUDGET_ATTENDANCE", "STEP4_SERVICES"]), ratios=["9x16"])
v.shot(8, 12, "payoff", "3", "EVENT", characters=["C1", "C5"], location="L3",
       action="He pours Arabic coffee from a gold-accented dallah into a small cup for smiling guests",
       camera={"shot_size": "MS", "lens_mm": 35, "movement": "slow gimbal arc"}, lighting="dusk, warm lanterns, " + WARM,
       vo=("بسعر وشروط مكتوبة… وخلّ بالك مع ضيوفك.", 8.2, 11.7), claims=["CLM_WRITTEN_TERMS"])
v.card(12, 15, vo="مناسبتك… تبدأ من هنا.", headline="مناسبتك… تبدأ من هنا", pdf="4")
v.save("رحلة فيصل مضغوطة في 15 ثانية: الجملة المؤلمة «كلّمني خاص» ثم طلب واحد وعرض واحد وليلة مرتّبة.",
       [{"pdf_shot": "1", "change": "kept"},
        {"pdf_shot": "2", "change": "«السعر واضح، والمكان موثّق، وكل الخدمات في حجز واحد» + price/verified screen → one request, one offer; real request-form recording"},
        {"pdf_shot": "3", "change": "«احجز» button press removed; VO now carries the written price and terms"},
        {"pdf_shot": "4", "change": "#33650C, real logo, CTA «قريبًا»"}],
       edit_notes={"cuts": "0.8–1.2s cuts inside 3–8s; cold grade shot 1, warm after", "music": "15s cut of the HERO42 theme from the silence point"})

# ------------------------------------------------------------------ T1
v = V("T1")
v.shot(0, 3, "hook · three bubbles", "T1-A", "CHAOS", characters=["C1"], location="L1",
       action="He sits staring at his phone with a blank green screen, then exhales in mild exasperation",
       camera={"shot_size": "MCU", "lens_mm": 50, "movement": "static with micro push-in"}, lighting=COLD,
       vo=("«كلّمني خاص»… للمرة الثالثة.", 0.3, 2.8),
       overlay_ar=[ov("كلّمني خاص", 0.2, 2.9, "top", "body", kind="chat_bubble"), ov("كلّمني خاص", 0.8, 2.9, "center", "body", kind="chat_bubble"),
                   ov("كلّمني خاص", 1.4, 2.9, "lower_third", "body", kind="chat_bubble")],
       sfx="muffled voice-call tone, no bells", negative_extra=["smiling"])
v.shot(3, 6, "wipe it away", "T1-B", characters=["C1"], location="L1",
       action="He swipes his index finger across the air in front of the camera with a confident half-smile, as if clearing something away",
       camera={"shot_size": "MCU", "lens_mm": 35, "movement": "static"}, lighting="warm light shifting in",
       vo=("اللفّ والدوران على السعر؟ خلاص.", 3.2, 5.8), claims=["CLM_PAIN_QUESTIONS"],
       edit_graphics=[{"type": "bubbles wiped by the finger", "note": "motion graphics"}], sfx="fast music beat")
v.shot(6, 11, "written price and terms", "T1-C", characters=["C1"], action=PHONE_HAND.replace("scrolling and tapping smoothly", "scrolling slowly"),
       camera=PHONE_CAM, lighting="warm golden light",
       vo=("مع سيزون فينيو… سعر وشروط مكتوبة قبل ما تأكد.", 6.2, 10.6), subtitle_ar="مع Season Venue… سعر وشروط مكتوبة قبل ما تأكد.",
       overlay_ar=[ov("سعر وشروط مكتوبة قبل ما تأكد", 6.4, 10.8)], claims=["CLM_WRITTEN_TERMS"], shows_product_ui=True,
       screen_insert=insert(["STEP1_EVENT_TYPE", "STEP3_GUESTS_BUDGET_ATTENDANCE"]))
v.card(11, 15, vo="طلب واحد… ونرجع لك بعرض واحد.")
v.save("الجملة المؤلمة «كلّمني خاص» تتكرر ثم تُمسح: السعر والشروط تصلك مكتوبة قبل التأكيد.",
       [{"pdf_shot": "6–11", "change": "«السعر ظاهر على كل مكان» + venue page with its price → written price and terms; request-form recording"},
        {"pdf_shot": "11–15", "change": "«حمّل… وشف الأسعار» → one request, one offer; CTA «قريبًا»"},
        {"pdf_shot": "3–6", "change": "«الأسعار المخفية؟ خلاص» softened so it does not imply public prices"}])

# ------------------------------------------------------------------ T2
v = V("T2")
v.shot(0, 3, "hook · racing the clock", "T2-A", "CHAOS", characters=["C1"], location="L1",
       action="Handheld shot, he paces quickly across the majlis with a phone to his ear, slightly stressed expression",
       camera={"shot_size": "MS", "lens_mm": 35, "movement": "energetic handheld follow"}, lighting=COLD,
       vo=("إيه… قريب… كم الضيوف؟", 0.3, 2.7), vo_speaker="C1 (on-camera line, native sound)",
       overlay_ar=[ov("POV: عزيمتك قرّبت وما حجزت شي", 0.2, 2.9, "top", "headline")],
       sfx="light room noise, fast pulse", negative_extra=["smiling"])
v.shot(3, 6, "breathe", "T2-B", characters=["C1"], location="L1",
       action="He sits down on the floor cushions, takes a slow breath and unlocks his phone with a blank green screen",
       camera={"shot_size": "MS", "lens_mm": 35, "movement": "static"}, lighting="light warming gradually",
       vo=("هدّ أعصابك.", 3.6, 5.2), sfx="soft transition into oud at 6s")
v.shot(6, 12, "one request", "screen", characters=["C1"], action=PHONE_HAND, camera=PHONE_CAM, lighting="warm golden light",
       vo=("طلب واحد: المكان، والضيافة، والخدمات… ونرجع لك بعرض واحد.", 6.3, 11.6),
       overlay_ar=[ov("مكان + ضيافة + خدمات = طلب واحد", 6.5, 11.8)], claims=["CLM_ONE_OFFER"], shows_product_ui=True,
       screen_insert=insert(["STEP1_EVENT_TYPE", "STEP4_SERVICES", "STEP6_REVIEW_SUBMIT"]))
v.shot(12, 16, "relief", "T2-C", characters=["C1"], location="L1",
       action="He leans back relaxed on a sand-beige sofa, places his phone face down on a wooden table and smiles contentedly",
       camera={"shot_size": "MS", "lens_mm": 35, "movement": "slow pull-out"}, lighting="warm golden afternoon light",
       vo=("أرسلت طلبك؟ الفريق يتواصل معك.", 12.3, 15.4))
v.card(16, 18, vo="قريبًا.")
v.save("سباق مع الوقت ينتهي بهدوء: بدل المكالمات، طلب واحد يجمع المكان والضيافة والخدمات.",
       [{"pdf_shot": "0–3", "change": "«عزيمتك بكرة» → «عزيمتك قرّبت»: the team reviews and replies, so no next-day promise. OPEN: owner to confirm lead time"},
        {"pdf_shot": "6–12", "change": "«اختيار مكان + إضافة ذبائح وضيافة» booking screen → request-form recording"},
        {"pdf_shot": "12–16", "change": "«خلصت. [المدة الفعلية للحجز]» removed (no instant booking) → the team gets in touch"},
        {"pdf_shot": "16–18", "change": "«احجز الليلة» → «قريبًا»"}])

# ------------------------------------------------------------------ T3
v = V("T3")
v.shot(0, 4, "hook · expectation / reality", "T3-A + T3-B", "CHAOS", mode="graphics",
       action="Split screen 50/50 assembled in the edit from two generated plates with matching slow vertical tilts",
       composite={"layout": "vertical split 50/50, right = expectation, left = reality", "plates": [
           {"clip": "T3_01A", "seconds": 4, "location": "L3", "prompt_en": "Elegant Saudi istiraha at dusk with Najdi mud-plaster walls, warm lanterns, majlis seating and palm trees, slow vertical tilt down, cinematic photorealistic"},
           {"clip": "T3_01B", "seconds": 4, "location": "L2", "prompt_en": "Dusty, poorly lit rest-house courtyard with faded artificial grass, scattered plastic chairs and a flickering bulb, flat grey daylight, slow vertical tilt down matching the previous shot, desaturated, photorealistic"}]},
       vo=("الصورة شي… والمكان شي ثاني؟", 0.4, 3.4), overlay_ar=[ov("التوقع / الواقع", 0.3, 3.8, "top", "headline")])
v.shot(4, 7, "the divider turns green", "", "TURN", mode="graphics",
       action="Motion graphics: the divider line between the two halves turns olive green and straightens",
       generation={"graphic": "green_line", "color": "#33650C"}, sfx="one clean rise, no bells")
v.shot(7, 12, "the offer in writing", "replaces 7–12", characters=["C1"], location="L1", ratios=["16x9"],
       action="He sits relaxed on the floor cushions reading a single printed offer sheet, nodding calmly, the document text is soft and unreadable",
       camera={"shot_size": "MCU", "lens_mm": 50, "movement": "slow push-in"}, lighting=WARM,
       negative_extra=["readable document text", "numbers", "official stamps"],
       generation={"reframe_note": "16:9 master shared with X1_03; cropped to 9:16 here"},
       vo=("مع سيزون فينيو… عرض مكتوب: السعر والشروط قبل ما تأكد.", 7.2, 11.8),
       subtitle_ar="مع Season Venue… عرض مكتوب: السعر والشروط قبل ما تأكد.",
       overlay_ar=[ov("عرض واحد مكتوب", 7.4, 11.8)], claims=["CLM_WRITTEN_TERMS", "CLM_ONE_OFFER"])
v.card(12, 15)
v.save("ترند «التوقع / الواقع»: بدل الاعتماد على صورة، العرض يصلك مكتوبًا بسعره وشروطه قبل التأكيد.",
       [{"pdf_shot": "7–12", "change": "«الأماكن موثّقة قبل ما تظهر لك» + verified-venue screen + real venue footage → postponed (no announced verification process). Replaced by the written offer. OPEN: is there a venue-inspection policy we may state?"},
        {"pdf_shot": "12–15", "change": "«تصفّح الأماكن الموثّقة» → tagline + «قريبًا»"}])

# ------------------------------------------------------------------ T4
v = V("T4")
v.shot(0, 3, "hook · mum asks", "T4-A", characters=["C2", "C1"], location="L1",
       action="She walks into the majlis and asks a question with a gentle, slightly worried look; he looks up from his phone",
       camera={"shot_size": "MS", "lens_mm": 35, "movement": "static"}, lighting="soft afternoon light",
       vo=("فيصل، حجزت ولا لا؟", 0.3, 2.6), vo_speaker="C2 (recorded dialogue)")
v.shot(3, 7, "he shows the confirmation", "T4-B", characters=["C1"], location="L1",
       action="He turns his phone toward her with a reassuring smile, the phone shows a blank green screen",
       camera={"shot_size": "MCU", "lens_mm": 50, "movement": "slow push-in"}, lighting="warm light",
       vo=("أرسلت الطلب يمّه… وهذا تأكيد الاستلام.", 3.3, 6.7), vo_speaker="C1 (recorded dialogue)",
       shows_product_ui=True, screen_insert=insert(["CONFIRMATION"]))
v.shot(7, 12, "relief", "T4-C", characters=["C2", "C1"], location="L1",
       action="She smiles warmly and pats his shoulder, both relaxed",
       camera={"shot_size": "MS", "lens_mm": 50, "movement": "slow gentle arc"}, lighting=WARM,
       vo=("طلب واحد… والفريق يرجع لك بعرض واحد. وبال أهلك مرتاح.", 7.2, 11.8),
       overlay_ar=[ov("طلب واحد · عرض واحد", 7.4, 11.8)], claims=["CLM_ONE_OFFER"], sfx="light oud")
v.card(12, 16)
v.save("لحظة عائلية دافئة: سؤال الأم «حجزت ولا لا؟» يُجاب بتأكيد استلام الطلب، والفريق يكمل.",
       [{"pdf_shot": "3–7", "change": "«حجزت يمه، وهذا التأكيد» → request sent + receipt confirmation (the real screen after submitting)"},
        {"pdf_shot": "7–12", "change": "«تأكيد فوري» banned → one request, the team comes back with one offer"},
        {"pdf_shot": "12–16", "change": "«احجز… وارتاح» → tagline + «قريبًا»; reminder feature not mentioned"}],
       audio_note="Dialogue recorded by two Saudi voice actors; announcer only from 7s.")

# ------------------------------------------------------------------ T5
v = V("T5")
v.shot(0, 3, "hook · stop", "T5-A", "CHAOS", mode="reuse", generation={"reuse": "HERO42_05"},
       vo=("لا تحوّل عربون… قبل ما تشوف هذا.", 0.1, 3.0), overlay_ar=[ov("لحظة!", 0.2, 2.8, "top", "headline")],
       claims=["CLM_PAIN_QUESTIONS"])
v.shot(3, 7, "he pulls back", "T5-B", "CHAOS", characters=["C1"], location="L1",
       action="He pulls his thumb back and thoughtfully turns his phone over on the table, the screen is not visible",
       camera={"shot_size": "MCU", "lens_mm": 50, "movement": "static"}, lighting="cool light easing into warm",
       vo=("التحويل لحساب ما تعرفه؟ مخاطرة.", 3.3, 6.4), claims=["CLM_PAIN_QUESTIONS"],
       negative_extra=["bank logos", "account numbers"])
v.shot(7, 12, "contract and deposit", "replaces 7–12", characters=["C1"], location="L1",
       action="He signs a printed contract on the wooden coffee table with a pen, the document text is soft and unreadable, then looks up with a small relieved smile",
       camera={"shot_size": "CU", "lens_mm": 50, "movement": "slow push-in from the pen to his face"}, lighting=WARM,
       negative_extra=["readable document text", "official stamps", "cash", "card terminal"],
       vo=("مع سيزون فينيو… عقد مكتوب، وعربون يثبت حجزك.", 7.3, 11.5), subtitle_ar="مع Season Venue… عقد مكتوب، وعربون يثبت حجزك.",
       overlay_ar=[ov("عقد مكتوب وعربون يثبت حجزك", 7.5, 11.8)], claims=["CLM_CONTRACT_DEPOSIT"])
v.card(12, 15)
v.save("توعية مباشرة تحوّل الخوف إلى حل: لا تحويل لحساب مجهول، بل عقد مكتوب وعربون يثبت الحجز.",
       [{"pdf_shot": "7–12", "change": "«الدفع داخل المنصة… محفوظ لك» + pay-step screen → contract and deposit (same action as HERO42 shot 10, generated vertical at 5s)"},
        {"pdf_shot": "12–15", "change": "«احجز بأمان» → tagline + «قريبًا»"},
        {"pdf_shot": "0–3", "change": "reuses HERO42 shot 5, as the PDF edit plan intends"}])

# ------------------------------------------------------------------ S1
v = V("S1")
v.shot(0, 3, "hook · selfie", "S1-A", "EVENT", characters=["C1"], location="L3",
       action="Front-facing selfie-style video, he talks cheerfully to camera, natural handheld phone movement",
       camera={"shot_size": "MCU", "lens_mm": 24, "movement": "handheld selfie"}, lighting="dusk, warm lanterns behind him",
       vo=("يا شباب… كل شي جاهز!", 0.3, 2.6), vo_speaker="C1 (on-camera line)", negative_extra=["overly polished look"],
       sfx="light wind, firewood crackle")
v.shot(3, 8, "the spread", "S1-B", "EVENT", location="L3",
       action="Handheld phone-camera reveal of an elegant hospitality setup: gold-accented dallah pots, finjan cups, dates in brass bowls and majlis cushions, natural walking movement",
       camera={"shot_size": "WS", "lens_mm": 24, "movement": "handheld walk"}, lighting="warm lantern glow",
       vo=("بدون ما تنسّق مع خمس جهات…", 3.4, 6.4), mode="text_to_video")
v.shot(8, 12, "one request for everything", "screen", characters=["C1"], action=PHONE_HAND, camera=PHONE_CAM, lighting="warm lantern light",
       vo=("طلب واحد… لكل شي.", 8.3, 10.6), overlay_ar=[ov("طلب واحد لكل شي", 8.4, 11.8)], claims=["CLM_ONE_OFFER"],
       shows_product_ui=True, screen_insert=insert(["STEP4_SERVICES"]))
v.card(12, 15)
v.save("فيصل يصوّر سناب لأصحابه وكل شيء جاهز قبل وصولهم: طلب واحد جمع المكان والضيافة.",
       [{"pdf_shot": "8–12", "change": "«حجز واحد» booking screen → request-form services step"},
        {"pdf_shot": "12–15", "change": "«اسحب للأعلى… واحجز» + arrow → «قريبًا» (no link yet; the swipe-up arrow returns with the URL)"}])

# ------------------------------------------------------------------ S2
v = V("S2")
v.shot(0, 4, "hook · three answers", "S2-A", "CHAOS", characters=["C5"], location="L1",
       action="Three of the young men sit side by side on a majlis bench, each holding up a smartphone with a blank green screen toward camera, exchanging puzzled glances",
       camera={"shot_size": "MS", "lens_mm": 35, "movement": "static"}, lighting=COLD,
       vo=("نفس المكان… وثلاث أسعار؟", 0.4, 3.4), overlay_ar=[ov("؟ ؟ ؟", 0.3, 3.8, "top", "headline")], claims=["CLM_PAIN_QUESTIONS"],
       edit_graphics=[{"type": "question marks on the three screens", "note": "never write different prices as numbers (PDF)"}])
v.shot(4, 7, "they laugh", "S2-B", characters=["C5"], location="L1",
       action="The same three men laugh and shake their heads in friendly disbelief",
       camera={"shot_size": "MS", "lens_mm": 35, "movement": "slight push-in"}, lighting="warm light easing in")
v.shot(7, 12, "one offer, in writing", "screen", characters=["C1"], action=PHONE_HAND, camera=PHONE_CAM, lighting="warm golden light",
       vo=("مع سيزون فينيو… عرض واحد، بسعر وشروط مكتوبة.", 7.3, 11.4),
       subtitle_ar="مع Season Venue… عرض واحد، بسعر وشروط مكتوبة.",
       overlay_ar=[ov("عرض واحد مكتوب قبل ما تأكد", 7.4, 11.8)], claims=["CLM_ONE_OFFER", "CLM_WRITTEN_TERMS"],
       shows_product_ui=True, screen_insert=insert(["STEP6_REVIEW_SUBMIT"]))
v.card(12, 15)
v.save("ثلاثة أصدقاء سألوا عن نفس المكان وجاءهم ثلاثة أسعار: الحل عرض واحد مكتوب.",
       [{"pdf_shot": "7–12", "change": "«السعر معلن… وتشوفه قبل ما تحجز» + venue page with public price → one written offer"},
        {"pdf_shot": "12–15", "change": "«شف السعر الحين» / swipe up → «قريبًا»"}])

# ------------------------------------------------------------------ S3
v = V("S3")
v.shot(0, 3, "hook · group chat", "S3-A", characters=["C1"],
       action="He sits in his car in a Riyadh parking lot, raises his phone with a blank green screen and smiles at incoming messages, natural light through the windshield",
       camera={"shot_size": "MCU", "lens_mm": 35, "movement": "static"}, lighting="golden hour",
       overlay_ar=[ov("«وين جمعة الخميس؟»", 0.2, 2.9, "top", "body", kind="chat_bubble")],
       edit_graphics=[{"type": "group notifications", "note": "generic bubbles, no real messaging app name"}], sfx="soft taps, no notification chime")
v.shot(3, 9, "date and guests", "screen", characters=["C1"], action=PHONE_HAND, camera=PHONE_CAM, lighting="golden hour light",
       vo=("اكتب التاريخ التقريبي… وعدد الضيوف… وأرسل طلبك.", 3.3, 8.6),
       overlay_ar=[ov("التاريخ · العدد · أرسل", 3.5, 8.8)], shows_product_ui=True,
       screen_insert=insert(["STEP2_CITY_DATE", "STEP3_GUESTS_BUDGET_ATTENDANCE", "STEP6_REVIEW_SUBMIT"]))
v.shot(9, 12, "sent", "S3-B", characters=["C1"],
       action="He types quickly and sends a message with a satisfied grin, slight handheld movement, the screen is not visible",
       camera={"shot_size": "MCU", "lens_mm": 35, "movement": "slight handheld"}, lighting="warm golden hour light",
       overlay_ar=[ov("«أرسلت الطلب»", 9.2, 11.8, "top", "body", kind="chat_bubble")])
v.card(12, 15)
v.save("رسالة في قروب الشباب «وين جمعة الخميس؟» تتحوّل إلى طلب بتاريخ تقريبي وعدد ضيوف.",
       [{"pdf_shot": "3–9", "change": "date/guest FILTER and «تطلع لك الأماكن المتاحة» (unconfirmed feature) → the form's own date and guest fields"},
        {"pdf_shot": "9–12", "change": "«حجزت» + venue photo → «أرسلت الطلب»"},
        {"pdf_shot": "12–15", "change": "swipe up → «قريبًا»"}])

# ------------------------------------------------------------------ S4
v = V("S4")
for i, (src, t) in enumerate([("HERO42_01", 0), ("HERO42_02", 1), ("HERO42_05", 2), ("HERO42_04", 3)]):
    kw = {}
    if i == 0:
        kw = dict(vo=("السوق كان يحتاج ترتيب…", 0.4, 3.4))
    v.shot(t, t + 1, f"chaos montage {i+1}/4", "0–4", "CHAOS", mode="reuse", generation={"reuse": src}, **kw)
v.shot(4, 6, "the green line", "4–6", "TURN", mode="graphics", ratios=["9x16"],
       action="Motion graphics: black screen, the crooked olive-green line straightens and glows",
       generation={"graphic": "green_line", "color": "#33650C"}, vo=("وصل.", 4.6, 5.6))
v.shot(6, 12, "partner venues, one offer", "replaces 6–12", "SYSTEM", mode="text_to_video", location="L4",
       action="Slow glide through the empty, beautifully prepared hall with round tables set",
       camera={"shot_size": "WS", "lens_mm": 24, "movement": "slow dolly forward"}, lighting="soft warm chandelier light",
       vo=("سيزون فينيو… قاعات وشاليهات واستراحات شريكة، وعرض واحد واضح.", 6.3, 11.6),
       subtitle_ar="Season Venue… قاعات وشاليهات واستراحات شريكة، وعرض واحد واضح.",
       overlay_ar=[ov("قاعات · شاليهات · استراحات شريكة", 6.5, 11.8)], claims=["CLM_PARTNER_VENUES", "CLM_ONE_OFFER"])
v.card(12, 15, vo="تعرّف علينا… قريبًا.")
v.save("إعلان العلامة: أربع لقطات فوضى سريعة تتجمّع في خط أخضر يستقيم، ثم قاعات شريكة وعرض واحد.",
       [{"pdf_shot": "0–4", "change": "kept: recut of HERO42 shots 1, 2, 4, 3B at 9:16, no new generation. «منظّم» → «ترتيب» so it cannot read as a regulator claim (owner may restore)"},
        {"pdf_shot": "6–12", "change": "«أماكن موثّقة، وأسعار واضحة» + verified-venues grid + count → partner venues and one clear offer, no number"},
        {"pdf_shot": "12–15", "change": "swipe up → «قريبًا»"}])

# ------------------------------------------------------------------ S5
v = V("S5")
v.shot(0, 3, "hook · the endless list", "S5-A", "CHAOS", mode="text_to_video",
       action="Close-up of a hand writing a long checklist on cream paper with a gold pen, the list partially blurred and unreadable",
       camera={"shot_size": "CU", "lens_mm": 50, "movement": "static", "focus": "shallow depth of field"}, lighting="soft warm desk lamp light",
       vo=("ليلة العمر… وتفاصيلها ما تخلص.", 0.3, 2.9), overlay_ar=[ov("قاعة؟ ضيافة؟ تنسيق؟", 0.3, 2.9, "top", "headline")],
       negative_extra=["readable handwriting"], sfx="delicate qanun with strings")
v.shot(3, 9, "the hall", "S5-B", location="L4", mode="text_to_video",
       action="The hall is empty of guests; an event staff team in neat black uniforms sets the round tables",
       camera={"shot_size": "WS", "lens_mm": 24, "movement": "smooth slow dolly forward"}, lighting="soft warm light, crystal chandeliers",
       vo=("القاعة، والضيافة، والخدمات… في حجز واحد.", 3.4, 8.2), claims=["CLM_ONE_OFFER"],
       negative_extra=["bride", "groom", "wedding guests"])
v.shot(9, 14, "one line through the list", "S5-C", mode="text_to_video",
       action="Close-up of the same gold pen drawing one confident line through the entire checklist",
       camera={"shot_size": "CU", "lens_mm": 50, "movement": "static"}, lighting="warm light",
       vo=("ونتابع معك… حتى تسليم القاعة.", 9.4, 12.6), overlay_ar=[ov("نتابع الحجز حتى تسليم القاعة", 9.6, 13.8)],
       claims=["CLM_FOLLOW_UP"], negative_extra=["readable handwriting"])
v.card(14, 18, vo="ابدأ تخطيط زواجك من هنا.", headline="ليلة العمر… بطلب واحد")
v.save("تفاصيل الزواج الكثيرة تُختصر في حجز واحد: قائمة مهام طويلة تُشطب بخط واحد.",
       [{"pdf_shot": "9–14", "change": "«مع شركاء تنظيم معتمدين [العدد]» → number and «معتمدين» removed; replaced by follow-up until hall handover (poster 2)"},
        {"pdf_shot": "9–14", "change": "booking screen removed; the strike-through carries the beat"},
        {"pdf_shot": "14–18", "change": "swipe up → «قريبًا»"}],
       caution="Never show a real bride, groom or guests; hall and set-up only (PDF).")

# ------------------------------------------------------------------ X1
v = V("X1")
v.shot(0, 4, "hook · one question", "0–4", "TURN", mode="graphics", ratios=list(v.d["aspect_ratios"]),
       action="Motion graphics: kinetic white text on an olive-green background",
       generation={"graphic": "kinetic_text", "color": "#33650C"},
       vo=("سؤال واحد… ليش سعر المناسبة سرّ؟", 0.4, 3.6), overlay_ar=[ov("ليش سعر المناسبة سرّ؟", 0.4, 3.9, "center", "headline")],
       claims=["CLM_PAIN_QUESTIONS"])
v.shot(4, 8, "the call that goes nowhere", "X1-A", "CHAOS", characters=["C1"], location="L1",
       action="He stands by a window with his phone to his ear, waiting, then lowers it and shakes his head slightly",
       camera={"shot_size": "MS", "lens_mm": 35, "movement": "static"}, lighting="cool overcast daylight", negative_extra=["smiling"])
v.shot(8, 12, "the offer in writing", "replaces 8–12", mode="reuse", generation={"reuse": "T3_03"},
       vo=("مع سيزون فينيو… السعر والشروط مكتوبة.", 8.3, 11.6), subtitle_ar="مع Season Venue… السعر والشروط مكتوبة.",
       overlay_ar=[ov("سعر وشروط مكتوبة قبل ما تأكد", 8.4, 11.8)], claims=["CLM_WRITTEN_TERMS"])
v.card(12, 15)
v.save("سؤال واحد مباشر على خلفية صامتة يفتح النقاش: ليش سعر المناسبة سرّ؟",
       [{"pdf_shot": "8–12", "change": "«السعر معلن» + venue page with price → written price and terms; printed offer sheet, unreadable (shares the T3_03 master)"},
        {"pdf_shot": "12–15", "change": "«زُر الموقع» → «قريبًا»"}],
       tweet_ar="سؤال بسيط: ليش لازم تتصل عشان تعرف سعر مكان لمناسبتك؟ مع Season Venue: طلب واحد، وعرض واحد بسعر وشروط مكتوبة قبل ما تأكد. قريبًا.",
       tweet_note="PDF hashtag #السوق_صار_له_نظام dropped (reads as a regulator claim); owner may supply one.")

# ------------------------------------------------------------------ X2
v = V("X2")
gfx = dict(mode="graphics", ratios=list(v.d["aspect_ratios"]))
v.shot(0, 2, "title", "0–2", "CHAOS", action="Motion graphics: title card on a cream background with burnt-orange icons",
       generation={"graphic": "title_card"}, vo=("خمس علامات… شفتها؟ وقف.", 0.1, 1.95),
       overlay_ar=[ov("خمس علامات إن الحجز فيه مشكلة", 0.2, 1.9, "center", "headline")], **gfx)
cards = ["السعر ما ينقال إلا خاص.", "الصور ما فيها تفاصيل.", "عربون لحساب شخصي.", "ما فيه تأكيد مكتوب.", "الضيافة تنسّقها لحالك."]
for i, text in enumerate(cards):
    s = round(2 + 2.4 * i, 1); e = round(s + 2.4, 1)
    v.shot(s, e, f"warning card {i+1}/5", "2–14", "CHAOS", action="Motion graphics: a cream card with a simple burnt-orange icon slides in",
           generation={"graphic": "list_card"}, vo=(text, round(s + 0.05, 2), round(e - 0.05, 2)),
           overlay_ar=[ov(text.rstrip("."), round(s + 0.1, 1), round(e - 0.05, 2), "center", "headline")], claims=["CLM_PAIN_QUESTIONS"], **gfx)
v.shot(14, 18, "the green line strikes the list", "14–18", "TURN",
       action="Motion graphics: the olive-green line strikes through the five cards and everything turns green",
       generation={"graphic": "green_line", "color": "#33650C"},
       vo=("مع سيزون فينيو… عرض مكتوب، وعقد يثبت حجزك.", 14.2, 17.9), subtitle_ar="مع Season Venue… عرض مكتوب، وعقد يثبت حجزك.",
       overlay_ar=[ov("عرض واحد مكتوب · عقد وعربون", 14.4, 17.8)], claims=["CLM_ONE_OFFER", "CLM_CONTRACT_DEPOSIT"], **gfx)
v.card(18, 20, vo="قريبًا.")
v.save("قائمة توعية بالموشن جرافيك كاملة: خمس علامات على حجز فيه مشكلة، يشطبها الخط الأخضر.",
       [{"pdf_shot": "0–2", "change": "«5» written as «خمس»"},
        {"pdf_shot": "14–18", "change": "«قواعدنا تمنع هالشي» + [platform rules] → the approved facts only: one written offer, contract and deposit"},
        {"pdf_shot": "18–20", "change": "«اعرف قواعدنا» + link → «قريبًا»"}],
       production_note="No video generation: full motion graphics in campaign colours; cream cards, burnt-orange #C8553D icons, all green at 14s.")

# ------------------------------------------------------------------ X3
v = V("X3")
v.shot(0, 4, "hook · the load", "X3-A", "CHAOS", characters=["C3"], location="L5",
       action="She sits at a glass desk surrounded by papers and an open laptop, rubbing her forehead in mild stress, the laptop screen is not visible",
       camera={"shot_size": "MS", "lens_mm": 35, "movement": "slow push-in"}, lighting="golden hour through glass walls",
       vo=("حفل الشركة… ومسؤوليته عليك.", 0.4, 3.4), negative_extra=["smiling"])
v.shot(4, 10, "one request for the company event", "screen", characters=["C3"], location="L5",
       action="She calmly fills a short form on her tablet with a blank green screen",
       camera={"shot_size": "MCU", "lens_mm": 50, "movement": "slow lateral slider"}, lighting="warm golden hour light",
       vo=("طلب واحد لفعالية شركتك… ونرجع لك بعرض واحد: قاعة، وضيافة، وخدمات.", 4.3, 9.8),
       overlay_ar=[ov("فعاليات الشركات · عرض واحد", 4.5, 9.8)], claims=["CLM_ONE_OFFER"], shows_product_ui=True,
       screen_insert=insert(["STEP1_EVENT_TYPE", "STEP4_SERVICES", "STEP6_REVIEW_SUBMIT"]))
v.shot(10, 15, "done", "X3-B", characters=["C3"], location="L5",
       action="She closes her laptop with a calm confident smile and turns toward two female colleagues in abayas who smile back",
       camera={"shot_size": "MS", "lens_mm": 35, "movement": "slow lateral slider"}, lighting="warm golden hour light flooding the office")
v.card(15, 18)
v.save("نورة، منسّقة الفعاليات، تنهي طلب فعالية الشركة بثقة: طلب واحد وعرض واحد.",
       [{"pdf_shot": "4–10", "change": "«مكان موثّق… وفاتورة واضحة… وتأكيد فوري» + booking screen → request form (event type «فعاليات الشركات»), one offer"},
        {"pdf_shot": "15–18", "change": "«احجز لفريقك» + link → «قريبًا»"}],
       tweet_ar="فعالية شركتك تبدأ بطلب واحد.. وعرض واحد: قاعة وضيافة وخدمات. Season Venue — قريبًا.")

# ------------------------------------------------------------------ X4
v = V("X4")
v.d["title_ar"] = "«عزيمتك الجاية… بطلب واحد»"
v.d["title_pdf"] = "«عزيمتك الجاية… بدون ولا مكالمة»"
v.shot(0, 3, "hook · stillness", "X4-A", mode="text_to_video",
       action="Still top-down shot of a smartphone lying motionless on a walnut wooden table next to a small finjan of Arabic coffee and dates, blank green screen",
       camera={"shot_size": "INSERT", "angle": "top-down", "lens_mm": 50, "movement": "very slow push-in"}, lighting="warm calm afternoon light",
       vo=("عزيمتك الجاية…", 0.6, 2.4), overlay_ar=[ov("طلب واحد", 0.5, 2.9, "top", "headline")], claims=["CLM_ONE_OFFER"])
v.shot(3, 11, "the whole request, honestly", "3–11", mode="screen_recording", ratios=["9x16"],
       action="Full real screen recording of the request form, sped up, composited over his hand holding the phone",
       generation={"source_path": REC, "flow_steps": ["STEP1_EVENT_TYPE", "STEP2_CITY_DATE", "STEP3_GUESTS_BUDGET_ATTENDANCE", "STEP4_SERVICES", "STEP5_CONTACT", "STEP6_REVIEW_SUBMIT"]},
       shows_product_ui=True,
       vo=("اختر مناسبتك… حدّد ضيوفك وخدماتك… وأرسل. والباقي نرجع لك فيه بعرض واحد.", 3.3, 10.6),
       overlay_ar=[ov("اختر · حدّد · أرسل", 3.5, 10.8)], claims=["CLM_ONE_OFFER"])
v.card(11, 15)
v.save("تسجيل شاشة صادق بإيقاع هادئ يثبت السهولة: طلب واحد من أوله إلى إرساله.",
       [{"pdf_shot": "title", "change": "«بدون ولا مكالمة» is banned: the team does contact the customer. New title «بطلب واحد»"},
        {"pdf_shot": "0–3", "change": "«مكالمات: 0» counter → «طلب واحد»"},
        {"pdf_shot": "3–11", "change": "«تصفّح، اختر، احجز» → the six real form steps, then the team returns with one offer"},
        {"pdf_shot": "11–15", "change": "«جرّبها» + link → «قريبًا»"}],
       tweet_ar="عزيمتك الجاية تبدأ بطلب واحد: مناسبتك، ضيوفك، خدماتك. ونرجع لك بعرض واحد. Season Venue — قريبًا.")

# ------------------------------------------------------------------ X5
v = V("X5")
v.shot(0, 4, "hook · calls vs bookings", "X5-A", "CHAOS", characters=["C4"], location="L3",
       action="He stands in the courtyard of his well-kept istiraha answering his phone with a tired expression, the screen is not visible",
       camera={"shot_size": "MS", "lens_mm": 35, "movement": "static"}, lighting="late afternoon light",
       vo=("لأصحاب الاستراحات… كم مكالمة اليوم؟ وكم حجز؟", 0.3, 3.8), negative_extra=["smiling"], sfx="one soft vibration, no ringtone")
v.shot(4, 10, "new customers, no marketing cost", "replaces 4–10", characters=["C4"], location="L3",
       action="He walks calmly through his tidy istiraha straightening the majlis cushions, content",
       camera={"shot_size": "MS", "lens_mm": 35, "movement": "slow gimbal follow"}, lighting=WARM,
       vo=("سيزون فينيو… عملاء جدد بدون تكلفة تسويق، وبدون عمولة في فترة الإثبات.", 4.2, 9.8),
       subtitle_ar="Season Venue… عملاء جدد بدون تكلفة تسويق، وبدون عمولة في فترة الإثبات.",
       overlay_ar=[ov("عملاء جدد · بدون عمولة في فترة الإثبات", 4.5, 9.8),
                   ov("فترة الإثبات: ثلاثة أشهر أو عشرة حجوزات", 5.0, 9.8, "bottom", "body")],
       claims=["CLM_PARTNER_NEW_CLIENTS", "CLM_PARTNER_TRIAL"])
v.shot(10, 15, "your dates stay yours", "X5-B", characters=["C4"], location="L3",
       action="He sits relaxed on the majlis cushions pouring himself Arabic coffee from a dallah with a content expression",
       camera={"shot_size": "MS", "lens_mm": 50, "movement": "slow arc"}, lighting="warm golden light",
       overlay_ar=[ov("التواريخ بيدك: ما يثبت موعد إلا بتأكيدك", 10.4, 14.8)], claims=["CLM_PARTNER_DATES"])
v.card(15, 18, vo="سجّل مكانك… قريبًا.", headline="انضم شريكًا · الرياض أولًا", claims=["CLM_PARTNER_NO_EXCLUSIVITY"])
v.save("لملاك القاعات والاستراحات: من مكالمات لا تنتهي بحجز إلى عملاء جدد بلا تكلفة تسويق.",
       [{"pdf_shot": "4–10", "change": "«حجوزات مؤكدة ومدفوعة» + owner-calendar screen (feature not confirmed) → new customers with no marketing cost, no commission in the proof period (three months or ten bookings)"},
        {"pdf_shot": "10–15", "change": "added the approved line that dates are fixed only after the partner confirms"},
        {"pdf_shot": "15–18", "change": "«سجّل مكانك» kept without «مجانًا»; contact number → «قريبًا»"}],
       tweet_ar="لأصحاب القاعات والاستراحات: عملاء جدد بدون تكلفة تسويق، وبدون عمولة في فترة الإثبات (ثلاثة أشهر أو عشرة حجوزات). Season Venue — قريبًا.")

# ------------------------------------------------------------------ Y1
v = V("Y1")
split = {"layout": "horizontal split: top = before (cold grade), bottom = after (warm grade), olive-green divider", "plates": [
    {"clip": "Y1_A", "seconds": 9, "prompt_en": "A Saudi man in his early 30s with a short neat black beard, white thobe and red-and-white shemagh sitting on beige cushions in a Riyadh majlis, phone to his ear, glancing at his silver wristwatch impatiently, cool grey daylight, static camera, cinematic photorealistic (16:9, cropped to half-frame)"},
    {"clip": "Y1_B", "seconds": 6, "prompt_en": "The same man at an elegant istiraha at dusk greeting Saudi male guests in white thobes with warm handshakes and smiles, warm lantern light, slow gimbal push, cinematic photorealistic (16:9, cropped to half-frame)"}]}
v.shot(0, 3, "hook · same gathering, two ways", "0–3", "CHAOS", mode="graphics", composite=split,
       action="Split screen assembled in the edit: top he calls anxiously, bottom he calmly holds a phone with a blank green screen",
       vo=("نفس العزيمة… طريقتين.", 0.4, 2.6), overlay_ar=[ov("قبل / بعد", 0.3, 2.9, "center", "headline")])
v.shot(3, 9, "waiting vs requesting", "3–9", "CHAOS", mode="graphics", composite=split,
       action="Split screen: top he waits for a reply and checks his watch; bottom a phone with a blank green screen carries the real request form",
       shows_product_ui=True, screen_insert=insert(["STEP1_EVENT_TYPE", "STEP3_GUESTS_BUDGET_ATTENDANCE", "STEP6_REVIEW_SUBMIT"]))
v.shot(9, 14, "still calling vs hosting", "9–14", "EVENT", mode="graphics", composite=split,
       action="Split screen: top he is still on the phone; bottom he welcomes his guests at the istiraha",
       vo=("الفرق؟ طلب واحد… وبال مرتاح.", 9.4, 12.6), claims=["CLM_ONE_OFFER"])
v.card(14, 18)
v.save("شاشة مقسومة أفقيًا: الطريقة القديمة في الأعلى، وSeason Venue في الأسفل، بنفس اللحظة.",
       [{"pdf_shot": "3–9", "change": "«اختيار وحجز» screen → request-form recording"},
        {"pdf_shot": "9–14", "change": "«الفرق؟ دقايق [المدة الفعلية]» → «طلب واحد»: no booking-time claim"},
        {"pdf_shot": "14–18", "change": "«احجز الآن» → «قريبًا»"}],
       edit_notes={"loop": "the green card dissolves back into the split screen", "grade": "cold top, warm bottom, olive divider"})

# ------------------------------------------------------------------ Y2
v = V("Y2")
v.shot(0, 4, "hook · sunset time-lapse", "Y2-A", "EVENT", mode="text_to_video", location="L3",
       action="Cinematic time-lapse of the sun setting behind the palm trees, warm lanterns switching on one by one as the sky turns deep blue",
       camera={"shot_size": "WS", "lens_mm": 24, "movement": "locked-off"}, lighting="sunset into blue hour",
       overlay_ar=[ov("عشرون ثانية… ليلة كاملة", 0.4, 3.8, "top", "headline")])
v.shot(4, 7, "guests arrive", "Y2-B", "EVENT", characters=["C5"], location="L3",
       action="They arrive at the gate of the lantern-lit istiraha and are welcomed with handshakes",
       camera={"shot_size": "MS", "lens_mm": 35, "movement": "smooth gimbal"}, lighting="warm lantern light")
v.shot(7, 10, "dinner is served", "Y2-C", "EVENT", mode="text_to_video", location="L3",
       action="A large traditional platter of rice and lamb is placed on a floor spread surrounded by guests, steam rising",
       camera={"shot_size": "INSERT", "angle": "overhead", "lens_mm": 50, "movement": "overhead slide"}, lighting="warm lantern light, cinematic food photography")
v.shot(10, 16, "laughter and goodbye", "Y2-D", "EVENT", characters=["C1", "C5"], location="L3",
       action="He laughs with his guests on majlis cushions late at night, then walks them to the gate and waves goodbye",
       camera={"shot_size": "MS", "lens_mm": 35, "movement": "slow pull-back"}, lighting="warm lantern glow",
       vo=("كل شي كان مرتّب من قبل…", 11.6, 14.6))
v.card(16, 20, vo="ابدأ بطلب واحد.", headline="ليلتك… تبدأ بطلب واحد")
v.save("Time-lapse سينمائي لليلة المناسبة من الغروب حتى الوداع، بلا تعليق تقريبًا.",
       [{"pdf_shot": "0–4", "change": "«20 ثانية» written as «عشرون ثانية»"},
        {"pdf_shot": "10–16", "change": "PDF prompt is 4s for a 6s slot: one 6s generation"},
        {"pdf_shot": "16–20", "change": "«ابدأ حجزك» → «ابدأ بطلب واحد» + «قريبًا»"}],
       edit_notes={"loop": "the end card dissolves to the opening sunset"})

# ------------------------------------------------------------------ Y3
v = V("Y3")
v.d["title_ar"] = "«كيف تطلب مناسبتك؟ ست خطوات»"
v.d["title_pdf"] = "«كيف نوثّق المكان قبل ما يظهر لك؟»"
steps = [("STEP1_EVENT_TYPE", "نوع المناسبة"), ("STEP2_CITY_DATE", "المدينة والتاريخ التقريبي"),
         ("STEP3_GUESTS_BUDGET_ATTENDANCE", "الضيوف · الميزانية · نوع الحضور"), ("STEP4_SERVICES", "الخدمات"),
         ("STEP5_CONTACT", "الاسم والجوال"), ("STEP6_REVIEW_SUBMIT", "راجع وأرسل")]
v.shot(0, 3, "hook", "0–3", characters=["C1"], location="L1",
       action="He settles on the floor cushions and unlocks his phone with a blank green screen, relaxed",
       camera={"shot_size": "MCU", "lens_mm": 50, "movement": "slow push-in"}, lighting=WARM,
       vo=("كيف تطلب مناسبتك؟ ست خطوات.", 0.3, 2.8), overlay_ar=[ov("كيف تطلب مناسبتك؟", 0.3, 2.9, "top", "headline")], claims=["CLM_SIX_STEPS"])
seg = 11 / 6
v.shot(3, 14, "the six steps", "replaces 3–14", mode="screen_recording",
       action="Real screen recording of the request form, one step at a time, full frame",
       generation={"source_path": REC, "flow_steps": [s for s, _ in steps]}, shows_product_ui=True,
       vo=("نوع المناسبة. المدينة والتاريخ. الضيوف والميزانية. الخدمات. اسمك وجوالك. راجع… وأرسل.", 3.3, 13.6),
       overlay_ar=[ov(lbl, round(3 + i * seg + 0.1, 2), round(3 + (i + 1) * seg - 0.1, 2), "top", "headline") for i, (_, lbl) in enumerate(steps)],
       claims=["CLM_SIX_STEPS"])
v.shot(14, 17, "receipt, then the team", "replaces 14–17", mode="screen_recording",
       action="Real screen recording of the request-received confirmation",
       generation={"source_path": REC, "flow_steps": ["CONFIRMATION"]}, shows_product_ui=True,
       vo=("يوصلك تأكيد الاستلام… وفريقنا يتواصل معك.", 14.1, 16.9), overlay_ar=[ov("تأكيد استلام الطلب", 14.3, 16.9, "top", "headline")])
v.card(17, 20)
v.save("بدل «كيف نوثّق المكان»: كيف يطلب العميل مناسبته في ست خطوات، بتسجيل شاشة حقيقي.",
       [{"pdf_shot": "all", "change": "The PDF's verification behind-the-scenes cannot be made: no announced verification process (brand_facts). Replaced, as the owner's table requires, by «كيف يطلب العميل مناسبته؟ (6 خطوات)»"},
        {"pdf_shot": "3–14", "change": "live-action field visit → real request-form recording, six steps in 11s"},
        {"pdf_shot": "14–17", "change": "«يظهر لك موثّق» + badge → receipt confirmation, then the team gets in touch"}],
       production_note="No AI generation except the 3s hook. Needs the real recording; blocked until the demo is reachable.")

# ------------------------------------------------------------------ Y4
v = V("Y4")
v.shot(0, 3, "hook · the team arrives", "Y4-A", "EVENT", mode="text_to_video", location="L3",
       action="A hospitality team of Saudi men in neat matching uniforms carries brass trays, dallah coffee pots and covered dishes through the gate, purposeful walk",
       camera={"shot_size": "MS", "lens_mm": 35, "movement": "gimbal follow"}, lighting="early evening warm light",
       vo=("الضيافة وصلت…", 0.6, 2.4), sfx="footsteps and trays, no bells")
v.shot(3, 7, "set in minutes of screen time", "Y4-B", "EVENT", mode="text_to_video", location="L3",
       action="Hands quickly and precisely arrange finjan cups, dates and sweets on a low majlis table",
       camera={"shot_size": "INSERT", "angle": "overhead", "lens_mm": 50, "movement": "smooth slide"}, lighting="warm lantern light, cinematic food photography",
       vo=("قبل الضيوف.", 3.6, 5.2))
v.shot(7, 12, "guests find it ready", "Y4-C", "EVENT", characters=["C5", "C1"], location="L3",
       action="The guests enter to find the table fully set; he nods with quiet satisfaction",
       camera={"shot_size": "MS", "lens_mm": 35, "movement": "slow push-in"}, lighting="warm light",
       vo=("لأنها مع القاعة… في نفس العرض.", 7.4, 10.6), overlay_ar=[ov("قاعة وضيافة في عرض واحد", 7.5, 11.8)], claims=["CLM_ONE_OFFER"])
v.card(12, 16)
v.save("سباق صغير يفوز فيه الالتزام بالموعد: الضيافة تصل قبل الضيوف لأنها ضمن العرض نفسه.",
       [{"pdf_shot": "7–12", "change": "«محجوزة مع المكان… من نفس الحجز» → «مع القاعة… في نفس العرض»"},
        {"pdf_shot": "12–16", "change": "«احجز ضيافتك» → tagline + «قريبًا»"}],
       caution="Use only if a hospitality service is really offered at launch (PDF). The wall-clock «7:00» hook is dropped: no punctuality figure is claimed.")

# ------------------------------------------------------------------ Y5
v = V("Y5")
DISC = "الدفع المرن اختياري عبر جهات تمويل مرخصة من ساما. الموافقة والشروط تعود لجهة التمويل. Season Venue لا تقدّم تمويلاً."
v.shot(0, 3, "hook · a big total", "Y5-A", "CHAOS", characters=["C1"], location="L1",
       action="He looks at a printed sheet with blurred, unreadable numbers and exhales thoughtfully",
       camera={"shot_size": "MCU", "lens_mm": 50, "movement": "static"}, lighting="cool soft light",
       vo=("مناسبتك كبيرة…", 0.6, 2.4), negative_extra=["readable numbers", "currency symbols"])
v.shot(3, 10, "flexible payment, optional", "replaces 3–10", characters=["C1"], location="L1",
       action="He reads the printed offer calmly with a pen in hand, then nods, the document text is soft and unreadable",
       camera={"shot_size": "MCU", "lens_mm": 50, "movement": "slow push-in"}, lighting="light warming gradually",
       vo=("تقدر تقدّم على دفع مرن، اختياري… عبر جهات تمويل مرخصة من ساما.", 3.3, 9.6),
       overlay_ar=[ov("دفع مرن · اختياري", 3.5, 9.8), ov(DISC, 3.5, 12.0, "bottom", "body", kind="disclosure")],
       claims=["CLM_FLEX_PAY"], negative_extra=["bank logos", "payment-provider logos", "readable numbers", "card terminal"])
v.shot(10, 12, "relief", "Y5-B", characters=["C1"], location="L1",
       action="He smiles with relief and sets his phone down on a wooden table, the screen is not visible",
       camera={"shot_size": "MCU", "lens_mm": 50, "movement": "slight push-in"}, lighting="warm golden light")
v.card(12, 15, extra=[ov("Season Venue لا تقدّم تمويلاً. الموافقة والشروط تعود لجهة التمويل.", 12.3, 15, "top", "body", kind="disclosure")],
       claims=["CLM_ONE_OFFER", "CLM_FLEX_PAY"])
v.save("الدفعة الأولى كبيرة؟ خيار دفع مرن اختياري عبر جهات تمويل مرخصة من ساما، مع الإفصاح الإلزامي.",
       [{"pdf_shot": "version A", "change": "Tabby/Tamara by name → not allowed until the owner supplies them in writing"},
        {"pdf_shot": "version B", "change": "«ادفع بأمان داخل المنصة… محفوظ لك حتى تتم مناسبتك» banned → the approved flexible-payment wording"},
        {"pdf_shot": "3–10", "change": "pay-step screen removed; mandatory disclosure on screen from 3.5s to the end"},
        {"pdf_shot": "12–15", "change": "«احجز بأمان» → tagline + «قريبًا» + disclosure"}],
       caution="Financing advert: needs owner and legal sign-off on the exact wording before any publication.")
print("scripts written")
