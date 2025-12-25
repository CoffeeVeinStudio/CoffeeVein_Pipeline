import nuke
import os

print('='*30)
print('Calling Coffee Vein Studio init -> ', os.path.dirname(__file__))

plugins_to_load = { 
    '3d_party': 
        ('w_hotbox',),
    'internal':
        ('CoffeeBoard',)}

for base_folder, sub_folders in plugins_to_load.items():
    for sub_folder in sub_folders:
        
        # Exempel 1: os.path.join('3d_party', 'w_hotbox') -> '3d_party\w_hotbox'
        # Exempel 2: os.path.join('internal', 'CoffeeBoard') -> 'internal\CoffeeBoard'
        path_to_add = os.path.join(base_folder, sub_folder)
        
        print(f"\tLägger till {sub_folder}")
        print('\t\t' + path_to_add)
        nuke.pluginAddPath(path_to_add)



print('='*30)
print('\n')