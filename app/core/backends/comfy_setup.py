"""ComfyUI für Solidon einrichten (Bauplan §27, §36).

Solidon rechnet die Mesh-Erzeugung nicht selbst, sondern schickt einen Ablauf
an ein lokales ComfyUI. Die Knoten dieses Ablaufs bringt ComfyUI selbst mit —
TRELLIS.2, Freistellen, Netznachbearbeitung und FLUX.2 sind eingebaute Knoten
(ab :data:`app.core.backends.mesh.MINIMUM_COMFYUI`). Was fehlt, sind die Modelldateien. Sie von Hand
zusammenzusuchen ist der Punkt, an dem die meisten aufgeben — also nimmt es
dieses Modul ab: jede Datei mit festem Modellstand, Größe und SHA-256.

**Warum es hier steht und nicht in ``tools/``.** ``tools/`` reist nicht im
Paket mit; was der Kunde aus der laufenden Anwendung heraus einrichten soll,
muss im Kern stehen. ``tools/setup_comfyui.py`` ist ein dünner Aufrufer.

**Was es nicht tut: ComfyUI installieren, aktualisieren oder starten.** Das
ist ein fremdes Programm mit eigenem Installationsweg; ein zu altes nennt die
Einrichtung mit Version und Weg (:func:`check_version`), und ein laufendes,
dem Knoten fehlen, nennt :meth:`app.core.backends.mesh.ComfyBackend.missing_nodes`.

**Bis Oktober 2026 stand hier TripoSG** mit eigenem Knoten, Quelltextabruf,
Quellpatches und Paketnachzügen. Ein Teil des TripoSG-Quelltexts steht unter
einer Tencent-Lizenz, deren Gebiet die EU ausnimmt (RM-003); seit TRELLIS.2
ein Kernmodell von ComfyUI ist, braucht Weg 3 nichts davon. Was Solidon damals
selbst angelegt hat, räumt :func:`remove_legacy` weg.
"""

from __future__ import annotations

import contextlib
import json
import math
import os
import queue
import re
import shutil
import stat
import subprocess
import sys
import threading
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import IO, Final

from app.core import discover
from app.core.backends.mesh import MINIMUM_COMFYUI, role_candidates
from app.core.log import get_logger
from app.i18n import TranslatableText, _, format_decimal

_log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ModelFile:
    """Eine Modelldatei, wie Solidon sie lädt: woher, welcher Stand, wohin, welche Prüfsumme.

    ``role`` ist die Modellrolle aus :data:`app.core.backends.mesh.MODEL_ROLES`,
    die diese Datei im Ablauf ausfüllt. Liegt im Zielordner schon eine andere
    Datei, die die Rolle ausfüllt — eine bf16-Fassung statt der int8, ein
    selbst geholtes Freistellmodell —, wird nichts geladen: Welche Datei läuft,
    entscheidet die Rollenauflösung, nicht der Dateiname hier.
    """

    repo: str
    revision: str
    path: str
    """Der Pfad im Repositorium; der Dateiname am Ziel ist sein letzter Teil."""
    size: int
    """Byte, abgelesen über die Hugging-Face-API (``?blobs=true``)."""
    sha256: str
    folder: str
    """Der Zielordner, von ComfyUIs Ordner aus gerechnet."""
    role: str

    @property
    def name(self) -> str:
        return PurePosixPath(self.path).name

    def target(self, comfyui: Path) -> Path:
        return comfyui / self.folder / self.name


