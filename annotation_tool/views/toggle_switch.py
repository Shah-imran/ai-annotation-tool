"""
Custom toggle switch widget for PyQt5.
"""
from PyQt5.QtWidgets import QCheckBox
from PyQt5.QtCore import Qt, QRect
from PyQt5.QtGui import QPainter, QColor, QBrush, QMouseEvent


class ToggleSwitch(QCheckBox):
    """Custom toggle switch widget that looks like a modern switch."""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setMinimumSize(50, 24)
        self.setMaximumSize(50, 24)
        # Remove default text spacing
        self.setText("")
        # Make the entire widget clickable
        self.setStyleSheet("QCheckBox::indicator { width: 0px; height: 0px; }")
        
    def mousePressEvent(self, event: QMouseEvent):
        """Handle mouse press - make entire area clickable."""
        if event.button() == Qt.LeftButton:
            # Toggle the state when clicking anywhere on the widget
            self.setChecked(not self.isChecked())
        super().mousePressEvent(event)
        
    def paintEvent(self, event):
        """Custom paint event to draw the toggle switch."""
        # Don't call super().paintEvent() to avoid default checkbox painting
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        
        # Get the widget rectangle
        rect = self.rect()
        width = rect.width()
        height = rect.height()
        
        # Draw background (track)
        if self.isChecked():
            # Green when checked
            track_color = QColor(76, 175, 80)  # #4CAF50
        else:
            # Gray when unchecked
            track_color = QColor(102, 102, 102)  # #666666
        
        # Draw rounded rectangle for track
        painter.setBrush(QBrush(track_color))
        painter.setPen(Qt.NoPen)
        painter.drawRoundedRect(0, 0, width, height, height // 2, height // 2)
        
        # Draw the thumb (circle)
        thumb_radius = (height - 4) // 2
        if self.isChecked():
            # Position on the right when checked
            thumb_x = width - thumb_radius - 2
        else:
            # Position on the left when unchecked
            thumb_x = thumb_radius + 2
        
        thumb_y = height // 2
        
        # Draw white circle for thumb
        painter.setBrush(QBrush(QColor(255, 255, 255)))
        painter.setPen(Qt.NoPen)
        painter.drawEllipse(thumb_x - thumb_radius, thumb_y - thumb_radius, 
                           thumb_radius * 2, thumb_radius * 2)
        
        # Draw hover effect if mouse is over
        if self.underMouse():
            hover_color = QColor(255, 255, 255, 30)
            painter.setBrush(QBrush(hover_color))
            painter.drawRoundedRect(0, 0, width, height, height // 2, height // 2)
