"""
Main controller orchestrating the entire application.
"""
import os
from typing import Optional
from PyQt5.QtCore import QObject, pyqtSignal, QThread, Qt
from PyQt5.QtWidgets import QProgressDialog
from PIL import Image
from ..models import ImageModel, AnnotationModel, SettingsModel, QuestionsModel, QAAnswersModel
from ..views import MainWindow
from ..views.preferences_dialog import PreferencesDialog
from .annotation_controller import AnnotationController


class _TiffToJpgWorker(QObject):
    """Background worker to convert TIFF files to JPG without blocking the UI."""
    
    progress = pyqtSignal(int, int)  # completed, total
    finished = pyqtSignal(int, int, int, bool)  # converted, errors, total, cancelled
    
    def __init__(self, files, output_dir: str):
        super().__init__()
        self._files = list(files)
        self._output_dir = output_dir
        self._cancelled = False
    
    def cancel(self):
        """Request cancellation."""
        self._cancelled = True
    
    def run(self):
        """Run the conversion loop in a background thread."""
        total = len(self._files)
        converted = 0
        errors = 0
        
        for idx, src_path in enumerate(self._files, start=1):
            if self._cancelled:
                break
            
            try:
                with Image.open(src_path) as img:
                    # Use first frame for multi-page TIFFs
                    try:
                        img.seek(0)
                    except Exception:
                        # Some images may not be multi-frame; ignore
                        pass
                    
                    # Get image mode and handle different TIFF formats
                    mode = img.mode
                    
                    # Handle transparency/alpha channel by compositing on white background
                    if mode in ('RGBA', 'LA', 'P') and 'transparency' in img.info:
                        # Create white background
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        if mode == 'P':
                            # Palette mode with transparency
                            img = img.convert('RGBA')
                        # Composite image on white background
                        background.paste(img, mask=img.split()[-1] if img.mode == 'RGBA' else None)
                        rgb = background
                    elif mode == 'RGBA':
                        # RGBA without transparency info - composite on white
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        background.paste(img, mask=img.split()[-1])
                        rgb = background
                    elif mode == 'LA':
                        # Grayscale with alpha - convert to RGB
                        background = Image.new('RGB', img.size, (255, 255, 255))
                        rgb_img = img.convert('RGB')
                        background.paste(rgb_img, mask=img.split()[-1])
                        rgb = background
                    elif mode == 'CMYK':
                        # CMYK color mode - convert to RGB
                        rgb = img.convert('RGB')
                    elif mode == 'L':
                        # Grayscale - convert to RGB
                        rgb = img.convert('RGB')
                    elif mode == 'P':
                        # Palette mode - convert to RGB
                        rgb = img.convert('RGB')
                    elif mode == 'RGB':
                        # Already RGB
                        rgb = img
                    else:
                        # Fallback: try to convert to RGB
                        print(f"Warning: Unknown image mode '{mode}' for {src_path}, attempting RGB conversion")
                        rgb = img.convert('RGB')
                    
                    # Handle 16-bit TIFFs - Pillow's convert might not handle them properly
                    # Check if image is 16-bit and needs scaling
                    if mode in ('I', 'I;16', 'I;16B', 'I;16L') or 'I;16' in mode:
                        # 16-bit integer mode - need to scale to 8-bit
                        try:
                            import numpy as np
                            # Convert to numpy array
                            arr = np.array(img)
                            if arr.dtype == np.uint16 or arr.dtype == np.int16:
                                # Normalize 16-bit to 8-bit range (0-65535 -> 0-255)
                                arr_normalized = ((arr.astype(np.float32) / 65535.0) * 255.0).astype(np.uint8)
                                # Convert back to PIL Image
                                rgb = Image.fromarray(arr_normalized, mode='RGB' if len(arr_normalized.shape) == 3 else 'L')
                                if rgb.mode == 'L':
                                    rgb = rgb.convert('RGB')
                            else:
                                # Already 8-bit or other format, just convert to RGB
                                rgb = Image.fromarray(arr).convert('RGB')
                        except ImportError:
                            # NumPy not available - use Pillow's point operation
                            # This is a fallback but may not work perfectly for 16-bit
                            if rgb.mode in ('I', 'I;16'):
                                rgb = rgb.convert('RGB')
                        except Exception as e:
                            print(f"Warning: Could not handle 16-bit image {src_path}: {e}")
                            # Fallback to simple conversion
                            rgb = img.convert('RGB')
                    
                    base_name = os.path.splitext(os.path.basename(src_path))[0]
                    dst_path = os.path.join(self._output_dir, base_name + ".jpg")
                    
                    # Save as JPEG with quality 95
                    rgb.save(dst_path, "JPEG", quality=95, optimize=True)
                    converted += 1
            except Exception as e:
                errors += 1
                print(f"Error converting {src_path} to JPG: {e}")
                import traceback
                traceback.print_exc()
            
            self.progress.emit(idx, total)
        
        self.finished.emit(converted, errors, total, self._cancelled)


