"""IVT Bosch Rego Local Easyconf: IVT and Bosch heat pumps, local first.

One config entry is one heat pump. It can be reached through several sources
at once - an EMS-ESP gateway on its bus, a Husdata interface, a Bosch internet
gateway answering on the LAN, Bosch's cloud - and every value is read from the
best of them that has it (const.SOURCE_PRIORITY, merge.py).
"""

from __future__ import annotations

from datetime import timedelta
import logging
import time

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.storage import Store
from homeassistant.loader import async_get_integration
import voluptuous as vol

from . import faults
from .const import (
    CONF_CLOUD_SCAN_INTERVAL,
    CONF_KIND,
    CONF_MODE_CIRCUITS,
    CONF_SCAN_INTERVAL,
    CONF_SOURCES,
    CONF_STEP_BLOCKED,
    CONF_STEP_BOOST,
    CONF_STEP_ECO,
    DEFAULT_CLOUD_SCAN_INTERVAL,
    DEFAULT_SCAN_INTERVAL,
    DOMAIN,
    PLATFORMS,
    SERVICE_RESCAN,
    SOURCE_CLOUD,
)
from .coordinator import RegoCoordinator, SourceState
from .cop import STORAGE_VERSION as COP_STORAGE_VERSION, CopTracker
from .frontend import async_register_frontend, async_unregister_frontend
from .heating_mode import BLOCKED, BOOST, ECO, Controller, Lever, steps_from
from .model import AuthError, SourceError
from .sources import build, dump, load, points_store

_LOGGER = logging.getLogger(__name__)

COP_SAMPLE_INTERVAL = timedelta(hours=6)
STEP_KEYS = {BLOCKED: CONF_STEP_BLOCKED, ECO: CONF_STEP_ECO, BOOST: CONF_STEP_BOOST}

type RegoConfigEntry = ConfigEntry[RegoCoordinator]

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def language_of(hass: HomeAssistant) -> str:
    return "sv" if str(hass.config.language or "").lower().startswith("sv") else "en"


async def async_setup(hass: HomeAssistant, config) -> bool:
    async def rescan(call: ServiceCall) -> None:
        entry_ids = [call.data["entry_id"]] if call.data.get("entry_id") else [
            e.entry_id for e in hass.config_entries.async_entries(DOMAIN)
        ]
        for entry_id in entry_ids:
            await points_store(hass, entry_id).async_remove()
            await hass.config_entries.async_reload(entry_id)

    hass.services.async_register(
        DOMAIN, SERVICE_RESCAN, rescan, schema=vol.Schema({vol.Optional("entry_id"): cv.string})
    )
    return True


