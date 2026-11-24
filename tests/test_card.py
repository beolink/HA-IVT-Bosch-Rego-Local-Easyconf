"""The dashboard card's logic, run in node.

The card's pure helpers are loaded into node when it is installed (GitHub's
runners have it); the custom elements are only defined in a browser, so the
DOM part is not tested here. What is pinned is what decides which entities a
user sees and how: that another integration's entities never leak in, that a
disabled entity stays out, that the device-name prefix Home Assistant adds to
every entity is dropped, that a role's own group decides its section, and
that a card given the pump's device also shows the devices hung under it.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess

import pytest

CARD = (
    Path(__file__).resolve().parents[1]
    / "custom_components"
    / "rego_local_easyconf"
    / "www"
    / "rego-easyconf-card.js"
)

NODE = shutil.which("node") or (
    "/opt/homebrew/bin/node" if Path("/opt/homebrew/bin/node").exists() else None
)

pytestmark = pytest.mark.skipif(NODE is None, reason="node not installed")


def _run(script: str):
    """Evaluate `script` in node with the card's helpers bound to `c`."""
    program = f"const c = require({json.dumps(str(CARD))});\n{script}"
    out = subprocess.run(
        [NODE, "-e", program], capture_output=True, text=True, timeout=30, check=True
    )
    return json.loads(out.stdout)


