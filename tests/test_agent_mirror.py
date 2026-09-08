"""Die Codex-Agentenprofile stehen auf dem Stand ihrer Claude-Quelle.

Dieselben vierzehn Fachagenten liegen zweimal im Repository, einmal je
Werkzeug. Bis zum 08.09.2026 wurden beide Seiten von Hand gepflegt, und die
Historie sagt, wie gut das ging: neun Commits nur auf der Claude-Seite, drei
nur auf der Codex-Seite, keiner auf beiden. Am Ende wichen alle vierzehn
Beschreibungen ab, drei Claude-Agenten schrieben einen Testlauf vor, der seit
dem 16.08.2026 im Speicherabriss endet, und keiner kannte
``tools/affected_tests.py``.

Seither erzeugt ``tools/sync_agents.py`` die Codex-Seite aus der Claude-Seite.
Diese Datei ist der Wächter dazu — ohne ihn wäre der Generator nur ein
Angebot, das man vergessen kann.

**Codex läuft nicht auf jeder Maschine, an der hier gearbeitet wird.** Eine
kaputte TOML-Datei fiele deshalb erst dort auf, wo niemand sie repariert;
darum prüft :func:`test_generated_profiles_are_valid_toml` jede Datei mit
``tomllib``, statt sich auf den Generator zu verlassen.
"""

from __future__ import annotations

import os
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = ROOT / ".claude" / "agents"
TARGET_DIR = ROOT / ".codex" / "agents"

sys.path.insert(0, str(ROOT))

from tools import sync_agents  # noqa: E402


def test_codex_profiles_are_current() -> None:
    """Jedes Profil trägt, was seine Quelle sagt."""
    assert sync_agents.main(["--check"]) == 0, "Codex profiles are stale — run tools/sync_agents.py"


def test_every_agent_exists_on_both_sides() -> None:
    """Kein Agent fehlt auf einer der beiden Seiten."""
    sources = {path.stem for path in SOURCE_DIR.glob("*.md")}
    targets = {path.stem for path in TARGET_DIR.glob("*.toml")}
    assert sources, "no agent definitions found"
    assert sources == targets, f"only Claude: {sources - targets}, only Codex: {targets - sources}"


def test_generated_profiles_are_valid_toml() -> None:
    """Jedes Profil lässt sich lesen, und die Pflichtfelder stehen darin."""
    for path in sorted(TARGET_DIR.glob("*.toml")):
        with path.open("rb") as handle:
            profile = tomllib.load(handle)
        assert profile["name"] == path.stem, f"{path.name}: name mismatch"
        for field in ("description", "model", "model_reasoning_effort", "developer_instructions"):
            assert profile.get(field), f"{path.name}: {field} missing or empty"


def test_windows_paths_survive_the_toml_round_trip() -> None:
    """Ein Backslash im Anweisungstext kommt einfach wieder heraus.

    Die Agenten nennen Befehle wie ``.venv\\Scripts\\python.exe``. In einer
    TOML-Zeichenkette leitet der Backslash eine Maskierung ein — wer ihn nicht
    verdoppelt, erzeugt entweder Unsinn oder eine unlesbare Datei.
    """
    seen = 0
    for path in sorted(TARGET_DIR.glob("*.toml")):
        with path.open("rb") as handle:
            profile = tomllib.load(handle)
        text = profile["developer_instructions"]
        assert "\\\\" not in text, f"{path.name}: doubled backslash survived into the text"
        seen += text.count(".venv\\Scripts")
    assert seen, "no Windows path in any profile — the round trip was never exercised"


def test_render_derives_model_effort_and_sandbox(tmp_path: Path) -> None:
    """Modell, Aufwand und Sandbox folgen aus dem Frontmatter."""
    source = tmp_path / "probe.md"
    source.write_text(
        "---\n"
        "name: probe\n"
        "description: >\n"
        "  Erste Zeile\n"
        "  zweite Zeile.\n"
        "model: sonnet\n"
        "effort: medium\n"
        "tools: Read, Grep\n"
        "---\n\n"
        "# Probe\n",
        encoding="utf-8",
    )

    profile = tomllib.loads(sync_agents.render(source))

    assert profile["model"] == sync_agents.MODELS["sonnet"]
    assert profile["model_reasoning_effort"] == "medium"
    # Ohne Write und Edit arbeitet der Agent nur lesend.
    assert profile["sandbox_mode"] == "read-only"
    # `description: >` faltet die Zeilen eines Absatzes zusammen und schließt
    # mit genau einem Zeilenumbruch — dasselbe, was YAML für `>` vorschreibt.
    assert profile["description"] == "Erste Zeile zweite Zeile.\n"


