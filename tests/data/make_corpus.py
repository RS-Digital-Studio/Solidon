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
    bracket_inch()
    plate_cm()
    plate_holes()
    plate_holes_twin()
    plate_countersunk()
    plate_countersunk_blind()
    sphere_socket()
    torus_ring()
    post_with_fillet()
    degenerate()
    broken_open()
    two_components()
    generated_figure()
    clean_figure()
    broken_selfint()
    colored_3mf()
    island_tower()
    oversized()
    dense_1m()
