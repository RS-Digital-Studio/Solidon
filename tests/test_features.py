"""Merkmalserkennung gegen eine Platte mit bekannten Maßen (§21.1, §40).

plate_holes.stl ist 80 x 50 x 8 mm mit vier Bohrungen zu 5,2 mm — jede Zahl,
die die Erkennung erzeugt, lässt sich also prüfen statt bewundern.
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest
import trimesh

from app.core.geom.mesh import MeshData, read_mesh
from app.core.ingest.loader import normalise
from app.core.perceive.features import (
    _FEATURE_CACHE,
    CACHE_LIMIT,
    CYLINDER_TOLERANCE,
    EDGE_LOOP_LIMIT,
    component_count,
    detect,
    detect_cones,
    detect_edge_loops,
    detect_faces,
    detect_holes,
    detect_pins,
    detect_spheres,
    detect_tori,
    fit_cylinder,
    fit_torus,
    forget_cache,
)

MESHES = Path(__file__).parent / "data" / "meshes"


def plate(name: str = "plate_holes.stl") -> MeshData:
    return normalise(read_mesh((MESHES / name).read_bytes(), ".stl"), "mm").mesh


def cube() -> MeshData:
    return normalise(read_mesh((MESHES / "cube_clean.stl").read_bytes(), ".stl"), "mm").mesh


def as_a_file_arrives(body: trimesh.Trimesh) -> MeshData:
    """Durch eine STL geschickt und **ungeschweißt** zurückgelesen.

    Genau so kommt jede STL an, und genau so lädt ``generate.into_project``
    (``weld: False``). Das Format kennt keine gemeinsamen Ecken: Jedes Dreieck
    bringt seine eigenen drei Punkte mit, also hat topologisch jede Kante
    keinen Partner — auch an einem Körper, der rundum geschlossen ist.

    Der Umweg über die Datei ist Absicht und nicht Umständlichkeit: Ein von
    Hand gebautes ``Trimesh`` ist bereits zusammengeführt, und ein Test darauf
    prüfte den Fall nicht, um den es hier geht.
    """
    data = trimesh.exchange.stl.export_stl(body)
    return MeshData.of(
        trimesh.load(trimesh.util.wrap_as_stream(data), file_type="stl", process=False)
    )


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


def u_profile() -> MeshData:
    """Ein U-Profil mit einer Durchgangsbohrung im linken Schenkel.

    Der rechte Schenkel steht auf derselben Achse — er liegt in der Projektion
    „über" der Bohrung, ohne sie zu verschließen. Genau die Lage, an der die
    Prüfung „liegt irgendein Dreieck über der Achse" das falsche Ergebnis
    liefert.
    """
    left = trimesh.creation.box(extents=(4.0, 30.0, 20.0))
    left.apply_translation((-11.0, 0.0, 0.0))
    right = trimesh.creation.box(extents=(4.0, 30.0, 20.0))
    right.apply_translation((11.0, 0.0, 0.0))
    base = trimesh.creation.box(extents=(26.0, 30.0, 4.0))
    base.apply_translation((0.0, 0.0, -12.0))
    bore = trimesh.creation.cylinder(
        radius=3.0,
        height=40.0,
        sections=64,
        transform=trimesh.transformations.rotation_matrix(math.pi / 2.0, [0.0, 1.0, 0.0]),
    )
    bore.apply_translation((-11.0, 0.0, 0.0))
    frame = trimesh.boolean.union([left, right, base])
    return MeshData.of(trimesh.boolean.difference([frame, bore]))


def test_a_bore_through_one_leg_of_a_u_is_a_through_bore() -> None:
    """Der Fund: „durchgehend" hieß wörtlich „kein Dreieck irgendwo darüber".

    Der gegenüberliegende Schenkel eines U-Profils liegt in der Projektion
    senkrecht zur Achse genau über der Bohrung — er verschließt sie aber
    nicht, er steht zwanzig Millimeter daneben. Die Bohrung galt damit als
    Sackloch; im Steckbrief steht dann „Sackbohrung Ø 6" über einem Loch, durch
    das man hindurchsieht, und eine Passung dagegen zu setzen ist sinnlos.

    Gefragt wird deshalb entlang der Achse: Material zählt, wo es **im**
    Bohrungsabschnitt liegt.
    """
    holes = detect_holes(u_profile())

    assert len(holes) == 1, [hole.id for hole in holes]
    assert holes[0].params["through"] is True


def test_a_blind_bore_stays_blind() -> None:
    """Die Gegenprobe: Ein Sackloch hat seinen Boden **im** eigenen Abschnitt.

    Ohne sie wäre die Prüfung mit „immer durchgehend" grün.
    """
    plate_body = trimesh.creation.box(extents=(30.0, 30.0, 12.0))
    bore = trimesh.creation.cylinder(radius=3.0, height=8.0, sections=64)
    # Von oben eingesenkt, der Boden liegt bei z = -2.
    bore.apply_translation((0.0, 0.0, 6.0))
    body = MeshData.of(trimesh.boolean.difference([plate_body, bore]))

    holes = detect_holes(body)

    assert holes, "die Sackbohrung wird gefunden"
    assert all(hole.params["through"] is False for hole in holes)


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


def test_faces_of_the_same_size_are_numbered_the_same_way_every_time() -> None:
    """§21.2: Eine Provenienz-ID muss eine Neuberechnung überleben.

    Die sechs Flächen eines Würfels sind exakt gleich groß, sortiert wurde
    aber nur nach Fläche — welche ``face_1`` wird, hing damit an der
    Reihenfolge der Dreiecke im Netz. Dieselbe Geometrie mit anders
    nummerierten Dreiecken gab eine andere Zuordnung: ``face_1`` lag einmal
    links und einmal unten.

    Die Zuordnung (§21.2) fängt das im Regelbetrieb wieder ein, weil sie über
    die Lage vergleicht — aber die **Ersterkennung** ist der Fall, in dem es
    noch nichts zum Vergleichen gibt.
    """
    box = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    turned = trimesh.Trimesh(
        vertices=box.vertices.copy(), faces=np.roll(box.faces, 5, axis=0), process=False
    )

    first = {
        face.id: tuple(round(value, 2) for value in face.params["centre"])
        for face in detect_faces(MeshData.of(box))
    }
    second = {
        face.id: tuple(round(value, 2) for value in face.params["centre"])
        for face in detect_faces(MeshData.of(turned))
    }

    assert len(first) == 6
    assert first == second


def test_turning_a_part_does_not_renumber_its_faces() -> None:
    """Die Gegenbedingung, und sie schließt den naheliegenden Tiebreak aus.

    Nach Koordinaten zu sortieren wäre deterministisch und trotzdem falsch:
    Deck- und Bodenfläche einer Platte sind gleich groß, und um zwanzig Grad
    gekippt tauschen sie ihre Reihenfolge. ``align`` legt aber ``face_1``
    eines gedrehten Teils auf ``face_1`` des festen — beide müssen dieselbe
    Fläche des Teils meinen, sonst liegt das Teil verkehrt herum auf dem
    anderen.
    """
    flat = plate()
    tilted = MeshData.of(
        flat.raw.copy().apply_transform(
            trimesh.transformations.rotation_matrix(math.radians(20.0), [1.0, 0.0, 0.0])
        )
    )

    before = {face.id: face.face_indices for face in detect_faces(flat)}
    after = {face.id: face.face_indices for face in detect_faces(tilted)}

    assert before, "ohne erkannte Flächen prüft der Vergleich nichts"
    assert before == after, "dieselben Dreiecke tragen dieselbe Nummer"


def test_a_face_knows_where_it_looks() -> None:
    top = max(detect_faces(cube()), key=lambda face: face.params["centre"][2])
    assert top.params["normal"][2] == pytest.approx(1.0, abs=1e-6)


# --- open edges -----------------------------------------------------------------


def test_an_open_model_reports_its_edges() -> None:
    broken = normalise(read_mesh((MESHES / "broken_open.stl").read_bytes(), ".stl"), "mm").mesh
    loops = detect_edge_loops(broken)

    assert loops and loops[0].kind == "edge_loop"
    # Die Datei ist eingecheckt und ändert sich nicht: fünf offene Kanten.
    # ``> 0`` bliebe grün, wenn die Zählung nur noch eine einzige meldete.
    assert loops[0].params["open_edges"] == 5


def test_a_closed_model_has_no_open_edges() -> None:
    assert detect_edge_loops(cube()) == []


def test_two_holes_in_a_shell_are_two_features() -> None:
    """Der Fund: Alle offenen Kanten wurden **ein** Merkmal.

    Der gemeinsame Schwerpunkt zweier Löcher liegt zwischen ihnen — also im
    Leeren. Die Kamera flog auf einen Punkt, an dem nichts ist, und die Zahl
    daneben („8 offene Kanten") gehörte zu zwei Stellen, die nichts
    miteinander zu tun haben. Jede zusammenhängende Kantenschleife ist ein
    eigener Defekt und bekommt ein eigenes Merkmal.
    """
    parts = []
    for shift in (-20.0, 20.0):
        box = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
        box.apply_translation((shift, 0.0, 0.0))
        # Die Deckfläche heraus: übrig bleibt ein offener Kasten mit einer
        # Schleife aus vier Kanten.
        box.update_faces(
            np.array([index for index, normal in enumerate(box.face_normals) if normal[2] < 0.9])
        )
        parts.append(box)
    broken = MeshData.of(trimesh.util.concatenate(parts))

    loops = detect_edge_loops(broken)

    assert len(loops) == 2, [loop.id for loop in loops]
    assert sum(int(loop.params["open_edges"]) for loop in loops) == 8
    xs = sorted(round(float(loop.params["centre"][0]), 1) for loop in loops)
    assert xs == [-20.0, 20.0], "jede Schleife sitzt an ihrem eigenen Loch"


@pytest.mark.parametrize("name", ["plate_holes.stl", "torus_ring.stl", "cube_clean.stl"])
def test_a_closed_model_stays_closed_when_it_arrives_unwelded(name: str) -> None:
    """Der Fund: Eine geschlossene Datei meldete eine offene Stelle je Dreieck.

    Eine STL speichert jedes Dreieck mit eigenen Ecken. Wer die gespeicherte
    Topologie befragt statt der geometrischen, bekommt deshalb an **jeder**
    Kante „kein Partner" — gemessen 2 388 offene Kanten an ``plate_holes.stl``,
    6 912 an ``torus_ring.stl``, 36 an ``cube_clean.stl``. Alle drei Teile sind
    dicht; die Zahlen beschrieben das Dateiformat und nicht das Modell.

    Für den Kunden ist das die Auskunft, für die er Solidon öffnet (Weg 1,
    §2.2): Er zieht ein heruntergeladenes Teil herein und liest im Prüfbericht,
    was damit ist. Eine Zahl, die dort etwas anderes beschreibt als sein Teil,
    ist schlimmer als keine.

    Geprüft wird an drei Dateien und nicht an einer: Die Zahl der Dreiecke
    reicht von 12 bis 2 304, und die Toleranz des Zusammenführens hängt an der
    Modellgröße.
    """
    path = MESHES / name
    body = trimesh.load(path, process=False, force="mesh")

    assert not body.is_watertight, (
        f"{name} kommt hier bereits zusammengeführt an — dann prüft der Test seinen Aufbau"
    )
    assert trimesh.load(path, process=True, force="mesh").is_watertight, (
        f"{name} ist auch zusammengeführt nicht dicht — dann ist es der falsche Prüfling"
    )

    assert detect_edge_loops(MeshData.of(body)) == [], (
        "ein dichtes Teil hat keine offene Stelle, gleich wie die Datei es speichert"
    )


def test_a_real_hole_survives_the_merge() -> None:
    """Und die Gegenrichtung, ohne die die Änderung oben wertlos wäre.

    Was ``repair`` schließt, muss die Erkennung erst finden. Ein Zusammenführen,
    das ein echtes Loch verschwinden ließe, nähme der Reparatur die Grundlage —
    und das wäre der schlechtere Fehler: Der Kunde bekäme „alles in Ordnung"
    über einem Teil, das beim Drucken auffliegt.

    Der Kasten ohne Deckel kommt hier denselben Weg wie oben, also
    ungeschweißt. Zusammengelegt werden nur Ecken **am selben Ort**; die vier
    Kanten des offenen Randes haben keinen Partner am selben Ort und bleiben
    deshalb, was sie sind.
    """
    box = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    box.update_faces(
        np.array([index for index, normal in enumerate(box.face_normals) if normal[2] < 0.9])
    )

    loops = detect_edge_loops(as_a_file_arrives(box))

    assert len(loops) == 1, [loop.id for loop in loops]
    assert loops[0].params["open_edges"] == 4, "die vier Kanten der fehlenden Deckfläche"
    assert loops[0].params["centre"][2] == pytest.approx(5.0, abs=1e-6), (
        "die Schleife sitzt oben, wo der Deckel fehlt"
    )


def test_two_holes_stay_two_when_the_file_arrives_unwelded() -> None:
    """Die Absicht von ``5c90fac6`` gilt auch hier — sie ist der Grund, warum
    nicht einfach alles zu einem Merkmal zusammengefasst wird.

    Zwei Löcher, ungeschweißt geladen: zwei Merkmale an zwei Orten, nicht eines
    dazwischen im Leeren.
    """
    parts = []
    for shift in (-20.0, 20.0):
        part = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
        part.apply_translation((shift, 0.0, 0.0))
        part.update_faces(
            np.array([index for index, normal in enumerate(part.face_normals) if normal[2] < 0.9])
        )
        parts.append(part)

    loops = detect_edge_loops(as_a_file_arrives(trimesh.util.concatenate(parts)))

    assert len(loops) == 2, [loop.id for loop in loops]
    xs = sorted(round(float(loop.params["centre"][0]), 1) for loop in loops)
    assert xs == [-20.0, 20.0], "jede Schleife sitzt an ihrem eigenen Loch"


def test_an_unwelded_edge_loop_keeps_its_number_when_the_body_turns() -> None:
    """Dieselbe Zusage wie unten, aber am ungeschweißten Netz — und nur hier
    lässt sie sich überhaupt verletzen.

    Das Zusammenführen nummeriert die Ecken um, und es ordnet sie dabei **nach
    Koordinaten**. Genau davor warnt ``detect_faces``: Eine Ordnung nach
    Koordinaten überlebt keine Drehung. Die Erkennung rechnet deshalb zwar über
    die zusammengeführte Topologie, sortiert aber über die **Original**-Nummern
    der Ecken, die sich weder beim Drehen noch beim Umsortieren ändern.

    **Der Test unten kann das nicht prüfen**, und das ist der Grund für diesen
    hier: Er baut sein Netz von Hand, damit ist es bereits zusammengeführt, und
    Orts- und Original-Nummern fallen zusammen. Gegengeprobt — mit den
    Ortsnummern wandert ``edge_loop_1`` bei dieser Drehung von x=−20 auf x=−20,
    obwohl es bei +20 liegen müsste; der Test unten bleibt dabei grün.
    """
    parts = []
    for shift in (-20.0, 20.0):
        part = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
        part.apply_translation((shift, 0.0, 0.0))
        part.update_faces(
            np.array([index for index, normal in enumerate(part.face_normals) if normal[2] < 0.9])
        )
        parts.append(part)
    body = trimesh.util.concatenate(parts)

    before = detect_edge_loops(as_a_file_arrives(body))
    assert len(before) == 2, "sonst prüft der Test seinen eigenen Aufbau"
    assert before[0].params["open_edges"] == before[1].params["open_edges"], (
        "nur bei gleicher Kantenzahl entscheidet das zweite Kriterium — darum geht es hier"
    )

    turn = trimesh.transformations.rotation_matrix(np.pi, (0.0, 0.0, 1.0))
    turned = body.copy()
    turned.apply_transform(turn)
    after = detect_edge_loops(as_a_file_arrives(turned))

    assert len(after) == 2
    expected = trimesh.transform_points([list(before[0].params["centre"])], turn)[0]
    assert tuple(after[0].params["centre"]) == pytest.approx(tuple(expected), abs=1e-6), (
        "edge_loop_1 meint nach der Drehung die andere Schleife — daran hängen Ops und Passungen"
    )


def test_many_open_places_come_as_one_summary() -> None:
    """Die zweite Linie: ein Netz, das wirklich in Stücken ankommt.

    Nicht mehr der ungeschweißte Regelfall — den beantwortet die Erkennung
    selbst —, sondern ein Körper, der tatsächlich aus lauter losen Dreiecken
    besteht. Die bleiben auch zusammengeführt lose, denn sie liegen wirklich
    nicht aneinander.

    Zwanzig Stellen bekommen einen eigenen Namen, der Rest **eine** Zeile.
    Dreitausend einzeln anklickbare Einträge sind keine Bedienung, und die
    Zuordnung (§21.2) wächst quadratisch in der Zahl der Merkmale.

    Die Schranke daneben ist keine Zierde: Der Test baut seinen Prüfling aus
    ``EDGE_LOOP_LIMIT`` und wanderte damit stillschweigend mit, wenn jemand die
    Grenze auf hunderttausend setzte — er prüfte dann die Aktualität der Zahl
    statt ihrer Richtigkeit. Was die Zahl leisten muss, ist eine Liste, die
    jemand durchgeht; das ist die Zusage, und sie steht hier.
    """
    assert EDGE_LOOP_LIMIT <= 50, (
        "die Grenze ist eine Bedienzahl — was darüber liegt, geht niemand mehr durch"
    )

    count = EDGE_LOOP_LIMIT + 12
    apart = trimesh.util.concatenate(
        [
            trimesh.Trimesh(
                vertices=np.array([[0.0, 0.0, 0.0], [1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])
                + np.array([10.0 * index, 0.0, 0.0]),
                faces=np.array([[0, 1, 2]]),
                process=False,
            )
            for index in range(count)
        ]
    )

    loops = detect_edge_loops(MeshData.of(apart))

    assert len(loops) == EDGE_LOOP_LIMIT + 1, [loop.id for loop in loops]
    summary = loops[-1]
    assert summary.kind == "edge_loop", "das Kontextmenü zum Reparieren hängt an der Art"
    assert summary.params["loops"] == count - EDGE_LOOP_LIMIT, (
        "die Sammelzeile sagt, wie viele Stellen sie zusammenfasst"
    )
    assert summary.params["open_edges"] == 3 * (count - EDGE_LOOP_LIMIT)
    # **Der Ort ist eine echte Stelle, kein Schwerpunkt.** Ein Mittelwert über
    # alle läge zwischen ihnen und damit im Leeren — genau der Fehler, den die
    # Aufteilung in einzelne Schleifen behoben hat (§18.4).
    assert any(
        summary.params["centre"] == loop.params["centre"]
        for loop in detect_edge_loops(MeshData.of(apart))
    )
    assert sum(int(loop.params["open_edges"]) for loop in loops) == 3 * count, (
        "keine offene Kante geht beim Zusammenfassen verloren"
    )


def test_an_edge_loop_keeps_its_number_when_the_body_turns() -> None:
    """Zwei gleich große Schleifen behalten ihre Nummer, wenn das Teil sich dreht.

    An den IDs hängen Ops und Passungen (§21.2), und ``detect_faces`` sagt
    neunzig Zeilen weiter oben ausdrücklich, warum: Eine Nummerierung nach
    Koordinaten überlebt keine Drehung. ``detect_edge_loops`` tat trotzdem
    genau das — bei gleicher Kantenzahl entschied der gerundete Mittelpunkt.

    **Gedreht wird um 180 Grad, und das ist keine Willkür.** Bei zwanzig Grad
    bliebe die linke Schleife links; der Test wäre auch mit der alten
    Sortierung grün und würde eine Zusage prüfen, die er gar nicht auslöst.
    Erst eine Drehung, welche die Reihenfolge *umkehrt*, stellt die Frage.

    Verglichen wird über den mitgedrehten Mittelpunkt: Trägt ``edge_loop_1``
    danach die Stelle, die vorher ``edge_loop_1`` war, meint die ID dieselbe
    Schleife.
    """
    parts = []
    for shift in (-20.0, 20.0):
        box = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
        box.apply_translation((shift, 0.0, 0.0))
        box.update_faces(
            np.array([index for index, normal in enumerate(box.face_normals) if normal[2] < 0.9])
        )
        parts.append(box)
    body = trimesh.util.concatenate(parts)

    before = detect_edge_loops(MeshData.of(body))
    assert len(before) == 2, "sonst prüft der Test seinen eigenen Aufbau"
    assert before[0].params["open_edges"] == before[1].params["open_edges"], (
        "nur bei gleicher Kantenzahl entscheidet das zweite Kriterium — darum geht es hier"
    )

    turn = trimesh.transformations.rotation_matrix(np.pi, (0.0, 0.0, 1.0))
    turned = body.copy()
    turned.apply_transform(turn)
    after = detect_edge_loops(MeshData.of(turned))

    assert len(after) == 2
    expected = trimesh.transform_points([list(before[0].params["centre"])], turn)[0]
    assert tuple(after[0].params["centre"]) == pytest.approx(tuple(expected), abs=1e-6), (
        "edge_loop_1 meint nach der Drehung die andere Schleife — daran hängen Ops und Passungen"
    )


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

    # **Erst festhalten, dass überhaupt etwas erkannt wird.** Ohne diese Zeile
    # wäre der Test auch grün, wenn ``detect`` gar nichts mehr liefert — eine
    # gefilterte Teilmenge einer leeren Menge ist leer. Gemessen: drei Kugeln
    # und eine offene Kante.
    assert features, "die Erkennung liefert auf diesem Netz nichts mehr"

    faces = [entry for entry in features.values() if entry.kind == "face"]
    assert not faces, f"{len(faces)} Flächen auf einem organischen Netz"


def test_a_scratch_is_not_a_bore() -> None:
    """Eine Düse legt 0,4 mm breite Bahnen — 0,05 mm hat kein Werkzeug gemacht."""
    body = generated_body()
    assert detect(body), "die Erkennung liefert auf diesem Netz nichts mehr"
    holes = detect_holes(body)

    # **Nicht ``all(... >= 0.5)``.** Auf einem organischen Netz gibt es keine
    # Bohrung, die Liste ist also leer — und ``all`` über eine leere Liste ist
    # wahr. Die Zusicherung war grün, ohne je etwas zu prüfen, und hätte
    # einen Kratzer durchgelassen, der als Ø2 gemeldet wird.
    assert not holes, f"{len(holes)} angebliche Bohrungen auf einem organischen Netz"


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


# --- Kugel und Torus (§21.1, Ausbaustufe §41) -------------------------------------


def test_a_socket_is_recognised_as_a_sphere() -> None:
    """Die Kugel als **Pfanne** — der Fall, den §41 zuerst nennt.

    Eine freistehende Kugel kommt in einem Druckteil kaum vor, eine Pfanne für
    ein Kugelgelenk oder einen Magneten dauernd. Vor dem 22.08.2026 kam an
    ``sphere_socket.stl`` nichts heraus als die sechs Flächen des Blocks: keine
    Falschmeldung, aber auch kein Merkmal, auf das der Agent hätte zeigen
    können (Leitprinzip 5).
    """
    spheres = detect_spheres(plate("sphere_socket.stl"))

    assert len(spheres) == 1, f"one socket: {[sphere.id for sphere in spheres]}"
    # R = 8 im Entwurf; eine Icosphere ist einbeschrieben, die Facetten liegen
    # also ein Stück innen. Gemessen 7,97.
    assert spheres[0].params["diameter"] == pytest.approx(15.94, abs=0.1)
    # Der Mittelpunkt liegt auf der Oberfläche des Blocks, nicht in der Mitte
    # der Kappe — dort, wo eine Kugel läge, die man hineinsetzt.
    assert spheres[0].params["centre"][2] == pytest.approx(7.5, abs=0.05)
    assert spheres[0].params["recess"] is True


def test_a_ring_is_recognised_as_a_torus() -> None:
    """Die zweite Form, und die teurere: Mit ihr kommt später der Radius einer
    Verrundung, weil eine Verrundung um eine runde Kante ein Torusstück ist.
    """
    tori = detect_tori(plate("torus_ring.stl"))

    assert len(tori) == 1, f"one ring: {[torus.id for torus in tori]}"
    # ``diameter`` ist der Ring — derselbe Schlüssel wie bei jeder anderen Art,
    # weil die Zuordnung die Größe eines Merkmals genau dort liest (§21.2).
    assert tori[0].params["diameter"] == pytest.approx(40.0, abs=0.2)
    assert tori[0].params["tube_diameter"] == pytest.approx(10.0, abs=0.2)
    assert abs(tori[0].params["axis"][2]) == pytest.approx(1.0, abs=0.01)


def test_a_piece_of_a_ring_is_enough_for_the_two_radii() -> None:
    """Ein Torus**stück** reicht der Einpassung, ein ganzer Ring ist nicht nötig.

    Das ist der Unterschied zum früheren Weg, der Ring- und Röhrenradius aus
    den **Rändern** des Flecks las: Ränder hat ein Ausschnitt auch, nur sagen
    sie dort nichts. Der Meridianschnitt eines Torus ist ein Kreis, und eine
    Kreiseinpassung braucht keinen ganzen Kreis.

    Die Zahl, auf die es ankommt, ist der **Röhren**radius — an einer
    Verrundung ist er ihr Radius.
    """
    ring = trimesh.creation.torus(
        major_radius=20.0, minor_radius=5.0, major_sections=96, minor_sections=48
    )
    angle = np.arctan2(ring.triangles_center[:, 1], ring.triangles_center[:, 0])
    quarter = [int(index) for index in np.where((angle > 0.0) & (angle < math.pi / 2.0))[0]]

    fit = fit_torus(ring, quarter)

    assert fit is not None and fit.good, "a quarter of a ring is still a ring"
    assert fit.ring_radius == pytest.approx(20.0, abs=0.1)
    assert fit.tube_radius == pytest.approx(5.0, abs=0.1)


def test_too_small_a_piece_is_refused_instead_of_guessed() -> None:
    """Und darunter wird abgelehnt, nicht geraten (Regel 21, §41).

    Bei einem Zweiundzwanzig-Grad-Ausschnitt liegt der Ringradius um das
    Vierfache daneben — die Einpassung findet dann eine Form, die niemand
    gemeint hat. Auffallen muss das dem **Rückstand**, nicht einem Menschen:
    Er steigt auf 0,078 und damit über ``ROUND_TOLERANCE``, und ``good`` wird
    falsch. Ein Elftel-Ring kommt gar nicht mehr durch die Schutzbedingung.
    """
    ring = trimesh.creation.torus(
        major_radius=20.0, minor_radius=5.0, major_sections=96, minor_sections=48
    )
    angle = np.arctan2(ring.triangles_center[:, 1], ring.triangles_center[:, 0])
    sliver = [int(index) for index in np.where((angle > 0.0) & (angle < math.pi / 8.0))[0]]

    fit = fit_torus(ring, sliver)

    assert fit is None or not fit.good, "a sliver must not pass as a ring"


def test_a_fillet_no_longer_swallows_the_post_it_sits_on() -> None:
    """Das Alltagsteil, an dem die Erkennung bis zum 22.08.2026 nichts fand.

    Eine Säule mit verrundetem Fuß: Die Verrundung schließt **tangential** an —
    das ist ihr Zweck —, und die Fleckenbildung trennt an Knicken. Mantel und
    Kehle lagen deshalb in **einem** Fleck, auf den weder ein Zylinder noch ein
    Torus passte. Sieben ebene Flächen kamen heraus und sonst nichts: keine
    Mantelfläche, auf die der Agent hätte zeigen können, keine Passung, die sie
    findet, kein Eintrag im Steckbrief.
    """
    found = detect(plate("post_with_fillet.stl"))
    pins = [entry for entry in found.values() if entry.kind == "pin"]
    tori = [entry for entry in found.values() if entry.kind == "torus"]

    assert len(pins) == 1, f"the post is a pin: {sorted(found)}"
    assert pins[0].params["diameter"] == pytest.approx(12.0, abs=0.05)
    assert len(tori) == 1, f"the fillet is a torus: {sorted(found)}"
    assert tori[0].params["tube_diameter"] == pytest.approx(6.0, abs=0.05)


def test_a_rounded_edge_keeps_its_own_radius() -> None:
    """Der Fehlbefund, der schlimmer war als ein fehlender Befund.

    An einem Quader mit **einer** verrundeten Kante R 3 meldete die Erkennung
    einen Zapfen mit Ø 28,92 — fast so breit wie das Teil. Nicht „nichts
    gefunden", sondern etwas Falsches gefunden: §14 nennt einen Zapfen das,
    womit man eine Bohrung paart, und die Operationen aus ``applies_to`` boten
    sich daran an.

    Die Ursache saß **über** der Einpassung, nicht in ihr. Zwei ebene Facetten
    von 1110 und 510 mm² galten als gekrümmt, weil sie die Rundung berühren,
    und hängten sich ihrem Fleck an; die Kreiseinpassung gewichtet quadratisch,
    und vier Punkte in bis zu 25 mm Abstand ziehen einen Kreis von R 3 auf
    14,46. Der Löser war in Ordnung — er bekam den falschen Fleck.
    """
    found = detect(plate("block_with_rounded_edge.stl"))
    fillets = [entry for entry in found.values() if entry.kind == "fillet"]

    assert len(fillets) == 1, f"one rounded edge: {sorted(found)}"
    # **R 3, nicht Ø 6.** Eine Verrundung wird mit ihrem Radius bestellt,
    # gezeichnet und gemessen; der Durchmesser steht daneben, weil die
    # Zuordnung die Größe aus diesem Schlüssel liest (§21.2).
    assert fillets[0].params["radius"] == pytest.approx(3.0, abs=0.05)
    assert not [entry for entry in found.values() if entry.kind == "pin"], (
        "a rounded edge is not a pin — nothing pairs with it (§14)"
    )
    # Und die zwei großen Ebenen daneben sind wieder Flächen.
    assert sum(1 for entry in found.values() if entry.kind == "face") == 6


def test_the_residual_cannot_see_a_blown_up_circle() -> None:
    """Der Rückstand ist die letzte Schranke, und allein sieht er nichts.

    Er misst gegen den **eingepassten** Kreis, nicht gegen die Wirklichkeit —
    ein Bogen von neunzig Grad passt auf unendlich viele Kreise fast gleich
    gut. Und er normiert **relativ** zum Radius, belohnt also genau das, was er
    fangen soll: Dieselbe absolute Streuung ist bei r = 3 ein Viertel des
    Radius und bei r = 90 ein Promille.

    Gemessen an einem Viertelbogen eines Zylinders r = 3: Die Einpassung findet
    **r = 89,79** und meldet einen Rückstand von 0,0023 bei einer Schwelle von
    0,08. Der ``spread`` misst absolut und in Facettenbreiten — er meldet 0,11
    bei einer Schwelle von 0,02, und die Form wird abgelehnt.
    """
    import trimesh

    cylinder = trimesh.creation.cylinder(radius=3.0, height=30.0, sections=96)
    angle = np.arctan2(cylinder.triangles_center[:, 1], cylinder.triangles_center[:, 0])
    quarter = [int(index) for index in np.where((angle > 0.0) & (angle < math.pi / 2.0))[0]]

    fit = fit_cylinder(cylinder, quarter)

    assert fit is not None
    assert fit.radius > 50.0, "the fit really is that far off"
    assert fit.residual < CYLINDER_TOLERANCE, "and the residual really does not notice"
    assert not fit.good, "but the spread does"


def test_a_ring_is_not_a_heap_of_flat_faces() -> None:
    """Der Wächter gegen die Reparatur von oben.

    Die zweite Schwelle misst an der **Gesamtoberfläche** und nicht an der
    größten Facette — denn ein Torus besteht nur aus Mantelstreifen, seine
    größte Facette ist selbst einer, und jede läge damit bei fast hundert
    Prozent. Gegen die größte gemessen zerfiel ``torus_ring.stl`` in 288 ebene
    Flächen.
    """
    found = detect(plate("torus_ring.stl"))

    assert [entry.kind for entry in found.values()] == ["torus"], sorted(found)


def test_nothing_that_was_recognised_gets_split_again() -> None:
    """Die Nachtrennung greift **nur**, wo keine Form gefunden wurde.

    Grundsätzlich nachgetrennt zerfiel im Beispielprojekt *Aushöhlen und
    Teilen* ein Kegel in zwei — ein Kegel hat keine feste Krümmung, sein
    Querradius wächst stetig. Zwei gespiegelte Senkungen sehen für die
    Zuordnung ohnehin gleich aus, also hielt die Auswertung an und fragte
    viermal, welches Merkmal ``cone_1`` entspricht. In einem **mitgelieferten
    Beispiel**, dem freundlichsten Weg, den die Anwendung hat.

    Der Wächter dagegen ist die gesenkte Bohrung: ein einziger Kegel, und er
    muss einer bleiben.
    """
    cones = [
        entry for entry in detect(plate("plate_countersunk.stl")).values() if entry.kind == "cone"
    ]

    assert len(cones) == 1, f"one sink, not two: {[cone.id for cone in cones]}"


def test_a_chamfered_bore_is_one_bore_and_not_four() -> None:
    """Der Standardfall jeder Schraubenbohrung, und er lieferte vier Merkmale.

    Die Vereinigung von Bohrer und Fasenkegel setzt Punkte auf die
    Bohrungswand; die Boolesche Operation trianguliert sie darunter mit
    Knicken von siebzig bis neunzig Grad, und die Fleckenbildung trennt dort zu
    Recht. Heraus kamen **vier** Bohrungen für ein Loch — zwei mit
    ``through=True``, zwei mit ``through=False``.

    Für den Nutzer ist das schlimmer als eine fehlende Bohrung: Vier Merkmale
    an derselben Stelle sind für die Zuordnung vier gleich gute Kandidaten,
    also hält die Auswertung an und fragt bei **jeder** Auswertung — mit einer
    Frage, auf die es keine richtige Antwort gibt (§21.3).
    """
    found = detect(plate("plate_chamfer_and_taper.stl"))
    bores = [entry for entry in found.values() if entry.kind == "hole"]

    assert len(bores) == 1, f"one bore, not four: {sorted(found)}"
    assert bores[0].params["diameter"] == pytest.approx(6.0, abs=0.05)
    assert bores[0].params["through"] is True


def test_the_corpus_carries_all_three_kinds_of_cone() -> None:
    """§21.1 nennt drei: Senkung, Fase, Verjüngung. Der Korpus trug nur die
    Senkung, und zwar bis zum 22.08.2026 in zwei Dateien.

    Jeder grüne Lauf sagte damit nichts über die anderen beiden. Hier stehen
    Fase und Verjüngung nebeneinander — die eine ausgehöhlt, die andere
    aufgesetzt.
    """
    cones = detect_cones(plate("plate_chamfer_and_taper.stl"))
    by_shape = {entry.params["recess"]: entry for entry in cones}

    assert len(cones) == 2, f"a chamfer and a taper: {[cone.id for cone in cones]}"
    assert by_shape[True].params["diameter"] == pytest.approx(9.0, abs=0.1)
    assert by_shape[False].params["diameter"] == pytest.approx(10.0, abs=0.1)


def test_a_bore_beside_a_boss_still_goes_through() -> None:
    """Die Dicke des Körpers ist nicht die Dicke an der Bohrung.

    Die alte Prüfung mass die Spanne **aller** Punkte entlang der Achse: An
    einer 10 mm dicken Platte mit einem 15 mm hohen Zapfen daneben kam eine
    Dicke von 25 mm heraus, und die durchgehende Bohrung galt als Sackloch.
    Eine Platte mit einem Dom und einer Bohrung daneben ist ein Alltagsteil.

    Die Prüfung fragt heute nicht mehr nach Dicken, sondern danach, ob ein
    Dreieck über der Achse liegt — dem Zapfen daneben ist das gleichgültig.
    """
    bores = [
        entry
        for entry in detect(plate("plate_chamfer_and_taper.stl")).values()
        if entry.kind == "hole"
    ]

    assert bores[0].params["through"] is True


def test_a_full_cylinder_is_never_taken_for_a_fillet() -> None:
    """Die Gegenprobe, und sie ist über den ganzen Korpus gemessen.

    Getrennt wird an der Überdeckung um die Achse: Bohrungen und Zapfen
    überdecken 345 bis 356 Grad, eine verrundete Quaderkante 90. Dazwischen
    liegt nichts — die Schwelle bei 300 muss nicht kalibriert werden, sie sitzt
    in einem Loch.
    """
    for name in ("plate_holes.stl", "clean_figure.stl", "plate_chamfer_and_taper.stl"):
        found = detect(plate(name))

        # Ein Verbot über eine gefilterte Menge ist grün, solange die Menge
        # leer ist. Erst festhalten, dass auf jedem der drei Körper überhaupt
        # runde Merkmale erkannt werden — sonst prüft die Zeile darunter, dass
        # nichts nichts ist.
        round_ones = [entry for entry in found.values() if "diameter" in entry.params]
        assert round_ones, f"{name}: kein einziges rundes Merkmal erkannt"

        assert not [entry for entry in found.values() if entry.kind == "fillet"], (
            f"{name}: a whole cylinder is not a fillet"
        )


def test_a_thread_is_not_a_stack_of_eight_pins() -> None:
    """Ein M6-Gewinde meldete acht Zapfen, die es nicht gibt.

    Jede Windung ist für sich ein Zylinderstück — koaxial zu den anderen,
    gleich dick, einen Millimeter darüber, also genau die Steigung. §14 nennt
    einen Zapfen das, womit man eine Bohrung paart; mit einem Gewindegang
    paart niemand etwas. Und für die Zuordnung sind acht koaxiale gleich große
    Merkmale acht gleich gute Kandidaten.

    Das Gewinde selbst bleibt: Es entsteht in einem Baustein und trägt seinen
    Namen von dort (§21.1 — „Ein Gewinde sieht sie nicht"). Verworfen wird
    allein, was die Erkennung daneben stellt.
    """
    from app.core.bootstrap import load_operations
    from app.core.knowledge import profiles
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Gewinde",
        [
            OperationDraft(op="create_box", params={"width": 30.0, "depth": 30.0, "height": 10.0}),
            OperationDraft(
                op="insert_printed_thread",
                inputs=("obj_1",),
                params={"size": "M6", "length": 12.0, "internal": False, "z": 5.0},
            ),
        ],
    )
    result = evaluate(
        project.document,
        profiles.make_profile("centauri-carbon-2", "petg"),
        sources=ProjectSources(project),
    )
    entry = next(iter(result.scene.objects.values()))
    kinds = [feature.kind for feature in entry.features.values()]

    assert "pin" not in kinds, f"a thread turn is not a pin: {sorted(entry.features)}"
    assert kinds.count("thread") == 1, "and the thread itself stays"


def test_a_countersink_is_not_a_sphere() -> None:
    """Die Gegenprobe, und sie ist der Grund für die strengere Schwelle.

    Eine 90°-Senkung passt erstaunlich gut auf eine Kugel: gemessen ein
    Rückstand von 0,054, also **unter** der Schwelle, die für Zylinder und
    Kegel gilt. Die echte Kalotte liefert 0,0003 — zwei Größenordnungen
    darunter. Genau davor warnt §41: Ein Anpassungsverfahren, das Grundformen
    sucht, findet auch welche, die niemand gemeint hat, und die Reihenfolge der
    Prüfungen entscheidet, welchen Namen ein Fleck bekommt.
    """
    found = detect(plate("plate_countersunk.stl"))
    kinds = sorted({feature.kind for feature in found.values()})

    assert "sphere" not in kinds, f"the sink became a sphere: {kinds}"
    assert "torus" not in kinds, f"the sink became a torus: {kinds}"
    # Und was dort steht, steht weiter dort.
    assert "cone" in kinds and "hole" in kinds, kinds


def test_a_bore_is_never_read_as_a_torus() -> None:
    """Ein Zylinder ist ein Torus mit unendlichem Ringradius, die Einpassung
    findet an jeder Bohrung also einen. Sie darf ihn nur nicht behalten.
    """
    assert not detect_tori(plate("plate_holes.stl"))
    assert not detect_spheres(plate("plate_holes.stl"))


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


def test_one_ring_is_one_feature_and_not_two() -> None:
    """Ein Ring zerfällt in Flecken, und jeder wurde ein eigenes Merkmal.

    Im Bildschirmfoto eines Kunden standen drei Wülste untereinander: Ø 34,09,
    Ø 34,06 und Ø 34,03 mm. Drei Kanten oder eine, dreimal erkannt? Am Korpus
    nachgestellt kam derselbe einzelne Ring in **jeder** geprüften Vernetzung
    als zwei Merkmale heraus — 33,93 und 33,94 bei 48 Segmenten, 33,73 und
    33,75 bei 24. Für die Zuordnung sind zwei Merkmale an derselben Stelle zwei
    gleich gute Kandidaten, also hält die Auswertung an und fragt (§21.3).

    Zylinderflecken werden seit `4ae96ec` zusammengefasst; für Ringe fehlte das
    Gegenstück.
    """
    for sections, tube in ((48, 0.5), (24, 0.5), (96, 1.0)):
        ring = trimesh.creation.torus(
            major_radius=17.0, minor_radius=tube, major_sections=sections, minor_sections=12
        )
        found = [entry for entry in detect(MeshData(raw=ring)).values() if entry.kind == "torus"]

        assert len(found) == 1, f"{sections} Segmente: {[e.params['diameter'] for e in found]}"


def test_two_rings_above_each_other_stay_two() -> None:
    """Die Gegenprobe, und sie entscheidet über das Kriterium.

    Der **Rest** trennt die beiden Fälle nicht: Zwei Hälften eines Rings
    zusammengelegt streuen 0,00040 — und zwei verschiedene Ringe, fälschlich
    zusammengelegt, ebenfalls 0,00040. Was sie trennt, ist der Mittelpunkt.
    """
    lower = trimesh.creation.torus(
        major_radius=17.0, minor_radius=0.5, major_sections=48, minor_sections=12
    )
    upper = trimesh.creation.torus(
        major_radius=17.0, minor_radius=0.5, major_sections=48, minor_sections=12
    )
    upper.apply_translation((0.0, 0.0, 8.0))

    found = [
        entry
        for entry in detect(MeshData(raw=trimesh.util.concatenate([lower, upper]))).values()
        if entry.kind == "torus"
    ]

    assert len(found) == 2
    assert sorted(round(float(entry.params["centre"][2])) for entry in found) == [0, 8]


@pytest.mark.parametrize(
    ("name", "expected"),
    [("plate_holes.stl", 10), ("post_with_fillet.stl", 9), ("torus_ring.stl", 1)],
)
def test_detection_sees_the_same_part_whether_it_arrives_welded_or_not(
    name: str, expected: int
) -> None:
    """Dieselbe Datei, zweimal geladen, muss dieselbe Auskunft geben.

    Der Zwilling des Fundes vom 26.08.2026: ``detect_edge_loops`` fragte die
    **gespeicherte** Topologie statt der geometrischen und meldete an einer
    ungeschweißten STL eine offene Stelle je Dreieck. Das ist behoben — die
    übrigen ``detect_*`` fragten weiter dasselbe Falsche, und dort fällt es
    nicht als Übermaß auf, sondern als **Schweigen**: Roh geladen kam aus
    ``detect`` gar nichts zurück, obwohl dieselbe Datei verschweißt zehn, neun
    und ein Merkmal liefert.

    Ein Übermaß sieht jeder, ein Schweigen niemand — der Kunde liest „keine
    Merkmale erkannt" und hält es für eine Eigenschaft seines Teils. Und er hat
    keine Möglichkeit, es zu bemerken: Ob eine Datei mit gemeinsamen Ecken
    ankommt, entscheidet das Format, nicht er. ``generate.into_project`` lädt
    aus gutem Grund ungeschweißt, also trifft es ausgerechnet Weg 3.

    Geprüft wird auf **Gleichheit beider Wege** und nicht auf eine feste Zahl:
    Was die Erkennung findet, darf sich mit ihr weiterentwickeln — dass die
    Antwort vom Dateiformat abhängt, darf nie wieder passieren.
    """
    path = MESHES / name
    welded = MeshData.of(trimesh.load(path, process=True, force="mesh"))
    unwelded = MeshData.of(trimesh.load(path, process=False, force="mesh"))

    from_welded = detect(welded)
    from_unwelded = detect(unwelded)

    assert len(from_welded) == expected, f"der verschweißte Weg ist der Bezug: {name}"
    assert len(from_unwelded) == len(from_welded), (
        f"{name}: roh {len(from_unwelded)} Merkmale, verschweißt {len(from_welded)} — "
        "die Auskunft hängt am Dateiformat"
    )


def test_the_same_mesh_is_not_examined_twice() -> None:
    """Ein bitgleiches Netz kann keine anderen Merkmale haben.

    Die Erkennung läuft nach **jeder** Operation, und das ist richtig (§21.2):
    Sonst wäre ``hole_3`` in Schritt fünf ein anderes Loch als in Schritt vier.
    Sie lief aber auch dann, wenn die Geometrie gar nicht gerechnet wurde —
    nach einem Treffer im Plattencache. Gemessen an den neun Beispielprojekten,
    je drei Auswertungen wie beim Öffnen: 11,65 s Erkennung, davon **7,52 s auf
    bitgleichen Netzen**.

    Geprüft wird beides, was ein Cache falsch machen kann: dass er antwortet
    (sonst wäre er keiner) und dass er dasselbe antwortet (sonst wäre er
    schlimmer als keiner).
    """
    forget_cache()
    mesh = MeshData.of(trimesh.load(MESHES / "plate_holes.stl", process=False, force="mesh"))

    first = detect(mesh)
    assert first, "ohne erkannte Merkmale prüft der Test nichts"
    second = detect(mesh)

    assert second == first, "dasselbe Netz, andere Merkmale"
    assert second is not first, "der Aufrufer darf sein Ergebnis behalten dürfen"

    # Ein zweites Netz mit denselben Zahlen, aber eigenen Feldern: Der
    # Schlüssel ist der Inhalt und nicht die Objektkennung — ``id()`` wird
    # wiederverwendet, sobald ein Körper freigegeben ist.
    twin = MeshData.of(trimesh.load(MESHES / "plate_holes.stl", process=False, force="mesh"))
    assert detect(twin) == first, "gleicher Inhalt, gleiche Antwort"


def test_a_changed_mesh_is_examined_again() -> None:
    """Und die Gegenrichtung, ohne die der Test oben eine Falle wäre.

    Ein Cache, der auf ein *verändertes* Netz die alte Antwort gibt, ist der
    schlimmste Fall überhaupt: Der Kunde bohrt, und der Merkmalsbaum zeigt
    weiter das Teil von vorher.
    """
    forget_cache()
    body = trimesh.load(MESHES / "plate_holes.stl", process=False, force="mesh")
    before = detect(MeshData.of(body))

    moved = body.copy()
    moved.apply_translation([0.0, 0.0, 7.0])
    after = detect(MeshData.of(moved))

    assert after, "das verschobene Teil hat dieselben Merkmale, nur woanders"
    heights_before = sorted(
        round(float(f.params["centre"][2]), 2) for f in before.values() if "centre" in f.params
    )
    heights_after = sorted(
        round(float(f.params["centre"][2]), 2) for f in after.values() if "centre" in f.params
    )
    assert heights_before, "ohne Höhen misst der Vergleich nichts"
    assert heights_after != heights_before, "das verschobene Netz bekam die alte Antwort"


def test_a_long_history_stays_in_the_feature_cache() -> None:
    """Ein warmer langer Verlauf darf den Cache nicht beim Lesen leeren.

    Das Kundenmodell hat 132 verschiedene Zwischenkörper. Mit der früheren
    Grenze von 32 verdrängten die ersten Schritte eines neuen Durchlaufs genau
    die später noch benötigten Einträge; trotz vollständiger Treffer im
    Ergebnis-Cache wurde jedes Merkmal erneut gesucht.
    """
    forget_cache()
    body = trimesh.load(MESHES / "cube_clean.stl", process=False, force="mesh")
    history_length = 132

    for step in range(history_length):
        moved = body.copy()
        moved.apply_translation([float(step) * 3.0, 0.0, 0.0])
        detect(MeshData.of(moved))

    assert len(_FEATURE_CACHE) == history_length, (
        "der Cache muss alle Zwischenkörper des gemessenen Kundenverlaufs halten"
    )


def test_the_cache_keeps_only_what_it_promises() -> None:
    """Die Grenze hält, sonst wächst er über die Laufzeit eines Tages hinaus."""
    forget_cache()
    body = trimesh.load(MESHES / "cube_clean.stl", process=False, force="mesh")

    for step in range(CACHE_LIMIT + 5):
        moved = body.copy()
        moved.apply_translation([float(step) * 3.0, 0.0, 0.0])
        detect(MeshData.of(moved))

    assert len(_FEATURE_CACHE) == CACHE_LIMIT, (
        f"{len(_FEATURE_CACHE)} gemerkte Netze bei einer Grenze von {CACHE_LIMIT}"
    )


def test_the_inner_wall_of_a_hollow_box_knows_it_is_inside() -> None:
    """Innen- und Außenwand zeigen in dieselbe Richtung und hießen gleich.

    Handbuchbild vom 02.09.2026, Objektbaum der ausgehöhlten Dose: „Rückseite
    3200 mm²" und „Rückseite 2797 mm²", viermal so — der Kunde konnte die
    Innenwand nur an der Zahl erkennen. Die Wahrnehmung entscheidet jetzt an
    der Stelle, an der sie alle Flächen kennt: Eine Fläche liegt innen, wenn
    eine gleichgerichtete weiter außen liegt.
    """
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.perceive.features import detect

    outer = trimesh.creation.box(extents=(40.0, 30.0, 20.0))
    outer.apply_translation((0.0, 0.0, 10.0))
    cavity = trimesh.creation.box(extents=(34.0, 24.0, 20.0))
    cavity.apply_translation((0.0, 0.0, 13.0 + 10.0))  # oben offen, Boden bleibt
    hollow = trimesh.boolean.difference([outer, cavity])
    faces = [f for f in detect(MeshData.of(hollow)).values() if f.kind == "face"]

    def side(normal: tuple[float, float, float], *, inner: bool) -> list:
        return [
            f
            for f in faces
            if tuple(round(v) for v in f.params["normal"]) == normal
            and bool(f.params.get("inner")) is inner
        ]

    # Die Rückwand: außen bei y = +15 zeigt +y; die Innenwand vorn zeigt auch +y.
    assert side((0, 1, 0), inner=False), "die Außenwand nach hinten gilt als außen"
    assert side((0, 1, 0), inner=True), "die Innenwand nach hinten gilt als innen"
    assert side((0, -1, 0), inner=False) and side((0, -1, 0), inner=True)
    # Der Boden: nur eine Fläche zeigt nach unten — außen. Nach oben zeigen
    # zwei: der Rand der Wände bei z = 20 (außen) und der Boden innen bei
    # z = 3 — und der liegt unter dem Rand, also innen. Genau so heißt er im
    # Objektbaum: „Oberseite innen" ist der Grund der Dose.
    assert side((0, 0, -1), inner=False) and not side((0, 0, -1), inner=True)
    assert side((0, 0, 1), inner=False), "der Rand der Wände ist außen"
    assert side((0, 0, 1), inner=True), "der Boden innen liegt unter dem Rand"


def test_a_solid_box_has_no_inner_faces() -> None:
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.perceive.features import detect

    box = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    faces = [f for f in detect(MeshData.of(box)).values() if f.kind == "face"]

    assert len(faces) == 6
    assert not any(f.params.get("inner") for f in faces)


def test_an_inner_face_is_named_as_such() -> None:
    from app.core.types import Feature
    from app.ui.labels import feature_name

    outer = Feature(
        id="face_1",
        kind="face",
        provenance="detected",
        params={"normal": (0.0, 1.0, 0.0), "centre": (0.0, 15.0, 10.0), "area": 800.0},
    )
    inner = Feature(
        id="face_2",
        kind="face",
        provenance="detected",
        params={
            "normal": (0.0, 1.0, 0.0),
            "centre": (0.0, -12.0, 12.0),
            "area": 600.0,
            "inner": True,
        },
    )

    assert feature_name("face_1", outer) != feature_name("face_2", inner)
    assert feature_name("face_1", outer) in feature_name("face_2", inner)


def test_a_fillet_smaller_than_any_tool_is_none() -> None:
    """Dieselbe Schranke wie bei Bohrung und Zapfen — sie fehlte hier.

    **Der Befund (3d-druck-7f, 03.09.2026):** Im Objektbaum eines Kundenmodells
    standen Zeilen mit „Hohlkehle R0,00 mm", dazu eine ganze Leiter nach unten
    — R0,01, R0,03, R0,20. Gemessen an „Blessed Family — Heart Script Decor":
    109 erkannte Verrundungen, die kleinste mit **0,0007 mm** Radius, und
    zweiundzwanzig unter einer Extrusionsbahn (0,42 mm). Das ist Tesselierung
    und keine Kante: Wo ein paar Dreiecke zufällig um eine Achse stehen,
    findet der Fit einen Zylinderausschnitt.

    `MIN_CYLINDER_DIAMETER` gab es längst, mit genau dieser Begründung — „was
    für kein Werkzeug zu klein ist, ist für keine Passung zu klein" —, und sie
    galt für Bohrungen und Zapfen. Der Kommentar bei den Zapfen sagt sogar
    ausdrücklich „dieselbe Schranke wie bei der Bohrung"; die Verrundung war
    die dritte, an die niemand gedacht hat.

    Geprüft wird an einem Quader mit zwei verrundeten Kanten: eine über der
    Schranke, eine darunter. Der Test nimmt sie über die Passungen entgegen,
    damit er ohne den vollen Erkennungslauf auskommt.
    """
    from dataclasses import replace

    from app.core.perceive.features import (
        MIN_CYLINDER_DIAMETER,
        CylinderFit,
        detect_fillets,
    )

    mesh = MeshData(trimesh.creation.box(extents=(20.0, 20.0, 20.0)))
    gross = CylinderFit(
        axis=(0.0, 0.0, 1.0),
        centre=(0.0, 0.0, 0.0),
        radius=3.0,
        residual=0.0,
        inward=False,
        spread=0.0,
    )
    winzig = replace(gross, radius=MIN_CYLINDER_DIAMETER / 2.0 - 0.01)
    genau = replace(gross, radius=MIN_CYLINDER_DIAMETER / 2.0)

    fläche = tuple(range(6))
    gefunden = detect_fillets(mesh, [(gross, list(fläche)), (winzig, list(fläche))])

    assert [f.params["radius"] for f in gefunden] == [3.0], (
        "was für kein Werkzeug groß genug ist, ist auch keine Verrundung"
    )
    assert [f.id for f in gefunden] == ["fillet_1"], (
        "und die Nummern bleiben lückenlos — eine fillet_2 ohne fillet_1 wäre "
        "ein Verweis ins Leere (§21.2)"
    )

    auf_der_grenze = detect_fillets(mesh, [(genau, list(fläche))])
    assert len(auf_der_grenze) == 1, "genau auf der Schranke zählt noch"
