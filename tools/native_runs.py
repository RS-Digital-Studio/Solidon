"""Native Läufe am echten Fenster — gebunden, gesiegelt und begrenzt (FD-164).

    .venv\\Scripts\\python.exe tools/native_runs.py bind --out <bindung.json>
    .venv\\Scripts\\python.exe tools/native_runs.py case --binding <bindung.json>
        --inventory <lauf> --case <nummer> --screen <name> --out <ordner>
        [--deadline <s>] [--affinity <hex>] (--check | --native)
    .venv\\Scripts\\python.exe tools/native_runs.py measure-card --binding <bindung.json>
        --inventory <inventar> --screen <name> --out <ordner> [--languages de,en]
        [--deadline <s>] [--affinity <hex>] (--check | --native)

``bind`` hält den sauberen Stand fest (``native_binding``). ``case`` fährt
einen Funktions- oder Sprachfall eines Laufs von ``file_acceptance.py``
(``inventory --functions``) noch einmal: Metadaten und Startszenen werden in
den neuen Ordner kopiert und gehasht, Fallordner, Flächen und Bilder nicht —
``LanguageFlow`` überspränge vorhandene Flächen. Der Fall selbst ist
``file_acceptance.py child``, aufgerufen nach der Siegelprüfung im Kind.
``measure-card`` fährt die Maßkartenfolge (``native_measure_card``) je
Sprache in einem eigenen Prozess; ihre Zeilen und Szenen kommen aus einem
Inventar mit ``--rows resize_hole,move_feature,duplicate_feature,rotate_feature``.

Was jeder Start einhält — übernommen aus den Sitzungsläufern, die die
D0-Nachweise am MSI-Schirm fuhren:

- **Siegel zuerst.** Bindung, Läufer und Quellen werden vor dem Start, im Kind
  vor dem ersten Qt-Import und nach dem Lauf geprüft; eine geänderte Datei
  verweigert den Start mit Ausgang 2 und dem nächsten Schritt.
- **Nur mit Schalter.** Ohne ``--native`` startet kein Fenster; ``--check``
  prüft alles bis zum Start und legt nichts an.
- **Eigenes Profil.** Alle acht Nutzerordner (``native_binding.PROFILE_VARIABLES``)
  zeigen in den neuen Ordner, schon beim Aufseher. Das echte Profil wird nur
  per ``stat`` verglichen (Größe, Änderungszeit), nie gelesen.
- **Eigener Prozessbaum, begrenzt.** Je Kind eine eigene Prozessgruppe, eine
  Frist (``--deadline``, dazu die Wartezeit des Vorhersagetors), eine lesende
  Aufnahme aller Nachkommen mit PID und Startzeit; nach der Frist
  ``terminate_process_tree``, danach wird jeder verbliebene eigene Nachkomme
  beendet und gemeldet — ein Lauf mit Rest ist rot. Ein Sprachfall, der vor
  einer Fläche einen frischen Prozess braucht (Ausgang 75, FD-132), beginnt neu
  wie unter ``file_acceptance.py run``.
- **Belege außerhalb des Repositorys** in einem neuen Ordner; nichts wird
  überschrieben oder wieder aufgenommen.

Ausgang 0 heißt: Prozess, Abbau, Siegel und Messbedingungen vollständig —
keine Bildabnahme. Nur unter Windows; die Plattform ``windows`` und die
Kernmaske sind dort zu Hause. Kein Testlauf und nicht im Tor: Die Logik
prüfen ``tests/test_native_runs.py`` und ``tests/test_native_measure_card_cursor.py``.
"""

from __future__ import annotations

import argparse
import ctypes
import json
import os
import shutil
import subprocess
import sys
import time
import traceback
from collections.abc import Callable, Iterable, Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final, NamedTuple

ROOT: Final = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools import native_binding  # noqa: E402
from tools.native_binding import SealError  # noqa: E402

#: Äußere Frist eines Einzelfalls (Sekunden), wirksam ist das Minimum mit
#: ``file_acceptance.case_timeout``. Das 2,2-Fache des längsten regulären
#: Sprachfalls im 48er-Lauf (D8 Portugiesisch, 188 s); Funktionsfälle brauchten
#: höchstens 64 s.
CASE_DEADLINE_S: Final = 420.0

#: Frist je Sprache der Maßkartenfolge (Sekunden); der Kindprozess bricht
#: :data:`INNER_MARGIN_S` vorher selbst mit Stapel ab (``faulthandler``).
CARD_DEADLINE_S: Final = 300.0
INNER_MARGIN_S: Final = 15.0

#: Wie oft der Aufseher den Prozessbaum liest (Sekunden).
POLL_S: Final = 1.0

#: Wie lange auf das Ende eines beendeten Baums gewartet wird (Sekunden).
STOP_WAIT_S: Final = 30.0

#: Was aus einem Inventar in den neuen Ordner reist: Pflicht und, wenn da, dazu.
REQUIRED_INPUTS: Final = ("cases.json", "rows.json")
OPTIONAL_INPUTS: Final = ("menubar.json", "reference.json")

#: Die Fallarten, die ``case`` fährt; Datei- und Startfälle fährt ``file_acceptance.py run``.
CASE_KINDS: Final = ("function", "language")

#: Die Zeilen der Maßkartenfolge, in dieser Reihenfolge; die erste geht den Bohrungsweg.
CARD_ROWS: Final = ("resize_hole", "move_feature", "duplicate_feature", "rotate_feature")

#: Die Dateien des echten Profils, die nur per ``stat`` verglichen werden — je
#: Ordner des Nutzers. Die Namen sind die der Anwendung (``settings.SETTINGS_FILE``,
#: ``activation.store.TRIAL_FILE`` und ``STATE_FILE``; ein Test hält sie gleich).
WATCHED_FILES: Final = ("settings.json", "trial.json", "activation.state")

