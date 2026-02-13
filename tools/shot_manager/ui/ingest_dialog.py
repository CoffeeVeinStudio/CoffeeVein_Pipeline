"""Ingest dialog for moving _Incoming items into shot structure."""

from pathlib import Path

from ..qt_compat import QtWidgets, QtCore, QtGui

from ..core import OutputType
from .. import database, paths


# Map OutputType → display label for the type combo
_TYPE_CHOICES = [
    (OutputType.PLATE, "Plate"),
    (OutputType.CG, "CG"),
    (OutputType.REFERENCE, "Reference"),
]


def _make_type_combo(suggested_type=None):
    """Create a type combo box, pre-selected to suggested_type."""
    combo = QtWidgets.QComboBox()
    for output_type, label in _TYPE_CHOICES:
        combo.addItem(label, output_type)
    if suggested_type:
        for i in range(combo.count()):
            if combo.itemData(i) == suggested_type:
                combo.setCurrentIndex(i)
                break
    return combo


def _make_dest_combo(default_text=""):
    """Create an editable destination combo box."""
    combo = QtWidgets.QComboBox()
    combo.setEditable(True)
    combo.setInsertPolicy(QtWidgets.QComboBox.NoInsert)
    combo.setEditText(default_text)
    return combo


class IngestDialog(QtWidgets.QDialog):
    """Dialog for configuring how incoming items are ingested into a shot.

    Single-item mode: shot, destination (editable combo), type, notes.
    Batch mode: shot, per-item table (destination + type per row), notes.
    """

    def __init__(self, shots, items, project_root, suggested_shot=None,
                 parent=None):
        """
        Args:
            shots: List of (shot_name, shot_path) tuples.
            items: List of (Output, IncomingItem) tuples to ingest.
            project_root: Path to the project root (for querying existing names).
            suggested_shot: Shot name to pre-select.
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Move to Shot")
        self.setMinimumWidth(550)

        self._shots = shots
        self._items = items
        self._project_root = Path(project_root)
        self._suggested_shot = suggested_shot

        # Per-item widgets (batch mode)
        self._item_dest_combos = []
        self._item_type_combos = []

        self._build_ui()
        self._populate()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # --- Items summary ---
        if len(self._items) == 1:
            _, item = self._items[0]
            summary = f"Moving: {item.name}  ({item.item_type})"
        else:
            summary = f"Moving {len(self._items)} items"
        summary_label = QtWidgets.QLabel(summary)
        summary_label.setStyleSheet("font-weight: bold; padding: 4px;")
        layout.addWidget(summary_label)

        # --- Form ---
        form = QtWidgets.QFormLayout()

        # Target shot
        self._shot_combo = QtWidgets.QComboBox()
        self._shot_combo.setEditable(False)
        self._shot_combo.currentIndexChanged.connect(self._on_shot_changed)
        form.addRow("Target Shot:", self._shot_combo)

        if len(self._items) == 1:
            # Single-item mode: destination + type in form
            _, item = self._items[0]

            self._dest_combo = _make_dest_combo(item.name)
            form.addRow("Destination:", self._dest_combo)

            self._type_combo = _make_type_combo(item.suggested_type)
            self._type_combo.currentIndexChanged.connect(
                self._on_single_type_changed
            )
            form.addRow("Type:", self._type_combo)
        else:
            self._dest_combo = None
            self._type_combo = None

        # Notes (shared)
        self._notes_edit = QtWidgets.QLineEdit()
        self._notes_edit.setPlaceholderText("Optional notes for this version...")
        form.addRow("Notes:", self._notes_edit)

        # Create Read nodes checkbox (Nuke-only)
        self._create_reads_check = None
        try:
            import nuke
            self._create_reads_check = QtWidgets.QCheckBox("Create Read nodes after moving")
            self._create_reads_check.setChecked(False)
            form.addRow("", self._create_reads_check)
        except ImportError:
            pass  # Not in Nuke

        layout.addLayout(form)

        # --- Per-item table (batch mode) ---
        if len(self._items) > 1:
            group = QtWidgets.QGroupBox("Items to ingest")
            group_layout = QtWidgets.QVBoxLayout(group)

            self._table = QtWidgets.QTableWidget(len(self._items), 4)
            self._table.setHorizontalHeaderLabels(
                ["Destination", "Name", "Info", "Type"]
            )
            header = self._table.horizontalHeader()
            header.setStretchLastSection(False)
            header.setSectionResizeMode(0, QtWidgets.QHeaderView.Stretch)
            header.setSectionResizeMode(1, QtWidgets.QHeaderView.ResizeToContents)
            header.setSectionResizeMode(2, QtWidgets.QHeaderView.ResizeToContents)
            header.setSectionResizeMode(3, QtWidgets.QHeaderView.ResizeToContents)
            self._table.verticalHeader().setVisible(False)
            self._table.setEditTriggers(
                QtWidgets.QAbstractItemView.NoEditTriggers
            )
            self._table.setSelectionMode(
                QtWidgets.QAbstractItemView.NoSelection
            )
            self._table.setMaximumHeight(
                min(40 + len(self._items) * 34, 250)
            )

            for row, (_, item) in enumerate(self._items):
                # Destination combo (editable, per-item)
                dest_combo = _make_dest_combo(item.name)
                self._table.setCellWidget(row, 0, dest_combo)
                self._item_dest_combos.append(dest_combo)

                # Name (read-only, original filename)
                name_item = QtWidgets.QTableWidgetItem(item.name)
                name_item.setForeground(QtGui.QColor("#888888"))
                self._table.setItem(row, 1, name_item)

                # Info
                info = item.item_type
                if item.frame_range:
                    info += f" [{item.frame_range[0]}-{item.frame_range[1]}]"
                self._table.setItem(
                    row, 2, QtWidgets.QTableWidgetItem(info)
                )

                # Type combo (per-item)
                type_combo = _make_type_combo(item.suggested_type)
                # Connect type change to refresh that row's destination
                type_combo.currentIndexChanged.connect(
                    lambda _, r=row: self._on_batch_type_changed(r)
                )
                self._table.setCellWidget(row, 3, type_combo)
                self._item_type_combos.append(type_combo)

            group_layout.addWidget(self._table)
            layout.addWidget(group)

        # --- Buttons ---
        btn_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        btn_box.button(QtWidgets.QDialogButtonBox.Ok).setText("Move")
        btn_box.accepted.connect(self.accept)
        btn_box.rejected.connect(self.reject)
        layout.addWidget(btn_box)

    # ------------------------------------------------------------------
    # Populate and refresh
    # ------------------------------------------------------------------

    def _populate(self):
        """Initial population of combos."""
        # Shot combo
        for name, path in self._shots:
            self._shot_combo.addItem(name, path)

        # Pre-select suggested shot
        if self._suggested_shot:
            idx = self._shot_combo.findText(self._suggested_shot)
            if idx >= 0:
                self._shot_combo.setCurrentIndex(idx)

        # Refresh destination combos with existing names
        self._refresh_all_destinations()

    def _get_existing_names(self, shot_name, output_type):
        """Query existing output names for a shot+type from .versions.json files."""
        shots_dir = paths.get_shots_dir(self._project_root)
        if shots_dir is None:
            return []
        shot_dir = shots_dir / shot_name
        if not shot_dir.exists():
            return []
        type_folder = OutputType.folder_for(output_type)
        outputs = database.discover_outputs(shot_dir, output_type, type_folder)
        return sorted(o.name for o in outputs)

    def _refresh_destination_combo(self, combo, output_type, default_text):
        """Refresh a destination combo with existing names for current shot+type."""
        shot_name = self._shot_combo.currentText()
        if not shot_name:
            return

        # Preserve current text
        current_text = combo.currentText() or default_text

        combo.blockSignals(True)
        combo.clear()
        existing = self._get_existing_names(shot_name, output_type)
        combo.addItems(existing)
        combo.setEditText(current_text)
        combo.blockSignals(False)

    def _refresh_all_destinations(self):
        """Refresh all destination combos (called when shot changes)."""
        if self._dest_combo and self._type_combo:
            # Single mode
            _, item = self._items[0]
            self._refresh_destination_combo(
                self._dest_combo,
                self._type_combo.currentData(),
                item.name,
            )
        else:
            # Batch mode
            for i, (_, item) in enumerate(self._items):
                if i < len(self._item_dest_combos):
                    type_combo = self._item_type_combos[i]
                    self._refresh_destination_combo(
                        self._item_dest_combos[i],
                        type_combo.currentData(),
                        item.name,
                    )

    # ------------------------------------------------------------------
    # Signal handlers
    # ------------------------------------------------------------------

    def _on_shot_changed(self, index):
        """Shot selection changed — refresh all destination dropdowns."""
        self._refresh_all_destinations()

    def _on_single_type_changed(self, index):
        """Type changed in single-item mode — refresh destination."""
        if self._dest_combo and self._type_combo:
            _, item = self._items[0]
            self._refresh_destination_combo(
                self._dest_combo,
                self._type_combo.currentData(),
                item.name,
            )

    def _on_batch_type_changed(self, row):
        """Type changed for a batch row — refresh that row's destination."""
        if row < len(self._item_dest_combos):
            _, item = self._items[row]
            type_combo = self._item_type_combos[row]
            self._refresh_destination_combo(
                self._item_dest_combos[row],
                type_combo.currentData(),
                item.name,
            )

    # ------------------------------------------------------------------
    # Public accessors
    # ------------------------------------------------------------------

    @property
    def target_shot_name(self):
        """Selected shot name."""
        return self._shot_combo.currentText()

    @property
    def target_shot_path(self):
        """Selected shot directory path."""
        return self._shot_combo.currentData()

    @property
    def output_name(self):
        """Destination name (single-item mode)."""
        if self._dest_combo:
            return self._dest_combo.currentText().strip()
        return ""

    @property
    def output_type(self):
        """Selected OutputType string (single-item mode only)."""
        if self._type_combo:
            return self._type_combo.currentData()
        return None

    @property
    def notes(self):
        """User-entered notes."""
        return self._notes_edit.text().strip()

    def get_item_name(self, index):
        """Get the destination name for a specific item (batch mode).

        Returns the text from that row's editable destination combo.
        """
        if self._item_dest_combos and index < len(self._item_dest_combos):
            return self._item_dest_combos[index].currentText().strip()
        # Fall back to single-mode destination
        return self.output_name

    def get_item_type(self, index):
        """Get the output type for a specific item (batch mode)."""
        if self._item_type_combos and index < len(self._item_type_combos):
            return self._item_type_combos[index].currentData()
        return self.output_type

    @property
    def create_reads(self):
        """Whether to create Read nodes after ingest (Nuke-only)."""
        if self._create_reads_check:
            return self._create_reads_check.isChecked()
        return False
