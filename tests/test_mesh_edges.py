"""Die Kanten eines Netzes — als Züge, mit stabilen Schlüsseln.

Der Grund für dieses Gebiet steht in `app/core/geom/edges.py`: Ein
importiertes Modell soll dieselben Werkzeuge annehmen wie ein selbst
gezeichnetes (Entscheidung Robert, 10.09.2026). Verrunden und Fasen setzen
an einer **Kante** an, und ein Netz hat keine — es hat Dreiecke.

Zwei Zusagen tragen das Ganze, und beide stehen hier:

* Derselbe Schlüssel überlebt eine **Neuvernetzung**. Sonst zeigte er nach
  dem nächsten Schritt auf eine andere Kante, und zwar still.
* Derselbe Schlüssel kommt aus **beiden Kernen**. Sonst müsste alles
  darüber — Anklicken, Beschriftung, der Parameter der Operation — die zwei
  Rechenwege auseinanderhalten.
"""

from __future__ import annotations

import math
from typing import Any

import pytest
import trimesh

from app.core.bootstrap import load_operations
from app.core.errors import GeometryError
from app.core.geom.boolean import boolean
from app.core.geom.edges import (
    MIN_ARC_STEPS,
    _arc_steps,
    bead_edges,
    bevel_edges,
    edge_key,
    edges_of,
    named_edges,
    reround,
    round_edges,
    unround,
)
from app.core.geom.edges import (
    wanted as wanted_edges,
)
from app.core.geom.mesh import MeshData
from app.core.geom.repair import remove_hollow_shells
from app.core.knowledge import profiles
from app.core.perceive.features import detect
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import Feature, OpContext, OpResult, Profile, Scene, SceneObject
from app.core.units import MAX_FACET_ANGLE, MAX_FACET_SAG

WIDTH, DEPTH, HEIGHT = 40.0, 30.0, 20.0
RADIUS = 10.0


def block() -> MeshData:
    return MeshData(trimesh.creation.box(extents=(WIDTH, DEPTH, HEIGHT)))


def test_a_box_has_twelve_edges_and_no_more() -> None:
    """Zwölf Kanten, vier je Länge — und jede genau einmal.

    Die Flächendiagonalen sind keine: Dort knickt nichts. Ohne diese
    Unterscheidung bekäme der Kunde achtzehn Kanten an einem Quader, von
    denen sechs im Bild gar nicht zu sehen sind.
    """
    found = edges_of(block())

    assert len(found) == 12
    assert sorted(round(entry.length, 6) for entry in found) == [
        HEIGHT,
        HEIGHT,
        HEIGHT,
        HEIGHT,
        DEPTH,
        DEPTH,
        DEPTH,
        DEPTH,
        WIDTH,
        WIDTH,
        WIDTH,
        WIDTH,
    ]
    assert all(entry.convex for entry in found), "ein Quader hat nur Außenkanten"
    keys = [edge_key(entry) for entry in found]
    assert len(set(keys)) == len(keys), "zwei Kanten teilen keinen Schlüssel"


def test_a_finer_mesh_keeps_the_same_twelve_keys() -> None:
    """Die Zusage, an der alles hängt: Der Schlüssel überlebt die Vernetzung.

    Ein Netz mit 192 Dreiecken zeigt dieselben zwölf Kanten wie eines mit
    zwölf — **wenn** sie verkettet werden. Ohne die Verkettung wären es
    achtundvierzig Segmente, der Kunde sähe zwölf, und jede Verfeinerung
    änderte jeden Schlüssel.
    """
    coarse = trimesh.creation.box(extents=(WIDTH, DEPTH, HEIGHT))
    fine = coarse.subdivide().subdivide()
    assert len(fine.faces) > len(coarse.faces) * 8, "sonst prüft der Test keine Verfeinerung"

    rough = edges_of(MeshData(coarse))
    dense = edges_of(MeshData(fine))

    assert len(dense) == len(rough) == 12
    assert all(len(entry.points) > 2 for entry in dense), "im feinen Netz ist eine Kante ein Zug"
    assert sorted(edge_key(entry) for entry in dense) == sorted(edge_key(entry) for entry in rough)


def test_both_kernels_name_the_same_edge_the_same_way() -> None:
    """Ein Schlüssel, zwei Kerne — sonst gäbe es zwei Kantenauswahlen.

    Der Quader steht in beiden Fällen an derselben Stelle: Der exakte Kern
    setzt ihn auf ``z = 0``, ``trimesh`` zentriert ihn, also wird das Netz um
    die halbe Höhe angehoben. Was dann noch verschieden wäre, läge an der
    Rechnung und nicht an der Lage.
    """
    brep = pytest.importorskip("app.core.brep.edit")
    if not pytest.importorskip("app.core.brep.kernel").available():
        pytest.skip("OpenCASCADE is an optional dependency")

    exact = brep.box(WIDTH, DEPTH, HEIGHT)
    raw = trimesh.creation.box(extents=(WIDTH, DEPTH, HEIGHT))
    raw.apply_translation((0.0, 0.0, HEIGHT / 2.0))

    from_brep = sorted(brep.edge_key(entry) for entry in brep.edges_of(exact))
    from_mesh = sorted(edge_key(entry) for entry in edges_of(MeshData(raw)))

    assert from_brep, "leeres Register des exakten Kerns — dann prüft das nichts"
    assert from_mesh == from_brep

    # **Und der Zylinder ist der Fall, der die beiden auseinandertrieb.**
    # Seine Kanten sind geschlossene Kreise: Der Schwerpunkt liegt auf der
    # Achse, und die Richtung von Anfang zu Ende ist entartet. Zwei Dinge
    # gingen daran schief — ein Mittelpunkt auf halber Weglänge statt im
    # Schwerpunkt, und eine winzige negative Zahl, die sich als „-0.000"
    # schreibt und damit ein anderer Schlüssel ist als „0.000".
    round_exact = brep.cylinder(2.0 * RADIUS, HEIGHT)
    round_raw = trimesh.creation.cylinder(radius=RADIUS, height=HEIGHT, sections=64)
    round_raw.apply_translation((0.0, 0.0, HEIGHT / 2.0))

    circles_brep = sorted(brep.edge_key(entry) for entry in brep.edges_of(round_exact))
    circles_mesh = sorted(edge_key(entry) for entry in edges_of(MeshData(round_raw)))

    assert len(circles_brep) == 2, "ein Zylinder hat zwei Kreiskanten — die Naht zählt nicht"
    assert circles_mesh == circles_brep
    assert not any("-0.000" in key for key in circles_mesh), "eine Null trägt kein Vorzeichen"


def _tube_edges(backend: str, inner: float = 5.0) -> tuple[Any, list[Any]]:
    """Ein Rohr mit konzentrischen Rändern, an beiden Kernen auf dem Bett."""
    if backend == "mesh":
        raw = trimesh.creation.annulus(r_min=inner, r_max=RADIUS, height=HEIGHT, sections=64)
        raw.apply_translation((0.0, 0.0, HEIGHT / 2.0))
        body = MeshData(raw)
        return body, edges_of(body)
    brep = pytest.importorskip("app.core.brep.edit")
    if not pytest.importorskip("app.core.brep.kernel").available():
        pytest.skip("OpenCASCADE is an optional dependency")
    body = brep.cylinder(2.0 * RADIUS, HEIGHT)
    if inner > 0.0:
        body = brep.boolean("difference", [body, brep.cylinder(2.0 * inner, HEIGHT)])
    return body, brep.edges_of(body)


