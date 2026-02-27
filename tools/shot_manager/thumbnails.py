"""Thumbnail generation and caching for CoffeeVein Shot Manager.

Generates JPEG thumbnails from render frames using Nuke's node graph.
Only the generation function requires Nuke — loading cached thumbnails
works in standalone mode.
"""

import re
from pathlib import Path
from typing import Optional


def get_thumbnail_path(version_dir: Path) -> Path:
    """Return the cached thumbnail path for a version directory."""
    return version_dir / ".thumbnail.jpg"


def generate_thumbnail(file_path: Path, frame: int) -> Optional[Path]:
    """Generate a thumbnail from a single frame using Nuke.

    Creates a temporary Read -> Reformat -> Write node chain, renders
    one frame scaled to 256px wide at native aspect ratio, then deletes
    all temp nodes. Returns the thumbnail path on success, None on failure.

    Args:
        file_path: Path to the file or sequence pattern (may contain ####).
        frame: Frame number to render.

    Returns:
        Path to .thumbnail.jpg on success, None on any failure.
    """
    import nuke

    # Resolve frame pattern (e.g., Denoise.####.exr -> Denoise.1001.exr)
    name = file_path.name
    resolved_name = re.sub(r'#+', lambda m: str(frame).zfill(len(m.group(0))), name)
    resolved_path = file_path.parent / resolved_name

    if not resolved_path.exists():
        print(f"[ShotManager] Thumbnail: frame file not found: {resolved_path}")
        return None

    thumbnail_path = get_thumbnail_path(file_path.parent)
    is_sequence = '#' in file_path.name
    read = reformat = write = None
    try:
        if is_sequence:
            # Pass the pattern path so Nuke resolves frame numbers correctly
            read = nuke.nodes.Read(
                file=str(file_path).replace('\\', '/'),
                first=frame,
                last=frame,
            )
            execute_frame = frame
        else:
            # Movie: let Nuke detect its internal frame range, read first frame
            read = nuke.nodes.Read(file=str(file_path).replace('\\', '/'))
            execute_frame = read.firstFrame()

        reformat = nuke.nodes.Reformat(inputs=[read], type='scale')
        reformat['scale'].setExpression('256/width')
        write = nuke.nodes.Write(
            inputs=[reformat],
            file=str(thumbnail_path).replace('\\', '/'),
            file_type='jpeg',
        )
        write['_jpeg_quality'].setValue(0.85)
        nuke.execute(write, execute_frame, execute_frame)
        if thumbnail_path.exists():
            print(f"[ShotManager] Thumbnail saved: {thumbnail_path}")
            return thumbnail_path
        print(f"[ShotManager] Thumbnail: execute succeeded but file not found: {thumbnail_path}")
        return None
    except Exception as e:
        print(f"[ShotManager] Thumbnail generation failed: {e}")
        return None
    finally:
        for node in (write, reformat, read):
            if node is not None:
                try:
                    nuke.delete(node)
                except Exception:
                    pass
