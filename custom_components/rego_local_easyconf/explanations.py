"""What each value is, and what changing it does, in Swedish and English.

The roles are written out by hand: they are the values a person looks at or
changes. A point that plays no role gets its explanation from its own title
and a glossary of the component designations Bosch and IVT use on the
refrigerant and water circuits (TC0, TR6, PL1 ...), so ``hptr3`` still says
it is the liquid line after the condenser rather than just "TR3".
"""

from __future__ import annotations

import re

from .model import Point

# role -> (sv, en)
ROLE_TEXTS: dict[str, tuple[str, str]] = {
    "outdoor_temp": (
        "Utetemperaturen som värmepumpen själv mäter med sin utegivare. Den styr värmekurvan: ju kallare ute, desto varmare framledning. En givare i sol eller nära en husvägg visar för varmt och ger ett för kallt hus.",
        "The outdoor temperature the heat pump measures with its own sensor. It drives the heat curve: the colder outside, the warmer the supply. A sensor in sunshine or close to a wall reads warm and leaves the house cold.",
    ),
    "outdoor_temp_damped": (
        "Utetemperaturen utjämnad över tid efter husets tröghet (byggnadstyp). Det är den här styrenheten räknar värmekurvan på.",
        "The outdoor temperature smoothed over time to match the building's inertia (building type). This is what the controller calculates the heat curve from.",
    ),
    "supply_temp": (
        "Temperaturen på vattnet som går ut till radiatorer och golvvärme (TC1). Följer värmekurvan.",
        "The temperature of the water going out to the radiators and floor heating (TC1). Follows the heat curve.",
    ),
    "return_temp": (
        "Temperaturen på vattnet som kommer tillbaka från huset (TC0). Skillnaden mot framledningen visar hur mycket värme huset tar upp.",
        "The temperature of the water coming back from the house (TC0). Its difference to the supply shows how much heat the house takes.",
    ),
    "supply_target": (
        "Framledningstemperaturen pumpen just nu siktar på, efter värmekurva, rumsbörvärde och tillägg.",
        "The supply temperature the pump is aiming for right now, after heat curve, room setpoint and offsets.",
    ),
    "brine_in": (
        "Köldbäraren (brine) som kommer in från borrhålet eller marken till förångaren. Sjunker under säsongen; under cirka −5 °C bör kollektorn ses över.",
        "The brine coming in from the borehole or ground loop to the evaporator. Falls over the season; below about −5 °C the collector deserves a look.",
    ),
    "brine_out": (
        "Köldbäraren som går tillbaka ut i borrhålet efter att pumpen tagit värme ur den. Normalt 2–4 °C kallare än in när kompressorn går.",
        "The brine going back out to the borehole after the pump has taken heat from it. Normally 2–4 °C colder than the inflow while the compressor runs.",
    ),
    "hot_gas_temp": (
        "Hetgasen direkt efter kompressorn (TR6). Stiger med hög framledning och varmvattenladdning; runt 110 °C stoppar pumpen kompressorn för att skydda den.",
        "The hot gas right after the compressor (TR6). Rises with a high supply temperature and hot water charging; around 110 °C the pump stops the compressor to protect it.",
    ),
    "dhw_temp": (
        "Varmvattnet i beredaren, mätt där pumpen jämför med start- och stopptemperaturen.",
        "The hot water in the cylinder, measured where the pump compares it with its start and stop temperatures.",
    ),
    "dhw_temp_top": (
        "Varmvattnet mätt högre upp i beredaren (TW1), det som kommer ur kranen först.",
        "The hot water measured higher up in the cylinder (TW1), what comes out of the tap first.",
    ),
    "room_temp": ("Rumstemperaturen från en rumsgivare, om en sådan finns.", "The room temperature from a room sensor, where one is fitted."),
    "compressor_on": ("Om kompressorn går just nu.", "Whether the compressor is running right now."),
    "compressor_activity": (
        "Vad pumpen gör: av, värme, varmvatten, kyla, pool, avfrostning eller kompressorlarm.",
        "What the pump is doing: off, heating, hot water, cooling, pool, defrosting or a compressor alarm.",
    ),
    "compressor_speed": ("Kompressorns varvtal i procent av max.", "The compressor's speed in percent of its maximum."),
    "compressor_power": (
        "Elen kompressorn drar just nu, mätt av pumpen själv. Tillsatsen ingår inte.",
        "The electricity the compressor draws right now, as the pump measures it. The aux heater is not included.",
    ),
    "heat_output": ("Värmeeffekten pumpen avger just nu.", "The heat the pump is delivering right now."),
    "compressor_starts": (
        "Kompressorns starter sedan installationen. Många korta starter sliter; en bergvärmepump bör inte behöva mer än några få i timmen.",
        "Compressor starts since installation. Many short runs wear it; a ground source pump should not need more than a few an hour.",
    ),
    "compressor_hours": ("Kompressorns drifttid sedan installationen.", "The compressor's run time since installation."),
    "aux_heater_level": (
        "Hur mycket elpatronen (tillsatsen) ger just nu, i procent. Den går in när kompressorn inte räcker till, vid legionellaprogram och vid larm.",
        "How much the immersion heater (aux heater) gives right now, in percent. It steps in when the compressor is not enough, for the legionella program and on alarms.",
    ),
    "brine_pump_speed": ("Köldbärarpumpens varvtal.", "The brine pump's speed."),
    "circ_pump_speed": ("Laddpumpens (värmebärarens) varvtal.", "The charge (heat carrier) pump's speed."),
    "energy_in_total": (
        "All el pumpen förbrukat sedan den togs i drift, enligt dess egen mätning: kompressor och tillsats. Används för värmefaktorn och passar i energipanelen.",
        "All the electricity the pump has used since it was commissioned, by its own measurement: compressor and aux heater. Used for the coefficient of performance and fit for the energy dashboard.",
    ),
    "energy_out_total": (
        "All värme pumpen levererat sedan den togs i drift, till värme och varmvatten. Delat med förbrukningen blir det värmefaktorn.",
        "All the heat the pump has delivered since it was commissioned, to heating and hot water. Divided by the consumption it is the coefficient of performance.",
    ),
    "energy_in_heating": ("Kompressorns el till uppvärmning sedan driftstart.", "The compressor's electricity for heating since commissioning."),
    "energy_in_dhw": ("Kompressorns el till varmvatten sedan driftstart.", "The compressor's electricity for hot water since commissioning."),
    "energy_out_heating": ("Värme levererad till huset sedan driftstart.", "Heat delivered to the house since commissioning."),
    "energy_out_dhw": ("Värme levererad till varmvattnet sedan driftstart.", "Heat delivered to the hot water since commissioning."),
    "energy_aux_total": ("Elpatronens förbrukning sedan driftstart.", "The immersion heater's consumption since commissioning."),
    "alarm": (
        "Pumpens senaste fel: koden displayen visar, orsakskoden och texten ur IVT:s och Bosch felkodslista. Attributet active säger om felet pågår.",
        "The pump's latest fault: the code the display shows, the cause code and the text from IVT's and Bosch's fault list. The active attribute says whether it is still on.",
    ),
    "controller_alarm": ("Styrenhetens senaste fel.", "The controller's latest fault."),
    "dhw_mode": (
        "Varmvattenläget: hur varmt beredaren laddas och hur ofta. Eko sparar el, komfort ger mer varmvatten.",
        "The hot water mode: how hot the cylinder is charged and how often. Eco saves electricity, comfort gives more hot water.",
    ),
    "dhw_boost": (
        "Startar en engångsladdning av varmvattnet till boosttemperaturen. Det är den här en energistyrning som EMS Steward ska binda som varmvattenberedare med \"boost\" ikryssat. Av avbryter.",
        "Starts a one-time charge of the hot water to the boost temperature. This is the one an energy manager such as EMS Steward binds as its water heater, with \"boost\" ticked. Off stops it.",
    ),
    "dhw_boost_temp": (
        "Temperaturen en engångsladdning går till. Högt ger mer varmvatten men kan stoppa kompressorn på hetgasskyddet så att elpatronen tar resten; på bergvärme brukar 55–58 °C gå på kompressorn ensam.",
        "The temperature a one-time charge goes to. Higher gives more hot water but can trip the compressor's hot gas protection so the immersion heater finishes; on ground source 55–58 °C usually runs on the compressor alone.",
    ),
    "dhw_setpoint": ("Varmvattnets normala börvärde.", "The hot water's normal setpoint."),
    "dhw_charging": ("Om varmvattnet laddas just nu.", "Whether the hot water is being charged right now."),
    "silent_mode": ("Tyst läge sänker kompressorns och fläktens maxvarv under valda tider.", "Silent mode lowers the compressor's and fan's top speed during the chosen hours."),
    "aux_heater_blocked": ("Spärrar elpatronen helt. Huset och varmvattnet kan då bli kalla om kompressorn inte räcker.", "Blocks the immersion heater entirely. The house and hot water may go cold if the compressor is not enough."),
    "heating_off": ("Stänger av uppvärmningen. Varmvattnet fortsätter.", "Switches heating off. Hot water carries on."),
    "heating_mode": (
        "Värmeläget en energistyrning skriver: blocked, eco, normal eller boost. Varje läge flyttar rumsbörvärdet i alla värmekretsar ett steg från husets normala värde, så värmekurvan går upp eller ned. Värmen stängs aldrig av.",
        "The heating mode an energy manager writes: blocked, eco, normal or boost. Each mode moves the room setpoint of every heating circuit a step from the house's normal value, so the heat curve shifts up or down. Heating is never switched off.",
    ),
    "cop_day": ("Värmefaktorn senaste dygnet: levererad värme delad med förbrukad el.", "The coefficient of performance over the last day: heat delivered divided by electricity used."),
    "cop_year": ("Värmefaktorn över ett rullande år. Tills ett år finns visas livstidsvärdet; attributet basis säger vilket.", "The coefficient of performance over a rolling year. Until a year exists the lifetime figure stands in; the basis attribute says which."),
    "cop_lifetime": ("Värmefaktorn över allt räkneverken räknat sedan driftstart.", "The coefficient of performance over everything the counters have counted since commissioning."),
}

