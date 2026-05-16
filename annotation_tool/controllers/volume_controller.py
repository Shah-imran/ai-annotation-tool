"""
Controller for 3D volume voxel annotation workflow.
"""
import os
from typing import List, Optional, Tuple

import numpy as np
from PyQt5.QtCore import QObject, Qt, QThread, pyqtSignal
from PyQt5.QtWidgets import QFileDialog

from ..models.label_volume_model import LabelVolumeModel
from ..models.volume_model import VolumeModel
from ..services.volume_io import (
    load_segmentation_nifti,
    save_segmentation_nifti,
    save_volume_meta,
)
from ..services.volume_preview_worker import VolumePreviewWorker, start_preview_build_thread
from ..views.volume_workspace import VolumeWorkspace


class VolumeController(QObject):
    status_message = pyqtSignal(str)

    def __init__(
        self,
        volume_model: VolumeModel,
        label_model: LabelVolumeModel,
        workspace: VolumeWorkspace,
        parent_window,
        get_annotations_dir,
        get_voxel_spacing,
        get_class_names,
        get_last_scan_dir=None,
    ):
        super().__init__()
        self._volume_model = volume_model
        self._label_model = label_model
        self._workspace = workspace
        self._parent = parent_window
        self._get_annotations_dir = get_annotations_dir
        self._get_voxel_spacing = get_voxel_spacing
        self._get_class_names = get_class_names
        self._get_last_scan_dir = get_last_scan_dir

        self._stroke_z: Optional[int] = None
        self._stroke_before_slice: Optional[np.ndarray] = None
        self._stroke_bounds: Optional[Tuple[int, int, int, int]] = None

        self._canvas = workspace.slice_canvas
        self._panel = workspace.control_panel
        self._preview = workspace.preview_3d
        self._preview_thread: Optional[QThread] = None
        self._preview_worker: Optional[VolumePreviewWorker] = None
        self._pending_preview_result = None
        self._preview_generation = 0
        self._vtk_render_generation = 0
        self._last_status_result = None

        self._connect_signals()
        self._refresh_class_list()

    def _connect_signals(self):
        self._volume_model.slice_changed.connect(self._on_slice_changed)
        self._volume_model.scan_loaded.connect(self._on_scan_loaded)
        self._label_model.labels_changed.connect(self._on_labels_changed)

        self._panel.load_scan_requested.connect(self._load_scan_dialog)
        self._panel.save_requested.connect(self.save_labels)
        self._panel.export_nifti_requested.connect(self.export_nifti)
        self._panel.load_seg_requested.connect(self.load_nifti_dialog)
        self._panel.previous_slice_requested.connect(self._previous_slice)
        self._panel.next_slice_requested.connect(self._next_slice)
        self._panel.slice_index_requested.connect(self._volume_model.set_current_index)
        self._panel.class_changed.connect(self._on_class_changed)
        self._panel.brush_radius_changed.connect(self._canvas.set_brush_radius)
        self._panel.erase_mode_changed.connect(self._canvas.set_erase_mode)
        self._panel.window_center_changed.connect(self._on_window_center_changed)
        self._panel.window_width_changed.connect(self._on_window_width_changed)
        self._panel.reset_window_requested.connect(self._reset_window)

        self._canvas.stroke_started.connect(self._on_stroke_started)
        self._canvas.stroke_segment.connect(self._on_stroke_segment)
        self._canvas.stroke_ended.connect(self._on_stroke_ended)

        self._panel.preview_rebuild_requested.connect(self._start_preview_build)
        self._panel.preview_stop_requested.connect(self._stop_preview_requested)
        self._panel.preview_reset_view_requested.connect(self._preview.reset_orientation)
        self._preview.render_finished.connect(self._on_vtk_render_finished, Qt.QueuedConnection)
        self._preview.render_stage.connect(self._panel.set_preview_status, Qt.QueuedConnection)

    def _refresh_class_list(self):
        names = self._get_class_names()
        if names:
            self._label_model.set_class_names(names)
        self._panel.update_class_list(self._label_model.class_names)

    def _label_memmap_path(self) -> str:
        scan_id = self._volume_model.scan_id or "scan"
        return os.path.join(self._get_annotations_dir(), f"{scan_id}_labels.dat")

    def _seg_nifti_path(self) -> str:
        scan_id = self._volume_model.scan_id or "scan"
        return os.path.join(self._get_annotations_dir(), f"{scan_id}_seg.nii.gz")

    def _meta_path(self) -> str:
        scan_id = self._volume_model.scan_id or "scan"
        return os.path.join(self._get_annotations_dir(), f"{scan_id}_meta.json")

    def _load_scan_dialog(self):
        start = self._volume_model.scan_dir or ""
        if not start and self._get_last_scan_dir:
            start = self._get_last_scan_dir() or ""
        path = QFileDialog.getExistingDirectory(
            self._parent, "Select Volume Scan Folder", start
        )
        if path:
            self.load_scan(path)

    def load_scan(self, scan_dir: str) -> bool:
        if not self._volume_model.load_scan(scan_dir):
            self.status_message.emit("Failed to load scan: no slice_*.tif files found")
            return False

        shape = self._volume_model.shape_zyx
        label_path = self._label_memmap_path()
        self._label_model.attach_volume(shape, label_path)

        seg_path = self._seg_nifti_path()
        if os.path.isfile(seg_path):
            try:
                data = load_segmentation_nifti(seg_path)
                if data.shape == shape:
                    self._label_model.load_from_array(data, label_path)
                    self.status_message.emit(f"Loaded existing segmentation: {os.path.basename(seg_path)}")
            except Exception as e:
                print(f"Could not load seg: {e}")

        self._refresh_class_list()
        self._canvas.set_current_class_id(self._label_model.current_class_id)
        self._panel.set_scan_info(self._volume_model.scan_id, self._volume_model.num_slices)
        self._panel.set_scan_slice_count(self._volume_model.num_slices)
        self._panel.set_window_sliders(
            self._volume_model.window_center, self._volume_model.window_width
        )
        self._refresh_canvas()
        if self._preview.is_available:
            self._panel.set_preview_status(
                "Press Start preview when you are ready to build the 3D view."
            )
        else:
            self._panel.set_preview_status(
                "Install PyVista for 3D preview: pip install pyvista pyvistaqt"
            )
        self.status_message.emit(
            f"Loaded scan {self._volume_model.scan_id} ({shape[0]} slices)"
        )
        return True

    def _on_scan_loaded(self, scan_id: str):
        self._panel.set_scan_info(scan_id, self._volume_model.num_slices)
        self._panel.set_scan_slice_count(self._volume_model.num_slices)

    def _on_slice_changed(self, index: int, total: int):
        self._panel.update_slice_counter(index, total)
        self._refresh_canvas()
        self._preview.set_current_slice(index)

    def _on_labels_changed(self):
        """Redraw overlay only; avoid reloading TIFF from disk."""
        if self._volume_model.num_slices == 0:
            return
        z = self._volume_model.current_index
        labels = self._label_model.get_slice_labels(z)
        self._canvas.update_label_overlay(labels)

    def _refresh_canvas(self):
        if self._volume_model.num_slices == 0:
            return
        z = self._volume_model.current_index
        sl = self._volume_model.get_slice_u16(z)
        labels = self._label_model.get_slice_labels(z)
        self._canvas.set_slice_data(
            sl,
            labels,
            z,
            self._volume_model.window_center,
            self._volume_model.window_width,
            self._volume_model.use_window_level,
        )

    def _on_stroke_started(self, z: int) -> None:
        """Snapshot slice labels before the first paint point of this stroke."""
        if self._volume_model.num_slices == 0:
            return
        self._stroke_z = z
        self._stroke_before_slice = np.array(self._label_model.get_slice_labels(z), copy=True)
        self._stroke_bounds = None

    def _expand_stroke_bounds(
        self, points: List[Tuple[int, int]], radius: int
    ) -> None:
        if not points:
            return
        h, w = self._volume_model.shape_zyx[1], self._volume_model.shape_zyx[2]
        ys = [p[0] for p in points]
        xs = [p[1] for p in points]
        y0 = max(0, min(ys) - radius)
        y1 = min(h, max(ys) + radius + 1)
        x0 = max(0, min(xs) - radius)
        x1 = min(w, max(xs) + radius + 1)
        if self._stroke_bounds is None:
            self._stroke_bounds = (y0, y1, x0, x1)
        else:
            by0, by1, bx0, bx1 = self._stroke_bounds
            self._stroke_bounds = (
                min(by0, y0),
                max(by1, y1),
                min(bx0, x0),
                max(bx1, x1),
            )

    def _on_stroke_segment(self, z: int, points, radius: int, erase: bool):
        """Apply brush while dragging — update overlay only (no TIFF reload)."""
        self._expand_stroke_bounds(points, radius)
        class_id = 0 if erase else self._label_model.current_class_id
        self._label_model.paint_stroke(
            z, points, radius, class_id, erase=erase, emit_changed=False
        )
        self._canvas.update_label_overlay(self._label_model.get_slice_labels(z))

    def _on_stroke_ended(self):
        """Commit stroke to undo stack and refresh overlay."""
        if self._volume_model.num_slices == 0:
            return
        z = self._volume_model.current_index
        self._label_model.flush()
        self._canvas.update_label_overlay(self._label_model.get_slice_labels(z))

        if (
            self._stroke_before_slice is not None
            and self._stroke_z is not None
            and self._stroke_bounds is not None
        ):
            y0, y1, x0, x1 = self._stroke_bounds
            before_patch = self._stroke_before_slice[y0:y1, x0:x1]
            after_patch = np.array(
                self._label_model.get_slice_labels(self._stroke_z)[y0:y1, x0:x1],
                copy=True,
            )
            self._label_model.push_paint_stroke_undo(
                self._stroke_z, y0, y1, x0, x1, before_patch, after_patch
            )

        self._stroke_z = None
        self._stroke_before_slice = None
        self._stroke_bounds = None

    def _stop_preview_requested(self) -> None:
        """Cancel background slice load and/or abort queued VTK render."""
        self._preview_generation += 1
        self._vtk_render_generation += 1
        self._cancel_preview_build()
        self._pending_preview_result = None
        self._last_status_result = None
        self._preview.cancel_render()
        self._panel.set_preview_busy(False)
        self._panel.set_preview_status("Preview stopped.")
        self.status_message.emit("3D preview stopped")

    def _preview_build_inputs(
        self,
    ) -> Tuple[List[str], List[int], Tuple[int, int, int], Tuple[int, int]]:
        """
        Slice paths and full-volume Z indices for the 3D preview.

        Returns (paths, z_indices, full_shape_zyx, preview_z_range inclusive).
        """
        paths = self._volume_model.slice_paths
        full_shape = self._volume_model.shape_zyx
        n = len(paths)
        if n == 0:
            return [], [], full_shape, (0, 0)

        if self._panel.is_preview_range_limited():
            z0, z1 = self._panel.get_preview_z_range_0based()
            z0 = max(0, min(z0, n - 1))
            z1 = max(z0, min(z1, n - 1))
        else:
            z0, z1 = 0, n - 1

        indices = list(range(z0, z1 + 1))
        sub_paths = [paths[i] for i in indices]
        return sub_paths, indices, full_shape, (z0, z1)

    def _cancel_preview_build(self) -> None:
        if self._preview_worker is not None:
            self._preview_worker.request_cancel()

    def _start_preview_build(self) -> None:
        if self._volume_model.num_slices == 0 or not self._preview.is_available:
            return

        self._cancel_preview_build()
        self._preview_generation += 1
        self._vtk_render_generation += 1
        self._last_status_result = None
        self._preview.cancel_render()
        build_generation = self._preview_generation

        spacing = self._get_voxel_spacing()
        if len(spacing) >= 3:
            spacing_xyz = (float(spacing[0]), float(spacing[1]), float(spacing[2]))
        else:
            spacing_xyz = (1.0, 1.0, 1.0)

        include_mask = self._panel.preview_mask_check.isChecked()
        label_path = self._label_memmap_path() if include_mask else ""
        label_shape = self._volume_model.shape_zyx

        self._panel.set_preview_busy(True)
        self._panel.set_preview_status(
            "Loading slice stack for 3D…\n"
            "When slices finish, meshes build on a background CPU thread, then the GPU draws in steps."
        )

        preview_paths, z_indices, full_shape, z_range = self._preview_build_inputs()
        if not preview_paths:
            self._panel.set_preview_status("No slices in preview range")
            self._panel.set_preview_busy(False)
            return

        stride_zyx = None
        if not self._panel.is_preview_native_resolution():
            sz = self._panel.get_preview_stride_z()
            sxy = self._panel.get_preview_stride_xy()
            stride_zyx = (sz, sxy, sxy)

        worker = VolumePreviewWorker()
        worker.configure(
            preview_paths,
            spacing_xyz,
            self._panel.get_preview_mode(),
            self._volume_model.window_center,
            self._volume_model.window_width,
            self._volume_model.use_window_level,
            include_mask=include_mask,
            preview_level=self._panel.get_preview_level(),
            native_full_volume=self._panel.is_preview_native_resolution(),
            source_z_indices=z_indices,
            full_shape_zyx=full_shape,
            label_path=label_path,
            label_shape=label_shape,
            stride_zyx=stride_zyx,
        )
        worker.progress.connect(
            self._panel.set_preview_status, Qt.QueuedConnection
        )
        worker.finished.connect(
            lambda result, gen=build_generation: self._on_preview_data_ready(result, gen),
            Qt.QueuedConnection,
        )
        worker.failed.connect(self._on_preview_failed, Qt.QueuedConnection)
        worker.finished.connect(worker.deleteLater)
        worker.failed.connect(worker.deleteLater)

        self._preview_worker = worker
        self._preview_thread, _ = start_preview_build_thread(worker, parent=self)
        self._preview_thread.finished.connect(self._on_preview_thread_finished)
        self._preview_thread.finished.connect(self._preview_thread.deleteLater)

    def _on_preview_data_ready(self, result, build_generation: int) -> None:
        """Begin VTK draw (deferred + chunked) on the UI thread after worker data is ready."""
        if build_generation != self._preview_generation:
            return
        self._last_status_result = result
        self._panel.set_preview_status(
            "Slice stack ready — preparing 3D display…\n"
            "Next: mesh build (CPU thread) → GPU draw (chunked on main thread)."
        )
        gen = self._vtk_render_generation
        z = self._volume_model.current_index
        self._preview.begin_set_preview(result, z, gen)

    def _on_vtk_render_finished(self, gen: int) -> None:
        if gen != self._vtk_render_generation:
            return
        result = self._last_status_result
        self._last_status_result = None
        if result is None:
            self._panel.set_preview_busy(False)
            return
        self._panel.set_preview_status(self._format_preview_status(result))
        self.status_message.emit("3D preview updated")
        self._panel.set_preview_busy(False)

    def _format_preview_status(self, result) -> str:
        n_pts = len(result.points_xyz) if result.points_xyz is not None else 0
        z_full, _, _ = result.shape_zyx
        z_ds = result.intensity_u8.shape[0]
        stz, sty, stx = result.stride_zyx
        mode_labels = {
            "solid": "Solid volume",
            "isosurface": "Isosurface",
            "mip": "Soft volume",
            "point_cloud": "Point cloud",
        }
        mode = mode_labels.get(result.mode, result.mode)
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
                f"XY downsampled {sty}×{stx} "
                f"({w_full}→{w_ds} px wide, saves RAM)"
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
            + "\nDrag rotate · scroll zoom · right-drag pan"
        )

    def _on_preview_failed(self, message: str) -> None:
        self._last_status_result = None
        self._panel.set_preview_status(f"Preview failed: {message}")
        self.status_message.emit(f"3D preview failed: {message}")
        self._panel.set_preview_busy(False)

    def _on_preview_thread_finished(self) -> None:
        self._preview_thread = None
        self._preview_worker = None

    def undo(self) -> bool:
        ok = self._label_model.undo()
        return ok

    def redo(self) -> bool:
        ok = self._label_model.redo()
        return ok

    def can_undo(self) -> bool:
        return self._label_model.can_undo()

    def can_redo(self) -> bool:
        return self._label_model.can_redo()

    def _on_class_changed(self, combo_index: int):
        class_id = self._panel.class_combo.itemData(combo_index)
        if class_id is not None:
            class_id = int(class_id)
            self._label_model.set_current_class_id(class_id)
            self._canvas.set_current_class_id(class_id)

    def _on_window_center_changed(self, center: float):
        self._volume_model.set_window_level(center, self._volume_model.window_width)
        self._refresh_canvas()

    def _on_window_width_changed(self, width: float):
        self._volume_model.set_window_level(self._volume_model.window_center, width)
        self._refresh_canvas()

    def _reset_window(self):
        self._volume_model.reset_window_level_for_current()
        self._panel.set_window_sliders(
            self._volume_model.window_center, self._volume_model.window_width
        )
        self._refresh_canvas()

    def _previous_slice(self):
        if not self._volume_model.previous_slice():
            self.status_message.emit("Already at first slice")

    def _next_slice(self):
        if not self._volume_model.next_slice():
            self.status_message.emit("Already at last slice")

    def save_labels(self) -> bool:
        if self._volume_model.num_slices == 0:
            return False
        self._label_model.flush()
        save_volume_meta(
            self._meta_path(),
            self._volume_model.scan_id,
            self._volume_model.scan_dir,
            self._volume_model.shape_zyx,
            self._label_model.class_names,
            self._get_voxel_spacing(),
        )
        self.status_message.emit("Labels saved (memmap + metadata)")
        return True

    def export_nifti(self) -> bool:
        if self._volume_model.num_slices == 0:
            return False
        path, _ = QFileDialog.getSaveFileName(
            self._parent,
            "Export NIfTI Segmentation",
            self._seg_nifti_path(),
            "NIfTI (*.nii.gz);;All files (*)",
        )
        if not path:
            return False
        try:
            self._label_model.flush()
            save_segmentation_nifti(
                self._label_model.as_array(),
                path,
                self._get_voxel_spacing(),
            )
            save_volume_meta(
                os.path.splitext(path)[0].replace("_seg", "") + "_meta.json"
                if path.endswith("_seg.nii.gz")
                else self._meta_path(),
                self._volume_model.scan_id,
                self._volume_model.scan_dir,
                self._volume_model.shape_zyx,
                self._label_model.class_names,
                self._get_voxel_spacing(),
            )
            self.status_message.emit(f"Exported {os.path.basename(path)}")
            return True
        except Exception as e:
            self.status_message.emit(f"Export failed: {e}")
            return False

    def load_nifti_dialog(self):
        path, _ = QFileDialog.getOpenFileName(
            self._parent,
            "Load NIfTI Segmentation",
            self._get_annotations_dir(),
            "NIfTI (*.nii.gz *.nii);;All files (*)",
        )
        if path:
            self.load_nifti(path)

    def load_nifti(self, path: str) -> bool:
        if self._volume_model.num_slices == 0:
            self.status_message.emit("Load a scan first")
            return False
        try:
            data = load_segmentation_nifti(path)
            if data.shape != self._volume_model.shape_zyx:
                self.status_message.emit(
                    f"Shape mismatch: seg {data.shape} vs volume {self._volume_model.shape_zyx}"
                )
                return False
            self._label_model.load_from_array(data, self._label_memmap_path())
            self._refresh_canvas()
            self.status_message.emit(f"Loaded {os.path.basename(path)}")
            return True
        except Exception as e:
            self.status_message.emit(f"Load failed: {e}")
            return False

    def handle_key(self, key: str) -> bool:
        """Return True if key was handled."""
        if key.upper() == "A":
            self._previous_slice()
            return True
        if key.upper() == "D":
            self._next_slice()
            return True
        return False