#: One installation as Home Assistant's frontend sees it: the pump (d1) with
#: its roles, the controller (d3) and the EMS-ESP gateway (d4) hung under it,
#: a second pump (d5) with its own controller (d6), and another integration's
#: device (d2) that also happens to sit under the pump.
HASS = """
const hass = {
  config: {language: "sv"},
  devices: {
    d1: {id: "d1", name: "IVT Geo", via_device_id: null},
    d2: {id: "d2", name: "Pool", via_device_id: "d1"},
    d3: {id: "d3", name: "IVT Geo styrenhet", via_device_id: "d1"},
    d4: {id: "d4", name: "EMS-ESP (BBQKees)", via_device_id: "d1"},
    d5: {id: "d5", name: "Garage VP", via_device_id: null},
    d6: {id: "d6", name: "Garage VP styrenhet", via_device_id: "d5"},
  },
  entities: {
    "sensor.ivt_geo_utetemperatur": {entity_id: "sensor.ivt_geo_utetemperatur",
      platform: "rego_local_easyconf", device_id: "d1", entity_category: null},
    "sensor.ivt_geo_kompressor_varvtal": {entity_id: "sensor.ivt_geo_kompressor_varvtal",
      platform: "rego_local_easyconf", device_id: "d1", entity_category: null},
    "sensor.ivt_geo_larm": {entity_id: "sensor.ivt_geo_larm",
      platform: "rego_local_easyconf", device_id: "d1", entity_category: null},
    "select.ivt_geo_varmelage": {entity_id: "select.ivt_geo_varmelage",
      platform: "rego_local_easyconf", device_id: "d1", entity_category: null,
      translation_key: "heating_mode"},
    "sensor.ivt_geo_cop_dygn": {entity_id: "sensor.ivt_geo_cop_dygn",
      platform: "rego_local_easyconf", device_id: "d1", entity_category: null},
    "number.ivt_geo_styrenhet_dimensionerande_framledning_krets_1": {
      entity_id: "number.ivt_geo_styrenhet_dimensionerande_framledning_krets_1",
      platform: "rego_local_easyconf", device_id: "d3", entity_category: "config"},
    "sensor.ivt_geo_styrenhet_firmware": {entity_id: "sensor.ivt_geo_styrenhet_firmware",
      platform: "rego_local_easyconf", device_id: "d3", entity_category: "diagnostic"},
    "sensor.ivt_geo_styrenhet_dampad": {entity_id: "sensor.ivt_geo_styrenhet_dampad",
      platform: "rego_local_easyconf", device_id: "d3", entity_category: null},
    "binary_sensor.ems_esp_bbqkees_ansluten": {entity_id: "binary_sensor.ems_esp_bbqkees_ansluten",
      platform: "rego_local_easyconf", device_id: "d4", entity_category: "diagnostic"},
    "sensor.pool_temp": {entity_id: "sensor.pool_temp",
      platform: "intellipool", device_id: "d2"},
    "sensor.ivt_geo_disabled": {entity_id: "sensor.ivt_geo_disabled",
      platform: "rego_local_easyconf", device_id: "d1"},
    "climate.ivt_geo_varmekrets_1": {entity_id: "climate.ivt_geo_varmekrets_1",
      platform: "rego_local_easyconf", device_id: "d1", entity_category: null},
    "water_heater.ivt_geo_varmvatten": {entity_id: "water_heater.ivt_geo_varmvatten",
      platform: "rego_local_easyconf", device_id: "d1", entity_category: null},
    "sensor.garage_vp_utetemperatur": {entity_id: "sensor.garage_vp_utetemperatur",
      platform: "rego_local_easyconf", device_id: "d5", entity_category: null},
    "sensor.garage_vp_styrenhet_rum": {entity_id: "sensor.garage_vp_styrenhet_rum",
      platform: "rego_local_easyconf", device_id: "d6", entity_category: null},
  },
  states: {
    "sensor.ivt_geo_utetemperatur": {state: "3.4", attributes: {
      friendly_name: "IVT Geo Utetemperatur", unit_of_measurement: "°C",
      device_class: "temperature", state_class: "measurement",
      description: "Utomhusgivaren T1.", role: "outdoor_temp", group: "temperatures",
      source: "emsesp", source_key: "boiler/outdoortemp", source_title: "outside temperature"}},
    "sensor.ivt_geo_kompressor_varvtal": {state: "38", attributes: {
      friendly_name: "IVT Geo Kompressor, varvtal", unit_of_measurement: "%",
      description: "Hur fort kompressorn går.", role: "compressor_speed", group: "compressor",
      source: "emsesp", source_key: "boiler/hpcompspd", source_title: "compressor speed"}},
    "sensor.ivt_geo_larm": {state: "Inget fel", attributes: {
      friendly_name: "IVT Geo Larm", description: "Senaste felet.", role: "alarm",
      group: "status", source: "emsesp", source_key: "boiler/lastcode",
      source_title: "last error code", alarm_code: 0, active: false,
      display_code: null, cause_code: null}},
    "select.ivt_geo_varmelage": {state: "eco", attributes: {
      friendly_name: "IVT Geo Värmeläge", options: ["blocked", "eco", "normal", "boost"],
      description: "Värmeläget.", setpoints: {}, normal_setpoints: {hc1: 21}}},
    "sensor.ivt_geo_cop_dygn": {state: "3.4", attributes: {
      friendly_name: "IVT Geo COP, dygn", description: "Värmefaktor.", span: "day",
      basis: "senaste dygnet"}},
    "number.ivt_geo_styrenhet_dimensionerande_framledning_krets_1": {state: "45", attributes: {
      friendly_name: "IVT Geo styrenhet Dimensionerande framledning, krets 1",
      min: 30, max: 90, step: 1, unit_of_measurement: "°C",
      description: "Framledningen vid DUT.", source: "emsesp",
      source_key: "thermostat/hc1.designtemp", source_title: "design temperature"}},
    "sensor.ivt_geo_styrenhet_firmware": {state: "04.08", attributes: {
      friendly_name: "IVT Geo styrenhet Firmware", source: "emsesp",
      source_key: "thermostat/version", source_title: "version"}},
    "sensor.ivt_geo_styrenhet_dampad": {state: "2.1", attributes: {
      friendly_name: "IVT Geo styrenhet Dämpad utetemp.", unit_of_measurement: "°C",
      source: "emsesp", source_key: "thermostat/dampedoutdoortemp",
      source_title: "damped outdoor temperature"}},
    "binary_sensor.ems_esp_bbqkees_ansluten": {state: "on", attributes: {
      friendly_name: "EMS-ESP (BBQKees) Ansluten", device_class: "connectivity",
      source: "emsesp", label: "EMS-ESP (BBQKees)", points: 212, last_error: null}},
    "sensor.pool_temp": {state: "24", attributes: {friendly_name: "Pool temp"}},
    "climate.ivt_geo_varmekrets_1": {state: "auto", attributes: {
      friendly_name: "IVT Geo Värmekrets 1", description: "Termostaten"}},
    "water_heater.ivt_geo_varmvatten": {state: "eco", attributes: {
      friendly_name: "IVT Geo Varmvatten", description: "Varmvattnet"}},
    "sensor.garage_vp_utetemperatur": {state: "2.9", attributes: {
      friendly_name: "Garage VP Utetemperatur", role: "outdoor_temp", group: "temperatures"}},
    "sensor.garage_vp_styrenhet_rum": {state: "20.5", attributes: {
      friendly_name: "Garage VP styrenhet Rum"}},
  },
};
"""

PUMP_ONLY = (
    "const rows = c.collectRows(hass, 'd1');"
    "const byId = Object.fromEntries(rows.map(r => [r.entityId, r]));"
)


