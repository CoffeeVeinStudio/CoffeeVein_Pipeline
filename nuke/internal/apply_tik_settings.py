"""Apply TIK Manager metadata to Nuke project settings.

Reads metadata from the current TIK work's parent task and applies
fps, resolution, frame range (with handles) to the Nuke script.
"""

import nuke
import tik_manager4


def apply_tik_settings():
    """Read all TIK metadata and apply to Nuke project settings."""
    scene_path = nuke.root().knob("name").value()

    if not scene_path or scene_path == "Root":
        nuke.message("Save your script first, or open a TIK-managed work.")
        return

    tik = tik_manager4.initialize("Nuke")
    work, version = tik.project.find_work_by_absolute_path(scene_path)
    if not work:
        nuke.message(
            "Current script is not managed by TIK Manager.\n"
            "Save it as a TIK work first."
        )
        return

    task = tik.project.find_task_by_id(work.task_id)
    metadata = task.metadata

    applied = []

    # --- FPS ---
    fps = metadata.get_value("fps", fallback_value=None)
    if fps is not None:
        nuke.root()["fps"].setValue(float(fps))
        applied.append(f"FPS: {fps}")

    # --- Resolution ---
    resolution = metadata.get_value("resolution", fallback_value=None)
    if resolution and isinstance(resolution, (list, tuple)) and len(resolution) == 2:
        width, height = int(resolution[0]), int(resolution[1])
        format_name = f"TIK_{width}x{height}"

        existing = None
        for fmt in nuke.formats():
            if fmt.name() == format_name:
                existing = fmt
                break

        if not existing:
            nuke.addFormat(f"{width} {height} 1.0 {format_name}")

        nuke.root()["format"].setValue(format_name)
        applied.append(f"Resolution: {width}x{height}")

    # --- Frame Range with Handles ---
    start_frame = metadata.get_value("start_frame", fallback_value=None)
    end_frame = metadata.get_value("end_frame", fallback_value=None)
    pre_handle = metadata.get_value("pre_handle", fallback_value=0) or 0
    post_handle = metadata.get_value("post_handle", fallback_value=0) or 0

    if start_frame is not None and end_frame is not None:
        actual_start = int(start_frame) - int(pre_handle)
        actual_end = int(end_frame) + int(post_handle)

        nuke.root()["first_frame"].setValue(actual_start)
        nuke.root()["last_frame"].setValue(actual_end)
        nuke.root()["lock_range"].setValue(True)

        range_str = f"Range: {actual_start}-{actual_end}"
        if pre_handle or post_handle:
            range_str += f" (handles: -{pre_handle}/+{post_handle})"
        applied.append(range_str)

    # --- Summary ---
    if applied:
        summary = "TIK Settings Applied:\n\n" + "\n".join(applied)
        nuke.message(summary)
        print(f"[CoffeeVein] {summary}")
    else:
        nuke.message("No metadata values found in TIK task.")
