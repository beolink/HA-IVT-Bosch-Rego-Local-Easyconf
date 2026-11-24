"""Entities: one per role, and one per point that plays no role.

A role entity (roles.py) belongs to the heat pump and reads its value from
whichever source currently has it; its attributes say which. A point entity
belongs to the device its source sees it on - the pump, its controller, a
mixing module - and reads that one point.

Every entity carries:

* ``description`` - what the value is and what changing it does;
* ``source`` - which way the value came in (emsesp, husdata, bosch_local, cloud);
* ``source_key`` and ``source_title`` - the source's own name for it, unmodified.
"""

from __future__ import annotations

from typing import Any

from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, SOURCE_EMSESP, SOURCE_LABELS
from .coordinator import RegoCoordinator
from .explanations import explain_point, explain_role
from .merge import primary_point
from .model import BOOL, ENUM, NUMBER, TEXT, Point, Value
from .names import default_on, name_for
from .roles import ROLES, Role, role_name

#: EMS-ESP device types shown as devices of their own under the pump.
SUBDEVICE_NAMES = {
    "thermostat": ("Styrenhet", "Controller"),
    "mixer": ("Shuntgrupp", "Mixing module"),
    "solar": ("Solvärme", "Solar module"),
    "heatpump": ("Värmepumpsmodul", "Heat pump module"),
    "ventilation": ("Ventilation", "Ventilation"),
    "water": ("Varmvattenmodul", "Hot water module"),
    "pool": ("Pool", "Pool"),
    "temperaturesensor": ("Givare på gatewayn", "Gateway sensors"),
    "analogsensor": ("Analoga ingångar", "Analog inputs"),
}
#: The EMS device that is the heat pump itself.
PUMP_DEVICES = frozenset({"boiler", "heatpump"})


def pump_device_info(coordinator: RegoCoordinator) -> DeviceInfo:
    entry = coordinator.config_entry
    brand, model, sw = None, None, None
    for state in coordinator.sources:
        if state.info is None:
            continue
        for device in state.info.devices:
            if device.kind in PUMP_DEVICES or device.key == "heatpump":
                brand = brand or device.brand
                model = model or device.model
                sw = sw or device.sw_version
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        manufacturer=brand or "Bosch",
        model=model,
        sw_version=sw,
        name=entry.title,
    )


def _via(coordinator: RegoCoordinator) -> dict:
    """The link to the pump's device: by registry id where Home Assistant takes
    one (2026.8 deprecated the identifier tuple), by identifiers before."""
    if "via_device_id" in DeviceInfo.__annotations__ and getattr(coordinator, "pump_device_id", None):
        return {"via_device_id": coordinator.pump_device_id}
    return {"via_device": (DOMAIN, coordinator.config_entry.entry_id)}


def sub_device_info(coordinator: RegoCoordinator, source: str, device: str, language: str) -> DeviceInfo:
    entry = coordinator.config_entry
    state = coordinator.source(source)
    description = None
    if state is not None and state.info is not None:
        description = next((d for d in state.info.devices if d.key == device), None)
    words = SUBDEVICE_NAMES.get(device)
    label = (words[0] if language == "sv" else words[1]) if words else device
    model = description.model if description else None
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}-{source}-{device}")},
        manufacturer=(description.brand if description and description.brand else None) or "Bosch",
        model=model,
        sw_version=description.sw_version if description else None,
        name=f"{entry.title} {label.lower()}" if language == "sv" else f"{entry.title} {label}",
        **_via(coordinator),
    )


def gateway_device_info(coordinator: RegoCoordinator, source: str, language: str) -> DeviceInfo:
    entry = coordinator.config_entry
    state = coordinator.source(source)
    info = state.info if state else None
    label = SOURCE_LABELS.get(source, {}).get(language, source)
    url = None
    if info is not None and info.host and source != "cloud":
        url = info.host if info.host.startswith("http") else f"http://{info.host}"
    return DeviceInfo(
        identifiers={(DOMAIN, f"{entry.entry_id}-{source}")},
        manufacturer={"emsesp": "BBQKees / EMS-ESP", "husdata": "Husdata", "bosch_local": "Bosch", "cloud": "Bosch"}.get(source),
        model=info.model if info else None,
        sw_version=info.sw_version if info else None,
        name=label,
        configuration_url=url,
        **_via(coordinator),
    )


def device_info_for_point(coordinator: RegoCoordinator, point: Point, language: str) -> DeviceInfo:
    if point.device in PUMP_DEVICES or point.source != SOURCE_EMSESP:
        return pump_device_info(coordinator)
    return sub_device_info(coordinator, point.source, point.device, language)


