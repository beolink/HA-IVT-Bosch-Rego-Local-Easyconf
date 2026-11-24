"""The values every heat pump has, whichever way they are read.

A *role* is a value with a meaning of its own - the outdoor temperature, the
heat delivered over the pump's lifetime, the room setpoint of heating circuit
1 - and each source says which of its points plays it. That is what lets one
entity show the outdoor temperature from EMS-ESP while the gateway answers,
from Husdata or the cloud when it does not, and what lets a source lower in
the order fill in a value the one above it lacks, without the same value
showing up twice.

The heating mode, the thermostat, the water heater, the hot water boost and
the coefficient of performance are all built on roles, so they work the same
whichever source feeds them.

A role lists candidates per source in order of preference: EMS-ESP reports a
heat pump's supply temperature both as the boiler's "current flow
temperature" and as the heat pump's own TC1, and on a pump with a low loss
header those are different sensors. The first candidate the installation has
wins.
"""

from __future__ import annotations

from dataclasses import dataclass

from .const import CIRCUITS, SOURCE_CLOUD, SOURCE_EMSESP, SOURCE_HUSDATA

SENSOR = "sensor"
BINARY = "binary_sensor"
NUMBER = "number"
SELECT = "select"
SWITCH = "switch"

#: What a role is for, which decides where the page puts it.
GROUP_TEMPS = "temperatures"
GROUP_COMPRESSOR = "compressor"
GROUP_ENERGY = "energy"
GROUP_HEATING = "heating"
GROUP_HOTWATER = "hotwater"
GROUP_STATUS = "status"


@dataclass(frozen=True)
class Role:
    id: str
    sv: str
    en: str
    platform: str
    group: str
    unit: str | None = None
    device_class: str | None = None
    state_class: str | None = None
    icon: str | None = None
    #: Shown on the page's overview.
    overview: bool = False
    circuit: str | None = None


def _r(*args, **kwargs) -> Role:
    return Role(*args, **kwargs)


T = {"unit": "°C", "device_class": "temperature", "state_class": "measurement"}
KWH = {"unit": "kWh", "device_class": "energy", "state_class": "total_increasing"}

