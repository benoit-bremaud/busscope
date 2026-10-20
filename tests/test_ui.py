from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QSettings
from PySide6.QtWidgets import QApplication

from busscope.analysis import CapturedFrame, IdentifierStatistics, TemporalAnalyzer
from busscope.app import create_application, create_capture_window
from busscope.capture import CanInterface, CaptureConfiguration
from busscope.preferences import DisplayPreferences, IdentifierFormat
from busscope.protocol import (
    CanFrame,
    DecodeResult,
    ModuleRatings,
    ModuleState,
    SystemMeasurements,
)
from busscope.settings_ui import SettingsWidget
from busscope.transmission import ManualTransmission
from busscope.transmission_ui import TransmissionWidget
from busscope.ui import CaptureController, CaptureWindow


class FakeController:
    def __init__(self, results: list[DecodeResult]) -> None:
        self.results = iter(results)
        self.configurations: list[CaptureConfiguration] = []
        self.stop_called = False

    def start(self, configuration: CaptureConfiguration) -> None:
        self.configurations.append(configuration)

    def poll(self, timeout: float | None = None) -> DecodeResult | None:
        del timeout
        return next(self.results, None)

    def stop(self) -> None:
        self.stop_called = True


class MemoryPreferencesRepository:
    def __init__(self, preferences: DisplayPreferences) -> None:
        self.preferences = preferences

    def load(self) -> DisplayPreferences:
        return self.preferences

    def save(self, preferences: DisplayPreferences) -> None:
        self.preferences = preferences


class FakeTransmitter:
    def __init__(self) -> None:
        self.requests: list[ManualTransmission] = []

    def send(self, request: ManualTransmission) -> None:
        self.requests.append(request)


def create_test_window(
    controller: CaptureController,
    preferences: DisplayPreferences | None = None,
    transmitter: FakeTransmitter | None = None,
) -> CaptureWindow:
    selected = preferences or DisplayPreferences.defaults()
    repository = MemoryPreferencesRepository(selected)
    transmission = TransmissionWidget(transmitter or FakeTransmitter())
    return CaptureWindow(
        controller,
        selected,
        SettingsWidget(selected, repository),
        transmission,
    )


@pytest.fixture
def qt_application() -> QApplication:
    application = QApplication.instance()
    if application is None or not isinstance(application, QApplication):
        application = QApplication([])
    return application


def test_window_starts_and_displays_decoded_frame(qt_application: QApplication) -> None:
    del qt_application
    result = DecodeResult(CanFrame(0x123, b"\x01\x02"), None, "Undecoded frame")
    controller = FakeController([result])
    window = create_test_window(controller)

    window.start_capture()
    window._poll_capture()

    assert controller.configurations == [CaptureConfiguration(channel="can0")]
    assert window.frame_list.count() == 1
    assert "0x123 [01 02]" in window.frame_list.item(0).text()
    assert "Undecoded frame" in window.frame_list.item(0).text()


def test_window_displays_decoded_system_measurements(
    qt_application: QApplication,
) -> None:
    del qt_application
    result = DecodeResult(
        CanFrame(0x02813FF0, bytes.fromhex("43 FA 00 00 42 48 00 00")),
        None,
        "Decoded Infypower frame",
        system_measurements=SystemMeasurements(500.0, 50.0),
    )
    window = create_test_window(FakeController([result]))

    window.start_capture()
    window._poll_capture()

    assert "Vout=500.000 V, Iout=50.000 A" in window.frame_list.item(0).text()


def test_window_drains_available_frames_in_one_poll(qt_application: QApplication) -> None:
    del qt_application
    results = [
        DecodeResult(CanFrame(0x100 + index, b"\x00"), None, "Undecoded frame")
        for index in range(3)
    ]
    window = create_test_window(FakeController(results))

    window.start_capture()
    window._poll_capture()

    assert window.frame_list.count() == 3


def test_window_refreshes_identifier_statistics(qt_application: QApplication) -> None:
    del qt_application
    results = [
        DecodeResult(CanFrame(0x123, b"\x00"), None, "First"),
        DecodeResult(CanFrame(0x123, b"\x01"), None, "Second"),
    ]
    window = create_test_window(FakeController(results))

    window.start_capture()
    window._poll_capture()
    window.refresh_statistics()

    assert window.statistics_list.count() == 1
    assert "0x123: count=2" in window.statistics_list.item(0).text()
    assert "frequency=" in window.statistics_list.item(0).text()
    assert "interval_min=" in window.statistics_list.item(0).text()
    assert "interval_max=" in window.statistics_list.item(0).text()
    assert "interval_deviation_max=" in window.statistics_list.item(0).text()


