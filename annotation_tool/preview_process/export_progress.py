"""Modal progress dialog for 3D preview export tasks."""
from __future__ import annotations

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QApplication, QProgressDialog, QWidget


def open_export_progress(
    parent: QWidget,
    title: str,
    message: str,
) -> QProgressDialog:
    """Show a non-cancelable indeterminate progress dialog and pump events once."""
    dlg = QProgressDialog(message, None, 0, 0, parent)
    dlg.setWindowTitle(title)
    dlg.setWindowModality(Qt.WindowModal)
    dlg.setMinimumDuration(0)
    dlg.setAutoClose(False)
    dlg.setAutoReset(False)
    dlg.setCancelButton(None)
    dlg.setMinimumWidth(360)
    dlg.show()
    QApplication.processEvents()
    return dlg
