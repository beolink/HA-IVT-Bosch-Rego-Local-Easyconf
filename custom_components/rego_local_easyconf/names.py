"""Short names for the points that play no role, and which of them are on by default.

The device page cuts a name at about 25 characters, so these stay at or under
24. EMS-ESP's own titles are in the gateway's language (English unless its
locale was changed) and run long ("refrigerant temperature liquid side
(condenser output) (TR3)"); a point without a name here keeps that title.

Keys are EMS-ESP's, per device. A circuit's points are named once for every
circuit: ``hc1.designtemp`` and ``hc2.designtemp`` both come from
``designtemp`` with ", krets 1" or ", krets 2" after it, and a hot water
point from its ``dhw.`` key with the second cylinder's "2" where there is one.
"""

from __future__ import annotations

from .model import Point

# (sv, en)
BOILER: dict[str, tuple[str, str]] = {
    "heatingactive": ("Värme aktiv", "Heating active"),
    "tapwateractive": ("Varmvatten aktiv", "Hot water active"),
    "selflowtemp": ("Framledning, börvärde", "Supply setpoint"),
    "heatingpumpmod": ("Värmebärarpump, modul.", "Heat carrier pump mod."),
    "curflowtemp": ("Framledning, panna", "Supply, boiler"),
    "rettemp": ("Retur, panna", "Return, boiler"),
    "headertemp": ("Bufferttank/fördelare", "Low loss header"),
    "heatingactivated": ("Värme tillåten", "Heating enabled"),
    "heatingtemp": ("Max värmetemperatur", "Heating temperature"),
    "heatingpump": ("Värmebärarpump", "Heat carrier pump"),
    "pumpcharacter": ("Pumpkarakteristik", "Pump characteristic"),
    "ubauptime": ("Drifttid, styrkort", "Control unit uptime"),
    "servicecodenumber": ("Servicekod", "Service code"),
    "emergencyops": ("Nöddrift", "Emergency operation"),
    "emergencytemp": ("Nöddrift, temperatur", "Emergency temperature"),
    "pc1on": ("Pump PC1", "Pump PC1"),
    "pc1rate": ("Pump PC1, varvtal", "Pump PC1 rate"),
    "pumpkickhour": ("Pumpmotion, timme", "Pump kick hour"),
    "pumpkickday": ("Pumpmotion, dag", "Pump kick day"),
    "pumpkickdelay": ("Pumpmotion, intervall", "Pump kick delay"),
    "uptimetotal": ("Drifttid, totalt", "Total uptime"),
    "uptimecontrol": ("Drifttid, värme", "Run time, heat"),
    "uptimecompheating": ("Kompr. drifttid, värme", "Compr. time, heating"),
    "uptimecompcooling": ("Kompr. drifttid, kyla", "Compr. time, cooling"),
    "dhw.uptimecomp": ("Kompr. drifttid, VV", "Compr. time, hot water"),
    "uptimecomppool": ("Kompr. drifttid, pool", "Compr. time, pool"),
    "heatingstarts": ("Starter, värme", "Starts, heating"),
    "coolingstarts": ("Starter, kyla", "Starts, cooling"),
    "dhw.startshp": ("Starter, varmvatten", "Starts, hot water"),
    "poolstarts": ("Starter, pool", "Starts, pool"),
    "nrgconscomptotal": ("Förbrukning, kompressor", "Consumption, compressor"),
    "nrgconscompcooling": ("Förbrukning, kyla", "Consumption, cooling"),
    "nrgconscomppool": ("Förbrukning, pool", "Consumption, pool"),
    "auxelecheatnrgconsheating": ("Tillsats, värme", "Aux heater, heating"),
    "dhw.auxelecheatnrgcons": ("Tillsats, varmvatten", "Aux heater, hot water"),
    "auxelecheatnrgconspool": ("Tillsats, pool", "Aux heater, pool"),
    "nrgsuppcooling": ("Produktion, kyla", "Production, cooling"),
    "nrgsupppool": ("Produktion, pool", "Production, pool"),
    "hpmaxpower": ("Kompressor, maxeffekt", "Compressor max power"),
    "pvmaxcomp": ("Kompressor max vid sol", "Compr. max with PV"),
    "hpswitchvalve": ("Växelventil", "Switch valve"),
    "hptargetspd": ("Kompressor, mål-varvtal", "Compressor target speed"),
    "recvalve": ("Receiverventil VR0", "Receiver valve VR0"),
    "expvalve": ("Expansionsventil VR1", "Expansion valve VR1"),
    "hptc3": ("Kondensor ut (TC3)", "Condenser out (TC3)"),
    "hptr1": ("Kompressor (TR1)", "Compressor (TR1)"),
    "hptr3": ("Vätskeledning (TR3)", "Liquid line (TR3)"),
    "hptr4": ("Förångare in (TR4)", "Evaporator in (TR4)"),
    "hptr5": ("Suggas (TR5)", "Suction gas (TR5)"),
    "hptr7": ("Kondensor in, gas (TR7)", "Condenser gas in (TR7)"),
    "hptl2": ("Luft in (TL2)", "Air inlet (TL2)"),
    "hppl1": ("Lågtryck (PL1)", "Low pressure (PL1)"),
    "hpph1": ("Högtryck (PH1)", "High pressure (PH1)"),
    "hpta4": ("Droppskål (TA4)", "Drain pan (TA4)"),
    "hptw1": ("Varmvattentank (TW1)", "Hot water tank (TW1)"),
    "hptc0": ("Retur (TC0)", "Return (TC0)"),
    "hptc1": ("Framledning (TC1)", "Supply (TC1)"),
    "poolsettemp": ("Pool, börvärde", "Pool setpoint"),
    "hpin1": ("Ingång 1", "Input 1"),
    "hpin2": ("Ingång 2", "Input 2"),
    "hpin3": ("Ingång 3", "Input 3"),
    "hpin4": ("Ingång 4", "Input 4"),
    "hpin1opt": ("Ingång 1, val", "Input 1 options"),
    "hpin2opt": ("Ingång 2, val", "Input 2 options"),
    "hpin3opt": ("Ingång 3, val", "Input 3 options"),
    "hpin4opt": ("Ingång 4, val", "Input 4 options"),
    "maxheatcomp": ("Tillsats max, kompressor", "Heat limit, compressor"),
    "maxheatheat": ("Tillsats max, värme", "Heat limit, heating"),
    "dhw.maxheat": ("Tillsats max, VV", "Heat limit, hot water"),
    "auxheatersource": ("Tillsatskälla", "Aux heater source"),
    "pvcooling": ("Kyla bara med sol", "Cooling only with PV"),
    "auxheateronly": ("Endast tillsats", "Aux heater only"),
    "auxheaterstatus": ("Tillsats, status", "Aux heater status"),
    "auxheaterdelay": ("Tillsats, fördröjning", "Aux heater delay"),
    "auxmaxlimit": ("Tillsats, maxgräns", "Aux heater max limit"),
    "auxlimitstart": ("Tillsats, startgräns", "Aux heater start limit"),
    "auxheatrmode": ("Tillsats, läge", "Aux heater mode"),
    "hphystheat": ("Hysteres, värme", "Hysteresis, heating"),
    "hphystcool": ("Hysteres, kyla", "Hysteresis, cooling"),
    "hphystpool": ("Hysteres, pool", "Hysteresis, pool"),
    "silentfrom": ("Tyst läge från", "Silent mode from"),
    "silentto": ("Tyst läge till", "Silent mode to"),
    "mintempsilent": ("Tyst läge, min ute", "Silent mode min outdoor"),
    "tempparmode": ("Parallelldrift under", "Parallel mode below"),
    "auxheatmix": ("Tillsats, shunt", "Aux heater mixer"),
    "tempdiffheat": ("Delta TC3/TC0, värme", "Delta TC3/TC0, heat"),
    "tempdiffcool": ("Delta TC3/TC0, kyla", "Delta TC3/TC0, cool"),
    "vpcooling": ("Ventil/pump kyla", "Valve/pump cooling"),
    "heatcable": ("Värmekabel", "Heating cable"),
    "vc0valve": ("Ventil VC0", "Valve VC0"),
    "primepump": ("Primärpump", "Primary pump"),
    "primepumpmod": ("Primärpump, modul.", "Primary pump mod."),
    "hp3way": ("Trevägsventil", "3-way valve"),
    "elheatstep1": ("Elsteg 1", "Electric step 1"),
    "elheatstep2": ("Elsteg 2", "Electric step 2"),
    "elheatstep3": ("Elsteg 3", "Electric step 3"),
    "hpea0": ("Kondensvärmare (EA0)", "Condensate heater (EA0)"),
    "fanspd": ("Fläkt, varvtal", "Fan speed"),
    "hppowerlimit": ("Effektgräns", "Power limit"),
    "dhw.alternatingop": ("VV, växeldrift", "DHW, alternating op."),
    "dhw.altopprioheat": ("Växeldrift, tid värme", "Alt. op., heating time"),
    "dhw.altopprio": ("Växeldrift, tid VV", "Alt. op., DHW time"),
    "dhw.comfoff": ("VV komfort, stopp", "DHW comfort, stop"),
    "dhw.ecooff": ("VV eko, stopp", "DHW eco, stop"),
    "dhw.ecoplusoff": ("VV eko+, stopp", "DHW eco+, stop"),
    "dhw.hpcircpump": ("VV, cirk.pump tillåten", "DHW, circ. pump allowed"),
    "dhw.settemp": ("VV, aktuellt börvärde", "DHW, current setpoint"),
    "dhw.seltemplow": ("VV, lägre börvärde", "DHW, lower setpoint"),
    "dhw.tempecoplus": ("VV, eko+ börvärde", "DHW, eco+ setpoint"),
    "dhw.comfort1": ("VV, komfortläge", "DHW comfort mode"),
    "dhw.flowtempoffset": ("VV, framledningstillägg", "DHW, supply offset"),
    "dhw.circpump": ("VVC-pump finns", "DHW circ. pump fitted"),
    "dhw.hyston": ("VV, hysteres på", "DHW, hysteresis on"),
    "dhw.hystoff": ("VV, hysteres av", "DHW, hysteresis off"),
    "dhw.disinfectiontemp": ("Legionella, temperatur", "Disinfection temp."),
    "dhw.circmode": ("VVC-pump, läge", "DHW circ. pump mode"),
    "dhw.circ": ("VVC aktiv", "DHW circulation active"),
    "dhw.curflow": ("Tappflöde", "Tap water flow"),
    "dhw.activated": ("Varmvatten tillåtet", "DHW enabled"),
    "dhw.onetime": ("VV engångsladdning", "DHW one-time charge"),
    "dhw.disinfecting": ("Legionella pågår", "Disinfecting"),
    "dhw.recharging": ("VV, omladdning", "DHW recharging"),
    "dhw.tempok": ("VV, temperatur nådd", "DHW temperature ok"),
    "dhw.3wayvalve": ("VV, trevägsventil", "DHW 3-way valve"),
    "dhw.dhwprio": ("VV-prioritet", "DHW priority"),
    "reset": ("Återställ", "Reset"),
    "chimneysweeper": ("Sotarfunktion", "Chimney sweeper"),
    "mandefrost": ("Manuell avfrostning", "Manual defrost"),
    "lastcode": ("Senaste fel", "Last error"),
}

