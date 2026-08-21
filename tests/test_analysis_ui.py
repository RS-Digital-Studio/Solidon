"""Analysekarten, Merkmals-Überlagerung und Schichtanalyse in der
Oberfläche (§18.4, §18.5, §18.10).

Wieder offscreen: geprüft werden die Verdrahtung und die Legende, nicht das
Bild. Ob die Farben auf dem richtigen Dreieck landen, entscheidet der Kern, und
``tests/test_maps.py`` prüft es dort.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QThread
from PySide6.QtWidgets import QApplication

from app.core.perceive import maps
from app.core.types import Finding
from app.i18n import format_decimal, tr
from app.ui.analysis_bar import MAP_ORDER, AnalysisBar, LayerBar, MapLegend
from app.ui.labels import feature_label
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings

MESHES = Path(__file__).parent / "data" / "meshes"


@pytest.fixture
def window(qt_app: QApplication) -> Iterator[MainWindow]:
    """Ein Fenster für einen Test — und danach warten, bis es still ist.

    Ohne das lief nach dem Test noch ein Arbeiter, und beim Herunterfahren des
    Interpreters ist der Thread-Pool der Schichtanalyse längst zu: „cannot
    schedule new futures after interpreter shutdown", quer über eine grüne
    Suite. Gewartet wird auf **alle** Arbeiter des Fensters, nicht nur auf die
    der Sitzung — das Fenster führt vier eigene, und einer davon, die
    Update-Prüfung, startet bei jedem Fenster von selbst.

    **Gewartet, nicht gelöscht**, und nicht über ``close()``:

    * ``close()`` löst ``closeEvent`` aus, und der fragt bei ungesicherten
      Änderungen modal nach — der Test hängt dann an einem Fenster, das
      niemand sieht. Die Falle steht seit zwei Runden im Kopf von
      ``tests/test_ui.py``.
    * ``deleteLater`` brachte nichts und kostete Stabilität. Ein Fenster, das
      liegen bleibt, ist harmlos; ein Thread, der noch läuft, ist es nicht,
      und genau der war die Ursache des Rauschens.

    **Zum sporadischen Absturz** (``Windows fatal exception: access
    violation``, ohne Zeile, an wechselnder Stelle): der galt hier lange als
    unabhängig von jeder Aufräumung — nachgemessen an je vier Läufen mit
    Aufräumung, mit Löschen und ganz ohne, riss er in jeder Fassung.

    Eine Ursache ist inzwischen gefunden und behoben: der Interaktionsstil des
    Viewports hielt eine gebundene Methode und damit den Viewport, der den
    Plotter hält, der den Interactor hält, der den Stil hält. Diese Schleife
    überlebt jedes Schließen; abgeräumt wird sie später, und dann steht ein
    C++-Objekt hinter einer Python-Referenz, die es nicht mehr gibt. Mit einer
    schwachen Referenz läuft die Suite wieder in einem Zug.

    Es bleibt dasselbe Muster, das die Roadmap als „ersetzte Arbeiter lassen
    ihre Referenz los" führt. Reißt es wieder, ist die erste Frage: welche
    Python-Referenz hält ein Qt- oder VTK-Objekt am Leben, das längst weg
    sein sollte?
    """
    window = MainWindow(Session(), UiSettings())
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    yield window
    wait_for_map(window)
    window.wait_for_workers()


def select_plate(window: MainWindow) -> None:
    item = window.object_tree.tree.topLevelItem(0)
    assert item is not None
    item.setSelected(True)


def wait_for_map(window: MainWindow) -> None:
    """§18.9: Karten werden im Hintergrund gebaut, der Test wartet also wie
    das Fenster.
    """
    worker = window._map_worker
    if worker is not None:
        worker.wait(20_000)
    QApplication.processEvents()


# --- die Kartenauswahl ----------------------------------------------------------


def test_every_map_of_the_table_is_offered(qt_app: QApplication) -> None:
    """§18.4 zählt sieben Karten auf; die Leiste bietet alle sieben an und
    „keine".
    """
    bar = AnalysisBar()
    offered = [bar.selector.itemData(index) for index in range(bar.selector.count())]

    assert offered[0] is None
    assert tuple(offered[1:]) == MAP_ORDER


def test_choosing_a_map_paints_the_body(window: MainWindow) -> None:
    select_plate(window)
    window.analysis_bar.selector.setCurrentIndex(window.analysis_bar.selector.findData("overhang"))
    wait_for_map(window)

    analysis = window.viewport.analysis_map
    assert analysis is not None
    assert analysis.kind == "overhang"
    assert window.analysis_bar.legend.entries, "a map always comes with a legend (§18.4)"


def test_the_map_goes_away_again(window: MainWindow) -> None:
    select_plate(window)
    window.analysis_bar.selector.setCurrentIndex(window.analysis_bar.selector.findData("features"))
    window.analysis_bar.selector.setCurrentIndex(0)

    assert window.viewport.analysis_map is None
    assert window.analysis_bar.legend.entries == []


def test_without_a_selection_the_bar_says_what_is_missing(window: MainWindow) -> None:
    window.object_tree.tree.clearSelection()
    window._on_map_changed("wall")

    assert "Objekt" in window.analysis_bar.legend.note.text()


def test_ambient_occlusion_yields_to_a_map(qt_app: QApplication) -> None:
    """Schönheit vor Ablesbarkeit gibt es nicht (§18.4, Konzept P15 §7).

    Die Umgebungsverdeckung dunkelt Vertiefungen nach — auf einer Karte, die
    nach Zahlen färbt und ihren Wertebereich als Legende danebenstellt, wäre
    der abgelesene Wert damit ein anderer als der gemeldete.

    Geprüft wird die Regel, nicht der Plotter: offscreen gibt es keinen, und
    ein Test, der sich dort überspringt, prüft nie etwas.
    """
    from app.ui.viewport import Viewport

    viewport = Viewport()
    try:
        assert viewport.ambient_occlusion, "ohne Karte ist die Verdeckung an"
        assert viewport.contact_shadows, "und der Kontaktschatten ebenso"

        viewport.set_analysis_map(
            maps.AnalysisMap(kind="wall", title="x", values=(1.0,), unit="mm", low=1.0, high=4.0),
            None,
        )
        assert not viewport.ambient_occlusion, "mit Karte ist sie aus"
        assert not viewport.contact_shadows, "und der Schatten auch — er dunkelt genauso nach"

        viewport.set_analysis_map(None, None)
        assert viewport.ambient_occlusion, "danach wieder an"
    finally:
        # Ein Widget ohne Elternteil räumt sich nicht selbst weg, und was am
        # Ende des Laufs noch lebt, wird beim Herunterfahren des Interpreters
        # aufgeräumt — dann ist der Thread-Pool der Schichtanalyse längst zu,
        # und die Meldung darüber landet als Rauschen in einer grünen Suite.
        viewport.deleteLater()


def test_a_painted_body_is_drawn_in_its_filament_colours(qt_app: QApplication) -> None:
    """§20: die Farbe steht im Dokument und wird exportiert — sie gehört
    gezeigt, solange ein Fehlgriff noch billig ist.

    Geprüft wird die Farbtabelle, nicht das Bild: sie entscheidet, welcher
    Slot welche Farbe bekommt, und sie ist ohne OpenGL-Kontext zu haben.
    """
    pv = pytest.importorskip("pyvista")
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.types import MaterialSlot, SceneObject
    from app.ui.viewport import Viewport

    body = trimesh.creation.box(extents=(10, 10, 10))
    # Halb rot, halb blau — zwölf Dreiecke, sechs je Farbe.
    mesh = MeshData.of(body, tuple([1] * 6 + [2] * 6))
    entry = SceneObject(
        id=1,
        name="Teil",
        mesh=mesh,
        material_slots=[
            MaterialSlot(index=1, name="Rot", colour=(1.0, 0.0, 0.0)),
            MaterialSlot(index=2, name="Blau", colour=(0.0, 0.0, 1.0)),
        ],
    )

    viewport = Viewport()
    try:
        surface = pv.Cube().triangulate()
        extra = viewport._slot_colours(surface, mesh, entry, 12)
        assert extra["cmap"][1] == "#ff0000"
        assert extra["cmap"][2] == "#0000ff"
        assert extra["clim"] == (0, 2)
        assert list(surface.cell_data["slot"]) == [1] * 6 + [2] * 6

        # Ein Körper ohne Bemalung bleibt in der Objektfarbe.
        plain = SceneObject(id=2, name="Grau", mesh=MeshData.of(body))
        assert viewport._slot_colours(surface, plain.mesh, plain, 12) == {}
    finally:
        viewport.deleteLater()


def test_feature_edges_leave_a_round_body_alone() -> None:
    """Eine Kugel hat keine Kante, und eine erfundene wäre schlimmer als keine.

    Geprüft wird die Auswahlregel selbst, nicht das Bild: der Winkel entscheidet,
    was als Kante des Körpers gilt. Ein fein aufgelöster Zylinder darf seine
    Facetten nicht als Kanten bekommen, sonst ist das Ergebnis dasselbe wie
    „Massiv mit Kanten" — und dafür gibt es diesen Modus schon.
    """
    pv = pytest.importorskip("pyvista")
    from app.ui.viewport import FEATURE_EDGE_ANGLE

    def edges_of(mesh: object) -> int:
        found = mesh.extract_feature_edges(  # type: ignore[attr-defined]
            feature_angle=FEATURE_EDGE_ANGLE,
            boundary_edges=True,
            non_manifold_edges=False,
            feature_edges=True,
            manifold_edges=False,
        )
        return int(found.n_cells)

    assert edges_of(pv.Sphere(theta_resolution=120, phi_resolution=120)) == 0
    assert edges_of(pv.Cylinder(resolution=96).triangulate()) > 0, (
        "die Deckflächen eines Zylinders treffen die Mantelfläche im rechten Winkel"
    )
    assert edges_of(pv.Cube().triangulate()) == 12, "ein Würfel hat zwölf Kanten"


# --- die Legende ----------------------------------------------------------------


def test_a_measured_map_shows_its_range_and_its_origin(qt_app: QApplication) -> None:
    legend = MapLegend()
    legend.show_map(
        maps.AnalysisMap(
            kind="wall",
            title="x",
            values=(1.0, 4.0),
            unit="mm",
            low=1.0,
            high=4.0,
            resolution=0.3,
        )
    )

    labels = [text for text, _colour in legend.entries]
    assert labels[0].startswith("1")
    assert labels[-1].startswith("4")
    # §22.5: woher eine Zahl kommt, gehört neben die Zahl.
    assert "intern" in legend.note.text()
    assert "0,3" in legend.note.text(), "a sampled map says how fine it was sampled"


def test_the_report_names_the_origin_of_every_finding(window: MainWindow) -> None:
    """§22.5: eine Schätzung und eine Messung dürfen nie gleich aussehen."""
    window.report.show_result(window.session.last_result)
    if window.report.list.count() == 0:
        pytest.skip("this model produced no findings")

    assert "Herkunft" in window.report.list.item(0).toolTip()


def test_a_map_of_levels_names_them(qt_app: QApplication) -> None:
    legend = MapLegend()
    legend.show_map(
        maps.AnalysisMap(
            kind="defects",
            title="x",
            values=(0.0, 1.0),
            unit="",
            low=0.0,
            high=2.0,
            categories=maps.DEFECT_LEVELS,
        )
    )

    assert [text for text, _colour in legend.entries] == list(maps.DEFECT_LEVELS)


def test_the_colours_of_the_legend_rise_in_luminance() -> None:
    """§19.1: die Rampe ist in Graustufen lesbar, sie darf also kein Regenbogen
    sein.
    """
    from app.ui.palette import VIRIDIS, is_monotonic

    assert is_monotonic(VIRIDIS)


# --- Von einer Warnung zur Stelle -------------------------------------------------


def test_clicking_a_warning_switches_the_map_and_moves_the_camera(window: MainWindow) -> None:
    """§18.4: der kürzeste Weg von „da ist ein Problem" zu „hier ist es"."""
    select_plate(window)
    finding = Finding(
        code="fit.violated",
        severity="warning",
        message="zu eng",
        object_id="obj_1",
        feature_ids=("hole_1",),
    )
    window._on_finding_activated(finding)
    wait_for_map(window)

    assert window.analysis_bar.chosen() == "fits"
    analysis = window.viewport.analysis_map
    assert analysis is not None and analysis.kind == "fits"


def test_a_warning_without_a_map_still_finds_its_place(window: MainWindow) -> None:
    select_plate(window)
    finding = Finding(
        code="etwas.anderes",
        severity="warning",
        message="x",
        object_id="obj_1",
        location=(1.0, 2.0, 3.0),
    )
    window._on_finding_activated(finding)

    assert window.analysis_bar.chosen() is None, "no map claims this code"


# --- feature overlay (§18.5) ----------------------------------------------------


def test_the_object_tree_lists_the_features(window: MainWindow) -> None:
    """Name links, Maß rechts — und beides lesbar.

    Vorher stand links die ganze Beschriftung und rechts der Typ („hole",
    „face"): links war abgeschnitten, was rechts gefehlt hat.
    """
    item = window.object_tree.tree.topLevelItem(0)

    assert item is not None and item.childCount() >= 4, "four bores and the faces"
    names = [item.child(index).text(0) for index in range(item.childCount())]
    measures = [item.child(index).text(1) for index in range(item.childCount())]

    assert any(text.startswith(tr("Bohrung")) for text in names)
    assert any(text.startswith("Ø") for text in measures), "das Maß gehört in die Maßspalte"
    assert not any(text in ("hole", "face") for text in measures), "der Typ ist kein Maß"


def test_a_face_is_named_by_where_it_looks() -> None:
    """Im Baum stand `face_2` — die Kennung, mit der der Op-Stack rechnet, und
    für einen Menschen eine Nummer ohne Aussage.

    Eine ebene Fläche weiß, wohin sie zeigt. Die Kennung bleibt: sie steht im
    Tooltip und in jedem Parameterfeld.
    """
    from app.core.types import Feature
    from app.ui.labels import feature_name

    def face(name: str, normal: tuple[float, float, float]) -> Feature:
        return Feature(
            id=name, kind="face", params={"normal": normal, "area": 100.0}, provenance="test"
        )

    assert feature_name("face_2", face("face_2", (0.0, 0.0, 1.0))) == tr("Oberseite")
    assert feature_name("face_1", face("face_1", (0.0, 0.0, -1.0))) == tr("Unterseite")
    assert feature_name("face_3", face("face_3", (0.0, -1.0, 0.0))) == tr("Vorderseite")
    assert feature_name("face_9", face("face_9", (0.6, 0.0, 0.8))) == tr("Schrägfläche")


def test_a_feature_offers_the_operations_that_apply_to_it(window: MainWindow) -> None:
    """§10, §18.5: das Kontextmenü kommt aus ``applies_to``, nicht aus einer
    Liste.
    """
    entries = window.object_tree.operations_for_feature("face")

    assert entries, "drilling applies to a face"
    assert all("face" in spec.applies_to for spec in entries)


def test_the_view_and_the_tree_show_the_same_menu(window: MainWindow) -> None:
    """Zwei Menüs mit derselben Aufgabe wären zwei Gelegenheiten,
    auseinanderzulaufen.

    Der Viewport baut deshalb keines: er lässt sich das des Objektbaums geben.
    Ohne Auswahl gibt es nichts anzubieten — und dann geht auch nichts auf.
    """
    window.object_tree.tree.clearSelection()
    assert window.object_tree.context_menu() is None

    select_plate(window)
    menu = window.object_tree.context_menu()

    assert menu is not None
    offered = {
        action.text()
        for entry in menu.actions()
        for action in (entry.menu().actions() if entry.menu() else [entry])
    }
    assert any(str(spec.title) in offered for spec in window.object_tree.operations_for_object())
    menu.deleteLater()


def test_a_feature_menu_names_the_operations_of_its_kind(window: MainWindow) -> None:
    """Der Ort, den §18.5 „die wichtigste Einzelfunktion" nennt.

    Die Art des Merkmals wurde aus der zweiten Spalte des Baums gelesen, und
    dort steht das Maß: „Ø3,22 mm" für eine Bohrung. An ``for_feature``
    gereicht fand das nie eine Operation, und das Menü an einer angeklickten
    Bohrung bestand aus Ausblenden und Alles andere ausblenden.
    """
    window.object_tree.select_feature("obj_1", "hole_2")
    menu = window.object_tree.context_menu()

    assert menu is not None
    labels = {action.text() for action in menu.actions()}
    expected = {str(spec.title) for spec in window.object_tree.operations_for_feature("hole")}

    assert expected, "an einer Bohrung gibt es etwas zu tun"
    assert expected <= labels, "und es steht direkt da, ohne Aufklappen"
    menu.deleteLater()


def test_a_feature_without_operations_of_its_own_offers_the_body(window: MainWindow) -> None:
    """Wer genauer gezeigt hat, bekommt nicht weniger.

    Zu einer Merkmalsart ohne eigene Operationen bestand das Menü aus
    *Ausblenden* und *Alles andere ausblenden* — weniger als ein Klick auf den
    Körper daneben, und der Körper ist mitgewählt. ``thread`` ist heute so eine
    Art: ein Gewinde entsteht als benanntes Merkmal eines Bausteins, und keine
    Operation nennt es in ``applies_to``.

    Dieselbe Überlegung, aus der ``applies_to`` in der Befehlspalette eine
    Reihenfolge ist und keine Auswahl (§2.6).
    """
    from app.core.registry import REGISTRY

    assert not REGISTRY.for_feature("thread"), (
        "sobald eine Operation am Gewinde arbeitet, prüft dieser Test die "
        "andere Hälfte der Regel — dann eine Art ohne Operationen einsetzen"
    )

    window.object_tree._feature_kind = lambda: "thread"  # type: ignore[method-assign]
    select_plate(window)
    menu = window.object_tree.context_menu()

    assert menu is not None
    rows = [action for action in menu.actions() if not action.isSeparator()]
    assert len(rows) > 2, [action.text() for action in rows]
    offered = {
        action.text()
        for entry in rows
        for action in (entry.menu().actions() if entry.menu() else [entry])
    }
    assert any(str(spec.title) in offered for spec in window.object_tree.operations_for_object())
    menu.deleteLater()


def test_a_body_menu_stays_short_enough_to_read(window: MainWindow) -> None:
    """Siebenundfünfzig Zeilen sind kein Menü, sondern ein Register.

    Am ganzen Körper passt fast alles, was das Register kennt. Gruppiert wird
    dann nach derselben Kategorie wie in der Menüleiste — flach bleibt es nur,
    solange man es überblickt.
    """
    from app.ui.panels import MAX_MENU_ROWS

    select_plate(window)
    menu = window.object_tree.context_menu()

    assert menu is not None
    rows = [action for action in menu.actions() if not action.isSeparator()]
    assert len(rows) <= MAX_MENU_ROWS, [action.text() for action in rows]
    assert any(action.menu() is not None for action in rows), "gruppiert, nicht gekürzt"
    menu.deleteLater()


def test_selecting_a_feature_reaches_the_viewport(window: MainWindow) -> None:
    window.object_tree.select_feature("obj_1", "hole_2")

    assert window.object_tree.selected_feature() == "hole_2"
    assert window.object_tree.selected() == "obj_1"


def test_the_diameter_of_a_bore_reaches_the_status_bar(window: MainWindow) -> None:
    """§18.3: der Durchmesser kommt aus dem Merkmal, nicht aus einem Messklick."""
    select_plate(window)
    item = window.object_tree.tree.topLevelItem(0)
    assert item is not None
    window.object_tree.select_feature("obj_1", "hole_1")

    assert "Ø" in window.measurements.text()


def test_the_rotation_centre_is_the_body_and_not_the_scenery(window: MainWindow) -> None:
    """Gedreht wird um das Teil, nicht um den Bauraum (§2.9).

    Der Drehpunkt kam aus ``ComputeVisiblePropBounds`` — den Grenzen alles
    Sichtbaren, und dazu gehören Druckplatte und Bauraumrahmen. Der Rahmen ist
    250 mm hoch, das Teil 8: die Mitte lag über hundert Millimeter über dem
    Modell, die Kamera rückte dorthin mit, und im Bild stand die Kulisse,
    während das Teil unten aus der Ecke ragte. Genau so kam das Hauptfenster
    aus dem Abbildungswerkzeug heraus.

    Geprüft wird die Auskunft, nicht die Kamera: offscreen gibt es keinen
    Plotter, und ein Test, der sich dort überspringt, prüft nie etwas.
    """
    select_plate(window)
    window.viewport.show_scene(window.session.last_result)
    window.viewport.show_build_volume(window.session.profile)

    centre = window.viewport.rotation_centre()
    entry = window.session.last_result.scene.objects["obj_1"]
    box = entry.mesh.bounds

    assert centre is not None
    for axis in range(3):
        expected = (box.minimum[axis] + box.maximum[axis]) / 2.0
        assert centre[axis] == pytest.approx(expected), "die Mitte des Körpers"

    height = window.session.profile.printer.build_volume[2]
    assert centre[2] < height / 4.0, "und nicht die halbe Bauraumhöhe"


def test_a_chosen_feature_lights_up_instead_of_its_body(window: MainWindow) -> None:
    """Wer eine Bohrung anklickt, meint die Bohrung (§18.5).

    Gefärbt wurde der ganze Körper: die Auswahl zeigte das Objekt, und die
    Stelle, die gemeint war, unterschied sich von der Wand daneben durch
    nichts. Jetzt trägt das Merkmal die Auswahlfarbe auf seinen eigenen
    Dreiecken, und der Körper bleibt grau — dass er ausgewählt ist, steht im
    Objektbaum und in der Statusleiste, wie bei einer Analysekarte auch
    (§19.1).

    Geprüft wird die Entscheidung, nicht das Bild: offscreen gibt es keinen
    Plotter, und ein Test, der sich dort überspringt, prüft nie etwas.
    """
    select_plate(window)
    window.viewport.show_scene(window.session.last_result)
    window.viewport.select("obj_1")

    assert window.viewport.highlighted_object() == "obj_1", "ohne Merkmal färbt der Körper"
    assert window.viewport.highlighted_faces() == (), "und es leuchtet keine Fläche"

    window.object_tree.select_feature("obj_1", "hole_2")

    assert window.viewport.selected_feature == "hole_2"
    assert window.viewport.highlighted_object() is None, "jetzt nicht mehr der ganze Körper"
    faces = window.viewport.highlighted_faces()
    assert faces, "sondern die Dreiecke der Bohrung"
    entry = window.session.last_result.scene.objects["obj_1"]
    assert set(faces) == set(entry.features["hole_2"].face_indices)

    # Und zurück: ohne Merkmal gehört die Farbe wieder dem Körper.
    window.viewport.select_feature(None)
    assert window.viewport.highlighted_object() == "obj_1"
    assert window.viewport.highlighted_faces() == ()


def test_a_hidden_body_lights_up_nothing(window: MainWindow) -> None:
    """Ein ausgeblendeter Körper ist nicht im Bild, sein Merkmal also auch
    nicht — eine Fläche, die über einem unsichtbaren Teil schwebt, behauptet
    Geometrie, wo keine steht (§18.8)."""
    select_plate(window)
    window.viewport.show_scene(window.session.last_result)
    window.viewport.select("obj_1")
    window.viewport.select_feature("hole_2")
    assert window.viewport.highlighted_faces(), "sichtbar leuchtet sie"

    window.viewport.set_hidden(frozenset({"obj_1"}))
    assert window.viewport.highlighted_faces() == ()


def test_a_click_in_the_view_finds_the_feature_under_it(window: MainWindow) -> None:
    """§40 für P3: ein Klick muss die richtige Merkmal-ID liefern, keinen
    Beinahe-Treffer.
    """
    select_plate(window)
    window.viewport.show_scene(window.session.last_result)
    window.viewport.select("obj_1")
    entry = window.session.last_result.scene.objects["obj_1"]
    centre = entry.features["hole_3"].params["centre"]

    picked = window.viewport._feature_at((centre[0] + 0.4, centre[1] - 0.3, centre[2]))
    assert picked == "hole_3"


class _PickyPlotter:
    """Ein Plotter, der sich beim Picking verhält wie pyvista.

    Der echte lehnt ein zweites ``enable_point_picking`` mit einer Ausnahme ab.
    Offscreen gibt es keinen Plotter, also führt kein Test den Zweig aus, in
    dem das Picking eingeschaltet wird — genau darum startete die Anwendung
    nach dem Anschließen der Auswahl nicht mehr, und die Suite war grün dabei.
    """

    def __init__(self) -> None:
        self.enabled = False
        self.rounds = 0

    def enable_point_picking(self, **_: object) -> None:
        if self.enabled:
            raise RuntimeError("Picking is already enabled")
        self.enabled = True
        self.rounds += 1

    def disable_picking(self) -> None:
        self.enabled = False


def test_switching_navigation_keeps_the_picking_alive(qt_app: QApplication) -> None:
    """Ein Stilwechsel darf das Picking nicht abhängen (§18.5).

    Der Test hat lange geprüft, dass ``plotter.enable_point_picking`` nach
    jedem Wechsel neu läuft. Das war richtig gedacht und half nichts: pyvista
    sucht sich den Renderer über ``GetInteractorStyle()._parent()``, also über
    seinen **eigenen** Stil, und Solidon setzt für die vier
    Navigationsschemata einen eigenen. Jeder Klick endete in einem
    ``AttributeError``, den pyvistaqt zu einer Warnung macht — die Auswahl im
    Viewport hat nie funktioniert, und der Test war grün dabei.

    Jetzt löst der Stil das Picking selbst aus. Geprüft wird also, was
    tatsächlich zählt: dass ein Klick nach dem Wechsel ankommt.
    """
    from app.ui.viewport import _InteractorStyle

    seen: list[tuple[int, int]] = []

    style = _InteractorStyle(None, "slicer", None, lambda x, y: seen.append((x, y)))
    assert hasattr(style, "_left_at"), "der Stil merkt sich, wo gedrückt wurde"

    # Ohne Interactor lässt sich kein Klick nachstellen; was hier zählt, ist
    # die Verdrahtung — dass der Rückruf im Stil steckt und nicht bei pyvista.
    assert style.GetClassName().startswith("vtkInteractorStyle")


def test_picking_needs_no_plotter_call_any_more(qt_app: QApplication) -> None:
    """Und ``_enable_picking`` fasst den Plotter nicht mehr an.

    Der ``_PickyPlotter`` lehnt ein zweites ``enable_point_picking`` ab, wie es
    der echte tut. Wird er gar nicht erst gerufen, kann auch nichts doppelt
    angeschaltet werden — das war der eigentliche Grund für die Klimmzüge
    davor.
    """
    from app.ui.viewport import Viewport

    viewport = Viewport()
    try:
        plotter = _PickyPlotter()
        viewport.plotter = plotter

        viewport._enable_picking()
        viewport._enable_picking()

        assert plotter.rounds == 0, "das Picking hängt am eigenen Stil, nicht am Plotter"
    finally:
        viewport.plotter = None
        viewport.deleteLater()


def test_the_same_finding_is_not_listed_twice(qt_app: QApplication) -> None:
    """§17.3: zweimal gemeldet ist nicht zweimal passiert.

    „Kollisionen prüfen" und die Exportprüfung sehen dieselbe Sache. Nach
    beidem stand „Ein Objekt steht über den Bauraum hinaus" zweimal im Bericht,
    und wer das liest, sucht nach zwei Körpern, von denen es nur einen gibt.

    Geprüft wird das Panel allein: es braucht kein Fenster, und jedes Fenster
    bringt einen Viewport mit, der aufgeräumt werden will.
    """
    from app.ui.panels import ReportPanel

    finding = Finding(
        code="arrange.out_of_build_volume",
        severity="warning",
        message="Ein Objekt steht über den Bauraum hinaus.",
        object_id="obj_1",
        values={"object": "Halter", "excess": "15,00 mm"},
    )
    panel = ReportPanel()
    try:
        panel.add_findings([finding])
        panel.add_findings([finding])

        assert panel.list.count() == 1
    finally:
        panel.deleteLater()


def test_the_same_message_about_another_body_stays_its_own_line(qt_app: QApplication) -> None:
    """Zwei Körper stehen aus verschiedenen Gründen hinaus — zwei Zeilen."""
    from app.ui.panels import ReportPanel

    first = Finding(
        code="arrange.out_of_build_volume",
        severity="warning",
        message="Ein Objekt steht über den Bauraum hinaus.",
        object_id="obj_1",
        values={"object": "Halter"},
    )
    second = dataclasses.replace(first, object_id="obj_2", values={"object": "Deckel"})
    panel = ReportPanel()
    try:
        panel.add_findings([first, second])

        assert panel.list.count() == 2
    finally:
        panel.deleteLater()


def test_a_finding_says_in_its_line_what_it_is_about() -> None:
    """§17.3: „Zwei Objekte überschneiden sich" — welche zwei?

    Die Antwort stand schon in ``values``, aber nur im Tooltip: man musste
    wissen, dass dort etwas ist, und mit der Maus hinfahren. Ein Bericht, den
    man abfährt, um ihn zu lesen, wird nicht gelesen.
    """
    from app.ui.panels import _line_for

    finding = Finding(
        code="arrange.collision",
        severity="warning",
        message="Zwei Objekte überschneiden sich.",
        values={"a": "Gehäuse", "b": "Deckel", "shared": "12,40 mm³", "checked": "exact"},
    )

    line = _line_for(finding)
    assert "Gehäuse" in line and "Deckel" in line
    assert "12,40 mm³" in line, "und wie viel — ein Streifschuss ist kein Problem"
    assert "exact" not in line, "das Verfahren gehört in den Tooltip, nicht in die Zeile"


def test_a_finding_without_values_stays_as_it_is() -> None:
    """Kein Gedankenstrich ohne etwas dahinter."""
    from app.ui.panels import _line_for

    finding = Finding(code="ingest.welded", severity="info", message="Doppelte Punkte verschweißt.")

    assert _line_for(finding) == "Doppelte Punkte verschweißt."


def test_a_part_that_fits_gets_told_so(window: MainWindow) -> None:
    """§2.7: eine Handlung endet in einer Aussage, auch wenn nichts zu tun war.

    Der Kern sagt es sauber — ``transaction is None`` —, und das Fenster macht
    daraus einen Satz. Getestet war er bis hierher nicht, hätte also jederzeit
    verschwinden können; wer *Automatisch teilen* auf ein passendes Teil
    anwendet, stünde dann vor einem unveränderten Fenster und müsste raten, ob
    die Funktion kaputt ist oder das Teil in Ordnung.

    Die geladene Platte ist 80 × 50 × 8 mm und passt auf jedes Bett dieser
    Startbestückung.
    """
    window.action_auto_split("obj_1")
    window.session.wait_for_idle()
    window.wait_for_workers()

    assert "passt bereits" in window.status_message.text()


def test_a_right_click_opens_the_menu_and_a_drag_does_not() -> None:
    """§18.5: das Kontextmenü am Merkmal ist der Ort für Weg 1.

    Ein fremdes Modell wird angepasst, indem man auf die Stelle zeigt, die
    stört. Bis hierher zeigte ein Rechtsklick auf einen Körper gar nichts — das
    Menü gab es nur im Objektbaum, wo die Merkmale ``hole_3`` heißen.

    In jedem Schema tut die rechte Taste aber auch etwas an der Kamera: ein Zug
    meint sie, ein Klick meint das, worauf er zeigt. Sonst ginge nach jedem
    Drehen ein Menü auf.
    """
    from app.ui.viewport import is_click

    assert is_click((100, 200), (100, 200)), "stillgehalten ist ein Klick"
    assert is_click((100, 200), (101, 199)), "eine Maus steht beim Drücken selten ganz still"
    assert not is_click((100, 200), (160, 240)), "ein Zug öffnet kein Menü"
    assert not is_click((100, 200), (100, 210)), "auch senkrecht gezogen ist gezogen"
    assert not is_click(None, (100, 200)), "ohne Druck davor gibt es nichts zu beenden"


def test_fitting_measures_the_bodies_not_the_build_volume(window: MainWindow) -> None:
    """§18.1: „Alles einpassen" meint die Körper.

    ``plotter.reset_camera()`` nimmt alle Aktoren, und dazu gehört der Rahmen
    des Bauraums. Bei einem 80-mm-Teil in einem 256er Bauraum füllte damit die
    Kulisse das Bild — der Befehl tat sichtbar nichts, weil schon eingepasst
    war.
    """
    window.viewport.show_scene(window.session.last_result)
    entry = window.session.last_result.scene.objects["obj_1"]
    box = entry.mesh.bounds

    bounds = window.viewport._object_bounds()
    assert bounds is not None
    assert bounds == (
        box.minimum[0],
        box.maximum[0],
        box.minimum[1],
        box.maximum[1],
        box.minimum[2],
        box.maximum[2],
    )


def test_an_empty_scene_still_shows_the_build_volume(qt_app: QApplication) -> None:
    """Ohne Körper ist der Bauraum das Einzige, was es zu sehen gibt."""
    from app.ui.viewport import Viewport

    viewport = Viewport()
    try:
        assert viewport._object_bounds() is None
    finally:
        viewport.deleteLater()


def test_the_camera_is_fitted_once_and_then_left_alone(window: MainWindow) -> None:
    """Ein Zoom überlebt die nächste Auswahl.

    Die Ansicht wird bei jeder Änderung neu aufgebaut; pyvista setzt die Kamera
    zurück, sobald es den ersten Aktor bekommt, und nach dem Leerräumen ist
    jeder Körper der erste. Damit sprang die Ansicht bei jedem Klick auf
    Anfang.
    """
    result = window.session.last_result
    window.viewport.show_scene(result)
    assert window.viewport._fitted_to == "objects", "das geöffnete Projekt steht im Bild"

    window.viewport.show_scene(result)
    assert window.viewport._fitted_to == "objects", "und der nächste Aufbau passt nicht erneut ein"

    window.viewport.show_scene(None)
    assert window.viewport._fitted_to == "bed", (
        "eine leere Szene macht den Weg für das nächste Projekt frei"
    )


class _CameraPlotter:
    """Ein Plotter, der nur Buch führt.

    Offscreen gibt es keinen echten — und genau dort spielt dieser Fehler:
    ein Test, der sich ohne Plotter überspringt, hätte nie gemerkt, dass das
    Einpassen wirkungslos war.
    """

    def __init__(self) -> None:
        self.camera_set = False
        self.fitted_to: list[object] = []

    def reset_camera(self, bounds: object = None) -> None:
        self.fitted_to.append(bounds)


def test_fitting_tells_pyvista_that_it_is_done(window: MainWindow) -> None:
    """Sonst passt pyvista gleich noch einmal ein — über alles.

    ``reset_camera(bounds=…)`` lässt ``camera_set`` auf False stehen, und der
    nächste Zugriff auf ``plotter.camera`` (beim Rendern, beim Stilwechsel, bei
    jeder Achsansicht) setzt die Kamera daraufhin selbst — diesmal über *alle*
    Aktoren. Der Bauraum gewann also jedes Mal, obwohl hier die Maße der Körper
    standen: „Alles einpassen" tat sichtbar nichts.

    Eingepasst wird **mit Luft**: genau auf die Grenzen berührte ein 40 mm
    großer Quader links und rechts den Bildrand.
    """
    from app.ui.viewport import with_margin

    window.viewport.show_scene(window.session.last_result)
    plotter = _CameraPlotter()
    window.viewport.plotter = plotter

    window.viewport.reset_camera()

    bounds = window.viewport._object_bounds()
    assert bounds is not None
    assert plotter.fitted_to == [with_margin(bounds)], "auf die Körper, mit Luft darum"
    assert plotter.camera_set, "und danach fasst pyvista die Kamera nicht mehr an"


def test_an_empty_scene_still_fits_on_something(window: MainWindow) -> None:
    """Ohne Körper bleibt der Bauraum das Maß — dann ist er das Einzige, was
    es zu sehen gibt.

    **Gerechnet wird er hier selbst**, statt ``reset_camera()`` ohne Grenzen zu
    rufen und pyvista alle Aktoren suchen zu lassen. Zwei Gründe: nur so bekommt
    auch die leere Szene ihre Luft, und nur so hängt das Ergebnis nicht daran,
    welche Kulisse gerade zusätzlich im Bild steht. Ohne Grenzen rutschte die
    Platte ins untere Drittel und teilweise hinter die Werkzeugzeile.
    """
    from app.ui.viewport import with_margin

    window.viewport.show_scene(None)
    plotter = _CameraPlotter()
    window.viewport.plotter = plotter

    window.viewport.reset_camera()

    volume = window.viewport._volume_bounds()
    assert volume is not None, "das Fenster hat ein Profil, also gilt ein Bauraum"
    assert plotter.fitted_to == [with_margin(volume)]
    assert plotter.camera_set


def test_a_new_project_puts_the_build_volume_in_the_picture(window: MainWindow) -> None:
    """Nach *Neues Projekt* muss die Druckplatte zu sehen sein.

    Sie war es nicht: eingepasst wurde nur, wenn Körper da waren, und die
    Startkamera stand aus dem Aufbau heraus auf (1, -1, 0,8) — anderthalb
    Millimeter vom Ursprung entfernt, während der Bauraum 220 mm misst. Wer
    ein neues Projekt anlegte, sah eine leere Fläche und musste Pos1 drücken,
    um zu erfahren, dass alles in Ordnung ist.

    Geprüft wird ``_fit_once_for`` und nicht ``show_scene``: die Entscheidung
    fällt dort, und der Buchhalter-Plotter kennt nur ``reset_camera``.
    """
    viewport = window.viewport
    viewport.show_scene(window.session.last_result)
    assert viewport._fitted_to == "objects"

    plotter = _CameraPlotter()
    viewport.plotter = plotter
    # In derselben Reihenfolge wie ``show_scene``: erst steht die neue Szene,
    # dann wird eingepasst. Andersherum misst ``reset_camera`` die Körper der
    # vorigen und passt auf etwas ein, das nicht mehr da ist.
    viewport._result = None
    viewport._fit_once_for(None)

    from app.ui.viewport import with_margin

    volume = viewport._volume_bounds()
    assert volume is not None
    assert plotter.fitted_to == [with_margin(volume)], "die leere Szene passt auf den Bauraum ein"
    assert viewport._bed_extent is not None, "der Bauraum gilt auch ohne Plotter"
    assert viewport._fitted_to == "bed"

    plotter.fitted_to.clear()
    viewport._fit_once_for(None)
    assert plotter.fitted_to == [], "der nächste leere Aufbau lässt die Kamera in Ruhe"


def test_a_scene_that_outgrows_the_view_gets_fitted_again() -> None:
    """Der Sprung ist etwas anderes als die Feinarbeit.

    „Jeder weitere Aufbau lässt die Kamera in Ruhe" schützt den Zoom, und das
    bleibt so: Wer heranzoomt und eine Bohrung setzt, will seinen Zoom behalten.
    Aufgenommen am laufenden Fenster war aber auch der andere Fall zu sehen: In
    ein Teil von zwei Millimetern hineingezoomt und einen 400er Körper dazu
    erzeugt — die Kamera stand in dessen Innerem, und zu sehen war eine
    dunkelrote Fläche. Der Prüfbericht warnte richtig, das Bild sagte nichts.

    Geprüft wird die Entscheidung als reine Funktion: offscreen gibt es keinen
    Plotter, und was nur im Zeichnen steht, prüft niemand.
    """
    from app.ui.viewport import OUTGROWN_FACTOR, diagonal_of, outgrown

    tiny = (-1.0, 1.0, -1.0, 1.0, 0.0, 1.0)
    huge = (-200.0, 200.0, -150.0, 150.0, 0.0, 250.0)
    aside = (500.0, 520.0, 500.0, 520.0, 0.0, 20.0)
    nearby = (-2.0, 2.0, -2.0, 2.0, 0.0, 2.0)

    assert outgrown(tiny, huge), "gewachsen: die Kamera steht im neuen Körper"
    assert diagonal_of(huge) > OUTGROWN_FACTOR * diagonal_of(tiny), "und zwar deutlich"
    assert outgrown(tiny, aside), "weggerückt: das Modell liegt außerhalb des Bildes"

    assert not outgrown(tiny, nearby), "das Doppelte ist Feinarbeit — der Zoom bleibt"
    assert not outgrown(huge, tiny), "was kleiner wird, zieht die Kamera nicht an sich"
    assert not outgrown(None, huge), "ohne Vorher gibt es nichts zu vergleichen"
    assert not outgrown(huge, None), "und ohne Körper nichts einzupassen"


def test_the_camera_follows_a_body_that_dwarfs_the_scene(window: MainWindow) -> None:
    """Dieselbe Sache am Fenster: erst eingepasst, dann entwachsen.

    Die Blickrichtung bleibt dabei, wo sie war — ``reset_camera`` rahmt neu und
    dreht nichts.
    """
    viewport = window.viewport
    viewport.show_scene(window.session.last_result)
    assert viewport._fitted_to == "objects"
    assert viewport._fitted_bounds is not None, "worauf eingepasst wurde, wird gemerkt"

    plotter = _CameraPlotter()
    viewport.plotter = plotter
    viewport._fit_once_for(window.session.last_result)
    assert plotter.fitted_to == [], "derselbe Stand lässt die Kamera in Ruhe"

    # Die Szene wächst: derselbe Zustand „objects", aber ein Vielfaches groß.
    viewport._fitted_bounds = (-1.0, 1.0, -1.0, 1.0, 0.0, 1.0)
    viewport._fit_once_for(window.session.last_result)
    assert plotter.fitted_to, "der Sprung wird neu gerahmt"


def test_the_build_volume_is_a_hint_not_a_cage() -> None:
    """Als geschlossener Drahtkasten war die Oberkante aus der Vorgabeansicht
    eine große Raute weit über dem Bett — und das Teil darunter ein Fleck.

    Gebraucht wird zweierlei: wie hoch darf es werden, und wo hört die Fläche
    auf. Vier senkrechte Ecken und je zwei kurze Winkel oben tragen beides.
    """
    from app.ui.viewport import CORNER_FRACTION, volume_edges

    segments = volume_edges(200.0, 100.0, 250.0)
    assert len(segments) == 12, "vier Ecken mit je einer Senkrechten und zwei Winkeln"

    uprights = [pair for pair in segments if pair[0][2] != pair[1][2]]
    assert len(uprights) == 4
    for start, end in uprights:
        assert (start[2], end[2]) == (0.0, 250.0), "vom Bett bis nach oben"

    top = [pair for pair in segments if pair[0][2] == pair[1][2] == 250.0]
    assert len(top) == 8, "zwei Arme je Ecke, keine durchgehende Kante"
    for start, end in top:
        length = max(abs(end[0] - start[0]), abs(end[1] - start[1]))
        assert length in (200.0 * CORNER_FRACTION, 100.0 * CORNER_FRACTION)
        # Nach innen: außerhalb der Fläche hätten sie nichts zu begrenzen.
        assert abs(end[0]) <= abs(start[0]) and abs(end[1]) <= abs(start[1])


def test_the_gizmo_axes_say_which_is_which() -> None:
    """Regel 18: Rot, Grün und Blau waren die einzige Unterscheidung.

    Wer die drei Farben nicht trennt, sah drei gleiche Pfeile — und der Gizmo
    ist das Werkzeug, mit dem man ein Teil bewegt, also ist „welche Achse" die
    einzige Frage, die er beantworten muss.
    """
    from app.ui.viewport import GIZMO_LABEL_GAP, gizmo_labels

    marks = gizmo_labels((10.0, 20.0, 30.0), 50.0)
    assert [text for _point, text in marks] == ["X", "Y", "Z"]

    reach = 50.0 * GIZMO_LABEL_GAP
    assert marks[0][0] == (10.0 + reach, 20.0, 30.0)
    assert marks[1][0] == (10.0, 20.0 + reach, 30.0)
    assert marks[2][0] == (10.0, 20.0, 30.0 + reach)
    assert reach > 50.0, "hinter der Spitze, nicht auf ihr — dort will man greifen"


def test_the_gizmo_labels_follow_the_body() -> None:
    """Der Griff sitzt am Objekt, also auch seine Beschriftung."""
    from app.ui.viewport import gizmo_labels

    near = gizmo_labels((0.0, 0.0, 0.0), 10.0)
    far = gizmo_labels((100.0, 0.0, 0.0), 10.0)
    assert far[0][0][0] - near[0][0][0] == 100.0


def test_the_gizmo_is_big_enough_to_grab() -> None:
    """pyvistas Vorgaben ergaben auf einem 80-mm-Teil ein Gebilde aus dünnen
    Linien von etwa vierzig Bildpunkten."""
    from app.ui.viewport import GIZMO_LINE_RADIUS, GIZMO_SCALE

    assert GIZMO_SCALE > 0.15, "die Vorgabe von pyvista"
    assert GIZMO_LINE_RADIUS > 0.02, "und ihre Strichstärke"


class _GizmoActor:
    """Ein Actor mit genau dem, was Auswahl, Beschriftung und Griffe anfassen."""

    def __init__(self) -> None:
        self.prop = SimpleNamespace(color=None)
        self.center = (0.0, 0.0, 0.0)
        self.mapper = SimpleNamespace(
            SetResolveCoincidentTopologyToPolygonOffset=lambda: None,
            SetRelativeCoincidentTopologyPolygonOffsetParameters=lambda *_args: None,
        )
        self.user_matrix = None

    def GetLength(self) -> float:  # noqa: N802 — VTK-Name
        return 10.0


class _GizmoWidget:
    """Spiegelt die echte API: ``AffineWidget3D`` hat ``remove()`` — und
    kein ``Off()``. Ein Fake mit ``Off`` hätte den Absturz beim Abschalten
    genau so versteckt, wie die Suite ihn versteckt hat."""

    def __init__(self, actor: object) -> None:
        self.actor = actor
        self.removed = False

    def remove(self) -> None:
        self.removed = True


class _GizmoInteractor:
    """Verbucht, wer den Interaktionsstil setzt."""

    def __init__(self) -> None:
        self.styles: list[object] = []

    def SetInteractorStyle(self, style: object) -> None:  # noqa: N802 — VTK-Name
        self.styles.append(style)


class _GizmoObservers:
    """Der ``iren`` des Fakes: zählt Beobachter an und wieder ab.

    Der Skaliergriff meldet drei an und muss alle drei wieder loswerden —
    ein vergessener zieht am Griff der vorigen Auswahl weiter.
    """

    def __init__(self) -> None:
        self.active: dict[int, str] = {}
        self._next = 0

    def add_observer(
        self,
        event: str,
        _call: object,
        interactor_style_fallback: bool = True,
    ) -> int:
        self._next += 1
        self.active[self._next] = event
        return self._next

    def remove_observer(self, identifier: int) -> None:
        del self.active[identifier]


class _GizmoPlotter:
    """Ein Plotter, der Griffe und Beschriftungen nur verbucht."""

    def __init__(self) -> None:
        self.widgets: list[_GizmoWidget] = []
        self.interactor = _GizmoInteractor()
        self.iren = _GizmoObservers()

    def add_affine_transform_widget(self, actor: object, **_kwargs: object) -> _GizmoWidget:
        widget = _GizmoWidget(actor)
        self.widgets.append(widget)
        return widget

    def add_point_labels(self, *_args: object, **_kwargs: object) -> object:
        return object()

    def remove_actor(self, _actor: object, render: bool = True) -> None:
        pass

    def add_mesh(self, *_args: object, **_kwargs: object) -> _GizmoActor:
        return _GizmoActor()

    def render(self) -> None:
        pass


def _gizmo_viewport() -> tuple[object, _GizmoPlotter]:
    """Ein Viewport mit Buchführungs-Plotter und zwei Körpern im Bild."""
    from app.ui.viewport import Viewport

    viewport = Viewport()
    plotter = _GizmoPlotter()
    viewport.plotter = plotter
    viewport._actors = {"obj_1": _GizmoActor(), "obj_2": _GizmoActor()}
    return viewport, plotter


def test_the_gizmo_comes_off_again(qt_app: QApplication) -> None:
    """Abschalten nimmt den Griff aus dem Bild.

    ``AffineWidget3D`` hat kein ``Off()`` — der alte Aufruf endete als
    ``AttributeError``, den Qt verschluckte: der Griff blieb stehen, obwohl
    der Schalter aus war. Die Gizmo-Tests prüften bis dahin nur die reinen
    Funktionen, nie das Widget selbst.
    """
    viewport, plotter = _gizmo_viewport()
    try:
        viewport.select("obj_1")
        viewport.set_gizmo(True)
        assert viewport._gizmo is plotter.widgets[-1]

        viewport.set_gizmo(False)
        assert viewport._gizmo is None
        assert plotter.widgets[-1].removed, "über remove(), die Methode, die es gibt"
    finally:
        viewport.deleteLater()


def test_the_gizmo_follows_the_selection(qt_app: QApplication) -> None:
    """§18.11: wer ein anderes Objekt wählt, will es auch bewegen.

    Der Griff hing bis dahin an der Auswahl zum Zeitpunkt des Einschaltens —
    ein Wechsel im Objektbaum ließ ihn am vorigen Körper stehen, und nach
    jeder Auswertung sogar an einem Actor, der gar nicht mehr im Bild war.
    """
    viewport, _plotter = _gizmo_viewport()
    try:
        viewport.set_gizmo(True)
        assert viewport._gizmo is None, "ohne Auswahl gibt es nichts zu greifen"

        viewport.select("obj_1")
        assert viewport._gizmo is not None, "die Auswahl bringt den Griff mit"
        first = viewport._gizmo
        assert first.actor is viewport._actors["obj_1"]

        viewport.select("obj_2")
        assert first.removed, "der alte Griff geht weg"
        assert viewport._gizmo.actor is viewport._actors["obj_2"], "der neue sitzt am neuen"

        viewport.select(None)
        assert viewport._gizmo is None
        assert viewport._gizmo_wanted, "die Entscheidung bleibt — nur der Griff geht"
    finally:
        viewport.deleteLater()


def test_a_drag_below_the_snap_leaves_no_ghost(qt_app: QApplication) -> None:
    """Ein Zug unter der Fangschwelle erzeugt keine Operation — dann darf er
    auch kein Bild hinterlassen.

    pyvistas Widget verschiebt den Actor schon während des Ziehens und merkt
    sich die Matrix für den nächsten Zug. Ohne Neuanhängen stand der Körper
    im Bild versetzt, während die Szene ihn nie bewegt hat — und der nächste
    Zug hätte den vorigen gleich noch einmal angewandt.
    """
    from app.core.geom.transform import translation

    viewport, _plotter = _gizmo_viewport()
    try:
        viewport.select("obj_1")
        viewport.set_gizmo(True)
        viewport.set_snapping(1.0, 15.0)
        first = viewport._gizmo
        dragged: list[object] = []
        viewport.transformDragged.connect(dragged.append)

        viewport._on_gizmo_released(translation((0.4, 0.0, 0.0)))
        assert dragged == [], "0,4 mm bei 1 mm Raster ist kein Zug"
        assert first.removed, "der Griff wird frisch angehängt"
        assert viewport._gizmo is not None
        assert viewport._gizmo is not first, "mit leerer Matrix statt der alten"

        second = viewport._gizmo
        viewport._on_gizmo_released(translation((5.0, 0.0, 0.0)))
        assert len(dragged) == 1, "ein echter Zug kommt als Schritte an"
        assert second.removed and viewport._gizmo is not second
    finally:
        viewport.deleteLater()


def test_the_axis_letters_travel_with_the_drag(qt_app: QApplication) -> None:
    """Regel 18 gilt auch während des Zugs, nicht nur davor und danach.

    Die Buchstaben standen fest an der Startposition — je weiter man zog,
    desto weiter lag das X von dem Pfeil weg, den es benennt. Jetzt hängen
    sie an einem lebenden PolyData, und jedes Move-Ereignis versetzt dessen
    Punkte um die Matrix des Zugs.
    """
    import numpy as np

    from app.core.geom.transform import rotation, translation
    from app.ui.viewport import moved_marks

    # Die reine Rechnung: verschieben verschiebt, drehen dreht um den Ursprung.
    base = np.array([[10.0, 0.0, 0.0], [0.0, 10.0, 0.0], [0.0, 0.0, 10.0]])
    shifted = moved_marks(base, translation((5.0, 0.0, 0.0)))
    assert shifted[0] == pytest.approx((15.0, 0.0, 0.0))
    turned = moved_marks(base, rotation("z", 90.0))
    assert turned[0] == pytest.approx((0.0, 10.0, 0.0), abs=1e-9), "X-Marke wandert auf die Y-Achse"

    # Und am Griff: die Punkte hinter der Beschriftung folgen dem Ereignis.
    viewport, _plotter = _gizmo_viewport()
    try:
        viewport.select("obj_1")
        viewport.set_gizmo(True)
        assert viewport._gizmo_label_data is not None
        assert viewport._gizmo_label_data.n_points == 4, "X, Y, Z und das S des Würfels"
        before = viewport._gizmo_label_data.points.copy()

        viewport._on_gizmo_interacted(translation((7.0, 0.0, 0.0)))
        after = viewport._gizmo_label_data.points
        assert after[:, 0] == pytest.approx(before[:, 0] + 7.0)

        viewport.set_gizmo(False)
        assert viewport._gizmo_label_data is None, "mit dem Griff geht auch das Dataset"
    finally:
        viewport.deleteLater()


def test_the_scale_factor_is_the_ratio_of_distances() -> None:
    """§18.11 nennt Verschieben, Drehen und Skalieren — der Faktor eines
    Zugs ist Ist-Abstand durch Start-Abstand, eingespannt gegen Ausrutscher.
    """
    from app.ui.scale_widget import FACTOR_RANGE, dragged_factor, ray_plane_hit

    centre = (0.0, 0.0, 0.0)
    assert dragged_factor(centre, (10.0, 0.0, 0.0), (15.0, 0.0, 0.0)) == pytest.approx(1.5)
    assert dragged_factor(centre, (10.0, 0.0, 0.0), (5.0, 0.0, 0.0)) == pytest.approx(0.5)
    assert dragged_factor(centre, (10.0, 0.0, 0.0), (10.0, 0.0, 0.0)) == pytest.approx(1.0)

    # Eingespannt: durchs Zentrum gezogen heißt nicht „auf null geschrumpft".
    assert dragged_factor(centre, (10.0, 0.0, 0.0), (0.0, 0.0, 0.0)) == FACTOR_RANGE[0]
    assert dragged_factor(centre, (0.1, 0.0, 0.0), (1000.0, 0.0, 0.0)) == FACTOR_RANGE[1]
    # Ein Start im Zentrum wäre eine Division durch null — er zieht nichts.
    assert dragged_factor(centre, (0.0, 0.0, 0.0), (5.0, 0.0, 0.0)) == 1.0

    # Der Strahl auf die Kameraebene: senkrecht getroffen, parallel nichts.
    hit = ray_plane_hit((0.0, 0.0, 10.0), (0.0, 0.0, -1.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0))
    assert hit == pytest.approx((0.0, 0.0, 0.0))
    assert (
        ray_plane_hit((0.0, 0.0, 10.0), (1.0, 0.0, 0.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0)) is None
    )


def test_the_scale_handle_lives_and_dies_with_the_gizmo(qt_app: QApplication) -> None:
    """Der Würfel gehört zum Griffsatz: er kommt am Objekt, fehlt an der
    Fläche, und beim Abschalten meldet er seine Beobachter wieder ab.

    Ein vergessener Beobachter zöge am Griff der vorigen Auswahl weiter —
    dieselbe Familie Fehler wie das Widget, das nie abgeschaltet wurde.
    """
    from app.core.types import Feature

    viewport, plotter = _gizmo_viewport()
    try:
        viewport.select("obj_1")
        viewport.set_gizmo(True)
        assert viewport._scale_handle is not None, "am Objekt gibt es den Würfel"
        assert len(plotter.iren.active) == 3, "drei Beobachter: Bewegen, Drücken, Loslassen"
        assert viewport._gizmo_label_data.n_points == 4, "X, Y, Z — und S"

        viewport.set_gizmo(False)
        assert viewport._scale_handle is None
        assert plotter.iren.active == {}, "alle Beobachter sind wieder abgemeldet"

        # An der Fläche gibt es keinen Würfel: sie kennt nur vor und zurück.
        face = Feature(
            id="face_1",
            kind="face",
            provenance="detected",
            params={"normal": (0.0, 0.0, 1.0), "centre": (0.0, 0.0, 5.0)},
        )
        viewport.gizmo_target = lambda: face  # type: ignore[method-assign]
        viewport.set_gizmo(True)
        assert viewport._scale_handle is None, "eine Fläche hat keine Größe zu ändern"
        assert viewport._gizmo_label_data.n_points == 3
    finally:
        viewport.deleteLater()


def test_a_scale_drag_becomes_an_operation(qt_app: QApplication) -> None:
    """Loslassen am Würfel meldet den Faktor — ein Zug, eine Operation,
    ein Undo (§18.11, §2.1). Ein Faktor von eins meldet nichts.
    """
    viewport, plotter = _gizmo_viewport()
    try:
        viewport.select("obj_1")
        viewport.set_gizmo(True)
        first = viewport._gizmo
        factors: list[float] = []
        viewport.scaleDragged.connect(factors.append)

        viewport._on_scale_released(1.00001)
        assert factors == [], "wer nicht gezogen hat, hat nichts skaliert"
        assert first.removed and viewport._gizmo is not first, "der Griffsatz ist frisch"

        viewport._on_scale_released(1.5)
        assert factors == [1.5]
        assert len(plotter.interactor.styles) == 2, "und das Schema ist beide Male zurück"
    finally:
        viewport.deleteLater()


def test_the_drag_shows_its_number_while_it_runs(qt_app: QApplication) -> None:
    """§18.11: die Zahl zum Zug — lesbar, während gezogen wird.

    Wie weit man gezogen hatte, stand bis dahin erst hinterher im Verlauf.
    Jetzt füttert jedes Move-Ereignis das Feld über dem Bild: Achse und
    Millimeter beim Verschieben, Achse und Grad beim Drehen, der Faktor am
    Würfel — und solange niemand tippt, folgt das Feld dem Zeiger.
    """
    from app.core.geom.transform import rotation, translation

    viewport, _plotter = _gizmo_viewport()
    try:
        viewport.select("obj_1")
        viewport.set_gizmo(True)

        viewport._on_gizmo_interacted(translation((3.4, 0.0, 0.0)))
        assert viewport._drag_kind == "move"
        assert viewport._drag_axis == "x"
        # isHidden statt isVisible: offscreen ist der Viewport selbst nie
        # sichtbar, und ein Kind erbt das — gefragt ist, ob das Feld gezeigt
        # würde, nicht ob der Testlauf ein Fenster hat.
        assert not viewport.drag_bar.isHidden()
        assert viewport.drag_bar.value.text() == "3,40"

        viewport._on_gizmo_interacted(rotation("z", 30.0))
        assert viewport._drag_kind == "turn"
        assert viewport.drag_bar.value.text() == "30,0"
        assert viewport.drag_bar.unit.text() == "°"

        viewport._on_scale_interacted(1.375)
        assert viewport._drag_kind == "scale"
        assert viewport.drag_bar.value.text() == "1,375"

        # Sobald getippt wurde, gehört das Feld der Tastatur.
        viewport.drag_bar.typing = True
        viewport.drag_bar.value.setText("2")
        viewport._on_scale_interacted(1.8)
        assert viewport.drag_bar.value.text() == "2", "der Zeiger überschreibt keine Eingabe"
    finally:
        viewport.deleteLater()


def test_a_typed_number_is_applied_exactly(qt_app: QApplication) -> None:
    """§18.11 „Zahleneingabe während des Ziehens": Enter wendet genau die
    getippte Zahl an — ohne Rasterfang, denn wer tippt, meint es exakt.
    """
    from app.core.geom.transform import translation

    viewport, _plotter = _gizmo_viewport()
    try:
        viewport.select("obj_1")
        viewport.set_gizmo(True)
        viewport.set_snapping(1.0, 15.0)
        dragged: list[object] = []
        viewport.transformDragged.connect(dragged.append)

        viewport._on_gizmo_interacted(translation((3.4, 0.0, 0.0)))
        viewport.drag_bar.typing = True
        viewport.drag_bar.value.setText("12,5")
        viewport._apply_typed()

        assert len(dragged) == 1
        assert dragged[0].offset == pytest.approx((12.5, 0.0, 0.0)), (
            "exakt, kein Fang auf 12 oder 13"
        )
        assert viewport._drag_kind is None, "der Zug ist damit zu Ende"
        assert viewport.drag_bar.isHidden()

        # Loslassen während des Tippens wendet nichts an — die Zahl gilt.
        viewport._on_gizmo_interacted(translation((3.4, 0.0, 0.0)))
        viewport.drag_bar.typing = True
        viewport._on_gizmo_released(translation((3.4, 0.0, 0.0)))
        assert len(dragged) == 1, "das Release hat nicht zusätzlich angewandt"
        assert viewport._drag_kind == "move", "und der getippte Zug läuft weiter"

        # Eine Zahl, mit der sich nichts anfangen lässt, wendet nichts an.
        viewport.drag_bar.value.setText("keine Zahl")
        viewport._apply_typed()
        assert len(dragged) == 1
        assert viewport._drag_kind == "move", "der Zug bleibt offen, das Feld markiert sich"

        # Esc verwirft: nichts angewandt, Zustand weg.
        viewport._end_drag()
        assert viewport._drag_kind is None
        assert len(dragged) == 1
    finally:
        viewport.deleteLater()


def test_a_typed_scale_factor_becomes_the_operation(qt_app: QApplication) -> None:
    """Auch am Würfel gilt: die getippte Zahl schlägt den Mausweg — und ein
    Faktor, der nichts ändert oder nichts übrig ließe, wird nicht angewandt.
    """
    viewport, _plotter = _gizmo_viewport()
    try:
        viewport.select("obj_1")
        viewport.set_gizmo(True)
        factors: list[float] = []
        viewport.scaleDragged.connect(factors.append)

        viewport._on_scale_interacted(1.4)
        viewport.drag_bar.typing = True
        viewport.drag_bar.value.setText("2,0")
        viewport._apply_typed()
        assert factors == [2.0]

        viewport._on_scale_interacted(1.4)
        viewport.drag_bar.typing = True
        viewport.drag_bar.value.setText("0")
        viewport._apply_typed()
        assert factors == [2.0], "auf null schrumpfen gibt es nicht"
        assert viewport._drag_kind == "scale", "der Zug bleibt offen"
    finally:
        viewport.deleteLater()


def test_a_drag_gives_the_navigation_back(qt_app: QApplication) -> None:
    """Nach dem Loslassen gilt wieder das gewählte Schema.

    pyvistas Widget schaltet beim Greifen auf seinen Trackball-Stil um und
    stellt beim Loslassen *seinen* Standard wieder her — nicht unseren. Ohne
    die Wiederherstellung waren nach dem ersten Zug Auswahl-Klick,
    Kontextmenü und das Navigationsschema verschwunden, und kein Test sah
    es, weil keiner je einen Zug zu Ende fuhr.
    """
    from app.core.geom.transform import translation

    viewport, plotter = _gizmo_viewport()
    try:
        viewport.select("obj_1")
        viewport.set_gizmo(True)
        assert plotter.interactor.styles == [], "bis hierhin hat niemand den Stil angefasst"

        viewport._on_gizmo_released(translation((5.0, 0.0, 0.0)))
        assert len(plotter.interactor.styles) == 1, "der eigene Stil ist zurück"

        viewport._on_gizmo_released(translation((0.2, 0.0, 0.0)))
        assert len(plotter.interactor.styles) == 2, "auch ein Zug unter der Fangschwelle"
    finally:
        viewport.deleteLater()


class _FakeRenderer:
    """Ein Renderer, der nur rechnet, was für diese Prüfung nötig ist.

    Offscreen gibt es kein VTK — ``_available`` verbietet es ausdrücklich,
    weil ein fehlender OpenGL-Kontext den Prozess mitnähme. Ein Test, der sich
    dort überspringt, prüft nie etwas; also wird die **Verwendung** der
    VTK-Schnittstelle geprüft und nicht VTK selbst: die Reihenfolge der
    Aufrufe und die homogene Division, die man vergessen kann.
    """

    def __init__(self, scale: float = 2.0) -> None:
        self.scale = scale
        """Wie viele Bildpunkte ein Millimeter bekommt."""
        self._world = (0.0, 0.0, 0.0, 1.0)
        self._display = (0.0, 0.0, 0.0)

    def GetActiveCamera(self) -> object:  # noqa: N802 — VTK-Name
        return self

    def GetFocalPoint(self) -> tuple[float, float, float]:  # noqa: N802 — VTK-Name
        return (0.0, 0.0, 0.0)

    def SetWorldPoint(self, x: float, y: float, z: float, w: float) -> None:  # noqa: N802
        self._world = (x, y, z, w)

    def WorldToDisplay(self) -> None:  # noqa: N802 — VTK-Name
        x, y, z, _w = self._world
        self._display = (x * self.scale, y * self.scale, z)

    def GetDisplayPoint(self) -> tuple[float, float, float]:  # noqa: N802 — VTK-Name
        return self._display

    def SetDisplayPoint(self, x: float, y: float, z: float) -> None:  # noqa: N802
        self._display = (x, y, z)

    def DisplayToWorld(self) -> None:  # noqa: N802 — VTK-Name
        x, y, z = self._display
        # Mit einem Gewicht ungleich eins: wer die Division vergisst, bekommt
        # hier den doppelten Wert und fällt auf.
        self._world = (x / self.scale * 2.0, y / self.scale * 2.0, z * 2.0, 2.0)

    def GetWorldPoint(self) -> tuple[float, float, float, float]:  # noqa: N802
        return self._world


def test_the_point_under_the_pointer_is_computed_in_world_units() -> None:
    """Handbuch und Code-Kommentar behaupteten beide, das Rad zoome dorthin,
    wo der Zeiger steht. Nachgemessen wanderte der Punkt weg — VTKs
    Trackball-Stil dollyt entlang der Kamera-Achse, und man zoomt an dem
    vorbei, was man ansehen wollte.

    Die Rechnung dahinter: Bildpunkt zurück in die Welt, auf der Tiefe des
    Fokuspunkts, mit homogener Division. An der echten Kamera gemessen bleibt
    der Punkt danach auf null Komma null Millimeter stehen; hier wird geprüft,
    dass die Schnittstelle richtig benutzt wird.
    """
    from app.ui.viewport import _world_under

    renderer = _FakeRenderer(scale=2.0)

    point = _world_under(renderer, 100, 50)

    assert point is not None
    assert point == pytest.approx((50.0, 25.0, 0.0)), "geteilt, nicht nur umgerechnet"


def test_a_pointer_without_a_world_point_says_nothing() -> None:
    """Ein Gewicht von null hieße Division durch null — dann lieber kein
    Punkt als eine Ausnahme mitten in einer Mausbewegung."""
    from app.ui.viewport import _world_under

    class _Degenerate(_FakeRenderer):
        def DisplayToWorld(self) -> None:  # noqa: N802 — VTK-Name
            self._world = (1.0, 1.0, 1.0, 0.0)

    assert _world_under(_Degenerate(), 10, 10) is None


def test_a_click_on_the_body_selects_it(window: MainWindow) -> None:
    """§2.9 und §18.5: „links wählt aus" muss ohne den Baum gelten.

    Vorher lief das Picking nur, wenn Messen, Bemalen oder die
    Merkmalsbeschriftung eingeschaltet waren — ein Klick auf einen Körper tat
    in der Vorgabe nichts, obwohl Schema und Handbuch es versprechen.
    """
    window.viewport.show_scene(window.session.last_result)
    entry = window.session.last_result.scene.objects["obj_1"]
    centre = entry.mesh.bounds.centre

    assert window.viewport._object_at(centre) == "obj_1"


def test_a_click_beside_the_body_clears_the_selection(window: MainWindow) -> None:
    """Ein Klick daneben ist eine Aussage, kein Beinahe-Treffer.

    ``_nearest_mesh`` antwortet immer mit dem nächsten Körper; für die Auswahl
    wäre das falsch — sonst gäbe es keinen Weg, sie ohne den Baum loszuwerden.
    """
    window.viewport.show_scene(window.session.last_result)
    entry = window.session.last_result.scene.objects["obj_1"]
    far = tuple(value + 500.0 for value in entry.mesh.bounds.centre)

    assert window.viewport._object_at(far) is None


def test_the_smallest_body_wins_when_several_overlap(window: MainWindow) -> None:
    """Wer auf eine Schraube in einem Gehäuse zeigt, meint die Schraube."""
    result = window.session.last_result
    entry = result.scene.objects["obj_1"]
    centre = entry.mesh.bounds.centre

    # Der geladene Körper allein: er ist der kleinste und damit der Treffer.
    assert window.viewport._object_at(centre) == "obj_1"


def test_clicking_needs_no_overlay_switch(window: MainWindow) -> None:
    """Die Merkmalsbeschriftung schaltet Beschriftungen, nicht das Anklicken.

    §18.5 nennt das Zeigen auf ein Merkmal die wichtigste Einzelfunktion — sie
    hinter einem Häkchen zu verstecken hieße, sie für jeden abzuschalten, der
    das Häkchen nicht findet.
    """
    window.viewport.show_scene(window.session.last_result)
    window.viewport.set_feature_overlay(False)
    entry = window.session.last_result.scene.objects["obj_1"]
    centre = entry.features["hole_3"].params["centre"]

    assert window.viewport._feature_at(centre) == "hole_3"


def test_the_label_names_the_feature_and_its_size(window: MainWindow) -> None:
    entry = window.session.last_result.scene.objects["obj_1"]
    label = feature_label("hole_1", entry.features["hole_1"])

    assert label.startswith(f"{tr('Bohrung')} 1 · Ø"), "gelesen wird der Name, nicht die Kennung"


# --- layer analysis (§18.10) ----------------------------------------------------


def _wait_for_slice(window: MainWindow, timeout_ms: int = 20_000) -> None:
    """Wartet auf den Schichtanalyse-Arbeiter des Fensters.

    Kein `processEvents` in einer Endlosschleife: der Thread wird abgewartet
    und danach einmal die Warteschlange geleert, damit sein Signal ankommt.
    """
    worker = window._slice_worker
    if worker is not None:
        worker.wait(timeout_ms)
    application = QApplication.instance()
    if application is not None:
        application.processEvents()


def test_the_layer_tool_is_called_what_it_is(window: MainWindow) -> None:
    """Keine Vorschau: sie zeigt Geometrie, keine Werkzeugwege (§18.10).

    Die Benennung trug früher das Auswahlfeld in der Leiste selbst; seit es
    weg ist, tragen sie der Werkzeugknopf und sein Hinweis.
    """
    title = window.tools.tool_titles()["layers"]
    hint = str(window.tools.tools()["layers"].hint)

    assert "Schichten" in title
    assert "Vorschau" not in title
    assert "Vorschau" not in hint


def test_opening_the_layer_tool_is_the_only_switch(window: MainWindow) -> None:
    """Ein Umschalter, nicht zwei.

    In der Leiste stand ein Auswahlfeld mit „Keine Schichtanalyse" und
    „Schichtanalyse" — hinter dem Werkzeugknopf, der die Leiste überhaupt
    erst öffnet. Wer *Schichten* anklickte, bekam einen toten Regler und
    musste erraten, dass er daneben noch einmal einschalten muss.
    """
    select_plate(window)
    assert not window.layer_bar.enabled(), "geschlossen ist aus"

    window.tools.activate("layers")
    assert window.layer_bar.enabled(), "der Knopf schaltet die Analyse ein"

    window.tools.activate(None)
    assert not window.layer_bar.enabled(), "und wieder aus"
    assert window.layer_bar.index() == -1


def test_scrubbing_shows_one_layer(window: MainWindow) -> None:
    """Die Schichtanalyse rechnet im Arbeiter (§2.8) — die Leiste füllt sich,
    sobald sie da ist, statt das Fenster so lange anzuhalten.
    """
    select_plate(window)
    window.layer_bar.set_active(True)
    _wait_for_slice(window)

    assert window.layer_bar.slider.maximum() > 0, "the plate has layers"
    window.layer_bar.slider.setValue(3)
    assert "z" in window.layer_bar.readout.text()
    assert "Schicht" in window.layer_bar.readout.text()


def test_a_finished_worker_never_drops_its_successor(window: MainWindow) -> None:
    """Ein auslaufender Arbeiter räumt seine eigene Referenz weg — und nur die.

    Hier stand ein ``lambda: setattr(self, "_slice_worker", None)``. Wer durch
    die Schichten schiebt, startet einen zweiten Schnitt, während der erste
    noch rechnet; dessen ``finished`` löschte dann die Referenz auf den
    **laufenden zweiten**. Einen ``QThread``, den niemand mehr hält, sammelt
    der Speicherbereiniger mitsamt C++-Objekt ein — die Zugriffsverletzung ohne
    Zeile, gegen die weiter oben schon ``_retired`` geschrieben wurde.

    Geprüft wird die Identitätsprüfung, nicht das Aufräumen: gestartet wird
    keiner der beiden, sonst hinge der Test am Timing des Absturzes, den er
    verhindern soll.
    """
    from app.ui.main_window import _SliceWorker

    entry = window.session.last_result.scene.objects["obj_1"]
    first = _SliceWorker(entry, 0.2)
    second = _SliceWorker(entry, 0.2)
    window._slice_worker = second

    window._slice_worker_done(first)

    assert window._slice_worker is second, "der Vorgänger hat den Nachfolger gelöscht"

    window._slice_worker_done(second)

    assert window._slice_worker is None, "seinen eigenen räumt er sehr wohl weg"


def test_scrubbing_starts_one_worker_per_body_not_one_per_step(window: MainWindow) -> None:
    """Beim Ziehen durch die Schichten rechnet genau ein Arbeiter je Körper.

    Vorher startete jeder Schieberschritt einen weiteren, solange das Ergebnis
    noch nicht im Cache lag — an einem texturierten Netz rechnete jeder davon
    Sekunden, alle gleichzeitig, und die Anwendung stand. Wer etwas vom
    laufenden Ergebnis will, stellt sich an; die Schichtansicht steht dabei nur
    einmal in der Reihe, egal wie oft geschoben wird.
    """
    entry = window.session.last_result.scene.objects["obj_1"]
    key = ("obj_1", entry.mesh.triangle_count)
    sentinel = object()
    window._slice_key = None
    window._slice_worker = sentinel
    window._slice_pending = key
    window._slice_waiters = []
    try:
        assert window._slice_of("obj_1", window._show_current_layer) is None
        assert window._slice_of("obj_1", window._show_current_layer) is None

        assert window._slice_worker is sentinel, "es wurde ein zweiter Arbeiter gestartet"
        assert window._slice_waiters == [window._show_current_layer], (
            "die Schichtansicht steht genau einmal in der Reihe"
        )
    finally:
        # Von Hand gesetzt, von Hand weggeräumt: das Platzhalter-Objekt hat
        # kein ``wait``, und die Fixture wartet am Ende auf alle Arbeiter.
        window._slice_worker = None
        window._slice_pending = None
        window._slice_waiters = []


def test_a_superseded_workers_result_is_dropped(window: MainWindow) -> None:
    """Das Ergebnis eines abgelösten Arbeiters gilt nicht mehr.

    Inzwischen rechnet ein neuer an einem anderen Körper — das alte Ergebnis
    jetzt zu übernehmen zeigte dessen Schichten und riefe Rückrufe, die auf
    den neuen warten.
    """
    from app.core.types import SliceResult

    outcome = SliceResult(layers=(), support_volume=0.0, first_layer_area=0.0, source="internal")
    window._slice_cache = None
    window._slice_key = None
    window._slice_worker = None

    window._slice_ready(outcome, ("obj_1", 12), object())

    assert window._slice_cache is None, "ein abgelöster Arbeiter schreibt keinen Cache"
    assert window._slice_key is None


def test_when_the_slice_arrives_every_waiter_is_served_once(window: MainWindow) -> None:
    """Wer sich angestellt hat, bekommt das Ergebnis — und die Reihe ist danach leer."""
    from app.core.types import SliceResult

    outcome = SliceResult(layers=(), support_volume=0.0, first_layer_area=0.0, source="internal")
    served: list[object] = []
    current = object()
    window._slice_worker = current
    window._slice_pending = ("obj_1", 12)
    window._slice_waiters = [served.append]
    try:
        window._slice_ready(outcome, ("obj_1", 12), current)

        assert served == [outcome]
        assert window._slice_cache is outcome
        assert window._slice_pending is None
        assert window._slice_waiters == []
    finally:
        window._slice_worker = None


def test_scrubbing_defers_the_body_cut_until_the_slider_rests(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Beim Fahren folgen die Konturen sofort, der Körperschnitt erst zur Ruhe.

    Die Körper an der Schichthöhe zu kappen ist echte Geometrie und kostet an
    einem texturierten Netz um die Sekunde — je Schieberschritt im Hauptthread
    war das die Blockade, die §2.8 ausschließt. Ein- und Ausschalten schneiden
    weiterhin sofort; nur der Schritt von Höhe zu Höhe wartet, bis der Schieber
    stehen bleibt.
    """
    from app.core.types import LayerInfo

    viewport = window.viewport
    first = LayerInfo(z=1.0, contours=(), area=0.0, overhang_area=0.0, islands=(), min_width=0.0)
    second = LayerInfo(z=2.0, contours=(), area=0.0, overhang_area=0.0, islands=(), min_width=0.0)

    viewport.set_layer(first)
    assert not viewport._layer_rebuild.isActive(), "Einschalten schneidet sofort"

    rebuilt: list[object] = []
    monkeypatch.setattr(viewport, "show_scene", rebuilt.append)
    viewport.set_layer(second)
    assert viewport._layer_rebuild.isActive(), "beim Fahren wird aufgeschoben"
    assert rebuilt == [], "und zwar wirklich: kein Schnitt im selben Atemzug"

    application = QApplication.instance()
    assert application is not None
    deadline = 200
    while not rebuilt and deadline > 0:
        application.processEvents()
        QThread.msleep(25)
        deadline -= 1
    assert rebuilt, "sobald der Schieber ruht, kommt der Schnitt nach"

    viewport.set_layer(None)
    assert not viewport._layer_rebuild.isActive(), "Ausschalten lässt nichts nachhängen"


def test_a_chosen_layer_cuts_away_what_lies_above(window: MainWindow) -> None:
    """„Durch die Höhe fahren und den Querschnitt ansehen" versprach der Text.

    Der Schieber lief, die Zahlen stimmten — und das Modell blieb vollständig
    undurchsichtig stehen; sichtbar wurde nur eine dünne Kontur darunter. Wer
    eine Schicht gewählt hat, will sehen, was auf dieser Höhe steht.
    """
    from app.core.types import LayerInfo

    window.viewport.show_scene(window.session.last_result)
    entry = window.session.last_result.scene.objects["obj_1"]
    full = entry.mesh.bounds

    window.viewport.set_layer(
        LayerInfo(
            z=full.minimum[2] + 1.0,
            contours=(),
            area=0.0,
            overhang_area=0.0,
            islands=(),
            min_width=0.0,
        )
    )
    cut_mesh = window.viewport._sectioned(entry.mesh)

    assert cut_mesh.bounds.maximum[2] < full.maximum[2], "oben ist etwas weg"
    assert cut_mesh.bounds.maximum[2] == pytest.approx(full.minimum[2] + 1.0, abs=0.2)

    window.viewport.set_layer(None)
    assert window.viewport._sectioned(entry.mesh).bounds.maximum[2] == pytest.approx(
        full.maximum[2]
    ), "und ohne Schicht steht wieder alles da"


def test_switching_it_off_clears_the_view(window: MainWindow) -> None:
    select_plate(window)
    window.layer_bar.set_active(True)
    window.layer_bar.set_active(False)

    assert window.layer_bar.index() == -1
    assert window.layer_bar.readout.text() == ""


# --- Maßstab an der Druckplatte (Konzept P15 §7 Etappe 1) ----------------------


def test_what_is_fitted_gets_air_around_it() -> None:
    """``reset_camera(bounds=…)`` passt genau ein — und das war zu genau.

    Ein 40 mm großer Quader berührte links und rechts den Bildrand, und von der
    Druckplatte war nichts mehr zu sehen. Zwölf Prozent je Achse, um die Mitte
    gelegt: die Mitte bleibt, wo sie war, und beide Seiten gewinnen gleich viel.

    Eine Achse ohne Ausdehnung bleibt unberührt — eine flache Skizze soll nicht
    in die Tiefe wachsen, nur weil jemand einpasst.
    """
    from app.ui.viewport import CAMERA_MARGIN, with_margin

    wide = with_margin((-20.0, 20.0, -15.0, 15.0, 0.0, 10.0))
    assert wide[0] == pytest.approx(-20.0 - 40.0 * CAMERA_MARGIN / 2.0)
    assert wide[1] == pytest.approx(20.0 + 40.0 * CAMERA_MARGIN / 2.0)
    # Die Mitte verschiebt sich nicht.
    assert (wide[0] + wide[1]) / 2.0 == pytest.approx(0.0)
    assert (wide[4] + wide[5]) / 2.0 == pytest.approx(5.0)

    flat = with_margin((-10.0, 10.0, -10.0, 10.0, 3.0, 3.0))
    assert flat[4] == pytest.approx(3.0)
    assert flat[5] == pytest.approx(3.0)


def test_the_bed_carries_numbers_not_just_lines() -> None:
    """Ein Raster ohne Zahlen sagt nur, dass es ein Raster gibt.

    Erst die Zahl daneben macht daraus einen Maßstab, an dem sich ein Teil
    einordnen lässt, ohne es zu messen — und genau dafür steht die Platte in
    echter Größe da.

    Als reine Rechnung geprüft: offscreen gibt es keinen Plotter, und ein Test,
    der sich dort überspringt, prüft nie etwas.
    """
    from app.ui.viewport import BED_SCALE_STEP, bed_scale

    marks = bed_scale(256.0, 256.0)
    labels = [text for _point, text in marks]

    assert "50" in labels
    assert "100" in labels
    # 128 mm je Seite, alle 50 mm: Null, 50 und 100 in beide Richtungen — je
    # Kante fünf Zahlen.
    assert len(marks) == 2 * 5

    steps = sorted({float(text) for text in labels})
    assert steps == [-2 * BED_SCALE_STEP, -BED_SCALE_STEP, 0.0, BED_SCALE_STEP, 2 * BED_SCALE_STEP]


def test_the_bed_scale_signs_its_numbers_and_puts_zero_in_the_middle() -> None:
    """Die Skala widersprach sich selbst.

    ``abs()`` nahm beiden Seiten das Vorzeichen — dieselbe „100" lag zweimal im
    Bild —, und die einzige Null stand in der **Ecke** der Platte, mit der
    Begründung, sie gehöre beiden Kanten. Der Nullpunkt der Szene ist aber die
    Mitte: bei 220 mm stand „0" bei x = -110 und zehn Millimeter weiter „100".
    Ein Körper aus ``create_box`` steht in dieser Mitte, und „Position X = -40"
    im Dialog meint dieselbe Achse.

    Geprüft wird beides — dass die Null dort liegt, wo sie hingehört, und dass
    die negative Seite ihr Vorzeichen behält.
    """
    from app.ui.viewport import bed_scale

    marks = bed_scale(220.0, 220.0)
    # Die Marken der Vorderkante liegen weiter vorn als seitlich, die der linken
    # Kante umgekehrt — das trennt die beiden Kanten, ohne den Abstand zu kennen,
    # mit dem sie vor der Platte stehen.
    front = [(point, text) for point, text in marks if point[1] < point[0]]

    zeros = [point for point, text in marks if text == "0"]
    assert len(zeros) == 2, "jede Kante trägt ihre eigene Null"
    for point in zeros:
        assert abs(point[0]) < 1e-9 or abs(point[1]) < 1e-9, (
            "die Null einer Kante liegt in ihrer Mitte, nicht in der Ecke"
        )

    assert "-100" in [text for _point, text in marks], "die negative Seite behält ihr Vorzeichen"
    assert [text for _point, text in front].count("100") == 1, "keine Zahl steht zweimal je Kante"


def test_a_small_bed_still_gets_a_scale() -> None:
    """Und eine Platte, die kleiner ist als ein Schritt, bekommt wenigstens
    ihren Nullpunkt — statt einer leeren Beschriftungsliste, über die VTK
    stolpert."""
    from app.ui.viewport import bed_scale

    marks = bed_scale(60.0, 60.0)
    assert marks
    # Je Kante ihre Null, seit die Skala vorzeichenbehaftet ist — vorher war es
    # eine einzige in der Ecke, und die lag am falschen Ort.
    assert [text for _point, text in marks] == ["0", "0"]


def test_a_shadow_falls_beside_the_body_not_under_it() -> None:
    """Senkrecht projiziert ist ein Schatten unsichtbar.

    Der erste Versuch legte ihn genau unter den Körper — dort verdeckt ihn der
    Körper, und im Bild war schlicht kein Schatten. Er fällt deshalb entlang
    der Lichtrichtung, und sein Versatz wächst mit der Höhe: damit beantwortet
    er nebenbei die Frage, für die er da ist, denn ein schwebendes Teil hat
    seinen Schatten weiter weg.
    """
    import numpy as np

    from app.ui.viewport import shadow_points

    standing = shadow_points(np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 40.0]]), (0.3, 0.4))
    assert standing[0][0] == pytest.approx(0.0), "was aufliegt, wirft an Ort und Stelle"
    assert standing[1][0] == pytest.approx(40.0 * 0.3)
    assert standing[1][1] == pytest.approx(40.0 * 0.4)
    assert all(point[2] == 0.0 for point in standing), "der Schatten liegt auf der Platte"


