/* IVT Bosch Rego Local Easyconf — the heat pump on one page: control it, see
 * how it is doing, and read every value with its explanation.
 *
 * Served by the integration at /rego_local_easyconf/rego-easyconf-card.js and
 * used two ways:
 *
 *   - as the sidebar panel the integration registers on its own, so a user
 *     gets the page without editing any dashboard;
 *   - as a card for their own dashboards (the resource is auto-registered on
 *     storage-mode Lovelace):
 *
 *       type: custom:rego-easyconf-card
 *       device_id: <optional, the pump's device when there is more than one>
 *       tabs: [overview, controls, performance, values]  # optional, the default
 *
 * One installation spans several Home Assistant devices: the pump, which
 * carries every role, and the devices hung under it with via_device - the
 * controller, a mixing module, each source's gateway. A card given the pump's
 * device_id shows the pump's entities and those of the devices under it.
 *
 * The page has four tabs:
 *
 *   1. **Overview.** What the pump is doing right now: the alarm, its
 *      operating state, the heating mode and the day's coefficient of
 *      performance, which sources answer, the few controls an owner reaches
 *      for, one graph of the last day, and the key figures.
 *   2. **Controls.** Everything writable, as the thing it is - a dropdown, a
 *      slider, a toggle - grouped by what it does to the house: heating, hot
 *      water, operation.
 *   3. **Performance.** Graphs, built from Home Assistant's own history and
 *      statistics cards through `loadCardHelpers`. They are a bonus: if that
 *      ever goes away the tab stays empty and the rest still works.
 *   4. **All values.** The full list with the filter, each row with its
 *      explanation and the source it was read from.
 *
 * Everything is found by what the integration says about its entities, never
 * by their names: a role entity carries `role` ("outdoor_temp") and `group`
 * ("temperatures"), every entity `source`, `source_key` and `source_title`.
 * Those attributes vanish while an entity is unavailable, so the page keeps
 * the last ones it saw.
 *
 * The explanation is shown on hover through the title attribute, and also on
 * tap, written out under the row: a title attribute alone is invisible on a
 * phone and to a screen reader.
 *
 * Every string from Home Assistant goes into the page as text, never as HTML.
 *
 * The pure helpers at the top are loaded by tests/test_card.py in node, which
 * is why the custom elements are only defined in a browser.
 */

const DOMAIN = "rego_local_easyconf";

const TEXT = {
  sv: {
    temperatures: "Temperaturer",
    compressor: "Kompressor",
    energy: "Energi",
    heating: "Värme",
    hotwater: "Varmvatten",
    status: "Status",
    sensor: "Mätvärden",
    config: "Inställningar",
    diagnostic: "Diagnostik",
    filter: "Filtrera…",
    empty: "Inga entiteter från IVT Bosch Rego Local Easyconf ännu.",
    none: "Inget matchar filtret.",
    details: "Mer info",
    press: "Kör",
    unavailable: "ej tillgänglig",
    on: "på",
    off: "av",
    title: "Värmepump",
    overview: "Översikt",
    controls: "Styrning",
    performance: "Prestanda",
    values: "Alla värden",
    quick: "Snabbstyrning",
    now: "Just nu",
    readings: "Nyckeltal",
    operation: "Drift",
    other: "Övrigt",
    graphTemps: "Temperaturer, ett dygn",
    graphCompressor: "Kompressorn, ett dygn",
    graphEnergy: "Energi per dygn",
    graphCop: "Värmefaktor per dygn",
    noControls: "Inget styrbart värde är påslaget.",
    explain: "Förklaring",
    source: "Källa",
    sources: {
      emsesp: "EMS-ESP",
      husdata: "Husdata",
      bosch_local: "Bosch-gateway",
      cloud: "Bosch-molnet",
    },
    modes: { blocked: "Spärrad", eco: "Eko", normal: "Normal", boost: "Boost" },
  },
  en: {
    temperatures: "Temperatures",
    compressor: "Compressor",
    energy: "Energy",
    heating: "Heating",
    hotwater: "Hot water",
    status: "Status",
    sensor: "Readings",
    config: "Settings",
    diagnostic: "Diagnostics",
    filter: "Filter…",
    empty: "No entities from IVT Bosch Rego Local Easyconf yet.",
    none: "Nothing matches the filter.",
    details: "More info",
    press: "Run",
    unavailable: "unavailable",
    on: "on",
    off: "off",
    title: "Heat pump",
    overview: "Overview",
    controls: "Controls",
    performance: "Performance",
    values: "All values",
    quick: "Quick controls",
    now: "Right now",
    readings: "Key readings",
    operation: "Operation",
    other: "Other",
    graphTemps: "Temperatures, 24 hours",
    graphCompressor: "The compressor, 24 hours",
    graphEnergy: "Energy per day",
    graphCop: "Coefficient of performance, daily",
    noControls: "No writable value is switched on.",
    explain: "Explanation",
    source: "Source",
    sources: {
      emsesp: "EMS-ESP",
      husdata: "Husdata",
      bosch_local: "Bosch gateway",
      cloud: "Bosch cloud",
    },
    modes: { blocked: "Blocked", eco: "Eco", normal: "Normal", boost: "Boost" },
  },
};

//: The role groups first, in the order the questions come, then the sections
//: of the device page for the source's own points that play no role.
const ROLE_GROUPS = ["temperatures", "compressor", "energy", "heating", "hotwater", "status"];
const GROUP_ORDER = [...ROLE_GROUPS, "sensor", "config", "diagnostic"];
const TAB_ORDER = ["overview", "controls", "performance", "values"];
const CONTROL_DOMAINS = ["select", "number", "switch", "button"];
//: Entities made of other entities on this page: the thermostat is the room
//: sensor, the setpoint and the heating mode, the water heater the hot water
//: mode and its temperatures. Shown through their parts, not twice.
const COMPOSITE_DOMAINS = ["climate", "water_heater"];
const CONTROL_GROUP_ORDER = ["heating", "hotwater", "operation", "other"];
//: Which control group a role group lands in.
const CONTROL_GROUPS = { heating: "heating", hotwater: "hotwater", status: "operation" };
//: The ids an energy manager writes to the heating mode select.
const HEATING_MODES = ["blocked", "eco", "normal", "boost"];
const ALARM_ROLES = ["alarm", "controller_alarm"];
const SPAN_ORDER = ["day", "year", "lifetime"];

//: The key figures, in the order they are read: around the circuit, then the
//: compressor, then the counters. The coefficient of performance follows.
const READING_ROLES = [
  "outdoor_temp", "supply_temp", "return_temp", "brine_in", "brine_out", "dhw_temp",
  "compressor_power", "compressor_speed", "energy_in_total", "energy_out_total",
];
//: The one graph on the overview: the circuit and the hot water over a day.
const OVERVIEW_GRAPH_ROLES = ["outdoor_temp", "supply_temp", "return_temp", "dhw_temp"];
//: What the performance tab draws. An entry that is a list takes the first
//: role the pump has: a house without a room sensor of its own may still have
//: one on heating circuit 1.
const GRAPH_ROLES = {
  temps: [
    ["room_temp", "hc1_room_temp"], "outdoor_temp", "supply_temp", "return_temp",
    "dhw_temp", "brine_in", "brine_out",
  ],
  compressor: ["compressor_speed", "compressor_power", "heat_output"],
  energy: ["energy_out_total", "energy_in_total", "energy_aux_total"],
};

//: What an entity says about itself that it stops saying while unavailable.
const REMEMBERED = [
  "description", "role", "roleGroup", "source", "sourceKey", "sourceTitle", "sourceLabel",
  "copSpan",
];

