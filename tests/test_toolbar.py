import pytest

from busscope.toolbar import (
    PrimaryIntent,
    ToolbarAction,
    ToolbarMode,
    ToolbarState,
    can_switch_mode,
    primary_intent,
    visible_actions,
)

A = ToolbarAction
LIVE = ToolbarMode.LIVE
REPLAY = ToolbarMode.REPLAY


@pytest.mark.parametrize(
    ("state", "expected"),
    [
        (ToolbarState(LIVE), {A.PRIMARY, A.CLEAR, A.EXPORT}),
        (ToolbarState(LIVE, capturing=True), {A.PRIMARY, A.FREEZE, A.CLEAR, A.EXPORT}),
        (ToolbarState(REPLAY), {A.LOAD}),
        (ToolbarState(REPLAY, replay_loaded=True), {A.PRIMARY, A.LOAD, A.EXPORT}),
        (
            ToolbarState(REPLAY, replay_loaded=True, replay_playing=True, replay_active=True),
            {A.PRIMARY, A.REPLAY_STOP, A.EXPORT},
        ),
        (
            ToolbarState(REPLAY, replay_loaded=True, replay_active=True),
            {A.PRIMARY, A.REPLAY_STOP, A.EXPORT},
        ),
    ],
)
def test_visible_actions_per_state(state: ToolbarState, expected: set[ToolbarAction]) -> None:
    assert visible_actions(state) == expected


def test_replay_actions_never_leak_into_live_mode() -> None:
    state = ToolbarState(LIVE, replay_loaded=True, replay_active=True)

    assert A.LOAD not in visible_actions(state)
    assert A.REPLAY_STOP not in visible_actions(state)


@pytest.mark.parametrize(
    ("state", "intent"),
    [
        (ToolbarState(LIVE), PrimaryIntent.RECORD),
        (ToolbarState(LIVE, capturing=True), PrimaryIntent.STOP),
        (ToolbarState(REPLAY, replay_loaded=True), PrimaryIntent.PLAY),
        (ToolbarState(REPLAY, replay_loaded=True, replay_playing=True), PrimaryIntent.PAUSE),
    ],
)
def test_primary_intent(state: ToolbarState, intent: PrimaryIntent) -> None:
    assert primary_intent(state) is intent


@pytest.mark.parametrize(
    ("state", "allowed"),
    [
        (ToolbarState(LIVE), True),
        (ToolbarState(LIVE, capturing=True), False),
        (ToolbarState(REPLAY, replay_loaded=True, replay_active=True), True),
        (ToolbarState(REPLAY, replay_loaded=True, replay_playing=True), False),
    ],
)
def test_mode_switch_is_blocked_while_a_source_runs(state: ToolbarState, allowed: bool) -> None:
    assert can_switch_mode(state) is allowed
