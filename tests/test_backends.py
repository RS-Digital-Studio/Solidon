"""LLM-Backends und der Schlüssel, der aus der Projektdatei
heraushält (Bauplan §27).
"""

from __future__ import annotations

import json
import time
from typing import Any

import pytest

from app.core.backends import keys, llm
from app.core.backends.llm import (
    AnthropicBackend,
    BackendAnswerUnreadable,
    BackendUnavailable,
    Message,
    OllamaBackend,
    Reply,
    ToolCall,
    first_available,
    ollama_size_warning,
    ollama_tool_check,
    parse_parameter_count,
    takes_temperature,
)
from app.core.backends.scripted import ScriptedBackend
from app.core.errors import AppError, ExternalToolError, InternalError


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


# --- das gehostete Backend -------------------------------------------------------


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
    assert payload["system"][0]["text"] == "Regeln"
    assert [entry["role"] for entry in payload["messages"]] == ["user"]
    assert headers["x-api-key"] == "geheim"


def test_the_stable_prefix_is_marked_for_caching(monkeypatch: pytest.MonkeyPatch) -> None:
    """Systemprompt und Werkzeugschemata sind über alle Schritte eines Zuges
    identisch — rund 99 KB, bis zu acht Mal je Zug. Die ``cache_control``-
    Markierung auf dem Systemblock und dem letzten Schema lässt die Gegenseite
    das ganze stabile Präfix zwischenspeichern, statt es je Schritt neu zu
    verrechnen (Konzept Agent-Vertiefung 2.3).
    """
    monkeypatch.setenv(keys.ENVIRONMENT_VARIABLE, "geheim")
    transport = Recorder(anthropic_answer())

    AnthropicBackend(transport=transport).complete(
        [Message(role="system", content="Regeln"), Message(role="user", content="Bohr das")],
        tools=[
            {"name": "drill_hole", "input_schema": {"type": "object"}},
            {"name": "ask_user", "input_schema": {"type": "object"}},
        ],
    )

    _url, _headers, payload = transport.calls[0]
    assert payload["system"][-1]["cache_control"] == {"type": "ephemeral"}
    assert "cache_control" not in payload["tools"][0], "eine Markierung je Präfix genügt"
    assert payload["tools"][-1]["cache_control"] == {"type": "ephemeral"}


