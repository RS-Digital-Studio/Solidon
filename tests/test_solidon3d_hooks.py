"""Die gemeinsamen Projekt-Hooks funktionieren auch unter Codex."""

from __future__ import annotations

import fnmatch
import importlib.util
import json
import os
import re
import shlex
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
        ("bash .claude/scripts/suite-getrennt.sh", True),
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
    '"F:/3D Druck/.venv/Scripts/python.exe" tools/upload_website.py',
    '"$SUITE_PYTHON" tools/run_agent_suite.py',
    ".venv/Scripts/python.exe -m tools.deploy_activation_server",
    "./tools/sign_release.py",
    "& $env:SUITE_PYTHON tools\\check_support.py",
    "cd tools && python make_licence_keys.py",
    "python -m pytest tests/test_example.py -q",
    "& '.venv\\Scripts\\python.exe' -m pytest -q",
    ".venv/Scripts/python.exe tools/affected_tests.py --run",
    "bash .claude/scripts/suite-getrennt.sh",
    'bash -lc "py.test -q"',
    "python - <<'PY'\nPath('a.py').write_text('x')\nPY",
    "handle.writelines(lines)",
    "sed  -i 's/a/b/' app/x.py",
    "echo x >app/x.py",
    "cat a | tee app/b.py",
    "python -m ruff format app/x.py",
]


def _claude_filter(event: str, group: int) -> tuple[list[list[str]], bool]:
    """Die `case`-Muster vor einem Claude-Hook: alle Gruppen müssen treffen."""
    handlers = json.loads(CLAUDE_SETTINGS.read_text(encoding="utf-8"))["hooks"][event]
    command = handlers[group]["hooks"][0]["command"]
    groups = re.findall(r'case "\$in" in (.*?)\) ;;', command)
    patterns = [[pattern.replace("'", "") for pattern in found.split("|")] for found in groups]
    return patterns, "shopt -s nocasematch;" in command.partition('case "$in" in ')[0]


def _passes(patterns: list[list[str]], command: str, *, ignore_case: bool = False) -> bool:
    """Wie die Shell die Nutzlast gegen die Muster hält — nach JSON-Kodierung."""
    payload = json.dumps(
        {"session_id": "s", "tool_input": {"command": command}},
        ensure_ascii=False,
        separators=(",", ":"),
    )
    if ignore_case:
        payload = payload.casefold()
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
    patterns, ignore_case = _claude_filter(event, group)
    assert patterns, "kein Vorfilter gefunden"
    if event == "PreToolUse":
        reacting = [
            c for c in REACTING_COMMANDS if hook.VERWIRFT.search(c) or hook.rueckfrage_werkzeug(c)
        ]
        assert any(hook.rueckfrage_werkzeug(c) for c in reacting), (
            "kein Beispiel für ein Werkzeug, das Geld kostet oder veröffentlicht"
        )
        reacting += [f"PYTHON TOOLS/{tool.upper()}.PY" for tool in hook.RUECKFRAGE_WERKZEUGE]
    else:
        reacting = [
            c for c in REACTING_COMMANDS if hook._test_command(c) or hook.SCHREIBT_DATEI.search(c)
        ]
    assert len(reacting) >= 5, "zu wenige Beispiele, die der Hook meldet"
    assert [c for c in reacting if not _passes(patterns, c, ignore_case=ignore_case)] == []
    assert not _passes(patterns, "ls -la", ignore_case=ignore_case), (
        "der Vorfilter lässt alles durch"
    )


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


#: Die Werkzeuge, vor denen auch unter `bypassPermissions` gefragt wird, weil sie
#: Geld kosten oder etwas veröffentlichen (`.claude/README.md`, „settings.json“).
GUARDED_TOOLS = ("run_agent_suite", "upload_website", "deploy_activation_server")