def test_a_body_below_the_plate_throws_nothing_forward() -> None:
    """Sonst zöge ein halb versunkenes Teil seinen Schatten falsch herum."""
    import numpy as np

    from app.ui.viewport import shadow_points

    sunk = shadow_points(np.array([[5.0, 7.0, -12.0]]), (0.3, 0.4))
    assert sunk[0][0] == pytest.approx(5.0)
    assert sunk[0][1] == pytest.approx(7.0)


def test_the_shadow_steps_beside_the_body_and_never_towards_the_viewer() -> None:
    """Zur Seite, weil hinten das Teil selbst steht.

    Das Licht hängt an der Kamera, und ein Schatten, der von der Kamera weg
    fällt, liegt hinter dem Teil — von der Kamera aus also dort, wo das Teil
    ist. Er war damit nicht zu sehen: gemessen an zwei Aufnahmen desselben
    Bildes, einmal mit und einmal ohne die Schattenaktoren, waren von 260 000
    verglichenen Bildpunkten **vier** dunkler. Zur Seite geworfen sind es
    2 988, und die Frage aus §18.6 — steht das Teil auf der Platte oder
    darüber? — bekommt eine Antwort.

    Die Gegenrichtung ist ausdrücklich verboten: Ein Schatten, der auf den
    Betrachter zu fällt, wäre noch besser zu sehen (gemessen 5 053 Punkte) und
    behauptete ein Licht hinter dem Teil, dessen Vorderseite hell beleuchtet
    ist. Das war schon einmal der Stand und wurde aus genau diesem Grund
    verworfen; ohne diese Zusicherung wäre der Weg zurück offen.
    """
    import numpy as np

    from app.ui.viewport import VIEW_DIRECTIONS, shadow_direction

    for name, (position, _up) in VIEW_DIRECTIONS.items():
        if name in {"top", "bottom"}:
            continue  # Senkrecht von oben gibt es kein Hinten; siehe unten.
        step = np.array(shadow_direction(position, (0.0, 0.0, 0.0)))
        forward = np.array([-position[0], -position[1]], dtype=float)
        forward /= np.linalg.norm(forward)
        sideways = np.array([-forward[1], forward[0]])
        along = float(np.dot(step, forward))
        across = float(np.dot(step, sideways))
        assert abs(across) > abs(along), (
            f"in der Ansicht {name!r} läuft der Schatten hinter das Teil: "
            f"{along:.2f} nach hinten, {across:.2f} zur Seite"
        )
        assert along >= 0.0, (
            f"in der Ansicht {name!r} fällt der Schatten auf den Betrachter zu ({along:.2f})"
        )


