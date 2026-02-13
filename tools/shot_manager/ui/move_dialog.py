"""Move output dialog for CoffeeVein Shot Manager."""

from ..qt_compat import QtWidgets, QtCore


class MoveDialog(QtWidgets.QDialog):
    """Dialog for moving an output to a different location."""

    def __init__(self, output_name, shot_list, current_shot_name=None, parent=None):
        """
        Args:
            output_name: Name of the output being moved.
            shot_list: List of (shot_name, shot_path) tuples for destination.
            current_shot_name: Name of current shot (to exclude from list).
            parent: Parent widget.
        """
        super().__init__(parent)
        self.setWindowTitle("Move Output")
        self.setMinimumWidth(450)

        self._output_name = output_name
        self._shot_list = shot_list
        self._current_shot_name = current_shot_name

        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Header
        header = QtWidgets.QLabel(f"Moving output: <b>{self._output_name}</b>")
        layout.addWidget(header)

        layout.addSpacing(10)

        # Destination type selector
        dest_group = QtWidgets.QGroupBox("Destination")
        dest_layout = QtWidgets.QVBoxLayout(dest_group)

        self._dest_shot_radio = QtWidgets.QRadioButton("Shot")
        self._dest_shot_radio.setChecked(True)
        self._dest_shot_radio.toggled.connect(self._on_dest_type_changed)
        dest_layout.addWidget(self._dest_shot_radio)

        self._dest_reference_radio = QtWidgets.QRadioButton("Reference (project-level)")
        self._dest_reference_radio.toggled.connect(self._on_dest_type_changed)
        dest_layout.addWidget(self._dest_reference_radio)

        self._dest_incoming_radio = QtWidgets.QRadioButton("_Incoming")
        self._dest_incoming_radio.toggled.connect(self._on_dest_type_changed)
        dest_layout.addWidget(self._dest_incoming_radio)

        layout.addWidget(dest_group)

        # Target selector (changes based on destination type)
        self._target_group = QtWidgets.QGroupBox("Target")
        self._target_layout = QtWidgets.QVBoxLayout(self._target_group)

        # Shot selector
        self._shot_combo = QtWidgets.QComboBox()
        for shot_name, shot_path in self._shot_list:
            # Exclude current shot
            if shot_name != self._current_shot_name:
                self._shot_combo.addItem(shot_name, shot_path)
        self._shot_combo.currentIndexChanged.connect(self._update_preview)
        self._target_layout.addWidget(self._shot_combo)

        # _Incoming subfolder selector
        self._incoming_combo = QtWidgets.QComboBox()
        self._incoming_combo.addItem("Plates", "Plates")
        self._incoming_combo.addItem("CG", "CG")
        self._incoming_combo.addItem("Reference", "Reference")
        self._incoming_combo.currentIndexChanged.connect(self._update_preview)
        self._incoming_combo.setVisible(False)
        self._target_layout.addWidget(self._incoming_combo)

        layout.addWidget(self._target_group)

        # Optional rename
        rename_group = QtWidgets.QGroupBox("Output Name (optional)")
        rename_layout = QtWidgets.QVBoxLayout(rename_group)

        self._rename_edit = QtWidgets.QLineEdit()
        self._rename_edit.setPlaceholderText(f"Leave empty to keep: {self._output_name}")
        self._rename_edit.textChanged.connect(self._update_preview)
        rename_layout.addWidget(self._rename_edit)

        layout.addWidget(rename_group)

        # Preview
        preview_group = QtWidgets.QGroupBox("Preview")
        preview_layout = QtWidgets.QVBoxLayout(preview_group)

        self._preview_label = QtWidgets.QLabel()
        self._preview_label.setWordWrap(True)
        self._preview_label.setStyleSheet("color: #888888; font-style: italic;")
        preview_layout.addWidget(self._preview_label)

        layout.addWidget(preview_group)

        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()

        self._move_btn = QtWidgets.QPushButton("Move")
        self._move_btn.clicked.connect(self.accept)
        self._move_btn.setDefault(True)
        button_layout.addWidget(self._move_btn)

        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

        # Initial state
        self._on_dest_type_changed()
        self._update_preview()

    def _on_dest_type_changed(self):
        """Update UI when destination type changes."""
        if self._dest_shot_radio.isChecked():
            self._target_group.setVisible(True)
            self._shot_combo.setVisible(True)
            self._incoming_combo.setVisible(False)
        elif self._dest_reference_radio.isChecked():
            self._target_group.setVisible(False)
        elif self._dest_incoming_radio.isChecked():
            self._target_group.setVisible(True)
            self._shot_combo.setVisible(False)
            self._incoming_combo.setVisible(True)

        self._update_preview()

    def _update_preview(self):
        """Update the preview text based on current selections."""
        output_name = self._rename_edit.text().strip() or self._output_name

        if self._dest_shot_radio.isChecked():
            shot_name = self._shot_combo.currentText()
            preview = f"All versions of <b>{self._output_name}</b> will be moved to shot <b>{shot_name}</b>"
            if output_name != self._output_name:
                preview += f" as <b>{output_name}</b>"
        elif self._dest_reference_radio.isChecked():
            preview = f"All versions of <b>{self._output_name}</b> will be moved to project-level <b>Reference</b>"
            if output_name != self._output_name:
                preview += f" as <b>{output_name}</b>"
        elif self._dest_incoming_radio.isChecked():
            subfolder = self._incoming_combo.currentText()
            preview = f"All versions of <b>{self._output_name}</b> will be flattened and moved to <b>_Incoming/{subfolder}</b>"
            preview += "<br><i>(Version structure will be lost)</i>"
        else:
            preview = ""

        self._preview_label.setText(preview)

    def get_destination(self):
        """Get the selected destination.

        Returns:
            Tuple of (dest_type, target, new_name):
            - dest_type: "shot", "reference", or "incoming"
            - target: shot_name (for shot), None (for reference), or subfolder (for incoming)
            - new_name: New output name or None to keep current
        """
        new_name = self._rename_edit.text().strip() or None

        if self._dest_shot_radio.isChecked():
            return "shot", self._shot_combo.currentText(), new_name
        elif self._dest_reference_radio.isChecked():
            return "reference", None, new_name
        elif self._dest_incoming_radio.isChecked():
            return "incoming", self._incoming_combo.currentData(), new_name

        return None, None, None
