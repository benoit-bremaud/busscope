"""Qt-free catalogue of the protocols BusScope can (or plans to) listen to.

Protocols are grouped as families -> sub-families -> protocols so the operator can find what
to test. The catalogue is plain immutable data, exported as a dict for the future React UI.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Transport(Enum):
    """Physical carrier of a protocol; it decides which capture settings apply."""

    CAN = "can"
    SERIAL = "serial"
    ETHERNET = "ethernet"
    CONTROL_PILOT = "control-pilot"
    POWERLINE = "powerline"
    LOGIC = "logic"


class Availability(Enum):
    """Whether the protocol can be captured today or is only on the roadmap."""

    AVAILABLE = "available"
    PLANNED = "planned"


@dataclass(frozen=True)
class Protocol:
    """One selectable protocol; ``carried_by`` names the protocol it stacks on."""

    key: str
    name: str
    description: str
    transport: Transport
    availability: Availability = Availability.PLANNED
    carried_by: str | None = None
    keywords: tuple[str, ...] = ()

    def matches(self, text: str) -> bool:
        """Return whether ``text`` occurs in the name, description or keywords."""
        needle = text.strip().casefold()
        if not needle:
            return True
        haystack = (self.name, self.description, *self.keywords)
        return any(needle in value.casefold() for value in haystack)


@dataclass(frozen=True)
class SubFamily:
    """A group of related protocols inside a family."""

    key: str
    name: str
    protocols: tuple[Protocol, ...]


@dataclass(frozen=True)
class Family:
    """Top-level group of the catalogue."""

    key: str
    name: str
    sub_families: tuple[SubFamily, ...]


class CatalogueError(ValueError):
    """Raised when the catalogue data breaks one of its invariants."""


@dataclass(frozen=True)
class ProtocolCatalogue:
    """Validated, searchable family / sub-family / protocol tree."""

    families: tuple[Family, ...]
    _by_key: dict[str, Protocol] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Index protocols and enforce unique keys and a valid ``carried_by`` chain."""
        by_key: dict[str, Protocol] = {}
        for protocol in self.protocols():
            if protocol.key in by_key:
                raise CatalogueError(f"duplicate protocol key: {protocol.key}")
            by_key[protocol.key] = protocol
        for protocol in by_key.values():
            _check_carrier_chain(protocol, by_key)
        object.__setattr__(self, "_by_key", by_key)

    def protocols(self) -> tuple[Protocol, ...]:
        """Return every protocol in catalogue order."""
        return tuple(
            protocol
            for family in self.families
            for sub_family in family.sub_families
            for protocol in sub_family.protocols
        )

    def get(self, key: str) -> Protocol:
        """Return the protocol with ``key``; raise ``KeyError`` when unknown."""
        return self._by_key[key]

    def search(self, text: str) -> tuple[Protocol, ...]:
        """Return protocols matching ``text``; an empty query returns all of them."""
        return tuple(protocol for protocol in self.protocols() if protocol.matches(text))

    def to_dict(self) -> dict[str, object]:
        """Export the tree as JSON-compatible data for non-Python front ends."""
        return {
            "families": [
                {
                    "key": family.key,
                    "name": family.name,
                    "subFamilies": [
                        {
                            "key": sub.key,
                            "name": sub.name,
                            "protocols": [_protocol_dict(p) for p in sub.protocols],
                        }
                        for sub in family.sub_families
                    ],
                }
                for family in self.families
            ]
        }


def _check_carrier_chain(protocol: Protocol, by_key: dict[str, Protocol]) -> None:
    seen = {protocol.key}
    carrier = protocol.carried_by
    while carrier is not None:
        if carrier not in by_key:
            raise CatalogueError(f"{protocol.key} is carried by unknown {carrier}")
        if carrier in seen:
            raise CatalogueError(f"carrier cycle through {protocol.key}")
        seen.add(carrier)
        carrier = by_key[carrier].carried_by


def _protocol_dict(protocol: Protocol) -> dict[str, object]:
    return {
        "key": protocol.key,
        "name": protocol.name,
        "description": protocol.description,
        "transport": protocol.transport.value,
        "availability": protocol.availability.value,
        "carriedBy": protocol.carried_by,
        "keywords": list(protocol.keywords),
    }


_CAN, _SERIAL, _ETH = Transport.CAN, Transport.SERIAL, Transport.ETHERNET

