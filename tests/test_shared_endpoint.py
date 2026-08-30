"""Der ganze Weg der Börse über HTTP: hochladen, bestätigen, suchen, holen.

**Gefahren wird der Weg, den ein Kunde geht**, nicht die Funktionen darunter.
Ein Test, der `shared_upload()` direkt riefe, prüfte die Funktion und nicht den
Endpunkt — er sähe weder das Formularfeld noch den Statuscode noch die Mail.
Dieselbe Entscheidung wie bei `test_support`: Ein Nachbau prüft den Nachbau.

Der Server ist ein echter `php -S`, die Ablage ein Temp-Ordner
(`SOLIDON_SHARED_DB`, `SOLIDON_SHARED_FILES`), und die Mail fängt ein
Socket-Fänger ab. Ohne ihn bräche der Upload mit `mail_failed` ab — auf einer
Entwicklermaschine gibt es keinen Postausgang, und der Bestätigungslink ist
genau das, was hier zu prüfen ist.

Ohne PHP überspringt sich alles.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import socket
import sqlite3
import subprocess
import threading
import time
import urllib.error
import urllib.request
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent
ENDPUNKT = WURZEL / "website" / "api" / "shared.php"

#: Ein Rezept, das die Prüfung annimmt — dieselbe Form wie in test_shared_php.
REZEPT = {
    "format_version": 1,
    "name": "werkbank_halter",
    "title": "Halter für die Werkbank",
    "doc": "Zwei Einhänger, Rückwand 120 mm.",
    "author": "RS Digital",
    "license": "CC-BY-4.0",
    "document": {
        "ops": [{"op": "create_box", "params": {"width": 120.0, "depth": 60.0, "height": 45.0}}]
    },
}


class Postfach:
    """Ein SMTP-Fänger, der genug spricht, um eine Mail entgegenzunehmen.

    Er beantwortet `EHLO`, `MAIL`, `RCPT`, `DATA` und den Schlusspunkt — mehr
    verlangt PHPs `mail()` auf Windows nicht. Was er sammelt, ist die fertige
    Nachricht samt Kopfzeilen; darin steht der Bestätigungslink, um den es geht.
    """

    def __init__(self) -> None:
        self.nachrichten: list[str] = []
        self._server = socket.socket()
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind(("127.0.0.1", 0))
        self._server.listen(4)
        self.port = self._server.getsockname()[1]
        self._läuft = True
        self._faden = threading.Thread(target=self._bedienen, daemon=True)
        self._faden.start()

    def _bedienen(self) -> None:
        while self._läuft:
            try:
                verbindung, _ = self._server.accept()
            except OSError:
                return
            with verbindung, contextlib.suppress(OSError):
                self._sprechen(verbindung)

    def _sprechen(self, verbindung: socket.socket) -> None:
        # ASCII, und zwar nicht aus Bequemlichkeit: Ein Byte-Literal trägt keine
        # Umlaute, und die Begrüßungszeile eines SMTP-Servers ist eines.
        verbindung.sendall(b"220 solidon-pruefstand\r\n")
        inhalt: list[str] = []
        daten = False
        puffer = b""
        while True:
            teil = verbindung.recv(4096)
            if not teil:
                return
            puffer += teil
            while b"\r\n" in puffer:
                zeile, puffer = puffer.split(b"\r\n", 1)
                text = zeile.decode("utf-8", "replace")
                if daten:
                    if text == ".":
                        self.nachrichten.append("\n".join(inhalt))
                        inhalt = []
                        daten = False
                        verbindung.sendall(b"250 angenommen\r\n")
                    else:
                        inhalt.append(text)
                    continue
                oben = text.upper()
                if oben.startswith(("EHLO", "HELO")):
                    verbindung.sendall(b"250 hallo\r\n")
                elif oben.startswith(("MAIL", "RCPT")):
                    verbindung.sendall(b"250 gut\r\n")
                elif oben.startswith("DATA"):
                    daten = True
                    verbindung.sendall(b"354 los\r\n")
                elif oben.startswith("QUIT"):
                    verbindung.sendall(b"221 ende\r\n")
                    return
                else:
                    verbindung.sendall(b"250 gut\r\n")

    def schliessen(self) -> None:
        self._läuft = False
        self._server.close()


@pytest.fixture
def boerse(tmp_path: Path):
    """Ein laufender PHP-Server mit eigener Ablage und eigenem Postfach."""
    php = shutil.which("php")
    if php is None:
        pytest.skip("ohne PHP nicht prüfbar")

    postfach = Postfach()
    umgebung = dict(os.environ)
    umgebung.update(
        {
            "SOLIDON_SHARED_DB": str(tmp_path / "shared.sqlite"),
            "SOLIDON_SHARED_FILES": str(tmp_path / "dateien"),
            # Ohne Startwert verweigert die Börse den Dienst — absichtlich, damit
            # niemand mit wechselndem Hash Doppeleinreichungen zählt.
            "SOLIDON_SHARED_SEED": "prüfstand",
        }
    )

    frei = socket.socket()
    frei.bind(("127.0.0.1", 0))
    port = frei.getsockname()[1]
    frei.close()

    optionen = ["-d", "extension=mbstring", "-d", "extension=pdo_sqlite"]
    erweiterungen = Path(php).parent / "ext"
    if erweiterungen.is_dir():
        optionen[:0] = ["-d", f"extension_dir={erweiterungen}"]
    optionen += ["-d", "SMTP=127.0.0.1", "-d", f"smtp_port={postfach.port}"]

    # **In eine Datei und nicht in ein Rohr.** Ein `PIPE`, das niemand liest,
    # bleibt beim Aufräumen offen und wird unter `filterwarnings = ["error"]`
    # zu drei Fehlern, obwohl jeder Test bestanden hat. Die Datei kostet
    # nichts und trägt im Fehlerfall PHPs eigene Meldung.
    protokoll = (tmp_path / "php.log").open("w", encoding="utf-8")
    lauf = subprocess.Popen(
        [php, *optionen, "-S", f"127.0.0.1:{port}", "-t", str(ENDPUNKT.parent)],
        env=umgebung,
        stdout=subprocess.DEVNULL,
        stderr=protokoll,
    )
    basis = f"http://127.0.0.1:{port}/shared.php"
    for _ in range(60):
        try:
            urllib.request.urlopen(basis + "?do=list", timeout=1).read()
            break
        except urllib.error.HTTPError:
            break
        except OSError:
            time.sleep(0.1)
    else:
        lauf.terminate()
        protokoll.close()
        postfach.schliessen()
        pytest.skip("der PHP-Server kam nicht hoch")

    try:
        yield basis, postfach, umgebung
    finally:
        lauf.terminate()
        lauf.wait(timeout=10)
        protokoll.close()
        postfach.schliessen()


def _hochladen(basis: str, rezept: dict, adresse: str = "kunde@beispiel.de") -> tuple[int, dict]:
    """Eine Einreichung als multipart, wie ein Formular sie schickt."""
    grenze = "----solidonpruefstand"
    nutzlast = json.dumps(rezept, ensure_ascii=False).encode("utf-8")
    teile = (
        (
            f"--{grenze}\r\n"
            f'Content-Disposition: form-data; name="contact"\r\n\r\n{adresse}\r\n'
            f"--{grenze}\r\n"
            f'Content-Disposition: form-data; name="recipe"; filename="rezept.json"\r\n'
            f"Content-Type: application/json\r\n\r\n"
        ).encode()
        + nutzlast
        + f"\r\n--{grenze}--\r\n".encode()
    )

    anfrage = urllib.request.Request(
        basis + "?do=upload",
        data=teile,
        headers={"Content-Type": f"multipart/form-data; boundary={grenze}"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=30) as antwort:
            return antwort.status, json.loads(antwort.read())
    except urllib.error.HTTPError as fehler:
        return fehler.code, json.loads(fehler.read())


def _holen(url: str) -> tuple[int, dict]:
    try:
        with urllib.request.urlopen(url, timeout=30) as antwort:
            return antwort.status, json.loads(antwort.read())
    except urllib.error.HTTPError as fehler:
        return fehler.code, json.loads(fehler.read())


def test_a_recipe_travels_upload_confirm_list_and_download(boerse) -> None:
    """Der ganze Weg, wie ein Kunde ihn geht — und die Datei kommt zurück.

    Robert zu diesem Punkt: „die bausteine sollen einfach sauber exportiert und
    importiert werden können ohne etwas zu verlieren." Geprüft wird deshalb am
    Ende nicht der Statuscode, sondern **Byte für Byte**, dass herauskommt, was
    hineinging.
    """
    basis, postfach, _ = boerse

    status, antwort = _hochladen(basis, REZEPT)
    assert status == 200, antwort
    assert antwort["ok"] and antwort["pending"], antwort

    # Vor der Bestätigung ist nichts sichtbar — das ist die ganze Zusage der
    # Mailadresse (Konzept §3.4).
    _, liste = _holen(basis + "?do=list")
    assert liste["total"] == 0, f"unbestätigt und trotzdem in der Liste: {liste}"

    for _ in range(50):
        if postfach.nachrichten:
            break
        time.sleep(0.1)
    assert postfach.nachrichten, "es ging keine Bestätigungsmail hinaus"
    mail = postfach.nachrichten[0]
    marke = mail.split("token=")[1].split()[0].strip()
    assert len(marke) == 32, f"die Marke im Link sieht nicht aus wie eine: {marke!r}"

    status, bestätigt = _holen(basis + f"?do=confirm&token={marke}")
    assert status == 200 and bestätigt["ok"], bestätigt
    kurzname = bestätigt["slug"]

    _, liste = _holen(basis + "?do=list")
    assert liste["total"] == 1, liste
    eintrag = liste["parts"][0]
    assert eintrag["title"] == REZEPT["title"]
    assert eintrag["licence"] == "CC-BY-4.0"
    assert eintrag["has_geometry"] == 0

    with urllib.request.urlopen(basis + f"?do=download&slug={kurzname}", timeout=30) as antwort:
        zurück = antwort.read()
    assert json.loads(zurück) == REZEPT, "was herauskommt, ist nicht, was hineinging"


def test_a_file_the_check_refuses_never_reaches_the_store(boerse, tmp_path: Path) -> None:
    """Was die Prüfung ablehnt, wird nicht abgelegt — und nennt alle Gründe.

    **Die zweite Hälfte ist die wichtigere.** Eine Ablehnung, die nach jedem
    Berichtigen einen neuen Grund nennt, ist eine Kette ohne Ende; wer zweimal
    hochladen muss, um beide zu erfahren, hat die schlechtere Prüfung.
    """
    basis, _, umgebung = boerse
    schlecht = {**REZEPT, "title": "ä" * 200, "license": "WTFPL"}

    status, antwort = _hochladen(basis, schlecht)

    assert status == 422, antwort
    assert antwort["code"] == "rejected", antwort
    assert len(antwort["findings"]) == 2, f"nur ein Grund genannt: {antwort['findings']}"

    _, liste = _holen(basis + "?do=list")
    assert liste["total"] == 0, "eine abgelehnte Datei steht in der Liste"

    datenbank = Path(umgebung["SOLIDON_SHARED_DB"])
    if datenbank.is_file():
        # `with sqlite3.connect(...)` schließt **nicht** — es committet nur.
        # Unter `filterwarnings = ["error"]` wird die offene Verbindung zum
        # Fehler, und zwar erst beim Aufräumen, lange nach dem grünen Test.
        with contextlib.closing(sqlite3.connect(datenbank)) as verbindung:
            anzahl = verbindung.execute("SELECT COUNT(*) FROM parts").fetchone()[0]
        assert anzahl == 0, "die abgewiesene Datei hat trotzdem einen Datensatz angelegt"
    ordner = Path(umgebung["SOLIDON_SHARED_FILES"])
    assert not list(ordner.glob("*.json")) if ordner.is_dir() else True, (
        "die abgewiesene Datei liegt auf der Platte"
    )


def test_an_unknown_confirmation_link_says_what_to_do(boerse) -> None:
    """Regel 17 gilt auch hier: Ein toter Link endet nicht mit „abgelehnt"."""
    basis, _, _ = boerse

    status, antwort = _holen(basis + "?do=confirm&token=" + "0" * 32)

    assert status == 404, antwort
    assert not antwort["ok"]
    assert "Börse" in antwort["error"] and "nach" in antwort["error"], (
        f"der Fehler nennt keinen Weg nach vorn: {antwort['error']}"
    )


