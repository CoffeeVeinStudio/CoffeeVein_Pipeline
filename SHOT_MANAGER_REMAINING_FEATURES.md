# Shot Manager — Remaining Features from Iteration 5

## Overview

This plan covers the **6 incomplete features** from SHOT_MANAGER_ITERATION5_PLAN.md:
- 3 features partially implemented (need completion)
- 3 features not yet started

**Status:** 6 of 12 features from Iteration 5 remain incomplete.

---

## Completed Features (for reference)

✅ **Feature 1:** Frame Range Selection (In/Out, Full, Custom)
✅ **Feature 3:** Import Render to Nuke Script (Read nodes with LIVE tracking)
✅ **Feature 4:** Re-Render Last (with status tracking)
✅ **Feature 5:** _Incoming Pre-sorted Subfolders (Plates/CG/Reference)
✅ **Feature 6:** Move Incoming Items to Shot (Ingest UI with dialog)

---

## Feature 2: Thumbnails for Versions ❌ NOT STARTED

**Priority:** Medium (nice-to-have, improves UX)

**Current State:**
- `_load_thumbnail()` in version_panel.py is a TODO stub (lines 261-266)
- Shows only text: `"No preview"` and version number
- No thumbnail generation, no caching

**What's Needed:**

### New file: `thumbnails.py`
```python
def get_thumbnail_path(version_dir: Path) -> Path:
    """Return path to .thumbnail.jpg in version directory."""
    return version_dir / ".thumbnail.jpg"

def generate_thumbnail(version_dir: Path, file_pattern: str, frame: int) -> Path:
    """Generate thumbnail from middle frame (Nuke-only).

    Creates temp node tree: Read → Reformat(256w) → Write(jpg, quality 85)
    Renders single frame, cleans up temp nodes.
    Returns path to saved .thumbnail.jpg
    """
    # Implementation details in original plan lines 51-57
```

### Update: `ui/version_panel.py`
- Modify `_load_thumbnail()` (lines 261-266):
  1. Call `thumbnails.get_thumbnail_path(version_dir)`
  2. If `.thumbnail.jpg` exists: load as QPixmap, scale to fit label
  3. If missing and in Nuke: call `thumbnails.generate_thumbnail()` on first view
  4. If missing and standalone: show "No preview available"

**Dependencies:** None — independent feature

**Testing:**
1. Select a version with existing frames → thumbnail auto-generates
2. Select version in standalone mode → shows cached thumbnail or "No preview"
3. Check `.thumbnail.jpg` file created in version directory

---

## Feature 7: Project-Level Reference Directory ⚠️ PARTIALLY IMPLEMENTED

**Priority:** High (architectural change, affects organization)

**Current State:**
- `OutputType.REFERENCE` exists in core.py (line 25)
- `_Incoming/Reference/` subfolder scanner works (incoming.py line 22-24)
- **Missing:** Project-level Reference endpoint (`get_project_reference_dir()` in paths.py)
- **Missing:** Reference entry in shot_list UI below _Incoming

**What's Needed:**

### Update: `paths.py`
Add new function:
```python
def get_project_reference_dir(project_root: Path) -> Path:
    """Return project-level Reference directory.

    Returns: {project_root}/Reference/

    This is a project-wide asset directory (not per-shot).
    """
    return Path(project_root) / "Reference"
```

### Update: `ui/shot_list.py`
- Add "Reference" entry below shots (similar to _Incoming)
- Style distinctly (e.g., different icon or color)
- New signal: `reference_selected(str)` emitting the Reference directory path
- When clicked, emit signal with `get_project_reference_dir(project_root)`

### Update: `ui/main_window.py`
- Connect `shot_list.reference_selected` signal to new handler `_on_reference_selected(ref_path)`
- Handler scans Reference directory for outputs (similar to _Incoming logic)
- Display in output panel with `OutputType.REFERENCE`
- Refresh reference count on project load (alongside _Incoming)

