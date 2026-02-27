"""Version panel widget for CoffeeVein Shot Manager.

Shows version details for the selected output: version selector,
notes, metadata, thumbnail, and action buttons.
"""

import os
from pathlib import Path

from ..qt_compat import QtWidgets, QtCore, QtGui

from ..core import Output


class VersionPanel(QtWidgets.QWidget):
    """Right panel: version details and controls."""

    live_changed = QtCore.Signal(object, int)  # (Output, version_number)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._output = None
        self._shot_dir = None
        self._current_version = None
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        header = QtWidgets.QLabel("Versions")
        header.setStyleSheet("font-weight: bold; font-size: 12px; padding: 4px;")
        layout.addWidget(header)

        # Version selector row
        selector_row = QtWidgets.QHBoxLayout()

        self._version_combo = QtWidgets.QComboBox()
        self._version_combo.setMinimumWidth(120)
        self._version_combo.currentIndexChanged.connect(self._on_version_changed)
        selector_row.addWidget(self._version_combo)

        self._live_label = QtWidgets.QLabel()
        self._live_label.setStyleSheet(
            "color: #4caf50; font-weight: bold; padding: 2px 8px;"
        )
        selector_row.addWidget(self._live_label)

        selector_row.addStretch()

        self._set_live_btn = QtWidgets.QPushButton("Set LIVE")
        self._set_live_btn.setStyleSheet(
            "QPushButton { background-color: #2d7b3a; padding: 4px 12px; }"
            "QPushButton:hover { background-color: #3dab4a; }"
        )
        self._set_live_btn.clicked.connect(self._on_set_live)
        selector_row.addWidget(self._set_live_btn)

        layout.addLayout(selector_row)

        # Metadata area
        self._info_group = QtWidgets.QGroupBox("Details")
        info_layout = QtWidgets.QFormLayout(self._info_group)

        self._date_label = QtWidgets.QLabel()
        info_layout.addRow("Created:", self._date_label)

        self._creator_label = QtWidgets.QLabel()
        info_layout.addRow("Creator:", self._creator_label)

        self._frames_label = QtWidgets.QLabel()
        info_layout.addRow("Frames:", self._frames_label)

        self._format_label = QtWidgets.QLabel()
        info_layout.addRow("Format:", self._format_label)

        self._source_label = QtWidgets.QLabel()
        self._source_label.setWordWrap(True)
        info_layout.addRow("Source:", self._source_label)

        self._path_label = QtWidgets.QLabel()
        self._path_label.setWordWrap(True)
        self._path_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        info_layout.addRow("Path:", self._path_label)

        layout.addWidget(self._info_group)

        # Notes
        notes_group = QtWidgets.QGroupBox("Notes")
        notes_layout = QtWidgets.QVBoxLayout(notes_group)
        self._notes_text = QtWidgets.QTextEdit()
        self._notes_text.setReadOnly(True)
        self._notes_text.setMaximumHeight(80)
        notes_layout.addWidget(self._notes_text)
        layout.addWidget(notes_group)

        # Thumbnail area
        self._thumbnail_label = QtWidgets.QLabel()
        self._thumbnail_label.setAlignment(QtCore.Qt.AlignCenter)
        self._thumbnail_label.setMinimumHeight(200)
        self._thumbnail_label.setStyleSheet(
            "background-color: #1a1a1a; border: 1px solid #333;"
        )
        self._thumbnail_label.setText("No preview")
        layout.addWidget(self._thumbnail_label, stretch=1)

        # Action buttons
        btn_row = QtWidgets.QHBoxLayout()

        self._open_folder_btn = QtWidgets.QPushButton("Open Folder")
        self._open_folder_btn.clicked.connect(self._on_open_folder)
        btn_row.addWidget(self._open_folder_btn)

        # Create Read button (Nuke-only, with dropdown menu)
        self._create_read_btn = None
        try:
            import nuke
            # We're in Nuke — show Create Read button
            self._create_read_btn = QtWidgets.QToolButton()
            self._create_read_btn.setText("Create Read")
            self._create_read_btn.setPopupMode(QtWidgets.QToolButton.MenuButtonPopup)

            # Create dropdown menu
            read_menu = QtWidgets.QMenu(self._create_read_btn)

            self._create_static_action = read_menu.addAction("Create Read (static version)")
            self._create_static_action.triggered.connect(self._on_create_static_read)

            self._create_live_action = read_menu.addAction("Create LIVE Read")
            self._create_live_action.triggered.connect(self._on_create_live_read)

            read_menu.addSeparator()

            self._update_existing_action = read_menu.addAction("Update Existing Read...")
            self._update_existing_action.triggered.connect(self._on_update_existing_read)

            self._create_read_btn.setMenu(read_menu)
            self._create_read_btn.setDefaultAction(self._create_static_action)
            btn_row.addWidget(self._create_read_btn)
        except ImportError:
            pass  # Not in Nuke, skip the button

        btn_row.addStretch()
        layout.addLayout(btn_row)

        # Start with everything disabled
        self._set_enabled(False)

    def _set_enabled(self, enabled):
        """Enable/disable all controls."""
        self._version_combo.setEnabled(enabled)
        self._set_live_btn.setEnabled(enabled)
        self._open_folder_btn.setEnabled(enabled)
        if self._create_read_btn:
            self._create_read_btn.setEnabled(enabled)

    def clear(self):
        """Clear all version info."""
        self._output = None
        self._current_version = None
        self._version_combo.clear()
        self._live_label.clear()
        self._date_label.clear()
        self._creator_label.clear()
        self._frames_label.clear()
        self._format_label.clear()
        self._source_label.clear()
        self._path_label.clear()
        self._notes_text.clear()
        self._thumbnail_label.setText("No preview")
        self._set_enabled(False)

    def set_output(self, output, shot_dir=None):
        """Display versions for an output.

        Args:
            output: Output object.
            shot_dir: Path to the shot directory (for resolving absolute paths).
        """
        self._output = output
        self._shot_dir = shot_dir
        self._set_enabled(True)

        # Detect if viewing _Incoming (no shot_dir or output.shot == "_Incoming")
        is_incoming = (shot_dir is None or output.shot == "_Incoming")

        # Hide Create Read button for _Incoming (Open Folder still works)
        if self._create_read_btn:
            self._create_read_btn.setVisible(not is_incoming)

        # Populate version combo
        self._version_combo.blockSignals(True)
        self._version_combo.clear()

        # Add LIVE entry if applicable
        if output.live_version is not None:
            self._version_combo.addItem(
                f"LIVE (v{output.live_version:03d})",
                output.live_version
            )

        # Add all versions in reverse order (newest first)
        for ver in sorted(output.versions, key=lambda v: v.version, reverse=True):
            self._version_combo.addItem(f"v{ver.version:03d}", ver.version)

        self._version_combo.blockSignals(False)

        # Select LIVE or latest
        if self._version_combo.count() > 0:
            self._version_combo.setCurrentIndex(0)
            self._on_version_changed(0)

    def _on_version_changed(self, index):
        """Handle version selection change."""
        if self._output is None or index < 0:
            return

        version_number = self._version_combo.itemData(index)
        version = self._output.get_version(version_number)
        if version is None:
            return

        self._current_version = version

        # Update LIVE indicator
        is_live = self._output.live_version == version.version
        if is_live:
            self._live_label.setText("LIVE")
        else:
            self._live_label.clear()

        # Update Create Read button default action (Nuke-only)
        if self._create_read_btn is not None:
            if is_live:
                # Viewing LIVE version → default to LIVE Read (auto-tracks updates)
                self._create_read_btn.setDefaultAction(self._create_live_action)
            else:
                # Viewing non-LIVE version → default to static Read
                self._create_read_btn.setDefaultAction(self._create_static_action)

        # Update metadata
        self._date_label.setText(version.created)
        self._creator_label.setText(version.creator)

        if version.frames:
            frame_count = version.frames[1] - version.frames[0] + 1
            self._frames_label.setText(
                f"{version.frames[0]} - {version.frames[1]} ({frame_count} frames)"
            )
        else:
            self._frames_label.setText("N/A")

        self._format_label.setText(version.format or "Unknown")
        self._source_label.setText(version.source_work or "N/A")
        self._path_label.setText(version.path or "N/A")
        self._notes_text.setPlainText(version.notes)

        # Check if files exist on disk
        files_exist = self._check_files_exist(version)
        if not files_exist:
            self._version_combo.setStyleSheet("color: #ff6666;")
            self._frames_label.setText("⚠ FILES MISSING")
        else:
            self._version_combo.setStyleSheet("")

        # Try to load thumbnail
        self._load_thumbnail(version)

    def _load_thumbnail(self, version):
        """Load cached thumbnail or generate one in Nuke, with text fallback."""
        from .. import thumbnails

        if not version.path:
            self._thumbnail_label.setPixmap(QtGui.QPixmap())
            self._thumbnail_label.setText("No preview")
            return

        # Resolve file_path — same logic as _check_files_exist
        if self._shot_dir is None:
            file_path = Path(version.path)
        else:
            from ..core import OutputType
            from .. import paths as path_module
            if self._output.output_type == OutputType.REFERENCE:
                output_dir = Path(self._shot_dir) / self._output.name
            else:
                output_dir = path_module.get_output_dir(
                    self._shot_dir, self._output.output_type, self._output.name
                )
            file_path = output_dir / version.path

        thumbnail_path = thumbnails.get_thumbnail_path(file_path.parent)

        if thumbnail_path.exists():
            self._set_thumbnail_pixmap(thumbnail_path)
            return

        # Lazy Nuke generation (fallback for pre-existing renders and _Incoming)
        try:
            import nuke  # noqa: F401
            frame = (
                (version.frames[0] + version.frames[1]) // 2
                if version.frames else 1
            )
            result = thumbnails.generate_thumbnail(file_path, frame)
            if result and result.exists():
                self._set_thumbnail_pixmap(result)
                return
        except ImportError:
            pass

        # Standalone / generation failed
        self._thumbnail_label.setPixmap(QtGui.QPixmap())
        self._thumbnail_label.setText(f"{self._output.name}\nv{version.version:03d}")

    def _set_thumbnail_pixmap(self, path: Path):
        """Scale and display a thumbnail image in the thumbnail label."""
        pixmap = QtGui.QPixmap(str(path))
        if pixmap.isNull():
            self._thumbnail_label.setText("No preview")
            return
        w = max(self._thumbnail_label.width(), 256)
        h = max(self._thumbnail_label.height(), 200)
        scaled = pixmap.scaled(
            w, h,
            QtCore.Qt.KeepAspectRatio,
            QtCore.Qt.SmoothTransformation,
        )
        self._thumbnail_label.setPixmap(scaled)
        self._thumbnail_label.setText("")

    def _check_files_exist(self, version) -> bool:
        """Check if the version's files exist on disk."""
        import re

        if not version.path:
            return True

        def _resolve_frame(pattern_path, frame):
            name = pattern_path.name
            resolved = re.sub(r'#+', lambda m: str(frame).zfill(len(m.group(0))), name)
            return pattern_path.parent / resolved

        if self._shot_dir is None:
            file_path = Path(version.path)
        else:
            from ..core import OutputType
            from .. import paths as path_module
            if self._output.output_type == OutputType.REFERENCE:
                output_dir = Path(self._shot_dir) / self._output.name
            else:
                output_dir = path_module.get_output_dir(
                    self._shot_dir, self._output.output_type, self._output.name
                )
            file_path = output_dir / version.path

        if version.frames:
            first = _resolve_frame(file_path, version.frames[0])
            last = _resolve_frame(file_path, version.frames[1])
            return first.exists() and last.exists()
        else:
            return file_path.exists()

    def _on_set_live(self):
        """Set the currently viewed version as LIVE."""
        if self._output is None or self._current_version is None:
            return
        self.live_changed.emit(self._output, self._current_version.version)

        # Refresh the combo to show updated LIVE
        self.set_output(self._output, self._shot_dir)

    def _on_open_folder(self):
        """Open the version folder in the system file explorer."""
        if self._output is None or self._current_version is None:
            return

        if self._shot_dir is None:
            # _Incoming items: version.path is already absolute
            path = Path(self._current_version.path)
            # If it's a file, open its parent directory
            if path.is_file():
                path = path.parent
            if path.exists():
                os.startfile(str(path))
        else:
            # Shot or Reference outputs: calculate version_dir from base directory
            from ..core import OutputType
            from .. import paths as path_module

            if self._output.output_type == OutputType.REFERENCE:
                # Reference outputs: simpler structure {reference_dir}/{output_name}/v001/
                version_dir = Path(self._shot_dir) / self._output.name / f"v{self._current_version.version:03d}"
            else:
                # Shot outputs: use standard path calculation
                version_dir = path_module.get_version_dir(
                    self._shot_dir, self._output.output_type,
                    self._output.name, self._current_version.version
                )

            if version_dir.exists():
                os.startfile(str(version_dir))

    # ------------------------------------------------------------------
    # Nuke Read node creation
    # ------------------------------------------------------------------

    def _on_create_static_read(self):
        """Create a Read node with static path to the current version."""
        if self._output is None or self._current_version is None:
            return
        if self._shot_dir is None:
            return

        try:
            from .. import nuke_read, paths as path_module

            version_dir = path_module.get_version_dir(
                self._shot_dir, self._output.output_type,
                self._output.name, self._current_version.version
            )

            # Build file path from version.path (relative pattern)
            if not self._current_version.path:
                QtWidgets.QMessageBox.warning(
                    self, "No Path",
                    f"Version v{self._current_version.version:03d} has no file path set."
                )
                return

            # Resolve the path: output_dir + version.path
            from .. import paths as path_module
            output_dir = path_module.get_output_dir(
                self._shot_dir, self._output.output_type, self._output.name
            )
            file_path = output_dir / self._current_version.path

            # Get frame range
            if self._current_version.frames:
                first_frame, last_frame = self._current_version.frames
            else:
                first_frame = last_frame = 1001

            # Create the Read node
            node = nuke_read.create_read_node(
                file_path=file_path,
                first_frame=first_frame,
                last_frame=last_frame,
                name=f"{self._output.name}_v{self._current_version.version:03d}"
            )

            QtWidgets.QMessageBox.information(
                self, "Read Node Created",
                f"Created Read node '{node.name()}' for {self._output.name} v{self._current_version.version:03d}."
            )

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Error",
                f"Failed to create Read node:\n\n{e}"
            )

    def _on_create_live_read(self):
        """Create a LIVE Read node with expression-based auto-tracking."""
        if self._output is None:
            return
        if self._shot_dir is None:
            return

        if self._output.live_version is None:
            QtWidgets.QMessageBox.warning(
                self, "No LIVE Version",
                f"Output '{self._output.name}' has no LIVE version set.\n\n"
                "Set a version as LIVE first, then create the LIVE Read node."
            )
            return

        try:
            from .. import nuke_read, paths as path_module

            output_dir = path_module.get_output_dir(
                self._shot_dir, self._output.output_type, self._output.name
            )

            # Create the LIVE Read node
            node = nuke_read.create_live_read_node(
                output_dir=output_dir,
                output=self._output,
                name=f"{self._output.name}_LIVE"
            )

            QtWidgets.QMessageBox.information(
                self, "LIVE Read Created",
                f"Created LIVE Read node '{node.name()}' for {self._output.name}.\n\n"
                f"This node will automatically track LIVE version changes."
            )

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Error",
                f"Failed to create LIVE Read node:\n\n{e}"
            )

    def _on_update_existing_read(self):
        """Show dialog to pick an existing Read node and update it."""
        if self._output is None or self._current_version is None:
            return
        if self._shot_dir is None:
            return

        try:
            from .. import nuke_read, paths as path_module

            # Find all Read nodes
            read_nodes = nuke_read.find_read_nodes()
            if not read_nodes:
                QtWidgets.QMessageBox.information(
                    self, "No Read Nodes",
                    "No Read nodes found in the script."
                )
                return

            # Show picker dialog
            node_labels = [r['display'] for r in read_nodes]
            chosen, ok = QtWidgets.QInputDialog.getItem(
                self, "Update Read Node",
                "Select a Read node to update:",
                node_labels, 0, False
            )
            if not ok:
                return

            # Find the selected node
            idx = node_labels.index(chosen)
            selected_node = read_nodes[idx]["node"]

            # Build file path
            output_dir = path_module.get_output_dir(
                self._shot_dir, self._output.output_type, self._output.name
            )
            file_path = output_dir / self._current_version.path

            # Get frame range
            if self._current_version.frames:
                first_frame, last_frame = self._current_version.frames
            else:
                first_frame = last_frame = 1001

            # Update the node
            nuke_read.update_read_node(
                node=selected_node,
                file_path=file_path,
                first_frame=first_frame,
                last_frame=last_frame
            )

            QtWidgets.QMessageBox.information(
                self, "Read Node Updated",
                f"Updated '{selected_node.name()}' to {self._output.name} v{self._current_version.version:03d}."
            )

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Error",
                f"Failed to update Read node:\n\n{e}"
            )
