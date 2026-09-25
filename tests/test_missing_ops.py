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
from app.core.units import EPS_GEOM

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


def needle_plate() -> MeshData:
    """Die Lochplatte, viermal unterteilt: 203 776 Dreiecke mit Fächern um jede Bohrung.

    Der Körper, an dem ``fast_simplification`` stillsteht — sein Flip-Schutz
    lehnt jeden Kollaps ab, der ein spitzes Dreieck spitzer macht, und an den
    Fächern um eine Bohrung ist jeder Kollaps so einer (gemessen am 22.09.2026:
    vier Sekunden, 197 458 Dreiecke bleiben).
    """
    mesh = normalise(read_mesh((MESHES / "plate_holes.stl").read_bytes(), ".stl"), "mm").mesh
    raw = mesh.raw
    for _step in range(4):
        vertices, faces = trimesh.remesh.subdivide(raw.vertices, raw.faces)
        raw = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    return MeshData.of(raw)


def test_the_display_decimation_gets_past_a_needle_plate() -> None:
    """Ein Bild von einem CAD-Export darf nicht am Quadrik-Solver hängen bleiben."""
    plate = needle_plate()
    assert plate.triangle_count == 203_776

    small = mesh_ops.decimate_for_display(plate, 600)

    assert small.triangle_count <= 600, "das Ziel eines Vorschaubilds"
    assert small.is_watertight, "der exakte Kern gibt einen geschlossenen Körper zurück"
    assert small.volume == pytest.approx(plate.volume, rel=0.02), "dieselbe Platte"


def test_the_display_decimation_takes_an_open_mesh_too() -> None:
    """Ohne Volumen kein Kern — dann legt das Raster zusammen, und ein Bild kommt trotzdem."""
    ball = trimesh.creation.icosphere(subdivisions=6, radius=40.0)
    keep = ball.triangles_center[:, 2] < 30.0
    open_mesh = trimesh.Trimesh(vertices=ball.vertices, faces=ball.faces[keep], process=False)
    assert not open_mesh.is_watertight
    bowl = MeshData.of(open_mesh)

    small = mesh_ops.decimate_for_display(bowl, 600)

    assert small.triangle_count < bowl.triangle_count // 10
    assert np.allclose(small.bounds.minimum, bowl.bounds.minimum, atol=2.0)
    assert np.allclose(small.bounds.maximum, bowl.bounds.maximum, atol=2.0)


def test_the_display_decimation_carries_the_slots() -> None:
    """§20: Wer für die Anzeige dezimiert, behält die Farben je Dreieck."""
    ball = trimesh.creation.icosphere(subdivisions=5, radius=20.0)
    upper = ball.triangles_center[:, 2] > 0.0
    slotted = MeshData.of(ball, slots=tuple(int(flag) for flag in upper))

    small = mesh_ops.decimate_for_display(slotted, 600)

    assert small.triangle_count <= 600
    assert len(small.slots) == small.triangle_count
    centres = small.raw.triangles_center
    clear = np.abs(centres[:, 2]) > 2.0
    expected = (centres[clear, 2] > 0.0).astype(int)
    assert np.array_equal(np.asarray(small.slots)[clear], expected)


