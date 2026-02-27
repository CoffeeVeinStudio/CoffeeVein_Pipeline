"""Package Shot dialog for CoffeeVein Shot Manager.

Lets the user select published scripts and render versions to package
into a Packaged/ delivery folder using hardlinks (or copy as fallback).
Supports incremental updates — already-packaged items are shown as
disabled/checked.
"""

from pathlib import Path

from ..qt_compat import QtWidgets, QtCore
from .. import package


class PackageDialog(QtWidgets.QDialog):
    """Dialog for selecting scripts and renders to package for delivery."""

    def __init__(self, shot_name, shot_dir, parent=None):
        super().__init__(parent)
        self.setWindowTitle(f"Package Shot: {shot_name}")
        self.setMinimumWidth(550)
        self.setMinimumHeight(500)

        self._shot_name = shot_name
        self._shot_dir = shot_dir
        self._packaged_dir = package.get_packaged_dir(shot_dir)

        # Discover available items
        self._scripts = package.scan_published_scripts(shot_dir)
        self._plates = package.scan_plate_versions(shot_dir)
        self._renders = package.scan_render_versions(shot_dir)

        # Detect already-packaged items
        self._existing = package.scan_existing_package(self._packaged_dir)

        # Discover external Read node sources (not already in plates/renders)
        known_dirs = set()
        for _, _, _, version_dir, _ in self._plates:
            known_dirs.add(Path(version_dir).as_posix())
        for _, _, _, version_dir in self._renders:
            known_dirs.add(Path(version_dir).as_posix())
        self._externals = package.scan_external_read_nodes(shot_dir, known_dirs)

        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # --- Published Scripts ---
        scripts_group = QtWidgets.QGroupBox(
            f"Nuke Scripts (from TIK)  —  {len(self._scripts)} found"
        )
        scripts_layout = QtWidgets.QVBoxLayout(scripts_group)

        self._scripts_list = QtWidgets.QListWidget()
        self._scripts_list.setMaximumHeight(160)
        for display_name, source_path in self._scripts:
            already = display_name in self._existing["scripts"]
            label = display_name
            if already:
                label += "    (already packaged)"
            item = QtWidgets.QListWidgetItem(label)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            if already:
                item.setCheckState(QtCore.Qt.Checked)
                item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEnabled)
            else:
                item.setCheckState(QtCore.Qt.Unchecked)
            item.setData(QtCore.Qt.UserRole, (display_name, source_path))
            self._scripts_list.addItem(item)

        scripts_layout.addWidget(self._scripts_list)

        if not self._scripts:
            empty = QtWidgets.QLabel("No Nuke scripts found in work folders")
            empty.setStyleSheet("color: #888888; font-style: italic;")
            scripts_layout.addWidget(empty)

        layout.addWidget(scripts_group)

        # --- Plates / CG ---
        ext_suffix = f", {len(self._externals)} external" if self._externals else ""
        plates_group = QtWidgets.QGroupBox(
            f"Plates && CG  —  {len(self._plates)} found{ext_suffix}"
        )
        plates_layout = QtWidgets.QVBoxLayout(plates_group)

        self._plates_list = QtWidgets.QListWidget()
        self._plates_list.setMaximumHeight(160)
        for output_name, ver_num, version_obj, version_dir, output_type in self._plates:
            folder_name = package.get_render_folder_name(output_name, ver_num)
            already = folder_name in self._existing["plates"]

            # Build info string
            info_parts = [output_type.upper()]
            if version_obj.frames:
                frame_count = version_obj.frames[1] - version_obj.frames[0] + 1
                info_parts.append(f"{frame_count} frames")
            if version_obj.format:
                info_parts.append(version_obj.format)
            info_str = f"  ({', '.join(info_parts)})" if info_parts else ""

            label = f"{output_name} v{ver_num:03d}{info_str}"
            if already:
                label += "    (already packaged)"

            item = QtWidgets.QListWidgetItem(label)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            if already:
                item.setCheckState(QtCore.Qt.Checked)
                item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEnabled)
            else:
                item.setCheckState(QtCore.Qt.Unchecked)
            item.setData(QtCore.Qt.UserRole, (output_name, ver_num, version_dir))
            self._plates_list.addItem(item)

        # Add external Read node sources
        for output_name, ver_num, version_obj, version_dir, output_type in self._externals:
            folder_name = package.get_render_folder_name(output_name, ver_num)
            already = folder_name in self._existing["plates"]

            info_parts = []
            if version_obj.frames:
                frame_count = version_obj.frames[1] - version_obj.frames[0] + 1
                info_parts.append(f"{frame_count} frames")
            fmt_label = version_obj.format if version_obj.format else "unknown"
            info_str = f"  ({', '.join(info_parts)})" if info_parts else ""

            label = f"{output_name} v{ver_num:03d}{info_str}  (External, {fmt_label})"
            if already:
                label += "    (already packaged)"

            item = QtWidgets.QListWidgetItem(label)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            if already:
                item.setCheckState(QtCore.Qt.Checked)
                item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEnabled)
            else:
                item.setCheckState(QtCore.Qt.Unchecked)
            item.setData(QtCore.Qt.UserRole, (output_name, ver_num, version_dir))
            self._plates_list.addItem(item)

        plates_layout.addWidget(self._plates_list)

        if not self._plates and not self._externals:
            empty = QtWidgets.QLabel("No plates or CG found in Plates/ or CG/")
            empty.setStyleSheet("color: #888888; font-style: italic;")
            plates_layout.addWidget(empty)

        layout.addWidget(plates_group)

        # --- Render Versions ---
        renders_group = QtWidgets.QGroupBox(
            f"Render Versions (from Shot Manager)  —  {len(self._renders)} found"
        )
        renders_layout = QtWidgets.QVBoxLayout(renders_group)

        self._renders_list = QtWidgets.QListWidget()
        self._renders_list.setMaximumHeight(200)
        for output_name, ver_num, version_obj, version_dir in self._renders:
            folder_name = package.get_render_folder_name(output_name, ver_num)
            already = folder_name in self._existing["renders"]

            # Build info string
            info_parts = []
            if version_obj.frames:
                frame_count = version_obj.frames[1] - version_obj.frames[0] + 1
                info_parts.append(f"{frame_count} frames")
            if version_obj.format:
                info_parts.append(version_obj.format)
            info_str = f"  ({', '.join(info_parts)})" if info_parts else ""

            label = f"{output_name} v{ver_num:03d}{info_str}"
            if already:
                label += "    (already packaged)"

            item = QtWidgets.QListWidgetItem(label)
            item.setFlags(item.flags() | QtCore.Qt.ItemIsUserCheckable)
            if already:
                item.setCheckState(QtCore.Qt.Checked)
                item.setFlags(item.flags() & ~QtCore.Qt.ItemIsEnabled)
            else:
                item.setCheckState(QtCore.Qt.Unchecked)
            item.setData(QtCore.Qt.UserRole, (output_name, ver_num, version_dir))
            self._renders_list.addItem(item)

        renders_layout.addWidget(self._renders_list)

        if not self._renders:
            empty = QtWidgets.QLabel("No render versions found in Comp/renders/")
            empty.setStyleSheet("color: #888888; font-style: italic;")
            renders_layout.addWidget(empty)

        layout.addWidget(renders_group)

        # --- File Mode ---
        mode_group = QtWidgets.QGroupBox("File Mode")
        mode_layout = QtWidgets.QHBoxLayout(mode_group)

        self._hardlink_radio = QtWidgets.QRadioButton("Hardlink (recommended)")
        self._hardlink_radio.setChecked(True)
        self._hardlink_radio.setToolTip(
            "Create hardlinks — saves disk space.\n"
            "Requires source and destination on the same drive."
        )
        mode_layout.addWidget(self._hardlink_radio)

        self._copy_radio = QtWidgets.QRadioButton("Copy")
        self._copy_radio.setToolTip("Copy files — uses additional disk space.")
        mode_layout.addWidget(self._copy_radio)

        mode_layout.addStretch()
        layout.addWidget(mode_group)

        # --- Destination preview ---
        dest_label = QtWidgets.QLabel(
            f"Destination: <b>{self._packaged_dir}</b>"
        )
        dest_label.setWordWrap(True)
        dest_label.setStyleSheet("color: #888888; padding: 4px;")
        layout.addWidget(dest_label)

        # --- Buttons ---
        button_layout = QtWidgets.QHBoxLayout()

        select_all_btn = QtWidgets.QPushButton("Select All")
        select_all_btn.clicked.connect(self._select_all)
        button_layout.addWidget(select_all_btn)

        deselect_all_btn = QtWidgets.QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(self._deselect_all)
        button_layout.addWidget(deselect_all_btn)

        button_layout.addStretch()

        self._package_btn = QtWidgets.QPushButton("Package")
        self._package_btn.setStyleSheet(
            "QPushButton { background-color: #2d7b5a; padding: 8px 20px; "
            "font-weight: bold; }"
            "QPushButton:hover { background-color: #3dab7a; }"
        )
        self._package_btn.clicked.connect(self._on_package)
        self._package_btn.setDefault(True)
        button_layout.addWidget(self._package_btn)

        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    # ------------------------------------------------------------------
    # Selection helpers
    # ------------------------------------------------------------------

    def _select_all(self):
        for lst in (self._scripts_list, self._plates_list, self._renders_list):
            for i in range(lst.count()):
                item = lst.item(i)
                if item.flags() & QtCore.Qt.ItemIsEnabled:
                    item.setCheckState(QtCore.Qt.Checked)

    def _deselect_all(self):
        for lst in (self._scripts_list, self._plates_list, self._renders_list):
            for i in range(lst.count()):
                item = lst.item(i)
                if item.flags() & QtCore.Qt.ItemIsEnabled:
                    item.setCheckState(QtCore.Qt.Unchecked)

    # ------------------------------------------------------------------
    # Packaging
    # ------------------------------------------------------------------

    def _get_selected_scripts(self):
        """Return list of (display_name, source_path) for newly selected scripts."""
        selected = []
        for i in range(self._scripts_list.count()):
            item = self._scripts_list.item(i)
            if (item.checkState() == QtCore.Qt.Checked
                    and item.flags() & QtCore.Qt.ItemIsEnabled):
                selected.append(item.data(QtCore.Qt.UserRole))
        return selected

    def _get_selected_plates(self):
        """Return list of (output_name, version_number, version_dir) for newly selected plates/CG."""
        selected = []
        for i in range(self._plates_list.count()):
            item = self._plates_list.item(i)
            if (item.checkState() == QtCore.Qt.Checked
                    and item.flags() & QtCore.Qt.ItemIsEnabled):
                selected.append(item.data(QtCore.Qt.UserRole))
        return selected

    def _get_selected_renders(self):
        """Return list of (output_name, version_number, version_dir) for newly selected renders."""
        selected = []
        for i in range(self._renders_list.count()):
            item = self._renders_list.item(i)
            if (item.checkState() == QtCore.Qt.Checked
                    and item.flags() & QtCore.Qt.ItemIsEnabled):
                selected.append(item.data(QtCore.Qt.UserRole))
        return selected

    def _check_cross_drive_items(self, selected_plates, selected_renders):
        """Split plate/render items into linkable vs cross-drive lists.

        Returns:
            (linkable_plates, linkable_renders, cross_drive) where cross_drive
            is a list of (label, output_name, ver_num, version_dir, dest_subfolder,
            output_type, source_drive, dest_drive) tuples.
        """
        linkable_plates = []
        linkable_renders = []
        cross_drive = []

        dest_drive = Path(self._packaged_dir).drive.upper()

        for output_name, ver_num, version_dir in selected_plates:
            can_link, reason = package.can_hardlink(version_dir, self._packaged_dir)
            if can_link:
                linkable_plates.append((output_name, ver_num, version_dir))
            else:
                src_drive = Path(version_dir).drive.upper()
                # Determine output_type from the path
                # version_dir is like {shot}/Plates/{name}/v001 or {shot}/CG/{name}/v001
                parent_folder = Path(version_dir).parent.parent.name
                if parent_folder == "CG":
                    output_type = "cg"
                else:
                    output_type = "plate"
                cross_drive.append((
                    f"{output_name} v{ver_num:03d}",
                    output_name, ver_num, version_dir, "plates",
                    output_type, src_drive, dest_drive,
                ))

        for output_name, ver_num, version_dir in selected_renders:
            can_link, reason = package.can_hardlink(version_dir, self._packaged_dir)
            if can_link:
                linkable_renders.append((output_name, ver_num, version_dir))
            else:
                src_drive = Path(version_dir).drive.upper()
                cross_drive.append((
                    f"{output_name} v{ver_num:03d}",
                    output_name, ver_num, version_dir, "renders",
                    "render", src_drive, dest_drive,
                ))

        return linkable_plates, linkable_renders, cross_drive

    def _show_cross_drive_dialog(self, cross_drive_items):
        """Show dialog for cross-drive items. Returns 'move', 'copy', or 'skip'."""
        item_lines = "\n".join(
            f"  \u2022 {label}  ({src} \u2192 {dst})"
            for label, _, _, _, _, _, src, dst in cross_drive_items
        )

        msg = QtWidgets.QMessageBox(self)
        msg.setWindowTitle("Cross-Drive Items")
        msg.setIcon(QtWidgets.QMessageBox.Question)
        msg.setText(
            "Some items are on a different drive and cannot be hardlinked:"
        )
        msg.setInformativeText(
            f"{item_lines}\n\n"
            "Choose how to handle these:"
        )

        move_btn = msg.addButton("Move to Shot + Link", QtWidgets.QMessageBox.AcceptRole)
        copy_btn = msg.addButton("Copy Directly", QtWidgets.QMessageBox.AcceptRole)
        msg.addButton("Skip", QtWidgets.QMessageBox.RejectRole)

        msg.exec_()
        clicked = msg.clickedButton()

        if clicked == move_btn:
            return "move"
        elif clicked == copy_btn:
            return "copy"
        return "skip"

    def _on_package(self):
        """Run the packaging operation with per-item hardlink decisions."""
        selected_scripts = self._get_selected_scripts()
        selected_plates = self._get_selected_plates()
        selected_renders = self._get_selected_renders()

        if not selected_scripts and not selected_plates and not selected_renders:
            QtWidgets.QMessageBox.information(
                self, "Nothing Selected",
                "Select at least one item to package."
            )
            return

        use_hardlink = self._hardlink_radio.isChecked()

        # Per-item hardlink checking
        cross_drive = []
        cross_drive_choice = "skip"
        if use_hardlink:
            linkable_plates, linkable_renders, cross_drive = \
                self._check_cross_drive_items(selected_plates, selected_renders)

            # Scripts are small — always just copy if cross-drive
            linkable_scripts = []
            copy_scripts = []
            for display_name, source_path in selected_scripts:
                can_link, _ = package.can_hardlink(source_path, self._packaged_dir)
                if can_link:
                    linkable_scripts.append((display_name, source_path))
                else:
                    copy_scripts.append((display_name, source_path))

            if cross_drive:
                cross_drive_choice = self._show_cross_drive_dialog(cross_drive)
                if cross_drive_choice == "skip":
                    # Remove cross-drive items, keep linkable ones
                    cross_drive = []
        else:
            # Copy mode — everything goes through as copy
            linkable_scripts = []
            copy_scripts = selected_scripts
            linkable_plates = []
            linkable_renders = []
            # Treat all plates/renders as cross-drive with "copy" choice
            cross_drive = []
            for output_name, ver_num, version_dir in selected_plates:
                cross_drive.append((
                    f"{output_name} v{ver_num:03d}",
                    output_name, ver_num, version_dir, "plates",
                    "plate", "", "",
                ))
            for output_name, ver_num, version_dir in selected_renders:
                cross_drive.append((
                    f"{output_name} v{ver_num:03d}",
                    output_name, ver_num, version_dir, "renders",
                    "render", "", "",
                ))
            cross_drive_choice = "copy"

        # Build the final work list
        # Items: (output_name, ver_num, version_dir, dest_subfolder, mode)
        # mode: "hardlink", "move_and_link", "copy"
        work_items = []
        for output_name, ver_num, version_dir in linkable_plates:
            work_items.append((output_name, ver_num, version_dir, "plates", "hardlink", None))
        for output_name, ver_num, version_dir in linkable_renders:
            work_items.append((output_name, ver_num, version_dir, "renders", "hardlink", None))
        for label, output_name, ver_num, version_dir, dest_sub, out_type, _, _ in cross_drive:
            mode = "move_and_link" if cross_drive_choice == "move" else "copy"
            work_items.append((output_name, ver_num, version_dir, dest_sub, mode, out_type))

        # Count total work items for progress
        total_frames = 0
        for output_name, ver_num, version_dir, _, _, _ in work_items:
            total_frames += sum(1 for f in Path(version_dir).iterdir() if f.is_file())
        all_scripts = linkable_scripts + copy_scripts
        total_items = len(all_scripts) + total_frames

        if not all_scripts and not work_items:
            QtWidgets.QMessageBox.information(
                self, "Nothing to Package",
                "All cross-drive items were skipped. Nothing to package."
            )
            return

        progress = QtWidgets.QProgressDialog(
            "Packaging...", "Cancel", 0, max(total_items, 1), self
        )
        progress.setWindowModality(QtCore.Qt.WindowModal)
        progress.setWindowTitle("Packaging Shot")
        progress.show()

        current = [0]  # Mutable counter for nested callback
        total_errors = 0
        stats = {"hardlinked": 0, "moved_and_linked": 0, "copied": 0}

        # Package scripts
        if linkable_scripts:
            progress.setLabelText("Packaging scripts (hardlink)...")
            successes, errors = package.package_scripts(
                linkable_scripts, self._packaged_dir, use_hardlink=True
            )
            total_errors += errors
            stats["hardlinked"] += successes
            current[0] += len(linkable_scripts)
            progress.setValue(current[0])

        if copy_scripts:
            progress.setLabelText("Packaging scripts (copy)...")
            successes, errors = package.package_scripts(
                copy_scripts, self._packaged_dir, use_hardlink=False
            )
            total_errors += errors
            stats["copied"] += successes
            current[0] += len(copy_scripts)
            progress.setValue(current[0])

        # Package plates and renders
        for output_name, ver_num, version_dir, dest_sub, mode, out_type in work_items:
            if progress.wasCanceled():
                break

            mode_label = {
                "hardlink": "hardlinking",
                "move_and_link": "moving + linking",
                "copy": "copying",
            }[mode]
            progress.setLabelText(
                f"Packaging {output_name} v{ver_num:03d} ({mode_label})..."
            )

            actual_source = version_dir

            # Move to shot first if needed
            if mode == "move_and_link":
                actual_source = package.move_to_shot(
                    version_dir, self._shot_dir,
                    out_type, output_name, ver_num,
                )

            def on_progress(i, total, filename):
                progress.setValue(current[0] + i)

            do_hardlink = mode in ("hardlink", "move_and_link")
            successes, errors = package.package_render_version(
                output_name, ver_num, actual_source,
                self._packaged_dir, use_hardlink=do_hardlink,
                progress_callback=on_progress,
                dest_subfolder=dest_sub,
            )
            total_errors += errors

            if mode == "hardlink":
                stats["hardlinked"] += successes
            elif mode == "move_and_link":
                stats["moved_and_linked"] += successes
            else:
                stats["copied"] += successes

            current[0] += sum(1 for f in Path(version_dir).iterdir() if f.is_file())
            progress.setValue(current[0])

        progress.setValue(total_items)

        # Summary report
        if progress.wasCanceled():
            QtWidgets.QMessageBox.information(
                self, "Cancelled",
                "Packaging was cancelled. Partial results may exist."
            )
        elif total_errors > 0:
            QtWidgets.QMessageBox.warning(
                self, "Packaging Complete",
                f"Packaged with {total_errors} error(s).\n\n"
                f"Check the console for details.\n"
                f"Location: {self._packaged_dir}"
            )
        else:
            total_count = stats["hardlinked"] + stats["moved_and_linked"] + stats["copied"]
            breakdown = []
            if stats["hardlinked"]:
                breakdown.append(f"  \u2022 {stats['hardlinked']} items hardlinked")
            if stats["moved_and_linked"]:
                breakdown.append(f"  \u2022 {stats['moved_and_linked']} items moved to shot + hardlinked")
            if stats["copied"]:
                breakdown.append(f"  \u2022 {stats['copied']} items copied")
            breakdown_str = "\n".join(breakdown)

            QtWidgets.QMessageBox.information(
                self, "Packaging Complete",
                f"Successfully packaged {total_count} items:\n"
                f"{breakdown_str}\n\n"
                f"Location: {self._packaged_dir}"
            )

        self.accept()
