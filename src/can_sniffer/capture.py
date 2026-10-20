"""Hardware boundary for read-only CAN capture."""

from __future__ import annotations

import json
import shutil
import subprocess
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol, cast

import can

from can_sniffer.protocol import CanFrame

_IP_TIMEOUT_SECONDS = 5.0


class CanInterface(StrEnum):
    """python-can backend used to reach the adapter."""

    SOCKETCAN = "socketcan"
    SLCAN = "slcan"


class ListenOnlyUnavailableError(RuntimeError):
    """Raised when listen-only operation cannot be guaranteed for a channel.

    Distinct from a missing device or a malformed channel: it means the capture was
    refused rather than attempted, because the adapter might otherwise acknowledge.
    """


@dataclass(frozen=True, slots=True)
class CaptureConfiguration:
    """Runtime settings required to open a CAN capture."""

    channel: str
    bitrate: int = 125_000
    listen_only: bool = True
    interface: CanInterface = CanInterface.SOCKETCAN
    #: Accept a silent mode that was requested but cannot be confirmed. Required by the
    #: slcan backend, whose firmware acknowledges no command, so the adapter has no way
    #: to tell a listening device from an acknowledging one. Isolated benches only.
    allow_unverified_listen_only: bool = False


class CanCapturePort(Protocol):
    """Application-facing contract for a CAN frame source."""

    def open(self, configuration: CaptureConfiguration) -> None:
        """Open the capture source."""

    def receive(self, timeout: float | None = None) -> CanFrame | None:
        """Receive one frame, or return None after a timeout."""

    def close(self) -> None:
        """Close the capture source."""


class ControllerModePort(Protocol):
    """Reports the controller mode of an interface configured out of band."""

    def is_listen_only(self, channel: str) -> bool | None:
        """True/False when the mode is known, None when it cannot be determined."""


class CanBus(Protocol):
    """Minimal bus contract required by the python-can adapter."""

    def recv(self, timeout: float | None = None) -> can.Message | None:
        """Receive one python-can message, or return None after a timeout."""

    def shutdown(self) -> None:
        """Release the underlying CAN bus resources."""


BusFactory = Callable[[CaptureConfiguration], CanBus]


class SlcanChannel(Protocol):
    """The one method the adapter needs beyond the bus contract."""

    def set_bitrate(self, bitrate: int) -> None:
        """Close the channel, write the bitrate, reopen. Order matters to the firmware."""


def _parse_listen_only(payload: str, channel: str) -> bool | None:
    """Read the controller mode out of `ip -json` output, refusing anything ambiguous."""
    try:
        links = json.loads(payload)
    except json.JSONDecodeError:
        return None
    # `dev <name>` cannot match a filter keyword, so exactly one link is expected.
    if not isinstance(links, list) or len(links) != 1 or not isinstance(links[0], dict):
        return None
    # Name it explicitly rather than trusting the query to have filtered: this mirrors
    # the check the transmission inspector already performs on the same output.
    if links[0].get("ifname") != channel:
        return None
    info = links[0].get("linkinfo")
    if not isinstance(info, dict) or info.get("info_kind") != "can":
        return None
    data = info.get("info_data")
    if not isinstance(data, dict):
        return None
    modes = data.get("ctrlmode")
    if not isinstance(modes, list):
        return False
    return any(str(mode).lower() == "listen-only" for mode in modes)


