"""
Questions Model for managing Q&A question sets.

This module handles loading and managing question sets from JSON files
for the Q&A feature.
"""

import json
import os
from typing import List, Dict, Any, Optional
from PyQt5.QtCore import QObject, pyqtSignal


class QuestionsModel(QObject):
    """Model for managing Q&A question sets."""
    
    # Signals
    questions_loaded = pyqtSignal(list)  # Emitted when questions are loaded
    questions_cleared = pyqtSignal()    # Emitted when questions are cleared
    
    def __init__(self):
        super().__init__()
        self._questions: List[Dict[str, Any]] = []  # Now stores question objects with options
        self._questions_file_path: str = ""
    
    def load_questions_from_file(self, file_path: str) -> bool:
        """
        Load questions from a JSON file.
        
        Expected format:
        {
            "questions": [
                "What is the object doing?",
                "Is the object damaged?",
                "What is the object's condition?"
            ]
        }
        
        Args:
            file_path: Path to the questions JSON file
            
        Returns:
            bool: True if loaded successfully, False otherwise
        """
        try:
            if not os.path.isfile(file_path):
                print(f"Questions file not found: {file_path}")
                return False
            
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            if "questions" not in data:
                print("Invalid questions file format: missing 'questions' key")
                return False
            
            questions = data["questions"]
            if not isinstance(questions, list):
                print("Invalid questions file format: 'questions' must be a list")
                return False
            
            # Normalize questions to new format (support both old and new formats)
            normalized_questions = []
            for i, question in enumerate(questions):
                if isinstance(question, str):
                    # Old format: simple string (no options - use text input)
                    normalized_questions.append({
                        "question": question,
                        "options": []  # Empty options means text input
                    })
                elif isinstance(question, dict):
                    # New format: object with question and options
                    if "question" not in question:
                        print(f"Invalid question at index {i}: missing 'question' field")
                        return False
                    if not isinstance(question["question"], str):
                        print(f"Invalid question at index {i}: 'question' must be a string")
                        return False
                    
                    options = question.get("options", [])
                    if not isinstance(options, list):
                        print(f"Invalid question at index {i}: 'options' must be a list")
                        return False
                    
                    # Validate all options are strings
                    for j, option in enumerate(options):
                        if not isinstance(option, str):
                            print(f"Invalid option at question {i}, option {j}: must be a string")
                            return False
                    
                    normalized_questions.append({
                        "question": question["question"],
                        "options": options
                    })
                else:
                    print(f"Invalid question at index {i}: must be a string or object")
                    return False
            
            self._questions = normalized_questions
            self._questions_file_path = file_path
            
            print(f"Loaded {len(self._questions)} questions from {file_path}")
            self.questions_loaded.emit(self._questions)
            return True
            
        except json.JSONDecodeError as e:
            print(f"Error parsing questions file: {e}")
            return False
        except Exception as e:
            print(f"Error loading questions file: {e}")
            return False
    
    def get_questions(self) -> List[Dict[str, Any]]:
        """
        Get the current list of questions.
        
        Returns:
            List[Dict[str, Any]]: List of question objects with 'question' and 'options' fields
        """
        return self._questions.copy()
    
    def get_questions_file_path(self) -> str:
        """
        Get the path of the currently loaded questions file.
        
        Returns:
            str: Path to questions file, empty if none loaded
        """
        return self._questions_file_path
    
    def clear_questions(self):
        """Clear all loaded questions."""
        self._questions = []
        self._questions_file_path = ""
        self.questions_cleared.emit()
    
    def has_questions(self) -> bool:
        """
        Check if any questions are loaded.
        
        Returns:
            bool: True if questions are loaded, False otherwise
        """
        return bool(self._questions)
    
    def get_question_count(self) -> int:
        """
        Get the number of loaded questions.
        
        Returns:
            int: Number of questions
        """
        return len(self._questions)
    
    def create_sample_questions_file(self, file_path: str) -> bool:
        """
        Create a sample questions file for reference.
        
        Args:
            file_path: Path where to create the sample file
            
        Returns:
            bool: True if created successfully, False otherwise
        """
        sample_data = {
            "questions": [
                {
                    "question": "What is the primary object in this bounding box?",
                    "options": ["Person", "Vehicle", "Equipment", "Tool", "Building", "Animal", "Other"]
                },
                {
                    "question": "What action or state is being demonstrated?",
                    "options": ["Active/Working", "Idle/Stationary", "Damaged/Broken", "Under Maintenance", "In Transit", "Unknown"]
                },
                {
                    "question": "Is there any damage or defect visible?",
                    "options": ["No damage", "Minor damage", "Moderate damage", "Severe damage", "Cannot determine"]
                },
                {
                    "question": "What is the approximate size category?",
                    "options": ["Small", "Medium", "Large", "Extra Large"]
                },
                {
                    "question": "Are there any safety concerns?",
                    "options": ["No concerns", "Minor concern", "Moderate concern", "High concern", "Critical concern"]
                },
                {
                    "question": "What materials can you identify?",
                    "options": ["Metal", "Plastic", "Wood", "Concrete", "Glass", "Fabric", "Mixed materials", "Unknown"]
                },
                {
                    "question": "Is this object functioning properly?",
                    "options": ["Yes, functioning", "No, not functioning", "Partially functioning", "Cannot determine"]
                },
                {
                    "question": "What is the overall condition?",
                    "options": ["Excellent", "Good", "Fair", "Poor", "Very Poor"]
                }
            ]
        }
        
        try:
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(sample_data, f, indent=2, ensure_ascii=False)
            print(f"Sample questions file created: {file_path}")
            return True
        except Exception as e:
            print(f"Error creating sample questions file: {e}")
            return False
