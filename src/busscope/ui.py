"""PySide6 main window for CAN capture, replay, settings, and transmission."""

import logging
import time
from pathlib import Path
from typing import Protocol

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QKeySequence, QPalette
from PySide6.QtWidgets import (
    QAbstractButton,
    QApplication,
    QButtonGroup,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMainWindow,
    QMenu,
    QSizePolicy,
    QTabWidget,
    QToolBar,
    QToolButton,
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
from busscope.icons import load_icon
from busscope.preferences import DisplayPreferences, IdentifierFormat
from busscope.protocol import DecodeResult, format_decoded_values
from busscope.protocol_catalogue import DEFAULT_CATALOGUE, Feature
from busscope.protocol_selector import ProtocolSelector
from busscope.replay import CsvCaptureLoader, ReplayController
from busscope.settings_ui import SettingsWidget
from busscope.toolbar import (
    PrimaryIntent,
    ToolbarAction,
    ToolbarMode,
    ToolbarState,
    can_switch_mode,
    primary_intent,
    visible_actions,
)
from busscope.transmission_ui import TransmissionWidget

_PRIMARY_PRESENTATION = {
    PrimaryIntent.RECORD: ("circle-dot", "Start capture"),
    PrimaryIntent.STOP: ("square", "Stop capture"),
    PrimaryIntent.PLAY: ("play", "Play replay"),
    PrimaryIntent.PAUSE: ("pause", "Pause replay"),
}

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
    # Emitted when the frames exposed by captured_frames() are another capture, or when the
    # first frame of a capture arrives: read-only consumers re-evaluate what they show.
    capture_changed = Signal()

    def __init__(
        self,
        controller: CaptureController,
        preferences: DisplayPreferences,
        settings_widget: SettingsWidget,
        transmission_widget: TransmissionWidget | None,
        initial_protocol_key: str | None = None,
    ) -> None:
        """Wire the controller, preferences and child widgets into the main window.

        Without ``initial_protocol_key`` the capture tab starts on the protocol picker alone.
        Without ``transmission_widget`` the window has no Transmission tab (ADR-0009).
        """
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
        self._capture_generation = 0
        # Index of the first record of the current source: an earlier source's records stay
        # on screen but are not the current capture.
        self._source_start = 0
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
        # No source until the protocol makes one possible and the operator picks it.
        self._mode: ToolbarMode | None = None
        self._replay_active = False
        self.primary_action = QAction(self)
        self.primary_shortcut = QAction(self)
        self.primary_shortcut.setShortcut(QKeySequence(Qt.Key.Key_Space))
        self.freeze_action = self._create_action("snowflake", "Freeze display")
        self.freeze_action.setCheckable(True)
        self.clear_action = self._create_action("trash-2", "Clear frames", "Ctrl+L")
        self.export_action = self._create_action("download", "Export CSV", "Ctrl+E")
        self.load_action = self._create_action("folder-open", "Load CSV", "Ctrl+O")
        self.replay_stop_action = self._create_action("square", "Stop replay")
        self.statistics_action = self._create_action("refresh-cw", "Refresh statistics")
        self.reset_replay_action = self._create_action("rotate-ccw", "Reset replay")
        self.live_mode_button = QToolButton()
        self.live_mode_button.setText("Live")
        self.replay_mode_button = QToolButton()
        self.replay_mode_button.setText("Replay")
        self._mode_group = QButtonGroup(self)
        for button in (self.live_mode_button, self.replay_mode_button):
            button.setCheckable(True)
            self._mode_group.addButton(button)
        self.live_mode_button.setToolTip("Live capture (Ctrl+M to switch)")
        self.replay_mode_button.setToolTip("CSV replay (Ctrl+M to switch)")
        self.switch_mode_action = QAction(self)
        self.switch_mode_action.setShortcut(QKeySequence("Ctrl+M"))
        self.status_pill = QLabel()
        self.status_pill.setObjectName("statusPill")
        self.status_pill.setStyleSheet(
            "QLabel#statusPill { border: 1px solid palette(mid); border-radius: 9px;"
            " padding: 1px 8px; }"
        )
        self.listen_only_label = QLabel("Listen-only")
        self.listen_only_label.setToolTip(
            "Frame transmission is disabled"
            if transmission_widget is None
            else "The capture tab is listen-only; manual transmission is enabled in its own tab"
        )
        lock_icon = load_icon("lock", self.palette().color(QPalette.ColorRole.WindowText))
        self.listen_only_icon = QLabel()
        self.listen_only_icon.setPixmap(lock_icon.pixmap(16, 16))
        self.listen_only_label.setAccessibleName("Listen-only")
        self.overflow_button = QToolButton()
        self.overflow_button.setIcon(
            load_icon("ellipsis", self.palette().color(QPalette.ColorRole.WindowText))
        )
        self.overflow_button.setToolTip("More actions")
        self.overflow_button.setAccessibleName("More actions")
        self.overflow_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        overflow_menu = QMenu(self.overflow_button)
        overflow_menu.addAction(self.statistics_action)
        overflow_menu.addAction(self.reset_replay_action)
        self.overflow_button.setMenu(overflow_menu)
        self.status_label = QLabel("Ready")
        # Refusal messages are long; wrap them to the window instead of widening it.
        self.status_label.setWordWrap(True)
        self.frame_list = QListWidget()
        self.frame_list.setAccessibleName("Captured CAN frames")
        self.statistics_list = QListWidget()
        self.statistics_list.setAccessibleName("CAN identifier statistics")
        self._replay_timer = QTimer(self)
        self._replay_timer.setInterval(50)
        self._replay_timer.timeout.connect(self._advance_replay)

        self.live_settings = QWidget()
        live_settings_layout = QHBoxLayout(self.live_settings)
        live_settings_layout.setContentsMargins(0, 0, 0, 0)
        self.backend_settings = self._labelled("Backend:", self.interface_input)
        self.channel_settings = self._labelled("Channel:", self.channel_input)
        live_settings_layout.addWidget(self.backend_settings)
        live_settings_layout.addWidget(self.channel_settings)
        live_settings_layout.addWidget(self.unverified_silence_input)
        self.can_filter = QWidget()
        can_filter_layout = QHBoxLayout(self.can_filter)
        can_filter_layout.setContentsMargins(0, 0, 0, 0)
        can_filter_layout.addWidget(QLabel("Filter:"))
        can_filter_layout.addWidget(self.filter_input)
        # Protocol first, then source; every other control follows from both (issue #77).
        self.protocol_selector = ProtocolSelector(DEFAULT_CATALOGUE, initial_protocol_key)
        controls = QHBoxLayout()
        controls.addWidget(self.live_mode_button)
        controls.addWidget(self.replay_mode_button)
        controls.addWidget(self.live_settings)
        controls.addWidget(self.can_filter)
        self.toolbar = QToolBar()
        self.toolbar.addAction(self.primary_action)
        for action in (
            self.freeze_action,
            self.replay_stop_action,
            self.clear_action,
            self.load_action,
            self.export_action,
        ):
            self.toolbar.addAction(action)
        spacer = QWidget()
        spacer.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        self.toolbar.addWidget(spacer)
        self.toolbar.addWidget(self.status_pill)
        self.toolbar.addWidget(self.overflow_button)

        capture_widget = QWidget()
        layout = QVBoxLayout(capture_widget)
        # The listen-only badge stays visible in every state, even before a source exists.
        top_row = QHBoxLayout()
        top_row.addWidget(self.protocol_selector)
        top_row.addWidget(self.listen_only_icon)
        top_row.addWidget(self.listen_only_label)
        layout.addLayout(top_row)
        layout.addLayout(controls)
        layout.addWidget(self.toolbar)
        # Space and Ctrl+M belong to the capture tab only, not to Settings or Transmission.
        for action in (self.primary_shortcut, self.switch_mode_action):
            action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            capture_widget.addAction(action)
        layout.addWidget(self.status_label)
        self.statistics_label = QLabel("Statistics:")
        layout.addWidget(self.statistics_label)
        layout.addWidget(self.statistics_list)
        layout.addWidget(self.frame_list)
        self.tabs = QTabWidget()
        self.tabs.addTab(capture_widget, "Capture")
        if self.transmission_widget is not None:
            self.tabs.addTab(self.transmission_widget, "Transmission")
        self.tabs.addTab(self.settings_widget, "Settings")
        self.setCentralWidget(self.tabs)
        self.setWindowTitle("BusScope")
        self.resize(720, 480)

        self.primary_action.triggered.connect(self.trigger_primary)
        self.primary_shortcut.triggered.connect(self._on_space)
        self.freeze_action.triggered.connect(self.toggle_display_pause)
        self.clear_action.triggered.connect(self.clear_history)
        self.export_action.triggered.connect(self.export_csv)
        self.statistics_action.triggered.connect(self.refresh_statistics)
        self.load_action.triggered.connect(self.load_replay)
        self.replay_stop_action.triggered.connect(self.stop_replay)
        self.reset_replay_action.triggered.connect(self.reset_replay)
        self.live_mode_button.clicked.connect(lambda: self.set_mode(ToolbarMode.LIVE))
        self.replay_mode_button.clicked.connect(lambda: self.set_mode(ToolbarMode.REPLAY))
        self.switch_mode_action.triggered.connect(self.switch_mode)
        self.filter_input.textChanged.connect(self.apply_filter)
        self.protocol_selector.protocol_changed.connect(lambda _: self._on_protocol_changed())
        self.settings_widget.preferences_changed.connect(self.apply_preferences)
        self.apply_preferences(preferences)
        self._on_protocol_changed()

    @staticmethod
    def _labelled(label: str, field: QWidget) -> QWidget:
        """Group a field with its label so both appear and disappear together."""
        widget = QWidget()
        layout = QHBoxLayout(widget)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(QLabel(label))
        layout.addWidget(field)
        return widget

    def captured_frames(self) -> tuple[CapturedFrame, ...]:
        """Frames captured, or the whole loaded replay, for read-only consumers (AI tab)."""
        if self._mode is ToolbarMode.REPLAY and self._replay.has_records:
            return self._replay.records
        return tuple(self._records[self._source_start :])

    def capture_generation(self) -> int:
        """Identity of the capture behind captured_frames(): bumped on every source change."""
        return self._capture_generation

    def _new_capture(self) -> None:
        """Record that captured_frames() now describes another capture."""
        self._capture_generation += 1
        self._source_start = len(self._records)
        self.capture_changed.emit()

    def features(self) -> frozenset[Feature]:
        """Features the chosen protocol resolves from the catalogue; none before a pick."""
        protocol = self.protocol_selector.selected
        if protocol is None:
            return frozenset()
        return DEFAULT_CATALOGUE.features(protocol.key)

    def _sources(self) -> tuple[ToolbarMode, ...]:
        features = self.features()
        return tuple(
            mode
            for mode, feature in (
                (ToolbarMode.LIVE, Feature.LIVE_SOURCE),
                (ToolbarMode.REPLAY, Feature.REPLAY_SOURCE),
            )
            if feature in features
        )

    def _on_protocol_changed(self) -> None:
        """Keep the source if the new protocol offers it; skip the choice when only one."""
        sources = self._sources()
        if self._mode not in sources:
            self._mode = None
        if len(sources) == 1:
            self._mode = sources[0]
        self._check_mode_button()
        self._sync_toolbar()

    def _check_mode_button(self) -> None:
        # An exclusive group refuses to uncheck its last button, hence the toggle.
        self._mode_group.setExclusive(False)
        self.live_mode_button.setChecked(self._mode is ToolbarMode.LIVE)
        self.replay_mode_button.setChecked(self._mode is ToolbarMode.REPLAY)
        self._mode_group.setExclusive(True)

    def _create_action(self, icon: str, text: str, shortcut: str | None = None) -> QAction:
        """Build an icon-only action whose tooltip names it and its shortcut."""
        color = self.palette().color(QPalette.ColorRole.WindowText)
        action = QAction(load_icon(icon, color), text, self)
        if shortcut is not None:
            action.setShortcut(QKeySequence(shortcut))
            action.setToolTip(f"{text} ({shortcut})")
        return action

    def _toolbar_state(self, mode: ToolbarMode) -> ToolbarState:
        """Snapshot the window state for the toolbar rules."""
        return ToolbarState(
            mode=mode,
            capturing=self._capturing,
            replay_loaded=self._replay.has_records,
            replay_playing=self._replay.is_playing,
            replay_active=self._replay_active,
        )

    def _sync_toolbar(self) -> None:
        """Show only the controls the chosen protocol and the current state make possible."""
        features = self.features()
        sources = self._sources()
        self.live_mode_button.setVisible(len(sources) > 1)
        self.replay_mode_button.setVisible(len(sources) > 1)
        self._sync_statistics()
        self.can_filter.setVisible(self._mode is not None and Feature.CAN_FILTER in features)
        live = self._mode is ToolbarMode.LIVE
        self.backend_settings.setVisible(Feature.CAN_BACKEND in features)
        self.channel_settings.setVisible(Feature.CAN_CHANNEL in features)
        self.live_settings.setVisible(
            live and bool({Feature.CAN_BACKEND, Feature.CAN_CHANNEL} & features)
        )
        # Same rule as the source switch (#69): locked while a source feeds the view.
        self.protocol_selector.setEnabled(
            self._mode is None or can_switch_mode(self._toolbar_state(self._mode))
        )
        self.toolbar.setVisible(self._mode is not None)
        if self._mode is None:
            self.status_pill.setText("Choose source" if sources else "Choose protocol")
            return
        state = self._toolbar_state(self._mode)
        visible = visible_actions(state)
        controls = {
            ToolbarAction.PRIMARY: self.primary_action,
            ToolbarAction.FREEZE: self.freeze_action,
            ToolbarAction.CLEAR: self.clear_action,
            ToolbarAction.EXPORT: self.export_action,
            ToolbarAction.LOAD: self.load_action,
            ToolbarAction.REPLAY_STOP: self.replay_stop_action,
        }
        for toolbar_action, action in controls.items():
            action.setVisible(toolbar_action in visible)
        intent = primary_intent(state)
        icon, text = _PRIMARY_PRESENTATION[intent]
        self.primary_action.setIcon(
            load_icon(icon, self.palette().color(QPalette.ColorRole.WindowText))
        )
        self.primary_action.setText(text)
        self.primary_action.setToolTip(f"{text} (Space)")
        switchable = can_switch_mode(state)
        self.live_mode_button.setEnabled(switchable)
        self.replay_mode_button.setEnabled(switchable)
        self.reset_replay_action.setVisible(self._mode is ToolbarMode.REPLAY)
        self.freeze_action.setChecked(self._display_paused)
        freeze_icon, freeze_text = (
            ("play", "Resume display") if self._display_paused else ("snowflake", "Freeze display")
        )
        self.freeze_action.setIcon(
            load_icon(freeze_icon, self.palette().color(QPalette.ColorRole.WindowText))
        )
        self.freeze_action.setText(freeze_text)
        self.freeze_action.setToolTip(freeze_text)
        self.status_pill.setText(self._status_pill_text(state))

    def _status_pill_text(self, state: ToolbarState) -> str:
        """Name the current state in one or two words."""
        if state.mode is ToolbarMode.LIVE:
            if not state.capturing:
                return "Idle"
            return "Frozen" if self._display_paused else "Listening"
        if not state.replay_loaded:
            return "No capture"
        if state.replay_playing:
            return "Playing"
        return "Paused" if state.replay_active else "Loaded"

    def set_mode(self, mode: ToolbarMode) -> None:
        """Switch to ``mode`` if the protocol offers it and no source is running."""
        running = self._mode is not None and not can_switch_mode(self._toolbar_state(self._mode))
        if mode in self._sources() and not running and mode is not self._mode:
            self._mode = mode
            self._new_capture()
        self._check_mode_button()
        self._sync_toolbar()

    def switch_mode(self) -> None:
        """Toggle to the other source (Ctrl+M); nothing to toggle before a first choice."""
        if self._mode is None:
            return
        other = ToolbarMode.REPLAY if self._mode is ToolbarMode.LIVE else ToolbarMode.LIVE
        self.set_mode(other)

    def trigger_primary(self) -> None:
        """Run the primary toggle of the current state; inert before a source is chosen."""
        if self._mode is None:
            return
        dispatch = {
            PrimaryIntent.RECORD: self.start_capture,
            PrimaryIntent.STOP: self.stop_capture,
            PrimaryIntent.PLAY: self.play_replay,
            PrimaryIntent.PAUSE: self.pause_replay,
        }
        dispatch[primary_intent(self._toolbar_state(self._mode))]()

    def _on_space(self) -> None:
        """Trigger the primary toggle, unless a focused control owns Space.

        The shortcut would otherwise steal Space from the focused button or combo box
        and break keyboard navigation.
        """
        focused = QApplication.focusWidget()
        if isinstance(focused, QAbstractButton):
            focused.click()
            return
        if isinstance(focused, QComboBox):
            focused.showPopup()
            return
        self.primary_action.trigger()

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
        visible = self._sync_statistics()
        self._render_display()
        if visible and statistics_changed:
            self.refresh_statistics()

    def _sync_statistics(self) -> bool:
        """Show statistics when the preference, the protocol and a chosen source allow it."""
        visible = (
            self._preferences.show_temporal_statistics
            and self._mode is not None
            and Feature.STATISTICS in self.features()
        )
        self.statistics_label.setVisible(visible)
        self.statistics_list.setVisible(visible)
        self.statistics_action.setVisible(visible)
        return visible

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
        # Only slcan cannot verify silence, so only slcan offers to accept it.
        self.unverified_silence_input.setVisible(slcan)
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
        self._sync_toolbar()
        self.status_label.setText(f"Capturing on {channel}")
        self._timer.start()

    def stop_capture(self) -> None:
        """Stop polling and reset the window even if cleanup fails."""
        self._timer.stop()
        self._capturing = False
        self._display_paused = False
        self._display_pause_index = None
        self._sync_toolbar()
        try:
            self._controller.stop()
        except Exception as error:
            self.status_label.setText(f"Error: {error}")
            return
        self.status_label.setText("Stopped")

    def toggle_display_pause(self) -> None:
        """Pause or resume display updates without stopping capture."""
        self._display_paused = not self._display_paused
        self._sync_toolbar()
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
        self._replay_active = False
        self._sync_toolbar()
        self.frame_list.clear()
        self._new_capture()
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
            # A finished replay shows as Loaded, so Play restarts it from the beginning.
            self.reset_replay()
            self._replay.play()
        self._replay_last_tick = time.monotonic()
        self._replay_timer.start()
        self._replay_active = True
        self._sync_toolbar()
        self.status_label.setText("Replaying CSV capture")

    def pause_replay(self) -> None:
        """Pause local CSV playback."""
        self._replay.pause()
        self._replay_timer.stop()
        self._sync_toolbar()
        self.status_label.setText("Replay paused")

    def stop_replay(self) -> None:
        """Stop local CSV playback while preserving its current position."""
        self._replay.stop()
        self._replay_timer.stop()
        self._replay_active = False
        self._sync_toolbar()
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
        self._replay_active = False
        self._sync_toolbar()
        self.status_label.setText("Replay reset")
        self._new_capture()

    def _advance_replay(self) -> None:
        """Release replay records that became due since the last tick, then stop at the end."""
        was_playing = self._replay.is_playing
        now = time.monotonic()
        due = self._replay.advance(now - self._replay_last_tick)
        self._replay_last_tick = now
        for captured in due:
            self._append_record(captured)
            if not self._display_paused and self._frame_filter.matches(captured):
                self._add_to_display(captured)
        if was_playing and not self._replay.is_playing:
            self._replay_timer.stop()
            self._replay_active = False
            self._sync_toolbar()
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
                self._display_paused = False
                self._display_pause_index = None
                self._sync_toolbar()
                self.status_label.setText(f"Error: {error}")
                return

            if result is None:
                return
            capture_origin = self._capture_origin
            if capture_origin is None:
                logger.error("Cannot timestamp a frame without a capture origin")
                return
            captured = CapturedFrame(time.monotonic() - capture_origin, result)
            self._append_record(captured)
            if not self._display_paused and self._frame_filter.matches(captured):
                self._add_to_display(captured)

    def _append_record(self, captured: CapturedFrame) -> None:
        """Keep the frame; the first one makes the capture usable by read-only consumers."""
        first = len(self._records) == self._source_start
        self._records.append(captured)
        if first:
            self.capture_changed.emit()

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
        decoded_values = (
            format_decoded_values(result, self._format_number)
            if self._preferences.show_decoded_values
            else []
        )
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
