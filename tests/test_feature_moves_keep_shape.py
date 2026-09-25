"""Merkmalshandlungen lassen den Körper, wie er war — bis auf das Merkmal selbst.

Drei Befunde der Netzkern-Durchsicht vom 21.09.2026, jeder mit seiner Zahl:
Ein Versetzen am Netz ließ rund 270 Dreiecke Narben zurück (796 → 1042 →
1308 → 1576 → 1852 an der Lochplatte), eine vergrabene Senkung am exakten
Körper verlor je Versetzen ein Scheibchen von 1,33 mm³, und ein Ring ohne
gemessene Achse wurde still an der Z-Achse bearbeitet. Dazu, was eine
Handlung weiterreicht und was sie sich merkt: Die durchgereichten Merkmale
tragen am neuen Netz keine alten Dreiecksnummern, und ob eine Bohrung leer
ist, wird je Körper und Bohrung einmal gerechnet.

Und aus RM-220 (25.09.2026): Eine gekippte Bohrung trägt nichts ab, was vor
ihren alten Mündungen steht, eine versetzte sagt, was sie an der neuen Stelle
wirklich ist — und beide Kerne antworten dasselbe.
"""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from app.core.bootstrap import load_operations
from app.core.errors import CHANGE_SELECTION, ValidationError
from app.core.geom import prepare_ops
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.ingest.plan import import_plan
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import ProjectSources, checksum, new_project
from app.core.types import Feature, Finding, Profile, SceneObject, Source

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


# --- Kippen und Versetzen gesenkter Bohrungen (RM-220) ------------------------------

#: Die Bohrungsprofile der Rippenplatte, als (Radius, Höhe) um die Z-Achse.
RIBBED: dict[str, list[tuple[float, float]]] = {
    "gesenkt": [(0, 0), (3, 0), (3, 10), (5, 12), (0, 12), (0, 0)],
    "durchgehend": [(0, 0), (3, 0), (3, 12), (0, 12), (0, 0)],
    "gesenktes Sackloch": [(0, 2), (3, 2), (3, 10), (5, 12), (0, 12), (0, 2)],
    "vergrabene Senkung": [(0, 0), (3, 0), (3, 8), (5, 10), (0, 10), (0, 0)],
    "Senkung ohne Bohrung": [(0, 9), (1, 9), (4, 12), (0, 12), (0, 9)],
}

#: Gesenkte Durchgangsbohrung Ø 6 mit 90°-Senkung Ø 10 in der Platte 30 x 24 x 12.
SUNK = RIBBED["gesenkt"]


def _body(kernel: str, solid: Any) -> SceneObject:
    """Derselbe exakte Körper als ``brep`` oder als sein Netz, je mit seiner Erkennung."""
    from app.core.brep.features import features_of
    from app.core.perceive.features import detect

    if kernel == "brep":
        return SceneObject("plate", "Platte", solid, kind="brep", features=features_of(solid))
    mesh = as_mesh_data(solid)
    return SceneObject("plate", "Platte", mesh, features=detect(mesh))


def _bored(kernel: str, outline: Sequence[tuple[float, float]], *, ribbed: bool) -> SceneObject:
    """Platte 30 × 24 × 12 mit einer Bohrung aus ``outline`` in der Mitte.

    ``ribbed`` stellt Material vor beide Mündungen, das die gerade Bohrung nie
    berührt: eine Rippe auf der Oberseite (y −12 … −6, z 12 … 18) und einen Fuß
    unter der Unterseite (y 3,5 … 12, z −6 … 0).
    """
    from app.core.brep import edit
    from app.core.sketch.planes import frame_of

    plate = edit.box(30.0, 24.0, 12.0)
    if ribbed:
        plate = edit.unified(
            edit.boolean(
                "union",
                [
                    plate,
                    edit.moved(edit.box(30.0, 6.0, 6.0), (0.0, -9.0, 12.0)),
                    edit.moved(edit.box(30.0, 8.5, 6.0), (0.0, 7.75, -6.0)),
                ],
            )
        )
    solid = edit.bore_profile(plate, list(outline), frame_of((0, 0, 1), (0, 0, 0)))
    return _body(kernel, solid)


