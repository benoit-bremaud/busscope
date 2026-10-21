from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QSettings, Qt
from PySide6.QtWidgets import QApplication

from busscope import ui as ui_module
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
from busscope.protocol_catalogue import (
    DEFAULT_PROTOCOL_KEY,
    Availability,
    Feature,
    Group,
    Protocol,
    ProtocolCatalogue,
    Transport,
)
from busscope.settings_ui import SettingsWidget
from busscope.toolbar import ToolbarMode
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
    initial_protocol_key: str | None = DEFAULT_PROTOCOL_KEY,
) -> CaptureWindow:
    selected = preferences or DisplayPreferences.defaults()
    repository = MemoryPreferencesRepository(selected)
    transmission = TransmissionWidget(transmitter or FakeTransmitter())
    window = CaptureWindow(
        controller,
        selected,
        SettingsWidget(selected, repository),
        transmission,
        initial_protocol_key,
    )
    if initial_protocol_key is not None:
        window.set_mode(ToolbarMode.LIVE)
    return window


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

    window.load_replay()

    assert window._display_paused is False
    assert window.freeze_action.isChecked() is False


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
    assert window.primary_action.text() == "Stop capture"


def test_window_stop_requests_controller_and_closes_capture(qt_application: QApplication) -> None:
    del qt_application
    controller = FakeController([])
    window = create_test_window(controller)

    window.start_capture()
    window.stop_capture()

    assert controller.stop_called is True
    assert window.primary_action.text() == "Start capture"


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
    assert window.primary_action.text() == "Start capture"


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
    assert window.primary_action.text() == "Start capture"


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
    assert window.tabs.tabText(3) == "AI assistant"
    window.tabs.setCurrentIndex(3)  # opening the tab re-checks readiness
    window.tabs.setCurrentIndex(0)
    assert window.captured_frames() == ()
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
    assert not window.statistics_action.isVisible()
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
    assert window.unverified_silence_input.isHidden() is True

    window.interface_input.setCurrentIndex(window.interface_input.findData(CanInterface.SLCAN))
    assert window.unverified_silence_input.isHidden() is False
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


