import nuke
import sys
from pathlib import Path

print('=' * 50)
print('Coffee Vein Studio - Pipeline Init')
print('=' * 50)

NUKE_ROOT = Path(__file__).resolve().parent

def add_to_paths(path_obj):
    """Lägger till mappen i både Nuke och Python path."""
    if path_obj.exists():
        p_str = path_obj.as_posix()
        nuke.pluginAddPath(p_str)
        if p_str not in sys.path:
            sys.path.insert(0, p_str)
        return True
    return False

# 1. Rotmappar
add_to_paths(NUKE_ROOT)
add_to_paths(NUKE_ROOT / "icons")

# === 2. SKANNA INTERNAL OCH 3RD PARTY (MED HIERARKI) ===
for category in ["internal", "3rd_party"]:
    cat_path = NUKE_ROOT / category
    if not cat_path.exists():
        continue
        
    print(f"\n[{category.replace('_', ' ').title()}]")
    
    # Lista alla mappar i första nivån (t.ex. w_hotbox, gizmos)
    for plugin_dir in sorted(cat_path.iterdir()):
        if not plugin_dir.is_dir() or plugin_dir.name.startswith('.'):
            continue
            
        add_to_paths(plugin_dir)
        print(f"    + {plugin_dir.name}")
        
        # Om det är gizmo-mappen, skanna en nivå till för kategorierna
        if plugin_dir.name.lower() == "gizmos":
            for sub_dir in sorted(plugin_dir.iterdir()):
                if sub_dir.is_dir() and not sub_dir.name.startswith('.'):
                    add_to_paths(sub_dir)
                    print(f"        + {sub_dir.name}")
        
        # För övriga paket, kolla bara efter standardmappar (python, icons etc)
        else:
            for sub_dir in plugin_dir.iterdir():
                if sub_dir.is_dir() and sub_dir.name.lower() in ["icons", "python", "gizmos"]:
                    add_to_paths(sub_dir)

print('\n' + '=' * 50)
print('Pipeline Init Complete')
print('=' * 50)