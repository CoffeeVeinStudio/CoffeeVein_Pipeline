"""Path resolution for CoffeeVein Shot Manager.

Discovers project structure by reading TIK's project_structure.json
and scanning the filesystem. Works without TIK being imported — only
reads the JSON files directly.
"""

import json
from pathlib import Path

from .core import OutputType


# ---------------------------------------------------------------------------
# Project discovery
# ---------------------------------------------------------------------------

TIK_DATABASE_DIR = "tikDatabase"
TIK_STRUCTURE_FILE = "project_structure.json"


def find_project_root(start_path=None):
    """Find the TIK project root by looking for tikDatabase/project_structure.json.

    Searches upward from start_path (or cwd if None).

    Returns:
        Path to project root, or None if not found.
    """
    if start_path is None:
        start_path = Path.cwd()
    else:
        start_path = Path(start_path)

    current = start_path.absolute()
    for _ in range(20):  # Limit search depth
        tik_dir = current / TIK_DATABASE_DIR / TIK_STRUCTURE_FILE
        if tik_dir.exists():
            return current
        parent = current.parent
        if parent == current:
            break
        current = parent
    return None


def load_project_structure(project_root):
    """Load TIK's project structure JSON.

    Args:
        project_root: Path to the project root directory.

    Returns:
        Dictionary with project structure, or None on error.
    """
    structure_file = Path(project_root) / TIK_DATABASE_DIR / TIK_STRUCTURE_FILE
    if not structure_file.exists():
        return None

    with open(structure_file, "r", encoding="utf-8") as f:
        return json.load(f)


def get_project_name(project_root):
    """Get the project name from TIK's structure file."""
    structure = load_project_structure(project_root)
    if structure:
        return structure.get("name", Path(project_root).name)
    return Path(project_root).name


def get_shots_dir(project_root):
    """Get the Shots directory path.

    Reads TIK's project_structure.json to find the Shots sub-project,
    falls back to looking for a 'Shots' directory.
    """
    structure = load_project_structure(project_root)
    if structure:
        for sub in structure.get("subs", []):
            if sub.get("name") == "Shots" and not sub.get("deleted"):
                return Path(project_root) / sub["path"]

    # Fallback: look for Shots directory
    shots_dir = Path(project_root) / "Shots"
    if shots_dir.exists():
        return shots_dir
    return None


def get_incoming_dir(project_root):
    """Get the _Incoming directory path."""
    return Path(project_root) / "_Incoming"


def get_project_reference_dir(project_root):
    """Get the project-level Reference directory.

    Returns:
        Path to {project_root}/Reference/

    This is a project-wide asset directory (not per-shot) for shared
    reference materials like HDRIs, texture libraries, LUTs, etc.
    """
    return Path(project_root) / "Reference"


# ---------------------------------------------------------------------------
# Shot discovery
# ---------------------------------------------------------------------------

def discover_shots(project_root):
    """Discover all shots in the project.

    Returns:
        List of (shot_name, shot_path) tuples, sorted by name.
    """
    shots_dir = get_shots_dir(project_root)
    if shots_dir is None or not shots_dir.exists():
        return []

    shots = []
    for entry in sorted(shots_dir.iterdir()):
        if entry.is_dir() and not entry.name.startswith((".", "_")):
            shots.append((entry.name, str(entry)))
    return shots


# ---------------------------------------------------------------------------
# Output paths
# ---------------------------------------------------------------------------

def get_output_base_dir(shot_dir, output_type):
    """Get the base directory for a given output type within a shot.

    Args:
        shot_dir: Path to the shot directory.
        output_type: OutputType string (e.g., "render", "plate").

    Returns:
        Path to the type's base directory (e.g., .../A004_C020/Comp/renders/).
    """
    type_folder = OutputType.folder_for(output_type)
    return Path(shot_dir) / type_folder


def get_output_dir(shot_dir, output_type, output_name):
    """Get the directory for a specific named output.

    Args:
        shot_dir: Path to the shot directory.
        output_type: OutputType string.
        output_name: Name of the output (e.g., "Denoise").

    Returns:
        Path to the output directory (e.g., .../Comp/renders/Denoise/).
    """
    return get_output_base_dir(shot_dir, output_type) / output_name


def get_version_dir(shot_dir, output_type, output_name, version_number):
    """Get the directory for a specific version of an output.

    Returns:
        Path (e.g., .../Comp/renders/Denoise/v001/).
    """
    return get_output_dir(shot_dir, output_type, output_name) / f"v{version_number:03d}"


def get_live_dir(shot_dir, output_type, output_name):
    """Get the LIVE directory path for an output.

    Returns:
        Path (e.g., .../Comp/renders/Denoise/LIVE/).
    """
    return get_output_dir(shot_dir, output_type, output_name) / "LIVE"


# ---------------------------------------------------------------------------
# Project settings from TIK
# ---------------------------------------------------------------------------

def get_project_settings(project_root):
    """Read basic project settings from TIK's structure (fps, resolution, start_frame).

    Returns:
        Dictionary with fps, resolution, start_frame keys, or defaults.
    """
    defaults = {"fps": 25.0, "resolution": [1920, 1080], "start_frame": 1001}

    structure = load_project_structure(project_root)
    if not structure:
        return defaults

    # Settings are often on the Shots sub-project
    for sub in structure.get("subs", []):
        if sub.get("name") == "Shots":
            if "fps" in sub:
                defaults["fps"] = sub["fps"]
            if "resolution" in sub:
                defaults["resolution"] = sub["resolution"]
            if "start_frame" in sub:
                defaults["start_frame"] = sub["start_frame"]
            break

    return defaults
