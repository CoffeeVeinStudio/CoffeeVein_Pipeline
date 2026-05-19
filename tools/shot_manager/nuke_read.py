"""Nuke Read node creation and management for CoffeeVein Shot Manager.

Provides tools to create Read nodes from rendered outputs, with special
support for "LIVE Read" nodes that automatically track version updates.

Only imported when running inside Nuke — standalone mode skips this module.
"""

from pathlib import Path
import json
import re


def sanitize_node_name(name):
    """Remove/replace illegal Nuke node name characters.

    Nuke node names cannot contain: spaces, parentheses, most special chars.
    They also cannot start with digits.

    Args:
        name: Proposed node name.

    Returns:
        Sanitized name safe for Nuke.
    """
    # Replace illegal characters with underscores
    name = re.sub(r'[^\w\-]', '_', name)
    # Remove leading digits and underscores
    name = re.sub(r'^[\d_]+', '', name)
    # Fallback if name is now empty
    if not name:
        name = "Read"
    return name


def create_read_node(file_path, first_frame=None, last_frame=None, name=None, colorspace="default", output_dir=None):
    """Create a Read node with a static file path.

    Args:
        file_path: Absolute path to the file/sequence (e.g., "Z:/.../.../v001/Name.####.exr")
        first_frame: First frame of the sequence (None for movies).
        last_frame: Last frame of the sequence (None for movies).
        name: Optional custom name for the Read node.
        colorspace: Colorspace to set (default: "default" uses Nuke's auto-detect).
        output_dir: If provided, stores a hidden sm_output_dir knob for reconnect support.

    Returns:
        The created nuke.Node (Read node).
    """
    import nuke

    # CRITICAL: Always use forward slashes for Nuke file paths
    file_path = str(file_path).replace("\\", "/")

    # Detect movie vs sequence
    ext = Path(file_path).suffix.lower()
    is_movie = ext in ('.mov', '.mp4', '.avi', '.mxf', '.mkv', '.mov64')

    read_node = nuke.createNode("Read", inpanel=False)

    if is_movie:
        # Movies: use fromUserText to auto-detect frame range and colorspace
        read_node["file"].fromUserText(file_path)
    else:
        # Sequences: manual setup
        read_node["file"].setValue(file_path)
        if first_frame is not None and last_frame is not None:
            read_node["first"].setValue(int(first_frame))
            read_node["last"].setValue(int(last_frame))
            read_node["origfirst"].setValue(int(first_frame))
            read_node["origlast"].setValue(int(last_frame))

        if colorspace != "default":
            read_node["colorspace"].setValue(colorspace)

    if name:
        safe_name = sanitize_node_name(name)
        read_node.setName(safe_name, uncollide=True)

    if output_dir is not None:
        tab = nuke.Tab_Knob("shot_manager_static", "Shot Manager", nuke.TABBEGINGROUP)
        read_node.addKnob(tab)
        dir_knob = nuke.String_Knob("sm_output_dir", "Output Directory")
        dir_knob.setValue(str(output_dir).replace("\\", "/"))
        read_node.addKnob(dir_knob)
        read_node.addKnob(nuke.Tab_Knob("shot_manager_static_end", "", nuke.TABENDGROUP))

    # Position the node nicely in the DAG
    read_node.setXpos(int(nuke.selectedNode().xpos()) if nuke.selectedNodes() else 0)
    read_node.setYpos(int(nuke.selectedNode().ypos()) if nuke.selectedNodes() else 0)

    return read_node