CIRCUIT_TEXTS: dict[str, tuple[str, str]] = {
    "room_setpoint": (
        "Rumstemperaturen kretsen ska hålla. Utan rumsgivare flyttar den ändå värmekurvan: en grad upp ger varmare framledning vid alla utetemperaturer. Det är det värmeläget styr.",
        "The room temperature the circuit aims for. Without a room sensor it still moves the heat curve: a degree up gives a warmer supply at every outdoor temperature. This is what the heating mode steers.",
    ),
    "room_temp": ("Rumstemperaturen kretsens rumsgivare mäter.", "The room temperature the circuit's room sensor measures."),
    "target_flow": ("Framledningen styrenheten räknat fram för kretsen just nu.", "The supply temperature the controller has calculated for the circuit right now."),
    "flow_temp": ("Kretsens framledning efter shunten.", "The circuit's supply after the mixing valve."),
    "offset": ("Parallellförskjuter värmekurvan. Ändra en grad och vänta ett dygn.", "Shifts the heat curve in parallel. Change it a degree and wait a day."),
    "mode": ("Kretsens driftsätt: av, manuell (fast börvärde) eller auto (program).", "The circuit's operating mode: off, manual (a fixed setpoint) or auto (program)."),
    "comfort_temp": ("Börvärdet i programmets komfortperioder.", "The setpoint in the program's comfort periods."),
    "eco_temp": ("Börvärdet i programmets sänkta perioder.", "The setpoint in the program's reduced periods."),
    "design_temp": ("Framledningen vid dimensionerande utetemperatur: kurvans lutning.", "The supply at the design outdoor temperature: the slope of the curve."),
    "max_flow": ("Högsta tillåtna framledning i kretsen.", "The highest supply temperature the circuit allows."),
    "min_flow": ("Lägsta framledning i kretsen.", "The lowest supply temperature of the circuit."),
    "summer_mode": ("Sommar stänger värmen över sommargränsen, vinter håller den igång.", "Summer switches heating off above the summer threshold, winter keeps it on."),
    "pump": ("Kretsens cirkulationspump.", "The circuit's circulation pump."),
}