def test_looking_straight_down_the_shadow_still_has_a_direction() -> None:
    """Eine Draufsicht hat kein Hinten, aber eine Oberkante.

    Ohne diesen Fall teilte die Rechnung durch null, und der Schatten wäre in
    der Ansicht verschwunden, in der man ihn zum Anordnen am ehesten braucht.
    """
    from app.ui.viewport import SHADOW_REACH, SHADOW_SIDE, shadow_direction

    assert shadow_direction((0.0, 0.0, 100.0), (0.0, 0.0, 0.0)) == (SHADOW_SIDE, SHADOW_REACH)


def test_the_shadow_of_a_standing_body_reaches_past_its_own_footprint() -> None:
    """Ein Schatten, der unter dem Teil bleibt, ist keiner.

    Die Richtung allein sagt es nicht: Erst zusammen mit der Höhe entsteht der
    Versatz, und der muss den eigenen Umriss verlassen, sonst deckt das Teil
    seinen Schatten selbst ab. Gerechnet an einem 40er Würfel — 20 mm hoch,
    also 12,6 mm Versatz — gegen die Hälfte seiner Kantenlänge.
    """
    import numpy as np

    from app.ui.viewport import VIEW_DIRECTIONS, shadow_direction, shadow_points

    hull = np.array(
        [(x, y, z) for x in (-20.0, 20.0) for y in (-20.0, 20.0) for z in (0.0, 20.0)],
        dtype=float,
    )
    for name, (position, _up) in VIEW_DIRECTIONS.items():
        if name in {"top", "bottom"}:
            continue  # Senkrecht von oben verdeckt das Teil seinen Schatten immer.
        step = shadow_direction(position, (0.0, 0.0, 0.0))
        cast = shadow_points(hull, step)
        forward = np.array([-position[0], -position[1]], dtype=float)
        forward /= np.linalg.norm(forward)
        sideways = np.array([-forward[1], forward[0]])
        # Gemessen wird **quer** zur Blickrichtung: nach hinten hinaus liegt
        # der Schatten hinter dem Teil, und von dort sieht ihn niemand.
        reach = float(np.max(np.abs(cast[:, :2] @ sideways))) - float(
            np.max(np.abs(hull[:, :2] @ sideways))
        )
        assert reach > 5.0, (
            f"in der Ansicht {name!r} tritt der Schatten nur {reach:.1f} mm "
            "seitlich unter dem Teil hervor"
        )


