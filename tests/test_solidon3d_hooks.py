"""Die gemeinsamen Projekt-Hooks funktionieren auch unter Codex."""

from __future__ import annotations

import fnmatch
import importlib.util
import json
import os
import re
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
        ('"$SUITE_PYTHON" -m pytest -q > "$TEMP/t.txt" 2>&1; echo "Exit=$?"', True),
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


CLAUDE_SETTINGS = ROOT / ".claude" / "settings.json"

#: Befehle, auf die `vor-bash` oder `testlauf` reagieren müssen — samt
#: Tabulator und Zeilenumbruch, die im JSON als Escape-Folge ankommen.
REACTING_COMMANDS = [
    "git reset --hard HEAD",
    "git checkout -- app/core/units.py",
    "git checkout .",
    "git\tcheckout HEAD",
    "git\nrestore app/x.py",
    "git clean -fd",
    "git push origin main --force",
    "git push -f origin main",
    "git checkout main -- app/x.py",
    "git switch --discard-changes main",
    "git stash drop",
    "git branch -D feature",
    "git pull --rebase",
    "git worktree remove --force ../x",
    'git -C "F:/3D Druck" restore app/x.py',
    "git filter-repo --path x",
    "python -m pytest tests/test_example.py -q",
    "& '.venv\\Scripts\\python.exe' -m pytest -q",
    ".venv/Scripts/python.exe tools/affected_tests.py --run",
    "bash .claude/.state/oberflaechen-durchsicht-2026-08-19/suite-getrennt.sh",
    'bash -lc "py.test -q"',
    "python - <<'PY'\nPath('a.py').write_text('x')\nPY",
    "handle.writelines(lines)",
    "sed  -i 's/a/b/' app/x.py",
    "echo x >app/x.py",
    "cat a | tee app/b.py",
    "python -m ruff format app/x.py",
]


def _claude_filter(event: str, group: int) -> list[list[str]]:
    """Die `case`-Muster vor einem Claude-Hook: alle Gruppen müssen treffen."""
    handlers = json.loads(CLAUDE_SETTINGS.read_text(encoding="utf-8"))["hooks"][event]
    command = handlers[group]["hooks"][0]["command"]
    groups = re.findall(r'case "\$in" in (.*?)\) ;;', command)
    return [[pattern.replace("'", "") for pattern in found.split("|")] for found in groups]


