# Shot Manager — Iteration 5 Plan

## Overview

Seven feature areas based on user testing feedback.

---

## 1. Frame Range Selection

**Current:** Always renders full timeline range (`nuke.root().firstFrame()` to `lastFrame()`).

**New:** Three modes — In/Out Point, Full Range, Custom.

### UI (in Nuke controls bar)
```
Frame range: (●) In/Out  ( ) Full  ( ) Custom    [1010] — [1045]   [↻]
[Render Selected Write Node]                      [Re-Render Last]
```

- **In/Out** (default) — reads viewer in/out: `nuke.activeViewer().node().knob('frame_range').getValue()` → parses `"10-55"` string
- **Full Range** — `nuke.root().firstFrame()` / `nuke.root().lastFrame()`
- **Custom** — user edits spinboxes directly
- **↻ button** — re-reads from Nuke (useful if user changed timeline after opening Shot Manager)

### Implementation

**File: `ui/main_window.py`**
- Add `_build_frame_range_controls(parent_layout)` — 3 radio buttons + 2 spinboxes + reset button
- `_get_frame_range() -> (start, end)` — reads from spinboxes (which are populated based on selected mode)
- `_on_frame_mode_changed()` — auto-populate spinboxes from Nuke based on selected radio
- `_on_reset_range()` — re-read from Nuke
- Pass `start_frame` and `end_frame` to `RenderJob.__init__()` (already supported)

---

## 2. Thumbnails for Versions

**Current:** `_load_thumbnail()` in version_panel.py is a TODO stub showing text.

**New:** Show thumbnail from the middle frame of a render/plate/CG sequence.

### Approach
- When a version is selected, look for `.thumbnail.jpg` in the version directory
- If not found and in Nuke: auto-generate using a temp Read→Reformat→Write node chain
- Standalone: show cached thumbnails only, "No preview" if missing
- Thumbnail size: 256px wide, aspect-preserved

### Implementation

**New file: `thumbnails.py`**
- `get_thumbnail_path(version_dir) -> Path` — returns `.thumbnail.jpg` path
- `generate_thumbnail(version_dir, file_pattern, frame) -> Path` (Nuke-only)
  - Creates temp node tree: Read → Reformat(256w) → Write(jpg, quality 85)
  - Renders single frame (middle of range)
  - Cleans up temp nodes
  - Returns path to saved `.thumbnail.jpg`

**File: `ui/version_panel.py`**
- `_load_thumbnail()`: check for `.thumbnail.jpg`, load as QPixmap scaled to fit label
- If missing and in Nuke: generate on first view

---

## 3. Import Render to Nuke Script (Read Nodes)

**Current:** No import functionality.

**New:** Create Read nodes from the version panel, with a special "LIVE Read" that auto-tracks.

### Two import modes

#### A. Create Read (specific version)
- Creates a Read node with static path: `Z:/PROJECTS/SWAN/Shots/.../v001/Name.####.exr`
- Frame range set from version metadata
- Forward slashes (as per our Nuke lesson)

#### B. Create LIVE Read (expression-based)
- Creates a Read node with a **Python expression** in the file knob
- Expression reads the live version path from `.versions.json`:
  ```python
  [python {
  import json
  d = json.load(open("Z:/PROJECTS/SWAN/Shots/A004_C020/Comp/renders/Denoise/.versions.json"))
  v = next(v for v in d["versions"] if v["version"] == d["live_version"])
  "Z:/PROJECTS/SWAN/Shots/A004_C020/Comp/renders/Denoise/" + v["path"]
  }]
  ```
- When LIVE version changes → Shot Manager updates Read node's `first_frame`, `last_frame`, and `origfirst`/`origlast` knobs to match the new LIVE version's frame range
- The file expression automatically resolves to the new version's path (re-evaluated by Nuke)

#### C. Update Existing Read
- Shows dialog listing all Read nodes in the script
- User picks one → its file path and frame range are updated to the selected version

### UI (in version panel)
```
[Open Folder]   [Create Read ▾]   [Set LIVE]
```
"Create Read" is a QToolButton with dropdown menu:
- **Create Read (v001)** — static path
- **Create LIVE Read** — expression-based (only if output has LIVE version)
- **Update Existing Read...** — pick from dialog

