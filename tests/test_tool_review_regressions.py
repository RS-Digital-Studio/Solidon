"""Werkzeugregressionen an temporären Beständen, ohne echte Sperren oder Nutzerdaten."""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

from tools import affected_tests, link_memory, make_linux_packages


def _bash_executable() -> Path | None:
    """Findet Bash im Suchpfad oder relativ zur tatsächlich installierten Git-Ausgabe."""
    executable = shutil.which("bash")
    if executable and "system32" not in Path(executable).parts[-2].lower():
        return Path(executable)
    git = shutil.which("git")
    roots = [Path(git).parent.parent] if git else []
    for variable, suffix in (("ProgramFiles", "Git"), ("LOCALAPPDATA", "Programs/Git")):
        value = os.environ.get(variable)
        if value:
            roots.append(Path(value) / suffix)
    return next(
        (root / "bin" / "bash.exe" for root in roots if (root / "bin" / "bash.exe").is_file()),
        None,
    )


def test_bash_is_found_beside_a_custom_git_installation(tmp_path, monkeypatch) -> None:
    """Eine Git-Installation außerhalb des Standardlaufwerks bleibt benutzbar."""
    root = tmp_path / "Meine Werkzeuge" / "Git"
    executable = root / "bin" / "bash.exe"
    executable.parent.mkdir(parents=True)
    executable.touch()
    monkeypatch.setattr(
        shutil, "which", lambda name: str(root / "cmd" / "git.exe") if name == "git" else None
    )
    assert _bash_executable() == executable


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
    bash = _bash_executable()
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
    bash = _bash_executable()
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
    bash = _bash_executable()
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
