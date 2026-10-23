import subprocess
from collections.abc import Iterable

import can
import pytest
from conftest import FakeControllerMode

from busscope.capture import (
    CanInterface,
    CaptureConfiguration,
    IpLinkControllerMode,
    ListenOnlyUnavailableError,
    PythonCanAdapter,
    receive_frames,
)


def listening(bus_factory: object = None) -> PythonCanAdapter:
    """Adapter whose socketcan channel is confirmed listen-only."""
    return PythonCanAdapter(bus_factory, FakeControllerMode(True))  # type: ignore[arg-type]


class FakeBus:
    def __init__(self, messages: Iterable[can.Message]) -> None:
        self.messages = iter(messages)
        self.shutdown_called = False
        self.sequence: list[str] = []

    def recv(self, timeout: float | None = None) -> can.Message | None:
        del timeout
        return next(self.messages, None)

    def shutdown(self) -> None:
        self.shutdown_called = True

    def close(self) -> None:
        self.sequence.append("close")

    def set_bitrate(self, bitrate: int) -> None:
        self.sequence.append(f"set_bitrate={bitrate}")

    def open(self) -> None:
        self.sequence.append("open")


def test_adapter_opens_and_converts_standard_frame() -> None:
    bus = FakeBus([can.Message(arbitration_id=0x123, data=[1, 2], is_extended_id=False)])
    adapter = listening(lambda configuration: bus)

    adapter.open(CaptureConfiguration(channel="can0"))
    frame = adapter.receive()

    assert frame is not None
    assert frame.arbitration_id == 0x123
    assert frame.data == b"\x01\x02"
    assert frame.is_extended_id is False
    adapter.close()
    assert bus.shutdown_called is True