### Implementation

**New file: `nuke_read.py`**
- `create_read_node(file_path, first_frame, last_frame, name=None) -> nuke.Node`
  - Forward-slash path
  - Sets `first`, `last`, `origfirst`, `origlast`, `colorspace`
- `create_live_read_node(output_dir, output, name=None) -> nuke.Node`
  - Sets file knob expression that reads from `.versions.json`
  - Sets frame range from current LIVE version
  - Adds `shot_manager_live` knob (hidden Tab) storing `output_dir` for later updates
- `update_live_readers(output_dir, output)`
  - Scans all Read nodes for `shot_manager_live` knob matching `output_dir`
  - Updates their `first`/`last`/`origfirst`/`origlast` from new LIVE version
- `find_read_nodes() -> list[dict]` — returns all Read nodes with name + current file path
- `update_read_node(node, file_path, first_frame, last_frame)`

**File: `ui/version_panel.py`**
- Replace "Open Folder" area with button row including Create Read dropdown (Nuke-only)
- Import signals or call `nuke_read` directly

**File: `ui/main_window.py`**
- In `_on_live_changed()`: after updating .versions.json, call `nuke_read.update_live_readers()` to refresh LIVE Read nodes

---

## 4. Remove Cancel, Replace "Render All" with "Re-Render Last"

**Current bottom bar:**
```
[Render Selected Write Node]  [Render All Write Nodes]  [Cancel]
```

**New bottom bar:**
```
Frame range: (●) In/Out  ( ) Full  ( ) Custom    [1010] — [1045]  [↻]
[Render Selected Write Node]                      [Re-Render Last]
```

### Version registration: upfront, before render starts

Currently, version is only registered in `.versions.json` AFTER render completes. This means cancelled renders leave orphan directories on disk with no metadata.

**New behavior:**
1. `RenderJob.prepare()` registers the version in `.versions.json` immediately with `status: "rendering"`
2. `RenderJob.render()` on success: updates status to `"complete"` in `.versions.json`
3. On cancel/error: version stays in `.versions.json` with `status: "incomplete"`
4. Incomplete versions are visible in the UI (marked with warning indicator)

### "Re-Render Last" behavior
1. Finds the latest version for the Write node (from `.versions.json`, includes incomplete)
2. If latest version is incomplete → re-renders into that same directory
3. If latest version is complete → still re-renders into it (overwrite use case)
4. Confirmation dialog: "Re-render {node_name} v{X}? This will overwrite existing frames."
5. On success: updates version status to `"complete"`, updates frame range / notes

### Implementation

**File: `core.py`**
- Add `status: str = "complete"` field to `Version` dataclass
- Include in `to_dict()` / `from_dict()`

**File: `render.py`**
- `prepare()`: save version to `.versions.json` with `status="rendering"` BEFORE render starts
- `render()`: on success, update status to `"complete"`
- New `prepare_overwrite(version_number)`: like `prepare()` but targets existing version directory, no version increment
- On cancel: the version stays as `"incomplete"` (set by a new `finalize(status)` method)

**File: `ui/main_window.py`**
- Remove `_render_all_btn` and `_cancel_btn`
- Add `_rerender_btn` ("Re-Render Last")
- `_on_rerender_last()`: find latest version, confirm with user, render with overwrite flag

---

## 5. _Incoming Pre-sorted Subfolders

**Current:** `_Incoming/` scanned recursively, type guessed from extension.

**New:** Three fixed subdirectories, each mapping to an OutputType:

```
_Incoming/
  Plates/       → OutputType.PLATE
  CG/           → OutputType.CG
  Reference/    → OutputType.REFERENCE
```

- Scanner reads each subfolder separately and tags items with the correct type
- Loose files in `_Incoming/` root are shown as "Unsorted" with a warning
- `create_incoming_dirs(project_root)` creates the three subdirs if missing

### Implementation

**File: `incoming.py`**
- `INCOMING_SUBDIRS = {"Plates": OutputType.PLATE, "CG": OutputType.CG, "Reference": OutputType.REFERENCE}`
- `scan_incoming()` → iterate over each subdir, tag items with `suggested_type`
- Also scan root for loose items → `suggested_type = None` (unsorted)
- `create_incoming_dirs(project_root)` — create subdirs if missing
- Remove extension-based type guessing

