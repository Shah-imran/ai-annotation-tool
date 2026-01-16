# Annotation Tool (Scan Lab)
"""
A modern image annotation tool built for Scan Lab using MVC architecture.

Features:
- Rectangular bounding box annotations
- Text descriptions for annotations  
- YOLO format support
- Keyboard shortcuts
- Auto-save functionality
"""

__version__ = "1.0.0"
__author__ = "Scan Lab"

from .models import BoundingBox, AnnotationModel, ImageModel
from .views import MainWindow, ImageCanvas, ControlPanel
from .controllers import AnnotationController, MainController

__all__ = [
    'BoundingBox', 'AnnotationModel', 'ImageModel',
    'MainWindow', 'ImageCanvas', 'ControlPanel', 
    'AnnotationController', 'MainController'
]

