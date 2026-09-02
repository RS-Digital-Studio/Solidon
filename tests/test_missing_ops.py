"""Die Operationen, die §25 nennt und die dem Register fehlten (§25, §10).

Spiegeln, Netz, Aushöhlen, Elefantenfuß, Senken, Verschließen, Beschriftung,
Zeichnungen. Jede einzelne ist etwas, wofür Leute die Anwendung sonst verlassen
— und jede einzelne wird hier gegen eine Zahl gemessen, die sich von Hand
nachrechnen lässt, nicht auf einem Bild angeschaut.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest
import trimesh

from app.core.errors import ValidationError
from app.core.geom import mesh_ops
from app.core.geom.hollow import hollow
from app.core.geom.label_ops import outlines
from app.core.geom.mesh import MeshData, as_mesh_data, read_mesh
from app.core.geom.prepare import compensate_elephant_foot, countersink, plug
from app.core.ingest.loader import normalise
from app.core.ingest.outline import extrude, is_outline
from app.core.knowledge import profiles
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import OpContext, Profile, Scene, SceneObject

SVG = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">'
    b'<path d="M10,10 L90,10 L90,90 L10,90 Z M30,30 L30,70 L70,70 L70,30 Z"/></svg>'
)

MESHES = Path(__file__).parent / "data" / "meshes"


def block(width: float = 40.0, depth: float = 40.0, height: float = 40.0) -> MeshData:
    body = trimesh.creation.box(extents=(width, depth, height))
    body.apply_translation((0.0, 0.0, height / 2.0))
    return MeshData.of(body)


def run(op: str, entry: SceneObject | None, profile: Profile, **params: object):
    spec = REGISTRY.get(op)
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry} if entry else {}),
            inputs=[entry] if entry else [],
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


# --- mirroring ------------------------------------------------------------------


def test_mirroring_turns_the_part_over_without_turning_it_inside_out(profile: Profile) -> None:
    """Eine Spiegelung stülpt jedes Dreieck um — ein Körper mit umgedrehten
    Normalen ist kaputt.
    """
    wedge = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    wedge.apply_translation((15.0, 0.0, 10.0))
    entry = SceneObject(id="obj_1", name="Rechts", mesh=MeshData.of(wedge))

    result = run("mirror_object", entry, profile, axis="x", about="origin")

    mirrored = result.outputs[0].mesh
    assert mirrored.volume == pytest.approx(8000.0), "positive, so not inside out"
    assert mirrored.is_watertight
    assert mirrored.bounds.centre[0] == pytest.approx(-15.0)


# --- das Netz -------------------------------------------------------------------


def test_decimation_keeps_the_shape_within_a_measured_bound(profile: Profile) -> None:
    sphere = MeshData.of(trimesh.creation.icosphere(subdivisions=5, radius=20.0))
    entry = SceneObject(id="obj_1", name="Kugel", mesh=sphere)

    result = run("decimate_mesh", entry, profile, triangles=2000)

    after = result.outputs[0].mesh
    assert after.triangle_count == 2000
    assert mesh_ops.deviation(sphere, after) < 0.2, "under two tenths on a 40 mm ball"
    assert [finding.code for finding in result.findings] == ["mesh.deviation"]
    assert result.findings[0].values["deviation_mm"] > 0.0, "it says what it cost"


@pytest.mark.parametrize("target", [20_000, 8_000, 2_000])
def test_decimation_does_not_tear_an_unwelded_body_apart(target: int) -> None:
    """Der Fund „`decimate` zerlegt glatte Körper" — die Glätte war es nicht.

    Quadrik-Dezimierung zieht Kanten zusammen. Wo keine Kante zwei Dreiecke
    verbindet, weil jedes seine eigenen drei Punkte trägt, zieht sie das Netz
    auseinander: **81 920 einzelne Dreiecke kamen als 12 450 Teile heraus,
    nicht wasserdicht.** Gemessen an der Vase aus dem Erzeuger war es dasselbe
    Bild (607 k → 200 k, 60 Teile) — und ein Modell aus dem Erzeuger ist genau
    so ein Netz, wie es jedes frisch gelesene STL ist.

    Über drei Ziele, weil ein einzelnes nichts über die Stufe darunter sagt:
    Der Riss entsteht beim Zusammenziehen, und je weiter dezimiert wird, desto
    mehr Kanten sind daran beteiligt.
    """
    ball = trimesh.creation.icosphere(subdivisions=6, radius=40.0)
    # Eine Dreieckssuppe, wie sie aus einer STL-Datei kommt: kein Punkt geteilt.
    loose = trimesh.Trimesh(
        vertices=ball.vertices[ball.faces].reshape(-1, 3),
        faces=np.arange(len(ball.faces) * 3).reshape(-1, 3),
        process=False,
    )
    soup = MeshData.of(loose)
    # **Gefragt wird die Speicherform, nicht das Teil.** Hier stand
    # ``component_count == triangle_count`` — bis zum 27.08.2026 traf das zu,
    # weil die Komponentenzählung die gespeicherte Nachbarschaft las und in
    # einer Suppe jedes Dreieck für sich stand. Seither zählt sie über den Ort
    # mit und sagt richtig **1**: Die Kugel *ist* ein Teil, gleich wie sie
    # abgelegt ist. Die Zusicherung, die dieser Test braucht, ist eine andere —
    # dass keine Kante zwei Dreiecke verbindet, denn genau daran zieht die
    # Dezimierung. Gefragt wird sie mit derselben Kennzahl, an der auch
    # ``_welded_for_simplify`` entscheidet.
    assert len(loose.face_adjacency) == 0, "die Suppe ist keine Suppe"
    assert len(loose.vertices) / len(loose.faces) > mesh_ops.LOOSE_VERTEX_RATIO, (
        "und zwar nach demselben Maß, das die Vereinfachung anlegt"
    )

    after = mesh_ops.decimate(soup, target)

    assert after.triangle_count == target
    assert after.is_watertight, f"bei {target} Dreiecken nicht mehr geschlossen"
    assert after.component_count == 1, (
        f"bei {target} Dreiecken in {after.component_count} Teile zerfallen"
    )
    # Eine Kugel von 40 mm Radius hat 268 cm³. Bleibt sie das, ist nicht bloß
    # die Topologie heil, sondern auch die Form.
    assert after.volume / 1000.0 == pytest.approx(268.0, abs=1.0)


def test_a_welded_body_is_not_welded_again() -> None:
    """Verschweißt wird nur, wo es nötig ist — es kostet vierzig Prozent.

    Auf einem schon verschweißten Netz bewegt `merge_vertices` null Punkte und
    kostet trotzdem 37 bis 43 Prozent der Vereinfachung obendrauf (gemessen:
    103 ms zu 281 bei 328 k Dreiecken, 408 zu 951 bei 1,3 Mio.). `decimate`
    läuft auch für die Anzeige im Viewport, und ein Zuschlag für nichts gehört
    dort nicht hin.

    Geprüft am Verhältnis, nicht an der Zeit: Eine Messung wäre auf einer
    belasteten Maschine unbrauchbar, und die Frage ist ohnehin nicht „wie
    schnell", sondern „wird überhaupt angefasst".
    """
    welded = MeshData.of(trimesh.creation.icosphere(subdivisions=5, radius=40.0))

    assert len(welded.raw.vertices) < welded.triangle_count, (
        "die Vorbedingung stimmt nicht — dieses Netz gilt als unverschweißt"
    )
    assert mesh_ops._welded_for_simplify(welded) is welded, (
        "ein verschweißtes Netz wird noch einmal angefasst"
    )


def test_a_small_body_is_left_alone() -> None:
    small = MeshData.of(trimesh.creation.box(extents=(10.0, 10.0, 10.0)))

    assert mesh_ops.decimate(small, 4).triangle_count == small.triangle_count


def test_smoothing_does_not_shrink_the_body(profile: Profile) -> None:
    """Taubin statt Laplace — zehn Durchgänge des Letzteren kosten eine
    Passung.
    """
    sphere = MeshData.of(trimesh.creation.icosphere(subdivisions=4, radius=20.0))
    entry = SceneObject(id="obj_1", name="Kugel", mesh=sphere)

    result = run("smooth_mesh", entry, profile, iterations=10)

    assert result.outputs[0].mesh.volume == pytest.approx(sphere.volume, rel=0.02)


def test_smoothing_a_thin_wall_refuses_instead_of_turning_it_inside_out(
    profile: Profile,
) -> None:
    """Ein negatives Volumen ist kein Ergebnis, sondern ein umgestülpter Körper.

    Aushöhlen, dann glätten: die Innenwand wandert an der Außenwand vorbei, und
    heraus kommt ein Netz, das sich wasserdicht nennt und −19 318 mm³ misst.
    Jede Kennzahl danach ist falsch — Materialverbrauch, Massivität, der ganze
    Prüfbericht — und exportieren ließ es sich auch.
    """
    box = trimesh.creation.box(extents=(40.0, 40.0, 30.0))
    box.apply_translation((0.0, 0.0, 15.0))
    hollowed = hollow(MeshData.of(box), 2.0, vents=1).mesh
    entry = SceneObject(id="obj_1", name="Schale", mesh=hollowed)

    with pytest.raises(ValidationError) as raised:
        run("smooth_mesh", entry, profile, iterations=5)

    assert raised.value.suggestions


def test_smoothing_says_how_much_body_it_cost(profile: Profile) -> None:
    """„Ohne den Körper zu schrumpfen" gilt für ein feines Netz, nicht für ein
    grobes.

    Ein Quader aus zwölf Dreiecken hat nichts als Ecken, und Taubin zieht sie
    zusammen: aus 48 000 mm³ werden 3 315, also sieben Prozent. Die
    Abweichungswarnung sagt dazu „die Fläche hat sich spürbar verschoben" —
    richtig und viel zu leise.
    """
    entry = SceneObject(id="obj_1", name="Quader", mesh=block(40.0, 40.0, 30.0))

    result = run("smooth_mesh", entry, profile, iterations=5)

    codes = {finding.code for finding in result.findings}
    assert "mesh.smooth_shrank" in codes
    warning = next(f for f in result.findings if f.code == "mesh.smooth_shrank")
    assert warning.severity == "warning"
    assert float(warning.values["lost"]) > 0.5


def test_smoothing_a_fine_mesh_stays_quiet(profile: Profile) -> None:
    """Die Gegenprobe — sonst warnt jedes Glätten und keine Warnung zählt."""
    sphere = MeshData.of(trimesh.creation.icosphere(subdivisions=4, radius=20.0))
    entry = SceneObject(id="obj_1", name="Kugel", mesh=sphere)

    result = run("smooth_mesh", entry, profile, iterations=5)

    assert "mesh.smooth_shrank" not in {finding.code for finding in result.findings}


def test_remeshing_splits_edges_without_moving_anything(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Würfel", mesh=block(20.0, 20.0, 20.0))

    result = run("remesh_mesh", entry, profile, edge=5.0)

    after = result.outputs[0].mesh
    assert after.triangle_count > 12
    assert after.volume == pytest.approx(8000.0), "the shape is untouched"
    assert after.is_watertight


def test_remeshing_an_uneven_body_keeps_it_closed(profile: Profile) -> None:
    """Der Würfel oben ging immer gut, weil alle seine Kanten gleich lang sind.

    Bei ungleichen Kanten wird jede Fläche verschieden oft geteilt, und an den
    Nähten dazwischen stand ein Punkt auf einer Kante, die ihn nicht kannte:
    192 Kanten mit nur einem Nachbarn, drei Komponenten, kein geschlossener
    Körper. Der Befund sagte trotzdem „die Form ist unverändert", und die
    nächste boolesche Operation fiel auf die Voxelstufe und rundete die Maße.
    """
    entry = SceneObject(id="obj_1", name="Platte", mesh=block(40.0, 30.0, 10.0))

    result = run("remesh_mesh", entry, profile, edge=5.0)

    after = result.outputs[0].mesh
    assert after.is_watertight, "ein zerrissenes Netz bricht alles, was danach kommt"
    assert after.component_count == 1
    assert after.volume == pytest.approx(12_000.0)
    assert after.triangle_count > 12


def test_remeshing_reaches_the_edge_length_it_promises(profile: Profile) -> None:
    """„Teilt lange Kanten, bis das Netz gleichmäßig ist" — nachgemessen."""
    entry = SceneObject(id="obj_1", name="Platte", mesh=block(40.0, 30.0, 10.0))

    result = run("remesh_mesh", entry, profile, edge=5.0)

    longest = max(mesh_ops.edge_lengths(as_mesh_data(result.outputs[0].mesh)))
    assert longest <= 5.0 + 1e-9