def test_a_thumbnail_never_holds_the_window_on_the_exact_kernel(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein Vorschaubild dezimiert über das Raster, nie über ``manifold3d``.

    Der Kern gibt den Interpreter während ``simplify`` nicht frei, und die
    Bilder des Objektbaums entstehen in einem Arbeiter neben dem Fenster: Am
    Besenhalter aus dem Kundenbestand stand das Fenster nach jeder Operation
    bis zu 0,46 s still (22.09.2026). Das Raster braucht denselben Weg in
    32 ms und gibt den Interpreter frei.
    """
    from app.core import drawing

    def refused(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("ein Vorschaubild darf den exakten Kern nicht fragen")

    monkeypatch.setattr(mesh_ops, "_display_manifold_decimation", refused)
    plate = needle_plate()

    svg = drawing.thumbnail(plate.raw, 20)

    assert svg.startswith("<svg") and "<polygon" in svg, "ein Bild mit Flächen"
    small = mesh_ops.raster_for_display(
        plate, drawing.PREVIEW_FACES, sag=plate.bounds.diagonal / 80
    )
    assert small.triangle_count < plate.triangle_count // 50, "das Bild zeichnet ein paar hundert"
    assert np.allclose(small.bounds.minimum, plate.bounds.minimum, atol=plate.bounds.diagonal / 40)
    assert np.allclose(small.bounds.maximum, plate.bounds.maximum, atol=plate.bounds.diagonal / 40)


def test_a_small_body_is_not_decimated_for_display() -> None:
    body = MeshData.of(trimesh.creation.icosphere(subdivisions=2, radius=20.0))
    assert mesh_ops.decimate_for_display(body, 600) is body


def test_the_fast_decimation_is_the_display_path_and_keeps_a_hole_readable(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """*Dreiecke verringern* mit ``method="fast"`` nimmt den Anzeigeweg (RM-208).

    Die grobe Vorschau verkleinert große Körper damit (Entscheidung Robert,
    23.09.2026): Kern nach Sehnenfehler, dann Raster, ohne Messung. Geprüft
    wird, was die Tabelle der groben Stufe in ``wartezeit.md`` zusagt — die
    Oberfläche bleibt innerhalb des Sehnenfehlers, mit dem beide Kerne
    tessellieren, und eine Bohrung danach bleibt eine Bohrung: Geschlecht
    eins, erkannter Durchmesser, derselbe Abtrag wie am genauen Körper. Und
    es wird nicht gemessen — genau das kostete am Weg der Operation die
    Sekunden.
    """
    from app.core.perceive.features import detect
    from app.core.units import MAX_FACET_SAG

    assert mesh_ops.DecimateParams().method == "measured", "alte Projekte rechnen wie zuvor"
    sphere = MeshData.of(trimesh.creation.icosphere(subdivisions=6, radius=20.0))
    assert sphere.triangle_count == 81_920
    entry = SceneObject(id="obj_1", name="Kugel", mesh=sphere)

    def refused(*_args: object, **_kwargs: object) -> None:
        raise AssertionError("der Anzeigeweg misst nicht und fragt den Solver nicht")

    with monkeypatch.context() as patched:
        patched.setattr(mesh_ops, "deviation", refused)
        patched.setattr(mesh_ops, "_decimate_with_solver", refused)
        result = run("decimate_mesh", entry, profile, triangles=20_000, method="fast")

    coarse = result.outputs[0].mesh
    assert coarse.triangle_count <= 20_000
    assert coarse.is_watertight, "der Kern gibt einen geschlossenen Körper zurück"
    # Beide Richtungen: Der Kern lässt Ecken weg (neue Ecke auf alter
    # Fläche, Abstand null), und die Sehne dazwischen liegt höchstens um den
    # Sehnenfehler innen — gemessen 0,0497 mm.
    assert mesh_ops.deviation(sphere, coarse) <= MAX_FACET_SAG
    assert mesh_ops.deviation(coarse, sphere) <= MAX_FACET_SAG
    assert [finding.code for finding in result.findings] == ["mesh.simplified_unmeasured"]

    drilled = {
        name: run(
            "drill_hole",
            SceneObject(id="obj_1", name="Kugel", mesh=body),
            profile,
            diameter=5.0,
            x=0.0,
            y=0.0,
            z=20.0,
            depth=0.0,
        )
        .outputs[0]
        .mesh
        for name, body in (("exact", sphere), ("coarse", coarse))
    }
    rough = drilled["coarse"]
    assert rough.raw.euler_number == 0, "Geschlecht eins: ein Durchgangsloch"
    assert coarse.volume - rough.volume == pytest.approx(
        sphere.volume - drilled["exact"].volume, rel=0.01
    ), "derselbe Abtrag wie am genauen Körper"
    holes = {
        name: [feature for feature in detect(body).values() if feature.kind == "hole"]
        for name, body in drilled.items()
    }
    assert len(holes["coarse"]) == 1, "die Bohrung wird am groben Körper erkannt"
    assert holes["coarse"][0].params["diameter"] == pytest.approx(
        holes["exact"][0].params["diameter"], abs=0.02
    ), "mit demselben Durchmesser wie am genauen"


def test_the_fast_decimation_leaves_a_small_body_alone(profile: Profile) -> None:
    """Unter dem Ziel gibt es nichts zu verringern — derselbe Befund wie am gemessenen Weg."""
    body = MeshData.of(trimesh.creation.icosphere(subdivisions=2, radius=20.0))
    entry = SceneObject(id="obj_1", name="Kugel", mesh=body)

    result = run("decimate_mesh", entry, profile, triangles=600, method="fast")

    assert result.outputs[0].mesh is body
    assert [finding.code for finding in result.findings] == ["mesh.already_below_target"]


def test_the_raster_keeps_two_triangles_apart_beyond_two_million_corners() -> None:
    """Die Kennung eines Dreiecks im Raster darf nicht überlaufen.

    Das Raster legt Ecken zusammen und nimmt doppelte Dreiecke heraus; dazu
    wurden die drei Ecken als Stellen **einer** Zahl zur Basis der Eckenzahl
    geschrieben. Das hält bis 2²¹ Ecken, dann läuft die 64-Bit-Zahl über, und
    zwei verschiedene Dreiecke tragen dieselbe Kennung: Bei 2²² Ecken sind
    ``(0, 1, 2)`` und ``(0, 1, 2 + 2²⁰)`` modulo 2⁶⁴ gleich, und eines davon
    fiel als „doppelt" aus dem Bild. Ein offenes Netz mit mehreren Millionen
    Ecken ist genau der Fall, für den dieser Weg da ist.
    """
    corners = 2**22
    distinct = np.array([[0, 1, 2], [0, 1, 2 + 2**20]], dtype=np.int64)

    first = mesh_ops._first_of_each_triangle(distinct, corners)

    assert sorted(first.tolist()) == [0, 1], "zwei verschiedene Dreiecke bleiben zwei"

    doubled = np.array([[0, 1, 2], [3, 4, 5], [0, 1, 2]], dtype=np.int64)
    for count in (6, corners):
        kept = mesh_ops._first_of_each_triangle(doubled, count)
        assert sorted(kept.tolist()) == [0, 1], "ein doppeltes Dreieck bleibt einmal"


def test_redundant_corners_go_exactly_before_any_solver_runs() -> None:
    """Das Vorspiel an der Nadelplatte (§25, Netz): 203 776 Dreiecke aus
    unterteilten Fächern, und keine der Ecken beschreibt etwas — sie liegen
    alle auf ebenen Nachbarschaften. Der exakte Kern nimmt sie heraus, ohne
    eine zu bewegen; danach ist das Ziel erreicht, und kein Solver hat die
    Form angefasst. Bis zum 22.09.2026 stand ``fast_simplification`` hier vier
    Sekunden still, und der Rückfall maß danach elf.
    """
    plate = needle_plate()

    reduced, solver, measured = mesh_ops._decimate_with_solver(plate, 5_000)

    assert solver == "exact", "kein Solver, nur das exakte Vorspiel"
    assert reduced.triangle_count < plate.triangle_count // 100
    assert reduced.is_watertight and reduced.component_count == plate.component_count
    assert reduced.volume == pytest.approx(plate.volume, rel=1e-12)
    assert measured == (0.0, 0.0), "gemessen: jede neue Ecke ist eine alte"
    # Und wirklich keine Ecke bewegt: Die neuen Ecken sind eine Teilmenge der alten.
    old_corners = {tuple(row) for row in np.round(plate.raw.vertices, 9).tolist()}
    new_corners = {tuple(row) for row in np.round(reduced.raw.vertices, 9).tolist()}
    assert new_corners <= old_corners


def test_the_prelude_leaves_a_body_alone_that_has_nothing_redundant() -> None:
    """Eine Kugel trägt keine Ecke auf einer ebenen Nachbarschaft — das
    Vorspiel findet nichts und reicht nichts weiter; der erste Solver
    arbeitet wie bisher."""
    ball = MeshData.of(trimesh.creation.icosphere(subdivisions=5, radius=40.0))

    assert mesh_ops._exactly_flattened(ball, None) is None
    reduced, solver, _measured = mesh_ops._decimate_with_solver(ball, 2_000)
    assert solver == "fast_simplification"
    assert reduced.triangle_count <= 2_000


def test_the_operation_falls_back_when_the_quadric_solver_misses_the_target() -> None:
    """``decimate_mesh`` an echten Nadeln: Ein Zylinder aus 2 048 Sektionen
    trägt lange Seitendreiecke, deren Ecken alle etwas beschreiben — das
    Vorspiel findet nichts, der erste Solver bleibt weit über dem Ziel, und
    das gilt als Stillstand, nicht als Ergebnis. Der Kern-Rückfall bringt ihn
    unter das Ziel und misst die Abweichung beidseitig.
    """
    pipe = MeshData.of(trimesh.creation.cylinder(radius=10.0, height=100.0, sections=2048))

    reduced, solver, measured = mesh_ops._decimate_with_solver(pipe, 2_048)

    assert solver == "manifold", "der zweite Solver, weil der erste das Ziel weit verfehlt"
    assert reduced.triangle_count <= 2_048
    assert measured is not None and 0.0 <= measured[0] <= measured[1]
    assert measured[1] <= max(pipe.bounds.diagonal, 1.0) * mesh_ops.DEVIATION_WARN
    assert reduced.is_watertight


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


def test_hollowing_an_open_hull_names_the_hull_and_offers_repair(profile: Profile) -> None:
    """RM-170: An der generierten Figur (Weg 3, nach dem Import nicht
    wasserdicht) scheiterten alle Stufen der Kette, und die Meldung sagte
    „Auch die letzte Rückfallstufe hat kein brauchbares Ergebnis geliefert" —
    wahr, aber ohne den Weg. Nach *Reparieren* geht dieselbe Figur durch.
    Also nennt der Fehler die Hülle und bietet die Reparatur an (Regel 17)."""
    from app.core.errors import REPAIR_AND_RETRY, NotManifoldError
    from app.core.geom.repair import repair

    figure = normalise(
        read_mesh((MESHES / "generated_figure.stl").read_bytes(), ".stl"), "mm", mend=False
    ).mesh
    assert not figure.is_watertight, "die Voraussetzung des Falls"

    with pytest.raises(NotManifoldError) as caught:
        hollow(figure, 2.0)
    assert "nicht geschlossen" in str(caught.value.detail)
    assert caught.value.open_edges > 0
    assert REPAIR_AND_RETRY in caught.value.suggestions
    assert caught.value.__cause__ is not None, "die Kette bleibt die Ursache"

    mended = repair(figure).mesh
    assert mended.is_watertight
    hollowed = hollow(mended, 2.0)
    assert hollowed.mesh.volume < mended.volume, "nach der Reparatur wird ausgehöhlt"


def test_the_hull_is_named_at_every_boolean_of_the_hollowing(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review 14.09.2026: Die Kette kommt an mancher offenen Stelle durch, und
    dann reißt erst der Deckelschnitt oder die Entlüftung — an demselben nicht
    geschlossenen Körper. Dort stand wieder „Auch die letzte Rückfallstufe …";
    jetzt an allen drei Booleschen derselbe Satz (``_the_hull_or_the_chain``),
    und an einer dichten Hülle bleibt die Kette der Grund.

    Drei Zusicherungen: der Helfer selbst an offener und dichter Hülle; der
    Weg über die Entlüftung an der offenen Figur aus dem Korpus, die ersten
    zwei Booleschen bestanden; und über den Syntaxbaum, dass jede Boolesche
    und der Entlüftungsaufruf in ``hollow`` unter diesem Helfer stehen — die
    erste Fassung fing nur die ersten zwei.
    """
    import ast
    import inspect

    from app.core.errors import BooleanFailedError, NotManifoldError
    from app.core.geom import hollow as module
    from app.core.geom.boolean import BooleanOutcome

    failure = BooleanFailedError(detail="Kette")
    box = trimesh.creation.box(extents=(30.0, 30.0, 30.0))
    open_box = MeshData.of(
        trimesh.Trimesh(vertices=box.vertices, faces=box.faces[:-1], process=False)
    )
    assert not open_box.is_watertight, "die Voraussetzung des Falls"
    with pytest.raises(NotManifoldError) as caught:
        module._the_hull_or_the_chain(open_box, failure)
    assert "nicht geschlossen" in str(caught.value.detail)
    assert caught.value.open_edges > 0 and caught.value.__cause__ is failure
    with pytest.raises(BooleanFailedError) as chain:
        module._the_hull_or_the_chain(MeshData.of(box), failure)
    assert chain.value is failure, "an einer dichten Hülle bleibt die Kette der Grund"

    # Der Weg: Hohlraum und Einschluss bestehen, die Entlüftung reißt.
    figure = normalise(
        read_mesh((MESHES / "generated_figure.stl").read_bytes(), ".stl"), "mm", mend=False
    ).mesh
    assert not figure.is_watertight

    def passes(kind: str, meshes: list[MeshData], **kwargs: object) -> BooleanOutcome:
        return BooleanOutcome(mesh=meshes[0], solver=None)

    def rips(*args: object, **kwargs: object) -> object:
        raise failure

    monkeypatch.setattr(module, "boolean", passes)
    monkeypatch.setattr(module, "_vent", rips)
    with pytest.raises(NotManifoldError) as at_the_vent:
        hollow(figure, 2.0, vents=1)
    assert at_the_vent.value.__cause__ is failure

    # Und jede Boolesche des Aushöhlens steht unter dem Helfer — der
    # Deckelschnitt eingeschlossen, den kein Netz aus dem Korpus erreicht.
    #
    # **Gezählt wird nicht bis drei, sondern verglichen.** Die dritte
    # Boolesche steht seit dem 22.09.2026 in ``_enclosed_cavity``, im ``try``
    # gerufen und damit geschützt — eine feste Zahl im Block hätte sie
    # verloren. Gefragt ist ohnehin nicht „wie viele", sondern „jede": Was
    # ``hollow`` und seine Helfer an Booleschen erreichen können, muss unter
    # demselben Satz stehen.
    helpers = {
        node.name: node
        for node in ast.walk(ast.parse(inspect.getsource(module)))
        if isinstance(node, ast.FunctionDef)
    }

    def reached(start: ast.AST, seen: set[str] | None = None) -> list[str]:
        """Die Aufrufe eines Blocks, samt derer in den Helfern, die er ruft."""
        seen = set() if seen is None else seen
        found: list[str] = []
        for call in ast.walk(start):
            if not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name):
                continue
            name = call.func.id
            found.append(name)
            if name in helpers and name not in seen:
                seen.add(name)
                found.extend(reached(helpers[name], seen))
        return found

    tree = ast.parse(inspect.getsource(module.hollow))
    guarded: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Try):
            continue
        handled = any(
            isinstance(call, ast.Call)
            and isinstance(call.func, ast.Name)
            and call.func.id == "_the_hull_or_the_chain"
            for handler in node.handlers
            for call in ast.walk(handler)
        )
        if handled:
            guarded.extend(reached(ast.Module(body=node.body, type_ignores=[])))
    every_call = [name for name in reached(tree) if name in ("boolean", "_vent")]
    assert every_call, "hollow ruft die Kette — sonst prüft dieser Test nichts"
    assert every_call.count("boolean") >= 3, every_call
    assert guarded.count("boolean") == every_call.count("boolean"), (guarded, every_call)
    assert guarded.count("_vent") == every_call.count("_vent") == 1


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