class RegoEntity(CoordinatorEntity[RegoCoordinator]):
    _attr_has_entity_name = True

    def __init__(self, coordinator: RegoCoordinator, language: str) -> None:
        super().__init__(coordinator)
        self._language = language


class RoleEntity(RegoEntity):
    """A value with a meaning of its own, from the best source that has it."""

    def __init__(self, coordinator: RegoCoordinator, role: Role, language: str) -> None:
        super().__init__(coordinator, language)
        self.role = role
        self._attr_name = role_name(role, language)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-role-{role.id}"
        self._attr_device_info = pump_device_info(coordinator)
        self._attr_icon = role.icon
        # The role as translation key: the frontend's entity registry carries
        # it even while the entity is unavailable, so the page still knows
        # what the entity is.
        self._attr_translation_key = role.id
        self._description = explain_role(role.id, language)

    @property
    def point(self) -> Point:
        return self.coordinator.role_point(self.role.id) or primary_point(self.coordinator.bindings[self.role.id])

    @property
    def raw_value(self) -> Value:
        return self.coordinator.role_value(self.role.id)

    @property
    def available(self) -> bool:
        return super().available and self.raw_value is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        point = self.coordinator.role_point(self.role.id)
        binding = self.coordinator.bindings.get(self.role.id)
        attributes: dict[str, Any] = {
            "description": self._description,
            "role": self.role.id,
            "group": self.role.group,
        }
        if point is not None:
            attributes.update(
                source=point.source,
                source_key=f"{point.device}/{point.key}",
                source_title=point.title,
            )
        if binding is not None and len({p.source for p in binding.candidates}) > 1:
            attributes["sources"] = [p.uid for p in binding.candidates]
        return attributes


class PointEntity(RegoEntity):
    """One point of one source that plays no role."""

    def __init__(self, coordinator: RegoCoordinator, point: Point, language: str) -> None:
        super().__init__(coordinator, language)
        self.point = point
        self._attr_name = name_for(point, language)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}-{point.uid}"
        self._attr_device_info = device_info_for_point(coordinator, point, language)
        self._attr_entity_registry_enabled_default = default_on(
            point, first_source=point.source == coordinator.first_source
        )
        if point.writable:
            self._attr_entity_category = EntityCategory.CONFIG
        elif point.kind in (TEXT,) or point.device in ("temperaturesensor", "analogsensor"):
            self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._description = explain_point(point, language)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.coordinator.subscribe(self.point.uid)

    async def async_will_remove_from_hass(self) -> None:
        self.coordinator.unsubscribe(self.point.uid)
        await super().async_will_remove_from_hass()

    @property
    def raw_value(self) -> Value:
        return self.coordinator.point_value(self.point)

    @property
    def available(self) -> bool:
        return super().available and self.raw_value is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        attributes = {
            "description": self._description,
            "source": self.point.source,
            "source_key": f"{self.point.device}/{self.point.key}",
            "source_title": self.point.title,
        }
        if self.point.circuit:
            attributes["circuit"] = self.point.circuit
        return attributes


def platform_for_point(point: Point) -> str | None:
    if point.kind == NUMBER:
        return "number" if point.writable else "sensor"
    if point.kind == ENUM:
        return "select" if point.writable and point.options else "sensor"
    if point.kind == BOOL:
        return "switch" if point.writable else "binary_sensor"
    if point.kind == TEXT:
        return "sensor"
    return None


def roles_for(coordinator: RegoCoordinator, platform: str) -> list[Role]:
    return [ROLES[r] for r in coordinator.bindings if ROLES[r].platform == platform]


def points_for(coordinator: RegoCoordinator, platform: str) -> list[Point]:
    return [p for p in coordinator.own if platform_for_point(p) == platform]


def switch_on_new_defaults(coordinator: RegoCoordinator, platform: str, entities: list) -> None:
    """Switch on entities this integration once switched off and now wants on.

    Home Assistant reads ``entity_registry_enabled_default`` only when an entity
    is first registered; one this integration switched off is its own to switch
    on again, one the user switched off is left alone.
    """
    registry = er.async_get(coordinator.hass)
    for entity in entities:
        if not getattr(entity, "_attr_entity_registry_enabled_default", True):
            continue
        entity_id = registry.async_get_entity_id(platform, DOMAIN, entity.unique_id)
        existing = registry.async_get(entity_id) if entity_id else None
        if existing is not None and existing.disabled_by is er.RegistryEntryDisabler.INTEGRATION:
            registry.async_update_entity(entity_id, disabled_by=None)
