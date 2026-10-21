import json

import pytest

from busscope.protocol_catalogue import (
    DEFAULT_CATALOGUE,
    DEFAULT_PROTOCOL_KEY,
    Availability,
    CatalogueError,
    Family,
    Protocol,
    ProtocolCatalogue,
    SubFamily,
    Transport,
)


def _catalogue(*protocols: Protocol) -> ProtocolCatalogue:
    return ProtocolCatalogue((Family("f", "F", (SubFamily("s", "S", protocols),)),))


def test_default_catalogue_has_the_four_validated_families() -> None:
    names = [family.name for family in DEFAULT_CATALOGUE.families]

    assert names == ["Fieldbus", "Serial / industrial", "EV charging", "Generic logic tap"]


def test_only_shipped_can_decoding_is_available_today() -> None:
    available = [
        p.key for p in DEFAULT_CATALOGUE.protocols() if p.availability is Availability.AVAILABLE
    ]

    assert available == [DEFAULT_PROTOCOL_KEY, "infypower"]
    assert DEFAULT_CATALOGUE.get(DEFAULT_PROTOCOL_KEY).transport is Transport.CAN


@pytest.mark.parametrize(
    ("query", "expected"),
    [("modbus", {"modbus-rtu", "modbus-tcp"}), ("  PGN ", {"j1939"}), ("homeplug", {"iso15118"})],
)
def test_search_matches_name_description_and_keywords_case_insensitively(
    query: str, expected: set[str]
) -> None:
    assert {p.key for p in DEFAULT_CATALOGUE.search(query)} == expected


def test_empty_search_returns_everything_and_unknown_returns_nothing() -> None:
    assert DEFAULT_CATALOGUE.search("") == DEFAULT_CATALOGUE.protocols()
    assert DEFAULT_CATALOGUE.search("zigbee") == ()


def test_get_unknown_key_raises_key_error() -> None:
    with pytest.raises(KeyError):
        DEFAULT_CATALOGUE.get("nope")


def test_duplicate_keys_are_rejected() -> None:
    with pytest.raises(CatalogueError, match="duplicate"):
        _catalogue(Protocol("a", "A", "", Transport.CAN), Protocol("a", "B", "", Transport.CAN))


def test_unknown_carrier_is_rejected() -> None:
    with pytest.raises(CatalogueError, match="unknown"):
        _catalogue(Protocol("a", "A", "", Transport.CAN, carried_by="ghost"))


def test_carrier_cycle_is_rejected() -> None:
    with pytest.raises(CatalogueError, match="cycle"):
        _catalogue(
            Protocol("a", "A", "", Transport.CAN, carried_by="b"),
            Protocol("b", "B", "", Transport.CAN, carried_by="a"),
        )


def test_every_default_carrier_exists() -> None:
    for protocol in DEFAULT_CATALOGUE.protocols():
        if protocol.carried_by is not None:
            assert DEFAULT_CATALOGUE.get(protocol.carried_by)


def test_to_dict_is_json_serialisable_and_keeps_the_tree() -> None:
    data = DEFAULT_CATALOGUE.to_dict()
    round_trip = json.loads(json.dumps(data))

    can_sub = round_trip["families"][0]["subFamilies"][0]
    j1939 = next(p for p in can_sub["protocols"] if p["key"] == "j1939")
    assert j1939 == {
        "key": "j1939",
        "name": "SAE J1939",
        "description": "Vehicle network PGN/SPN layer.",
        "transport": "can",
        "availability": "planned",
        "carriedBy": DEFAULT_PROTOCOL_KEY,
        "keywords": ["pgn", "spn"],
    }