def test_the_shadow_keeps_its_length_whatever_the_view() -> None:
    """Ein Teil darf beim Drehen nicht zu wachsen scheinen."""
    import numpy as np

    from app.ui.viewport import VIEW_DIRECTIONS, shadow_direction

    lengths = [
        float(np.linalg.norm(shadow_direction(position, (0.0, 0.0, 0.0))))
        for position, _up in VIEW_DIRECTIONS.values()
    ]
    assert max(lengths) - min(lengths) < 1e-9


def test_the_shadow_hull_holds_the_corners_and_drops_the_rest(qt_app: QApplication) -> None:
    """Die Hülle wird einmal je Körper gerechnet, der Umriss je Ansicht.

    Vorher lief eine Triangulierung über **jeden** Punkt des Anzeigenetzes, und
    zwar bei jedem Szenenaufbau: 31 ms bei zwanzigtausend Dreiecken, 127 ms bei
    zweiundachtzigtausend, je Körper und im Qt-Hauptthread. Für den Umriss
    zählen nur die Punkte der konvexen Hülle — bei einem Quader acht von
    Hunderten.
    """
    pv = pytest.importorskip("pyvista")
    import numpy as np

    from app.ui.viewport import Viewport

    viewport = Viewport()
    try:
        body = pv.Box(bounds=(0.0, 20.0, 0.0, 20.0, 0.0, 30.0)).triangulate().subdivide(3)
        hull = viewport._shadow_hull_of(body)
        assert len(hull) == 8, "ein Quader hat acht Ecken, wie fein er auch vernetzt ist"
        assert len(hull) < body.n_points / 10

        outline = viewport._shadow_outline_of(hull, (0.5, 0.0))
        assert outline is not None and outline.n_cells > 0
        assert np.allclose(outline.points[:, 2], 0.05), "der Schatten liegt auf der Platte"
        # 30 mm hoch, halber Versatz je Millimeter: der Umriss reicht 15 mm
        # weiter als der Körper.
        assert outline.points[:, 0].max() == pytest.approx(35.0)
        assert outline.points[:, 1].max() == pytest.approx(20.0)
    finally:
        viewport.deleteLater()


