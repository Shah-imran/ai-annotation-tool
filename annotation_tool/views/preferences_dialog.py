"""
Preferences Dialog for configuring all application settings.
"""

import os
import json
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QLineEdit, QFileDialog, QGroupBox, 
                            QGridLayout, QMessageBox, QDialogButtonBox, QCheckBox,
                            QSpinBox, QTabWidget, QWidget)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont


class PreferencesDialog(QDialog):
    """Dialog for configuring all application preferences."""
    
    # Signals
    image_directory_changed = pyqtSignal(str)
    image_list_file_changed = pyqtSignal(str, str)  # file_path, base_directory
    classes_file_changed = pyqtSignal(str)
    qa_enabled_changed = pyqtSignal(bool)
    questions_file_changed = pyqtSignal(str)
    answers_folder_changed = pyqtSignal(str)
    auto_load_session_changed = pyqtSignal(bool)
    auto_save_interval_changed = pyqtSignal(int)
    max_recent_items_changed = pyqtSignal(int)
    settings_file_path_changed = pyqtSignal(str)  # Emitted when settings file path is changed
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._image_directory = ""
        self._image_list_file = ""
        self._base_directory = ""
        self._classes_file = ""
        self._qa_enabled = False
        self._questions_file = ""
        self._answers_folder = ""
        self._auto_load_session = True
        self._auto_save_interval = 30
        self._max_recent_items = 5
        self._settings_file_path = ""
        self._setup_ui()
    
    def _setup_ui(self):
        """Setup the user interface."""
        self.setWindowTitle("Preferences")
        self.setModal(True)
        
        # Make dialog resizable and scale based on screen size
        from PyQt5.QtWidgets import QApplication
        screen = QApplication.primaryScreen().geometry()
        screen_width = screen.width()
        screen_height = screen.height()
        
        # Use 60% of screen size for dialog, with minimum and maximum constraints
        dialog_width = max(600, min(1200, int(screen_width * 0.6)))
        dialog_height = max(500, min(900, int(screen_height * 0.7)))
        
        self.setMinimumSize(600, 500)
        self.resize(dialog_width, dialog_height)
        
        # Center dialog on screen
        x = (screen_width - dialog_width) // 2
        y = (screen_height - dialog_height) // 2
        self.move(x, y)
        
        layout = QVBoxLayout()
        
        # Title
        title_label = QLabel("Application Preferences")
        title_font = QFont()
        title_font.setPointSize(14)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)
        
        # Create tab widget
        tabs = QTabWidget()
        
        # File Paths tab
        file_paths_tab = self._create_file_paths_tab()
        tabs.addTab(file_paths_tab, "File Paths")
        
        # Q&A Settings tab
        qa_tab = self._create_qa_tab()
        tabs.addTab(qa_tab, "Q&A Settings")
        
        # General Settings tab
        general_tab = self._create_general_tab()
        tabs.addTab(general_tab, "General")
        
        layout.addWidget(tabs)
        
        # Buttons
        self._create_buttons(layout)
        
        self.setLayout(layout)
    
    def _create_file_paths_tab(self):
        """Create the file paths configuration tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Image directory group
        self._create_image_directory_group(layout)
        
        # Image list file group
        self._create_image_list_group(layout)
        
        # Classes file group
        self._create_classes_group(layout)
        
        layout.addStretch()
        return widget
    
    def _create_image_directory_group(self, parent_layout):
        """Create image directory selection group."""
        group = QGroupBox("Image Directory")
        layout = QGridLayout()
        
        desc_label = QLabel("Default directory for loading images:")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label, 0, 0, 1, 3)
        
        self.image_directory_edit = QLineEdit()
        self.image_directory_edit.setPlaceholderText("No directory selected...")
        self.image_directory_edit.setReadOnly(True)
        layout.addWidget(self.image_directory_edit, 1, 0, 1, 2)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_image_directory)
        layout.addWidget(browse_btn, 1, 2)
        
        group.setLayout(layout)
        parent_layout.addWidget(group)
    
    def _create_image_list_group(self, parent_layout):
        """Create image list file selection group."""
        group = QGroupBox("Image List File")
        layout = QGridLayout()
        
        desc_label = QLabel("File containing list of image paths (one per line):")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label, 0, 0, 1, 3)
        
        self.image_list_file_edit = QLineEdit()
        self.image_list_file_edit.setPlaceholderText("No file selected...")
        self.image_list_file_edit.setReadOnly(True)
        layout.addWidget(self.image_list_file_edit, 1, 0, 1, 2)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_image_list_file)
        layout.addWidget(browse_btn, 1, 2)
        
        # Base directory
        base_dir_label = QLabel("Base Directory (for relative paths):")
        layout.addWidget(base_dir_label, 2, 0)
        
        self.base_directory_edit = QLineEdit()
        self.base_directory_edit.setPlaceholderText("No base directory selected...")
        self.base_directory_edit.setReadOnly(True)
        layout.addWidget(self.base_directory_edit, 3, 0, 1, 2)
        
        browse_base_btn = QPushButton("Browse...")
        browse_base_btn.clicked.connect(self._browse_base_directory)
        layout.addWidget(browse_base_btn, 3, 2)
        
        group.setLayout(layout)
        parent_layout.addWidget(group)
    
    def _create_classes_group(self, parent_layout):
        """Create classes file selection group."""
        group = QGroupBox("Classes File")
        layout = QGridLayout()
        
        desc_label = QLabel("File containing class names (one per line):")
        desc_label.setWordWrap(True)
        layout.addWidget(desc_label, 0, 0, 1, 3)
        
        self.classes_file_edit = QLineEdit()
        self.classes_file_edit.setPlaceholderText("No file selected...")
        self.classes_file_edit.setReadOnly(True)
        layout.addWidget(self.classes_file_edit, 1, 0, 1, 2)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_classes_file)
        layout.addWidget(browse_btn, 1, 2)
        
        group.setLayout(layout)
        parent_layout.addWidget(group)
    
    def _create_qa_tab(self):
        """Create the Q&A settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Q&A enabled checkbox
        self.qa_enabled_checkbox = QCheckBox("Enable Q&A Annotations")
        self.qa_enabled_checkbox.setChecked(self._qa_enabled)
        layout.addWidget(self.qa_enabled_checkbox)
        
        # Questions file group
        self._create_questions_group(layout)
        
        # Answers folder group
        self._create_answers_group(layout)
        
        layout.addStretch()
        return widget
    
    def _create_questions_group(self, parent_layout):
        """Create questions file selection group."""
        group = QGroupBox("Questions File")
        layout = QGridLayout()
        
        desc_label = QLabel("Select a JSON file containing the questions for annotations:")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("margin-bottom: 5px;")
        layout.addWidget(desc_label, 0, 0, 1, 3)
        
        self.questions_file_edit = QLineEdit()
        self.questions_file_edit.setPlaceholderText("No questions file selected...")
        self.questions_file_edit.setReadOnly(True)
        layout.addWidget(self.questions_file_edit, 1, 0, 1, 2)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_questions_file)
        layout.addWidget(browse_btn, 1, 2)
        
        create_sample_btn = QPushButton("Create Sample File...")
        create_sample_btn.clicked.connect(self._create_sample_questions)
        layout.addWidget(create_sample_btn, 2, 0, 1, 3)
        
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
        
        desc_label = QLabel("Select the folder where Q&A answers will be saved:")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("margin-bottom: 5px;")
        layout.addWidget(desc_label, 0, 0, 1, 3)
        
        self.answers_folder_edit = QLineEdit()
        self.answers_folder_edit.setPlaceholderText("No answers folder selected...")
        self.answers_folder_edit.setReadOnly(True)
        layout.addWidget(self.answers_folder_edit, 1, 0, 1, 2)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_answers_folder)
        layout.addWidget(browse_btn, 1, 2)
        
        info_label = QLabel(
            "Answers will be saved as [image_name].qa.json files in this folder.\n"
            "Each file contains Q&A data for all bounding boxes in that image."
        )
        info_label.setWordWrap(True)
        info_label.setStyleSheet("font-size: 10px; color: #666666; margin-top: 5px;")
        layout.addWidget(info_label, 2, 0, 1, 3)
        
        group.setLayout(layout)
        parent_layout.addWidget(group)
    
    def _create_general_tab(self):
        """Create the general settings tab."""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)
        
        # Settings file path group
        self._create_settings_file_group(layout)
        
        # Auto-load session
        self.auto_load_checkbox = QCheckBox("Auto-load last session on startup")
        self.auto_load_checkbox.setChecked(self._auto_load_session)
        layout.addWidget(self.auto_load_checkbox)
        
        # Auto-save interval
        auto_save_group = QGroupBox("Auto-save Settings")
        auto_save_layout = QGridLayout()
        
        auto_save_label = QLabel("Auto-save interval (seconds):")
        auto_save_layout.addWidget(auto_save_label, 0, 0)
        
        self.auto_save_spinbox = QSpinBox()
        self.auto_save_spinbox.setMinimum(1)
        self.auto_save_spinbox.setMaximum(3600)
        self.auto_save_spinbox.setValue(self._auto_save_interval)
        auto_save_layout.addWidget(self.auto_save_spinbox, 0, 1)
        
        auto_save_group.setLayout(auto_save_layout)
        layout.addWidget(auto_save_group)
        
        # Max recent items
        recent_group = QGroupBox("Recent Items")
        recent_layout = QGridLayout()
        
        recent_label = QLabel("Maximum recent items to remember:")
        recent_layout.addWidget(recent_label, 0, 0)
        
        self.max_recent_spinbox = QSpinBox()
        self.max_recent_spinbox.setMinimum(1)
        self.max_recent_spinbox.setMaximum(20)
        self.max_recent_spinbox.setValue(self._max_recent_items)
        recent_layout.addWidget(self.max_recent_spinbox, 0, 1)
        
        recent_group.setLayout(recent_layout)
        layout.addWidget(recent_group)
        
        layout.addStretch()
        return widget
    
    def _create_settings_file_group(self, parent_layout):
        """Create settings file path selection group."""
        group = QGroupBox("Settings File")
        layout = QGridLayout()
        
        desc_label = QLabel("Location where application settings are stored:")
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("margin-bottom: 5px;")
        layout.addWidget(desc_label, 0, 0, 1, 3)
        
        self.settings_file_edit = QLineEdit()
        self.settings_file_edit.setPlaceholderText("No settings file selected...")
        self.settings_file_edit.setReadOnly(True)
        layout.addWidget(self.settings_file_edit, 1, 0, 1, 2)
        
        browse_btn = QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_settings_file)
        layout.addWidget(browse_btn, 1, 2)
        
        info_label = QLabel(
            "Changing the settings file will load settings from the new location.\n"
            "Current settings will be saved to the new file."
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
    
    # Browse methods
    def _browse_image_directory(self):
        """Browse for image directory."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Image Directory",
            self._image_directory or os.getcwd(),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if directory:
            self._image_directory = directory
            self.image_directory_edit.setText(directory)
    
    def _browse_image_list_file(self):
        """Browse for image list file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Image List File",
            self._image_list_file or os.getcwd(),
            "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            self._image_list_file = file_path
            self.image_list_file_edit.setText(file_path)
    
    def _browse_base_directory(self):
        """Browse for base directory."""
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Base Directory",
            self._base_directory or os.getcwd(),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if directory:
            self._base_directory = directory
            self.base_directory_edit.setText(directory)
    
    def _browse_classes_file(self):
        """Browse for classes file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Classes File",
            self._classes_file or os.getcwd(),
            "Text Files (*.txt);;Names Files (*.names);;All Files (*)"
        )
        
        if file_path:
            self._classes_file = file_path
            self.classes_file_edit.setText(file_path)
    
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
    
    def _browse_settings_file(self):
        """Browse for settings file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Settings File",
            self._settings_file_path or os.getcwd(),
            "JSON Files (*.json);;All Files (*)"
        )
        
        if file_path:
            self._settings_file_path = file_path
            self.settings_file_edit.setText(file_path)
    
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
        # Validate file paths if provided
        if self._image_list_file and not os.path.isfile(self._image_list_file):
            QMessageBox.warning(
                self,
                "Invalid File",
                "The selected image list file does not exist."
            )
            return
        
        if self._classes_file and not os.path.isfile(self._classes_file):
            QMessageBox.warning(
                self,
                "Invalid File",
                "The selected classes file does not exist."
            )
            return
        
        if self._questions_file and not os.path.isfile(self._questions_file):
            QMessageBox.warning(
                self,
                "Invalid File",
                "The selected questions file does not exist."
            )
            return
        
        if self._answers_folder and not os.path.isdir(self._answers_folder):
            try:
                os.makedirs(self._answers_folder, exist_ok=True)
            except Exception as e:
                QMessageBox.critical(
                    self,
                    "Invalid Folder",
                    f"Cannot create answers folder:\n{str(e)}"
                )
                return
        
        # Emit signals for changed settings
        if self._image_directory:
            self.image_directory_changed.emit(self._image_directory)
        
        if self._image_list_file:
            self.image_list_file_changed.emit(self._image_list_file, self._base_directory)
        
        if self._classes_file:
            self.classes_file_changed.emit(self._classes_file)
        
        # Q&A settings
        qa_enabled = self.qa_enabled_checkbox.isChecked()
        if qa_enabled != self._qa_enabled:
            self.qa_enabled_changed.emit(qa_enabled)
        
        if self._questions_file:
            self.questions_file_changed.emit(self._questions_file)
        
        if self._answers_folder:
            self.answers_folder_changed.emit(self._answers_folder)
        
        # General settings
        auto_load = self.auto_load_checkbox.isChecked()
        if auto_load != self._auto_load_session:
            self.auto_load_session_changed.emit(auto_load)
        
        auto_save_interval = self.auto_save_spinbox.value()
        if auto_save_interval != self._auto_save_interval:
            self.auto_save_interval_changed.emit(auto_save_interval)
        
        max_recent = self.max_recent_spinbox.value()
        if max_recent != self._max_recent_items:
            self.max_recent_items_changed.emit(max_recent)
        
        # Settings file path
        if self._settings_file_path:
            self.settings_file_path_changed.emit(self._settings_file_path)
        
        self.accept()
    
    # Setter methods for initializing dialog with current values
    def set_image_directory(self, directory: str):
        """Set the current image directory."""
        self._image_directory = directory
        self.image_directory_edit.setText(directory)
    
    def set_image_list_file(self, file_path: str, base_directory: str = ""):
        """Set the current image list file and base directory."""
        self._image_list_file = file_path
        self._base_directory = base_directory
        self.image_list_file_edit.setText(file_path)
        self.base_directory_edit.setText(base_directory)
    
    def set_classes_file(self, file_path: str):
        """Set the current classes file."""
        self._classes_file = file_path
        self.classes_file_edit.setText(file_path)
    
    def set_qa_enabled(self, enabled: bool):
        """Set Q&A enabled state."""
        self._qa_enabled = enabled
        self.qa_enabled_checkbox.setChecked(enabled)
    
    def set_questions_file(self, file_path: str):
        """Set the current questions file."""
        self._questions_file = file_path
        self.questions_file_edit.setText(file_path)
    
    def set_answers_folder(self, folder_path: str):
        """Set the current answers folder."""
        self._answers_folder = folder_path
        self.answers_folder_edit.setText(folder_path)
    
    def set_auto_load_session(self, enabled: bool):
        """Set auto-load session preference."""
        self._auto_load_session = enabled
        self.auto_load_checkbox.setChecked(enabled)
    
    def set_auto_save_interval(self, interval: int):
        """Set auto-save interval."""
        self._auto_save_interval = interval
        self.auto_save_spinbox.setValue(interval)
    
    def set_max_recent_items(self, max_items: int):
        """Set maximum recent items."""
        self._max_recent_items = max_items
        self.max_recent_spinbox.setValue(max_items)
    
    def set_settings_file_path(self, file_path: str):
        """Set the current settings file path."""
        self._settings_file_path = file_path
        self.settings_file_edit.setText(file_path)
