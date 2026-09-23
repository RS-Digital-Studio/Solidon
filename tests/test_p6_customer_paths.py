"""Die zwei Kundenwege aus Konzept §13.9 für P6.1 und P6.4 — Ende zu Ende am Stapel.

„Variable Griffverrundung" und „Gehäuse mit gewählten Entformungsflächen":
Schritt anlegen, auswerten, einen Wert ändern, Rückgängig und Wiederholen,
speichern und wieder öffnen — und jedes Mal dieselbe Form. Die Sollwerte sind
Lehrbuchgeometrie (Zwickel ``(1 − π/4)·∫r²``, Hohlraum als Integral seiner
Querschnitte), nicht der Prüfling. Beide Körperarten: Der Griff und das
Gehäuse entstehen einmal als Netz (``create_box``) und einmal exakt
(``create_brep_box``).
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import pytest
from scipy import integrate

from app.core.geom.edges import edge_key, edges_in_kernel
from app.core.geom.mesh import as_mesh_data
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import ProjectSources, load, new_project, save
from app.core.types import Profile
from app.core.units import MAX_FACET_ANGLE, MAX_FACET_SAG

CREATORS = [("create_box", "mesh"), ("create_brep_box", "brep")]


def needs_exact(kind: str) -> None:
    if kind != "brep":
        return
    kernel = pytest.importorskip("app.core.brep.kernel")
    if not kernel.available():
        pytest.skip("OpenCASCADE is an optional dependency")


def polygon_share(radius: float) -> float:
    """Zwickelanteil eines Sehnenzugs mit der Feinheit der Zusage (siehe test_variable_fillet)."""
    turn = min(2.0 * math.acos(1.0 - MAX_FACET_SAG / radius), MAX_FACET_ANGLE)
    steps = max(4, math.ceil((math.pi / 2.0) / turn))
    return 1.0 - steps * math.sin((math.pi / 2.0) / steps) / 2.0


def volume_of(project: Any, profile: Profile, object_id: str) -> float:
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete, [finding.message for finding in result.report.findings]
    return float(result.scene.objects[object_id].mesh.volume)


# --- Variable Griffverrundung ----------------------------------------------------------

LENGTH, WIDTH, HEIGHT = 120.0, 20.0, 15.0


@pytest.mark.parametrize(("creator", "kind"), CREATORS)
def test_a_variable_handle_fillet_survives_change_undo_and_reopening(
    creator: str, kind: str, profile: Profile, tmp_path: Path
) -> None:
    """Ein Griff 120 × 20 × 15: die zwei langen oberen Kanten, 2 mm an den Enden, 5 in der Mitte.

    Danach die Mitte auf 4 mm, Rückgängig, Wiederholen, Speichern, Öffnen.
    """
    needs_exact(kind)
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Griff",
        [OperationDraft(op=creator, params={"width": LENGTH, "depth": WIDTH, "height": HEIGHT})],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    (object_id, body), *_rest = result.scene.objects.items()
    top = float(body.mesh.bounds.maximum[2])
    _kernel, entries = edges_in_kernel(body.mesh, kind)
    long_top = [
        entry
        for entry in entries
        if abs(entry.middle[2] - top) < 1e-6 and abs(entry.direction[0]) > 0.9
    ]
    assert len(long_top) == 2, "die zwei langen oberen Kanten"
    keys = " ".join(edge_key(entry) for entry in long_top)
    before = float(body.mesh.volume)

    params = {
        "radius": 2.0,
        "mode": "variable_radius",
        "end_radius": 2.0,
        "stations": "50:5",
        "edges": "named",
        "edge_keys": keys,
    }
    history.apply(
        "Griffverrundung",
        [OperationDraft(op="fillet_edges", inputs=(object_id,), params=params)],
    )
    step = history.operations[-1].id

    def removed_for(middle: float) -> float:
        """Zwei Kanten, Verlauf 2 → middle → 2 (monoton kubisch, ohne Knick in der Mitte)."""
        from app.core.geom.edges import RadiusLaw

        law = RadiusLaw((0.0, 0.5, 1.0), (2.0, middle, 2.0))
        squares, _error = integrate.quad(lambda t: law.at(t) ** 2, 0.0, 1.0, limit=200)
        share = (1.0 - math.pi / 4.0) if kind == "brep" else polygon_share(middle)
        return 2.0 * share * LENGTH * squares

    wide = volume_of(project, profile, object_id)
    assert before - wide == pytest.approx(removed_for(5.0), rel=2e-3 if kind == "mesh" else 1e-5)

    history.change_params(step, {**params, "stations": "50:4"})
    narrower = volume_of(project, profile, object_id)
    assert before - narrower == pytest.approx(
        removed_for(4.0), rel=2e-3 if kind == "mesh" else 1e-5
    )

    assert history.undo() is not None
    assert volume_of(project, profile, object_id) == pytest.approx(wide, abs=1e-9)
    assert history.redo() is not None
    assert volume_of(project, profile, object_id) == pytest.approx(narrower, abs=1e-9)

    path = save(project, tmp_path / "griff.p3d")
    reopened = load(path)
    assert volume_of(reopened, profile, object_id) == pytest.approx(narrower, abs=1e-9)


# --- Gehäuse mit gewählten Entformungsflächen ------------------------------------------

OUTER = (60.0, 40.0, 30.0)
WALL = 3.0
DRAFT = 2.0


def inner_walls(body: Any) -> tuple[str, ...]:
    """Die vier Innenwände: senkrechte Flächen, deren Mitte innerhalb der Außenwände liegt."""
    width, depth, _height = OUTER
    found = []
    for name, feature in body.features.items():
        if feature.kind != "face" or abs(feature.params["normal"][2]) > 1e-6:
            continue
        x, y, _z = feature.params["centre"]
        if abs(x) < width / 2.0 - 1.0 and abs(y) < depth / 2.0 - 1.0:
            found.append(name)
    return tuple(sorted(found))


def cavity_growth(angle_deg: float) -> float:
    slope = math.tan(math.radians(angle_deg))
    width, depth, height = OUTER
    inner_w, inner_d = width - 2 * WALL, depth - 2 * WALL
    value, _error = integrate.quad(
        lambda z: (inner_w + 2 * z * slope) * (inner_d + 2 * z * slope) - inner_w * inner_d,
        WALL,
        height,
    )
    return value


@pytest.mark.parametrize(("creator", "kind"), CREATORS)
def test_a_housing_with_chosen_draft_faces_survives_change_undo_and_reopening(
    creator: str, kind: str, profile: Profile, tmp_path: Path
) -> None:
    """Gehäuse 60 × 40 × 30, Wand 3: die Innenwände 2°, neutral am Boden, nach oben entformt.

    Danach 1°, Rückgängig, Wiederholen, Speichern, Öffnen. Die Außenwände
    bleiben stehen, der Hohlraum weitet sich nach oben.
    """
    needs_exact(kind)
    width, depth, height = OUTER
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Gehäuse",
        [
            OperationDraft(op=creator, params={"width": width, "depth": depth, "height": height}),
            OperationDraft(
                op=creator,
                params={
                    "width": width - 2 * WALL,
                    "depth": depth - 2 * WALL,
                    "height": height,
                    "z": WALL,
                },
            ),
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    outer_id, inner_id = list(result.scene.objects)
    history.apply(
        "Aushöhlen",
        [OperationDraft(op="subtract_objects", inputs=(outer_id, inner_id), params={})],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    body = result.scene.objects[outer_id]
    walls = inner_walls(body)
    assert len(walls) == 4, walls
    before = float(as_mesh_data(body.mesh).volume)

    history.apply(
        "Formschräge",
        [
            OperationDraft(
                op="draft_faces", inputs=(outer_id,), params={"faces": list(walls), "angle": DRAFT}
            )
        ],
    )
    step = history.operations[-1].id
    two = volume_of(project, profile, outer_id)
    assert two == pytest.approx(before - cavity_growth(DRAFT), abs=1e-3)

    history.change_params(step, {"faces": list(walls), "angle": 1.0})
    one = volume_of(project, profile, outer_id)
    assert one == pytest.approx(before - cavity_growth(1.0), abs=1e-3)

    assert history.undo() is not None
    assert volume_of(project, profile, outer_id) == pytest.approx(two, abs=1e-9)
    assert history.redo() is not None
    assert volume_of(project, profile, outer_id) == pytest.approx(one, abs=1e-9)

    path = save(project, tmp_path / "gehaeuse.p3d")
    reopened = load(path)
    assert volume_of(reopened, profile, outer_id) == pytest.approx(one, abs=1e-9)
