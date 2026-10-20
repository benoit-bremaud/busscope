"""Qt persistence adapter for display preferences."""

import logging

from PySide6.QtCore import QSettings

from busscope.preferences import DisplayPreferences

logger = logging.getLogger(__name__)


class QtSettingsRepository:
    """Store display preferences in an injected QSettings instance."""

    _PREFIX = "display/"

    def __init__(self, settings: QSettings) -> None:
        """Keep the injected QSettings so tests can use an isolated store."""
        self._settings = settings

    def load(self) -> DisplayPreferences:
        """Load preferences or domain defaults after a global storage failure."""
        self._settings.sync()
        if self._settings.status() is not QSettings.Status.NoError:
            logger.warning("Cannot read display preferences; using defaults")
            return DisplayPreferences.defaults()
        return DisplayPreferences.from_values(
            {
                "identifier_format": self._read("identifier_format"),
                "numeric_precision": self._stored_integer("numeric_precision"),
                "show_raw_payload": self._stored_boolean("show_raw_payload"),
                "show_decoded_values": self._stored_boolean("show_decoded_values"),
                "show_diagnostics": self._stored_boolean("show_diagnostics"),
                "show_temporal_statistics": self._stored_boolean(
                    "show_temporal_statistics"
                ),
            }
        )

    def _read(self, key: str) -> object:
        """Read one raw value under the display prefix; None when absent."""
        return self._settings.value(f"{self._PREFIX}{key}")

    def _stored_integer(self, key: str) -> object:
        """Coerce INI string storage back to int; leave anything else for domain validation."""
        value = self._read(key)
        if isinstance(value, str):
            try:
                return int(value)
            except ValueError:
                return value
        return value

    def _stored_boolean(self, key: str) -> object:
        """Coerce INI 'true'/'false' strings back to bool; leave anything else for validation."""
        value = self._read(key)
        if isinstance(value, str) and value.lower() in {"true", "false"}:
            return value.lower() == "true"
        return value

    def save(self, preferences: DisplayPreferences) -> None:
        """Persist all preference values without interrupting the application on failure."""
        values: dict[str, object] = {
            "identifier_format": preferences.identifier_format.value,
            "numeric_precision": preferences.numeric_precision,
            "show_raw_payload": preferences.show_raw_payload,
            "show_decoded_values": preferences.show_decoded_values,
            "show_diagnostics": preferences.show_diagnostics,
            "show_temporal_statistics": preferences.show_temporal_statistics,
        }
        for key, value in values.items():
            self._settings.setValue(f"{self._PREFIX}{key}", value)
        self._settings.sync()
        if self._settings.status() is not QSettings.Status.NoError:
            logger.warning("Cannot persist display preferences")
