"""Eine Auswahlhandlung richtet sich nach dem Schritt, der die Absage auslöst (RB-1, RB-2).

*Andere Kanten wählen*, *Andere Flächen wählen* und *Anderes Merkmal wählen*
öffnen den Schritt (``change_step``). Dieselbe Kantenabsage kommt aber aus
*Verrunden* (Feld *Kanten*) und aus *Merkmal ändern* (Feld *Merkmal*), dieselbe
Flächenabsage aus *Formschräge anstellen* und *Kammer ändern*. Wer die Absage
wirft, kennt den Schritt nicht; die Auswertung kennt ihn
(``evaluate._finding_from`` und die Befunde einer Ausgabe). Dort passt
``scene.choice_ways`` die Handlung an das Schema des Schritts an und legt das
Feld ab, das sie meint (``values["choice_field"]``, dazu ``field``, wenn die
Absage keins nennt). Alles hier ohne Fenster; die Fenstertests stehen in
``test_choice_ways_ui.py``.
"""

from __future__ import annotations

import pytest

from app.core.bootstrap import load_operations
from app.core.errors import (
    CANCEL,
    CHANGE_EDGES,
    CHANGE_FACES,
    CHANGE_FEATURE,
    CHANGE_THIS_STEP,
    CORRECT_INPUT,
    GeometryError,
)
from app.core.registry import REGISTRY
from app.core.scene.choice_ways import CHOICE_ACTIONS, choice_fields, fitted_to_step
from app.core.types import Action, Finding, Operation

load_operations()


def _fitted(op: str, *ways: Action, **values: str) -> Finding:
    finding = Finding(
        code="op.test", severity="error", message="nein", values=values, suggestions=ways
    )
    return fitted_to_step(finding, op)


@pytest.mark.parametrize(
    ("op", "action", "kept", "field"),
    [
        ("fillet_edges", CHANGE_EDGES, CHANGE_EDGES, "edges"),
        ("chamfer_edges", CHANGE_EDGES, CHANGE_EDGES, "edges"),
        ("cut_away", CHANGE_EDGES, CHANGE_EDGES, "edge"),
        ("draft_faces", CHANGE_FACES, CHANGE_FACES, "faces"),
        ("push_face", CHANGE_FACES, CHANGE_FACES, "face"),
        ("hollow_object", CHANGE_FACES, CHANGE_FACES, "openings"),
        ("create_seal", CHANGE_FACES, CHANGE_FACES, "support_feature"),
        ("apply_texture", CHANGE_FACES, CHANGE_FACES, "face"),
        ("resize_chamber", CHANGE_FEATURE, CHANGE_FEATURE, "at_feature"),
        ("pattern_feature", CHANGE_FEATURE, CHANGE_FEATURE, "at_features"),
        # RB-1: dieselbe Absage aus einem Merkmalsschritt meint dessen Merkmal.
        ("resize_feature", CHANGE_EDGES, CHANGE_FEATURE, "at_feature"),
        ("remove_feature", CHANGE_EDGES, CHANGE_FEATURE, "at_feature"),
        ("resize_chamber", CHANGE_FACES, CHANGE_FEATURE, "at_feature"),
    ],
)
def test_the_action_names_a_field_of_its_step(
    op: str, action: Action, kept: Action, field: str
) -> None:
    fitted = _fitted(op, action, CANCEL)
    assert fitted.suggestions == (kept, CANCEL)
    assert fitted.values["choice_field"] == field
    assert fitted.values["field"] == field


def test_a_value_field_of_the_same_refusal_stays_for_correct_input() -> None:
    """*Eingabe korrigieren* behält seinen Wert, *Andere Kanten wählen* bekommt die Kanten."""
    fitted = _fitted("chamfer_edges", CORRECT_INPUT, CHANGE_EDGES, CANCEL, field="second_distance")
    assert fitted.suggestions == (CORRECT_INPUT, CHANGE_EDGES, CANCEL)
    assert fitted.values["field"] == "second_distance"
    assert fitted.values["choice_field"] == "edges"
    # Ohne eigenes Feld öffnet *Eingabe korrigieren* weiter das erste, den Radius.
    unnamed = _fitted("fillet_edges", CORRECT_INPUT, CHANGE_EDGES, CANCEL)
    assert "field" not in unnamed.values
    assert unnamed.values["choice_field"] == "edges"


