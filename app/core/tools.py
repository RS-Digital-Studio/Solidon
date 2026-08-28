"""Externe Programme (Bauplan §38, §37.2).

Der Slicer, Ollama und ComfyUI werden nicht mitgeliefert — sie werden
konfiguriert. Das ist beim Slicer eine Lizenzentscheidung (§36, GPL) und beim
Rest eine Größenentscheidung, und es bedeutet, dass die Anwendung klar sagen
können muss, welches davon da ist und welches nicht.

Nichts davon ist Pflicht. Jedes ist eine Rückfallebene oder eine Zugabe, ein
Rechner ohne alle drei läuft den ganzen Kernweg (§24.1). Die Erstinbetriebnahme
*zeigt* diese Liste — sie fordert sie nicht ein.

**Es waren vier, und das vierte war OpenSCAD.** Am 26.08.2026 entfernt: Was es
tragen sollte, war die Rückfallebene aus §24.1 für Formen ohne Baustein — und
seit die Skizzen im Haus sind (§30.1), gibt es diese Formen nicht mehr. Ein
Programm in dieser Liste, das nie gerufen wird, ist eine Aufforderung ohne
Gegenwert: Der Kunde installiert 40 MB und merkt nichts davon.

**Zwei Arten, zwei Fragen.** Ein Programm wird aufgerufen, es braucht also eine
Datei; gesucht wird sie von :mod:`app.core.discover`, und zwar nicht nur im
PATH. Ein Dienst wird angesprochen, er braucht also eine Adresse; gefragt wird
sein Port. Ollama ist beides: erst installiert, dann gestartet — und zwischen
diesen beiden Zuständen liegt genau der Satz, den jemand lesen muss, um weiter
zu kommen.
"""

from __future__ import annotations

import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from app.core import discover
from app.core.backends import llm, mesh
from app.core.log import get_logger
from app.i18n import TranslatableText, _

_log = get_logger(__name__)

Kind = Literal["program", "service"]


@dataclass(frozen=True, slots=True)
class ExternalTool:
    """Ein Programm, das die Anwendung benutzen kann, wenn es da ist."""

    id: str
    title: TranslatableText | str
    what_for: TranslatableText | str
    kind: Kind = "program"
    executables: tuple[str, ...] = ()
    """Namen, unter denen die ausführbare Datei installiert wird."""
    url: str = ""
    """Vorgabeadresse eines Dienstes. Bei einem reinen Programm leer."""
    optional: bool = True
    start_arguments: tuple[str, ...] = ()
    """Womit sich dieser Dienst starten lässt, oder nichts.

    Nur wo es einen Befehl gibt, den ein Mensch genauso eingeben würde:
    ``ollama serve``. ComfyUI bleibt leer — es wird aus seinem eigenen Ordner
    mit seinem eigenen Python gestartet, und eine Anwendung, die das errät,
    startet irgendwann das Falsche.
    """

    def path(self) -> Path | None:
        """Die ausführbare Datei, wenn es eine gibt und sie gefunden wird."""
        if not self.executables:
            return None
        return discover.find_program(self.id, self.executables)

    def address(self) -> str:
        """Die Adresse, unter der der Dienst gesucht wird."""
        return discover.service_url(self.id, self.url) if self.url else ""

    def running(self) -> bool:
        """Antwortet der Dienst? Bei einem reinen Programm immer ``False``."""
        address = self.address()
        return bool(address) and discover.reachable(address)

    @property
    def available(self) -> bool:
        """Kann Solidon das gerade benutzen?

        Bei einem Dienst heißt das „antwortet", bei einem Programm „liegt da".
        Ein installiertes, aber nicht gestartetes Ollama ist für den Chat
        genauso wenig nutzbar wie ein nicht installiertes — nur ist der Satz
        dazu ein anderer, und den trägt :class:`ToolState`.
        """
        if self.kind == "service":
            return self.running()
        return self.path() is not None


#: Slicer, die G-Code schreiben. Nur für die Gegenprobe (§28.1) und zum
#: Weitergeben eines Modells nötig — nie, um eines zu rechnen.
SLICERS: Final = (
    "prusa-slicer",
    "PrusaSlicer",
    "prusa-slicer-console",
    "orca-slicer",
    "OrcaSlicer",
    "elegoo-slicer",
    "ElegooSlicer",
    "bambu-studio",
    "BambuStudio",
    "SuperSlicer",
    "superslicer",
    # Cura vor seiner Oberfläche: neben ``UltiMaker-Cura.exe`` liegt
    # ``CuraEngine.exe``, und nur die zweite hat eine Kommandozeile. Die erste
    # startet das Fenster, beendet sich mit Code 2 und schreibt nichts — was
    # als „Der Slicer hat keine Druckdatei geschrieben" ankam.
    "CuraEngine",
    "Ultimaker-Cura",
    "cura",
)

TOOLS: Final[tuple[ExternalTool, ...]] = (
    ExternalTool(
        id="slicer",
        title=_("Slicer"),
        what_for=_("Für die Druckdatei und die Gegenprobe aus dem G-Code."),
        executables=SLICERS,
    ),
    ExternalTool(
        id="ollama",
        title="Ollama",
        what_for=_("Sprachmodell lokal, statt mit eigenem Schlüssel."),
        kind="service",
        executables=("ollama",),
        url=llm.OLLAMA_URL,
        start_arguments=("serve",),
    ),
    ExternalTool(
        id="comfyui",
        title="ComfyUI",
        what_for=_("3D-Modell aus Text oder Bild erzeugen."),
        kind="service",
        executables=("ComfyUI", "comfyui", "comfy"),
        url=mesh.DEFAULT_COMFY_URL,
    ),
)