@pytest.mark.parametrize("font", ["Comfortaa", "Dancing Script", "DejaVu Sans"])
@pytest.mark.parametrize("text", ["Mama", "illu", "&%8"])
def test_overlapping_strokes_fill_by_winding_not_by_parity(font: str, text: str) -> None:
    """Eine Schrift füllt nach Umlaufzahl — überlappende Striche bleiben voll.

    Comfortaa und Dancing Script liegen als variable Schriften bei, und deren
    Striche überlappen sich: Die Konturen werden erst beim Zeichnen vereinigt,
    und zwar nach der Umlaufzahl (TrueType, „nonzero"). ``outlines`` füllte bis
    zum 22.09.2026 nach Parität — ein Symmetrische-Differenz-Lauf über alle
    Ringe —, und wo zwei Striche übereinanderlagen, stand danach ein Loch:
    „Mama" in Comfortaa auf 10 mm verlor 2,4 mm², „Hallo Welt" in Dancing
    Script 0,3 mm², und erhaben gedruckt hatten die Buchstaben Schlitze.

    Der Sollwert kommt nicht aus ``outlines``: Die Umlaufzahl wird hier an
    einem Punktraster direkt aus den Konturen der Schrift gerechnet.
    """
    from matplotlib.textpath import TextPath
    from shapely import contains_xy

    from app.core.geom.label_ops import font_properties, outlines

    size = 10.0
    path = TextPath((0.0, 0.0), text, size=size, prop=font_properties(font))
    rings = [np.asarray(ring, dtype=float) for ring in path.to_polygons() if len(ring) >= 4]
    low = np.min([ring.min(axis=0) for ring in rings], axis=0)
    high = np.max([ring.max(axis=0) for ring in rings], axis=0)
    xs, ys = np.meshgrid(
        np.arange(low[0], high[0], 0.04) + 0.013, np.arange(low[1], high[1], 0.04) + 0.017
    )
    px, py = xs.ravel(), ys.ravel()
    winding = np.zeros(len(px), dtype=int)
    for ring in rings:
        start, end = ring[:-1], ring[1:]
        for (x0, y0), (x1, y1) in zip(start, end, strict=True):
            side = (x1 - x0) * (py - y0) - (px - x0) * (y1 - y0)
            winding += ((y0 <= py) & (y1 > py) & (side > 0)).astype(int)
            winding -= ((y0 > py) & (y1 <= py) & (side < 0)).astype(int)
    from shapely.ops import unary_union

    shape = unary_union(outlines(text, size, font))
    near_edge = contains_xy(shape.boundary.buffer(0.03), px, py)
    covered = contains_xy(shape, px, py)
    inside = winding != 0
    assert not np.any(inside & ~covered & ~near_edge), "ein Strich hat ein Loch bekommen"
    assert not np.any(~inside & covered & ~near_edge), "ein Zwischenraum ist gefüllt"


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