### Update: `incoming.py`
- When ingesting from `_Incoming/Reference/`:
  - Target should be `{project_root}/Reference/{name}/` (NOT `{shot_dir}/Reference/{name}/`)
  - Use `paths.get_project_reference_dir()` to determine target

**Dependencies:** None — independent architectural change

**Testing:**
1. Click "Reference" in shot list → shows project-level reference outputs
2. Ingest item from `_Incoming/Reference/` → files move to project Reference directory
3. Check file path: `{project_root}/Reference/{output_name}/v001/...`

---

## Feature 8: Missing Files Detection (red/strikethrough) ❌ NOT STARTED

**Priority:** Medium (safety feature, prevents confusion)

**Current State:**
- No file existence checks
- Deleted/moved files still show as normal in UI

**What's Needed:**

### Update: `ui/version_panel.py`
Modify `_on_version_changed()` (after line 246):
```python
# Check if files exist on disk
version_path = self._shot_dir / version.path if self._shot_dir else Path(version.path)

if version.frames:
    # Sequence: check first and last frame exist
    first_file = # resolve from pattern + first frame
    last_file = # resolve from pattern + last frame
    files_exist = first_file.exists() and last_file.exists()
else:
    # Single file/movie
    files_exist = version_path.exists()

if not files_exist:
    # Show warning
    self._version_combo.setStyleSheet("color: #ff6666;")  # Red text
    self._frames_label.setText("⚠️ FILES MISSING")
else:
    self._version_combo.setStyleSheet("")  # Reset
```

### Update: `ui/output_list.py` (optional enhancement)
- Check LIVE version file existence when displaying outputs
- If LIVE files missing: show red diamond (◆) instead of green (◆)

**Dependencies:** None — independent feature

**Testing:**
1. Delete a frame from a version → version shows red text, "FILES MISSING" warning
2. Restore file → warning clears
3. Check output list: outputs with missing LIVE files show red indicator

---

## Feature 9: Loose Image Sequence Detection in _Incoming ⚠️ PARTIALLY IMPLEMENTED

**Priority:** High (usability — loose sequences are common delivery format)

**Current State:**
- `_detect_sequence()` function exists (incoming.py lines 237-288)
- Works inside subdirectories via `_scan_directory()` (line 229)
- **Problem:** Root-level loose files NOT grouped
  - Files like `shot.1001.exr`, `shot.1002.exr` at `_Incoming/Plates/` root are each treated as separate items

**What's Needed:**

### Update: `incoming.py` — Root-level scan
Modify `scan_incoming()` (lines 116-161):

**Current logic (lines 123-146):**
```python
if entry.is_file():
    ext = entry.suffix.lower()
    if ext in _MOVIE_EXTS:
        # Create movie item
    elif ext in _SEQ_EXTS:
        # Create SINGLE file item (WRONG)
```

**New logic:**
```python
# After iterating all entries, group loose sequences:
loose_files = []  # Collect during iteration
for entry in sorted(incoming_dir.iterdir()):
    if entry.is_file() and entry.suffix.lower() in _SEQ_EXTS:
        loose_files.append(entry)

# Group by (base_name, extension) using _FRAME_PATTERN
sequences = defaultdict(list)
for f in loose_files:
    match = _FRAME_PATTERN.match(f.name)
    if match:
        base = match.group(1)
        ext = match.group(3)
        frame = int(match.group(2))
        sequences[(base, ext)].append((frame, str(f)))

# Create IncomingItem for each sequence (≥2 frames)
for (base_name, ext), frames in sequences.items():
    if len(frames) >= 2:
        # Create sequence item (similar to _detect_sequence() logic)
    else:
        # Single file, create file item
```

Same logic needed for unsorted root items (lines 137-161).

**Dependencies:** None — builds on existing `_detect_sequence()` pattern

