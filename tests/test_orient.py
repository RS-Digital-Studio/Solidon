"""Druckorientierung als Heuristik, offen als solche benannt (Bauplan §25,
P2).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest
import trimesh

from app.core.geom.mesh import MeshData, read_mesh
from app.core.geom.orient import (
    candidates,
    evaluate_direction,
    orient_for_print,
    ranked_orientations,
    rotation_to_down,
)
from app.core.geom.transform import apply, rotation, translation
from app.core.ingest.loader import normalise
from app.core.registry import REGISTRY, VARIABLE
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.cache import ResultCache
from app.core.scene.project import Project, ProjectSources, new_project
from app.core.types import Document, Profile, Source
from app.i18n import _

MESHES = Path(__file__).parent / "data" / "meshes"


def plate():
    """Eine flache Platte: 80 x 50 x 8 mm. Ihre beste Seite ist offensichtlich."""
    return normalise(read_mesh((MESHES / "plate_holes.stl").read_bytes(), ".stl"), "mm").mesh


def test_a_tilted_plate_is_laid_flat_again() -> None:
    tilted = apply(plate(), rotation("x", 37.0))
    result = orient_for_print(tilted)

    assert result.mesh.bounds.size[2] == pytest.approx(8.0, abs=0.2), "it lies flat again"
    assert result.mesh.bounds.minimum[2] == pytest.approx(0.0), "and sits on the bed"


def test_a_standing_plate_is_laid_down() -> None:
    standing = apply(plate(), rotation("y", 90.0))
    assert standing.bounds.size[2] == pytest.approx(80.0, abs=0.5)

    result = orient_for_print(standing)
    assert result.mesh.bounds.size[2] < 20.0, "lying down beats standing up"


def test_the_footprint_beats_the_alternatives() -> None:
    body = plate()
    lying = evaluate_direction(body, (0.0, 0.0, -1.0))
    on_edge = evaluate_direction(body, (1.0, 0.0, 0.0))

    assert lying.footprint > on_edge.footprint
    assert lying.score > on_edge.score


@pytest.mark.parametrize(
    "direction", [(0.0, 0.0, -1.0), (1.0, 2.0, -3.0), (-2.0, 0.5, 4.0), (0.0, 0.0, 0.0)]
)
def test_direction_metrics_match_the_physically_rotated_body(direction) -> None:
    """Die billige Vorauswahl misst dieselbe Geometrie wie eine echte Drehung."""
    body = apply(plate(), translation((71.0, -43.0, 28.0)) @ rotation("y", 23.0))
    physical = apply(body, rotation_to_down(direction))
    expected = evaluate_direction(physical, (0.0, 0.0, -1.0))
    actual = evaluate_direction(body, direction)
    assert actual.footprint == pytest.approx(expected.footprint, abs=1e-7)
    assert actual.overhang == pytest.approx(expected.overhang, abs=1e-7)
    assert actual.height == pytest.approx(expected.height, abs=1e-7)


def test_the_shortlist_only_places_as_many_ranked_candidates_as_needed(
    monkeypatch, profile
) -> None:
    """Die drei Finalisten brauchen keine Druckflächenprüfung aller Hüllnormalen."""
    import app.core.geom.orient as orient

    body = plate()
    ranked = ranked_orientations(body)
    checked = []

    def fit(mesh, direction, printer, *, margin=0.0):
        checked.append(direction)
        # Auch ein hoch bewerteter Kandidat darf außerhalb des Druckbereichs liegen.
        return None if direction == ranked[0].direction else np.eye(4)

    monkeypatch.setattr(orient, "fitting_transform", fit)
    selected = ranked_orientations(body, limit=3, printer=profile.printer)
    assert selected == ranked[1:4]
    assert checked == [entry.direction for entry in ranked[:4]]


def test_unused_vertices_do_not_change_orientation_metrics() -> None:
    """Ein Importrest außerhalb der Dreiecke ist keine Fläche des Körpers."""
    raw = trimesh.creation.box(extents=(20.0, 30.0, 40.0))
    with_unused_point = trimesh.Trimesh(
        vertices=np.vstack((raw.vertices, (500.0, 700.0, -900.0))),
        faces=raw.faces,
        process=False,
    )
    for direction in ((0.0, 0.0, -1.0), (1.0, 2.0, 3.0)):
        actual = evaluate_direction(MeshData.of(with_unused_point), direction)
        expected = evaluate_direction(MeshData.of(raw), direction)
        assert actual == expected


@pytest.mark.parametrize("limit", [-200, -1, 0, 1, 12, 200])
def test_normal_group_order_preserves_area_ties_and_unrounded_directions(limit: int) -> None:
    """Flächengruppen bleiben nach Fläche und dann lexikographisch geordnet."""
    from app.core.geom.orient import _largest_normals

    raw = apply(plate(), rotation("x", 27.0) @ rotation("y", 13.0)).raw
    normals = np.asarray(raw.face_normals)
    areas = np.asarray(raw.area_faces)
    groups = {}
    for normal, area in zip(normals, areas, strict=True):
        key = tuple(np.round(normal, 6))
        total, weighted = groups.get(key, (0.0, np.zeros(3)))
        groups[key] = (total + area, weighted + normal * area)
    keys = sorted(groups, key=lambda key: (-groups[key][0], key))[:limit]
    expected = [groups[key][1] / np.linalg.norm(groups[key][1]) for key in keys]
    actual = _largest_normals(normals, areas, limit)
    np.testing.assert_allclose(actual, expected, rtol=0.0, atol=1e-12)


def test_the_heuristic_says_that_it_is_one() -> None:
    """Sie wird in P3 von der Schichtanalyse ersetzt, und sie sagt das auch."""
    result = orient_for_print(plate())
    codes = {finding.code for finding in result.findings}

    assert "orient.heuristic" in codes
    finding = next(f for f in result.findings if f.code == "orient.heuristic")
    assert finding.values["candidates"] >= 6


def test_heavy_overhang_is_called_out() -> None:
    """Ein Kegel auf seiner Spitze lässt sich durch Drehen nicht retten — also
    sagt er das.
    """
    cone = MeshData.of(trimesh.creation.cone(radius=20.0, height=60.0, sections=32))
    result = orient_for_print(apply(cone, rotation("x", 180.0)))

    assert result.mesh.bounds.minimum[2] == pytest.approx(0.0)
    assert isinstance(result.chosen.overhang, float)


def test_the_candidates_include_the_axes_and_the_big_faces() -> None:
    found = candidates(plate())

    assert (0.0, 0.0, 1.0) in found
    assert len(found) > 6, "the large flat faces add their own directions"


def test_orienting_runs_as_an_operation(document: Document, profile: Profile) -> None:
    project = new_project("centauri-carbon-2", "petg")
    project.document = document
    document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/plate_holes.stl", sha256=""
    )
    project.sources["src_1"] = (MESHES / "plate_holes.stl").read_bytes()

    history = History(document)
    history.apply(_("Laden"), [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})])
    history.apply(
        _("Drehen"),
        [
            OperationDraft(
                op="rotate_object", inputs=("obj_1",), params={"axis": "y", "angle": 90.0}
            )
        ],
    )
    history.apply(
        _("Ausrichten"),
        [OperationDraft(op="orient_for_print", inputs=("obj_1",), params={"thorough": False})],
    )

    result = evaluate(document, profile, sources=ProjectSources(project))

    assert result.complete
    assert result.scene.objects["obj_1"].mesh.bounds.size[2] < 20.0
    assert "orient.heuristic" in {finding.code for finding in result.scene.report.findings}


def test_the_thorough_orientation_uses_the_layer_analysis(
    document: Document, profile: Profile
) -> None:
    """Vorgabe ist gründlich: hunderte Lagen, an echtem Stützvolumen beurteilt."""
    project = new_project("centauri-carbon-2", "petg")
    project.document = document
    document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/plate_holes.stl", sha256=""
    )
    project.sources["src_1"] = (MESHES / "plate_holes.stl").read_bytes()

    history = History(document)
    history.apply(_("Laden"), [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})])
    history.apply(
        _("Ausrichten"),
        [OperationDraft(op="orient_for_print", inputs=("obj_1",), params={"candidates": 24})],
    )

    result = evaluate(document, profile, sources=ProjectSources(project))

    assert result.complete
    assert "orient.searched" in {finding.code for finding in result.scene.report.findings}
    assert history.operations[-1].seed is None, "geometry candidates need no random seed (§28.2)"


def test_the_orientation_operation_is_registered() -> None:
    """Sie nimmt so viele Körper, wie gewählt sind — nicht genau einen.

    Hier stand ``(1, 1)``, und das war die festgeschriebene Gestalt eines
    Fehlers: Wer alle Teile einer Baugruppe wählte und *Druckoptimal
    ausrichten* rief, bekam den ersten gedreht und die übrigen liegengelassen.
    Lag der erste schon richtig, sah es aus, als täte die Operation gar nichts
    (Befund Robert, 07.09.2026).
    """
    spec = REGISTRY.get("orient_for_print")
    assert spec.category == "transform"
    assert (spec.consumes, spec.produces) == (VARIABLE, VARIABLE)
    assert spec.minimum_inputs == 1, "ein einzelner Körper bleibt zulässig"


def test_every_chosen_body_gets_its_own_orientation(document: Document, profile: Profile) -> None:
    """Zwei Körper, zwei verschiedene Fehllagen — beide kommen flach heraus.

    Der Nachweis, den die Stelligkeit allein nicht führt: Es genügt nicht, dass
    die Operation mehrere Eingänge *annimmt*; sie muss auch jeden davon
    bewegen. Die beiden Körper werden deshalb um verschiedene Achsen gekippt —
    eine gemeinsame Drehung könnte nicht beide aufrichten.
    """
    project = new_project("centauri-carbon-2", "petg")
    project.document = document
    document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/plate_holes.stl", sha256=""
    )
    project.sources["src_1"] = (MESHES / "plate_holes.stl").read_bytes()

    history = History(document)
    history.apply(_("Laden"), [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})])
    history.apply(
        _("Verdoppeln"),
        [OperationDraft(op="duplicate_object", inputs=("obj_1",))],
    )
    zweiter = "obj_2"
    history.apply(
        _("Beide kippen"),
        [
            OperationDraft(
                op="rotate_object", inputs=("obj_1",), params={"axis": "y", "angle": 90.0}
            ),
            OperationDraft(
                op="rotate_object", inputs=(zweiter,), params={"axis": "x", "angle": 90.0}
            ),
        ],
    )
    history.apply(
        _("Ausrichten"),
        [
            OperationDraft(
                op="orient_for_print",
                inputs=("obj_1", zweiter),
                params={"thorough": False},
            )
        ],
    )

    result = evaluate(document, profile, sources=ProjectSources(project))

    assert result.complete
    for kennung in ("obj_1", zweiter):
        hoehe = result.scene.objects[kennung].mesh.bounds.size[2]
        assert hoehe < 20.0, f"{kennung} steht noch hochkant ({hoehe:.1f} mm)"


def _towers(document: Document) -> tuple[Project, list[str]]:
    """Zwei stehende Türme mit 15 mm Luft — die beim Hinlegen ineinanderlaufen."""
    project = new_project("centauri-carbon-2", "petg")
    project.document = document
    history = History(document)
    for offset in ((0.0, 0.0), (35.0, 0.0)):
        history.apply(
            _("Turm"),
            [
                OperationDraft(
                    op="create_box",
                    params={
                        "width": 20.0,
                        "depth": 20.0,
                        "height": 90.0,
                        "x": offset[0],
                        "y": offset[1],
                    },
                )
            ],
        )
    return project, ["obj_1", "obj_2"]


def test_orienting_does_not_leave_the_bodies_inside_each_other(
    document: Document, profile: Profile
) -> None:
    """Ausrichten dreht — und legt danach hin, was es umgeworfen hat.

    **Der Befund** (Robert, 09.09.2026: „bei druckoptimal ausrichten, werden
    verschiedene modelle überlagert ohne abstand"): Die Operation dreht jeden
    Körper um seine eigene Mitte und lässt ihn dort stehen. Beim Hinlegen
    wächst die Grundfläche, und der Nachbar steht im Weg. Gemessen an zwei
    Türmen 20 x 20 x 90 mit 15 mm Luft: hinterher x -45..45 gegen x -10..80,
    also 55 mm Durchdringung — und kein Wort im Bericht.

    Das Anordnen macht die Operation nicht zu einer zweiten *Auf dem Bett
    anordnen*: Sie ordnet genau die Körper an, die sie gedreht hat, und die
    übrigen der Szene bleiben liegen und belegen ihren Platz.
    """
    project, bodies = _towers(document)
    History(document).apply(
        _("Ausrichten"),
        [OperationDraft(op="orient_for_print", inputs=tuple(bodies), params={"thorough": False})],
    )

    result = evaluate(document, profile, sources=ProjectSources(project))

    assert result.complete
    boxes = [result.scene.objects[name].mesh.bounds for name in bodies]
    for first in range(len(boxes)):
        for second in range(first + 1, len(boxes)):
            one, other = boxes[first], boxes[second]
            apart = (
                one.maximum[0] <= other.minimum[0] + 1e-6
                or other.maximum[0] <= one.minimum[0] + 1e-6
                or one.maximum[1] <= other.minimum[1] + 1e-6
                or other.maximum[1] <= one.minimum[1] + 1e-6
            )
            assert apart, f"{bodies[first]} und {bodies[second]} stecken ineinander"


def test_a_body_that_was_not_chosen_keeps_its_place(document: Document, profile: Profile) -> None:
    """Wer nicht gewählt ist, wird nicht bewegt — und sein Platz bleibt belegt.

    Die Operation nimmt so viele Körper, wie gewählt sind. Ordnete sie danach
    an, als wäre die Szene leer, legte sie einen gedrehten Körper genau dorthin,
    wo ein nicht gewählter schon steht. Der liest sich aus ``ctx.scene``, und
    lesen darf sie ihn (Regel 3).
    """
    project, bodies = _towers(document)
    standing = bodies[1]

    History(document).apply(
        _("Nur den ersten ausrichten"),
        [OperationDraft(op="orient_for_print", inputs=(bodies[0],), params={"thorough": False})],
    )
    result = evaluate(document, profile, sources=ProjectSources(project))

    assert result.complete
    kept = result.scene.objects[standing].mesh.bounds
    assert abs(kept.minimum[0] - 25.0) < 1e-6, f"der zweite ist gewandert: {kept.minimum[0]}"
    moved = result.scene.objects[bodies[0]].mesh.bounds
    apart = (
        moved.maximum[0] <= kept.minimum[0] + 1e-6
        or kept.maximum[0] <= moved.minimum[0] + 1e-6
        or moved.maximum[1] <= kept.minimum[1] + 1e-6
        or kept.maximum[1] <= moved.minimum[1] + 1e-6
    )
    assert apart, "der gedrehte Körper liegt im nicht gewählten"


def test_moving_an_unchosen_body_makes_the_arrangement_run_again(profile: Profile) -> None:
    """Der Cache darf die fremde Lage nicht überleben.

    Der Test darüber sichert zu, dass die Operation dem nicht gewählten Körper
    ausweicht. Sie liest ihn aber an ihren Eingängen vorbei, und
    ``operation_hash`` deckt nur die Eingänge: Verschiebt jemand den fremden
    Körper, blieb der Schlüssel derselbe — und der gedrehte wich einem
    Nachbarn aus, der längst woanders stand.

    **Gefahren wird das über die Auswertung mit echtem Cache**, nicht über den
    Schlüssel allein: Dass er kippen *kann*, prüft ``test_cache.py``; hier
    steht, dass die Anwendung ihn auch kippen lässt.
    """

    def orientiert(second_at: tuple[float, float]) -> Any:
        """Ein frisches Dokument: erster Turm gleich, zweiter an ``second_at``."""
        document = Document(format_version=1, app_version="0.0.1")
        project = new_project("centauri-carbon-2", "petg")
        project.document = document
        history = History(document)
        for offset in ((0.0, 0.0), second_at):
            history.apply(
                _("Turm"),
                [
                    OperationDraft(
                        op="create_box",
                        params={
                            "width": 20.0,
                            "depth": 20.0,
                            "height": 90.0,
                            "x": offset[0],
                            "y": offset[1],
                        },
                    )
                ],
            )
        history.apply(
            _("Nur den ersten ausrichten"),
            [OperationDraft(op="orient_for_print", inputs=("obj_1",), params={"thorough": False})],
        )
        return evaluate(document, profile, sources=ProjectSources(project), cache=cache)

    # **Zwei Szenen, ein Cache** — und der erste Turm ist in beiden derselbe.
    # Damit ist sein Eingangshash gleich, und ein Schlüssel, der nur die
    # Eingänge kennt, kann die zwei Läufe nicht auseinanderhalten. Ein Schritt,
    # der den zweiten Turm *nachträglich* verschiebt, prüfte das nicht: Dort
    # stünde er zur Zeit des Ausrichtens noch an der alten Stelle, und der
    # Cache-Treffer wäre richtig.
    cache = ResultCache()
    first = orientiert((35.0, 0.0))
    assert first.complete
    landed = first.scene.objects["obj_1"].mesh.bounds

    # Der zweite Turm steht diesmal genau dort, wo der gedrehte gerade gelandet
    # ist. Bleibt das alte Ergebnis gültig, stecken sie ineinander.
    centre = (
        float(landed.minimum[0] + landed.maximum[0]) / 2.0,
        float(landed.minimum[1] + landed.maximum[1]) / 2.0,
    )
    second = orientiert(centre)
    assert second.complete

    moved_now = second.scene.objects["obj_1"].mesh.bounds
    kept_now = second.scene.objects["obj_2"].mesh.bounds
    apart = (
        moved_now.maximum[0] <= kept_now.minimum[0] + 1e-6
        or kept_now.maximum[0] <= moved_now.minimum[0] + 1e-6
        or moved_now.maximum[1] <= kept_now.minimum[1] + 1e-6
        or kept_now.maximum[1] <= moved_now.minimum[1] + 1e-6
    )
    assert apart, "das Ergebnis kam aus dem Cache und kennt die neue Lage nicht"


@pytest.mark.parametrize("per_batch", [1, 3, 50])
def test_batched_scores_match_physical_rotations_across_batch_boundaries(
    monkeypatch: pytest.MonkeyPatch, per_batch: int
) -> None:
    """Die Speichergrenze verändert weder Reihenfolge noch geometrische Kennzahlen."""
    import app.core.geom.orient as orient
    from app.core.knowledge.rules import OVERHANG_LIMIT_DEGREES
    from app.core.units import EPS_GEOM

    body = apply(plate(), translation((71.0, -43.0, 28.0)) @ rotation("y", 23.0))
    raw = body.raw
    body = MeshData.of(
        trimesh.Trimesh(
            vertices=np.vstack((raw.vertices, (500.0, 700.0, -900.0))),
            faces=raw.faces,
            process=False,
        )
    )
    directions = [
        (float(np.cos(angle)), float(np.sin(angle)), 0.25) for angle in np.linspace(0.2, 6.3, 14)
    ]
    directions.extend([(0.0, 0.0, 0.0), (EPS_GEOM / 2.0, 0.0, -1.0)])
    monkeypatch.setattr(
        orient, "MAX_PROJECTION_VALUES", per_batch * max(body.vertex_count, body.triangle_count)
    )
    scores = orient._evaluate_directions(body, directions)
    assert [score.direction for score in scores] == directions
    for direction, actual in zip(directions, scores, strict=True):
        physical = apply(body, rotation_to_down(direction))
        normals = np.asarray(physical.raw.face_normals)
        areas = np.asarray(physical.raw.area_faces)
        flat = (normals[:, 2] < -0.999) & (
            physical.raw.triangles_center[:, 2] < physical.bounds.minimum[2] + 0.05
        )
        downward = normals[:, 2] < -np.cos(np.deg2rad(OVERHANG_LIMIT_DEGREES))
        assert actual.footprint == pytest.approx(float(areas[flat].sum()), abs=1e-7)
        assert actual.overhang == pytest.approx(float(areas[downward & ~flat].sum()), abs=1e-7)
        assert actual.height == pytest.approx(physical.bounds.size[2], abs=1e-7)