DEFAULT_PROTOCOL_KEY = "can-2.0b"

DEFAULT_CATALOGUE = ProtocolCatalogue(
    families=(
        Family(
            "fieldbus",
            "Fieldbus",
            (
                SubFamily(
                    "can",
                    "CAN",
                    (
                        Protocol("can-2.0a", "CAN 2.0A", "Standard 11-bit identifiers.", _CAN),
                        Protocol(
                            DEFAULT_PROTOCOL_KEY,
                            "CAN 2.0B",
                            "Extended 29-bit identifiers, listen-only capture.",
                            _CAN,
                            Availability.AVAILABLE,
                            keywords=("extended", "29-bit"),
                        ),
                        Protocol("can-fd", "CAN FD", "Flexible data-rate CAN.", _CAN),
                        Protocol(
                            "j1939",
                            "SAE J1939",
                            "Vehicle network PGN/SPN layer.",
                            _CAN,
                            carried_by=DEFAULT_PROTOCOL_KEY,
                            keywords=("pgn", "spn"),
                        ),
                        Protocol(
                            "canopen",
                            "CANopen",
                            "PDO/SDO object dictionary protocol.",
                            _CAN,
                            carried_by="can-2.0a",
                            keywords=("pdo", "sdo"),
                        ),
                        Protocol(
                            "infypower",
                            "Infypower module",
                            "Infypower power-module status and measurements.",
                            _CAN,
                            carried_by=DEFAULT_PROTOCOL_KEY,
                            keywords=("charger", "rectifier"),
                        ),
                    ),
                ),
            ),
        ),
        Family(
            "serial-industrial",
            "Serial / industrial",
            (
                SubFamily(
                    "rs485",
                    "RS-485",
                    (
                        Protocol("rs485-raw", "RS-485 raw", "Undecoded RS-485 bytes.", _SERIAL),
                        Protocol(
                            "modbus-rtu",
                            "Modbus RTU",
                            "Modbus over a serial line.",
                            _SERIAL,
                            carried_by="rs485-raw",
                            keywords=("register", "meter"),
                        ),
                    ),
                ),
                SubFamily(
                    "industrial-ethernet",
                    "Industrial Ethernet",
                    (
                        Protocol(
                            "modbus-tcp",
                            "Modbus TCP",
                            "Modbus over TCP/IP.",
                            _ETH,
                            keywords=("register",),
                        ),
                    ),
                ),
            ),
        ),
        Family(
            "ev-charging",
            "EV charging",
            (
                SubFamily(
                    "basic-signalling",
                    "Basic signalling",
                    (
                        Protocol(
                            "iec61851",
                            "IEC 61851 CP/PP",
                            "Control Pilot PWM and Proximity Pilot states.",
                            Transport.CONTROL_PILOT,
                            keywords=("pwm", "control pilot", "proximity"),
                        ),
                    ),
                ),
                SubFamily(
                    "high-level",
                    "High-level communication",
                    (
                        Protocol(
                            "iso15118",
                            "ISO 15118-2/-20",
                            "Vehicle-to-charger messages over HomePlug Green PHY.",
                            Transport.POWERLINE,
                            keywords=("plc", "homeplug", "v2g"),
                        ),
                        Protocol(
                            "chademo",
                            "CHAdeMO",
                            "DC charging dialogue over CAN.",
                            _CAN,
                            carried_by=DEFAULT_PROTOCOL_KEY,
                        ),
                    ),
                ),
                SubFamily(
                    "backend",
                    "Back-end",
                    (
                        Protocol(
                            "ocpp",
                            "OCPP 1.6/2.0.1",
                            "Charger-to-CSMS WebSocket protocol.",
                            _ETH,
                            keywords=("websocket", "csms"),
                        ),
                    ),
                ),
            ),
        ),
        Family(
            "logic-tap",
            "Generic logic tap",
            (
                SubFamily(
                    "serial-buses",
                    "Serial buses",
                    (
                        Protocol("uart", "UART", "Asynchronous serial.", Transport.LOGIC),
                        Protocol("spi", "SPI", "Serial peripheral interface.", Transport.LOGIC),
                        Protocol("i2c", "I²C", "Two-wire bus.", Transport.LOGIC, keywords=("i2c",)),
                    ),
                ),
            ),
        ),
    )
)