#: TRELLIS.2-4B (Microsoft, MIT) in der Packung von Comfy-Org: der Formkern als
#: int8 (5,25 GB statt 10,3 GB bf16), die Form-VAE und der Bildkodierer DINOv3
#: ViT-L/16 (Metas DINOv3-Lizenz). Die Textur-VAE fehlt mit Absicht: Solidon
#: braucht die Form, keine Farbe. Stand 23.09.2026.
SHAPE_REPO: Final = "Comfy-Org/TRELLIS.2"
SHAPE_REVISION: Final = "430a9d09b2416687018c8fe8edced2ad4858a439"
SHAPE_FILES: Final = (
    ModelFile(
        repo=SHAPE_REPO,
        revision=SHAPE_REVISION,
        path="diffusion_models/trellis_2_int8_convrot.safetensors",
        size=5_253_048_192,
        sha256="d01952ad137213f6a868f86b6b877026276f84af5eec23069217475a0bad3a31",
        folder="models/diffusion_models",
        role="shape",
    ),
    ModelFile(
        repo=SHAPE_REPO,
        revision=SHAPE_REVISION,
        path="vae/trellis_2_shape_vae_bf16.safetensors",
        size=1_095_844_024,
        sha256="de0cb4949a76c59ee5c091a995a69bcc8c51d5aeda939f0c641a50d2a72341f4",
        folder="models/vae",
        role="shape_vae",
    ),
    ModelFile(
        repo=SHAPE_REPO,
        revision=SHAPE_REVISION,
        path="clip_vision/dino_v3_vit_l.safetensors",
        size=1_212_559_776,
        sha256="5cb785e458de7c460579082418af81f5c62380c181599344bdc60898c63468ee",
        folder="models/clip_vision",
        role="image_encoder",
    ),
)

#: Das Freistellmodell, ohne das der Bildweg nicht läuft: TRELLIS.2 will ein
#: freigestelltes Objekt, kein Foto mit Zimmer dahinter. BiRefNet (MIT) über
#: ComfyUIs eigene Knoten ``LoadBackgroundRemovalModel`` und
#: ``RemoveBackground`` — hier stand einmal ein GPL-Knoten, und Regel 15 lässt
#: keine GPL-Abhängigkeit zu.
BACKGROUND: Final = ModelFile(
    repo="Comfy-Org/BiRefNet",
    revision="5a1bd8ae750548f8cd42e3c8afa854fd3eba0fb1",
    path="background_removal/birefnet.safetensors",
    size=444_473_596,
    sha256="9ab37426bf4de0567af6b5d21b16151357149139362e6e8992021b8ce356a154",
    folder="models/background_removal",
    role="background",
)

#: Das Bildmodell für den **Textweg** — auf Wunsch geholt, nicht ungefragt.
#:
#: Aus Text wird erst ein Bild, und dafür braucht ComfyUI ein Bildmodell. Wer
#: nur Bilder mitbringt, braucht es nie, deshalb ein eigenes Häkchen in der
#: Einrichtung (:func:`setup`, ``image_model``). FLUX.2 [klein] 4B (Black Forest
#: Labs, Apache-2.0) mit dem Textkodierer Qwen3-4B (Apache-2.0): die fp8-Fassung
#: direkt vom Hersteller, Textkodierer und VAE aus der Packung von Comfy-Org.
#: **Nur die 4B-Fassung** — die 9B-Fassung und FLUX.2 [dev] stehen unter einer
#: nicht-kommerziellen Lizenz; die Rolle ``image`` schließt sie aus.
IMAGE_MODEL_FILES: Final = (
    ModelFile(
        repo="black-forest-labs/FLUX.2-klein-4b-fp8",
        revision="5b4408e59397a4a37ccb46afe426d8ed86379441",
        path="flux-2-klein-4b-fp8.safetensors",
        size=4_070_624_520,
        sha256="97ed34fe0567e436200f2faee3939b88f2b5d99f8af2a4dc16532c4245c0ccb6",
        folder="models/diffusion_models",
        role="image",
    ),
    ModelFile(
        repo="Comfy-Org/vae-text-encorder-for-flux-klein-4b",
        revision="5f526678002e43af5551dadb73ce2e8c91b43afe",
        path="split_files/text_encoders/qwen_3_4b_fp4_flux2.safetensors",
        size=3_848_213_998,
        sha256="3eab03a77adb0ee5304a4e677d5c10ac22f9049c1d7c894adca4f8bb39206ca8",
        folder="models/text_encoders",
        role="text_encoder",
    ),
    ModelFile(
        repo="Comfy-Org/vae-text-encorder-for-flux-klein-4b",
        revision="5f526678002e43af5551dadb73ce2e8c91b43afe",
        path="split_files/vae/flux2-vae.safetensors",
        size=336_211_292,
        sha256="868fe7b343cc8f3a19dbcfcafbc3d5f888802be3f89bd81b65b3621a066ce8f3",
        folder="models/vae",
        role="image_vae",
    ),
)


def _gigabytes(files: tuple[ModelFile, ...]) -> float:
    return round(sum(entry.size for entry in files) / 1_000_000_000, 1)