#: Was ein natives Kind nicht erben darf: Bewegung aus und PySide-Laden setzt ``app.ui``.
DROPPED_VARIABLES: Final = ("SOLIDON3D_MOTION", "PYSIDE6_OPTION_LAZY")

#: Ein BLAS-Faden je Prozess, wie Suite und Tor (``tests.md``).
THREAD_VARIABLES: Final = (
    "OPENBLAS_NUM_THREADS",
    "OMP_NUM_THREADS",
    "MKL_NUM_THREADS",
    "NUMEXPR_NUM_THREADS",
)


class StartRefusedError(RuntimeError):
    """Ein Start, der nicht stattfindet — mit dem Satz, was jetzt hilft (Regel 17)."""

    def __init__(self, problem: str, suggestion: str) -> None:
        super().__init__(f"{problem}\nHandlungsvorschlag: {suggestion}")


class CaseRunError(RuntimeError):
    """Ein gelaufener Fall, dessen Prozess, Abbau oder Protokoll nicht trägt."""


def now() -> str:
    return datetime.now(UTC).isoformat()


write_json = native_binding.write_json


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8-sig"))


# --- Prozessbaum ---------------------------------------------------------------


class ProcessRow(NamedTuple):
    """Ein Prozess der Tabelle: PID, Elternteil, Programm, Startzeit (FILETIME oder None)."""

    pid: int
    parent: int
    name: str
    created: int | None = None


def own_tree(
    rows: Sequence[ProcessRow],
    known: Mapping[int, ProcessRow],
    created_of: Callable[[int], int | None],
) -> dict[int, ProcessRow]:
    """Die bekannten eigenen Prozesse samt allen Nachkommen, die ``rows`` nennt.

    Ein Prozess zählt, wenn sein Elternteil dazugehört und er nicht vor ihm
    entstand. Lebt das Elternteil noch, muss es dasselbe sein (gleiche
    Startzeit): Eine wiederverwendete PID adoptiert keine fremden Kinder. Ein
    verwaister Nachkomme eines schon beendeten eigenen Prozesses zählt weiter.
    """
    tree = dict(known)
    living = {row.pid for row in rows}
    changed = True
    while changed:
        changed = False
        for row in rows:
            parent = tree.get(row.parent)
            if row.pid in tree or parent is None:
                continue
            if row.parent in living and created_of(row.parent) != parent.created:
                continue
            created = created_of(row.pid)
            if created is None or (parent.created is not None and created < parent.created):
                continue
            tree[row.pid] = row._replace(created=created)
            changed = True
    return tree


def still_running(
    tree: Mapping[int, ProcessRow],
    rows: Sequence[ProcessRow],
    created_of: Callable[[int], int | None],
) -> list[ProcessRow]:
    """Die eigenen Prozesse, die noch laufen — dieselbe PID mit derselben Startzeit."""
    living = {row.pid for row in rows}
    return [
        member
        for member in tree.values()
        if member.pid in living
        and member.created is not None
        and created_of(member.pid) == member.created
    ]


def _kernel() -> Any:
    if sys.platform != "win32":
        raise StartRefusedError(
            "Die Prozessaufnahme dieses Läufers gibt es nur unter Windows.",
            "Fahren Sie native Läufe auf dem Windows-Rechner mit dem Aufnahmeschirm.",
        )
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = (ctypes.c_uint32, ctypes.c_int, ctypes.c_uint32)
    kernel.OpenProcess.restype = ctypes.c_void_p
    kernel.GetProcessTimes.argtypes = (ctypes.c_void_p, *(ctypes.POINTER(ctypes.c_uint64),) * 4)
    kernel.GetProcessTimes.restype = ctypes.c_int
    kernel.TerminateProcess.argtypes = (ctypes.c_void_p, ctypes.c_uint32)
    kernel.TerminateProcess.restype = ctypes.c_int
    kernel.CloseHandle.argtypes = (ctypes.c_void_p,)
    kernel.CloseHandle.restype = ctypes.c_int
    kernel.CreateToolhelp32Snapshot.argtypes = (ctypes.c_uint32, ctypes.c_uint32)
    kernel.CreateToolhelp32Snapshot.restype = ctypes.c_void_p
    return kernel


#: ``PROCESS_QUERY_LIMITED_INFORMATION`` und ``PROCESS_TERMINATE``.
_QUERY: Final = 0x1000
_TERMINATE: Final = 0x0001


def _created(kernel: Any, handle: Any) -> int | None:
    times = [ctypes.c_uint64() for _ in range(4)]
    if not kernel.GetProcessTimes(handle, *(ctypes.byref(value) for value in times)):
        return None
    return int(times[0].value)


def creation_time(pid: int) -> int | None:
    """Wann der Prozess ``pid`` startete (FILETIME); ``None``, wenn er nicht zu öffnen ist."""
    kernel = _kernel()
    handle = kernel.OpenProcess(_QUERY, 0, pid)
    if not handle:
        return None
    try:
        return _created(kernel, handle)
    finally:
        kernel.CloseHandle(handle)


