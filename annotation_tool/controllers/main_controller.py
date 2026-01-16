"""
Main controller orchestrating the entire application.
"""
import os
from typing import Optional
from PyQt5.QtCore import QObject, pyqtSignal
from ..models import ImageModel, AnnotationModel, SettingsModel, QuestionsModel, QAAnswersModel
from ..views import MainWindow
from ..views.preferences_dialog import PreferencesDialog
from .annotation_controller import AnnotationController


class MainController(QObject):
    """
    Main application controller that coordinates between all models, views, and controllers.
    """
    
    def __init__(self):
        super().__init__()
        
        # Initialize models
        self._settings_model = SettingsModel()
        self._image_model = ImageModel()
        self._annotation_model = AnnotationModel()
        self._questions_model = QuestionsModel()
        self._qa_answers_model = QAAnswersModel()
        
        # Initialize main window
        self._main_window = MainWindow()
        
        # Initialize annotation controller
        self._annotation_controller = AnnotationController(
            self._annotation_model,
            self._main_window.image_canvas,
            self._main_window.control_panel
        )
        
        # Connect signals
        self._connect_signals()
        
        # Initialize preferences dialog
        self._preferences_dialog = None
        
        # Load last session if enabled
        self._load_last_session()
        
        # Initialize Q&A system
        self._initialize_qa_system()
        
        # Show settings path (for debugging)
        print(f"Settings saved to: {self._settings_model.get_settings_file_path()}")
    
    def _connect_signals(self):
        """Connect all signals between models, views, and controllers."""
        # Image model signals
        self._image_model.current_image_changed.connect(self._on_current_image_changed)
        self._image_model.images_loaded.connect(self._on_images_loaded)
        
        # Main window signals
        self._main_window.load_images_from_directory.connect(self._on_load_images_from_directory)
        self._main_window.load_images_from_file_list.connect(self._on_load_images_from_file_list)
        self._main_window.load_class_names.connect(self._on_load_class_names)
        self._main_window.load_settings_file.connect(self._on_load_settings_file)
        self._main_window.qa_mode_toggled.connect(self._on_qa_mode_toggled)
        self._main_window.preferences_requested.connect(self._on_preferences_requested)
        self._main_window.window_closing.connect(self.save_window_state)
        
        # Settings model signals
        self._settings_model.settings_loaded_from_file.connect(self._on_settings_loaded)
        
        # Control panel signals
        self._main_window.control_panel.next_image_requested.connect(self._on_next_image_requested)
        self._main_window.control_panel.previous_image_requested.connect(self._on_previous_image_requested)
        self._main_window.control_panel.save_requested.connect(self._on_save_requested)
        self._main_window.control_panel.load_images_requested.connect(self._on_load_images_dialog)
        self._main_window.control_panel.load_classes_requested.connect(self._on_load_classes_dialog)
        self._main_window.control_panel.copy_boxes_to_next_requested.connect(self._on_copy_boxes_to_next_requested)
        self._main_window.undo_requested.connect(self._on_undo_requested)
        self._main_window.control_panel.qa_answer_changed.connect(self._on_qa_answer_changed)
        
        # Annotation controller signals
        self._annotation_controller.status_message.connect(self._main_window.show_message)
        self._annotation_controller.annotation_saved.connect(self._on_annotation_saved)
        self._annotation_controller.annotation_selected.connect(self._on_annotation_selected)
        
        # Q&A model signals
        self._questions_model.questions_loaded.connect(self._on_questions_loaded)
        self._qa_answers_model.answers_saved.connect(self._on_qa_answers_saved)
    
    def show(self):
        """Show the main window."""
        # Restore window geometry, but ensure it fits on screen
        from PyQt5.QtWidgets import QApplication
        screen = QApplication.primaryScreen().geometry()
        geometry = self._settings_model.get_window_geometry()
        
        # Ensure window fits on screen
        width = min(geometry["width"], int(screen.width() * 0.95))
        height = min(geometry["height"], int(screen.height() * 0.95))
        x = max(0, min(geometry["x"], screen.width() - width))
        y = max(0, min(geometry["y"], screen.height() - height))
        
        # Ensure minimum size
        width = max(width, 1200)
        height = max(height, 700)
        
        self._main_window.setGeometry(x, y, width, height)
        self._main_window.show()
    
    def _on_current_image_changed(self, index: int, image_path: str):
        """Handle current image changed."""
        # Load image in canvas
        success = self._main_window.image_canvas.load_image(image_path)
        
        if success:
            # Load annotations for this image
            self._annotation_controller.load_image_annotations(image_path)
            
            # Update navigation UI
            total_images = self._image_model.total_images
            self._main_window.control_panel.update_image_counter(index, total_images)
            
            # Update window title
            filename = os.path.basename(image_path)
            self._main_window.setWindowTitle(f"Annotation Tool (Scan Lab) - {filename}")
            
            # Update Q&A answers model with current image
            self._qa_answers_model.set_current_image(filename)
            
            self._main_window.show_message(f"Loaded image: {filename}")
        else:
            self._main_window.show_error("Error", f"Failed to load image: {image_path}")
    
    def _on_images_loaded(self, count: int):
        """Handle images loaded."""
        self._main_window.show_message(f"Loaded {count} images")
        
        # Enable/disable navigation based on image count
        has_images = count > 0
        self._main_window.control_panel.prev_btn.setEnabled(has_images)
        self._main_window.control_panel.next_btn.setEnabled(has_images)
    
    def _on_load_images_from_directory(self, directory: str):
        """Handle load images from directory request."""
        success = self._image_model.load_images_from_directory(directory)
        
        if success:
            # Save to settings for next time
            self._settings_model.set_last_image_directory(directory)
        else:
            self._main_window.show_error(
                "Error",
                f"No supported images found in directory: {directory}"
            )
    
    def _on_load_images_from_file_list(self, file_path: str, base_directory: str):
        """Handle load images from file list request."""
        success = self._image_model.load_images_from_file_list(file_path, base_directory)
        
        if success:
            # Save to settings for next time
            self._settings_model.set_last_image_list_file(file_path)
            if base_directory:
                self._settings_model.set_last_base_directory(base_directory)
        else:
            self._main_window.show_error(
                "Error",
                f"Failed to load images from file: {file_path}"
            )
    
    def _on_load_class_names(self, file_path: str):
        """Handle load class names request."""
        success = self._annotation_controller.load_class_names(file_path)
        
        if success:
            # Save to settings for next time
            self._settings_model.set_last_classes_file(file_path)
        else:
            self._main_window.show_error(
                "Error",
                f"Failed to load class names from: {file_path}"
            )
    
    def _on_next_image_requested(self):
        """Handle next image request."""
        if not self._image_model.next_image():
            self._main_window.show_message("Already at last image")
    
    def _on_previous_image_requested(self):
        """Handle previous image request."""
        if not self._image_model.previous_image():
            self._main_window.show_message("Already at first image")
    
    def _on_save_requested(self):
        """Handle save request."""
        success = self._annotation_controller.save_current_annotations()
        
        if not success:
            self._main_window.show_error("Error", "Failed to save annotations")
    
    def _on_copy_boxes_to_next_requested(self):
        """Handle copy boxes to next image request."""
        # Check if there are images loaded
        if self._image_model.total_images == 0:
            self._main_window.show_message("No images loaded")
            return
        
        # Check if we're not at the last image
        if self._image_model.current_index >= self._image_model.total_images - 1:
            self._main_window.show_message("Already at last image - cannot copy to next")
            return
        
        # Get current annotations
        current_annotations = self._annotation_model.annotations
        if not current_annotations:
            self._main_window.show_message("No annotations to copy")
            return
        
        # Save current annotations first
        self._annotation_controller.save_current_annotations()
        
        # Get next image path
        next_index = self._image_model.current_index + 1
        next_image_path = self._image_model.image_files[next_index]
        
        # Get next image's annotation path
        import os
        next_annotation_path = os.path.splitext(next_image_path)[0] + ".txt"
        
        # Load next image's existing annotations (if any)
        self._annotation_model.load_annotations(next_annotation_path)
        
        # Save original annotations from next image for undo
        original_next_annotations = [bbox.copy() for bbox in self._annotation_model.annotations]
        
        # Copy all boxes from current image (don't record undo for individual adds)
        copied_count = 0
        for bbox in current_annotations:
            # Create a copy of the bounding box
            copied_bbox = bbox.copy()
            # Add to annotations (don't record undo for individual adds - we'll record the whole operation)
            self._annotation_model.add_annotation(copied_bbox, record_undo=False)
            copied_count += 1
        
        # Save the next image's annotations with copied boxes
        success = self._annotation_model.save_annotations(next_annotation_path)
        
        if not success:
            self._main_window.show_error("Error", "Failed to save copied annotations")
            return
        
        # Reload current image's annotations to restore state
        current_image_path = self._image_model.current_image_path
        self._annotation_controller.load_image_annotations(current_image_path)
        
        # Record undo action for copy operation
        from ..models.undo_manager import ActionType
        self._annotation_model._undo_manager.push_action(
            ActionType.COPY_BOXES_TO_NEXT,
            {
                "current_image_path": current_image_path,
                "next_image_path": next_image_path,
                "copied_count": copied_count,
                "next_image_original_annotations": original_next_annotations
            }
        )
        
        # Show success message
        self._main_window.show_message(f"Copied {copied_count} annotation(s) to next image")
    
    def _on_annotation_saved(self):
        """Handle annotation saved."""
        # Could add additional logic here, like updating save status
        pass
    
    def _on_load_images_dialog(self):
        """Handle load images dialog request from control panel."""
        # This will trigger the main window's file dialog
        self._main_window._load_images_directory()
    
    def _on_load_classes_dialog(self):
        """Handle load classes dialog request from control panel."""
        # This will trigger the main window's file dialog
        self._main_window._load_class_names()
    
    def get_current_image_path(self) -> Optional[str]:
        """Get current image path."""
        return self._image_model.current_image_path
    
    def get_annotation_stats(self) -> dict:
        """Get annotation statistics."""
        return self._annotation_controller.get_annotation_stats()
    
    def load_sample_data(self):
        """Load sample data for testing (optional)."""
        # This could load some default images and classes for testing
        sample_classes = [
            "person",
            "car",
            "bicycle",
            "motorcycle",
            "airplane",
            "bus",
            "train",
            "truck",
            "boat",
            "traffic light"
        ]
        
        self._annotation_controller.set_class_names(sample_classes)
        self._main_window.show_message("Loaded sample classes")
    
    def export_annotations(self, export_path: str) -> bool:
        """
        Export all annotations to a file.
        
        Args:
            export_path: Path to export file
            
        Returns:
            bool: True if exported successfully
        """
        try:
            image_files = self._image_model.image_files
            all_annotations = []
            
            for image_path in image_files:
                annotation_path = os.path.splitext(image_path)[0] + ".txt"
                if os.path.exists(annotation_path):
                    with open(annotation_path, 'r', encoding='utf-8') as f:
                        lines = f.readlines()
                    
                    for line in lines:
                        all_annotations.append({
                            'image': image_path,
                            'annotation': line.strip()
                        })
            
            # Export to JSON or other format
            import json
            with open(export_path, 'w', encoding='utf-8') as f:
                json.dump(all_annotations, f, indent=2)
            
            self._main_window.show_message(f"Exported {len(all_annotations)} annotations")
            return True
            
        except Exception as e:
            self._main_window.show_error("Export Error", f"Failed to export annotations: {str(e)}")
            return False
    
    def import_annotations(self, import_path: str) -> bool:
        """
        Import annotations from a file.
        
        Args:
            import_path: Path to import file
            
        Returns:
            bool: True if imported successfully
        """
        try:
            import json
            with open(import_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            imported_count = 0
            for item in data:
                image_path = item['image']
                annotation_line = item['annotation']
                
                annotation_path = os.path.splitext(image_path)[0] + ".txt"
                
                # Append to existing annotations
                with open(annotation_path, 'a', encoding='utf-8') as f:
                    f.write(annotation_line + '\n')
                
                imported_count += 1
            
            # Reload current image annotations if any
            current_image = self._image_model.current_image_path
            if current_image:
                self._annotation_controller.load_image_annotations(current_image)
            
            self._main_window.show_message(f"Imported {imported_count} annotations")
            return True
            
        except Exception as e:
            self._main_window.show_error("Import Error", f"Failed to import annotations: {str(e)}")
            return False
    
    def _load_last_session(self):
        """Load the last session if auto-load is enabled."""
        if not self._settings_model.get_auto_load_last_session():
            # Set default class names if auto-load is disabled
            default_classes = ["object"]
            self._annotation_model.set_class_names(default_classes)
            return
        
        # Try to load last classes file first
        last_classes_file = self._settings_model.get_last_classes_file()
        if last_classes_file and os.path.exists(last_classes_file):
            success = self._annotation_controller.load_class_names(last_classes_file)
            if success:
                self._main_window.show_message(f"Restored classes from: {os.path.basename(last_classes_file)}")
        else:
            # Set default class names if no classes file
            default_classes = ["object"]
            self._annotation_model.set_class_names(default_classes)
        
        # Try to load last image directory
        last_image_dir = self._settings_model.get_last_image_directory()
        if last_image_dir and os.path.exists(last_image_dir):
            success = self._image_model.load_images_from_directory(last_image_dir)
            if success:
                self._main_window.show_message(f"Restored images from: {os.path.basename(last_image_dir)}")
                return
        
        # If no directory, try image list file
        last_image_list = self._settings_model.get_last_image_list_file()
        if last_image_list and os.path.exists(last_image_list):
            base_dir = self._settings_model.get_last_base_directory()
            success = self._image_model.load_images_from_file_list(last_image_list, base_dir)
            if success:
                self._main_window.show_message(f"Restored images from: {os.path.basename(last_image_list)}")
                return
        
        # If nothing was restored, show a helpful message
        if self._settings_model.has_previous_session():
            self._main_window.show_message("Previous session files not found - please reload your data")
        else:
            self._main_window.show_message("Welcome! Load images and classes to start annotating")
    
    def save_window_state(self):
        """Save current window state to settings."""
        geometry = self._main_window.geometry()
        self._settings_model.set_window_geometry(
            geometry.x(), geometry.y(), geometry.width(), geometry.height()
        )
    
    # Q&A Methods
    def _initialize_qa_system(self):
        """Initialize the Q&A system with saved settings."""
        # Load Q&A enabled state
        qa_enabled = self._settings_model.get_qa_enabled()
        self._main_window.set_qa_mode_enabled(qa_enabled)
        self._main_window.control_panel.set_qa_enabled(qa_enabled)
        
        # Load questions file if set
        questions_file = self._settings_model.get_qa_questions_file()
        if questions_file and os.path.exists(questions_file):
            self._questions_model.load_questions_from_file(questions_file)
        
        # Set answers folder
        answers_folder = self._settings_model.get_qa_answers_folder()
        if answers_folder:
            self._qa_answers_model.set_answers_folder(answers_folder)
    
    def _on_qa_mode_toggled(self, enabled: bool):
        """Handle Q&A mode toggle."""
        # Save the setting
        self._settings_model.set_qa_enabled(enabled)
        
        # Update control panel
        self._main_window.control_panel.set_qa_enabled(enabled)
        
        # Show status message
        status = "enabled" if enabled else "disabled"
        self._main_window.show_message(f"Q&A annotations {status}")
        
        # If enabling Q&A but no questions loaded, suggest loading questions
        if enabled and not self._questions_model.has_questions():
            self._main_window.show_message("No questions loaded. Use Tools > Preferences to configure.", 5000)
    
    def _on_preferences_requested(self):
        """Handle preferences dialog request."""
        if self._preferences_dialog is None:
            self._preferences_dialog = PreferencesDialog(self._main_window)
            
            # Connect dialog signals
            self._preferences_dialog.image_directory_changed.connect(self._on_image_directory_changed)
            self._preferences_dialog.image_list_file_changed.connect(self._on_image_list_file_changed)
            self._preferences_dialog.classes_file_changed.connect(self._on_classes_file_changed)
            self._preferences_dialog.qa_enabled_changed.connect(self._on_qa_mode_toggled)
            self._preferences_dialog.questions_file_changed.connect(self._on_questions_file_changed)
            self._preferences_dialog.answers_folder_changed.connect(self._on_answers_folder_changed)
            self._preferences_dialog.auto_load_session_changed.connect(self._on_auto_load_session_changed)
            self._preferences_dialog.auto_save_interval_changed.connect(self._on_auto_save_interval_changed)
            self._preferences_dialog.max_recent_items_changed.connect(self._on_max_recent_items_changed)
            self._preferences_dialog.settings_file_path_changed.connect(self._on_settings_file_path_changed)
        
        # Set current values
        self._preferences_dialog.set_image_directory(self._settings_model.get_last_image_directory())
        self._preferences_dialog.set_image_list_file(
            self._settings_model.get_last_image_list_file(),
            self._settings_model.get_last_base_directory()
        )
        self._preferences_dialog.set_classes_file(self._settings_model.get_last_classes_file())
        self._preferences_dialog.set_qa_enabled(self._settings_model.get_qa_enabled())
        self._preferences_dialog.set_questions_file(self._settings_model.get_qa_questions_file())
        self._preferences_dialog.set_answers_folder(self._settings_model.get_qa_answers_folder())
        self._preferences_dialog.set_auto_load_session(self._settings_model.get_auto_load_last_session())
        self._preferences_dialog.set_auto_save_interval(self._settings_model.get_auto_save_interval())
        self._preferences_dialog.set_max_recent_items(self._settings_model.get_max_recent_items())
        self._preferences_dialog.set_settings_file_path(self._settings_model.get_settings_file_path())
        
        # Show dialog
        self._preferences_dialog.exec_()
    
    def _on_image_directory_changed(self, directory: str):
        """Handle image directory change."""
        self._settings_model.set_last_image_directory(directory)
        # Optionally load images from the new directory
        if directory and os.path.isdir(directory):
            self._image_model.load_images_from_directory(directory)
            self._main_window.show_message(f"Loaded images from: {os.path.basename(directory)}")
    
    def _on_image_list_file_changed(self, file_path: str, base_directory: str):
        """Handle image list file change."""
        self._settings_model.set_last_image_list_file(file_path)
        if base_directory:
            self._settings_model.set_last_base_directory(base_directory)
        # Optionally load images from the new list
        if file_path and os.path.isfile(file_path):
            self._image_model.load_images_from_file_list(file_path, base_directory)
            self._main_window.show_message(f"Loaded images from list: {os.path.basename(file_path)}")
    
    def _on_classes_file_changed(self, file_path: str):
        """Handle classes file change."""
        self._settings_model.set_last_classes_file(file_path)
        # Optionally load classes from the new file
        if file_path and os.path.isfile(file_path):
            self._annotation_controller.load_class_names(file_path)
            self._main_window.show_message(f"Loaded classes from: {os.path.basename(file_path)}")
    
    def _on_questions_file_changed(self, file_path: str):
        """Handle questions file change."""
        if self._questions_model.load_questions_from_file(file_path):
            self._settings_model.set_qa_questions_file(file_path)
            self._main_window.show_message(f"Loaded {self._questions_model.get_question_count()} questions")
        else:
            self._main_window.show_error("Error", "Failed to load questions file")
    
    def _on_answers_folder_changed(self, folder_path: str):
        """Handle answers folder change."""
        self._qa_answers_model.set_answers_folder(folder_path)
        self._settings_model.set_qa_answers_folder(folder_path)
        self._main_window.show_message(f"Q&A answers will be saved to: {os.path.basename(folder_path)}")
    
    def _on_auto_load_session_changed(self, enabled: bool):
        """Handle auto-load session preference change."""
        self._settings_model.set_auto_load_last_session(enabled)
        self._main_window.show_message(f"Auto-load last session: {'enabled' if enabled else 'disabled'}")
    
    def _on_auto_save_interval_changed(self, interval: int):
        """Handle auto-save interval change."""
        self._settings_model.set_auto_save_interval(interval)
        # Update the auto-save timer in main window if needed
        self._main_window.show_message(f"Auto-save interval set to {interval} seconds")
    
    def _on_max_recent_items_changed(self, max_items: int):
        """Handle max recent items change."""
        self._settings_model.set_max_recent_items(max_items)
        self._main_window.show_message(f"Maximum recent items set to {max_items}")
    
    def _on_undo_requested(self):
        """Handle undo request."""
        # Check if we can undo
        if not self._annotation_model.can_undo():
            self._main_window.show_message("Nothing to undo")
            return False
        
        # Get the last action to check if it's a copy operation
        from ..models.undo_manager import ActionType
        undo_manager = self._annotation_model._undo_manager
        
        # Peek at the last action without removing it
        if undo_manager._undo_stack:
            last_action = undo_manager._undo_stack[-1]
            
            # If it's a copy operation, handle it specially
            if last_action.action_type == ActionType.COPY_BOXES_TO_NEXT:
                # Pop the action
                action = undo_manager.pop_action()
                data = action.data
                
                # Restore next image's original annotations
                next_image_path = data["next_image_path"]
                original_annotations = data["next_image_original_annotations"]
                current_image_path = data["current_image_path"]
                
                # Save current image first
                self._annotation_controller.save_current_annotations()
                
                # Get next image index
                next_index = None
                for i, img_path in enumerate(self._image_model.image_files):
                    if img_path == next_image_path:
                        next_index = i
                        break
                
                if next_index is not None and next_index < self._image_model.total_images:
                    # Load next image
                    self._image_model.set_current_index(next_index)
                    self._annotation_controller.load_image_annotations(next_image_path)
                    
                    # Restore original annotations (don't record undo for this)
                    self._annotation_model._annotations = [bbox.copy() for bbox in original_annotations]
                    self._annotation_model.annotations_changed.emit()
                    
                    # Save next image
                    import os
                    next_annotation_path = os.path.splitext(next_image_path)[0] + ".txt"
                    self._annotation_model.save_annotations(next_annotation_path)
                    
                    # Reload current image
                    current_index = None
                    for i, img_path in enumerate(self._image_model.image_files):
                        if img_path == current_image_path:
                            current_index = i
                            break
                    
                    if current_index is not None:
                        self._image_model.set_current_index(current_index)
                        self._annotation_controller.load_image_annotations(current_image_path)
                    
                    self._main_window.show_message(f"Undid copy of {data['copied_count']} annotation(s)")
                    return True
        
        # For other actions, use the model's undo method
        success = self._annotation_model.undo()
        if success:
            # Auto-save after undo
            self._annotation_controller.save_current_annotations()
            self._main_window.show_message("Undo successful")
        else:
            self._main_window.show_message("Nothing to undo")
        
        return success
    
    def _on_settings_file_path_changed(self, file_path: str):
        """Handle settings file path change."""
        if self._settings_model.load_settings_from_file(file_path):
            self._main_window.show_message(f"Settings loaded from: {os.path.basename(file_path)}")
            # Reload session data based on new settings
            self._load_last_session()
            # Reinitialize Q&A system with new settings
            self._initialize_qa_system()
        else:
            self._main_window.show_error("Error", "Failed to load settings file. Please check the file format.")
    
    def _on_questions_loaded(self, questions: list):
        """Handle questions loaded."""
        self._main_window.control_panel.load_questions(questions)
    
    def _on_qa_answer_changed(self, question: str, answer: str):
        """Handle Q&A answer change."""
        # Save answers automatically when they change
        if self._annotation_controller.get_current_annotation_index() >= 0:
            self._save_current_qa_answers()
    
    def _on_annotation_selected(self, index: int):
        """Handle annotation selection - load Q&A answers for selected annotation."""
        if index >= 0 and self._main_window.control_panel._qa_enabled:
            # Get current annotation
            annotations = self._annotation_model.annotations
            if 0 <= index < len(annotations):
                bbox = annotations[index]
                
                # Load answers for this bounding box
                answers = self._qa_answers_model.get_answers_for_bbox(
                    index, bbox.class_id, bbox.x, bbox.y, bbox.width, bbox.height
                )
                
                # Set answers in control panel
                self._main_window.control_panel.set_qa_answers(answers)
        else:
            # Clear answers when no annotation selected
            self._main_window.control_panel.clear_qa_answers()
    
    def _save_current_qa_answers(self):
        """Save current Q&A answers for the selected annotation."""
        index = self._annotation_controller.get_current_annotation_index()
        if index < 0:
            return
        
        annotations = self._annotation_model.annotations
        if index >= len(annotations):
            return
        
        bbox = annotations[index]
        answers = self._main_window.control_panel.get_qa_answers()
        
        # Save answers to model
        self._qa_answers_model.set_answers_for_bbox(
            index, bbox.class_id, bbox.x, bbox.y, bbox.width, bbox.height, answers
        )
        
        # Save to file
        self._qa_answers_model.save_current_answers()
    
    def _on_qa_answers_saved(self, file_path: str):
        """Handle Q&A answers saved."""
        # Optional: Show a brief message
        pass
    
    def _on_load_settings_file(self, file_path: str):
        """Handle settings file load request."""
        if self._settings_model.load_settings_from_file(file_path):
            self._main_window.show_message(f"Settings loaded from: {os.path.basename(file_path)}")
            # Reload session data based on new settings
            self._load_last_session()
            # Reinitialize Q&A system with new settings
            self._initialize_qa_system()
        else:
            self._main_window.show_error("Error", "Failed to load settings file. Please check the file format.")
    
    def _on_settings_loaded(self, file_path: str):
        """Handle settings loaded from file signal."""
        # Update window geometry if changed
        geometry = self._settings_model.get_window_geometry()
        self._main_window.setGeometry(geometry["x"], geometry["y"], geometry["width"], geometry["height"])
    