#: Wie groß das Modell für den Bildweg ist, Freistellen eingeschlossen — als
#: Zahl aus den Dateien, nicht getippt: Sie steht in Dialog, Handbuch und
#: Fortschritt, und eine Zweitschrift daneben veraltet beim nächsten Stand.
WEIGHT_GIGABYTES: Final = _gigabytes((*SHAPE_FILES, BACKGROUND))
SHAPE_GIGABYTES: Final = _gigabytes(SHAPE_FILES)
IMAGE_MODEL_GIGABYTES: Final = _gigabytes(IMAGE_MODEL_FILES)
BACKGROUND_MEGABYTES: Final = math.ceil(BACKGROUND.size / 1_000_000)

#: Was über den Dateien frei bleiben muss — Luft für das, was
#: ``huggingface_hub`` beim Laden zwischenlagert.
#:
#: Geprüft wird **vorher** und nicht im Fehlerfall: Ein Download, der an einer
#: vollen Platte stirbt, meldet „Background writer channel closed" und nennt
#: den Grund mit keinem Wort.
HEADROOM_GIGABYTES: Final = 1.5

#: Was Solidon bis Oktober 2026 selbst in ComfyUI anlegte (:func:`remove_legacy`).
LEGACY_NODES: Final = "custom_nodes/ComfyUI-TripoSG-Solidon"
LEGACY_WEIGHTS: Final = "models/triposg/TripoSG"
LEGACY_MARKER: Final = ".solidon-complete.json"
LEGACY_SCRATCH: Final = "dl-triposg"


#: Wo ComfyUI erfahrungsgemäß liegt, wenn niemand etwas anderes sagt.
#:
#: Die tragbare Version entpackt der Nutzer selbst, also steht sie dort, wohin
#: er sie gelegt hat — geraten wird an den Stellen, an denen sie
#: erfahrungsgemäß landet. **ComfyUI Desktop** dagegen wählt selbst, und die
#: Wahl steht in seiner eigenen Aufstellung: :func:`_from_desktop` liest sie.
def guesses_for(platform: str) -> tuple[Path, ...]:
    """Wo ComfyUI auf dieser Plattform erfahrungsgemäß liegt.

    Eine Funktion und keine Liste mit ``if sys.platform``, aus demselben Grund
    wie :func:`app.core.discover.parts_for`: Die Zuordnung ist damit von
    **jeder** Maschine aus prüfbar. ``~/comfy/ComfyUI`` ist der Ort, an den
    ``comfy-cli`` von sich aus installiert.
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
#: ComfyUI.
DESKTOP_RECORD: Final = "Comfy Desktop/installations.json"

#: Ein Schritt darf lange dauern — die größte Datei sind 5,3 GB.
STEP_TIMEOUT_SECONDS: Final = 3600.0

ProgressFn = Callable[[TranslatableText | str], None]
CancelledFn = Callable[[], bool]


def scratch_dir(name: str) -> Path:
    """Ein Zwischenordner für einen Download — im Nutzer-Cache, nicht im Temp.

    **Ein fester Name im gemeinsamen Temp gehört nicht uns.** Unter Linux ist
    ``/tmp`` für alle Konten schreibbar; wer den Ordner vorher anlegt, bestimmt,
    was nach dem Download nach ``models`` verschoben wird. Der Nutzer-Cache
    gehört dem Nutzer.

    Der Name bleibt **fest**, und das ist Absicht: Ein abgebrochener Download
    setzt beim nächsten Lauf fort, und das kann er nur, wenn seine Bruchstücke
    da liegen, wo er sie sucht. Kurz muss er außerdem sein — Windows deckelt
    einen Pfad bei 260 Zeichen, und ``huggingface_hub`` hängt einen Teil davon
    selbst an.
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
    weights: bool
    """Liegt alles für den Bildweg — Formmodell, Bildkodierer, Freistellen?"""
    image_model: bool = False
    """Liegt das Bildmodell für den Weg aus Text?"""
    reason: TranslatableText | str = ""
    legacy_left: tuple[str, ...] = ()
    """Was von Solidons alter TripoSG-Einrichtung stehen blieb, relativ zu
    ComfyUI (:func:`remove_legacy`) — der Dialog nennt es samt Ausweg."""

    @property
    def done(self) -> bool:
        return not self.reason


