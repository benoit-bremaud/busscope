import pytest
from PySide6.QtWidgets import QApplication

from busscope.preferences import DisplayPreferences, IdentifierFormat
from busscope.settings_ui import SettingsWidget


class RecordingRepository:
    def __init__(self) -> None:
        self.saved: list[DisplayPreferences] = []

    def load(self) -> DisplayPreferences:
        return self.saved[-1] if self.saved else DisplayPreferences.defaults()

    def save(self, preferences: DisplayPreferences) -> None:
        self.saved.append(preferences)


@pytest.fixture
def qt_application() -> QApplication:
    application = QApplication.instance()
    if application is None or not isinstance(application, QApplication):
        application = QApplication([])
    return application


def test_widget_persists_and_publishes_a_valid_change(
    qt_application: QApplication,
) -> None:
    del qt_application
    repository = RecordingRepository()
    widget = SettingsWidget(DisplayPreferences.defaults(), repository)
    emitted: list[DisplayPreferences] = []
    widget.preferences_changed.connect(emitted.append)

    widget.numeric_precision.setValue(6)

    assert repository.saved[-1].numeric_precision == 6
    assert emitted[-1].numeric_precision == 6


def test_widget_restores_and_persists_defaults(qt_application: QApplication) -> None:
    del qt_application
    repository = RecordingRepository()
    initial = DisplayPreferences(
        identifier_format=IdentifierFormat.DECIMAL,
        numeric_precision=0,
        show_raw_payload=False,
        show_decoded_values=False,
        show_diagnostics=False,
        show_temporal_statistics=False,
    )
    widget = SettingsWidget(initial, repository)
    emitted: list[DisplayPreferences] = []
    widget.preferences_changed.connect(emitted.append)

    widget.restore_defaults()

    assert repository.saved == [DisplayPreferences.defaults()]
    assert emitted == [DisplayPreferences.defaults()]
    assert widget.numeric_precision.value() == 3
    assert widget.show_raw_payload.isChecked() is True