def create_live_read_node(output_dir, output, name=None):
    """Create a LIVE Read node that auto-tracks version updates.

    The node's file path points to the current LIVE version and is updated
    automatically by update_live_readers() when the LIVE version changes.

    Args:
        output_dir: Absolute path to the output directory (e.g., ".../renders/Denoise/")
        output: Output object with live_version and versions.
        name: Optional custom name for the Read node.

    Returns:
        The created nuke.Node (Read node).

    Raises:
        ValueError: If the output has no LIVE version set.
    """
    import nuke

    if output.live_version is None:
        raise ValueError(f"Output {output.name} has no LIVE version set")

    live_version = output.get_version(output.live_version)
    if live_version is None:
        raise ValueError(f"LIVE version {output.live_version} not found in output {output.name}")

    output_dir = Path(output_dir)

    # CRITICAL: Always use forward slashes for Nuke paths
    output_dir_str = str(output_dir).replace("\\", "/")

    # Build initial file path from current LIVE version
    file_path = output_dir / live_version.path
    file_path_str = str(file_path).replace("\\", "/")

    # Detect movie vs sequence
    ext = Path(file_path).suffix.lower()
    is_movie = ext in ('.mov', '.mp4', '.avi', '.mxf', '.mkv', '.mov64')

    read_node = nuke.createNode("Read", inpanel=False)

    if is_movie:
        read_node["file"].fromUserText(file_path_str)
    else:
        read_node["file"].setValue(file_path_str)
        if live_version.frames:
            first_frame, last_frame = live_version.frames
            read_node["first"].setValue(int(first_frame))
            read_node["last"].setValue(int(last_frame))
            read_node["origfirst"].setValue(int(first_frame))
            read_node["origlast"].setValue(int(last_frame))

    if name:
        safe_name = sanitize_node_name(name)
        read_node.setName(safe_name, uncollide=True)

    # Add hidden metadata to track this as a LIVE Read node
    # (Store output_dir so we can find and update this node later)
    tab_knob = nuke.Tab_Knob("shot_manager_live", "Shot Manager LIVE", nuke.TABBEGINGROUP)
    read_node.addKnob(tab_knob)

    output_dir_knob = nuke.String_Knob("shot_manager_output_dir", "Output Directory")
    output_dir_knob.setValue(output_dir_str)
    read_node.addKnob(output_dir_knob)

    tab_end = nuke.Tab_Knob("shot_manager_live_end", "", nuke.TABENDGROUP)
    read_node.addKnob(tab_end)

    # Position the node
    read_node.setXpos(int(nuke.selectedNode().xpos()) if nuke.selectedNodes() else 0)
    read_node.setYpos(int(nuke.selectedNode().ypos()) if nuke.selectedNodes() else 0)

    return read_node


def create_geo_read_node(file_path, name=None):
    """Create a ReadGeo2 node pointing to a geometry file (.abc, .obj, .fbx).

    Args:
        file_path: Absolute path to the geometry file.
        name: Optional custom name for the ReadGeo2 node.

    Returns:
        The created nuke.Node (ReadGeo2 node).
    """
    import nuke

    file_path = str(file_path).replace("\\", "/")
    geo = nuke.createNode("ReadGeo2", inpanel=False)
    geo["file"].setValue(file_path)

    if name:
        geo.setName(sanitize_node_name(name), uncollide=True)

    geo.setXpos(int(nuke.selectedNode().xpos()) if nuke.selectedNodes() else 0)
    geo.setYpos((int(nuke.selectedNode().ypos()) + 80) if nuke.selectedNodes() else 80)

    return geo


def create_deep_read_node(file_path, first_frame=None, last_frame=None, name=None):
    """Create a DeepRead node pointing to a deep image file.

    Args:
        file_path: Absolute path to the deep file (.exr, .dtex, .dex).
        first_frame: First frame of the sequence (None for single-frame deep files).
        last_frame: Last frame of the sequence.
        name: Optional custom name for the DeepRead node.

    Returns:
        The created nuke.Node (DeepRead node).
    """
    import nuke

    file_path = str(file_path).replace("\\", "/")
    node = nuke.createNode("DeepRead", inpanel=False)
    node["file"].setValue(file_path)

    if first_frame is not None and last_frame is not None:
        node["first"].setValue(int(first_frame))
        node["last"].setValue(int(last_frame))
        node["origfirst"].setValue(int(first_frame))
        node["origlast"].setValue(int(last_frame))

    if name:
        node.setName(sanitize_node_name(name), uncollide=True)

    node.setXpos(int(nuke.selectedNode().xpos()) if nuke.selectedNodes() else 0)
    node.setYpos((int(nuke.selectedNode().ypos()) + 80) if nuke.selectedNodes() else 80)

    return node