def test_only_this_integrations_enabled_entities_appear():
    ids = _run(HASS + "console.log(JSON.stringify(c.collectRows(hass, null).map(r => r.entityId)))")
    assert "sensor.pool_temp" not in ids  # another integration
    assert "sensor.ivt_geo_disabled" not in ids  # disabled: no state
    # The thermostat and the water heater are made of roles that are rows of
    # their own.
    assert "climate.ivt_geo_varmekrets_1" not in ids
    assert "water_heater.ivt_geo_varmvatten" not in ids
    assert len(ids) == 11


def test_a_card_given_the_pump_also_shows_the_devices_under_it():
    """The controller and the gateway are devices of their own, hung under the
    pump with via_device; the pump's card is about all of them, and about
    nothing of the other pump's."""
    ids = _run(HASS + "console.log(JSON.stringify(c.collectRows(hass, 'd1').map(r => r.entityId)))")
    assert "sensor.ivt_geo_utetemperatur" in ids  # the pump itself
    assert "number.ivt_geo_styrenhet_dimensionerande_framledning_krets_1" in ids  # controller
    assert "binary_sensor.ems_esp_bbqkees_ansluten" in ids  # the gateway
    assert "sensor.garage_vp_utetemperatur" not in ids  # the other pump
    assert "sensor.garage_vp_styrenhet_rum" not in ids  # and its controller
    assert "sensor.pool_temp" not in ids  # under the pump, but not ours
    garage = _run(HASS + "console.log(JSON.stringify(c.collectRows(hass, 'd5').map(r => r.entityId)))")
    assert sorted(garage) == ["sensor.garage_vp_styrenhet_rum", "sensor.garage_vp_utetemperatur"]
    devices = _run(HASS + "console.log(JSON.stringify([...c.devicesOf(hass, 'd1')].sort()))")
    assert devices == ["d1", "d2", "d3", "d4"]


def test_roles_land_in_their_own_group():
    """A role says what it is for; that, not its entity category, decides its
    section. The heading words follow."""
    groups = _run(
        HASS + PUMP_ONLY
        + "console.log(JSON.stringify(Object.fromEntries(rows.map(r => [r.entityId, r.group]))))"
    )
    assert groups["sensor.ivt_geo_utetemperatur"] == "temperatures"
    assert groups["sensor.ivt_geo_kompressor_varvtal"] == "compressor"
    assert groups["sensor.ivt_geo_larm"] == "status"
    # Made of other values, but still about the heating and the energy.
    assert groups["select.ivt_geo_varmelage"] == "heating"
    assert groups["sensor.ivt_geo_cop_dygn"] == "energy"
    order = _run("console.log(JSON.stringify(c.GROUP_ORDER))")
    assert order == [
        "temperatures", "compressor", "energy", "heating", "hotwater", "status",
        "sensor", "config", "diagnostic",
    ]
    words = _run(
        "const t = c.textFor('sv'); console.log(JSON.stringify(c.GROUP_ORDER.map(g => t[g])))"
    )
    assert words == [
        "Temperaturer", "Kompressor", "Energi", "Värme", "Varmvatten", "Status",
        "Mätvärden", "Inställningar", "Diagnostik",
    ]


def test_points_without_a_role_land_in_the_device_pages_own_sections():
    groups = _run(
        HASS + PUMP_ONLY
        + "console.log(JSON.stringify(Object.fromEntries(rows.map(r => [r.entityId, r.group]))))"
    )
    assert groups["number.ivt_geo_styrenhet_dimensionerande_framledning_krets_1"] == "config"
    assert groups["sensor.ivt_geo_styrenhet_firmware"] == "diagnostic"
    assert groups["binary_sensor.ems_esp_bbqkees_ansluten"] == "diagnostic"
    assert groups["sensor.ivt_geo_styrenhet_dampad"] == "sensor"


def test_the_device_name_prefix_is_dropped():
    names = _run(
        HASS + "console.log(JSON.stringify(c.collectRows(hass, null).map(r => [r.name, r.place])))"
    )
    assert ["Utetemperatur", ""] in names
    # A device under the pump keeps a word for where it sits, since its own
    # name is gone from the entity's.
    assert ["Dimensionerande framledning, krets 1", "Styrenhet"] in names
    assert ["Ansluten", "EMS-ESP (BBQKees)"] in names
    assert not any(name.startswith(("IVT Geo ", "Garage VP ", "EMS-ESP")) for name, _ in names)