ROLES: dict[str, Role] = {
    role.id: role
    for role in (
        _r("outdoor_temp", "Utetemperatur", "Outdoor temperature", SENSOR, GROUP_TEMPS, overview=True, **T),
        _r("outdoor_temp_damped", "Utetemp., dämpad", "Outdoor temp., damped", SENSOR, GROUP_TEMPS, **T),
        _r("supply_temp", "Framledning", "Supply temperature", SENSOR, GROUP_TEMPS, overview=True, **T),
        _r("return_temp", "Retur", "Return temperature", SENSOR, GROUP_TEMPS, overview=True, **T),
        _r("supply_target", "Framledning, börvärde", "Supply setpoint", SENSOR, GROUP_TEMPS, **T),
        _r("brine_in", "Köldbärare in", "Brine in", SENSOR, GROUP_TEMPS, overview=True, **T),
        _r("brine_out", "Köldbärare ut", "Brine out", SENSOR, GROUP_TEMPS, overview=True, **T),
        _r("hot_gas_temp", "Hetgas", "Hot gas", SENSOR, GROUP_COMPRESSOR, **T),
        _r("dhw_temp", "Varmvatten", "Hot water", SENSOR, GROUP_HOTWATER, overview=True, **T),
        _r("dhw_temp_top", "Varmvatten, topp", "Hot water, top", SENSOR, GROUP_HOTWATER, **T),
        _r("room_temp", "Rumstemperatur", "Room temperature", SENSOR, GROUP_TEMPS, overview=True, **T),
        _r("compressor_on", "Kompressor", "Compressor", BINARY, GROUP_COMPRESSOR, device_class="running", overview=True),
        _r("compressor_activity", "Driftläge", "Operating state", SENSOR, GROUP_STATUS, device_class="enum", icon="mdi:heat-pump", overview=True),
        _r("compressor_speed", "Kompressor, varvtal", "Compressor speed", SENSOR, GROUP_COMPRESSOR, unit="%", state_class="measurement", icon="mdi:speedometer"),
        _r("compressor_power", "Kompressor, eleffekt", "Compressor, electric power", SENSOR, GROUP_COMPRESSOR, unit="W", device_class="power", state_class="measurement", overview=True),
        _r("heat_output", "Avgiven effekt", "Heat output", SENSOR, GROUP_COMPRESSOR, unit="kW", device_class="power", state_class="measurement"),
        _r("compressor_starts", "Kompressorstarter", "Compressor starts", SENSOR, GROUP_COMPRESSOR, state_class="total_increasing", icon="mdi:counter"),
        _r("compressor_hours", "Kompressor, drifttid", "Compressor, run time", SENSOR, GROUP_COMPRESSOR, unit="h", device_class="duration", state_class="total_increasing"),
        _r("aux_heater_level", "Tillsats, nivå", "Aux heater, level", SENSOR, GROUP_COMPRESSOR, unit="%", state_class="measurement", icon="mdi:radiator", overview=True),
        _r("brine_pump_speed", "Köldbärarpump", "Brine pump", SENSOR, GROUP_COMPRESSOR, unit="%", state_class="measurement", icon="mdi:pump"),
        _r("circ_pump_speed", "Laddpump", "Charge pump", SENSOR, GROUP_COMPRESSOR, unit="%", state_class="measurement", icon="mdi:pump"),
        _r("energy_in_total", "Total förbrukning", "Total consumption", SENSOR, GROUP_ENERGY, overview=True, **KWH),
        _r("energy_out_total", "Total produktion", "Total production", SENSOR, GROUP_ENERGY, overview=True, **KWH),
        _r("energy_in_heating", "Förbrukning, värme", "Consumption, heating", SENSOR, GROUP_ENERGY, **KWH),
        _r("energy_in_dhw", "Förbrukning, varmvatten", "Consumption, hot water", SENSOR, GROUP_ENERGY, **KWH),
        _r("energy_out_heating", "Produktion, värme", "Production, heating", SENSOR, GROUP_ENERGY, **KWH),
        _r("energy_out_dhw", "Produktion, varmvatten", "Production, hot water", SENSOR, GROUP_ENERGY, **KWH),
        _r("energy_aux_total", "Tillsats, förbrukning", "Aux heater, consumption", SENSOR, GROUP_ENERGY, **KWH),
        _r("alarm", "Larm", "Alarm", SENSOR, GROUP_STATUS, icon="mdi:alert-circle-outline", overview=True),
        _r("controller_alarm", "Larm, styrenhet", "Alarm, controller", SENSOR, GROUP_STATUS, icon="mdi:alert-circle-outline"),
        # Hot water controls
        _r("dhw_mode", "Varmvattenläge", "Hot water mode", SELECT, GROUP_HOTWATER, icon="mdi:water-boiler"),
        _r("dhw_boost", "Varmvattenboost", "Hot water boost", SWITCH, GROUP_HOTWATER, icon="mdi:water-plus"),
        _r("dhw_boost_temp", "Boost, temperatur", "Boost temperature", NUMBER, GROUP_HOTWATER, unit="°C", device_class="temperature"),
        _r("dhw_setpoint", "Varmvatten, börvärde", "Hot water setpoint", NUMBER, GROUP_HOTWATER, unit="°C", device_class="temperature"),
        _r("dhw_charging", "Varmvattenladdning", "Hot water charging", BINARY, GROUP_HOTWATER, device_class="running"),
        _r("silent_mode", "Tyst läge", "Silent mode", SELECT, GROUP_STATUS, icon="mdi:volume-off"),
        _r("aux_heater_blocked", "Tillsats spärrad", "Aux heater blocked", SWITCH, GROUP_HEATING, icon="mdi:radiator-off"),
        _r("heating_off", "Värme av", "Heating off", SWITCH, GROUP_HEATING, icon="mdi:radiator-off"),
    )
}

