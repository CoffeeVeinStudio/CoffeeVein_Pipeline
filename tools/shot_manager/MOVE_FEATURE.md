# Output Move Feature

## Overview

The Move feature allows you to relocate entire outputs (all versions together) between shots, to project-level Reference, or back to _Incoming.

**Primary Use Case:** Fix accidental ingestion to the wrong shot.

---

## How to Use

1. **Select a shot or Reference** in the shot list
2. **Select an output** in the output list
3. **Click "Move..."** button (bottom action bar)
4. **Choose destination:**
   - **Shot:** Select target shot from dropdown
   - **Reference:** Move to project-level Reference directory
   - **_Incoming:** Select subfolder (Plates/CG/Reference) — flattens version structure
5. **Optionally rename** the output folder
6. **Click "Move"** to confirm

---

## Behavior

### Version Handling
- **Keeps same version numbers** when possible (v001 → v001, v002 → v002)
- **Merges versions** if destination has same output name:
  - If destination has v001-v003, source v001-v002 become v004-v005
- **All versions moved together** — not individual versions

### LIVE Status
- **Destination has LIVE:** Keeps destination's LIVE version
- **Destination has no LIVE:** Moved output's current LIVE becomes new LIVE at destination
- **Source LIVE:** Always deleted after move

### Moving to _Incoming
- **Flattens structure:** All version files moved to _Incoming subfolder
- **Version metadata lost:** .versions.json deleted
- **Files may be renamed:** Adds suffix (_1, _2, etc.) to avoid conflicts

---

## Technical Details

### Files Modified
- **move.py** (new): Core move logic
  - `move_output_to_shot()`
  - `move_output_to_reference()`
  - `move_output_to_incoming()`
  - Version renumbering and .versions.json updates
  - LIVE symlink/junction handling

- **ui/move_dialog.py** (new): Move dialog UI
  - Destination type selector (Shot/Reference/_Incoming)
  - Target selector (changes based on destination)
  - Optional rename field
  - Preview of move operation

- **ui/main_window.py**:
  - Added output action bar (similar to _Incoming bar)
  - "Move..." button (shown when viewing Shot or Reference)
  - `_on_move_output()` handler
  - Context-aware bar visibility

### Move Logic

**Shot → Shot:**
```
Source: {shot_A}/Comp/renders/Denoise/v001/
Target: {shot_B}/Comp/renders/Denoise/v004/ (if v001-v003 exist)
```

**Shot → Reference:**
```
Source: {shot_A}/Comp/renders/HDRI/v001/
Target: {project_root}/Reference/HDRI/v001/
```

**Shot → _Incoming:**
```
Source: {shot_A}/Comp/renders/Denoise/v001/file.####.exr
Target: {project_root}/_Incoming/Plates/file.1001.exr, file.1002.exr, ...
```

**Reference → Shot:**
```
Source: {project_root}/Reference/LUT/v001/
Target: {shot_A}/Reference/LUT/v001/
```

### Edge Cases Handled
- **Name conflicts:** Version renumbering (merge)
- **LIVE conflicts:** Keep destination's LIVE if exists
- **Empty directories:** Cleaned up after move
- **.versions.json:** Updated at both source and destination
- **Windows junctions:** Properly deleted without deleting target

---

## Testing Checklist

### Shot → Shot
- [ ] Move output to different shot
- [ ] Version numbers preserved when no conflict
- [ ] Version numbers renumbered when conflict exists
- [ ] LIVE status handled correctly
- [ ] Source cleaned up (empty dirs removed)

### Shot → Reference
- [ ] Output moved to project-level Reference
- [ ] Simplified Reference structure maintained
- [ ] Optional rename works

### Shot/Reference → _Incoming
- [ ] Files flattened to _Incoming subfolder
- [ ] Version structure lost
- [ ] .versions.json deleted
- [ ] Name conflicts resolved with suffix

### UI
- [ ] "Move..." button shown when viewing Shot or Reference
- [ ] Button hidden when viewing _Incoming
- [ ] Button enabled only when output selected
- [ ] Dialog shows correct destination options
- [ ] Preview text updates correctly

### Error Handling
- [ ] Missing source directory
- [ ] Missing target shot
- [ ] Permission errors
- [ ] Disk full errors

---

## Future Enhancements (Optional)

- **Undo feature:** Keep backup before move
- **Move individual versions:** Not just entire output
- **Batch move:** Move multiple outputs at once
- **Move history log:** Track all moves in .json file
- **Keyboard shortcut:** Ctrl+M for move dialog