def _config_home(platform: str = sys.platform) -> Path:
    """Der Ort, an dem Electron-Anwendungen ihre Einstellungen ablegen.

    Die Plattform ist ein **Parameter** und kein ``sys.platform`` mitten im
    Code: So ist die Zuordnung von jeder Maschine aus prüfbar, und mypy hält
    die anderen Zweige nicht für unerreichbar. Dieselbe Bauart wie
    ``discover.parts_for``.
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

    ComfyUI Desktop legt sein ComfyUI tief unter ``AppData/Local`` ab, und
    keine geratene Stelle trifft das; es schreibt den Ort aber in eine eigene
    Datei, samt dem Ort, den der Nutzer im Installer gewählt hat. Gelesen wird
    tolerant: Die Datei gehört jemand anderem, ihr Aufbau ist nirgends
    zugesagt, und daran zu scheitern wäre schlechter als weiter zu raten.
    """
    record = _desktop_record()
    try:
        listed = json.loads(record.read_text(encoding="utf-8"))
    except OSError, ValueError:
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
    """Der Ordner, in dem ``models`` und ``custom_nodes`` liegen."""
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

    # Die Desktop-Version steht vorn, weil sie nicht geraten ist.
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


_VERSION: Final = re.compile(r"""__version__\s*=\s*["'](\d+)\.(\d+)\.(\d+)""")


def comfyui_version(comfyui: Path) -> tuple[int, int, int] | None:
    """Die Fassung dieses ComfyUI aus ``comfyui_version.py``, sonst ``None``.

    **Gelesen, nicht ausgeführt** — die Datei gehört einem fremden Programm
    (Regel 11). ``None`` heißt „unbekannt“, nicht „zu alt“: ComfyUI Desktop
    hält seinen Programmcode getrennt von dem Ordner, in dem Modelle und
    ``custom_nodes`` liegen, und dort steht keine Versionsdatei. Dann sagt es
    der laufende Server, welche Knoten ihm fehlen
    (:meth:`app.core.backends.mesh.ComfyBackend.missing_nodes`).
    """
    try:
        text = (comfyui / "comfyui_version.py").read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    found = _VERSION.search(text)
    if found is None:
        return None
    major, minor, patch = (int(part) for part in found.groups())
    return major, minor, patch


def _dotted(version: tuple[int, ...]) -> str:
    return ".".join(str(part) for part in version)


def check_version(comfyui: Path) -> None:
    """Hält an, wenn dieses ComfyUI die Knoten des Ablaufs noch nicht kennt.

    **Die billige Prüfung zuerst** (``kern.md``, „Einrichten heißt nicht
    laufen“): Eine Datei lesen kostet nichts, und ein zu altes ComfyUI nach
    acht Gigabyte Download zu melden, wäre eine halbe Stunde zu spät.
    """
    found = comfyui_version(comfyui)
    if found is None:
        _log.info("comfyui version unknown in %s, checked at run time", comfyui)
        return
    if found >= MINIMUM_COMFYUI:
        return
    raise SetupFailed(
        str(
            _(
                "Dieses ComfyUI hat die Version {found}. Die Knoten für den Weg "
                "zum 3D-Modell bringt ComfyUI ab Version {needed} selbst mit. "
                "ComfyUI aktualisieren — bei der tragbaren Fassung mit "
                "„update_comfyui.bat“ im Ordner „update“, bei ComfyUI Desktop "
                "über dessen Menü —, danach die Einrichtung erneut starten.",
                found=_dotted(found),
                needed=_dotted(MINIMUM_COMFYUI),
            )
        )
    )