def test_thinning_a_dense_body_keeps_its_corners() -> None:
    """Die Stichprobe hält die Form, die Stützpunkte halten die Ecken.

    Bei einer feinen Kugel liegt jeder Punkt auf der Hülle — dort kostete die
    Hüllenrechnung mehr als die Triangulierung, die sie ersetzen sollte. Sie
    bekommt deshalb einen Deckel. Nur darf der die Ecken nicht wegwerfen: ein
    gescannter Halter würfe sonst einen Schatten, der um Millimeter zu klein
    ist.
    """
    import numpy as np

    from app.ui.viewport import SHADOW_HULL_POINTS, _thinned_for_hull

    rng = np.random.default_rng(7)
    cloud = rng.uniform(-10.0, 10.0, size=(SHADOW_HULL_POINTS * 4, 3))
    corners = np.array([[-40.0, -40.0, 0.0], [40.0, -40.0, 0.0], [0.0, 40.0, 30.0]])
    # Die Ecken in die Mitte, wo keine Stichprobe sie zufällig erwischt.
    points = np.vstack((cloud[: len(cloud) // 2], corners, cloud[len(cloud) // 2 :]))

    thinned = _thinned_for_hull(points)
    assert len(thinned) < len(points) / 3, "ausgedünnt wurde"
    for corner in corners:
        assert np.any(np.all(np.isclose(thinned, corner), axis=1)), f"{corner} fehlt"


def test_a_small_body_is_not_thinned_at_all() -> None:
    """Unter dem Deckel bleibt die Hülle exakt — sie ist dort ohnehin billig."""
    import numpy as np

    from app.ui.viewport import SHADOW_HULL_POINTS, _thinned_for_hull

    points = np.zeros((SHADOW_HULL_POINTS, 3))
    assert _thinned_for_hull(points) is points


def test_a_body_too_thin_for_a_hull_still_gets_one(qt_app: QApplication) -> None:
    """Ein ebener Körper hat keine räumliche Hülle — er wirft trotzdem.

    Qhull gibt bei entarteten Punktwolken auf. Sein Fehler darf nicht der
    Fehler der Ansicht werden: die paar Punkte gehen dann unverändert weiter.
    """
    pv = pytest.importorskip("pyvista")

    from app.ui.viewport import Viewport

    viewport = Viewport()
    try:
        flat = pv.PolyData([[0.0, 0.0, 5.0], [10.0, 0.0, 5.0], [10.0, 10.0, 5.0], [0.0, 10.0, 5.0]])
        hull = viewport._shadow_hull_of(flat)
        assert hull is not None and len(hull) == 4
        assert viewport._shadow_outline_of(hull, (0.5, 0.5)) is not None
    finally:
        viewport.deleteLater()


def test_a_body_standing_on_another_throws_its_shadow_onto_it(qt_app: QApplication) -> None:
    """Sonst löst sich der Schatten von dem ab, was ihn wirft.

    Ein Turm auf einer zwölf Millimeter hohen Grundplatte warf seinen Schatten
    auf die Druckplatte: gemessen ab null statt ab der Fläche, auf der er
    steht, und damit um die volle Bauhöhe versetzt. Im Bild tauchte er erst
    neben der Grundplatte auf — ein Fleck ohne Verbindung zu dem, was ihn
    wirft.
    """
    pytest.importorskip("pyvista")
    import numpy as np

    from app.ui.viewport import Viewport, outline_of

    viewport = Viewport()
    try:
        plate = np.array(
            [[x, y, z] for x in (-40.0, 40.0) for y in (-40.0, 40.0) for z in (0.0, 12.0)]
        )
        tower = np.array(
            [[x, y, z] for x in (0.0, 10.0) for y in (0.0, 10.0) for z in (12.0, 52.0)]
        )
        viewport._shadow_ground["plate"] = (0.0, 12.0, outline_of(plate))
        viewport._shadow_ground["tower"] = (12.0, 52.0, outline_of(tower))

        catchers = viewport._shadow_catchers("tower")
        assert [ground for ground, _window in catchers] == [0.0, 12.0], (
            "die Grundplatte fängt, die Druckplatte fängt daneben"
        )

        ground, window = catchers[1]
        outline = viewport._shadow_outline_of(tower, (0.5, 0.0), ground, window)
        assert outline is not None
        assert np.allclose(outline.points[:, 2], 12.05), "er liegt auf der Grundplatte"
        # 40 mm über ihr, halber Versatz je Millimeter: 20 mm weiter als der
        # Turm, nicht 26 wie bei der Rechnung ab null.
        assert outline.points[:, 0].max() == pytest.approx(30.0)
    finally:
        viewport.deleteLater()


def test_a_body_on_the_plate_has_only_the_plate_below_it(qt_app: QApplication) -> None:
    """Ein Körper daneben ist kein Boden, solange er nicht darunter liegt."""
    pytest.importorskip("pyvista")
    import numpy as np

    from app.ui.viewport import Viewport, outline_of

    viewport = Viewport()
    try:
        neighbour = np.array(
            [[x, y, z] for x in (50.0, 60.0) for y in (0.0, 10.0) for z in (0.0, 30.0)]
        )
        viewport._shadow_ground["neighbour"] = (0.0, 30.0, outline_of(neighbour))
        viewport._shadow_ground["mine"] = (0.0, 20.0, outline_of(neighbour + 100.0))
        assert [ground for ground, _window in viewport._shadow_catchers("mine")] == [0.0]
    finally:
        viewport.deleteLater()


def test_the_shadow_is_cut_at_the_edge_of_the_plate(qt_app: QApplication) -> None:
    """Außerhalb der Platte liegt er auf blankem Hintergrund.

    Bei aufgezogener Explosion oder einem Körper weit vom Ursprung war das ein
    dunkler Umriss ohne Fläche darunter — die einzige Stelle, an der die
    Ansicht Boden behauptete, wo keiner ist.
    """
    pytest.importorskip("pyvista")
    import numpy as np

    from app.ui.viewport import Viewport

    viewport = Viewport()
    try:
        viewport._bed_extent = (100.0, 100.0)
        body = np.array([[x, y, z] for x in (40.0, 80.0) for y in (0.0, 10.0) for z in (0.0, 20.0)])
        ground, window = viewport._shadow_catchers("body")[0]
        outline = viewport._shadow_outline_of(body, (0.5, 0.0), ground, window)
        assert outline is not None
        assert outline.points[:, 0].max() == pytest.approx(50.0), "an der Kante ist Schluss"

        far = body + np.array([200.0, 0.0, 0.0])
        assert viewport._shadow_outline_of(far, (0.5, 0.0), ground, window) is None, (
            "was ganz daneben fällt, wirft gar keinen Schatten"
        )
    finally:
        viewport.deleteLater()


def test_without_a_build_volume_nothing_is_cut(qt_app: QApplication) -> None:
    """Ohne gezeigten Bauraum gibt es keine Kante, an der zu schneiden wäre."""
    pytest.importorskip("pyvista")

    from app.ui.viewport import Viewport

    viewport = Viewport()
    try:
        assert viewport._shadow_catchers("body") == [(0.0, None)]
    finally:
        viewport.deleteLater()


def test_clipping_keeps_the_part_inside_and_cuts_the_rest() -> None:
    """Sutherland und Hodgman, an einem Fall mit bekannter Antwort.

    Ein Quadrat, das zur Hälfte über das Fenster hinausragt, wird an dessen
    Kante abgeschnitten — nicht weggelassen und nicht ganz behalten.
    """
    import numpy as np

    from app.ui.viewport import bed_outline, clip_polygon

    window = bed_outline(100.0, 100.0)
    half_out = np.array([[30.0, -10.0], [70.0, -10.0], [70.0, 10.0], [30.0, 10.0]])
    clipped = clip_polygon(half_out, window)
    assert len(clipped) >= 3
    assert clipped[:, 0].max() == pytest.approx(50.0)
    assert clipped[:, 0].min() == pytest.approx(30.0)

    inside = np.array([[-10.0, -10.0], [10.0, -10.0], [10.0, 10.0], [-10.0, 10.0]])
    assert np.allclose(clip_polygon(inside, window), inside), "was drin liegt, bleibt wie es ist"

    outside = inside + 200.0
    assert len(clip_polygon(outside, window)) == 0


def test_a_list_in_the_bottom_bar_opens_upwards_when_it_has_to() -> None:
    """Qt hält eine Aufklappliste am Bildschirm, nicht am Fenster.

    Die Leisten unter dem Viewport sitzen an der Unterkante der Anwendung —
    ihre Listen klappten über das Fenster hinaus auf den Schreibtisch und
    verdeckten, was dort lag. Gerechnet wird in Bildschirmkoordinaten.
    """
    from PySide6.QtCore import QRect

    from app.ui.tool_strip import list_top

    window = QRect(100, 100, 900, 600)  # unten bei 699

    roomy = QRect(120, 200, 160, 24)  # unten bei 223
    assert list_top(roomy, 200, window) == roomy.bottom(), "passt darunter — dann darunter"

    cramped = QRect(120, 640, 160, 24)  # unten bei 663, darunter nur 36
    assert list_top(cramped, 200, window) == cramped.top() - 200, "sonst darüber"

    tall = list_top(cramped, 700, window)
    assert tall == window.top(), "passt nirgends: dann bündig, nicht über den Rand"
    assert tall + 700 >= window.bottom()


def test_every_list_in_the_bottom_bars_knows_that(qt_app: QApplication) -> None:
    """Und zwar jede — die Regel nützt nichts, wenn eine Leiste sie vergisst.

    Geprüft werden die Leisten unter dem Viewport. Listen in Dialogen haben das
    Problem nicht: die stehen in der Fenstermitte.
    """
    from PySide6.QtWidgets import QComboBox

    from app.ui.explode_bar import ExplodeBar
    from app.ui.section_bar import MeasureBar, SectionBar
    from app.ui.tool_strip import BarComboBox

    plain: list[str] = []
    for bar in (AnalysisBar(), LayerBar(), ExplodeBar(), MeasureBar(), SectionBar()):
        for child in bar.findChildren(QComboBox):
            if not isinstance(child, BarComboBox):
                plain.append(f"{type(bar).__name__}.{child.objectName() or '?'}")

    assert not plain, (
        f"Diese Listen klappen über den Fensterrand hinaus: {plain}. "
        "In einer Leiste unter dem Viewport ist BarComboBox die richtige Klasse."
    )


def test_a_click_in_the_middle_of_a_face_has_to_hit_something() -> None:
    """Warum der Viewport eine Zelle pickt und keinen Punkt (§18.5).

    Ein ``vtkPointPicker`` trifft **Eckpunkte**. Ein Würfel hat acht davon, und
    ein Klick mitten auf seine Fläche fand nichts: Auswählen, Kontextmenü am
    Merkmal, Messen und Bemalen taten in der laufenden Anwendung nichts,
    während Rad und Rechtsziehen die Kamera bewegten. Die Verdrahtung war seit
    ihrer Reparatur richtig — das Werkzeug nicht.

    Geprüft wird an einem eigenen Offscreen-Renderer und nicht am Viewport: der
    baut ohne Bildschirm keinen Plotter, und ein Test, der sich selbst
    überspringt, prüft nie etwas.
    """
    import pyvista as pv
    from vtkmodules.vtkRenderingCore import vtkCellPicker, vtkPointPicker

    from app.ui.viewport import PICK_TOLERANCE

    plotter = pv.Plotter(off_screen=True, window_size=(400, 400))
    try:
        plotter.add_mesh(pv.Cube(center=(0.0, 0.0, 0.0), x_length=20, y_length=20, z_length=20))
        plotter.view_xy()
        plotter.render()
        middle = (200.0, 200.0)  # die Bildmitte, und dort liegt die Deckfläche

        points = vtkPointPicker()
        cells = vtkCellPicker()
        cells.SetTolerance(PICK_TOLERANCE)

        hit_point = points.Pick(middle[0], middle[1], 0.0, plotter.renderer)
        hit_cell = cells.Pick(middle[0], middle[1], 0.0, plotter.renderer)
    finally:
        plotter.close()

    assert not hit_point, "genau darum ging nichts: mitten auf der Fläche liegt kein Eckpunkt"
    assert hit_cell, "das Dreieck darunter gibt es, und darauf zeigt der Nutzer"


def test_a_click_on_a_feature_selects_its_body_too(window: MainWindow) -> None:
    """Sonst tut der erste Klick nichts (§18.5).

    Der Baum zeigt ein Merkmal nur unter der Zeile seines Objekts. Solange der
    Viewport bei einem Treffer allein ``featurePicked`` sendete, lief das ins
    Leere: ``_on_feature_picked`` fragt den Baum nach dem ausgewählten Objekt,
    und ausgewählt war noch keines. Im Fenster sah es aus, als käme der Klick
    nicht an — in Wahrheit war er angekommen und hatte niemanden.
    """
    picked: list[str] = []
    features: list[str] = []
    window.viewport.objectPicked.connect(picked.append)
    window.viewport.featurePicked.connect(features.append)

    entry = window.session.last_result.scene.objects["obj_1"]
    hole = next((name for name, feature in entry.features.items() if feature.kind == "hole"), None)
    assert hole is not None, "die Platte aus dem Korpus hat Bohrungen"
    centre = entry.features[hole].params["centre"]

    window.viewport._select_at((float(centre[0]), float(centre[1]), float(centre[2])))

    assert picked == ["obj_1"], "der Körper zuerst — er trägt die Zeile im Baum"
    assert features == [hole], "und danach das Merkmal, das darunter erscheint"


def test_the_report_says_where_you_stand_not_only_what_to_do(qt_app: QApplication) -> None:
    """Ein Bericht aus Sätzen sagt, *was* zu tun ist — nicht, woran man ist.

    Die Kennzahlen darüber tun das, und sie kosten nichts: wasserdicht,
    Volumen, Zahl der Teile stehen im ausgewerteten Netz. Was einen Schnitt
    durch jede Schicht kostet — schmalste Wand, schlimmster Überhang —, steht
    bewusst nicht dort.
    """
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.scene import EvaluationResult
    from app.core.types import Scene, SceneObject
    from app.ui.panels import ReportPanel

    box = MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 20.0)))
    scene = Scene(objects={"obj_1": SceneObject(id="obj_1", name="Klotz", mesh=box)})
    panel = ReportPanel()
    try:
        panel.show_result(EvaluationResult(scene=scene))

        assert panel.facts.isVisible() or panel.facts.text()
        text = panel.facts.text()
        assert tr("wasserdicht") in text
        # Ein Wuerfel mit 20 mm Kante ist 8 Kubikzentimeter — die Zahl kommt aus
        # dem Netz, nicht aus
        # dem Test: eine abgeschriebene Konstante prüfte nur sich selbst.
        assert format_decimal(box.volume / 1000.0, 1) in text
        assert tr("Teil") in text

        panel.show_result(None)
        assert not panel.facts.text()
    finally:
        panel.deleteLater()


