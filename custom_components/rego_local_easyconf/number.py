"""Numbers: writable setpoints, from a role or a source's own point."""

from __future__ import annotations

from homeassistant.components.number import NumberEntity, NumberMode

from .entity import PointEntity, RoleEntity, points_for, roles_for, switch_on_new_defaults
from .model import Point
from .roles import Role


def _limits(point: Point) -> tuple[float, float, float]:
    low = point.minimum if point.minimum is not None else -100.0
    high = point.maximum if point.maximum is not None else 100.0
    # EMS-ESP gives the data type's range for many setpoints (0..254 °C); a
    # temperature setpoint past 90 °C is never meant, and a slider that wide
    # cannot be aimed.
    if point.unit == "°C" and high > 90:
        high = 90.0
    if point.unit == "°C" and low < -40:
        low = -40.0
    return float(low), float(high), float(point.step or 1.0)


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    coordinator = entry.runtime_data
    language = coordinator.language
    entities: list = [
        RoleNumber(coordinator, role, language)
        for role in roles_for(coordinator, "number")
        if coordinator.writable_role(role.id)
    ]
    entities.extend(PointNumber(coordinator, p, language) for p in points_for(coordinator, "number"))
    switch_on_new_defaults(coordinator, "number", entities)
    async_add_entities(entities)


class RoleNumber(RoleEntity, NumberEntity):
    def __init__(self, coordinator, role: Role, language: str) -> None:
        super().__init__(coordinator, role, language)
        writable = next(p for p in coordinator.bindings[role.id].candidates if p.writable)
        low, high, step = _limits(writable)
        self._attr_native_min_value = low
        self._attr_native_max_value = high
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = role.unit or writable.unit
        self._attr_mode = NumberMode.BOX if high - low > 60 else NumberMode.SLIDER

    @property
    def native_value(self) -> float | None:
        value = self.raw_value
        return None if value is None else float(value)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_write_role(self.role.id, value)


class PointNumber(PointEntity, NumberEntity):
    def __init__(self, coordinator, point: Point, language: str) -> None:
        super().__init__(coordinator, point, language)
        low, high, step = _limits(point)
        self._attr_native_min_value = low
        self._attr_native_max_value = high
        self._attr_native_step = step
        self._attr_native_unit_of_measurement = point.unit
        self._attr_mode = NumberMode.BOX if high - low > 60 else NumberMode.SLIDER

    @property
    def native_value(self) -> float | None:
        value = self.raw_value
        return None if value is None else float(value)

    async def async_set_native_value(self, value: float) -> None:
        await self.coordinator.async_write_point(self.point, value)
