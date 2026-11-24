"""Sensors: measured roles, a source's own read-only values, the alarm and the COP."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)

from . import faults, words
from .entity import (
    PointEntity,
    RegoEntity,
    RoleEntity,
    points_for,
    pump_device_info,
    roles_for,
    switch_on_new_defaults,
)
from .explanations import explain_role
from .model import ENUM, NUMBER, TEXT, Point

#: Units each device class accepts; anything else is shown without a class.
UNITS = {
    "temperature": {"°C", "K"},
    "power": {"W", "kW"},
    "energy": {"kWh", "Wh", "MWh"},
    "duration": {"s", "min", "h", "d"},
    "pressure": {"bar", "mbar", "kPa", "Pa"},
    "voltage": {"V", "mV"},
    "current": {"A", "mA"},
    "humidity": {"%"},
}
#: EMS-ESP uses "K" for temperature differences; Home Assistant's temperature
#: class wants a temperature.
DIFFERENCE_UNITS = {"K", "K*min"}
STATE_CLASSES = {"measurement", "total", "total_increasing"}

ALARM_ROLES = {"alarm", "controller_alarm"}


def _device_class(device_class: str | None, unit: str | None) -> SensorDeviceClass | None:
    if not device_class or unit in DIFFERENCE_UNITS:
        return None
    allowed = UNITS.get(device_class)
    if allowed is None or unit not in allowed:
        return None
    try:
        return SensorDeviceClass(device_class)
    except ValueError:
        return None


def _state_class(state_class: str | None, kind: str) -> SensorStateClass | None:
    if kind != NUMBER or state_class not in STATE_CLASSES:
        return None
    return SensorStateClass(state_class)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = entry.runtime_data
    language = coordinator.language
    entities: list = []
    for role in roles_for(coordinator, "sensor"):
        if role.id in ALARM_ROLES:
            entities.append(AlarmSensor(coordinator, role, language))
        else:
            entities.append(RoleSensor(coordinator, role, language))
    entities.extend(PointSensor(coordinator, p, language) for p in points_for(coordinator, "sensor"))
    if coordinator.has_role("energy_in_total") and coordinator.has_role("energy_out_total"):
        entities.extend(CopSensor(coordinator, span, language) for span in ("day", "year", "lifetime"))
    switch_on_new_defaults(coordinator, "sensor", entities)
    async_add_entities(entities)


class RoleSensor(RoleEntity, SensorEntity):
    def __init__(self, coordinator, role, language) -> None:
        super().__init__(coordinator, role, language)
        point = self.point
        unit = role.unit or point.unit
        self._attr_native_unit_of_measurement = unit
        self._enum = point.kind == ENUM or role.device_class == "enum"
        if self._enum:
            # Every candidate's options: EMS-ESP says "hot water" where the
            # cloud says "dhw", and either may be the one answering.
            merged: dict[str, str] = {}
            for candidate in coordinator.bindings[role.id].candidates:
                merged.update(words.options(candidate.options, language))
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = list(merged) or None
            if not self._attr_options:
                self._attr_device_class = None
                self._enum = False
        else:
            self._attr_device_class = _device_class(role.device_class or point.device_class, unit)
            self._attr_state_class = _state_class(role.state_class or point.state_class, NUMBER)
        if role.state_class == "total_increasing" and unit is None:
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING

    @property
    def native_value(self) -> Any:
        value = self.raw_value
        if value is None:
            return None
        if self._enum:
            shown = words.show(str(value), self._language)
            return shown if shown in (self._attr_options or ()) else None
        if isinstance(value, bool):
            return int(value)
        return value


class AlarmSensor(RoleEntity, SensorEntity):
    """The latest fault, in words, with its parts as attributes."""

    @property
    def available(self) -> bool:
        return super(RoleEntity, self).available and self.coordinator.role_point(self.role.id) is not None

    @property
    def native_value(self) -> str:
        return faults.text(faults.parse(self.raw_value), self._language)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attributes = super().extra_state_attributes
        fault = faults.parse(self.raw_value)
        attributes.update(
            alarm_code=fault.code if fault else 0,
            display_code=fault.display if fault else None,
            cause_code=fault.cause if fault else None,
            active=fault.active if fault else False,
            started=fault.start.isoformat() if fault and fault.start else None,
            ended=fault.end.isoformat() if fault and fault.end else None,
            raw=self.raw_value,
        )
        row = faults.row_for(fault)
        if row:
            sv = self._language == "sv"
            attributes["category"] = row.get("category")
            detail = row.get("sv_detail" if sv else "en_detail")
            if detail:
                attributes["detail"] = detail
            attributes["text_status"] = row.get("sv_status" if sv else "en_status")
        return attributes


class PointSensor(PointEntity, SensorEntity):
    def __init__(self, coordinator, point: Point, language) -> None:
        super().__init__(coordinator, point, language)
        self._attr_native_unit_of_measurement = point.unit if point.kind == NUMBER else None
        if point.kind == NUMBER:
            self._attr_device_class = _device_class(point.device_class, point.unit)
            self._attr_state_class = _state_class(point.state_class, point.kind)
        elif point.kind == ENUM and point.options:
            self._attr_device_class = SensorDeviceClass.ENUM
            self._attr_options = list(words.options(point.options, language))

    @property
    def native_value(self) -> Any:
        value = self.raw_value
        if value is None:
            return None
        if self.point.kind == ENUM:
            shown = words.show(str(value), self._language)
            if self._attr_options and shown not in self._attr_options:
                return None
            return shown
        if self.point.kind == TEXT:
            return str(value)[:255]
        return value


class CopSensor(RegoEntity, SensorEntity):
    """Coefficient of performance over a day, a rolling year or the lifetime."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_icon = "mdi:heat-pump-outline"
    _attr_suggested_display_precision = 2

    NAMES = {
        "day": ("COP, dygn", "COP, day"),
        "year": ("COP, år", "COP, year"),
        "lifetime": ("COP, livstid", "COP, lifetime"),
    }

    def __init__(self, coordinator, span: str, language) -> None:
        super().__init__(coordinator, language)
        self.span = span
        self._attr_name = self.NAMES[span][0 if language == "sv" else 1]
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-cop-{span}"
        self._attr_translation_key = f"cop_{span}"
        self._attr_device_info = pump_device_info(coordinator)
        self._description = explain_role(f"cop_{span}", language)

    def _result(self):
        tracker = self.coordinator.cop
        out, used = self.coordinator.energy_out, self.coordinator.energy_in
        if tracker is None:
            return None
        if self.span == "day":
            return tracker.result_day(out, used)
        if self.span == "year":
            return tracker.result(out, used)
        return tracker.result_lifetime(out, used)

    @property
    def native_value(self) -> float | None:
        result = self._result()
        return None if result is None else result.value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        result = self._result()
        attributes: dict[str, Any] = {
            "description": self._description,
            "span": self.span,
            "role": f"cop_{self.span}",
            "group": "energy",
            "basis": None,
        }
        if result is not None:
            attributes.update(result.as_attributes(self._language))
        return attributes

