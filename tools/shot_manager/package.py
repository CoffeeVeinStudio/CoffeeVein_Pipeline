"""Package shot for delivery — core logic.

Creates a Packaged/ directory in the shot root using hardlinks (default)
to avoid duplicating render data. Supports incremental updates.

Target structure:
    {shot_name}/
    └── Packaged/
        ├── script/
        │   ├── A004_C020_Comp_v001.nk
        │   └── A004_C020_Comp_v003.nk
        ├── plates/
        │   └── GreenScreen_v001/
        │       └── GreenScreen_v001.####.exr  (hardlinked)
        └── renders/
            ├── Denoise_v001/
            │   └── Denoise_v001.####.exr  (hardlinked)
            └── Beauty_v001/
                └── Beauty_v001.####.exr   (hardlinked)
"""

import os
import re
import shutil
from datetime import datetime
from pathlib import Path

from . import database
from .core import Output, OutputType, Version


# ---------------------------------------------------------------------------
# Path helpers
# ---------------------------------------------------------------------------

def get_packaged_dir(shot_dir):
    """Return the Packaged/ directory for a shot."""
    return Path(shot_dir) / "Packaged"


# ---------------------------------------------------------------------------
# Script discovery (from TIK work folders)
# ---------------------------------------------------------------------------

def scan_published_scripts(shot_dir):
    """Scan TIK work folders for .nk scripts.

    TIK stores Nuke scripts at:
        {shot}/{category}/nuke/{work_name}/{work_name}_v{NNN}.nk
    Example:
        A004_C020/Comp/nuke/A004_C020_Comp/A004_C020_Comp_v001.nk

    Returns:
        List of (display_name, source_path) tuples.
        display_name: e.g. "A004_C020_Comp_v001.nk"
        source_path: absolute Path to the .nk file
    """
    scripts = []
    shot_path = Path(shot_dir)

    # Scan each category directory (Comp, Cleanup, etc.)
    for category_dir in sorted(shot_path.iterdir()):
        if not category_dir.is_dir() or category_dir.name.startswith((".", "_")):
            continue

        nuke_dir = category_dir / "nuke"
        if not nuke_dir.exists():
            continue

        # Scan work directories under nuke/
        for work_dir in sorted(nuke_dir.iterdir()):
            if not work_dir.is_dir() or work_dir.name.startswith((".", "_")):
                continue
            # Skip known non-work dirs
            if work_dir.name in ("LIVE", "publish", "work"):
                continue

            # Find versioned .nk files: {work_name}_v001.nk
            for nk_file in sorted(work_dir.glob("*_v[0-9][0-9][0-9].nk")):
                scripts.append((nk_file.name, nk_file))

    return scripts


# ---------------------------------------------------------------------------
# Render discovery (from Shot Manager)
# ---------------------------------------------------------------------------

def scan_render_versions(shot_dir):
    """Discover all render output versions using Shot Manager database.

    Returns:
        List of (output_name, version_number, version_obj, version_dir) tuples.
        output_name: e.g. "Denoise"
        version_number: e.g. 1
        version_obj: Version dataclass with metadata (frames, format, etc.)
        version_dir: Path to the version directory on disk
    """
    outputs = database.discover_outputs(
        shot_dir, OutputType.RENDER, "Comp/renders"
    )

    results = []
    for output in outputs:
        output_dir = Path(shot_dir) / "Comp" / "renders" / output.name
        for version in output.versions:
            version_dir = output_dir / f"v{version.version:03d}"
            if version_dir.exists():
                results.append((
                    output.name,
                    version.version,
                    version,
                    version_dir,
                ))

    return results


# ---------------------------------------------------------------------------
# Plate / CG discovery (from Shot Manager)
# ---------------------------------------------------------------------------

_VERSION_DIR_RE = re.compile(r"^v(\d{3})$")


def _infer_version_from_disk(version_dir, version_number):
    """Build a lightweight Version object from files on disk."""
    files = [f for f in version_dir.iterdir() if f.is_file()]
    frames = None
    fmt = ""

    if files:
        fmt = files[0].suffix.lstrip(".")

        # Try to detect frame range from numbered sequences
        frame_numbers = []
        for f in files:
            m = re.search(r'\.(\d+)\.', f.name)
            if m:
                frame_numbers.append(int(m.group(1)))
        if frame_numbers:
            frames = [min(frame_numbers), max(frame_numbers)]

    return Version(
        version=version_number,
        created="",
        format=fmt,
        frames=frames,
    )


