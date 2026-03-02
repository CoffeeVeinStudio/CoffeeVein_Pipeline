"""Incoming file management for CoffeeVein Shot Manager.

Scans the _Incoming directory, detects file sequences and movies,
helps classify and move them into the shot structure with versioning.
"""

import os
import re
import shutil
from pathlib import Path
from collections import defaultdict

from .core import Output, OutputType
from . import database, paths


# ---------------------------------------------------------------------------
# _Incoming subdirectory mapping
# ---------------------------------------------------------------------------

INCOMING_SUBDIRS = {
    "Plates": OutputType.PLATE,
    "CG": OutputType.CG,
    "Reference": OutputType.REFERENCE,
}


# ---------------------------------------------------------------------------
# Sequence detection
# ---------------------------------------------------------------------------

# Matches frame numbers in filenames: name.1001.exr, name_0119.tif, name.1.jpg
_FRAME_PATTERN = re.compile(r'^(.+?)[._](\d+)(\.\w+)$')

# Movie/video extensions
_MOVIE_EXTS = {'.mov', '.mp4', '.avi', '.mxf', '.mkv'}

# All Nuke-supported image/sequence extensions
_SEQ_EXTS = {
    '.exr',                             # OpenEXR
    '.dpx',                             # DPX
    '.cin',                             # CIN
    '.tif', '.tiff',                    # TIFF
    '.tga', '.targa',                   # TARGA
    '.png',                             # PNG
    '.jpg', '.jpeg',                    # JPEG
    '.sgi', '.rgb', '.rgba',            # SGI
    '.hdr', '.hdri',                    # Radiance
    '.iff',                             # Maya IFF
    '.psd',                             # Photoshop
    '.pic',                             # SoftImage PIC
    '.rla',                             # RLA
    '.xpm',                             # XPM
    '.yuv',                             # YUV
    '.gif',                             # GIF
    '.dng',                             # DNG
    '.ari',                             # ARRIRAW
    '.r3d',                             # REDCODE RAW
    '.dtex',                            # DTEX
}

# 3D geometry extensions (Nuke 3D system — cameras, objects, animation)
_GEO_EXTS = {'.abc', '.obj', '.fbx'}


class IncomingItem:
    """Represents a detected item in _Incoming (sequence or single file)."""

    def __init__(self, name, path, item_type="unknown"):
        self.name = name  # Display name (e.g., "A004_C020_0129VV_001")
        self.path = path  # Absolute path to folder or file
        self.item_type = item_type  # "sequence", "movie", "folder", "file"
        self.frame_range = None  # (first, last) for sequences
        self.frame_count = 0
        self.extension = ""
        self.pattern = ""  # e.g., "name.####.exr"
        self.suggested_shot = None  # Auto-detected shot name
        self.suggested_type = None  # Auto-detected output type (plate, cg, etc.)
        self.files = []  # List of actual file paths

    def __repr__(self):
        return f"IncomingItem({self.name!r}, type={self.item_type}, frames={self.frame_range})"


def scan_incoming(project_root):
    """Scan the _Incoming directory for new items.

    Scans three pre-sorted subdirectories (Plates/, CG/, Reference/) and
    tags each item with the corresponding OutputType. Loose files/folders
    in the _Incoming root are tagged as unsorted (suggested_type=None).

    Args:
        project_root: Path to the project root.

    Returns:
        List of IncomingItem objects.
    """
    incoming_dir = paths.get_incoming_dir(project_root)
    if not incoming_dir.exists():
        return []

    items = []

    # Scan each pre-sorted subdirectory
    for subdir_name, output_type in INCOMING_SUBDIRS.items():
        subdir = incoming_dir / subdir_name
        if not subdir.exists():
            continue
        sub_items = []
        _scan_directory(subdir, sub_items, depth=0, max_depth=2)
        for item in sub_items:
            item.suggested_type = output_type
        items.extend(sub_items)

    # Scan root for loose (unsorted) items
    loose_root_images = []

    for entry in sorted(incoming_dir.iterdir()):
        if entry.name.startswith(('.', '_')) or entry.name.endswith('.thumbnail.jpg'):
            continue
        # Skip the known subdirectories
        if entry.is_dir() and entry.name in INCOMING_SUBDIRS:
            continue

        if entry.is_file():
            ext = entry.suffix.lower()
            if ext in _MOVIE_EXTS:
                item = IncomingItem(
                    name=entry.stem,
                    path=str(entry),
                    item_type="movie"
                )
                item.extension = ext
                item.files = [str(entry)]
                item.suggested_shot = _guess_shot_name(entry.stem)
                item.suggested_type = None  # Unsorted
                items.append(item)
            elif ext in _SEQ_EXTS:
                # Collect for sequence grouping
                loose_root_images.append(entry)
        elif entry.is_dir():
            # Unrecognized folder at root — could be a sequence or misc folder
            seq = _detect_sequence(entry)
            if seq is not None:
                seq.suggested_type = None  # Unsorted
                items.append(seq)
            else:
                item = IncomingItem(
                    name=entry.name,
                    path=str(entry),
                    item_type="folder"
                )
                item.suggested_type = None  # Unsorted
                items.append(item)

    # Group loose root image files into sequences where possible
    seq_items, single_items = _group_loose_sequences(loose_root_images, incoming_dir)
    for item in seq_items + single_items:
        item.suggested_type = None  # Unsorted
    items.extend(seq_items)
    items.extend(single_items)

    return items


