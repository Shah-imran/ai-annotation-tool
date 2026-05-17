"""
Entrypoint for the 3D-preview child process.

Usage:
    python -m annotation_tool.preview_process --socket <pipe-name>

The parent app creates a QLocalServer with that name, then spawns this module.
"""
from __future__ import annotations

import argparse
import sys

from PyQt5.QtWidgets import QApplication

from .child_window import ChildPreviewWindow
from .ipc_endpoint import ChildIpcEndpoint


def _parse_argv(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="annotation_tool.preview_process")
    parser.add_argument("--socket", required=True, help="QLocalServer socket name to connect to")
    parser.add_argument("--title", default="3D Volume Preview", help="Window title")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_argv(argv if argv is not None else sys.argv[1:])

    app = QApplication(sys.argv)
    app.setApplicationName("AnnotationTool3DPreview")
    app.setQuitOnLastWindowClosed(False)

    window = ChildPreviewWindow(title=args.title)
    endpoint = ChildIpcEndpoint(window=window, socket_name=args.socket)
    endpoint.connect_to_parent()

    # Stay hidden until the parent sends show_window after the preview build
    # finishes. Prewarm only loads VTK/PyVista in the background.
    window.hide()

    return app.exec_()


if __name__ == "__main__":
    sys.exit(main())
