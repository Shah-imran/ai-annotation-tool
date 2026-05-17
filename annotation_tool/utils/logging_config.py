"""
Central logging setup for the annotation tool.

Call ``setup_logging()`` once at application startup (see ``annotation_tool.main``).
Modules should use::

    from annotation_tool.utils.logging_config import get_logger
    logger = get_logger(__name__)
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

_CONFIGURED = False
_LOG_DIR_NAME = "logs"
_LOG_FILE_NAME = "annotation_tool.log"


def setup_logging(
    level: int = logging.INFO,
    log_to_file: bool = True,
    log_dir: Optional[Path] = None,
) -> None:
    """Configure root logging once for the whole application."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    root = logging.getLogger()
    root.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console = logging.StreamHandler(sys.stderr)
    console.setLevel(level)
    console.setFormatter(formatter)
    root.addHandler(console)

    if log_to_file:
        try:
            base = log_dir or (Path.cwd() / _LOG_DIR_NAME)
            base.mkdir(parents=True, exist_ok=True)
            log_path = base / _LOG_FILE_NAME
            file_handler = RotatingFileHandler(
                log_path,
                maxBytes=2_000_000,
                backupCount=3,
                encoding="utf-8",
            )
            file_handler.setLevel(level)
            file_handler.setFormatter(formatter)
            root.addHandler(file_handler)
            logging.getLogger(__name__).info("Logging to %s", log_path)
        except OSError as exc:
            logging.getLogger(__name__).warning(
                "Could not create log file handler: %s", exc
            )

    # Quiet noisy third-party loggers unless debugging.
    for noisy in ("PIL", "matplotlib", "vtk", "paraview"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a module logger (setup_logging should have run already)."""
    return logging.getLogger(name)
