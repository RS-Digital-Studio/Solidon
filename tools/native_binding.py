"""Bindung und Siegel der nativen Läufe: welcher Stand am echten Fenster läuft (FD-164).

    .venv\\Scripts\\python.exe tools/native_runs.py bind --out <bindung.json>

Eine Bindung hält Wurzel, Kopf, Baum, Interpreter und den SHA-256 jeder
versionierten Datei unter ``app/`` und ``tools/`` fest. Die Läufer selbst
(:data:`RUNNER_FILES`) stehen darunter noch einmal gesondert: Das ist ihr
**Siegel**. Erhoben wird eine Bindung nur an einem sauberen Baum — was nicht
committet ist, lässt sich nicht binden, also läuft auch nichts Ungesichertes.
Geprüft wird sie dreimal: vom Aufseher vor dem Start
(``tools/native_runs.py``), im Kindprozess vor dem ersten Qt-Import
(:func:`enter`) und nach dem Lauf (:func:`leave`). Weicht etwas ab, startet
nichts, und die Meldung nennt die Datei und den nächsten Schritt (Regel 17).

Anlass: Die nativen Anschlüsse lagen als Sitzungswerkzeuge außerhalb des
Baums, und eine spätere, ungesiegelte Ergänzung im Läuferordner wäre ohne
Prüfung gelaufen (FD-164). Dieses Modul lädt weder Qt noch ``app``, bevor die
Bindung geprüft ist.
"""

from __future__ import annotations

import ctypes
import hashlib
import json
import os
import platform
import subprocess
import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

ROOT: Final = Path(__file__).resolve().parent.parent

#: Die Läufer, deren Hash das Siegel bildet. Eine Änderung an einem davon
#: verweigert den Start, bis sie committet und neu gebunden ist.
RUNNER_FILES: Final = (
    "tools/native_binding.py",
    "tools/native_runs.py",
    "tools/native_measure_card.py",
)

#: Wessen versionierte Dateien gepinnt werden: Produkt und Prüfstand.
PINNED_TREES: Final = ("app", "tools")

#: Wo keine ungesicherte Änderung liegen darf — auch keine neue Datei, die ein
#: Import träfe.
CLEAN_TREES: Final = ("app", "tools", "tests")

#: Die Nutzerordner, die ein nativer Lauf auf sein eigenes Profil legt. Nie
#: ``HOME`` oder ``USERPROFILE``: Grafiktreiber und ihre Zwischenspeicher
#: hängen daran (``file_acceptance.PROFILE_VARIABLES``).
PROFILE_VARIABLES: Final = (
    "APPDATA",
    "LOCALAPPDATA",
    "XDG_CONFIG_HOME",
    "XDG_DATA_HOME",
    "XDG_CACHE_HOME",
    "XDG_STATE_HOME",
    "TEMP",
    "TMP",
)

#: Fassung des Bindungsformats. Die Bindungen der Sitzungswerkzeuge trugen 1.
SCHEMA: Final = 2

#: Wie lange ein Git-Aufruf höchstens dauern darf (Sekunden).
GIT_SECONDS: Final = 60

#: Wie viele Abweichungen eine Meldung höchstens aufzählt.
LISTED: Final = 8