def test_a_customer_can_withdraw_what_they_uploaded(boerse, tmp_path: Path) -> None:
    """Der zweite Link aus derselben Mail — und danach ist wirklich nichts mehr da.

    `datenschutz.html` sagt zu: „Beim Hochladen und beim Kommentieren erhalten
    Sie einen Link mit einem langen Schlüssel, über den Sie Ihren Beitrag
    jederzeit selbst zurückziehen können; damit geht die Adresse mit."

    **Die Zusage stand im Rechtstext und nicht im Code** — gefunden von 72 beim
    Lesen des Schemas, nicht von einem Test: Beide Seiten waren für sich
    stimmig, und genau deshalb fällt so etwas keiner Prüfung auf.

    Geprüft wird die ganze Zusage und nicht nur der Statuscode: Der Baustein ist
    aus der Liste **und** aus der Datenbank verschwunden, die Datei ist von der
    Platte, und der Hash der Adresse ist mit ihr gegangen. Ein `hidden = 1`
    ließe ihn stehen, und er ist ein Personenbezug, solange der Startwert lebt.
    """
    basis, postfach, umgebung = boerse

    status, antwort = _hochladen(basis, REZEPT)
    assert status == 200, antwort
    for _ in range(50):
        if postfach.nachrichten:
            break
        time.sleep(0.1)
    mail = postfach.nachrichten[0]

    marke = mail.split("do=confirm&token=")[1].split()[0].strip()
    schluessel = mail.split("do=withdraw&key=")[1].split()[0].strip()
    assert len(schluessel) == 64, f"„ein langer Schlüssel“ sind 32 Byte: {schluessel!r}"
    assert schluessel != marke, "Bestätigung und Rückzug dürfen nicht derselbe Schlüssel sein"

    _holen(basis + f"?do=confirm&token={marke}")
    _, liste = _holen(basis + "?do=list")
    assert liste["total"] == 1, "der bestätigte Baustein steht nicht in der Liste"

    status, zurück = _holen(basis + f"?do=withdraw&key={schluessel}")
    assert status == 200 and zurück["ok"], zurück
    assert zurück["kind"] == "part", zurück

    _, liste = _holen(basis + "?do=list")
    assert liste["total"] == 0, "zurückgezogen und trotzdem in der Liste"

    with contextlib.closing(sqlite3.connect(umgebung["SOLIDON_SHARED_DB"])) as verbindung:
        zeilen = verbindung.execute("SELECT COUNT(*) FROM parts").fetchone()[0]
    assert zeilen == 0, "der Datensatz steht noch, also steht auch der Adress-Hash noch"
    ordner = Path(umgebung["SOLIDON_SHARED_FILES"])
    assert not list(ordner.glob("*.json")), "die Datei liegt noch auf der Platte"


