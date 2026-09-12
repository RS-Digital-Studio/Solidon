"""The difference view (Bauplan §18.7)."""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import pytest
import trimesh

from app.core.geom.difference import compare, compare_scenes
from app.core.geom.mesh import MeshData, read_mesh
from app.core.geom.transform import apply, translation
from app.core.ingest.loader import normalise
from app.core.types import Profile, Scene, SceneObject

MESHES = Path(__file__).parent / "data" / "meshes"


def cube(size: float = 20.0) -> MeshData:
    return MeshData.of(trimesh.creation.box(extents=(size, size, size)))


def plate() -> MeshData:
    return normalise(read_mesh((MESHES / "plate_holes.stl").read_bytes(), ".stl"), "mm").mesh


def test_a_body_that_grew_shows_the_added_volume() -> None:
    difference = compare(cube(20.0), cube(24.0))

    assert difference.added_volume == pytest.approx(24.0**3 - 20.0**3, rel=0.02)
    assert difference.removed_volume < 1.0
    assert difference.changed


def test_a_body_that_shrank_shows_the_removed_volume() -> None:
    difference = compare(cube(24.0), cube(20.0))

    assert difference.removed_volume == pytest.approx(24.0**3 - 20.0**3, rel=0.02)
    assert difference.added_volume < 1.0


def test_a_body_that_did_not_change_is_not_a_failed_computation() -> None:
    """Ein Vergleich, der nichts findet, hat nichts zu melden.

    Aus dem Protokoll des ersten Kunden mit 0.1.3: zwölfmal
    ``difference could not be computed: Es bleibt kein Körper übrig`` und ein
    Befund im Prüfbericht daneben — für zwei Zustände, zwischen denen sich
    schlicht nichts geändert hatte. Die Rechnung war nie gescheitert; sie war
    leer, und leer ist hier die richtige Antwort.

    Ohne ``allow_empty`` in :func:`_cut` wirft die Boolesche Kette an dieser
    Stelle, und der Vergleich meldet einen Fehlschlag, den es nicht gab.
    """
    difference = compare(cube(20.0), cube(20.0))

    assert not difference.changed
    assert difference.added_volume < 1.0
    assert difference.removed_volume < 1.0
    assert not difference.findings, [str(entry.message) for entry in difference.findings]


def test_a_body_that_moved_shows_both_sides() -> None:
    """Bewegen ist hier Entfernen und dort Hinzufügen — und die Ansicht sagt
    das.
    """
    moved = apply(cube(20.0), translation((10.0, 0.0, 0.0)))
    difference = compare(cube(20.0), moved)

    assert difference.added_volume > 0.0
    assert difference.removed_volume > 0.0


def test_an_unchanged_body_is_not_a_change() -> None:
    difference = compare(cube(20.0), cube(20.0))

    assert not difference.changed


def test_the_solver_stage_is_kept(profile: Profile) -> None:
    """§17.2: welche Stufe die Differenz getragen hat, ist Teil der Antwort."""
    difference = compare(cube(20.0), cube(24.0))

    assert difference.solvers
    assert difference.solvers[0].strategy in ("direct", "welded", "jittered", "voxel")


# --- whole scenes -----------------------------------------------------------------


def scene_with(**objects: MeshData) -> Scene:
    return Scene(
        objects={name: SceneObject(id=name, name=name, mesh=mesh) for name, mesh in objects.items()}
    )


def test_a_transaction_is_compared_body_by_body() -> None:
    before = scene_with(obj_1=cube(20.0), obj_2=plate())
    after = scene_with(obj_1=cube(24.0), obj_2=plate())

    difference = compare_scenes(before, after)

    assert set(difference.entries) == {"obj_1"}, "an untouched body is not compared at all"
    assert difference.changed
    assert difference.added_volume > 0.0


def test_new_and_gone_objects_are_named() -> None:
    before = scene_with(obj_1=cube(20.0))
    after = scene_with(obj_1=cube(20.0), obj_2=cube(10.0))

    difference = compare_scenes(before, after)

    assert difference.created == ("obj_2",)
    assert difference.deleted == ()
    assert difference.changed