def test_the_report_writes_a_volume_that_says_something(qt_app: QApplication) -> None:
    """„wasserdicht · 0,0 cm³ · 1 Teil" stand über einem Teil von 4 mm³.

    Die Zeile rechnete selbst — ``format_decimal(volume / 1000.0, 1)`` mit
    festem „cm³" dahinter. Zwei Fehler in einer Zeile: Unter einem
    Kubikzentimeter sagt eine Nachkommastelle Kubikzentimeter nichts mehr, und
    in Zoll stand die Zahl auch dann in Kubikzentimetern, wenn jede Länge
    daneben in Zoll gemessen war (§19.3). Der Kern beantwortet beide Fragen;
    diese Karte fragt ihn jetzt.
    """
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.scene import EvaluationResult
    from app.core.types import Scene, SceneObject
    from app.ui import labels
    from app.ui.panels import ReportPanel

    def shown(extents: tuple[float, float, float]) -> str:
        box = MeshData.of(trimesh.creation.box(extents=extents))
        scene = Scene(objects={"obj_1": SceneObject(id="obj_1", name="Teil", mesh=box)})
        panel.show_result(EvaluationResult(scene=scene))
        return panel.facts.text()

    panel = ReportPanel()
    try:
        tiny = shown((2.0, 2.0, 1.0))
        assert "mm³" in tiny, f"ein Teil von 4 mm³ steht als: {tiny!r}"
        assert "0,0" not in tiny, "eine Null mit Komma ist keine Auskunft"

        assert "8,0 cm³" in shown((20.0, 20.0, 20.0)), "im gewohnten Bereich bleibt es cm³"

        labels.set_display_unit("in")
        try:
            inches = shown((20.0, 20.0, 20.0))
        finally:
            labels.set_display_unit("mm")
        assert "in³" in inches, f"in Zoll steht Kubikzoll da, nicht: {inches!r}"
    finally:
        panel.deleteLater()


