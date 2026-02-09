"""
Control panel widget for annotation tool interface.
"""
from typing import List, Optional, Dict, Any
from PyQt5.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QLabel, 
                            QLineEdit, QPushButton, QListWidget, QListWidgetItem,
                            QComboBox, QSpinBox, QTextEdit, QGroupBox, QGridLayout,
                            QProgressBar, QSplitter, QScrollArea, QCheckBox, QFrame,
                            QSlider)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QFont, QKeySequence


class ControlPanel(QWidget):
    """
    Control panel for managing annotations, classes, and navigation.
    """
    
    # Signals
    class_changed = pyqtSignal(int)
    annotation_text_changed = pyqtSignal(str)
    delete_annotation_requested = pyqtSignal()
    clear_all_requested = pyqtSignal()
    next_image_requested = pyqtSignal()
    previous_image_requested = pyqtSignal()
    image_index_requested = pyqtSignal(int)  # Request to navigate to specific image index
    load_images_requested = pyqtSignal()
    load_classes_requested = pyqtSignal()
    save_requested = pyqtSignal()
    copy_boxes_to_next_requested = pyqtSignal()  # Copy all boxes to next image
    copy_boxes_count_changed = pyqtSignal(int)  # Number of images to copy to
    qa_answer_changed = pyqtSignal(str, str)  # question, answer
    toggle_panel_requested = pyqtSignal()  # Request to toggle panel visibility
    
    def __init__(self):
        super().__init__()
        self._current_annotation_index = -1
        
        # Q&A related
        self._qa_enabled = False
        self._questions = []
        self._qa_answers = {}  # question -> answer text
        
        self._setup_ui()
    
    def _setup_ui(self):
        """Initialize the UI components."""
        # Make control panel resizable with minimum width only
        # Maximum width will be enforced by the splitter handler in main window
        self.setMinimumWidth(250)
        self.setStyleSheet("""
            QGroupBox {
                font-weight: bold;
                border: 2px solid #cccccc;
                border-radius: 5px;
                margin-top: 1ex;
                padding-top: 10px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px 0 5px;
            }
            QPushButton {
                background-color: #4CAF50;
                border: none;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:pressed {
                background-color: #3d8b40;
            }
            QPushButton:disabled {
                background-color: #cccccc;
                color: #666666;
            }
        """)
        
        layout = QVBoxLayout(self)
        layout.setSpacing(10)
        
        # Create scroll area for the entire control panel
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)
        
        # File operations
        self._create_file_operations_group(scroll_layout)
        
        # Navigation
        self._create_navigation_group(scroll_layout)
        
        # Class selection
        self._create_class_selection_group(scroll_layout)
        
        # Current annotation
        self._create_annotation_group(scroll_layout)
        
        # Q&A section (collapsible)
        self._create_qa_group(scroll_layout)
        
        # Annotation list
        self._create_annotation_list_group(scroll_layout)
        
        # Actions
        self._create_actions_group(scroll_layout)
        
        # Help
        self._create_help_group(scroll_layout)
        
        scroll_layout.addStretch()
        scroll_area.setWidget(scroll_widget)
        layout.addWidget(scroll_area)
    
    def _create_file_operations_group(self, parent_layout):
        """Create file operations group."""
        group = QGroupBox("File Operations")
        layout = QVBoxLayout(group)
        
        # Load images button
        self.load_images_btn = QPushButton("Load Images...")
        self.load_images_btn.clicked.connect(self.load_images_requested.emit)
        layout.addWidget(self.load_images_btn)
        
        # Load classes button
        self.load_classes_btn = QPushButton("Load Classes...")
        self.load_classes_btn.clicked.connect(self.load_classes_requested.emit)
        layout.addWidget(self.load_classes_btn)
        
        # Save button
        self.save_btn = QPushButton("Save (Ctrl+S)")
        self.save_btn.clicked.connect(self.save_requested.emit)
        self.save_btn.setEnabled(False)
        layout.addWidget(self.save_btn)
        
        parent_layout.addWidget(group)
    
    def _create_navigation_group(self, parent_layout):
        """Create navigation group."""
        group = QGroupBox("Navigation")
        layout = QVBoxLayout(group)
        
        # Image counter
        self.image_counter_label = QLabel("No images loaded")
        self.image_counter_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.image_counter_label)
        
        # Draggable slider for image navigation
        self.image_slider = QSlider(Qt.Horizontal)
        self.image_slider.setMinimum(0)
        self.image_slider.setMaximum(0)
        self.image_slider.setValue(0)
        self.image_slider.setVisible(False)
        self.image_slider.setTickPosition(QSlider.NoTicks)
        self.image_slider.valueChanged.connect(self._on_slider_value_changed)
        self.image_slider.sliderPressed.connect(self._on_slider_pressed)
        self.image_slider.sliderReleased.connect(self._on_slider_released)
        layout.addWidget(self.image_slider)
        
        # Flag to prevent recursive updates when programmatically setting slider value
        self._updating_slider = False
        
        # Debouncing timer for slider - wait for user to slow down before changing images
        self._slider_debounce_timer = QTimer()
        self._slider_debounce_timer.setSingleShot(True)
        self._slider_debounce_timer.timeout.connect(self._on_slider_debounce_timeout)
        self._pending_image_index = None
        self._is_dragging = False
        
        # Navigation buttons
        nav_layout = QHBoxLayout()
        
        self.prev_btn = QPushButton("Previous (A)")
        self.prev_btn.clicked.connect(self.previous_image_requested.emit)
        self.prev_btn.setEnabled(False)
        nav_layout.addWidget(self.prev_btn)
        
        self.next_btn = QPushButton("Next (D)")
        self.next_btn.clicked.connect(self.next_image_requested.emit)
        self.next_btn.setEnabled(False)
        nav_layout.addWidget(self.next_btn)
        
        layout.addLayout(nav_layout)
        
        # Copy boxes count control
        copy_boxes_layout = QHBoxLayout()
        copy_boxes_label = QLabel("Copy to next:")
        copy_boxes_layout.addWidget(copy_boxes_label)
        
        self.copy_boxes_spinbox = QSpinBox()
        self.copy_boxes_spinbox.setMinimum(1)
        self.copy_boxes_spinbox.setMaximum(2147483647)  # Maximum 32-bit integer value
        self.copy_boxes_spinbox.setValue(1)
        self.copy_boxes_spinbox.setToolTip("Number of images to copy boxes to when using Ctrl+C")
        self.copy_boxes_spinbox.valueChanged.connect(self.copy_boxes_count_changed.emit)
        copy_boxes_layout.addWidget(self.copy_boxes_spinbox)
        
        copy_boxes_layout.addStretch()
        layout.addLayout(copy_boxes_layout)
        
        parent_layout.addWidget(group)
    
    def _create_class_selection_group(self, parent_layout):
        """Create class selection group."""
        group = QGroupBox("Class Selection")
        layout = QVBoxLayout(group)
        
        # Current class display
        self.current_class_label = QLabel("No classes loaded")
        self.current_class_label.setAlignment(Qt.AlignCenter)
        self.current_class_label.setStyleSheet("font-weight: bold; color: blue;")
        layout.addWidget(self.current_class_label)
        
        # Class combo box
        self.class_combo = QComboBox()
        self.class_combo.currentIndexChanged.connect(self.class_changed.emit)
        self.class_combo.setEnabled(False)
        layout.addWidget(self.class_combo)
        
        parent_layout.addWidget(group)
    
    def _create_annotation_group(self, parent_layout):
        """Create current annotation group."""
        group = QGroupBox("Current Annotation")
        layout = QVBoxLayout(group)
        
        # Annotation info
        self.annotation_info_label = QLabel("No annotation selected")
        layout.addWidget(self.annotation_info_label)
        
        # Text input
        text_label = QLabel("Description:")
        layout.addWidget(text_label)
        
        self.annotation_text = QTextEdit()
        self.annotation_text.setMaximumHeight(80)
        self.annotation_text.setPlaceholderText("Enter description for this annotation...")
        self.annotation_text.textChanged.connect(self._on_text_changed)
        self.annotation_text.setEnabled(False)
        
        # Ensure proper text direction and input behavior
        self.annotation_text.setLayoutDirection(Qt.LeftToRight)
        self.annotation_text.setAlignment(Qt.AlignLeft)
        
        # Set text cursor to move left-to-right
        cursor = self.annotation_text.textCursor()
        cursor.movePosition(cursor.Start)
        self.annotation_text.setTextCursor(cursor)
        
        # Ensure proper input method hints
        self.annotation_text.setInputMethodHints(Qt.ImhNoAutoUppercase | Qt.ImhNoPredictiveText)
        
        # Focus event handling
        self.annotation_text.focusInEvent = self._on_text_focus_in
        self.annotation_text.focusOutEvent = self._on_text_focus_out
        
        # Custom styling for focus states
        self._apply_text_edit_styling()
        
        layout.addWidget(self.annotation_text)
        
        parent_layout.addWidget(group)
    
    def _create_annotation_list_group(self, parent_layout):
        """Create annotation list group."""
        group = QGroupBox("Annotations")
        layout = QVBoxLayout(group)
        
        # Annotation count
        self.annotation_count_label = QLabel("0 annotations")
        layout.addWidget(self.annotation_count_label)
        
        # Annotation list
        self.annotation_list = QListWidget()
        self.annotation_list.setMaximumHeight(150)
        self.annotation_list.itemClicked.connect(self._on_annotation_item_clicked)
        layout.addWidget(self.annotation_list)
        
        parent_layout.addWidget(group)
    
    def _create_actions_group(self, parent_layout):
        """Create actions group."""
        group = QGroupBox("Actions")
        layout = QVBoxLayout(group)
        
        # Delete annotation
        self.delete_btn = QPushButton("Delete Selected (R)")
        self.delete_btn.clicked.connect(self.delete_annotation_requested.emit)
        self.delete_btn.setEnabled(False)
        layout.addWidget(self.delete_btn)
        
        # Clear all
        self.clear_all_btn = QPushButton("Clear All (C)")
        self.clear_all_btn.clicked.connect(self.clear_all_requested.emit)
        self.clear_all_btn.setEnabled(False)
        layout.addWidget(self.clear_all_btn)
        
        parent_layout.addWidget(group)
    
    def _create_help_group(self, parent_layout):
        """Create help group."""
        group = QGroupBox("Help")
        layout = QVBoxLayout(group)
        
        help_text = """
Keyboard Shortcuts:
• A/D - Previous/Next image
• 0-9 - Select class
• R - Delete selected annotation
• C - Clear all annotations
• Ctrl+S - Save annotations
• I - Toggle magnification
• M - Cycle magnification method
• ESC - Clear text box focus

Mouse Controls:
• Left click + drag - Draw annotation
• Right click - Select annotation
• Right drag - Move annotation
• Mouse wheel - Adjust magnification scale
        """
        
        help_label = QLabel(help_text)
        help_label.setWordWrap(True)
        help_label.setStyleSheet("font-size: 10px; color: #666666;")
        layout.addWidget(help_label)
        
        parent_layout.addWidget(group)
    
    def _create_qa_group(self, parent_layout):
        """Create Q&A group with dropdown question selection."""
        self.qa_group = QGroupBox("Q&A Annotations")
        self.qa_group.setVisible(False)  # Hidden by default
        layout = QVBoxLayout()
        
        # Info label
        self.qa_info_label = QLabel("No questions loaded")
        self.qa_info_label.setAlignment(Qt.AlignCenter)
        self.qa_info_label.setStyleSheet("color: #666666; font-style: italic;")
        layout.addWidget(self.qa_info_label)
        
        # Question selection dropdown
        question_selection_layout = QVBoxLayout()
        
        question_label = QLabel("Select Question:")
        question_label.setStyleSheet("font-weight: bold; margin-top: 5px;")
        question_selection_layout.addWidget(question_label)
        
        self.qa_question_combo = QComboBox()
        self.qa_question_combo.setVisible(False)
        self.qa_question_combo.currentTextChanged.connect(self._on_question_selected)
        question_selection_layout.addWidget(self.qa_question_combo)
        
        layout.addLayout(question_selection_layout)
        
        # Answer area (can be dropdown or text input)
        answer_layout = QVBoxLayout()
        
        self.answer_label = QLabel("Answer:")
        self.answer_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        answer_layout.addWidget(self.answer_label)
        
        # Container for answer widget (will hold either dropdown or text input)
        self.qa_answer_container = QWidget()
        self.qa_answer_layout = QVBoxLayout()
        self.qa_answer_layout.setContentsMargins(0, 0, 0, 0)
        self.qa_answer_container.setLayout(self.qa_answer_layout)
        answer_layout.addWidget(self.qa_answer_container)
        
        # Initialize with no answer widget
        self.qa_current_answer_widget = None
        
        layout.addLayout(answer_layout)
        
        # Progress indicator
        self.qa_progress_label = QLabel("")
        self.qa_progress_label.setAlignment(Qt.AlignCenter)
        self.qa_progress_label.setStyleSheet("color: #666666; font-size: 10px; margin-top: 5px;")
        self.qa_progress_label.setVisible(False)
        layout.addWidget(self.qa_progress_label)
        
        self.qa_group.setLayout(layout)
        parent_layout.addWidget(self.qa_group)
    
    def _apply_text_edit_styling(self):
        """Apply custom styling to text edit widget."""
        self.annotation_text.setStyleSheet("""
            QTextEdit {
                background-color: #ffffff;
                border: 2px solid #cccccc;
                border-radius: 4px;
                padding: 4px;
                font-size: 12px;
                color: #333333;
            }
            QTextEdit:focus {
                border: 2px solid #4CAF50;
                background-color: #f0fff0;
                box-shadow: 0px 0px 5px rgba(76, 175, 80, 0.3);
            }
            QTextEdit:disabled {
                background-color: #f5f5f5;
                border: 2px solid #e0e0e0;
                color: #888888;
            }
        """)
    
    def _on_text_focus_in(self, event):
        """Handle text edit focus in event."""
        # Call original focus in event
        QTextEdit.focusInEvent(self.annotation_text, event)
        
        # Additional visual feedback
        self.annotation_text.setStyleSheet("""
            QTextEdit {
                background-color: #f0fff0;
                border: 3px solid #4CAF50;
                border-radius: 4px;
                padding: 4px;
                font-size: 12px;
                color: #333333;
                box-shadow: 0px 0px 8px rgba(76, 175, 80, 0.5);
            }
        """)
    
    def _on_text_focus_out(self, event):
        """Handle text edit focus out event."""
        # Call original focus out event
        QTextEdit.focusOutEvent(self.annotation_text, event)
        
        # Revert to normal styling
        self._apply_text_edit_styling()
    
    def _on_text_changed(self):
        """Handle annotation text changes."""
        text = self.annotation_text.toPlainText()
        self.annotation_text_changed.emit(text)
    
    def _on_annotation_item_clicked(self, item):
        """Handle annotation list item clicks."""
        row = self.annotation_list.row(item)
        if hasattr(item, 'annotation_index'):
            # This would be implemented in the controller
            pass
    
    def update_image_counter(self, current: int, total: int):
        """Update image counter display."""
        if total > 0:
            self.image_counter_label.setText(f"Image {current + 1} of {total}")
            # Cancel any pending debounce timer since we're updating programmatically
            self._slider_debounce_timer.stop()
            self._pending_image_index = None
            # Update slider
            self._updating_slider = True
            self.image_slider.setMaximum(max(0, total - 1))  # Slider is 0-indexed
            self.image_slider.setValue(current)
            self.image_slider.setVisible(True)
            self._updating_slider = False
            self.prev_btn.setEnabled(True)
            self.next_btn.setEnabled(True)
            self.save_btn.setEnabled(True)
        else:
            self.image_counter_label.setText("No images loaded")
            # Cancel any pending debounce timer
            self._slider_debounce_timer.stop()
            self._pending_image_index = None
            self.image_slider.setVisible(False)
            self.image_slider.setMaximum(0)
            self.image_slider.setValue(0)
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)
            self.save_btn.setEnabled(False)
    
    def _on_slider_value_changed(self, value: int):
        """Handle slider value change - use debouncing when dragging."""
        # Only handle if slider change was user-initiated (not programmatic update)
        if self._updating_slider:
            return
        
        # Update the counter label immediately to show target image
        total = self.image_slider.maximum() + 1
        if total > 0:
            self.image_counter_label.setText(f"Image {value + 1} of {total}")
        
        # If user is dragging, use debouncing to wait for them to slow down
        if self._is_dragging:
            # Store the pending index
            self._pending_image_index = value
            # Restart the debounce timer (300ms delay)
            self._slider_debounce_timer.stop()
            self._slider_debounce_timer.start(300)
        else:
            # If not dragging (e.g., clicked on a specific position), navigate immediately
            self.image_index_requested.emit(value)
    
    def _on_slider_pressed(self):
        """Handle slider press - user started dragging."""
        self._is_dragging = True
    
    def _on_slider_released(self):
        """Handle slider release - navigate to final position immediately."""
        self._is_dragging = False
        # Stop the debounce timer
        self._slider_debounce_timer.stop()
        # Navigate to the current slider value immediately
        if self._pending_image_index is not None:
            self.image_index_requested.emit(self._pending_image_index)
            self._pending_image_index = None
        else:
            # Fallback to current slider value
            self.image_index_requested.emit(self.image_slider.value())
    
    def _on_slider_debounce_timeout(self):
        """Handle debounce timeout - user has slowed down, navigate to pending index."""
        if self._pending_image_index is not None:
            self.image_index_requested.emit(self._pending_image_index)
            self._pending_image_index = None
    
    def update_class_list(self, class_names: List[str]):
        """Update class selection."""
        self.class_combo.clear()
        self.class_combo.setEnabled(bool(class_names))
        
        if class_names:
            for i, name in enumerate(class_names):
                self.class_combo.addItem(f"{i}: {name}")
            self.current_class_label.setText(f"Current: {class_names[0]}")
        else:
            self.current_class_label.setText("No classes loaded")
    
    def update_current_class(self, class_id: int, class_names: List[str]):
        """Update current class display."""
        if 0 <= class_id < len(class_names):
            self.current_class_label.setText(f"Current: {class_names[class_id]}")
            self.class_combo.setCurrentIndex(class_id)
    
    def update_annotation_info(self, annotation_index: int, annotation=None, class_names: List[str] = None):
        """Update current annotation info."""
        self._current_annotation_index = annotation_index
        
        if annotation is None or annotation_index < 0:
            self.annotation_info_label.setText("No annotation selected")
            self.annotation_text.setEnabled(False)
            self.annotation_text.clear()
            self.delete_btn.setEnabled(False)
        else:
            class_name = "Unknown"
            if class_names and 0 <= annotation.class_id < len(class_names):
                class_name = class_names[annotation.class_id]
            
            info_text = f"Class: {annotation.class_id} ({class_name})\n"
            info_text += f"Position: ({annotation.x:.3f}, {annotation.y:.3f})\n"
            info_text += f"Size: {annotation.width:.3f} × {annotation.height:.3f}"
            
            self.annotation_info_label.setText(info_text)
            self.annotation_text.setEnabled(True)
            
            # Update text without triggering change signal
            self.annotation_text.blockSignals(True)
            self.annotation_text.setPlainText(annotation.text)
            
            # Ensure cursor is at the end for proper text input
            cursor = self.annotation_text.textCursor()
            cursor.movePosition(cursor.End)
            self.annotation_text.setTextCursor(cursor)
            
            self.annotation_text.blockSignals(False)
            
            self.delete_btn.setEnabled(True)
    
    def update_annotation_list(self, annotations, class_names: List[str]):
        """Update annotation list display."""
        self.annotation_list.clear()
        self.annotation_count_label.setText(f"{len(annotations)} annotations")
        self.clear_all_btn.setEnabled(len(annotations) > 0)
        
        for i, annotation in enumerate(annotations):
            class_name = "Unknown"
            if class_names and 0 <= annotation.class_id < len(class_names):
                class_name = class_names[annotation.class_id]
            
            item_text = f"{i+1}. {class_name}"
            if annotation.text:
                item_text += f" - {annotation.text[:30]}{'...' if len(annotation.text) > 30 else ''}"
            
            item = QListWidgetItem(item_text)
            item.annotation_index = i
            self.annotation_list.addItem(item)
    
    def set_selected_annotation_in_list(self, index: int):
        """Highlight selected annotation in list."""
        if 0 <= index < self.annotation_list.count():
            self.annotation_list.setCurrentRow(index)
        else:
            self.annotation_list.clearSelection()
    
    def clear_text_focus(self):
        """Clear focus from text edit widget."""
        if self.annotation_text.hasFocus():
            self.annotation_text.clearFocus()
            # Force focus to parent widget
            self.setFocus()
    
    def has_text_focus(self):
        """Check if text edit widget has focus."""
        if self.annotation_text.hasFocus():
            return True
        
        # Check Q&A answer widget (if it's a text edit)
        if (hasattr(self, 'qa_current_answer_widget') and 
            self.qa_current_answer_widget and 
            isinstance(self.qa_current_answer_widget, QTextEdit) and 
            self.qa_current_answer_widget.hasFocus()):
            return True
        
        return False
    
    # Q&A Methods
    def set_qa_enabled(self, enabled: bool):
        """Enable or disable Q&A interface."""
        self._qa_enabled = enabled
        self.qa_group.setVisible(enabled)
    
    def load_questions(self, questions: List[Dict[str, Any]]):
        """Load questions into dropdown."""
        self._questions = questions.copy()
        self._qa_answers = {}  # Store answers for each question
        
        if not questions:
            self.qa_info_label.setText("No questions loaded")
            self.qa_info_label.setVisible(True)
            self.qa_question_combo.setVisible(False)
            self.qa_answer_text.setVisible(False)
            self.qa_progress_label.setVisible(False)
            return
        
        # Populate dropdown with question text
        self.qa_question_combo.clear()
        question_texts = [q["question"] for q in questions]
        self.qa_question_combo.addItems(question_texts)
        
        # Show UI elements
        self.qa_info_label.setText(f"{len(questions)} questions available")
        self.qa_info_label.setVisible(True)
        self.qa_question_combo.setVisible(True)
        self.qa_progress_label.setVisible(True)
        
        # Update answer widget for first question
        self._update_answer_widget()
        
        # Update progress
        self._update_progress_display()
    
    def _on_question_selected(self, question_text: str):
        """Handle question selection from dropdown."""
        if not question_text or not self._questions:
            return
        
        # Save current answer before switching
        self._save_current_answer()
        
        # Update answer widget for new question
        self._update_answer_widget()
        
        # Update progress display
        self._update_progress_display()
    
    def _update_answer_widget(self):
        """Update the answer widget based on current question."""
        current_question = self.qa_question_combo.currentText()
        if not current_question:
            return
        
        # Find the question object
        question_obj = None
        for q in self._questions:
            if q["question"] == current_question:
                question_obj = q
                break
        
        if not question_obj:
            return
        
        # Remove current answer widget
        if self.qa_current_answer_widget:
            self.qa_answer_layout.removeWidget(self.qa_current_answer_widget)
            self.qa_current_answer_widget.deleteLater()
            self.qa_current_answer_widget = None
        
        # Get current answer
        current_answer = self._qa_answers.get(current_question, "")
        
        # Create appropriate widget based on options
        options = question_obj.get("options", [])
        
        if options:
            # Create dropdown for options
            self.qa_current_answer_widget = QComboBox()
            self.qa_current_answer_widget.addItem("-- Select an answer --")  # Default option
            self.qa_current_answer_widget.addItems(options)
            
            # Set current selection
            if current_answer and current_answer in options:
                index = options.index(current_answer) + 1  # +1 for default option
                self.qa_current_answer_widget.setCurrentIndex(index)
            
            # Connect signal
            self.qa_current_answer_widget.currentTextChanged.connect(self._on_dropdown_answer_changed)
            
        else:
            # Create text input for free text
            self.qa_current_answer_widget = QTextEdit()
            self.qa_current_answer_widget.setMaximumHeight(100)
            self.qa_current_answer_widget.setPlaceholderText("Enter your answer here...")
            self.qa_current_answer_widget.setPlainText(current_answer)
            
            # Connect signal
            self.qa_current_answer_widget.textChanged.connect(self._on_text_answer_changed)
        
        # Apply styling
        self.qa_current_answer_widget.setStyleSheet("""
            QComboBox, QTextEdit {
                background-color: #ffffff;
                border: 2px solid #cccccc;
                border-radius: 4px;
                padding: 8px;
                font-size: 11px;
            }
            QComboBox:focus, QTextEdit:focus {
                border: 2px solid #4CAF50;
                background-color: #f0fff0;
            }
        """)
        
        # Add to layout
        self.qa_answer_layout.addWidget(self.qa_current_answer_widget)
        self.qa_current_answer_widget.setVisible(True)
    
    def _on_dropdown_answer_changed(self, answer_text: str):
        """Handle dropdown answer selection."""
        if answer_text == "-- Select an answer --":
            answer_text = ""
        
        current_question = self.qa_question_combo.currentText()
        if current_question:
            self._qa_answers[current_question] = answer_text
            
            # Emit signal for saving
            self.qa_answer_changed.emit(current_question, answer_text)
            
            # Update progress display
            self._update_progress_display()
    
    def _on_text_answer_changed(self):
        """Handle text answer change."""
        current_question = self.qa_question_combo.currentText()
        if current_question and isinstance(self.qa_current_answer_widget, QTextEdit):
            answer = self.qa_current_answer_widget.toPlainText()
            self._qa_answers[current_question] = answer
            
            # Emit signal for saving
            self.qa_answer_changed.emit(current_question, answer)
            
            # Update progress display
            self._update_progress_display()
    
    def _save_current_answer(self):
        """Save the current answer before switching questions."""
        current_question = self.qa_question_combo.currentText()
        if current_question and self.qa_current_answer_widget:
            if isinstance(self.qa_current_answer_widget, QComboBox):
                answer = self.qa_current_answer_widget.currentText()
                if answer == "-- Select an answer --":
                    answer = ""
            elif isinstance(self.qa_current_answer_widget, QTextEdit):
                answer = self.qa_current_answer_widget.toPlainText()
            else:
                answer = ""
            
            self._qa_answers[current_question] = answer
    
    def _update_progress_display(self):
        """Update the progress indicator."""
        if not self._questions:
            return
        
        answered_count = sum(1 for answer in self._qa_answers.values() if answer.strip())
        total_count = len(self._questions)
        
        self.qa_progress_label.setText(f"Answered: {answered_count}/{total_count} questions")
        
        # Change color based on progress
        if answered_count == 0:
            color = "#999999"
        elif answered_count == total_count:
            color = "#4CAF50"  # Green when complete
        else:
            color = "#FF9800"  # Orange for partial
        
        self.qa_progress_label.setStyleSheet(f"color: {color}; font-size: 10px; margin-top: 5px;")
    
    def set_qa_answers(self, answers: dict):
        """Set answers for the current bounding box."""
        self._qa_answers = answers.copy()
        
        # Update current answer display
        self._update_answer_widget()
        
        # Update progress
        self._update_progress_display()
    
    def get_qa_answers(self) -> dict:
        """Get current answers from all questions."""
        # Save current answer first
        self._save_current_answer()
        
        # Return only non-empty answers
        return {q: a for q, a in self._qa_answers.items() if a.strip()}
    
    def clear_qa_answers(self):
        """Clear all Q&A answer fields."""
        self._qa_answers = {}
        
        # Update current answer display
        self._update_answer_widget()
        
        # Update progress
        self._update_progress_display()
    
    def set_copy_boxes_count(self, count: int):
        """Set the number of images to copy boxes to."""
        self.copy_boxes_spinbox.setValue(count)
    
    def get_copy_boxes_count(self) -> int:
        """Get the number of images to copy boxes to."""
        return self.copy_boxes_spinbox.value()