def scan_plate_versions(shot_dir):
    """Discover all plate and CG output versions in a shot.

    First checks Shot Manager metadata (.versions.json), then also scans
    for version directories on disk that lack metadata (manually placed plates).

    Returns:
        List of (output_name, version_number, version_obj, version_dir, output_type) tuples.
        output_type: "plate" or "cg" — used for display grouping.
    """
    results = []

    for output_type, type_folder in ((OutputType.PLATE, "Plates"),
                                     (OutputType.CG, "CG")):
        base_dir = Path(shot_dir) / type_folder
        if not base_dir.exists():
            continue

        # Collect known versions from .versions.json
        known = set()  # (output_name, version_number)
        outputs = database.discover_outputs(shot_dir, output_type, type_folder)
        for output in outputs:
            output_dir = base_dir / output.name
            for version in output.versions:
                version_dir = output_dir / f"v{version.version:03d}"
                if version_dir.exists():
                    known.add((output.name, version.version))
                    results.append((
                        output.name,
                        version.version,
                        version,
                        version_dir,
                        output_type,
                    ))

        # Also scan disk for output dirs without .versions.json
        for output_dir in sorted(base_dir.iterdir()):
            if not output_dir.is_dir() or output_dir.name.startswith((".", "_")):
                continue

            for entry in sorted(output_dir.iterdir()):
                if not entry.is_dir():
                    continue
                m = _VERSION_DIR_RE.match(entry.name)
                if not m:
                    continue
                ver_num = int(m.group(1))

                if (output_dir.name, ver_num) in known:
                    continue

                # Has files inside?
                if not any(entry.iterdir()):
                    continue

                version_obj = _infer_version_from_disk(entry, ver_num)
                results.append((
                    output_dir.name,
                    ver_num,
                    version_obj,
                    entry,
                    output_type,
                ))

    return results


# ---------------------------------------------------------------------------
# External Read node discovery (from Nuke script)
# ---------------------------------------------------------------------------

def scan_external_read_nodes(shot_dir, known_version_dirs):
    """Scan Nuke Read nodes for sources not in the known plates/renders.

    Compares each Read node's version directory against known_version_dirs.
    Returns external items in the same format as scan_plate_versions().

    Args:
        shot_dir: Current shot directory path.
        known_version_dirs: Set of already-known version dir paths (normalized, posix).

    Returns:
        List of (output_name, version_number, version_obj, version_dir, output_type) tuples.
        output_type is always "plate" for external items.
    """
    try:
        import nuke
    except ImportError:
        return []

    results = []
    seen_dirs = set()

    for node in nuke.allNodes("Read"):
        file_path = node["file"].value()
        if not file_path:
            continue

        path = Path(file_path)
        parent = path.parent

        # Determine version_dir, output_name, and version_number
        ver_match = _VERSION_DIR_RE.match(parent.name)
        if ver_match:
            # Case A: parent dir is v001/ — versioned structure
            version_dir = parent
            output_name = parent.parent.name
            version_number = int(ver_match.group(1))
        else:
            # Case B: no version dir — treat parent as the output directory
            version_dir = parent
            output_name = parent.name
            version_number = 1

        # Normalize for comparison and dedup
        normalized = version_dir.as_posix()
        if normalized in known_version_dirs:
            continue
        if normalized in seen_dirs:
            continue
        seen_dirs.add(normalized)

        # Verify directory exists and has files
        if not version_dir.exists() or not any(version_dir.iterdir()):
            continue

        version_obj = _infer_version_from_disk(version_dir, version_number)
        results.append((
            output_name,
            version_number,
            version_obj,
            version_dir,
            "plate",
        ))

    return results


# ---------------------------------------------------------------------------
# Incremental detection
# ---------------------------------------------------------------------------

def scan_existing_package(packaged_dir):
    """Scan Packaged/ to find already-packaged items.

    Returns:
        dict with keys:
            "scripts": set of display names (e.g. {"Comp_v001.nk"})
            "renders": set of folder names (e.g. {"Denoise_v001", "Beauty_v002"})
            "plates": set of folder names (e.g. {"GreenScreen_v001"})
    """
    result = {"scripts": set(), "renders": set(), "plates": set()}

    script_dir = Path(packaged_dir) / "script"
    if script_dir.exists():
        for f in script_dir.iterdir():
            if f.suffix == ".nk":
                result["scripts"].add(f.name)

    for subfolder, key in (("renders", "renders"), ("plates", "plates")):
        sub_dir = Path(packaged_dir) / subfolder
        if sub_dir.exists():
            for d in sub_dir.iterdir():
                if d.is_dir():
                    result[key].add(d.name)

    return result


# ---------------------------------------------------------------------------
# Hardlink / copy logic
# ---------------------------------------------------------------------------

def _is_unc_path(path):
    """Check if path is a UNC (network) path."""
    s = str(path)
    return s.startswith("\\\\") or s.startswith("//")


def can_hardlink(source, dest):
    """Check if hardlink is possible between source and dest.

    Returns:
        (can_link, reason) — reason is None if can_link is True.
    """
    if _is_unc_path(source):
        return False, "source is a network path"
    if _is_unc_path(dest):
        return False, "destination is a network path"

    source_drive = Path(source).drive.upper()
    dest_drive = Path(dest).drive.upper()

    if not source_drive:
        return False, "source has no drive letter"
    if not dest_drive:
        return False, "destination has no drive letter"
    if source_drive != dest_drive:
        return False, f"different drives ({source_drive} → {dest_drive})"

    return True, None


