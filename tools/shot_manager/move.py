"""Output moving operations for CoffeeVein Shot Manager.

Handles moving outputs between shots, to Reference, or back to _Incoming.
"""

import json
import shutil
from pathlib import Path
from typing import Optional, List, Tuple

from . import paths
from .core import OutputType, Output, Version


def get_next_version_number(output_dir: Path) -> int:
    """Get the next available version number in an output directory.

    Args:
        output_dir: Path to output directory (e.g., .../Comp/renders/Denoise/)

    Returns:
        Next available version number (1 if no versions exist)
    """
    if not output_dir.exists():
        return 1

    max_version = 0
    for entry in output_dir.iterdir():
        if entry.is_dir() and entry.name.startswith("v"):
            try:
                version_num = int(entry.name[1:])
                max_version = max(max_version, version_num)
            except ValueError:
                continue

    return max_version + 1


def move_output_to_shot(
    project_root: str,
    source_output: Output,
    source_base_dir: str,
    target_shot_name: str,
    new_output_name: Optional[str] = None
) -> Tuple[bool, str]:
    """Move an output (all versions) from one shot to another.

    Args:
        project_root: Project root path.
        source_output: Output object to move.
        source_base_dir: Base directory for source (shot or Reference dir).
        target_shot_name: Target shot name.
        new_output_name: Optional new name for the output (default: keep same name).

    Returns:
        (success, message) tuple
    """
    output_name = new_output_name if new_output_name else source_output.name

    # Get target shot directory
    shots_dir = paths.get_shots_dir(project_root)
    if not shots_dir:
        return False, "Could not find Shots directory"

    target_shot_dir = shots_dir / target_shot_name
    if not target_shot_dir.exists():
        return False, f"Target shot does not exist: {target_shot_name}"

    # Determine source and target output directories
    if source_output.output_type == OutputType.REFERENCE:
        # Source is project-level Reference with simplified structure
        source_output_dir = Path(source_base_dir) / source_output.name
    else:
        # Source is shot with standard structure
        source_output_dir = paths.get_output_dir(
            source_base_dir, source_output.output_type, source_output.name
        )

    target_output_dir = paths.get_output_dir(
        target_shot_dir, source_output.output_type, output_name
    )

    if not source_output_dir.exists():
        return False, f"Source output directory not found: {source_output_dir}"

    # Check if target already has this output (version conflict)
    version_offset = 0
    if target_output_dir.exists():
        # Merge: find next available version number at destination
        version_offset = get_next_version_number(target_output_dir) - 1

    # Move all version directories
    moved_versions = []
    try:
        target_output_dir.mkdir(parents=True, exist_ok=True)

        for version_dir in sorted(source_output_dir.iterdir()):
            if version_dir.is_dir() and version_dir.name.startswith("v"):
                try:
                    old_version_num = int(version_dir.name[1:])
                except ValueError:
                    continue

                # Skip LIVE symlink/junction
                if version_dir.name == "LIVE":
                    continue

                new_version_num = old_version_num + version_offset
                new_version_dir = target_output_dir / f"v{new_version_num:03d}"

                # Move version directory
                shutil.move(str(version_dir), str(new_version_dir))
                moved_versions.append((old_version_num, new_version_num))

        # Update .versions.json at both source and destination
        _update_versions_json_after_move(
            source_output_dir, target_output_dir,
            source_output.name, output_name,
            target_shot=target_shot_name,
            target_output_type=source_output.output_type,
            moved_versions=moved_versions,
        )

        # Handle LIVE symlink
        _update_live_after_move(
            source_output_dir, target_output_dir,
            source_output, moved_versions
        )

        # Clean up source if empty
        if source_output_dir.exists() and not any(source_output_dir.iterdir()):
            source_output_dir.rmdir()

        version_count = len(moved_versions)
        return True, f"Moved {version_count} version(s) to {target_shot_name}/{output_name}"

    except Exception as e:
        return False, f"Failed to move output: {e}"