/** The language the page speaks. Home Assistant has two: the system language,
 *  which is the one the integration named the entities in, and the language of
 *  the person looking. Following the viewer would leave English entity names
 *  under Swedish headings on an English installation, so the system language
 *  wins and the whole page reads as one. */
function languageOf(hass) {
  const config = (hass && hass.config && hass.config.language) || "";
  const viewer = (hass && hass.locale && hass.locale.language) || "";
  return config || viewer;
}

/** The chosen language's words, falling back to English for anything else. */
function textFor(language) {
  const code = String(language || "").slice(0, 2).toLowerCase();
  return TEXT[code] || TEXT.en;
}

/** Which section of the list a row belongs in. A role says it itself; the
 *  heating mode and the coefficient of performance belong with the heating
 *  and the energy; a source's own point goes where the device page puts it. */
function groupOf(row) {
  if (row && ROLE_GROUPS.includes(row.roleGroup)) return row.roleGroup;
  if (row && row.isHeatingMode) return "heating";
  if (row && row.isCop) return "energy";
  if (row && row.entityCategory === "diagnostic") return "diagnostic";
  if (row && row.entityCategory === "config") return "config";
  return "sensor";
}

/** Which control group a writable row belongs to. A role says it through its
 *  group; a source's own point through its key, since EMS-ESP names every
 *  heating circuit's values "hcN.…" and the hot water's "dhw.…". */
function controlGroupOf(row) {
  if (!row) return "other";
  if (row.isHeatingMode) return "heating";
  if (row.roleGroup) return CONTROL_GROUPS[row.roleGroup] || "other";
  const key = String(row.sourceKey || "").split("/").slice(1).join("/");
  if (/^hc\d/i.test(key)) return "heating";
  if (/^dhw\d*\./i.test(key)) return "hotwater";
  return "other";
}

/** The control a value deserves. A number gets a slider when its range has few
 *  enough steps to aim at; a wide range in fine steps would be a lottery, so
 *  those get a field to type in. */
function widgetFor(entityId, attributes) {
  const domain = String(entityId || "").split(".")[0];
  if (domain === "select") return "select";
  if (domain === "switch") return "toggle";
  if (domain === "button") return "button";
  if (domain !== "number") return "text";
  const attrs = attributes || {};
  const min = Number(attrs.min);
  const max = Number(attrs.max);
  const step = Number(attrs.step) || 1;
  if (!Number.isFinite(min) || !Number.isFinite(max) || max <= min) return "number";
  return (max - min) / step <= 120 ? "slider" : "number";
}

/** An option as a person reads it. The heating mode's ids are the ones an
 *  energy manager writes, in English; the page says them in its language. */
function optionLabel(row, option, text) {
  if (row && row.isHeatingMode && text.modes && text.modes[option]) return text.modes[option];
  return String(option);
}

/** A state as a person reads it: the value with its unit, or a word. */
function formatState(stateObj, text, row) {
  if (!stateObj) return text.unavailable;
  const value = stateObj.state;
  if (value === "unavailable" || value === "unknown") return text.unavailable;
  if (row && row.isHeatingMode) return optionLabel(row, value, text);
  if (value === "on") return text.on;
  if (value === "off") return text.off;
  const unit = stateObj.attributes && stateObj.attributes.unit_of_measurement;
  return unit ? `${value} ${unit}` : String(value);
}

/** True when every word of the filter appears in the name or explanation. */
function matchesFilter(filter, name, description) {
  const words = String(filter || "").toLowerCase().split(/\s+/).filter(Boolean);
  if (!words.length) return true;
  const haystack = `${name || ""} ${description || ""}`.toLowerCase();
  return words.every((word) => haystack.includes(word));
}

/** A source as the page names it; the integration's own label for one the
 *  page does not know. */
function sourceLabel(source, text, fallback) {
  return (text.sources && text.sources[source]) || fallback || source || "";
}

/** Where a value was read: "Källa: EMS-ESP · boiler/outdoortemp · outdoor
 *  temperature". Empty for an entity the integration makes of other values,
 *  such as the heating mode or the coefficient of performance. */
function sourceMeta(row, text) {
  const parts = [];
  if (row && row.source) parts.push(`${text.source}: ${sourceLabel(row.source, text, row.sourceLabel)}`);
  if (row && row.sourceKey) parts.push(row.sourceKey);
  if (row && row.sourceTitle) parts.push(row.sourceTitle);
  return parts.join(" · ");
}

/** A source's connectivity sensor as a small chip: "EMS-ESP ✓". */
function sourceChip(row, stateObj, text) {
  const label = sourceLabel(row && row.source, text, row && row.sourceLabel);
  const state = stateObj ? stateObj.state : "";
  const up = state === "on";
  const known = state === "on" || state === "off";
  return { label, up, known, text: `${label} ${up ? "✓" : known ? "✗" : "?"}` };
}

/** Whether an alarm chip should be red: only while the fault is still there.
 *  The sensor keeps the last fault after it has cleared, in words, and that is
 *  history rather than an alarm. */
function alarmRaised(row, stateObj) {
  if (!row || !row.isAlarm || !stateObj || stateObj.state === "unavailable") return false;
  return Boolean(stateObj.attributes && stateObj.attributes.active === true);
}

function sameOptions(options, wanted) {
  return Array.isArray(options) && options.length === wanted.length &&
    wanted.every((option) => options.includes(option));
}

/** The devices a card given `deviceId` shows: that device and the devices
 *  hung under it - the controller, a mixing module, each source's gateway. */
function devicesOf(hass, deviceId) {
  const wanted = new Set([deviceId]);
  for (const [id, device] of Object.entries((hass && hass.devices) || {})) {
    if (device && device.via_device_id === deviceId) wanted.add(device.id || id);
  }
  return wanted;
}

/** The devices this integration's enabled entities sit on. */
function ownDevices(hass) {
  const ids = new Set();
  for (const entry of Object.values((hass && hass.entities) || {})) {
    if (entry && entry.platform === DOMAIN && entry.device_id) ids.add(entry.device_id);
  }
  return ids;
}

/** Where under the pump a device sits, as a word: "Styrenhet" for "IVT Geo
 *  styrenhet" under "IVT Geo". Empty for the pump itself. Names are stripped
 *  of their device, so without this the four sources' "Ansluten" would read
 *  the same. */
function placeOf(device, devices, own) {
  if (!device || !device.via_device_id || !own.has(device.via_device_id)) return "";
  const parent = devices[device.via_device_id];
  if (!parent) return "";
  const name = device.name_by_user || device.name || "";
  const parentName = parent.name_by_user || parent.name || "";
  const rest = parentName && name.startsWith(`${parentName} `)
    ? name.slice(parentName.length + 1)
    : name;
  return rest.charAt(0).toUpperCase() + rest.slice(1);
}

/** The installations the page is about, for its heading: the given device,
 *  or every device of this integration that is not hung under another. */
function installationNames(hass, deviceId) {
  const devices = (hass && hass.devices) || {};
  const nameOf = (device) => device.name_by_user || device.name;
  if (deviceId) {
    return devices[deviceId] ? nameOf(devices[deviceId]) || "" : "";
  }
  const own = ownDevices(hass);
  const names = [];
  for (const id of own) {
    const device = devices[id];
    if (!device || own.has(device.via_device_id)) continue;
    const name = nameOf(device);
    if (name && !names.includes(name)) names.push(name);
  }
  return names.join(" · ");
}

/** Collect this integration's entities from hass, grouped and sorted.
 *
 * `hass.entities` is the entity registry as the frontend sees it; only
 * entities present in `hass.states` are enabled, so disabled ones - most of
 * a source's points - never appear here.
 */