@pytest.mark.parametrize("backend", ["mesh", "brep"])
def test_concentric_rims_have_distinct_stable_keys(backend: str) -> None:
    """Innen- und Außenrand teilen die Mitte, sind aber verschiedene Kanten."""
    _, found = _tube_edges(backend)
    _, again = _tube_edges(backend)
    keys = [edge_key(entry) for entry in found]

    assert len(found) == len(set(keys)) == 4
    assert sorted(keys) == sorted(edge_key(entry) for entry in again)
    for entry, key in zip(found, keys, strict=True):
        selected = named_edges(found, [key])
        assert selected == [entry]


def test_concentric_rim_keys_agree_between_kernels_and_after_subdivision() -> None:
    """Die Ergänzung am Schlüssel erhält die Zusage für Netz und exakten Kreis."""
    mesh, coarse = _tube_edges("mesh")
    _, exact = _tube_edges("brep")
    fine = edges_of(MeshData(mesh.raw.subdivide()))

    keys = sorted(edge_key(entry) for entry in exact)
    assert len(set(keys)) == 4
    assert sorted(edge_key(entry) for entry in coarse) == keys
    assert sorted(edge_key(entry) for entry in fine) == keys


@pytest.mark.parametrize("backend", ["mesh", "brep"])
def test_an_unambiguous_legacy_rim_key_still_selects_its_edge(backend: str) -> None:
    """Ein gespeicherter Zylinderrand bleibt nach der Schlüsselergänzung lesbar."""
    _, found = _tube_edges(backend, inner=0.0)
    selected = wanted_edges(found, "named", [f"e:0.00,0.00,{HEIGHT:.2f}:0.000,0.000,0.000"])

    assert len(selected) == 1
    assert selected[0].middle[2] == pytest.approx(HEIGHT)


@pytest.mark.parametrize("backend", ["mesh", "brep"])
def test_an_ambiguous_legacy_rim_key_stops_before_modifying_a_body(backend: str) -> None:
    """Ein alter Rohrschlüssel verrät nicht, ob innen oder außen gemeint war."""
    _, found = _tube_edges(backend)
    with pytest.raises(GeometryError) as problem:
        wanted_edges(found, "named", [f"e:0.00,0.00,{HEIGHT:.2f}:0.000,0.000,0.000"])

    assert problem.value.suggestions
    assert "nicht eindeutig" in str(problem.value.detail)


def test_a_remaining_key_collision_is_never_resolved_by_iteration_order() -> None:
    """Auch zwei sehr nahe Kanten dürfen bei der Quantisierung nicht verschmelzen."""
    thin = MeshData(trimesh.creation.box(extents=(0.004, 10.0, 10.0)))
    found = edges_of(thin)
    key = edge_key(next(entry for entry in found if entry.upright))

    with pytest.raises(GeometryError) as problem:
        wanted_edges(found, "named", [key])

    assert problem.value.suggestions
    assert "nicht eindeutig" in str(problem.value.detail)


@pytest.mark.parametrize("outer", [False, True], ids=["inner", "outer"])
def test_a_named_rim_chamfer_cuts_the_requested_side_of_a_tube(outer: bool) -> None:
    """Das Volumen der gewählten Ringfase folgt ihrer eigenen Kreisgeometrie."""
    body, found = _tube_edges("brep")
    upper = [entry for entry in found if entry.middle[2] > HEIGHT / 2.0]
    selected = (max if outer else min)(upper, key=lambda entry: entry.length)
    source = SceneObject(id="obj_1", name="Rohr", mesh=body, kind="brep")

    changed = run(
        "chamfer_edges", source, distance=1.0, edges="named", edge_keys=edge_key(selected)
    )
    solid = changed.outputs[0].mesh
    # Integration des Kreisrings über eine 45-Grad-Fase von einem Millimeter:
    # außen π(R d² - d³/3), innen π(r d² + d³/3).
    removed = math.pi * (RADIUS - 1.0 / 3.0 if outer else 5.0 + 1.0 / 3.0)
    assert solid.volume == pytest.approx(body.volume - removed, abs=1e-6)
    assert solid.is_watertight and solid.component_count == 1


@pytest.mark.parametrize("operation", ["fillet_edges", "chamfer_edges", "bead_edges"])
def test_a_warm_legacy_edge_cache_cannot_hide_an_ambiguous_selection(operation: str) -> None:
    """Ein gespeichertes Ergebnis der alten Auswahl überspringt keine neue Prüfung."""
    import dataclasses

    from app.core.registry import Registry
    from app.core.scene import ResultCache, evaluate
    from app.core.types import Document, Operation

    load_operations()
    body, _ = _tube_edges("brep")

    def make_tube(ctx: OpContext) -> OpResult:
        return OpResult(outputs=[SceneObject(id="", name="Rohr", mesh=body, kind="brep")])

    def old_result(ctx: OpContext) -> OpResult:
        # Der alte Lauf hat seine Auswahl bereits gerechnet. Der Inhalt ist
        # für den Cache-Test nebensächlich; die neue Auswahl muss neu laufen.
        return OpResult(outputs=[dataclasses.replace(ctx.inputs[0])])

    source = dataclasses.replace(REGISTRY.get("create_brep_cylinder"), fn=make_tube)
    current = REGISTRY.get(operation)
    previous = dataclasses.replace(current, fn=old_result, cache_version="")
    before, after = Registry(), Registry()
    for registry, editing in ((before, previous), (after, current)):
        registry.register(source)
        registry.register(editing)
    document = Document(
        format_version=1,
        app_version="0.0.1",
        ops=[
            Operation(id=1, op=source.name, inputs=[], outputs=["obj_1"], params={}),
            Operation(
                id=2,
                op=operation,
                inputs=["obj_1"],
                outputs=["obj_1"],
                params={
                    "edges": "named",
                    "edge_keys": f"e:0.00,0.00,{HEIGHT:.2f}:0.000,0.000,0.000",
                },
            ),
        ],
    )
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    cache = ResultCache()

    old = evaluate(document, profile, registry=before, cache=cache)
    assert old.complete and len(cache) == 2
    fresh = evaluate(document, profile, registry=after, cache=cache)

    assert fresh.stopped_at == 2
    assert any("nicht eindeutig" in str(entry.message) for entry in fresh.scene.report.findings)


def test_a_groove_tells_its_inner_edges_from_its_outer_ones() -> None:
    """Konkav oder konvex — daran hängt, wohin eine Verrundung Material bewegt.

    An einer Außenkante geht welches weg, an einer Innenkante kommt welches
    dazu. Der exakte Kern liest das aus der Topologie; am Netz muss es an der
    Kante stehen, sonst rundet eine Nut nach der falschen Seite.
    """
    plate = MeshData(trimesh.creation.box(extents=(WIDTH, DEPTH, 10.0)))
    cutter = trimesh.creation.box(extents=(10.0, DEPTH + 10.0, 4.0))
    cutter.apply_translation((0.0, 0.0, 5.0))
    grooved = boolean("difference", [plate, MeshData(cutter)], quality="fine").mesh

    found = edges_of(grooved)
    inner = [entry for entry in found if not entry.convex]

    assert len(inner) == 2, "eine durchgehende Nut hat zwei Bodenkanten"
    assert all(round(entry.length, 3) == DEPTH for entry in inner)
    assert len(found) - len(inner) > 10, "und ringsum bleiben die Außenkanten"


