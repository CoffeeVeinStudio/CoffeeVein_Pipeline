#!/usr/bin/env python
"""Standalone launcher for Tik Manager 4"""

import sys
from pathlib import Path

# Add the tik_manager4 directory to Python path
tik_manager_path = Path(__file__).parent / "tikmanager" / "tik_manager4"
sys.path.insert(0, str(tik_manager_path))

from tik_manager4.ui.Qt import QtWidgets, QtCore
from tik_manager4.ui import main

def launch_standalone():
    """Launch Tik Manager 4 in standalone mode"""
    # Create QApplication if it doesn't exist
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
        app.setAttribute(QtCore.Qt.AA_DontUseNativeMenuBar)
    
    # Launch Tik Manager
    tik_manager_ui = main.launch(dcc="Standalone")
    
    # Show the UI
    tik_manager_ui.show()
    
    # Run the application
    if hasattr(app, 'exec'):
        sys.exit(app.exec())
    else:  # Fallback for older PyQt versions
        sys.exit(app.exec_())

if __name__ == "__main__":
    launch_standalone()