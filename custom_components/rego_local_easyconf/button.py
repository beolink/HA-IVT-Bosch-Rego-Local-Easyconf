"""Buttons: read every source's list of values again."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.const import EntityCategory

from .const import DOMAIN, SERVICE_RESCAN
from .entity import RegoEntity, pump_device_info


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = entry.runtime_data
    async_add_entities([RescanButton(coordinator, coordinator.language)])


class RescanButton(RegoEntity, ButtonEntity):
    _attr_entity_category = EntityCategory.CONFIG
    _attr_icon = "mdi:magnify-scan"

    def __init__(self, coordinator, language: str) -> None:
        super().__init__(coordinator, language)
        self._attr_name = "Sök om värden" if language == "sv" else "Rescan values"
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-rescan"
        self._attr_device_info = pump_device_info(coordinator)

    async def async_press(self) -> None:
        await self.hass.services.async_call(
            DOMAIN, SERVICE_RESCAN, {"entry_id": self.coordinator.config_entry.entry_id}, blocking=True
        )