def create_incoming_dirs(project_root):
    """Create the pre-sorted _Incoming subdirectories if they don't exist.

    Creates:
        _Incoming/Plates/
        _Incoming/CG/
        _Incoming/Reference/

    Args:
        project_root: Path to the project root.

    Returns:
        Path to the _Incoming directory.
    """
    incoming_dir = paths.get_incoming_dir(project_root)
    for subdir_name in INCOMING_SUBDIRS:
        (incoming_dir / subdir_name).mkdir(parents=True, exist_ok=True)
    return incoming_dir


def _group_loose_sequences(image_files, parent_dir):
    """Group loose image files into sequences by (base_name, extension).

    Files matching _FRAME_PATTERN are grouped. Groups with >=2 frames become
    a single sequence IncomingItem. Remaining files (non-matching or single-
    frame groups) become individual file items.

    Args:
        image_files: List of Path objects for image files.
        parent_dir: The directory containing these files (used as item.path
                    for sequences since they have no dedicated folder).

    Returns:
        Tuple of (sequence_items, single_items).
    """
    seq_groups = defaultdict(list)  # (base_name, ext) → [(frame_num, path)]
    non_matching = []

    for f in image_files:
        match = _FRAME_PATTERN.match(f.name)
        if match:
            base = match.group(1)
            frame = int(match.group(2))
            ext = match.group(3)
            seq_groups[(base, ext)].append((frame, str(f)))
        else:
            non_matching.append(f)

    sequence_items = []
    single_items = []

    for (base_name, ext), frames in seq_groups.items():
        if len(frames) >= 2:
            frames.sort()
            first_frame = frames[0][0]
            last_frame = frames[-1][0]

            # Determine padding from first frame filename
            first_file = Path(frames[0][1])
            match = _FRAME_PATTERN.match(first_file.name)
            padding = len(match.group(2))
            pad_str = "#" * padding

            item = IncomingItem(
                name=base_name,
                path=str(parent_dir),
                item_type="sequence"
            )
            item.frame_range = (first_frame, last_frame)
            item.frame_count = len(frames)
            item.extension = ext
            item.pattern = f"{base_name}.{pad_str}{ext}"
            item.files = [f[1] for f in frames]
            item.suggested_shot = _guess_shot_name(base_name)
            sequence_items.append(item)
        else:
            # Single frame — treat as individual file
            f_path = Path(frames[0][1])
            item = IncomingItem(
                name=f_path.stem,
                path=str(f_path),
                item_type="file"
            )
            item.extension = ext
            item.files = [str(f_path)]
            item.suggested_shot = _guess_shot_name(f_path.stem)
            single_items.append(item)

    # Non-matching image files are also individual items
    for f in non_matching:
        item = IncomingItem(
            name=f.stem,
            path=str(f),
            item_type="file"
        )
        item.extension = f.suffix.lower()
        item.files = [str(f)]
        item.suggested_shot = _guess_shot_name(f.stem)
        single_items.append(item)

    return sequence_items, single_items