def test_a_torn_remesh_says_so_instead_of_claiming_the_shape_is_fine(profile: Profile) -> None:
    """Was die Operation über ihr Ergebnis sagt, muss sie geprüft haben.

    Ein offener Körper kommt hier nicht aus dem Unterteilen, sondern aus dem
    Eingang — und dann darf die Meldung nicht behaupten, alles sei in Ordnung.
    """
    open_body = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    open_body.update_faces(np.arange(len(open_body.faces)) > 1)
    entry = SceneObject(id="obj_1", name="Offen", mesh=MeshData.of(open_body))

    result = run("remesh_mesh", entry, profile, edge=2.0)

    codes = {finding.code for finding in result.findings}
    assert "mesh.remesh_open" in codes
    assert any(finding.severity == "warning" for finding in result.findings)


def test_remeshing_an_imported_part_keeps_it_closed_and_says_the_price(
    profile: Profile,
) -> None:
    """Geschlossen bleibt die Bedingung — was es kostet, hat trimesh 5 geändert.

    ``plate_holes`` hat winzige Bohrungsfacetten neben großen Grundflächen. Der
    bedarfsgerechte Weg schafft 5 mm, zerreißt das Netz dabei aber; der
    gleichmäßige hält es geschlossen, weil er die winzigen Facetten mitzerteilt.

    Was er dafür verlangt, ist eingebrochen (gemessen am 14.08.2026 an
    derselben Datei): Aus 796 Dreiecken wurden unter **trimesh 4.12.2**
    815 104 — Faktor 1024, und die längste Kante lag bei 2,51 mm, also weit
    unter den verlangten 5. Unter **trimesh 5.0.0** sind es 22 636, Faktor 28,
    und die längste Kante trifft die 5,0 genau. Der Warnbefund
    ``mesh.remesh_dense`` bleibt hier deshalb aus; er greift erst ab dem
    Hundertfachen und hat seinen eigenen Test darunter.
    """
    mesh = normalise(read_mesh((MESHES / "plate_holes.stl").read_bytes(), ".stl"), "mm").mesh
    entry = SceneObject(id="obj_1", name="Platte", mesh=mesh)

    result = run("remesh_mesh", entry, profile, edge=5.0)

    after = result.outputs[0].mesh
    assert after.is_watertight, "geschlossen bleibt die Bedingung, nicht der Wunsch"
    assert after.component_count == 1
    assert max(mesh_ops.edge_lengths(as_mesh_data(after))) <= 5.0 + 1e-9
    assert "mesh.remeshed" in {finding.code for finding in result.findings}
    assert after.triangle_count < mesh.triangle_count * mesh_ops.DENSE_FACTOR, (
        "das Netz ist wieder explodiert — dann gehört der Warnbefund geprüft, "
        "nicht diese Schranke gelockert"
    )