#: Per heating circuit: the values the thermostat and the heating mode use.
CIRCUIT_ROLES: dict[str, tuple[str, str, str, str, dict]] = {
    # suffix: (sv, en, platform, group, extra)
    "room_setpoint": ("Rumsbörvärde", "Room setpoint", NUMBER, GROUP_HEATING, {"unit": "°C", "device_class": "temperature"}),
    "room_temp": ("Rumstemperatur", "Room temperature", SENSOR, GROUP_TEMPS, T),
    "target_flow": ("Beräknad framledning", "Calculated supply", SENSOR, GROUP_HEATING, T),
    "flow_temp": ("Framledning", "Supply temperature", SENSOR, GROUP_TEMPS, T),
    "offset": ("Kurvförskjutning", "Curve offset", NUMBER, GROUP_HEATING, {"unit": "°C"}),
    "mode": ("Driftsätt", "Operating mode", SELECT, GROUP_HEATING, {"icon": "mdi:thermostat"}),
    "comfort_temp": ("Komforttemperatur", "Comfort temperature", NUMBER, GROUP_HEATING, {"unit": "°C", "device_class": "temperature"}),
    "eco_temp": ("Sänkt temperatur", "Eco temperature", NUMBER, GROUP_HEATING, {"unit": "°C", "device_class": "temperature"}),
    "design_temp": ("Dimensionerande framledning", "Design supply temp.", NUMBER, GROUP_HEATING, {"unit": "°C", "device_class": "temperature"}),
    "max_flow": ("Max framledning", "Max supply temp.", NUMBER, GROUP_HEATING, {"unit": "°C", "device_class": "temperature"}),
    "min_flow": ("Min framledning", "Min supply temp.", NUMBER, GROUP_HEATING, {"unit": "°C", "device_class": "temperature"}),
    "summer_mode": ("Sommarläge", "Summer mode", SELECT, GROUP_HEATING, {"icon": "mdi:weather-sunny"}),
    "pump": ("Cirkulationspump", "Circulation pump", BINARY, GROUP_HEATING, {"device_class": "running"}),
}

for _hc in CIRCUITS:
    _n = _hc[2:]
    for _suffix, (_sv, _en, _platform, _group, _extra) in CIRCUIT_ROLES.items():
        _id = f"{_hc}_{_suffix}"
        ROLES[_id] = Role(
            _id,
            f"{_sv}, krets {_n}",
            f"{_en}, circuit {_n}",
            _platform,
            _group,
            unit=_extra.get("unit"),
            device_class=_extra.get("device_class"),
            state_class=_extra.get("state_class"),
            icon=_extra.get("icon"),
            circuit=_hc,
        )

#: Candidates per role and source: (device, key) in order of preference.
Candidates = tuple[tuple[str, str], ...]