def move_output_to_reference(
    project_root: str,
    source_output: Output,
    source_base_dir: str,
    new_output_name: Optional[str] = None
) -> Tuple[bool, str]:
    """Move an output from a shot to project-level Reference.

    Args:
        project_root: Project root path.
        source_output: Output object to move.
        source_base_dir: Base directory for source (shot dir).
        new_output_name: Optional new name for the output.

    Returns:
        (success, message) tuple
    """
    output_name = new_output_name if new_output_name else source_output.name

    # Get Reference directory
    reference_dir = paths.get_project_reference_dir(project_root)

    # Source output directory
    source_output_dir = paths.get_output_dir(
        source_base_dir, source_output.output_type, source_output.name
    )

    if not source_output_dir.exists():
        return False, f"Source output directory not found: {source_output_dir}"

    # Target: simplified Reference structure {reference_dir}/{output_name}/v001/
    target_output_dir = reference_dir / output_name

    # Check for version conflicts
    version_offset = 0
    if target_output_dir.exists():
        version_offset = get_next_version_number(target_output_dir) - 1

    # Move all versions
    moved_versions = []
    try:
        target_output_dir.mkdir(parents=True, exist_ok=True)

        for version_dir in sorted(source_output_dir.iterdir()):
            if version_dir.is_dir() and version_dir.name.startswith("v"):
                try:
                    old_version_num = int(version_dir.name[1:])
                except ValueError:
                    continue

                if version_dir.name == "LIVE":
                    continue

                new_version_num = old_version_num + version_offset
                new_version_dir = target_output_dir / f"v{new_version_num:03d}"

                shutil.move(str(version_dir), str(new_version_dir))
                moved_versions.append((old_version_num, new_version_num))

        # Update .versions.json
        _update_versions_json_after_move(
            source_output_dir, target_output_dir,
            source_output.name, output_name,
            target_shot="",  # Reference is project-level, no shot
            target_output_type=OutputType.REFERENCE,
            moved_versions=moved_versions,
        )

        # Handle LIVE
        _update_live_after_move(
            source_output_dir, target_output_dir,
            source_output, moved_versions
        )

        # Clean up source
        if source_output_dir.exists() and not any(source_output_dir.iterdir()):
            source_output_dir.rmdir()

        version_count = len(moved_versions)
        return True, f"Moved {version_count} version(s) to Reference/{output_name}"

    except Exception as e:
        return False, f"Failed to move output: {e}"


def move_output_to_incoming(
    project_root: str,
    source_output: Output,
    source_base_dir: str,
    incoming_subfolder: str  # "Plates", "CG", or "Reference"
) -> Tuple[bool, str]:
    """Move an output back to _Incoming, flattening version structure.

    Args:
        project_root: Project root path.
        source_output: Output object to move.
        source_base_dir: Base directory for source.
        incoming_subfolder: Target subfolder in _Incoming (Plates/CG/Reference).

    Returns:
        (success, message) tuple
    """
    # Get _Incoming directory
    incoming_dir = paths.get_incoming_dir(project_root)
    target_dir = incoming_dir / incoming_subfolder
    target_dir.mkdir(parents=True, exist_ok=True)

    # Source output directory
    if source_output.output_type == OutputType.REFERENCE:
        source_output_dir = Path(source_base_dir) / source_output.name
    else:
        source_output_dir = paths.get_output_dir(
            source_base_dir, source_output.output_type, source_output.name
        )

    if not source_output_dir.exists():
        return False, f"Source output directory not found: {source_output_dir}"

    # Flatten: move all files from all versions to _Incoming
    moved_files = 0
    try:
        for version_dir in sorted(source_output_dir.iterdir()):
            if version_dir.is_dir() and version_dir.name.startswith("v"):
                if version_dir.name == "LIVE":
                    continue

                # Move all files from this version to _Incoming
                for file_path in version_dir.iterdir():
                    if file_path.is_file():
                        target_file = target_dir / file_path.name
                        # Handle name conflicts: add suffix
                        counter = 1
                        while target_file.exists():
                            stem = file_path.stem
                            suffix = file_path.suffix
                            target_file = target_dir / f"{stem}_{counter}{suffix}"
                            counter += 1

                        shutil.move(str(file_path), str(target_file))
                        moved_files += 1

        # Delete LIVE symlink if exists
        live_dir = source_output_dir / "LIVE"
        if live_dir.exists():
            _delete_symlink_or_junction(live_dir)

        # Delete .versions.json if exists
        versions_json = source_output_dir / ".versions.json"
        if versions_json.exists():
            versions_json.unlink()

        # Clean up empty directories
        for version_dir in list(source_output_dir.iterdir()):
            if version_dir.is_dir() and not any(version_dir.iterdir()):
                version_dir.rmdir()

        if source_output_dir.exists() and not any(source_output_dir.iterdir()):
            source_output_dir.rmdir()

        return True, f"Moved {moved_files} file(s) to _Incoming/{incoming_subfolder}"

    except Exception as e:
        return False, f"Failed to move to _Incoming: {e}"


