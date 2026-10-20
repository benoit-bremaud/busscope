# Sequence diagram — display settings — update and persist a preference

> **Feature**: issue #26 — [Add persistent display settings](https://github.com/benoit-bremaud/busscope/issues/26)
> **Source specs**: `docs/architecture/specs/display-settings.md` §Rules, §Persistence keys

## Context

This sequence clarifies how a valid UI change crosses the domain preference model and the
Qt persistence adapter before refreshing retained presentation. It does not recapture or
redecode frames.

## Diagram

```mermaid
sequenceDiagram
    actor Operator
    participant Settings as Settings tab
    participant Window as CaptureWindow
    participant Preferences as DisplayPreferences
    participant Store as QtSettingsRepository

    Operator->>Settings: Change one display preference
    Settings->>Preferences: Create validated replacement
    Preferences-->>Settings: Updated preferences
    Settings->>Store: save(preferences)
    Store-->>Settings: Saved or recoverable failure
    Settings->>Window: apply_preferences(preferences)
    Window->>Window: Re-render retained frames
    Window->>Window: Refresh or hide statistics
    Window-->>Operator: Show updated presentation
```

## Notes

- The immutable value object prevents partially updated invalid state.
- A persistence failure does not stop capture or discard the in-memory preference change.
- Existing decoded results are reformatted rather than decoded again.
