"""Framework-independent contracts for safe manual CAN transmission."""

import re
from dataclasses import dataclass
from typing import Protocol, Self

MAX_EXTENDED_IDENTIFIER = 0x1FFFFFFF
_CHANNEL_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,14}")
_BYTE_PATTERN = re.compile(r"[0-9A-Fa-f]{2}")


@dataclass(frozen=True, slots=True)
class ManualTransmission:
    """One validated immutable Infypower transmission request."""

    channel: str
    arbitration_id: int
    payload: bytes

    def __post_init__(self) -> None:
        """Reject malformed requests so nothing invalid reaches the bus."""
        if _CHANNEL_PATTERN.fullmatch(self.channel) is None:
            raise ValueError("CAN channel must be a valid Linux interface name")
        if not 0 <= self.arbitration_id <= MAX_EXTENDED_IDENTIFIER:
            raise ValueError("CAN identifier must be between 0x00000000 and 0x1FFFFFFF")
        if not isinstance(self.payload, bytes) or len(self.payload) != 8:
            raise ValueError("CAN payload must contain exactly 8 bytes")

    @classmethod
    def from_text(cls, channel: str, identifier: str, payload: str) -> Self:
        """Parse strict operator input into a validated request."""
        normalized_identifier = identifier.strip()
        if normalized_identifier.lower().startswith("0x"):
            normalized_identifier = normalized_identifier[2:]
        if (
            not normalized_identifier
            or re.fullmatch(r"[0-9A-Fa-f]+", normalized_identifier) is None
        ):
            raise ValueError("CAN identifier must be hexadecimal")

        tokens = payload.split()
        if len(tokens) != 8:
            raise ValueError("CAN payload must contain exactly 8 bytes")
        if any(_BYTE_PATTERN.fullmatch(token) is None for token in tokens):
            raise ValueError("Each CAN payload byte must be two hexadecimal digits")

        return cls(
            channel=channel.strip(),
            arbitration_id=int(normalized_identifier, 16),
            payload=bytes(int(token, 16) for token in tokens),
        )

    @property
    def identifier_hex(self) -> str:
        """Return the identifier in stable eight-digit extended form."""
        return f"0x{self.arbitration_id:08X}"

    @property
    def payload_hex(self) -> str:
        """Return the payload as stable uppercase byte tokens."""
        return self.payload.hex(" ").upper()


class CanTransmissionPort(Protocol):
    """Application-facing contract for one manual CAN send."""

    def send(self, request: ManualTransmission) -> None:
        """Submit one validated transmission request."""


class CanInterfaceReadinessPort(Protocol):
    """Safety contract checked immediately before a CAN send."""

    def ensure_ready(self, channel: str) -> None:
        """Raise when the interface cannot guarantee one physical attempt."""
