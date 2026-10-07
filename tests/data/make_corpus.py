"""Baut den Referenzkorpus (Bauplan §34).

Alles hier wird erzeugt, nie heruntergeladen: der Korpus wird mit der Anwendung
veröffentlicht, er muss also frei von fremden Lizenzen sein. Dieses Skript nur
laufen lassen, wenn eine Datei sich ändern muss, und die erwarteten Kennzahlen
in ``README.md`` notieren.

    python tests/data/make_corpus.py
"""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import trimesh

HERE = Path(__file__).parent
MESHES = HERE / "meshes"


def write(mesh: trimesh.Trimesh, name: str) -> None:
    MESHES.mkdir(parents=True, exist_ok=True)
    path = MESHES / name
    path.write_bytes(trimesh.exchange.stl.export_stl(mesh))
    print(f"{name}: {len(mesh.faces)} triangles, extents {mesh.extents}")


def cube_clean() -> None:
    """Der Grundfall: wasserdicht, 12 Dreiecke, in Millimetern geschrieben."""
    write(trimesh.creation.box(extents=(20.0, 20.0, 20.0)), "cube_clean.stl")


def rounded_magnet_bore(sections: int = 126) -> trimesh.Trimesh:
    """Eigener Prüfkörper: Sackloch Ø9, Tiefe 1,5 mit gerundetem Eintritt R0,2."""
    angles = np.linspace(np.pi, np.pi * 1.5, 31)
    contour = [
        (0.0, 1.5),
        (4.5, 1.5),
        *((4.7 + 0.2 * np.cos(angle), 0.2 + 0.2 * np.sin(angle)) for angle in angles),
        (13.0, 0.0),
        (13.0, 5.0),
        (0.0, 5.0),
    ]
    return trimesh.creation.revolve(contour, sections=sections)


def dense_cylinder() -> None:
    """Ein dicht facettierter Zylinder, dessen Kappen den ersten
    Vereinfacher festhalten.

    Der Anlass sind die Masten des Piratenschiffs aus dem Nutzerdurchgang:
    Mantel und Boden lassen sich getrennt vereinfachen, der geschlossene
    Körper blieb jedoch bei jeder Aggressivität vollständig unverändert.
    """
    write(
        trimesh.creation.cylinder(radius=2.5, height=40.0, sections=360),
        "dense_cylinder.stl",
    )


def bracket_inch() -> None:
    """Eine in Zoll gespeicherte Platte — 4 x 2 x 0,25 in, die Einheit ist
    also mehrdeutig.
    """
    write(trimesh.creation.box(extents=(4.0, 2.0, 0.25)), "bracket_inch.stl")


def plate_cm() -> None:
    """Eine Platte in Zentimetern abgelegt — 8 × 5 × 0,5 cm."""
    write(trimesh.creation.box(extents=(8.0, 5.0, 0.5)), "plate_cm.stl")


def plate_holes() -> None:
    """Eine Platte mit vier Bohrungen bekannter Größe — Merkmalserkennung und
    Messen.
    """
    plate = trimesh.creation.box(extents=(80.0, 50.0, 8.0))
    drills = []
    for x, y in ((-25.0, -15.0), (25.0, -15.0), (-25.0, 15.0), (25.0, 15.0)):
        drill = trimesh.creation.cylinder(radius=2.6, height=40.0, sections=48)
        drill.apply_translation((x, y, 0.0))
        drills.append(drill)
    write(trimesh.boolean.difference([plate, *drills]), "plate_holes.stl")


def plate_coarse_slots() -> None:
    """Zwei grob facettierte Langlöcher, deren Bogenflecken Tangentenreste tragen."""
    from shapely.geometry import LineString

    plate = trimesh.creation.box(extents=(70.0, 24.0, 2.0))
    tools = []
    for travel, y in ((3.8, -5.0), (21.0, 5.0)):
        outline = LineString([(-travel / 2.0, y), (travel / 2.0, y)]).buffer(1.9, quad_segs=4)
        tool = trimesh.creation.extrude_polygon(outline, height=4.0)
        tool.apply_translation((0.0, 0.0, -2.0))
        tools.append(tool)
    write(trimesh.boolean.difference([plate, *tools]), "plate_coarse_slots.stl")


def open_cylinder_clip() -> None:
    """Ein offener Clip: Innenradius 12, Außenradius 16, Höhe 17 und 184 Grad."""
    from shapely.geometry import Polygon

    angles = np.linspace(0.0, math.radians(184.0), 73)
    outer = np.column_stack((16.0 * np.cos(angles), 16.0 * np.sin(angles)))
    inner = np.column_stack((12.0 * np.cos(angles[::-1]), 12.0 * np.sin(angles[::-1])))
    outline = Polygon(np.vstack((outer, inner)))
    clip = trimesh.creation.extrude_polygon(outline, height=17.0)
    write(clip, "open_cylinder_clip.stl")
    # Zusätzliche Knoten innerhalb der Deckelflächen dürfen beim Ändern
    # einer Trimmkurve keine veralteten Dreiecksdiagonalen erzwingen.
    caps = np.flatnonzero(np.isclose(np.abs(clip.face_normals[:, 2]), 1.0))
    faces = np.asarray(clip.faces)[caps]
    centres = np.arange(len(caps)) + len(clip.vertices)
    divided = np.vstack(
        [np.column_stack((faces[:, edge], faces[:, (edge + 1) % 3], centres)) for edge in range(3)]
    )
    write(
        trimesh.Trimesh(
            vertices=np.vstack((clip.vertices, clip.triangles_center[caps])),
            faces=np.vstack((np.delete(clip.faces, caps, axis=0), divided)),
            process=False,
        ),
        "open_cylinder_clip_cap_nodes.stl",
    )


