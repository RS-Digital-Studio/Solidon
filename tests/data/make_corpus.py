"""Builds the reference corpus (Bauplan §34).

Everything here is generated, never downloaded: the corpus is published with the
application, so it must be free of foreign licences. Run this script only when a
file has to change, and note the expected figures in ``README.md``.

    python tests/data/make_corpus.py
"""

from __future__ import annotations

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
    """The base case: watertight, 12 triangles, written in millimetres."""
    write(trimesh.creation.box(extents=(20.0, 20.0, 20.0)), "cube_clean.stl")


def bracket_inch() -> None:
    """A plate stored in inches — 4 x 2 x 0.25 in, so the unit is ambiguous."""
    write(trimesh.creation.box(extents=(4.0, 2.0, 0.25)), "bracket_inch.stl")


def plate_cm() -> None:
    """A plate stored in centimetres — 8 x 5 x 0.5 cm."""
    write(trimesh.creation.box(extents=(8.0, 5.0, 0.5)), "plate_cm.stl")


def plate_holes() -> None:
    """A plate with four bores of known size — feature detection and measuring."""
    plate = trimesh.creation.box(extents=(80.0, 50.0, 8.0))
    drills = []
    for x, y in ((-25.0, -15.0), (25.0, -15.0), (-25.0, 15.0), (25.0, 15.0)):
        drill = trimesh.creation.cylinder(radius=2.6, height=40.0, sections=48)
        drill.apply_translation((x, y, 0.0))
        drills.append(drill)
    write(trimesh.boolean.difference([plate, *drills]), "plate_holes.stl")


def plate_holes_twin() -> None:
    """Two identical bores close together — the ambiguity case for §21.2."""
    plate = trimesh.creation.box(extents=(60.0, 30.0, 8.0))
    drills = []
    for x in (-4.0, 4.0):
        drill = trimesh.creation.cylinder(radius=2.6, height=40.0, sections=48)
        drill.apply_translation((x, 0.0, 0.0))
        drills.append(drill)
    write(trimesh.boolean.difference([plate, *drills]), "plate_holes_twin.stl")


def degenerate() -> None:
    """A cube plus a zero-area triangle, a needle and a duplicate face."""
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
    """A cube missing three triangles — three open places for the repair chain."""
    box = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    write(
        trimesh.Trimesh(vertices=box.vertices, faces=box.faces[:-3], process=False),
        "broken_open.stl",
    )


def broken_selfint() -> None:
    """Two blocks pushed into each other, joined without being cut (§34).

    Not a boolean union — that would resolve exactly what this file is for.
    The two skins pass straight through one another, which is the case the
    fallback chain of §17.2 has stages three and four for: a kernel cannot say
    what is inside a body that is inside itself.
    """
    first = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    second = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    second.apply_translation((8.0, 8.0, 8.0))
    write(trimesh.util.concatenate([first, second]), "broken_selfint.stl")


def colored_3mf() -> None:
    """Two colours in one 3MF, per triangle (§34, §20).

    Written by the application's own writer, because that is the file the
    import has to be able to read back — a 3MF from somewhere else would test
    somebody else's writer.
    """
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
    """Two parts and the fit between them (§34, §14).

    A plate with a bore and a pin that goes into it, tied together by a fit
    pair with a tolerance reference rather than a number. What this file is for
    is the check on every evaluation: change the material and the pair has to
    notice.

    The numbers are not arbitrary and are worth following once. The bore is
    drilled at 6 mm nominal and comes out at 6.2, because FDM prints holes
    tight and the material profile says so (``hole_compensation``). PETG wants
    0.25 mm of play for a sliding fit, so the pin is 5.95 — and the fit holds
    exactly as long as those two profile values stay what they are.
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
    """A block that starts in mid-air (Bauplan §34, §22.2).

    A column, a second block floating beside it, and a bridge joining the two
    further up. The floating block has no connection downwards when it begins —
    that is an island, and it needs support whatever the orientation.
    """
    column = trimesh.creation.box(extents=(10.0, 10.0, 30.0))
    column.apply_translation((0.0, 0.0, 15.0))

    floating = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    floating.apply_translation((20.0, 0.0, 25.0))

    bridge = trimesh.creation.box(extents=(30.0, 10.0, 5.0))
    bridge.apply_translation((10.0, 0.0, 27.5))

    write(trimesh.boolean.union([column, floating, bridge]), "island_tower.stl")


def dense_1m() -> None:
    """About a million triangles — the yardstick for the performance budget (§31).

    A subdivided sphere rather than noise: it stays watertight, so the boolean
    and slicing measurements have something legitimate to work on.
    """
    sphere = trimesh.creation.icosphere(subdivisions=8, radius=40.0)
    write(sphere, "dense_1m.stl")


def oversized() -> None:
    """Longer than any plate — the auto split has to make this printable (§25).

    Not a plain bar: two thick ends joined by a slimmer middle, so the parting
    plane has something to find. A body of constant section would let any cut
    win and would prove nothing about the search.
    """
    left = trimesh.creation.box(extents=(120.0, 80.0, 40.0))
    left.apply_translation((-140.0, 0.0, 20.0))
    right = trimesh.creation.box(extents=(120.0, 80.0, 40.0))
    right.apply_translation((140.0, 0.0, 20.0))
    middle = trimesh.creation.box(extents=(170.0, 40.0, 30.0))
    middle.apply_translation((0.0, 0.0, 20.0))
    write(trimesh.boolean.union([left, middle, right]), "oversized.stl")


def two_components() -> None:
    """A cube with a tiny stray fragment next to it — reported, never deleted."""
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


if __name__ == "__main__":
    cube_clean()
    bracket_inch()
    plate_cm()
    plate_holes()
    plate_holes_twin()
    degenerate()
    broken_open()
    two_components()
    generated_figure()
    broken_selfint()
    colored_3mf()
    island_tower()
    oversized()
    dense_1m()