def test_window_loads_and_replays_csv_capture(
    qt_application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    del qt_application
    source = tmp_path / "capture.csv"
    source.write_text(
        "timestamp_seconds,arbitration_id,is_extended_id,is_error_frame,data,description,"
        "decoded_values,diagnostics\n"
        "0.000000,0x0284F001,true,false,00 00 02 00 1B 00 40 00,Stored,Group=99,\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "busscope.ui.QFileDialog.getOpenFileName",
        lambda *args: (str(source), "CSV files (*.csv)"),
    )
    clock = iter([10.0, 10.0])
    monkeypatch.setattr("busscope.ui.time.monotonic", lambda: next(clock))
    window = create_test_window(FakeController([]))

    window.load_replay()
    window.play_replay()
    window._advance_replay()

    assert window.frame_list.count() == 1
    assert "Group=2" in window.frame_list.item(0).text()
    assert "Ambient=27 °C" in window.frame_list.item(0).text()
    window.pause_replay()
    window.reset_replay()
    assert window.frame_list.count() == 0


def test_window_load_replay_resets_display_pause(
    qt_application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    del qt_application
    source = tmp_path / "capture.csv"
    source.write_text(
        "timestamp_seconds,arbitration_id,is_extended_id,is_error_frame,data,description,"
        "decoded_values,diagnostics\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "busscope.ui.QFileDialog.getOpenFileName",
        lambda *args: (str(source), "CSV files (*.csv)"),
    )
    window = create_test_window(FakeController([]))
    window._display_paused = True
    window.pause_button.setText("Resume display")

    window.load_replay()

    assert window._display_paused is False
    assert window.pause_button.text() == "Pause display"


def test_window_reports_replay_completion(
    qt_application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    del qt_application
    source = tmp_path / "capture.csv"
    source.write_text(
        "timestamp_seconds,arbitration_id,is_extended_id,is_error_frame,data,description,"
        "decoded_values,diagnostics\n"
        "0.000000,0x123,true,false,01,Frame,,\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "busscope.ui.QFileDialog.getOpenFileName",
        lambda *args: (str(source), "CSV files (*.csv)"),
    )
    clock = iter([10.0, 10.0])
    monkeypatch.setattr("busscope.ui.time.monotonic", lambda: next(clock))
    window = create_test_window(FakeController([]))
    window.load_replay()
    window.play_replay()

    window._advance_replay()

    assert window.status_label.text() == "Replay finished"


def test_window_rejects_loading_replay_while_capturing(qt_application: QApplication) -> None:
    del qt_application
    window = create_test_window(FakeController([]))
    window.start_capture()

    window.load_replay()

    assert "stop live capture" in window.status_label.text()


def test_window_rejects_replay_while_live_capture_is_active(qt_application: QApplication) -> None:
    del qt_application
    window = create_test_window(FakeController([]))
    window.start_capture()

    window.play_replay()

    assert "stop live capture" in window.status_label.text()


def test_window_rejects_live_capture_until_replay_is_reset(qt_application: QApplication) -> None:
    del qt_application
    window = create_test_window(FakeController([]))
    window._replay.load(
        (CapturedFrame(0.0, DecodeResult(CanFrame(0x123, b"\x00"), None, "Frame")),)
    )
    window._replay.play()

    window.start_capture()

    assert "pause replay" in window.status_label.text()


def test_window_reset_replay_does_not_clear_live_capture(
    qt_application: QApplication,
) -> None:
    del qt_application
    window = create_test_window(FakeController([]))
    window.start_capture()

    window.reset_replay()

    assert "stop live capture" in window.status_label.text()


def test_window_stop_replay_preserves_position(qt_application: QApplication) -> None:
    del qt_application
    window = create_test_window(FakeController([]))
    window._replay.load(
        (CapturedFrame(0.0, DecodeResult(CanFrame(0x123, b"\x00"), None, "Frame")),)
    )
    window.play_replay()
    window.stop_replay()

    assert window.status_label.text() == "Replay stopped"
    assert window._replay.is_playing is False


def test_window_filters_visible_history_without_stopping_capture(
    qt_application: QApplication,
) -> None:
    del qt_application
    results = [
        DecodeResult(CanFrame(0x123, b"\x00"), None, "First"),
        DecodeResult(CanFrame(0x456, b"\x01"), None, "Second"),
    ]
    window = create_test_window(FakeController(results))

    window.start_capture()
    window._poll_capture()
    window.filter_input.setText("0x456")

    assert window._capturing is True
    assert window.frame_list.count() == 1
    assert "0x456" in window.frame_list.item(0).text()


def test_window_pause_retains_records_and_resume_refreshes_display(
    qt_application: QApplication,
) -> None:
    del qt_application
    results = [DecodeResult(CanFrame(0x123, b"\x00"), None, "Frame")]
    window = create_test_window(FakeController(results))

    window.start_capture()
    window.toggle_display_pause()
    window._poll_capture()

    assert window.frame_list.count() == 0
    assert len(window._records) == 1
    assert window._capturing is True

    window.toggle_display_pause()
    assert window.frame_list.count() == 1


def test_window_clear_history_keeps_records_for_export(qt_application: QApplication) -> None:
    del qt_application
    window = create_test_window(
        FakeController([DecodeResult(CanFrame(0x123, b"\x00"), None, "Frame")])
    )

    window.start_capture()
    window._poll_capture()
    window.clear_history()

    assert window.frame_list.count() == 0
    assert len(window._records) == 1


def test_window_clear_history_is_preserved_when_filter_changes(
    qt_application: QApplication,
) -> None:
    del qt_application
    results = [
        DecodeResult(CanFrame(0x123, b"\x00"), None, "Old"),
        DecodeResult(CanFrame(0x456, b"\x01"), None, "New"),
    ]
    window = create_test_window(FakeController(results))

    window.start_capture()
    window._poll_capture()
    window.clear_history()
    window.filter_input.setText("0x123")

    assert window.frame_list.count() == 0
    assert len(window._records) == 2


def test_window_uses_one_timestamp_origin_across_capture_sessions(
    qt_application: QApplication,
) -> None:
    del qt_application
    controller = FakeController([DecodeResult(CanFrame(0x123, b"\x00"), None, "First")])
    window = create_test_window(controller)

    window.start_capture()
    window._poll_capture()
    first_timestamp = window._records[0].timestamp_seconds
    window.stop_capture()
    controller.results = iter([DecodeResult(CanFrame(0x456, b"\x01"), None, "Second")])
    window.start_capture()
    window._poll_capture()

    assert window._records[1].timestamp_seconds >= first_timestamp


def test_window_starts_relative_timestamps_at_first_capture(
    qt_application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del qt_application
    clock = iter([100.0, 101.5])
    monkeypatch.setattr("busscope.ui.time.monotonic", lambda: next(clock))
    window = create_test_window(
        FakeController([DecodeResult(CanFrame(0x123, b"\x00"), None, "Frame")])
    )

    window.start_capture()
    window._poll_capture()

    assert window._records[0].timestamp_seconds == 1.5


def test_window_exports_all_retained_records(
    qt_application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    del qt_application
    destination = tmp_path / "capture.csv"
    monkeypatch.setattr(
        "busscope.ui.QFileDialog.getSaveFileName",
        lambda *args: (str(destination), "CSV files (*.csv)"),
    )
    window = create_test_window(
        FakeController([DecodeResult(CanFrame(0x123, b"\x00"), None, "Frame")])
    )

    window.start_capture()
    window._poll_capture()
    window.export_csv()

    assert "Exported 1 frame" in window.status_label.text()
    assert "description" in destination.read_text(encoding="utf-8")


def test_window_keeps_bounded_display_history(
    qt_application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del qt_application
    monkeypatch.setattr(CaptureWindow, "_MAX_DISPLAYED_FRAMES", 2)
    results = [
        DecodeResult(CanFrame(0x100 + index, b"\x00"), None, "Undecoded frame")
        for index in range(3)
    ]
    window = create_test_window(FakeController(results))

    window.start_capture()
    window._poll_capture()

    assert window.frame_list.count() == 2
    assert "0x101" in window.frame_list.item(0).text()


def test_window_displays_module_diagnostics_and_ratings(
    qt_application: QApplication,
) -> None:
    del qt_application
    result = DecodeResult(
        CanFrame(0x028400F0, bytes.fromhex("00 00 00 00 FE 80 41 01")),
        None,
        "Decoded Infypower frame",
        module_state=ModuleState(module_fault=True, output_short=True),
        ambient_temperature_celsius=-2,
        module_ratings=ModuleRatings(750, 100, 25.6, 15000),
        module_group_number=2,
    )
    window = create_test_window(FakeController([result]))

    window.start_capture()
    window._poll_capture()

    item_text = window.frame_list.item(0).text()
    assert "Ratings=100.000-750.000 V, 25.600 A, 15000.000 W" in item_text
    assert "Group=2; Ambient=-2 °C" in item_text
    assert "Faults=module_fault, output_short" in item_text


def test_window_rejects_empty_channel(qt_application: QApplication) -> None:
    del qt_application
    controller = FakeController([])
    window = create_test_window(controller)
    window.channel_input.clear()

    window.start_capture()

    assert controller.configurations == []
    assert "required" in window.status_label.text()


def test_window_remains_capturing_when_no_frame_is_available(
    qt_application: QApplication,
) -> None:
    del qt_application
    window = create_test_window(FakeController([]))

    window.start_capture()
    window._poll_capture()

    assert window.status_label.text() == "Capturing on can0"
    assert window.start_button.isEnabled() is False
    assert window.stop_button.isEnabled() is True


def test_window_stop_requests_controller_and_closes_capture(qt_application: QApplication) -> None:
    del qt_application
    controller = FakeController([])
    window = create_test_window(controller)

    window.start_capture()
    window.stop_capture()

    assert controller.stop_called is True
    assert window.start_button.isEnabled() is True
    assert window.stop_button.isEnabled() is False


def test_window_stop_reports_cleanup_error_and_resets_controls(
    qt_application: QApplication,
) -> None:
    del qt_application

    class FailingController(FakeController):
        def stop(self) -> None:
            raise RuntimeError("close failed")

    window = create_test_window(FailingController([]))
    window.start_capture()
    window.stop_capture()

    assert "close failed" in window.status_label.text()
    assert window.start_button.isEnabled() is True
    assert window.stop_button.isEnabled() is False


def test_window_preserves_poll_error_when_cleanup_also_fails(
    qt_application: QApplication,
) -> None:
    del qt_application

    class FailingController(FakeController):
        def poll(self, timeout: float | None = None) -> DecodeResult | None:
            del timeout
            raise OSError("receive failed")

        def stop(self) -> None:
            raise RuntimeError("close failed")

    window = create_test_window(FailingController([]))
    window.start_capture()
    window._poll_capture()

    assert "receive failed" in window.status_label.text()
    assert "close failed" not in window.status_label.text()
    assert window.start_button.isEnabled() is True
    assert window.stop_button.isEnabled() is False


def test_window_displays_capture_error(qt_application: QApplication) -> None:
    del qt_application

    class FailingController(FakeController):
        def start(self, configuration: CaptureConfiguration) -> None:
            del configuration
            raise OSError("CAN unavailable")

    window = create_test_window(FailingController([]))

    window.start_capture()
    window._poll_capture()

    assert "CAN unavailable" in window.status_label.text()


def test_application_composition_builds_capture_window(
    qt_application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    settings = QSettings(str(tmp_path / "settings.ini"), QSettings.Format.IniFormat)
    monkeypatch.setattr("busscope.app.QSettings", lambda: settings)
    application = create_application([])
    window = create_capture_window()

    assert application is qt_application
    assert isinstance(window, CaptureWindow)
    assert QCoreApplication.organizationName() == "benoit-bremaud"
    assert QCoreApplication.applicationName() == "busscope"


def test_window_applies_settings_without_changing_capture_state(
    qt_application: QApplication,
) -> None:
    del qt_application
    result = DecodeResult(
        CanFrame(0x123, b"\x01\x02"),
        None,
        "Decoded Infypower frame",
        system_measurements=SystemMeasurements(12.345, 0.126),
        module_count=7,
        diagnostics=("diagnostic",),
    )
    window = create_test_window(FakeController([result]))
    window.start_capture()
    window._poll_capture()
    assert "Modules=7" in window.frame_list.item(0).text()
    retained = list(window._records)
    window.toggle_display_pause()
    hidden = CapturedFrame(1.0, result)
    window._records.append(hidden)

    window.apply_preferences(
        DisplayPreferences(
            identifier_format=IdentifierFormat.DECIMAL,
            numeric_precision=2,
            show_raw_payload=False,
            show_decoded_values=False,
            show_diagnostics=False,
            show_temporal_statistics=False,
        )
    )

    assert window.frame_list.count() == 1
    assert window.frame_list.item(0).text() == "291 | Decoded Infypower frame"
    assert window.statistics_label.isHidden()
    assert window.statistics_list.isHidden()
    assert window.statistics_button.isHidden()
    assert window._capturing is True
    assert window._display_paused is True
    assert window._records == [*retained, hidden]

    window.toggle_display_pause()

    assert window.frame_list.count() == 2


def test_unrelated_preferences_do_not_recalculate_statistics(
    qt_application: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    del qt_application
    window = create_test_window(FakeController([]))
    calls = 0

    def summarize(records: list[CapturedFrame]) -> list[IdentifierStatistics]:
        nonlocal calls
        del records
        calls += 1
        return []

    monkeypatch.setattr(TemporalAnalyzer, "summarize", summarize)

    window.apply_preferences(DisplayPreferences(show_raw_payload=False))

    assert calls == 0


def test_window_reformats_retained_measurements_and_statistics(
    qt_application: QApplication,
) -> None:
    del qt_application
    result = DecodeResult(
        CanFrame(0x123, b"\x01"),
        None,
        "Decoded Infypower frame",
        system_measurements=SystemMeasurements(12.345, 0.126),
    )
    window = create_test_window(FakeController([result]))
    window.start_capture()
    window._poll_capture()

    window.apply_preferences(DisplayPreferences(numeric_precision=2))

    assert "Vout=12.35 V, Iout=0.13 A" in window.frame_list.item(0).text()
    assert window.statistics_list.item(0).text().startswith("0x123: count=1, first=")
    assert window.tabs.count() == 3
    assert window.tabs.tabText(1) == "Transmission"
    assert window.tabs.tabText(2) == "Settings"
    assert not hasattr(window.settings_widget, "transmission")


def test_capture_and_replay_controls_cannot_transmit(qt_application: QApplication) -> None:
    del qt_application
    transmitter = FakeTransmitter()
    window = create_test_window(FakeController([]), transmitter=transmitter)

    window.start_capture()
    window.stop_capture()
    window.play_replay()
    window.pause_replay()
    window.stop_replay()
    window.reset_replay()

    assert transmitter.requests == []


def test_window_selects_backend_and_states_the_expected_channel_form(
    qt_application: QApplication,
) -> None:
    """The two backends take different channel forms, so the UI must say which."""
    del qt_application
    controller = FakeController([])
    window = create_test_window(controller)

    assert window.selected_interface() is CanInterface.SOCKETCAN
    assert window.channel_input.placeholderText() == "can0"
    assert "ip link" in window.channel_input.toolTip()

    slcan_index = window.interface_input.findData(CanInterface.SLCAN)
    window.interface_input.setCurrentIndex(slcan_index)

    assert window.selected_interface() is CanInterface.SLCAN
    assert window.channel_input.placeholderText().startswith("/dev/serial/by-id/")
    assert "listen-only" in window.channel_input.toolTip()

    window.channel_input.setText("/dev/serial/by-id/usb-CANable")
    window.start_capture()

    # An entry carrying something that is not a backend falls back to the guarded
    # default rather than propagating a value the adapter cannot honour.
    window.interface_input.insertItem(0, "bogus", "bogus")
    window.interface_input.setCurrentIndex(0)
    assert window.selected_interface() is CanInterface.SOCKETCAN
    window.interface_input.setCurrentIndex(window.interface_input.findData(CanInterface.SLCAN))

    # The chosen backend must reach the capture configuration, not just the widget.
    assert controller.configurations == [
        CaptureConfiguration(channel="/dev/serial/by-id/usb-CANable", interface=CanInterface.SLCAN)
    ]


def test_window_scopes_the_unverified_silence_acceptance_to_slcan(
    qt_application: QApplication,
) -> None:
    """Only slcan needs it, and a stale tick must not follow the operator around."""
    del qt_application
    controller = FakeController([])
    window = create_test_window(controller)

    # socketcan is verifiable, so accepting an unverifiable silence is meaningless there.
    assert window.unverified_silence_input.isEnabled() is False

    window.interface_input.setCurrentIndex(window.interface_input.findData(CanInterface.SLCAN))
    assert window.unverified_silence_input.isEnabled() is True
    window.unverified_silence_input.setChecked(True)
    window.channel_input.setText("/dev/serial/by-id/usb-CANable")
    window.start_capture()

    assert controller.configurations == [
        CaptureConfiguration(
            channel="/dev/serial/by-id/usb-CANable",
            interface=CanInterface.SLCAN,
            allow_unverified_listen_only=True,
        )
    ]

    # Going back to a verifiable backend clears it, so it cannot silently return.
    window.interface_input.setCurrentIndex(window.interface_input.findData(CanInterface.SOCKETCAN))
    assert window.unverified_silence_input.isChecked() is False
