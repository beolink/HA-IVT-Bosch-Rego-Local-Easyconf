"""Selects: the heating mode, modes from roles, and a source's own option values."""

from __future__ import annotations

from typing import Any

from homeassistant.components.select import SelectEntity
from homeassistant.helpers.restore_state import RestoreEntity

from . import words
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
from .heating_mode import MODES
from .model import Point


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = entry.runtime_data
    language = coordinator.language
    entities: list = []
    if coordinator.heating_mode is not None:
        entities.append(HeatingModeSelect(coordinator, language))
    for role in roles_for(coordinator, "select"):
        if coordinator.writable_role(role.id) and coordinator.role_point(role.id).options:
            entities.append(RoleSelect(coordinator, role, language))
    entities.extend(PointSelect(coordinator, p, language) for p in points_for(coordinator, "select"))
    switch_on_new_defaults(coordinator, "select", entities)
    async_add_entities(entities)


class HeatingModeSelect(RegoEntity, SelectEntity, RestoreEntity):
    """blocked / eco / normal / boost, the ids an energy manager writes."""

    _attr_icon = "mdi:home-thermometer-outline"
    _attr_options = list(MODES)
    _attr_translation_key = "heating_mode"

    def __init__(self, coordinator, language: str) -> None:
        super().__init__(coordinator, language)
        self._attr_name = "Värmeläge" if language == "sv" else "Heating mode"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-heating_mode"
        self._attr_device_info = pump_device_info(coordinator)
        self._description = explain_role("heating_mode", language)

    @property
    def available(self) -> bool:
        return super().available and self.coordinator.heating_mode.available

    @property
    def current_option(self) -> str | None:
        return self.coordinator.heating_mode.mode

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.heating_mode.async_choose(option)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"description": self._description, **self.coordinator.heating_mode.attributes()}


class _OptionsMixin:
    _map: dict[str, str]

    def _setup_options(self, point: Point, language: str) -> None:
        self._map = words.options(point.options, language)
        self._attr_options = list(self._map)

    def _shown(self, value) -> str | None:
        if value is None:
            return None
        for shown, raw in self._map.items():
            if raw == str(value):
                return shown
        return None


class RoleSelect(_OptionsMixin, RoleEntity, SelectEntity):
    def __init__(self, coordinator, role, language: str) -> None:
        super().__init__(coordinator, role, language)
        writable = next(p for p in coordinator.bindings[role.id].candidates if p.writable)
        self._setup_options(writable, language)

    @property
    def current_option(self) -> str | None:
        return self._shown(self.raw_value)

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_write_role(self.role.id, self._map[option])


class PointSelect(_OptionsMixin, PointEntity, SelectEntity):
    def __init__(self, coordinator, point: Point, language: str) -> None:
        super().__init__(coordinator, point, language)
        self._setup_options(point, language)

    @property
    def current_option(self) -> str | None:
        return self._shown(self.raw_value)

    async def async_select_option(self, option: str) -> None:
        await self.coordinator.async_write_point(self.point, self._map[option])