#: Jede Schreibweise, in der ein Werkzeug gestartet wird — die `ask`-Regeln in
#: `.claude/settings.json` sind Präfixregeln und kennen nur die erste.
TOOL_NOTATIONS = {
    "relativ": ".venv/Scripts/python.exe tools/{tool}.py",
    "absolut": '"F:/3D Druck/.venv/Scripts/python.exe" tools/{tool}.py --dry-run',
    "absolutes Skript": '"F:/3D Druck/.venv/Scripts/python.exe" "F:/3D Druck/tools/{tool}.py"',
    "Variable": '"$SUITE_PYTHON" tools/{tool}.py',
    "Variable in Klammern": '"${{SUITE_PYTHON}}" -X utf8 tools/{tool}.py',
    "Modul": ".venv/Scripts/python.exe -m tools.{tool}",
    "Modul mit Variable": '"$SUITE_PYTHON" -u -m tools.{tool} --help',
    "direkt": "./tools/{tool}.py",
    "direkt ohne Punkt": "tools/{tool}.py --site all",
    "PowerShell": ".venv\\Scripts\\python.exe tools/{tool}.py",
    "PowerShell rückwärts": ".venv\\Scripts\\python.exe tools\\{tool}.py",
    "PowerShell absolut": '& "F:\\3D Druck\\.venv\\Scripts\\python.exe" tools\\{tool}.py',
    "PowerShell Variable": "& $env:SUITE_PYTHON -m tools.{tool}",
    "Start-Process": (
        "Start-Process -FilePath .venv\\Scripts\\python.exe -ArgumentList 'tools\\{tool}.py'"
    ),
    "Umgebung davor": "PYTHONUTF8=1 python tools/{tool}.py",
    "nach cd": "cd tools && python {tool}.py",
    "in einer Kette": "git status && py -3.14 tools/{tool}.py",
    "bash -c": "bash -lc '.venv/Scripts/python.exe tools/{tool}.py'",
    "pwsh -Command": 'pwsh -NoProfile -Command "& .venv\\Scripts\\python.exe tools\\{tool}.py"',
}


@pytest.mark.parametrize("notation", sorted(TOOL_NOTATIONS))
@pytest.mark.parametrize("tool", GUARDED_TOOLS)
def test_a_guarded_tool_asks_in_every_notation(hook: ModuleType, tool: str, notation: str) -> None:
    """Gefragt wird am Werkzeugnamen, nicht an der Schreibweise des Interpreters."""
    command = TOOL_NOTATIONS[notation].format(tool=tool)

    assert hook.rueckfrage_werkzeug(command) == tool, command


@pytest.mark.parametrize(
    "command",
    [
        "git log -- tools/upload_website.py",
        "cat tools/upload_website.py",
        "grep -n upload tools/run_agent_suite.py",
        '"$SUITE_PYTHON" -m pytest tests/test_upload_website.py -q',
        "python -m ruff check tools/deploy_activation_server.py",
        ".venv/Scripts/python.exe tools/affected_tests.py tools/upload_website.py --why",
        "python -c \"print('tools/upload_website.py')\"",
        'echo ".venv/Scripts/python.exe tools/upload_website.py"',
        "python tools/upload_website_notes.py",
    ],
)
def test_reading_or_naming_a_guarded_tool_does_not_ask(hook: ModuleType, command: str) -> None:
    """Lesen, Prüfen und Nennen startet das Werkzeug nicht und fragt nicht."""
    assert hook.rueckfrage_werkzeug(command) is None


def test_the_hook_guards_the_same_tools_as_the_ask_list() -> None:
    """Hook und `ask`-Liste nennen dieselben Werkzeuge — eine Liste allein altert still."""
    spec = importlib.util.spec_from_file_location("solidon_hooks_tool_list", HOOK)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rules = json.loads(CLAUDE_SETTINGS.read_text(encoding="utf-8"))["permissions"]["ask"]
    named = {match for rule in rules for match in re.findall(r"tools/(\w+)\.py", rule)}

    assert set(GUARDED_TOOLS) <= named
    assert set(module.RUECKFRAGE_WERKZEUGE) == named


def _vor_bash(command: str, *extra: str) -> str:
    payload = {
        "session_id": "test-session",
        "hook_event_name": "PreToolUse",
        "tool_name": "Bash",
        "tool_input": {"command": command},
    }
    environment = os.environ.copy()
    environment.pop("SOLIDON3D_HOOKS", None)
    result = subprocess.run(
        [sys.executable, str(HOOK), "vor-bash", *extra],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        timeout=10,
        cwd=ROOT,
        env=environment,
    )
    assert result.returncode == 0
    return result.stdout