THERMOSTAT: dict[str, tuple[str, str]] = {
    "datetime": ("Datum och tid", "Date and time"),
    "intoffset": ("Rumsgivare, justering", "Room sensor offset"),
    "floordry": ("Golvtorkning", "Floor drying"),
    "floordrytemp": ("Golvtorkning, temp.", "Floor drying temp."),
    "building": ("Byggnadstyp", "Building type"),
    "minexttemp": ("Dimensionerande ute", "Design outdoor temp."),
    "damping": ("Dämpning utegivare", "Outdoor damping"),
    "solar": ("Solvärme", "Solar"),
    "energycostratio": ("Energiprisförhållande", "Energy cost ratio"),
    "pvenabledhw": ("Höj VV med solel", "Raise DHW with PV"),
    "pvraiseheat": ("Höj värme med solel", "Raise heating with PV"),
    "pvlowercool": ("Sänk kyla med solel", "Lower cooling with PV"),
    "absent": ("Bortrest", "Absent"),
    "dhw.modetype": ("VV, aktivt läge", "DHW active mode"),
    "dhw.circmode": ("VVC, läge", "DHW circulation mode"),
    "dhw.chargeduration": ("Extra VV, varaktighet", "Extra DHW duration"),
    "dhw.extra": ("Extra VV pågår", "Extra DHW running"),
    "dhw.disinfecting": ("Legionellaprogram", "Disinfection program"),
    "dhw.disinfectday": ("Legionella, dag", "Disinfection day"),
    "dhw.disinfecttime": ("Legionella, tid", "Disinfection time"),
    "dhw.dailyheating": ("Daglig uppvärmning", "Daily heating"),
    "dhw.dailyheattime": ("Daglig uppv., tid", "Daily heating time"),
    "lastcode": ("Senaste fel, styrenhet", "Last error, controller"),
}

