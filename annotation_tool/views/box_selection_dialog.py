"""
Dialog for selecting which bounding boxes to copy.
"""
from typing import List
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QCheckBox, QScrollArea, QWidget,
                            QGroupBox, QMessageBox)
from PyQt5.QtCore import Qt, pyqtSignal, QEvent
from PyQt5.QtGui import QFont
from ..models.bounding_box import BoundingBox


class HoverableCheckBox(QCheckBox):
    """CheckBox that emits hover signals."""
    hover_entered = pyqtSignal()
    hover_left = pyqtSignal()
    
    def enterEvent(self, event: QEvent):
        """Handle mouse entering the checkbox."""
        super().enterEvent(event)
        self.hover_entered.emit()
    
    def leaveEvent(self, event):
        """Handle mouse leaving the checkbox."""
        super().leaveEvent(event)
        self.hover_left.emit()


class BoxSelectionDialog(QDialog):
    """
    Dialog for selecting which bounding boxes to copy to the next image(s).
    """
    
    # Signals
    selection_changed = pyqtSignal(set)  # Emitted when selection changes, sends set of selected indices
    checkbox_hovered = pyqtSignal(int, bool)  # Emitted when hovering over checkbox, sends (index, is_entering)
    
    def __init__(self, annotations: List[BoundingBox], class_names: List[str], parent=None):
        """
        Initialize the dialog.
        
        Args:
            annotations: List of BoundingBox objects to select from
            class_names: List of class names for display
            parent: Parent widget
        """
        super().__init__(parent)
        self._annotations = annotations
        self._class_names = class_names
        self._checkboxes = []
        self._setup_ui()
    
    def _setup_ui(self):
        """Initialize the UI components."""
        self.setWindowTitle("Select Boxes to Copy")
        self.setMinimumSize(500, 400)
        
        # Main layout
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(10)
        
        # Instructions label
        instructions = QLabel("Select the bounding boxes you want to copy to the next image(s):")
        instructions.setWordWrap(True)
        instructions.setStyleSheet("font-weight: bold; padding: 5px;")
        main_layout.addWidget(instructions)
        
        # Scroll area for checkboxes
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setMinimumHeight(300)
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        scroll_layout.setSpacing(5)
        
        # Create checkboxes for each annotation
        if not self._annotations:
            no_boxes_label = QLabel("No annotations available to copy.")
            no_boxes_label.setAlignment(Qt.AlignCenter)
            scroll_layout.addWidget(no_boxes_label)
        else:
            for i, bbox in enumerate(self._annotations):
                # Create hoverable checkbox with box information
                checkbox = HoverableCheckBox()
                checkbox.setChecked(True)  # All boxes selected by default
                
                # Get class name
                class_name = "Unknown"
                if 0 <= bbox.class_id < len(self._class_names):
                    class_name = self._class_names[bbox.class_id]
                
                # Format box info
                box_info = f"Box {i + 1}: Class {bbox.class_id} ({class_name})"
                if bbox.text:
                    box_info += f" - {bbox.text[:50]}"  # Truncate long text
                
                checkbox.setText(box_info)
                checkbox.setToolTip(
                    f"Class: {class_name}\n"
                    f"Position: ({bbox.x:.3f}, {bbox.y:.3f})\n"
                    f"Size: {bbox.width:.3f} x {bbox.height:.3f}\n"
                    f"Text: {bbox.text if bbox.text else 'No description'}"
                )
                
                # Connect checkbox state change
                checkbox.stateChanged.connect(lambda state, idx=i: self._on_checkbox_changed(idx, state))
                
                # Connect hover events for visual feedback
                checkbox.hover_entered.connect(lambda idx=i: self._on_checkbox_enter(idx))
                checkbox.hover_left.connect(lambda idx=i: self._on_checkbox_leave(idx))
                
                self._checkboxes.append(checkbox)
                scroll_layout.addWidget(checkbox)
        
        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_widget)
        main_layout.addWidget(scroll_area)
        
        # Select All / Deselect All buttons
        select_buttons_layout = QHBoxLayout()
        
        select_all_btn = QPushButton("Select All")
        select_all_btn.clicked.connect(self._select_all)
        select_buttons_layout.addWidget(select_all_btn)
        
        deselect_all_btn = QPushButton("Deselect All")
        deselect_all_btn.clicked.connect(self._deselect_all)
        select_buttons_layout.addWidget(deselect_all_btn)
        
        select_buttons_layout.addStretch()
        main_layout.addLayout(select_buttons_layout)
        
        # Dialog buttons
        button_layout = QHBoxLayout()
        button_layout.addStretch()
        
        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)
        button_layout.addWidget(cancel_btn)
        
        ok_btn = QPushButton("Copy Selected")
        ok_btn.setDefault(True)
        ok_btn.clicked.connect(self._on_ok_clicked)
        button_layout.addWidget(ok_btn)
        
        main_layout.addLayout(button_layout)
        
        # Apply dark theme
        self._apply_dark_theme()
        
        # Emit initial selection (all boxes are selected by default)
        if self._annotations:
            initial_selection = set(range(len(self._annotations)))
            self.selection_changed.emit(initial_selection)
    
    def _apply_dark_theme(self):
        """Apply dark theme to the dialog."""
        dark_stylesheet = """
        QDialog {
            background-color: #2b2b2b;
            color: #ffffff;
        }
        QLabel {
            color: #ffffff;
        }
        QCheckBox {
            color: #ffffff;
            padding: 5px;
        }
        QCheckBox::indicator {
            width: 18px;
            height: 18px;
        }
        QCheckBox::indicator:unchecked {
            background-color: #3c3c3c;
            border: 2px solid #555555;
        }
        QCheckBox::indicator:checked {
            background-color: #4CAF50;
            border: 2px solid #4CAF50;
        }
        QPushButton {
            background-color: #3c3c3c;
            color: #ffffff;
            border: 1px solid #555555;
            padding: 8px 16px;
            border-radius: 4px;
        }
        QPushButton:hover {
            background-color: #4c4c4c;
        }
        QPushButton:pressed {
            background-color: #2c2c2c;
        }
        QPushButton:default {
            background-color: #4CAF50;
            border: 1px solid #4CAF50;
        }
        QPushButton:default:hover {
            background-color: #45a049;
        }
        QScrollArea {
            border: 1px solid #555555;
            background-color: #2b2b2b;
        }
        """
        self.setStyleSheet(dark_stylesheet)
    
    def _select_all(self):
        """Select all checkboxes."""
        # Block signals temporarily to avoid multiple updates
        for checkbox in self._checkboxes:
            checkbox.blockSignals(True)
            checkbox.setChecked(True)
            checkbox.blockSignals(False)
        # Emit one update after all changes
        selected_indices = self.get_selected_indices()
        self.selection_changed.emit(set(selected_indices))
    
    def _deselect_all(self):
        """Deselect all checkboxes."""
        # Block signals temporarily to avoid multiple updates
        for checkbox in self._checkboxes:
            checkbox.blockSignals(True)
            checkbox.setChecked(False)
            checkbox.blockSignals(False)
        # Emit one update after all changes
        selected_indices = self.get_selected_indices()
        self.selection_changed.emit(set(selected_indices))
    
    def _on_checkbox_changed(self, index: int, state: int):
        """Handle checkbox state change."""
        # Emit signal with current selection
        selected_indices = self.get_selected_indices()
        self.selection_changed.emit(set(selected_indices))
    
    def _on_checkbox_enter(self, index: int):
        """Handle mouse entering checkbox area."""
        # Highlight just this box temporarily
        self.checkbox_hovered.emit(index, True)
    
    def _on_checkbox_leave(self, index: int):
        """Handle mouse leaving checkbox area."""
        # Return to showing all selected boxes
        self.checkbox_hovered.emit(index, False)
        # Update highlights to show current selection
        selected_indices = self.get_selected_indices()
        self.selection_changed.emit(set(selected_indices))
    
    def _on_ok_clicked(self):
        """Handle OK button click."""
        # Check if at least one box is selected
        selected_count = sum(1 for cb in self._checkboxes if cb.isChecked())
        if selected_count == 0:
            QMessageBox.warning(self, "No Selection", "Please select at least one box to copy.")
            return
        
        self.accept()
    
    def get_selected_indices(self) -> List[int]:
        """
        Get indices of selected boxes.
        
        Returns:
            List of indices of selected annotations
        """
        selected = []
        for i, checkbox in enumerate(self._checkboxes):
            if checkbox.isChecked():
                selected.append(i)
        return selected
    
    def get_selected_annotations(self) -> List[BoundingBox]:
        """
        Get list of selected bounding boxes.
        
        Returns:
            List of selected BoundingBox objects
        """
        selected = []
        for i, checkbox in enumerate(self._checkboxes):
            if checkbox.isChecked():
                selected.append(self._annotations[i])
        return selected
