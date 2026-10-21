import pytest
from PySide6.QtWidgets import QApplication, QTreeWidgetItem

from busscope.protocol_catalogue import (
    Availability,
    Family,
    Protocol,
    ProtocolCatalogue,
    SubFamily,
    Transport,
)
from busscope.protocol_selector import ProtocolSelector

_CAN = Protocol("can", "CAN", "Bus", Transport.CAN, Availability.AVAILABLE)
_RTU = Protocol("rtu", "Modbus RTU", "Serial", Transport.SERIAL, Availability.AVAILABLE)
_PLANNED = Protocol("j1939", "J1939", "PGN", Transport.CAN, carried_by="can")
_CATALOGUE = ProtocolCatalogue(
    (
        Family("bus", "Fieldbus", (SubFamily("can-sub", "CAN", (_CAN, _PLANNED)),)),
        Family("serial", "Serial", (SubFamily("rs485", "RS-485", (_RTU,)),)),
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

    serial = selector.item("rtu")
    selector.tree.setCurrentItem(serial)

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

    selector.tree.setCurrentItem(_parent(_parent(selector.item("rtu"))))  # family row
    selector._on_current_changed(selector.item("j1939"))
    selector._on_current_changed(None)

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
