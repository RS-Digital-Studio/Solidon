"""Analysekarten, Merkmals-Überlagerung und Schichtanalyse in der
Oberfläche (§18.4, §18.5, §18.10).

Wieder offscreen: geprüft werden die Verdrahtung und die Legende, nicht das
Bild. Ob die Farben auf dem richtigen Dreieck landen, entscheidet der Kern, und
``tests/test_maps.py`` prüft es dort.
"""

from __future__ import annotations

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
def window(qt_app: QApplication) -> MainWindow:
    window = MainWindow(Session(), UiSettings())
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    return window


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

        viewport.set_analysis_map(
            maps.AnalysisMap(kind="wall", title="x", values=(1.0,), unit="mm", low=1.0, high=4.0),
            None,
        )
        assert not viewport.ambient_occlusion, "mit Karte ist sie aus"

        viewport.set_analysis_map(None, None)
        assert viewport.ambient_occlusion, "danach wieder an"
    finally:
        # Ein Widget ohne Elternteil räumt sich nicht selbst weg, und was am
        # Ende des Laufs noch lebt, wird beim Herunterfahren des Interpreters
        # aufgeräumt — dann ist der Thread-Pool der Schichtanalyse längst zu,
        # und die Meldung darüber landet als Rauschen in einer grünen Suite.
        viewport.deleteLater()


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
