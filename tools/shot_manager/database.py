"""JSON database for CoffeeVein Shot Manager.

Each Output (render, plate, etc.) stores its version history in a
`.versions.json` file inside its output folder. This module handles
reading and writing those files with file locking for safety.
"""

import json
import os
from pathlib import Path

from .core import Output, OutputType


VERSIONS_FILENAME = ".versions.json"


def _infer_metadata_from_path(output_dir):
    """Infer output name, type, and shot name from directory structure.

    Directory layouts:
        {shot}/Comp/renders/{name}  → render, shot is 3 levels up
        {shot}/Plates/{name}        → plate, shot is 2 levels up
        {shot}/CG/{name}            → cg, shot is 2 levels up
        {shot}/Reference/{name}     → reference, shot is 2 levels up
    """
    output_dir = Path(output_dir)
    name = output_dir.name
    parent_name = output_dir.parent.name.lower()

    if parent_name == "renders":
        return name, output_dir.parent.parent.parent.name, OutputType.RENDER
    elif parent_name == "plates":
        return name, output_dir.parent.parent.name, OutputType.PLATE
    elif parent_name == "cg":
        return name, output_dir.parent.parent.name, OutputType.CG
    elif parent_name == "reference":
        return name, output_dir.parent.parent.name, OutputType.REFERENCE
    else:
        return name, output_dir.parent.parent.name, OutputType.RENDER


def _ensure_dir(path):
    """Create directory if it doesn't exist."""
    Path(path).mkdir(parents=True, exist_ok=True)


def load_output(output_dir):
    """Load an Output from its .versions.json file.

    Performs auto-repair if metadata (name, shot, type) doesn't match
    the directory structure — fixes in-memory and rewrites JSON to disk.

    Args:
        output_dir: Path to the output directory (e.g., .../renders/Denoise/)

    Returns:
        Output object, or None if no .versions.json exists.
    """
    output_dir = Path(output_dir)
    versions_file = output_dir / VERSIONS_FILENAME
    if not versions_file.exists():
        return None

    try:
        with open(versions_file, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        print(f"[ShotManager] Warning: corrupt .versions.json at {output_dir}, rebuilding metadata")
        data = {}

    output = Output.from_dict(data)

    # Auto-repair: directory path is ground truth for name/shot/type
    expected_name, expected_shot, expected_type = _infer_metadata_from_path(output_dir)
    if output.name != expected_name or output.shot != expected_shot or output.output_type != expected_type:
        print(f"[ShotManager] Repairing .versions.json metadata at {output_dir.name}")
        output.name = expected_name
        output.shot = expected_shot
        output.output_type = expected_type
        try:
            save_output(output, output_dir)
        except OSError as e:
            print(f"[ShotManager] Warning: could not write repaired .versions.json: {e}")

    return output


def save_output(output, output_dir):
    """Save an Output to its .versions.json file.

    Args:
        output: Output object to save.
        output_dir: Path to the output directory.
    """
    _ensure_dir(output_dir)
    versions_file = Path(output_dir) / VERSIONS_FILENAME

    data = output.to_dict()

    # Write atomically: write to temp file then rename
    tmp_file = versions_file.with_suffix(".tmp")
    with open(tmp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)

    # On Windows, need to remove target first if it exists
    if versions_file.exists():
        versions_file.unlink()
    tmp_file.rename(versions_file)


def discover_outputs(shot_dir, output_type, type_folder):
    """Discover all outputs of a given type in a shot directory.

    Scans for .versions.json files in the expected folder structure.

    Args:
        shot_dir: Path to the shot directory (e.g., .../Shots/A004_C020/)
        output_type: OutputType string (e.g., "render")
        type_folder: Relative folder for this type (e.g., "Comp/renders")

    Returns:
        List of Output objects found.
    """
    base_dir = Path(shot_dir) / type_folder
    if not base_dir.exists():
        return []

    outputs = []
    for entry in sorted(base_dir.iterdir()):
        if entry.is_dir():
            try:
                output = load_output(entry)
                if output is not None:
                    outputs.append(output)
            except Exception as e:
                print(f"[ShotManager] Warning: failed to load output from {entry}: {e}")
    return outputs


def get_output_dir(shot_dir, output_type_folder, output_name):
    """Get the directory path for a specific output.

    Args:
        shot_dir: Path to the shot directory.
        output_type_folder: Relative folder (e.g., "Comp/renders").
        output_name: Name of the output (e.g., "Denoise").

    Returns:
        Path object for the output directory.
    """
    return Path(shot_dir) / output_type_folder / output_name


def get_version_dir(output_dir, version_number):
    """Get the directory path for a specific version.

    Args:
        output_dir: Path to the output directory.
        version_number: Version number (integer).

    Returns:
        Path object for the version directory (e.g., .../Denoise/v001/).
    """
    return Path(output_dir) / f"v{version_number:03d}"