# --- Verrunden am Netz --------------------------------------------------------

PLATE = 10.0
FILLET = 3.0
GROOVE = 1.5
BEVEL = 2.0
WEDGE_HEIGHT = 12.0

#: Der Zwickel an einer rechtwinkligen Kante, **rund** gerechnet: die
#: Lehrbuchzahl ``R² - ¼πR²``. Was gebaut wird, ist geringfügig mehr — siehe
#: :func:`cross_section`.
ROUND_CROSS_SECTION = FILLET**2 - math.pi * FILLET**2 / 4.0


def grooved_plate() -> MeshData:
    """Eine Platte mit durchgehender Nut — zwei Innenkanten, ringsum Außenkanten."""
    plate = MeshData(trimesh.creation.box(extents=(WIDTH, DEPTH, PLATE)))
    cutter = trimesh.creation.box(extents=(10.0, DEPTH + 10.0, 4.0))
    cutter.apply_translation((0.0, 0.0, PLATE / 2.0))
    return boolean("difference", [plate, MeshData(cutter)], quality="fine").mesh


def cross_section(radius: float = FILLET, inner: float = math.pi / 2.0) -> float:
    """Der Querschnitt des Werkzeugs — als **Vieleck**, nicht als Kreis.

    ``t·R`` ist das Viereck zwischen Kante, den beiden Berührpunkten und dem
    Mittelpunkt (``t = R/tan(θ/2)``); davon geht der Bogenfächer ab. Der Bogen
    ist ein Sehnenzug, also ist der Fächer ein Vieleck aus ``n`` Dreiecken zu
    ``½R²·sin(φ)`` — und nicht der Kreissektor der Lehrbuchformel.

    **Wer gegen die Lehrbuchzahl prüft, prüft nicht das, was gebaut wurde.**
    Bei R = 3 sind das 4,2 % Unterschied, und die stecken nicht in einem
    Fehler, sondern in der Auflösung des Bogens.
    """
    span = math.pi - inner
    steps = _arc_steps(radius, span)
    tangent = radius / math.tan(inner / 2.0)
    return tangent * radius - steps * 0.5 * radius**2 * math.sin(span / steps)


def test_a_rounded_outer_edge_takes_exactly_the_wedge_away() -> None:
    """Was weggeht, ist der Zwickel zwischen den zwei Flächen und dem Bogen.

    **Die Stückzahl steht hier als Zahl**, und das ist Absicht:
    :func:`cross_section` fragt sonst dieselbe Funktion wie der Prüfling, und
    ein zu grober Bogen verschöbe Soll und Ist gemeinsam. Sechs Sehnen auf
    einen Viertelkreis sind es bei R = 3 — nachgerechnet aus der Winkelgrenze
    (``⌈(π/2) / 0,3⌉``), nicht abgelesen.
    """
    assert _arc_steps(FILLET, math.pi / 2.0) == 6, "sonst misst der Test eine andere Auflösung"
    edge = next(entry for entry in edges_of(block()) if entry.upright)

    outcome = round_edges(block(), FILLET, "named", [edge_key(edge)])
    body = outcome.mesh.raw

    assert body.is_watertight, "eine Verrundung darf den Körper nicht öffnen"
    assert body.body_count == 1
    assert body.volume == pytest.approx(WIDTH * DEPTH * HEIGHT - cross_section() * HEIGHT, abs=1e-3)
    assert outcome.solver.strategy == "direct", "eine Verrundung braucht keine Rückfallstufe"


def test_a_rounded_inner_edge_adds_material_without_growing_the_body() -> None:
    """Die Kehle füllt den Hohlraum — und ragt dabei nirgends hinaus.

    **Zwei Fehler stecken in diesem einen Test.** Der erste: Ohne die
    Fallunterscheidung im Zwickel lag das Werkzeug unter dem Nutboden im
    vollen Material, und die Vereinigung legte 0,02 mm³ dazu statt 30 — eine
    Kehle, die nichts tut. Der zweite: Mit dem Überstand, den eine Differenz
    braucht, klebte sie 0,01 mm dicke Grate auf beide Stirnflächen der
    Platte. Beide Male blieb der Körper wasserdicht und sah richtig aus.
    """
    grooved = grooved_plate()
    inner = [entry for entry in edges_of(grooved) if not entry.convex]
    assert len(inner) == 2, "sonst prüft der Test keine Innenkante"
    before = grooved.raw.volume

    outcome = round_edges(grooved, GROOVE, "named", [edge_key(entry) for entry in inner])
    body = outcome.mesh.raw

    assert body.is_watertight
    assert body.volume == pytest.approx(before + 2.0 * cross_section(GROOVE) * DEPTH, abs=1e-3)
    assert body.bounds.tolist() == grooved.raw.bounds.tolist(), "die Kehle liegt innen"


def test_the_same_edge_of_a_finer_mesh_gives_the_same_body() -> None:
    """Die Verkettung trägt bis in die Rechnung.

    Im feinen Netz besteht die Kante aus vier Stücken mit vier Normalenpaaren,
    und der Werkzeugkörper entsteht stückweise. Käme dabei etwas anderes
    heraus als am groben Netz, hinge das Ergebnis an der Vernetzung — und ein
    Kunde, der sein Modell feiner einliest, bekäme eine andere Verrundung.
    """
    coarse = trimesh.creation.box(extents=(WIDTH, DEPTH, HEIGHT))
    fine = MeshData(coarse.subdivide().subdivide())
    edge = next(entry for entry in edges_of(fine) if entry.upright)
    assert len(edge.normals) == 4, "sonst prüft der Test keine Verkettung"

    outcome = round_edges(fine, FILLET, "named", [edge_key(edge)])

    assert outcome.mesh.raw.volume == pytest.approx(
        WIDTH * DEPTH * HEIGHT - cross_section() * HEIGHT, abs=1e-3
    )


def test_no_chord_strays_further_from_the_arc_than_a_facet_may() -> None:
    """Die Feinheit hängt am Radius, nicht an einer festen Zahl.

    Geprüft wird die Zusage selbst: Der Abstand einer Sehne zur Rundung
    (``R·(1 - cos(φ/2))``) bleibt unter :data:`MAX_FACET_SAG`, bei jedem
    Radius. Eine feste Stückzahl hielte sie nur in einem Bereich — bei
    R = 30 mm ließen sechzehn Stücke 0,036 mm stehen, bei R = 0,5 mm rechnete
    sie sechzehnmal für sechs Tausendstel.

    **Und beide Grenzen kommen vor.** Am Viertelkreis entscheidet bis R = 8
    der Winkel und darüber die Abweichung; ``MIN_ARC_STEPS`` greift an keinem
    von beiden — eine 135-Grad-Kante hat einen Bogen von 45 Grad, und dort
    kämen sonst drei Sehnen heraus. Ein Test ohne die stumpfen Winkel ließe
    diese Untergrenze ungeprüft.
    """
    seen = set()
    for radius in (0.02, 0.2, 0.5, 1.0, 3.0, 8.0, 30.0, 100.0):
        for span in (math.pi / 2.0, math.pi / 4.0, 2.0 * math.pi / 3.0):
            steps = _arc_steps(radius, span)
            turn = span / steps
            seen.add(steps == MIN_ARC_STEPS)

            assert steps >= MIN_ARC_STEPS, "unter vier Sehnen ist ein Bogen eine Ecke"
            assert turn <= MAX_FACET_ANGLE + 1e-9, f"R={radius} dreht zu weit je Stück"
            if radius > MAX_FACET_SAG and steps > MIN_ARC_STEPS:
                assert radius * (1.0 - math.cos(turn / 2.0)) <= MAX_FACET_SAG + 1e-9, (
                    f"R={radius} weicht zu weit von der Rundung ab"
                )
    assert seen == {True, False}, "die Untergrenze kam in keinem oder in jedem Fall zum Tragen"


