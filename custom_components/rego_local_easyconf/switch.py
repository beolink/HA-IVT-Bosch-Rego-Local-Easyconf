"""Switches: hot water boost and other on/off roles, and a source's own on/off points."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity

from .entity import PointEntity, RoleEntity, points_for, roles_for, switch_on_new_defaults
from .model import to_bool


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = entry.runtime_data
    language = coordinator.language
    entities: list = [
        RoleSwitch(coordinator, role, language)
        for role in roles_for(coordinator, "switch")
        if coordinator.writable_role(role.id)
    ]
    entities.extend(PointSwitch(coordinator, p, language) for p in points_for(coordinator, "switch"))
    switch_on_new_defaults(coordinator, "switch", entities)
    async_add_entities(entities)


class RoleSwitch(RoleEntity, SwitchEntity):
    @property
    def is_on(self) -> bool | None:
        return to_bool(self.raw_value)

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_write_role(self.role.id, True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_write_role(self.role.id, False)


class PointSwitch(PointEntity, SwitchEntity):
    @property
    def is_on(self) -> bool | None:
        return to_bool(self.raw_value)

    async def async_turn_on(self, **kwargs) -> None:
        await self.coordinator.async_write_point(self.point, True)

    async def async_turn_off(self, **kwargs) -> None:
        await self.coordinator.async_write_point(self.point, False)