async def async_setup_entry(hass: HomeAssistant, entry: RegoConfigEntry) -> bool:
    integration = await async_get_integration(hass, DOMAIN)
    version = str(integration.version)
    await hass.async_add_executor_job(faults.table)

    store = points_store(hass, entry.entry_id)
    cached = await store.async_load() or {}
    cache_valid = cached.get("version") == version
    language = language_of(hass)
    scan = int(entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL))
    cloud_scan = int(entry.options.get(CONF_CLOUD_SCAN_INTERVAL, DEFAULT_CLOUD_SCAN_INTERVAL))

    def save_tokens(kind: str, tokens: dict) -> None:
        """A source renewed its tokens: keep them in the entry for the next start."""
        sources = [dict(s) for s in entry.data.get(CONF_SOURCES, [])]
        for conf in sources:
            if conf.get(CONF_KIND) == kind:
                conf.update(tokens)
        hass.config_entries.async_update_entry(entry, data={**entry.data, CONF_SOURCES: sources})

    states: list[SourceState] = []
    fresh_cache: dict[str, dict] = {}
    auth_failed: list[str] = []
    for conf in entry.data.get(CONF_SOURCES, []):
        kind = conf[CONF_KIND]
        client = build(hass, conf, on_tokens=lambda tokens, kind=kind: save_tokens(kind, tokens))
        info, points, from_cache = None, [], False
        try:
            info = await client.async_info()
            points = await client.async_points()
            fresh_cache[kind] = dump(info, points)
        except AuthError as err:
            auth_failed.append(f"{kind}: {err}")
            if kind in (cached.get("sources") or {}):
                info, points = load(cached["sources"][kind])
                from_cache = True
        except SourceError as err:
            _LOGGER.warning("%s did not answer at start: %s", kind, err)
            if kind in (cached.get("sources") or {}):
                info, points = load(cached["sources"][kind])
                from_cache = True
        if not points:
            continue
        state = SourceState(
            kind=kind,
            client=client,
            info=info,
            points={p.uid: p for p in points},
            interval=cloud_scan if kind == SOURCE_CLOUD else scan,
            from_cache=from_cache,
        )
        initial = getattr(client, "initial_values", None)
        if initial and not from_cache:
            state.healthy = True
            state.last_ok = time.time()
        states.append(state)

    if not states:
        if auth_failed and len(auth_failed) == len(entry.data.get(CONF_SOURCES, [])):
            raise ConfigEntryAuthFailed("; ".join(auth_failed))
        raise ConfigEntryNotReady("No source of this heat pump answers yet")

    if fresh_cache:
        merged = dict(cached.get("sources") or {}) if cache_valid else {}
        merged.update(fresh_cache)
        await store.async_save({"version": version, "sources": merged})

    coordinator = RegoCoordinator(hass, entry, states, scan_interval=min(s.interval for s in states))
    coordinator.language = language
    for state in states:
        initial = getattr(state.client, "initial_values", None)
        if initial and not state.from_cache:
            coordinator.values.update(initial)
            # The list came with values; no need to read them again at once.
            state.next_due = time.monotonic() + state.interval / 2

    # Heating mode over every circuit with a writable room setpoint.
    levers = _levers(coordinator, entry)
    if levers:
        coordinator.heating_mode = Controller(
            levers,
            steps_from(entry.options, STEP_KEYS),
            Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.heating_mode"),
            coordinator.async_update_listeners,
        )
        await coordinator.heating_mode.async_load()

    if coordinator.has_role("energy_in_total") and coordinator.has_role("energy_out_total"):
        coordinator.cop = CopTracker(Store(hass, COP_STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}.cop"))
        await coordinator.cop.async_load()

    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    # The pump's device first, so the controller, the mixing module and the
    # gateways can name it as the device they sit behind.
    from .entity import pump_device_info

    coordinator.pump_device_id = (
        dr.async_get(hass).async_get_or_create(config_entry_id=entry.entry_id, **pump_device_info(coordinator)).id
    )

    if coordinator.cop is not None:

        async def sample(_now=None) -> None:
            await coordinator.cop.async_record(coordinator.energy_out, coordinator.energy_in)

        await sample()
        entry.async_on_unload(async_track_time_interval(hass, sample, COP_SAMPLE_INTERVAL))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await async_register_frontend(hass, version)
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))
    return True


def _levers(coordinator: RegoCoordinator, entry: ConfigEntry) -> list[Lever]:
    chosen = entry.options.get(CONF_MODE_CIRCUITS)
    levers = []
    for role, binding in coordinator.bindings.items():
        if not role.endswith("_room_setpoint") or not binding.writable:
            continue
        circuit = role.split("_", 1)[0]
        if chosen is not None and circuit not in chosen:
            continue
        point = next(p for p in binding.candidates if p.writable)

        def read(role=role):
            value = coordinator.role_value(role)
            return None if value is None else float(value)

        async def write(value: float, role=role):
            stored = await coordinator.async_write_role(role, value)
            return None if stored is None else float(stored)

        comfort_role = f"{circuit}_comfort_temp"

        def normal(comfort_role=comfort_role):
            value = coordinator.role_value(comfort_role)
            return None if value is None else float(value)

        levers.append(
            Lever(
                circuit=circuit,
                low=max(5.0, point.minimum if point.minimum is not None else 5.0),
                high=min(30.0, point.maximum if point.maximum is not None else 30.0),
                step=point.step or 0.5,
                read=read,
                write=write,
                normal=normal if coordinator.has_role(comfort_role) else None,
            )
        )
    return sorted(levers, key=lambda lever: lever.circuit)


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: RegoConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        for state in entry.runtime_data.sources:
            await state.client.async_close()
        if not any(
            e.entry_id != entry.entry_id and e.state is ConfigEntryState.LOADED for e in hass.config_entries.async_entries(DOMAIN)
        ):
            async_unregister_frontend(hass)
    return unloaded


async def async_remove_entry(hass: HomeAssistant, entry: ConfigEntry) -> None:
    for name in ("points", "heating_mode", "cop"):
        await Store(hass, 1, f"{DOMAIN}.{entry.entry_id}.{name}").async_remove()
