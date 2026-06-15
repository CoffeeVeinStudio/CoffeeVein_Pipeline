import nuke
import sys
import os
import contextlib
import io
from pathlib import Path

# Qt.py resolves its binding once at import time. Nuke 15 and earlier use PySide2;
# Nuke 16+ use PySide6. Set this before any tik_manager4 import so the shim picks
# the same binding Nuke itself is using.
if nuke.NUKE_VERSION_MAJOR < 16:
    os.environ.setdefault("QT_PREFERRED_BINDING", "PySide2")
else:
    os.environ.setdefault("QT_PREFERRED_BINDING", "PySide6")

# --- KONFIGURATION ---
# Lista över moduler som ska importeras manuellt, 
# då de saknar en egen menu.py i sin mapp.
MANUAL_IMPORTS = ["W_hotbox", "W_hotboxManager"]

print("=" * 50)
print("Coffee Vein Studio - Menu Init")
print("=" * 50)

NUKE_ROOT = Path(__file__).resolve().parent

# --- HJÄLPFUNKTIONER ---

def build_recursive_menu(directory: Path, menu_obj, mode="gizmo"):
    """Bygger menyer för .gizmo och .nk rekursivt."""
    if not directory.exists():
        return
    
    # Sortera och exkludera skräp
    items = sorted([f for f in directory.iterdir() if not f.name.startswith(('.', '_'))], key=lambda x: x.name.lower())
    
    for item in items:
        if item.is_dir():
            new_menu = menu_obj.addMenu(item.name)
            build_recursive_menu(item, new_menu, mode=mode)
        elif item.suffix in ['.gizmo', '.nk']:
            name = item.stem
            if mode == "gizmo" and item.suffix == ".gizmo":
                menu_obj.addCommand(name, f'nuke.createNode("{name}")')
            elif mode == "template" and item.suffix == ".nk":
                menu_obj.addCommand(name, f'nuke.nodePaste("{item.as_posix()}")')

# --- INITIALISERA MENYER ---
nodes_menu = nuke.menu("Nodes")
cv_menu = nodes_menu.addMenu("CoffeeVein", icon="coffeevein.png")

# === 1a. LADDA PLUGINS (Internal & 3rd Party) ===
print("\n[Loading Plugin Menus]")
for folder in ["internal", "3rd_party"]:
    root = NUKE_ROOT / folder
    if not root.exists():
        continue

    for d in sorted(root.iterdir()):
        if d.is_dir() and d.name.lower() not in ["gizmos", "toolsets", "templates", "icons"]:
            m = d / "menu.py"
            if m.exists():
                with contextlib.redirect_stdout(io.StringIO()), \
                     contextlib.redirect_stderr(io.StringIO()):
                    try:
                        exec(compile(open(m).read(), str(m), 'exec'), {**globals(), '__file__': str(m)})
                        status = "[OK]"
                    except Exception as e:
                        status = "[ERROR]"

                print(f"  {status.ljust(10)} {d.name}")

# === 1b. STANDALONE SCRIPTS (Internal) ===
print("\n[Loading Standalone Scripts]")
for script in sorted((NUKE_ROOT / "internal").glob("*.py")):
    with contextlib.redirect_stdout(io.StringIO()), \
         contextlib.redirect_stderr(io.StringIO()):
        try:
            exec(open(script).read(), globals())
            status = "[OK]"
        except Exception as e:
            status = "[ERROR]"
    print(f"  {status.ljust(10)} {script.stem}")

# === 2. SPECIAL: MANUELLA IMPORTER (W_hotbox etc.) ===
print("\n[Loading Manual Modules]")
original_tprint = nuke.tprint   # Vi sparar undan den riktiga tprint-funktionen temporärt
for module_name in MANUAL_IMPORTS:
    try:
        # Importrerar modulen dynamiskt
        nuke.tprint = lambda *args, **kwargs: None  # Temporärt tysta nuke.tprint
        globals()[module_name] = __import__(module_name)
        nuke.tprint = original_tprint  # Återställ tprint
        
        print(f"  [OK]     {module_name}")
    except ImportError as e:
        print(f"  [ERROR]  {module_name}: {e}")

# === 3. GIZMOS ===
print("\n[Building Gizmo Menus]")
build_recursive_menu(NUKE_ROOT / "internal" / "Gizmos", cv_menu.addMenu("Internal Gizmos"))
build_recursive_menu(NUKE_ROOT / "3rd_party" / "gizmos", cv_menu.addMenu("3rd Party Gizmos"))

# === 4. TEMPLATES / TOOLSETS ===
print("[Building Template Menus]")
build_recursive_menu(NUKE_ROOT / "3rd_party" / "ToolSets", cv_menu.addMenu("Templates"), mode="template")

# === 4.5. COFFEEBOARD PANEL ===
_cb_tools = str(NUKE_ROOT.parent / 'tools')
if _cb_tools not in sys.path:
    sys.path.insert(0, _cb_tools)
try:
    import CoffeeBoard.adapters.nuke_adapter  # noqa: side-effect
except Exception as _e:
    nuke.warning(f'[CoffeeBoard] panel load failed: {_e}')

# === 5. COFFEEVEIN SCENE MANAGER ===
_tools_path = str(NUKE_ROOT.parent / "tools")
toolbar = nuke.menu('Nodes')
smMenu = toolbar.addMenu('SceneManager', icon='coffeevein.png')

# -- Shot Manager (main UI) --
smMenu.addCommand('Shot Manager',
    "import sys\n"
    f"sys.path.insert(0, r'{_tools_path}')\n"
    "from shot_manager.launch import launch_in_nuke\n"
    "launch_in_nuke()",
    "shift+r",
    icon='coffeevein.png')

# -- Save New Scene Version (replaces TIK's Alt+Shift+S) --
smMenu.addCommand('Save New Scene Version',
    "import sys\n"
    f"sys.path.insert(0, r'{_tools_path}')\n"
    "from shot_manager.ui.scene_actions import save_new_version_from_nuke\n"
    "save_new_version_from_nuke()",
    "alt+shift+s",
    icon='coffeevein.png')

smMenu.addSeparator()

smMenu.addCommand('Reconnect Read Nodes',
    "import sys\n"
    f"sys.path.insert(0, r'{_tools_path}')\n"
    "from shot_manager.project_registry import get_current_project_root\n"
    "from shot_manager.nuke_read import reconnect_broken_reads\n"
    "pr = get_current_project_root()\n"
    "reconnect_broken_reads(pr) if pr else nuke.message('No project set in Shot Manager')",
    icon='coffeevein.png')

smMenu.addSeparator()

# -- Package Shot --
smMenu.addCommand('Package Shot for Delivery',
    "import sys\n"
    f"sys.path.insert(0, r'{_tools_path}')\n"
    "from shot_manager.package_launcher import launch_package_dialog\n"
    "launch_package_dialog()",
    icon='coffeevein.png')
# -- Script Packager --
smMenu.addCommand('Package Script for Delivery',
    'from Script_Packager import launch_packager; launch_packager()',
    'ctrl+alt+p', icon='coffeevein.png')

print("\n" + "=" * 50)
print("Menu Init Complete")
print("=" * 50)