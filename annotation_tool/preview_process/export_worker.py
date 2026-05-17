"""
Background export tasks for the 3D preview child window.

OpenGL screenshot capture must run on the GUI thread; writing PNG files and
merging/saving VTK meshes are offloaded here.
"""
from __future__ import annotations

from typing import List

import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal, pyqtSlot

from ..utils.logging_config import get_logger

logger = get_logger(__name__)


class PreviewExportWorker(QObject):
    """Runs disk-heavy export work on a QThread."""

    finished = pyqtSignal(bool, str)  # success, path or error message

    @pyqtSlot(object, str)
    def save_png(self, image_array, path: str) -> None:
        try:
            from PIL import Image

            arr = np.asarray(image_array)
            if arr.size == 0:
                raise ValueError("Empty screenshot buffer")

            if arr.dtype != np.uint8:
                if arr.max() <= 1.0:
                    arr = (np.clip(arr, 0.0, 1.0) * 255.0).astype(np.uint8)
                else:
                    arr = np.clip(arr, 0, 255).astype(np.uint8)

            if arr.ndim == 2:
                img = Image.fromarray(arr, mode="L")
            elif arr.ndim == 3 and arr.shape[2] >= 3:
                img = Image.fromarray(arr[:, :, :3], mode="RGB")
            else:
                raise ValueError(f"Unexpected screenshot shape {arr.shape}")

            img.save(path)
            logger.info("Wrote 3D snapshot %s", path)
            self.finished.emit(True, path)
        except Exception as exc:
            logger.exception("PNG write failed for %s", path)
            self.finished.emit(False, str(exc))

    @pyqtSlot(object, str)
    def export_mesh(self, meshes, path: str) -> None:
        try:
            mesh_list: List = list(meshes)
            if not mesh_list:
                raise ValueError("No mesh data to export")
            combined = mesh_list[0]
            for mesh in mesh_list[1:]:
                combined = combined.merge(mesh)
            combined.save(path)
            logger.info(
                "Exported 3D mesh %s (%d parts, %d points)",
                path,
                len(mesh_list),
                combined.n_points,
            )
            self.finished.emit(True, path)
        except Exception as exc:
            logger.exception("Mesh export failed for %s", path)
            self.finished.emit(False, str(exc))
