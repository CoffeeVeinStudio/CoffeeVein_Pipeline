"""Qt compatibility layer — imports PySide2 or PySide6 transparently.

In Nuke 15: PySide2 is available (bundled with Nuke).
In Nuke 16+: PySide6 is available.
Standalone: Uses whichever is installed (prefers PySide2, falls back to PySide6).

Usage:
    from shot_manager.qt_compat import QtWidgets, QtCore, QtGui
"""

try:
    from PySide2 import QtWidgets, QtCore, QtGui
    QT_VERSION = 2
except ImportError:
    from PySide6 import QtWidgets, QtCore, QtGui
    QT_VERSION = 6

# Alias for exec() compatibility (PySide2 uses exec_(), PySide6 uses exec())
if QT_VERSION == 2:
    def app_exec(app):
        return app.exec_()
else:
    def app_exec(app):
        return app.exec()
