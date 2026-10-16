"""Wer die Nutzerordner umbiegt, nimmt den Schlüsselbund des Nutzers mit weg (CS-36, RC-12).

Der Schlüsselbund liegt in keinem Nutzerordner — Windows-Tresor,
macOS-Schlüsselbund, Secret Service —, und ``keyring`` wählt sein Backend aus
``PYTHON_KEYRING_BACKEND``. Ein Werkzeug, das ein frisches Profil herstellt,
aber den Schlüsselbund lässt, fragt die Schlüssel des Nutzers: Die Bilder der
Website zeigten, ob in Roberts Tresor ein Chat-Schlüssel liegt, und ein Fall des
Prüfstands hing an fremden Daten. ``app.core.paths.ISOLATED_KEYRING`` ist die
eine Quelle; dieser Wächter liest jede Funktion unter ``tools/``, die eine
Umgebung mit Nutzerordnern beschreibt, und verlangt sie dort. Ohne Fenster.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

#: Woran eine Funktion zu erkennen ist, die Nutzerordner nennt.
PROFILE_NAMES = re.compile(r"""['"](?:LOCAL)?APPDATA['"]|PROFILE_VARIABLES|ISOLATED_VARIABLES""")
#: Woran sie zu erkennen ist, dass sie eine Umgebung schreibt.
WRITES = re.compile(
    r"\b(?:os\.environ|env|environment)(?:\[[^\]\n]+\]\s*=(?!=)|\.update\(|\.setdefault\()"
)
#: Funktionen, die Nutzerordner schreiben, ohne ein frisches Profil herzustellen.
NOT_AN_ISOLATION = {
    # Biegt für einen Augenblick auf das echte Profil zurück, um dessen Ordner per
    # ``stat`` zu vergleichen; fragt keinen Schlüssel.
    ("tools/native_runs.py", "real_profile"),
}


def _own_source(source: str, function: ast.FunctionDef | ast.AsyncFunctionDef) -> str:
    """Der Text einer Funktion ohne die Funktionen darin."""
    text = ast.get_source_segment(source, function) or ""
    for inner in ast.walk(function):
        if inner is not function and isinstance(inner, ast.FunctionDef | ast.AsyncFunctionDef):
            text = text.replace(ast.get_source_segment(source, inner) or "", "")
    return text


def profile_writers(source: str) -> list[tuple[str, bool]]:
    """Je Funktion, die Nutzerordner in eine Umgebung schreibt: Name, mit Schlüsselbund?"""
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            text = _own_source(source, node)
            if PROFILE_NAMES.search(text) and WRITES.search(text):
                found.append((node.name, "ISOLATED_KEYRING" in text))
    return found


def test_every_profile_isolation_in_the_tools_takes_the_keyring_too() -> None:
    writers = {
        (path.relative_to(ROOT).as_posix(), name): keyring
        for path in sorted((ROOT / "tools").glob("*.py"))
        for name, keyring in profile_writers(path.read_text(encoding="utf-8"))
    }
    # Zählen, bevor geurteilt wird: Eine Suche, die nichts findet, sähe grün aus.
    assert len(writers) >= 12, sorted(writers)
    missing = sorted(
        where for where, keyring in writers.items() if not keyring and where not in NOT_AN_ISOLATION
    )
    assert not missing, f"Nutzerordner umgebogen, Schlüsselbund nicht: {missing}"
    assert set(writers) >= NOT_AN_ISOLATION, "eine Ausnahme ohne Fundstelle"


def test_the_scan_sees_an_isolation_without_the_keyring() -> None:
    """Gegenprobe: jede Bauart einer Umbiegung fällt ohne Schlüsselbund auf, mit ihm nicht."""
    planted = (
        "def a(p):\n    for v in PROFILE_VARIABLES:\n        os.environ[v] = p\n"
        "def b(p):\n    env = {}\n    env['APPDATA'] = p\n    return env\n"
        "def c(p):\n    os.environ.update(dict.fromkeys(PROFILE_VARIABLES, p))\n"
        'def d(p):\n    for n, c in (("APPDATA", "r"),):\n        os.environ[n] = c\n'
        "def e(p):\n    os.environ.update(ISOLATED_KEYRING)\n"
        "    for v in PROFILE_VARIABLES:\n        os.environ[v] = p\n"
        "def f():\n    return os.environ['APPDATA']\n"
    )
    assert profile_writers(planted) == [
        ("a", False),
        ("b", False),
        ("c", False),
        ("d", False),
        ("e", True),
    ]


def test_the_keyring_of_a_fresh_profile_has_one_source() -> None:
    """``app.core.paths`` trägt sie; kein Werkzeug führt eine eigene Fassung."""
    from app.core.paths import ISOLATED_KEYRING

    assert ISOLATED_KEYRING == {"PYTHON_KEYRING_BACKEND": "keyring.backends.null.Keyring"}
    own = [
        path.name
        for path in sorted((ROOT / "tools").glob("*.py"))
        if re.search(r"^ISOLATED_KEYRING\b", path.read_text(encoding="utf-8"), re.MULTILINE)
    ]
    assert own == []


@pytest.mark.parametrize("tool", ["check_print_equal", "registry_dump", "check_part_ranges"])
def test_a_tool_profile_hands_the_attrappe_to_its_children(
    tool: str, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Am Werkzeug: Nach der Umbiegung fragt ein Kind die Attrappe, danach gilt das Alte."""
    import importlib

    from app.core.paths import PROFILE_VARIABLES

    for name in PROFILE_VARIABLES:
        monkeypatch.setenv(name, str(tmp_path / "vorher"))
    monkeypatch.setenv("PYTHON_KEYRING_BACKEND", "keyring.backends.fail.Keyring")
    module = importlib.import_module(f"tools.{tool}")
    ask = "import keyring; t = type(keyring.get_keyring()); print(t.__module__ + '.' + t.__name__)"

    def chosen() -> str:
        return subprocess.run(
            [sys.executable, "-c", ask],
            capture_output=True,
            text=True,
            timeout=120,
            check=True,
            cwd=tmp_path,
        ).stdout.strip()

    if tool == "check_print_equal":
        module._isolated(str(tmp_path / "profil"))
        assert chosen() == "keyring.backends.null.Keyring"
        return
    bend = module._own_profile() if tool == "registry_dump" else module._isolate(tmp_path)
    with bend:
        assert chosen() == "keyring.backends.null.Keyring"
    assert os.environ["PYTHON_KEYRING_BACKEND"] == "keyring.backends.fail.Keyring"
