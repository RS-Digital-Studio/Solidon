"""Dateien aus ``website/`` auf den Webserver laden.

Die Website liegt auf einem netcup-Hosting-Paket, und bis hierher wanderte
jede Änderung von Hand über den Dateimanager. Das ist kein Werkzeug, sondern
eine Gewohnheit, und Gewohnheiten vergessen Dateien.

    .venv\\Scripts\\python.exe tools/upload_website.py website/api/support.php
    .venv\\Scripts\\python.exe tools/upload_website.py --geaendert
    .venv\\Scripts\\python.exe tools/upload_website.py --vorlage

**Der Zugang steht in ``.webserver.json`` und nirgends sonst.** Die Datei ist
in ``.gitignore`` eingetragen: Ein Passwort in einem Repository ist ein
veröffentlichtes Passwort, auch in einem privaten — und ein Klon davon liegt
auf jeder Maschine, auf der jemand einmal gearbeitet hat.

**Ein Anmeldeversuch, nicht zwei.** Drei Fehlschläge in Folge sind bei
fail2ban der Weg zu einer gesperrten IP; wer beim ersten Nein ein zweites
Passwort probiert, sperrt sich aus. Gesprochen wird FTPS und nicht SFTP: FTP
ist auf diesem Paket immer offen, SSH nur, solange der Schalter in Plesk steht.
"""

from __future__ import annotations

import argparse
import ftplib
import json
import ssl
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

#: Wo der Zugang steht. Neben dem Repository, nicht darin (``.gitignore``).
ACCESS_FILE = ROOT / ".webserver.json"

#: Was lokal die Website ist. Alles darunter wird auf den Dokumentenstamm
#: abgebildet: ``website/api/support.php`` → ``<root>/api/support.php``.
LOCAL_ROOT = ROOT / "website"

#: Was in der Zugangsdatei stehen muss.
VORLAGE: dict[str, Any] = {
    "host": "188.68.47.33",
    "user": "hosting245877",
    "password": "hier eintragen",
    "root": "solidon3d.de/httpdocs",
}


def read_access() -> dict[str, Any]:
    """Der Zugang, oder ein Satz, der sagt, wie er dorthin kommt."""
    if not ACCESS_FILE.is_file():
        raise SystemExit(
            f"Es gibt keine {ACCESS_FILE.name}.\n"
            "  tools/upload_website.py --vorlage  schreibt sie an; "
            "danach das Passwort eintragen.\n"
            "  Sie ist in .gitignore und bleibt auf dieser Maschine."
        )
    access = json.loads(ACCESS_FILE.read_text(encoding="utf-8"))
    missing = [key for key in VORLAGE if not str(access.get(key, "")).strip()]
    if missing:
        raise SystemExit(f"In {ACCESS_FILE.name} fehlt: {', '.join(missing)}")
    return dict(access)


def write_template() -> int:
    if ACCESS_FILE.exists():
        print(f"{ACCESS_FILE.name} gibt es schon — sie wird nicht überschrieben.")
        return 1
    ACCESS_FILE.write_text(json.dumps(VORLAGE, ensure_ascii=False, indent=2) + "\n", "utf-8")
    print(f"{ACCESS_FILE.name} angelegt. Jetzt das Passwort eintragen.")
    print("Sie steht in .gitignore und wird nie mitcommittet.")
    return 0


def changed_files() -> list[Path]:
    """Was unter ``website/`` gegenüber dem letzten Commit anders ist.

    Aus Git und nicht aus Zeitstempeln: Ein neu erzeugtes Handbuch ist überall
    frisch, geändert hat sich davon das Wenigste.
    """
    result = subprocess.run(
        ["git", "status", "--porcelain", "--", "website"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    found: list[Path] = []
    for line in result.stdout.splitlines():
        name = line[3:].strip().strip('"')
        if line[:2] == " D" or not name:
            continue
        path = ROOT / name
        if path.is_file():
            found.append(path)
    return found


def files_since(reference: str) -> list[Path]:
    """Was sich seit einem Commit unter ``website/`` geändert hat.

    Der Fall nach dem Committen: ``git status`` ist dann sauber, hochgeladen
    ist trotzdem nichts. Ohne diesen Weg bliebe nur, die Dateien von Hand
    aufzuzählen — und genau dabei vergisst man eine.
    """
    result = subprocess.run(
        ["git", "diff", "--name-only", "--diff-filter=d", reference, "--", "website"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [ROOT / name for name in result.stdout.split("\n") if name and (ROOT / name).is_file()]


def remote_name(path: Path) -> str:
    """Der Pfad auf dem Server, abgeleitet aus dem lokalen."""
    return path.resolve().relative_to(LOCAL_ROOT).as_posix()


def connect(access: dict[str, Any]) -> ftplib.FTP_TLS:
    """Eine Anmeldung. Scheitert sie, endet der Lauf — siehe Modulkopf."""
    context = ssl.create_default_context()
    # Das Zertifikat gehört dem Hoster und läuft auf einen anderen Namen als
    # die IP. Geprüft wird damit die Verschlüsselung, nicht der Name; für den
    # Dateitransfer in ein eigenes Paket ist das die Abwägung wert.
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE

    session = ftplib.FTP_TLS(context=context)
    session.connect(str(access["host"]), int(access.get("port", 21)), timeout=30)
    session.login(str(access["user"]), str(access["password"]))
    session.prot_p()
    return session


def ensure_dir(session: ftplib.FTP_TLS, parts: list[str]) -> None:
    """Ins Zielverzeichnis wechseln und anlegen, was fehlt."""
    session.cwd("/")
    for part in parts:
        if not part:
            continue
        try:
            session.cwd(part)
        except ftplib.error_perm:
            session.mkd(part)
            session.cwd(part)
            print(f"  angelegt: {part}")


def upload(session: ftplib.FTP_TLS, access: dict[str, Any], path: Path) -> None:
    target = remote_name(path)
    parts = str(access["root"]).strip("/").split("/") + target.split("/")[:-1]
    ensure_dir(session, parts)
    with path.open("rb") as source:
        session.storbinary(f"STOR {path.name}", source)
    print(f"  {target}  ({path.stat().st_size} Bytes)")


def main() -> int:
    parser = argparse.ArgumentParser(description="Dateien aus website/ hochladen.")
    parser.add_argument("files", nargs="*", type=Path, help="Dateien unter website/")
    parser.add_argument(
        "--geaendert",
        action="store_true",
        help="alles nehmen, was git unter website/ als geändert führt",
    )
    parser.add_argument(
        "--seit",
        metavar="COMMIT",
        default="",
        help="alles nehmen, was sich seit diesem Commit unter website/ geändert hat",
    )
    parser.add_argument(
        "--vorlage", action="store_true", help=f"{ACCESS_FILE.name} anlegen und aufhören"
    )
    arguments = parser.parse_args()

    if arguments.vorlage:
        return write_template()

    if arguments.seit:
        files = files_since(arguments.seit)
    elif arguments.geaendert:
        files = changed_files()
    else:
        files = [path.resolve() for path in arguments.files]
    if not files:
        print("Nichts zu tun. Dateien nennen, --geaendert oder --seit benutzen.")
        return 1

    for path in files:
        if not path.is_file():
            raise SystemExit(f"Gibt es nicht: {path}")
        if LOCAL_ROOT not in path.parents:
            raise SystemExit(f"Liegt nicht unter website/: {path}")

    access = read_access()
    print(f"{len(files)} Datei(en) → {access['host']}:{access['root']}")

    session = connect(access)
    try:
        for path in files:
            upload(session, access, path)
    finally:
        session.quit()
    print("fertig")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
