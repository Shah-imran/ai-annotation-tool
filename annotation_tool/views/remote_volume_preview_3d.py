"""
Parent-side proxy for the out-of-process 3D preview.

This object replaces the in-app VolumePreview3D in the workspace. All VTK
rendering happens in a separate child process; this proxy simply spawns /
shuts down the child, forwards commands over IPC, and re-emits status as
signals the rest of the app already listens to.

It is a QWidget only so it can be parented to the workspace and live with
the same lifetime; it intentionally has no visible UI and is never added
to a layout.

Public API mirrors the subset of the old VolumePreview3D contract used by
VolumeController:
- is_available
- clear()
- cancel_render()
- reset_orientation()
- set_current_slice(z)
- start_remote_preview(generation, params)
- signals: render_finished(int), render_stage(str)
plus child-window helpers:
- show_child_window(), hide_child_window(), is_child_window_visible
- busy_changed(bool), child_window_visible_changed(bool)
"""
from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtWidgets import QWidget

from ..services.preview_process_client import PreviewProcessClient


class RemoteVolumePreview3D(QWidget):
    """Headless proxy driving a child-process 3D preview window."""

    # Signals compatible with the legacy VolumePreview3D contract.
    render_finished = pyqtSignal(int)
    render_stage = pyqtSignal(str)

    # Extra signals specific to the remote path.
    spawn_failed = pyqtSignal(str)
    child_window_visible_changed = pyqtSignal(bool)
    busy_changed = pyqtSignal(bool)
    preview_ui_changed = pyqtSignal(dict)

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        # Never visible — kept as a QWidget purely for parent ownership.
        self.setVisible(False)

        self._client = PreviewProcessClient(self)
        self._child_visible = False
        self._busy = False
        self._active_generation = 0
        # Last generation we were told to track; used to clear panel busy
        # state even if the child disconnects without emitting FINISHED.
        self._last_generation = 0
        self._preview_ui_config: dict = {}

        self._wire_client()

    # ----- legacy-compatible API -----------------------------------------

    @property
    def is_available(self) -> bool:
        return True

    @property
    def is_child_window_visible(self) -> bool:
        return self._child_visible

    @property
    def is_busy(self) -> bool:
        return self._busy

    def clear(self) -> None:
        if self._client.is_alive:
            self._client.send_clear()

    def cancel_render(self) -> None:
        # Cancel in the child but also locally flip our busy state to False;
        # the controller's stop handler is what actually drove this.
        if self._client.is_alive:
            self._client.send_cancel()
        self._set_busy(False)

    def reset_orientation(self) -> None:
        # No need to spawn the child just to reset a camera that doesn't
        # exist yet. If it isn't running, this is a no-op.
        if self._client.is_alive:
            self._client.send_reset_view()

    def set_current_slice(self, z: int) -> None:
        if self._client.is_alive:
            self._client.send_set_slice(int(z))

    # ----- new API for child-process driven preview ----------------------

    def start_remote_preview(self, generation: int, params: dict) -> bool:
        """Spawn the child if needed and send a start_preview command."""
        if not self._client.ensure_started():
            return False
        self._active_generation = int(generation)
        self._last_generation = int(generation)
        self._set_busy(True)
        self._emit_stage("Spawning 3D preview process…")
        ok = self._client.send_start_preview(int(generation), params)
        if not ok:
            self._emit_stage("Queued preview — waiting for child process to come up…")
        # Keep the 3D window hidden until the child reports FINISHED.
        self.hide_child_window()
        return True

    def show_child_window(self) -> None:
        if not self._client.ensure_started():
            return
        self._client.show_child_window()
        # The child confirms visibility via window_closed (and we treat any
        # successful show as visible until then).
        if not self._child_visible:
            self._child_visible = True
            self.child_window_visible_changed.emit(True)

    def hide_child_window(self) -> None:
        if self._client.is_alive:
            self._client.hide_child_window()
        if self._child_visible:
            self._child_visible = False
            self.child_window_visible_changed.emit(False)

    def shutdown(self) -> None:
        self._client.shutdown()

    def configure_preview_ui(
        self,
        *,
        brightness_percent: int = 100,
        snapshot_dir: str = "",
        mesh_dir: str = "",
    ) -> None:
        self._preview_ui_config = {
            "brightness_percent": int(brightness_percent),
            "snapshot_dir": snapshot_dir or "",
            "mesh_dir": mesh_dir or "",
        }
        if self._client.is_ready:
            self._client.send_set_preview_ui(**self._preview_ui_config)

    def _apply_pending_preview_ui(self) -> None:
        if self._preview_ui_config and self._client.is_ready:
            self._client.send_set_preview_ui(**self._preview_ui_config)

    def prewarm(self) -> None:
        """Spawn the child process in the background.

        Called when the user enters 3D mode or loads a scan, so that the
        ~1–2 s VTK / PyVista import cost is paid silently while the user is
        still picking modes and scrolling slices. By the time they click
        Start the child is already alive and the first preview kicks off
        instantly. No-op if the child is already running or starting.
        """
        self._client.ensure_started()

    # ----- wiring --------------------------------------------------------

    def _wire_client(self) -> None:
        self._client.ready.connect(self._on_child_ready)
        self._client.stage.connect(self._on_stage)
        self._client.started.connect(self._on_started)
        self._client.finished.connect(self._on_finished)
        self._client.failed.connect(self._on_failed)
        self._client.window_closed.connect(self._on_child_window_closed)
        self._client.disconnected.connect(self._on_child_disconnected)
        self._client.spawn_failed.connect(self._on_spawn_failed)
        self._client.preview_ui_changed.connect(self.preview_ui_changed.emit)

    def _emit_stage(self, text: str) -> None:
        self.render_stage.emit(text)

    def _set_busy(self, busy: bool) -> None:
        if self._busy == busy:
            return
        self._busy = busy
        self.busy_changed.emit(busy)

    def _clear_busy_for_active_generation(self) -> None:
        """Clear busy state by emitting render_finished for whatever
        generation the controller is currently waiting on. This is the
        recovery path when the child disconnects without a FINISHED."""
        if not self._busy:
            return
        gen = self._active_generation or self._last_generation
        self._set_busy(False)
        self.render_finished.emit(int(gen))

    # ----- IPC signal handlers ------------------------------------------

    def _on_child_ready(self) -> None:
        self._emit_stage("3D preview process ready.")
        self._apply_pending_preview_ui()

    def _on_stage(self, text: str, gen: int) -> None:
        del gen
        self._emit_stage(text)

    def _on_started(self, gen: int) -> None:
        self._active_generation = int(gen)
        self._last_generation = int(gen)
        self._set_busy(True)
        self._emit_stage("Build started in 3D preview process…")

    def _on_finished(self, gen: int, text: str) -> None:
        gen_int = int(gen)
        if text:
            self._emit_stage(text)
        # Clear busy regardless of which generation finished, so a stale
        # FINISHED still releases the UI.
        self._set_busy(False)
        self.render_finished.emit(gen_int)
        # Reveal the 3D window only once the full preview is ready.
        self.show_child_window()

    def _on_failed(self, gen: int, text: str) -> None:
        self._emit_stage(f"3D preview failed: {text}")
        self._set_busy(False)
        self.render_finished.emit(int(gen))

    def _on_child_window_closed(self) -> None:
        if self._child_visible:
            self._child_visible = False
            self.child_window_visible_changed.emit(False)

    def _on_child_disconnected(self) -> None:
        # Child crashed or quit. Make sure the panel doesn't sit forever
        # with a grayed-out Start button waiting on a FINISHED that will
        # never arrive.
        if self._child_visible:
            self._child_visible = False
            self.child_window_visible_changed.emit(False)
        self._emit_stage(
            "3D preview process is not running. Click Start preview to relaunch it."
        )
        self._clear_busy_for_active_generation()

    def _on_spawn_failed(self, message: str) -> None:
        self._emit_stage(f"Could not start 3D preview process: {message}")
        self.spawn_failed.emit(message)
        self._clear_busy_for_active_generation()
