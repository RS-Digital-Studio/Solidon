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

from app.core.errors import (
    CANCEL,
    CHANGE_FEATURE,
    CHANGE_SELECTION,
    SHOW_DETAILS,
    AppError,
    UserError,
)
from app.ui.dialogs import offered_actions, problem_text, unhandled_advice


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


def test_with_a_step_the_way_is_a_button_and_no_sentence() -> None:
    error = UserError(detail="nein", suggestions=(CHANGE_FEATURE, CANCEL), op_id=4)
    assert offered_actions(error, HANDLERS) == [CHANGE_FEATURE]
    assert unhandled_advice(error, HANDLERS) == []


def test_other_objects_without_a_step_is_advice_not_a_dead_button() -> None:
    """Der Handler kehrt ohne Schritt sofort zurück; ein Knopf täte nichts."""
    error = UserError(detail="nichts zum Slicen", suggestions=(CHANGE_SELECTION, CANCEL))
    assert CHANGE_SELECTION not in offered_actions(error, HANDLERS)
    assert "Andere Objekte wählen" in unhandled_advice(error, HANDLERS)