def test_a_scene_that_did_not_change_says_so() -> None:
    before = scene_with(obj_1=plate())
    after = scene_with(obj_1=plate())

    assert not compare_scenes(before, after).changed


def test_an_exact_body_shows_its_difference_too() -> None:
    """Der Zwilling des Analysekarten-Absturzes (27.08.2026), nur still.

    ``compare_scenes`` übersprang jeden Körper, der kein ``MeshData`` ist —
    ein STEP-Import also, und alles aus dem exakten Kern. Kein Absturz, keine
    Meldung: Die Differenzansicht blieb nach jeder Änderung an einem exakten
    Körper einfach leer, und §18.7 verspricht genau sie. Wer sich fragt, was
    ein Schritt getan hat, bekam bei der einen Körperart eine Antwort und bei
    der anderen nichts, ohne zu erfahren, warum.

    Dieselbe Auflösung wie dort: Der Weg von B-Rep zu Mesh steht jederzeit
    offen (§30), verglichen wird auf der Tessellation.
    """
    from app.core.brep.kernel import Solid, available

    if not available():
        pytest.skip("OpenCASCADE is an optional dependency")

    from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox

    def scene_of(mesh: object) -> Scene:
        return Scene(objects={"obj_1": SceneObject(id="obj_1", name="Teil", mesh=mesh)})

    before = scene_of(Solid(BRepPrimAPI_MakeBox(20.0, 20.0, 20.0).Shape()))
    after = scene_of(Solid(BRepPrimAPI_MakeBox(30.0, 30.0, 30.0).Shape()))

    result = compare_scenes(before, after)

    assert "obj_1" in result.entries, "auch ein exakter Körper zeigt, was sich geändert hat"
    assert result.entries["obj_1"].added_volume > 0.0


def test_a_body_that_did_not_exist_before_is_shown_as_added() -> None:
    """Ein neu erzeugter Körper ist die Differenz — die ganze.

    **Gemessen an der Live-Vorschau, und dort fällt es beim Kunden auf:** Wer
    eine Skizze extrudiert, einen Quader anlegt oder einen Zylinder erzeugt,
    tippt eine Höhe und sieht nichts. Der Dialog rechnet die Vorschau, die
    Ansicht zeichnet ``entries`` — und ein neuer Körper stand allein in
    ``created``, ohne Geometrie daneben.

    Das trifft **jede erzeugende Operation**, also genau den Anfang von Weg 2:
    neu konstruieren. Robert hat danach gefragt („in die Seitenansicht gehen
    und nach oben ziehen") — was fehlte, war nicht der Griff, sondern das Bild.

    Und die zweite Hälfte ist die Zahl: ``added_volume`` meldete null, während
    achttausend Kubikmillimeter entstanden. Eine Differenz, die ihr eigenes
    Ergebnis nicht mitzählt, ist als Auskunft falsch, nicht nur als Bild leer.
    """
    before = Scene(objects={})
    body = cube(20.0)
    after = Scene(objects={"obj_1": SceneObject(id="obj_1", name="Teil", mesh=body)})

    difference = compare_scenes(before, after)

    assert difference.created == ("obj_1",), "die Liste der Neuen bleibt, wie sie war"
    assert "obj_1" in difference.entries, "und er steht jetzt auch als Geometrie da"
    entry = difference.entries["obj_1"]
    assert entry.added is not None, "sein Netz ist das Hinzugekommene"
    assert entry.added_volume == pytest.approx(8000.0, rel=1e-6), "der ganze Körper"
    assert entry.removed_volume == 0.0, "weggenommen wurde nichts"
    assert difference.added_volume == pytest.approx(8000.0, rel=1e-6)


