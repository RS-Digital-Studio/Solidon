"""Die Fallgrenze beendet auch Launcher und Helfer vor dem nächsten Fall."""

from __future__ import annotations

import csv
import json
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.core.process import process_group_options, terminate_process_tree
from tools import file_acceptance as acceptance

HELPER = """import json, os, subprocess, sys, time
from pathlib import Path
out = Path(sys.argv[sys.argv.index('--out') + 1])
stop = out / 'stop'
deadline = time.monotonic() + 20
if '--leaf' in sys.argv:
    (out / 'leaf.json').write_text(json.dumps({'pid': os.getpid()}))
    while not stop.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
else:
    child = subprocess.Popen([sys.executable, __file__, '--out', str(out), '--leaf'],
                             creationflags=subprocess.CREATE_NO_WINDOW)
    while not (out / 'leaf.json').exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    data = json.loads((out / 'leaf.json').read_text())
    data.update(parent=os.getpid(), launcher=child.pid, profiles={
        key: os.environ.get(key) for key in ('APPDATA', 'LOCALAPPDATA',
        'XDG_CONFIG_HOME', 'XDG_DATA_HOME', 'XDG_STATE_HOME', 'XDG_CACHE_HOME')})
    print('echte Standardausgabe', flush=True)
    print('echte Fehlerausgabe', file=sys.stderr, flush=True)
    (out / 'ready.json').write_text(json.dumps(data))
    mode = os.environ['FD59_MODE']
    if mode in ('normal', 'nonzero'):
        stop.touch()
    while not stop.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    stop.touch()
    child.wait(timeout=10)
    sys.exit(7 if mode == 'nonzero' else 0)
"""


def alive(pid: int) -> bool:
    """Liest genau die eigene PID aus der öffentlichen Windows-Prozessliste."""
    output = subprocess.check_output(
        ["tasklist.exe", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
        text=True,
        encoding="oem",
        creationflags=subprocess.CREATE_NO_WINDOW,
        timeout=10,
    )
    return any(len(row) > 1 and row[1] == str(pid) for row in csv.reader(output.splitlines()))


@pytest.mark.skipif(sys.platform != "win32", reason="Echte Windows-Launcher-/Interpreterkette")
@pytest.mark.parametrize("mode", ["normal", "nonzero", "timeout", "exception"])
def test_real_case_process_tree(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, mode: str) -> None:
    script = tmp_path / "helper.py"
    script.write_text(HELPER, encoding="utf-8")
    monkeypatch.setattr(sys, "path", [str(tmp_path), *sys.path])
    monkeypatch.setattr(acceptance, "__file__", str(script))
    monkeypatch.setattr(acceptance, "read_cases", lambda _out: [acceptance.Case(1, "Fall", "", "")])
    monkeypatch.setattr(acceptance, "summary", lambda *_args: {})
    monkeypatch.setenv("FD59_MODE", mode)
    expected_profiles = {}
    for key in (
        "APPDATA",
        "LOCALAPPDATA",
        "XDG_CONFIG_HOME",
        "XDG_DATA_HOME",
        "XDG_STATE_HOME",
        "XDG_CACHE_HOME",
    ):
        expected_profiles[key] = str(tmp_path / key)
        monkeypatch.setenv(key, expected_profiles[key])
    children: list[subprocess.Popen[Any]] = []
    options: list[dict[str, Any]] = []

    def start(*args: Any, **kwargs: Any) -> subprocess.Popen[Any]:
        options.append(dict(kwargs))
        # Auch die rote Gegenprobe darf keine neue Konsole öffnen.
        kwargs["creationflags"] = kwargs.get("creationflags", 0) | subprocess.CREATE_NO_WINDOW
        child = subprocess.Popen(*args, **kwargs)
        children.append(child)
        if mode == "exception":
            wait = child.wait
            first = True

            def interrupted(timeout: float | None = None) -> int:
                nonlocal first
                if first:
                    first = False
                    raise RuntimeError("Warteaufruf unterbrochen")
                return wait(timeout=timeout)

            child.wait = interrupted  # type: ignore[method-assign]
        return child

    monkeypatch.setattr(
        acceptance,
        "subprocess",
        SimpleNamespace(
            Popen=start,
            TimeoutExpired=subprocess.TimeoutExpired,
        ),
    )

    def deadline(_case: acceptance.Case, _timeout: float) -> float:
        until = time.monotonic() + 10
        while not (tmp_path / "ready.json").exists() and time.monotonic() < until:
            time.sleep(0.01)
        assert (tmp_path / "ready.json").is_file(), "Helferkette nicht bereit"
        return 0.05 if mode == "timeout" else 10

    monkeypatch.setattr(acceptance, "case_timeout", deadline)
    data: dict[str, Any] = {}
    try:
        if mode == "exception":
            with pytest.raises(RuntimeError, match="Warteaufruf unterbrochen"):
                acceptance.run(tmp_path, 1, 1, False, 10)
        else:
            code = acceptance.run(tmp_path, 1, 1, False, 10)
            assert code == (0 if mode == "normal" else 1)
        data = json.loads((tmp_path / "ready.json").read_text())
        assert sys.path[0] == str(acceptance.ROOT)
        assert data["profiles"] == expected_profiles
        assert not alive(data["pid"]), f"Helfer {data['pid']} lebt nach {mode} weiter"
        assert all(not alive(pid) for pid in {data["parent"], data["launcher"], children[0].pid})
        folder = tmp_path / "cases" / "001"
        assert "echte Standardausgabe" in (folder / "stdout.log").read_text(encoding="utf-8")
        assert "echte Fehlerausgabe" in (folder / "stderr.log").read_text(encoding="utf-8")
        assert options[0]["cwd"] == acceptance.ROOT
        for name, value in process_group_options(no_window=True).items():
            assert options[0][name] == value
        if mode != "exception":
            status = json.loads((folder / "process.json").read_text())
            assert status["timeout"] is (mode == "timeout")
            assert status["pid"] == children[0].pid
            assert status["exit_code"] == children[0].returncode
            assert status["wall_s"] > 0
            assert not acceptance.resumes(acceptance.Case(1, "Fall", "", ""), status)
            language = acceptance.Case(1, "Sprache", "", "", kind="language")
            assert acceptance.resumes(language, status) is (mode != "normal")
    finally:
        (tmp_path / "stop").touch()
        for child in children:
            if child.poll() is None:
                terminate_process_tree(child)
        if data:
            until = time.monotonic() + 5
            while alive(data["pid"]) and time.monotonic() < until:
                time.sleep(0.05)
            assert not alive(data["pid"]), "Eigener Helfer nach Gegenprobe nicht beendet"
