"""Die eine Auskunft „darf ändern“ (FD-5) — ohne Fenster.

``app.ui.change_lock`` ist die Quelle, die Prüfbericht, Merkmalfenster,
Kontextmenüs, Filamentwähler, Operationsdialog und Menü fragen. Hier steht,
was sie antwortet: gesperrt in beiden Zuständen aus Prüfpunkt 18, offen im
Kontrollfall, und Lesendes läuft immer weiter. Die Zugänge selbst prüft
``tests/test_licence_lock_offers.py`` am Fenster.
"""

from __future__ import annotations

import ast
from datetime import date
from pathlib import Path

import pytest

from app.core import activation
from app.core.activation import store
from app.ui.change_lock import READING_ACTIONS, action_refusal, change_refusal
from app.ui.dialogs import licence_lock_line
from tools import function_setup

CORE = Path(__file__).resolve().parent.parent / "app" / "core"


def _set_licence(monkeypatch: pytest.MonkeyPatch, state: str) -> activation.Activation:
    monkeypatch.setattr(store, "DEMO_UNTIL", None)
    if state == "sale_without_trial":
        monkeypatch.setattr(store, "TRIAL_FROM", None)
    cached = function_setup.licence_activation(state, date.today())
    assert getattr(cached, state), f"der Zustand {state} ließ sich nicht herstellen"
    monkeypatch.setattr(activation, "_cached", cached)
    return cached


@pytest.mark.parametrize("state", ["sale_without_trial", "needs_activation"])
def test_a_locked_licence_refuses_every_change_with_the_line_of_its_state(
    monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    cached = _set_licence(monkeypatch, state)
    reason = licence_lock_line(cached)
    assert reason and change_refusal() == reason
    assert action_refusal("place_on_bed") == reason, "eine Handlung, die einen Schritt anlegt"
    assert action_refusal("eine_neue_handlung") == reason, "Unbekanntes gilt als ändernd"
    for reading in ("show_location", "show_details", "activate_online", "report_error"):
        assert action_refusal(reading) == "", f"{reading} liest nur und bleibt bedienbar"


def test_with_a_licence_nothing_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_licence(monkeypatch, "licensed")
    assert change_refusal() == ""
    assert action_refusal("place_on_bed") == ""


def test_every_reading_action_is_one_the_core_offers() -> None:
    """Ein Name in der Leseliste, den der Kern nicht kennt, prüft nichts mehr.

    Gesammelt werden die Kennungen aller ``Action("…", …)`` im Kern; eine
    umbenannte Handlung fiele sonst still aus der Liste und wäre gesperrt.
    """
    offered: set[str] = set()
    for path in CORE.rglob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not (isinstance(node, ast.Call) and getattr(node.func, "id", None) == "Action"):
                continue
            first = (
                node.args[0]
                if node.args
                else next((keyword.value for keyword in node.keywords if keyword.arg == "id"), None)
            )
            if isinstance(first, ast.Constant) and isinstance(first.value, str):
                offered.add(first.value)
    assert len(offered) > 50, f"nur {len(offered)} Handlungen gefunden — die Suche greift nicht"
    assert offered >= READING_ACTIONS, sorted(READING_ACTIONS - offered)
