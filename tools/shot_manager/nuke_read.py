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


def create_read_node(file_path, first_frame=None, last_frame=None, name=None, colorspace="default"):
    """Create a Read node with a static file path.

    Args:
        file_path: Absolute path to the file/sequence (e.g., "Z:/.../.../v001/Name.####.exr")
        first_frame: First frame of the sequence (None for movies).
        last_frame: Last frame of the sequence (None for movies).
        name: Optional custom name for the Read node.
        colorspace: Colorspace to set (default: "default" uses Nuke's auto-detect).

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
