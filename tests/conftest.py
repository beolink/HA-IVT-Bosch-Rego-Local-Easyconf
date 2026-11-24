"""Shared fixtures: the EMS-ESP answers of the IVT Geo 608C this was built against."""

from __future__ import annotations

import json
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

FIXTURES = Path(__file__).parent / "fixtures" / "emsesp_geo608c"


def load(name: str):
    return json.loads((FIXTURES / name).read_text(encoding="utf-8"))


@pytest.fixture
def geo_entities() -> dict[str, dict]:
    return {device: load(f"{device}_entities.json") for device in ("boiler", "thermostat", "mixer")}


@pytest.fixture
def geo_info() -> dict:
    return load("system_info.json")