class _ExportAnnotationsWorker(QObject):
    """Background worker to export annotations without blocking the UI."""
    
    progress = pyqtSignal(int, int)  # completed, total
    finished = pyqtSignal(bool, int, str)  # success, count, error_message
    
    def __init__(self, image_files, export_path: str):
        super().__init__()
        self._image_files = list(image_files)
        self._export_path = export_path
        self._cancelled = False
    
    def cancel(self):
        self._cancelled = True
    
    def run(self):
        import json
        
        all_annotations = []
        total = len(self._image_files)
        
        try:
            for idx, image_path in enumerate(self._image_files, start=1):
                if self._cancelled:
                    # Treat as successful but with partial data; controller can decide messaging.
                    break
                
                annotation_path = os.path.splitext(image_path)[0] + ".txt"
                if os.path.exists(annotation_path):
                    try:
                        with open(annotation_path, 'r', encoding='utf-8') as f:
                            lines = f.readlines()
                        for line in lines:
                            all_annotations.append({
                                'image': image_path,
                                'annotation': line.strip()
                            })
                    except Exception as e:
                        print(f"Error reading {annotation_path} during export: {e}")
                
                self.progress.emit(idx, total)
            
            # Write out the collected annotations
            with open(self._export_path, 'w', encoding='utf-8') as f:
                json.dump(all_annotations, f, indent=2)
            
            self.finished.emit(True, len(all_annotations), "")
        except Exception as e:
            self.finished.emit(False, 0, str(e))