def test_both_kernels_round_the_same_edges_to_the_same_body() -> None:
    """Dieselbe Handlung, zwei Kerne — und der Unterschied ist der Sehnenzug.

    Der exakte Kern trifft das analytische Volumen; das Netz liegt darunter,
    weil seine Sehnen innerhalb der Rundung liegen und deshalb etwas mehr
    wegnehmen. Wie viel, ist keine Frage des Zufalls: Es sind genau die
    Kreisabschnitte unter den Sehnen, und die Schranke dafür ist
    :data:`MAX_FACET_SAG`.
    """
    brep = pytest.importorskip("app.core.brep.edit")
    if not pytest.importorskip("app.core.brep.kernel").available():
        pytest.skip("OpenCASCADE is an optional dependency")

    exact = brep.fillet(brep.box(WIDTH, DEPTH, HEIGHT), FILLET, "vertical")
    raw = trimesh.creation.box(extents=(WIDTH, DEPTH, HEIGHT))
    raw.apply_translation((0.0, 0.0, HEIGHT / 2.0))
    outcome = round_edges(MeshData(raw), FILLET, "vertical")

    assert exact.volume == pytest.approx(
        WIDTH * DEPTH * HEIGHT - 4.0 * ROUND_CROSS_SECTION * HEIGHT, abs=1e-3
    ), "der exakte Kern rundet rund"
    assert outcome.mesh.raw.volume == pytest.approx(
        WIDTH * DEPTH * HEIGHT - 4.0 * cross_section() * HEIGHT, abs=1e-3
    )
    lost = (exact.volume - outcome.mesh.raw.volume) / exact.volume
    assert 0.0 < lost < 0.001, f"der Sehnenzug nimmt {100 * lost:.4f} % zu viel"


def test_a_chamfer_on_a_mesh_is_not_an_approximation_at_all() -> None:
    """Die Fase ist der Fall, in dem die zwei Kerne dasselbe rechnen.

    Eine Rundung muss ein Netz durch Sehnen annähern; eine Fase ist eine
    **Ebene**, und eine Ebene hat ein Netz exakt. Gemessen an vier senkrechten
    Kanten: derselbe Körper auf die letzte Stelle, nicht „nah dran".

    Das ist die Zahl, an der man merkt, wofür der exakte Kern noch da ist —
    und wofür nicht.
    """
    brep = pytest.importorskip("app.core.brep.edit")
    if not pytest.importorskip("app.core.brep.kernel").available():
        pytest.skip("OpenCASCADE is an optional dependency")

    exact = brep.chamfer(brep.box(WIDTH, DEPTH, HEIGHT), BEVEL, "vertical")
    outcome = bevel_edges(block(), BEVEL, "vertical")

    expected = WIDTH * DEPTH * HEIGHT - 4.0 * 0.5 * BEVEL**2 * HEIGHT
    assert exact.volume == pytest.approx(expected, abs=1e-6)
    assert outcome.mesh.raw.volume == pytest.approx(expected, abs=1e-6)
    assert outcome.mesh.raw.is_watertight


def test_a_chamfer_and_a_fillet_take_different_amounts_away() -> None:
    """Der Schalter im Werkzeugbau tut wirklich etwas.

    Beide Handlungen teilen sich bis auf zwei Zeilen denselben Weg, und genau
    deshalb gehört hier eine Zusicherung hin: Ein ``rounded``, das
    versehentlich immer wahr wäre, machte aus jeder Fase eine Verrundung, und
    kein Test würde rot — die Körper sehen beide plausibel aus.

    Bei gleichem Maß nimmt die Fase **mehr** weg als die Rundung: Sie
    schneidet die Ecke gerade ab, wo die Rundung sie stehen lässt.
    """
    edge = next(entry for entry in edges_of(block()) if entry.upright)
    keys = [edge_key(edge)]

    rounded = round_edges(block(), BEVEL, "named", keys).mesh.raw.volume
    bevelled = bevel_edges(block(), BEVEL, "named", keys).mesh.raw.volume

    assert bevelled == pytest.approx(WIDTH * DEPTH * HEIGHT - 0.5 * BEVEL**2 * HEIGHT, abs=1e-6)
    assert rounded == pytest.approx(
        WIDTH * DEPTH * HEIGHT - cross_section(BEVEL) * HEIGHT, abs=1e-3
    )
    assert bevelled < rounded, "die Fase schneidet die Ecke ab, die Rundung lässt sie stehen"


def wedge_block() -> MeshData:
    """Ein Prisma über einem gleichseitigen Dreieck — drei Kanten zu 60 Grad.

    **Der Quader taugt für diese Frage nicht.** An einem rechten Winkel ist
    ``R/tan(θ/2)`` gleich ``R``, und damit sind Fase und Rundung dort an ihrer
    Tangentenlänge nicht zu unterscheiden: Eine Verwechslung der beiden
    Formeln blieb am Quader unsichtbar (gemessen — die Mutation lief grün
    durch). Erst ein spitzer Winkel trennt sie: ``R/tan(30°)`` ist das
    1,73-Fache von ``R``.
    """
    from shapely.geometry import Polygon as ShapelyPolygon

    side = 20.0
    triangle = ShapelyPolygon([(0.0, 0.0), (side, 0.0), (side / 2.0, side * math.sqrt(3) / 2.0)])
    return MeshData(trimesh.creation.extrude_polygon(triangle, height=WEDGE_HEIGHT))


def test_a_sharp_corner_tells_the_two_formulas_apart() -> None:
    """Fase und Rundung an einer 60-Grad-Kante — jede mit ihrer eigenen Zahl.

    Die Fase nimmt jeder Fläche ``d`` weg, ihr Querschnitt ist deshalb
    ``½d²·sin(θ)`` und hängt am Winkel. Die Rundung setzt ihre Berührpunkte
    ``R/tan(θ/2)`` von der Kante entfernt, hier also 1,73·R statt R. Beides
    fällt am rechten Winkel zusammen und hier auseinander.
    """
    keil = wedge_block()
    inner_angle = math.pi / 3.0
    edge = next(entry for entry in edges_of(keil) if entry.upright)
    keys = [edge_key(edge)]
    before = keil.raw.volume

    bevelled = bevel_edges(keil, BEVEL, "named", keys).mesh.raw
    rounded = round_edges(keil, BEVEL, "named", keys).mesh.raw

    assert bevelled.volume == pytest.approx(
        before - 0.5 * BEVEL**2 * math.sin(inner_angle) * WEDGE_HEIGHT, abs=1e-6
    )
    assert rounded.volume == pytest.approx(
        before - cross_section(BEVEL, inner_angle) * WEDGE_HEIGHT, abs=1e-3
    )
    assert bevelled.is_watertight and rounded.is_watertight
    assert rounded.volume < bevelled.volume, (
        "am spitzen Winkel nimmt die Rundung mehr weg als die Fase — anders als am rechten"
    )