def create_camera_read_node(file_path, name=None):
    """Create a Camera2 node reading animation data from a file (.chan, .abc, .fbx).

    Args:
        file_path: Absolute path to the camera file.
        name: Optional custom name for the Camera node.

    Returns:
        The created nuke.Node (Camera2 node).
    """
    import nuke

    file_path = str(file_path).replace("\\", "/")
    node = nuke.createNode("Camera2", inpanel=False)
    node["read_from_file"].setValue(True)
    node["file"].setValue(file_path)

    if name:
        node.setName(sanitize_node_name(name), uncollide=True)

    node.setXpos(int(nuke.selectedNode().xpos()) if nuke.selectedNodes() else 0)
    node.setYpos((int(nuke.selectedNode().ypos()) + 80) if nuke.selectedNodes() else 80)

    return node


def update_live_readers(output_dir):
    """Update all LIVE Read nodes that reference this output directory.

    Scans all Read nodes in the script for the shot_manager_output_dir knob.
    For matching nodes, updates their file path and frame range to match the
    new LIVE version.

    Args:
        output_dir: Absolute path to the output directory that changed.
    """
    import nuke

    output_dir = Path(output_dir)
    versions_json = output_dir / ".versions.json"

    if not versions_json.exists():
        return

    # Load the updated LIVE version info
    with open(versions_json, "r", encoding="utf-8") as f:
        data = json.load(f)

    live_version_number = data.get("live_version")
    if live_version_number is None:
        return

    versions = {v["version"]: v for v in data.get("versions", [])}
    live_version = versions.get(live_version_number)
    if not live_version:
        return

    # Build new file path
    file_path = output_dir / live_version.get("path", "")
    file_path_str = str(file_path).replace("\\", "/")

    # Detect movie vs sequence
    ext = Path(file_path).suffix.lower()
    is_movie = ext in ('.mov', '.mp4', '.avi', '.mxf', '.mkv', '.mov64')

    frames = live_version.get("frames")
    first_frame = frames[0] if frames and len(frames) >= 2 else None
    last_frame = frames[1] if frames and len(frames) >= 2 else None

    # Find all Read nodes with matching shot_manager_output_dir
    output_dir_str = str(output_dir).replace("\\", "/")

    for node in nuke.allNodes():
        if node.Class() != "Read":
            continue

        # Check if this is a LIVE Read node tracking this output
        if "shot_manager_output_dir" not in node.knobs():
            continue

        node_output_dir = node["shot_manager_output_dir"].value()
        if node_output_dir != output_dir_str:
            continue

        # Update file path
        if is_movie:
            node["file"].fromUserText(file_path_str)
        else:
            node["file"].setValue(file_path_str)
            if first_frame is not None and last_frame is not None:
                node["first"].setValue(int(first_frame))
                node["last"].setValue(int(last_frame))
                node["origfirst"].setValue(int(first_frame))
                node["origlast"].setValue(int(last_frame))

        print(f"[ShotManager] Updated LIVE Read '{node.name()}' to {file_path_str}")


def sync_all_live_readers():
    """Sync all LIVE Read nodes in the current script to their current LIVE version.

    Scans all Read nodes for the shot_manager_output_dir knob and calls
    update_live_readers() for each unique output directory found.
    Called on panel show so nodes stay fresh if LIVE changed externally.
    """
    import nuke

    output_dirs = set()
    for node in nuke.allNodes("Read"):
        if "shot_manager_output_dir" in node.knobs():
            val = node["shot_manager_output_dir"].value()
            if val:
                output_dirs.add(val)

    for dir_str in output_dirs:
        try:
            update_live_readers(Path(dir_str))
        except Exception as e:
            print(f"[ShotManager] Warning: Failed to sync LIVE node for {dir_str}: {e}")


def find_read_nodes():
    """Find all Read nodes in the current script.

    Returns:
        List of dicts with 'node', 'name', 'file', and 'display' keys.
        'display' is a user-friendly label for picker dialogs.
    """
    import nuke

    results = []
    for node in nuke.allNodes():
        if node.Class() == "Read":
            node_name = node.name()
            file_path = node["file"].value()

            # Smart display label
            if re.match(r'^Read\d+$', node_name):
                # Default Nuke name (Read1, Read2, ...) → show filename only
                display = Path(file_path).name if file_path else node_name
            else:
                # Custom name → show node name only
                display = node_name

            results.append({
                "node": node,
                "name": node_name,
                "file": file_path,
                "display": display,
            })
    return sorted(results, key=lambda r: r["name"])


