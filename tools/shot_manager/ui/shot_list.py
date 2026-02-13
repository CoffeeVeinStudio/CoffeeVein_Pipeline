"""Shot list widget for CoffeeVein Shot Manager."""

from ..qt_compat import QtWidgets, QtCore, QtGui


# Special markers for special entries
INCOMING_MARKER = "_incoming_"
REFERENCE_MARKER = "_reference_"


class ShotListWidget(QtWidgets.QWidget):
    """Left panel: list of shots in the project."""

    shot_selected = QtCore.Signal(str, str)  # (shot_name, shot_path)
    incoming_selected = QtCore.Signal(str)   # (incoming_path)
    reference_selected = QtCore.Signal(str)  # (reference_path)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._shots = []  # List of (name, path) tuples
        self._incoming_path = None
        self._incoming_count = 0
        self._reference_path = None
        self._reference_count = 0
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QtWidgets.QLabel("Shots")
        header.setStyleSheet("font-weight: bold; font-size: 12px; padding: 4px;")
        layout.addWidget(header)

        # Filter
        self._filter = QtWidgets.QLineEdit()
        self._filter.setPlaceholderText("Filter shots...")
        self._filter.textChanged.connect(self._apply_filter)
        layout.addWidget(self._filter)

        # List
        self._list = QtWidgets.QListWidget()
        self._list.currentItemChanged.connect(self._on_item_changed)
        layout.addWidget(self._list)

    def set_shots(self, shots):
        """Set the shot list. shots: list of (name, path) tuples."""
        self._shots = shots
        self._populate()

    def set_incoming(self, incoming_path, item_count=0):
        """Set _Incoming entry info.

        Args:
            incoming_path: Path to the _Incoming directory.
            item_count: Number of detected incoming items.
        """
        self._incoming_path = incoming_path
        self._incoming_count = item_count
        self._populate()

    def set_reference(self, reference_path, item_count=0):
        """Set Reference entry info.

        Args:
            reference_path: Path to the project-level Reference directory.
            item_count: Number of detected reference outputs.
        """
        self._reference_path = reference_path
        self._reference_count = item_count
        self._populate()

    def _populate(self):
        """Populate the list widget."""
        self._list.clear()
        filter_text = self._filter.text().lower()

        for name, path in self._shots:
            if filter_text and filter_text not in name.lower():
                continue
            item = QtWidgets.QListWidgetItem(name)
            item.setData(QtCore.Qt.UserRole, path)
            self._list.addItem(item)

        # Add _Incoming entry at the bottom
        if self._incoming_path and (
            not filter_text or "incoming" in filter_text
        ):
            # Separator
            sep_item = QtWidgets.QListWidgetItem()
            sep_item.setFlags(QtCore.Qt.NoItemFlags)
            sep_item.setSizeHint(QtCore.QSize(0, 8))
            self._list.addItem(sep_item)

            # _Incoming entry
            label = "_Incoming"
            if self._incoming_count > 0:
                label += f"  ({self._incoming_count} items)"
            incoming_item = QtWidgets.QListWidgetItem(label)
            incoming_item.setData(QtCore.Qt.UserRole, INCOMING_MARKER)
            incoming_item.setForeground(QtGui.QColor("#e8a838"))
            font = incoming_item.font()
            font.setItalic(True)
            incoming_item.setFont(font)
            self._list.addItem(incoming_item)

        # Add Reference entry below _Incoming
        if self._reference_path and (
            not filter_text or "reference" in filter_text
        ):
            # Reference entry (no separator if right after _Incoming)
            label = "Reference"
            if self._reference_count > 0:
                label += f"  ({self._reference_count} items)"
            reference_item = QtWidgets.QListWidgetItem(label)
            reference_item.setData(QtCore.Qt.UserRole, REFERENCE_MARKER)
            reference_item.setForeground(QtGui.QColor("#9b59b6"))  # Purple
            font = reference_item.font()
            font.setItalic(True)
            reference_item.setFont(font)
            self._list.addItem(reference_item)

    def _apply_filter(self):
        """Re-filter the shot list."""
        self._populate()

    def select_shot(self, shot_name):
        """Programmatically select a shot by name."""
        for i in range(self._list.count()):
            item = self._list.item(i)
            if item.text() == shot_name:
                self._list.setCurrentItem(item)
                return True
        return False

    def _on_item_changed(self, current, previous):
        """Emit shot_selected, incoming_selected, or reference_selected when selection changes."""
        if current is None:
            return
        path = current.data(QtCore.Qt.UserRole)
        if path == INCOMING_MARKER:
            self.incoming_selected.emit(self._incoming_path)
        elif path == REFERENCE_MARKER:
            self.reference_selected.emit(self._reference_path)
        elif path is not None:
            name = current.text()
            self.shot_selected.emit(name, path)
