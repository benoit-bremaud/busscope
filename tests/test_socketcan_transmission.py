import shutil
import subprocess

import can
import pytest

from busscope.socketcan_transmission import (
    IpLinkCanInterfaceInspector,
    SocketCanTransmitter,
)
from busscope.transmission import ManualTransmission


class FakeReadiness:
    def __init__(self, error: Exception | None = None) -> None:
        self.channels: list[str] = []
        self.error = error

    def ensure_ready(self, channel: str) -> None:
        self.channels.append(channel)
        if self.error is not None:
            raise self.error


class FakeBus:
    def __init__(self, error: Exception | None = None) -> None:
        self.calls: list[tuple[can.Message, float | None]] = []
        self.shutdown_called = False
        self.error = error

    def send(self, message: can.Message, timeout: float | None = None) -> None:
        self.calls.append((message, timeout))
        if self.error is not None:
            raise self.error

    def shutdown(self) -> None:
        self.shutdown_called = True


def request() -> ManualTransmission:
    return ManualTransmission("can0", 0x1ABCDE, bytes.fromhex("01 02 03 04 05 06 07 08"))


@pytest.mark.parametrize(
    "state",
    [
        '[{"ifname":"can0","linkinfo":{"info_kind":"vcan"}}]',
        '[{"ifname":"can0","linkinfo":{"info_kind":"can",'
        '"info_data":{"ctrlmode":["ONE-SHOT"]}}}]',
    ],
)
def test_inspector_accepts_safe_interfaces(state: str) -> None:
    IpLinkCanInterfaceInspector(lambda channel: state).ensure_ready("can0")


@pytest.mark.parametrize(
    ("state", "message"),
    [
        (
            '[{"ifname":"can0","linkinfo":{"info_kind":"can",'
            '"info_data":{"ctrlmode":["ONE-SHOT","LISTEN-ONLY"]}}}]',
            "listen-only",
        ),
        (
            '[{"ifname":"can0","linkinfo":{"info_kind":"can",'
            '"info_data":{"ctrlmode":["BERR-REPORTING"]}}}]',
            "one-shot",
        ),
        ('[{"ifname":"can0","linkinfo":{"info_kind":"dummy"}}]', "cannot verify"),
        ("not json", "cannot verify"),
        ("[]", "cannot verify"),
        ('[{"ifname":"other","linkinfo":{"info_kind":"vcan"}}]', "cannot verify"),
        ('[{"ifname":"can0"}]', "cannot verify"),
        (
            '[{"ifname":"can0","linkinfo":{"info_kind":"can"}}]',
            "cannot verify",
        ),
        (
            '[{"ifname":"can0","linkinfo":{"info_kind":"can",'
            '"info_data":{"ctrlmode":"ONE-SHOT"}}}]',
            "cannot verify",
        ),
    ],
)
def test_inspector_rejects_unsafe_or_unknown_state(state: str, message: str) -> None:
    with pytest.raises(RuntimeError, match=message):
        IpLinkCanInterfaceInspector(lambda channel: state).ensure_ready("can0")


def test_transmitter_checks_readiness_before_opening_bus() -> None:
    readiness = FakeReadiness(RuntimeError("unsafe"))
    opened = False

    def open_bus(channel: str) -> FakeBus:
        nonlocal opened
        opened = True
        return FakeBus()

    transmitter = SocketCanTransmitter(readiness, open_bus)

    with pytest.raises(RuntimeError, match="unsafe"):
        transmitter.send(request())

    assert readiness.channels == ["can0"]
    assert opened is False


def test_transmitter_builds_one_classical_extended_frame_and_closes() -> None:
    readiness = FakeReadiness()
    bus = FakeBus()
    transmitter = SocketCanTransmitter(readiness, lambda channel: bus)

    transmitter.send(request())

    assert len(bus.calls) == 1
    message, timeout = bus.calls[0]
    assert message.arbitration_id == 0x1ABCDE
    assert bytes(message.data) == bytes.fromhex("01 02 03 04 05 06 07 08")
    assert message.is_extended_id is True
    assert message.is_fd is False
    assert message.is_remote_frame is False
    assert message.is_error_frame is False
    assert timeout == 1.0
    assert bus.shutdown_called is True


def test_transmitter_closes_bus_when_send_fails() -> None:
    bus = FakeBus(OSError("send failed"))
    transmitter = SocketCanTransmitter(FakeReadiness(), lambda channel: bus)

    with pytest.raises(OSError, match="send failed"):
        transmitter.send(request())

    assert len(bus.calls) == 1
    assert bus.shutdown_called is True


def test_transmitter_does_not_retry_when_bus_open_fails() -> None:
    attempts = 0

    def fail_to_open(channel: str) -> FakeBus:
        nonlocal attempts
        del channel
        attempts += 1
        raise OSError("open failed")

    transmitter = SocketCanTransmitter(FakeReadiness(), fail_to_open)

    with pytest.raises(OSError, match="open failed"):
        transmitter.send(request())

    assert attempts == 1


def test_default_bus_factory_disables_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []
    bus = FakeBus()

    def fake_bus(**kwargs: object) -> FakeBus:
        calls.append(kwargs)
        return bus

    monkeypatch.setattr(can, "Bus", fake_bus)
    SocketCanTransmitter(FakeReadiness()).send(request())

    assert calls == [
        {
            "interface": "socketcan",
            "channel": "can0",
            "fd": False,
            "local_loopback": False,
            "receive_own_messages": False,
        }
    ]


@pytest.mark.parametrize(
    ("error", "message"),
    [
        (FileNotFoundError(), "ip command"),
        (subprocess.TimeoutExpired("ip", 2), "timed out"),
        (
            subprocess.CalledProcessError(1, ["ip"], stderr="device missing"),
            "device missing",
        ),
    ],
)
def test_default_inspector_reports_command_failures(
    monkeypatch: pytest.MonkeyPatch, error: Exception, message: str
) -> None:
    def fail(*args: object, **kwargs: object) -> None:
        raise error

    monkeypatch.setattr(subprocess, "run", fail)

    with pytest.raises(RuntimeError, match=message):
        IpLinkCanInterfaceInspector().ensure_ready("can0")


def test_default_inspector_reports_missing_ip_command(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(shutil, "which", lambda command: None)

    with pytest.raises(RuntimeError, match="ip command"):
        IpLinkCanInterfaceInspector().ensure_ready("can0")


def test_default_inspector_reads_ip_details(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[list[str], dict[str, object]]] = []

    def run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append((command, kwargs))
        return subprocess.CompletedProcess(
            command,
            0,
            '[{"ifname":"vcan0","linkinfo":{"info_kind":"vcan"}}]',
            "",
        )

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(shutil, "which", lambda command: "/usr/sbin/ip")
    IpLinkCanInterfaceInspector().ensure_ready("vcan0")

    assert calls[0][0] == [
        "/usr/sbin/ip",
        "-details",
        "-json",
        "link",
        "show",
        "dev",
        "vcan0",
    ]
    assert calls[0][1]["check"] is True
    assert calls[0][1]["timeout"] == 2.0
