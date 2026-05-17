"""
Child-side IPC: connects to the parent's QLocalServer and dispatches messages.
"""
from __future__ import annotations

from typing import Optional

from PyQt5.QtCore import QObject, Qt, QTimer, pyqtSignal
from PyQt5.QtNetwork import QLocalSocket

from ..services import preview_ipc as ipc
from .child_coordinator import ChildPreviewCoordinator
from .child_window import ChildPreviewWindow


class ChildIpcEndpoint(QObject):
    """Owns the QLocalSocket, the window, and the coordinator. Wires them up."""

    def __init__(self, window: ChildPreviewWindow, socket_name: str, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._window = window
        self._socket_name = socket_name

        self._socket = QLocalSocket(self)
        self._reader = ipc.JsonLineReader()
        self._socket.readyRead.connect(self._on_ready_read)
        self._socket.connected.connect(self._on_connected)
        self._socket.disconnected.connect(self._on_disconnected)
        self._socket.errorOccurred.connect(self._on_error)

        self._coord = ChildPreviewCoordinator(window.preview, parent=self)
        self._coord.stage.connect(self._on_stage, Qt.QueuedConnection)
        self._coord.started.connect(self._on_started, Qt.QueuedConnection)
        self._coord.finished.connect(self._on_finished, Qt.QueuedConnection)
        self._coord.failed.connect(self._on_failed, Qt.QueuedConnection)

        self._window.user_closed.connect(self._on_window_closed)
        self._window.reset_view_clicked.connect(self._coord.reset_view)

        self._reconnect_attempts = 0
        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.setSingleShot(True)
        self._reconnect_timer.timeout.connect(self.connect_to_parent)

    def connect_to_parent(self) -> None:
        if self._socket.state() != QLocalSocket.UnconnectedState:
            return
        self._socket.connectToServer(self._socket_name)

    def _send(self, message: dict) -> None:
        if self._socket.state() != QLocalSocket.ConnectedState:
            return
        try:
            self._socket.write(ipc.encode_message(message))
            self._socket.flush()
        except Exception as exc:
            print(f"[child] write failed: {exc}")

    def _on_connected(self) -> None:
        self._reconnect_attempts = 0
        self._send({"type": ipc.MSG_READY})
        self._window.set_status_text("Connected to main app — waiting for preview request.")

    def _on_disconnected(self) -> None:
        self._window.set_status_text("Disconnected from main app.")
        # The parent quitting will close stdin/socket — exit shortly after.
        QTimer.singleShot(150, self._maybe_quit_on_lost_parent)

    def _maybe_quit_on_lost_parent(self) -> None:
        if self._socket.state() == QLocalSocket.ConnectedState:
            return
        from PyQt5.QtWidgets import QApplication
        QApplication.instance().quit()

    def _on_error(self, _err) -> None:
        if self._socket.state() == QLocalSocket.ConnectedState:
            return
        self._reconnect_attempts += 1
        if self._reconnect_attempts > 40:  # ~6s
            from PyQt5.QtWidgets import QApplication
            QApplication.instance().quit()
            return
        self._reconnect_timer.start(150)

    def _on_ready_read(self) -> None:
        chunk = bytes(self._socket.readAll())
        for msg in self._reader.feed(chunk):
            self._dispatch(msg)

    def _dispatch(self, msg: dict) -> None:
        mtype = msg.get("type")
        if mtype == ipc.MSG_START_PREVIEW:
            gen = int(msg.get("generation", 0))
            params = msg.get("params") or {}
            if not isinstance(params, dict):
                params = {}
            self._window.set_status_text("Loading slice stack…")
            self._coord.start_build(gen, params)
        elif mtype == ipc.MSG_CANCEL:
            self._coord.cancel()
            self._window.set_status_text("Cancelled.")
        elif mtype == ipc.MSG_SET_SLICE:
            self._coord.set_current_slice(int(msg.get("z", 0)))
        elif mtype == ipc.MSG_RESET_VIEW:
            self._coord.reset_view()
        elif mtype == ipc.MSG_CLEAR:
            self._coord.clear_scene()
            self._window.set_status_text("Scene cleared.")
        elif mtype == ipc.MSG_SHOW_WINDOW:
            self._window.showNormal()
            self._window.raise_()
            self._window.activateWindow()
        elif mtype == ipc.MSG_HIDE_WINDOW:
            self._window.hide()
        elif mtype == ipc.MSG_SHUTDOWN:
            self._send({"type": ipc.MSG_BYE})
            from PyQt5.QtWidgets import QApplication
            QApplication.instance().quit()
        elif mtype == ipc.MSG_HELLO:
            self._send({"type": ipc.MSG_READY})
        # Unknown messages are ignored.

    def _on_stage(self, text: str) -> None:
        self._window.set_status_text(text)
        self._send({"type": ipc.MSG_STAGE, "text": text, "generation": self._coord.current_generation})

    def _on_started(self, gen: int) -> None:
        self._send({"type": ipc.MSG_STARTED, "generation": int(gen)})

    def _on_finished(self, gen: int, text: str) -> None:
        self._window.set_status_text(text)
        self._send({"type": ipc.MSG_FINISHED, "generation": int(gen), "text": text})

    def _on_failed(self, gen: int, text: str) -> None:
        self._window.set_status_text(f"Failed: {text}")
        self._send({"type": ipc.MSG_FAILED, "generation": int(gen), "text": text})

    def _on_window_closed(self) -> None:
        self._send({"type": ipc.MSG_WINDOW_CLOSED})