def test_render_grants_no_sandbox_to_a_writing_agent(tmp_path: Path) -> None:
    """Wer schreiben darf, bekommt keine Nur-Lesen-Sandbox."""
    source = tmp_path / "probe.md"
    source.write_text(
        "---\n"
        "name: probe\n"
        "description: >\n"
        "  Kurz.\n"
        "model: opus\n"
        "effort: high\n"
        "tools: Read, Write, Edit\n"
        "---\n\n"
        "# Probe\n",
        encoding="utf-8",
    )

    profile = tomllib.loads(sync_agents.render(source))

    assert "sandbox_mode" not in profile
    assert profile["model"] == sync_agents.MODELS["opus"]


def test_render_points_a_skill_reference_at_the_codex_file(tmp_path: Path) -> None:
    """`/pruefen` heißt bei Codex anders — ein erfundener Skill bleibt stehen."""
    source = tmp_path / "probe.md"
    source.write_text(
        "---\n"
        "name: probe\n"
        "description: >\n"
        "  Kurz.\n"
        "model: opus\n"
        "effort: high\n"
        "tools: Read\n"
        "---\n\n"
        "Der Prüfweg steht in `/pruefen`, nicht in `/gibtesnicht`.\n",
        encoding="utf-8",
    )

    text = tomllib.loads(sync_agents.render(source))["developer_instructions"]

    assert "`.agents/skills/pruefen/SKILL.md`" in text
    assert "`/gibtesnicht`" in text, "an unknown skill must not be rewritten"


def test_render_rejects_a_frontmatter_without_model(tmp_path: Path) -> None:
    """Eine unvollständige Quelle wird gemeldet, nicht stillschweigend ergänzt."""
    source = tmp_path / "probe.md"
    source.write_text(
        "---\nname: probe\ndescription: >\n  Kurz.\neffort: high\ntools: Read\n---\n\n# Probe\n",
        encoding="utf-8",
    )

    with pytest.raises(sync_agents.SyncError, match="model"):
        sync_agents.render(source)


def test_render_rejects_an_unknown_model(tmp_path: Path) -> None:
    """Für ein Modell ohne Codex-Entsprechung gibt es keine stille Vorgabe."""
    source = tmp_path / "probe.md"
    source.write_text(
        "---\n"
        "name: probe\n"
        "description: >\n"
        "  Kurz.\n"
        "model: haiku\n"
        "effort: high\n"
        "tools: Read\n"
        "---\n\n"
        "# Probe\n",
        encoding="utf-8",
    )

    with pytest.raises(sync_agents.SyncError, match="haiku"):
        sync_agents.render(source)


