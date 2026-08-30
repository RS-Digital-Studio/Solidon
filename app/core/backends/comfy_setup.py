"""ComfyUI für Solidon einrichten (Bauplan §27, §36).

Solidon rechnet die Mesh-Erzeugung nicht selbst, sondern schickt einen Workflow
an ein lokales ComfyUI. Damit dieser Workflow läuft, muss auf der anderen Seite
dreierlei vorhanden sein: die Knoten, die er anspricht, das Modell, das sie
laden, und die Pakete, an denen beides hängt. Das von Hand zusammenzusuchen ist
der Punkt, an dem die meisten aufgeben — also nimmt es dieses Modul ab.

**Warum es hier steht und nicht in ``tools/``.** Dort stand es, und die
Anwendung wies auf es hin: „Einzurichten ist sie mit «python
tools/setup_comfyui.py»." Für den Kunden war das eine Sackgasse mit
Wegbeschreibung — ``tools/`` reist nicht im Paket mit, es gibt diese Datei auf
seinem Rechner nicht. Die Logik gehört also dorthin, wo sie beides erreicht:
in den Kern, den die Oberfläche aufrufen kann und der paketiert wird. Die
Kommandozeile in ``tools/setup_comfyui.py`` ist jetzt ein dünner Aufrufer
darauf und tut unverändert dasselbe.

**Was es nicht tut: ComfyUI installieren.** Das ist ein fremdes Programm mit
eigenem Installationsweg; hier wird nur eingerichtet, was Solidon braucht.
Und es startet ComfyUI nicht — der Ordner bringt sein eigenes Python mit, und
eine Anwendung, die den Startbefehl errät, startet irgendwann das Falsche.
"""

from __future__ import annotations

import json
import os
import queue
import shutil
import subprocess
import sys
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import IO, Final

from app.core import discover
from app.core.log import get_logger
from app.i18n import TranslatableText, _

_log = get_logger(__name__)

#: Die Knoten reisen als Daten mit — neben den Workflows, die sie ansprechen.
#: In der Spec deckt der Eintrag für ``app/core/backends/data`` beide ab.
NODE_SOURCE: Final = Path(__file__).parent / "data" / "comfyui" / "ComfyUI-TripoSG-Solidon"
NODE_NAME: Final = "ComfyUI-TripoSG-Solidon"

TRIPOSG_REPO: Final = "https://github.com/VAST-AI-Research/TripoSG.git"
WEIGHTS_REPO: Final = "VAST-AI/TripoSG"

#: Das Freistell-Modell, ohne das der Bildweg nicht läuft: TripoSG will ein
#: freigestelltes Objekt, kein Lichtbild mit Zimmer dahinter.
#:
#: **Hier stand ein GPL-Knoten, und das war ein Regelverstoß.** Der Ablauf
#: sprach ``RMBG`` aus ``ComfyUI-RMBG`` an — GPL-3.0, und Regel 15 lässt keine
#: GPL-Abhängigkeit zu. Aufgefallen ist es erst, als der Weg zum ersten Mal
#: wirklich gefahren wurde: Der Knoten fehlte, und beim Nachsehen, woher er
#: kommt, stand die Lizenz in seiner ersten Zeile.
#:
#: ComfyUI kann es seit 0.33 selbst — ``LoadBackgroundRemovalModel`` und
#: ``RemoveBackground``, beide eingebaut. Damit fällt nicht nur die Lizenzfrage
#: weg, sondern auch ein Installationsschritt: Es fehlt nur noch die
#: Gewichtsdatei. Ein älteres ComfyUI kennt die Knoten nicht, und dann sagt
#: :meth:`ComfyBackend.missing_nodes` ihre Namen — das ist der richtige Weg
#: dafür und keine zweite Version des Ablaufs.
BACKGROUND_REPO: Final = "Comfy-Org/BiRefNet"
BACKGROUND_FILE: Final = "background_removal/birefnet.safetensors"

#: Das Bildmodell für den **Textweg** — und der einzige Posten dieser Liste,
#: den Solidon **nicht** selbst holt.
#:
#: **Warum es hier steht, obwohl nichts es lädt.** Aus Text wird erst ein Bild,
#: und dafür braucht ComfyUI ein SDXL-Modell unter ``models/checkpoints``. Wer
#: nur Bilder mitbringt, braucht es nie — sieben Gigabyte für einen Weg, den
#: ein vorhandenes Foto umgeht, gehören nicht in jede Installation. Bis zum
#: 30.08.2026 stand deshalb nirgends, **welches**: Der Erzeugungsdialog sagte,
#: dass eines fehlt, das Handbuch nannte es „ComfyUIs eigene Sache", und der
#: Kunde stand vor einer Auskunft ohne Weg.
#:
#: Genannt wird das Basismodell und kein Feintuning: Es ist das, was die
#: Rollenauflösung in :data:`app.core.backends.mesh.MODEL_ROLES` über ``sd_xl``
#: sicher trifft, es ist die Referenz, und seine Lizenz
#: (CreativeML Open RAIL++-M) wirft für den lokalen Gebrauch keine Frage auf —
#: anders als bei Hunyuan, dessen Lizenz die EU ausnimmt. Wer ein anderes
#: bevorzugt, legt es daneben: ``juggernaut`` und ``dreamshaper`` stehen in der
#: Rangfolge davor und gewinnen dann.
IMAGE_MODEL_REPO: Final = "stabilityai/stable-diffusion-xl-base-1.0"
IMAGE_MODEL_FILE: Final = "sd_xl_base_1.0.safetensors"
IMAGE_MODEL_GIGABYTES: Final = 6.9

#: Wohin es gehört, von ComfyUIs Ordner aus gerechnet. Als Konstante, weil
#: derselbe Pfad in drei Sätzen steht — Dialog, Handbuch, Fehlermeldung.
IMAGE_MODEL_FOLDER: Final = "models/checkpoints"

#: Wie groß die Freistell-Gewichte sind — 444 MB gegen 7,5 GB, also nennt der
#: Schritt sie zusammen und nicht getrennt.
#:
#: **Die Zahl steht auch im Fortschrittstext, und zwar dort von Hand.** Diese
#: Konstante las bis zum 24.08.2026 niemand; sie und ``WEIGHT_GIGABYTES`` waren
#: zwei stille Zweitschriften. Der Text bleibt, wie er ist — die Zahl in die
#: Message-ID hineinzuformatieren (wie ``NEEDED_GIGABYTES`` es weiter unten
#: richtig macht) kostet fünf Übersetzungen für zwei Sätze. Stattdessen hält
#: `tests/test_mesh_backend.py::test_the_sizes_in_the_progress_text_match_the_constants`
#: beide Stellen zusammen: Wer die Größe hier nachzieht und den Text vergisst,
#: bekommt einen roten Lauf.
BACKGROUND_MEGABYTES: Final = 445