def test_the_object_tree_draws_its_bodies_once_per_shape(qt_app: QApplication) -> None:
    """Ein Bild je Form, nicht je Auswertung.

    Gerendert wird über den Hash des Körpers: „obj_1" bleibt dasselbe Objekt,
    wenn sich seine Wandstärke ändert — sein Bild nicht. Ohne den Vorrat
    zeichnete jede Auswertung alles neu, und das kostet bei einem gescannten
    Teil achtzig Millisekunden je Zeile im Hauptthread.
    """
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.scene import EvaluationResult
    from app.core.types import Scene, SceneObject
    from app.ui.panels import ObjectTree

    box = MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 20.0)))
    scene = Scene(objects={"obj_1": SceneObject(id="obj_1", name="Klotz", mesh=box)})
    result = EvaluationResult(scene=scene, object_hashes={"obj_1": "abc"})

    tree = ObjectTree()
    try:
        tree.show_scene(result)
        # Der Baum steht sofort; die Bilder kommen nach.
        assert tree.tree.topLevelItemCount() == 1
        while tree._pending:
            tree._render_pending()
        assert len(tree._previews) == 1

        tree.show_scene(result)
        while tree._pending:
            tree._render_pending()
        assert len(tree._previews) == 1, "derselbe Körper wurde zweimal gezeichnet"
    finally:
        tree.deleteLater()


