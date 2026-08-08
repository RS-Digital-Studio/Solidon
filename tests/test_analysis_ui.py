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

from PySide6.QtWidgets import QApplication

from app.core.perceive import maps
from app.core.types import Finding
from app.i18n import tr
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
    assert window.viewport._fitted, "das geöffnete Projekt steht im Bild"

    window.viewport.show_scene(result)
    assert window.viewport._fitted, "und der nächste Aufbau passt nicht erneut ein"

    window.viewport.show_scene(None)
    assert not window.viewport._fitted, (
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
    """
    window.viewport.show_scene(window.session.last_result)
    plotter = _CameraPlotter()
    window.viewport.plotter = plotter

    window.viewport.reset_camera()

    assert plotter.fitted_to == [window.viewport._object_bounds()], "auf die Körper"
    assert plotter.camera_set, "und danach fasst pyvista die Kamera nicht mehr an"


def test_an_empty_scene_still_fits_on_something(window: MainWindow) -> None:
    """Ohne Körper bleibt der Bauraum das Maß — dann ist er das Einzige, was
    es zu sehen gibt."""
    window.viewport.show_scene(None)
    plotter = _CameraPlotter()
    window.viewport.plotter = plotter

    window.viewport.reset_camera()

    assert plotter.fitted_to == [None]
    assert plotter.camera_set


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
    """Ein Actor mit genau dem, was Auswahl und Beschriftung anfassen."""

    def __init__(self) -> None:
        self.prop = SimpleNamespace(color=None)
        self.center = (0.0, 0.0, 0.0)

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


class _GizmoPlotter:
    """Ein Plotter, der Griffe und Beschriftungen nur verbucht."""

    def __init__(self) -> None:
        self.widgets: list[_GizmoWidget] = []

    def add_affine_transform_widget(self, actor: object, **_kwargs: object) -> _GizmoWidget:
        widget = _GizmoWidget(actor)
        self.widgets.append(widget)
        return widget

    def add_point_labels(self, *_args: object, **_kwargs: object) -> object:
        return object()

    def remove_actor(self, _actor: object, render: bool = True) -> None:
        pass

    def add_mesh(self, *_args: object, **_kwargs: object) -> object:
        return object()

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