def _write_replay(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = tmp_path / "capture.csv"
    source.write_text(
        "timestamp_seconds,arbitration_id,is_extended_id,is_error_frame,data,description,"
        "decoded_values,diagnostics\n"
        "0.000000,0x123,true,false,01,Frame,,\n"
        "5.000000,0x124,true,false,02,Frame,,\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        "busscope.ui.QFileDialog.getOpenFileName",
        lambda *args: (str(source), "CSV files (*.csv)"),
    )


def _visible_toolbar_controls(window: CaptureWindow) -> int:
    contextual = (
        window.primary_action,
        window.freeze_action,
        window.clear_action,
        window.export_action,
        window.load_action,
        window.replay_stop_action,
    )
    # The mode switch and the overflow button are always shown; the status pill and the
    # listen-only lock are indicators, not controls.
    return sum(action.isVisible() for action in contextual) + 2


def test_toolbar_starts_in_live_idle(qt_application: QApplication) -> None:
    del qt_application
    window = create_test_window(FakeController([]))

    assert window.live_mode_button.isChecked()
    assert window.status_pill.text() == "Idle"
    assert window.primary_action.toolTip() == "Start capture (Space)"
    assert window.export_action.toolTip() == "Export CSV (Ctrl+E)"
    assert window.freeze_action.isVisible() is False
    assert window.load_action.isVisible() is False
    assert window.listen_only_label.accessibleName() == "Listen-only"


def test_primary_toggle_drives_live_capture(qt_application: QApplication) -> None:
    del qt_application
    controller = FakeController([])
    window = create_test_window(controller)

    window.trigger_primary()

    assert window.status_pill.text() == "Listening"
    assert window.freeze_action.isVisible() is True
    assert window.replay_mode_button.isEnabled() is False

    window.freeze_action.trigger()
    assert window.status_pill.text() == "Frozen"
    assert window.freeze_action.isChecked() is True

    window.trigger_primary()
    assert controller.stop_called is True
    assert window.status_pill.text() == "Idle"
    assert window.freeze_action.isChecked() is False


def test_mode_switch_is_refused_while_capturing(qt_application: QApplication) -> None:
    del qt_application
    window = create_test_window(FakeController([]))
    window.start_capture()

    window.set_mode(ToolbarMode.REPLAY)

    assert window.live_mode_button.isChecked()
    assert window.live_settings.isHidden() is False


def test_replay_mode_lifecycle(
    qt_application: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    del qt_application
    _write_replay(tmp_path, monkeypatch)
    window = create_test_window(FakeController([]))

    window.switch_mode()
    assert window.replay_mode_button.isChecked()
    assert window.live_settings.isHidden()
    assert window.status_pill.text() == "No capture"
    assert window.primary_action.isVisible() is False
    assert window.reset_replay_action.isVisible() is True

    window.load_action.trigger()
    assert window.status_pill.text() == "Loaded"
    assert window.primary_action.text() == "Play replay"

    window.trigger_primary()
    assert window.status_pill.text() == "Playing"
    assert window.replay_stop_action.isVisible() is True
    assert window.load_action.isVisible() is False
    assert window.live_mode_button.isEnabled() is False

    window.trigger_primary()
    assert window.status_pill.text() == "Paused"
    assert window.replay_stop_action.isVisible() is True
    assert window.live_mode_button.isEnabled() is True

    window.replay_stop_action.trigger()
    assert window.status_pill.text() == "Loaded"

    window.trigger_primary()
    window.reset_replay_action.trigger()
    assert window.status_pill.text() == "Loaded"

    window.switch_mode()
    assert window.live_mode_button.isChecked()
    assert window.reset_replay_action.isVisible() is False


def test_toolbar_never_shows_more_than_six_controls(
    qt_application: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    del qt_application
    _write_replay(tmp_path, monkeypatch)
    window = create_test_window(FakeController([]))
    counts = [_visible_toolbar_controls(window)]
    window.start_capture()
    counts.append(_visible_toolbar_controls(window))
    window.stop_capture()
    window.set_mode(ToolbarMode.REPLAY)
    counts.append(_visible_toolbar_controls(window))
    window.load_replay()
    counts.append(_visible_toolbar_controls(window))
    window.play_replay()
    counts.append(_visible_toolbar_controls(window))

    assert counts == [5, 6, 3, 5, 5]


def test_overflow_menu_holds_rare_actions(qt_application: QApplication) -> None:
    del qt_application
    window = create_test_window(FakeController([]))
    menu = window.overflow_button.menu()

    assert menu is not None
    assert [action.text() for action in menu.actions()] == [
        "Refresh statistics",
        "Reset replay",
    ]


def test_replay_finish_returns_to_loaded(
    qt_application: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    del qt_application
    _write_replay(tmp_path, monkeypatch)
    clock = iter([10.0, 20.0])
    monkeypatch.setattr("busscope.ui.time.monotonic", lambda: next(clock))
    window = create_test_window(FakeController([]))
    window.set_mode(ToolbarMode.REPLAY)
    window.load_replay()
    window.play_replay()

    window._advance_replay()

    assert window.status_pill.text() == "Loaded"
    assert window.primary_action.text() == "Play replay"


def test_space_is_handed_back_to_a_focused_button(
    qt_application: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    del qt_application
    window = create_test_window(FakeController([]))
    button = window.replay_mode_button
    monkeypatch.setattr("busscope.ui.QApplication.focusWidget", lambda: button)

    window.primary_shortcut.trigger()

    assert button.isChecked() is True
    assert window.status_pill.text() == "No capture"


def test_space_opens_a_focused_combo_box(
    qt_application: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    del qt_application
    window = create_test_window(FakeController([]))
    combo = window.interface_input
    opened: list[bool] = []
    monkeypatch.setattr(combo, "showPopup", lambda: opened.append(True))
    monkeypatch.setattr("busscope.ui.QApplication.focusWidget", lambda: combo)

    window.primary_shortcut.trigger()

    assert opened == [True]
    assert window.status_pill.text() == "Idle"


def test_space_without_focused_control_starts_capture(
    qt_application: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    del qt_application
    window = create_test_window(FakeController([]))
    monkeypatch.setattr("busscope.ui.QApplication.focusWidget", lambda: None)

    window.primary_shortcut.trigger()

    assert window.status_pill.text() == "Listening"


def test_shortcuts_are_scoped_to_the_capture_tab(qt_application: QApplication) -> None:
    del qt_application
    window = create_test_window(FakeController([]))

    for action in (window.primary_shortcut, window.switch_mode_action):
        assert action.shortcutContext() is Qt.ShortcutContext.WidgetWithChildrenShortcut
    assert window.switch_mode_action.shortcut().toString() == "Ctrl+M"


def test_poll_error_clears_display_freeze(qt_application: QApplication) -> None:
    del qt_application

    class FailingController(FakeController):
        def poll(self, timeout: float | None = None) -> DecodeResult | None:
            raise OSError("bus down")

    window = create_test_window(FailingController([]))
    window.start_capture()
    window.toggle_display_pause()

    window._poll_capture()

    assert window.freeze_action.isChecked() is False
    assert window.status_pill.text() == "Idle"


def test_freeze_action_announces_resume_while_frozen(qt_application: QApplication) -> None:
    del qt_application
    window = create_test_window(FakeController([]))
    window.start_capture()

    window.freeze_action.trigger()
    assert window.freeze_action.text() == "Resume display"
    assert window.freeze_action.toolTip() == "Resume display"

    window.freeze_action.trigger()
    assert window.freeze_action.text() == "Freeze display"


def test_play_after_replay_finished_restarts_from_the_beginning(
    qt_application: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    del qt_application
    _write_replay(tmp_path, monkeypatch)
    clock = iter([10.0, 20.0, 30.0])
    monkeypatch.setattr("busscope.ui.time.monotonic", lambda: next(clock))
    window = create_test_window(FakeController([]))
    window.set_mode(ToolbarMode.REPLAY)
    window.load_replay()
    window.play_replay()
    window._advance_replay()

    window.trigger_primary()

    assert window.status_pill.text() == "Playing"
    assert window.status_label.text() == "Replaying CSV capture"
    assert window._records == []


def test_capture_tab_offers_protocol_catalogue_with_can_fields(
    qt_application: QApplication,
) -> None:
    del qt_application
    window = create_test_window(FakeController([]))

    selected = window.protocol_selector.selected
    assert selected is not None
    assert selected.name == "CAN 2.0B"
    assert window.protocol_selector.isEnabled()
    assert window.can_filter.isHidden() is False
    window.start_capture()
    assert window.protocol_selector.isEnabled() is False
    window.stop_capture()
    window.set_mode(ToolbarMode.REPLAY)
    assert window.protocol_selector.isHidden() is False
    assert window.live_settings.isHidden()
    assert window.can_filter.isHidden() is False


def _visible_capture_controls(window: CaptureWindow) -> dict[str, bool]:
    return {
        "modes": not window.live_mode_button.isHidden(),
        "live_settings": not window.live_settings.isHidden(),
        "filter": not window.can_filter.isHidden(),
        "statistics": not window.statistics_list.isHidden(),
        "toolbar": not window.toolbar.isHidden(),
    }


def test_capture_tab_starts_with_only_the_protocol_picker(qt_application: QApplication) -> None:
    del qt_application
    controller = FakeController([])
    window = create_test_window(controller, initial_protocol_key=None)

    assert window.protocol_selector.selected is None
    assert not any(_visible_capture_controls(window).values())
    assert window.status_pill.text() == "Choose protocol"
    assert window.listen_only_label.isHidden() is False
    assert window.listen_only_icon.isHidden() is False
    # Space and Ctrl+M have nothing to act on yet.
    window.trigger_primary()
    window.switch_mode()
    assert controller.configurations == []


def test_controls_appear_as_protocol_then_source_are_chosen(
    qt_application: QApplication,
) -> None:
    del qt_application
    window = create_test_window(FakeController([]), initial_protocol_key=None)

    window.protocol_selector.choose(window.protocol_selector.item("infypower"))
    assert _visible_capture_controls(window) == {
        "modes": True,
        "live_settings": False,
        "filter": False,
        "statistics": False,
        "toolbar": False,
    }
    assert window.live_mode_button.isChecked() is False
    assert window.status_pill.text() == "Choose source"

    window.set_mode(ToolbarMode.LIVE)
    assert all(_visible_capture_controls(window).values())
    assert window.status_pill.text() == "Idle"

    # Changing to another protocol offering the same source keeps it.
    window.protocol_selector.choose(window.protocol_selector.item(DEFAULT_PROTOCOL_KEY))
    assert window.live_mode_button.isChecked()


def test_single_source_protocol_skips_the_source_choice(
    qt_application: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    del qt_application
    replay_only = Protocol("log", "Log", "", Transport.LOGIC, Availability.AVAILABLE)
    live_only = Protocol("bus", "Bus", "", Transport.CAN, Availability.AVAILABLE)
    catalogue = ProtocolCatalogue(
        Group(
            "root",
            "Root",
            (
                Group("files", "Files", (replay_only,), adds=frozenset({Feature.REPLAY_SOURCE})),
                Group("wires", "Wires", (live_only,), adds=frozenset({Feature.LIVE_SOURCE})),
            ),
        )
    )
    monkeypatch.setattr(ui_module, "DEFAULT_CATALOGUE", catalogue)
    window = create_test_window(FakeController([]), initial_protocol_key=None)

    window.protocol_selector.choose(window.protocol_selector.item("log"))
    assert window.replay_mode_button.isChecked()
    assert window.replay_mode_button.isHidden()
    assert window.toolbar.isHidden() is False
    assert window.statistics_list.isHidden()

    # A source the new protocol lacks is dropped, then the only remaining one is taken.
    window.protocol_selector.choose(window.protocol_selector.item("bus"))
    assert window.live_mode_button.isChecked()
    window.set_mode(ToolbarMode.REPLAY)
    assert window.live_mode_button.isChecked()
    assert window.live_settings.isHidden()