def process_table() -> list[ProcessRow]:
    """Alle Prozesse des Rechners mit PID, Elternteil und Programm — gelesen, nichts berührt."""

    class Entry(ctypes.Structure):
        _fields_ = [
            ("size", ctypes.c_uint32),
            ("usage", ctypes.c_uint32),
            ("pid", ctypes.c_uint32),
            ("heap", ctypes.c_size_t),
            ("module", ctypes.c_uint32),
            ("threads", ctypes.c_uint32),
            ("parent", ctypes.c_uint32),
            ("priority", ctypes.c_long),
            ("flags", ctypes.c_uint32),
            ("exe", ctypes.c_wchar * 260),
        ]

    kernel = _kernel()
    kernel.Process32FirstW.argtypes = (ctypes.c_void_p, ctypes.POINTER(Entry))
    kernel.Process32FirstW.restype = ctypes.c_int
    kernel.Process32NextW.argtypes = (ctypes.c_void_p, ctypes.POINTER(Entry))
    kernel.Process32NextW.restype = ctypes.c_int
    snapshot = kernel.CreateToolhelp32Snapshot(0x00000002, 0)
    if snapshot in (None, ctypes.c_void_p(-1).value):
        raise OSError(ctypes.get_last_error(), "Die Prozesstabelle ließ sich nicht lesen")
    rows: list[ProcessRow] = []
    try:
        entry = Entry(size=ctypes.sizeof(Entry))
        found = kernel.Process32FirstW(snapshot, ctypes.byref(entry))
        while found:
            rows.append(ProcessRow(int(entry.pid), int(entry.parent), str(entry.exe)))
            found = kernel.Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        kernel.CloseHandle(snapshot)
    return rows


def stop_process(member: ProcessRow) -> bool:
    """Beendet genau diesen eigenen Prozess — nur wenn PID und Startzeit noch passen."""
    kernel = _kernel()
    handle = kernel.OpenProcess(_QUERY | _TERMINATE, 0, member.pid)
    if not handle:
        return False
    try:
        if _created(kernel, handle) != member.created:
            return False
        return bool(kernel.TerminateProcess(handle, 1))
    finally:
        kernel.CloseHandle(handle)


def supervise(
    command: Sequence[str],
    *,
    cwd: Path,
    env: Mapping[str, str],
    deadline_s: float,
    folder: Path,
    poll_s: float = POLL_S,
    append: bool = False,
) -> dict[str, Any]:
    """Startet ``command`` in eigener Prozessgruppe, begrenzt es und baut seinen Baum ab.

    ``child-tree.json`` hält jeden eigenen Prozess mit PID und Startzeit, was
    nach dem Ende noch lief und beendet wurde, und was danach noch lief.
    ``clean_end`` ist wahr nur ohne Fristablauf, ohne beendeten Rest und ohne
    verbliebenen Prozess; der rohe Ausgang des Kindes bleibt daneben stehen.
    ``append`` hängt die Ausgaben an die eines vorigen Laufs (Neustart).
    """
    from app.core.process import no_error_dialogs, process_group_options, terminate_process_tree

    folder.mkdir(parents=True, exist_ok=True)
    record: dict[str, Any] = {
        "command": list(command),
        "deadline_s": deadline_s,
        "timeout": False,
        "started_utc": now(),
    }
    began = time.monotonic()
    mode = "a" if append else "w"
    with (
        (folder / "stdout.log").open(mode, encoding="utf-8") as stdout,
        (folder / "stderr.log").open(mode, encoding="utf-8") as stderr,
        no_error_dialogs(),
    ):
        child = subprocess.Popen(
            list(command),
            cwd=cwd,
            env=dict(env),
            stdout=stdout,
            stderr=stderr,
            **process_group_options(no_window=True),
        )
        record["pid"] = child.pid
        # Der Griff des Popen hält die PID: Sie kann nicht neu vergeben werden.
        tree = {
            child.pid: ProcessRow(
                child.pid, os.getpid(), Path(command[0]).name, creation_time(child.pid)
            )
        }
        try:
            while True:
                tree = own_tree(process_table(), tree, creation_time)
                write_json(folder / "own-pids.json", [row._asdict() for row in tree.values()])
                remaining = deadline_s - (time.monotonic() - began)
                if remaining <= 0:
                    raise subprocess.TimeoutExpired(list(command), deadline_s)
                try:
                    code = child.wait(timeout=min(poll_s, remaining))
                    break
                except subprocess.TimeoutExpired:
                    continue
        except subprocess.TimeoutExpired:
            record["timeout"] = True
            tree = own_tree(process_table(), tree, creation_time)
            terminate_process_tree(child)
            code = child.wait(timeout=STOP_WAIT_S)
        except BaseException:
            terminate_process_tree(child)
            child.wait(timeout=STOP_WAIT_S)
            raise
        record["exit_code"] = code
        record["wall_unrated_s"] = time.monotonic() - began
        # Nach dem Ende: Verwaiste Nachkommen hängen noch an der PID des Kindes.
        tree = own_tree(process_table(), tree, creation_time)
        left = still_running(tree, process_table(), creation_time)
        stopped = [member for member in left if stop_process(member)]
        deadline = time.monotonic() + STOP_WAIT_S
        remaining_rows = still_running(tree, process_table(), creation_time)
        while remaining_rows and time.monotonic() < deadline:
            time.sleep(0.2)
            remaining_rows = still_running(tree, process_table(), creation_time)
    record.update(
        own_process_tree=[row._asdict() for row in tree.values()],
        stopped=[row._asdict() for row in stopped],
        remaining=[row._asdict() for row in remaining_rows],
        ended_utc=now(),
    )
    record["clean_end"] = not record["timeout"] and not stopped and not remaining_rows
    write_json(folder / "child-tree.json", record)
    return record


