import json

import pytest

from busscope.protocol_catalogue import (
    DEFAULT_CATALOGUE,
    DEFAULT_PROTOCOL_KEY,
    Availability,
    CatalogueError,
    Feature,
    Group,
    Protocol,
    ProtocolCatalogue,
    Transport,
)

_ALL_FEATURES = frozenset(Feature)


def _catalogue(*protocols: Protocol) -> ProtocolCatalogue:
    return ProtocolCatalogue(Group("root", "Root", (Group("f", "F", protocols),)))


def _available(key: str, removes: frozenset[Feature] = frozenset()) -> Protocol:
    return Protocol(key, key.upper(), "", Transport.CAN, Availability.AVAILABLE, removes=removes)


def test_default_catalogue_has_the_four_validated_families() -> None:
    names = [node.name for node in DEFAULT_CATALOGUE.root.children]

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

    can_group = round_trip["root"]["children"][0]["children"][0]
    assert can_group["adds"] == ["can-backend", "can-channel", "can-filter"]
    j1939 = next(p for p in can_group["children"] if p["key"] == "j1939")
    assert j1939 == {
        "key": "j1939",
        "name": "SAE J1939",
        "adds": [],
        "removes": [],
        "description": "Vehicle network PGN/SPN layer.",
        "transport": "can",
        "availability": "planned",
        "carriedBy": DEFAULT_PROTOCOL_KEY,
        "keywords": ["pgn", "spn"],
    }


def test_available_can_protocol_inherits_root_and_can_features() -> None:
    assert DEFAULT_CATALOGUE.features("infypower") == _ALL_FEATURES
    assert [node.key for node in DEFAULT_CATALOGUE.path("infypower")] == [
        "all",
        "fieldbus",
        "can",
        "infypower",
    ]


def test_planned_protocol_resolves_no_feature() -> None:
    assert DEFAULT_CATALOGUE.features("j1939") == frozenset()


def test_features_fold_over_arbitrary_depth_with_add_and_remove() -> None:
    leaf = _available("leaf", removes=frozenset({Feature.STATISTICS}))
    deep = Group(
        "a",
        "A",
        (Group("b", "B", (Group("c", "C", (leaf,), adds=frozenset({Feature.CAN_FILTER})),)),),
        adds=frozenset({Feature.LIVE_SOURCE, Feature.STATISTICS}),
    )
    catalogue = ProtocolCatalogue(Group("root", "Root", (deep,)))

    assert catalogue.features("leaf") == {Feature.LIVE_SOURCE, Feature.CAN_FILTER}
    assert len(catalogue.path("leaf")) == 5


def test_removing_a_feature_not_inherited_is_rejected() -> None:
    with pytest.raises(CatalogueError, match="does not inherit"):
        _catalogue(_available("a", removes=frozenset({Feature.STATISTICS})))


def test_empty_group_is_rejected() -> None:
    with pytest.raises(CatalogueError, match="empty group"):
        ProtocolCatalogue(Group("root", "Root", (Group("g", "G", ()),)))


def test_group_and_protocol_keys_share_one_namespace() -> None:
    with pytest.raises(CatalogueError, match="duplicate"):
        _catalogue(_available("f"))


def test_unknown_key_has_no_path_or_features() -> None:
    with pytest.raises(KeyError):
        DEFAULT_CATALOGUE.path("nope")
    with pytest.raises(KeyError):
        DEFAULT_CATALOGUE.features("nope")
