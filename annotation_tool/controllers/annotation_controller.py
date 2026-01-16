"""
Controller for managing annotations and their interactions.
"""
from typing import Optional
from PyQt5.QtCore import QObject, pyqtSignal
from ..models import BoundingBox, AnnotationModel
from ..views import ImageCanvas, ControlPanel


class AnnotationController(QObject):
    """
    Controller for managing annotation-related operations and UI interactions.
    """
    
    # Signals
    annotation_saved = pyqtSignal()
    status_message = pyqtSignal(str)
    annotation_selected = pyqtSignal(int)  # Emitted when annotation is selected
    
    def __init__(self, annotation_model: AnnotationModel, image_canvas: ImageCanvas, control_panel: ControlPanel):
        super().__init__()
        
        self._annotation_model = annotation_model
        self._image_canvas = image_canvas
        self._control_panel = control_panel
        self._current_image_path: Optional[str] = None
        
        self._connect_signals()
        self._update_views()
    
    def _connect_signals(self):
        """Connect model and view signals."""
        # Model signals
        self._annotation_model.annotations_changed.connect(self._update_views)
        self._annotation_model.annotation_added.connect(self._on_annotation_added)
        self._annotation_model.annotation_removed.connect(self._on_annotation_removed)
        self._annotation_model.annotation_modified.connect(self._on_annotation_modified)
        self._annotation_model.classes_loaded.connect(self._on_classes_loaded)
        
        # Canvas signals
        self._image_canvas.annotation_drawn.connect(self._on_annotation_drawn)
        self._image_canvas.annotation_selected.connect(self._on_annotation_selected)
        self._image_canvas.annotation_moved.connect(self._on_annotation_moved)
        self._image_canvas.right_clicked.connect(self._on_canvas_right_clicked)
        
        # Control panel signals
        self._control_panel.class_changed.connect(self._on_class_changed)
        self._control_panel.annotation_text_changed.connect(self._on_annotation_text_changed)
        self._control_panel.delete_annotation_requested.connect(self._on_delete_annotation_requested)
        self._control_panel.clear_all_requested.connect(self._on_clear_all_requested)
    
    def load_class_names(self, class_file_path: str) -> bool:
        """
        Load class names from file.
        
        Args:
            class_file_path: Path to class names file
            
        Returns:
            bool: True if loaded successfully
        """
        success = self._annotation_model.load_class_names(class_file_path)
        if success:
            self.status_message.emit(f"Loaded {len(self._annotation_model.class_names)} classes")
        else:
            self.status_message.emit("Failed to load class names")
        return success
    
    def set_class_names(self, class_names: list):
        """
        Set class names programmatically.
        
        Args:
            class_names: List of class names
        """
        self._annotation_model.set_class_names(class_names)
        self.status_message.emit(f"Set {len(class_names)} classes")
    
    def load_image_annotations(self, image_path: str) -> bool:
        """
        Load annotations for a specific image.
        
        Args:
            image_path: Path to image file
            
        Returns:
            bool: True if loaded successfully
        """
        self._current_image_path = image_path
        annotation_path = self._get_annotation_path(image_path)
        
        success = self._annotation_model.load_annotations(annotation_path)
        if success:
            annotation_count = len(self._annotation_model.annotations)
            self.status_message.emit(f"Loaded {annotation_count} annotations")
        
        return success
    
    def save_current_annotations(self) -> bool:
        """
        Save current annotations to file.
        
        Returns:
            bool: True if saved successfully
        """
        if not self._current_image_path:
            return False
        
        annotation_path = self._get_annotation_path(self._current_image_path)
        success = self._annotation_model.save_annotations(annotation_path)
        
        if success:
            self.annotation_saved.emit()
            annotation_count = len(self._annotation_model.annotations)
            self.status_message.emit(f"Saved {annotation_count} annotations")
        else:
            self.status_message.emit("Failed to save annotations")
        
        return success
    
    def _get_annotation_path(self, image_path: str) -> str:
        """Get annotation file path for given image path."""
        import os
        return os.path.splitext(image_path)[0] + ".txt"
    
    def _update_views(self):
        """Update all views with current model state."""
        annotations = self._annotation_model.annotations
        class_names = self._annotation_model.class_names
        selected_index = self._annotation_model.selected_annotation_index
        
        # Update canvas
        self._image_canvas.set_annotations(annotations, class_names)
        self._image_canvas.set_selected_annotation(selected_index)
        
        # Update control panel
        self._control_panel.update_annotation_list(annotations, class_names)
        self._control_panel.set_selected_annotation_in_list(selected_index)
        
        # Update current annotation info
        selected_annotation = self._annotation_model.selected_annotation
        self._control_panel.update_annotation_info(selected_index, selected_annotation, class_names)
        
        # Update current class
        if class_names:
            current_class_id = self._annotation_model.current_class_id
            self._control_panel.update_current_class(current_class_id, class_names)
    
    def _on_annotation_drawn(self, x1: int, y1: int, x2: int, y2: int):
        """Handle new annotation drawn on canvas."""
        if not self._current_image_path:
            return
        
        # Load image to get dimensions
        from PyQt5.QtGui import QPixmap
        pixmap = QPixmap(self._current_image_path)
        if pixmap.isNull():
            return
        
        # Create bounding box
        bbox = BoundingBox.from_absolute_coords(
            x1, y1, x2, y2,
            pixmap.width(), pixmap.height(),
            self._annotation_model.current_class_id
        )
        
        # Add to model (record undo)
        index = self._annotation_model.add_annotation(bbox, record_undo=True)
        self.status_message.emit(f"Added annotation {index + 1}")
        
        # Auto-save
        self.save_current_annotations()
    
    def _on_annotation_selected(self, index: int):
        """Handle annotation selection on canvas."""
        self._annotation_model.set_selected_annotation(index)
        self.status_message.emit(f"Selected annotation {index + 1}")
        
        # Emit signal for Q&A integration
        self.annotation_selected.emit(index)
    
    def _on_annotation_moved(self, index: int, x1: int, y1: int, x2: int, y2: int):
        """Handle annotation moved on canvas."""
        if not self._current_image_path:
            return
        
        # Load image to get dimensions
        from PyQt5.QtGui import QPixmap
        pixmap = QPixmap(self._current_image_path)
        if pixmap.isNull():
            return
        
        # Get existing annotation
        annotations = self._annotation_model.annotations
        if 0 <= index < len(annotations):
            old_annotation = annotations[index]
            
            # Create updated bounding box
            bbox = BoundingBox.from_absolute_coords(
                x1, y1, x2, y2,
                pixmap.width(), pixmap.height(),
                old_annotation.class_id,
                old_annotation.text
            )
            
            # Update in model (record undo)
            self._annotation_model.modify_annotation(index, bbox, record_undo=True)
            self.status_message.emit(f"Moved annotation {index + 1}")
            
            # Auto-save
            self.save_current_annotations()
    
    def _on_canvas_right_clicked(self, x: int, y: int):
        """Handle right click on canvas (when not on annotation)."""
        self._annotation_model.set_selected_annotation(-1)
        self.status_message.emit("Deselected annotation")
    
    def _on_annotation_added(self, index: int):
        """Handle annotation added to model."""
        # Views are updated via _update_views()
        pass
    
    def _on_annotation_removed(self, index: int):
        """Handle annotation removed from model."""
        # Views are updated via _update_views()
        pass
    
    def _on_annotation_modified(self, index: int):
        """Handle annotation modified in model."""
        # Views are updated via _update_views()
        pass
    
    def _on_classes_loaded(self, class_names: list):
        """Handle classes loaded in model."""
        self._control_panel.update_class_list(class_names)
        if class_names:
            self._control_panel.update_current_class(0, class_names)
    
    def _on_class_changed(self, class_id: int):
        """Handle class selection changed in control panel."""
        if self._annotation_model.set_current_class_id(class_id):
            class_names = self._annotation_model.class_names
            if class_names and 0 <= class_id < len(class_names):
                self._control_panel.update_current_class(class_id, class_names)
                self.status_message.emit(f"Selected class: {class_names[class_id]}")
    
    def _on_annotation_text_changed(self, text: str):
        """Handle annotation text changed in control panel."""
        selected_annotation = self._annotation_model.selected_annotation
        selected_index = self._annotation_model.selected_annotation_index
        
        if selected_annotation and selected_index >= 0:
            # Create updated annotation
            updated_annotation = BoundingBox(
                selected_annotation.x,
                selected_annotation.y,
                selected_annotation.width,
                selected_annotation.height,
                selected_annotation.class_id,
                text
            )
            
            # Update in model (record undo)
            self._annotation_model.modify_annotation(selected_index, updated_annotation, record_undo=True)
            
            # Auto-save
            self.save_current_annotations()
    
    def _on_delete_annotation_requested(self):
        """Handle delete annotation request from control panel."""
        selected_index = self._annotation_model.selected_annotation_index
        if selected_index >= 0:
            if self._annotation_model.remove_annotation(selected_index, record_undo=True):
                self.status_message.emit(f"Deleted annotation {selected_index + 1}")
                # Auto-save
                self.save_current_annotations()
    
    def _on_clear_all_requested(self):
        """Handle clear all annotations request from control panel."""
        annotation_count = len(self._annotation_model.annotations)
        if annotation_count > 0:
            self._annotation_model.clear_annotations(record_undo=True)
            self.status_message.emit(f"Cleared {annotation_count} annotations")
            # Auto-save
            self.save_current_annotations()
    
    def get_annotation_stats(self) -> dict:
        """
        Get statistics about current annotations.
        
        Returns:
            dict: Statistics including counts by class
        """
        annotations = self._annotation_model.annotations
        class_names = self._annotation_model.class_names
        
        stats = {
            'total': len(annotations),
            'by_class': {}
        }
        
        for annotation in annotations:
            class_id = annotation.class_id
            class_name = self._annotation_model.get_class_name(class_id)
            
            if class_name not in stats['by_class']:
                stats['by_class'][class_name] = 0
            stats['by_class'][class_name] += 1
        
        return stats
    
    def get_current_annotation_index(self) -> int:
        """Get the currently selected annotation index."""
        return self._annotation_model.selected_annotation_index