def test_the_explanation_and_the_source_travel_with_the_row():
    row = _run(HASS + PUMP_ONLY + "console.log(JSON.stringify(byId['sensor.ivt_geo_utetemperatur']))")
    assert row["description"] == "Utomhusgivaren T1."
    assert row["role"] == "outdoor_temp"
    assert row["source"] == "emsesp"
    assert row["sourceKey"] == "boiler/outdoortemp"
    assert row["sourceTitle"] == "outside temperature"
    meta = _run(
        HASS + PUMP_ONLY
        + "console.log(JSON.stringify([c.sourceMeta(byId['sensor.ivt_geo_utetemperatur'], c.textFor('sv')),"
        + "c.sourceMeta({source: 'cloud', sourceKey: 'heatpump/x'}, c.textFor('en')),"
        + "c.sourceMeta(byId['sensor.ivt_geo_cop_dygn'], c.textFor('sv'))]))"
    )
    assert meta == [
        "Källa: EMS-ESP · boiler/outdoortemp · outside temperature",
        "Source: Bosch cloud · heatpump/x",
        "",  # made by the integration, read from no source
    ]


def test_what_an_unavailable_entity_stops_saying_is_remembered():
    """An unavailable entity carries no attributes: no explanation, no role,
    no group, no source. The page keeps what it said last, so the outdoor
    temperature keeps its place on the overview while its source is away."""
    kept = _run(
        HASS
        + "const memory = new Map(); c.recall(c.collectRows(hass, 'd1'), memory);"
        + "hass.states['sensor.ivt_geo_utetemperatur'] = {state: 'unavailable', attributes: {"
        + "  friendly_name: 'IVT Geo Utetemperatur', device_class: 'temperature'}};"
        + "const rows = c.recall(c.collectRows(hass, 'd1'), memory);"
        + "const row = rows.find(r => r.entityId === 'sensor.ivt_geo_utetemperatur');"
        + "const fresh = c.collectRows(hass, 'd1').find(r => r.entityId === row.entityId);"
        + "console.log(JSON.stringify([row.role, row.group, row.description, row.sourceKey,"
        + "  c.pickOverview(rows).readings[0].entityId, fresh.role, fresh.group]))"
    )
    assert kept == [
        "outdoor_temp", "temperatures", "Utomhusgivaren T1.", "boiler/outdoortemp",
        "sensor.ivt_geo_utetemperatur",
        "", "sensor",  # what it would have been without the memory
    ]


def test_values_read_like_the_device_page():
    text = _run(
        HASS
        + "const t = c.textFor('sv'); const rows = c.collectRows(hass, 'd1');"
        + "const mode = rows.find(r => r.isHeatingMode);"
        + "console.log(JSON.stringify(["
        + "c.formatState(hass.states['sensor.ivt_geo_utetemperatur'], t),"
        + "c.formatState(hass.states['binary_sensor.ems_esp_bbqkees_ansluten'], t),"
        + "c.formatState(undefined, t),"
        + "c.formatState(hass.states['select.ivt_geo_varmelage'], t, mode),"
        + "c.formatState(hass.states['select.ivt_geo_varmelage'], c.textFor('en'), mode),"
        + "c.optionLabel(mode, 'blocked', t), c.optionLabel({}, 'blocked', t)]))"
    )
    assert text == ["3.4 °C", "på", "ej tillgänglig", "Eko", "Eco", "Spärrad", "blocked"]


def test_the_filter_searches_names_and_explanations():
    hits = _run(
        "console.log(JSON.stringify(["
        "c.matchesFilter('ute', 'Utetemperatur', ''),"
        "c.matchesFilter('t1', 'Utetemperatur', 'Utomhusgivaren T1.'),"
        "c.matchesFilter('ute t1', 'Utetemperatur', 'Utomhusgivaren T1.'),"
        "c.matchesFilter('pool', 'Utetemperatur', ''),"
        "c.matchesFilter('', 'x', '')]))"
    )
    assert hits == [True, True, True, False, True]


def test_an_unrelated_state_change_does_not_redraw():
    same = _run(
        HASS
        + "const rows = c.collectRows(hass, null); const before = c.signature(hass, rows);"
        + "hass.states['sensor.pool_temp'] = {state: '25', attributes: {}};"
        + "const afterPool = c.signature(hass, rows);"
        + "hass.states['sensor.ivt_geo_utetemperatur'] = {state: '4.0', attributes: {}};"
        + "const afterPump = c.signature(hass, rows);"
        + "console.log(JSON.stringify([before === afterPool, before === afterPump]))"
    )
    assert same == [True, False]


