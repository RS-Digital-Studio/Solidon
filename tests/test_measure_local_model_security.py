"""Fremdantwortgrenzen des manuellen Ollama-Messwerkzeugs."""

from __future__ import annotations

import hashlib
import http.server
import json
import threading
from collections.abc import Callable, Iterator
from typing import Any

import pytest

from app.core.agent.prompt import system_prompt
from app.core.agent.tools import tool_schemas
from app.core.backends import llm
from app.core.http import ResponseTooLargeError
from app.core.json_boundary import StrictJsonError
from tools import measure_local_model


class _Body:
    def __init__(self, body: bytes) -> None:
        self.body = body
        self.timeouts: list[float] = []

    def read(self, size: int = -1) -> bytes:
        chunk, self.body = self.body[:size], self.body[size:]
        return chunk

    def set_read_timeout(self, seconds: float) -> None:
        self.timeouts.append(seconds)


@pytest.mark.parametrize(
    "raw",
    [
        b'{"prompt_eval_count":NaN}',
        (b"[" * 65) + b"0" + (b"]" * 65),
    ],
)
def test_measurement_answers_refuse_unsafe_json(raw: bytes) -> None:
    with pytest.raises(StrictJsonError):
        measure_local_model._answer_json(_Body(raw), limit=4096, timeout=1.0)


def test_measurement_answers_stop_at_the_byte_limit() -> None:
    with pytest.raises(ResponseTooLargeError):
        measure_local_model._answer_json(_Body(b"12345"), limit=4, timeout=1.0)


def test_measurement_answer_accepts_the_exact_boundary() -> None:
    body = _Body(b'{"ok":true}')

    assert measure_local_model._answer_json(body, limit=11, timeout=1.0) == {"ok": True}
    assert body.timeouts


@pytest.fixture
def count_call(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Callable[[object], tuple[int, list[bytes]]]]:
    """Ein echter lokaler HTTP-Weg; jeder Zeitmessungszweig wäre ein Testfehler."""
    outgoing: list[bytes] = []
    response: list[object] = []

    class Answer(http.server.BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            outgoing.append(self.rfile.read(int(self.headers["Content-Length"])))
            raw = json.dumps(response[0]).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, pattern: str, *args: object) -> None:
            pass

    def forbidden(*args: object, **kwargs: object) -> Any:
        pytest.fail("der reine Zählweg darf keine Leistungsmessung auslösen")

    server = http.server.HTTPServer(("127.0.0.1", 0), Answer)
    serving = threading.Thread(
        target=server.serve_forever, kwargs={"poll_interval": 0.01}, daemon=True
    )
    monkeypatch.setattr(
        measure_local_model,
        "ollama_endpoint",
        lambda _url: f"http://127.0.0.1:{server.server_port}",
    )
    monkeypatch.setattr(
        "sys.argv", ["measure_local_model.py", "--count-tokens", "--model", "qwen3:14b"]
    )
    for name in ("_ask", "_report", "model_state", "unload"):
        monkeypatch.setattr(measure_local_model, name, forbidden)

    def run(answer: object) -> tuple[int, list[bytes]]:
        response.append(answer)
        return measure_local_model.main(), outgoing

    serving.start()
    try:
        yield run
    finally:
        server.shutdown()
        serving.join(timeout=2)
        server.server_close()


def _complete_count() -> dict[str, object]:
    """Vollständige Auskunft, deren Umfang zum aktuellen kompakten Auftrag passt."""
    return {
        "model": "qwen3:14b",
        "done": True,
        "prompt_eval_count": llm.PROMPT_TOKENS,
        "eval_count": 1,
    }


def test_token_count_sends_every_tool_once_and_identifies_the_actual_request(
    count_call: Callable[[object], tuple[int, list[bytes]]], capsys: pytest.CaptureFixture[str]
) -> None:
    status, requests = count_call(_complete_count())

    assert status == 0
    assert len(requests) == 1
    payload = json.loads(requests[0])
    schemas = list(tool_schemas(compact=True))
    assert payload["messages"] == [
        {"role": "system", "content": system_prompt(compact=True)},
        {"role": "user", "content": "Hallo."},
    ]
    assert payload["options"] == {
        "temperature": 0.0,
        "num_ctx": llm.OLLAMA_CONTEXT_TOKENS,
        "num_predict": 1,
    }
    assert payload["keep_alive"] == 0
    assert payload["stream"] is False
    assert {entry["function"]["name"] for entry in payload["tools"]} == {
        entry["name"] for entry in schemas
    }
    assert len(payload["tools"]) == len(schemas)
    for sent, source in zip(payload["tools"], schemas, strict=True):
        assert sent["function"]["parameters"] == source["input_schema"]
    output = capsys.readouterr()
    assert output.err == ""
    assert json.loads(output.out) == {
        "model": "qwen3:14b",
        "num_ctx": llm.OLLAMA_CONTEXT_TOKENS,
        "tool_count": len(schemas),
        "prompt_eval_count": llm.PROMPT_TOKENS,
        "eval_count": 1,
        "request_sha256": hashlib.sha256(requests[0]).hexdigest(),
    }


@pytest.mark.parametrize(
    "changed",
    [
        {"done": False},
        {"model": "falsches-modell"},
        {"error": "abgelehnt"},
        {"prompt_eval_count": None},
        {"prompt_eval_count": True},
        {"prompt_eval_count": 0},
        {"prompt_eval_count": 17.5},
        {"prompt_eval_count": "37000"},
        {"prompt_eval_count": llm.OLLAMA_CONTEXT_TOKENS // 2 + 2},
        {"prompt_eval_count": llm.OLLAMA_CONTEXT_TOKENS - 1},
        {"eval_count": None},
        {"eval_count": False},
        {"eval_count": -1},
        {"eval_count": 2},
    ],
)
def test_token_count_rejects_unverified_answers_without_printing_a_reference(
    changed: dict[str, object],
    count_call: Callable[[object], tuple[int, list[bytes]]],
    capsys: pytest.CaptureFixture[str],
) -> None:
    status, requests = count_call({**_complete_count(), **changed})

    assert status == 1
    assert len(requests) == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "erneut zählen" in output.err


def test_token_count_reports_transport_failure_without_a_reference(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def fail(_payload: bytes) -> dict[str, object]:
        raise OSError("Verbindung getrennt")

    monkeypatch.setattr("sys.argv", ["measure_local_model.py", "--count-tokens"])
    monkeypatch.setattr(measure_local_model, "_chat", fail)

    assert measure_local_model.main() == 1
    output = capsys.readouterr()
    assert output.out == ""
    assert "Verbindung getrennt" in output.err
    assert "erneut zählen" in output.err


def test_token_count_refuses_a_partial_tool_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("sys.argv", ["measure_local_model.py", "--count-tokens", "--tools", "0"])

    with pytest.raises(SystemExit) as caught:
        measure_local_model.main()

    assert caught.value.code == 2
