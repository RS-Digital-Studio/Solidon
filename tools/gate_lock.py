"""Ein Schloss für das Tor: nur ein Testlauf gleichzeitig auf dieser Maschine.

An diesem Projekt arbeiten regelmäßig zwei bis vier Sitzungen nebeneinander.
Die **Dateien** trennt Claude Code selbst — jede Sitzung bekommt mit
``claude --worktree`` ihren eigenen Arbeitsbaum. Die **Maschine** trennt es
nicht, und genau daran scheitern Messungen.

Der Beleg ist vom 22.08.2026: zwei Läufe derselben Software am selben Tag, bei
48 Prozent Fremdlast **fünf rot**, bei 16 Prozent **neunzehn grün**. Alle fünf
waren die 25-Prozent-Regressionsschwelle, kein Zielwert aus Bauplan §31. Wer
gegen Fremdlast misst, meldet eine Regression, die es nicht gibt — und der
nächste sucht sie eine Stunde lang.

Benutzt wird es, indem es den Lauf **umschließt**::

    python tools/gate_lock.py run --who "meine-sitzung" -- .venv/Scripts/python.exe -m pytest -q
    python tools/gate_lock.py status

Der Rückgabewert ist der des umschlossenen Befehls, damit ein Tor hinter dem
Schloss dasselbe sagt wie davor. Ist das Schloss belegt, endet ``run`` mit 75
(``EX_TEMPFAIL``) und nennt Halter und Alter; ``--wait SEKUNDEN`` wartet
stattdessen.

**Warum umschließend und nicht als Paar aus Nehmen und Freigeben:** Der erste
Entwurf hatte ``nehmen``/``freigeben`` und scheiterte an der Prozessnummer. Ein
Schloss muss wissen, ob sein Halter noch lebt, sonst sperrt eine abgestürzte
Sitzung alle anderen aus. Gemessen am 22.08.2026:

* ``os.getpid()`` gehört dem aufrufenden Python, und das endet nach dem Nehmen
  — das Schloss wäre eine Sekunde später verwaist.
* ``os.getppid()`` ist unter Git Bash nicht stabil: zwei Aufrufe derselben
  Shell meldeten 9604 und 15596.
* ``$$`` ist eine bash-interne Nummer, kein Windows-Prozess. ``OpenProcess``
  findet sie nicht, und das Schloss gilt sofort als tot.

Umschließend gibt es das Problem nicht: Der Halter **ist** der laufende
Prozess. Er trägt seine echte Nummer ein, gibt im ``finally`` frei, und wenn er
abstürzt, sieht der nächste an der Nummer, dass niemand mehr da ist.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import math
import os
import subprocess
import sys
import time
from functools import cache
from pathlib import Path
from typing import Any, TypedDict

if str(Path(__file__).resolve().parent.parent) not in sys.path:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.licence_archive import ArchiveBusyError, archive_lock

#: Wie lange ein Schloss höchstens gilt, auch wenn sein Prozess noch lebt.
#:
#: Der zweite Rettungsanker neben der Prozessnummer, für den Fall, dass ein
#: Prozess hängt statt zu enden. Zwei Stunden sind großzügiger als jeder Lauf
#: dieses Projekts: der geteilte Durchgang samt Leistungstests braucht keine
#: dreißig Minuten.
MAX_AGE_SECONDS = 2 * 60 * 60

#: Wie oft beim Warten nachgesehen wird. Ein Testlauf dauert Minuten; jede
#: Sekunde nachzusehen wäre Lärm ohne Nutzen.
POLL_SECONDS = 5.0

#: „Gerade nicht, versuch es später" — derselbe Wert, den Unix dafür kennt.
#: Ein belegtes Schloss ist kein Fehlschlag des Tors, und es darf nicht wie
#: einer aussehen.
BUSY_EXIT = 75


def common_dir() -> Path:
    """Das Git-Verzeichnis, das sich alle Arbeitsbäume teilen.

    Nicht ``--git-dir``: Der zeigt in einem Arbeitsbaum auf dessen eigenen
    Unterordner, und dann hätte jede Sitzung ihr eigenes Schloss — also keines.
    """
    finished = subprocess.run(
        ["git", "rev-parse", "--git-common-dir"],
        capture_output=True,
        text=True,
        check=True,
    )
    return Path(finished.stdout.strip()).resolve()


def _lock_file() -> Path:
    return common_dir() / "solidon-tor.lock"


def _alive(pid: int) -> bool:
    """Läuft dieser Prozess noch?

    Im Zweifel gilt er als **lebend**: Ein Schloss zu übernehmen, das noch
    jemand hält, ist der teurere Fehler.

    Auf Windows über ``OpenProcess`` und nicht über ``tasklist``. Der erste
    Anlauf tat das und scheiterte in der Gegenprobe: Die Ausgabe von
    ``tasklist`` ist auf einem deutschen Windows nicht cp1252, ``text=True``
    warf beim Dekodieren, und ``stdout`` blieb ``None`` — die Prüfung stürzte
    also genau dann ab, wenn sie gebraucht wurde. Die Windows-Schnittstelle
    liefert die Antwort als Zahl und hat gar keine Kodierung.

    ``os.kill(pid, 0)`` scheidet dort aus: Python setzt es auf Windows über
    ``TerminateProcess`` um, und das beendet den Prozess, statt nach ihm zu
    fragen.
    """
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes

        #: Reicht, um nach der Existenz zu fragen; verlangt keine Rechte am
        #: fremden Prozess.
        query_limited_information = 0x1000
        kernel = ctypes.windll.kernel32
        handle = kernel.OpenProcess(query_limited_information, False, pid)
        if handle:
            # **Ein Handle heißt nicht „läuft".** Windows gibt den
            # Prozesseintrag erst frei, wenn das letzte Handle darauf
            # geschlossen ist — und solange der Starter eines Prozesses seines
            # offen hält (jedes ``subprocess.Popen`` tut das), liefert
            # ``OpenProcess`` auch für einen längst beendeten Prozess eines.
            # Am 22.08.2026 stand das Schloss deshalb neunzehn Minuten auf
            # einem toten Halter, und vier Sitzungen kamen nicht ins Tor.
            #
            # Die Unschärfe, die bleibt: Ein Prozess, der wirklich mit 259
            # endet, ist von einem laufenden nicht zu unterscheiden. Das ist
            # selten und der billigere Fehler — er geht in die Richtung „gilt
            # als lebend", und ein Schloss, das im Zweifel hält, sperrt
            # jemanden aus, statt zwei Läufe gleichzeitig zuzulassen.
            still_active = 259
            code = ctypes.c_ulong()
            ok = kernel.GetExitCodeProcess(handle, ctypes.byref(code))
            kernel.CloseHandle(handle)
            return not ok or int(code.value) == still_active
        # 5 heißt „Zugriff verweigert" — den Prozess *gibt* es dann, er gehört
        # nur jemand anderem. 87 heißt „ungültiger Parameter", und das ist die
        # Antwort für eine Nummer, die niemand mehr trägt.
        return int(kernel.GetLastError()) != 87
    else:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        except OSError:
            return True
        return True


#: Wie lange gemessen wird, um „steht" von „rechnet" zu trennen. Kürzer wird
#: es ungenau — eine Rechnung, die gerade auf die Platte schreibt, sieht sonst
#: aus wie ein Stillstand.
IDLE_SAMPLE_SECONDS = 2.0

#: Ab wann ein stehender Halter überhaupt erwähnt wird. Ein Testlauf, der
#: gerade ein Fenster aufbaut, steht sekundenweise — das ist normal und keine
#: Meldung wert.
IDLE_REPORT_SECONDS = 120.0


class ProcessQueryError(RuntimeError):
    """Die Prozessabfrage lieferte keine belastbare Auskunft."""


class _WindowsProcessEntry(ctypes.Structure):
    """PROCESSENTRY32W mit zeigerbreitem Heap-Feld, auch auf 64-Bit-Windows."""

    _fields_ = [
        ("size", ctypes.c_uint32),
        ("usage", ctypes.c_uint32),
        ("pid", ctypes.c_uint32),
        ("heap", ctypes.c_size_t),
        ("module", ctypes.c_uint32),
        ("threads", ctypes.c_uint32),
        ("parent", ctypes.c_uint32),
        ("priority", ctypes.c_int32),
        ("flags", ctypes.c_uint32),
        ("name", ctypes.c_wchar * 260),
    ]


class _WindowsUnicodeString(ctypes.Structure):
    """UNICODE_STRING trägt Bytezahlen und einen Zeiger, keinen Python-Text."""

    _fields_ = [
        ("length", ctypes.c_uint16),
        ("maximum", ctypes.c_uint16),
        ("buffer", ctypes.c_void_p),
    ]


@cache
def _windows_process_api() -> tuple[Any, Any]:
    """Lädt die vorhandenen System-APIs dynamisch und bindet ihre echten Zeigertypen."""
    if sys.platform == "win32":
        try:
            kernel = ctypes.WinDLL("kernel32", use_last_error=True)
            native = ctypes.WinDLL("ntdll", use_last_error=True)
            signatures = {
                "CreateToolhelp32Snapshot": ([ctypes.c_uint32, ctypes.c_uint32], ctypes.c_void_p),
                "Process32FirstW": (
                    [ctypes.c_void_p, ctypes.POINTER(_WindowsProcessEntry)],
                    ctypes.c_int,
                ),
                "Process32NextW": (
                    [ctypes.c_void_p, ctypes.POINTER(_WindowsProcessEntry)],
                    ctypes.c_int,
                ),
                "OpenProcess": ([ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32], ctypes.c_void_p),
                "CloseHandle": ([ctypes.c_void_p], ctypes.c_int),
            }
            for name, (arguments, result) in signatures.items():
                function = getattr(kernel, name)
                function.argtypes = arguments
                function.restype = result
            native.NtQueryInformationProcess.argtypes = [
                ctypes.c_void_p,
                ctypes.c_uint32,
                ctypes.c_void_p,
                ctypes.c_uint32,
                ctypes.POINTER(ctypes.c_uint32),
            ]
            native.NtQueryInformationProcess.restype = ctypes.c_int32
        except (OSError, AttributeError) as exc:
            raise ProcessQueryError(
                f"Windows-Prozessabfrage nicht verfügbar: {type(exc).__name__}."
            ) from None
        return kernel, native
    else:
        raise ProcessQueryError("Windows-Prozessabfrage nicht verfügbar: andere Plattform.")


def _windows_last_error() -> int:
    """Liest den Threadfehler ausschließlich auf der Plattform, die diesen Vertrag anbietet."""
    if sys.platform == "win32":
        return ctypes.get_last_error()
    else:
        raise ProcessQueryError("Windows-Prozessabfrage nicht verfügbar: andere Plattform.")


def _windows_processes() -> dict[int, tuple[int, str]]:
    """Liest den Prozessbestand einmal; nur ERROR_NO_MORE_FILES beendet ihn erfolgreich."""
    kernel, _ = _windows_process_api()
    snapshot = kernel.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
    if snapshot in (None, 0, ctypes.c_void_p(-1).value):
        raise ProcessQueryError(f"Windows-Prozessbestand: Fehler {_windows_last_error()}.")
    try:
        entry = _WindowsProcessEntry(size=ctypes.sizeof(_WindowsProcessEntry))
        found = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        processes = {}
        while found:
            processes[int(entry.pid)] = (int(entry.parent), entry.name)
            found = kernel.Process32NextW(snapshot, ctypes.byref(entry))
        error = _windows_last_error()
        if error != 18:  # ERROR_NO_MORE_FILES
            raise ProcessQueryError(f"Windows-Prozessbestand unvollständig: Fehler {error}.")
        return processes
    finally:
        kernel.CloseHandle(snapshot)


def _windows_command_line(pid: int) -> str | None:
    """Liest eine Befehlszeile ohne PowerShell-Start und ohne fremden PEB-Speicher.

    ProcessCommandLineInformation (60) gibt seit Windows 8.1 den Text direkt
    mit QUERY_LIMITED_INFORMATION zurück. Die interne NT-API wird dynamisch
    geladen; fehlt sie oder ändert sich ihr Vertrag, bleibt die Auskunft
    ausdrücklich unbekannt. Quelle: Microsoft NtQueryInformationProcess;
    der eingeschränkte Zugriff ist auch in psutil, Issue 1384, belegt.
    """
    kernel, native = _windows_process_api()
    handle = kernel.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
    if not handle:
        error = _windows_last_error()
        if error == 87:  # ERROR_INVALID_PARAMETER: seit dem Snapshot verschwunden
            return None
        raise ProcessQueryError(f"Windows-Prozess {pid} nicht lesbar: Fehler {error}.")
    try:
        required = ctypes.c_uint32()
        status = native.NtQueryInformationProcess(handle, 60, None, 0, ctypes.byref(required))
        status &= 0xFFFFFFFF
        if status == 0xC000010A:  # STATUS_PROCESS_IS_TERMINATING
            return None
        if status not in (0xC0000004, 0xC0000023):  # INFO_LENGTH_MISMATCH, BUFFER_TOO_SMALL
            raise ProcessQueryError(
                f"Windows-Prozess {pid}: NTSTATUS 0x{status:08X} beim Abmessen."
            )
        # UNICODE_STRING verwendet USHORT-Bytezahlen. Größer kann sein Text
        # nicht sein; ein kaputter Größenwert darf keine Allokation auslösen.
        header_size = ctypes.sizeof(_WindowsUnicodeString)
        if not header_size <= required.value <= header_size + 0xFFFF:
            raise ProcessQueryError(
                f"Windows-Prozess {pid}: ungültige Puffergröße {required.value}."
            )
        buffer = ctypes.create_string_buffer(required.value)
        returned = ctypes.c_uint32()
        status = (
            native.NtQueryInformationProcess(
                handle, 60, buffer, len(buffer), ctypes.byref(returned)
            )
            & 0xFFFFFFFF
        )
        if status == 0xC000010A:
            return None
        if status != 0:
            raise ProcessQueryError(f"Windows-Prozess {pid}: NTSTATUS 0x{status:08X} beim Lesen.")
        if not header_size <= returned.value <= len(buffer):
            raise ProcessQueryError(
                f"Windows-Prozess {pid}: ungültige Antwortlänge {returned.value}."
            )
        text = _WindowsUnicodeString.from_buffer(buffer)
        if text.length > text.maximum or text.length % 2 or text.maximum % 2:
            raise ProcessQueryError(f"Windows-Prozess {pid}: ungültige Textlänge.")
        if text.length == 0 and not text.buffer:
            return ""
        start = ctypes.addressof(buffer)
        pointer = text.buffer or 0
        if (
            pointer % 2
            or not start + header_size <= pointer <= start + returned.value - text.maximum
        ):
            raise ProcessQueryError(
                f"Windows-Prozess {pid}: Textzeiger außerhalb des Antwortpuffers."
            )
        return ctypes.string_at(pointer, text.length).decode("utf-16-le", errors="surrogatepass")
    finally:
        kernel.CloseHandle(handle)


def _descendants(root: int) -> set[int]:
    """Der ganze Prozessbaum unter ``root``, einschließlich ``root`` selbst.

    **Über die Kette und nicht über direkte Kinder.** Am 22.08.2026 hat eine
    Sitzung einen laufenden Testlauf für tot erklärt, weil unter der bash kein
    Kind stand — der ``pytest`` hing eine Ebene tiefer, an einem
    Zwischenprozess, der inzwischen beendet war. Wer nur die erste Ebene
    zählt, misst etwas, das neben der Sache steht.
    """
    parents: dict[int, int] = {}
    if sys.platform == "win32":
        parents = {pid: parent for pid, (parent, _) in _windows_processes().items()}
    else:
        for entry in Path("/proc").glob("[0-9]*"):
            try:
                fields = (entry / "stat").read_text(encoding="utf-8").rsplit(") ", 1)[-1].split()
                parents[int(entry.name)] = int(fields[1])
            except OSError, ValueError, IndexError:
                continue

    tree = {root}
    # Mehrfach durchlaufen: Die Liste steht in beliebiger Reihenfolge, ein Kind
    # kann vor seinem Elternteil kommen.
    for _ in range(len(parents) + 1):
        grown = {kind for kind, vater in parents.items() if vater in tree}
        if grown <= tree:
            break
        tree |= grown
    return tree


def _test_processes() -> set[int]:
    """Laufende Testprozesse, gefunden am **Kommando** statt an der Abstammung.

    **Warum die Kette allein nicht reicht, und der Fall, der es gezeigt hat.**
    Am 22.08.2026 hielt eine Sitzung das Schloss, und der Wächter meldete
    „rechnet nicht" — richtig, aber aus dem falschen Grund: Sein Baum bestand
    aus **einem** Prozess, dem Halter selbst. Der ``pytest`` lief unter einer
    ganz anderen Kette, weil Windows die Elternnummer eines Prozesses nicht
    umsetzt, wenn der Elternprozess endet; die Kette bricht dort ab, und alles
    darunter ist über die Abstammung nicht mehr erreichbar.

    Zufällig stimmte die Meldung damals. Strukturell hieße es: Ein gesunder,
    rechnender Lauf bekäme dieselbe Warnung, und jemand bräche ihn ab — 3453
    bestandene Tests für einen Fehlalarm. Deshalb sucht der Wächter zusätzlich
    am Kommando: Ein Prozess, der ``pytest`` fährt, gehört zum Lauf, ganz
    gleich, wer gerade sein Elternteil ist.

    Eine erfolgreiche leere Abfrage bedeutet keine gefundenen Tests. Eine
    gescheiterte Systemabfrage wirft ``ProcessQueryError`` mit Fehlerart,
    aber ohne fremde Kommandozeilen. Der Aufrufer darf diese
    fehlende Auskunft nicht als leeren Prozessbestand lesen.
    """
    found: set[int] = set()
    if sys.platform == "win32":
        for pid, (_, name) in _windows_processes().items():
            if "python" not in name.casefold():
                continue
            line = _windows_command_line(pid) or ""
            # Wartende gate_lock-Hüllen tragen den geschützten pytest-Befehl
            # ebenfalls in ihren Argumenten, sind aber selbst keine Testläufe.
            if "-m pytest" in line and "gate_lock" not in line:
                found.add(pid)
    else:
        for entry in Path("/proc").glob("[0-9]*"):
            try:
                line = (
                    (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
                )
            except OSError:
                continue
            if "-m pytest" in line and "gate_lock" not in line:
                found.add(int(entry.name))
    return found


def _cpu_seconds(pid: int) -> float | None:
    """Verbrauchte Rechenzeit eines Prozesses, oder nichts.

    ``None`` heißt „keine Aussage möglich" — der Prozess ist weg, gehört
    jemand anderem, oder das System gibt die Auskunft nicht. Es heißt nie
    „rechnet nicht".
    """
    if sys.platform == "win32":
        import ctypes
        import ctypes.wintypes as wt

        kernel = ctypes.windll.kernel32
        handle = kernel.OpenProcess(0x1000, False, pid)  # QUERY_LIMITED_INFORMATION
        if not handle:
            return None
        try:
            created, exited, kernel_time, user_time = (wt.FILETIME() for _ in range(4))
            ok = kernel.GetProcessTimes(
                handle,
                ctypes.byref(created),
                ctypes.byref(exited),
                ctypes.byref(kernel_time),
                ctypes.byref(user_time),
            )
            if not ok:
                return None

            # FILETIME zählt in 100-Nanosekunden-Schritten.
            def _as_seconds(value: wt.FILETIME) -> float:
                return ((int(value.dwHighDateTime) << 32) + int(value.dwLowDateTime)) / 1e7

            return _as_seconds(kernel_time) + _as_seconds(user_time)
        finally:
            kernel.CloseHandle(handle)
    else:
        try:
            fields = (
                Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").rsplit(") ", 1)[-1].split()
            )
            ticks = float(fields[11]) + float(fields[12])
            return ticks / os.sysconf("SC_CLK_TCK")
        except OSError, ValueError, IndexError:
            return None


def _started_at(pid: int) -> float | None:
    """Wann ein Prozess erzeugt wurde, als Unix-Zeit — oder nichts.

    Gebraucht, um fremde Testläufe auszuschließen: Wer schon lief, bevor das
    Schloss genommen wurde, gehört nicht zu seinem Halter. Ohne diese Grenze
    zählt der Wächter jeden ``pytest`` auf der Maschine mit und schweigt,
    solange irgendjemand rechnet — gemessen am 22.08.2026, als vier Sitzungen
    gleichzeitig arbeiteten und er acht fremde Prozesse für den Lauf hielt,
    den er beurteilen sollte.
    """
    if sys.platform == "win32":
        import ctypes
        import ctypes.wintypes as wt

        kernel = ctypes.windll.kernel32
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return None
        try:
            created, exited, kernel_time, user_time = (wt.FILETIME() for _ in range(4))
            ok = kernel.GetProcessTimes(
                handle,
                ctypes.byref(created),
                ctypes.byref(exited),
                ctypes.byref(kernel_time),
                ctypes.byref(user_time),
            )
            if not ok:
                return None
            #: FILETIME zählt 100-Nanosekunden-Schritte seit 1601, Unix-Zeit
            #: Sekunden seit 1970. Dazwischen liegen 11644473600 Sekunden.
            hundert_ns = (int(created.dwHighDateTime) << 32) + int(created.dwLowDateTime)
            return hundert_ns / 1e7 - 11644473600.0
        finally:
            kernel.CloseHandle(handle)
    else:
        try:
            # Feld 22 ist die Startzeit in Ticks seit dem Systemstart.
            fields = (
                Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").rsplit(") ", 1)[-1].split()
            )
            ticks = float(fields[19]) / os.sysconf("SC_CLK_TCK")
            uptime = float(Path("/proc/uptime").read_text(encoding="utf-8").split()[0])
            return time.time() - (uptime - ticks)
        except OSError, ValueError, IndexError:
            return None


def _sum_cpu(pids: set[int]) -> float | None:
    """Rechenzeit einer Prozessmenge. ``None``, wenn keiner Auskunft gibt."""
    values = [value for pid in pids if (value := _cpu_seconds(pid)) is not None]
    return sum(values) if values else None


def standing_still(
    pid: int, sample: float = IDLE_SAMPLE_SECONDS, extra: frozenset[int] = frozenset()
) -> bool | None:
    """Ob der Baum unter ``pid`` gerade **nicht** rechnet.

    Gemessen wird über ein Intervall und nicht als Gesamtwert: Die Gesamtzeit
    eines wartenden Wrappers ist immer klein, egal was sein Kind tut — auch
    dieser Fehler ist am 22.08.2026 einmal gemacht worden. ``None`` heißt
    „nicht messbar" und wird nie als „steht" gelesen.
    """
    # **Jeder gefundene Prozess bringt seinen Unterbaum mit.** Ein
    # ``subprocess.Popen`` startet auf Windows einen Wrapper, der den echten
    # Python-Prozess erst erzeugt: Der Wrapper verbraucht 0,016 Sekunden und
    # steht danach still, während sein Kind rechnet. Wer nur die gefundene
    # Nummer misst, hält jeden solchen Lauf für stehend — gemessen am
    # 22.08.2026, als diese Zeile noch ``| set(extra)`` hieß.
    watched = _descendants(pid)
    for extra_pid in extra:
        watched |= _descendants(extra_pid)
    before = _sum_cpu(watched)
    if before is None:
        return None
    time.sleep(sample)
    after = _sum_cpu(watched)
    if after is None:
        return None
    # Eine Zehntelsekunde Toleranz: Ein Prozess, der nur seine eigene Uhr
    # liest, ist kein rechnender Testlauf.
    return (after - before) < 0.1


class _LockEntry(TypedDict, total=False):
    """Geprüfte Schlossfelder; Zahlenzeichenketten bleiben für vorhandene Dateien lesbar."""

    wer: str
    pid: int | float | str | None
    seit: int | float | str | None


def _idle_note(entry: _LockEntry) -> str:
    """Ein Satz über den Halter, wenn er steht — sonst nichts.

    Er tötet nichts und schlägt es auch nicht vor. Am 22.08.2026 standen zwei
    Läufe still, zwölf und siebenundzwanzig Minuten, und blockierten dabei
    alle anderen Sitzungen; wer wartet, soll das erfahren, statt es selbst zu
    messen.
    """
    pid = int(entry.get("pid") or 0)
    age = time.time() - float(entry.get("seit") or 0.0)
    if pid <= 0 or age < IDLE_REPORT_SECONDS:
        return ""
    # **Der Wächter urteilt nicht mehr, er berichtet — und der Grund ist ein
    # Zielkonflikt, den er nicht auflösen kann.**
    #
    # Um den Lauf des Halters zu finden, gibt es zwei Wege, und beide sind
    # unvollständig. Über die **Abstammung**: Windows setzt die Elternnummer
    # nicht um, wenn ein Zwischenprozess endet — der ``pytest`` fällt dann aus
    # dem Baum, und übrig bleiben ``gate_lock`` und ``bash``, deren Ruhe völlig
    # normal ist. Über das **Kommando**: Das findet jeden ``pytest`` auf der
    # Maschine, auch die der drei anderen Sitzungen.
    #
    # Am 23.08.2026 hat beides zusammen genau das Falsche ergeben: Der Halter
    # hing (zwanzig Sekunden ohne CPU und ohne ein Byte Protokoll, von
    # 3d-druck-3a gemessen), und ein **fremder** Lauf rechnete daneben
    # (44,9 → 62,5 CPU-Sekunden). Der Wächter sah den fremden und schwieg —
    # beim Fehlalarm meldete er, beim echten Hänger nicht.
    #
    # Deshalb sagt er jetzt, was er sieht, statt zu entscheiden: Der Baum des
    # Halters ruht, und wie viele Testprozesse sich ihm nicht zuordnen lassen.
    # Die verlässliche Antwort gibt nur eine Handmessung, und die steht in
    # ``.claude/rules/tests.md``.
    try:
        ruht = standing_still(pid)
        if ruht is not True:
            return ""
        began = float(entry.get("seit") or 0.0)
        test_processes = _test_processes()
        descendants = _descendants(pid)
        fremde = [
            candidate
            for candidate in test_processes
            if candidate not in descendants
            and ((started := _started_at(candidate)) is None or started >= began - 5.0)
        ]
    except ProcessQueryError as exc:
        return (
            f"Achtung: {exc} Ob der Lauf des Halters steht, lässt sich ohne diese "
            "Prozessauskunft nicht beurteilen. Sieh in sein Protokoll und prüfe den "
            "Status später erneut."
        )
    if fremde:
        return (
            f"Achtung: Der Prozessbaum des Halters hat in {IDLE_SAMPLE_SECONDS:.0f} Sekunden "
            "keine Rechenzeit verbraucht. Ob sein Lauf steht, lässt sich von hier aus nicht "
            f"sagen: Es laufen {len(fremde)} weitere Testprozesse, die sich ihm nicht sicher "
            "zuordnen lassen (auf Windows reißt die Elternkette, wenn ein Zwischenprozess "
            "endet). Von Hand messen — das Verfahren steht in .claude/rules/tests.md unter "
            "Steht er oder rechnet er?"
        )
    return (
        f"Achtung: Der Halter rechnet gerade nicht — in {IDLE_SAMPLE_SECONDS:.0f} Sekunden "
        "hat sein ganzer Prozessbaum keine Rechenzeit verbraucht. Das kann ein Wartezustand "
        "sein (eine Eingabe, ein Dialog) oder ein Stillstand. Sieh in sein Protokoll, bevor "
        "du weiter wartest. "
        "    Und eine Lücke ist normal: Ein Tor, das je Fensterdatei einen eigenen "
        "Prozess startet, steht zwischen Abbau und Aufbau regelmäßig ein bis zwei "
        "Sekunden ohne Rechenzeit da. Erst wenn diese Meldung mehrfach hintereinander "
        "kommt, ist sie ein Befund."
    )


def _head_commit() -> str:
    """Der Commit, gegen den gerade gemessen wird — leer, wenn es keinen gibt.

    **Vorgeschlagen von 3d-druck-b8 am 23.08.2026, nach zwei verlorenen
    Stunden.** Sie hatte einen richtigen Befund zurückgezogen, weil sie nach
    einer fremden Reparatur nachmaß und den neuen Stand für den alten hielt;
    belegen ließ es sich erst mit ``git show <commit>~1`` gegen
    ``git show <commit>`` — ein Treffer gegen zwölf.

    Die Zeile im Protokoll erspart das: Wer später zwei Ergebnisse vergleicht,
    sieht sofort, ob sie denselben Stand meinen. Ohne sie ist eine Zahl aus
    einem Lauf von gestern eine Zahl ohne Datum.
    """
    try:
        finished = subprocess.run(
            [
                "git",
                "-C",
                str(Path(__file__).resolve().parent.parent),
                "rev-parse",
                "--short",
                "HEAD",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
    except OSError, subprocess.SubprocessError:
        return ""
    return finished.stdout.strip() if finished.returncode == 0 else ""


def _source_stamps() -> dict[str, float]:
    """Zeitstempel aller Quelldateien — die Grundlage für „hat sich etwas geändert".

    **Zeitstempel und nicht Inhalt**, weil es um Sekundenbruchteile geht: Ein
    Hash über tausend Dateien kostet bei jedem Lauf Zeit, und die Frage lautet
    nicht „ist es dieselbe Datei", sondern „hat jemand geschrieben". Ein
    Schreibvorgang, der den Inhalt nicht ändert, zählt hier mit — das ist die
    Seite, auf der man lieber irrt.
    """
    root = Path(__file__).resolve().parent.parent
    stamps: dict[str, float] = {}
    for folder in ("app", "tests", "tools"):
        for entry in (root / folder).rglob("*.py"):
            try:
                stamps[str(entry.relative_to(root))] = entry.stat().st_mtime
            except OSError:
                continue
    return stamps


def _moved_sources(before: dict[str, float]) -> set[str]:
    """Welche Quelldateien sich seit dem Abdruck geändert haben — samt neuer."""
    now = _source_stamps()
    return {name for name, zeit in now.items() if before.get(name) != zeit}


def _read(path: Path) -> _LockEntry | None:
    """Prüft die JSON-Grenze, bevor Status und Besitzprüfung mit Zahlen rechnen."""
    try:
        raw: object = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return None
        pid: object = raw.get("pid")
        began: object = raw.get("seit")
        who: object = raw.get("wer")
        if not isinstance(pid, (int, float, str, type(None))):
            return None
        if not isinstance(began, (int, float, str, type(None))):
            return None
        if who is not None and not isinstance(who, str):
            return None
        # Derselbe Zahlenvertrag wie beim Lesen des Alters und der Prozess-ID.
        # Ursprungswerte erhalten: Der Besitzvergleich nutzt auch ihre Identität.
        int(pid or 0)
        if not math.isfinite(float(began or 0.0)):
            return None
        return {"wer": who or "", "pid": pid, "seit": began}
    except OSError, ValueError, TypeError, OverflowError:
        return None


def _stale(entry: _LockEntry) -> str:
    """Warum das vorhandene Schloss nicht mehr gilt — oder eine leere Zeichenkette."""
    pid = int(entry.get("pid") or 0)
    if pid > 0 and not _alive(pid):
        return f"der Prozess {pid} lebt nicht mehr"
    age = time.time() - float(entry.get("seit") or 0.0)
    if age > MAX_AGE_SECONDS:
        return f"es ist {age / 3600:.1f} Stunden alt und damit über der Grenze"
    return ""


def _describe(entry: _LockEntry) -> str:
    age = time.time() - float(entry.get("seit") or 0.0)
    return (
        f"{entry.get('wer') or 'unbenannt'} (Prozess {entry.get('pid')}), seit {age / 60:.0f} min"
    )


def _runnable(command: list[str]) -> list[str]:
    """Den Befehl so schreiben, dass dieses System ihn startet.

    Unter Windows nimmt ``CreateProcess`` in einem **relativen** Pfad keine
    Schrägstriche: ``.venv/Scripts/python.exe`` endet mit „Datei nicht
    gefunden", derselbe Pfad mit Backslashes läuft. In bash schreibt aber jeder
    Schrägstriche, und `CLAUDE.md` nennt die Backslash-Fassung — beide Formen
    kommen hier also an. Sie umzuschreiben ist billiger, als es dem Aufrufer zu
    erklären.

    Umgeschrieben wird nur das erste Wort und nur, wenn dort wirklich eine
    Datei liegt. Ein Argument wie ``-m`` oder ein Programm aus dem Suchpfad
    bleibt unangetastet.
    """
    if not command:
        return command
    first = Path(command[0])
    if first.exists():
        return [str(first.resolve()), *command[1:]]
    return command


#: So lange darf eine unlesbare Sperrdatei jung sein, bevor sie als Rest gilt —
#: das Fenster zwischen ``open("x")`` und dem geschriebenen Eintrag ist Millisekunden.
UNREADABLE_GRACE_SECONDS = 5.0


def _acquire(path: Path, who: str, wait: float) -> _LockEntry | None:
    """Legt das Schloss an. Gibt den fremden Eintrag zurück, wenn es nicht geht."""
    deadline = time.monotonic() + wait
    while True:
        try:
            # Dieselbe betriebssystemgestützte Sperre wie beim Archiv schützt
            # ausschließlich die kurze Änderung dieser temporären Tordatei.
            # Ein Prozessende gibt sie automatisch frei; kein weiterer PID-
            # Wächter muss über die Gültigkeit der Änderung entscheiden.
            with archive_lock(path, timeout=0.0):
                foreign = _try_acquire(path, who)
        except ArchiveBusyError:
            foreign = _unwritten()
        except OSError as problem:
            print(f"Torschloss nicht zugänglich: {problem}. Ablageort prüfen und erneut versuchen.")
            return _unwritten()
        if foreign is None:
            return None
        remaining = deadline - time.monotonic()
        if remaining <= 0.0:
            return foreign
        time.sleep(min(POLL_SECONDS, remaining))


def _unwritten() -> _LockEntry:
    """Ein noch nicht lesbarer Eintrag belegt das Tor, statt es freizugeben."""
    return {"wer": "Sperrdatei wird gerade geschrieben", "pid": 0, "seit": time.time()}


def _signature(path: Path) -> tuple[int, int, int, int, int] | None:
    """Identität und Schreibstand der Datei; Lesen und Prüfen müssen zusammenpassen."""
    try:
        stamp = path.stat()
    except FileNotFoundError:
        return None
    return stamp.st_dev, stamp.st_ino, stamp.st_size, stamp.st_mtime_ns, stamp.st_ctime_ns


def _try_acquire(path: Path, who: str) -> _LockEntry | None:
    """Ein Versuch unter der gemeinsamen Schreibsperre; gewartet wird außerhalb."""
    before = _signature(path)
    present = _read(path) if before is not None else None
    if before is not None and present is None:
        # Auch ein alter unlesbarer Eintrag kann zwischen Lesen und Prüfen
        # fertig werden. Dann gehört die Datei dem inzwischen lesbaren Halter.
        if _signature(path) != before:
            return _read(path) or _unwritten()
        age = time.time() - before[3] / 1e9
        if age < UNREADABLE_GRACE_SECONDS:
            return _unwritten()
        again = _read(path)
        if again is not None:
            return again
        if _signature(path) != before:
            return _unwritten()
        path.unlink(missing_ok=True)
        print("Unlesbares altes Schloss entfernt — es trug keinen Halter.", flush=True)
    elif present is not None:
        if not _discard_unlocked(path, present):
            return _read(path) or _unwritten()

    entry = {"wer": who, "pid": os.getpid(), "seit": time.time()}
    try:
        with path.open("x", encoding="utf-8") as file:
            file.write(json.dumps(entry, ensure_ascii=False))
    except FileExistsError:
        return _read(path) or _unwritten()
    return None


def run(who: str, wait: float, command: list[str]) -> int:
    """Fährt den Befehl unter dem Schloss und gibt dessen Rückgabewert zurück."""
    if not command:
        print("Kein Befehl angegeben — nach `--` gehört der Lauf, den das Schloss schützt.")
        return 2

    path = _lock_file()
    foreign = _acquire(path, who, wait)
    if foreign is not None:
        print(f"Das Tor läuft schon: {_describe(foreign)}")
        if wait <= 0:
            print("Warte, bis es durch ist, oder starte mit --wait SEKUNDEN.")
        else:
            # **Der Vorschlag muss zur Lage passen (Regel 17).** Hier stand
            # bisher derselbe Satz wie oben — auch nach einer abgelaufenen
            # Wartezeit, und damit „starte mit --wait" an jemanden, der genau
            # das getan hatte. Am 22.08.2026 hat das eine Sitzung zu dem
            # Schluss gebracht, ``--wait`` greife nicht; sie hat 3000 Sekunden
            # gewartet und die Meldung als Beweis gelesen.
            print(
                f"Nach {wait:.0f} Sekunden Wartezeit ist es immer noch belegt. "
                "Bevor du länger wartest: Sieh nach, ob der Halter überhaupt "
                "noch rechnet — ein Prozess, der steht, hält das Schloss "
                "genauso wie einer, der arbeitet."
            )
        note = _idle_note(foreign)
        if note:
            print(note)
        return BUSY_EXIT

    # **Was sich unter dem Lauf moved hat.** Das Schloss serialisiert
    # Rechenzeit — es hindert niemanden daran, in denselben Baum zu schreiben,
    # während hier gemessen wird. Am 23.08.2026 hat das viermal Stunden
    # gekostet, und jedes Mal sah das Ergebnis stimmig aus:
    #
    #   * Ein Lauf maß zehn Minuten gegen einen Import, den eine andere Sitzung
    #     im selben Moment reparierte — zweimal rot, reproduzierbar, Ursache im
    #     Code gelesen und trotzdem falsch.
    #   * Ein Torlauf sah eine Datei halb umgebaut und meldete Merkmalszahlen,
    #     die es so nie gab.
    #   * Zwei Läufe endeten mit Übersetzungsfehlern für Texte, die zwei Minuten
    #     später übersetzt waren.
    #
    # **In einem Baum, in dem vier Sitzungen schreiben, misst man nicht den
    # Baum, sondern einen Zeitpunkt** — und der stand bisher nirgends. Diese
    # Zeilen schreiben ihn hin.
    #
    # Verhindert wird nichts: Der Lauf läuft, das Ergebnis steht. Nur weiß der
    # Leser danach, wie viel es trägt.
    before = _source_stamps()
    commit_before = _head_commit()

    mine: _LockEntry = _read(path) or {}
    held = mine.get("pid") == os.getpid()
    try:
        try:
            return subprocess.run(_runnable(command)).returncode
        except OSError as problem:
            print(f"Der Lauf ließ sich nicht starten: {problem}")
            print(f"Gemeint war: {' '.join(command)}")
            print("Steht das Programm dort, und ist der Pfad für dieses System geschrieben?")
            return 127
    finally:
        # Nur das eigene Schloss aufräumen: Hat ein anderer es inzwischen
        # übernommen — weil dieser Lauf über die Altersgrenze kam —, gehört es
        # ihm, und ihm wegzunehmen wäre schlimmer als der Stau.
        if held:
            try:
                with archive_lock(path, timeout=0.0):
                    current = _read(path)
                    if current is not None and (current.get("pid"), current.get("seit")) == (
                        mine.get("pid"),
                        mine.get("seit"),
                    ):
                        path.unlink(missing_ok=True)
            except ArchiveBusyError:
                # Ein späterer Blick erkennt den inzwischen beendeten Halter.
                pass
        commit_after = _head_commit()
        moved = _moved_sources(before)
        if commit_before:
            shifted = (
                f" (bei Beginn {commit_before})"
                if commit_after and commit_after != commit_before
                else ""
            )
            print(f"Gemessen gegen {commit_after or commit_before}{shifted}.", file=sys.stderr)
        if moved:
            names = ", ".join(sorted(moved)[:4])
            more = f" und {len(moved) - 4} more" if len(moved) > 4 else ""
            print(file=sys.stderr)
            print(
                f"Achtung: Während dieses Laufs haben sich {len(moved)} Quelldatei(en) "
                f"geändert — {names}{more}.",
                file=sys.stderr,
            )
            print(
                "Das Ergebnis oben gilt einem Zeitpunkt und nicht diesem Baum. Bevor du "
                "einem roten Test glaubst, sieh nach, ob er zu einer dieser Dateien gehört.",
                file=sys.stderr,
            )


def _discard(path: Path, present: _LockEntry) -> bool:
    """Prüfen und Entfernen benutzen dieselbe Schreibsperre wie das Anlegen."""
    try:
        with archive_lock(path, timeout=0.0):
            return _discard_unlocked(path, present)
    except ArchiveBusyError:
        return False


def _discard_unlocked(path: Path, present: _LockEntry) -> bool:
    """Ein verwaistes Schloss wegräumen — aber nur genau dieses.

    **Zwischen Lesen und Löschen kann ein neuer Halter angelegt haben.** Dann
    zeigt die Datei auf einen lebenden Lauf, und ihn zu löschen wäre schlimmer
    als das verwaiste Schloss: Zwei Torläufe messen gleichzeitig, und beide
    Ergebnisse sind wertlos. Verglichen wird deshalb vor dem Löschen noch
    einmal, und zwar an Prozess **und** Zeitpunkt — eine Kennung allein wird
    auf jedem System irgendwann wiederverwendet.
    """
    again = _read(path) if path.exists() else None
    if again is None:
        return False
    if (again.get("pid"), again.get("seit")) != (present.get("pid"), present.get("seit")):
        return False
    if _stale(again) == "":
        return False
    path.unlink(missing_ok=True)
    return True


def release() -> int:
    """Ein verwaistes Schloss von Hand wegräumen. Ein lebendes bleibt liegen.

    Gebraucht, weil ein Schloss sonst nur zufällig verschwindet: ``_acquire``
    räumt es ab, wer aber bloß nachsieht, ließ es liegen. Am 03.09.2026 lag
    eines nach einem abgebrochenen Aufnahmelauf **196 Minuten** da, und
    solange hat jede andere Sitzung entweder gewartet oder ungeschützt
    gemessen.

    Ein lebendes Schloss rührt dieser Weg nicht an. Wer einen laufenden Lauf
    beenden will, beendet den Prozess — dann ist das Schloss verwaist und
    fällt beim nächsten Blick von selbst.
    """
    path = _lock_file()
    present = _read(path) if path.exists() else None
    if present is None:
        if path.exists():
            print("Das Torschloss ist noch nicht lesbar — erneut prüfen, nichts weggeräumt.")
            return 1
        print("Das Tor ist frei — nichts wegzuräumen.")
        return 0
    reason = _stale(present)
    if not reason:
        print(f"Das Tor läuft: {_describe(present)}")
        print("Ein lebendes Schloss wird nicht weggeräumt — beende erst den Prozess.")
        return 1
    if _discard(path, present):
        print(f"Verwaistes Schloss weggeräumt ({reason}): {_describe(present)}")
        return 0
    print("Inzwischen hat jemand anderes das Tor genommen — nichts weggeräumt.")
    return 1


def status() -> int:
    """0 heißt frei, 1 heißt belegt — damit ein Skript danach entscheiden kann."""
    path = _lock_file()
    present = _read(path) if path.exists() else None
    if present is None:
        if path.exists():
            print("Das Torschloss ist noch nicht lesbar — erneut prüfen.")
            return 1
        print("Das Tor ist frei.")
        return 0
    reason = _stale(present)
    if reason:
        # **Erkennen und liegenlassen war die halbe Handlung.** Wer den Beweis
        # in der Hand hält, dass das Schloss nichts mehr schützt, räumt es auch
        # weg; sonst liest es die nächste Sitzung noch einmal und die
        # übernächste auch.
        if _discard(path, present):
            print(
                f"Ein verwaistes Schloss lag da und ist weggeräumt ({reason}): {_describe(present)}"
            )
        else:
            print(f"Ein verwaistes Schloss liegt da ({reason}): {_describe(present)}")
        return 0
    print(f"Das Tor läuft: {_describe(present)}")
    note = _idle_note(present)
    if note:
        print(note)
    return 1


def main() -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    sub = parser.add_subparsers(dest="task", required=True)

    runner = sub.add_parser("run", help="einen Befehl unter dem Schloss fahren")
    runner.add_argument("--who", default=os.environ.get("CLAUDE_SESSION_NAME", "unbenannt"))
    runner.add_argument(
        "--wait",
        type=float,
        default=0.0,
        help="so viele Sekunden auf ein belegtes Tor warten, statt sofort aufzugeben",
    )
    runner.add_argument("command", nargs=argparse.REMAINDER)

    sub.add_parser("status", help="sagen, ob und von wem das Tor gerade läuft")
    sub.add_parser("frei", help="ein verwaistes Schloss wegräumen; ein lebendes bleibt")

    args = parser.parse_args()
    if args.task == "run":
        command = list(args.command)
        if command and command[0] == "--":
            command = command[1:]
        return run(args.who, args.wait, command)
    if args.task == "frei":
        return release()
    return status()


if __name__ == "__main__":
    raise SystemExit(main())