def test_language_falls_back_to_english():
    labels = _run(
        "console.log(JSON.stringify([c.textFor('sv').config, c.textFor('en').config,"
        " c.textFor('de').config, c.textFor(undefined).config,"
        " c.textFor('sv').title, c.textFor('en').title]))"
    )
    assert labels == ["Inställningar", "Settings", "Settings", "Settings", "Värmepump", "Heat pump"]
    same_keys = _run(
        "console.log(JSON.stringify(Object.keys(c.textFor('en')).every(k => k in c.textFor('sv'))))"
    )
    assert same_keys is True


def test_the_page_speaks_the_language_the_entities_were_named_in():
    languages = _run(
        "console.log(JSON.stringify(["
        "c.languageOf({config: {language: 'en'}, locale: {language: 'sv'}}),"
        "c.languageOf({config: {language: 'sv'}, locale: {language: 'en'}}),"
        "c.languageOf({locale: {language: 'sv'}}),"
        "c.languageOf({})]))"
    )
    assert languages == ["en", "sv", "sv", ""]


def test_the_heading_names_the_installations_not_their_parts():
    names = _run(
        HASS
        + "console.log(JSON.stringify([c.installationNames(hass, null),"
        + "c.installationNames(hass, 'd1'), c.installationNames(hass, 'nope')]))"
    )
    assert names == ["IVT Geo · Garage VP", "IVT Geo", ""]


# ------------------------------------------------------------------ controls


def test_controls_are_grouped_by_what_they_do():
    groups = _run(
        "console.log(JSON.stringify(["
        "c.controlGroupOf({isHeatingMode: true}),"
        "c.controlGroupOf({roleGroup: 'heating'}),"
        "c.controlGroupOf({roleGroup: 'hotwater'}),"
        "c.controlGroupOf({roleGroup: 'status'}),"
        "c.controlGroupOf({roleGroup: 'temperatures'}),"
        # A point that plays no role, by the source's own key.
        "c.controlGroupOf({sourceKey: 'thermostat/hc2.designtemp'}),"
        "c.controlGroupOf({sourceKey: 'boiler/dhw.seltemp'}),"
        "c.controlGroupOf({sourceKey: 'boiler/dhw2.seltemp'}),"
        "c.controlGroupOf({sourceKey: 'boiler/pumpkickhour'}),"
        "c.controlGroupOf({})]))"
    )
    assert groups == [
        "heating", "heating", "hotwater", "operation", "other",
        "heating", "hotwater", "hotwater", "other", "other",
    ]
    assert _run("console.log(JSON.stringify(c.CONTROL_GROUP_ORDER))") == [
        "heating", "hotwater", "operation", "other",
    ]


def test_a_number_gets_a_slider_only_when_it_can_be_aimed_at():
    kinds = _run(
        "console.log(JSON.stringify(["
        "c.widgetFor('number.offset', {min: -10, max: 10, step: 0.5}),"
        "c.widgetFor('number.wide', {min: -100, max: 100, step: 0.1}),"
        "c.widgetFor('number.design', {min: 30, max: 90, step: 1}),"
        "c.widgetFor('number.unknown', {}),"
        "c.widgetFor('select.mode', {}), c.widgetFor('switch.boost', {}),"
        "c.widgetFor('button.rescan', {}), c.widgetFor('sensor.t1', {})]))"
    )
    assert kinds == ["slider", "number", "slider", "number", "select", "toggle", "button", "text"]


def test_only_writable_entities_reach_the_control_section_and_in_group_order():
    rows = _run(
        "const rows = ["
        "{entityId: 'sensor.t1', name: 'Utetemperatur', roleGroup: 'temperatures'},"
        "{entityId: 'button.rescan', name: 'Sök om värden'},"
        "{entityId: 'select.silent', name: 'Tyst läge', roleGroup: 'status'},"
        "{entityId: 'switch.boost', name: 'Varmvattenboost', roleGroup: 'hotwater'},"
        "{entityId: 'number.design', name: 'Dimensionerande framledning, krets 1',"
        " sourceKey: 'thermostat/hc1.designtemp'},"
        "{entityId: 'select.mode', name: 'Värmeläge', isHeatingMode: true}];"
        "console.log(JSON.stringify(c.controlRows(rows).map(r => r.entityId)))"
    )
    assert rows == [
        "number.design", "select.mode", "switch.boost", "select.silent", "button.rescan",
    ]


