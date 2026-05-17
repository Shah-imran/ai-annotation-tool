"""
Embedded PyVista 3D preview for volume annotation (recon-style solid / isosurface / MIP).

CPU mesh prep runs on a QThread; GPU attach is chunked with QTimer so the UI stays responsive.
"""
from typing import Any, List, Optional, Tuple

import numpy as np
from PyQt5.QtCore import QThread, QTimer, Qt, pyqtSignal
from PyQt5.QtWidgets import (
    QLabel,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

try:
    import pyvista as pv
    from pyvistaqt import QtInteractor

    pv.set_plot_theme("dark")
    HAS_PYVISTA = True
except ImportError:
    HAS_PYVISTA = False

from ..services.volume_preview_builder import VolumePreviewResult
from ..services.volume_preview_vtk_worker import (
    VolumePreviewVTKWorker,
    start_vtk_prepare_thread,
)
from ..services.volume_vtk_prepare import PreviewVTKPayload
from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class VolumePreview3D(QWidget):
    """3D orbit view: solid volume, isosurface, soft MIP, or point cloud."""

    slice_clicked = pyqtSignal(int)
    render_finished = pyqtSignal(int)
    render_stage = pyqtSignal(str)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumHeight(200)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setFocusPolicy(Qt.StrongFocus)

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._plotter = None
        self._placeholder: Optional[QLabel] = None
        self._result: Optional[VolumePreviewResult] = None
        self._current_z = 0
        self._plane_actor = None
        self._cloud_actor = None
        self._mask_actor = None
        self._volume_actor = None
        self._surface_actor = None
        self._axes_actor = None
        # Meshes kept for export (STL/OBJ/VTK/PLY) after the preview is built.
        self._export_meshes: List[Any] = []

        self._kickoff_timer = QTimer(self)
        self._kickoff_timer.setSingleShot(True)
        self._kickoff_timer.timeout.connect(self._start_vtk_prepare_thread)
        self._pending_render: Optional[Tuple[VolumePreviewResult, int, int]] = None
        self._render_cancelled = False
        self._expected_gen: int = 0

        self._prepare_thread: Optional[QThread] = None
        self._prepare_worker: Optional[VolumePreviewVTKWorker] = None

        self._chunk_timer = QTimer(self)
        self._chunk_timer.setSingleShot(True)
        self._chunk_timer.timeout.connect(self._apply_next_chunk)
        self._apply_queue: List[Tuple[Any, ...]] = []
        self._apply_i: int = 0
        self._chunk_payload: Optional[PreviewVTKPayload] = None
        self._chunk_gen: int = 0

        self._busy_overlay: Optional[QWidget] = None
        self._busy_title: Optional[QLabel] = None
        self._busy_detail: Optional[QLabel] = None
        self._spinner_timer = QTimer(self)
        self._spinner_timer.timeout.connect(self._tick_spinner)
        self._spinner_frame = 0
        self._spinner_chars = ("⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏")
        self._busy_subtext = ""

        # Brightness control: scale all renderer lights by this factor (1.0 = default).
        # `_base_light_intensities` is captured once per lighting setup so dragging the
        # slider doesn't compound previous multiplications.
        self._brightness_factor: float = 1.0
        self._base_light_intensities: List[float] = []

        if HAS_PYVISTA:
            self._plotter = QtInteractor(self, auto_update=False)
            # Soft "studio cyclorama" gray gradient. Pairs well with the warm
            # rim / cool fill lights used by isosurface_lit and still gives
            # point clouds enough contrast against the background.
            self._set_studio_background()
            self._plotter.enable_trackball_style()
            self._plotter.disable_parallel_projection()
            try:
                self._plotter.enable_anti_aliasing("fxaa")
            except Exception:
                pass

            interactor = self._plotter.interactor
            interactor.setFocusPolicy(Qt.StrongFocus)
            interactor.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
            self._layout.addWidget(interactor, stretch=1)
            self._setup_busy_overlay()
            # Snapshot the default VTK headlight intensities so the brightness
            # slider has something to scale even when no preview is loaded yet.
            self._capture_base_light_intensities()
        else:
            self._placeholder = QLabel(
                "3D preview requires PyVista.\n\n"
                "Install: pip install pyvista pyvistaqt"
            )
            self._placeholder.setAlignment(Qt.AlignCenter)
            self._placeholder.setWordWrap(True)
            self._placeholder.setStyleSheet("color: #cccccc; padding: 12px;")
            self._layout.addWidget(self._placeholder)

    def _setup_busy_overlay(self) -> None:
        self._busy_overlay = QWidget(self)
        self._busy_overlay.setVisible(False)
        self._busy_overlay.setStyleSheet(
            "background-color: rgba(25, 25, 25, 230); border-radius: 6px;"
        )
        ol = QVBoxLayout(self._busy_overlay)
        ol.setContentsMargins(24, 24, 24, 24)
        self._busy_title = QLabel("Preparing 3D preview")
        self._busy_title.setAlignment(Qt.AlignCenter)
        self._busy_title.setStyleSheet("color: #e0e0e0; font-size: 15px; font-weight: bold;")
        ol.addStretch(1)
        ol.addWidget(self._busy_title)
        self._busy_detail = QLabel("Please wait…")
        self._busy_detail.setAlignment(Qt.AlignCenter)
        self._busy_detail.setWordWrap(True)
        self._busy_detail.setStyleSheet("color: #b0b0b0; font-size: 12px; padding-top: 8px;")
        ol.addWidget(self._busy_detail)
        ol.addStretch(2)
        self._busy_overlay.raise_()

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if self._busy_overlay is not None:
            self._busy_overlay.setGeometry(self.rect())

    def _set_busy_text(self, title: str, detail: str = "") -> None:
        """Update the in-window busy overlay only (child process)."""
        self._busy_subtext = detail or "Working…"
        if self._busy_title is not None:
            self._busy_title.setText(title)
        if self._busy_detail is not None:
            c = self._spinner_chars[self._spinner_frame % len(self._spinner_chars)]
            self._busy_detail.setText(f"{c}  {self._busy_subtext}")

    def _emit_progress(self, title: str, detail: str = "") -> None:
        """Sync child overlay + main-panel status (title + detail, same as 3D window)."""
        detail = detail or "Working…"
        self._set_busy_text(title, detail)
        self.render_stage.emit(f"{title}\n{detail}")

    def _tick_spinner(self) -> None:
        self._spinner_frame += 1
        if self._busy_detail is not None:
            c = self._spinner_chars[self._spinner_frame % len(self._spinner_chars)]
            self._busy_detail.setText(f"{c}  {self._busy_subtext}")

    def _show_busy_overlay(self, title: str, detail: str) -> None:
        if self._busy_overlay is None:
            return
        self._spinner_frame = 0
        self._set_busy_text(title, detail)
        self._busy_overlay.setGeometry(self.rect())
        self._busy_overlay.show()
        self._busy_overlay.raise_()
        if not self._spinner_timer.isActive():
            self._spinner_timer.start(80)

    def _hide_busy_overlay(self) -> None:
        self._spinner_timer.stop()
        if self._busy_overlay is not None:
            self._busy_overlay.hide()

    @property
    def is_available(self) -> bool:
        return HAS_PYVISTA and self._plotter is not None

    def clear(self) -> None:
        self._shutdown_prepare_thread()
        self._chunk_timer.stop()
        self._pending_render = None
        self._apply_queue.clear()
        self._hide_busy_overlay()
        self._result = None
        if not self.is_available:
            return
        self._plotter.clear()
        self._plane_actor = None
        self._cloud_actor = None
        self._mask_actor = None
        self._volume_actor = None
        self._surface_actor = None
        self._axes_actor = None
        self._export_meshes = []
        # Lighting may have been reset to the default headlight; re-snapshot
        # and re-apply the user's brightness so the next preview honours it.
        self._capture_base_light_intensities()
        self._apply_brightness_factor()
        self._plotter.render()

    def cancel_render(self) -> None:
        """Cancel background mesh prep and any queued kickoff / GPU chunks."""
        self._render_cancelled = True
        self._chunk_timer.stop()
        pending_gen = None
        if self._pending_render is not None:
            pending_gen = self._pending_render[2]
        if self._kickoff_timer.isActive():
            self._kickoff_timer.stop()
        self._pending_render = None
        self._apply_queue.clear()
        self._hide_busy_overlay()
        if self._prepare_worker is not None:
            self._prepare_worker.request_cancel()
        if self._prepare_thread is not None and self._prepare_thread.isRunning():
            self._prepare_thread.quit()
            self._prepare_thread.wait(3000)
        self._prepare_thread = None
        self._prepare_worker = None
        if pending_gen is not None:
            self.render_finished.emit(pending_gen)

    def begin_set_preview(
        self, result: VolumePreviewResult, current_z: int, generation: int
    ) -> None:
        if not self.is_available:
            self.render_finished.emit(generation)
            return
        self._chunk_timer.stop()
        self._shutdown_prepare_thread()
        self._expected_gen = generation
        self._pending_render = (result, current_z, generation)
        self._render_cancelled = False
        self._show_busy_overlay("Preparing 3D preview", "Starting…")
        self._emit_progress(
            "Preparing 3D preview",
            "Scheduling mesh build (CPU thread) and GPU draw steps…",
        )
        self._kickoff_timer.start(0)

    def _shutdown_prepare_thread(self) -> None:
        if self._prepare_worker is not None:
            self._prepare_worker.request_cancel()
        if self._prepare_thread is not None and self._prepare_thread.isRunning():
            self._prepare_thread.quit()
            self._prepare_thread.wait(3000)
        self._prepare_thread = None
        self._prepare_worker = None

    def _start_vtk_prepare_thread(self) -> None:
        if self._pending_render is None:
            return
        result, current_z, gen = self._pending_render
        self._pending_render = None
        if self._render_cancelled or gen != self._expected_gen:
            self._hide_busy_overlay()
            self.render_finished.emit(gen)
            return

        self._emit_progress(
            "Building 3D meshes",
            "Contouring & triangulating on CPU thread…\n"
            "Large volumes can take several minutes.",
        )

        worker = VolumePreviewVTKWorker()
        worker.configure(
            result,
            current_z,
            gen,
            is_cancelled=lambda: self._render_cancelled,
        )
        worker.stage.connect(self._on_vtk_worker_stage, Qt.QueuedConnection)
        worker.prepare_done.connect(self._on_prepare_done, Qt.QueuedConnection)
        worker.failed.connect(self._on_prepare_failed, Qt.QueuedConnection)

        self._prepare_worker = worker
        self._prepare_thread, _ = start_vtk_prepare_thread(worker, parent=self)
        self._prepare_thread.finished.connect(worker.deleteLater)
        self._prepare_thread.finished.connect(self._on_prepare_thread_exited)

    def _on_prepare_thread_exited(self) -> None:
        self._prepare_thread = None
        self._prepare_worker = None

    def _on_vtk_worker_stage(self, text: str) -> None:
        self._emit_progress("Building 3D meshes", text)

    def _on_prepare_failed(self, message: str) -> None:
        self._chunk_timer.stop()
        self._hide_busy_overlay()
        if not self.is_available:
            self.render_finished.emit(self._expected_gen)
            return
        self._plotter.clear()
        self._plotter.add_text(f"Preview render failed: {message}", font_size=10)
        self._plotter.render()
        self.render_finished.emit(self._expected_gen)

    def _on_prepare_done(self, payload: object, gen: int) -> None:
        if gen != self._expected_gen:
            return
        if payload is None:
            self._hide_busy_overlay()
            self.render_finished.emit(gen)
            return
        self._chunk_gen = gen
        self._start_chunked_apply(payload)

    def _build_apply_queue(self, payload: PreviewVTKPayload) -> List[Tuple[Any, ...]]:
        q: List[Tuple[Any, ...]] = [("clear",)]
        result = payload.result
        for kind, data, kw in payload.primary:
            if kind == "volume":
                q.append(("volume", data, kw, payload))
            else:
                q.append(("cmd", kind, data, kw))
        for kind, data, kw in payload.mask:
            q.append(("cmd", kind, data, kw))
        q.append(("finale", payload.current_z))
        return q

    def _start_chunked_apply(self, payload: PreviewVTKPayload) -> None:
        self._chunk_payload = payload
        self._apply_queue = self._build_apply_queue(payload)
        self._apply_i = 0
        n = len(self._apply_queue)
        self._emit_progress(
            "Drawing 3D preview",
            f"Pushing geometry to GPU — {n} steps…\nThe main window stays responsive.",
        )
        self._chunk_timer.start(0)

    def _apply_next_chunk(self) -> None:
        if self._chunk_gen != self._expected_gen or self._render_cancelled:
            self._hide_busy_overlay()
            return
        n = len(self._apply_queue)
        if self._apply_i >= n:
            self._finalize_chunked_apply()
            return

        op = self._apply_queue[self._apply_i]
        self._apply_i += 1
        step_done = self._apply_i
        step_action = {
            "clear": "Clearing scene",
            "volume": "Connecting volume renderer",
            "cmd": "Adding surface / points",
            "finale": "Finishing scene (camera & slice plane)",
        }.get(op[0], "Working")
        self._emit_progress(
            "Drawing 3D preview",
            f"Step {step_done} of {n} — {step_action}\n"
            f"GPU attach: {step_action.lower()}…",
        )

        kind = op[0]
        if kind == "clear":
            self._plotter.clear()
            self._reset_detail_effects()
            self._plane_actor = None
            self._cloud_actor = None
            self._mask_actor = None
            self._volume_actor = None
            self._surface_actor = None
            self._axes_actor = None
            self._result = self._chunk_payload.result if self._chunk_payload else None
            self._current_z = self._chunk_payload.current_z if self._chunk_payload else 0
        elif kind == "volume":
            _, grid, kw, pl = op
            ok = self._try_add_volume(grid, kw)
            if (
                not ok
                and pl.result.mode in ("solid", "mip")
                and pl.volume_fallback
            ):
                self._emit_progress(
                    "Drawing 3D preview",
                    "GPU volume renderer unavailable — falling back to layered surfaces.",
                )
                for j, fb in enumerate(pl.volume_fallback):
                    fk, fd, fkw = fb
                    self._apply_queue.insert(self._apply_i + j, ("cmd", fk, fd, fkw))
        elif kind == "cmd":
            self._apply_command(op[1], op[2], op[3])
        elif kind == "finale":
            z = op[1]
            self._update_slice_plane(z)
            self._add_bounds_axes()
            self._reset_camera_to_data()
            self._plotter.render()

        self._chunk_timer.start(0)

    def _finalize_chunked_apply(self) -> None:
        self._hide_busy_overlay()
        self._chunk_payload = None
        self.render_finished.emit(self._chunk_gen)

    def _try_add_volume(self, grid: "pv.ImageData", kw: dict) -> bool:
        mappers = ("smart", "gpu", "fixed_point")
        last_err: Optional[Exception] = None
        last_mapper = ""
        base = dict(kw)
        for mapper in mappers:
            try:
                mkw = dict(base)
                mkw["mapper"] = mapper
                actor = self._plotter.add_volume(grid, **mkw)
                if actor is None:
                    last_err = RuntimeError(f"add_volume returned None ({mapper})")
                    last_mapper = mapper
                    continue
                self._volume_actor = actor
                return True
            except Exception as exc:
                last_err = exc
                last_mapper = mapper
                self._volume_actor = None
        if last_err is not None:
            msg = f"Volume render failed (mapper={last_mapper}, {last_err.__class__.__name__}: {last_err})"
            print(msg)
            self._emit_progress(
                "Drawing 3D preview",
                f"GPU volume renderer error: {last_err.__class__.__name__}: {last_err}",
            )
        return False

    def _apply_command(self, kind: str, data: Any, kw: dict) -> bool:
        if kind == "text":
            self._plotter.add_text(data, **kw)
            return True
        if kind == "mesh":
            mkw = dict(kw)
            detail_lit = bool(mkw.pop("_detail_lit", False))
            actor = self._plotter.add_mesh(data, **mkw)
            if self._surface_actor is None:
                self._surface_actor = actor
            try:
                self._export_meshes.append(data.copy(deep=True))
            except Exception:
                self._export_meshes.append(data)
            if detail_lit:
                self._enable_detail_lighting()
            return True
        if kind == "volume":
            return self._try_add_volume(data, kw)
        return True

    def _reset_detail_effects(self) -> None:
        if not self.is_available:
            return
        try:
            self._plotter.disable_ssao()
        except Exception:
            pass
        try:
            self._plotter.disable_eye_dome_lighting()
        except Exception:
            pass

    def _set_studio_background(self) -> None:
        """Fixed neutral-gray gradient. Falls back to a flat color on older PyVista."""
        if not self.is_available:
            return
        bottom = "#363636"
        top = "#5a5a5a"
        try:
            self._plotter.set_background(bottom, top=top)
        except TypeError:
            # Older PyVista versions don't accept `top` — flat fill is fine.
            try:
                self._plotter.set_background(bottom)
            except Exception:
                pass
        except Exception:
            pass

    def _enable_detail_lighting(self) -> None:
        """SSAO + ambient occlusion + multi-light setup to reveal voids / small features."""
        if not self.is_available:
            return
        try:
            # Replace the default headlight with key + fill + rim to reveal shape.
            self._plotter.remove_all_lights()
            try:
                from pyvista import Light
            except Exception:
                Light = None  # type: ignore
            if Light is not None:
                key = Light(
                    position=(1.2, 1.0, 1.5),
                    focal_point=(0, 0, 0),
                    color="white",
                    intensity=0.95,
                    light_type="scene light",
                )
                fill = Light(
                    position=(-1.2, 0.5, 0.8),
                    focal_point=(0, 0, 0),
                    color="#cfd6e0",
                    intensity=0.45,
                    light_type="scene light",
                )
                rim = Light(
                    position=(0.0, -1.4, 1.0),
                    focal_point=(0, 0, 0),
                    color="#ffd9b3",
                    intensity=0.35,
                    light_type="scene light",
                )
                self._plotter.add_light(key)
                self._plotter.add_light(fill)
                self._plotter.add_light(rim)
            # Re-snapshot base intensities for the brightness slider and
            # re-apply the user's current factor so the new lights inherit it.
            self._capture_base_light_intensities()
            self._apply_brightness_factor()
        except Exception as exc:
            print(f"Detail-lighting setup skipped: {exc}")
        try:
            self._plotter.enable_ssao(radius=12.0, bias=0.01, kernel_size=64, blur=True)
        except Exception:
            try:
                self._plotter.enable_ssao()
            except Exception as exc:
                print(f"SSAO unavailable: {exc}")
        try:
            self._plotter.enable_eye_dome_lighting()
        except Exception:
            pass
        try:
            self._plotter.enable_anti_aliasing("ssaa")
        except Exception:
            pass

    def _apply_vtk_payload_immediate(self, payload: PreviewVTKPayload) -> None:
        if not self.is_available:
            return
        self._result = payload.result
        self._current_z = payload.current_z
        self._plotter.clear()
        self._plane_actor = None
        self._cloud_actor = None
        self._mask_actor = None
        self._volume_actor = None
        self._surface_actor = None
        self._axes_actor = None
        self._export_meshes = []

        for kind, data, kw in payload.primary:
            if kind == "volume":
                vol_ok = self._try_add_volume(data, kw)
                if (
                    not vol_ok
                    and payload.result.mode == "solid"
                    and payload.volume_fallback
                ):
                    for fk, fd, fkw in payload.volume_fallback:
                        self._apply_command(fk, fd, fkw)
            else:
                self._apply_command(kind, data, kw)

        for kind, data, kw in payload.mask:
            self._apply_command(kind, data, kw)

        self._update_slice_plane(payload.current_z)
        self._add_bounds_axes()
        self._reset_camera_to_data()
        self._plotter.render()

    def set_preview(self, result: VolumePreviewResult, current_z: int = 0) -> None:
        from ..services.volume_vtk_prepare import build_preview_payload

        payload = build_preview_payload(
            result, current_z, 0, should_cancel=lambda: False
        )
        self._expected_gen = 0
        self._apply_vtk_payload_immediate(payload)
        self.render_finished.emit(0)

    def set_current_slice(self, z: int) -> None:
        if not self.is_available or self._result is None:
            return
        self._current_z = z
        self._update_slice_plane(z)

    def _volume_bounds(self, result: VolumePreviewResult) -> Tuple[float, float, float, float, float, float]:
        ex, ey, ez = result.physical_extent_xyz
        return (0.0, max(ex, 1.0), 0.0, max(ey, 1.0), 0.0, max(ez, 1.0))

    def _reset_camera_to_data(self) -> None:
        if not self.is_available or self._result is None:
            return
        bounds = self._volume_bounds(self._result)
        self._plotter.reset_camera(bounds=bounds)
        self._plotter.view_isometric()
        try:
            self._plotter.camera.zoom(0.85)
        except Exception:
            pass

    def reset_orientation(self) -> None:
        """Public: reorient the 3D camera to the default isometric view."""
        if not self.is_available:
            return
        if self._result is None:
            try:
                self._plotter.view_isometric()
                self._plotter.reset_camera()
                self._plotter.render()
            except Exception:
                pass
            return
        self._reset_camera_to_data()
        self._plotter.render()

    # ------------------------------------------------------------------
    # Brightness control
    # ------------------------------------------------------------------
    @property
    def brightness_factor(self) -> float:
        return self._brightness_factor

    def set_brightness(self, factor: float) -> None:
        """Scale every renderer light by `factor` (1.0 = unchanged, 0 = dark, 2.0 = double).

        We always rescale relative to the snapshot taken when the lighting
        setup was installed, so repeated calls don't compound.
        """
        try:
            value = float(factor)
        except (TypeError, ValueError):
            return
        # Clamp to a sensible range; VTK accepts very large values but the
        # picture clips long before we get there.
        value = max(0.0, min(value, 4.0))
        self._brightness_factor = value
        self._apply_brightness_factor()

    def _capture_base_light_intensities(self) -> None:
        """Record the current intensity of every light so the slider has a baseline."""
        if not self.is_available:
            self._base_light_intensities = []
            return
        try:
            lights = self._plotter.renderer.GetLights()
            n = lights.GetNumberOfItems()
            lights.InitTraversal()
            intensities: List[float] = []
            for _ in range(n):
                light = lights.GetNextItem()
                if light is None:
                    continue
                intensities.append(float(light.GetIntensity()))
            self._base_light_intensities = intensities
        except Exception:
            self._base_light_intensities = []

    def _apply_brightness_factor(self) -> None:
        if not self.is_available or not self._base_light_intensities:
            return
        try:
            lights = self._plotter.renderer.GetLights()
            n = lights.GetNumberOfItems()
            lights.InitTraversal()
            i = 0
            for _ in range(n):
                light = lights.GetNextItem()
                if light is None:
                    continue
                if i < len(self._base_light_intensities):
                    base = self._base_light_intensities[i]
                    light.SetIntensity(max(0.0, base * self._brightness_factor))
                i += 1
            self._plotter.render()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Export snapshot / 3D model
    # ------------------------------------------------------------------
    def has_exportable_geometry(self) -> bool:
        return bool(self._export_meshes)

    def capture_screenshot_array(self, scale: int = 3) -> Optional[np.ndarray]:
        """Capture the current view to a numpy image (must run on the GUI thread)."""
        if not self.is_available:
            return None
        try:
            scale = max(1, min(int(scale), 8))
            self._plotter.render()
            w, h = self._plotter.window_size
            try:
                img = self._plotter.screenshot(
                    window_size=(w * scale, h * scale),
                    return_img=True,
                )
            except TypeError:
                img = self._plotter.screenshot(scale=scale, return_img=True)
            if img is None:
                return None
            return np.asarray(img)
        except Exception as exc:
            logger.exception("Screenshot capture failed: %s", exc)
            return None

    def copy_export_meshes(self) -> List[Any]:
        """Deep-copy export meshes for use on a worker thread."""
        copies: List[Any] = []
        for mesh in self._export_meshes:
            try:
                copies.append(mesh.copy(deep=True))
            except Exception:
                copies.append(mesh)
        return copies

    def save_screenshot(self, path: str, scale: int = 3) -> bool:
        """Synchronous screenshot save (capture + write on calling thread)."""
        arr = self.capture_screenshot_array(scale)
        if arr is None:
            return False
        try:
            from PIL import Image

            data = arr
            if data.dtype != np.uint8:
                if data.max() <= 1.0:
                    data = (np.clip(data, 0.0, 1.0) * 255.0).astype(np.uint8)
                else:
                    data = np.clip(data, 0, 255).astype(np.uint8)
            if data.ndim == 3 and data.shape[2] >= 3:
                Image.fromarray(data[:, :, :3], mode="RGB").save(path)
            else:
                Image.fromarray(data).save(path)
            logger.info("Saved 3D screenshot %s", path)
            return True
        except Exception as exc:
            logger.exception("Screenshot save failed: %s", exc)
            return False

    def export_combined_mesh(self, path: str) -> bool:
        """Synchronous mesh export (merge + write on calling thread)."""
        if not HAS_PYVISTA or not self._export_meshes:
            return False
        meshes = self.copy_export_meshes()
        try:
            combined = meshes[0]
            for mesh in meshes[1:]:
                combined = combined.merge(mesh)
            combined.save(path)
            logger.info(
                "Exported 3D mesh %s (%d parts, %d points)",
                path,
                len(meshes),
                combined.n_points,
            )
            return True
        except Exception as exc:
            logger.exception("Mesh export failed: %s", exc)
            return False

    def _add_bounds_axes(self) -> None:
        self._axes_actor = self._plotter.add_axes(
            interactive=False,
            line_width=2,
            color="white",
        )

    def _update_slice_plane(self, z_full: int) -> None:
        if self._result is None or not self.is_available:
            return

        sz, sy, sx = self._result.spacing_zyx
        _, h_full, w_full = self._result.shape_zyx
        z_max = max(0, self._result.shape_zyx[0] - 1)
        z_full = int(np.clip(z_full, 0, z_max))

        plane_w = max(1.0, (w_full - 1) * sx)
        plane_h = max(1.0, (h_full - 1) * sy)
        z_pos = z_full * sz
        center = (plane_w * 0.5, plane_h * 0.5, z_pos)

        if self._plane_actor is not None:
            self._plotter.remove_actor(self._plane_actor)

        self._plane_actor = self._plotter.add_mesh(
            pv.Plane(center=center, direction=(0, 0, 1), i_size=plane_w, j_size=plane_h),
            color="cyan",
            opacity=0.12,
            style="wireframe",
            line_width=1,
            pickable=False,
        )
        self._plotter.render()

    def enterEvent(self, event):
        if self._plotter is not None:
            self._plotter.interactor.setFocus()
        super().enterEvent(event)

    def mousePressEvent(self, event):
        if self._plotter is not None:
            self._plotter.interactor.setFocus()
        super().mousePressEvent(event)

    def keyPressEvent(self, event):
        if event.key() == Qt.Key_Home:
            self.reset_orientation()
            event.accept()
            return
        super().keyPressEvent(event)
