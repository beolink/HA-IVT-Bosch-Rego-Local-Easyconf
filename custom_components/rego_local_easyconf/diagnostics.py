"""Diagnostics: the sources, the roles they feed and the values, with logins removed."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_PASSWORD, CONF_REFRESH_TOKEN, CONF_TOKEN, CONF_USERNAME

REDACT = {CONF_PASSWORD, CONF_TOKEN, CONF_REFRESH_TOKEN, CONF_USERNAME, "access_token", "mac"}


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry) -> dict[str, Any]:
    coordinator = entry.runtime_data
    return {
        "entry": async_redact_data({"data": dict(entry.data), "options": dict(entry.options)}, REDACT),
        "sources": async_redact_data(coordinator.summary(), REDACT),
        "roles": {
            role: {
                "candidates": [p.uid for p in binding.candidates],
                "value": coordinator.role_value(role),
                "from": getattr(coordinator.role_point(role), "uid", None),
            }
            for role, binding in sorted(coordinator.bindings.items())
        },
        "own_points": len(coordinator.own),
        "values": {uid: value for uid, value in sorted(coordinator.values.items())},
        "heating_mode": None if coordinator.heating_mode is None else {
            "mode": coordinator.heating_mode.mode,
            **coordinator.heating_mode.attributes(),
        },
    }
