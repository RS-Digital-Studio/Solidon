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


def _common_dir() -> Path:
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
    return _common_dir() / "solidon-tor.lock"


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
            kernel.CloseHandle(handle)
            return True
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


def _acquire(path: Path, who: str, wait: float) -> dict[str, object] | None:
    """Legt das Schloss an. Gibt den fremden Eintrag zurück, wenn es nicht geht."""
    deadline = time.monotonic() + wait
    while True:
        present = _read(path) if path.exists() else None
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
        return BUSY_EXIT

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


def status() -> int:
    """0 heißt frei, 1 heißt belegt — damit ein Skript danach entscheiden kann."""
    path = _lock_file()
    present = _read(path) if path.exists() else None
    if present is None:
        print("Das Tor ist frei.")
        return 0
    reason = _stale(present)
    if reason:
        print(f"Ein verwaistes Schloss liegt da ({reason}): {_describe(present)}")
        return 0
    print(f"Das Tor läuft: {_describe(present)}")
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

    args = parser.parse_args()
    if args.task == "run":
        command = list(args.command)
        if command and command[0] == "--":
            command = command[1:]
        return run(args.who, args.wait, command)
    return status()


if __name__ == "__main__":
    raise SystemExit(main())