def plate_holes_twin() -> None:
    """Zwei gleiche Bohrungen dicht beieinander — der Mehrdeutigkeitsfall für
    §21.2.
    """
    plate = trimesh.creation.box(extents=(60.0, 30.0, 8.0))
    drills = []
    for x in (-4.0, 4.0):
        drill = trimesh.creation.cylinder(radius=2.6, height=40.0, sections=48)
        drill.apply_translation((x, 0.0, 0.0))
        drills.append(drill)
    write(trimesh.boolean.difference([plate, *drills]), "plate_holes_twin.stl")


def plate_countersunk() -> None:
    """Eine Platte mit **einer gesenkten** Bohrung — der Fall, an dem die
    Merkmalserkennung am 22.08.2026 nicht nur die Senkung, sondern die Bohrung
    selbst verlor.

    Maße einer M5-Senkkopfschraube: Durchgang Ø 5,2 mm, Senkung 90° auf
    Ø 10 mm. Der Kegel und die Bohrungswand hängen zusammen, und die
    Fleckenbildung trennte sie nicht — die Zylindereinpassung über
    Wand-plus-Kegel kam als nichts heraus, und damit stand ein gesenktes Loch
    für den Agenten überhaupt nicht in der Szene.
    """
    plate = trimesh.creation.box(extents=(60.0, 40.0, 8.0))
    drill = trimesh.creation.cylinder(radius=2.6, height=40.0, sections=48)
    # 45 Grad Halbwinkel: der radiale Zuwachs ist gleich dem axialen, also
    # steht der Kegel mit Radius 5 dort, wo er die Deckfläche trifft.
    sink = trimesh.creation.cone(radius=5.0, height=5.0, sections=48)
    sink.apply_transform(trimesh.transformations.rotation_matrix(math.pi, (1.0, 0.0, 0.0)))
    sink.apply_translation((0.0, 0.0, 4.0))
    write(trimesh.boolean.difference([plate, drill, sink]), "plate_countersunk.stl")


def plate_countersunk_blind() -> None:
    """Dieselbe Platte, aber die Bohrung endet **vor** der Unterseite — die
    Gegenprobe zu :func:`plate_countersunk`.

    Sie steht hier, weil ohne sie jede Reparatur grün wäre, die schlicht „an
    der Bohrung hängt eine Senkung, also geht sie durch" sagt. Beide Löcher
    haben dieselbe Senkung, dieselbe Wandhöhe darunter fehlt: 3,6 mm Zylinder
    plus 2,4 mm Kegel sind 6 von 8 mm, und was fehlt, ist der Boden.
    """
    plate = trimesh.creation.box(extents=(60.0, 40.0, 8.0))
    # Höhe 12 statt durchgehend: Der Boden liegt bei z = -2, oben ragt der
    # Bohrer aus der Platte heraus, damit die Differenz dort sauber schneidet.
    drill = trimesh.creation.cylinder(radius=2.6, height=12.0, sections=48)
    drill.apply_translation((0.0, 0.0, 4.0))
    sink = trimesh.creation.cone(radius=5.0, height=5.0, sections=48)
    sink.apply_transform(trimesh.transformations.rotation_matrix(math.pi, (1.0, 0.0, 0.0)))
    sink.apply_translation((0.0, 0.0, 4.0))
    write(trimesh.boolean.difference([plate, drill, sink]), "plate_countersunk_blind.stl")


def sphere_socket() -> None:
    """Ein Block mit einer eingefrästen Kalotte — die Kugel als **Pfanne**.

    Der Fall, den §41 zuerst nennt, und er ist der realistische: Eine
    freistehende Kugel kommt in einem Druckteil kaum vor, eine Pfanne für ein
    Kugelgelenk oder einen Magneten dauernd. Gemessen wird an ihr, dass die
    Einpassung den Radius trifft und den Mittelpunkt **dort** findet, wo er
    liegt — auf der Oberfläche des Blocks und nicht in der Mitte der Kappe.

    Vor dem Bau der Kugelerkennung kam hier nichts heraus außer den sechs
    Flächen des Blocks: keine Falschmeldung, aber auch kein Merkmal, auf das
    der Agent hätte zeigen können.
    """
    block = trimesh.creation.box(extents=(40.0, 40.0, 15.0))
    ball = trimesh.creation.icosphere(subdivisions=3, radius=8.0)
    ball.apply_translation((0.0, 0.0, 7.5))
    write(trimesh.boolean.difference([block, ball]), "sphere_socket.stl")


def _surface_patch(body: trimesh.Trimesh, faces: np.ndarray) -> trimesh.Trimesh:
    """Aus gewählten Dreiecken eine eigenständige offene Prüffläche bauen."""
    patch = trimesh.Trimesh(
        vertices=np.asarray(body.vertices),
        faces=np.asarray(body.faces)[faces],
        process=False,
    )
    patch.remove_unreferenced_vertices()
    return patch


