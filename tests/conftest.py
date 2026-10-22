"""Shared test doubles for the capture boundary."""

from __future__ import annotations

from collections.abc import Iterator

import keyring
import pytest
from keyring.backends.fail import Keyring as FailKeyring


class FakeControllerMode:
    """Stands in for the `ip link` reader, which the suite must never actually run.

    Shared rather than duplicated per module: it encodes the shape of a protocol, so a
    second copy would silently go stale when ControllerModePort changes.
    """

    def __init__(self, answer: bool | None = True) -> None:
        self.answer = answer
        self.channels: list[str] = []

    def is_listen_only(self, channel: str) -> bool | None:
        self.channels.append(channel)
        return self.answer


@pytest.fixture(autouse=True)
def _no_real_keyring() -> Iterator[None]:
    """The suite must never read or write the developer's real OS keyring."""
    previous = keyring.get_keyring()
    keyring.set_keyring(FailKeyring())  # type: ignore[no-untyped-call]  # unannotated
    yield
    keyring.set_keyring(previous)
