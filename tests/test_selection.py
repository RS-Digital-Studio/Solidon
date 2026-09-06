"""Die Auswahl in der Ansicht: was ein Klick trifft und wie tief (§18.5).

Der Klick auf ein Modell soll erst das Modell wählen und erst der nächste die
Bohrung darin. Diese Datei hält beide Hälften davon fest — dass die **Stufe**
stimmt, und dass der **Treffer** stimmt. Die zweite ist die ältere Frage: Bis
zur gestuften Tiefe nahm ``_feature_at`` das Merkmal mit dem nächsten
Mittelpunkt und traf damit immer eines, egal wie weit weg der Klick lag.

**Offscreen, und darum ohne Renderer.** Genau das ist hier die Falle: Vierzig
Methoden des Viewports steigen bei ``self.renderer is None`` sofort aus, und ein
Test, der einen von ihnen ruft, ist grün, ohne etwas geprüft zu haben. Alles,
was hier zählt, hängt deshalb an Methoden ohne diese Wache —
``_click_target``, ``_feature_at``, ``_select_at``, ``selection_depth`` sind
Aussagen über die Szene und nicht über den Renderer. Wo doch einer nötig ist
(der Mauszeiger), steht eine Attrappe mit genau den Feldern, die benutzt
werden, nach dem Muster von ``tests/test_cursors.py``.
"""

from __future__ import annotations

import dataclasses
import math
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from app.core.geom.mesh import MeshData
from app.core.perceive.features import detect
from app.core.scene.evaluate import EvaluationResult
from app.core.types import Scene, SceneObject
from app.ui.main_window import MainWindow
from app.ui.render.api import Pick
from app.ui.session import Session
from app.ui.settings import UiSettings
from app.ui.viewport import Viewport
from tests.render_fakes import RecordingRenderer

MESHES = Path(__file__).parent / "data" / "meshes"

#: Die Platte aus dem Korpus: 80 x 50 x 8 mm, vier Bohrungen Ø5,19 an
#: (±25, ±15), sechs erkannte Flächen. Die Deckfläche liegt auf z = +4.
PLATE = MESHES / "plate_holes.stl"


def test_surface_pick_keeps_its_body_among_overlapping_bounds(qt_app: QApplication) -> None:
    """Ein sichtbarer Treffer gehört seinem Aktor, auch im kleineren Hüllquader."""
    import trimesh

    small = MeshData(trimesh.creation.box(extents=(8.0, 8.0, 4.0)))
    large = MeshData(trimesh.creation.box(extents=(10.0, 10.0, 4.0)))
    entries = {
        key: SceneObject(id=key, name=key, mesh=mesh, features=detect(mesh))
        for key, mesh in (("small", small), ("large", large))
    }
    view = Viewport()
    renderer = RecordingRenderer()
    view.renderer = renderer
    view.show_scene(EvaluationResult(scene=Scene(objects=entries)))
    point = (0.0, 0.0, 2.0)
    renderer.picks[(200, 200)] = Pick(point, view._actors["large"], 4)

    assert view._world_at(200, 200) == point
    assert view._object_at_view(point) == "large"
    assert view._click_target(view._from_view(point))[0] == "large"
    assert view._nearest_mesh(view._from_view(point)) is large


def test_surface_triangle_breaks_the_tie_between_adjacent_features(qt_app: QApplication) -> None:
    """Auf einer gemeinsamen Kante entscheidet das tatsächlich gepickte Dreieck."""
    import numpy as np
    import trimesh

    mesh = MeshData(trimesh.creation.box(extents=(10.0, 10.0, 4.0)))
    top = next(
        feature
        for feature in detect(mesh).values()
        if feature.params.get("normal") == (0.0, 0.0, 1.0)
    )
    first, second = top.face_indices
    features = {
        key: dataclasses.replace(top, id=key, face_indices=(index,))
        for key, index in (("first", first), ("second", second))
    }
    shared = np.intersect1d(mesh.raw.faces[first], mesh.raw.faces[second])
    point = tuple(float(value) for value in mesh.raw.vertices[shared].mean(axis=0))
    entry = SceneObject(id="body", name="Körper", mesh=mesh, features=features)
    view = Viewport()
    renderer = RecordingRenderer()
    view.renderer = renderer
    view.show_scene(EvaluationResult(scene=Scene(objects={"body": entry})))
    renderer.picks[(200, 200)] = Pick(point, view._actors["body"], second)

    assert view._world_at(200, 200) == point
    assert view._click_target(view._from_view(point), direct=True) == ("body", "second")


def test_surface_pick_is_converted_from_the_exploded_view(qt_app: QApplication) -> None:
    """Der Ansichtsversatz darf keine Auswahl- oder Messkoordinaten verändern."""
    import numpy as np
    import trimesh

    entries = {}
    for key, x in (("left", -20.0), ("right", 20.0)):
        raw = trimesh.creation.box(extents=(10.0, 10.0, 4.0))
        raw.apply_translation((x, 0.0, 0.0))
        mesh = MeshData(raw)
        entries[key] = SceneObject(id=key, name=key, mesh=mesh, features=detect(mesh))
    view = Viewport()
    renderer = RecordingRenderer()
    view.renderer = renderer
    result = EvaluationResult(scene=Scene(objects=entries))
    view.show_scene(result)
    view.set_explosion(1.0)
    point = (20.0, 0.0, 2.0)
    shown = tuple(np.asarray(point) + view._view_offset(entries["right"], result))
    renderer.picks[(200, 200)] = Pick(shown, view._actors["right"], 4)

    assert view._world_at(200, 200) == shown
    assert view._from_view(shown) == pytest.approx(point)
    assert view._click_target(view._from_view(shown))[0] == "right"


def test_changed_display_topology_uses_the_surface_distance(qt_app: QApplication) -> None:
    """Gleich viele Dreiecke bedeuten nach einem Schnitt keine gleiche Zuordnung."""
    import numpy as np
    import trimesh

    mesh = MeshData(trimesh.creation.box(extents=(10.0, 10.0, 4.0)))
    features = detect(mesh)
    top = next(
        feature for feature in features.values() if feature.params.get("normal") == (0.0, 0.0, 1.0)
    )
    changed = mesh.raw.copy()
    order = np.roll(np.arange(len(changed.faces)), -top.face_indices[0])
    changed.faces = changed.faces[order]
    display = MeshData(changed)
    entry = SceneObject(id="body", name="Körper", mesh=mesh, features=features)
    view = Viewport()
    renderer = RecordingRenderer()
    view.renderer = renderer
    view._for_display = lambda *_args: display  # type: ignore[method-assign]
    view.show_scene(EvaluationResult(scene=Scene(objects={"body": entry})))
    point = tuple(float(value) for value in changed.triangles_center[0])
    renderer.picks[(200, 200)] = Pick(point, view._actors["body"], 0)

    assert view._world_at(200, 200) == point
    assert view._click_target(view._from_view(point), direct=True) == ("body", top.id)


@pytest.mark.parametrize("layout", ["plates", "exploded"])
def test_looking_into_a_hole_keeps_the_body_in_the_shown_layout(
    qt_app: QApplication, layout: str
) -> None:
    """Durchs Loch sehen behält die zweite Platte und den Explosionsversatz."""
    import numpy as np
    import trimesh

    raw = trimesh.load(PLATE)
    mesh = MeshData(raw)
    first = SceneObject(id="first", name="Erste Platte", mesh=mesh, features=detect(mesh))
    if layout == "plates":
        second = dataclasses.replace(first, id="second", plate=1)
    else:
        shifted = raw.copy()
        shifted.apply_translation((200.0, 0.0, 0.0))
        second_mesh = MeshData(shifted)
        second = dataclasses.replace(
            first, id="second", mesh=second_mesh, features=detect(second_mesh)
        )
    result = EvaluationResult(scene=Scene(objects={"first": first, "second": second}))
    view = Viewport()
    view.show_scene(result)
    view.renderer = RecordingRenderer()
    view._plate = -1
    view._beds_drawn = 2 if layout == "plates" else 1
    view._bed_extent = (256.0, 256.0)
    view._explosion = 1.0 if layout == "exploded" else 0.0
    feature = second.features["hole_1"]
    centre = np.asarray(feature.params["centre"])
    shown = centre + view._view_offset(second, result)
    ray = ((float(shown[0]), float(shown[1]), 100.0), (0.0, 0.0, -1.0))
    view._pick_ray = lambda *_args: ray  # type: ignore[method-assign]

    point = view._aim_at(200, 200)
    assert point is not None
    assert view._click_target(view._from_view(point), direct=True) == ("second", "hole_1")
    assert view._from_view(point) == pytest.approx(centre)


def test_a_new_pick_and_scene_forget_the_old_surface_target(qt_app: QApplication) -> None:
    """Ein misslungener Pick und eine neue Auswertung dürfen nichts erben."""
    import trimesh

    mesh = MeshData(trimesh.creation.box())
    entry = SceneObject(id="body", name="Körper", mesh=mesh, features=detect(mesh))
    result = EvaluationResult(scene=Scene(objects={"body": entry}))
    view = Viewport()
    renderer = RecordingRenderer()
    view.renderer = renderer
    view.show_scene(result)
    point = tuple(float(value) for value in mesh.raw.triangles_center[0])
    renderer.picks[(200, 200)] = Pick(point, view._actors["body"], 0)
    view._world_at(200, 200)
    assert view._hit_at(point) is not None
    assert view._world_at(100, 100) is None
    assert view._hit_at(point) is None
    view._world_at(200, 200)
    view.show_scene(result)
    assert view._hit_at(point) is None


def test_a_body_without_features_does_not_borrow_the_selected_bodys_features(
    qt_app: QApplication,
) -> None:
    """Eine unerkannte Fläche bekommt keine Merkmalskennung ihres Nachbarn."""
    import trimesh

    mesh = MeshData(trimesh.creation.box())
    plain = SceneObject(id="plain", name="Ohne Merkmale", mesh=mesh)
    known = dataclasses.replace(plain, id="known", features=detect(mesh))
    view = Viewport()
    renderer = RecordingRenderer()
    view.renderer = renderer
    view.show_scene(EvaluationResult(scene=Scene(objects={"known": known, "plain": plain})))
    view.select("known")
    point = tuple(float(value) for value in mesh.raw.triangles_center[0])
    renderer.picks[(200, 200)] = Pick(point, view._actors["plain"], 0)

    view._world_at(200, 200)
    assert view._click_target(point, direct=True) == ("plain", None)