#: Was auf der Platte frei sein muss, bevor der große Download beginnt.
#:
#: 7,5 GB Gewichte, dazu Luft für das, was ``huggingface_hub`` beim Entpacken
#: zwischenlagert. Geprüft wird **vorher** und nicht im Fehlerfall, und das ist
#: der Punkt: Am 23.08.2026 lief der Download dreimal an und starb dreimal nach
#: Minuten, weil ``C:`` voll war. Die Meldung, die dabei herauskam, nennt den
#: Grund mit keinem Wort:
#:
#:     RuntimeError: File reconstruction error: Internal Writer Error:
#:     Background writer channel closed
#:
#: Wer sie liest, sucht am Netz. Gefunden wurde es nur, weil der Abbruch
#: **dreimal an derselben Stelle** kam.
NEEDED_GIGABYTES: Final = 9.0

#: Woran der TripoSG-Quelltext hängt und was eine ComfyUI-Installation nicht
#: ohnehin mitbringt. ``fast_simplification`` steht hier statt ``pymeshlab``:
#: dasselbe Können, aber MIT statt GPL (Regel 15).
#:
#: **Die Liste war zu kurz, und das fiel nicht auf.** Sie nannte drei Pakete,
#: gemessen an einer Installation, in der andere Knoten das übrige längst
#: mitgebracht hatten. Auf einem frischen ComfyUI Desktop fehlten sechs
#: weitere, und die Einrichtung meldete trotzdem „fertig" — der Fehler kam
#: erst beim Erzeugen, als ComfyUI den Knoten zu laden versuchte. Gefunden
#: wurden sie einzeln, indem der Knoten geladen wurde, bis er lud; genau das
#: prüft :func:`nodes_load` seither am Ende jeder Einrichtung.
#:
#: ``antlr4-python3-runtime`` trägt eine Version, und die ist kein
#: Übervorsicht: ``omegaconf`` liest damit einen vorkompilierten Automaten,
#: und die 4.13 serialisiert ihn anders — „Could not deserialize ATN with
#: version 3 (expected 4)" ist der Satz, den es sonst sagt.
#:
#: **Die Lizenzen stehen in der Freigabeliste**, nicht in diesem Kommentar:
#: ``knowledge/data/licences.toml`` führt jedes dieser Pakete samt Lizenz, und
#: ``tests/test_licences.py`` hält die beiden Listen zusammen. Hier stand
#: einmal „alle Lizenzen sind geprüft" — genau so eine Behauptung war der
#: GPL-Knoten ``RMBG``: wahr gemeint, von keinem Test gehalten (Regel 22).
PACKAGES: Final = (
    "jaxtyping",
    "typeguard",
    "fast-simplification",
    "trimesh",
    "diffusers",
    "scikit-image",
    "lazy_loader",
    "omegaconf",
    "antlr4-python3-runtime==4.9.3",
)


#: Wo ComfyUI erfahrungsgemäß liegt, wenn niemand etwas anderes sagt.
#:
#: Die tragbare Version entpackt der Nutzer selbst, also steht sie dort, wohin
#: er sie gelegt hat — geraten wird an den drei Stellen, an denen sie
#: erfahrungsgemäß landet. **ComfyUI Desktop** dagegen wählt selbst, und die
#: Wahl steht in seiner eigenen Aufstellung: :func:`_from_desktop` liest sie
#: und schlägt deshalb auch dann an, wenn der Nutzer beim Installieren einen
#: anderen Ort angegeben hat.
def guesses_for(platform: str) -> tuple[Path, ...]:
    """Wo ComfyUI auf dieser Plattform erfahrungsgemäß liegt.

    Eine Funktion und keine Liste mit ``if sys.platform``, aus demselben Grund
    wie :func:`app.core.discover.parts_for`: Die Zuordnung ist damit von
    **jeder** Maschine aus prüfbar. Eine Liste, deren Linux-Pfade nur unter
    Linux zu sehen sind, wird nirgends geprüft.

    Die drei Laufwerkspfade waren bis zum 27.08.2026 die ganze Liste — auf
    Linux und macOS ist ``Path("F:/AI/...")`` ein *relativer* Pfad namens
    „F:", also blieben dort zwei Rateorte übrig. ``~/comfy/ComfyUI`` fehlte
    dabei ganz, und das ist der Ort, an den ``comfy-cli`` von sich aus
    installiert.
    """
    home = Path.home()
    common = (home / "comfy" / "ComfyUI", home / "ComfyUI", home / "Documents" / "ComfyUI")
    if platform == "win32":
        return (
            Path("F:/AI/ComfyUI_windows_portable/ComfyUI"),
            Path("D:/AI/ComfyUI_windows_portable/ComfyUI"),
            Path("C:/ComfyUI_windows_portable/ComfyUI"),
            *common,
        )
    if platform == "darwin":
        return (*common, home / "Applications" / "ComfyUI", Path("/Applications/ComfyUI"))
    return (*common, home / ".local" / "share" / "ComfyUI", Path("/opt/ComfyUI"))


GUESSES: Final = guesses_for(sys.platform)

#: Wo ComfyUI Desktop notiert, was es wohin installiert hat. Ein Eintrag je
#: Installation, und ``installPath`` ist der Ordner **über** dem eigentlichen
#: ComfyUI — dieselbe Verschachtelung, die :func:`find_comfyui` beim Nutzer
#: ohnehin annimmt.
DESKTOP_RECORD: Final = "Comfy Desktop/installations.json"

#: Ein Schritt darf lange dauern — die Gewichte sind 7,5 GB.
STEP_TIMEOUT_SECONDS: Final = 3600.0

#: Wie groß die Gewichte sind. Steht im Fortschrittstext, weil „das dauert"
#: ohne Zahl niemandem sagt, ob er Kaffee holen kann.
WEIGHT_GIGABYTES: Final = 7.5

ProgressFn = Callable[[TranslatableText | str], None]
CancelledFn = Callable[[], bool]


