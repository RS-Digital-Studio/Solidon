"""Merkmalsmuster: ein Merkmal linear, kreisförmig oder gespiegelt wiederholen (P6.7).

Konzept §13.2, Zeile P6.7, und der Kundenweg aus §13.9: Bohrungs- und
Senkungsmuster auf einem selbst erzeugten und einem eingelesenen Teil, mit
Anzahl, Maßen, Richtungen, ausgelassenen Instanzen und nachgeführter
Quelländerung — und ohne versehentliche Kopie des ganzen Körpers (das tut
``pattern``, *Kopien in Reihe oder Kreis*).

Die Sollwerte stammen aus der Konstruktion: Jede Instanz nimmt genau so viel
Material wie die Quelle, liegt an der Stelle, die Abstand, Winkel oder
Spiegelebene vorgeben, und zeigt in die Richtung, die die Bewegung ihr gibt.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from app.core.bootstrap import load_operations
from app.core.errors import ValidationError
from app.core.geom.mesh import as_mesh_data, read_mesh
from app.core.ingest.loader import normalise
from app.core.perceive.features import detect
from app.core.types import Feature, Profile, SceneObject
from tests.helpers import countersunk_plate, exact_kernel, material_plate
from tests.helpers import run_operation as run
from tests.test_exact_feature_ops import COUNTERSUNK_CAVITY, PIN_VOLUME

MESHES = Path(__file__).parent / "data" / "meshes"
PLATE = (60.0, 40.0, 10.0)
BORE = math.pi * 3.0**2 * PLATE[2]


def _holes(entry: SceneObject, kind: str = "hole") -> list[Feature]:
    return sorted(
        (feature for feature in entry.features.values() if feature.kind == kind),
        key=lambda feature: tuple(round(float(v), 3) for v in feature.params["centre"]),
    )


def _centres(features: list[Feature]) -> list[tuple[float, float]]:
    return [
        (round(float(f.params["centre"][0]), 6), round(float(f.params["centre"][1]), 6))
        for f in features
    ]


def _exact_plate_with_bore(x: float, y: float, *, depth: float = 10.0, top: float = 10.0) -> Any:
    """Die exakte Platte 60 × 40 × 10 mit einer Bohrung Ø 6 an (x, y), von oben."""
    edit = exact_kernel()
    from app.core.brep.features import features_of

    body = edit.cut_bore(
        edit.box(*PLATE),
        position=(x, y, top - depth / 2.0),
        direction=(0.0, 0.0, 1.0),
        diameter=6.0,
        depth=depth,
    )
    return SceneObject(
        id="obj_1", name="Platte", mesh=body, kind="brep", features=features_of(body)
    )


def _mesh_plate_with_bore(profile: Profile, x: float, y: float) -> SceneObject:
    """Dieselbe Platte als Netz, die Bohrung Ø 6 durchgehend mit *Bohrung setzen*."""
    box = run("create_box", None, profile, width=PLATE[0], depth=PLATE[1], height=PLATE[2])
    drilled = run(
        "drill_hole",
        box.outputs[0],
        profile,
        x=x,
        y=y,
        z=PLATE[2],
        diameter=6.0,
        depth=0.0,
        compensate=False,
    ).outputs[0]
    mesh = as_mesh_data(drilled.mesh)
    return SceneObject(id="obj_1", name="Platte", mesh=mesh, features=detect(mesh))


def _codes(result: Any) -> dict[str, Any]:
    return {finding.code: finding for finding in result.findings}


# --- exakt -----------------------------------------------------------------------


def test_a_linear_row_of_exact_bores_with_one_left_out(profile: Profile) -> None:
    """Vier Plätze im Abstand 8, der dritte ausgelassen: drei Bohrungen, exakt."""
    load_operations()
    source = _exact_plate_with_bore(0.0, 0.0)
    hole = _holes(source)[0]

    result = run(
        "pattern_feature",
        source,
        profile,
        at_features=(hole.id,),
        kind="linear",
        count=4,
        spacing=8.0,
        skip="3",
        dx=1.0,
        dy=0.0,
        dz=0.0,
    )

    output = result.outputs[0]
    assert output.kind == "brep" and output.mesh.is_closed
    assert float(output.mesh.volume) == pytest.approx(24000.0 - 3 * BORE, rel=1e-9)
    holes = _holes(output)
    assert _centres(holes) == [(0.0, 0.0), (8.0, 0.0), (24.0, 0.0)]
    assert holes[0].id == hole.id, "die Quelle behält ihren Namen"
    assert all(h.params["diameter"] == pytest.approx(6.0, abs=1e-9) for h in holes)
    assert all(h.params["through"] for h in holes)
    assert {h.id for h in holes[1:]} <= set(output.reserved_feature_ids)
    assert not any(finding.converts_exact_body for finding in result.findings)
    done = _codes(result)["pattern_feature.done"]
    assert done.values["placed"] == 2 and done.values["skipped"] == 1


def test_a_circular_pattern_of_exact_bores_closes_the_ring(profile: Profile) -> None:
    """Vier Bohrungen im vollen Kreis um z: die vierte fällt nicht auf die erste."""
    load_operations()
    source = _exact_plate_with_bore(15.0, 0.0)
    hole = _holes(source)[0]

    result = run(
        "pattern_feature",
        source,
        profile,
        at_features=(hole.id,),
        kind="circular",
        count=4,
        angle=360.0,
        dx=0.0,
        dy=0.0,
        dz=1.0,
    )

    output = result.outputs[0]
    assert output.kind == "brep"
    assert float(output.mesh.volume) == pytest.approx(24000.0 - 4 * BORE, rel=1e-9)
    assert sorted(_centres(_holes(output))) == [
        (-15.0, 0.0),
        (0.0, -15.0),
        (0.0, 15.0),
        (15.0, 0.0),
    ]


def test_radial_bores_turn_with_the_ring(profile: Profile) -> None:
    """Eine radiale Bohrung in einer Walze, vierfach um die Walzenachse.

    Die Achse der Instanz dreht mit — der Fall, den eine reine Verschiebung
    nicht kann. Jede Instanz nimmt dasselbe Material wie die Quelle.
    """
    edit = exact_kernel()
    load_operations()
    from app.core.brep.features import features_of

    drum = edit.cylinder(40.0, 20.0)
    drilled = edit.cut_bore(
        drum, position=(17.0, 0.0, 10.0), direction=(1.0, 0.0, 0.0), diameter=4.0, depth=8.0
    )
    source = SceneObject(
        id="obj_1", name="Walze", mesh=drilled, kind="brep", features=features_of(drilled)
    )
    hole = _holes(source)[0]
    removed = float(drum.volume) - float(drilled.volume)

    result = run(
        "pattern_feature",
        source,
        profile,
        at_features=(hole.id,),
        kind="circular",
        count=4,
        angle=360.0,
        dx=0.0,
        dy=0.0,
        dz=1.0,
    )

    output = result.outputs[0]
    assert output.kind == "brep"
    assert float(output.mesh.volume) == pytest.approx(float(drum.volume) - 4 * removed, rel=1e-9)
    axes = sorted(tuple(round(abs(float(v)), 6) for v in h.params["axis"]) for h in _holes(output))
    assert axes == [(0.0, 1.0, 0.0), (0.0, 1.0, 0.0), (1.0, 0.0, 0.0), (1.0, 0.0, 0.0)]


def test_a_mirrored_blind_bore_opens_on_the_other_side(profile: Profile) -> None:
    """Sackloch von oben, an der Mittelebene gespiegelt: ein Sackloch von unten."""
    load_operations()
    source = _exact_plate_with_bore(10.0, 5.0, depth=4.0)
    hole = _holes(source)[0]
    assert hole.params["through"] is False

    result = run(
        "pattern_feature",
        source,
        profile,
        at_features=(hole.id,),
        kind="mirror",
        dx=0.0,
        dy=0.0,
        dz=1.0,
        cz=5.0,
    )

    output = result.outputs[0]
    assert output.kind == "brep"
    assert float(output.mesh.volume) == pytest.approx(24000.0 - 2 * math.pi * 9.0 * 4.0, rel=1e-9)
    heights = sorted(round(float(h.params["centre"][2]), 6) for h in _holes(output))
    assert heights == [2.0, 8.0]
    assert all(h.params["through"] is False for h in _holes(output))


def test_a_slot_turns_its_direction_in_a_circular_pattern(profile: Profile) -> None:
    edit = exact_kernel()
    load_operations()
    from app.core.brep.features import features_of

    body = edit.slot_bore(
        edit.box(*PLATE),
        position=(12.0, 0.0, 5.0),
        direction=(0.0, 0.0, 1.0),
        diameter=6.0,
        depth=10.0,
        length=10.0,
        angle_deg=0.0,
        overlap=0.0,
    )
    source = SceneObject(
        id="obj_1", name="Platte", mesh=body, kind="brep", features=features_of(body)
    )
    slot = _holes(source, "slot")[0]
    area = math.pi * 9.0 + 6.0 * 4.0

    result = run(
        "pattern_feature",
        source,
        profile,
        at_features=(slot.id,),
        kind="circular",
        count=4,
        angle=360.0,
        dz=1.0,
    )

    output = result.outputs[0]
    assert output.kind == "brep"
    assert float(output.mesh.volume) == pytest.approx(24000.0 - 4 * area * 10.0, rel=1e-9)
    by_place = {
        tuple(round(float(v), 6) for v in s.params["centre"][:2]): s for s in _holes(output, "slot")
    }
    turned = by_place[(0.0, 12.0)]
    assert abs(float(np.asarray(turned.params["direction"], dtype=float) @ (0.0, 1.0, 0.0))) == (
        pytest.approx(1.0, abs=1e-9)
    )


def test_a_row_of_exact_pins(profile: Profile) -> None:
    load_operations()
    source = material_plate("pin")
    pin = _holes(source, "pin")[0]

    result = run(
        "pattern_feature",
        source,
        profile,
        at_features=(pin.id,),
        kind="linear",
        count=3,
        spacing=12.0,
        dx=1.0,
    )

    output = result.outputs[0]
    assert output.kind == "brep" and output.mesh.is_closed
    assert float(output.mesh.volume) == pytest.approx(24000.0 + 3 * PIN_VOLUME, rel=1e-9)
    assert _centres(_holes(output, "pin")) == [(0.0, 0.0), (12.0, 0.0), (24.0, 0.0)]


def test_a_countersunk_bore_repeats_as_a_whole(profile: Profile) -> None:
    """Bohrung und Senkung sind ein Hohlraum; jede Instanz bekommt beide."""
    load_operations()
    source = countersunk_plate(profile)
    hole = _holes(source)[0]

    result = run(
        "pattern_feature",
        source,
        profile,
        at_features=(hole.id,),
        kind="linear",
        count=2,
        spacing=20.0,
        dx=1.0,
    )

    output = result.outputs[0]
    assert output.kind == "brep"
    assert float(output.mesh.volume) == pytest.approx(24000.0 - 2 * COUNTERSUNK_CAVITY, rel=1e-9)
    assert len(_holes(output)) == 2 and len(_holes(output, "cone")) == 2
    assert sorted(_centres(_holes(output, "cone"))) == [(0.0, 0.0), (20.0, 0.0)]


def test_an_exact_pin_in_the_air_is_explained_and_left_out(profile: Profile) -> None:
    """Die zweite Instanz stünde neben der Platte in der Luft — sie entsteht nicht."""
    load_operations()
    source = material_plate("pin")
    pin = _holes(source, "pin")[0]

    result = run(
        "pattern_feature",
        source,
        profile,
        at_features=(pin.id,),
        kind="linear",
        count=2,
        spacing=40.0,
        dx=1.0,
    )

    output = result.outputs[0]
    assert float(output.mesh.volume) == pytest.approx(24000.0 + PIN_VOLUME, rel=1e-9)
    missing = _codes(result)["pattern_feature.no_target"]
    assert missing.values["instances"] == "2"
    assert missing.suggestions


# --- Netz ------------------------------------------------------------------------


def test_a_linear_row_of_mesh_bores(profile: Profile) -> None:
    load_operations()
    source = _mesh_plate_with_bore(profile, -20.0, 0.0)
    hole = _holes(source)[0]
    removed = 24000.0 - float(source.mesh.volume)

    result = run(
        "pattern_feature",
        source,
        profile,
        at_features=(hole.id,),
        kind="linear",
        count=4,
        spacing=12.0,
        dx=1.0,
    )

    output = result.outputs[0]
    assert output.kind == "mesh" and output.mesh.is_watertight
    assert float(output.mesh.volume) == pytest.approx(24000.0 - 4 * removed, rel=1e-4)
    declared = _holes(output)
    assert _centres(declared) == [(-20.0, 0.0), (-8.0, 0.0), (4.0, 0.0), (16.0, 0.0)]
    found = _holes(SceneObject(id="x", name="x", mesh=output.mesh, features=detect(output.mesh)))
    assert _centres(found) == pytest.approx(_centres(declared), abs=1e-3)
    assert all(h.params["diameter"] == pytest.approx(6.0, abs=0.05) for h in found)


def test_a_circular_and_a_mirrored_pattern_on_a_mesh(profile: Profile) -> None:
    load_operations()
    source = _mesh_plate_with_bore(profile, 15.0, 8.0)
    hole = _holes(source)[0]
    removed = 24000.0 - float(source.mesh.volume)

    mirrored = run(
        "pattern_feature", source, profile, at_features=(hole.id,), kind="mirror", dx=1.0
    ).outputs[0]
    assert float(mirrored.mesh.volume) == pytest.approx(24000.0 - 2 * removed, rel=1e-4)
    assert sorted(_centres(_holes(mirrored))) == [(-15.0, 8.0), (15.0, 8.0)]

    ring = run(
        "pattern_feature",
        source,
        profile,
        at_features=(hole.id,),
        kind="circular",
        count=2,
        angle=360.0,
        dz=1.0,
    ).outputs[0]
    assert float(ring.mesh.volume) == pytest.approx(24000.0 - 2 * removed, rel=1e-4)
    assert sorted(_centres(_holes(ring))) == [(-15.0, -8.0), (15.0, 8.0)]


def test_an_imported_countersunk_plate_gets_its_pattern(profile: Profile) -> None:
    """Der Kundenweg am eingelesenen Teil: Senkbohrung aus dem Korpus, zweimal."""
    load_operations()
    path = MESHES / "plate_countersunk.stl"
    # Der Ladeweg der Anwendung: verschweißt, wie ein geöffnetes STL.
    mesh = normalise(read_mesh(path.read_bytes(), path.suffix), "mm").mesh
    source = SceneObject(id="obj_1", name="Platte", mesh=mesh, features=detect(mesh))
    hole = _holes(source)[0]
    full = 60.0 * 40.0 * 8.0
    removed = full - float(mesh.volume)

    result = run(
        "pattern_feature",
        source,
        profile,
        at_features=(hole.id,),
        kind="linear",
        count=2,
        spacing=18.0,
        dx=1.0,
    )

    body = result.outputs[0].mesh
    assert body.is_watertight
    assert float(body.volume) == pytest.approx(full - 2 * removed, rel=1e-3)
    found = detect(body)
    assert len([f for f in found.values() if f.kind == "hole"]) == 2
    assert len([f for f in found.values() if f.kind == "cone"]) == 2


def test_an_imported_plate_on_the_bed_gets_a_fifth_hole(profile: Profile) -> None:
    """Korpusplatte 80 × 50 × 8 mit vier 48-eckigen Bohrungen Ø 5,2: eine weitere längs Y."""
    load_operations()
    path = MESHES / "plate_holes.stl"
    mesh = normalise(read_mesh(path.read_bytes(), path.suffix), "mm", place_on_bed=True).mesh
    source = SceneObject(id="obj_1", name="Lochplatte", mesh=mesh, features=detect(mesh))
    hole = _holes(source)[0]

    result = run(
        "pattern_feature",
        source,
        profile,
        at_features=(hole.id,),
        kind="linear",
        count=2,
        spacing=15.0,
        dy=1.0,
    )

    body = result.outputs[0].mesh
    # Jeder der 48 Mantelabschnitte begrenzt ein Dreieck vom Kreismittelpunkt.
    bore_volume = 48 / 2 * 2.6**2 * math.sin(2 * math.pi / 48) * 8.0
    assert float(body.volume) == pytest.approx(80 * 50 * 8 - 5 * bore_volume, abs=1e-3)
    assert body.is_watertight and body.component_count == 1
    assert len(_holes(result.outputs[0])) == 5
    assert _codes(result)["pattern_feature.done"].values["placed"] == 1
    assert "pattern_feature.no_target" not in _codes(result)


def test_overlapping_instances_are_explained_and_left_out(profile: Profile) -> None:
    """Abstand 4 bei Ø 6: die zweite Instanz schnitte in die Quelle — sie entsteht nicht."""
    load_operations()
    source = _mesh_plate_with_bore(profile, -20.0, 0.0)
    hole = _holes(source)[0]
    removed = 24000.0 - float(source.mesh.volume)

    result = run(
        "pattern_feature",
        source,
        profile,
        at_features=(hole.id,),
        kind="linear",
        count=3,
        spacing=4.0,
        dx=1.0,
    )

    overlap = _codes(result)["pattern_feature.overlap"]
    assert overlap.values["instances"] == "2"
    assert overlap.suggestions
    assert float(result.outputs[0].mesh.volume) == pytest.approx(24000.0 - 2 * removed, rel=1e-4)
    assert _centres(_holes(result.outputs[0])) == [(-20.0, 0.0), (-12.0, 0.0)]


def test_instances_beyond_the_part_are_explained_and_left_out(profile: Profile) -> None:
    load_operations()
    source = _mesh_plate_with_bore(profile, -20.0, 0.0)
    hole = _holes(source)[0]
    removed = 24000.0 - float(source.mesh.volume)

    result = run(
        "pattern_feature",
        source,
        profile,
        at_features=(hole.id,),
        kind="linear",
        count=4,
        spacing=30.0,
        dx=1.0,
    )

    missing = _codes(result)["pattern_feature.no_target"]
    assert missing.values["instances"] == "3, 4"
    assert float(result.outputs[0].mesh.volume) == pytest.approx(24000.0 - 2 * removed, rel=1e-4)


@pytest.mark.parametrize(
    ("case", "constraint"),
    [
        ("none", "required"),
        ("unknown", "unknown_feature"),
        ("single", "pattern_count"),
        ("thread", "not_movable"),
        ("unproven", "not_evidenced"),
        ("skip_source", "pattern_skip"),
    ],
)
def test_every_refusal_of_a_pattern_names_its_reason(
    profile: Profile, case: str, constraint: str
) -> None:
    load_operations()
    source = _mesh_plate_with_bore(profile, -20.0, 0.0)
    hole = _holes(source)[0]
    params: dict[str, Any] = {"at_features": (hole.id,), "kind": "linear", "count": 3}
    if case == "none":
        params["at_features"] = ()
    elif case == "unknown":
        params["at_features"] = ("hole_99",)
    elif case == "single":
        params["count"] = 1
    elif case == "skip_source":
        params["skip"] = "1"
    elif case in {"thread", "unproven"}:
        extra = Feature(
            id="odd_1",
            kind="thread" if case == "thread" else "hole",
            provenance="detected",
            params={"diameter": 6.0, "centre": (0.0, 0.0, 5.0), "axis": (0.0, 0.0, 1.0)},
        )
        source = SceneObject(
            id="obj_1",
            name="Platte",
            mesh=source.mesh,
            features={**source.features, "odd_1": extra},
        )
        params["at_features"] = ("odd_1",)

    with pytest.raises(ValidationError) as caught:
        run("pattern_feature", source, profile, **params)

    assert caught.value.constraint == constraint, caught.value.constraint
    assert caught.value.suggestions, "jede Absage nennt einen Ausweg (Regel 17)"


# --- Kundenweg: die Quelle bleibt maßgebend ----------------------------------------


@pytest.mark.parametrize("exact", [True, False])
def test_the_pattern_follows_its_source_through_history_undo_and_the_file(
    profile: Profile, tmp_path: Path, exact: bool
) -> None:
    """Bohrung setzen, dreimal wiederholen, die Bohrung im ursprünglichen Schritt
    auf Ø 8 ändern: Die Instanzen folgen. Ein Strg+Z nimmt das ganze Muster.

    Auf beiden Körperarten, mit Speichern und Wiederöffnen dazwischen.
    """
    if exact:
        exact_kernel()
    from app.core.scene import ResultCache, evaluate
    from app.core.scene.history import History, OperationDraft
    from app.core.scene.project import load, new_project, save

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    box = "create_brep_box" if exact else "create_box"
    history.apply(
        "Platte",
        [OperationDraft(op=box, params={"width": PLATE[0], "depth": PLATE[1], "height": PLATE[2]})],
    )
    history.apply(
        "Bohrung",
        [
            OperationDraft(
                op="drill_hole",
                inputs=("obj_1",),
                params={
                    "x": -20.0,
                    "y": 0.0,
                    "z": PLATE[2],
                    "diameter": 5.0,
                    "depth": 0.0,
                    "compensate": False,
                },
            )
        ],
    )
    drilled = evaluate(project.document, profile, cache=ResultCache())
    hole = _holes(drilled.scene.objects["obj_1"])[0]
    one = 24000.0 - float(drilled.scene.objects["obj_1"].mesh.volume)

    history.apply(
        "Muster",
        [
            OperationDraft(
                op="pattern_feature",
                inputs=("obj_1",),
                params={
                    "at_features": [hole.id],
                    "kind": "linear",
                    "count": 3,
                    "spacing": 15.0,
                    "dx": 1.0,
                },
            )
        ],
    )
    patterned = evaluate(project.document, profile, cache=ResultCache())
    assert patterned.stopped_at is None, patterned.stopped_at
    body = patterned.scene.objects["obj_1"]
    assert body.kind == ("brep" if exact else "mesh")
    assert float(body.mesh.volume) == pytest.approx(24000.0 - 3 * one, rel=1e-9 if exact else 1e-4)

    # Die Quelle ändern — im Schritt, der sie gesetzt hat.
    drill = next(op for op in project.document.ops if op.op == "drill_hole")
    history.change_params(drill.id, {**drill.params, "diameter": 8.0})
    wider = evaluate(project.document, profile, cache=ResultCache())
    assert wider.stopped_at is None, wider.stopped_at
    grown = wider.scene.objects["obj_1"]
    holes = _holes(grown)
    assert _centres(holes) == pytest.approx([(-20.0, 0.0), (-5.0, 0.0), (10.0, 0.0)], abs=1e-3)
    assert all(h.params["diameter"] == pytest.approx(8.0, abs=0.05) for h in holes)
    if exact:
        assert float(grown.mesh.volume) == pytest.approx(
            24000.0 - 3 * math.pi * 16.0 * PLATE[2], rel=1e-9
        )

    path = save(project, tmp_path / "platte.p3d")
    again = evaluate(load(path).document, profile, cache=ResultCache())
    assert float(again.scene.objects["obj_1"].mesh.volume) == pytest.approx(
        float(grown.mesh.volume), rel=1e-9
    )

    history.undo()  # die Änderung der Quelle
    history.undo()  # das ganze Muster, ein Schritt
    back = evaluate(project.document, profile, cache=ResultCache())
    assert len(_holes(back.scene.objects["obj_1"])) == 1
    assert float(back.scene.objects["obj_1"].mesh.volume) == pytest.approx(24000.0 - one, rel=1e-9)
    history.redo()
    forth = evaluate(project.document, profile, cache=ResultCache())
    assert len(_holes(forth.scene.objects["obj_1"])) == 3


@pytest.mark.parametrize("exact", [True, False])
def test_a_cancelled_pattern_stops_without_a_result(profile: Profile, exact: bool) -> None:
    """Abbrechen hält an, ohne halbes Muster — auf beiden Kernen (§15.6)."""
    from app.core.errors import OperationCancelled
    from app.core.registry import REGISTRY
    from app.core.scene.cancel import CancelSignal
    from app.core.types import OpContext, Scene

    load_operations()
    source = _exact_plate_with_bore(0.0, 0.0) if exact else _mesh_plate_with_bore(profile, 0.0, 0.0)
    hole = _holes(source)[0]
    signal = CancelSignal()
    signal.cancel()
    spec = REGISTRY.get("pattern_feature")

    with pytest.raises(OperationCancelled):
        spec.fn(
            OpContext(
                scene=Scene(objects={source.id: source}),
                inputs=[source],
                params=spec.params(at_features=(hole.id,), kind="linear", count=3, spacing=8.0),
                profile=profile,
                quality="fine",
                seed=None,
                progress=lambda fraction, text: None,
                ask=lambda question, choices: choices[0],
                cancelled=signal,
            )
        )


def test_the_body_pattern_is_not_the_feature_pattern(profile: Profile) -> None:
    """Keine versehentliche Kopie des ganzen Körpers: ein Objekt hinein, eines heraus."""
    load_operations()
    source = _mesh_plate_with_bore(profile, -20.0, 0.0)
    hole = _holes(source)[0]

    result = run(
        "pattern_feature",
        source,
        profile,
        at_features=(hole.id,),
        kind="linear",
        count=3,
        spacing=12.0,
        dx=1.0,
    )

    assert len(result.outputs) == 1
    assert result.outputs[0].id == source.id
    bounds = result.outputs[0].mesh.bounds
    assert tuple(bounds.size) == pytest.approx(PLATE, abs=1e-6)
