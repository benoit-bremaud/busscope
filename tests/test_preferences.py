from dataclasses import FrozenInstanceError

import pytest

from busscope.preferences import DisplayPreferences, IdentifierFormat


def test_preferences_expose_documented_defaults() -> None:
    preferences = DisplayPreferences.defaults()

    assert preferences == DisplayPreferences()
    assert preferences.identifier_format is IdentifierFormat.HEXADECIMAL
    assert preferences.numeric_precision == 3
    assert preferences.show_raw_payload is True
    assert preferences.show_decoded_values is True
    assert preferences.show_diagnostics is True
    assert preferences.show_temporal_statistics is True


@pytest.mark.parametrize("precision", [0, 6])
def test_preferences_accept_precision_boundaries(precision: int) -> None:
    assert DisplayPreferences(numeric_precision=precision).numeric_precision == precision


@pytest.mark.parametrize("precision", [-1, 7, True, 1.5])
def test_preferences_reject_invalid_precision(precision: object) -> None:
    with pytest.raises(ValueError, match="numeric_precision"):
        DisplayPreferences(numeric_precision=precision)  # type: ignore[arg-type]


def test_preferences_are_immutable() -> None:
    preferences = DisplayPreferences.defaults()

    with pytest.raises(FrozenInstanceError):
        preferences.numeric_precision = 2  # type: ignore[misc]


def test_preferences_reject_invalid_identifier_format() -> None:
    with pytest.raises(ValueError, match="identifier_format"):
        DisplayPreferences(identifier_format="decimal")  # type: ignore[arg-type]


@pytest.mark.parametrize(
    "field",
    [
        "show_raw_payload",
        "show_decoded_values",
        "show_diagnostics",
        "show_temporal_statistics",
    ],
)
def test_preferences_reject_non_boolean_flags(field: str) -> None:
    with pytest.raises(ValueError, match=field):
        DisplayPreferences(**{field: 1})  # type: ignore[arg-type]


def test_from_values_preserves_valid_fields_and_defaults_invalid_fields() -> None:
    preferences = DisplayPreferences.from_values(
        {
            "identifier_format": "decimal",
            "numeric_precision": 6,
            "show_raw_payload": False,
            "show_decoded_values": "invalid",
            "show_diagnostics": False,
            "show_temporal_statistics": False,
            "obsolete": True,
        }
    )

    assert preferences == DisplayPreferences(
        identifier_format=IdentifierFormat.DECIMAL,
        numeric_precision=6,
        show_raw_payload=False,
        show_decoded_values=True,
        show_diagnostics=False,
        show_temporal_statistics=False,
    )


def test_from_values_defaults_missing_and_out_of_range_values() -> None:
    assert DisplayPreferences.from_values({"numeric_precision": 7}) == DisplayPreferences.defaults()


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("identifier_format", "unknown"),
        ("show_raw_payload", 1),
        ("show_decoded_values", None),
        ("show_diagnostics", "false"),
        ("show_temporal_statistics", 0),
    ],
)
def test_from_values_defaults_each_malformed_field(field: str, value: object) -> None:
    assert DisplayPreferences.from_values({field: value}) == DisplayPreferences.defaults()