function collectRows(hass, deviceId) {
  const rows = [];
  const registry = (hass && hass.entities) || {};
  const devices = (hass && hass.devices) || {};
  const states = (hass && hass.states) || {};
  const wanted = deviceId ? devicesOf(hass, deviceId) : null;
  const own = ownDevices(hass);
  for (const entry of Object.values(registry)) {
    if (!entry || entry.platform !== DOMAIN) continue;
    if (wanted && !wanted.has(entry.device_id)) continue;
    const stateObj = states[entry.entity_id];
    if (!stateObj) continue;
    const domain = entry.entity_id.split(".")[0];
    if (COMPOSITE_DOMAINS.includes(domain)) continue;
    const attributes = stateObj.attributes || {};
    const device = entry.device_id ? devices[entry.device_id] : null;
    const deviceName = device ? device.name_by_user || device.name : null;
    const role = attributes.role || "";
    const row = {
      entityId: entry.entity_id,
      domain,
      entityCategory: entry.entity_category || "",
      deviceId: entry.device_id || "",
      // Home Assistant prefixes the device name to every entity name; on a
      // page that is already about the pump it only pushes the value off.
      name: stripDeviceName(attributes.friendly_name || entry.entity_id, deviceName),
      place: placeOf(device, devices, own),
      description: attributes.description || "",
      role,
      roleGroup: attributes.group || "",
      source: attributes.source || "",
      sourceKey: attributes.source_key || "",
      sourceTitle: attributes.source_title || "",
      // The integration's own label for a source, on its connectivity sensor.
      sourceLabel: attributes.label || "",
      deviceClass: attributes.device_class || "",
      stateClass: attributes.state_class || "",
      // "day", "year" or "lifetime" on the coefficient of performance
      // sensors, the only ones that carry a span.
      copSpan: attributes.span || "",
      isCop: attributes.span !== undefined || attributes.basis !== undefined,
      // The state as a string, for picking between two of the same kind: the
      // day's coefficient of performance has no value on a mild day, when too
      // little electricity has been used to divide by.
      state: stateObj.state,
      isAlarm: ALARM_ROLES.includes(role) || attributes.alarm_code !== undefined,
      alarmActive: attributes.active === true,
      // The select an energy manager writes: blocked, eco, normal or boost.
      isHeatingMode: domain === "select" && (
        entry.translation_key === "heating_mode" ||
        attributes.normal_setpoints !== undefined ||
        sameOptions(attributes.options, HEATING_MODES)
      ),
      // Whether a source answered its last poll.
      isSource: domain === "binary_sensor" && attributes.device_class === "connectivity" &&
        entry.entity_category === "diagnostic",
    };
    row.group = groupOf(row);
    rows.push(row);
  }
  rows.sort((a, b) => a.name.localeCompare(b.name));
  return rows;
}

/** Fill in what an unavailable entity no longer says from what it said last,
 *  and keep what it says now for its next quiet spell. An entity that is
 *  unavailable carries no attributes at all, so without this the outdoor
 *  temperature would drop off the overview, and its explanation and its
 *  section with it, whenever its source is away. */
function recall(rows, memory) {
  for (const row of rows) {
    const kept = memory.get(row.entityId) || {};
    const seen = { ...kept };
    for (const key of REMEMBERED) {
      if (row[key]) seen[key] = row[key];
      else if (kept[key]) row[key] = kept[key];
    }
    if (row.copSpan) row.isCop = true;
    if (ALARM_ROLES.includes(row.role)) row.isAlarm = true;
    row.group = groupOf(row);
    memory.set(row.entityId, seen);
  }
  return rows;
}

/** The writable rows, in the order the control section shows them. */
function controlRows(rows) {
  const writable = rows.filter((row) =>
    CONTROL_DOMAINS.includes(row.entityId.split(".")[0])
  );
  return writable.sort((a, b) => {
    const left = CONTROL_GROUP_ORDER.indexOf(controlGroupOf(a));
    const right = CONTROL_GROUP_ORDER.indexOf(controlGroupOf(b));
    return left === right ? a.name.localeCompare(b.name) : left - right;
  });
}

/** The row playing a role; for a list of roles, the first the pump has. */
function byRole(rows, role) {
  for (const id of Array.isArray(role) ? role : [role]) {
    const hit = rows.find((row) => row.role === id);
    if (hit) return hit;
  }
  return null;
}

/** One row per role, in the order given, never twice. */
function pickRoles(rows, roles) {
  const picked = [];
  for (const role of roles) {
    const hit = byRole(rows.filter((row) => !picked.includes(row)), role);
    if (hit) picked.push(hit);
  }
  return picked;
}

/** The coefficient of performance sensors, day first. */
function copRows(rows) {
  return rows
    .filter((row) => row.isCop)
    .sort((a, b) => spanIndex(a) - spanIndex(b));
}

function spanIndex(row) {
  const index = SPAN_ORDER.indexOf(row.copSpan);
  return index < 0 ? SPAN_ORDER.length : index;
}

/** The controls the overview puts at the top: how the heating runs, how the
 *  hot water runs, and the boost. Only what the pump actually has shows up. */
function pickQuickControls(rows) {
  const writable = controlRows(rows);
  return [
    writable.find((row) => row.isHeatingMode),
    byRole(writable, "dhw_mode"),
    byRole(writable, "dhw_boost"),
  ].filter(Boolean);
}

/** What the overview shows: the pump's own state, the sources it is read
 *  through, and the numbers that say how it is doing. How the pump is running
 *  right now is the day's coefficient of performance; the year's and the
 *  lifetime's are key figures among the others. */
function pickOverview(rows) {
  const status = [];
  const alarm = byRole(rows, ALARM_ROLES);
  if (alarm) status.push(alarm);
  // The controller keeps a fault list of its own; it earns a chip only while
  // it has something to say.
  const controller = byRole(rows, "controller_alarm");
  if (controller && controller !== alarm && controller.alarmActive) status.push(controller);
  const activity = byRole(rows, "compressor_activity");
  if (activity) status.push(activity);
  const mode = rows.find((row) => row.isHeatingMode);
  if (mode) status.push(mode);
  const cop = copRows(rows);
  const day = cop.filter((row) => row.copSpan === "day");
  // Sensors without a span keep the old rule: the figure that has a number
  // stands on the chip, rather than an empty "unavailable".
  const chip = day.length
    ? day[0]
    : cop.slice().sort((a, b) => Number(hasNumber(b)) - Number(hasNumber(a)))[0];
  if (chip) status.push(chip);
  const readings = pickRoles(rows.filter((row) => !status.includes(row)), READING_ROLES).concat(
    cop.filter((row) => (row.copSpan === "year" || row.copSpan === "lifetime") && !status.includes(row))
  );
  const sources = rows.filter((row) => row.isSource);
  return { status, readings, cop, sources };
}

/** The overview's graph: the circuit and the hot water over the last day. */
function overviewGraphs(rows) {
  const temps = pickRoles(rows, OVERVIEW_GRAPH_ROLES);
  return temps.length ? [{ key: "temps", title: "graphTemps", entities: ids(temps) }] : [];
}

/** What the performance section draws, given what this pump reports.
 *
 * Each graph names the roles it needs; an empty one is left out, which is how
 * a pump without energy counters ends up without the coefficient of
 * performance and an air source pump without its brine lines.
 */
