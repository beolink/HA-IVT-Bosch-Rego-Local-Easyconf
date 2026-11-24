"""Which source answers for which value.

The sources of one installation stand in the order const.SOURCE_PRIORITY
gives: EMS-ESP, Husdata, a Bosch gateway on the LAN, the cloud. For every role
(roles.py) the candidates are collected from every source in that order, and a
value is read from the first candidate whose source answered the last poll and
had a value for it. A source further down therefore does two things without
being told: it fills in a role the sources above it lack, and it stands in for
one that has gone away.

A point that plays no role is the source's own: it becomes an entity of its
own, switched on by default only when it comes from the installation's first
source (and the source's default list wants it). The same value can come
from two sources without a role tying them together - both the EMS-ESP gateway
and the cloud read the controller's bus - and an entity a person never asked
for, showing what another one already shows, is noise; so a lower source's own
points are created switched off, to be switched on where they add something.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from .const import SOURCE_PRIORITY
from .model import Point, Value
from .roles import ROLES, SOURCE_ROLES, Candidates


@dataclass
class Binding:
    """One role in this installation and every point that can play it, best first."""

    role: str
    candidates: list[Point] = field(default_factory=list)

    @property
    def writable(self) -> bool:
        return any(point.writable for point in self.candidates)


def priority(source: str) -> int:
    try:
        return SOURCE_PRIORITY.index(source)
    except ValueError:
        return len(SOURCE_PRIORITY)


def bind(
    points_by_source: Mapping[str, Iterable[Point]],
    roles: Mapping[str, Mapping[str, Candidates]] | None = None,
) -> tuple[dict[str, Binding], list[Point]]:
    """The roles this installation has, and the points that play none."""
    roles = SOURCE_ROLES if roles is None else roles
    index: dict[str, dict[tuple[str, str], Point]] = {
        source: {(p.device, p.key): p for p in points} for source, points in points_by_source.items()
    }
    bindings: dict[str, Binding] = {}
    used: set[str] = set()
    for source in sorted(index, key=priority):
        mapping = roles.get(source, {})
        for role, candidates in mapping.items():
            if role not in ROLES:
                continue
            for device_key in candidates:
                point = index[source].get(device_key)
                if point is None:
                    continue
                bindings.setdefault(role, Binding(role)).candidates.append(point)
                used.add(point.uid)
    own = [
        point
        for source in sorted(index, key=priority)
        for point in index[source].values()
        if point.uid not in used
    ]
    return bindings, own


def first_value(
    binding: Binding, values: Mapping[str, Value], healthy: Mapping[str, bool]
) -> tuple[Value, Point | None]:
    """The value of a role and the point it came from: the first healthy candidate with one."""
    for point in binding.candidates:
        if not healthy.get(point.source, False):
            continue
        value = values.get(point.uid)
        if value is not None:
            return value, point
    return None, None


def write_target(binding: Binding, healthy: Mapping[str, bool]) -> Point | None:
    """Where a role is written: the first writable candidate of a source that answers."""
    for point in binding.candidates:
        if point.writable and healthy.get(point.source, False):
            return point
    return None


def primary_point(binding: Binding) -> Point:
    """The point that describes a role's range and options: the best candidate."""
    return binding.candidates[0]
