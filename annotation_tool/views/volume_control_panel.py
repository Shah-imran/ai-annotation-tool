"""
Control panel for 3D volume / voxel annotation mode.
"""
from typing import Tuple

from PyQt5.QtCore import Qt, pyqtSignal, QTimer
from PyQt5.QtGui import QColor
from PyQt5.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from .toggle_switch import ToggleSwitch


class VolumeControlPanel(QWidget):
    load_scan_requested = pyqtSignal()
    save_requested = pyqtSignal()
    export_nifti_requested = pyqtSignal()
    load_seg_requested = pyqtSignal()
    previous_slice_requested = pyqtSignal()
    next_slice_requested = pyqtSignal()
    slice_index_requested = pyqtSignal(int)
    class_changed = pyqtSignal(int)
    brush_radius_changed = pyqtSignal(int)
    erase_mode_changed = pyqtSignal(bool)
    window_center_changed = pyqtSignal(float)
    window_width_changed = pyqtSignal(float)
    reset_window_requested = pyqtSignal()
    preview_rebuild_requested = pyqtSignal()
    preview_stop_requested = pyqtSignal()
    preview_reset_view_requested = pyqtSignal()
    preview_show_window_requested = pyqtSignal()
    preview_hide_window_requested = pyqtSignal()
    preview_mode_changed = pyqtSignal(str)
    preview_show_mask_changed = pyqtSignal(bool)
    preview_settings_changed = pyqtSignal()

    def __init__(self):
        super().__init__()
        self.setMinimumWidth(250)
        # Match the 2D bounding-box panel's button + group-box styling so
        # both annotation modes have a consistent look.
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
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        inner = QWidget()
        inner_layout = QVBoxLayout(inner)

        file_group = QGroupBox("Volume")
        file_layout = QVBoxLayout(file_group)
        self.load_btn = QPushButton("Load Scan Folder...")
        self.load_btn.clicked.connect(self.load_scan_requested.emit)
        file_layout.addWidget(self.load_btn)
        self.scan_label = QLabel("No scan loaded")
        self.scan_label.setWordWrap(True)
        file_layout.addWidget(self.scan_label)
        self.save_btn = QPushButton("Save Labels")
        self.save_btn.clicked.connect(self.save_requested.emit)
        file_layout.addWidget(self.save_btn)
        self.export_btn = QPushButton("Export NIfTI Segmentation...")
        self.export_btn.clicked.connect(self.export_nifti_requested.emit)
        file_layout.addWidget(self.export_btn)
        self.load_seg_btn = QPushButton("Load NIfTI Segmentation...")
        self.load_seg_btn.clicked.connect(self.load_seg_requested.emit)
        file_layout.addWidget(self.load_seg_btn)
        inner_layout.addWidget(file_group)

        preview_group = QGroupBox("3D Preview")
        preview_layout = QVBoxLayout(preview_group)
        self.preview_status = QLabel("Load a scan to build preview")
        self.preview_status.setWordWrap(True)
        self.preview_status.setMinimumHeight(72)
        self.preview_status.setStyleSheet(
            "QLabel { background-color: #2a2a2a; color: #e8e8e8; "
            "padding: 8px; border-radius: 4px; font-size: 11px; }"
        )
        preview_layout.addWidget(self.preview_status)
        mode_row = QHBoxLayout()
        mode_row.addWidget(QLabel("Mode"))
        self.preview_mode_combo = QComboBox()
        self.preview_mode_combo.addItem(
            "Isosurface (opaque, lit)", "isosurface_lit"
        )
        self.preview_mode_combo.addItem("Point cloud", "point_cloud")
        self.preview_mode_combo.currentIndexChanged.connect(self._on_preview_mode_changed)
        mode_row.addWidget(self.preview_mode_combo)
        preview_layout.addLayout(mode_row)
        stride_z_row = QHBoxLayout()
        stride_z_row.addWidget(QLabel("Z stride"))
        self.preview_stride_z_slider = QSlider(Qt.Horizontal)
        self.preview_stride_z_slider.setMinimum(1)
        self.preview_stride_z_slider.setMaximum(16)
        self.preview_stride_z_slider.setValue(1)
        self.preview_stride_z_slider.setToolTip(
            "Along the stack axis: use every Nth slice in the preview range.\n"
            "1 = all slices in range; larger = fewer slabs, less RAM and faster build."
        )
        self.preview_stride_z_slider.valueChanged.connect(self._on_preview_stride_changed)
        stride_z_row.addWidget(self.preview_stride_z_slider)
        self.preview_stride_z_value = QLabel("1")
        self.preview_stride_z_value.setMinimumWidth(22)
        self.preview_stride_z_value.setStyleSheet("color: #aaa;")
        stride_z_row.addWidget(self.preview_stride_z_value)
        preview_layout.addLayout(stride_z_row)

        stride_xy_row = QHBoxLayout()
        stride_xy_row.addWidget(QLabel("XY stride"))
        self.preview_stride_xy_slider = QSlider(Qt.Horizontal)
        self.preview_stride_xy_slider.setMinimum(1)
        self.preview_stride_xy_slider.setMaximum(32)
        self.preview_stride_xy_slider.setValue(1)
        self.preview_stride_xy_slider.setToolTip(
            "In-plane downsampling (max-pool): N×N pixels → 1 preview voxel along X and Y.\n"
            "1 = full resolution; larger = coarser preview and much less RAM."
        )
        self.preview_stride_xy_slider.valueChanged.connect(self._on_preview_stride_changed)
        stride_xy_row.addWidget(self.preview_stride_xy_slider)
        self.preview_stride_xy_value = QLabel("1")
        self.preview_stride_xy_value.setMinimumWidth(22)
        self.preview_stride_xy_value.setStyleSheet("color: #aaa;")
        stride_xy_row.addWidget(self.preview_stride_xy_value)
        preview_layout.addLayout(stride_xy_row)

        self.preview_stride_hint = QLabel("")
        self.preview_stride_hint.setWordWrap(True)
        self.preview_stride_hint.setStyleSheet("color: #888; font-size: 10px;")
        preview_layout.addWidget(self.preview_stride_hint)

        # --- Mode-specific parameter pages -------------------------------
        self._mode_param_stack = QStackedWidget()
        self._mode_param_stack.addWidget(self._build_iso_param_page())   # idx 0
        self._mode_param_stack.addWidget(self._build_point_param_page()) # idx 1
        preview_layout.addWidget(self._mode_param_stack)
        self._sync_preview_mode_visibility()

        self.preview_native_check = QCheckBox("Native resolution (full grid, high RAM)")
        self.preview_native_check.setToolTip(
            "Load every slice in the preview range at full XY resolution (stride 1×1×1).\n"
            "Overrides Z / XY stride sliders for voxel budget.\n\n"
            "Rough size: Z × width × height × 1 byte (e.g. several GiB for large stacks).\n"
            "Isosurface on huge grids may be slow or fail in VTK — prefer stride sliders or a slice range."
        )
        self.preview_native_check.toggled.connect(self._emit_preview_settings_changed)
        preview_layout.addWidget(self.preview_native_check)

        self.preview_limit_range_check = QCheckBox("Limit preview to slice range")
        self.preview_limit_range_check.setToolTip(
            "Build 3D preview only between From/To slices (inclusive)."
        )
        self.preview_limit_range_check.toggled.connect(self._emit_preview_settings_changed)
        preview_layout.addWidget(self.preview_limit_range_check)

        range_row = QHBoxLayout()
        range_row.addWidget(QLabel("From"))
        self.preview_z_start_spin = QSpinBox()
        self.preview_z_start_spin.setRange(1, 1)
        self.preview_z_start_spin.setValue(1)
        self.preview_z_start_spin.setEnabled(False)
        self.preview_z_start_spin.valueChanged.connect(self._emit_preview_settings_changed)
        range_row.addWidget(self.preview_z_start_spin)
        range_row.addWidget(QLabel("To"))
        self.preview_z_end_spin = QSpinBox()
        self.preview_z_end_spin.setRange(1, 1)
        self.preview_z_end_spin.setValue(1)
        self.preview_z_end_spin.setEnabled(False)
        self.preview_z_end_spin.valueChanged.connect(self._emit_preview_settings_changed)
        range_row.addWidget(self.preview_z_end_spin)
        preview_layout.addLayout(range_row)
        self.preview_mask_check = QCheckBox("Show label overlay")
        self.preview_mask_check.setChecked(True)
        self.preview_mask_check.toggled.connect(self.preview_show_mask_changed.emit)
        preview_layout.addWidget(self.preview_mask_check)
        preview_btn_row = QHBoxLayout()
        self.preview_start_btn = QPushButton("Start preview")
        self.preview_start_btn.setToolTip(
            "Build preview data (background) then render 3D. Adjust settings first, then press Start."
        )
        self.preview_start_btn.clicked.connect(self.preview_rebuild_requested.emit)
        self.preview_stop_btn = QPushButton("Stop")
        self.preview_stop_btn.setEnabled(False)
        self.preview_stop_btn.setToolTip(
            "Cancel slice loading in the worker, or abort before the next render step."
        )
        self.preview_stop_btn.clicked.connect(self.preview_stop_requested.emit)
        preview_btn_row.addWidget(self.preview_start_btn)
        preview_btn_row.addWidget(self.preview_stop_btn)
        preview_layout.addLayout(preview_btn_row)

        window_btn_row = QHBoxLayout()
        self.preview_show_window_btn = QPushButton("Show 3D window")
        self.preview_show_window_btn.setToolTip(
            "Open or bring forward the separate 3D preview window."
        )
        self.preview_show_window_btn.clicked.connect(
            self.preview_show_window_requested.emit
        )
        window_btn_row.addWidget(self.preview_show_window_btn)

        self.preview_hide_window_btn = QPushButton("Hide 3D window")
        self.preview_hide_window_btn.setToolTip(
            "Hide the separate 3D preview window without stopping the build."
        )
        self.preview_hide_window_btn.setEnabled(False)
        self.preview_hide_window_btn.clicked.connect(
            self.preview_hide_window_requested.emit
        )
        window_btn_row.addWidget(self.preview_hide_window_btn)
        preview_layout.addLayout(window_btn_row)

        self.preview_reset_view_btn = QPushButton("Reset 3D view")
        self.preview_reset_view_btn.setToolTip(
            "Reset the 3D camera to the default isometric view (or press Home in the 3D window)."
        )
        self.preview_reset_view_btn.clicked.connect(self.preview_reset_view_requested.emit)
        preview_layout.addWidget(self.preview_reset_view_btn)
        inner_layout.addWidget(preview_group)

        nav_group = QGroupBox("Slices")
        nav_layout = QVBoxLayout(nav_group)

        self.slice_counter = QLabel("No slices loaded")
        self.slice_counter.setAlignment(Qt.AlignCenter)
        nav_layout.addWidget(self.slice_counter)

        self.slice_slider = QSlider(Qt.Horizontal)
        self.slice_slider.setMinimum(0)
        self.slice_slider.setMaximum(0)
        self.slice_slider.setValue(0)
        self.slice_slider.setVisible(False)
        self.slice_slider.setTickPosition(QSlider.NoTicks)
        self.slice_slider.valueChanged.connect(self._on_slider_value_changed)
        self.slice_slider.sliderPressed.connect(self._on_slider_pressed)
        self.slice_slider.sliderReleased.connect(self._on_slider_released)
        nav_layout.addWidget(self.slice_slider)

        self._updating_slider = False
        self._is_dragging = False
        self._pending_slice_index = None
        self._slider_debounce_timer = QTimer()
        self._slider_debounce_timer.setSingleShot(True)
        self._slider_debounce_timer.timeout.connect(self._on_slider_debounce_timeout)

        row = QHBoxLayout()
        self.prev_btn = QPushButton("Previous (A)")
        self.prev_btn.clicked.connect(self.previous_slice_requested.emit)
        self.next_btn = QPushButton("Next (D)")
        self.next_btn.clicked.connect(self.next_slice_requested.emit)
        row.addWidget(self.prev_btn)
        row.addWidget(self.next_btn)
        nav_layout.addLayout(row)
        inner_layout.addWidget(nav_group)

        wl_group = QGroupBox("Display Brightness & Contrast")
        wl_layout = QVBoxLayout(wl_group)
        brightness_label = QLabel("Brightness")
        brightness_label.setToolTip("Slide right to brighten, left to darken.")
        wl_layout.addWidget(brightness_label)
        self.wc_slider = QSlider(Qt.Horizontal)
        self.wc_slider.setRange(0, 65535)
        self.wc_slider.valueChanged.connect(lambda v: self.window_center_changed.emit(float(v)))
        wl_layout.addWidget(self.wc_slider)
        contrast_label = QLabel("Contrast")
        contrast_label.setToolTip("Slide left for more contrast, right for less.")
        wl_layout.addWidget(contrast_label)
        self.ww_slider = QSlider(Qt.Horizontal)
        self.ww_slider.setRange(1, 65535)
        self.ww_slider.valueChanged.connect(lambda v: self.window_width_changed.emit(float(v)))
        wl_layout.addWidget(self.ww_slider)
        reset_wl = QPushButton("Reset Display")
        reset_wl.clicked.connect(self.reset_window_requested.emit)
        wl_layout.addWidget(reset_wl)
        inner_layout.addWidget(wl_group)

        brush_group = QGroupBox("Brush")
        brush_layout = QVBoxLayout(brush_group)
        radius_row = QHBoxLayout()
        radius_row.addWidget(QLabel("Radius"))
        self.radius_spin = QSpinBox()
        self.radius_spin.setRange(1, 128)
        self.radius_spin.setValue(8)
        self.radius_spin.valueChanged.connect(self.brush_radius_changed.emit)
        radius_row.addWidget(self.radius_spin)
        brush_layout.addLayout(radius_row)
        erase_row = QHBoxLayout()
        erase_label = QLabel("Eraser")
        erase_label.setToolTip("When ON, brush strokes erase labels instead of painting.")
        erase_row.addWidget(erase_label)
        erase_row.addStretch(1)
        self.erase_switch = ToggleSwitch()
        self.erase_switch.setToolTip("Toggle eraser mode on/off.")
        self.erase_switch.toggled.connect(self.erase_mode_changed.emit)
        erase_row.addWidget(self.erase_switch)
        brush_layout.addLayout(erase_row)
        # Backward-compat alias for any code that still pokes the old attribute.
        self.erase_btn = self.erase_switch
        inner_layout.addWidget(brush_group)

        class_group = QGroupBox("Class")
        class_layout = QVBoxLayout(class_group)
        self.class_combo = QComboBox()
        self.class_combo.currentIndexChanged.connect(self.class_changed.emit)
        class_layout.addWidget(self.class_combo)
        inner_layout.addWidget(class_group)

        help_group = QGroupBox("Shortcuts")
        help_layout = QVBoxLayout(help_group)
        help_layout.addWidget(QLabel(
            "A / D — prev / next slice\n"
            "Ctrl+S — save labels\n"
            "Wheel — brush size · Ctrl+wheel — zoom 2D slice\n"
            "Middle-drag — pan · Home — reset zoom"
        ))
        inner_layout.addWidget(help_group)

        inner_layout.addStretch()
        scroll.setWidget(inner)
        layout.addWidget(scroll)

    def set_scan_info(self, scan_id: str, num_slices: int) -> None:
        self.scan_label.setText(f"Scan: {scan_id}\n{num_slices} slices")

    def update_slice_counter(self, index: int, total: int) -> None:
        if total > 0:
            self.slice_counter.setText(f"Slice {index + 1} of {total}")
            self._slider_debounce_timer.stop()
            self._pending_slice_index = None
            self._updating_slider = True
            self.slice_slider.setMaximum(max(0, total - 1))
            self.slice_slider.setValue(index)
            self.slice_slider.setVisible(True)
            self._updating_slider = False
            self.prev_btn.setEnabled(index > 0)
            self.next_btn.setEnabled(index < total - 1)
        else:
            self.slice_counter.setText("No slices loaded")
            self._slider_debounce_timer.stop()
            self._pending_slice_index = None
            self.slice_slider.setVisible(False)
            self.slice_slider.setMaximum(0)
            self.slice_slider.setValue(0)
            self.prev_btn.setEnabled(False)
            self.next_btn.setEnabled(False)

    def _on_slider_value_changed(self, value: int) -> None:
        if self._updating_slider:
            return

        total = self.slice_slider.maximum() + 1
        if total > 0:
            self.slice_counter.setText(f"Slice {value + 1} of {total}")

        if self._is_dragging:
            self._pending_slice_index = value
            self._slider_debounce_timer.stop()
            self._slider_debounce_timer.start(300)
        else:
            self.slice_index_requested.emit(value)

    def _on_slider_pressed(self) -> None:
        self._is_dragging = True

    def _on_slider_released(self) -> None:
        self._is_dragging = False
        self._slider_debounce_timer.stop()
        if self._pending_slice_index is not None:
            self.slice_index_requested.emit(self._pending_slice_index)
            self._pending_slice_index = None
        else:
            self.slice_index_requested.emit(self.slice_slider.value())

    def _on_slider_debounce_timeout(self) -> None:
        if self._pending_slice_index is not None:
            self.slice_index_requested.emit(self._pending_slice_index)
            self._pending_slice_index = None

    def set_window_sliders(self, center: float, width: float) -> None:
        self.wc_slider.blockSignals(True)
        self.ww_slider.blockSignals(True)
        self.wc_slider.setValue(int(center))
        self.ww_slider.setValue(int(max(1, width)))
        self.wc_slider.blockSignals(False)
        self.ww_slider.blockSignals(False)

    def update_class_list(self, class_names: list) -> None:
        self.class_combo.blockSignals(True)
        self.class_combo.clear()
        for i, name in enumerate(class_names):
            if i == 0 and name.lower() == "background":
                continue
            self.class_combo.addItem(f"{i}: {name}", i)
        self.class_combo.blockSignals(False)

    def set_brush_radius(self, radius: int) -> None:
        self.radius_spin.blockSignals(True)
        self.radius_spin.setValue(radius)
        self.radius_spin.blockSignals(False)

    def _on_preview_stride_changed(self, _value: int) -> None:
        self.preview_stride_z_value.setText(str(self.preview_stride_z_slider.value()))
        self.preview_stride_xy_value.setText(str(self.preview_stride_xy_slider.value()))
        self._update_stride_hint()
        self._emit_preview_settings_changed()

    def _on_preview_mode_changed(self, _index: int) -> None:
        mode = self.preview_mode_combo.currentData()
        if mode:
            self.preview_mode_changed.emit(str(mode))
        self._sync_preview_mode_visibility()

    def get_preview_mode(self) -> str:
        mode = self.preview_mode_combo.currentData()
        return str(mode) if mode else "isosurface_lit"

    def set_preview_mode(self, mode: str) -> None:
        target = "isosurface_lit" if mode == "isosurface_lit" else "point_cloud"
        self.preview_mode_combo.blockSignals(True)
        for i in range(self.preview_mode_combo.count()):
            if self.preview_mode_combo.itemData(i) == target:
                self.preview_mode_combo.setCurrentIndex(i)
                break
        self.preview_mode_combo.blockSignals(False)
        self._sync_preview_mode_visibility()

    def get_preview_level(self) -> int:
        return int(self.preview_level_spin.value())

    def set_preview_level(self, level: int) -> None:
        self.preview_level_spin.blockSignals(True)
        self.preview_level_spin.setValue(max(1, min(5, int(level))))
        self.preview_level_spin.blockSignals(False)
        self._update_level_hint()

    # --- Isosurface params ------------------------------------------------

    def get_preview_iso_color(self) -> str:
        return self._iso_color_hex

    def set_preview_iso_color(self, hex_color: str) -> None:
        color = QColor(hex_color) if hex_color else QColor("#dcdcdc")
        if not color.isValid():
            color = QColor("#dcdcdc")
        self._iso_color_hex = color.name()
        self._refresh_iso_color_button()

    def _refresh_iso_color_button(self) -> None:
        if not hasattr(self, "preview_iso_color_btn"):
            return
        hex_color = self._iso_color_hex or "#dcdcdc"
        text_color = self._readable_text_color(hex_color)
        # Override the panel-wide green button styling for this swatch only.
        self.preview_iso_color_btn.setStyleSheet(
            f"QPushButton {{ background-color: {hex_color}; color: {text_color}; "
            f"  border: 1px solid #555; border-radius: 4px; padding: 4px 8px; }}"
            f"QPushButton:hover {{ border: 1px solid #aaa; }}"
            f"QPushButton:disabled {{ color: #888; border: 1px solid #444; }}"
        )
        self.preview_iso_color_btn.setText(hex_color.upper())

    @staticmethod
    def _readable_text_color(hex_color: str) -> str:
        c = QColor(hex_color)
        if not c.isValid():
            return "#000000"
        # Standard luminance threshold — dark text on light swatches, light on dark.
        luminance = (0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()) / 255.0
        return "#101010" if luminance > 0.55 else "#f0f0f0"

    def _on_iso_color_clicked(self) -> None:
        initial = QColor(self._iso_color_hex or "#dcdcdc")
        color = QColorDialog.getColor(
            initial, self, "Pick isosurface color"
        )
        if not color.isValid():
            return
        hex_color = color.name()
        if hex_color == self._iso_color_hex:
            return
        self._iso_color_hex = hex_color
        self._refresh_iso_color_button()
        self._emit_preview_settings_changed()

    # --- Point cloud params -----------------------------------------------

    def get_preview_point_size(self) -> float:
        return self.preview_point_size_slider.value() / 10.0

    def set_preview_point_size(self, value: float) -> None:
        raw = int(round(max(1.0, min(20.0, float(value))) * 10))
        self.preview_point_size_slider.blockSignals(True)
        self.preview_point_size_slider.setValue(raw)
        self.preview_point_size_slider.blockSignals(False)
        self.preview_point_size_value.setText(f"{raw / 10.0:.1f}")

    def is_preview_point_threshold_auto(self) -> bool:
        return self.preview_point_threshold_auto.isChecked()

    def set_preview_point_threshold_auto(self, enabled: bool) -> None:
        self.preview_point_threshold_auto.blockSignals(True)
        self.preview_point_threshold_auto.setChecked(bool(enabled))
        self.preview_point_threshold_auto.blockSignals(False)
        self._update_point_threshold_enabled()

    def get_preview_point_threshold(self) -> int:
        return int(self.preview_point_threshold_slider.value())

    def set_preview_point_threshold(self, value: int) -> None:
        self.preview_point_threshold_slider.blockSignals(True)
        self.preview_point_threshold_slider.setValue(max(0, min(255, int(value))))
        self.preview_point_threshold_slider.blockSignals(False)
        self.preview_point_threshold_value.setText(
            str(int(self.preview_point_threshold_slider.value()))
        )

    def get_preview_stride_z(self) -> int:
        return int(self.preview_stride_z_slider.value())

    def get_preview_stride_xy(self) -> int:
        return int(self.preview_stride_xy_slider.value())

    def set_preview_stride_z(self, stride: int) -> None:
        self.preview_stride_z_slider.blockSignals(True)
        self.preview_stride_z_slider.setValue(max(1, min(16, int(stride))))
        self.preview_stride_z_slider.blockSignals(False)
        self.preview_stride_z_value.setText(str(self.preview_stride_z_slider.value()))
        self._update_stride_hint()

    def set_preview_stride_xy(self, stride: int) -> None:
        self.preview_stride_xy_slider.blockSignals(True)
        self.preview_stride_xy_slider.setValue(max(1, min(32, int(stride))))
        self.preview_stride_xy_slider.blockSignals(False)
        self.preview_stride_xy_value.setText(str(self.preview_stride_xy_slider.value()))
        self._update_stride_hint()

    # --- Mode-specific parameter page builders ---------------------------

    def _build_iso_param_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(4)

        color_row = QHBoxLayout()
        color_label = QLabel("Surface color")
        color_label.setToolTip("Color of the rendered isosurface mesh.")
        color_row.addWidget(color_label)
        self._iso_color_hex = "#dcdcdc"
        self.preview_iso_color_btn = QPushButton()
        self.preview_iso_color_btn.setToolTip("Click to choose the isosurface color.")
        self.preview_iso_color_btn.setMinimumWidth(60)
        self.preview_iso_color_btn.setMinimumHeight(22)
        self.preview_iso_color_btn.clicked.connect(self._on_iso_color_clicked)
        color_row.addWidget(self.preview_iso_color_btn, 1)
        layout.addLayout(color_row)
        self._refresh_iso_color_button()
        return page

    def _build_point_param_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(0, 4, 0, 4)
        layout.setSpacing(4)

        density_row = QHBoxLayout()
        density_row.addWidget(QLabel("Density"))
        self.preview_level_spin = QSpinBox()
        self.preview_level_spin.setRange(1, 5)
        self.preview_level_spin.setValue(5)
        self.preview_level_spin.setToolTip(
            "Point-cloud density preset (1 = sparse · 5 = dense). Also sets the\n"
            "automatic intensity threshold unless overridden below."
        )
        self.preview_level_spin.valueChanged.connect(self._on_point_level_changed)
        density_row.addWidget(self.preview_level_spin)
        self.preview_level_label = QLabel("5 = dense")
        self.preview_level_label.setStyleSheet("color: #aaa;")
        density_row.addWidget(self.preview_level_label)
        layout.addLayout(density_row)

        size_row = QHBoxLayout()
        size_row.addWidget(QLabel("Point size"))
        self.preview_point_size_slider = QSlider(Qt.Horizontal)
        self.preview_point_size_slider.setRange(10, 200)  # 1.0 .. 20.0 ×10
        self.preview_point_size_slider.setValue(30)
        self.preview_point_size_slider.setToolTip(
            "Rendered size of each point in pixels (1.0–20.0). Larger points fill\n"
            "gaps in sparse clouds; smaller points show structure better."
        )
        self.preview_point_size_slider.valueChanged.connect(self._on_point_size_changed)
        size_row.addWidget(self.preview_point_size_slider)
        self.preview_point_size_value = QLabel("3.0")
        self.preview_point_size_value.setMinimumWidth(32)
        self.preview_point_size_value.setStyleSheet("color: #aaa;")
        size_row.addWidget(self.preview_point_size_value)
        layout.addLayout(size_row)

        thr_row = QHBoxLayout()
        thr_row.addWidget(QLabel("Threshold"))
        self.preview_point_threshold_slider = QSlider(Qt.Horizontal)
        self.preview_point_threshold_slider.setRange(0, 255)
        self.preview_point_threshold_slider.setValue(25)
        self.preview_point_threshold_slider.setToolTip(
            "Intensity (0–255) above which a voxel becomes a point.\n"
            "Lower = more points (denser cloud) · Higher = only the brightest."
        )
        self.preview_point_threshold_slider.valueChanged.connect(self._on_point_threshold_slider)
        thr_row.addWidget(self.preview_point_threshold_slider)
        self.preview_point_threshold_value = QLabel("25")
        self.preview_point_threshold_value.setMinimumWidth(28)
        self.preview_point_threshold_value.setStyleSheet("color: #aaa;")
        thr_row.addWidget(self.preview_point_threshold_value)
        layout.addLayout(thr_row)

        self.preview_point_threshold_auto = QCheckBox("Auto threshold (from Density)")
        self.preview_point_threshold_auto.setChecked(True)
        self.preview_point_threshold_auto.toggled.connect(self._on_point_threshold_auto_toggled)
        layout.addWidget(self.preview_point_threshold_auto)

        self._update_point_threshold_enabled()
        return page

    # --- mode-specific event handlers ------------------------------------

    def _on_point_level_changed(self, _value: int) -> None:
        self._update_level_hint()
        self._emit_preview_settings_changed()

    def _on_point_size_changed(self, raw: int) -> None:
        value = raw / 10.0
        self.preview_point_size_value.setText(f"{value:.1f}")
        self._emit_preview_settings_changed()

    def _on_point_threshold_slider(self, value: int) -> None:
        self.preview_point_threshold_value.setText(str(int(value)))
        self._emit_preview_settings_changed()

    def _on_point_threshold_auto_toggled(self, checked: bool) -> None:
        del checked
        self._update_point_threshold_enabled()
        self._emit_preview_settings_changed()

    def _update_point_threshold_enabled(self) -> None:
        auto = self.preview_point_threshold_auto.isChecked()
        self.preview_point_threshold_slider.setEnabled(not auto)
        self.preview_point_threshold_value.setEnabled(not auto)

    def _sync_preview_mode_visibility(self) -> None:
        if not hasattr(self, "_mode_param_stack"):
            return
        mode = self.get_preview_mode()
        self._mode_param_stack.setCurrentIndex(0 if mode == "isosurface_lit" else 1)

    def is_preview_native_resolution(self) -> bool:
        return self.preview_native_check.isChecked()

    def set_preview_native_resolution(self, enabled: bool) -> None:
        self.preview_native_check.blockSignals(True)
        self.preview_native_check.setChecked(bool(enabled))
        self.preview_native_check.blockSignals(False)
        self._update_stride_controls_enabled()
        self._update_level_hint()
        self._update_stride_hint()

    def is_preview_range_limited(self) -> bool:
        return self.preview_limit_range_check.isChecked()

    def get_preview_z_range_0based(self) -> Tuple[int, int]:
        """Inclusive range in 0-based slice indices."""
        z0 = self.preview_z_start_spin.value() - 1
        z1 = self.preview_z_end_spin.value() - 1
        if z1 < z0:
            z1 = z0
        return z0, z1

    def set_scan_slice_count(self, count: int) -> None:
        """Update From/To spin limits when a scan is loaded."""
        n = max(1, count)
        self.preview_z_start_spin.setRange(1, n)
        self.preview_z_end_spin.setRange(1, n)
        if self.preview_z_end_spin.value() > n:
            self.preview_z_end_spin.setValue(n)
        if self.preview_z_start_spin.value() > n:
            self.preview_z_start_spin.setValue(1)

    def set_preview_z_range_1based(self, start: int, end: int, limit: bool) -> None:
        self.preview_limit_range_check.blockSignals(True)
        self.preview_limit_range_check.setChecked(limit)
        self.preview_limit_range_check.blockSignals(False)
        self.preview_z_start_spin.blockSignals(True)
        self.preview_z_end_spin.blockSignals(True)
        self.preview_z_start_spin.setValue(max(1, start + 1))
        self.preview_z_end_spin.setValue(max(1, end + 1))
        self.preview_z_start_spin.setEnabled(limit)
        self.preview_z_end_spin.setEnabled(limit)
        self.preview_z_start_spin.blockSignals(False)
        self.preview_z_end_spin.blockSignals(False)

    def _update_level_hint(self) -> None:
        v = self.preview_level_spin.value()
        hints = {
            1: "1 = sparse",
            2: "2",
            3: "3",
            4: "4",
            5: "5 = dense",
        }
        self.preview_level_label.setText(hints.get(v, ""))

    def _update_stride_controls_enabled(self) -> None:
        native = self.preview_native_check.isChecked()
        for w in (
            self.preview_stride_z_slider,
            self.preview_stride_xy_slider,
        ):
            w.setEnabled(not native)

    def _update_stride_hint(self) -> None:
        if self.preview_native_check.isChecked():
            self.preview_stride_hint.setText(
                "Native resolution: stride locked to 1×1×1 (full grid — highest RAM)."
            )
            return
        zv = self.preview_stride_z_slider.value()
        xyv = self.preview_stride_xy_slider.value()
        self.preview_stride_hint.setText(
            f"Preview grid uses every {zv} slice(s) in range and XY pool {xyv}×{xyv} — "
            "Z and XY are independent."
        )

    def _emit_preview_settings_changed(self, *_args) -> None:
        native = self.preview_native_check.isChecked()
        self._update_stride_controls_enabled()
        self._update_level_hint()
        self._update_stride_hint()
        if self.preview_limit_range_check.isChecked():
            self.preview_z_start_spin.setEnabled(True)
            self.preview_z_end_spin.setEnabled(True)
        else:
            self.preview_z_start_spin.setEnabled(False)
            self.preview_z_end_spin.setEnabled(False)
        self.preview_settings_changed.emit()

    def set_preview_status(self, text: str) -> None:
        self.preview_status.setText(text)

    def set_preview_busy(self, busy: bool) -> None:
        self.preview_start_btn.setEnabled(not busy)
        self.preview_stop_btn.setEnabled(busy)
        self.preview_mode_combo.setEnabled(not busy)
        native = self.preview_native_check.isChecked()
        self.preview_stride_z_slider.setEnabled(not busy and not native)
        self.preview_stride_xy_slider.setEnabled(not busy and not native)
        self.preview_native_check.setEnabled(not busy)
        is_pc = self.get_preview_mode() == "point_cloud"
        is_iso = not is_pc
        # Isosurface params.
        self.preview_iso_color_btn.setEnabled(not busy and is_iso)
        # Point-cloud params.
        self.preview_level_spin.setEnabled(not busy and is_pc)
        self.preview_point_size_slider.setEnabled(not busy and is_pc)
        self.preview_point_threshold_auto.setEnabled(not busy and is_pc)
        self.preview_point_threshold_slider.setEnabled(
            not busy and is_pc and not self.preview_point_threshold_auto.isChecked()
        )

    def set_preview_window_visible(self, visible: bool) -> None:
        """Reflect the child 3D window's open/closed state in the buttons."""
        self.preview_show_window_btn.setEnabled(not visible)
        self.preview_hide_window_btn.setEnabled(bool(visible))
