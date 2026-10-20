"""PySide6 editor for persistent display preferences."""

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from busscope.preferences import DisplayPreferences, IdentifierFormat, PreferencesRepository


class SettingsWidget(QWidget):
    """Edit, persist, and publish display-only preferences."""

    preferences_changed = Signal(object)

    def __init__(
        self, preferences: DisplayPreferences, repository: PreferencesRepository
    ) -> None:
        """Build the controls from the given preferences without persisting them."""
        super().__init__()
        self._repository = repository
        self._updating = False

        self.identifier_format = QComboBox()
        self.identifier_format.addItem("Hexadecimal", IdentifierFormat.HEXADECIMAL)
        self.identifier_format.addItem("Decimal", IdentifierFormat.DECIMAL)
        self.numeric_precision = QSpinBox()
        self.numeric_precision.setRange(0, 6)
        self.show_raw_payload = QCheckBox("Show raw payload")
        self.show_decoded_values = QCheckBox("Show decoded values")
        self.show_diagnostics = QCheckBox("Show diagnostics")
        self.show_temporal_statistics = QCheckBox("Show temporal statistics")
        self.restore_defaults_button = QPushButton("Restore defaults")

        form = QFormLayout()
        form.addRow("Identifier format:", self.identifier_format)
        form.addRow("Numeric precision:", self.numeric_precision)
        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.show_raw_payload)
        layout.addWidget(self.show_decoded_values)
        layout.addWidget(self.show_diagnostics)
        layout.addWidget(self.show_temporal_statistics)
        layout.addWidget(self.restore_defaults_button)
        layout.addStretch()

        self.identifier_format.currentIndexChanged.connect(self._publish)
        self.numeric_precision.valueChanged.connect(self._publish)
        self.show_raw_payload.toggled.connect(self._publish)
        self.show_decoded_values.toggled.connect(self._publish)
        self.show_diagnostics.toggled.connect(self._publish)
        self.show_temporal_statistics.toggled.connect(self._publish)
        self.restore_defaults_button.clicked.connect(self.restore_defaults)
        self.set_preferences(preferences)

    def set_preferences(self, preferences: DisplayPreferences) -> None:
        """Update every control without publishing intermediate states."""
        self._updating = True
        self.identifier_format.setCurrentIndex(
            self.identifier_format.findData(preferences.identifier_format)
        )
        self.numeric_precision.setValue(preferences.numeric_precision)
        self.show_raw_payload.setChecked(preferences.show_raw_payload)
        self.show_decoded_values.setChecked(preferences.show_decoded_values)
        self.show_diagnostics.setChecked(preferences.show_diagnostics)
        self.show_temporal_statistics.setChecked(preferences.show_temporal_statistics)
        self._updating = False

    def restore_defaults(self) -> None:
        """Persist and publish the documented defaults."""
        defaults = DisplayPreferences.defaults()
        self.set_preferences(defaults)
        self._repository.save(defaults)
        self.preferences_changed.emit(defaults)

    def _publish(self) -> None:
        """Persist and emit the edited preferences, unless a programmatic update is running."""
        if self._updating:
            return
        preferences = DisplayPreferences(
            identifier_format=IdentifierFormat(self.identifier_format.currentData()),
            numeric_precision=self.numeric_precision.value(),
            show_raw_payload=self.show_raw_payload.isChecked(),
            show_decoded_values=self.show_decoded_values.isChecked(),
            show_diagnostics=self.show_diagnostics.isChecked(),
            show_temporal_statistics=self.show_temporal_statistics.isChecked(),
        )
        self._repository.save(preferences)
        self.preferences_changed.emit(preferences)
