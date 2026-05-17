"""
2D slice viewer with window/level display and brush painting for voxel labels.
"""
import math
from typing import Optional, Tuple

import numpy as np
from PyQt5.QtCore import Qt, QPoint, QPointF, QTimer, pyqtSignal
from PyQt5.QtGui import QColor, QImage, QKeyEvent, QMouseEvent, QPainter, QPen, QPixmap
from PyQt5.QtWidgets import QWidget

from ..services.volume_io import interpolate_brush_line, slice_to_display_u8
from ..utils.class_colors import build_class_qcolors, build_class_rgba_lut, distinct_class_color


class SliceCanvas(QWidget):
    """Displays one axial slice and supports brush/eraser painting."""

    MIN_ZOOM = 0.25
    MAX_ZOOM = 32.0
    ZOOM_WHEEL_FACTOR = 1.12  # multiplied per ±120 delta step

    # Batched stroke points while dragging (y, x)
    stroke_started = pyqtSignal(int)  # z — before first paint point of stroke
    stroke_segment = pyqtSignal(int, list, int, bool)  # z, points, radius, erase
    stroke_ended = pyqtSignal()  # mouse released after painting

    def __init__(self):
        super().__init__()
        self.setMinimumSize(400, 300)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.StrongFocus)
        self.setStyleSheet("background-color: #2b2b2b;")

        self._slice_u16: Optional[np.ndarray] = None
        self._label_slice: Optional[np.ndarray] = None
        self._display_u8: Optional[np.ndarray] = None
        self._pixmap: Optional[QPixmap] = None
        self._scaled_pixmap: Optional[QPixmap] = None
        self._scale_x = 1.0
        self._scale_y = 1.0
        self._image_offset = QPoint(0, 0)

        self._zoom = 1.0  # multiplied by the “fit widget” baseline scale
        self._view_origin_f = QPointF(0.0, 0.0)  # top-left of pixmap in widget coordinates
        self._view_initialized = False
        self._center_pending = False  # defer center until widget has final layout size
        self._slice_hw: Optional[Tuple[int, int]] = None  # image (h, w) for resetting zoom/pan when shape changes
        self._middle_panning = False
        self._middle_last_pos = QPoint(0, 0)

        self._window_center = 0.0
        self._window_width = 1.0
        self._use_window_level = False
        self._z_index = 0

        self._brush_radius = 8
        self._current_class_id = 1
        self._erase_mode = False
        self._painting = False
        self._last_paint_pos: Optional[Tuple[int, int]] = None
        self._cursor_pos: Optional[QPoint] = None
        self._show_brush_cursor = False

        self._class_colors = build_class_qcolors(256)
        self._color_lut = build_class_rgba_lut(256)

    def refresh_class_palette(self, num_classes=None) -> None:
        """Rebuild overlay colors when the class list changes (supports id > 4)."""
        del num_classes  # palette is fixed 256-entry; all ids stay visible
        self._class_colors = build_class_qcolors(256)
        self._color_lut = build_class_rgba_lut(256)
        self.update()

    def set_brush_radius(self, radius: int) -> None:
        self._brush_radius = max(1, min(128, radius))
        self.update()

    def set_current_class_id(self, class_id: int) -> None:
        self._current_class_id = max(0, class_id)
        self.update()

    def set_erase_mode(self, erase: bool) -> None:
        self._erase_mode = erase
        self.update()

    def update_label_overlay(self, label_slice: Optional[np.ndarray]) -> None:
        """Update mask overlay without reloading the intensity slice."""
        self._label_slice = label_slice
        self.update()

    def set_slice_data(
        self,
        slice_u16: np.ndarray,
        label_slice: Optional[np.ndarray],
        z_index: int,
        window_center: float,
        window_width: float,
        use_window_level: bool = False,
    ) -> None:
        self._slice_u16 = slice_u16
        self._label_slice = label_slice
        self._z_index = z_index
        self._window_center = window_center
        self._window_width = window_width
        self._use_window_level = use_window_level
        h, w = int(slice_u16.shape[0]), int(slice_u16.shape[1])
        shape_changed = self._slice_hw != (h, w)
        if shape_changed:
            self._slice_hw = (h, w)
            self._reset_zoom_pan_for_new_dimensions()
        self._rebuild_pixmap()
        if shape_changed or not self._view_initialized:
            self._schedule_center_layout()
        else:
            self._layout_view()
        self.update()

    def reset_view_zoom(self) -> None:
        """Zoom 1×, pan centered (fit baseline). Callable from shortcuts."""
        self._reset_zoom_pan_for_new_dimensions()
        if self._pixmap:
            self._schedule_center_layout()

    def _reset_zoom_pan_for_new_dimensions(self) -> None:
        self._zoom = 1.0
        self._view_initialized = False
        self._view_origin_f = QPointF(0.0, 0.0)
        self._center_pending = True

    def _schedule_center_layout(self) -> None:
        """Center after Qt finishes sizing splitters (avoids left-shift on startup)."""
        self._center_pending = True
        QTimer.singleShot(0, self._apply_pending_center)

    def _apply_pending_center(self) -> None:
        if not self._center_pending or self._pixmap is None:
            return
        if self.width() <= 0 or self.height() <= 0:
            return
        self._layout_view(force_center=True)
        self._center_pending = False
        self.update()

    def showEvent(self, event):
        super().showEvent(event)
        if self._center_pending and self._pixmap is not None:
            self._apply_pending_center()

    def _rebuild_pixmap(self) -> None:
        if self._slice_u16 is None:
            self._display_u8 = None
            self._pixmap = None
            self._scaled_pixmap = None
            return
        self._display_u8 = slice_to_display_u8(
            self._slice_u16,
            self._window_center,
            self._window_width,
            self._use_window_level,
        )
        h, w = self._display_u8.shape
        qimg = QImage(
            np.ascontiguousarray(self._display_u8).data,
            w,
            h,
            w,
            QImage.Format_Grayscale8,
        )
        self._pixmap = QPixmap.fromImage(qimg.copy())

    def _layout_view(
        self,
        stabilize_widget: Optional[QPoint] = None,
        stabilize_ix: Optional[float] = None,
        stabilize_iy: Optional[float] = None,
        force_center: bool = False,
    ) -> None:
        """Rebuild scaled pixmap from zoom; optionally anchor one image point to a widget location."""
        if not self._pixmap:
            self._scaled_pixmap = None
            return

        widget_size = self.size()
        ww, wh = widget_size.width(), widget_size.height()
        iw, ih = self._pixmap.width(), self._pixmap.height()
        if iw <= 0 or ih <= 0 or ww <= 0 or wh <= 0:
            return

        scale_fit = min(ww / float(iw), wh / float(ih), 1.0)
        scale_abs = scale_fit * self._zoom
        tw = max(1, int(round(iw * scale_abs)))
        th = max(1, int(round(ih * scale_abs)))

        self._scaled_pixmap = self._pixmap.scaled(
            tw, th, Qt.IgnoreAspectRatio, Qt.SmoothTransformation
        )

        dw = self._scaled_pixmap.width()
        dh = self._scaled_pixmap.height()
        self._scale_x = dw / float(iw)
        self._scale_y = dh / float(ih)

        if force_center or not self._view_initialized:
            self._view_origin_f = QPointF((ww - dw) / 2.0, (wh - dh) / 2.0)
        elif (
            stabilize_widget is not None
            and stabilize_ix is not None
            and stabilize_iy is not None
        ):
            self._view_origin_f = QPointF(
                stabilize_widget.x() - stabilize_ix * self._scale_x,
                stabilize_widget.y() - stabilize_iy * self._scale_y,
            )

        self._clamp_view_origin()
        self._view_initialized = True
        self._sync_pixel_offset()

    def _sync_pixel_offset(self) -> None:
        self._image_offset.setX(int(round(self._view_origin_f.x())))
        self._image_offset.setY(int(round(self._view_origin_f.y())))

    def _clamp_view_origin(self) -> None:
        """Keep at least image edges reachable; allow letterboxing."""
        if not self._scaled_pixmap:
            return
        ww, wh = max(1, self.width()), max(1, self.height())
        dw, dh = self._scaled_pixmap.width(), self._scaled_pixmap.height()
        ox, oy = self._view_origin_f.x(), self._view_origin_f.y()

        lo_x = float(min(0, ww - dw))
        hi_x = float(max(0.0, float(ww - dw)))
        lo_y = float(min(0, wh - dh))
        hi_y = float(max(0.0, float(wh - dh)))

        ox = min(hi_x, max(lo_x, ox))
        oy = min(hi_y, max(lo_y, oy))
        self._view_origin_f = QPointF(ox, oy)

    def resizeEvent(self, event):
        old_sz = event.oldSize()
        anchor_ix = None
        anchor_iy = None
        if (
            self._pixmap is not None
            and self._view_initialized
            and old_sz.isValid()
            and old_sz.width() > 0
            and old_sz.height() > 0
        ):
            piv = QPointF(old_sz.width() / 2.0, old_sz.height() / 2.0)
            anchor_ix = (piv.x() - self._view_origin_f.x()) / max(self._scale_x, 1e-12)
            anchor_iy = (piv.y() - self._view_origin_f.y()) / max(self._scale_y, 1e-12)

        super().resizeEvent(event)

        if self._pixmap is None:
            return

        if self._center_pending:
            self._apply_pending_center()
            return

        ww, wh = self.width(), self.height()
        if anchor_ix is not None and anchor_iy is not None and ww > 0 and wh > 0:
            center = QPoint(int(round(ww / 2.0)), int(round(wh / 2.0)))
            self._layout_view(center, anchor_ix, anchor_iy)
        elif self._view_initialized and ww > 0 and wh > 0:
            cx = ww / 2.0
            cy = wh / 2.0
            aix = (cx - self._view_origin_f.x()) / max(self._scale_x, 1e-12)
            aiy = (cy - self._view_origin_f.y()) / max(self._scale_y, 1e-12)
            self._layout_view(QPoint(int(round(cx)), int(round(cy))), aix, aiy)
        else:
            self._layout_view()
        self.update()

    def _widget_to_image_fractional(self, pos: QPoint) -> Tuple[float, float]:
        if self._slice_u16 is None or not self._scaled_pixmap:
            return 0.0, 0.0
        h, w = self._slice_u16.shape
        ox = self._view_origin_f.x()
        oy = self._view_origin_f.y()
        fx = (pos.x() - ox) / max(self._scale_x, 1e-12)
        fy = (pos.y() - oy) / max(self._scale_y, 1e-12)
        fx = float(np.clip(fx, 0.0, w - 1))
        fy = float(np.clip(fy, 0.0, h - 1))
        return fy, fx  # iy, ix

    def _widget_to_image(self, pos: QPoint) -> Tuple[int, int]:
        if self._slice_u16 is None or not self._scaled_pixmap:
            return 0, 0
        h, w = self._slice_u16.shape
        fy, fx = self._widget_to_image_fractional(pos)
        ix = int(np.clip(round(fx), 0, w - 1))
        iy = int(np.clip(round(fy), 0, h - 1))
        return iy, ix

    def _zoom_at_scroll(self, pivot: QPoint, angle_delta_y: int) -> None:
        if (
            self._pixmap is None
            or self._slice_u16 is None
            or angle_delta_y == 0
        ):
            return

        iy_f, ix_f = self._widget_to_image_fractional(pivot)

        factor = math.pow(float(self.ZOOM_WHEEL_FACTOR), angle_delta_y / 120.0)
        nz = float(self._zoom * factor)
        nz = min(float(self.MAX_ZOOM), max(float(self.MIN_ZOOM), nz))
        if abs(nz - self._zoom) < 1e-6:
            return
        self._zoom = nz
        self._layout_view(pivot, float(ix_f), float(iy_f))
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.fillRect(self.rect(), QColor(43, 43, 43))
        if not self._scaled_pixmap:
            painter.setPen(QColor(180, 180, 180))
            painter.drawText(self.rect(), Qt.AlignCenter, "Load a volume scan to begin")
            return

        painter.drawPixmap(self._image_offset, self._scaled_pixmap)

        if self._label_slice is not None and self._label_slice.max() > 0:
            self._draw_label_overlay(painter)

        if self._show_brush_cursor and self._cursor_pos is not None:
            self._draw_brush_cursor(painter)

        self._draw_axis_indicator(painter)

    def _draw_axis_indicator(self, painter: QPainter) -> None:
        """Small X→ / Y↓ legend in the bottom-left of the canvas."""
        if self._slice_u16 is None:
            return

        painter.save()
        painter.setRenderHint(QPainter.Antialiasing, True)
        margin = 14
        arm = 38
        ox = margin
        oy = self.height() - margin

        bg = QColor(20, 20, 20, 165)
        painter.setBrush(bg)
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(ox - 8, oy - arm - 22, arm + 60, arm + 36, 6, 6)

        axis_pen = QPen(QColor(230, 90, 90), 2)
        painter.setPen(axis_pen)
        painter.drawLine(ox, oy, ox + arm, oy)
        painter.drawLine(ox + arm, oy, ox + arm - 5, oy - 4)
        painter.drawLine(ox + arm, oy, ox + arm - 5, oy + 4)

        axis_pen = QPen(QColor(90, 200, 110), 2)
        painter.setPen(axis_pen)
        painter.drawLine(ox, oy, ox, oy - arm)
        painter.drawLine(ox, oy - arm, ox - 4, oy - arm + 5)
        painter.drawLine(ox, oy - arm, ox + 4, oy - arm + 5)

        painter.setPen(QColor(245, 245, 245))
        font = painter.font()
        font.setBold(True)
        font.setPointSize(max(8, font.pointSize()))
        painter.setFont(font)
        painter.drawText(ox + arm + 4, oy + 5, "X")
        painter.drawText(ox - 4, oy - arm - 4, "Y")

        font.setBold(False)
        painter.setFont(font)
        painter.setPen(QColor(190, 190, 190))
        h, w = self._slice_u16.shape
        painter.drawText(
            ox + 14,
            oy - arm - 8,
            f"Z={self._z_index}  ({w}×{h} px)",
        )
        painter.restore()

    def _cursor_over_image(self, pos: QPoint) -> bool:
        if not self._scaled_pixmap:
            return False
        ox_f = float(self._view_origin_f.x())
        oy_f = float(self._view_origin_f.y())
        dw, dh = self._scaled_pixmap.width(), self._scaled_pixmap.height()
        return ox_f <= pos.x() < ox_f + dw and oy_f <= pos.y() < oy_f + dh

    def _draw_brush_cursor(self, painter: QPainter) -> None:
        if self._cursor_pos is None or self._slice_u16 is None:
            return

        iy, ix = self._widget_to_image(self._cursor_pos)
        cx = self._view_origin_f.x() + (ix + 0.5) * self._scale_x
        cy = self._view_origin_f.y() + (iy + 0.5) * self._scale_y
        r = self._brush_radius * ((self._scale_x + self._scale_y) * 0.5)

        if self._erase_mode:
            pen = QPen(QColor(255, 255, 255), 2, Qt.DashLine)
            fill = QColor(0, 200, 255, 55)
        else:
            color = distinct_class_color(self._current_class_id)
            pen = QPen(color.lighter(130), 2, Qt.SolidLine)
            fill = QColor(color.red(), color.green(), color.blue(), 70)

        painter.setPen(pen)
        painter.setBrush(fill)
        painter.setRenderHint(QPainter.Antialiasing, True)
        painter.drawEllipse(QPointF(cx, cy), r, r)

    def _draw_label_overlay(self, painter: QPainter) -> None:
        ls = self._label_slice
        h, w = ls.shape
        overlay = self._color_lut[ls]
        qimg = QImage(
            np.ascontiguousarray(overlay).data, w, h, w * 4, QImage.Format_RGBA8888
        )
        ov_pix = QPixmap.fromImage(qimg.copy())
        ov_scaled = ov_pix.scaled(
            self._scaled_pixmap.width(),
            self._scaled_pixmap.height(),
            Qt.IgnoreAspectRatio,
            Qt.FastTransformation,
        )
        painter.drawPixmap(self._image_offset, ov_scaled)

    def _emit_paint_point(self, iy: int, ix: int) -> None:
        self.stroke_segment.emit(
            self._z_index, [(iy, ix)], self._brush_radius, self._erase_mode
        )

    def _emit_paint_line(self, y0: int, x0: int, y1: int, x1: int) -> None:
        points = interpolate_brush_line(y0, x0, y1, x1, self._brush_radius)
        if points:
            self.stroke_segment.emit(
                self._z_index, points, self._brush_radius, self._erase_mode
            )

    def mousePressEvent(self, event: QMouseEvent):
        if (
            event.button() == Qt.MiddleButton
            and self._slice_u16 is not None
            and self._scaled_pixmap is not None
        ):
            self.setFocus()
            self._middle_panning = True
            self._middle_last_pos = QPoint(event.pos())
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return

        if event.button() == Qt.LeftButton and self._slice_u16 is not None:
            self.setFocus()
            self._painting = True
            self.grabMouse()
            self.stroke_started.emit(self._z_index)
            iy, ix = self._widget_to_image(event.pos())
            self._last_paint_pos = (iy, ix)
            self._emit_paint_point(iy, ix)

    def _update_brush_cursor(self, pos: QPoint) -> None:
        if self._slice_u16 is None:
            return
        over = self._cursor_over_image(pos)
        if over:
            self._cursor_pos = pos
            self._show_brush_cursor = True
        else:
            self._cursor_pos = None
            self._show_brush_cursor = False
        if not self._painting:
            self.update()

    def mouseMoveEvent(self, event: QMouseEvent):
        if self._middle_panning:
            dp = QPoint(event.pos() - self._middle_last_pos)
            self._middle_last_pos = QPoint(event.pos())
            self._view_origin_f = QPointF(
                self._view_origin_f.x() + dp.x(),
                self._view_origin_f.y() + dp.y(),
            )
            self._clamp_view_origin()
            self._sync_pixel_offset()
            self.update()
            event.accept()
            return

        self._update_brush_cursor(event.pos())

        if not self._painting or self._slice_u16 is None:
            return
        if not (event.buttons() & Qt.LeftButton):
            self._end_stroke()
            return

        iy, ix = self._widget_to_image(event.pos())
        if self._last_paint_pos is not None:
            ly, lx = self._last_paint_pos
            if ly != iy or lx != ix:
                self._emit_paint_line(ly, lx, iy, ix)
        else:
            self._emit_paint_point(iy, ix)
        self._last_paint_pos = (iy, ix)

    def mouseReleaseEvent(self, event: QMouseEvent):
        if event.button() == Qt.MiddleButton and self._middle_panning:
            self._middle_panning = False
            self.unsetCursor()
            event.accept()
            return

        if event.button() == Qt.LeftButton and self._painting:
            self._end_stroke()

    def leaveEvent(self, event):
        # Keep painting while button held even if cursor briefly leaves widget
        if self._painting and not (self.mouseButtons() & Qt.LeftButton):
            self._end_stroke()
        if not self._middle_panning:
            self._show_brush_cursor = False
            self._cursor_pos = None
            if not self._painting:
                self.update()
        super().leaveEvent(event)

    def _end_stroke(self) -> None:
        if not self._painting:
            return
        self._painting = False
        self._last_paint_pos = None
        if self.mouseGrabber() == self:
            self.releaseMouse()
        self.stroke_ended.emit()

    def wheelEvent(self, event):
        if self._slice_u16 is None:
            return
        delta = event.angleDelta().y()
        if event.modifiers() & Qt.ControlModifier:
            self._zoom_at_scroll(event.pos(), delta)
            event.accept()
            return
        if delta > 0:
            self._brush_radius = min(128, self._brush_radius + 1)
        elif delta < 0:
            self._brush_radius = max(1, self._brush_radius - 1)
        event.accept()
        self.update()

    def keyPressEvent(self, event: QKeyEvent) -> None:
        if event.key() == Qt.Key_Home and self._pixmap is not None:
            self.reset_view_zoom()
            event.accept()
            return
        super().keyPressEvent(event)
