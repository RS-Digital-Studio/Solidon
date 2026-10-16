"""Kein Prozess eines Falls startet im Arbeitsbaum (RC-10).

Der Fallprozess lief mit ``cwd=ROOT``. Ein Speicherdialog, der nur einen
Dateinamen vorschlägt (*Projekt speichern*, OpenSCAD, *Baustein weitergeben*,
Aktivierungsanfrage), schreibt in den Arbeitsordner — das wäre der Baum des
Prüfstands. Jeder Start eines Kindes im Prüfstand nennt deshalb seinen Ordner
ausdrücklich, und der ist nie ``ROOT``; nur Git liest den Baum (``-C`` oder
``cwd=ROOT``). Ohne Fenster, über den Quelltext.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent

#: Die Werkzeuge, die Fall- und Kindprozesse des Prüfstands starten.
STARTERS = (
    "tools/file_acceptance.py",
    "tools/native_runs.py",
    "tools/native_binding.py",
    "tools/function_bench.py",
)
STARTS = frozenset({"run", "Popen", "check_output", "call", "check_call"})


def _is_git(call: ast.Call) -> bool:
    command = call.args[0] if call.args else None
    return (
        isinstance(command, ast.List)
        and bool(command.elts)
        and isinstance(command.elts[0], ast.Constant)
        and command.elts[0].value == "git"
    )


def starts_in_the_tree(source: str) -> list[int]:
    """Zeilen, an denen ein Kind ohne eigenen Ordner oder in ``ROOT`` startet — außer Git.

    Ein Start über ``subprocess`` nennt seinen Ordner; kein Aufruf reicht
    ``cwd=ROOT`` weiter (auch nicht an einen Aufseher wie ``supervise``).
    """
    found = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.Call) or _is_git(node):
            continue
        folder = next((k.value for k in node.keywords if k.arg == "cwd"), None)
        started = (
            isinstance(node.func, ast.Attribute)
            and node.func.attr in STARTS
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "subprocess"
        )
        in_tree = isinstance(folder, ast.Name) and folder.id == "ROOT"
        if in_tree or (started and folder is None):
            found.append(node.lineno)
    return found


def test_no_child_of_the_bench_starts_in_the_tree() -> None:
    found = {
        name: lines
        for name in STARTERS
        if (lines := starts_in_the_tree((ROOT / name).read_text(encoding="utf-8")))
    }
    assert not found, f"Kindprozess ohne eigenen Ordner oder im Baum: {found}"


def test_the_scan_sees_a_start_in_the_tree() -> None:
    """Gegenprobe: ohne ``cwd``, mit ``cwd=ROOT`` fällt es auf; Git und ein Fallordner nicht."""
    planted = (
        "subprocess.Popen([sys.executable, 'x'], cwd=ROOT)\n"
        "subprocess.run([sys.executable, '-m', 'app.cli.main'])\n"
        "subprocess.run(['git', 'rev-parse', 'HEAD'], cwd=ROOT)\n"
        "subprocess.Popen(command, cwd=folder)\n"
        "supervise(command, cwd=ROOT, env=env)\n"
    )
    assert starts_in_the_tree(planted) == [1, 2, 5]


def test_the_menubar_starts_in_a_run_folder_that_exists(tmp_path: Path, monkeypatch: Any) -> None:
    """Das Inventar fragt die Menüleiste, bevor es den Laufordner anlegt.

    Mit ``cwd=out`` (RC-10) scheiterte das an einem neuen Ordner mit
    „Der Verzeichnisname ist ungültig“ (Offscreen-Probe der Matrix).
    """
    import subprocess
    from types import SimpleNamespace

    from tools import file_acceptance

    out = tmp_path / "neuer-lauf"
    seen: list[bool] = []

    def run(command: list[str], **named: Any) -> Any:
        seen.append(Path(named["cwd"]).is_dir())
        if not seen[-1]:
            raise NotADirectoryError(267, "Der Verzeichnisname ist ungültig")
        (out / "menubar.json").write_text("{}", encoding="utf-8")
        return SimpleNamespace(returncode=0, stderr="")

    monkeypatch.setattr(file_acceptance.subprocess, "run", run)
    assert subprocess.run is run
    assert file_acceptance.menubar(out) == out / "menubar.json"
    assert seen == [True]