def supervise_restarting(
    command: Sequence[str],
    *,
    restarts: int,
    restart_exit: int,
    **supervised: Any,
) -> dict[str, Any]:
    """:func:`supervise`, und ein Sprachfall, der einen frischen Prozess braucht, läuft weiter.

    Wie ``file_acceptance.run`` (FD-132): Endet das Kind sauber mit ``restart_exit``,
    beginnt es neu, höchstens ``restarts`` mal; jeder Lauf hat die volle Frist,
    und seine Ausgaben hängen an die des vorigen. Ein Fristablauf oder ein
    unsauberes Ende bricht ab. ``restarts`` im Ergebnis zählt die Neustarts.
    """
    attempts = 0
    while True:
        record = supervise(command, append=attempts > 0, **supervised)
        if (
            record["exit_code"] != restart_exit
            or record["timeout"]
            or not record["clean_end"]
            or attempts >= restarts
        ):
            return {**record, "restarts": attempts}
        attempts += 1


# --- Eingaben, Profil, Umgebung -------------------------------------------------


def affinity_of(text: str | None) -> int | None:
    """Die Kernmaske aus ``--affinity`` (hexadezimal, etwa ``FFFFF0FF``)."""
    if not text:
        return None
    try:
        mask = int(text, 16)
    except ValueError:
        mask = 0
    if mask <= 0:
        raise StartRefusedError(
            f"--affinity {text} ist keine Kernmaske.",
            "Geben Sie eine hexadezimale Maske an, etwa FFFFF0FF.",
        )
    return mask


def fresh_out(path: Path) -> Path:
    """Ein neuer Belegordner außerhalb des Repositorys; nichts wird überschrieben."""
    try:
        out = native_binding.outside(path)
    except SealError as problem:
        raise StartRefusedError(problem.problem, problem.suggestion) from problem
    if out.exists():
        raise StartRefusedError(
            f"{out} liegt schon.",
            "Wählen Sie einen neuen Ordner; ein Lauf nimmt keinen alten wieder auf.",
        )
    return out


def profile_environment(base: Mapping[str, str], profile: Path) -> dict[str, str]:
    """Die Umgebung eines nativen Kindes: eigenes Profil, gebundene Wurzel, echte Plattform."""
    env = {key: value for key, value in base.items() if key not in DROPPED_VARIABLES}
    for name in native_binding.PROFILE_VARIABLES:
        env[name] = str(profile / name.lower())
    env.update(
        PYTHONPATH=str(ROOT),
        PYTHONUTF8="1",
        PYTHONDONTWRITEBYTECODE="1",
        QT_QPA_PLATFORM="windows",
        QT_SCALE_FACTOR="1",
    )
    for name in THREAD_VARIABLES:
        env[name] = "1"
    env.update(native_binding.ISOLATED_KEYRING)
    return env


def isolate_supervisor(profile: Path) -> None:
    """Auch der Aufseher schreibt nie in ein echtes Profil: Seins liegt ab dem Start im Beleg."""
    for name in native_binding.PROFILE_VARIABLES:
        folder = profile / name.lower()
        folder.mkdir(parents=True, exist_ok=True)
        os.environ[name] = str(folder)


def real_profile(environment: Mapping[str, str]) -> list[Path]:
    """Die echten Ordner und Dateien des Nutzers, die nur per ``stat`` verglichen werden."""
    from app.core import paths

    saved = {name: os.environ.get(name) for name in ("APPDATA", "LOCALAPPDATA")}
    try:
        for name in saved:
            if environment.get(name):
                os.environ[name] = environment[name]
        folders = [paths.user_config_dir(), paths.user_data_dir()]
    finally:
        for name, value in saved.items():
            if value is None:
                os.environ.pop(name, None)
            else:
                os.environ[name] = value
    return [path for folder in folders for path in (folder, *(folder / n for n in WATCHED_FILES))]


def stat_only(paths: Iterable[Path]) -> dict[str, list[int] | None]:
    """Größe und Änderungszeit je Pfad — kein Öffnen, kein Lesen."""
    found: dict[str, list[int] | None] = {}
    for path in paths:
        try:
            status = path.stat()
        except OSError:
            found[str(path)] = None
        else:
            found[str(path)] = [status.st_size, status.st_mtime_ns]
    return found


def copy_inputs(inventory: Path, out: Path, names: Iterable[str]) -> dict[str, str]:
    """Kopiert Dateien und ``scenes/`` eines Inventars und hält jeden Hash der Kopie fest."""
    copied: dict[str, str] = {}
    for name in names:
        if (inventory / name).is_file():
            shutil.copy2(inventory / name, out / name)
            copied[name] = native_binding.sha256_of(out / name)
    shutil.copytree(inventory / "scenes", out / "scenes")
    for path in sorted((out / "scenes").rglob("*")):
        if path.is_file():
            copied[path.relative_to(out).as_posix()] = native_binding.sha256_of(path)
    return copied


def unchanged_inputs(inventory: Path, copied: Mapping[str, str]) -> bool:
    """Ob das Inventar nach dem Lauf noch dieselben Bytes trägt wie seine Kopie davor."""
    return all(
        (inventory / name).is_file() and native_binding.sha256_of(inventory / name) == digest
        for name, digest in copied.items()
    )


def child_command(subcommand: str, *arguments: str, affinity: int | None) -> list[str]:
    command = [sys.executable, "-B", "-u", str(ROOT / "tools" / "native_runs.py"), subcommand]
    command += list(arguments)
    if affinity is not None:
        command += ["--affinity", f"{affinity:X}"]
    return command


# --- Einzelfall ----------------------------------------------------------------


def documented_skip(
    case: Mapping[str, Any], protocol: Mapping[str, Any], reason: str, screen: str
) -> bool:
    """Nur der öffentliche Rückweg einer Skalierung unter der kleinsten Fläche ist bildlos."""
    variant = protocol.get("variant", {})
    return bool(
        case.get("kind") == "function"
        and case.get("variant", {}).get("set") == "skalierung"
        and variant.get("set") == "skalierung"
        and variant.get("scale") == case["variant"].get("scale")
        and variant.get("placed", {}).get("screen") == screen
        and reason
        and protocol.get("unmeasured") == {"scrollbars": reason, "icons": reason}
        and protocol.get("steps") == []
        and protocol.get("images") == []
        and protocol.get("scene") is None
        and protocol.get("result") is None
        and protocol.get("errors") == []
    )


