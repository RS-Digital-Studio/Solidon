"""Die gemeinsamen Projekt-Hooks funktionieren auch unter Codex."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HOOK = ROOT / ".claude" / "hooks" / "solidon3d_hooks.py"
CODEX_HOOKS = ROOT / ".codex" / "hooks.json"


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
