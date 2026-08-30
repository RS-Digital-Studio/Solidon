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
