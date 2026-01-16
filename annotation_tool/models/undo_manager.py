"""
Undo Manager for tracking and reversing annotation operations.
"""
from typing import List, Optional, Dict, Any
from enum import Enum
from .bounding_box import BoundingBox


class ActionType(Enum):
    """Types of actions that can be undone."""
    ADD_ANNOTATION = "add_annotation"
    REMOVE_ANNOTATION = "remove_annotation"
    MODIFY_ANNOTATION = "modify_annotation"
    CLEAR_ALL = "clear_all"
    COPY_BOXES_TO_NEXT = "copy_boxes_to_next"


class UndoAction:
    """Represents an action that can be undone."""
    
    def __init__(self, action_type: ActionType, data: Dict[str, Any]):
        """
        Initialize an undo action.
        
        Args:
            action_type: Type of action
            data: Action-specific data needed to undo
        """
        self.action_type = action_type
        self.data = data


class UndoManager:
    """Manages undo/redo stack for annotation operations."""
    
    def __init__(self, max_history: int = 50):
        """
        Initialize undo manager.
        
        Args:
            max_history: Maximum number of actions to keep in history
        """
        self._undo_stack: List[UndoAction] = []
        self._max_history = max_history
    
    def push_action(self, action_type: ActionType, data: Dict[str, Any]):
        """
        Push an action onto the undo stack.
        
        Args:
            action_type: Type of action
            data: Action-specific data
        """
        action = UndoAction(action_type, data)
        self._undo_stack.append(action)
        
        # Limit stack size
        if len(self._undo_stack) > self._max_history:
            self._undo_stack.pop(0)
    
    def pop_action(self) -> Optional[UndoAction]:
        """
        Pop the last action from the undo stack.
        
        Returns:
            UndoAction or None if stack is empty
        """
        if self._undo_stack:
            return self._undo_stack.pop()
        return None
    
    def can_undo(self) -> bool:
        """Check if there are actions to undo."""
        return len(self._undo_stack) > 0
    
    def clear(self):
        """Clear the undo stack."""
        self._undo_stack.clear()