def test_a_control_writes_through_its_own_service():
    calls = _run(
        "console.log(JSON.stringify(["
        "c.serviceFor('select.mode', 'eco'),"
        "c.serviceFor('number.design', '45'),"
        "c.serviceFor('switch.boost', true),"
        "c.serviceFor('switch.boost', false),"
        "c.serviceFor('button.rescan', null),"
        "c.serviceFor('sensor.t1', 1)]))"
    )
    assert calls[0] == {
        "domain": "select", "service": "select_option",
        "data": {"entity_id": "select.mode", "option": "eco"},
    }
    assert calls[1] == {
        "domain": "number", "service": "set_value",
        "data": {"entity_id": "number.design", "value": 45},
    }
    assert calls[2]["service"] == "turn_on"
    assert calls[3]["service"] == "turn_off"
    assert calls[4] == {
        "domain": "button", "service": "press", "data": {"entity_id": "button.rescan"},
    }
    assert calls[5] is None


# ------------------------------------------------------------------ overview

#: Rows as collectRows makes them, for a pump that has every role the
#: overview asks for, in no particular order.
ROWS = """
const rows = [
  {entityId: "sensor.energy_out", name: "Total produktion", role: "energy_out_total", roleGroup: "energy"},
  {entityId: "sensor.energy_in", name: "Total förbrukning", role: "energy_in_total", roleGroup: "energy"},
  {entityId: "sensor.energy_aux", name: "Tillsats, förbrukning", role: "energy_aux_total", roleGroup: "energy"},
  {entityId: "sensor.speed", name: "Kompressor, varvtal", role: "compressor_speed", roleGroup: "compressor"},
  {entityId: "sensor.power", name: "Kompressor, eleffekt", role: "compressor_power", roleGroup: "compressor"},
  {entityId: "sensor.output", name: "Avgiven effekt", role: "heat_output", roleGroup: "compressor"},
  {entityId: "sensor.dhw", name: "Varmvatten", role: "dhw_temp", roleGroup: "hotwater"},
  {entityId: "sensor.brine_out", name: "Köldbärare ut", role: "brine_out", roleGroup: "temperatures"},
  {entityId: "sensor.brine_in", name: "Köldbärare in", role: "brine_in", roleGroup: "temperatures"},
  {entityId: "sensor.return", name: "Retur", role: "return_temp", roleGroup: "temperatures"},
  {entityId: "sensor.supply", name: "Framledning", role: "supply_temp", roleGroup: "temperatures"},
  {entityId: "sensor.outdoor", name: "Utetemperatur", role: "outdoor_temp", roleGroup: "temperatures"},
  {entityId: "sensor.hc1_room", name: "Rumstemperatur, krets 1", role: "hc1_room_temp", roleGroup: "temperatures"},
  {entityId: "sensor.activity", name: "Driftläge", role: "compressor_activity", roleGroup: "status"},
  {entityId: "sensor.alarm", name: "Larm", role: "alarm", roleGroup: "status", isAlarm: true},
  {entityId: "sensor.controller_alarm", name: "Larm, styrenhet", role: "controller_alarm",
   roleGroup: "status", isAlarm: true, alarmActive: false},
  {entityId: "sensor.cop_life", name: "COP, livstid", isCop: true, copSpan: "lifetime", state: "3.9"},
  {entityId: "sensor.cop_year", name: "COP, år", isCop: true, copSpan: "year", state: "4.1"},
  {entityId: "sensor.cop_day", name: "COP, dygn", isCop: true, copSpan: "day", state: "3.2"},
  {entityId: "select.mode", name: "Värmeläge", isHeatingMode: true},
  {entityId: "select.dhw_mode", name: "Varmvattenläge", role: "dhw_mode", roleGroup: "hotwater"},
  {entityId: "switch.dhw_boost", name: "Varmvattenboost", role: "dhw_boost", roleGroup: "hotwater"},
  {entityId: "number.dhw_setpoint", name: "Varmvatten, börvärde", role: "dhw_setpoint", roleGroup: "hotwater"},
  {entityId: "binary_sensor.emsesp", name: "Ansluten", isSource: true, source: "emsesp"},
  {entityId: "binary_sensor.cloud", name: "Ansluten", isSource: true, source: "cloud"},
];
"""


def test_the_overview_leads_with_the_alarm_the_state_the_mode_and_the_day():
    picked = _run(ROWS + "console.log(JSON.stringify(c.pickOverview(rows)))")
    assert [row["entityId"] for row in picked["status"]] == [
        "sensor.alarm", "sensor.activity", "select.mode", "sensor.cop_day",
    ]
    assert [row["entityId"] for row in picked["readings"]] == [
        "sensor.outdoor", "sensor.supply", "sensor.return", "sensor.brine_in",
        "sensor.brine_out", "sensor.dhw", "sensor.power", "sensor.speed",
        "sensor.energy_in", "sensor.energy_out", "sensor.cop_year", "sensor.cop_life",
    ]
    assert [row["entityId"] for row in picked["sources"]] == [
        "binary_sensor.emsesp", "binary_sensor.cloud",
    ]


