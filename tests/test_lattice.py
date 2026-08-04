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
