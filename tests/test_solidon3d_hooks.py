"""Die gemeinsamen Projekt-Hooks funktionieren auch unter Codex."""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude" / "hooks" / "solidon3d_hooks.py"
CODEX_HOOKS = ROOT / ".codex" / "hooks.json"


@pytest.fixture
def hook(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> ModuleType:
    """Jeder Protokolltest bekommt eigene Dateien und Sitzungsmarken."""
    spec = importlib.util.spec_from_file_location("solidon_hooks_under_test", HOOK)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(module, "WURZEL", tmp_path)
    monkeypatch.setattr(module, "MARKE", tmp_path / "state" / "last-test")
    monkeypatch.setattr(module, "ERINNERT", tmp_path / "state" / "last-reminder")
    monkeypatch.setattr(module, "SESSION_START", tmp_path / "state" / "started")
    return module


def test_codex_destructive_command_is_denied_without_internal_environment() -> None:
    """Die Codex-Kennung muss den unterstützten blockierenden Ausgang wählen."""
    environment = os.environ.copy()
    environment.pop("CODEX_THREAD_ID", None)
    environment.pop("CODEX_SESSION_ID", None)
    payload = {
        "session_id": "test-session",
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": "git reset --hard HEAD"},
    }

    result = subprocess.run(
        [sys.executable, str(HOOK), "vor-bash", "--codex"],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=10,
        cwd=ROOT,
        env=environment,
    )

    assert result.returncode == 0
    output = json.loads(result.stdout)
    specific = output["hookSpecificOutput"]
    assert specific["hookEventName"] == "PreToolUse"
    assert specific["permissionDecision"] == "deny"
    assert specific["permissionDecisionReason"]


def test_every_codex_hook_command_sets_explicit_codex_argument() -> None:
    """Jeder Codex-Einstieg muss den gemeinsamen Hook eindeutig kennzeichnen."""
    configuration = json.loads(CODEX_HOOKS.read_text(encoding="utf-8"))

    commands = [
        handler[field]
        for groups in configuration["hooks"].values()
        for group in groups
        for handler in group["hooks"]
        for field in ("command", "commandWindows")
    ]

    assert commands
    assert all(" --codex" in command for command in commands)


def test_session_end_releases_the_area_on_the_board(tmp_path: Path) -> None:
    """Endet die Sitzung, hält sie kein Gebiet mehr fest.

    Der Lauf bekommt ein eigenes Git-Verzeichnis: Das Brett liegt im
    gemeinsamen Git-Verzeichnis, und ein Test, der das echte anfasst, würde
    den Eintrag einer gerade arbeitenden Nachbarsitzung löschen.
    """
    subprocess.run(["git", "init", "--quiet"], cwd=tmp_path, check=True, capture_output=True)
    board = tmp_path / ".git" / "solidon-sitzungen"
    environment = os.environ.copy()
    environment["CLAUDE_PID"] = "424242"
    environment.pop("CLAUDE_CODE_MESSAGING_SOCKET", None)
    environment.pop("CODEX_THREAD_ID", None)
    environment.pop("CODEX_SESSION_ID", None)

    claimed = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "session_board.py"), "claim", "--area", "Probe"],
        capture_output=True,
        text=True,
        timeout=30,
        cwd=tmp_path,
        env=environment,
    )
    assert claimed.returncode == 0, claimed.stderr
    assert list(board.glob("*.json")), "the claim did not reach the temporary board"

    ended = subprocess.run(
        [sys.executable, str(HOOK), "sitzungsende"],
        input='{"hook_event_name": "SessionEnd"}',
        capture_output=True,
        text=True,
        timeout=30,
        cwd=tmp_path,
        env=environment,
    )

    assert ended.returncode == 0, ended.stderr
    assert not list(board.glob("*.json")), "the area is still held after the session ended"


def test_session_start_calls_current_environment_checker(hook: ModuleType, tmp_path: Path) -> None:
    """Der Start ruft die öffentliche Prüffunktion wirklich auf, kein veraltetes Alias."""
    package = tmp_path / "tools"
    package.mkdir()
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "check_env.py").write_text(
        'def check():\n    return ["Probe-Abweichung"], ["Probe-Abhilfe"]\n', encoding="utf-8"
    )

    note = hook.umgebungshinweis()

    assert "Probe-Abweichung" in note
    assert "Probe-Abhilfe" in note