def _scan_directory(directory, items, depth, max_depth):
    """Recursively scan a directory for items."""
    if depth > max_depth:
        return

    # Collect loose image files for sequence grouping
    loose_image_files = []

    for entry in sorted(Path(directory).iterdir()):
        if entry.name.startswith(('.', '_')) or entry.name.endswith('.thumbnail.jpg'):
            continue

        if entry.is_file():
            ext = entry.suffix.lower()
            if ext in _MOVIE_EXTS:
                item = IncomingItem(
                    name=entry.stem,
                    path=str(entry),
                    item_type="movie"
                )
                item.extension = ext
                item.files = [str(entry)]
                item.suggested_shot = _guess_shot_name(entry.stem)
                items.append(item)
            elif ext in _GEO_EXTS:
                item = IncomingItem(
                    name=entry.stem,
                    path=str(entry),
                    item_type="geo"
                )
                item.extension = ext
                item.files = [str(entry)]
                items.append(item)
            elif ext in _SEQ_EXTS:
                # Collect for sequence grouping instead of adding immediately
                loose_image_files.append(entry)

        elif entry.is_dir():
            # Check if it's a sequence folder
            seq = _detect_sequence(entry)
            if seq is not None:
                items.append(seq)
            else:
                # Recurse into subfolder
                _scan_directory(entry, items, depth + 1, max_depth)

    # Group loose image files into sequences where possible
    seq_items, single_items = _group_loose_sequences(loose_image_files, directory)
    items.extend(seq_items)
    items.extend(single_items)


def _detect_sequence(folder):
    """Check if a folder contains an image sequence.

    Returns:
        IncomingItem if sequence detected, None otherwise.
    """
    sequences = defaultdict(list)  # base_name → [(frame_num, full_path)]

    for f in sorted(folder.iterdir()):
        if not f.is_file():
            continue
        match = _FRAME_PATTERN.match(f.name)
        if match:
            base = match.group(1)
            frame = int(match.group(2))
            ext = match.group(3)
            sequences[(base, ext)].append((frame, str(f)))

    if not sequences:
        return None

    # Use the largest sequence found
    best_key = max(sequences, key=lambda k: len(sequences[k]))
    frames = sequences[best_key]
    base_name, ext = best_key

    if len(frames) < 2:
        return None  # Not really a sequence

    frames.sort()
    first_frame = frames[0][0]
    last_frame = frames[-1][0]

    # Determine padding from first frame filename
    first_file = Path(frames[0][1])
    match = _FRAME_PATTERN.match(first_file.name)
    padding = len(match.group(2))
    pad_str = "#" * padding

    item = IncomingItem(
        name=base_name,
        path=str(folder),
        item_type="sequence"
    )
    item.frame_range = (first_frame, last_frame)
    item.frame_count = len(frames)
    item.extension = ext
    item.pattern = f"{base_name}.{pad_str}{ext}"
    item.files = [f[1] for f in frames]
    item.suggested_shot = _guess_shot_name(base_name)

    return item


def _guess_shot_name(name):
    """Try to extract a shot name from a filename.

    Looks for patterns like A004_C020 in the name.

    Returns:
        Guessed shot name string, or None.
    """
    # Match camera card naming: A###_C###
    match = re.search(r'(A\d{3}_C\d{3})', name, re.IGNORECASE)
    if match:
        return match.group(1).upper()

    # Match scene/shot naming: sc##_sh###
    match = re.search(r'(sc\d+_sh\d+)', name, re.IGNORECASE)
    if match:
        return match.group(1)

    return None


# ---------------------------------------------------------------------------
# Ingest — move incoming items into shot structure
# ---------------------------------------------------------------------------

