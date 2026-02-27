# Shot Manager — TODO

## Overview

Tracks remaining features and improvements for the Shot Manager tool.
See `SHOT_MANAGER_ITERATION5_PLAN.md` for original design specs.

**Status:** See individual feature sections for current state.

---

## Completed Features (for reference)

✅ **Feature 1:** Frame Range Selection (In/Out, Full, Custom)
✅ **Feature 3:** Import Render to Nuke Script (Read nodes with LIVE tracking)
✅ **Feature 4:** Re-Render Last (with status tracking)
✅ **Feature 5:** _Incoming Pre-sorted Subfolders (Plates/CG/Reference)
✅ **Feature 6:** Move Incoming Items to Shot (Ingest UI with dialog)
✅ **Feature 7:** Project-Level Reference Directory
✅ **Feature 12:** Active Shot Indicator in Header (shows Nuke working context)
✅ **Move Output:** Move outputs between shots, to Reference, or back to _Incoming
✅ **Feature 15:** Resilient .versions.json — auto-repair on load infers name/shot/type from directory path, handles corrupt/empty JSON
✅ **Bug Fix:** LIVE Read Node Auto-Sync — `sync_all_live_readers()` added; `showEvent` in `ShotManagerWindow` calls it on panel show so nodes update when LIVE changes externally
✅ **Feature 8:** Missing Files Detection — `_check_files_exist()` in version_panel checks first/last frame for sequences (or the single file); missing files turn the version combo red and replace the Frames label with "⚠ FILES MISSING"
✅ **Feature 2:** Thumbnails — `.thumbnail.jpg` generated at render time (middle frame, 256px wide, native aspect ratio) via `thumbnails.py`; version panel loads cache or generates lazily in Nuke, shows text fallback in standalone

---

## Feature 2: Thumbnails for Versions ✅ COMPLETED

Implemented: `thumbnails.py` with `get_thumbnail_path()` and `generate_thumbnail()`.
Generation triggered at render time in `render.py` (middle frame, 256px wide, native aspect
ratio via Reformat `scale=256/width` expression). `_load_thumbnail()` in `version_panel.py`
loads cache → lazy Nuke generation → text fallback. Cached as `.thumbnail.jpg` in version dir.

---

## Feature 7: Project-Level Reference Directory ✅ COMPLETED

Implemented: `paths.get_project_reference_dir()`, Reference entry in shot_list,
`_on_reference_selected()` handler in main_window, and reference output scanning.

---

## Feature 8: Missing Files Detection ✅ COMPLETED

Implemented: `_check_files_exist(version)` in `ui/version_panel.py`. Resolves the full file path
using the same context logic as `_on_open_folder()` (handles _Incoming absolute paths, Reference,
and shot outputs). For sequences, checks first and last frame via `re.sub(r'#+', ...)` hash
expansion. Missing files turn the version combo text red and replace the Frames label with
"⚠ FILES MISSING". Stylesheet resets to normal when switching to an intact version.

---

## Feature 9: Loose Image Sequence Detection in _Incoming ✅ COMPLETED

Implemented: Added `_group_loose_sequences()` helper that groups loose image files by
`(base_name, extension)` using `_FRAME_PATTERN`. Groups with ≥2 frames become sequence
items; single frames and non-matching files remain as individual items.

**Changes made:**
- `incoming.py`: New `_group_loose_sequences(image_files, parent_dir)` function
- `incoming.py`: `_scan_directory()` collects loose image files, then groups via helper
- `incoming.py`: `scan_incoming()` root-level scan uses same grouping for unsorted files
- `incoming.py`: `_FRAME_PATTERN` relaxed from `\d{3,}` to `\d+` to support single-digit frame numbers

---

## Feature 10: Sequence/Still Toggle for Image Sequences ❌ NOT STARTED

**Priority:** Low (nice-to-have, advanced feature)

**Current State:**
- Version panel shows only metadata (created, creator, frames, format, notes)
- No way to view individual frame paths

**What's Needed:**

### Update: `ui/version_panel.py`
Add toggle UI (after line 100):
```python
# Toggle: Sequence mode (default) vs. File list mode
self._view_mode_toggle = QtWidgets.QCheckBox("Show individual frames")
self._view_mode_toggle.toggled.connect(self._on_view_mode_changed)
layout.addWidget(self._view_mode_toggle)

# Frame list widget (initially hidden)
self._frame_list = QtWidgets.QListWidget()
self._frame_list.setVisible(False)
layout.addWidget(self._frame_list)
```

Add handler:
```python
def _on_view_mode_changed(self, show_frames: bool):
    """Toggle between sequence mode and file list mode."""
    if show_frames and self._current_version.frames:
        # Generate frame list: resolve pattern + frame numbers
        # Populate self._frame_list with individual paths
        self._frame_list.setVisible(True)
    else:
        self._frame_list.setVisible(False)
```

**Dependencies:** None — independent UI enhancement

**Testing:**
1. Select sequence version → check toggle → frame list appears
2. List shows: `Name_v001.1001.exr`, `Name_v001.1002.exr`, ...
3. Uncheck toggle → frame list hides, shows summary view

---

