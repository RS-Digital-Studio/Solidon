"""Local logging (Bauplan §33.2).

A rotating file in the user directory, nothing else. The line to the forbidden
telemetry is sharp: the log leaves this machine only when the user attaches it to
an error report themselves.

Levels: ``debug`` only when the switch is set, ``info`` for op runs and file
access, ``warning`` for fallback stages and findings, ``error`` for exceptions.

No geometry in the log — metrics only.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Final

from app.core.paths import ensure_dir, user_log_dir

ROOT_LOGGER: Final = "app"
_LOG_FILE: Final = "app.log"
_MAX_BYTES: Final = 2 * 1024 * 1024
_BACKUP_COUNT: Final = 5

_configured = False


def log_path(directory: Path | None = None) -> Path:
    """Where the log file is. Read by the error report, and by nothing else —
    the file never leaves the machine on its own (§33.2)."""
    return (directory or user_log_dir()) / _LOG_FILE


class _OpFormatter(logging.Formatter):
    """Appends the op number where one is known — the anchor for later reading."""

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        op_id = getattr(record, "op", None)
        return f"{text}  [op {op_id}]" if op_id is not None else text


def configure(debug: bool = False, directory: Path | None = None, to_console: bool = True) -> Path:
    """Set up the rotating file log once and return the file path."""
    global _configured
    target = ensure_dir(directory or user_log_dir()) / _LOG_FILE
    logger = logging.getLogger(ROOT_LOGGER)
    logger.setLevel(logging.DEBUG if debug else logging.INFO)

    if _configured:
        return target

    formatter = _OpFormatter(
        fmt="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    file_handler = RotatingFileHandler(
        target, maxBytes=_MAX_BYTES, backupCount=_BACKUP_COUNT, encoding="utf-8"
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    if to_console:
        console = logging.StreamHandler()
        console.setFormatter(formatter)
        logger.addHandler(console)

    logger.propagate = False
    _configured = True
    return target


def get_logger(name: str) -> logging.Logger:
    """Logger for a module, always below the application root."""
    if name == ROOT_LOGGER or name.startswith(f"{ROOT_LOGGER}."):
        return logging.getLogger(name)
    return logging.getLogger(f"{ROOT_LOGGER}.{name}")