def shallow_sphere_caps() -> None:
    """Zwei echte 5°-Kalotten mit verschiedener Triangulierung.

    Eine flache Kalotte bestimmt ihren großen Radius nur über eine kleine
    Normalenänderung. Sie bleibt trotzdem ein Kugelmerkmal, wenn die Krümmung
    kreisförmig in zwei Richtungen belegt ist. Icosphere und UV-Gitter halten
    fest, dass das nicht an einer bestimmten Dreiecksanordnung hängt.
    """
    radius = 80.0
    threshold = radius * math.cos(math.radians(5.0))
    icosphere = trimesh.creation.icosphere(subdivisions=5, radius=radius)
    selected = np.flatnonzero(np.asarray(icosphere.triangles_center)[:, 2] >= threshold)
    write(_surface_patch(icosphere, selected), "shallow_sphere_cap_icosphere.stl")

    uv_sphere = trimesh.creation.uv_sphere(radius=radius, count=(64, 32))
    selected = np.flatnonzero(np.asarray(uv_sphere.triangles_center)[:, 2] >= threshold)
    write(_surface_patch(uv_sphere, selected), "shallow_sphere_cap_uv.stl")


def indeterminate_sphere_cap() -> None:
    """Eine fast ebene 2°-Kalotte, deren Mittelpunkt nicht belastbar ist."""
    radius = 80.0
    sphere = trimesh.creation.icosphere(subdivisions=6, radius=radius)
    threshold = radius * math.cos(math.radians(2.0))
    selected = np.flatnonzero(np.asarray(sphere.triangles_center)[:, 2] >= threshold)
    write(_surface_patch(sphere, selected), "indeterminate_sphere_cap.stl")


def ambiguous_sphere_ribbon() -> None:
    """Ein exakter, aber nur in einer Richtung belegter Kugelstreifen.

    Der Radius des Ausgangskörpers ist bekannt. Der schmale Ausschnitt allein
    belegt aber kein bearbeitbares Kugelmerkmal: Entlang seiner kurzen Richtung
    ändern sich die Normalen zehnmal weniger als entlang der langen.
    """
    radius = 80.0
    sphere = trimesh.creation.uv_sphere(radius=radius, count=(128, 64))
    centres = np.asarray(sphere.triangles_center)
    longitude = np.degrees(np.arctan2(centres[:, 1], centres[:, 0]))
    latitude = np.degrees(np.arcsin(centres[:, 2] / np.linalg.norm(centres, axis=1)))
    selected = np.flatnonzero((np.abs(latitude) <= 2.0) & (np.abs(longitude) <= 20.0))
    write(_surface_patch(sphere, selected), "ambiguous_sphere_ribbon.stl")


def near_sphere_ellipsoid() -> None:
    """Eine nur vier Prozent gestreckte Kugel, die keine Kugeloperation darf."""
    body = trimesh.creation.icosphere(subdivisions=3, radius=8.0)
    body.apply_scale((1.0, 1.0, 1.04))
    write(body, "near_sphere_ellipsoid.stl")


def torus_ring() -> None:
    """Ein Torus, freistehend — Ringradius 20, Röhrenradius 5.

    Die zweite Form aus §41, und die teurere: Mit ihr kommt der Radius einer
    Verrundung, weil eine Verrundung um eine runde Kante ein Torusstück ist.
    Der Ring steht hier ganz da, damit die beiden Radien eindeutig messbar
    sind; ob ein **Stück** davon auch erkannt wird, ist eine andere Frage und
    gehört zu dem Punkt, der den Verrundungsradius bringt.
    """
    write(
        trimesh.creation.torus(
            major_radius=20.0, minor_radius=5.0, major_sections=48, minor_sections=24
        ),
        "torus_ring.stl",
    )


def pocket_with_pin() -> None:
    """Ein Block mit Ringnut von unten: Tasche Ø 6,12, darin ein Zapfen Ø 5,44
    — die Maße der Kundentasche aus RM-535.

    Der Zapfen hängt oben am Block, die Nut ist unten offen. Versetzt um
    0,5 mm in die Taschenwand nahm die Operation ihn ganz weg (−178 mm³), und
    die Tasche selbst ließ sich versetzen und schnitt dabei in ihn.
    """
    block = trimesh.creation.box(extents=(20.0, 20.0, 12.0))
    block.apply_translation((0.0, 0.0, 6.0))
    outer = trimesh.creation.cylinder(radius=3.06, height=8.68, sections=48)
    outer.apply_translation((0.0, 0.0, 3.34))
    core = trimesh.creation.cylinder(radius=2.72, height=10.0, sections=48)
    core.apply_translation((0.0, 0.0, 3.0))
    groove = trimesh.boolean.difference([outer, core])
    write(trimesh.boolean.difference([block, groove]), "pocket_with_pin.stl")


def cup_on_stem() -> None:
    """Ein Becher Ø 30 auf einem schmaleren Fuß, innen Ø 28 mit Deckelfalz
    Ø 29,2 — nachgebaut nach dem Minitopf aus RM-535.

    Erkannt wird die Außenwand als Zapfen. Versetzt füllte die Operation den
    Becher aus seinen Flächen und schnitt den Innenraum aus Kennzahlen wieder
    hinein; der Falz fehlte danach, und jedes Versetzen trug gleich viel auf.
    """
    profile = [
        (0.0, 0.0),
        (8.0, 0.0),
        (8.0, 6.0),
        (15.0, 6.0),
        (15.0, 24.0),
        (14.6, 24.0),
        (14.6, 22.6),
        (14.0, 22.6),
        (14.0, 7.0),
        (0.0, 7.0),
    ]
    write(trimesh.creation.revolve(profile, sections=64), "cup_on_stem.stl")