def scratch_dir(name: str) -> Path:
    """Ein Zwischenordner für einen Download — im Nutzer-Cache, nicht im Temp.

    **Ein fester Name im gemeinsamen Temp gehört nicht uns.** Unter Linux ist
    ``/tmp`` für alle Konten schreibbar; wer ``/tmp/solidon-triposg`` vorher
    anlegt und behält, bestimmt, was hier nach 7,5 GB Download nach ``models``
    verschoben wird. Der Nutzer-Cache gehört dem Nutzer — dieselbe Wurzel, in
    die auch die Arbeitsordner eingesperrter Programme gehen
    (:func:`app.core.discover.workspace_for`).

    Der Name bleibt **fest**, und das ist Absicht: Ein abgebrochener Download
    soll beim nächsten Lauf fortsetzen, und das kann er nur, wenn seine
    Bruchstücke da liegen, wo er sie sucht (:data:`_FETCH_WEIGHTS`).

    Kurz muss er außerdem sein — Windows deckelt einen Pfad bei 260 Zeichen,
    und ``huggingface_hub`` hängt bis zu 163 davon selbst an. Der Cache misst
    gemessen 55 Zeichen gegen 45 bei ``tempfile``; die zehn sind bezahlbar,
    ein sprechender Ordnername wären es nicht.
    """
    from app.core.paths import ensure_dir, user_cache_dir

    return ensure_dir(user_cache_dir() / name)


def _silent(step: TranslatableText | str) -> None:
    del step


class Cancelled(RuntimeError):
    """Der Nutzer hat abgebrochen — kein Fehler, und nie als einer gezeigt.

    Dieselbe Rolle wie ``errors.OperationCancelled`` im Kern: Sie unterbricht
    einen Schritt, der Minuten läuft, und wird oben in die Auskunft
    umgewandelt, dass ein neuer Lauf fortsetzt.
    """


class SetupFailed(RuntimeError):
    """Etwas fehlt, und der Text sagt, was zu tun ist.

    Kein ``AppError``: Dieses Modul wird auch von der Kommandozeile aufgerufen,
    und dort ist eine Zeichenkette die ganze Ausgabe. Die Oberfläche fängt sie
    und macht daraus, was §2.7 verlangt.
    """


@dataclass(frozen=True, slots=True)
class Result:
    """Was eingerichtet wurde, und was gegebenenfalls noch fehlt."""

    comfyui: Path
    nodes: Path
    weights: bool
    reason: TranslatableText | str = ""

    @property
    def done(self) -> bool:
        return not self.reason


def _config_home(platform: str = sys.platform) -> Path:
    """Der Ort, an dem Electron-Anwendungen ihre Einstellungen ablegen.

    Die Plattform ist ein **Parameter** und kein ``sys.platform`` mitten im
    Code, und das aus zwei Gründen: So ist die Zuordnung von jeder Maschine aus
    prüfbar, auch von der, die gerade die andere Plattform nicht ist — und
    mypy hält die beiden anderen Zweige sonst für unerreichbar und meldet
    genau das. Dieselbe Bauart wie ``discover.parts_for``.
    """
    if platform == "win32":
        appdata = os.environ.get("APPDATA")
        return Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
    if platform == "darwin":
        return Path.home() / "Library" / "Application Support"
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")


def _desktop_record() -> Path:
    """Wo ComfyUI Desktop seine Aufstellung führt — je Plattform anders."""
    return _config_home() / DESKTOP_RECORD


