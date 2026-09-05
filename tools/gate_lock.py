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
import json
import os
import subprocess
import sys
import time
from pathlib import Path

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
        kernel = ctypes.windll.kernel32  # type: ignore[attr-defined]
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
        import ctypes
        import ctypes.wintypes as wt

        class _Entry(ctypes.Structure):
            _fields_ = [
                ("dwSize", wt.DWORD),
                ("cntUsage", wt.DWORD),
                ("th32ProcessID", wt.DWORD),
                ("th32DefaultHeapID", ctypes.POINTER(ctypes.c_ulong)),
                ("th32ModuleID", wt.DWORD),
                ("cntThreads", wt.DWORD),
                ("th32ParentProcessID", wt.DWORD),
                ("pcPriClassBase", ctypes.c_long),
                ("dwFlags", wt.DWORD),
                ("szExeFile", ctypes.c_char * 260),
            ]

        kernel = ctypes.windll.kernel32  # type: ignore[attr-defined]
        snapshot = kernel.CreateToolhelp32Snapshot(0x2, 0)  # TH32CS_SNAPPROCESS
        if snapshot in (0, -1):
            return {root}
        try:
            entry = _Entry()
            entry.dwSize = ctypes.sizeof(_Entry)
            weiter = kernel.Process32First(snapshot, ctypes.byref(entry))
            while weiter:
                parents[int(entry.th32ProcessID)] = int(entry.th32ParentProcessID)
                weiter = kernel.Process32Next(snapshot, ctypes.byref(entry))
        finally:
            kernel.CloseHandle(snapshot)
    else:
        for entry in Path("/proc").glob("[0-9]*"):
            try:
                fields = (entry / "stat").read_text(encoding="utf-8").rsplit(") ", 1)[-1].split()
                parents[int(entry.name)] = int(fields[1])
            except (OSError, ValueError, IndexError):
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

    Findet die Abfrage nichts oder scheitert sie, ist das keine Aussage — der
    Aufrufer behandelt eine leere Menge wie eine fehlende Auskunft.
    """
    found: set[int] = set()
    if sys.platform == "win32":
        # Über CIM, weil ``Toolhelp32`` nur den Dateinamen liefert und nicht
        # die Kommandozeile. Der Aufruf kostet eine halbe Sekunde und läuft
        # nur bei ``status`` und an einem belegten Tor, nie in der Warteschleife.
        query = (
            "Get-CimInstance Win32_Process -Filter \"Name like '%python%'\" | "
            "Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
        )
        try:
            raw = subprocess.run(
                ["powershell", "-NoProfile", "-Command", query],
                capture_output=True,
                text=True,
                # **Mit Kodierung, sonst stirbt der Lesefaden.** ``text=True``
                # nimmt auf Windows cp1252, und in einer fremden Kommandozeile
                # steht irgendwann ein Umlaut oder ein Pfad, den cp1252 nicht
                # kennt: ``UnicodeDecodeError`` in einem Thread, den niemand
                # sieht, und die Auskunft kommt halb zurück. Gemessen am
                # 23.08.2026 an einer Zeile mit 0x81.
                encoding="utf-8",
                errors="replace",
                timeout=20,
                check=False,
            )
            data = json.loads(raw.stdout or "[]")
        except (OSError, ValueError, subprocess.SubprocessError):
            return found
        if isinstance(data, dict):
            data = [data]
        for entry in data:
            # **``-m pytest`` und nicht ``pytest``, und ohne dieses Werkzeug
            # selbst.** Die Kommandozeile eines ``gate_lock``-Aufrufs enthält
            # den ganzen geschützten Befehl — also auch das Wort ``pytest``,
            # obwohl der Prozess nur wartet. Am 23.08.2026 hat dieselbe Falle
            # zwölf wartende Hüllen als „hängende Testläufe" erscheinen lassen:
            # keine Rechenzeit, Protokoll steht, die perfekte Hänger-Signatur —
            # und vollständig falsch. Gefunden von 3d-druck-64 an ihrer eigenen
            # Messung.
            line = str(entry.get("CommandLine") or "")
            if "-m pytest" in line and "gate_lock" not in line:
                found.add(int(entry.get("ProcessId") or 0))
        return {pid for pid in found if pid > 0}
    for entry in Path("/proc").glob("[0-9]*"):
        try:
            line = (entry / "cmdline").read_bytes().replace(b"\0", b" ").decode(errors="replace")
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

        kernel = ctypes.windll.kernel32  # type: ignore[attr-defined]
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
    try:
        fields = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").rsplit(") ", 1)[-1].split()
        ticks = float(fields[11]) + float(fields[12])
        return ticks / os.sysconf("SC_CLK_TCK")
    except (OSError, ValueError, IndexError):
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

        kernel = ctypes.windll.kernel32  # type: ignore[attr-defined]
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
    try:
        # Feld 22 ist die Startzeit in Ticks seit dem Systemstart.
        fields = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8").rsplit(") ", 1)[-1].split()
        ticks = float(fields[19]) / os.sysconf("SC_CLK_TCK")
        uptime = float(Path("/proc/uptime").read_text(encoding="utf-8").split()[0])
        return time.time() - (uptime - ticks)
    except (OSError, ValueError, IndexError):
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


def _idle_note(entry: dict[str, object]) -> str:
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
    ruht = standing_still(pid)
    if ruht is not True:
        return ""
    began = float(entry.get("seit") or 0.0)
    fremde = [
        candidate
        for candidate in _test_processes()
        if candidate not in _descendants(pid)
        and ((started := _started_at(candidate)) is None or started >= began - 5.0)
    ]
    if fremde:
        return (
            f"Achtung: Der Prozessbaum des Halters hat in {IDLE_SAMPLE_SECONDS:.0f} Sekunden "
            "keine Rechenzeit verbraucht. Ob sein Lauf steht, lässt sich von hier aus nicht "
            f"sagen: Es laufen {len(fremde)} more Testprozesse, die sich ihm nicht sicher "
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
    except (OSError, subprocess.SubprocessError):
        return ""
    return finished.stdout.strip() if finished.returncode == 0 else ""


def _source_stamps() -> dict[str, float]:
    """Zeitstempel aller Quelldateien — die Grundlage für „hat sich etwas moved".

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