**File: `ui/main_window.py`**
- `_on_incoming_selected()`: group items by subfolder type

---

## 6. Move Incoming Items to Shot (Ingest UI)

**Current:** `ingest_item()` exists in incoming.py but no UI triggers it.

**New:** "Move to Shot" button + dialog when viewing _Incoming.

### UI Flow
1. Select _Incoming → output panel shows items grouped by type
2. Select one or more items
3. Click "Move to Shot"
4. Dialog:
   - **Target shot**: combo box (auto-suggests active Nuke shot first, then falls back to name-matching from item name, then all shots)
   - **Output name**: text field (defaults to item name)
   - **Type**: read-only, from subfolder (Plate/CG/Reference)
   - **Notes**: text field
5. Files moved, .versions.json created, UI refreshes

### Implementation

**File: `ui/output_list.py`**
- `set_selection_mode(multi=True/False)` — toggle multi-selection for _Incoming view
- `get_selected_outputs() -> list`

**File: `ui/main_window.py`**
- Show "Move to Shot" button when _Incoming is selected (hidden otherwise)
- `_on_move_to_shot()` — get selected items, show dialog, call `ingest_item()`, refresh

**New file: `ui/ingest_dialog.py`**
- `IngestDialog(shots, suggested_shot, items, parent)`
  - Shot combo (pre-selected to suggested shot)
  - Output name field (editable, defaults to item name)
  - Type label (read-only)
  - Notes field
  - OK / Cancel

---

## 7. Project-Level Reference Directory

**Current:** Reference is defined as a per-shot output type (`{shot_dir}/Reference/`).

**Correction:** Reference is project-level at `{project_root}/Reference/`, same level as `_Incoming/`.

### Changes needed

**File: `paths.py`**
- Add `get_project_reference_dir(project_root) -> Path` → `{project_root}/Reference/`

**File: `ui/shot_list.py`**
- Add a "Reference" entry below shots (like _Incoming), styled distinctly
- New signal: `reference_selected(str)` emitting the Reference directory path

**File: `ui/main_window.py`**
- `_on_reference_selected(ref_path)`: scan Reference directory for outputs, display in output panel
- Reference outputs use `OutputType.REFERENCE` and follow same versioning as shot outputs
- Refresh reference count alongside _Incoming on project load

**File: `incoming.py`**
- When ingesting a Reference item from `_Incoming/Reference/`, target is `{project_root}/Reference/{name}/` not `{shot_dir}/Reference/{name}/`

---

## 8. Missing Files Detection (red/strikethrough)

**Current:** If files are manually moved or deleted from the shot directory, the UI still shows them as normal.

**New:** When displaying versions, check if the files actually exist on disk. If missing, show the version with a visual warning (red text, strikethrough, or warning icon).

### Implementation

**File: `ui/version_panel.py`**
- In `_on_version_changed()`: resolve the version's absolute path and check if files exist
- If missing: show a warning indicator (red text on the version combo entry, "Missing files" label)
- Consider checking on output selection too (mark outputs with missing LIVE files)

**File: `ui/output_list.py`**
- Optionally mark outputs where the LIVE version's files are missing (red diamond instead of normal diamond)

---

## 9. Loose Image Sequence Detection in _Incoming

**Current:** Image sequences are only detected when files are inside a subdirectory (via `_detect_sequence(folder)`). Loose numbered files directly in `_Incoming/Plates/` (e.g., `shot.1001.exr`, `shot.1002.exr`, ...) are each treated as individual `item_type="file"` items. This applies to ALL image formats, not just EXR.

**New:** Detect and group image sequences even when files are loose (not in their own folder).

### Implementation

**File: `incoming.py`**
- In `_scan_directory()`: after the per-file loop, collect all files that matched `_FRAME_PATTERN` and group by `(base_name, extension)`. If a group has ≥2 frames → create a single `IncomingItem` with `item_type="sequence"`. Remaining non-matching files stay as individual items.
- Same logic in the root-level scan in `scan_incoming()` for loose unsorted files.
- This must work for ALL `_SEQ_EXTS` formats (not just `.exr`) — the `_FRAME_PATTERN` regex already matches any extension.