#: Component designations on Bosch/IVT heat pumps.
GLOSSARY: dict[str, tuple[str, str]] = {
    "TC0": ("värmebärarens retur", "heat carrier return"),
    "TC1": ("värmebärarens framledning", "heat carrier supply"),
    "TC3": ("kondensorns utlopp", "condenser outlet"),
    "TR1": ("kompressorns temperatur", "compressor temperature"),
    "TR3": ("vätskeledningen efter kondensorn", "liquid line after the condenser"),
    "TR4": ("förångarens inlopp", "evaporator inlet"),
    "TR5": ("suggasen in till kompressorn", "suction gas into the compressor"),
    "TR6": ("hetgasen efter kompressorn", "hot gas after the compressor"),
    "TR7": ("gasen in i kondensorn", "gas into the condenser"),
    "TL2": ("luftintaget", "air intake"),
    "PL1": ("lågtryckssidan, som mättnadstemperatur", "low pressure side, as saturation temperature"),
    "PH1": ("högtryckssidan, som mättnadstemperatur", "high pressure side, as saturation temperature"),
    "TA4": ("droppskålen", "drain pan"),
    "TW1": ("varmvattenberedaren", "hot water cylinder"),
    "VR0": ("receiverventilen", "receiver valve"),
    "VR1": ("expansionsventilen", "expansion valve"),
    "VR4": ("fyrvägsventilen", "4-way valve"),
    "VC0": ("ventilen VC0", "valve VC0"),
    "VC1": ("shuntventilen", "mixing valve"),
    "PC0": ("värmebärarpumpen", "heat carrier pump"),
    "PC1": ("värmekretsens pump", "heating circuit pump"),
    "EA0": ("kondensvärmaren", "condensate heater"),
    "TS3": ("beredarens mitt", "middle of the cylinder"),
}

