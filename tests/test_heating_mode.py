"""The heating mode over every circuit with a room setpoint."""

from __future__ import annotations

from custom_components.rego_local_easyconf.heating_mode import (
    DEFAULT_STEPS,
    NORMAL,
    Controller,
    Lever,
    steps_from,
    target,
)


class Store:
    def __init__(self, data=None):
        self.data = data
        self.saved = None

    async def async_load(self):
        return self.data

    async def async_save(self, data):
        self.saved = data

    def async_delay_save(self, func, delay):
        self.saved = func()


def _controller(setpoints: dict[str, float], store=None):
    written: list[tuple[str, float]] = []

    def lever(circuit):
        async def write(value):
            written.append((circuit, value))
            setpoints[circuit] = value
            return value

        return Lever(circuit, 5, 30, 0.5, lambda: setpoints.get(circuit), write)

    steps = steps_from({}, {"blocked": "b", "eco": "e", "boost": "x"})
    return Controller([lever(c) for c in setpoints], steps, store or Store(), lambda: None), written


def test_steps_default_to_ems_steward_set_backs():
    assert DEFAULT_STEPS == {"blocked": -3.0, "eco": -1.5, "boost": 1.0}
    assert target("eco", 21, {"eco": -1.5}, 5, 30) == 19.5
    assert target("blocked", 6, {"blocked": -3}, 5, 30) == 5


async def test_every_circuit_moves_from_its_own_normal():
    setpoints = {"hc1": 21.0, "hc2": 19.0}
    controller, written = _controller(setpoints)
    controller.follow()
    await controller.async_choose("eco")
    assert written == [("hc1", 19.5), ("hc2", 17.5)]
    await controller.async_choose("boost")
    assert setpoints == {"hc1": 22.0, "hc2": 20.0}
    await controller.async_choose(NORMAL)
    assert setpoints == {"hc1": 21.0, "hc2": 19.0}


async def test_a_change_by_hand_in_normal_becomes_the_new_normal():
    setpoints = {"hc1": 21.0}
    controller, _ = _controller(setpoints)
    controller.follow()
    setpoints["hc1"] = 20.0
    controller.follow()
    assert controller.circuits["hc1"].normal == 20.0
    await controller.async_choose("blocked")
    assert setpoints["hc1"] == 17.0


async def test_a_change_by_hand_in_another_mode_holds_until_the_next_choice():
    setpoints = {"hc1": 21.0}
    controller, _ = _controller(setpoints)
    controller.follow()
    await controller.async_choose("eco")
    setpoints["hc1"] = 23.0
    controller.follow()
    assert controller.mode == "eco"
    assert controller.circuits["hc1"].normal == 21.0
    await controller.async_choose(NORMAL)
    assert setpoints["hc1"] == 21.0


async def test_state_survives_a_restart():
    store = Store({"mode": "eco", "circuits": {"hc1": {"normal": 21.0, "seen": 19.5}}})
    controller, _ = _controller({"hc1": 19.5}, store)
    await controller.async_load()
    controller.follow()
    assert controller.mode == "eco"
    assert controller.circuits["hc1"].normal == 21.0


async def test_the_controllers_comfort_temperature_is_normal():
    """A setpoint written elsewhere (another energy manager's set-back) never becomes normal."""
    setpoints = {"hc1": 18.0}
    written = []

    async def write(value):
        written.append(value)
        setpoints["hc1"] = value
        return value

    lever = Lever("hc1", 5, 30, 0.5, lambda: setpoints["hc1"], write, normal=lambda: 21.0)
    controller = Controller([lever], steps_from({}, {"blocked": "b", "eco": "e", "boost": "x"}), Store(), lambda: None)
    controller.follow()
    assert controller.circuits["hc1"].normal == 21.0
    setpoints["hc1"] = 19.5
    controller.follow()
    assert controller.circuits["hc1"].normal == 21.0
    await controller.async_choose("eco")
    await controller.async_choose(NORMAL)
    assert written == [19.5, 21.0]
