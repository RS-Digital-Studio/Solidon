"""Die eine Auskunft „darf ändern“ (FD-5, FD-26 bis FD-30) — ohne Fenster.

``app.ui.change_lock`` ist die Quelle, die Prüfbericht, Merkmalfenster,
Kontextmenüs, Filamentwähler, Operationsdialog, Maßgruppe und jeder
Fensterbefehl fragen. Hier steht, was sie antwortet: gesperrt in beiden
Zuständen aus Prüfpunkt 18, offen im Kontrollfall, und Lesendes läuft immer
weiter; jeder Sperrgrund nennt seinen Weg. Die Zugänge selbst prüft
``tests/test_licence_lock_offers.py`` am Fenster.
"""

from __future__ import annotations

import ast
from contextlib import suppress
from datetime import date
from pathlib import Path
from typing import Any

import pytest

from app.core import activation, guides
from app.core.activation import store
from app.i18n import tr
from app.ui.change_lock import (
    READING_ACTIONS,
    READING_COMMANDS,
    READING_MENUS,
    action_refusal,
    change_refusal,
    command_refusal,
    computing_refusal,
)
from app.ui.dialogs import licence_lock_line
from app.ui.placement_flow import QuietHost
from tools import function_capture, function_setup

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "app" / "core"

#: Die zwei gesperrten Zustände aus Prüfpunkt 18 des Funktionsdurchgangs.
LOCKED = ("sale_without_trial", "needs_activation")

#: Fensterbefehle, die das Dokument ändern und ohne Freischaltung offen standen
#: (FD-26), dazu eine Zeile, die es noch nicht gibt: Unbekanntes ist ändernd.
CHANGING = (
    "menubar.parameter_anlegen",
    "menubar.modell_aus_dem_netz",
    "menubar.zeichnen",
    "edit.bind_parameters",
    "tool.transform",
    "tool.split",
    "menubar.eine_neue_zeile",
)

#: Fensterbefehle, die nur öffnen, zeigen oder einstellen — sie bleiben offen.
READING = (
    "menubar.speichern",
    "menubar.rueckgaengig",
    "menubar.bausteinkatalog",
    "menubar.material_kalibrieren",
    "file.part_share",
    "settings.language",
    "tool.measure",
)


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


@pytest.mark.parametrize("state", LOCKED)
def test_a_locked_licence_refuses_every_window_command_that_changes(
    monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    """FD-26: *Parameter anlegen …* stand ohne Freischaltung offen.

    Fensterbefehle fragen dieselbe Quelle wie die Befundhandlungen; was nicht als
    lesend geführt ist, sperrt mit dem Satz des Zustands.
    """
    reason = licence_lock_line(_set_licence(monkeypatch, state))
    for name in CHANGING:
        assert command_refusal(name) == reason, f"{name} ändert und bleibt offen"
    for name in READING:
        assert command_refusal(name) == "", f"{name} liest nur und wird gesperrt"


def test_with_a_licence_no_window_command_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_licence(monkeypatch, "licensed")
    for name in (*CHANGING, *READING):
        assert command_refusal(name) == "", name


def test_every_reading_command_is_a_name_the_window_gives() -> None:
    """Ein Name in der Leseliste, den das Fenster nicht vergibt, hält nichts offen.

    Gesammelt aus ``main_window.py``: die Menüzeilen über ihre deutsche Quelle
    (``guides.menubar_name``), die Kennungen der Suche als Zeichenketten, die
    Werkzeuge der Zeile über ``tools.add``. Eine umbenannte Zeile fiele sonst
    still aus der Liste und wäre ohne Freischaltung grau, obwohl sie nur liest.
    """
    tree = ast.parse((ROOT / "app" / "ui" / "main_window.py").read_text(encoding="utf-8"))
    given: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            given.add(node.value)
        if not isinstance(node, ast.Call) or not node.args:
            continue
        first = node.args[0]
        if not (isinstance(first, ast.Constant) and isinstance(first.value, str)):
            continue
        if getattr(node.func, "id", None) == "_":
            with suppress(ValueError):
                given.add(guides.menubar_name(first.value))
        if getattr(node.func, "attr", None) == "add":
            given.add(f"tool.{first.value}")
    assert len(given) > 1000, f"nur {len(given)} Namen gefunden — die Suche greift nicht"
    named = READING_COMMANDS | READING_MENUS
    assert named <= given, sorted(named - given)


@pytest.mark.parametrize("state", LOCKED)
def test_the_measure_group_takes_nothing_without_a_licence(
    monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    """FD-28: Die Maßgruppe nannte den Satz der gescheiterten Vorschau und keinen Weg.

    Der Träger der Maßgruppe sperrt selbst, vor jeder Vorschau, mit dem Satz der
    Freischaltung — der nennt die Menüzeile. Übernehmen erreicht den Rückruf nicht.
    """
    reason = licence_lock_line(_set_licence(monkeypatch, state))
    taken: list[Any] = []
    host = QuietHost({"diameter": 5.0}, lambda values: taken.append(values) is None)
    assert host.blocked_reason == reason
    assert not host.can_accept()
    host.accept()
    assert taken == [], "gesperrt übernahm die Maßgruppe ihre Werte"
    _set_licence(monkeypatch, "licensed")
    assert host.blocked_reason is None and host.can_accept()
    host.accept()
    assert taken == [{"diameter": 5.0}], "freigeschaltet übernimmt sie"


@pytest.mark.parametrize("state", ["sale_without_trial", "needs_activation", "expired", "pending"])
def test_every_lock_line_names_the_menu_row_that_lifts_it(
    monkeypatch: pytest.MonkeyPatch, state: str
) -> None:
    """FD-30, V5: Ein Sperrgrund nennt den Weg, so wie der Kunde die Menüzeile liest.

    Abgelaufener Test und unbestätigte Deaktivierung sagten nur, dass es nicht
    geht; die Freischaltung, an der Schlüssel und erneutes Senden liegen, stand
    nicht darin.
    """
    if state == "pending":
        current = activation.Activation(deactivation_pending=True)
    else:
        current = _set_licence(monkeypatch, state)
    way = f"{tr('Hilfe')} → {tr('Solidon freischalten …')}"
    assert way in licence_lock_line(current), licence_lock_line(current)


def test_the_computing_lock_names_that_it_lifts_by_itself() -> None:
    """FD-30: „Erst nach der Berechnung …“ nannte keinen Ausweg.

    Die Sperre einer Befundhandlung während der Rechnung fällt mit ihrem Ende;
    das sagt der Satz, und der Prüfstand erkennt es als Ausweg (V5). Ein Satz
    ohne Weg bleibt einer.
    """

    class Bar:
        def actions(self) -> list[Any]:
            return []

    class Window:
        def menuBar(self) -> Bar:  # noqa: N802 - Qts Name
            return Bar()

    assert "Die Handlung ist wieder frei, sobald die Berechnung fertig ist." in computing_refusal()
    assert function_capture.way_out(Window(), computing_refusal())
    assert not function_capture.way_out(Window(), "Der Testzeitraum ist abgelaufen.")
