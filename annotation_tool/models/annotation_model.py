"""
Annotation model for managing bounding boxes and class information.
"""
import os
from typing import List, Optional, Dict
from PyQt5.QtCore import QObject, pyqtSignal
from .bounding_box import BoundingBox
from .undo_manager import UndoManager, ActionType


class AnnotationModel(QObject):
    """
    Model for managing annotations (bounding boxes) and class definitions.
    """
    
    # Signals
    annotations_changed = pyqtSignal()
    annotation_added = pyqtSignal(int)  # index of added annotation
    annotation_removed = pyqtSignal(int)  # index of removed annotation
    annotation_modified = pyqtSignal(int)  # index of modified annotation
    classes_loaded = pyqtSignal(list)  # list of class names
    
    def __init__(self):
        super().__init__()
        self._annotations: List[BoundingBox] = []
        self._class_names: List[str] = []
        self._current_class_id: int = 0
        self._selected_annotation_index: int = -1
        self._undo_manager = UndoManager()
    
    @property
    def annotations(self) -> List[BoundingBox]:
        """Get list of annotations."""
        return self._annotations.copy()
    
    @property
    def class_names(self) -> List[str]:
        """Get list of class names."""
        return self._class_names.copy()
    
    @property
    def current_class_id(self) -> int:
        """Get current class ID."""
        return self._current_class_id
    
    @property
    def selected_annotation_index(self) -> int:
        """Get index of selected annotation."""
        return self._selected_annotation_index
    
    @property
    def selected_annotation(self) -> Optional[BoundingBox]:
        """Get selected annotation."""
        if 0 <= self._selected_annotation_index < len(self._annotations):
            return self._annotations[self._selected_annotation_index]
        return None
    
    def load_class_names(self, class_file_path: str) -> bool:
        """
        Load class names from file.
        
        Args:
            class_file_path: Path to file containing class names
            
        Returns:
            bool: True if loaded successfully
        """
        if not os.path.isfile(class_file_path):
            return False
        
        try:
            with open(class_file_path, 'r', encoding='utf-8') as f:
                class_names = [line.strip() for line in f.readlines() if line.strip()]
            
            self._class_names = class_names
            self._current_class_id = 0 if class_names else 0
            self.classes_loaded.emit(class_names)
            return True
            
        except Exception as e:
            print(f"Error loading class names: {e}")
            return False
    
    def set_class_names(self, class_names: List[str]):
        """
        Set class names programmatically.
        
        Args:
            class_names: List of class names
        """
        self._class_names = class_names.copy()
        self._current_class_id = 0 if class_names else 0
        self.classes_loaded.emit(class_names)
    
    def set_current_class_id(self, class_id: int) -> bool:
        """
        Set current class ID.
        
        Args:
            class_id: New class ID
            
        Returns:
            bool: True if valid class ID
        """
        if 0 <= class_id < len(self._class_names):
            self._current_class_id = class_id
            return True
        return False
    
    def get_class_name(self, class_id: int) -> str:
        """
        Get class name for given ID.
        
        Args:
            class_id: Class ID
            
        Returns:
            str: Class name or "Unknown" if invalid ID
        """
        if 0 <= class_id < len(self._class_names):
            return self._class_names[class_id]
        return "Unknown"
    
    def add_annotation(self, bbox: BoundingBox, record_undo: bool = True) -> int:
        """
        Add new annotation.
        
        Args:
            bbox: BoundingBox to add
            record_undo: Whether to record this action for undo
            
        Returns:
            int: Index of added annotation
        """
        self._annotations.append(bbox)
        index = len(self._annotations) - 1
        self._selected_annotation_index = index
        
        # Record undo action
        if record_undo:
            self._undo_manager.push_action(
                ActionType.ADD_ANNOTATION,
                {"index": index, "bbox": bbox.copy()}
            )
        
        self.annotation_added.emit(index)
        self.annotations_changed.emit()
        return index
    
    def remove_annotation(self, index: int, record_undo: bool = True) -> bool:
        """
        Remove annotation at given index.
        
        Args:
            index: Index of annotation to remove
            record_undo: Whether to record this action for undo
            
        Returns:
            bool: True if removed successfully
        """
        if 0 <= index < len(self._annotations):
            removed_bbox = self._annotations[index].copy()
            old_selected = self._selected_annotation_index
            self._annotations.pop(index)
            
            # Adjust selected index
            if self._selected_annotation_index >= index:
                self._selected_annotation_index = max(-1, self._selected_annotation_index - 1)
            
            # Record undo action
            if record_undo:
                self._undo_manager.push_action(
                    ActionType.REMOVE_ANNOTATION,
                    {"index": index, "bbox": removed_bbox, "old_selected": old_selected}
                )
            
            self.annotation_removed.emit(index)
            self.annotations_changed.emit()
            return True
        return False
    
    def modify_annotation(self, index: int, bbox: BoundingBox, record_undo: bool = True) -> bool:
        """
        Modify annotation at given index.
        
        Args:
            index: Index of annotation to modify
            bbox: New BoundingBox data
            record_undo: Whether to record this action for undo
            
        Returns:
            bool: True if modified successfully
        """
        if 0 <= index < len(self._annotations):
            old_bbox = self._annotations[index].copy()
            self._annotations[index] = bbox
            
            # Record undo action
            if record_undo:
                self._undo_manager.push_action(
                    ActionType.MODIFY_ANNOTATION,
                    {"index": index, "old_bbox": old_bbox, "new_bbox": bbox.copy()}
                )
            
            self.annotation_modified.emit(index)
            self.annotations_changed.emit()
            return True
        return False
    
    def set_selected_annotation(self, index: int) -> bool:
        """
        Set selected annotation index.
        
        Args:
            index: Index to select (-1 for no selection)
            
        Returns:
            bool: True if valid index
        """
        if index == -1 or 0 <= index < len(self._annotations):
            self._selected_annotation_index = index
            return True
        return False
    
    def clear_annotations(self, record_undo: bool = True):
        """
        Clear all annotations.
        
        Args:
            record_undo: Whether to record this action for undo
        """
        if record_undo and self._annotations:
            # Save current state for undo
            saved_annotations = [bbox.copy() for bbox in self._annotations]
            old_selected = self._selected_annotation_index
            
            self._undo_manager.push_action(
                ActionType.CLEAR_ALL,
                {"annotations": saved_annotations, "old_selected": old_selected}
            )
        
        self._annotations.clear()
        self._selected_annotation_index = -1
        self.annotations_changed.emit()
    
    def find_annotation_at_point(self, x: float, y: float, img_width: int, img_height: int) -> int:
        """
        Find annotation containing the given point.
        
        Args:
            x, y: Point coordinates in pixels
            img_width, img_height: Image dimensions
            
        Returns:
            int: Index of annotation or -1 if none found
        """
        # Search in reverse order to prioritize recently added annotations
        for i in range(len(self._annotations) - 1, -1, -1):
            if self._annotations[i].contains_point(x, y, img_width, img_height):
                return i
        return -1
    
    def load_annotations(self, annotation_file_path: str) -> bool:
        """
        Load annotations from YOLO format file.
        
        Args:
            annotation_file_path: Path to annotation file
            
        Returns:
            bool: True if loaded successfully
        """
        self._annotations.clear()
        self._selected_annotation_index = -1
        # Clear undo stack when loading new annotations (new image)
        self._undo_manager.clear()
        
        if not os.path.isfile(annotation_file_path):
            self.annotations_changed.emit()
            return True  # No annotations file is valid
        
        try:
            with open(annotation_file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            for line in lines:
                bbox = BoundingBox.from_yolo_format(line)
                if bbox is not None:
                    self._annotations.append(bbox)
            
            self.annotations_changed.emit()
            return True
            
        except Exception as e:
            print(f"Error loading annotations: {e}")
            self._annotations.clear()
            self.annotations_changed.emit()
            return False
    
    def save_annotations(self, annotation_file_path: str) -> bool:
        """
        Save annotations to YOLO format file.
        
        Args:
            annotation_file_path: Path to save annotations
            
        Returns:
            bool: True if saved successfully
        """
        try:
            # Remove existing file if no annotations
            if not self._annotations and os.path.exists(annotation_file_path):
                os.remove(annotation_file_path)
                return True
            
            # Save annotations if any exist
            if self._annotations:
                with open(annotation_file_path, 'w', encoding='utf-8') as f:
                    for bbox in self._annotations:
                        f.write(bbox.to_yolo_format() + '\n')
            
            return True
            
        except Exception as e:
            print(f"Error saving annotations: {e}")
            return False
    
    def copy_annotation(self, index: int) -> Optional[BoundingBox]:
        """
        Create a copy of annotation at given index.
        
        Args:
            index: Index of annotation to copy
            
        Returns:
            BoundingBox: Copy of annotation or None if invalid index
        """
        if 0 <= index < len(self._annotations):
            return self._annotations[index].copy()
        return None
    
    def undo(self) -> bool:
        """
        Undo the last action.
        
        Returns:
            bool: True if an action was undone
        """
        action = self._undo_manager.pop_action()
        if not action:
            return False
        
        if action.action_type == ActionType.ADD_ANNOTATION:
            # Undo add: remove the annotation
            index = action.data["index"]
            if index < len(self._annotations):
                self._annotations.pop(index)
                if self._selected_annotation_index >= index:
                    self._selected_annotation_index = max(-1, self._selected_annotation_index - 1)
                self.annotation_removed.emit(index)
                self.annotations_changed.emit()
                return True
        
        elif action.action_type == ActionType.REMOVE_ANNOTATION:
            # Undo remove: restore the annotation
            index = action.data["index"]
            bbox = action.data["bbox"]
            old_selected = action.data.get("old_selected", -1)
            
            # Insert at original position
            self._annotations.insert(index, bbox)
            self._selected_annotation_index = old_selected
            self.annotation_added.emit(index)
            self.annotations_changed.emit()
            return True
        
        elif action.action_type == ActionType.MODIFY_ANNOTATION:
            # Undo modify: restore old bbox
            index = action.data["index"]
            old_bbox = action.data["old_bbox"]
            
            if 0 <= index < len(self._annotations):
                self._annotations[index] = old_bbox
                self.annotation_modified.emit(index)
                self.annotations_changed.emit()
                return True
        
        elif action.action_type == ActionType.CLEAR_ALL:
            # Undo clear: restore all annotations
            saved_annotations = action.data["annotations"]
            old_selected = action.data.get("old_selected", -1)
            
            self._annotations = saved_annotations
            self._selected_annotation_index = old_selected
            self.annotations_changed.emit()
            return True
        
        elif action.action_type == ActionType.COPY_BOXES_TO_NEXT:
            # Undo copy: this is handled in main controller
            # Just return True to indicate action was processed
            return True
        
        return False
    
    def can_undo(self) -> bool:
        """Check if there are actions to undo."""
        return self._undo_manager.can_undo()
    
    def redo(self) -> bool:
        """
        Redo the last undone action.
        
        Returns:
            bool: True if an action was redone
        """
        action = self._undo_manager.pop_redo_action()
        if not action:
            return False
        
        if action.action_type == ActionType.ADD_ANNOTATION:
            # Redo add: restore the annotation
            index = action.data["index"]
            bbox = action.data["bbox"]
            
            # Insert at original position
            self._annotations.insert(index, bbox)
            self._selected_annotation_index = index
            self.annotation_added.emit(index)
            self.annotations_changed.emit()
            return True
        
        elif action.action_type == ActionType.REMOVE_ANNOTATION:
            # Redo remove: remove the annotation again
            index = action.data["index"]
            if index < len(self._annotations):
                self._annotations.pop(index)
                if self._selected_annotation_index >= index:
                    self._selected_annotation_index = max(-1, self._selected_annotation_index - 1)
                self.annotation_removed.emit(index)
                self.annotations_changed.emit()
                return True
        
        elif action.action_type == ActionType.MODIFY_ANNOTATION:
            # Redo modify: apply the new bbox again
            index = action.data["index"]
            new_bbox = action.data["new_bbox"]
            
            if 0 <= index < len(self._annotations):
                self._annotations[index] = new_bbox
                self.annotation_modified.emit(index)
                self.annotations_changed.emit()
                return True
        
        elif action.action_type == ActionType.CLEAR_ALL:
            # Redo clear: clear all annotations again
            self._annotations.clear()
            self._selected_annotation_index = -1
            self.annotations_changed.emit()
            return True
        
        elif action.action_type == ActionType.COPY_BOXES_TO_NEXT:
            # Redo copy: this is handled in main controller
            # Just return True to indicate action was processed
            return True
        
        return False
    
    def can_redo(self) -> bool:
        """Check if there are actions to redo."""
        return self._undo_manager.can_redo()