EMSESP: dict[str, Candidates] = {
    "outdoor_temp": (("boiler", "outdoortemp"),),
    "outdoor_temp_damped": (("thermostat", "dampedoutdoortemp"),),
    "supply_temp": (("boiler", "hptc1"), ("boiler", "curflowtemp")),
    "return_temp": (("boiler", "hptc0"), ("boiler", "rettemp")),
    "supply_target": (("boiler", "selflowtemp"),),
    "brine_in": (("boiler", "hpbrinein"),),
    "brine_out": (("boiler", "hpbrineout"),),
    "hot_gas_temp": (("boiler", "hptr6"),),
    "dhw_temp": (("boiler", "dhw.curtemp"),),
    "dhw_temp_top": (("boiler", "dhw.curtemp2"),),
    "compressor_on": (("boiler", "hpcompon"),),
    "compressor_activity": (("boiler", "hpactivity"),),
    "compressor_speed": (("boiler", "hpcompspd"),),
    "compressor_power": (("boiler", "hpcurrpower"),),
    "heat_output": (("boiler", "hppower"),),
    "compressor_starts": (("boiler", "totalcompstarts"),),
    "aux_heater_level": (("boiler", "auxheaterlevel"),),
    "brine_pump_speed": (("boiler", "hpbrinepumpspd"),),
    "circ_pump_speed": (("boiler", "hpcircspd"),),
    "energy_in_total": (("boiler", "nrgconstotal"),),
    "energy_out_total": (("boiler", "nrgsupptotal"),),
    "energy_in_heating": (("boiler", "nrgconscompheating"),),
    "energy_in_dhw": (("boiler", "dhw.nrgconscomp"),),
    "energy_out_heating": (("boiler", "nrgsuppheating"),),
    "energy_out_dhw": (("boiler", "dhw.nrgsupp"),),
    "energy_aux_total": (("boiler", "auxelecheatnrgconstotal"),),
    "alarm": (("boiler", "lastcode"),),
    "controller_alarm": (("thermostat", "lastcode"),),
    "dhw_mode": (("thermostat", "dhw.mode"), ("boiler", "dhw.comfort1"), ("boiler", "dhw.comfort")),
    # The controller's "extra hot water" starts a one-time charge and runs it
    # for dhw.chargeduration; the boiler's own flag is the fallback. EMS
    # Steward charged through the thermostat's on the Geo 608C this was built on.
    "dhw_boost": (("thermostat", "dhw.charge"), ("boiler", "dhw.onetime")),
    "dhw_boost_temp": (("boiler", "dhw.seltempsingle"),),
    "dhw_setpoint": (("boiler", "dhw.seltemp"),),
    "dhw_charging": (("boiler", "dhw.charging"),),
    "silent_mode": (("boiler", "silentmode"),),
    "aux_heater_blocked": (("boiler", "auxheateroff"),),
    "heating_off": (("boiler", "heatingoff"),),
}
for _hc in CIRCUITS:
    EMSESP.update(
        {
            f"{_hc}_room_setpoint": (("thermostat", f"{_hc}.seltemp"),),
            f"{_hc}_room_temp": (("thermostat", f"{_hc}.currtemp"),),
            f"{_hc}_target_flow": (("thermostat", f"{_hc}.targetflowtemp"),),
            f"{_hc}_flow_temp": (("mixer", f"{_hc}.flowtemphc"),),
            f"{_hc}_offset": (("thermostat", f"{_hc}.offsettemp"),),
            f"{_hc}_mode": (("thermostat", f"{_hc}.mode"),),
            f"{_hc}_comfort_temp": (("thermostat", f"{_hc}.comforttemp"),),
            f"{_hc}_eco_temp": (("thermostat", f"{_hc}.ecotemp"),),
            f"{_hc}_design_temp": (("thermostat", f"{_hc}.designtemp"),),
            f"{_hc}_max_flow": (("thermostat", f"{_hc}.maxflowtemp"),),
            f"{_hc}_min_flow": (("thermostat", f"{_hc}.minflowtemp"),),
            f"{_hc}_summer_mode": (("thermostat", f"{_hc}.summersetmode"),),
            f"{_hc}_pump": (("mixer", f"{_hc}.pumpstatus"),),
        }
    )

