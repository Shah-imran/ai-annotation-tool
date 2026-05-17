"""
Inter-process protocol for the 3D-preview child process.

Wire format: newline-delimited JSON.
- Each message is a single JSON object terminated by a '\\n'.
- All payloads must be JSON-serializable (no numpy arrays, no PyVista data).
- Slice data and labels are referenced by file path; the child reads them itself.

Message dict shape: {"type": <MSG_TYPE>, ...fields...}.

Parent → Child:
  HELLO         introductory ping (also used to wake the child)
  START_PREVIEW kick off a new preview build (generation, params)
  CANCEL        cancel current build (matches generation)
  SET_SLICE     update the highlighted Z slice in 3D
  RESET_VIEW    reset the 3D camera to default orientation
  CLEAR         clear the 3D scene
  SHOW_WINDOW   show the child window
  HIDE_WINDOW   hide the child window
  SET_PREVIEW_UI  brightness %, default export folders for snapshot/mesh
  SHUTDOWN      ask child to exit cleanly

Child → Parent:
  READY         child is initialized and ready
  STAGE         status text update (matches generation)
  STARTED       build started (generation echoed)
  FINISHED      build finished; carries final status text + summary
  FAILED        build failed; carries error message
  WINDOW_CLOSED user closed the 3D window
  PREVIEW_UI_CHANGED  brightness % and/or export folder defaults changed
  LOG           debug/log line (string)
  BYE           child is exiting
"""
from __future__ import annotations

import json
from typing import Optional


MSG_HELLO = "hello"
MSG_START_PREVIEW = "start_preview"
MSG_CANCEL = "cancel"
MSG_SET_SLICE = "set_slice"
MSG_RESET_VIEW = "reset_view"
MSG_CLEAR = "clear"
MSG_SHOW_WINDOW = "show_window"
MSG_HIDE_WINDOW = "hide_window"
MSG_SET_PREVIEW_UI = "set_preview_ui"
MSG_SHUTDOWN = "shutdown"

MSG_READY = "ready"
MSG_STAGE = "stage"
MSG_STARTED = "started"
MSG_FINISHED = "finished"
MSG_FAILED = "failed"
MSG_WINDOW_CLOSED = "window_closed"
MSG_PREVIEW_UI_CHANGED = "preview_ui_changed"
MSG_LOG = "log"
MSG_BYE = "bye"


def encode_message(message: dict) -> bytes:
    """Serialize a message dict to a single newline-delimited JSON line (UTF-8)."""
    return (json.dumps(message, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")


class JsonLineReader:
    """Stateful buffer that splits a byte stream into JSON-line messages."""

    def __init__(self) -> None:
        self._buf = bytearray()

    def feed(self, data: bytes) -> list[dict]:
        """Append bytes and return any fully-buffered JSON messages."""
        if not data:
            return []
        self._buf.extend(data)
        out: list[dict] = []
        while True:
            idx = self._buf.find(b"\n")
            if idx < 0:
                break
            line = bytes(self._buf[:idx])
            del self._buf[: idx + 1]
            if not line.strip():
                continue
            try:
                msg = json.loads(line.decode("utf-8"))
            except Exception as exc:
                msg = {"type": MSG_LOG, "level": "error", "text": f"Bad IPC message: {exc!r}"}
            if isinstance(msg, dict):
                out.append(msg)
        return out

    def clear(self) -> None:
        self._buf.clear()


def make_preview_inputs(
    *,
    slice_paths: list[str],
    spacing_xyz: tuple,
    mode: str,
    window_center: float,
    window_width: float,
    use_window_level: bool,
    include_mask: bool,
    preview_level: int,
    native_full_volume: bool,
    source_z_indices: list[int],
    full_shape_zyx: tuple,
    label_path: str,
    label_shape: tuple,
    stride_zyx: Optional[tuple],
    current_z: int,
    # Point-cloud-only knobs (child substitutes defaults if missing).
    point_size: float = 3.0,
    point_threshold_override: Optional[int] = None,
    # Isosurface-only knobs.
    iso_color: str = "#dcdcdc",
) -> dict:
    """Build a JSON-safe payload describing a preview build."""
    return {
        "slice_paths": list(slice_paths),
        "spacing_xyz": [float(v) for v in spacing_xyz],
        "mode": str(mode),
        "window_center": float(window_center),
        "window_width": float(window_width),
        "use_window_level": bool(use_window_level),
        "include_mask": bool(include_mask),
        "preview_level": int(preview_level),
        "native_full_volume": bool(native_full_volume),
        "source_z_indices": list(int(i) for i in source_z_indices),
        "full_shape_zyx": [int(v) for v in full_shape_zyx],
        "label_path": str(label_path),
        "label_shape": [int(v) for v in label_shape],
        "stride_zyx": list(int(v) for v in stride_zyx) if stride_zyx is not None else None,
        "current_z": int(current_z),
        "point_size": float(point_size),
        "point_threshold_override": (
            int(point_threshold_override) if point_threshold_override is not None else None
        ),
        "iso_color": str(iso_color or "#dcdcdc"),
    }