def _prepare_mirror(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Legt einen frischen Klon ohne erzeugte Dateien für die Gegenproben an."""
    for field, relative in (
        ("SOURCE_DIR", ".claude/agents"),
        ("TARGET_DIR", ".codex/agents"),
        ("SOURCE_SKILL_DIR", ".claude/skills"),
        ("SKILL_DIR", ".agents/skills"),
    ):
        monkeypatch.setattr(sync_agents, field, tmp_path / relative)
    sync_agents.SOURCE_DIR.mkdir(parents=True)
    (sync_agents.SOURCE_SKILL_DIR / "probe" / "references").mkdir(parents=True)
    (sync_agents.SOURCE_DIR / "probe.md").write_text(
        "---\nname: probe\ndescription: >\n  Kurz.\nmodel: opus\neffort: high\n"
        "tools: Read, Write\n---\nLies `/probe`.\n",
        encoding="utf-8",
    )
    (sync_agents.SOURCE_SKILL_DIR / "probe" / "SKILL.md").write_text(
        "---\nname: probe\ndescription: >\n  Prüft den Aufruf.\n"
        "disable-model-invocation: true\n---\n# Probe: $ARGUMENTS\n"
        "Lies references/beleg.txt und `/probe`.\n",
        encoding="utf-8",
    )
    (sync_agents.SOURCE_SKILL_DIR / "probe" / "references" / "beleg.txt").write_bytes(b"Beleg\n")


def test_sync_populates_a_fresh_clone_from_source_skills(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Neue Skills brauchen keinen alten Zielbestand, um richtig verlinkt zu werden."""
    _prepare_mirror(tmp_path, monkeypatch)

    assert sync_agents.main([]) == 0

    profile = tomllib.loads((sync_agents.TARGET_DIR / "probe.toml").read_text(encoding="utf-8"))
    assert "`.agents/skills/probe/SKILL.md`" in profile["developer_instructions"]
    skill = (sync_agents.SKILL_DIR / "probe" / "SKILL.md").read_text(encoding="utf-8")
    assert "$ARGUMENTS" not in skill
    assert "`.agents/skills/probe/SKILL.md`" in skill
    assert (sync_agents.SKILL_DIR / "probe" / "references" / "beleg.txt").read_bytes() == b"Beleg\n"
    assert (sync_agents.SKILL_DIR / "probe" / "agents" / "openai.yaml").read_text(
        encoding="utf-8"
    ) == "policy:\n  allow_implicit_invocation: false\n"
    assert sync_agents.main(["--check"]) == 0


@pytest.mark.parametrize("change", ["skill", "reference", "policy", "orphan", "removed"])
def test_check_detects_skill_content_policy_and_removed_sources(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, change: str
) -> None:
    """Auch zusätzliche oder gelöschte Skilldateien machen den Spiegel rot."""
    _prepare_mirror(tmp_path, monkeypatch)
    assert sync_agents.main([]) == 0
    if change == "removed":
        (sync_agents.SOURCE_SKILL_DIR / "probe" / "SKILL.md").unlink()
    else:
        relative = {
            "skill": "probe/SKILL.md",
            "reference": "probe/references/beleg.txt",
            "policy": "probe/agents/openai.yaml",
            "orphan": "alt/SKILL.md",
        }[change]
        target = sync_agents.SKILL_DIR / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("Anderer Inhalt\n", encoding="utf-8")
    before = {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}

    assert sync_agents.main(["--check"]) == 1

    assert before == {path: path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}


def test_invalid_later_source_leaves_every_existing_target_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein später Quellfehler darf keine halbe neue Spiegelgeneration hinterlassen."""
    _prepare_mirror(tmp_path, monkeypatch)
    assert sync_agents.main([]) == 0
    before = {
        path: path.read_bytes()
        for directory in (sync_agents.TARGET_DIR, sync_agents.SKILL_DIR)
        for path in directory.rglob("*")
        if path.is_file()
    }
    source = sync_agents.SOURCE_DIR / "probe.md"
    source.write_text(source.read_text(encoding="utf-8") + "Neue Vorgabe.\n", encoding="utf-8")
    (sync_agents.SOURCE_DIR / "z-kaputt.md").write_text("ohne Frontmatter", encoding="utf-8")

    assert sync_agents.main([]) == 1

    assert all(path.read_bytes() == content for path, content in before.items())
    assert not (sync_agents.TARGET_DIR / "z-kaputt.toml").exists()


def test_invocation_metadata_has_exactly_one_source(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein zweites, widersprechendes Aufrufschema wird vor dem Schreiben abgelehnt."""
    _prepare_mirror(tmp_path, monkeypatch)
    metadata = sync_agents.SOURCE_SKILL_DIR / "probe" / "agents" / "openai.yaml"
    metadata.parent.mkdir()
    metadata.write_text("policy:\n  allow_implicit_invocation: true\n", encoding="utf-8")

    assert sync_agents.main([]) == 1
    assert not sync_agents.SKILL_DIR.exists()
    assert not sync_agents.TARGET_DIR.exists()


def test_check_accepts_git_windows_line_endings(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Windows-Checkout ist ohne Neuschreiben derselbe Textstand."""
    _prepare_mirror(tmp_path, monkeypatch)
    assert sync_agents.main([]) == 0
    for directory in (sync_agents.TARGET_DIR, sync_agents.SKILL_DIR):
        for path in directory.rglob("*"):
            if path.is_file() and path.suffix in {".md", ".toml", ".yaml"}:
                path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))

    assert sync_agents.main(["--check"]) == 0


@pytest.mark.parametrize(
    "body", ['Endet auf "', 'Docstring: """Text"""', "Steuerzeichen: \x1b", "Löschzeichen: \x7f"]
)
def test_toml_round_trip_preserves_quotes_and_control_characters(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, body: str
) -> None:
    """Anweisungen dürfen Anführungszeichen enthalten, ohne das Profil zu zerstören."""
    _prepare_mirror(tmp_path, monkeypatch)
    source = sync_agents.SOURCE_DIR / "probe.md"
    text = source.read_text(encoding="utf-8").replace("Lies `/probe`.", body)
    source.write_text(text, encoding="utf-8")

    assert tomllib.loads(sync_agents.render(source))["developer_instructions"] == body + "\n"


@pytest.mark.parametrize("tools", ['[Read, "Write"]', "\n  - Read\n  - Edit"])
def test_yaml_tool_lists_keep_the_writing_capability(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, tools: str
) -> None:
    """Die YAML-Listenform darf einem schreibenden Agenten keine Lesesperre geben."""
    _prepare_mirror(tmp_path, monkeypatch)
    source = sync_agents.SOURCE_DIR / "probe.md"
    source.write_text(
        source.read_text(encoding="utf-8").replace("tools: Read, Write", f"tools: {tools}"),
        encoding="utf-8",
    )

    assert "sandbox_mode" not in tomllib.loads(sync_agents.render(source))


@pytest.mark.parametrize("value", ["effort: ultra", "effort: high\neffort: low"])
def test_invalid_or_duplicate_effort_is_rejected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """Ungültige Modellparameter werden vor der Generierung gemeldet."""
    _prepare_mirror(tmp_path, monkeypatch)
    source = sync_agents.SOURCE_DIR / "probe.md"
    source.write_text(
        source.read_text(encoding="utf-8").replace("effort: high", value), encoding="utf-8"
    )

    with pytest.raises(sync_agents.SyncError):
        sync_agents.render(source)


def test_yaml_fold_keeps_the_number_of_paragraph_breaks() -> None:
    """Eine Leerzeile im gefalteten YAML-Block wird genau ein Zeilenumbruch."""
    assert sync_agents._fold("  Erste\n  Zeile.\n\n  Zweite.\n\n\n  Dritte.") == (
        "Erste Zeile.\nZweite.\n\nDritte."
    )


def test_new_agent_policies_are_never_silently_ignored(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eine neue Claude-Berechtigung braucht eine bewusste Codex-Entsprechung."""
    _prepare_mirror(tmp_path, monkeypatch)
    source = sync_agents.SOURCE_DIR / "probe.md"
    source.write_text(
        source.read_text(encoding="utf-8").replace(
            "tools: Read", "disallowedTools: Write\ntools: Read"
        ),
        encoding="utf-8",
    )

    with pytest.raises(sync_agents.SyncError, match="disallowedTools"):
        sync_agents.render(source)


def test_linked_skill_roots_are_rejected_before_the_source_can_be_overwritten(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein alter Junction-Spiegel darf keine Codex-Texte in die Quelle schreiben."""
    _prepare_mirror(tmp_path, monkeypatch)
    sync_agents.SKILL_DIR.parent.mkdir(parents=True)
    if os.name == "nt":
        subprocess.run(
            [
                "cmd",
                "/c",
                "mklink",
                "/J",
                str(sync_agents.SKILL_DIR),
                str(sync_agents.SOURCE_SKILL_DIR),
            ],
            check=True,
            capture_output=True,
        )
    else:
        sync_agents.SKILL_DIR.symlink_to(sync_agents.SOURCE_SKILL_DIR, target_is_directory=True)
    before = {
        path: path.read_bytes()
        for path in sync_agents.SOURCE_SKILL_DIR.rglob("*")
        if path.is_file()
    }

    assert sync_agents.main([]) == 1
    assert all(path.read_bytes() == content for path, content in before.items())
    assert not sync_agents.TARGET_DIR.exists()