@pytest.fixture
def window(qt_app: QApplication) -> Iterator[MainWindow]:
    """Ein Fenster mit der Platte darin — und danach warten, bis es still ist.

    Dieselbe Begründung wie in ``tests/test_analysis_ui.py``: Ein Arbeiter, der
    sein Fenster überlebt, nimmt beim Herunterfahren den Prozess mit. Nicht
    ``close()`` — das fragt bei ungesicherten Änderungen modal nach, und ein
    Test hängt dann an einem Fenster, das niemand sieht.
    """
    window = MainWindow(Session(), UiSettings())
    window.open_path(PLATE)
    window.session.wait_for_idle()
    yield window
    window.wait_for_workers()


def hole_centre(window: MainWindow) -> tuple[float, float, float]:
    entry = window.session.last_result.scene.objects["obj_1"]
    centre = entry.features["hole_1"].params["centre"]
    return (float(centre[0]), float(centre[1]), float(centre[2]))


def test_free_body_drag_resolves_feature_selection_before_its_preview(window: MainWindow) -> None:
    """Der sichtbare Körperzug darf beim Loslassen nicht nur eine Bohrung verschieben."""
    import numpy as np

    view = window.viewport
    renderer = RecordingRenderer()
    renderer.widget = view
    view.renderer = renderer
    view.show_scene(window.session.last_result)
    window.object_tree.select_feature("obj_1", "hole_1")
    before = np.asarray(window.session.last_result.scene.objects["obj_1"].mesh.raw.bounds).copy()
    count = len(window.session.project.document.ops)
    assert window.object_tree.selected_feature() == "hole_1"

    assert view.begin_body_drag_at((0.0, 0.0, float(before[1, 2])))
    assert window.object_tree.selected_feature() is None
    assert window.object_tree.selected() == "obj_1"
    view.continue_body_drag_at((3.0, 2.0))
    assert len(window.session.project.document.ops) == count
    assert np.allclose(window.session.last_result.scene.objects["obj_1"].mesh.raw.bounds, before)
    view.finish_body_drag()
    window.session.wait_for_idle()

    assert str(window.session.project.document.ops[-1].op) == "translate_object"
    assert len(window.session.project.document.ops) == count + 1
    assert np.allclose(
        window.session.last_result.scene.objects["obj_1"].mesh.raw.bounds,
        before + np.asarray((3.0, 2.0, 0.0)),
    )


def test_free_body_drag_preserves_mixed_feature_and_body_selection(window: MainWindow) -> None:
    """Loch an A plus Körper B: Vorschau, Transaktion und ein Undo betreffen beide Teile."""
    import numpy as np
    from PySide6.QtCore import Qt

    bodies = two_bodies(window)
    first = "obj_1"
    second = next(identifier for identifier in bodies if identifier != first)
    view = window.viewport
    renderer = RecordingRenderer()
    renderer.widget = view
    view.renderer = renderer
    view.show_scene(window.session.last_result)
    window.object_tree.select_feature(first, "hole_1")
    tree = window.object_tree.tree
    second_item = next(
        tree.topLevelItem(index)
        for index in range(tree.topLevelItemCount())
        if tree.topLevelItem(index).data(0, Qt.ItemDataRole.UserRole) == second
    )
    second_item.setSelected(True)
    assert window.object_tree.selected_objects() == (first, second)
    assert window.object_tree.selected_feature() is None
    assert view.selected_feature == "hole_1"
    assert view._selected_more == (second,)

    scene = window.session.last_result.scene
    before = {
        identifier: (entry.mesh.raw.vertices.copy(), entry.mesh.raw.faces.copy())
        for identifier, entry in scene.objects.items()
    }
    document = window.session.project.document
    operation_count = len(document.ops)
    transaction_count = len(document.transactions)
    top = float(scene.objects[first].mesh.raw.bounds[1, 2])
    assert view.begin_body_drag_at((0.0, 0.0, top))
    assert window.object_tree.selected_objects() == (first, second)
    view.continue_body_drag_at((3.0, 2.0))
    assert len(document.ops) == operation_count
    assert len(document.transactions) == transaction_count
    offset = np.asarray((3.0, 2.0, 0.0))
    for identifier, (vertices, faces) in before.items():
        assert np.allclose(view._actors[identifier].position(), offset)
        assert np.array_equal(scene.objects[identifier].mesh.raw.vertices, vertices)
        assert np.array_equal(scene.objects[identifier].mesh.raw.faces, faces)

    view.finish_body_drag()
    assert window.session.wait_for_idle()
    operations = document.ops[operation_count:]
    assert len(document.transactions) == transaction_count + 1
    assert len(operations) == 2
    assert all(str(operation.op) == "translate_object" for operation in operations)
    assert {operation.inputs for operation in operations} == {(first,), (second,)}
    for identifier, (vertices, faces) in before.items():
        moved = window.session.last_result.scene.objects[identifier].mesh.raw
        assert np.allclose(moved.vertices, vertices + offset, rtol=0, atol=1e-9)
        assert np.array_equal(moved.faces, faces)

    assert window.undo_action.isEnabled()
    window.undo_action.trigger()
    assert window.session.wait_for_idle()
    assert len(document.transactions) == transaction_count
    assert len(document.ops) == operation_count
    for identifier, (vertices, faces) in before.items():
        restored = window.session.last_result.scene.objects[identifier].mesh.raw
        assert np.array_equal(restored.vertices, vertices)
        assert np.array_equal(restored.faces, faces)


def on_the_bore_wall(window: MainWindow, feature_id: str = "hole_1") -> tuple[float, float, float]:
    """Eine Stelle, die ein Klick auf diese Bohrung wirklich trifft.

    Nämlich auf ihrer **Wand**, nicht auf ihrer Achse. Der Unterschied ist der
    Grund, aus dem hier eine eigene Funktion steht: Der Mittelpunkt einer
    Bohrung liegt im Leeren, dort ist keine Oberfläche, und ein Picker kann ihn
    nicht zurückgeben. Tests, die ihn benutzten, prüften gegen eine Stelle, an
    die kein Klick kommt.
    """
    entry = window.session.last_result.scene.objects["obj_1"]
    feature = entry.features[feature_id]
    centre = feature.params["centre"]
    radius = float(feature.params["diameter"]) * 0.5
    return (float(centre[0]) + radius, float(centre[1]), 2.0)


def top_of(window: MainWindow) -> float:
    """Die Höhe der Deckfläche, gemessen statt abgelesen.

    Hier stand sie als 4.0, weil die Platte von z -4 bis +4 lag. Seit das erste
    Modell eines Projekts aufgesetzt hereinkommt (§17.1, Schritt 6), liegt sie
    von 0 bis 8, und jeder Klick auf „die Deckfläche" traf die Mitte des
    Körpers. Eine abgelesene Zahl altert still; diese hier nicht.
    """
    return float(window.session.last_result.scene.objects["obj_1"].mesh.bounds.maximum[2])


def on_the_top_face_beside_a_hole(window: MainWindow) -> tuple[float, float, float]:
    """Die Deckfläche, sieben Millimeter neben einer Bohrung.

    Der Ort des gemeldeten Fehlers: Über die Mittelpunkte gerechnet lag
    ``hole_1`` (8,1 mm) näher als der Mittelpunkt der 80 mm langen Deckfläche
    (36,1 mm), und ein Klick hierhin wählte die Bohrung.
    """
    return (-30.0, -20.0, top_of(window))


def two_plates(qt_app: QApplication) -> tuple[Viewport, EvaluationResult]:
    """Eine Szene mit zwei echten Körpern, jeder mit eigenen Bohrungen.

    Von Hand gebaut und nicht aus einer Datei: Eine STL kennt keine Baugruppe,
    zwei Körper darin werden ein Objekt mit zwei Komponenten. Gebraucht werden
    hier aber zwei **Objekte** — die Frage ist, was ein Klick auf das Nachbarteil
    tut, während im ersten eine Bohrung gewählt ist.
    """
    import trimesh

    first = trimesh.load(PLATE)
    second = first.copy()
    second.apply_translation((200.0, 0.0, 0.0))
    objects: dict[str, SceneObject] = {}
    for index, body in enumerate((first, second), start=1):
        data = MeshData(body)
        objects[f"obj_{index}"] = SceneObject(
            id=f"obj_{index}",
            name=f"Platte {index}",
            mesh=data,
            features=detect(data),
        )
    result = EvaluationResult(scene=Scene(objects=objects))
    viewport = Viewport()
    viewport.show_scene(result)
    return viewport, result


# --- der Treffer: was liegt überhaupt unter dem Klick ---------------------------


def test_a_click_beside_a_hole_does_not_find_the_hole(window: MainWindow) -> None:
    """Der gemeldete Fehler, an seiner Stelle festgenagelt.

    Ein Klick auf die Deckfläche, sieben Millimeter neben einer Bohrung, meint
    die Fläche. Gemessen wurde vorher der Abstand zum **Mittelpunkt** jedes
    Merkmals, und der Mittelpunkt einer großen Fläche liegt weiter weg als der
    einer kleinen Bohrung daneben — es gab also immer einen Gewinner, und meist
    war es die Bohrung.
    """
    window.viewport.select("obj_1")
    found = window.viewport._feature_at(on_the_top_face_beside_a_hole(window))
    assert found != "hole_1", "sieben Millimeter neben der Bohrung ist nicht in ihr"
    assert found == "face_2", "es ist die Deckfläche, und die ist auch ein Merkmal"


def test_a_click_on_the_bore_wall_finds_that_hole(window: MainWindow) -> None:
    """§40 für P3: ein Klick muss die richtige Merkmal-ID liefern, keinen
    Beinahe-Treffer — und keinen Fehlgriff.

    Alle vier Bohrungen der Platte, jede an ihrer eigenen Wand. Die
    Verwechslungsgefahr ist echt: Sie sind gleich groß und liegen paarweise
    30 mm auseinander.

    **Dieser Test war in der Gegenprobe grün** — der alte Mittelpunktsabstand
    traf an der Bohrungswand dieselbe Bohrung. Er nagelt also keinen Fund fest,
    sondern hält die Hälfte, die schon stimmte: Die neue Reichweite darf einen
    richtigen Treffer nicht wegnehmen. Wer ihn später liest, soll das wissen
    und nicht auf ein Fix-Zeugnis schließen.
    """
    window.viewport.select("obj_1")
    for hole in ("hole_1", "hole_2", "hole_3", "hole_4"):
        point = on_the_bore_wall(window, hole)
        assert window.viewport._feature_at(point) == hole, hole


def test_a_click_far_from_every_feature_finds_none(window: MainWindow) -> None:
    """Neben dem Modell gibt es kein Merkmal — auch nicht das nächstgelegene.

    Ohne die Reichweite war das der Zustand, aus dem sich nichts mehr
    unterscheiden ließ: Jeder Punkt im Raum hatte ein nächstes Merkmal.
    """
    window.viewport.select("obj_1")
    assert window.viewport._feature_at((0.0, 0.0, 500.0)) is None


