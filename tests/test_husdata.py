"""Husdata's raw integers, from its documentation (no unit measured)."""

from __future__ import annotations

from custom_components.rego_local_easyconf.husdata import (
    controller_from_status,
    decode,
    encode,
    firmware_of,
    guess_controller,
)


def test_unsigned_16_bit_negatives():
    # Husdata's own example: "0007":65218 is -31.8 °C.
    assert decode("0007", 65218, 0.1) == -31.8
    assert decode("0007", -7, 0.1) == -0.7
    assert decode("0007", 275, 0.1) == 27.5


def test_counters_stay_unsigned_and_large():
    assert decode("6C55", 37018, 1.0) == 37018
    assert decode("5C52", 844329, 0.1) == 84432.9


def test_sentinels():
    assert decode("0009", 65053, 0.1) is None  # -48.3 °C, Rego 600 sensor not connected
    assert decode("0001", 32768, 0.1) is None


def test_on_off():
    assert decode("1A01", 1, None) is True
    assert decode("1A01", 0, None) is False


def test_writes_x10_on_h66_360702_and_raw_before():
    assert encode("0203", 21.5, 0.1, times_ten=True) == 215
    assert encode("0203", 21.5, 0.1, times_ten=False) == 215
    assert encode("2204", 3, 1.0, times_ten=True) == 30
    assert encode("2204", 3, 1.0, times_ten=False) == 3
    assert encode("1231", True, None, times_ten=True) == 1


def test_status_names_the_controller_and_firmware():
    status = {"status": {"H60ver": "191123", "H1ver": "001910", "mac": "cc50e348ccdf"}}
    assert controller_from_status(status) == "00"
    assert firmware_of(status) == ("H60", "191123")
    assert firmware_of({"status": {"H66ver": "360801"}}) == ("H66", "360801")


def test_controller_guessed_from_the_ids_sent():
    assert guess_controller({"0007", "5C51", "5C54", "C130", "9112", "3108"}) == "10"
