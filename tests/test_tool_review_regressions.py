"""Werkzeugregressionen an temporären Beständen, ohne echte Sperren oder Nutzerdaten."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from tools import affected_tests, gate_lock, link_memory, make_linux_packages


def test_b14_deleted_module_keeps_relative_and_indirect_importers(tmp_path: Path) -> None:
    """Die fehlende Datei bleibt ein Knoten des Importgraphen."""
    sources = {
        "app/__init__.py": "",
        "app/victim.py": "VALUE = 1\n",
        "app/bridge.py": "from . import victim\n",
        "tests/__init__.py": "",
        "tests/test_direct.py": "from app import victim\n",
        "tests/test_indirect.py": "from app import bridge\n",
        "tests/test_unrelated.py": "import math\n",
    }
    for relative, content in sources.items():
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    victim = tmp_path / "app/victim.py"
    before, _ = affected_tests.affected([victim], affected_tests.ImportGraph(tmp_path))
    victim.unlink()
    after, _ = affected_tests.affected([victim], affected_tests.ImportGraph(tmp_path))
    assert {path.name for path in before} == {"test_direct.py", "test_indirect.py"}
    assert after == before


def test_r17_a_young_unwritten_lock_is_busy_even_without_waiting(tmp_path: Path) -> None:
    """wait=0 beendet das Warten, nicht die Schonfrist eines fremden Schreibers."""
    path = tmp_path / "gate.lock"
    path.write_bytes(b"")
    foreign = gate_lock._acquire(path, "second", wait=0.0)
    assert foreign is not None
    assert path.read_bytes() == b""


def test_r17_a_lock_completed_between_read_and_stat_is_preserved(tmp_path, monkeypatch) -> None:
    """Ein zulässiges Interleaving darf den inzwischen gültigen Halter nicht ersetzen."""
    path = tmp_path / "gate.lock"
    path.write_bytes(b"")
    old = time.time() - 60.0
    os.utime(path, (old, old))
    owner = {"wer": "first", "pid": os.getpid(), "seit": time.time()}
    read = gate_lock._read

    def completed(target):
        result = read(target)
        if result is None:
            target.write_text(json.dumps(owner), encoding="utf-8")
        return result

    monkeypatch.setattr(gate_lock, "_read", completed)
    foreign = gate_lock._acquire(path, "second", wait=0.0)
    assert foreign == owner
    assert json.loads(path.read_text(encoding="utf-8")) == owner


def test_r17_two_concurrent_claims_have_exactly_one_owner(tmp_path) -> None:
    """Die Betriebssystemsperre schützt auch zwei gleichzeitig beginnende Schreiber."""
    path = tmp_path / "gate.lock"
    barrier = Barrier(2)

    def claim(name):
        barrier.wait(timeout=5)
        return name, gate_lock._acquire(path, name, wait=0.0)

    with ThreadPoolExecutor(max_workers=2) as executor:
        claims = list(executor.map(claim, ("first", "second")))
    owners = [name for name, foreign in claims if foreign is None]
    assert len(owners) == 1
    assert json.loads(path.read_text(encoding="utf-8"))["wer"] == owners[0]


def test_r19_existing_machine_backups_are_not_overwritten(tmp_path, monkeypatch) -> None:
    """Jede abweichende Fassung erhält einen freien, nachprüfbaren Ablageort."""
    local, shared = tmp_path / "local", tmp_path / "shared"
    local.mkdir()
    shared.mkdir()
    (local / "topic.md").write_text("aktuell lokal", encoding="utf-8")
    (shared / "topic.md").write_text("gemeinsam", encoding="utf-8")
    (shared / "topic.dieser-maschine.md").write_text("früher lokal", encoding="utf-8")
    (shared / "topic.dieser-maschine-2.md").write_text("noch eine Fassung", encoding="utf-8")
    monkeypatch.setattr(link_memory, "IN_REPO", shared)
    monkeypatch.setattr(link_memory, "harness_dir", lambda _: local)
    monkeypatch.setattr(link_memory, "link", lambda *_: None)
    assert link_memory.main([]) == 0
    assert not local.exists()
    assert {path.read_text(encoding="utf-8") for path in shared.iterdir()} == {
        "gemeinsam",
        "früher lokal",
        "noch eine Fassung",
        "aktuell lokal",
    }


@pytest.mark.parametrize(
    "part,encoded",
    [
        ("Person Mit Raum", "Person Mit Raum"),
        ("Nutz$er", "Nutz\\\\$er"),
        ("Nutz\\er", "Nutz\\\\\\\\er"),
        ('Nutz"er', 'Nutz\\\\"er'),
        ("Nutz`er", "Nutz\\\\`er"),
        ("Nutzer%f", "Nutzer%%f"),
    ],
)
def test_r24_generated_menu_entry_preserves_the_full_launcher_path(tmp_path, part, encoded) -> None:
    """Echte generierte Shellzeilen erfüllen beide Desktop-Entry-Escape-Ebenen."""
    bash = Path("C:/Program Files/Git/bin/bash.exe") if os.name == "nt" else shutil.which("sh")
    if not bash or not Path(bash).is_file():
        pytest.skip("POSIX shell unavailable")
    here, applications = tmp_path / "here", tmp_path / "applications"
    here.mkdir()
    applications.mkdir()
    (here / "fixture.desktop").write_text(
        "[Desktop Entry]\nType=Application\nExec=Solidon3D %f\n", encoding="utf-8"
    )
    source = make_linux_packages.install_script()
    snippet = source[source.index("LAUNCHER_PATH=$(") : source.index('cp "$HERE/icon.svg"')]
    script = tmp_path / "entry.sh"
    script.write_text(snippet, encoding="utf-8", newline="\n")
    environment = {
        **os.environ,
        "BIN_DIR": f"/home/{part}/.local/bin",
        "NAME": "Solidon3D",
        "HERE": here.as_posix(),
        "SHORT": "fixture",
        "APP_DIR": applications.as_posix(),
        "IDENTIFIER": "fixture",
    }
    completed = subprocess.run(
        [str(bash), str(script)],
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
    )
    assert completed.returncode == 0, completed.stderr
    entry = (applications / "fixture.desktop").read_text(encoding="utf-8")
    assert f'Exec="/home/{encoded}/.local/bin/Solidon3D" %f\n' in entry


@pytest.mark.parametrize(
    "part", ["Nutz$er", "Nutz`printf wrong`er", "Nutz'er", 'Nutz"er', "Nutz\\er"]
)
def test_r24_the_generated_shell_launcher_preserves_literal_target(tmp_path, part) -> None:
    """Der Menüeintrag erreicht einen Starter, der denselben literal gemeinten Pfad öffnet."""
    bash = Path("C:/Program Files/Git/bin/bash.exe") if os.name == "nt" else shutil.which("bash")
    if not bash or not Path(bash).is_file():
        pytest.skip("Bash unavailable")
    source = make_linux_packages.install_script()
    start = source.index("# Der Starter ist ein Skript")
    snippet = source[start : source.index("# Der Menüeintrag nennt", start)]
    script = tmp_path / "starter.sh"
    script.write_text(snippet, encoding="utf-8", newline="\n")
    environment = {
        **os.environ,
        "TARGET": f"/home/{part}/solidon3d",
        "BIN_DIR": tmp_path.as_posix(),
        "NAME": "Solidon3D",
        "SHORT": "solidon3d",
    }
    completed = subprocess.run(
        [str(bash), str(script)],
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
    )
    assert completed.returncode == 0, completed.stderr
    # Ein eigener Ersatz für exec protokolliert das Argument, ohne irgendein
    # Programm unter dem absichtlich ungewöhnlichen Zielpfad auszuführen.
    observed = subprocess.run(
        [
            str(bash),
            "-c",
            'exec() { printf "%s\\n" "$@"; }; . "$1"',
            "probe",
            str(tmp_path / "Solidon3D"),
        ],
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
    )
    assert observed.returncode == 0, observed.stderr
    assert observed.stdout.splitlines()[0] == f"/home/{part}/solidon3d/Solidon3D"


def test_r24_uninstall_paths_are_literal_saved_values(tmp_path) -> None:
    """Nur der erzeugte Variablenkopf läuft; keine Löschung oder Desktop-Aktion."""
    bash = Path("C:/Program Files/Git/bin/bash.exe") if os.name == "nt" else shutil.which("bash")
    if not bash or not Path(bash).is_file():
        pytest.skip("Bash unavailable")
    source = make_linux_packages.install_script()
    function = source[source.index("quote_value() {") : source.index("TARGET_QUOTED=$(")]
    start = source.index("{\n  printf '#!/bin/sh")
    end = source.index('chmod 755 "$TARGET/uninstall.sh"', start)
    script = tmp_path / "make-uninstall.sh"
    script.write_text(function + source[start:end], encoding="utf-8", newline="\n")
    literal = "/home/Nutz$er`printf wrong`mit\"Zitat'und\\Strich"
    environment = {
        **os.environ,
        "TARGET": tmp_path.as_posix(),
        "NAME": "Solidon3D",
        "SHORT": "solidon3d",
        "IDENTIFIER": "org.solidon3d.Solidon3D",
    }
    environment.update(
        {
            name: literal + "/" + name
            for name in ("BIN_DIR", "APP_DIR", "ICON_DIR", "META_DIR", "MIME_DIR")
        }
    )
    completed = subprocess.run(
        [str(bash), str(script)],
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
    )
    assert completed.returncode == 0, completed.stderr
    generated = (tmp_path / "uninstall.sh").read_text(encoding="utf-8")
    header = generated[: generated.index("set -eu")]
    header += 'printf "%s\\n" "$BIN_DIR" "$APP_DIR" "$ICON_DIR" "$META_DIR" "$MIME_DIR"\n'
    script.write_text(header, encoding="utf-8", newline="\n")
    observed = subprocess.run(
        [str(bash), str(script)], capture_output=True, text=True, encoding="utf-8", timeout=20
    )
    assert observed.returncode == 0, observed.stderr
    assert observed.stdout.splitlines() == [
        environment[name] for name in ("BIN_DIR", "APP_DIR", "ICON_DIR", "META_DIR", "MIME_DIR")
    ]
