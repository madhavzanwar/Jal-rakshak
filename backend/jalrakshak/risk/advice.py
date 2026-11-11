"""Deterministic, NDMA-style public guidance per risk level (pure)."""

from __future__ import annotations

from jalrakshak.models import Advice, RiskLevel

_ADVICE: dict[RiskLevel, Advice] = {
    "green": Advice(
        now=[
            "No flood threat expected in the next 72 hours.",
            "Follow IMD and local authority forecasts for updates.",
        ],
        prepare=[
            "Keep an emergency kit ready: drinking water, dry food, torch, medicines, documents in a waterproof bag.",
            "Know the nearest shelter and a route to higher ground.",
            "Save emergency numbers: 112, 1078, 1070.",
        ],
        avoid=["Do not dump waste in drains and nullahs; it blocks run-off during heavy rain."],
    ),
    "yellow": Advice(
        now=[
            "Be aware: heavy rain or rising river levels are possible.",
            "Check official IMD/CWC and district updates every few hours.",
        ],
        prepare=[
            "Charge phones and power banks; keep the emergency kit at hand.",
            "Move valuables, documents and medicines to a higher shelf.",
            "Plan how you would reach the nearest shelter; check on elderly neighbours.",
        ],
        avoid=[
            "Avoid unnecessary travel through low-lying roads and underpasses.",
            "Do not spread unverified messages; rely on official sources.",
        ],
    ),
    "orange": Advice(
        now=[
            "Be prepared to evacuate at short notice if officials advise.",
            "Move people with disabilities, the elderly, children and livestock to safer places early.",
            "Switch off electricity at the main if water starts entering your home.",
        ],
        prepare=[
            "Pack the emergency kit, drinking water for 3 days and essential medicines.",
            "Note the nearest shelter and route shown here; keep 112 handy.",
            "Store drinking water in clean covered containers.",
        ],
        avoid=[
            "Do not walk or drive through flood water: 15 cm of moving water can knock you down.",
            "Stay away from river banks, drains, electric poles and fallen wires.",
        ],
    ),
    "red": Advice(
        now=[
            "Act now: move to the nearest shelter or higher ground if you are in a low-lying area.",
            "Follow instructions from district authorities, police, SDRF and NDRF.",
            "Call 112 if you are trapped or need rescue.",
        ],
        prepare=[
            "Take only essentials: documents, medicines, water, phone and charger.",
            "Switch off electricity and gas before leaving; lock your home.",
            "Inform relatives of where you are going.",
        ],
        avoid=[
            "Never enter flood water on foot or by vehicle; turn around.",
            "Do not touch electric poles or wires; avoid bridges over swollen rivers.",
            "Do not return home until officials declare it safe.",
        ],
    ),
}


def advice_for(level: RiskLevel) -> Advice:
    """Return a copy of the guidance for ``level``."""
    return _ADVICE[level].model_copy(deep=True)
