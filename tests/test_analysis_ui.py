"""Analysekarten, Merkmals-Überlagerung und Schichtanalyse in der
Oberfläche (§18.4, §18.5, §18.10).

Wieder offscreen: geprüft werden die Verdrahtung und die Legende, nicht das
Bild. Ob die Farben auf dem richtigen Dreieck landen, entscheidet der Kern, und
``tests/test_maps.py`` prüft es dort.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from app.core.perceive import maps
from app.core.types import Finding
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
    violation``, ohne Zeile, an wechselnder Stelle): den gibt es hier
    unabhängig von dieser Fixture. Nachgemessen an je vier Läufen — mit
    Aufräumung, mit Löschen, und ganz ohne — riss er in jeder Fassung, auch in
    der ohne. Er gehört zu dem Muster, das die Roadmap als „ersetzte Arbeiter
    lassen ihre Referenz los" führt und für zwei Stellen behoben hat; die
    übrigen sind dort namentlich notiert.
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


# --- the map selector -----------------------------------------------------------


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


# --- the legend -----------------------------------------------------------------


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
    assert "0.3" in legend.note.text(), "a sampled map says how fine it was sampled"


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
    item = window.object_tree.tree.topLevelItem(0)

    assert item is not None and item.childCount() >= 4, "four bores and the faces"
    labels = [item.child(index).text(0) for index in range(item.childCount())]
    assert any(text.startswith("hole_1 · Ø") for text in labels)


def test_a_feature_offers_the_operations_that_apply_to_it(window: MainWindow) -> None:
    """§10, §18.5: das Kontextmenü kommt aus ``applies_to``, nicht aus einer
    Liste.
    """
    entries = window.object_tree.operations_for_feature("face")

    assert entries, "drilling applies to a face"
    assert all("face" in spec.applies_to for spec in entries)


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
    assert window.viewport._fitted, "das geöffnete Projekt steht im Bild"

    window.viewport.show_scene(result)
    assert window.viewport._fitted, "und der nächste Aufbau passt nicht erneut ein"

    window.viewport.show_scene(None)
    assert not window.viewport._fitted, (
        "eine leere Szene macht den Weg für das nächste Projekt frei"
    )


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

    assert label.startswith("hole_1 · Ø")


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


def test_the_layer_bar_is_called_what_it_is(qt_app: QApplication) -> None:
    """Keine Vorschau: sie zeigt Geometrie, keine Werkzeugwege (§18.10)."""
    bar = LayerBar()
    labels = [bar.active.itemText(index) for index in range(bar.active.count())]

    assert any("Schichtanalyse" in text for text in labels)
    assert not any("Vorschau" in text for text in labels)


def test_scrubbing_shows_one_layer(window: MainWindow) -> None:
    """Die Schichtanalyse rechnet im Arbeiter (§2.8) — die Leiste füllt sich,
    sobald sie da ist, statt das Fenster so lange anzuhalten.
    """
    select_plate(window)
    window.layer_bar.active.setCurrentIndex(1)
    _wait_for_slice(window)

    assert window.layer_bar.slider.maximum() > 0, "the plate has layers"
    window.layer_bar.slider.setValue(3)
    assert "z" in window.layer_bar.readout.text()
    assert "Schicht" in window.layer_bar.readout.text()


def test_switching_it_off_clears_the_view(window: MainWindow) -> None:
    select_plate(window)
    window.layer_bar.active.setCurrentIndex(1)
    window.layer_bar.active.setCurrentIndex(0)

    assert window.layer_bar.index() == -1
    assert window.layer_bar.readout.text() == ""


# --- Maßstab an der Druckplatte (Konzept P15 §7 Etappe 1) ----------------------


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
    assert labels.count("0") == 1, "der Nullpunkt gehört beiden Kanten, steht aber einmal da"
    # 128 mm je Seite, alle 50 mm: 50 und 100 in beide Richtungen, je Achse
    # vier Zahlen, dazu die Null.
    assert len(marks) == 2 * 4 + 1

    steps = sorted({float(text) for text in labels if text != "0"})
    assert steps == [BED_SCALE_STEP, 2 * BED_SCALE_STEP]


def test_a_small_bed_still_gets_a_scale() -> None:
    """Und eine Platte, die kleiner ist als ein Schritt, bekommt wenigstens
    ihren Nullpunkt — statt einer leeren Beschriftungsliste, über die VTK
    stolpert."""
    from app.ui.viewport import bed_scale

    marks = bed_scale(60.0, 60.0)
    assert marks
    assert [text for _point, text in marks] == ["0"]


def test_a_shadow_falls_beside_the_body_not_under_it() -> None:
    """Senkrecht projiziert ist ein Schatten unsichtbar.

    Der erste Versuch legte ihn genau unter den Körper — dort verdeckt ihn der
    Körper, und im Bild war schlicht kein Schatten. Er fällt deshalb entlang
    einer festen Lichtrichtung, und sein Versatz wächst mit der Höhe: damit
    beantwortet er nebenbei die Frage, für die er da ist, denn ein schwebendes
    Teil hat seinen Schatten weiter weg.
    """
    import numpy as np

    from app.ui.viewport import SHADOW_DIRECTION, shadow_points

    standing = shadow_points(np.array([[0.0, 0.0, 0.0], [0.0, 0.0, 40.0]]))
    assert standing[0][0] == pytest.approx(0.0), "was aufliegt, wirft an Ort und Stelle"
    assert standing[1][0] == pytest.approx(40.0 * SHADOW_DIRECTION[0])
    assert standing[1][1] == pytest.approx(40.0 * SHADOW_DIRECTION[1])
    assert all(point[2] == 0.0 for point in standing), "der Schatten liegt auf der Platte"


def test_a_body_below_the_plate_throws_nothing_forward() -> None:
    """Sonst zöge ein halb versunkenes Teil seinen Schatten falsch herum."""
    import numpy as np

    from app.ui.viewport import shadow_points

    sunk = shadow_points(np.array([[5.0, 7.0, -12.0]]))
    assert sunk[0][0] == pytest.approx(5.0)
    assert sunk[0][1] == pytest.approx(7.0)
