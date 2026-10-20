from collections.abc import Iterable

import pytest

from busscope.capture import CaptureConfiguration
from busscope.protocol import CanFrame, ProtocolDecoder
from busscope.session import CaptureSession


class FakePort:
    def __init__(self, frames: Iterable[CanFrame], open_error: Exception | None = None) -> None:
        self.frames = iter(frames)
        self.open_error = open_error
        self.opened = False
        self.closed = False

    def open(self, configuration: CaptureConfiguration) -> None:
        del configuration
        if self.open_error is not None:
            raise self.open_error
        self.opened = True

    def receive(self, timeout: float | None = None) -> CanFrame | None:
        del timeout
        return next(self.frames, None)

    def close(self) -> None:
        self.closed = True
        self.opened = False


def test_capture_session_opens_decodes_and_closes_on_timeout() -> None:
    port = FakePort([CanFrame(arbitration_id=0x123, data=b"\x00" * 8)])
    session = CaptureSession(port, ProtocolDecoder())

    results = list(session.capture(CaptureConfiguration(channel="can0")))

    assert len(results) == 1
    assert results[0].frame.arbitration_id == 0x123
    assert port.closed is True


def test_capture_session_poll_keeps_session_open_after_timeout() -> None:
    port = FakePort([])
    session = CaptureSession(port, ProtocolDecoder())

    session.start(CaptureConfiguration(channel="can0"))
    result = session.poll(timeout=0)

    assert result is None
    assert port.closed is False
    session.stop()
    assert port.closed is True


def test_capture_session_stop_ends_loop_after_current_frame() -> None:
    port = FakePort(
        [
            CanFrame(arbitration_id=0x123, data=b"\x00" * 8),
            CanFrame(arbitration_id=0x124, data=b"\x01" * 8),
        ]
    )
    session = CaptureSession(port, ProtocolDecoder())
    capture = session.capture(CaptureConfiguration(channel="can0"))

    first_result = next(capture)
    session.stop()

    assert first_result.frame.arbitration_id == 0x123
    assert list(capture) == []
    assert port.closed is True


def test_capture_session_generator_does_not_receive_after_stop() -> None:
    port = FakePort([CanFrame(arbitration_id=0x123, data=b"\x00" * 8)])
    session = CaptureSession(port, ProtocolDecoder())
    capture = session.capture(CaptureConfiguration(channel="can0"))

    next(capture)
    session.stop()

    assert list(capture) == []
    assert port.closed is True


def test_capture_session_preserves_open_error_when_close_also_fails() -> None:
    class FailingClosePort(FakePort):
        def close(self) -> None:
            raise RuntimeError("close failed")

    open_error = OSError("open failed")
    session = CaptureSession(FailingClosePort([], open_error=open_error), ProtocolDecoder())

    with pytest.raises(OSError, match="open failed"):
        list(session.capture(CaptureConfiguration(channel="can0")))


def test_capture_session_rejects_concurrent_capture() -> None:
    port = FakePort([CanFrame(arbitration_id=0x123, data=b"\x00" * 8)])
    session = CaptureSession(port, ProtocolDecoder())
    capture = session.capture(CaptureConfiguration(channel="can0"))
    next(capture)

    with pytest.raises(RuntimeError, match="already running"):
        list(session.capture(CaptureConfiguration(channel="can0")))

    session.stop()
    list(capture)
    assert port.closed is True


def test_capture_session_closes_port_when_open_fails() -> None:
    port = FakePort([], open_error=OSError("CAN interface unavailable"))
    session = CaptureSession(port, ProtocolDecoder())

    with pytest.raises(OSError, match="CAN interface unavailable"):
        list(session.capture(CaptureConfiguration(channel="can0")))

    assert port.closed is True


def test_capture_session_suppresses_close_error_when_stopping() -> None:
    class FailingClosePort(FakePort):
        def close(self) -> None:
            raise RuntimeError("close failed")

    port = FailingClosePort([])
    session = CaptureSession(port, ProtocolDecoder())
    session.start(CaptureConfiguration(channel="can0"))

    session.stop()

    with pytest.raises(RuntimeError, match="not running"):
        session.poll(timeout=0)