def _read(path: Path) -> dict[str, object] | None:
    try:
        return dict(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError):
        return None


def _stale(entry: dict[str, object]) -> str:
    """Warum das vorhandene Schloss nicht mehr gilt — oder eine leere Zeichenkette."""
    pid = int(entry.get("pid") or 0)
    if pid > 0 and not _alive(pid):
        return f"der Prozess {pid} lebt nicht mehr"
    age = time.time() - float(entry.get("seit") or 0.0)
    if age > MAX_AGE_SECONDS:
        return f"es ist {age / 3600:.1f} Stunden alt und damit über der Grenze"
    return ""


def _describe(entry: dict[str, object]) -> str:
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


def _acquire(path: Path, who: str, wait: float) -> dict[str, object] | None:
    """Legt das Schloss an. Gibt den fremden Eintrag zurück, wenn es nicht geht."""
    deadline = time.monotonic() + wait
    while True:
        present = _read(path) if path.exists() else None
        if present is None and path.exists():
            # Eine leere oder halb geschriebene Datei: Jung ist sie das
            # Fenster zwischen Anlegen und Schreiben eines anderen — kurz
            # warten. Alt ist sie ein Rest, der keinen Halter mehr hat; das
            # ``x`` darunter scheiterte an ihr in jeder Runde, und das Tor
            # stand für jeden weiteren Lauf endlos (Gesamtreview 05.09.2026,
            # R17).
            try:
                age = time.time() - path.stat().st_mtime
            except OSError:
                age = UNREADABLE_GRACE_SECONDS
            if age < UNREADABLE_GRACE_SECONDS and time.monotonic() < deadline:
                time.sleep(POLL_SECONDS)
                continue
            print("Unlesbares Schloss entfernt — es trug keinen Halter.", flush=True)
            path.unlink(missing_ok=True)
        if present is not None:
            reason = _stale(present)
            if not reason:
                if time.monotonic() < deadline:
                    time.sleep(POLL_SECONDS)
                    continue
                return present
            print(f"Verwaistes Schloss übernommen — {reason}.", flush=True)
            path.unlink(missing_ok=True)

        entry = {"wer": who, "pid": os.getpid(), "seit": time.time()}
        try:
            # ``x`` und nicht ``w``: Zwei Sitzungen, die im selben Augenblick
            # zugreifen, dürfen nicht beide gewinnen. Das Anlegen ist die
            # Entscheidung, nicht das Schreiben danach.
            with path.open("x", encoding="utf-8") as file:
                file.write(json.dumps(entry, ensure_ascii=False))
        except FileExistsError:
            continue
        except OSError as problem:
            # Ein Schloss darf nie das Tor verhindern. Kein Eintrag heißt: der
            # Lauf geht, nur ungeschützt — und das steht dann auch da.
            print(f"Ohne Schloss (es ließ sich nicht anlegen: {problem}).", flush=True)
            return None
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

    mine = _read(path) or {}
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
            current = _read(path)
            if current is not None and current.get("pid") == os.getpid():
                path.unlink(missing_ok=True)
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


def _discard(path: Path, present: dict[str, object]) -> bool:
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