def update_read_node(node, file_path, first_frame=None, last_frame=None):
    """Update an existing Read node with a new file path and frame range.

    Args:
        node: nuke.Node (Read node).
        file_path: New file path.
        first_frame: New first frame (None for movies).
        last_frame: New last frame (None for movies).
    """
    # CRITICAL: Always use forward slashes
    file_path = str(file_path).replace("\\", "/")

    # Detect movie vs sequence
    ext = Path(file_path).suffix.lower()
    is_movie = ext in ('.mov', '.mp4', '.avi', '.mxf', '.mkv', '.mov64')

    if is_movie:
        node["file"].fromUserText(file_path)
    else:
        node["file"].setValue(file_path)
        if first_frame is not None and last_frame is not None:
            node["first"].setValue(int(first_frame))
            node["last"].setValue(int(last_frame))
            node["origfirst"].setValue(int(first_frame))
            node["origlast"].setValue(int(last_frame))

    print(f"[ShotManager] Updated Read node '{node.name()}' to {file_path}")


def update_live_read_dir(old_output_dir, new_output_dir):
    """Update LIVE Read nodes whose output dir changed (called after a move).

    Updates the shot_manager_output_dir knob value for any LIVE Read nodes
    pointing at old_output_dir, then triggers update_live_readers() so their
    file paths refresh to the new location.
    """
    try:
        import nuke
    except ImportError:
        return
    old_str = str(old_output_dir).replace("\\", "/")
    new_str = str(new_output_dir).replace("\\", "/")
    for node in nuke.allNodes("Read"):
        if "shot_manager_output_dir" not in node.knobs():
            continue
        if node["shot_manager_output_dir"].value() == old_str:
            node["shot_manager_output_dir"].setValue(new_str)
    update_live_readers(Path(new_output_dir))


