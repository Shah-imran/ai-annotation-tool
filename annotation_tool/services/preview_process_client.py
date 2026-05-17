"""
Parent-side client for the 3D-preview child process.

Spawns `python -m annotation_tool.preview_process` lazily, listens for it on a
QLocalServer, and forwards commands / receives status updates.
"""
from __future__ import annotations

import os
import sys
import uuid
from typing import Optional

from PyQt5.QtCore import QObject, QProcess, QProcessEnvironment, Qt, QTimer, pyqtSignal
from PyQt5.QtNetwork import QLocalServer, QLocalSocket

from . import preview_ipc as ipc


class PreviewProcessClient(QObject):
    """Owns the QLocalServer, spawns the child, and dispatches IPC messages."""

    ready = pyqtSignal()
    stage = pyqtSignal(str, int)  # text, generation
    started = pyqtSignal(int)
    finished = pyqtSignal(int, str)  # generation, status text
    failed = pyqtSignal(int, str)  # generation, error text
    window_closed = pyqtSignal()
    disconnected = pyqtSignal()
    spawn_failed = pyqtSignal(str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._socket_name = f"annotool_3dpreview_{uuid.uuid4().hex}"
        self._server = QLocalServer(self)
        self._server.setSocketOptions(QLocalServer.UserAccessOption)
        self._server.newConnection.connect(self._on_new_connection)

        self._socket: Optional[QLocalSocket] = None
        self._reader = ipc.JsonLineReader()

        self._process: Optional[QProcess] = None
        self._is_ready = False
        self._is_spawning = False  # True between start() and started/errorOccurred
        self._pending_messages: list[dict] = []
        self._shutting_down = False

        # Try to listen now; on failure we still allow lazy retry.
        if not self._start_listening():
            QTimer.singleShot(0, self._start_listening)

    @property
    def is_ready(self) -> bool:
        return self._is_ready

    @property
    def is_alive(self) -> bool:
        return (
            self._process is not None
            and self._process.state() != QProcess.NotRunning
        )

    @property
    def is_spawning(self) -> bool:
        """True between the moment we call QProcess.start() and the moment
        the OS confirms the child has started (or failed to start)."""
        return self._is_spawning

    # ----- lifecycle -------------------------------------------------------

    def _start_listening(self) -> bool:
        try:
            QLocalServer.removeServer(self._socket_name)
        except Exception:
            pass
        if not self._server.listen(self._socket_name):
            err = self._server.errorString()
            self.spawn_failed.emit(f"Could not start IPC server: {err}")
            return False
        return True

    def ensure_started(self) -> bool:
        """Spawn the child process if not already running.

        This is **fully asynchronous** — it never blocks the parent's UI
        thread waiting for the child to come up. Returns True if the child
        is alive or has been kicked off; False only if we cannot even set
        up the local IPC server.

        Messages sent before the child connects are buffered by `_send` and
        flushed on READY, so callers don't need to wait either.
        """
        if self.is_alive or self._is_spawning:
            return True
        if not self._server.isListening() and not self._start_listening():
            return False

        process = QProcess(self)
        process.setProgram(sys.executable)
        process.setArguments([
            "-u",
            "-m",
            "annotation_tool.preview_process",
            "--socket",
            self._socket_name,
        ])
        # Inherit the parent's full environment (USERPROFILE, HOMEPATH, PATH, etc.)
        # then add PYTHONUNBUFFERED. Calling QProcess.processEnvironment() with no
        # prior setProcessEnvironment() returns an empty environment, which would
        # break matplotlib / pyvista in the child (Path.home() needs HOME-style vars).
        env = QProcessEnvironment.systemEnvironment()
        env.insert("PYTHONUNBUFFERED", "1")
        process.setProcessEnvironment(env)
        process.setProcessChannelMode(QProcess.ForwardedChannels)
        process.setWorkingDirectory(self._project_root())
        process.errorOccurred.connect(self._on_process_error)
        process.finished.connect(self._on_process_finished)
        process.started.connect(self._on_process_started)

        self._is_ready = False
        self._is_spawning = True
        self._process = process
        # start() returns immediately; the OS notifies us via the `started`
        # / `errorOccurred` signals when the child is actually up (or fails).
        process.start()
        return True

    def _on_process_started(self) -> None:
        self._is_spawning = False

    def shutdown(self, wait_ms: int = 1500) -> None:
        self._shutting_down = True
        if self._socket is not None and self._socket.state() == QLocalSocket.ConnectedState:
            try:
                self._socket.write(ipc.encode_message({"type": ipc.MSG_SHUTDOWN}))
                self._socket.flush()
            except Exception:
                pass
        if self._process is not None and self._process.state() != QProcess.NotRunning:
            if not self._process.waitForFinished(max(0, wait_ms)):
                self._process.terminate()
                if not self._process.waitForFinished(800):
                    self._process.kill()
                    self._process.waitForFinished(400)
        if self._server.isListening():
            self._server.close()

    # ----- send helpers ----------------------------------------------------

    def send_start_preview(self, generation: int, params: dict) -> bool:
        return self._send({
            "type": ipc.MSG_START_PREVIEW,
            "generation": int(generation),
            "params": params,
        })

    def send_cancel(self) -> bool:
        return self._send({"type": ipc.MSG_CANCEL})

    def send_set_slice(self, z: int) -> bool:
        return self._send({"type": ipc.MSG_SET_SLICE, "z": int(z)})

    def send_reset_view(self) -> bool:
        return self._send({"type": ipc.MSG_RESET_VIEW})

    def send_clear(self) -> bool:
        return self._send({"type": ipc.MSG_CLEAR})

    def show_child_window(self) -> bool:
        return self._send({"type": ipc.MSG_SHOW_WINDOW})

    def hide_child_window(self) -> bool:
        return self._send({"type": ipc.MSG_HIDE_WINDOW})

    # ----- internals -------------------------------------------------------

    def _send(self, message: dict) -> bool:
        if self._socket is None or self._socket.state() != QLocalSocket.ConnectedState:
            self._pending_messages.append(message)
            self.ensure_started()
            return False
        try:
            self._socket.write(ipc.encode_message(message))
            self._socket.flush()
            return True
        except Exception:
            self._pending_messages.append(message)
            return False

    def _flush_pending(self) -> None:
        if self._socket is None or self._socket.state() != QLocalSocket.ConnectedState:
            return
        pending = self._pending_messages
        self._pending_messages = []
        for msg in pending:
            try:
                self._socket.write(ipc.encode_message(msg))
            except Exception:
                self._pending_messages.append(msg)
        self._socket.flush()

    def _on_new_connection(self) -> None:
        socket = self._server.nextPendingConnection()
        if socket is None:
            return
        if self._socket is not None:
            try:
                self._socket.disconnectFromServer()
            except Exception:
                pass
            self._socket.deleteLater()
        self._socket = socket
        self._reader.clear()
        socket.readyRead.connect(self._on_ready_read)
        socket.disconnected.connect(self._on_socket_disconnected)

    def _on_ready_read(self) -> None:
        if self._socket is None:
            return
        chunk = bytes(self._socket.readAll())
        for msg in self._reader.feed(chunk):
            self._dispatch(msg)

    def _dispatch(self, msg: dict) -> None:
        mtype = msg.get("type")
        if mtype == ipc.MSG_READY:
            self._is_ready = True
            self._flush_pending()
            self.ready.emit()
        elif mtype == ipc.MSG_STAGE:
            self.stage.emit(str(msg.get("text", "")), int(msg.get("generation", 0)))
        elif mtype == ipc.MSG_STARTED:
            self.started.emit(int(msg.get("generation", 0)))
        elif mtype == ipc.MSG_FINISHED:
            self.finished.emit(int(msg.get("generation", 0)), str(msg.get("text", "")))
        elif mtype == ipc.MSG_FAILED:
            self.failed.emit(int(msg.get("generation", 0)), str(msg.get("text", "")))
        elif mtype == ipc.MSG_WINDOW_CLOSED:
            self.window_closed.emit()
        elif mtype == ipc.MSG_BYE:
            pass

    def _on_socket_disconnected(self) -> None:
        self._is_ready = False
        if self._socket is not None:
            self._socket.deleteLater()
            self._socket = None
        if not self._shutting_down:
            self.disconnected.emit()

    def _on_process_error(self, err) -> None:
        msg = self._process.errorString() if self._process else "unknown error"
        # FailedToStart is the async equivalent of waitForStarted() returning
        # False — we never even got off the ground. Clear state so a future
        # ensure_started() can try again.
        if err == QProcess.FailedToStart:
            self._is_spawning = False
            self._is_ready = False
            if self._process is not None:
                self._process.deleteLater()
                self._process = None
            # Drop any messages that were queued for a child that will never
            # exist — the caller will retry via ensure_started() if it cares.
            self._pending_messages.clear()
        self.spawn_failed.emit(f"Child process error: {msg}")

    def _on_process_finished(self, exit_code: int, exit_status) -> None:
        del exit_status, exit_code
        self._is_ready = False
        self._is_spawning = False
        if not self._shutting_down:
            self.disconnected.emit()
        if self._process is not None:
            self._process.deleteLater()
            self._process = None

    @staticmethod
    def _project_root() -> str:
        # services/preview_process_client.py → up two levels to repo root.
        here = os.path.dirname(os.path.abspath(__file__))
        return os.path.abspath(os.path.join(here, "..", ".."))
