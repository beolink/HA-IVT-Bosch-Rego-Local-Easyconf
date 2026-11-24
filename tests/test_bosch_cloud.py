"""Bosch's cloud: the login code, and the resource answers."""

from __future__ import annotations

from custom_components.rego_local_easyconf.bosch_cloud import (
    code_from,
    new_login,
    points_from_payload,
    values_from_payload,
    write_value,
)
from custom_components.rego_local_easyconf.model import BOOL, ENUM, NUMBER


def test_the_code_out_of_whatever_the_browser_shows():
    console = (
        "Failed to launch 'com.bosch.tt.dashtt.pointt://app/login?code=ABC%2Fdef-1&state=xyz' "
        "because the scheme does not have a registered handler."
    )
    assert code_from(console) == "ABC/def-1"
    assert code_from("com.bosch.tt.dashtt.pointt://app/login?code=QWE-1&scope=x") == "QWE-1"
    assert code_from("  QWE-1 ") == "QWE-1"


def test_login_url_uses_pkce_and_the_bosch_redirect():
    login = new_login("bosch")
    assert "code_challenge_method=S256" in login["url"]
    assert "com.bosch.tt.dashtt.pointt" in login["url"]
    assert len(login["verifier"]) >= 43


def test_float_and_string_values():
    payload = {"id": "/heatSources/returnTemperature", "type": "floatValue", "writeable": 0, "value": 50.3, "unitOfMeasure": "C"}
    (point,) = points_from_payload(payload["id"], payload)
    assert point.kind == NUMBER and point.unit == "°C" and not point.writable
    assert values_from_payload(payload["id"], payload, {point.uid: point}) == {point.uid: 50.3}
    sentinel = dict(payload, value=-32768.0)
    assert values_from_payload(payload["id"], sentinel, {point.uid: point}) == {point.uid: None}


def test_mode_and_charge():
    mode = {"type": "stringValue", "writeable": 1, "value": "manual", "allowedValues": ["off", "manual", "auto"]}
    (point,) = points_from_payload("/heatingCircuits/hc1/operationMode", mode)
    assert point.kind == ENUM and point.circuit == "hc1" and point.writable
    charge = {"type": "stringValue", "writeable": 1, "value": "stop", "allowedValues": ["start", "stop"]}
    (boost,) = points_from_payload("/dhwCircuits/dhw1/charge", charge)
    assert boost.kind == BOOL
    assert values_from_payload("/dhwCircuits/dhw1/charge", charge, {boost.uid: boost}) == {boost.uid: False}
    assert write_value(boost, True) == "start"
    assert write_value(boost, False) == "stop"


def test_energy_counters_add_compressor_and_aux():
    payload = {"type": "emonValue", "values": {"outputProduced": 28650, "compressor": 5842, "eheater": 31}}
    points = {p.uid: p for p in points_from_payload("/heatSources/emon/totalConsumption", payload)}
    values = values_from_payload("/heatSources/emon/totalConsumption", payload, points)
    assert values["cloud:heatpump:/heatSources/emon/totalConsumption#input"] == 5873
    assert values["cloud:heatpump:/heatSources/emon/totalConsumption#outputProduced"] == 28650