def find_python(comfyui: Path) -> Path:
    """Der Interpreter, mit dem ComfyUI selbst läuft.

    Geladen wird mit ``huggingface_hub``, und das bringt ComfyUI mit — Solidon
    nicht. Im gebauten Paket gibt es unser Python ohnehin nicht als
    Interpreter; ohne den von ComfyUI hält die Einrichtung an, statt ins Leere
    zu laden.
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
                    "In diesem ComfyUI ist kein eigenes Python zu finden, und mit ihm lädt "
                    "Solidon die Modelle. Wer die Modelldateien selbst in ComfyUIs Ordner "
                    "models legt, braucht diesen Schritt nicht: Solidon findet sie dort."
                )
            )
        )
    _log.info("no python inside %s, using %s", comfyui, sys.executable)
    return Path(sys.executable)


#: Wie oft nachgesehen wird, ob abgebrochen wurde oder die Frist steht — auch
#: wenn der Kindprozess gerade nichts sagt.
WATCH_SECONDS: Final = 0.2


def _pump(stream: IO[str], sink: queue.Queue[str | None]) -> None:
    """Liest den Kindprozess leer und legt jede Zeile in die Warteschlange.

    In einem eigenen Faden, weil das Lesen blockiert und ein schweigender
    Prozess beliebig lange schweigt. ``None`` heißt „der Strom ist zu Ende“.
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
) -> str:
    """Einen Schritt laufen lassen und seine letzten Ausgabezeilen zurückgeben.

    Gelesen wird über einen eigenen Faden (:func:`_pump`), und diese Schleife
    wartet mit Zeitscheibe: Alle :data:`WATCH_SECONDS` wird gefragt, ob
    abgebrochen wurde und ob die Frist steht — mit Ausgabe oder ohne. Ein
    Abbruch beendet den Kindprozess; ``huggingface_hub`` lässt teilweise
    geladene Dateien liegen und setzt beim nächsten Lauf fort.
    """
    if cancelled is not None and cancelled():
        raise Cancelled(str(what))
    progress(what)
    _log.info("comfy setup: %s", command[0])
    # Nur der Schluss wird behalten: Die Fehlermeldung zeigt die letzten
    # sechs Zeilen, und ein Download schreibt Zehntausende.
    lines: deque[str] = deque(maxlen=6)
    deadline = time.monotonic() + STEP_TIMEOUT_SECONDS
    # **Die Einrichtung läuft auf dem Rechner, nicht im Sandkasten.** ComfyUI
    # und sein Python liegen dort.
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
                    raise SetupFailed(
                        str(_("{step}: Der Schritt hat zu lange gebraucht.", step=what))
                    )
            code = process.wait()
    except (OSError, subprocess.SubprocessError) as problem:
        raise SetupFailed(f"{what}\n{problem}") from problem
    if code:
        raise SetupFailed(str(what) + chr(10) + chr(10).join(lines))
    return "\n".join(lines)


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

    ``huggingface_hub`` hält einen globalen HTTP-Client; sobald ein Fehler ihn
    schließt, antwortet jeder weitere Versuch im selben Prozess mit „Cannot
    send a request, as the client has been closed". Ein neuer Prozess hat einen
    neuen Client, und weil das Halbgeladene in einem Ordner mit festem Namen
    liegt, kostet der neue Anlauf nur, was noch fehlt.
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


#: Eine einzelne Datei holen, im Python von ComfyUI. Fester Modellstand,
#: gestreamte Prüfsumme, und **erst die geprüfte Datei** wird am Ziel
#: eingewechselt — daneben kopiert und umbenannt, damit ein Abbruch nie eine
#: halbe Datei unter dem richtigen Namen hinterlässt.
_FETCH_FILE = """
import hashlib, shutil, sys
from pathlib import Path
from huggingface_hub import hf_hub_download

target, repo, name = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
scratch = Path(sys.argv[4])
revision, expected = sys.argv[5], sys.argv[6]
scratch.mkdir(parents=True, exist_ok=True)
got = Path(hf_hub_download(repo, name, revision=revision, local_dir=str(scratch)))
print(f"SHA-256: {got.name}", flush=True)
digest = hashlib.sha256()
with got.open("rb") as stream:
    while block := stream.read(1024 * 1024):
        digest.update(block)
actual = digest.hexdigest()
if actual != expected:
    got.unlink(missing_ok=True)
    raise RuntimeError(
        f"Die Prüfsumme der geladenen Gewichte ist {actual} statt {expected}. "
        "Starten Sie die Einrichtung erneut."
    )
target.mkdir(parents=True, exist_ok=True)
destination = target / Path(name).name
staged = destination.with_name(destination.name + ".part")
staged.unlink(missing_ok=True)
try:
    shutil.move(str(got), str(staged))
    staged.replace(destination)
except BaseException:
    staged.unlink(missing_ok=True)
    raise
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
    Anlauf holt nur den Rest. Eine Platzprüfung, die das ignoriert, verweigert
    ausgerechnet die Wiederaufnahme.
    """
    if not folder.exists():
        return 0.0
    total = sum(f.stat().st_size for f in folder.rglob("*") if f.is_file())
    return total / 1_000_000_000


