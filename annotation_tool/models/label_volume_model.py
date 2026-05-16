"""
Memory-mapped 3D label volume for voxel mask annotation.
"""
from typing import List, Optional, Tuple

import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal

from ..services.volume_io import interpolate_brush_line, open_label_memmap
from .undo_manager import ActionType, UndoManager


class LabelVolumeModel(QObject):
    """Uint8 label volume (Z, H, W) backed by a memmap file."""

    labels_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self._labels: Optional[np.memmap] = None
        self._label_path: str = ""
        self._shape: Tuple[int, int, int] = (0, 0, 0)
        self._class_names: List[str] = ["background", "roi"]
        self._current_class_id: int = 1
        self._undo_manager = UndoManager(max_history=30)

    @property
    def label_path(self) -> str:
        return self._label_path

    @property
    def shape_zyx(self) -> Tuple[int, int, int]:
        return self._shape

    @property
    def class_names(self) -> List[str]:
        return self._class_names.copy()

    @property
    def current_class_id(self) -> int:
        return self._current_class_id

    def can_undo(self) -> bool:
        return self._undo_manager.can_undo()

    def can_redo(self) -> bool:
        return self._undo_manager.can_redo()

    def clear_undo_history(self) -> None:
        self._undo_manager.clear()

    def set_class_names(self, names: List[str]) -> None:
        if names:
            self._class_names = ["background"] + [n for n in names if n.lower() != "background"]
        else:
            self._class_names = ["background", "roi"]
        if self._current_class_id >= len(self._class_names):
            self._current_class_id = min(1, len(self._class_names) - 1)

    def set_current_class_id(self, class_id: int) -> bool:
        if 0 <= class_id < len(self._class_names):
            self._current_class_id = class_id
            return True
        return False

    def attach_volume(self, shape_zyx: Tuple[int, int, int], label_path: str) -> bool:
        """Create or open memmap label file for the given shape."""
        z, h, w = shape_zyx
        if z <= 0 or h <= 0 or w <= 0:
            return False

        self.close()
        self._label_path = label_path
        self._shape = (z, h, w)
        self._labels = open_label_memmap(label_path, (z, h, w))
        self.clear_undo_history()
        self.labels_changed.emit()
        return True

    def load_from_array(self, data: np.ndarray, label_path: str) -> bool:
        """Replace memmap contents from a numpy array."""
        if data.shape != self._shape:
            self.attach_volume(data.shape, label_path)
        self._labels[:] = data.astype(np.uint8)
        self._labels.flush()
        self.clear_undo_history()
        self.labels_changed.emit()
        return True

    def get_slice_labels(self, z: int) -> np.ndarray:
        if self._labels is None:
            return np.zeros(self._shape[1:], dtype=np.uint8)
        return np.asarray(self._labels[z])

    def push_paint_stroke_undo(
        self,
        z: int,
        y0: int,
        y1: int,
        x0: int,
        x1: int,
        before_patch: np.ndarray,
        after_patch: np.ndarray,
    ) -> bool:
        """Record one completed brush stroke for undo/redo."""
        if self._labels is None:
            return False
        if before_patch.shape != after_patch.shape:
            return False
        if np.array_equal(before_patch, after_patch):
            return False

        self._undo_manager.push_action(
            ActionType.VOLUME_PAINT_STROKE,
            {
                "z": z,
                "y0": y0,
                "y1": y1,
                "x0": x0,
                "x1": x1,
                "before": before_patch.copy(),
                "after": after_patch.copy(),
            },
        )
        return True

    def undo(self) -> bool:
        if not self._undo_manager.can_undo() or self._labels is None:
            return False

        action = self._undo_manager.pop_action()
        if action is None or action.action_type != ActionType.VOLUME_PAINT_STROKE:
            return False

        data = action.data
        z = data["z"]
        y0, y1, x0, x1 = data["y0"], data["y1"], data["x0"], data["x1"]
        self._labels[z, y0:y1, x0:x1] = data["before"]
        self._labels.flush()
        self.labels_changed.emit()
        return True

    def redo(self) -> bool:
        if not self._undo_manager.can_redo() or self._labels is None:
            return False

        action = self._undo_manager.pop_redo_action()
        if action is None or action.action_type != ActionType.VOLUME_PAINT_STROKE:
            return False

        data = action.data
        z = data["z"]
        y0, y1, x0, x1 = data["y0"], data["y1"], data["x0"], data["x1"]
        self._labels[z, y0:y1, x0:x1] = data["after"]
        self._labels.flush()
        self.labels_changed.emit()
        return True

    def paint_disk(
        self,
        z: int,
        cy: int,
        cx: int,
        radius: int,
        class_id: int,
        erase: bool = False,
        emit: bool = True,
    ) -> None:
        """Paint a circular brush on one slice."""
        if self._labels is None:
            return

        h, w = self._shape[1], self._shape[2]
        y0 = max(0, cy - radius)
        y1 = min(h, cy + radius + 1)
        x0 = max(0, cx - radius)
        x1 = min(w, cx + radius + 1)

        yy, xx = np.ogrid[y0:y1, x0:x1]
        mask = (yy - cy) ** 2 + (xx - cx) ** 2 <= radius * radius
        value = np.uint8(0 if erase else class_id)
        slab = self._labels[z, y0:y1, x0:x1]
        slab[mask] = value
        if emit:
            self.labels_changed.emit()

    def paint_stroke(
        self,
        z: int,
        points: List[Tuple[int, int]],
        radius: int,
        class_id: int,
        erase: bool = False,
        emit_changed: bool = True,
    ) -> None:
        if not points:
            return
        for cy, cx in points:
            self.paint_disk(z, cy, cx, radius, class_id, erase=erase, emit=False)
        self._labels.flush()
        if emit_changed:
            self.labels_changed.emit()

    def paint_stroke_line(
        self,
        z: int,
        y0: int,
        x0: int,
        y1: int,
        x1: int,
        radius: int,
        class_id: int,
        erase: bool = False,
    ) -> None:
        """Paint a continuous stroke between two pixel coordinates."""
        points = interpolate_brush_line(y0, x0, y1, x1, radius)
        self.paint_stroke(z, points, radius, class_id, erase=erase)

    def flush(self) -> None:
        if self._labels is not None:
            self._labels.flush()

    def as_array(self) -> np.ndarray:
        if self._labels is None:
            return np.zeros(self._shape, dtype=np.uint8)
        return np.asarray(self._labels)

    def close(self) -> None:
        if self._labels is not None:
            self._labels.flush()
            del self._labels
            self._labels = None
