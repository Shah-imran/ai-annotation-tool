"""
Main window for the PyQt5 annotation tool.
"""
import os
from PyQt5.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, 
                            QSplitter, QMenuBar, QAction, QFileDialog, 
                            QStatusBar, QMessageBox, QApplication)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt5.QtGui import QKeySequence, QIcon
from .image_canvas import ImageCanvas
from .control_panel import ControlPanel


class MainWindow(QMainWindow):
    """
    Main application window containing the image canvas and control panel.
    """
    
    # Signals for controller communication
    load_images_from_directory = pyqtSignal(str)
    load_images_from_file_list = pyqtSignal(str, str)
    load_class_names = pyqtSignal(str)
    qa_mode_toggled = pyqtSignal(bool)  # Emitted when Q&A mode is toggled
    preferences_requested = pyqtSignal()  # Emitted when preferences are requested
    load_settings_file = pyqtSignal(str)  # Emitted when user wants to load a settings file
    undo_requested = pyqtSignal()  # Emitted when undo is requested
    window_closing = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self._setup_ui()
        self._setup_menu()
        self._setup_status_bar()
        self._setup_shortcuts()
        
        # Auto-save timer
        self._auto_save_timer = QTimer()
        self._auto_save_timer.timeout.connect(self._on_auto_save)
        self._auto_save_timer.start(30000)  # Auto-save every 30 seconds
    
    def _setup_ui(self):
        """Initialize the main UI components."""
        self.setWindowTitle("Annotation Tool (Scan Lab)")
        
        # Get screen size and set window to use a percentage of screen
        screen = QApplication.primaryScreen().geometry()
        screen_width = screen.width()
        screen_height = screen.height()
        
        # Use 90% of screen size, with minimum sizes
        window_width = max(1200, int(screen_width * 0.9))
        window_height = max(700, int(screen_height * 0.85))
        
        # Center window on screen
        x = (screen_width - window_width) // 2
        y = (screen_height - window_height) // 2
        
        self.setGeometry(x, y, window_width, window_height)
        
        # Set application icon (if available)
        self.setWindowIcon(QIcon())
        
        # Create central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Create main layout
        main_layout = QHBoxLayout(central_widget)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)
        
        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Horizontal)
        
        # Create image canvas
        self.image_canvas = ImageCanvas()
        splitter.addWidget(self.image_canvas)
        
        # Connect canvas click to clear control panel focus
        self.image_canvas.canvas_clicked.connect(self._on_canvas_clicked)
        
        # Create control panel
        self.control_panel = ControlPanel()
        splitter.addWidget(self.control_panel)
        
        # Set splitter proportions based on window size (70% canvas, 30% panel)
        canvas_size = int(window_width * 0.7)
        panel_size = int(window_width * 0.3)
        splitter.setSizes([canvas_size, panel_size])
        splitter.setStretchFactor(0, 2)  # Canvas can stretch more
        splitter.setStretchFactor(1, 1)  # Control panel can also stretch
        
        main_layout.addWidget(splitter)
        
        # Apply dark theme
        self._apply_dark_theme()
    
    def _setup_menu(self):
        """Setup the menu bar."""
        menubar = self.menuBar()
        
        # File menu
        file_menu = menubar.addMenu('&File')
        
        # Load images from directory
        load_dir_action = QAction('Load Images from &Directory...', self)
        load_dir_action.setShortcut(QKeySequence.Open)
        load_dir_action.triggered.connect(self._load_images_directory)
        file_menu.addAction(load_dir_action)
        
        # Load images from file list
        load_list_action = QAction('Load Images from &List...', self)
        load_list_action.triggered.connect(self._load_images_file_list)
        file_menu.addAction(load_list_action)
        
        file_menu.addSeparator()
        
        # Load class names
        load_classes_action = QAction('Load &Classes...', self)
        load_classes_action.triggered.connect(self._load_class_names)
        file_menu.addAction(load_classes_action)
        
        file_menu.addSeparator()
        
        # Load Settings File
        load_settings_action = QAction('Load &Settings File...', self)
        load_settings_action.triggered.connect(self._load_settings_file)
        file_menu.addAction(load_settings_action)
        
        file_menu.addSeparator()
        
        # Save
        save_action = QAction('&Save', self)
        save_action.setShortcut(QKeySequence.Save)
        save_action.triggered.connect(self.control_panel.save_requested.emit)
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()
        
        # Exit
        exit_action = QAction('E&xit', self)
        exit_action.setShortcut(QKeySequence.Quit)
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # Edit menu
        edit_menu = menubar.addMenu('&Edit')
        
        # Delete annotation
        delete_action = QAction('&Delete Annotation', self)
        delete_action.setShortcut('R')
        delete_action.triggered.connect(self.control_panel.delete_annotation_requested.emit)
        edit_menu.addAction(delete_action)
        
        # Clear all
        clear_action = QAction('&Clear All', self)
        clear_action.setShortcut('C')
        clear_action.triggered.connect(self.control_panel.clear_all_requested.emit)
        edit_menu.addAction(clear_action)
        
        edit_menu.addSeparator()
        
        # Copy boxes to next image
        copy_boxes_action = QAction('Copy &Boxes to Next Image', self)
        copy_boxes_action.setShortcut(QKeySequence.Copy)  # Ctrl+C
        copy_boxes_action.triggered.connect(self.control_panel.copy_boxes_to_next_requested.emit)
        edit_menu.addAction(copy_boxes_action)
        
        # Undo
        undo_action = QAction('&Undo', self)
        undo_action.setShortcut(QKeySequence.Undo)  # Ctrl+Z
        undo_action.triggered.connect(self.undo_requested.emit)
        edit_menu.addAction(undo_action)
        
        # Navigation menu
        nav_menu = menubar.addMenu('&Navigation')
        
        # Previous image
        prev_action = QAction('&Previous Image', self)
        prev_action.setShortcut('A')
        prev_action.triggered.connect(self.control_panel.previous_image_requested.emit)
        nav_menu.addAction(prev_action)
        
        # Next image
        next_action = QAction('&Next Image', self)
        next_action.setShortcut('D')
        next_action.triggered.connect(self.control_panel.next_image_requested.emit)
        nav_menu.addAction(next_action)
        
        # Tools menu
        tools_menu = menubar.addMenu('&Tools')
        
        # Q&A toggle
        self.qa_toggle_action = QAction('Enable &Q&A Annotations', self)
        self.qa_toggle_action.setCheckable(True)
        self.qa_toggle_action.setChecked(False)
        self.qa_toggle_action.triggered.connect(self._toggle_qa_mode)
        tools_menu.addAction(self.qa_toggle_action)
        
        tools_menu.addSeparator()
        
        # Preferences
        preferences_action = QAction('&Preferences...', self)
        preferences_action.triggered.connect(self._show_preferences)
        tools_menu.addAction(preferences_action)
        
        # Help menu
        help_menu = menubar.addMenu('&Help')
        
        # About
        about_action = QAction('&About', self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)
    
    def _setup_status_bar(self):
        """Setup the status bar."""
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")
    
    def _setup_shortcuts(self):
        """Setup keyboard shortcuts."""
        # Number keys for class selection
        for i in range(10):
            shortcut = QAction(self)
            shortcut.setShortcut(str(i))
            shortcut.triggered.connect(lambda checked, class_id=i: self._handle_class_shortcut(class_id))
            self.addAction(shortcut)
        
        # Magnification shortcuts
        # Toggle magnification with 'I' key
        mag_toggle = QAction(self)
        mag_toggle.setShortcut('I')
        mag_toggle.triggered.connect(self._toggle_magnification)
        self.addAction(mag_toggle)
        
        # Cycle magnification method with 'M' key
        mag_method = QAction(self)
        mag_method.setShortcut('M')
        mag_method.triggered.connect(self._cycle_magnification_method)
        self.addAction(mag_method)
    
    def _apply_dark_theme(self):
        """Apply dark theme to the application."""
        dark_stylesheet = """
        QMainWindow {
            background-color: #2b2b2b;
            color: #ffffff;
        }
        QMenuBar {
            background-color: #3c3c3c;
            color: #ffffff;
            border: 1px solid #555555;
        }
        QMenuBar::item {
            background-color: transparent;
            padding: 4px 8px;
        }
        QMenuBar::item:selected {
            background-color: #4CAF50;
        }
        QMenu {
            background-color: #3c3c3c;
            color: #ffffff;
            border: 1px solid #555555;
        }
        QMenu::item:selected {
            background-color: #4CAF50;
        }
        QStatusBar {
            background-color: #3c3c3c;
            color: #ffffff;
            border-top: 1px solid #555555;
        }
        QSplitter::handle {
            background-color: #555555;
        }
        QSplitter::handle:horizontal {
            width: 3px;
        }
        QSplitter::handle:vertical {
            height: 3px;
        }
        """
        self.setStyleSheet(dark_stylesheet)
    
    def _load_images_directory(self):
        """Load images from a directory."""
        directory = QFileDialog.getExistingDirectory(
            self, 
            "Select Image Directory",
            "",
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
        )
        
        if directory:
            self.load_images_from_directory.emit(directory)
    
    def _load_images_file_list(self):
        """Load images from a file list."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Image List File",
            "",
            "Text Files (*.txt);;All Files (*)"
        )
        
        if file_path:
            # Ask for base directory
            base_dir = QFileDialog.getExistingDirectory(
                self,
                "Select Base Directory for Relative Paths (optional)",
                os.path.dirname(file_path),
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
            )
            
            self.load_images_from_file_list.emit(file_path, base_dir)
    
    def _load_class_names(self):
        """Load class names from file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Class Names File",
            "",
            "Text Files (*.txt);;Names Files (*.names);;All Files (*)"
        )
        
        if file_path:
            self.load_class_names.emit(file_path)
    
    def _load_settings_file(self):
        """Load settings from a custom file."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Select Settings File",
            "",
            "JSON Files (*.json);;All Files (*)"
        )
        
        if file_path:
            self.load_settings_file.emit(file_path)
    
    def _show_about(self):
        """Show about dialog."""
        QMessageBox.about(
            self,
            "About Annotation Tool (Scan Lab)",
            """
            <h3>Annotation Tool (Scan Lab)</h3>
            <p>A modern image annotation tool built with MVC architecture for Scan Lab.</p>
            <p><b>Features:</b></p>
            <ul>
                <li>Rectangular bounding box annotations</li>
                <li>Text descriptions for annotations</li>
                <li>Q&A annotations for detailed analysis</li>
                <li>YOLO format support</li>
                <li>Keyboard shortcuts</li>
                <li>Auto-save functionality</li>
            </ul>
            <p><b>Version:</b> 1.0.0</p>
            """
        )
    
    def _on_auto_save(self):
        """Handle auto-save timer."""
        # This will be connected to the controller's save method
        pass
    
    def show_message(self, message: str, timeout: int = 3000):
        """Show a message in the status bar."""
        self.status_bar.showMessage(message, timeout)
    
    def _toggle_qa_mode(self, checked: bool):
        """Handle Q&A mode toggle."""
        self.qa_mode_toggled.emit(checked)
    
    def _show_preferences(self):
        """Show preferences dialog."""
        self.preferences_requested.emit()
    
    def set_qa_mode_enabled(self, enabled: bool):
        """Update Q&A toggle state."""
        self.qa_toggle_action.setChecked(enabled)
    
    def show_error(self, title: str, message: str):
        """Show an error dialog."""
        QMessageBox.critical(self, title, message)
    
    def show_warning(self, title: str, message: str):
        """Show a warning dialog."""
        QMessageBox.warning(self, title, message)
    
    def show_info(self, title: str, message: str):
        """Show an info dialog."""
        QMessageBox.information(self, title, message)
    
    def confirm_action(self, title: str, message: str) -> bool:
        """Show a confirmation dialog."""
        reply = QMessageBox.question(
            self, title, message,
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No
        )
        return reply == QMessageBox.Yes
    
    def closeEvent(self, event):
        """Handle window close event."""
        # This signal can be connected to controller for cleanup
        self.window_closing.emit()
        event.accept()
    
    def _toggle_magnification(self):
        """Toggle magnification on/off."""
        enabled = self.image_canvas.toggle_magnification()
        status = "enabled" if enabled else "disabled"
        self.show_message(f"Magnification {status}")
    
    def _cycle_magnification_method(self):
        """Cycle through magnification methods."""
        method = self.image_canvas.cycle_magnification_method()
        self.show_message(f"Magnification method: {method}")
    
    def _on_canvas_clicked(self):
        """Handle canvas click to clear focus from control panel."""
        self.control_panel.clear_text_focus()
    
    def _handle_class_shortcut(self, class_id: int):
        """Handle class selection shortcut, but ignore if text box has focus."""
        if not self.control_panel.has_text_focus():
            self.control_panel.class_changed.emit(class_id)
    
    def keyPressEvent(self, event):
        """Handle key press events, but respect text box focus."""
        # If text box has focus, let it handle most keys
        if self.control_panel.has_text_focus():
            # Only allow certain global shortcuts when text has focus
            key = event.key()
            modifiers = event.modifiers()
            
            # Allow Ctrl+S for save even when text has focus
            if key == Qt.Key_S and modifiers == Qt.ControlModifier:
                self.control_panel.save_requested.emit()
                return
            
            # Allow Escape to clear focus
            if key == Qt.Key_Escape:
                self.control_panel.clear_text_focus()
                return
            
            # For all other keys, let the text box handle them
            super().keyPressEvent(event)
            return
        
        # Text box doesn't have focus, handle shortcuts normally
        key = event.key()
        
        # Handle navigation shortcuts
        if key == Qt.Key_A:
            self.control_panel.previous_image_requested.emit()
        elif key == Qt.Key_D:
            self.control_panel.next_image_requested.emit()
        elif key == Qt.Key_R:
            self.control_panel.delete_annotation_requested.emit()
        elif key == Qt.Key_C:
            self.control_panel.clear_all_requested.emit()
        elif key == Qt.Key_I:
            self._toggle_magnification()
        elif key == Qt.Key_M:
            self._cycle_magnification_method()
        else:
            # Let parent handle other keys
            super().keyPressEvent(event)

