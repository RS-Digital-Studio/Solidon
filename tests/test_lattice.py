"""Gitterfüllung im Modell (Konzept P15 §7 Etappe 7, D17).

Der Slicer füllt mit Gitter, was er für innen hält. Er kennt weder die
Lastrichtung noch die Stelle, an der es dünn sein darf, und seine Füllung
existiert erst im G-Code — sie überlebt keinen Export, keine zweite Maschine
und keinen Slicerwechsel.

Eine Füllung im Modell ist echte Geometrie: sie reist im 3MF mit, sie steht im
Steckbrief als Zahl, und sie ist dieselbe, egal wer sie schneidet. Das ist
Spherenes Thema — lokal, ohne Browser, und **kein G-Code-Slicer** (§22.5): das
hier ist Geometrie *vor* dem Slicer.
"""

from __future__ import annotations

import pytest
import trimesh

from app.core.bootstrap import load_operations
from app.core.errors import ValidationError
from app.core.geom import lattice
from app.core.geom.mesh import MeshData
from app.core.knowledge import profiles
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import (
    OpContext,
    OpResult,
    PrinterProfile,
    Scene,
    SceneObject,
)

PRINTER = PrinterProfile(id="test", title="Test", build_volume=(220.0, 220.0, 250.0))


def run(entry: SceneObject, **params: object) -> OpResult:
    load_operations()
    spec = REGISTRY.get("lattice_fill")
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}, parameters={}),
            inputs=[entry],
            params=spec.params(**params),
            profile=profiles.make_profile(),
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def hollow_cube(size: float = 40.0, wall: float = 2.0) -> SceneObject:
    """Ein ausgehöhlter Würfel — der Fall, für den die Füllung da ist."""
    outer = trimesh.creation.box(extents=(size,) * 3)
    inner = trimesh.creation.box(extents=(size - 2.0 * wall,) * 3)
    body = trimesh.boolean.difference([outer, inner])
    return SceneObject(id="obj_1", name="Kasten", mesh=MeshData.of(body))


# --- die Gitter selbst ----------------------------------------------------------


def test_every_structure_fills_the_box_it_is_given() -> None:
    """Jede Struktur füllt ihren Bereich, und keine füllt ihn ganz.

    Eine Füllung, die alles ausfüllt, ist ein Vollkörper; eine, die fast nichts
    ausfüllt, trägt nichts. Beide Grenzen prüft dieser Test — dieselbe Frage,
    die beim Kreuzrändel den Fehler gefunden hat.
    """
    box = ((-10.0, -10.0, -10.0), (10.0, 10.0, 10.0))
    for structure in lattice.STRUCTURES:
        body = lattice.build(structure, box, cell=5.0, wall=1.0)
        assert body is not None, f"{structure} liefert nichts"
        share = body.volume / (20.0**3)
        assert 0.02 < share < 0.8, f"{structure} füllt {share:.0%} — das ist keine Füllung"


def test_a_finer_cell_puts_more_material_in() -> None:
    """Kleinere Zellen heißen mehr Stege — sonst wäre die Zellgröße kein
    Regler, sondern eine Zierde."""
    box = ((-10.0, -10.0, -10.0), (10.0, 10.0, 10.0))
    coarse = lattice.build("gyroid", box, cell=10.0, wall=1.0)
    fine = lattice.build("gyroid", box, cell=5.0, wall=1.0)

    assert coarse is not None and fine is not None
    assert fine.volume > coarse.volume


def test_a_wall_below_the_nozzle_is_refused() -> None:
    """E1: ein Steg schmaler als zwei Extrusionsbahnen wird nicht gedruckt."""
    profile = profiles.make_profile()
    with pytest.raises(ValidationError) as problem:
        lattice.check_printable(wall=0.1, cell=5.0, profile=profile)

    assert problem.value.field == "wall"
    assert problem.value.suggestions


