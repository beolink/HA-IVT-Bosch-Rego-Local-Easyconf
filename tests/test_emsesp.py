"""EMS-ESP: the points come from the gateway's own description of each entity."""

from __future__ import annotations

from custom_components.rego_local_easyconf.emsesp import (
    flatten,
    looks_like_emsesp,
    points_from_entities,
    write_body,
    write_path,
)
from custom_components.rego_local_easyconf.model import BOOL, ENUM, NUMBER, TEXT


def _points(geo_entities, device):
    points, values = points_from_entities(device, geo_entities[device])
    return {p.key: p for p in points}, values


def test_only_entities_with_a_value_become_points(geo_entities):
    boiler, values = _points(geo_entities, "boiler")
    # 218 listed for the Geo's family; the ones carrying a value are this pump's.
    with_value = [k for k, v in geo_entities["boiler"].items() if v.get("value") is not None and v.get("readable", True)]
    assert set(boiler) == set(with_value)
    assert "switchtemp" not in boiler  # listed, never sent by this pump
    assert values["emsesp:boiler:outdoortemp"] == 9.3


def test_write_only_commands_are_left_out(geo_entities):
    boiler, _ = _points(geo_entities, "boiler")
    # reset offers a factory reset; nothing here should put that on a dashboard
    assert "reset" not in boiler
    assert "chimneysweeper" not in boiler


def test_kinds_ranges_and_options(geo_entities):
    boiler, values = _points(geo_entities, "boiler")
    seltempsingle = boiler["dhw.seltempsingle"]
    assert seltempsingle.kind == NUMBER and seltempsingle.writable
    assert seltempsingle.circuit == "dhw"
    assert seltempsingle.step == 0.5
    assert boiler["hpactivity"].kind == ENUM
    assert "hot water" in boiler["hpactivity"].options
    assert boiler["hpcompon"].kind == BOOL
    assert values["emsesp:boiler:hpcompon"] is False
    assert boiler["lastcode"].kind == TEXT


def test_circuit_points_of_the_controller(geo_entities):
    thermostat, values = _points(geo_entities, "thermostat")
    assert thermostat["hc1.seltemp"].writable
    assert thermostat["hc1.seltemp"].circuit == "hc1"
    assert thermostat["hc1.mode"].options == ("off", "manual", "auto")
    assert values["emsesp:thermostat:hc2.designtemp"] == 34
    assert "hc1.remotetemp" not in thermostat  # null on a pump without a room sensor


def test_flatten_nests_circuits_the_way_entities_key_them():
    assert flatten({"outdoortemp": 9.1, "hc1": {"seltemp": 18}, "dhw": {"charge": "off"}}) == {
        "outdoortemp": 9.1,
        "hc1.seltemp": 18,
        "dhw.charge": "off",
    }


def test_write_paths_and_bodies(geo_entities):
    thermostat, _ = _points(geo_entities, "thermostat")
    boiler, _ = _points(geo_entities, "boiler")
    assert write_path(thermostat["hc2.seltemp"]) == "/api/thermostat/hc2/seltemp"
    # The controller's dhw entities need their circuit, or EMS-ESP answers 400.
    assert write_path(thermostat["dhw.charge"]) == "/api/thermostat/dhw/charge"
    assert write_path(boiler["selflowtemp"]) == "/api/boiler/selflowtemp"
    assert write_body(thermostat["hc1.seltemp"], 19.5) == {"value": 19.5}
    assert write_body(thermostat["hc1.seltemp"], 21.0) == {"value": 21}
    assert write_body(thermostat["dhw.charge"], True) == {"value": "on"}
    assert write_body(thermostat["hc1.mode"], "manual") == {"value": "manual"}


def test_system_info_is_recognised(geo_info):
    assert looks_like_emsesp(geo_info)
    assert not looks_like_emsesp({"status": {"H60ver": "1"}})
