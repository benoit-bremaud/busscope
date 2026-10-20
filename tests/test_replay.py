from pathlib import Path

import pytest

from busscope.analysis import CapturedFrame, CsvExporter
from busscope.protocol import CanFrame, ProtocolDecoder
from busscope.replay import CsvCaptureLoader, ReplayController

CSV = (
    "timestamp_seconds,arbitration_id,is_extended_id,is_error_frame,data,description,"
    "decoded_values,diagnostics\n"
    "1.000000,0x123,true,false,01 02,First,,\n"
    "2.500000,0x456,true,false,03 04,Second,,warning\n"
)

SUPPORTED_FRAMES = (
    CanFrame(0x02813FF0, bytes.fromhex("43 FA 00 00 42 48 00 00")),
    CanFrame(0x0282F03F, bytes.fromhex("00 00 07 00 00 00 00 00")),
    CanFrame(0x028300F0, bytes.fromhex("43 FA 00 00 40 60 00 00")),
    CanFrame(0x0284F001, bytes.fromhex("00 00 02 00 1B 00 40 00")),
    CanFrame(0x028600F0, bytes.fromhex("0F B4 0F A5 0F A7 00 00")),
    CanFrame(0x028A00F0, bytes.fromhex("02 EE 00 64 01 00 05 DC")),
    CanFrame(0x028C00F0, bytes.fromhex("13 58 01 66 00 00 00 00")),
)

SAFE_NON_SEMANTIC_FRAMES = (
    CanFrame(0x123, bytes(8), is_extended_id=False),
    CanFrame(0, b"", is_error_frame=True),
    CanFrame(0x029A3FF0, bytes(7)),
    CanFrame(0x029A3FF0, bytes(8)),
)


def test_csv_loader_loads_exported_capture() -> None:
    records = CsvCaptureLoader.from_csv(CSV)

    assert len(records) == 2
    assert records[0].timestamp_seconds == 1.0
    assert records[1].result.frame.arbitration_id == 0x456
    assert records[1].result.diagnostics == ("Expected an 8-byte payload", "warning")


@pytest.mark.parametrize("frame", SUPPORTED_FRAMES)
def test_csv_loader_restores_all_supported_protocol_values(frame: CanFrame) -> None:
    decoded = ProtocolDecoder().decode(frame)
    content = CsvExporter.to_csv([CapturedFrame(0.0, decoded)])

    loaded = CsvCaptureLoader.from_csv(content)

    assert loaded[0].result == decoded


@pytest.mark.parametrize("frame", SAFE_NON_SEMANTIC_FRAMES)
def test_csv_loader_preserves_safe_decoder_behavior(frame: CanFrame) -> None:
    decoded = ProtocolDecoder().decode(frame)
    content = CsvExporter.to_csv([CapturedFrame(0.0, decoded)])

    loaded = CsvCaptureLoader.from_csv(content)

    assert loaded[0].result == decoded


def test_csv_loader_ignores_decoded_values_and_preserves_description() -> None:
    content = (
        CSV.split("\n", maxsplit=1)[0]
        + "\n0.000000,0x0282F03F,true,false,00 00 07 00 00 00 00 00,Stored,"
        "Modules=99,\n"
    )

    result = CsvCaptureLoader.from_csv(content)[0].result

    assert result.module_count == 7
    assert result.description == "Stored"


def test_csv_loader_combines_current_and_unique_stored_diagnostics() -> None:
    content = (
        CSV.split("\n", maxsplit=1)[0]
        + "\n0.000000,0x123,false,false,01 02,Stored,,"
        "Expected an 8-byte payload; historical warning\n"
    )

    result = CsvCaptureLoader.from_csv(content)[0].result

    assert result.diagnostics == (
        "Expected a 29-bit extended identifier",
        "Expected an 8-byte payload",
        "historical warning",
    )


def test_csv_loader_accepts_empty_capture() -> None:
    content = CSV.split("\n", maxsplit=1)[0] + "\n"

    assert CsvCaptureLoader.from_csv(content) == ()


@pytest.mark.parametrize(
    "content",
    [
        "wrong,header\n",
        CSV.replace("0x123", "0x20000000"),
        CSV.replace("1.000000", "0.000000\n0.500000"),
        CSV.replace("01 02", "01 02 03 04 05 06 07 08 09"),
        CSV.replace("true,false", "maybe,false"),
        CSV.replace("0x123,true", "0x800,false"),
        CSV.replace("1.000000", "NaN"),
        CSV.replace("1.000000", "inf"),
    ],
)
def test_csv_loader_rejects_invalid_content(content: str) -> None:
    with pytest.raises(ValueError):
        CsvCaptureLoader.from_csv(content)


def test_csv_loader_reports_missing_file(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="Cannot read capture file"):
        CsvCaptureLoader.load(tmp_path / "does-not-exist.csv")


def test_replay_controller_emits_records_according_to_relative_time() -> None:
    controller = ReplayController()
    controller.load(CsvCaptureLoader.from_csv(CSV))
    controller.play()

    assert controller.advance(0.0)[0].result.frame.arbitration_id == 0x123
    assert controller.is_playing is True
    assert controller.advance(1.5)[0].result.frame.arbitration_id == 0x456
    assert controller.advance(1.0) == ()
    assert controller.is_playing is False


def test_replay_controller_pause_and_reset_are_deterministic() -> None:
    controller = ReplayController()
    controller.load(CsvCaptureLoader.from_csv(CSV))
    controller.play()
    controller.pause()

    assert controller.advance(10.0) == ()
    controller.reset()
    controller.play()
    assert len(controller.advance(0.0)) == 1


def test_replay_controller_rejects_negative_time() -> None:
    with pytest.raises(ValueError, match="must not be negative"):
        ReplayController().advance(-1.0)


def test_replay_controller_reports_loaded_records() -> None:
    controller = ReplayController()

    assert controller.has_records is False
    controller.load(CsvCaptureLoader.from_csv(CSV))
    assert controller.has_records is True


def test_replay_controller_stop_preserves_position() -> None:
    controller = ReplayController()
    controller.load(CsvCaptureLoader.from_csv(CSV))
    controller.play()
    controller.advance(0.0)
    controller.stop()

    assert controller.is_playing is False
    controller.play()
    assert controller.advance(1.5)[0].result.frame.arbitration_id == 0x456