def test_a_net_that_explodes_says_so(profile: Profile, monkeypatch) -> None:
    """Der Warnbefund hing an einer Zahl, die trimesh 5 unterschritten hat.

    Vor dem Sprung löste ``plate_holes`` ihn von selbst aus — mit dem
    Tausendfachen war die Schwelle vom Hundertfachen leicht erreicht. Jetzt
    liegt derselbe Fall bei Faktor 28, und ohne diesen Test wäre der Pfad
    ungeprüft: Er ist nicht überflüssig geworden, er wird nur seltener
    gebraucht.
    """
    monkeypatch.setattr(mesh_ops, "DENSE_FACTOR", 2)
    mesh = normalise(read_mesh((MESHES / "plate_holes.stl").read_bytes(), ".stl"), "mm").mesh
    entry = SceneObject(id="obj_1", name="Platte", mesh=mesh)

    result = run("remesh_mesh", entry, profile, edge=5.0)

    codes = {finding.code for finding in result.findings}
    assert "mesh.remesh_dense" in codes, "der Sprung gehört gesagt, sonst sucht niemand die Ursache"


def test_an_edge_length_beyond_reach_names_one_that_works(profile: Profile) -> None:
    """Eine Ablehnung ohne Zahl schickt den Nutzer ins Raten.

    Er hat eine Kantenlänge eingetippt, sie ist zu klein, und die einzige
    Auskunft war „ergäbe mehr Dreiecke, als sich noch rechnen lassen". Welche
    ginge, stand nirgends — dabei weiß es die Operation.
    """
    mesh = normalise(read_mesh((MESHES / "plate_holes.stl").read_bytes(), ".stl"), "mm").mesh
    entry = SceneObject(id="obj_1", name="Platte", mesh=mesh)

    with pytest.raises(ValidationError) as raised:
        run("remesh_mesh", entry, profile, edge=0.05)

    assert raised.value.suggestions
    assert "reachable" in raised.value.values or "erreichbar" in str(raised.value.detail)


# --- hollowing ------------------------------------------------------------------


def test_hollowing_leaves_the_wall_and_takes_the_rest(profile: Profile) -> None:
    result = hollow(block(), 2.0, vents=1)

    assert result.mesh.is_watertight
    assert result.removed > 30_000.0, "a 40 mm cube has plenty inside"
    assert result.mesh.volume < 64_000.0 * 0.4
    assert len(result.vents) == 1


def test_a_wall_thicker_than_the_body_leaves_nothing_to_take(profile: Profile) -> None:
    thin = MeshData.of(trimesh.creation.box(extents=(6.0, 6.0, 6.0)))

    result = hollow(thin, 5.0)

    assert result.mesh is thin
    assert [finding.code for finding in result.findings] == ["hollow.too_thin"]


def test_hollowing_without_a_vent_is_possible_and_says_nothing_extra(profile: Profile) -> None:
    result = hollow(block(), 2.0, vents=0)

    assert not result.vents
    assert "hollow.no_vent" not in {finding.code for finding in result.findings}


def test_an_opened_body_is_a_tin(profile: Profile) -> None:
    """§25: der Weg von der Aushöhlung zur Dose ist ein Schalter, kein Umweg.

    Vorher endete *Aushöhlen* immer bei einem geschlossenen Hohlraum, und wer
    eine Dose wollte, baute sie aus zwei Zylindern und einer Differenz — dem
    Weg, den ein CAD-Anwender kennt und den die Bausteine nicht nahelegen.
    """
    closed = hollow(block(), 2.0)
    opened = hollow(block(), 2.0, open_top=True)

    assert opened.mesh.is_watertight
    assert opened.mesh.component_count == 1
    assert opened.mesh.volume < closed.mesh.volume, "die Decke ist weg"
    assert not opened.vents, "eine offene Dose ist ihre eigene Entlüftung"


