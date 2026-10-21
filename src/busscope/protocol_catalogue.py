"""Qt-free catalogue of the protocols BusScope can (or plans to) listen to.

Protocols are leaves of a domain tree of arbitrary depth (domain -> sub-domain -> ...). Each
node declares the features it grants; descendants inherit them and only add or remove.
The catalogue is plain immutable data, exported as a dict for the future React UI.
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


class Feature(Enum):
    """A capability a catalogue node grants to its descendants (setting or action)."""

    LIVE_SOURCE = "live-source"
    REPLAY_SOURCE = "replay-source"
    CAN_BACKEND = "can-backend"
    CAN_CHANNEL = "can-channel"
    CAN_FILTER = "can-filter"
    STATISTICS = "statistics"


@dataclass(frozen=True)
class Protocol:
    """Selectable leaf of the tree; ``carried_by`` names the protocol it stacks on."""

    key: str
    name: str
    description: str
    transport: Transport
    availability: Availability = Availability.PLANNED
    carried_by: str | None = None
    keywords: tuple[str, ...] = ()
    adds: frozenset[Feature] = frozenset()
    removes: frozenset[Feature] = frozenset()

    def matches(self, text: str) -> bool:
        """Return whether ``text`` occurs in the name, description or keywords."""
        needle = text.strip().casefold()
        if not needle:
            return True
        haystack = (self.name, self.description, *self.keywords)
        return any(needle in value.casefold() for value in haystack)


@dataclass(frozen=True)
class Group:
    """Domain node of arbitrary depth; descendants inherit its features."""

    key: str
    name: str
    children: tuple[Group | Protocol, ...]
    adds: frozenset[Feature] = frozenset()
    removes: frozenset[Feature] = frozenset()


Node = Group | Protocol


class CatalogueError(ValueError):
    """Raised when the catalogue data breaks one of its invariants."""


@dataclass(frozen=True)
class ProtocolCatalogue:
    """Validated, searchable domain tree whose features are inherited downwards."""

    root: Group
    _by_key: dict[str, Protocol] = field(init=False, repr=False, compare=False)
    _paths: dict[str, tuple[Node, ...]] = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        """Index the tree and enforce its invariants (see the class diagram)."""
        paths: dict[str, tuple[Node, ...]] = {}
        _index(self.root, (), paths)
        by_key = {key: path[-1] for key, path in paths.items() if isinstance(path[-1], Protocol)}
        for protocol in by_key.values():
            _check_carrier_chain(protocol, by_key)
        object.__setattr__(self, "_by_key", by_key)
        object.__setattr__(self, "_paths", paths)

    def protocols(self) -> tuple[Protocol, ...]:
        """Return every protocol in catalogue order."""
        return tuple(self._by_key.values())

    def get(self, key: str) -> Protocol:
        """Return the protocol with ``key``; raise ``KeyError`` when unknown."""
        return self._by_key[key]

    def path(self, key: str) -> tuple[Node, ...]:
        """Return the nodes from the root down to ``key``; raise ``KeyError`` when unknown."""
        return self._paths[key]

    def features(self, key: str) -> frozenset[Feature]:
        """Resolve the features of protocol ``key`` by folding its path from the root.

        A planned protocol cannot be captured yet, so it resolves to no feature at all.
        """
        protocol = self.get(key)
        if protocol.availability is not Availability.AVAILABLE:
            return frozenset()
        return _fold(self.path(key))

    def search(self, text: str) -> tuple[Protocol, ...]:
        """Return protocols matching ``text``; an empty query returns all of them."""
        return tuple(protocol for protocol in self.protocols() if protocol.matches(text))

    def to_dict(self) -> dict[str, object]:
        """Export the tree as JSON-compatible data for non-Python front ends."""
        return {"root": _node_dict(self.root)}


def _index(node: Node, parents: tuple[Node, ...], paths: dict[str, tuple[Node, ...]]) -> None:
    if node.key in paths:
        raise CatalogueError(f"duplicate key: {node.key}")
    path = (*parents, node)
    paths[node.key] = path
    inherited = _fold(parents)
    if node.removes - inherited:
        raise CatalogueError(f"{node.key} removes a feature it does not inherit")
    if isinstance(node, Group):
        if not node.children:
            raise CatalogueError(f"empty group: {node.key}")
        for child in node.children:
            _index(child, path, paths)


def _fold(nodes: tuple[Node, ...]) -> frozenset[Feature]:
    """Apply each node's additions then removals, from the root downwards."""
    resolved: frozenset[Feature] = frozenset()
    for node in nodes:
        resolved = (resolved | node.adds) - node.removes
    return resolved


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


def _features_list(features: frozenset[Feature]) -> list[str]:
    return sorted(feature.value for feature in features)


def _node_dict(node: Node) -> dict[str, object]:
    common: dict[str, object] = {
        "key": node.key,
        "name": node.name,
        "adds": _features_list(node.adds),
        "removes": _features_list(node.removes),
    }
    if isinstance(node, Group):
        return {**common, "children": [_node_dict(child) for child in node.children]}
    return {
        **common,
        "description": node.description,
        "transport": node.transport.value,
        "availability": node.availability.value,
        "carriedBy": node.carried_by,
        "keywords": list(node.keywords),
    }


_CAN, _SERIAL, _ETH = Transport.CAN, Transport.SERIAL, Transport.ETHERNET

DEFAULT_PROTOCOL_KEY = "can-2.0b"

# Shared by every CAN protocol, so declared once on the CAN group.
_CAN_FEATURES = frozenset({Feature.CAN_BACKEND, Feature.CAN_CHANNEL, Feature.CAN_FILTER})

DEFAULT_CATALOGUE = ProtocolCatalogue(
    Group(
        "all",
        "All protocols",
        (
            Group(
                "fieldbus",
                "Fieldbus",
                (
                    Group(
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
                                Availability.AVAILABLE,
                                carried_by=DEFAULT_PROTOCOL_KEY,
                                keywords=("charger", "rectifier"),
                            ),
                        ),
                        adds=_CAN_FEATURES,
                    ),
                ),
            ),
            Group(
                "serial-industrial",
                "Serial / industrial",
                (
                    Group(
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
                    Group(
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
            Group(
                "ev-charging",
                "EV charging",
                (
                    Group(
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
                    Group(
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
                                # Filed under EV charging, so the CAN group cannot grant these.
                                adds=_CAN_FEATURES,
                            ),
                        ),
                    ),
                    Group(
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
            Group(
                "logic-tap",
                "Generic logic tap",
                (
                    Group(
                        "serial-buses",
                        "Serial buses",
                        (
                            Protocol("uart", "UART", "Asynchronous serial.", Transport.LOGIC),
                            Protocol("spi", "SPI", "Serial peripheral interface.", Transport.LOGIC),
                            Protocol(
                                "i2c", "I²C", "Two-wire bus.", Transport.LOGIC, keywords=("i2c",)
                            ),
                        ),
                    ),
                ),
            ),
        ),
        adds=frozenset({Feature.LIVE_SOURCE, Feature.REPLAY_SOURCE, Feature.STATISTICS}),
    )
)