def _narrowest_hole(source: SceneObject) -> Feature:
    """Die Bohrung einer Kette — oder die Senkung, wo es keine Bohrung gibt."""
    holes = [feature for feature in source.features.values() if feature.kind == "hole"]
    if not holes:
        holes = [feature for feature in source.features.values() if feature.kind == "cone"]
    return min(holes, key=lambda feature: float(feature.params["diameter"]))


def _warnings(findings: Sequence[Finding]) -> list[str]:
    return sorted({finding.code for finding in findings if finding.severity == "warning"})


def _removed(before: SceneObject, after: SceneObject) -> MeshData:
    """Was die Handlung abgetragen hat, als Körper."""
    from app.core.geom.boolean import boolean

    return boolean(
        "difference", [as_mesh_data(before.mesh), as_mesh_data(after.mesh)], allow_empty=True
    ).mesh


def _beyond(mesh: MeshData, height: float, *, above: bool) -> float:
    """Das Volumen von ``mesh`` über (``above``) oder unter der Höhe ``height``."""
    from app.core.geom.section import SectionPlane, cut

    if not len(mesh.raw.faces):
        return 0.0
    plane = (
        SectionPlane(normal=(0.0, 0.0, -1.0), position=-height)
        if above
        else SectionPlane(position=height)
    )
    kept = cut(mesh, plane).mesh
    return abs(float(kept.volume)) if len(kept.raw.faces) else 0.0


@pytest.mark.parametrize("case", list(RIBBED))
def test_a_tilted_bore_takes_nothing_from_what_stands_before_its_mouths(
    profile: Profile, case: str
) -> None:
    """Um 30° gekippt, trägt die Bohrung nichts vor ihren alten Mündungen ab —
    an beiden Kernen gleich.

    Damit eine gekippte Bohrung durchgeht und eine gekippte Senkung die Fläche
    überall verlässt, wird das Werkzeug über die Mündungen hinaus verlängert.
    Gemessen am 25.09.2026 an dieser Platte: 738 mm³ Abtrag in der Rippe über
    der Senkung, an beiden Kernen; die vergrabene Senkung schnitt ihren Deckel
    durch (948 mm³); der exakte Kern bohrte die schlichte Durchgangsbohrung
    durch Rippe und Fuß, wo das Netz vor ihnen endete. Am Schraubenhalter mit
    Wabenmuster lagen 314 von 714 mm³ in den Waben. Dazu meldeten beide Kerne
    „über die Kante", weil die Achse erst auf der Rippe aus dem Hüllquader trat.
    Eine Senkung ohne Bohrung behielt am Netz auf einer Seite eine Decke (das
    Volumen stieg um 11 mm³) und schnitt am exakten Körper 80 mm³ aus der Rippe.
    """
    from app.core.geom.prepare import FEATURE_OVERLAP
    from tests.test_bore_depth import _evaluated

    top = 10.0 if case == "vergrabene Senkung" else 12.0
    seen = {}
    for kernel in ("mesh", "brep"):
        source = _bored(kernel, RIBBED[case], ribbed=True)
        hole = _narrowest_hole(source)
        changed, findings = _evaluated(
            source, profile, "rotate_feature", at_feature=hole.id, axis="x", angle=30.0
        )
        lost = _removed(source, changed)
        assert _beyond(lost, top + FEATURE_OVERLAP, above=True) == pytest.approx(0.0, abs=0.01), (
            kernel
        )
        assert _beyond(lost, -FEATURE_OVERLAP, above=False) == pytest.approx(0.0, abs=0.01), kernel
        codes = _warnings(findings)
        assert "bore.over_the_edge" not in codes, (kernel, codes)
        cones = [feature for feature in changed.features.values() if feature.kind == "cone"]
        seen[kernel] = (
            float(lost.volume),
            codes,
            bool(changed.features[hole.id].params.get("through")),
            [float(cone.params["diameter"]) for cone in cones],
        )
    mesh, brep = seen["mesh"], seen["brep"]
    assert mesh[0] == pytest.approx(brep[0], rel=0.01), "beide Kerne tragen dasselbe ab"
    assert mesh[1] == brep[1], "beide Kerne sagen dasselbe"
    assert mesh[2] == brep[2], "beide Kerne halten dieselbe Bohrung für durchgehend"
    assert mesh[3] == pytest.approx(brep[3], abs=0.1), "die Senkung ist am Ergebnis gemessen"


