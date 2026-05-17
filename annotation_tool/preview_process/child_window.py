"""
Top-level window for the 3D-preview child process.

Hosts the reused VolumePreview3D widget (which owns the PyVista QtInteractor).
All preview work happens in this process so the main app's UI stays responsive
regardless of mesh size.

The window also offers a small brightness slider at the bottom that scales the
intensity of every renderer light (key/fill/rim or the default headlight). It
lives in the child window — not in the main app — because it tweaks GPU state
on the plotter and has no need to round-trip through IPC.
"""
from __future__ import annotations

import os

from typing import Callable, Optional

from PyQt5.QtCore import Qt, QThread, pyqtSignal
from PyQt5.QtGui import QCloseEvent
from PyQt5.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMessageBox,
    QProgressDialog,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..utils.logging_config import get_logger
from ..views.volume_preview_3d import VolumePreview3D
from .export_progress import open_export_progress
from .export_worker import PreviewExportWorker

logger = get_logger(__name__)


# Slider value 100 == factor 1.0 (default). Range 10..250 -> factor 0.1..2.5.
_BRIGHTNESS_SLIDER_SCALE = 100
_BRIGHTNESS_DEFAULT = 100  # %
_BRIGHTNESS_MIN = 10
_BRIGHTNESS_MAX = 250


