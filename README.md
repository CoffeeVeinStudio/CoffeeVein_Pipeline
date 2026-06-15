# CoffeeVein Pipeline

A VFX pipeline built around [Kitsu](https://kitsu.cg-wire.com) for solo and small-studio production tracking. Built by [CoffeeVein Studio](https://coffeeveinstudio.com) as a practical TD learning project.

---

## What it does

- Creates and manages productions in Kitsu via the [gazu](https://github.com/cgwire/gazu) Python client
- Automatically creates matching folder structures on disk when projects and shots are created
- Designed for a Nuke-centric compositing workflow with multi-DCC support planned
- Lazy folder creation: DCC-specific folders are only created when a shot is actually opened in that DCC

---

## Tech Stack

- **Python 3.10+**
- **[Kitsu](https://kitsu.cg-wire.com)** — production tracking (self-hosted via Docker)
- **[gazu](https://github.com/cgwire/gazu)** — Python client for the Kitsu API
- **[PySide6](https://doc.qt.io/qtforpython-6/)** — UI (launcher app, in progress)
- **Rocky Linux 9** — server OS
- **Docker** — Kitsu deployment

---

## Project Structure

```
Pipeline/
    backend/                    # Kitsu/pipeline logic
        kitsu_client.py         # Authentication and connection
        project_manager.py      # Create, get, list projects
        sequence_manager.py     # Create, get, list sequences
        shot_manager.py         # Create, get, list, update shots
        pipeline_service.py     # Coordinates cross-manager operations
    launcher/                   # PySide6 app (in progress)
        main.py                 # Bootstrap and entry point
    nuke/                       # Nuke-specific plugins and init
    shared/
        vendor/                 # Third-party packages (installed via pip)
        templates/              # YAML folder structure templates
        lib/
            utils.py            # Config, env, template loading
            folder_manager.py   # Disk operations
```

---

## Setup

### Requirements

- Python 3.10+
- A running Kitsu instance (see [Kitsu self-hosting](https://zou.cg-wire.com))
- Docker (for running Kitsu locally)

### Install dependencies

```bash
pip install gazu pyyaml --target=Pipeline/shared/vendor
```

### Configuration

Copy `shared/lib/config.yaml` and update with your values:

```yaml
pipeline_root: "D:/YourStudio/Pipeline"
projects_root: "D:/YourStudio/Projects"
kitsu_host: "http://your-kitsu-server:8012/api"
```

Create a `.env` file in `backend/`:

```
KITSU_EMAIL=your@email.com
KITSU_PASSWORD=yourpassword
```

### Run

```bash
cd Pipeline
python launcher/main.py
```

---

## Status

Active development. Current focus: PySide6 launcher app.

| Component | Status |
|---|---|
| Backend (Kitsu integration) | ✅ Done |
| Folder structure automation | ✅ Done |
| PySide6 launcher app | 🔨 In progress |
| Nuke panel | 📋 Planned |
| Houdini adapter | 📋 Planned |
| Blender adapter | 📋 Planned |

---

## Background

This pipeline replaces a TIK Manager-based workflow with a Kitsu-integrated system built from scratch. The goal is a lightweight launcher that keeps Kitsu in sync with the local file system, with DCC-specific panels for daily work.

Built and maintained by Christoffer von Sydow / [CoffeeVein Studio](https://coffeeveinstudio.com).