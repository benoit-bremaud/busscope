# Component diagram — display settings — dependency boundaries

> **Feature**: issue #26 — [Add persistent display settings](https://github.com/benoit-bremaud/busscope/issues/26)
> **Source specs**: `docs/architecture/specs/display-settings.md` §Rules, §Persistence keys

## Context

This view defines the dependency direction between the pure preference model, the Qt UI,
and local persistence. It does not introduce a general-purpose configuration framework.

## Diagram

```mermaid
flowchart LR
    subgraph Domain[Framework-independent core]
        Model[DisplayPreferences]
        Contract[PreferencesRepository contract]
    end

    subgraph UI[PySide6 adapter]
        Bootstrap[Application bootstrap]
        Window[CaptureWindow]
        Settings[SettingsWidget]
    end

    subgraph Persistence[Qt persistence adapter]
        QStore[QtSettingsRepository]
        QSettings[QSettings]
    end

    Settings --> Model
    Settings --> Contract
    Window --> Settings
    Window --> Model
    Bootstrap -->|"configures stable namespace"| QSettings
    Bootstrap --> QStore
    Bootstrap --> Settings
    Bootstrap --> Window
    QStore --> Contract
    QStore --> Model
    QStore --> QSettings
```

## Notes

- Dependencies point toward the pure preference model and repository contract.
- The application bootstrap configures the `benoit-bremaud` / `busscope` namespace before
  the repository creates or accesses `QSettings`.
- The bootstrap assembles the concrete adapter and Qt widgets; `CaptureWindow` receives no
  persistence dependency.
- `CaptureWindow` subscribes to `SettingsWidget.preferences_changed`; the widget holds no
  reference to its containing window.
- `QSettings` remains confined to the persistence adapter.
- The capture and protocol modules do not depend on settings persistence.
