"""
Image model for managing loaded images and navigation.
"""
import os
import glob
from typing import List, Optional
from PyQt5.QtCore import QObject, pyqtSignal


class ImageModel(QObject):
    """
    Model for managing image files and current image state.
    """
    
    # Signals
    current_image_changed = pyqtSignal(int, str)  # index, filepath
    images_loaded = pyqtSignal(int)  # total count
    
    def __init__(self):
        super().__init__()
        self._image_files: List[str] = []
        self._current_index: int = 0
        self._supported_extensions = ['.jpg', '.jpeg', '.png', '.bmp', '.tiff', '.tif']
    
    @property
    def image_files(self) -> List[str]:
        """Get list of image file paths."""
        return self._image_files.copy()
    
    @property
    def current_index(self) -> int:
        """Get current image index."""
        return self._current_index
    
    @property
    def current_image_path(self) -> Optional[str]:
        """Get current image file path."""
        if 0 <= self._current_index < len(self._image_files):
            return self._image_files[self._current_index]
        return None
    
    @property
    def total_images(self) -> int:
        """Get total number of images."""
        return len(self._image_files)
    
    def load_images_from_directory(self, directory_path: str) -> bool:
        """
        Load image files from a directory.
        
        Args:
            directory_path: Path to directory containing images
            
        Returns:
            bool: True if images were loaded successfully
        """
        if not os.path.isdir(directory_path):
            return False
        
        image_files = []
        for ext in self._supported_extensions:
            pattern = os.path.join(directory_path, f"*{ext}")
            image_files.extend(glob.glob(pattern, recursive=False))
            pattern = os.path.join(directory_path, f"*{ext.upper()}")
            image_files.extend(glob.glob(pattern, recursive=False))
        
        # Remove duplicates and sort
        image_files = sorted(list(set(image_files)))
        
        if image_files:
            self._image_files = image_files
            self._current_index = 0
            self.images_loaded.emit(len(image_files))
            self.current_image_changed.emit(self._current_index, self._image_files[self._current_index])
            return True
        
        return False
    
    def load_images_from_file_list(self, file_list_path: str, base_directory: str = "") -> bool:
        """
        Load image files from a text file (like train.txt).
        
        Args:
            file_list_path: Path to text file containing image paths
            base_directory: Base directory for relative paths
            
        Returns:
            bool: True if images were loaded successfully
        """
        if not os.path.isfile(file_list_path):
            return False
        
        try:
            with open(file_list_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            image_files = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue
                
                # Handle relative paths
                if not os.path.isabs(line) and base_directory:
                    line = os.path.join(base_directory, line)
                
                # Check if file exists and has supported extension
                if os.path.isfile(line):
                    ext = os.path.splitext(line)[1].lower()
                    if ext in self._supported_extensions:
                        image_files.append(os.path.abspath(line))
            
            if image_files:
                self._image_files = image_files
                self._current_index = 0
                self.images_loaded.emit(len(image_files))
                self.current_image_changed.emit(self._current_index, self._image_files[self._current_index])
                return True
                
        except Exception as e:
            print(f"Error loading image list: {e}")
        
        return False
    
    def set_current_index(self, index: int) -> bool:
        """
        Set current image index.
        
        Args:
            index: New image index
            
        Returns:
            bool: True if index was valid and set
        """
        if 0 <= index < len(self._image_files):
            self._current_index = index
            self.current_image_changed.emit(self._current_index, self._image_files[self._current_index])
            return True
        return False
    
    def next_image(self) -> bool:
        """
        Move to next image.
        
        Returns:
            bool: True if moved successfully
        """
        return self.set_current_index((self._current_index + 1) % len(self._image_files))
    
    def previous_image(self) -> bool:
        """
        Move to previous image.
        
        Returns:
            bool: True if moved successfully
        """
        return self.set_current_index((self._current_index - 1) % len(self._image_files))
    
    def get_image_filename(self, index: Optional[int] = None) -> Optional[str]:
        """
        Get filename (without path) for an image.
        
        Args:
            index: Image index, uses current if None
            
        Returns:
            str: Filename or None if invalid index
        """
        if index is None:
            index = self._current_index
        
        if 0 <= index < len(self._image_files):
            return os.path.basename(self._image_files[index])
        return None
    
    def get_annotation_path(self, index: Optional[int] = None) -> Optional[str]:
        """
        Get corresponding annotation file path for an image.
        
        Args:
            index: Image index, uses current if None
            
        Returns:
            str: Annotation file path or None if invalid index
        """
        if index is None:
            index = self._current_index
        
        if 0 <= index < len(self._image_files):
            image_path = self._image_files[index]
            return os.path.splitext(image_path)[0] + ".txt"
        return None