def ingest_item(item, project_root, shot_name, output_name, output_type,
                notes="", creator="Admin"):
    """Ingest an incoming item into the shot structure or project-level Reference.

    Moves files from _Incoming into the appropriate versioned folder
    and creates the .versions.json entry.

    For REFERENCE outputs: targets {project_root}/Reference/{output_name}/
    For other outputs: targets {shots_dir}/{shot_name}/Comp/{type_folder}/{output_name}/

    Args:
        item: IncomingItem to ingest.
        project_root: Path to the project root.
        shot_name: Target shot name (e.g., "A004_C020") — ignored for REFERENCE type.
        output_name: Name for this output (e.g., "GreenScreen", "Background").
        output_type: OutputType string (e.g., "plate", "cg", "reference").
        notes: Version notes.
        creator: Who ingested this.

    Returns:
        Tuple of (Output, Version) for the created version.
    """
    # Check if this is a project-level REFERENCE
    if output_type == OutputType.REFERENCE:
        # Use project-level Reference directory
        reference_dir = paths.get_project_reference_dir(project_root)
        base_dir = reference_dir
        shot_name = "Project"  # Use "Project" as pseudo-shot name
    else:
        # Use shot-level directory
        shots_dir = paths.get_shots_dir(project_root)
        base_dir = shots_dir / shot_name

    # Ensure base directory exists
    base_dir.mkdir(parents=True, exist_ok=True)

    # Get/create output
    if output_type == OutputType.REFERENCE:
        # For project-level reference, output_dir is directly under Reference/
        output_dir = base_dir / output_name
    else:
        output_dir = paths.get_output_dir(base_dir, output_type, output_name)
    output = database.load_output(output_dir)
    if output is None:
        output = Output(
            name=output_name,
            shot=shot_name,
            output_type=output_type,
        )

    # Create version directory
    version_number = output.next_version_number
    if output_type == OutputType.REFERENCE:
        # For project-level reference, version_dir is directly under output_dir
        version_dir = output_dir / f"v{version_number:03d}"
    else:
        version_dir = paths.get_version_dir(
            base_dir, output_type, output_name, version_number
        )
    version_dir.mkdir(parents=True, exist_ok=True)

    # Move files
    src_thumb_path = None
    dst_thumb_path = None
    if item.item_type == "sequence":
        # Build new pattern with version number in filename
        base_name = item.name
        version_suffix = f"_v{version_number:03d}"
        # Extract padding from item.pattern (e.g., "name.####.exr" → "####")
        padding_match = re.search(r'(#+)', item.pattern)
        padding = padding_match.group(1) if padding_match else "####"
        ext = item.extension
        new_pattern = f"{base_name}{version_suffix}.{padding}{ext}"

        # Move and rename files to include version
        for src_file in item.files:
            src = Path(src_file)
            # Extract frame number from source filename
            frame_match = re.match(r'^.+?[._](\d{3,})(\.\w+)$', src.name)
            if frame_match:
                frame_num = frame_match.group(1)
                new_name = f"{base_name}{version_suffix}.{frame_num}{ext}"
                dst = version_dir / new_name
                shutil.move(str(src), str(dst))

        src_thumb_path = Path(item.path) / item.pattern
        dst_thumb_path = version_dir / new_pattern

        # Build relative path pattern
        rel_path = f"v{version_number:03d}/{new_pattern}"
        fmt = item.extension.lstrip(".")

    elif item.item_type == "movie":
        src = Path(item.path)
        version_suffix = f"_v{version_number:03d}"
        # Rename file to include version
        new_name = f"{item.name}{version_suffix}{item.extension}"
        dst = version_dir / new_name
        shutil.move(str(src), str(dst))

        src_thumb_path = src
        dst_thumb_path = dst

        rel_path = f"v{version_number:03d}/{new_name}"
        fmt = item.extension.lstrip(".")

    else:
        # Generic file/folder — copy everything
        src = Path(item.path)
        if src.is_dir():
            shutil.copytree(str(src), str(version_dir), dirs_exist_ok=True)
            shutil.rmtree(str(src))
            rel_path = f"v{version_number:03d}/"
            fmt = ""
        else:
            dst = version_dir / src.name
            shutil.move(str(src), str(dst))
            src_thumb_path = src
            dst_thumb_path = dst
            rel_path = f"v{version_number:03d}/{src.name}"
            fmt = src.suffix.lstrip(".")

    # Move thumbnail sidecar if present (best-effort, never fails the ingest)
    if src_thumb_path is not None and dst_thumb_path is not None:
        try:
            from . import thumbnails
            src_thumb = thumbnails.get_thumbnail_path(src_thumb_path)
            dst_thumb = thumbnails.get_thumbnail_path(dst_thumb_path)
            if src_thumb.exists():
                shutil.move(str(src_thumb), str(dst_thumb))
        except Exception:
            pass

    # Clean up empty source folder for sequences
    if item.item_type == "sequence":
        src_folder = Path(item.path)
        if src_folder.exists() and not any(src_folder.iterdir()):
            src_folder.rmdir()

    # Add version to output
    version = output.add_version(
        notes=notes,
        frames=list(item.frame_range) if item.frame_range else None,
        fmt=fmt,
        path=rel_path,
        creator=creator,
        set_live=True,
    )

    # Save metadata
    database.save_output(output, output_dir)

    return output, version
