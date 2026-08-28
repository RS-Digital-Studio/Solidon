"""Spielt den Aktivierungsdienst mit Sicherung auf den Produktivserver.

Private Dateien landen ausschließlich im benachbarten ``appdata`` und nie
unter ``httpdocs``. Eine vorhandene Produktivdatenbank wird geprüft, aber nie
über FTPS ersetzt — sonst könnte eine gleichzeitig offene SQLite-WAL verloren
gehen. Ein abweichender privater Startwert wird ebenfalls nicht automatisch
ersetzt, weil damit bereits ausgestellte Geräte-Zertifikate ihre
Vertrauenskette verlören.
"""

from __future__ import annotations

import argparse
import contextlib
import ftplib
import io
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
    Path("api/activation-health.php"),
    Path("offline-aktivierung.html"),
    Path("activation.js"),
    Path("style.css"),
    Path("eula.html"),
    Path("agb.html"),
    Path("widerruf.html"),
)


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
    except (OSError, ValueError):
        return False
    return (
        len(seed) == ed25519.POINT_BYTES
        and ed25519.public_key(seed) == certificate.ACTIVATION_PUBLIC_KEY
    )


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


def _database_bytes(payload: bytes) -> bytes:
    """Prüft Integrität und vollständiges Schema einer SQLite-Datei."""
    with tempfile.TemporaryDirectory(prefix="solidon-activation-") as temporary:
        target = Path(temporary) / "activation.sqlite"
        target.write_bytes(payload)
        with contextlib.closing(sqlite3.connect(target)) as database:
            result = database.execute("PRAGMA integrity_check").fetchone()
            if result != ("ok",):
                raise SystemExit("Die Aktivierungsdatenbank hat die Integritätsprüfung abgelehnt.")
            tables = {
                name
                for (name,) in database.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
            required = {"licences", "activations", "activation_attempts"}
            if not required <= tables:
                raise SystemExit(
                    "Die vorhandene Produktivdatenbank braucht eine Wartungsmigration; "
                    "sie wird über FTPS nicht überschrieben."
                )
        return target.read_bytes()


def _paths(access: dict[str, object]) -> tuple[str, str, str]:
    """Leitet Webroot, privaten Datenpfad und Sicherungswurzel gemeinsam ab."""
    webroot = str(access["root"]).strip("/")
    domain_root = webroot.rsplit("/", 1)[0]
    return webroot, f"{domain_root}/appdata", f"{domain_root}/backups/activation"


def deploy(seed: Path, database: Path) -> None:
    """Prüft, sichert und lädt alle zusammengehörigen Aktivierungsdateien."""
    seed = seed.expanduser().resolve()
    database = database.expanduser().resolve()
    for private in (seed, database):
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
        remote_seed = _remote_bytes(session, remote_seed_path)
        local_seed = seed.read_bytes()
        if remote_seed is not None and remote_seed.strip() != local_seed.strip():
            raise SystemExit(
                "Der Server trägt einen anderen Aktivierungsstartwert; er wird nicht ersetzt."
            )
        remote_database = _remote_bytes(session, remote_database_path)
        if remote_database is not None:
            _database_bytes(remote_database)
        else:
            _database_bytes(database.read_bytes())

        targets: list[tuple[str, bytes]] = []
        if remote_seed is None:
            targets.append((remote_seed_path, local_seed))
        if remote_database is None:
            targets.append((remote_database_path, database.read_bytes()))
        for relative in PUBLIC_FILES:
            local = upload_website.LOCAL_ROOT / relative
            targets.append((f"{webroot}/{relative.as_posix()}", local.read_bytes()))

        backup_sources: dict[str, bytes] = {}
        if remote_seed is not None:
            backup_sources[remote_seed_path] = remote_seed
        if remote_database is not None:
            backup_sources[remote_database_path] = remote_database
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
        "--apply",
        action="store_true",
        help="nach den lokalen Prüfungen wirklich sichern und hochladen",
    )
    arguments = parser.parse_args(argv)
    if not arguments.apply:
        parser.error("ohne --apply wird der Produktivserver nicht verändert")
    deploy(arguments.seed, arguments.database)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