class SealError(RuntimeError):
    """Ein Stand, der nicht zur Bindung passt — mit dem Satz, was jetzt hilft (Regel 17)."""

    def __init__(self, problem: str, suggestion: str) -> None:
        super().__init__(f"{problem}\nHandlungsvorschlag: {suggestion}")
        self.problem = problem
        self.suggestion = suggestion


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(pins: Mapping[str, str]) -> str:
    """Ein Hash über alle Pins — gleich genau dann, wenn jede Datei gleich ist."""
    text = json.dumps(dict(sorted(pins.items())), separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def git(root: Path, *arguments: str) -> str:
    """Ein Git-Aufruf im Baum ``root``; scheitert er, sagt die Meldung, woran."""
    try:
        finished = subprocess.run(
            ["git", "-C", str(root), *arguments],
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=GIT_SECONDS,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
    except (OSError, subprocess.TimeoutExpired) as problem:
        raise SealError(
            f"git {' '.join(arguments)} lief in {root} nicht: {problem}",
            "Prüfen Sie, ob git im PATH liegt und der Ordner ein Arbeitsbaum ist.",
        ) from problem
    if finished.returncode != 0:
        raise SealError(
            f"git {' '.join(arguments)} endete in {root} mit {finished.returncode}:"
            f" {finished.stderr.strip()}",
            "Prüfen Sie, ob der Ordner ein Arbeitsbaum dieses Repositorys ist.",
        )
    return finished.stdout


def tracked(root: Path) -> list[str]:
    """Die versionierten Dateien unter :data:`PINNED_TREES`, sortiert."""
    output = git(root, "ls-files", "-z", "--", *PINNED_TREES)
    return sorted(entry for entry in output.split("\0") if entry)


def unsaved(root: Path) -> list[str]:
    """Was unter :data:`CLEAN_TREES` geändert, gelöscht oder neu und nicht ignoriert ist."""
    output = git(
        root, "status", "--porcelain=v1", "-z", "--untracked-files=normal", "--", *CLEAN_TREES
    )
    return [entry for entry in output.split("\0") if entry]


def pins_of(root: Path, paths: list[str]) -> dict[str, str]:
    return {path: sha256_of(root / path) for path in paths}


def listed(entries: list[str]) -> str:
    shown = ", ".join(entries[:LISTED])
    return shown + (f" und {len(entries) - LISTED} weitere" if len(entries) > LISTED else "")


def make_binding(root: Path = ROOT) -> dict[str, Any]:
    """Die Bindung des sauberen Baums ``root``: Kopf, Baum, Interpreter, Pins, Siegel."""
    changes = unsaved(root)
    if changes:
        raise SealError(
            f"Ungesicherte Änderungen unter app/, tools/ oder tests/: {listed(changes)}.",
            "Committen Sie die Änderungen und binden Sie danach; gebunden wird nur ein"
            " versionierter Stand.",
        )
    paths = tracked(root)
    missing = [path for path in RUNNER_FILES if path not in paths]
    if missing:
        raise SealError(
            f"Der Läufer ist nicht versioniert: {listed(missing)}.",
            "Committen Sie die Läufer; ein Siegel gibt es nur über einen versionierten Stand.",
        )
    pins = pins_of(root, paths)
    return {
        "schema": SCHEMA,
        "root": str(root.resolve()),
        "head": git(root, "rev-parse", "HEAD").strip(),
        "tree": git(root, "rev-parse", "HEAD^{tree}").strip(),
        "python": str(Path(sys.executable).resolve()),
        "python_version": platform.python_version(),
        "runner": {path: pins[path] for path in RUNNER_FILES},
        "files": pins,
        "files_digest": digest(pins),
        "created_utc": datetime.now(UTC).isoformat(),
    }


def outside(path: Path, root: Path = ROOT) -> Path:
    """Ein Beleg liegt nie im Arbeitsbaum: Er reist nicht mit und stört keinen Status."""
    resolved = path.resolve()
    if resolved == root.resolve() or root.resolve() in resolved.parents:
        raise SealError(
            f"{resolved} liegt im Repository.",
            "Wählen Sie einen Ort außerhalb des Arbeitsbaums.",
        )
    return resolved


def write_binding(path: Path, root: Path = ROOT) -> dict[str, Any]:
    """Schreibt die Bindung nach ``path``; eine vorhandene Bindung bleibt, wie sie ist."""
    target = outside(path, root)
    if target.exists():
        raise SealError(
            f"{target} liegt schon.",
            "Wählen Sie einen neuen Namen; eine Bindung ist ein Beleg und wird nicht"
            " überschrieben.",
        )
    binding = make_binding(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(binding, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return binding


def form_problems(binding: object) -> list[str]:
    """Welche Felder einer Bindung fehlen, falsch geformt sind oder sich widersprechen."""
    if not isinstance(binding, dict) or binding.get("schema") != SCHEMA:
        return ["schema"]
    problems = [
        key
        for key in ("head", "tree")
        if not (
            isinstance(binding.get(key), str)
            and len(binding[key]) == 40
            and set(binding[key]) <= set("0123456789abcdef")
        )
    ]
    problems += [key for key in ("root", "python") if not isinstance(binding.get(key), str)]
    files = binding.get("files")
    if not (isinstance(files, dict) and files):
        return [*problems, "files"]
    if binding.get("files_digest") != digest(files):
        problems.append("files_digest")
    runner = binding.get("runner")
    if not (
        isinstance(runner, dict)
        and set(runner) == set(RUNNER_FILES)
        and all(files.get(path) == value for path, value in runner.items())
    ):
        problems.append("runner")
    return problems


def read_binding(path: Path) -> dict[str, Any]:
    """Liest eine Bindung und prüft ihre Form, bevor ihr irgendetwas geglaubt wird."""
    try:
        binding = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError) as problem:
        raise SealError(
            f"Die Bindung {path} ließ sich nicht lesen: {problem}",
            "Erzeugen Sie sie mit `tools/native_runs.py bind --out <datei>`.",
        ) from problem
    wrong = form_problems(binding)
    if wrong:
        raise SealError(
            f"Die Bindung {path} hat nicht die erwartete Form ({', '.join(wrong)}).",
            "Erzeugen Sie eine neue mit `tools/native_runs.py bind --out <datei>`; Bindungen"
            " der früheren Sitzungswerkzeuge gelten hier nicht.",
        )
    return dict(binding)


def verify(binding: Mapping[str, Any], root: Path = ROOT) -> dict[str, str]:
    """Prüft den heutigen Stand von ``root`` gegen die Bindung und gibt seine Pins zurück.

    Zuerst das Siegel der Läufer — das ist die genaueste Meldung —, dann
    Wurzel, Interpreter, Kopf, Baum, ungesicherte Änderungen und jede
    gepinnte Datei.
    """
    rebind = "Committen Sie die Änderung und binden Sie neu (`tools/native_runs.py bind`)."
    broken = [
        path
        for path, expected in binding["runner"].items()
        if not (root / path).is_file() or sha256_of(root / path) != expected
    ]
    if broken:
        raise SealError(
            f"Siegel gebrochen: {listed(broken)} weicht vom gebundenen Stand ab;"
            " der Läufer startet nicht.",
            rebind,
        )
    if Path(binding["root"]).resolve() != root.resolve():
        raise SealError(
            f"Die Bindung gehört zu {binding['root']}, der Läufer liegt in {root}.",
            "Starten Sie den Läufer aus dem gebundenen Baum oder binden Sie diesen Baum.",
        )
    if Path(sys.executable).resolve() != Path(binding["python"]).resolve():
        raise SealError(
            f"Der Interpreter {sys.executable} ist nicht der gebundene {binding['python']}.",
            "Starten Sie mit dem gebundenen Interpreter oder binden Sie mit diesem neu.",
        )
    for key, arguments in (("head", ("HEAD",)), ("tree", ("HEAD^{tree}",))):
        actual = git(root, "rev-parse", *arguments).strip()
        if actual != binding[key]:
            raise SealError(
                f"{key} ist {actual}, gebunden ist {binding[key]}.",
                "Binden Sie den heutigen Stand neu oder wechseln Sie auf den gebundenen.",
            )
    changes = unsaved(root)
    if changes:
        raise SealError(f"Ungesicherte Änderungen: {listed(changes)}.", rebind)
    pins = pins_of(root, tracked(root))
    expected = dict(binding["files"])
    differing = sorted(
        path for path in set(pins) | set(expected) if pins.get(path) != expected.get(path)
    )
    if differing:
        raise SealError(f"Gepinnte Dateien weichen ab: {listed(differing)}.", rebind)
    return pins


def write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8"
    )


def set_affinity(mask: int) -> int:
    """Legt den Prozess auf die Kerne der Maske und liest die Maske zurück (nur Windows)."""
    if sys.platform != "win32":
        raise SealError(
            "Eine Kernmaske setzt dieser Läufer nur unter Windows.",
            "Lassen Sie --affinity weg.",
        )
    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.GetCurrentProcess.restype = ctypes.c_void_p
    kernel.SetProcessAffinityMask.argtypes = (ctypes.c_void_p, ctypes.c_size_t)
    kernel.GetProcessAffinityMask.argtypes = (
        ctypes.c_void_p,
        ctypes.POINTER(ctypes.c_size_t),
        ctypes.POINTER(ctypes.c_size_t),
    )
    handle = kernel.GetCurrentProcess()
    actual, system = ctypes.c_size_t(), ctypes.c_size_t()
    if not (
        kernel.SetProcessAffinityMask(handle, mask)
        and kernel.GetProcessAffinityMask(handle, ctypes.byref(actual), ctypes.byref(system))
    ):
        raise SealError(
            f"Die Kernmaske {mask:X} ließ sich nicht setzen: {ctypes.get_last_error()}.",
            "Wählen Sie eine Maske, die nur vorhandene Kerne nennt.",
        )
    if actual.value != mask:
        raise SealError(
            f"Gesetzt war {mask:X}, gelesen wurde {actual.value:X}.",
            "Wählen Sie eine Maske, die nur vorhandene Kerne nennt.",
        )
    return int(actual.value)


def enter(
    binding_path: Path, evidence: Path, *, affinity: int | None = None
) -> tuple[dict[str, Any], dict[str, str]]:
    """Prüft im Kindprozess vor dem ersten Qt-Import: Siegel, Profil, Paketeinstieg, Kerne.

    Die Reihenfolge ist die Aussage. Zuerst die Bindung — sonst liefe ein
    fremder Stand. Dann die acht Nutzerordner auf ``<evidence>/profile`` —
    sonst schriebe der Lauf in ein echtes Profil. Dann ``app`` und ``app.ui``
    aus der gebundenen Wurzel; ``app.ui`` setzt ``PYSIDE6_OPTION_LAZY``, bevor
    irgendein PySide-Modul lädt. Erst danach entstehen eigene Belege.
    """
    if any(name == "PySide6" or name.startswith("PySide6.") for name in sys.modules):
        raise SealError(
            "PySide6 war vor der Siegelprüfung geladen.",
            "Starten Sie den Kindprozess nur über `tools/native_runs.py`.",
        )
    binding = read_binding(binding_path)
    pins = verify(binding)
    profile = (evidence / "profile").resolve()
    for name in PROFILE_VARIABLES:
        wanted = profile / name.lower()
        if Path(os.environ.get(name) or ".").resolve() != wanted:
            raise SealError(
                f"{name} zeigt nicht auf das Fallprofil {wanted}.",
                "Starten Sie den Kindprozess nur über `tools/native_runs.py`; er legt alle"
                " acht Nutzerordner auf das Fallprofil.",
            )
    # Im Belegordner, nie im Baum: Ein Speicherdialog, der nur einen Dateinamen
    # vorschlägt, schreibt in den Arbeitsordner (RC-10). ``app`` kommt über den Pfad.
    evidence.mkdir(parents=True, exist_ok=True)
    os.chdir(evidence)
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    sys.dont_write_bytecode = True
    import app
    import app.ui

    entries = {
        "app": (app.__file__, "app/__init__.py"),
        "app.ui": (app.ui.__file__, "app/ui/__init__.py"),
    }
    for module, (loaded, relative) in entries.items():
        if loaded is None or Path(loaded).resolve() != ROOT / relative:
            raise SealError(
                f"{module} kam aus {loaded}, nicht aus {ROOT / relative}.",
                "Starten Sie mit PYTHONPATH auf die gebundene Wurzel.",
            )
    if os.environ.get("PYSIDE6_OPTION_LAZY") != "0" or "PySide6" in sys.modules:
        raise SealError(
            "Der Paketeinstieg app.ui hat PySide6 geladen oder PYSIDE6_OPTION_LAZY nicht gesetzt.",
            "Prüfen Sie app/ui/__init__.py gegen den gebundenen Stand.",
        )
    mask = set_affinity(affinity) if affinity is not None else None
    for value in (profile / name.lower() for name in PROFILE_VARIABLES):
        value.mkdir(parents=True, exist_ok=True)
    record = evidence / "seal-enter.json"
    if record.exists():
        raise SealError(
            f"{record} liegt schon.",
            "Wählen Sie einen neuen Ausgabeordner; alte Belege bleiben unverändert.",
        )
    write_json(
        record,
        {
            "pid": os.getpid(),
            "executable": sys.executable,
            "app_file": app.__file__,
            "ui_entry_file": app.ui.__file__,
            "pyside_imported": False,
            "pyside_lazy": os.environ["PYSIDE6_OPTION_LAZY"],
            "sys_path_first": sys.path[0],
            "cwd": str(Path.cwd()),
            "head": binding["head"],
            "tree": binding["tree"],
            "binding_sha256": sha256_of(Path(binding_path)),
            "files_digest": digest(pins),
            "files": len(pins),
            "environment": {name: os.environ[name] for name in PROFILE_VARIABLES},
            "affinity": f"{mask:X}" if mask is not None else None,
            "performance_valid": False,
        },
    )
    return binding, pins


def leave(binding: Mapping[str, Any], before: Mapping[str, str], evidence: Path) -> None:
    """Prüft nach dem Lauf, dass Stand und Pins dieselben sind wie beim Eintritt."""
    after = verify(binding)
    write_json(
        evidence / "seal-leave.json",
        {"files_digest": digest(after), "files": len(after), "same": after == dict(before)},
    )
    if after != dict(before):
        raise SealError(
            "Gepinnte Dateien haben sich während des Laufs geändert.",
            "Wiederholen Sie den Lauf ohne parallele Arbeit im gebundenen Baum.",
        )
