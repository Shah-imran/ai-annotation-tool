"""
Background worker to build 3D volume previews without blocking the UI.
"""
from typing import List, Optional, Tuple

from PyQt5.QtCore import QObject, QThread, pyqtSignal, pyqtSlot

from .volume_preview_builder import PreviewBuildCancelled, build_preview


class VolumePreviewWorker(QObject):
    """Builds preview data on a QThread (TIFF IO + numpy only — no VTK)."""

    finished = pyqtSignal(object)  # VolumePreviewResult
    failed = pyqtSignal(str)
    progress = pyqtSignal(str)
    completed = pyqtSignal()  # always emitted so the QThread can exit

    def __init__(self):
        super().__init__()
        self._cancelled = False
        self._slice_paths: List[str] = []
        self._source_z_indices: List[int] = []
        self._full_shape_zyx: Tuple[int, int, int] = (0, 0, 0)
        self._spacing_xyz: Tuple[float, float, float] = (1.0, 1.0, 1.0)
        self._mode: str = "mip"
        self._window_center: float = 0.0
        self._window_width: float = 1.0
        self._use_window_level: bool = False
        self._point_threshold: int = 25
        self._include_mask: bool = True
        self._preview_level: int = 5
        self._native_full_volume: bool = False
        self._stride_zyx: Optional[Tuple[int, int, int]] = None
        self._label_path: str = ""
        self._label_shape: Tuple[int, int, int] = (0, 0, 0)

    def configure(
        self,
        slice_paths: List[str],
        spacing_xyz: Tuple[float, float, float],
        mode: str,
        window_center: float,
        window_width: float,
        use_window_level: bool,
        point_threshold: int = 25,
        include_mask: bool = True,
        preview_level: int = 5,
        source_z_indices: Optional[List[int]] = None,
        full_shape_zyx: Optional[Tuple[int, int, int]] = None,
        native_full_volume: bool = False,
        label_path: str = "",
        label_shape: Tuple[int, int, int] = (0, 0, 0),
        stride_zyx: Optional[Tuple[int, int, int]] = None,
    ) -> None:
        self._slice_paths = slice_paths
        self._spacing_xyz = spacing_xyz
        self._mode = mode
        self._window_center = window_center
        self._window_width = window_width
        self._use_window_level = use_window_level
        self._point_threshold = point_threshold
        self._include_mask = include_mask
        self._preview_level = max(1, min(5, int(preview_level)))
        self._native_full_volume = bool(native_full_volume)
        self._source_z_indices = (
            list(source_z_indices)
            if source_z_indices is not None
            else list(range(len(slice_paths)))
        )
        self._full_shape_zyx = full_shape_zyx or (len(slice_paths), 0, 0)
        self._label_path = label_path
        self._label_shape = label_shape
        self._stride_zyx = stride_zyx

    @pyqtSlot()
    def request_cancel(self) -> None:
        self._cancelled = True

    def _should_cancel(self) -> bool:
        return self._cancelled

    @pyqtSlot()
    def run_build(self) -> None:
        """Entry point connected to QThread.started (runs off the UI thread)."""
        self._cancelled = False
        try:
            if not self._slice_paths:
                self.failed.emit("No slices to preview")
                return

            def on_progress(done: int, total: int) -> None:
                if self._should_cancel():
                    return
                self.progress.emit(f"Loading slices… {done}/{total}")

            label_path = self._label_path if self._include_mask else ""
            label_shape = self._label_shape if self._include_mask else (0, 0, 0)

            result = build_preview(
                self._slice_paths,
                self._spacing_xyz,
                mode=self._mode,
                window_center=self._window_center,
                window_width=self._window_width,
                use_window_level=self._use_window_level,
                label_path=label_path,
                label_shape=label_shape,
                include_mask=self._include_mask and bool(label_path),
                preview_level=self._preview_level,
                native_full_volume=self._native_full_volume,
                stride_zyx=self._stride_zyx,
                source_z_indices=self._source_z_indices,
                full_shape_zyx=self._full_shape_zyx,
                progress_callback=on_progress,
                should_cancel=self._should_cancel,
            )
            if self._should_cancel():
                return
            self.finished.emit(result)
        except PreviewBuildCancelled:
            pass
        except MemoryError:
            if not self._should_cancel():
                self.failed.emit(
                    "Out of memory — disable Native resolution, narrow slice range, "
                    "or increase Z / XY stride on the preview panel."
                )
        except Exception as e:
            if not self._should_cancel():
                self.failed.emit(str(e))
        finally:
            self.completed.emit()


def start_preview_build_thread(
    worker: VolumePreviewWorker,
    parent: Optional[QObject] = None,
) -> Tuple[QThread, VolumePreviewWorker]:
    """Create a QThread, move worker onto it, and start the build."""
    thread = QThread(parent)
    worker.moveToThread(thread)
    thread.started.connect(worker.run_build)
    worker.completed.connect(thread.quit)
    thread.start()
    return thread, worker