# --- Als Operation, wie der Kunde sie fährt -----------------------------------


def run(op: str, entry: SceneObject, profile: Profile | None = None, **params: Any) -> OpResult:
    """Eine Operation so fahren, wie die Auswertung sie fährt."""
    load_operations()
    spec = REGISTRY.get(op)
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def imported(mesh: MeshData | None = None) -> SceneObject:
    """Ein Körper, wie er aus einer STL-Datei kommt: ein Netz, kein ``kind``."""
    return SceneObject(id="obj_1", name="Import", mesh=mesh if mesh is not None else block())


def test_the_menu_entry_works_on_an_imported_mesh() -> None:
    """Der Punkt der ganzen Übung — Robert, 10.09.2026.

    Bis dahin trug ``fillet_edges`` ein ``requires_kind="brep"``: Wer ein STL
    einlas, fand *Verrunden* ausgegraut. Jetzt läuft dieselbe Menüzeile, und
    der Körper bleibt ein Netz — der Rechenweg wechselt, nicht die Handlung.
    """
    result = run("fillet_edges", imported(), radius=FILLET, edges="vertical")
    body = result.outputs[0]

    assert body.kind == "mesh", "aus einem Netz wird kein exakter Körper (§30)"
    assert body.mesh.volume == pytest.approx(
        WIDTH * DEPTH * HEIGHT - 4.0 * cross_section() * HEIGHT, abs=1e-3
    )
    assert result.solver is not None, "welche Rückfallstufe gerechnet hat, gehört in den Bericht"
    assert result.solver.strategy == "direct"
    assert not result.findings


def test_the_same_entry_still_takes_an_exact_body() -> None:
    """Und der exakte Weg bleibt der exakte Weg.

    Dieselbe Operation, derselbe Parameter, ein Körper der Art ``brep`` — und
    das Ergebnis ist die runde Rundung, nicht der Sehnenzug. Ohne diesen Test
    könnte die Verzweigung stillschweigend immer am Netz rechnen, und das
    Ergebnis sähe richtig aus.
    """
    brep = pytest.importorskip("app.core.brep.edit")
    if not pytest.importorskip("app.core.brep.kernel").available():
        pytest.skip("OpenCASCADE is an optional dependency")

    entry = SceneObject(id="obj_1", name="Block", mesh=brep.box(WIDTH, DEPTH, HEIGHT), kind="brep")

    result = run("fillet_edges", entry, radius=FILLET, edges="vertical")
    body = result.outputs[0]

    assert body.kind == "brep", "ein exakter Körper bleibt exakt"
    assert body.mesh.volume == pytest.approx(
        WIDTH * DEPTH * HEIGHT - 4.0 * ROUND_CROSS_SECTION * HEIGHT, abs=1e-3
    )


def test_a_fillet_too_small_to_print_says_so() -> None:
    """Ein Schritt im Verlauf und ein unverändertes Teil — dazwischen ein Satz.

    Ein Radius von 0,01 mm trägt an einer 20 mm langen Kante 0,002 mm³ ab:
    mehr als ``EPS_GEOM`` und weniger, als je eine Düse legt. Ohne den Befund
    sähe der Kunde einen Schritt, der nichts getan hat, und suchte den Fehler
    an der falschen Stelle (Regel 17, §2.7).

    ``boolean.without_effect`` beantwortet dieselbe Frage mit dem falschen
    Satz — „das Werkzeug liegt neben dem Körper" —, deshalb steht hier ein
    eigener Code.
    """
    profile = profiles.make_profile("centauri-carbon-2", "petg")

    result = run("fillet_edges", imported(), profile, radius=0.01, edges="vertical")

    codes = [entry.code for entry in result.findings]
    assert codes == ["edges.without_effect"], codes
    said = str(result.findings[0].message)
    assert "Radius" in said, "der Satz nennt den Wert, an dem es liegt"
    assert "Werkzeug" not in said, "und nicht den Satz für eine Tasche, die danebenliegt"


def test_a_chamfer_too_small_to_print_says_it_about_the_width() -> None:
    """Und die Fase sagt es über ihre Breite, nicht über einen Radius.

    Zwei Sätze für zwei Handlungen: Eine Fase hat keinen Radius, und wer
    einen sucht, findet im Dialog keinen.
    """
    profile = profiles.make_profile("centauri-carbon-2", "petg")

    result = run("chamfer_edges", imported(), profile, distance=0.01, edges="vertical")

    said = str(result.findings[0].message)
    assert "Breite" in said and "Radius" not in said, said


def test_a_key_that_names_no_edge_is_a_sentence_not_a_silent_pass() -> None:
    """Eine Kante, die ein Schritt davor weggenommen hat (Regel 17).

    Der Schlüssel bleibt in der Projektdatei stehen, die Kante nicht. Was
    dann kommt, ist eine Auskunft mit Weg nach vorn — kein leerer Körper und
    kein Programmfehler.
    """
    with pytest.raises(GeometryError) as problem:
        run(
            "fillet_edges",
            imported(),
            radius=FILLET,
            edges="named",
            edge_keys="e:99.00,99.00,99.00:1.000,0.000,0.000",
        )

    assert problem.value.suggestions, "Regel 17: nie ohne Handlungsvorschlag"
    assert "nicht mehr" in str(problem.value.detail)


def test_a_group_choice_ignores_an_older_single_pick_on_a_mesh() -> None:
    """Der Umschalter entscheidet, nicht ein Wert, der noch dasteht (E4).

    Dieselbe Zusage wie am exakten Kern (``test_brep.py``) — und sie muss hier
    eigens stehen: Der Leser der Kantenliste ist mit den Operationen nach
    ``geom.edge_ops`` umgezogen, und ein Umzug ist die Gelegenheit, bei der
    eine Bedingung still verlorengeht.
    """
    edge = edge_key(next(entry for entry in edges_of(block()) if entry.upright))

    group = run("fillet_edges", imported(), radius=FILLET, edges="vertical", edge_keys=edge)
    single = run("fillet_edges", imported(), radius=FILLET, edges="named", edge_keys=edge)

    assert group.outputs[0].mesh.volume == pytest.approx(
        WIDTH * DEPTH * HEIGHT - 4.0 * cross_section() * HEIGHT, abs=1e-3
    ), "die Gruppe nimmt alle vier — der stehengebliebene Wert zählt nicht"
    assert single.outputs[0].mesh.volume == pytest.approx(
        WIDTH * DEPTH * HEIGHT - cross_section() * HEIGHT, abs=1e-3
    )


def test_rounding_twice_leaves_one_body_and_not_three() -> None:
    """Der zweite Zug läuft über die Facetten des ersten — und darf nichts zurücklassen.

    Wer die senkrechten Kanten einer Platte verrundet und danach die Oberkante,
    schickt das Werkzeug über eine schon facettierte Fläche. Dort bleiben
    Flächenpaare **ohne Dicke** stehen: gemessen zwei Häute zu vier Dreiecken
    an zwei diagonal gegenüberliegenden Ecken, 0,9485 mm² Fläche, Volumen null.

    **Das sah in jeder anderen Hinsicht richtig aus** — der Körper war
    wasserdicht und trug sein exaktes Volumen. Nur ``body_count`` sagte drei,
    und das meldet der Prüfbericht dem Kunden als zerfallenen Körper. Weder
    `remove_degenerate_faces` (die Dreiecke sind nicht entartet) noch
    `remove_small_components` (die Fläche ist nicht klein) fassen den Fall;
    was ihn fasst, ist `remove_hollow_shells` — es misst das Volumen.
    """
    first = round_edges(block(), FILLET, "vertical").mesh
    assert first.raw.body_count == 1, "sonst prüft der zweite Zug schon etwas Kaputtes"

    second = round_edges(first, 1.0, "top")
    third = round_edges(second.mesh, 1.0, "bottom")

    for name, outcome in (("oben", second), ("unten", third)):
        body = outcome.mesh.raw
        assert body.body_count == 1, f"{name}: {body.body_count} Teile statt einem"
        assert body.is_watertight, name
    assert third.mesh.raw.volume < second.mesh.raw.volume < first.raw.volume