def test_lettering_on_a_side_wall_reads_upright(profile: Profile) -> None:
    """Auf der Vorderseite der Beispieldose lag „SOLIDON3D" quer (02.09.2026):
    4,5 mm breit, 35 mm hoch — die Leserichtung auf der Welt-z-Achse, weil
    ``align_vectors`` nur die Normale trifft und die Drehung um sie nicht
    wählt. Eine Zeile liegt waagerecht, ihr Oben zeigt nach oben.
    """
    wall = trimesh.creation.box(extents=(40.0, 4.0, 30.0))
    wall.apply_translation((0.0, 0.0, 15.0))
    entry = SceneObject(id="obj_1", name="Wand", mesh=MeshData.of(wall))
    result = run(
        "label_text",
        entry,
        profile,
        text="ABCDEF",
        size=6.0,
        depth=0.6,
        x=0.0,
        y=-2.0,
        z=15.0,
        nx=0.0,
        ny=-1.0,
        nz=0.0,
    )
    vertices = np.asarray(result.outputs[0].mesh.raw.vertices)
    letters = vertices[vertices[:, 1] < -2.0 - 0.3]  # vor der Wand
    width = letters[:, 0].max() - letters[:, 0].min()
    height = letters[:, 2].max() - letters[:, 2].min()
    assert width > 2.0 * height, f"die Zeile liegt quer: {width:.1f} breit, {height:.1f} hoch"

    # Auf der Decke bleibt es, wie es war: die Zeile entlang x.
    flat = run("label_text", _plate(), profile, text="ABCDEF", size=6.0, depth=0.6, z=4.0)
    top = np.asarray(flat.outputs[0].mesh.raw.vertices)
    top = top[top[:, 2] > 4.0 + 0.3]
    assert (top[:, 0].max() - top[:, 0].min()) > 2.0 * (top[:, 1].max() - top[:, 1].min())


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


def _glyph_area(text: str, size: float, font: str = "DejaVu Sans") -> float:
    """Die Fläche eines Schriftzugs aus den Kurven seiner Glyphen — Green über jedes Stück.

    Unabhängig vom Prüfling: Die Codes des Glyphenpfads werden hier selbst
    gelesen (Strecke, quadratische und kubische Bézier-Kurve), und das
    Linienintegral ½∮(x dy − y dx) ist für ein Polynom mit acht
    Gauß-Legendre-Knoten exakt. Ohne überlappende Konturen (DejaVu) ist die
    nonzero-Füllung der Betrag der Summe.
    """
    import math

    from matplotlib.path import Path as MplPath
    from matplotlib.textpath import TextPath

    from app.core.geom.label_ops import font_properties

    path = TextPath((0.0, 0.0), text, size=size, prop=font_properties(font, "regular"))
    nodes, weights = np.polynomial.legendre.leggauss(8)

    def integral(poles: np.ndarray) -> float:
        degree = len(poles) - 1
        derivative = degree * np.diff(poles, axis=0)
        total = 0.0
        for node, weight in zip(nodes, weights, strict=True):
            t = (node + 1.0) / 2.0
            basis = [
                math.comb(degree, k) * (1 - t) ** (degree - k) * t**k for k in range(degree + 1)
            ]
            slope = [
                math.comb(degree - 1, k) * (1 - t) ** (degree - 1 - k) * t**k for k in range(degree)
            ]
            x, y = np.asarray(basis) @ poles
            dx, dy = np.asarray(slope) @ derivative
            total += 0.25 * (x * dy - y * dx) * weight
        return total

    area = 0.0
    start = last = None
    index = 0
    codes, vertices = path.codes, path.vertices
    while index < len(codes):
        code = codes[index]
        if code == MplPath.MOVETO:
            start = last = vertices[index]
            index += 1
        elif code == MplPath.LINETO:
            area += integral(np.asarray([last, vertices[index]]))
            last = vertices[index]
            index += 1
        elif code == MplPath.CURVE3:
            area += integral(np.asarray([last, *vertices[index : index + 2]]))
            last = vertices[index + 1]
            index += 2
        elif code == MplPath.CURVE4:
            area += integral(np.asarray([last, *vertices[index : index + 3]]))
            last = vertices[index + 2]
            index += 3
        else:
            if last is not None and start is not None:
                area += integral(np.asarray([last, start]))
            last = start
            index += 1
    return abs(area)


@pytest.mark.parametrize("mode", ["raised", "engraved"])
def test_text_on_an_exact_body_stays_exact_and_follows_the_curves(
    mode: str, profile: Profile
) -> None:
    """Text am exakten Körper: der Körper bleibt exakt, die Buchstaben sind die Kurven (P2.8).

    Bis zum 22.09.2026 machte *Text aufbringen* aus jedem exakten Körper ein
    Dreiecksmodell — ein beschriftetes STEP-Teil verlor Flächen, Kanten und
    den STEP-Export. Jetzt ändert sich das Volumen um genau die Fläche der
    Glyphenkurven mal die Tiefe (Sollwert aus Green, unabhängig vom
    Prüfling), auf 10⁻⁹ — ein Vieleck träfe das nicht: „Oo8" hat nur Kurven.
    """
    kernel = pytest.importorskip("app.core.brep.kernel")
    if not kernel.available():
        pytest.skip("ohne OpenCASCADE gibt es den exakten Kern nicht")
    from app.core.brep import edit, step
    from app.core.brep.features import features_of

    box = edit.box(40.0, 20.0, 4.0)
    entry = SceneObject(id="obj_1", name="Platte", mesh=box, kind="brep", features=features_of(box))
    result = run("label_text", entry, profile, text="Oo8", size=8.0, depth=0.6, z=4.0, mode=mode)

    output = result.outputs[0]
    assert output.kind == "brep"
    assert isinstance(output.mesh, kernel.Solid)
    assert output.mesh.is_closed and output.mesh.solid_count == 1
    change = output.mesh.volume - box.volume
    expected = _glyph_area("Oo8", 8.0) * 0.6
    assert abs(change) == pytest.approx(expected, rel=1e-9)
    assert (change > 0) == (mode == "raised")
    height = 4.6 if mode == "raised" else 4.0
    # Die Hülle trägt die Kantentoleranz der Kurvenflächen (10⁻⁷), nicht mehr.
    assert output.mesh.bounds.size[2] == pytest.approx(height, abs=EPS_GEOM)
    assert not result.findings
    assert step.read(step.write(output.mesh)).volume == pytest.approx(output.mesh.volume, rel=1e-9)


def test_exact_text_with_its_own_filament_keeps_the_slot_on_its_faces(profile: Profile) -> None:
    """Erhabene Schrift in einem eigenen Filament: die Buchstabenflächen tragen den Slot."""
    kernel = pytest.importorskip("app.core.brep.kernel")
    if not kernel.available():
        pytest.skip("ohne OpenCASCADE gibt es den exakten Kern nicht")
    from app.core.brep import edit
    from app.core.brep.features import features_of

    box = edit.box(40.0, 20.0, 4.0)
    entry = SceneObject(id="obj_1", name="Platte", mesh=box, kind="brep", features=features_of(box))
    result = run(
        "label_text", entry, profile, text="H", size=8.0, depth=0.6, z=4.0, mode="raised", slot=2
    )

    body = result.outputs[0].mesh
    assert set(body.face_slots) == {0, 2}
    raised = [
        index
        for index in range(body.face_count)
        if body.face_properties(index).centre[2] > 4.0 + 1e-6
    ]
    assert raised and all(body.face_slots[index] == 2 for index in raised)
    assert [(slot.index, str(slot.name)) for slot in result.outputs[0].material_slots] == [
        (0, "Körper"),
        (2, "Beschriftung"),
    ]


