"""
Workspace widget for 3D volume annotation (3D preview + slice viewer + control panel).
"""
from typing import List, Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QHBoxLayout, QSplitter, QWidget

from .collapsible_view_pane import CollapsibleViewPane
from .slice_canvas import SliceCanvas
from .volume_control_panel import VolumeControlPanel
from .volume_preview_3d import VolumePreview3D


class VolumeWorkspace(QWidget):
    """Splitter: [ 3D preview | slice canvas ] + volume control panel."""

    splitter_layout_changed = pyqtSignal(list, list)
    preview_pane_collapsed_changed = pyqtSignal(bool)
    slice_pane_collapsed_changed = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        self.preview_3d = VolumePreview3D()
        self.slice_canvas = SliceCanvas()
        self.control_panel = VolumeControlPanel()

        self.preview_pane = CollapsibleViewPane("3D Preview", self.preview_3d)
        self.slice_pane = CollapsibleViewPane("2D Slice", self.slice_canvas)

        self._saved_preview_height = 280
        self._saved_slice_height = 520
        self._updating_splitter = False

        self.view_splitter = QSplitter(Qt.Vertical)
        self.view_splitter.setObjectName("volumeViewSplitter")
        self.view_splitter.addWidget(self.preview_pane)
        self.view_splitter.addWidget(self.slice_pane)
        self.view_splitter.setStretchFactor(0, 1)
        self.view_splitter.setStretchFactor(1, 2)
        self.view_splitter.setSizes([280, 520])
        self.view_splitter.splitterMoved.connect(self._on_splitter_moved)

        self.preview_pane.collapse_changed.connect(self._on_preview_collapse_changed)
        self.slice_pane.collapse_changed.connect(self._on_slice_collapse_changed)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setObjectName("volumeMainSplitter")
        self.splitter.addWidget(self.view_splitter)
        self.splitter.addWidget(self.control_panel)
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([800, 320])
        self.splitter.splitterMoved.connect(self._on_splitter_moved)

        layout.addWidget(self.splitter)

    def _on_splitter_moved(self, pos: int, index: int) -> None:
        del pos, index
        if self._updating_splitter:
            return
        sizes = self.view_splitter.sizes()
        if len(sizes) == 2:
            if not self.preview_pane.is_collapsed and sizes[0] > CollapsibleViewPane.COLLAPSED_SPLITTER_SIZE:
                self._saved_preview_height = sizes[0]
            if not self.slice_pane.is_collapsed and sizes[1] > CollapsibleViewPane.COLLAPSED_SPLITTER_SIZE:
                self._saved_slice_height = sizes[1]
        self._emit_splitter_layout()

    def _on_preview_collapse_changed(self, collapsed: bool) -> None:
        self._apply_vertical_split_for_collapse()
        self.preview_pane_collapsed_changed.emit(collapsed)

    def _on_slice_collapse_changed(self, collapsed: bool) -> None:
        self._apply_vertical_split_for_collapse()
        self.slice_pane_collapsed_changed.emit(collapsed)

    def _apply_vertical_split_for_collapse(self) -> None:
        self._updating_splitter = True
        try:
            total = max(200, sum(self.view_splitter.sizes()))
            mini = CollapsibleViewPane.COLLAPSED_SPLITTER_SIZE
            preview_collapsed = self.preview_pane.is_collapsed
            slice_collapsed = self.slice_pane.is_collapsed

            if preview_collapsed and slice_collapsed:
                self.view_splitter.setSizes([mini, mini])
            elif preview_collapsed:
                self.view_splitter.setSizes([mini, total - mini])
            elif slice_collapsed:
                self.view_splitter.setSizes([total - mini, mini])
            else:
                preview_h = max(80, self._saved_preview_height)
                slice_h = max(80, self._saved_slice_height)
                scale = total / max(1, preview_h + slice_h)
                self.view_splitter.setSizes(
                    [int(preview_h * scale), int(slice_h * scale)]
                )
        finally:
            self._updating_splitter = False
        self._emit_splitter_layout()

    def set_preview_collapsed(self, collapsed: bool) -> None:
        self.preview_pane.set_collapsed(collapsed, emit_signal=False)
        self._apply_vertical_split_for_collapse()
        self.preview_pane_collapsed_changed.emit(collapsed)

    def set_slice_collapsed(self, collapsed: bool) -> None:
        self.slice_pane.set_collapsed(collapsed, emit_signal=False)
        self._apply_vertical_split_for_collapse()
        self.slice_pane_collapsed_changed.emit(collapsed)

    def is_preview_collapsed(self) -> bool:
        return self.preview_pane.is_collapsed

    def is_slice_collapsed(self) -> bool:
        return self.slice_pane.is_collapsed

    def toggle_preview_pane(self) -> bool:
        """Toggle 3D preview; returns new collapsed state."""
        collapsed = not self.preview_pane.is_collapsed
        self.set_preview_collapsed(collapsed)
        return collapsed

    def toggle_slice_pane(self) -> bool:
        """Toggle 2D slice view; returns new collapsed state."""
        collapsed = not self.slice_pane.is_collapsed
        self.set_slice_collapsed(collapsed)
        return collapsed

    def _emit_splitter_layout(self) -> None:
        self.splitter_layout_changed.emit(
            self.view_splitter.sizes(),
            self.splitter.sizes(),
        )

    def apply_splitter_sizes(
        self,
        vertical: Optional[List[int]] = None,
        horizontal: Optional[List[int]] = None,
    ) -> None:
        """Restore saved splitter sizes (called on startup / mode switch)."""
        if vertical and len(vertical) == 2 and sum(vertical) > 0:
            if not self.preview_pane.is_collapsed:
                self._saved_preview_height = vertical[0]
            if not self.slice_pane.is_collapsed:
                self._saved_slice_height = vertical[1]
            if not self.preview_pane.is_collapsed and not self.slice_pane.is_collapsed:
                self._updating_splitter = True
                self.view_splitter.setSizes(vertical)
                self._updating_splitter = False
            else:
                self._apply_vertical_split_for_collapse()
        if horizontal and len(horizontal) == 2 and sum(horizontal) > 0:
            self.splitter.blockSignals(True)
            self.splitter.setSizes(horizontal)
            self.splitter.blockSignals(False)

    def apply_pane_collapsed_state(
        self, preview_collapsed: bool, slice_collapsed: bool
    ) -> None:
        """Restore minimize/expand state without duplicate signals."""
        self.preview_pane.set_collapsed(preview_collapsed, emit_signal=False)
        self.slice_pane.set_collapsed(slice_collapsed, emit_signal=False)
        self._apply_vertical_split_for_collapse()
