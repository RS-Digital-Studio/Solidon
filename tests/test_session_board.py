"""Das Sitzungsboard unterscheidet Claude Code und Codex zuverlässig."""

from __future__ import annotations

from pathlib import Path

from tools import session_board


def test_codex_sessions_get_distinct_names_and_keys(monkeypatch) -> None:
    """Zwei Codex-Aufgaben dürfen nicht denselben Board-Eintrag überschreiben."""
    monkeypatch.delenv("CLAUDE_PID", raising=False)
    monkeypatch.setenv("CODEX_THREAD_ID", "01a06cd6-8dd6-7a42-aed5-32db975ca6dc")
    monkeypatch.setenv("CODEX_SESSION_ID", "anderer-rückfall")

    assert session_board._own_name() == "Codex 01a06cd6"
    assert session_board._key() == "codex-01a06cd6-8dd6-7a42-aed5-32db975ca6dc"

    monkeypatch.setenv("CODEX_THREAD_ID", "02bbbbbb-1111-2222-3333-444444444444")

    assert session_board._own_name() == "Codex 02bbbbbb"
    assert session_board._key() == "codex-02bbbbbb-1111-2222-3333-444444444444"


def test_codex_session_id_is_used_as_fallback(monkeypatch) -> None:
    """Ohne Thread-ID bleibt die Sitzungs-ID als eindeutiger Rückfall erhalten."""
    monkeypatch.delenv("CLAUDE_PID", raising=False)
    monkeypatch.delenv("CODEX_THREAD_ID", raising=False)
    monkeypatch.setenv("CODEX_SESSION_ID", "03cccccc-1111-2222-3333-444444444444")

    assert session_board._own_name() == "Codex 03cccccc"
    assert session_board._key() == "codex-03cccccc-1111-2222-3333-444444444444"


def test_two_codex_sessions_claim_list_and_release_isolated_entries(
    monkeypatch, tmp_path: Path, capsys
) -> None:
    """Zwei Codex-Aufgaben dürfen ihre echten Board-Einträge nicht überschreiben."""
    first_id = "04dddddd-1111-2222-3333-444444444444"
    second_id = "05eeeeee-1111-2222-3333-444444444444"
    monkeypatch.setattr(session_board, "_board", lambda: tmp_path)
    monkeypatch.delenv("CLAUDE_PID", raising=False)
    monkeypatch.delenv("CLAUDE_CODE_MESSAGING_SOCKET", raising=False)
    monkeypatch.delenv("CODEX_SESSION_ID", raising=False)

    monkeypatch.setenv("CODEX_THREAD_ID", first_id)
    assert session_board.claim("Kern", "app/core/**", "") == 0

    monkeypatch.setenv("CODEX_THREAD_ID", second_id)
    assert session_board.claim("Oberfläche", "app/ui/**", "") == 0
    assert sorted(path.name for path in tmp_path.glob("*.json")) == [
        f"codex-{first_id}.json",
        f"codex-{second_id}.json",
    ]
    assert session_board.show() == 1
    assert session_board.release() == 0

    monkeypatch.setenv("CODEX_THREAD_ID", first_id)
    assert session_board.show() == 0
    assert session_board.release() == 0
    assert list(tmp_path.glob("*.json")) == []

    output = capsys.readouterr().out
    assert "Codex 04dddddd" in output
    assert "Codex 05eeeeee" in output