def _passes(patterns: list[list[str]], command: str) -> bool:
    """Wie die Shell die Nutzlast gegen die Muster hält — nach JSON-Kodierung."""
    payload = json.dumps(
        {"session_id": "s", "tool_input": {"command": command}},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return all(any(fnmatch.fnmatchcase(payload, p) for p in group) for group in patterns)


@pytest.mark.parametrize(("event", "group"), [("PreToolUse", 0), ("PostToolUse", 1)])
def test_shell_prefilter_never_hides_a_command_the_hook_reacts_to(
    hook: ModuleType, event: str, group: int
) -> None:
    """Der Vorfilter in `.claude/settings.json` spart den Python-Start, nie eine Meldung.

    Er ist eine Obermenge der Auslöser im Skript. Wer `VERWIRFT`,
    `SCHREIBT_DATEI` oder `_test_command` erweitert, zieht die Muster nach —
    sonst schweigt der Hook genau bei dem neuen Befehl.
    """
    patterns = _claude_filter(event, group)
    assert patterns, "kein Vorfilter gefunden"
    if event == "PreToolUse":
        reacting = [c for c in REACTING_COMMANDS if hook.VERWIRFT.search(c)]
    else:
        reacting = [
            c for c in REACTING_COMMANDS if hook._test_command(c) or hook.SCHREIBT_DATEI.search(c)
        ]
    assert len(reacting) >= 5, "zu wenige Beispiele, die der Hook meldet"
    assert [c for c in reacting if not _passes(patterns, c)] == []
    assert not _passes(patterns, "ls -la"), "der Vorfilter lässt alles durch"


@pytest.mark.parametrize(
    ("command", "discards"),
    [
        ("git reset --hard HEAD", True),
        ("git -C x reset --hard", True),
        ('git -C "F:/3D Druck" restore app/x.py', True),
        ("git -c core.quotepath=off checkout -- .", True),
        ("git checkout -f main", True),
        ("git checkout origin/main -- .", True),
        ("git switch --discard-changes main", True),
        ("git clean -df", True),
        ("git clean --force -d", True),
        ("git push -f origin main", True),
        ("git push origin +main", True),
        ("git stash clear", True),
        ("git branch -D feature", True),
        ("git rebase main", True),
        ("git pull origin main --rebase", True),
        ("git worktree remove --force ../x", True),
        ("git filter-branch --tree-filter x", True),
        ("git checkout -b feature", False),
        ("git checkout main", False),
        ("git switch -c neu", False),
        ("git push origin main", False),
        ("git push --force-with-lease", False),
        ("git stash", False),
        ("git branch -d erledigt", False),
        ("git worktree remove ../x", False),
        ("git clean -n", False),
        ("git reset -q -- .claude/memory", False),
        ("git pull", False),
    ],
)
def test_revert_guard_catches_every_discarding_form(
    hook: ModuleType, command: str, discards: bool
) -> None:
    """Der Schutz fragt vor allem, was Arbeit verwirft oder Geschichte umschreibt.

    `git -C <pfad> …` ist mit mehreren Worktrees die übliche Form und ging
    anfangs durch, ebenso `push -f`, `checkout <rev> -- <pfad>`, `rebase` und
    `branch -D`. Ein Zweigwechsel, ein gewöhnlicher Push oder ein
    Zurücknehmen der Vormerkung verwirft nichts und fragt nicht.
    """
    assert bool(hook.VERWIRFT.search(command)) is discards


def test_write_prefilter_lets_python_and_memory_through() -> None:
    """Der Vorfilter vor `nach-aenderung` spart den Python-Start bei Markdown und Co."""
    patterns = _claude_filter("PostToolUse", 0)
    assert patterns, "kein Vorfilter gefunden"

    def passes(path: str) -> bool:
        payload = json.dumps({"tool_input": {"file_path": path, "content": "x"}})
        return all(any(fnmatch.fnmatchcase(payload, p) for p in group) for group in patterns)

    assert passes("F:\\3D Druck\\app\\core\\units.py")
    assert passes("C:\\Users\\r\\.claude\\projects\\F--3D-Druck\\memory\\neu.md")
    assert not passes("F:\\3D Druck\\ROADMAP.md"), "der Vorfilter lässt alles durch"


def _memory(root: Path) -> Path:
    folder = root / ".claude" / "memory"
    folder.mkdir(parents=True)
    for name, description in (
        ("testlaeufe-messen", "Exit-Code, Pipe und Fortschrittszeichen beim Testlauf lesen"),
        ("git-im-geteilten-baum", "Commit, Index und Worktrees mit mehreren Sitzungen"),
    ):
        (folder / f"{name}.md").write_text(
            f"---\nname: {name}\ndescription: {description}\n---\n", encoding="utf-8"
        )
    (folder / "MEMORY.md").write_text(
        "- [Testläufe](testlaeufe-messen.md)\n- [Git](git-im-geteilten-baum.md)\n",
        encoding="utf-8",
    )
    return folder


def test_a_new_memory_file_is_pointed_at_the_nearest_topic(
    hook: ModuleType, tmp_path: Path
) -> None:
    """Erinnerungen sind Themendateien: Eine neue Datei bekommt ihr Thema genannt."""
    folder = _memory(tmp_path)
    new = folder / "exit-code-hinter-tail.md"
    new.write_text(
        "---\nname: exit-code-hinter-tail\ndescription: Der Exit-Code hinter einer Pipe "
        "gehört tail, nicht dem Testlauf\n---\n",
        encoding="utf-8",
    )

    note = hook.themenhinweis({"tool_input": {"file_path": str(new)}})

    assert "`exit-code-hinter-tail.md`" in note
    assert "testlaeufe-messen.md" in note, "das Thema mit gemeinsamen Stichwörtern wird genannt"
    assert "git-im-geteilten-baum.md" not in note, "ohne gemeinsames Stichwort kein Vorschlag"


def test_extending_a_known_topic_stays_silent(hook: ModuleType, tmp_path: Path) -> None:
    """Wer eine Datei ergänzt, die der Index schon nennt, bekommt keinen Hinweis."""
    folder = _memory(tmp_path)
    known = folder / "testlaeufe-messen.md"
    assert hook.themenhinweis({"tool_input": {"file_path": str(known)}}) == ""
    readme = tmp_path / "README.md"
    readme.write_text("x", encoding="utf-8")
    assert hook.themenhinweis({"tool_input": {"file_path": str(readme)}}) == ""


def test_session_start_says_nothing_when_nothing_deviates(
    hook: ModuleType,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Was CLAUDE.md und AGENTS.md sagen, sagt der Start nicht noch einmal.

    Alte Sitzungsmarken räumt er dabei weg, junge bleiben.
    """
    _memory(tmp_path)
    monkeypatch.setattr(hook, "eingabe", lambda: {"session_id": "neu"})
    monkeypatch.setattr(hook, "umgebungshinweis", lambda: "")
    state = tmp_path / "state"
    state.mkdir()
    old, young = state / "last-test-alt", state / "started-jung"
    for marker in (old, young):
        marker.write_text("0", encoding="utf-8")
    month_ago = old.stat().st_mtime - 30 * 86400
    os.utime(old, (month_ago, month_ago))

    hook.sitzungsstart()

    assert capsys.readouterr().out == ""
    assert not old.exists() and young.exists()


def test_session_start_restores_memories_a_pull_removed(
    hook: ModuleType, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Fehlt `MEMORY.md`, ruft der Start die Wiederherstellung und nennt ihr Ergebnis."""
    calls: list[list[str]] = []

    def restored(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        return subprocess.CompletedProcess(command, 0, "Zurückgeholt: 5 Dateien.\n", "")

    monkeypatch.setattr(hook.subprocess, "run", restored)
    assert hook.erinnerungshinweis().strip() == "Zurückgeholt: 5 Dateien."
    assert calls and calls[0][-1] == "--wiederherstellen"
    _memory(tmp_path)
    assert hook.erinnerungshinweis() == "", "mit Index gibt es nichts zu tun"


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