def test_default_factory_configures_read_only_socketcan(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []
    bus = FakeBus([])

    def fake_bus(**kwargs: object) -> FakeBus:
        calls.append(kwargs)
        return bus

    monkeypatch.setattr(can, "Bus", fake_bus)

    adapter = listening()
    adapter.open(CaptureConfiguration(channel="can0"))

    # python-can's socketcan backend accepts neither bitrate nor listen_only; passing them
    # would only restate an intent it silently discards.
    assert calls == [{"interface": "socketcan", "channel": "can0", "fd": False}]
    adapter.close()


def test_adapter_preserves_error_frame_and_timeout() -> None:
    bus = FakeBus([can.Message(is_error_frame=True)])
    adapter = listening(lambda configuration: bus)
    adapter.open(CaptureConfiguration(channel="can0"))

    frame = adapter.receive(timeout=0.1)

    assert frame is not None
    assert frame.is_error_frame is True
    assert adapter.receive(timeout=0.1) is None


def test_adapter_rejects_invalid_configuration_and_lifecycle() -> None:
    adapter = listening(lambda configuration: FakeBus([]))

    with pytest.raises(RuntimeError, match="not open"):
        adapter.receive()
    with pytest.raises(ValueError, match="must not be empty"):
        adapter.open(CaptureConfiguration(channel=""))
    with pytest.raises(ValueError, match="must be positive"):
        adapter.open(CaptureConfiguration(channel="can0", bitrate=0))
    with pytest.raises(ValueError, match="listen-only mode is mandatory"):
        adapter.open(CaptureConfiguration(channel="can0", listen_only=False))

    adapter.open(CaptureConfiguration(channel="can0"))
    with pytest.raises(RuntimeError, match="already open"):
        adapter.open(CaptureConfiguration(channel="can0"))
    adapter.close()


def test_receive_frames_yields_until_timeout() -> None:
    bus = FakeBus([can.Message(arbitration_id=0x100, data=[0xAA])])
    adapter = listening(lambda configuration: bus)
    adapter.open(CaptureConfiguration(channel="can0"))

    frames = list(receive_frames(adapter))

    assert len(frames) == 1
    assert frames[0].data == b"\xaa"


def test_slcan_backend_applies_bitrate_and_listen_only(monkeypatch: pytest.MonkeyPatch) -> None:
    """The whole point of this backend: what is declared is what reaches the device."""
    calls: list[dict[str, object]] = []
    bus = FakeBus([])

    def record(**kwargs: object) -> FakeBus:
        calls.append(kwargs)
        return bus

    monkeypatch.setattr(can, "Bus", record)
    mode = FakeControllerMode(True)

    adapter = PythonCanAdapter(controller_mode=mode)
    adapter.open(
        CaptureConfiguration(
            channel="/dev/serial/by-id/usb-CANable",
            bitrate=250_000,
            interface=CanInterface.SLCAN,
            allow_unverified_listen_only=True,
        )
    )

    assert calls == [
        {
            "interface": "slcan",
            "channel": "/dev/serial/by-id/usb-CANable",
            "listen_only": True,
        }
    ]
    # The bitrate is applied by the explicit reopen, not by the constructor, because a
    # channel left open by a previous client would otherwise keep its old one.
    # set_bitrate is what closes, writes S<n> and reopens; the constructor never
    # applies the bitrate, so a stale open channel would keep its previous one.
    assert bus.sequence == ["set_bitrate=250000"]
    # Nothing to verify out of band: this backend sets the mode itself.
    assert mode.channels == []
    adapter.close()


def test_socketcan_refuses_when_listen_only_is_not_confirmed() -> None:
    created: list[object] = []

    def factory(configuration: CaptureConfiguration) -> FakeBus:
        created.append(configuration)
        return FakeBus([])

    for answer, expected in ((False, "not in listen-only"), (None, "could not be determined")):
        mode = FakeControllerMode(answer)
        adapter = PythonCanAdapter(factory, mode)
        with pytest.raises(ListenOnlyUnavailableError, match=expected):
            adapter.open(CaptureConfiguration(channel="can1"))
        # The channel verified must be the one requested, not a hardcoded default.
        assert mode.channels == ["can1"]

    # Fail closed: an unconfirmed channel is never opened, so it can never acknowledge.
    assert created == []


CAN_LINK = (
    '[{{"ifname":"can0","linkinfo":{{"info_kind":"can","info_data":{{"ctrlmode":{modes}}}}}}}]'
)


@pytest.mark.parametrize(
    ("payload", "expected"),
    [
        (CAN_LINK.format(modes='["listen-only"]'), True),
        (CAN_LINK.format(modes='["loopback","listen-only"]'), True),
        (CAN_LINK.format(modes="[]"), False),
        (CAN_LINK.format(modes='["loopback"]'), False),
        # No ctrlmode key at all: the controller has no special mode set.
        ('[{"ifname":"can0","linkinfo":{"info_kind":"can","info_data":{}}}]', False),
        # A link alias can contain the flag name; only the parsed ctrlmode counts.
        ('[{"ifname":"can0","ifalias":"listen-only","linkinfo":{"info_kind":"veth"}}]', None),
        # Another interface's answer must never authorise the requested one.
        (
            '[{"ifname":"can1","linkinfo":'
            '{"info_kind":"can","info_data":{"ctrlmode":["listen-only"]}}}]',
            None,
        ),
        # `dev` should make this impossible, but two links means the query widened.
        ("[{},{}]", None),
        ("not json", None),
        ("[]", None),
    ],
)
def test_ip_link_reads_the_controller_mode(
    payload: str, expected: bool | None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A link alias or a widened query must never be read as a confirmation."""
    invocations: list[tuple[object, dict[str, object]]] = []

    def run(argv: object, **kwargs: object) -> object:
        invocations.append((argv, kwargs))
        return type("Completed", (), {"returncode": 0, "stdout": payload})()

    monkeypatch.setattr("busscope.capture.shutil.which", lambda name: "/usr/bin/ip")
    monkeypatch.setattr("busscope.capture.subprocess.run", run)

    assert IpLinkControllerMode().is_listen_only("can0") is expected

    # The argv is the contract of this boundary: -details is what prints the mode,
    # `dev` is what stops a value like "up" being read as a filter, and the timeout is
    # what keeps a wedged `ip` from freezing the UI thread.
    argv, kwargs = invocations[-1]
    assert argv == ["/usr/bin/ip", "-details", "-json", "link", "show", "dev", "can0"]
    assert kwargs["timeout"] == 5.0
    assert kwargs["check"] is False


@pytest.mark.parametrize(
    "failure",
    [OSError("ip vanished"), subprocess.TimeoutExpired(cmd="ip", timeout=5.0)],
)
def test_ip_link_never_guesses_when_it_cannot_ask(
    failure: Exception, monkeypatch: pytest.MonkeyPatch
) -> None:
    def explode(*args: object, **kwargs: object) -> object:
        raise failure

    monkeypatch.setattr("busscope.capture.shutil.which", lambda name: "/usr/bin/ip")
    monkeypatch.setattr("busscope.capture.subprocess.run", explode)
    assert IpLinkControllerMode().is_listen_only("can0") is None


def test_ip_link_returns_none_without_iproute2(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("busscope.capture.shutil.which", lambda name: None)
    assert IpLinkControllerMode().is_listen_only("can0") is None


def test_ip_link_returns_none_when_the_query_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("busscope.capture.shutil.which", lambda name: "/usr/bin/ip")
    monkeypatch.setattr(
        "busscope.capture.subprocess.run",
        lambda *a, **k: type("Completed", (), {"returncode": 1, "stdout": ""})(),
    )
    assert IpLinkControllerMode().is_listen_only("can0") is None


def test_slcan_releases_the_device_when_configuration_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A refused bitrate must not leave the serial port claimed by a half-open channel."""
    bus = FakeBus([])

    def explode(bitrate: int) -> None:
        raise ValueError("Invalid bitrate, choose one of ...")

    bus.set_bitrate = explode  # type: ignore[method-assign]
    monkeypatch.setattr(can, "Bus", lambda **kwargs: bus)
    adapter = PythonCanAdapter(controller_mode=FakeControllerMode(True))
    slcan = CaptureConfiguration(
        channel="/dev/ttyACM0",
        interface=CanInterface.SLCAN,
        allow_unverified_listen_only=True,
    )

    with pytest.raises(ValueError, match="Invalid bitrate"):
        adapter.open(slcan)

    assert bus.shutdown_called is True
    # The adapter stayed closed, so the operator can retry without restarting the app.
    bus.shutdown_called = False
    bus.set_bitrate = lambda bitrate: None  # type: ignore[method-assign]
    adapter.open(slcan)
    adapter.close()


def test_close_stays_usable_when_shutdown_raises() -> None:
    """An adapter unplugged mid-capture must not be wedged as permanently open."""

    class FailingBus(FakeBus):
        def shutdown(self) -> None:
            raise RuntimeError("device vanished")

    buses: list[FakeBus] = [FailingBus([]), FakeBus([])]
    adapter = listening(lambda configuration: buses.pop(0))

    adapter.open(CaptureConfiguration(channel="can0"))
    with pytest.raises(RuntimeError, match="device vanished"):
        adapter.close()

    # The failed shutdown must not leave the adapter believing it is still open.
    adapter.open(CaptureConfiguration(channel="can0"))
    adapter.close()


def test_slcan_refuses_until_the_unverifiable_silence_is_accepted() -> None:
    """The firmware acknowledges nothing, so silence is requested, never confirmed."""
    created: list[CaptureConfiguration] = []
    adapter = PythonCanAdapter(
        lambda configuration: created.append(configuration) or FakeBus([]),  # type: ignore[func-returns-value]
        FakeControllerMode(True),
    )
    refused = CaptureConfiguration(channel="/dev/ttyACM0", interface=CanInterface.SLCAN)

    with pytest.raises(ListenOnlyUnavailableError, match="silence cannot be confirmed"):
        adapter.open(refused)

    # Deny by default is uniform: no backend opens on an unproven mode by accident.
    assert created == []
    adapter.open(
        CaptureConfiguration(
            channel="/dev/ttyACM0",
            interface=CanInterface.SLCAN,
            allow_unverified_listen_only=True,
        )
    )
    assert len(created) == 1


def test_accepting_the_risk_never_relaxes_socketcan() -> None:
    """The acceptance covers an unverifiable backend, not a verifiable one that failed."""
    adapter = PythonCanAdapter(lambda configuration: FakeBus([]), FakeControllerMode(False))

    configuration = CaptureConfiguration(channel="can0", allow_unverified_listen_only=True)
    with pytest.raises(ListenOnlyUnavailableError, match="not in listen-only"):
        adapter.open(configuration)
