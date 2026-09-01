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
import re
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Final
from urllib.parse import urlsplit, urlunsplit

from app.core.paths import ensure_dir, user_log_dir

ROOT_LOGGER: Final = "app"
_LOG_FILE: Final = "app.log"
_MAX_BYTES: Final = 2 * 1024 * 1024
_BACKUP_COUNT: Final = 5
_MAX_MESSAGE_CHARACTERS: Final = 8192
_URL = re.compile(r"(?i)\bhttps?://[^\s<>]+")
_SECRET_ASSIGNMENT = re.compile(
    r"""(?ix)
    (?P<prefix>
        ["']?
        (?:authorization|proxy-authorization|x-api-key|api[-_]?key|
           x-solidon-operator-token|access[-_]?token|password|passwd|secret|token)
        ["']?\s*[:=]\s*
    )
    (?:
        ["'][^"']*["']
        |
        (?:bearer\s+)?[^\s,;}\]]+
    )
    """
)
_BEARER = re.compile(r"(?i)\bbearer\s+[a-z0-9._~+/=-]+")
_KNOWN_TOKEN = re.compile(r"(?i)\b(?:sk|rk|pk)-[a-z0-9_-]{12,}\b")

_configured = False


def redact_url(url: str) -> str:
    """Eine URL ohne Benutzerinfo, Abfrage und Fragment.

    Der Pfad bleibt als technische Auskunft erhalten. Ist schon die
    Autorität unlesbar, wird nicht geraten, welcher Teil davon ein
    Zugangswert sein könnte.
    """
    try:
        parts = urlsplit(url)
        host = parts.hostname
        port = parts.port
    except ValueError:
        return "<redigierte URL>"
    if parts.scheme.lower() not in {"http", "https"} or not host:
        return "<redigierte URL>"
    display_host = f"[{host}]" if ":" in host else host
    netloc = f"{display_host}:{port}" if port is not None else display_host
    return urlunsplit((parts.scheme.lower(), netloc, parts.path, "", ""))


def redact(value: object, *, limit: int = _MAX_MESSAGE_CHARACTERS) -> str:
    """Entfernt Zugangsdaten und URL-Geheimnisse aus Diagnoseausgaben.

    Der Deckel und die sichtbare Darstellung von Steuerzeichen gelten auch
    für fremde Servertexte. Damit kann ein Antwortkörper weder neue
    Protokollzeilen einschleusen noch das lokale Protokoll mit Rohdaten
    füllen.
    """
    if limit < 1:
        raise ValueError("limit must be positive")
    text = str(value)

    def replace_url(match: re.Match[str]) -> str:
        raw = match.group(0)
        trailing = ""
        while raw and raw[-1] in ".,;:!?)]}":
            trailing = raw[-1] + trailing
            raw = raw[:-1]
        return redact_url(raw) + trailing

    text = _URL.sub(replace_url, text)
    text = _SECRET_ASSIGNMENT.sub(lambda match: f"{match.group('prefix')}<redigiert>", text)
    text = _BEARER.sub("Bearer <redigiert>", text)
    text = _KNOWN_TOKEN.sub("<redigiert>", text)
    text = "".join(
        character
        if ord(character) >= 32 and ord(character) != 127
        else {"\n": r"\n", "\r": r"\r", "\t": r"\t"}.get(character, "?")
        for character in text
    )
    if len(text) <= limit:
        return text
    return text[: max(1, limit - 1)].rstrip() + "…"


def redact_external(value: object, *, limit: int = 500) -> str:
    """Ein begrenzter, redigierter Ausschnitt aus einer fremden Antwort."""
    return redact(value, limit=limit)


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
        if op_id is not None:
            text = f"{text}  [op {redact(op_id, limit=80)}]"
        return redact(text)


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