class _ImportAnnotationsWorker(QObject):
    """Background worker to import annotations without blocking the UI."""
    
    progress = pyqtSignal(int, int)  # completed, total
    finished = pyqtSignal(bool, int, str)  # success, count, error_message
    
    def __init__(self, import_path: str):
        super().__init__()
        self._import_path = import_path
        self._cancelled = False
    
    def cancel(self):
        self._cancelled = True
    
    def run(self):
        import json
        
        try:
            with open(self._import_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            self.finished.emit(False, 0, f"Failed to read import file: {e}")
            return
        
        total = len(data)
        imported_count = 0
        
        try:
            for idx, item in enumerate(data, start=1):
                if self._cancelled:
                    break
                
                try:
                    image_path = item['image']
                    annotation_line = item['annotation']
                    annotation_path = os.path.splitext(image_path)[0] + ".txt"
                    
                    # Append to existing annotations
                    with open(annotation_path, 'a', encoding='utf-8') as f:
                        f.write(annotation_line + '\n')
                    
                    imported_count += 1
                except Exception as e:
                    print(f"Error importing annotation for {item.get('image')}: {e}")
                
                self.progress.emit(idx, total)
            
            self.finished.emit(True, imported_count, "")
        except Exception as e:
            self.finished.emit(False, imported_count, str(e))


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
        
        # Initialize control panel with settings
        self._main_window.control_panel.set_copy_boxes_count(self._settings_model.get_copy_boxes_count())
        
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
        self._main_window.convert_tiff_to_jpg_requested.connect(self._on_convert_tiff_to_jpg)
        self._main_window.qa_mode_toggled.connect(self._on_qa_mode_toggled)
        self._main_window.preferences_requested.connect(self._on_preferences_requested)
        self._main_window.window_closing.connect(self.save_window_state)
        self._main_window.sidebar_width_changed.connect(self._on_sidebar_width_changed)
        
        # Settings model signals
        self._settings_model.settings_loaded_from_file.connect(self._on_settings_loaded)
        
        # Control panel signals
        self._main_window.control_panel.next_image_requested.connect(self._on_next_image_requested)
        self._main_window.control_panel.previous_image_requested.connect(self._on_previous_image_requested)
        self._main_window.control_panel.image_index_requested.connect(self._on_image_index_requested)
        self._main_window.control_panel.save_requested.connect(self._on_save_requested)
        self._main_window.control_panel.load_images_requested.connect(self._on_load_images_dialog)
        self._main_window.control_panel.load_classes_requested.connect(self._on_load_classes_dialog)
        self._main_window.control_panel.copy_boxes_to_next_requested.connect(self._on_copy_boxes_to_next_requested)
        self._main_window.control_panel.copy_boxes_count_changed.connect(self._on_copy_boxes_count_changed)
        self._main_window.control_panel.toggle_panel_requested.connect(self._on_toggle_panel_requested)
        self._main_window.undo_requested.connect(self._on_undo_requested)
        self._main_window.redo_requested.connect(self._on_redo_requested)
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
        
        # Show window first so it has proper dimensions
        self._main_window.show()
        
        # Restore sidebar width if saved (after window is shown so dimensions are correct)
        saved_width = self._settings_model.get_sidebar_width()
        if saved_width > 0:
            # Use QTimer to ensure window is fully rendered before setting splitter sizes
            from PyQt5.QtCore import QTimer
            QTimer.singleShot(100, lambda: self._main_window.set_sidebar_width(saved_width))
    
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
    
    def _on_convert_tiff_to_jpg(self, input_dir: str, output_dir: str):
        """Handle TIFF to JPG conversion request using a background thread and progress dialog."""
        if not os.path.isdir(input_dir):
            self._main_window.show_error("Invalid Input Folder", f"Input folder does not exist:\n{input_dir}")
            return
        
        if not os.path.isdir(output_dir):
            try:
                os.makedirs(output_dir, exist_ok=True)
            except Exception as e:
                self._main_window.show_error("Invalid Output Folder", f"Cannot create output folder:\n{output_dir}\n\n{e}")
                return
        
        # Find TIFF files (.tif, .tiff)
        tiff_files = []
        for name in os.listdir(input_dir):
            lower = name.lower()
            if lower.endswith(".tif") or lower.endswith(".tiff"):
                tiff_files.append(os.path.join(input_dir, name))
        
        if not tiff_files:
            self._main_window.show_message("No TIFF files found in the selected input folder", 5000)
            return
        
        total = len(tiff_files)
        
        # Set up progress dialog
        progress = QProgressDialog(
            "Converting TIFF to JPG...",
            "Cancel",
            0,
            total,
            self._main_window
        )
        progress.setWindowModality(Qt.WindowModal)
        progress.setWindowTitle("TIFF to JPG Conversion")
        progress.setMinimumDuration(0)
        progress.setValue(0)
        
        # Create worker and thread
        worker = _TiffToJpgWorker(tiff_files, output_dir)
        thread = QThread(self)
        worker.moveToThread(thread)
        
        # Keep references to prevent garbage collection
        self._tiff_thread = thread
        self._tiff_worker = worker
        self._tiff_progress = progress
        
        # Wire up signals
        def on_progress(done: int, total_files: int):
            progress.setMaximum(total_files)
            progress.setValue(done)
        
        def on_finished(converted: int, errors: int, total_files: int, cancelled: bool):
            progress.close()
            
            if cancelled:
                msg = f"Conversion cancelled after {converted} of {total_files} file(s) converted"
                if errors:
                    msg += f" (with {errors} error(s) – see console for details)"
                self._main_window.show_warning("Conversion Cancelled", msg)
            elif converted > 0:
                msg = f"Converted {converted} TIFF file(s) to JPG"
                if errors:
                    msg += f" (with {errors} error(s) – see console for details)"
                self._main_window.show_message(msg, 8000)
            else:
                self._main_window.show_error("Conversion Failed", "No TIFF files could be converted to JPG.")
            
            thread.quit()
            thread.wait()
            worker.deleteLater()
            thread.deleteLater()
            self._tiff_thread = None
            self._tiff_worker = None
            self._tiff_progress = None
        
        worker.progress.connect(on_progress)
        worker.finished.connect(on_finished)
        thread.started.connect(worker.run)
        
        def on_cancel():
            worker.cancel()
        
        progress.canceled.connect(on_cancel)
        
        # Start background conversion
        thread.start()
    
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
    
    def _on_image_index_requested(self, index: int):
        """Handle image index request from slider."""
        if self._image_model.set_current_index(index):
            # Image change will be handled by the current_image_changed signal
            pass
        else:
            self._main_window.show_message(f"Invalid image index: {index}")
    
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
        
        # Get copy count from settings
        copy_count = self._settings_model.get_copy_boxes_count()
        
        # Check if we have enough images ahead
        current_index = self._image_model.current_index
        max_available = self._image_model.total_images - current_index - 1
        if max_available <= 0:
            self._main_window.show_message("Already at last image - cannot copy to next")
            return
        
        # Limit copy_count to available images
        if copy_count > max_available:
            self._main_window.show_message(f"Only {max_available} image(s) available, copying to {max_available} image(s)")
            copy_count = max_available
        
        # Get current annotations
        current_annotations = self._annotation_model.annotations
        if not current_annotations:
            self._main_window.show_message("No annotations to copy")
            return
        
        # Show dialog to select boxes
        from ..views.box_selection_dialog import BoxSelectionDialog
        from PyQt5.QtWidgets import QDialog
        dialog = BoxSelectionDialog(
            current_annotations,
            self._annotation_model.class_names,
            self._main_window
        )
        
        # Connect dialog signals to canvas for visual feedback
        def on_selection_changed(selected_indices):
            """Update canvas highlights when selection changes."""
            self._main_window.image_canvas.set_highlighted_indices(selected_indices)
        
        def on_checkbox_hovered(index, is_entering):
            """Highlight individual box on hover."""
            if is_entering:
                # Show just this box highlighted
                self._main_window.image_canvas.set_highlighted_indices({index})
            else:
                # Return to showing all selected boxes
                selected_indices = dialog.get_selected_indices()
                self._main_window.image_canvas.set_highlighted_indices(set(selected_indices))
        
        dialog.selection_changed.connect(on_selection_changed)
        dialog.checkbox_hovered.connect(on_checkbox_hovered)
        
        # Show dialog and check if user clicked OK
        result = dialog.exec_()
        
        # Clear highlights when dialog closes
        self._main_window.image_canvas.clear_highlights()
        
        if result != QDialog.Accepted:
            return  # User cancelled
        
        # Get selected annotations
        selected_annotations = dialog.get_selected_annotations()
        if not selected_annotations:
            self._main_window.show_message("No boxes selected")
            return
        
        # Save current annotations first
        self._annotation_controller.save_current_annotations()
        
        import os
        current_image_path = self._image_model.current_image_path
        copied_images = []
        total_copied_count = 0
        
        # Copy to N images
        from PyQt5.QtWidgets import QProgressDialog
        from PyQt5.QtCore import QCoreApplication
        
        progress = QProgressDialog(
            "Copying boxes to next images...",
            "Cancel",
            0,
            copy_count,
            self._main_window
        )
        progress.setWindowModality(Qt.WindowModal)
        progress.setWindowTitle("Copy Boxes")
        progress.setMinimumDuration(0)
        progress.setValue(0)
        
        for i in range(1, copy_count + 1):
            target_index = current_index + i
            if target_index >= self._image_model.total_images:
                break
            
            # Get target image path from the list
            image_files = self._image_model.image_files
            if target_index >= len(image_files):
                break
            
            target_image_path = image_files[target_index]
            target_annotation_path = os.path.splitext(target_image_path)[0] + ".txt"
            
            # Load target image's existing annotations (if any)
            self._annotation_model.load_annotations(target_annotation_path)
            
            # Save original annotations from target image for undo
            original_annotations = [bbox.copy() for bbox in self._annotation_model.annotations]
            
            # Copy only selected boxes from current image (don't record undo for individual adds)
            for bbox in selected_annotations:
                # Create a copy of the bounding box
                copied_bbox = bbox.copy()
                # Add to annotations (don't record undo for individual adds - we'll record the whole operation)
                self._annotation_model.add_annotation(copied_bbox, record_undo=False)
                total_copied_count += 1
            
            # Save the target image's annotations with copied boxes
            success = self._annotation_model.save_annotations(target_annotation_path)
            
            if not success:
                self._main_window.show_error("Error", f"Failed to save copied annotations to image {i}")
                continue
            
            copied_images.append({
                "image_path": target_image_path,
                "annotation_path": target_annotation_path,
                "original_annotations": original_annotations
            })
            
            # Update progress
            progress.setValue(i)
            QCoreApplication.processEvents()
            if progress.wasCanceled():
                break
        
        progress.close()
        
        # Reload current image's annotations to restore state
        self._annotation_controller.load_image_annotations(current_image_path)
        
        # Record undo action for copy operation
        from ..models.undo_manager import ActionType
        self._annotation_model._undo_manager.push_action(
            ActionType.COPY_BOXES_TO_NEXT,
            {
                "current_image_path": current_image_path,
                "copied_images": copied_images,
                "copied_count": total_copied_count
            }
        )
        
        # Show success message
        self._main_window.show_message(f"Copied {len(selected_annotations)} annotation(s) to {len(copied_images)} image(s)")
    
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
            total = len(image_files)
            if total == 0:
                self._main_window.show_message("No images loaded to export annotations from")
                return False
            
            progress = QProgressDialog(
                "Exporting annotations...",
                "Cancel",
                0,
                total,
                self._main_window
            )
            progress.setWindowModality(Qt.WindowModal)
            progress.setWindowTitle("Export Annotations")
            progress.setMinimumDuration(0)
            progress.setValue(0)
            
            worker = _ExportAnnotationsWorker(image_files, export_path)
            thread = QThread(self)
            worker.moveToThread(thread)
            
            self._export_thread = thread
            self._export_worker = worker
            self._export_progress = progress
            
            def on_progress(done: int, total_files: int):
                progress.setMaximum(total_files)
                progress.setValue(done)
            
            def on_finished(success: bool, count: int, error_message: str):
                progress.close()
                
                if success:
                    self._main_window.show_message(f"Exported {count} annotations")
                else:
                    self._main_window.show_error("Export Error", f"Failed to export annotations: {error_message}")
                
                thread.quit()
                thread.wait()
                worker.deleteLater()
                thread.deleteLater()
                self._export_thread = None
                self._export_worker = None
                self._export_progress = None
            
            worker.progress.connect(on_progress)
            worker.finished.connect(on_finished)
            thread.started.connect(worker.run)
            
            def on_cancel():
                worker.cancel()
            
            progress.canceled.connect(on_cancel)
            
            thread.start()
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
            if not os.path.exists(import_path):
                self._main_window.show_error("Import Error", f"Import file does not exist:\n{import_path}")
                return False
            
            # We don't know the total count yet without reading the file, so let the worker handle it
            worker = _ImportAnnotationsWorker(import_path)
            thread = QThread(self)
            worker.moveToThread(thread)
            
            # Temporary progress dialog; maximum will be updated once we know total
            progress = QProgressDialog(
                "Importing annotations...",
                "Cancel",
                0,
                0,
                self._main_window
            )
            progress.setWindowModality(Qt.WindowModal)
            progress.setWindowTitle("Import Annotations")
            progress.setMinimumDuration(0)
            progress.setValue(0)
            
            self._import_thread = thread
            self._import_worker = worker
            self._import_progress = progress
            
            def on_progress(done: int, total_items: int):
                progress.setMaximum(total_items)
                progress.setValue(done)
            
            def on_finished(success: bool, count: int, error_message: str):
                progress.close()
                
                if success:
                    # Reload current image annotations if any
                    current_image = self._image_model.current_image_path
                    if current_image:
                        self._annotation_controller.load_image_annotations(current_image)
                    
                    self._main_window.show_message(f"Imported {count} annotations")
                else:
                    self._main_window.show_error("Import Error", f"Failed to import annotations: {error_message}")
                
                thread.quit()
                thread.wait()
                worker.deleteLater()
                thread.deleteLater()
                self._import_thread = None
                self._import_worker = None
                self._import_progress = None
            
            worker.progress.connect(on_progress)
            worker.finished.connect(on_finished)
            thread.started.connect(worker.run)
            
            def on_cancel():
                worker.cancel()
            
            progress.canceled.connect(on_cancel)
            
            thread.start()
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
            self._preferences_dialog.copy_boxes_count_changed.connect(self._on_copy_boxes_count_changed)
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
        self._preferences_dialog.set_copy_boxes_count(self._settings_model.get_copy_boxes_count())
        self._preferences_dialog.set_settings_file_path(self._settings_model.get_settings_file_path())
        
        # Set control panel value
        self._main_window.control_panel.set_copy_boxes_count(self._settings_model.get_copy_boxes_count())
        
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
    
    def _on_copy_boxes_count_changed(self, count: int):
        """Handle copy boxes count preference change."""
        self._settings_model.set_copy_boxes_count(count)
        # Sync control panel value
        self._main_window.control_panel.set_copy_boxes_count(count)
        self._main_window.show_message(f"Copy boxes count set to: {count}")
    
    def _on_toggle_panel_requested(self):
        """Handle toggle panel request from control panel button."""
        # Toggle the current state
        current_state = self._main_window.control_panel.isVisible()
        self._main_window._toggle_control_panel(not current_state)
    
    def _on_sidebar_width_changed(self, width: int):
        """Handle sidebar width change - save to settings."""
        self._settings_model.set_sidebar_width(width)
    
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
                
                current_image_path = data["current_image_path"]
                copied_images = data.get("copied_images", [])
                
                # Save current image first
                self._annotation_controller.save_current_annotations()
                
                import os
                # Restore original annotations for all copied images
                for img_data in copied_images:
                    target_image_path = img_data["image_path"]
                    target_annotation_path = img_data["annotation_path"]
                    original_annotations = img_data["original_annotations"]
                    
                    # Get target image index
                    target_index = None
                    for i, img_path in enumerate(self._image_model.image_files):
                        if img_path == target_image_path:
                            target_index = i
                            break
                    
                    if target_index is not None and target_index < self._image_model.total_images:
                        # Load target image
                        self._image_model.set_current_index(target_index)
                        self._annotation_controller.load_image_annotations(target_image_path)
                        
                        # Restore original annotations (don't record undo for this)
                        self._annotation_model._annotations = [bbox.copy() for bbox in original_annotations]
                        self._annotation_model.annotations_changed.emit()
                        
                        # Save target image
                        self._annotation_model.save_annotations(target_annotation_path)
                
                # Reload current image
                current_index = None
                for i, img_path in enumerate(self._image_model.image_files):
                    if img_path == current_image_path:
                        current_index = i
                        break
                
                if current_index is not None:
                    self._image_model.set_current_index(current_index)
                    self._annotation_controller.load_image_annotations(current_image_path)
                
                self._main_window.show_message(f"Undid copy to {len(copied_images)} image(s)")
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
    
    def _on_redo_requested(self):
        """Handle redo request."""
        # Check if we can redo
        if not self._annotation_model.can_redo():
            self._main_window.show_message("Nothing to redo")
            return False
        
        # Get the last redo action to check if it's a copy operation
        from ..models.undo_manager import ActionType
        undo_manager = self._annotation_model._undo_manager
        
        # Peek at the last redo action without removing it
        if undo_manager._redo_stack:
            last_action = undo_manager._redo_stack[-1]
            
            # If it's a copy operation, handle it specially
            if last_action.action_type == ActionType.COPY_BOXES_TO_NEXT:
                # Pop the action from redo (moves it back to undo stack)
                action = undo_manager.pop_redo_action()
                data = action.data
                
                # Re-execute the copy operation
                current_image_path = data["current_image_path"]
                copied_images = data.get("copied_images", [])
                
                # Get current image index to reload annotations
                current_index = None
                for i, img_path in enumerate(self._image_model.image_files):
                    if img_path == current_image_path:
                        current_index = i
                        break
                
                if current_index is None:
                    self._main_window.show_message("Cannot redo: current image not found")
                    return False
                
                # Get current annotations from the current image
                self._image_model.set_current_index(current_index)
                self._annotation_controller.load_image_annotations(current_image_path)
                current_annotations = [bbox.copy() for bbox in self._annotation_model.annotations]
                
                # Save current annotations first
                self._annotation_controller.save_current_annotations()
                
                import os
                # Copy to all target images again
                for img_data in copied_images:
                    target_image_path = img_data["image_path"]
                    target_annotation_path = img_data["annotation_path"]
                    
                    # Load target image's existing annotations
                    self._annotation_model.load_annotations(target_annotation_path)
                    
                    # Copy all boxes from current image
                    for bbox in current_annotations:
                        copied_bbox = bbox.copy()
                        self._annotation_model.add_annotation(copied_bbox, record_undo=False)
                    
                    # Save the target image's annotations
                    self._annotation_model.save_annotations(target_annotation_path)
                
                # Reload current image's annotations to restore state
                self._annotation_controller.load_image_annotations(current_image_path)
                
                self._main_window.show_message(f"Redid copy to {len(copied_images)} image(s)")
                return True
        
        # For other actions, use the model's redo method
        success = self._annotation_model.redo()
        if success:
            # Auto-save after redo
            self._annotation_controller.save_current_annotations()
            self._main_window.show_message("Redo successful")
        else:
            self._main_window.show_message("Nothing to redo")
        
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
    