## Feature 11: Fixed-Width Panels (prevent layout shift) ⚠️ PARTIALLY IMPLEMENTED

**Priority:** Low (polish, UX improvement)

**Current State:**
- Word wrap enabled on path label (`setWordWrap(True)` — line 82) ✅
- Text is selectable (`setTextInteractionFlags` — line 83)
- **Missing:** Size policy to prevent expansion
- **Missing:** Splitter stretch factor (only right panel should stretch)

**What's Needed:**

### Update: `ui/version_panel.py`
Modify path label setup (after line 83):
```python
self._path_label.setMinimumWidth(0)  # Allow shrinking
size_policy = QtWidgets.QSizePolicy(
    QtWidgets.QSizePolicy.Preferred,
    QtWidgets.QSizePolicy.Preferred
)
size_policy.setHorizontalStretch(0)  # Don't expand horizontally
self._path_label.setSizePolicy(size_policy)
```

Alternative approach (elision with tooltip):
```python
self._path_label.setWordWrap(False)  # Disable wrap
from PyQt5.QtCore import Qt
self._path_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
# Set elide mode: shows ".../" for long paths
# Full path shown on hover via tooltip (set in _on_version_changed)
```

### Update: `ui/main_window.py`
After splitter setup (line 92):
```python
self._splitter.setSizes([200, 200, 400])
# Only the version panel (index 2) should stretch
self._splitter.setStretchFactor(0, 0)  # Shot list: fixed
self._splitter.setStretchFactor(1, 0)  # Output list: fixed
self._splitter.setStretchFactor(2, 1)  # Version panel: stretch
```

**Dependencies:** None — independent UI fix

**Testing:**
1. Select output with very long path → layout doesn't shift
2. Resize window → only version panel (right) resizes
3. Shot list and output list maintain fixed width

---

## Feature 12: Active Shot Indicator in Header ✅ COMPLETED

Implemented: Shows current Nuke working context (auto-detected from script path)
in header bar. Updates on shot selection and _Incoming/Reference navigation.

---

## Feature 13: UI Button Reorganization in Version Panel ❌ NOT STARTED

**Priority:** Low (polish, UX improvement)

**Current State:**
- "Open Folder" and "Create LIVE Read" buttons are in separate rows
- Takes up vertical space and looks disconnected from action bar

**What's Needed:**

### Update: `ui/version_panel.py`
Reorganize buttons to be on same horizontal row:
```python
# Move "Open Folder" and "Create LIVE Read" buttons from their current location
# to the same row as the output action bar (similar to "Move to Shot" button layout)

# Create horizontal layout for action buttons
button_row = QtWidgets.QHBoxLayout()
button_row.addWidget(self._open_folder_btn)
button_row.addWidget(self._create_read_btn)
button_row.addStretch()
```

**Dependencies:** None — independent UI reorganization

**Testing:**
1. Check that buttons are on same horizontal row
2. Verify functionality unchanged (Open Folder and Create Read still work)
3. Confirm layout looks cleaner and more compact

---

## Feature 14: UI Button deactivation in Version Panel

**Priority:** Low (polish, UX improvement)

**Current State:**
- "Move to shot" button are always active

**What's Needed:**

### Update: `ui/main_window.py`
Deactivete the button if there is no file selected.
Like the "Move" button when you are in a shot or Reference

**Dependencies:** None — independent UI reorganization

**Testing:**
1. Check that buttons are deactivated when no files ar selected
2. Verify functionality by making sure that the button becomes active when a file is selected




---

## Feature 15: Resilient .versions.json Handling ✅ COMPLETED

Implemented: `_infer_metadata_from_path()` in `database.py` infers name/shot/type from
directory structure. `load_output()` now handles `JSONDecodeError`, compares loaded metadata
against expected values, and auto-repairs both in-memory and on disk if there's a mismatch.

---

## Implementation Priority & Dependencies

### High Priority (implement first)


### Medium Priority

### Low Priority (polish)
5. **Feature 10: Sequence/Still Toggle** — Advanced feature
6. **Feature 11: Fixed-Width Panels** — UI polish
7. **Feature 13: Button Reorganization** — Visual cleanup
8. **Feature 14: Button Deactivation** — UX consistency

### Dependencies
- **None** — All remaining features are independent
- Can be implemented in any order

### Recommended Implementation Order
1. **Feature 14** (Button Deactivation) — Quick UX fix
2. **Feature 13** (Button Reorganization) — Quick layout tweak
3. **Feature 11** (Fixed-Width Panels) — Simple UI tweak
4. **Feature 10** (Sequence/Still Toggle) — Lowest priority, advanced feature

---

## Testing Strategy

After implementing each feature:
1. **Manual testing:** Follow test cases in each feature section
2. **Integration testing:** Ensure feature doesn't break existing functionality
3. **Edge cases:**
   - Empty directories
   - Missing files / corrupt .versions.json
   - Manually renamed output folders
   - Single-frame "sequences"
   - Very long paths
   - Non-standard naming conventions

---

## Summary

**4 features remain:**
- 4 not yet started (Feature 10, 11, 13, 14)

**No blocking dependencies** — all features are independent and can be implemented in parallel or any order.
