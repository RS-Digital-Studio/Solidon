"""Eine Absage an Flächen bietet andere Flächen an, nicht andere Objekte (FD-165).

*Formschräge anstellen* und *Fläche versetzen* sagten bei einer gewölbten,
verschwundenen oder quer stehenden Fläche „Andere Objekte wählen“ — der Knopf
gibt dem Schritt die im Objektbaum markierten Körper, und der Kunde wählte
damit einen anderen Körper statt einer anderen Fläche. Die Flächen wählt man im
Dialog des Schritts (*Flächen*, *Fläche*); dorthin führt *Andere Flächen
wählen*. Der Zwilling an Kanten ist FD-123 (``test_edge_refusal_ways``).
"""

from __future__ import annotations

import inspect
from collections.abc import Callable

import pytest
import trimesh

from app.core.errors import CHANGE_FACES, CHANGE_SELECTION, CORRECT_INPUT, GeometryError
from app.core.geom import face_ops, faces
from app.core.geom.mesh import MeshData
from app.core.types import Feature
from tests.helpers import exact_kernel


def _refusal(make: Callable[[], object]) -> GeometryError:
    try:
        make()
    except GeometryError as error:
        return error
    raise AssertionError("keine Absage")


def _sphere_mesh() -> MeshData:
    return MeshData(trimesh.creation.icosphere(subdivisions=3, radius=10.0))


def _curved_side() -> GeometryError:
    """Die Mantelfläche eines Zylinders lässt sich nicht versetzen."""
    body = trimesh.creation.cylinder(radius=10.0, height=20.0, sections=48)
    side = [
        int(index) for index in range(len(body.faces)) if abs(body.face_normals[index][2]) < 0.5
    ]
    return _refusal(lambda: faces._must_be_flat(MeshData(body), side, body.face_normals[side[0]]))


def _without_direction() -> GeometryError:
    flat = Feature(id="f1", kind="face", provenance="detected", params={"normal": (0.0, 0.0, 0.0)})
    return _refusal(lambda: faces.face_normal(flat))


def _no_face() -> GeometryError:
    error = face_ops._no_face()
    assert isinstance(error, GeometryError)
    return error


MESH_REFUSALS: dict[str, Callable[[], GeometryError]] = {
    "Fläche verschwunden": faces.gone_face_error,
    "keine Fläche gewählt": _no_face,
    "Fläche gewölbt": _curved_side,
    "Richtung unbekannt": _without_direction,
    "quer zur Entformung": faces._across_the_pull,
    "keine Wand in Entformungsrichtung": lambda: _refusal(
        lambda: faces.draft_walls(_sphere_mesh(), 5.0)
    ),
}


@pytest.mark.parametrize("case", sorted(MESH_REFUSALS))
def test_a_face_refusal_offers_other_faces(case: str) -> None:
    error = MESH_REFUSALS[case]()
    labels = [str(action.label) for action in error.suggestions]
    assert CHANGE_SELECTION not in error.suggestions, f"{case}: {labels}"
    assert CHANGE_FACES in error.suggestions, f"{case}: {labels}"


def test_the_exact_kernel_refuses_faces_the_same_way() -> None:
    edit = exact_kernel()
    from app.core.brep import profiles
    from app.core.brep.canonical import PlaneSurface

    cylinder = edit.cylinder(20.0, 10.0)
    curved = next(
        index
        for index in range(len(cylinder.faces()))
        if not isinstance(cylinder.surface(index), PlaneSurface)
    )
    for case, attempt in {
        "keine Wand in Entformungsrichtung": lambda: profiles.draft_faces(edit.sphere(20.0), 5.0),
        "gewölbte Fläche gewählt": lambda: profiles.draft_faces(
            cylinder, 5.0, selected_faces=(curved,)
        ),
    }.items():
        error = _refusal(attempt)
        labels = [str(action.label) for action in error.suggestions]
        assert CHANGE_SELECTION not in error.suggestions, f"{case}: {labels}"
        assert CHANGE_FACES in error.suggestions, f"{case}: {labels}"


def test_no_face_refusal_is_left_offering_other_objects() -> None:
    """Jede Absage der Flächenwege — auch die schwer auslösbaren an Ecken und
    Rundungen — steht in diesen Quellen; keine bietet mehr Objekte an."""
    exact_kernel()
    from app.core.brep import profiles

    for source in (
        inspect.getsource(faces),
        inspect.getsource(profiles.draft_faces),
        inspect.getsource(face_ops._no_face),
    ):
        assert "CHANGE_SELECTION" not in source


def test_other_faces_opens_the_step_where_the_faces_are_chosen() -> None:
    """Der Knopf öffnet den Schritt wie *Größe ändern* (``change_step``),
    neben *Eingabe korrigieren*, wo auch ein Wert die Absage löst."""
    assert CHANGE_FACES.id == "change_step"
    assert str(CHANGE_FACES.label) == "Andere Flächen wählen"
    assert CORRECT_INPUT in faces._across_the_pull().suggestions
