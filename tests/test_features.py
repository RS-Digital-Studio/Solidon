"""Merkmalserkennung gegen eine Platte mit bekannten Maßen (§21.1, §40).

plate_holes.stl ist 80 x 50 x 8 mm mit vier Bohrungen zu 5,2 mm — jede Zahl,
die die Erkennung erzeugt, lässt sich also prüfen statt bewundern.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import trimesh

from app.core.geom.mesh import MeshData, read_mesh
from app.core.ingest.loader import normalise
from app.core.perceive.features import (
    component_count,
    detect,
    detect_cones,
    detect_edge_loops,
    detect_faces,
    detect_holes,
    detect_pins,
    fit_cylinder,
)

MESHES = Path(__file__).parent / "data" / "meshes"


def plate(name: str = "plate_holes.stl") -> MeshData:
    return normalise(read_mesh((MESHES / name).read_bytes(), ".stl"), "mm").mesh


def cube() -> MeshData:
    return normalise(read_mesh((MESHES / "cube_clean.stl").read_bytes(), ".stl"), "mm").mesh


# --- bores ----------------------------------------------------------------------


def test_all_four_bores_are_found() -> None:
    """§40: plate_holes is recognised completely."""
    holes = detect_holes(plate())

    assert len(holes) == 4
    assert {hole.id for hole in holes} == {"hole_1", "hole_2", "hole_3", "hole_4"}


def test_the_bore_diameter_is_measured_correctly() -> None:
    for hole in detect_holes(plate()):
        assert hole.params["diameter"] == pytest.approx(5.2, abs=0.05)
        assert hole.params["residual"] < 0.02, "a drilled hole fits a cylinder closely"


def test_the_bores_stand_upright_and_go_through() -> None:
    for hole in detect_holes(plate()):
        axis = hole.params["axis"]
        assert abs(abs(axis[2]) - 1.0) < 0.01, "the bores run along Z"
        assert hole.params["through"] is True
        assert hole.params["depth"] == pytest.approx(8.0, abs=0.1)


def test_the_bores_sit_where_they_were_drilled() -> None:
    centres = sorted(
        (round(hole.params["centre"][0], 1), round(hole.params["centre"][1], 1))
        for hole in detect_holes(plate())
    )
    assert centres == [(-25.0, -15.0), (-25.0, 15.0), (25.0, -15.0), (25.0, 15.0)]


def test_the_numbering_is_reproducible() -> None:
    first = {hole.id: hole.params["centre"] for hole in detect_holes(plate())}
    second = {hole.id: hole.params["centre"] for hole in detect_holes(plate())}
    assert first == second


def test_two_coaxial_bores_are_numbered_from_below() -> None:
    """§21.2: Zwei Bohrungen übereinander haben dieselbe Mitte in X und Y.

    Eine Durchführung durch zwei Wände ist die häufigste Doppelbohrung
    überhaupt — und die Sortierung, aus der die Nummern entstehen, verglich
    nur X und Y. Der Vergleich endete unentschieden, und welche von beiden
    ``hole_1`` wurde, hing an der Reihenfolge der gefundenen Flecken. Eine
    Provenienz-ID darf das nicht: Eine Op, die an ``hole_2`` hängt, säße nach
    der nächsten Auswertung an der anderen Bohrung.
    """
    lower = trimesh.creation.box(extents=(30.0, 30.0, 4.0))
    upper = trimesh.creation.box(extents=(30.0, 30.0, 4.0))
    upper.apply_translation((0.0, 0.0, 20.0))
    bore = trimesh.creation.cylinder(radius=2.6, height=60.0, sections=64)
    body = MeshData.of(trimesh.util.concatenate([lower, upper]).difference(bore))

    holes = sorted(detect_holes(body), key=lambda hole: hole.id)

    assert [hole.id for hole in holes] == ["hole_1", "hole_2"]
    heights = [hole.params["centre"][2] for hole in holes]
    assert heights == sorted(heights), f"die untere ist hole_1: {heights}"


def test_a_cube_has_no_bores() -> None:
    assert detect_holes(cube()) == []


def test_a_pin_is_not_reported_as_a_bore() -> None:
    """Die Normalen entscheiden: zur Achse zeigend ist eine Bohrung, von ihr
    weg ein Stift.
    """
    pin = MeshData.of(trimesh.creation.cylinder(radius=4.0, height=20.0, sections=48))
    # Nur die Hülle, ohne die zwei Endkappen — die sind Flächen, kein Zylinder.
    shell = [
        index for index, normal in enumerate(pin.raw.face_normals) if abs(float(normal[2])) < 0.5
    ]
    fit = fit_cylinder(pin.raw, shell)

    assert fit is not None
    assert fit.radius == pytest.approx(4.0, abs=0.05)
    assert not fit.inward, "a cylinder seen from outside is a pin"
    assert detect_holes(pin) == []


def test_a_cylinder_bigger_than_its_body_is_no_feature() -> None:
    """Ein sanft gebogener Arm **ist** örtlich ein Zylinder mit großem Radius —
    als Merkmal ist er trotzdem keines.

    Gemessen an einem heruntergeladenen Sockel von 160 auf 231 auf 14 mm: Die
    Erkennung fand dort zehn Zapfen, den dicksten mit Ø 631,6 mm. Ein Zapfen ist
    das, was man mit einer Bohrung paart (§14), und mit einem Ø 631 paart
    niemand etwas. Über sieben Modelle waren es 21 von 112 Zapfen und 19 von
    165 Bohrungen, die breiter waren als ihr eigener Körper.

    Gebogen und nicht gerade, damit die Einpassung überhaupt anspringt: Ein
    flacher Streifen hat keine gewölbte Fläche, in die ein Zylinder passt.
    """
    ring = trimesh.creation.annulus(r_min=290.0, r_max=300.0, height=8.0)
    # Nur ein Achtel davon — ein flacher Bogen, wie ihn ein Arm hat. Sein
    # Radius ist 295 mm, sein Körper misst quer zur Achse keine 240.
    arc = ring.slice_plane([0.0, 0.0, 0.0], [0.0, 1.0, 0.0])
    arc = arc.slice_plane([0.0, 0.0, 0.0], [-1.0, 1.0, 0.0])
    body = MeshData.of(arc)
    across = max(body.bounds.size[0], body.bounds.size[1])

    gefunden = detect_pins(body) + detect_holes(body)

    assert across < 590.0, "der Bogen ist schmaler als der Zylinder, der in ihn passt"
    for feature in gefunden:
        assert float(feature.params["diameter"]) <= across + 1e-6, (
            f"{feature.id} mit Ø {feature.params['diameter']} auf {across:.1f} mm Körper"
        )


def test_a_real_pin_is_kept() -> None:
    """Die Gegenprobe, und die ist die wichtigere: Ein Zapfen, der in seinen
    Körper passt, bleibt — sonst hätte die Prüfung die Merkmalserkennung
    stillgelegt.

    Ø 8 auf einem Körper, der quer zur Achse 22 mm misst: das ist der
    Sechskantzapfen einer Querstange aus dem Bestand, und der wird gebraucht.
    """
    # Der Quader kürzer als der Zapfen, sonst steckt der ganz in ihm und es
    # gibt keine gewölbte Außenfläche, in die etwas einzupassen wäre.
    stange = trimesh.creation.box(extents=(22.0, 10.0, 12.0))
    zapfen = trimesh.creation.cylinder(
        radius=4.0,
        height=18.0,
        sections=48,
        transform=trimesh.transformations.rotation_matrix(1.5707963, [1.0, 0.0, 0.0]),
    )
    body = MeshData.of(trimesh.boolean.union([stange, zapfen]))

    gefunden = detect_pins(body)

    assert gefunden, "der Zapfen wird weiter gefunden"
    assert any(abs(float(feature.params["diameter"]) - 8.0) < 0.3 for feature in gefunden), [
        round(float(f.params["diameter"]), 2) for f in gefunden
    ]


# --- faces ----------------------------------------------------------------------


def test_the_six_faces_of_a_cube_are_found() -> None:
    faces = detect_faces(cube())

    assert len(faces) == 6
    for face in faces:
        assert face.params["area"] == pytest.approx(400.0)


def test_the_largest_face_comes_first() -> None:
    faces = detect_faces(plate())

    assert faces[0].id == "face_1"
    assert faces[0].params["area"] > faces[-1].params["area"]
    assert faces[0].params["area"] == pytest.approx(80.0 * 50.0, rel=0.05)


def test_a_face_knows_where_it_looks() -> None:
    top = max(detect_faces(cube()), key=lambda face: face.params["centre"][2])
    assert top.params["normal"][2] == pytest.approx(1.0, abs=1e-6)


# --- open edges -----------------------------------------------------------------


def test_an_open_model_reports_its_edges() -> None:
    broken = normalise(read_mesh((MESHES / "broken_open.stl").read_bytes(), ".stl"), "mm").mesh
    loops = detect_edge_loops(broken)

    assert loops and loops[0].kind == "edge_loop"
    assert loops[0].params["open_edges"] > 0


def test_a_closed_model_has_no_open_edges() -> None:
    assert detect_edge_loops(cube()) == []


# --- everything together --------------------------------------------------------


def test_detection_names_everything_it_found() -> None:
    features = detect(plate())

    kinds = {feature.kind for feature in features.values()}
    assert "hole" in kinds
    assert "face" in kinds
    assert all(feature.provenance == "detected" for feature in features.values())
    assert all(identifier == feature.id for identifier, feature in features.items())


# --- was kein Merkmal ist ---------------------------------------------------------


def generated_body() -> MeshData:
    """Ein erzeugtes Netz, wie ein Bildmodell es liefert (siehe tests/data/README)."""
    return normalise(read_mesh((MESHES / "generated_figure.stl").read_bytes(), ".stl"), "mm").mesh


def test_a_generated_mesh_does_not_drown_in_faces() -> None:
    """Der Fund, aus dem ``MIN_FACE_AREA`` entstand.

    Der relative Anteil an der größten Fläche filtert nur bei einem
    konstruierten Teil. Auf einem gleichmäßig facettierten Netz ist jede Facette
    „mindestens zwei Prozent der größten", und die Kugel meldete 180 Flächen.
    Danach war jede Zuordnung mehrdeutig und die Auswertung hielt bei jeder
    Operation an (§21.3) — Weg 3 kam nach der Reparatur nicht weiter.
    """
    features = detect(generated_body())

    faces = [entry for entry in features.values() if entry.kind == "face"]
    assert not faces, f"{len(faces)} Flächen auf einem organischen Netz"


def test_a_scratch_is_not_a_bore() -> None:
    """Eine Düse legt 0,4 mm breite Bahnen — 0,05 mm hat kein Werkzeug gemacht."""
    holes = detect_holes(generated_body())

    assert all(entry.params["diameter"] >= 0.5 for entry in holes)


def test_the_faces_of_a_real_part_survive_the_limit() -> None:
    """Die Grenze darf nur das treffen, was sie treffen soll."""
    faces = detect_faces(plate())

    assert len(faces) == 6, "eine Platte hat sechs Seiten, und alle sind Flächen"


def test_a_face_keeps_its_centre_when_it_gets_a_hole() -> None:
    """Der Mittelpunkt gehört der Form, nicht der Vernetzung.

    Als Mittel über die Dreiecksschwerpunkte wanderte er zum Loch, weil dort
    viele kleine Dreiecke entstehen: bei einem 60 × 40er Deckel um 16,8 mm.
    Die Zuordnung (§21.2) hielt die Oberseite danach für eine andere Fläche und
    meldete die alte als verwaist — vier Warnungen im Beispielprojekt, ohne
    dass jemand etwas falsch gemacht hätte.
    """
    from app.core.geom.prepare import drill
    from app.core.knowledge import profiles

    box = trimesh.creation.box(extents=(60.0, 40.0, 6.0))
    box.apply_translation((0.0, 0.0, 3.0))
    plain = MeshData.of(box)
    drilled = drill(
        plain,
        position=(-20.0, 0.0, 6.0),
        axis="z",
        diameter=4.5,
        depth=0.0,
        profile=profiles.make_profile("centauri-carbon-2", "petg"),
    ).mesh

    def top_of(mesh: MeshData) -> tuple[float, ...]:
        top = max(detect_faces(mesh), key=lambda face: face.params["centre"][2])
        return tuple(top.params["centre"])

    before, after = top_of(plain), top_of(drilled)

    moved = sum((a - b) ** 2 for a, b in zip(before, after, strict=True)) ** 0.5
    assert moved < 1.0, f"der Mittelpunkt wanderte um {moved:.1f} mm"


def plate_with_pin() -> MeshData:
    """Eine Platte mit einem 6-mm-Stift darauf — das Gegenstück einer Bohrung."""
    base = trimesh.creation.box(extents=(40.0, 40.0, 8.0))
    base.apply_translation((0.0, 0.0, 4.0))
    pin = trimesh.creation.cylinder(radius=3.0, height=12.0, sections=48)
    pin.apply_translation((0.0, 0.0, 12.0))
    return MeshData.of(trimesh.boolean.union([base, pin]))


def test_a_pin_is_recognised_as_one() -> None:
    """§14 braucht beide Enden einer Passung; eine Bohrung allein ist die
    Hälfte.
    """
    found = detect_pins(plate_with_pin())

    assert len(found) == 1
    assert found[0].id == "pin_1"
    assert found[0].kind == "pin"
    assert found[0].params["diameter"] == pytest.approx(6.0, abs=0.02)
    assert found[0].params["axis"][2] == pytest.approx(1.0, abs=0.01)


def test_a_pin_on_a_plate_is_not_reported_as_a_bore() -> None:
    assert detect_holes(plate_with_pin()) == []


def test_a_bore_is_not_reported_as_a_pin() -> None:
    assert detect_pins(plate()) == []


def test_a_small_flat_face_is_not_swallowed_by_the_curve_next_to_it() -> None:
    """Der Fehler hinter dem Stift: ein Deckel aus vielen koplanaren Dreiecken
    ist eine Fläche.

    Nur nach Fläche gegen die größte Fläche des Körpers beurteilt, ist die
    Oberseite eines 6-mm-Stifts unter zwei Prozent einer 40-mm-Platte — sie
    zählte als gekrümmt, schloss sich der Wand an, und die Zylinder-Einpassung
    über Deckel-plus-Wand fand gar nichts.
    """
    from app.core.perceive.features import _large_facet_faces

    body = plate_with_pin().raw
    planar = _large_facet_faces(body)

    top = max(
        (facet for facet in body.facets if len(facet) >= 8),
        key=lambda facet: len(facet),
    )
    assert {int(index) for index in top} <= planar


def test_a_cylinder_has_three_faces_and_not_fifty() -> None:
    """§21.1: „auf die Fläche zeigen" meint eine Fläche, keine Facette.

    Ein Ø-50-Zylinder mit 48 Segmenten trug einundfünfzig Merkmale der Art
    ``face`` — achtundvierzig Mantelstreifen, Deckel, Boden und die Bohrung.
    Fusion zeigt für denselben Körper drei Flächen. Ein Merkmalsbaum von
    ``face_1`` bis ``face_51`` ist keine Auswahl, sondern eine Liste.

    Der Mantel wird jetzt als das gemeldet, was er ist: ein Zylinder, also ein
    ``pin`` — dieselbe Erkennung, die auch die Bohrung findet.
    """
    import trimesh

    body = trimesh.creation.cylinder(radius=25.0, height=20.0, sections=48)
    bore = trimesh.creation.cylinder(radius=4.1, height=40.0, sections=48)
    features = detect(MeshData.of(trimesh.boolean.difference([body, bore])))

    kinds = [entry.kind for entry in features.values()]
    assert sorted(kinds) == ["face", "face", "hole", "pin"], kinds


def test_a_coarse_prism_keeps_its_sides() -> None:
    """Die Grenze zwischen Rundung und Kante liegt bei dreißig Grad.

    Ein Achteck-Prisma ist kein Zylinder — seine acht Seiten sind Flächen, an
    denen jemand etwas ansetzt, und sie einzeln zu melden ist richtig. Erst ab
    zwölf Segmenten (30 Grad) wird aus dem Vieleck eine Rundung.
    """
    import trimesh

    prism = MeshData.of(trimesh.creation.cylinder(radius=25.0, height=20.0, sections=8))

    faces = detect_faces(prism)

    assert len(faces) == 10, "acht Seiten, Deckel und Boden"


def test_components_are_counted() -> None:
    two = normalise(read_mesh((MESHES / "two_components.stl").read_bytes(), ".stl"), "mm").mesh
    assert component_count(two) == 2
    assert component_count(cube()) == 1


# --- gesenkte Bohrung (§21.1) ---------------------------------------------------


def test_a_countersink_does_not_swallow_its_own_bore() -> None:
    """Gefunden am 22.08.2026, und es war schlimmer als „die Senkung fehlt".

    Kegelwand und Bohrungswand hängen zusammen, die Fleckenbildung trennte sie
    nicht, und die Zylindereinpassung über Wand-plus-Kegel kam als nichts
    heraus. Ein gesenktes Loch — die häufigste Bohrung in einem Druckteil —
    stand damit überhaupt nicht in der Szene, und der Agent konnte auf nichts
    zeigen (Leitprinzip 5).
    """
    bores = detect_holes(plate("plate_countersunk.stl"))

    assert len(bores) == 1, f"one bore under the sink: {[bore.id for bore in bores]}"
    assert bores[0].params["diameter"] == pytest.approx(5.2, abs=0.15)
    # Die Tiefe ist die des **Zylinders**, nicht die der Platte: 8 mm minus die
    # 2,4 mm, die der Kegel wegnimmt. Das bleibt auch so — was die Senkung
    # dazutut, steht in ``through`` und nicht in ``depth``.
    assert bores[0].params["depth"] == pytest.approx(5.6, abs=0.15)


def test_a_countersunk_bore_is_still_a_through_hole() -> None:
    """Die zweite Hälfte desselben Fundes, und sie stand bis heute offen.

    ``through`` mass die Höhe der **Zylinderwand** gegen die Dicke des
    Körpers. Bei einer Senkung gehört das obere Stück des Lochs aber zum
    Kegel, nicht zum Zylinder — 5,6 gegen 8 mm, und damit galt die häufigste
    Bohrung eines Druckteils als Sackloch. Das ist keine Frage der Anzeige:
    Eine Passung sucht sich ihr Gegenstück über die Merkmalsarten (§14), und
    in ein Sackloch geht keine durchgesteckte Schraube.

    Entscheidbar ist es, seit der Kegel selbst ein Merkmal ist (§21.1) —
    vorher gab es nichts, was die fehlenden 2,4 mm hätte erklären können.
    """
    bores = detect_holes(plate("plate_countersunk.stl"))

    assert bores[0].params["through"] is True


def test_a_sink_does_not_turn_a_blind_bore_into_a_through_one() -> None:
    """Die Gegenprobe, und sie ist der Grund für die zweite Korpusdatei.

    ``plate_countersunk_blind.stl`` trägt dieselbe Senkung über einem Loch,
    das vor der Unterseite endet: 3,6 mm Zylinder plus 2,4 mm Kegel sind 6 von
    8 mm. Wer die Senkung bloß als „geht durch" verbucht, statt ihre Tiefe zu
    addieren, bekommt diesen Test rot.
    """
    bores = detect_holes(plate("plate_countersunk_blind.stl"))

    assert len(bores) == 1, f"one bore under the sink: {[bore.id for bore in bores]}"
    assert bores[0].params["depth"] == pytest.approx(3.6, abs=0.15)
    assert bores[0].params["through"] is False


def test_the_bore_reads_the_same_alone_as_in_a_whole_detection() -> None:
    """Dieselbe Frage, zwei Wege — und beide müssen dasselbe sagen.

    ``detect`` gibt die einmal gesuchten Einpassungen weiter, ``detect_holes``
    allein sucht sie selbst. Genau an dieser Naht entstand der Fehler schon
    einmal (siehe ``test_the_expensive_search_runs_once_per_detection``), und
    er ist von der teuren Sorte: Jeder Test **innerhalb** eines der beiden Wege
    bleibt grün, während die Anwendung etwas anderes sieht als die
    Kommandozeile.
    """
    mesh = plate("plate_countersunk.stl")

    alone = detect_holes(mesh)[0]
    together = detect(mesh)[alone.id]

    assert alone.params["through"] == together.params["through"]
    assert alone.params["depth"] == pytest.approx(together.params["depth"])


def test_the_same_plate_without_the_sink_was_never_the_problem() -> None:
    """Die Gegenprobe, damit der Test oben nicht auf ein anderes Maß hereinfällt."""
    assert len(detect_holes(plate("plate_holes.stl"))) == 4


def test_the_expensive_search_runs_once_per_detection(monkeypatch: pytest.MonkeyPatch) -> None:
    """Der Docstring von ``_cylinders`` verspricht es seit es ihn gibt, die
    Verdrahtung hielt es nicht: ``detect_holes`` und ``detect_pins`` riefen
    jede für sich.

    Gezählt statt gemessen — eine Zeitmessung wäre auf einer belegten Maschine
    kein Wächter (§31).
    """
    from app.core.perceive import features

    calls = 0
    original = features._fitted

    def counted(mesh: MeshData) -> object:
        nonlocal calls
        calls += 1
        return original(mesh)

    monkeypatch.setattr(features, "_fitted", counted)
    features.detect(plate())

    assert calls == 1, f"the search ran {calls} times for one detection"


# --- Kegel (§21.1) ---------------------------------------------------------------


def test_the_countersink_is_a_feature_of_its_own() -> None:
    """Eine Senkung war bis zum 22.08.2026 ein namenloser Haufen Dreiecke.

    Damit konnte der Agent nicht auf sie zeigen, und Leitprinzip 5 lässt ihm
    keinen zweiten Weg — Koordinaten erzeugt er nicht.
    """
    cones = detect_cones(plate("plate_countersunk.stl"))

    assert len(cones) == 1, f"one sink: {[cone.id for cone in cones]}"
    # Der **Öffnungswinkel**, nicht der Halbwinkel: Eine Senkung heißt „90 Grad".
    assert cones[0].params["angle"] == pytest.approx(90.0, abs=0.5)
    assert cones[0].params["recess"] is True
    # Ø 10 auf die Stelle: der Durchmesser kommt aus den **Ecken** des Flecks
    # und nicht aus den Dreiecksmitten, die ein Stück darunter liegen.
    assert cones[0].params["diameter"] == pytest.approx(10.0, abs=0.05)
    # Und die Mitte liegt auf der Deckfläche, nicht an der Spitze im Nichts.
    assert cones[0].params["centre"][2] == pytest.approx(4.0, abs=0.05)


def test_a_plain_bore_is_never_read_as_a_cone() -> None:
    """Ein Zylinder ist ein Kegel mit Öffnungswinkel null, also findet die
    Einpassung an jeder Bohrung auch einen.

    Stünde eine Bohrung als Kegel in der Szene, wäre sie für jede
    Bohrungs-Operation unsichtbar — deshalb entscheidet der Winkel und nicht
    die Reihenfolge.
    """
    assert detect_cones(plate()) == []
    assert len(detect_holes(plate())) == 4


def test_a_cone_that_sticks_out_is_not_a_recess() -> None:
    """Dieselbe Form, andere Seite — und die Unterscheidung entscheidet, was
    man damit tun kann.
    """
    base = trimesh.creation.box(extents=(40.0, 40.0, 6.0))
    boss = trimesh.creation.cone(radius=6.0, height=10.0, sections=64)
    boss.apply_translation((0.0, 0.0, 3.0))
    mesh = MeshData.of(trimesh.boolean.union([base, boss]))

    cones = detect_cones(mesh)

    assert len(cones) == 1
    assert cones[0].params["recess"] is False
    assert cones[0].params["angle"] == pytest.approx(61.9, abs=1.5)


def test_the_normals_decide_the_shape_and_not_the_residual() -> None:
    """Der Fall, an dem die naheliegende Reihenfolge scheitert.

    Jede Facette eines aufgesetzten Kegels ist **ein** Dreieck von der
    Grundfläche zur Spitze; ihr Schwerpunkt liegt auf einem Drittel der Höhe,
    und damit liegen alle Schwerpunkte auf einem Kreis. Die
    Zylindereinpassung rechnet über die Schwerpunkte und findet einen
    tadellosen Zylinder — Rückstand 0,0000 — an einem Kegel mit 31 Grad.
    """
    from app.core.perceive.features import fit_cone, fit_cylinder

    base = trimesh.creation.box(extents=(40.0, 40.0, 6.0))
    boss = trimesh.creation.cone(radius=6.0, height=10.0, sections=64)
    boss.apply_translation((0.0, 0.0, 3.0))
    body = MeshData.of(trimesh.boolean.union([base, boss])).raw
    from app.core.perceive.features import _connected_patches, _large_facet_faces

    planar = _large_facet_faces(body)
    curved = [index for index in range(len(body.faces)) if index not in planar]
    patch = max(_connected_patches(body, curved), key=len)

    cylinder = fit_cylinder(body, patch)
    cone = fit_cone(body, patch)

    assert cylinder is not None and cylinder.good, "this is the trap: the cylinder looks perfect"
    assert cone is not None and cone.half_angle == pytest.approx(30.9, abs=1.0)
