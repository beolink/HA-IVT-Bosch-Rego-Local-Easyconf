"""Heating mode: blocked, eco, normal or boost, the way an energy manager steers a heat pump.

An energy manager such as EMS Steward decides quarter by quarter whether the
house heats as usual, holds back while electricity is dear or stores heat
while it is cheap, and it expects a select offering exactly these four ids.

On a Rego controller the lever is each heating circuit's room setpoint. With
no room sensor fitted it still moves the heat curve: on the IVT Geo 608C this
was built against, the setpoints EMS Steward wrote through EMS-ESP since
2026-11-07 (18 / 19.5 / 21 / 22 °C for blocked / eco / normal / boost) moved
the radiator circuit's calculated supply between 25 and 33 °C, and the floor
circuit's between 22 and 26 °C, with the house staying at 20.3-21 °C.

So a mode is a step from the house's own normal setpoint, per circuit - every
circuit with a writable setpoint, which is what EMS Steward could not do when
it was bound to one thermostat of two. The defaults are EMS Steward's own
thermostat set-backs: -3 °C blocked, -1.5 °C eco, +1 °C boost. Heating is
never switched off; a blocked house coasts with the curve's minimum supply
temperature still guarding it.

Normal is the circuit's own comfort temperature where the controller has one
(a Rego 3000's ``hcN.comforttemp``, 21 °C on both circuits of the Geo 608C):
the room temperature the house is set up for, kept in the controller and
changed there or through its own entity. A setpoint changed anywhere else -
at the display, by another energy manager still bound to the setpoint - then
never becomes the normal; it holds until the mode next changes. Learning it
from the setpoint instead took a set-back for normal on the first house this
was installed on, where an energy manager held the house in one through its
own binding at that moment.

Where there is no comfort temperature (Husdata, the cloud), normal is learned
as in the NIBE integration: the setpoint each circuit had when the select
first saw it, and a setpoint changed elsewhere while in normal becomes the new
normal. Either way the select keeps showing the mode last chosen, so an energy
manager does not undo a change made by hand.

Nothing here imports Home Assistant.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import asdict, dataclass, replace
import logging

_LOGGER = logging.getLogger(__name__)

BLOCKED = "blocked"
ECO = "eco"
NORMAL = "normal"
BOOST = "boost"
MODES: tuple[str, ...] = (BLOCKED, ECO, NORMAL, BOOST)

DEFAULT_STEPS: Mapping[str, float] = {BLOCKED: -3.0, ECO: -1.5, BOOST: 1.0}

#: A setpoint read back within this of the one last seen is the same one.
TOLERANCE = 0.05


@dataclass(frozen=True)
class CircuitState:
    normal: float
    #: The setpoint last seen, so a change made elsewhere can be told apart.
    seen: float


@dataclass(frozen=True)
class ModeState:
    mode: str
    circuits: dict[str, CircuitState]


def steps_from(options: Mapping, keys: Mapping[str, str]) -> dict[str, float]:
    steps = {mode: float(options.get(keys[mode], step)) for mode, step in DEFAULT_STEPS.items()}
    steps[NORMAL] = 0.0
    return steps


def target(mode: str, normal: float, steps: Mapping[str, float], low: float, high: float, step: float = 0.5) -> float:
    """The setpoint a mode writes, rounded to the setpoint's step and kept in range."""
    raw = normal + steps[mode]
    if step:
        raw = round(raw / step) * step
    return max(low, min(high, raw))


def follow(state: CircuitState | None, mode: str, value: float) -> CircuitState:
    """A circuit's state once its setpoint is seen at ``value`` without a mode chosen."""
    if state is None:
        return CircuitState(value, value)
    if abs(value - state.seen) <= TOLERANCE:
        return state
    if mode == NORMAL:
        return CircuitState(value, value)
    return replace(state, seen=value)


