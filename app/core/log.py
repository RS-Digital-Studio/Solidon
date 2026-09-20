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

import faulthandler
import logging
import os
import re
import secrets
import sys
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from types import TracebackType
from typing import Final
from urllib.parse import urlsplit, urlunsplit

from app.branding import APP_VERSION
from app.core.paths import ensure_dir, lock_file, user_log_dir

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
_CRASH_PATTERN = re.compile(r"crash-\d{8}T\d{6}-[\w.+-]+-\d+-[0-9a-f]{16}\.log")
_CRASH_KEEP = 5
_capture_guard = threading.RLock()
_installed = False


@dataclass(frozen=True, slots=True)
class _CrashCapture:
    """Rohe Deskriptoren bleiben auch beim Abbau von Python bis zum Prozessende offen."""

    path: Path
    descriptor: int
    lease: int


_capture: _CrashCapture | None = None


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


def exception_text(error: BaseException, traceback: TracebackType | None = None) -> str:
    """Redigierter Ausnahmestapel ohne Quellzeilen, Argumente oder lokale Variablen."""
    lines: list[str] = []
    seen: set[int] = set()
    remaining = _MAX_BYTES

    def add(line: str) -> None:
        nonlocal remaining
        if remaining > 0:
            encoded = line.encode("utf-8", errors="replace")[:remaining]
            part = encoded.decode("utf-8", errors="ignore")
            lines.append(part)
            remaining -= len(encoded) + 1

    def append(problem: BaseException, stack: TracebackType | None, depth: int = 0) -> None:
        if remaining <= 0:
            return
        if id(problem) in seen or len(seen) >= 100 or depth >= 20:
            add("…")
            return
        seen.add(id(problem))
        previous = problem.__cause__
        if previous is None and not problem.__suppress_context__:
            previous = problem.__context__
        if previous is not None:
            append(previous, previous.__traceback__, depth + 1)
            add("---")
        add("Traceback (most recent call last):")
        count = 0
        while stack is not None and count < 100 and remaining > 0:
            code = stack.tb_frame.f_code
            add(
                f'  File "{redact(code.co_filename, limit=500)}", '
                f"line {stack.tb_lineno}, in {redact(code.co_name, limit=500)}"
            )
            stack = stack.tb_next
            count += 1
        if stack is not None:
            add("…")
        try:
            message = redact(problem)
        except Exception:
            message = "<Ausnahmetext nicht lesbar>"
        add(f"{redact(type(problem).__name__)}: {message}")
        if isinstance(problem, BaseExceptionGroup):
            for child in problem.exceptions[:20]:
                append(child, child.__traceback__, depth + 1)
            if len(problem.exceptions) > 20:
                add("…")

    append(error, traceback if traceback is not None else error.__traceback__)
    return "\n".join(lines)


def crash_paths(directory: Path | None = None) -> tuple[Path, ...]:
    """Nur eigene Absturzdateien; leere Dateien allein belegen keinen Absturz."""
    folder = directory or user_log_dir()
    return tuple(
        sorted(
            (
                path
                for path in folder.glob("crash-*.log")
                if _CRASH_PATTERN.fullmatch(path.name) and not path.is_symlink()
            ),
            reverse=True,
        )
    )


def _trim_automatic_reports(folder: Path, keep: int) -> None:
    """Räumt nur erzeugte Diagnoseanhänge auf; fremde Dateien bleiben erhalten."""
    if folder.is_symlink():
        return
    reports = sorted(
        folder.glob("bericht-*"), key=lambda path: path.stat().st_mtime_ns, reverse=True
    )
    for report in reports[keep:]:
        if report.is_symlink() or not report.is_dir():
            continue
        for name in ("bericht.txt", "protokoll.txt", "absturzprotokoll.txt"):
            (report / name).unlink(missing_ok=True)
        if not any(report.iterdir()):
            report.rmdir()
    if folder.is_dir() and not any(folder.iterdir()):
        folder.rmdir()


def _prune_crashes(folder: Path) -> None:
    """Behält fünf beendete Läufe; die Betriebssystemsperre schützt lebende Prozesse."""
    kept = 0
    for path in crash_paths(folder):
        lease = path.with_suffix(".lock")
        try:
            # Eigene Dateinamen werden nie wiederverwendet. Solange diese
            # Sperre gehalten wird, kann kein anderer Aufräumer löschen.
            with lease.open("a+b") as stream:
                try:
                    lock_file(stream)
                except OSError:
                    continue
                size = path.stat().st_size
                if size and kept < _CRASH_KEEP:
                    kept += 1
                    continue
                path.unlink()
                _trim_automatic_reports(path.with_suffix(""), 0)
            lease.unlink(missing_ok=True)
        except FileNotFoundError:
            continue
        except OSError as problem:
            get_logger(__name__).warning("crash log could not be removed: %s", problem)


def _diagnostic_stderr(text: str) -> None:
    """Auch ein GUI-Prozess ohne stderr darf den ursprünglichen Fehler behalten."""
    stream = sys.stderr or sys.__stderr__
    if stream is None:
        return
    try:
        stream.write(text + "\n")
        stream.flush()
    except Exception:
        # Ohne beschreibbaren Standardkanal bleibt der bereits geschriebene
        # Absturzdeskriptor; ein weiterer Schreibversuch hätte dasselbe Ziel.
        return