function pickGraphs(rows) {
  const graphs = [];
  const temps = pickRoles(rows, GRAPH_ROLES.temps);
  if (temps.length) graphs.push({ key: "temps", title: "graphTemps", entities: ids(temps) });

  const compressor = pickRoles(rows, GRAPH_ROLES.compressor);
  if (compressor.length) {
    graphs.push({ key: "compressor", title: "graphCompressor", entities: ids(compressor) });
  }

  // The day against the year: two spans that move. The lifetime figure is a
  // near-flat line and belongs among the key figures rather than in a graph.
  const cop = copRows(rows).filter((row) => row.copSpan !== "lifetime").slice(0, 2);
  if (cop.length) {
    graphs.push({ key: "cop", title: "graphCop", entities: ids(cop), statistic: "mean" });
  }

  const energy = pickRoles(rows, GRAPH_ROLES.energy);
  if (energy.length) {
    graphs.push({ key: "energy", title: "graphEnergy", entities: ids(energy), statistic: "change" });
  }
  return graphs;
}

function hasNumber(row) {
  return Boolean(row) && row.state !== "" && row.state !== null &&
    Number.isFinite(Number(row.state));
}

function ids(rows) {
  return rows.map((row) => row.entityId);
}

/** The same ids, marking which rows carry an explanation. A card built while
 *  its entities were unavailable - right after a restart, say - has none, and
 *  has to be built again once they arrive, or it keeps its missing ⓘ. */
function structureOf(rows) {
  return rows.map((row) => row.entityId + (row.description ? "!" : "")).join(",");
}

/** A graph as a Home Assistant card configuration. Counters are drawn from the
 *  long-term statistics, which is the only place a year of them survives; the
 *  rest come from the recorder's own history. */
function graphConfig(graph, text) {
  if (graph.statistic) {
    return {
      type: "statistics-graph",
      title: text[graph.title],
      entities: graph.entities,
      period: "day",
      days_to_show: 30,
      stat_types: [graph.statistic],
      chart_type: graph.statistic === "change" ? "bar" : "line",
    };
  }
  return {
    type: "history-graph",
    title: text[graph.title],
    hours_to_show: 24,
    entities: graph.entities,
  };
}

/** What the list currently shows, as one string. Home Assistant hands the card
 *  a new `hass` on every state change anywhere in the house - often several a
 *  second - and redrawing every row each time makes the hover text flicker.
 *  Comparing this skips every update that changes nothing on screen. */
function signature(hass, rows) {
  return rows
    .map((row) => {
      const stateObj = hass.states[row.entityId];
      return `${row.entityId}=${stateObj ? stateObj.state : ""}`;
    })
    .join("|");
}

/** Drop the device name that Home Assistant prefixes to every entity name. */
function stripDeviceName(name, deviceName) {
  if (deviceName && name.startsWith(`${deviceName} `)) {
    return name.slice(deviceName.length + 1);
  }
  return name;
}

/** The service call a control makes. Returned rather than called, so the
 *  mapping from widget to service is testable without Home Assistant. */
function serviceFor(entityId, value) {
  const domain = String(entityId || "").split(".")[0];
  if (domain === "select") {
    return { domain: "select", service: "select_option", data: { entity_id: entityId, option: value } };
  }
  if (domain === "number") {
    return { domain: "number", service: "set_value", data: { entity_id: entityId, value: Number(value) } };
  }
  if (domain === "switch") {
    return { domain: "switch", service: value ? "turn_on" : "turn_off", data: { entity_id: entityId } };
  }
  if (domain === "button") {
    return { domain: "button", service: "press", data: { entity_id: entityId } };
  }
  return null;
}

if (typeof module !== "undefined") {
  module.exports = {
    textFor, languageOf, groupOf, formatState, optionLabel, matchesFilter, collectRows,
    devicesOf, installationNames, stripDeviceName, signature, controlGroupOf, controlRows,
    widgetFor, pickGraphs, overviewGraphs, graphConfig, byRole, pickOverview,
    pickQuickControls, hasNumber, structureOf, recall, alarmRaised, sourceChip, sourceLabel,
    sourceMeta, serviceFor,
    GROUP_ORDER, CONTROL_GROUP_ORDER, TAB_ORDER, DOMAIN, HEATING_MODES,
  };
}

/* ------------------------------------------------------------------ DOM -- */

