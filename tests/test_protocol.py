import pytest

from busscope.protocol import CanFrame, ProtocolDecoder


def test_decodes_documented_extended_identifier() -> None:
    frame = CanFrame(0x029A3FF0, bytes.fromhex("01 00 00 00 00 00 00 00"))

    result = ProtocolDecoder().decode(frame)

    assert result.identifier is not None
    assert result.identifier.error_code == 0
    assert result.identifier.device_number == 0x0A
    assert result.identifier.command_number == 0x1A
    assert result.identifier.destination_address == 0x3F
    assert result.identifier.source_address == 0xF0
    assert result.diagnostics == ()


def test_preserves_frame_and_reports_non_extended_identifier() -> None:
    frame = CanFrame(0x123, b"", is_extended_id=False)

    result = ProtocolDecoder().decode(frame)

    assert result.frame == frame
    assert result.identifier is None
    assert "29-bit extended" in result.diagnostics[0]
    assert "8-byte payload" in result.diagnostics[1]


def test_reports_controller_error_frame_without_dropping_payload() -> None:
    frame = CanFrame(0, b"", is_error_frame=True)

    result = ProtocolDecoder().decode(frame)

    assert result.frame == frame
    assert result.identifier is None
    assert result.diagnostics == ("CAN controller error frame", "Expected an 8-byte payload")


def test_decodes_module_state_and_signed_ambient_temperature() -> None:
    frame = CanFrame(0x028400F0, bytes.fromhex("00 00 00 00 FE 80 41 01"))

    result = ProtocolDecoder().decode(frame)

    assert result.ambient_temperature_celsius == -2
    assert result.module_state is not None
    assert result.module_state.communication_interrupt is True
    assert result.module_state.module_off is False
    assert result.module_state.input_over_voltage is True
    assert result.module_state.power_limit is True
    assert result.module_state.output_short is True
    assert result.module_state.active_faults() == (
        "communication_interrupt",
        "input_over_voltage",
        "power_limit",
        "output_short",
    )


def test_decodes_documented_system_module_count() -> None:
    frame = CanFrame(0x0282F03F, bytes.fromhex("00 00 07 00 00 00 00 00"))

    result = ProtocolDecoder().decode(frame)

    assert result.module_count == 7
    assert result.module_group_number is None


def test_decodes_documented_group_module_count() -> None:
    frame = CanFrame(0x02C2F001, bytes.fromhex("00 00 03 00 00 00 00 00"))

    result = ProtocolDecoder().decode(frame)

    assert result.identifier is not None
    assert result.identifier.device_number == 0x0B
    assert result.identifier.source_address == 1
    assert result.module_count == 3


def test_decodes_documented_module_group_with_existing_information() -> None:
    frame = CanFrame(0x0284F001, bytes.fromhex("00 00 02 00 1B 00 40 00"))

    result = ProtocolDecoder().decode(frame)

    assert result.module_group_number == 2
    assert result.module_count is None
    assert result.ambient_temperature_celsius == 27
    assert result.module_state is not None


@pytest.mark.parametrize(
    ("arbitration_id", "field"),
    [(0x0282F03F, "module_count"), (0x0284F001, "module_group_number")],
)
@pytest.mark.parametrize("value", [0, 255])
def test_decodes_topology_byte_as_unsigned(
    arbitration_id: int,
    field: str,
    value: int,
) -> None:
    frame = CanFrame(arbitration_id, bytes((0, 0, value, 0, 0, 0, 0, 0)))

    result = ProtocolDecoder().decode(frame)

    assert getattr(result, field) == value


@pytest.mark.parametrize("arbitration_id", [0x0282F03F, 0x0284F001])
@pytest.mark.parametrize("payload", [bytes(7), bytes(9)])
def test_invalid_payload_length_does_not_expose_topology(
    arbitration_id: int,
    payload: bytes,
) -> None:
    result = ProtocolDecoder().decode(CanFrame(arbitration_id, payload))

    assert result.module_count is None
    assert result.module_group_number is None
    assert result.diagnostics == ("Expected an 8-byte payload",)


def test_decodes_documented_system_voltage_and_current() -> None:
    frame = CanFrame(0x02813FF0, bytes.fromhex("43 FA 00 00 42 48 00 00"))

    result = ProtocolDecoder().decode(frame)

    assert result.system_measurements is not None
    assert result.system_measurements.output_voltage_volts == 500.0
    assert result.system_measurements.total_output_current_amperes == 50.0
    assert result.module_count is None
    assert result.module_group_number is None


def test_decodes_documented_module_voltage_and_current() -> None:
    frame = CanFrame(0x028300F0, bytes.fromhex("43 FA 00 00 40 60 00 00"))

    result = ProtocolDecoder().decode(frame)

    assert result.module_measurements is not None
    assert result.module_measurements.output_voltage_volts == 500.0
    assert result.module_measurements.output_current_amperes == 3.5


def test_decodes_documented_ac_input_voltages() -> None:
    frame = CanFrame(0x028600F0, bytes.fromhex("0F B4 0F A5 0F A7 00 00"))

    result = ProtocolDecoder().decode(frame)

    assert result.ac_input_measurements is not None
    assert result.ac_input_measurements.first_phase_voltage_volts == 402.0
    assert result.ac_input_measurements.second_phase_voltage_volts == 400.5
    assert result.ac_input_measurements.third_phase_voltage_volts == 400.7


def test_decodes_documented_module_ratings() -> None:
    frame = CanFrame(0x028A00F0, bytes.fromhex("02 EE 00 64 01 00 05 DC"))

    result = ProtocolDecoder().decode(frame)

    assert result.module_ratings is not None
    assert result.module_ratings.maximum_output_voltage_volts == 750
    assert result.module_ratings.minimum_output_voltage_volts == 100
    assert result.module_ratings.maximum_output_current_amperes == 25.6
    assert result.module_ratings.rated_output_power_watts == 15000


def test_decodes_documented_module_availability() -> None:
    frame = CanFrame(0x028C00F0, bytes.fromhex("13 58 01 66 00 00 00 00"))

    result = ProtocolDecoder().decode(frame)

    assert result.module_availability is not None
    assert result.module_availability.external_voltage_volts == 495.2
    assert result.module_availability.available_current_amperes == 35.8
    assert result.module_availability.indicates_power_off() is False


def test_zero_available_current_indicates_power_off() -> None:
    frame = CanFrame(0x028C00F0, bytes.fromhex("13 58 00 00 00 00 00 00"))

    result = ProtocolDecoder().decode(frame)

    assert result.module_availability is not None
    assert result.module_availability.indicates_power_off() is True
