"""Fremdantwortgrenzen des manuellen Ollama-Messwerkzeugs."""

from __future__ import annotations

import pytest

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
