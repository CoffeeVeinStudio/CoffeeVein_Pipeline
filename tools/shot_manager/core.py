"""Core data classes for CoffeeVein Shot Manager.

Hierarchy:
    Project → Shot → Output → Version

An Output is a named stream of versioned files (e.g., "Denoise" render,
"GreenScreen" plate). Each Output has its own independent version counter
and LIVE tracking.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Output types — defines where in the shot folder outputs are stored
# ---------------------------------------------------------------------------

class OutputType:
    RENDER = "render"       # Comp/renders/{name}/
    PLATE = "plate"         # Plates/{name}/
    CG = "cg"              # CG/{name}/
    REFERENCE = "reference" # Reference/{name}/
    UNSORTED = "unsorted"   # _Incoming root (no subfolder)

    # Map type → relative folder inside the shot directory
    FOLDERS = {
        "render": "Comp/renders",
        "plate": "Plates",
        "cg": "CG",
        "reference": "Reference",
        "unsorted": "Unsorted",
    }

    @classmethod
    def folder_for(cls, output_type):
        """Return the relative folder path for a given output type."""
        return cls.FOLDERS.get(output_type, output_type)


# ---------------------------------------------------------------------------
# Version — a single published version of an output
# ---------------------------------------------------------------------------

@dataclass
class Version:
    """A single version of an output (render, plate, CG, etc.)."""
    version: int
    created: str  # ISO 8601 timestamp
    creator: str = "Admin"
    notes: str = ""
    frames: Optional[list] = None  # [first_frame, last_frame] or None for single files
    format: str = ""  # exr, tif, mov, etc.
    source_work: str = ""  # Which Nuke script version produced this render
    path: str = ""  # Relative path from the output folder, e.g. "v001/Denoise.####.exr"
    status: str = "complete"  # "complete", "rendering", "incomplete"

    def to_dict(self):
        """Serialize to dictionary for JSON storage."""
        data = {
            "version": self.version,
            "created": self.created,
            "creator": self.creator,
            "notes": self.notes,
            "format": self.format,
            "path": self.path,
            "status": self.status,
        }
        if self.frames is not None:
            data["frames"] = self.frames
        if self.source_work:
            data["source_work"] = self.source_work
        return data

    @classmethod
    def from_dict(cls, data):
        """Deserialize from dictionary."""
        return cls(
            version=data["version"],
            created=data["created"],
            creator=data.get("creator", ""),
            notes=data.get("notes", ""),
            frames=data.get("frames"),
            format=data.get("format", ""),
            source_work=data.get("source_work", ""),
            path=data.get("path", ""),
            status=data.get("status", "complete"),  # Default for backward compat
        )


# ---------------------------------------------------------------------------
# Output — a named stream of versions (e.g., "Denoise", "GreenScreen")
# ---------------------------------------------------------------------------

@dataclass
class Output:
    """A named output with independent versioning.

    Examples:
        - Render output "Denoise" with versions v001, v002, v003
        - Plate "GreenScreen" with versions v001 (original), v002 (redelivered)
    """
    name: str
    shot: str
    output_type: str  # OutputType constant
    versions: list = field(default_factory=list)  # List[Version]
    live_version: Optional[int] = None  # Version number that is LIVE

    @property
    def latest_version_number(self):
        """Return the highest version number, or 0 if no versions exist."""
        if not self.versions:
            return 0
        return max(v.version for v in self.versions)

    @property
    def next_version_number(self):
        """Return the next available version number."""
        return self.latest_version_number + 1

    @property
    def live(self):
        """Return the LIVE version object, or None."""
        if self.live_version is None:
            return None
        for v in self.versions:
            if v.version == self.live_version:
                return v
        return None

    def get_version(self, version_number):
        """Get a specific version by number."""
        for v in self.versions:
            if v.version == version_number:
                return v
        return None

    def add_version(self, notes="", frames=None, fmt="", source_work="",
                    path="", creator="Admin", status="complete", set_live=True):
        """Create and add a new version. Returns the new Version."""
        ver = Version(
            version=self.next_version_number,
            created=datetime.now().isoformat(timespec="seconds"),
            creator=creator,
            notes=notes,
            frames=frames,
            format=fmt,
            source_work=source_work,
            path=path,
            status=status,
        )
        self.versions.append(ver)
        if set_live:
            self.live_version = ver.version
        return ver

    def to_dict(self):
        """Serialize to dictionary for JSON storage."""
        return {
            "name": self.name,
            "shot": self.shot,
            "type": self.output_type,
            "versions": [v.to_dict() for v in self.versions],
            "live_version": self.live_version,
        }

    @classmethod
    def from_dict(cls, data):
        """Deserialize from dictionary."""
        return cls(
            name=data["name"],
            shot=data["shot"],
            output_type=data["type"],
            versions=[Version.from_dict(v) for v in data.get("versions", [])],
            live_version=data.get("live_version"),
        )


# ---------------------------------------------------------------------------
# Shot — a container for outputs
# ---------------------------------------------------------------------------

@dataclass
class Shot:
    """A shot in the project, containing multiple outputs."""
    name: str  # e.g., "A004_C020"
    path: str  # Absolute path to the shot directory
    outputs: list = field(default_factory=list)  # List[Output]

    def get_output(self, name, output_type=None):
        """Find an output by name (and optionally type)."""
        for output in self.outputs:
            if output.name == name:
                if output_type is None or output.output_type == output_type:
                    return output
        return None

    def get_outputs_by_type(self, output_type):
        """Return all outputs of a given type."""
        return [o for o in self.outputs if o.output_type == output_type]
