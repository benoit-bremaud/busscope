"""Compact protocol picker: a button that opens the searchable, recursive domain tree."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLineEdit,
    QPushButton,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from busscope.protocol_catalogue import Availability, Group, Protocol, ProtocolCatalogue

_KEY_ROLE = Qt.ItemDataRole.UserRole


class ProtocolSelector(QWidget):
    """Let the operator find and pick an available protocol; planned ones stay disabled."""

    protocol_changed = Signal(object)
    _POPUP_WIDTH = 420
    _POPUP_HEIGHT = 320

    def __init__(self, catalogue: ProtocolCatalogue, selected_key: str | None = None) -> None:
        """Build the tree from ``catalogue``; start on ``selected_key`` or on no protocol."""
        super().__init__()
        self._catalogue = catalogue
        self._selected: Protocol | None = None
        if selected_key is not None:
            self._selected = catalogue.get(selected_key)
            if self._selected.availability is not Availability.AVAILABLE:
                raise ValueError(f"{selected_key} cannot be captured yet")
        self.search_input = QLineEdit()
        self.search_input.setPlaceholderText("Search protocols")
        self.search_input.setAccessibleName("Protocol search")
        self.tree = QTreeWidget()
        self.tree.setHeaderLabels(["Protocol", "Status"])
        self.tree.setAccessibleName("Protocol catalogue")
        self._items: dict[str, QTreeWidgetItem] = {}
        self._groups: list[tuple[QTreeWidgetItem, list[QTreeWidgetItem]]] = []
        self._populate()
        # The tree lives in a popup (PulseView / PCAN-View style) so the frame list keeps
        # the vertical space; the button shows the current choice.
        self.button = QPushButton()
        self.button.setAccessibleName("Protocol")
        self.button.setToolTip("Choose the protocol to capture")
        self.popup = QFrame(self, Qt.WindowType.Popup)
        self.popup.setFrameShape(QFrame.Shape.StyledPanel)
        popup_layout = QVBoxLayout(self.popup)
        popup_layout.addWidget(self.search_input)
        popup_layout.addWidget(self.tree)
        self.popup.resize(self._POPUP_WIDTH, self._POPUP_HEIGHT)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.button)
        layout.addStretch()
        self._update_button()
        self.button.clicked.connect(self.open_popup)
        self.search_input.textChanged.connect(self.filter)
        # Choose on click or Enter only: arrow keys and live search just move the cursor.
        self.tree.itemClicked.connect(self.choose)
        self.tree.itemActivated.connect(self.choose)

    @property
    def selected(self) -> Protocol | None:
        """Return the protocol currently chosen for capture, ``None`` before the first pick."""
        return self._selected

    def open_popup(self) -> None:
        """Show the searchable catalogue under the button, search field focused."""
        self.popup.move(self.button.mapToGlobal(self.button.rect().bottomLeft()))
        self.search_input.clear()
        self._focus_selected()
        self.popup.show()
        self.search_input.setFocus()

    def _update_button(self) -> None:
        name = "choose\u2026" if self._selected is None else self._selected.name
        self.button.setText(f"Protocol: {name} \u25be")

    def filter(self, text: str) -> None:
        """Hide protocols not matching ``text`` and groups left empty."""
        visible = {protocol.key for protocol in self._catalogue.search(text)}
        for key, item in self._items.items():
            item.setHidden(key not in visible)
        # Groups are recorded after their children (post-order), so children settle first.
        for group, children in self._groups:
            group.setHidden(all(child.isHidden() for child in children))

    def item(self, key: str) -> QTreeWidgetItem:
        """Return the tree item showing protocol ``key``."""
        return self._items[key]

    def _populate(self) -> None:
        # The root only gathers the domains; showing it would add a useless level.
        for child in self._catalogue.root.children:
            self._add_node(None, child)
        self.tree.expandAll()
        self.tree.resizeColumnToContents(0)
        self._focus_selected()

    def _focus_selected(self) -> None:
        if self._selected is not None:
            item = self._items[self._selected.key]
            self.tree.setCurrentItem(item)
            self.tree.scrollToItem(item)

    def _add_node(self, parent: QTreeWidgetItem | None, node: Group | Protocol) -> QTreeWidgetItem:
        if isinstance(node, Protocol):
            item = self._protocol_item(parent, node)
            self._items[node.key] = item
            return item
        item = self._tree_item(parent, [node.name])
        item.setFlags(Qt.ItemFlag.ItemIsEnabled)
        children = [self._add_node(item, child) for child in node.children]
        self._groups.append((item, children))
        return item

    def _tree_item(self, parent: QTreeWidgetItem | None, texts: list[str]) -> QTreeWidgetItem:
        if parent is None:
            return QTreeWidgetItem(self.tree, texts)
        return QTreeWidgetItem(parent, texts)

    def _protocol_item(self, parent: QTreeWidgetItem | None, protocol: Protocol) -> QTreeWidgetItem:
        item = self._tree_item(parent, [protocol.name, protocol.availability.value])
        item.setData(0, _KEY_ROLE, protocol.key)
        tooltip = protocol.description
        if protocol.carried_by is not None:
            tooltip += f" (on {protocol.carried_by})"
        item.setToolTip(0, tooltip)
        if protocol.availability is not Availability.AVAILABLE:
            item.setDisabled(True)
        return item

    def choose(self, current: QTreeWidgetItem | None, _column: int = 0) -> None:
        """Select the protocol shown by ``current`` and close the popup.

        Group rows and planned protocols are ignored and leave the popup open.
        """
        if current is None or current.isDisabled():
            return
        key = current.data(0, _KEY_ROLE)
        if not isinstance(key, str):
            return
        protocol = self._catalogue.get(key)
        if protocol != self._selected:
            self._selected = protocol
            self._update_button()
            self.protocol_changed.emit(protocol)
        self.popup.hide()