#: Circuit points, named once: "hc1.designtemp" -> "designtemp".
CIRCUIT: dict[str, tuple[str, str]] = {
    "haclimate": ("Klimat visar", "Climate shows"),
    "modetype": ("Aktivt läge", "Active mode"),
    "manualtemp": ("Manuell temperatur", "Manual temperature"),
    "summertemp": ("Sommargräns", "Summer threshold"),
    "baseflowtemp": ("Fotpunkt", "Base flow temperature"),
    "roominfluence": ("Rumsgivarpåverkan", "Room influence"),
    "roominflfactor": ("Rumspåverkan, faktor", "Room influence factor"),
    "curroominfl": ("Rumspåverkan nu", "Current room influence"),
    "nofrostmode": ("Frostskydd, läge", "Frost protection mode"),
    "nofrosttemp": ("Frostskydd, temp.", "Frost protection temp."),
    "heatingtype": ("Värmesystem", "Heating type"),
    "summermode": ("Sommar/vinter nu", "Summer/winter now"),
    "vacationmode": ("Semesterläge", "Vacation mode"),
    "controlmode": ("Reglering", "Control mode"),
    "program": ("Program", "Program"),
    "tempautotemp": ("Tillfällig temp. auto", "Temporary temp. auto"),
    "cooltemp": ("Kyltemperatur", "Cooling temperature"),
    "fastheatup": ("Snabbuppvärmning", "Fast heat-up"),
    "comfoffset": ("Komfortpunkt, tillägg", "Comfort point offset"),
    "comftemp": ("Komfortpunkt, temp.", "Comfort point temp."),
    "switchonoptimization": ("Startoptimering", "Switch-on optimisation"),
    "reducemode": ("Sänkningsläge", "Reduce mode"),
    "noreducetemp": ("Ingen sänkning under", "No reduction below"),
    "reducetemp": ("Sänkning/av-gräns", "Reduce/off threshold"),
    "hpcooling": ("Kyla tillåten", "Cooling allowed"),
    "coolingon": ("Kyla på", "Cooling on"),
    "hpmode": ("Värme/kyla", "Heat/cool mode"),
    "dewoffset": ("Daggpunkt, marginal", "Dew point offset"),
    "roomtempdiff": ("Rumstemp.-differens", "Room temp. difference"),
    "hpminflowtemp": ("VP min framledning", "HP min supply"),
    "control": ("Rumsenhet", "Room unit"),
    "remotetemp": ("Fjärrgivare, temp.", "Remote sensor temp."),
    "remotehum": ("Fjärrgivare, fukt", "Remote sensor humidity"),
    "boost": ("Boost", "Boost"),
    "boosttime": ("Boost, tid", "Boost time"),
    "switchprogmode": ("Programläge", "Program switch mode"),
    "redthreshold": ("Sänkningströskel", "Reduction threshold"),
    "solarinfl": ("Solpåverkan", "Solar influence"),
    "currsolarinfl": ("Solpåverkan nu", "Current solar influence"),
    # mixer (MM100) circuit points
    "valvestatus": ("Shuntventil", "Mixing valve"),
    "flowsettemp": ("Shunt, börvärde", "Mixer setpoint"),
    "activated": ("Krets aktiverad", "Circuit enabled"),
    "valvesettime": ("Shunt, gångtid", "Valve run time"),
    "flowtempoffset": ("Shunt, tillägg", "Mixer offset"),
    "dhwprio": ("VV-prioritet", "DHW priority"),
}

