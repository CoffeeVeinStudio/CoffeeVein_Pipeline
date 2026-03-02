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
✅ **Feature 13 (Plan):** Multi-Selection + Batch Move — `ExtendedSelection` enabled for all categories; `_on_move_output()` iterates `get_selected_outputs()`; move dialog handles multiple outputs
✅ **Feature 14 (Plan):** Relocate Buttons — "Open Folder" moved to header bar; "Create Read" + "Set LIVE" moved to bottom action bar; version panel is now purely informational
✅ **Feature 14:** Button Deactivation — "Move to Shot" button starts disabled when entering _Incoming view; enabled on item selection, matching "Move..." button behaviour in shot/Reference views
✅ **Feature 11:** Fixed-Width Panels — `QSizePolicy.Ignored` (horizontal) on `_path_label`, `_source_label`, and `_thumbnail_label` prevents `minimumSizeHint()` from propagating through the layout and forcing QSplitter to redistribute panels on content changes
✅ **Feature 10:** Sequence/Still Toggle — `QCheckBox("Show individual frames")` appears below Notes for sequences only; `_populate_frame_list()` resolves `####` hash patterns per-frame via `re.sub`; filenames shown in list, full path on tooltip; auto-refreshes when switching versions while open

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

## Feature 10: Sequence/Still Toggle for Image Sequences ✅ COMPLETED

Implemented: `QCheckBox("Show individual frames")` placed between Notes and thumbnail in
`ui/version_panel.py`. Only visible when `version.frames` is set (sequences, not stills).
`_populate_frame_list()` resolves `####` hash patterns for every frame via `re.sub(r'#+', ...)`.
Items show just the filename; full absolute path available as tooltip. Auto-refreshes
when switching versions while the toggle is checked.

---

## Feature 11: Fixed-Width Panels ✅ COMPLETED

Implemented: `setMinimumWidth(0)` added to `_path_label` in `version_panel.py` after
`setTextInteractionFlags`. Prevents `QLabel(wordWrap=True)` from inflating its minimum size hint
to full unbroken-text width, which would propagate through the layout and force the splitter to
redistribute panel widths on shot selection.

---

## Feature 12: Active Shot Indicator in Header ✅ COMPLETED

Implemented: Shows current Nuke working context (auto-detected from script path)
in header bar. Updates on shot selection and _Incoming/Reference navigation.

---

## Feature 14: UI Button Deactivation ✅ COMPLETED

Implemented: `_move_to_shot_btn.setEnabled(False)` added to `_on_incoming_selected()` so
the button starts disabled when entering `_Incoming` view. `_on_output_selected()` enables
it via `else` branch when `_viewing_incoming` is True, mirroring the `_move_output_btn`
pattern used in shot/Reference views.

---

## Feature 15: Resilient .versions.json Handling ✅ COMPLETED

Implemented: `_infer_metadata_from_path()` in `database.py` infers name/shot/type from
directory structure. `load_output()` now handles `JSONDecodeError`, compares loaded metadata
against expected values, and auto-repairs both in-memory and on disk if there's a mismatch.

---

## Feature 16: External Thumbnail Generation (oiiotool + ffmpeg) ❌ NOT STARTED

**Priority:** Medium

### Current State
`thumbnails.py` generates thumbnails via a temporary Nuke node graph (Read → Reformat →
Write). Generation only works inside Nuke; lazy-load in `version_panel.py` is gated by
`import nuke` and falls back to a text label in standalone mode.

### What's Needed

**`tools/shot_manager/thumbnails.py`** — replace `generate_thumbnail()` with subprocess calls:

- **Images / sequences** → `oiiotool {resolved_frame} --resize 256x0 -o {thumbnail}`
  - Resolve `####` hash pattern to actual frame number before calling oiiotool
- **Movies** → `ffmpeg -i {file} -frames:v 1 -vf scale=256:-1 -q:v 2 -y {thumbnail}`
  - Detect by extension: `.mov .mp4 .avi .mxf .mkv`
- Both paths: `subprocess.run(..., capture_output=True, timeout=30/60)`, return `None` on failure
- Remove all `nuke` imports from `thumbnails.py`

