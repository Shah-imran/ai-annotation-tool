"""
Q&A Preferences Dialog for configuring Q&A annotation settings.
"""

import os
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QLineEdit, QFileDialog, QGroupBox, 
                            QGridLayout, QMessageBox, QDialogButtonBox)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont


class QAPreferencesDialog(QDialog):
    """Dialog for configuring Q&A annotation preferences."""
    
    # Signals
    questions_file_changed = pyqtSignal(str)  # Emitted when questions file is selected
    answers_folder_changed = pyqtSignal(str)  # Emitted when answers folder is selected
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._questions_file = ""
        self._answers_folder = ""
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the user interface."""
        self.setWindowTitle("Q&A Preferences")
        self.setModal(True)
        
        # Make dialog resizable and scale based on screen size
        from PyQt5.QtWidgets import QApplication
        screen = QApplication.primaryScreen().geometry()
        screen_width = screen.width()
        screen_height = screen.height()
        
        # Use 50% of screen size for dialog, with minimum constraints
        dialog_width = max(500, min(800, int(screen_width * 0.5)))
        dialog_height = max(350, min(600, int(screen_height * 0.5)))
        
        self.setMinimumSize(500, 350)
        self.resize(dialog_width, dialog_height)
        
        # Center dialog on screen
        x = (screen_width - dialog_width) // 2
        y = (screen_height - dialog_height) // 2
        self.move(x, y)
        
        layout = QVBoxLayout()
        
        # Title
        title_label = QLabel("Q&A Annotation Configuration")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Description
        desc_label = QLabel(
            "Configure the questions file and answers save location for Q&A annotations."
        )
        desc_label.setWordWrap(True)
        desc_label.setAlignment(Qt.AlignCenter)
        desc_label.setStyleSheet("color: #666666; margin: 10px;")
        layout.addWidget(desc_label)
        
        # Questions file group
        self._create_questions_group(layout)
        
        # Answers folder group
        self._create_answers_group(layout)
        
        # Buttons
        self._create_buttons(layout)
        
        self.setLayout(layout)
    
    def _create_questions_group(self, parent_layout):
        """Create questions file selection group."""
        group = QGroupBox("Questions File")
        layout = QGridLayout()
        
        # Description
        desc_label = QLabel("Select a JSON file containing the questions for annotations:")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("margin-bottom: 5px;")
        layout.addWidget(desc_label, 0, 0, 1, 3)
        
        # File path display
        self.questions_file_edit = QLineEdit()
        self.questions_file_edit.setPlaceholderText("No questions file selected...")
        self.questions_file_edit.setReadOnly(True)
        layout.addWidget(self.questions_file_edit, 1, 0, 1, 2)
        
        # Browse button
        self.browse_questions_btn = QPushButton("Browse...")
        self.browse_questions_btn.clicked.connect(self._browse_questions_file)
        layout.addWidget(self.browse_questions_btn, 1, 2)
        
        # Create sample button
        self.create_sample_btn = QPushButton("Create Sample File...")
        self.create_sample_btn.clicked.connect(self._create_sample_questions)
        layout.addWidget(self.create_sample_btn, 2, 0, 1, 3)
        
        # Format info
        format_info = QLabel(
            "Format: JSON file with 'questions' array containing question strings.\n"
            "Example: {\"questions\": [\"What is this object?\", \"Is it damaged?\"]}"
        )
        format_info.setWordWrap(True)
        format_info.setStyleSheet("font-size: 10px; color: #666666; margin-top: 5px;")
        layout.addWidget(format_info, 3, 0, 1, 3)
        
        group.setLayout(layout)
        parent_layout.addWidget(group)
    
    def _create_answers_group(self, parent_layout):
        """Create answers folder selection group."""
        group = QGroupBox("Answers Save Folder")
        layout = QGridLayout()
        
        # Description
        desc_label = QLabel("Select the folder where Q&A answers will be saved:")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("margin-bottom: 5px;")
        layout.addWidget(desc_label, 0, 0, 1, 3)
        
        # Folder path display
        self.answers_folder_edit = QLineEdit()
        self.answers_folder_edit.setPlaceholderText("No answers folder selected...")
        self.answers_folder_edit.setReadOnly(True)
        layout.addWidget(self.answers_folder_edit, 1, 0, 1, 2)
        
        # Browse button
        self.browse_answers_btn = QPushButton("Browse...")
        self.browse_answers_btn.clicked.connect(self._browse_answers_folder)
        layout.addWidget(self.browse_answers_btn, 1, 2)
        
        # Info
        info_label = QLabel(
            "Answers will be saved as [image_name].qa.json files in this folder.\n"
            "Each file contains Q&A data for all bounding boxes in that image."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("font-size: 10px; color: #666666; margin-top: 5px;")
        layout.addWidget(info_label, 2, 0, 1, 3)
        
        group.setLayout(layout)
        parent_layout.addWidget(group)
    
    def _create_buttons(self, parent_layout):
        """Create dialog buttons."""
        button_box = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        button_box.accepted.connect(self._apply_settings)
        button_box.rejected.connect(self.reject)
        
        parent_layout.addWidget(button_box)
    
    def _browse_questions_file(self):
        """Browse for questions JSON file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Questions File",
            self._questions_file or os.getcwd(),
            "JSON files (*.json);;All files (*.*)"
        )
        
        if file_path:
            self._questions_file = file_path
            self.questions_file_edit.setText(file_path)
    
    def _browse_answers_folder(self):
        """Browse for answers save folder."""
        folder_path = QFileDialog.getExistingDirectory(
            self,
            "Select Answers Save Folder",
            self._answers_folder or os.getcwd()
        )
        
        if folder_path:
            self._answers_folder = folder_path
            self.answers_folder_edit.setText(folder_path)
    
    def _create_sample_questions(self):
        """Create a sample questions file."""
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "Create Sample Questions File",
            os.path.join(os.getcwd(), "sample_questions.json"),
            "JSON files (*.json);;All files (*.*)"
        )
        
        if file_path:
            try:
                sample_data = {
                    "questions": [
                        "What is the primary object in this bounding box?",
                        "What action or state is being demonstrated?",
                        "Is there any damage or defect visible?",
                        "What is the approximate size category?",
                        "Are there any safety concerns?",
                        "What materials can you identify?",
                        "Is this object functioning properly?",
                        "What is the overall condition?"
                    ]
                }
                
                import json
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(sample_data, f, indent=2, ensure_ascii=False)
                
                QMessageBox.information(
                    self,
                    "Sample Created",
                    f"Sample questions file created successfully:\n{file_path}\n\n"
                    "You can edit this file to customize the questions for your needs."
                )
                
                # Automatically select the created file
                self._questions_file = file_path
                self.questions_file_edit.setText(file_path)
                
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Error",
                    f"Failed to create sample file:\n{str(e)}"
                )
    
    def _apply_settings(self):
        """Apply the selected settings."""
        # Validate questions file
        if self._questions_file:
            if not os.path.isfile(self._questions_file):
                QMessageBox.warning(
                    self,
                    "Invalid Questions File",
                    "The selected questions file does not exist."
                )
                return
        
        # Validate answers folder
        if self._answers_folder:
            if not os.path.isdir(self._answers_folder):
                try:
                    os.makedirs(self._answers_folder, exist_ok=True)
                except Exception as e:
                    QMessageBox.critical(
                        self,
                        "Invalid Answers Folder",
                        f"Cannot create answers folder:\n{str(e)}"
                    )
                    return
        
        # Emit signals
        if self._questions_file:
            self.questions_file_changed.emit(self._questions_file)
        
        if self._answers_folder:
            self.answers_folder_changed.emit(self._answers_folder)
        
        self.accept()
    
    def set_questions_file(self, file_path: str):
        """Set the current questions file."""
        self._questions_file = file_path
        self.questions_file_edit.setText(file_path)
    
    def set_answers_folder(self, folder_path: str):
        """Set the current answers folder."""
        self._answers_folder = folder_path
        self.answers_folder_edit.setText(folder_path)
    
    def get_questions_file(self) -> str:
        """Get the selected questions file."""
        return self._questions_file
    
    def get_answers_folder(self) -> str:
        """Get the selected answers folder."""
        return self._answers_folder

