from pathlib import Path

from PySide6.QtCore import QSettings

from busscope.preferences import DisplayPreferences, IdentifierFormat
from busscope.qt_settings import QtSettingsRepository


def create_settings(path: Path) -> QSettings:
    return QSettings(str(path), QSettings.Format.IniFormat)


def test_repository_persists_and_restores_preferences(tmp_path: Path) -> None:
    path = tmp_path / "settings.ini"
    expected = DisplayPreferences(
        identifier_format=IdentifierFormat.DECIMAL,
        numeric_precision=6,
        show_raw_payload=False,
        show_decoded_values=False,
        show_diagnostics=False,
        show_temporal_statistics=False,
    )

    QtSettingsRepository(create_settings(path)).save(expected)

    assert QtSettingsRepository(create_settings(path)).load() == expected


def test_repository_defaults_only_malformed_fields(tmp_path: Path) -> None:
    settings = create_settings(tmp_path / "settings.ini")
    settings.setValue("display/identifier_format", "decimal")
    settings.setValue("display/numeric_precision", "invalid")
    settings.setValue("display/show_raw_payload", False)
    settings.setValue("display/obsolete", "ignored")
    settings.sync()

    preferences = QtSettingsRepository(settings).load()

    assert preferences.identifier_format is IdentifierFormat.DECIMAL
    assert preferences.numeric_precision == 3
    assert preferences.show_raw_payload is False
    assert preferences.show_decoded_values is True


def test_repository_converts_native_string_values(tmp_path: Path) -> None:
    settings = create_settings(tmp_path / "settings.ini")
    settings.setValue("display/identifier_format", "decimal")
    settings.setValue("display/numeric_precision", "2")
    settings.setValue("display/show_raw_payload", "false")
    settings.setValue("display/show_decoded_values", "true")
    settings.setValue("display/show_diagnostics", "false")
    settings.setValue("display/show_temporal_statistics", "true")
    settings.sync()

    preferences = QtSettingsRepository(settings).load()

    assert preferences == DisplayPreferences(
        identifier_format=IdentifierFormat.DECIMAL,
        numeric_precision=2,
        show_raw_payload=False,
        show_decoded_values=True,
        show_diagnostics=False,
        show_temporal_statistics=True,
    )


def test_repository_returns_defaults_when_storage_cannot_be_read(tmp_path: Path) -> None:
    settings = create_settings(tmp_path)

    assert QtSettingsRepository(settings).load() == DisplayPreferences.defaults()


def test_repository_does_not_propagate_storage_write_failure(tmp_path: Path) -> None:
    repository = QtSettingsRepository(create_settings(tmp_path))

    repository.save(DisplayPreferences.defaults())