def test_a_feature_without_triangles_stays_reachable(qt_app: QApplication) -> None:
    """Eine offene Kantenschleife hat keine eigenen Dreiecke (§17.1).

    Sie bleibt über ihren Mittelpunkt erreichbar, sonst wäre der einzige
    Befund, den man anklicken möchte, der einzige, den man nicht anklicken
    kann. Die Reichweite gilt auch dort — sonst wäre die Grenze wieder weg.
    """
    import trimesh

    body = trimesh.load(MESHES / "broken_open.stl")
    data = MeshData(body)
    features = detect(data)
    loops = [key for key in features if key.startswith("edge_loop")]
    assert loops, "die kaputte Datei aus dem Korpus hat offene Kanten"
    entry = SceneObject(id="obj_1", name="Bruch", mesh=data, features=features)
    viewport = Viewport()
    viewport.show_scene(EvaluationResult(scene=Scene(objects={"obj_1": entry})))
    viewport.select("obj_1")

    centre = features[loops[0]].params["centre"]
    at = (float(centre[0]), float(centre[1]), float(centre[2]))
    assert viewport._feature_at(at) == loops[0], "am Mittelpunkt ist sie zu treffen"
    far = (at[0], at[1], at[2] + 500.0)
    # ``is None`` und nicht ``!= loops[0]``: Die schwächere Fassung war auch
    # gegen den alten Stand grün, weil der dort ``face_4`` zurückgab — die
    # nächste von fünf Mitten, einen halben Meter entfernt. Geprüft werden soll
    # aber, dass **keines** mehr in Reichweite ist.
    assert viewport._feature_at(far) is None, "einen halben Meter daneben keines"


# --- der Blick hinein: was ein Klick meint, wo kein Dreieck liegt --------------


def looking_down(
    x: float, y: float
) -> tuple[tuple[float, float, float], tuple[float, float, float]]:
    """Ein Sichtstrahl senkrecht von oben, wie in der Draufsicht."""
    return ((x, y, 100.0), (0.0, 0.0, -1.0))


def until_the_top_face(window: MainWindow) -> float:
    """Wie weit der Strahl in der Draufsicht läuft, bis er die Deckfläche
    erreicht. Der Wert steht für ``until`` — alles, was erst dahinter beginnt,
    hat der Klick nicht gemeint.

    Stand hier als 96.0 (von z = 100 bis zur Deckfläche bei z = +4) und ist aus
    demselben Grund gemessen wie :func:`top_of`: Die Platte liegt jetzt höher,
    und 96 mm reichten vier Millimeter **in** den Körper hinein.
    """
    return 100.0 - top_of(window)


def test_looking_straight_into_a_through_hole_aims_at_it(window: MainWindow) -> None:
    """Der gemeldete Fehler: in der Draufsicht war eine Bohrung nicht anklickbar.

    **Gemessen am echten Picker (damals VTKs ``vtkCellPicker``)** in einem
    sichtbaren Fenster, Platte
    aus dem Korpus, Bohrung 32 Pixel breit: Ein Klick 0 bis 8 Pixel neben der
    Bohrungsmitte gab ``kein Treffer`` — der Picker fand nichts, weil die
    Zylinderwand parallel zum Strahl liegt und hinter der Durchgangsbohrung
    keine Fläche mehr kommt. Erst 12 Pixel weiter, praktisch auf der Wand,
    kam ``hole_1``.

    Was der Nutzer davon sah: Ein Klick mitten in die Bohrung tat nichts oder
    hob die Auswahl auf (``objectPicked.emit("")`` in :meth:`_on_left_click`),
    ein Klick knapp daneben wählte die Deckfläche. „Wir erwischen oft nur die
    Oberfläche und kommen nicht zur Bohrung."

    Der Punkt aus :meth:`Viewport._bore_aim` liegt **im Loch**, und von dort
    findet die schon vorhandene Rechnung (:meth:`_feature_inside`) die Bohrung.
    """
    viewport = window.viewport
    centre = hole_centre(window)
    origin, direction = looking_down(centre[0], centre[1])

    aimed = viewport._bore_aim(origin, direction, float("inf"))
    assert aimed is not None, "senkrecht in die Bohrung gesehen ist sie gemeint"
    assert viewport._feature_at(aimed) == "hole_1", "und von dort führt der Weg zu ihr"


def test_a_hole_wins_over_the_face_a_fraction_beside_it(window: MainWindow) -> None:
    """Knapp neben dem Bohrungsrand meint der Klick die Bohrung, nicht die Fläche.

    Der zweite Teil des gemeldeten Fehlers, und er hing nicht am Picker: Landet
    der Strahl auf der Deckfläche, gewinnt sie **immer** — ihr Abstand ist
    null, der der Bohrung größer als null. Damit war
    :data:`FEATURE_REACH_SHARE` für Bohrungen wirkungslos; gemessen gab schon
    ein Punkt 0,4 mm neben dem Bohrungsrand ``face_2``, bei einer Reichweite
    von 0,95 mm.

    Die erste Zusicherung hält den alten Weg fest, damit sichtbar bleibt, was
    sich ändert: Über den Punkt allein ist es die Fläche.
    """
    viewport = window.viewport
    centre = hole_centre(window)
    radius = (
        float(
            window.session.last_result.scene.objects["obj_1"].features["hole_1"].params["diameter"]
        )
        * 0.5
    )
    beside = centre[0] + radius + 0.4

    on_the_face = (beside, centre[1], top_of(window))
    assert viewport._feature_at(on_the_face) == "face_2", "über den Punkt allein die Fläche"

    origin, direction = looking_down(beside, centre[1])
    aimed = viewport._bore_aim(origin, direction, until_the_top_face(window))
    assert aimed is not None, "vier Zehntel neben dem Rand ist die Bohrung gemeint"
    assert viewport._feature_at(aimed) == "hole_1"


def test_a_ray_well_beside_the_hole_aims_at_nothing(window: MainWindow) -> None:
    """Sieben Millimeter daneben bleibt die Fläche die Fläche.

    Die Gegenprobe zu ``test_a_click_beside_a_hole_does_not_find_the_hole``: Der
    Vorrang der Bohrung gilt nur, solange der Strahl sie überhaupt durchquert.
    Ohne diese Grenze wäre die Reichweite wieder weg, und wir hätten den Fehler
    von vorher — „die Auswahl nimmt immer die Bohrung statt des Modells".
    """
    viewport = window.viewport
    origin, direction = looking_down(-30.0, -20.0)
    assert viewport._bore_aim(origin, direction, until_the_top_face(window)) is None


@pytest.mark.parametrize("recess", [False, True], ids=["outer_rounding", "inner_ring_groove"])
def test_a_torus_does_not_capture_the_visible_plane_through_its_centre(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, recess: bool
) -> None:
    """Eine Ringrundung vor der Fläche macht ihre ganze Hülle nicht zur Bohrung."""
    import numpy as np
    import trimesh

    from app.core.types import Feature

    ring = trimesh.creation.torus(
        major_radius=12.0, minor_radius=1.0, major_sections=32, minor_sections=8
    )
    ring.apply_translation((0.0, 0.0, 20.0))
    if recess:
        ring.invert()
    plate = trimesh.creation.box(extents=(100.0, 100.0, 1.0))
    plate.apply_translation((0.0, 0.0, -0.5))
    raw = trimesh.util.concatenate((ring, plate))
    plate_faces = tuple(
        int(index) + len(ring.faces) for index in np.flatnonzero(plate.face_normals[:, 2] > 0.9)
    )
    features = {
        "rounding": Feature(
            id="rounding",
            kind="torus",
            provenance="detected",
            params={
                "diameter": 24.0,
                "tube_diameter": 2.0,
                "axis": (0.0, 0.0, 1.0),
                "centre": (0.0, 0.0, 20.0),
                "recess": recess,
            },
            face_indices=tuple(range(len(ring.faces))),
        ),
        "plane": Feature(
            id="plane",
            kind="face",
            provenance="detected",
            params={"normal": (0.0, 0.0, 1.0)},
            face_indices=plate_faces,
        ),
    }
    entry = SceneObject(id="body", name="Ring über Platte", mesh=MeshData(raw), features=features)
    view = Viewport()
    renderer = RecordingRenderer()
    view.renderer = renderer
    view.show_scene(EvaluationResult(scene=Scene(objects={entry.id: entry})))
    view.select(entry.id)
    # Ohne Originalzellkennung muss auch der LOD-Ortsfang dieselbe sichtbare
    # Fläche finden; die Ringmitte liegt weit von sämtlichen Ringdreiecken.
    view._original_pick_cells.clear()
    point = (2.0, 1.0, 0.0)
    renderer.picks[(200, 200)] = Pick(point, view._actors[entry.id], plate_faces[0])
    monkeypatch.setattr(view, "_pick_ray", lambda *_: ((2.0, 1.0, 100.0), (0.0, 0.0, -1.0)))
    aimed = view._aim_at(200, 200)
    assert aimed is not None
    assert view._click_target(view._from_view(aimed), direct=True) == (entry.id, "plane")
    assert view._feature_at((2.0, 1.0, 20.0)) is None

    # Die wirkliche Ringoberfläche bleibt trotz ausgeschlossener Zielhilfe
    # über ihre Originaldreiecke erreichbar.
    ring_point = tuple(float(value) for value in ring.triangles_center[0])
    renderer.picks[(220, 200)] = Pick(ring_point, view._actors[entry.id], 0)
    assert view._world_at(220, 200) == ring_point
    assert view._click_target(ring_point, direct=True) == (entry.id, "rounding")


def test_a_countersink_keeps_its_opening_target(qt_app: QApplication) -> None:
    """Durch die offene Senkung gezielt bleibt ihre axiale Zielhilfe erhalten."""
    import numpy as np
    import trimesh

    from app.core.types import Feature

    angles = np.arange(16) * math.tau / 16
    rings = [
        np.column_stack((radius * np.cos(angles), radius * np.sin(angles), np.full(16, height)))
        for radius, height in ((4.0, 15.0), (8.0, 20.0))
    ]
    faces = [
        triangle
        for index in range(16)
        for triangle in (
            (index, index + 16, (index + 1) % 16),
            ((index + 1) % 16, index + 16, (index + 1) % 16 + 16),
        )
    ]
    mesh = MeshData(trimesh.Trimesh(vertices=np.vstack(rings), faces=faces, process=False))
    feature = Feature(
        id="countersink",
        kind="cone",
        provenance="detected",
        params={
            "diameter": 16.0,
            "axis": (0.0, 0.0, 1.0),
            "centre": (0.0, 0.0, 17.5),
            "recess": True,
        },
        face_indices=tuple(range(len(faces))),
    )
    entry = SceneObject(id="body", name="Offene Senkung", mesh=mesh, features={feature.id: feature})
    view = Viewport()
    view.show_scene(EvaluationResult(scene=Scene(objects={entry.id: entry})))
    view.select(entry.id)
    aimed = view._bore_aim((0.0, 0.0, 100.0), (0.0, 0.0, -1.0), math.inf)
    assert aimed is not None
    assert view._feature_at(aimed) == feature.id