def test_the_controllers_alarm_gets_a_chip_only_while_it_lasts():
    status = _run(
        ROWS
        + "rows.find(r => r.role === 'controller_alarm').alarmActive = true;"
        + "console.log(JSON.stringify(c.pickOverview(rows).status.map(r => r.entityId)))"
    )
    assert status[:2] == ["sensor.alarm", "sensor.controller_alarm"]


def test_the_alarm_chip_is_red_only_while_the_fault_is_active():
    """The alarm sensor keeps the last fault, in words, after it has cleared;
    a code alone does not make it an alarm."""
    raised = _run(
        "const alarm = {isAlarm: true};"
        "console.log(JSON.stringify(["
        "c.alarmRaised(alarm, {state: 'A01/5201: Lågt tryck', attributes: {alarm_code: 'A01/5201', active: true}}),"
        "c.alarmRaised(alarm, {state: 'A01/5201: Lågt tryck', attributes: {alarm_code: 'A01/5201', active: false}}),"
        "c.alarmRaised(alarm, {state: 'Inget fel', attributes: {alarm_code: 0, active: false}}),"
        "c.alarmRaised(alarm, {state: 'unavailable', attributes: {active: true}}),"
        "c.alarmRaised(alarm, undefined),"
        "c.alarmRaised({isAlarm: false}, {state: 'x', attributes: {active: true}})]))"
    )
    assert raised == [True, False, False, False, False, False]


def test_each_source_reads_as_a_small_chip():
    chips = _run(
        "const sv = c.textFor('sv'), en = c.textFor('en');"
        "console.log(JSON.stringify(["
        "c.sourceChip({source: 'emsesp'}, {state: 'on'}, sv).text,"
        "c.sourceChip({source: 'cloud'}, {state: 'off'}, sv).text,"
        "c.sourceChip({source: 'cloud'}, {state: 'off'}, en).text,"
        "c.sourceChip({source: 'bosch_local'}, {state: 'on'}, sv).text,"
        "c.sourceChip({source: 'husdata'}, undefined, sv).text,"
        "c.sourceChip({source: 'new', sourceLabel: 'Ny källa'}, {state: 'on'}, sv).text,"
        "c.sourceChip({source: 'cloud'}, {state: 'off'}, sv).up]))"
    )
    assert chips == [
        "EMS-ESP ✓", "Bosch-molnet ✗", "Bosch cloud ✗", "Bosch-gateway ✓", "Husdata ?",
        "Ny källa ✓", False,
    ]


def test_the_overview_carries_the_controls_that_matter():
    picked = _run(ROWS + "console.log(JSON.stringify(c.pickQuickControls(rows).map(r => r.entityId)))")
    assert picked == ["select.mode", "select.dhw_mode", "switch.dhw_boost"]


def test_the_overview_has_no_efficiency_when_the_pump_has_none():
    picked = _run(
        ROWS
        + "const p = c.pickOverview(rows.filter(r => !r.isCop));"
        + "console.log(JSON.stringify([p.cop, p.status.map(r => r.entityId)]))"
    )
    assert picked == [[], ["sensor.alarm", "sensor.activity", "select.mode"]]


def test_without_a_days_figure_the_chip_shows_one_that_has_a_number():
    picked = _run(
        """const rows = [
          {entityId: "sensor.cop_a", name: "COP a", isCop: true, state: "unknown"},
          {entityId: "sensor.cop_b", name: "COP b", isCop: true, state: "4.18"},
        ];
        console.log(JSON.stringify(c.pickOverview(rows).status.map(r => r.entityId)))"""
    )
    assert picked == ["sensor.cop_b"]


# -------------------------------------------------------------------- graphs


def test_graphs_are_picked_by_role():
    graphs = _run(ROWS + "console.log(JSON.stringify(c.pickGraphs(rows)))")
    assert [g["key"] for g in graphs] == ["temps", "compressor", "cop", "energy"]
    # No room sensor of its own: heating circuit 1's stands in.
    assert graphs[0]["entities"] == [
        "sensor.hc1_room", "sensor.outdoor", "sensor.supply", "sensor.return",
        "sensor.dhw", "sensor.brine_in", "sensor.brine_out",
    ]
    assert graphs[1]["entities"] == ["sensor.speed", "sensor.power", "sensor.output"]
    # The day against the year; a lifetime line barely moves.
    assert graphs[2]["entities"] == ["sensor.cop_day", "sensor.cop_year"]
    assert graphs[3]["entities"] == ["sensor.energy_out", "sensor.energy_in", "sensor.energy_aux"]
    overview = _run(ROWS + "console.log(JSON.stringify(c.overviewGraphs(rows)))")
    assert overview == [{
        "key": "temps", "title": "graphTemps",
        "entities": ["sensor.outdoor", "sensor.supply", "sensor.return", "sensor.dhw"],
    }]