def test_a_body_that_vanished_is_shown_as_removed() -> None:
    """Die Gegenrichtung, damit die Auskunft in beide Richtungen stimmt.

    Ein gelöschter Körper ist genauso eine Differenz wie ein neuer — und ohne
    diesen Fall bliebe die Hälfte der Zusage unbewiesen.
    """
    body = cube(20.0)
    before = Scene(objects={"obj_1": SceneObject(id="obj_1", name="Teil", mesh=body)})
    after = Scene(objects={})

    difference = compare_scenes(before, after)

    assert difference.deleted == ("obj_1",)
    assert "obj_1" in difference.entries, "auch das Verschwundene hat Geometrie"
    entry = difference.entries["obj_1"]
    assert entry.removed_volume == pytest.approx(8000.0, rel=1e-6)
    assert entry.added_volume == 0.0


# --- was als Änderung zählt, sagt der Drucker (RM-097) ----------------------------


def _box(height: float) -> MeshData:
    return MeshData.of(trimesh.creation.box(extents=(10.0, 10.0, height)))


def test_a_change_below_what_the_printer_leaves_is_no_change(profile: Profile) -> None:
    """AGENTS.md Regel 7: die Grenze lebt im Profil, nicht im Code (RM-097).

    ``NOISE_VOLUME = 1e-3`` war die Untergrenze der **Rechnung** und wurde als
    Untergrenze der **Änderung** gelesen. Zwischen beiden liegt der Fall, den
    der Kunde sieht: Ein Quader, der um zwei Zehntausendstel Millimeter
    wächst, ändert 0,02 mm³ — mehr als das Rauschen und ein Fünfzehntel
    dessen, was der Centauri überhaupt hinterlässt. Die Differenzansicht
    meldete das als Änderung, und im Chat stand „+0,00 cm³".

    Dieselbe Grenze und dieselbe Begründung wie bei
    :func:`boolean.without_effect`; ohne Profil bleibt es beim Rauschen — wer
    keinen Drucker kennt, soll keinen erfinden.
    """
    winzig = compare(_box(10.0), _box(10.0002), profile=profile)

    assert winzig.added_volume == pytest.approx(0.02, abs=0.005), "die Zahl, um die es geht"
    assert not winzig.changed, (
        "0,02 mm³ sind ein Fünfzehntel dessen, was diese Düse legt — das sieht niemand"
    )
    assert compare(_box(10.0), _box(10.0002)).changed, (
        "ohne Profil bleibt es beim Rauschen, und das ist die Antwort, die belegt ist"
    )


def test_the_same_change_reads_differently_on_a_coarser_nozzle(profile: Profile) -> None:
    """Die Gegenrichtung, und sie ist der Grund für Regel 7.

    Ein Zehntel Kubikmillimeter ist am Centauri (0,42 mm Bahn, 0,2 mm Schicht)
    das Dreifache einer Bahnportion und damit eine Änderung. An einer 0,8er
    Düse sind es 0,28 mm³ je Portion, und dieselbe Änderung verschwindet
    darin. Dieselbe Geometrie, zwei Drucker, zwei richtige Antworten — eine
    Zahl im Code kann nur eine davon geben.
    """
    grob = replace(
        profile,
        printer=replace(
            profile.printer, nozzle_diameter=0.8, extrusion_width=0.84, layer_height=0.4
        ),
    )

    assert compare(_box(10.0), _box(10.001), profile=profile).changed
    assert not compare(_box(10.0), _box(10.001), profile=grob).changed


def test_the_scene_hands_its_printer_to_the_difference(profile: Profile) -> None:
    """Die Szene bringt den Drucker mit — sonst käme die Zahl nie an.

    ``compare_scenes`` ist der Weg, den die Anwendung geht (``Session``), und
    ohne diese eine Zeile bliebe die Profilgrenze eine Möglichkeit, die
    niemand benutzt — die Sorte Lücke, die Testart „Anschluss" meint.
    """

    def scene_with(height: float, *, with_printer: bool) -> Scene:
        entry = SceneObject(id="obj_1", name="Klotz", mesh=_box(height))
        return Scene(objects={"obj_1": entry}, profile=profile if with_printer else None)

    assert not compare_scenes(
        scene_with(10.0, with_printer=True), scene_with(10.0002, with_printer=True)
    ).changed
    assert compare_scenes(
        scene_with(10.0, with_printer=False), scene_with(10.0002, with_printer=False)
    ).changed
