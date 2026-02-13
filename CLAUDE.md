# Pipeline Project Instructions

## Git Commit Guidelines

**CRITICAL:** Do NOT include "Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>" in any git commits or publishes for this project.

When creating commits:
- Use concise, descriptive commit messages
- Focus on the "why" rather than just the "what"
- Follow the existing commit message style (see git log)
- DO NOT add co-author attribution lines

## Project Structure

This is a VFX pipeline for CoffeeVein Studio with:
- **Nuke integration** — Custom tools, gizmos, and menu structure
- **TIK Manager** — Scene versioning system (handles .nk file versions)
- **Shot Manager** — Custom render output versioning and incoming asset management
- **tikmanager/coffeevein_settings/** — Project-specific TIK settings and templates

## Shot Manager Architecture

The Shot Manager (`tools/shot_manager/`) is a custom tool that handles:
- **Render outputs** — Versioned renders with status tracking (rendering/complete/incomplete)
- **_Incoming assets** — Pre-sorted subfolders (Plates/CG/Reference) with ingest UI
- **Read node creation** — Static and LIVE (auto-tracking) Read nodes in Nuke
- **Version metadata** — JSON-based tracking separate from TIK Manager

**Key Principle:** TIK handles scene versioning (.nk files), Shot Manager handles render outputs and incoming assets.

## Nuke Pipeline Conventions

- **Always use forward slashes** in file paths (even on Windows) — backslashes cause EXR render errors
- **Path storage:** Use `.absolute()` instead of `.resolve()` to avoid UNC path conversion on mapped drives
- **Qt compatibility:** Use `qt_compat.py` for PySide2/PySide6 compatibility (Nuke 15 vs 16+)
- **Project path:** Mapped drive `Z:` → `\\DESKTOP-SO3GUK7\Projects\`

## Code Style

- Keep implementations simple and focused — don't over-engineer
- Only add features/refactors that are explicitly requested
- Avoid adding error handling for scenarios that can't happen
- Trust internal code and framework guarantees
- No docstrings/comments on unchanged code

## VFX Company Prospecting

(See memory for full details)
- Two prospect types: VFX companies (partners) and production companies (clients)
- Always check `false_positives.csv` before classifying companies
- Ask about ALL search criteria before searching (bransch, ort, antal anställda)

## Testing

When implementing Shot Manager features:
- Test in both Nuke and standalone mode
- Check frame range edge cases (single frame, custom ranges)
- Verify file path handling (forward slashes, relative vs absolute)
- Ensure LIVE Read nodes update correctly when versions change
