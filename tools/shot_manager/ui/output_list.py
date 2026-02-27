"""Output list widget for CoffeeVein Shot Manager.

Shows all outputs (renders, plates, CG, etc.) for the selected shot,
grouped by type.
"""

import re
from pathlib import Path

from ..qt_compat import QtWidgets, QtCore, QtGui

from ..core import OutputType


def _live_files_exist(output, base_dir) -> bool:
    """Check if the LIVE version's files exist on disk.

    Returns True if there is no LIVE version, or if files are present.
    """
    live_version = output.live
    if live_version is None or not live_version.path:
        return True

    def _resolve_frame(pattern_path, frame):
        name = pattern_path.name
        resolved = re.sub(r'#+', lambda m: str(frame).zfill(len(m.group(0))), name)
        return pattern_path.parent / resolved

    if base_dir is None:
        file_path = Path(live_version.path)
    else:
        from .. import paths as path_module
        if output.output_type == OutputType.REFERENCE:
            output_dir = Path(base_dir) / output.name
        else:
            output_dir = path_module.get_output_dir(
                base_dir, output.output_type, output.name
            )
        file_path = output_dir / live_version.path

    if live_version.frames:
        first = _resolve_frame(file_path, live_version.frames[0])
        last = _resolve_frame(file_path, live_version.frames[1])
        return first.exists() and last.exists()
    else:
        return file_path.exists()


# Group labels and order
_TYPE_LABELS = {
    OutputType.RENDER: "Renders",
    OutputType.PLATE: "Plates",
    OutputType.CG: "CG",
    OutputType.REFERENCE: "Reference",
    OutputType.UNSORTED: "Unsorted",
}

_TYPE_COLORS = {
    OutputType.RENDER: "#47a3cb",
    OutputType.PLATE: "#a3cb47",
    OutputType.CG: "#cb8f47",
    OutputType.REFERENCE: "#9b47cb",
    OutputType.UNSORTED: "#e8a838",
}


class OutputListWidget(QtWidgets.QWidget):
    """Middle panel: outputs grouped by type."""

    output_selected = QtCore.Signal(object)  # Output object

    def __init__(self, parent=None):
        super().__init__(parent)
        self._outputs = []
        self._base_dir = None
        self._multi_select = False
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QtWidgets.QLabel("Outputs")
        header.setStyleSheet("font-weight: bold; font-size: 12px; padding: 4px;")
        layout.addWidget(header)

        self._tree = QtWidgets.QTreeWidget()
        self._tree.setHeaderHidden(True)
        self._tree.setIndentation(16)
        self._tree.currentItemChanged.connect(self._on_item_changed)
        layout.addWidget(self._tree)

    def set_outputs(self, outputs, base_dir=None):
        """Set and display outputs grouped by type.

        Args:
            outputs: List of Output objects.
            base_dir: Shot or reference directory for resolving file paths.
                      None for _Incoming (uses absolute paths).
        """
        self._outputs = outputs
        self._base_dir = base_dir
        self._populate()

    def _populate(self):
        """Rebuild the tree widget."""
        self._tree.clear()

        # Group outputs by type
        grouped = {}
        for output in self._outputs:
            grouped.setdefault(output.output_type, []).append(output)

        # Create tree items
        for output_type in (OutputType.RENDER, OutputType.PLATE,
                            OutputType.CG, OutputType.REFERENCE,
                            OutputType.UNSORTED):
            outputs = grouped.get(output_type, [])
            if not outputs:
                continue

            label = _TYPE_LABELS.get(output_type, output_type)
            color = _TYPE_COLORS.get(output_type, "#cccccc")

            group_item = QtWidgets.QTreeWidgetItem([f"  {label}"])
            group_item.setForeground(0, QtGui.QColor(color))
            font = group_item.font(0)
            font.setBold(True)
            group_item.setFont(0, font)
            group_item.setFlags(group_item.flags() & ~QtCore.Qt.ItemIsSelectable)
            self._tree.addTopLevelItem(group_item)

            for output in sorted(outputs, key=lambda o: o.name):
                has_live = output.live_version is not None
                display = f"  {output.name}"

                if has_live:
                    live_ok = _live_files_exist(output, self._base_dir)
                    if live_ok:
                        display += "  \u2666"  # Diamond: LIVE version present
                        child = QtWidgets.QTreeWidgetItem([display])
                        child.setForeground(0, QtGui.QColor(color))
                    else:
                        display += "  \u26a0"  # Warning triangle: LIVE files missing
                        child = QtWidgets.QTreeWidgetItem([display])
                        child.setForeground(0, QtGui.QColor("#ff6666"))
                else:
                    child = QtWidgets.QTreeWidgetItem([display])

                child.setData(0, QtCore.Qt.UserRole, output)
                group_item.addChild(child)

            group_item.setExpanded(True)

    def set_selection_mode(self, multi=False):
        """Toggle between single and multi-selection mode.

        Multi-selection is used when viewing _Incoming so users can
        select multiple items for batch ingest.
        """
        self._multi_select = multi
        if multi:
            self._tree.setSelectionMode(
                QtWidgets.QAbstractItemView.ExtendedSelection
            )
        else:
            self._tree.setSelectionMode(
                QtWidgets.QAbstractItemView.SingleSelection
            )

    def get_selected_outputs(self):
        """Return all currently selected Output objects.

        Skips group header items (which have no UserRole data).
        """
        outputs = []
        for item in self._tree.selectedItems():
            output = item.data(0, QtCore.Qt.UserRole)
            if output is not None:
                outputs.append(output)
        return outputs

    def update_output(self, output):
        """Refresh a single output's display (e.g., after LIVE change)."""
        # Simple approach: rebuild entire tree
        self._populate()

    def _on_item_changed(self, current, previous):
        """Emit output_selected when an output item is clicked."""
        if current is None:
            return
        output = current.data(0, QtCore.Qt.UserRole)
        if output is not None:
            self.output_selected.emit(output)
