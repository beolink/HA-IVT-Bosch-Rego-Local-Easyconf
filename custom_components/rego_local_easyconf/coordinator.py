"""One heat pump, read through every source it has, best first.

The coordinator holds the installation's sources in priority order (EMS-ESP,
Husdata, a Bosch gateway on the LAN, the cloud), polls each as often as it
should be polled, and keeps one dictionary of values keyed by point. Which
source answers for a role is merge.py's business; the coordinator only keeps
track of which sources answered their last poll.

A source that stops answering does not take the installation down: its
values go stale, the roles it fed fall to the next source that has them, and
only when every source is silent does the update fail.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import timedelta
import logging
import time
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import DOMAIN, SOURCE_PRIORITY
from .merge import Binding, bind, first_value, primary_point, priority, write_target
from .model import Point, Source, SourceError, SourceInfo, Value, WriteRefused

_LOGGER = logging.getLogger(__name__)


@dataclass
class SourceState:
    """One source of the installation and how it is doing."""

    kind: str
    client: Source
    info: SourceInfo | None
    points: dict[str, Point]
    interval: float
    healthy: bool = False
    next_due: float = 0.0
    last_ok: float | None = None
    last_error: str | None = None
    failures: int = 0
    #: True when the points came from the cache because the source was away at start.
    from_cache: bool = False
    extra: dict[str, Any] = field(default_factory=dict)


class RegoCoordinator(DataUpdateCoordinator[dict[str, Value]]):
    """Values of every source, and the roles bound to them."""

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        sources: list[SourceState],
        scan_interval: int,
    ) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=scan_interval),
            config_entry=entry,
        )
        self.sources = sorted(sources, key=lambda s: priority(s.kind))
        self.values: dict[str, Value] = {}
        self.bindings: dict[str, Binding] = {}
        self.own: list[Point] = []
        #: Own points with an enabled entity; roles are always read.
        self._subscribers: dict[str, int] = {}
        self._write_lock = asyncio.Lock()
        self.heating_mode = None  # heating_mode.Controller
        self.cop = None  # cop.CopTracker
        self.read_failures = 0
        self.rebind()

    # --- structure ---------------------------------------------------------

    def rebind(self) -> None:
        self.bindings, self.own = bind({s.kind: list(s.points.values()) for s in self.sources})

    @property
    def first_source(self) -> str | None:
        return self.sources[0].kind if self.sources else None

    def source(self, kind: str) -> SourceState | None:
        return next((s for s in self.sources if s.kind == kind), None)

    @property
    def healthy(self) -> dict[str, bool]:
        return {s.kind: s.healthy for s in self.sources}

    @property
    def can_write(self) -> dict[str, bool]:
        """Sources that answer and hold what they need to write."""
        return {s.kind: s.healthy and bool(s.info is None or s.info.can_write) for s in self.sources}

    def subscribe(self, uid: str) -> None:
        self._subscribers[uid] = self._subscribers.get(uid, 0) + 1

    def unsubscribe(self, uid: str) -> None:
        count = self._subscribers.get(uid, 0) - 1
        if count <= 0:
            self._subscribers.pop(uid, None)
        else:
            self._subscribers[uid] = count

    def _wanted(self, state: SourceState) -> list[Point]:
        """What to read from a source: every role candidate, and the own points shown."""
        wanted: dict[str, Point] = {}
        for binding in self.bindings.values():
            for point in binding.candidates:
                if point.source == state.kind:
                    wanted[point.uid] = point
        for uid in self._subscribers:
            point = state.points.get(uid)
            if point is not None:
                wanted[uid] = point
        return list(wanted.values())

    # --- values --------------------------------------------------------------

    def role_value(self, role: str) -> Value:
        binding = self.bindings.get(role)
        if binding is None:
            return None
        return first_value(binding, self.values, self.healthy)[0]

    def role_point(self, role: str) -> Point | None:
        """The point a role's value currently comes from, or its best candidate."""
        binding = self.bindings.get(role)
        if binding is None:
            return None
        point = first_value(binding, self.values, self.healthy)[1]
        return point or primary_point(binding)

    def point_value(self, point: Point) -> Value:
        state = self.source(point.source)
        if state is None or not state.healthy:
            return None
        return self.values.get(point.uid)

    def has_role(self, role: str) -> bool:
        return role in self.bindings

    @property
    def energy_out(self) -> float | None:
        value = self.role_value("energy_out_total")
        return None if value is None else float(value)

    @property
    def energy_in(self) -> float | None:
        value = self.role_value("energy_in_total")
        return None if value is None else float(value)

    # --- polling -------------------------------------------------------------

    async def _async_update_data(self) -> dict[str, Value]:
        now = time.monotonic()
        for state in self.sources:
            if now < state.next_due:
                continue
            state.next_due = now + max(state.interval, state.client.min_interval) - 1
            try:
                values = await state.client.async_read(self._wanted(state))
            except SourceError as err:
                state.failures += 1
                self.read_failures += 1
                if state.healthy or state.last_error is None:
                    _LOGGER.warning("%s stopped answering: %s", state.kind, err)
                state.healthy = False
                state.last_error = str(err)
                continue
            if not state.healthy and state.last_ok is not None:
                _LOGGER.info("%s answers again", state.kind)
            state.healthy = True
            state.last_ok = time.time()
            state.last_error = None
            state.failures = 0
            self.values.update(values)
        if not any(s.healthy for s in self.sources):
            raise UpdateFailed(
                "; ".join(f"{s.kind}: {s.last_error}" for s in self.sources if s.last_error)
                or "No source answers"
            )
        if self.heating_mode is not None:
            self.heating_mode.follow()
        return dict(self.values)

    # --- writes --------------------------------------------------------------

    async def async_write_point(self, point: Point, value: Value) -> Value:
        state = self.source(point.source)
        if state is None:
            raise HomeAssistantError(f"No source {point.source}")
        async with self._write_lock:
            try:
                stored = await state.client.async_write(point, value)
            except WriteRefused as err:
                raise HomeAssistantError(str(err)) from err
            except SourceError as err:
                raise HomeAssistantError(f"{state.kind}: {err}") from err
        if stored is not None:
            if stored != value:
                _LOGGER.info("%s written %s, the pump holds %s", point.uid, value, stored)
            self.values[point.uid] = stored
        elif point.kind != "command":
            self.values[point.uid] = value
        self.async_set_updated_data(dict(self.values))
        return stored

    async def async_write_role(self, role: str, value: Value) -> Value:
        binding = self.bindings.get(role)
        if binding is None:
            raise HomeAssistantError(f"This pump has no {role}")
        # A source that answers but has no login to write with (EMS-ESP read
        # only) is passed over, so a lower one that can write (the cloud)
        # takes the write instead of it failing.
        point = write_target(binding, self.can_write)
        if point is None:
            raise HomeAssistantError(
                f"No source that answers can write {role}"
                + ("" if binding.writable else " (read only)")
            )
        return await self.async_write_point(point, value)

    def writable_role(self, role: str) -> bool:
        binding = self.bindings.get(role)
        return binding is not None and binding.writable

    def summary(self) -> dict[str, Any]:
        """For diagnostics and the page: what each source is and how it is doing."""
        return {
            s.kind: {
                "healthy": s.healthy,
                "points": len(s.points),
                "interval": s.interval,
                "last_error": s.last_error,
                "from_cache": s.from_cache,
                "info": None
                if s.info is None
                else {
                    "name": s.info.name,
                    "model": s.info.model,
                    "sw_version": s.info.sw_version,
                    "can_write": s.info.can_write,
                    "devices": [d.key for d in s.info.devices],
                },
            }
            for s in self.sources
        }


SOURCE_ORDER = SOURCE_PRIORITY