def test_the_answer_budget_is_a_parameter_capped_by_the_turn(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """``max_tokens`` war eine Konstante (4096) neben einem Zugbudget von
    120 000. Jetzt ist es ein Parameter mit Vorgabe 8192, und das verbleibende
    Zugbudget deckelt ihn je Aufruf — nie umgekehrt.
    """
    monkeypatch.setenv(keys.ENVIRONMENT_VARIABLE, "geheim")

    transport = Recorder(anthropic_answer())
    AnthropicBackend(transport=transport).complete([Message(role="user", content="x")])
    assert transport.calls[0][2]["max_tokens"] == 8192

    transport = Recorder(anthropic_answer())
    AnthropicBackend(transport=transport).complete(
        [Message(role="user", content="x")], max_output_tokens=500
    )
    assert transport.calls[0][2]["max_tokens"] == 500

    transport = Recorder(anthropic_answer())
    AnthropicBackend(transport=transport).complete(
        [Message(role="user", content="x")], max_output_tokens=999_999
    )
    assert transport.calls[0][2]["max_tokens"] == 8192, "das Budget hebt die Vorgabe nie an"


def test_views_travel_as_image_blocks(monkeypatch: pytest.MonkeyPatch) -> None:
    """§23: die Ansichten reisen neben dem Steckbrief — als base64-PNG mit
    ihrer Beschriftung davor, denn ein Bild ohne Namen lässt sich nicht
    ansprechen.
    """
    import base64

    monkeypatch.setenv(keys.ENVIRONMENT_VARIABLE, "geheim")
    transport = Recorder(anthropic_answer())
    png = b"\x89PNG\r\n\x1a\nfake"

    AnthropicBackend(transport=transport).complete(
        [Message(role="user", content="Steckbrief", images=(("Ansicht von oben", png),))]
    )

    _url, _headers, payload = transport.calls[0]
    blocks = payload["messages"][0]["content"]
    assert blocks[0] == {"type": "text", "text": "Steckbrief"}
    assert blocks[1] == {"type": "text", "text": "Ansicht von oben"}
    assert blocks[2]["type"] == "image"
    assert blocks[2]["source"]["media_type"] == "image/png"
    assert base64.b64decode(blocks[2]["source"]["data"]) == png
    assert AnthropicBackend().supports_images
    assert not OllamaBackend(transport=transport).supports_images


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


# --- das lokale Backend -----------------------------------------------------------


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


def test_the_local_backend_opens_a_window_big_enough_for_the_tools() -> None:
    """Ohne ``num_ctx`` schneidet Ollama den Prompt ab, und zwar stillschweigend.

    Sein Vorgabefenster ist 4096 Token; das Register bringt allein 85
    Werkzeugschemata mit rund 109 000 Zeichen. Was nicht hineinpasst, fällt weg
    — und mit ihm der Systemprompt samt der vier Vorrangregeln. Das war der
    Befund „der Agent greift nicht zu den Bausteinen (0/13)": nicht die Regel,
    nicht das Modell, sondern ein Fenster, in das die Regel nie gelangte.
    Gemessen mit `qwen3:14b`: 0 von 3 bei der Vorgabe, 3 von 3 mit 32768.
    """
    from app.core.backends.llm import OLLAMA_CONTEXT_TOKENS

    transport = Recorder(ollama_answer())
    OllamaBackend(transport=transport).complete([Message(role="user", content="Halter")])

    _url, _headers, payload = transport.calls[0]
    assert payload["options"]["num_ctx"] == OLLAMA_CONTEXT_TOKENS
    assert OLLAMA_CONTEXT_TOKENS >= 25361, "so viel brauchen die Werkzeuge allein"


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


# --- das Skript-Backend -----------------------------------------------------------


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


# --- die Prüfung der Modellgröße (§27) ---------------------------------------------


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


def test_a_model_that_calls_the_tool_passes_the_probe() -> None:
    """Die Probe fragt genau eines: kam ein Aufruf zurück oder Fließtext."""
    assert ollama_tool_check("llama3.1:8b", transport=Recorder(ollama_answer())) is True


def test_a_model_that_writes_the_call_as_text_fails_the_probe() -> None:
    """Das reale Fehlerbild: das Modell gibt den Aufruf als JSON im Inhalt aus.

    Ollama kann ihn dann nicht auslesen, `tool_calls` bleibt leer, und die
    Agentenschicht sieht Prosa, wo sie eine Operation erwartet. Weder die
    Parameterzahl noch die gemeldete Fähigkeit verrät das vorher — nur ein
    echter Zug.
    """
    prosa = {
        "model": "qwen2.5-coder:14b",
        "message": {
            "role": "assistant",
            "content": '{"name": "set_length", "arguments": {"value": 20}}',
        },
    }

    assert ollama_tool_check("qwen2.5-coder:14b", transport=Recorder(prosa)) is False


def test_a_probe_without_an_answer_claims_nothing() -> None:
    """Ein Server, der schweigt, meldet sich über `available` ab — eine
    Behauptung obendrauf wäre geraten.
    """

    def fail(url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
        raise OSError("no route to host")

    assert ollama_tool_check("llama3.1:8b", transport=fail) is None


def test_the_probe_asks_with_a_tool_that_has_a_required_field() -> None:
    """Ohne Pflichtfeld könnte ein leeres Objekt als Aufruf durchgehen."""
    recorder = Recorder(ollama_answer())

    ollama_tool_check("llama3.1:8b", transport=recorder)

    _url, _headers, payload = recorder.calls[0]
    schema = payload["tools"][0]["function"]["parameters"]
    assert schema["required"] == ["value"]


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


#: Freistellmodelle, die ein verkauftes Programm nicht vorgeben darf.
#:
#: ``RMBG-2.0`` steht unter CC BY-NC 4.0 — nicht-kommerziell. Es stand als
#: Vorgabe in beiden mitgelieferten Graphen: der zahlende Nutzer landete ohne
#: Zutun im nicht-kommerziellen Modell, ohne dass irgendwo ein Wort dazu stand.
#: ``INSPYRENET`` (MIT) tut dasselbe und darf es.
NON_COMMERCIAL_MODELS = ("RMBG-2.0", "rmbg-2.0", "BEN2")


def test_the_shipped_graphs_name_no_non_commercial_model() -> None:
    """§36: Was mitgeliefert wird, muss auch verkauft werden dürfen.

    Geprüft wird der Text der Graphen und nicht ein geladener Knoten: die
    Datei ist das, was ausgeliefert wird, und ein Modellname darin ist eine
    Vorgabe an jeden, der sie benutzt.
    """
    from pathlib import Path

    import app.core.backends as backends

    ordner = Path(backends.__file__).parent / "data"
    graphen = sorted(ordner.glob("*.json"))
    assert graphen, "ohne Graphen prüft dieser Test nichts"
    for graph in graphen:
        text = graph.read_text(encoding="utf-8")
        for modell in NON_COMMERCIAL_MODELS:
            assert modell not in text, (
                f"{graph.name} nennt {modell} — dessen Lizenz erlaubt keine "
                "kommerzielle Nutzung (§36)"
            )


def test_temperature_reaches_only_a_model_that_still_takes_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ab Claude Opus 4.7 ist ``temperature`` entfernt, und ein
    Nicht-Standardwert liefert einen 400er — der Aufruf scheitert also
    vollständig. Das Backend sendet den Parameter deshalb nur noch an Modelle,
    die ihn annehmen; bei allen anderen fehlt er, und die Gegenseite nimmt
    ihren eigenen Vorgabewert.

    Geprüft wird über eine Positivliste, nicht über eine Sperrliste: Ein
    unbekanntes Modell soll in „nicht senden" fallen, denn das ist immer
    zulässig — eine vergessene Sperrzeile wäre ein harter Fehler.
    """
    monkeypatch.setenv(keys.ENVIRONMENT_VARIABLE, "geheim")

    transport = Recorder(anthropic_answer())
    AnthropicBackend(model="claude-sonnet-4-5", transport=transport).complete(
        [Message(role="user", content="x")]
    )
    assert transport.calls[0][2]["temperature"] == 0.0, "die älteren Modelle nehmen ihn"

    transport = Recorder(anthropic_answer())
    AnthropicBackend(transport=transport).complete([Message(role="user", content="x")])
    assert "temperature" not in transport.calls[0][2], "die heutige Vorgabe nimmt ihn nicht"

    for model in ("claude-opus-4-7", "claude-opus-5", "claude-sonnet-5", "claude-fable-5"):
        transport = Recorder(anthropic_answer())
        AnthropicBackend(model=model, transport=transport).complete(
            [Message(role="user", content="x")]
        )
        assert "temperature" not in transport.calls[0][2], model

    transport = Recorder(anthropic_answer())
    AnthropicBackend(model="claude-etwas-noch-nicht-erschienenes", transport=transport).complete(
        [Message(role="user", content="x")]
    )
    assert "temperature" not in transport.calls[0][2], "unbekannt heißt: nicht senden"


def test_a_model_alias_and_its_snapshot_are_judged_alike() -> None:
    """Dieselbe Version ist unter zwei Namen erreichbar — dem Alias und dem
    Schnappschuss mit Datum. Wer nur den Alias prüft, schickt an den
    Schnappschuss keinen Parameter und an den Alias einen.
    """
    assert takes_temperature("claude-sonnet-4-5")
    assert takes_temperature("claude-sonnet-4-5-20250929")
    assert not takes_temperature("claude-opus-5")


# --- Ein Modell holen, ohne Terminal (§27) ----------------------------------------


def test_the_installed_models_come_from_the_server() -> None:
    """Die Auswahl im Einrichtungsdialog braucht sie — ein Textfeld setzte
    voraus, dass man den Namen kennt.
    """
    found = llm.installed_models(fetch=lambda url: _tags(("qwen3:14b", "14.8B")))

    assert found == ("qwen3:14b",)


def test_a_silent_server_offers_no_models_and_no_error() -> None:
    def fail(url: str) -> dict[str, Any]:
        raise OSError("no route to host")

    assert llm.installed_models(fetch=fail) == ()


def test_every_suggested_model_says_its_size_and_what_it_does() -> None:
    """Zwischen fünf und neun Gigabyte liegt eine Entscheidung.

    Ein Modellname allein hilft nicht: Der Download ist groß, und ob das
    Modell Werkzeuge aufruft, ist die eigentliche Frage. Beides steht am
    Eintrag, nicht in einer Fußnote.
    """
    assert llm.OLLAMA_SUGGESTIONS, "ohne Vorschlag ist die Liste ein leeres Feld"
    for name, gigabytes, what in llm.OLLAMA_SUGGESTIONS:
        assert ":" in name, f"{name}: ein Ollama-Name trägt seinen Tag"
        assert 0.5 < gigabytes < 100.0, name
        assert str(what), name
    names = [name for name, _size, _what in llm.OLLAMA_SUGGESTIONS]
    assert llm.DEFAULT_OLLAMA_MODEL in names, "das eingestellte Modell steht zur Auswahl"


class _PullServer:
    """Ollamas Antwort auf ``/api/pull``: eine Zeile JSON je Zustand."""

    def __init__(self, lines: list[bytes]) -> None:
        self.lines = lines
        self.asked = ""

    def __call__(self, request: Any, timeout: float = 0.0) -> Any:
        import json as json_module

        self.asked = request.full_url
        self.payload = json_module.loads(request.data.decode("utf-8"))
        return self

    def __enter__(self) -> Any:
        return iter(self.lines)

    def __exit__(self, *_args: object) -> None:
        return None


def test_pulling_a_model_reports_a_real_share(monkeypatch: pytest.MonkeyPatch) -> None:
    """Neun Gigabyte an einem unbestimmten Balken sehen aus wie ein Hänger.

    Ollama trägt in seinen Fortschrittszeilen ``total`` und ``completed`` —
    daraus wird ein Prozentwert, und der ist der Unterschied zwischen einem
    Vorgang und einem Verdacht.
    """
    server = _PullServer(
        [
            b'{"status":"pulling manifest"}\n',
            b'{"status":"pulling 1a2b","total":1000,"completed":250}\n',
            b'{"status":"pulling 1a2b","total":1000,"completed":1000}\n',
            b'{"status":"success"}\n',
        ]
    )
    monkeypatch.setattr(llm.urllib.request, "urlopen", server)
    seen: list[tuple[str, float]] = []

    problem = llm.pull_model("qwen3:14b", progress=lambda step, share: seen.append((step, share)))

    assert problem is None
    assert server.asked.endswith("/api/pull")
    assert server.payload["model"] == "qwen3:14b", "der Name geht so hinaus, wie er hereinkam"
    assert seen[0] == ("pulling manifest", -1.0), "ohne Zahlen wird keine behauptet"
    assert seen[1][1] == pytest.approx(0.25)
    assert seen[2][1] == pytest.approx(1.0)


def test_a_pull_can_be_stopped_and_says_it_continues(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ein Vorgang dieser Länge ohne Ausgang wäre die Sackgasse aus §2.8.

    Und der Satz dazu ist keine Höflichkeit: Ollama behält, was schon geladen
    ist. Wer das nicht weiß, fängt von vorn an.
    """
    server = _PullServer([b'{"status":"pulling","total":10,"completed":1}\n'] * 5)
    monkeypatch.setattr(llm.urllib.request, "urlopen", server)

    problem = llm.pull_model("qwen3:14b", cancelled=lambda: True)

    assert problem is not None
    assert "setzt fort" in str(problem)


def test_a_pull_that_ollama_refuses_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ein Name, den Ollama nicht kennt, kommt als Fehlerzeile zurück — nicht
    als Download, der nie endet.
    """
    server = _PullServer([b'{"error":"pull model manifest: file does not exist"}\n'])
    monkeypatch.setattr(llm.urllib.request, "urlopen", server)

    problem = llm.pull_model("gibtesnicht:1b")

    assert problem is not None
    assert "nicht angenommen" in str(problem)


def test_a_pull_without_a_server_blames_the_server(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail(request: Any, timeout: float = 0.0) -> Any:
        raise OSError("connection refused")

    monkeypatch.setattr(llm.urllib.request, "urlopen", fail)

    problem = llm.pull_model("qwen3:14b")

    assert problem is not None
    assert "läuft es noch" in str(problem)


def test_a_dropped_connection_is_not_a_program_fault(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ein Verbindungsabbruch ist ein Fremdprogramm-Fehler, kein Absturz.

    **Gemeldet von einem Kunden mit 0.1.5** (Vorgang S-20260826-1db075), auf
    Englisch und knapp: „Try to use Ollama, after many attempts, the program
    crashed." Im Bericht stand:

        An unexpected error occurred in the application.
        ConnectionResetError: [WinError 10054] An existing connection was
        forcibly closed by the remote host

    Das ist **der Zwilling** des Zeitlimits im Test darunter, und die Ursache
    ist dieselbe Lücke in ``post_json``: Beim Verbindungsaufbau wickelt urllib
    einen Abbruch in ``URLError``; beim **Lesen der Antwort** kommt der nackte
    ``ConnectionResetError`` durch. Ollama macht die Verbindung genau dort zu,
    wenn ihm ein Modell zu groß wird oder der Dienst neu startet — nach
    „vielen Versuchen" ist das der wahrscheinlichste Ausgang.

    Gefangen wird ``ConnectionError`` und nicht nur die eine Klasse: Abbruch
    (``Reset``), Abbruch durch die eigene Seite (``Aborted``), verweigerte
    Annahme (``Refused``) und die geschlossene Gegenstelle (``BrokenPipe``)
    sind für den Kunden dieselbe Lage und verdienen denselben Satz.
    """
    for klasse in (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):

        def abgerissen(request: Any, timeout: float = 0.0, fehler: type = klasse) -> Any:
            raise fehler(10054, "An existing connection was forcibly closed")

        monkeypatch.setattr(llm.urllib.request, "urlopen", abgerissen)
        with pytest.raises(llm.BackendUnavailable) as gefangen:
            llm.post_json("http://127.0.0.1:11434/api/chat", {}, {})

        # Regel 17: nie „unerwarteter Fehler", immer ein Satz, der weiterführt.
        assert "unerwartet" not in str(gefangen.value.title).lower(), klasse.__name__


def test_a_slow_local_model_is_not_a_program_fault(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ein Zeitlimit ist ein Fremdprogramm-Fehler, kein Absturz.

    **Gemeldet vom ersten Kunden mit 0.1.3.** Er ließ den Agenten auf einem
    lokalen ``qwen3:8b`` rechnen, und nach 122 Sekunden stand da:

        Im Programm ist ein unerwarteter Fehler aufgetreten.
        TimeoutError: timed out

    Das ist die falsche Klasse und der falsche Satz. Ein lokales Modell, das
    lange rechnet, ist kein Programmfehler — es ist genau das, wovor Solidon
    im Chat selbst warnt („für einen Werkzeugaufruf zwei Minuten"). Der Kunde
    bekam die Aufforderung, einen Fehlerbericht zu schicken, statt eines
    Satzes, der sagt, was zu tun ist.

    Die Ursache ist eine Lücke in ``post_json``: Es fängt ``HTTPError`` und
    ``URLError``, und beim **Verbindungsaufbau** wickelt urllib ein Zeitlimit
    auch in ``URLError``. Beim **Lesen der Antwort** nicht — dort kommt der
    nackte ``TimeoutError`` durch, und genau dort stand er im Protokoll
    (``http/client.py`` → ``socket.readinto``).
    """

    def zu_langsam(request: Any, timeout: float = 0.0) -> Any:
        raise TimeoutError("timed out")

    monkeypatch.setattr(llm.urllib.request, "urlopen", zu_langsam)

    with pytest.raises(llm.BackendTooSlow) as gefangen:
        llm.post_json("http://127.0.0.1:11434/api/chat", {}, {})

    problem = gefangen.value
    assert problem.suggestions, "Regel 17: ein Fehler endet nie ohne Handlungsvorschlag"
    text = f"{problem.title} {problem.detail}"
    assert "Zeit" in text or "lange" in text, f"der Satz nennt den Grund nicht: {text!r}"


def test_a_local_model_gets_more_time_than_a_hosted_one() -> None:
    """Zwei Minuten sind für ein lokales Modell keine Frist, sondern ein Abbruch.

    Der Kunde riss bei 122 Sekunden — das Limit stand auf 120. Ein gehostetes
    Modell antwortet in Sekunden, ein lokales rechnet Minuten; dieselbe Zahl
    für beide misst beim einen die Erreichbarkeit und beim anderen die
    Rechenleistung des Kunden.

    Das Zeitlimit gilt dem **Hängen**, nicht der Langsamkeit — dieselbe Regel
    wie bei ComfyUI (``.claude/rules/kern.md``).
    """
    assert llm.LOCAL_TIMEOUT_SECONDS > llm.TIMEOUT_SECONDS
    assert llm.LOCAL_TIMEOUT_SECONDS >= 600.0, "unter zehn Minuten ist kein Hängen, sondern Rechnen"
    assert llm.OllamaBackend().transport is llm.post_json_local


# --- Die Adresse, die der Kunde einträgt (24.08.2026) ------------------------------


def test_every_way_a_person_writes_the_ollama_address_finds_the_endpoint() -> None:
    """Was ein Werkzeug über sich selbst sagt, tippt der Kunde ein.

    Ollamas eigene Ausgabe nennt ``http://127.0.0.1:11434`` — die Basisadresse
    ohne Endpunkt ist damit die *wahrscheinlichste* Eingabe. Bis zum 24.08.2026
    entstand die Adresse aus ``replace("/api/chat", …)``, griff bei genau dieser
    Eingabe nicht, und jede Anfrage ging an die Wurzel. Gegen ein laufendes
    Ollama gemessen: POST auf die Wurzel **405**, auf ``/api/pull`` **200**.
    """
    for written in (
        "http://localhost:11434/api/chat",
        "http://127.0.0.1:11434",
        "127.0.0.1:11434",
        "http://127.0.0.1:11434/",
        "  http://127.0.0.1:11434  ",
    ):
        assert llm.ollama_endpoint(written, "/api/pull").endswith("/api/pull"), written
        assert "/api/chat" not in llm.ollama_endpoint(written, "/api/pull"), written


def test_a_path_in_front_of_the_endpoint_survives() -> None:
    """Hinter einem Reverse-Proxy liegt Ollama unter ``/ollama`` — wer das
    einträgt, meint es.

    Die Sollwerte stehen hier von Hand und sind **nicht** mit der geprüften
    Funktion erzeugt: sonst prüfte dieser Test, ob sie sich seit gestern
    geändert hat, und nicht, ob sie recht hat.
    """
    erwartet = {
        # Was der Endpunkt ist, wird ersetzt …
        "http://localhost:11434/api/chat": "http://localhost:11434/api/pull",
        "http://host/api/": "http://host/api/pull",
        "http://host/api": "http://host/api/pull",
        # … was davor steht, bleibt.
        "http://h/ollama/api/chat": "http://h/ollama/api/pull",
        "http://h/ollama": "http://h/ollama/api/pull",
        # Und ein Pfad, der nur so *anfängt*, ist kein Endpunkt. Beide Zeilen
        # hat eine erste Fassung dieser Funktion abgeschnitten — sie suchte
        # ``/api`` ohne den Schrägstrich dahinter, damit ``…/api`` als Basis
        # durchginge, und nahm ``/apiary`` gleich mit.
        "http://h/apiary": "http://h/apiary/api/pull",
        "http://h/api-gateway": "http://h/api-gateway/api/pull",
        "http://h/apiary/api/chat": "http://h/apiary/api/pull",
        # Ein Zugangstoken in der Abfrage gehört dem Proxy und bleibt stehen.
        "http://host:11434/api/chat?token=x": "http://host:11434/api/pull?token=x",
        "https://fern:11434/api/chat": "https://fern:11434/api/pull",
    }

    for written, wanted in erwartet.items():
        assert llm.ollama_endpoint(written, "/api/pull") == wanted, written


def test_an_empty_address_falls_back_to_this_machine() -> None:
    assert llm.ollama_endpoint("", "/api/chat") == llm.OLLAMA_URL
    assert llm.ollama_endpoint(None, "/api/chat") == llm.OLLAMA_URL


def test_pulling_a_model_reaches_the_endpoint_from_a_bare_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Der Fall des Kunden, als Test: Basisadresse eingetragen, Modell holen.

    Vorher landete der POST auf der Wurzel, Ollama antwortete 405, und im
    Protokoll standen vierzehn davon.
    """
    server = _PullServer([b'{"status":"success"}\n'])
    monkeypatch.setattr(llm.urllib.request, "urlopen", server)

    problem = llm.pull_model("qwen3:14b", url="http://127.0.0.1:11434")

    assert problem is None
    assert server.asked == "http://127.0.0.1:11434/api/pull", server.asked


def test_the_installed_models_are_asked_from_a_bare_address() -> None:
    asked: list[str] = []

    def note(url: str) -> dict[str, Any]:
        asked.append(url)
        return _tags(("qwen3:14b", "14.8B"))

    llm.installed_models(url="127.0.0.1:11434", fetch=note)

    assert asked == ["http://127.0.0.1:11434/api/tags"]


def test_a_windows_path_in_the_address_field_is_unreachable_and_not_a_crash() -> None:
    """Ein Kunde trug dort seinen Modellordner ein.

    ``urlsplit`` liest alles hinter ``C:`` als Port und wirft beim Zugriff
    darauf ``ValueError`` — der fing niemand, und der Arbeiter des
    Einrichtungsdialogs starb mitten in der Einrichtung (Regel 17).
    """
    backend = llm.OllamaBackend(url=r"C:\Users\Jemand\.ollama\models")

    assert backend.available is False


class _Keychain:
    """Ein Schlüsselbund im Speicher — dieselbe Attrappe wie oben, nur benannt,
    weil ihn jetzt mehr als ein Test braucht."""

    def __init__(self) -> None:
        self.store: dict[tuple[str, str], str] = {}

    def get_password(self, service: str, account: str) -> str | None:
        return self.store.get((service, account))

    def set_password(self, service: str, account: str, key: str) -> None:
        self.store[(service, account)] = key

    def delete_password(self, service: str, account: str) -> None:
        del self.store[(service, account)]


# --- Ein Schlüssel, der keiner sein kann (24.08.2026) ------------------------------


def test_a_pasted_error_message_is_refused_as_a_key() -> None:
    """Der Kunde markierte die Fehlermeldung samt Knopfbeschriftung und fügte
    sie ins Schlüsselfeld ein. Ungeprüft gespeichert flog sie beim nächsten Zug
    als ``ValueError`` aus ``http.client.putheader``."""
    pasted = '{"type":"error","error":{"message":"invalid x-api-key"}}\nErneut versuchen'

    assert keys.unusable(pasted) is not None
    assert keys.store("anthropic", pasted) is False


def test_a_key_keeps_none_of_the_whitespace_it_arrived_with(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein hängengebliebenes Leerzeichen ist der häufigste Grund für einen
    Schlüssel, der „nicht geht" — und niemand sieht es ihm an."""
    # **Eine** Attrappe, nicht je Aufruf eine neue: ``store`` und ``read``
    # fragen nacheinander, und zwei Schlüsselbünde teilen sich nichts.
    keychain = _Keychain()
    monkeypatch.setattr(keys, "_keyring", lambda: keychain)

    assert keys.store("anthropic", "  sk-echt-aussehend  ")
    assert keys.read("anthropic") == "sk-echt-aussehend"


def test_an_empty_field_says_so_instead_of_storing_nothing() -> None:
    assert keys.unusable("   ") is not None


# --- Ein abgelehnter Zugang sperrt das lokale Modell nicht mehr aus ----------------


def test_a_refused_key_stops_counting_as_available(monkeypatch: pytest.MonkeyPatch) -> None:
    """``available`` fragte, ob ein Schlüssel *da* ist — nicht, ob er *gilt*.

    Ein einziger Tippversuch im Schlüsselfeld sperrte damit ein vollständig
    eingerichtetes Ollama dauerhaft aus: Anthropic steht in ``backends()`` vorn
    und galt mit jedem beliebigen Text als verfügbar.
    """
    monkeypatch.setattr(keys, "read", lambda account: "sk-sieht-echt-aus")
    backend = llm.AnthropicBackend()
    assert backend.available is True

    llm.reject(backend.id)

    assert backend.available is False


def test_storing_a_new_key_is_a_new_attempt(monkeypatch: pytest.MonkeyPatch) -> None:
    """Was die Gegenseite abgelehnt hat, war ein *anderer* Schlüssel."""
    monkeypatch.setattr(keys, "_keyring", lambda: _Keychain())
    llm.reject("anthropic")

    keys.store("anthropic", "sk-der-neue")

    assert "anthropic" not in llm._rejected


def test_an_authentication_error_marks_the_backend_and_names_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Zwei Zusagen in einem Zug: Der Zugang gilt danach als abgelehnt, und die
    Meldung nennt den Anbieter.

    Der Kunde richtete Ollama ein und las „Das Sprachmodell hat nicht
    geantwortet" über einem Anthropic-Schlüsselfehler. Geantwortet *hatte*
    eines — nur ein anderes als das eingerichtete.
    """
    monkeypatch.setattr(keys, "read", lambda account: "sk-abgelaufen")

    def refuse(url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
        raise llm.BackendUnavailable(status=401, detail="invalid x-api-key")

    backend = llm.AnthropicBackend(transport=refuse)
    with pytest.raises(llm.BackendUnavailable) as raised:
        backend.complete([Message(role="user", content="hallo")])

    assert raised.value.values["provider"] == "anthropic"
    assert backend.available is False, "derselbe Schlüssel wird nicht noch einmal geschickt"


def test_the_chat_falls_back_to_the_local_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Der Sinn des Ganzen: Nach der Ablehnung wählt der Chat das nächste
    Modell, statt bis zum Neustart denselben Fehler zu melden."""
    monkeypatch.setattr(keys, "read", lambda account: "sk-abgelaufen")
    monkeypatch.setattr(llm.OllamaBackend, "available", property(lambda self: True))
    # ``conftest`` leert die Backend-Liste, damit die Suite nicht nach einem
    # echten Modell auf dieser Maschine sucht. Genau die Liste ist hier die
    # Sache — das Original steht unter eigenem Namen bereit.
    monkeypatch.setattr(llm, "backends", llm.unpatched_backends)
    assert llm.first_available() is not None
    assert llm.first_available().id == "anthropic"

    llm.reject("anthropic")

    assert llm.first_available().id == "ollama"


# --- Vier Wege zu Ollama, und drei fingen den Pfad nicht --------------------------


def test_no_way_to_ollama_turns_a_typo_into_a_program_error() -> None:
    """Gefunden von ``3d-druck-61`` im Review von ``335c204``.

    ``available`` fragt die Adresse selbst und sah einen ``ValueError`` aus
    ``urllib.parse``. Die drei Wege über ``http.client`` bekommen für denselben
    Pfad ein ``InvalidURL``, und das erbt von ``HTTPException`` — **weder von
    ``ValueError`` noch von ``OSError``**. Der Kunde hätte also weiter einen
    Programmfehler samt Bitte um einen Fehlerbericht bekommen, sobald der
    Einrichtungsdialog die Modellliste holt (Regel 17).

    Geprüft wird der **Weg**, nicht die Ausnahme: Was eine unbrauchbare Adresse
    wirft, ist Sache der Bibliothek und kann sich ändern. Dass hier nichts
    herausfliegt, ist unsere Zusage.
    """
    path = r"C:\Users\Jemand\.ollama\models"

    assert llm.installed_models(path) == ()
    assert llm.ollama_size_warning("qwen3:14b", url=path) is None
    assert llm.pull_model("qwen3:14b", url=path) is not None, "ein Satz, keine Ausnahme"


def test_an_address_without_a_scheme_is_no_program_error_either() -> None:
    """``urllib.request.Request`` wirft selbst, bevor irgendetwas sendet —
    gemessen an ``://kaputt``. In ``pull_model`` stand sein Aufruf eine Zeile
    **über** dem ``try``, also außerhalb.
    """
    assert llm.pull_model("qwen3:14b", url="://kaputt") is not None


# --- Antworten, die keine sind (Review 25.08.2026) --------------------------------


def unreadable(raw: bytes) -> BackendAnswerUnreadable:
    """Was :func:`llm.post_json` aus diesen Bytes macht — der Fehler, nicht der
    Wert."""
    with pytest.raises(BackendAnswerUnreadable) as gefangen:
        llm._as_object(raw, "http://127.0.0.1:11434/api/chat")
    return gefangen.value


def test_a_login_page_from_a_proxy_is_no_program_error() -> None:
    """**Ein Firmenproxy antwortet mit HTML, und das ist kein Programmfehler.**

    ``json.loads`` warf einen ``ValueError``, den niemand fing: Der Kunde las
    „Im Programm ist ein unerwarteter Fehler aufgetreten" samt Bitte um einen
    Fehlerbericht — für eine Adresse, die er selbst ändern kann.
    """
    problem = unreadable(b"<!DOCTYPE html><html><body>Bitte anmelden</body></html>")

    assert isinstance(problem, ExternalToolError), "eine Sache der Umgebung, nicht des Programms"
    assert not isinstance(problem, InternalError)
    assert "html" in str(problem.values["answer"]).lower(), "der Anfang der Antwort steht dabei"
    assert [action.id for action in problem.suggestions], "und ein Weg weiter (Regel 17)"


def test_a_json_list_is_not_an_answer_either() -> None:
    """``dict(json.loads(...))`` warf für eine Liste — dieselbe Familie."""
    problem = unreadable(b'[{"error": "no such model"}]')

    assert isinstance(problem, ExternalToolError)
    assert "no such model" in str(problem.values["answer"])


def test_a_text_content_block_does_not_crash_the_hosted_path() -> None:
    """``content`` als Zeichenkette ließ die Schleife über *Zeichen* laufen und
    ``block.get`` einen ``AttributeError`` werfen.
    """
    with pytest.raises(BackendAnswerUnreadable):
        llm._from_anthropic({"content": "Ich setze eine Bohrung.", "usage": {}})


def test_a_message_that_is_no_object_is_reported_and_not_crashed() -> None:
    with pytest.raises(BackendAnswerUnreadable):
        llm._from_ollama({"message": "fertig"}, "qwen3:14b")


def test_tool_arguments_as_json_text_are_read_and_not_refused() -> None:
    """**Der Normalfall bei OpenAI-kompatiblen Servern**, nicht die Ausnahme:
    ``arguments`` ist dort eine Zeichenkette mit JSON darin. ``dict("{…}")``
    warf, und der ganze Zug endete als Programmfehler — obwohl der Aufruf
    lesbar dastand.
    """
    reply = llm._from_ollama(
        {
            "message": {
                "content": "",
                "tool_calls": [
                    {"function": {"name": "drill_hole", "arguments": '{"diameter": 5.0}'}}
                ],
            }
        },
        "qwen3:14b",
    )

    assert reply.tool_calls[0].arguments == {"diameter": 5.0}


def test_arguments_that_are_no_json_are_marked_as_unreadable() -> None:
    """Nicht lesbar heißt hier nicht „Ausnahme" — aber auch nicht „leer".

    Das leere Objekt stand hier als der harmlose Ausgang: Die Schemaprüfung der
    Sitzung mache daraus eine Meldung, die das Modell korrigieren kann (§26.5).
    Bei einer Operation mit ``consumes=0`` tut sie das nicht — sie füllt jeden
    nicht verlangten Parameter mit seiner Vorgabe, und aus einem unlesbaren
    Aufruf wird ein Vorgabekörper mit der Antwort „Ausgeführt" (Regel 21).

    Ein Aufruf, der nicht zu lesen war, trägt jetzt eine erkennbare Spur.
    ``UnreadableArguments`` ist trotzdem ein ``dict``: Wer die Spur nicht liest,
    bekommt das bisherige Verhalten und keine Ausnahme.
    """
    reply = llm._from_ollama(
        {"message": {"tool_calls": [{"function": {"name": "drill_hole", "arguments": "5 mm"}}]}},
        "qwen3:14b",
    )

    assert isinstance(reply.tool_calls[0].arguments, llm.UnreadableArguments)
    assert reply.tool_calls[0].arguments == {}, (
        "und bleibt für jeden anderen Leser ein leeres Objekt"
    )
    assert reply.tool_calls[0].name == "drill_hole"


def test_arguments_that_are_really_empty_are_not_marked() -> None:
    """Die Gegenprobe: ``{}`` als Argumentliste ist gültig und häufig.

    ``read_report`` und ``read_digest`` werden ohne Argumente aufgerufen — eine
    Markierung, die auch sie trifft, machte aus jedem dieser Aufrufe eine
    Ablehnung.
    """
    reply = llm._from_ollama(
        {"message": {"tool_calls": [{"function": {"name": "read_report", "arguments": "{}"}}]}},
        "qwen3:14b",
    )

    assert reply.tool_calls[0].arguments == {}
    assert not isinstance(reply.tool_calls[0].arguments, llm.UnreadableArguments)


def test_a_usage_count_that_is_no_number_counts_zero() -> None:
    """``int("viele")`` machte aus einer schrägen Angabe einen Programmfehler."""
    reply = llm._from_ollama(
        {"message": {"content": "gut"}, "prompt_eval_count": "viele"}, "qwen3:14b"
    )

    assert reply.input_tokens == 0
    assert reply.text == "gut"


def test_content_blocks_from_a_local_server_become_text() -> None:
    reply = llm._from_ollama(
        {"message": {"content": [{"text": "halb "}, {"text": "und halb"}]}}, "qwen3:14b"
    )

    assert reply.text == "halb und halb"


# --- was ein Zug wirklich gekostet hat --------------------------------------------


def test_the_cached_tokens_count_towards_the_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    """**Der Deckel maß den kleinsten Teil.** Dieser Weg markiert Systemblock
    und Werkzeugliste für den Zwischenspeicher der Gegenseite; ``input_tokens``
    zählt dann nur, was **neu** verrechnet wurde. Zugbudget (§26.5) und
    Kostenanzeige lasen genau diese Zahl.
    """
    monkeypatch.setenv(keys.ENVIRONMENT_VARIABLE, "geheim")
    answer = anthropic_answer()
    answer["usage"] = {
        "input_tokens": 120,
        "cache_creation_input_tokens": 19000,
        "cache_read_input_tokens": 6000,
        "output_tokens": 30,
    }

    reply = AnthropicBackend(transport=Recorder(answer)).complete(
        [Message(role="user", content="Bohr das")]
    )

    assert reply.input_tokens == 25120, "alle drei Felder, nicht nur das kleinste"
    assert reply.output_tokens == 30


def test_the_budget_weighs_a_cache_read_at_a_tenth(monkeypatch: pytest.MonkeyPatch) -> None:
    """**Zwei Fragen, zwei Zahlen.** Wie viele Token geflossen sind, sagt
    ``input_tokens``; was der Schritt vom Zugbudget nimmt, ``budget_input_tokens``.

    Die Summe als Deckel zu nehmen war der Fehler dahinter: Die markierte
    Werkzeugliste geht in jedem Schritt erneut als Cache-Lesung durch die
    Zählung und kostet dort ein Zehntel. Gewichtet steht hier also ein Zug von
    25 120 geflossenen Token mit 24 470 im Budget — teuer, weil er den
    Zwischenspeicher gerade **anlegt** (das 1,25-fache); der nächste Schritt
    liest ihn nur noch.
    """
    monkeypatch.setenv(keys.ENVIRONMENT_VARIABLE, "geheim")
    answer = anthropic_answer()
    answer["usage"] = {
        "input_tokens": 120,
        "cache_creation_input_tokens": 19000,
        "cache_read_input_tokens": 6000,
        "output_tokens": 30,
    }

    reply = AnthropicBackend(transport=Recorder(answer)).complete(
        [Message(role="user", content="Bohr das")]
    )

    assert reply.cache_write_tokens == 19000
    assert reply.cache_read_tokens == 6000
    assert reply.input_tokens == 25120, "die Kostenzeile bekommt die ungewichtete Summe"
    assert reply.budget_input_tokens == 24470, "120 + 1,25 * 19000 + 0,1 * 6000"


def test_a_reply_without_cache_numbers_weighs_itself(monkeypatch: pytest.MonkeyPatch) -> None:
    """Der lokale Weg meldet keinen Zwischenspeicher, und ein selbst gebautes
    :class:`Reply` auch nicht. Dann ist die gewichtete Zahl die Rohsumme — sonst
    hinge an der Gewichtung eine zweite Bedingung, die niemand kennt.
    """
    monkeypatch.setenv(keys.ENVIRONMENT_VARIABLE, "geheim")
    local = llm._from_ollama({"message": {"content": "gut"}, "prompt_eval_count": 900}, "qwen3:14b")

    assert local.budget_input_tokens == 900 == local.input_tokens
    assert Reply(input_tokens=7).budget_input_tokens == 7


def test_a_token_count_that_is_too_large_counts_zero() -> None:
    """JSON kennt kein Unendlich und schreibt es trotzdem hin.

    ``1e400`` wird beim Lesen zu ``inf``, und daraus wird kein ``int``: Das ist
    ein ``OverflowError``, nicht der ``ValueError``, den der Nachbar unten
    abfängt. Gefangen wurde also nur die eine Hälfte, und die andere machte aus
    einer schrägen Zahl einen Programmfehler samt Bitte um Fehlerbericht.
    """
    reply = llm._from_anthropic(
        json.loads('{"content": [], "usage": {"input_tokens": 1e400, "output_tokens": 12}}')
    )

    assert reply.input_tokens == 0
    assert reply.output_tokens == 12, "die brauchbare Zahl daneben bleibt brauchbar"


def test_a_truncated_answer_says_so(monkeypatch: pytest.MonkeyPatch) -> None:
    """``stop_reason`` wurde gespeichert und nie gelesen."""
    monkeypatch.setenv(keys.ENVIRONMENT_VARIABLE, "geheim")
    answer = anthropic_answer()
    answer["stop_reason"] = "max_tokens"

    reply = AnthropicBackend(transport=Recorder(answer)).complete(
        [Message(role="user", content="Bohr das")]
    )

    assert reply.truncated and not reply.refused


def test_a_refusal_is_told_apart_from_an_empty_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(keys.ENVIRONMENT_VARIABLE, "geheim")
    answer = anthropic_answer()
    answer["stop_reason"] = "refusal"

    reply = AnthropicBackend(transport=Recorder(answer)).complete(
        [Message(role="user", content="Bohr das")]
    )

    assert reply.refused and not reply.truncated
    assert not Reply().refused, "ohne Grund wird nichts behauptet"


def test_the_speed_probe_goes_through_the_endpoint_like_everything_else() -> None:
    """**Genau der Kunde mit der krummen Adresse bekam keine Warnung.**

    ``ollama_speed`` schickte an die rohe Eingabe. „127.0.0.1:11434" — die
    Schreibweise, die Ollama selbst ausgibt — landete damit nicht bei
    ``/api/chat``, die Messung schlug fehl, und die Langsam-Warnung blieb aus.
    """
    gesehen: list[str] = []

    def transport(url: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
        gesehen.append(url)
        return {"prompt_eval_count": 19249, "prompt_eval_duration": 10_000_000_000}

    speed = llm.ollama_speed("qwen3:14b", url="127.0.0.1:11434", transport=transport)

    assert gesehen == ["http://127.0.0.1:11434/api/chat"]
    assert speed.tokens_per_second is not None, "gemessen, weil die Anfrage ankam"


def test_an_installed_model_says_what_it_can_do() -> None:
    """Auch das installierte Modell trägt seinen Satz, nicht nur das empfohlene.

    In der Auswahl standen die installierten Modelle **ohne Zusatz** — „sie
    sind einen Klick entfernt". Damit sah ein Modell, das Werkzeuge gar nicht
    aufruft, aus wie ein gutes: Es schreibt die Aufrufe als Fließtext hin, und
    im Chat sieht das aus, als arbeite es.
    """
    assert llm.known_model_note("qwen3:14b") is not None, "das Vorgabemodell ist bekannt"
    assert llm.known_model_note("mistral-nemo:latest") is not None, "und das unbrauchbare"
    assert llm.known_model_note("gibt-es-nicht:7b") is None, "ein fremdes bleibt ohne Satz"


def test_the_note_does_not_hang_on_the_latest_tag() -> None:
    """``mistral-nemo`` und ``mistral-nemo:latest`` sind dasselbe Modell.

    Ollama meldet das installierte mit ``:latest``, getippt wird es ohne —
    und beim ersten Anlauf schnitt der Vergleich den Tag nur an der **Anfrage**
    ab. Solange der Eintrag ohne Tag dastand, ging das auf; seit er (zu Recht)
    einen trägt, fand die umgekehrte Richtung nichts mehr.
    """
    ohne = llm.known_model_note("mistral-nemo")
    mit = llm.known_model_note("mistral-nemo:latest")
    assert ohne is not None and mit is not None
    assert str(ohne) == str(mit), "derselbe Satz, egal wie der Name geschrieben steht"