def pin_with_end_chamfers() -> None:
    """Ein Stift Ø 33,8 × 40 mit Fasen 5 mm an beiden Enden und einem
    Sackloch Ø 23,8 von unten, das in der unteren Fase mündet — der Stift
    der Kundensitzung aus RM-535.

    Ohne das Sackloch unter den Merkmalen füllte das Versetzen der unteren
    Fase dessen Mündung (+2 218 mm³ beim Kunden).
    """
    outer = trimesh.creation.revolve(
        [(0, 0), (11.9, 0), (16.9, 5), (16.9, 35), (11.9, 40), (0, 40)], sections=48
    )
    bore = trimesh.creation.cylinder(radius=11.9, height=24.1, sections=48)
    bore.apply_translation((0.0, 0.0, 10.05))
    write(trimesh.boolean.difference([outer, bore]), "pin_with_end_chamfers.stl")


def post_with_fillet() -> None:
    """Eine Säule mit verrundetem Fuß — das Alltagsteil, an dem die Erkennung
    bis zum 22.08.2026 **nichts** fand.

    Säule Ø 12 auf einer Platte, der Übergang mit R 3 ausgerundet. Eine
    Verrundung schließt **tangential** an, das ist ihr Zweck — und die
    Fleckenbildung trennt an Knicken. Mantel und Kehle lagen deshalb in einem
    Fleck, auf den weder ein Zylinder noch ein Torus passte: Die Säule hatte
    keine Mantelfläche, auf die der Agent hätte zeigen können, keine Bohrungs-
    oder Passungs-Operation fand sie, und der Steckbrief nannte sie nicht.
    Heraus kamen sieben ebene Flächen und sonst nichts.

    Der Korpus hatte bis dahin keinen einzigen verrundeten Körper, und genau
    deshalb fiel es niemandem auf.
    """
    plate = trimesh.creation.box(extents=(60.0, 60.0, 6.0))
    plate.apply_translation((0.0, 0.0, -3.0))
    post = trimesh.creation.cylinder(radius=6.0, height=30.0, sections=96)
    post.apply_translation((0.0, 0.0, 15.0))
    # Das Kehlmaterial: der Ring zwischen Säule und R 3, abzüglich des Torus,
    # dessen Röhre die Rundung schlägt.
    outer = trimesh.creation.cylinder(radius=9.0, height=3.0, sections=96)
    outer.apply_translation((0.0, 0.0, 1.5))
    inner = trimesh.creation.cylinder(radius=6.0, height=6.0, sections=96)
    inner.apply_translation((0.0, 0.0, 1.5))
    torus = trimesh.creation.torus(
        major_radius=9.0, minor_radius=3.0, major_sections=96, minor_sections=48
    )
    torus.apply_translation((0.0, 0.0, 3.0))
    fillet = trimesh.boolean.difference([trimesh.boolean.difference([outer, inner]), torus])
    write(trimesh.boolean.union([plate, post, fillet]), "post_with_fillet.stl")


def block_with_rounded_edge() -> None:
    """Ein Quader mit **einer** verrundeten Kante — der Fall, an dem die
    Erkennung einen Zapfen meldete, den es nicht gibt.

    Quader 40 x 30 x 20, die Kante bei x = 20 / z = 10 mit R 3 ausgerundet.
    Herauskam bis zum 22.08.2026 ein ``pin`` mit Ø 28,92 — fast so breit wie
    das Teil, und §14 sagt, ein Zapfen sei das, womit man eine Bohrung paart.
    Mit diesem paart niemand etwas, und die Operationen aus ``applies_to``
    boten sich trotzdem daran an.

    Die Ursache saß eine Stufe über der Einpassung: Zwei **ebene** Facetten von
    1110 und 510 mm² galten als gekrümmt, weil sie die Rundung berühren, und
    hängten sich ihrem Fleck an. Die Kreiseinpassung gewichtet quadratisch —
    vier Punkte in bis zu 25 mm Abstand ziehen einen Kreis von R 3 auf 14,46.

    Gebaut wird die Rundung wie in echt: Nur das Material **zwischen** Kante
    und Rundung kommt weg, nicht die ganze Ecke. Zweimal falsch gebaut, bevor
    das Volumen stimmte — 23942 mm³ gegen den Sollwert aus 40·30·20 minus
    (9 − 9π/4)·30.
    """
    block = trimesh.creation.box(extents=(40.0, 30.0, 20.0))
    corner = trimesh.creation.box(extents=(3.0, 30.0, 3.0))
    corner.apply_translation((18.5, 0.0, 8.5))
    rod = trimesh.creation.cylinder(radius=3.0, height=32.0, sections=96)
    rod.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2.0, (1.0, 0.0, 0.0)))
    rod.apply_translation((17.0, 0.0, 7.0))
    waste = trimesh.boolean.difference([corner, rod])
    write(trimesh.boolean.difference([block, waste]), "block_with_rounded_edge.stl")


