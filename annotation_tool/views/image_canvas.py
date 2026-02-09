"""
Image canvas widget for displaying and interacting with images and annotations.
"""
import os
import numpy as np
import cv2
from typing import Optional, Tuple
from PyQt5.QtWidgets import QWidget, QLabel, QVBoxLayout, QScrollArea
from PyQt5.QtCore import Qt, pyqtSignal, QRect, QPoint
from PyQt5.QtGui import QPainter, QPen, QPixmap, QFont, QColor, QBrush, QMouseEvent, QPaintEvent, QImage


class ImageCanvas(QWidget):
    """
    Widget for displaying images and drawing/editing bounding box annotations.
    """
    
    # Signals
    annotation_drawn = pyqtSignal(int, int, int, int)  # x1, y1, x2, y2
    annotation_selected = pyqtSignal(int)  # annotation index
    annotation_moved = pyqtSignal(int, int, int, int, int)  # index, x1, y1, x2, y2
    right_clicked = pyqtSignal(int, int)  # x, y coordinates
    canvas_clicked = pyqtSignal()  # Canvas was clicked (for clearing focus)
    
    def __init__(self):
        super().__init__()
        self._setup_ui()
        self._init_drawing_state()
    
    def _setup_ui(self):
        """Initialize the UI components."""
        # Make canvas resizable with reasonable minimum size
        self.setMinimumSize(400, 300)
        self.setStyleSheet("background-color: #2b2b2b;")
        self.setMouseTracking(True)
        
        # Current state
        self._pixmap: Optional[QPixmap] = None
        self._scaled_pixmap: Optional[QPixmap] = None
        self._scale_factor: float = 1.0
        self._image_offset: QPoint = QPoint(0, 0)
        
        # Annotation data
        self._annotations = []
        self._class_names = []
        self._selected_annotation_index = -1
        self._highlighted_indices = set()  # Set of indices to highlight (for selection dialog)
        
        # Drawing settings
        self._pen_width = 2
        self._annotation_colors = [
            QColor(0, 255, 0),    # Green
            QColor(0, 0, 255),    # Blue
            QColor(255, 255, 0),  # Yellow
            QColor(255, 0, 255),  # Magenta
            QColor(0, 255, 255),  # Cyan
            QColor(255, 128, 0),  # Orange
            QColor(128, 0, 255),  # Purple
            QColor(128, 255, 128), # Light Green
            QColor(128, 128, 255), # Light Blue
            QColor(255, 255, 128), # Light Yellow
        ]
        self._selected_color = QColor(255, 0, 0)  # Red for selected
        
        # Magnification settings
        self._magnification_enabled = False
        self._magnification_size = 200
        self._magnification_scale = 4.0
        self._magnification_method = 'bicubic'
        self._magnification_methods = {
            'nearest': cv2.INTER_NEAREST,    # Fastest but lowest quality
            'bilinear': cv2.INTER_LINEAR,    # Good balance of speed and quality
            'bicubic': cv2.INTER_CUBIC,      # Better quality, especially for smooth areas
            'lanczos': cv2.INTER_LANCZOS4    # Best quality, especially for sharp edges
        }
        self._last_mouse_pos = QPoint(0, 0)
    
    def _init_drawing_state(self):
        """Initialize drawing state variables."""
        self._drawing = False
        self._start_point: Optional[QPoint] = None
        self._end_point: Optional[QPoint] = None
        self._moving_annotation = False
        self._move_start_point: Optional[QPoint] = None
        self._moving_annotation_index = -1
    
    def load_image(self, image_path: str) -> bool:
        """
        Load and display an image.
        
        Args:
            image_path: Path to image file
            
        Returns:
            bool: True if loaded successfully
        """
        if not os.path.isfile(image_path):
            return False
        
        self._pixmap = QPixmap(image_path)
        if self._pixmap.isNull():
            return False
        
        self._fit_image_to_widget()
        self.update()
        return True
    
    def _fit_image_to_widget(self):
        """Scale image to fit widget while maintaining aspect ratio."""
        if not self._pixmap:
            return
        
        widget_size = self.size()
        image_size = self._pixmap.size()
        
        # Calculate scale factor to fit image in widget
        scale_x = widget_size.width() / image_size.width()
        scale_y = widget_size.height() / image_size.height()
        self._scale_factor = min(scale_x, scale_y, 1.0)  # Don't scale up
        
        # Calculate scaled size and offset for centering
        scaled_width = int(image_size.width() * self._scale_factor)
        scaled_height = int(image_size.height() * self._scale_factor)
        
        self._image_offset.setX((widget_size.width() - scaled_width) // 2)
        self._image_offset.setY((widget_size.height() - scaled_height) // 2)
        
        # Create scaled pixmap
        self._scaled_pixmap = self._pixmap.scaled(
            scaled_width, scaled_height,
            Qt.KeepAspectRatio, Qt.SmoothTransformation
        )
    
    def set_annotations(self, annotations, class_names):
        """
        Set annotations to display.
        
        Args:
            annotations: List of BoundingBox objects
            class_names: List of class names
        """
        self._annotations = annotations
        self._class_names = class_names
        self._selected_annotation_index = -1
        self.update()
    
    def set_selected_annotation(self, index: int):
        """
        Set selected annotation index.
        
        Args:
            index: Annotation index (-1 for no selection)
        """
        self._selected_annotation_index = index
        self.update()
    
    def set_highlighted_indices(self, indices: set):
        """
        Set highlighted annotation indices (for selection dialog).
        
        Args:
            indices: Set of annotation indices to highlight
        """
        self._highlighted_indices = indices.copy() if indices else set()
        self.update()
    
    def clear_highlights(self):
        """Clear all highlighted annotations."""
        self._highlighted_indices.clear()
        self.update()
    
    def set_pen_width(self, width: int):
        """Set annotation box pen width."""
        self._pen_width = max(1, min(5, width))
        self.update()
    
    def toggle_magnification(self):
        """Toggle magnification on/off."""
        self._magnification_enabled = not self._magnification_enabled
        self.update()
        return self._magnification_enabled
    
    def set_magnification_scale(self, scale: float):
        """Set magnification scale."""
        self._magnification_scale = max(1.0, min(10.0, scale))
        self.update()
    
    def adjust_magnification_scale(self, delta: float):
        """Adjust magnification scale by delta."""
        new_scale = self._magnification_scale + delta
        self.set_magnification_scale(new_scale)
    
    def cycle_magnification_method(self):
        """Cycle through magnification interpolation methods."""
        methods = list(self._magnification_methods.keys())
        current_idx = methods.index(self._magnification_method)
        self._magnification_method = methods[(current_idx + 1) % len(methods)]
        self.update()
        return self._magnification_method
    
    def get_magnification_info(self):
        """Get current magnification information."""
        return {
            'enabled': self._magnification_enabled,
            'scale': self._magnification_scale,
            'method': self._magnification_method
        }
    
    def resizeEvent(self, event):
        """Handle widget resize."""
        super().resizeEvent(event)
        if self._pixmap:
            self._fit_image_to_widget()
    
    def paintEvent(self, event: QPaintEvent):
        """Paint the widget."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Fill background
        painter.fillRect(self.rect(), QColor(43, 43, 43))
        
        # Draw image
        if self._scaled_pixmap:
            painter.drawPixmap(self._image_offset, self._scaled_pixmap)
            
            # Draw annotations
            self._draw_annotations(painter)
            
            # Draw current drawing box
            if self._drawing and self._start_point and self._end_point:
                self._draw_current_box(painter)
            
            # Draw magnification window
            if self._magnification_enabled:
                self._draw_magnification(painter)
    
    def _draw_annotations(self, painter: QPainter):
        """Draw all annotations."""
        if not self._pixmap or not self._annotations:
            return
        
        font = QFont()
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        
        for i, annotation in enumerate(self._annotations):
            # Get absolute coordinates
            x1, y1, x2, y2 = annotation.to_absolute_coords(
                self._pixmap.width(), self._pixmap.height()
            )
            
            # Convert to widget coordinates
            widget_x1 = int(x1 * self._scale_factor + self._image_offset.x())
            widget_y1 = int(y1 * self._scale_factor + self._image_offset.y())
            widget_x2 = int(x2 * self._scale_factor + self._image_offset.x())
            widget_y2 = int(y2 * self._scale_factor + self._image_offset.y())
            
            # Choose color and pen width
            # Priority: selected > highlighted (from dialog) > normal
            if i == self._selected_annotation_index:
                color = self._selected_color
                pen_width = self._pen_width + 2  # Make selected boxes thicker
            elif i in self._highlighted_indices:
                color = self._selected_color  # Red for highlighted boxes
                pen_width = self._pen_width + 1  # Slightly thicker for highlighted
            else:
                color = self._annotation_colors[annotation.class_id % len(self._annotation_colors)]
                pen_width = self._pen_width
            
            # Draw bounding box
            pen = QPen(color, pen_width)
            painter.setPen(pen)
            painter.drawRect(widget_x1, widget_y1, widget_x2 - widget_x1, widget_y2 - widget_y1)
            
            # Draw class label
            class_name = self._get_class_name(annotation.class_id)
            label_text = f"{annotation.class_id}: {class_name}"
            
            # Draw label background
            text_rect = painter.fontMetrics().boundingRect(label_text)
            label_rect = QRect(widget_x1, widget_y1 - text_rect.height() - 5,
                             text_rect.width() + 6, text_rect.height() + 4)
            
            painter.fillRect(label_rect, QBrush(color))
            
            # Draw label text - use complementary color for better visibility
            text_color = self._get_complementary_color(color)
            painter.setPen(QPen(text_color))
            painter.drawText(label_rect.adjusted(3, 2, -3, -2), Qt.AlignLeft | Qt.AlignTop, label_text)
            
            # Note: Textual description is not displayed on canvas
            # Text descriptions are managed through the control panel only
    
    def _draw_current_box(self, painter: QPainter):
        """Draw the box currently being drawn."""
        pen = QPen(QColor(0, 255, 0), self._pen_width)
        painter.setPen(pen)
        
        x1 = min(self._start_point.x(), self._end_point.x())
        y1 = min(self._start_point.y(), self._end_point.y())
        x2 = max(self._start_point.x(), self._end_point.x())
        y2 = max(self._start_point.y(), self._end_point.y())
        
        painter.drawRect(x1, y1, x2 - x1, y2 - y1)
    
    def _draw_magnification(self, painter: QPainter):
        """Draw magnification window."""
        if not self._pixmap:
            return
        
        # Get mouse position in widget coordinates
        mx = self._last_mouse_pos.x()
        my = self._last_mouse_pos.y()
        
        # Convert to image coordinates
        image_x = (mx - self._image_offset.x()) / self._scale_factor
        image_y = (my - self._image_offset.y()) / self._scale_factor
        
        # Clamp to image bounds
        image_x = max(0, min(self._pixmap.width() - 1, image_x))
        image_y = max(0, min(self._pixmap.height() - 1, image_y))
        
        # Calculate region to magnify
        half_size = int(self._magnification_size / (2 * self._magnification_scale))
        mag_x1 = max(0, int(image_x - half_size))
        mag_y1 = max(0, int(image_y - half_size))
        mag_x2 = min(self._pixmap.width(), int(image_x + half_size))
        mag_y2 = min(self._pixmap.height(), int(image_y + half_size))
        
        if mag_x2 <= mag_x1 or mag_y2 <= mag_y1:
            return
        
        # Convert QPixmap to numpy array for processing
        qimage = self._pixmap.toImage()
        width = qimage.width()
        height = qimage.height()
        
        # Convert QImage to format compatible with OpenCV
        qimage = qimage.convertToFormat(qimage.Format_RGB888)
        
        # Extract the region
        ptr = qimage.bits()
        ptr.setsize(height * width * 3)
        arr = np.frombuffer(ptr, np.uint8).reshape((height, width, 3))
        
        # Extract magnification region
        mag_region = arr[mag_y1:mag_y2, mag_x1:mag_x2]
        
        if mag_region.size == 0:
            return
        
        # Resize using OpenCV
        interpolation = self._magnification_methods[self._magnification_method]
        magnified = cv2.resize(mag_region, 
                             (self._magnification_size, self._magnification_size),
                             interpolation=interpolation)
        
        # Convert back to QImage
        h, w, ch = magnified.shape
        bytes_per_line = ch * w
        qt_image = QImage(magnified.data, w, h, bytes_per_line, QImage.Format_RGB888)
        
        # Convert to QPixmap
        mag_pixmap = QPixmap.fromImage(qt_image)
        
        # Calculate position for magnification window
        mag_x = min(mx + 20, self.width() - self._magnification_size)
        mag_y = min(my + 20, self.height() - self._magnification_size)
        
        # Ensure magnification window stays in widget bounds
        mag_x = max(0, mag_x)
        mag_y = max(0, mag_y)
        
        # Draw border
        border_rect = QRect(mag_x - 1, mag_y - 1, 
                           self._magnification_size + 2, self._magnification_size + 2)
        painter.fillRect(border_rect, QColor(255, 255, 255))
        
        # Draw magnified region
        mag_rect = QRect(mag_x, mag_y, self._magnification_size, self._magnification_size)
        painter.drawPixmap(mag_rect, mag_pixmap)
        
        # Draw scale and method info
        scale_text = f"{self._magnification_scale:.1f}x {self._magnification_method}"
        font = QFont()
        font.setPointSize(10)
        font.setBold(True)
        painter.setFont(font)
        
        # Calculate text position
        text_rect = painter.fontMetrics().boundingRect(scale_text)
        text_x = mag_x + (self._magnification_size - text_rect.width()) // 2
        text_y = mag_y + self._magnification_size + 20
        
        # Draw text background
        bg_rect = QRect(text_x - 2, text_y - text_rect.height() - 2,
                       text_rect.width() + 4, text_rect.height() + 4)
        painter.fillRect(bg_rect, QColor(0, 0, 0, 180))
        
        # Draw text
        painter.setPen(QPen(QColor(255, 255, 255)))
        painter.drawText(text_x, text_y, scale_text)
    
    def _get_class_name(self, class_id: int) -> str:
        """Get class name for given ID."""
        if 0 <= class_id < len(self._class_names):
            return self._class_names[class_id]
        return "Unknown"
    
    def _get_complementary_color(self, background_color: QColor) -> QColor:
        """
        Get complementary text color for better contrast.
        Uses perceptual luminance to determine if text should be black or white.
        """
        # Calculate relative luminance using the sRGB formula
        r = background_color.red() / 255.0
        g = background_color.green() / 255.0
        b = background_color.blue() / 255.0
        
        # Apply gamma correction
        def gamma_correct(c):
            if c <= 0.03928:
                return c / 12.92
            else:
                return pow((c + 0.055) / 1.055, 2.4)
        
        r_linear = gamma_correct(r)
        g_linear = gamma_correct(g)
        b_linear = gamma_correct(b)
        
        # Calculate luminance
        luminance = 0.2126 * r_linear + 0.7152 * g_linear + 0.0722 * b_linear
        
        # Use white text on dark backgrounds, black text on light backgrounds
        if luminance > 0.5:
            return QColor(0, 0, 0)  # Black text
        else:
            return QColor(255, 255, 255)  # White text
    
    def _widget_to_image_coords(self, widget_point: QPoint) -> Tuple[int, int]:
        """Convert widget coordinates to image coordinates."""
        if not self._pixmap:
            return (0, 0)
        
        # Convert to image coordinates
        image_x = (widget_point.x() - self._image_offset.x()) / self._scale_factor
        image_y = (widget_point.y() - self._image_offset.y()) / self._scale_factor
        
        # Clamp to image bounds
        image_x = max(0, min(self._pixmap.width() - 1, image_x))
        image_y = max(0, min(self._pixmap.height() - 1, image_y))
        
        return (int(image_x), int(image_y))
    
    def _is_point_in_image(self, point: QPoint) -> bool:
        """Check if point is within the displayed image area."""
        if not self._scaled_pixmap:
            return False
        
        image_rect = QRect(
            self._image_offset,
            self._scaled_pixmap.size()
        )
        return image_rect.contains(point)
    
    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press events."""
        if not self._pixmap:
            return
        
        # Update mouse position for magnification
        self._last_mouse_pos = event.pos()
        self.update()  # Trigger redraw for magnification
        
        # Emit canvas clicked signal to clear focus from other widgets
        self.canvas_clicked.emit()
        
        if event.button() == Qt.LeftButton:
            if self._is_point_in_image(event.pos()):
                self._drawing = True
                self._start_point = event.pos()
                self._end_point = event.pos()
        
        elif event.button() == Qt.RightButton:
            if self._is_point_in_image(event.pos()):
                # Check if clicking on existing annotation
                image_x, image_y = self._widget_to_image_coords(event.pos())
                
                for i, annotation in enumerate(self._annotations):
                    if annotation.contains_point(image_x, image_y, self._pixmap.width(), self._pixmap.height()):
                        self.annotation_selected.emit(i)
                        self._moving_annotation = True
                        self._moving_annotation_index = i
                        self._move_start_point = event.pos()
                        return
                
                # No annotation found, emit right click signal
                self.right_clicked.emit(image_x, image_y)
    
    def mouseMoveEvent(self, event: QMouseEvent):
        """Handle mouse move events."""
        # Update mouse position for magnification
        self._last_mouse_pos = event.pos()
        
        if self._drawing and self._is_point_in_image(event.pos()):
            self._end_point = event.pos()
            self.update()
        
        elif self._moving_annotation and self._move_start_point:
            # Calculate movement delta
            delta = event.pos() - self._move_start_point
            self._move_start_point = event.pos()
            
            # Update annotation position
            if 0 <= self._moving_annotation_index < len(self._annotations):
                annotation = self._annotations[self._moving_annotation_index]
                
                # Convert delta to image coordinates
                delta_x = delta.x() / self._scale_factor
                delta_y = delta.y() / self._scale_factor
                
                # Update annotation center
                new_center_x = annotation.x * self._pixmap.width() + delta_x
                new_center_y = annotation.y * self._pixmap.height() + delta_y
                
                # Convert back to relative coordinates
                annotation.x = new_center_x / self._pixmap.width()
                annotation.y = new_center_y / self._pixmap.height()
                
                # Clamp to image bounds
                annotation.x = max(annotation.width / 2, min(1.0 - annotation.width / 2, annotation.x))
                annotation.y = max(annotation.height / 2, min(1.0 - annotation.height / 2, annotation.y))
                
                self.update()
        
        # Always update for magnification if enabled
        elif self._magnification_enabled:
            self.update()
    
    def mouseReleaseEvent(self, event: QMouseEvent):
        """Handle mouse release events."""
        if event.button() == Qt.LeftButton and self._drawing:
            if self._start_point and self._end_point and self._pixmap:
                # Convert to image coordinates
                start_x, start_y = self._widget_to_image_coords(self._start_point)
                end_x, end_y = self._widget_to_image_coords(self._end_point)
                
                # Ensure minimum size
                if abs(end_x - start_x) > 5 and abs(end_y - start_y) > 5:
                    x1, x2 = min(start_x, end_x), max(start_x, end_x)
                    y1, y2 = min(start_y, end_y), max(start_y, end_y)
                    
                    self.annotation_drawn.emit(x1, y1, x2, y2)
            
            self._drawing = False
            self._start_point = None
            self._end_point = None
            self.update()
        
        elif event.button() == Qt.RightButton and self._moving_annotation:
            if 0 <= self._moving_annotation_index < len(self._annotations):
                annotation = self._annotations[self._moving_annotation_index]
                x1, y1, x2, y2 = annotation.to_absolute_coords(
                    self._pixmap.width(), self._pixmap.height()
                )
                self.annotation_moved.emit(self._moving_annotation_index, x1, y1, x2, y2)
            
            self._moving_annotation = False
            self._moving_annotation_index = -1
            self._move_start_point = None
    
    def wheelEvent(self, event):
        """Handle mouse wheel events for magnification scale."""
        if self._magnification_enabled:
            # Get wheel delta
            delta = event.angleDelta().y() / 120  # Normalize wheel delta
            
            # Adjust magnification scale
            scale_delta = 0.5 * delta
            self.adjust_magnification_scale(scale_delta)
            
            # Accept the event to prevent scrolling
            event.accept()
        else:
            # Let parent handle if magnification is disabled
            super().wheelEvent(event)

