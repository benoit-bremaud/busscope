# Persistent display settings

> **Feature**: issue #26 — [Add persistent display settings](https://github.com/benoit-bremaud/busscope/issues/26)
> **Status**: implemented

## Objective

Allow an operator to customize how retained CAN information is presented and restore those
preferences on the next application launch. Preferences affect presentation only and must
not change capture, protocol decoding, temporal calculations, or transmission safety.

## Preferences

| Preference | Type | Default | Valid values |
| --- | --- | --- | --- |
| Identifier format | enum | hexadecimal | `hexadecimal`, `decimal` |
| Numeric precision | integer | 3 | 0 through 6 |
| Show raw payload | boolean | true | true, false |
| Show decoded values | boolean | true | true, false |
| Show diagnostics | boolean | true | true, false |
| Show temporal statistics | boolean | true | true, false |

Numeric precision is the number of digits rendered after the decimal separator. It applies
to decoded decimal measurements and temporal statistics, with trailing zeroes retained for
stable output. For example, precision `3` renders `12.3` as `12.300` and `0.00123` as
`0.001`. CAN identifiers, raw bytes, integer counts, and diagnostic text are unaffected.

## Rules

1. `DisplayPreferences` is a framework-independent immutable value object.
2. Preferences are persisted locally through a small repository contract. The Qt adapter
   uses `QSettings`; the domain does not import PySide6.
3. Only preference values are persisted. Captures, payloads, identifiers, credentials, and
   charger-specific data are never stored by this feature.
4. Every preference is validated independently when loaded. A missing, invalid, or obsolete
   value falls back to that field's documented default without invalidating other fields.
   `DisplayPreferences.from_values()` owns this framework-independent reconstruction from raw
   primitive values; the persistence adapter does not duplicate domain validation.
5. A valid change is saved immediately and reapplied to retained frame rows and statistics.
   Live capture and replay state are preserved.
6. Restoring defaults replaces all preferences, persists them, updates the Settings controls,
   and refreshes the visible presentation.
7. Disabling raw payload, decoded values, or diagnostics changes only the corresponding
   rendered segment. The retained `CapturedFrame` and `DecodeResult` remain unchanged.
8. Disabling temporal statistics hides the statistics controls and view without discarding
   retained records or calculated data.
9. No preference enables CAN transmission or changes the SocketCAN interface state.

## Persistence keys

The application bootstrap configures the stable `QSettings` namespace before creating a
repository:

- organization: `benoit-bremaud`;
- application: `busscope`.

The Qt adapter owns stable keys under a `display` group:

- `identifier_format`;
- `numeric_precision`;
- `show_raw_payload`;
- `show_decoded_values`;
- `show_diagnostics`;
- `show_temporal_statistics`.

Unknown keys are ignored. Storage failures must leave the in-memory preferences usable and
must not interrupt capture.

## Verification

Tests must cover:

- documented defaults;
- every valid preference value;
- persistence and restoration across repository instances;
- missing, malformed, out-of-range, and obsolete stored values;
- immediate refresh of retained frames and statistics;
- restoring and persisting defaults;
- unchanged capture and replay state while preferences change;
- absence of any transmission setting.

## Out of scope

Themes, localization, configurable decoding rules, configurable analysis algorithms,
automatic SocketCAN setup, CAN transmission, and persistence of capture content.