def test_a_shell_without_thickness_goes_and_a_small_part_stays() -> None:
    """Was die Bereinigung wirft, und was sie stehen lässt.

    Die Grenze ist das **Volumen** und nicht die Größe, und der Datensatz ist
    eigens so gebaut, dass die Fläche die *falsche* Antwort gäbe: Die Haut ist
    mit 100 mm² die größere von beiden, das echte Bauteil daneben misst
    1,5 mm². Wer nach Fläche entscheidet — mit einer Schranke wie mit einem
    Anteil an der größten Komponente, so wie `remove_small_components` — wirft
    das Bauteil und behält die Haut.

    **Der erste Anlauf hatte genau diesen Fehler im Testkörper**: eine Haut von
    0,95 mm² neben einem Würfel von 6 mm², und damit gaben beide Kriterien
    dasselbe Ergebnis. Die Mutation „miss die Fläche" lief grün durch.
    """
    body = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    crumb = trimesh.creation.box(extents=(0.5, 0.5, 0.5))
    crumb.apply_translation((20.0, 0.0, 0.0))
    skin = trimesh.Trimesh(
        vertices=[[0.0, 0.0, 30.0], [10.0, 0.0, 30.0], [0.0, 10.0, 30.0]],
        faces=[[0, 1, 2], [0, 2, 1]],
        process=False,
    )
    together = MeshData(trimesh.util.concatenate([body, crumb, skin]))
    assert together.raw.body_count == 3, "sonst prüft der Test die falsche Ausgangslage"
    assert float(skin.area) > float(crumb.area), "sonst entscheidet die Fläche genauso"

    cleaned, dropped = remove_hollow_shells(together)

    assert dropped == 1
    assert cleaned.raw.body_count == 2, "die Krume bleibt — sie hat ein Volumen"
    assert cleaned.raw.volume == pytest.approx(1000.125, abs=1e-6)


# --- Eine erkannte Rundung ändern und wegnehmen -------------------------------


def rounded_block(radius: float = FILLET) -> MeshData:
    """Ein Quader mit vier verrundeten senkrechten Kanten."""
    return round_edges(block(), radius, "vertical").mesh


def fillets_of(mesh: MeshData) -> list[Feature]:
    return [entry for entry in detect(mesh).values() if entry.kind == "fillet"]


def test_taking_a_fillet_away_gives_the_sharp_block_back_exactly() -> None:
    """Die Probe aufs Ganze: verrunden, zurücknehmen, und der Quader ist wieder da.

    **Die Kante wird über den Schnitt der zwei Nachbarebenen zurückgerechnet
    und nicht über den Radius.** Der erkannte Radius stammt aus einem
    Sehnenzug — gemessen 2,9772 an einer Rundung, die mit 3,0 gebaut wurde —,
    und die daraus gerechnete Kante läge 0,023 mm neben der wirklichen.

    **Und der Füllkörper bekommt keinen Überstand.** Er wird *vereinigt*; was
    über das Kantenende hinausragt, klebt außen an. Mit dem Überstand, den
    eine Differenz braucht, stand der Quader danach 20,04 mm hoch und trug
    24000,72 mm³. Die Bedingung dafür hängt seitdem an der Booleschen
    Richtung und nicht mehr an ``convex``.
    """
    body = rounded_block()
    assert body.raw.volume < WIDTH * DEPTH * HEIGHT, "sonst wurde gar nicht verrundet"

    for _ in range(len(fillets_of(body)) + 1):
        found = fillets_of(body)
        if not found:
            break
        body = MeshData(unround(body, found[0]).mesh.raw)

    assert not fillets_of(body), "am Ende ist keine Rundung mehr da"
    assert body.raw.volume == pytest.approx(WIDTH * DEPTH * HEIGHT, abs=1e-4)
    assert body.raw.is_watertight and body.raw.body_count == 1
    assert body.raw.bounds[1][2] == pytest.approx(HEIGHT / 2.0, abs=1e-4), "und kein Grat oben"


def test_changing_a_radius_is_taking_away_and_rounding_again() -> None:
    """Größer und kleiner, beide Male auf die vierte Stelle.

    Gerechnet gegen die Vieleckfläche der jeweiligen Auflösung: Der neue
    Radius bekommt seine eigene Stückzahl, und drei Ecken behalten die alte.
    """
    body = rounded_block()
    chosen = fillets_of(body)[0]

    for wanted in (5.0, 1.0):
        changed = reround(body, chosen, wanted).mesh.raw
        expected = (
            WIDTH * DEPTH * HEIGHT
            - 3.0 * cross_section(FILLET) * HEIGHT
            - cross_section(wanted) * HEIGHT
        )

        assert changed.volume == pytest.approx(expected, abs=1e-3), f"R{wanted}"
        assert changed.is_watertight and changed.body_count == 1


@pytest.mark.parametrize("radius", [1.0, 5.0], ids=["smaller", "larger"])
def test_changing_a_mesh_radius_keeps_the_materials_on_unchanged_faces(radius: float) -> None:
    """Zwei eingefärbte Seiten behalten beim Ändern einer Rundung ihr Filament.

    Geprüft wird die Zuweisung an erhaltenen Flächen. Neu entstandene
    Schnittflächen dürfen weiterhin den Schnittslot der Booleschen Op tragen.
    """
    body = rounded_block()
    slots = tuple(3 if centre[0] > 0.0 else 2 for centre in body.raw.triangles_center)
    painted = MeshData(body.raw, slots=slots)
    features = detect(painted)
    chosen = next(
        feature
        for feature in features.values()
        if feature.kind == "fillet"
        and feature.params["centre"][0] > 0.0
        and feature.params["centre"][1] > 0.0
    )
    source = SceneObject(id="obj_1", name="Zweifarbig", mesh=painted, features=features)

    changed = run("resize_feature", source, at_feature=chosen.id, diameter=2.0 * radius).outputs[0]

    assert isinstance(changed.mesh, MeshData)
    assert len(changed.mesh.slots) == changed.mesh.triangle_count
    for side, slot in ((-1.0, 2), (1.0, 3)):
        retained = [
            index
            for index, centre in enumerate(changed.mesh.raw.triangles_center)
            if math.isclose(centre[0], side * WIDTH / 2.0, abs_tol=1e-6) and centre[1] < 0.0
        ]
        assert retained, "die unveränderte Seitenfläche muss noch vorhanden sein"
        assert all(changed.mesh.slots[index] == slot for index in retained)
    assert painted.slots == slots, "die Eingabe bleibt unverändert"
    assert changed.mesh.is_watertight and changed.mesh.component_count == 1
    assert changed.mesh.volume == pytest.approx(
        WIDTH * DEPTH * HEIGHT - (3.0 * cross_section(FILLET) + cross_section(radius)) * HEIGHT,
        abs=1e-3,
    )


