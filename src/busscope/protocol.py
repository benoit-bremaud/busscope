"""Pure Infypower charger CAN protocol decoding."""

from collections.abc import Callable
from dataclasses import dataclass
from struct import unpack


@dataclass(frozen=True, slots=True)
class CanFrame:
    """Hardware-independent representation of a received CAN frame."""

    arbitration_id: int
    data: bytes
    is_extended_id: bool = True
    is_error_frame: bool = False


@dataclass(frozen=True, slots=True)
class InfypowerIdentifier:
    """Fields extracted from the 29-bit Infypower arbitration identifier."""

    raw: int
    error_code: int
    device_number: int
    command_number: int
    destination_address: int
    source_address: int


@dataclass(frozen=True, slots=True)
class ModuleState:
    """Named state and fault flags from an Infypower module response."""

    communication_interrupt: bool = False
    walk_in_enabled: bool = False
    output_over_voltage: bool = False
    over_temperature: bool = False
    fan_fault: bool = False
    module_protect: bool = False
    module_fault: bool = False
    module_off: bool = False
    input_over_voltage: bool = False
    input_under_voltage: bool = False
    input_unbalance: bool = False
    input_phase_lost: bool = False
    load_unsharing: bool = False
    module_id_repetition: bool = False
    power_limit: bool = False
    pfc_off: bool = False
    air_duct_obstruction: bool = False
    discharge_abnormal: bool = False
    pfc_abnormal: bool = False
    internal_communication_interrupt: bool = False
    hardware_failure: bool = False
    output_short: bool = False

    def active_faults(self) -> tuple[str, ...]:
        """Return active fault names in a stable display order."""
        return tuple(
            name
            for name, active in (
                ("communication_interrupt", self.communication_interrupt),
                ("output_over_voltage", self.output_over_voltage),
                ("over_temperature", self.over_temperature),
                ("fan_fault", self.fan_fault),
                ("module_protect", self.module_protect),
                ("module_fault", self.module_fault),
                ("module_off", self.module_off),
                ("input_over_voltage", self.input_over_voltage),
                ("input_under_voltage", self.input_under_voltage),
                ("input_unbalance", self.input_unbalance),
                ("input_phase_lost", self.input_phase_lost),
                ("load_unsharing", self.load_unsharing),
                ("module_id_repetition", self.module_id_repetition),
                ("power_limit", self.power_limit),
                ("pfc_off", self.pfc_off),
                ("air_duct_obstruction", self.air_duct_obstruction),
                ("discharge_abnormal", self.discharge_abnormal),
                ("pfc_abnormal", self.pfc_abnormal),
                ("internal_communication_interrupt", self.internal_communication_interrupt),
                ("hardware_failure", self.hardware_failure),
                ("output_short", self.output_short),
            )
            if active
        )


@dataclass(frozen=True, slots=True)
class SystemMeasurements:
    """System output measurements from an Infypower command 0x01 response."""

    output_voltage_volts: float
    total_output_current_amperes: float


@dataclass(frozen=True, slots=True)
class ModuleMeasurements:
    """Output measurements from an Infypower command 0x03 response."""

    output_voltage_volts: float
    output_current_amperes: float


@dataclass(frozen=True, slots=True)
class ACInputMeasurements:
    """AC input voltages from an Infypower command 0x06 response."""

    first_phase_voltage_volts: float
    second_phase_voltage_volts: float
    third_phase_voltage_volts: float


@dataclass(frozen=True, slots=True)
class ModuleRatings:
    """Nominal ratings from an Infypower command 0x0A response."""

    maximum_output_voltage_volts: float
    minimum_output_voltage_volts: float
    maximum_output_current_amperes: float
    rated_output_power_watts: float


@dataclass(frozen=True, slots=True)
class ModuleAvailability:
    """Available output capacity from an Infypower command 0x0C response."""

    external_voltage_volts: float
    available_current_amperes: float

    def indicates_power_off(self) -> bool:
        """Return whether the documented zero-current power-off condition is present."""
        return self.available_current_amperes == 0


@dataclass(frozen=True, slots=True)
class DecodeResult:
    """Decoded information while preserving the original frame."""

    frame: CanFrame
    identifier: InfypowerIdentifier | None
    description: str
    module_state: ModuleState | None = None
    ambient_temperature_celsius: int | None = None
    system_measurements: SystemMeasurements | None = None
    module_measurements: ModuleMeasurements | None = None
    ac_input_measurements: ACInputMeasurements | None = None
    module_ratings: ModuleRatings | None = None
    module_availability: ModuleAvailability | None = None
    diagnostics: tuple[str, ...] = ()
    module_count: int | None = None
    module_group_number: int | None = None


