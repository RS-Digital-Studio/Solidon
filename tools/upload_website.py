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
import ipaddress
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
TEMPLATE: dict[str, Any] = {
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
    missing = [key for key in TEMPLATE if not str(access.get(key, "")).strip()]
    if missing:
        raise SystemExit(f"In {ACCESS_FILE.name} fehlt: {', '.join(missing)}")
    return dict(access)


def write_template() -> int:
    if ACCESS_FILE.exists():
        print(f"{ACCESS_FILE.name} gibt es schon — sie wird nicht überschrieben.")
        return 1
    ACCESS_FILE.write_text(json.dumps(TEMPLATE, ensure_ascii=False, indent=2) + "\n", "utf-8")
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


def wanted(path: Path) -> bool:
    """Ob eine lokale Datei überhaupt auf den Server gehört.

    Zwei Ausnahmen, beide mit Grund:

    ``dl/`` trägt die Installationspakete. Sie stehen nicht im Repository
    (``.gitignore``) und wiegen je Fassung hundert Megabyte; hochgeladen
    werden sie einmal und nicht bei jedem Abgleich.

    ``.md`` ist Entwicklerdoku. ``website/README.md`` erklärt, wie die Seiten
    gebaut sind — 232 Zeilen, die niemand im Netz lesen soll und die ein
    Abgleich sonst brav mit hochlädt. Genau das ist einmal passiert.
    """
    relative = path.relative_to(LOCAL_ROOT)
    return relative.parts[0] != "dl" and path.suffix != ".md"


def local_files() -> list[Path]:
    """Alles, was lokal zur Website gehört."""
    return sorted(path for path in LOCAL_ROOT.rglob("*") if path.is_file() and wanted(path))


def remote_index(session: ftplib.FTP_TLS, root: str) -> dict[str, int]:
    """Was auf dem Server liegt, mit Größe — rekursiv.

    Der Abgleich ist der Grund, aus dem es dieses Werkzeug gibt: Fünf Bilder
    der Startseite fehlten dort monatelang, weil beim Hochladen von Hand die
    Seite mitkam und ihre Bilder nicht. Ein Alternativtext, den niemand lesen
    soll, stand an ihrer Stelle.
    """
    found: dict[str, int] = {}

    def walk(path: str) -> None:
        try:
            entries = list(session.mlsd(path, facts=["type", "size"]))
        except ftplib.error_perm:
            return
        for name, facts in entries:
            if name in (".", ".."):
                continue
            kind = facts.get("type", "")
            full = f"{path}/{name}"
            if kind == "dir":
                walk(full)
            elif kind == "file":
                found[full[len(root) + 1 :]] = int(facts.get("size", 0))

    walk(root)
    return found


def remote_name(path: Path) -> str:
    """Der Pfad auf dem Server, abgeleitet aus dem lokalen."""
    return path.resolve().relative_to(LOCAL_ROOT).as_posix()


def is_address(host: str) -> bool:
    """Ob der Zugang eine IP nennt statt eines Namens.

    Der Unterschied entscheidet, wie weit die Zertifikatsprüfung reicht: Auf
    eine IP stellt kein Hoster ein Zertifikat aus, auf seinen Namen schon.
    """
    try:
        ipaddress.ip_address(host)
    except ValueError:
        return False
    return True


def connect(access: dict[str, Any]) -> ftplib.FTP_TLS:
    """Eine Anmeldung. Scheitert sie, endet der Lauf — siehe Modulkopf.

    **Das Zertifikat wird geprüft.** Hier stand einmal ``CERT_NONE`` mit der
    Begründung, damit werde „die Verschlüsselung geprüft, nicht der Name" —
    das ist nicht, was ``CERT_NONE`` tut. Es prüft gar nichts: Kette, Ablauf
    und Aussteller fallen mit weg, und ein Zertifikat, das sich jemand selbst
    ausgestellt hat, wird angenommen wie das echte. Über diese Leitung geht
    das Passwort zum Produktivserver.

    Was gemeint war, ist ``CERT_REQUIRED`` ohne Namensprüfung — Kette und
    Ablauf werden geprüft, nur der Name nicht. Nötig ist das allein, solange
    der Zugang eine IP nennt; steht dort ein Name, bleibt auch die
    Namensprüfung an, und dann ist die Verbindung vollständig abgesichert.
    """
    host = str(access["host"])
    context = ssl.create_default_context()
    if is_address(host):
        context.check_hostname = False
        print("  Hinweis: Zugang nennt eine IP — Zertifikatsname ungeprüft.")
        print("           Ein Hostname in .webserver.json schließt die Lücke.")

    session = ftplib.FTP_TLS(context=context)
    session.connect(host, int(access.get("port", 21)), timeout=30)
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
    # **Der Schalter heißt deutsch, das Feld dahinter englisch.** Die
    # Kommandozeile ist Oberfläche und spricht die Sprache des Bedieners; was
    # argparse daraus macht, ist ein Bezeichner und fällt unter die
    # Sprachregelung. Ohne ``dest`` ist es beides zugleich — und dann hängt es
    # vom Zufall ab, ob das Wort in der kuratierten Liste von
    # ``test_language_rules`` steht oder nicht.
    parser.add_argument(
        "--geaendert",
        dest="changed",
        action="store_true",
        help="alles nehmen, was git unter website/ als geändert führt",
    )
    parser.add_argument(
        "--seit",
        dest="since",
        metavar="COMMIT",
        default="",
        help="alles nehmen, was sich seit diesem Commit unter website/ geändert hat",
    )
    parser.add_argument(
        "--fehlend",
        dest="missing",
        action="store_true",
        help="den Serverstand listen und alles laden, was fehlt oder anders groß ist",
    )
    parser.add_argument(
        "--vorlage",
        dest="template",
        action="store_true",
        help=f"{ACCESS_FILE.name} anlegen und aufhören",
    )
    arguments = parser.parse_args()

    if arguments.template:
        return write_template()

    if arguments.since:
        files = files_since(arguments.since)
    elif arguments.changed:
        files = changed_files()
    elif arguments.missing:
        files = []
    else:
        files = [path.resolve() for path in arguments.files]
    if not files and not arguments.missing:
        print("Nichts zu tun. Dateien nennen, --geaendert, --seit oder --fehlend benutzen.")
        return 1

    for path in files:
        if not path.is_file():
            raise SystemExit(f"Gibt es nicht: {path}")
        if LOCAL_ROOT not in path.parents:
            raise SystemExit(f"Liegt nicht unter website/: {path}")

    access = read_access()
    root = str(access["root"]).strip("/")
    try:
        session = connect(access)
    except ssl.SSLCertVerificationError as problem:
        # Seit die Prüfung wirklich prüft, kann sie auch scheitern — und dann steht
        # hier ein Satz statt eines Stapelabzugs. Die drei Wege hinaus in der
        # Reihenfolge, in der man sie gehen sollte.
        raise SystemExit(
            f"Das Zertifikat des Servers wurde abgelehnt: {problem.verify_message or problem}\n"
            "  Abgelaufen? Beim Hoster erneuern.\n"
            "  Auf einen anderen Namen ausgestellt? Diesen Namen als 'host' in "
            f"{ACCESS_FILE.name} eintragen statt der IP.\n"
            "  Eigene Zertifizierungsstelle? Ihr Wurzelzertifikat gehört in den "
            "Speicher des Systems, nicht in eine Ausnahme hier."
        ) from problem
    try:
        if arguments.missing:
            remote = remote_index(session, "/" + root)
            files = [
                path
                for path in local_files()
                if remote.get(remote_name(path)) != path.stat().st_size
            ]
            print(f"{len(remote)} Dateien oben, {len(files)} davon fehlen oder weichen ab")
            if not files:
                print("Der Server hat alles.")
                return 0
        print(f"{len(files)} Datei(en) → {access['host']}:{root}")
        for path in files:
            upload(session, access, path)
    finally:
        session.quit()
    print("fertig")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
