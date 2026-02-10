import nuke
import sys
import contextlib
import io
from pathlib import Path

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

# === 1. LADDA PLUGINS (Internal & 3rd Party) ===
print("\n[Loading Plugin Menus]")
for folder in ["internal", "3rd_party"]:
    root = NUKE_ROOT / folder
    if not root.exists():
        continue
        
    for d in sorted(root.iterdir()):
        if d.is_dir() and d.name.lower() not in ["gizmos", "toolsets", "templates", "icons"]:
            m = d / "menu.py"
            if m.exists():
                # Tysta ner output
                with contextlib.redirect_stdout(io.StringIO()), \
                     contextlib.redirect_stderr(io.StringIO()):
                    try:
                        exec(open(m).read(), globals())
                        status = "[OK]"
                    except Exception as e:
                        status = f"[ERROR]"
                
                print(f"  {status.ljust(10)} {d.name}")

# === 2. SPECIAL: MANUELLA IMPORTER (W_hotbox etc.) ===
print("\n[Loading Manual Modules]")
original_tprint = nuke.tprint   # Vi sparar undan den riktiga tprint-funktionen temporärt
for module_name in MANUAL_IMPORTS:
    try:
        # Importrerar modulen dynamiskt
        nuke.tprint = lambda *args, **kwargs: None  # Temporärt tysta nuke.tprint
        __import__(module_name)
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

print("\n" + "=" * 50)
print("Menu Init Complete")
print("=" * 50)