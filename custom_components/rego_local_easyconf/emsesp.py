"""EMS-ESP over its REST API: a BBQKees gateway, or any board running EMS-ESP32.

EMS-ESP sits on the heat pump's EMS bus and decodes what the pump, its
controller (Rego 1000/2000/3000, HMI800, UI800 ...) and the mixing modules
send each other. Its REST API describes every value it decodes: GET
``/api/<device>/entities`` gives, per entity, the type, unit, range, options and
whether it can be written. That is the map, from the gateway itself - nothing
here keeps a list per model.

Measured on a BBQKees E32 V2.2 with EMS-ESP 3.8.6 on an IVT Geo 608C with a
Rego 3000 and an MM100 (2026-11-24):

* a device's values take 0.3-0.6 s to fetch (``/api/boiler`` 2.9 kB in 0.5 s);
* requests sent back to back are answered ``429 Too Many Requests``; with
  0.3 s between them every one went through, so requests here are serialised
  with a gap and a 429 is retried after a pause;
* reads need no token; writes need the bearer token of an admin user of the
  web interface, which ``POST /rest/signIn`` hands out for the user name and
  password. It carries no expiry (HS256 over the user name and admin flag,
  signed with the Super User password), so it is kept, and the user name and
  password only to sign in again if it is refused. EMS-ESP 3.10 will want a
  token for reads too, so one is sent with every request once there is one;
* a write is only queued: the gateway sends it on the bus and reads the device
  back on its own, so the value is read again after a moment;
* ``/api/<device>`` nests circuit values (``{"hc1": {"seltemp": 18}}``) while
  ``/entities`` keys them ``hc1.seltemp``; the two are joined on the latter.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

import aiohttp

from .const import SOURCE_EMSESP
from .model import (
    BOOL,
    COMMAND,
    ENUM,
    NUMBER,
    TEXT,
    AuthError,
    DeviceDescription,
    Point,
    SourceError,
    SourceInfo,
    Value,
    WriteRefused,
    coerce,
    to_bool,
)

_LOGGER = logging.getLogger(__name__)

#: Time between two requests to the gateway. EMS-ESP 3.8.3+ answers 429 to a
#: GET that arrives within 50 ms of the previous request finishing
#: (WebAPIService.cpp); 0.3 s was measured to be enough on a busy gateway.
REQUEST_GAP = 0.3
TIMEOUT = aiohttp.ClientTimeout(total=20)
RETRIES_ON_BUSY = 4

#: Device types EMS-ESP reports that carry no values of their own here.
SKIPPED_TYPES = frozenset({"gateway", "controller", "connect", "alert", "extension", "custom", "scheduler"})

#: Device types whose /api/<type> call lists sensors the user added, without
#: an /entities description.
SENSOR_TYPES = frozenset({"temperaturesensor", "analogsensor"})

_TYPE_MAP = {"number": NUMBER, "enum": ENUM, "boolean": BOOL, "string": TEXT, "command": COMMAND}


def flatten(values: dict[str, Any], prefix: str = "") -> dict[str, Any]:
    """``{"hc1": {"seltemp": 18}}`` as ``{"hc1.seltemp": 18}``."""
    flat: dict[str, Any] = {}
    for key, value in values.items():
        name = f"{prefix}{key}"
        if isinstance(value, dict):
            flat.update(flatten(value, f"{name}."))
        else:
            flat[name] = value
    return flat


def points_from_entities(device: str, entities: dict[str, dict]) -> tuple[list[Point], dict[str, Any]]:
    """The points of one device from its ``/entities`` answer, and the values it carried.

    Only entities that are readable and carry a value become points: the list
    holds everything EMS-ESP can decode for the device family (218 entries for
    the Geo's family, of which the Geo 608C fills 161), and one that has never
    carried a value is a feature this unit does not have. Write-only commands
    (``reset``, ``chimneysweeper``, ``mandefrost``) are left out on purpose:
    ``reset`` offers a factory reset among its options, and nothing here should
    put that one tap away from a dashboard.
    """
    points: list[Point] = []
    values: dict[str, Any] = {}
    for key, meta in entities.items():
        if not isinstance(meta, dict):
            continue
        kind = _TYPE_MAP.get(str(meta.get("type")), TEXT)
        if kind == COMMAND or meta.get("readable") is False:
            continue
        if "value" not in meta or meta.get("value") is None:
            continue
        if meta.get("visible") is False:
            # Hidden by the user in EMS-ESP's own customisation.
            continue
        writable = bool(meta.get("writeable"))
        options = tuple(str(o) for o in meta.get("enum") or ())
        if kind == BOOL:
            options = ()
        circuit = meta.get("circuit") or None
        point = Point(
            source=SOURCE_EMSESP,
            device=device,
            key=key,
            title=str(meta.get("fullname") or key),
            kind=kind,
            unit=meta.get("uom") or None,
            device_class=meta.get("device_class") or None,
            state_class=meta.get("state_class") or None,
            writable=writable,
            minimum=_float(meta.get("min")),
            maximum=_float(meta.get("max")),
            step=_step(meta),
            options=options,
            circuit=circuit,
        )
        points.append(point)
        values[point.uid] = coerce(point, meta.get("value"))
    return points, values


def _float(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _step(meta: dict) -> float | None:
    """EMS-ESP gives no step; setpoints in °C go in halves, the rest in units."""
    if meta.get("type") != "number":
        return None
    if meta.get("uom") == "°C" and meta.get("writeable"):
        return 0.5
    return 1.0


def write_path(point: Point) -> str:
    """``/api/thermostat/hc1/seltemp`` for ``hc1.seltemp``; ``/api/boiler/selflowtemp`` otherwise."""
    return f"/api/{point.device}/" + point.key.replace(".", "/")


def write_body(point: Point, value: Value) -> dict[str, Any]:
    """The value as EMS-ESP takes it: numbers as numbers, the rest as its own words."""
    if point.kind == BOOL:
        return {"value": "on" if to_bool(value) else "off"}
    if point.kind == NUMBER:
        number = float(value)  # type: ignore[arg-type]
        return {"value": int(number) if number.is_integer() else number}
    if point.kind == COMMAND:
        return {"value": value if value is not None else ""}
    return {"value": str(value)}


class EmsEspSource:
    """One EMS-ESP gateway."""

    kind = SOURCE_EMSESP
    min_interval = 10.0

    def __init__(
        self,
        session: aiohttp.ClientSession,
        host: str,
        *,
        token: str | None = None,
        username: str | None = None,
        password: str | None = None,
    ) -> None:
        self._session = session
        self.host = host.strip().rstrip("/")
        self._token = token or None
        self._username = username or None
        self._password = password or None
        self._lock = asyncio.Lock()
        self._last_request = 0.0
        #: device type -> list of points, after async_points.
        self._devices: dict[str, list[Point]] = {}
        #: Values that came with the /entities answer, so the first poll is free.
        self.initial_values: dict[str, Value] = {}
        self.info: SourceInfo | None = None
        #: The gateway's "bypass access token authorization on API calls".
        self._no_token = False

    @property
    def base_url(self) -> str:
        host = self.host
        if host.startswith(("http://", "https://")):
            return host
        return f"http://{host}"

    @property
    def can_write(self) -> bool:
        return bool(self._token or (self._username and self._password))

    @property
    def token(self) -> str | None:
        return self._token

    async def _request(self, method: str, path: str, *, json: Any = None, auth: bool = False) -> Any:
        """One request, spaced from the last and retried while the gateway says it is busy."""
        headers = {"Accept": "application/json"}
        if auth and not self._token:
            await self.async_sign_in()
        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
        for attempt in range(RETRIES_ON_BUSY + 1):
            async with self._lock:
                wait = REQUEST_GAP - (time.monotonic() - self._last_request)
                if wait > 0:
                    await asyncio.sleep(wait)
                try:
                    async with self._session.request(
                        method, self.base_url + path, json=json, headers=headers, timeout=TIMEOUT
                    ) as response:
                        status = response.status
                        text = await response.text()
                except (aiohttp.ClientError, TimeoutError) as err:
                    raise SourceError(f"EMS-ESP at {self.host} did not answer {path}: {err}") from err
                finally:
                    self._last_request = time.monotonic()
            if status == 429 and attempt < RETRIES_ON_BUSY:
                await asyncio.sleep(0.5 * (attempt + 1))
                continue
            break
        if status in (401, 403):
            if auth and self._username and self._password and attempt == 0:
                # A token that expired or was revoked: sign in again, once.
                self._token = None
            raise AuthError(f"EMS-ESP at {self.host} refused {path} ({status})")
        try:
            data = _json(text)
        except ValueError as err:
            raise SourceError(f"EMS-ESP at {self.host} answered {path} with {text[:80]!r}") from err
        if status >= 400:
            message = data.get("message") if isinstance(data, dict) else text
            if method == "POST":
                raise WriteRefused(f"EMS-ESP refused {path}: {message}")
            raise SourceError(f"EMS-ESP at {self.host} answered {path} with {status}: {message}")
        return data

    async def async_sign_in(self) -> str:
        """A bearer token from the web interface's user name and password."""
        if not (self._username and self._password):
            raise AuthError("EMS-ESP needs a user name and password, or a token, to write")
        try:
            async with self._lock:
                async with self._session.post(
                    self.base_url + "/rest/signIn",
                    json={"username": self._username, "password": self._password},
                    timeout=TIMEOUT,
                ) as response:
                    status = response.status
                    text = await response.text()
                self._last_request = time.monotonic()
        except (aiohttp.ClientError, TimeoutError) as err:
            raise SourceError(f"EMS-ESP at {self.host} did not answer the sign-in: {err}") from err
        if status != 200:
            raise AuthError(f"EMS-ESP at {self.host} refused the sign-in ({status})")
        data = _json(text)
        token = data.get("access_token") if isinstance(data, dict) else None
        if not token:
            raise AuthError("EMS-ESP's sign-in answered without a token")
        self._token = str(token)
        return self._token

    async def async_info(self) -> SourceInfo:
        data = await self._request("GET", "/api/system/info")
        if not isinstance(data, dict) or "system" not in data:
            raise SourceError(f"{self.host} does not answer like EMS-ESP")
        system = data.get("system") or {}
        network = data.get("network") or {}
        devices = [
            _describe(device, str(device.get("type") or ""))
            for device in data.get("devices") or []
            if device.get("type")
        ]
        mac = network.get("MAC") or network.get("mac") or system.get("MAC")
        hostname = network.get("hostname") or "ems-esp"
        info = SourceInfo(
            kind=SOURCE_EMSESP,
            unique_id=_unique_id(mac, hostname, self.host),
            name=hostname,
            model=system.get("model") or system.get("boardProfile") or "EMS-ESP",
            sw_version=system.get("version"),
            host=self.host,
            devices=devices,
            extra={
                "bus": (data.get("bus") or {}).get("busStatus"),
                "bus_protocol": (data.get("bus") or {}).get("busProtocol"),
                "mqtt_ha_discovery": (data.get("mqtt") or {}).get("haEnabled"),
                "readonly_mode": (data.get("settings") or {}).get("readonlyMode"),
                "no_token_api": (data.get("settings") or {}).get("noTokenApi"),
                "locale": (data.get("settings") or {}).get("locale"),
            },
            can_write=self.can_write or bool((data.get("settings") or {}).get("noTokenApi")),
        )
        self._no_token = bool((data.get("settings") or {}).get("noTokenApi"))
        self.info = info
        return info

    async def async_points(self) -> list[Point]:
        """Every value the gateway decodes, from each device's own description."""
        if self.info is None:
            await self.async_info()
        assert self.info is not None
        points: list[Point] = []
        self._devices = {}
        self.initial_values = {}
        for device in self.info.devices:
            kind = device.kind or ""
            if kind in SKIPPED_TYPES or not kind:
                continue
            if kind in SENSOR_TYPES:
                found = await self._sensor_points(kind)
            else:
                entities = await self._request("GET", f"/api/{kind}/entities")
                if not isinstance(entities, dict):
                    continue
                found, values = points_from_entities(kind, entities)
                self.initial_values.update(values)
            if found:
                self._devices[kind] = found
                points.extend(found)
        return points

    async def _sensor_points(self, kind: str) -> list[Point]:
        """The user's own Dallas and analog sensors: names they gave, numbers."""
        data = await self._request("GET", f"/api/{kind}")
        if not isinstance(data, dict):
            return []
        points = []
        for key, value in flatten(data).items():
            point = Point(
                source=SOURCE_EMSESP,
                device=kind,
                key=key,
                title=key.replace("_", " "),
                kind=NUMBER if not isinstance(value, str) else TEXT,
                unit="°C" if kind == "temperaturesensor" else None,
                device_class="temperature" if kind == "temperaturesensor" else None,
                state_class="measurement" if not isinstance(value, str) else None,
            )
            points.append(point)
            self.initial_values[point.uid] = coerce(point, value)
        return points

    async def async_read(self, points: list[Point]) -> dict[str, Value]:
        """One request per device that has a point asked for."""
        wanted: dict[str, list[Point]] = {}
        for point in points:
            wanted.setdefault(point.device, []).append(point)
        values: dict[str, Value] = {}
        errors: list[Exception] = []
        for device, device_points in wanted.items():
            try:
                data = await self._request("GET", f"/api/{device}")
            except SourceError as err:
                errors.append(err)
                continue
            if not isinstance(data, dict):
                continue
            flat = flatten(data)
            for point in device_points:
                if point.key in flat:
                    values[point.uid] = coerce(point, flat[point.key])
        if errors and not values:
            raise errors[0]
        return values

    async def async_write(self, point: Point, value: Value) -> Value:
        if not point.writable:
            raise WriteRefused(f"{point.key} on the {point.device} cannot be written")
        needs_auth = not self._no_token
        try:
            await self._request("POST", write_path(point), json=write_body(point, value), auth=needs_auth)
        except AuthError:
            if not (self._username and self._password):
                raise
            # One retry with a fresh token.
            self._token = None
            await self._request("POST", write_path(point), json=write_body(point, value), auth=True)
        if point.kind == COMMAND:
            return None
        # The gateway sends the write on the bus and fetches the device's
        # telegram again; give it a moment before reading what it now holds.
        await asyncio.sleep(1.5)
        return await self.async_read_one(point)

    async def async_read_one(self, point: Point) -> Value:
        data = await self._request("GET", write_path(point))
        if isinstance(data, dict) and "value" in data:
            return coerce(point, data["value"])
        return None

    async def async_close(self) -> None:
        """The session is Home Assistant's; nothing of ours to close."""


def _json(text: str) -> Any:
    import json

    if not text.strip():
        return {}
    return json.loads(text)


def _describe(device: dict, kind: str) -> DeviceDescription:
    brand = (device.get("brand") or "").strip() or None
    return DeviceDescription(
        key=kind,
        name=str(device.get("name") or kind),
        brand=brand,
        model=str(device.get("name") or "") or None,
        sw_version=device.get("version"),
        address=device.get("deviceID"),
        kind=kind,
        serial=None,
    )


def _unique_id(mac: str | None, hostname: str | None, host: str) -> str:
    if mac:
        return "emsesp-" + str(mac).lower().replace(":", "").replace("-", "")
    return f"emsesp-{(hostname or host).lower()}"


def looks_like_emsesp(data: Any) -> bool:
    """Whether a /api/system/info answer is EMS-ESP's."""
    return (
        isinstance(data, dict)
        and isinstance(data.get("system"), dict)
        and "version" in data["system"]
        and isinstance(data.get("devices"), list)
    )