@pytest.mark.parametrize("op", ["fillet_edges", "chamfer_edges", "bead_edges"])
def test_named_edges_open_the_chosen_edges_not_the_group(op: str) -> None:
    """Bei *Kanten* „Einzeln gewählt“ meint die Handlung die gewählten Kanten (RB2-3).

    Sie stehen in *Einzelne Kanten* hinten; die Gruppe davor sagt nur
    „Einzeln gewählt“. Mit einer Gruppe bleibt es die Gruppe — dann wirkt
    *Einzelne Kanten* nicht.
    """
    finding = Finding(
        code="op.test", severity="error", message="nein", suggestions=(CHANGE_EDGES, CANCEL)
    )
    named = fitted_to_step(finding, op, {"edges": "named", "edge_keys": "e1 e2"})
    assert named.suggestions == (CHANGE_EDGES, CANCEL)
    assert named.values["choice_field"] == "edge_keys"
    assert named.values["field"] == "edge_keys"
    grouped = fitted_to_step(finding, op, {"edges": "top", "edge_keys": "e1"})
    assert grouped.values["choice_field"] == "edges"


def test_the_evaluation_hands_the_values_of_the_step_over() -> None:
    """Ein Halt an benannten Kanten öffnet sie — die Auswertung reicht die Werte weiter."""
    from app.core.scene.evaluate import _finding_from

    error = GeometryError(detail="zu groß", suggestions=(CORRECT_INPUT, CHANGE_EDGES, CANCEL))
    operation = Operation(
        id=2,
        op="fillet_edges",
        inputs=("obj_1",),
        params={"radius": 40.0, "edges": "named", "edge_keys": "e1"},
    )
    finding = _finding_from(error, operation)
    assert finding.values["choice_field"] == "edge_keys"


def test_a_step_without_any_choice_field_offers_the_step_itself() -> None:
    """Ohne passendes Feld bleibt *Diesen Schritt ändern*, kein leeres Versprechen."""
    fitted = _fitted("create_box", CHANGE_FEATURE, CANCEL)
    assert fitted.suggestions == (CHANGE_THIS_STEP, CANCEL)
    assert "choice_field" not in fitted.values


def test_every_step_resolves_every_choice_to_a_field_it_has() -> None:
    """Über das ganze Register: Was angeboten bleibt, hat sein Feld im Schema."""
    for spec in REGISTRY.all():
        names = {entry.name for entry in spec.params.spec()}
        fields = choice_fields(spec.params.spec())
        for action in CHOICE_ACTIONS:
            fitted = _fitted(spec.name, action, CANCEL)
            (way, _cancel) = fitted.suggestions
            if way == CHANGE_THIS_STEP:
                assert not fields[CHOICE_ACTIONS[action]] and not fields["feature"], spec.name
                continue
            chosen = fitted.values["choice_field"]
            assert chosen in names, (spec.name, chosen)
            assert chosen in fields[CHOICE_ACTIONS[way]], (spec.name, way, chosen)


def test_the_evaluation_fits_a_halted_step() -> None:
    """Der eine Weg vom Fehler zum Befund am Schritt trägt die Anpassung."""
    from app.core.scene.evaluate import _finding_from

    error = GeometryError(detail="zu groß", suggestions=(CORRECT_INPUT, CHANGE_EDGES, CANCEL))
    operation = Operation(id=3, op="resize_feature", inputs=("obj_1",))
    finding = _finding_from(error, operation)
    assert finding.suggestions == (CORRECT_INPUT, CHANGE_FEATURE, CANCEL)
    assert finding.values["choice_field"] == "at_feature"


def test_both_ways_into_the_report_fit_the_choice() -> None:
    """Ein Halt (``_finding_from``) und die Befunde einer Ausgabe gehen beide durch die Anpassung.

    Die Absagen selbst nennen kein Kantenfeld — sie wissen nicht, ob *Verrunden*
    oder *Merkmal ändern* sie ruft. Fehlt einer der zwei Wege, steht dort wieder
    eine Handlung ohne Feld.
    """
    import importlib
    import inspect

    # ``app.core.scene.evaluate`` heißt im Paket auch die Funktion; das Modul selbst.
    evaluation = importlib.import_module("app.core.scene.evaluate")
    assert "fitted_to_step(" in inspect.getsource(evaluation._finding_from)
    assert inspect.getsource(evaluation).count("fitted_to_step(") >= 2
