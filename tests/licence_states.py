"""Freischaltzustände für die Fenstertests der Sperre — über die Nahtstelle der Suite.

Gebraucht von ``test_licence_lock_offers.py`` und ``test_lock_reason_once.py``.
Ein eigenes Modul und nicht ``ui_helpers``: Es zieht ``tools.function_setup``
nach, und über ``ui_helpers`` hinge jede Änderung am Prüfstandswerkzeug an
siebzig Fenstertestdateien (``tests.md``, „Ein Helfer, den nur eine Testdatei
braucht …“; Review 1 Restpaket A, RA-9).
"""

from __future__ import annotations

from datetime import date

import pytest

from app.core import activation
from app.core.activation import store
from app.ui.dialogs import licence_lock_line
from tools import function_setup


def set_licence(monkeypatch: pytest.MonkeyPatch, state: str) -> str:
    """Den Freischaltzustand setzen; zurück kommt der Sperrgrund — leer, wenn frei."""
    monkeypatch.setattr(store, "DEMO_UNTIL", None)
    if state == "sale_without_trial":
        monkeypatch.setattr(store, "TRIAL_FROM", None)
    cached = function_setup.licence_activation(state, date.today())
    assert getattr(cached, state), f"der Zustand {state} ließ sich nicht herstellen"
    monkeypatch.setattr(activation, "_cached", cached)
    return "" if cached.unlocked else licence_lock_line(cached)
