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

import math
from collections.abc import Sequence
from itertools import pairwise
from pathlib import Path
from typing import Any, Final

import numpy as np
import pytest

from app.core.bootstrap import load_operations
from app.core.errors import CHANGE_SELECTION, ValidationError
from app.core.geom import prepare_ops
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.ingest.plan import import_plan
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import ProjectSources, checksum, new_project
from app.core.types import Feature, Finding, Profile, Quality, SceneObject, Source, kind_of
from tests.helpers import (
    BOTH_ENDS,
    cavity_under,
    contains,
    narrowest_hole,
    sloped_slot_plate,
    widened_bore,
)

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
    "spitze Senkung": [(0, 8), (4, 12), (0, 12), (0, 8)],
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


def _sides_lost(before: SceneObject, after: SceneObject) -> float:
    """Wie viel Fläche die vier Seiten der Platte 30 × 24 verloren haben, in mm².

    Gezählt werden die Dreiecke in den Ebenen x = ±15 und y = ±12 mit ihrer
    Normale nach außen — ein Schnitt, der aus einer Seite läuft, nimmt ihr
    Fläche; einer, der sie nicht berührt, lässt sie, wie sie war.
    """

    def sides(entry: SceneObject) -> float:
        raw = as_mesh_data(entry.mesh).raw
        corners = np.asarray(raw.triangles, dtype=np.float64)
        normals = np.asarray(raw.face_normals, dtype=np.float64)
        areas = np.asarray(raw.area_faces, dtype=np.float64)
        total = 0.0
        for index, value in ((0, 15.0), (0, -15.0), (1, 12.0), (1, -12.0)):
            on = (np.abs(corners[:, :, index] - value).max(axis=1) < 1e-6) & (
                normals[:, index] * np.sign(value) > 0.99
            )
            total += float(areas[on].sum())
        return total

    return sides(before) - sides(after)


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
    Volumen stieg um 11 mm³) und schnitt am exakten Körper 80 mm³ aus der Rippe;
    eine spitze hat nur einen Randring, blieb deshalb ungekappt und schnitt an
    beiden Kernen 82 mm³ aus ihr.

    **„Über die Kante" heißt dabei, dass eine Seitenfläche aufgeht** — nicht
    „nie" (Durchsicht seit 0.5.0, 25.09.2026). Um die Bohrungsmitte gekippt,
    läuft die flache Flanke einer 90°-Senkung Ø 10 aus der 24 mm breiten
    Platte: 22,6 mm² der Seite y = -12 fehlten danach an der gesenkten
    Bohrung, 19 mm² am gesenkten Sackloch und an der vergrabenen Senkung, an
    beiden Kernen — und beide schwiegen, denn der Kranz war der Kreis des
    weiten Endes statt des Kegelschnitts. Und gleich viel abgetragen heißt
    gleiches Volumen danach: Der Vergleich des Abtrags allein zählt an einer
    Senkung ohne Bohrung einen Splitter zweimal, wo die Facetten des alten und
    des gekippten Kegels sich kreuzen.
    """
    from app.core.geom.prepare import FEATURE_OVERLAP
    from tests.helpers import evaluated_operation

    top = 10.0 if case == "vergrabene Senkung" else 12.0
    seen = {}
    for kernel in ("mesh", "brep"):
        source = _bored(kernel, RIBBED[case], ribbed=True)
        hole = narrowest_hole(source)
        changed, findings = evaluated_operation(
            source, profile, "rotate_feature", at_feature=hole.id, axis="x", angle=30.0
        )
        lost = _removed(source, changed)
        assert _beyond(lost, top + FEATURE_OVERLAP, above=True) == pytest.approx(0.0, abs=0.01), (
            kernel
        )
        assert _beyond(lost, -FEATURE_OVERLAP, above=False) == pytest.approx(0.0, abs=0.01), kernel
        codes = _warnings(findings)
        opened = _sides_lost(source, changed) > 1.0
        assert ("bore.over_the_edge" in codes) is opened, (kernel, codes, opened)
        cones = [feature for feature in changed.features.values() if feature.kind == "cone"]
        seen[kernel] = (
            float(source.mesh.volume) - float(changed.mesh.volume),
            codes,
            bool(changed.features[hole.id].params.get("through")),
            [float(cone.params["diameter"]) for cone in cones],
        )
    mesh, brep = seen["mesh"], seen["brep"]
    assert mesh[0] == pytest.approx(brep[0], rel=0.01), "beide Kerne tragen dasselbe ab"
    assert mesh[1] == brep[1], "beide Kerne sagen dasselbe"
    assert mesh[2] == brep[2], "beide Kerne halten dieselbe Bohrung für durchgehend"
    assert mesh[3] == pytest.approx(brep[3], abs=0.1), "die Senkung ist am Ergebnis gemessen"


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
def test_a_tilted_through_slot_takes_only_its_own_slant(profile: Profile, kernel: str) -> None:
    """Ein durchgehendes Langloch, gekippt, geht durch und trägt vor seinen
    Mündungen nichts ab — an beiden Kernen (Durchsicht 0.5.1, BOHRUNG-08).

    Am ``build_tray_v3.step`` schnitt der exakte Kern ein um 10° gekipptes
    Langloch über die ganze Hülle: 8 012 mm³ fehlten vor der Mündung, quer
    durch die Schale. Das Netz verlängerte es gar nicht und ließ +104,9 mm³
    als Häute stehen, „geht nicht mehr durch". Hier: Platte 60 × 40 × 4, darüber
    auf zwei Stützen eine zweite Platte (z 10 … 14) auf der Linie des
    Schlitzes, Langloch Ø 6 × 20 entlang x, um 10° um x gekippt. Sollwert:
    Querschnitt mal Wand durch cos 10° minus vorher, A · t · (1/cos θ − 1) mit
    A = π · 3² + 6 · 14, und über der unteren Platte fehlt nichts.
    """
    from app.core.brep import edit
    from app.core.geom.prepare import FEATURE_OVERLAP
    from tests.helpers import evaluated_operation

    plate = edit.unified(
        edit.boolean(
            "union",
            [
                edit.box(60.0, 40.0, 4.0),
                edit.moved(edit.box(6.0, 40.0, 6.0), (-27.0, 0.0, 4.0)),
                edit.moved(edit.box(6.0, 40.0, 6.0), (27.0, 0.0, 4.0)),
                edit.moved(edit.box(60.0, 40.0, 4.0), (0.0, 0.0, 10.0)),
            ],
        )
    )
    solid = edit.slot_bore(
        plate,
        position=(0.0, 0.0, 2.0),
        direction=(0.0, 0.0, 1.0),
        diameter=6.0,
        depth=6.0,
        length=20.0,
        angle_deg=0.0,
        overlap=0.0,
    )
    source = _body(kernel, solid)
    slot = next(feature for feature in source.features.values() if feature.kind == "slot")
    changed, findings = evaluated_operation(
        source, profile, "rotate_feature", at_feature=slot.id, axis="x", angle=10.0
    )
    lost = _removed(source, changed)
    assert _beyond(lost, 4.0 + FEATURE_OVERLAP, above=True) == pytest.approx(0.0, abs=0.01)
    assert _beyond(lost, -FEATURE_OVERLAP, above=False) == pytest.approx(0.0, abs=0.01)
    assert "rotate_feature.no_longer_through" not in _warnings(findings), findings
    section = math.pi * 9.0 + 6.0 * 14.0
    slant = section * 4.0 * (1.0 / math.cos(math.radians(10.0)) - 1.0)
    change = float(source.mesh.volume) - float(changed.mesh.volume)
    assert change == pytest.approx(slant, rel=0.1), kernel


def test_a_tilted_bore_is_capped_where_the_flat_cut_fails(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Kommt der ebene Schnitt an den alten Randebenen ohne Deckel zurück, kappen Quader.

    An der Öffnung eines Mini-Topfs (Ø 28 in 0,3 mm Wand) scheiterte der
    Schnitt, und das ungekappte Werkzeug trug 59 mm³ vor den Mündungen ab
    (25.09.2026). Die Lage wird an ``_cut_at_the_rims`` gestellt.
    """
    from app.core.geom.prepare import FEATURE_OVERLAP
    from tests.helpers import evaluated_operation

    source = _bored("mesh", RIBBED["gesenkt"], ribbed=True)
    monkeypatch.setattr(prepare_ops, "_cut_at_the_rims", lambda *_args: None)
    changed, _findings = evaluated_operation(
        source,
        profile,
        "rotate_feature",
        at_feature=narrowest_hole(source).id,
        axis="x",
        angle=30.0,
    )
    lost = _removed(source, changed)
    assert _beyond(lost, 12.0 + FEATURE_OVERLAP, above=True) == pytest.approx(0.0, abs=0.01)
    assert _beyond(lost, -FEATURE_OVERLAP, above=False) == pytest.approx(0.0, abs=0.01)


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
    from tests.helpers import evaluated_operation

    seen = {}
    for kernel in ("mesh", "brep"):
        source = _with_neighbour(kernel, RIBBED[case])
        hole = min(
            (feature for feature in source.features.values() if feature.kind == "hole"),
            key=lambda feature: abs(float(feature.params["centre"][0])),
        )
        _changed, findings = evaluated_operation(
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
    from tests.helpers import evaluated_operation

    for rise in (1.0, -1.0):
        source = _bored(kernel, SUNK, ribbed=False)
        hole = narrowest_hole(source)
        cone = next(feature for feature in source.features.values() if feature.kind == "cone")
        x, y, z = (float(value) for value in hole.params["centre"])
        changed, findings = evaluated_operation(
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
    from tests.helpers import evaluated_operation

    source = _bored(kernel, RIBBED["gesenktes Sackloch"], ribbed=False)
    hole = narrowest_hole(source)
    x, y, z = (float(value) for value in hole.params["centre"])
    _deeper, findings = evaluated_operation(
        source, profile, op, at_feature=hole.id, x=x + 8.0, y=y, z=z - 1.0
    )
    assert f"{op}.mouth_covered" in _warnings(findings), _warnings(findings)
    _across, findings = evaluated_operation(
        source, profile, op, at_feature=hole.id, x=x + 8.0, y=y, z=z
    )
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
    from tests.helpers import evaluated_operation

    source = _bored(kernel, RIBBED["durchgehend"], ribbed=False)
    hole = narrowest_hole(source)
    x, y, z = (float(value) for value in hole.params["centre"])
    changed, findings = evaluated_operation(
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
    from tests.helpers import evaluated_operation

    source = _bored(kernel, RIBBED[case], ribbed=False)
    feature = narrowest_hole(source)
    with pytest.raises(ValidationError) as refused:
        evaluated_operation(
            source, profile, "rotate_feature", at_feature=feature.id, axis="x", angle=45.0
        )
    assert refused.value.constraint == "sink_runs_out"
    assert "45,0" in str(refused.value) or "45.0" in str(refused.value)
    changed, _findings = evaluated_operation(
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
    from tests.helpers import evaluated_operation

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
        _moved, findings = evaluated_operation(
            source, profile, "move_feature", at_feature=hole.id, x=x + step, y=y, z=z
        )
        codes = _warnings(findings)
        assert expected in codes, (step, codes)
        assert "bore.over_the_edge" not in codes, (step, codes)
    _moved, findings = evaluated_operation(
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
    from tests.helpers import evaluated_operation

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
        _copied, findings = evaluated_operation(
            source, profile, "duplicate_feature", at_feature=hole.id, x=x - step, y=y, z=z
        )
        assert expected in _warnings(findings), (step, _warnings(findings))
    _copied, findings = evaluated_operation(
        source, profile, "duplicate_feature", at_feature=hole.id, x=x - wide - 2.0, y=y, z=z
    )
    assert not [code for code in _warnings(findings) if code.startswith("bore.neighbour_")]


# --- Durchsicht seit 0.5.0 (25.09.2026) ------------------------------------------------


def _raw_as(op: str, entry: SceneObject, profile: Profile, *, quality: Quality, **params: object):
    """Wie :func:`_raw`, mit wählbarer Qualität — der Entwurf ist, womit gedreht wird."""
    from app.core.registry import REGISTRY
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene

    load_operations()
    spec = REGISTRY.get(op)
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(**params),
            profile=profile,
            quality=quality,
            seed=11,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


@pytest.mark.parametrize("angle", [40.0, -40.0])
def test_a_tilted_bore_that_opens_its_neighbour_is_no_edge_on_either_kernel(
    profile: Profile, angle: float
) -> None:
    """Reißt die gekippte Bohrung die Wand zur Nachbarin auf, sagen beide Kerne nur das.

    Um 40° gekippt öffnet die schlichte Durchgangsbohrung die Wand zur Bohrung
    10 mm daneben — zur Nachbarin hin mit der oberen, von ihr weg mit der
    unteren Mündung. Am Netz steht dann allein ``bore.neighbour_opened``:
    ``_without_opened_twice`` streicht „über die Kante" daneben, denn die
    Mündung der Nachbarin ist keine Kante. ``_exact_rotate_cavity`` nahm den
    Kantenbefund erst **nach** dieser Frage in die Liste, und der exakte Körper
    meldete beide (Durchsicht seit 0.5.0, 25.09.2026). Bei 30° bleibt die Wand
    stehen, dort fiel es nicht auf
    (``test_a_tilted_bore_reports_its_neighbour_on_both_kernels``).
    """
    from tests.helpers import evaluated_operation

    seen = {}
    for kernel in ("mesh", "brep"):
        source = _with_neighbour(kernel, RIBBED["durchgehend"])
        hole = min(
            (feature for feature in source.features.values() if feature.kind == "hole"),
            key=lambda feature: abs(float(feature.params["centre"][0])),
        )
        _changed, findings = evaluated_operation(
            source, profile, "rotate_feature", at_feature=hole.id, axis="y", angle=angle
        )
        codes = _warnings(findings)
        assert "bore.neighbour_opened" in codes, (kernel, codes)
        assert "bore.over_the_edge" not in codes, (kernel, codes)
        seen[kernel] = codes
    assert seen["mesh"] == seen["brep"]


def test_tilting_a_bore_writes_the_stage_its_closing_needed(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Stufe, die das Schließen an der alten Stelle brauchte, steht im Schritt (§17.2).

    *Merkmal drehen* rechnet zwei Boolesche Schritte: an der alten Stelle
    schließen, an der neuen setzen. Gemeldet wurde nur der zweite — fiel das
    Schließen auf die Störstufe zurück, stand im Schritt trotzdem ``direct``,
    und ihr Startwert fehlte. Versetzen und die Kette melden die tiefste der
    Stufen (``deepest``); hier wird es an ``_closed_at`` erzwungen.
    """
    import dataclasses

    from app.core.types import SolverInfo

    closed_at = prepare_ops._closed_at

    def jittered(*args: Any, **kwargs: Any) -> Any:
        outcome = closed_at(*args, **kwargs)
        return dataclasses.replace(
            outcome,
            solver=SolverInfo(
                strategy="jittered", attempted=("direct", "welded", "jittered"), seed=11
            ),
        )

    monkeypatch.setattr(prepare_ops, "_closed_at", jittered)
    source = _bored("mesh", RIBBED["durchgehend"], ribbed=False)
    result = _raw_as(
        "rotate_feature",
        source,
        profile,
        quality="fine",
        at_feature=narrowest_hole(source).id,
        axis="x",
        angle=20.0,
    )
    assert result.solver is not None
    assert result.solver.strategy == "jittered", result.solver
    assert result.solver.seed == 11


@pytest.mark.parametrize("quality", ["draft", "fine"])
def test_boxes_cap_a_tilted_bore_only_on_the_lossless_stages(
    profile: Profile, monkeypatch: pytest.MonkeyPatch, quality: Quality
) -> None:
    """Die Quaderkappe rechnet ohne Störung und ohne Raster — hält sie nicht, bleibt das
    Werkzeug ungekappt, wie ``_within_the_old_rims`` es sagt.

    Scheitert der ebene Schnitt an den alten Randebenen, kappen Quader
    (``_boxed_in``). Deren Schnittmenge lief bis zum 25.09.2026 in feiner
    Qualität über die ganze Kette, mit dem Startwert null statt dem des
    Schritts und ohne Abbruchmarke: Im Entwurf konnte das Werkzeug still auf
    Voxeln entstehen, und der Befund dazu ging mit dem verworfenen Ergebnis
    verloren; scheiterte die ganze Kette, brach der Schritt ab, statt beim
    ungekappten Werkzeug zu bleiben. Hier scheitert jede Stufe der Kappe.
    """
    from app.core.geom import boolean as chain

    monkeypatch.setattr(prepare_ops, "_cut_at_the_rims", lambda *_args: None)
    tried: list[str] = []
    run_stage = chain._run_stage

    def capping_fails(kind: Any, meshes: Any, stage: Any, seed: Any, cancelled: Any = None) -> Any:
        if kind == "intersection" and len(meshes) > 2:
            tried.append(stage)
            raise ValueError("Probe: die Kappe hält auf keiner Stufe")
        return run_stage(kind, meshes, stage, seed, cancelled)

    monkeypatch.setattr(chain, "_run_stage", capping_fails)
    source = _bored("mesh", RIBBED["gesenkt"], ribbed=True)
    result = _raw_as(
        "rotate_feature",
        source,
        profile,
        quality=quality,
        at_feature=narrowest_hole(source).id,
        axis="x",
        angle=30.0,
    )
    assert result.outputs[0].mesh.is_watertight
    assert tried, "die Kappe über Quader ist gefragt worden"
    assert set(tried) <= {"direct", "welded"}, tried


def test_a_tilted_countersink_keeps_its_flank_beyond_the_mouth(profile: Profile) -> None:
    """Das Werkzeug der gekippten Senkung ohne Bohrung ist ihr Kegel — auch im Überstand.

    ``_turned_open_cone`` führt den Kegel über das weite Ende hinaus weiter und
    gibt ihm dort die Zugabe aus §39 dazu. Am oberen Ende stand der Radius der
    Weiterführung **ohne** diese Zugabe: Die Flanke lief über die ganze Länge
    etwas steiler als die gemessene, um 30° gekippt eine 90°-Senkung Ø 8 mit
    0,014 mm Abstand zum Kegel am oberen Rand. Sollwert: jede Mantelecke liegt
    auf dem Kegel aus den Kennzahlen der Senkung, gekippt wie sie.
    """
    from app.core.geom import transform

    source = _bored("mesh", RIBBED["Senkung ohne Bohrung"], ribbed=False)
    sink = narrowest_hole(source)
    assert sink.kind == "cone"
    centre = tuple(float(value) for value in sink.params["centre"])
    matrix = np.asarray(transform.rotation("x", 30.0, centre), dtype=np.float64)
    tool = prepare_ops._turned_open_cone(as_mesh_data(source.mesh), sink, matrix, 30.0)
    assert tool is not None

    half = np.radians(float(sink.params["angle"]) / 2.0)
    radius = float(sink.params["diameter"]) / 2.0
    outward = np.asarray(sink.params["axis"], dtype=np.float64)
    outward /= np.linalg.norm(outward)
    apex = np.asarray(centre) - outward * (radius / np.tan(half))
    apex = matrix[:3, :3] @ apex + matrix[:3, 3]
    turned = matrix[:3, :3] @ outward
    relative = np.asarray(tool.raw.vertices, dtype=np.float64) - apex
    along = relative @ turned
    across = np.linalg.norm(relative - np.outer(along, turned), axis=1)
    mantle = across > 1e-6
    assert mantle.sum() >= 2 * prepare_ops.FEATURE_SECTIONS
    assert np.abs(across[mantle] - along[mantle] * np.tan(half)).max() < 1e-9


@pytest.mark.parametrize("case", ["Senkung ohne Bohrung", "spitze Senkung"])
@pytest.mark.parametrize("angle", [30.0, -35.0])
def test_a_countersink_tilted_near_a_side_says_what_the_side_shows(
    profile: Profile, case: str, angle: float
) -> None:
    """Eine Senkung Ø 8 einen Millimeter vor der Seitenfläche, gekippt: „über die
    Kante" genau dann, wenn eine Seite der Platte danach Fläche verloren hat —
    an beiden Kernen.

    Zur Kante hin gekippt, läuft die flache Flanke aus der Seite (30°: 10 mm²
    der Seite x = 15 fehlen); von ihr weg nicht. Beide Kerne schwiegen zur
    Kante hin, und das Netz meldete die Flanke von ihr weg: Der Kranz war der
    Kreis des weiten Endes statt des Schnitts des Kegels mit der Oberseite,
    und der Kreis über die ganze Länge blieb so weit wie die Mündung. Der
    exakte Körper fragte die Kante gar nicht (``_exact_rotate_cone``;
    Durchsicht seit 0.5.0, 25.09.2026).
    """
    from app.core.brep import edit
    from app.core.sketch.planes import frame_of
    from tests.helpers import evaluated_operation

    for kernel in ("mesh", "brep"):
        solid = edit.bore_profile(
            edit.box(30.0, 24.0, 12.0), list(RIBBED[case]), frame_of((0, 0, 1), (10.0, 0, 0))
        )
        source = _body(kernel, solid)
        sink = narrowest_hole(source)
        changed, findings = evaluated_operation(
            source, profile, "rotate_feature", at_feature=sink.id, axis="y", angle=angle
        )
        opened = _sides_lost(source, changed) > 1.0
        assert opened is (angle > 0.0), (kernel, _sides_lost(source, changed))
        codes = _warnings(findings)
        assert ("bore.over_the_edge" in codes) is opened, (kernel, codes)


def test_a_needle_in_the_tool_is_no_wall_of_the_through_column() -> None:
    """Ein Dreieck ohne Fläche im Werkzeug ist keine Wand, an der die Säule endet.

    Die Durchgangsprüfung nimmt als Säule höchstens den Innenkreis der
    Werkzeugwand (``_inscribed_radius``). Ein Dreieck ohne Fläche trägt die
    Normale null, stand damit „quer zur Achse" und im Abstand null: Die Säule
    schrumpfte auf nichts, und „geht nicht mehr durch" blieb aus. Werkzeuge
    aus den eigenen Dreiecken eines Körpers (``_past_the_mouths``) tragen
    solche Nadeln mit, wo der Import sie behielt, damit das Netz dicht bleibt.
    Sollwert: der Innenkreis des 48-Ecks, 3 · cos(π/48).
    """
    import math

    import trimesh

    from app.core.geom import lathe

    column = lathe.cylinder(radius=3.0, height=10.0, sections=48)
    count = len(column.vertices)
    needle = trimesh.Trimesh(
        np.vstack([column.vertices, [[3.0, 0.0, 0.0], [3.0, 0.0, 0.0], [3.0, 0.0, 1.0]]]),
        np.vstack([column.faces, [[count, count + 1, count + 2]]]),
        process=False,
    )
    inscribed = 3.0 * math.cos(math.pi / 48.0)
    for tool in (column, needle):
        radius = prepare_ops._inscribed_radius(MeshData.of(tool), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0))
        assert radius == pytest.approx(inscribed, abs=1e-9), len(tool.faces)


# --- Bohrungen mit Erweiterung an beiden Enden (RM-245) -----------------------------


#: Die gekrümmten Unterseiten der Platte, in denen die untere Mündung liegt
#: (RM-248): gewölbt wie ein Zylinder R 40 entlang X, als Rinne R 40 von 0,5 mm
#: Tiefe in die ebene Unterseite geschnitten (nach innen gewölbt, wie die
#: Hohlkehle des Gartenschlauchhalters), und eben für y < 0, tangential in den
#: Zylinder für y > 0 — die Mündung liegt über der Naht zweier Flächen.
CURVED_BOTTOMS: tuple[str, ...] = ("Zylinder R 40", "Rinne R 40", "Naht Ebene-Zylinder")


def _profile_volume(outline: Sequence[tuple[float, float]]) -> float:
    """Das Volumen des Hohlraums aus seinem Profil: je Abschnitt ein Kegelstumpf."""
    return sum(
        np.pi * (z1 - z0) * (r0 * r0 + r0 * r1 + r1 * r1) / 3.0
        for (r0, z0), (r1, z1) in pairwise(outline[1:-1])
    )


def _cavity_members(source: SceneObject) -> list[Feature]:
    return sorted(
        (feature for feature in source.features.values() if feature.kind in ("hole", "cone")),
        key=lambda feature: feature.id,
    )


def _chain_ids(source: SceneObject) -> set[str]:
    """Die Namen aller Abschnitte, die in einer Kette mit zwei Seiten stehen."""
    from app.core.perceive.relations import cavity_chain_state_at, cavity_sides

    mesh = as_mesh_data(source.mesh)
    found: set[str] = set()
    for feature in _cavity_members(source):
        chain = cavity_chain_state_at(feature, source.features, mesh).chain
        if chain is not None and len(cavity_sides(chain)) == 2:
            found.update(part.id for part in chain)
    return found


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
@pytest.mark.parametrize("case", list(BOTH_ENDS))
def test_a_bore_widened_at_both_ends_is_one_chain_with_two_sides(kernel: str, case: str) -> None:
    """Bis RM-245 musste die engste Bohrung ein Ende der Kette sein; eine, die
    sich an beiden Enden weitet, hieß „geht in einen anderen Hohlraum über".

    Jetzt steht sie vorn, dahinter je Seite ihre Erweiterungen nach außen, und
    ``cavity_sides`` gibt beide Seiten zurück — von jedem Abschnitt aus
    dieselbe Kette. Eine Kette mit einer Seite bleibt eine.
    """
    from app.core.perceive.relations import cavity_chain_state_at, cavity_sides

    source = widened_bore(kernel, BOTH_ENDS[case])
    mesh = as_mesh_data(source.mesh)
    bore = narrowest_hole(source)
    states = [
        cavity_chain_state_at(part, source.features, mesh) for part in _cavity_members(source)
    ]
    assert {tuple(part.id for part in state.chain or ()) for state in states} == {
        tuple(part.id for part in states[0].chain or ())
    }
    chain = cavity_chain_state_at(bore, source.features, mesh).chain
    assert chain is not None and len(chain) == 3 and chain[0].id == bore.id
    sides = cavity_sides(chain)
    assert len(sides) == 2
    below = [float(side[1].params["centre"][2]) < float(bore.params["centre"][2]) for side in sides]
    assert sorted(below) == [False, True], below

    one_sided = _bored(kernel, SUNK, ribbed=False)
    single = cavity_chain_state_at(
        narrowest_hole(one_sided), one_sided.features, as_mesh_data(one_sided.mesh)
    ).chain
    assert single is not None and cavity_sides(single) == (single,)


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
@pytest.mark.parametrize("case", list(BOTH_ENDS))
def test_a_bore_widened_at_both_ends_moves_tilts_and_copies_on_both_kernels(
    profile: Profile, kernel: str, case: str
) -> None:
    """Die Abnahme von RM-245 an der Platte: Versetzen, Kippen und Verdoppeln
    gehen an beiden Kernen mit denselben Befunden — keinen —, und die Kette
    steht danach wieder da.

    Sollwerte: Versetzen ändert das Volumen nicht, Verdoppeln nimmt den
    Hohlraum ein zweites Mal ab, Entfernen gibt ihn zurück — sein Volumen aus
    dem Profil, je Abschnitt ein Zylinder oder Kegelstumpf. Am exakten Kern
    kam die gekippte Zylindersenkung vorher als verloren zurück, und die Kopie
    einer Bohrung hieß „geht nicht mehr durch", weil die Erkennung der neuen
    Senkung den Namen der Kopie gegeben hatte.
    """
    from tests.helpers import evaluated_operation

    outline = BOTH_ENDS[case]
    source = widened_bore(kernel, outline)
    before = abs(float(as_mesh_data(source.mesh).volume))
    cavity = _profile_volume(outline)
    bore = narrowest_hole(source)
    x, y, z = (float(value) for value in bore.params["centre"])
    members = {feature.id for feature in _cavity_members(source)}

    moved, findings = evaluated_operation(
        source, profile, "move_feature", at_feature=bore.id, x=x + 5.0, y=y, z=z
    )
    assert _warnings(findings) == [], findings
    assert abs(float(as_mesh_data(moved.mesh).volume)) == pytest.approx(before, abs=0.05)
    assert _chain_ids(moved) == members

    turned, findings = evaluated_operation(
        source, profile, "rotate_feature", at_feature=bore.id, axis="x", angle=15.0
    )
    assert _warnings(findings) == [], findings
    assert _chain_ids(turned) == members

    copied, findings = evaluated_operation(
        source, profile, "duplicate_feature", at_feature=bore.id, x=x + 16.0, y=y, z=z
    )
    assert _warnings(findings) == [], findings
    taken = before - abs(float(as_mesh_data(copied.mesh).volume))
    assert taken == pytest.approx(cavity, rel=0.01), (taken, cavity)
    assert len(_chain_ids(copied)) == 6

    closed, findings = evaluated_operation(
        source, profile, "remove_feature", at_feature=bore.id, sections="chain"
    )
    assert _warnings(findings) == [], findings
    given = abs(float(as_mesh_data(closed.mesh).volume)) - before
    assert given == pytest.approx(cavity, rel=0.01), (given, cavity)


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
@pytest.mark.parametrize("case", list(BOTH_ENDS))
def test_each_section_of_a_bore_widened_at_both_ends_is_removed_alone(
    profile: Profile, kernel: str, case: str
) -> None:
    """Nur einen Abschnitt entfernen: Die Seite, auf der er lag, geht bis zu
    ihrer Mündung weiter durch, die andere bleibt, wie sie war. Ohne die
    Bohrung geht keiner der übrigen mehr durch — das ist der Sinn des
    Schritts und kein Befund; am exakten Kern stand dort „geht nicht mehr
    durch" (RM-245).
    """
    from tests.helpers import evaluated_operation

    source = widened_bore(kernel, BOTH_ENDS[case])
    bore = narrowest_hole(source)
    for section in _cavity_members(source):
        changed, findings = evaluated_operation(
            source, profile, "remove_feature", at_feature=section.id, sections="single"
        )
        assert _warnings(findings) == [], (section.id, findings)
        rest = {feature.id for feature in _cavity_members(changed)}
        assert section.id not in rest, section.id
        if section.id != bore.id:
            assert bore.id in rest, section.id
            assert changed.features[bore.id].params.get("through"), section.id


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
@pytest.mark.parametrize("bottom", CURVED_BOTTOMS)
def test_a_widened_bore_whose_mouth_lies_in_a_curved_face_is_moved_on_both_kernels(
    profile: Profile, kernel: str, bottom: str
) -> None:
    """Die untere Zylindersenkung mündet in eine gekrümmte Fläche.

    Am exakten Kern sagte jede Kettenhandlung dort ab — mit dem Satz des
    Einlaufs, der zu „Nur Bohrungsdurchmesser" riet, einem Feld, das
    Versetzen nicht hat (RM-245). Danach füllten beide Kerne die alte Stelle
    mit einem Fächer vom Mittelpunkt des Rands, und der lag auf der mittleren
    Höhe des Rands statt auf der Fläche (RM-248): am Zylinder R 40 eine Mulde
    von 4,9 mm³ am Netz und 4,0 mm³ am exakten Körper, an der Naht 3,5 und 2,0,
    in der Rinne eine Beule.

    Jetzt ist der Deckel die Fläche um den Rand, fortgesetzt — exakt auf dem
    Träger der Nachbarfläche oder als Füllung über der gemessenen Fläche, am
    Netz als Gitter auf ihr —, und das Werkzeug an der neuen Stelle reicht aus
    den Flächen bis hinter die Fläche. Versetzt wird entlang X, wo die Fläche
    sich nicht ändert: Das Volumen bleibt, gemessen am eigenen Kern (am
    exakten das Integral), auf einen halben Kubikmillimeter von 651.
    """
    from tests.helpers import evaluated_operation

    source = widened_bore(kernel, BOTH_ENDS["Zylindersenkung und Fase"], bottom=bottom)
    before = abs(float(source.mesh.volume))
    bore = narrowest_hole(source)
    x, y, z = (float(value) for value in bore.params["centre"])
    members = {feature.id for feature in _cavity_members(source)}
    moved, findings = evaluated_operation(
        source, profile, "move_feature", at_feature=bore.id, x=x + 5.0, y=y, z=z
    )
    assert _warnings(findings) == [], findings
    change = abs(float(moved.mesh.volume)) - before
    assert abs(change) < 0.5, change
    assert _chain_ids(moved) == members


def _rounded_mouth(*, at: float = -8.0, rounding: float = 1.0) -> Any:
    """Die Platte 44 × 24 × 12 mit Zylindersenkung und Fase (``BOTH_ENDS``) bei
    x = ``at`` — die Mündungskante der Zylindersenkung in der ebenen Unterseite
    um ``rounding`` gerundet, wie an der Lochplatte gs-100 (dort in einer
    gekrümmten Fläche, RM-259)."""
    from OCP.BRepAdaptor import BRepAdaptor_Curve

    from app.core.brep import edit
    from app.core.sketch.planes import frame_of

    solid = edit.bore_profile(
        edit.box(44.0, 24.0, 12.0),
        list(BOTH_ENDS["Zylindersenkung und Fase"]),
        frame_of((0, 0, 1), (at, 0, 0)),
    )
    picked = []
    for index, edge in enumerate(solid.edges()):
        curve = BRepAdaptor_Curve(edge)
        middle = curve.Value((curve.FirstParameter() + curve.LastParameter()) / 2.0)
        if abs(math.hypot(middle.X() - at, middle.Y()) - 5.0) < 0.05 and middle.Z() < 2.0:
            picked.append(index)
    assert len(picked) >= 1
    return edit.fillet(solid, rounding, selected_edges=picked)


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
def test_a_rounded_mouth_travels_with_its_counterbore(profile: Profile, kernel: str) -> None:
    """Die gerundete Mündungskante einer Zylindersenkung gehört zu ihr (RM-259).

    Die Rundung R 1 zwischen Senkung und ebener Unterseite ist kein eigenes
    Merkmal der Kette. Am Netz ergänzte ``relations._blended_cavity_faces`` sie
    schon — und verwarf sie wieder, weil der Hohlraum mit der offenen Schulter
    vier Randringe hat statt zwei; am exakten Kern kamen Stopfen und Werkzeug
    aus den Profilen der Kette, die die Rundung nicht kennen. An beiden Kernen
    blieb beim Versetzen an der alten Stelle eine Mulde von 1 mm stehen, und an
    der neuen deckte eine Haut die Senkung zu („geht nicht mehr durch“);
    Entfernen gab 570,5 statt 655,9 mm³ zurück.

    Jetzt reist die Rundung mit: an der alten Stelle ist die Unterseite wieder
    eben, an der neuen ist die Senkung offen und ihre Kante gerundet.
    """
    from app.core.brep import edit
    from tests.helpers import evaluated_operation

    source = _body(kernel, _rounded_mouth())
    before = abs(float(source.mesh.volume))
    bore = narrowest_hole(source)
    x, y, z = (float(value) for value in bore.params["centre"])
    members = {feature.id for feature in _cavity_members(source)}

    moved, findings = evaluated_operation(
        source, profile, "move_feature", at_feature=bore.id, x=x + 5.0, y=y, z=z
    )
    assert _warnings(findings) == [], findings
    assert abs(float(moved.mesh.volume)) == pytest.approx(before, abs=0.05)
    assert _chain_ids(moved) == members
    twin = as_mesh_data(moved.mesh)
    # Alte Stelle, abseits der neuen: in der Senkung und im Band der Rundung
    # wieder Material.
    assert contains(twin, [(-11.0, 0.0, 0.5), (-11.0, 0.0, 3.0), (-13.5, 0.0, 0.05)]).all()
    # Neue Stelle: offen bis in die Unterseite, und 5,5 mm neben der Achse
    # liegt dicht über der Unterseite die Luft der mitgereisten Rundung.
    assert not contains(twin, [(-3.0, 0.0, 0.1), (-3.0, 0.0, 3.0), (2.5, 0.0, 0.05)]).any()

    closed, findings = evaluated_operation(
        source, profile, "remove_feature", at_feature=bore.id, sections="chain"
    )
    assert _warnings(findings) == [], findings
    plate = abs(float(as_mesh_data(edit.box(44.0, 24.0, 12.0)).volume))
    assert abs(float(closed.mesh.volume)) == pytest.approx(plate, abs=0.05)

    # Die Kopie trägt dieselbe Rundung: Sie nimmt so viel ab, wie der Hohlraum
    # samt Rundung groß ist, und dicht über der Unterseite 5,5 mm neben ihrer
    # Achse ist Luft.
    copied, findings = evaluated_operation(
        source, profile, "duplicate_feature", at_feature=bore.id, x=x + 16.0, y=y, z=z
    )
    assert _warnings(findings) == [], findings
    taken = before - abs(float(copied.mesh.volume))
    assert taken == pytest.approx(plate - before, abs=0.05)
    assert not contains(as_mesh_data(copied.mesh), [(13.5, 0.0, 0.05)]).any()


@pytest.mark.parametrize("bottom", CURVED_BOTTOMS)
def test_a_bore_under_a_curved_face_is_closed_up_to_that_face(
    profile: Profile, bottom: str
) -> None:
    """Entfernt, gibt die Kette genau ihren Hohlraum bis an die Fläche zurück.

    Der Sollwert kommt nicht aus dem Programm: Profil der Kette minus das, was
    die Unterseite unter der Senkung höher liegt als z = 0, über die Scheibe
    integriert (:func:`_cavity_under`). Mit dem Fächer fehlten am Zylinder
    R 40 6,5 mm³, in der Rinne stand eine Beule über der Fläche (RM-248); am
    exakten Kern liegt der Deckel jetzt auf dem Träger oder folgt ihm als
    Füllung.
    """
    from tests.helpers import evaluated_operation

    outline = BOTH_ENDS["Zylindersenkung und Fase"]
    source = widened_bore("brep", outline, bottom=bottom)
    bore = narrowest_hole(source)
    closed, findings = evaluated_operation(
        source, profile, "remove_feature", at_feature=bore.id, sections="chain"
    )
    assert _warnings(findings) == [], findings
    given = float(closed.mesh.volume) - float(source.mesh.volume)
    assert given == pytest.approx(cavity_under(bottom, outline), abs=0.05)


def test_the_exact_filling_asks_the_faces_around_the_rim_and_not_only_its_own() -> None:
    """Die Füllung am exakten Kern stützt sich auf dieselbe Nachbarschaft wie das Netz.

    ``edit._filled_cap`` vernetzte zuerst nur die Flächen, an denen der Rand
    liegt. An der Lochplatte ``pegboard-gs-100-v2.step`` sind das vier
    Spline-Flächen einer Mündungsrundung, ein Band von 1,7 mm, und das Polynom
    über dieses Band allein lief über das Loch fortgesetzt als Trichter hinein:
    Beim Versetzen um 1 mm fehlten 7,8 statt 4,1 mm³ (Durchsicht 0.5.1) — am
    Netz derselben Platte fand die Anpassung keine Fläche, und es blieb beim
    Fächer. ``_faces_near`` nimmt jede Fläche in dem Ring, den die Anpassung
    abtastet: in der Rinne R 40 auch die ebene Unterseite hinter der Kante der
    Rinne, die den Rand nicht berührt, und keine Fläche des Hohlraums.
    """
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepTools import BRepTools
    from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane
    from OCP.TopAbs import TopAbs_WIRE
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    from app.core.brep import edit
    from app.core.perceive.relations import cavity_chain_state_at, cavity_surface_indices

    source = widened_bore("brep", BOTH_ENDS["Zylindersenkung und Fase"], bottom="Rinne R 40")
    solid = source.mesh
    mesh = as_mesh_data(solid)
    bore = narrowest_hole(source)
    chain = cavity_chain_state_at(bore, source.features, mesh).chain
    assert chain is not None
    chosen = set(solid.faces_of_triangles(cavity_surface_indices(mesh, chain)))
    faces = solid.faces()

    def surface(face: Any) -> Any:
        return BRepAdaptor_Surface(face)

    groove = next(
        index
        for index, face in enumerate(faces)
        if surface(face).GetType() == GeomAbs_Cylinder
        and surface(face).Cylinder().Radius() == pytest.approx(40.0)
    )
    outer = BRepTools.OuterWire_s(faces[groove])
    walk = TopExp_Explorer(faces[groove], TopAbs_WIRE)
    rims = []
    while walk.More():
        if not walk.Current().IsSame(outer):
            rims.append(TopoDS.Wire(walk.Current()))
        walk.Next()
    assert len(rims) == 1
    near = edit._faces_near(rims[0], faces, chosen)
    picked = {index for index, face in enumerate(faces) if any(face.IsSame(n) for n in near)}
    assert groove in picked
    assert not picked & chosen
    flat_bottom = {
        index
        for index in picked
        if surface(faces[index]).GetType() == GeomAbs_Plane
        and abs(surface(faces[index]).Plane().Axis().Direction().Z()) > 0.999
        and surface(faces[index]).Plane().Location().Z() == pytest.approx(0.0, abs=1e-6)
    }
    assert flat_bottom, "die ebene Unterseite hinter der Rinne gehört zur Nachbarschaft"


# --- Eine Seite, die schmaler ist als die Hülle (RM-249) ------------------------------


def _narrow_plate(kernel: str, *, thickness: float = 6.0) -> SceneObject:
    """Grundplatte 40 x 16 (y ±8) mit einer Bohrung Ø 6 bei x = 8, dazu eine
    Säule 10 x 24 x 30 am linken Ende (y ±12): Die Hülle reicht in y bis ±12,
    die Platte nur bis ±8 — wie an der Lochplatte ``pegboard-gs-100-v2``, die
    auf Höhe der oberen Schraubbohrung schmaler ist als ihre Hülle.
    """
    from app.core.brep import edit
    from app.core.sketch.planes import frame_of

    plate = edit.box(40.0, 16.0, thickness)
    column = edit.moved(edit.box(10.0, 24.0, 30.0), (-15.0, 0.0, 0.0))
    body = edit.unified(edit.boolean("union", [plate, column]))
    outline = [(0, 0), (3, 0), (3, thickness), (0, thickness), (0, 0)]
    solid = edit.bore_profile(body, outline, frame_of((0, 0, 1), (8.0, 0.0, 0.0)))
    return _body(kernel, solid)


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
def test_a_copy_over_a_side_inside_the_hull_says_so_on_both_kernels(
    profile: Profile, kernel: str
) -> None:
    """Die Kantenprüfung fragte zuerst den Hüllquader und schwieg, solange die
    Scheibe darin blieb — auch über einer Seite, die schmaler ist als die
    Hülle (RM-249). An der Lochplatte gs-100 lief eine Kopie 3,4 mm über die
    Seite, und keiner der beiden Kerne sagte etwas; der exakte meldete die
    Kopie als verloren, das Netz trug sie ungeprüft weiter.

    Jetzt sagen beide „über die Kante" und beide „nicht wiederzufinden", beim
    Versetzen „über die Kante". Eine Kopie, die ganz im Material steht, sagt
    nichts.
    """
    from tests.helpers import evaluated_operation

    source = _narrow_plate(kernel)
    bore = narrowest_hole(source)
    x, y, z = (float(value) for value in bore.params["centre"])
    _copied, findings = evaluated_operation(
        source, profile, "duplicate_feature", at_feature=bore.id, x=x, y=y + 9.5, z=z
    )
    assert _warnings(findings) == ["bore.over_the_edge", "duplicate_feature.feature_lost"]
    # Die Kopie, die es nicht gibt, sagt nicht „Die Geometrie stimmt", sondern
    # zeigt ihre Stelle (Durchsicht 0.5.1, BOHRUNG-04).
    from app.core.errors import SHOW_LOCATION

    lost = next(f for f in findings if f.code == "duplicate_feature.feature_lost")
    assert "Geometrie stimmt" not in str(lost.message)
    assert lost.location == pytest.approx((x, y + 9.5, z), abs=1e-6)
    assert SHOW_LOCATION in lost.suggestions
    _moved, findings = evaluated_operation(
        source, profile, "move_feature", at_feature=bore.id, x=x, y=y + 6.0, z=z
    )
    assert _warnings(findings) == ["bore.over_the_edge"]
    copied, findings = evaluated_operation(
        source, profile, "duplicate_feature", at_feature=bore.id, x=x + 8.0, y=y, z=z
    )
    assert _warnings(findings) == []
    assert len([feature for feature in copied.features.values() if feature.kind == "hole"]) == 2


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
def test_drilling_over_a_side_inside_the_hull_says_so(profile: Profile, kernel: str) -> None:
    """Bohren fragt die Kante mit seiner Tiefe genauso (RM-249).

    Über der schmalen Seite heißt es „über die Kante"; eine Bohrung, die in
    die vorhandene schneidet, ist keine Kante — dort ist die Flanke in den
    Nachbarn offen, und ein Strahl vom Kranz nach außen trifft dessen Wand.
    Und eine Bohrung ganz im Material sagt nichts.
    """
    from tests.helpers import evaluated_operation

    source = _narrow_plate(kernel)
    for x, y, expected in (
        (-2.0, 6.0, ["bore.over_the_edge"]),
        (-2.0, 3.0, []),
        (8.0, 3.0, []),
    ):
        _drilled, findings = evaluated_operation(
            source, profile, "drill_hole", x=x, y=y, z=6.0, diameter=6.0, depth=0.0, axis="z"
        )
        edge = [code for code in _warnings(findings) if code == "bore.over_the_edge"]
        assert edge == expected, (x, y, findings)


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
def test_a_bore_in_a_thin_plate_is_no_edge(profile: Profile, kernel: str) -> None:
    """Die Probe tastet über die eigene Länge der Bohrung, nicht in
    Sechzehnteln der Hüllendiagonale: Dort fände sich an einer dünnen Platte
    keine Tiefe mit dem Kranz ganz im Material, und jede Bohrung hieße „über
    die Kante". Eine Platte 1 mm stark, gebohrt, versetzt und verdoppelt mitten
    im Material — kein Kantenbefund.
    """
    from tests.helpers import evaluated_operation

    source = _narrow_plate(kernel, thickness=1.0)
    bore = narrowest_hole(source)
    x, y, z = (float(value) for value in bore.params["centre"])
    for op, params in (
        ("drill_hole", {"x": -2.0, "y": 0.0, "z": 1.0, "diameter": 6.0, "depth": 0.0, "axis": "z"}),
        ("move_feature", {"at_feature": bore.id, "x": x + 2.0, "y": y, "z": z}),
        ("duplicate_feature", {"at_feature": bore.id, "x": x + 8.0, "y": y, "z": z}),
    ):
        _changed, findings = evaluated_operation(source, profile, op, **params)
        assert "bore.over_the_edge" not in _warnings(findings), (op, findings)


def _stepped(kernel: str, *, bored: bool) -> SceneObject:
    """Grundplatte 40 x 40 x 5 (z 0 … 5), darauf ein Block 20 x 40 x 10 (x −20 … 0,
    z 5 … 15); ``bored`` bohrt bei x = −10 durch beide Ø 6."""
    from app.core.brep import edit
    from app.core.sketch.planes import frame_of

    solid = edit.unified(
        edit.boolean(
            "union",
            [edit.box(40.0, 40.0, 5.0), edit.moved(edit.box(20.0, 40.0, 10.0), (-10.0, 0.0, 5.0))],
        )
    )
    if bored:
        outline = [(0, 0), (3, 0), (3, 15), (0, 15), (0, 0)]
        solid = edit.bore_profile(solid, outline, frame_of((0, 0, 1), (-10.0, 0.0, 0.0)))
    return _body(kernel, solid)


def _step_side_lost(before: SceneObject, after: SceneObject) -> float:
    """Wie viel Fläche die Seite x = 0 des Blocks (z über 5) verloren hat, in mm²."""

    def side(entry: SceneObject) -> float:
        raw = as_mesh_data(entry.mesh).raw
        corners = np.asarray(raw.triangles, dtype=np.float64)
        normals = np.asarray(raw.face_normals, dtype=np.float64)
        on = (
            (np.abs(corners[:, :, 0]).max(axis=1) < 1e-6)
            & (normals[:, 0] > 0.99)
            & (corners[:, :, 2].min(axis=1) > 5.0 - 1e-6)
        )
        return float(np.asarray(raw.area_faces, dtype=np.float64)[on].sum())

    return side(before) - side(after)


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
def test_a_bore_that_runs_out_of_a_step_says_so_on_both_kernels(
    profile: Profile, kernel: str
) -> None:
    """„Über die Kante" gilt auch an einer abgesetzten Stelle, an der die Bohrung
    darunter ringsum Material hat (Durchsicht 0.5.1, BOHRUNG-01).

    Die Kantenprüfung nannte eine Flanke geschlossen, sobald der Kranz an einer
    einzigen Tiefe ganz im Material lag. Eine Bohrung Ø 6 bei x = −1 läuft im
    Block 2 mm aus dessen Seite x = 0 — die Seite verliert rund 57 mm² — und
    hat in der Grundplatte darunter ringsum Material: Bohren, Versetzen und
    Verdoppeln schwiegen an beiden Kernen. Sollwert ist die verlorene Fläche
    der Seite. Bei x = −3,5 bleibt die Seite ganz, und keiner sagt etwas (die
    Kopie lässt dort 0,5 mm zur Vorlage bei x = −10 stehen; bei −4 berührten
    sich beide Bohrungen in einer Linie, ein Körper ohne Wanddicke).
    """
    from tests.helpers import evaluated_operation

    plain = _stepped(kernel, bored=False)
    bored = _stepped(kernel, bored=True)
    bore = narrowest_hole(bored)
    _x, y, z = (float(value) for value in bore.params["centre"])
    for x in (-1.0, -3.5):
        cases = (
            (plain, "drill_hole", {"x": x, "y": 0.0, "z": 15.0, "diameter": 6.0, "depth": 0.0}),
            (bored, "move_feature", {"at_feature": bore.id, "x": x, "y": y, "z": z}),
            (bored, "duplicate_feature", {"at_feature": bore.id, "x": x, "y": y, "z": z}),
        )
        for source, op, params in cases:
            changed, findings = evaluated_operation(source, profile, op, **params)
            opened = _step_side_lost(source, changed) > 1.0
            assert opened is (x > -3.0), (kernel, op, x)
            assert ("bore.over_the_edge" in _warnings(findings)) is opened, (
                kernel,
                op,
                x,
                findings,
            )


# --- Eine still gescheiterte exakte Differenz --------------------------------------------


def _cut_with_twins(monkeypatch: pytest.MonkeyPatch, closed: list[bool]) -> list[float]:
    """Eine exakte Differenz, deren Zwilling der Reihe nach ``closed`` antwortet —
    zurück kommen die Überstände, mit denen geschnitten wurde."""
    from types import SimpleNamespace

    from app.core.brep import edit

    answers = iter(closed)
    monkeypatch.setattr(
        prepare_ops, "as_mesh_data", lambda _body: SimpleNamespace(is_watertight=next(answers))
    )
    plate = edit.box(20.0, 20.0, 5.0)
    overlaps: list[float] = []

    def tool_with(overlap: float) -> Any:
        overlaps.append(overlap)
        return edit.moved(edit.cylinder(4.0, 7.0), (0.0, 0.0, -1.0))

    prepare_ops._exact_chain_cut_holding(plate, tool_with)
    return overlaps


def test_a_cut_that_failed_silently_is_retried_with_more_overlap(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """OpenCASCADE sagt nicht immer, wenn es nicht schneiden konnte: An der
    Lochplatte gs-100 kam die untere Schraubbohrung, 1,5 mm nach oben
    versetzt, mit dem Volumen des gefüllten Körpers und einem undichten
    Zwilling zurück, und ``BRepCheck`` nannte alles gültig. Mit doppeltem
    Überstand über die offenen Mündungen hielt die Differenz. Ein Ergebnis
    gilt deshalb nur mit dichtem Zwilling, und sonst wird wiederholt; hält
    keiner der drei Überstände, sagt die Handlung ab.
    """
    from app.core.errors import GeometryError

    overlap = prepare_ops.FEATURE_OVERLAP
    assert _cut_with_twins(monkeypatch, [True]) == [overlap]
    assert _cut_with_twins(monkeypatch, [False, True]) == [overlap, 2.0 * overlap]
    with pytest.raises(GeometryError) as refused:
        _cut_with_twins(monkeypatch, [False, False, False])
    assert refused.value.detail == prepare_ops.CUT_DID_NOT_HOLD


@pytest.mark.parametrize("case", ["gesenkt", "durchgehend"])
def test_a_moved_bore_is_measured_where_it_stands(
    profile: Profile, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    """Nach dem Versetzen misst das Netz örtlich nach, nicht mit der ganzen
    Merkmalssuche (Durchsicht 0.5.1, BOHRUNG-07).

    Die volle Erkennung am Ergebnis kostete jedes Versetzen am
    Gartenschlauchhalter kalt 88 statt 12 s, auch in der Vorschau. Die
    gesenkte und die schlichte Bohrung, je 4 mm quer versetzt, müssen ohne sie
    auskommen und tragen danach die Maße der Konstruktion: Ø 6 durchgehend an
    der neuen Stelle.
    """
    from tests.helpers import evaluated_operation

    source = _bored("mesh", RIBBED[case], ribbed=False)
    hole = narrowest_hole(source)

    def refused(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("die volle Erkennung lief")

    monkeypatch.setattr(prepare_ops, "_detect_resized_bores", refused)
    x, y, z = (float(value) for value in hole.params["centre"])
    changed, findings = evaluated_operation(
        source, profile, "move_feature", at_feature=hole.id, x=x + 4.0, y=y, z=z
    )
    assert _warnings(findings) == []
    measured = changed.features[hole.id]
    assert float(measured.params["diameter"]) == pytest.approx(6.0, abs=0.01)
    assert measured.params["through"] is True
    assert float(measured.params["centre"][0]) == pytest.approx(x + 4.0, abs=1e-6)


@pytest.mark.parametrize("op", ["move_feature", "duplicate_feature"])
def test_a_single_exact_bore_cut_is_held_like_a_chain(
    profile: Profile, monkeypatch: pytest.MonkeyPatch, op: str
) -> None:
    """Auch eine einzelne Bohrung geht am exakten Körper über die Haltefrage
    (Durchsicht 0.5.1, BOHRUNG-06).

    Am Teppichclip (``carpet-corner-clip.step``) kam ein Langloch, 0,5 mm
    entlang seiner Richtung versetzt, als geschlossener Körper mit undichtem
    Zwilling und 6 mm³ zu viel zurück — kein Befund, denn nur Ketten wurden
    nachgeprüft. Hier wird gezählt, womit ``_exact_rigid_cut`` schneidet: drei
    Überstände für eine Durchgangsbohrung, und das Werkzeug reicht mit jedem
    Überstand weiter über die offenen Mündungen — um genau die Differenz, je
    Mündung, also die doppelte Differenz in der Länge.
    """
    from tests.helpers import evaluated_operation

    source = _bored("brep", RIBBED["durchgehend"], ribbed=False)
    hole = narrowest_hole(source)
    seen: list[tuple[float, float]] = []
    real = prepare_ops._exact_chain_cut_holding

    def counted(solid: Any, tool_with: Any, **kwargs: Any) -> Any:
        def measured(overlap: float) -> Any:
            tool = tool_with(overlap)
            seen.append((overlap, float(tool.bounds.maximum[2] - tool.bounds.minimum[2])))
            return tool

        for factor in kwargs.get("overlaps") or prepare_ops.CUT_OVERLAPS:
            measured(prepare_ops.FEATURE_OVERLAP * factor)
        return real(solid, tool_with, **kwargs)

    monkeypatch.setattr(prepare_ops, "_exact_chain_cut_holding", counted)
    x, y, z = (float(value) for value in hole.params["centre"])
    evaluated_operation(source, profile, op, at_feature=hole.id, x=x + 4.0, y=y, z=z)
    overlaps = [overlap for overlap, _length in seen]
    assert overlaps == pytest.approx(
        [prepare_ops.FEATURE_OVERLAP * factor for factor in prepare_ops.CUT_OVERLAPS]
    )
    lengths = [length for _overlap, length in seen]
    assert lengths[1] - lengths[0] == pytest.approx(2.0 * prepare_ops.FEATURE_OVERLAP, abs=1e-6)


#: Die Neigung der Unterseite in :func:`_sloped_slot_plate`, in Grad.
_SLOPE = 4.0


@pytest.mark.parametrize(
    ("kernel", "chamfer"),
    [("mesh", False), ("mesh", True), ("brep", False), ("brep", True)],
    ids=["Netz", "Netz gefast", "exakt", "exakt gefast"],
)
@pytest.mark.parametrize("way", ["entlang", "gegen", "quer", "Kopie"])
def test_a_slot_through_a_sloped_wall_moves_as_a_whole(
    profile: Profile, kernel: str, chamfer: bool, way: str
) -> None:
    """Ein Langloch durch eine Wand mit schräger Unterseite geht beim Versetzen
    und Verdoppeln ganz mit — mit seinen Fasen, bis zu beiden Mündungen, an
    beiden Kernen (Durchsicht 0.5.1, BOHRUNG-05).

    Am Wedge-Lock (STL) füllte der Stopfen das Langloch über die ganze Wand,
    das Werkzeug schnitt aber nur die gemessene Tiefe: 0,5 mm versetzt blieben
    +125 mm³ als Häute stehen, „geht nicht mehr durch". Am Teppichclip (STEP)
    blieben die Fasen an der alten Stelle zurück, und der Schnitt kam undicht.

    Gegen die Neigung versetzt, rückt die untere Mündung um 0,03 mm ins
    Material — Messrauschen unter der Facettengrenze, wie am exakten Kern
    (``_seated``); das Netz ließ dort eine Haut stehen und sagte „geht nicht
    mehr durch".

    Am exakten Körper auch mit Fase: OpenCASCADE fast die Bögen auf der
    schrägen Unterseite als BSpline-Flächen, und die Erkennung zählte sie
    nicht zum Langloch — der Rand der Auswahl lag dann mitten in der Fase und
    in keiner Ebene, und am Teppichclip blieb die Fase beim Versetzen stehen.
    Seit sie das Netz fragt, ob es ein Kegelstück ist, geht sie mit
    (``brep.features._mouth_chamfers_folded``).

    Sollwerte: Quer versetzt ist die Wand an der neuen Stelle so dick wie an der
    alten, das Volumen bleibt. Entlang der Neigung um 0,5 mm ist sie um
    0,5 · tan 4° dünner, und das Volumen wächst um die Fläche der unteren
    Mündung mal diese Differenz — mit der Fase ist das der Umriss um 0,75 mm
    weiter, denn sie geht starr mit und liegt danach ein Stück vor der
    Fläche. Die Kopie 12 mm daneben trägt so viel ab, wie der Hohlraum misst.
    """
    from tests.helpers import evaluated_operation

    solid = sloped_slot_plate(chamfer=chamfer)
    source = _body(kernel, solid)
    slot = next(feature for feature in source.features.values() if feature.kind == "slot")
    x, y, z = (float(value) for value in slot.params["centre"])
    if way == "entlang":
        op, target = "move_feature", (x, y + 0.5, z)
    elif way == "gegen":
        op, target = "move_feature", (x, y - 0.5, z)
    elif way == "quer":
        op, target = "move_feature", (x + 0.5, y, z)
    else:
        op, target = "duplicate_feature", (x + 12.0, y, z)
    changed, findings = evaluated_operation(
        source, profile, op, at_feature=slot.id, x=target[0], y=target[1], z=target[2]
    )
    assert _warnings(findings) == [], findings
    assert as_mesh_data(changed.mesh).is_watertight
    change = float(changed.mesh.volume) - float(source.mesh.volume)
    if way in ("entlang", "gegen"):
        # Die Unterseite steigt an der neuen Stelle um 0,5 · tan 4° oder fällt
        # darum; die Mündung liegt starr mitbewegt um so viel davor oder, ins
        # Material gerückt, bündig — samt dem Ring ihrer Fase.
        rim = 0.75 if chamfer else 0.0
        mouth = math.pi * (3.0 + rim) ** 2 + (6.0 + 2.0 * rim) * 14.0
        expected = mouth * 0.5 * math.tan(math.radians(_SLOPE))
        if way == "gegen":
            expected = -expected
    elif way == "quer":
        expected = 0.0
    else:
        cavity = float(_body(kernel, sloped_slot_plate(chamfer=False, slotted=False)).mesh.volume)
        expected = -(cavity - float(source.mesh.volume))
    assert change == pytest.approx(expected, abs=0.15), (kernel, change, expected)
    slots = [feature for feature in changed.features.values() if feature.kind == "slot"]
    assert len(slots) == (2 if op == "duplicate_feature" else 1), slots
    assert all(feature.params.get("through") for feature in slots), slots


@pytest.mark.parametrize("case", ["durchgehend", "Sackloch"])
def test_a_widened_through_bore_is_measured_where_it_stands(
    profile: Profile, monkeypatch: pytest.MonkeyPatch, case: str
) -> None:
    """Nach dem Aufweiten misst das Netz eine Durchgangsbohrung örtlich nach,
    nicht mit der ganzen Merkmalssuche (Durchsicht 0.5.1, BOHRUNG-12).

    Am Gartenschlauchhalter kostete die volle Erkennung 74 der 76 s eines
    Aufweitens von Ø 6 auf 7. Die Durchgangsbohrung muss ohne sie auskommen
    und trägt danach Ø 8; ein Sackloch braucht seinen Boden und darf sie
    nehmen — dort muss der Boden danach unter seinem Namen stehen.
    """
    from tests.helpers import evaluated_operation

    outline = (
        RIBBED["durchgehend"]
        if case == "durchgehend"
        else [(0, 4), (3, 4), (3, 12), (0, 12), (0, 4)]
    )
    source = _bored("mesh", outline, ribbed=False)
    hole = narrowest_hole(source)
    ran: list[int] = []
    real = prepare_ops._detect_resized_bores

    def watched(*args: Any, **kwargs: Any) -> Any:
        ran.append(1)
        return real(*args, **kwargs)

    monkeypatch.setattr(prepare_ops, "_detect_resized_bores", watched)
    changed, findings = evaluated_operation(
        source, profile, "resize_hole", at_feature=hole.id, diameter=8.0, compensate=False
    )
    assert _warnings(findings) == []
    measured = changed.features[hole.id]
    assert float(measured.params["diameter"]) == pytest.approx(8.0, abs=0.01)
    assert bool(measured.params["through"]) is (case == "durchgehend")
    assert bool(ran) is (case != "durchgehend")


def _lid_with_a_magnet_pocket(box: str) -> tuple[Any, History, float]:
    """Deckel 80 × 60 × 5 mit einer Magnettasche 8x3 von oben bei (−30, −20) —
    der Aufbau aus ``magnet_lid`` der Agenten-Suite. Zurück: Projekt, Verlauf
    und Volumen des Deckels ohne Tasche."""
    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Deckel",
        [OperationDraft(op=box, params={"width": 80.0, "depth": 60.0, "height": 5.0})],
    )
    history.apply(
        "Magnet",
        [
            OperationDraft(
                op="insert_magnet_pocket",
                inputs=("obj_1",),
                params={"size": "8x3", "x": -30.0, "y": -20.0, "z": 5.0},
            )
        ],
    )
    return project, history, 80.0 * 60.0 * 5.0


@pytest.mark.parametrize("box", ["create_brep_box", "create_box"], ids=["exakt", "Netz"])
@pytest.mark.parametrize(
    "op", ["pattern_feature", "duplicate_feature", "move_feature", "remove_feature"]
)
def test_a_magnet_pocket_from_a_part_is_copied_moved_and_removed_with_its_lip(
    profile: Profile, box: str, op: str
) -> None:
    """Eine Magnettasche aus dem Baustein lässt sich vervielfachen, verdoppeln,
    versetzen und entfernen — mit ihrer Haltelippe, an beiden Kernen
    (Durchsicht 0.5.1, BOHRUNG-13, Befund des Prüfers ki).

    Das Merkmal des Bausteins trägt keine Dreiecke, und die Lippe verengt die
    Mündung von Ø 8,25 auf 7,95: Die Prüfung „steht Material in der Bohrung?"
    zählte die eigene Lippe als fremdes Material, und jede dieser Handlungen
    sagte „In dieser Bohrung steht Material; sie ist eine Wand, keine
    Bohrung." Im Assistenten wiederholte das Modell den Aufruf bis zur
    Schrittgrenze (``magnet_lid``). Sollwerte: Jede Kopie trägt so viel ab wie
    die Tasche selbst — samt Lippe —, das Versetzen lässt das Volumen, und
    entfernt steht der volle Deckel da.

    **Seit die Erkennung dem Merkmal des Bausteins Flächen zuordnet**
    (Nachtrag nach der Zusammenführung), ist die Tasche eine Kette aus Bohrung
    und Lippenkegel. Entfernt wird deshalb der ganze Hohlraum
    (``sections="chain"``, *Den ganzen Hohlraum entfernen*); „nur das gewählte
    Merkmal" ließe die Lippe als Ring stehen, und das ist dort die Absicht.
    """
    from app.core.geom.mesh import as_mesh_data as twin_of
    from app.core.scene.project import ProjectSources

    project, history, lid = _lid_with_a_magnet_pocket(box)
    sources = ProjectSources(project)
    before = evaluate(project.document, profile, sources=sources)
    assert before.complete
    body = before.scene.objects["obj_1"]
    pocket = next(name for name in body.features if "magnet" in name)
    volume = float(twin_of(body.mesh).volume)
    cavity = lid - volume
    params: dict[str, Any] = {"at_feature": pocket}
    if op == "pattern_feature":
        params = {
            "at_features": [pocket],
            "kind": "linear",
            "count": 2,
            "spacing": 60.0,
            "dx": 1.0,
            "dy": 0.0,
            "dz": 0.0,
        }
        expected = volume - cavity
    elif op == "duplicate_feature":
        params.update(x=30.0, y=-20.0, z=3.5)
        expected = volume - cavity
    elif op == "move_feature":
        params.update(x=-20.0, y=-20.0, z=3.5)
        expected = volume
    else:
        params["sections"] = "chain"
        expected = lid
    history.apply(op, [OperationDraft(op=op, inputs=("obj_1",), params=params)])
    after = evaluate(project.document, profile, sources=sources)
    assert after.complete, [str(finding.message) for finding in after.scene.report.findings]
    # Keine Warnung: weder „nicht als eigenes Merkmal zu erkennen" an einer
    # Kopie, die dasteht, noch ein Verlust dessen, was entfernt werden sollte.
    assert _warnings(after.scene.report.findings) == [], op
    changed = float(twin_of(after.scene.objects["obj_1"].mesh).volume)
    # Die Lippe selbst misst rund 0,8 mm³ (Kegelring Ø 8,25 → 7,95 über 0,4 mm):
    # Eine Kopie als glatter Zylinder läge darüber.
    assert changed == pytest.approx(expected, abs=0.25), (op, changed, expected)


#: Die Magnettasche 8x3 aus dem Baustein im Deckel von ``_lid_with_a_magnet_pocket``:
#: Tasche Ø 8,25 von z 2 bis 4,6, Lippe bis zur Mündung z 5 mit der Öffnung Ø 7,95.
_POCKET_FLOOR, _LIP_FOOT, _POCKET_MOUTH = 2.0, 4.6, 5.0
_POCKET_RADIUS, _OPENING_RADIUS = 4.125, 3.975


def _pocket_cavity(radius: float, *, keep: bool) -> float:
    """Der Hohlraum der Magnettasche nach *Bohrung ändern* auf ``radius``.

    Mitgenommen behält die Lippe Breite, Winkel und Höhe; mit *Nur
    Bohrungsdurchmesser* bleibt ihre Öffnung — an einer weiteren Tasche setzt
    sie am alten Fuß an, an einer engeren mit ihrem Winkel dort, wo sie so eng
    ist wie die Tasche (``prepare_ops._narrowing_radii``).
    """
    height = _POCKET_MOUTH - _LIP_FOOT
    opening = _OPENING_RADIUS if keep else radius - (_POCKET_RADIUS - _OPENING_RADIUS)
    foot = _LIP_FOOT
    if keep and radius < _POCKET_RADIUS:
        foot += (_POCKET_RADIUS - radius) * height / (_POCKET_RADIUS - _OPENING_RADIUS)
    lip = _POCKET_MOUTH - foot
    frustum = math.pi * lip / 3.0 * (radius**2 + radius * opening + opening**2)
    return math.pi * radius**2 * (foot - _POCKET_FLOOR) + frustum


@pytest.mark.parametrize("box", ["create_brep_box", "create_box"], ids=["exakt", "Netz"])
@pytest.mark.parametrize(
    ("diameter", "mode", "opening"),
    [(8.5, "follow", 8.2), (8.0, "follow", 7.7), (8.5, "keep", 7.95), (8.1, "keep", 7.95)],
)
def test_a_magnet_pocket_changes_its_diameter_and_keeps_its_lip(
    profile: Profile, box: str, diameter: float, mode: str, opening: float
) -> None:
    """*Bohrung ändern* an der Magnettasche aus dem Baustein behält ihre Lippe,
    an beiden Kernen mit denselben Sollmaßen (Durchsicht 0.5.1, rest-lippe).

    Mit Einlauf sagte die Operation an der Lippe ab, und das Merkmalfenster
    belegte deshalb *Nur Bohrungsdurchmesser* vor. Damit rechneten die Kerne
    verschieden: Ø 8,1 schnitt am Netz die Lippe auf 8,09 auf (der Magnet
    fiel heraus), der exakte Kern behielt sie; Ø 7,8 ließ am Netz eine
    Hinterschneidung unter der Lippe, der exakte Kern schnitt gerade durch;
    Ø 8,5 nahm an beiden die Lippe weg. Jetzt: mitgenommen wird die Lippe
    mit der Tasche weiter oder enger (Öffnung Ø 8,2 an Ø 8,5), mit *Nur
    Bohrungsdurchmesser* bleibt ihre Öffnung Ø 7,95 — die hält den Magneten.
    Sollwerte: Volumen aus den Maßen (am Netz das 48-Eck der Tasche) und die
    Öffnung der frisch erkannten Verengung.
    """
    from app.core.geom.mesh import as_mesh_data as twin_of
    from app.core.perceive.features import detect, forget_cache
    from app.core.scene.project import ProjectSources

    project, history, lid = _lid_with_a_magnet_pocket(box)
    sources = ProjectSources(project)
    before = evaluate(project.document, profile, sources=sources)
    assert before.complete
    history.apply(
        "Ändern",
        [
            OperationDraft(
                op="resize_hole",
                inputs=("obj_1",),
                params={
                    "at_feature": "magnet_pocket_pocket_1",
                    "diameter": diameter,
                    "entrance_mode": mode,
                },
            )
        ],
    )
    after = evaluate(project.document, profile, sources=sources)
    assert after.complete, [str(finding.message) for finding in after.scene.report.findings]
    assert _warnings(after.scene.report.findings) == []
    body = after.scene.objects["obj_1"]
    twin = twin_of(body.mesh)
    assert twin.is_watertight
    cavity = _pocket_cavity(diameter / 2.0, keep=mode == "keep")
    if box == "create_brep_box":
        assert body.mesh.volume == pytest.approx(lid - cavity, abs=1e-3)
    else:
        polygon = 48.0 / (2.0 * math.pi) * math.sin(2.0 * math.pi / 48.0)
        assert twin.volume == pytest.approx(lid - polygon * cavity, abs=1e-3)
    forget_cache()
    found = detect(twin)
    forget_cache()
    at_the_pocket = [
        feature
        for feature in found.values()
        if feature.kind in ("hole", "cone")
        and math.dist(feature.params["centre"][:2], (-30.0, -20.0)) < 0.1
    ]
    lips = [feature for feature in at_the_pocket if feature.kind == "cone"]
    bores = [feature for feature in at_the_pocket if feature.kind == "hole"]
    assert len(lips) == 1 and lips[0].params.get("narrowing") is True, at_the_pocket
    assert float(lips[0].params["opening"]) == pytest.approx(opening, abs=0.05)
    assert len(bores) == 1 and float(bores[0].params["diameter"]) == pytest.approx(
        diameter, abs=0.05
    )


def test_a_magnet_pocket_tilts_only_without_its_lip(
    profile: Profile,
) -> None:
    """*Merkmal drehen* an der Magnettasche aus dem Baustein: An Tasche und Lippe
    sagen Merkmalfenster und Operation denselben Satz, an beiden Kernen — und
    der Weg darin führt: Ohne Lippe kippt die Tasche, samt Boden
    (Durchsicht 0.5.1, rest-lippe).

    Vorher bot das Fenster die Zeile an, und die Operation sagte ab — am Netz
    mit dem Satz über eine Senkung, die in ihre Bohrung übergeht, am exakten
    Körper, der Hohlraum lasse sich nicht als Bohrung lesen. Probeweise
    gekippt las danach keine Erkennung die Lippe wieder als Verengung, und die
    nächste Handlung rechnete ohne sie (``NARROWING_STAYS_STRAIGHT``). *Zum
    Langloch ziehen* riet an der Tasche, „zuerst die Senkung“ zu entfernen.
    """
    from app.core.geom.mesh import as_mesh_data as twin_of
    from app.core.perceive.actions import (
        NARROWING_STAYS_ROUND,
        NARROWING_STAYS_STRAIGHT,
        actions_for,
    )
    from app.core.registry import REGISTRY
    from app.core.scene.project import ProjectSources

    pivot = np.asarray((-30.0, -20.0, 3.5))
    turn = np.asarray(
        [
            [1.0, 0.0, 0.0],
            [0.0, math.cos(math.radians(10.0)), -math.sin(math.radians(10.0))],
            [0.0, math.sin(math.radians(10.0)), math.cos(math.radians(10.0))],
        ]
    )

    def turned(points: list[tuple[float, float, float]]) -> Any:
        return (np.asarray(points, dtype=float) - pivot) @ turn.T + pivot

    def tilt(history: History) -> None:
        history.apply(
            "Drehen",
            [
                OperationDraft(
                    op="rotate_feature",
                    inputs=("obj_1",),
                    params={"at_feature": "magnet_pocket_pocket_1", "axis": "x", "angle": 10.0},
                )
            ],
        )

    title = str(REGISTRY.get("rotate_feature").title)
    slot_title = str(REGISTRY.get("slot_hole").title)
    for box in ("create_brep_box", "create_box"):
        project, history, _lid = _lid_with_a_magnet_pocket(box)
        sources = ProjectSources(project)
        before = evaluate(project.document, profile, sources=sources)
        assert before.complete
        body = before.scene.objects["obj_1"]
        lips = [
            feature
            for feature in body.features.values()
            if feature.kind == "cone" and feature.params.get("narrowing")
        ]
        assert len(lips) == 1, (box, sorted(body.features))
        for chosen in ("magnet_pocket_pocket_1", lips[0].id):
            rows = {
                str(action.title): action
                for action in actions_for(
                    body.features[chosen], body.features, mesh=twin_of(body.mesh)
                )
            }
            assert rows[title].op is None, (box, chosen)
            assert rows[title].reason is NARROWING_STAYS_STRAIGHT, (box, chosen)
            # Und *Zum Langloch ziehen* sagt an der Tasche, was an der Lippe gilt —
            # dort stand „Entfernen Sie zuerst die Senkung“.
            assert rows[slot_title].reason is NARROWING_STAYS_ROUND, (box, chosen)
        tilt(history)
        refused = evaluate(project.document, profile, sources=sources)
        assert not refused.complete, box
        told = [str(finding.message) for finding in refused.scene.report.findings]
        assert str(NARROWING_STAYS_STRAIGHT) in told, (box, told)

        project, history, _lid = _lid_with_a_magnet_pocket(box)
        sources = ProjectSources(project)
        history.apply(
            "Langloch",
            [
                OperationDraft(
                    op="slot_hole",
                    inputs=("obj_1",),
                    params={"at_feature": "magnet_pocket_pocket_1", "slot_length": 12.0},
                )
            ],
        )
        refused = evaluate(project.document, profile, sources=sources)
        assert not refused.complete, box
        told = [str(finding.message) for finding in refused.scene.report.findings]
        assert str(NARROWING_STAYS_ROUND) in told, (box, told)

        project, history, _lid = _lid_with_a_magnet_pocket(box)
        sources = ProjectSources(project)
        history.apply(
            "Lippe weg",
            [
                OperationDraft(
                    op="remove_feature",
                    inputs=("obj_1",),
                    params={"at_feature": lips[0].id, "sections": "single"},
                )
            ],
        )
        tilt(history)
        after = evaluate(project.document, profile, sources=sources)
        assert after.complete, [str(finding.message) for finding in after.scene.report.findings]
        assert _warnings(after.scene.report.findings) == [], box
        twin = twin_of(after.scene.objects["obj_1"].mesh)
        assert twin.is_watertight
        # Die gekippte Tasche ist leer, seitlich der Kippachse steht ihre Wand,
        # und ihr Boden steht quer zur gekippten Achse. **Und die Mündung ist
        # auch auf der Seite offen, zu der sie sinkt** (RM-263): 1,8 mm über
        # der Mitte und 3 mm zur tiefen Seite lag dort eine Haut, bis 0,72 mm
        # dick — an beiden Kernen, am Netz um die Zugabe aus §39 dünner.
        pocket = turned(
            [(-26.0, -20.0, 3.5), (-34.0, -20.0, 3.5), (-30.0, -20.0, 2.05), (-30.0, -23.0, 5.3)]
        )
        wall = turned([(-25.7, -20.0, 3.5), (-34.3, -20.0, 3.5), (-30.0, -20.0, 1.95)])
        assert not contains(twin, pocket).any(), box
        assert contains(twin, wall).all(), box
        # Der Hohlraum: jede Säule von ihrem gekippten Boden bis zur Deckfläche,
        # im Mittel 1,5/cos 10° + 1,5 mm lang. Die Kerne gleich bis auf das
        # 48-Eck der Netzwand; vorher exakt 152,724, am Netz umgerechnet 153,282.
        cavity = math.pi * 4.125 * 4.125 * (1.5 / math.cos(math.radians(10.0)) + 1.5)
        sides = 48.0 / math.tau * math.sin(math.tau / 48.0)
        removed = 80.0 * 60.0 * 5.0 - (
            float(after.scene.objects["obj_1"].mesh.volume)
            if box == "create_brep_box"
            else float(twin.volume)
        )
        if box == "create_brep_box":
            assert removed == pytest.approx(cavity, abs=0.01), box
        else:
            assert removed == pytest.approx(cavity * sides, abs=0.05), box


# --- RM-386: berührende Platten an jedem schließenden Weg ---------------------------
#
# Zwei Platten zu 40 x 20 x 10 mm berühren sich bei z = 10 mm, eine Bohrung Ø 6
# geht durch beide, wahlweise mit einer 90°-Senkung Ø 12 von oben. RM-319 heilte
# nur den Langlochzug; die Zwillinge rechneten still falsch: am Netz verlor die
# versetzte Senkbohrung 2 516,3 mm³, am exakten Kern ließ *Bohrung ändern* mit
# Versatz einen losen Zylinder von 502,7 mm³ stehen, und Versetzen und Kippen
# sagten mit dem Rat ab, die Stelle anders zu setzen.
#
# Die Kontrolle ist dieselbe Handlung an einer 20 mm starken Platte aus einem
# Stück; wo sich das Ergebnis rechnen lässt, steht der Sollwert daneben.

#: Grundfläche der Platten und ihre gemeinsame Stärke.
_PLATES = 40.0 * 20.0 * 20.0
#: Die Bohrung Ø 6 durch beide Platten.
_BORE = 9.0 * math.pi * 20.0
#: Was die Senkung Ø 12 / 90° über den Schaft hinaus wegnimmt: Kegelstumpf
#: π·h/3·(R² + Rr + r²) mit h = 3, R = 6, r = 3, abzüglich des Schafts darin.
_SINK = math.pi * (36.0 + 18.0 + 9.0) - 9.0 * math.pi * 3.0


def _touching_plates(kernel: str, *, sunk: bool, one_piece: bool = False) -> SceneObject:
    """Die zwei Berührplatten (oder die Kontrolle aus einem Stück), von oben gebohrt."""
    from app.core.perceive.features import detect

    if kernel == "brep":
        from tests.helpers import exact_kernel

        edit = exact_kernel()
        from OCP.BRep import BRep_Builder
        from OCP.TopoDS import TopoDS_Compound

        from app.core.brep.features import features_of
        from app.core.brep.kernel import Solid

        if one_piece:
            solid = edit.box(40.0, 20.0, 20.0)
        else:
            compound = TopoDS_Compound()
            builder = BRep_Builder()
            builder.MakeCompound(compound)
            builder.Add(compound, edit.box(40.0, 20.0, 10.0).shape)
            builder.Add(compound, edit.moved(edit.box(40.0, 20.0, 10.0), (0.0, 0.0, 10.0)).shape)
            solid = Solid(compound)
        plates = SceneObject("obj_1", "Platten", solid, kind="brep", features=features_of(solid))
    else:
        import trimesh

        if one_piece:
            whole = trimesh.creation.box(extents=(40.0, 20.0, 20.0))
            whole.apply_translation((0.0, 0.0, 10.0))
            shells = MeshData.of(whole)
        else:
            lower = trimesh.creation.box(extents=(40.0, 20.0, 10.0))
            lower.apply_translation((0.0, 0.0, 5.0))
            upper = trimesh.creation.box(extents=(40.0, 20.0, 10.0))
            upper.apply_translation((0.0, 0.0, 15.0))
            shells = MeshData.of(trimesh.util.concatenate([lower, upper]))
        plates = SceneObject("obj_1", "Platten", shells, features=detect(shells))
    widening = (
        {"widening_diameter": 12.0, "widening_depth": 0.0, "transition_angle": 90.0} if sunk else {}
    )
    drilled = _raw(
        "drill_hole",
        plates,
        _plates_profile(),
        x=0.0,
        y=0.0,
        z=20.0,
        axis="z",
        nx=0.0,
        ny=0.0,
        nz=1.0,
        diameter=6.0,
        depth=0.0,
        anchor="mouth",
        compensate=False,
        **widening,
    ).outputs[0]
    return _redetected(kernel, drilled)


def _plates_profile() -> Profile:
    from app.core.knowledge import profiles

    load_operations()
    return profiles.make_profile("centauri-carbon-2", "petg")


def _redetected(kernel: str, entry: SceneObject) -> SceneObject:
    """Das Ergebnis neu erkannt, wie die Auswertung es nach jedem Schritt tut."""
    import dataclasses

    from app.core.perceive.features import detect

    if entry.kind == "brep":
        from app.core.brep.features import features_of

        return dataclasses.replace(entry, features=features_of(entry.mesh))
    return dataclasses.replace(entry, features=detect(as_mesh_data(entry.mesh)))


def _cavities(entry: SceneObject) -> list[tuple[str, float, tuple[float, ...]]]:
    """Art, Durchmesser und Mitte jeder Bohrung und Senkung — gerundet zum Vergleich."""
    return sorted(
        (
            feature.kind,
            round(float(feature.params["diameter"]), 1),
            tuple(round(float(value), 1) + 0.0 for value in feature.params["centre"]),
        )
        for feature in entry.features.values()
        if feature.kind in ("hole", "cone", "slot")
    )


def _closing_values(entry: SceneObject, op: str) -> dict[str, object]:
    hole = next(name for name, feature in entry.features.items() if feature.kind == "hole")
    x, y, z = (float(value) for value in entry.features[hole].params["centre"])
    if op == "move_feature":
        return {"at_feature": hole, "x": x + 8.0, "y": y, "z": z}
    if op == "place_feature":
        # Der freie Platzierungsweg (``_place_oriented_feature``): mit Richtung.
        return {"at_feature": hole, "x": x + 8.0, "y": y, "z": z, "nx": 0.0, "ny": 0.0, "nz": 1.0}
    if op == "rotate_feature":
        return {"at_feature": hole, "axis": "x", "angle": 10.0}
    if op == "resize_hole":
        return {
            "at_feature": hole,
            "diameter": 8.0,
            "compensate": False,
            "x": x + 8.0,
            "y": y,
            "z": z,
        }
    return {"at_feature": hole}


#: Der exakte Sollwert je Handlung, wo er sich rechnen lässt (ohne / mit Senkung).
_EXACT_AFTER: dict[str, tuple[float | None, float | None]] = {
    "move_feature": (_PLATES - _BORE, _PLATES - _BORE - _SINK),
    "place_feature": (_PLATES - _BORE, _PLATES - _BORE - _SINK),
    # Die schräge Bohrung endet an den alten Randebenen: ein schiefer Zylinder
    # zwischen zwei Ebenen im Abstand 20, Querschnitt π r² / cos 10°.
    "rotate_feature": (_PLATES - _BORE / math.cos(math.radians(10.0)), None),
    "resize_hole": (_PLATES - 16.0 * math.pi * 20.0, None),
    "remove_feature": (_PLATES, _PLATES),
    "plug_hole": (_PLATES, _PLATES - _SINK - 9.0 * math.pi * 3.0),
}


#: Die schließenden Wege je Kern — auch der freie Platzierungsweg mit Richtung
#: (``_place_oriented_feature``) am exakten Körper, seit er dort exakt rechnet
#: bzw. ein Netz als Netz ausweist (RM-423).
_CLOSING_WAYS: Final = [
    (kernel, op)
    for kernel in ("mesh", "brep")
    for op in (
        "move_feature",
        "place_feature",
        "rotate_feature",
        "resize_hole",
        "remove_feature",
        "plug_hole",
    )
]


@pytest.mark.parametrize("sunk", [False, True], ids=["Bohrung", "Senkbohrung"])
@pytest.mark.parametrize(("kernel", "op"), _CLOSING_WAYS)
def test_every_closing_way_treats_touching_plates_as_one_printed_body(
    kernel: str, sunk: bool, op: str
) -> None:
    """Jeder schließende Weg verbindet berührende Schalen vorher, an beiden Kernen (RM-386).

    Das Ergebnis an den zwei Berührplatten ist das an der Platte aus einem
    Stück: ein dichter Körper, dasselbe Volumen, dieselben Hohlräume an
    derselben Stelle — und der Bericht sagt, dass vereinigt wurde. Vorher
    verlor am Netz die versetzte Senkbohrung 2 516,3 mm³ und zerfiel in zwei
    halbe Bohrungen, am exakten Kern stand nach *Bohrung ändern* mit Versatz ein
    loser Zylinder von 502,7 mm³ in der neuen Bohrung, Versetzen und Kippen
    sagten ab, und *Merkmal entfernen* und *Bohrung verschließen* hinterließen
    einen Körper, dessen Netz nicht dicht war.
    """
    profile = _plates_profile()
    plates = _touching_plates(kernel, sunk=sunk)
    control = _touching_plates(kernel, sunk=sunk, one_piece=True)
    assert _cavities(plates) == _cavities(control), "die Vorbedingung: dieselbe Bohrung"
    if kernel == "brep":
        assert plates.mesh.solid_count == 2, "die Vorbedingung: zwei Volumenkörper"
    else:
        assert plates.mesh.component_count == 2, "die Vorbedingung: zwei Schalen"

    registered = "move_feature" if op == "place_feature" else op
    result = _raw(registered, plates, profile, **_closing_values(plates, op))
    wanted = _raw(registered, control, profile, **_closing_values(control, op))
    after = _redetected(kernel, result.outputs[0])
    expected = _redetected(kernel, wanted.outputs[0])

    twin = as_mesh_data(after.mesh)
    pieces = after.mesh.solid_count if after.kind == "brep" else twin.component_count
    assert pieces == 1, f"{op}: ein Körper erwartet, {pieces} gefunden"
    assert twin.is_watertight, f"{op}: das Netz des Ergebnisses ist nicht dicht"
    assert float(after.mesh.volume) == pytest.approx(float(expected.mesh.volume), abs=0.05), op
    assert _cavities(after) == _cavities(expected), op
    reference = _EXACT_AFTER[op][1 if sunk else 0]
    if after.kind == "brep" and reference is not None:
        assert float(after.mesh.volume) == pytest.approx(reference, abs=0.05), op
    codes = [finding.code for finding in result.findings]
    assert codes.count("boolean.parts_united") == 1, codes
    assert not [finding for finding in result.findings if finding.severity == "warning"], codes


@pytest.mark.parametrize("sunk", [False, True], ids=["Bohrung", "Senkbohrung"])
@pytest.mark.parametrize("kernel", ["mesh", "brep"])
def test_a_bore_placed_with_a_new_direction_says_which_kernel_it_ended_on(
    kernel: str, sunk: bool
) -> None:
    """*Merkmal verschieben* mit Richtung am exakten Körper (RM-423).

    Gerechnet wurde am Netz, und der Körper kam als Netz unter der Bauart
    ``brep`` zurück — Folgeschritte des exakten Kerns trafen ein Netz. Eine
    einzelne Bohrung rechnet jetzt exakt: dasselbe Volumen wie die um 10°
    gekippte Bohrung durch die Platte, π r² · 20 / cos 10°. Eine Senkbohrung
    rechnet weiter am Netz und ist danach eins.
    """
    profile = _plates_profile()
    plate = _touching_plates(kernel, sunk=sunk, one_piece=True)
    hole = next(name for name, feature in plate.features.items() if feature.kind == "hole")
    x, y, z = (float(value) for value in plate.features[hole].params["centre"])
    tilt = math.radians(10.0)

    result = _raw(
        "move_feature",
        plate,
        profile,
        at_feature=hole,
        x=x,
        y=y,
        z=z,
        nx=math.sin(tilt),
        ny=0.0,
        nz=math.cos(tilt),
    )

    after = result.outputs[0]
    stays_exact = kernel == "brep" and not sunk
    assert after.kind == ("brep" if stays_exact else "mesh"), after.kind
    assert (kind_of(after.mesh) == "brep") == (after.kind == "brep"), "Bauart und Körper stimmen"
    if not sunk:
        reference = _PLATES - _BORE / math.cos(tilt)
        if stays_exact:
            assert float(after.mesh.volume) == pytest.approx(reference, abs=0.05)
        else:
            assert float(after.mesh.volume) == pytest.approx(reference, rel=1e-2)
        axis = np.asarray(after.features[hole].params["axis"], dtype=float)
        assert abs(abs(float(axis[2])) - math.cos(tilt)) < 1e-6, axis


#: Die schließenden Wege, die nur eine Senkbohrung hat: Abschnitte einzeln,
#: Senkung ändern, Einlauf mitnehmen — je Operation und Werte ab ihren Merkmalen.
_SECTION_WAYS: Final = {
    "Senkung ändern": ("resize_feature", "cone", {"diameter": 14.0}),
    "Einlauf mitnehmen": (
        "resize_hole",
        "hole",
        {"diameter": 8.0, "compensate": False, "entrance_mode": "follow"},
    ),
    "nur die Senkung entfernen": ("remove_feature", "cone", {"sections": "single"}),
    "nur die Bohrung entfernen": ("remove_feature", "hole", {"sections": "single"}),
}


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
@pytest.mark.parametrize("way", list(_SECTION_WAYS))
def test_every_section_of_a_countersunk_bore_closes_touching_plates_as_one_body(
    kernel: str, way: str
) -> None:
    """Auch die Kettenwege lesen und schließen am verbundenen Körper (RM-386).

    Am exakten Kern lasen diese vier Wege den Einlauf am Compound, an dem die
    Grenzfläche die Bohrungswand in zwei Abschnitte teilt, und sagten ab: der
    Hohlraum lasse sich nicht als eine Bohrung lesen, der Einlauf nicht
    gemeinsam ändern, aus den Flächen entstehe kein Körper. Das Netz rechnete
    sie richtig. Soll ist die Platte aus einem Stück.
    """
    op, kind, values = _SECTION_WAYS[way]
    profile = _plates_profile()
    results = []
    for one_piece in (False, True):
        entry = _touching_plates(kernel, sunk=True, one_piece=one_piece)
        chosen = next(name for name, feature in entry.features.items() if feature.kind == kind)
        result = _raw(op, entry, profile, at_feature=chosen, **values)
        results.append((result, _redetected(kernel, result.outputs[0])))
    (result, after), (_wanted, expected) = results

    twin = as_mesh_data(after.mesh)
    pieces = after.mesh.solid_count if after.kind == "brep" else twin.component_count
    assert pieces == 1, f"{way}: ein Körper erwartet, {pieces} gefunden"
    assert twin.is_watertight, way
    assert float(after.mesh.volume) == pytest.approx(float(expected.mesh.volume), abs=0.05), way
    assert _cavities(after) == _cavities(expected), way
    codes = [finding.code for finding in result.findings]
    assert codes.count("boolean.parts_united") == 1, codes
    assert not [finding for finding in result.findings if finding.severity == "warning"], codes