def test_a_withdraw_key_that_belongs_to_nobody_says_what_to_do(boerse) -> None:
    """Ein Schlüssel ohne Beitrag endet nicht mit „abgelehnt" (Regel 17)."""
    basis, _, _ = boerse

    status, antwort = _holen(basis + "?do=withdraw&key=" + "a" * 64)

    assert status == 404, antwort
    assert "zurückgezogen" in antwort["error"], (
        f"der Fehler nennt den wahrscheinlichsten Grund nicht: {antwort['error']}"
    )


# --- Like und Kommentar ------------------------------------------------------


def _veroeffentlichen(basis: str, postfach) -> str:
    """Ein Baustein, der öffentlich steht — der Boden für alles hierunter.

    Ohne ihn prüfte jeder Test darunter gegen eine leere Börse, und „null
    Likes" wäre auch dann richtig, wenn der Endpunkt gar nichts tut.
    """
    status, antwort = _hochladen(basis, REZEPT)
    assert status == 200 and antwort["ok"], antwort
    for _ in range(50):
        if postfach.nachrichten:
            break
        time.sleep(0.1)
    assert postfach.nachrichten, "es ging keine Bestätigungsmail hinaus"
    marke = postfach.nachrichten[0].split("token=")[1].split()[0].strip()
    status, bestätigt = _holen(basis + f"?do=confirm&token={marke}")
    assert status == 200 and bestätigt["ok"], bestätigt
    postfach.nachrichten.clear()
    return str(bestätigt["slug"])


