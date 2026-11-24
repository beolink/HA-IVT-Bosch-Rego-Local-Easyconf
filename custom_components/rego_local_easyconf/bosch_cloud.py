"""Bosch's cloud (POINTT), through the K30/K40 internet module.

IVT sells the K30 RF / K40 module as "IVT Anywhere II"; Bosch calls the same
service HomeCom Easy. The module talks out to Bosch and answers nothing on the
LAN (the K30 on the IVT Geo 608C this was built against has no open port), so
this is the one source that leaves the house, and it comes last in the order:
it fills in what the local sources lack, or is the way in when there is none.

Login is SingleKey ID's OAuth code flow with PKCE. SingleKey only accepts the
Bosch app's own redirect scheme, so the browser cannot hand the code back to
Home Assistant: the person logs in in a browser tab and pastes what the
browser shows - the redirect URL, the "Failed to launch ..." console line, or
the bare code - into the flow. IVT owners log in with the Bosch variant; that
is what IVT Anywhere II pumps (Geo 612 C on a K40, Air X on a K30) are seen
using. Refresh tokens are single use and rotate, so a refresh is serialised
and both new tokens are handed back for the config entry at once.

API facts from serbanb11/homecom_alt (MIT) and the bosch-homecom-hass issue
tracker, read 2026-11-24: base ``pointt-api/api/v1``, ``GET gateways/``,
``GET|PUT gateways/<id>/resource<path>`` with ``{"value": ...}``, and
``POST bulk`` taking up to 30 paths without the ``/resource`` prefix. Bosch
publishes no rate limit, but about 50 requests a cycle brought 429s on a
gateway and broke the official app with it, so the points are read in bulk,
at most 30 to a call, and by default every five minutes.
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import logging
import re
import secrets
import time
from typing import Any
from urllib.parse import unquote, urlencode

import aiohttp

from .const import CONF_DEVICE_ID, CONF_REFRESH_TOKEN, CONF_TOKEN, SOURCE_CLOUD
from .model import (
    BOOL,
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

AUTHORIZE_URL = "https://singlekey-id.com/auth/connect/authorize"
TOKEN_URL = "https://singlekey-id.com/auth/connect/token"
CLIENT_ID = "762162C0-FA2D-4540-AE66-6489F189FADC"
REDIRECTS = {
    "bosch": ("com.bosch.tt.dashtt.pointt://app/login", "tt_bsch"),
    "buderus": ("com.buderus.tt.dashtt://app/login", "tt_bud"),
}
SCOPE = (
    "openid email profile offline_access pointt.gateway.claiming pointt.gateway.removal "
    "pointt.gateway.list pointt.gateway.users pointt.gateway.resource.dashapp "
    "pointt.castt.flow.token-exchange bacon hcc.tariff.read"
)
API = "https://pointt-api.bosch-thermotechnology.com/pointt-api/api/v1/"
API_TIMEOUT = aiohttp.ClientTimeout(total=20)
#: Token calls get longer: a refresh token is spent the moment SingleKey
#: receives it, so a reply lost to a short timeout loses the session.
TOKEN_TIMEOUT = aiohttp.ClientTimeout(total=60)
BULK_MAX = 30
SENTINELS = {-32768.0, 32767.0, -3276.8, 3276.7}

#: Resource paths worth reading behind a K30/K40 on a heat pump. A path the
#: installation does not answer is dropped at setup.
PATHS: tuple[str, ...] = (
    "/system/sensors/temperatures/outdoor_t1",
    "/system/silentMode/enabled",
    "/system/awayMode/enabled",
    "/heatSources/actualSupplyTemperature",
    "/heatSources/returnTemperature",
    "/heatSources/actualModulation",
    "/heatSources/systemPressure",
    "/heatSources/numberOfStarts",
    "/heatSources/compressor/status",
    "/heatSources/Source/eHeater/status",
    "/heatSources/hs1/supplyFlowCondenserTemp",
    "/heatSources/hs1/brineCircuit/collectorInflowTemp",
    "/heatSources/hs1/brineCircuit/collectorOutflowTemp",
    "/heatSources/emon/totalConsumption",
    "/heatSources/emon/chConsumption",
    "/heatSources/emon/dhwConsumption",
    "/dhwCircuits/dhw1/actualTemp",
    "/dhwCircuits/dhw1/operationMode",
    "/dhwCircuits/dhw1/currentSetpoint",
    "/dhwCircuits/dhw1/charge",
    "/dhwCircuits/dhw1/chargeDuration",
    "/dhwCircuits/dhw1/singleChargeSetpoint",
    "/dhwCircuits/dhw1/temperatureLevels/high",
    "/dhwCircuits/dhw1/temperatureLevels/low",
    "/dhwCircuits/dhw1/temperatureLevels/eco",
    "/notifications",
)
CIRCUIT_LEAVES: tuple[str, ...] = (
    "operationMode",
    "roomtemperature",
    "currentRoomSetpoint",
    "manualRoomSetpoint",
    "supplyTemperatureSetpoint",
    "actualSupplyTemp",
    "suWiSwitchMode",
    "currentSuWiMode",
    "heatCurveMax",
    "heatCurveMin",
)

#: emonValue counters: what each field is, and the synthetic input total.
EMON_FIELDS = ("outputProduced", "compressor", "eheater")

#: Two-word values that are really on/off.
BOOL_WORDS = ({"on", "off"}, {"start", "stop"}, {"true", "false"})

#: The cloud's words for a few values, as EMS-ESP says them, so a role reads
#: and is written the same whichever source answers. The cloud calls the hot
#: water modes eco, low and high where IVT's display and EMS-ESP say Eco+, Eco
#: and Comfort (bosch-homecom-hass maps them the same way); its compressor
#: status says dhw where EMS-ESP says hot water.
_STATUS = {"dhw": "hot water", "pool_heat": "pool heating", "alarm": "compressor alarm"}
VALUE_MAPS: dict[str, dict[str, str]] = {
    "/dhwCircuits/dhw1/operationMode": {"Off": "off", "low": "eco", "high": "comfort", "eco": "eco+", "ownprogram": "auto"},
    "/heatSources/compressor/status": _STATUS,
    "/heatSources/Source/eHeater/status": _STATUS,
}


def to_ems(path: str, value: str) -> str:
    return VALUE_MAPS.get(path, {}).get(value, value)


def from_ems(path: str, value: str) -> str:
    for cloud, ems in VALUE_MAPS.get(path, {}).items():
        if ems == value:
            return cloud
    return value


UNITS = {"C": "°C", "K": "K", "kW": "kW", "W": "W", "kWh": "kWh", "bar": "bar", "%": "%", "mins": "min", "min": "min", "s": "s"}


# -- login -------------------------------------------------------------------


def new_login(brand: str = "bosch") -> dict[str, str]:
    """A fresh verifier, state and nonce, and the URL to open."""
    verifier = secrets.token_urlsafe(64)[:86]
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    redirect, style = REDIRECTS.get(brand, REDIRECTS["bosch"])
    state = secrets.token_urlsafe(16)
    query = {
        "redirect_uri": redirect,
        "client_id": CLIENT_ID,
        "response_type": "code",
        "prompt": "login",
        "state": state,
        "nonce": secrets.token_urlsafe(16),
        "scope": SCOPE,
        "code_challenge": challenge,
        "code_challenge_method": "S256",
        "style_id": style,
    }
    return {
        "verifier": verifier,
        "brand": brand,
        "url": f"{AUTHORIZE_URL}?{urlencode(query)}",
    }


_CODE = re.compile(r"[?&]code=([^&'\"\s]+)")


def code_from(pasted: str) -> str:
    """The code out of whatever the browser showed: URL, console line or the code alone."""
    text = (pasted or "").strip()
    match = _CODE.search(text)
    code = match.group(1) if match else text.strip("'\" ")
    return unquote(code)


async def async_exchange(session: aiohttp.ClientSession, code: str, verifier: str, brand: str) -> dict[str, Any]:
    redirect = REDIRECTS.get(brand, REDIRECTS["bosch"])[0]
    form = {
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect,
        "client_id": CLIENT_ID,
        "code_verifier": verifier,
    }
    return await _token_call(session, form)


async def _token_call(session: aiohttp.ClientSession, form: dict[str, str]) -> dict[str, Any]:
    try:
        async with session.post(TOKEN_URL, data=form, timeout=TOKEN_TIMEOUT) as response:
            text = await response.text()
            status = response.status
    except (aiohttp.ClientError, TimeoutError) as err:
        raise SourceError(f"SingleKey ID did not answer: {err}") from err
    if status != 200:
        raise AuthError(f"SingleKey ID refused the login ({status}): {text[:120]}")
    data = json.loads(text)
    if "access_token" not in data:
        raise AuthError("SingleKey ID answered without a token")
    return data


def token_expiry(token: str) -> float:
    """The access token's exp claim, read without verifying (it is only a timer)."""
    try:
        payload = token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        return float(json.loads(base64.urlsafe_b64decode(payload))["exp"])
    except (IndexError, KeyError, ValueError, TypeError):
        return 0.0


