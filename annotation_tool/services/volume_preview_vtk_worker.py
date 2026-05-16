"""
Background thread: CPU-heavy VTK filters (contour, mesh ops) off the GUI thread.
OpenGL / QtInteractor drawing stays on the main thread in VolumePreview3D.
"""
from typing import Callable, Optional, Tuple

from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

from .volume_preview_builder import VolumePreviewResult
from .volume_vtk_prepare import (
    PreviewPrepareCancelled,
    build_preview_payload,
)


class VolumePreviewVTKWorker(QObject):
    """Runs build_preview_payload on a QThread (no plotter, no OpenGL)."""

    prepare_done = pyqtSignal(object, int)  # PreviewVTKPayload or None, generation
    failed = pyqtSignal(str)
    stage = pyqtSignal(str)
    completed = pyqtSignal()

    def __init__(self) -> None:
        super().__init__()
        self._result: Optional[VolumePreviewResult] = None
        self._current_z: int = 0
        self._generation: int = 0
        self._cancelled: bool = False
        self._external_cancel: Callable[[], bool] = lambda: False

    def configure(
        self,
        result: VolumePreviewResult,
        current_z: int,
        generation: int,
        is_cancelled: Callable[[], bool],
    ) -> None:
        self._result = result
        self._current_z = current_z
        self._generation = generation
        self._external_cancel = is_cancelled

    def _should_cancel(self) -> bool:
        return self._cancelled or self._external_cancel()

    @pyqtSlot()
    def run(self) -> None:
        self._cancelled = False
        if self._result is None:
            self.completed.emit()
            return
        gen = self._generation
        try:
            if self._should_cancel():
                self.prepare_done.emit(None, gen)
                return
            self.stage.emit(
                "3D display: contouring & triangulating (CPU thread)…\n"
                "Isosurfaces for large volumes can take several minutes."
            )
            payload = build_preview_payload(
                self._result,
                self._current_z,
                gen,
                should_cancel=self._should_cancel,
            )
            if self._should_cancel():
                self.prepare_done.emit(None, gen)
            else:
                self.prepare_done.emit(payload, gen)
        except PreviewPrepareCancelled:
            self.prepare_done.emit(None, gen)
        except Exception as e:
            if not self._should_cancel():
                self.failed.emit(str(e))
        finally:
            self.completed.emit()

    @pyqtSlot()
    def request_cancel(self) -> None:
        self._cancelled = True


def start_vtk_prepare_thread(
    worker: VolumePreviewVTKWorker,
    parent: Optional[QObject] = None,
) -> Tuple[QThread, VolumePreviewVTKWorker]:
    """Create QThread, move worker, start prepare run."""
    thread = QThread(parent)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    worker.completed.connect(thread.quit)
    thread.start()
    return thread, worker
