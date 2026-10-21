import pytest
from PySide6.QtWidgets import QApplication, QTreeWidgetItem

from busscope.protocol_catalogue import (
    Availability,
    Group,
    Protocol,
    ProtocolCatalogue,
    Transport,
)
from busscope.protocol_selector import ProtocolSelector

_CAN = Protocol("can", "CAN", "Bus", Transport.CAN, Availability.AVAILABLE)
_RTU = Protocol("rtu", "Modbus RTU", "Serial", Transport.SERIAL, Availability.AVAILABLE)
_PLANNED = Protocol("j1939", "J1939", "PGN", Transport.CAN, carried_by="can")
_CATALOGUE = ProtocolCatalogue(
    Group(
        "root",
        "Root",
        (
            Group("bus", "Fieldbus", (Group("can-sub", "CAN", (_CAN, _PLANNED)),)),
            Group("serial", "Serial", (Group("rs485", "RS-485", (_RTU,)),)),
        ),
    )
)


def _parent(item: QTreeWidgetItem) -> QTreeWidgetItem:
    parent = item.parent()
    assert parent is not None
    return parent


@pytest.fixture(scope="module")
def qt_application() -> QApplication:
    application = QApplication.instance()
    if isinstance(application, QApplication):
        return application
    return QApplication([])


def test_selector_starts_on_requested_protocol(qt_application: QApplication) -> None:
    selector = ProtocolSelector(_CATALOGUE, "can")

    assert selector.selected is _CAN
    assert selector.tree.currentItem() is selector.item("can")


def test_selecting_available_protocol_emits_change(qt_application: QApplication) -> None:
    selector = ProtocolSelector(_CATALOGUE, "can")
    received: list[Protocol] = []
    selector.protocol_changed.connect(received.append)

    selector.choose(selector.item("rtu"))

    assert received == [_RTU]
    assert selector.selected is _RTU


def test_planned_protocol_is_disabled_with_stack_tooltip(qt_application: QApplication) -> None:
    selector = ProtocolSelector(_CATALOGUE, "can")
    planned = selector.item("j1939")

    assert planned.isDisabled()
    assert planned.text(1) == "planned"
    assert planned.toolTip(0) == "PGN (on can)"


def test_group_and_planned_items_do_not_change_selection(qt_application: QApplication) -> None:
    selector = ProtocolSelector(_CATALOGUE, "can")
    received: list[Protocol] = []
    selector.protocol_changed.connect(received.append)

    selector.choose(_parent(_parent(selector.item("rtu"))))  # family row
    selector.choose(selector.item("j1939"))
    selector.choose(None)

    assert received == []
    assert selector.selected is _CAN


def test_search_hides_non_matching_protocols_and_empty_groups(
    qt_application: QApplication,
) -> None:
    selector = ProtocolSelector(_CATALOGUE, "can")

    selector.search_input.setText("modbus")

    assert selector.item("can").isHidden()
    assert _parent(selector.item("can")).isHidden()
    assert not _parent(selector.item("rtu")).isHidden()
    selector.search_input.setText("")
    assert not selector.item("j1939").isHidden()
    assert not _parent(selector.item("can")).isHidden()


def test_selector_refuses_a_planned_protocol_as_initial_choice(
    qt_application: QApplication,
) -> None:
    with pytest.raises(ValueError, match="cannot be captured"):
        ProtocolSelector(_CATALOGUE, "j1939")


def test_button_names_selection_and_popup_closes_after_pick(
    qt_application: QApplication,
) -> None:
    selector = ProtocolSelector(_CATALOGUE, "can")
    assert selector.button.text() == "Protocol: CAN \u25be"

    selector.button.click()
    assert selector.popup.isVisible()
    selector.choose(selector.item("rtu"))

    assert selector.popup.isHidden()
    assert selector.button.text() == "Protocol: Modbus RTU \u25be"


def test_browsing_or_picking_planned_keeps_popup_open(qt_application: QApplication) -> None:
    selector = ProtocolSelector(_CATALOGUE, "can")
    selector.search_input.setText("modbus")
    selector.open_popup()

    assert selector.search_input.text() == ""
    assert selector.tree.currentItem() is selector.item("can")
    selector.tree.setCurrentItem(selector.item("rtu"))  # arrow-key style move
    selector.choose(selector.item("j1939"))

    assert selector.popup.isVisible()
    assert selector.selected is _CAN
    selector.choose(selector.item("can"))  # re-picking current closes too
    assert selector.popup.isHidden()


def test_selector_can_start_with_no_protocol(qt_application: QApplication) -> None:
    selector = ProtocolSelector(_CATALOGUE)
    received: list[Protocol] = []
    selector.protocol_changed.connect(received.append)

    assert selector.selected is None
    assert selector.button.text() == "Protocol: choose\u2026 \u25be"
    selector.open_popup()
    assert selector.tree.currentItem() is None
    selector.choose(selector.item("can"))

    assert received == [_CAN]
    assert selector.button.text() == "Protocol: CAN \u25be"


def test_root_is_not_shown_and_depth_is_unbounded(qt_application: QApplication) -> None:
    deep = Protocol("deep", "Deep", "", Transport.LOGIC, Availability.AVAILABLE)
    catalogue = ProtocolCatalogue(
        Group("root", "Root", (Group("a", "A", (Group("b", "B", (Group("c", "C", (deep,)),)),)),))
    )
    selector = ProtocolSelector(catalogue)

    top = _parent(_parent(_parent(selector.item("deep"))))
    assert selector.tree.topLevelItemCount() == 1
    assert selector.tree.topLevelItem(0) is top
    assert top.text(0) == "A"
    selector.search_input.setText("zzz")
    assert top.isHidden()