class IpLinkControllerMode:
    """Read the controller mode from iproute2.

    SocketCAN exposes the mode nowhere in the python-can API, so this runs `ip`. It is
    the only reason the port exists: keeping the subprocess out of the application.
    """

    def is_listen_only(self, channel: str) -> bool | None:
        """Return None whenever the answer is not unambiguous, never a guess."""
        executable = shutil.which("ip")
        if executable is None:
            return None
        try:
            completed = subprocess.run(  # noqa: S603 - fixed executable, no shell
                # `dev` pins the argument into the device slot: without it a value like
                # "up" or "type" is read as a filter and lists every interface on the
                # host. `-json` is parsed, never grepped — the flag name also appears in
                # a link alias, which a substring test would accept as confirmation.
                [executable, "-details", "-json", "link", "show", "dev", channel],
                capture_output=True,
                text=True,
                timeout=_IP_TIMEOUT_SECONDS,
                check=False,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if completed.returncode != 0:
            return None
        return _parse_listen_only(completed.stdout, channel)


class PythonCanAdapter:
    """Translate python-can messages into hardware-independent domain frames.

    One adapter serves every backend: only bus creation varies, while translation and
    the open/receive/close lifecycle are identical.
    """

    def __init__(
        self,
        bus_factory: BusFactory | None = None,
        controller_mode: ControllerModePort | None = None,
    ) -> None:
        """Inject the bus factory and controller-mode probe; defaults talk to real hardware."""
        self._bus_factory = bus_factory or self._create_bus
        self._controller_mode = controller_mode or IpLinkControllerMode()
        self._bus: CanBus | None = None

    def open(self, configuration: CaptureConfiguration) -> None:
        """Open the configured backend, refusing anything that may acknowledge."""
        if not configuration.channel:
            raise ValueError("CAN channel must not be empty")
        if configuration.bitrate <= 0:
            raise ValueError("CAN bitrate must be positive")
        if not configuration.listen_only:
            raise ValueError("listen-only mode is mandatory")
        if self._bus is not None:
            raise RuntimeError("CAN adapter is already open")
        if configuration.interface is CanInterface.SLCAN:
            self._require_accepted_risk(configuration)
        else:
            # Deny by default: a future backend is guarded rather than silently exempt.
            self._require_listen_only(configuration.channel)
        self._bus = self._bus_factory(configuration)

    def _require_listen_only(self, channel: str) -> None:
        """Fail closed: python-can cannot set this mode on socketcan, only observe it."""
        confirmed = self._controller_mode.is_listen_only(channel)
        # Identity, not truthiness: an injected port returning 1 or "unknown" is not a
        # confirmation, and this is the single gate protecting the invariant.
        if confirmed is True:
            return
        detail = (
            "it is not in listen-only mode"
            if confirmed is False
            else "its mode could not be determined"
        )
        raise ListenOnlyUnavailableError(
            f"refusing to capture on {channel!r} because {detail}; "
            f"the socketcan backend cannot set listen-only, so configure the interface "
            f"out of band (ip link set {channel} type can listen-only on) or select the "
            f"slcan backend, which applies it directly"
        )

    @staticmethod
    def _require_accepted_risk(configuration: CaptureConfiguration) -> None:
        """slcan requests listen-only but cannot prove it, so the operator must accept it.

        The adapter writes `L` and the device answers nothing: docs/hardware/canable-2.0.md
        records that this firmware's published command list does not even guarantee the
        command, and that a created interface is no proof of electrical silence. Refusing
        by default keeps one rule for every backend — nothing captures unverified unless
        somebody said so on purpose.
        """
        if configuration.allow_unverified_listen_only:
            return
        raise ListenOnlyUnavailableError(
            f"refusing to capture on {configuration.channel!r}: the slcan backend requests "
            f"listen-only but the adapter acknowledges no command, so silence cannot be "
            f"confirmed. Set allow_unverified_listen_only for an isolated bench, or install "
            f"firmware exposing a native CAN interface before connecting to a live bus"
        )

    def receive(self, timeout: float | None = None) -> CanFrame | None:
        """Receive one message while preserving error-frame metadata."""
        if self._bus is None:
            raise RuntimeError("CAN adapter is not open")
        message = self._bus.recv(timeout)
        if message is None:
            return None
        return CanFrame(
            arbitration_id=message.arbitration_id,
            data=bytes(message.data),
            is_extended_id=message.is_extended_id,
            is_error_frame=message.is_error_frame,
        )

    def close(self) -> None:
        """Shutdown the bus and make the adapter reusable."""
        # Drop the reference first: a shutdown that raises must not leave the adapter
        # believing it is still open, which would reject every later start.
        bus, self._bus = self._bus, None
        if bus is not None:
            bus.shutdown()

    @staticmethod
    def _create_bus(configuration: CaptureConfiguration) -> CanBus:
        """Open the python-can bus for the configured backend, honouring listen-only."""
        if configuration.interface is CanInterface.SLCAN:
            bus = can.Bus(
                interface="slcan",
                channel=configuration.channel,
                listen_only=configuration.listen_only,
            )
            # set_bitrate closes, writes S<n>, then reopens. That order is required:
            # the firmware ignores a bitrate command on an open channel, so a channel
            # left open by a previous client would otherwise keep its old bitrate --
            # silently, which is exactly the failure this backend exists to avoid.
            # The cast records that python-can types the factory as BusABC while the
            # slcan bus really does expose set_bitrate.
            try:
                cast(SlcanChannel, bus).set_bitrate(configuration.bitrate)
            except BaseException:
                # The constructor already claimed the serial port and open() has not
                # stored the bus yet, so nothing else would ever release it.
                bus.shutdown()
                raise
            return bus
        # socketcan takes neither bitrate nor listen_only; both are set out of band.
        return can.Bus(
            interface="socketcan",
            channel=configuration.channel,
            fd=False,
        )


def receive_frames(port: CanCapturePort, timeout: float | None = None) -> Iterator[CanFrame]:
    """Yield frames until the port returns a timeout result."""
    while True:
        frame = port.receive(timeout)
        if frame is None:
            return
        yield frame
