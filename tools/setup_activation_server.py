"""Richtet die privaten Dateien des Aktivierungsdienstes sicher ein.

Der private 32-Byte-Startwert wird als Hexdatei geschrieben und niemals
ausgegeben. Die Datei gehört anschließend außerhalb des Web-Stammverzeichnisses
auf den Server. Die SQLite-Datei wird mit derselben festen Struktur angelegt,
die der PHP-Dienst erwartet. Ziele innerhalb des Repositorys werden abgelehnt,
damit ein späterer Website-Abgleich keine privaten Daten veröffentlichen kann.
Der optionale Ratenstartwert ist unabhängig vom Signaturschlüssel, wird mit
privaten Rechten exklusiv angelegt und niemals ersetzt.

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
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.activation import ed25519
from tools.make_stats_access import prepare_private_directory, write_private

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
    prepare_private_directory(target.parent)
    if target.exists():
        target.chmod(0o600)
    else:
        write_private(target, "")
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
            CREATE TABLE IF NOT EXISTS operator_events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                occurred_at TEXT NOT NULL,
                licence_digest TEXT NOT NULL,
                action TEXT NOT NULL,
                reason TEXT NOT NULL,
                changed INTEGER NOT NULL
            );
            """
        )
        database.commit()


def _write_secret(target: Path, text: str, *, replace_existing: bool = False) -> None:
    """Ersetzt einen freigegebenen Bestand erst nach vollständigem privaten Schreiben."""
    prepare_private_directory(target.parent)
    if not replace_existing:
        write_private(target, text)
        return
    with tempfile.TemporaryDirectory(prefix=f".{target.name}.", dir=target.parent) as directory:
        staged = Path(directory) / target.name
        write_private(staged, text)
        staged.replace(target)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private", type=Path, help="Startwert außerhalb des Repositorys")
    parser.add_argument("--database", type=Path, help="SQLite-Datei außerhalb des Repositorys")
    parser.add_argument(
        "--rate-key", type=Path, help="Getrennter Ratenstartwert außerhalb des Repositorys"
    )
    parser.add_argument(
        "--operator-token",
        type=Path,
        help="256-Bit-Zugang der privaten Support-Verwaltung außerhalb des Repositorys",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="vorhandenes Paar bewusst ersetzen (bestehende Aktivierungen werden ungültig)",
    )
    parser.add_argument(
        "--replace-operator-token",
        action="store_true",
        help="vorhandenen Betreiberzugang bewusst ersetzen",
    )
    arguments = parser.parse_args(argv)
    if (
        arguments.private is None
        and arguments.database is None
        and arguments.operator_token is None
        and arguments.rate_key is None
    ):
        parser.error("mindestens --private, --database, --operator-token oder --rate-key angeben")
    if arguments.replace and arguments.private is None:
        parser.error("--replace gilt nur zusammen mit --private")
    if arguments.replace_operator_token and arguments.operator_token is None:
        parser.error("--replace-operator-token gilt nur zusammen mit --operator-token")

    private = _external_target(parser, arguments.private) if arguments.private is not None else None
    database = (
        _external_target(parser, arguments.database) if arguments.database is not None else None
    )
    operator_token = (
        _external_target(parser, arguments.operator_token)
        if arguments.operator_token is not None
        else None
    )
    rate_key = (
        _external_target(parser, arguments.rate_key) if arguments.rate_key is not None else None
    )
    if rate_key is not None:
        if rate_key in (private, database, operator_token):
            parser.error("der Ratenstartwert braucht einen eigenen Pfad")
        if rate_key.exists():
            parser.error(f"{rate_key} besteht bereits; ein Ratenstartwert wird nicht ersetzt")
    if private is not None and private.exists() and not arguments.replace:
        parser.error(f"{private} besteht bereits; zum bewussten Ersetzen --replace angeben")
    if (
        operator_token is not None
        and operator_token.exists()
        and not arguments.replace_operator_token
    ):
        parser.error(
            f"{operator_token} besteht bereits; zum bewussten Ersetzen "
            "--replace-operator-token angeben"
        )

    try:
        if private is not None:
            seed = secrets.token_bytes(ed25519.POINT_BYTES)
            _write_secret(private, seed.hex() + "\n", replace_existing=arguments.replace)
            print(
                "Privater Aktivierungsschlüssel wurde geschrieben (Inhalt wird nicht ausgegeben):"
            )
            print(f"  {private}")
            print("Öffentlicher Aktivierungsschlüssel für Anwendung und Dienst:")
            print(f"  {ed25519.public_key(seed).hex()}")
        if database is not None:
            _initialise_database(database)
            print("Aktivierungsdatenbank ist eingerichtet:")
            print(f"  {database}")
        if operator_token is not None:
            _write_secret(
                operator_token,
                secrets.token_hex(32) + "\n",
                replace_existing=arguments.replace_operator_token,
            )
            print("Privater Betreiberzugang wurde geschrieben (Inhalt wird nicht ausgegeben):")
            print(f"  {operator_token}")
        if rate_key is not None:
            _write_secret(rate_key, secrets.token_hex(32))
            print("Privater Ratenstartwert wurde geschrieben (Inhalt wird nicht ausgegeben):")
            print(f"  {rate_key}")
    except OSError, sqlite3.Error:
        parser.error(
            "Die privaten Aktivierungsdateien ließen sich nicht sicher vorbereiten. "
            "Eigentümer, Verzeichnisrechte und freien Speicher am gewählten Ort prüfen."
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
