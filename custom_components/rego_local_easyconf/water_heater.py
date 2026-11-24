"""The hot water as a water heater: its temperature, its mode and its boost.

The current temperature is the cylinder sensor the pump charges by; the
target is the hot water setpoint; the operation modes are the controller's own
hot water modes (Rego 3000: off, eco+, eco, comfort, auto), shown in the
installation's language. "Boost" is one more operation: it starts the same
one-time charge as the hot water boost switch, and choosing any other mode
ends it.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.water_heater import (
    WaterHeaterEntity,
    WaterHeaterEntityFeature,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature

from . import words
from .entity import RegoEntity, pump_device_info
from .explanations import explain_role
from .model import to_bool

BOOST = "boost"


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = entry.runtime_data
    if coordinator.has_role("dhw_temp") and (
        coordinator.writable_role("dhw_setpoint")
        or coordinator.writable_role("dhw_mode")
        or coordinator.writable_role("dhw_boost")
    ):
        async_add_entities([HotWater(coordinator, coordinator.language)])


class HotWater(RegoEntity, WaterHeaterEntity):
    # Home Assistant 2026.11 renamed the temperature members native_*; the old
    # names stop working in 2027.11. Both are given, as in the NIBE
    # integration: 2026.11+ is served the native ones without a warning, older
    # releases the old ones.
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_temperature_unit = UnitOfTemperature.CELSIUS

    def __init__(self, coordinator, language: str) -> None:
        super().__init__(coordinator, language)
        self._attr_name = "Varmvatten" if language == "sv" else "Hot water"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-water_heater"
        self._attr_device_info = pump_device_info(coordinator)
        features = WaterHeaterEntityFeature(0)
        if coordinator.writable_role("dhw_setpoint"):
            features |= WaterHeaterEntityFeature.TARGET_TEMPERATURE
            point = next(p for p in coordinator.bindings["dhw_setpoint"].candidates if p.writable)
            self._attr_min_temp = max(20.0, point.minimum or 20.0)
            self._attr_max_temp = min(70.0, point.maximum or 70.0)
        self._map: dict[str, str] = {}
        if coordinator.writable_role("dhw_mode"):
            point = next(p for p in coordinator.bindings["dhw_mode"].candidates if p.writable)
            self._map = words.options(point.options, language)
        self._boost = coordinator.writable_role("dhw_boost")
        operations = list(self._map) + ([BOOST] if self._boost else [])
        if operations:
            features |= WaterHeaterEntityFeature.OPERATION_MODE
            self._attr_operation_list = operations
        self._attr_supported_features = features
        self._description = explain_role("dhw_mode", language)

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.role_value("dhw_temp") is not None

    @property
    def native_current_temperature(self) -> float | None:
        value = self.coordinator.role_value("dhw_temp")
        return None if value is None else float(value)

    current_temperature = native_current_temperature

    @property
    def native_target_temperature(self) -> float | None:
        value = self.coordinator.role_value("dhw_setpoint")
        return None if value is None else float(value)

    target_temperature = native_target_temperature

    @property
    def current_operation(self) -> str | None:
        if self._boost and to_bool(self.coordinator.role_value("dhw_boost")):
            return BOOST
        raw = self.coordinator.role_value("dhw_mode")
        for shown, value in self._map.items():
            if value == raw:
                return shown
        return None

    async def async_set_temperature(self, **kwargs: Any) -> None:
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is not None:
            await self.coordinator.async_write_role("dhw_setpoint", float(temperature))

    async def async_set_operation_mode(self, operation_mode: str) -> None:
        if operation_mode == BOOST:
            await self.coordinator.async_write_role("dhw_boost", True)
            return
        if self._boost and to_bool(self.coordinator.role_value("dhw_boost")):
            await self.coordinator.async_write_role("dhw_boost", False)
        await self.coordinator.async_write_role("dhw_mode", self._map[operation_mode])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "description": self._description,
            "top_temperature": self.coordinator.role_value("dhw_temp_top"),
            "boost_temperature": self.coordinator.role_value("dhw_boost_temp"),
            "charging": self.coordinator.role_value("dhw_charging"),
        }
