# IVT Bosch Rego Local Easyconf

IVT and Bosch heat pumps in Home Assistant, local first. One heat pump is one
installation, reached through every way in it has, and every value is read
from the best of them that has it:

| Order | Source | What it is | How it is reached |
|---|---|---|---|
| 1 | **EMS-ESP** | A BBQKees gateway (or any board running EMS-ESP32) on the pump's EMS bus | REST API on the LAN |
| 2 | **Husdata H60/H66** | Husdata's interface on the Rego controller's own bus: Rego 600/637, 800, 1000, 2000/3000 | HTTP API on the LAN |
| 3 | **Bosch cloud** | The K30 RF / K40 internet module (IVT Anywhere II, Bosch HomeCom Easy) | Bosch's POINTT API, SingleKey ID login |

A source further down does two things without being told: it fills in a value
the sources above it lack, and it stands in for one that has stopped
answering. The entities stay the same either way; each says in its `source`
attribute where its value came from just now.

It looks and works like [Nibe Local Easyconf](https://github.com/beolink/HA-Nibe-Easyconf)
and [CTC Local Easyconf](https://github.com/beolink/HA-CTC-Local-Easyconf):
names in Swedish or English, an explanation on every value, a heating mode for
an energy manager, a hot water boost, a thermostat per heating circuit, the
coefficient of performance, faults in words and a page of its own in the
sidebar.

Because EMS-ESP decodes the whole EMS family, the same works for Bosch
Compress, Buderus Logatherm, Nefit, Junkers and Worcester heat pumps behind an
EMS-ESP gateway; the names and roles were written for, and measured on, an IVT.

## Install

Needs Home Assistant 2026.9 or later (tested on 2026.9.2 and 2026.11.2).

**HACS** → Custom repositories → `https://github.com/beolink/HA-IVT-Bosch-Rego-Local-Easyconf`
as an Integration → download → restart Home Assistant.

**By hand**: copy `custom_components/rego_local_easyconf/` into your
`config/custom_components/` and restart.

## Set up

**Settings → Devices & services → Add integration → IVT Bosch Rego Local Easyconf.**

1. **Search the local network** (recommended). Home Assistant's own subnet is
   swept for an EMS-ESP gateway and a Husdata interface. An open port proves
   nothing, so a host only counts when it answers in its own words
   (`/api/system/info` for EMS-ESP, `/api/status` and `/api/alldata` for
   Husdata). What is found is listed, one of each kind ticked.
2. **EMS-ESP login.** Reading needs nothing; writing needs an admin user of the
   gateway's web interface (`admin` / `admin` from the factory), or an access
   token from *Security → Users*. Leave it empty and the gateway is read only;
   the login can be added later under *Configure*.
3. **The cloud, last.** Only after the local sources is Bosch's cloud offered,
   to fill in and stand in. When nothing was found locally it is the way in.
4. **Enter an address** is always on the menu.

An EMS-ESP gateway also announces itself (mDNS `_http._tcp` named `ems-esp`,
DHCP hostname `ems-esp`), so Home Assistant usually offers it on its own.

Under **Configure**: poll intervals, the heating mode's steps and circuits,
adding a local source or the cloud to an installation set up without it, the
EMS-ESP login, and removing a source.

### Husdata

Switch the API on in the interface's settings: `API_ENABLED=1` to read, `2` to
write as well, then restart the interface. Built from Husdata's documentation
and variable lists (C00, C05, C10, C15, C30, C35); **no H60 or H66 has been
measured yet**. What is known to vary is handled: negative values arriving as
unsigned 16-bit, H66 firmware 360702+ taking every write ×10, IDs moving
between firmware versions (the points are the IDs the interface actually
sends). Every write is read back, because Husdata answers "Ok" to anything
well formed.

### The cloud

SingleKey ID only accepts the Bosch app's own redirect, so the browser cannot
hand the login back to Home Assistant. The flow shows a link; log in in a new
tab, then open the browser's developer tools (F12 → Console) and paste the line
starting `Failed to launch 'com.bosch...` (or the address with `code=` in it).
The code works once and briefly. IVT Anywhere II uses the Bosch login.
Refresh tokens are single use and rotate; both are saved at once. The cloud is
polled every five minutes by default and read in bulk, at most 30 values a
call: Bosch publishes no limit, and about 50 requests a cycle have been seen
to lock a gateway and the official app out.

The K30/K40 has no local API: it is an outbound client of Bosch's cloud.
Buderus's KM50/KM100/KM200 and MB LAN 2 do answer on the LAN; they have a place
in the order but are not supported until one can be measured.

## What EMS-ESP gives

Measured on a BBQKees E32 V2.2 with EMS-ESP 3.8.6 on an IVT Geo 608C, Rego
3000 and MM100 (two heating circuits):

- `/api/<device>/entities` describes every value the gateway decodes - type,
  unit, range, options, whether it can be written - so nothing here keeps a map
  per model. Of 218 entries for the Geo's family, 161 carry a value on this
  pump; only those become entities (295 in all with the controller and the
  mixing module). About a hundred are on by default.
- A device's values take 0.3-0.6 s. EMS-ESP 3.8.3+ answers `429` to a request
  within 50 ms of the last, so requests are spaced 0.3 s and a 429 is retried.
- A write is only queued: the gateway sends it on the bus and reads the
  device back on its own, so the value is read again 1.5 s later and the entity
  shows what the pump holds.
- Write-only commands (`reset`, which offers a factory reset among its options,
  `chimneysweeper`, `mandefrost`) are left out on purpose.

If the gateway's own MQTT discovery is on, the same values also exist as
EMS-ESP's MQTT entities. Both can run; switch the gateway's discovery off once
this integration has taken over.

## Entities

**Roles** - the values every heat pump has, whichever way they are read:
outdoor, supply, return, brine in and out, hot gas, hot water, compressor
state, speed and power, aux heater, the energy counters, the fault, hot water
mode, boost, boost temperature, and per heating circuit the room setpoint,
calculated supply, curve offset, mode and limits. Hand-written short names and
explanations, on the pump's device.

**A source's own values** - everything else it sends, on the device it comes
from (the pump, the controller, the mixing module), named from a table where
one is written and from the source's own title otherwise. The ones a person
checking on the pump looks at are on by default from the first source; a
lower source's own values are created switched off.

Every entity carries `description`, `source`, `source_key` and `source_title`.

### Heating mode

A select, *Värmeläge* (*Heating mode*): `blocked`, `eco`, `normal`, `boost`,
the ids an energy manager such as [EMS Steward](https://github.com/beolink/ha-ems)
writes. A mode is a step from each heating circuit's normal room setpoint:
−3 °C blocked, −1.5 °C eco, +1 °C boost (EMS Steward's own set-backs;
changeable under *Configure*), written to **every** circuit with a writable
setpoint. Without a room sensor the setpoint still moves the Rego's heat curve:
on the Geo 608C the setpoints EMS Steward wrote moved the radiator circuit's
calculated supply between 25 and 33 °C and the floor circuit's between 22 and
26 °C. Heating is never switched off.

Normal is learned: the setpoint each circuit has when the select first sees
it. A setpoint changed anywhere else is taken as meant - in normal it becomes
the new normal; in another mode it holds until the mode next changes.
**Bind an energy manager to this select only while the pump is in its normal
setpoint**, or the learned normal will be a set-back.

### Hot water

*Varmvattenboost* (*Hot water boost*), the switch to bind as an energy
manager's water heater with "boost" ticked: the controller's extra hot water
(`dhw.charge` on a Rego 3000, `dhw/onetime` on the pump as fallback, `charge`
start/stop in the cloud). *Boost, temperatur* is the one-time charge's target;
on ground source 55-58 °C usually runs on the compressor alone, while 60-65 °C
can trip the hot gas protection and leave the rest to the immersion heater.

*Varmvatten* is a water heater with the controller's hot water modes and
"boost" as one more operation.

### Thermostats

*Värmekrets 1*, *2* ...: target = room setpoint, current = the circuit's room
sensor where one is fitted, HVAC mode = the circuit's mode (off / manual /
auto), presets = the heating mode.

### Faults

*Larm* reads the pump's last fault in words: `A01/5201: Varning Kabelbrott i
utetemp.givare T1`, with `display_code`, `cause_code`, `active`, `started`,
`ended` and the manufacturer's advice as attributes. 596 codes from IVT's,
Bosch's and Buderus's published lists ([docs/fault-codes.md](docs/fault-codes.md));
each row says whether its Swedish and English text is the manufacturer's or
translated here. EMS-ESP keeps the last fault after it cleared; the state then
says "Inget fel nu (senast ...)".

### Coefficient of performance

*COP, dygn*, *COP, år* and *COP, livstid* from the pump's two lifetime counters,
computed as in the NIBE and CTC integrations. On the Geo 608C: 28 650 kWh
delivered over 5 873 kWh used, 4.88.

## The page

Setting the integration up adds **Heatpump** to the sidebar: Overview,
Controls, Performance and All values, built from the entities' roles and
attributes, every value with its explanation. The same view is a card:

```yaml
type: custom:rego-easyconf-card
device_id: <optional>
```

## Development

```bash
<venv with homeassistant>/bin/python -m pytest
<venv with homeassistant>/bin/python scripts/smoke_real_ha.py
```

The smoke test sets the integration up under a real Home Assistant against a
stand-in EMS-ESP gateway serving the Geo 608C's recorded answers
(`tests/fixtures/emsesp_geo608c`), through the config flow, every platform, a
heating mode and a boost.

## Licence

[Apache License 2.0](LICENSE). No third-party code is copied: the cloud's
endpoints and login parameters were read from
[homecom_alt](https://github.com/serbanb11/homecom_alt) (MIT), EMS-ESP's
behaviour from its source (GPL-3.0), Husdata's from its documentation. The
fault texts are the manufacturers' published lists, with sources per row.
IVT, Bosch, Buderus and Husdata are their owners' marks; this project is not
made by, endorsed by or affiliated with any of them, and its icon is its own.