def plate_chamfer_and_taper() -> None:
    """Die zwei Kegelarten, die dem Korpus fehlten: **Fase** und
    **Verjüngung**.

    §21.1 nennt für den Kegel drei Fälle — Senkung, Fase an einer Bohrung,
    Verjüngung. Im Korpus stand bis zum 22.08.2026 nur die Senkung, und zwar in
    zwei Dateien. Jeder grüne Lauf sagte damit nichts über die anderen beiden.

    Links eine Bohrung Ø 6 mit einer Fase auf Ø 9, rechts ein konischer Zapfen
    — die eine ausgehöhlt (``recess``), der andere aufgesetzt.

    **Die Fase ist der Grund, aus dem diese Datei entstanden ist.** Sie ist der
    Standardfall jeder Schraubenbohrung, und sie legte einen Fehler frei, den
    achtzehn scharfkantige Korpuskörper nie zeigen konnten: Die Vereinigung von
    Bohrer und Fasenkegel setzt Punkte auf die Bohrungswand, die Boolesche
    Operation trianguliert sie mit Knicken von siebzig bis neunzig Grad, und
    die Wand zerfiel in **vier** Flecken. Heraus kamen vier Bohrungen für ein
    Loch, zwei davon mit ``through=True`` und zwei mit ``through=False``.
    """
    plate = trimesh.creation.box(extents=(50.0, 30.0, 10.0))
    drill = trimesh.creation.cylinder(radius=3.0, height=30.0, sections=64)
    drill.apply_translation((-12.0, 0.0, 0.0))
    chamfer = trimesh.creation.cone(radius=4.5, height=1.5, sections=64)
    chamfer.apply_transform(trimesh.transformations.rotation_matrix(math.pi, (1.0, 0.0, 0.0)))
    chamfer.apply_translation((-12.0, 0.0, 5.0))
    # **Das Werkzeug wird vorher vereinigt.** Drei Körper auf einmal abzuziehen
    # gibt eine schlechtere Naht — gemessen, und es kostete zwei Anläufe.
    tool = trimesh.boolean.union([drill, chamfer])
    taper = trimesh.creation.cone(radius=5.0, height=15.0, sections=64)
    taper.apply_translation((12.0, 0.0, 5.0))
    write(
        trimesh.boolean.union([trimesh.boolean.difference([plate, tool]), taper]),
        "plate_chamfer_and_taper.stl",
    )


def plate_chamfered_mouths() -> None:
    """Zwei gefaste Mündungen, deren Wand unter der Fläche endet (24.09.2026).

    Platte 60 × 40 × 8 mm (z −4 bis 4): links ein Sackloch Ø 9 von unten,
    6 mm tief, mit 0,6-mm-Fase an der Mündung; rechts ein durchgehendes
    Langloch Breite 6, Länge 18 mit 0,8-mm-Fasen oben und unten. Die gemessene
    Bohrungswand endet an der Fase, eine Fasenbreite unter der Oberfläche —
    ohne die Suche entlang der Achse (``placement.seat_of``, ``mouth_reach``)
    hatte ein solches Loch keine Trägerfläche und damit keine Maße im Bild.
    Gebaut mit manifold3d statt trimesh: Die Fasen sind Hüllen aus Kegeln, und
    die Boolesche Differenz bleibt damit geschlossen.
    """
    import manifold3d

    sections = 64

    def cylinder(
        x: float, y: float, height: float, bottom: float, top: float, z: float
    ) -> manifold3d.Manifold:
        return manifold3d.Manifold.cylinder(height, bottom, top, sections).translate((x, y, z))

    plate = manifold3d.Manifold.cube((60.0, 40.0, 8.0), center=True)
    bore = cylinder(-15.0, 0.0, 6.0 + 1.0, 4.5, 4.5, -4.0 - 1.0)
    chamfer = cylinder(-15.0, 0.0, 0.6 + 0.5, 4.5 + 0.6 + 0.5, 4.5, -4.0 - 0.5)
    ends = [(12.0 - 6.0, 0.0), (12.0 + 6.0, 0.0)]
    slot = manifold3d.Manifold.batch_hull([cylinder(x, y, 10.0, 3.0, 3.0, -5.0) for x, y in ends])
    top = manifold3d.Manifold.batch_hull(
        [cylinder(x, y, 0.8 + 0.5, 3.0, 3.0 + 0.8 + 0.5, 4.0 - 0.8) for x, y in ends]
    )
    bottom = manifold3d.Manifold.batch_hull(
        [cylinder(x, y, 0.8 + 0.5, 3.0 + 0.8 + 0.5, 3.0, -4.0 - 0.5) for x, y in ends]
    )
    body = (plate - bore - chamfer - slot - top - bottom).to_mesh()
    write(
        trimesh.Trimesh(
            vertices=np.asarray(body.vert_properties)[:, :3],
            faces=np.asarray(body.tri_verts),
            process=True,
        ),
        "plate_chamfered_mouths.stl",
    )


def degenerate() -> None:
    """Ein Würfel plus ein Null-Flächen-Dreieck, eine Nadel und eine doppelte
    Fläche.
    """
    box = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    vertices = np.vstack(
        [
            box.vertices,
            [[30.0, 0.0, 0.0], [30.0, 0.0, 0.0], [30.0, 0.0, 0.0]],  # zero area
            [[40.0, 0.0, 0.0], [40.0 + 1e-9, 0.0, 0.0], [45.0, 0.0, 0.0]],  # needle
        ]
    )
    count = len(box.vertices)
    faces = np.vstack(
        [
            box.faces,
            [[count, count + 1, count + 2]],
            [[count + 3, count + 4, count + 5]],
            [box.faces[0]],  # duplicate
        ]
    )
    write(trimesh.Trimesh(vertices=vertices, faces=faces, process=False), "degenerate.stl")


def broken_open() -> None:
    """Ein Würfel, dem drei Dreiecke fehlen — drei offene Stellen für die
    Reparaturkette.
    """
    box = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    write(
        trimesh.Trimesh(vertices=box.vertices, faces=box.faces[:-3], process=False),
        "broken_open.stl",
    )


