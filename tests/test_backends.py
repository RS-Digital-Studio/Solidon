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
    ollama_tool_check,
    parse_parameter_count,
    takes_temperature,
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
