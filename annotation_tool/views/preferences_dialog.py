"""
Preferences Dialog for configuring all application settings.
"""

import os
import json
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel, 
                            QPushButton, QLineEdit, QFileDialog, QGroupBox, 
                            QGridLayout, QMessageBox, QDialogButtonBox, QCheckBox,
                            QSpinBox, QDoubleSpinBox, QTabWidget, QWidget, QComboBox,
                            QScrollArea, QColorDialog)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont, QColor


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
    copy_boxes_count_changed = pyqtSignal(int)
    settings_file_path_changed = pyqtSignal(str)  # Emitted when settings file path is changed
    volume_scan_dir_changed = pyqtSignal(str)
    annotations_output_dir_changed = pyqtSignal(str)
    voxel_spacing_changed = pyqtSignal(float, float, float)
    default_annotation_mode_changed = pyqtSignal(str)  # "2d" or "3d"
    volume_brush_radius_changed = pyqtSignal(int)
    volume_preview_defaults_changed = pyqtSignal(dict)
    
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
        self._copy_boxes_count = 1
        self._settings_file_path = ""
        self._volume_scan_dir = ""
        self._annotations_output_dir = ""
        self._voxel_spacing = (1.0, 1.0, 1.0)
        self._default_annotation_mode = "2d"
        self._volume_brush_radius = 8
        self._preview_iso_color = "#dcdcdc"
        self._snapshot_export_dir = ""
        self._mesh_export_dir = ""
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

        # 3D Volume tab
        volume_tab = self._create_volume_tab()
        tabs.addTab(volume_tab, "3D Volume")
        
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
    
    def _create_volume_tab(self):
        """Create the 3D volume annotation settings tab."""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setSpacing(15)
        layout.setContentsMargins(10, 10, 10, 10)

        scan_group = QGroupBox("Volume Scan Folder")
        scan_layout = QGridLayout()
        scan_desc = QLabel("Default folder for slice stacks (slice_NNNN.tif):")
        scan_desc.setWordWrap(True)
        scan_layout.addWidget(scan_desc, 0, 0, 1, 3)
        self.volume_scan_dir_edit = QLineEdit()
        self.volume_scan_dir_edit.setReadOnly(True)
        self.volume_scan_dir_edit.setPlaceholderText("No scan folder selected...")
        scan_layout.addWidget(self.volume_scan_dir_edit, 1, 0, 1, 2)
        scan_browse = QPushButton("Browse...")
        scan_browse.clicked.connect(self._browse_volume_scan_dir)
        scan_layout.addWidget(scan_browse, 1, 2)
        scan_group.setLayout(scan_layout)
        layout.addWidget(scan_group)

        ann_group = QGroupBox("Annotations Output Folder")
        ann_layout = QGridLayout()
        ann_desc = QLabel("Folder for label memmaps and NIfTI exports (_seg.nii.gz):")
        ann_desc.setWordWrap(True)
        ann_layout.addWidget(ann_desc, 0, 0, 1, 3)
        self.annotations_output_dir_edit = QLineEdit()
        self.annotations_output_dir_edit.setReadOnly(True)
        self.annotations_output_dir_edit.setPlaceholderText("No output folder selected...")
        ann_layout.addWidget(self.annotations_output_dir_edit, 1, 0, 1, 2)
        ann_browse = QPushButton("Browse...")
        ann_browse.clicked.connect(self._browse_annotations_output_dir)
        ann_layout.addWidget(ann_browse, 1, 2)
        ann_group.setLayout(ann_layout)
        layout.addWidget(ann_group)

        spacing_group = QGroupBox("Voxel Spacing (NIfTI export)")
        spacing_layout = QGridLayout()
        spacing_layout.addWidget(QLabel("X:"), 0, 0)
        self.voxel_spacing_x = QDoubleSpinBox()
        self.voxel_spacing_x.setRange(0.0001, 10000.0)
        self.voxel_spacing_x.setDecimals(4)
        self.voxel_spacing_x.setValue(1.0)
        spacing_layout.addWidget(self.voxel_spacing_x, 0, 1)
        spacing_layout.addWidget(QLabel("Y:"), 0, 2)
        self.voxel_spacing_y = QDoubleSpinBox()
        self.voxel_spacing_y.setRange(0.0001, 10000.0)
        self.voxel_spacing_y.setDecimals(4)
        self.voxel_spacing_y.setValue(1.0)
        spacing_layout.addWidget(self.voxel_spacing_y, 0, 3)
        spacing_layout.addWidget(QLabel("Z:"), 1, 0)
        self.voxel_spacing_z = QDoubleSpinBox()
        self.voxel_spacing_z.setRange(0.0001, 10000.0)
        self.voxel_spacing_z.setDecimals(4)
        self.voxel_spacing_z.setValue(1.0)
        spacing_layout.addWidget(self.voxel_spacing_z, 1, 1)
        spacing_info = QLabel("Physical size per voxel in exported NIfTI files (mm or µm).")
        spacing_info.setWordWrap(True)
        spacing_info.setStyleSheet("font-size: 10px; color: #666666;")
        spacing_layout.addWidget(spacing_info, 2, 0, 1, 4)
        spacing_group.setLayout(spacing_layout)
        layout.addWidget(spacing_group)

        export_group = QGroupBox("3D Preview Export Folders")
        export_layout = QGridLayout()
        export_layout.addWidget(QLabel("Default folder for snapshots (PNG):"), 0, 0, 1, 3)
        self.snapshot_export_dir_edit = QLineEdit()
        self.snapshot_export_dir_edit.setReadOnly(True)
        self.snapshot_export_dir_edit.setPlaceholderText("Home folder (default)")
        export_layout.addWidget(self.snapshot_export_dir_edit, 1, 0, 1, 2)
        snap_browse = QPushButton("Browse...")
        snap_browse.clicked.connect(self._browse_snapshot_export_dir)
        export_layout.addWidget(snap_browse, 1, 2)
        export_layout.addWidget(QLabel("Default folder for 3D model export:"), 2, 0, 1, 3)
        self.mesh_export_dir_edit = QLineEdit()
        self.mesh_export_dir_edit.setReadOnly(True)
        self.mesh_export_dir_edit.setPlaceholderText("Home folder (default)")
        export_layout.addWidget(self.mesh_export_dir_edit, 3, 0, 1, 2)
        mesh_browse = QPushButton("Browse...")
        mesh_browse.clicked.connect(self._browse_mesh_export_dir)
        export_layout.addWidget(mesh_browse, 3, 2)
        export_group.setLayout(export_layout)
        layout.addWidget(export_group)

        preview_group = QGroupBox("3D Preview Defaults")
        preview_layout = QGridLayout()
        row = 0
        preview_layout.addWidget(QLabel("Render mode:"), row, 0)
        self.pref_preview_mode_combo = QComboBox()
        self.pref_preview_mode_combo.addItem("Isosurface (opaque, lit)", "isosurface_lit")
        self.pref_preview_mode_combo.addItem("Point cloud", "point_cloud")
        preview_layout.addWidget(self.pref_preview_mode_combo, row, 1)
        row += 1
        preview_layout.addWidget(QLabel("Detail level (1–5):"), row, 0)
        self.pref_preview_level_spin = QSpinBox()
        self.pref_preview_level_spin.setRange(1, 5)
        self.pref_preview_level_spin.setValue(5)
        self.pref_preview_level_spin.setToolTip(
            "Coarse (1) to fine (5). Sets default Z and XY stride sliders."
        )
        preview_layout.addWidget(self.pref_preview_level_spin, row, 1)
        row += 1
        preview_layout.addWidget(QLabel("Z stride:"), row, 0)
        self.pref_preview_stride_z = QSpinBox()
        self.pref_preview_stride_z.setRange(1, 32)
        self.pref_preview_stride_z.setValue(1)
        preview_layout.addWidget(self.pref_preview_stride_z, row, 1)
        row += 1
        preview_layout.addWidget(QLabel("XY stride:"), row, 0)
        self.pref_preview_stride_xy = QSpinBox()
        self.pref_preview_stride_xy.setRange(1, 32)
        self.pref_preview_stride_xy.setValue(1)
        preview_layout.addWidget(self.pref_preview_stride_xy, row, 1)
        row += 1
        self.pref_preview_native_check = QCheckBox("Native resolution (full grid, high RAM)")
        preview_layout.addWidget(self.pref_preview_native_check, row, 0, 1, 2)
        row += 1
        self.pref_preview_limit_range_check = QCheckBox("Limit preview to slice range")
        preview_layout.addWidget(self.pref_preview_limit_range_check, row, 0, 1, 2)
        row += 1
        preview_layout.addWidget(QLabel("From slice:"), row, 0)
        self.pref_preview_z_start = QSpinBox()
        self.pref_preview_z_start.setRange(1, 99999)
        self.pref_preview_z_start.setValue(1)
        preview_layout.addWidget(self.pref_preview_z_start, row, 1)
        row += 1
        preview_layout.addWidget(QLabel("To slice:"), row, 0)
        self.pref_preview_z_end = QSpinBox()
        self.pref_preview_z_end.setRange(1, 99999)
        self.pref_preview_z_end.setValue(1)
        preview_layout.addWidget(self.pref_preview_z_end, row, 1)
        row += 1
        self.pref_preview_show_mask_check = QCheckBox("Show label overlay in 3D")
        preview_layout.addWidget(self.pref_preview_show_mask_check, row, 0, 1, 2)
        row += 1
        preview_layout.addWidget(QLabel("Isosurface color:"), row, 0)
        iso_row = QHBoxLayout()
        self.pref_preview_iso_color_btn = QPushButton()
        self.pref_preview_iso_color_btn.setFixedSize(40, 22)
        self.pref_preview_iso_color_btn.clicked.connect(self._pick_pref_preview_iso_color)
        iso_row.addWidget(self.pref_preview_iso_color_btn)
        iso_row.addStretch(1)
        iso_wrap = QWidget()
        iso_wrap.setLayout(iso_row)
        preview_layout.addWidget(iso_wrap, row, 1)
        row += 1
        preview_layout.addWidget(QLabel("Point size:"), row, 0)
        self.pref_preview_point_size = QDoubleSpinBox()
        self.pref_preview_point_size.setRange(1.0, 20.0)
        self.pref_preview_point_size.setSingleStep(0.5)
        self.pref_preview_point_size.setValue(3.0)
        preview_layout.addWidget(self.pref_preview_point_size, row, 1)
        row += 1
        self.pref_preview_point_threshold_auto = QCheckBox("Auto point-cloud threshold")
        preview_layout.addWidget(self.pref_preview_point_threshold_auto, row, 0, 1, 2)
        row += 1
        preview_layout.addWidget(QLabel("Point threshold (0–255):"), row, 0)
        self.pref_preview_point_threshold = QSpinBox()
        self.pref_preview_point_threshold.setRange(0, 255)
        self.pref_preview_point_threshold.setValue(25)
        preview_layout.addWidget(self.pref_preview_point_threshold, row, 1)
        row += 1
        preview_layout.addWidget(QLabel("3D window brightness:"), row, 0)
        self.pref_preview_brightness = QSpinBox()
        self.pref_preview_brightness.setRange(10, 250)
        self.pref_preview_brightness.setValue(100)
        self.pref_preview_brightness.setSuffix(" %")
        self.pref_preview_brightness.setToolTip(
            "Default brightness for the separate 3D preview window (10–250%)."
        )
        preview_layout.addWidget(self.pref_preview_brightness, row, 1)
        preview_group.setLayout(preview_layout)
        layout.addWidget(preview_group)
        self._refresh_pref_preview_iso_color_btn()

        ui_group = QGroupBox("3D UI Defaults")
        ui_layout = QGridLayout()
        ui_layout.addWidget(QLabel("Default tab on startup:"), 0, 0)
        self.default_mode_combo = QComboBox()
        self.default_mode_combo.addItem("2D Bounding Box", "2d")
        self.default_mode_combo.addItem("3D Volume", "3d")
        ui_layout.addWidget(self.default_mode_combo, 0, 1)
        ui_layout.addWidget(QLabel("Default brush radius:"), 1, 0)
        self.volume_brush_spinbox = QSpinBox()
        self.volume_brush_spinbox.setRange(1, 128)
        self.volume_brush_spinbox.setValue(8)
        ui_layout.addWidget(self.volume_brush_spinbox, 1, 1)
        ui_group.setLayout(ui_layout)
        layout.addWidget(ui_group)

        layout.addStretch()
        scroll.setWidget(widget)
        return scroll

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
        
        # Copy boxes count
        copy_boxes_group = QGroupBox("Copy Boxes Settings")
        copy_boxes_layout = QGridLayout()
        
        copy_boxes_label = QLabel("Number of images to copy boxes to:")
        copy_boxes_layout.addWidget(copy_boxes_label, 0, 0)
        
        self.copy_boxes_spinbox = QSpinBox()
        self.copy_boxes_spinbox.setMinimum(1)
        # Allow large values; the actual copy logic will clamp to the
        # number of available images, so this just controls intent.
        self.copy_boxes_spinbox.setMaximum(2147483647)
        self.copy_boxes_spinbox.setValue(self._copy_boxes_count)
        copy_boxes_layout.addWidget(self.copy_boxes_spinbox, 0, 1)
        
        copy_boxes_info = QLabel("When using Ctrl+C to copy boxes, this many subsequent images will receive the copied annotations.")
        copy_boxes_info.setWordWrap(True)
        copy_boxes_info.setStyleSheet("font-size: 10px; color: #666666; margin-top: 5px;")
        copy_boxes_layout.addWidget(copy_boxes_info, 1, 0, 1, 2)
        
        copy_boxes_group.setLayout(copy_boxes_layout)
        layout.addWidget(copy_boxes_group)
        
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
            "All Files (*)"
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
    
    def _browse_volume_scan_dir(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Volume Scan Folder",
            self._volume_scan_dir or os.getcwd(),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if directory:
            self._volume_scan_dir = directory
            self.volume_scan_dir_edit.setText(directory)

    def _browse_annotations_output_dir(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            "Select Annotations Output Folder",
            self._annotations_output_dir or os.getcwd(),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if directory:
            self._annotations_output_dir = directory
            self.annotations_output_dir_edit.setText(directory)

    def _browse_snapshot_export_dir(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            "Default Snapshot Export Folder",
            self._snapshot_export_dir or os.path.expanduser("~"),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if directory:
            self._snapshot_export_dir = directory
            self.snapshot_export_dir_edit.setText(directory)

    def _browse_mesh_export_dir(self):
        directory = QFileDialog.getExistingDirectory(
            self,
            "Default 3D Model Export Folder",
            self._mesh_export_dir or os.path.expanduser("~"),
            QFileDialog.ShowDirsOnly | QFileDialog.DontResolveSymlinks,
        )
        if directory:
            self._mesh_export_dir = directory
            self.mesh_export_dir_edit.setText(directory)

    def _pick_pref_preview_iso_color(self):
        initial = QColor(self._preview_iso_color or "#dcdcdc")
        color = QColorDialog.getColor(initial, self, "Pick isosurface color")
        if not color.isValid():
            return
        self._preview_iso_color = color.name()
        self._refresh_pref_preview_iso_color_btn()

    def _refresh_pref_preview_iso_color_btn(self):
        hex_color = self._preview_iso_color or "#dcdcdc"
        self.pref_preview_iso_color_btn.setStyleSheet(
            f"QPushButton {{ background-color: {hex_color}; border: 1px solid #666;"
            f"  border-radius: 3px; }}"
        )

    def collect_volume_preview_defaults(self) -> dict:
        return {
            "mode": self.pref_preview_mode_combo.currentData(),
            "level": self.pref_preview_level_spin.value(),
            "stride_z": self.pref_preview_stride_z.value(),
            "stride_xy": self.pref_preview_stride_xy.value(),
            "native_resolution": self.pref_preview_native_check.isChecked(),
            "limit_z_range": self.pref_preview_limit_range_check.isChecked(),
            "z_start": self.pref_preview_z_start.value() - 1,
            "z_end": self.pref_preview_z_end.value() - 1,
            "show_mask": self.pref_preview_show_mask_check.isChecked(),
            "iso_color": self._preview_iso_color,
            "point_size": self.pref_preview_point_size.value(),
            "point_threshold_auto": self.pref_preview_point_threshold_auto.isChecked(),
            "point_threshold": self.pref_preview_point_threshold.value(),
            "brightness_percent": self.pref_preview_brightness.value(),
            "snapshot_dir": self._snapshot_export_dir,
            "mesh_dir": self._mesh_export_dir,
        }

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
        
        copy_boxes_count = self.copy_boxes_spinbox.value()
        if copy_boxes_count != self._copy_boxes_count:
            self.copy_boxes_count_changed.emit(copy_boxes_count)
        
        # Settings file path
        if self._settings_file_path:
            self.settings_file_path_changed.emit(self._settings_file_path)

        # 3D volume settings
        if self._volume_scan_dir:
            self.volume_scan_dir_changed.emit(self._volume_scan_dir)

        if self._annotations_output_dir:
            self.annotations_output_dir_changed.emit(self._annotations_output_dir)

        sx = self.voxel_spacing_x.value()
        sy = self.voxel_spacing_y.value()
        sz = self.voxel_spacing_z.value()
        if (sx, sy, sz) != self._voxel_spacing:
            self.voxel_spacing_changed.emit(sx, sy, sz)

        mode = self.default_mode_combo.currentData()
        if mode and mode != self._default_annotation_mode:
            self.default_annotation_mode_changed.emit(mode)

        brush = self.volume_brush_spinbox.value()
        if brush != self._volume_brush_radius:
            self.volume_brush_radius_changed.emit(brush)

        self.volume_preview_defaults_changed.emit(self.collect_volume_preview_defaults())
        
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
    
    def set_copy_boxes_count(self, count: int):
        """Set the number of images to copy boxes to."""
        self._copy_boxes_count = count
        self.copy_boxes_spinbox.setValue(count)
    
    def set_settings_file_path(self, file_path: str):
        """Set the current settings file path."""
        self._settings_file_path = file_path
        self.settings_file_edit.setText(file_path)

    def set_volume_scan_dir(self, directory: str):
        self._volume_scan_dir = directory or ""
        self.volume_scan_dir_edit.setText(directory or "")

    def set_annotations_output_dir(self, directory: str):
        self._annotations_output_dir = directory or ""
        self.annotations_output_dir_edit.setText(directory or "")

    def set_voxel_spacing(self, sx: float, sy: float, sz: float):
        self._voxel_spacing = (sx, sy, sz)
        self.voxel_spacing_x.setValue(sx)
        self.voxel_spacing_y.setValue(sy)
        self.voxel_spacing_z.setValue(sz)

    def set_default_annotation_mode(self, mode: str):
        self._default_annotation_mode = mode if mode in ("2d", "3d") else "2d"
        idx = self.default_mode_combo.findData(self._default_annotation_mode)
        if idx >= 0:
            self.default_mode_combo.setCurrentIndex(idx)

    def set_volume_brush_radius(self, radius: int):
        self._volume_brush_radius = max(1, min(128, int(radius)))
        self.volume_brush_spinbox.setValue(self._volume_brush_radius)

    def set_volume_preview_defaults(self, prefs: dict) -> None:
        mode = prefs.get("mode", "isosurface_lit")
        idx = self.pref_preview_mode_combo.findData(mode)
        if idx >= 0:
            self.pref_preview_mode_combo.setCurrentIndex(idx)
        self.pref_preview_level_spin.setValue(int(prefs.get("level", 5)))
        self.pref_preview_stride_z.setValue(int(prefs.get("stride_z", 1)))
        self.pref_preview_stride_xy.setValue(int(prefs.get("stride_xy", 1)))
        self.pref_preview_native_check.setChecked(bool(prefs.get("native_resolution", False)))
        self.pref_preview_limit_range_check.setChecked(bool(prefs.get("limit_z_range", False)))
        z0 = max(0, int(prefs.get("z_start", 0)))
        z1 = max(0, int(prefs.get("z_end", 0)))
        self.pref_preview_z_start.setValue(z0 + 1)
        self.pref_preview_z_end.setValue(max(z0 + 1, z1 + 1))
        self.pref_preview_show_mask_check.setChecked(bool(prefs.get("show_mask", True)))
        self._preview_iso_color = str(prefs.get("iso_color", "#dcdcdc"))
        self._refresh_pref_preview_iso_color_btn()
        self.pref_preview_point_size.setValue(float(prefs.get("point_size", 3.0)))
        self.pref_preview_point_threshold_auto.setChecked(
            bool(prefs.get("point_threshold_auto", True))
        )
        self.pref_preview_point_threshold.setValue(int(prefs.get("point_threshold", 25)))
        self.pref_preview_brightness.setValue(int(prefs.get("brightness_percent", 100)))
        self._snapshot_export_dir = str(prefs.get("snapshot_dir", "") or "")
        self.snapshot_export_dir_edit.setText(self._snapshot_export_dir)
        self._mesh_export_dir = str(prefs.get("mesh_dir", "") or "")
        self.mesh_export_dir_edit.setText(self._mesh_export_dir)