def _space_or_stop(where: Path, needed: float, destination: str) -> None:
    """Hält an, wenn der Datenträger dieses Ordners die Dateien nicht fasst.

    **Was schon liegt, zählt mit** (:func:`_gigabytes_in`). **Die Meldung nennt
    den Ordner** (Regel 17): Zwischenordner und ``models`` liegen regelmäßig
    auf verschiedenen Datenträgern, und „zu wenig Platz" ohne Ort ist eine
    Suchaufgabe.
    """
    free = free_gigabytes(where) + _gigabytes_in(where)
    if free >= needed:
        return
    raise SetupFailed(
        str(
            _(
                "Auf dem Datenträger von {drive} sind {free} GB frei, gebraucht "
                "werden {needed} GB. Schaffen Sie dort Platz — geladen wird in den "
                "Zwischenordner, und von dort wandern die Gewichte nach "
                "{folder}; beide Orte müssen sie fassen."
            )
        ).format(
            drive=where,
            free=format_decimal(free, 1),
            needed=format_decimal(needed, 1),
            folder=destination,
        )
    )


def _listed(folder: Path) -> list[str]:
    """Die Modelldateien eines Ordners, wie ComfyUI sie anbieten würde."""
    if not folder.is_dir():
        return []
    return sorted(
        entry.relative_to(folder).as_posix()
        for entry in folder.rglob("*")
        if entry.is_file() and entry.suffix.lower() in (".safetensors", ".ckpt", ".pt", ".pth")
    )


def file_present(comfyui: Path, entry: ModelFile) -> bool:
    """Liegt diese Datei — oder eine andere, die ihre Rolle ausfüllt?

    Unsere Datei zählt nur mit ihrer vollen Größe: Ein Rest unter dem
    richtigen Namen ist keine Datei. Eine fremde zählt, wenn die
    Rollenauflösung sie nehmen würde — dieselbe Frage, die der Ablauf beim
    Erzeugen stellt (:func:`app.core.backends.mesh.role_candidates`).
    """
    target = entry.target(comfyui)
    try:
        if target.is_file() and target.stat().st_size == entry.size:
            return True
    except OSError:
        return False
    others = [name for name in _listed(comfyui / entry.folder) if name != entry.name]
    return bool(role_candidates(entry.role, others))


def background_present(comfyui: Path) -> bool:
    """Liegt ein Freistellmodell da? Welches, entscheidet die Rolle."""
    return file_present(comfyui, BACKGROUND)


def weights_present(comfyui: Path) -> bool:
    """Liegt alles für den Bildweg: Formkern, Form-VAE, Bildkodierer, Freistellen?"""
    return background_present(comfyui) and all(
        file_present(comfyui, entry) for entry in SHAPE_FILES
    )


def image_model_present(comfyui: Path) -> bool:
    """Liegt das Bildmodell für den Weg aus Text — alle drei Teile?"""
    return all(file_present(comfyui, entry) for entry in IMAGE_MODEL_FILES)


def _fetch_files(
    comfyui: Path,
    python: Path,
    files: tuple[ModelFile, ...],
    scratch_name: str,
    what: TranslatableText,
    progress: ProgressFn,
    cancelled: CancelledFn | None,
) -> None:
    """Die fehlenden Dateien dieser Gruppe holen, eine nach der anderen.

    **Geprüft wird der Platz vorher, an beiden Orten** — im Zwischenordner und
    unter ``models``; ``shutil.move`` verschiebt innerhalb eines Datenträgers
    und **kopiert** über seine Grenze hinweg.
    """
    missing = tuple(entry for entry in files if not file_present(comfyui, entry))
    if not missing:
        return
    needed = sum(entry.size for entry in missing) / 1_000_000_000 + HEADROOM_GIGABYTES
    scratch = scratch_dir(scratch_name)
    _space_or_stop(scratch, needed, missing[0].folder)
    _space_or_stop(comfyui / "models", needed, missing[0].folder)
    for entry in missing:
        target = comfyui / entry.folder
        target.mkdir(parents=True, exist_ok=True)
        _run_repeatedly(
            [
                str(python),
                "-s",
                "-c",
                _FETCH_FILE,
                str(target),
                entry.repo,
                entry.path,
                str(scratch),
                entry.revision,
                entry.sha256,
            ],
            what,
            progress,
            cancelled,
        )