def partially_open() -> None:
    """Eine große fehlende Wand plus ein kleines schließbares Loch.

    Der Reparaturbericht braucht einen echten Teilerfolg: Ein Bodendreieck
    kann der Füller ersetzen, die vollständig fehlende Decke nicht. Der
    unterteilte Würfel beginnt deshalb mit neunzehn offenen Kanten; nach dem
    Füllen bleiben sechzehn. Genau dieser Unterschied muss im sichtbaren
    Bericht stehen, statt als pauschaler Vollzug zu erscheinen.
    """
    box = trimesh.creation.box(extents=(20.0, 20.0, 20.0)).subdivide().subdivide()
    normals = np.asarray(box.face_normals)
    keep = np.ones(len(box.faces), dtype=bool)
    keep[normals[:, 2] > 0.9] = False
    keep[int(np.flatnonzero(normals[:, 2] < -0.9)[0])] = False
    box.update_faces(keep)
    write(box, "partially_open.stl")


def broken_selfint() -> None:
    """Zwei ineinandergeschobene Blöcke, verbunden ohne geschnitten zu
    sein (§34).

    Keine Boolesche Vereinigung — die löste genau das auf, wofür es diese Datei
    gibt. Die zwei Häute laufen glatt durcheinander hindurch, und das ist der
    Fall, für den die Rückfallkette aus §17.2 ihre Stufen drei und vier hat:
    ein Kern kann nicht sagen, was in einem Körper innen ist, der in sich selbst
    liegt.
    """
    first = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    second = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    second.apply_translation((8.0, 8.0, 8.0))
    write(trimesh.util.concatenate([first, second]), "broken_selfint.stl")


def crossing_and_apart() -> None:
    """Zwei Blöcke, die sich durchdringen, und ein dritter daneben (KUNDE-13).

    Drei Teile beim Einlesen, zwei nach *Überschneidungen auflösen*. Der Satz
    des Ladeschritts nennt die Zahl, die er gemessen hat — am Endstand mit
    zwei Teilen ist er falsch, und der Körper ist trotzdem nicht aus einem
    Stück. Vereinigt: 2 · 8000 − 12³ = 14 272 mm³, dazu 8000 für den dritten.
    """
    first = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    second = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    second.apply_translation((8.0, 8.0, 8.0))
    apart = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    apart.apply_translation((60.0, 0.0, 0.0))
    write(trimesh.util.concatenate([first, second, apart]), "crossing_and_apart.stl")


#: Die Teile von :func:`parts_enclosing_air` als (Ausdehnung, Mitte) — der Test
#: rechnet die erste Schicht aus denselben Zahlen nach.
ENCLOSING_FRAME_BARS = (
    ((60.0, 8.0, 9.37), (0.0, 21.0, 4.685)),
    ((60.0, 8.0, 11.13), (0.0, -21.0, 5.565)),
    ((8.0, 50.6, 10.41), (25.7, 0.0, 5.205)),
    ((8.4, 49.2, 8.83), (-25.1, 0.2, 4.415)),
)


def parts_enclosing_air() -> None:
    """Teile, die sich überlappen und dabei Luft einschließen (RM-485).

    So kommen Tinkercad-Exporte und Baugruppen als eine STL: jedes Teil eine
    eigene, nach außen gerichtete Schale, keine vereinigt. Vier Balken bilden
    einen Rahmen mit Fenster, ein schräger Balken teilt das Fenster, ein Ring
    aus sechs Zylindern umschließt darüber einen Luftkern, ein Zylinder steckt
    ganz in einem Balken, und ein umgekehrter Quader ist ein echter Hohlraum
    im anderen. Kein Eckpunkt fällt auf den eines anderen Teils, damit das
    Einlesen keine Schalen verschweißt.
    """
    parts = [
        trimesh.creation.box(extents, trimesh.transformations.translation_matrix(centre))
        for extents, centre in ENCLOSING_FRAME_BARS
    ]
    slanted = trimesh.creation.box((70.0, 5.0, 4.0))
    slanted.apply_transform(trimesh.transformations.rotation_matrix(math.radians(12.0), (0, 1, 0)))
    slanted.apply_translation((0.0, 0.5, 9.5))
    parts.append(slanted)
    for index in range(6):
        angle = 2.0 * math.pi * index / 6.0
        parts.append(
            trimesh.creation.cylinder(
                radius=4.0,
                height=11.4,
                sections=32,
                transform=trimesh.transformations.translation_matrix(
                    (7.0 * math.cos(angle), 7.0 * math.sin(angle), 15.6)
                ),
            )
        )
    parts.append(
        trimesh.creation.cylinder(
            radius=2.5,
            height=6.0,
            sections=24,
            transform=trimesh.transformations.translation_matrix((0.0, 21.0, 4.4)),
        )
    )
    cavity = trimesh.creation.box((10.0, 4.0, 5.0))
    cavity.apply_translation((-5.0, -21.0, 5.0))
    cavity.invert()
    parts.append(cavity)
    write(trimesh.util.concatenate(parts), "parts_enclosing_air.stl")


def colored_3mf() -> None:
    """Zwei Farben in einer 3MF, je Dreieck (§34, §20)."""
    import sys

    sys.path.insert(0, str(HERE.parent.parent))
    from app.core.export import threemf
    from app.core.geom.attributes import with_slot
    from app.core.geom.boolean import boolean
    from app.core.geom.mesh import MeshData
    from app.core.types import MaterialSlot

    left = with_slot(MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 20.0))), 1)
    right_body = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    right_body.apply_translation((20.0, 0.0, 0.0))
    right = with_slot(MeshData.of(right_body), 2)

    joined = boolean("union", [left, right]).mesh
    payload = threemf.write(
        joined,
        [
            MaterialSlot(index=1, name="Rot", colour=(0.9, 0.1, 0.1)),
            MaterialSlot(index=2, name="Schwarz", colour=(0.1, 0.1, 0.1)),
        ],
        "Zweifarbig",
    )
    MESHES.mkdir(parents=True, exist_ok=True)
    (MESHES / "colored.3mf").write_bytes(payload)
    print(f"colored.3mf: {joined.triangle_count} triangles, 2 slots")


