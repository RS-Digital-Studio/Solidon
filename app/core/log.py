"""Lokales Protokoll (Bauplan §33.2).

Eine rotierende Datei im Nutzerverzeichnis, sonst nichts. Die Linie zur
verbotenen Telemetrie ist scharf: das Protokoll verlässt diesen Rechner nur,
wenn der Nutzer es selbst an eine Rückmeldung hängt und sie absendet
(:mod:`app.core.support`). Kein Zeitgeber und kein Fehlerpfad schickt es.

Stufen: ``debug`` nur mit gesetztem Schalter, ``info`` für Op-Läufe und
Dateizugriffe, ``warning`` für Rückfallstufen und Befunde, ``error`` für
Ausnahmen.

Keine Geometrie im Protokoll — nur Kennzahlen.
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
    """Wo die Protokolldatei liegt. Liest der Fehlerbericht, und sonst
    niemand — von allein verlässt die Datei den Rechner nie (§33.2)."""
    return (directory or user_log_dir()) / _LOG_FILE


class _OpFormatter(logging.Formatter):
    """Hängt die Op-Nummer an, wo eine bekannt ist — der Anker fürs spätere
    Lesen."""

    def format(self, record: logging.LogRecord) -> str:
        text = super().format(record)
        op_id = getattr(record, "op", None)
        return f"{text}  [op {op_id}]" if op_id is not None else text


def configure(debug: bool = False, directory: Path | None = None, to_console: bool = True) -> Path:
    """Richtet das rotierende Dateiprotokoll einmal ein und gibt den Pfad zurück."""
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
    """Logger für ein Modul, immer unterhalb der Anwendungswurzel."""
    if name == ROOT_LOGGER or name.startswith(f"{ROOT_LOGGER}."):
        return logging.getLogger(name)
    return logging.getLogger(f"{ROOT_LOGGER}.{name}")
