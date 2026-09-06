"""Merkmalserkennung gegen eine Platte mit bekannten Maßen (§21.1, §40).

plate_holes.stl ist 80 x 50 x 8 mm mit vier Bohrungen zu 5,2 mm — jede Zahl,
die die Erkennung erzeugt, lässt sich also prüfen statt bewundern.
"""

from __future__ import annotations

import dataclasses
import math
import re
from pathlib import Path

import numpy as np
import pytest
import trimesh

from app.core.geom.mesh import MeshData, read_mesh
from app.core.ingest.loader import normalise
from app.core.perceive import features as features_module
from app.core.perceive.features import (
    _FEATURE_CACHE,
    CACHE_LIMIT,
    CYLINDER_TOLERANCE,
    EDGE_LOOP_LIMIT,
    FREEFORM_ROUND_COUNT,
    FREEFORM_ROUND_SHARE,
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
    fit_sphere,
    fit_torus,
    forget_cache,
    freeform_dropped,
    is_a_freeform,
)
from app.core.perceive.relations import widening_at_the_mouth
from app.core.types import Feature, Profile

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

    def counted(mesh: MeshData, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        return original(mesh, **kwargs)

    monkeypatch.setattr(features, "_fitted", counted)
    features.detect(plate())

    assert calls == 1, f"the search ran {calls} times for one detection"


def test_the_planar_mask_is_shared_by_fits_and_faces(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die beiden Erkennungsphasen brauchen dieselbe Maske nur einmal."""
    original = features_module._large_facet_faces
    calls = 0

    def counted(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        return original(*args, **kwargs)

    monkeypatch.setattr(features_module, "_large_facet_faces", counted)
    forget_cache()
    found = detect(plate())

    assert calls == 1
    assert any(feature.kind == "hole" for feature in found.values())
    assert any(feature.kind == "face" for feature in found.values())


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


def test_an_extruded_curve_wall_is_not_a_sphere_at_any_height() -> None:
    """Ein senkrecht extrudierter Kurvenzug bestimmt keinen Kugelmittelpunkt.

    Die Mantelnormalen haben keine Z-Komponente. Damit hat das Kugelsystem nur
    Rang drei: Eine Verschiebung in Z darf aus demselben Fleck weder eine
    andere Kugel noch ein anderes Güteurteil machen.
    """

    def wall_at(z_offset: float) -> tuple[trimesh.Trimesh, list[int]]:
        angles = np.linspace(-0.04, 0.04, 5)
        lower = np.column_stack(
            [100.0 * np.cos(angles), 100.0 * np.sin(angles), np.full(5, z_offset)]
        )
        upper = lower.copy()
        upper[:, 2] += 10.0
        vertices = np.vstack([lower, upper])
        faces: list[tuple[int, int, int]] = []
        for index in range(4):
            faces.extend(
                [
                    (index, index + 1, index + 6),
                    (index, index + 6, index + 5),
                ]
            )
        body = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
        return body, list(range(len(faces)))

    for z_offset in (0.0, 20.0):
        body, patch = wall_at(z_offset)
        assert (
            np.linalg.matrix_rank(np.column_stack([body.face_normals[patch], np.ones(len(patch))]))
            == 3
        )
        assert fit_sphere(body, patch) is None


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


@pytest.mark.parametrize("phase", ["fit_cone", "detect_faces", "_shapes_on_a_freeform"])
def test_cancelled_recognition_does_not_fill_the_caches(
    monkeypatch: pytest.MonkeyPatch, phase: str
) -> None:
    """Abbruch im Fit, zwischen Detektoren und vor Veröffentlichung bleibt ohne Teilresultat."""
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    mesh = plate()
    vertices, faces = mesh.raw.vertices.copy(), mesh.raw.faces.copy()
    signal = CancelSignal()
    forget_cache()
    original = getattr(features_module, phase)
    calls = 0

    def cancel_after_phase(*args: object, **kwargs: object) -> object:
        nonlocal calls
        calls += 1
        result = original(*args, **kwargs)
        signal.cancel()
        return result

    with monkeypatch.context() as patch:
        patch.setattr(features_module, phase, cancel_after_phase)
        with pytest.raises(OperationCancelled):
            detect(mesh, check_cancelled=signal.raise_if_cancelled)

    assert calls == 1, "nach dem Abbruch darf kein weiterer Fleck derselben Phase rechnen"
    assert not features_module._FEATURE_CACHE
    assert not features_module._CACHE_INDICES
    assert not features_module._FREEFORM_DROPPED
    np.testing.assert_array_equal(mesh.raw.vertices, vertices)
    np.testing.assert_array_equal(mesh.raw.faces, faces)
    signal.reset()
    assert detect(mesh, check_cancelled=signal.raise_if_cancelled)


def test_cancelled_recognition_does_not_reorder_a_warm_cache() -> None:
    """Auch ein schneller Cachetreffer achtet den schon verlangten Abbruch."""
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    forget_cache()
    first, second = cube(), plate()
    detect(first)
    detect(second)
    before = list(features_module._FEATURE_CACHE.items())
    signal = CancelSignal()
    signal.cancel()

    with pytest.raises(OperationCancelled):
        detect(first, check_cancelled=signal.raise_if_cancelled)

    assert list(features_module._FEATURE_CACHE.items()) == before


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


# --- Was der Kunde mit einem erkannten Merkmal tun kann (Panel, 03.09.2026) --------


def test_the_actions_of_a_bore_come_with_their_measured_values() -> None:
    """Die Auskunft fürs Merkmalspanel — eine Liste, kein Nachschlagewerk.

    Robert am 03.09.2026: „evtl noch ein eigenes panel damit man nicht für
    alles rechtsklick machen muss übersichtlich, verständlich innovativ und
    intuitiv." Der Entwurf dazu ist, dass eine geänderte Zahl **die Operation
    ist**: Das Panel zeigt, was Solidon gemessen hat, und der Kunde ändert es.

    Damit muss jedes Feld seinen **heutigen** Wert mitbringen — eine Vorgabe,
    die nicht der gemessene Wert ist, wäre eine stille Änderung, sobald jemand
    auf Übernehmen drückt.

    **Abgeleitet aus dem Register, nicht aus einer zweiten Tabelle.** Welche
    Operationen für eine Merkmalsart gelten, steht in ihren ``applies_to``;
    eine Liste daneben, die dasselbe noch einmal sagt, weiß beim nächsten
    Registereintrag die Hälfte.
    """
    from app.core.bootstrap import load_operations
    from app.core.perceive.actions import actions_for
    from app.core.types import Feature

    load_operations()
    bore = Feature(
        id="hole_1",
        kind="hole",
        provenance="detected",
        params={
            "centre": (-15.0, 0.0, 2.0),
            "axis": (0.0, 0.0, 1.0),
            "diameter": 8.0,
            "depth": 20.0,
            "through": True,
        },
    )

    actions = actions_for(bore)
    by_op = {entry.op: entry for entry in actions if entry.op}

    assert "move_feature" in by_op, sorted(by_op)
    assert "remove_feature" in by_op
    assert "rotate_feature" in by_op

    move = by_op["move_feature"]
    fields = {field.name: field for field in move.fields}
    assert fields["x"].value == pytest.approx(-15.0), "die Vorgabe ist der gemessene Ort"
    assert fields["y"].value == pytest.approx(0.0)
    assert fields["z"].value == pytest.approx(2.0)
    assert fields["x"].unit == "mm" and fields["x"].kind == "length"
    assert "at_feature" not in fields, "die Kennung wählt das Panel selbst, sie ist kein Feld"

    turn = by_op["rotate_feature"]
    turn_fields = {field.name: field for field in turn.fields}
    assert turn_fields["axis"].kind == "choice"
    assert [value for value, _label in turn_fields["axis"].choices] == ["x", "y", "z"]
    assert turn_fields["angle"].kind == "angle"

    assert by_op["remove_feature"].fields == (), "eine Handlung ohne Felder ist ein Knopf"


def test_an_edge_loop_is_told_why_nothing_applies() -> None:
    """Was nicht gilt, kommt **mit** — als Satz, nicht als Lücke.

    Ein Panel, das bei einer Kantenschleife nichts zeigt, lässt den Kunden
    raten, ob die Handlungen fehlen oder vergessen wurden. Eine Zeile
    „Verschieben — eine offene Kantenschleife ist ein Loch im Netz" beantwortet
    die Frage und beendet das Suchen (Entwurf 3d-druck-d4, 03.09.2026).
    """
    from app.core.bootstrap import load_operations
    from app.core.perceive.actions import actions_for
    from app.core.types import Feature

    load_operations()
    loop = Feature(
        id="edge_1",
        kind="edge_loop",
        provenance="detected",
        params={"centre": (0.0, 0.0, 0.0), "open_edges": 12},
    )

    actions = actions_for(loop)

    assert actions, "auch hier steht etwas — nur eben, warum es nicht geht"
    assert all(entry.op is None for entry in actions), [entry.op for entry in actions]
    assert all(str(entry.reason) for entry in actions), "jede Zeile trägt ihren Grund"
    assert any("Netz" in str(entry.reason) for entry in actions)


def test_no_feature_is_smaller_than_the_tool_that_would_make_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Kegel, Kugel und Torus hatten die Werkzeugschranke auch nicht.

    **Der Befund, eine Stunde nach der Verrundung (03.09.2026):** Ich hatte
    die Schranke bei `detect_fillets` nachgetragen und in den Kommentar
    geschrieben, sie habe „hier als Einziger" gefehlt. Gemessen an Roberts
    Modellen stimmte das nicht — `garden-hose-holder.3mf` (392 532 Dreiecke)
    lieferte **1130 Merkmale**: 497 Kugeln, 421 Tori, 183 Kegel, und **257
    davon trugen ein Maß unter einer Extrusionsbahn** (0,42 mm), der kleinste
    Kegel mit 0,0074 mm.

    Der Suchfehler dahinter ist der lehrreiche Teil: Ich hatte nach den
    Aufrufern derselben *Zylinder*-Einpassung gesucht und damit genau die drei
    Arten übersehen, die eine andere benutzen. Danach 834 Merkmale, keines
    mehr unter einer Bahn.

    Robert am selben Tag: „wir brauchen auch nur Merkmale usw, die auch von
    der Größenordnung zum 3D-Drucker passen und sinnvoll sind."

    Beim Torus entscheidet das **kleinere** der beiden Maße: Ein Ring von
    40 mm aus einem Rohr von drei Zehnteln ist nichts, was ein Drucker legen
    kann.
    """
    from dataclasses import replace

    from app.core.perceive.features import (
        MIN_CYLINDER_DIAMETER,
        ConeFit,
        SphereFit,
        TorusFit,
        detect_cones,
        detect_spheres,
        detect_tori,
    )

    mesh = MeshData(trimesh.creation.box(extents=(20.0, 20.0, 20.0)))
    fläche = list(range(6))
    winzig = MIN_CYLINDER_DIAMETER / 2.0 - 0.01
    genau = MIN_CYLINDER_DIAMETER / 2.0

    kegel = ConeFit(
        axis=(0.0, 0.0, 1.0),
        apex=(0.0, 0.0, 0.0),
        centre=(0.0, 0.0, 0.0),
        half_angle=45.0,
        radius=3.0,
        residual=0.0,
        recess=False,
    )
    # Dieser Test isoliert die Werkzeuggröße. Die geometrische Kegelgüte prüft
    # ``test_cone_fit_quality.py`` an echten Flächen statt an Würfelflächen.
    monkeypatch.setattr(features_module, "_cone_is_recognisable", lambda *_args: True)
    gefunden = detect_cones(mesh, [(kegel, fläche), (replace(kegel, radius=winzig), fläche)])
    assert [f.params["diameter"] for f in gefunden] == [6.0], "ein Kegel unter Werkzeuggröße"
    assert [f.id for f in gefunden] == ["cone_1"], "und die Nummern bleiben lückenlos"
    assert len(detect_cones(mesh, [(replace(kegel, radius=genau), fläche)])) == 1

    kugel = SphereFit(centre=(0.0, 0.0, 0.0), radius=3.0, residual=0.0, recess=False)
    # Dieser Test isoliert die Werkzeuggröße. Die geometrische Kugelgüte prüft
    # ``test_sphere_fit_quality.py`` an echten Flächen statt an Würfelflächen.
    monkeypatch.setattr(features_module, "_sphere_is_recognisable", lambda *_args: True)
    gefunden = detect_spheres(mesh, [(kugel, fläche), (replace(kugel, radius=winzig), fläche)])
    assert [f.params["diameter"] for f in gefunden] == [6.0], "eine Kugel unter Werkzeuggröße"
    assert [f.id for f in gefunden] == ["sphere_1"]
    assert len(detect_spheres(mesh, [(replace(kugel, radius=genau), fläche)])) == 1

    torus = TorusFit(
        axis=(0.0, 0.0, 1.0),
        centre=(0.0, 0.0, 0.0),
        ring_radius=8.0,
        tube_radius=2.0,
        residual=0.0,
        recess=False,
    )
    # Entsprechend gehört die Torusgüte in ``test_torus_fit_quality.py``.
    monkeypatch.setattr(features_module, "_torus_is_recognisable", lambda *_args: True)
    # **Der Ring ist groß, die Röhre nicht** — genau der Fall, den ein Blick
    # allein auf ``diameter`` durchgelassen hätte.
    dünn = replace(torus, tube_radius=winzig)
    gefunden = detect_tori(mesh, [(torus, fläche), (dünn, fläche)])
    assert [f.params["tube_diameter"] for f in gefunden] == [4.0], (
        "ein Ring von 16 mm aus einem Rohr von einem Viertel ist nicht druckbar"
    )
    assert [f.id for f in gefunden] == ["torus_1"]
    # Und andersherum: winziger Ring, dicke Röhre — auch das ist nichts.
    gestaucht = replace(torus, ring_radius=winzig)
    assert detect_tori(mesh, [(gestaucht, fläche)]) == []


def test_the_operation_refuses_exactly_what_the_panel_greys_out() -> None:
    """Anschluss: Hinsehen und Ausführen antworten dasselbe.

    Das Panel graut eine Zeile aus und schreibt einen Grund daneben; der Kern
    lehnt denselben Aufruf ab und nennt einen Grund. Solange beides aus
    derselben Tabelle kommt, kann es nicht auseinanderlaufen — und dass es aus
    derselben kommt, prüft dieser Test und nicht ein Kommentar.

    Der Fall, den er fängt: Bis zum 03.09.2026 führte ``geom.prepare_ops`` eine
    zweite Ausgabe der Gründetabelle mit denselben fünf Sätzen. Zwei davon
    waren dort veraltet, und niemand hätte es gemerkt — ein Satz, den nur der
    Chat zu sehen bekommt, wird von keinem Bildschirmfoto widerlegt.
    """
    from app.core.bootstrap import load_operations
    from app.core.perceive.actions import ACTION_ORDER, actions_for, reason_against
    from app.core.registry import FEATURE_KINDS
    from app.core.types import Feature

    load_operations()
    for kind in FEATURE_KINDS:
        feature = Feature(
            id=f"{kind}_1",
            kind=kind,
            provenance="detected",
            params={"centre": (0.0, 0.0, 0.0), "axis": (0.0, 0.0, 1.0), "diameter": 6.0},
        )
        for row, action in zip(ACTION_ORDER, actions_for(feature), strict=True):
            for op in row:
                against = reason_against(op, kind)
                if action.op == op:
                    assert against is None, f"{kind}/{op}: das Panel bietet es an"
                else:
                    assert against is not None, f"{kind}/{op}: das Panel bietet es nicht an"
                    assert str(against), f"{kind}/{op}: der Grund ist leer"


def test_a_torus_is_told_it_belongs_to_what_it_encircles() -> None:
    """Ein Ring fiel bis zum 03.09.2026 in den Auffangsatz.

    ``torus`` wird erkannt — ``detect_tori`` liefert ihn, und der Objektbaum
    nennt ihn *Kehle* oder *Wulst* —, stand aber in keiner der beiden
    Gründetabellen. Das Panel sagte deshalb „Für diese Art von Merkmal gibt es
    noch keine Handlung", viermal, ohne Grund und ohne Ausweg. Der Satz war
    nicht falsch, er war leer.

    Ein Ring ist fast nie für sich da: Er ist eine Rille um eine Bohrung oder
    ein Wulst um einen Zapfen. Versetzt man ihn allein, läge die Rille neben
    ihrer Bohrung — und genau das sagt die Zeile jetzt, samt dem Weg, der
    stattdessen geht.
    """
    from app.core.bootstrap import load_operations
    from app.core.perceive.actions import actions_for
    from app.core.types import Feature

    load_operations()
    ring = Feature(
        id="torus_1",
        kind="torus",
        provenance="detected",
        params={"centre": (0.0, 0.0, 0.0), "axis": (0.0, 0.0, 1.0), "diameter": 12.0},
    )

    actions = actions_for(ring)

    assert actions, "auch hier steht etwas"
    assert all(entry.op is None for entry in actions), [entry.op for entry in actions]
    assert any("Rille" in str(entry.reason) for entry in actions), [
        str(entry.reason) for entry in actions
    ]


def test_the_panel_offers_duplicating_beside_the_original() -> None:
    """Die Vorgabe ist hier **nicht** der gemessene Wert, und das mit Absicht.

    Sonst gilt im Panel die gemessene Zahl (``_FROM_FEATURE``), damit ein Klick
    auf Übernehmen nichts still ändert. Beim Verdoppeln wäre die gemessene
    Mitte die Stelle, an der das Merkmal schon liegt: eine Boolesche auf sich
    selbst, ein Schritt im Verlauf und dasselbe Teil im Bild. Um einen
    Durchmesser versetzt liegt die Kopie neben dem Original und ist zu sehen
    (Vorschlag 3d-druck-d4, 03.09.2026).

    Y und Z bleiben dagegen gemessen — versetzt wird in **eine** Richtung, und
    welche das ist, soll man an der Zahl erkennen.
    """
    from app.core.bootstrap import load_operations
    from app.core.perceive.actions import actions_for
    from app.core.types import Feature

    load_operations()
    bore = Feature(
        id="hole_1",
        kind="hole",
        provenance="detected",
        params={
            "centre": (-15.0, 2.0, 3.0),
            "axis": (0.0, 0.0, 1.0),
            "diameter": 8.0,
            "depth": 20.0,
            "through": True,
        },
    )

    row = next(entry for entry in actions_for(bore) if entry.op == "duplicate_feature")
    fields = {field.name: field.value for field in row.fields}

    assert fields["x"] == pytest.approx(-7.0), fields
    assert fields["y"] == pytest.approx(2.0), fields
    assert fields["z"] == pytest.approx(3.0), fields


def test_one_countersink_is_one_cone(profile: Profile) -> None:
    """Eine Senkung stand dreimal im Objektbaum.

    **Befund 3d-druck-a0, 03.09.2026**, beim Gegenlesen des Changelogs
    gefunden und nicht bei einer Suche danach: Ein Quader mit **einer**
    durchgehenden Bohrung Ø 6 und **einer** Senkung Ø 12 lieferte **drei**
    Kegel.

    | | Dreiecke | Ø | Achse | Halbwinkel |
    |---|---|---|---|---|
    | cone_1 | 56 | 11,98 | Z | 44,94° |
    | cone_2 | 8 | 11,98 | Z | 44,94° |
    | cone_3 | 37 | 12,88 | 3° verkippt | 47,14° |

    Die drei Flecken sind **disjunkt** — zusammen 101 Dreiecke, keine
    gemeinsame Fläche. Es war also ein Mantel in drei Stücken und kein
    dreifacher Fit; der Unterschied entscheidet, ob eine Zusammenführung die
    Antwort ist oder eine bessere Einpassung.

    **Das dritte Geschwister ohne die Regel:** `_merged_cylinders` gibt es seit
    je, `_merged_tori` seit einem Kundenbild mit drei Wülsten — für den Kegel
    hat sie niemand gebaut. Dieselbe Familie wie die Werkzeugschranke, die
    Bohrung und Zapfen hatten und Verrundung, Kegel, Kugel und Torus nicht.

    Warum es dem Kunden weh tut: Drei Senkungen, wo eine ist. Er klickt eine
    an, und die Operationen antworten je nach Zeile verschieden — zwei lehnen
    mit gutem Grund ab, die dritte ändert 0,4 mm³ an einer Stelle, die er nicht
    gemeint hat.

    Geprüft wird beides: dass eine Senkung **eine** wird, und dass zwei
    Senkungen **zwei** bleiben.

    **Was dieser Test ausdrücklich nicht misst:** :data:`CONE_SAME_ANGLE`.
    Gegengeprobt — die Schranke entschärft, und der Test bleibt grün. Das ist
    kein Mangel, sondern die Sache selbst: Sie ist ein Vorfilter, der einen
    groben Ausreißer abfängt, bevor ein Fit dafür gerechnet wird. Getrennt
    wird über die Spitze und darüber, dass der gemeinsame Fit ``good`` bleibt
    — und **das** misst der zweite Teil hier. Wer die Winkelschranke prüfen
    will, braucht zwei Kegel mit derselben Spitze und derselben Achse bei
    verschiedenem Winkel; die schneiden einander und kommen an einem Körper
    nicht vor.
    """
    from app.core.geom.prepare_ops import countersink, drill

    def with_a_countersink(body: MeshData, x: float) -> MeshData:
        bored = drill(
            body,
            position=(x, 0.0, 10.0),
            axis="z",
            diameter=6.0,
            profile=profile,
            compensate=False,
        ).mesh
        return countersink(
            bored, position=(x, 0.0, 10.0), axis="z", diameter=12.0, profile=profile
        ).mesh

    block = MeshData(trimesh.creation.box(extents=(60.0, 40.0, 20.0)))

    single = detect_cones(with_a_countersink(block, 15.0))
    assert len(single) == 1, (
        f"eine Senkung ist ein Kegel, nicht {len(single)} — "
        f"Ø {[round(float(f.params['diameter']), 2) for f in single]}"
    )
    assert float(single[0].params["diameter"]) == pytest.approx(12.0, abs=0.15), (
        "und er trägt das Maß der Senkung, nicht das eines Ausschnitts"
    )
    assert len(single[0].face_indices) > 90, "der zusammengeführte Fleck trägt den ganzen Mantel"

    # **Die Gegenprobe gehört in denselben Test**: Eine Zusammenführung, die
    # zu viel zusammenführt, sieht am ersten Fall genauso gut aus.
    both = with_a_countersink(with_a_countersink(block, -15.0), 15.0)
    pair = detect_cones(both)
    assert len(pair) == 2, f"zwei Senkungen bleiben zwei, nicht {len(pair)}"
    apart = abs(float(pair[0].params["centre"][0]) - float(pair[1].params["centre"][0]))
    assert apart == pytest.approx(30.0, abs=0.5), "und zwar an ihren beiden Orten"


def test_the_cache_counts_weight_and_not_only_entries() -> None:
    """Die Cache-Grenze zählte Einträge, und die kosten sehr verschieden viel.

    **Gemessen am 03.09.2026**, angestoßen von Roberts Frage nach Dingen, die
    gesetzt und nie abgeräumt werden: Ein Eintrag für
    `garden-hose-holder.3mf` (392 532 Dreiecke, 797 Merkmale) wiegt **3,9 MiB**
    — davon 2,7 allein an Flächenindizes, 97 425 Stück zu je 28 Byte. Bei
    :data:`CACHE_LIMIT` von 256 hielte der Cache damit **991 MiB**, und der
    Kundenverlauf, mit dem die 256 begründet sind (132 verschiedene Netze),
    käme auf gut 500.

    Abgeräumt **wurde** also — die Grenze zählte nur das Falsche. Für ein
    kleines Teil mit tausend Indizes je Eintrag sind 256 Einträge sieben
    Megabyte, und dort soll der Cache voll ausgenutzt werden; für ein großes
    kostet derselbe Zähler das Hundertfache.

    Geprüft wird deshalb beides: dass die Anzahl die kleinen weiter deckelt,
    und dass ein einzelner Eintrag über der Gewichtsgrenze trotzdem bleibt —
    ihn wegzuwerfen hieße, ihn beim nächsten Aufruf sofort neu zu rechnen, und
    der Cache wäre nicht begrenzt, sondern aus.
    """
    from app.core.perceive.features import (
        _CACHE_INDICES,
        _FEATURE_CACHE,
        CACHE_INDEX_LIMIT,
        CACHE_LIMIT,
        detect,
        forget_cache,
    )

    forget_cache()
    for step in range(CACHE_LIMIT + 8):
        # Jeder Körper ein anderes Maß, damit jeder einen eigenen Schlüssel hat.
        detect(MeshData(trimesh.creation.box(extents=(10.0 + step * 0.01, 10.0, 10.0))))

    assert len(_FEATURE_CACHE) == CACHE_LIMIT, "die Anzahl deckelt die kleinen weiter"
    assert len(_CACHE_INDICES) == len(_FEATURE_CACHE), (
        "und der Gewichtszähler läuft mit — sonst wächst er, während der Cache verdrängt"
    )
    assert sum(_CACHE_INDICES.values()) < CACHE_INDEX_LIMIT, (
        "kleine Körper kommen der Gewichtsgrenze nicht nahe"
    )

    # Ein einzelner Eintrag bleibt, auch wenn er für sich schwer ist.
    forget_cache()
    detect(MeshData(trimesh.creation.icosphere(subdivisions=5)))
    assert len(_FEATURE_CACHE) == 1
    assert sum(_CACHE_INDICES.values()) > 0, "und sein Gewicht steht im Zähler"

    # Und Vergessen räumt beide Seiten ab. Ein Zähler, der einen Eintrag
    # überlebt, ist genau die Sorte Rest, um die es hier geht.
    forget_cache()
    assert not _FEATURE_CACHE and not _CACHE_INDICES


def test_every_fitted_kind_asks_the_same_question() -> None:
    """Die Werkzeugschranke wird an **einer** Stelle gefragt, nicht an sechs.

    **Der Anlass ist ein Zwilling meiner eigenen Arbeit vom selben Tag
    (03.09.2026):** `_too_small_to_make` entstand, damit die nächste
    Merkmalsart die Frage beantworten **muss** statt sie zu übersehen — und
    bekam sie nur bei den drei Erkennern, die an dem Tag neu dazukamen. Kegel,
    Kugel und Torus riefen die Funktion; Bohrung, Zapfen und Verrundung
    verglichen weiter von Hand gegen `MIN_CYLINDER_DIAMETER`.

    Dieselbe Bedingung, dasselbe Ergebnis — und trotzdem der Fehler, gegen den
    die Funktion gebaut war: Wer fragt „wer ruft `_too_small_to_make` nicht?",
    bekommt drei Namen und hält sie für die Lücke. **Eine halbe
    Vereinheitlichung ist schlechter als keine, weil sie vollständig
    aussieht.**

    Dieser Wächter prüft deshalb den Quelltext und nicht das Verhalten: Die
    Konstante darf außerhalb ihrer eigenen Definition und der einen Funktion
    nirgends mehr verglichen werden.
    """
    import re

    import app.core.perceive.features as modul

    quelle = Path(modul.__file__).read_text(encoding="utf-8")

    # Zeilen, die die Konstante in einem Vergleich benutzen — Kommentare und
    # Docstrings zählen nicht, sie dürfen sie beim Namen nennen.
    vergleiche = [
        zeile.strip()
        for zeile in quelle.splitlines()
        if "MIN_CYLINDER_DIAMETER" in zeile
        and not zeile.lstrip().startswith(("#", "*", '"', "'"))
        and re.search(r"[<>=!]=|<|>", zeile)
    ]

    assert vergleiche == ["return size < MIN_CYLINDER_DIAMETER"], (
        "die Schranke wird nur in _too_small_to_make verglichen, sonst nirgends: "
        + "; ".join(vergleiche)
    )


def test_a_socket_stays_a_socket_when_the_mesh_gets_finer(profile: Profile) -> None:
    """Eine Kugelpfanne wurde zur Senkung, sobald das Netz fein genug war.

    **Der Fall (03.09.2026), und er ist der unangenehmste von heute:** Ein
    feineres Netz machte die Erkennung *schlechter*. Dieselbe Pfanne Ø 16 in
    demselben Quader:

    | Netz | Kegel-Rückstand | Kugel-Rückstand | erkannt als |
    |---|---|---|---|
    | 482 Dreiecke | 0,0891 | 0,00049 | Kugel |
    | 1602 Dreiecke | **0,0779** | 0,00009 | **Senkung** |
    | 5746 Dreiecke | 0,0736 | 0,00002 | **Senkung** |

    Der Kegelzweig wird vor dem Kugelzweig gefragt, und sein Rückstand rutscht
    mit steigender Feinheit unter `CONE_TOLERANCE` (0,08). Bei 0,0891 fiel er
    durch und die Pfanne erreichte die Kugel; bei 0,0779 nicht mehr.

    Heruntergeladene Modelle sind fein vernetzt — der Fall trifft also genau
    die Dateien, mit denen ein Kunde ankommt. Im Objektbaum stand dann
    „Senkung", und die Operationen behandelten eine Pfanne wie eine Bohrung.

    **Die Reihenfolge bleibt, die Kugel muss sich den Vortritt verdienen:** Sie
    verdrängt den Kegel nur, wenn sie um Größenordnungen besser passt
    (`SPHERE_BEATS_CONE`). An einer echten Senkung ist der Kegel der bessere
    Fit — Verhältnis 0,7 —, an einer Pfanne liegt es bei 182 aufwärts.

    Geprüft wird beides, und das zweite ist das wichtigere: dass eine echte
    Senkung eine Senkung bleibt.
    """
    from app.core.geom.prepare_ops import countersink, drill
    from app.core.perceive.features import detect_cones, detect_spheres

    def with_a_socket(fineness: int) -> MeshData:
        block = trimesh.creation.box(extents=(60.0, 60.0, 20.0))
        ball = trimesh.creation.icosphere(subdivisions=fineness, radius=8.0)
        ball.apply_translation((0.0, 0.0, 10.0 + 8.0 - 4.0))
        return MeshData(trimesh.boolean.difference([block, ball]))

    for fineness in (3, 4):
        mesh = with_a_socket(fineness)
        balls = detect_spheres(mesh)
        cones = detect_cones(mesh)
        assert len(balls) == 1, (
            f"Feinheit {fineness}: die Pfanne ist eine Kugel, gefunden {len(balls)} "
            f"(und {len(cones)} Kegel)"
        )
        assert balls[0].params["recess"] is True, "und zwar eine Pfanne, keine Kuppel"
        assert not cones, f"Feinheit {fineness}: keine Senkung, sondern eine Pfanne"

    # **Die Gegenrichtung, und sie trägt den Fix:** Eine echte Senkung darf
    # nicht zur Kugel werden. Ohne diese Hälfte wäre der Fix eine Verschiebung
    # des Fehlers und keine Behebung.
    block = MeshData(trimesh.creation.box(extents=(60.0, 40.0, 20.0)))
    bored = drill(
        block,
        position=(0.0, 0.0, 10.0),
        axis="z",
        diameter=6.0,
        profile=profile,
        compensate=False,
    ).mesh
    sunk = countersink(
        bored, position=(0.0, 0.0, 10.0), axis="z", diameter=12.0, profile=profile
    ).mesh
    assert detect_cones(sunk), "eine Senkung bleibt eine Senkung"
    assert not detect_spheres(sunk), "und wird keine Pfanne"


def test_a_sphere_that_beats_a_cone_is_fitted_only_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die Gegenprobe zum Vortritt der Kugel zählt die teure Einpassung.

    Ein feines Kugelsegment besteht den Kegelfit, wird aber wegen seines viel
    kleineren Kugelrückstands als Kugel erkannt. Derselbe Fleck braucht dafür
    keine zweite identische Kleinste-Quadrate-Rechnung.
    """
    block = trimesh.creation.box(extents=(60.0, 60.0, 20.0))
    ball = trimesh.creation.icosphere(subdivisions=4, radius=8.0)
    ball.apply_translation((0.0, 0.0, 14.0))
    mesh = MeshData(trimesh.boolean.difference([block, ball]))
    original = features_module.fit_sphere
    patches: list[tuple[int, ...]] = []

    def counted(body: trimesh.Trimesh, patch: list[int]) -> features_module.SphereFit | None:
        patches.append(tuple(patch))
        return original(body, patch)

    monkeypatch.setattr(features_module, "fit_sphere", counted)
    forget_cache()

    found = detect(mesh)

    assert any(feature.kind == "sphere" for feature in found.values())
    assert len(patches) == len(set(patches)), patches


def test_a_countersink_knows_the_bore_it_widens() -> None:
    """Die Senkung findet ihre Bohrung — und der Zapfen findet keine.

    **Der Fall.** Robert hat am 04.09.2026 an einem heruntergeladenen Halter
    den Durchmesser einer Bohrung geändert; über ihr saß eine Senkung, die
    stehen blieb, und im Teil entstand eine Stufe. Gesagt wurde nichts:
    ``resize_hole`` ändert genau ein Merkmal und kannte seine Nachbarschaft
    nicht. ``prepare_ops._feature_body`` schreibt seit dem 03.09.2026 im
    Docstring, was fehlt — „Bis Solidon die Nachbarschaft kennt, ist die
    Absage die richtige Antwort".

    **Und der Fehlgriff der ersten Fassung steht hier mit drin**, denn er ist
    die eigentliche Schärfe des Tests: Ohne die Bedingung „auch ein Hohlraum"
    fand die Bohrung Ø 34 des Halters den Zapfen Ø 40,80 als ihre Senkung —
    koaxial, weiter, und seine Mitte liegt in ihrer Strecke. Ein Zapfen umgibt
    die Bohrung aber, er mündet nicht in sie.

    Geprüft an der Platte des Korpus in beiden Richtungen: ``plate_holes.stl``
    hat vier Bohrungen ohne Senkung und darf **kein** Paar liefern,
    ``plate_countersunk.stl`` genau eines.
    """
    ohne = detect(plate("plate_holes.stl"))
    for feature in ohne.values():
        assert widening_at_the_mouth(feature, ohne) is None, (
            f"{feature.id} hat eine Senkung bekommen, die es nicht gibt"
        )

    mit = detect(plate("plate_countersunk.stl"))
    paare = {
        feature.id: found.id
        for feature in mit.values()
        if (found := widening_at_the_mouth(feature, mit)) is not None
    }
    assert len(paare) == 1, f"genau ein Paar erwartet, gefunden: {paare}"
    bohrung, senkung = next(iter(paare.items()))
    assert mit[bohrung].kind == "hole", f"die Bohrung ist keine: {mit[bohrung].kind}"
    assert mit[senkung].params["diameter"] > mit[bohrung].params["diameter"], (
        "die Senkung muss weiter sein als ihre Bohrung"
    )


def test_material_beside_a_bore_is_not_its_countersink() -> None:
    """Ein Zapfen um eine Bohrung herum ist keine Aufweitung ihrer Öffnung.

    Die Gegenprobe zum Test darüber, an einem eigens gebauten Körper statt am
    Kundenmodell: Eine Bohrung **im** Zapfen ist koaxial mit ihm, er ist
    weiter, und seine Mitte liegt in ihrer Strecke — drei der vier Bedingungen
    treffen zu. Was ihn ausschließt, ist die vierte.

    **Der Prüfkörper ist eigens dafür gebaut, und das ist der Punkt.** Der
    erste Anlauf nahm ``plate_with_pin`` aus dieser Datei: eine Platte mit
    einem Stift daneben, ohne Bohrung darin. Ohne die Hohlraum-Bedingung war
    der Test trotzdem grün — er traf den Fall nicht. Ein Rohr trifft ihn: Die
    Bohrung steckt im Zapfen, wie am Halter (Ø 34 in Ø 40,80), an dem der
    Fehlgriff aufgefallen ist.
    """
    tube = trimesh.creation.annulus(r_min=8.0, r_max=14.0, height=20.0, sections=96)
    body = MeshData.of(tube)
    features = detect(body)
    pins = [feature for feature in features.values() if feature.kind == "pin"]
    bores = [feature for feature in features.values() if feature.kind == "hole"]
    assert pins and bores, (
        f"der Prüfkörper trägt nicht beides — Zapfen {[p.id for p in pins]}, "
        f"Bohrungen {[b.id for b in bores]}; dann prüft der Test nichts"
    )

    for feature in features.values():
        found = widening_at_the_mouth(feature, features)
        assert found is None or found.kind != "pin", (
            f"{feature.id} hält den Zapfen {found.id if found else ''} für seine Senkung"
        )


def test_each_condition_of_the_countersink_rule_separates_something() -> None:
    """Fünf Bedingungen, und jede muss allein etwas trennen.

    **Der Anlass ist ein Fehlschlag dieser Datei.** Nach dem ersten Anlauf
    standen drei Tests auf der Regel, und eine Mutation je Bedingung zeigte:
    Vier von fünf hielt niemand fest. Die Korpusplatte hat keine Senkung, die
    gesenkte Platte hat genau ein Paar — bei einem einzigen Kandidaten findet
    ihn jede Bedingung, gleich welche man streicht. Der Docstring behauptete
    fünf gemessene Bedingungen; gemessen war eine (gefunden am 04.09.2026 nach
    einem Zuruf von 3d-druck-11, die denselben Fehler an ihrer eigenen
    Begründung gefunden hatte).

    Geprüft wird deshalb an der **echten** gesenkten Platte, und verändert wird
    je Durchgang genau ein Wert der Senkung. Was danach nicht mehr gefunden
    wird, hat die Bedingung getrennt.
    """
    features = dict(detect(plate("plate_countersunk.stl")))
    bore = next(feature for feature in features.values() if feature.kind == "hole")
    sink = next(
        feature
        for feature in features.values()
        if feature.kind == "cone" and feature.params.get("recess")
    )
    assert widening_at_the_mouth(bore, features) is not None, (
        "der Grundfall trifft nicht — dann trennt keine der Abwandlungen etwas"
    )

    centre = [float(value) for value in sink.params["centre"]]
    axis = [float(value) for value in sink.params["axis"]]
    radius = float(bore.params["diameter"]) / 2.0

    abwandlungen = {
        # Quer zur Achse gekippt: dieselbe Stelle, andere Richtung.
        "gleiche Achse": {"axis": (axis[1], axis[2], axis[0])},
        # Danebengeschoben, quer zur Achse — zwei Bohrungen nebeneinander
        # haben dieselbe Richtung und sind trotzdem zwei.
        "Mitten auf einer Linie": {"centre": (centre[0] + radius * 4.0, centre[1], centre[2])},
        # Weit weg **auf** der Achse: die Senkung der nächsten Wand.
        "auf der Strecke der Bohrung": {
            "centre": tuple(centre[index] + axis[index] * radius * 40.0 for index in range(3))
        },
        # Enger als ihre Bohrung — dann ist sie keine Senkung.
        "ist weiter": {"diameter": float(bore.params["diameter"]) / 2.0},
        # Materie statt Hohlraum.
        "ist ein Hohlraum": {"recess": False},
    }

    for bedingung, änderung in abwandlungen.items():
        verändert = dataclasses.replace(sink, params={**sink.params, **änderung})
        gefunden = widening_at_the_mouth(bore, {**features, sink.id: verändert})
        assert gefunden is None, (
            f"Bedingung {bedingung!r} trennt nichts: die Senkung wird auch "
            f"als {gefunden.id} gefunden"
        )


def test_the_search_does_not_rehash_the_mesh_for_every_patch() -> None:
    """Die Erkennung liest die Normalen je Fleck — und hasht dabei nicht neu.

    **Der teuerste Posten der Erkennung war Buchhaltung.** Jeder Zugriff auf
    ``body.face_normals`` lässt ``trimesh`` prüfen, ob sich das Netz geändert
    hat, und diese Prüfung hasht das ganze Netz. Gemessen am 04.09.2026 an
    einem Segel mit 421 194 Dreiecken und 3362 Flecken: 227 036 Hashes,
    **17,3 von 26,6 Sekunden** (cProfile), allein 4832 Aufrufe aus
    ``fit_sphere``.

    Mit ``Cache.__enter__`` um den Durchgang fällt die Prüfung weg, solange
    niemand schreiben kann — und niemand kann: ``_one_body`` gibt bei Bedarf
    ein neues Netz zurück, die vier Einpassungen lesen nur.

        421 194 Dreiecke:    24,34 s ->  6,33 s
        885 570 Dreiecke:    17,25 s -> 10,58 s
        1 223 836 Dreiecke: 562,72 s -> 153,20 s

    **Gezählt statt gestoppt**, denn eine Zeitmessung wäre maschinenabhängig
    und würde in der Suite streuen. Gemessen wird die Sache selbst: Vor dem
    Umbau kostete ``post_with_fillet.stl`` 3566 Hashes, danach **drei** — und
    drei sind es an jedem der vier Korpusmodelle, gleich wie groß sie sind und
    wie viele Merkmale sie tragen. Genau das ist die Zusage: Die Zahl hängt
    nicht mehr an der Zahl der Flecken.
    """
    from app.core.perceive.features import forget_cache

    def hashes_of(name: str) -> tuple[int, int]:
        """Wie oft ``detect`` das Netz hasht — und wie viele Merkmale es fand.

        Der Zähler steht in einer eigenen Funktion und nicht in der Schleife:
        Ein Lambda, das eine Schleifenvariable fängt, sieht deren **letzten**
        Wert, und der Zähler zählte dann für das falsche Modell.
        """
        mesh = plate(name)
        forget_cache()
        body = mesh.raw
        treffer: list[int] = []
        echt = body._cache._id_function
        body._cache._id_function = lambda: (treffer.append(1), echt())[1]
        try:
            return len(detect(mesh)), len(treffer)
        finally:
            body._cache._id_function = echt

    gezaehlt: dict[str, int] = {}
    for name in ("plate_holes.stl", "post_with_fillet.stl"):
        merkmale, treffer_zahl = hashes_of(name)
        features = merkmale
        gezaehlt[name] = treffer_zahl
        assert features, f"{name} trägt keine Merkmale — dann prüft der Test nichts"
        assert treffer_zahl < 50, (
            f"{name}: {treffer_zahl} Hashes über das ganze Netz — die Sperre greift nicht"
        )

    # Und die eigentliche Zusage: Das größere Modell mit den meisten Flecken
    # kostet nicht mehr Hashes als das kleine. Eine Obergrenze allein ginge
    # durch, sobald jemand sie großzügig genug wählt.
    assert gezaehlt["post_with_fillet.stl"] <= gezaehlt["plate_holes.stl"] + 2, (
        f"die Zahl wächst mit dem Modell: {gezaehlt}"
    )


def _curvature_patch_family(count: int, *, noisy: bool = False) -> MeshData:
    """Viele getrennte Rundflecken wie an einem gegliederten Druckteil.

    Die Form jedes Glieds bleibt gleich, nur ihre Zahl wächst. Leichtes
    Radialrauschen erzeugt innerhalb jedes Flecks echte Krümmungssprünge, ohne
    die Flecken miteinander zu verbinden.
    """
    rng = np.random.default_rng(7291)
    parts: list[trimesh.Trimesh] = []
    subdivisions = 2 if noisy else 1
    for index in range(count):
        part = trimesh.creation.icosphere(subdivisions=subdivisions, radius=1.0)
        vertices = np.asarray(part.vertices, dtype=float).copy()
        if noisy:
            vertices *= (1.0 + rng.normal(0.0, 0.02, len(vertices)))[:, None]
        part = trimesh.Trimesh(vertices=vertices, faces=part.faces, process=False)
        part.apply_scale((1.0, 1.3, 0.7))
        part.apply_translation((index * 4.0, 0.0, 0.0))
        parts.append(part)
    return MeshData.of(trimesh.util.concatenate(parts))


def test_curvature_splitting_scans_adjacency_once_for_many_failed_patches(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mehr Flecken dürfen keinen weiteren Ganznetz-Durchlauf auslösen.

    Der Kundenfall hatte 392 532 Dreiecke und viele Flecken, auf die keine
    Grundform passte. Jeder davon durchlief bislang sämtliche
    Flächennachbarschaften erneut. Gezählt wird der Zugriff auf genau diese
    Grundmenge; eine Zeitgrenze wäre maschinenabhängig.
    """
    descriptor = trimesh.Trimesh.face_adjacency
    assert descriptor.fget is not None
    reads = 0

    def counted(body: trimesh.Trimesh) -> np.ndarray:
        nonlocal reads
        reads += 1
        return np.asarray(descriptor.fget(body))

    monkeypatch.setattr(trimesh.Trimesh, "face_adjacency", property(counted))
    for name in ("fit_cone", "fit_cylinder", "fit_sphere", "fit_torus"):
        monkeypatch.setattr(features_module, name, lambda *_args, **_kwargs: None)

    def reads_for(count: int) -> int:
        nonlocal reads
        reads = 0
        forget_cache()
        assert detect(_curvature_patch_family(count)) == {}
        return reads

    few = reads_for(4)
    many = reads_for(32)

    assert many <= few + 2, f"vier Flecken: {few}, zweiunddreißig Flecken: {many}"


def test_batched_curvature_splitting_matches_the_previous_result() -> None:
    """Die einmalige Indexierung ändert keinen Flecken und keine Reihenfolge."""
    body = _curvature_patch_family(6, noisy=True).raw
    faces = list(range(len(body.faces)))
    patches = features_module._connected_patches(body, faces)
    jumps = features_module._curvature_jumps(body)
    pairs = np.asarray(body.face_adjacency)
    angles = np.degrees(np.asarray(body.face_adjacency_angles, dtype=float))

    def previous(patch: list[int]) -> list[list[int]]:
        wanted = set(patch)
        adjacency = [
            pair
            for pair, angle, step in zip(pairs, angles, jumps, strict=True)
            if angle < features_module.CURVATURE_LIMIT
            and step <= features_module.CURVATURE_JUMP
            and int(pair[0]) in wanted
            and int(pair[1]) in wanted
        ]
        if not adjacency:
            return [patch]
        groups = trimesh.graph.connected_components(
            np.asarray(adjacency), nodes=np.asarray(patch), engine="scipy"
        )
        return [[int(index) for index in group] for group in groups]

    expected = [previous(patch) for patch in patches]
    actual = features_module._split_patches_by_curvature(body, patches, jumps)

    assert any(len(pieces) > 1 for pieces in expected), "die Probe erzeugt keinen Krümmungssprung"
    assert actual == expected


def test_batched_curvature_splitting_checks_for_cancellation_inside_the_work() -> None:
    """Ein Abbruch wartet nicht bis hinter alle Flecken und Fits."""

    class StopHereError(RuntimeError):
        pass

    body = _curvature_patch_family(32).raw
    patches = features_module._connected_patches(body, list(range(len(body.faces))))
    jumps = features_module._curvature_jumps(body)
    checks = 0

    def stop() -> None:
        nonlocal checks
        checks += 1
        if checks == 8:
            raise StopHereError

    with pytest.raises(StopHereError):
        features_module._split_patches_by_curvature(body, patches, jumps, check_cancelled=stop)
    assert checks == 8


def _mast_after_moving_its_pin(tmp_path: Path) -> tuple[MeshData, dict[str, object]]:
    """Ein eingelesener Mast, dessen Zapfen einmal versetzt wurde.

    **Eingelesen und nicht gebaut**, weil es genau um den Weg geht, den ein
    Kunde nimmt: Datei öffnen, ein Merkmal anfassen, Ergebnis im Baum lesen.
    Und versetzt, weil erst die Boolesche Operation neu vernetzt.
    """
    from app.core.bootstrap import load_operations
    from app.core.knowledge import profiles as knowledge_profiles
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project
    from app.core.types import Source

    load_operations()
    mast = trimesh.creation.cylinder(radius=2.5, height=115.0, sections=360)
    path = tmp_path / "mast.stl"
    mast.export(path)

    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/mast.stl", sha256=""
    )
    project.sources["src_1"] = path.read_bytes()
    History(project.document).apply(
        "Probe",
        [
            OperationDraft(op="load", params={"source": "src_1", "unit": "mm"}),
            OperationDraft(
                op="move_feature",
                inputs=("obj_1",),
                params={"at_feature": "pin_1", "x": 0.0, "y": 0.0, "z": 5.0},
                # **Der Startwert steht hier und wird nicht gewürfelt.** Die
                # Rückfallkette der Booleschen stupst die Eckpunkte an (§11.3),
                # und wie viele Streifen dabei entstehen, hängt daran. Ohne
                # festen Wert schwankt die Zahl der Funde von Lauf zu Lauf, und
                # ein Test darüber wäre eine Münze.
                seed=902239366,
            ),
        ],
    )
    result = evaluate(
        project.document,
        knowledge_profiles.make_profile("centauri-carbon-2", "petg"),
        sources=ProjectSources(project),
    )
    entry = next(iter(result.scene.objects.values()))
    return entry.mesh, dict(entry.features)


def test_a_boolean_seam_does_not_become_a_feature(tmp_path: Path) -> None:
    """Ein versetztes Merkmal erfand fünfzig Formen, die es nicht gibt.

    Gemessen von 3d-druck-11 an einem Kundenmodell und hier nachgestellt: Ein
    glatter Mast Ø 5 mit drei Merkmalen kam nach ``move_feature`` mit
    **zweiundsiebzig** zurück — zwanzig „Verrundungen", sieben Kegel, zwei
    Kugeln, dazu ein Torus Ø 89,91 auf einem Körper von Ø 5. Es sind die
    schmalen Dreiecksstreifen, die eine Boolesche Operation an ihren
    Nahtstellen hinterlässt: sechs bis neun Dreiecke, über die ganze Länge
    des Körpers gezogen.

    ``MIN_CYLINDER_DIAMETER`` griff dort nicht — die Streifen sind im
    Durchmesser groß genug. Zu klein ist ihre **Breite**
    (:data:`app.core.perceive.features.MIN_SURFACE_WIDTH`).

    **Null wird es nicht, und der Test behauptet es auch nicht.** Über zehn
    Startwerte gemessen fallen 369 erfundene Formen auf 22 — je Lauf eine bis
    vier bleiben übrig, und welche, hängt am Stups der Rückfallkette. Wer hier
    ``== {}`` schreibt, bekommt einen Test, der bei jedem zweiten Startwert
    rot ist; die verbleibenden gehören in die Zusammenführung der Flächen und
    nicht in diese Schranke.
    """
    _mesh, features = _mast_after_moving_its_pin(tmp_path)
    fitted = {
        name: feature
        for name, feature in features.items()
        if getattr(feature, "kind", "") in ("hole", "cone", "sphere", "torus", "fillet")
    }
    assert len(fitted) <= 5, "Neuvernetzung erfand: " + str(
        [(n, f.kind) for n, f in fitted.items()]
    )

    # Und der echte Zapfen bleibt, mit seinem echten Maß — das ist die Hälfte,
    # auf die es ankommt: Eine Schranke, die alles verwirft, bestünde die Zeile
    # darüber ebenfalls.
    pins = [f for f in features.values() if getattr(f, "kind", "") == "pin"]
    assert len(pins) == 1
    assert float(pins[0].params["diameter"]) == pytest.approx(5.0, abs=0.05)


def test_a_real_narrow_surface_survives_the_sliver_guard() -> None:
    """Die Schranke darf nichts Echtes nehmen — und schmal ist nicht dünn.

    Die Gegenprobe zum Test darüber, denn eine Schranke, die alles verwirft,
    besteht ihn ebenfalls. Über den Referenzkorpus ist die schmalste echte
    Fläche 0,379 mm breit und die schmalste echte Verrundung einer Kundendatei
    0,646 mm; die Streifen der Neuvernetzung messen 0,013 bis 0,038 mm.
    """
    from app.core.perceive.features import MIN_SURFACE_WIDTH, _a_sliver

    for name in ("plate_holes.stl", "plate_countersunk.stl", "post_with_fillet.stl"):
        mesh = plate(name)
        found = detect(mesh)
        for feature_name, feature in found.items():
            if feature.kind not in ("hole", "pin", "cone", "sphere", "torus", "fillet"):
                continue
            assert not _a_sliver(mesh.raw, list(feature.face_indices)), (
                f"{name}: {feature_name} ({feature.kind}) wäre unter"
                f" {MIN_SURFACE_WIDTH} mm verworfen worden"
            )


def test_the_width_is_asked_where_the_diameter_is_asked() -> None:
    """Beide Schranken an denselben sechs Stellen — sonst ist es eine halbe.

    Der Zwilling zu :func:`test_every_fitted_kind_asks_the_same_question`, und
    aus demselben Grund: ``_a_sliver`` ist entstanden, weil
    ``_too_small_to_make`` die falsche Achse misst. Wenn die neue Frage nur bei
    fünf der sechs Arten gestellt wird, sieht die Vereinheitlichung vollständig
    aus und ist es nicht.
    """
    import app.core.perceive.features as modul

    source = Path(modul.__file__).read_text(encoding="utf-8")
    lines = source.splitlines()
    asks_diameter = [
        index
        for index, line in enumerate(lines)
        if "_too_small_to_make(" in line and not line.lstrip().startswith(("#", "*", '"', "'"))
    ]
    # Der Aufruf innerhalb der Definition selbst zählt nicht mit.
    asks_diameter = [i for i in asks_diameter if not lines[i].lstrip().startswith("def ")]

    for index in asks_diameter:
        window = "\n".join(lines[max(0, index - 6) : index + 7])
        assert "_a_sliver(" in window, (
            "hier wird der Durchmesser geprüft und die Breite nicht: " + lines[index].strip()
        )

    comparisons = [
        line.strip()
        for line in lines
        if "MIN_SURFACE_WIDTH" in line
        and not line.lstrip().startswith(("#", "*", '"', "'"))
        and re.search(r"[<>=!]=|<|>", line)
    ]
    assert comparisons == ["return area / reach < MIN_SURFACE_WIDTH"], (
        "die Breitenschranke wird nur in _a_sliver verglichen: " + "; ".join(comparisons)
    )


# --- Freiformen -----------------------------------------------------------------


def _listed(kinds: dict[str, int]) -> dict[str, Feature]:
    """Eine Merkmalsliste, wie ``detect`` sie zurückgäbe — nur die Arten zählen."""
    return {
        f"{kind}_{number}": Feature(
            id=f"{kind}_{number}", kind=kind, provenance="detected", params={}
        )
        for kind, count in kinds.items()
        for number in range(1, count + 1)
    }


def _scan_like_blob(seed: int = 7) -> MeshData:
    """Ein Körper wie ein Scan: glatte Beulen auf einer Kugel, feines Rauschen,
    unten eine ebene Standfläche.

    **Ohne das Rauschen findet die Erkennung an so einem Körper nichts** —
    die Krümmung ändert sich zu stetig, als dass ``_split_patches_by_curvature``
    Flecken abteilte (gemessen am 05.09.2026: zwei Flächen, sonst nichts).
    Mit ihm zerfällt die Oberfläche in Dutzende Flecken annähernd gleicher
    Krümmung, und auf jeden passt eine Kugel — genau der Mechanismus, der auf
    dem Kiefer-Scan eines Kunden 281 Rundformen fand; hier sind es 39.
    """
    rng = np.random.default_rng(seed)
    ball = trimesh.creation.icosphere(subdivisions=5, radius=20.0)
    vertices = np.asarray(ball.vertices, dtype=float).copy()
    unit = vertices / np.linalg.norm(vertices, axis=1)[:, None]
    centres = rng.normal(size=(40, 3))
    centres /= np.linalg.norm(centres, axis=1)[:, None]
    widths = rng.uniform(0.15, 0.5, size=40)
    heights = rng.uniform(-0.25, 0.25, size=40)
    scale = np.ones(len(vertices))
    for centre, width, height in zip(centres, widths, heights, strict=True):
        distance = np.arccos(np.clip(unit @ centre, -1.0, 1.0))
        scale += height * np.exp(-((distance / width) ** 2))
    scale += rng.normal(scale=0.01, size=len(vertices))
    blob = trimesh.Trimesh(vertices=vertices * scale[:, None], faces=ball.faces, process=False)
    with_base = trimesh.intersections.slice_mesh_plane(
        blob, plane_normal=(0.0, 0.0, 1.0), plane_origin=(0.0, 0.0, -12.0), cap=True
    )
    return MeshData.of(with_base)


def test_the_freeform_verdict_needs_the_count_and_the_share() -> None:
    """Zwei Zahlen an der fertigen Liste — und die Fälle, an denen sie gemessen sind.

    Die Nozzle-Box ist der wichtige: konstruiert, 116 Merkmale, 69 davon
    Kugeln und Ringe (59 %). Das Register vom 04.09.2026 kannte für
    Konstruiertes nur 0 bis 7 %; die Schwelle liegt deshalb bei sieben
    Zehnteln und nicht bei der Hälfte. Der Ring allein ist zu hundert Prozent
    rund und trotzdem ein Ring — dafür die Mindestzahl.
    """
    assert math.isclose(FREEFORM_ROUND_SHARE, 0.7)
    assert FREEFORM_ROUND_COUNT == 12

    assert is_a_freeform(_listed({"sphere": 8, "torus": 4}))
    assert is_a_freeform(_listed({"sphere": 60, "torus": 40, "cone": 10, "face": 20})), (
        "77 Prozent, wie die Retro-Maus"
    )
    assert not is_a_freeform(
        _listed({"sphere": 17, "torus": 52, "cone": 22, "hole": 8, "face": 16, "fillet": 1})
    ), "die Nozzle-Box: konstruiert, 59 Prozent rund"
    assert not is_a_freeform(_listed({"sphere": 11, "face": 1})), "elf sind zu wenige"
    assert not is_a_freeform(_listed({"torus": 1})), "torus_ring.stl: ein Ring ist ein Ring"
    assert is_a_freeform(
        _listed({"torus": 12, "cone": 7, "face": 1}),
        unpublished_round_shapes=27,
    ), "unsichere Kugelfits bleiben als Freiformbeleg erhalten"
    assert not is_a_freeform({})


def test_on_a_freeform_the_round_shapes_go_and_the_rest_stays() -> None:
    kept, dropped = features_module._shapes_on_a_freeform(
        _listed({"sphere": 20, "torus": 10, "cone": 3, "fillet": 2, "hole": 1, "pin": 1, "face": 2})
    )
    assert dropped == 35
    assert {feature.kind for feature in kept.values()} == {"hole", "pin", "face"}

    unchanged = _listed({"sphere": 1, "face": 6})
    assert features_module._shapes_on_a_freeform(unchanged) == (unchanged, 0)


def test_a_scan_keeps_its_flat_base_and_loses_the_invented_round_shapes() -> None:
    """Der Kundenfall an einem Körper aus dem Test selbst — ohne Korpusdatei,
    weil kein freies Scanmodell im Korpus liegt.

    Was bleibt, ist das Echte: die ebene Standfläche. Was geht, sind die
    Kugeln und Ringe, die die Krümmungsflecken hergaben — und der Zähler
    daneben sagt der Auswertung, wie viele es waren (Regel 17).
    """
    mesh = _scan_like_blob()
    forget_cache()

    found = detect(mesh)

    kinds = {feature.kind for feature in found.values()}
    assert freeform_dropped(mesh) >= FREEFORM_ROUND_COUNT, freeform_dropped(mesh)
    assert not kinds & {"sphere", "torus", "cone", "fillet"}, kinds
    assert "face" in kinds, "die Standfläche ist echt und bleibt"


def test_without_the_freeform_rule_the_same_scan_keeps_only_supported_round_shapes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die Gegenprobe trennt Flächengüte und Urteil über das ganze Modell."""
    monkeypatch.setattr(features_module, "FREEFORM_ROUND_COUNT", 10**6)
    forget_cache()

    found = detect(_scan_like_blob())

    round_shapes = [f for f in found.values() if f.kind in ("sphere", "torus")]
    assert 0 < len(round_shapes) < FREEFORM_ROUND_COUNT, len(round_shapes)
    assert freeform_dropped(_scan_like_blob()) == 0


def test_a_constructed_part_with_one_round_feature_is_left_alone() -> None:
    """Die Gegenrichtung am Korpus: Pfanne, Ring und Verrundung bleiben."""
    for name in ("sphere_socket.stl", "torus_ring.stl", "post_with_fillet.stl"):
        forget_cache()
        mesh = plate(name)
        found = detect(mesh)
        assert freeform_dropped(mesh) == 0, name
        assert any(f.kind in ("sphere", "torus") for f in found.values()), name