---

## 10. Sequence/Still Toggle for Image Sequences

**Current:** No way to switch between viewing a sequence as a sequence vs. individual frames.

**New:** Add a toggle in the version panel or output list to switch between "sequence mode" (shows `name.####.exr [1001-1045]`) and "file list mode" (shows each frame individually).

### Implementation

**File: `ui/version_panel.py`**
- Add a toggle button/checkbox: "Sequence" / "Files"
- When in file list mode, show a scrollable list of individual frame paths
- Default to sequence mode

---

## 11. Fixed-Width Panels (prevent layout shift)

**Current:** The splitter panels change width when selecting different clips, likely because the Path label in the version panel expands with long paths.

**New:** Prevent the version panel's path display from pushing the layout wider.

### Implementation

**File: `ui/version_panel.py`**
- Set `self._path_label.setWordWrap(True)` (already done) and add `self._path_label.setMinimumWidth(0)` + a `QSizePolicy` that prevents expansion
- Alternatively, set `self._path_label.setTextInteractionFlags(...)` with elision (show `...` for long paths, full path on hover tooltip)

**File: `ui/main_window.py`**
- After `self._splitter.setSizes([200, 200, 400])`, call `self._splitter.setStretchFactor(2, 1)` so only the right panel stretches — or lock minimum sizes

---

## 12. Active Shot Indicator in Header

**Current:** Header shows only `Project: SWAN  [Refresh]  [Set Project]`. No indication of which shot the user is working on.

**New:** Show the active shot name in the header bar:
```
Project: SWAN    Shot: A001_C020              [Refresh]  [Set Project]
```

### Implementation

**File: `ui/main_window.py`**
- Add `self._shot_label = QLabel("Shot: (none)")` to the header layout, after the project label
- Update `_on_shot_selected()` and `_auto_select_nuke_shot()` to set `self._shot_label.setText(f"Shot: {shot_name}")`
- When viewing _Incoming, set to "Shot: (none)" or "_Incoming"

---

## 13. Multi-Selection for Shot/Reference Outputs + Batch Move

**Current:** Multi-selection (`ExtendedSelection`) is only enabled when viewing `_Incoming`. Shot and Reference outputs use `SingleSelection`. The "Move..." button operates on a single `self._current_output`.

**New:** Enable multi-selection in all categories (shots, Reference, _Incoming). Allow batch-moving multiple selected outputs to another shot, Reference, or _Incoming.

### UI Changes

**Bottom bar when viewing shots/Reference:**
```
[Move...]          [Create Read ▾]  [Set LIVE]
```
- "Move..." operates on all selected outputs (1 or more)
- Confirmation dialog shows count: "Move 3 outputs to A004_C020?"

### Implementation

**File: `ui/output_list.py`**
- Remove the single-only restriction: always use `ExtendedSelection` mode (drop `set_selection_mode()` or default `multi=True`)
- Keep `get_selected_outputs()` as-is (already handles multi-selection)

**File: `ui/main_window.py`**
- `_on_shot_selected()`: enable multi-selection (`set_selection_mode(multi=True)`)
- `_on_reference_selected()`: enable multi-selection (`set_selection_mode(multi=True)`)
- `_on_move_output()`: iterate over `get_selected_outputs()` instead of using `self._current_output`
  - For each output, call `move_module.move_output_to_shot()` / `move_output_to_reference()` / `move_output_to_incoming()`
  - Collect errors per-output and report at the end
  - Show confirmation: "Move {count} output(s) to {destination}?"
- Update `_move_output_btn` enable logic: enable when ≥1 output is selected

**File: `ui/move_dialog.py`**
- Accept list of output names instead of single name
- Header: "Moving 3 outputs" (or "Moving output: Name" for single)
- Rename field hidden when moving multiple (keep original names)
- Preview shows list of outputs being moved

---

## 14. Relocate Buttons — Clean Version Panel Layout

**Current:** The version panel has "Open Folder" and "Create Read" buttons at the bottom of the panel, below the thumbnail/preview area. The bottom action bar only has "Move...".

