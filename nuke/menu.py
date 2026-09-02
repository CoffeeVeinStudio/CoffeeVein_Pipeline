import nuke
import sys
import os
import glob
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

# === 1a-PRE. CRAGL CONNECT QT6 BOOTSTRAP ===
# cragl connect v3.17's native connect_w.pyd is compiled against PySide6/Qt6.
# Nuke <=15 ships PySide2/Qt5, so connect_w's own QApplication check fails
# ("QWidget: Must construct a QApplication before a QWidget") unless a Qt6
# QApplication already exists in-process. We construct one here, borrowed
# from a standalone PySide6 install, before cragl's menu (and its "connect"
# command) is ever wired up. Nuke 16+ ships PySide6 natively and doesn't
# need this.
_cragl_qt6_app = None
if nuke.NUKE_VERSION_MAJOR < 16 and (NUKE_ROOT / "3rd_party" / "cragl").exists():
    print("\n[cragl Qt6 Bootstrap]")
    _py_tag = f"Python{sys.version_info[0]}{sys.version_info[1]}"
    _site_packages_candidates = glob.glob(
        os.path.expandvars(rf"%LOCALAPPDATA%\Programs\Python\{_py_tag}\Lib\site-packages")
    )
    for _sp in _site_packages_candidates:
        if os.path.isdir(os.path.join(_sp, "PySide6")):
            if _sp not in sys.path:
                sys.path.insert(0, _sp)
            # Nuke's own Qt5 startup pins QT_QPA_PLATFORM_PLUGIN_PATH (often to an
            # empty value) to keep Qt5 from picking up unrelated system Qt plugins.
            # Qt6 inherits that same env var, finds no "windows" platform plugin at
            # that (wrong/empty) path, and aborts the whole process. Point it at
            # PySide6's own bundled plugin dir before constructing the Qt6 app.
            _qt6_platforms = os.path.join(_sp, "PySide6", "plugins", "platforms")
            if os.path.isdir(_qt6_platforms):
                os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = _qt6_platforms
            try:
                from PySide6.QtWidgets import QApplication as _QApp6
                _cragl_qt6_app = _QApp6.instance() or _QApp6(sys.argv)
                print(f"  [OK]     PySide6 QApplication ready ({_sp})")
            except Exception as e:
                print(f"  [ERROR]  PySide6 bootstrap failed: {e}")

            # cragl's own connect/*.py files (video.py at least, maybe others) branch
            # on nuke.NUKE_VERSION_MAJOR at import time to decide both WHICH Qt
            # binding to pull in (PySide2 vs PySide6) AND which API surface to call
            # against it (e.g. QMediaPlayer.stateChanged on Qt5 vs
            # .playbackStateChanged on Qt6) - a leftover from before connect_w.pyd
            # required Qt6 unconditionally. Since connect_w.pyd itself is always
            # Qt6, every one of those branches needs to agree on ">=16" even though
            # the real Nuke here is <16, or we get a slow trickle of "wrong
            # binding"/"wrong attribute" crashes as each branch gets hit. Rather
            # than patch cragl's shipped files one crash at a time, make Nuke report
            # itself as version 16 for the duration of importing cragl's own
            # modules only, via an import hook - so every NK-gated branch in their
            # code consistently takes the Qt6 path, matching the real Qt6
            # QApplication we just constructed above. Nothing outside cragl's own
            # "connect" package ever sees the spoofed version.
            try:
                import importlib.abc
                import importlib.machinery

                class _CraglNukeVersionSpoofFinder(importlib.abc.MetaPathFinder):
                    def find_spec(self, name, path, target=None):
                        if name != "connect" and not name.startswith("connect."):
                            return None
                        spec = importlib.machinery.PathFinder.find_spec(name, path, target)
                        if spec is None or spec.loader is None or not spec.origin:
                            return None
                        if "cragl" not in spec.origin.replace("\\", "/"):
                            return None
                        real_exec_module = spec.loader.exec_module
                        def exec_module(module, _real_exec_module=real_exec_module):
                            _real_major = nuke.NUKE_VERSION_MAJOR
                            nuke.NUKE_VERSION_MAJOR = 16
                            try:
                                _real_exec_module(module)
                            finally:
                                nuke.NUKE_VERSION_MAJOR = _real_major
                        spec.loader.exec_module = exec_module
                        return spec

                sys.meta_path.insert(0, _CraglNukeVersionSpoofFinder())
                print("  [OK]     cragl NUKE_VERSION_MAJOR spoof (import hook) installed")
            except Exception as e:
                print(f"  [WARN]   cragl NUKE_VERSION_MAJOR spoof failed: {e}")
            break
    else:
        print("  [SKIP]   No PySide6 install found next to a matching Python version")

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