def licence_protocol_only(
    case: Mapping[str, Any],
    protocol: Mapping[str, Any],
    *,
    phases: Mapping[str, Sequence[str]],
    licence_states: Sequence[str],
    run_states: Sequence[str],
    screen: str,
) -> bool:
    """Nur vollständig getypte Lizenzmesswerte passieren bildlos; das Urteil bleibt dem Bericht."""
    variant = protocol.get("variant", {})
    wanted = case.get("variant", {})
    state = wanted.get("licence")
    runs = protocol.get("licence_runs")
    if not (
        case.get("kind") == "function"
        and wanted.get("set") == "lizenz"
        and tuple(wanted.get("phases") or phases.get("lizenz", ())) == ("licence",)
        and all(
            variant.get(key) == value
            for key, value in wanted.items()
            if key not in {"screen", "window_size"}
        )
        and variant.get("placed", {}).get("screen") == screen
        and protocol.get("row", {}).get("id") == case.get("row")
        and state in licence_states
        and isinstance(runs, dict)
        and set(runs) == {state}
        and protocol.get("unmeasured") == {}
        and protocol.get("errors") == []
        and protocol.get("images") == []
        and isinstance(protocol.get("steps"), list)
    ):
        return False
    entry = runs[state]
    return (
        isinstance(entry, dict)
        and set(entry) == {"writes", "state", "reason"}
        and type(entry["writes"]) is bool
        and entry["state"] in run_states
        and isinstance(entry["reason"], str)
    )


def judge_case(
    folder: Path, case: Mapping[str, Any], record: Mapping[str, Any], *, head: str, screen: str
) -> dict[str, Any]:
    """Prüft Prozess, Abbau, Protokolle und Bilder eines Falls; wirft :class:`CaseRunError`."""
    if record.get("exit_code") != 0 or record.get("timeout"):
        raise CaseRunError(
            f"Der Fallprozess endete mit {record.get('exit_code')}"
            f"{' nach Fristablauf' if record.get('timeout') else ''};"
            " stderr.log, stapel.log und qt.log im Fallordner nennen den Grund."
        )
    if not record.get("clean_end"):
        raise CaseRunError("Eigene Prozesse liefen nach dem Fall weiter (child-tree.json).")
    try:
        bench = read_json(folder / "bench.json")
    except (OSError, ValueError) as problem:
        raise CaseRunError(f"bench.json fehlt oder ist kaputt: {problem}") from problem
    if bench.get("case") != dict(case):
        raise CaseRunError("bench.json nennt einen anderen Fall.")
    if bench.get("stage") != "done" or bench.get("shutdown_complete") is not True:
        raise CaseRunError(f"Der Fall endete nicht regulär: Stufe {bench.get('stage')}.")
    if bench.get("harness_exception"):
        raise CaseRunError("Der Prüfstand warf eine Ausnahme (bench.json, harness_exception).")
    protocols = (
        [folder / "function.json"]
        if case["kind"] == "function"
        else sorted((folder / "surfaces").glob("*.json"))
    )
    if not protocols or not all(path.is_file() for path in protocols):
        raise CaseRunError("Der Fall schrieb kein Flächen- oder Funktionsprotokoll.")
    for path in protocols:
        protocol = read_json(path)
        if protocol.get("errors"):
            raise CaseRunError(f"{path.name} trägt Fehler: {protocol['errors']}")
        if protocol.get("variant", {}).get("placed", {}).get("screen") != screen:
            raise CaseRunError(f"{path.name} lief nicht auf dem Schirm {screen}.")
        if protocol.get("version", {}).get("commit") != head:
            raise CaseRunError(f"{path.name} lief nicht am gebundenen Kopf {head}.")
    images = sorted(folder.glob("*.png"))
    if images:
        if not all(path.read_bytes().startswith(b"\x89PNG\r\n\x1a\n") for path in images):
            raise CaseRunError("Ein Bild des Falls ist kein PNG.")
        return {
            "status": "measured_needs_review",
            "images": len(images),
            "surfaces": len(protocols),
        }
    from tools.function_list import licence_states
    from tools.function_points import LICENCE_RUN_STATES
    from tools.function_setup import PHASES, Variant, below_smallest

    protocol = read_json(folder / "function.json") if case["kind"] == "function" else {}
    if licence_protocol_only(
        case,
        protocol,
        phases=PHASES,
        licence_states=licence_states(),
        run_states=LICENCE_RUN_STATES,
        screen=screen,
    ):
        return {"status": "licence_protocol_needs_judgement", "images": 0}
    reason = below_smallest(
        protocol.get("variant", {}).get("placed", {}), Variant.of(case.get("variant"))
    )
    if not documented_skip(case, protocol, reason, screen):
        raise CaseRunError("Bilder fehlen ohne öffentlichen Skalierungs- oder Lizenzvertrag.")
    return {"status": "unmeasured", "reason": reason, "images": 0}


