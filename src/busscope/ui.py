"""PySide6 main window for CAN capture, replay, settings, and transmission."""

import logging
import time
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QPushButton,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from busscope.analysis import (
    CapturedFrame,
    CsvExporter,
    FrameFilter,
    IdentifierStatistics,
    TemporalAnalyzer,
)
from busscope.capture import CanInterface, CaptureConfiguration
from busscope.preferences import DisplayPreferences, IdentifierFormat
from busscope.protocol import DecodeResult
from busscope.replay import CsvCaptureLoader, ReplayController
from busscope.settings_ui import SettingsWidget
from busscope.transmission_ui import TransmissionWidget

logger = logging.getLogger(__name__)


class CaptureController(Protocol):
    """Application contract consumed by the capture window."""

    def start(self, configuration: CaptureConfiguration) -> None:
        """Start a capture session."""

    def poll(self, timeout: float | None = None) -> DecodeResult | None:
        """Poll for one decoded result without ending the session on timeout."""

    def stop(self) -> None:
        """Request capture termination."""


class CaptureWindow(QMainWindow):
    """Display decoded CAN frames while keeping capture polling non-blocking."""

    _MAX_FRAMES_PER_TICK = 100
    _MAX_DISPLAYED_FRAMES = 10_000

    def __init__(
        self,
        controller: CaptureController,
        preferences: DisplayPreferences,
        settings_widget: SettingsWidget,
        transmission_widget: TransmissionWidget,
    ) -> None:
        """Wire the controller, preferences and child widgets into the main window."""
        super().__init__()
        self._controller = controller
        self._preferences = preferences
        self.settings_widget = settings_widget
        self.transmission_widget = transmission_widget
        self._capturing = False
        self._display_paused = False
        self._display_pause_index: int | None = None
        self._capture_origin: float | None = None
        self._channel = ""
        self._records: list[CapturedFrame] = []
        self._display_start_index = 0
        self._replay = ReplayController()
        self._replay_last_tick = 0.0
        self._frame_filter = FrameFilter()
        self._timer = QTimer(self)
        self._timer.setInterval(50)
        self._timer.timeout.connect(self._poll_capture)

        self._hinted_interface: CanInterface | None = None
        self.interface_input = QComboBox()
        self.interface_input.setAccessibleName("CAN backend")
        for backend in CanInterface:
            self.interface_input.addItem(backend.value, backend)
        self.unverified_silence_input = QCheckBox("Accept unverified silence")
        self.unverified_silence_input.setAccessibleName("Accept unverified listen-only")
        self.unverified_silence_input.setToolTip(
            "The slcan firmware acknowledges no command, so the adapter cannot confirm it "
            "is electrically silent. Isolated bench only: never on a live charger bus."
        )
        self.channel_input = QLineEdit("can0")
        self.channel_input.setAccessibleName("CAN channel")
        # The two backends take different channel forms; say so instead of expecting
        # the operator to infer it from a failure.
        self.interface_input.currentIndexChanged.connect(self._update_channel_hint)
        self._update_channel_hint()
        self.filter_input = QLineEdit()
        self.filter_input.setPlaceholderText("IDs, e.g. 0x123, 0x456")
        self.filter_input.setAccessibleName("CAN identifier filter")
        self.start_button = QPushButton("Start")
        self.start_button.setAccessibleName("Start capture")
        self.stop_button = QPushButton("Stop")
        self.stop_button.setAccessibleName("Stop capture")
        self.stop_button.setEnabled(False)
        self.pause_button = QPushButton("Pause display")
        self.pause_button.setAccessibleName("Pause display")
        self.pause_button.setEnabled(False)
        self.clear_button = QPushButton("Clear")
        self.clear_button.setAccessibleName("Clear displayed frames")
        self.export_button = QPushButton("Export CSV")
        self.export_button.setAccessibleName("Export captured frames")
        self.statistics_button = QPushButton("Refresh statistics")
        self.statistics_button.setAccessibleName("Refresh CAN statistics")
        self.load_replay_button = QPushButton("Load CSV")
        self.load_replay_button.setAccessibleName("Load CSV replay")
        self.play_replay_button = QPushButton("Play")
        self.play_replay_button.setAccessibleName("Play CSV replay")
        self.pause_replay_button = QPushButton("Pause")
        self.pause_replay_button.setAccessibleName("Pause CSV replay")
        self.stop_replay_button = QPushButton("Stop")
        self.stop_replay_button.setAccessibleName("Stop CSV replay")
        self.reset_replay_button = QPushButton("Reset")
        self.reset_replay_button.setAccessibleName("Reset CSV replay")
        self.status_label = QLabel("Ready")
        self.frame_list = QListWidget()
        self.frame_list.setAccessibleName("Captured CAN frames")
        self.statistics_list = QListWidget()
        self.statistics_list.setAccessibleName("CAN identifier statistics")
        self._replay_timer = QTimer(self)
        self._replay_timer.setInterval(50)
        self._replay_timer.timeout.connect(self._advance_replay)

        controls = QHBoxLayout()
        controls.addWidget(QLabel("Backend:"))
        controls.addWidget(self.interface_input)
        controls.addWidget(QLabel("Channel:"))
        controls.addWidget(self.channel_input)
        controls.addWidget(self.unverified_silence_input)
        controls.addWidget(QLabel("Filter:"))
        controls.addWidget(self.filter_input)
        controls.addWidget(self.start_button)
        controls.addWidget(self.stop_button)
        controls.addWidget(self.pause_button)
        controls.addWidget(self.clear_button)
        controls.addWidget(self.export_button)
        controls.addWidget(self.statistics_button)
        controls.addWidget(self.load_replay_button)
        controls.addWidget(self.play_replay_button)
        controls.addWidget(self.pause_replay_button)
        controls.addWidget(self.stop_replay_button)
        controls.addWidget(self.reset_replay_button)

        capture_widget = QWidget()
        layout = QVBoxLayout(capture_widget)
        layout.addLayout(controls)
        layout.addWidget(self.status_label)
        self.statistics_label = QLabel("Statistics:")
        layout.addWidget(self.statistics_label)
        layout.addWidget(self.statistics_list)
        layout.addWidget(self.frame_list)
        self.tabs = QTabWidget()
        self.tabs.addTab(capture_widget, "Capture")
        self.tabs.addTab(self.transmission_widget, "Transmission")
        self.tabs.addTab(self.settings_widget, "Settings")
        self.setCentralWidget(self.tabs)
        self.setWindowTitle("BusScope")
        self.resize(720, 480)

        self.start_button.clicked.connect(self.start_capture)
        self.stop_button.clicked.connect(self.stop_capture)
        self.pause_button.clicked.connect(self.toggle_display_pause)
        self.clear_button.clicked.connect(self.clear_history)
        self.export_button.clicked.connect(self.export_csv)
        self.statistics_button.clicked.connect(self.refresh_statistics)
        self.load_replay_button.clicked.connect(self.load_replay)
        self.play_replay_button.clicked.connect(self.play_replay)
        self.pause_replay_button.clicked.connect(self.pause_replay)
        self.stop_replay_button.clicked.connect(self.stop_replay)
        self.reset_replay_button.clicked.connect(self.reset_replay)
        self.filter_input.textChanged.connect(self.apply_filter)
        self.settings_widget.preferences_changed.connect(self.apply_preferences)
        self.apply_preferences(preferences)

    def apply_preferences(self, preferences: DisplayPreferences) -> None:
        """Apply display preferences immediately without changing retained data or state."""
        statistics_changed = (
            self._preferences.identifier_format is not preferences.identifier_format
            or self._preferences.numeric_precision != preferences.numeric_precision
            or (
                not self._preferences.show_temporal_statistics
                and preferences.show_temporal_statistics
            )
        )
        self._preferences = preferences
        visible = preferences.show_temporal_statistics
        self.statistics_label.setVisible(visible)
        self.statistics_list.setVisible(visible)
        self.statistics_button.setVisible(visible)
        self._render_display()
        if visible and statistics_changed:
            self.refresh_statistics()

    def selected_interface(self) -> CanInterface:
        """Backend chosen by the operator, defaulting to socketcan."""
        # Qt stores the StrEnum as a plain str, so convert back rather than isinstance.
        try:
            return CanInterface(self.interface_input.currentData())
        except ValueError:
            return CanInterface.SOCKETCAN

    def _update_channel_hint(self) -> None:
        """Channel means an interface name on socketcan, a serial device on slcan."""
        # Clear rather than carry a channel across backends: "can0" submitted as a
        # serial device path is the kind of silently wrong input this change exists to
        # stop. The placeholder states what the selected backend expects.
        if self._hinted_interface is not None:
            self.channel_input.clear()
        self._hinted_interface = self.selected_interface()
        slcan = self.selected_interface() is CanInterface.SLCAN
        self.unverified_silence_input.setEnabled(slcan)
        if not slcan:
            # socketcan is verifiable, so the acceptance has no meaning there and must
            # not survive as a stale tick that would later apply to slcan unnoticed.
            self.unverified_silence_input.setChecked(False)
        if slcan:
            self.channel_input.setPlaceholderText("/dev/serial/by-id/usb-...")
            self.channel_input.setToolTip(
                "Serial device of the adapter. This backend applies the bitrate and "
                "listen-only mode itself."
            )
        else:
            self.channel_input.setPlaceholderText("can0")
            self.channel_input.setToolTip(
                "SocketCAN interface name. Listen-only cannot be set here, only verified: "
                "configure it with ip link, or use the slcan backend."
            )

    def start_capture(self) -> None:
        """Start polling the configured channel."""
        channel = self.channel_input.text().strip()
        if not channel:
            self.status_label.setText("Error: CAN channel is required")
            return
        if self._replay.is_playing:
            self.status_label.setText("Error: pause replay before starting live capture")
            return

        try:
            self._controller.start(
                CaptureConfiguration(
                    channel=channel,
                    interface=self.selected_interface(),
                    allow_unverified_listen_only=(self.unverified_silence_input.isChecked()),
                )
            )
        except Exception as error:
            self.status_label.setText(f"Error: {error}")
            return
        self._capturing = True
        self._display_paused = False
        self._display_pause_index = None
        if self._capture_origin is None:
            self._capture_origin = time.monotonic()
        self._channel = channel
        self.start_button.setEnabled(False)
        self.stop_button.setEnabled(True)
        self.pause_button.setEnabled(True)
        self.pause_button.setText("Pause display")
        self.status_label.setText(f"Capturing on {channel}")
        self._timer.start()

    def stop_capture(self) -> None:
        """Stop polling and reset the window even if cleanup fails."""
        self._timer.stop()
        self._capturing = False
        self.start_button.setEnabled(True)
        self.stop_button.setEnabled(False)
        self.pause_button.setEnabled(False)
        try:
            self._controller.stop()
        except Exception as error:
            self.status_label.setText(f"Error: {error}")
            return
        self.status_label.setText("Stopped")

    def toggle_display_pause(self) -> None:
        """Pause or resume display updates without stopping capture."""
        self._display_paused = not self._display_paused
        self.pause_button.setText("Resume display" if self._display_paused else "Pause display")
        if self._display_paused:
            self._display_pause_index = len(self._records)
            return
        self._display_pause_index = None
        self._refresh_display()

    def clear_history(self) -> None:
        """Clear visible history while retaining captured records for export."""
        self._display_start_index = len(self._records)
        self.frame_list.clear()

    def apply_filter(self, text: str) -> None:
        """Apply an identifier filter to the visible history."""
        try:
            self._frame_filter = FrameFilter.from_text(text)
        except ValueError as error:
            self.status_label.setText(f"Error: {error}")
            return
        if self._capturing:
            self.status_label.setText(f"Capturing on {self._channel}")
        else:
            self.status_label.setText("Ready")
        self._refresh_display()

    def export_csv(self) -> None:
        """Export all retained records to a CSV file selected by the operator."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Export CAN frames", "capture.csv", "CSV files (*.csv)"
        )
        if not path:
            return
        try:
            Path(path).write_text(CsvExporter.to_csv(self._records), encoding="utf-8", newline="")
        except OSError as error:
            self.status_label.setText(f"Error: {error}")
            return
        self.status_label.setText(f"Exported {len(self._records)} frame(s)")

    def refresh_statistics(self) -> None:
        """Refresh identifier statistics from all retained records."""
        statistics = TemporalAnalyzer.summarize(self._records)
        self.statistics_list.clear()
        for item in statistics:
            self.statistics_list.addItem(self._format_statistics(item))

    def load_replay(self) -> None:
        """Load a CSV capture without opening a CAN port."""
        if self._capturing:
            self.status_label.setText("Error: stop live capture before loading a replay")
            return
        path, _ = QFileDialog.getOpenFileName(self, "Load CAN capture", "", "CSV files (*.csv)")
        if not path:
            return
        try:
            records = CsvCaptureLoader.load(Path(path))
        except ValueError as error:
            self.status_label.setText(f"Error: {error}")
            return
        self._replay.load(records)
        self._records.clear()
        self._display_start_index = 0
        self._display_paused = False
        self._display_pause_index = None
        self.pause_button.setText("Pause display")
        self.frame_list.clear()
        self.statistics_list.clear()
        self.status_label.setText(f"Loaded {len(records)} replay frame(s)")

    def play_replay(self) -> None:
        """Start or resume local CSV playback."""
        if self._capturing:
            self.status_label.setText("Error: stop live capture before replay")
            return
        if not self._replay.has_records:
            self.status_label.setText("Error: load a CSV capture before replay")
            return
        self._replay.play()
        if not self._replay.is_playing:
            self.status_label.setText("Error: replay has finished, reset it before replay")
            return
        self._replay_last_tick = time.monotonic()
        self._replay_timer.start()
        self.status_label.setText("Replaying CSV capture")

    def pause_replay(self) -> None:
        """Pause local CSV playback."""
        self._replay.pause()
        self._replay_timer.stop()
        self.status_label.setText("Replay paused")

    def stop_replay(self) -> None:
        """Stop local CSV playback while preserving its current position."""
        self._replay.stop()
        self._replay_timer.stop()
        self.status_label.setText("Replay stopped")

    def reset_replay(self) -> None:
        """Reset local playback and clear replayed records from the views."""
        if self._capturing:
            self.status_label.setText("Error: stop live capture before resetting replay")
            return
        self._replay.reset()
        self._replay_timer.stop()
        self._records.clear()
        self._display_start_index = 0
        self.frame_list.clear()
        self.statistics_list.clear()
        self.status_label.setText("Replay reset")

    def _advance_replay(self) -> None:
        """Release replay records that became due since the last tick, then stop at the end."""
        was_playing = self._replay.is_playing
        now = time.monotonic()
        due = self._replay.advance(now - self._replay_last_tick)
        self._replay_last_tick = now
        for captured in due:
            self._records.append(captured)
            if not self._display_paused and self._frame_filter.matches(captured):
                self._add_to_display(captured)
        if was_playing and not self._replay.is_playing:
            self._replay_timer.stop()
            self.status_label.setText("Replay finished")

    def _format_statistics(self, item: IdentifierStatistics) -> str:
        """Format one identifier statistics row for the operator."""
        number = self._format_number
        period = (
            "n/a"
            if item.observed_period_seconds is None
            else f"{number(item.observed_period_seconds)} s"
        )
        frequency = "n/a" if item.frequency_hz is None else f"{number(item.frequency_hz)} Hz"
        minimum_interval = (
            "n/a"
            if item.minimum_interval_seconds is None
            else f"{number(item.minimum_interval_seconds)} s"
        )
        maximum_interval = (
            "n/a"
            if item.maximum_interval_seconds is None
            else f"{number(item.maximum_interval_seconds)} s"
        )
        maximum_interval_deviation = (
            "n/a"
            if item.maximum_interval_deviation_seconds is None
            else f"{number(item.maximum_interval_deviation_seconds)} s"
        )
        return (
            f"{self._format_identifier(item.arbitration_id)}: count={item.count}, "
            f"first={number(item.first_timestamp_seconds)} s, "
            f"last={number(item.last_timestamp_seconds)} s, "
            f"period={period}, frequency={frequency}, "
            f"interval_min={minimum_interval}, interval_max={maximum_interval}, "
            f"interval_deviation_max={maximum_interval_deviation}"
        )

    def _stop_after_poll_error(self) -> None:
        """Stop capture while preserving the original polling error."""
        try:
            self._controller.stop()
        except Exception:
            logger.warning("Failed to clean up after a CAN polling error", exc_info=True)

    def _poll_capture(self) -> None:
        """Drain at most one bounded batch of frames per tick so the UI stays responsive."""
        if not self._capturing:
            return
        for _ in range(self._MAX_FRAMES_PER_TICK):
            try:
                result = self._controller.poll(timeout=0)
            except Exception as error:
                self._timer.stop()
                self._stop_after_poll_error()
                self._capturing = False
                self.start_button.setEnabled(True)
                self.stop_button.setEnabled(False)
                self.status_label.setText(f"Error: {error}")
                return

            if result is None:
                return
            capture_origin = self._capture_origin
            if capture_origin is None:
                logger.error("Cannot timestamp a frame without a capture origin")
                return
            captured = CapturedFrame(time.monotonic() - capture_origin, result)
            self._records.append(captured)
            if not self._display_paused and self._frame_filter.matches(captured):
                self._add_to_display(captured)

    def _add_to_display(self, captured: CapturedFrame) -> None:
        """Append one row and drop the oldest beyond the display cap."""
        self.frame_list.addItem(self._format_result(captured.result))
        while self.frame_list.count() > self._MAX_DISPLAYED_FRAMES:
            self.frame_list.takeItem(0)

    def _refresh_display(self) -> None:
        """Re-render the list unless the display is paused."""
        if self._display_paused:
            return
        self._render_display()

    def _render_display(self) -> None:
        """Rebuild the visible list from the stored records honouring pause and filter."""
        self.frame_list.clear()
        display_end = self._display_pause_index if self._display_paused else None
        matching = [
            captured
            for captured in self._records[self._display_start_index : display_end]
            if self._frame_filter.matches(captured)
        ]
        for captured in matching[-self._MAX_DISPLAYED_FRAMES :]:
            self._add_to_display(captured)

    def _format_number(self, value: float) -> str:
        """Format a number with the operator's chosen precision."""
        return f"{value:.{self._preferences.numeric_precision}f}"

    def _format_identifier(self, arbitration_id: int) -> str:
        """Format an identifier in the operator's chosen base."""
        if self._preferences.identifier_format is IdentifierFormat.DECIMAL:
            return str(arbitration_id)
        return f"0x{arbitration_id:X}"

    def _format_result(self, result: DecodeResult) -> str:
        """Format one decoded result for the operator's event list."""
        frame = result.frame
        number = self._format_number
        decoded_values: list[str] = []
        if self._preferences.show_decoded_values and result.system_measurements is not None:
            system_measurements = result.system_measurements
            decoded_values.append(
                f"Vout={number(system_measurements.output_voltage_volts)} V, "
                f"Iout={number(system_measurements.total_output_current_amperes)} A"
            )
        if self._preferences.show_decoded_values and result.module_measurements is not None:
            module_measurements = result.module_measurements
            decoded_values.append(
                f"Module Vout={number(module_measurements.output_voltage_volts)} V, "
                f"Iout={number(module_measurements.output_current_amperes)} A"
            )
        if self._preferences.show_decoded_values and result.ac_input_measurements is not None:
            ac_measurements = result.ac_input_measurements
            decoded_values.append(
                f"AC={number(ac_measurements.first_phase_voltage_volts)}/"
                f"{number(ac_measurements.second_phase_voltage_volts)}/"
                f"{number(ac_measurements.third_phase_voltage_volts)} V"
            )
        if self._preferences.show_decoded_values and result.module_availability is not None:
            module_availability = result.module_availability
            decoded_values.append(
                f"Available={number(module_availability.available_current_amperes)} A"
            )
        if self._preferences.show_decoded_values and result.module_ratings is not None:
            module_ratings = result.module_ratings
            decoded_values.append(
                f"Ratings={number(module_ratings.minimum_output_voltage_volts)}-"
                f"{number(module_ratings.maximum_output_voltage_volts)} V, "
                f"{number(module_ratings.maximum_output_current_amperes)} A, "
                f"{number(module_ratings.rated_output_power_watts)} W"
            )
        if self._preferences.show_decoded_values and result.module_count is not None:
            decoded_values.append(f"Modules={result.module_count}")
        if self._preferences.show_decoded_values and result.module_group_number is not None:
            decoded_values.append(f"Group={result.module_group_number}")
        if self._preferences.show_decoded_values and result.ambient_temperature_celsius is not None:
            decoded_values.append(f"Ambient={result.ambient_temperature_celsius} °C")
        if self._preferences.show_decoded_values and result.module_state is not None:
            faults = result.module_state.active_faults()
            decoded_values.append(f"Faults={', '.join(faults) if faults else 'none'}")
        description = f" | {result.description}" if result.description else ""
        details = f" | {'; '.join(decoded_values)}" if decoded_values else ""
        diagnostics = (
            f" | {'; '.join(result.diagnostics)}"
            if self._preferences.show_diagnostics and result.diagnostics
            else ""
        )
        payload = f" [{frame.data.hex(' ')}]" if self._preferences.show_raw_payload else ""
        return (
            f"{self._format_identifier(frame.arbitration_id)}"
            f"{payload}{description}{details}{diagnostics}"
        )
