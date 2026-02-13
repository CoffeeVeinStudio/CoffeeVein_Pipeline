"""Standalone launcher for CoffeeVein Shot Manager.

Usage:
    python -m shot_manager.launch [project_path]

Or from any script:
    from tools.shot_manager.launch import launch
    launch("D:/CoffeeVeinStudio/Projects/PROJECTS/SWAN")
"""

import sys
from pathlib import Path


def launch(project_root=None):
    """Launch the Shot Manager window.

    Args:
        project_root: Path to the TIK project root. If None, user must
                      set it via the UI.
    """
    from .qt_compat import QtWidgets, app_exec
    from .ui.main_window import ShotManagerWindow

    # Create app if not already running (standalone mode)
    app = QtWidgets.QApplication.instance()
    standalone = False
    if app is None:
        app = QtWidgets.QApplication(sys.argv)
        standalone = True

        # Apply dark theme
        app.setStyle("Fusion")
        palette = _dark_palette()
        app.setPalette(palette)

    window = ShotManagerWindow(project_root=project_root)
    window.show()

    if standalone:
        sys.exit(app_exec(app))

    return window


def launch_in_nuke(project_root=None):
    """Launch Shot Manager inside Nuke.

    If no project_root is given, attempts to detect it from the
    current Nuke script path.
    """
    if project_root is None:
        try:
            from .render import get_current_nuke_context
            root, shot_name, shot_dir = get_current_nuke_context()
            if root is not None:
                project_root = str(root)
        except Exception:
            pass

    from .qt_compat import QtWidgets
    from .ui.main_window import ShotManagerWindow

    # In Nuke, find the main Nuke window as parent
    parent = None
    try:
        for widget in QtWidgets.QApplication.topLevelWidgets():
            if widget.metaObject().className() == "Foundry::UI::DockMainWindow":
                parent = widget
                break
    except Exception:
        pass

    window = ShotManagerWindow(project_root=project_root, parent=parent)
    window.show()
    window.raise_()

    return window


def _dark_palette():
    """Create a dark color palette matching TIK/Nuke aesthetic."""
    from .qt_compat import QtGui

    palette = QtGui.QPalette()

    # Base colors
    dark = QtGui.QColor(42, 42, 42)
    darker = QtGui.QColor(30, 30, 30)
    mid = QtGui.QColor(55, 55, 55)
    light = QtGui.QColor(200, 200, 200)
    highlight = QtGui.QColor(71, 143, 203)  # TIK's render blue

    palette.setColor(QtGui.QPalette.Window, dark)
    palette.setColor(QtGui.QPalette.WindowText, light)
    palette.setColor(QtGui.QPalette.Base, darker)
    palette.setColor(QtGui.QPalette.AlternateBase, mid)
    palette.setColor(QtGui.QPalette.ToolTipBase, dark)
    palette.setColor(QtGui.QPalette.ToolTipText, light)
    palette.setColor(QtGui.QPalette.Text, light)
    palette.setColor(QtGui.QPalette.Button, mid)
    palette.setColor(QtGui.QPalette.ButtonText, light)
    palette.setColor(QtGui.QPalette.BrightText, QtGui.QColor(255, 255, 255))
    palette.setColor(QtGui.QPalette.Link, highlight)
    palette.setColor(QtGui.QPalette.Highlight, highlight)
    palette.setColor(QtGui.QPalette.HighlightedText, QtGui.QColor(255, 255, 255))

    # Disabled colors
    palette.setColor(
        QtGui.QPalette.Disabled, QtGui.QPalette.Text,
        QtGui.QColor(128, 128, 128)
    )
    palette.setColor(
        QtGui.QPalette.Disabled, QtGui.QPalette.ButtonText,
        QtGui.QColor(128, 128, 128)
    )

    return palette


if __name__ == "__main__":
    project = sys.argv[1] if len(sys.argv) > 1 else None
    launch(project)