def format_decoded_values(result: DecodeResult, number: Callable[[float], str]) -> list[str]:
    """Render every decoded value of ``result`` as short ``name=value unit`` items."""
    values: list[str] = []
    if (system := result.system_measurements) is not None:
        values.append(
            f"Vout={number(system.output_voltage_volts)} V, "
            f"Iout={number(system.total_output_current_amperes)} A"
        )
    if (module := result.module_measurements) is not None:
        values.append(
            f"Module Vout={number(module.output_voltage_volts)} V, "
            f"Iout={number(module.output_current_amperes)} A"
        )
    if (ac := result.ac_input_measurements) is not None:
        values.append(
            f"AC={number(ac.first_phase_voltage_volts)}/"
            f"{number(ac.second_phase_voltage_volts)}/"
            f"{number(ac.third_phase_voltage_volts)} V"
        )
    if (availability := result.module_availability) is not None:
        values.append(f"Available={number(availability.available_current_amperes)} A")
    if (ratings := result.module_ratings) is not None:
        values.append(
            f"Ratings={number(ratings.minimum_output_voltage_volts)}-"
            f"{number(ratings.maximum_output_voltage_volts)} V, "
            f"{number(ratings.maximum_output_current_amperes)} A, "
            f"{number(ratings.rated_output_power_watts)} W"
        )
    if result.module_count is not None:
        values.append(f"Modules={result.module_count}")
    if result.module_group_number is not None:
        values.append(f"Group={result.module_group_number}")
    if result.ambient_temperature_celsius is not None:
        values.append(f"Ambient={result.ambient_temperature_celsius} °C")
    if result.module_state is not None:
        faults = result.module_state.active_faults()
        values.append(f"Faults={', '.join(faults) if faults else 'none'}")
    return values