def reconnect_broken_reads(project_root):
    """Show a dialog to reconnect static Read nodes whose file paths have moved.

    Scans all Read nodes for broken file paths (parent directory missing).
    Nodes with sm_output_dir knob are matched by output name against
    .versions.json files found under project_root.
    Nodes without the knob get a simple prefix-substitution UI.
    """
    try:
        import nuke
    except ImportError:
        return

    if project_root is None:
        return

    project_root = Path(project_root)

    # --- Collect broken Read nodes ---
    keyed_nodes = []    # [(node, output_name, old_dir_str)]  — have sm_output_dir
    legacy_nodes = []   # [node]  — no knob

    for node in nuke.allNodes("Read"):
        file_val = node["file"].value()
        if not file_val:
            continue
        parent = Path(file_val).parent
        if parent.exists():
            continue  # not broken

        if "sm_output_dir" in node.knobs():
            dir_val = node["sm_output_dir"].value()
            output_name = Path(dir_val).name if dir_val else ""
            keyed_nodes.append((node, output_name, dir_val))
        else:
            legacy_nodes.append(node)

    if not keyed_nodes and not legacy_nodes:
        nuke.message("No broken Read nodes found.")
        return

    # --- Search project for .versions.json candidates ---
    candidates_by_name = {}  # output_name -> [Path(output_dir), ...]
    for vj in project_root.rglob(".versions.json"):
        try:
            with open(vj, "r", encoding="utf-8") as f:
                data = json.load(f)
            vname = data.get("name", "")
            if vname:
                candidates_by_name.setdefault(vname, []).append(vj.parent)
        except Exception:
            continue

    # --- Build the Qt dialog ---
    try:
        from PySide6 import QtWidgets, QtCore
    except ImportError:
        from PySide2 import QtWidgets, QtCore

    dialog = QtWidgets.QDialog()
    dialog.setWindowTitle("Reconnect Read Nodes")
    dialog.setMinimumWidth(700)
    layout = QtWidgets.QVBoxLayout(dialog)

    # -- Keyed nodes table --
    row_data = []  # [(node, output_name, [candidate_paths])]
    if keyed_nodes:
        layout.addWidget(QtWidgets.QLabel("<b>Read nodes with Shot Manager metadata:</b>"))
        table = QtWidgets.QTableWidget(len(keyed_nodes), 3)
        table.setHorizontalHeaderLabels(["Node", "Old Location", "New Location"])
        table.horizontalHeader().setStretchLastSection(True)
        table.setSelectionMode(QtWidgets.QAbstractItemView.NoSelection)
        table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

        for row, (node, output_name, old_dir) in enumerate(keyed_nodes):
            candidates = candidates_by_name.get(output_name, [])
            row_data.append((node, output_name, candidates))

            table.setItem(row, 0, QtWidgets.QTableWidgetItem(node.name()))
            table.setItem(row, 1, QtWidgets.QTableWidgetItem(old_dir or "(unknown)"))

            combo = QtWidgets.QComboBox()
            combo.addItem("-- Not found --", None)
            for cand in candidates:
                combo.addItem(str(cand).replace("\\", "/"), str(cand))
            table.setCellWidget(row, 2, combo)

        table.resizeColumnsToContents()
        layout.addWidget(table)

    # -- Legacy nodes section --
    from_edit = None
    to_edit = None
    if legacy_nodes:
        layout.addWidget(QtWidgets.QLabel(
            f"<b>{len(legacy_nodes)} legacy Read node(s) without metadata</b> — replace path prefix:"
        ))
        grid = QtWidgets.QWidget()
        grid_layout = QtWidgets.QFormLayout(grid)
        from_edit = QtWidgets.QLineEdit()
        to_edit = QtWidgets.QLineEdit()
        grid_layout.addRow("From:", from_edit)
        grid_layout.addRow("To:", to_edit)
        layout.addWidget(grid)

    # -- Buttons --
    buttons = QtWidgets.QDialogButtonBox(
        QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel
    )
    buttons.button(QtWidgets.QDialogButtonBox.Ok).setText("Reconnect Selected")
    buttons.accepted.connect(dialog.accept)
    buttons.rejected.connect(dialog.reject)
    layout.addWidget(buttons)

    if dialog.exec_() != QtWidgets.QDialog.Accepted:
        return

    # --- Apply reconnections ---
    reconnected = 0

    # Keyed nodes: update from chosen candidate
    if keyed_nodes:
        for row, (node, output_name, candidates) in enumerate(row_data):
            combo = table.cellWidget(row, 2)
            new_dir_str = combo.currentData()
            if not new_dir_str:
                continue

            new_output_dir = Path(new_dir_str)
            vj = new_output_dir / ".versions.json"
            if not vj.exists():
                continue

            try:
                with open(vj, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except Exception:
                continue

            live_version_num = data.get("live_version")
            versions = {v["version"]: v for v in data.get("versions", [])}

            # Pick live version, else latest
            version_entry = None
            if live_version_num and live_version_num in versions:
                version_entry = versions[live_version_num]
            elif versions:
                version_entry = versions[max(versions)]

            if not version_entry:
                continue

            rel_path = version_entry.get("path", "")
            new_file_path = new_output_dir / rel_path
            new_file_str = str(new_file_path).replace("\\", "/")

            frames = version_entry.get("frames")
            first_frame = frames[0] if frames and len(frames) >= 2 else None
            last_frame = frames[1] if frames and len(frames) >= 2 else None

            ext = Path(new_file_str).suffix.lower()
            is_movie = ext in ('.mov', '.mp4', '.avi', '.mxf', '.mkv', '.mov64')
            if is_movie:
                node["file"].fromUserText(new_file_str)
            else:
                node["file"].setValue(new_file_str)
                if first_frame is not None and last_frame is not None:
                    node["first"].setValue(int(first_frame))
                    node["last"].setValue(int(last_frame))
                    node["origfirst"].setValue(int(first_frame))
                    node["origlast"].setValue(int(last_frame))

            node["sm_output_dir"].setValue(str(new_output_dir).replace("\\", "/"))
            print(f"[ShotManager] Reconnected '{node.name()}' → {new_file_str}")
            reconnected += 1

    # Legacy nodes: prefix substitution
    if legacy_nodes and from_edit and to_edit:
        from_str = from_edit.text().strip()
        to_str = to_edit.text().strip()
        if from_str and to_str:
            for node in legacy_nodes:
                old_file = node["file"].value()
                if from_str in old_file:
                    new_file = old_file.replace(from_str, to_str).replace("\\", "/")
                    node["file"].setValue(new_file)
                    print(f"[ShotManager] Prefix-fixed '{node.name()}' → {new_file}")
                    reconnected += 1

    nuke.message(f"Reconnected {reconnected} Read node(s).")