def _link_or_copy(source, dest, use_hardlink=True):
    """Hardlink a single file, or copy as fallback.

    Returns:
        (success, error_message_or_None)
    """
    dest = Path(dest)
    source = Path(source)

    if dest.exists():
        dest.unlink()

    if use_hardlink:
        try:
            os.link(source, dest)
            return True, None
        except OSError as e:
            return False, str(e)
    else:
        try:
            shutil.copy2(source, dest)
            return True, None
        except OSError as e:
            return False, str(e)


# ---------------------------------------------------------------------------
# Packaging operations
# ---------------------------------------------------------------------------

def package_scripts(script_items, packaged_dir, use_hardlink=True):
    """Hardlink/copy .nk script files into Packaged/script/.

    Args:
        script_items: list of (display_name, source_path) tuples.
        packaged_dir: Path to the Packaged/ directory.
        use_hardlink: True for hardlinks, False for copy.

    Returns:
        (successes, errors) — counts.
    """
    script_dest = Path(packaged_dir) / "script"
    script_dest.mkdir(parents=True, exist_ok=True)

    successes = 0
    errors = 0
    for display_name, source_path in script_items:
        dest = script_dest / display_name
        ok, err = _link_or_copy(source_path, dest, use_hardlink)
        if ok:
            successes += 1
        else:
            print(f"[Package] Failed to package {display_name}: {err}")
            errors += 1

    return successes, errors


def package_render_version(output_name, version_number, source_version_dir,
                           packaged_dir, use_hardlink=True,
                           progress_callback=None, dest_subfolder="renders"):
    """Hardlink/copy all frames from a version directory into Packaged/{dest_subfolder}/.

    Creates: Packaged/{dest_subfolder}/{output_name}_v{NNN}/

    Args:
        output_name: e.g. "Denoise"
        version_number: e.g. 1
        source_version_dir: Path to the version directory (e.g. .../Denoise/v001/)
        packaged_dir: Path to the Packaged/ directory.
        use_hardlink: True for hardlinks, False for copy.
        progress_callback: Optional callable(current, total, filename) for progress.
        dest_subfolder: Subfolder inside Packaged/ (default "renders", also "plates").

    Returns:
        (successes, errors) — frame counts.
    """
    folder_name = f"{output_name}_v{version_number:03d}"
    render_dest = Path(packaged_dir) / dest_subfolder / folder_name
    render_dest.mkdir(parents=True, exist_ok=True)

    source_dir = Path(source_version_dir)
    files = sorted(f for f in source_dir.iterdir() if f.is_file())

    successes = 0
    errors = 0
    for i, source_file in enumerate(files):
        if progress_callback:
            progress_callback(i, len(files), source_file.name)

        dest = render_dest / source_file.name
        ok, err = _link_or_copy(source_file, dest, use_hardlink)
        if ok:
            successes += 1
        else:
            print(f"[Package] Failed to link {source_file.name}: {err}")
            errors += 1

    return successes, errors


def get_render_folder_name(output_name, version_number):
    """Get the folder name used in Packaged/renders/ for a render version."""
    return f"{output_name}_v{version_number:03d}"


# ---------------------------------------------------------------------------
# Move-to-shot (for cross-drive items)
# ---------------------------------------------------------------------------

def move_to_shot(source_version_dir, shot_dir, output_type, output_name, version_number):
    """Copy a version directory into the shot's proper folder structure.

    Used when the source is on a different drive — copies files locally
    so they can then be hardlinked into Packaged/.

    E.g. copies external plate files into {shot}/Plates/{name}/v001/
    Returns the new local version_dir Path.
    """
    type_folder = OutputType.folder_for(output_type)
    dest_dir = Path(shot_dir) / type_folder / output_name / f"v{version_number:03d}"
    dest_dir.mkdir(parents=True, exist_ok=True)

    for f in Path(source_version_dir).iterdir():
        if f.is_file():
            shutil.copy2(f, dest_dir / f.name)

    # Create .versions.json so Shot Manager discovers the output
    output_dir = dest_dir.parent
    output = database.load_output(output_dir)
    if output is None:
        output = Output(
            name=output_name,
            shot=Path(shot_dir).name,
            output_type=output_type,
        )

    # Only add if this version doesn't already exist
    if output.get_version(version_number) is None:
        inferred = _infer_version_from_disk(dest_dir, version_number)

        # Build relative path pattern from first copied file
        files = sorted(f for f in dest_dir.iterdir() if f.is_file())
        if files:
            rel_path = f"v{version_number:03d}/{files[0].name}"
        else:
            rel_path = f"v{version_number:03d}/"

        version = Version(
            version=version_number,
            created=datetime.now().isoformat(timespec="seconds"),
            notes="Moved from external source (package dialog)",
            frames=inferred.frames,
            format=inferred.format,
            path=rel_path,
            status="complete",
        )
        output.versions.append(version)

    database.save_output(output, output_dir)

    return dest_dir