@dataclass
class Lever:
    """One circuit's setpoint as the controller sees it."""

    circuit: str
    low: float
    high: float
    step: float
    read: Callable[[], float | None]
    write: Callable[[float], Awaitable[float | None]]
    #: The controller's own comfort temperature, when it has one: the normal.
    normal: Callable[[], float | None] | None = None

    def fixed_normal(self) -> float | None:
        if self.normal is None:
            return None
        value = self.normal()
        return None if value is None else float(value)


class Controller:
    """The heating mode of one pump, over every circuit it steers.

    The select and each thermostat's presets read and write the same
    controller, so they can never disagree about the mode or learn two
    different normals.
    """

    def __init__(self, levers: list[Lever], steps: Mapping[str, float], store, notify: Callable[[], None]) -> None:
        self.levers = {lever.circuit: lever for lever in levers}
        self.steps = dict(steps)
        self._store = store
        self._notify = notify
        self.mode = NORMAL
        self.circuits: dict[str, CircuitState] = {}
        self._writing = False

    async def async_load(self) -> None:
        stored = await self._store.async_load()
        if not isinstance(stored, dict):
            return
        if stored.get("mode") in MODES:
            self.mode = stored["mode"]
        for circuit, row in (stored.get("circuits") or {}).items():
            try:
                self.circuits[circuit] = CircuitState(float(row["normal"]), float(row["seen"]))
            except (KeyError, TypeError, ValueError):
                continue

    def _data(self) -> dict:
        return {"mode": self.mode, "circuits": {c: asdict(s) for c, s in self.circuits.items()}}

    @property
    def available(self) -> bool:
        return any(lever.read() is not None for lever in self.levers.values())

    def follow(self) -> None:
        """Take in setpoints changed outside the select. Called on every poll."""
        if self._writing:
            return
        changed = False
        for circuit, lever in self.levers.items():
            value = lever.read()
            if value is None:
                continue
            before = self.circuits.get(circuit)
            fixed = lever.fixed_normal()
            after = CircuitState(fixed, float(value)) if fixed is not None else follow(before, self.mode, float(value))
            if after != before:
                if before is not None and fixed is None:
                    _LOGGER.info(
                        "Room setpoint of %s changed to %s outside the heating mode; mode %s, normal %s",
                        circuit, value, self.mode, after.normal,
                    )
                self.circuits[circuit] = after
                changed = True
        if changed:
            self._store.async_delay_save(self._data, 1)

    def targets(self, mode: str) -> dict[str, float]:
        out = {}
        for circuit, lever in self.levers.items():
            state = self.circuits.get(circuit)
            if state is not None:
                out[circuit] = target(mode, state.normal, self.steps, lever.low, lever.high, lever.step)
        return out

    async def async_choose(self, mode: str) -> None:
        if mode not in MODES:
            raise ValueError(f"{mode} is not a heating mode")
        if not self.circuits:
            raise RuntimeError("No room setpoint has been read yet")
        self._writing = True
        errors: list[Exception] = []
        try:
            for circuit, value in self.targets(mode).items():
                lever = self.levers[circuit]
                try:
                    stored = await lever.write(value)
                except Exception as err:  # one circuit failing must not leave the others behind
                    errors.append(err)
                    continue
                seen = value if stored is None else float(stored)
                state = self.circuits[circuit]
                fixed = lever.fixed_normal()
                learned = seen if mode == NORMAL else state.normal
                self.circuits[circuit] = CircuitState(fixed if fixed is not None else learned, seen)
        finally:
            self._writing = False
        self.mode = mode
        await self._store.async_save(self._data())
        self._notify()
        if errors:
            raise errors[0]

    def attributes(self) -> dict:
        return {
            "normal_setpoints": {c: s.normal for c, s in self.circuits.items()},
            "setpoints": {mode: self.targets(mode) for mode in MODES},
            "steps": {m: s for m, s in self.steps.items() if m != NORMAL},
        }
