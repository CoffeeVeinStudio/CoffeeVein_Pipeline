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
    frames_move_requested = QtCore.Signal(object, list, object)  # (Output, [abs_paths], shot_dir)
    meta_changed = QtCore.Signal(object)  # (Output) — meta dict was modified, save needed

    def __init__(self, parent=None):
        super().__init__(parent)
        self._output = None
        self._shot_dir = None
        self._current_version = None
        self._fallback_dir = None
        # Scene mode state
        self._mode = "output"  # "output" or "scene"
        self._scene_work = None
        self._scenes_dir = None
        self._shot_dir_for_scene = None
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
        _sp = self._source_label.sizePolicy()
        _sp.setHorizontalPolicy(QtWidgets.QSizePolicy.Ignored)
        self._source_label.setSizePolicy(_sp)
        info_layout.addRow("Source:", self._source_label)

        self._path_label = QtWidgets.QLabel()
        self._path_label.setWordWrap(True)
        self._path_label.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse)
        _sp = self._path_label.sizePolicy()
        _sp.setHorizontalPolicy(QtWidgets.QSizePolicy.Ignored)
        self._path_label.setSizePolicy(_sp)
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

        # Frame list toggle (only shown for image sequences)
        self._frames_toggle = QtWidgets.QCheckBox("Show individual frames")
        self._frames_toggle.toggled.connect(self._on_frames_toggle_changed)
        self._frames_toggle.setVisible(False)
        layout.addWidget(self._frames_toggle)

        self._frame_list = QtWidgets.QListWidget()
        self._frame_list.setMaximumHeight(180)
        self._frame_list.setVisible(False)
        self._frame_list.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        self._frame_list.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self._frame_list.customContextMenuRequested.connect(self._on_frame_context_menu)
        layout.addWidget(self._frame_list)

        # Thumbnail area
        self._thumbnail_label = QtWidgets.QLabel()
        self._thumbnail_label.setAlignment(QtCore.Qt.AlignCenter)
        self._thumbnail_label.setMinimumHeight(200)
        self._thumbnail_label.setStyleSheet(
            "background-color: #1a1a1a; border: 1px solid #333;"
        )
        self._thumbnail_label.setText("No preview")
        _sp = self._thumbnail_label.sizePolicy()
        _sp.setHorizontalPolicy(QtWidgets.QSizePolicy.Ignored)
        self._thumbnail_label.setSizePolicy(_sp)
        self._thumbnail_label.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        self._thumbnail_label.customContextMenuRequested.connect(self._on_thumb_context_menu)
        layout.addWidget(self._thumbnail_label, stretch=1)

        # Action buttons
        btn_row = QtWidgets.QHBoxLayout()

        self._open_folder_btn = QtWidgets.QPushButton("Open Folder")
        self._open_folder_btn.clicked.connect(self._on_open_folder)
        btn_row.addWidget(self._open_folder_btn)

        # Open in Nuke button (scene mode only, Nuke-only)
        self._open_scene_btn = None
        try:
            import nuke  # noqa: F401
            self._open_scene_btn = QtWidgets.QPushButton("Open in Nuke")
            self._open_scene_btn.setStyleSheet(
                "QPushButton { background-color: #2d5a7b; padding: 4px 12px; }"
                "QPushButton:hover { background-color: #3d7aab; }"
            )
            self._open_scene_btn.clicked.connect(self._on_open_scene)
            self._open_scene_btn.setVisible(False)
            btn_row.addWidget(self._open_scene_btn)
        except ImportError:
            pass

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

            read_menu.addSeparator()

            self._create_geo_action = read_menu.addAction("Create ReadGeo")
            self._create_geo_action.triggered.connect(self._on_create_geo_read)

            self._create_deep_action = read_menu.addAction("Create ReadDeep")
            self._create_deep_action.triggered.connect(self._on_create_deep_read)

            self._create_camera_action = read_menu.addAction("Create Camera")
            self._create_camera_action.triggered.connect(self._on_create_camera_read)

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
        """Enable/disable all controls except Open Folder (always enabled)."""
        self._version_combo.setEnabled(enabled)
        self._set_live_btn.setEnabled(enabled)
        if self._create_read_btn:
            self._create_read_btn.setEnabled(enabled)

    def set_fallback_dir(self, path):
        """Set the directory opened when no output is selected."""
        self._fallback_dir = path

    def clear(self):
        """Clear all version info."""
        self._output = None
        self._scene_work = None
        self._scenes_dir = None
        self._shot_dir_for_scene = None
        self._mode = "output"
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
        self._frames_toggle.setChecked(False)
        self._frames_toggle.setVisible(False)
        self._frame_list.clear()
        self._frame_list.setVisible(False)
        self._set_enabled(False)
        self._set_live_btn.setVisible(True)
        if self._open_scene_btn:
            self._open_scene_btn.setVisible(False)
        if self._create_read_btn:
            self._create_read_btn.setVisible(True)

    def set_scene_work(self, work, scenes_dir, shot_dir=None):
        """Display versions for a SceneWork in scene mode.

        Switches the panel to scene mode: hides Set LIVE and Create Read,
        shows Open in Nuke. Populates the version combo with SceneVersions.

        Args:
            work: SceneWork object.
            scenes_dir: Path to the shot's Comp/scenes/ directory.
            shot_dir: Path to the shot root (used to find render thumbnails).
        """
        self._mode = "scene"
        self._scene_work = work
        self._scenes_dir = scenes_dir
        self._shot_dir_for_scene = Path(shot_dir) if shot_dir else None
        self._output = None
        self._set_enabled(True)

        # Toggle scene-mode buttons
        self._set_live_btn.setVisible(False)
        if self._open_scene_btn:
            self._open_scene_btn.setVisible(True)
        if self._create_read_btn:
            self._create_read_btn.setVisible(False)

        # Hide sequence-specific widgets
        self._frames_toggle.setVisible(False)
        self._frame_list.setVisible(False)
        self._live_label.clear()

        # Populate version combo (newest first)
        self._version_combo.blockSignals(True)
        self._version_combo.clear()
        for ver in sorted(work.versions, key=lambda v: v.version, reverse=True):
            self._version_combo.addItem(f"v{ver.version:03d}", ver.version)
        self._version_combo.blockSignals(False)

        if self._version_combo.count() > 0:
            self._version_combo.setCurrentIndex(0)
            self._on_scene_version_changed(0)

    def _on_scene_version_changed(self, index):
        """Handle version combo change in scene mode."""
        if self._scene_work is None or index < 0:
            return
        version_number = self._version_combo.itemData(index)
        version = self._scene_work.get_version(version_number)
        if version is None:
            return

        self._current_version = version
        self._date_label.setText(version.created)
        self._creator_label.setText(version.creator)
        meta = version.meta or {}
        if meta.get("root_first") is not None:
            rf = meta["root_first"]
            rl = meta["root_last"]
            h = meta.get("handles", 0)
            frames_text = f"{rf}–{rl}"
            if h:
                frames_text += f"  (+{h} handles)"
            self._frames_label.setText(frames_text)
        else:
            self._frames_label.setText("N/A")
        self._format_label.setText(version.dcc.upper() if version.dcc else "")
        self._source_label.setText("")

        # Resolve and display the file path
        from .. import scene_database
        file_path = scene_database.get_scene_version_path(self._scenes_dir, version)
        if file_path:
            self._path_label.setText(str(file_path))
            exists = file_path.exists()
            self._version_combo.setStyleSheet("" if exists else "color: #ff6666;")
        else:
            self._path_label.setText("N/A")

        self._notes_text.setPlainText(version.notes)

        # Try to show the shot's latest render thumbnail; fall back to text
        thumb = self._find_scene_thumbnail()
        if thumb:
            self._set_thumbnail_pixmap(thumb)
        else:
            self._thumbnail_label.setPixmap(QtGui.QPixmap())
            self._thumbnail_label.setText(
                f"{self._scene_work.name}\nv{version.version:03d}"
            )

    def _find_scene_thumbnail(self):
        """Return the most-recently-modified thumbnail in the shot's output dirs, or None."""
        if not self._shot_dir_for_scene or not self._shot_dir_for_scene.is_dir():
            return None
        candidates = list(self._shot_dir_for_scene.rglob("*.thumbnail.jpg"))
        if not candidates:
            return None
        return max(candidates, key=lambda p: p.stat().st_mtime)

    def _on_open_scene(self):
        """Open the selected scene version in Nuke."""
        if self._scene_work is None or self._current_version is None:
            return
        from .. import scene_database
        from ..dcc import get_dcc
        file_path = scene_database.get_scene_version_path(
            self._scenes_dir, self._current_version
        )
        if not file_path or not file_path.exists():
            QtWidgets.QMessageBox.warning(
                self, "File Not Found", f"Scene file not found:\n{file_path}"
            )
            return
        get_dcc().open_scene(file_path)

    def set_frames_label(self, text):
        """Update the Frames label directly (used for async updates)."""
        self._frames_label.setText(text)

    def set_output(self, output, shot_dir=None):
        """Display versions for an output.

        Args:
            output: Output object.
            shot_dir: Path to the shot directory (for resolving absolute paths).
        """
        self._mode = "output"
        self._output = output
        self._shot_dir = shot_dir
        self._set_enabled(True)

        # Reset scene-mode button visibility
        self._set_live_btn.setVisible(True)
        if self._open_scene_btn:
            self._open_scene_btn.setVisible(False)

        # Detect if viewing _Incoming (no shot_dir or output.shot == "_Incoming")
        is_incoming = (shot_dir is None or output.shot == "Incoming")

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
        if self._mode == "scene":
            self._on_scene_version_changed(index)
            return
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

        has_sequence = bool(version.frames)
        meta = version.meta or {}
        if meta.get("root_first") is not None:
            rf = meta["root_first"]
            rl = meta["root_last"]
            h = meta.get("handles", 0)
            frames_text = f"{rf}–{rl}"
            if h:
                frames_text += f"  (+{h} handles)"
            self._frames_label.setText(frames_text)
        elif has_sequence:
            frame_count = version.frames[1] - version.frames[0] + 1
            self._frames_label.setText(
                f"{version.frames[0]} - {version.frames[1]} ({frame_count} frames)"
            )
        elif meta.get("mov_frames") is not None:
            count = meta["mov_frames"]
            self._frames_label.setText(f"1 - {count} ({count} frames)")
        elif meta.get("is_movie"):
            self._frames_label.setText("Detecting...")
        else:
            self._frames_label.setText("N/A")

        # Show frame list toggle only for sequences; auto-refresh if already open
        self._frames_toggle.setVisible(has_sequence)
        if not has_sequence:
            self._frames_toggle.setChecked(False)
            self._frame_list.setVisible(False)
        elif self._frames_toggle.isChecked():
            self._populate_frame_list(version)

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

    def _get_file_path(self, version) -> Path:
        """Resolve the absolute file path for a version."""
        if self._shot_dir is None:
            return Path(version.path)
        from ..core import OutputType
        from .. import paths as path_module
        if self._output.output_type == OutputType.REFERENCE:
            output_dir = Path(self._shot_dir) / self._output.name
        else:
            output_dir = path_module.get_output_dir(
                self._shot_dir, self._output.output_type, self._output.name
            )
        return output_dir / version.path

    def _load_thumbnail(self, version):
        """Load cached thumbnail or generate one in Nuke, with text fallback."""
        from .. import thumbnails

        if not version.path:
            self._thumbnail_label.setPixmap(QtGui.QPixmap())
            self._thumbnail_label.setText("No preview")
            return

        file_path = self._get_file_path(version)
        thumbnail_path = thumbnails.get_thumbnail_path(file_path)

        if thumbnail_path.exists():
            self._set_thumbnail_pixmap(thumbnail_path)
            return

        is_incoming = (self._shot_dir is None)

        # Only attempt generation for file types Nuke can read
        if not thumbnails.is_thumbnail_supported(file_path):
            self._thumbnail_label.setPixmap(QtGui.QPixmap())
            self._thumbnail_label.setText(f"{self._output.name}\nv{version.version:03d}")
            return

        # Skip if a previous attempt already failed
        if is_incoming:
            if thumbnails.get_thumbnail_failed_path(file_path).exists():
                self._thumbnail_label.setPixmap(QtGui.QPixmap())
                self._thumbnail_label.setText(f"{self._output.name}\nv{version.version:03d}")
                return
        elif version.meta.get("thumbnail_failed"):
            self._thumbnail_label.setPixmap(QtGui.QPixmap())
            self._thumbnail_label.setText(f"{self._output.name}\nv{version.version:03d}")
            return

        # Use a stored layer preference if one exists
        if is_incoming:
            layer_file = thumbnails.get_thumbnail_layer_path(file_path)
            stored_layer = layer_file.read_text().strip() if layer_file.exists() else None
        else:
            stored_layer = version.meta.get("thumbnail_layer")

        # Lazy Nuke generation
        try:
            import nuke  # noqa: F401
            frame = (
                (version.frames[0] + version.frames[1]) // 2
                if version.frames else 1
            )
            result = thumbnails.generate_thumbnail(file_path, frame, layer=stored_layer)
            if result and result.exists():
                self._set_thumbnail_pixmap(result)
                return
            # Record the failure so we don't retry on every selection
            if is_incoming:
                try:
                    thumbnails.get_thumbnail_failed_path(file_path).touch()
                except Exception:
                    pass
            else:
                version.meta["thumbnail_failed"] = True
                self.meta_changed.emit(self._output)
        except ImportError:
            pass

        # Fallback to text
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

        file_path = self._get_file_path(version)

        if version.frames:
            first = _resolve_frame(file_path, version.frames[0])
            last = _resolve_frame(file_path, version.frames[1])
            return first.exists() and last.exists()
        else:
            return file_path.exists()

    def _on_frame_context_menu(self, pos):
        selected = self._frame_list.selectedItems()
        if not selected or self._output is None:
            return

        file_paths = [item.data(QtCore.Qt.UserRole) for item in selected]

        menu = QtWidgets.QMenu(self)
        count = len(file_paths)
        label = f"Move {count} frame{'s' if count > 1 else ''} to Shot..."
        move_action = menu.addAction(label)
        action = menu.exec_(self._frame_list.viewport().mapToGlobal(pos))

        if action == move_action:
            self.frames_move_requested.emit(self._output, file_paths, self._shot_dir)

    def _on_thumb_context_menu(self, pos):
        if self._current_version is None or self._output is None:
            return
        try:
            import nuke  # noqa: F401
        except ImportError:
            return
        from .. import thumbnails
        file_path = self._get_file_path(self._current_version)
        if not thumbnails.is_thumbnail_supported(file_path):
            return

        menu = QtWidgets.QMenu(self)
        action = menu.addAction("Create thumbnail from Layer...")
        if menu.exec_(self._thumbnail_label.mapToGlobal(pos)) == action:
            frame = (
                (self._current_version.frames[0] + self._current_version.frames[1]) // 2
                if self._current_version.frames else 1
            )
            self._create_thumbnail_from_layer(file_path, frame)

    def _create_thumbnail_from_layer(self, file_path, frame):
        import nuke
        from .. import thumbnails

        read = None
        try:
            read = nuke.nodes.Read(file=str(file_path).replace('\\', '/'))
            layers = nuke.layers(read)
        except Exception as e:
            QtWidgets.QMessageBox.warning(
                self, "Layer Enumeration Failed",
                f"Could not read layers from file:\n{e}"
            )
            return
        finally:
            if read is not None:
                try:
                    nuke.delete(read)
                except Exception:
                    pass

        if not layers:
            QtWidgets.QMessageBox.information(self, "No Layers", "No layers found in the file.")
            return

        dialog = LayerSelectDialog(layers, parent=self)
        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return

        selected_layer = dialog.selected_layer()
        result = thumbnails.generate_thumbnail(file_path, frame, layer=selected_layer)
        is_incoming = (self._shot_dir is None)

        if result and result.exists():
            if is_incoming:
                try:
                    thumbnails.get_thumbnail_layer_path(file_path).write_text(selected_layer)
                    failed = thumbnails.get_thumbnail_failed_path(file_path)
                    if failed.exists():
                        failed.unlink()
                except Exception:
                    pass
            else:
                self._current_version.meta["thumbnail_layer"] = selected_layer
                self._current_version.meta.pop("thumbnail_failed", None)
                self.meta_changed.emit(self._output)
            self._load_thumbnail(self._current_version)
        else:
            QtWidgets.QMessageBox.warning(
                self, "Thumbnail Failed",
                f"Could not create thumbnail with layer '{selected_layer}'."
            )

    def _on_frames_toggle_changed(self, show_frames: bool):
        if show_frames and self._current_version and self._current_version.frames:
            self._populate_frame_list(self._current_version)
            self._frame_list.setVisible(True)
        else:
            self._frame_list.setVisible(False)

    def _populate_frame_list(self, version):
        import re
        self._frame_list.clear()

        if not version.path or not version.frames:
            return

        base_path = self._get_file_path(version)

        first, last = version.frames
        for frame in range(first, last + 1):
            filename = re.sub(
                r'#+',
                lambda m, f=frame: str(f).zfill(len(m.group(0))),
                base_path.name
            )
            full_path = str(base_path.parent / filename)
            item = QtWidgets.QListWidgetItem(filename)
            item.setToolTip(full_path)
            item.setData(QtCore.Qt.UserRole, full_path)
            self._frame_list.addItem(item)

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
            if self._fallback_dir:
                path = Path(self._fallback_dir)
                if path.exists():
                    os.startfile(str(path))
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
                name=f"{self._output.name}_v{self._current_version.version:03d}",
                output_dir=output_dir,
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

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Error",
                f"Failed to update Read node:\n\n{e}"
            )

    def _on_create_geo_read(self):
        """Create a ReadGeo2 node for the current version's geometry file."""
        if self._output is None or self._current_version is None:
            return
        if self._shot_dir is None:
            return

        try:
            from .. import nuke_read, paths as path_module

            if not self._current_version.path:
                QtWidgets.QMessageBox.warning(
                    self, "No Path",
                    f"Version v{self._current_version.version:03d} has no file path set."
                )
                return

            output_dir = path_module.get_output_dir(
                self._shot_dir, self._output.output_type, self._output.name
            )
            file_path = output_dir / self._current_version.path

            node = nuke_read.create_geo_read_node(
                file_path=file_path,
                name=f"{self._output.name}_v{self._current_version.version:03d}",
            )

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Error",
                f"Failed to create ReadGeo node:\n\n{e}"
            )

    def _on_create_deep_read(self):
        """Create a DeepRead node for the current version's deep image file."""
        if self._output is None or self._current_version is None:
            return
        if self._shot_dir is None:
            return

        try:
            from .. import nuke_read, paths as path_module

            if not self._current_version.path:
                QtWidgets.QMessageBox.warning(
                    self, "No Path",
                    f"Version v{self._current_version.version:03d} has no file path set."
                )
                return

            output_dir = path_module.get_output_dir(
                self._shot_dir, self._output.output_type, self._output.name
            )
            file_path = output_dir / self._current_version.path

            if self._current_version.frames:
                first_frame, last_frame = self._current_version.frames
            else:
                first_frame = last_frame = 1001

            node = nuke_read.create_deep_read_node(
                file_path=file_path,
                first_frame=first_frame,
                last_frame=last_frame,
                name=f"{self._output.name}_v{self._current_version.version:03d}",
            )

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Error",
                f"Failed to create DeepRead node:\n\n{e}"
            )

    def _on_create_camera_read(self):
        """Create a Camera2 node reading from the current version's camera file."""
        if self._output is None or self._current_version is None:
            return
        if self._shot_dir is None:
            return

        try:
            from .. import nuke_read, paths as path_module

            if not self._current_version.path:
                QtWidgets.QMessageBox.warning(
                    self, "No Path",
                    f"Version v{self._current_version.version:03d} has no file path set."
                )
                return

            output_dir = path_module.get_output_dir(
                self._shot_dir, self._output.output_type, self._output.name
            )
            file_path = output_dir / self._current_version.path

            nuke_read.create_camera_read_node(
                file_path=file_path,
                name=f"{self._output.name}_v{self._current_version.version:03d}",
            )

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Error",
                f"Failed to create Camera node:\n\n{e}"
            )


class LayerSelectDialog(QtWidgets.QDialog):
    """Dialog for selecting an EXR layer to use for thumbnail generation."""

    def __init__(self, layers, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Select Layer for Thumbnail")
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel("Select layer for thumbnail:"))
        self._combo = QtWidgets.QComboBox()
        self._combo.addItems(layers)
        layout.addWidget(self._combo)
        btns = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
        )
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def selected_layer(self):
        return self._combo.currentText()
