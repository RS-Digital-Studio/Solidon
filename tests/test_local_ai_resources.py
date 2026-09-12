"""Gemeinsame Rechnerressourcen der lokalen KI-Backends."""

from __future__ import annotations

import threading
import time

import pytest

from app.core.errors import OperationCancelled
from app.core.scene.cancel import CancelSignal


def test_only_one_local_gpu_backend_runs_at_a_time() -> None:
    """Ollama und ComfyUI dürfen eine 16-GB-Karte nicht gleichzeitig füllen."""
    from app.core.backends.resources import local_ai_slot

    token = CancelSignal()
    waiting = threading.Event()
    errors: list[BaseException] = []

    with local_ai_slot("http://127.0.0.1:11434", None):

        def enter_second_slot() -> None:
            waiting.set()
            try:
                with local_ai_slot("http://localhost:8188", token):
                    raise AssertionError("die zweite lokale KI lief gleichzeitig")
            except BaseException as error:
                errors.append(error)

        worker = threading.Thread(target=enter_second_slot)
        worker.start()
        assert waiting.wait(1.0)
        token.cancel()
        worker.join(1.0)

    assert not worker.is_alive()
    assert len(errors) == 1 and isinstance(errors[0], OperationCancelled)


def test_remote_backends_do_not_share_the_local_slot() -> None:
    from app.core.backends.resources import local_ai_slot

    with (
        local_ai_slot("http://127.0.0.1:11434", None),
        local_ai_slot("http://192.0.2.1:8188", None),
    ):
        pass


def test_waiting_reports_once_and_times_out_without_releasing_the_other_job(monkeypatch) -> None:
    from app.core.backends import resources

    monkeypatch.setattr(resources, "MAX_WAIT_SECONDS", 0.02)
    seen: list[str] = []
    with resources.local_ai_slot("http://localhost:11434", None):
        started = time.monotonic()
        with (
            pytest.raises(resources.LocalAiBusyError) as raised,
            resources.local_ai_slot("http://localhost:8188", None, seen.append),
        ):
            pytest.fail("the occupied local slot must not be entered")
        assert time.monotonic() - started < 1.0
        assert resources._LOCAL_AI_LOCK.locked()
    assert len(seen) == 1
    assert "Grafikkarte" in seen[0]
    assert {action.id for action in raised.value.suggestions} == {"retry", "cancel"}
    with resources.local_ai_slot("http://localhost:8188", None, seen.append):
        pass
    assert len(seen) == 1, "there is no waiting message for an immediately available slot"


def test_waiting_can_be_cancelled_from_its_progress_callback() -> None:
    from app.core.backends import resources

    token = CancelSignal()
    seen: list[str] = []

    def progress(text: str) -> None:
        seen.append(text)
        token.cancel()

    with resources.local_ai_slot("http://localhost:11434", None):
        with (
            pytest.raises(OperationCancelled),
            resources.local_ai_slot("http://localhost:8188", token, progress),
        ):
            pytest.fail("a cancelled waiter must not enter")
        assert resources._LOCAL_AI_LOCK.locked()
    assert len(seen) == 1