def read_case(inventory: Path, number: int) -> dict[str, Any]:
    """Der Fall ``number`` aus ``cases.json`` eines Inventars — nur Funktions- und Sprachfälle."""
    missing = [name for name in REQUIRED_INPUTS if not (inventory / name).is_file()]
    missing += [] if (inventory / "scenes").is_dir() else ["scenes/"]
    if missing:
        raise StartRefusedError(
            f"Im Inventar {inventory} fehlt {', '.join(missing)}.",
            "Legen Sie es an: `tools/file_acceptance.py inventory --functions --out <lauf>`.",
        )
    cases = read_json(inventory / "cases.json")
    case = next((entry for entry in cases if entry.get("number") == number), None)
    if case is None:
        raise StartRefusedError(
            f"Das Inventar kennt keinen Fall {number}.",
            "Nennen Sie eine Nummer aus cases.json.",
        )
    if case.get("kind") not in CASE_KINDS:
        raise StartRefusedError(
            f"Fall {number} ist ein {case.get('kind')}-Fall.",
            f"Fahren Sie ihn mit `tools/file_acceptance.py run --first {number} --last {number}`.",
        )
    return dict(case)


def case_limit(
    case: Mapping[str, Any], rows: Iterable[Mapping[str, Any]], deadline: float | None
) -> float:
    """Die Frist eines Fallprozesses: ``--deadline`` oder :data:`CASE_DEADLINE_S`, dazu das Tor.

    ``--deadline`` setzt die Frist, auch über die Vorgabe hinaus. Mit dem
    Vorhersagetor (V4) wartet ein Fall je Klick bis ``PREDICTION_WAIT_S`` auf den
    Prüfer; diese Zeit kommt dazu, wie in ``file_acceptance.run``
    (``function_cases.prediction_wait_s``, RF10-2).
    """
    from tools.file_acceptance import Case
    from tools.function_cases import prediction_wait_s

    base = deadline if deadline is not None else CASE_DEADLINE_S
    return base + prediction_wait_s(Case(**case), rows)


def run_case(arguments: argparse.Namespace) -> int:
    """``case``: einen Fall eines Inventars neu, gebunden, begrenzt, mit Abbau und Urteil."""
    binding = checked_binding(arguments.binding)
    inventory = arguments.inventory.resolve()
    case = read_case(inventory, arguments.case)
    out = fresh_out(arguments.out)
    deadline = arguments.deadline or CASE_DEADLINE_S
    plan = {"case": case, "inventory": str(inventory), "out": str(out), "deadline_s": deadline}
    if not started(arguments, plan):
        return 0
    from tools.file_acceptance import crash_note
    from tools.function_cases import RESTART_EXIT, most_restarts

    rows = list(read_json(inventory / "rows.json"))
    limit = case_limit(case, rows, arguments.deadline)

    original = dict(os.environ)
    out.mkdir(parents=True)
    isolate_supervisor(out / "profile")
    real = real_profile(original)
    real_before = stat_only(real)
    copied = copy_inputs(inventory, out, (*REQUIRED_INPUTS, *OPTIONAL_INPUTS))
    # Ein Sprachfall, der vor einer Fläche einen frischen Prozess braucht, läuft
    # weiter — höchstens einmal je Zeile, wie in ``file_acceptance.run`` (FD-132).
    restarts = most_restarts(rows, case["row"]) if case["kind"] == "language" else 0
    identity = identity_of(arguments, binding, plan) | {
        "limit_s": limit,
        "restarts_allowed": restarts,
        "inputs": copied,
    }
    write_json(out / "identity.json", identity)
    folder = out / "cases" / f"{arguments.case:03d}"
    command = child_command(
        "case-child",
        "--binding",
        str(arguments.binding.resolve()),
        "--out",
        str(out),
        "--case",
        str(arguments.case),
        "--screen",
        arguments.screen,
        affinity=arguments.affinity,
    )
    failure = None
    verdict: dict[str, Any] = {}
    try:
        record = supervise_restarting(
            command,
            restarts=restarts,
            restart_exit=RESTART_EXIT,
            cwd=folder,
            env=profile_environment(os.environ, out / "profile"),
            deadline_s=limit,
            folder=folder,
        )
        crashed = record["exit_code"] != 0 or record["timeout"]
        write_json(
            folder / "process.json", {**record, "crash": crash_note(folder) if crashed else ""}
        )
        verdict = judge_case(folder, case, record, head=binding["head"], screen=arguments.screen)
    except Exception:
        failure = traceback.format_exc()
    if folder.exists():
        files = {
            path.relative_to(folder).as_posix(): native_binding.sha256_of(path)
            for path in sorted(folder.rglob("*"))
            if path.is_file() and path.suffix in (".json", ".png", ".log")
        }
        write_json(folder / "evidence.json", {**verdict, "files": files})
    return finish(out, binding, inventory, copied, real, real_before, failure, {"verdict": verdict})


# --- Maßkartenfolge ---------------------------------------------------------------


def card_rows(inventory: Path) -> list[dict[str, Any]]:
    """Die vier Zeilen der Maßkartenfolge aus ``rows.json`` eines Inventars, in ihrer Folge."""
    rows_file = inventory / "rows.json"
    if not rows_file.is_file() or not (inventory / "scenes").is_dir():
        raise StartRefusedError(
            f"Im Inventar {inventory} fehlen rows.json oder scenes/.",
            "Legen Sie es an: `tools/file_acceptance.py inventory --functions --rows"
            " resize_hole,move_feature,duplicate_feature,rotate_feature --out <inventar>`.",
        )
    by_id = {str(row.get("id")): row for row in read_json(rows_file)}
    missing = [name for name in CARD_ROWS if name not in by_id]
    if missing:
        raise StartRefusedError(
            f"rows.json nennt {', '.join(missing)} nicht.",
            f"Legen Sie das Inventar mit `--rows {','.join(CARD_ROWS)}` an.",
        )
    return [by_id[name] for name in CARD_ROWS]


def card_languages(text: str | None) -> list[str]:
    from app.i18n.catalog import available_languages

    known = list(available_languages())
    wanted = [entry for entry in (text or "").split(",") if entry] or known
    strange = [entry for entry in wanted if entry not in known]
    if strange:
        raise StartRefusedError(
            f"Unbekannte Sprache: {', '.join(strange)}.",
            f"Wählen Sie aus {', '.join(known)}.",
        )
    return wanted


