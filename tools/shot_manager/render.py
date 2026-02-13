"""Nuke render module for CoffeeVein Shot Manager.

Handles rendering Write nodes with per-node independent versioning.
Only imported when running inside Nuke — standalone mode skips this module.
"""

import os
import time
from pathlib import Path
from datetime import datetime

from .core import Output, OutputType
from . import database, paths


class RenderCancelled(Exception):
    """Raised when user cancels a render."""
    pass


class RenderJob:
    """A single render job for one Write node.

    Manages the render lifecycle: setup output path, render frames,
    track progress, handle cancellation, save version metadata.
    """

    def __init__(self, write_node, project_root, shot_name, shot_dir,
                 start_frame=None, end_frame=None, notes="",
                 source_work="", creator="Admin"):
        self.write_node = write_node
        self.node_name = write_node.name()
        self.project_root = project_root
        self.shot_name = shot_name
        self.shot_dir = shot_dir
        self.start_frame = start_frame
        self.end_frame = end_frame
        self.notes = notes
        self.source_work = source_work
        self.creator = creator

        self._cancel_requested = False
        self._progress_callback = None  # fn(message: str, progress: float)
        self._frames_rendered = 0
        self._total_frames = 0
        self._is_overwrite = False  # Set to True by prepare_overwrite()

        # Resolved paths (set during prepare())
        self.output_dir = None  # .../Comp/renders/Denoise/
        self.version_dir = None  # .../Comp/renders/Denoise/v001/
        self.version_number = 0
        self.output_file_pattern = ""  # .../v001/Denoise.####.exr

    def set_progress_callback(self, callback):
        """Set callback: fn(message: str, progress: float 0-1)."""
        self._progress_callback = callback

    def request_cancel(self):
        """Request cancellation of this render."""
        self._cancel_requested = True

    def prepare(self):
        """Resolve output paths and create version directory.

        Must be called before render(). Sets up:
        - output_dir, version_dir, version_number
        - Creates the version folder on disk
        - Loads/creates the Output metadata
        """
        import nuke

        # Resolve frame range
        if self.start_frame is None:
            self.start_frame = int(nuke.root()["first_frame"].value())
        if self.end_frame is None:
            self.end_frame = int(nuke.root()["last_frame"].value())

        self.output_dir = paths.get_output_dir(
            self.shot_dir, OutputType.RENDER, self.node_name
        )

        # Load existing output or create new
        output = database.load_output(self.output_dir)
        if output is None:
            output = Output(
                name=self.node_name,
                shot=self.shot_name,
                output_type=OutputType.RENDER,
            )

        self.version_number = output.next_version_number
        self.version_dir = paths.get_version_dir(
            self.shot_dir, OutputType.RENDER, self.node_name, self.version_number
        )
        self.version_dir.mkdir(parents=True, exist_ok=True)

        # Determine file format from node settings
        file_type = self.write_node["file_type"].value()
        if not file_type:
            # Try to infer from the existing file knob path
            existing_file = self.write_node["file"].value()
            if existing_file:
                ext = Path(existing_file).suffix.lstrip(".")
                if ext:
                    file_type = ext
            if not file_type:
                file_type = "exr"

        # Build output file pattern (include version number in filename)
        version_suffix = f"_v{self.version_number:03d}"
        if file_type.lower() in ("mov", "mov64", "mp4", "avi"):
            self.output_file_pattern = str(
                self.version_dir / f"{self.node_name}{version_suffix}.{file_type}"
            )
            rel_pattern = f"{self.node_name}{version_suffix}.{file_type}"
        else:
            self.output_file_pattern = str(
                self.version_dir / f"{self.node_name}{version_suffix}.####.{file_type}"
            )
            rel_pattern = f"{self.node_name}{version_suffix}.####.{file_type}"

        self._file_type = file_type
        self._output = output
        self._total_frames = self.end_frame - self.start_frame + 1

        # REGISTER VERSION IMMEDIATELY (before render starts)
        # This ensures incomplete renders are tracked in .versions.json
        version = output.add_version(
            notes=self.notes,
            frames=[self.start_frame, self.end_frame],
            fmt=file_type,
            source_work=self.source_work,
            path=f"v{self.version_number:03d}/{rel_pattern}",
            creator=self.creator,
            status="rendering",  # Mark as in-progress
            set_live=False,  # Don't set LIVE until render completes
        )
        database.save_output(output, self.output_dir)

        # Store reference to the version object for later updates
        self._version = version

        # Verify the version directory was created
        if not self.version_dir.exists():
            raise RuntimeError(
                f"Failed to create output directory: {self.version_dir}"
            )

        print(f"[ShotManager] {self.node_name}: rendering to {self.output_file_pattern}")
        print(f"[ShotManager] Frames: {self.start_frame}-{self.end_frame} ({self._total_frames} frames)")

    def prepare_overwrite(self, version_number, existing_output):
        """Prepare to re-render an existing version (overwrite mode).

        Unlike prepare(), this does NOT create a new version or increment counter.
        Instead, it targets an existing version directory for overwriting.

        Args:
            version_number: The existing version number to overwrite.
            existing_output: The loaded Output object containing this version.
        """
        import nuke

        # Resolve frame range
        if self.start_frame is None:
            self.start_frame = int(nuke.root()["first_frame"].value())
        if self.end_frame is None:
            self.end_frame = int(nuke.root()["last_frame"].value())

        self.output_dir = paths.get_output_dir(
            self.shot_dir, OutputType.RENDER, self.node_name
        )

        self.version_number = version_number
        self.version_dir = paths.get_version_dir(
            self.shot_dir, OutputType.RENDER, self.node_name, self.version_number
        )

        if not self.version_dir.exists():
            raise RuntimeError(f"Version directory does not exist: {self.version_dir}")

        # Determine file format
        file_type = self.write_node["file_type"].value()
        if not file_type:
            existing_file = self.write_node["file"].value()
            if existing_file:
                ext = Path(existing_file).suffix.lstrip(".")
                if ext:
                    file_type = ext
            if not file_type:
                file_type = "exr"

        # Build output file pattern (same as prepare())
        version_suffix = f"_v{self.version_number:03d}"
        if file_type.lower() in ("mov", "mov64", "mp4", "avi"):
            self.output_file_pattern = str(
                self.version_dir / f"{self.node_name}{version_suffix}.{file_type}"
            )
        else:
            self.output_file_pattern = str(
                self.version_dir / f"{self.node_name}{version_suffix}.####.{file_type}"
            )

        self._file_type = file_type
        self._output = existing_output
        self._total_frames = self.end_frame - self.start_frame + 1
        self._is_overwrite = True  # Flag to indicate overwrite mode

        print(f"[ShotManager] {self.node_name}: re-rendering v{self.version_number:03d}")
        print(f"[ShotManager] Frames: {self.start_frame}-{self.end_frame} ({self._total_frames} frames)")

    def render(self):
        """Execute the render. Call prepare() first.

        Returns:
            Version object for the completed render.

        Raises:
            RenderCancelled: If the user cancels.
            RuntimeError: If render fails.
        """
        import nuke

        self._cancel_requested = False
        self._frames_rendered = 0

        # Save original node settings
        original_file = self.write_node["file"].value()
        original_file_type = self.write_node["file_type"].value()

        try:
            # Set output path on the Write node (Nuke requires forward slashes)
            self.write_node["file"].setValue(
                self.output_file_pattern.replace("\\", "/")
            )

            is_movie = self._file_type.lower() in ("mov", "mov64", "mp4", "avi")

            if is_movie:
                self._render_movie()
            else:
                self._render_sequence()

        finally:
            # Always restore original node settings
            self.write_node["file"].setValue(original_file)
            self.write_node["file_type"].setValue(original_file_type)

        # Update version status to complete
        if self._is_overwrite:
            # Update existing version metadata
            existing_version = self._output.get_version(self.version_number)
            if existing_version:
                existing_version.notes = self.notes
                existing_version.frames = [self.start_frame, self.end_frame]
                existing_version.source_work = self.source_work
                existing_version.status = "complete"
                existing_version.created = datetime.now().isoformat(timespec="seconds")
                version = existing_version
        else:
            # Normal render: version was pre-registered in prepare(), just update status
            self._version.status = "complete"
            self._output.live_version = self._version.version  # Set LIVE on success
            version = self._version

        database.save_output(self._output, self.output_dir)

        # Update LIVE directory
        self._update_live()

        return version

    def _render_movie(self):
        """Render movie format (entire range at once)."""
        import nuke

        if self._cancel_requested:
            raise RenderCancelled("Cancelled before starting")

        self._report_progress(
            f"Rendering {self.node_name} (movie)\n"
            f"{self._total_frames} frames — Press ESC to cancel",
            0.0
        )

        try:
            nuke.execute(self.write_node, self.start_frame, self.end_frame)
        except RuntimeError as e:
            msg = str(e).lower()
            if "cancelled" in msg or "aborted" in msg or "user" in msg:
                # Clean up partial movie
                if os.path.exists(self.output_file_pattern):
                    try:
                        os.remove(self.output_file_pattern)
                    except OSError:
                        pass
                raise RenderCancelled("Cancelled by user")
            raise RuntimeError(
                f"{self.node_name}: {e}\n"
                f"Output path: {self.output_file_pattern}"
            )

        self._report_progress(f"Rendered {self.node_name} — Complete!", 1.0)

    def _render_sequence(self):
        """Render image sequence frame-by-frame with progress."""
        import nuke
        from .qt_compat import QtWidgets

        task = nuke.ProgressTask(f"Rendering {self.node_name}")
        task.setMessage("Starting render...")
        task.setProgress(0)

        start_time = time.time()

        try:
            for frame in range(self.start_frame, self.end_frame + 1):
                if task.isCancelled() or self._cancel_requested:
                    raise RenderCancelled(f"Cancelled at frame {frame}")

                frame_start = time.time()
                nuke.execute(self.write_node, frame, frame)
                frame_time = time.time() - frame_start

                self._frames_rendered += 1
                progress = self._frames_rendered / self._total_frames

                # Time estimation
                elapsed = time.time() - start_time
                avg_per_frame = elapsed / self._frames_rendered
                remaining = avg_per_frame * (self._total_frames - self._frames_rendered)

                time_str = _format_time(remaining)
                msg = (
                    f"Frame {frame}/{self.end_frame} ({int(progress * 100)}%) — "
                    f"{time_str} remaining — {frame_time:.1f}s/frame"
                )

                task.setProgress(int(progress * 100))
                task.setMessage(msg)
                self._report_progress(f"Rendering {self.node_name}\n{msg}", progress)

                # Keep Qt responsive
                QtWidgets.QApplication.processEvents()

        finally:
            del task

        total_time = time.time() - start_time
        self._report_progress(
            f"Rendered {self.node_name} — {_format_time(total_time)} total",
            1.0
        )

    def _update_live(self):
        """Update the LIVE directory to point to the latest version.

        On Windows, uses a junction (directory link) which doesn't require
        admin privileges. Falls back to a marker file if junction fails.
        """
        live_dir = paths.get_live_dir(
            self.shot_dir, OutputType.RENDER, self.node_name
        )

        # Remove existing LIVE
        if live_dir.exists():
            if live_dir.is_symlink() or _is_junction(live_dir):
                # Remove symlink/junction
                live_dir.rmdir()
            elif live_dir.is_dir():
                # Remove regular directory (shouldn't happen, but safe)
                import shutil
                shutil.rmtree(live_dir)

        # Create junction (Windows) or symlink (Unix) to version dir
        try:
            if os.name == "nt":
                # Use junction on Windows (no admin required)
                import subprocess
                subprocess.run(
                    ["cmd", "/c", "mklink", "/J",
                     str(live_dir), str(self.version_dir)],
                    check=True, capture_output=True
                )
            else:
                live_dir.symlink_to(self.version_dir)
        except (OSError, subprocess.CalledProcessError):
            # Fallback: write a LIVE.txt pointer file
            pointer = live_dir.parent / "LIVE.txt"
            pointer.write_text(str(self.version_dir), encoding="utf-8")

    def _report_progress(self, message, progress):
        """Report progress to callback if set."""
        if self._progress_callback:
            self._progress_callback(message, progress)


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _format_time(seconds):
    """Format seconds into human-readable string."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}h {minutes}m {secs}s"
    elif minutes > 0:
        return f"{minutes}m {secs}s"
    return f"{secs}s"


def _is_junction(path):
    """Check if a path is a Windows junction point."""
    if os.name != "nt":
        return False
    try:
        import ctypes
        attrs = ctypes.windll.kernel32.GetFileAttributesW(str(path))
        FILE_ATTRIBUTE_REPARSE_POINT = 0x400
        return bool(attrs & FILE_ATTRIBUTE_REPARSE_POINT)
    except (OSError, AttributeError):
        return False


def discover_write_nodes():
    """Discover all Write nodes in the current Nuke script.

    Returns:
        List of nuke.Node objects (Write nodes), sorted by name.
    """
    import nuke
    nodes = [n for n in nuke.allNodes() if n.Class() == "Write"]
    return sorted(nodes, key=lambda n: n.name())


def get_selected_write_nodes():
    """Get currently selected Write nodes.

    Returns:
        List of selected Write nodes, or all Write nodes if none selected.
    """
    import nuke
    selected = nuke.selectedNodes()
    if selected:
        write_nodes = [n for n in selected if n.Class() == "Write"]
        if write_nodes:
            return sorted(write_nodes, key=lambda n: n.name())

    # Nothing selected or no Write nodes in selection — return all
    return discover_write_nodes()


def get_current_nuke_context():
    """Get the current Nuke script's TIK context (project root, shot name).

    Tries to determine the shot from the script's file path.

    Returns:
        Tuple of (project_root: Path, shot_name: str, shot_dir: Path) or
        (None, None, None) if not determinable.
    """
    import nuke

    script_path = nuke.root().name()
    if not script_path or script_path == "Root":
        return None, None, None

    script_path = Path(script_path).absolute()

    # Walk up the path looking for the project root
    project_root = paths.find_project_root(script_path.parent)
    if project_root is None:
        return None, None, None

    # Determine shot name from path
    # Expected structure: .../Shots/{shot_name}/...
    shots_dir = paths.get_shots_dir(project_root)
    if shots_dir is None:
        return None, None, None

    # Find which shot directory the script is under
    try:
        rel = script_path.relative_to(shots_dir)
        shot_name = rel.parts[0]  # First component after Shots/
        shot_dir = shots_dir / shot_name
        return project_root, shot_name, shot_dir
    except (ValueError, IndexError):
        return None, None, None
