"""Eine Absage ohne Schritt nennt ihren Weg trotzdem (RB-3, Regel 17).

*Gegenstück zum Gewinde* ist ein Ablauf vor jedem Schritt: Sagt
``counterpart.thread_values_for`` ab, fehlt dem Fehler die Schrittkennung.
*Anderes Merkmal wählen* (``change_step``) braucht sie und fällt als Knopf weg
(``dialogs.NEEDS_OP``); weil das Fenster einen Handler dafür hat, übersprang
``unhandled_advice`` sie auch als Satz, und der Dialog endete mit *Schließen*.
Dasselbe gilt für *Andere Objekte wählen*, deren Handler ohne Schritt nichts
tut. Ohne Fenster: Die Handler sind Platzhalter mit den Kennungen des Fensters.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest
from PySide6.QtWidgets import QApplication

from app.core.errors import (
    CANCEL,
    CHANGE_FEATURE,
    CHANGE_SELECTION,
    SHOW_DETAILS,
    AppError,
    UserError,
)
from app.core.types import Action
from app.ui.dialogs import offered_actions, problem_text, unhandled_advice

#: Der Weg der Vorabzählung (``mesh_ops._too_fine``): steht in ``NEEDS_OP``,
#: der Operationsdialog löst ihn trotzdem ohne Schritt ein.
REACHABLE = Action(id="use_reachable", label="Die kleinste Kantenlänge nehmen, die noch geht.")


def _nothing(_error: AppError) -> None:
    """Ein Handler, wie das Fenster ihn hat; hier zählt nur die Kennung."""


HANDLERS: dict[str, Callable[[AppError], None]] = {
    "change_step": _nothing,
    "change_selection": _nothing,
    "correct_input": _nothing,
    SHOW_DETAILS.id: _nothing,
}


def _tapered_thread_refusal() -> AppError:
    from app.core.counterpart import thread_values_for
    from app.core.knowledge import standards
    from app.core.types import Feature

    tapered = Feature(
        id="thread_1",
        kind="thread",
        provenance="detected",
        params={"diameter": 37.0, "pitch": 0.9, "length": 10.0, "taper": 1.79},
    )
    try:
        thread_values_for(tapered, None, standards.shown_thread_families())
    except AppError as error:
        return error
    raise AssertionError("keine Absage")


def test_the_thread_counterpart_names_its_way_without_a_step() -> None:
    error = _tapered_thread_refusal()
    assert error.op_id is None
    assert CHANGE_FEATURE in error.suggestions
    assert CHANGE_FEATURE not in offered_actions(error, HANDLERS), "ohne Schritt kein Knopf"
    assert "Anderes Merkmal wählen" in unhandled_advice(error, HANDLERS)
    assert "Anderes Merkmal wählen" in problem_text(error, HANDLERS)
    # Neben dem Rat ein Knopf, der mehr zeigt, nicht nur *Schließen*.
    assert offered_actions(error, HANDLERS) == [SHOW_DETAILS]


@pytest.mark.parametrize(("unit", "suffix"), [("mm", " mm"), ("in", " in")])
def test_the_thread_refusals_say_lengths_in_the_display_unit_without_an_identifier(
    unit: str, suffix: str
) -> None:
    """FD-186: Unter der Absage stand „Merkmal: thread_1“, „Durchmesser: 37,0“, „Steigung: 0,9“.

    Beide Absagen des Gegenstücks (kegelig ohne Tabellengröße, außerhalb der
    Reihen): Längen in der Anzeigeeinheit, keine Kennung — der Satz nennt das
    Gewinde schon.
    """
    from app.core.counterpart import thread_values_for
    from app.core.knowledge import standards
    from app.core.types import Feature
    from app.ui import labels
    from app.ui.dialogs import spoken_values

    refusals = [_tapered_thread_refusal()]
    huge = Feature(
        id="thread_1",
        kind="thread",
        provenance="detected",
        params={"diameter": 1500.0, "pitch": 6.0, "length": 10.0},
    )
    try:
        thread_values_for(huge, None, standards.shown_thread_families())
    except AppError as error:
        refusals.append(error)
    assert [error.values.get("constraint") for error in refusals] == [
        "thread_shape",
        "beyond_threads",
    ]
    labels.set_display_unit(unit)  # type: ignore[arg-type]
    try:
        for error in refusals:
            lines = spoken_values(error)
            assert not [line for line in lines if "thread_1" in line], lines
            measured = [line for line in lines if line.startswith(("Durchmesser:", "Steigung:"))]
            assert len(measured) == 2, lines
            assert all(line.endswith(suffix) for line in measured), lines
    finally:
        labels.set_display_unit("mm")


def test_a_feature_identifier_reads_as_kind_and_number() -> None:
    """Die Zwillinge: Jede andere Absage legt ``values["feature"]`` für Agent und Handler ab.

    Angezeigt wird sie wie in der Merkmalsliste, „Bohrung 2“ statt „hole_2“;
    ein Körper davor fällt weg, eine Liste bleibt eine Liste, ein Name ohne
    bekannte Art bleibt, wie er ist.
    """
    from app.ui.labels import value_line

    assert value_line("feature", "hole_2") == "Merkmal: Bohrung 2"
    assert value_line("feature", "obj_1:thread_1") == "Merkmal: Gewinde 1"
    assert value_line("feature", "hole_1, fillet_3") == "Merkmal: Bohrung 1, Verrundung 3"
    assert value_line("feature", "mating") == "Merkmal: mating"


def test_with_a_step_the_way_is_a_button_and_no_sentence() -> None:
    error = UserError(detail="nein", suggestions=(CHANGE_FEATURE, CANCEL), op_id=4)
    assert offered_actions(error, HANDLERS) == [CHANGE_FEATURE]
    assert unhandled_advice(error, HANDLERS) == []


def test_what_stands_as_a_button_is_left_out_of_the_advice() -> None:
    """``left_out`` nimmt die Wege, die der Ort selbst als Knopf zeigt (RB2-2)."""
    error = UserError(detail="zu fein", suggestions=(REACHABLE, CHANGE_FEATURE, CANCEL))
    local = {**HANDLERS, REACHABLE.id: _nothing}
    assert str(REACHABLE.label) in problem_text(error, local)
    text = problem_text(error, local, left_out={REACHABLE.id})
    assert str(REACHABLE.label) not in text
    assert "Anderes Merkmal wählen" in text, "was kein Knopf ist, bleibt Rat"


def test_the_notice_shows_a_way_without_a_step_once_as_its_button(qt_app: QApplication) -> None:
    """Im Operationsdialog ist ein örtlicher Weg ohne Schritt ein Knopf, kein Satz (RB2-2).

    Die Vorabzählung von *Kanten verfeinern* sagt ohne Schrittkennung ab
    (RESTVERLAUF-04); der Dialog hat für *Die kleinste Kantenlänge nehmen*
    einen eigenen Handler. ``show_error`` zeigte den Weg ohne Schritt als
    Satz (RB-3), ``ErrorNotice`` als Knopf — beides zugleich stand doppelt da.
    """
    from PySide6.QtWidgets import QPushButton

    from app.ui.dialogs import ErrorNotice

    notice = ErrorNotice()
    try:
        error = UserError(detail="zu fein", suggestions=(REACHABLE, CANCEL))
        assert error.op_id is None
        notice.set_error(error, {REACHABLE.id: _nothing})
        buttons = [button.text() for button in notice.findChildren(QPushButton)]
        assert buttons == [str(REACHABLE.label)]
        assert str(REACHABLE.label) not in notice.text().splitlines()
        # Ohne örtlichen Handler bleibt der Weg Rat (RB-3).
        notice.set_error(UserError(detail="kegelig", suggestions=(CHANGE_FEATURE, CANCEL)), {})
        assert "Anderes Merkmal wählen" in notice.text().splitlines()
    finally:
        notice.deleteLater()
        qt_app.processEvents()


def test_other_objects_without_a_step_is_advice_not_a_dead_button() -> None:
    """Der Handler kehrt ohne Schritt sofort zurück; ein Knopf täte nichts."""
    error = UserError(detail="nichts zum Slicen", suggestions=(CHANGE_SELECTION, CANCEL))
    assert CHANGE_SELECTION not in offered_actions(error, HANDLERS)
    assert "Andere Objekte wählen" in unhandled_advice(error, HANDLERS)