class ChildPreviewWindow(QMainWindow):
    """Standalone window hosting the 3D preview widget plus a brightness control."""

    user_closed = pyqtSignal()
    reset_view_clicked = pyqtSignal()
    preview_ui_changed = pyqtSignal(dict)

    def __init__(self, title: str = "3D Volume Preview") -> None:
        super().__init__()
        self.setWindowTitle(title)
        self.resize(1024, 768)
        self.setMinimumSize(640, 480)

        central = QWidget(self)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._preview = VolumePreview3D(central)
        root.addWidget(self._preview, 1)

        # Brightness strip — thin bar at the bottom. Subtle styling so the
        # 3D view stays the focus.
        self._brightness_bar = self._build_brightness_bar(central)
        root.addWidget(self._brightness_bar, 0)

        self.setCentralWidget(central)

        self._export_thread: Optional[QThread] = None
        self._export_worker: Optional[PreviewExportWorker] = None
        self._snap_btn: Optional[QToolButton] = None
        self._mesh_btn: Optional[QToolButton] = None
        self._snapshot_default_dir = ""
        self._mesh_default_dir = ""
        self._syncing_brightness = False

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_brightness_bar(self, parent: QWidget) -> QWidget:
        bar = QWidget(parent)
        bar.setStyleSheet(
            "QWidget { background-color: #1a1a1a; }"
            "QLabel { color: #d8d8d8; font-size: 11px; }"
            "QToolButton { color: #d8d8d8; background: transparent;"
            "  border: 1px solid #3a3a3a; border-radius: 3px; padding: 2px 8px; }"
            "QToolButton:hover { background-color: #2a2a2a; }"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 4, 10, 6)
        layout.setSpacing(8)

        label = QLabel("Brightness")
        label.setToolTip(
            "Scales the intensity of every light in the 3D scene.\n"
            "100% is the default. Lower = darker, higher = brighter.\n"
            "Helpful for revealing detail inside dark cavities or toning down\n"
            "overly bright isosurfaces."
        )
        layout.addWidget(label)

        self._brightness_slider = QSlider(Qt.Horizontal, bar)
        self._brightness_slider.setRange(_BRIGHTNESS_MIN, _BRIGHTNESS_MAX)
        self._brightness_slider.setValue(_BRIGHTNESS_DEFAULT)
        self._brightness_slider.setSingleStep(5)
        self._brightness_slider.setPageStep(20)
        self._brightness_slider.setToolTip(
            "Drag to brighten or darken the 3D scene without rebuilding the preview."
        )
        self._brightness_slider.valueChanged.connect(self._on_brightness_changed)
        layout.addWidget(self._brightness_slider, 1)

        self._brightness_value = QLabel(f"{_BRIGHTNESS_DEFAULT}%")
        self._brightness_value.setMinimumWidth(46)
        self._brightness_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self._brightness_value)

        reset_btn = QToolButton(bar)
        reset_btn.setText("Reset")
        reset_btn.setToolTip("Restore the default brightness (100%).")
        reset_btn.clicked.connect(self._reset_brightness)
        layout.addWidget(reset_btn)

        layout.addSpacing(16)

        self._snap_btn = QToolButton(bar)
        self._snap_btn.setText("Save snapshot…")
        self._snap_btn.setToolTip(
            "Save a high-resolution PNG of the current 3D view (3× window size)."
        )
        self._snap_btn.clicked.connect(self._save_snapshot)
        layout.addWidget(self._snap_btn)

        self._mesh_btn = QToolButton(bar)
        self._mesh_btn.setText("Export 3D model…")
        self._mesh_btn.setToolTip(
            "Export the visible surface mesh (STL, OBJ, VTK, PLY, VTP).\n"
            "Available after an isosurface preview is built."
        )
        self._mesh_btn.clicked.connect(self._export_mesh)
        layout.addWidget(self._mesh_btn)

        return bar

    # ------------------------------------------------------------------
    # External API
    # ------------------------------------------------------------------
    @property
    def preview(self) -> VolumePreview3D:
        return self._preview

    def set_status_text(self, text: str) -> None:
        # Status now lives only in the main app's volume panel.
        del text

    def reset_orientation(self) -> None:
        self._preview.reset_orientation()

    def apply_preview_ui(
        self,
        *,
        brightness_percent: Optional[int] = None,
        snapshot_dir: Optional[str] = None,
        mesh_dir: Optional[str] = None,
    ) -> None:
        if snapshot_dir is not None:
            self._snapshot_default_dir = (snapshot_dir or "").strip()
        if mesh_dir is not None:
            self._mesh_default_dir = (mesh_dir or "").strip()
        if brightness_percent is not None:
            pct = max(_BRIGHTNESS_MIN, min(_BRIGHTNESS_MAX, int(brightness_percent)))
            self._syncing_brightness = True
            try:
                self._brightness_slider.setValue(pct)
            finally:
                self._syncing_brightness = False
            factor = float(pct) / float(_BRIGHTNESS_SLIDER_SCALE)
            self._brightness_value.setText(f"{pct}%")
            self._preview.set_brightness(factor)

    # ------------------------------------------------------------------
    # Brightness handling
    # ------------------------------------------------------------------
    def _on_brightness_changed(self, value: int) -> None:
        factor = float(value) / float(_BRIGHTNESS_SLIDER_SCALE)
        self._brightness_value.setText(f"{int(value)}%")
        self._preview.set_brightness(factor)
        if not self._syncing_brightness:
            self.preview_ui_changed.emit({"brightness_percent": int(value)})

    def _reset_brightness(self) -> None:
        # `setValue` will fire `valueChanged`, which both updates the label
        # and pushes the new factor down to the preview widget.
        self._brightness_slider.setValue(_BRIGHTNESS_DEFAULT)

    def _export_in_progress(self) -> bool:
        return self._export_thread is not None and self._export_thread.isRunning()

    def _set_export_busy(self, busy: bool) -> None:
        if self._snap_btn is not None:
            self._snap_btn.setEnabled(not busy)
        if self._mesh_btn is not None:
            self._mesh_btn.setEnabled(not busy)

    def _close_progress(self, progress: Optional[QProgressDialog]) -> None:
        if progress is None:
            return
        try:
            progress.close()
            progress.deleteLater()
        except Exception:
            pass
        QApplication.processEvents()

    def _run_export_async(
        self,
        start_fn: Callable[[PreviewExportWorker], None],
        success_title: str,
        fail_title: str,
        progress: Optional[QProgressDialog] = None,
    ) -> None:
        """Run ``start_fn(worker)`` on a background QThread."""
        if self._export_in_progress():
            self._close_progress(progress)
            return

        thread = QThread(self)
        worker = PreviewExportWorker()
        worker.moveToThread(thread)

        def _on_finished(ok: bool, message: str) -> None:
            self._close_progress(progress)
            self._set_export_busy(False)
            if ok:
                QMessageBox.information(self, success_title, f"Saved:\n{message}")
            else:
                QMessageBox.warning(self, fail_title, message or "Export failed.")

        def _cleanup() -> None:
            if self._export_worker is worker:
                self._export_worker = None
            if self._export_thread is thread:
                self._export_thread = None
            worker.deleteLater()
            thread.deleteLater()

        worker.finished.connect(_on_finished, Qt.QueuedConnection)
        worker.finished.connect(thread.quit, Qt.QueuedConnection)
        thread.finished.connect(_cleanup)

        self._export_thread = thread
        self._export_worker = worker
        self._set_export_busy(True)
        thread.started.connect(lambda: start_fn(worker))
        thread.start()

    def _default_snapshot_path(self) -> str:
        base = self._snapshot_default_dir or os.path.expanduser("~")
        return os.path.join(base, "volume_preview.png")

    def _default_mesh_path(self) -> str:
        base = self._mesh_default_dir or os.path.expanduser("~")
        return os.path.join(base, "volume_preview.stl")

    def _remember_export_dir(self, path: str, *, snapshot: bool) -> None:
        folder = os.path.dirname(os.path.abspath(path))
        if not folder:
            return
        if snapshot:
            self._snapshot_default_dir = folder
        else:
            self._mesh_default_dir = folder
        self.preview_ui_changed.emit({
            "snapshot_dir" if snapshot else "mesh_dir": folder,
        })

    def _save_snapshot(self) -> None:
        if self._export_in_progress():
            return
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save 3D Preview Snapshot",
            self._default_snapshot_path(),
            "PNG image (*.png);;All files (*)",
        )
        if not path:
            return
        if not path.lower().endswith(".png"):
            path += ".png"

        progress = open_export_progress(
            self, "Export snapshot", "Capturing 3D view (high resolution)…"
        )
        self._set_export_busy(True)
        try:
            # OpenGL capture must stay on the GUI thread.
            image = self._preview.capture_screenshot_array(scale=3)
            if image is None:
                self._close_progress(progress)
                self._set_export_busy(False)
                QMessageBox.warning(
                    self,
                    "Snapshot failed",
                    "Could not capture the 3D view. Build a preview first.",
                )
                return

            progress.setLabelText("Writing PNG file…")
            QApplication.processEvents()

            def _start(worker: PreviewExportWorker) -> None:
                worker.save_png(image, path)

            self._remember_export_dir(path, snapshot=True)
            self._run_export_async(
                _start, "Snapshot saved", "Snapshot failed", progress=progress
            )
        except Exception:
            self._close_progress(progress)
            self._set_export_busy(False)
            raise

    def _export_mesh(self) -> None:
        if self._export_in_progress():
            return
        if not self._preview.has_exportable_geometry():
            QMessageBox.warning(
                self,
                "No mesh",
                "No exportable surface mesh yet.\n\n"
                "Build an Isosurface preview first (point clouds cannot be "
                "exported as a single surface file).",
            )
            return
        path, selected_filter = QFileDialog.getSaveFileName(
            self,
            "Export 3D Model",
            self._default_mesh_path(),
            "STL mesh (*.stl);;OBJ mesh (*.obj);;VTK polydata (*.vtp);;"
            "PLY mesh (*.ply);;VTK legacy (*.vtk);;All files (*)",
        )
        if not path:
            return
        ext_map = {
            "STL mesh (*.stl)": ".stl",
            "OBJ mesh (*.obj)": ".obj",
            "VTK polydata (*.vtp)": ".vtp",
            "PLY mesh (*.ply)": ".ply",
            "VTK legacy (*.vtk)": ".vtk",
        }
        ext = ext_map.get(selected_filter, "")
        if ext and not path.lower().endswith(ext):
            path += ext

        progress = open_export_progress(
            self, "Export 3D model", "Preparing mesh data…"
        )
        self._set_export_busy(True)
        try:
            meshes = self._preview.copy_export_meshes()
            if not meshes:
                self._close_progress(progress)
                self._set_export_busy(False)
                QMessageBox.warning(self, "Export failed", "No mesh data to export.")
                return

            progress.setLabelText("Merging surfaces and writing file…")
            QApplication.processEvents()

            def _start(worker: PreviewExportWorker) -> None:
                worker.export_mesh(meshes, path)

            self._remember_export_dir(path, snapshot=False)
            self._run_export_async(
                _start, "Model exported", "Export failed", progress=progress
            )
        except Exception:
            self._close_progress(progress)
            self._set_export_busy(False)
            raise

    # ------------------------------------------------------------------
    # Window events
    # ------------------------------------------------------------------
    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        # Don't actually exit when the user clicks 'X' — parent decides lifecycle.
        # Hide and tell the parent so it can update its proxy state.
        event.ignore()
        self.hide()
        self.user_closed.emit()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key_Home:
            self.reset_orientation()
            event.accept()
            return
        super().keyPressEvent(event)
