"""LLM-Backends und der Schlüssel, der aus der Projektdatei
heraushält (Bauplan §27).
"""

from __future__ import annotations

import time
from typing import Any

import pytest

from app.core.backends import keys, llm
from app.core.backends.llm import (
    AnthropicBackend,
    BackendUnavailable,
    Message,
    OllamaBackend,
    Reply,
    ToolCall,
    first_available,
    ollama_size_warning,
    parse_parameter_count,
)
from app.core.backends.scripted import ScriptedBackend
from app.core.errors import AppError


class Recorder:
    """Ein Transport, der aus einem Skript antwortet statt aus einem Netz."""

    def __init__(self, answer: dict[str, Any] | Exception) -> None:
        self.answer = answer
        self.calls: list[tuple[str, dict[str, str], dict[str, Any]]] = []

    def __call__(
        self, url: str, headers: dict[str, str], payload: dict[str, Any]
    ) -> dict[str, Any]:
        self.calls.append((url, headers, payload))
        if isinstance(self.answer, Exception):
            raise self.answer
        return self.answer


@pytest.fixture(autouse=True)
def no_stored_key(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tests erreichen nie den echten Schlüsselbund der Maschine, auf der sie
    laufen.
    """
    monkeypatch.setattr(keys, "_keyring", lambda: None)
    monkeypatch.delenv(keys.ENVIRONMENT_VARIABLE, raising=False)
    monkeypatch.delenv(f"{keys.ENVIRONMENT_VARIABLE}_ANTHROPIC", raising=False)


# --- keys ------------------------------------------------------------------------


def test_without_a_key_there_is_no_agent(monkeypatch: pytest.MonkeyPatch) -> None:
    """§27: die Agentenfunktionen grauen aus, die Anwendung bleibt voll
    nutzbar.
    """
    assert keys.read("anthropic") is None
    assert keys.source("anthropic") == "none"
    assert not AnthropicBackend().available


def test_the_environment_can_carry_the_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(keys.ENVIRONMENT_VARIABLE, "geheim")

    assert keys.read("anthropic") == "geheim"
    assert keys.source("anthropic") == "environment"


def test_a_backend_specific_key_wins(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(keys.ENVIRONMENT_VARIABLE, "allgemein")
    monkeypatch.setenv(f"{keys.ENVIRONMENT_VARIABLE}_ANTHROPIC", "genau dieser")

    assert keys.read("anthropic") == "genau dieser"


def test_the_keychain_is_used_when_there_is_one(monkeypatch: pytest.MonkeyPatch) -> None:
    class Keychain:
        def __init__(self) -> None:
            self.store: dict[tuple[str, str], str] = {}

        def get_password(self, service: str, account: str) -> str | None:
            return self.store.get((service, account))

        def set_password(self, service: str, account: str, key: str) -> None:
            self.store[(service, account)] = key

        def delete_password(self, service: str, account: str) -> None:
            del self.store[(service, account)]

    keychain = Keychain()
    monkeypatch.setattr(keys, "_keyring", lambda: keychain)

    assert keys.store("anthropic", "schluessel")
    assert keys.read("anthropic") == "schluessel"
    assert keys.source("anthropic") == "keychain"
    assert keys.forget("anthropic")
    assert keys.read("anthropic") is None


# --- the hosted backend ----------------------------------------------------------


def anthropic_answer() -> dict[str, Any]:
    return {
        "model": "claude-sonnet-4-5",
        "stop_reason": "tool_use",
        "usage": {"input_tokens": 120, "output_tokens": 30},
        "content": [
            {"type": "text", "text": "Ich setze eine Bohrung."},
            {
                "type": "tool_use",
                "id": "call_1",
                "name": "drill_hole",
                "input": {"diameter": 5.0},
            },
        ],
    }


def test_a_hosted_reply_becomes_text_and_calls(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(keys.ENVIRONMENT_VARIABLE, "geheim")
    transport = Recorder(anthropic_answer())
    backend = AnthropicBackend(transport=transport)

    reply = backend.complete(
        [Message(role="system", content="Regeln"), Message(role="user", content="Bohr das")],
        tools=[{"name": "drill_hole", "description": "x", "parameters": {"type": "object"}}],
    )

    assert reply.text == "Ich setze eine Bohrung."
    assert reply.tool_calls == (
        ToolCall(id="call_1", name="drill_hole", arguments={"diameter": 5.0}),
    )
    assert reply.wants_tools
    assert reply.input_tokens == 120


def test_the_system_prompt_travels_apart(monkeypatch: pytest.MonkeyPatch) -> None:
    """Anthropic nimmt den Systemtext als eigenes Feld, nicht als Beitrag."""
    monkeypatch.setenv(keys.ENVIRONMENT_VARIABLE, "geheim")
    transport = Recorder(anthropic_answer())

    AnthropicBackend(transport=transport).complete(
        [Message(role="system", content="Regeln"), Message(role="user", content="Hallo")]
    )

    _url, headers, payload = transport.calls[0]
    assert payload["system"] == "Regeln"
    assert [entry["role"] for entry in payload["messages"]] == ["user"]
    assert headers["x-api-key"] == "geheim"


def test_a_tool_result_goes_back_as_a_result(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(keys.ENVIRONMENT_VARIABLE, "geheim")
    transport = Recorder(anthropic_answer())

    AnthropicBackend(transport=transport).complete(
        [
            Message(role="user", content="Bohr das"),
            Message(
                role="assistant",
                tool_calls=(ToolCall(id="call_1", name="drill_hole", arguments={}),),
            ),
            Message(role="tool", tool_call_id="call_1", content="fertig"),
        ]
    )

    _url, _headers, payload = transport.calls[0]
    last = payload["messages"][-1]
    assert last["content"][0]["type"] == "tool_result"
    assert last["content"][0]["tool_use_id"] == "call_1"


def test_without_a_key_the_backend_says_so() -> None:
    with pytest.raises(BackendUnavailable):
        AnthropicBackend(transport=Recorder({})).complete([Message(role="user", content="x")])


def test_an_unreachable_model_is_an_error_with_a_suggestion(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """§33.1: jede Ausnahme trägt mindestens einen Ausweg."""
    monkeypatch.setenv(keys.ENVIRONMENT_VARIABLE, "geheim")
    transport = Recorder(BackendUnavailable(status=529, detail="overloaded"))

    with pytest.raises(AppError) as raised:
        AnthropicBackend(transport=transport).complete([Message(role="user", content="x")])
    assert raised.value.suggestions


# --- the local backend ------------------------------------------------------------


def ollama_answer() -> dict[str, Any]:
    return {
        "model": "qwen2.5-coder:14b",
        "done_reason": "stop",
        "prompt_eval_count": 90,
        "eval_count": 12,
        "message": {
            "role": "assistant",
            "content": "",
            "tool_calls": [
                {"function": {"name": "ask_user", "arguments": {"frage": "Welche Bohrung?"}}}
            ],
        },
    }


def test_the_local_backend_speaks_the_same_language() -> None:
    transport = Recorder(ollama_answer())

    reply = OllamaBackend(transport=transport).complete(
        [Message(role="user", content="Mach das Loch größer")],
        tools=[{"name": "ask_user", "parameters": {"type": "object"}}],
    )

    assert reply.tool_calls[0].name == "ask_user"
    assert reply.tool_calls[0].arguments["frage"] == "Welche Bohrung?"
    _url, _headers, payload = transport.calls[0]
    assert payload["tools"][0]["type"] == "function"
    assert payload["stream"] is False


def test_a_local_server_that_is_not_running_is_not_available() -> None:
    """Mit einem Socket gefragt, ein geschlossener Port kostet also
    Millisekunden, keine Sekunden.
    """
    backend = OllamaBackend(url="http://localhost:1/api/chat", transport=Recorder({}))

    started = time.perf_counter()
    assert not backend.available
    assert time.perf_counter() - started < 2.0


def test_without_any_backend_there_is_no_chat(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ohne Schlüssel und ohne lokales Modell gibt es keinen Chat (§27).

    Die Abwesenheit wird hergestellt, nicht vorausgesetzt: auf einem Rechner
    mit laufendem Ollama fand dieser Test eines und ging trotzdem durch, weil
    er die Maschine für den Prüfling hielt.
    """
    monkeypatch.setattr(llm, "backends", tuple)

    assert first_available() is None


# --- the scripted backend ---------------------------------------------------------


def test_the_scripted_backend_answers_in_order() -> None:
    backend = ScriptedBackend(
        answers=[
            Reply(tool_calls=(ToolCall(id="1", name="drill_hole", arguments={}),)),
            Reply(text="fertig"),
        ]
    )

    first = backend.complete([Message(role="user", content="a")])
    second = backend.complete([Message(role="user", content="b")])

    assert first.tool_calls and first.stop_reason == "tool_use"
    assert second.text == "fertig" and second.stop_reason == "end_turn"
    assert len(backend.seen) == 2


def test_the_scripted_backend_keeps_what_it_was_told() -> None:
    backend = ScriptedBackend()
    backend.complete(
        [Message(role="system", content="Regelsammlung 1"), Message(role="user", content="x")],
        tools=[{"name": "ask_user"}],
    )

    assert "Regelsammlung 1" in backend.last_system_prompt
    assert backend.tools_seen[0] == ("ask_user",)


# --- the model size check (§27) ----------------------------------------------------


def _tags(*models: tuple[str, str]) -> dict[str, Any]:
    """Eine Ollama-``/api/tags``-Antwort aus Name und Parametergröße."""
    return {
        "models": [{"name": name, "details": {"parameter_size": size}} for name, size in models]
    }


def test_parameter_sizes_are_read_in_billions() -> None:
    assert parse_parameter_count("14.8B") == pytest.approx(14.8)
    assert parse_parameter_count("7B") == pytest.approx(7.0)
    assert parse_parameter_count("780M") == pytest.approx(0.78)
    assert parse_parameter_count("unfug") is None
    assert parse_parameter_count("") is None


def test_a_small_model_gets_the_sentence_from_the_spec() -> None:
    """§27: kleine Modelle scheitern an Werkzeugaufrufen reproduzierbar — der
    Satz dazu fällt bei der Einrichtung, nicht erst beim Scheitern.
    """
    warning = ollama_size_warning("llama3.2:3b", fetch=lambda url: _tags(("llama3.2:3b", "3.2B")))

    assert warning is not None
    assert "Milliarden" in str(warning)


def test_a_big_model_passes_in_silence() -> None:
    assert (
        ollama_size_warning(
            "qwen2.5-coder:14b", fetch=lambda url: _tags(("qwen2.5-coder:14b", "14.8B"))
        )
        is None
    )


def test_a_missing_model_is_its_own_answer() -> None:
    """Ein eingestelltes Modell, das nicht installiert ist, scheitert beim
    ersten Zug genauso still — auch das wird bei der Einrichtung gesagt.
    """
    warning = ollama_size_warning("qwen2.5-coder:14b", fetch=lambda url: _tags())

    assert warning is not None
    assert "nicht installiert" in str(warning)


def test_a_model_without_a_tag_matches_its_latest() -> None:
    """Ollama behandelt „modell" als „modell:latest" — die Prüfung auch."""
    assert (
        ollama_size_warning(
            "qwen2.5-coder", fetch=lambda url: _tags(("qwen2.5-coder:latest", "14.8B"))
        )
        is None
    )


def test_a_silent_server_is_not_an_error() -> None:
    """Antwortet der Server nicht, meldet sich der Chat ohnehin ab — eine
    Warnung obendrauf wäre geraten.
    """

    def fail(url: str) -> dict[str, Any]:
        raise OSError("no route to host")

    assert ollama_size_warning("qwen2.5-coder:14b", fetch=fail) is None


def test_an_unknown_size_claims_nothing() -> None:
    warning = ollama_size_warning("mystery", fetch=lambda url: _tags(("mystery", "keine Angabe")))

    assert warning is None
