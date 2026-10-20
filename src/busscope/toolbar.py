"""Framework-neutral rules for the context-aware capture toolbar (issue #69).

The window feeds a snapshot of its state and gets back which controls to show and what the
single primary toggle does. Keeping this free of Qt lets the future React UI reuse it.
"""

from dataclasses import dataclass
from enum import Enum


class ToolbarMode(Enum):
    """Data source the capture tab is working on."""

    LIVE = "live"
    REPLAY = "replay"


class ToolbarAction(Enum):
    """Context-dependent toolbar controls; the mode switch and overflow are always shown."""

    PRIMARY = "primary"
    FREEZE = "freeze"
    CLEAR = "clear"
    EXPORT = "export"
    LOAD = "load"
    REPLAY_STOP = "replay_stop"


class PrimaryIntent(Enum):
    """What the primary toggle (Space) does in the current state."""

    RECORD = "record"
    STOP = "stop"
    PLAY = "play"
    PAUSE = "pause"


@dataclass(frozen=True)
class ToolbarState:
    """Snapshot of the window state that drives the toolbar.

    ``replay_active`` is true from the first play until stop, reset, reload or the end of
    the capture, so a paused replay keeps its stop control.
    """

    mode: ToolbarMode
    capturing: bool = False
    replay_loaded: bool = False
    replay_playing: bool = False
    replay_active: bool = False


def visible_actions(state: ToolbarState) -> frozenset[ToolbarAction]:
    """Return the controls to show; everything else is hidden rather than greyed out."""
    if state.mode is ToolbarMode.LIVE:
        actions = {ToolbarAction.PRIMARY, ToolbarAction.CLEAR, ToolbarAction.EXPORT}
        if state.capturing:
            actions.add(ToolbarAction.FREEZE)
        return frozenset(actions)
    if not state.replay_loaded:
        return frozenset({ToolbarAction.LOAD})
    if state.replay_active:
        return frozenset({ToolbarAction.PRIMARY, ToolbarAction.REPLAY_STOP, ToolbarAction.EXPORT})
    return frozenset({ToolbarAction.PRIMARY, ToolbarAction.LOAD, ToolbarAction.EXPORT})


def primary_intent(state: ToolbarState) -> PrimaryIntent:
    """Return the action the primary toggle performs next."""
    if state.mode is ToolbarMode.LIVE:
        return PrimaryIntent.STOP if state.capturing else PrimaryIntent.RECORD
    return PrimaryIntent.PAUSE if state.replay_playing else PrimaryIntent.PLAY


def can_switch_mode(state: ToolbarState) -> bool:
    """Forbid switching while a source is feeding the frame view."""
    return not state.capturing and not state.replay_playing