**Testing:**
1. Place loose sequence at `_Incoming/Plates/`: `shot.1001.exr`, `shot.1002.exr`, `shot.1003.exr`
2. Scan _Incoming → shows as single sequence item (not 3 separate files)
3. Check frame range: `[1001-1003]`
4. Ingest → files moved and renamed with version suffix

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

## Feature 12: Active Shot Indicator in Header ❌ NOT STARTED

**Priority:** Medium (user orientation, clarity)

**Current State:**
- Header shows: `Project: SWAN  [Refresh]  [Set Project]`
- No indication of active shot

**What's Needed:**

### Update: `ui/main_window.py`
Add shot label to header (after line 67):
```python
# Project label
self._project_label = QtWidgets.QLabel("(no project)")
header_layout.addWidget(self._project_label)

header_layout.addSpacing(20)

# Shot label (NEW)
self._shot_label = QtWidgets.QLabel("Shot: (none)")
self._shot_label.setStyleSheet("color: #888888;")  # Gray when none selected
header_layout.addWidget(self._shot_label)

header_layout.addStretch()
```

Update handlers:
```python
def _on_shot_selected(self, shot_name, shot_dir):
    """Handle shot selection."""
    # ... existing code ...

    # Update shot indicator
    self._shot_label.setText(f"Shot: {shot_name}")
    self._shot_label.setStyleSheet("color: #47a3cb;")  # Active blue

def _on_incoming_selected(self, incoming_dir):
    """Handle _Incoming selection."""
    # ... existing code ...

    # Clear shot indicator
    self._shot_label.setText("_Incoming")
    self._shot_label.setStyleSheet("color: #888888;")  # Gray
```

Also update `_auto_select_nuke_shot()` to set shot label when auto-detecting from script path.

**Dependencies:** None — independent UI addition

**Testing:**
1. Select shot → header shows "Shot: A004_C020" in blue
2. Click _Incoming → header shows "_Incoming" in gray
3. Open Nuke script → shot auto-detected and displayed in header

---

## Implementation Priority & Dependencies

### High Priority (implement first)
1. **Feature 7: Project-Level Reference** — Architectural change, affects file organization
2. **Feature 9: Loose Sequence Detection** — Common workflow, high usability impact

### Medium Priority
3. **Feature 2: Thumbnails** — Nice-to-have, improves UX significantly
4. **Feature 8: Missing Files Detection** — Safety feature
5. **Feature 12: Active Shot Indicator** — User orientation

### Low Priority (polish)
6. **Feature 10: Sequence/Still Toggle** — Advanced feature
7. **Feature 11: Fixed-Width Panels** — UI polish

### Dependencies
- **None** — All remaining features are independent!
- No feature depends on another being implemented first
- Can be implemented in any order

### Recommended Implementation Order
1. **Feature 12** (Active Shot Indicator) — Quickest win, 1 file, ~20 lines
2. **Feature 9** (Loose Sequence Detection) — Builds on existing pattern, contained to incoming.py
3. **Feature 7** (Project-Level Reference) — Completes the pre-sorted subdirs architecture
4. **Feature 8** (Missing Files Detection) — Safety/defensive feature
5. **Feature 2** (Thumbnails) — More complex, new file + generation logic
6. **Feature 11** (Fixed-Width Panels) — Simple UI tweak
7. **Feature 10** (Sequence/Still Toggle) — Lowest priority, advanced feature

---

## Testing Strategy

After implementing each feature:
1. **Manual testing:** Follow test cases in each feature section
2. **Integration testing:** Ensure feature doesn't break existing functionality
3. **Edge cases:**
   - Empty directories
   - Missing files
   - Single-frame "sequences"
   - Very long paths
   - Non-standard naming conventions

---

## Summary

**6 features remain:**
- 3 partially implemented (need completion)
- 3 not yet started

**Total estimated effort:** 2-3 days
- High priority: 1 day
- Medium priority: 1 day
- Low priority: 0.5 days

**No blocking dependencies** — all features are independent and can be implemented in parallel or any order.
