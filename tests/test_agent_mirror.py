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
