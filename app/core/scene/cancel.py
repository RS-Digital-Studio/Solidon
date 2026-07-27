"""Cooperative cancellation (Bauplan §15.6, §2.8).

Anything that computes runs in a worker thread with progress and a cancel
button. A cancelled run leaves the stack on the last fully computed state —
there are no half applied operations, so the token is polled between operations
and inside long ones, never enforced from outside.
"""

from __future__ import annotations

import threading

from app.core.errors import OperationCancelled


class CancelSignal:
    """The token an operation polls, and the switch the surface flips."""

    def __init__(self) -> None:
        self._event = threading.Event()

    @property
    def is_cancelled(self) -> bool:
        return self._event.is_set()

    def cancel(self) -> None:
        self._event.set()

    def reset(self) -> None:
        self._event.clear()

    def raise_if_cancelled(self) -> None:
        if self._event.is_set():
            raise OperationCancelled


class NeverCancelled:
    """For command line runs and tests: nothing ever cancels."""

    @property
    def is_cancelled(self) -> bool:
        return False

    def raise_if_cancelled(self) -> None:
        return None