def test_claude_is_asked_before_a_guarded_tool() -> None:
    """Unter Claude wird gefragt — auch im Modus `bypassPermissions`."""
    output = json.loads(_vor_bash('"F:/3D Druck/.venv/Scripts/python.exe" -m tools.upload_website'))

    specific = output["hookSpecificOutput"]
    assert specific["permissionDecision"] == "ask"
    assert "upload_website" in specific["permissionDecisionReason"]


def test_codex_is_stopped_before_a_guarded_tool_until_robert_agrees() -> None:
    """Codex kennt `ask` nicht: Es blockiert, bis der Freigabemarker im Befehl steht."""
    output = json.loads(_vor_bash("./tools/run_agent_suite.py", "--codex"))

    specific = output["hookSpecificOutput"]
    assert specific["permissionDecision"] == "deny"
    assert "SOLIDON3D_WERKZEUG_FREIGEGEBEN=ja" in specific["permissionDecisionReason"]
    assert (
        _vor_bash("SOLIDON3D_WERKZEUG_FREIGEGEBEN=ja ./tools/run_agent_suite.py", "--codex") == ""
    )


def test_an_ordinary_command_passes_the_hook_silently() -> None:
    assert _vor_bash('"$SUITE_PYTHON" tools/affected_tests.py --run') == ""


def test_write_prefilter_lets_python_and_memory_through() -> None:
    """Der Vorfilter vor `nach-aenderung` spart den Python-Start bei Markdown und Co."""
    patterns, ignore_case = _claude_filter("PostToolUse", 0)
    assert patterns, "kein Vorfilter gefunden"

    def passes(path: str) -> bool:
        payload = json.dumps({"tool_input": {"file_path": path, "content": "x"}})
        if ignore_case:
            payload = payload.casefold()
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


# Nur Aufrufformen; die Werkzeugnamen kommen aus der vorhandenen Hookquelle.
RM346_NOTATIONS = {
    "ganze Argumentzeichenkette": (
        "Start-Process -FilePath python -ArgumentList 'tools/{tool}.py --help'"
    ),
    "Kommaliste ohne Leerzeichen": (
        "Start-Process -FilePath python -ArgumentList 'tools/{tool}.py','--help'"
    ),
    "Kommaliste mit Leerzeichen": (
        'Start-Process -FilePath python -ArgumentList "tools/{tool}.py", "--help"'
    ),
    "gewöhnliches Array": (
        "Start-Process -FilePath python -ArgumentList @('tools/{tool}.py', '--help')"
    ),
    "Array vor weiterem Befehl": (
        "Start-Process -FilePath python -ArgumentList @('tools/{tool}.py', '--help'); echo fertig"
    ),
    "Array mit inneren Pfadquotes": (
        "Start-Process -FilePath python -ArgumentList "
        "@('\"F:/3D Druck/tools/{tool}.py\"', '--site', 'all')"
    ),
    "Zeichenkette mit inneren Pfadquotes": (
        "Start-Process -FilePath python -ArgumentList '\"F:/3D Druck/tools/{tool}.py\" --help'"
    ),
    "Backtickquotes": (
        'Start-Process -FilePath python -ArgumentList "-Xutf8 '
        '`"F:/3D Druck/tools/{tool}.py`" --help"'
    ),
    "benannte Parameter umgekehrt": (
        "Start-Process -ArgumentList '-m','tools.{tool}','--help' -FilePath python"
    ),
    "Array mit Interpreteroptionen": (
        "Start-Process -WindowStyle Hidden -ArgumentList "
        "@('-Xutf8', '-Wignore', 'tools/{tool}.py', '--dry-run') "
        "-FilePath 'F:/3D Druck/.venv/Scripts/PYTHON.EXE'"
    ),
    "positionale Argumentliste": "Start-Process python 'tools/{tool}.py --help'",
    "Argumentalias": "start python -Args 'tools/{tool}.py','--help'",
    "kompaktes X": "python -Xutf8 tools/{tool}.py --help",
    "kompaktes W": "python -Wignore tools/{tool}.py --help",
    "kompakte Optionen vor Modul": "python -Xutf8 -Werror -m tools.{tool} --help",
    "Windows Dateigroßschreibung": "python tools/{upper}.PY --help",
    "Windows Pfadgroßschreibung": (
        '& "F:/3D Druck/.venv/Scripts/PYTHON.EXE" "F:/3D Druck/TOOLS/{upper}.PY" --help'
    ),
    "Komma und Klammern im Pfad": (
        "Start-Process -FilePath python -ArgumentList "
        '\'"F:/3D Druck (alt), Neu/tools/{tool}.py" --label "a,b"\''
    ),
    "getrennte Optionen als Kontrolle": "python -X utf8 -W ignore tools/{tool}.py --help",
    "nacktes Argument als Kontrolle": (
        "Start-Process -WindowStyle Hidden -FilePath python -ArgumentList 'tools/{tool}.py'"
    ),
}