def assembly_fit() -> None:
    """Zwei Teile und die Passung zwischen ihnen (§34, §14).

    Eine Platte mit einer Bohrung und ein Stift, der hineingeht, aneinander
    gebunden durch ein Passungspaar mit einem Toleranzverweis statt einer Zahl.
    Wofür es diese Datei gibt, ist die Prüfung bei jeder Auswertung: das
    Material ändern, und das Paar muss es bemerken.

    Die Zahlen sind nicht beliebig und lohnen, einmal nachvollzogen zu werden.
    Die Bohrung wird mit 6 mm nominal gebohrt und kommt mit 6,2 heraus, denn
    FDM druckt Löcher zu eng, und das Materialprofil sagt das
    (``hole_compensation``). PETG will 0,25 mm Spiel für eine Gleitpassung, der
    Stift ist also 5,95 — und die Passung hält genau so lange, wie diese zwei
    Profilwerte bleiben, was sie sind.
    """
    import sys

    sys.path.insert(0, str(HERE.parent.parent))
    from app.core.bootstrap import load_operations
    from app.core.scene import History, OperationDraft
    from app.core.scene.project import new_project, save
    from app.core.types import FeatureRef, Fit

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Platte",
        [OperationDraft(op="create_box", params={"width": 40.0, "depth": 40.0, "height": 8.0})],
    )
    history.apply(
        "Bohrung",
        [
            OperationDraft(
                op="drill_hole",
                inputs=("obj_1",),
                params={"diameter": 6.0, "x": 0.0, "y": 0.0, "z": 4.0, "axis": "z"},
            )
        ],
    )
    history.apply(
        "Gegenstück",
        [
            OperationDraft(
                op="create_box",
                params={"width": 20.0, "depth": 20.0, "height": 6.0, "name": "Deckel"},
            )
        ],
    )
    history.apply(
        "Stift",
        [
            OperationDraft(
                op="insert_dowel",
                inputs=("obj_2",),
                params={"diameter": 5.95, "length": 12.0, "kind": "pin", "z": 6.0},
            )
        ],
    )
    project.document.fits.append(
        Fit(
            name="stift_1",
            a=FeatureRef("obj_2", "dowel_pin_1"),
            b=FeatureRef("obj_1", "hole_1"),
            kind="clearance",
            tolerance="auto:petg",
        )
    )

    target = HERE / "projects" / "assembly_fit.p3d"
    save(project, target)
    print(f"assembly_fit.p3d: {len(project.document.ops)} operations, 1 fit")


def island_tower() -> None:
    """Ein Block, der in der Luft beginnt (Bauplan §34, §22.2).

    Eine Säule, ein zweiter Block, der daneben schwebt, und eine Brücke, die
    die zwei weiter oben verbindet. Der schwebende Block hat keine Verbindung
    nach unten, wenn er beginnt — das ist eine Insel, und sie braucht Stützen,
    in welcher Lage auch immer.
    """
    column = trimesh.creation.box(extents=(10.0, 10.0, 30.0))
    column.apply_translation((0.0, 0.0, 15.0))

    floating = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    floating.apply_translation((20.0, 0.0, 25.0))

    bridge = trimesh.creation.box(extents=(30.0, 10.0, 5.0))
    bridge.apply_translation((10.0, 0.0, 27.5))

    write(trimesh.boolean.union([column, floating, bridge]), "island_tower.stl")


def dense_1m() -> None:
    """Etwa eine Million Dreiecke — der Maßstab für das
    Leistungsbudget (§31).

    Eine unterteilte Kugel statt Rauschen: sie bleibt wasserdicht, die
    Booleschen und die Schnittmessungen haben also etwas Rechtmäßiges zu tun.
    """
    sphere = trimesh.creation.icosphere(subdivisions=8, radius=40.0)
    write(sphere, "dense_1m.stl")


def oversized() -> None:
    """Länger als jede Platte — Auto Split muss das druckbar machen (§25).

    Kein schlichter Balken: zwei dicke Enden, verbunden durch eine schlankere
    Mitte, damit die Trennebene etwas zu finden hat. Ein Körper mit
    gleichbleibendem Querschnitt ließe jeden Schnitt gewinnen und bewiese
    nichts über die Suche.
    """
    left = trimesh.creation.box(extents=(120.0, 80.0, 40.0))
    left.apply_translation((-140.0, 0.0, 20.0))
    right = trimesh.creation.box(extents=(120.0, 80.0, 40.0))
    right.apply_translation((140.0, 0.0, 20.0))
    middle = trimesh.creation.box(extents=(170.0, 40.0, 30.0))
    middle.apply_translation((0.0, 0.0, 20.0))
    write(trimesh.boolean.union([left, middle, right]), "oversized.stl")


def two_components() -> None:
    """Ein Würfel mit einem winzigen losen Fragment daneben — gemeldet, nie
    gelöscht.
    """
    box = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    fragment = trimesh.creation.box(extents=(0.2, 0.2, 0.2))
    fragment.apply_translation((40.0, 0.0, 0.0))
    write(trimesh.util.concatenate([box, fragment]), "two_components.stl")