def test_the_lid_finds_the_opening_that_hollowing_made(profile: Profile) -> None:
    """Die zwei Schritte hintereinander — das ist der Punkt der Sache.

    *Deckel erzeugen* verlangt eine Öffnung und meldete sonst „auf dieser Höhe
    massiv". Ein ausgehöhlter und oben geöffneter Körper hat eine.
    """
    from app.core.registry import REGISTRY
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene

    tin = SceneObject(id="obj_1", name="Dose", mesh=hollow(block(), 3.0, open_top=True).mesh)
    spec = REGISTRY.get("create_lid")
    result = spec.fn(
        OpContext(
            scene=Scene(objects={tin.id: tin}),
            inputs=[tin],
            params=spec.params(thickness=2.4, collar=4.0),
            profile=profile,
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )

    lid = result.outputs[1].mesh
    assert lid.is_watertight
    assert lid.bounds.size[0] == pytest.approx(40.0, abs=0.5), "der Deckel deckt die Dose"


def test_hollow_runs_as_an_operation(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Klotz", mesh=block())

    result = run("hollow_object", entry, profile, wall=2.0, vents=1)

    assert result.outputs[0].mesh.volume < 30_000.0
    assert "hollow.done" in {finding.code for finding in result.findings}


# --- die erste Schicht ----------------------------------------------------------


def test_the_first_layers_are_pulled_in_by_the_profile_value(profile: Profile) -> None:
    """Regel 7: der Wert kommt aus dem Material, nie aus einer Schätzung."""
    body = block(40.0, 40.0, 10.0)
    entry = SceneObject(id="obj_1", name="Klotz", mesh=body)

    result = run("compensate_first_layer", entry, profile, height=0.6)

    corrected = result.outputs[0].mesh
    assert corrected.volume < body.volume
    lost = body.volume - corrected.volume
    expected = (40.0**2 - (40.0 - 2 * profile.material.elephant_foot) ** 2) * 0.6
    assert lost == pytest.approx(expected, rel=0.15)
    assert "prepare.elephant_foot" in {finding.code for finding in result.findings}


def test_without_a_measured_value_nothing_happens(profile: Profile) -> None:
    import dataclasses

    flat = dataclasses.replace(
        profile, material=dataclasses.replace(profile.material, elephant_foot=0.0)
    )
    body = block()

    corrected, findings, solver = compensate_elephant_foot(body, flat)

    assert corrected is body and not findings
    assert solver is None, "ohne Schnitt gibt es auch keine Rückfallstufe"


# --- holes ----------------------------------------------------------------------


def test_a_countersink_takes_off_the_cone_of_the_head(profile: Profile) -> None:
    body = block(40.0, 40.0, 10.0)
    diameter, angle = 8.0, 90.0

    result = countersink(body, position=(0.0, 0.0, 10.0), axis="z", diameter=diameter, angle=angle)

    depth = diameter / 2.0 / math.tan(math.radians(angle / 2.0))
    cone = math.pi * (diameter / 2.0) ** 2 * depth / 3.0
    assert body.volume - result.mesh.volume == pytest.approx(cone, rel=0.05)


def test_a_plug_fills_a_bore_and_stays_inside_the_part(profile: Profile) -> None:
    from app.core.geom.prepare import drill

    body = block(40.0, 40.0, 10.0)
    drilled = drill(body, position=(0.0, 0.0, 5.0), axis="z", diameter=6.0, profile=profile).mesh
    assert drilled.volume < body.volume

    filled = plug(drilled, position=(0.0, 0.0, 5.0), axis="z", diameter=6.5)

    assert filled.mesh.volume == pytest.approx(body.volume, rel=0.01)
    assert filled.mesh.bounds.size[2] == pytest.approx(10.0, abs=0.01), "no plug sticking out"


def test_a_plug_with_nothing_to_fill_says_so(profile: Profile) -> None:
    """„Bohrung verschließen" auf einem Körper ohne Bohrung tat nichts und
    sagte nichts.

    Der Kunde sieht denselben Körper wie vorher und einen Schritt im Verlauf.
    Beim Bohren gibt es den Satz seit je („Der Schnitt hat nichts abgetragen");
    beim Verschließen fehlte die Gegenseite.
    """
    result = plug(block(40.0, 40.0, 10.0), position=(0.0, 0.0, 5.0), axis="z", diameter=6.0)

    assert "boolean.without_effect" in {finding.code for finding in result.findings}


def test_repairing_a_healthy_body_says_there_was_nothing_to_do(profile: Profile) -> None:
    """Ein Lauf ohne Wirkung ist ein Ergebnis und muss eines bleiben.

    Ohne diesen Satz sieht „Reparieren" auf einem gesunden Netz genauso aus
    wie ein Reparieren, das nicht gelaufen ist.
    """
    entry = SceneObject(id="obj_1", name="Würfel", mesh=block(20.0, 20.0, 20.0))

    result = run(
        "repair", entry, profile, weld=True, degenerate=True, normals=True, fill_holes=True
    )

    assert "repair.nothing_to_do" in {finding.code for finding in result.findings}


def test_the_hole_operations_are_in_the_register() -> None:
    for name in ("countersink_hole", "plug_hole"):
        assert REGISTRY.get(name).category == "holes"


# --- labels ---------------------------------------------------------------------


def test_a_letter_with_a_hole_comes_out_with_a_hole() -> None:
    """„o" sind zwei Ringe, und welcher das Loch ist, folgt aus der
    Enthaltung.
    """
    shapes = outlines("o", 10.0)

    assert shapes
    assert sum(len(entry.interiors) for entry in shapes) == 1


def test_raised_text_adds_exactly_its_own_volume(profile: Profile) -> None:
    plate = trimesh.creation.box(extents=(40.0, 20.0, 4.0))
    plate.apply_translation((0.0, 0.0, 2.0))
    entry = SceneObject(id="obj_1", name="Platte", mesh=MeshData.of(plate))
    area = sum(shape.area for shape in outlines("M4", 8.0))

    result = run("label_text", entry, profile, text="M4", size=8.0, depth=0.6, z=4.0)

    added = result.outputs[0].mesh.volume - 3200.0
    assert added == pytest.approx(area * 0.6, rel=0.01)
    assert result.outputs[0].mesh.bounds.size[2] == pytest.approx(4.6, abs=0.01)


def test_engraved_text_takes_away_the_same_volume(profile: Profile) -> None:
    """Der Fehler, um den es hier geht: ein Schnitt, der nur bis zur
    Überlappung reicht, ist ein Kratzer.
    """
    plate = trimesh.creation.box(extents=(40.0, 20.0, 4.0))
    plate.apply_translation((0.0, 0.0, 2.0))
    entry = SceneObject(id="obj_1", name="Platte", mesh=MeshData.of(plate))
    area = sum(shape.area for shape in outlines("M4", 8.0))

    result = run(
        "label_text", entry, profile, text="M4", size=8.0, depth=0.6, mode="engraved", z=4.0
    )

    removed = 3200.0 - result.outputs[0].mesh.volume
    assert removed == pytest.approx(area * 0.6, rel=0.01)
    assert result.outputs[0].mesh.bounds.size[2] == pytest.approx(4.0, abs=0.01), "nothing proud"


def test_raised_text_that_sinks_into_the_body_says_so(profile: Profile) -> None:
    """Gemessen am Beispiel „Dose mit Deckel", 02.09.2026: Ohne Ort und
    Richtung setzt die Operation die Schrift bei (0, 0, 0) mit der Normalen
    nach oben — für einen Körper auf dem Bett ist das der Boden, und erhaben
    nach oben heißt ins Material hinein. Sichtbar blieb nichts außer der
    Überlappung unter dem Boden, und kein Befund sagte es.
    """
    sunk = run("label_text", _plate(), profile, text="AB", size=6.0, depth=0.6)
    codes = [entry.code for entry in sunk.findings]
    assert "label.buried" in codes, f"kein Befund, gemeldet wurde: {codes}"
    buried = next(entry for entry in sunk.findings if entry.code == "label.buried")
    assert buried.severity == "warning"
    assert "Fläche" in str(buried.message), "der Befund nennt den Weg — die Fläche anklicken"

    # Dieselbe Schrift auf der Oberseite steht, und der Befund schweigt.
    standing = run("label_text", _plate(), profile, text="AB", size=6.0, depth=0.6, z=4.0)
    assert "label.buried" not in [entry.code for entry in standing.findings]


def _plate() -> SceneObject:
    plate = trimesh.creation.box(extents=(40.0, 20.0, 4.0))
    plate.apply_translation((0.0, 0.0, 2.0))
    return SceneObject(id="obj_1", name="Platte", mesh=MeshData.of(plate))


def test_a_label_beside_the_body_falls_off_as_loose_letters(profile: Profile) -> None:
    """**Die zweite Hälfte derselben Auskunft** (gemessen 31.08.2026).

    ``without_effect`` fragt nach dem **Volumen** und schweigt deshalb genau
    dann, wenn die Schrift danebenfällt statt zu fehlen: Die Buchstaben kommen
    ja hinzu, nur eben neben dem Teil. An einer Platte 40 auf 20 mit einer
    Beschriftung 200 mm daneben kamen **drei Komponenten** zurück, wo eine war
    — wasserdicht, plausibles Volumen, kein Befund.

    Der Kommentar an der Aufrufstelle beschreibt genau das, seit es ihn gibt:
    „die Buchstaben stehen dann als eigene Komponente neben dem Teil und reisen
    bis in den Export mit." Geprüft hat es niemand. Dieselbe Bauart und
    derselbe Satzbau wie ``texture.fell_apart``.
    """
    result = run("label_text", _plate(), profile, text="AB", size=6.0, depth=0.6, x=200.0, z=4.0)

    codes = [finding.code for finding in result.findings]
    assert "label.fell_apart" in codes, f"kein Befund, gemeldet wurde: {codes}"

    apart = next(f for f in result.findings if f.code == "label.fell_apart")
    assert int(apart.values["before"]) == 1, "die Platte war vorher schon zerteilt"
    assert int(apart.values["after"]) > 1, "nichts ist abgefallen — der Test misst nichts"
    assert apart.severity == "error", "lose Lettern im Export sind kein Schönheitsfehler"


def test_a_label_on_the_body_stays_silent(profile: Profile) -> None:
    """Die Gegenprobe: Was haftet, wird nicht angemeckert.

    Ohne sie bliebe der Test oben grün, auch wenn die Prüfung jede Beschriftung
    meldete — und der Kunde lernte, sie zu überlesen.
    """
    result = run("label_text", _plate(), profile, text="AB", size=6.0, depth=0.6, z=4.0)

    codes = [finding.code for finding in result.findings]
    assert "label.fell_apart" not in codes, f"Fehlalarm bei haftender Schrift: {codes}"


def test_an_engraved_label_may_divide_the_body() -> None:
    """Vertieft schneidet, und Schneiden darf teilen.

    Dieselbe Ausnahme wie bei Textur und Bausteinen. Geprüft wird die Funktion
    direkt, weil eine gravierte Schrift den Körper über die Operation gar nicht
    zerteilt — ein Test darüber wäre auch ohne die Bedingung grün und hielte
    damit nichts.
    """
    from types import SimpleNamespace

    from app.core.geom.label_ops import _fell_apart

    vorher = SimpleNamespace(component_count=1)
    nachher = SimpleNamespace(component_count=3)

    assert _fell_apart(vorher, nachher, "engraved") is None, (
        "ein Schnitt, der teilt, wurde als Zerfall gemeldet"
    )
    assert _fell_apart(vorher, nachher, "raised") is not None, (
        "die Gegenprobe: bei erhabener Schrift muss dieselbe Lage gemeldet werden"
    )


def test_a_label_that_misses_the_body_says_so(profile: Profile) -> None:
    """Denselben Satz bekommt seit je, wer eine Magnettasche daneben setzt —
    die Beschriftung bekam ihn nicht.

    So gefunden, an einem Sockel, dessen Hüllquader in der Mitte hohl ist:
    „BASIS" graviert kam mit unverändertem Volumen und unveränderter
    Dreieckszahl zurück, und der Prüfbericht hatte dazu keine Zeile. Im
    Verlauf stand ein Schritt, im Bild dasselbe Teil (§2.7).
    """
    plate = trimesh.creation.box(extents=(40.0, 20.0, 4.0))
    plate.apply_translation((0.0, 0.0, 2.0))
    entry = SceneObject(id="obj_1", name="Platte", mesh=MeshData.of(plate))

    result = run(
        "label_text",
        entry,
        profile,
        text="M4",
        size=8.0,
        depth=0.6,
        mode="engraved",
        x=200.0,
        z=4.0,
    )

    assert result.outputs[0].mesh.volume == pytest.approx(3200.0), "nothing was cut"
    assert "boolean.without_effect" in {finding.code for finding in result.findings}


def test_a_label_on_the_body_stays_quiet(profile: Profile) -> None:
    """Die Gegenprobe — sonst stünde die Warnung unter jeder Beschriftung."""
    plate = trimesh.creation.box(extents=(40.0, 20.0, 4.0))
    plate.apply_translation((0.0, 0.0, 2.0))
    entry = SceneObject(id="obj_1", name="Platte", mesh=MeshData.of(plate))

    result = run(
        "label_text", entry, profile, text="M4", size=8.0, depth=0.6, mode="engraved", z=4.0
    )

    assert "boolean.without_effect" not in {finding.code for finding in result.findings}


def test_a_label_without_text_is_a_user_error(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Platte", mesh=block())

    with pytest.raises(ValidationError) as problem:
        run("label_text", entry, profile, text="   ", size=8.0)

    assert problem.value.field == "text"


def test_lettering_can_carry_its_own_slot(profile: Profile) -> None:
    """§20: zwei Farben in einer Datei statt in zwei Dateien.

    Die Buchstaben gehen mit ihrem Slot bekleidet in die Vereinigung, und die
    Attributübertragung der Booleschen Op bringt ihn auf der anderen Seite
    heraus (P9). Was der Drucker liest, ist eine 3MF mit zwei Gruppen.
    """
    from app.core.geom.attributes import counts, used_slots

    plate = trimesh.creation.box(extents=(40.0, 20.0, 4.0))
    plate.apply_translation((0.0, 0.0, 2.0))
    entry = SceneObject(id="obj_1", name="Deckel", mesh=MeshData.of(plate))

    result = run("label_text", entry, profile, text="RS", size=10.0, z=4.0, slot=1)

    output = result.outputs[0]
    assert used_slots(output.mesh) == (0, 1)
    assert counts(output.mesh)[1] > 0, "the letters are in the second slot"
    assert [(slot.index, str(slot.name)) for slot in output.material_slots] == [
        (0, "Körper"),
        (1, "Schrift"),
    ]


def test_without_a_slot_the_lettering_stays_one_colour(profile: Profile) -> None:
    plate = trimesh.creation.box(extents=(40.0, 20.0, 4.0))
    plate.apply_translation((0.0, 0.0, 2.0))
    entry = SceneObject(id="obj_1", name="Deckel", mesh=MeshData.of(plate))

    result = run("label_text", entry, profile, text="RS", size=10.0, z=4.0)

    assert not result.outputs[0].mesh.slots


def test_a_label_can_be_a_body_of_its_own(profile: Profile) -> None:
    """Der andere Weg zu zwei Farben: eine zweite Datei für einen Drucker ohne
    AMS.
    """
    result = run("create_label", None, profile, text="RS", size=10.0, depth=2.0)

    body = result.outputs[0]
    assert body.name == "RS"
    assert body.mesh.bounds.size[2] == pytest.approx(2.0)
    assert body.mesh.triangle_count > 0


def test_a_label_body_keeps_the_counters_of_its_letters(profile: Profile) -> None:
    """Warum es **keinen** Text als Skizzenelement gibt (Konzept P15, D12).

    SindriCADs Sketcher kann einen Schriftzug als Skizzenkontur; unserer kann
    es nicht, und das ist eine Entscheidung. ``Profile`` trägt genau **einen**
    geschlossenen Umriss — ein Schriftzug ist eine Menge davon, jeder Buchstabe
    einer, und A, B und O tragen zusätzlich ein Loch. Das zu ändern hieße, alle
    fünf Skizzen-Operationen und den B-Rep-Kern anzufassen.

    Für einen Fall, den ``create_label`` bereits vollständig löst: drei
    getrennte Körper, jeder geschlossen, mit den Löchern an der richtigen
    Stelle. Dieser Test hält das fest, damit die Entscheidung eine Grundlage
    behält und nicht bei der nächsten Durchsicht neu geraten wird.
    """
    result = run("create_label", None, profile, text="ABO", size=10.0, depth=2.0)

    body = result.outputs[0].mesh
    assert body.raw.is_watertight, "jeder Buchstabe ist ein geschlossener Körper"
    assert len(body.raw.split()) == 3, "drei Buchstaben, drei Teile"
    # Die volle Hüllfläche wäre rund 157 mm³ bei 2 mm Tiefe; die Zähler in A,
    # B und O fehlen darin, also liegt das Volumen deutlich darunter.
    assert body.volume < 0.75 * body.bounds.size[0] * body.bounds.size[1] * 2.0


def test_an_empty_label_body_is_a_user_error(profile: Profile) -> None:
    with pytest.raises(ValidationError) as problem:
        run("create_label", None, profile, text="  ", size=10.0)

    assert problem.value.field == "text"


# --- das Prüfstück --------------------------------------------------------------


def drilled_plate() -> MeshData:
    plate = trimesh.creation.box(extents=(80.0, 50.0, 8.0))
    plate.apply_translation((0.0, 0.0, 4.0))
    drill = trimesh.creation.cylinder(radius=3.0, height=40.0)
    drill.apply_translation((25.0, 15.0, 0.0))
    return MeshData.of(trimesh.boolean.difference([plate, drill]))


def test_a_test_piece_is_a_cut_out_of_the_real_part(profile: Profile) -> None:
    """Ein Stück, das anders druckt als das Teil, wäre schlechter als keines."""
    body = drilled_plate()
    entry = SceneObject(id="obj_1", name="Halterung", mesh=body)

    result = run("test_piece", entry, profile, size=20.0, x=25.0, y=15.0, z=4.0)

    piece = result.outputs[0].mesh
    assert piece.bounds.size[0] == pytest.approx(20.0)
    assert piece.bounds.size[2] == pytest.approx(8.0), "the plate is thinner than the window"
    assert piece.is_watertight
    assert piece.volume < body.volume * 0.15, "a tenth of the print time"


def test_the_test_piece_lands_on_the_bed(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Halterung", mesh=drilled_plate())

    result = run("test_piece", entry, profile, size=20.0, x=25.0, y=15.0, z=4.0, on_bed=True)

    assert result.outputs[0].mesh.bounds.minimum[2] == pytest.approx(0.0, abs=1e-6)


def test_the_bore_is_still_in_the_piece(profile: Profile) -> None:
    """Sonst ist es ein Würfel, und ein Würfel beweist nichts über eine
    Passung.
    """
    entry = SceneObject(id="obj_1", name="Halterung", mesh=drilled_plate())

    result = run("test_piece", entry, profile, size=20.0, x=25.0, y=15.0, z=4.0)

    solid = 20.0 * 20.0 * 8.0
    assert result.outputs[0].mesh.volume < solid * 0.98, "a hole is missing from it"


def test_a_window_over_thin_air_is_a_user_error(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Halterung", mesh=drilled_plate())

    with pytest.raises(ValidationError) as problem:
        run("test_piece", entry, profile, size=10.0, x=500.0, y=0.0, z=0.0)

    assert problem.value.constraint == "empty"


# --- drawings -------------------------------------------------------------------


def test_a_drawing_becomes_a_body_with_its_holes() -> None:
    result = extrude(SVG, ".svg", 5.0)

    assert result.contours == 1
    assert result.mesh.volume == pytest.approx((80.0**2 - 40.0**2) * 5.0)
    assert result.mesh.is_watertight
    assert result.mesh.bounds.minimum[2] == pytest.approx(0.0), "on the plate"


def test_a_target_width_scales_the_plane_and_not_the_height() -> None:
    result = extrude(SVG, ".svg", 5.0, width=40.0)

    assert result.mesh.bounds.size[0] == pytest.approx(40.0)
    assert result.mesh.bounds.size[2] == pytest.approx(5.0), "the height was asked for in mm"


def test_a_target_width_measures_the_body_and_not_a_stray_line() -> None:
    """H1: skaliert wird der Körper aus den geschlossenen Ringen, nicht die
    ganze Zeichnung.

    Eine offene Hilfs- oder Maßlinie geht in die Zeichnung ein, aber nicht in
    den Körper — bei DXF ist das der Normalfall. An ``path.bounds`` gemessen
    (Quadrat 80 breit, Linie bis 200) wurde aus 40 mm verlangter Breite ein Teil
    von 17 mm, und der Befund meldete die Breite der Linie statt des Umrisses.
    """
    with_helper_line = (
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 210 210">'
        b'<path d="M10,10 L90,10 L90,90 L10,90 Z"/>'
        b'<path d="M10,150 L200,150"/></svg>'
    )

    result = extrude(with_helper_line, ".svg", 5.0, width=40.0)

    assert result.contours == 1, "nur das Quadrat wird ein Körper, die Linie nicht"
    assert result.mesh.bounds.size[0] == pytest.approx(40.0), "das Quadrat, nicht die Zeichnung"
    assert result.width == pytest.approx(80.0), "gemeldet wird die Breite des Körpers"


def test_a_drawing_with_no_closed_area_says_so() -> None:
    open_path = (
        b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"><path d="M0,0 L10,10"/></svg>'
    )

    with pytest.raises(ValidationError) as problem:
        extrude(open_path, ".svg", 2.0)

    assert problem.value.constraint == "no_area"


def test_a_drawing_reaches_the_scene_through_load_outline(profile: Profile) -> None:
    """§25: derselbe Weg hinein wie bei jeder anderen Datei — eine Quelle und
    eine Operation.
    """
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source

    project = new_project("centauri-carbon-2", "petg")
    project.sources["src_1"] = SVG
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/logo.svg", sha256=""
    )
    History(project.document).apply(
        "Zeichnung",
        [OperationDraft(op="load_outline", params={"source": "src_1", "height": 4.0})],
    )

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete
    entry = result.scene.objects["obj_1"]
    assert entry.mesh.bounds.size[2] == pytest.approx(4.0)
    assert "ingest.extruded" in {finding.code for finding in result.scene.report.findings}


def test_only_flat_formats_go_this_way() -> None:
    assert is_outline(".SVG") and is_outline(".dxf")
    assert not is_outline(".stl")

    with pytest.raises(ValidationError):
        extrude(SVG, ".stl", 2.0)


# --- das Register ---------------------------------------------------------------


def test_every_category_of_the_plan_has_something_in_it() -> None:
    """§25 zählt auf, was die Anwendung kann; eine leere Kategorie ist eine
    Lücke.
    """
    filled = {spec.category for spec in REGISTRY.all()}
    for category in ("transform", "mesh", "prepare", "holes", "label", "import", "colour"):
        assert category in filled, category


# --- Eine Szene, mehr als ein Material (§12) -------------------------------------


def test_a_body_can_be_given_its_own_material(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Dichtung", mesh=block())

    result = run("set_material", entry, profile, material="tpu-95a")

    assert result.outputs[0].material == "tpu-95a"
    assert result.findings and result.findings[0].code == "prepare.material"


def test_an_empty_material_puts_the_body_back_on_the_project(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Dichtung", mesh=block(), material="tpu-95a")

    result = run("set_material", entry, profile, material="")

    assert result.outputs[0].material is None
    assert result.findings == [], "back to normal is not worth a line in the report"


def test_an_unknown_material_says_which_ones_there_are(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Dichtung", mesh=block())

    with pytest.raises(ValidationError) as problem:
        run("set_material", entry, profile, material="gummiband")

    assert "petg" in problem.value.values["known"]


def test_the_elephant_foot_follows_the_body_not_the_project(profile: Profile) -> None:
    """§12: TPU quetscht 0,25 mm in seine erste Schicht, PETG 0,2.

    Mit dem Projektmaterial gerechnet kommt eine TPU-Dichtung ringsum 0,05 mm
    zu breit heraus — bei einer Dichtung ist das der Unterschied zwischen
    dichten und nicht dichten.
    """
    plain = run("compensate_first_layer", SceneObject(id="obj_1", name="A", mesh=block()), profile)
    soft = run(
        "compensate_first_layer",
        SceneObject(id="obj_1", name="B", mesh=block(), material="tpu-95a"),
        profile,
    )

    assert soft.outputs[0].mesh.volume < plain.outputs[0].mesh.volume, "TPU is pulled in further"


def test_a_simplification_that_changed_nothing_says_so() -> None:
    """Der Kunde verlangte 400 Dreiecke und bekam 992 — ohne ein Wort dazu.

    Gemessen an ``weg1-halterung-anpassen``: 992 Dreiecke hinein, 992 heraus,
    und zwar bei jedem Ziel von 900 bis 400. Das Netz ist dabei in Ordnung —
    wasserdicht, eine Komponente, keine entarteten Dreiecke, Euler-Zahl minus
    acht: ein CAD-Teil mit fünf Durchbrüchen, das bereits minimal trianguliert
    ist. Jede Kante trennt dort zwei Ebenen, und eine solche zusammenzuziehen
    hieße, die Form zu ändern; dieselbe Rechnung trifft an Kugel und Quader
    jedes Ziel exakt.

    Im Prüfbericht stand dazu „Die Fläche hat sich dabei kaum verschoben" —
    zutreffend und vollkommen nebensächlich. Im Verlauf ein Schritt, im Bild
    dasselbe Teil, und wer das liest, sucht den Fehler bei sich. Genau das
    verbietet die Regel „Eine Operation, die nichts bewirkt hat, sagt das".
    """
    body = trimesh.creation.icosphere(subdivisions=4)
    same = MeshData.of(body)

    findings = mesh_ops._simplification_findings(same, same, 400, "obj_1")

    assert [f.code for f in findings] == ["mesh.not_simplified"], (
        f"ein Lauf ohne jede Wirkung blieb stumm: {[f.code for f in findings]}"
    )
    assert findings[0].values["target"] == 400
    assert findings[0].values["after"] == same.triangle_count


def test_a_simplification_that_worked_stays_quiet() -> None:
    """Und die Gegenrichtung, ohne die der Test oben nichts wert wäre.

    Ein Befund, der bei jedem Lauf erscheint, wird nach dem dritten Mal
    übersehen — und nimmt die daneben mit. Gemeldet wird deshalb nur, wo
    **gar nichts** geschah: Die Quadrik-Dezimierung landet regelmäßig ein paar
    Dreiecke neben der Vorgabe, und das ist kein Befund, sondern das Verfahren.
    """
    body = trimesh.creation.icosphere(subdivisions=4)
    before = MeshData.of(body)
    after = mesh_ops.decimate(before, 1000)

    assert after.triangle_count < before.triangle_count, "hier soll es gewirkt haben"
    assert mesh_ops._simplification_findings(before, after, 1000, "obj_1") == []

    # Und knapp daneben ist immer noch gewirkt.
    knapp = mesh_ops.decimate(before, before.triangle_count - 2)
    assert mesh_ops._simplification_findings(before, knapp, before.triangle_count - 2, "o") == []


def test_a_simplification_that_missed_its_target_by_far_says_so() -> None:
    """Und der Fall dazwischen, den beide Tests darüber durchließen.

    Die Schwelle fragte, **wie viel reduziert** wurde, und gemeint war, **wie
    weit am Ziel vorbei**. Das sind verschiedene Achsen, und bei einem Körper
    mit Durchgangsloch fallen sie auseinander: Ein Rohr aus 131 072 Dreiecken
    kommt bei jedem Ziel zwischen 20 000 und 600 mit **74 592** heraus — um 43
    Prozent reduziert, also weit unter den fünf Prozent, ab denen gemeldet
    wurde, und dabei das 124-Fache der verlangten Zahl.

    Der Kunde stellte 600 ein, bekam 74 592 und erfuhr nichts. Wer 400
    verlangte und 992 bekam, wurde gewarnt — je weiter das Ziel verfehlt war,
    desto seltener meldete es sich.

    **Die Topologie entscheidet, und es ist der Alltagsfall.** Gemessen:
    Euler-Zahl 2 (Kugel, Quader) trifft jedes Ziel exakt; Euler-Zahl 0 — ein
    Körper mit Durchgangsloch, also jede Hülse, jeder Ring, jedes Gehäuse mit
    Durchbruch — bleibt stehen, ohne entartete Dreiecke und ohne offene Kante.
    """
    outer = trimesh.creation.cylinder(radius=15.0, height=30.0, sections=256)
    inner = trimesh.creation.cylinder(radius=14.4, height=36.0, sections=256)
    tube = trimesh.boolean.difference([outer, inner])
    for _ in range(3):
        tube = tube.subdivide()

    before = MeshData.of(tube)
    assert before.raw.euler_number == 0, "der Fall lebt vom Durchgangsloch"
    after = mesh_ops.decimate(before, 600)

    assert after.triangle_count > 600 * 10, (
        f"ohne verfehltes Ziel prüft dieser Test nichts: {after.triangle_count}"
    )
    assert after.triangle_count < before.triangle_count * 0.95, (
        "und ohne kräftige Reduktion griffe die alte Schwelle ohnehin"
    )

    findings = mesh_ops._simplification_findings(before, after, 600, "obj_1")

    assert [f.code for f in findings] == ["mesh.not_simplified"], (
        f"das um das 124-Fache verfehlte Ziel blieb stumm: {[f.code for f in findings]}"
    )
    assert findings[0].values["target"] == 600
    assert findings[0].values["after"] == after.triangle_count


def test_the_operation_actually_asks(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die Verdrahtung, nicht die Rechnung — der teurere der beiden Fehler.

    Ein Befund, den niemand ruft, ist so still wie keiner. Geprüft wird
    deshalb über die **Operation**, mit einer Vereinfachung, die nichts tut:
    Genau so verhält sich der echte Fall, und genau so lässt er sich ohne ein
    besonderes Netz nachstellen.
    """
    from app.core.registry import REGISTRY

    monkeypatch.setattr(mesh_ops, "decimate", lambda mesh, target: mesh)
    spec = REGISTRY.get("decimate_mesh")
    body = MeshData.of(trimesh.creation.icosphere(subdivisions=4))
    entry = SceneObject(id="obj_1", name="Kugel", mesh=body)
    result = spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(triangles=400),
            profile=profiles.make_profile("centauri-carbon-2", "petg"),
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )

    assert "mesh.not_simplified" in {f.code for f in result.findings}, (
        f"die Operation fragt nicht danach: {sorted(f.code for f in result.findings)}"
    )
