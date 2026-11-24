# IVT/Bosch/Buderus heat pump fault codes via EMS-ESP: findings

Researched 2026-11-24. The table is `custom_components/rego_local_easyconf/faults.json` (596 rows); this report says where its texts come from. Section 1 works through the two faults the IVT Geo 608C the integration was built on reported that day, as an example of reading them.

## 1. What A01(5201) and A11(1037) mean

| EMS-ESP string | Device | Meaning | Category |
|---|---|---|---|
| `A01(5201) 24.11.2026 13:27 - now` | heat pump 0x08 (lastcode) | **Warning: outdoor temperature sensor T1 open circuit.** SV (IVT Geo 600): "Varning Kabelbrott i utetemp.givare T1". Raised when T1 resistance is above 179 kOhm (about −50 °C). Causes: T1 not installed, or the signal cable between the installer module and T1 is broken. If it persists, it becomes alarm **5203** (H01, "Alarm Outside temperature sensor T1 fault") after 3 faults within 3 h or 30 min continuously open or shorted. | warning (installer level, no buzzer) |
| `A11(1037) …` | controller 0x10, Rego 3000 / HMI800.2 (lastcode) | **Outdoor temperature sensor faulty, heating standby (substitute) mode active.** SV (IVT): "Utegivare defekt - ersättningsdrift värme aktiv". DE: "Außentemperaturfühler defekt, Ersatzbetrieb Heizung aktiv". In EMS plus this is fault category 14: the system keeps running with limited function, and the message clears when the cause is removed. The same code appears as A61–A68 when a heating-circuit controller reports it. | fault, customer level |

**Both codes point to the same root cause:** the heat pump's outdoor sensor T1 reads as an open circuit, so the controller has no outdoor temperature and heats in substitute mode. The ` - now` on 5201 means EMS-ESP read the log entry with no end date, so the fault was still active at the last read, starting 24.11.2026 13:27. Check the T1 wiring and connector on the installer module, and measure T1's resistance.

Sources:
- 5201 / 5203:
  - A/W semi monoblock service manual (EN), PDF p.16: https://bosch-de-de.boschhc-documents.com/download/pdf/file/6721823168#page=16
  - CS 7800i LW Servicehandbuch (DE), p.14: https://www.buderus.de/resource/blob/43038/e8bd293964d56cfcb105333032d98bf2/Servicehandbuch_CS_7800i_LW_LWM-DE-20230622.pdf#page=14
  - IVT larmkoder, Geo 600-serien: https://www.ivt.se/support/larmkoder/
- 1037:
  - A/W semi monoblock manual, p.12
  - CS 7800i LW, p.8
  - Compress 3000 AWS alarm list, p.1
  - IVT larmkoder (AirX, AirSplit, Vent; the Geo 600 list on the site has no 1037 entry)
  - Buderus EMS plus manual (FR), p.116 for A11 and p.156 for A61–A68: https://www.buderus.lu/resource/blob/78724/ffebb03865fa5b54eb8ffd11df93e6f4/manuel-d-entretien-ems-plus-data.pdf#page=116

## 2. How EMS-ESP builds these strings

Read from EMS-ESP32 `dev` (boiler.cpp @2d80f70, thermostat.cpp @4739684, 2026-11). The formats are identical on `main` (v3.9.1).

The display code always comes before `(`, and the number in parentheses is the cause code.

**Heat pump / boiler (`boiler/lastcode`)** keeps only the newest entry:
- **0xC2** (display code in bytes 5–7, cause code uint16 in bytes 8–9, start date in bytes 10–14, end date in bytes 15–19; the year byte has 0x80 set when the date is valid) and **0xC6** (same layout shifted one byte):
  - `XXX(n) dd.mm.yyyy hh:mm - dd.mm.yyyy hh:mm`: the fault has ended.
  - `XXX(n) dd.mm.yyyy hh:mm - now`: no valid end date, so the fault is still active.
  - `XXX(n) @uptime S - E min`: the system has no clock.
- **0x10/0x11** (older UBA): `XX(n) dd.mm.yyyy hh:mm (D min)`, with a 2-character display code and a duration. If the date is invalid the string is just `XX(n)`.
- EMS-ESP reads 0xC2/0xC6 at startup and again when the device broadcasts 0xBF (ErrorMessage). It does not poll. A `- now` therefore stays until the next 0xBF or restart. Whether the pump sends 0xBF when a fault clears is unverified.

