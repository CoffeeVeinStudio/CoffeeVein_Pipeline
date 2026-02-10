"""
CoffeeVein Script Packager
Packages Nuke script with all dependencies for client delivery

Features:
- Custom delivery name (auto-generated with override)
- Select Read nodes to include
- Select published render versions to include
- Hardlinks (recommended), symlinks, or copy files
- Client-friendly naming by stripping TIK prefixes
"""

import nuke
import os
import re
import shutil
from pathlib import Path
from PySide2 import QtWidgets, QtCore


class ScriptPackager(QtWidgets.QDialog):
    """Dialog for packaging Nuke scripts with dependencies."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Script Packager")
        self.setModal(True)
        self.resize(800, 700)

        self.read_nodes = []
        self.selected_files = {}
        self.errors = []  # Track errors during packaging

        self.build_ui()
        self.scan_script()
        self.scan_publish_versions()

    def build_ui(self):
        """Build the UI."""
        layout = QtWidgets.QVBoxLayout(self)

        # Instructions
        info_label = QtWidgets.QLabel(
            "Package your Nuke script for client delivery.\n"
            "Select Read nodes and/or published renders to include."
        )
        layout.addWidget(info_label)

        # === Delivery Name Section ===
        name_group = QtWidgets.QGroupBox("Delivery Name")
        name_layout = QtWidgets.QHBoxLayout(name_group)

        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setPlaceholderText("e.g. A006C019_v001")
        self.name_edit.setText(self.get_default_delivery_name())
        self.name_edit.setToolTip(
            "This will be the name of the output folder and script.\n"
            "Auto-generated from Source files or script name."
        )
        name_layout.addWidget(QtWidgets.QLabel("Name:"))
        name_layout.addWidget(self.name_edit)

        layout.addWidget(name_group)

        # === Read Nodes Section ===
        reads_group = QtWidgets.QGroupBox("Read Nodes")
        reads_layout = QtWidgets.QVBoxLayout(reads_group)

        self.nodes_list = QtWidgets.QListWidget()
        self.nodes_list.setMaximumHeight(150)
        reads_layout.addWidget(self.nodes_list)

        layout.addWidget(reads_group)

        # === Published Renders Section ===
        publish_group = QtWidgets.QGroupBox("Published Renders")
        publish_layout = QtWidgets.QVBoxLayout(publish_group)

        self.publish_list = QtWidgets.QListWidget()
        self.publish_list.setMaximumHeight(150)
        publish_layout.addWidget(self.publish_list)

        publish_info = QtWidgets.QLabel(
            "Select render versions from the publish folder to include."
        )
        publish_info.setStyleSheet("color: gray; font-size: 10px;")
        publish_layout.addWidget(publish_info)

        layout.addWidget(publish_group)

        # === Options Section ===
        options_group = QtWidgets.QGroupBox("Options")
        options_layout = QtWidgets.QVBoxLayout(options_group)

        # Copy mode
        copy_layout = QtWidgets.QHBoxLayout()
        copy_label = QtWidgets.QLabel("File Mode:")
        copy_layout.addWidget(copy_label)

        self.copy_radio = QtWidgets.QRadioButton("Copy Files")
        self.copy_radio.setToolTip("Copy actual files (uses disk space)")
        copy_layout.addWidget(self.copy_radio)

        self.link_radio = QtWidgets.QRadioButton("Create Hardlinks")
        self.link_radio.setChecked(True)  # Default to hardlinks
        self.link_radio.setToolTip(
            "Create hardlinks (saves space, works with Accsyn)\n"
            "Requires files on the same drive."
        )
        copy_layout.addWidget(self.link_radio)

        self.symlink_radio = QtWidgets.QRadioButton("Create Symlinks")
        self.symlink_radio.setToolTip(
            "Create symbolic links\n"
            "Requires Developer Mode or Admin on Windows."
        )
        copy_layout.addWidget(self.symlink_radio)

        copy_layout.addStretch()
        options_layout.addLayout(copy_layout)

        # Naming options
        naming_layout = QtWidgets.QHBoxLayout()
        naming_label = QtWidgets.QLabel("Naming:")
        naming_layout.addWidget(naming_label)

        self.keep_names_radio = QtWidgets.QRadioButton("Keep Original Names")
        self.keep_names_radio.setToolTip("Use current file names as-is")
        naming_layout.addWidget(self.keep_names_radio)

        self.client_names_radio = QtWidgets.QRadioButton("Client-Friendly Names")
        self.client_names_radio.setChecked(True)
        self.client_names_radio.setToolTip(
            "Strip TIK Manager prefixes from filenames\n"
            "SNAPSHOT_SH42_Source_A006C019.mov -> A006C019.mov"
        )
        naming_layout.addWidget(self.client_names_radio)

        naming_layout.addStretch()
        options_layout.addLayout(naming_layout)

        layout.addWidget(options_group)

        # === Output Path Section ===
        path_group = QtWidgets.QGroupBox("Output Location")
        path_layout = QtWidgets.QHBoxLayout(path_group)

        self.path_edit = QtWidgets.QLineEdit()
        self.path_edit.setText(self.get_default_output_path())
        browse_btn = QtWidgets.QPushButton("Browse...")
        browse_btn.clicked.connect(self.browse_output)

        path_layout.addWidget(QtWidgets.QLabel("Folder:"))
        path_layout.addWidget(self.path_edit)
        path_layout.addWidget(browse_btn)

        layout.addWidget(path_group)

        # === Buttons ===
        button_layout = QtWidgets.QHBoxLayout()

        select_all_btn = QtWidgets.QPushButton("Select All")
        select_all_btn.clicked.connect(self.select_all)
        button_layout.addWidget(select_all_btn)

        deselect_all_btn = QtWidgets.QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(self.deselect_all)
        button_layout.addWidget(deselect_all_btn)

        button_layout.addStretch()

        package_btn = QtWidgets.QPushButton("Package Script")
        package_btn.setStyleSheet(
            "background-color: rgb(60, 100, 60); padding: 8px 16px; font-weight: bold;"
        )
        package_btn.clicked.connect(self.package_script)
        button_layout.addWidget(package_btn)

        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)

        layout.addLayout(button_layout)

    def get_default_delivery_name(self):
        """Auto-generate delivery name from Source files or script."""
        # Try to find client name from Source nodes
        for n in nuke.allNodes("Read"):
            file_path = n['file'].value()
            if '/Source/' in file_path or '\\Source\\' in file_path:
                filename = Path(file_path).stem
                # Remove frame padding
                filename = re.sub(r'\.\d+$', '', filename)
                # Strip TIK prefix: SNAPSHOT_{SHOT}_Source_{CLIENTNAME}
                match = re.match(r'^SNAPSHOT_[^_]+_Source_(.+)$', filename)
                if match:
                    base_name = match.group(1)
                    version = self.get_script_version() or "v001"
                    return f"{base_name}_{version}"

        # Fallback: use script name
        script_path = nuke.root().name()
        if script_path and script_path != "Root":
            return Path(script_path).stem
        return "delivery"

    def get_script_version(self):
        """Extract version from script name (e.g., Sh019_Comp_v003.nk -> v003)."""
        script_path = nuke.root().name()
        if not script_path or script_path == "Root":
            return None
        script_name = Path(script_path).stem
        version_match = re.search(r'_(v\d+)$', script_name)
        if version_match:
            return version_match.group(1)
        return None

    def get_default_output_path(self):
        """Get default output path based on current script."""
        script_path = nuke.root().name()

        if script_path == "Root":
            return ""

        script_dir = Path(script_path).parent
        # Go up to project root and create Delivery folder
        delivery_dir = script_dir.parent.parent.parent / "Delivery"

        return str(delivery_dir)

    def browse_output(self):
        """Browse for output directory."""
        folder = QtWidgets.QFileDialog.getExistingDirectory(
            self,
            "Select Output Folder",
            self.path_edit.text()
        )

        if folder:
            self.path_edit.setText(folder)

    def scan_script(self):
        """Scan script for Read nodes."""
        self.read_nodes = [n for n in nuke.allNodes() if n.Class() == "Read"]

        for node in self.read_nodes:
            file_path = node['file'].value()

            # Handle sequences vs single files
            if '####' in file_path or '%' in file_path:
                file_type = "Sequence"
            else:
                file_type = "Single"

            # Create list item
            item_text = f"{node.name()} - {file_type} - {Path(file_path).name}"
            item = QtWidgets.QListWidgetItem(item_text)
            item.setCheckState(QtCore.Qt.Checked)
            item.setData(QtCore.Qt.UserRole, node)

            self.nodes_list.addItem(item)

    def scan_publish_versions(self):
        """Scan publish folder for available render versions."""
        script_path = nuke.root().name()
        if not script_path or script_path == "Root":
            return

        script_path = Path(script_path)

        # Navigate to publish folder
        # Script path: .../nuke/LIVE/{version}/{script}.nk
        # We need: .../nuke/publish/
        try:
            # Try different folder structures
            nuke_dir = None

            # Check if LIVE is in path
            parts = script_path.parts
            for i, part in enumerate(parts):
                if part == "LIVE":
                    nuke_dir = Path(*parts[:i])
                    break
                if part == "nuke":
                    nuke_dir = Path(*parts[:i+1])
                    break

            if not nuke_dir:
                # Fallback: go up from script
                nuke_dir = script_path.parent.parent.parent

            publish_dir = nuke_dir / "publish"

            if not publish_dir.exists():
                return

            # Find all RENDER_ folders in publish
            render_dirs = []
            for task_dir in publish_dir.iterdir():
                if not task_dir.is_dir():
                    continue
                for render_dir in task_dir.iterdir():
                    if render_dir.is_dir() and render_dir.name.startswith("RENDER_"):
                        render_dirs.append(render_dir)

            # Sort by version (newest first)
            render_dirs.sort(key=lambda x: x.name, reverse=True)

            for render_dir in render_dirs:
                # Count files in directory
                file_count = sum(1 for f in render_dir.iterdir() if f.is_file())

                item_text = f"{render_dir.name} ({file_count} files)"
                item = QtWidgets.QListWidgetItem(item_text)
                item.setCheckState(QtCore.Qt.Unchecked)  # Unchecked by default
                item.setData(QtCore.Qt.UserRole, render_dir)
                self.publish_list.addItem(item)

        except Exception as e:
            print(f"Error scanning publish folder: {e}")

    def select_all(self):
        """Select all items in both lists."""
        for i in range(self.nodes_list.count()):
            self.nodes_list.item(i).setCheckState(QtCore.Qt.Checked)
        for i in range(self.publish_list.count()):
            self.publish_list.item(i).setCheckState(QtCore.Qt.Checked)

    def deselect_all(self):
        """Deselect all items in both lists."""
        for i in range(self.nodes_list.count()):
            self.nodes_list.item(i).setCheckState(QtCore.Qt.Unchecked)
        for i in range(self.publish_list.count()):
            self.publish_list.item(i).setCheckState(QtCore.Qt.Unchecked)

    def package_script(self):
        """Package the script with selected dependencies."""
        self.errors = []  # Reset errors
        self._cross_drive_copy_all = None  # Reset cross-drive user choice

        output_dir = Path(self.path_edit.text())

        if not output_dir or not self.path_edit.text().strip():
            nuke.message("Please select an output folder")
            return

        # Get delivery name from text field
        delivery_name = self.name_edit.text().strip()
        if not delivery_name:
            delivery_name = Path(nuke.root().name()).stem

        # Create output structure
        package_dir = output_dir / delivery_name
        footage_dir = package_dir / "footage"

        try:
            package_dir.mkdir(parents=True, exist_ok=True)
            footage_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            nuke.message(f"Failed to create output folder: {e}")
            return

        # Determine copy mode
        if self.link_radio.isChecked():
            copy_mode = "hardlink"
        elif self.symlink_radio.isChecked():
            copy_mode = "symlink"
        else:
            copy_mode = "copy"

        # Determine naming mode
        use_client_names = self.client_names_radio.isChecked()

        # Collect selected Read nodes
        selected_nodes = []
        for i in range(self.nodes_list.count()):
            item = self.nodes_list.item(i)
            if item.checkState() == QtCore.Qt.Checked:
                node = item.data(QtCore.Qt.UserRole)
                selected_nodes.append(node)

        # Collect selected publish versions
        selected_publish = []
        for i in range(self.publish_list.count()):
            item = self.publish_list.item(i)
            if item.checkState() == QtCore.Qt.Checked:
                render_dir = item.data(QtCore.Qt.UserRole)
                selected_publish.append(render_dir)

        if not selected_nodes and not selected_publish:
            nuke.message("No files selected.\nPlease select Read nodes or Published Renders.")
            return

        # Progress
        total_items = len(selected_nodes) + len(selected_publish) + 1
        progress = QtWidgets.QProgressDialog(
            "Packaging script...",
            "Cancel",
            0,
            total_items,
            self
        )
        progress.setWindowModality(QtCore.Qt.WindowModal)
        progress.show()

        # Process each Read node
        path_mapping = {}
        current_item = 0

        for node in selected_nodes:
            if progress.wasCanceled():
                nuke.message("Packaging cancelled")
                return

            progress.setValue(current_item)
            progress.setLabelText(f"Processing {node.name()}...")
            current_item += 1

            file_path = node['file'].value()

            # Determine output filename
            if use_client_names:
                output_name = self.get_client_friendly_name(node, file_path)
            else:
                output_name = Path(file_path).name

            # Handle sequence vs single file
            if '####' in file_path or '%' in file_path:
                # Sequence - copy all frames
                success = self.copy_sequence(file_path, footage_dir, copy_mode, node, output_name)
            else:
                # Single file
                success = self.copy_file(file_path, footage_dir, copy_mode, output_name)

            if success:
                # Store new path for script update
                new_path = footage_dir / output_name
                path_mapping[file_path] = str(new_path)

        # Process selected publish versions
        for render_dir in selected_publish:
            if progress.wasCanceled():
                nuke.message("Packaging cancelled")
                return

            progress.setValue(current_item)
            progress.setLabelText(f"Processing {render_dir.name}...")
            current_item += 1

            # Copy all files from this render version
            for file in render_dir.iterdir():
                if file.is_file():
                    if use_client_names:
                        output_name = self.get_client_friendly_name(None, str(file))
                    else:
                        output_name = file.name
                    self.copy_file(str(file), footage_dir, copy_mode, output_name)

        # Save modified script
        progress.setLabelText("Saving packaged script...")
        progress.setValue(current_item)

        # Create a copy of the script with updated paths
        new_script_path = package_dir / f"{delivery_name}.nk"

        # Read current script
        try:
            with open(nuke.root().name(), 'r') as f:
                script_content = f.read()

            # Replace paths
            for old_path, new_path in path_mapping.items():
                # Use relative path
                relative_path = os.path.relpath(new_path, package_dir)
                script_content = script_content.replace(old_path, relative_path)

            # Write new script
            with open(new_script_path, 'w') as f:
                f.write(script_content)
        except Exception as e:
            self.errors.append(f"Script save failed: {e}")

        progress.setValue(total_items)

        # Show result
        if self.errors:
            error_text = "\n".join(self.errors[:10])  # Show max 10 errors
            if len(self.errors) > 10:
                error_text += f"\n... and {len(self.errors) - 10} more errors"
            nuke.message(
                f"Package completed with {len(self.errors)} errors:\n\n{error_text}\n\n"
                f"Location: {package_dir}"
            )
        else:
            nuke.message(
                f"Script packaged successfully!\n\n"
                f"Location: {package_dir}\n\n"
                f"Package includes:\n"
                f"- {delivery_name}.nk\n"
                f"- footage/ ({len(path_mapping)} items from Read nodes"
                f"{f', {len(selected_publish)} publish versions' if selected_publish else ''})\n\n"
                f"Ready for delivery!"
            )

        self.accept()

    def find_source_client_name(self):
        """Find client name from Source Read nodes by stripping TIK prefix."""
        for n in nuke.allNodes("Read"):
            file_path = n['file'].value()
            if '/Source/' in file_path or '\\Source\\' in file_path:
                filename = Path(file_path).stem
                # Remove frame padding if present
                filename = re.sub(r'\.\d+$', '', filename)
                # TIK pattern: SNAPSHOT_{SHOT}_Source_{CLIENTNAME}
                match = re.match(r'^SNAPSHOT_[^_]+_Source_(.+)$', filename)
                if match:
                    return match.group(1)
                # If no TIK pattern, return filename as-is
                return filename
        return None

    def get_client_friendly_name(self, node, file_path):  # noqa: ARG002 - node kept for API compatibility
        """
        Generate client-friendly filename by stripping TIK Manager prefixes.

        TIK patterns:
        - SNAPSHOT_{SHOT}_Source_{CLIENTNAME} -> {CLIENTNAME}
        - RENDER_{SHOT}_{NAME}_{VERSION} -> {CLIENTNAME}_{VERSION}

        Handles:
        - Sequence PATTERNS: file.####.exr, file.%04d.exr → file.####.exr
        - Actual frame FILES: file.0001.exr → file.0001.exr (keeps frame number!)
        """
        _ = node  # Unused but kept for potential future use
        filename = Path(file_path).name  # Full filename with extension

        # First, check for sequence PATTERNS (####, %04d, %4d, etc.)
        # These should be normalized to ####
        pattern_match = re.match(
            r'^(.+?)(\.(?:#{4}|%\d*d))(\.\w+)$',
            filename
        )

        if pattern_match:
            # Sequence PATTERN - normalize to ####
            base_name = pattern_match.group(1)
            frame_pattern = '.####'
            extension = pattern_match.group(3)
        else:
            # Check for actual frame NUMBER (file.0001.exr)
            # Keep the frame number as-is!
            frame_match = re.match(
                r'^(.+?)\.(\d{4,})(\.\w+)$',
                filename
            )

            if frame_match:
                # Actual frame file - KEEP the frame number
                base_name = frame_match.group(1)
                frame_number = frame_match.group(2)
                extension = frame_match.group(3)
                frame_pattern = f'.{frame_number}'  # Keep actual frame number!
            else:
                # Single file (no frame pattern or number)
                base_name = Path(file_path).stem
                frame_pattern = ''
                extension = Path(file_path).suffix

        # Remove any remaining frame padding from base_name (edge cases)
        base_name_clean = re.sub(r'\.\d+$', '', base_name)

        # Strip TIK prefixes from base_name
        clean_name = self._strip_tik_prefix(base_name_clean, file_path)

        return f"{clean_name}{frame_pattern}{extension}"

    def _strip_tik_prefix(self, base_name, file_path):
        """Strip TIK Manager prefixes from filename."""
        # Check if file is in Source folder
        if '/Source/' in file_path or '\\Source\\' in file_path:
            # TIK pattern: SNAPSHOT_{SHOT}_Source_{CLIENTNAME}
            match = re.match(r'^SNAPSHOT_[^_]+_Source_(.+)$', base_name)
            if match:
                client_name = match.group(1)
                version = self.get_script_version()
                if version:
                    return f"{client_name}_{version}"
                return client_name
            # No TIK pattern - use as-is
            return base_name

        # Check for TIK render pattern: RENDER_{SHOT}_{NAME}_{VERSION}
        render_match = re.match(r'^RENDER_[^_]+_(.+)_(v\d+)$', base_name)
        if render_match:
            # Try to find client name from Source files
            source_name = self.find_source_client_name()
            version = render_match.group(2)
            if source_name:
                return f"{source_name}_{version}"
            # Fallback: use the render name part
            return f"{render_match.group(1)}_{version}"

        # No TIK pattern found - keep original name
        return base_name

    def _is_unc_path(self, path):
        """Check if path is a UNC (network) path."""
        str_path = str(path)
        return str_path.startswith('\\\\') or str_path.startswith('//')

    def _can_hardlink(self, source, dest):
        """Check if hardlink is possible between source and dest.

        Returns (can_link: bool, reason: str or None)
        """
        # UNC paths cannot be hardlinked
        if self._is_unc_path(source):
            return False, f"network path ({str(source)[:40]}...)"
        if self._is_unc_path(dest):
            return False, f"network destination"

        source_drive = Path(source).drive.upper()
        dest_drive = Path(dest).drive.upper()

        # Empty drive = likely UNC or special path
        if not source_drive:
            return False, "source has no drive letter"
        if not dest_drive:
            return False, "destination has no drive letter"

        # Different drives cannot be hardlinked
        if source_drive != dest_drive:
            return False, f"different drives ({source_drive} → {dest_drive})"

        return True, None

    def _normalize_frame_pattern(self, pattern):
        """Normalize frame patterns to %04d for consistent handling."""
        if '####' in pattern:
            return pattern.replace('####', '%04d')
        elif '%4d' in pattern:  # Common variant
            return pattern.replace('%4d', '%04d')
        return pattern

    def _format_frame_number(self, pattern, frame):
        """Format a filename pattern with a frame number."""
        # DEBUG: Uncomment to debug frame formatting issues
        # print(f"[DEBUG] _format_frame_number('{pattern}', {frame})")

        if '%' in pattern:
            try:
                result = pattern % frame
                # print(f"[DEBUG]   → % format OK: '{result}'")
                return result
            except (TypeError, ValueError) as e:
                print(f"[WARN] Frame format failed for '{pattern}': {e}")

        # Fallback: manual replacement for #### patterns
        if '####' in pattern:
            result = pattern.replace('####', str(frame).zfill(4))
            # print(f"[DEBUG]   → #### replace: '{result}'")
            return result

        # No pattern found - return as-is
        # print(f"[DEBUG]   → No pattern, returning as-is")
        return pattern

    def copy_sequence(self, sequence_path, dest_dir, copy_mode, node, output_name=None):
        """Copy an image sequence."""
        # Get frame range from node
        first_frame = int(node['first'].value())
        last_frame = int(node['last'].value())

        # Parse source sequence pattern
        base_path = Path(sequence_path)
        parent = base_path.parent
        source_pattern = self._normalize_frame_pattern(base_path.name)

        # Determine output pattern
        if output_name:
            output_pattern = self._normalize_frame_pattern(output_name)
        else:
            output_pattern = source_pattern

        # Copy each frame
        frames_copied = 0
        for frame in range(first_frame, last_frame + 1):
            # Generate actual filenames with frame number
            source_filename = self._format_frame_number(source_pattern, frame)
            output_filename = self._format_frame_number(output_pattern, frame)

            source_file = parent / source_filename

            if source_file.exists():
                success = self.copy_file(str(source_file), dest_dir, copy_mode, output_filename)
                if success:
                    frames_copied += 1
            else:
                # Try resolving LIVE symlinks
                resolved = self.resolve_live_path(str(source_file))
                if resolved and Path(resolved).exists():
                    success = self.copy_file(resolved, dest_dir, copy_mode, output_filename)
                    if success:
                        frames_copied += 1

        return frames_copied > 0

    def resolve_live_path(self, file_path):
        """Resolve LIVE symlink path to actual file."""
        # LIVE folders are symlinks to actual version folders
        # Try to resolve the actual path
        path = Path(file_path)
        try:
            if path.exists():
                return str(path.resolve())
            # Check parent for LIVE symlink
            if 'LIVE' in str(path):
                resolved = path.resolve()
                if resolved.exists():
                    return str(resolved)
        except Exception:
            pass
        return None

    def copy_file(self, source_path, dest_dir, copy_mode, output_name=None):
        """Copy a single file with proper error handling."""
        source = Path(source_path)

        # IMPORTANT: Do NOT call resolve() unconditionally!
        # resolve() can convert local paths (Z:\...) to UNC paths (\\server\share\...)
        # which breaks hardlinks. Only resolve if the file doesn't exist (for LIVE symlinks).
        if not source.exists():
            try:
                resolved = source.resolve()
                if resolved.exists():
                    source = resolved
            except Exception:
                pass

        if not source.exists():
            self.errors.append(f"File not found: {source_path}")
            return False

        dest = dest_dir / (output_name if output_name else source.name)

        try:
            if copy_mode == "copy":
                shutil.copy2(source, dest)

            elif copy_mode == "hardlink":
                # Check if hardlink is possible (same drive, not UNC, etc.)
                can_link, reason = self._can_hardlink(source, dest)

                if not can_link:
                    # Ask user if they want to copy instead (only once per operation)
                    if self._cross_drive_copy_all is None:
                        result = nuke.ask(
                            f"Cannot create hardlinks ({reason}).\n\n"
                            f"Copy files instead?\n"
                            f"(This will be applied to all remaining files)"
                        )
                        self._cross_drive_copy_all = result

                    if self._cross_drive_copy_all:
                        shutil.copy2(source, dest)
                        return True
                    else:
                        self.errors.append(f"Skipped ({reason}): {source.name}")
                        return False

                # Same drive, not UNC - proceed with hardlink
                if dest.exists():
                    dest.unlink()
                try:
                    os.link(source, dest)
                except OSError as e:
                    self.errors.append(f"Hardlink failed for {source.name}: {e}")
                    return False

            elif copy_mode == "symlink":
                if dest.exists():
                    dest.unlink()
                try:
                    os.symlink(source, dest)
                except OSError as e:
                    # Windows symlink privilege error
                    if hasattr(e, 'winerror') and e.winerror == 1314:
                        nuke.message(
                            "Symlink creation failed - Windows requires special permissions.\n\n"
                            "To enable symlinks:\n"
                            "1. Open Windows Settings\n"
                            "2. Go to: Privacy & Security -> For developers\n"
                            "3. Enable 'Developer Mode'\n\n"
                            "Or use 'Create Hardlinks' instead (recommended)."
                        )
                        return False
                    raise

            return True

        except Exception as e:
            self.errors.append(f"Failed to {copy_mode} {source.name}: {e}")
            return False


def launch_packager():
    """Launch the script packager dialog."""

    # Check if script is saved
    if nuke.root().name() == "Root":
        nuke.message("Please save your script first")
        return

    dialog = ScriptPackager()
    dialog.exec_()


# Add to menu
nuke.menu('Nuke').addCommand(
    'CoffeeVein/Package Script for Delivery',
    launch_packager,
    'ctrl+alt+p'
)
