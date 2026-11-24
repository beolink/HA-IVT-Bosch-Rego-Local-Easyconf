"""A thermostat per heating circuit, made of the circuit's roles.

Home Assistant's thermostat card, its scheduler helpers and the voice
assistants speak to ``climate`` entities. Each circuit with a writable room
setpoint gets one: the target is the room setpoint, the current temperature
the circuit's room sensor where one is fitted, the HVAC mode the circuit's own
operating mode (Rego: off / manual / auto), and the presets are the heating
mode the select also shows - the same controller, so the two never disagree.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.climate import (
    ClimateEntity,
    ClimateEntityFeature,
    HVACAction,
    HVACMode,
)
from homeassistant.const import ATTR_TEMPERATURE, UnitOfTemperature
from homeassistant.exceptions import ServiceValidationError

from .const import CIRCUITS
from .entity import RegoEntity, pump_device_info
from .explanations import explain_role
from .heating_mode import MODES

#: Rego's circuit modes as Home Assistant's.
MODE_MAP = {"off": HVACMode.OFF, "manual": HVACMode.HEAT, "auto": HVACMode.AUTO}


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = entry.runtime_data
    language = coordinator.language
    async_add_entities(
        CircuitClimate(coordinator, circuit, language)
        for circuit in CIRCUITS
        if coordinator.writable_role(f"{circuit}_room_setpoint")
    )


class CircuitClimate(RegoEntity, ClimateEntity):
    # Home Assistant 2026.11 renamed the temperature members native_*; the old
    # names stop working in 2027.11. Both are given, as in the NIBE
    # integration: 2026.11+ is served the native ones without a warning, older
    # releases the old ones.
    _attr_native_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_temperature_unit = UnitOfTemperature.CELSIUS
    _attr_target_temperature_step = 0.5
    _enable_turn_on_off_backwards_compatibility = False

    def __init__(self, coordinator, circuit: str, language: str) -> None:
        super().__init__(coordinator, language)
        self.circuit = circuit
        number = circuit[2:]
        self._attr_name = f"Värmekrets {number}" if language == "sv" else f"Heating circuit {number}"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-climate-{circuit}"
        self._attr_device_info = pump_device_info(coordinator)
        binding = coordinator.bindings[f"{circuit}_room_setpoint"]
        writable = next(p for p in binding.candidates if p.writable)
        self._attr_min_temp = max(5.0, writable.minimum if writable.minimum is not None else 5.0)
        self._attr_max_temp = min(30.0, writable.maximum if writable.maximum is not None else 30.0)
        features = ClimateEntityFeature.TARGET_TEMPERATURE
        self._mode_point = None
        mode_binding = coordinator.bindings.get(f"{circuit}_mode")
        if mode_binding is not None and mode_binding.writable:
            self._mode_point = next(p for p in mode_binding.candidates if p.writable)
        modes = []
        if self._mode_point is not None:
            modes = [MODE_MAP[o] for o in self._mode_point.options if o in MODE_MAP]
            if HVACMode.OFF in modes:
                features |= ClimateEntityFeature.TURN_OFF | ClimateEntityFeature.TURN_ON
        self._attr_hvac_modes = modes or [HVACMode.HEAT]
        if coordinator.heating_mode is not None and circuit in coordinator.heating_mode.levers:
            features |= ClimateEntityFeature.PRESET_MODE
            self._attr_preset_modes = list(MODES)
        self._attr_supported_features = features
        self._description = explain_role(f"{circuit}_room_setpoint", language)

    def _role(self, suffix: str):
        return self.coordinator.role_value(f"{self.circuit}_{suffix}")

    @property
    def available(self) -> bool:
        return super().available and self._role("room_setpoint") is not None

    @property
    def native_current_temperature(self) -> float | None:
        value = self._role("room_temp")
        return None if value is None else float(value)

    current_temperature = native_current_temperature

    @property
    def native_target_temperature(self) -> float | None:
        value = self._role("room_setpoint")
        return None if value is None else float(value)

    target_temperature = native_target_temperature

    @property
    def hvac_mode(self) -> HVACMode:
        mode = self._role("mode")
        if mode is None:
            return HVACMode.HEAT
        return MODE_MAP.get(str(mode), HVACMode.HEAT)

    @property
    def hvac_action(self) -> HVACAction | None:
        if self.hvac_mode == HVACMode.OFF:
            return HVACAction.OFF
        activity = self.coordinator.role_value("compressor_activity")
        if activity is None:
            return None
        if activity == "heating":
            return HVACAction.HEATING
        if activity == "cooling":
            return HVACAction.COOLING
        if activity == "defrost":
            return HVACAction.DEFROSTING
        return HVACAction.IDLE

    @property
    def preset_mode(self) -> str | None:
        controller = self.coordinator.heating_mode
        return controller.mode if controller is not None else None

    async def async_set_preset_mode(self, preset_mode: str) -> None:
        await self.coordinator.heating_mode.async_choose(preset_mode)

    async def async_set_temperature(self, **kwargs: Any) -> None:
        if (temperature := kwargs.get(ATTR_TEMPERATURE)) is None:
            return
        await self.coordinator.async_write_role(f"{self.circuit}_room_setpoint", float(temperature))

    async def async_set_hvac_mode(self, hvac_mode: HVACMode) -> None:
        if self._mode_point is None:
            raise ServiceValidationError("This circuit's operating mode cannot be set")
        for raw, mode in MODE_MAP.items():
            if mode == hvac_mode and raw in self._mode_point.options:
                await self.coordinator.async_write_role(f"{self.circuit}_mode", raw)
                return
        raise ServiceValidationError(f"{hvac_mode} is not offered by this circuit")

    async def async_turn_on(self) -> None:
        await self.async_set_hvac_mode(HVACMode.HEAT if HVACMode.HEAT in self.hvac_modes else HVACMode.AUTO)

    async def async_turn_off(self) -> None:
        await self.async_set_hvac_mode(HVACMode.OFF)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {
            "description": self._description,
            "circuit": self.circuit,
            "calculated_supply": self._role("target_flow"),
        }