def test_a_fillet_next_to_parallel_faces_is_a_sentence() -> None:
    """Wo keine zwei Ebenen zusammenstoßen, gibt es keine Kante darunter.

    Eine Rundung an einer Zylinderkante hätte diese Lage; der Satz nennt sie,
    statt einen Körper zu liefern, den niemand bestellt hat (Regel 17).
    """
    body = rounded_block()
    chosen = fillets_of(body)[0]
    misplaced = Feature(
        id=chosen.id,
        kind="fillet",
        provenance=chosen.provenance,
        params={**chosen.params, "axis": (1.0, 0.0, 0.0)},
        face_indices=chosen.face_indices,
    )

    with pytest.raises(GeometryError) as problem:
        unround(body, misplaced)

    assert problem.value.suggestions, "Regel 17: nie ohne Handlungsvorschlag"


def test_both_kernels_take_the_same_fillet_away() -> None:
    """Beide Kerne stellen denselben Quader wieder her.

    Der exakte nimmt die Rundungsfläche als **Ding**
    (``BRepAlgoAPI_Defeaturing``) und trifft die analytische Zahl; das Netz
    legt den Zwickel dazu und trifft sie ebenso — hier bleibt kein Sehnenzug
    übrig, denn der Füllkörper hat gar keinen Bogen.
    """
    brep = pytest.importorskip("app.core.brep.edit")
    if not pytest.importorskip("app.core.brep.kernel").available():
        pytest.skip("OpenCASCADE is an optional dependency")

    exact = brep.fillet(brep.box(WIDTH, DEPTH, HEIGHT), FILLET, "vertical")
    for spot in ((-17.0, -12.0, 0.0), (-17.0, 12.0, 0.0), (17.0, -12.0, 0.0), (17.0, 12.0, 0.0)):
        exact = brep.unround(exact, spot, FILLET)

    assert exact.volume == pytest.approx(WIDTH * DEPTH * HEIGHT, abs=1e-6)


def test_the_exact_kernel_changes_a_radius_without_becoming_a_mesh() -> None:
    """Und am exakten Körper bleibt die neue Rundung eine Kurve.

    **Das ist der Grund für den eigenen Zweig.** Der Netz-Weg bekäme dort die
    Tessellation und gäbe ein Netz zurück, das sich weiter ``brep`` nennt —
    der Kunde verlöre seine bearbeitbaren Flächen still, mitten in einer
    Handlung, die davon gar nicht spricht.
    """
    brep = pytest.importorskip("app.core.brep.edit")
    if not pytest.importorskip("app.core.brep.kernel").available():
        pytest.skip("OpenCASCADE is an optional dependency")

    exact = brep.fillet(brep.box(WIDTH, DEPTH, HEIGHT), FILLET, "vertical")
    changed = brep.reround(exact, (-17.0, -12.0, 0.0), FILLET, 5.0)

    round_corner = FILLET**2 - math.pi * FILLET**2 / 4.0
    wide_corner = 5.0**2 - math.pi * 5.0**2 / 4.0
    assert changed.volume == pytest.approx(
        WIDTH * DEPTH * HEIGHT - 3.0 * round_corner * HEIGHT - wide_corner * HEIGHT, abs=1e-6
    )


# --- Wulst und Kehlnaht -------------------------------------------------------


def test_a_bead_lays_a_round_rod_on_the_edge() -> None:
    """Die Gegenrichtung: Material kommt dazu, statt wegzugehen.

    Was außerhalb des Körpers vom Stab übrig bleibt, ist an einer
    rechtwinkligen Außenkante ein Dreiviertelkreis. Die Zahl ist die
    facettierte davon — ein Vieleck aus ``_ring_steps``, das
    :data:`MAX_FACET_SAG` einhält.
    """
    body = block()
    edge = next(entry for entry in edges_of(body) if entry.upright)
    radius = 2.0

    outcome = bead_edges(body, radius, "named", [edge_key(edge)])
    beaded = outcome.mesh.raw

    assert beaded.is_watertight and beaded.body_count == 1
    assert beaded.volume > body.raw.volume, "ein Wulst legt Material auf"
    round_rod = 3.0 / 4.0 * math.pi * radius**2 * HEIGHT
    assert beaded.volume == pytest.approx(WIDTH * DEPTH * HEIGHT + round_rod, rel=0.002)
    assert beaded.bounds[0][0] == pytest.approx(-WIDTH / 2.0 - radius, abs=0.03), (
        "und steht um den Radius über — das ist der caveat der Operation"
    )


def test_a_bead_in_an_inner_corner_is_a_weld_and_not_a_smooth_cove() -> None:
    """Der Unterschied, den der erste Entwurf im Docstring falsch versprach.

    An einer Innenkante legt der Wulst den Rundstab ins Eck — eine Kehlnaht.
    Die **glatte Hohlkehle** nimmt dem Winkel dagegen seine Kante und füllt
    nur den Zwickel; dafür gibt es *Verrunden* an derselben Kante. Gemessen an
    einer Nut mit R = 1,5: 104,45 mm³ gegen 28,97 — der Faktor zwischen den
    beiden ist kein Rundungsfehler, sondern die andere Form.
    """
    grooved = grooved_plate()
    inner = [entry for entry in edges_of(grooved) if not entry.convex]
    keys = [edge_key(entry) for entry in inner]
    radius = 1.5
    before = grooved.raw.volume

    weld = bead_edges(grooved, radius, "named", keys).mesh.raw
    cove = round_edges(grooved, radius, "named", keys).mesh.raw

    quarter = math.pi * radius**2 / 4.0 * DEPTH * 2.0
    assert weld.volume - before == pytest.approx(quarter, rel=0.02), "der Viertelkreis je Kante"
    assert cove.volume - before == pytest.approx(2.0 * cross_section(radius) * DEPTH, abs=1e-3), (
        "die Hohlkehle füllt nur den Zwickel"
    )
    assert weld.volume > cove.volume * 1.001, "und die beiden sind nicht dieselbe Handlung"


def test_a_bead_along_a_bent_chain_has_no_gaps_at_the_bends() -> None:
    """Wo ein Zug knickt, lassen zwei Zylinder außen einen Keil frei.

    **Ein unterteilter Quader zeigt das nicht** — dort sind die Stücke einer
    Kante kollinear, sie stoßen stumpf aneinander, und die Mutation „Kugeln
    weg" lief grün durch. Der Fall braucht einen **gebogenen** Zug: Die
    Oberkante eines schon verrundeten Quaders läuft um die vier Rundungen und
    knickt dabei siebenundzwanzigmal um je fünfzehn Grad.

    Gemessen gegen den analytischen Wulst — Dreiviertelkreis mal Länge des
    Zugs. Ohne die Kugeln fehlen 28,95 mm³, also 2,3 %.
    """
    body = rounded_block()
    chain = next(entry for entry in edges_of(body) if entry.middle[2] > 0.0)
    assert len(chain.points) > 20, "sonst prüft der Test keinen gebogenen Zug"
    radius = 2.0
    before = body.raw.volume

    beaded = bead_edges(body, radius, "named", [edge_key(chain)]).mesh.raw

    assert beaded.is_watertight and beaded.body_count == 1
    rod = 0.75 * math.pi * radius**2 * chain.length
    assert beaded.volume - before == pytest.approx(rod, rel=0.01), (
        "an den Knicken darf kein Material fehlen"
    )