def _record_unhandled(error: BaseException, traceback: TracebackType | None, context: str) -> None:
    """Sichert zuerst den Fehler; der komfortablere Bericht darf daran nichts ändern."""
    text = exception_text(error, traceback)
    with _capture_guard:
        current = _capture
        if current is not None:
            try:
                data = (f"\n{datetime.now(UTC).isoformat()} {context}\n{text}\n").encode(
                    "utf-8", errors="replace"
                )
                data = data[-_MAX_BYTES:].decode("utf-8", errors="ignore").encode("utf-8")
                if os.fstat(current.descriptor).st_size + len(data) > _MAX_BYTES:
                    os.ftruncate(current.descriptor, 0)
                    os.lseek(current.descriptor, 0, os.SEEK_SET)
                os.write(current.descriptor, data)
            except OSError as problem:
                _diagnostic_stderr(f"{text}\n{redact(problem)}")
        _diagnostic_stderr(text)
        try:
            # Erst im Fehlerfall importieren: der frühe Startweg benötigt
            # weder Geometrie, Qt noch die Berichts- und Sprachinfrastruktur.
            from app.core import report

            record = report.exception_report(error, traceback=traceback, context=context)
            folder = current.path.with_suffix("") if current is not None else None
            written = report.write(record, directory=folder)
            from app.i18n import tr

            _diagnostic_stderr(f"{tr('Der Fehlerbericht liegt hier')}: {written}")
            if folder is not None:
                _trim_automatic_reports(folder, _CRASH_KEEP)
        except Exception as problem:
            from app.branding import SUPPORT_ADDRESS

            _diagnostic_stderr(f"{text}\n{exception_text(problem)}\n{SUPPORT_ADDRESS}")


def _unhandled_exception(
    kind: type[BaseException], error: BaseException, traceback: TracebackType | None
) -> None:
    """Ein unbehandelter Hauptfadenfehler landet im selben lokalen Bericht wie die CLI."""
    if issubclass(kind, (KeyboardInterrupt, SystemExit)):
        sys.__excepthook__(kind, error, traceback)
        return
    _record_unhandled(error, traceback, "Python")


def _unhandled_thread(args: threading.ExceptHookArgs) -> None:
    """Behält weder den Faden noch dessen Ausnahme nach dem Schreiben zurück."""
    if args.exc_value is not None and not issubclass(args.exc_type, SystemExit):
        _record_unhandled(args.exc_value, args.exc_traceback, "Thread")


def install_crash_logging(directory: Path | None = None) -> Path | None:
    """Installiert den gemeinsamen Prozessschutz einmal, ausdrücklich beim Start.

    Die zwei rohen, nicht vererbbaren Deskriptoren schließen ausschließlich
    mit dem Prozess. Weder Qt-Ende, Logger-Rotation noch Python-Finalisierung
    dürfen den von faulthandler gespeicherten Deskriptor neu vergeben.
    """
    global _capture, _installed
    with _capture_guard:
        if _installed:
            return _capture.path if _capture is not None else None
        descriptor: int | None = None
        lease_descriptor: int | None = None
        path: Path | None = None
        handler_attempted = False
        try:
            folder = ensure_dir(directory or user_log_dir())
            _prune_crashes(folder)
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S")
            path = folder / f"crash-{stamp}-{APP_VERSION}-{os.getpid()}-{secrets.token_hex(8)}.log"
            # Erst die Sperre, dann die sichtbare Protokolldatei: Ein parallel
            # startendes Fenster kann die neue, noch leere Datei nicht löschen.
            lease_descriptor = os.open(
                path.with_suffix(".lock"), os.O_RDWR | os.O_CREAT | os.O_EXCL
            )
            with os.fdopen(lease_descriptor, "r+b", closefd=False) as stream:
                lock_file(stream)
            descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_APPEND, 0o600)
            capture = _CrashCapture(path, descriptor, lease_descriptor)
            handler_attempted = True
            faulthandler.enable(file=descriptor, all_threads=True, c_stack=False)
            _capture = capture
        except Exception as problem:
            # Auch eine teilweise Einrichtung darf keinen aktiven Handler
            # mit einem anschließend neu vergebenen Deskriptor zurücklassen.
            if handler_attempted:
                faulthandler.disable()
            for opened in (descriptor, lease_descriptor):
                if opened is not None:
                    os.close(opened)
            if path is not None:
                for created, candidate in (
                    (descriptor, path),
                    (lease_descriptor, path.with_suffix(".lock")),
                ):
                    if created is not None:
                        try:
                            candidate.unlink(missing_ok=True)
                        except OSError as denied:
                            _diagnostic_stderr(exception_text(denied))
            _diagnostic_stderr(f"Absturzprotokoll: {exception_text(problem)}")
        sys.excepthook = _unhandled_exception
        threading.excepthook = _unhandled_thread
        _installed = True
        return _capture.path if _capture is not None else None


def log_path(directory: Path | None = None) -> Path:
    """Wo die Protokolldatei liegt. Liest der Fehlerbericht, und sonst
    niemand — von allein verlässt die Datei den Rechner nie (§33.2)."""
    return (directory or user_log_dir()) / _LOG_FILE


class _OpFormatter(logging.Formatter):
    """Hängt die Op-Nummer an, wo eine bekannt ist — der Anker fürs spätere
    Lesen."""

    def formatMessage(self, record: logging.LogRecord) -> str:  # noqa: N802 - logging gibt den Namen
        """Redigiert die **Meldung** — den Stapel hängt ``format`` unberührt an.

        Redigiert wurde bis hierher der ganze fertige Eintrag, und ``redact``
        macht aus jedem Zeilenumbruch ein ``\\n`` und kappt bei 8192 Zeichen:
        Ein Traceback kam damit einzeilig und abgeschnitten im Protokoll an —
        und genau den liest, wer einen Fehlerbericht bekommt (§33.2). Die
        Meldung bleibt redigiert; sie ist die Stelle, an der ein fremder Text
        hereinkommt, ein Stapel unseres eigenen Codes ist es nicht.
        """
        text = super().formatMessage(record)
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