DEVICES: dict[str, dict[str, tuple[str, str]]] = {
    "boiler": BOILER,
    "thermostat": THERMOSTAT,
}

#: An installation's own points switched on by default: what a person
#: checking on the pump looks at, beyond the roles (which are always on).
DEFAULT_ON: dict[str, frozenset[str]] = {
    "boiler": frozenset(
        {
            "hptc3", "hptr1", "hppl1", "hpph1", "hptw1", "heatingactive",
            "tapwateractive", "uptimecompheating", "dhw.uptimecomp", "heatingstarts",
            "dhw.startshp", "auxheaterstatus", "hpswitchvalve", "dhw.settemp",
            "dhw.activated", "nrgconscomptotal", "heatingpump", "maxheatcomp",
            "maxheatheat", "dhw.maxheat", "dhw.alternatingop",
        }
    ),
    "thermostat": frozenset({"building", "minexttemp", "absent", "dhw.extra", "dhw.chargeduration"}),
    "mixer": frozenset(),
}
CIRCUIT_DEFAULT_ON = frozenset({"heatingtype", "controlmode", "baseflowtemp", "roominfluence", "modetype", "valvestatus", "summermode"})


def _circuit_label(circuit: str, language: str) -> str:
    if circuit.startswith("hc"):
        return f"krets {circuit[2:]}" if language == "sv" else f"circuit {circuit[2:]}"
    if circuit.startswith("dhw") and circuit != "dhw":
        return f"VV {circuit[3:]}" if language == "sv" else f"DHW {circuit[3:]}"
    return ""


