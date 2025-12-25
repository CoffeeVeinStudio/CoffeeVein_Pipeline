
import nuke


# Importera W_hotbox på ett mer robust sätt
try:
    import W_hotbox
    import W_hotboxManager
    print("W_hotbox loaded successfully")
except ImportError as e:
    print(f"Failed to load W_hotbox: {e}")
    # Debug: Visa vilka paths som finns
    import sys
    print("Python paths:")
    for p in sys.path:
        print(f"  {p}")
    
    
'''
from CvS_reference_board import reference_board



scripts={'show reference board':'reference_board.show_reference_board()',
         }





# Sidomenyn
t = nuke.menu('Nodes').addMenu('CoffeeVeinStudio')
# Menyfaltet i toppen
m = nuke.menu('Nuke').addMenu('CoffeeVeinStudio')

for name, script in scripts.items():
    t.addCommand(name,script)
    m.addCommand(name,script)

'''