_DESIGNATION = re.compile(r"\(([A-Z]{2}\d)\)")


def explain_role(role: str, language: str) -> str:
    index = 0 if language == "sv" else 1
    if role in ROLE_TEXTS:
        return ROLE_TEXTS[role][index]
    head, _, suffix = role.partition("_")
    if head.startswith("hc") and suffix in CIRCUIT_TEXTS:
        return CIRCUIT_TEXTS[suffix][index]
    return ""


def explain_point(point: Point, language: str) -> str:
    """Built from the source's own title and the glossary."""
    sv = language == "sv"
    parts: list[str] = []
    match = _DESIGNATION.search(point.title)
    if match and match.group(1) in GLOSSARY:
        words = GLOSSARY[match.group(1)][0 if sv else 1]
        parts.append(
            f"{match.group(1)} är givaren för {words}." if sv else f"{match.group(1)} is the sensor for the {words}."
        )
    source = {"emsesp": "EMS-ESP", "husdata": "Husdata", "bosch_local": "Bosch-gatewayn", "cloud": "Bosch-molnet"}.get(
        point.source, point.source
    )
    if sv:
        parts.append(f"{source} kallar värdet ”{point.title}” ({point.device}/{point.key}).")
        if point.writable:
            span = _span(point)
            parts.append("Värdet kan ändras" + (f", {span}." if span else "."))
    else:
        parts.append(f"{source} calls it “{point.title}” ({point.device}/{point.key}).")
        if point.writable:
            span = _span(point)
            parts.append("It can be changed" + (f", {span}." if span else "."))
    return " ".join(parts)


def _span(point: Point) -> str:
    if point.minimum is None or point.maximum is None:
        return ""
    unit = f" {point.unit}" if point.unit else ""
    low = int(point.minimum) if float(point.minimum).is_integer() else point.minimum
    high = int(point.maximum) if float(point.maximum).is_integer() else point.maximum
    return f"{low}–{high}{unit}"
