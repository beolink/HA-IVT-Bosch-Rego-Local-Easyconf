"""Constants for IVT Bosch Rego Local Easyconf."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "rego_local_easyconf"
NAME: Final = "IVT Bosch Rego Local Easyconf"

#: The ways in, best first. A value is taken from the first source in this
#: order that has it, and a source further down only fills in what the ones
#: above it lack - or stands in while one of them is away. Local before cloud,
#: and among the local ones the one that sees the most: EMS-ESP sits on the
#: pump's own bus and reads everything the controller does; Husdata reads what
#: its firmware maps; a Bosch internet gateway answering on the LAN reads the
#: controller's own tree; the cloud reads that same tree from Bosch's servers.
SOURCE_EMSESP: Final = "emsesp"
SOURCE_HUSDATA: Final = "husdata"
SOURCE_BOSCH_LOCAL: Final = "bosch_local"
SOURCE_CLOUD: Final = "cloud"
SOURCE_PRIORITY: Final[tuple[str, ...]] = (
    SOURCE_EMSESP,
    SOURCE_HUSDATA,
    SOURCE_BOSCH_LOCAL,
    SOURCE_CLOUD,
)
LOCAL_SOURCES: Final = frozenset({SOURCE_EMSESP, SOURCE_HUSDATA, SOURCE_BOSCH_LOCAL})

SOURCE_LABELS: Final[dict[str, dict[str, str]]] = {
    SOURCE_EMSESP: {"sv": "EMS-ESP (BBQKees)", "en": "EMS-ESP (BBQKees)"},
    SOURCE_HUSDATA: {"sv": "Husdata H60/H66", "en": "Husdata H60/H66"},
    SOURCE_BOSCH_LOCAL: {"sv": "Bosch-gateway i nätet", "en": "Bosch gateway on the LAN"},
    SOURCE_CLOUD: {"sv": "Bosch-molnet", "en": "Bosch cloud"},
}

# Config entry data: one list of sources, each a dict with "kind" and its own keys.
CONF_SOURCES: Final = "sources"
CONF_KIND: Final = "kind"
CONF_HOST: Final = "host"
CONF_USERNAME: Final = "username"
CONF_PASSWORD: Final = "password"
CONF_TOKEN: Final = "token"
CONF_REFRESH_TOKEN: Final = "refresh_token"
CONF_DEVICE_ID: Final = "device_id"
CONF_BRAND: Final = "brand"
CONF_LANGUAGE: Final = "language"

# Options
CONF_SCAN_INTERVAL: Final = "scan_interval"
CONF_CLOUD_SCAN_INTERVAL: Final = "cloud_scan_interval"
CONF_STEP_BLOCKED: Final = "heating_mode_blocked"
CONF_STEP_ECO: Final = "heating_mode_eco"
CONF_STEP_BOOST: Final = "heating_mode_boost"
CONF_MODE_CIRCUITS: Final = "heating_mode_circuits"

DEFAULT_SCAN_INTERVAL: Final = 30
#: The cloud is polled far less often: Bosch's servers are shared, a request
#: there takes the round trip to the K30/K40 and back, and nothing it adds
#: beside a local source changes by the minute.
DEFAULT_CLOUD_SCAN_INTERVAL: Final = 300
MIN_SCAN_INTERVAL: Final = 10

PLATFORMS: Final = (
    "sensor",
    "binary_sensor",
    "number",
    "select",
    "switch",
    "button",
    "climate",
    "water_heater",
)

SERVICE_RESCAN: Final = "rescan"

#: Heating circuits an installation can have on the EMS bus.
CIRCUITS: Final[tuple[str, ...]] = ("hc1", "hc2", "hc3", "hc4")