async def async_gateways(session: aiohttp.ClientSession, access_token: str) -> list[dict[str, Any]]:
    """The gateways on the account: [{"deviceId": "...", "deviceType": "k30"}]."""
    try:
        async with session.get(
            API + "gateways/", headers={"Authorization": f"Bearer {access_token}"}, timeout=API_TIMEOUT
        ) as response:
            if response.status in (401, 403):
                raise AuthError("The cloud refused the token")
            if response.status != 200:
                raise SourceError(f"The cloud answered {response.status} for the gateway list")
            data = await response.json(content_type=None)
    except (aiohttp.ClientError, TimeoutError) as err:
        raise SourceError(f"The cloud did not answer: {err}") from err
    return [g for g in data or [] if isinstance(g, dict) and g.get("deviceId")]


# -- values -------------------------------------------------------------------


def _kind_of(payload: dict[str, Any]) -> tuple[str, tuple[str, ...]]:
    kind = payload.get("type")
    allowed = tuple(str(v) for v in payload.get("allowedValues") or ())
    if kind == "floatValue":
        return NUMBER, ()
    if kind == "stringValue":
        if allowed and {a.lower() for a in allowed} in BOOL_WORDS:
            return BOOL, allowed
        return (ENUM, allowed) if allowed else (TEXT, ())
    return TEXT, ()