def _update_versions_json_after_move(
    source_dir: Path,
    target_dir: Path,
    source_name: str,
    target_name: str,
    target_shot: str,
    target_output_type: str,
    moved_versions: List[Tuple[int, int]]  # [(old_num, new_num), ...]
):
    """Update .versions.json files after moving versions.

    Removes moved versions from source, adds to target with new version numbers.
    Ensures target .versions.json has full metadata (name, shot, type).
    """
    # Read source .versions.json
    source_json = source_dir / ".versions.json"
    source_data = {"versions": []}
    if source_json.exists():
        with open(source_json, "r", encoding="utf-8") as f:
            source_data = json.load(f)

    # Read or create target .versions.json with full metadata
    target_json = target_dir / ".versions.json"
    target_data = {
        "name": target_name,
        "shot": target_shot,
        "type": target_output_type,
        "versions": [],
    }
    if target_json.exists():
        with open(target_json, "r", encoding="utf-8") as f:
            existing = json.load(f)
            target_data["versions"] = existing.get("versions", [])

    # Build mapping of old → new version numbers
    version_map = {old: new for old, new in moved_versions}

    # Move version entries from source to target
    remaining_source_versions = []
    for version_entry in source_data.get("versions", []):
        old_version_num = version_entry.get("version")
        if old_version_num in version_map:
            # This version was moved: add to target with new number
            new_entry = version_entry.copy()
            new_entry["version"] = version_map[old_version_num]
            target_data["versions"].append(new_entry)
        else:
            # This version stayed: keep in source
            remaining_source_versions.append(version_entry)

    # Sort target versions by version number
    target_data["versions"].sort(key=lambda v: v.get("version", 0))

    # Write updated JSONs
    if remaining_source_versions:
        source_data["versions"] = remaining_source_versions
        with open(source_json, "w", encoding="utf-8") as f:
            json.dump(source_data, f, indent=2)
    elif source_json.exists():
        # No versions left at source: delete .versions.json
        source_json.unlink()

    with open(target_json, "w", encoding="utf-8") as f:
        json.dump(target_data, f, indent=2)


def _update_live_after_move(
    source_dir: Path,
    target_dir: Path,
    source_output: Output,
    moved_versions: List[Tuple[int, int]]
):
    """Update LIVE symlinks after moving versions.

    If source had a LIVE version that was moved:
    - Check if target already has LIVE (keep it)
    - If not, create LIVE at target pointing to moved version

    Always delete source LIVE.
    """
    source_live = source_dir / "LIVE"
    target_live = target_dir / "LIVE"

    # Check if target already has LIVE
    if target_live.exists():
        # Keep existing target LIVE, just delete source LIVE
        if source_live.exists():
            _delete_symlink_or_junction(source_live)
        return

    # Check if source's LIVE version was moved
    if source_live.exists() and source_output.live_version:
        version_map = {old: new for old, new in moved_versions}
        if source_output.live_version in version_map:
            # Source LIVE was moved: create LIVE at target
            new_live_version = version_map[source_output.live_version]
            target_version_dir = target_dir / f"v{new_live_version:03d}"

            if target_version_dir.exists():
                _create_symlink_or_junction(target_version_dir, target_live)

        # Delete source LIVE
        _delete_symlink_or_junction(source_live)


def _create_symlink_or_junction(target: Path, link: Path):
    """Create a symlink (Unix) or junction (Windows) pointing to target."""
    import os
    if os.name == "nt":
        # Windows: use junction
        import subprocess
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(target)],
            check=True,
            capture_output=True
        )
    else:
        # Unix: use symlink
        link.symlink_to(target, target_is_directory=True)


def _delete_symlink_or_junction(path: Path):
    """Delete a symlink or junction without deleting the target."""
    import os
    if os.name == "nt":
        # Windows: use rmdir for junctions (doesn't delete target)
        import subprocess
        subprocess.run(
            ["cmd", "/c", "rmdir", str(path)],
            check=True,
            capture_output=True
        )
    else:
        # Unix: unlink symlink
        path.unlink()
