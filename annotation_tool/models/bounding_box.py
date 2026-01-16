"""
BoundingBox model class for storing annotation data.
"""
from typing import Optional
from dataclasses import dataclass


@dataclass
class BoundingBox:
    """
    Represents a bounding box annotation with text description.
    
    Coordinates are stored in YOLO format (relative coordinates):
    - x, y: center point (0.0 to 1.0)
    - width, height: box dimensions (0.0 to 1.0)
    """
    x: float
    y: float
    width: float
    height: float
    class_id: int
    text: str = ""
    
    def __post_init__(self):
        """Validate bounding box coordinates."""
        self.x = max(0.0, min(1.0, self.x))
        self.y = max(0.0, min(1.0, self.y))
        self.width = max(0.0, min(1.0, self.width))
        self.height = max(0.0, min(1.0, self.height))
    
    def to_absolute_coords(self, img_width: int, img_height: int) -> tuple:
        """
        Convert relative coordinates to absolute pixel coordinates.
        
        Returns:
            tuple: (x1, y1, x2, y2) in pixel coordinates
        """
        center_x = self.x * img_width
        center_y = self.y * img_height
        box_width = self.width * img_width
        box_height = self.height * img_height
        
        x1 = int(center_x - box_width / 2)
        y1 = int(center_y - box_height / 2)
        x2 = int(center_x + box_width / 2)
        y2 = int(center_y + box_height / 2)
        
        return (x1, y1, x2, y2)
    
    @classmethod
    def from_absolute_coords(cls, x1: int, y1: int, x2: int, y2: int, 
                           img_width: int, img_height: int, class_id: int, text: str = "") -> 'BoundingBox':
        """
        Create BoundingBox from absolute pixel coordinates.
        
        Args:
            x1, y1, x2, y2: Absolute pixel coordinates
            img_width, img_height: Image dimensions
            class_id: Class identifier
            text: Text description
            
        Returns:
            BoundingBox: New instance with relative coordinates
        """
        # Ensure coordinates are in correct order
        x1, x2 = min(x1, x2), max(x1, x2)
        y1, y2 = min(y1, y2), max(y1, y2)
        
        # Convert to relative coordinates
        center_x = (x1 + x2) / (2 * img_width)
        center_y = (y1 + y2) / (2 * img_height)
        width = (x2 - x1) / img_width
        height = (y2 - y1) / img_height
        
        return cls(center_x, center_y, width, height, class_id, text)
    
    def contains_point(self, x: float, y: float, img_width: int, img_height: int) -> bool:
        """
        Check if a point (in pixel coordinates) is inside this bounding box.
        
        Args:
            x, y: Point coordinates in pixels
            img_width, img_height: Image dimensions
            
        Returns:
            bool: True if point is inside the box
        """
        x1, y1, x2, y2 = self.to_absolute_coords(img_width, img_height)
        return x1 <= x <= x2 and y1 <= y <= y2
    
    def to_yolo_format(self) -> str:
        """
        Convert to YOLO annotation format string.
        
        Returns:
            str: YOLO format line (class_id x y width height text)
        """
        return f"{self.class_id} {self.x:.6f} {self.y:.6f} {self.width:.6f} {self.height:.6f} {self.text}"
    
    @classmethod
    def from_yolo_format(cls, line: str) -> Optional['BoundingBox']:
        """
        Create BoundingBox from YOLO format string.
        
        Args:
            line: YOLO format string
            
        Returns:
            BoundingBox or None if parsing fails
        """
        try:
            parts = line.strip().split()
            if len(parts) >= 5:
                class_id = int(parts[0])
                x, y, width, height = map(float, parts[1:5])
                text = ' '.join(parts[5:]) if len(parts) > 5 else ""
                return cls(x, y, width, height, class_id, text)
        except (ValueError, IndexError):
            pass
        return None
    
    def copy(self) -> 'BoundingBox':
        """Create a copy of this bounding box."""
        return BoundingBox(self.x, self.y, self.width, self.height, self.class_id, self.text)