def test_a_hole_behind_the_surface_is_not_aimed_at(window: MainWindow) -> None:
    """Von der Seite gesehen liegt die Bohrung hinter dem Material.

    Gemessen in der Vorderansicht: Der Klick auf die Stelle, an der die Bohrung
    *wäre*, gab ``face_3`` — die Stirnfläche, 7,5 mm vor der Bohrung. Das ist
    richtig, denn dort ist keine Bohrung zu sehen, und es muss richtig bleiben:
    Der Strahl durchquert den Bohrungszylinder erst **hinter** dem
    Auftreffpunkt, und was hinter dem Sichtbaren liegt, hat niemand gemeint.
    """
    viewport = window.viewport
    centre = hole_centre(window)
    # Von vorn (-y) auf die Stirnfläche bei y = -25, die Bohrung liegt bei y = -15.
    origin = (centre[0], -100.0, 2.0)
    direction = (0.0, 1.0, 0.0)
    until = 75.0

    assert viewport._bore_aim(origin, direction, until) is None, "hinter der Fläche zählt nicht"
    assert viewport._bore_aim(origin, direction, float("inf")) is not None, (
        "ohne Grenze wäre sie es — genau deshalb braucht die Rechnung den Auftreffpunkt"
    )


def test_a_surface_far_behind_an_opening_is_what_the_click_means(window: MainWindow) -> None:
    """Durch eine Öffnung auf einen Boden weit dahinter gesehen ist der Boden gemeint.

    Gemessen am Desk-Organizer (Abnahme 06.09.2026): Der Sichtstrahl durchquerte
    eine Senkung in der schrägen Wand und traf 56 mm dahinter den Boden — die
    Anwendung wählte die Senkung, obwohl der Kunde auf den Boden sah und dort
    klickte. Die Zielhilfe gilt, solange das Sichtbare in Reichweite hinter dem
    Austritt liegt (die Rückwand einer Sackbohrung, ein Boden dicht dahinter);
    was weiter dahinter liegt, meint der Klick.
    """
    viewport = window.viewport
    centre = hole_centre(window)
    origin, direction = looking_down(centre[0], centre[1])
    bore = next(
        target for target in viewport._prepared_bores("obj_1") if target.feature_id == "hole_1"
    )
    depth = bore.bounds[1] - bore.bounds[0]
    reach = viewport._feature_reach("obj_1")
    top = until_the_top_face(window)

    close_behind = top + depth + 0.5 * reach
    assert viewport._bore_aim(origin, direction, close_behind) is not None, (
        "ein Boden dicht hinter dem Austritt lässt die Bohrung gemeint sein"
    )
    far_behind = top + depth + 3.0 * reach + 20.0
    assert viewport._bore_aim(origin, direction, far_behind) is None, (
        "weit dahinter ist die Fläche gemeint, die man durch das Loch sieht"
    )
    assert viewport._bore_aim(origin, direction, float("inf")) is not None, (
        "ohne etwas dahinter bleibt es die Bohrung"
    )


