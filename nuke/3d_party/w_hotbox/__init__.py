# Importera modulerna så de blir tillgängliga
import sys
import os

# Lägg till den här mappen i sys.path om den inte redan finns
current_dir = os.path.dirname(__file__)
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)