def test_a_wall_thicker_than_the_cell_is_refused() -> None:
    """Ein Steg, der so dick ist wie seine Zelle, ist ein Vollkörper."""
    with pytest.raises(ValidationError) as problem:
        lattice.check_printable(wall=5.0, cell=5.0, profile=profiles.make_profile())

    assert problem.value.field == "cell"


# --- die Operation --------------------------------------------------------------


def test_filling_a_hollow_body_adds_material_inside() -> None:
    """Die Füllung sitzt im Hohlraum und macht den Körper schwerer, nicht
    größer."""
    entry = hollow_cube()
    before = entry.mesh.volume
    outside = entry.mesh.bounds.size

    result = run(entry, structure="gyroid", cell=8.0, wall=1.0)

    body = result.outputs[0].mesh
    assert body.volume > before, "im Hohlraum steht jetzt Material"
    assert body.bounds.size == pytest.approx(outside, abs=1e-6), "von außen unverändert"


def test_a_cubic_fill_stays_inside_the_body() -> None:
    """Das Würfelgitter bleibt im Hohlraum — keine Stäbe außerhalb des Teils.

    Die Stabmitten liefen bis eine ganze Zelle über den Hohlraum hinaus; was
    dabei jenseits der Außenwand lag, überlebte die Differenz gegen den Körper
    und hing frei neben dem Teil. Gemessen war ein Außenmaß von +2,5 mm und drei
    Dutzend lose Balken. Der Gyroid-Test daneben deckt genau diese Struktur
    nicht ab.
    """
    entry = hollow_cube(size=40.0, wall=2.0)
    outside = entry.mesh.bounds.size
    before = entry.mesh.volume

    result = run(entry, structure="cubic", cell=8.0, wall=1.0)

    body = result.outputs[0].mesh
    assert body.bounds.size == pytest.approx(outside, abs=1e-6), (
        "von außen unverändert — kein Stab jenseits der Außenwand"
    )
    assert body.volume > before, "im Hohlraum steht jetzt Material"


def test_filling_a_solid_body_says_it_needs_a_cavity() -> None:
    """Ein Vollkörper hat keinen Hohlraum, und eine Füllung ohne Hohlraum ist
    nichts — das sagt die Operation, statt stillschweigend nichts zu tun."""
    solid = SceneObject(
        id="obj_1", name="Klotz", mesh=MeshData.of(trimesh.creation.box(extents=(20.0,) * 3))
    )

    with pytest.raises(ValidationError) as problem:
        run(solid, structure="gyroid", cell=5.0, wall=1.0)

    assert problem.value.field == "structure"
    assert problem.value.suggestions, "Regel 17: der Fehler nennt den Weg — erst aushöhlen"


def test_the_digest_says_how_solid_a_body_is() -> None:
    """Die Kennzahl, die sagt, wie viel Material der Druck kostet (§23).

    Ein Vollkörper füllt seinen Hüllquader ganz, ein ausgehöhlter kaum, ein
    gefüllter liegt dazwischen. Sie steht schon in den beiden Zahlen davor —
    Maße und Volumen —, aber niemand rechnet sie im Kopf.

    Ein offener Körper bekommt sie nicht: sein Volumen ist keine verlässliche
    Zahl, und eine unverlässliche Prozentangabe ist schlimmer als keine.
    """
    from app.core.perceive.digest import digest
    from app.core.types import Scene

    solid = SceneObject(
        id="obj_1", name="Klotz", mesh=MeshData.of(trimesh.creation.box(extents=(20.0,) * 3))
    )
    text = digest(Scene(objects={"obj_1": solid}, parameters={}))
    assert "100%" in text.replace(" %", "%"), "ein Quader füllt seinen Hüllquader ganz"

    box = hollow_cube(size=40.0, wall=2.0)
    hollow_text = digest(Scene(objects={"obj_1": box}, parameters={}))
    assert "100%" not in hollow_text, "ein ausgehöhlter Körper nicht"