def test_environment_timeout_is_bounded_and_visible(
    hook: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein langsamer Prüfer verschluckt nicht die gesamte SessionStart-Antwort."""

    def timed_out(command: list[str], **kwargs: object) -> None:
        assert 0 < kwargs["timeout"] < 25
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(hook.subprocess, "run", timed_out)
    assert "python tools/check_env.py" in hook.umgebungshinweis()


def test_patch_move_is_checked_at_the_payload_working_directory(
    hook: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Umbenannte Dateien und Unterverzeichnisse erreichen dieselbe Prüfung wie Edit."""
    folder = tmp_path / "unterordner"
    folder.mkdir()
    moved = folder / "änderung.py"
    moved.write_text("answer=42\n", encoding="utf-8")
    wrong = tmp_path / moved.name
    wrong.write_text("answer=13\n", encoding="utf-8")
    checked = []
    monkeypatch.setattr(
        hook,
        "eingabe",
        lambda: {
            "cwd": str(folder),
            "tool_name": "apply_patch",
            "tool_input": {
                "command": "*** Begin Patch\n*** Update File: old.py\n*** Move to: änderung.py\n"
                "@@\n-answer=1\n+answer=42\n*** End Patch"
            },
            "tool_response": "Success. Updated the following files:\nM änderung.py\n",
        },
    )
    monkeypatch.setattr(hook, "_check_changed_file", lambda path: checked.append(path) or [])

    hook.nach_aenderung()

    assert checked == [moved]


@pytest.mark.parametrize(
    "response", [None, "apply_patch verification failed: missing context", {"isError": True}]
)
def test_failed_patch_does_not_format_existing_files(
    hook: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, response: object
) -> None:
    """Der Inhalt einer erfolglos adressierten Datei gehört weiterhin seinem Urheber."""
    path = tmp_path / "existing.py"
    path.write_text("answer=42\n", encoding="utf-8")
    monkeypatch.setattr(
        hook,
        "eingabe",
        lambda: {
            "tool_name": "apply_patch",
            "tool_input": {"command": "*** Update File: existing.py"},
            "tool_response": response,
        },
    )
    monkeypatch.setattr(
        hook, "_check_changed_file", lambda path: pytest.fail("formatted failed patch")
    )

    hook.nach_aenderung()


@pytest.mark.parametrize(
    ("command", "expected"),
    [
        ("python -m pytest tests/test_example.py -q", True),
        ("& '.venv\\Scripts\\python.exe' -m pytest -q", True),
        (".venv/Scripts/python.exe tools/affected_tests.py --run", True),
        ("bash .claude/.state/oberflaechen-durchsicht-2026-08-19/suite-getrennt.sh", True),
        ("echo pytest", False),
        ("echo -m pytest", False),
        ("echo tools/affected_tests.py --run", False),
        ('S=test; "$SUITE_PYTHON" tools/affected_tests.py tests/test_agent_mirror.py --run', True),
        ('"$SUITE_PYTHON" -m pytest -q', True),
        ('"${SUITE_PYTHON}" -u -m pytest -q', True),
        ("& $env:SUITE_PYTHON -m pytest -q", True),
        ('S="name with space" "$SUITE_PYTHON" -m pytest -q', True),
        ('bash -lc "python -m pytest -q"', True),
        (r"""& 'C:\Program Files\Git\bin\bash.exe' -lc '"$SUITE_PYTHON" -m pytest -q' """, True),
        ("""powershell.exe -NoProfile -Command '& "$env:SUITE_PYTHON" -m pytest -q' """, True),
        (
            """S="session"\nexport S SUITE_PYTHON\n"$SUITE_PYTHON" tools/gate_lock.py run """
            """--who "$S" --wait 1800 -- bash -c '\n"""
            """  .claude/.state/oberflaechen-durchsicht-2026-08-19/suite-getrennt.sh """
            """> "$TEMP/g4-$S.txt" 2>&1\n"""
            """  suite_status=$?\n  echo "geteilt Exit=$suite_status"\n"""
            """  "$SUITE_PYTHON" -m pytest -q -m performance > "$TEMP/g5-$S.txt" 2>&1\n' """,
            True,
        ),
        ('S=test; "$SUITE_PYTHON" -m pytest -q > "$TEMP/t-$S.txt" 2>&1; echo "Exit=$?"', True),
        ('S=test; echo "python -m pytest -q"', False),
        ('bash -lc "echo pytest"', False),
        ("""bash -lc 'echo "python -m pytest -q"' """, False),
        ("""bash -lc '"$SUITE_PYTHON" -m pytest --collect-only -q' """, False),
        ('"$SUITE_PYTHON" -m pytest --help', False),
        ('"$SUITE_PYTHON" tools/affected_tests.py --why', False),
        ("python -c \"print('pytest')\"", False),
        ("python -m ruff check pytest.py", False),
        ('echo "python -m pytest -q"', False),
        ("python -m pytest --collect-only -q", False),
        ("python -m pytest --help", False),
        ("python tools/affected_tests.py --why", False),
    ],
)
def test_test_marker_requires_a_test_invocation(
    hook: ModuleType, command: str, expected: bool
) -> None:
    """Dokumentations- und Sammlungsbefehle machen den Prüfhinweis nicht stumm."""
    assert hook._test_command(command) is expected


def test_test_markers_belong_to_one_session(
    hook: ModuleType, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein fremder Testlauf darf die eigene Erinnerung nicht quittieren."""
    data = {
        "session_id": "one",
        "tool_input": {"command": "python -m pytest -q"},
        "tool_response": {"exit_code": 1},
    }
    monkeypatch.setattr(hook, "eingabe", lambda: data)
    monkeypatch.setattr(hook, "_ruff_hinweis", lambda command: "")
    monkeypatch.setattr(hook, "_commit_hinweis", lambda command: "")
    hook.testlauf()
    assert not hook._session_path(hook.MARKE, data).exists()
    data["tool_response"] = {"exit_code": 0}
    hook.testlauf()
    assert hook._session_path(hook.MARKE, data).exists()
    assert not hook._session_path(hook.MARKE, {"session_id": "two"}).exists()


def test_stop_warns_again_after_the_same_file_changes(
    hook: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Die unterstützte Stop-Warnung unterscheidet neue Änderungen vom alten Hinweis."""
    (tmp_path / "tools").mkdir()
    path = tmp_path / "tools" / "example.py"
    path.write_text("value = 1\n", encoding="utf-8")
    monkeypatch.setattr(hook, "eingabe", lambda: {"session_id": "one"})
    hook.abschluss()
    first = json.loads(capsys.readouterr().out)
    assert "systemMessage" in first and "hookSpecificOutput" not in first
    hook.abschluss()
    assert not capsys.readouterr().out
    os.utime(path, (path.stat().st_atime, path.stat().st_mtime + 1))
    hook.abschluss()
    assert "systemMessage" in json.loads(capsys.readouterr().out)


def test_codex_session_end_uses_payload_identity_in_a_worktree(
    hook: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Das dokumentierte session_id-Feld gibt nur das eigene gemeinsame Brett frei."""
    common = tmp_path / "main" / ".git"
    internal = common / "worktrees" / "test"
    internal.mkdir(parents=True)
    (internal / "commondir").write_text("../..", encoding="utf-8")
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    (worktree / ".git").write_text(f"gitdir: {internal}", encoding="utf-8")
    board = common / "solidon-sitzungen"
    board.mkdir()
    mine = board / "codex-payload-session.json"
    other = board / "codex-inherited-session.json"
    mine.write_text("{}", encoding="utf-8")
    other.write_text("{}", encoding="utf-8")
    monkeypatch.setenv("CODEX_THREAD_ID", "inherited-session")
    monkeypatch.setattr(hook, "is_codex", lambda: True)
    monkeypatch.setattr(
        hook, "eingabe", lambda: {"cwd": str(worktree), "session_id": "payload-session"}
    )
    monkeypatch.setattr(
        hook.subprocess, "run", lambda *args, **kwargs: pytest.fail("SessionEnd starts Git")
    )

    hook.sitzungsende()

    assert not mine.exists()
    assert other.exists()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows-Einstieg über cmd und py")
def test_windows_session_end_wrapper_preserves_payload_and_exit_code(tmp_path: Path) -> None:
    """Der konfigurierte Einstieg läuft aus einem Unterordner und übergibt UTF-8."""
    configuration = json.loads(CODEX_HOOKS.read_text(encoding="utf-8"))
    command = configuration["hooks"]["SessionEnd"][0]["hooks"][0]["commandWindows"]
    copied_hook = tmp_path / ".claude" / "hooks" / HOOK.name
    copied_hook.parent.mkdir(parents=True)
    shutil.copyfile(HOOK, copied_hook)
    board = tmp_path / ".git" / "solidon-sitzungen"
    board.mkdir(parents=True)
    claim = board / "codex-session-ä.json"
    claim.write_text("{}", encoding="utf-8")
    subfolder = tmp_path / "unterordner"
    subfolder.mkdir()
    payload = {"session_id": "session-ä", "cwd": str(subfolder), "hook_event_name": "SessionEnd"}

    result = subprocess.run(
        'cmd.exe /d /s /c "' + command + '"',
        input=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        capture_output=True,
        cwd=subfolder,
        timeout=20,
    )

    assert result.returncode == 0, result.stderr
    assert not claim.exists()
    assert not result.stdout
    # Ein Fehler des gestarteten Skripts muss den Wrapper unverändert verlassen.
    copied_hook.write_text("raise SystemExit(7)\n", encoding="utf-8")
    failed = subprocess.run(
        'cmd.exe /d /s /c "' + command + '"',
        input=b"{}",
        capture_output=True,
        cwd=subfolder,
        timeout=20,
    )
    assert failed.returncode == 7
