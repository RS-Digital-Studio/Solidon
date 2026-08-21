"""OpenSCAD als Rückfallebene (Bauplan §24.1, §32, §36).

Immer nur als installiertes externes Programm aufgerufen, nie mitgeliefert:
OpenSCAD ist GPL, die Anwendung nicht (§36). Und immer nur als Rückfall —
Bausteine sind gegen ``manifold3d`` gebaut, nichts auf dem Hauptweg braucht
also eine Installation (§24.1).

Was das hier sicher macht, ist nicht die Sandbox, sondern die Prüfung davor.
Quelltext erreicht dieses Modul aus zwei gleichermaßen unvertrauten
Richtungen: aus einer Projektdatei, die als Fehlerbericht herumgereicht wird
(§33.3), und aus einem Sprachmodell. Beide können ``include <...>`` enthalten,
das irgendwohin auf dem Rechner zeigt.

Also werden die Regeln aus §32 hier durchgesetzt, in dieser Reihenfolge:

1. der Quelltext wird **gelesen**, bevor er läuft — ``include``, ``use``,
   ``import`` und ``surface`` samt den veralteten Einbindungen
   (``import_stl`` und Verwandte) und jedem ``file=`` nur mit relativen
   Pfaden unterhalb des Arbeitsordners;
2. jeder Lauf bekommt seinen **eigenen Arbeitsordner** und nichts außerhalb;
3. **Zeit und Speicher sind gedeckelt**, und der Prozess bekommt kein Netz.

Ein abgelehnter Quelltext läuft gar nicht erst. Das steht in den Tests, denn
„es würde ohnehin scheitern" ist kein Sicherheitsargument.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

from app.core import discover
from app.core.errors import Action, AppError, ExternalToolError
from app.core.log import get_logger
from app.core.types import Finding
from app.i18n import _

_log = get_logger(__name__)

#: Anweisungen, die etwas anderes hereinholen. Jede einzelne ist ein Weg aus
#: dem Arbeitsordner hinaus, wenn der Pfad nicht geprüft wird. Die hinteren
#: fünf sind seit Jahren als veraltet gemeldet — OpenSCAD führt sie trotzdem
#: aus, also prüfen wir sie trotzdem.
INCLUDING = (
    "include",
    "use",
    "import",
    "surface",
    "import_stl",
    "import_dxf",
    "import_off",
    "dxf_linear_extrude",
    "dxf_rotate_extrude",
)

#: Dazu jedes ``file=``: ``linear_extrude`` und ``rotate_extrude`` (und die
#: dxf-Altformen) lesen darüber eine Datei, ohne dass der Modulname es verrät.

_INCLUDE_PATTERN = re.compile(
    r"\b(include|use)\s*<([^>]*)>"
    r"|\b(import_stl|import_dxf|import_off|dxf_linear_extrude|dxf_rotate_extrude"
    r"|import|surface)\s*\(\s*(?:file\s*=\s*)?\"([^\"]*)\""
    r"|\b(file)\s*=\s*\"([^\"]*)\"",
    re.IGNORECASE,
)

#: Dieselben Anweisungen, aber ohne Anspruch, ihr Ziel zu lesen.
#:
#: ``_INCLUDE_PATTERN`` erkennt nur die Schreibweise mit Zeichenkette. OpenSCAD
#: nimmt an dieser Stelle aber jeden Ausdruck: ``p = str("/e", "tc"); import(p);``
#: ist gültig und stand für die Literal-Suche gar nicht da — sie fand keinen
#: Verweis und gab den Lauf frei. Eine Prüfung, die man mit einer
#: Zeichenkettenverkettung umgeht, ist keine. Also wird jede Anweisung gezählt,
#: und was die Literal-Suche nicht erklären kann, gilt als nicht prüfbar.
_ANY_INCLUDE_PATTERN = re.compile(
    r"\b(include|use|import_stl|import_dxf|import_off|dxf_linear_extrude"
    r"|dxf_rotate_extrude|import|surface)\s*[<(]"
    r"|\bfile\s*=",
    re.IGNORECASE,
)

#: Wie lange ein Lauf dauern darf. Ein Modell, das länger braucht, ist kein
#: Rückfall, sondern ein Fehler (§31).
TIMEOUT_SECONDS = 60.0

#: Wie viel Speicher ein Lauf nehmen darf (§32). Das Zeitlimit allein genügt
#: nicht: ein ``for (i = [0 : 2000000])`` aus einem Sprachmodell füllt den
#: Arbeitsspeicher lange bevor eine Minute um ist, und was dann anfängt zu
#: swappen, ist der Rechner des Nutzers und nicht dieser Unterprozess.
#: Zwei Gigabyte sind großzügig für das, wofür diese Rückfallebene da ist.
MEMORY_LIMIT_BYTES = 2 * 1024**3

#: Namen, unter denen OpenSCAD installiert wird.
EXECUTABLES = ("openscad", "openscad-nightly", "OpenSCAD")


@dataclass(frozen=True, slots=True)
class SourceCheck:
    """Was das Lesen des Quelltexts ergeben hat (§32)."""

    allowed: bool
    references: tuple[str, ...] = ()
    refused: tuple[str, ...] = ()
    findings: tuple[Finding, ...] = ()

    @property
    def has_references(self) -> bool:
        return bool(self.references or self.refused)


class UnsafeSource(AppError):
    """Der Quelltext wollte etwas außerhalb seines Arbeitsordners."""

    default_title = _("Dieser OpenSCAD-Quelltext greift nach außen.")
    default_suggestions = (
        Action(id="remove_include", label=_("Die eingebundenen Dateien entfernen.")),
        Action(id="show_source", label=_("Quelltext ansehen.")),
    )


class ScadUnavailable(AppError):
    """OpenSCAD ist nicht installiert. Alles außer dieser Rückfallebene
    läuft weiter.
    """

    default_title = _("OpenSCAD ist auf diesem Rechner nicht installiert.")
    default_suggestions = (
        # ``install`` ist die Kennung von ``INSTALL_MISSING`` — der Handler des
        # Fensters hängt daran, und deshalb wird daraus ein Knopf und nicht bloß
        # ein Satz. Das Label bleibt eigen, weil es das Programm beim Namen
        # nennt; „und erneut versuchen" stand darin und war ein Versprechen, das
        # keine Handlung einlöst: installiert wird hier, wiederholt vom Nutzer.
        Action(id="install", label=_("OpenSCAD installieren …"), primary=True),
        Action(id="use_parts", label=_("Stattdessen einen Baustein verwenden.")),
    )


def check_source(source: str) -> SourceCheck:
    """Liest den Quelltext und entscheidet, ob er laufen darf (§32).

    Ein relativer Pfad unterhalb des Arbeitsordners ist in Ordnung. Alles
    andere — ein absoluter Pfad, ein Laufwerksbuchstabe, ein Schritt nach oben,
    eine URL — wird abgelehnt, und der Befund nennt, *was* abgelehnt wurde,
    nicht nur, dass etwas abgelehnt wurde.
    """
    references: list[str] = []
    refused: list[str] = []

    # Spannen statt Startpositionen: ``import(file="…")`` ist ein lesbarer
    # Fund, aber sein ``file=`` steht mitten darin — als bloße Position würde
    # der zweite Durchlauf es für eine eigene, ungelesene Anweisung halten.
    readable: list[tuple[int, int]] = []
    for match in _INCLUDE_PATTERN.finditer(source):
        path = next(
            (
                group
                for group in (match.group(2), match.group(4), match.group(6))
                if group is not None
            ),
            None,
        )
        if path is None:
            continue
        readable.append(match.span())
        (references if _is_local(path) else refused).append(path.strip())

    # Jede Anweisung, die keine lesbare Zeichenkette dabeihat, führt irgendwohin
    # — nur wohin, steht erst zur Laufzeit fest. Sie wird abgelehnt statt
    # übersehen: der Nutzer sieht die Stelle und kann sie ausschreiben.
    for match in _ANY_INCLUDE_PATTERN.finditer(source):
        if not any(start <= match.start() < end for start, end in readable):
            refused.append(match.group(0).strip())

    findings = tuple(
        Finding(
            code="scad.refused_reference",
            severity="error",
            message=_("Ein Verweis führt aus dem Arbeitsordner hinaus."),
            values={"reference": entry},
        )
        for entry in refused
    )
    if refused:
        _log.warning("refused %d OpenSCAD references", len(refused))
    return SourceCheck(
        allowed=not refused,
        references=tuple(references),
        refused=tuple(refused),
        findings=findings,
    )


def _is_local(path: str) -> bool:
    text = path.strip().replace("\\", "/")
    if not text:
        return False
    if text.startswith(("/", "~")):
        return False
    if re.match(r"^[a-zA-Z]:", text):
        return False
    if "://" in text:
        return False
    return not any(part == ".." for part in text.split("/"))


def available() -> bool:
    """Ob sich OpenSCAD überhaupt aufrufen lässt."""
    return executable() is not None


def executable() -> str | None:
    """Wo OpenSCAD liegt.

    Über :mod:`app.core.discover` und nicht über den PATH allein: sonst sagt
    der Dialog „gefunden" und die Operation danach „nicht installiert", weil
    beide verschieden gesucht haben.
    """
    from app.core import discover

    found = discover.find_program("openscad", EXECUTABLES)
    return str(found) if found is not None else None


@dataclass(slots=True)
class RenderResult:
    """Was ein Lauf erzeugt hat."""

    stl: bytes = b""
    findings: list[Finding] = field(default_factory=list)
    seconds: float = 0.0


def _limit_this_process(limit: int) -> None:  # pragma: no cover - läuft im Kindprozess
    """Setzt die Speichergrenze, nachdem der Kindprozess abgespalten ist.

    Nur auf POSIX; Windows kennt ``RLIMIT_AS`` nicht und bekommt weiter unten
    ein Job-Objekt.

    **Und die Grenze darf den Start nicht verhindern.** Was hier scheitert,
    scheitert im Kindprozess zwischen ``fork`` und ``exec``; Python macht
    daraus einen ``SubprocessError`` im Elternprozess, und der nimmt den
    ganzen Lauf mit. Auf macOS ist genau das passiert: Darwin setzt
    ``RLIMIT_AS`` nicht durch und weist den Wert zurück — OpenSCAD ließ sich
    dort **überhaupt nicht** aufrufen, und zwar für jeden Aufruf, nicht nur
    für große. Aufgefallen ist es erst, als die Suite auf dem Mac zum ersten
    Mal wirklich lief.

    Dieselbe Abwägung wie beim Windows-Job eine Etage tiefer: Eine
    Rückfallebene, die gar nicht startet, ist der schlechtere Tausch. Ohne
    Grenze bleibt das Zeitlimit, und das greift überall.
    """
    if sys.platform == "win32":
        return
    import contextlib
    import resource

    # Kein Protokoll im Fehlerfall: Zwischen fork und exec ist der Prozess ein
    # halber, und ein Logger, der hier eine Sperre anfasst, hängt ihn auf.
    with contextlib.suppress(OSError, ValueError):
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))


def _memory_capped_job(limit: int) -> int | None:
    """Ein Windows-Job-Objekt, das seinen Prozessen ``limit`` Bytes zugesteht.

    Das Gegenstück zu ``RLIMIT_AS``. Ein Prozess in einem solchen Job bekommt
    bei einer Anforderung darüber hinaus eine Fehlschlagsmeldung statt des
    Speichers — dieselbe Wirkung, anderer Weg.

    ``None``, wenn das System keinen Job hergibt. Dann läuft der Lauf ohne
    Speichergrenze weiter: eine Rückfallebene, die gar nicht startet, wäre der
    schlechtere Tausch, und das Zeitlimit greift weiterhin.
    """
    if sys.platform != "win32":
        return None
    import ctypes
    from ctypes import wintypes

    class _BasicLimits(ctypes.Structure):
        _fields_ = [
            ("PerProcessUserTimeLimit", ctypes.c_int64),
            ("PerJobUserTimeLimit", ctypes.c_int64),
            ("LimitFlags", wintypes.DWORD),
            ("MinimumWorkingSetSize", ctypes.c_size_t),
            ("MaximumWorkingSetSize", ctypes.c_size_t),
            ("ActiveProcessLimit", wintypes.DWORD),
            ("Affinity", ctypes.POINTER(ctypes.c_ulong)),
            ("PriorityClass", wintypes.DWORD),
            ("SchedulingClass", wintypes.DWORD),
        ]

    class _IoCounters(ctypes.Structure):
        _fields_ = [
            ("ReadOperationCount", ctypes.c_uint64),
            ("WriteOperationCount", ctypes.c_uint64),
            ("OtherOperationCount", ctypes.c_uint64),
            ("ReadTransferCount", ctypes.c_uint64),
            ("WriteTransferCount", ctypes.c_uint64),
            ("OtherTransferCount", ctypes.c_uint64),
        ]

    class _ExtendedLimits(ctypes.Structure):
        _fields_ = [
            ("BasicLimitInformation", _BasicLimits),
            ("IoInfo", _IoCounters),
            ("ProcessMemoryLimit", ctypes.c_size_t),
            ("JobMemoryLimit", ctypes.c_size_t),
            ("PeakProcessMemoryUsed", ctypes.c_size_t),
            ("PeakJobMemoryUsed", ctypes.c_size_t),
        ]

    job_memory_limit = 0x00000100
    extended_information_class = 9

    kernel = ctypes.windll.kernel32
    handle = int(kernel.CreateJobObjectW(None, None))
    if not handle:
        return None

    information = _ExtendedLimits()
    information.BasicLimitInformation.LimitFlags = job_memory_limit
    information.ProcessMemoryLimit = limit
    stored = kernel.SetInformationJobObject(
        handle,
        extended_information_class,
        ctypes.byref(information),
        ctypes.sizeof(information),
    )
    if not stored:
        kernel.CloseHandle(handle)
        return None
    return handle


def _join_job(job: int, pid: int) -> None:
    """Nimmt den frisch gestarteten Prozess in den Job auf."""
    if sys.platform != "win32":
        return
    import ctypes

    set_quota_and_terminate = 0x0100 | 0x0001
    kernel = ctypes.windll.kernel32
    process = int(kernel.OpenProcess(set_quota_and_terminate, False, pid))
    if not process:
        return
    try:
        kernel.AssignProcessToJobObject(job, process)
    finally:
        kernel.CloseHandle(process)


def run_guarded(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    timeout: float,
    memory: int = MEMORY_LIMIT_BYTES,
) -> subprocess.CompletedProcess[bytes]:
    """Führt ein fremdes Programm mit Zeit- **und** Speichergrenze aus (§32).

    Beides steht in §32 nebeneinander, und die Zeit allein reicht nicht: was in
    einer Minute den Arbeitsspeicher füllt, hat den Rechner schon geholt, bevor
    das Zeitlimit zuschlägt.

    Zwei Wege, weil die Systeme zwei anbieten — ``RLIMIT_AS`` im abgespaltenen
    Kind, ein Job-Objekt auf Windows. Der Job wird nach dem Start zugewiesen;
    in dem Augenblick dazwischen hat der Prozess noch nichts angefordert.
    """
    on_windows = sys.platform == "win32"
    job = _memory_capped_job(memory) if on_windows else None

    process = subprocess.Popen(
        command,
        cwd=cwd,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        preexec_fn=None if on_windows else (lambda: _limit_this_process(memory)),
    )
    try:
        if job is not None:
            _join_job(job, process.pid)
        try:
            out, err = process.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
            raise
    finally:
        if job is not None and sys.platform == "win32":
            import ctypes

            ctypes.windll.kernel32.CloseHandle(job)

    return subprocess.CompletedProcess(command, process.returncode, out, err)


def render(source: str, *, timeout: float = TIMEOUT_SECONDS) -> RenderResult:
    """Führt einen Quelltext aus und gibt das Netz zurück — nach der Prüfung,
    nie davor.
    """
    check = check_source(source)
    if not check.allowed:
        raise UnsafeSource(
            detail=", ".join(check.refused),
            values={"refused": ", ".join(check.refused)},
        )

    binary = executable()
    if binary is None:
        raise ScadUnavailable()

    import time

    started = time.perf_counter()
    # **Der Ordner muss dort liegen, wo dieses OpenSCAD hinsehen kann.** Ein
    # Flatpak hat sein eigenes ``/tmp``; die Datei wäre geschrieben, der Aufruf
    # käme an, und OpenSCAD fände nichts. Siehe ``discover.workspace_for``.
    with discover.workspace_for(binary, "solidon-scad-") as workspace:
        scad_file = workspace / "model.scad"
        stl_file = workspace / "model.stl"
        scad_file.write_text(source, encoding="utf-8")

        try:
            completed = run_guarded(
                [binary, "-o", str(stl_file), str(scad_file)],
                cwd=workspace,
                env=_environment(workspace),
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as expired:
            # Das Zeitlimit aus §32 ist kein Sonderfall, sondern der erwartete
            # Ausgang bei einer zu feinen Auflösung — ``sphere(r = 50,
            # $fn = 2000)`` genügt. Ungefangen kam ein Stapelabzug heraus, wo
            # ein Satz mit Ausweg hingehört (Regel 17).
            raise ExternalToolError(
                tool="OpenSCAD",
                detail=_(
                    "OpenSCAD hat länger gebraucht als erlaubt und wurde beendet. "
                    "Meist liegt es an einer sehr feinen Auflösung ($fn)."
                ),
                values={"seconds": timeout},
                suggestions=(
                    Action(id="lower_resolution", label=_("Die Auflösung verringern ($fn).")),
                    Action(id="show_source", label=_("Quelltext ansehen.")),
                    Action(id="use_parts", label=_("Stattdessen einen Baustein verwenden.")),
                ),
            ) from expired
        if completed.returncode != 0 or not stl_file.is_file():
            raise AppError(
                _("OpenSCAD konnte den Quelltext nicht übersetzen."),
                detail=completed.stderr.decode("utf-8", errors="replace")[:500],
                suggestions=(
                    Action(id="show_source", label=_("Quelltext ansehen.")),
                    Action(id="use_parts", label=_("Stattdessen einen Baustein verwenden.")),
                ),
            )
        payload = stl_file.read_bytes()

    return RenderResult(
        stl=payload,
        findings=[
            Finding(
                code="scad.rendered",
                severity="info",
                message=_("Dieser Körper kommt aus OpenSCAD, nicht aus der Bausteinbibliothek."),
                values={"bytes": len(payload)},
            )
        ],
        seconds=time.perf_counter() - started,
    )


def _environment(workspace: Path) -> dict[str, str]:
    """Ein Lauf bekommt einen festen Arbeitsordner und keinen Weg ins
    Netz (§32).

    Nichts hier hält ein entschlossenes Programm auf, und das soll es auch
    nicht: aufgehalten wird ein Quelltext, der still eine Schrift, eine Datei
    oder eine URL liest, weil das Modell zufällig danach gefragt hat.
    """
    keep = ("PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "HOME", "USERPROFILE", "DISPLAY")
    environment = {name: os.environ[name] for name in keep if name in os.environ}
    environment["OPENSCADPATH"] = str(workspace)
    environment["HTTP_PROXY"] = environment["HTTPS_PROXY"] = "127.0.0.1:0"
    environment["no_proxy"] = ""
    return environment
