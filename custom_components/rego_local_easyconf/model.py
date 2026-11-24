"""What every source hands the rest of the integration: points, values, devices.

A *point* is one value a source can read, and maybe write: an EMS-ESP entity
such as ``hc1.seltemp`` on the thermostat, a Husdata variable ID such as
``0007``, a path in Bosch's resource tree such as
``/heatingCircuits/hc1/roomtemperature``. Each source describes its own points
from what the device itself says about them - EMS-ESP lists type, unit, range
and options for every entity it decodes - so nothing here keeps a map of a
model that could go stale.

Nothing in this module imports Home Assistant: the sources, the merge and the
heating mode are tested without it.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Protocol

NUMBER = "number"
ENUM = "enum"
BOOL = "bool"
TEXT = "text"
COMMAND = "command"
KINDS = frozenset({NUMBER, ENUM, BOOL, TEXT, COMMAND})

Value = float | int | str | bool | None


@dataclass(frozen=True)
class Point:
    """One value of one device behind one source."""

    source: str
    #: The device behind the source: "boiler", "thermostat", "mixer" on
    #: EMS-ESP, "heatpump" for the sources that see the pump as one thing.
    device: str
    #: The source's own key for the value, unique within the device.
    key: str
    #: The source's own title for it, unmodified.
    title: str
    kind: str
    unit: str | None = None
    device_class: str | None = None
    state_class: str | None = None
    writable: bool = False
    minimum: float | None = None
    maximum: float | None = None
    step: float | None = None
    options: tuple[str, ...] = ()
    #: "hc1".."hc4", "dhw", "dhw2" or None.
    circuit: str | None = None

    @property
    def uid(self) -> str:
        return f"{self.source}:{self.device}:{self.key}"


@dataclass
class DeviceDescription:
    """A device a source sees: the pump, its controller, a mixing module."""

    key: str
    name: str
    brand: str | None = None
    model: str | None = None
    sw_version: str | None = None
    serial: str | None = None
    #: The source's own id for the device on its bus (EMS-ESP: "0x08").
    address: str | None = None
    #: EMS-ESP's device type ("boiler", "thermostat", "mixer", ...).
    kind: str | None = None


@dataclass
class SourceInfo:
    """What a source says about itself when it is first reached."""

    kind: str
    #: Stable across address changes where the source offers one (a MAC
    #: address, a cloud device id); otherwise the host.
    unique_id: str
    name: str
    model: str | None = None
    sw_version: str | None = None
    host: str | None = None
    devices: list[DeviceDescription] = field(default_factory=list)
    #: Anything else worth keeping for diagnostics and the flow's summary.
    extra: dict[str, Any] = field(default_factory=dict)
    #: True when writes are possible with the credentials given.
    can_write: bool = False


class SourceError(Exception):
    """A source could not be reached or did not answer as expected."""


class AuthError(SourceError):
    """The source refused the credentials, or needs some."""


class WriteRefused(SourceError):
    """The source answered a write with a refusal: out of range, read only."""


class Source(Protocol):
    """The four ways in all look like this to the coordinator."""

    kind: str
    #: Seconds between polls the source itself asks for at least.
    min_interval: float

    async def async_info(self) -> SourceInfo: ...

    async def async_points(self) -> list[Point]: ...

    async def async_read(self, points: list[Point]) -> dict[str, Value]:
        """Current values keyed by Point.uid; a missing key means no value."""
        ...

    async def async_write(self, point: Point, value: Value) -> Value:
        """Write, then return what the source holds afterwards (None if unknown)."""
        ...

    async def async_close(self) -> None: ...


TRUE_WORDS = frozenset({"on", "true", "1", "yes", "ja", "an", "ein", "aan", "på"})
FALSE_WORDS = frozenset({"off", "false", "0", "no", "nej", "aus", "uit", "av"})


def to_bool(value: Any) -> bool | None:
    """A boolean from whatever form a source sends one in."""
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return bool(value)
    if isinstance(value, str):
        word = value.strip().lower()
        if word in TRUE_WORDS:
            return True
        if word in FALSE_WORDS:
            return False
    return None


def to_number(value: Any) -> float | None:
    """A number, or None for anything that is not one (including booleans)."""
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip().replace(",", "."))
        except ValueError:
            return None
    return None


def coerce(point: Point, value: Any) -> Value:
    """A raw value as the kind its point says it is; None when it is not one."""
    if value is None or value == "":
        return None
    if point.kind == NUMBER:
        return to_number(value)
    if point.kind == BOOL:
        return to_bool(value)
    if point.kind == ENUM:
        if isinstance(value, (int, float)) and not isinstance(value, bool) and point.options:
            index = int(value)
            if 0 <= index < len(point.options) and str(value) not in point.options:
                return point.options[index]
        return str(value)
    if point.kind == COMMAND:
        return None
    return str(value)
