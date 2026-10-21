"""Searchable family / sub-family / protocol tree for the capture tab."""

from __future__ import annotations

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLineEdit, QTreeWidget, QTreeWidgetItem, QVBoxLayout, QWidget

from busscope.protocol_catalogue import Availability, Protocol, ProtocolCatalogue

_KEY_ROLE = Qt.ItemDataRole.UserRole


class ProtocolSelector(QWidget):
    """Let the operator find and pick an available protocol; planned ones stay disabled."""

    protocol_changed = Signal(object)

    def __init__(self, catalogue: ProtocolCatalogue, selected_key: str) -> None:
        """Build the tree from ``catalogue`` and select ``selected_key``."""
        super().__init__()
        self._catalogue = catalogue
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
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.search_input)
        layout.addWidget(self.tree)
        self.search_input.textChanged.connect(self.filter)
        self.tree.currentItemChanged.connect(self._on_current_changed)

    @property
    def selected(self) -> Protocol:
        """Return the protocol currently chosen for capture."""
        return self._selected

    def filter(self, text: str) -> None:
        """Hide protocols not matching ``text`` and groups left empty."""
        visible = {protocol.key for protocol in self._catalogue.search(text)}
        for key, item in self._items.items():
            item.setHidden(key not in visible)
        # Sub-families are listed before families, so children are settled first.
        for group, children in self._groups:
            group.setHidden(all(child.isHidden() for child in children))

    def item(self, key: str) -> QTreeWidgetItem:
        """Return the tree item showing protocol ``key``."""
        return self._items[key]

    def _populate(self) -> None:
        for family in self._catalogue.families:
            family_item = QTreeWidgetItem(self.tree, [family.name])
            family_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
            sub_items = []
            for sub_family in family.sub_families:
                sub_item = QTreeWidgetItem(family_item, [sub_family.name])
                sub_item.setFlags(Qt.ItemFlag.ItemIsEnabled)
                leaves = [self._protocol_item(sub_item, p) for p in sub_family.protocols]
                self._items.update(zip((p.key for p in sub_family.protocols), leaves, strict=True))
                self._groups.append((sub_item, leaves))
                sub_items.append(sub_item)
            self._groups.append((family_item, sub_items))
        self.tree.expandAll()
        self.tree.resizeColumnToContents(0)
        self.tree.setCurrentItem(self._items[self._selected.key])
        self.tree.scrollToItem(self._items[self._selected.key])

    @staticmethod
    def _protocol_item(parent: QTreeWidgetItem, protocol: Protocol) -> QTreeWidgetItem:
        item = QTreeWidgetItem(parent, [protocol.name, protocol.availability.value])
        item.setData(0, _KEY_ROLE, protocol.key)
        tooltip = protocol.description
        if protocol.carried_by is not None:
            tooltip += f" (on {protocol.carried_by})"
        item.setToolTip(0, tooltip)
        if protocol.availability is not Availability.AVAILABLE:
            item.setDisabled(True)
        return item

    def _on_current_changed(self, current: QTreeWidgetItem | None) -> None:
        if current is None or current.isDisabled():
            return
        key = current.data(0, _KEY_ROLE)
        if not isinstance(key, str):
            return
        protocol = self._catalogue.get(key)
        if protocol != self._selected:
            self._selected = protocol
            self.protocol_changed.emit(protocol)
