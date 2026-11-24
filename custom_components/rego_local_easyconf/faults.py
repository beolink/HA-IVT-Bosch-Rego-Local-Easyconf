"""Fault codes in words.

EMS-ESP reports a device's last fault as one string: the code the display
shows, the cause code in brackets, when it began and either when it ended or
"now" while it lasts - ``A01(5201) 24.11.2026 13:27 - now`` from the IVT Geo,
``A11(1037) 24.11.2026 13:27-24.11.2026 13:28`` from its Rego 3000. The texts
come from Bosch's, Buderus's and IVT's published fault lists (faults.json,
596 codes; docs/fault-codes.md has the sources), keyed by the cause code,
since the display code changes with the device reporting it. Each row says
whether its Swedish and English text is the manufacturer's or translated
here. A code the list lacks keeps its number.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import json
from pathlib import Path
import re

_FAULT_RE = re.compile(
    r"^\s*(?P<display>[A-Za-z0-9]{1,4})?\s*(?:\((?P<cause>\d+)\))?\s*"
    r"(?P<start>\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2})?"
    r"\s*(?:-\s*(?P<end>now|\d{2}\.\d{2}\.\d{4}\s+\d{2}:\d{2}))?\s*$",
    re.IGNORECASE,
)

FAULTS_FILE = Path(__file__).parent / "faults.json"


@dataclass(frozen=True)
class Fault:
    display: str | None
    cause: int | None
    start: datetime | None
    end: datetime | None
    active: bool

    @property
    def code(self) -> str:
        if self.display and self.cause is not None:
            return f"{self.display}/{self.cause}"
        return self.display or (str(self.cause) if self.cause is not None else "")


def _stamp(text: str | None) -> datetime | None:
    if not text or text.lower() == "now":
        return None
    try:
        return datetime.strptime(" ".join(text.split()), "%d.%m.%Y %H:%M")
    except ValueError:
        return None


def parse(value: str | None) -> Fault | None:
    """The parts of an EMS-ESP fault string; None for an empty one."""
    if not value or not str(value).strip():
        return None
    match = _FAULT_RE.match(str(value))
    if match is None:
        return Fault(str(value).strip(), None, None, None, False)
    cause = match.group("cause")
    start = match.group("start")
    end = match.group("end")
    # The pump writes an open fault as "<start> - now"; the controller leaves
    # the end off while its fault lasts and writes "<start>-<end>" once it
    # cleared (EMS-ESP boiler.cpp / thermostat.cpp).
    active = bool(end and end.lower() == "now") or bool(start and not end)
    return Fault(
        display=match.group("display"),
        cause=int(cause) if cause else None,
        start=_stamp(start),
        end=_stamp(end),
        active=active,
    )


_TABLE: dict[str, dict[str, str]] | None = None


def table() -> dict[str, dict[str, str]]:
    """faults.json as {"<display>/<cause>" or "<cause>": {"sv": ..., "en": ...}}.

    Loaded once; read in an executor by the setup path before the event loop
    asks for it, since it is a file.
    """
    global _TABLE
    if _TABLE is None:
        try:
            rows = json.loads(FAULTS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            rows = []
        built: dict[str, dict[str, str]] = {}
        for row in rows:
            cause = row.get("cause_code")
            display = row.get("display_code")
            texts = {
                k: row[k]
                for k in ("sv", "en", "category", "sv_detail", "en_detail", "sv_status", "en_status")
                if row.get(k)
            }
            if cause is not None:
                if display:
                    built[f"{display}/{cause}"] = texts
                built.setdefault(str(cause), texts)
            elif display:
                built.setdefault(str(display), texts)
        _TABLE = built
    return _TABLE


def row_for(fault: Fault | None) -> dict[str, str] | None:
    if fault is None:
        return None
    rows = table()
    return (
        rows.get(fault.code)
        or (rows.get(str(fault.cause)) if fault.cause is not None else None)
        or (rows.get(fault.display or "") if fault.display else None)
    )


def text(fault: Fault | None, language: str) -> str:
    """The fault in words: the published text where there is one, the code otherwise."""
    sv = language == "sv"
    if fault is None:
        return "Inget fel" if sv else "No fault"
    row = row_for(fault)
    words = None
    if row:
        words = row.get("sv" if sv else "en") or row.get("en") or row.get("sv")
    label = fault.code
    described = f"{label}: {words}" if words else (f"felkod {label}" if sv else f"fault {label}")
    if fault.active:
        return described[:1].upper() + described[1:255] if not words else described[:255]
    # EMS-ESP keeps the last fault after it cleared; say it is over.
    return (f"Inget fel nu (senast {described})" if sv else f"No fault now (last {described})")[:255]
