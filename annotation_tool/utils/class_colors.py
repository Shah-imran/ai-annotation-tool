"""
Distinct overlay colors for volume annotation class IDs (0 = transparent background).
"""
from __future__ import annotations

import colorsys
from typing import List, Tuple

from PyQt5.QtGui import QColor


def distinct_class_color(class_id: int, alpha: int = 140) -> QColor:
    """Pick a stable, distinguishable color for ``class_id`` (id 0 = background)."""
    if class_id <= 0:
        return QColor(0, 0, 0, 0)
    # Golden-ratio hue stepping keeps neighbors visually distinct.
    hue = (class_id * 0.618033988749895) % 1.0
    sat = 0.72 if class_id % 3 else 0.58
    val = 0.88 if class_id % 2 else 0.78
    r, g, b = colorsys.hsv_to_rgb(hue, sat, val)
    return QColor(int(r * 255), int(g * 255), int(b * 255), alpha)


def build_class_qcolors(max_id: int = 256) -> List[QColor]:
    """QColor list indexed by class id (length ``max_id``)."""
    return [distinct_class_color(i) for i in range(max_id)]


def build_class_rgba_lut(size: int = 256):
    """RGBA uint8 lookup table shape ``(size, 4)`` for fast numpy overlay indexing."""
    import numpy as np  # local import keeps Qt-only callers light

    lut = np.zeros((size, 4), dtype=np.uint8)
    for i in range(size):
        c = distinct_class_color(i)
        lut[i] = (c.red(), c.green(), c.blue(), c.alpha())
    return lut