def by_id(tool_id: str) -> ExternalTool | None:
    """Ein Werkzeug beim Namen. Für die Oberfläche, die eine Zeile bearbeitet."""
    for tool in TOOLS:
        if tool.id == tool_id:
            return tool
    return None


@dataclass(frozen=True, slots=True)
class ToolState:
    """Was gefunden wurde, für die Erstinbetriebnahme und die Einstellungen."""

    tool: ExternalTool
    path: Path | None
    running: bool = False

    @property
    def available(self) -> bool:
        """Benutzbar — bei einem Dienst heißt das „läuft"."""
        if self.tool.kind == "service":
            return self.running
        return self.path is not None

    @property
    def installed(self) -> bool:
        """Auf dem Rechner vorhanden, ob gestartet oder nicht."""
        return self.path is not None or self.running

    def explain(self) -> TranslatableText | str:
        """Der Satz, der neben dem Zustand steht — er sagt, was als Nächstes hilft."""
        if self.available:
            return _("Vorhanden")
        if self.installed:
            # Nur der Dienst kommt hierher: die Datei liegt da, es läuft nur nicht.
            return _("Gefunden, aber es läuft gerade nicht — erst starten.")
        if self.tool.kind == "service":
            return _(
                "Antwortet nicht — es muss laufen. Steht es auf einem anderen "
                "Rechner, kann seine Adresse hier eingetragen werden."
            )
        return _(
            "Nicht gefunden. Wer es an einer ungewöhnlichen Stelle hat, kann sie hier angeben."
        )


def state_of(tool: ExternalTool) -> ToolState:
    """Ein Werkzeug einmal ansehen. Fehlend ist normal, kein Fehler."""
    return ToolState(tool=tool, path=tool.path(), running=tool.running())


def survey() -> tuple[ToolState, ...]:
    """Jedes externe Programm einmal suchen."""
    found = tuple(state_of(tool) for tool in TOOLS)
    _log.info("found %d of %d external tools", sum(1 for e in found if e.available), len(found))
    return found


def set_location(tool_id: str, location: str) -> None:
    """Den Pfad oder die Adresse merken, die jemand angegeben hat.

    Eine leere Angabe nimmt die Festlegung zurück und sucht wieder selbst.
    """
    discover.remember(tool_id, location)


#: Wie lange auf einen gestarteten Dienst gewartet wird, bevor gesagt wird,
#: dass er nicht antwortet. Ollama lädt beim Start seine Modellliste; eine
#: Sekunde ist zu wenig, eine Minute wäre ein Hänger.
START_TIMEOUT_SECONDS: Final = 20.0


def start(tool: ExternalTool, wait_seconds: float = START_TIMEOUT_SECONDS) -> bool:
    """Einen Dienst starten, der installiert ist und nicht läuft.

    **Warum das hier steht und nicht in einem Satz.** „Ollama antwortet nicht.
    Läuft es? «ollama serve» startet es." war die vollständige Auskunft — an
    einen Menschen, der gerade in einem Fenster sitzt und keine Konsole offen
    hat. Der Befehl ist derselbe, den er eintippen würde; ihn an einen Knopf
    zu hängen, nimmt ihm einen Umweg und keine Entscheidung ab.

    Der Prozess wird **losgelassen**: Er gehört nicht Solidon, er überlebt es
    und wird von Solidon nie beendet. Was hier zurückkommt, ist die Antwort
    auf die einzige Frage, die zählt — antwortet der Port jetzt?
    """
    if tool.kind != "service" or not tool.start_arguments:
        return False
    program = tool.path()
    if program is None:
        return False

    # Losgelöst und ohne Fenster: ein Konsolenfenster, das über der Anwendung
    # aufgeht, ist für den Nutzer ein Fehler und für uns nichts. Die beiden
    # Windows-Merker über ``getattr`` — sie gibt es dort nur, und eine
    # Typprüfung, die unter Linux läuft, kennt sie nicht.
    windows = sys.platform == "win32"
    no_window = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    detached = getattr(subprocess, "DETACHED_PROCESS", 0)
    # **Auch dieser Start geht auf den Rechner, nicht in den Sandkasten.**
    # ``program`` kommt aus ``discover.find_program`` und ist im Flatpak ein
    # Host-Pfad; im Sandkasten gibt es ihn nicht. Ohne ``on_host`` endet der
    # Knopf in einem ``OSError``, einer Protokollzeile und ``False`` — er tut
    # sichtbar nichts, und daneben steht weiter „Antwortet nicht".
    launched = discover.on_host([str(program), *tool.start_arguments])
    try:
        subprocess.Popen(
            launched,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            creationflags=(no_window | detached) if windows else 0,
            start_new_session=not windows,
        )
    except OSError as problem:
        _log.warning("could not start %s: %s", tool.id, problem)
        return False

    _log.info("started %s, waiting for its port", tool.id)
    deadline = time.monotonic() + wait_seconds
    while time.monotonic() < deadline:
        if tool.running():
            return True
        time.sleep(_POLL_SECONDS)
    return tool.running()


#: Wie oft nachgesehen wird, ob der Port antwortet. Die Probe selbst kostet
#: schon ein Viertel Sekunde (:data:`discover.PROBE_SECONDS`).
_POLL_SECONDS: Final = 0.25
