"""Launcher for the Package Shot dialog from Nuke menu."""


def launch_package_dialog():
    """Launch the Package Shot dialog using the current Nuke script's context."""
    from .qt_compat import QtWidgets
    from .ui.package_dialog import PackageDialog

    # Detect shot context from the current Nuke script
    try:
        from .render import get_current_nuke_context
        project_root, shot_name, shot_dir = get_current_nuke_context()
    except Exception:
        project_root = shot_name = shot_dir = None

    if not shot_name or not shot_dir:
        QtWidgets.QMessageBox.warning(
            None, "No Shot Detected",
            "Could not determine the current shot from the Nuke script.\n\n"
            "Make sure your script is saved inside a shot directory."
        )
        return

    # Find Nuke main window as parent
    parent = None
    try:
        for widget in QtWidgets.QApplication.topLevelWidgets():
            if widget.metaObject().className() == "Foundry::UI::DockMainWindow":
                parent = widget
                break
    except Exception:
        pass

    dialog = PackageDialog(
        shot_name=shot_name,
        shot_dir=shot_dir,
        parent=parent,
    )
    dialog.exec_()