def name_for(point: Point, language: str) -> str:
    """The short name of a point that plays no role."""
    index = 0 if language == "sv" else 1
    table = DEVICES.get(point.device, {})
    if point.key in table:
        return table[point.key][index]
    head, _, tail = point.key.partition(".")
    if tail and head.startswith("hc"):
        names = CIRCUIT.get(tail) or table.get(tail)
        if names:
            return f"{names[index]}, {_circuit_label(head, language)}"
    if tail and head.startswith("dhw") and head != "dhw":
        # A second cylinder: dhw2.seltemp is named like dhw.seltemp, with its number.
        names = table.get(f"dhw.{tail}")
        if names:
            return f"{names[index]} ({_circuit_label(head, language)})"
    return _clean_title(point)


def _clean_title(point: Point) -> str:
    """The source's own title, first letter up, circuit prefix moved to the end."""
    title = point.title.strip()
    if point.circuit and title.lower().startswith(point.circuit.lower() + " "):
        title = f"{title[len(point.circuit) + 1:]} ({point.circuit})"
    return title[:1].upper() + title[1:] if title else point.key


def default_on(point: Point, *, first_source: bool) -> bool:
    if not first_source:
        return False
    if point.key in DEFAULT_ON.get(point.device, frozenset()):
        return True
    head, _, tail = point.key.partition(".")
    return bool(tail) and head.startswith("hc") and tail in CIRCUIT_DEFAULT_ON