def _rm346_hook_output(
    hook: ModuleType,
    command: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    *,
    codex: bool,
) -> str:
    """Reicht ausschließlich Text an den echten PreToolUse-Einstieg, ohne Shellstart."""
    monkeypatch.setattr(hook, "eingabe", lambda: {"tool_input": {"command": command}})
    monkeypatch.setattr(hook.sys, "argv", ["hook.py", "vor-bash", *(["--codex"] if codex else [])])
    hook.vor_bash()
    return capsys.readouterr().out


@pytest.mark.parametrize("notation", sorted(RM346_NOTATIONS))
def test_rm346_parser_recognizes_the_actual_argument_list(hook: ModuleType, notation: str) -> None:
    """Jede Form trifft alle sechs Namen aus der gemeinsamen Quelle."""
    assert len(hook.RUECKFRAGE_WERKZEUGE) == 6
    for tool in hook.RUECKFRAGE_WERKZEUGE:
        command = RM346_NOTATIONS[notation].format(tool=tool, upper=tool.upper())
        assert hook.rueckfrage_werkzeug(command) == tool, command


@pytest.mark.parametrize("notation", sorted(RM346_NOTATIONS))
@pytest.mark.parametrize("permission", ("ask", "deny", "allowed"))
def test_rm346_argument_forms_reach_the_real_hook_decision(
    hook: ModuleType,
    notation: str,
    permission: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Erkennung schließt an ask, deny und die vorhandene explizite Freigabe an."""
    for tool in hook.RUECKFRAGE_WERKZEUGE:
        command = RM346_NOTATIONS[notation].format(tool=tool, upper=tool.upper())
        # Die stille Freigabe darf nicht durch eine fehlende Erkennung grün werden.
        assert hook.rueckfrage_werkzeug(command) == tool, command
        if permission == "allowed":
            command += " # SOLIDON3D_WERKZEUG_FREIGEGEBEN=ja"
        output = _rm346_hook_output(hook, command, monkeypatch, capsys, codex=permission != "ask")
        if permission == "allowed":
            assert output == ""
        else:
            specific = json.loads(output)["hookSpecificOutput"]
            assert specific["hookEventName"] == "PreToolUse"
            assert specific["permissionDecision"] == permission
            assert f"tools/{tool}.py" in specific["permissionDecisionReason"]


@pytest.mark.parametrize(
    "command_template",
    [
        "Start-Process -FilePath notepad -ArgumentList 'tools/{tool}.py'",
        "Start-Process -FilePath notepad -ArgumentList 'tools/{tool}.py','--help'",
        "Start-Process -FilePath python -WorkingDirectory 'tools/{tool}.py'",
        "Start-Process -WorkingDirectory 'tools/{tool}.py' -FilePath notepad",
        "Start-Process -WorkingDirectory 'tools/{tool}.py' -FilePath python "
        "-ArgumentList '-m ruff check ordinary.py'",
        "Start-Process -FilePath python -ArgumentList '-m ruff check tools/{tool}.py'",
        "Start-Process -FilePath python -ArgumentList @('-m', 'pytest', 'tools/{tool}.py')",
        "Start-Process -FilePath python -ArgumentList '-c \"print(0)\" tools/{tool}.py'",
        "Start-Process -FilePath python -ArgumentList '-c \"print(0)\" ; python tools/{tool}.py'",
        "Start-Process -FilePath python -ArgumentList "
        "@('-c', '\"print(0)\"', ';', 'python', 'tools/{tool}.py')",
        "Start-Process -FilePath python -ArgumentList "
        "'-c','\"print(0)\"',';','python','tools/{tool}.py'",
        "Start-Process -FilePath python -ArgumentList "
        "'tools/affected_tests.py','tools/{tool}.py','--why'",
        "python -Xutf8 -m ruff check tools/{tool}.py",
        "python -Wignore -c \"print('tools/{tool}.py')\"",
        'echo "Start-Process -FilePath python -ArgumentList tools/{tool}.py"',
    ],
)
def test_rm346_program_and_mentions_are_not_interchanged(
    hook: ModuleType,
    command_template: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Notepad, Arbeitsordner, Prüfer und c-Text starten kein geschütztes Werkzeug."""
    for tool in hook.RUECKFRAGE_WERKZEUGE:
        command = command_template.format(tool=tool)
        assert hook.rueckfrage_werkzeug(command) is None, command
        for codex in (False, True):
            assert _rm346_hook_output(hook, command, monkeypatch, capsys, codex=codex) == ""


@pytest.mark.parametrize("depth", (8, 9))
def test_rm346_shell_recursion_keeps_the_existing_boundary(hook: ModuleType, depth: int) -> None:
    """Acht Hüllen werden entpackt; die neunte übersteigt den bisherigen Schutz."""
    for tool in hook.RUECKFRAGE_WERKZEUGE:
        command = f"python tools/{tool}.py"
        for _ in range(depth):
            command = "bash -c " + shlex.quote(command)
        assert hook.rueckfrage_werkzeug(command) == (tool if depth == 8 else None)


def test_rm346_unclosed_command_keeps_the_existing_conservative_guard(hook: ModuleType) -> None:
    """Eine nicht zerlegbare Zeile behält den vorhandenen Schutz am Werkzeugnamen."""
    for tool in hook.RUECKFRAGE_WERKZEUGE:
        assert hook.rueckfrage_werkzeug(f"python tools/{tool}.py 'offen") == tool


# Konkrete unabhängige Funde am ersten gehaltenen RM346-Stand.
RM346_REVIEW_NOTATIONS = {
    "Trenner unmittelbar vor Kommentar": "echo fertig;# Kommentar\npython tools/{tool}.py",
    "erster Trenner nach Kommentar": "# Kommentar\n; python tools/{tool}.py",
    "Argumentposition nach benanntem Programm": (
        "Start-Process -FilePath python 'tools/{tool}.py --help'"
    ),
    "Programmposition nach Schalter": (
        "Start-Process -NoNewWindow python -ArgumentList 'tools/{tool}.py --help'"
    ),
    "beide Positionen nach benannten Werten": (
        "Start-Process -WorkingDirectory 'F:/3D Druck' -Wait -WindowStyle Hidden "
        "python 'tools/{tool}.py --help'"
    ),
    "Argumentposition nach Arbeitsordner": (
        "Start-Process -FilePath python -WorkingDirectory 'F:/3D Druck' 'tools/{tool}.py --help'"
    ),
    "Apostroph im nativen Argument": (
        'Start-Process -FilePath python -ArgumentList "tools/{tool}.py O\'Brien"'
    ),
    "Apostroph im nativen Skriptpfad": (
        'Start-Process -FilePath python -ArgumentList "`"F:/O\'Brien/tools/{tool}.py`" --help"'
    ),
    "nativer Kommapfad": "python F:/alt,neu/tools/{tool}.py --help",
    "nativer mehrfacher Kommapfad": "python F:/alt,,neu/tools/{tool}.py --help",
    "relativer Kommapfad": "python ./alt,neu/tools/{tool}.py --help",
    "mehrzeiliges Pythonarray": (
        "Start-Process -FilePath python -ArgumentList @(\n 'tools/{tool}.py',\n '--help'\n)"
    ),
    "Array vor nativem Kommapfad": (
        "Start-Process -FilePath notepad -ArgumentList @('gewöhnlich', '--help'); "
        "python F:/alt,neu/tools/{tool}.py"
    ),
}


@pytest.mark.parametrize("notation", sorted(RM346_REVIEW_NOTATIONS))
@pytest.mark.parametrize("permission", ("ask", "deny", "allowed"))
def test_rm346_review_reproduced_forms_reach_the_real_hook(
    hook: ModuleType,
    notation: str,
    permission: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Jeder belegte Start trifft alle sechs Namen und den tatsächlichen Ausgang."""
    assert len(hook.RUECKFRAGE_WERKZEUGE) == 6
    for tool in hook.RUECKFRAGE_WERKZEUGE:
        command = RM346_REVIEW_NOTATIONS[notation].format(tool=tool)
        assert hook.rueckfrage_werkzeug(command) == tool, command
        if permission == "allowed":
            command += " # SOLIDON3D_WERKZEUG_FREIGEGEBEN=ja"
        output = _rm346_hook_output(hook, command, monkeypatch, capsys, codex=permission != "ask")
        if permission == "allowed":
            assert output == ""
        else:
            specific = json.loads(output)["hookSpecificOutput"]
            assert specific["hookEventName"] == "PreToolUse"
            assert specific["permissionDecision"] == permission
            assert f"tools/{tool}.py" in specific["permissionDecisionReason"]


@pytest.mark.parametrize(
    "command_template",
    [
        "Start-Process -FilePath notepad -ArgumentList @('gewöhnlich',\n 'tools/{tool}.py')",
        "Start-Process -FilePath notepad -ArgumentList @(\n 'tools/{tool}.py',\n '--help'\n)",
        "Start-Process -FilePath python -ArgumentList "
        "@(\n '-c',\n '\"print(0)\"',\n 'tools/{tool}.py'\n)",
        "Start-Process -FilePath python -ArgumentList @('-m',\n 'ruff',\n 'tools/{tool}.py')",
        "Start-Process -NoNewWindow notepad 'tools/{tool}.py --help'",
        "Start-Process -WorkingDirectory 'tools/{tool}.py' python -ArgumentList '-m ruff'",
        "Start-Process -FilePath python -WorkingDirectory "
        "'tools/{tool}.py' '-m pytest ordinary.py'",
        'Start-Process -FilePath python -ArgumentList "-c `"print(0)`" O\'Brien tools/{tool}.py"',
        "Start-Process -FilePath python -ArgumentList "
        "@('-c', '\"print(0)\"',\n ';', 'python', 'tools/{tool}.py')",
        "echo ';' '# Kommentar' 'tools/{tool}.py'",
        "echo '`;' 'tools/{tool}.py'",
        "echo '\n;' 'tools/{tool}.py'",
        "python -c \"print('gewöhnlich')\" F:/alt,neu/tools/{tool}.py",
        "python -m ruff check F:/alt,neu/tools/{tool}.py",
        "cat F:/alt,neu/tools/{tool}.py",
    ],
)
def test_rm346_review_native_values_and_multiline_arrays_are_not_commands(
    hook: ModuleType,
    command_template: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Native Daten, Zeilen und Arbeitsordner erzeugen keinen zweiten Start."""
    for tool in hook.RUECKFRAGE_WERKZEUGE:
        command = command_template.format(tool=tool)
        assert hook.rueckfrage_werkzeug(command) is None, command
        for codex in (False, True):
            assert _rm346_hook_output(hook, command, monkeypatch, capsys, codex=codex) == ""


@pytest.mark.parametrize(
    ("argument_line", "expected"),
    [
        ('"alpha beta" gamma delta', ["alpha beta", "gamma", "delta"]),
        (r'"ab\"c" "\\" d', ['ab"c', "\\", "d"]),
        (r'a\\\b d"e f"g h', [r"a\\\b", "de fg", "h"]),
        (r"a\\\"b c d", ['a\\"b', "c", "d"]),
        (r'a\\\\"b c" d e', [r"a\\b c", "d", "e"]),
        ('a"b"" c d', ['ab" c d']),
        ('"" O\'Brien "zweiter Wert"', ["", "O'Brien", "zweiter Wert"]),
    ],
)
def test_rm346_review_native_argument_line_reaches_the_actual_child_parser(
    hook: ModuleType,
    argument_line: str,
    expected: list[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Beobachtet die echten Kindargumente nach den Microsoft-C-Argumentregeln."""
    original = hook._werkzeug_aufruf
    native_calls: list[list[str]] = []

    def observed(tokens: list[str], depth: int) -> str | None:
        if depth == 1:
            native_calls.append(list(tokens))
        return original(tokens, depth)

    monkeypatch.setattr(hook, "_werkzeug_aufruf", observed)
    # PowerShells äußere Zeichenkette erhält die inneren nativen Quotes.
    outer = '"' + argument_line.replace("`", "``").replace('"', '`"') + '"'
    assert hook.rueckfrage_werkzeug("Start-Process -FilePath python -ArgumentList " + outer) is None
    assert native_calls == [["python", *expected]]


# Gebundene PowerShell-Parameter verwenden dieselbe begrenzte Literalgrammatik.
RM346_BOUND_NOTATIONS = {
    "gebundene ArgumentList": "Start-Process -FilePath python -ArgumentList:tools/{tool}.py",
    "gebundener Programmwert als vorhandene Kontrolle": (
        "Start-Process -FilePath:python -ArgumentList tools/{tool}.py"
    ),
    "beide Werte gebunden": "Start-Process -FilePath:python -ArgumentList:tools/{tool}.py",
    "beide Werte gebunden in umgekehrter Reihenfolge": (
        "Start-Process -ArgumentList:tools/{tool}.py -FilePath:python"
    ),
    "gebundene Argumente vor freiem Programm": (
        "Start-Process -ArgumentList:'tools/{tool}.py --help' python"
    ),
    "gebundenes Programm vor freien Argumenten": (
        "Start-Process -FilePath:python 'tools/{tool}.py --help'"
    ),
    "gebundene Argumente nach Schalter und Arbeitsordner": (
        "Start-Process -NoNewWindow -WorkingDirectory:'F:/3D Druck' "
        "python -ArgumentList:'tools/{tool}.py --help'"
    ),
    "einfach zitierte Argumente": (
        "Start-Process -FilePath:python -ArgumentList:'tools/{tool}.py --help'"
    ),
    "doppelt zitierte Argumente": (
        'Start-Process -FilePath:python -ArgumentList:"tools/{tool}.py --help"'
    ),
    "zitierter Programmpfad und innere Pfadquotes": (
        "Start-Process -FilePath:'F:/3D Druck/.venv/Scripts/PYTHON.EXE' "
        "-ArgumentList:'\"F:/3D Druck/tools/{tool}.py\" --help'"
    ),
    "gebundene Kommaliste": (
        "Start-Process -FilePath:python -ArgumentList:'tools/{tool}.py','--help'"
    ),
    "gebundenes mehrzeiliges Array": (
        "Start-Process -FilePath:python -ArgumentList:@(\n 'tools/{tool}.py',\n '--help'\n)"
    ),
    "gebundene geklammerte Modulliste": (
        "Start-Process -FilePath:python -ArgumentList:('-m', 'tools.{tool}', '--help')"
    ),
    "gebundene Aliase und Großschreibung": (
        "START-PROCESS -PATH:PYTHON.EXE -ARGS:'TOOLS/{upper}.PY --help'"
    ),
    "getrennte Werte als vorhandene Kontrolle": (
        "Start-Process -FilePath python -ArgumentList 'tools/{tool}.py --help'"
    ),
}


@pytest.mark.parametrize("notation", sorted(RM346_BOUND_NOTATIONS))
@pytest.mark.parametrize("permission", ("ask", "deny", "allowed"))
def test_rm346_bound_parameters_reach_the_actual_hook(
    hook: ModuleType,
    notation: str,
    permission: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Gebundene und gemischte Werte treffen alle sechs Namen und echten Entscheidungen."""
    assert len(hook.RUECKFRAGE_WERKZEUGE) == 6
    for tool in hook.RUECKFRAGE_WERKZEUGE:
        plain = RM346_BOUND_NOTATIONS[notation].format(tool=tool, upper=tool.upper())
        command = plain
        if permission == "allowed":
            command += " # SOLIDON3D_WERKZEUG_FREIGEGEBEN=ja"
        output = _rm346_hook_output(hook, command, monkeypatch, capsys, codex=permission != "ask")
        # Auch die stille Markerfreigabe braucht eine tatsächlich erkannte Vorlage.
        assert hook.rueckfrage_werkzeug(plain) == tool, plain
        if permission == "allowed":
            assert output == ""
        else:
            specific = json.loads(output)["hookSpecificOutput"]
            assert specific["hookEventName"] == "PreToolUse"
            assert specific["permissionDecision"] == permission
            assert f"tools/{tool}.py" in specific["permissionDecisionReason"]


@pytest.mark.parametrize(
    "command_template",
    [
        "Start-Process -FilePath:notepad -ArgumentList:tools/{tool}.py",
        "Start-Process -FilePath notepad -ArgumentList:'tools/{tool}.py --help'",
        "Start-Process -FilePath:python -ArgumentList:'-m ruff check tools/{tool}.py'",
        "Start-Process -FilePath:python -ArgumentList:@('-m', 'ruff', 'tools/{tool}.py')",
        "Start-Process -FilePath:python -ArgumentList:'-c \"print(0)\" tools/{tool}.py'",
        "Start-Process -FilePath:python -ArgumentList:"
        "@('-c', '\"print(0)\"', ';', 'python', 'tools/{tool}.py')",
        "Start-Process -FilePath:python -WorkingDirectory:'tools/{tool}.py' "
        "-ArgumentList:'-m ruff'",
        "Start-Process -WorkingDirectory:'tools/{tool}.py' python -ArgumentList:'-m ruff'",
        "Start-Process -WorkingDirectory:'tools/{tool}.py' -FilePath:notepad "
        "-ArgumentList:'gewöhnlich'",
        "Start-Process -FilePath:python '-ArgumentList:tools/{tool}.py'",
        "Start-Process '-FilePath:python' -ArgumentList:tools/{tool}.py",
        'echo "Start-Process -FilePath:python -ArgumentList:tools/{tool}.py"',
        'python -c "print(0)" -ArgumentList:tools/{tool}.py',
        "python -m ruff check tools/{tool}.py",
        "Start-Process -FilePath:notepad -ArgumentList:@('gewöhnlich',\n 'tools/{tool}.py')",
    ],
)
def test_rm346_bound_mentions_and_quoted_parameter_names_are_not_starts(
    hook: ModuleType,
    command_template: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Bindung erfindet keine Programme aus Arbeitsordnern, Nennungen oder Prüferargumenten."""
    for tool in hook.RUECKFRAGE_WERKZEUGE:
        command = command_template.format(tool=tool)
        assert hook.rueckfrage_werkzeug(command) is None, command
        for codex in (False, True):
            assert _rm346_hook_output(hook, command, monkeypatch, capsys, codex=codex) == ""


@pytest.mark.parametrize("literal", ("(", ")", ",", ";", "-FilePath:python"))
def test_rm346_bound_quoted_values_keep_their_literal_metadata(
    hook: ModuleType, literal: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Zitierte Trenner bleiben Werte am echten nativen Kindparseranschluss."""
    original = hook._werkzeug_aufruf
    native_calls: list[list[str]] = []

    def observed(tokens: list[str], depth: int) -> str | None:
        if depth == 1:
            native_calls.append(list(tokens))
        return original(tokens, depth)

    monkeypatch.setattr(hook, "_werkzeug_aufruf", observed)
    command = "Start-Process -FilePath:python -ArgumentList:'" + literal + "'"
    assert hook.rueckfrage_werkzeug(command) is None
    assert native_calls == [["python", literal]]