def test_a_pump_without_a_role_gets_no_graph_for_it():
    keys = _run(
        ROWS
        + "console.log(JSON.stringify(c.pickGraphs(rows.filter(r => !r.isCop &&"
        + " !(r.roleGroup === 'compressor'))).map(g => g.key)))"
    )
    assert keys == ["temps", "energy"]
    assert _run("console.log(JSON.stringify(c.pickGraphs([])))") == []


def test_counters_are_drawn_from_the_statistics_and_the_rest_from_history():
    configs = _run(
        ROWS
        + "const t = c.textFor('sv');"
        + "console.log(JSON.stringify(c.pickGraphs(rows).map(g => c.graphConfig(g, t))))"
    )
    temps, _compressor, cop, energy = configs
    assert temps["type"] == "history-graph" and temps["hours_to_show"] == 24
    assert temps["title"] == "Temperaturer, ett dygn"
    assert energy["type"] == "statistics-graph"
    assert energy["stat_types"] == ["change"] and energy["chart_type"] == "bar"
    assert energy["period"] == "day" and energy["days_to_show"] == 30
    assert cop["stat_types"] == ["mean"] and cop["chart_type"] == "line"


# -------------------------------------------------------------------- source


def test_an_explanation_that_arrives_late_still_gets_its_i():
    marks = _run(
        """const quiet = [{entityId: "sensor.t1", name: "Ute", description: ""}];
        const loud = [{entityId: "sensor.t1", name: "Ute", description: "Mäter ute."}];
        console.log(JSON.stringify([c.structureOf(quiet), c.structureOf(loud)]))"""
    )
    assert marks == ["sensor.t1", "sensor.t1!"]
    source = CARD.read_text(encoding="utf-8")
    assert "this.remember(collectRows(this.hass, this.deviceId))" in source


def test_every_value_on_the_page_carries_its_explanation():
    source = CARD.read_text(encoding="utf-8")
    assert source.count('why.textContent = "ⓘ"') == 1
    assert source.count("this.explainButton(") == 3  # controls, tiles, chips


def test_nothing_from_home_assistant_is_parsed_as_html():
    """Names, explanations and the sources' own titles come from devices and
    gateways; they go into the page as text only."""
    source = CARD.read_text(encoding="utf-8")
    assert "innerHTML" not in source
    assert "insertAdjacentHTML" not in source
    assert "outerHTML" not in source


def test_the_page_wears_the_integrations_mark_or_none():
    source = CARD.read_text(encoding="utf-8")
    assert 'mark.src = `/${DOMAIN}/icon.png`' in source
    assert 'mark.addEventListener("error", () => { mark.hidden = true; })' in source
    assert _run("console.log(JSON.stringify(c.DOMAIN))") == "rego_local_easyconf"


def test_the_elements_are_the_ones_the_integration_registers():
    source = CARD.read_text(encoding="utf-8")
    assert 'customElements.define("rego-easyconf-card"' in source
    assert 'customElements.define("rego-easyconf-panel"' in source
    frontend = (CARD.parents[1] / "frontend.py").read_text(encoding="utf-8")
    assert 'PANEL_ELEMENT = "rego-easyconf-panel"' in frontend
    assert '"www" / "rego-easyconf-card.js"' in frontend


def test_nothing_of_the_pump_it_was_ported_from_is_left():
    source = CARD.read_text(encoding="utf-8").lower()
    for word in ("nibe", "modbus", "modbus_register", "accessor", "nibetitle"):
        assert word not in source, word


def test_the_layout_keeps_its_shape():
    """The overview puts the controls beside the graph, and the performance
    tab fills two columns itself so each graph keeps its own height."""
    source = CARD.read_text(encoding="utf-8")
    assert "this.overviewRow.append(this.quickCard, this.overviewGraphs)" in source
    assert 'this.graphsBody.className = "graphs flow"' in source
    assert "columns[index % columns.length]" in source


def test_the_tabs_end_with_every_value():
    tabs = _run("console.log(JSON.stringify(c.TAB_ORDER))")
    assert tabs == ["overview", "controls", "performance", "values"]
