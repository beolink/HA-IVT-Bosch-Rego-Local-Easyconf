"""Building a source from its config entry data, and keeping its list of points.

Each source's points are cached, with the version of the integration that
listed them. A start reaches every source for a fresh list; a source that is
away at that moment is set up from the cache, so its entities exist and show
unavailable rather than vanishing, and the next start tries again.
"""

from __future__ import annotations

from dataclasses import asdict
import logging
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.storage import Store

from .const import (
    CONF_HOST,
    CONF_KIND,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
    DOMAIN,
    SOURCE_CLOUD,
    SOURCE_EMSESP,
    SOURCE_HUSDATA,
)
from .model import DeviceDescription, Point, Source, SourceInfo

_LOGGER = logging.getLogger(__name__)

STORAGE_VERSION = 1


def build(hass: HomeAssistant, conf: dict[str, Any], on_tokens=None) -> Source:
    """A source client from one entry in the config entry's list of sources."""
    kind = conf[CONF_KIND]
    session = async_get_clientsession(hass)
    if kind == SOURCE_EMSESP:
        from .emsesp import EmsEspSource

        return EmsEspSource(
            session,
            conf[CONF_HOST],
            token=conf.get(CONF_TOKEN),
            username=conf.get(CONF_USERNAME),
            password=conf.get(CONF_PASSWORD),
        )
    if kind == SOURCE_HUSDATA:
        from .husdata import HusdataSource

        return HusdataSource(session, conf[CONF_HOST], variant=conf.get("variant"))
    if kind == SOURCE_CLOUD:
        from .bosch_cloud import BoschCloudSource

        borrow = None
        if conf.get("borrow") == HOMECOM_DOMAIN:
            device_id = str(conf.get("device_id"))
            borrow = lambda: homecom_token(hass, device_id)  # noqa: E731
        return BoschCloudSource(session, conf, on_tokens=on_tokens, borrow=borrow)
    raise ValueError(f"Unknown source {kind}")


#: The community integration for Bosch's cloud (serbanb11/bosch-homecom-hass),
#: whose login this one can borrow.
HOMECOM_DOMAIN = "bosch_homecom"


def homecom_entries(hass: HomeAssistant) -> list:
    """Bosch HomeCom entries that are switched on and hold an access token."""
    return [
        entry
        for entry in hass.config_entries.async_entries(HOMECOM_DOMAIN)
        if entry.disabled_by is None and (entry.data or {}).get("token")
    ]


def homecom_token(hass: HomeAssistant, device_id: str | None = None) -> str | None:
    """The access token Bosch HomeCom keeps renewed, for the entry that has ``device_id``.

    Bosch HomeCom stores both tokens in its entry after every renewal, and
    lists its gateways as ``<device id>_<type>`` keys under ``devices``.
    """
    for entry in homecom_entries(hass):
        devices = (entry.data or {}).get("devices") or {}
        if device_id is None or not devices or any(str(k).split("_", 1)[0] == device_id for k in devices):
            return entry.data.get("token")
    return None


def points_store(hass: HomeAssistant, entry_id: str) -> Store:
    return Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry_id}.points")


def dump(info: SourceInfo | None, points: list[Point]) -> dict[str, Any]:
    return {
        "info": None if info is None else {**asdict(info), "devices": [asdict(d) for d in info.devices]},
        "points": [asdict(p) for p in points],
    }


def load(data: dict[str, Any]) -> tuple[SourceInfo | None, list[Point]]:
    info = None
    raw = data.get("info")
    if isinstance(raw, dict):
        devices = [DeviceDescription(**d) for d in raw.get("devices") or []]
        info = SourceInfo(**{**raw, "devices": devices})
    points = []
    for row in data.get("points") or []:
        try:
            row = dict(row)
            row["options"] = tuple(row.get("options") or ())
            points.append(Point(**row))
        except TypeError:
            continue
    return info, points