def test_exact_engraved_text_carries_its_slot_in_its_walls_and_floor(profile: Profile) -> None:
    """Vertieft trägt die Schrift ihren Slot auch am exakten Körper in den Rillen.

    Am Netz gilt das seit dem 22.09.2026 (``cut_slot``, siehe
    :func:`test_engraved_lettering_carries_its_slot_in_its_walls_and_floor`).
    Beim Zusammenführen der Durchsicht 0.5.0 kam der exakte Weg dazu, und dort
    nahm die exakte Differenz nur die Flächen des Körpers mit: Das Feld
    *Filament* stand wieder ohne Wirkung da — schlechter als vorher, denn bis
    dahin wurde ein exakter Körper vernetzt und bekam die Rillen gefärbt.
    """
    kernel = pytest.importorskip("app.core.brep.kernel")
    if not kernel.available():
        pytest.skip("ohne OpenCASCADE gibt es den exakten Kern nicht")
    from app.core.brep import edit
    from app.core.brep.features import features_of

    box = edit.box(40.0, 20.0, 4.0)
    entry = SceneObject(id="obj_1", name="Platte", mesh=box, kind="brep", features=features_of(box))
    result = run(
        "label_text", entry, profile, text="H", size=8.0, depth=0.6, z=4.0, mode="engraved", slot=2
    )

    body = result.outputs[0].mesh
    assert result.outputs[0].kind == "brep"
    centres = [body.face_properties(index).centre[2] for index in range(body.face_count)]
    floor = [index for index, z in enumerate(centres) if abs(z - 3.4) < 1e-6]
    top = [index for index, z in enumerate(centres) if abs(z - 4.0) < 1e-6]
    walls = [index for index, z in enumerate(centres) if 3.4 + 1e-6 < z < 4.0 - 1e-6]
    assert floor and all(body.face_slots[index] == 2 for index in floor), "der Rillenboden"
    assert walls and all(body.face_slots[index] == 2 for index in walls), "die Rillenwände"
    assert top and all(body.face_slots[index] == 0 for index in top), "die Oberseite bleibt"
    assert [(slot.index, str(slot.name)) for slot in result.outputs[0].material_slots] == [
        (0, "Körper"),
        (2, "Beschriftung"),
    ]


@pytest.mark.parametrize(
    ("font", "text"), [("Comfortaa", "Dancing"), ("Dancing Script", "Solidon")]
)
def test_exact_letters_fill_overlapping_strokes_like_the_font(font: str, text: str) -> None:
    """Überlappende Striche füllen auch exakt — die ebene Faltung nach dem Drehsinn.

    Comfortaa und Dancing Script lassen Konturen einander decken; die Summe der
    Konturflächen zählt die Deckung doppelt (0,7 bis 2,5 % zu viel), die
    gerade-ungerade-Regel gar nicht. ``brep.lettering`` vereinigt im Drehsinn
    der größten Kontur und zieht die gegenläufigen ab. Sollwert: ein Raster
    von 0,02 mm über dicht abgetasteten Kurven (64 Punkte je Kurve), gezählt
    nach der Umlaufzahl — unabhängig vom Prüfling, auf 10⁻³.
    """
    kernel = pytest.importorskip("app.core.brep.kernel")
    if not kernel.available():
        pytest.skip("ohne OpenCASCADE gibt es den exakten Kern nicht")
    import shapely
    from matplotlib.path import Path as MplPath
    from matplotlib.textpath import TextPath
    from shapely.geometry import LinearRing, Polygon

    from app.core.brep import lettering
    from app.core.geom.label_ops import font_properties

    path = TextPath((0.0, 0.0), text, size=10.0, prop=font_properties(font, "regular"))
    rings: list[list[tuple[float, float]]] = []
    current: list[tuple[float, float]] = []
    last = (0.0, 0.0)
    index = 0
    while index < len(path.codes):
        code = path.codes[index]
        if code == MplPath.MOVETO:
            if len(current) >= 3:
                rings.append(current)
            current = [tuple(path.vertices[index])]
            last = current[0]
            index += 1
        elif code == MplPath.LINETO:
            last = tuple(path.vertices[index])
            current.append(last)
            index += 1
        elif code in (MplPath.CURVE3, MplPath.CURVE4):
            count = 2 if code == MplPath.CURVE3 else 3
            poles = np.asarray([last, *path.vertices[index : index + count]])
            degree = len(poles) - 1
            for t in np.linspace(0.0, 1.0, 65)[1:]:
                weights = [
                    math.comb(degree, k) * (1 - t) ** (degree - k) * t**k for k in range(degree + 1)
                ]
                current.append(tuple(np.asarray(weights) @ poles))
            last = current[-1]
            index += count
        else:
            index += 1
    if len(current) >= 3:
        rings.append(current)
    points = np.asarray([point for ring in rings for point in ring])
    step = 0.02
    xs = np.arange(points[:, 0].min(), points[:, 0].max(), step) + step / 2.0
    ys = np.arange(points[:, 1].min(), points[:, 1].max(), step) + step / 2.0
    grid_x, grid_y = np.meshgrid(xs, ys)
    winding = np.zeros(grid_x.shape, dtype=int)
    for ring in rings:
        linear = LinearRing(ring)
        inside = shapely.contains_xy(Polygon(linear).buffer(0), grid_x, grid_y)
        winding += np.where(inside, 1 if linear.is_ccw else -1, 0)
    expected = np.count_nonzero(winding) * step * step

    body = lettering.letters(path, 1.0)

    assert body.is_closed
    assert body.volume == pytest.approx(expected, rel=1e-3)


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
        (1, "Beschriftung"),
    ]


