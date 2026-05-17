"""
Top-level window for the 3D-preview child process.

Hosts the reused VolumePreview3D widget (which owns the PyVista QtInteractor).
All preview work happens in this process so the main app's UI stays responsive
regardless of mesh size.

The window also offers a small brightness slider at the bottom that scales the
intensity of every renderer light (key/fill/rim or the default headlight). It
lives in the child window — not in the main app — because it tweaks GPU state
on the plotter and has no need to round-trip through IPC.
"""
from __future__ import annotations

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QCloseEvent
from PyQt5.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QSlider,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from ..views.volume_preview_3d import VolumePreview3D


# Slider value 100 == factor 1.0 (default). Range 10..250 -> factor 0.1..2.5.
_BRIGHTNESS_SLIDER_SCALE = 100
_BRIGHTNESS_DEFAULT = 100  # %
_BRIGHTNESS_MIN = 10
_BRIGHTNESS_MAX = 250


class ChildPreviewWindow(QMainWindow):
    """Standalone window hosting the 3D preview widget plus a brightness control."""

    user_closed = pyqtSignal()
    reset_view_clicked = pyqtSignal()

    def __init__(self, title: str = "3D Volume Preview") -> None:
        super().__init__()
        self.setWindowTitle(title)
        self.resize(1024, 768)
        self.setMinimumSize(640, 480)

        central = QWidget(self)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        self._preview = VolumePreview3D(central)
        root.addWidget(self._preview, 1)

        # Brightness strip — thin bar at the bottom. Subtle styling so the
        # 3D view stays the focus.
        self._brightness_bar = self._build_brightness_bar(central)
        root.addWidget(self._brightness_bar, 0)

        self.setCentralWidget(central)

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_brightness_bar(self, parent: QWidget) -> QWidget:
        bar = QWidget(parent)
        bar.setStyleSheet(
            "QWidget { background-color: #1a1a1a; }"
            "QLabel { color: #d8d8d8; font-size: 11px; }"
            "QToolButton { color: #d8d8d8; background: transparent;"
            "  border: 1px solid #3a3a3a; border-radius: 3px; padding: 2px 8px; }"
            "QToolButton:hover { background-color: #2a2a2a; }"
        )
        layout = QHBoxLayout(bar)
        layout.setContentsMargins(10, 4, 10, 6)
        layout.setSpacing(8)

        label = QLabel("Brightness")
        label.setToolTip(
            "Scales the intensity of every light in the 3D scene.\n"
            "100% is the default. Lower = darker, higher = brighter.\n"
            "Helpful for revealing detail inside dark cavities or toning down\n"
            "overly bright isosurfaces."
        )
        layout.addWidget(label)

        self._brightness_slider = QSlider(Qt.Horizontal, bar)
        self._brightness_slider.setRange(_BRIGHTNESS_MIN, _BRIGHTNESS_MAX)
        self._brightness_slider.setValue(_BRIGHTNESS_DEFAULT)
        self._brightness_slider.setSingleStep(5)
        self._brightness_slider.setPageStep(20)
        self._brightness_slider.setToolTip(
            "Drag to brighten or darken the 3D scene without rebuilding the preview."
        )
        self._brightness_slider.valueChanged.connect(self._on_brightness_changed)
        layout.addWidget(self._brightness_slider, 1)

        self._brightness_value = QLabel(f"{_BRIGHTNESS_DEFAULT}%")
        self._brightness_value.setMinimumWidth(46)
        self._brightness_value.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        layout.addWidget(self._brightness_value)

        reset_btn = QToolButton(bar)
        reset_btn.setText("Reset")
        reset_btn.setToolTip("Restore the default brightness (100%).")
        reset_btn.clicked.connect(self._reset_brightness)
        layout.addWidget(reset_btn)

        return bar

    # ------------------------------------------------------------------
    # External API
    # ------------------------------------------------------------------
    @property
    def preview(self) -> VolumePreview3D:
        return self._preview

    def set_status_text(self, text: str) -> None:
        # Status now lives only in the main app's volume panel.
        del text

    def reset_orientation(self) -> None:
        self._preview.reset_orientation()

    # ------------------------------------------------------------------
    # Brightness handling
    # ------------------------------------------------------------------
    def _on_brightness_changed(self, value: int) -> None:
        factor = float(value) / float(_BRIGHTNESS_SLIDER_SCALE)
        self._brightness_value.setText(f"{int(value)}%")
        self._preview.set_brightness(factor)

    def _reset_brightness(self) -> None:
        # `setValue` will fire `valueChanged`, which both updates the label
        # and pushes the new factor down to the preview widget.
        self._brightness_slider.setValue(_BRIGHTNESS_DEFAULT)

    # ------------------------------------------------------------------
    # Window events
    # ------------------------------------------------------------------
    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        # Don't actually exit when the user clicks 'X' — parent decides lifecycle.
        # Hide and tell the parent so it can update its proxy state.
        event.ignore()
        self.hide()
        self.user_closed.emit()

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key_Home:
            self.reset_orientation()
            event.accept()
            return
        super().keyPressEvent(event)
