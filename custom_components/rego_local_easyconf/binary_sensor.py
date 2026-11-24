"""Binary sensors: on/off roles, a source's own on/off values, and whether each source answers."""

from __future__ import annotations

import contextlib
from typing import Any

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.const import EntityCategory

from .const import SOURCE_LABELS
from .entity import (
    PointEntity,
    RegoEntity,
    RoleEntity,
    gateway_device_info,
    points_for,
    roles_for,
    switch_on_new_defaults,
)
from .model import to_bool


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = entry.runtime_data
    language = coordinator.language
    entities: list = [RoleBinary(coordinator, role, language) for role in roles_for(coordinator, "binary_sensor")]
    entities.extend(PointBinary(coordinator, p, language) for p in points_for(coordinator, "binary_sensor"))
    entities.extend(SourceConnected(coordinator, s.kind, language) for s in coordinator.sources)
    switch_on_new_defaults(coordinator, "binary_sensor", entities)
    async_add_entities(entities)


class RoleBinary(RoleEntity, BinarySensorEntity):
    def __init__(self, coordinator, role, language) -> None:
        super().__init__(coordinator, role, language)
        if role.device_class:
            with contextlib.suppress(ValueError):
                self._attr_device_class = BinarySensorDeviceClass(role.device_class)

    @property
    def is_on(self) -> bool | None:
        return to_bool(self.raw_value)


class PointBinary(PointEntity, BinarySensorEntity):
    @property
    def is_on(self) -> bool | None:
        return to_bool(self.raw_value)


class SourceConnected(RegoEntity, BinarySensorEntity):
    """Whether a source answered its last poll."""

    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, coordinator, kind: str, language: str) -> None:
        super().__init__(coordinator, language)
        self.kind = kind
        self._attr_name = "Ansluten" if language == "sv" else "Connected"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-{kind}-connected"
        self._attr_device_info = gateway_device_info(coordinator, kind, language)

    @property
    def available(self) -> bool:
        return True

    @property
    def is_on(self) -> bool:
        state = self.coordinator.source(self.kind)
        return bool(state and state.healthy)

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        state = self.coordinator.source(self.kind)
        base = {
            "source": self.kind,
            "label": SOURCE_LABELS.get(self.kind, {}).get(self._language, self.kind),
            "description": (
                "Om källan svarade vid senaste avläsningen. När den inte svarar tar nästa källa i ordningen över de värden den har."
                if self._language == "sv"
                else "Whether the source answered its last poll. While it does not, the next source in the order takes over the values it has."
            ),
        }
        if state is None:
            return base
        return {
            **base,
            "points": len(state.points),
            "last_error": state.last_error,
            "poll_interval_s": state.interval,
            "can_write": bool(state.info and state.info.can_write),
            "from_cache": state.from_cache,
        }
