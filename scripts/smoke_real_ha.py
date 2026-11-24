#!/usr/bin/env python3
"""Set the integration up under a real Home Assistant, against a stand-in EMS-ESP gateway.

The stand-in serves what the BBQKees gateway on an IVT Geo 608C with a Rego
3000 and an MM100 answered on 2026-11-24 (tests/fixtures/emsesp_geo608c):
``/api/system/info``, each device's ``/entities``, its values nested by
circuit, single entities, ``/rest/signIn`` and writes with a bearer token. It
answers 429 to a GET that comes within 50 ms of the last request, as EMS-ESP
3.8.3+ does.

In order: the config flow from the menu through the typed-in address, the
login and the cloud offer to an entry; the entry set up with every platform;
the entities and their values; a heating mode chosen (two writes, one per
circuit); the hot water boost; and the entry unloaded. The frontend is not
installed in the venv, so the panel registration is replaced by a no-op.

Usage: <venv with homeassistant>/bin/python scripts/smoke_real_ha.py
Ends with os._exit: Python 3.14 crashes on shutdown after Home Assistant's C
extensions are loaded, once the work is done.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from pathlib import Path
import socket
import sys
import tempfile
import time
from unittest.mock import patch

from aiohttp import web

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIXTURES = ROOT / "tests" / "fixtures" / "emsesp_geo608c"
DOMAIN = "rego_local_easyconf"
TOKEN = "smoke-token"

failures: list[str] = []


def check(condition: bool, what: str) -> None:
    print(("ok    " if condition else "FAIL  ") + what)
    if not condition:
        failures.append(what)


def free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


class FakeEmsEsp:
    def __init__(self) -> None:
        self.info = json.loads((FIXTURES / "system_info.json").read_text())
        self.entities = {
            d: json.loads((FIXTURES / f"{d}_entities.json").read_text()) for d in ("boiler", "thermostat", "mixer")
        }
        self.writes: list[tuple[str, object]] = []
        self.last = 0.0
        self.busy = 0

    def _throttle(self) -> bool:
        now = time.monotonic()
        too_soon = now - self.last < 0.05
        self.last = now
        if too_soon:
            self.busy += 1
        return too_soon

    def _values(self, device: str) -> dict:
        out: dict = {}
        for key, meta in self.entities[device].items():
            if meta.get("value") is None:
                continue
            head, _, tail = key.partition(".")
            if tail:
                out.setdefault(head, {})[tail] = meta["value"]
            else:
                out[key] = meta["value"]
        return out

    async def handle(self, request: web.Request) -> web.Response:
        path = request.path
        if request.method == "POST" and path == "/rest/signIn":
            body = await request.json()
            if body.get("username") == "admin" and body.get("password") == "admin":
                return web.json_response({"access_token": TOKEN})
            return web.Response(status=401)
        if request.method == "GET" and self._throttle():
            return web.Response(status=429)
        parts = path.strip("/").split("/")
        if parts[:3] == ["api", "system", "info"]:
            return web.json_response(self.info)
        if parts[:2] == ["api", "temperaturesensor"]:
            return web.json_response({"gateway_temperature": 28.6})
        if parts[:2] == ["api", "analogsensor"]:
            return web.json_response({})
        device = parts[1] if len(parts) > 1 else ""
        if device not in self.entities:
            return web.json_response({"message": "unknown"}, status=404)
        if len(parts) == 2 and request.method == "GET":
            return web.json_response(self._values(device))
        if parts[2:] == ["entities"]:
            return web.json_response(self.entities[device])
        key = ".".join(parts[2:])
        meta = self.entities[device].get(key)
        if meta is None:
            return web.json_response({"message": f"no '{key}' in {device}"}, status=404)
        if request.method == "GET":
            return web.json_response(meta)
        if request.headers.get("Authorization") != f"Bearer {TOKEN}":
            return web.json_response({"message": "authentication failed"}, status=401)
        if request.content_type != "application/json":
            return web.json_response({"message": "Not found"}, status=404)
        value = (await request.json()).get("value")
        self.writes.append((f"{device}/{key}", value))
        if meta.get("type") == "boolean":
            meta["value"] = "on" if str(value).lower() in ("on", "1", "true") else "off"
        else:
            meta["value"] = value
        return web.json_response({})

    async def start(self) -> int:
        app = web.Application()
        app.router.add_route("*", "/{tail:.*}", self.handle)
        self.runner = web.AppRunner(app)
        await self.runner.setup()
        port = free_port()
        await web.TCPSite(self.runner, "127.0.0.1", port).start()
        return port


async def main() -> int:
    from homeassistant import auth as ha_auth, bootstrap, config_entries, loader
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers import entity_registry as er
    from homeassistant.setup import async_setup_component

    logging.basicConfig(level=logging.WARNING)
    fake = FakeEmsEsp()
    port = await fake.start()
    host = f"127.0.0.1:{port}"

    with tempfile.TemporaryDirectory() as config_dir:
        os.makedirs(f"{config_dir}/custom_components")
        os.symlink(ROOT / "custom_components" / DOMAIN, f"{config_dir}/custom_components/{DOMAIN}")
        hass = HomeAssistant(config_dir)
        hass.config.language = "sv"
        await hass.config.async_set_time_zone("Europe/Stockholm")
        loader.async_setup(hass)
        hass.config_entries = config_entries.ConfigEntries(hass, {})
        await hass.config_entries.async_initialize()
        assert await bootstrap.async_load_base_functionality(hass)
        hass.auth = await ha_auth.auth_manager_from_config(hass, [{"type": "homeassistant"}], [])
        assert await async_setup_component(hass, "homeassistant", {})
        assert await async_setup_component(hass, "http", {"http": {"server_port": free_port()}})
        assert await async_setup_component(hass, "network", {})
        # No frontend package in the venv: count it as there, and skip the panel.
        hass.config.components.update({"frontend", "panel_custom"})

        async def no_frontend(*_args, **_kwargs):
            return None

        with patch(f"custom_components.{DOMAIN}.async_register_frontend", no_frontend):
            flow = hass.config_entries.flow
            result = await flow.async_init(DOMAIN, context={"source": "user"})
            check(result["type"] == "menu" and "manual" in result["menu_options"], "flow opens on the menu")
            result = await flow.async_configure(result["flow_id"], {"next_step_id": "manual"})
            check(result["step_id"] == "manual", "the address form")
            result = await flow.async_configure(result["flow_id"], {"host": host})
            check(result.get("step_id") == "emsesp_auth", f"EMS-ESP identified, login asked ({result.get('step_id')})")
            bad = await flow.async_configure(result["flow_id"], {"username": "admin", "password": "wrong"})
            check(bad.get("errors") == {"base": "invalid_auth"}, "a wrong password is refused")
            result = await flow.async_configure(result["flow_id"], {"username": "admin", "password": "admin"})
            check(result.get("step_id") == "offer_cloud", "the cloud is offered after the local login")
            result = await flow.async_configure(result["flow_id"], {"next_step_id": "finish"})
            check(result["type"] == "create_entry", f"entry created: {result.get('title')}")
            entry = result["result"]
            check(entry.title == "IVT värmepump", f"titled from the brand ({entry.title})")
            await hass.async_block_till_done()
            check(entry.state is config_entries.ConfigEntryState.LOADED, f"entry loaded ({entry.state})")

            registry = er.async_get(hass)
            ours = [e for e in registry.entities.values() if e.platform == DOMAIN]
            enabled = [e for e in ours if not e.disabled]
            print(f"      {len(ours)} entities, {len(enabled)} enabled by default")
            check(len(ours) > 250, "every value the gateway sends is an entity")
            check(60 <= len(enabled) <= 160, "a manageable default set")

            def state_by_role(role: str):
                for e in ours:
                    st = hass.states.get(e.entity_id)
                    if st is not None and st.attributes.get("role") == role:
                        return st
                return None

            outdoor = state_by_role("outdoor_temp")
            check(outdoor is not None and float(outdoor.state) == 9.3, f"outdoor temperature ({outdoor and outdoor.state})")
            check(outdoor is not None and outdoor.name.endswith("Utetemperatur"), f"named in Swedish ({outdoor and outdoor.name})")
            alarm = state_by_role("alarm")
            check(alarm is not None and "Kabelbrott i utetemp.givare T1" in alarm.state, f"alarm in words ({alarm and alarm.state})")
            check(alarm is not None and alarm.attributes.get("active") is True, "the alarm is active")
            supply = state_by_role("supply_temp")
            check(supply is not None and supply.attributes.get("source_key") == "boiler/hptc1", "supply from TC1")
            cop = [hass.states.get(e.entity_id) for e in ours if e.unique_id.endswith("-cop-lifetime")]
            check(bool(cop) and cop[0] is not None and abs(float(cop[0].state) - 4.88) < 0.01, f"lifetime COP ({cop and cop[0] and cop[0].state})")

            mode_id = next(e.entity_id for e in ours if e.unique_id.endswith("-heating_mode"))
            mode = hass.states.get(mode_id)
            check(mode.state == "normal", f"heating mode starts normal ({mode.state})")
            climates = [e.entity_id for e in ours if e.domain == "climate"]
            check(len(climates) == 2, f"a thermostat per circuit ({climates})")
            heaters = [e.entity_id for e in ours if e.domain == "water_heater"]
            check(len(heaters) == 1, "a water heater")

            fake.writes.clear()
            await hass.services.async_call("select", "select_option", {"entity_id": mode_id, "option": "eco"}, blocking=True)
            await hass.async_block_till_done()
            check(
                sorted(fake.writes) == [("thermostat/hc1.seltemp", 19.5), ("thermostat/hc2.seltemp", 19.5)],
                f"eco: both circuits 1.5 °C under their comfort temperature, 21 °C ({fake.writes})",
            )
            check(hass.states.get(mode_id).state == "eco", "the select shows eco")
            climate = hass.states.get(climates[0])
            check(climate.attributes.get("preset_mode") == "eco", "the thermostat's preset follows")

            boost = state_by_role("dhw_boost")
            fake.writes.clear()
            await hass.services.async_call("switch", "turn_on", {"entity_id": boost.entity_id}, blocking=True)
            check(fake.writes == [("thermostat/dhw.charge", "on")], f"boost through the controller's charge ({fake.writes})")
            check(hass.states.get(boost.entity_id).state == "on", "the boost switch reads back on")

            await hass.services.async_call("select", "select_option", {"entity_id": mode_id, "option": "normal"}, blocking=True)
            check(fake.entities["thermostat"]["hc1.seltemp"]["value"] == 21, "normal is the comfort temperature")

            coordinator = entry.runtime_data
            await coordinator.async_refresh()
            check(coordinator.last_update_success, "a poll after the writes")
            print(f"      the stand-in answered 429 {fake.busy} times")

            check(await hass.config_entries.async_unload(entry.entry_id), "unloads")
        await hass.async_stop(force=True)
    await fake.runner.cleanup()
    print("\nFAILED: " + "; ".join(failures) if failures else "\nall passed")
    return 1 if failures else 0


if __name__ == "__main__":
    rc = asyncio.run(main())
    logging.shutdown()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(rc)
