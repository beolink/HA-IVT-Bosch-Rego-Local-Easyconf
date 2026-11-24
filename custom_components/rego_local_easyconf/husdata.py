"""Husdata H60 and H66: IVT's older controllers, and the EMS ones, over HTTP.

Husdata's interfaces sit on the controller's own bus - the Rego 600's serial
port, the Rego 800/1000's CAN bus, the Rego 2000/3000's EMS bus - and give
every value as a variable ID over a small HTTP API:

* ``GET /api/alldata`` - every value, as raw integers keyed by a 4-digit hex ID;
* ``GET /api/set?idx=XXXX&val=N`` - a write, answered "Ok" whether or not the
  ID exists, so every write is read back;
* ``GET /api/status`` - firmware, the MAC address and the controller.

The API has to be switched on in the interface's settings (``API_ENABLED`` 1
to read, 2 to write too) and the interface restarted.

The first hex digit of an ID is its type: 0 temperature in tenths, 1 on/off,
2 a number, 3 percent in tenths, 5 kWh in tenths, 6 hours, 7 minutes, 8
degree minutes, 9 kW in tenths, C watts. An ID can be written exactly when its
second digit is 2 (Husdata's own firmware tests the same thing). The names,
units, scales and ranges per controller are Husdata's published variable
lists (husdata_ids.json, from online.husdata.se/h-docs/C00 ... C35.pdf, read
2026-11-24); a type-2 number's scale differs per ID and is null where Husdata
does not say.

Built from that documentation and Husdata's own example code only: no H60 or
H66 has been measured. What is known to vary, and handled here:

* the H60 sends negative numbers as unsigned 16-bit (``"0007": 65218`` is
  -31.8 °C), newer firmware as negative numbers - both are read;
* H66 firmware 360702 and later take every API write "x10", modes included;
  older firmware takes the raw value;
* IDs move between firmware versions, so the points are the IDs the interface
  actually sends, named from the list where the list knows them.
"""

from __future__ import annotations

import asyncio
import json
import logging
from pathlib import Path
import re
from typing import Any

import aiohttp

from .const import SOURCE_HUSDATA
from .model import BOOL, NUMBER, DeviceDescription, Point, SourceError, SourceInfo, Value, WriteRefused, to_bool

_LOGGER = logging.getLogger(__name__)

TIMEOUT = aiohttp.ClientTimeout(total=10)
IDS_FILE = Path(__file__).parent / "husdata_ids.json"

#: Default scale and unit per first hex digit.
TYPES: dict[str, tuple[float, str | None, str | None]] = {
    # digit: (scale, unit, device_class)
    "0": (0.1, "°C", "temperature"),
    "1": (1.0, None, None),
    "2": (1.0, None, None),
    "3": (0.1, "%", None),
    "4": (0.1, "A", "current"),
    "5": (0.1, "kWh", "energy"),
    "6": (1.0, "h", "duration"),
    "7": (1.0, "min", "duration"),
    "8": (1.0, "K*min", None),
    "9": (0.1, "kW", "power"),
    "A": (1.0, None, None),
    "B": (1.0, None, None),
    "C": (1.0, "W", "power"),
}
SIGNED = frozenset({"0", "2", "8"})
#: Readings that mean "no sensor": 0x8000, NIBE's 32758, Rego 600's -48.3 °C.
SENTINELS_RAW = frozenset({-32768, 32768, 32758})
SENTINEL_TEMPS = frozenset({-48.3})

CONTROLLERS = {
    "00": "IVT Rego 600/637",
    "05": "IVT Rego 400",
    "10": "IVT Rego 2000/3000",
    "15": "IVT Rego 5200",
    "30": "IVT Rego 1000",
    "35": "IVT Rego 800",
}

_IDS: dict[str, Any] | None = None


