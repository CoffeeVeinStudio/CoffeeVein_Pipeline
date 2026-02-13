"""Main window for CoffeeVein Shot Manager.

Works both standalone and inside Nuke. When running inside Nuke,
shows additional render controls at the bottom.
"""

from pathlib import Path

from ..qt_compat import QtWidgets, QtCore, QtGui

from ..core import OutputType, Shot, Output
from .. import paths, database
from .shot_list import ShotListWidget
from .output_list import OutputListWidget
from .version_panel import VersionPanel


def is_nuke_available():
    """Check if we're running inside Nuke."""
    try:
        import nuke
        return True
    except ImportError:
        return False


class ShotManagerWindow(QtWidgets.QMainWindow):
    """Main Shot Manager window."""

    def __init__(self, project_root=None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("CoffeeVein Shot Manager")
        self.setMinimumSize(900, 600)

        self._project_root = None
        self._current_shot = None
        self._current_output = None
        self._viewing_incoming = False
        self._incoming_items = {}  # output.name → IncomingItem mapping
        self._in_nuke = is_nuke_available()

        self._build_ui()
        self._connect_signals()

        if project_root:
            self.set_project(project_root)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------

    def _build_ui(self):
        """Build the main UI layout."""
        central = QtWidgets.QWidget()
        self.setCentralWidget(central)
        main_layout = QtWidgets.QVBoxLayout(central)
        main_layout.setContentsMargins(4, 4, 4, 4)

        # Header
        header = QtWidgets.QHBoxLayout()
        header.addWidget(QtWidgets.QLabel("Project:"))
        self._project_label = QtWidgets.QLabel("(none)")
        self._project_label.setStyleSheet("font-weight: bold; font-size: 13px;")
        header.addWidget(self._project_label)
        header.addStretch()

        self._refresh_btn = QtWidgets.QPushButton("Refresh")
        self._refresh_btn.clicked.connect(self._on_refresh)
        header.addWidget(self._refresh_btn)

        self._set_project_btn = QtWidgets.QPushButton("Set Project")
        self._set_project_btn.clicked.connect(self._on_set_project)
        header.addWidget(self._set_project_btn)
        main_layout.addLayout(header)

        # Main splitter: Shots | Outputs | Versions
        self._splitter = QtWidgets.QSplitter(QtCore.Qt.Horizontal)
        main_layout.addWidget(self._splitter, stretch=1)

        # Shot list (left panel)
        self._shot_list = ShotListWidget()
        self._splitter.addWidget(self._shot_list)

        # Output list (middle panel)
        self._output_list = OutputListWidget()
        self._splitter.addWidget(self._output_list)

        # Version panel (right panel)
        self._version_panel = VersionPanel()
        self._splitter.addWidget(self._version_panel)

        self._splitter.setSizes([200, 200, 400])

        # _Incoming action bar (hidden by default)
        self._incoming_bar = QtWidgets.QHBoxLayout()
        self._incoming_bar_widget = QtWidgets.QWidget()
        incoming_bar_inner = QtWidgets.QHBoxLayout(self._incoming_bar_widget)
        incoming_bar_inner.setContentsMargins(0, 4, 0, 4)

        self._move_to_shot_btn = QtWidgets.QPushButton("Move to Shot")
        self._move_to_shot_btn.setStyleSheet(
            "QPushButton { background-color: #5a7b2d; padding: 6px 16px; }"
            "QPushButton:hover { background-color: #7aab3d; }"
        )
        self._move_to_shot_btn.clicked.connect(self._on_move_to_shot)
        incoming_bar_inner.addWidget(self._move_to_shot_btn)
        incoming_bar_inner.addStretch()

        main_layout.addWidget(self._incoming_bar_widget)
        self._incoming_bar_widget.setVisible(False)

        # Nuke render controls (bottom bar, only in Nuke)
        if self._in_nuke:
            self._build_nuke_controls(main_layout)

    def _build_nuke_controls(self, parent_layout):
        """Build the Nuke-specific render controls bar."""
        separator = QtWidgets.QFrame()
        separator.setFrameShape(QtWidgets.QFrame.HLine)
        parent_layout.addWidget(separator)

        nuke_bar = QtWidgets.QHBoxLayout()

        nuke_label = QtWidgets.QLabel("Nuke:")
        nuke_label.setStyleSheet("font-weight: bold; color: #47a3cb;")
        nuke_bar.addWidget(nuke_label)

        # === FRAME RANGE CONTROLS ===
        frame_label = QtWidgets.QLabel("Frame range:")
        nuke_bar.addWidget(frame_label)

        # Radio buttons for mode selection
        self._frame_mode_inout = QtWidgets.QRadioButton("In/Out")
        self._frame_mode_inout.setChecked(True)  # Default
        self._frame_mode_inout.toggled.connect(self._on_frame_mode_changed)
        nuke_bar.addWidget(self._frame_mode_inout)

        self._frame_mode_full = QtWidgets.QRadioButton("Full")
        self._frame_mode_full.toggled.connect(self._on_frame_mode_changed)
        nuke_bar.addWidget(self._frame_mode_full)

        self._frame_mode_custom = QtWidgets.QRadioButton("Custom")
        self._frame_mode_custom.toggled.connect(self._on_frame_mode_changed)
        nuke_bar.addWidget(self._frame_mode_custom)

        # Spinboxes for frame range
        self._frame_start_spin = QtWidgets.QSpinBox()
        self._frame_start_spin.setRange(0, 999999)
        self._frame_start_spin.setValue(1001)
        self._frame_start_spin.setMinimumWidth(70)
        nuke_bar.addWidget(self._frame_start_spin)

        nuke_bar.addWidget(QtWidgets.QLabel("—"))

        self._frame_end_spin = QtWidgets.QSpinBox()
        self._frame_end_spin.setRange(0, 999999)
        self._frame_end_spin.setValue(1100)
        self._frame_end_spin.setMinimumWidth(70)
        nuke_bar.addWidget(self._frame_end_spin)

        # Reset/refresh button
        self._frame_reset_btn = QtWidgets.QPushButton("↻")
        self._frame_reset_btn.setMaximumWidth(30)
        self._frame_reset_btn.setToolTip("Refresh from Nuke")
        self._frame_reset_btn.clicked.connect(self._on_reset_frame_range)
        nuke_bar.addWidget(self._frame_reset_btn)

        nuke_bar.addSpacing(20)
        # === END FRAME RANGE CONTROLS ===

        self._render_selected_btn = QtWidgets.QPushButton("Render Selected Write Node")
        self._render_selected_btn.setStyleSheet(
            "QPushButton { background-color: #2d5a7b; padding: 6px 16px; }"
            "QPushButton:hover { background-color: #3d7aab; }"
        )
        self._render_selected_btn.clicked.connect(self._on_render_selected)
        nuke_bar.addWidget(self._render_selected_btn)

        nuke_bar.addStretch()

        self._rerender_btn = QtWidgets.QPushButton("Re-Render Last")
        self._rerender_btn.setStyleSheet(
            "QPushButton { background-color: #5a5a2d; padding: 6px 16px; }"
            "QPushButton:hover { background-color: #7a7a3d; }"
        )
        self._rerender_btn.clicked.connect(self._on_rerender_last)
        nuke_bar.addWidget(self._rerender_btn)

        parent_layout.addLayout(nuke_bar)

    # ------------------------------------------------------------------
    # Signals
    # ------------------------------------------------------------------

    def _connect_signals(self):
        """Connect widget signals."""
        self._shot_list.shot_selected.connect(self._on_shot_selected)
        self._shot_list.incoming_selected.connect(self._on_incoming_selected)
        self._output_list.output_selected.connect(self._on_output_selected)
        self._version_panel.live_changed.connect(self._on_live_changed)

    # ------------------------------------------------------------------
    # Project management
    # ------------------------------------------------------------------

    def set_project(self, project_root):
        """Set the active project and refresh the shot list."""
        self._project_root = Path(project_root)
        project_name = paths.get_project_name(self._project_root)
        self._project_label.setText(project_name)
        self.setWindowTitle(f"CoffeeVein Shot Manager — {project_name}")
        self._refresh_shots()

        # Auto-detect current shot from Nuke script
        if self._in_nuke:
            self._auto_select_nuke_shot()
            # Initialize frame range controls
            self._on_frame_mode_changed()

    def _on_set_project(self):
        """Let user pick a project directory."""
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self, "Select Project Root"
        )
        if folder:
            # Verify it's a TIK project
            if (Path(folder) / "tikDatabase").exists():
                self.set_project(folder)
            else:
                QtWidgets.QMessageBox.warning(
                    self, "Not a TIK Project",
                    "Selected folder does not contain a tikDatabase directory."
                )

    def _on_refresh(self):
        """Refresh the shot list and current view."""
        self._refresh_shots()
        if self._viewing_incoming:
            incoming_dir = paths.get_incoming_dir(self._project_root)
            self._on_incoming_selected(str(incoming_dir))
        elif self._current_shot:
            self._refresh_outputs(self._current_shot[1])

    # ------------------------------------------------------------------
    # Shot selection
    # ------------------------------------------------------------------

    def _refresh_shots(self):
        """Reload the shot list from disk."""
        if self._project_root is None:
            return
        shots = paths.discover_shots(self._project_root)
        self._shot_list.set_shots(shots)

        # Ensure _Incoming subdirs exist and scan
        from .. import incoming as incoming_module
        incoming_dir = paths.get_incoming_dir(self._project_root)
        if incoming_dir.exists():
            incoming_module.create_incoming_dirs(str(self._project_root))
            items = incoming_module.scan_incoming(str(self._project_root))
            self._shot_list.set_incoming(str(incoming_dir), len(items))

    def _auto_select_nuke_shot(self):
        """Auto-detect the current shot from the open Nuke script and select it."""
        try:
            from .. import render as render_module
            project_root, shot_name, shot_dir = render_module.get_current_nuke_context()
            if shot_name and shot_dir:
                self._current_shot = (shot_name, str(shot_dir))
                self._shot_list.select_shot(shot_name)
                self._refresh_outputs(str(shot_dir))
        except Exception:
            pass

    def _get_render_shot(self):
        """Get the shot to render into.

        Uses auto-detected Nuke context (current script path) first,
        falls back to the UI-selected shot.

        Returns:
            (shot_name, shot_dir) tuple, or None if no shot can be determined.
        """
        # Always prefer detecting from the current Nuke script
        if self._in_nuke:
            try:
                from .. import render as render_module
                project_root, shot_name, shot_dir = render_module.get_current_nuke_context()
                if shot_name and shot_dir:
                    return (shot_name, str(shot_dir))
            except Exception:
                pass

        # Fall back to UI selection
        if self._current_shot:
            return self._current_shot

        return None

    def _on_shot_selected(self, shot_name, shot_path):
        """Handle shot selection — populate outputs."""
        self._viewing_incoming = False
        self._incoming_items.clear()
        self._current_shot = (shot_name, shot_path)
        self._incoming_bar_widget.setVisible(False)
        self._output_list.set_selection_mode(multi=False)
        self._refresh_outputs(shot_path)

    def _on_incoming_selected(self, incoming_path):
        """Handle _Incoming selection — show incoming items as outputs."""
        self._viewing_incoming = True
        self._current_shot = None
        self._incoming_items.clear()
        self._version_panel.clear()

        from .. import incoming as incoming_module
        items = incoming_module.scan_incoming(str(self._project_root))

        # Convert IncomingItems to pseudo-Output objects for display
        incoming_outputs = []
        for item in items:
            # Use suggested_type from subfolder, or UNSORTED for root-level items
            output_type = item.suggested_type if item.suggested_type else OutputType.UNSORTED

            # Build display label: show "Unsorted" warning for root-level items
            type_label = item.item_type
            if item.suggested_type is None:
                type_label = f"{item.item_type} (Unsorted)"

            output = Output(
                name=item.name,
                shot="_Incoming",
                output_type=output_type,
            )
            # Add a single pseudo-version with the item's info
            frames = list(item.frame_range) if item.frame_range else None
            output.add_version(
                notes=f"Type: {type_label}",
                frames=frames,
                fmt=item.extension.lstrip(".") if item.extension else "",
                path=item.path,
                creator="",
                set_live=False,
            )
            incoming_outputs.append(output)

            # Store mapping so we can look up the IncomingItem later
            self._incoming_items[item.name] = item

        self._output_list.set_selection_mode(multi=True)
        self._output_list.set_outputs(incoming_outputs)
        self._incoming_bar_widget.setVisible(True)

    def _on_move_to_shot(self):
        """Show ingest dialog and move selected _Incoming items to a shot."""
        from .. import incoming as incoming_module
        from .ingest_dialog import IngestDialog

        # Get selected outputs from the tree
        selected_outputs = self._output_list.get_selected_outputs()
        if not selected_outputs:
            QtWidgets.QMessageBox.information(
                self, "No Selection",
                "Select one or more items to move."
            )
            return

        # Resolve IncomingItems from the stored mapping
        pairs = []  # (Output, IncomingItem)
        for output in selected_outputs:
            item = self._incoming_items.get(output.name)
            if item is not None:
                pairs.append((output, item))

        if not pairs:
            return

        # Build suggested shot: try first item's guessed name, then Nuke context
        suggested_shot = None
        for _, item in pairs:
            if item.suggested_shot:
                suggested_shot = item.suggested_shot
                break
        if suggested_shot is None and self._in_nuke:
            try:
                from .. import render as render_module
                _, shot_name, _ = render_module.get_current_nuke_context()
                if shot_name:
                    suggested_shot = shot_name
            except Exception:
                pass

        shots = paths.discover_shots(self._project_root)
        dialog = IngestDialog(
            shots=shots,
            items=pairs,
            project_root=self._project_root,
            suggested_shot=suggested_shot,
            parent=self,
        )

        if dialog.exec_() != QtWidgets.QDialog.Accepted:
            return

        # Perform ingest for each item
        target_shot = dialog.target_shot_name
        notes = dialog.notes
        errors = []

        for i, (output, item) in enumerate(pairs):
            # Get destination name: single mode uses form field, batch uses per-row combo
            if len(pairs) == 1:
                output_name = dialog.output_name or item.name
            else:
                output_name = dialog.get_item_name(i) or item.name

            # Per-item type (batch mode has individual combos)
            output_type = dialog.get_item_type(i)

            try:
                incoming_module.ingest_item(
                    item=item,
                    project_root=str(self._project_root),
                    shot_name=target_shot,
                    output_name=output_name,
                    output_type=output_type,
                    notes=notes,
                )
            except Exception as e:
                errors.append(f"{item.name}: {e}")

        # Report results
        if errors:
            QtWidgets.QMessageBox.warning(
                self, "Ingest Errors",
                "Some items failed to move:\n\n" + "\n".join(errors)
            )
        else:
            count = len(pairs)
            success_msg = f"Moved {count} item{'s' if count > 1 else ''} to {target_shot}."

            # Create Read nodes if requested (Nuke-only)
            if dialog.create_reads and self._in_nuke:
                try:
                    from .. import nuke_read
                    shots_dir = paths.get_shots_dir(self._project_root)
                    shot_dir = shots_dir / target_shot

                    for i, (output, item) in enumerate(pairs):
                        output_name = dialog.get_item_name(i) or item.name
                        output_type = dialog.get_item_type(i)

                        # Load the ingested output to get version info
                        output_dir = paths.get_output_dir(shot_dir, output_type, output_name)
                        ingested_output = database.load_output(output_dir)

                        if ingested_output and ingested_output.versions:
                            version = ingested_output.versions[-1]  # Latest (just created)
                            file_path = output_dir / version.path
                            first_frame = version.frames[0] if version.frames else None
                            last_frame = version.frames[1] if version.frames else None

                            nuke_read.create_read_node(
                                file_path=file_path,
                                first_frame=first_frame,
                                last_frame=last_frame,
                                name=f"{output_name}_v{version.version:03d}"
                            )

                    success_msg += f"\n\nCreated {count} Read node{'s' if count > 1 else ''}."
                except Exception as e:
                    success_msg += f"\n\nWarning: Failed to create Read nodes:\n{e}"

            QtWidgets.QMessageBox.information(
                self, "Ingest Complete",
                success_msg
            )

        # Refresh _Incoming view
        incoming_dir = paths.get_incoming_dir(self._project_root)
        self._on_incoming_selected(str(incoming_dir))

    # ------------------------------------------------------------------
    # Output browsing
    # ------------------------------------------------------------------

    def _refresh_outputs(self, shot_dir):
        """Discover and display all outputs for a shot."""
        all_outputs = []

        for output_type in (OutputType.RENDER, OutputType.PLATE,
                            OutputType.CG, OutputType.REFERENCE):
            type_folder = OutputType.folder_for(output_type)
            outputs = database.discover_outputs(shot_dir, output_type, type_folder)
            for output in outputs:
                all_outputs.append(output)

        self._output_list.set_outputs(all_outputs)
        self._version_panel.clear()

    def _on_output_selected(self, output):
        """Handle output selection — show versions."""
        self._current_output = output
        shot_dir = self._current_shot[1] if self._current_shot else None
        self._version_panel.set_output(output, shot_dir)

    def _on_live_changed(self, output, version_number):
        """Handle LIVE version change."""
        if self._current_shot is None:
            return
        shot_dir = self._current_shot[1]
        output_dir = paths.get_output_dir(
            shot_dir, output.output_type, output.name
        )
        output.live_version = version_number
        database.save_output(output, output_dir)

        # Update LIVE junction/symlink
        self._update_live_link(shot_dir, output, version_number)

        # Update any LIVE Read nodes in the Nuke script
        if self._in_nuke:
            try:
                from .. import nuke_read
                nuke_read.update_live_readers(output_dir)
            except Exception as e:
                print(f"[ShotManager] Warning: Failed to update LIVE Read nodes: {e}")

        # Refresh the output list to update LIVE indicators
        self._output_list.update_output(output)

    def _update_live_link(self, shot_dir, output, version_number):
        """Update the LIVE directory junction/symlink."""
        import os
        import shutil

        live_dir = paths.get_live_dir(shot_dir, output.output_type, output.name)
        version_dir = paths.get_version_dir(
            shot_dir, output.output_type, output.name, version_number
        )

        # Remove existing LIVE
        if live_dir.exists() or live_dir.is_symlink():
            if live_dir.is_symlink() or _is_junction(live_dir):
                live_dir.rmdir()
            elif live_dir.is_dir():
                shutil.rmtree(live_dir)

        # Create new junction/symlink
        try:
            if os.name == "nt":
                import subprocess
                subprocess.run(
                    ["cmd", "/c", "mklink", "/J",
                     str(live_dir), str(version_dir)],
                    check=True, capture_output=True
                )
            else:
                live_dir.symlink_to(version_dir)
        except (OSError, Exception):
            pass  # LIVE link is nice-to-have, not critical

    # ------------------------------------------------------------------
    # Nuke render controls
    # ------------------------------------------------------------------

    def _on_frame_mode_changed(self):
        """Handle frame range mode change — auto-populate spinboxes."""
        import nuke

        try:
            if self._frame_mode_inout.isChecked():
                # Read viewer in/out points
                viewer = nuke.activeViewer()
                if viewer:
                    range_str = viewer.node().knob('frame_range').getValue()
                    # Parse "10-55" format
                    if range_str and '-' in range_str:
                        start, end = range_str.split('-')
                        self._frame_start_spin.setValue(int(start))
                        self._frame_end_spin.setValue(int(end))
                        self._frame_start_spin.setEnabled(False)
                        self._frame_end_spin.setEnabled(False)
                        return

                # No viewer or no in/out set — fall back to Full Range
                self._frame_mode_full.setChecked(True)
                return

            elif self._frame_mode_full.isChecked():
                # Use project timeline range
                first = int(nuke.root()["first_frame"].value())
                last = int(nuke.root()["last_frame"].value())
                self._frame_start_spin.setValue(first)
                self._frame_end_spin.setValue(last)
                self._frame_start_spin.setEnabled(False)
                self._frame_end_spin.setEnabled(False)

            elif self._frame_mode_custom.isChecked():
                # User can edit spinboxes directly
                self._frame_start_spin.setEnabled(True)
                self._frame_end_spin.setEnabled(True)

        except Exception as e:
            # Fallback to Full Range on any error
            print(f"[ShotManager] Frame range detection failed: {e}")
            self._frame_mode_full.setChecked(True)

    def _on_reset_frame_range(self):
        """Re-read frame range from Nuke based on current mode."""
        self._on_frame_mode_changed()

    def _get_frame_range(self):
        """Get the current frame range from UI spinboxes.

        Returns:
            Tuple of (start_frame, end_frame).
        """
        return (self._frame_start_spin.value(), self._frame_end_spin.value())

    def _on_render_selected(self):
        """Render the currently selected Write node(s) in Nuke."""
        if not self._in_nuke:
            return

        from .. import render as render_module

        write_nodes = render_module.get_selected_write_nodes()
        if not write_nodes:
            QtWidgets.QMessageBox.information(
                self, "No Write Nodes", "No Write nodes found to render."
            )
            return

        # Ask which node(s) to render if multiple
        if len(write_nodes) > 1:
            names = [n.name() for n in write_nodes]
            items = ["All"] + names
            chosen, ok = QtWidgets.QInputDialog.getItem(
                self, "Select Write Node", "Render which Write node?",
                items, 0, False
            )
            if not ok:
                return
            if chosen != "All":
                write_nodes = [n for n in write_nodes if n.name() == chosen]

        self._run_render(write_nodes)

    def _on_rerender_last(self):
        """Re-render the latest version of the selected Write node."""
        if not self._in_nuke:
            return

        from .. import render as render_module
        from .. import paths, database
        from ..core import OutputType
        import nuke

        # Get selected Write node
        write_nodes = render_module.get_selected_write_nodes()
        if not write_nodes:
            QtWidgets.QMessageBox.information(
                self, "No Write Nodes", "No Write nodes found to re-render."
            )
            return

        # If multiple nodes, ask user to pick one
        if len(write_nodes) > 1:
            names = [n.name() for n in write_nodes]
            chosen, ok = QtWidgets.QInputDialog.getItem(
                self, "Select Write Node", "Re-render which Write node?",
                names, 0, False
            )
            if not ok:
                return
            write_nodes = [n for n in write_nodes if n.name() == chosen]

        write_node = write_nodes[0]
        node_name = write_node.name()

        # Get shot context
        render_shot = self._get_render_shot()
        if render_shot is None:
            QtWidgets.QMessageBox.warning(
                self, "No Shot Detected",
                "Could not determine which shot to render into."
            )
            return
        shot_name, shot_dir = render_shot

        # Load output metadata to find latest version
        output_dir = paths.get_output_dir(shot_dir, OutputType.RENDER, node_name)
        output = database.load_output(output_dir)

        if output is None or not output.versions:
            QtWidgets.QMessageBox.information(
                self, "No Versions Found",
                f"No previous versions found for {node_name}.\n\n"
                f"Use 'Render Selected Write Node' to create the first version."
            )
            return

        # Find latest version
        latest_version = output.versions[-1]
        version_number = latest_version.version

        # Confirm with user
        status_str = latest_version.status
        if status_str == "incomplete":
            msg = (
                f"Re-render {node_name} v{version_number:03d}?\n\n"
                f"Status: {status_str.upper()}\n"
                f"This will continue the incomplete render."
            )
        else:
            msg = (
                f"Re-render {node_name} v{version_number:03d}?\n\n"
                f"This will OVERWRITE existing frames."
            )

        reply = QtWidgets.QMessageBox.question(
            self, "Confirm Re-Render", msg,
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        )
        if reply != QtWidgets.QMessageBox.Yes:
            return

        # Get notes (pre-fill with existing notes)
        notes, ok = QtWidgets.QInputDialog.getText(
            self, "Render Notes",
            f"Notes for v{version_number:03d} re-render:",
            text=latest_version.notes
        )
        if not ok:
            return

        # Get source work file
        script_path = nuke.root().name()
        source_work = Path(script_path).name if script_path else ""

        # Get frame range from UI
        start_frame, end_frame = self._get_frame_range()

        self._render_selected_btn.setEnabled(False)
        self._rerender_btn.setEnabled(False)

        try:
            job = render_module.RenderJob(
                write_node=write_node,
                project_root=str(self._project_root),
                shot_name=shot_name,
                shot_dir=shot_dir,
                start_frame=start_frame,
                end_frame=end_frame,
                notes=notes,
                source_work=source_work,
            )

            # Use overwrite mode (target existing version)
            job.prepare_overwrite(version_number, output)

            self.statusBar().showMessage(
                f"Re-rendering {node_name} v{version_number:03d}..."
            )

            job.set_progress_callback(self._on_render_progress)
            version = job.render()

            self.statusBar().showMessage(
                f"Re-rendered {node_name} v{version_number:03d}", 5000
            )

        except render_module.RenderCancelled as e:
            self.statusBar().showMessage(f"Re-render cancelled: {e}", 5000)
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Re-Render Error", f"Re-render failed:\n\n{e}"
            )
        finally:
            self._render_selected_btn.setEnabled(True)
            self._rerender_btn.setEnabled(True)

            # Refresh outputs to show updated version
            self._refresh_outputs(shot_dir)
            self._current_shot = (shot_name, shot_dir)
            self._shot_list.select_shot(shot_name)

    def _run_render(self, write_nodes):
        """Execute render for a list of Write nodes."""
        import nuke
        from .. import render as render_module

        # Auto-detect shot from Nuke script path
        render_shot = self._get_render_shot()
        if render_shot is None:
            QtWidgets.QMessageBox.warning(
                self, "No Shot Detected",
                "Could not determine which shot to render into.\n\n"
                "Make sure your Nuke script is saved inside a shot directory\n"
                "(e.g., .../Shots/A004_C020/Comp/nuke/...)."
            )
            return
        shot_name, shot_dir = render_shot

        # Get notes from user
        notes, ok = QtWidgets.QInputDialog.getText(
            self, "Render Notes",
            f"Notes for this render ({', '.join(n.name() for n in write_nodes)}):"
        )
        if not ok:
            return

        # Determine source work file
        script_path = nuke.root().name()
        source_work = Path(script_path).name if script_path else ""

        # Get frame range from UI
        start_frame, end_frame = self._get_frame_range()

        self._render_selected_btn.setEnabled(False)
        self._rerender_btn.setEnabled(False)

        try:
            for write_node in write_nodes:
                job = render_module.RenderJob(
                    write_node=write_node,
                    project_root=str(self._project_root),
                    shot_name=shot_name,
                    shot_dir=shot_dir,
                    start_frame=start_frame,
                    end_frame=end_frame,
                    notes=notes,
                    source_work=source_work,
                )

                job.prepare()

                self.statusBar().showMessage(
                    f"Rendering {write_node.name()} v{job.version_number:03d}..."
                )

                job.set_progress_callback(self._on_render_progress)
                version = job.render()

                self.statusBar().showMessage(
                    f"Rendered {write_node.name()} v{version.version:03d}",
                    5000
                )

        except render_module.RenderCancelled as e:
            self.statusBar().showMessage(f"Render cancelled: {e}", 5000)
        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Render Error", f"Render failed:\n\n{e}"
            )
        finally:
            self._render_selected_btn.setEnabled(True)
            self._rerender_btn.setEnabled(True)

            # Refresh outputs to show new version
            self._refresh_outputs(shot_dir)
            # Also update UI selection to match the rendered shot
            self._current_shot = (shot_name, shot_dir)
            self._shot_list.select_shot(shot_name)

    def _on_render_progress(self, message, progress):
        """Handle render progress updates."""
        self.statusBar().showMessage(message)
        QtWidgets.QApplication.processEvents()

def _is_junction(path):
    """Check if path is a Windows junction."""
    import os
    if os.name != "nt":
        return False
    try:
        import ctypes
        attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
        return bool(attrs & 0x400)
    except (OSError, AttributeError):
        return False
