# Sequence diagram — display settings — load persisted preferences

> **Feature**: issue #26 — [Add persistent display settings](https://github.com/benoit-bremaud/busscope/issues/26)
> **Source specs**: `docs/architecture/specs/display-settings.md` §Rules, §Persistence keys

## Context

This sequence defines startup restoration and per-field fallback before the Qt views are
created. It keeps primitive storage conversion outside the framework-independent model.

## Diagram

```mermaid
sequenceDiagram
    participant Bootstrap as Application bootstrap
    participant Store as QtSettingsRepository
    participant Settings as QSettings
    participant Preferences as DisplayPreferences
    participant SettingsTab as SettingsWidget
    participant Window as CaptureWindow

    Bootstrap->>Store: load()
    Store->>Settings: Read raw display values
    alt Read succeeds
        Settings-->>Store: Primitive values
        Store->>Preferences: from_values(values)
        Preferences->>Preferences: Validate each field independently
        Preferences-->>Store: Valid preferences with per-field defaults
    else Settings backend cannot be read
        Settings-->>Store: Storage access failure
        Store->>Preferences: defaults()
        Preferences-->>Store: Default preferences
    end
    Store-->>Bootstrap: DisplayPreferences
    Bootstrap->>SettingsTab: Create with preferences and repository
    Bootstrap->>Window: Create with preferences and SettingsWidget
    Window-->>Bootstrap: Capture and Settings tabs ready
```

## Notes

- Missing, malformed, out-of-range, and obsolete values affect only their own field.
- A global storage read failure returns domain defaults and does not prevent startup or capture.
- `DisplayPreferences` has no dependency on Qt or the storage format.
- `CaptureWindow` receives no persistence adapter and remains unaware of `QSettings`.
- The application bootstrap loads preferences before constructing the views.