def points_from_payload(path: str, payload: dict[str, Any]) -> list[Point]:
    """The points one resource answer describes (an emonValue gives several)."""
    kind = payload.get("type")
    circuit = None
    match = re.match(r"^/(heatingCircuits|dhwCircuits)/(hc\d|dhw\d)/", path)
    if match:
        circuit = match.group(2)
    if kind == "emonValue":
        out = [
            Point(SOURCE_CLOUD, "heatpump", f"{path}#{field}", f"{path.rsplit('/', 1)[-1]} {field}", NUMBER,
                  unit="kWh", device_class="energy", state_class="total_increasing")
            for field in EMON_FIELDS
        ]
        out.append(
            Point(SOURCE_CLOUD, "heatpump", f"{path}#input", f"{path.rsplit('/', 1)[-1]} compressor+eheater",
                  NUMBER, unit="kWh", device_class="energy", state_class="total_increasing")
        )
        return out
    if kind == "errorList" or path == "/notifications":
        return [Point(SOURCE_CLOUD, "heatpump", path, "notifications", TEXT)]
    if kind not in ("floatValue", "stringValue"):
        return []
    point_kind, options = _kind_of(payload)
    unit = UNITS.get(str(payload.get("unitOfMeasure") or ""), payload.get("unitOfMeasure") or None)
    return [
        Point(
            source=SOURCE_CLOUD,
            device="heatpump",
            key=path,
            title=path,
            kind=point_kind,
            unit=unit if point_kind == NUMBER else None,
            device_class="temperature" if unit == "°C" and point_kind == NUMBER else None,
            state_class="measurement" if point_kind == NUMBER and not payload.get("writeable") else None,
            writable=bool(payload.get("writeable")),
            minimum=_num(payload.get("minValue")),
            maximum=_num(payload.get("maxValue")),
            step=_num(payload.get("stepSize")) or (0.5 if unit == "°C" else None),
            options=(
                tuple(to_ems(path, o) for o in options) if point_kind == ENUM else options if point_kind == BOOL else ()
            ),
            circuit=circuit,
        )
    ]