def judge_language(record: Mapping[str, Any], folder: Path) -> dict[str, Any]:
    """Was eine Sprache der Folge belegt: Prozess, Abbau, Siegel und jede Bedingung."""
    try:
        observation = read_json(folder / "observation.json")
    except OSError, ValueError:
        observation = {}
    checks = observation.get("checks", [])
    held = sum(bool(check.get("holds")) for check in checks)
    item = {
        "exit": record.get("exit_code"),
        "timeout": record.get("timeout"),
        "clean_end": record.get("clean_end"),
        "execution_complete": observation.get("execution_complete") is True,
        "shutdown_complete": observation.get("shutdown_complete") is True,
        "source_pins_unchanged": observation.get("source_pins_unchanged") is True,
        "checks_held": held,
        "checks": len(checks),
        "unmeasured": len(observation.get("unmeasured", [])),
        "captures": len(observation.get("captures", [])),
    }
    item["complete"] = bool(
        item["exit"] == 0
        and not item["timeout"]
        and item["clean_end"]
        and item["execution_complete"]
        and item["shutdown_complete"]
        and item["source_pins_unchanged"]
        and checks
        and held == len(checks)
    )
    return item


def run_measure_card(arguments: argparse.Namespace) -> int:
    """``measure-card``: je Sprache ein gebundener, begrenzter Prozess der Maßkartenfolge."""
    binding = checked_binding(arguments.binding)
    inventory = arguments.inventory.resolve()
    rows = card_rows(inventory)
    languages = card_languages(arguments.languages)
    out = fresh_out(arguments.out)
    deadline = arguments.deadline or CARD_DEADLINE_S
    plan = {
        "languages": languages,
        "inventory": str(inventory),
        "out": str(out),
        "deadline_s": deadline,
    }
    if not started(arguments, plan):
        return 0
    original = dict(os.environ)
    out.mkdir(parents=True)
    isolate_supervisor(out / "profile")
    real = real_profile(original)
    real_before = stat_only(real)
    write_json(out / "rows.json", rows)
    copied = copy_inputs(inventory, out, ())
    copied["rows.json"] = native_binding.sha256_of(inventory / "rows.json")
    write_json(out / "identity.json", identity_of(arguments, binding, plan) | {"inputs": copied})
    children: list[dict[str, Any]] = []
    failure = None
    try:
        for language in languages:
            folder = out / language
            command = child_command(
                "card-child",
                "--binding",
                str(arguments.binding.resolve()),
                "--evidence",
                str(folder),
                "--language",
                language,
                "--rows",
                str(out / "rows.json"),
                "--scenes",
                str(out / "scenes"),
                "--screen",
                arguments.screen,
                "--deadline",
                f"{deadline:g}",
                affinity=arguments.affinity,
            )
            record = supervise(
                command,
                cwd=folder,
                env=profile_environment(os.environ, folder / "profile"),
                deadline_s=deadline,
                folder=folder,
            )
            item = {"language": language, **judge_language(record, folder)}
            write_json(folder / "process.json", {**record, **item})
            children.append(item)
            write_json(out / "progress.json", children)
            if not item["complete"]:
                raise CaseRunError(f"Die Sprache {language} trägt nicht: {item}")
    except Exception:
        failure = traceback.format_exc()
    complete = len(children) == len(languages) and all(item["complete"] for item in children)
    return finish(
        out,
        binding,
        inventory,
        copied,
        real,
        real_before,
        failure,
        {
            "completed_languages": [item["language"] for item in children if item["complete"]],
            "children": children,
            "all_languages_complete": complete,
            "visual_review_complete": False,
        },
    )


# --- Gemeinsam ------------------------------------------------------------------------


def checked_binding(path: Path) -> dict[str, Any]:
    """Liest und prüft die Bindung, bevor irgendetwas anderes geschieht."""
    binding = native_binding.read_binding(path)
    native_binding.verify(binding)
    return binding


def started(arguments: argparse.Namespace, plan: Mapping[str, Any]) -> bool:
    """``--check`` meldet den geprüften Plan; ohne ``--native`` startet nichts."""
    if not arguments.screen.strip():
        raise StartRefusedError(
            "--screen ist leer.", "Nennen Sie den Aufnahmeschirm, etwa MSI MAG271CQR."
        )
    if arguments.check:
        print(json.dumps({"ready": True, **plan}, ensure_ascii=False, indent=2), flush=True)
        return False
    if not arguments.native:
        raise StartRefusedError(
            "Kein Start ohne --native: Der Lauf zeigt ein echtes Fenster auf dem Schirm"
            f" {arguments.screen}.",
            "Prüfen Sie mit --check und starten Sie mit --native erst mit freigegebenem Schirm.",
        )
    if sys.platform != "win32":
        raise StartRefusedError(
            "Native Läufe fährt dieses Werkzeug nur unter Windows.",
            "Fahren Sie sie auf dem Windows-Rechner mit dem Aufnahmeschirm.",
        )
    return True


def identity_of(
    arguments: argparse.Namespace, binding: Mapping[str, Any], plan: Mapping[str, Any]
) -> dict[str, Any]:
    return {
        **plan,
        "head": binding["head"],
        "tree": binding["tree"],
        "root": binding["root"],
        "files_digest": binding["files_digest"],
        "binding": str(arguments.binding.resolve()),
        "binding_sha256": native_binding.sha256_of(arguments.binding),
        "runner": dict(binding["runner"]),
        "python": sys.executable,
        "screen": arguments.screen,
        "affinity": f"{arguments.affinity:X}" if arguments.affinity is not None else None,
        "supervisor_pid": os.getpid(),
        "started_utc": now(),
        "performance_valid": False,
    }