def fetch_background(
    comfyui: Path,
    python: Path,
    progress: ProgressFn = _silent,
    cancelled: CancelledFn | None = None,
) -> None:
    """Das Freistellmodell holen — und nur, wenn keines da ist."""
    _fetch_files(
        comfyui,
        python,
        (BACKGROUND,),
        "dl-bg",
        _("Modell fürs Freistellen laden — {size} MB", size=BACKGROUND_MEGABYTES),
        progress,
        cancelled,
    )


def fetch_weights(
    comfyui: Path,
    python: Path,
    progress: ProgressFn = _silent,
    cancelled: CancelledFn | None = None,
) -> None:
    """TRELLIS.2 holen: Formkern, Form-VAE und Bildkodierer — nur, was fehlt."""
    _fetch_files(
        comfyui,
        python,
        SHAPE_FILES,
        "dl-shape",
        _(
            "Modell für den Weg aus Bild laden — rund {size} GB, das dauert",
            size=format_decimal(WEIGHT_GIGABYTES, 1),
        ),
        progress,
        cancelled,
    )


def fetch_image_model(
    comfyui: Path,
    python: Path,
    progress: ProgressFn = _silent,
    cancelled: CancelledFn | None = None,
) -> None:
    """Das Bildmodell für den Textweg holen — nur, was fehlt."""
    _fetch_files(
        comfyui,
        python,
        IMAGE_MODEL_FILES,
        "dl-image",
        _(
            "Bildmodell für den Weg aus Text laden — rund {size} GB, das dauert",
            size=format_decimal(IMAGE_MODEL_GIGABYTES, 1),
        ),
        progress,
        cancelled,
    )


def _writable_again(function: Callable[[str], object], path: str, _problem: BaseException) -> None:
    """Hebt den Schreibschutz auf und versucht es noch einmal (``shutil.rmtree``).

    Git legt seine Objektdateien schreibgeschützt an, und unter Windows
    verweigert ``rmtree`` sie dann mit „Zugriff verweigert“. Der alte
    TripoSG-Knoten trägt einen Klon (``_clone/.git``): An der echten Einrichtung
    blieb der Ordner samt ``nodes.py`` stehen, und ComfyUI lud ihn weiter.
    """
    Path(path).chmod(stat.S_IWRITE)
    function(path)


def legacy_leftovers(comfyui: Path) -> tuple[Path, ...]:
    """Was :func:`remove_legacy` entfernen wird — dieselbe Liste für Dialog und Löschung.

    Der Einrichtungsdialog nennt diese Ordner samt Größe, bevor er etwas
    anfasst (Entscheidung Robert, 07.10.2026): Gelöscht wird nur, was vorher
    dastand.
    """
    nodes = comfyui / LEGACY_NODES
    weights = comfyui / LEGACY_WEIGHTS
    doomed: list[Path] = []
    if (nodes / "nodes.py").is_file() and (nodes / "__init__.py").is_file():
        doomed.append(nodes)
    if (weights / LEGACY_MARKER).is_file():
        doomed.append(weights)
    doomed.extend(
        leftover
        for leftover in sorted(weights.parent.glob(weights.name + ".*"))
        if leftover.is_dir() and (leftover.name.endswith(".part") or ".previous-" in leftover.name)
    )
    return tuple(doomed)


def legacy_gigabytes(leftovers: tuple[Path, ...]) -> float:
    """Wie viel Platz das Entfernen der alten Einrichtung frei macht, in GB."""
    return sum(_gigabytes_in(folder) for folder in leftovers)


