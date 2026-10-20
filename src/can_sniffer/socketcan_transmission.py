"""Linux and python-can adapters for safe manual CAN transmission."""

import json
import shutil
import subprocess
from collections.abc import Callable
from typing import Protocol

import can

from can_sniffer.transmission import CanInterfaceReadinessPort, ManualTransmission

_SEND_TIMEOUT_SECONDS = 1.0
_INSPECTION_TIMEOUT_SECONDS = 2.0


class TransmissionBus(Protocol):
    """Minimal python-can bus contract required for one send."""

    def send(self, message: can.Message, timeout: float | None = None) -> None:
        """Send one message."""

    def shutdown(self) -> None:
        """Release bus resources."""


BusFactory = Callable[[str], TransmissionBus]
InterfaceStateReader = Callable[[str], str]


class IpLinkCanInterfaceInspector:
    """Verify transmission safety from read-only Linux interface state."""

    def __init__(self, state_reader: InterfaceStateReader | None = None) -> None:
        """Inject the interface state reader; the default shells out to 'ip -json'."""
        self._state_reader = state_reader or self._read_interface_state

    def ensure_ready(self, channel: str) -> None:
        """Accept vcan or a physical CAN interface in one-shot mode."""
        try:
            document = json.loads(self._state_reader(channel))
        except json.JSONDecodeError as error:
            raise RuntimeError("cannot verify CAN controller modes") from error
        if not isinstance(document, list) or len(document) != 1:
            raise RuntimeError("cannot verify CAN controller modes")
        interface = document[0]
        if not isinstance(interface, dict) or interface.get("ifname") != channel:
            raise RuntimeError("cannot verify CAN controller modes")
        linkinfo = interface.get("linkinfo")
        if not isinstance(linkinfo, dict):
            raise RuntimeError("cannot verify CAN controller modes")
        kind = linkinfo.get("info_kind")
        if kind == "vcan":
            return
        if kind != "can":
            raise RuntimeError("cannot verify CAN controller modes")
        data = linkinfo.get("info_data")
        if not isinstance(data, dict):
            raise RuntimeError("cannot verify CAN controller modes")
        ctrlmode = data.get("ctrlmode", [])
        if not isinstance(ctrlmode, list) or not all(
            isinstance(mode, str) for mode in ctrlmode
        ):
            raise RuntimeError("cannot verify CAN controller modes")
        modes = {mode.upper() for mode in ctrlmode}
        if "LISTEN-ONLY" in modes:
            raise RuntimeError("CAN interface is in listen-only mode")
        if "ONE-SHOT" not in modes:
            raise RuntimeError("CAN interface must have one-shot mode enabled")

    @staticmethod
    def _read_interface_state(channel: str) -> str:
        """Return 'ip -details -json link show' output, failing closed when unavailable."""
        executable = shutil.which("ip")
        if executable is None:
            raise RuntimeError("ip command is required to verify CAN safety")
        try:
            result = subprocess.run(  # noqa: S603 - validated channel is one argv element.
                [executable, "-details", "-json", "link", "show", "dev", channel],
                check=True,
                capture_output=True,
                text=True,
                timeout=_INSPECTION_TIMEOUT_SECONDS,
            )
        except FileNotFoundError as error:
            raise RuntimeError("ip command is required to verify CAN safety") from error
        except subprocess.TimeoutExpired as error:
            raise RuntimeError("CAN interface safety check timed out") from error
        except subprocess.CalledProcessError as error:
            detail = error.stderr.strip() or "interface is unavailable"
            raise RuntimeError(f"cannot inspect CAN interface: {detail}") from error
        return result.stdout


class SocketCanTransmitter:
    """Send one validated Classical CAN frame through SocketCAN."""

    def __init__(
        self,
        readiness: CanInterfaceReadinessPort,
        bus_factory: BusFactory | None = None,
    ) -> None:
        """Inject the readiness check and bus factory; the default opens a real socket."""
        self._readiness = readiness
        self._bus_factory = bus_factory or self._create_bus

    def send(self, request: ManualTransmission) -> None:
        """Check safety, open a short-lived socket, and submit once."""
        self._readiness.ensure_ready(request.channel)
        message = can.Message(
            arbitration_id=request.arbitration_id,
            data=request.payload,
            is_extended_id=True,
            is_fd=False,
            is_remote_frame=False,
            is_error_frame=False,
            check=True,
        )
        bus = self._bus_factory(request.channel)
        try:
            bus.send(message, timeout=_SEND_TIMEOUT_SECONDS)
        finally:
            bus.shutdown()

    @staticmethod
    def _create_bus(channel: str) -> TransmissionBus:
        """Open a Classical CAN socket that does not loop back its own frames."""
        return can.Bus(
            interface="socketcan",
            channel=channel,
            fd=False,
            local_loopback=False,
            receive_own_messages=False,
        )