@pytest.mark.parametrize("structure", lattice.STRUCTURES)
def test_round_imported_cavity_adds_nothing_outside_the_original_envelope(structure):
    from app.core.geom.boolean import boolean

    outer = MeshData.of(trimesh.creation.cylinder(radius=10, height=20, sections=48))
    inner = MeshData.of(trimesh.creation.cylinder(radius=8, height=16, sections=48))
    shell = boolean("difference", [outer, inner]).mesh
    result = run(
        SceneObject(id="obj_1", name="Dose", mesh=shell), structure=structure, cell=5, wall=1
    )
    filled = result.outputs[0].mesh
    outside = boolean("difference", [filled, outer], allow_empty=True)
    assert outside.mesh.volume < 1e-6
    assert filled.volume > shell.volume


def test_vented_concave_cavity_survives_storage_and_stays_inside():
    from app.core.geom.boolean import boolean
    from app.core.geom.hollow import hollow

    first = trimesh.creation.box((30, 12, 16))
    second = trimesh.creation.box((12, 30, 16))
    second.apply_translation((9, 9, 0))
    outer = boolean("union", [MeshData.of(first), MeshData.of(second)]).mesh
    hollowed = hollow(outer, 2, vents=1)
    assert len(hollowed.vents) == 1
    shell = hollowed.mesh
    assert shell.cavity is not None
    restored = MeshData.from_bytes(shell.to_bytes())
    result = run(
        SceneObject(id="obj_1", name="Winkel", mesh=restored), structure="cubic", cell=5, wall=1
    )
    assert result.outputs[0].mesh.volume > shell.volume
    outside = boolean("difference", [result.outputs[0].mesh, outer], allow_empty=True)
    assert outside.mesh.volume < 1e-6
    # Das Entlüftungsloch muss Innen- und Außenfläche tatsächlich verbinden.
    # Getrennte geschlossene Innenflächen bleiben beim Import ausdrücklich nutzbar.
    imported = MeshData.of(shell.raw.copy())
    if len(imported.raw.split(only_watertight=False)) == 1:
        with pytest.raises(ValidationError):
            run(
                SceneObject(id="obj_1", name="Import", mesh=imported),
                structure="cubic",
                cell=5,
                wall=1,
            )


def test_cavity_metadata_is_not_recursively_serialized():
    import dataclasses

    body = MeshData.of(trimesh.creation.box())
    once = dataclasses.replace(body, cavity=body)
    with pytest.raises(ValueError, match="nested_cavity"):
        dataclasses.replace(body, cavity=once)
    assert once.replacing(body.raw.copy()).cavity is None


def test_document_hollow_lattice_roundtrip_uses_the_same_enclosed_geometry(tmp_path):
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, load, new_project, save

    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Füllen",
        [
            OperationDraft(op="create_cylinder", params={"diameter": 20, "height": 20}),
            OperationDraft(op="hollow_object", inputs=("obj_1",), params={"wall": 2}),
            OperationDraft(
                op="lattice_fill",
                inputs=("obj_1",),
                params={"structure": "cubic", "cell": 5, "wall": 1},
            ),
        ],
    )
    reopened = load(save(project, tmp_path / "filled.solidon"))
    result = evaluate(reopened.document, profiles.make_profile(), sources=ProjectSources(reopened))
    assert result.complete, result.scene.report.findings
    assert result.scene.objects["obj_1"].mesh.bounds.size == pytest.approx((20, 20, 20), abs=1e-5)


def test_open_import_has_no_guessed_cavity():
    from app.core.geom.boolean import boolean

    outer = trimesh.creation.cylinder(radius=10, height=20, sections=48)
    inner = trimesh.creation.cylinder(radius=8, height=20, sections=48)
    inner.apply_translation((0, 0, 2))
    cup = boolean("difference", [MeshData.of(outer), MeshData.of(inner)]).mesh
    assert len(cup.raw.split(only_watertight=False)) == 1
    with pytest.raises(ValidationError):
        run(SceneObject(id="obj_1", name="Import", mesh=cup), structure="cubic", cell=5, wall=1)
