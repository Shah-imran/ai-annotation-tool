"""
Workspace widget for 3D volume annotation (2D slice viewer + control panel).

The 3D preview now runs in a separate process and is driven entirely from
the volume control panel on the right — there is no in-window 3D pane any
more. The 2D slice canvas is shown directly (no collapse/minimize chrome)
because there's nothing else to share vertical space with.

The RemoteVolumePreview3D proxy is still owned by this workspace for
lifetime management, but it is intentionally invisible and is not added to
the layout.
"""
from typing import List, Optional

from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtWidgets import QHBoxLayout, QSplitter, QVBoxLayout, QWidget

from .remote_volume_preview_3d import RemoteVolumePreview3D
from .slice_canvas import SliceCanvas
from .volume_control_panel import VolumeControlPanel


class VolumeWorkspace(QWidget):
    """Splitter: [ 2D slice canvas ] + volume control panel."""

    splitter_layout_changed = pyqtSignal(list, list)
    # Kept for backwards-compatibility with the main window/controller; neither
    # the 3D pane nor the slice-pane collapse feature exists anymore, so these
    # signals are never emitted.
    preview_pane_collapsed_changed = pyqtSignal(bool)
    slice_pane_collapsed_changed = pyqtSignal(bool)

    def __init__(self):
        super().__init__()
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Headless proxy — parented for lifetime, never shown.
        self.preview_3d = RemoteVolumePreview3D(self)

        self.slice_canvas = SliceCanvas()
        self.control_panel = VolumeControlPanel()

        # The slice canvas no longer needs a collapsible wrapper — show it
        # directly. We still expose a `view_splitter` so any persistence code
        # that asks for vertical splitter sizes keeps working (it holds one
        # widget now).
        slice_holder = QWidget()
        slice_layout = QVBoxLayout(slice_holder)
        slice_layout.setContentsMargins(0, 0, 0, 0)
        slice_layout.addWidget(self.slice_canvas)

        self.view_splitter = QSplitter(Qt.Vertical)
        self.view_splitter.setObjectName("volumeViewSplitter")
        self.view_splitter.addWidget(slice_holder)
        self.view_splitter.setStretchFactor(0, 1)
        self.view_splitter.splitterMoved.connect(self._on_splitter_moved)

        self.splitter = QSplitter(Qt.Horizontal)
        self.splitter.setObjectName("volumeMainSplitter")
        self.splitter.addWidget(self.view_splitter)
        self.splitter.addWidget(self.control_panel)
        self.splitter.setStretchFactor(0, 2)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([800, 320])
        self.splitter.splitterMoved.connect(self._on_splitter_moved)

        layout.addWidget(self.splitter)

    # ----- splitter / pane state ----------------------------------------

    def _on_splitter_moved(self, pos: int, index: int) -> None:
        del pos, index
        self._emit_splitter_layout()

    # ----- collapse stubs (no-op now) -----------------------------------

    def set_preview_collapsed(self, collapsed: bool) -> None:
        del collapsed

    def is_preview_collapsed(self) -> bool:
        return True

    def toggle_preview_pane(self) -> bool:
        return True

    def set_slice_collapsed(self, collapsed: bool) -> None:
        del collapsed

    def is_slice_collapsed(self) -> bool:
        return False

    def toggle_slice_pane(self) -> bool:
        return False

    # ----- persistence --------------------------------------------------

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
        if vertical and sum(vertical) > 0:
            total = sum(vertical)
            self.view_splitter.blockSignals(True)
            self.view_splitter.setSizes([total])
            self.view_splitter.blockSignals(False)
        if horizontal and len(horizontal) == 2 and sum(horizontal) > 0:
            self.splitter.blockSignals(True)
            self.splitter.setSizes(horizontal)
            self.splitter.blockSignals(False)

    def apply_pane_collapsed_state(
        self, preview_collapsed: bool, slice_collapsed: bool
    ) -> None:
        """Backwards-compatible stub. Collapse no longer exists in 3D mode."""
        del preview_collapsed, slice_collapsed
