"""Alert guards: length, script, hallucinated numbers, 112, level words, URLs, languages."""

from __future__ import annotations

from collections.abc import Callable

import pytest

from jalrakshak.agents.facts import build_facts
from jalrakshak.agents.guards import (
    is_gsm7,
    level_words_ok,
    run_guards,
    script_share,
    unverified_numbers,
)
from jalrakshak.agents.templates import render_all
from jalrakshak.data.cities import all_cities
from jalrakshak.data.facilities import city_facilities
from jalrakshak.models import AlertVersion, CityRisk, GuardResult


def _versions(risk: CityRisk) -> tuple[list[AlertVersion], set[str], str]:
    f = build_facts(risk, city_facilities(risk.city.id)[0])
    vs = [AlertVersion(lang=lang, **v) for lang, v in render_all(f).items()]  # type: ignore[arg-type]
    return vs, f.allowed_numbers(), f.level


def _by_name(results: list[GuardResult]) -> dict[str, GuardResult]:
    return {r.name: r for r in results}


@pytest.mark.parametrize("city_id", list(all_cities()))
@pytest.mark.parametrize(("rain", "ratio"), [(7.0, 1.05), (3.0, 0.85), (9.0, 0.2), (2.0, 0.0)])
def test_vetted_templates_pass_all_guards(
    make_risk: Callable[..., CityRisk], city_id: str, rain: float, ratio: float
) -> None:
    vs, allowed, level = _versions(make_risk(city_id, rain, ratio))
    results = run_guards(vs, level, allowed)  # type: ignore[arg-type]
    assert all(r.passed for r in results), [r for r in results if not r.passed]
    for v in vs:
        assert len(v.sms) <= (160 if v.lang == "en" else 134)


def _mutate(make_risk: Callable[..., CityRisk], lang: str, sms: str) -> dict[str, GuardResult]:
    vs, allowed, level = _versions(make_risk())
    vs = [v.model_copy(update={"sms": sms}) if v.lang == lang else v for v in vs]
    return _by_name(run_guards(vs, level, allowed))  # type: ignore[arg-type]


def test_sms_too_long(make_risk: Callable[..., CityRisk]) -> None:
    r = _mutate(make_risk, "en", "RED ALERT Guwahati. Call 112. " + "x" * 150)
    assert not r["sms_length"].passed and "160" in r["sms_length"].detail


def test_unicode_sms_limit(make_risk: Callable[..., CityRisk]) -> None:
    r = _mutate(make_risk, "hi", "लाल चेतावनी 112 " + "बाढ़" * 40)
    assert not r["sms_length"].passed


def test_non_gsm7_english(make_risk: Callable[..., CityRisk]) -> None:
    r = _mutate(make_risk, "en", "RED ALERT Guwahati – move now. 112 🚨")
    assert not r["sms_length"].passed and "GSM-7" in r["sms_length"].detail
    assert is_gsm7("RED ALERT 112: move now.") and not is_gsm7("–")


def test_wrong_script(make_risk: Callable[..., CityRisk]) -> None:
    r = _mutate(
        make_risk, "hi", "Flood RED ALERT (लाल चेतावनी) Guwahati: move to shelters now. Call 112"
    )
    assert not r["script"].passed
    r2 = _mutate(make_risk, "ta", "சிவப்பு எச்சரிக்கை বন্যা 112")
    assert not r2["script"].passed and "bengali" in r2["script"].detail
    share, others = script_share("नमस्ते Anil", "devanagari")
    assert 0.5 < share < 1 and not others
    assert script_share("123", "latin") == (0.0, set())


def test_hallucinated_number(make_risk: Callable[..., CityRisk]) -> None:
    r = _mutate(
        make_risk, "en", "RED ALERT Guwahati: 437 mm rain and 9999 people affected. Call 112"
    )
    assert not r["numbers_verified"].passed
    assert "437" in r["numbers_verified"].detail
    assert unverified_numbers("call 112 or 1,078", {"112", "1078"}) == []
    assert unverified_numbers("at 18.00", {"18", "00"}) == []


def test_missing_112(make_risk: Callable[..., CityRisk]) -> None:
    r = _mutate(make_risk, "bn", "বন্যা লাল সতর্কতা: গুয়াহাটি। এখনই উঁচু জায়গায় যান।")
    assert not r["contains_112"].passed
    r2 = _mutate(make_risk, "en", "RED ALERT Guwahati: call 1120 now")
    assert not r2["contains_112"].passed


def test_level_consistency(make_risk: Callable[..., CityRisk]) -> None:
    r = _mutate(make_risk, "en", "ORANGE ALERT Guwahati: be ready. Call 112")
    assert not r["level_consistent"].passed
    r2 = _mutate(make_risk, "en", "RED ALERT Guwahati, not yellow. Call 112")
    assert not r2["level_consistent"].passed
    assert level_words_ok("Zoo Road RED ALERT", "en", "red") == (True, "ok")
    assert not level_words_ok("नारंगी चेतावनी", "hi", "red")[0]


def test_no_urls(make_risk: Callable[..., CityRisk]) -> None:
    r = _mutate(make_risk, "en", "RED ALERT Guwahati: see bit.ly/flood. Call 112")
    assert not r["no_urls"].passed
    r2 = _mutate(make_risk, "en", "RED ALERT Guwahati: https://example.org Call 112")
    assert not r2["no_urls"].passed


def test_missing_language_and_empty(make_risk: Callable[..., CityRisk]) -> None:
    vs, allowed, level = _versions(make_risk())
    r = _by_name(run_guards(vs[:4], level, allowed))  # type: ignore[arg-type]
    assert not r["all_languages"].passed and "bn" in r["all_languages"].detail
    r2 = _mutate(make_risk, "mr", " ")
    assert not r2["all_languages"].passed