def _from_desktop() -> list[Path]:
    """Was ComfyUI Desktop installiert hat, laut eigener Aufstellung.

    **Der Weg, den ein Kunde am ehesten geht, war der einzige, den wir nicht
    kannten.** ``comfy.org`` bietet die Desktop-Anwendung als Erstes an; sie
    legt ihr ComfyUI sechs Ebenen tief unter ``AppData/Local/Comfy-Desktop/``
    ab, und keine der geratenen Stellen trifft das. Wer sie installiert hatte,
    las bei uns „an den üblichen Stellen nicht gefunden" — und wir hatten die
    Antwort vor uns liegen: Die Anwendung schreibt ihren Installationsordner in
    eine eigene Datei, samt dem Ort, den der Nutzer im Installer gewählt hat.

    Gelesen wird tolerant. Diese Datei gehört jemand anderem, ihr Aufbau ist
    nirgends zugesagt, und eine Anwendung, die daran scheitert, wäre schlechter
    als eine, die einfach weiter rät.
    """
    record = _desktop_record()
    try:
        listed = json.loads(record.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    if not isinstance(listed, list):
        return []
    found: list[Path] = []
    for entry in listed:
        if not isinstance(entry, dict):
            continue
        where = entry.get("installPath")
        if isinstance(where, str) and where:
            found.append(Path(where))
    _log.info("comfy desktop lists %d installation(s)", len(found))
    return found


def find_comfyui(given: str | Path | None = None) -> Path:
    """Der Ordner, in dem ``main.py`` und ``custom_nodes`` liegen."""
    if given:
        path = Path(given)
        # Ein Nutzer zeigt genauso oft auf den Ordner darüber wie auf den
        # richtigen. Beides anzunehmen kostet zwei Zeilen und spart eine
        # Rückfrage.
        for candidate in (path, path / "ComfyUI"):
            if (candidate / "custom_nodes").is_dir():
                return candidate
        raise SetupFailed(
            str(
                _(
                    "Dort liegt kein ComfyUI — erwartet wird ein Ordner, in dem "
                    "„custom_nodes“ steht."
                )
            )
        )

    # Die Desktop-Version steht vorn, weil sie nicht geraten ist: Sie hat es
    # selbst aufgeschrieben. Und dieselbe Verschachtelung wie beim Nutzer —
    # ``installPath`` nennt den Ordner darüber.
    for listed in _from_desktop():
        for candidate in (listed / "ComfyUI", listed):
            if (candidate / "custom_nodes").is_dir():
                return candidate
    for candidate in GUESSES:
        if (candidate / "custom_nodes").is_dir():
            return candidate
    raise SetupFailed(
        str(
            _(
                "ComfyUI ist an den üblichen Stellen nicht gefunden worden. Der "
                "Ordner lässt sich angeben — gesucht wird der, in dem "
                "„custom_nodes“ steht."
            )
        )
    )


def find_python(comfyui: Path) -> Path:
    """Der Interpreter, mit dem ComfyUI selbst läuft.

    Nicht der, mit dem Solidon läuft: Eine tragbare Installation bringt ihr
    eigenes Python mit, und ein Paket im falschen kommt dort nie an, wo es
    gebraucht wird. Im gebauten Paket gibt es unser Python ohnehin nicht als
    Interpreter — dann bleibt nur der von ComfyUI, und ohne ihn hält die
    Einrichtung an, statt in die Leere zu installieren.
    """
    portable = comfyui.parent / "python_embeded" / "python.exe"
    if portable.is_file():
        return portable
    for name in ("venv", ".venv"):
        for relative in (f"{name}/Scripts/python.exe", f"{name}/bin/python"):
            candidate = comfyui / relative
            if candidate.is_file():
                return candidate
    if getattr(sys, "frozen", False):
        raise SetupFailed(
            str(
                _(
                    "In diesem ComfyUI ist kein eigenes Python zu finden. Die "
                    "Pakete für TripoSG müssen in die Umgebung, mit der ComfyUI "
                    "läuft — welche das ist, weiß Solidon hier nicht."
                )
            )
        )
    _log.info("no python inside %s, using %s", comfyui, sys.executable)
    return Path(sys.executable)


#: Wie oft nachgesehen wird, ob abgebrochen wurde oder die Frist steht — auch
#: wenn der Kindprozess gerade nichts sagt. Kurz genug, dass ein Klick auf
#: *Abbrechen* sofort wirkt, lang genug, dass die Schleife nichts kostet.
WATCH_SECONDS: Final = 0.2


def _pump(stream: IO[str], sink: queue.Queue[str | None]) -> None:
    """Liest den Kindprozess leer und legt jede Zeile in die Warteschlange.

    In einem eigenen Faden, weil das Lesen blockiert und ein schweigender
    Prozess beliebig lange schweigt. ``None`` heißt „der Strom ist zu Ende" —
    das ist das Signal, auf das :func:`_run` seine Schleife verlässt.

    Der Faden ist ein Daemon und hält beim Beenden nichts auf: Wird der Prozess
    getötet, endet der Strom von selbst; endet er nicht, geht der Faden mit dem
    Programm.
    """
    try:
        for raw in stream:
            sink.put(raw)
    finally:
        sink.put(None)


def _run(
    command: list[str],
    what: TranslatableText | str,
    progress: ProgressFn,
    cancelled: CancelledFn | None = None,
) -> None:
    """Einen Schritt laufen lassen — abbrechbar, mitten drin.

    **``subprocess.run`` machte „Abbrechen" beim längsten Schritt wirkungslos.**
    Es blockiert bis zum Ende des Prozesses; die Abbruchprüfung lag *zwischen*
    den Schritten, und einer davon lädt 7,5 GB. Wer abbrach, wartete eine halbe
    Stunde auf einen Download, den er nicht mehr wollte — und der Satz daneben
    („der laufende Schritt läuft aus") war wahr und keine Hilfe.

    Gelesen wird zeilenweise, und zwischen den Zeilen wird gefragt. Ein Abbruch
    beendet den Kindprozess: ``huggingface_hub`` lässt teilweise geladene
    Dateien liegen und setzt beim nächsten Lauf fort, also kostet er nichts als
    die Zeit, die schon vergangen ist.

    **„Zwischen den Zeilen" reichte nicht, denn manche Schritte schweigen.**
    ``for raw in process.stdout`` blockiert, bis eine Zeile kommt — kommt keine,
    kam auch die Abbruchprüfung nicht dran, und die Frist genauso wenig. Ein
    Kindprozess, der ohne Ausgabe hängt (ein Klon, der auf eine Anmeldung
    wartet, ein Download hinter einer toten Verbindung), fror damit die
    Einrichtung ein: *Abbrechen* wirkte nicht, und die Stunde aus
    :data:`STEP_TIMEOUT_SECONDS` verstrich nie, weil niemand auf die Uhr sah.

    Deshalb liest ein eigener Faden (:func:`_pump`), und diese Schleife wartet
    mit Zeitscheibe: Alle :data:`WATCH_SECONDS` wird gefragt, ob abgebrochen
    wurde und ob die Frist steht — mit Ausgabe oder ohne.
    """
    progress(what)
    _log.info("comfy setup: %s", command[0])
    lines: list[str] = []
    deadline = time.monotonic() + STEP_TIMEOUT_SECONDS
    # **Die Einrichtung läuft auf dem Rechner, nicht im Sandkasten.** ComfyUI
    # liegt dort, ``git`` liegt dort, und das Python, mit dem installiert wird,
    # auch. Ohne ``on_host`` endet die Einrichtung in einem Flatpak an „git
    # fehlt" — auf einem Rechner, auf dem git installiert ist.
    launched = discover.on_host(list(command))
    try:
        with subprocess.Popen(
            launched,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            stdin=subprocess.DEVNULL,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        ) as process:
            assert process.stdout is not None
            sink: queue.Queue[str | None] = queue.Queue()
            reader = threading.Thread(
                target=_pump, args=(process.stdout, sink), name="comfy-setup", daemon=True
            )
            reader.start()
            while True:
                try:
                    raw = sink.get(timeout=WATCH_SECONDS)
                except queue.Empty:
                    raw = ""
                if raw is None:
                    break
                line = raw.strip()
                if line:
                    lines.append(line)
                if cancelled is not None and cancelled():
                    process.kill()
                    raise Cancelled(str(what))
                if time.monotonic() > deadline:
                    process.kill()
                    raise SetupFailed(f"{what}: " + str(_("Der Schritt hat zu lange gebraucht.")))
            code = process.wait()
    except (OSError, subprocess.SubprocessError) as problem:
        raise SetupFailed(f"{what}: {problem}") from problem
    if code:
        raise SetupFailed(str(what) + chr(10) + chr(10).join(lines[-6:]))


#: Wie oft ein Download wiederholt wird, bevor er als gescheitert gilt.
DOWNLOAD_TRIES: Final = 3

#: Wie lange zwischen zwei Anläufen gewartet wird.
RETRY_SECONDS: Final = 5.0


def _run_repeatedly(
    command: list[str],
    what: TranslatableText | str,
    progress: ProgressFn,
    cancelled: CancelledFn | None = None,
) -> None:
    """Einen Download mehrmals versuchen — jedes Mal in einem **neuen Prozess**.

    **Die Schleife stand zuerst im Programm selbst, und dort konnte sie nichts
    bewirken.** ``huggingface_hub`` hält einen globalen HTTP-Client; sobald ein
    Fehler ihn schließt, antwortet jeder weitere Versuch im selben Prozess mit
    „Cannot send a request, as the client has been closed" — der zweite Anlauf
    scheiterte also schneller als der erste und aus einem anderen Grund.
    Gemessen an drei Abbrüchen auf einer wackeligen Leitung; bei 7,5 GB ist das
    der Normalfall und nicht das Pech.

    Ein neuer Prozess hat einen neuen Client. Und weil das Halbgeladene in
    einem Ordner mit festem Namen liegt, kostet der neue Anlauf nur, was noch
    fehlt.
    """
    for attempt in range(DOWNLOAD_TRIES):
        try:
            _run(command, what, progress, cancelled)
            return
        except SetupFailed:
            if attempt == DOWNLOAD_TRIES - 1:
                raise
            progress(_("Abgebrochen — neuer Anlauf, es geht dort weiter, wo es stand."))
            _log.info("download attempt %d failed, retrying", attempt + 1)
            time.sleep(RETRY_SECONDS)


def copy_nodes(comfyui: Path, progress: ProgressFn = _silent) -> Path:
    """Die Solidon-Knoten in ``custom_nodes`` legen."""
    if not NODE_SOURCE.is_dir():
        raise SetupFailed(str(_("Die Knoten fehlen in dieser Installation von Solidon.")))
    progress(_("Knoten hinlegen"))
    target = comfyui / "custom_nodes" / NODE_NAME
    target.mkdir(parents=True, exist_ok=True)
    for name in ("nodes.py", "__init__.py"):
        shutil.copy2(NODE_SOURCE / name, target / name)
    _log.info("nodes copied to %s", target)
    return target


def fetch_triposg(
    target: Path, progress: ProgressFn = _silent, cancelled: CancelledFn | None = None
) -> None:
    """Den TripoSG-Quelltext neben die Knoten holen."""
    if (target / "triposg").is_dir():
        return
    # Gefragt wird über ``discover``, nicht über ``shutil.which``: Im Flatpak
    # liegt git auf dem Rechner, und ``which`` sieht nur den Sandkasten. Die
    # Meldung darunter schickte den Kunden sonst zu einer Installation, die er
    # längst hat.
    if discover.find_program("git", ("git",)) is None:
        raise SetupFailed(
            str(
                _(
                    "Für den TripoSG-Quelltext wird git gebraucht. Entweder git "
                    "installieren, oder das Verzeichnis „triposg“ von Hand neben "
                    "die Knoten legen — woher, steht in der Doku."
                )
            )
        )
    scratch = target / "_clone"
    _run(
        ["git", "clone", "--depth", "1", TRIPOSG_REPO, str(scratch)],
        _("TripoSG holen"),
        progress,
        cancelled,
    )
    shutil.move(str(scratch / "triposg"), str(target / "triposg"))
    for extra in ("LICENSE", "NOTICE"):
        if (scratch / extra).is_file():
            shutil.copy2(scratch / extra, target / f"{extra}-TripoSG")
    shutil.rmtree(scratch, ignore_errors=True)


#: Die Stellen, an denen der TripoSG-Quelltext eine NVIDIA-Karte voraussetzt,
#: obwohl er keine bräuchte. Jede ist mechanisch: Was dort steht, meint „das
#: Gerät, auf dem gerechnet wird", und schreibt „cuda".
#:
#: **Gefunden, weil der Bildweg auf einer Intel-Arc-Grafik abbrach**: „Torch
#: not compiled with CUDA enabled", gemeldet von ``TripoSGImageToMesh``. Unser
#: eigener Knoten fragt ComfyUI nach dem Gerät (``get_torch_device``) und ist
#: damit richtig; der geholte Quelltext fragt nicht.
#:
#: Ob TripoSG auf einer solchen Karte danach wirklich **rechnet**, ist eine
#: andere Frage als ob es startet — der Flicken nimmt ihm nur die Annahme.
_DEVICE_FIXES: Final = (
    # **Kein Kommentar am Zeilenende.** Der erste Versuch hängte „# von
    # Solidon" an, und die Zeile ging weiter: ``dtype`` und ``requires_grad``
    # standen dahinter und waren damit wegkommentiert, die Klammer blieb offen.
    # ComfyUI meldete „'(' was never closed", und die ganze Sammlung fiel aus.
    # Gefangen hat es :func:`nodes_load` — der Beleg dafür, dass der Schritt
    # hingehört.
    (
        "device='cuda', dtype=torch.float16",
        "device=edge_coords.device, dtype=torch.float16",
    ),
    (
        'with torch.autocast(device_type="cuda", dtype=torch.float32):',
        "with torch.autocast(device_type=queries.device.type, dtype=torch.float32):",
    ),
    # ``empty_cache`` steht viermal darin und wirft ohne CUDA. Der Aufruf ist
    # eine Aufräumbitte und nie notwendig — also wird er zu einer, die fragt.
    (
        "torch.cuda.empty_cache()",
        "torch.cuda.empty_cache() if torch.cuda.is_available() else None  # von Solidon",
    ),
)


def _fix_devices(path: Path) -> bool:
    """Die CUDA-Annahmen in einer Datei richten. Liefert, ob etwas geschah.

    Jede Ersetzung prüft **die Wirkung** und nicht den eigenen Kommentar: Wer
    den Marker sucht, den er selbst geschrieben hat, flickt eine von Hand
    geänderte Datei ein zweites Mal. Und keine ist Pflicht — der Quelltext
    kommt aus einem fremden Repositorium und darf sich ändern, ohne dass die
    Einrichtung deshalb anhält.
    """
    text = original = path.read_text(encoding="utf-8")
    for wanted, fixed in _DEVICE_FIXES:
        if fixed in text or wanted not in text:
            continue
        text = text.replace(wanted, fixed)
    if text == original:
        return False
    path.write_text(text, encoding="utf-8")
    return True


def patch_sources(target: Path, progress: ProgressFn = _silent) -> None:
    """Die Stellen richten, an denen der Quelltext hier nicht durchläuft.

    Alle sind angesagt und werden vor dem Schreiben geprüft: Wer den Ordner
    später neu holt, bekommt sie erneut, und wer sie schon hat, bekommt sie
    nicht zweimal.
    """
    progress(_("Stellen im Quelltext richten"))
    utils = target / "triposg" / "inference_utils.py"
    text = utils.read_text(encoding="utf-8")
    # Geprüft wird die Wirkung, nicht der eigene Kommentar: Wer den Marker
    # sucht, den er selbst geschrieben hat, patcht eine von Hand geänderte
    # Datei ein zweites Mal und macht aus ihr Bruch.
    if "try:\n    from diso import DiffDMC" not in text:
        alternative = "from diso import DiffDMC\n"
        if alternative not in text:
            raise SetupFailed(f"{utils.name}: " + str(_("Der erwartete Import steht nicht darin.")))
        text = text.replace(
            alternative,
            "# Von Solidon angepasst: diso ist eine CUDA-Erweiterung ohne\n"
            "# Windows-Wheel und wird nur im Flash-Decoder-Pfad gebraucht.\n"
            "try:\n"
            "    from diso import DiffDMC\n"
            "except ImportError:  # von Solidon\n"
            "    DiffDMC = None\n",
            1,
        )
        utils.write_text(text, encoding="utf-8")

    vae = target / "triposg" / "models" / "autoencoders" / "autoencoder_kl_triposg.py"
    text = vae.read_text(encoding="utf-8")
    if "self.embedder(queries).to(" not in text:
        alternative = "            queries = self.embedder(queries)\n"
        if alternative not in text:
            raise SetupFailed(f"{vae.name}: " + str(_("Der erwartete Aufruf steht nicht darin.")))
        text = text.replace(
            alternative,
            "            # von Solidon: Typ zurückholen — der Fourier-Embedder\n"
            "            # gibt float32 zurück, die nächste Linearschicht trägt\n"
            "            # halbe Gewichte und bricht sonst ab.\n"
            "            queries = self.embedder(queries).to(dtype=z.dtype)\n",
            1,
        )
        vae.write_text(text, encoding="utf-8")

    for path in (utils, vae):
        if _fix_devices(path):
            _log.info("device assumptions fixed in %s", path.name)


def install_packages(
    python: Path, progress: ProgressFn = _silent, cancelled: CancelledFn | None = None
) -> None:
    """Die fehlenden Pakete nachziehen, ohne die Installation umzubauen.

    ``--no-deps`` ist hier kein Geiz, sondern Notwehr: Die Anforderungsliste
    von TripoSG nennt ``numpy==1.22.3``, und wer das durchlässt, hat danach ein
    ComfyUI, das nicht mehr startet.
    """
    _run(
        [str(python), "-s", "-m", "pip", "install", "--no-deps", *PACKAGES],
        _("Pakete für TripoSG nachziehen"),
        progress,
        cancelled,
    )


def weights_present(comfyui: Path) -> bool:
    """Liegen die Gewichte schon da?"""
    return (comfyui / "models" / "triposg" / "TripoSG" / "model_index.json").is_file()


#: Das Programm, das die Gewichte holt. Es steht hier als Text, weil es im
#: Python **von ComfyUI** laufen muss und nicht in unserem (siehe
#: :func:`find_python`) — und weil der Umweg über einen kurzen Ordner eine
#: Begründung braucht, die in keinen Einzeiler passt.
#:
#: **Der Umweg ist Windows.** ``huggingface_hub`` legt seine halbfertigen
#: Dateien unter ``<Ziel>/.cache/huggingface/download/<Ordner>/`` ab, und deren
#: Namen sind rund 130 Zeichen lang — Prüfsumme, Etag, Endung. Zusammen mit dem
#: Installationspfad von ComfyUI Desktop, das sein ComfyUI sechs Ebenen tief
#: unter ``AppData\Local`` ablegt, waren das gemessene 261 Zeichen. ``MAX_PATH``
#: ist 260. **Ein Zeichen**, und der Kunde bekam mitten im 7,5-GB-Download
#: einen ``FileNotFoundError`` mit einem Pfad, den kein Mensch liest.
#:
#: Zwei Auswege wurden verworfen und einer gewählt. ``LongPathsEnabled`` in der
#: Registrierung ist eine Systemeinstellung und gehört keiner Anwendung; das
#: Präfix ``\\?\`` half gemessen nicht (derselbe ``FileNotFoundError``).
#: Bleibt der Umweg über einen wirklich kurzen Ordner — und „kurz" heißt hier
#: gemessen: HFs Anhang war 163 Zeichen, das Ziel 98, zusammen die 261.
#: ``tempfile`` liefert rund 45, also 208 und mit Abstand unter der Grenze. Ein
#: Ordner *neben* dem Ziel wäre nur vier Zeichen kürzer gewesen als ``TripoSG``
#: selbst und hätte beim nächsten tieferen Installationspfad wieder gerissen.
#:
#: Der Preis steht dazu: Liegt der Temp-Ordner auf einem anderen Laufwerk als
#: ComfyUI, ist das Verschieben ein Kopieren von 7,5 GB. Deshalb sagt der
#: Schritt es an, statt still zu stehen — das ``print`` unten läuft in
#: **ComfyUIs** Python, und :func:`_run` liest dessen Ausgabe Zeile für Zeile
#: in ``progress``. Es ist der Fortschritt, keine Ausgabe aus dem Kern.
#:
#: **Der Ordner liegt im Nutzer-Cache, nicht im gemeinsamen Temp.** Er lag
#: dort, unter festem Namen — und ein fester Name im gemeinsamen Temp ist unter
#: Linux von jedem anderen Konto vorbelegbar: Wer ``/tmp/solidon-triposg``
#: anlegt und behält, entscheidet, was hier 7,5 GB später nach ``models``
#: verschoben wird. Der Pfad kommt deshalb von :func:`app.core.paths.user_cache_dir`
#: und wird als Argument übergeben — dieses Programm läuft in **ComfyUIs**
#: Python und hat unseren Kern nicht auf dem Suchpfad.
#:
#: Der Ordner bleibt damit kurz genug: gemessen 55 Zeichen für den Cache statt
#: 45 für ``tempfile``, und die Grenze liegt bei 260 (siehe oben).
#:
#: **Der Ordner trägt einen festen Namen, und das ist der Punkt.** Er hieß
#: zuerst ``mkdtemp``, also jedes Mal anders, und ein ``finally`` räumte ihn
#: auf. Beides zusammen machte die Zusage im Docstring von :func:`setup` zur
#: Lüge: „setzt beim nächsten Lauf fort" — fortgesetzt wurde nichts, das
#: Halbgeladene war gelöscht und lag beim nächsten Versuch woanders. Gemessen
#: an drei Abbrüchen hintereinander auf einer wackeligen Leitung (``WinError
#: 10054``, dann 2 GB weit, dann ``WinError 10038``); bei 7,5 GB ist das der
#: Normalfall und nicht das Pech. Aufgeräumt wird jetzt nur, was gelungen ist.
#:
#: Und wiederholt wird von hier aus, drei Anläufe: ``huggingface_hub`` setzt je
#: Datei fort, also kostet ein neuer Anlauf nur das, was noch fehlt. Ein
#: Abbruch von außen kommt durch — ``_run`` beendet den Prozess, und eine
#: Schleife im Kind hält das nicht auf.
_FETCH_WEIGHTS = """
import shutil, sys
from pathlib import Path
from huggingface_hub import snapshot_download

target = Path(sys.argv[1])
scratch = Path(sys.argv[3])
scratch.mkdir(parents=True, exist_ok=True)
snapshot_download(sys.argv[2], local_dir=str(scratch), max_workers=8)
shutil.rmtree(scratch / ".cache", ignore_errors=True)
print("Verschieben", flush=True)
target.parent.mkdir(parents=True, exist_ok=True)
if target.exists():
    shutil.rmtree(target, ignore_errors=True)
shutil.move(str(scratch), str(target))
"""


def background_present(comfyui: Path) -> bool:
    """Liegt ein Freistell-Modell da? Welches, entscheidet die Rolle.

    Gefragt wird nach dem Ordner und nicht nach unserer Datei: Wer ``lucida``
    installiert hat, hat eines — und die Rollenauflösung in
    :data:`app.core.backends.mesh.MODEL_ROLES` nimmt es dann auch.
    """
    folder = comfyui / "models" / "background_removal"
    return any(folder.glob("*.safetensors")) if folder.is_dir() else False


def fetch_background(
    comfyui: Path,
    python: Path,
    progress: ProgressFn = _silent,
    cancelled: CancelledFn | None = None,
) -> None:
    """Das Freistell-Modell holen — 445 MB, und nur wenn keines da ist."""
    if background_present(comfyui):
        return
    target = comfyui / "models" / "background_removal"
    target.mkdir(parents=True, exist_ok=True)
    _run_repeatedly(
        [
            str(python),
            "-s",
            "-c",
            _FETCH_FILE,
            str(target),
            BACKGROUND_REPO,
            BACKGROUND_FILE,
            str(scratch_dir("dl-bg")),
        ],
        _("Modell fürs Freistellen laden — 445 MB"),
        progress,
        cancelled,
    )


#: Eine einzelne Datei holen, statt eines ganzen Repositoriums. Derselbe Grund
#: für den kurzen Ordner wie bei :data:`_FETCH_WEIGHTS`, und dieselbe
#: Wiederholung: Die Leitung entscheidet, nicht die Dateigröße.
_FETCH_FILE = """
import shutil, sys
from pathlib import Path
from huggingface_hub import hf_hub_download

target, repo, name = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
scratch = Path(sys.argv[4])
scratch.mkdir(parents=True, exist_ok=True)
got = hf_hub_download(repo, name, local_dir=str(scratch))
target.mkdir(parents=True, exist_ok=True)
shutil.move(got, str(target / Path(name).name))
shutil.rmtree(scratch, ignore_errors=True)
"""


def free_gigabytes(where: Path) -> float:
    """Wie viel auf dem Datenträger dieses Pfades frei ist.

    Gefragt wird der nächste Ordner, den es schon gibt — das Ziel selbst wird
    erst angelegt, und ``disk_usage`` will einen vorhandenen Pfad.
    """
    existing = where
    while not existing.exists() and existing != existing.parent:
        existing = existing.parent
    return shutil.disk_usage(existing).free / 1_000_000_000


def _gigabytes_in(folder: Path) -> float:
    """Was in diesem Ordner schon liegt — für die Rechnung, wie viel noch fehlt.

    Ein abgebrochener Download lässt seine Bruchstücke stehen, und der nächste
    Anlauf holt nur den Rest (:func:`_run_repeatedly`). Eine Platzprüfung, die
    das ignoriert, verweigert ausgerechnet die Wiederaufnahme.
    """
    if not folder.exists():
        return 0.0
    total = sum(f.stat().st_size for f in folder.rglob("*") if f.is_file())
    return total / 1_000_000_000


def _space_or_stop(where: Path) -> None:
    """Hält an, wenn der Datenträger dieses Ordners die Gewichte nicht fasst.

    **Was schon liegt, zählt mit.** Ein abgebrochener Download hinterlässt seine
    Bruchstücke im Zwischenordner, und ``_run_repeatedly`` setzt genau dort fort
    — nur was fehlt, wird noch geholt. Ohne diesen Zuschlag verweigerte die
    Prüfung ausgerechnet den zweiten Anlauf, obwohl er weniger braucht als der
    erste: Bei 5 von 7,5 GB geladen fehlen 2,5, und verlangt worden wären 9. Am
    Ziel gilt dasselbe aus einem anderen Grund — es wird vor dem Verschieben
    geräumt, sein Inhalt wird also frei.

    **Die Meldung nennt den Ordner** (Regel 17). „Auf dem Datenträger ist zu
    wenig Platz" ist für einen Rechner mit zwei Platten keine Auskunft, sondern
    eine Suchaufgabe — und die beiden Orte liegen hier regelmäßig auf
    verschiedenen Datenträgern.
    """
    free = free_gigabytes(where) + _gigabytes_in(where)
    if free >= NEEDED_GIGABYTES:
        return
    raise SetupFailed(
        str(
            _(
                "Auf dem Datenträger von {drive} sind {frei:.1f} GB frei, gebraucht "
                "werden {noetig:.0f}. Schaffen Sie dort Platz — geladen wird in den "
                "Zwischenordner, und von dort wandern die Gewichte nach "
                "models/triposg; beide Orte müssen sie fassen."
            )
        ).format(drive=where, frei=free, noetig=NEEDED_GIGABYTES)
    )


def fetch_weights(
    comfyui: Path,
    python: Path,
    progress: ProgressFn = _silent,
    cancelled: CancelledFn | None = None,
) -> None:
    """Die Gewichte holen — rund 7,5 GB, und nur wenn sie fehlen.

    **Geprüft wird der Platz vorher** (:data:`NEEDED_GIGABYTES`). Ein Download,
    der nach zwanzig Minuten an einer vollen Platte stirbt, kostet die zwanzig
    Minuten **und** die Suche danach — die Meldung des fremden Programms nennt
    den Grund nicht.

    **Und geprüft werden beide Orte.** Geladen wird in den Nutzer-Cache, liegen
    bleibt es unter ``models/triposg`` — das kann derselbe Datenträger sein und
    muss es nicht: ComfyUI auf ``D:`` mit viel Platz und ein knappes ``C:`` ist
    der Normalfall, nicht der Sonderfall. Vom 25.08.2026 bis zum 26.08.2026 fragte
    die Prüfung nur den ComfyUI-Datenträger und meldete grün, während der
    Download auf dem anderen starb. Beide braucht es auch dann, wenn der Platz
    da ist: ``shutil.move`` verschiebt innerhalb eines Datenträgers und
    **kopiert** über seine Grenze hinweg.
    """
    if weights_present(comfyui):
        return
    target = comfyui / "models" / "triposg" / "TripoSG"
    scratch = scratch_dir("dl-triposg")
    _space_or_stop(scratch)
    _space_or_stop(target)
    target.parent.mkdir(parents=True, exist_ok=True)
    _run_repeatedly(
        [
            str(python),
            "-s",
            "-c",
            _FETCH_WEIGHTS,
            str(target),
            WEIGHTS_REPO,
            str(scratch),
        ],
        _("Gewichte laden — rund 7,5 GB, das dauert"),
        progress,
        cancelled,
    )


#: Das Programm, das prüft, ob die Knoten wirklich laden. Es läuft im Python
#: von ComfyUI, denn nur dort steht, was ComfyUI hat — unser eigenes wüsste
#: darüber nichts.
#:
#: Geladen wird über den Dateipfad und nicht als Modul: Der Ordner heißt
#: ``ComfyUI-TripoSG-Solidon``, und Bindestriche sind in einem Modulnamen nicht
#: erlaubt. ``folder_paths`` liegt in ComfyUIs Wurzel, also muss die auf dem
#: Suchpfad stehen; ``argv`` wird gesetzt, weil ComfyUI beim Import seine
#: Startargumente liest und ohne sie über unsere stolpert.
_LOAD_NODES = """
import importlib.util, sys
from pathlib import Path

root, nodes = Path(sys.argv[1]), Path(sys.argv[2])
sys.argv = ["main.py"]
sys.path.insert(0, str(root))
spec = importlib.util.spec_from_file_location(
    "solidon_nodes", nodes / "__init__.py", submodule_search_locations=[str(nodes)]
)
module = importlib.util.module_from_spec(spec)
sys.modules["solidon_nodes"] = module
spec.loader.exec_module(module)
names = sorted(getattr(module, "NODE_CLASS_MAPPINGS", {}))
if not names:
    raise SystemExit("Die Sammlung meldet keine Knoten.")
print("Knoten:", ", ".join(names))
"""


def nodes_load(
    comfyui: Path,
    python: Path,
    nodes: Path,
    progress: ProgressFn = _silent,
    cancelled: CancelledFn | None = None,
) -> None:
    """Nachsehen, ob ComfyUI die Knoten laden **kann**. Wirft, wenn nicht.

    **Die Einrichtung sagte „fertig", ohne es zu wissen.** Sie kopierte, klonte,
    flickte und installierte — und ob am Ende etwas lief, erfuhr der Kunde erst,
    wenn er ein Bild hineinlegte und *Erzeugen* drückte: Dann stand in ComfyUIs
    Protokoll „No module named 'trimesh'", und im Dialog stand, der Knoten sei
    unbekannt. Auf einem frischen ComfyUI Desktop war das der Normalfall, nicht
    der Ausnahmefall — sechs Pakete fehlten.

    Der Schritt kostet zwei Sekunden und ist der einzige, der die Frage stellt,
    die den Kunden angeht: Läuft es. Was er findet, reist mit — die Meldung des
    Ladefehlers sagt genauer, was fehlt, als jeder Satz, den wir vorher
    erraten könnten.

    **Zwei Sekunden sind nicht null.** Dies war der einzige ``_run``-Aufruf
    ohne Abbruchmerker; hängt der Import in ComfyUIs Umgebung — er lädt Torch
    —, wartete *Abbrechen* auf einen Schritt, der ihn gar nicht bemerkt hätte.
    """
    try:
        _run(
            [str(python), "-s", "-c", _LOAD_NODES, str(comfyui), str(nodes)],
            _("Nachsehen, ob die Knoten laden"),
            progress,
            cancelled,
        )
    except SetupFailed as problem:
        raise SetupFailed(
            str(
                _(
                    "Die Knoten liegen an ihrem Platz, ComfyUI kann sie aber nicht "
                    "laden. Meist fehlt ein Paket in ComfyUIs eigener Umgebung — "
                    "was genau, steht darunter. Ein zweiter Lauf der Einrichtung "
                    "zieht es nach; bleibt es dabei, gehört die Zeile in eine "
                    "Rückmeldung an den Support."
                )
            )
            + chr(10)
            + chr(10)
            + str(problem)
        ) from problem


def setup(
    comfyui: str | Path | None = None,
    *,
    weights: bool = True,
    progress: ProgressFn = _silent,
    cancelled: CancelledFn | None = None,
) -> Result:
    """Alle Schritte, in dieser Reihenfolge. Wirft :class:`SetupFailed`.

    Abgebrochen wird **auch mitten in einem Schritt** — der Download der
    Gewichte dauert eine halbe Stunde, und ein Abbrechen, das erst danach
    wirkt, ist keines. Was dabei halb geladen ist, bleibt liegen:
    ``huggingface_hub`` setzt beim nächsten Lauf fort, und die Knoten sind
    idempotent kopiert.
    """
    found = find_comfyui(comfyui)
    python = find_python(found)
    progress(_("ComfyUI gefunden"))

    target = copy_nodes(found, progress)
    try:
        if cancelled is not None and cancelled():
            return _stopped(found, target)
        fetch_triposg(target, progress, cancelled)
        if cancelled is not None and cancelled():
            return _stopped(found, target)
        patch_sources(target, progress)
        install_packages(python, progress, cancelled)
        # **Erst prüfen, dann „fertig" sagen** — und vor den Gewichten, denn
        # ein fehlendes Paket zu melden ist nach zwei Sekunden mehr wert als
        # nach einer halben Stunde Download.
        nodes_load(found, python, target, progress, cancelled)
        if not weights:
            return Result(comfyui=found, nodes=target, weights=weights_present(found))
        if cancelled is not None and cancelled():
            return _stopped(found, target)
        # Das Kleine zuerst: 445 MB gegen 7,5 GB. Wer abbricht, hat dann
        # wenigstens den Teil, der schnell ging.
        fetch_background(found, python, progress, cancelled)
        if cancelled is not None and cancelled():
            return _stopped(found, target)
        fetch_weights(found, python, progress, cancelled)
    except Cancelled:
        # **Der Abbruch mitten im Schritt**, nicht nur zwischen zweien: Der
        # Download der Gewichte dauert eine halbe Stunde, und ein Abbrechen,
        # das erst danach wirkt, ist keines.
        return _stopped(found, target)
    _log.info("comfy setup finished in %s", found)
    return Result(comfyui=found, nodes=target, weights=True)


def _stopped(comfyui: Path, nodes: Path) -> Result:
    return Result(
        comfyui=comfyui,
        nodes=nodes,
        weights=weights_present(comfyui),
        reason=_("Abgebrochen. Was schon da ist, bleibt — ein neuer Lauf setzt fort."),
    )