def _senden(url: str, felder: dict[str, str]) -> tuple[int, dict]:
    """Ein POST mit gewöhnlichen Formularfeldern."""
    daten = urllib.parse.urlencode(felder).encode("utf-8")
    anfrage = urllib.request.Request(
        url,
        data=daten,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(anfrage, timeout=30) as antwort:
            return antwort.status, json.loads(antwort.read())
    except urllib.error.HTTPError as fehler:
        return fehler.code, json.loads(fehler.read())


def test_a_like_counts_once_per_browser_and_part(boerse) -> None:
    """Ein Like je Kennung und Baustein — die Zusage aus ``datenschutz.html``.

    Dort steht wörtlich: „Damit dieselbe Person nicht beliebig oft dasselbe
    Teil hochzählt, legt die Seite beim ersten Like eine zufällige Kennung im
    lokalen Speicher Ihres Browsers ab und schickt sie beim Liken mit."

    Geprüft wird deshalb **beides**: dass ein zweiter Klick derselben Kennung
    nichts ändert, und dass eine andere Kennung zählt. Nur der erste Teil wäre
    auch von einem Endpunkt erfüllt, der überhaupt nicht zählt.
    """
    basis, postfach, _ = boerse
    kurzname = _veroeffentlichen(basis, postfach)

    status, erst = _senden(basis + "?do=like", {"slug": kurzname, "browser": "aaa" * 8})
    assert status == 200 and erst["ok"], erst
    assert erst["likes"] == 1, erst

    status, nochmal = _senden(basis + "?do=like", {"slug": kurzname, "browser": "aaa" * 8})
    assert status == 200, nochmal
    assert nochmal["likes"] == 1, f"derselbe Browser hat zweimal gezählt: {nochmal}"

    status, andere = _senden(basis + "?do=like", {"slug": kurzname, "browser": "bbb" * 8})
    assert status == 200 and andere["likes"] == 2, andere

    # Und die Liste zeigt dieselbe Zahl — sonst zählt der Endpunkt in eine
    # Tabelle, die niemand liest.
    _, liste = _holen(basis + "?do=list")
    assert liste["parts"][0]["likes"] == 2, liste


def test_a_like_for_a_part_that_is_not_there_says_so(boerse) -> None:
    """Ein Like ins Leere ist ein Fehler und kein stilles Ja.

    Ein Endpunkt, der auf jeden Aufruf „ok" antwortet, ist von einem, der
    wirklich zählt, an einem einzelnen Aufruf nicht zu unterscheiden.
    """
    basis, _, _ = boerse

    status, antwort = _senden(basis + "?do=like", {"slug": "gibtesnicht", "browser": "c" * 24})
    assert status == 404, antwort
    assert antwort.get("error"), antwort


def test_a_comment_stays_invisible_until_its_address_is_confirmed(boerse) -> None:
    """Dieselbe Zusage wie beim Upload, und aus demselben Grund.

    ``datenschutz.html``: „Sie wird an die angegebene Adresse bestätigt und
    danach gespeichert." Vor der Bestätigung steht der Kommentar nirgends —
    sonst wäre die Adresse eine Formalie und keine Hürde.
    """
    basis, postfach, _ = boerse
    kurzname = _veroeffentlichen(basis, postfach)

    status, antwort = _senden(
        basis + "?do=comment",
        {
            "slug": kurzname,
            "body": "Sitzt stramm auf M4, danke dafür.",
            "author": "Robert",
            "contact": "leser@beispiel.de",
        },
    )
    assert status == 200 and antwort["ok"], antwort
    assert antwort["pending"], "ein Kommentar darf nicht sofort öffentlich sein"

    _, sichtbar = _holen(basis + f"?do=comments&slug={kurzname}")
    assert sichtbar["comments"] == [], f"unbestätigt und trotzdem sichtbar: {sichtbar}"

    for _ in range(50):
        if postfach.nachrichten:
            break
        time.sleep(0.1)
    assert postfach.nachrichten, "es ging keine Bestätigungsmail hinaus"
    mail = postfach.nachrichten[0]
    marke = mail.split("token=")[1].split()[0].strip()

    status, bestätigt = _holen(basis + f"?do=confirm_comment&token={marke}")
    assert status == 200 and bestätigt["ok"], bestätigt

    _, sichtbar = _holen(basis + f"?do=comments&slug={kurzname}")
    assert len(sichtbar["comments"]) == 1, sichtbar
    eintrag = sichtbar["comments"][0]
    assert eintrag["body"] == "Sitzt stramm auf M4, danke dafür."
    assert eintrag["author"] == "Robert"


def test_the_address_of_a_comment_never_reaches_the_page(boerse) -> None:
    """„Die Adresse wird nicht angezeigt" — weder am Kommentar noch am Baustein.

    Der Satz steht so im Datenschutztext, und er ist die einzige Zusage darin,
    die sich an der **Ausgabe** prüfen lässt statt an der Ablage. Gesucht wird
    die Adresse im ganzen Antworttext und nicht in einem Feld: Ein Feld, das
    man nicht kennt, prüft man nicht.
    """
    basis, postfach, _ = boerse
    kurzname = _veroeffentlichen(basis, postfach)
    adresse = "geheim@beispiel.de"

    _senden(
        basis + "?do=comment",
        {"slug": kurzname, "body": "Passt.", "author": "R", "contact": adresse},
    )
    for _ in range(50):
        if postfach.nachrichten:
            break
        time.sleep(0.1)
    marke = postfach.nachrichten[0].split("token=")[1].split()[0].strip()
    _holen(basis + f"?do=confirm_comment&token={marke}")

    for weg in (f"?do=comments&slug={kurzname}", "?do=list"):
        with urllib.request.urlopen(basis + weg, timeout=30) as antwort:
            text = antwort.read().decode("utf-8")
        assert adresse not in text, f"die Adresse steht in {weg}"
        assert "geheim" not in text, f"der Ortsteil der Adresse steht in {weg}"


def test_a_comment_carries_the_key_that_takes_it_back(boerse) -> None:
    """Der Rückzieh-Link ist zugesagt, also reist er in der Mail mit.

    ``datenschutz.html``: „Beim Hochladen und beim Kommentieren erhalten Sie
    einen Link mit einem langen Schlüssel, über den Sie Ihren Beitrag
    jederzeit selbst zurückziehen können; damit geht die Adresse mit."

    Zwei Zusagen in einem Satz, und beide werden hier gemessen: Der Schlüssel
    steht in der Mail, und was er entfernt, ist danach weg.
    """
    basis, postfach, _ = boerse
    kurzname = _veroeffentlichen(basis, postfach)

    _senden(
        basis + "?do=comment",
        {"slug": kurzname, "body": "Doch nicht.", "author": "R", "contact": "weg@beispiel.de"},
    )
    for _ in range(50):
        if postfach.nachrichten:
            break
        time.sleep(0.1)
    mail = postfach.nachrichten[0]
    marke = mail.split("token=")[1].split()[0].strip()
    _holen(basis + f"?do=confirm_comment&token={marke}")

    assert "key=" in mail, f"kein Rückzieh-Schlüssel in der Mail: {mail[:400]}"
    schluessel = mail.split("key=")[1].split()[0].strip()
    assert len(schluessel) >= 32, f"das ist kein langer Schluessel: {schluessel!r}"

    _, vorher = _holen(basis + f"?do=comments&slug={kurzname}")
    assert len(vorher["comments"]) == 1, vorher

    status, zurück = _holen(basis + f"?do=withdraw&key={schluessel}")
    assert status == 200 and zurück["ok"], zurück

    _, nachher = _holen(basis + f"?do=comments&slug={kurzname}")
    assert nachher["comments"] == [], f"zurückgezogen und immer noch da: {nachher}"


# --- Eine Datenbank, die es schon gibt ---------------------------------------

#: Das Schema, wie es vor dem Rückziehweg aussah — als **fester Text** und
#: nicht als gekürzte Kopie von `shared_create_schema`.
#:
#: Wer das alte Schema aus der heutigen Funktion ableitet, prüft sie gegen sich
#: selbst; in einem Jahr wäre „alt" dann der Stand von heute-minus-eins statt
#: der, den es beim Kunden wirklich gibt. Abgeschrieben aus `shared_store.php`
#: vor `39e4a27b` (30.08.2026) — die Spalten `withdraw_key`, `confirm_token`
#: und `confirm_expires` fehlen hier absichtlich.
ALTES_SCHEMA = """
CREATE TABLE parts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    doc TEXT NOT NULL DEFAULT "",
    author TEXT NOT NULL DEFAULT "",
    licence TEXT NOT NULL DEFAULT "",
    size INTEGER NOT NULL,
    has_geometry INTEGER NOT NULL DEFAULT 0,
    contact_hash TEXT NOT NULL,
    created INTEGER NOT NULL,
    published INTEGER,
    hidden INTEGER NOT NULL DEFAULT 0,
    downloads INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    part_id INTEGER NOT NULL,
    body TEXT NOT NULL,
    author TEXT NOT NULL DEFAULT "",
    contact_hash TEXT NOT NULL,
    created INTEGER NOT NULL,
    published INTEGER,
    hidden INTEGER NOT NULL DEFAULT 0
);
"""


def test_a_database_that_already_exists_gets_the_new_columns(boerse, tmp_path: Path) -> None:
    """Der Fall, den kein anderer Test dieser Datei sehen kann.

    Jeder Lauf hier bekommt `SOLIDON_SHARED_DB` in einen Temp-Ordner, also
    beginnt er bei null und das Schema entsteht vollständig. **Im Betrieb ist
    die Datenbank per Definition alt** — und `CREATE TABLE IF NOT EXISTS`
    ändert eine vorhandene Tabelle nicht. `withdraw_key`, `confirm_token` und
    `confirm_expires` wären dort nie entstanden, und der Rückziehweg hätte an
    einer Spalte gescheitert, die es nach jedem Testlauf gibt.

    Geprüft wird deshalb nicht `shared_add_column`, sondern **der Weg**: eine
    Datenbank im alten Schema anlegen, den Server darüberlaufen lassen, und
    danach muss ein Kommentar durchgehen und sich zurückziehen lassen.
    """
    basis, postfach, _ = boerse

    # Der Server hat seine Datenbank beim Hochfahren schon angelegt — für den
    # Fall „alte Datenbank" muss sie weg und im alten Schema neu entstehen.
    pfad = tmp_path / "shared.sqlite"
    pfad.unlink(missing_ok=True)
    with contextlib.closing(sqlite3.connect(pfad)) as verbindung:
        verbindung.executescript(ALTES_SCHEMA)
        verbindung.commit()

    with contextlib.closing(sqlite3.connect(pfad)) as verbindung:
        spalten = {
            zeile[1] for zeile in verbindung.execute("PRAGMA table_info(comments)").fetchall()
        }
    assert "withdraw_key" not in spalten, "der Testfall stellt das alte Schema nicht her"
    assert "confirm_token" not in spalten, "der Testfall stellt das alte Schema nicht her"

    # Und jetzt der ganze Weg über den Server, der die Spalten nachziehen muss.
    kurzname = _veroeffentlichen(basis, postfach)
    status, antwort = _senden(
        basis + "?do=comment",
        {"slug": kurzname, "body": "Läuft auch auf alt.", "author": "R", "contact": "a@b.de"},
    )
    assert status == 200 and antwort["ok"], antwort

    for _ in range(50):
        if postfach.nachrichten:
            break
        time.sleep(0.1)
    mail = postfach.nachrichten[0]
    marke = mail.split("token=")[1].split()[0].strip()
    status, bestätigt = _holen(basis + f"?do=confirm_comment&token={marke}")
    assert status == 200 and bestätigt["ok"], bestätigt

    schluessel = mail.split("key=")[1].split()[0].strip()
    status, zurück = _holen(basis + f"?do=withdraw&key={schluessel}")
    assert status == 200 and zurück["ok"], zurück


def test_what_stays_unconfirmed_for_seven_days_disappears(boerse, tmp_path: Path) -> None:
    """Die Löschzusage aus `datenschutz.html`, eingelöst statt beschrieben.

    Dort steht: „Eine unbestätigte Adresse wird nach sieben Tagen gelöscht."
    Die Spalten dafür standen da, und gelöscht hat sie niemand — es gab kein
    einziges `DELETE` darauf. Eine Löschzusage ist eine Zusage und keine
    Beschreibung; gemessen wird deshalb, dass die Zeile **weg** ist, nicht dass
    eine Funktion existiert.

    Die Uhr wird nicht gestellt, sondern der Datensatz altert: `created` acht
    Tage zurück ist dasselbe Ereignis und braucht keinen Eingriff in die Zeit
    des Servers.
    """
    basis, postfach, _ = boerse
    kurzname = _veroeffentlichen(basis, postfach)

    _senden(
        basis + "?do=comment",
        {"slug": kurzname, "body": "Nie bestätigt.", "author": "R", "contact": "alt@beispiel.de"},
    )
    _hochladen(basis, REZEPT | {"name": "zweiter", "title": "Nie bestätigt"})

    pfad = tmp_path / "shared.sqlite"
    vor_acht_tagen = int(time.time()) - 8 * 86400
    with contextlib.closing(sqlite3.connect(pfad)) as verbindung:
        verbindung.execute(
            "UPDATE comments SET created = ? WHERE published IS NULL", (vor_acht_tagen,)
        )
        verbindung.execute(
            "UPDATE parts SET created = ? WHERE published IS NULL", (vor_acht_tagen,)
        )
        verbindung.commit()
        offen = verbindung.execute(
            "SELECT (SELECT COUNT(*) FROM comments WHERE published IS NULL),"
            "       (SELECT COUNT(*) FROM parts WHERE published IS NULL)"
        ).fetchone()
    assert offen == (1, 1), f"der Testfall legt nicht an, was er wegräumen lassen will: {offen}"

    # Irgendein Aufruf genügt — es gibt keinen Zeitgeber, jeder Zugriff räumt.
    _holen(basis + "?do=list")

    with contextlib.closing(sqlite3.connect(pfad)) as verbindung:
        danach = verbindung.execute(
            "SELECT (SELECT COUNT(*) FROM comments WHERE published IS NULL),"
            "       (SELECT COUNT(*) FROM parts WHERE published IS NULL),"
            "       (SELECT COUNT(*) FROM parts WHERE published IS NOT NULL)"
        ).fetchone()
    assert danach[0] == 0, "der unbestätigte Kommentar liegt nach acht Tagen immer noch da"
    assert danach[1] == 0, "der unbestätigte Baustein liegt nach acht Tagen immer noch da"
    assert danach[2] == 1, "der veröffentlichte Baustein wurde mit weggeräumt"
