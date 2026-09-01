"""Gemeinsame Rechnerressourcen der lokalen KI-Backends."""

from __future__ import annotations

import threading

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
