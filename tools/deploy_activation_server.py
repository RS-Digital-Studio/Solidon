"""Spielt den Aktivierungsdienst mit Sicherung auf den Produktivserver.

Private Dateien landen ausschließlich im benachbarten ``appdata`` und nie
unter ``httpdocs``. Eine vorhandene Produktivdatenbank wird samt ihrer
SQLite-WAL als konsistenter Ein-Datei-Schnappschuss gesichert, aber nie über
FTPS ersetzt. Ein abweichender privater Startwert wird ebenfalls nicht
automatisch ersetzt, weil damit bereits ausgestellte Geräte-Zertifikate ihre
Vertrauenskette verlören.
"""

from __future__ import annotations

import argparse
import contextlib
import ftplib
import io
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.activation import certificate, ed25519
from tools import upload_website
from tools.setup_activation_server import ROOT

PUBLIC_FILES = (
    Path("api/activation_common.php"),
    Path("api/activation.php"),
    Path("api/deactivation.php"),
    Path("api/operator.php"),
    Path("api/activation-health.php"),
    Path("offline-aktivierung.html"),
    Path("activation.js"),
    Path("style.css"),
    Path("eula.html"),
    Path("agb.html"),
    Path("widerruf.html"),
)
CORE_DATABASE_TABLES = frozenset({"licences", "activations", "activation_attempts"})
SUPPORT_DATABASE_TABLES = CORE_DATABASE_TABLES | {"operator_events"}


def _remote_parts(path: str) -> tuple[list[str], str]:
    """Teilt einen absoluten Serverpfad in Verzeichnis und Dateiname."""
    clean = path.strip("/")
    parts = clean.split("/")
    return parts[:-1], parts[-1]


def _remote_bytes(session: ftplib.FTP_TLS, path: str) -> bytes | None:
    """Liest eine vorhandene kleine Serverdatei; fehlend ist kein Fehler."""
    directories, name = _remote_parts(path)
    try:
        upload_website.ensure_dir(session, directories)
        names = set(session.nlst())
        if name not in names:
            return None
        target = io.BytesIO()
        session.retrbinary(f"RETR {name}", target.write)
        return target.getvalue()
    except ftplib.error_perm as problem:
        if str(problem).startswith("550"):
            return None
        raise


def _store_bytes(session: ftplib.FTP_TLS, path: str, payload: bytes) -> None:
    directories, name = _remote_parts(path)
    upload_website.ensure_dir(session, directories)
    session.storbinary(f"STOR {name}", io.BytesIO(payload))


def _seed_matches(path: Path) -> bool:
    """Prüft den privaten Teil, ohne ihn oder eine Ableitung davon auszugeben."""
    try:
        seed = bytes.fromhex(path.read_text(encoding="ascii").strip())
    except OSError, ValueError:
        return False
    return (
        len(seed) == ed25519.POINT_BYTES
        and ed25519.public_key(seed) == certificate.ACTIVATION_PUBLIC_KEY
    )


def _operator_token_is_valid(path: Path) -> bool:
    """Prüft Form und Entropielänge, ohne den Betreiberzugang auszugeben."""
    try:
        token = path.read_text(encoding="ascii").strip()
    except OSError, UnicodeError:
        return False
    return re.fullmatch(r"[0-9a-f]{64}", token) is not None