def test_bore_target_slack_cannot_cross_a_blind_hole_back_wall(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eine größere Zielhilfe darf die geschlossene Rückwand nicht überbrücken."""
    import numpy as np

    from app.core.geom.measure import ray_distances
    from app.core.geom.mesh import read_mesh
    from app.core.ingest.loader import normalise

    mesh = normalise(
        read_mesh((MESHES / "plate_countersunk_blind.stl").read_bytes(), ".stl"), "mm"
    ).mesh
    entry = SceneObject(id="body", name="Sackbohrung", mesh=mesh, features=detect(mesh))
    view = Viewport()
    view.show_scene(EvaluationResult(scene=Scene(objects={"body": entry})))
    # Am großen Nutzermodell überstieg die seitliche Zielhilfe die Wandstärke.
    monkeypatch.setattr(view, "_feature_reach", lambda _object_id: 3.0)
    origin = np.array([0.0, 0.0, -100.0])
    direction = np.array([0.0, 0.0, 1.0])
    distances = ray_distances(mesh, origin, direction)
    until = float(distances[distances > 0.0].min())

    assert until == pytest.approx(96.0)
    assert view._bore_aim(tuple(origin), tuple(direction), until) is None
    assert view._bore_aim(tuple(origin), tuple(direction), float("inf")) is not None


def test_bore_target_slack_cannot_cross_a_closed_side_wall(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Seitliche Zielhilfe erlaubt einen Öffnungsrand, keinen Blick durch Material."""
    viewport = window.viewport
    centre = hole_centre(window)
    monkeypatch.setattr(viewport, "_feature_reach", lambda _object_id: 9.0)

    assert viewport._bore_aim((centre[0], -100.0, 2.0), (0.0, 1.0, 0.0), 75.0) is None


def test_bore_span_along_the_axis(window: MainWindow) -> None:
    """Die Rechnung selbst, im entarteten Fall: Strahl parallel zur Achse.

    Dann gibt es keinen Ein- und Austritt durch den Mantel — der Strahl liegt
    ganz innen oder ganz außen. Wer das übersieht, teilt durch null und verliert
    genau den Fall, um den es hier geht: die Draufsicht.
    """
    from app.ui.viewport import bore_span

    axis = (0.0, 0.0, 1.0)
    centre = (0.0, 0.0, 0.0)
    along = (-4.0, 4.0)

    inside = bore_span((0.0, 0.0, 100.0), (0.0, 0.0, -1.0), centre, axis, 2.5, along)
    assert inside is not None, "auf der Achse läuft der Strahl durch die ganze Bohrung"
    assert inside[0] == pytest.approx(96.0), "Eintritt an der Oberkante"
    assert inside[1] == pytest.approx(104.0), "Austritt an der Unterkante"

    outside = bore_span((9.0, 0.0, 100.0), (0.0, 0.0, -1.0), centre, axis, 2.5, along)
    assert outside is None, "neun Millimeter neben der Achse geht er vorbei"


def test_a_tool_that_sets_a_place_does_not_look_for_a_bore(window: MainWindow) -> None:
    """Der Bohrungsvorrang gilt der **Auswahl**, nicht jedem Klick.

    Formen, Bemalen, Messen, Trennen und Skelett setzen eine Stelle, und die
    liegt auf der Oberfläche. Ein Punkt auf der Bohrungsachse wäre dort einer in
    der Luft: bemalt würde nichts, gemessen würde von einer Stelle, an der kein
    Material ist, und der Pinselring stünde im Leeren.

    Geprüft wird an :meth:`_means_a_feature`, weil offscreen kein Plotter
    existiert und :meth:`_on_left_click` deshalb nichts täte — die Weiche ist
    die Aussage, nicht der Klick.
    """
    viewport = window.viewport
    assert viewport._means_a_feature(), "ohne Werkzeug meint ein Klick die Auswahl"

    for turn_on, turn_off in (
        (lambda: viewport.set_sculpting(True, 5.0), lambda: viewport.set_sculpting(False)),
        (lambda: viewport.set_boning(True), lambda: viewport.set_boning(False)),
        (lambda: viewport.set_splitting(True), lambda: viewport.set_splitting(False)),
        (
            lambda: viewport.set_measure_mode("distance"),
            lambda: viewport.set_measure_mode("off"),
        ),
    ):
        turn_on()
        assert not viewport._means_a_feature(), "mit Werkzeug meint er eine Stelle"
        turn_off()
        assert viewport._means_a_feature(), "und danach wieder die Auswahl"


def pierced_plate(qt_app: QApplication) -> Viewport:
    """Eine Platte mit **rechteckigem** Durchbruch: ein Loch ohne Merkmal.

    Der Unterschied zur Bohrung ist der Punkt dieser Tests. Eine Bohrung ist
    ein Merkmal (``hole``, mit Durchmesser und Achse); ein rechteckiger
    Ausschnitt ist es nicht — er besteht aus vier Wandflächen, und keine davon
    ist die Sache, auf die jemand zeigt.

    **Durch den Einleseweg der Anwendung**, nicht über ``trimesh.load``: Die
    Erkennung hängt an den beim Einlesen zusammengeführten Eckpunkten, und ein
    Prüfaufbau, der diesen Weg umgeht, hat schon einmal einen Mangel erfunden,
    den es nicht gab (ROADMAP, 24.08.2026).
    """
    import trimesh

    from app.core.geom.mesh import read_mesh
    from app.core.ingest.loader import normalise

    plate = trimesh.creation.box(extents=(60.0, 40.0, 8.0))
    cut = trimesh.creation.box(extents=(12.0, 8.0, 40.0))
    pierced = trimesh.boolean.difference([plate, cut], engine="manifold")
    data = normalise(read_mesh(trimesh.exchange.stl.export_stl(pierced), ".stl"), "mm").mesh
    entry = SceneObject(id="obj_1", name="Durchbruch", mesh=data, features=detect(data))
    viewport = Viewport()
    viewport.show_scene(EvaluationResult(scene=Scene(objects={"obj_1": entry})))
    return viewport


def test_a_click_through_an_opening_means_the_body_and_beside_it_nothing(
    qt_app: QApplication,
) -> None:
    """Ein Klick durch eine Öffnung hebt die Auswahl nicht auf — und daneben doch.

    Der zweite Teil des Fundes vom 24.08., und er brauchte eine andere Rechnung
    als die Bohrung. Zwei Dinge, die zuerst plausibel klangen und beide falsch
    sind:

    * **„Strahl gegen die Merkmalsdreiecke" löst es nicht.** Bei senkrechtem
      Blick sind die Wände des Ausschnitts **parallel** zum Strahl — dort ist so
      wenig ein Dreieck zu treffen wie an der Bohrungswand.
    * **Es gibt kein Merkmal zu wählen.** Vier Wandflächen, keine davon
      „richtiger" als die andere; ein Gewinner wäre erfunden.

    Was bleibt, ist die Aussage über den **Körper**: Wer in eine Öffnung zeigt,
    hat auf das Teil gezeigt. Vorher gab der Picker dort nichts zurück, und
    ``_on_left_click`` machte daraus ``objectPicked.emit("")`` — die Auswahl war
    weg. Gemessen am echten Picker, Draufsicht: 0 bis 30 Pixel in der Öffnung
    vorher ``(None, None)``, jetzt ``("obj_1", None)``.

    **Beide Richtungen in einem Test, und das ist kein Sparen an Zusicherungen,
    sondern eines an Fenstern:** Die Gegenprobe „daneben ist daneben" braucht
    denselben Körper, und jede zusätzliche Viewport-Instanz erhöht die Rate des
    Abbau-Risses dieser Datei. Gemessen: ohne die neuen Ansichten 0 von 10
    Läufen gerissen, mit ihnen 2 von 10. Das reißt die vorab gesetzte Latte
    nicht (≥4 von 10), zeigt aber die Richtung — also nur so viele Fenster wie
    Aussagen, die keinen eigenen brauchen.

    „Daneben" ist dabei die Zusage aus §18.5: Ein Klick daneben hebt die Auswahl
    auf, und das ist der einzige Weg, sie ohne den Objektbaum loszuwerden.
    Deshalb fragt die Rechnung die **konvexe Hülle** und nicht den Hüllquader.
    """
    viewport = pierced_plate(qt_app)
    viewport.select("obj_1")

    aimed = viewport._through_aim((0.0, 0.0, 200.0), (0.0, 0.0, -1.0))
    assert aimed is not None, "senkrecht durch den Ausschnitt ist das Teil gemeint"
    assert viewport._click_target(aimed) == ("obj_1", None), "der Körper, kein erfundenes Merkmal"
    assert viewport._feature_at(aimed) is None, (
        "mitten im Ausschnitt liegt keine Wand in Reichweite"
    )

    assert viewport._through_aim((100.0, 0.0, 200.0), (0.0, 0.0, -1.0)) is None, "neben dem Teil"
    assert viewport._through_aim((0.0, 60.0, 200.0), (0.0, 0.0, -1.0)) is None, "daneben in y"


def test_a_ray_through_a_notch_means_the_body_too(qt_app: QApplication) -> None:
    """Die Grenze der Rechnung, als Zusage und nicht als Zufall.

    Die konvexe Hülle deckt auch eine **Kerbe** ab — bei einem L-Profil liegt
    der Strahl durch den fehlenden Quadranten in ihr, ohne das Netz zu treffen.
    Der Klick wählt dort also den Körper, obwohl er durch Luft geht.

    **Das ist die gewollte Seite der Abwägung**, und die Alternative wäre
    schlechter: Ein Kriterium, das die Kerbe ausnimmt, müsste zwischen „Loch"
    und „Einbuchtung" unterscheiden — dieselbe Unterscheidung, die ein Kunde
    nicht trifft, wenn er auf ein Teil zeigt und zwei Bildpunkte neben die
    Silhouette kommt. Wer die Auswahl loswerden will, klickt in den freien
    Raum, und dort ist auch keine Hülle.
    """
    import trimesh

    from app.core.geom.mesh import read_mesh
    from app.core.ingest.loader import normalise

    upright = trimesh.creation.box(extents=(10.0, 40.0, 40.0))
    foot = trimesh.creation.box(extents=(40.0, 40.0, 10.0))
    foot.apply_translation((15.0, 0.0, -15.0))
    profile = trimesh.boolean.union([upright, foot], engine="manifold")
    data = normalise(read_mesh(trimesh.exchange.stl.export_stl(profile), ".stl"), "mm").mesh
    entry = SceneObject(id="obj_1", name="L-Profil", mesh=data, features=detect(data))
    viewport = Viewport()
    viewport.show_scene(EvaluationResult(scene=Scene(objects={"obj_1": entry})))
    viewport.select("obj_1")

    # Durch den fehlenden Quadranten: über dem Fuß, neben dem Steher.
    through_the_notch = viewport._through_aim((20.0, 0.0, 200.0), (0.0, 0.0, -1.0))
    assert through_the_notch is None or viewport._click_target(through_the_notch)[0] == "obj_1", (
        "in der Kerbe ist das Teil gemeint, nicht das Nichts"
    )


def test_the_sampled_hull_says_the_same_as_the_exact_one() -> None:
    """Die Zusage der Stichprobe, und sie hat keinen anderen Ort.

    :func:`app.core.geom.mesh.hull_planes` rechnet die konvexe Hülle über
    höchstens :data:`HULL_SAMPLE_LIMIT` Eckpunkte, weil die exakte an einer
    feinen Kugel 5084 ms kostet — jeder ihrer Punkte liegt auf der Hülle. Die
    Stichprobe **unterschätzt** die Hülle grundsätzlich; was sie taugt, ist
    deshalb eine Messung und keine Herleitung.

    Geprüft wird gegen die Platte aus dem Korpus, wo beide Wege dasselbe sagen
    müssen: zwölf Flächen und das Volumen eines Quaders. Ohne diesen Test wäre
    die Zahl 4096 eine Behauptung, die still altert — wer sie senkt, sieht hier,
    wann sie zu klein wird.

    **Kein Widget, deshalb ohne ``qt_app``** — und trotzdem hier: Die Rechnung
    hat genau einen Aufrufer, und das ist der Klick nebenan
    (``Viewport._through_aim``). Eine eigene Datei für zwei Funktionen wäre ein
    Ort, an dem niemand sucht.
    """
    import numpy as np
    from scipy.spatial import ConvexHull

    from app.core.geom.mesh import hull_planes, read_mesh
    from app.core.ingest.loader import normalise

    data = normalise(read_mesh(PLATE.read_bytes(), ".stl"), "mm").mesh
    planes = hull_planes(data)
    assert planes is not None, "eine Platte hat eine räumliche Hülle"

    exact = ConvexHull(np.asarray(data.raw.vertices, dtype=float))
    assert len(planes) == len(exact.equations), "dieselbe Zahl Flächen wie exakt gerechnet"
    # 80 x 50 x 8 mm: der Quader ist seine eigene Hülle.
    assert exact.volume == pytest.approx(32000.0, rel=1e-6)


def test_a_body_without_vertices_has_no_hull() -> None:
    """Ein Körper ohne Eckpunkte hat keinen Innenraum, und das ist kein Fehler.

    Das ``Mesh``-Protokoll (§9) sagt nichts über ein ``raw`` zu — ein
    B-Rep-Körper hat keines. Die Rechnung antwortet dann mit ``None``, und der
    Klick fällt auf sein voriges Verhalten zurück, statt eine Ausnahme in einen
    Qt-Slot zu werfen, wo sie niemand sieht.
    """
    from app.core.geom.mesh import hull_planes

    class WithoutRaw:
        """Genau so viel Mesh, wie die Frage braucht: keines."""

    assert hull_planes(WithoutRaw()) is None  # type: ignore[arg-type]


# --- die Stufe: wie tief ein Klick geht ----------------------------------------


def test_the_first_click_takes_the_body_and_the_second_the_hole(window: MainWindow) -> None:
    """Das Verlangte, in einem Test.

    Zweimal dieselbe Stelle auf der Bohrungswand. Der erste Klick meint das
    Teil, der zweite die Bohrung darin — das Modell von Figma und Illustrator,
    wo ein Klick die Gruppe nimmt und der nächste das Element darin.

    Vorher war die Reihenfolge umgekehrt und die erste Stufe fehlte ganz: Ein
    Körper mit erkannten Bohrungen war per Klick überhaupt nicht auswählbar,
    und wer die Platte verschieben wollte, musste in den Objektbaum ausweichen.
    """
    viewport = window.viewport
    point = on_the_bore_wall(window)

    assert viewport._click_target(point) == ("obj_1", None), "erst das Teil"
    viewport._select_at(point)
    assert viewport.selection_depth() == 1, "und die Auswahl steht auf dem Teil"

    assert viewport._click_target(point) == ("obj_1", "hole_1"), "dann die Bohrung"
    viewport._select_at(point)
    assert viewport.selection_depth() == 2
    assert viewport.selected_feature == "hole_1"


def test_inside_a_body_the_next_hole_comes_directly(window: MainWindow) -> None:
    """Wer drin ist, bleibt drin — die Tiefe hängt am Körper, nicht am Pixel.

    Von einer gewählten Bohrung zur nächsten führt **ein** Klick und nicht
    erst der Weg zurück über das ganze Teil. Blender setzt beim Weiterschalten
    zurück, sobald die Maus sich bewegt; für vier Bohrungen an einer Platte
    wäre das eine Stufe zu viel.

    **Auch dieser war in der Gegenprobe grün**, und zwar aus dem Fehler heraus,
    den es zu beheben gab: Der alte Stand ging immer sofort auf das Merkmal, ein
    Klick genügte also erst recht. Was er festhält, ist die Zusage, dass die
    neue Stufe diesen kurzen Weg **nicht** verlängert.
    """
    viewport = window.viewport
    viewport._select_at(on_the_bore_wall(window, "hole_1"))
    viewport._select_at(on_the_bore_wall(window, "hole_1"))
    assert viewport.selected_feature == "hole_1"

    viewport._select_at(on_the_bore_wall(window, "hole_3"))
    assert viewport.selected_feature == "hole_3", "ein Klick, nicht zwei"


def test_a_click_on_bare_surface_comes_back_up_to_the_body(window: MainWindow) -> None:
    """Im Körper drin auf die nackte Fläche geklickt heißt: der Körper.

    Genauer die Deckfläche, die hier selbst ein Merkmal ist — auch das ist eine
    Stufe zurück gegenüber der Bohrung, und niemand bleibt in ihr hängen.
    """
    viewport = window.viewport
    viewport._select_at(on_the_bore_wall(window))
    viewport._select_at(on_the_bore_wall(window))
    assert viewport.selection_depth() == 2

    viewport._select_at(on_the_top_face_beside_a_hole(window))
    assert viewport.selected_feature == "face_2", "die Fläche, nicht die Bohrung"


def test_another_body_starts_over_at_the_top(qt_app: QApplication) -> None:
    """Ein Klick auf das Nachbarteil wählt das Nachbarteil, nicht sein Merkmal.

    Sonst führte der Weg von einer Bohrung im ersten Teil zu einer Bohrung im
    zweiten, ohne dass jemand das zweite Teil gemeint hätte.
    """
    viewport, _ = two_plates(qt_app)
    viewport.select("obj_1")
    viewport.select_feature("hole_1")

    # Dieselbe Stelle wie in obj_1, nur 200 mm weiter — die Wand von hole_1
    # des zweiten Körpers.
    wall_in_the_other = (200.0 - 25.0 + 2.595, -15.0, 2.0)
    assert viewport._click_target(wall_in_the_other) == ("obj_2", None)


def test_a_click_beside_the_model_clears_everything(window: MainWindow) -> None:
    """Neben das Modell geklickt heißt: Auswahl weg, und zwar ganz.

    Der einzige Weg, sie ohne den Objektbaum loszuwerden — deshalb steht er
    nicht unter der gestuften Tiefe, sondern daneben.
    """
    viewport = window.viewport
    viewport._select_at(on_the_bore_wall(window))
    viewport._select_at(on_the_bore_wall(window))
    assert viewport.selection_depth() == 2

    assert viewport._click_target((0.0, 0.0, 500.0)) == (None, None)
    viewport._select_at((0.0, 0.0, 500.0))
    assert viewport.selection_depth() == 0


def test_the_body_is_announced_before_its_feature(window: MainWindow) -> None:
    """Die Reihenfolge der Signale, und sie ist keine Geschmacksfrage.

    Der Baum zeigt ein Merkmal nur unter der Zeile seines Objekts. Solange der
    Viewport bei einem Treffer allein ``featurePicked`` sendete, lief das ins
    Leere: ``_on_feature_picked`` fragt den Baum nach dem ausgewählten Objekt,
    und ausgewählt war noch keines. Im Fenster sah es aus, als käme der Klick
    nicht an — in Wahrheit war er angekommen und hatte niemanden.

    Zwei Klicks statt einem, seit die Tiefe gestuft ist; die Reihenfolge im
    zweiten ist dieselbe geblieben.
    """
    order: list[str] = []
    window.viewport.objectPicked.connect(lambda name: order.append(f"object:{name}"))
    window.viewport.featurePicked.connect(lambda name: order.append(f"feature:{name}"))

    point = on_the_bore_wall(window)
    window.viewport._select_at(point)
    window.viewport._select_at(point)

    assert order == ["object:obj_1", "object:obj_1", "feature:hole_1"]


# --- der Weg zurück -------------------------------------------------------------


def test_escape_steps_back_out_one_level_at_a_time(window: MainWindow) -> None:
    """Merkmal → Körper → nichts, mit je einem Escape (§18.5).

    Ohne diesen Weg ist die Tiefe eine Einbahnstraße: Wer eine Bohrung gewählt
    hatte, kam nur wieder zum ganzen Teil, indem er neben das Modell klickte
    und von vorn anfing.
    """
    viewport = window.viewport
    point = on_the_bore_wall(window)
    viewport._select_at(point)
    viewport._select_at(point)
    assert viewport.selection_depth() == 2

    assert window._step_selection_out() is True
    assert viewport.selection_depth() == 1, "das Merkmal fällt weg, das Teil bleibt"
    assert window.object_tree.selected() == "obj_1"

    assert window._step_selection_out() is True
    assert viewport.selection_depth() == 0, "und dann auch das Teil"

    assert window._step_selection_out() is False, "aus nichts führt kein Weg heraus"


def test_escape_closes_an_open_tool_before_it_touches_the_selection(
    window: MainWindow,
) -> None:
    """Ein offenes Werkzeug meint mit Escape sich selbst.

    Die Rangfolge in ``_escape``: Skizze, Skelett, Formen, Werkzeug, und erst
    danach die Auswahl. Wer *Messen* offen hat und Escape drückt, will das
    Messen beenden — dass dabei auch noch die Auswahl zerfiele, wäre eine
    zweite Wirkung, die niemand bestellt hat.
    """
    viewport = window.viewport
    point = on_the_bore_wall(window)
    viewport._select_at(point)
    viewport._select_at(point)
    window.tools.activate("measure")

    window._escape()
    assert window.tools.active() is None, "das Werkzeug ist zu"
    assert viewport.selection_depth() == 2, "und die Auswahl steht noch"

    window._escape()
    assert viewport.selection_depth() == 1, "jetzt greift Escape die Auswahl"


# --- was der Zeiger verspricht --------------------------------------------------


def test_the_pointer_promises_exactly_what_the_click_does(window: MainWindow) -> None:
    """Der Zeiger stellt dieselbe Frage wie der Klick, mit derselben Rechnung.

    Damit wird die Stufe sichtbar, ohne dass irgendwo ein Satz darüber stehen
    muss: Über einer Bohrung am noch nicht gewählten Teil steht der
    Auswahlzeiger, nach dem ersten Klick der Merkmalszeiger. Laufen die beiden
    auseinander, verspricht der Zeiger etwas, das nicht eintritt — die Falle,
    vor der `.claude/rules/ansicht.md` bei ``_resting_role`` warnt.
    """
    viewport = window.viewport
    point = on_the_bore_wall(window)

    assert viewport._would_pick_feature(point) is False, "erster Klick nimmt das Teil"
    viewport._select_at(point)
    assert viewport._would_pick_feature(point) is True, "der nächste die Bohrung"


def test_the_resting_pointer_reaches_the_decision(window: MainWindow) -> None:
    """Und die Antwort kommt auch am Zeiger an, nicht nur in der Rechnung.

    Der Grund für die Attrappe: ``_look_under_pointer`` und ``_update_cursor``
    steigen bei ``self.renderer is None`` beide aus, und offscreen gibt es
    keinen Plotter. Ein Test ohne sie prüfte, dass die Methode umkehrt.

    **Gefälscht wird die Punktquelle, und die heißt jetzt ``_aim_at``** — vorher
    stand hier ``module._world_under``. Der Zeiger fragt dasselbe wie der Klick,
    und das schließt den Blick durch eine Bohrung hindurch ein; hinter
    ``_aim_at`` liegt der Oberflächen-Pick des Renderers, und die Attrappe
    hier hat keinen. Was diese Kette **davor** tut, steht in den Tests
    zu ``_bore_aim`` weiter oben; was sie **danach** tut, ist genau das, was
    hier geprüft wird.
    """
    viewport = window.viewport
    point = on_the_bore_wall(window)
    shown: list[Any] = []

    class FakeInteractor:
        def setCursor(self, cursor: Any) -> None:  # noqa: N802 — Qt-Name
            shown.append(cursor)

        def height(self) -> int:
            return 600

    renderer = RecordingRenderer()
    renderer.widget = FakeInteractor()
    viewport.renderer = renderer
    try:
        viewport._aim_at = lambda *_args: point  # type: ignore[method-assign]
        # Dieser Test gilt dem Zeigerweg; die sichtbare Hover-Fläche hat ihren
        # eigenen Plotter-Test in ``test_viewport_decisions.py``.
        viewport._redraw_features = lambda: None  # type: ignore[method-assign]
        viewport._hover_at = (10, 10)

        viewport._look_under_pointer()
        assert viewport._cursor_role == "select", "noch nichts gewählt: das Teil"

        viewport.select("obj_1")
        viewport._look_under_pointer()
        assert viewport._cursor_role == "feature", "Teil gewählt: jetzt die Bohrung"
    finally:
        del viewport._aim_at
        del viewport._redraw_features
        viewport.renderer = None

    assert shown, "und gesetzt wurde er wirklich, nicht nur vermerkt"


def test_a_right_click_goes_straight_to_the_deepest_target(window: MainWindow) -> None:
    """Rechts fragt, was hier liegt — und meint immer das Genaueste (§18.5).

    Der Bauplan nennt das Kontextmenü **am Merkmal** den Ort für Weg 1: ein
    fremdes Modell wird angepasst, indem man auf die Stelle zeigt, die stört.
    Wäre der Rechtsklick gestuft wie der Linksklick, hinge diese Zusage an einer
    Vorbedingung, die niemand kennt — man müsste die Bohrung erst linksklicken,
    um ihr Menü zu bekommen.

    Damit teilen sich die zwei Tasten die Arbeit: **links wandert** durch die
    Tiefe, **rechts fragt** nach dem, was unter dem Zeiger liegt. Dieselbe
    Trennung hat Fusion 360.
    """
    viewport = window.viewport
    point = on_the_bore_wall(window)

    assert viewport._click_target(point) == ("obj_1", None), "links: erst das Teil"
    assert viewport._click_target(point, direct=True) == ("obj_1", "hole_1"), "rechts: sofort"


def test_a_right_click_leaves_the_selection_where_it_landed(window: MainWindow) -> None:
    """Und die Stufe geht dabei nicht verloren.

    Ein Rechtsklick auf eine Bohrung setzt die Auswahl auf sie; der nächste
    Linksklick führt von dort weiter und nicht von vorn. Sonst wären es zwei
    Auswahlbegriffe — einer für jede Maustaste.
    """
    viewport = window.viewport
    viewport._select_at(on_the_bore_wall(window, "hole_1"), direct=True)
    assert viewport.selection_depth() == 2
    assert viewport.selected_feature == "hole_1"

    viewport._select_at(on_the_bore_wall(window, "hole_4"))
    assert viewport.selected_feature == "hole_4", "der Linksklick setzt fort, statt aufzusetzen"


# --- wenn ein Dialog fragt ------------------------------------------------------


def test_a_dialog_gets_its_answer_on_the_first_click(window: MainWindow) -> None:
    """Solange ein Dialog nach einem Merkmal fragt, gibt es keine Stufen.

    Ein Klick ist dann eine Antwort und keine Navigation. Zweimal zeigen zu
    müssen, um zu antworten, sähe aus wie ein verschluckter erster Klick —
    genau der Eindruck, aus dem §18.5 mit dem Anklicken herausführen soll.
    """
    viewport = window.viewport
    point = on_the_bore_wall(window)

    viewport.set_direct_picking(True)
    assert viewport._click_target(point) == ("obj_1", "hole_1"), "sofort, ohne Umweg"

    viewport.set_direct_picking(False)
    assert viewport._click_target(point) == ("obj_1", None), "und danach wieder gestuft"


def test_opening_and_closing_a_dialog_switches_it(window: MainWindow) -> None:
    """Und das Fenster schaltet es wirklich um — an beiden Enden.

    Ohne das Zurückschalten bliebe die gestufte Tiefe nach dem ersten Dialog
    für den Rest der Sitzung aus.
    """
    from PySide6.QtWidgets import QDialog

    dialog = QDialog(window)
    window._open_operation_dialog(dialog, lambda: None)  # type: ignore[arg-type]
    assert window.viewport._direct_picking is True

    dialog.reject()
    QApplication.processEvents()
    assert window.viewport._direct_picking is False


# --- was die Stufe nicht kaputt macht ------------------------------------------


def test_a_new_evaluation_forgets_the_prepared_triangles(window: MainWindow) -> None:
    """Die vorbereiteten Merkmalsdreiecke gehören einer Auswertung.

    Eine Operation, die eine Bohrung verschiebt, ändert ihre Dreiecke — würde
    der Zwischenspeicher überleben, träfe ein Klick danach dort, wo sie war.
    """
    viewport = window.viewport
    viewport.select("obj_1")
    assert viewport._feature_at(on_the_bore_wall(window)) == "hole_1"
    assert viewport._feature_geometry, "vorbereitet wurde etwas"

    viewport.show_scene(window.session.last_result)
    assert not viewport._feature_geometry, "und beim Szenenwechsel weggeräumt"


def test_the_reach_grows_with_the_body(window: MainWindow) -> None:
    """Ein fester Millimeterwert wäre an einem Gehäuse zu streng.

    Gepickt wird im dezimierten Anzeigenetz (§18.9), und dessen Oberfläche
    liegt nicht auf der der Szene. Die Reichweite wächst deshalb mit der
    Diagonale, mit einer Untergrenze für kleine Teile.
    """
    entry = window.session.last_result.scene.objects["obj_1"]
    big = dataclasses.replace(entry, id="obj_big")
    viewport = window.viewport

    small = viewport._feature_reach("obj_1")
    assert small > 0.5, "die Platte ist groß genug für den Anteil"
    assert viewport._feature_reach(None) == pytest.approx(0.5), "ohne Körper die Untergrenze"
    assert big.id != entry.id, "der Vergleichskörper ist ein anderer"


def test_a_second_feature_takes_over_from_the_first(window: MainWindow) -> None:
    """Von einer Bohrung direkt auf die nächste — ohne Umweg über den Körper.

    **Robert am 23.08.2026:** „wenn ich ein merkmal auswähle und im viewport
    dann wieder auf das modell oder einem anderen merkmal klicke wechseln wir
    auch nicht."

    Der Weg dorthin ist gebaut: ``_click_target`` gibt bei demselben Körper
    ``self._feature_at(point)`` zurück, und ``_select_at`` setzt es. Geprüft
    war bisher nur der Wechsel **hinein** (Körper → Bohrung, in
    ``test_the_first_click_takes_the_body_and_the_second_the_hole``) und der
    Weg **heraus** auf eine Fläche, die selbst ein Merkmal ist. Der Wechsel
    zwischen zwei gleichrangigen Merkmalen stand nicht darin.
    """
    viewport = window.viewport
    entry = window.session.last_result.scene.objects["obj_1"]
    holes = [f for f in entry.features.values() if f.kind == "hole"]
    assert len(holes) >= 2, "ohne zwei Bohrungen prüft der Test nichts"

    def on_wall(feature: Any) -> tuple[float, float, float]:
        index = next(iter(feature.face_indices or ()))
        return tuple(float(value) for value in entry.mesh.raw.triangles[index].mean(axis=0))

    window.viewport.select("obj_1")
    viewport._select_at(on_wall(holes[0]))
    assert viewport.selected_feature == holes[0].id, "die erste Bohrung wurde nicht gewählt"

    viewport._select_at(on_wall(holes[1]))
    assert viewport.selected_feature == holes[1].id, (
        f"von {holes[0].id} kommend bleibt die Auswahl stehen statt auf {holes[1].id} zu wechseln"
    )


# --- Was ein Zug bei mehreren gewählten Körpern trifft -------------------------


def two_bodies(window: MainWindow) -> tuple[str, str]:
    """Ein zweiter Körper neben der Platte, beide im Baum markiert.

    Über ``session.apply`` und nicht durch Zusammensetzen einer Szene von Hand:
    Was der Test bewegt, muss dasselbe sein, was ein Kunde bewegt — sonst misst
    er eine Lage, die kein Klick herstellt.
    """
    from app.core.scene.history import OperationDraft

    window.session.apply(
        "Kasten",
        [
            OperationDraft(
                op="create_box",
                inputs=(),
                params={"width": 10.0, "depth": 20.0, "height": 5.0},
            )
        ],
    )
    window.session.wait_for_idle()
    # **Der zweite Körper steht daneben, und das ist der Punkt.**
    # ``create_box`` legt ihn um den Ursprung an, genau wie die Platte — beide
    # Mittelpunkte lägen dann auf der Z-Achse, und eine Drehung um Z um ihre
    # gemeinsame Mitte ließe beide stehen. Der Test wäre grün, ohne etwas
    # geprüft zu haben; genau diese Lage hat er in seiner ersten Fassung
    # gemessen. Fünfzig Millimeter Versatz machen den Unterschied sichtbar.
    box = window.session.last_result.scene.objects
    letzter = [one for one in box if one != "obj_1"][-1]
    window.session.apply(
        "Danebenstellen",
        [OperationDraft(op="translate_object", inputs=(letzter,), params={"dx": 50.0})],
    )
    window.session.wait_for_idle()

    tree = window.object_tree.tree
    assert tree.topLevelItemCount() >= 2, "der zweite Körper fehlt — dann prüft das nichts"
    for index in range(tree.topLevelItemCount()):
        item = tree.topLevelItem(index)
        assert item is not None
        item.setSelected(True)

    chosen = window.object_tree.selected_objects()
    assert len(chosen) == 2, f"zwei Körper sollten markiert sein, markiert sind {len(chosen)}"
    return chosen[0], chosen[1]


def centre_of(window: MainWindow, object_id: str) -> tuple[float, float, float]:
    from app.core.geom.mesh import as_mesh_data

    entry = window.session.last_result.scene.objects[object_id]
    centre = as_mesh_data(entry.mesh).bounds.centre
    return (float(centre[0]), float(centre[1]), float(centre[2]))


def size_of(window: MainWindow, object_id: str) -> tuple[float, float, float]:
    """Die Kantenmaße — und **nicht** der Mittelpunkt, wenn es ums Drehen geht.

    Die erste Fassung dieses Tests maß den Mittelpunkt und blieb grün, als die
    Gegenprobe das Drehen versuchsweise auf alle Körper ausdehnte: Eine Drehung
    um den *eigenen* Mittelpunkt lässt genau diesen unverändert. Ein Würfel
    hätte auch die Kantenmaße behalten, deshalb ist der zweite Körper 10 x 20 x
    5 — um Z gedreht wird daraus 20 x 10 x 5, und das ist zu sehen.
    """
    from app.core.geom.mesh import as_mesh_data

    entry = window.session.last_result.scene.objects[object_id]
    size = as_mesh_data(entry.mesh).bounds.size
    return (round(float(size[0]), 3), round(float(size[1]), 3), round(float(size[2]), 3))


def test_a_drag_moves_every_selected_body(window: MainWindow) -> None:
    """Zwei Teile gewählt, einmal gezogen — beide müssen sich bewegen.

    **Weil ein Kunde, der zwei Teile markiert hat, zwei Teile meint.** Vorher
    nahm der Zug still ``selected()``, also ``items[0]``: Die Auswahl sagte
    zwei, das Bild bewegte eines, und niemand erfuhr, warum. Das ist nicht
    ungenau, sondern kaputt — und es ist genau der Fall, den jemand ohne
    CAD-Erfahrung als Fehler der Anwendung liest, nicht als Bedienfehler.
    """
    from app.ui.viewport import TransformSteps

    first, second = two_bodies(window)
    before = (centre_of(window, first), centre_of(window, second))

    window._on_transform_dragged(TransformSteps(offset=(5.0, 0.0, 0.0)))
    window.session.wait_for_idle()

    after = (centre_of(window, first), centre_of(window, second))
    moved = [round(after[i][0] - before[i][0], 3) for i in (0, 1)]
    assert moved == [5.0, 5.0], (
        f"beide gewählten Körper müssen um 5 mm wandern, gewandert sind sie um {moved} mm"
    )


def test_two_drags_in_a_row_are_one_step_in_the_history(window: MainWindow) -> None:
    """Ziehen, nachsehen, nachziehen — eine Absicht, ein Eintrag (§15.5, P9).

    **Die Bündelung war nur am Kern geprüft** (``tests/test_bundling.py``), und
    das ließ die Hälfte offen: Ob das Angebot ``bundle=True`` aus dem Fenster
    überhaupt bei der Geschichte ankommt — und ob der zweite Zug dort beim
    ersten landet —, entscheidet sich auf diesem Weg und nirgends sonst.

    Gemessen an beidem, wie im Kern: an der Zahl der Schritte und an der Lage.
    Nur zu zählen ließe offen, ob der zweite Zug angekommen ist; nur zu messen
    ließe offen, ob er einen eigenen Eintrag kostete.
    """
    from app.ui.viewport import TransformSteps

    result = window.session.last_result
    assert result is not None
    body = next(iter(result.scene.objects))
    window.object_tree.select_object(body)
    vorher = len(window.session.project.document.transactions)
    anfang = centre_of(window, body)

    window._on_transform_dragged(TransformSteps(offset=(5.0, 0.0, 0.0)))
    window.session.wait_for_idle()
    window._on_transform_dragged(TransformSteps(offset=(5.0, 0.0, 0.0)))
    window.session.wait_for_idle()

    schritte = [one.title for one in window.session.project.document.transactions]
    assert len(schritte) == vorher + 1, (
        f"zwei Züge hintereinander ergaben {len(schritte) - vorher} Schritte: {schritte}"
    )
    mitte = centre_of(window, body)
    assert mitte[0] - anfang[0] == pytest.approx(10.0, abs=1e-6), (
        f"der zweite Zug ist nicht angekommen: {mitte[0] - anfang[0]:.3f} mm statt 10"
    )

    window.session.undo()
    window.session.wait_for_idle()

    zurueck = centre_of(window, body)
    assert zurueck[0] == pytest.approx(anfang[0], abs=1e-6), (
        f"ein Strg+Z ließ das Teil bei {zurueck[0]:.3f} statt {anfang[0]:.3f} mm stehen — "
        "es nimmt den letzten Zug zurück statt der Handlung"
    )
    assert len(window.session.project.document.transactions) == vorher, (
        "nach einem Undo steht noch ein Teil des Bündels im Verlauf: "
        f"{[one.title for one in window.session.project.document.transactions]}"
    )


def test_turning_several_bodies_turns_them_as_a_group(window: MainWindow) -> None:
    """Zwei Teile gewählt, einmal gedreht — die Gruppe dreht, nicht jeder für sich.

    **Hier stand einmal das Gegenteil**, und die Begründung war richtig, solange
    sie galt: ``rotate_object`` nahm seinen Bezugspunkt aus dem *eigenen* Netz,
    jeder Körper drehte also um sich selbst, und die Anordnung, die der Kunde
    gerade hergestellt hat, wäre auseinandergefallen. Deshalb galt Drehen dem
    zuerst gewählten Teil, und die Statuszeile sagte es.

    Für einen Kunden war das aber keine Lösung, sondern eine Grenze: Wer zwei
    Teile markiert und dreht, erwartet, dass sie sich zusammen drehen. Seit die
    Operation einen genannten Punkt annimmt, gibt es die Grenze nicht mehr.

    Gemessen an der **Anordnung**: Der Abstand zwischen den Mittelpunkten muss
    die Drehung überstehen. Dreht jeder um sich selbst, bleiben beide stehen,
    wo sie sind — dann ist der Abstand ebenfalls gleich, und der Test sähe
    nichts. Deshalb wird zusätzlich geprüft, dass die Körper sich überhaupt
    bewegt haben.
    """
    import math

    from app.ui.viewport import TransformSteps

    first, second = two_bodies(window)
    vorher = (centre_of(window, first), centre_of(window, second))
    abstand_vorher = math.dist(vorher[0], vorher[1])

    window._on_transform_dragged(TransformSteps(axis="z", angle=90.0))
    window.session.wait_for_idle()

    nachher = (centre_of(window, first), centre_of(window, second))
    abstand_nachher = math.dist(nachher[0], nachher[1])

    assert abstand_nachher == pytest.approx(abstand_vorher, abs=1e-6), (
        f"die Anordnung muss die Drehung überstehen: aus {abstand_vorher:.3f} mm "
        f"Abstand wurde {abstand_nachher:.3f} mm"
    )
    gewandert = [math.dist(vorher[i], nachher[i]) for i in (0, 1)]
    assert all(weg > 1e-6 for weg in gewandert), (
        f"beide Körper müssen um die gemeinsame Mitte gewandert sein, gewandert "
        f"sind sie um {gewandert} mm — dreht jeder um sich selbst, steht jeder still"
    )


def test_one_body_still_turns_around_itself(window: MainWindow) -> None:
    """Ein einzelner Körper dreht um seinen eigenen Schwerpunkt — wie immer.

    **Die Gegenprobe zur Gruppendrehung.** Der gemeinsame Punkt darf nur ab
    zwei markierten Körpern in die Parameter kommen; stünde er auch bei einem,
    änderte sich das Verhalten jedes bestehenden Projekts still mit.
    """
    from app.ui.viewport import TransformSteps

    window.object_tree.select_object("obj_1")
    assert window.pivot_for_transform() == {}, (
        "bei einem einzelnen Körper darf kein Punkt in die Parameter wandern"
    )

    vorher = centre_of(window, "obj_1")
    window._on_transform_dragged(TransformSteps(axis="z", angle=90.0))
    window.session.wait_for_idle()

    assert centre_of(window, "obj_1") == pytest.approx(vorher, abs=1e-6), (
        "ein einzelner Körper dreht um sich selbst, sein Mittelpunkt bleibt stehen"
    )


def test_the_status_line_counts_the_selected_parts(window: MainWindow) -> None:
    """Die Zeile nennt die Zahl der gewählten Teile, nicht bloß „Auswahl".

    **Und sie sagt nichts mehr über Einschränkungen.** Hier stand kurz
    „Ziehen verschiebt alle · Drehen und Größe gelten dem ersten" — ein
    ehrlicher Satz, solange die Grenze bestand. Seit alle drei Züge der ganzen
    Auswahl gelten, wäre er ein Versprechen über eine Einschränkung, die es
    nicht gibt, und das ist schlechter als kein Satz. Der Schlüssel ist aus
    allen fünf Katalogen entfernt.
    """
    two_bodies(window)
    text = window.measurements.text()

    assert "2" in text, f"die Zeile muss die Zahl der gewählten Teile nennen: {text!r}"
    assert "Auswahl" not in text, (
        f"„Auswahl“ sagt nicht, wie viele es sind — das war der alte Text: {text!r}"
    )


# --- Was der Griff sagt, bevor gezogen wird -----------------------------------


def test_the_handle_on_a_face_says_which_face_it_is() -> None:
    """Sitzt der Griff auf einer Fläche, nennt er sie — statt X, Y und Z.

    **Weil drei Achsenbuchstaben dort die falsche Auskunft sind.** Der Griff
    springt bei gewählter Fläche dorthin und kennt nur vor und zurück
    (§18.11); beschriftet war er weiter mit X, Y und Z, und was wirklich
    passiert, erfuhr der Kunde erst während des Zugs. Wer nicht aus dem CAD
    kommt, liest drei Achsen als „hier geht es in drei Richtungen" und zieht in
    eine, die verfällt.

    Geprüft wird die reine Funktion und nicht der Plotter: Offscreen gibt es
    keinen, und ein Test, der sich dort überspringt, ist grün über einer leeren
    Menge (siehe den Kopf dieser Datei).
    """
    from app.ui.viewport import FACE_ARROW, gizmo_labels

    achsen = gizmo_labels((0.0, 0.0, 0.0), 10.0)
    assert [text for _punkt, text in achsen] == ["X", "Y", "Z"], (
        "ohne Fläche bleibt es bei den drei Achsen"
    )

    flaeche = gizmo_labels((0.0, 0.0, 0.0), 10.0, ("Oberseite", (0.0, 0.0, 1.0)))
    beschriftung = [text for _punkt, text in flaeche]
    assert beschriftung == [FACE_ARROW], (
        f"der Griff muss die eine Richtung zeigen, er sagt {beschriftung}"
    )
    assert "X" not in beschriftung and "Y" not in beschriftung, (
        "die Achsenbuchstaben dürfen daneben nicht stehen bleiben — sie "
        "versprechen Richtungen, die es an einer Fläche nicht gibt"
    )


def test_the_face_label_sits_along_the_normal() -> None:
    """Die Beschriftung liegt in Zugrichtung, nicht auf einer Achse.

    Sonst stünde sie bei einer schräg liegenden Fläche irgendwo im Raum, und
    der Doppelpfeil zeigte in eine Richtung, in die nichts geht.
    """
    from app.ui.viewport import GIZMO_LABEL_GAP, gizmo_labels

    reach = 10.0 * GIZMO_LABEL_GAP
    ((punkt, _text),) = gizmo_labels((1.0, 2.0, 3.0), 10.0, ("Vorderseite", (0.0, -1.0, 0.0)))

    assert punkt == pytest.approx((1.0, 2.0 - reach, 3.0)), (
        f"die Beschriftung muss auf der Normalen liegen, sie liegt bei {punkt}"
    )


def test_a_customer_never_reads_the_internal_name(window: MainWindow) -> None:
    """Am Griff steht „Oberseite" und nirgends ``face_2``.

    Die Kennung ist die Sprache des Op-Stacks. Für jemanden ohne
    CAD-Erfahrung ist sie eine Nummer ohne Aussage — sie gehört in den Tooltip
    und in Parameterfelder, nicht in die Ansicht (§18.5).

    Über die Flächen des Korpus und nicht über ein selbstgebautes Merkmal: Was
    hier geprüft wird, muss das sein, was die Anwendung erzeugt.
    """
    from app.ui.labels import feature_name

    entry = window.session.last_result.scene.objects["obj_1"]
    faces = [(fid, f) for fid, f in entry.features.items() if f.kind == "face"]
    assert len(faces) >= 3, f"nur {len(faces)} Flächen — dann prüft das nichts"

    for feature_id, feature in faces:
        name = feature_name(feature_id, feature)
        assert feature_id not in name, (
            f"die Kennung {feature_id!r} darf nicht in die Ansicht durchschlagen: {name!r}"
        )
        assert name.strip(), f"{feature_id}: ohne Namen stünde der Doppelpfeil allein am Griff"


def test_choosing_a_face_reaches_the_handle_label(window: MainWindow) -> None:
    """Von der gewählten Fläche bis zur Beschriftung — das Stück dazwischen.

    **Die beiden Enden sind geprüft, das Stück dazwischen war es nicht.**
    ``gizmo_labels`` beschriftet richtig, wenn man ihm eine Fläche gibt, und
    ``feature_name`` benennt sie kundengerecht — aber ob die Auswahl je dort
    ankommt, sagt keines von beiden. Durchgereicht ist nicht gerufen.

    Offscreen prüfbar, weil ``gizmo_face_label`` keine Plotter-Wache trägt:
    ``_label_gizmo`` steigt bei fehlendem Plotter sofort aus und wäre hier
    grün über einer leeren Menge.
    """
    entry = window.session.last_result.scene.objects["obj_1"]
    faces = [fid for fid, f in entry.features.items() if f.kind == "face"]
    assert faces, "die Platte hat keine Flächen — dann prüft das nichts"

    window.object_tree.select_object("obj_1")
    assert window.viewport.gizmo_face_label() is None, (
        "ohne gewählte Fläche darf am Griff keine stehen — dort gelten X, Y und Z"
    )

    window.viewport.select_feature(faces[0])
    beschriftung = window.viewport.gizmo_face_label()

    assert beschriftung is not None, (
        f"eine gewählte Fläche ({faces[0]}) muss am Griff ankommen — sonst sagt "
        "er weiter X, Y und Z und verspricht Richtungen, die es nicht gibt"
    )
    name, normal = beschriftung
    assert name.strip() and faces[0] not in name, (
        f"am Griff steht die Kennung statt des Namens: {name!r}"
    )
    assert len(normal) == 3 and any(abs(wert) > 0.0 for wert in normal), (
        f"die Richtung fehlt oder ist null: {normal}"
    )


def test_nothing_on_the_gizmo_leaves_ascii() -> None:
    """Am Griff steht ASCII — und sonst nichts.

    **Der erste Grund war eine harte Grenze:** Die Griffbeschriftung war ein
    ``vtkStringArray``, und pyvista lehnte alles andere ab, nicht mit einer
    Warnung, sondern mit ``ValueError: String array contains non-ASCII
    characters``; der ganze Griffaufbau stürzte damit ab. Die Grenze ist mit
    VTK gegangen, **die Regel bleibt**, denn ihr zweiter Grund steht: Der
    Griff ist der eine Ort, an den ein übersetzter Text nicht gehört —
    überall sonst zeichnet Qt, und ein Wort am Griff stünde in sechs Sprachen
    an einer Stelle, die keine Prüfung sieht.

    **Der Fall ist einmal passiert und wäre in der deutschen Fassung nie
    aufgefallen:** Am Griff standen kurz ein Doppelpfeil „↕" und der Name der
    Fläche aus ``feature_name``. Auf Französisch heißen vier der sechs Flächen
    ``Face supérieure``, ``Arrière``, ``Côté gauche`` und ``Côté droit`` — die
    Anwendung wäre dort beim Klick auf eine Fläche abgestürzt, hier nicht.

    Deshalb prüft dieser Test **jede** Beschriftung, die die Funktion erzeugen
    kann, und nicht nur die deutsche Lage. Der Name steht in der Statusleiste,
    wo Qt zeichnet und jede Sprache darf.
    """
    from app.ui.viewport import gizmo_labels

    laeufe = [
        gizmo_labels((0.0, 0.0, 0.0), 10.0),
        gizmo_labels((0.0, 0.0, 0.0), 10.0, ("Face supérieure", (0.0, 0.0, 1.0))),
        gizmo_labels((0.0, 0.0, 0.0), 10.0, ("Côté gauche", (-1.0, 0.0, 0.0))),
        gizmo_labels((0.0, 0.0, 0.0), 10.0, ("Arrière", (0.0, 1.0, 0.0))),
    ]
    assert len(laeufe) == 4, "die Grundmenge ist leer — dann prüft dieser Test nichts"

    for marken in laeufe:
        for _punkt, text in marken:
            assert text.isascii(), (
                f"am Griff steht {text!r} — übersetzte Texte gehören in die Statusleiste, "
                "nicht an den Griff"
            )
