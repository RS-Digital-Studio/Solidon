"""Eine Absage an Kanten bietet andere Kanten an, nicht andere Objekte (FD-123).

*Andere Objekte wählen* (``change_selection``) gibt einem Schritt im
Objektbaum markierte Körper — an einer Rundung, deren Radius für die Kanten
zu groß ist, ist das der falsche Weg: Der Kunde wählte einen anderen Körper
statt einer anderen Kante. Die Kanten wählt man im Dialog des Schritts
(*Kanten*, *Einzelne Kanten*); dorthin führt *Andere Kanten wählen*.
"""

from __future__ import annotations

from collections.abc import Callable

import pytest

from app.core.errors import CHANGE_EDGES, CHANGE_SELECTION, GeometryError
from app.core.geom.edges import too_large_for_the_faces, wanted


def _refusal(make: Callable[[], object]) -> GeometryError:
    try:
        make()
    except GeometryError as error:
        return error
    raise AssertionError("keine Absage")


def _chamfer_sides_unknown() -> GeometryError:
    from app.core.brep.edit import _chamfer_sides_unknown as refusal

    return refusal()


REFUSALS: dict[str, Callable[[], GeometryError]] = {
    "Radius zu groß": lambda: too_large_for_the_faces(4.0, 1.5, rounded=True),
    "Breite zu groß": lambda: too_large_for_the_faces(4.0, 1.5, rounded=False),
    "zweite Breite zu groß": lambda: too_large_for_the_faces(4.0, 1.5, rounded=False, second=True),
    "Radien zu groß": lambda: too_large_for_the_faces(4.0, 1.5, rounded=True, varying=True),
    "keine Kante benannt": lambda: _refusal(lambda: wanted([], "named", ())),
    "keine Kante in der Gruppe": lambda: _refusal(lambda: wanted([], "vertical", ())),
    "Fasenflächen unbestimmt": _chamfer_sides_unknown,
}


@pytest.mark.parametrize("case", sorted(REFUSALS))
def test_an_edge_refusal_offers_other_edges(case: str) -> None:
    error = REFUSALS[case]()
    labels = [str(action.label) for action in error.suggestions]
    assert CHANGE_SELECTION not in error.suggestions, f"{case}: {labels}"
    assert CHANGE_EDGES in error.suggestions, f"{case}: {labels}"


def test_other_edges_opens_the_step_where_the_edges_are_chosen() -> None:
    """Der Knopf öffnet den Schritt wie *Größe ändern* (``change_step``)."""
    assert CHANGE_EDGES.id == "change_step"
    assert str(CHANGE_EDGES.label) == "Andere Kanten wählen"