def test_taking_one_radius_away_leaves_the_other_alone() -> None:
    """Zwei Radien am selben Körper — und nur der gemeinte verschwindet.

    **Am Körper mit einem einzigen Radius war das nicht zu prüfen.** Die
    Mutation „nimm irgendeine Zylinderfläche" lief dort grün durch, weil alle
    vier Flächen denselben Radius hatten und die nächstgelegene ohnehin die
    richtige war. Erst zwei verschiedene Radien trennen die Auswahl von der
    Nähe.
    """
    brep = pytest.importorskip("app.core.brep.edit")
    if not pytest.importorskip("app.core.brep.kernel").available():
        pytest.skip("OpenCASCADE is an optional dependency")

    solid = brep.box(WIDTH, DEPTH, HEIGHT)
    upright = [entry for entry in brep.edges_of(solid) if entry.upright]
    left = [brep.edge_key(entry) for entry in upright if entry.middle[0] < 0.0]
    right = [brep.edge_key(entry) for entry in upright if entry.middle[0] > 0.0]
    assert len(left) == len(right) == 2, "vier senkrechte Kanten, zwei je Seite"

    mixed = brep.fillet(brep.fillet(solid, 3.0, "named", left), 5.0, "named", right)
    corner = lambda radius: radius**2 - math.pi * radius**2 / 4.0  # noqa: E731
    assert mixed.volume == pytest.approx(
        WIDTH * DEPTH * HEIGHT - 2.0 * corner(3.0) * HEIGHT - 2.0 * corner(5.0) * HEIGHT, abs=1e-6
    ), "sonst steht der Prüfling schon falsch"

    without_small = brep.unround(mixed, (-17.0, -12.0, 0.0), 3.0)
    assert without_small.volume == pytest.approx(mixed.volume + corner(3.0) * HEIGHT, abs=1e-6), (
        "genau eine kleine Rundung ist weg — nicht die große daneben"
    )

    # **Und die Gegenprobe, die den Radiusfilter überhaupt erst prüft:** An
    # derselben Stelle nach einer R5 gefragt, muss die **weiter entfernte**
    # große genommen werden. Ohne den Filter gewänne die nähere R3, und der
    # Kunde bekäme eine Rundung weg, die er nicht gemeint hat.
    wrong_size = brep.unround(mixed, (-17.0, -12.0, 0.0), 5.0)
    assert wrong_size.volume == pytest.approx(mixed.volume + corner(5.0) * HEIGHT, abs=1e-6), (
        "der Radius entscheidet mit, nicht die Nähe allein"
    )


@pytest.mark.parametrize("height", [5.0, 25.0], ids=["lower", "upper"])
@pytest.mark.parametrize("operation", ["remove_feature", "resize_feature"])
def test_coaxial_fillets_are_edited_at_the_selected_height(height: float, operation: str) -> None:
    """Gleicher Radius und gleiche Achse machen zwei Rundungen nicht zu einer.

    Zwei verrundete Platten hängen an einem mittigen Steg zusammen. Nur die
    angeklickte Rundung darf verschwinden oder ihren Radius ändern; die
    zweite liegt zwanzig Millimeter höher beziehungsweise tiefer.
    """
    brep = pytest.importorskip("app.core.brep.edit")
    if not pytest.importorskip("app.core.brep.kernel").available():
        pytest.skip("OpenCASCADE is an optional dependency")
    from app.core.brep.features import features_of
    from app.core.brep.kernel import Solid

    plate = brep.fillet(brep.box(20.0, 20.0, 10.0), 1.0, "vertical")
    solid = brep.boolean(
        "union", [plate, brep.moved(plate, (0.0, 0.0, 20.0)), brep.cylinder(4.0, 30.0)]
    )
    features = features_of(solid)
    chosen = next(
        feature
        for feature in features.values()
        if feature.kind == "fillet"
        and feature.params["centre"][0] > 0.0
        and feature.params["centre"][1] > 0.0
        and math.isclose(feature.params["centre"][2], height)
    )
    source = SceneObject(
        id="obj_1", name="Doppelplatte", mesh=solid, kind="brep", features=features
    )
    params: dict[str, Any] = {"at_feature": chosen.id}
    if operation == "resize_feature":
        params["diameter"] = 4.0

    changed = run(operation, source, **params).outputs[0]
    assert isinstance(changed.mesh, Solid)
    remaining = [entry for entry in features_of(changed.mesh).values() if entry.kind == "fillet"]
    coaxial = sorted(
        (entry.params["centre"][2], entry.params["radius"])
        for entry in remaining
        if entry.params["centre"][0] > 0.0 and entry.params["centre"][1] > 0.0
    )
    expected = [(30.0 - height, 1.0)]
    radius_squared = 0.0
    if operation == "resize_feature":
        expected.append((height, 2.0))
        radius_squared = 4.0
    assert len(remaining) == 6 + len(expected)
    assert len(coaxial) == len(expected)
    for actual, expected_fillet in zip(coaxial, sorted(expected), strict=True):
        assert actual == pytest.approx(expected_fillet, abs=1e-6)
    assert changed.kind == "brep" and changed.mesh.is_watertight
    assert changed.mesh.component_count == 1
    assert changed.mesh.volume == pytest.approx(
        solid.volume + (1.0 - radius_squared) * (1.0 - math.pi / 4.0) * 10.0, abs=1e-6
    )


def test_the_fillet_location_decides_and_not_its_parametric_origin() -> None:
    """Welche Rundung gemeint ist, entscheidet ihre Lage am Körper.

    ``gp_Cylinder.Location()`` ist irgendein Punkt auf der Achse, den die
    Parametrisierung gewählt hat — an einer oberen Rundung liegt er am
    **Rand** der Kante: (-17, -15, 17) bei einer Achse, die in y läuft. Der
    Schwerpunkt, den das Merkmal nennt, liegt dagegen in der Mitte.

    Gemessen an einem oben verrundeten Quader: Vom Merkmalsort (-18,97 | 0 |
    18,85) ist die richtige Achse 2,70 mm entfernt, ihr Ursprung aber 15,2 —
    weiter als der Ursprung der **falschen** Rundung daneben mit 12,2. Wer den
    Ursprung misst, nimmt die falsche weg, und der Kunde sieht eine Kante
    verschwinden, die er nicht angeklickt hat.
    """
    brep = pytest.importorskip("app.core.brep.edit")
    if not pytest.importorskip("app.core.brep.kernel").available():
        pytest.skip("OpenCASCADE is an optional dependency")
    from app.core.brep.features import features_of

    solid = brep.fillet(brep.box(WIDTH, DEPTH, HEIGHT), FILLET, "top")
    before = [entry for entry in features_of(solid).values() if entry.kind == "fillet"]
    assert len(before) == 4, "vier obere Rundungen"
    chosen = min(before, key=lambda entry: entry.params["centre"][0])
    spot = tuple(float(value) for value in chosen.params["centre"])

    without = brep.unround(solid, spot, FILLET)
    after = [entry for entry in features_of(without).values() if entry.kind == "fillet"]

    assert len(after) == 3, "genau eine ist weg"
    assert all(entry.params["centre"][0] > spot[0] + 1.0 for entry in after), (
        "und zwar die an der gewählten Stelle — nicht eine der drei anderen"
    )
