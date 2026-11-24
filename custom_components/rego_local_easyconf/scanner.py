"""Find the local ways in to a heat pump, before anyone is asked for a password.

Home Assistant's own subnets are swept for anything answering HTTP on port
80, and every answer is asked who it is, in the order the sources are
preferred: an EMS-ESP gateway (``/api/system/info``), then a Husdata
interface. (A Bosch internet gateway answering on the LAN has its place in the
order, but no gateway IVT sells does: see bosch_local.py.) An open port proves nothing -
printers, routers and inverters all serve a page - so a host only counts when
it answers in its own words.

Zeroconf and DHCP discovery find the same devices on their own when they
announce themselves; the sweep is for when setup should not wait for that.
"""

from __future__ import annotations

import asyncio
import contextlib
from dataclasses import dataclass, field
import ipaddress
import logging
from typing import Any

import aiohttp
from homeassistant.components import network
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import SOURCE_EMSESP, SOURCE_HUSDATA, SOURCE_PRIORITY
from .emsesp import looks_like_emsesp

_LOGGER = logging.getLogger(__name__)

MAX_HOSTS = 1024
CONCURRENCY = 64
CONNECT_TIMEOUT = 0.6
PROBE_TIMEOUT = aiohttp.ClientTimeout(total=6)


@dataclass
class Found:
    kind: str
    host: str
    #: A line for the flow: what it is and what it sees.
    label: str
    unique_id: str | None = None
    details: dict[str, Any] = field(default_factory=dict)


async def _port_open(host: str, port: int) -> bool:
    try:
        _reader, writer = await asyncio.wait_for(asyncio.open_connection(host, port), timeout=CONNECT_TIMEOUT)
    except (OSError, TimeoutError):
        return False
    writer.close()
    with contextlib.suppress(OSError, TimeoutError):
        await writer.wait_closed()
    return True


async def _get_json(session: aiohttp.ClientSession, url: str, **kwargs) -> Any:
    try:
        async with session.get(url, timeout=PROBE_TIMEOUT, **kwargs) as response:
            if response.status != 200:
                return None
            return await response.json(content_type=None)
    except (aiohttp.ClientError, TimeoutError, ValueError, UnicodeDecodeError):
        return None


async def probe_emsesp(session: aiohttp.ClientSession, host: str) -> Found | None:
    data = await _get_json(session, f"http://{host}/api/system/info")
    if not looks_like_emsesp(data):
        return None
    system = data.get("system") or {}
    devices = [
        d for d in data.get("devices") or [] if d.get("type") not in ("temperaturesensor", "analogsensor")
    ]
    pump = next((d for d in devices if d.get("type") in ("boiler", "heatpump")), None)
    controller = next((d for d in devices if d.get("type") == "thermostat"), None)
    parts = []
    if pump:
        parts.append(f"{(pump.get('brand') or '').strip()} {pump.get('name')}".strip())
    if controller:
        parts.append(str(controller.get("name")))
    cloud_module = next((d for d in devices if d.get("type") == "gateway"), None)
    label = f"EMS-ESP {system.get('version', '')} på {host}"
    if parts:
        label += ": " + ", ".join(parts)
    hostname = (data.get("network") or {}).get("hostname")
    return Found(
        kind=SOURCE_EMSESP,
        host=host,
        label=label,
        unique_id=f"emsesp-{(hostname or host).lower()}",
        details={
            "version": system.get("version"),
            "brand": (pump or {}).get("brand"),
            "pump": (pump or {}).get("name"),
            "controller": (controller or {}).get("name"),
            "cloud_module": (cloud_module or {}).get("name"),
            "devices": len(devices),
        },
    )


async def probe_husdata(session: aiohttp.ClientSession, host: str) -> Found | None:
    from .husdata import probe

    return await probe(session, host)


PROBES = {
    SOURCE_EMSESP: probe_emsesp,
    SOURCE_HUSDATA: probe_husdata,
}


async def async_identify(hass: HomeAssistant, host: str) -> Found | None:
    """What answers at ``host``, asked in the order the sources are preferred."""
    session = async_get_clientsession(hass)
    for kind in SOURCE_PRIORITY:
        probe = PROBES.get(kind)
        if probe is None:
            continue
        try:
            found = await probe(session, host)
        except Exception:  # one odd host must not end a sweep
            _LOGGER.debug("Probing %s as %s failed", host, kind, exc_info=True)
            found = None
        if found is not None:
            return found
    return None


async def async_candidate_hosts(hass: HomeAssistant) -> list[str]:
    hosts: list[str] = []
    seen: set[str] = set()
    for adapter in await network.async_get_adapters(hass):
        if not adapter["enabled"]:
            continue
        for address in adapter["ipv4"]:
            try:
                interface = ipaddress.ip_interface(f"{address['address']}/{address['network_prefix']}")
            except ValueError:
                continue
            net = interface.network
            if net.is_loopback or net.num_addresses > MAX_HOSTS:
                continue
            for candidate in net.hosts():
                text = str(candidate)
                if text != str(interface.ip) and text not in seen:
                    seen.add(text)
                    hosts.append(text)
    return hosts


async def async_find(hass: HomeAssistant, extra_hosts: list[str] | None = None) -> list[Found]:
    """Everything local that answers as one of the sources, best kind first."""
    hosts = list(dict.fromkeys((extra_hosts or []) + await async_candidate_hosts(hass)))
    semaphore = asyncio.Semaphore(CONCURRENCY)

    async def check(host: str) -> Found | None:
        async with semaphore:
            if not await _port_open(host, 80):
                return None
        return await async_identify(hass, host)

    results = [r for r in await asyncio.gather(*(check(h) for h in hosts)) if r is not None]
    order = {kind: i for i, kind in enumerate(SOURCE_PRIORITY)}
    results.sort(key=lambda f: (order.get(f.kind, 99), f.host))
    _LOGGER.info("Search found %s", ", ".join(f"{f.kind}@{f.host}" for f in results) or "nothing")
    return results