def test_engraved_lettering_carries_its_slot_in_its_walls_and_floor(profile: Profile) -> None:
    """Vertieft trägt die Schrift ihren Slot auf Wänden und Boden der Rillen.

    Das Feld *Filament* stand bei vertiefter Schrift bis zum 22.09.2026 ohne
    Wirkung da: Die Differenz gab den frisch geschnittenen Flächen den Slot
    des Körpers, und die Zahl im Feld ging verloren, ohne dass jemand es
    sagte. Eingefärbte Rillen sind der übliche Weg, eine vertiefte Schrift
    lesbar zu drucken.
    """
    from app.core.geom.attributes import used_slots

    plate = trimesh.creation.box(extents=(40.0, 20.0, 4.0))
    plate.apply_translation((0.0, 0.0, 2.0))
    entry = SceneObject(id="obj_1", name="Deckel", mesh=MeshData.of(plate))

    result = run("label_text", entry, profile, text="RS", size=10.0, z=4.0, slot=2, mode="engraved")

    output = result.outputs[0]
    mesh = output.mesh
    assert used_slots(mesh) == (0, 2)
    centres = mesh.raw.triangles_center
    slots = np.asarray(mesh.slots)
    floor = np.abs(centres[:, 2] - 3.4) < 1e-6
    assert floor.any() and np.all(slots[floor] == 2), "der Boden der Rillen ist in Slot 2"
    top = np.abs(centres[:, 2] - 4.0) < 1e-6
    assert np.all(slots[top] == 0), "die Oberseite bleibt, wie sie war"
    assert [(slot.index, str(slot.name)) for slot in output.material_slots] == [
        (0, "Körper"),
        (2, "Beschriftung"),
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

    # Datei 13 aus dem Nutzerdurchgang verlangte nur zwanzig Prozent weniger:
    # 2878 hinein, Ziel 2302, 2878 heraus. Das Verhältnis 1,25 zum Ziel lag
    # unter der allgemeinen 1,5-Schwelle und ließ einen vollständig wirkungslosen
    # Schritt stumm. Gar keine Wirkung ist unabhängig von diesem Verhältnis.
    target = int(same.triangle_count * 0.8)
    findings = mesh_ops._simplification_findings(same, same, target, "obj_1")

    assert [f.code for f in findings] == ["mesh.not_simplified"], (
        f"ein Lauf ohne jede Wirkung blieb stumm: {[f.code for f in findings]}"
    )
    assert findings[0].values["target"] == target
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
    # Der erste Solver allein, nicht ``decimate``: Seit dem 22.09.2026 gilt
    # ein weit verfehltes Ziel dort als Stillstand, und der zweite Solver
    # bringt das Rohr auf 576. Der Befund darunter gehört zu dem Fall, in dem
    # auch der nicht greift — und der lässt sich am ersten Solver messen.
    after = before.replacing(before.raw.simplify_quadric_decimation(face_count=600))

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

    monkeypatch.setattr(
        mesh_ops,
        "_decimate_with_solver",
        lambda mesh, target, cancelled: (mesh, "fast_simplification", None),
    )
    spec = REGISTRY.get("decimate_mesh")
    body = MeshData.of(trimesh.creation.icosphere(subdivisions=4))
    entry = SceneObject(id="obj_1", name="Kugel", mesh=body)
    target = int(body.triangle_count * 0.8)
    result = spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(triangles=target),
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


def test_a_bold_style_carries_thicker_strokes_at_the_same_height() -> None:
    """Was der Schnitt für den Druck bedeutet, in Zahlen.

    Bis zum 10.09.2026 bot die Beschriftung drei Schriften an — die drei
    Familien, die matplotlib mitbringt. Die **Schnitte** dazu lagen längst im
    selben Paket, vier Dateien je Familie, und niemand kam an sie heran.

    Für den Druck ist das keine Geschmacksfrage: ``MIN_SIZE`` steht bei drei
    Millimetern, weil dünne Striche unter einer Düsenbreite verschmieren. Ein
    fetter Schnitt trägt bei **gleicher Höhe** dickere Striche und bleibt
    lesbar, wo der normale schon zerfällt — gemessen an „ABC 123" auf 10 mm:
    88,59 mm² normal gegen 149,72 fett, also 69 Prozent mehr Material.
    """
    from app.core.geom.label_ops import FONT_STYLES, FONT_STYLES_AVAILABLE, FONTS

    # **Nur die Familien, die mehr als einen Schnitt haben.** Comfortaa und
    # Dancing Script sind variable Schriften und bringen nur ihre
    # Standardinstanz mit; sie stehen deshalb in ``FONT_STYLES_AVAILABLE`` und
    # werden von ``font_properties`` abgewiesen, statt still dasselbe zu
    # liefern. Der eigene Test dazu ist
    # ``test_a_font_with_only_one_cut_says_so_instead_of_silently_giving_the_same``.
    complete = [font for font in FONTS if font not in FONT_STYLES_AVAILABLE]
    assert len(complete) >= 6, f"die statischen Familien fehlen — {complete}"

    for font in complete:
        areas = {
            style: sum(shape.area for shape in outlines("ABC 123", 10.0, font, style))
            for style in FONT_STYLES
        }
        assert areas["bold"] > areas["regular"] * 1.2, (
            f"{font}: fett trägt spürbar mehr Material — {areas}"
        )
        # Kursiv ist geneigt und nicht dicker; die Fläche bleibt in derselben
        # Größenordnung. Ohne diese Zeile wäre der Test auch mit vier gleichen
        # Schnitten grün.
        assert math.isclose(areas["italic"], areas["regular"], rel_tol=0.05), (
            f"{font}: kursiv neigt, es verdickt nicht — {areas}"
        )


def test_a_font_that_is_not_there_says_so_instead_of_quietly_becoming_another() -> None:
    """matplotlib fällt still auf DejaVu Sans zurück — Solidon nicht mehr.

    Gemessen am 10.09.2026: ``FontProperties(family="Arial")`` findet auf
    Windows Arial und auf Mac und Linux nichts; ``findfont`` liefert trotzdem
    ein Ergebnis, nämlich ``DejaVuSans.ttf``, und schreibt eine Zeile auf die
    Fehlerausgabe, die kein Kunde sieht. Ein Projekt sähe damit auf zwei
    Rechnern verschieden aus, ohne dass irgendwo etwas stünde — genau das, wovor
    der Kommentar an ``FONTS`` seit je warnt.

    Solange nur mitgelieferte Familien zur Wahl stehen, kann es nicht
    eintreten. Der Riegel gilt der nächsten mitgelieferten Schrift, die es aus
    einem Paketfehler nicht ins Paket schafft (Regel 21).
    """
    from app.core.errors import ValidationError

    with pytest.raises(ValidationError) as fehler:
        outlines("A", 10.0, "Eine Schrift, die es nicht gibt")

    assert fehler.value.field == "font"
    assert "Eine Schrift, die es nicht gibt" in str(fehler.value.detail)
    assert fehler.value.suggestions, "und ein Weg nach vorn steht dabei (Regel 17)"


def test_a_font_with_only_one_cut_says_so_instead_of_silently_giving_the_same() -> None:
    """Eine variable Schrift bringt nur ihre Standardinstanz mit.

    Comfortaa und Dancing Script kommen als eine Datei mit einer
    Gewichtsachse; matplotlib kann sie nicht instanziieren und nimmt die
    Vorgabe — „fett" liefert dieselben Umrisse, gemeldet nur auf einer
    Fehlerausgabe, die kein Kunde sieht. Gemessen am 10.09.2026 an
    „ABCabc 123" auf 10 mm: bei den sechs statischen Familien wächst die
    mittlere Strichbreite von 0,61–0,84 auf 0,89–1,44 mm, bei diesen beiden
    bleibt sie bei 0,70 beziehungsweise 0,48.

    Der Riegel in ``font_properties`` hätte das nicht gefangen — er prüft die
    **Familie**, und die ist ja da.
    """
    from app.core.errors import ValidationError
    from app.core.geom.label_ops import FONT_STYLES_AVAILABLE

    for font in FONT_STYLES_AVAILABLE:
        for style in ("bold", "italic", "bold_italic"):
            with pytest.raises(ValidationError) as fehler:
                outlines("A", 10.0, font, style)
            assert fehler.value.field == "style", f"{font}/{style}"
            assert font in str(fehler.value.detail)
        # Und der eine, den es gibt, geht.
        assert outlines("A", 10.0, font, "regular")


def test_a_script_face_says_how_tall_it_has_to_be_for_the_nozzle() -> None:
    """Die Untergrenze gilt allen Schriften gleich — die Striche nicht.

    ``MIN_SIZE`` steht bei drei Millimetern und muss für die feinste und die
    gröbste Düse zugleich gelten. Was wirklich trägt, hängt an drei Dingen, die
    das Schema nicht kennt: Schrift, Schnitt und Bahnbreite. Gemessen am
    10.09.2026 an „SOLIDON3D" auf 10 mm — „Dancing Script" 0,51 mm mittlere
    Strichbreite, „DejaVu Sans" 0,90, dieselbe fett 1,57.

    Gemeldet wird die **Zahl**, ab der es trägt, nicht ein „zu dünn" — sonst
    rät der Kunde (Regel 17). Und gerechnet wird gegen die schmalste Bahn und
    nicht gegen die Düse: Ein Slicer quetscht bis auf 0,85 davon.
    """
    from app.core.geom.label_ops import outlines, stroke_width, too_thin_to_print

    def needed_for(font: str, size: float, bead: float, style: str = "regular") -> float | None:
        return too_thin_to_print(outlines("SOLIDON3D", size, font, style), size, bead)

    assert needed_for("DejaVu Sans", 10.0, 0.34) is None, "0,90 mm trägt eine 0,34er Bahn"

    needed = needed_for("Dancing Script", 3.0, 0.34)
    assert needed is not None and needed == pytest.approx(6.6, abs=0.3), needed

    # Eine feinere Düse verschiebt die Grenze — die Zahl gehört ihr und nicht
    # der Schrift.
    assert needed_for("Dancing Script", 6.0, 0.21) is None, "mit 0,21er Bahn trägt sie bei 6 mm"
    assert needed_for("Dancing Script", 6.0, 0.68) is not None, "mit 0,68er nicht"

    # **Und der Schnitt gehört zur Frage.** Eine Tabelle je Familie hätte für
    # fett dieselbe Antwort gegeben wie für normal, obwohl fett rund
    # anderthalbmal so breite Striche trägt.
    # Gemessen: normal trägt eine 0,68er Bahn ab 7,6 mm, fett schon ab 4,3.
    thin = needed_for("DejaVu Sans", 6.0, 0.68)
    thick = needed_for("DejaVu Sans", 6.0, 0.68, style="bold")
    assert thin is not None, "0,54 mm bei 6 mm Höhe trägt keine 0,68er Bahn"
    assert thick is None, "0,94 mm schon — sonst sieht die Prüfung den Schnitt nicht"

    # Die gemessene Breite skaliert linear mit der Höhe; darauf beruht die
    # Umrechnung auf die nötige Größe.
    small = stroke_width(outlines("SOLIDON3D", 5.0, "DejaVu Sans", "regular"))
    large = stroke_width(outlines("SOLIDON3D", 10.0, "DejaVu Sans", "regular"))
    assert large == pytest.approx(2.0 * small, rel=0.02), (small, large)


def test_both_labelling_ops_report_a_face_too_fine_for_the_nozzle(profile: Profile) -> None:
    """Der Anschlusstest: Die **Operation** meldet es, nicht nur die Funktion.

    Beide Wege bringen dieselbe Schrift auf — ``label_text`` auf einen Körper,
    ``create_label`` als eigenes Schild —, und beide gingen bis zum 10.09.2026
    ohne ein Wort durch. Beim Schild wiegt es schwerer: Es hängt an keinem
    Körper, der es hielte.

    Geprüft wird zusätzlich, **was** der Satz rät. „Nehmen Sie den fetten
    Schnitt" ist bei einer variablen Schrift kein Ausweg, sondern der nächste
    Fehler: Sie bringt nur einen mit, und dieselbe Operation lehnt jeden
    anderen ab.
    """
    from app.core.geom.label_ops import FONT_STYLES_AVAILABLE

    plate = block(60.0, 60.0, 5.0)
    body = SceneObject(id="plate", name="Platte", mesh=plate)

    for op, extra in (("label_text", {"z": 5.0}), ("create_label", {})):
        result = run(
            op,
            body if op == "label_text" else None,
            profile,
            text="SOLIDON3D",
            size=3.0,
            font="Dancing Script",
            depth=0.6,
            **extra,
        )
        found = [entry for entry in result.findings if entry.code == "label.too_fine"]
        assert found, f"{op} sagt nichts zu einer Schrift, die keine Bahn trägt"
        said = str(found[0].message)
        assert "fett" not in said.lower(), (
            f"{op} rät zu einem Schnitt, den „Dancing Script“ nicht hat: {said}"
        )
        assert "Dancing Script" in FONT_STYLES_AVAILABLE, "sonst prüft die Zeile darüber nichts"

    # Und bei einer Familie mit fettem Schnitt steht er im Satz.
    result = run(
        "create_label",
        None,
        profile,
        text="SOLIDON3D",
        size=3.0,
        font="DejaVu Sans",
        depth=0.6,
    )
    found = [entry for entry in result.findings if entry.code == "label.too_fine"]
    assert found and "fett" in str(found[0].message).lower(), found

    # Groß genug gesetzt schweigt sie — sonst wäre der Befund kein Befund,
    # sondern eine Eigenschaft der Operation.
    quiet = run(
        "create_label", None, profile, text="SOLIDON3D", size=30.0, font="DejaVu Sans", depth=0.6
    )
    assert not [entry for entry in quiet.findings if entry.code == "label.too_fine"]


def test_a_second_screw_lid_gets_a_number(profile: Profile) -> None:
    """Zwei Objekte mit demselben Namen sind im Baum eines (RM-097).

    *Drehdeckel* und *Prüfstück* trugen ihren Namen als festes Wort. Wer zwei
    Dosen verschloss, fand zwei Zeilen, die gleich heißen, und musste die
    richtige durch Anklicken suchen — die Kopie macht es seit je anders.

    Der Zähler beginnt bei zwei: Der erste heißt, wie er heißt, und „Drehdeckel
    1" neben nichts wäre eine Nummer ohne Reihe.
    """
    from app.core.registry import REGISTRY
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene

    tin = SceneObject(id="obj_1", name="Dose", mesh=hollow(block(), 3.0, open_top=True).mesh)
    schon_da = SceneObject(id="obj_9", name="Drehdeckel", mesh=block())
    spec = REGISTRY.get("screw_lid")
    result = spec.fn(
        OpContext(
            scene=Scene(objects={tin.id: tin, schon_da.id: schon_da}),
            inputs=[tin],
            params=spec.params(),
            profile=profile,
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )

    namen = [str(entry.name) for entry in result.outputs]
    assert "Drehdeckel 2" in namen, f"der zweite Deckel heißt wie der erste: {namen}"


def test_the_screw_lid_name_follows_the_language(profile: Profile) -> None:
    """Der Name des Drehdeckels wandert mit der Sprache — auch mit Zähler.

    ``unused_name`` nahm ein ``str`` und gab eins zurück, also stand
    ``str(_("Drehdeckel"))`` im Ergebnis: das Wort in der Sprache, die beim
    Rechnen eingestellt war, vom Ergebnis-Cache festgehalten. Der Deckel
    daneben (*Deckel erzeugen*) hatte genau das schon abgelegt; der Kommentar
    im Drehdeckel sagte „kein eingefrorenes Wort" über einer Zeile, die eines
    einfror.
    """
    from app.core.registry import REGISTRY
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene
    from app.i18n import SOURCE_LANGUAGE, get_language, set_language
    from app.i18n.catalog import install_language

    tin = SceneObject(id="obj_1", name="Dose", mesh=hollow(block(), 3.0, open_top=True).mesh)
    spec = REGISTRY.get("screw_lid")

    def lid_name(scene_objects: dict[str, SceneObject]) -> object:
        result = spec.fn(
            OpContext(
                scene=Scene(objects=scene_objects),
                inputs=[tin],
                params=spec.params(),
                profile=profile,
                quality="fine",
                seed=None,
                progress=lambda fraction, text: None,
                ask=lambda question, choices: choices[0],
                cancelled=NeverCancelled(),
            )
        )
        return result.outputs[1].name

    install_language("fr")
    vorher = get_language()
    try:
        set_language("fr")
        first = lid_name({tin.id: tin})
        taken = SceneObject(id="obj_9", name=str(first), mesh=block())
        second = lid_name({tin.id: tin, taken.id: taken})
        set_language(SOURCE_LANGUAGE)
        assert str(first) == "Drehdeckel"
        assert str(second) == "Drehdeckel 2"
    finally:
        set_language(vorher)


# --- ein Ziel über der vorhandenen Dreieckszahl ----------------------------------


def test_a_target_above_the_triangle_count_says_there_is_nothing_to_reduce(
    profile: Profile,
) -> None:
    """Das Ziel steht vorbelegt auf 50 000, und die meisten Teile sind kleiner.

    Gemessen am 14.09.2026 über das Fenster: *Dreiecke verringern* an einem
    Körper mit 320 Dreiecken, Vorgabe übernommen, Übernehmen gedrückt — ein
    Schritt im Verlauf, dasselbe Teil im Bild und im Band „am Volumen ändert
    sich nichts". Der Kunde hatte nichts falsch gemacht und konnte trotzdem
    nicht sehen, warum nichts geschah: Sein Körper trägt längst weniger
    Dreiecke, als er verlangt.

    ``_simplification_findings`` kehrte hier leer zurück — dieselbe Antwort
    wie bei einer geglückten Vereinfachung, denn beide Male liegt das Ergebnis
    unter dem Ziel. Die zwei Fälle unterscheidet erst der **Eingang**.
    """
    body = MeshData.of(trimesh.creation.icosphere(subdivisions=2))
    entry = SceneObject(id="obj_1", name="Kugel", mesh=body)
    assert body.triangle_count < 50_000, "sonst prüft dieser Test den anderen Fall"

    result = run("decimate_mesh", entry, profile)

    treffer = [f for f in result.findings if f.code == "mesh.already_below_target"]
    assert treffer, (
        f"ein Ziel über der vorhandenen Zahl blieb stumm: {sorted(f.code for f in result.findings)}"
    )
    assert treffer[0].severity == "info", "schiefgegangen ist nichts"
    assert treffer[0].values["before"] == body.triangle_count
    assert treffer[0].values["target"] == 50_000
    assert "verringern" in str(treffer[0].message), "der Satz nennt, was es nicht zu tun gab"
    assert result.outputs[0].mesh.triangle_count == body.triangle_count


def test_a_target_below_the_triangle_count_keeps_quiet_about_it(profile: Profile) -> None:
    """Die Gegenprobe: Ein Ziel, das etwas zu tun gibt, meldet nichts dergleichen.

    Ohne sie wäre der Test darüber auch mit einem Befund grün, der bei jedem
    Lauf erscheint — und ein Satz, der immer dasteht, wird nach dem dritten Mal
    nicht mehr gelesen.
    """
    body = MeshData.of(trimesh.creation.icosphere(subdivisions=4))
    entry = SceneObject(id="obj_1", name="Kugel", mesh=body)
    assert body.triangle_count > 1000, "das Ziel muss unter der vorhandenen Zahl liegen"

    result = run("decimate_mesh", entry, profile, triangles=1000)

    assert "mesh.already_below_target" not in {f.code for f in result.findings}


@pytest.mark.parametrize(
    ("op", "core", "params"),
    [
        ("smooth_mesh", "smooth", {"iterations": 2}),
        ("remesh_mesh", "remesh", {"edge": 20.0}),
        ("remesh_uniform", "uniform", {"edge": 20.0, "deviation": 0.1}),
        ("subdivide_surface", "subdivided", {"edge": 20.0}),
    ],
)
def test_a_cancelled_mesh_operation_does_not_measure_afterwards(
    profile: Profile, monkeypatch: pytest.MonkeyPatch, op: str, core: str, params: dict
) -> None:
    """Wer während der Rechnung abbricht, wartet nicht noch auf die Messung danach.

    Gemessen am Voronoi-Spiderman (885 570 Dreiecke, 23.09.2026): *Glätten*
    rechnet 0,5 s und misst danach 5,4 s, wie weit die Fläche gewandert ist —
    ohne eine einzige Abbruchfrage. Dasselbe bei *Kanten verfeinern*,
    *Dreiecke angleichen* und *Fläche unterteilen* (25 s für die Rechnung
    allein). Der Knopf „Abbrechen" wirkte erst, wenn alles fertig war.
    """
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    signal = CancelSignal()
    original = getattr(mesh_ops, core)

    def computed_then_cancelled(*args: object, **kwargs: object):
        result = original(*args, **kwargs)
        signal.cancel()
        return result

    monkeypatch.setattr(mesh_ops, core, computed_then_cancelled)
    measured = pytest.fail
    monkeypatch.setattr(
        mesh_ops, "max_distance_to_surface", lambda *_a, **_k: measured("nach dem Abbruch gemessen")
    )
    ball = MeshData.of(trimesh.creation.icosphere(subdivisions=3, radius=20.0))
    entry = SceneObject(id="obj_1", name="Kugel", mesh=ball)
    spec = REGISTRY.get(op)

    with pytest.raises(OperationCancelled):
        spec.fn(
            OpContext(
                scene=Scene(objects={entry.id: entry}),
                inputs=[entry],
                params=spec.params(**params),
                profile=profile,
                quality="fine",
                seed=None,
                progress=lambda fraction, text: None,
                ask=lambda question, choices: choices[0],
                cancelled=signal,
            )
        )


def _two_coloured_sheet() -> MeshData:
    """Eine offene Fläche 40 x 20 mm, links Filament 0, rechts Filament 1."""
    xs = np.linspace(-20.0, 20.0, 5)
    ys = np.linspace(-10.0, 10.0, 3)
    vertices = np.array([(x, y, 0.0) for y in ys for x in xs])
    faces = []
    slots = []
    for row in range(len(ys) - 1):
        for column in range(len(xs) - 1):
            a = row * len(xs) + column
            b, c, d = a + 1, a + len(xs), a + len(xs) + 1
            faces += [(a, b, d), (a, d, c)]
            slots += [int(xs[column] >= 0.0)] * 2
    sheet = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    return MeshData.of(sheet, slots=tuple(slots))


def test_thickening_keeps_the_filaments_and_names_its_body(profile: Profile) -> None:
    """§20: Ein zweifarbiges Schild kam aus *Offene Fläche schließen* einfarbig.

    Außen- und Innenhaut sind dieselben Dreiecke, eine Randwand gehört zu dem
    Dreieck, an dessen Kante sie steht — also liegt jedes Dreieck links der
    Mitte auf Filament 0 und jedes rechts auf Filament 1. Und der Befund nennt
    den Körper, an dem er entstand, wie jeder andere Befund der Netzoperationen.
    """
    entry = SceneObject(id="obj_1", name="Schild", mesh=_two_coloured_sheet())

    result = run("thicken", entry, profile, thickness=2.0)

    body = result.outputs[0].mesh
    assert body.is_watertight
    assert len(body.slots) == body.triangle_count
    centres = np.asarray(body.raw.triangles_center)
    clear = np.abs(centres[:, 0]) > 1e-6
    expected = (centres[clear, 0] > 0.0).astype(int)
    assert np.array_equal(np.asarray(body.slots)[clear], expected)
    assert {finding.object_id for finding in result.findings} == {"obj_1"}


def test_thickening_a_sheet_beside_a_closed_part_leaves_the_part_alone(profile: Profile) -> None:
    """Nur das Blatt bekommt seine Wand; der Würfel daneben keine zweite Innenhaut.

    *Dicke geben* steht auch am Befund „Ein Teil des Modells ist eine Fläche
    ohne Dicke". Die Operation trug bis dahin jede Fläche des Körpers auf, und
    der Würfel neben dem Blatt kam mit einer zweiten, positiven Innenschale
    heraus — 15 057 statt 8 115 mm³ (Review R6, 24.09.2026).
    """
    from app.core.geom.mesh import face_components

    cube = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    sheet = trimesh.Trimesh(
        vertices=[[30.0, 0.0, 0.0], [42.0, 0.0, 0.0], [42.0, 12.0, 0.0], [30.0, 12.0, 0.0]],
        faces=[[0, 1, 2], [0, 2, 3]],
        process=False,
    )
    entry = SceneObject(
        id="obj_1",
        name="Würfel und Blatt",
        mesh=MeshData.of(trimesh.util.concatenate([cube, sheet])),
    )

    body = run("thicken", entry, profile, thickness=0.8).outputs[0].mesh

    assert body.is_watertight
    pieces = face_components(body.raw)
    assert len(pieces) == 2, "ein Würfel und ein Blatt mit Wand — keine dritte Schale"
    assert body.volume == pytest.approx(8000.0 + 12.0 * 12.0 * 0.8, rel=1e-9)
