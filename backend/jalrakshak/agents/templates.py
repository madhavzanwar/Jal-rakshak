"""VETTED public-alert templates for en/hi/mr/ta/bn with slot filling.

Design decision: a 3B local model is not trusted to translate safety-critical text, so the
Hindi, Marathi, Tamil and Bengali versions are ALWAYS rendered from these hand-written
templates (proper Devanagari / Tamil / Bengali script). Only the slots vary: city, level,
wards (kept in Latin script as proper nouns), river, peak time, nearest shelter and 112.
The English version is a fallback for the LLM draft, which must pass the same guards.

SMS length budgets follow the contract: English <= 160 GSM-7 characters; Unicode languages
<= 134 characters (2 x 67-char UCS-2 segments). Wards are dropped one by one until a version
fits.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Literal

from jalrakshak.agents.facts import Facts
from jalrakshak.models import Lang, RiskLevel

Hazard = Literal["river_danger", "river_warning", "rain"]

SMS_LIMIT: dict[Lang, int] = {"en": 160, "hi": 134, "mr": 134, "ta": 134, "bn": 134}
WHATSAPP_LIMIT = 1000

LEVEL_WORDS: dict[Lang, dict[RiskLevel, str]] = {
    "en": {
        "red": "RED ALERT",
        "orange": "ORANGE ALERT",
        "yellow": "YELLOW ALERT",
        "green": "GREEN",
    },
    "hi": {
        "red": "लाल चेतावनी",
        "orange": "नारंगी चेतावनी",
        "yellow": "पीली चेतावनी",
        "green": "सामान्य स्थिति",
    },
    "mr": {
        "red": "लाल इशारा",
        "orange": "नारंगी इशारा",
        "yellow": "पिवळा इशारा",
        "green": "सामान्य स्थिती",
    },
    "ta": {
        "red": "சிவப்பு எச்சரிக்கை",
        "orange": "ஆரஞ்சு எச்சரிக்கை",
        "yellow": "மஞ்சள் எச்சரிக்கை",
        "green": "இயல்பு நிலை",
    },
    "bn": {"red": "লাল সতর্কতা", "orange": "কমলা সতর্কতা", "yellow": "হলুদ সতর্কতা", "green": "স্বাভাবিক অবস্থা"},
}

#: Colour stems used by the level-consistency guard (no other level's stem may appear).
LEVEL_STEMS: dict[Lang, dict[RiskLevel, str]] = {
    "en": {"red": "red", "orange": "orange", "yellow": "yellow", "green": "green"},
    "hi": {"red": "लाल", "orange": "नारंगी", "yellow": "पीली", "green": "सामान्य"},
    "mr": {"red": "लाल", "orange": "नारंगी", "yellow": "पिवळा", "green": "सामान्य"},
    "ta": {"red": "சிவப்பு", "orange": "ஆரஞ்சு", "yellow": "மஞ்சள்", "green": "இயல்பு"},
    "bn": {"red": "লাল", "orange": "কমলা", "yellow": "হলুদ", "green": "স্বাভাবিক"},
}

CITY_NAMES: dict[str, dict[Lang, str]] = {
    "mumbai": {"hi": "मुंबई", "mr": "मुंबई", "ta": "மும்பை", "bn": "মুম্বই"},
    "chennai": {"hi": "चेन्नई", "mr": "चेन्नई", "ta": "சென்னை", "bn": "চেন্নাই"},
    "guwahati": {"hi": "गुवाहाटी", "mr": "गुवाहाटी", "ta": "குவாஹாட்டி", "bn": "গুয়াহাটি"},
    "patna": {"hi": "पटना", "mr": "पाटणा", "ta": "பாட்னா", "bn": "পাটনা"},
    "kochi": {"hi": "कोच्चि", "mr": "कोची", "ta": "கொச்சி", "bn": "কোচি"},
    "srinagar": {"hi": "श्रीनगर", "mr": "श्रीनगर", "ta": "ஸ்ரீநகர்", "bn": "শ্রীনগর"},
    "kolkata": {"hi": "कोलकाता", "mr": "कोलकाता", "ta": "கொல்கத்தா", "bn": "কলকাতা"},
    "bhubaneswar": {"hi": "भुवनेश्वर", "mr": "भुवनेश्वर", "ta": "புவனேஸ்வர்", "bn": "ভুবনেশ্বর"},
    "surat": {"hi": "सूरत", "mr": "सुरत", "ta": "சூரத்", "bn": "সুরাট"},
    "hyderabad": {"hi": "हैदराबाद", "mr": "हैदराबाद", "ta": "ஹைதராபாத்", "bn": "হায়দ্রাবাদ"},
    "pune": {"hi": "पुणे", "mr": "पुणे", "ta": "புனே", "bn": "পুনে"},
    "dibrugarh": {"hi": "डिब्रूगढ़", "mr": "दिब्रुगड", "ta": "திப்ருகர்", "bn": "ডিব্রুগড়"},
}

RIVER_NAMES: dict[str, dict[Lang, str]] = {
    "Brahmaputra": {"hi": "ब्रह्मपुत्र", "mr": "ब्रह्मपुत्रा", "ta": "பிரம்மபுத்திரா", "bn": "ব্রহ্মপুত্র"},
    "Ganga": {"hi": "गंगा", "mr": "गंगा", "ta": "கங்கை", "bn": "গঙ্গা"},
    "Periyar": {"hi": "पेरियार", "mr": "पेरियार", "ta": "பெரியாறு", "bn": "পেরিয়ার"},
    "Jhelum": {"hi": "झेलम", "mr": "झेलम", "ta": "ஜீலம்", "bn": "ঝিলম"},
    "Hooghly": {"hi": "हुगली", "mr": "हुगळी", "ta": "ஹூக்ளி", "bn": "হুগলি"},
    "Mahanadi": {"hi": "महानदी", "mr": "महानदी", "ta": "மகாநதி", "bn": "মহানদী"},
    "Tapi": {"hi": "तापी", "mr": "तापी", "ta": "தபதி", "bn": "তাপী"},
    "Musi": {"hi": "मूसी", "mr": "मुसी", "ta": "மூசி", "bn": "মুসি"},
    "Mula-Mutha": {"hi": "मुला-मुठा", "mr": "मुळा-मुठा", "ta": "முலா-முத்தா", "bn": "মুলা-মুঠা"},
    "Adyar": {"hi": "अड्यार", "mr": "अड्यार", "ta": "அடையாறு", "bn": "আদিয়ার"},
    "Mithi": {"hi": "मीठी", "mr": "मिठी", "ta": "மிதி", "bn": "মিঠি"},
}

HAZARD: dict[Lang, dict[Hazard, str]] = {
    "en": {
        "river_danger": "{river} above danger level",
        "river_warning": "{river} rising above warning level",
        "rain": "{rain_cat} rain expected",
    },
    "hi": {
        "river_danger": "{river} खतरे के निशान से ऊपर",
        "river_warning": "{river} का जलस्तर बढ़ रहा है",
        "rain": "भारी बारिश की आशंका",
    },
    "mr": {
        "river_danger": "{river} नदी धोक्याच्या पातळीवर",
        "river_warning": "{river} नदीची पातळी वाढत आहे",
        "rain": "मुसळधार पावसाची शक्यता",
    },
    "ta": {
        "river_danger": "{river} அபாய அளவை தாண்டியது",
        "river_warning": "{river} ஆற்றில் நீர்மட்டம் உயர்கிறது",
        "rain": "கனமழை எதிர்பார்க்கப்படுகிறது",
    },
    "bn": {
        "river_danger": "{river} বিপদসীমার উপরে",
        "river_warning": "{river} নদীর জলস্তর বাড়ছে",
        "rain": "ভারী বৃষ্টির সম্ভাবনা",
    },
}

ACTION: dict[Lang, dict[RiskLevel, str]] = {
    "en": {
        "red": "Move to higher ground or a shelter now",
        "orange": "Be ready to evacuate",
        "yellow": "Stay alert and follow official updates",
        "green": "No flood threat expected",
    },
    "hi": {
        "red": "तुरंत ऊँचे स्थान या शिविर में जाएँ",
        "orange": "सुरक्षित स्थान पर जाने के लिए तैयार रहें",
        "yellow": "सतर्क रहें, आधिकारिक सूचना पर ध्यान दें",
        "green": "बाढ़ का कोई खतरा नहीं",
    },
    "mr": {
        "red": "त्वरित उंच ठिकाणी किंवा निवारा केंद्रात जा",
        "orange": "स्थलांतरासाठी तयार राहा",
        "yellow": "सतर्क राहा, अधिकृत सूचनांकडे लक्ष द्या",
        "green": "पुराचा धोका नाही",
    },
    "ta": {
        "red": "உடனே மேடான இடத்துக்கு செல்லவும்",
        "orange": "வெளியேற தயாராக இருக்கவும்",
        "yellow": "விழிப்புடன் இருக்கவும்",
        "green": "வெள்ள அபாயம் இல்லை",
    },
    "bn": {
        "red": "এখনই উঁচু জায়গা বা ত্রাণ শিবিরে যান",
        "orange": "সরে যাওয়ার জন্য প্রস্তুত থাকুন",
        "yellow": "সতর্ক থাকুন, সরকারি বার্তা অনুসরণ করুন",
        "green": "বন্যার আশঙ্কা নেই",
    },
}

# SMS skeletons: {flood} {level}: {city} ({wards}). {hazard}. {action}. {emergency} 112
SMS: dict[Lang, str] = {
    "en": "JalRakshak {level} {city}{wards_paren}: {hazard}. {action}. Emergency: 112",
    "hi": "बाढ़ {level}: {city}{wards_paren}। {hazard}। {action}। आपात नंबर 112",
    "mr": "पूर {level}: {city}{wards_paren}. {hazard}. {action}. आपत्कालीन क्रमांक 112",
    "ta": "வெள்ள {level}: {city}{wards_paren}. {hazard}. {action}. அவசர உதவி 112",
    "bn": "বন্যা {level}: {city}{wards_paren}। {hazard}। {action}। জরুরি নম্বর 112",
}

WA_LINES: dict[Lang, dict[str, str]] = {
    "en": {
        "title": "*JalRakshak - Flood {level} - {city}*",
        "wards": "Wards: {wards}",
        "time": "Expected peak: {hhmm} IST",
        "shelter": "Nearest shelter: {shelter}",
        "contacts": "Emergency 112 | NDMA helpline 1078 | State EOC 1070",
        "official": "Rely only on official IMD/CWC and district updates.",
    },
    "hi": {
        "title": "*जलरक्षक - बाढ़ {level} - {city}*",
        "wards": "प्रभावित वार्ड: {wards}",
        "time": "अनुमानित चरम समय: {hhmm} (IST)",
        "shelter": "निकटतम आश्रय: {shelter}",
        "contacts": "आपातकाल: 112 | राष्ट्रीय आपदा हेल्पलाइन: 1078 | राज्य आपात केंद्र: 1070",
        "official": "केवल आधिकारिक सूचना पर भरोसा करें।",
    },
    "mr": {
        "title": "*जलरक्षक - पूर {level} - {city}*",
        "wards": "बाधित प्रभाग: {wards}",
        "time": "अपेक्षित उच्चांक वेळ: {hhmm} (IST)",
        "shelter": "जवळचे निवारा केंद्र: {shelter}",
        "contacts": "आपत्कालीन: 112 | राष्ट्रीय आपत्ती हेल्पलाइन: 1078 | राज्य आपत्कालीन केंद्र: 1070",
        "official": "फक्त अधिकृत सूचनांवर विश्वास ठेवा.",
    },
    "ta": {
        "title": "*ஜலரக்ஷக் - வெள்ள {level} - {city}*",
        "wards": "பாதிக்கப்பட்ட வார்டுகள்: {wards}",
        "time": "எதிர்பார்க்கப்படும் உச்ச நேரம்: {hhmm} (IST)",
        "shelter": "அருகிலுள்ள நிவாரண முகாம்: {shelter}",
        "contacts": "அவசரம்: 112 | தேசிய பேரிடர் உதவி எண்: 1078 | மாநில அவசர மையம்: 1070",
        "official": "அதிகாரப்பூர்வ அறிவிப்புகளை மட்டும் நம்பவும்.",
    },
    "bn": {
        "title": "*জলরক্ষক - বন্যা {level} - {city}*",
        "wards": "ক্ষতিগ্রস্ত ওয়ার্ড: {wards}",
        "time": "সম্ভাব্য চূড়ান্ত সময়: {hhmm} (IST)",
        "shelter": "নিকটতম আশ্রয়: {shelter}",
        "contacts": "জরুরি: 112 | জাতীয় দুর্যোগ হেল্পলাইন: 1078 | রাজ্য জরুরি কেন্দ্র: 1070",
        "official": "শুধুমাত্র সরকারি বার্তায় বিশ্বাস করুন।",
    },
}


def hazard_kind(f: Facts) -> Hazard:
    if f.has_gauge and f.gauge_status in ("danger", "extreme"):
        return "river_danger"
    if f.has_gauge and f.gauge_status == "warning":
        return "river_warning"
    return "rain"


def _city(f: Facts, lang: Lang) -> str:
    return f.city if lang == "en" else CITY_NAMES.get(f.city_id, {}).get(lang, f.city)


def _river(f: Facts, lang: Lang) -> str:
    return f.river if lang == "en" else RIVER_NAMES.get(f.river, {}).get(lang, f.river)


def _hazard(f: Facts, lang: Lang) -> str:
    rain_cat = f.rain_category.capitalize() if f.rain_category != "no rain" else "Heavy"
    return HAZARD[lang][hazard_kind(f)].format(river=_river(f, lang), rain_cat=rain_cat)


def _fit(render: Callable[[list[str]], str], wards: list[str], limit: int) -> str:
    """Render with as many wards as fit within ``limit`` characters."""
    for n in range(min(len(wards), 3), -1, -1):
        text = render(wards[:n])
        if len(text) <= limit:
            return text
    return render([])


def render_sms(f: Facts, lang: Lang) -> str:
    def render(wards: list[str]) -> str:
        return SMS[lang].format(
            level=LEVEL_WORDS[lang][f.level],
            city=_city(f, lang),
            wards_paren=f" ({', '.join(wards)})" if wards else "",
            hazard=_hazard(f, lang),
            action=ACTION[lang][f.level],
        )

    return _fit(render, f.ward_names, SMS_LIMIT[lang])


def render_whatsapp(f: Facts, lang: Lang) -> str:
    L = WA_LINES[lang]
    lines = [
        L["title"].format(level=LEVEL_WORDS[lang][f.level], city=_city(f, lang)),
        L["wards"].format(wards=", ".join(f.ward_names)),
        f"- {_hazard(f, lang)}",
        f"- {L['time'].format(hhmm=f.peak_hhmm)}",
        ACTION[lang][f.level] + ("." if lang in ("en", "mr", "ta") else "।"),
    ]
    if f.shelter:
        lines.append(L["shelter"].format(shelter=f.shelter))
    lines += [L["contacts"], L["official"]]
    return "\n".join(lines)[:WHATSAPP_LIMIT]


def render(f: Facts, lang: Lang) -> dict[str, str]:
    return {"sms": render_sms(f, lang), "whatsapp": render_whatsapp(f, lang)}


def render_all(f: Facts) -> dict[str, dict[str, str]]:
    return {lang: render(f, lang) for lang in ("en", "hi", "mr", "ta", "bn")}