**New:** Move all buttons out of the version panel:
- **"Open Folder"** → next to the shot name in the header bar. When no shot is selected (or viewing _Incoming), opens the shot root directory.
- **"Create Read" dropdown + "Set LIVE"** → bottom action bar, next to "Move..."

### Header bar (new layout)
```
Project: 4C_Health    Shot: A0001_C005   [📂]       [Refresh]  [Set Project]
```
- `[📂]` opens the current shot's directory on disk
- If no shot selected → opens the project's `Shots/` root directory
- If viewing _Incoming → opens the `_Incoming/` directory
- If viewing Reference → opens the `Reference/` directory

### Bottom action bar (new layout)
```
[Move...]   [Create Read ▾]   [Set LIVE]                    (stretch)
```
- "Create Read" and "Set LIVE" are only visible when in Nuke and an output is selected (not _Incoming)
- "Set LIVE" operates on the currently viewed version in the version panel

### Implementation

**File: `ui/version_panel.py`**
- Remove the button row (`btn_row`) entirely — no more `_open_folder_btn` or `_create_read_btn`
- Remove `_on_open_folder()`, `_on_create_static_read()`, `_on_create_live_read()`, `_on_update_existing_read()` methods
- Keep `_on_set_live()` signal emission but remove the `_set_live_btn` from the version selector row (button moves to bottom bar)
- The version panel becomes purely informational: version selector + details + notes + thumbnail

**File: `ui/main_window.py`**
- **Header:** Add `_open_folder_btn` (folder icon) next to `_shot_label`
  - `_on_open_folder()`: if shot selected → `os.startfile(shot_dir)`. If viewing _Incoming → open `_Incoming/`. If viewing Reference → open Reference dir. If nothing selected → open `Shots/` root.
- **Bottom action bar** (merge `_incoming_bar` and `_output_action_bar` into one unified bar, always visible):
  - `[Move...]` — visible when outputs are selected (any category)
  - `[Move to Shot]` — visible only when viewing _Incoming
  - `[Create Read ▾]` — visible only in Nuke, when output selected (not _Incoming)
  - `[Set LIVE]` — visible only when output selected (not _Incoming)
  - Logic from version_panel's button handlers moves here (read node creation, set LIVE delegates to `_version_panel.live_changed` signal)

---

## Summary of All File Changes

| File | Changes |
|------|---------|
| `ui/main_window.py` | Frame range controls; remove Cancel + Render All; add Re-Render Last; Move to Shot button; LIVE Read node updates; Reference selection handling; Open Folder in header; unified bottom bar with Create Read + Set LIVE; batch move for multi-selected outputs |
| `ui/version_panel.py` | Thumbnail display; buttons removed (moved to main_window bottom bar) |
| `ui/output_list.py` | Multi-selection mode for all categories (shots, Reference, _Incoming) |
| `ui/shot_list.py` | Reference entry below shots |
| `core.py` | Add `status` field to Version |
| `render.py` | `prepare_overwrite()`; upfront version registration with status tracking |
| `incoming.py` | Pre-sorted subdirs scanner; `create_incoming_dirs()` |
| `paths.py` | `get_project_reference_dir()` |
| **New: `nuke_read.py`** | Create/update Read nodes; LIVE expression Read; update LIVE readers |
| **New: `thumbnails.py`** | Thumbnail generation (Nuke) + caching |
| **New: `ui/ingest_dialog.py`** | Dialog for moving incoming items to shots |
| `ui/move_dialog.py` | Batch mode for multiple outputs |

## Implementation Order

1. **Frame range controls** — small, self-contained Nuke bar change
2. **Remove Cancel + Render All, add Re-Render Last** — Nuke bar + render.py status tracking
3. **_Incoming pre-sorted subfolders** — update scanner
4. **Project-level Reference directory** — paths + shot list + main window
5. **Move to Shot (ingest UI)** — builds on updated scanner + reference
6. **Import to Script (Read nodes + LIVE Read)** — new nuke_read.py + version panel
7. **Thumbnails** — nice-to-have, last priority
8. **Multi-selection + batch move** — enable multi-select on all categories, update move dialog and logic
9. **Relocate buttons** — move Open Folder to header, Create Read + Set LIVE to bottom bar, clean up version panel