if (typeof customElements !== "undefined") {
  const STYLE = `
    :host { display: block; }
    .wrap { padding: 16px; max-width: 1600px; margin: 0 auto; }
    .head { display: flex; flex-wrap: wrap; align-items: center; gap: 4px 12px; }
    .head .mark { width: 28px; height: 28px; flex: none; }
    h1 { font-size: 1.4rem; font-weight: 500; margin: 4px 0; color: var(--primary-text-color); }
    h3 { font-size: .95rem; font-weight: 500; margin: 0 0 8px; color: var(--primary-text-color); }
    .tabs {
      display: flex; gap: 4px; margin: 12px 0 16px; overflow-x: auto;
      border-bottom: 1px solid var(--divider-color, #e0e0e0);
    }
    .tabs button {
      font: inherit; padding: 10px 16px; border: none; background: none; cursor: pointer;
      color: var(--secondary-text-color); border-bottom: 2px solid transparent; white-space: nowrap;
    }
    .tabs button[aria-selected="true"] {
      color: var(--primary-color, #03a9f4); border-bottom-color: var(--primary-color, #03a9f4);
    }
    .tabs button:focus-visible { outline: 2px solid var(--primary-color, #03a9f4); outline-offset: -2px; }
    .cards { display: grid; gap: 16px; grid-template-columns: repeat(auto-fill, minmax(340px, 1fr)); }
    .card {
      background: var(--ha-card-background, var(--card-background-color, #fff));
      border-radius: var(--ha-card-border-radius, 12px);
      box-shadow: var(--ha-card-box-shadow, 0 2px 4px rgba(0,0,0,.08));
      border: var(--ha-card-border-width, 0) solid var(--ha-card-border-color, transparent);
      padding: 14px 16px; margin-bottom: 16px;
    }
    .chips { display: flex; flex-wrap: wrap; gap: 10px; }
    .chip {
      display: flex; gap: 8px; align-items: baseline; padding: 8px 14px; border-radius: 999px;
      background: var(--secondary-background-color, #f1f3f4);
    }
    .chip .label { color: var(--secondary-text-color); font-size: .8em; }
    .chip .value { color: var(--primary-text-color); font-weight: 500; }
    .chip.alarm-on { background: var(--error-color, #db4437); }
    .chip.alarm-on .label, .chip.alarm-on .value { color: #fff; }
    .chips.sources { gap: 6px; margin-top: 10px; }
    .chip.source {
      padding: 3px 10px; font-size: .8em; color: var(--secondary-text-color);
    }
    .chip.source.down { color: var(--error-color, #db4437); }
    .tiles { display: grid; gap: 16px 24px; grid-template-columns: repeat(auto-fill, minmax(140px, 1fr)); }
    .tile .label { color: var(--secondary-text-color); font-size: .8em; overflow-wrap: anywhere; }
    .tile .note, .chips-note { grid-column: auto; padding-top: 4px; }
    .chips-note { color: var(--secondary-text-color); font-size: .85em; line-height: 1.45; }
    .tile .big { font-size: 1.6rem; font-weight: 500; color: var(--primary-text-color); }
    .tile .sub { color: var(--secondary-text-color); font-size: .75em; }
    .control {
      display: grid; grid-template-columns: 1fr auto; align-items: center;
      gap: 6px 12px; padding: 8px 0; border-bottom: 1px solid var(--divider-color, #eee);
    }
    .control:last-of-type { border-bottom: none; }
    .control .name { color: var(--primary-text-color); overflow-wrap: break-word; min-width: 0; }
    .control .widget { display: flex; align-items: center; gap: 8px; justify-self: end; }
    .control .widget[data-pending="1"] { opacity: .5; }
    .control select, .control input[type="number"] {
      font: inherit; padding: 6px 8px; border-radius: 8px; max-width: 190px;
      border: 1px solid var(--divider-color, #ccc);
      background: var(--card-background-color, #fff); color: var(--primary-text-color);
    }
    .control input[type="range"] { width: 130px; accent-color: var(--primary-color, #03a9f4); }
    .control .reading { color: var(--primary-text-color); font-weight: 500; min-width: 64px; text-align: right; }
    .control .widget button {
      font: inherit; padding: 6px 14px; border-radius: 8px; cursor: pointer;
      border: 1px solid var(--primary-color, #03a9f4);
      background: transparent; color: var(--primary-color, #03a9f4);
    }
    .switch { position: relative; width: 44px; height: 24px; }
    .switch input { opacity: 0; width: 100%; height: 100%; margin: 0; cursor: pointer; }
    .switch .track {
      position: absolute; inset: 0; border-radius: 12px; pointer-events: none;
      background: var(--divider-color, #ccc); transition: background .15s;
    }
    .switch .knob {
      position: absolute; top: 3px; left: 3px; width: 18px; height: 18px; border-radius: 50%;
      background: #fff; box-shadow: 0 1px 3px rgba(0,0,0,.3); transition: transform .15s; pointer-events: none;
    }
    .switch input:checked ~ .track { background: var(--primary-color, #03a9f4); }
    .switch input:checked ~ .knob { transform: translateX(20px); }
    .switch input:focus-visible ~ .track { outline: 2px solid var(--primary-color, #03a9f4); outline-offset: 2px; }
    .why {
      background: none; border: none; cursor: pointer; padding: 0 2px;
      color: var(--primary-color, #03a9f4); font: inherit; line-height: 1;
    }
    .why:focus-visible { outline: 1px solid var(--primary-color, #03a9f4); outline-offset: 2px; }
    .note {
      grid-column: 1 / -1; color: var(--secondary-text-color); font-size: .85em;
      line-height: 1.45; padding-bottom: 4px;
    }
    .graphs { display: grid; gap: 16px; grid-template-columns: repeat(auto-fill, minmax(420px, 1fr)); }
    /* The performance tab fills two columns itself, so each graph keeps its
       own height and the next one follows directly under it. */
    .graphs.flow { grid-template-columns: repeat(2, minmax(0, 1fr)); align-items: start; }
    .graphs.flow > .column { display: flex; flex-direction: column; gap: 16px; min-width: 0; }
    @media (max-width: 900px) { .graphs.flow { grid-template-columns: 1fr; } }
    /* The overview reads left to right: what to change, and how it has run.
       Both boxes take the height of the taller one, so the row lines up. */
    .beside { display: grid; gap: 16px; align-items: stretch; margin-bottom: 16px;
              grid-template-columns: minmax(280px, 1fr) minmax(0, 2fr); }
    .beside > * { min-width: 0; margin-bottom: 0; }
    .beside > .graphs { grid-template-columns: minmax(0, 1fr); }
    .beside > .graphs > * { height: 100%; }
    @media (max-width: 900px) { .beside { grid-template-columns: 1fr; } }
    .toolbar { display: flex; gap: 12px; align-items: center; margin-bottom: 12px; }
    .toolbar input {
      flex: 1; max-width: 420px; padding: 8px 12px; font: inherit;
      border: 1px solid var(--divider-color, #ccc); border-radius: 8px;
      background: var(--card-background-color, #fff); color: var(--primary-text-color);
    }
    .count { color: var(--secondary-text-color); font-size: .9em; }
    h2 {
      font-size: 1rem; font-weight: 500; margin: 20px 0 8px;
      color: var(--secondary-text-color); text-transform: uppercase; letter-spacing: .04em;
    }
    .grid {
      display: grid; gap: 1px 24px;
      grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
    }
    .row {
      display: grid; grid-template-columns: 1fr auto; gap: 4px 12px;
      padding: 10px 4px; border-bottom: 1px solid var(--divider-color, #eee);
      cursor: pointer; border-radius: 4px;
    }
    .row:hover, .row:focus-visible { background: var(--secondary-background-color, #f5f5f5); outline: none; }
    .name { color: var(--primary-text-color); overflow-wrap: anywhere; }
    .place { color: var(--secondary-text-color); font-size: .8em; }
    .value { color: var(--primary-text-color); font-weight: 500; white-space: nowrap; text-align: right; }
    .info { color: var(--secondary-text-color); font-size: .75em; margin-left: 4px; }
    .detail {
      grid-column: 1 / -1; color: var(--secondary-text-color); font-size: .9em;
      line-height: 1.45; padding-top: 2px;
    }
    .detail .meta { display: block; margin-top: 6px; font-size: .85em; opacity: .8; }
    .detail a { color: var(--primary-color); cursor: pointer; text-decoration: underline; }
    .empty { color: var(--secondary-text-color); padding: 24px 4px; }
  `;

  //: Where the chosen tab is remembered, so a reload comes back to it.
  const TAB_STORAGE = "rego-easyconf-tab";

  /** Shared rendering: one instance per card or panel. */
  class RegoEasyconfView {
    constructor(root) {
      this.root = root;
      this.filter = "";
      this.open = new Set();
      this.hass = null;
      this.deviceId = null;
      this.tabs = TAB_ORDER;
      this.tab = restoreTab();
      this.built = false;
      this.lastSignature = null;
      this.controlSignature = null;
      //: entity id -> what it last said about itself, kept over its quiet spells.
      this.memory = new Map();
      this.graphSignature = null;
      this.overviewSignature = null;
      this.quickSignature = null;
      this.overviewGraphSignature = null;
      this.widgets = new Map();
      this.quickWidgets = new Map();
      this.readingTiles = new Map();
      this.statusChips = new Map();
      this.sourceChips = new Map();
      this.graphCards = [];
      this.overviewCards = [];
      this.explained = new Set();
    }

    build() {
      this.root.replaceChildren();
      const style = document.createElement("style");
      style.textContent = STYLE;
      this.root.appendChild(style);

      this.wrap = document.createElement("div");
      this.wrap.className = "wrap";

      const head = document.createElement("div");
      head.className = "head";
      // The integration's own mark, served from its brand folder. If the file
      // is missing, the heading stands on its own rather than a broken image.
      const mark = document.createElement("img");
      mark.className = "mark";
      mark.src = `/${DOMAIN}/icon.png`;
      mark.alt = "";
      mark.addEventListener("error", () => { mark.hidden = true; });
      this.heading = document.createElement("h1");
      head.append(mark, this.heading);

      this.tabBar = document.createElement("div");
      this.tabBar.className = "tabs";
      this.tabBar.setAttribute("role", "tablist");
      this.tabButtons = new Map();
      for (const tab of this.tabs) {
        const button = document.createElement("button");
        button.type = "button";
        button.setAttribute("role", "tab");
        button.addEventListener("click", () => this.showTab(tab));
        this.tabBar.appendChild(button);
        this.tabButtons.set(tab, button);
      }

      // Overview
      this.overviewPanel = document.createElement("div");
      this.quickCard = document.createElement("div");
      this.quickCard.className = "card";
      this.quickHeading = document.createElement("h3");
      this.quickBody = document.createElement("div");
      this.quickCard.append(this.quickHeading, this.quickBody);
      this.statusCard = document.createElement("div");
      this.statusCard.className = "card";
      this.statusChipsRow = document.createElement("div");
      this.statusChipsRow.className = "chips";
      this.statusHeading = document.createElement("h3");
      this.statusNote = document.createElement("div");
      this.statusNote.className = "chips-note";
      this.statusNote.hidden = true;
      this.sourceChipsRow = document.createElement("div");
      this.sourceChipsRow.className = "chips sources";
      this.statusCard.append(
        this.statusHeading, this.statusChipsRow, this.statusNote, this.sourceChipsRow
      );
      this.readingsCard = document.createElement("div");
      this.readingsCard.className = "card";
      this.readingsHeading = document.createElement("h3");
      this.readingsGrid = document.createElement("div");
      this.readingsGrid.className = "tiles";
      this.readingsCard.append(this.readingsHeading, this.readingsGrid);
      this.overviewGraphs = document.createElement("div");
      this.overviewGraphs.className = "graphs";
      // The graph and the controls share a row: the graph takes the width it
      // needs to be readable, the controls stand beside it rather than under.
      this.overviewRow = document.createElement("div");
      this.overviewRow.className = "beside";
      this.overviewRow.append(this.quickCard, this.overviewGraphs);
      this.overviewPanel.append(
        this.statusCard, this.overviewRow, this.readingsCard
      );

      // Controls
      this.controlsPanel = document.createElement("div");
      this.controlsBody = document.createElement("div");
      this.controlsBody.className = "cards";
      this.controlsPanel.appendChild(this.controlsBody);

      // Performance
      this.performancePanel = document.createElement("div");
      this.graphsBody = document.createElement("div");
      this.graphsBody.className = "graphs flow";
      this.performancePanel.appendChild(this.graphsBody);

      // All values
      this.valuesPanel = document.createElement("div");
      const toolbar = document.createElement("div");
      toolbar.className = "toolbar";
      this.input = document.createElement("input");
      this.input.type = "search";
      this.input.addEventListener("input", () => {
        this.filter = this.input.value;
        this.renderList(true);
      });
      this.count = document.createElement("span");
      this.count.className = "count";
      toolbar.append(this.input, this.count);
      this.body = document.createElement("div");
      this.valuesPanel.append(toolbar, this.body);

      this.panels = {
        overview: this.overviewPanel,
        controls: this.controlsPanel,
        performance: this.performancePanel,
        values: this.valuesPanel,
      };
      this.wrap.append(head, this.tabBar);
      for (const tab of this.tabs) this.wrap.appendChild(this.panels[tab]);
      this.root.appendChild(this.wrap);
      this.built = true;
      if (!this.tabs.includes(this.tab)) this.tab = this.tabs[0];
    }

    showTab(tab) {
      this.tab = tab;
      try {
        window.localStorage.setItem(TAB_STORAGE, tab);
      } catch (err) {
        // A browser that refuses storage still gets the tab for this visit.
      }
      this.render();
    }

    moreInfo(entityId) {
      this.root.host.dispatchEvent(new CustomEvent("hass-more-info", {
        detail: { entityId }, bubbles: true, composed: true,
      }));
    }

    call(entityId, value) {
      const call = serviceFor(entityId, value);
      if (!call) return;
      this.hass.callService(call.domain, call.service, call.data);
    }

    /** An entity that is unavailable carries no attributes at all, so its
     *  explanation, its role and its source go with it - and the page would
     *  lose the value from the overview for as long as its source is quiet.
     *  The last ones seen are kept and handed back. */
    remember(rows) {
      return recall(rows, this.memory);
    }

    render() {
      if (!this.hass) return;
      if (!this.built) this.build();
      const text = textFor(languageOf(this.hass));
      this.input.placeholder = text.filter;
      const rows = this.remember(collectRows(this.hass, this.deviceId));
      this.heading.textContent = installationNames(this.hass, this.deviceId) || text.title;

      for (const [tab, button] of this.tabButtons) {
        button.textContent = text[tab];
        button.setAttribute("aria-selected", String(tab === this.tab));
        this.panels[tab].hidden = tab !== this.tab;
      }

      // Only the tab in front is drawn; the others keep what they had.
      if (this.tab === "overview") this.renderOverview(rows, text);
      if (this.tab === "controls") this.renderControls(rows, text);
      if (this.tab === "performance") this.renderGraphs(rows, text);
      if (this.tab === "values") this.renderList(false, rows, text);
    }

    /* ----------------------------------------------------------- overview */

    renderOverview(rows, text) {
      const picked = pickOverview(rows);
      const structure = [
        structureOf(picked.status), structureOf(picked.readings), ids(picked.sources).join(","),
      ].join("|");
      this.statusHeading.textContent = text.now;
      this.quickHeading.textContent = text.quick;
      this.readingsHeading.textContent = text.readings;

      if (structure !== this.overviewSignature) {
        this.overviewSignature = structure;
        this.statusChips.clear();
        this.readingTiles.clear();
        this.sourceChips.clear();
        this.statusChipsRow.replaceChildren();
        this.readingsGrid.replaceChildren();
        this.sourceChipsRow.replaceChildren();
        this.statusNote.hidden = true;
        for (const row of picked.status) {
          const chip = document.createElement("div");
          chip.className = "chip";
          const label = document.createElement("span");
          label.className = "label";
          label.textContent = row.name;
          const value = document.createElement("span");
          value.className = "value";
          chip.append(label, value);
          if (row.description) {
            chip.title = row.description;
            label.appendChild(this.explainButton(row, text, (open) => {
              this.statusNote.textContent = open ? row.description : "";
              this.statusNote.hidden = !open;
            }));
          }
          this.statusChipsRow.appendChild(chip);
          this.statusChips.set(row.entityId, { chip, value, row });
        }
        for (const row of picked.sources) {
          const chip = document.createElement("div");
          chip.className = "chip source";
          this.sourceChipsRow.appendChild(chip);
          this.sourceChips.set(row.entityId, { chip, row });
        }
        for (const row of picked.readings) {
          this.readingsGrid.appendChild(this.buildTile(row, row.isCop, text));
        }
      }
      this.statusCard.hidden = !picked.status.length && !picked.sources.length;
      this.sourceChipsRow.hidden = !picked.sources.length;
      this.readingsCard.hidden = !picked.readings.length;

      for (const [entityId, chip] of this.statusChips) {
        const stateObj = this.hass.states[entityId];
        chip.value.textContent = formatState(stateObj, text, chip.row);
        // A fault that is still there is the one thing on this page that
        // should be impossible to miss; one that has cleared is history.
        chip.chip.classList.toggle("alarm-on", alarmRaised(chip.row, stateObj));
      }
      for (const [entityId, { chip, row }] of this.sourceChips) {
        const stateObj = this.hass.states[entityId];
        const shown = sourceChip(row, stateObj, text);
        chip.textContent = shown.text;
        chip.classList.toggle("down", shown.known && !shown.up);
        const error = stateObj && stateObj.attributes && stateObj.attributes.last_error;
        chip.title = error && !shown.up ? `${shown.label}: ${error}` : shown.label;
      }
      for (const [entityId, tile] of this.readingTiles) {
        const stateObj = this.hass.states[entityId];
        tile.value.textContent = formatState(stateObj, text);
        if (tile.sub) {
          tile.sub.textContent = (stateObj && stateObj.attributes.basis) || "";
        }
      }
      this.renderQuickControls(rows, text);
      this.renderOverviewGraph(rows, text);
    }

    /** The most important controls, on the overview, as the same widgets the
     *  controls tab uses. They keep their own map: both tabs can hold a widget
     *  for the same entity, and each has to update its own. */
    renderQuickControls(rows, text) {
      const controls = pickQuickControls(rows);
      const structure = structureOf(controls);
      if (structure !== this.quickSignature) {
        this.quickSignature = structure;
        this.quickWidgets.clear();
        this.quickBody.replaceChildren();
        for (const row of controls) {
          this.quickBody.appendChild(this.buildControl(row, text, this.quickWidgets));
        }
      }
      this.quickCard.hidden = !controls.length;
      for (const widget of this.quickWidgets.values()) widget.update();
    }

    buildTile(row, withBasis = false, text = null) {
      text = text || textFor(languageOf(this.hass));
      const tile = document.createElement("div");
      tile.className = "tile";
      const label = document.createElement("div");
      label.className = "label";
      label.textContent = row.name;
      const value = document.createElement("div");
      value.className = "big";
      tile.append(label, value);
      let note = null;
      if (row.description) {
        tile.title = row.description;
        note = document.createElement("div");
        note.className = "note";
        note.textContent = row.description;
        note.hidden = !this.explained.has(row.entityId);
        label.appendChild(
          this.explainButton(row, text, (open) => { note.hidden = !open; })
        );
      }
      let sub = null;
      if (withBasis) {
        sub = document.createElement("div");
        sub.className = "sub";
        tile.appendChild(sub);
      }
      // The explanation stands under the figure and what it rests on.
      if (note) tile.appendChild(note);
      this.readingTiles.set(row.entityId, { value, sub });
      return tile;
    }

    /** One graph on the overview: the circuit over the last day. */
    async renderOverviewGraph(rows, text) {
      const temps = overviewGraphs(rows);
      const structure = temps.map((graph) => graph.entities.join(",")).join("|");
      if (structure === this.overviewGraphSignature) {
        for (const card of this.overviewCards) card.hass = this.hass;
        return;
      }
      this.overviewGraphSignature = structure;
      this.overviewCards = await this.fillGraphs(this.overviewGraphs, temps, text);
    }

    /* ----------------------------------------------------------- controls */

    renderControls(rows, text) {
      const controls = controlRows(rows);
      const structure = structureOf(controls);
      if (structure !== this.controlSignature) {
        this.controlSignature = structure;
        this.buildControls(controls, text);
      }
      for (const widget of this.widgets.values()) widget.update();
    }

    buildControls(controls, text) {
      this.controlsBody.replaceChildren();
      this.widgets.clear();
      if (!controls.length) {
        const empty = document.createElement("div");
        empty.className = "empty";
        empty.textContent = text.noControls;
        this.controlsBody.appendChild(empty);
        return;
      }
      for (const group of CONTROL_GROUP_ORDER) {
        const members = controls.filter((row) => controlGroupOf(row) === group);
        if (!members.length) continue;
        const card = document.createElement("div");
        card.className = "card";
        const heading = document.createElement("h3");
        heading.textContent = text[group];
        card.appendChild(heading);
        for (const row of members) card.appendChild(this.buildControl(row, text, this.widgets));
        this.controlsBody.appendChild(card);
      }
    }

    /** The blue "i" that opens an explanation. Everything the page shows has
     *  one: a value is only worth reading if you know what it is. */
    explainButton(row, text, toggle) {
      const why = document.createElement("button");
      why.className = "why";
      why.type = "button";
      why.textContent = "ⓘ";
      why.setAttribute("aria-label", text.explain);
      why.addEventListener("click", (event) => {
        event.stopPropagation();
        if (this.explained.has(row.entityId)) this.explained.delete(row.entityId);
        else this.explained.add(row.entityId);
        toggle(this.explained.has(row.entityId));
      });
      return why;
    }

    /** The name of a row, with the device under the pump it sits on. */
    nameElement(row) {
      const name = document.createElement("span");
      name.className = "name";
      name.textContent = row.name;
      if (row.place) {
        const place = document.createElement("span");
        place.className = "place";
        place.textContent = ` · ${row.place}`;
        name.appendChild(place);
      }
      return name;
    }

    buildControl(row, text, registry) {
      const el = document.createElement("div");
      el.className = "control";

      const name = this.nameElement(row);
      const note = document.createElement("div");
      note.className = "note";
      note.textContent = row.description;
      note.hidden = !this.explained.has(row.entityId);
      if (row.description) {
        name.title = row.description;
        name.appendChild(
          this.explainButton(row, text, (open) => { note.hidden = !open; })
        );
      }

      const widget = document.createElement("span");
      widget.className = "widget";
      el.append(name, widget, note);
      registry.set(row.entityId, this.fillWidget(widget, row, text));
      return el;
    }

    /** Build the widget itself and return how to keep it current. A widget the
     *  user is holding is left alone: Home Assistant sends a new state while a
     *  slider is being dragged, and writing it back would fight the thumb. */
    fillWidget(container, row, text) {
      const entityId = row.entityId;
      const kind = widgetFor(entityId, (this.hass.states[entityId] || {}).attributes);
      const send = (value) => {
        container.dataset.pending = "1";
        this.call(entityId, value);
        setTimeout(() => { container.dataset.pending = "0"; }, 6000);
      };

      if (kind === "select") {
        const select = document.createElement("select");
        select.addEventListener("change", () => send(select.value));
        container.appendChild(select);
        return { update: () => {
          const stateObj = this.hass.states[entityId];
          const options = (stateObj && stateObj.attributes.options) || [];
          if (select.options.length !== options.length ||
              [...select.options].some((option, i) => option.value !== options[i])) {
            select.replaceChildren();
            for (const option of options) {
              const item = document.createElement("option");
              item.value = option;
              item.textContent = optionLabel(row, option, text);
              select.appendChild(item);
            }
          }
          if (document.activeElement !== select && stateObj) {
            select.value = stateObj.state;
            if (select.value === stateObj.state) container.dataset.pending = "0";
          }
          select.disabled = !stateObj || stateObj.state === "unavailable";
        } };
      }

      if (kind === "toggle") {
        const label = document.createElement("label");
        label.className = "switch";
        const input = document.createElement("input");
        input.type = "checkbox";
        const track = document.createElement("span");
        track.className = "track";
        const knob = document.createElement("span");
        knob.className = "knob";
        input.addEventListener("change", () => send(input.checked));
        label.append(input, track, knob);
        container.appendChild(label);
        return { update: () => {
          const stateObj = this.hass.states[entityId];
          if (document.activeElement !== input) input.checked = Boolean(stateObj && stateObj.state === "on");
          input.disabled = !stateObj || stateObj.state === "unavailable";
          if (stateObj && (stateObj.state === "on") === input.checked) container.dataset.pending = "0";
        } };
      }

      if (kind === "button") {
        const button = document.createElement("button");
        button.type = "button";
        button.textContent = text.press;
        button.addEventListener("click", () => send(null));
        container.appendChild(button);
        return { update: () => {} };
      }

      if (kind === "slider") {
        const attrs = (this.hass.states[entityId] || {}).attributes || {};
        const slider = document.createElement("input");
        slider.type = "range";
        slider.min = attrs.min;
        slider.max = attrs.max;
        slider.step = attrs.step || 1;
        const reading = document.createElement("span");
        reading.className = "reading";
        slider.addEventListener("input", () => {
          reading.textContent = withUnit(slider.value, attrs.unit_of_measurement);
        });
        slider.addEventListener("change", () => send(slider.value));
        container.append(slider, reading);
        return { update: () => {
          const stateObj = this.hass.states[entityId];
          if (!stateObj) return;
          if (document.activeElement !== slider) {
            slider.value = stateObj.state;
            reading.textContent = formatState(stateObj, text);
            if (String(slider.value) === String(stateObj.state)) container.dataset.pending = "0";
          }
          slider.disabled = stateObj.state === "unavailable";
        } };
      }

      const attrs = (this.hass.states[entityId] || {}).attributes || {};
      const field = document.createElement("input");
      field.type = "number";
      if (attrs.min !== undefined) field.min = attrs.min;
      if (attrs.max !== undefined) field.max = attrs.max;
      field.step = attrs.step || "any";
      const unit = document.createElement("span");
      unit.className = "reading";
      unit.textContent = attrs.unit_of_measurement || "";
      field.addEventListener("change", () => send(field.value));
      container.append(field, unit);
      return { update: () => {
        const stateObj = this.hass.states[entityId];
        if (!stateObj) return;
        if (document.activeElement !== field) {
          field.value = stateObj.state;
          if (String(field.value) === String(stateObj.state)) container.dataset.pending = "0";
        }
        field.disabled = stateObj.state === "unavailable";
      } };
    }

    /* ------------------------------------------------------------- graphs */

    async renderGraphs(rows, text) {
      const graphs = pickGraphs(rows);
      const structure = graphs.map((graph) => `${graph.key}:${graph.entities.join(",")}`).join("|");
      if (structure === this.graphSignature) {
        for (const card of this.graphCards) card.hass = this.hass;
        return;
      }
      this.graphSignature = structure;
      this.graphCards = await this.fillGraphs(this.graphsBody, graphs, text);
    }

    /** Put Home Assistant's own history and statistics cards in a container.
     *  They are reached the way every custom card reaches them; if that ever
     *  fails the graphs are left out, since the page is useful without them. */
    async fillGraphs(container, graphs, text) {
      container.replaceChildren();
      if (!graphs.length) return [];
      let helpers = null;
      try {
        helpers = window.loadCardHelpers ? await window.loadCardHelpers() : null;
      } catch (err) {
        helpers = null;
      }
      if (!helpers) return [];
      // Two columns filled by hand rather than by the grid: a grid row is as
      // tall as its tallest card, which would leave a day of temperatures
      // stretched out beside a taller graph instead of letting the next one up.
      const flow = container.classList.contains("flow");
      const columns = [];
      if (flow) {
        for (let i = 0; i < Math.min(2, graphs.length); i += 1) {
          const column = document.createElement("div");
          column.className = "column";
          container.appendChild(column);
          columns.push(column);
        }
      }
      const cards = [];
      graphs.forEach((graph, index) => {
        try {
          const card = helpers.createCardElement(graphConfig(graph, text));
          card.hass = this.hass;
          (columns.length ? columns[index % columns.length] : container).appendChild(card);
          cards.push(card);
        } catch (err) {
          // One graph the frontend cannot build must not take the others.
        }
      });
      return cards;
    }

    /* --------------------------------------------------------- all values */

    renderList(force = false, rows = null, text = null) {
      if (!this.hass) return;
      text = text || textFor(languageOf(this.hass));
      const all = rows || this.remember(collectRows(this.hass, this.deviceId));

      const current = signature(this.hass, all);
      if (!force && current === this.lastSignature) return;
      this.lastSignature = current;
      // The source's own name and key are searchable too: "hc1.seltemp" finds
      // the value the gateway's web page calls that.
      const shown = all.filter((row) => matchesFilter(
        this.filter, `${row.name} ${row.place}`,
        `${row.description} ${row.sourceTitle} ${row.sourceKey}`
      ));
      this.count.textContent = `${shown.length} / ${all.length}`;

      this.body.replaceChildren();
      if (!all.length || !shown.length) {
        const empty = document.createElement("div");
        empty.className = "empty";
        empty.textContent = all.length ? text.none : text.empty;
        this.body.appendChild(empty);
        return;
      }

      for (const group of GROUP_ORDER) {
        const members = shown.filter((row) => row.group === group);
        if (!members.length) continue;
        const heading = document.createElement("h2");
        heading.textContent = text[group];
        const grid = document.createElement("div");
        grid.className = "grid";
        for (const row of members) grid.appendChild(this.renderRow(row, text));
        this.body.append(heading, grid);
      }
    }

    renderRow(row, text) {
      const el = document.createElement("div");
      el.className = "row";
      el.tabIndex = 0;
      el.setAttribute("role", "button");
      el.setAttribute("aria-expanded", String(this.open.has(row.entityId)));
      // Hover, for a mouse. The same text is written out on tap below.
      if (row.description) el.title = row.description;

      const name = this.nameElement(row);
      if (row.description) {
        const info = document.createElement("span");
        info.className = "info";
        info.textContent = "ⓘ";
        info.setAttribute("aria-hidden", "true");
        name.appendChild(info);
      }

      const value = document.createElement("span");
      value.className = "value";
      value.textContent = formatState(this.hass.states[row.entityId], text, row);
      el.append(name, value);

      if (this.open.has(row.entityId)) {
        const detail = document.createElement("div");
        detail.className = "detail";
        detail.textContent = row.description || row.sourceTitle || "";
        const meta = document.createElement("span");
        meta.className = "meta";
        const where = sourceMeta(row, text);
        if (where) meta.append(where, " · ");
        const link = document.createElement("a");
        link.textContent = text.details;
        link.addEventListener("click", (event) => {
          event.stopPropagation();
          this.moreInfo(row.entityId);
        });
        meta.append(link);
        detail.appendChild(meta);
        el.appendChild(detail);
      }

      const toggle = () => {
        if (this.open.has(row.entityId)) this.open.delete(row.entityId);
        else this.open.add(row.entityId);
        this.renderList(true);
      };
      el.addEventListener("click", toggle);
      el.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          toggle();
        }
      });
      return el;
    }
  }

  function withUnit(value, unit) {
    return unit ? `${value} ${unit}` : String(value);
  }

  function restoreTab() {
    try {
      const saved = window.localStorage.getItem(TAB_STORAGE);
      if (saved && TAB_ORDER.includes(saved)) return saved;
    } catch (err) {
      // No storage: start on the overview, like a first visit.
    }
    return TAB_ORDER[0];
  }

  class RegoEasyconfCard extends HTMLElement {
    constructor() {
      super();
      this.view = new RegoEasyconfView(this.attachShadow({ mode: "open" }));
    }
    setConfig(config) {
      this.view.deviceId = (config && config.device_id) || null;
      const tabs = config && config.tabs;
      this.view.tabs = Array.isArray(tabs) && tabs.length
        ? TAB_ORDER.filter((tab) => tabs.includes(tab))
        : TAB_ORDER;
      this.view.built = false;
      this.view.lastSignature = null;
      this.view.controlSignature = null;
      this.view.graphSignature = null;
      this.view.overviewSignature = null;
      this.view.quickSignature = null;
      this.view.overviewGraphSignature = null;
    }
    set hass(hass) {
      this.view.hass = hass;
      this.view.render();
    }
    getCardSize() {
      return 20;
    }
    static getStubConfig() {
      return {};
    }
  }

  class RegoEasyconfPanel extends HTMLElement {
    constructor() {
      super();
      this.view = new RegoEasyconfView(this.attachShadow({ mode: "open" }));
    }
    set hass(hass) {
      this.view.hass = hass;
      this.view.render();
    }
    set panel(_panel) {}
    set narrow(_narrow) {}
  }

  if (!customElements.get("rego-easyconf-card")) {
    customElements.define("rego-easyconf-card", RegoEasyconfCard);
  }
  if (!customElements.get("rego-easyconf-panel")) {
    customElements.define("rego-easyconf-panel", RegoEasyconfPanel);
  }

  window.customCards = window.customCards || [];
  if (!window.customCards.some((card) => card.type === "rego-easyconf-card")) {
    window.customCards.push({
      type: "rego-easyconf-card",
      name: "IVT Bosch Rego Local Easyconf",
      description: "The heat pump's controls, a few graphs, and every value with its explanation and source.",
    });
  }
}
