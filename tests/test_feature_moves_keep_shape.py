"""Merkmalshandlungen lassen den Körper, wie er war — bis auf das Merkmal selbst.

Drei Befunde der Netzkern-Durchsicht vom 21.09.2026, jeder mit seiner Zahl:
Ein Versetzen am Netz ließ rund 270 Dreiecke Narben zurück (796 → 1042 →
1308 → 1576 → 1852 an der Lochplatte), eine vergrabene Senkung am exakten
Körper verlor je Versetzen ein Scheibchen von 1,33 mm³, und ein Ring ohne
gemessene Achse wurde still an der Z-Achse bearbeitet. Dazu, was eine
Handlung weiterreicht und was sie sich merkt: Die durchgereichten Merkmale
tragen am neuen Netz keine alten Dreiecksnummern, und ob eine Bohrung leer
ist, wird je Körper und Bohrung einmal gerechnet.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from app.core.bootstrap import load_operations
from app.core.errors import CHANGE_SELECTION, ValidationError
from app.core.geom import prepare_ops
from app.core.ingest.plan import import_plan
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import ProjectSources, checksum, new_project
from app.core.types import Feature, Profile, Source

MESHES = Path(__file__).parent / "data" / "meshes"


def _loaded_plate():
    """Die Lochplatte des Korpus als Projekt, ausgewertet — wie sie der Kunde öffnet."""
    load_operations()
    payload = (MESHES / "plate_holes.stl").read_bytes()
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/plate_holes.stl", sha256=checksum(payload)
    )
    project.sources["src_1"] = payload
    plan = import_plan("src_1", "plate_holes.stl", payload, first_model=True)
    history = History(project.document)
    history.apply(plan.title, [plan.draft])
    return project, history


def test_moving_a_bore_four_times_leaves_no_scars(profile: Profile) -> None:
    """Vier Züge derselben Bohrung: gleiches Volumen, gleicher Durchmesser, und die
    Dreieckszahl bleibt bei der der Platte — die koplanaren Kappen des Stopfens
    werden zusammengelegt, sobald Dichtheit und Volumen es erlauben."""
    project, history = _loaded_plate()
    sources = ProjectSources(project)

    def state():
        result = evaluate(project.document, profile, sources=sources)
        assert result.complete, [str(f.message) for f in result.scene.report.findings]
        body = next(iter(result.scene.objects.values()))
        return body, body.features["hole_1"]

    body, hole = state()
    triangles, volume = body.mesh.triangle_count, body.mesh.volume
    diameter = float(hole.params["diameter"])
    for step in range(1, 5):
        centre = hole.params["centre"]
        history.apply(
            f"Versetzen {step}",
            [
                OperationDraft(
                    op="move_feature",
                    inputs=(body.id,),
                    params={
                        "at_feature": hole.id,
                        "x": float(centre[0]) + 2.0,
                        "y": float(centre[1]),
                        "z": float(centre[2]),
                    },
                    seed=step,
                )
            ],
        )
        body, hole = state()
        assert body.mesh.volume == pytest.approx(volume, abs=1e-6)
        assert float(hole.params["diameter"]) == pytest.approx(diameter, abs=1e-6)
        # Das Netz wächst je Zug um höchstens ein paar Dreiecke, nicht um 270.
        assert body.mesh.triangle_count <= triangles + 8, (step, body.mesh.triangle_count)


def test_a_buried_countersink_keeps_its_volume_when_moved(profile: Profile) -> None:
    """Eine Senkung, deren Mündung unter der Oberfläche liegt, ist ein vergrabener
    Hohlraum: Ihr Deckel ist Material, keine Mündung, und bekommt beim Versetzen
    keine Zugabe. Volumen und Tiefe bleiben; die offene Kette daneben ebenso."""
    from tests.helpers import exact_kernel

    exact_kernel()
    load_operations()
    outcomes = {}
    for mouth in (6.0, 8.0):
        project = new_project("centauri-carbon-2", "petg")
        history = History(project.document)
        history.apply(
            "Quader",
            [
                OperationDraft(
                    op="create_brep_box", params={"width": 40.0, "depth": 40.0, "height": 8.0}
                )
            ],
        )
        history.apply(
            "Bohren",
            [
                OperationDraft(
                    op="drill_hole",
                    inputs=("obj_1",),
                    params={
                        "diameter": 5.0,
                        "x": 0.0,
                        "y": 0.0,
                        "z": mouth,
                        "axis": "z",
                        "depth": 0.0,
                        "widening_diameter": 9.0,
                        "widening_depth": 2.0,
                        "anchor": "mouth",
                    },
                )
            ],
        )
        sources = ProjectSources(project)
        before = evaluate(project.document, profile, sources=sources)
        assert before.complete
        body = before.scene.objects["obj_1"]
        hole = next(
            f for f in body.features.values() if f.kind == "hole" and f.params["diameter"] < 6
        )
        wide = next(
            f for f in body.features.values() if f.kind == "hole" and f.params["diameter"] > 6
        )
        centre = hole.params["centre"]
        history.apply(
            "Versetzen",
            [
                OperationDraft(
                    op="move_feature",
                    inputs=("obj_1",),
                    params={
                        "at_feature": hole.id,
                        "x": float(centre[0]) + 5.0,
                        "y": float(centre[1]) + 5.0,
                        "z": float(centre[2]),
                    },
                    seed=1,
                )
            ],
        )
        after = evaluate(project.document, profile, sources=sources)
        assert after.complete, [str(f.message) for f in after.scene.report.findings]
        moved = after.scene.objects["obj_1"]
        assert moved.kind == "brep"
        assert moved.mesh.volume == pytest.approx(body.mesh.volume, abs=1e-6), mouth
        wide_after = next(
            f for f in moved.features.values() if f.kind == "hole" and f.params["diameter"] > 6
        )
        assert float(wide_after.params["depth"]) == pytest.approx(
            float(wide.params["depth"]), abs=1e-6
        )
        outcomes[mouth] = (body.mesh.volume, moved.mesh.volume)
    assert outcomes[6.0][0] > outcomes[8.0][0], "die vergrabene Senkung nimmt weniger Material"


def test_a_ring_without_a_measured_axis_is_refused_not_guessed() -> None:
    """Ein Ring ohne Achse hat keine Lage, an der ein Werkzeug ansetzen könnte — die
    Absage nennt die Auswahl, statt still die Z-Achse zu nehmen."""
    feature = Feature(
        id="ring_1",
        kind="torus",
        provenance="detected",
        params={"centre": (0.0, 0.0, 0.0), "axis": (0.0, 0.0, 1.0), "diameter": 20.0},
    )
    axis = prepare_ops._torus_axis(feature)
    assert np.allclose(axis, (0.0, 0.0, 1.0))
    with pytest.raises(ValidationError) as caught:
        prepare_ops._torus_axis(feature, (0.0, 0.0, 0.0))
    assert CHANGE_SELECTION in caught.value.suggestions
    assert caught.value.constraint == "not_movable"


def _raw(op: str, entry, profile: Profile, **params: object):
    """Eine Operation roh fahren — ohne die Auswertung, die die Merkmale auffrischt."""
    from app.core.registry import REGISTRY
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene

    spec = REGISTRY.get(op)
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=7,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


@pytest.mark.parametrize(
    ("op", "params", "carried"),
    [
        ("remove_feature", {}, 4),
        ("plug_hole", {}, 4),
        ("move_feature", {"x": -30.0, "y": 0.0, "z": 5.0}, 4),
        ("duplicate_feature", {"x": -30.0, "y": 0.0, "z": 5.0}, 4),
        ("rotate_feature", {"angle": 20.0}, 4),
        # Bohrung ändern reicht nur erzeugte Merkmale weiter; erkannte holt die
        # Auswertung ohnehin neu — hier bleibt keine der vier übrig.
        ("resize_hole", {"diameter": 7.0, "compensate": False}, 0),
    ],
)
def test_a_mesh_operation_hands_no_old_triangle_numbers_on(
    op: str, params: dict[str, float], carried: int, profile: Profile
) -> None:
    """Die durchgereichten Merkmale tragen am neuen Netz keine Dreiecksnummern.

    Die Vereinigung mit dem Stopfen nummeriert neu, und das Zusammenlegen der
    Narben vernetzt die Deckflächen ganz neu; die alten Nummern der vier
    unberührten Bohrungen bezeichneten danach fremde Dreiecke — und der
    nächste Schritt hielt eine intakte Bohrung für unlesbar. Ort und Maß
    bleiben, die Oberfläche holt sich die Auswertung an der Erkennung.
    """
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.geom.prepare import drill
    from app.core.perceive.features import detect
    from app.core.types import SceneObject

    load_operations()
    plate = MeshData.of(trimesh.creation.box(extents=(100.0, 40.0, 10.0)))
    for x in (-40.0, -20.0, 0.0, 20.0, 40.0):
        plate = drill(
            plate, position=(x, 0.0, 5.0), axis="z", diameter=6.0, profile=profile, compensate=False
        ).mesh
    entry = SceneObject(id="obj_1", name="Platte", mesh=plate, features=detect(plate))
    bores = [name for name, found in entry.features.items() if found.kind == "hole"]
    assert len(bores) == 5, bores
    assert all(entry.features[name].face_indices for name in bores), "die Erkennung belegt jede"

    result = _raw(op, entry, profile, at_feature=bores[2], **params)
    output = result.outputs[0]
    assert output.mesh.triangle_count > 0
    untouched = [name for name in bores if name != bores[2] and name in output.features]
    assert len(untouched) == carried, (op, untouched)
    for name in untouched:
        feature = output.features[name]
        assert feature.face_indices == (), (op, name, feature.face_indices[:5])
        assert feature.surface_patches == (), (op, name)
        assert feature.params["centre"] == entry.features[name].params["centre"]
    for name, feature in output.features.items():
        if feature.face_indices:
            assert max(feature.face_indices) < output.mesh.triangle_count, (op, name)


def test_whether_a_bore_is_clear_is_answered_once_per_body_and_bore(
    monkeypatch: pytest.MonkeyPatch, profile: Profile
) -> None:
    """Das Merkmalfenster fragt es bei jedem Klick zweimal — gerechnet wird einmal.

    An der Lochplatte mit 360 000 Dreiecken kostete jede Antwort 90 ms, weil
    die Endebenen dafür eine Kopie des Netzes verschweißen (Paket C/D,
    22.09.2026). Die Antwort hängt an Körper, Flächen, Achse, Mitte und Maßen
    und stirbt mit dem Körper.
    """
    import gc

    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.geom.prepare import drill
    from app.core.perceive.features import detect

    plate = MeshData.of(trimesh.creation.box(extents=(60.0, 40.0, 10.0)))
    for x in (-15.0, 15.0):
        plate = drill(
            plate, position=(x, 0.0, 5.0), axis="z", diameter=8.0, profile=profile, compensate=False
        ).mesh
    bores = [found for found in detect(plate).values() if found.kind == "hole"]
    assert len(bores) == 2, bores

    calls: list[str] = []
    read = prepare_ops._hole_is_clear_read

    def counted(mesh, feature, radius, depth):
        calls.append(feature.id)
        return read(mesh, feature, radius, depth)

    monkeypatch.setattr(prepare_ops, "_hole_is_clear_read", counted)
    assert prepare_ops.hole_is_clear(plate, bores[0]) is True
    assert prepare_ops.hole_is_clear(plate, bores[0]) is True
    assert calls == [bores[0].id], "dieselbe Frage an denselben Körper rechnet einmal"
    assert prepare_ops.hole_is_clear(plate, bores[1]) is True
    assert calls == [bores[0].id, bores[1].id], "eine andere Bohrung ist eine andere Frage"

    # Ein Zapfen in der Bohrung: die Antwort kippt, und auch sie wird gemerkt.
    pin = trimesh.creation.cylinder(radius=2.0, height=10.0, sections=32)
    pin.apply_translation((float(bores[0].params["centre"][0]), 0.0, 5.0))
    blocked = MeshData.of(trimesh.util.concatenate([plate.raw.copy(), pin]))
    assert prepare_ops.hole_is_clear(blocked, bores[0]) is False
    assert prepare_ops.hole_is_clear(blocked, bores[0]) is False
    assert len(calls) == 3, "ein anderer Körper rechnet neu — einmal"

    # Stirbt der Körper, stirbt seine Antwort: derselbe Körper neu gebaut rechnet neu.
    del blocked
    gc.collect()
    again = MeshData.of(trimesh.util.concatenate([plate.raw.copy(), pin]))
    assert prepare_ops.hole_is_clear(again, bores[0]) is False
    assert len(calls) == 4
