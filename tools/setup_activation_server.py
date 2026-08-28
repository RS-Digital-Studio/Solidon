"""Richtet die privaten Dateien des Aktivierungsdienstes sicher ein.

Der private 32-Byte-Startwert wird als Hexdatei geschrieben und niemals
ausgegeben. Die Datei gehört anschließend außerhalb des Web-Stammverzeichnisses
auf den Server. Die SQLite-Datei wird mit derselben festen Struktur angelegt,
die der PHP-Dienst erwartet. Ziele innerhalb des Repositorys werden abgelehnt,
damit ein späterer Website-Abgleich keine privaten Daten veröffentlichen kann.

Beispiel::

    python tools/setup_activation_server.py --private D:\\Geheim\\activation.seed

Ohne ``--replace`` wird eine vorhandene Datei niemals überschrieben. Ein
versehentlich neues Paar würde alle bereits ausgestellten Geräte-Zertifikate
ungültig machen.
"""

from __future__ import annotations

import argparse
import contextlib
import secrets
import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.activation import ed25519

ROOT = Path(__file__).resolve().parent.parent


def _external_target(parser: argparse.ArgumentParser, target: Path) -> Path:
    """Löst ein Ziel auf und hält private Daten aus dem Arbeitsbaum heraus."""
    resolved = target.expanduser().resolve()
    try:
        resolved.relative_to(ROOT)
    except ValueError:
        return resolved
    parser.error(
        f"{resolved} liegt im Repository. Aktivierungsgeheimnisse und "
        "-datenbanken müssen außerhalb davon liegen"
    )


def _initialise_database(target: Path) -> None:
    """Legt die feste Serverstruktur an, ohne bestehende Daten zu löschen."""
    target.parent.mkdir(parents=True, exist_ok=True)
    with contextlib.closing(sqlite3.connect(target)) as database:
        database.executescript(
            """
            CREATE TABLE IF NOT EXISTS licences (
                digest TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS activations (
                id TEXT PRIMARY KEY,
                licence_digest TEXT NOT NULL,
                device_public TEXT NOT NULL,
                device_name TEXT NOT NULL,
                activated_on TEXT NOT NULL,
                deactivated_at TEXT NULL,
                FOREIGN KEY(licence_digest) REFERENCES licences(digest)
            );
            CREATE UNIQUE INDEX IF NOT EXISTS one_active_device
                ON activations(licence_digest) WHERE deactivated_at IS NULL;
            CREATE TABLE IF NOT EXISTS activation_attempts (
                licence_digest TEXT NOT NULL,
                day TEXT NOT NULL,
                attempts INTEGER NOT NULL,
                PRIMARY KEY(licence_digest, day)
            );
            """
        )
        database.commit()
    with contextlib.suppress(OSError):
        target.chmod(0o600)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private", type=Path, help="Startwert außerhalb des Repositorys")
    parser.add_argument("--database", type=Path, help="SQLite-Datei außerhalb des Repositorys")
    parser.add_argument(
        "--replace",
        action="store_true",
        help="vorhandenes Paar bewusst ersetzen (bestehende Aktivierungen werden ungültig)",
    )
    arguments = parser.parse_args(argv)
    if arguments.private is None and arguments.database is None:
        parser.error("mindestens --private oder --database angeben")
    if arguments.replace and arguments.private is None:
        parser.error("--replace gilt nur zusammen mit --private")

    private = _external_target(parser, arguments.private) if arguments.private is not None else None
    database = (
        _external_target(parser, arguments.database) if arguments.database is not None else None
    )
    if private is not None and private.exists() and not arguments.replace:
        parser.error(f"{private} besteht bereits; zum bewussten Ersetzen --replace angeben")

    if private is not None:
        private.parent.mkdir(parents=True, exist_ok=True)
        seed = secrets.token_bytes(ed25519.POINT_BYTES)
        private.write_text(seed.hex() + "\n", encoding="ascii")
        with contextlib.suppress(OSError):
            private.chmod(0o600)
        print("Privater Aktivierungsschlüssel wurde geschrieben (Inhalt wird nicht ausgegeben):")
        print(f"  {private}")
        print("Öffentlicher Aktivierungsschlüssel für Anwendung und Dienst:")
        print(f"  {ed25519.public_key(seed).hex()}")
    if database is not None:
        _initialise_database(database)
        print("Aktivierungsdatenbank ist eingerichtet:")
        print(f"  {database}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