def generated_figure() -> None:
    """Was ein Bildmodell abliefert — und was daran zu reparieren ist (§34, Weg 3).

    ``broken_open.stl`` fehlt eine ganze Wand; die *kann* keine Reparatur
    schließen, und das ist dort der Punkt. Für Weg 3 braucht es das andere
    Bild: die Fehler, die ein Generator wirklich macht, und die alle behebbar
    sind.

    Drei davon stecken hier drin, jeder aus einem anderen Grund:

    * **einzelne fehlende Dreiecke.** Marching Cubes über ein Dichtefeld lässt
      Zellen aus, in denen sich der Schwellwert nicht entscheiden konnte. Auf
      einem feinen Netz ist jedes davon ein Loch in Dreiecksgröße — genau der
      Fall, den die Kette schließt.
    * **verdrehte Normalen.** Ein Teil der Dreiecke zeigt nach innen, weil das
      Feld an der Stelle das Vorzeichen wechselt.
    * **ein loser Splitter.** Ein Fetzen ohne Volumen, der irgendwo neben dem
      Körper schwebt.

    Die Form selbst ist organisch — drei verschmolzene Kugeln, wie ein
    Generator sie liefert, und nicht der Quader, den niemand erzeugen lassen
    würde.
    """
    body = trimesh.creation.icosphere(subdivisions=3, radius=10.0)
    head = trimesh.creation.icosphere(subdivisions=3, radius=6.0)
    head.apply_translation((0.0, 0.0, 12.0))
    arm = trimesh.creation.icosphere(subdivisions=3, radius=4.0)
    arm.apply_translation((9.0, 0.0, 4.0))
    figure = trimesh.boolean.union([body, head, arm])

    faces = figure.faces.copy()
    # Fünf einzelne Löcher, weit auseinander, damit keine zwei zu einer Wand
    # zusammenwachsen. Der Startwert ist fest: dieselbe Datei soll bei jedem
    # Lauf dieselbe sein (AGENTS.md Regel 9).
    rng = np.random.default_rng(20260731)
    missing = rng.choice(len(faces), size=5, replace=False)
    faces = np.delete(faces, missing, axis=0)

    # Ein Fünftel der Dreiecke zeigt nach innen.
    flipped = rng.choice(len(faces), size=len(faces) // 5, replace=False)
    faces[flipped] = faces[flipped][:, ::-1]

    broken = trimesh.Trimesh(vertices=figure.vertices, faces=faces, process=False)

    splinter = trimesh.Trimesh(
        vertices=np.array([[18.0, 0.0, 0.0], [18.4, 0.0, 0.0], [18.2, 0.3, 0.2]]),
        faces=np.array([[0, 1, 2]]),
        process=False,
    )
    write(trimesh.util.concatenate([broken, splinter]), "generated_figure.stl")


def clean_figure() -> None:
    """Eine Figur ohne Fehler — die Grundlage fürs Formen (§34, Konzept P16.5).

    ``generated_figure.stl`` trägt absichtlich die Fehler eines Generators und
    ist als Prüfstein für Weg 3 richtig. Als *Sculpting*-Grundlage taugt sie
    nicht: Sie ist erst nach der Reparaturkette ein Volumen, und ein
    Geometrietest, der nebenbei eine Reparatur mitprüft, misst zwei Dinge und
    sagt über keines etwas Genaues.

    Diese hier ist der Gegenpol: derselbe Aufbau, den P16.11 dem Käfigeditor
    entgegenhält — Rumpf, Kopf, zwei Arme, zwei Beine aus Grundformen, weich
    verschmolzen. Sie entsteht also auf dem Weg, den die Anwendung ihren
    Nutzern anbietet, und nicht auf einem, den nur dieses Skript kennt.

    Bewusst grob gehalten: Wer darauf formen will, vernetzt vorher gleichmäßig.
    Genau diese Vorbedingung soll an ihr prüfbar sein.
    """
    parts = [trimesh.creation.box(extents=(24.0, 14.0, 40.0))]

    head = trimesh.creation.icosphere(subdivisions=2, radius=9.0)
    head.apply_translation((0.0, 0.0, 26.0))
    parts.append(head)

    for side in (-1.0, 1.0):
        arm = trimesh.creation.cylinder(radius=3.5, height=22.0, sections=24)
        arm.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2.0, [0, 1, 0]))
        arm.apply_translation((side * 18.0, 0.0, 12.0))
        parts.append(arm)

        leg = trimesh.creation.cylinder(radius=4.5, height=30.0, sections=24)
        leg.apply_translation((side * 7.0, 0.0, -32.0))
        parts.append(leg)

    figure = trimesh.boolean.union(parts)
    figure.apply_translation(-figure.bounds[0] * np.array([0.0, 0.0, 1.0]))
    write(figure, "clean_figure.stl")


if __name__ == "__main__":
    cube_clean()
    dense_cylinder()
    bracket_inch()
    plate_cm()
    plate_holes()
    plate_coarse_slots()
    open_cylinder_clip()
    plate_holes_twin()
    plate_countersunk()
    plate_countersunk_blind()
    sphere_socket()
    shallow_sphere_caps()
    indeterminate_sphere_cap()
    ambiguous_sphere_ribbon()
    near_sphere_ellipsoid()
    torus_ring()
    pocket_with_pin()
    cup_on_stem()
    pin_with_end_chamfers()
    post_with_fillet()
    block_with_rounded_edge()
    plate_chamfer_and_taper()
    plate_chamfered_mouths()
    degenerate()
    broken_open()
    partially_open()
    two_components()
    generated_figure()
    clean_figure()
    broken_selfint()
    crossing_and_apart()
    parts_enclosing_air()
    colored_3mf()
    island_tower()
    oversized()
    dense_1m()