def _check_php() -> None:
    """Hält vor jedem Upload an, wenn eine Endpunktdatei nicht einmal lädt."""
    executable = shutil.which("php")
    if executable is None:
        raise SystemExit("PHP fehlt; die Endpunktdateien wurden nicht syntaktisch geprüft.")
    for relative in PUBLIC_FILES:
        if relative.suffix != ".php":
            continue
        result = subprocess.run(
            [executable, "-l", str(upload_website.LOCAL_ROOT / relative)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise SystemExit(result.stderr.strip() or result.stdout.strip())


def _database_snapshot(
    payload: bytes,
    wal_payload: bytes | None = None,
    *,
    require_operator_events: bool = False,
) -> bytes:
    """Erzeugt aus Hauptdatei und optionaler WAL eine geprüfte Ein-Datei-Sicherung."""
    with tempfile.TemporaryDirectory(prefix="solidon-activation-") as temporary:
        source = Path(temporary) / "activation.sqlite"
        source.write_bytes(payload)
        if wal_payload is not None:
            source.with_name(source.name + "-wal").write_bytes(wal_payload)
        snapshot = Path(temporary) / "activation-backup.sqlite"
        with contextlib.closing(sqlite3.connect(source)) as database:
            result = database.execute("PRAGMA integrity_check").fetchone()
            if result != ("ok",):
                raise SystemExit("Die Aktivierungsdatenbank hat die Integritätsprüfung abgelehnt.")
            tables = {
                name
                for (name,) in database.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            required = SUPPORT_DATABASE_TABLES if require_operator_events else CORE_DATABASE_TABLES
            if not required <= tables:
                raise SystemExit(
                    "Die vorhandene Produktivdatenbank braucht eine Wartungsmigration; "
                    "sie wird über FTPS nicht überschrieben."
                )
            with contextlib.closing(sqlite3.connect(snapshot)) as destination:
                database.backup(destination)
        with contextlib.closing(sqlite3.connect(snapshot)) as checked:
            if checked.execute("PRAGMA integrity_check").fetchone() != ("ok",):
                raise SystemExit("Der Datenbankschnappschuss ist nicht wiederherstellbar.")
        return snapshot.read_bytes()


def _database_bytes(payload: bytes, *, require_operator_events: bool = True) -> bytes:
    """Prüft eine einzelne SQLite-Datei und normalisiert sie für die Sicherung."""
    return _database_snapshot(payload, require_operator_events=require_operator_events)


def _remote_database_snapshot(session: ftplib.FTP_TLS, path: str) -> bytes | None:
    """Liest Hauptdatei und WAL stabil und vereinigt beide ohne Datenverlust."""
    wal_path = f"{path}-wal"
    for _attempt in range(3):
        database_before = _remote_bytes(session, path)
        if database_before is None:
            return None
        wal_before = _remote_bytes(session, wal_path)
        database_after = _remote_bytes(session, path)
        wal_after = _remote_bytes(session, wal_path)
        if database_before == database_after and wal_before == wal_after:
            return _database_snapshot(database_after, wal_after)
    raise SystemExit(
        "Die Aktivierungsdatenbank wurde während der Sicherung fortlaufend verändert. "
        "Erneut in einem ruhigen Wartungsfenster ausführen."
    )


def _operator_upload_needed(remote: bytes | None, local: bytes, rotate: bool) -> bool:
    """Erlaubt einen neuen Betreiberzugang nur mit ausdrücklicher Rotation."""
    if remote is None:
        return True
    if remote.strip() == local.strip():
        return False
    if not rotate:
        raise SystemExit(
            "Der Server trägt einen anderen Betreiberzugang. Für die bewusste Rotation "
            "--rotate-operator-token angeben; vorher wird die alte Datei gesichert."
        )
    return True


def _paths(access: dict[str, object]) -> tuple[str, str, str]:
    """Leitet Webroot, privaten Datenpfad und Sicherungswurzel gemeinsam ab."""
    webroot = str(access["root"]).strip("/")
    domain_root = webroot.rsplit("/", 1)[0]
    return webroot, f"{domain_root}/appdata", f"{domain_root}/backups/activation"


def deploy(
    seed: Path,
    database: Path,
    operator_token: Path,
    *,
    rotate_operator_token: bool = False,
) -> None:
    """Prüft, sichert und lädt alle zusammengehörigen Aktivierungsdateien."""
    seed = seed.expanduser().resolve()
    database = database.expanduser().resolve()
    operator_token = operator_token.expanduser().resolve()
    for private in (seed, database, operator_token):
        try:
            private.relative_to(ROOT)
        except ValueError:
            pass
        else:
            raise SystemExit(f"Private Aktivierungsdatei liegt im Repository: {private}")
        if not private.is_file():
            raise SystemExit(f"Private Aktivierungsdatei fehlt: {private}")
    if not _seed_matches(seed):
        raise SystemExit("Der private Aktivierungsstartwert passt nicht zum eingebauten Schlüssel.")
    if not _operator_token_is_valid(operator_token):
        raise SystemExit("Der private Betreiberzugang muss 32 zufällige Bytes als Hex enthalten.")
    _check_php()

    access = upload_website.read_access()
    host = str(access["host"])
    if upload_website.is_address(host):
        raise SystemExit("Der FTPS-Zugang nennt eine IP; der Zertifikatsname wäre ungeprüft.")
    webroot, data_root, backup_root = _paths(access)
    timestamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    backup = f"{backup_root}/{timestamp}"

    session = upload_website.connect(access)
    try:
        remote_seed_path = f"{data_root}/activation.seed"
        remote_database_path = f"{data_root}/activation.sqlite"
        remote_operator_path = f"{data_root}/operator.token"
        remote_seed = _remote_bytes(session, remote_seed_path)
        local_seed = seed.read_bytes()
        if remote_seed is not None and remote_seed.strip() != local_seed.strip():
            raise SystemExit(
                "Der Server trägt einen anderen Aktivierungsstartwert; er wird nicht ersetzt."
            )
        remote_database = _remote_database_snapshot(session, remote_database_path)
        local_database = _database_bytes(
            database.read_bytes(),
            require_operator_events=True,
        )
        if remote_database is not None:
            _database_bytes(remote_database, require_operator_events=False)
        remote_operator = _remote_bytes(session, remote_operator_path)
        local_operator = operator_token.read_bytes()
        replace_operator = _operator_upload_needed(
            remote_operator,
            local_operator,
            rotate_operator_token,
        )

        targets: list[tuple[str, bytes]] = []
        if remote_seed is None:
            targets.append((remote_seed_path, local_seed))
        if remote_database is None:
            targets.append((remote_database_path, local_database))
        if replace_operator:
            targets.append((remote_operator_path, local_operator))
        for relative in PUBLIC_FILES:
            local = upload_website.LOCAL_ROOT / relative
            targets.append((f"{webroot}/{relative.as_posix()}", local.read_bytes()))

        backup_sources: dict[str, bytes] = {}
        if remote_seed is not None:
            backup_sources[remote_seed_path] = remote_seed
        if remote_database is not None:
            backup_sources[remote_database_path] = remote_database
        if remote_operator is not None:
            backup_sources[remote_operator_path] = remote_operator
        for remote, _payload in targets:
            previous = _remote_bytes(session, remote)
            if previous is not None:
                backup_sources[remote] = previous

        backed_up = 0
        for remote, previous in backup_sources.items():
            name = remote.strip("/").replace("/", "__")
            backup_path = f"{backup}/{name}"
            _store_bytes(session, backup_path, previous)
            if _remote_bytes(session, backup_path) != previous:
                raise SystemExit(f"Serversicherung ließ sich nicht bestätigen: {remote}")
            backed_up += 1
        print(f"{backed_up} vorhandene Datei(en) gesichert unter {backup}.")

        for remote, payload in targets:
            _store_bytes(session, remote, payload)
            stored = _remote_bytes(session, remote)
            if stored != payload:
                raise SystemExit(f"Upload ließ sich nicht bytegenau bestätigen: {remote}")
            print(f"  {remote} ({len(payload)} Bytes)")
    finally:
        with contextlib.suppress(Exception):
            session.quit()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=Path, required=True, help="privater Startwert")
    parser.add_argument("--database", type=Path, required=True, help="lokale Ausgangsdatenbank")
    parser.add_argument(
        "--operator-token",
        type=Path,
        required=True,
        help="privater Zugang der Support-Verwaltung",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="nach den lokalen Prüfungen wirklich sichern und hochladen",
    )
    parser.add_argument(
        "--rotate-operator-token",
        action="store_true",
        help="abweichenden Betreiberzugang nach bestätigter Sicherung bewusst ersetzen",
    )
    arguments = parser.parse_args(argv)
    if not arguments.apply:
        parser.error("ohne --apply wird der Produktivserver nicht verändert")
    deploy(
        arguments.seed,
        arguments.database,
        arguments.operator_token,
        rotate_operator_token=arguments.rotate_operator_token,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
