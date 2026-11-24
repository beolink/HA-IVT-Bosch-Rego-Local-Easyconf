"""Option values in Swedish.

EMS-ESP's options are English words ("hot water", "outside basepoint") unless
its locale was changed. A select shows them in the installation's language and
writes the source's own word back; a word with no translation here is shown as
the source has it.
"""

from __future__ import annotations

SV: dict[str, str] = {
    "off": "Av",
    "on": "På",
    "auto": "Auto",
    "manual": "Manuell",
    "heating": "Värme",
    "cooling": "Kyla",
    "hot water": "Varmvatten",
    "pool": "Pool",
    "pool heating": "Poolvärme",
    "defrost": "Avfrostning",
    "compressor alarm": "Kompressorlarm",
    "eco": "Eko",
    "eco+": "Eko+",
    "comfort": "Komfort",
    "high comfort": "Hög komfort",
    "intelligent": "Intelligent",
    "hot": "Varm",
    "summer": "Sommar",
    "winter": "Vinter",
    "radiator": "Radiator",
    "convector": "Konvektor",
    "floor": "Golvvärme",
    "light": "Lätt",
    "medium": "Medel",
    "heavy": "Tung",
    "outdoor": "Ute",
    "room": "Rum",
    "room outdoor": "Rum och ute",
    "weather compensated": "Väderkompenserad",
    "outside basepoint": "Ute med fotpunkt",
    "power": "Effekt",
    "constant": "Konstant",
    "reduce": "Sänkning",
    "level": "Nivå",
    "absolute": "Absolut",
    "heating & cooling": "Värme och kyla",
    "continuous": "Kontinuerlig",
    "own prog": "Eget program",
    "electric heater": "Elpatron",
    "not installed": "Ej installerad",
    "exclusive": "Exklusiv",
    "parallel": "Parallell",
    "hybrid": "Hybrid",
    "proportional": "Proportionell",
    "mo": "Måndag",
    "tu": "Tisdag",
    "we": "Onsdag",
    "th": "Torsdag",
    "fr": "Fredag",
    "sa": "Lördag",
    "su": "Söndag",
    "all": "Alla dagar",
    "prog 1": "Program 1",
    "prog 2": "Program 2",
    "start": "Start",
    "hold": "Håll",
    "cool": "Kyla",
    "end": "Slut",
    "dhw": "Varmvatten",
    "pool_heat": "Poolvärme",
    "alarm": "Larm",
    "low": "Låg",
    "high": "Hög",
    "ownprogram": "Eget program",
    "Off": "Av",
    "automatic": "Automatisk",
    "forced": "Tvingad",
    "selTemp": "Börvärde",
    "roomTemp": "Rumstemp.",
}


def show(value: str | None, language: str) -> str | None:
    if value is None:
        return None
    if language == "sv":
        return SV.get(value, value)
    return value[:1].upper() + value[1:] if value else value


def options(values: tuple[str, ...], language: str) -> dict[str, str]:
    """Shown word -> source word, keeping every shown word distinct."""
    out: dict[str, str] = {}
    for value in values:
        if value in ("-", ""):
            continue
        shown = show(value, language) or value
        if shown in out:
            shown = f"{shown} ({value})"
        out[shown] = value
    return out
