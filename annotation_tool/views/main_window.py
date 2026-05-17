"""
Main window for the PyQt5 annotation tool.
"""
import os
from PyQt5.QtWidgets import (QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, 
                            QSplitter, QMenuBar, QAction, QFileDialog, 
                            QStatusBar, QMessageBox, QApplication, QPushButton, QCheckBox, QLabel,
                            QDialog, QDialogButtonBox, QLineEdit, QGridLayout,
                            QStackedWidget, QTabBar)
from PyQt5.QtCore import Qt, pyqtSignal, QTimer, QSize
from PyQt5.QtGui import QKeySequence, QIcon
from .image_canvas import ImageCanvas
from .control_panel import ControlPanel
from .toggle_switch import ToggleSwitch
from .volume_workspace import VolumeWorkspace


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
    redo_requested = pyqtSignal()  # Emitted when redo is requested
    window_closing = pyqtSignal()
    sidebar_width_changed = pyqtSignal(int)  # Emitted when sidebar width changes
    convert_tiff_to_jpg_requested = pyqtSignal(str, str)  # input_dir, output_dir
    mode_changed = pyqtSignal(str)  # "2d" or "3d"
    load_volume_scan_requested = pyqtSignal(str)
    volume_save_requested = pyqtSignal()
    
    def __init__(self):
        super().__init__()
        self._saved_sidebar_width = 0  # Store saved sidebar width
        self._annotation_mode = "2d"
        self._actions_2d_only = []
        self._actions_3d_only = []
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
        
        # Stacked workspaces: 2D bbox vs 3D volume. A horizontal mode tab
        # bar sits as a second row directly under the menubar; the stacked
        # workspaces sit below it.
        central = QWidget()
        central_layout = QVBoxLayout(central)
        central_layout.setContentsMargins(0, 0, 0, 0)
        central_layout.setSpacing(0)

        self._mode_tab_bar = QTabBar()
        self._mode_tab_bar.setShape(QTabBar.RoundedNorth)
        self._mode_tab_bar.setExpanding(False)
        self._mode_tab_bar.setUsesScrollButtons(False)
        self._mode_tab_bar.setDrawBase(False)
        self._mode_tab_bar.addTab("2D Bounding Box")
        self._mode_tab_bar.addTab("3D Volume")
        self._mode_tab_bar.setTabToolTip(0, "2D bounding-box annotation")
        self._mode_tab_bar.setTabToolTip(1, "3D volume / voxel annotation")
        self._mode_tab_bar.currentChanged.connect(self._on_mode_tab_changed)

        tab_strip = QWidget()
        tab_strip.setObjectName("modeTabStrip")
        tab_strip_layout = QHBoxLayout(tab_strip)
        tab_strip_layout.setContentsMargins(6, 4, 6, 0)
        tab_strip_layout.setSpacing(0)
        tab_strip_layout.addWidget(self._mode_tab_bar)
        tab_strip_layout.addStretch(1)

        self._stack = QStackedWidget()

        central_layout.addWidget(tab_strip)
        central_layout.addWidget(self._stack, 1)
        self.setCentralWidget(central)

        # --- 2D workspace ---
        workspace_2d = QWidget()
        layout_2d = QHBoxLayout(workspace_2d)
        layout_2d.setContentsMargins(5, 5, 5, 5)
        self.splitter = QSplitter(Qt.Horizontal)
        self.image_canvas = ImageCanvas()
        self.splitter.addWidget(self.image_canvas)
        self.image_canvas.canvas_clicked.connect(self._on_canvas_clicked)
        self.control_panel = ControlPanel()
        self.splitter.addWidget(self.control_panel)
        canvas_size = int(window_width * 0.7)
        panel_size = int(window_width * 0.3)
        self.splitter.setSizes([canvas_size, panel_size])
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.splitterMoved.connect(self._on_splitter_moved)
        layout_2d.addWidget(self.splitter)
        self._stack.addWidget(workspace_2d)

        # --- 3D volume workspace ---
        self.volume_workspace = VolumeWorkspace()
        self._stack.addWidget(self.volume_workspace)
        
        # Apply dark theme
        self._apply_dark_theme()
    
    def resizeEvent(self, event):
        """Handle window resize - enforce sidebar max width."""
        super().resizeEvent(event)
        # Check if sidebar exceeds 30% limit after window resize
        sizes = self.splitter.sizes()
        if len(sizes) > 1 and sizes[1] > 0:
            max_panel_width = int(self.width() * 0.3)
            if sizes[1] > max_panel_width:
                # Adjust to respect the limit
                canvas_size = self.width() - max_panel_width - self.splitter.handleWidth()
                self.splitter.setSizes([canvas_size, max_panel_width])
                self._saved_sidebar_width = max_panel_width
                self.sidebar_width_changed.emit(max_panel_width)
    
    def _setup_menu(self):
        """Setup the menu bar."""
        menubar = self.menuBar()

        # Note: the 2D/3D mode tabs live in the left-side vertical tab bar
        # created in _setup_ui — the menubar stays clean.

        # Add toggle switch to top right corner of menu bar
        # Create a widget to hold the toggle
        toggle_widget = QWidget()
        toggle_layout = QHBoxLayout(toggle_widget)
        toggle_layout.setContentsMargins(0, 0, 10, 0)
        toggle_layout.setSpacing(5)
        
        # Label for the toggle
        toggle_label = QLabel("Panel:")
        toggle_label.setStyleSheet("color: #cccccc; font-size: 11px;")
        toggle_layout.addWidget(toggle_label)
        
        # Toggle switch (custom widget)
        self.panel_toggle_switch = ToggleSwitch()
        self.panel_toggle_switch.setChecked(True)  # Panel is visible by default
        self.panel_toggle_switch.setToolTip("Toggle control panel visibility")
        self.panel_toggle_switch.toggled.connect(self._toggle_control_panel)
        toggle_layout.addWidget(self.panel_toggle_switch)
        toggle_layout.addStretch()
        
        # Add the widget to the menu bar
        menubar.setCornerWidget(toggle_widget, Qt.TopRightCorner)
        
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
        
        # Redo
        redo_action = QAction('&Redo', self)
        redo_action.setShortcut(QKeySequence("Ctrl+Shift+Z"))  # Explicitly set to Ctrl+Shift+Z
        redo_action.triggered.connect(self.redo_requested.emit)
        edit_menu.addAction(redo_action)
        
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
        
        # Toggle control panel visibility
        self.toggle_panel_action = QAction('Toggle &Control Panel', self)
        self.toggle_panel_action.setCheckable(True)
        self.toggle_panel_action.setChecked(True)
        self.toggle_panel_action.triggered.connect(lambda checked: self._toggle_control_panel(checked))
        tools_menu.addAction(self.toggle_panel_action)
        
        tools_menu.addSeparator()
        
        # Q&A toggle
        self.qa_toggle_action = QAction('Enable &Q&A Annotations', self)
        self.qa_toggle_action.setCheckable(True)
        self.qa_toggle_action.setChecked(False)
        self.qa_toggle_action.triggered.connect(self._toggle_qa_mode)
        tools_menu.addAction(self.qa_toggle_action)
        
        tools_menu.addSeparator()
        
        # TIFF to JPG conversion
        convert_tiff_action = QAction('Convert &TIFF to JPG...', self)
        convert_tiff_action.triggered.connect(self._show_tiff_to_jpg_dialog)
        tools_menu.addAction(convert_tiff_action)
        
        tools_menu.addSeparator()
        
        # Preferences
        preferences_action = QAction('&Preferences...', self)
        preferences_action.triggered.connect(self._show_preferences)
        tools_menu.addAction(preferences_action)
        
        # Volume menu (3D mode)
        volume_menu = menubar.addMenu('&Volume')
        load_vol_action = QAction('Load &Scan Folder...', self)
        load_vol_action.triggered.connect(self._load_volume_scan)
        volume_menu.addAction(load_vol_action)
        self._actions_3d_only.append(load_vol_action)

        vol_save_action = QAction('&Save Labels', self)
        vol_save_action.setShortcut(QKeySequence.Save)
        vol_save_action.triggered.connect(self.volume_save_requested.emit)
        volume_menu.addAction(vol_save_action)
        self._actions_3d_only.append(vol_save_action)

        vol_prev = QAction('Previous &Slice', self)
        vol_prev.setShortcut('A')
        vol_prev.triggered.connect(self.volume_workspace.control_panel.previous_slice_requested.emit)
        volume_menu.addAction(vol_prev)
        self._actions_3d_only.append(vol_prev)

        vol_next = QAction('Next S&lice', self)
        vol_next.setShortcut('D')
        vol_next.triggered.connect(self.volume_workspace.control_panel.next_slice_requested.emit)
        volume_menu.addAction(vol_next)
        self._actions_3d_only.append(vol_next)

        # The 3D preview pane lives in its own process window (driven from
        # the 3D Preview group in the right-hand panel). The 2D slice pane
        # is always visible — no minimize/show toggles in the Volume menu.

        self._volume_menu = volume_menu

        # Track 2D-only actions for mode switching
        self._actions_2d_only.extend([
            load_dir_action, load_list_action, load_classes_action, save_action,
            delete_action, clear_action, copy_boxes_action,
            prev_action, next_action, self.qa_toggle_action,
        ])

        # Help menu
        help_menu = menubar.addMenu('&Help')
        
        # About
        about_action = QAction('&About', self)
        about_action.triggered.connect(self._show_about)
        help_menu.addAction(about_action)

        self._update_mode_menu_state()
    
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
        QWidget#modeTabStrip {
            background-color: #2b2b2b;
            border-bottom: 1px solid #3a3a3a;
        }
        QTabBar::tab {
            background-color: #333333;
            color: #cccccc;
            padding: 6px 18px;
            margin-right: 2px;
            border: 1px solid #3a3a3a;
            border-bottom: none;
            border-top-left-radius: 4px;
            border-top-right-radius: 4px;
            min-width: 130px;
            font-weight: bold;
        }
        QTabBar::tab:selected {
            background-color: #4CAF50;
            color: #ffffff;
            border-color: #4CAF50;
        }
        QTabBar::tab:hover:!selected {
            background-color: #3a3a3a;
            color: #ffffff;
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
            "All Files (*)"
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
    
    def _show_tiff_to_jpg_dialog(self):
        """Show a popup dialog to select input and output folders for TIFF->JPG conversion."""
        dialog = QDialog(self)
        dialog.setWindowTitle("Convert TIFF to JPG")
        
        layout = QVBoxLayout(dialog)
        
        info_label = QLabel("Select an input folder containing TIFF files and an output folder for JPG files.")
        info_label.setWordWrap(True)
        layout.addWidget(info_label)
        
        grid = QGridLayout()
        
        # Input folder
        input_label = QLabel("Input folder (TIFF):")
        grid.addWidget(input_label, 0, 0)
        
        input_edit = QLineEdit()
        input_edit.setReadOnly(True)
        grid.addWidget(input_edit, 0, 1)
        
        input_browse = QPushButton("Browse...")
        grid.addWidget(input_browse, 0, 2)
        
        # Output folder
        output_label = QLabel("Output folder (JPG):")
        grid.addWidget(output_label, 1, 0)
        
        output_edit = QLineEdit()
        output_edit.setReadOnly(True)
        grid.addWidget(output_edit, 1, 1)
        
        output_browse = QPushButton("Browse...")
        grid.addWidget(output_browse, 1, 2)
        
        layout.addLayout(grid)
        
        # Buttons
        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(buttons)
        
        # Browse handlers
        def _browse_input():
            directory = QFileDialog.getExistingDirectory(
                self,
                "Select Input Folder (TIFF)",
                "",
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
            )
            if directory:
                input_edit.setText(directory)
        
        def _browse_output():
            directory = QFileDialog.getExistingDirectory(
                self,
                "Select Output Folder (JPG)",
                "",
                QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks
            )
            if directory:
                output_edit.setText(directory)
        
        input_browse.clicked.connect(_browse_input)
        output_browse.clicked.connect(_browse_output)
        
        def _on_accept():
            input_dir = input_edit.text().strip()
            output_dir = output_edit.text().strip()
            
            if not input_dir or not output_dir:
                QMessageBox.warning(
                    self,
                    "Missing Folders",
                    "Please select both an input folder and an output folder."
                )
                return
            
            dialog.accept()
            self.convert_tiff_to_jpg_requested.emit(input_dir, output_dir)
        
        buttons.accepted.connect(_on_accept)
        buttons.rejected.connect(dialog.reject)
        
        dialog.exec_()
    
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
    
    def _on_splitter_moved(self, pos: int, index: int):
        """Handle splitter movement - save sidebar width and enforce max width."""
        if index == 1:  # Panel is at index 1
            sizes = self.splitter.sizes()
            if len(sizes) > 1 and sizes[1] > 0:
                # Enforce maximum width (30% of window width)
                max_panel_width = int(self.width() * 0.3)
                if sizes[1] > max_panel_width:
                    # Adjust sizes to respect the limit
                    canvas_size = self.width() - max_panel_width - self.splitter.handleWidth()
                    self.splitter.setSizes([canvas_size, max_panel_width])
                    self._saved_sidebar_width = max_panel_width
                    self.sidebar_width_changed.emit(max_panel_width)
                else:
                    # Only save if panel is actually visible (size > 0)
                    self._saved_sidebar_width = sizes[1]
                    self.sidebar_width_changed.emit(sizes[1])
    
    def set_sidebar_width(self, width: int):
        """Set the sidebar width (called from controller to restore saved width)."""
        if width > 0:
            # Enforce maximum width (30% of window width)
            current_width = self.width() if self.width() > 0 else 1200
            max_panel_width = int(current_width * 0.3)
            width = min(width, max_panel_width)
            
            self._saved_sidebar_width = width
            # Set the splitter sizes - calculate canvas size based on current window width
            canvas_size = current_width - width - self.splitter.handleWidth()
            if canvas_size > 0:
                self.splitter.setSizes([canvas_size, width])
    

    def _active_splitter(self):
        if self.is_volume_mode():
            return self.volume_workspace.splitter
        return self.splitter

    def _active_control_panel(self):
        if self.is_volume_mode():
            return self.volume_workspace.control_panel
        return self.control_panel

    def _toggle_control_panel(self, checked: bool = None):
        """Toggle control panel visibility."""
        splitter = self._active_splitter()
        panel = self._active_control_panel()
        # If called without argument, toggle current state
        # Check actual visibility by checking splitter sizes, not just isVisible()
        if checked is None:
            current_sizes = splitter.sizes()
            # Panel is visible if its size is greater than 0
            panel_visible = len(current_sizes) > 1 and current_sizes[1] > 0
            checked = not panel_visible
        
        # Block signals on all controls to prevent recursion
        switch_blocked = False
        action_blocked = False
        
        if hasattr(self, 'panel_toggle_switch'):
            switch_blocked = self.panel_toggle_switch.signalsBlocked()
            self.panel_toggle_switch.blockSignals(True)
        if hasattr(self, 'toggle_panel_action'):
            action_blocked = self.toggle_panel_action.signalsBlocked()
            self.toggle_panel_action.blockSignals(True)
        
        try:
            panel.setVisible(checked)
            if checked:
                # Restore splitter sizes - use saved width if available, otherwise default
                max_panel_width = int(self.width() * 0.3)  # Maximum 30% of window
                if self._saved_sidebar_width > 0:
                    # Use saved width, but respect maximum
                    panel_size = min(self._saved_sidebar_width, max_panel_width)
                    canvas_size = self.width() - panel_size - splitter.handleWidth()
                else:
                    # Use default proportions (30% max)
                    canvas_size = int(self.width() * 0.7)
                    panel_size = max_panel_width
                splitter.setSizes([canvas_size, panel_size])
            else:
                # Hide panel by setting its size to 0
                splitter.setSizes([self.width(), 0])
            
            # Update menu action state
            if hasattr(self, 'toggle_panel_action'):
                self.toggle_panel_action.setChecked(checked)
            
            # Update toggle switch state
            if hasattr(self, 'panel_toggle_switch'):
                self.panel_toggle_switch.setChecked(checked)
        finally:
            # Always unblock signals (restore previous state)
            if hasattr(self, 'panel_toggle_switch'):
                self.panel_toggle_switch.blockSignals(switch_blocked)
            if hasattr(self, 'toggle_panel_action'):
                self.toggle_panel_action.blockSignals(action_blocked)
    
    def _on_mode_tab_changed(self, index: int):
        mode = "2d" if index == 0 else "3d"
        self.set_annotation_mode(mode)

    def set_annotation_mode(self, mode: str):
        """Switch between 2D bbox and 3D volume annotation."""
        if mode not in ("2d", "3d"):
            return
        self._annotation_mode = mode
        self._stack.setCurrentIndex(0 if mode == "2d" else 1)
        self._mode_tab_bar.blockSignals(True)
        self._mode_tab_bar.setCurrentIndex(0 if mode == "2d" else 1)
        self._mode_tab_bar.blockSignals(False)
        self._update_mode_menu_state()
        suffix = "2D" if mode == "2d" else "3D Volume"
        base = "Annotation Tool (Scan Lab)"
        self.setWindowTitle(f"{base} - {suffix}")
        self.mode_changed.emit(mode)

    def _update_mode_menu_state(self):
        is_2d = self._annotation_mode == "2d"
        for action in self._actions_2d_only:
            action.setEnabled(is_2d)
        for action in self._actions_3d_only:
            action.setEnabled(not is_2d)
        self._volume_menu.menuAction().setVisible(True)

    def _load_volume_scan(self):
        directory = QFileDialog.getExistingDirectory(
            self, "Select Volume Scan Folder",
            getattr(self, "_volume_dialog_start_dir", "") or "",
        )
        if directory:
            self.load_volume_scan_requested.emit(directory)

    def is_volume_mode(self) -> bool:
        return self._annotation_mode == "3d"

    def _handle_class_shortcut(self, class_id: int):
        """Handle class selection shortcut, but ignore if text box has focus."""
        if not self.control_panel.has_text_focus():
            self.control_panel.class_changed.emit(class_id)
    
    def keyPressEvent(self, event):
        """Handle key press events, but respect text box focus."""
        if self.is_volume_mode():
            key = event.key()
            modifiers = event.modifiers()
            if key == Qt.Key_S and modifiers == Qt.ControlModifier:
                self.volume_save_requested.emit()
                return
            if key == Qt.Key_Z and modifiers == Qt.ControlModifier:
                if modifiers & Qt.ShiftModifier:
                    self.redo_requested.emit()
                else:
                    self.undo_requested.emit()
                return
            if key == Qt.Key_A:
                self.volume_workspace.control_panel.previous_slice_requested.emit()
                return
            if key == Qt.Key_D:
                self.volume_workspace.control_panel.next_slice_requested.emit()
                return
            super().keyPressEvent(event)
            return

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