**Controller (`thermostat/lastcode`)**, read from **0xC0** for RC300/UI800/Rego 3000:
- `A11(1037) dd.mm.yyyy hh:mm` when the end date is empty, meaning still active. This format has no ` - now`.
- `A11(1037) dd.mm.yyyy hh:mm-dd.mm.yyyy hh:mm` once ended. There are no spaces around the `-`.
- `A11(1037) N min` when there is no clock.
- 0x12/0x13 (older RC): `XX(n) dd.mm.yyyy hh:mm (D min)`.

**`thermostat/errorcode`** (0xA2) is the current error as `XXX(n)`.

**`servicecode` / `servicecodenumber`** (boiler/heat pump) is the status or service code as shown on the display, not the error log:
- From 0x18 UBAMonitorFast: 2 characters at offset 18–19 and a uint16 at offset 20.
- From 0xE4 UBAMonitorFastPlus (EMS+): 3 characters at offset 1–3 and a uint16 at offset 4.

What a heat pump actually reports in these fields is unverified.

Suggested parser:

```
^(?P<display>[^(]{1,3})\((?P<cause>-?\d+)\)(?:\s+(?P<start>\d\d\.\d\d\.\d{4} \d\d:\d\d)\s*-\s*(?P<end>now|\d\d\.\d\d\.\d{4} \d\d:\d\d)?|\s+(?P<start2>\d\d\.\d\d\.\d{4} \d\d:\d\d)(?:\s+\((?P<dur>\d+) min\))?|\s+@uptime.*|\s+\d+ min)?\s*$
```

Interpreting the parsed fields:
- Heat pump: active when `end == "now"`.
- Controller (0xC0): active when there is a start date and no end date.

Key the text lookup on the cause code. Use the display code only as extra information, because it varies by reporting device (1037 is A11 or A61–A68; 1010 is A11 on heat pumps but A01 on CS5800/6800i AW).

## 3. The JSON table

Main fields:
- `display_code`
- `cause_code` (int)
- `sv`, `en`
- `category`: `alarm`, `warning` or `info`
- `source`: a list of `URL#page=N (document)`

Extra fields:
- `sv_status` / `en_status`: `official (...)` or `translated (not official, from DE/FR/SV)`
- `level`: customer or installer
- `category_basis`
- `ems_plus_fault_category`
- `display_code_alternatives`
- `sv_detail`: the IVT cause/action text
- `en_detail`: the manual's alarm definition
- `de` / `fr`: original texts
- `appears_in`
- `notes`

Coverage (596 codes):
- **288 core codes** for the EMS-ESP product 172 family and its controller: Compress 7000i AW / WLW196i / IVT AirX, CS7800i LW / WSW196i.2, IVT Geo 312/500/600, Compress 3000 AWS / AirSplit, and IVT Vent. 225 have official English text and 271 have official Swedish text (191 from the Geo 600 list, the rest from other IVT products).
- **124 codes for CS5800/6800i AW (WLW176i/186i)**, a newer platform (BC400/UI800). The German text is official; English and Swedish are translated.
- **184 EMS plus controller and module codes** (RC300 family: circuits 5–8, DHW module, solar, heat pump 2 "Z2"). The French text is official; English and Swedish are translated. Whether these apply to HMI800/Rego 3000 is **unverified**.

How categories were set:
- Bosch has two groups: alarm and warning. Newer HMI firmware renamed "Warning" to "Info" (A/W semi monoblock manual, p.11).
- The category comes from the Alarm/Warning/Info word in the official texts. Where sources disagree, the majority decides; on a tie, English decides, then Swedish.
- Codes with no such word use the EMS plus fault category: 0–14 = alarm, 16 = warning, 18/20 = info.
- `info` is kept where the sources literally say "Info" (for example 5902, 6219/6220).
- Display codes in the manuals: A01 is mostly warnings, H01 is customer-level alarms, and A11/A2x/A3x/A6x are controller codes.