def ids() -> dict[str, Any]:
    global _IDS
    if _IDS is None:
        try:
            _IDS = json.loads(IDS_FILE.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _IDS = {}
    return _IDS


def guess_controller(keys: set[str]) -> str | None:
    """The controller whose list shares the most IDs with what the interface sends."""
    best, score = None, 0
    for code, table in ids().items():
        if code == "H66":
            continue
        overlap = len(keys & set(table["ids"]))
        if overlap > score:
            best, score = code, overlap
    return best


def controller_from_status(status: dict[str, Any]) -> str | None:
    h1 = str((status.get("status") or {}).get("H1ver") or "")
    if len(h1) >= 2 and h1[:2] in CONTROLLERS:
        return h1[:2]
    return None


def firmware_of(status: dict[str, Any]) -> tuple[str, str | None]:
    """("H60" | "H66", firmware) from /api/status."""
    inner = status.get("status") or {}
    for key, value in inner.items():
        match = re.fullmatch(r"(H6\d)ver", str(key), re.IGNORECASE)
        if match:
            return match.group(1).upper(), str(value)
    return "H60", None


def decode(idx: str, raw: Any, scale: float | None) -> Value:
    """A raw alldata value as what it measures."""
    if raw is None:
        return None
    try:
        number = int(raw)
    except (TypeError, ValueError):
        try:
            number = int(float(raw))
        except (TypeError, ValueError):
            return None
    digit = idx[:1].upper()
    if digit in SIGNED and 32768 <= number <= 65535:
        number -= 65536
    if number in SENTINELS_RAW:
        return None
    if digit == "1":
        return bool(number)
    value = number * (scale if scale is not None else TYPES.get(digit, (1.0, None, None))[0])
    value = round(value, 3)
    if digit == "0" and (value in SENTINEL_TEMPS or not -60 <= value <= 150):
        return None
    return value


def encode(idx: str, value: Value, scale: float | None, times_ten: bool) -> int:
    """The val= of a write: x10 on H66 360702+, the raw value before."""
    if idx[:1] == "1":
        return 1 if to_bool(value) else 0
    number = float(value)  # type: ignore[arg-type]
    if times_ten:
        return round(number * 10)
    return round(number / (scale or 1.0))


class HusdataSource:
    kind = SOURCE_HUSDATA
    min_interval = 15.0

    def __init__(self, session: aiohttp.ClientSession, host: str, variant: str | None = None) -> None:
        self._session = session
        self.host = host.strip().rstrip("/")
        self.variant = variant
        self.firmware: str | None = None
        self.controller: str | None = None
        self._scales: dict[str, float | None] = {}
        self._lock = asyncio.Lock()
        self.info: SourceInfo | None = None
        self.initial_values: dict[str, Value] = {}

    @property
    def base(self) -> str:
        return self.host if self.host.startswith("http") else f"http://{self.host}"

    async def _get(self, path: str) -> Any:
        async with self._lock:
            try:
                async with self._session.get(self.base + path, timeout=TIMEOUT) as response:
                    status = response.status
                    text = await response.text()
            except (aiohttp.ClientError, TimeoutError) as err:
                raise SourceError(f"Husdata at {self.host} did not answer {path}: {err}") from err
        if status != 200:
            raise SourceError(f"Husdata at {self.host} answered {status} to {path}")
        try:
            return json.loads(text)
        except ValueError as err:
            raise SourceError(f"Husdata at {self.host} answered {path} with {text[:60]!r}") from err

    @property
    def times_ten(self) -> bool:
        if self.variant != "H66" or not self.firmware:
            return False
        try:
            return int(re.sub(r"\D", "", self.firmware)[:6]) >= 360702
        except ValueError:
            return False

    async def async_info(self) -> SourceInfo:
        status = await self._get("/api/status")
        if not isinstance(status, dict) or "status" not in status:
            raise SourceError(f"{self.host} does not answer like a Husdata interface")
        self.variant, self.firmware = firmware_of(status)
        inner = status.get("status") or {}
        mac = str(inner.get("mac") or "").lower().replace(":", "")
        self.controller = controller_from_status(status)
        api = str((status.get("config") or {}).get("API_ENABLED", "")).strip()
        self.info = SourceInfo(
            kind=SOURCE_HUSDATA,
            unique_id=f"husdata-{mac or self.host}",
            name=f"Husdata {self.variant}",
            model=self.variant,
            sw_version=self.firmware,
            host=self.host,
            devices=[DeviceDescription(key="heatpump", name=CONTROLLERS.get(self.controller or "", "IVT"), kind="heatpump",
                                       model=CONTROLLERS.get(self.controller or ""), brand="IVT")],
            extra={"api_enabled": api, "controller": self.controller, "mac": mac},
            can_write=api in ("2", ""),
        )
        return self.info

    async def async_points(self) -> list[Point]:
        data = await self._get("/api/alldata")
        if not isinstance(data, dict):
            raise SourceError("Husdata's alldata is not a list of values; is the API switched on (API_ENABLED)?")
        keys = {str(k).upper() for k in data}
        if self.controller is None:
            self.controller = guess_controller(keys)
            if self.info is not None and self.controller:
                self.info.devices[0].model = CONTROLLERS.get(self.controller)
        table = (ids().get(self.controller or "") or {}).get("ids", {})
        extra = (ids().get("H66") or {}).get("ids", {})
        points: list[Point] = []
        self.initial_values = {}
        for idx in sorted(keys):
            meta = table.get(idx) or extra.get(idx) or {}
            digit = idx[:1]
            scale, unit, device_class = TYPES.get(digit, (1.0, None, None))
            if "scale" in meta:
                scale = meta["scale"]
            self._scales[idx] = scale
            unit = meta.get("unit") or unit
            writable = len(idx) == 4 and idx[1] == "2"
            options = meta.get("options") or []
            point = Point(
                source=SOURCE_HUSDATA,
                device="heatpump",
                key=idx,
                title=meta.get("name_en") or f"Husdata {idx}",
                kind=BOOL if digit == "1" else NUMBER,
                unit=None if digit == "1" else unit,
                device_class=None if digit == "1" else device_class,
                state_class=(
                    "total_increasing" if digit in ("5", "6") or idx in ("2C61",)
                    else ("measurement" if digit in ("0", "3", "4", "9", "C") and not writable else None)
                ),
                writable=writable,
                minimum=float(meta["min"]) if "min" in meta else (float(min(options)) if options else None),
                maximum=float(meta["max"]) if "max" in meta else (float(max(options)) if options else None),
                step=0.5 if unit == "°C" and writable else 1.0,
            )
            points.append(point)
            self.initial_values[point.uid] = decode(idx, data.get(idx, data.get(idx.lower())), scale)
        # Total consumption is the compressor's and the aux heater's together,
        # as on the EMS bus; Husdata lists them apart.
        if {"5C54", "5C57"} <= keys:
            total = Point(SOURCE_HUSDATA, "heatpump", "5C54+5C57", "Compr. + aux consumption", NUMBER,
                          unit="kWh", device_class="energy", state_class="total_increasing")
            points.append(total)
            self.initial_values[total.uid] = self._sum(self.initial_values)
        return points

    def _sum(self, values: dict[str, Value]) -> Value:
        a = values.get(f"{SOURCE_HUSDATA}:heatpump:5C54")
        b = values.get(f"{SOURCE_HUSDATA}:heatpump:5C57")
        return None if a is None or b is None else round(float(a) + float(b), 1)

    async def async_read(self, points: list[Point]) -> dict[str, Value]:
        data = await self._get("/api/alldata")
        if not isinstance(data, dict):
            raise SourceError("Husdata's alldata is not a list of values")
        upper = {str(k).upper(): v for k, v in data.items()}
        if upper and all(v in (0, "0") for v in upper.values()):
            # Right after the interface restarts it can send all zeros.
            raise SourceError("Husdata sent only zeros (restarting?)")
        values: dict[str, Value] = {}
        for idx, raw in upper.items():
            values[f"{SOURCE_HUSDATA}:heatpump:{idx}"] = decode(idx, raw, self._scales.get(idx))
        values[f"{SOURCE_HUSDATA}:heatpump:5C54+5C57"] = self._sum(values)
        return values

    async def async_write(self, point: Point, value: Value) -> Value:
        if not point.writable:
            raise WriteRefused(f"{point.key} cannot be written")
        val = encode(point.key, value, self._scales.get(point.key), self.times_ten)
        answer = await self._get(f"/api/set?idx={point.key}&val={val}")
        if isinstance(answer, dict) and str(answer.get("response", "")).lower() not in ("ok", ""):
            raise WriteRefused(f"Husdata refused {point.key}={val}: {answer.get('response')}")
        await asyncio.sleep(2)
        values = await self.async_read([point])
        return values.get(point.uid)

    async def async_close(self) -> None:
        """The session is Home Assistant's."""


async def probe(session: aiohttp.ClientSession, host: str):
    """A Found for a Husdata interface at ``host`` whose API answers, else None."""
    from .scanner import Found

    source = HusdataSource(session, host)
    try:
        info = await source.async_info()
    except SourceError:
        return None
    try:
        points = await source.async_points()
    except SourceError:
        points = []
    controller = CONTROLLERS.get(source.controller or "", "IVT")
    label = f"Husdata {source.variant} {source.firmware or ''} på {host}: {controller}".replace("  ", " ")
    if not points:
        label += " (API avstängt? Sätt API_ENABLED=2)"
    return Found(
        kind=SOURCE_HUSDATA,
        host=host,
        label=label,
        unique_id=info.unique_id,
        details={"brand": "IVT", "controller": source.controller, "conf": {"variant": source.variant}},
    )

