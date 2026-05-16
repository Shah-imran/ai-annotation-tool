"""
Model for lazy-loaded 3D slice stacks (X-ray / micro-CT).
"""
import os
from typing import List, Optional, Tuple

import numpy as np
from PyQt5.QtCore import QObject, pyqtSignal

from ..services.volume_io import (
    discover_slice_files,
    load_slice_tiff,
    scan_id_from_path,
    slice_window_defaults,
    validate_slice_stack,
)


class VolumeModel(QObject):
    """Manages a TIFF slice stack without loading the full volume into RAM."""

    scan_loaded = pyqtSignal(str)  # scan_id
    slice_changed = pyqtSignal(int, int)  # index, total

    def __init__(self):
        super().__init__()
        self._scan_dir: str = ""
        self._scan_id: str = ""
        self._slice_paths: List[str] = []
        self._height: int = 0
        self._width: int = 0
        self._current_index: int = 0
        self._window_center: float = 0.0
        self._window_width: float = 1.0
        self._use_window_level: bool = False
        self._slice_cache: dict = {}
        self._cache_limit = 8

    @property
    def scan_dir(self) -> str:
        return self._scan_dir

    @property
    def scan_id(self) -> str:
        return self._scan_id

    @property
    def slice_paths(self) -> List[str]:
        return self._slice_paths.copy()

    @property
    def num_slices(self) -> int:
        return len(self._slice_paths)

    @property
    def shape_zyx(self) -> Tuple[int, int, int]:
        return len(self._slice_paths), self._height, self._width

    @property
    def current_index(self) -> int:
        return self._current_index

    @property
    def window_center(self) -> float:
        return self._window_center

    @property
    def window_width(self) -> float:
        return self._window_width

    @property
    def use_window_level(self) -> bool:
        return self._use_window_level

    def load_scan(self, scan_dir: str) -> bool:
        """Load a scan folder containing slice_NNNN.tif files."""
        slice_paths = discover_slice_files(scan_dir)
        if not slice_paths:
            return False

        try:
            h, w = validate_slice_stack(slice_paths)
        except ValueError as e:
            print(f"Volume load error: {e}")
            return False

        self._scan_dir = os.path.normpath(scan_dir)
        self._scan_id = scan_id_from_path(scan_dir)
        self._slice_paths = slice_paths
        self._height = h
        self._width = w
        self._current_index = 0
        self._slice_cache.clear()
        self._use_window_level = False

        first = self.get_slice_u16(0)
        self._window_center, self._window_width = slice_window_defaults(first)

        self.scan_loaded.emit(self._scan_id)
        self.slice_changed.emit(self._current_index, self.num_slices)
        return True

    def get_slice_u16(self, index: int) -> np.ndarray:
        """Load one slice (cached)."""
        if index in self._slice_cache:
            return self._slice_cache[index]

        if not 0 <= index < len(self._slice_paths):
            raise IndexError(f"Slice index out of range: {index}")

        arr = load_slice_tiff(self._slice_paths[index])
        self._slice_cache[index] = arr
        if len(self._slice_cache) > self._cache_limit:
            oldest = min(self._slice_cache.keys(), key=lambda k: abs(k - index))
            del self._slice_cache[oldest]
        return arr

    def set_current_index(self, index: int) -> bool:
        if 0 <= index < len(self._slice_paths):
            self._current_index = index
            self.slice_changed.emit(index, self.num_slices)
            return True
        return False

    def next_slice(self) -> bool:
        return self.set_current_index(self._current_index + 1)

    def previous_slice(self) -> bool:
        return self.set_current_index(self._current_index - 1)

    def set_window_level(self, center: float, width: float) -> None:
        self._window_center = center
        self._window_width = max(1.0, width)
        self._use_window_level = True

    def reset_window_level_for_current(self) -> None:
        """Restore display like a standard 16-bit TIFF viewer (full square, no FOV mask)."""
        sl = self.get_slice_u16(self._current_index)
        self._window_center, self._window_width = slice_window_defaults(sl)
        self._use_window_level = False
