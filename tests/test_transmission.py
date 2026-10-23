import logging
from dataclasses import FrozenInstanceError

import pytest

from busscope.transmission import (
    TRANSMISSION_SWITCH,
    ManualTransmission,
    transmission_enabled,
)


@pytest.mark.parametrize(
    ("identifier", "expected"),
    [("0", 0), ("0x1FFFFFFF", 0x1FFFFFFF), ("aBcDe", 0xABCDE)],
)
def test_manual_transmission_parses_valid_boundaries(identifier: str, expected: int) -> None:
    request = ManualTransmission.from_text(" can0 ", identifier, "01 02 a3 B4 05 06 07 08")

    assert request.channel == "can0"
    assert request.arbitration_id == expected
    assert request.identifier_hex == f"0x{expected:08X}"
    assert request.payload_hex == "01 02 A3 B4 05 06 07 08"


@pytest.mark.parametrize("identifier", ["", "0x", "-1", "123G", "20000000"])
def test_manual_transmission_rejects_invalid_identifier(identifier: str) -> None:
    with pytest.raises(ValueError, match="identifier"):
        ManualTransmission.from_text("can0", identifier, "01 02 03 04 05 06 07 08")


@pytest.mark.parametrize(
    "payload",
    [
        "01 02 03 04 05 06 07",
        "01 02 03 04 05 06 07 08 09",
        "0102030405060708",
        "[01 02 03 04 05 06 07 08]",
        "01,02,03,04,05,06,07,08",
        "01 02 03 04 05 06 07 GG",
        "1 02 03 04 05 06 07 08",
    ],
)
def test_manual_transmission_rejects_invalid_payload(payload: str) -> None:
    with pytest.raises(ValueError, match="payload|byte"):
        ManualTransmission.from_text("can0", "123", payload)


@pytest.mark.parametrize("channel", ["", " can0 extra ", "-can0", "a" * 16])
def test_manual_transmission_rejects_invalid_channel(channel: str) -> None:
    with pytest.raises(ValueError, match="channel"):
        ManualTransmission.from_text(channel, "123", "01 02 03 04 05 06 07 08")


def test_manual_transmission_enforces_invariants_and_is_immutable() -> None:
    request = ManualTransmission("can0", 0x123, bytes(8))

    with pytest.raises(FrozenInstanceError):
        request.channel = "can1"  # type: ignore[misc]
    with pytest.raises(ValueError, match="identifier"):
        ManualTransmission("can0", -1, bytes(8))
    with pytest.raises(ValueError, match="8 bytes"):
        ManualTransmission("can0", 0x123, bytes(7))
    with pytest.raises(ValueError, match="8 bytes"):
        ManualTransmission("can0", 0x123, bytearray(8))  # type: ignore[arg-type]


@pytest.mark.parametrize(
    ("environment", "expected"),
    [
        ({}, False),
        ({"BUSSCOPE_ENABLE_TRANSMISSION": ""}, False),
        ({"BUSSCOPE_ENABLE_TRANSMISSION": "0"}, False),
        ({"BUSSCOPE_ENABLE_TRANSMISSION": "1"}, True),
    ],
)
def test_transmission_switch_is_off_unless_exactly_one(
    environment: dict[str, str], expected: bool
) -> None:
    assert transmission_enabled(environment) is expected


@pytest.mark.parametrize("value", ["true", "yes", " 1", "1 ", "01", "2", "on"])
def test_transmission_switch_ignores_malformed_values_with_a_warning(
    value: str, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="busscope.transmission"):
        enabled = transmission_enabled({TRANSMISSION_SWITCH: value})

    assert enabled is False
    assert TRANSMISSION_SWITCH in caplog.text
