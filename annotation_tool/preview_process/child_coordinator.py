"""
Driver inside the child process: runs the slice-loading worker, hands the
result to the VolumePreview3D widget, and forwards stage/result events to
the parent.
"""
from __future__ import annotations

from typing import Any, Optional, Tuple

from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal

from ..services.volume_preview_builder import VolumePreviewResult
from ..services.volume_preview_worker import (
    VolumePreviewWorker,
    start_preview_build_thread,
)
from ..views.volume_preview_3d import VolumePreview3D


def _mode_label(mode: str) -> str:
    return {
        "solid": "Solid volume",
        "isosurface": "Isosurface",
        "isosurface_lit": "Isosurface (opaque)",
        "mip": "Soft volume / MIP",
        "point_cloud": "Point cloud",
    }.get(mode, mode)


def _format_status(result: VolumePreviewResult) -> str:
    n_pts = len(result.points_xyz) if result.points_xyz is not None else 0
    z_full, _, _ = result.shape_zyx
    z_ds = result.intensity_u8.shape[0] if result.intensity_u8.ndim >= 1 else 0
    stz, sty, stx = result.stride_zyx
    mode = _mode_label(result.mode)
    level = result.preview_level
    z_lo, z_hi = result.preview_z_range
    range_limited = z_lo > 0 or z_hi < z_full - 1
    if range_limited:
        z_line = f"Range slices {z_lo + 1}–{z_hi + 1} of {z_full}"
    elif stz <= 1 and z_ds >= (z_hi - z_lo + 1):
        z_line = f"All {z_hi - z_lo + 1} slices in range"
    else:
        z_line = f"{z_ds} slabs in range (Z stride {stz})"
    _, h_full, w_full = result.shape_zyx
    h_ds = result.intensity_u8.shape[1] if result.intensity_u8.ndim >= 2 else 0
    w_ds = result.intensity_u8.shape[2] if result.intensity_u8.ndim >= 3 else 0
    if sty <= 1 and stx <= 1:
        xy_line = "full XY resolution"
    else:
        xy_line = (
            f"XY downsampled {sty}×{stx} ({w_full}→{w_ds} px wide, saves RAM)"
        )
    if result.native_resolution:
        level_line = f"Native resolution · stride {stz}×{sty}×{stx}"
        gb = result.intensity_u8.nbytes / (1024.0**3)
        native_note = f"\nPreview buffer ≈ {gb:.2f} GiB (uint8)"
    else:
        level_line = f"Stride Z={stz} · XY={sty}×{stx}"
        if result.mode == "point_cloud":
            level_line += f" · point sampling {level}/5"
        native_note = ""
    return (
        f"{mode} ready · {level_line}\n{z_line}\n{xy_line}{native_note}"
        + (f" · {n_pts:,} points" if n_pts else "")
    )