#: Bosch's cloud (POINTT) paths behind a K30/K40, device "heatpump".
_HP = "heatpump"
CLOUD: dict[str, Candidates] = {
    "outdoor_temp": ((_HP, "/system/sensors/temperatures/outdoor_t1"),),
    "supply_temp": ((_HP, "/heatSources/actualSupplyTemperature"),),
    "return_temp": ((_HP, "/heatSources/returnTemperature"),),
    "brine_in": ((_HP, "/heatSources/hs1/brineCircuit/collectorInflowTemp"),),
    "brine_out": ((_HP, "/heatSources/hs1/brineCircuit/collectorOutflowTemp"),),
    "compressor_activity": ((_HP, "/heatSources/compressor/status"),),
    "compressor_speed": ((_HP, "/heatSources/actualModulation"),),
    "compressor_starts": ((_HP, "/heatSources/numberOfStarts"),),
    "energy_in_total": ((_HP, "/heatSources/emon/totalConsumption#input"),),
    "energy_out_total": ((_HP, "/heatSources/emon/totalConsumption#outputProduced"),),
    "energy_in_heating": ((_HP, "/heatSources/emon/chConsumption#compressor"),),
    "energy_in_dhw": ((_HP, "/heatSources/emon/dhwConsumption#compressor"),),
    "energy_out_heating": ((_HP, "/heatSources/emon/chConsumption#outputProduced"),),
    "energy_out_dhw": ((_HP, "/heatSources/emon/dhwConsumption#outputProduced"),),
    "energy_aux_total": ((_HP, "/heatSources/emon/totalConsumption#eheater"),),
    "alarm": ((_HP, "/notifications"),),
    "dhw_temp": ((_HP, "/dhwCircuits/dhw1/actualTemp"),),
    "dhw_mode": ((_HP, "/dhwCircuits/dhw1/operationMode"),),
    "dhw_boost": ((_HP, "/dhwCircuits/dhw1/charge"),),
    "dhw_boost_temp": ((_HP, "/dhwCircuits/dhw1/singleChargeSetpoint"),),
    "dhw_setpoint": ((_HP, "/dhwCircuits/dhw1/currentSetpoint"),),
}
for _hc in CIRCUITS:
    CLOUD.update(
        {
            f"{_hc}_room_setpoint": ((_HP, f"/heatingCircuits/{_hc}/manualRoomSetpoint"),),
            f"{_hc}_room_temp": ((_HP, f"/heatingCircuits/{_hc}/roomtemperature"),),
            f"{_hc}_target_flow": ((_HP, f"/heatingCircuits/{_hc}/supplyTemperatureSetpoint"),),
            f"{_hc}_flow_temp": ((_HP, f"/heatingCircuits/{_hc}/actualSupplyTemp"),),
            f"{_hc}_mode": ((_HP, f"/heatingCircuits/{_hc}/operationMode"),),
        }
    )

#: Husdata's variable IDs (husdata.py), the same across IVT's controllers
#: where the controller has the value at all. "5C54+5C57" is husdata.py's sum
#: of compressor and aux heater consumption, which EMS reports as one counter.
HUSDATA: dict[str, Candidates] = {
    "outdoor_temp": ((_HP, "0007"),),
    "supply_temp": ((_HP, "0004"),),
    "return_temp": ((_HP, "0003"),),
    "brine_in": ((_HP, "0005"),),
    "brine_out": ((_HP, "0006"),),
    "hot_gas_temp": ((_HP, "000B"),),
    "dhw_temp": ((_HP, "000A"), (_HP, "0009")),
    "dhw_temp_top": ((_HP, "0009"),),
    "compressor_on": ((_HP, "1A01"),),
    "compressor_speed": ((_HP, "3108"), (_HP, "2108")),
    "compressor_power": ((_HP, "C130"),),
    "aux_heater_level": ((_HP, "3104"),),
    "brine_pump_speed": ((_HP, "3110"),),
    "circ_pump_speed": ((_HP, "3109"),),
    "compressor_starts": ((_HP, "2C61"),),
    "compressor_hours": ((_HP, "6C60"),),
    "energy_in_total": ((_HP, "5C54+5C57"),),
    "energy_out_total": ((_HP, "5C51"),),
    "energy_in_heating": ((_HP, "5C55"),),
    "energy_in_dhw": ((_HP, "5C56"),),
    "energy_out_heating": ((_HP, "5C52"),),
    "energy_out_dhw": ((_HP, "5C53"),),
    "energy_aux_total": ((_HP, "5C57"),),
    "dhw_boost": ((_HP, "1231"),),
    "dhw_setpoint": ((_HP, "0111"),),
    "hc1_room_setpoint": ((_HP, "0203"),),
    "hc1_room_temp": ((_HP, "0008"),),
    "hc1_target_flow": ((_HP, "0107"),),
    "hc1_flow_temp": ((_HP, "0002"),),
    "hc2_room_setpoint": ((_HP, "0220"),),
    "hc2_room_temp": ((_HP, "0021"),),
    "hc2_target_flow": ((_HP, "0120"),),
    "hc2_flow_temp": ((_HP, "0020"),),
}

SOURCE_ROLES: dict[str, dict[str, Candidates]] = {
    SOURCE_EMSESP: EMSESP,
    SOURCE_HUSDATA: HUSDATA,
    SOURCE_CLOUD: CLOUD,
}


def role_name(role: Role, language: str) -> str:
    return role.sv if language == "sv" else role.en
