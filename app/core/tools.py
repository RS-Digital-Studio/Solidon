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
sein Port. Ollama und ComfyUI sind beides: erst installiert, dann gestartet —
und zwischen diesen beiden Zuständen liegt genau der Satz, den jemand lesen
muss, um weiterzukommen.
"""

from __future__ import annotations

import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Final, Literal

from app.core import discover
from app.core.backends import llm, mesh
from app.core.log import get_logger
from app.i18n import TranslatableText, _

_log = get_logger(__name__)

Kind = Literal["program", "service"]


#: Wie lange auf einen gestarteten Dienst gewartet wird, bevor gesagt wird,
#: dass er nicht antwortet. Ollama lädt beim Start seine Modellliste; eine
#: Sekunde ist zu wenig, eine Minute wäre ein Hänger.
START_TIMEOUT_SECONDS: Final = 20.0


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
    start_arguments: tuple[str, ...] | None = None
    """Womit sich dieser Dienst starten lässt, oder nichts.

    ``None`` heißt: Solidon kennt keinen sicheren Startweg. Ein leeres Tupel
    heißt dagegen: die gefundene Desktop-Anwendung selbst öffnen.
    """
    start_argument_overrides: tuple[tuple[str, tuple[str, ...]], ...] = ()
    """Abweichende Argumente für einen bestimmten Programmnamen.

    Comfy Desktop wird ohne Argument geöffnet; die offizielle ``comfy``-CLI
    startet denselben Dienst mit ``launch --background``. Beides ist
    dokumentiert, nichts davon wird aus einem Installationsordner geraten.
    """
    start_seconds: float = START_TIMEOUT_SECONDS
    """Wie lange dieser Dienst zum Hochfahren haben darf.

    **Am gemessenen Startweg kalibriert, nicht geraten.** Zwanzig Sekunden
    waren der gemeinsame Wert für alle, und für Ollama stimmen sie: Es
    antwortet in wenigen Sekunden. ComfyUI Desktop lädt in derselben Zeit noch
    seine Plugins — gemessen am 30.08.2026 antwortete es nach gut zwei
    Minuten, und Solidon meldete nach zwanzig Sekunden einen Fehlschlag über
    einen laufenden Start.

    Das Limit bleibt hart, es gilt nur dem echten Hänger (`kern.md`: „Ein
    Zeitlimit gilt dem Hängen, nicht der Langsamkeit"). Was sich ändert, ist
    die Zahl **und** dass die Wartezeit sichtbar wird — ein stummer Dialog
    über drei Minuten wäre die schlechtere Hälfte des Fehlers (§2.8).
    """

    def path(self) -> Path | None:
        """Die ausführbare Datei, wenn es eine gibt und sie gefunden wird."""
        if not self.executables:
            return None
        return discover.find_program(self.id, self.executables)

    @property
    def startable(self) -> bool:
        """Kennt Solidon für diesen Dienst einen ausdrücklichen Startweg?"""
        return self.kind == "service" and self.start_arguments is not None

    def start_command(self) -> list[str] | None:
        """Der vollständige Startbefehl, oder ``None`` ohne gefundenes Programm."""
        if not self.startable:
            return None
        program = self.path()
        if program is None:
            return None
        if sys.platform == "darwin" and program.suffix.lower() == ".app":
            return ["/usr/bin/open", str(program)]
        arguments = self.start_arguments or ()
        program_name = discover.plain_name(program.name)
        for name, replacement in self.start_argument_overrides:
            if program_name == discover.plain_name(name):
                arguments = replacement
                break
        return [str(program), *arguments]

    def address(self) -> str:
        """Die Adresse, unter der der Dienst gesucht wird."""
        return discover.service_url(self.id, self.url) if self.url else ""

    def remote_address(self) -> str:
        """Die gespeicherte Netzadresse, auch während der lokale Dienst aktiv ist."""
        return discover.remembered_remote_address(self.id) if self.url else ""

    @property
    def using_remote_address(self) -> bool:
        """Ist die gespeicherte Netzadresse statt der lokalen Vorgabe aktiv?"""
        chosen = discover.remembered_address(self.id).rstrip("/")
        return bool(chosen and chosen != self.url.rstrip("/"))

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
        # Der offizielle Desktop heißt seit 2026 ``Comfy Desktop``. Die alten
        # Namen bleiben für dessen Vorgänger und für portable Installationen;
        # ``comfy`` ist die offizielle CLI.
        executables=(
            "Comfy Desktop",
            "comfy-desktop",
            "comfyui-desktop",
            "ComfyUI",
            "comfyui",
            "comfy",
        ),
        url=mesh.DEFAULT_COMFY_URL,
        start_arguments=(),
        start_argument_overrides=(("comfy", ("launch", "--background")),),
        # Gemessen: Comfy Desktop antwortet auf dieser Maschine nach gut zwei
        # Minuten. Drei sind der Abstand, ab dem es wirklich hängt.
        start_seconds=180.0,
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


@dataclass(frozen=True, slots=True)
class StartResult:
    """Was beim Öffnen eines lokalen Dienstes tatsächlich passiert ist."""

    program: Path | None = None
    command: tuple[str, ...] = ()
    address: str = ""
    launched: bool = False
    running: bool = False
    reason: str = ""
    stopped: bool = False
    """Ob **das Warten** abgebrochen wurde — der Dienst läuft weiter.

    Am Ergebnis und nicht als Merkmal am Dialog, und das ist der Unterschied
    zwischen einer Wahrheit und einer Vermutung: Ein Merkmal am Fenster gilt
    für den *nächsten* Rückruf mit, auch wenn der zu einem anderen Lauf
    gehört. Ein Ergebnis trägt seine eigene Herkunft — auch ein Nachzügler,
    der eintrifft, wenn längst etwas anderes läuft.
    """


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


def set_program(tool_id: str, location: str) -> None:
    """Den lokalen Startpfad setzen, ohne eine Netzadresse zu verwerfen."""
    discover.remember_path(tool_id, location)


def set_address(tool_id: str, address: str) -> None:
    """Die Netzadresse setzen, ohne einen lokalen Startpfad zu verwerfen."""
    discover.remember_address(tool_id, address)


def start_detailed(
    tool: ExternalTool,
    wait_seconds: float | None = None,
    progress: Callable[[float, float], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> StartResult:
    """Einen lokalen Dienst öffnen und das Ergebnis vollständig beschreiben.

    **Warum das hier steht und nicht in einem Satz.** „Ollama antwortet nicht.
    Läuft es? «ollama serve» startet es." war die vollständige Auskunft — an
    einen Menschen, der gerade in einem Fenster sitzt und keine Konsole offen
    hat. Bei ComfyUI gilt dasselbe für die Desktop-App und die offizielle CLI.
    Der dokumentierte Befehl hängt an einem Knopf und erspart den Umweg über
    ein Terminal.

    Der Prozess wird **losgelassen**: Er gehört nicht Solidon, er überlebt es
    und wird von Solidon nie beendet. Was hier zurückkommt, ist die Antwort
    auf die einzige Frage, die zählt — antwortet der Port jetzt?
    """
    command = tool.start_command()
    if command is None:
        return StartResult(reason="Kein lokales Startprogramm gefunden.")

    program = Path(command[1]) if command[0] == "/usr/bin/open" else Path(command[0])
    # Wer „Lokal starten“ drückt, meint den lokalen Vorgabedienst. Eine zuvor
    # gespeicherte Netzadresse bleibt erhalten, darf aber weder die Startprobe
    # noch den anschließenden Modellweg auf einen anderen Rechner lenken.
    target_address = tool.url or tool.address()

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
    launched = discover.on_host(command)
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
        return StartResult(
            program=program,
            command=tuple(command),
            address=target_address,
            reason=str(problem),
        )

    _log.info("started %s, waiting for %s", tool.id, target_address)
    # Ohne ausdrückliche Angabe die am Dienst kalibrierte Zeit — nicht die
    # gemeinsame Zahl, die für Ollama passt und für ComfyUI nicht.
    limit = tool.start_seconds if wait_seconds is None else wait_seconds
    begun = time.monotonic()
    deadline = begun + limit
    while time.monotonic() < deadline:
        if target_address and discover.reachable(target_address):
            discover.use_local_address(tool.id)
            return StartResult(
                program=program,
                command=tuple(command),
                address=target_address,
                launched=True,
                running=True,
            )
        if cancelled is not None and cancelled():
            # Abgebrochen heißt: Solidon wartet nicht mehr. Der Dienst läuft
            # weiter — er gehört uns nicht und wird von uns nie beendet.
            return StartResult(
                program=program,
                command=tuple(command),
                address=target_address,
                launched=True,
                stopped=True,
                reason=str(_("Das Warten wurde abgebrochen. Der Dienst startet weiter.")),
            )
        if progress is not None:
            progress(time.monotonic() - begun, limit)
        time.sleep(_POLL_SECONDS)
    running = bool(target_address) and discover.reachable(target_address)
    if running:
        discover.use_local_address(tool.id)
    return StartResult(
        program=program,
        command=tuple(command),
        address=target_address,
        launched=True,
        running=running,
    )


def start(tool: ExternalTool, wait_seconds: float | None = None) -> bool:
    """Kompatible Kurzantwort für bestehende Einrichtungswege."""
    return start_detailed(tool, wait_seconds).running


#: Wie oft nachgesehen wird, ob der Port antwortet. Die Probe selbst kostet
#: schon ein Viertel Sekunde (:data:`discover.PROBE_SECONDS`).
_POLL_SECONDS: Final = 0.25
