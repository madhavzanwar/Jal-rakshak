"""Deterministic safety guards for public alerts.

Guards (one GuardResult each, aggregated over all languages):

* ``all_languages``  - en, hi, mr, ta, bn present with non-empty SMS and WhatsApp text
* ``sms_length``     - en <= 160 GSM-7 chars; hi/mr/ta/bn <= 134 chars (2 Unicode segments)
* ``script``         - >= 60 % of letters in the language's script (Latin, Devanagari, Tamil,
                       Bengali) and no letters from another Indic script
* ``numbers_verified`` - every number in the text exists in the verified fact set
* ``contains_112``   - every SMS and WhatsApp text contains the national emergency number 112
* ``level_consistent`` - the level word for the alert's level appears; no other level word
* ``no_urls``        - no links (phishing-safe; official channels are named, not linked)
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Iterable

from jalrakshak.agents.templates import LEVEL_STEMS, SMS_LIMIT, WHATSAPP_LIMIT
from jalrakshak.models import LANGS, AlertVersion, GuardResult, Lang, RiskLevel

GSM7 = set(
    "@£$¥èéùìòÇ\nØø\rÅåΔ_ΦΓΛΩΠΨΣΘΞÆæßÉ !\"#¤%&'()*+,-./0123456789:;<=>?¡ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "ÄÖÑÜ§¿abcdefghijklmnopqrstuvwxyzäöñüà^{}\\[~]|€"
)
SCRIPT_RANGES: dict[str, tuple[int, int]] = {
    "latin": (0x0041, 0x024F),
    "devanagari": (0x0900, 0x097F),
    "bengali": (0x0980, 0x09FF),
    "tamil": (0x0B80, 0x0BFF),
}
LANG_SCRIPT: dict[Lang, str] = {
    "en": "latin",
    "hi": "devanagari",
    "mr": "devanagari",
    "ta": "tamil",
    "bn": "bengali",
}
URL_RE = re.compile(r"(https?://|www\.|\b[\w-]+\.(com|in|org|net|ly|io|gov)\b)", re.I)
NUM_RE = re.compile(r"\d+(?:[.,]\d+)*")
MIN_SCRIPT_SHARE = 0.6


def _script_of(ch: str) -> str | None:
    cp = ord(ch)
    for name, (lo, hi) in SCRIPT_RANGES.items():
        if lo <= cp <= hi:
            return name
    return None


def script_share(text: str, script: str) -> tuple[float, set[str]]:
    """(share of letters in ``script``, set of other Indic scripts present)."""
    letters = [c for c in text if unicodedata.category(c)[0] in ("L", "M")]
    if not letters:
        return 0.0, set()
    scripts = [_script_of(c) for c in letters]
    share = sum(1 for s in scripts if s == script) / len(letters)
    others = {s for s in scripts if s and s not in (script, "latin")}
    return share, others


def numbers_in(text: str) -> list[str]:
    return NUM_RE.findall(text)


def unverified_numbers(text: str, allowed: set[str]) -> list[str]:
    """Numbers in ``text`` not present in ``allowed`` (thousand separators tolerated)."""
    bad = []
    for n in numbers_in(text):
        if n in allowed or n.replace(",", "") in allowed:
            continue
        parts = re.split(r"[.,]", n)
        if all(p in allowed for p in parts):  # e.g. a time like 18.00
            continue
        bad.append(n)
    return bad


def is_gsm7(text: str) -> bool:
    return all(c in GSM7 for c in text)


def level_words_ok(text: str, lang: Lang, level: RiskLevel) -> tuple[bool, str]:
    stems = LEVEL_STEMS[lang]
    hay = text.lower() if lang == "en" else text

    def has(stem: str) -> bool:
        if lang == "en":
            return re.search(rf"\b{stem}\b", hay) is not None
        return stem in hay

    if not has(stems[level]):
        return False, f"missing level word '{stems[level]}'"
    wrong = [s for lvl, s in stems.items() if lvl != level and has(s)]
    if wrong:
        return False, f"conflicting level words {wrong}"
    return True, "ok"


# ---------------------------------------------------------------- per-text checks


def check_version(v: AlertVersion, level: RiskLevel, allowed: set[str]) -> dict[str, str]:
    """Return {guard_name: failure_detail} for one language version (empty dict = all pass)."""
    fails: dict[str, str] = {}
    lang: Lang = v.lang
    if not v.sms.strip() or not v.whatsapp.strip():
        fails["all_languages"] = f"{lang}: empty text"
    limit = SMS_LIMIT[lang]
    if len(v.sms) > limit:
        fails["sms_length"] = f"{lang}: SMS {len(v.sms)} > {limit} chars"
    elif lang == "en" and not is_gsm7(v.sms):
        bad = sorted({c for c in v.sms if c not in GSM7})
        fails["sms_length"] = f"en: non GSM-7 characters {bad} (would force Unicode)"
    if len(v.whatsapp) > WHATSAPP_LIMIT:
        fails["sms_length"] = f"{lang}: WhatsApp {len(v.whatsapp)} > {WHATSAPP_LIMIT} chars"
    for field, text in (("sms", v.sms), ("whatsapp", v.whatsapp)):
        share, others = script_share(text, LANG_SCRIPT[lang])
        if share < MIN_SCRIPT_SHARE or others:
            fails["script"] = f"{lang} {field}: {share:.0%} {LANG_SCRIPT[lang]} letters" + (
                f", foreign scripts {sorted(others)}" if others else ""
            )
        bad = unverified_numbers(text, allowed)
        if bad:
            fails["numbers_verified"] = f"{lang} {field}: unverified numbers {bad}"
        if "112" not in numbers_in(text):
            fails["contains_112"] = f"{lang} {field}: missing 112"
        ok, detail = level_words_ok(text, lang, level)
        if not ok:
            fails["level_consistent"] = f"{lang} {field}: {detail}"
        if URL_RE.search(text):
            fails["no_urls"] = f"{lang} {field}: contains a link"
    return fails


GUARD_NAMES = (
    "all_languages",
    "sms_length",
    "script",
    "numbers_verified",
    "contains_112",
    "level_consistent",
    "no_urls",
)


def run_guards(
    versions: Iterable[AlertVersion], level: RiskLevel, allowed: set[str]
) -> list[GuardResult]:
    """Run every guard over all versions; one aggregated GuardResult per guard."""
    vs = list(versions)
    failures: dict[str, list[str]] = {g: [] for g in GUARD_NAMES}
    langs = [v.lang for v in vs]
    missing = [lang for lang in LANGS if lang not in langs]
    if missing:
        failures["all_languages"].append(f"missing languages {missing}")
    for v in vs:
        for name, detail in check_version(v, level, allowed).items():
            failures[name].append(detail)
    ok_detail = {
        "all_languages": "en, hi, mr, ta, bn present and non-empty",
        "sms_length": "SMS within 160 GSM-7 (en) / 134 Unicode chars",
        "script": "each version written in its own script",
        "numbers_verified": "every number matches the verified fact set",
        "contains_112": "112 present in every message",
        "level_consistent": f"level word matches '{level}' everywhere",
        "no_urls": "no links",
    }
    return [
        GuardResult(
            name=g,
            passed=not failures[g],
            detail="; ".join(failures[g]) if failures[g] else ok_detail[g],
        )
        for g in GUARD_NAMES
    ]


def all_passed(results: Iterable[GuardResult]) -> bool:
    return all(r.passed for r in results)