def remove_legacy(comfyui: Path, progress: ProgressFn = _silent) -> tuple[Path, ...]:
    """Räumt weg, was Solidon für TripoSG selbst angelegt hat. Liefert, was stehen blieb.

    **Nur das Eigene, und nur am eigenen Zeichen erkannt.** Der Knotenordner
    trägt Solidons Namen und unsere zwei Dateien; ohne ihn lädt ComfyUI beim
    Start keinen TripoSG-Quelltext mehr (RM-003). Die Gewichte gehen nur, wenn
    unsere Abschlussmarke darin liegt — rund 7,5 GB, die kein Ablauf von
    Solidon mehr liest. Ein erkannter Ordner geht ganz, samt allem, was darin
    liegt; andere Ordner bleiben unberührt. So sagt es auch der Dialog vorher.

    Ein Fehler beim Löschen hält die Einrichtung nicht an: Der neue Weg braucht
    die alten Dateien nicht, und ein gesperrter Ordner ist kein Grund, keine
    Modelle zu laden. **Verschwiegen wird er nicht** (Review 1 P3, G-6): Hält
    ein laufendes ComfyUI eine Datei offen, bleibt der Knotenordner stehen,
    und ComfyUI lädt den TripoSG-Quelltext weiter. Die Ordner, die stehen
    blieben, gehen zurück an :class:`Result` und von dort in den Dialog.
    """
    weights = comfyui / LEGACY_WEIGHTS
    doomed = legacy_leftovers(comfyui)
    if not doomed:
        return ()
    progress(_("Alte TripoSG-Einrichtung von Solidon entfernen"))
    left: list[Path] = []
    for folder in doomed:
        try:
            shutil.rmtree(folder, onexc=_writable_again)
            _log.info("removed legacy %s", folder)
        except OSError as problem:
            _log.warning("legacy %s stays: %s", folder, problem)
            left.append(folder)
    with_triposg = weights.parent
    if with_triposg.is_dir() and not any(with_triposg.iterdir()):
        with contextlib.suppress(OSError):
            with_triposg.rmdir()
    from app.core.paths import user_cache_dir

    shutil.rmtree(user_cache_dir() / LEGACY_SCRATCH, ignore_errors=True)
    return tuple(left)


def setup(
    comfyui: str | Path | None = None,
    *,
    weights: bool = True,
    image_model: bool = False,
    progress: ProgressFn = _silent,
    cancelled: CancelledFn | None = None,
) -> Result:
    """Alle Schritte, in dieser Reihenfolge. Wirft :class:`SetupFailed`.

    ``weights`` holt das Modell für den Bildweg (TRELLIS.2 und Freistellen),
    ``image_model`` zusätzlich das Bildmodell für den Weg aus Text — als
    eigener Wunsch, denn es braucht nur dieser Weg. Es hängt nicht an
    ``weights``: Der Dialog schaltet die Gewichte ab, sobald sie schon liegen,
    und genau dann fehlt meist nur noch das Bildmodell (RM-343).

    Abgebrochen wird **auch mitten in einem Schritt** — ein Download dauert
    Minuten, und ein Abbrechen, das erst danach wirkt, ist keines. Was halb
    geladen ist, bleibt liegen, und ein neuer Lauf setzt fort.
    """
    found = find_comfyui(comfyui)
    check_version(found)
    progress(_("ComfyUI gefunden"))
    left = tuple(path.relative_to(found).as_posix() for path in remove_legacy(found, progress))
    if not weights and not image_model:
        return Result(
            comfyui=found,
            weights=weights_present(found),
            image_model=image_model_present(found),
            legacy_left=left,
        )
    python = find_python(found)
    try:
        if weights:
            if cancelled is not None and cancelled():
                return _stopped(found, left)
            # Das Kleine zuerst: Wer abbricht, hat dann wenigstens den Teil,
            # der schnell ging.
            fetch_background(found, python, progress, cancelled)
            if cancelled is not None and cancelled():
                return _stopped(found, left)
            fetch_weights(found, python, progress, cancelled)
        if image_model:
            if cancelled is not None and cancelled():
                return _stopped(found, left)
            # Zuletzt, weil es der einzige Posten ist, den nur ein Weg braucht:
            # Wer hier abbricht, hat den Bildweg vollständig.
            fetch_image_model(found, python, progress, cancelled)
    except Cancelled:
        return _stopped(found, left)
    _log.info("comfy setup finished in %s", found)
    return Result(
        comfyui=found,
        weights=weights_present(found),
        image_model=image_model_present(found),
        legacy_left=left,
    )


def _stopped(comfyui: Path, legacy_left: tuple[str, ...] = ()) -> Result:
    return Result(
        comfyui=comfyui,
        weights=weights_present(comfyui),
        image_model=image_model_present(comfyui),
        reason=_("Abgebrochen. Was schon da ist, bleibt — ein neuer Lauf setzt fort."),
        legacy_left=legacy_left,
    )