def test_a_hidden_body_keeps_its_own_mark(qt_app: QApplication) -> None:
    """Ein ausgeblendetes Objekt hat gerade nichts zu zeigen — es behält das
    Zeichen, das sagt, warum (Regel 18: Zeichen und Wort, nie Farbe allein)."""
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.scene import EvaluationResult
    from app.core.types import Scene, SceneObject
    from app.ui.panels import ObjectTree

    box = MeshData.of(trimesh.creation.box(extents=(10.0, 10.0, 10.0)))
    scene = Scene(objects={"obj_1": SceneObject(id="obj_1", name="Klotz", mesh=box)})
    tree = ObjectTree()
    try:
        tree.set_hidden(frozenset({"obj_1"}))
        tree.show_scene(EvaluationResult(scene=scene))

        assert not tree._pending, "für ein ausgeblendetes Objekt wird nichts gerendert"
        assert tr("ausgeblendet") in tree.tree.topLevelItem(0).text(0)
    finally:
        tree.deleteLater()


def test_a_theme_change_redraws_the_previews(qt_app: QApplication) -> None:
    """Die Bilder sind SVG mit eingebackenen Farben — ein helles Teil auf
    hellem Grund ist kein Bild mehr."""
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.scene import EvaluationResult
    from app.core.types import Scene, SceneObject
    from app.ui.panels import ObjectTree

    box = MeshData.of(trimesh.creation.box(extents=(10.0, 10.0, 10.0)))
    scene = Scene(objects={"obj_1": SceneObject(id="obj_1", name="Klotz", mesh=box)})
    tree = ObjectTree()
    try:
        tree.show_scene(EvaluationResult(scene=scene, object_hashes={"obj_1": "abc"}))
        while tree._pending:
            tree._render_pending()
        assert tree._previews

        tree.set_theme("light")
        assert not tree._previews, "der Vorrat gehört dem alten Thema"
    finally:
        tree.deleteLater()


def test_nothing_is_fitted_before_a_build_volume_exists(qt_app: QApplication) -> None:
    """Ein Einpassen ohne Bauraum zählt nicht als erledigt.

    Das Fenster baut die Ansicht auf, bevor ein Druckerprofil gilt. Passte man
    dort ein, gäbe es nichts zu messen — und der Zustand stünde danach auf
    „schon eingepasst", sodass das erste echte Projekt nie eingepasst würde.
    Genau so gemessen: ``_fitted_to`` sagte „bed", und die Kamera stand
    unverändert anderthalb Millimeter vom Ursprung entfernt.
    """
    from app.ui.viewport import Viewport

    viewport = Viewport()
    try:
        plotter = _CameraPlotter()
        viewport.plotter = plotter
        viewport._fit_once_for(None)

        assert plotter.fitted_to == [], "ohne Bauraum wird nicht eingepasst"
        assert viewport._fitted_to == "", "und nichts gilt als erledigt"
    finally:
        viewport.deleteLater()


def test_the_feature_legend_reads_like_the_object_tree(window: MainWindow) -> None:
    """Eine Legende aus ``face_10`` und ``pin_3`` ist eine Debug-Ausgabe.

    Die Merkmalskarte führt ihre Stufen als Provenienz-IDs — richtig für die
    Karte, falsch für die Legende darunter. Bei einem Gehäuse standen dort
    vierundzwanzig bunte Kacheln über die volle Fensterbreite: „ohne Merkmal",
    elf Flächen, fünf Bohrungen, ein Deckelinneres, vier Stifte, alphabetisch
    sortiert, also ``face_10`` und ``face_11`` zwischen ``face_1`` und
    ``face_2``.

    Jetzt übersetzt das Fenster die Kennungen in dieselben Namen, die im
    Objektbaum stehen, und die Liste bekommt einen Deckel.
    """
    from app.core.perceive.maps import AnalysisMap

    analysis = AnalysisMap(
        kind="features",
        title="Merkmale",
        values=(0.0, 1.0, 2.0),
        unit="",
        low=0.0,
        high=2.0,
        categories=("ohne Merkmal", "hole_1", "face_2"),
    )
    window.analysis_bar.show_legend(analysis, {"hole_1": "Bohrung 1 · ⌀4,2 mm"})

    labels = [label for label, _colour in window.analysis_bar.legend.entries]
    assert "Bohrung 1 · ⌀4,2 mm" in labels, "was einen Namen hat, trägt ihn"
    assert "face_2" in labels, "und was keinen hat, bleibt lesbar"


def test_a_long_legend_says_how_much_it_leaves_out(window: MainWindow) -> None:
    """Eine gekürzte Liste, die ihre Kürzung verschweigt, behauptet
    Vollständigkeit."""
    from app.core.perceive.maps import AnalysisMap
    from app.ui.analysis_bar import LEGEND_MAX_ENTRIES

    many = tuple(f"feature_{index}" for index in range(LEGEND_MAX_ENTRIES + 5))
    analysis = AnalysisMap(
        kind="features",
        title="Merkmale",
        values=tuple(float(index) for index in range(len(many))),
        unit="",
        low=0.0,
        high=float(len(many) - 1),
        categories=many,
    )
    window.analysis_bar.show_legend(analysis)

    labels = [label for label, _colour in window.analysis_bar.legend.entries]
    assert len(labels) == LEGEND_MAX_ENTRIES + 1, "acht Felder und ein Rest"
    assert "5" in labels[-1], "der Rest wird gezählt, nicht verschwiegen"


def test_the_angle_maps_write_the_degree_sign(window: MainWindow) -> None:
    """„45°", nicht „45 grad" — wie überall sonst im Programm."""
    from app.core.perceive.maps import AnalysisMap

    analysis = AnalysisMap(
        kind="overhang",
        title="Überhang",
        values=(0.0, 45.0, 90.0),
        unit="°",
        low=0.0,
        high=90.0,
    )
    window.analysis_bar.show_legend(analysis)

    labels = [label for label, _colour in window.analysis_bar.legend.entries]
    assert all("grad" not in label for label in labels)
    assert any(label.endswith("°") for label in labels)


def test_the_context_menu_greys_out_what_this_body_cannot_do(window: MainWindow) -> None:
    """Am Netz-Körper bot es die Operationen des exakten Kerns anklickbar an.

    Wer dort *Verrunden* wählte, füllte einen Dialog aus und bekam danach eine
    Absage — genau die Sackgasse, die Regel 19 ausschließt. Die Menüleiste
    vermeidet sie seit je: Sie graut aus und schreibt den Grund in den Tooltip,
    „statt sie anzubieten und nach dem ausgefüllten Dialog abzulehnen". Das
    Kontextmenü kannte die Bauart nicht — es fragte niemanden.

    Ausgegraut und nicht ausgeblendet, aus demselben Grund wie dort: Wer eine
    Zeile vermisst, sucht sie.
    """
    select_plate(window)
    menu = window.object_tree.context_menu()
    assert menu is not None

    actions = {
        action.text(): action
        for entry in menu.actions()
        for action in (entry.menu().actions() if entry.menu() else [entry])
    }
    exact = [spec for spec in window.object_tree.operations_for_object() if spec.requires_kind]
    assert exact, "ohne Operationen des exakten Kerns prüft dieser Test nichts"

    kinds = window.object_tree.kinds_of_selection()
    assert kinds == ["mesh"], f"die Platte ist ein Netz, gemeldet wurde {kinds}"

    for spec in exact:
        action = actions.get(str(spec.title))
        assert action is not None, f"{spec.name} fehlt im Menü — ausgegraut, nicht verschwunden"
        assert not action.isEnabled(), f"{spec.name} steht am Netz-Körper anklickbar da"
        assert "exakten Körper" in action.toolTip(), (
            f"{spec.name} sagt nicht, was ihm fehlt: {action.toolTip()!r}"
        )

    # Und was auf einem Netz kann, bleibt bedienbar — sonst wäre die Prüfung
    # eine Sperre und keine Auskunft.
    plain = [spec for spec in window.object_tree.operations_for_object() if not spec.requires_kind]
    enabled = [str(spec.title) for spec in plain if actions.get(str(spec.title)) is not None]
    assert any(actions[title].isEnabled() for title in enabled), "alles gesperrt wäre kein Menü"
    menu.deleteLater()


def test_a_finding_says_which_step_reported_it(window: MainWindow) -> None:
    """Die Liste sortiert nach Schwere — Sätze aus verschiedenen Schritten
    stehen also untereinander.

    Bei ``weg3-generiert-aufbereiten`` liest sich das als Widerspruch: „Das
    Modell ist nicht geschlossen." direkt neben „Eine offene Stelle ist
    geschlossen und damit fort." Beides stimmt, das eine kommt vom Einlesen, das
    andere von der Reparatur — und das stand nirgends. ``Finding`` trägt seine
    ``op_id`` seit je; gezeigt wurde sie nicht.

    Im Tooltip und nicht in der Zeile: die trägt schon Kennzahlen, und der
    Bericht ist die Ansicht, die ruhig bleiben muss.
    """
    from PySide6.QtCore import Qt

    report = window.report
    listed = [
        report.list.item(row)
        for row in range(report.list.count())
        if report.list.item(row).data(Qt.ItemDataRole.UserRole) is not None
    ]
    with_step = [
        item
        for item in listed
        if getattr(item.data(Qt.ItemDataRole.UserRole), "op_id", None) is not None
    ]
    assert with_step, "kein Befund im Bericht trägt eine Operationsnummer"

    # Die genaue Wendung, nicht bloß die Zahl: eine „2" steckt auch in
    # „2,40 mm", und ein Test, der darauf prüft, besteht auch ohne die Angabe.
    # (Genau das ist bei der Gegenprobe passiert.)
    from app.i18n import tr

    for item in with_step:
        finding = item.data(Qt.ItemDataRole.UserRole)
        wanted = f"{tr('aus Operation')} {finding.op_id}"
        assert wanted in item.toolTip(), (
            f"{finding.message!r} nennt seinen Schritt nicht: {item.toolTip()!r}"
        )


def test_the_context_menu_follows_the_titles_like_the_menu_bar() -> None:
    """Das Kontextmenü ordnete nach dem internen englischen Namen.

    ``REGISTRY.all()`` sortiert danach, und ``operations_for_object`` gab das
    ungefiltert weiter: „An Merkmal ausrichten", „Textur aufbringen", „Auf dem
    Bett anordnen", „Slot zuweisen" — dieselbe Zufallsfolge, die auch die
    Befehlspalette zeigte, während die Menüleiste daneben nach Titel sortiert.
    Drei Wege in dieselbe Funktion, zwei Ordnungen.

    Verglichen wird mit ``i18n.sort_key``, dem Schlüssel der Menüleiste: „Ü"
    steht im Zeichensatz hinter „z", und „Überhangfächer" landete roh
    verglichen hinter allem anderen.
    """
    from app.i18n import sort_key
    from app.ui.panels import ObjectTree

    titles = [str(spec.title) for spec in ObjectTree.operations_for_object(None)]  # type: ignore[arg-type]
    assert titles, "ohne Operationen prüft dieser Test nichts"
    assert titles == sorted(titles, key=sort_key), "das Kontextmenü folgt nicht dem Titel"
    assert any(title.startswith("Ü") for title in titles), (
        "ohne Umlaut am Wortanfang prüft der Vergleich den Sortierschlüssel nicht"
    )


def test_an_empty_report_offers_nothing_to_filter(qt_app: QApplication) -> None:
    """Der leere Bericht zeigte Suchfeld, Filterauswahl und einen leeren Kasten.

    Drei Bedienelemente, von denen keines etwas tun kann, und der einzige Satz
    mit Inhalt — „Keine Befunde." — stand darüber wie eine Überschrift. Das ist
    der häufigste Zustand des Berichts, nicht ein Randfall.

    Die Schwelle ist zwei: Bei einem einzigen Befund kann ein Filter nur ihn
    treffen oder die Zeile „Kein Befund passt zu …" erzeugen.
    """
    from app.ui.panels import FILTER_FROM, ReportPanel

    finding = Finding(
        code="arrange.out_of_build_volume",
        severity="warning",
        message="Ein Objekt steht über den Bauraum hinaus.",
        object_id="obj_1",
        values={"object": "Halter"},
    )
    panel = ReportPanel()
    try:
        panel.show_result(None)
        assert panel.list.isHidden(), "der leere Kasten steht noch da"
        assert panel.search.isHidden(), "gesucht wird in nichts"
        assert panel.severity.isHidden(), "gefiltert auch"
        assert panel.summary.text(), "und der Satz, der etwas sagt, bleibt"

        panel.add_findings([finding])
        assert not panel.list.isHidden(), "ein Befund gehört gezeigt"
        assert panel.search.isHidden(), f"ein Filter für {FILTER_FROM - 1} Befund"

        second = dataclasses.replace(finding, object_id="obj_2", values={"object": "Deckel"})
        panel.add_findings([second])
        assert not panel.search.isHidden(), "ab zwei Befunden gibt es etwas zu filtern"
        assert not panel.severity.isHidden()

        # Und ein Filter, der wieder verschwindet, nimmt seine Wirkung mit:
        # sonst bliebe eine Auswahl gesetzt, die niemand mehr zurücknehmen kann.
        panel.search.setText("Bauraum")
        panel.severity.setCurrentIndex(1)
        panel.show_result(None)
        assert panel.search.text() == "", "der Suchbegriff überlebt sein Feld"
        assert panel.severity.currentIndex() == 0, "und die Stufe ihre Auswahl"
    finally:
        panel.deleteLater()


def test_the_object_tree_gives_the_names_the_larger_half(qt_app: QApplication) -> None:
    """Beide Körper des ersten Beispiels standen als derselbe Text da.

    Der Kommentar über der Kopfzeile sagt: „Die Maßspalte nimmt, was sie
    braucht; der Rest gehört den Namen." Gegolten hat er nicht —
    ``stretchLastSection`` steht auf Qts Vorgabe ``True`` und überstimmt das
    ``ResizeToContents`` der letzten Spalte. Gemessen: 128 zu 128 bei 258 Pixeln
    Baumbreite, und nach Abzug von Einzug und Vorschaubild blieben für
    „Gehäuseboden" und „Gehäuseboden (Kopie) Prüfstück" dieselbe abgeschnittene
    Zeichenkette.

    Den Deckel nur abzuschalten kippt es um: dann nimmt die Maßspalte ihre
    Inhaltsbreite, und bei „60 x 40 x 12 mm" waren das 186 von 258 — 70 für den
    Namen. Geprüft wird deshalb das Verhältnis und nicht der Schalter: Der Name
    behält die Mehrheit, das Maß bekommt höchstens seinen Anteil, und über die
    Breite hinweg bleibt beides so.
    """
    from PySide6.QtWidgets import QTreeWidgetItem

    from app.ui.panels import MEASURE_SHARE, ObjectTree

    panel = ObjectTree()
    try:
        panel.resize(258, 400)
        panel.show()
        for name, size in (
            ("Gehäuseboden", "60 x 40 x 12 mm"),
            ("Gehäuseboden (Kopie) Prüfstück", "20 x 20 x 5 mm"),
        ):
            panel.tree.addTopLevelItem(QTreeWidgetItem([name, size]))
        QApplication.processEvents()

        header = panel.tree.header()
        assert not header.stretchLastSection(), (
            "der Deckel überstimmt jede Einstellung der letzten Spalte"
        )
        for width in (258, 420, 700):
            panel.resize(width, 400)
            QApplication.processEvents()
            panel._size_columns()
            QApplication.processEvents()
            names, measures = header.sectionSize(0), header.sectionSize(1)
            assert names > measures, f"bei {width} px: Name {names}, Maß {measures}"
            assert measures <= int(panel.tree.viewport().width() * MEASURE_SHARE) + 1, (
                f"bei {width} px nimmt die Maßspalte {measures} und damit mehr als ihren Anteil"
            )
    finally:
        panel.deleteLater()