def finish(
    out: Path,
    binding: Mapping[str, Any],
    inventory: Path,
    copied: Mapping[str, str],
    real: Sequence[Path],
    real_before: Mapping[str, Any],
    failure: str | None,
    result: Mapping[str, Any],
) -> int:
    """Schlussbindung: Siegel, Inventar und echtes Profil wie vorher; ``done.json`` sagt alles."""
    try:
        native_binding.verify(binding)
        seal_after = True
    except SealError as problem:
        seal_after = False
        failure = (failure or "") + str(problem)
    inputs_after = unchanged_inputs(inventory, copied)
    profile_after = stat_only(real) == dict(real_before)
    done = {
        **result,
        "failure": failure,
        "seal_unchanged": seal_after,
        "inputs_unchanged": inputs_after,
        "real_profile_unchanged": profile_after,
        "ended_utc": now(),
        "performance_valid": False,
    }
    write_json(out / "done.json", done)
    green = failure is None and seal_after and inputs_after and profile_after
    shown = ("failure", "seal_unchanged", "inputs_unchanged", "real_profile_unchanged")
    print(json.dumps({key: done[key] for key in shown}, ensure_ascii=False), flush=True)
    return 0 if green else 1


# --- Kindprozesse -----------------------------------------------------------------


def case_child(arguments: argparse.Namespace) -> int:
    """Kind von ``case``: Siegel im Kind, dann ``file_acceptance.py child``, dann Siegel."""
    out = arguments.out.resolve()
    binding, pins = native_binding.enter(arguments.binding, out, affinity=arguments.affinity)
    from tools import file_acceptance

    code = file_acceptance.main(
        ["child", "--out", str(out), "--case", str(arguments.case), "--screen", arguments.screen]
    )
    try:
        native_binding.leave(binding, pins, out)
    except SealError as problem:
        print(problem, file=sys.stderr, flush=True)
        return code or 3
    return code


def card_child(arguments: argparse.Namespace) -> int:
    """Kind von ``measure-card``: Siegel im Kind, Abbruchwächter, dann die Folge einer Sprache."""
    import faulthandler

    evidence = arguments.evidence.resolve()
    evidence.mkdir(parents=True, exist_ok=True)
    binding, pins = native_binding.enter(arguments.binding, evidence, affinity=arguments.affinity)
    faulthandler.enable()
    faulthandler.dump_traceback_later(max(arguments.deadline - INNER_MARGIN_S, 1.0), exit=True)
    from tools.native_measure_card import CardRoute

    try:
        return CardRoute(evidence, arguments.language).run(
            rows=read_json(arguments.rows),
            scenes=arguments.scenes.resolve(),
            screen=arguments.screen,
            head=binding["head"],
            leave=lambda: native_binding.leave(binding, pins, evidence),
        )
    finally:
        faulthandler.cancel_dump_traceback_later()


# --- Einstieg -------------------------------------------------------------------------


def parser() -> argparse.ArgumentParser:
    reading = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    commands = reading.add_subparsers(dest="command", required=True)
    binding = commands.add_parser("bind")
    binding.add_argument("--out", required=True, type=Path)
    for name in ("case", "measure-card"):
        command = commands.add_parser(name)
        command.add_argument("--binding", required=True, type=Path)
        command.add_argument("--inventory", required=True, type=Path)
        command.add_argument("--screen", required=True)
        command.add_argument("--out", required=True, type=Path)
        command.add_argument("--deadline", type=float, default=None)
        command.add_argument("--affinity", type=affinity_of, default=None)
        mode = command.add_mutually_exclusive_group()
        mode.add_argument("--check", action="store_true")
        mode.add_argument("--native", action="store_true")
        if name == "case":
            command.add_argument("--case", required=True, type=int)
        else:
            command.add_argument("--languages", default=None)
    child = commands.add_parser("case-child")
    child.add_argument("--binding", required=True, type=Path)
    child.add_argument("--out", required=True, type=Path)
    child.add_argument("--case", required=True, type=int)
    child.add_argument("--screen", required=True)
    child.add_argument("--affinity", type=affinity_of, default=None)
    card = commands.add_parser("card-child")
    card.add_argument("--binding", required=True, type=Path)
    card.add_argument("--evidence", required=True, type=Path)
    card.add_argument("--language", required=True)
    card.add_argument("--rows", required=True, type=Path)
    card.add_argument("--scenes", required=True, type=Path)
    card.add_argument("--screen", required=True)
    card.add_argument("--deadline", required=True, type=float)
    card.add_argument("--affinity", type=affinity_of, default=None)
    return reading


def main(argv: Sequence[str] | None = None) -> int:
    """Ausgang 0: fertig oder geprüft; 1: gelaufen, aber nicht tragfähig; 2: nicht gestartet."""
    try:
        arguments = parser().parse_args(list(argv) if argv is not None else None)
    except StartRefusedError as problem:
        print(problem, file=sys.stderr, flush=True)
        return 2
    try:
        if arguments.command == "bind":
            binding = native_binding.write_binding(arguments.out)
            print(
                f"{arguments.out}: {binding['head']} mit {len(binding['files'])} Pins", flush=True
            )
            return 0
        if arguments.command == "case":
            return run_case(arguments)
        if arguments.command == "measure-card":
            return run_measure_card(arguments)
        if arguments.command == "case-child":
            return case_child(arguments)
        return card_child(arguments)
    except (SealError, StartRefusedError) as problem:
        print(problem, file=sys.stderr, flush=True)
        return 2


if __name__ == "__main__":
    sys.exit(main())
