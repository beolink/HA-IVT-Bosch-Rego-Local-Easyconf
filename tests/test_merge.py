"""Which source answers for which value."""

from __future__ import annotations

from custom_components.rego_local_easyconf.emsesp import points_from_entities
from custom_components.rego_local_easyconf.merge import bind, first_value, write_target
from custom_components.rego_local_easyconf.model import NUMBER, Point


def _ems(geo_entities):
    points, values = [], {}
    for device, entities in geo_entities.items():
        found, found_values = points_from_entities(device, entities)
        points += found
        values.update(found_values)
    return points, values


def _cloud_point(path, writable=False):
    return Point("cloud", "heatpump", path, path, NUMBER, unit="°C", writable=writable)


def test_roles_are_bound_to_the_best_candidate(geo_entities):
    points, _ = _ems(geo_entities)
    bindings, own = bind({"emsesp": points})
    # TC1 is preferred over the boiler's "current flow temperature".
    assert bindings["supply_temp"].candidates[0].key == "hptc1"
    assert bindings["hc1_room_setpoint"].candidates[0].key == "hc1.seltemp"
    assert bindings["hc2_room_setpoint"].writable
    assert "hc3_room_setpoint" not in bindings
    # A candidate that plays a role is not also an entity of its own, and
    # neither is the second candidate: it is the role's fallback.
    assert "hptc1" not in {p.key for p in own}
    assert "curflowtemp" not in {p.key for p in own}


def test_a_lower_source_fills_in_and_stands_in(geo_entities):
    ems, values = _ems(geo_entities)
    cloud_outdoor = _cloud_point("/system/sensors/temperatures/outdoor_t1")
    cloud_only = _cloud_point("/heatSources/systemPressure")
    bindings, own = bind({"emsesp": ems, "cloud": [cloud_outdoor, cloud_only]})
    outdoor = bindings["outdoor_temp"]
    assert [p.source for p in outdoor.candidates] == ["emsesp", "cloud"]
    values[cloud_outdoor.uid] = 1.5
    healthy = {"emsesp": True, "cloud": True}
    assert first_value(outdoor, values, healthy) == (9.3, outdoor.candidates[0])
    # EMS-ESP away: the cloud's reading stands in.
    healthy["emsesp"] = False
    assert first_value(outdoor, values, healthy) == (1.5, cloud_outdoor)
    # A cloud value with no role is the cloud's own entity.
    assert cloud_only in own


def test_writes_go_to_the_first_writable_source_that_answers(geo_entities):
    ems, _ = _ems(geo_entities)
    cloud_setpoint = _cloud_point("/heatingCircuits/hc1/manualRoomSetpoint", writable=True)
    bindings, _ = bind({"emsesp": ems, "cloud": [cloud_setpoint]})
    binding = bindings["hc1_room_setpoint"]
    assert write_target(binding, {"emsesp": True, "cloud": True}).source == "emsesp"
    assert write_target(binding, {"emsesp": False, "cloud": True}) is cloud_setpoint
    assert write_target(binding, {"emsesp": False, "cloud": False}) is None
