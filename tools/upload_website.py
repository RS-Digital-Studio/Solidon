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
import io
import ipaddress
import json
import re
import ssl
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

#: Wo der Zugang steht. Neben dem Repository, nicht darin (``.gitignore``).
ACCESS_FILE = ROOT / ".webserver.json"

#: Was lokal die Website ist. Alles darunter wird auf den Dokumentenstamm
#: abgebildet: ``website/api/support.php`` → ``<root>/api/support.php``.
LOCAL_ROOT = ROOT / "website"

#: Was in der Zugangsdatei stehen muss.
TEMPLATE: dict[str, Any] = {
    "host": "a2f21.netcup.net",
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

    Drei Ausnahmen, jede mit Grund:

    ``dl/`` trägt die Installationspakete. Sie stehen nicht im Repository
    (``.gitignore``) und wiegen je Version hundert Megabyte; hochgeladen
    werden sie einmal und nicht bei jedem Abgleich.

    ``.md`` ist Entwicklerdoku. ``website/README.md`` erklärt, wie die Seiten
    gebaut sind — 232 Zeilen, die niemand im Netz lesen soll und die ein
    Abgleich sonst brav mit hochlädt. Genau das ist einmal passiert.

    ``.token`` ist ein Zugangswert. Der Betreiber-Token wird ausschließlich
    vom gehärteten Aktivierungs-Deployment in den privaten Serverordner gelegt.
    """
    relative = path.relative_to(LOCAL_ROOT)
    lower = path.name.lower()
    private_endings = (
        ".seed",
        ".sqlite",
        ".sqlite3",
        ".sqlite-wal",
        ".sqlite-shm",
        ".db",
        ".token",
        ".solidon-request",
        ".solidon-activation",
    )
    return (
        relative.parts[0] != "dl" and path.suffix != ".md" and not lower.endswith(private_endings)
    )


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


def remote_version(session: ftplib.FTP_TLS, root: str) -> dict[str, Any]:
    """``version.json`` **vom Server**, nicht die lokale.

    Der Unterschied ist der ganze Zweck: Was published liegt, ist für jeden Kunden
    die gültige Fassung — unabhängig davon, was hier für aktuell gehalten wird.
    """
    buffer = io.BytesIO()
    session.retrbinary(f"RETR /{root}/version.json", buffer.write)
    payload: dict[str, Any] = json.loads(buffer.getvalue().decode("utf-8"))
    return payload


def promised_files(payload: dict[str, Any]) -> set[str]:
    """Jeder Dateiname, den ``version.json`` nennt — aus **beiden** Feldern.

    ``updates.py`` liest ``url`` und ``file``: das eine, um zu laden, das andere,
    um zu benennen. Wer nur eines auswertet, hält eine Datei für entbehrlich,
    die das andere Feld noch verspricht.
    """
    names: set[str] = set()
    for entry in payload.get("packages", {}).values():
        if not isinstance(entry, dict):
            continue
        for field in ("url", "file"):
            value = str(entry.get(field, ""))
            if value:
                names.add(value.split("f=")[-1].split("/")[-1])
    return names


def stale_packages(session: ftplib.FTP_TLS, root: str) -> tuple[list[str], str]:
    """Welche Pakete unter ``dl/`` weg dürfen — und erst, wenn sie es dürfen.

    **Der Fall, der diese Funktion veranlasst hat.** Am 23.08.2026 wurden beim
    Veröffentlichen von 0.1.3 die alten Pakete gelöscht, **bevor** die Seiten und
    ``version.json`` published waren. Mehrere Minuten lang zeigte die Startseite in
    sechs Sprachen auf vier Dateien, die es nicht mehr gab, und die
    Update-Prüfung bot jedem Kunden eine Fassung an, deren Datei 404 gab.

    Gemerkt hat es keine der lokalen Prüfungen — lokal war durchgehend alles
    stimmig. Sichtbar wurde es erst durch einen Abruf **gegen den Server**.

    **Die Reihenfolge ist deshalb keine Gedächtnisaufgabe mehr, sondern eine
    Bedingung:** Gelöscht wird erst, wenn die ``version.json`` *published* die neue
    Fassung nennt. Bis dahin ist die alte die gültige, und ihre Dateien bleiben
    liegen. Nennt der Server noch die alte Fassung, gibt diese Funktion nichts
    zurück und sagt warum.

    Verschont wird außerdem alles, was ``version.json`` verspricht, und alles,
    was die laufende Fassung im Namen trägt — auch Dateien, die dort nicht
    stehen, etwa das Flatpak (Linux fehlt dort mit Absicht, ``updates.py``).
    """
    from app.branding import APP_VERSION

    payload = remote_version(session, root)
    published = str(payload.get("version", ""))
    if published != APP_VERSION:
        return [], (
            f"Der Server nennt noch Fassung {published}, die Anwendung ist {APP_VERSION}. "
            "Erst version.json hochladen, dann aufräumen — sonst zeigen Seiten "
            "und Update-Prüfung auf Dateien, die es nicht mehr gibt."
        )

    spared = promised_files(payload)
    if not spared:
        # **Eine Schonliste, die leer ist, schont nichts** — und dann stünde
        # jede Datei unter ``dl/`` auf der Löschliste, die nicht zufällig die
        # laufende Fassung im Namen trägt. Das passiert, wenn ``version.json``
        # oben zwar die richtige Version nennt, aber kein ``packages`` hat oder
        # eines, dessen Einträge keine Zuordnungen sind. Ein Werkzeug, das auf
        # einem Produktivserver löscht, darf aus einer unvollständigen Auskunft
        # keine weitreichende Handlung ableiten.
        return [], (
            "version.json nennt kein einziges Paket. Solange unklar ist, was "
            "noch gebraucht wird, wird nichts gelöscht."
        )
    candidates: list[str] = []
    for name, _size in remote_index(session, f"/{root}/dl").items():
        filename = name.split("/")[-1]
        if filename in spared or APP_VERSION in filename:
            continue
        candidates.append(filename)
    return sorted(candidates), ""


def hold_back_version(session: ftplib.FTP_TLS, root: str, files: list[Path]) -> list[Path]:
    """Lädt ``version.json`` erst, wenn ihre Pakete oben liegen.

    **Der Fall, der diese Funktion veranlasst hat**, ist derselbe wie bei
    :func:`stale_packages`, nur von der anderen Seite. Dort wurden die alten
    Pakete zu früh gelöscht; hier wird die neue Auskunft zu früh
    veröffentlicht. Das Ergebnis ist beide Male ein 404 für jeden Kunden.

    Am 27.08.2026 ist es mit 0.2.1 passiert, und zwar durch das Werkzeug
    selbst: ``--fehlend`` nimmt ``dl/`` bewusst aus (:func:`wanted` — Pakete
    gehen einmal hoch, nicht bei jedem Abgleich), lädt aber ``version.json``
    mit, und die zeigt genau dorthin. Ein Lauf, alle Seiten neu, drei Pakete
    versprochen, keines vorhanden.

    **Zwei Mengen, zwei Härten.** ``version.json`` führt die Pakete der
    Update-Automatik — Windows und die beiden Macs. Der Download-Kasten
    derselben Seiten verspricht mehr: am 27.08.2026 acht gegen drei, und die
    fünf übrigen (Linux, die macOS-Zips) fehlten oben genauso.

    Die Auskunft wird deshalb **zurückgehalten**, die Seiten gehen mit einer
    **Warnung** hoch. Der Unterschied liegt darin, wen es trifft: Ein Update
    holt sich jede Installation von selbst, und eine Fassung, die dabei 404
    gibt, hat der Kunde nicht gesucht. Einen Knopf im Kasten drückt jemand —
    er sieht, dass nichts kommt, und die alte Seite mit den alten Paketen
    wäre auch keine bessere Antwort, weil sie die neue Fassung verschweigt.
    """
    versprochen: set[str] = set()
    payload: dict[str, Any] = {}
    if any(path.name == "version.json" for path in files):
        payload = json.loads((LOCAL_ROOT / "version.json").read_text(encoding="utf-8"))
        versprochen |= promised_files(payload)

    # Was die hochzuladenden Seiten selbst im Kasten anbieten.
    im_kasten: set[str] = set()
    for path in files:
        if path.suffix != ".html":
            continue
        text = path.read_text(encoding="utf-8", errors="ignore")
        im_kasten.update(re.findall(r"(?:dl/|f=)(Solidon3D-[^\"'<> ]+)", text))

    if not versprochen and not im_kasten:
        return files

    oben = {
        name.split("/")[-1]: size for name, size in remote_index(session, f"/{root}/dl").items()
    }

    def complete(name: str) -> bool:
        """Ob die Datei oben liegt — **und ganz ist**.

        Der Name allein reicht nicht. Ein abgebrochener Upload hinterlässt den
        Eintrag und einen Teil der Bytes; die Pakete wiegen 260 bis 412 MB und
        gehen mit rund 1,8 MB/s hinauf, mehrere am Stück reißen die Verbindung.
        Wer nur nach dem Namen fragt, gibt ``version.json`` über einem halben
        Paket frei — und das ist schlimmer als der 404, gegen den diese
        Funktion gebaut wurde: Es sieht wie ein Erfolg aus, und die
        Update-Automatik lädt es jedem Kunden herunter.

        ``remote_index`` liefert die Größe ohnehin mit; :func:`differs` und
        :func:`verify_downloads` vergleichen sie längst. Nur hier fehlte sie.

        Ohne lokale Datei bleibt es beim Vorhandensein — dann gibt es kein
        Vergleichsmaß, und ein Paket, das hier nicht mehr liegt, ist deshalb
        nicht kaputt.
        """
        if name not in oben:
            return False
        local_file = LOCAL_ROOT / "dl" / name
        if not local_file.is_file():
            return True
        return oben[name] == local_file.stat().st_size

    def partial(name: str) -> bool:
        """Liegt oben, ist aber kürzer als hier — die Unterscheidung fürs Sagen."""
        return name in oben and not complete(name)

    fehlt_fuer_update = sorted(name for name in versprochen if not complete(name))
    fehlt_im_kasten = sorted(
        name for name in im_kasten if not complete(name) and name not in fehlt_fuer_update
    )

    if fehlt_im_kasten:
        print(f"Achtung: {len(fehlt_im_kasten)} Paket(e) aus dem Download-Kasten fehlen oben.")
        for name in fehlt_im_kasten:
            print(f"  {name}{' — liegt oben, aber unvollständig' if partial(name) else ''}")
        print("  Die Seiten gehen trotzdem hoch — ein Klick darauf gibt bis dahin 404.")

    if not fehlt_fuer_update:
        return files

    print(
        f"version.json bleibt liegen: {len(fehlt_fuer_update)} Paket(e) der Update-Prüfung "
        "fehlen oben."
    )
    for name in fehlt_fuer_update:
        if partial(name):
            full_size = (LOCAL_ROOT / "dl" / name).stat().st_size
            print(f"  {name} — liegt oben mit {oben[name]} statt {full_size} Bytes")
        else:
            print(f"  {name}")
    print("  Erst hochladen, dann version.json — sonst gibt jedes Update 404.")
    print(f"  Zu tun: python tools/upload_website.py website/dl/{fehlt_fuer_update[0]}")
    return [path for path in files if path.name != "version.json"]


def verify_downloads() -> int:
    """Ruft jede versprochene Datei ab — über HTTP, wie ein Kunde.

    **Lokal gegen lokal sagt nichts darüber, was oben liegt.** Am 23.08.2026
    (0.1.3) zeigten die Seiten in sechs Sprachen auf vier gelöschte Dateien,
    am 27.08.2026 (0.2.1) versprach ``version.json`` drei Pakete, die noch
    nicht hochgeladen waren. Beide Male waren alle lokalen Prüfungen grün, und
    beide Male hätte ein Abruf es in zehn Sekunden gesagt.

    Gefragt werden **beide** Quellen. ``version.json`` führt die Pakete der
    Update-Prüfung — Windows und die beiden Macs —, und wer nur sie liest,
    übersieht die Linux-Datei: Sie steht mit Absicht nicht darin
    (``updates.py``), im Download-Kasten aber schon.

    Geprüft wird auch die **Größe**: Ein abgebrochener Upload hinterlässt eine
    Datei, die es gibt und die nicht vollständig ist. HTTP 200 allein ist
    keine Auskunft darüber, ob jemand das Paket entpacken kann.
    """
    promised: set[str] = set()

    version_file = LOCAL_ROOT / "version.json"
    if version_file.is_file():
        promised |= promised_files(json.loads(version_file.read_text(encoding="utf-8")))

    for page in LOCAL_ROOT.glob("*/index.html"):
        promised.update(_LINKED.findall(page.read_text(encoding="utf-8", errors="ignore")))
    start = LOCAL_ROOT / "index.html"
    if start.is_file():
        promised.update(_LINKED.findall(start.read_text(encoding="utf-8", errors="ignore")))

    if not promised:
        print("Weder version.json noch die Startseiten versprechen ein Paket.")
        return 0

    base = str(read_access().get("public", "https://solidon3d.de/")).rstrip("/")
    print(f"{len(promised)} versprochene Datei(en) gegen {base}")

    broken: list[str] = []
    for name in sorted(promised):
        local = LOCAL_ROOT / "dl" / name
        expected = local.stat().st_size if local.is_file() else 0
        request = urllib.request.Request(f"{base}/dl/{name}", method="HEAD")
        try:
            with urllib.request.urlopen(request, timeout=30) as answer:
                length = int(answer.headers.get("Content-Length") or 0)
            if expected and length != expected:
                print(f"  GRÖSSE  {name}: oben {length}, hier {expected}")
                broken.append(name)
            else:
                print(f"  ok      {name}  {length / 1e6:.0f} MB")
        except urllib.error.HTTPError as problem:
            print(f"  HTTP {problem.code}  {name}")
            broken.append(name)
        except OSError as problem:
            print(f"  nicht erreichbar  {name}: {problem}")
            broken.append(name)

    if broken:
        print(f"\n{len(broken)} Datei(en) nicht in Ordnung — der Kunde bekommt dafür einen Fehler.")
        return 1
    print("\nAlles, was versprochen wird, liegt oben und ist vollständig.")
    return 0


#: Woran eine Seite eine Paketdatei nennt — im Kasten und hinter dem Zähler.
_LINKED = re.compile(r"(?:dl/|f=)(Solidon3D-[^\"'<> ]+)")


def remote_name(path: Path) -> str:
    """Der Pfad auf dem Server, abgeleitet aus dem lokalen."""
    return path.resolve().relative_to(LOCAL_ROOT).as_posix()


#: Dateien, deren Inhalt sich ändern kann, ohne dass die Länge es verrät.
#: Alles andere wird über die Größe verglichen — ein neu gerendertes Bild oder
#: ein neu gebautes Paket ist praktisch nie auf das Byte genau so groß wie sein
#: Vorgänger, und die Pakete sind dreihundert Megabyte schwer.
#:
#: **``.php`` steht bewusst nicht hier.** Der Server führt es aus, statt es
#: auszuliefern; ein Abruf gibt die Ausgabe zurück und nie den Quelltext, und
#: der Vergleich meldete deshalb bei jedem Lauf eine Abweichung, die keine ist.
#: Beim ersten Lauf dieser Prüfung war ``api/support.php`` genau dieser
#: Fehlbefund. Für PHP entscheidet die Größe.
_COMPARED_BY_CONTENT = frozenset(
    {".html", ".css", ".js", ".json", ".txt", ".xml", ".svg", ".webmanifest"}
)


def public_url(root: str, target: str) -> str:
    """Die Adresse, unter der eine Datei ausgeliefert wird.

    Der Dokumentenstamm heißt ``<domain>/httpdocs``; was dahinter liegt, ist
    der Pfad unter der Domain.
    """
    domain = root.strip("/").split("/")[0]
    return f"https://{domain}/{target}"


def differs(root: str, path: Path, remote_size: int | None) -> bool:
    """Weicht das, was der Kunde bekommt, von dem hier ab?

    **Die Größe allein genügt nicht, und das ist teuer.** Am 22.08.2026 stand
    auf der Website noch „Demo-Fassung", wo das Repository seit einem Commit
    „Demo-Version" sagte — in den AGB, der EULA und der Widerrufsbelehrung,
    also in den Texten, die im Zweifel vor Gericht gelten. Acht Dateien waren
    betroffen, und keine fiel auf: „Fassung" und „Version" sind beide sieben
    Zeichen lang. Ein Abgleich, der Längen vergleicht, sieht eine Umbenennung
    nie.

    Deshalb wird für Textdateien der Inhalt verglichen — und zwar **über
    HTTPS, nicht über FTP**. Das hat zwei Gründe, und der zweite ist der
    bessere: Erstens reißt die FTP-Datenverbindung nach der rekursiven
    Verzeichnisabfrage ab (gemessen, ``ConnectionResetError`` beim ersten
    ``RETR``). Zweitens ist die ausgelieferte Adresse die Wahrheit, auf die es
    ankommt — zwischen dem FTP-Verzeichnis und dem, was beim Kunden ankommt,
    stehen ``.htaccess``, Umschreibungen und alles andere, was der Server tut.
    Wer das FTP-Verzeichnis prüft, prüft die Ablage; wer die Adresse abruft,
    prüft die Auslieferung.

    Verglichen wird roh und nicht normalisiert: Liegt dort dieselbe Datei mit
    anderen Zeilenenden, ist sie eine andere Datei, und der nächste Upload
    bringt beide Seiten in denselben Zustand. Was nicht öffentlich abrufbar ist
    — ``.htaccess`` antwortet mit 403 —, entscheidet die Größe wie zuvor.
    """
    if remote_size is None:
        return True
    if remote_size != path.stat().st_size:
        return True
    if path.suffix.lower() not in _COMPARED_BY_CONTENT:
        return False
    request = urllib.request.Request(public_url(root, remote_name(path)))
    try:
        with urllib.request.urlopen(request, timeout=30) as answer:
            served = answer.read()
    except (urllib.error.URLError, TimeoutError):
        # Nicht öffentlich oder nicht erreichbar: Die Größe hat schon
        # gestimmt, mehr lässt sich von hier aus nicht sagen.
        return False
    return bool(served != path.read_bytes())


def with_outdated_page_assets(
    files: list[Path],
    root: str,
    remote: dict[str, int],
) -> list[Path]:
    """Abweichende gestempelte Dateien ausgewählter Seiten mitnehmen.

    Ein Inhaltsstempel in einer HTML-Adresse verhindert nur den Griff in den
    Browsercache. Er veröffentlicht nicht die Datei hinter der Adresse. Am
    29.08.2026 lag deshalb der neue Changelog bereits oben, während der Server
    unter ``site.js`` noch die Fassung ohne seine Versionsumschaltung ausgab:
    Das Auswahlfeld änderte sich, die sichtbare Karte nicht.

    Ausgewählte HTML-Seiten bilden hier mit ihren gestempelten lokalen
    Verweisen eine Liefereinheit. Mitgenommen wird nur, was oben fehlt oder
    in Inhalt beziehungsweise Größe abweicht; große, bereits gleiche Bilder
    reisen dadurch nicht bei jedem Seitenlauf erneut.
    """
    from tools.stamp_assets import LINK, target_of

    selected = list(dict.fromkeys(path.resolve() for path in files))
    known = set(selected)
    referenced: list[Path] = []
    for page in selected:
        if page.suffix.lower() != ".html":
            continue
        text = page.read_text(encoding="utf-8", errors="ignore")
        for _prefix, reference, stamp, _suffix in LINK.findall(text):
            if not stamp:
                continue
            target = target_of(page, reference).resolve()
            if target in known or target in referenced:
                continue
            if not target.is_file() or LOCAL_ROOT not in target.parents or not wanted(target):
                continue
            referenced.append(target)

    for target in referenced:
        name = remote_name(target)
        if differs(root, target, remote.get(name)):
            selected.append(target)
            known.add(target)
    return selected


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


def refuse_unsigned_version(files: list[Path]) -> None:
    """Hält an, bevor eine ``version.json`` ohne gültige Unterschrift hochgeht
    (§37.2).

    **Warum das hart abbricht und nicht warnt.** Eine Warnung beim Hochladen
    liest, wer zusieht; hochgeladen wird trotzdem. Und der Schaden ist
    lautlos: Die Datei liegt richtig da, die Seite zeigt sie an, die Pakete
    sind erreichbar — nur verwirft jede Installation die Datei still, und
    niemand erfährt je von dieser Fassung. Das fällt erst auf, wenn jemand
    fragt, warum sich niemand aktualisiert.

    ``make_download.py`` schreibt die Datei neu und macht dabei jede
    vorhandene Unterschrift ungültig. Genau zwischen diesen beiden Schritten
    steht diese Prüfung.
    """
    if not any(path.name == "version.json" for path in files):
        return
    from app.core.updates import signature_ok

    data = json.loads((LOCAL_ROOT / "version.json").read_text(encoding="utf-8"))
    if signature_ok(data):
        return
    raise SystemExit(
        "version.json trägt keine gültige Unterschrift und wird deshalb nicht "
        "hochgeladen.\n"
        "  Jede Installation prüft sie gegen updates.RELEASE_PUBLIC_KEY und "
        "verwirft sie ohne — das Update erreicht dann niemanden.\n"
        "  Zu tun: python tools/sign_version.py --private <datei>"
    )


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
        help="den Serverstand listen und alles laden, was fehlt oder abweicht "
        "(Textdateien werden am Inhalt verglichen, nicht an der Länge)",
    )
    parser.add_argument(
        "--alte-pakete",
        dest="prune",
        action="store_true",
        help="zeigen, welche Pakete unter dl/ keine Fassung mehr bedienen "
        "(löscht nichts, dafür braucht es zusätzlich --wirklich)",
    )
    parser.add_argument(
        "--wirklich",
        dest="confirm",
        action="store_true",
        help="zusammen mit --alte-pakete: die gezeigten Dateien wirklich löschen",
    )
    parser.add_argument(
        "--nachpruefen",
        dest="verify",
        action="store_true",
        help="jede Datei abrufen, die version.json und die Startseiten versprechen "
        "— gegen den Server, nicht gegen die Platte",
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

    if arguments.verify:
        # Braucht kein FTP: gefragt wird über HTTP, wie ein Kunde fragt.
        return verify_downloads()

    if arguments.since:
        files = files_since(arguments.since)
    elif arguments.changed:
        files = changed_files()
    elif arguments.missing:
        files = []
    else:
        files = [path.resolve() for path in arguments.files]
    if not files and not arguments.missing and not arguments.prune:
        print(
            "Nichts zu tun. Dateien nennen, --geaendert, --seit, --fehlend, "
            "--alte-pakete oder --nachpruefen benutzen."
        )
        return 1

    for path in files:
        if not path.is_file():
            raise SystemExit(f"Gibt es nicht: {path}")
        if LOCAL_ROOT not in path.parents:
            raise SystemExit(f"Liegt nicht unter website/: {path}")

    refuse_unsigned_version(files)

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
        if arguments.prune:
            stale, reason = stale_packages(session, root)
            if reason:
                print(reason)
                return 1
            if not stale:
                print("Unter dl/ liegt nichts, was keine Fassung mehr bedient.")
                return 0
            print(f"{len(stale)} Paket(e) bedienen keine Fassung mehr:")
            for name in stale:
                print(f"  {name}")
            if not arguments.confirm:
                print()
                print("Nichts gelöscht. Mit --wirklich noch einmal aufrufen.")
                return 0
            for name in stale:
                session.delete(f"/{root}/dl/{name}")
                print(f"  gelöscht: {name}")
            return 0

        if arguments.missing:
            remote = remote_index(session, "/" + root)
            files = [
                path for path in local_files() if differs(root, path, remote.get(remote_name(path)))
            ]
            print(f"{len(remote)} Dateien oben, {len(files)} davon fehlen oder weichen ab")
            if not files:
                print("Der Server hat alles.")
                return 0
        elif any(path.suffix.lower() == ".html" for path in files):
            remote = remote_index(session, "/" + root)
            files = with_outdated_page_assets(files, root, remote)
        files = hold_back_version(session, root, files)
        print(f"{len(files)} Datei(en) → {access['host']}:{root}")
        for path in files:
            upload(session, access, path)
    finally:
        session.quit()
    print("fertig")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