```python
import subprocess

_MOVIE_EXTS = {'.mov', '.mp4', '.avi', '.mxf', '.mkv'}

def generate_thumbnail(file_path: Path, frame: int) -> Optional[Path]:
    thumbnail_path = get_thumbnail_path(file_path)
    ext = file_path.suffix.lower()
    if ext in _MOVIE_EXTS:
        return _generate_from_movie(file_path, thumbnail_path)
    return _generate_from_image(file_path, frame, thumbnail_path)

def _generate_from_image(file_path, frame, thumbnail_path):
    if re.search(r'#+', str(file_path)):
        resolved = re.sub(r'#+', lambda m: str(frame).zfill(len(m.group())), file_path.name)
        input_file = file_path.parent / resolved
    else:
        input_file = file_path
    cmd = ['oiiotool', str(input_file).replace('\\', '/'),
           '--resize', '256x0', '-o', str(thumbnail_path).replace('\\', '/')]
    r = subprocess.run(cmd, capture_output=True, timeout=30)
    return thumbnail_path if r.returncode == 0 and thumbnail_path.exists() else None

def _generate_from_movie(file_path, thumbnail_path):
    cmd = ['ffmpeg', '-i', str(file_path).replace('\\', '/'),
           '-frames:v', '1', '-vf', 'scale=256:-1', '-q:v', '2', '-y',
           str(thumbnail_path).replace('\\', '/')]
    r = subprocess.run(cmd, capture_output=True, timeout=60)
    return thumbnail_path if r.returncode == 0 and thumbnail_path.exists() else None
```

**`tools/shot_manager/ui/version_panel.py`** — `_load_thumbnail()` lazy generation block (~lines 335–346):
- Remove `import nuke` guard; change `except ImportError` → `except Exception`

```python
# Before
try:
    import nuke  # noqa: F401
    frame = ((version.frames[0] + version.frames[1]) // 2 if version.frames else 1)
    result = thumbnails.generate_thumbnail(file_path, frame)
    if result and result.exists():
        self._set_thumbnail_pixmap(result)
        return
except ImportError:
    pass

# After
try:
    frame = ((version.frames[0] + version.frames[1]) // 2 if version.frames else 1)
    result = thumbnails.generate_thumbnail(file_path, frame)
    if result and result.exists():
        self._set_thumbnail_pixmap(result)
        return
except Exception:
    pass
```

### Dependencies
- `oiiotool` on system PATH (OpenImageIO — standard on VFX workstations)
- `ffmpeg` on system PATH

### Testing
1. EXR sequence: render → verify `.thumbnail.jpg` created in version dir
2. Still (JPG/PNG): add to _Incoming → thumbnail generated on version panel load
3. Movie (MOV/MP4): add to _Incoming → thumbnail generated
4. Standalone mode (no Nuke open): select a version → thumbnail appears without Nuke
5. Missing tool: remove oiiotool from PATH → graceful text fallback, no crash

---

## Feature 17: Project-Level Assets Directory ❌ NOT STARTED

**Priority:** Medium

### Current State
The shots panel has two project-level entries alongside the shot list: `_Incoming` and
`Reference`. There is no equivalent for shared project assets (characters, props,
environments, textures, etc.) that don't belong to a single shot.

### What's Needed

**`tools/shot_manager/paths.py`** — add path helper:
```python
def get_project_assets_dir(project_root):
    """Get the project-level Assets directory."""
    return Path(project_root) / "Assets"
```

**`tools/shot_manager/ui/main_window.py`** — mirror the Reference implementation (Feature 7):
- Add `Assets` entry to the shot list alongside `_Incoming` and `Reference`
- Add `_on_assets_selected()` handler (same pattern as `_on_reference_selected()`)
- Scan `Assets/` for outputs using the same output scanning logic as Reference

**`tools/shot_manager/core.py`** (if needed) — add `OutputType.ASSET` or reuse `OutputType.REFERENCE` depending on desired behavior for Read node creation and move targets.

### Dependencies
- Feature 7 (Reference directory) — already complete; Assets follows the same pattern

### Testing
1. Create `Assets/` at project root, add versioned output subdirs inside it
2. Verify "Assets" entry appears in shot list panel
3. Select Assets → output list populates correctly
4. Move an output to/from Assets using the Move dialog
5. Create a Read node from an Assets version

---

## Implementation Priority & Dependencies

### High Priority (implement first)

### Medium Priority
- **Feature 16** — External Thumbnail Generation (oiiotool + ffmpeg)
- **Feature 17** — Project-Level Assets Directory

### Low Priority (polish)
*(none remaining)*

### Dependencies
- **None** — All remaining features are independent
- Can be implemented in any order

### Recommended Implementation Order
1. Feature 16
2. Feature 17

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

**2 features remaining:** Feature 16 (External Thumbnail Generation), Feature 17 (Project-Level Assets Directory) — both medium priority.