Texts are kept verbatim except for whitespace. That means:
- They include the "Alarm/Warning/Larm/Varning" prefix, which you can strip.
- Some are truncated exactly as on the HMI, for example 5272 "…EM is not oper" and 5527 "…cooling circ".
- IVT's web texts contain some copy-paste slips. These are flagged in `notes`, for example 5366, 5438 and 5507, where the IVT text says "Larm" but the manuals call it a warning.

## 4. Where Swedish or English is not official

**Swedish translated by me (not official):**
- 3021–3024
- 5240–5245
- 5371
- 5445
- 5633
- 5668/5669
- 6212/6213
- all 124 CS5800/6800i AW codes
- all 184 EMS plus codes

**English translated by me:**
- 3021–3024, 3082–3084, 3171, 3181, 5240–5245, 5370, 5371, 5900–5994, 6212/6213 and 6216–6220, translated from DE (CS7800i LW)
- 251, 258, 5596–5599, 5946–5948 and 6209, translated from SV (IVT web only)
- the CS5800 and EMS plus sets

Each row's `*_status` says which.

## 5. Sources

| Doc | Language, status | URL |
|---|---|---|
| Bosch Service Manual "A/W semi monoblock" (Compress 7000i AW/6000 AW, Buderus WLW196i, IVT AirX, Junkers SupraEco, Nefit Enviline) | EN, Bosch host, primary | https://bosch-de-de.boschhc-documents.com/download/pdf/file/6721823168 |
| Buderus Servicehandbuch CS 7800i LW/LWM, WSW196i.2 (2023-06-22, translated from an English original dated 2023-02-15) | DE, primary | https://www.buderus.de/resource/blob/43038/e8bd293964d56cfcb105333032d98bf2/Servicehandbuch_CS_7800i_LW_LWM-DE-20230622.pdf |
| IVT Geo 312 C / Compress 7000 12 LWM Service Manual 2016-06-14 | EN, Bosch/IVT document on a dealer host | https://jseducation.se/files/pages/service-manual--ivt-geo-312-c-bosch-compress-7000-.pdf |
| Bosch Alarm List A/W Split (8754) 2018-01-10 (Compress 3000 AWS / AirSplit) | EN, Bosch document on a dealer host | https://lvisawo.fi/data/dokumentit/bosch/vikakoodit/BOSCH-Vikakoodit-Ilma-vesilampopumppu-Compress-3000-AWS-Split.pdf |
| Buderus Servicehandbuch CS 5800/6800i AW, Logatherm WLW176i/186i | DE, primary | https://www.buderus.de/resource/blob/43040/2eb983f5edd38723b876cf1973ad0eba/Servicehandbuch_CS_5800_6800i_AW-_Logatherm_WLW176i.pdf |
| Buderus Logamatic EMS et EMS plus, Manuel de service | FR, primary | https://www.buderus.lu/resource/blob/78724/ffebb03865fa5b54eb8ffd11df93e6f4/manuel-d-entretien-ems-plus-data.pdf |
| IVT larmkoder: the page embeds 1,544 entries for Geo 600/500/312-412, AirX, AirSplit 200/300 and Vent 202/302/402 in `window.HEC_ErrorCodes` | SV, primary | https://www.ivt.se/support/larmkoder/ |
| EMS-ESP32 source: src/devices/boiler.cpp, thermostat.cpp, src/core/device_library.h | code | https://github.com/emsesp/EMS-ESP32 |

Not found or not used:
- IVT's own Swedish service manuals are behind the Support24 login.
- No English CS7800i LW manual is public.
- The HMI800 and Rego 3000 manuals found have no code list.
- The Worcester Bosch installer guides checked have no code tables.
- The BC400 manual (6721108150) lists only a few codes.

## 6. Unverified

- That the IVT Geo 608C is the same platform as the CS7800i LW / WSW196i.2. This is inferred from the EMS-ESP product list and IVT's Geo 500/600 grouping.
- That the EMS plus (RC300) extra codes are used by the HMI800 / Rego 3000.
- Whether a cleared heat pump fault triggers 0xBF, so that EMS-ESP replaces `- now`.
- What `servicecode` shows on a heat pump.
- All translated texts.
- The Z2 (second heat pump) codes, which come only from the French EMS plus manual.