def _with_neighbour(kernel: str, outline: Sequence[tuple[float, float]]) -> SceneObject:
    """Platte 40 × 24 × 12, bei x = 0 eine Bohrung aus ``outline``, bei x = 10 eine
    Durchgangsbohrung Ø 6 — 4 mm Wand zwischen den Schäften."""
    from app.core.brep import edit
    from app.core.sketch.planes import frame_of

    solid = edit.bore_profile(
        edit.box(40.0, 24.0, 12.0), list(outline), frame_of((0, 0, 1), (0, 0, 0))
    )
    solid = edit.bore_profile(solid, RIBBED["durchgehend"], frame_of((0, 0, 1), (10.0, 0, 0)))
    return _body(kernel, solid)


@pytest.mark.parametrize("case", ["gesenkt", "durchgehend"])
@pytest.mark.parametrize("angle", [30.0, -30.0])
def test_a_tilted_bore_reports_its_neighbour_on_both_kernels(
    profile: Profile, case: str, angle: float
) -> None:
    """Die Nachbarwand fragt auch der exakte Körper.

    Am Netz fragt das Kippen seit RM-133, ob die Wand zur Bohrung daneben
    dünn wird oder aufreißt; ``_exact_rotate_cavity`` und
    ``_exact_rotate_chain`` fragten nicht, und derselbe Schritt schwieg am
    exakten Körper (RM-220). Gemessen am 25.09.2026: um 30° zur Nachbarin hin
    reißt die gesenkte Bohrung die Wand auf, davon weg bleiben 0,64 mm, die
    schlichte Bohrung lässt 0,06 mm. Und die Senkung, die in die Mündung der
    Nachbarin läuft, hieß daneben „über die Kante" — an beiden Kernen.
    """
    from tests.test_bore_depth import _evaluated

    seen = {}
    for kernel in ("mesh", "brep"):
        source = _with_neighbour(kernel, RIBBED[case])
        hole = min(
            (feature for feature in source.features.values() if feature.kind == "hole"),
            key=lambda feature: abs(float(feature.params["centre"][0])),
        )
        _changed, findings = _evaluated(
            source, profile, "rotate_feature", at_feature=hole.id, axis="y", angle=angle
        )
        walls = [finding for finding in findings if finding.code.startswith("bore.neighbour_")]
        assert walls, (kernel, [finding.code for finding in findings])
        assert "bore.over_the_edge" not in _warnings(findings), (
            "die Mündung der Nachbarin ist keine Kante"
        )
        seen[kernel] = (walls[0].code, float(walls[0].values["thickness"]))
    assert seen["mesh"][0] == seen["brep"][0]
    assert seen["mesh"][1] == pytest.approx(seen["brep"][1], abs=0.05)


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
def test_a_countersunk_bore_moved_along_its_axis_says_what_it_is_there(
    profile: Profile, kernel: str
) -> None:
    """Versetzt wird starr — erklärt wird, was am Ergebnis steht.

    Am Schraubenhalter wanderte eine gesenkte Bohrung 1 mm entlang ihrer
    Achse; das Netz erklärte die Senkung danach mit Ø 8,8 einen Millimeter vor
    der Fläche, am Körper stand sie mit Ø 6,8 in ihr (RM-220). Nach außen
    versetzt, misst die Senkung an der Fläche Ø 8; nach innen liegt sie unter
    einem Deckel, und die Bohrung geht an keinem Kern mehr durch — der exakte
    sagte das vorher nicht.
    """
    from tests.test_bore_depth import _evaluated

    for rise in (1.0, -1.0):
        source = _bored(kernel, SUNK, ribbed=False)
        hole = _narrowest_hole(source)
        cone = next(feature for feature in source.features.values() if feature.kind == "cone")
        x, y, z = (float(value) for value in hole.params["centre"])
        changed, findings = _evaluated(
            source, profile, "move_feature", at_feature=hole.id, x=x, y=y, z=z + rise
        )
        assert "move_feature.no_longer_through" in _warnings(findings), (rise, findings)
        assert changed.features[hole.id].params["through"] is False, rise
        sink = changed.features[cone.id]
        wide, level = (8.0, 12.0) if rise > 0 else (10.0, 11.0)
        assert float(sink.params["diameter"]) == pytest.approx(wide, abs=0.1), rise
        assert float(sink.params["centre"][2]) == pytest.approx(level, abs=0.05), rise


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
@pytest.mark.parametrize("op", ["move_feature", "duplicate_feature"])
def test_a_blind_countersink_set_under_the_surface_says_its_mouth_is_covered(
    profile: Profile, kernel: str, op: str
) -> None:
    """Eine Sackbohrung hat keinen Durchgang, der verloren gehen könnte — und
    sagte deshalb nichts, wenn ihre Mündung unter Material geriet.

    An einer schrägen Außenfläche um 3 mm quer versetzt, lag die Senkung
    0,24 mm unter der Fläche, zugedeckt von einer Druckschicht (RM-220,
    25.09.2026). Hier dieselbe Lage an der ebenen Platte: 8 mm quer und 1 mm
    tiefer. Quer allein bleibt die Mündung offen, und es kommt kein Satz.
    """
    from tests.test_bore_depth import _evaluated

    source = _bored(kernel, RIBBED["gesenktes Sackloch"], ribbed=False)
    hole = _narrowest_hole(source)
    x, y, z = (float(value) for value in hole.params["centre"])
    _deeper, findings = _evaluated(
        source, profile, op, at_feature=hole.id, x=x + 8.0, y=y, z=z - 1.0
    )
    assert f"{op}.mouth_covered" in _warnings(findings), _warnings(findings)
    _across, findings = _evaluated(source, profile, op, at_feature=hole.id, x=x + 8.0, y=y, z=z)
    assert f"{op}.mouth_covered" not in _warnings(findings), _warnings(findings)


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
@pytest.mark.parametrize("op", ["move_feature", "duplicate_feature"])
def test_a_through_bore_set_along_its_axis_leaves_material_on_both_kernels(
    profile: Profile, kernel: str, op: str
) -> None:
    """Starr versetzt, bleibt Material stehen — auch am exakten Körper.

    Am Netz ist es seit dem 03.09.2026 so entschieden und gemeldet
    (``no_longer_through``). Der exakte Kern schnitt eine Durchgangsbohrung
    über die ganze Zielhülle und bohrte an der neuen Stelle durch alles auf
    ihrer Linie; entlang der Achse versetzt, blieb sie durchgehend (RM-220).
    Und die Kopie am Netz behielt ``through``, obwohl der Satz das Gegenteil
    sagte.
    """
    from tests.test_bore_depth import _evaluated

    source = _bored(kernel, RIBBED["durchgehend"], ribbed=False)
    hole = _narrowest_hole(source)
    x, y, z = (float(value) for value in hole.params["centre"])
    changed, findings = _evaluated(
        source, profile, op, at_feature=hole.id, x=x + 8.0, y=y, z=z + 3.0
    )
    assert f"{op}.no_longer_through" in _warnings(findings), _warnings(findings)
    placed = [
        feature
        for feature in changed.features.values()
        if feature.kind == "hole" and float(feature.params["centre"][0]) > 4.0
    ]
    assert len(placed) == 1, placed
    assert placed[0].params["through"] is False


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
@pytest.mark.parametrize("case", ["gesenkt", "Senkung ohne Bohrung"])
def test_a_countersink_tilted_past_its_flank_is_refused_with_the_largest_angle(
    profile: Profile, kernel: str, case: str
) -> None:
    """Um ihren halben Öffnungswinkel gekippt, schließt sich eine Senkung nicht mehr.

    Ihre Flanke liegt dann flacher als die Fläche, und das Werkzeug lief als
    Rinne bis an den Rand des Körpers: 671 mm³ aus einer Platte von 8 256, an
    beiden Kernen, mit „über die Kante" als einzigem Satz (RM-220, 25.09.2026).
    Die Operation sagt ab und nennt den größten Winkel; knapp darunter bleibt
    es eine Senkung.
    """
    from tests.test_bore_depth import _evaluated

    source = _bored(kernel, RIBBED[case], ribbed=False)
    feature = _narrowest_hole(source)
    with pytest.raises(ValidationError) as refused:
        _evaluated(source, profile, "rotate_feature", at_feature=feature.id, axis="x", angle=45.0)
    assert refused.value.constraint == "sink_runs_out"
    assert "45,0" in str(refused.value) or "45.0" in str(refused.value)
    changed, _findings = _evaluated(
        source, profile, "rotate_feature", at_feature=feature.id, axis="x", angle=40.0
    )
    assert float(as_mesh_data(changed.mesh).volume) < float(as_mesh_data(source.mesh).volume)


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
@pytest.mark.parametrize("case", ["gesenkt", "durchgehend"])
def test_a_bore_moved_towards_its_neighbour_says_what_is_left_of_the_wall(
    profile: Profile, kernel: str, case: str
) -> None:
    """*Merkmal versetzen* fragt die Nachbarwand — wie Kippen und Neuschnitt.

    Gemessen am 25.09.2026: Eine Bohrung Ø 6, um 4,5 mm auf die Bohrung 10 mm
    daneben zu versetzt, riss die Trennwand auf, und an keinem Kern sagte der
    Schritt etwas; um 3,5 mm blieben 0,5 mm Wand, und auch das blieb still.
    Von der Nachbarin weg bleibt es still.
    """
    from tests.test_bore_depth import _evaluated

    source = _with_neighbour(kernel, RIBBED[case])
    hole = min(
        (feature for feature in source.features.values() if feature.kind == "hole"),
        key=lambda feature: abs(float(feature.params["centre"][0])),
    )
    x, y, z = (float(value) for value in hole.params["centre"])
    # Die Senkung Ø 10 kommt der Nachbarin 2 mm früher nahe als der Schaft Ø 6.
    reach = 2.0 if case == "gesenkt" else 0.0
    for step, expected in (
        (3.5 - reach, "bore.neighbour_wall_thin"),
        (4.5 - reach, "bore.neighbour_opened"),
    ):
        _moved, findings = _evaluated(
            source, profile, "move_feature", at_feature=hole.id, x=x + step, y=y, z=z
        )
        codes = _warnings(findings)
        assert expected in codes, (step, codes)
        assert "bore.over_the_edge" not in codes, (step, codes)
    _moved, findings = _evaluated(
        source, profile, "move_feature", at_feature=hole.id, x=x - 3.5, y=y, z=z
    )
    assert not [code for code in _warnings(findings) if code.startswith("bore.neighbour_")]


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
@pytest.mark.parametrize("case", ["gesenkt", "durchgehend"])
def test_a_copy_set_beside_its_original_says_what_is_left_of_the_wall(
    profile: Profile, kernel: str, case: str
) -> None:
    """*Merkmal verdoppeln* fragt die Wand zur Vorlage — die ist hier die Nachbarin.

    Vorher gab es keine Wand, die dünner werden konnte; jede zu dünne zählt.
    Ø 6 neben Ø 6, von der Nachbarin weg: 6,5 mm daneben bleiben 0,5 mm Wand,
    5 mm daneben überschneiden sich beide; 8 mm daneben ist alles gut. Bei der
    gesenkten Bohrung trifft die Senkung Ø 10 früher.
    """
    from tests.test_bore_depth import _evaluated

    source = _with_neighbour(kernel, RIBBED[case])
    hole = min(
        (feature for feature in source.features.values() if feature.kind == "hole"),
        key=lambda feature: abs(float(feature.params["centre"][0])),
    )
    x, y, z = (float(value) for value in hole.params["centre"])
    wide = 10.0 if case == "gesenkt" else 6.0
    for step, expected in (
        (wide + 0.5, "bore.neighbour_wall_thin"),
        (wide - 1.0, "bore.neighbour_opened"),
    ):
        _copied, findings = _evaluated(
            source, profile, "duplicate_feature", at_feature=hole.id, x=x - step, y=y, z=z
        )
        assert expected in _warnings(findings), (step, _warnings(findings))
    _copied, findings = _evaluated(
        source, profile, "duplicate_feature", at_feature=hole.id, x=x - wide - 2.0, y=y, z=z
    )
    assert not [code for code in _warnings(findings) if code.startswith("bore.neighbour_")]