class ChildPreviewCoordinator(QObject):
    """Owns the slice worker and the VolumePreview3D widget within the child."""

    stage = pyqtSignal(str)  # status text update
    started = pyqtSignal(int)  # generation
    finished = pyqtSignal(int, str)  # generation, final status text
    failed = pyqtSignal(int, str)  # generation, error text

    def __init__(self, preview: VolumePreview3D, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._preview = preview
        self._preview_thread: Optional[QThread] = None
        self._preview_worker: Optional[VolumePreviewWorker] = None
        self._generation: int = 0
        self._current_z: int = 0
        self._last_result: Optional[VolumePreviewResult] = None

        self._preview.render_finished.connect(self._on_render_finished, Qt.QueuedConnection)
        self._preview.render_stage.connect(self._forward_stage, Qt.QueuedConnection)

    @property
    def current_generation(self) -> int:
        return self._generation

    def _forward_stage(self, text: str) -> None:
        self.stage.emit(text)

    def cancel(self) -> None:
        if self._preview_worker is not None:
            self._preview_worker.request_cancel()
        self._preview.cancel_render()
        self._last_result = None

    def clear_scene(self) -> None:
        self.cancel()
        self._preview.clear()

    def reset_view(self) -> None:
        self._preview.reset_orientation()

    def set_current_slice(self, z: int) -> None:
        self._current_z = int(z)
        self._preview.set_current_slice(int(z))

    def start_build(self, generation: int, params: dict) -> None:
        self.cancel()
        self._generation = int(generation)
        self.started.emit(self._generation)

        slice_paths = list(params.get("slice_paths") or [])
        if not slice_paths:
            self.failed.emit(self._generation, "No slices in preview range")
            return

        spacing_xyz = tuple(float(v) for v in (params.get("spacing_xyz") or (1.0, 1.0, 1.0)))
        mode = str(params.get("mode") or "isosurface_lit")
        window_center = float(params.get("window_center", 0.0))
        window_width = float(params.get("window_width", 1.0))
        use_window_level = bool(params.get("use_window_level", False))
        include_mask = bool(params.get("include_mask", False))
        preview_level = int(params.get("preview_level", 5))
        native_full_volume = bool(params.get("native_full_volume", False))
        source_z_indices = list(int(i) for i in (params.get("source_z_indices") or []))
        full_shape_zyx = tuple(int(v) for v in (params.get("full_shape_zyx") or (0, 0, 0)))
        label_path = str(params.get("label_path") or "")
        label_shape = tuple(int(v) for v in (params.get("label_shape") or (0, 0, 0)))
        stride_raw = params.get("stride_zyx")
        stride_zyx: Optional[Tuple[int, int, int]] = (
            tuple(int(v) for v in stride_raw) if stride_raw else None
        )
        self._current_z = int(params.get("current_z", 0))

        point_size = float(params.get("point_size", 3.0))
        point_threshold_raw = params.get("point_threshold_override")
        point_threshold_override = (
            int(point_threshold_raw) if point_threshold_raw is not None else None
        )
        iso_color = str(params.get("iso_color") or "#dcdcdc")

        gen = self._generation

        worker = VolumePreviewWorker()
        worker.configure(
            slice_paths,
            spacing_xyz,
            mode,
            window_center,
            window_width,
            use_window_level,
            include_mask=include_mask,
            preview_level=preview_level,
            native_full_volume=native_full_volume,
            source_z_indices=source_z_indices,
            full_shape_zyx=full_shape_zyx,
            label_path=label_path,
            label_shape=label_shape,
            stride_zyx=stride_zyx,
            point_size=point_size,
            point_threshold_override=point_threshold_override,
            iso_color=iso_color,
        )

        def _progress(text: str) -> None:
            self.stage.emit(text)

        def _on_finished(result: VolumePreviewResult, gen_=gen) -> None:
            if gen_ != self._generation:
                return
            self._last_result = result
            self.stage.emit(
                "Slice stack ready — preparing 3D display…\n"
                "Next: mesh build (CPU thread) → GPU draw (chunked)."
            )
            self._preview.begin_set_preview(result, self._current_z, gen_)

        def _on_failed(message: str, gen_=gen) -> None:
            if gen_ != self._generation:
                return
            self.failed.emit(gen_, message)
            self._last_result = None

        worker.progress.connect(_progress, Qt.QueuedConnection)
        worker.finished.connect(_on_finished, Qt.QueuedConnection)
        worker.failed.connect(_on_failed, Qt.QueuedConnection)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)

        self._preview_worker = worker
        self._preview_thread, _ = start_preview_build_thread(worker, parent=self)
        self._preview_thread.finished.connect(self._on_worker_thread_finished)
        self._preview_thread.finished.connect(self._preview_thread.deleteLater)

    def _on_worker_thread_finished(self) -> None:
        self._preview_thread = None
        self._preview_worker = None

    def _on_render_finished(self, gen: int) -> None:
        if gen != self._generation:
            return
        result = self._last_result
        self._last_result = None
        text = _format_status(result) if result is not None else "3D preview ready."
        self.finished.emit(gen, text)
