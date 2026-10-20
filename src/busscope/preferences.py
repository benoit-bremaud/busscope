"""Framework-independent display preferences and persistence contract."""

from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol


class IdentifierFormat(StrEnum):
    """Supported CAN identifier renderings."""

    HEXADECIMAL = "hexadecimal"
    DECIMAL = "decimal"


@dataclass(frozen=True, slots=True)
class DisplayPreferences:
    """Validated preferences controlling presentation without changing capture data."""

    identifier_format: IdentifierFormat = IdentifierFormat.HEXADECIMAL
    numeric_precision: int = 3
    show_raw_payload: bool = True
    show_decoded_values: bool = True
    show_diagnostics: bool = True
    show_temporal_statistics: bool = True

    def __post_init__(self) -> None:
        """Reject invalid values so a preferences object is always safe to render."""
        if not isinstance(self.identifier_format, IdentifierFormat):
            raise ValueError("identifier_format must be an IdentifierFormat")
        if type(self.numeric_precision) is not int or not 0 <= self.numeric_precision <= 6:
            raise ValueError("numeric_precision must be an integer from 0 through 6")
        for name in (
            "show_raw_payload",
            "show_decoded_values",
            "show_diagnostics",
            "show_temporal_statistics",
        ):
            if type(getattr(self, name)) is not bool:
                raise ValueError(f"{name} must be a boolean")

    @classmethod
    def defaults(cls) -> "DisplayPreferences":
        """Return the documented default preferences."""
        return cls()

    @classmethod
    def from_values(cls, values: Mapping[str, object]) -> "DisplayPreferences":
        """Build preferences with an independent default fallback for each invalid field."""
        defaults = cls.defaults()
        identifier = values.get("identifier_format")
        try:
            identifier_format = (
                IdentifierFormat(identifier)
                if isinstance(identifier, str)
                else defaults.identifier_format
            )
        except (TypeError, ValueError):
            identifier_format = defaults.identifier_format

        precision = values.get("numeric_precision")
        numeric_precision = (
            precision
            if type(precision) is int and 0 <= precision <= 6
            else defaults.numeric_precision
        )

        def boolean_value(name: str, default: bool) -> bool:
            """Return the stored value only when it is a real bool, else the default."""
            value = values.get(name)
            return value if type(value) is bool else default

        return cls(
            identifier_format=identifier_format,
            numeric_precision=numeric_precision,
            show_raw_payload=boolean_value("show_raw_payload", defaults.show_raw_payload),
            show_decoded_values=boolean_value("show_decoded_values", defaults.show_decoded_values),
            show_diagnostics=boolean_value("show_diagnostics", defaults.show_diagnostics),
            show_temporal_statistics=boolean_value(
                "show_temporal_statistics", defaults.show_temporal_statistics
            ),
        )


class PreferencesRepository(Protocol):
    """Persistence boundary consumed by the settings UI."""

    def load(self) -> DisplayPreferences:
        """Load usable preferences, falling back when storage is unavailable."""

    def save(self, preferences: DisplayPreferences) -> None:
        """Persist preferences without propagating storage failures."""
