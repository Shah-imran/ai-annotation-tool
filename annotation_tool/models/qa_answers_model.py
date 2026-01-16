"""
Q&A Answers Model for managing question-answer pairs per bounding box.

This module handles saving and loading Q&A answers in separate JSON files,
with each entry containing image name, bounding box details, and answers.
"""

import json
import os
from typing import Dict, List, Any, Optional, Tuple
from PyQt5.QtCore import QObject, pyqtSignal


class QAAnswersModel(QObject):
    """Model for managing Q&A answers per bounding box."""
    
    # Signals
    answers_saved = pyqtSignal(str)     # Emitted when answers are saved (file_path)
    answers_loaded = pyqtSignal(str)    # Emitted when answers are loaded (file_path)
    
    def __init__(self):
        super().__init__()
        self._answers_folder: str = ""
        self._current_image_answers: Dict[str, Dict[str, str]] = {}  # bbox_id -> {question: answer}
        self._current_image_name: str = ""
    
    def set_answers_folder(self, folder_path: str):
        """
        Set the folder where Q&A answers will be saved.
        
        Args:
            folder_path: Path to the answers folder
        """
        self._answers_folder = folder_path
        if folder_path:
            os.makedirs(folder_path, exist_ok=True)
    
    def get_answers_folder(self) -> str:
        """
        Get the current answers folder path.
        
        Returns:
            str: Path to answers folder
        """
        return self._answers_folder
    
    def set_current_image(self, image_name: str):
        """
        Set the current image and load existing answers if any.
        
        Args:
            image_name: Name of the current image file
        """
        self._current_image_name = image_name
        self._current_image_answers = {}
        
        if image_name and self._answers_folder:
            self._load_answers_for_image(image_name)
    
    def _load_answers_for_image(self, image_name: str):
        """
        Load existing answers for an image.
        
        Args:
            image_name: Name of the image file
        """
        answers_file = self._get_answers_file_path(image_name)
        
        if os.path.isfile(answers_file):
            try:
                with open(answers_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                # Convert data to internal format: bbox_id -> {question: answer}
                for entry in data.get("entries", []):
                    bbox_id = entry.get("bbox_id", "")
                    answers = entry.get("answers", {})
                    if bbox_id:
                        self._current_image_answers[bbox_id] = answers
                
                print(f"Loaded Q&A answers for {image_name}: {len(self._current_image_answers)} bounding boxes")
                self.answers_loaded.emit(answers_file)
                
            except Exception as e:
                print(f"Error loading Q&A answers for {image_name}: {e}")
    
    def _get_answers_file_path(self, image_name: str) -> str:
        """
        Get the answers file path for an image.
        
        Args:
            image_name: Name of the image file
            
        Returns:
            str: Path to the answers JSON file
        """
        if not image_name or not self._answers_folder:
            return ""
        
        # Remove extension and add .qa.json
        base_name = os.path.splitext(image_name)[0]
        return os.path.join(self._answers_folder, f"{base_name}.qa.json")
    
    def _generate_bbox_id(self, bbox_index: int, class_id: int, x: float, y: float, width: float, height: float) -> str:
        """
        Generate a unique ID for a bounding box.
        
        Args:
            bbox_index: Index of the bounding box in the annotations list
            class_id: Class ID of the bounding box
            x, y, width, height: Normalized coordinates
            
        Returns:
            str: Unique bounding box ID
        """
        # Use a combination of index and coordinates for uniqueness
        return f"bbox_{bbox_index}_{class_id}_{x:.4f}_{y:.4f}_{width:.4f}_{height:.4f}"
    
    def set_answers_for_bbox(self, bbox_index: int, class_id: int, x: float, y: float, 
                           width: float, height: float, answers: Dict[str, str]):
        """
        Set answers for a specific bounding box.
        
        Args:
            bbox_index: Index of the bounding box
            class_id: Class ID of the bounding box
            x, y, width, height: Normalized coordinates
            answers: Dictionary of {question: answer}
        """
        bbox_id = self._generate_bbox_id(bbox_index, class_id, x, y, width, height)
        self._current_image_answers[bbox_id] = answers.copy()
    
    def get_answers_for_bbox(self, bbox_index: int, class_id: int, x: float, y: float, 
                           width: float, height: float) -> Dict[str, str]:
        """
        Get answers for a specific bounding box.
        
        Args:
            bbox_index: Index of the bounding box
            class_id: Class ID of the bounding box
            x, y, width, height: Normalized coordinates
            
        Returns:
            Dict[str, str]: Dictionary of {question: answer}
        """
        bbox_id = self._generate_bbox_id(bbox_index, class_id, x, y, width, height)
        return self._current_image_answers.get(bbox_id, {}).copy()
    
    def save_current_answers(self) -> bool:
        """
        Save all current answers to file.
        
        Returns:
            bool: True if saved successfully, False otherwise
        """
        if not self._current_image_name or not self._answers_folder:
            return False
        
        answers_file = self._get_answers_file_path(self._current_image_name)
        
        try:
            # Prepare data for saving
            entries = []
            for bbox_id, answers in self._current_image_answers.items():
                if answers:  # Only save if there are actual answers
                    entries.append({
                        "bbox_id": bbox_id,
                        "answers": answers
                    })
            
            data = {
                "image_name": self._current_image_name,
                "timestamp": self._get_current_timestamp(),
                "entries": entries
            }
            
            # Create directory if it doesn't exist
            os.makedirs(os.path.dirname(answers_file), exist_ok=True)
            
            # Save to file
            with open(answers_file, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            
            print(f"Saved Q&A answers for {self._current_image_name}: {len(entries)} bounding boxes")
            self.answers_saved.emit(answers_file)
            return True
            
        except Exception as e:
            print(f"Error saving Q&A answers: {e}")
            return False
    
    def _get_current_timestamp(self) -> str:
        """
        Get current timestamp as string.
        
        Returns:
            str: Current timestamp in ISO format
        """
        from datetime import datetime
        return datetime.now().isoformat()
    
    def clear_answers_for_bbox(self, bbox_index: int, class_id: int, x: float, y: float, 
                              width: float, height: float):
        """
        Clear answers for a specific bounding box.
        
        Args:
            bbox_index: Index of the bounding box
            class_id: Class ID of the bounding box
            x, y, width, height: Normalized coordinates
        """
        bbox_id = self._generate_bbox_id(bbox_index, class_id, x, y, width, height)
        if bbox_id in self._current_image_answers:
            del self._current_image_answers[bbox_id]
    
    def has_answers_for_bbox(self, bbox_index: int, class_id: int, x: float, y: float, 
                           width: float, height: float) -> bool:
        """
        Check if a bounding box has any answers.
        
        Args:
            bbox_index: Index of the bounding box
            class_id: Class ID of the bounding box
            x, y, width, height: Normalized coordinates
            
        Returns:
            bool: True if the bounding box has answers, False otherwise
        """
        bbox_id = self._generate_bbox_id(bbox_index, class_id, x, y, width, height)
        return bbox_id in self._current_image_answers and bool(self._current_image_answers[bbox_id])
    
    def get_total_answers_count(self) -> int:
        """
        Get the total number of bounding boxes with answers for current image.
        
        Returns:
            int: Number of bounding boxes with answers
        """
        return len(self._current_image_answers)
    
    def clear_all_answers(self):
        """Clear all answers for the current image."""
        self._current_image_answers = {}