class ProtocolDecoder:
    """Decode the stable identifier layer of the Infypower protocol."""

    _MAX_EXTENDED_ID = (1 << 29) - 1
    _ERROR_SHIFT = 26
    _DEVICE_SHIFT = 22
    _COMMAND_SHIFT = 16
    _BYTE_MASK = 0xFF
    _DEVICE_MASK = 0x0F
    _COMMAND_MASK = 0x3F
    _ERROR_MASK = 0x07

    def decode(self, frame: CanFrame) -> DecodeResult:
        """Decode one frame without hardware or UI side effects."""
        diagnostics: list[str] = []
        identifier: InfypowerIdentifier | None = None

        if frame.is_error_frame:
            diagnostics.append("CAN controller error frame")
        elif not frame.is_extended_id:
            diagnostics.append("Expected a 29-bit extended identifier")
        elif not 0 <= frame.arbitration_id <= self._MAX_EXTENDED_ID:
            diagnostics.append("Identifier is outside the 29-bit extended range")
        else:
            identifier = self._parse_identifier(frame.arbitration_id)

        if len(frame.data) != 8:
            diagnostics.append("Expected an 8-byte payload")

        module_state: ModuleState | None = None
        ambient_temperature: int | None = None
        system_measurements: SystemMeasurements | None = None
        module_measurements: ModuleMeasurements | None = None
        ac_input_measurements: ACInputMeasurements | None = None
        module_ratings: ModuleRatings | None = None
        module_availability: ModuleAvailability | None = None
        module_count: int | None = None
        module_group_number: int | None = None
        if identifier is not None and identifier.command_number == 0x02 and len(frame.data) == 8:
            module_count = frame.data[2]
        if identifier is not None and identifier.command_number == 0x04 and len(frame.data) == 8:
            module_group_number = frame.data[2]
            ambient_temperature = int.from_bytes(frame.data[4:5], byteorder="big", signed=True)
            module_state = self._decode_module_state(frame.data[5:8])
        if identifier is not None and identifier.command_number == 0x01 and len(frame.data) == 8:
            system_measurements = SystemMeasurements(
                output_voltage_volts=unpack(">f", frame.data[0:4])[0],
                total_output_current_amperes=unpack(">f", frame.data[4:8])[0],
            )
        if identifier is not None and identifier.command_number == 0x03 and len(frame.data) == 8:
            module_measurements = ModuleMeasurements(
                output_voltage_volts=unpack(">f", frame.data[0:4])[0],
                output_current_amperes=unpack(">f", frame.data[4:8])[0],
            )
        if identifier is not None and identifier.command_number == 0x06 and len(frame.data) == 8:
            ac_input_measurements = ACInputMeasurements(
                first_phase_voltage_volts=self._decode_tenth_volt(frame.data[0:2]),
                second_phase_voltage_volts=self._decode_tenth_volt(frame.data[2:4]),
                third_phase_voltage_volts=self._decode_tenth_volt(frame.data[4:6]),
            )
        if identifier is not None and identifier.command_number == 0x0A and len(frame.data) == 8:
            module_ratings = ModuleRatings(
                maximum_output_voltage_volts=self._decode_uint16(frame.data[0:2]),
                minimum_output_voltage_volts=self._decode_uint16(frame.data[2:4]),
                maximum_output_current_amperes=self._decode_uint16(frame.data[4:6]) / 10,
                rated_output_power_watts=self._decode_uint16(frame.data[6:8]) * 10,
            )
        if identifier is not None and identifier.command_number == 0x0C and len(frame.data) == 8:
            module_availability = ModuleAvailability(
                external_voltage_volts=self._decode_uint16(frame.data[0:2]) / 10,
                available_current_amperes=self._decode_uint16(frame.data[2:4]) / 10,
            )

        description = "Decoded Infypower frame" if identifier is not None else "Undecoded frame"
        return DecodeResult(
            frame=frame,
            identifier=identifier,
            description=description,
            module_state=module_state,
            ambient_temperature_celsius=ambient_temperature,
            system_measurements=system_measurements,
            module_measurements=module_measurements,
            ac_input_measurements=ac_input_measurements,
            module_ratings=module_ratings,
            module_availability=module_availability,
            module_count=module_count,
            module_group_number=module_group_number,
            diagnostics=tuple(diagnostics),
        )

    def _parse_identifier(self, raw: int) -> InfypowerIdentifier:
        """Split a 29-bit identifier into its error, device, command and address fields."""
        return InfypowerIdentifier(
            raw=raw,
            error_code=(raw >> self._ERROR_SHIFT) & self._ERROR_MASK,
            device_number=(raw >> self._DEVICE_SHIFT) & self._DEVICE_MASK,
            command_number=(raw >> self._COMMAND_SHIFT) & self._COMMAND_MASK,
            destination_address=(raw >> 8) & self._BYTE_MASK,
            source_address=raw & self._BYTE_MASK,
        )

    @staticmethod
    def _decode_module_state(state_bytes: bytes) -> ModuleState:
        """Map the three big-endian status bytes onto named module state flags."""
        state_2, state_1, state_0 = state_bytes
        return ModuleState(
            communication_interrupt=bool(state_2 & 0x80),
            walk_in_enabled=bool(state_2 & 0x40),
            output_over_voltage=bool(state_2 & 0x20),
            over_temperature=bool(state_2 & 0x10),
            fan_fault=bool(state_2 & 0x08),
            module_protect=bool(state_2 & 0x04),
            module_fault=bool(state_2 & 0x02),
            module_off=bool(state_2 & 0x01),
            input_over_voltage=bool(state_1 & 0x40),
            input_under_voltage=bool(state_1 & 0x20),
            input_unbalance=bool(state_1 & 0x10),
            input_phase_lost=bool(state_1 & 0x08),
            load_unsharing=bool(state_1 & 0x04),
            module_id_repetition=bool(state_1 & 0x02),
            power_limit=bool(state_1 & 0x01),
            pfc_off=bool(state_0 & 0x80),
            air_duct_obstruction=bool(state_0 & 0x40),
            discharge_abnormal=bool(state_0 & 0x20),
            pfc_abnormal=bool(state_0 & 0x10),
            internal_communication_interrupt=bool(state_0 & 0x04),
            hardware_failure=bool(state_0 & 0x02),
            output_short=bool(state_0 & 0x01),
        )

    @staticmethod
    def _decode_tenth_volt(value_bytes: bytes) -> float:
        """Decode an unsigned big-endian value expressed in tenths of a volt."""
        return int.from_bytes(value_bytes, byteorder="big", signed=False) / 10

    @staticmethod
    def _decode_uint16(value_bytes: bytes) -> int:
        """Decode an unsigned big-endian integer of any byte length."""
        return int.from_bytes(value_bytes, byteorder="big", signed=False)