def _num(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def values_from_payload(path: str, payload: dict[str, Any], points: dict[str, Point]) -> dict[str, Value]:
    kind = payload.get("type")
    out: dict[str, Value] = {}
    if kind == "emonValue" or (f"{SOURCE_CLOUD}:heatpump:{path}#input" in points):
        fields = _emon_fields(payload)
        for field, value in fields.items():
            out[f"{SOURCE_CLOUD}:heatpump:{path}#{field}"] = value
        if "compressor" in fields:
            out[f"{SOURCE_CLOUD}:heatpump:{path}#input"] = fields["compressor"] + fields.get("eheater", 0.0)
        return out
    uid = f"{SOURCE_CLOUD}:heatpump:{path}"
    point = points.get(uid)
    if point is None:
        return out
    if path == "/notifications":
        out[uid] = fault_string(payload)
        return out
    value = payload.get("value")
    if point.kind == NUMBER:
        number = _num(value)
        out[uid] = None if number is None or number in SENTINELS else number
    elif point.kind == BOOL:
        out[uid] = to_bool(value) if str(value).lower() not in ("start", "stop") else str(value).lower() == "start"
    elif point.kind == ENUM and value is not None:
        out[uid] = to_ems(path, str(value))
    else:
        out[uid] = coerce(point, value)
    return out


def _emon_fields(payload: dict[str, Any]) -> dict[str, float]:
    values = payload.get("values")
    fields: dict[str, float] = {}
    if isinstance(values, dict):
        source = values
    elif isinstance(values, list):
        source = {}
        for row in values:
            if isinstance(row, dict):
                source.update(row)
    else:
        source = payload
    for field in EMON_FIELDS:
        number = _num(source.get(field))
        if number is not None:
            fields[field] = number
    return fields


def fault_string(payload: dict[str, Any]) -> str:
    """The active notification as EMS-ESP writes a fault, so faults.py reads both alike."""
    for row in payload.get("values") or []:
        if isinstance(row, dict) and row.get("act") == "A" and row.get("cat") in ("E", "F", "B", None):
            display, cause = row.get("dcd"), row.get("ccd")
            return f"{display}({cause}) - now" if cause not in (None, "") else f"{display} - now"
    return ""


def write_value(point: Point, value: Value) -> Any:
    if point.kind == BOOL:
        on = to_bool(value)
        words = {w.lower(): w for w in point.options}
        if "start" in words:
            return words["start"] if on else words["stop"]
        if "on" in words:
            return words["on"] if on else words["off"]
        return "on" if on else "off"
    if point.kind == NUMBER:
        number = float(value)  # type: ignore[arg-type]
        return int(number) if number.is_integer() else number
    return from_ems(point.key, str(value))


class BoschCloudSource:
    kind = SOURCE_CLOUD
    min_interval = 60.0

    def __init__(self, session: aiohttp.ClientSession, conf: dict[str, Any], on_tokens=None, borrow=None) -> None:
        self._session = session
        #: Where the login is borrowed: a callable returning the access token
        #: another integration keeps renewed (Bosch HomeCom), or None when this
        #: source holds a login of its own. A refresh token is single use, so
        #: two integrations cannot both renew one login; borrowing leaves the
        #: renewing to the one that owns it.
        self._borrow = borrow
        self.device_id = str(conf[CONF_DEVICE_ID])
        self._access = conf.get(CONF_TOKEN)
        self._refresh = conf.get(CONF_REFRESH_TOKEN)
        self._on_tokens = on_tokens
        self._token_lock = asyncio.Lock()
        self._points: dict[str, Point] = {}
        self.info: SourceInfo | None = None
        self.initial_values: dict[str, Value] = {}

    async def _token(self, force: bool = False) -> str:
        if self._borrow is not None:
            token = self._borrow()
            if not token:
                raise AuthError("Bosch HomeCom has no login for this gateway (removed or disabled?)")
            if token_expiry(token) - time.time() < 30:
                raise SourceError("Bosch HomeCom has not renewed its login yet; trying again at the next poll")
            return token
        async with self._token_lock:
            if not force and self._access and token_expiry(self._access) - time.time() > 300:
                return self._access
            if not self._refresh:
                raise AuthError("No refresh token; log in to the cloud again")
            data = await _token_call(
                self._session,
                {"grant_type": "refresh_token", "client_id": CLIENT_ID, "refresh_token": self._refresh},
            )
            self._access = data["access_token"]
            self._refresh = data.get("refresh_token", self._refresh)
            if self._on_tokens is not None:
                self._on_tokens({CONF_TOKEN: self._access, CONF_REFRESH_TOKEN: self._refresh})
            return self._access

    async def _call(self, method: str, url: str, body: Any = None) -> Any:
        for attempt in (0, 1):
            token = await self._token(force=attempt == 1)
            headers = {"Authorization": f"Bearer {token}"}
            if body is not None:
                headers["Content-Type"] = "application/json; charset=UTF-8"
            try:
                async with self._session.request(
                    method, url, headers=headers, data=None if body is None else json.dumps(body), timeout=API_TIMEOUT
                ) as response:
                    status = response.status
                    text = await response.text()
            except (aiohttp.ClientError, TimeoutError) as err:
                raise SourceError(f"The cloud did not answer: {err}") from err
            if status == 401 and attempt == 0:
                continue
            break
        if status in (401, 403) and method == "GET":
            raise AuthError(f"The cloud refused {url} ({status})")
        if status == 429:
            raise SourceError("The cloud asks to slow down (429)")
        if status in (502, 503, 504):
            raise SourceError(f"The cloud could not reach the gateway ({status})")
        if status >= 400:
            if method == "PUT":
                raise WriteRefused(f"The cloud refused the write ({status}): {text[:120]}")
            raise SourceError(f"The cloud answered {status}")
        return json.loads(text) if text.strip() else None

    async def _bulk(self, paths: list[str]) -> dict[str, dict]:
        """Up to 30 paths a call; the answers that came back, by path."""
        out: dict[str, dict] = {}
        for start in range(0, len(paths), BULK_MAX):
            chunk = paths[start : start + BULK_MAX]
            data = await self._call("POST", API + "bulk", [{"gatewayId": self.device_id, "resourcePaths": chunk}])
            for gateway in data or []:
                for row in gateway.get("resourcePaths") or []:
                    response = row.get("gatewayResponse") or {}
                    if row.get("serverStatus") == 200 and response.get("status") == 200:
                        payload = response.get("payload")
                        if isinstance(payload, dict) and payload:
                            out[row.get("resourcePath")] = payload
        return out

    async def async_info(self) -> SourceInfo:
        gateway = await self._call("GET", API + f"gateways/{self.device_id}/") or {}
        devices: list[DeviceDescription] = []
        system = (await self._bulk(["/system/info"])).get("/system/info") or {}
        for module in system.get("values") or []:
            if isinstance(module, dict):
                devices.append(
                    DeviceDescription(
                        key=str(module.get("ModuleHwIdentStr") or module.get("Id")),
                        name=str(module.get("ProductName") or module.get("ModuleHwIdentStr") or "module"),
                        model=module.get("ModuleHwIdentStr"),
                        sw_version=module.get("Ver"),
                        brand=None,
                    )
                )
        devices.insert(0, DeviceDescription(key="heatpump", name="heatpump", kind="heatpump"))
        self.info = SourceInfo(
            kind=SOURCE_CLOUD,
            unique_id=f"cloud-{self.device_id}",
            name=f"Bosch {str(gateway.get('deviceType') or 'gateway').upper()}",
            model=gateway.get("hardwareVersion") or gateway.get("deviceType"),
            sw_version=gateway.get("firmwareVersion"),
            devices=devices,
            extra={"device_type": gateway.get("deviceType")},
            can_write=True,
        )
        return self.info

    async def async_points(self) -> list[Point]:
        circuits = (await self._bulk(["/heatingCircuits"])).get("/heatingCircuits") or {}
        names = [
            str(ref.get("id")).rsplit("/", 1)[-1]
            for ref in circuits.get("references") or []
            if isinstance(ref, dict) and ref.get("id")
        ] or ["hc1"]
        paths = list(PATHS) + [f"/heatingCircuits/{hc}/{leaf}" for hc in names for leaf in CIRCUIT_LEAVES]
        answers = await self._bulk(paths)
        points: list[Point] = []
        for path, payload in answers.items():
            points.extend(points_from_payload(path, payload))
        self._points = {p.uid: p for p in points}
        self.initial_values = {}
        for path, payload in answers.items():
            self.initial_values.update(values_from_payload(path, payload, self._points))
        return points

    async def async_read(self, points: list[Point]) -> dict[str, Value]:
        paths = sorted({p.key.split("#", 1)[0] for p in points})
        answers = await self._bulk(paths)
        values: dict[str, Value] = {}
        for path, payload in answers.items():
            values.update(values_from_payload(path, payload, self._points))
        return values

    async def async_write(self, point: Point, value: Value) -> Value:
        if not point.writable:
            raise WriteRefused(f"{point.key} cannot be written")
        await self._call(
            "PUT", API + f"gateways/{self.device_id}/resource{point.key}", {"value": write_value(point, value)}
        )
        # The cloud lags a write; the value written stands until the next poll.
        return None

    async def async_close(self) -> None:
        """The session is Home Assistant's."""
