"""Fault strings in words."""

from __future__ import annotations

from custom_components.rego_local_easyconf import faults


def test_the_pumps_open_fault():
    fault = faults.parse("A01(5201) 24.11.2026 13:27 - now")
    assert fault.display == "A01" and fault.cause == 5201
    assert fault.active and fault.end is None
    assert fault.start.hour == 13
    assert faults.text(fault, "sv") == "A01/5201: Varning Kabelbrott i utetemp.givare T1"
    assert "open circuit" in faults.text(fault, "en")


def test_the_controllers_cleared_fault():
    fault = faults.parse("A11(1037) 24.11.2026 13:27-24.11.2026 13:28")
    assert not fault.active
    assert fault.end.minute == 28
    assert faults.text(fault, "sv").startswith("Inget fel nu (senast A11/1037: Utegivare defekt")


def test_the_controllers_open_fault_has_no_end():
    assert faults.parse("A11(1037) 24.11.2026 13:27").active


def test_nothing_and_unknown():
    assert faults.parse("") is None
    assert faults.text(None, "sv") == "Inget fel"
    unknown = faults.parse("Z99(99999) - now")
    assert unknown.active
    assert faults.text(unknown, "en") == "Fault Z99/99999"


def test_the_clouds_notification_reads_alike():
    from custom_components.rego_local_easyconf.bosch_cloud import fault_string

    text = fault_string({"values": [{"cat": "E", "act": "A", "dcd": "A01", "ccd": "5201"}]})
    assert faults.parse(text).cause == 5201 and faults.parse(text).active
    assert fault_string({"values": [{"cat": "E", "act": "H", "dcd": "A01", "ccd": "5201"}]}) == ""
