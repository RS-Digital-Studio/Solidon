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
from typing import Any

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import Qt, QThread
from PySide6.QtWidgets import QApplication

from app.core.perceive import maps
from app.core.types import Action, Finding
from app.i18n import TranslatableText, format_decimal, tr
from app.ui.analysis_bar import MAP_ORDER, AnalysisBar, LayerBar, MapLegend
from app.ui.labels import feature_label, length
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
    der Sitzung — das Fenster führt vier eigene.

    **Einer davon, die Update-Prüfung, startet in der Suite allerdings nie**,
    und der Satz stand hier zwei Runden lang falsch: Sie hängt an
    ``UiSettings.check_for_updates``, das in der Vorgabe **aus** ist, und kein
    Test schaltet es ein. Im Betrieb startet sie bei jedem Fenster von selbst,
    in der Suite nicht — gemessen am 23.08.2026 von 3d-druck-b8, die wissen
    musste, ob ihre Frist von zwei Sekunden gegen die vier Sekunden dieses
    Arbeiters reicht. Sie reicht, weil er gar nicht läuft.

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
    Aufräumung, mit Löschen und ganz ohne, riss er in jeder Version.

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


def on_the_bore_wall(window: MainWindow, feature_id: str) -> tuple[float, float, float]:
    """Eine Stelle auf der Wand dieser Bohrung — also eine, die ein Klick
    wirklich trifft.

    Drei Tests dieser Datei zeigten bis zum 22.08.2026 auf den **Mittelpunkt**
    einer Bohrung. Der liegt auf ihrer Achse, mitten im Leeren, und dort ist
    keine Oberfläche: Ein ``vtkCellPicker`` kann diesen Punkt nicht
    zurückgeben. Grün waren sie, weil ``_feature_at`` damals das Merkmal mit
    dem nächsten Mittelpunkt nahm — sie prüften also gegen die Rechenweise und
    nicht gegen einen Klick. Seit die Reichweite an den Dreiecken des Merkmals
    hängt (§18.5), zeigen sie dorthin, wo gezeigt wird.

    Die eigentliche Auswahltiefe steht in ``tests/test_selection.py``; hier
    bleiben die drei Aussagen, um die es diesen Tests ging.
    """
    entry = window.session.last_result.scene.objects["obj_1"]
    feature = entry.features[feature_id]
    centre = feature.params["centre"]
    radius = float(feature.params["diameter"]) * 0.5
    return (float(centre[0]) + radius, float(centre[1]), 2.0)


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


def test_every_map_says_what_it_shows(qt_app: QApplication) -> None:
    """Sieben Fachwörter ohne Erklärung waren ein Ratespiel (Review 02.09.2026).

    Der Name benennt, der Satz sagt, was die Karte zeigt — als Tooltip und als
    Beschreibung für Hilfstechniken, für jeden Eintrag und für den Haken.
    """
    from PySide6.QtCore import Qt

    bar = AnalysisBar()
    for index in range(bar.selector.count()):
        for role in (Qt.ItemDataRole.ToolTipRole, Qt.ItemDataRole.AccessibleDescriptionRole):
            sentence = bar.selector.itemData(index, role)
            assert isinstance(sentence, str) and sentence.endswith("."), (index, role)
    assert bar.overlay.toolTip().endswith(".")
    assert bar.overlay.accessibleDescription() == bar.overlay.toolTip()


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

    # Aufgelöst verglichen, nicht gegen die Message-ID: Die Stufen sind seit
    # Regel 20 übersetzbar (`maps.DEFECT_LEVELS`), und was in der Legende steht,
    # ist ihre Übersetzung.
    assert [text for text, _colour in legend.entries] == [
        str(level) for level in maps.DEFECT_LEVELS
    ]


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


def test_a_report_click_keeps_its_mark_across_the_async_map(
    window: MainWindow,
) -> None:
    """Bericht, Kartenarbeiter, Renderer und Zeitgeber halten dieselbe Zusage.

    Der kleine Viewport-Test kann nur sagen, was ``show_scene`` mit einer
    Attrappe aufruft. Der Kundenfehler lag eine Ebene höher: Ein echter Klick
    zeichnete Ring und Text, die fertige Analysekarte baute danach die Szene
    neu und nahm beide wieder weg. Dieser Test fährt deshalb die ganze Kette
    von der sichtbaren Berichtszeile bis zu ``set_analysis_map`` und lässt den
    echten ``QTimer`` in der Qt-Ereignisschleife ablaufen.

    Headless bekommt einen echten PyVista-Renderer statt einer Methodenattrappe;
    auf einer Bildschirmplattform bleibt der wirkliche ``QtInteractor`` des
    Fensters im Einsatz. Damit prüft auch der normale Lauf native VTK-Aktoren,
    und der Windows-Beleg zusätzlich ihren Produktweg.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.ui.viewport import FINDING_MARK_MS

    viewport = window.viewport
    owned_plotter: Any | None = None
    before_rebuild: list[tuple[object | None, tuple[Any, ...], frozenset[str]]] = []
    after_rebuild: list[tuple[object | None, tuple[Any, ...], frozenset[str]]] = []
    original_set_map = viewport.set_analysis_map

    def actor_names() -> frozenset[str]:
        plotter = viewport.plotter
        assert plotter is not None
        renderer = plotter.renderer
        return frozenset(str(name) for name in renderer.actors)

    def has_actor(names: frozenset[str], wanted: str) -> bool:
        # ``add_point_labels`` hängt im nativen PyVista-Renderer die Rolle an
        # den vergebenen Namen (``finding_label-labels``). Der Ring bleibt
        # dagegen als ``finding_ring`` unverändert.
        return any(name == wanted or name.startswith(f"{wanted}-") for name in names)

    def observe_map(analysis: Any, object_id: Any) -> None:
        before_rebuild.append(
            (viewport._finding_mark, tuple(viewport._finding_actors), actor_names())
        )
        original_set_map(analysis, object_id)
        after_rebuild.append(
            (viewport._finding_mark, tuple(viewport._finding_actors), actor_names())
        )

    try:
        if viewport.plotter is None:
            pyvista = pytest.importorskip("pyvista")
            owned_plotter = pyvista.Plotter(off_screen=True)
            viewport.plotter = owned_plotter
            viewport.show_scene(window.session.last_result)
        viewport.set_analysis_map = observe_map  # type: ignore[method-assign]

        select_plate(window)
        finding = Finding(
            code="fit.violated",
            severity="warning",
            message="Diese Passung ist zu eng.",
            object_id="obj_1",
            feature_ids=("hole_1",),
        )
        window.report.add_findings([finding])
        window.resize(1040, 760)
        window.show()
        QApplication.processEvents()

        item = next(
            window.report.list.item(row)
            for row in range(window.report.list.count())
            if window.report.list.item(row).data(Qt.ItemDataRole.UserRole) is finding
        )
        window.report.list.scrollToItem(item)
        QApplication.processEvents()
        QTest.mouseClick(
            window.report.list.viewport(),
            Qt.MouseButton.LeftButton,
            pos=window.report.list.visualItemRect(item).center(),
        )
        wait_for_map(window)

        assert before_rebuild and before_rebuild[-1][0] is not None, (
            "die Marke muss schon stehen, wenn die fertige Karte die Szene neu baut"
        )
        assert len(before_rebuild[-1][1]) == 2, "Ring und Text standen vor dem Kartenaufbau"
        assert has_actor(before_rebuild[-1][2], "finding_ring"), sorted(before_rebuild[-1][2])
        assert has_actor(before_rebuild[-1][2], "finding_label"), sorted(before_rebuild[-1][2])
        assert after_rebuild and after_rebuild[-1][0] == before_rebuild[-1][0]
        assert len(after_rebuild[-1][1]) == 2, "der Kartenaufbau zeichnet beide Aktoren neu"
        assert after_rebuild[-1][1] != before_rebuild[-1][1], (
            "alte Python-Referenzen dürfen keinen erhaltenen Renderer vortäuschen"
        )
        assert has_actor(after_rebuild[-1][2], "finding_ring"), sorted(after_rebuild[-1][2])
        assert has_actor(after_rebuild[-1][2], "finding_label"), sorted(after_rebuild[-1][2])
        assert viewport.analysis_map is not None and viewport.analysis_map.kind == "fits"
        assert viewport._finding_mark == before_rebuild[-1][0]
        assert viewport._finding_timer.isActive(), "die sichtbare Frist läuft nach dem Kartenaufbau"
        assert tuple(viewport._finding_actors) == after_rebuild[-1][1]
        current_names = actor_names()
        assert has_actor(current_names, "finding_ring"), sorted(current_names)
        assert has_actor(current_names, "finding_label"), sorted(current_names)

        QTest.qWait(FINDING_MARK_MS + 100)
        QApplication.processEvents()
        assert viewport._finding_mark is None, "der semantische Zustand läuft mit der Frist ab"
        assert viewport._finding_actors == [], "nach der Frist bleibt kein nativer Aktor"
        expired_names = actor_names()
        assert not has_actor(expired_names, "finding_ring")
        assert not has_actor(expired_names, "finding_label")
    finally:
        window.hide()
        viewport.set_analysis_map = original_set_map  # type: ignore[method-assign]
        viewport._finding_timer.stop()
        viewport._hide_finding_mark(render=False)
        if owned_plotter is not None:
            owned_plotter.close()
            viewport.plotter = None
        elif viewport.plotter is not None:
            # Der native Interactor gehört dem Prozess und darf zwischen zwei
            # Fenstern nicht geschlossen werden (``MainWindow.release``).
            # Seine Szene räumen wir trotzdem explizit, damit der sichtbare
            # Beleg keine VTK-Aktoren bis zum Prozessende festhält.
            viewport.plotter.clear()


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


def test_a_fillet_says_what_it_is_and_how_big() -> None:
    """Im Objektbaum stand „fillet_1" — ein englisches Wort in der Oberfläche,
    an ``tr()`` vorbei, und daneben eine leere Maßspalte.

    Die Merkmalsart kam im August dazu; die Beschriftung wurde nicht
    nachgezogen, und ``feature_name`` fiel auf die Kennung zurück. **Kein Test
    hat es bemerkt, und das ist der eigentliche Befund:** Die Tests fragen, *ob*
    ein Merkmal erkannt wird, nicht, *was* dort steht. Gemeldet hat es
    3d-druck-3a beim Durchsehen der eigenen Arbeit.

    **R und nicht Ø**, weil eine Verrundung über ihren Radius benannt wird —
    der Kunde sagt „R3", der Slicer sagt „R3", Fusion sagt „R3".

    Und die Unterscheidung ist mehr als Kosmetik: Eine einspringende Ecke
    bedeutet für den Druck etwas anderes als eine ausspringende. Eine
    Hohlkehle ist die Stelle, an der später die Frage kommt, ob die Düse dort
    überhaupt hinkommt.
    """
    from app.core.types import Feature
    from app.ui.labels import feature_measure, feature_name

    def fillet(name: str, *, recess: bool) -> Feature:
        return Feature(
            id=name,
            kind="fillet",
            params={"radius": 3.0, "recess": recess},
            provenance="test",
        )

    assert feature_name("fillet_1", fillet("fillet_1", recess=False)) == tr("Verrundung")
    assert feature_name("fillet_2", fillet("fillet_2", recess=True)) == tr("Hohlkehle")
    assert feature_measure(fillet("fillet_1", recess=False)) == f"R{length(3.0)}"


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


def test_a_sphere_and_a_torus_say_which_way_they_point() -> None:
    """``recess`` trennt bei Kugel und Torus dasselbe wie beim Kegel zwischen
    Senkung und Verjüngung: hinein oder heraus.

    Eine ausgehöhlte Kugel ist eine Pfanne (Kugelgelenk, Magnettasche), eine
    aufgesetzte eine Kuppel; beim Torus heißen die beiden Formen Kehle und
    Wulst. Vor ``15d3d16`` stand dort die rohe Kennung — ``sphere_1`` im Baum,
    und der Nächste hält einen englischen Schlüssel für Absicht.

    Entworfen von 3d-druck-b8 zusammen mit den Beschriftungen; die Mutation
    (``recess`` bei der Kugel vertauscht) meldet beide Kugelzeilen und lässt
    die Torus-Zeilen grün, der Test trennt die vier Aussagen also wirklich.
    """
    from app.core.types import Feature
    from app.ui.labels import feature_name

    def round_one(kind: str, recess: bool) -> Feature:
        return Feature(id=f"{kind}_1", kind=kind, params={"recess": recess}, provenance="test")

    assert feature_name("sphere_1", round_one("sphere", True)) == tr("Pfanne")
    assert feature_name("sphere_1", round_one("sphere", False)) == tr("Kuppel")
    assert feature_name("torus_1", round_one("torus", True)) == tr("Kehle")
    assert feature_name("torus_1", round_one("torus", False)) == tr("Wulst")


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

    **Der Test verlangte lange, dass jede Operation direkt dasteht, und das war
    eine Zusage, die die Oberfläche nie gegeben hat.** ``_add_operations``
    faltet die größten Gruppen, sobald das Menü über zwölf Zeilen ginge — am
    Flächenklick tut es das seit je, dort bündelt *Bausteine* fünfundzwanzig
    Einträge zu einer Zeile. An der Bohrung waren es zehn Operationen und damit
    knapp darunter; mit *Merkmal verschieben*, *drehen* und *entfernen* sind es
    dreizehn, und dieselbe Regel greift auch hier: Die fünf Katalogeinträge
    stehen in einem Untermenü, die acht Operationen der Bohrung selbst direkt.

    Und wo die Bausteine gefaltet würden, tritt der **Katalog** an ihre Stelle
    — eine Zeile *Baustein einsetzen …*, die Bilder statt Vokabeln zeigt. Das
    ist Roberts Bedingung von damals („solange man einfach zum Katalog kommt,
    wenn man das Teil gewählt hat"), und sie gilt jetzt an der Bohrung wie
    längst an der Fläche.

    Geprüft wird deshalb, was die Oberfläche wirklich verspricht: **was das
    Merkmal selbst angeht, steht direkt da**, und die Bausteine sind einen
    Klick entfernt. Ein Katalog ist etwas anderes als eine Handlung an dieser
    Bohrung; ihn zu bündeln kostet einen Klick und gibt vier Zeilen an die
    Handlungen zurück, um derentwillen der Kunde geklickt hat.
    """
    window.object_tree.select_feature("obj_1", "hole_2")
    menu = window.object_tree.context_menu()

    assert menu is not None
    direct = {action.text().replace("&", "") for action in menu.actions()}
    offered = window.object_tree.operations_for_feature("hole")
    expected = {str(spec.title) for spec in offered}
    catalogue = {str(spec.title) for spec in offered if spec.category == "parts"}

    assert expected, "an einer Bohrung gibt es etwas zu tun"
    assert expected - catalogue <= direct, "was die Bohrung selbst angeht, steht direkt da"
    assert "Baustein einsetzen …" in direct, "und die Bausteine über den Katalog"
    menu.deleteLater()


def test_no_menu_shows_the_same_line_twice(window: MainWindow) -> None:
    """Zwei Zeilen mit demselben Text sind eine Frage ohne Antwort.

    An jeder Fläche stand **Bohrung setzen** zweimal: ``drill_hole`` und
    ``drill_brep_hole`` tragen denselben Titel, und der Kunde kann nicht
    wissen, welche gemeint ist — die Auswahl trifft er blind, und je nach
    Treffer bekommt er einen anderen Rechenkern.

    Die Menüleiste hat das Paar seit je zusammengelegt (``MENU_TWINS``): Der
    sichtbare Zwilling trägt den Eintrag, der andere ist über einen
    Umschalter in dessen Dialog erreichbar. ``operations_for_feature`` gab
    ``REGISTRY.for_feature`` ungefiltert weiter und kannte die Zusammenlegung
    nicht. **Dieselbe Frage, zwei Rechnungen** — genau der Grund, aus dem die
    Menütiefe in den Kern gewandert ist.

    Geprüft wird die Zusage und nicht der eine Fall: Kein Kontextmenü zeigt
    zwei Zeilen mit demselben Text, auf keiner Ebene. Ein Test auf „Bohrung
    setzen genau einmal" wäre am Tag des nächsten Zwillings still.

    Und **nicht** über ``operations_for_feature`` formuliert, obwohl der
    Filter dort sitzt: Ein Test, der seine Erwartung aus dem Prüfling holt,
    wird mit ihm zusammen falsch. Gezählt wird am gebauten Menü.
    """
    scene = window.session.last_result.scene.objects["obj_1"]
    features = [entry.id for entry in scene.features.values()]
    assert features, "das Testmodell hat keine Merkmale — dann prüft dieser Test nichts"

    seen = 0
    for feature_id in features:
        window.object_tree.select_feature("obj_1", feature_id)
        menu = window.object_tree.context_menu()
        assert menu is not None
        levels = [[action for action in menu.actions() if not action.isSeparator()]]
        levels += [
            [entry for entry in action.menu().actions() if not entry.isSeparator()]
            for action in menu.actions()
            if action.menu()
        ]
        for level in levels:
            texts = [action.text() for action in level]
            seen += len(texts)
            twice = sorted({text for text in texts if texts.count(text) > 1})
            assert not twice, f"{feature_id}: zweimal dieselbe Zeile {twice}"
        menu.deleteLater()

    assert seen > len(features), "keine Menüzeilen gezählt — dann prüft dieser Test nichts"


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


def _insert_a_thread(window: MainWindow) -> str:
    """Ein Gewinde einsetzen und die Kennung seines Merkmals zurückgeben.

    Die Fixture liest ein Modell ein, und dessen Merkmale sind **erkannt**.
    Ein erzeugtes entsteht, wo ein Baustein eines verspricht (§24.1) — beim
    Gewinde also, und das ist genau der Fall, an dem das leere Kontextmenü
    aufgefallen ist.

    Nicht am Bohren: ``drill_hole`` rechnet Geometrie und deklariert kein
    Merkmal. Was es hinterlässt, findet die Erkennung wieder, und ein
    erkanntes Merkmal trägt keinen Erzeuger.
    """
    from app.core.registry import REGISTRY

    select_plate(window)
    window.run_operation(REGISTRY.get("insert_printed_thread"))
    dialog = window._op_dialog
    assert dialog is not None

    # **Eine Stelle gehört dazu, seit der Baustein danach fragt.** Bis zum
    # 25.08.2026 kam dieser Test ohne aus: Ein Baustein ohne gewähltes Merkmal
    # landete still im Nullpunkt des Objekts, und der Test nahm das Ergebnis.
    # Jetzt hält die Auswertung an und sagt, was fehlt (Regel 21) — was der
    # Kunde im Katalog bekommt, bekommt dieser Test auch.
    before = window.session.last_result
    assert before is not None
    faces = [
        feature_id
        for entry in before.scene.objects.values()
        for feature_id, feature in entry.features.items()
        if feature.kind == "face"
    ]
    assert faces, "das eingelesene Modell trägt keine Fläche, an die etwas käme"
    picker = dialog._editors["at_feature"]
    index = picker.findData(faces[0])
    assert index >= 0, (
        f"{faces[0]} steht nicht zur Wahl: {[picker.itemData(i) for i in range(picker.count())]}"
    )
    picker.setCurrentIndex(index)
    dialog.accept()
    window.session.wait_for_idle()

    result = window.session.last_result
    assert result is not None
    made = [
        (object_id, feature_id)
        for object_id, entry in result.scene.objects.items()
        for feature_id, feature in entry.features.items()
        if feature.created_by is not None
    ]
    assert made, "der Baustein hat ein benanntes Merkmal hinterlassen"
    object_id, feature_id = made[0]
    window.object_tree.select_feature(object_id, feature_id)
    return feature_id


def test_a_created_feature_offers_the_step_that_made_it(window: MainWindow) -> None:
    """§21.2: Ein erzeugtes Merkmal bietet immer den Schritt an, der es erzeugt
    hat.

    Der einzige Weg vom *Ergebnis* zurück zum *Schritt*. Ohne ihn sucht der
    Kunde im Verlauf, welcher der Einträge die Bohrung war, die er gerade
    ansieht — mit ihm zeigt er auf das Ding, das er sieht.

    Die Frage lautete lange, welche Operation fachlich auf ein fertiges
    Gewinde gehört, und ``for_feature`` gab darauf nichts zurück. Über
    ``applies_to`` wäre die Antwort eine neue Operation je Merkmalsart
    gewesen; über die Provenienz gilt sie für alle.
    """
    _insert_a_thread(window)
    menu = window.object_tree.context_menu()

    assert menu is not None
    rows = [action.text() for action in menu.actions() if not action.isSeparator()]
    assert tr("Diesen Schritt ändern") in rows, rows
    menu.deleteLater()


def test_the_offered_step_is_the_one_that_made_the_feature(window: MainWindow) -> None:
    """Und zwar der richtige: die Kennung kommt aus ``created_by``, nicht aus
    dem Ende des Stapels.

    ``SceneObject.created_by`` wird bei **jeder** Operation neu gesetzt, die
    das Objekt ausgibt — sie zeigt auf die zuletzt beteiligte. Am Merkmal
    steht der Erzeuger.
    """
    feature_id = _insert_a_thread(window)
    result = window.session.last_result
    assert result is not None
    entry = result.scene.objects[window.object_tree.selected()]
    expected = entry.features[feature_id].created_by

    asked: list[int] = []
    window.object_tree.stepRequested.connect(asked.append)
    menu = window.object_tree.context_menu()
    assert menu is not None
    for action in menu.actions():
        if action.text() == tr("Diesen Schritt ändern"):
            action.trigger()

    assert asked == [expected], (asked, expected)
    menu.deleteLater()


def test_the_menu_entry_opens_that_step(window: MainWindow) -> None:
    """Und der Klick landet im Dialog des Schritts, nicht in einem neuen.

    Die halbe Zusage wäre ein Menüeintrag, der ein Signal sendet, das niemand
    hört. Geprüft wird deshalb bis ans Ende: Der Dialog steht offen, er zeigt
    die Operation, die das Merkmal erzeugt hat, und er **ersetzt** ihren
    Schritt beim Übernehmen, statt einen zweiten anzulegen (§15.4).

    „Kein zweiter Schritt" wird an der **Schrittliste** gemessen, nicht an
    der Transaktionszahl: Die erste Fassung nagelte hier fest, dass die
    Änderung keine Transaktion anlegt — und damit den Fehler, dass sie nicht
    rücknehmbar war (Gesamtreview-b, Bericht 01, Szene 5; tests.md: „Prüft
    dieser Test eine Zusage — oder den Ist-Zustand?"). Seit Format v12 IST
    die Transaktion Teil der Zusage: eine dazu, der Stapel unverändert.
    """
    _insert_a_thread(window)
    steps_before = [entry.id for entry in window.session.project.document.ops]
    transactions_before = len(window.session.project.document.transactions)
    menu = window.object_tree.context_menu()
    assert menu is not None
    for action in menu.actions():
        if action.text() == tr("Diesen Schritt ändern"):
            action.trigger()
    menu.deleteLater()

    dialog = window._op_dialog
    assert dialog is not None, "der Schritt steht offen"
    assert dialog.spec.name == "insert_printed_thread", dialog.spec.name

    dialog.accept()
    window.session.wait_for_idle()
    document = window.session.project.document
    assert [entry.id for entry in document.ops] == steps_before, (
        "derselbe Schritt, ersetzt — kein zweiter im Stapel, keiner weg"
    )
    assert len(document.transactions) == transactions_before + 1, (
        "und die Änderung ist rücknehmbar: genau eine Transaktion dazu (§15.5)"
    )


def test_a_detected_feature_has_no_step_to_offer(window: MainWindow) -> None:
    """Ein **erkanntes** Merkmal hat keinen Erzeuger, und der Eintrag entfällt
    dort ersatzlos.

    Ein Menüeintrag, der ins Leere führt, ist schlechter als keiner (§21.2).
    Die Bohrungen dieser Platte kommen aus einer STL — sie hat niemand
    gesetzt.
    """
    window.object_tree.select_feature("obj_1", "hole_2")
    result = window.session.last_result
    assert result is not None
    feature = result.scene.objects["obj_1"].features["hole_2"]
    assert feature.created_by is None, "eingelesen, nicht erzeugt"

    menu = window.object_tree.context_menu()

    assert menu is not None
    rows = [action.text() for action in menu.actions()]
    assert tr("Diesen Schritt ändern") not in rows, rows
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

    Gezeigt wird auf die Bohrungswand (:func:`on_the_bore_wall`) und nicht
    daneben auf die Achse — dort ist keine Oberfläche, und ein Beinahe-Treffer
    war genau das, was der alte Mittelpunktsabstand lieferte.
    """
    select_plate(window)
    window.viewport.show_scene(window.session.last_result)
    window.viewport.select("obj_1")

    picked = window.viewport._feature_at(on_the_bore_wall(window, "hole_3"))
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


def test_a_new_slicer_run_replaces_the_gcode_findings(qt_app: QApplication) -> None:
    """Die G-Code-Befunde beschreiben die jeweils letzte Druckdatei (Regel 14).

    Drei Läufe trugen dreimal die Druckzeit ein — jede mit anderer Zahl und
    darum nie „dasselbe" für die Wiedererkennung (Roberts Foto, 30.08.2026).
    Ein neuer Lauf ersetzt die Herkunft ``gcode``; was aus anderer Quelle
    stammt, bleibt stehen.
    """
    from app.ui.panels import ReportPanel

    def measured(minutes: str) -> Finding:
        return Finding(
            code="slicer.handover",
            severity="info",
            message="Diese Datei kommt aus dem externen Slicer.",
            values={"minutes": minutes},
            source="gcode",
        )

    kept = Finding(
        code="arrange.below_bed",
        severity="info",
        message="Ein Objekt steckt unter dem Druckbett.",
        object_id="obj_1",
        source="internal",
    )
    panel = ReportPanel()
    try:
        panel.add_findings([kept])
        panel.add_findings([measured("18")], replacing_source="gcode")
        panel.add_findings([measured("21")], replacing_source="gcode")

        assert panel.list.count() == 2, "ein Lauf, eine Messung — plus der fremde Befund"
        left = [
            panel.list.item(row).data(Qt.ItemDataRole.UserRole) for row in range(panel.list.count())
        ]
        assert any(entry.values.get("minutes") == "21" for entry in left), "die letzte Messung"
        assert not any(entry.values.get("minutes") == "18" for entry in left), "die alte ist fort"
        assert any(entry.code == "arrange.below_bed" for entry in left), "Fremdes bleibt"
    finally:
        panel.deleteLater()


def test_a_heavier_finding_replaces_the_lighter_same_one(qt_app: QApplication) -> None:
    """Derselbe Sachverhalt, zwei Gewichte — eine Zeile, die neuere gilt.

    Die Auswertung meldet „unter dem Druckbett" als Hinweis, die Exportprüfung
    beim Schreiben als Warnung (``about_to_write``). Beide nebeneinander lasen
    sich wie zwei Probleme (Roberts Foto, 30.08.2026); die severity steht mit
    Absicht nicht in der Wiedererkennung, also entscheidet die Reihenfolge —
    und der jüngere Stand einer Sache ist der, der gilt, in beide Richtungen.
    """
    from app.ui.panels import ReportPanel

    def sunk(severity: str) -> Finding:
        return Finding(
            code="arrange.below_bed",
            severity=severity,  # type: ignore[arg-type]
            message="Ein Objekt steckt unter dem Druckbett.",
            object_id="obj_1",
            values={"axes": "z", "excess": "10,00 mm"},
        )

    panel = ReportPanel()
    try:
        panel.add_findings([sunk("info")])
        panel.add_findings([sunk("warning")])

        assert panel.list.count() == 1, "ein Sachverhalt, eine Zeile"
        entry = panel.list.item(0).data(Qt.ItemDataRole.UserRole)
        assert entry.severity == "warning", "die Datei entsteht gleich — das wiegt schwerer"

        panel.add_findings([sunk("info")])
        assert panel.list.count() == 1
        entry = panel.list.item(0).data(Qt.ItemDataRole.UserRole)
        assert entry.severity == "info", "und zurück, sobald nur noch der Hinweis gilt"

        panel.add_findings([sunk("info")])
        assert panel.list.count() == 1, "gleich schwer bleibt stehen wie bisher"
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


def test_an_orphaned_feature_keeps_its_internal_name_in_details_only(
    qt_app: QApplication,
) -> None:
    """Einsteiger lesen Wirkung und Ausweg, die Diagnose behält die Kennung.

    „Merkmal face_3 hat keinen Nachfolger" beschreibt die interne Zuordnung
    statt der Folge für den Nutzer. Die Kennung bleibt im Tooltip und in der
    zugänglichen Beschreibung erreichbar; die sichtbare Zeile nennt Körper,
    Wirkung, nächsten Klick und dass die Bearbeitung erhalten ist.
    """
    from app.core.scene import EvaluationResult
    from app.core.types import Report, Scene
    from app.ui.panels import ReportPanel

    finding = Finding(
        code="perceive.orphaned",
        severity="info",
        message="Ein Formdetail ist nach diesem Schritt nicht mehr automatisch wiederzuerkennen.",
        object_id="obj_1",
        values={"feature": "face_3"},
    )
    panel = ReportPanel()
    try:
        panel.show_result(
            EvaluationResult(
                scene=Scene(report=Report(findings=(finding,))),
                object_names={"obj_1": "Halter"},
            )
        )
        item = panel.list.item(0)
        assert "Formdetail" in item.text() and "Halter" in item.text()
        assert "Anklicken zeigt den Körper und den Schritt" in item.text()
        assert "Bearbeitung bleibt erhalten" in item.text()
        assert "Merkmal" not in item.text() and "Nachfolger" not in item.text()
        assert "face_3" not in item.text(), "interne Kennungen sind keine Kundensprache"
        assert "face_3" in item.toolTip()
        assert "face_3" in str(item.data(Qt.ItemDataRole.AccessibleDescriptionRole))
    finally:
        panel.deleteLater()


def test_a_mended_defect_keeps_its_internal_name_in_details_only(
    qt_app: QApplication,
) -> None:
    """Eine geschlossene Fehlstelle ist Wirkung, nicht `edge_loop_7`."""
    from app.core.scene import EvaluationResult
    from app.core.types import Report, Scene
    from app.ui.panels import ReportPanel

    finding = Finding(
        code="perceive.mended",
        severity="info",
        message="Eine offene Stelle ist geschlossen und damit fort.",
        object_id="obj_1",
        values={"feature": "edge_loop_7"},
    )
    panel = ReportPanel()
    try:
        panel.show_result(
            EvaluationResult(
                scene=Scene(report=Report(findings=(finding,))),
                object_names={"obj_1": "Halter"},
            )
        )
        item = panel.list.item(0)
        assert "Halter" in item.text()
        assert "Merkmal" not in item.text() and "edge_loop_7" not in item.text()
        assert "edge_loop_7" in item.toolTip()
        assert "edge_loop_7" in str(item.data(Qt.ItemDataRole.AccessibleDescriptionRole))
    finally:
        panel.deleteLater()


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
    assert is_click((100, 200), (105, 204)), (
        "fünf Pixel Wandern sind beim Klicken normal — bis zum 23.08.2026 fiel dabei "
        "die Auswahl aus"
    )
    assert not is_click((100, 200), (160, 240)), "ein Zug öffnet kein Menü"
    assert not is_click((100, 200), (100, 240)), "auch senkrecht gezogen ist gezogen"
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


def test_a_problem_note_stays_inside_the_legend_layout(qt_app: QApplication) -> None:
    """Der Problemsatz der Legende stand außerhalb jeder Anordnung.

    ``show_map`` nimmt beim Aufräumen **jedes** Element aus dem Layout — auch
    die Notiz (geschützt war nur ihr Löschen) — und hängte sie nur im
    Erfolgsfall wieder ein. „Die Analysekarte wird berechnet …" und „… zu
    groß" standen damit auf 100 × 30 Punkten Geometrie irgendwo im Nichts
    (Gesamtreview 25.08.2026, I-9). Geprüft wird die Zugehörigkeit zum
    Layout — Sichtbarkeit lügt offscreen.
    """
    from app.ui.analysis_bar import AnalysisBar

    bar = AnalysisBar(None)
    try:
        legend = bar.legend

        bar.show_problem("Für eine Analysekarte ist dieses Modell zu groß.")
        assert legend._layout.indexOf(legend.note) >= 0, "der Problemsatz braucht sein Layout"

        bar.show_legend(None)
        assert legend._layout.indexOf(legend.note) >= 0, "auch beim Leeren"
    finally:
        bar.deleteLater()


def test_an_axis_view_fits_on_the_bodies_not_the_backdrop(window: MainWindow) -> None:
    """Strg+0 bis Strg+6 rahmten die Kulisse statt des Teils.

    ``view_from`` rief ``plotter.reset_camera()`` über alle Aktoren — exakt
    der Fehler, den ``reset_camera`` daneben in eigenen Worten beschreibt und
    behebt: Ein 80-mm-Teil im 256er Bauraum wurde ein Fleck. Und ohne
    ``camera_set`` passte der nächste Kamera-Zugriff gleich noch einmal ein
    (Gesamtreview 25.08.2026, J-8). Die Achsansicht geht jetzt durch dieselbe
    Einpassung wie „Alles einpassen".
    """
    from app.ui.viewport import with_margin

    window.viewport.show_scene(window.session.last_result)
    plotter = _CameraPlotter()
    window.viewport.plotter = plotter
    window.viewport._shadow_hulls.clear()

    window.viewport.view_from("front")

    bounds = window.viewport._object_bounds()
    assert bounds is not None
    assert plotter.fitted_to == [with_margin(bounds)], "auf die Körper, mit Luft darum"
    assert plotter.camera_set, "sonst rahmt der nächste Zugriff wieder alles"


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


def test_a_body_the_user_dragged_leaves_the_camera_alone() -> None:
    """Wer selbst schiebt, behält seine Ansicht (§2.9).

    **Robert am 23.08.2026**, nachdem er einen Körper über die Platte gezogen
    hatte: „nach jedem verschieben springt die kamera und das modell immer
    komisch … kamera bei aktueller position dann immer lassen."

    Der Grund lag im zweiten Kriterium von :func:`outgrown` — *weggerückt*.
    Es ist für ein Modell gedacht, das außerhalb des Bildes liegt, und trifft
    auf jeden geschobenen Körper zu: Beim Loslassen rahmte die Kamera neu.

    **Das Größenkriterium gilt weiter**, und das ist die Grenze der Regel: Ein
    Körper, der beim Schieben plötzlich zwanzigmal so groß dasteht, ist kein
    Schieben mehr.
    """
    from app.ui.viewport import outgrown

    fitted = (-10.0, 10.0, -10.0, 10.0, 0.0, 20.0)
    dragged = (100.0, 120.0, 100.0, 120.0, 0.0, 20.0)
    grown = (-200.0, 200.0, -200.0, 200.0, 0.0, 250.0)

    assert outgrown(fitted, dragged), "ohne die Unterscheidung rahmt jedes Ziehen neu"
    assert not outgrown(fitted, dragged, moved_only=True), "geschoben heißt: Ansicht bleibt"
    assert outgrown(fitted, grown, moved_only=True), "gewachsen bleibt gewachsen"


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
    """Verbucht, wer den Picker setzt.

    **Die Attrappe spiegelt die echte API-Oberfläche, nicht die vermutete.**
    ``SetPicker`` steht hier, weil der Viewport es ruft: pyvistas Griff fragt
    bei jeder Mausbewegung ``interactor.GetPicker()``, und der Picker, den das
    Widget selbst hinstellt, trifft in dieser Umgebung nichts. Ohne diese
    Methode fielen acht Tests mit ``AttributeError`` — dieselbe Sorte, vor der
    der Docstring am Griff selbst warnt.

    ``SetInteractorStyle`` stand hier und ist es nicht mehr: Der Viewport hängt
    seinen Stil seit dem 04.09.2026 über pyvistas Eigenschaft an
    (``iren.style``), weil ein daran vorbei gesetzter Stil beim nächsten
    ``update_style()`` verlorenging — beim Doppelklick etwa, also bei jedem
    zweiten Klick der gestuften Auswahl. Verbucht wird deshalb dort, wo der
    Aufruf hingeht (:class:`_GizmoObservers`); eine Attrappe, die die alte
    Stelle weiter anbietet, verstünde einen Rückfall als Erfolg.
    """

    def __init__(self) -> None:
        self.pickers: list[object] = []

    def SetPicker(self, picker: object) -> None:  # noqa: N802 — VTK-Name
        self.pickers.append(picker)


class _GizmoObservers:
    """Der ``iren`` des Fakes: zählt Beobachter an und wieder ab.

    Der Skaliergriff meldet drei an und muss alle drei wieder loswerden —
    ein vergessener zieht am Griff der vorigen Auswahl weiter.
    """

    def __init__(self) -> None:
        self.active: dict[int, str] = {}
        self._next = 0
        self.styles: list[object] = []
        """Wer den Interaktionsstil gesetzt hat — der Weg, den der Viewport
        wirklich nimmt (siehe :class:`_GizmoInteractor`)."""

    @property
    def style(self) -> object | None:
        return self.styles[-1] if self.styles else None

    @style.setter
    def style(self, style: object) -> None:
        self.styles.append(style)

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
        # **Eine Kamera im VTK-Stil.** Seit der Griff seine Länge in
        # Bildpunkten deckelt (`_gizmo_scale_for`), fragt er über
        # `_pixels_per_mm_at` die Projektion — und die ruft `GetPosition`,
        # nicht `position`. Ohne diese drei stirbt jeder Test, der einen Griff
        # anhängt, am Massstab statt an seiner Sache.
        self.camera = SimpleNamespace(
            GetPosition=lambda: (100.0, 100.0, 100.0),
            GetFocalPoint=lambda: (0.0, 0.0, 0.0),
            GetViewUp=lambda: (0.0, 0.0, 1.0),
        )

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

    def add_lines(self, *_args: object, **_kwargs: object) -> _GizmoActor:
        # Seit dem Drehbogen (:meth:`Viewport._draw_turn_arc`) zeichnet der Zug
        # auch Linien. Eine Attrappe, der eine Methode fehlt, macht aus einer
        # neuen Anzeige einen roten Test in einer fremden Datei — hier
        # `AttributeError: '_GizmoPlotter' object has no attribute 'add_lines'`.
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


def test_leaving_the_gizmo_restores_the_global_depth_resolution(qt_app: QApplication) -> None:
    """Der Bewegen-Modus darf keine Spuren in der ganzen Ansicht hinterlassen.

    pyvistas ``AffineWidget3D`` und der nachgebaute Skaliergriff rufen
    ``SetResolveCoincidentTopologyToPolygonOffset()`` — eine **statische**
    VTK-Einstellung, die prozessweit jeden Mapper trifft (gemessen: über einen
    zweiten, unbeteiligten Mapper gelesen). Ohne Rückstellung stachen nach dem
    ersten Besuch im Bewegen-Modus die Kantenlinien aller Körper dauerhaft
    durch die Flächen — als Striche an den Kantenmitten, die den Modus
    überlebten und in keiner Aktor-Eigenschaft standen (Gesamtreview
    25.08.2026, A3). Der Test stellt die Einstellung so um, wie das echte
    Widget es tut, und verlangt sie nach dem Abschalten zurück.
    """
    from vtkmodules.vtkRenderingCore import vtkMapper

    viewport, _plotter = _gizmo_viewport()
    before = int(vtkMapper.GetResolveCoincidentTopology())
    try:
        viewport.select("obj_1")
        viewport.set_gizmo(True)
        vtkMapper.SetResolveCoincidentTopologyToPolygonOffset()
        viewport.set_gizmo(False)

        assert int(vtkMapper.GetResolveCoincidentTopology()) == before
    finally:
        vtkMapper.SetResolveCoincidentTopology(before)
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
        assert len(plotter.iren.active) == 4, (
            "drei Beobachter des Skaliergriffs — Bewegen, Drücken, Loslassen — "
            "und der vierte, der den Drehgriff auf seine Raste zieht"
        )
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
        # **Beide Attrappen**, seit ``set_gizmo`` zwei Fragen stellt: wo der
        # Griff *sitzt* (``gizmo_feature``, jedes versetzbare Merkmal) und was
        # er *tut* (``gizmo_target``, nur die Fläche mit Press/Pull). Nur die
        # zweite zu setzen liess die erste die echte Auswahl lesen — leer —,
        # und der Würfel kam an einer Fläche zurück, an der er nichts zu
        # suchen hat.
        viewport.gizmo_feature = lambda: face  # type: ignore[method-assign]
        viewport.gizmo_target = lambda: face  # type: ignore[method-assign]
        viewport.set_gizmo(True)
        assert viewport._scale_handle is None, "eine Fläche hat keine Größe zu ändern"
        # **Eine Marke und nicht drei**, seit die Beschriftung sagt, was der
        # Griff an einer Fläche kann: vor und zurück. Drei Achsenbuchstaben
        # versprachen dort drei Richtungen, von denen zwei verfallen — wer
        # nicht aus dem CAD kommt, zieht in eine davon und sieht nichts
        # passieren. Der Name der Fläche steht in der Statusleiste, wo Qt
        # zeichnet: VTK nimmt in dieser Beschriftung kein Zeichen außerhalb
        # von ASCII, und die Flächennamen werden übersetzt.
        assert viewport._gizmo_label_data.n_points == 1, "an der Fläche eine Richtung"
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
        assert len(plotter.iren.styles) == 2, "und das Schema ist beide Male zurück"
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
        assert plotter.iren.styles == [], "bis hierhin hat niemand den Stil angefasst"

        viewport._on_gizmo_released(translation((5.0, 0.0, 0.0)))
        assert len(plotter.iren.styles) == 1, "der eigene Stil ist zurück"

        viewport._on_gizmo_released(translation((0.2, 0.0, 0.0)))
        assert len(plotter.iren.styles) == 2, "auch ein Zug unter der Fangschwelle"
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


def test_a_click_ignores_hidden_bodies(window: MainWindow) -> None:
    """§18.8: Ausblenden nimmt den Körper aus dem Bild — und damit aus dem Klick.

    ``_object_at`` prüfte nur den Hüllquader: Ein Klick wählte einen
    ausgeblendeten Körper, der Objektbaum sprang dorthin, und die nächste
    Operation traf ein Teil, das niemand sieht (Gesamtreview 25.08.2026, J-1).
    ``_nearest_mesh`` hatte dieselbe Lücke — es beliefert Messen und Bemalen.
    """
    window.viewport.show_scene(window.session.last_result)
    entry = window.session.last_result.scene.objects["obj_1"]
    centre = entry.mesh.bounds.centre
    window.viewport.set_hidden(frozenset({"obj_1"}))

    assert window.viewport._object_at(centre) is None
    assert window.viewport._nearest_mesh(centre) is None


def test_a_click_ignores_bodies_of_other_plates(window: MainWindow) -> None:
    """§25: Wer eine einzelne Platte ansieht, kann nur auf ihr wählen.

    Die Körper der anderen Platten liegen in Szenenkoordinaten am selben Ort —
    genau der Grund für die Plattenverschiebung. Ohne den Filter wählte ein
    Klick das unsichtbare Teil der fremden Platte (Gesamtreview J-1).
    """
    window.viewport.show_scene(window.session.last_result)
    entry = window.session.last_result.scene.objects["obj_1"]
    centre = entry.mesh.bounds.centre
    window.viewport.set_plate(entry.plate + 1)

    assert window.viewport._object_at(centre) is None
    assert window.viewport._nearest_mesh(centre) is None


def test_clicking_needs_no_overlay_switch(window: MainWindow) -> None:
    """Die Merkmalsbeschriftung schaltet Beschriftungen, nicht das Anklicken.

    §18.5 nennt das Zeigen auf ein Merkmal die wichtigste Einzelfunktion — sie
    hinter einem Häkchen zu verstecken hieße, sie für jeden abzuschalten, der
    das Häkchen nicht findet.
    """
    window.viewport.show_scene(window.session.last_result)
    window.viewport.set_feature_overlay(False)

    assert window.viewport._feature_at(on_the_bore_wall(window, "hole_3")) == "hole_3"


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

    **Der mittlere Zweig las sich einmal „sonst darüber", und das war ein Wort
    zu viel.** Das Ziel dieser Rechnung ist, die Liste im *Fenster* zu halten;
    dass sie dabei über dem Feld endet statt an dessen Unterkante, war die
    naheliegende Lesart von „nicht darunter" und keine eigene Zusage. Sie hat
    die Liste unbedienbar gemacht: Verschoben wird erst, **nachdem** Qt sie
    geöffnet hat, und wer eine Liste öffnet, hält die Maustaste über dem Feld.
    Endet sie an der Oberkante, liegt der Zeiger beim Loslassen außerhalb — und
    Qt schließt eine Aufklappliste, die ihren Zeiger verloren hat. Sie ging auf
    und sofort wieder zu (Roberts Fehlerbericht, 30.08.2026; an seiner
    Fenstergröße gerechnet lag der Zeiger bei 777 und die Liste endete bei
    767). Das Feld zu überdecken kostet nichts: Was dort steht, steht auch in
    der Liste, als der gewählte Eintrag.
    """
    from PySide6.QtCore import QRect

    from app.ui.tool_strip import list_top

    window = QRect(100, 100, 900, 600)  # unten bei 699

    roomy = QRect(120, 200, 160, 24)  # unten bei 223
    assert list_top(roomy, 200, window) == roomy.bottom(), "passt darunter — dann darunter"

    cramped = QRect(120, 640, 160, 24)  # unten bei 663, darunter nur 36
    assert list_top(cramped, 200, window) == cramped.bottom() - 200, (
        "sonst nach oben — bündig mit der Unterkante des Feldes, nicht darüber"
    )

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

    **Zwei Klicks statt einem**, seit die Auswahltiefe gestuft ist (§18.5): Der
    erste meint das Teil, der zweite die Bohrung darin. Die Aussage dieses
    Tests ist davon unberührt — sie betrifft die *Reihenfolge* im Klick, der
    ein Merkmal wählt, und die ist dieselbe geblieben.
    """
    entry = window.session.last_result.scene.objects["obj_1"]
    hole = next((name for name, feature in entry.features.items() if feature.kind == "hole"), None)
    assert hole is not None, "die Platte aus dem Korpus hat Bohrungen"
    wall = on_the_bore_wall(window, hole)

    window.viewport._select_at(wall)  # erste Stufe: der Körper

    picked: list[str] = []
    features: list[str] = []
    window.viewport.objectPicked.connect(picked.append)
    window.viewport.featurePicked.connect(features.append)

    window.viewport._select_at(wall)  # zweite Stufe: das Merkmal darin

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


def test_a_flood_of_identical_findings_becomes_one_line_that_counts_them(
    qt_app: QApplication,
) -> None:
    """118 wortgleiche Zeilen begraben die fünf, die etwas Eigenes sagen.

    Nach dem Löschen früher Verlaufsschritte meldete ``perceive.orphaned``
    jedes verlorene Formdetail einzeln — 118 wortgleiche Zeilen — und die zwei
    Warnungen dazwischen fand niemand. Gebündelt wird in der Anzeige, nicht im
    Kern: Agent, Kommandozeile und Steckbrief lesen weiter jeden Befund
    einzeln.
    """
    from app.core.scene import EvaluationResult
    from app.core.types import Report, Scene
    from app.ui.panels import ReportPanel

    orphan_text = (
        "Ein Formdetail ist nach diesem Schritt nicht mehr automatisch "
        "wiederzuerkennen. Anklicken zeigt den Körper und den Schritt; die "
        "Bearbeitung bleibt erhalten."
    )
    findings = (
        *(
            Finding(
                code="perceive.orphaned",
                severity="info",
                message=orphan_text,
                object_id="obj_1",
                values={"feature": f"hole_{n}"},
            )
            for n in range(118)
        ),
        Finding(code="mesh.thin_wall", severity="warning", message="Eine Wand ist zu dünn"),
        # Ein Kernbefund darf selbst einen ``count``-Wert führen („12 kleine
        # Objekte übergangen") — er bleibt eine Zeile und zählt als eine.
        Finding(
            code="ingest.small_components",
            severity="warning",
            message="Kleine Objekte wurden übergangen",
            values={"count": 12},
        ),
        *(
            Finding(code="mesh.gap_closed", severity="info", message="Eine Lücke wurde geschlossen")
            for _ in range(3)
        ),
    )
    panel = ReportPanel()
    try:
        panel.show_result(
            EvaluationResult(
                scene=Scene(report=Report(findings=findings)),
                object_names={"obj_1": "Griff"},
            )
        )

        texts = [panel.list.item(row).text() for row in range(panel.list.count())]
        assert len(texts) == 6, f"eine Sammelzeile statt 118, der Rest bleibt: {texts!r}"

        bundle = [text for text in texts if "118 Formdetails" in text]
        assert bundle == [
            "118 Formdetails sind nach diesem Schritt nicht mehr automatisch "
            "wiederzuerkennen. Anklicken zeigt den Körper und den Schritt; die "
            "Bearbeitung bleibt erhalten. — Griff"
        ], "Zahl, nächster Klick und verständlicher Körpername stehen sichtbar an der Zeile"

        row = texts.index(bundle[0])
        tooltip = panel.list.item(row).toolTip()
        assert "hole_0" in tooltip, "die Betroffenen bleiben erreichbar"
        assert "+103" in tooltip, "und der Rest hinter den ersten fünfzehn wird beziffert"

        stored: Finding = panel.list.item(row).data(Qt.ItemDataRole.UserRole)
        assert stored.values.get("count") == 118

        # Die Kopfzeile zählt die Befunde, nicht die Zeilen — und der
        # ``count``-Wert des Kernbefunds bläht sie nicht auf.
        summary = panel.summary.text()
        assert f"2 × {tr('Warnung')}" in summary, summary
        assert f"121 × {tr('Hinweis')}" in summary, summary
    finally:
        panel.deleteLater()


def test_a_bundle_survives_findings_that_arrive_later(qt_app: QApplication) -> None:
    """Der Nachschub-Weg zerlegte die Sammelzeile — und bündelte selbst nie.

    ``add_findings`` (G-Code-Gegenprobe, Kollisions-, Exportprüfung) baute
    die Liste über die *Zeilen* neu statt über die Befunde: ``_resort`` las
    das ersetzte Bündel-Finding aus dem ``UserRole`` und hängte es als
    Einzelzeile wieder an — die Kopfzeile zählte 1 statt 118, und die
    Namensliste aus dem Tooltip stand plötzlich in der Zeile. Seitdem hält
    das Panel die rohen Befunde und baut Zeilen immer über dieselbe
    Bündelung. Der Weg-3-Fall aus dem Register ist genau diese Folge:
    erst die Auswertung mit den Waisen, dann die Gegenprobe obendrauf.
    """
    from app.core.scene import EvaluationResult
    from app.core.types import Report, Scene
    from app.ui.panels import ReportPanel

    orphan_text = (
        "Ein Formdetail ist nach diesem Schritt nicht mehr automatisch "
        "wiederzuerkennen. Anklicken zeigt den Körper und den Schritt; die "
        "Bearbeitung bleibt erhalten."
    )
    orphans = tuple(
        Finding(
            code="perceive.orphaned",
            severity="info",
            message=orphan_text,
            values={"feature": f"hole_{n}"},
        )
        for n in range(118)
    )
    panel = ReportPanel()
    try:
        panel.show_result(EvaluationResult(scene=Scene(report=Report(findings=orphans))))
        assert panel.list.count() == 1

        panel.add_findings(
            [
                Finding(
                    code="gcode.print_time",
                    severity="info",
                    message="Die Druckzeit steht in der Druckdatei",
                    source="gcode",
                )
            ]
        )
        texts = [panel.list.item(row).text() for row in range(panel.list.count())]
        assert len(texts) == 2, f"die Sammelzeile übersteht den Nachschub: {texts!r}"
        assert any(text.startswith("118 Formdetails") for text in texts)
        assert f"119 × {tr('Hinweis')}" in panel.summary.text(), panel.summary.text()

        # Der Nachschub-Weg dedupliziert identische Kernbefunde. Vier
        # wortgleiche Warnungen ohne weitere Unterscheidungsmerkmale sind
        # deshalb genau eine Zeile und zählen auch nur einmal.
        panel.add_findings(
            [
                Finding(
                    code="check.collision",
                    severity="warning",
                    message="Zwei Objekte berühren sich",
                )
                for _ in range(4)
            ]
        )
        texts = [panel.list.item(row).text() for row in range(panel.list.count())]
        assert texts.count("Zwei Objekte berühren sich") == 1, texts
        assert len(texts) == 3, texts
        assert f"1 × {tr('Warnung')}" in panel.summary.text(), panel.summary.text()
    finally:
        panel.deleteLater()


def test_a_bundle_never_crosses_the_body_or_step_its_click_will_show(
    qt_app: QApplication,
) -> None:
    """Eine kurze Zeile darf nicht auf einen zufälligen Körper zeigen.

    Die erste Bündelung gruppierte nur nach Kennung, Schwere und Wortlaut. Acht
    Waisen aus zwei Körpern und zwei Schritten wurden eine Zeile; deren
    künstlicher Befund verlor den Körper, behielt aber den ersten Schritt. Ein
    Klick wählte deshalb den gerade markierten, womöglich falschen Körper und
    sprang im Verlauf zum ersten zufälligen Schritt.

    Der echte Einzelklick auf jede sichtbare Sammelzeile muss genau die
    Navigationsdaten ausgeben, die für alle ihre Mitglieder gelten.
    """
    from PySide6.QtTest import QTest

    from app.core.scene import EvaluationResult
    from app.core.types import Report, Scene
    from app.ui.panels import ReportPanel

    findings = tuple(
        Finding(
            code="perceive.orphaned",
            severity="info",
            message=(
                "Ein Formdetail ist nach diesem Schritt nicht mehr automatisch "
                "wiederzuerkennen. Anklicken zeigt den Körper und den Schritt; die "
                "Bearbeitung bleibt erhalten."
            ),
            object_id=object_id,
            op_id=op_id,
            feature_ids=(f"face_{index}",),
            values={"feature": f"face_{index}"},
            location=(float(index), 0.0, 0.0),
        )
        for object_id, op_id in (("obj_1", 7), ("obj_2", 11))
        for index in range(4)
    )
    panel = ReportPanel()
    activated: list[Finding] = []
    panel.findingActivated.connect(activated.append)
    try:
        panel.resize(420, 520)
        panel.show_result(
            EvaluationResult(
                scene=Scene(report=Report(findings=findings)),
                object_names={"obj_1": "Griff", "obj_2": "Deckel"},
            )
        )
        panel.show()
        qt_app.processEvents()

        assert panel.list.count() == 2, "je Körper und Schritt steht eine ehrliche Sammelzeile"
        texts = [panel.list.item(row).text() for row in range(panel.list.count())]
        assert texts[0] != texts[1], "gleich große Bündel müssen sichtbar unterscheidbar bleiben"
        assert "Griff" in texts[0] and f"{tr('Schritt')} 7" in texts[0]
        assert "Deckel" in texts[1] and f"{tr('Schritt')} 11" in texts[1]
        for row, expected in enumerate((("obj_1", 7), ("obj_2", 11))):
            item = panel.list.item(row)
            bundled: Finding = item.data(Qt.ItemDataRole.UserRole)
            assert (bundled.object_id, bundled.op_id) == expected
            assert bundled.feature_ids == (), "verschiedene verlorene Details sind kein Einzelziel"
            assert bundled.location is None, (
                "der erste von vier Orten wäre ein erfundener Sammelort"
            )
            QTest.mouseClick(
                panel.list.viewport(),
                Qt.MouseButton.LeftButton,
                pos=panel.list.visualItemRect(item).center(),
            )
            assert (activated[-1].object_id, activated[-1].op_id) == expected
    finally:
        panel.deleteLater()


def test_a_bundle_never_discards_different_actions(qt_app: QApplication) -> None:
    """Wortgleiche Fehler mit verschiedenen Auswegen bleiben getrennt.

    Der erste Gruppenschlüssel kannte die Vorschläge nicht. Acht Fehler wurden
    eine Zeile und der künstliche Befund bekam gar keine Handlung, sobald sich
    nur ein Vorschlag unterschied. Damit verlor eine verdichtete Fehlerzeile
    genau den Ausweg, den Regel 17 verlangt.
    """
    from app.core.scene import EvaluationResult
    from app.core.types import Report, Scene
    from app.ui.panels import ReportPanel

    first = Action(id="first_way", label="Ersten Ausweg verwenden")
    second = Action(id="second_way", label="Zweiten Ausweg verwenden")
    findings = tuple(
        Finding(
            code="probe.actionable",
            severity="error",
            message="Dieser Wert braucht eine Korrektur.",
            object_id="obj_1",
            op_id=4,
            suggestions=(action,),
        )
        for action in (first, second)
        for _ in range(4)
    )
    panel = ReportPanel()
    try:
        panel.show_result(EvaluationResult(scene=Scene(report=Report(findings=findings))))

        assert panel.list.count() == 2, "jeder andere Ausweg bildet ein eigenes Bündel"
        kept = {
            panel.list.item(row).data(Qt.ItemDataRole.UserRole).suggestions
            for row in range(panel.list.count())
        }
        assert kept == {(first,), (second,)}, "keine Fehlerzeile verliert ihre Handlung"
    finally:
        panel.deleteLater()


def test_a_generic_bundle_never_discards_different_places(qt_app: QApplication) -> None:
    """Ortsgebundene Warnungen bleiben je Ort und Merkmal anklickbar."""
    from app.core.scene import EvaluationResult
    from app.core.types import Report, Scene
    from app.ui.panels import ReportPanel

    findings = tuple(
        Finding(
            code="probe.located",
            severity="warning",
            message="Diese Stelle braucht Aufmerksamkeit.",
            object_id="obj_1",
            op_id=4,
            feature_ids=(f"face_{index}",),
            location=(float(index), 0.0, 0.0),
        )
        for index in range(4)
    )
    panel = ReportPanel()
    try:
        panel.show_result(EvaluationResult(scene=Scene(report=Report(findings=findings))))

        assert panel.list.count() == 4, "vier echte Stellen dürfen nicht zu keinem Ort werden"
        for row, expected in enumerate(findings):
            shown: Finding = panel.list.item(row).data(Qt.ItemDataRole.UserRole)
            assert shown.location == expected.location
            assert shown.feature_ids == expected.feature_ids
    finally:
        panel.deleteLater()


def test_a_generic_bundle_never_discards_different_values(qt_app: QApplication) -> None:
    """Messwerte trennen Gruppen; ein gemeinsamer Wert bleibt im Detail."""
    from app.core.scene import EvaluationResult
    from app.core.types import Report, Scene
    from app.ui.panels import ReportPanel

    def shown(values: tuple[float | str | TranslatableText, ...]) -> list[Finding]:
        findings = tuple(
            Finding(
                code="probe.measured",
                severity="warning",
                message="Diese Stelle ist zu dünn.",
                object_id="obj_1",
                op_id=4,
                values={"wall_mm": value},
            )
            for value in values
        )
        panel.show_result(EvaluationResult(scene=Scene(report=Report(findings=findings))))
        return [
            panel.list.item(row).data(Qt.ItemDataRole.UserRole) for row in range(panel.list.count())
        ]

    panel = ReportPanel()
    try:
        separate = shown((0.4, 0.5, 0.6, 0.7))
        assert len(separate) == 4, "vier verschiedene Messungen sind vier Aussagen"
        assert [entry.values["wall_mm"] for entry in separate] == [0.4, 0.5, 0.6, 0.7]

        typed = shown(
            (
                1.0,
                "1.0",
                TranslatableText("Gleicher sichtbarer Text", "erster Kontext"),
                TranslatableText("Gleicher sichtbarer Text", "zweiter Kontext"),
            )
        )
        assert len(typed) == 4, (
            "Typ und Übersetzungskontext gehören zur Rohidentität; "
            "die aktuelle Anzeige darf keine Werte verschlucken"
        )

        bundled = shown((0.6, 0.6, 0.6, 0.6))
        assert len(bundled) == 1, "wirklich identische Messungen dürfen eine Zeile werden"
        assert bundled[0].values["wall_mm"] == 0.6, "der gemeinsame Messwert bleibt im Detail"
    finally:
        panel.deleteLater()


def test_identical_findings_below_the_threshold_keep_their_own_lines(
    qt_app: QApplication,
) -> None:
    """Drei gleiche Zeilen sind lesbar, erst ab vier wird gebündelt.

    Und gleicher Wortlaut mit anderem Schweregrad gehört nie ins selbe
    Bündel — eine Warnung, die in 118 Hinweisen aufgeht, wäre verschluckt.
    """
    from app.core.scene import EvaluationResult
    from app.core.types import Report, Scene
    from app.ui.panels import ReportPanel

    def shown(findings: tuple[Finding, ...]) -> list[str]:
        panel.show_result(EvaluationResult(scene=Scene(report=Report(findings=findings))))
        return [panel.list.item(row).text() for row in range(panel.list.count())]

    def echo(count: int, severity: str = "info") -> tuple[Finding, ...]:
        return tuple(
            Finding(
                code="mesh.gap_closed", severity=severity, message="Eine Lücke wurde geschlossen"
            )  # type: ignore[arg-type]
            for _ in range(count)
        )

    def orphans(count: int) -> tuple[Finding, ...]:
        return tuple(
            Finding(
                code="perceive.orphaned",
                severity="info",
                message=(
                    "Ein Formdetail ist nach diesem Schritt nicht mehr automatisch "
                    "wiederzuerkennen. Anklicken zeigt den Körper und den Schritt; die "
                    "Bearbeitung bleibt erhalten."
                ),
                object_id="obj_1",
                op_id=7,
                values={"feature": f"face_{index}"},
            )
            for index in range(count)
        )

    panel = ReportPanel()
    try:
        assert len(shown(echo(3))) == 3, "unter der Schwelle bleibt jede Zeile stehen"
        assert len(shown(echo(4))) == 1, "ab vier wird gebündelt"
        assert len(shown(echo(4) + echo(1, "warning"))) == 2, (
            "gleicher Wortlaut, anderer Schweregrad — zwei Zeilen"
        )
        assert shown(orphans(1))[0].startswith("Ein Formdetail ist")
        assert shown(orphans(2))[0].startswith("2 Formdetails sind")
        assert shown(orphans(4))[0].startswith("4 Formdetails sind")
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
        assert "bearbeitbare Flächen und Kanten" in action.toolTip(), (
            f"{spec.name} sagt nicht, was ihm fehlt: {action.toolTip()!r}"
        )

    visible_labels = [
        action.text()
        for entry in menu.actions()
        for action in (entry.menu().actions() if entry.menu() else [entry])
        if not action.isSeparator()
    ]
    assert len(visible_labels) == len(set(visible_labels)), (
        "zusammengelegte Rechenwege stehen als doppelte Handlung im Kontextmenü"
    )

    # Und was auf einem Netz kann, bleibt bedienbar — sonst wäre die Prüfung
    # eine Sperre und keine Auskunft.
    plain = [spec for spec in window.object_tree.operations_for_object() if not spec.requires_kind]
    enabled = [str(spec.title) for spec in plain if actions.get(str(spec.title)) is not None]
    assert any(actions[title].isEnabled() for title in enabled), "alles gesperrt wäre kein Menü"
    menu.deleteLater()


def test_the_context_menu_actually_shows_the_reason_it_wrote(window: MainWindow) -> None:
    """Der Satz stand da und war unsichtbar.

    ``QMenu`` zeigt Tooltips von Haus aus **nicht** — ``toolTipsVisible`` ist
    falsch, bis jemand es setzt. Die Menüleiste tut das an ihren drei Stellen;
    das Kontextmenü am Körper tat es nicht. Damit war die ganze Kette umsonst:
    ``kind_requirement`` formuliert den Grund, ``_add_operation`` schreibt ihn
    an die Handlung, und Qt wirft ihn weg, bevor ihn jemand liest.

    Der bestehende Test daneben prüft den **Wert** von ``toolTip()``. Der war
    immer richtig — er stand nur an einem Menü, das keine Tooltips anzeigt.
    Eine Zusage über einen Text, ohne die Zusage, dass er erscheint, ist die
    Hälfte einer Prüfung.

    Auch für die Untermenüs: Am ganzen Körper sind es siebenundfünfzig
    Operationen, die stehen dann gruppiert in eigenen ``QMenu`` — und ein
    Untermenü erbt die Eigenschaft nicht.
    """
    select_plate(window)
    menu = window.object_tree.context_menu()
    assert menu is not None

    assert menu.toolTipsVisible(), "das Kontextmenü zeigt keine Tooltips an"
    for entry in menu.actions():
        submenu = entry.menu()
        if submenu is not None:
            assert submenu.toolTipsVisible(), (
                f"das Untermenü {entry.text()!r} zeigt keine Tooltips an"
            )

    # Gegenprobe: Ohne einen gesperrten Eintrag mit Grund prüfte der Test eine
    # Eigenschaft, die niemanden interessiert.
    locked = [
        action
        for entry in menu.actions()
        for action in (entry.menu().actions() if entry.menu() else [entry])
        if not action.isEnabled() and "bearbeitbare Flächen und Kanten" in action.toolTip()
    ]
    assert locked, "kein gesperrter Eintrag mit Grund — dann sagt der Test nichts"
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


def test_the_layer_readout_follows_the_unit(qt_app: object) -> None:
    """Die Zeile der Schichtanalyse baute ihre Einheit selbst.

    `f"{layer.area:.0f} mm²"` stand dort, und daneben `z {length(layer.z)}` —
    dieselbe Zeile mit einer Länge, die umschaltet, und einer Fläche, die es
    nicht tut. Geprüft wird an der echten Leiste, nicht an einem nachgebauten
    Satz.
    """
    from app.core.types import LayerInfo, SliceResult
    from app.ui.analysis_bar import LayerBar
    from app.ui.labels import set_display_unit

    bar = LayerBar()
    # Eingeschaltet wie im Fenster, sonst bleibt die Zeile leer.
    bar.set_active(True)
    layer = LayerInfo(z=1.0, contours=(), area=4334.0, overhang_area=0.0, islands=(), min_width=1.0)
    bar.show_result(SliceResult(layers=(layer,), support_volume=0.0, first_layer_area=4334.0))

    try:
        set_display_unit("mm")
        bar._show_readout()
        assert "4334 mm²" in bar.readout.text(), bar.readout.text()

        set_display_unit("in")
        bar._show_readout()
        assert "6,72 in²" in bar.readout.text(), bar.readout.text()
        assert "mm²" not in bar.readout.text()
    finally:
        set_display_unit("mm")


def test_a_selected_body_moves_by_dragging_it(window: MainWindow) -> None:
    """Auswählen, anfassen, ziehen — ohne vorher ein Werkzeug zu holen.

    **Robert am 23.08.2026:** „Das Verschieben eines 3D-Modellkörpers ist noch
    bisschen kompliziert, man soll es auswählen und dann zuschlagen ziehen
    verschieben können oder prüfen wie andere CAD Programme das machen."

    Der Weg war: Körper anklicken → *Bewegen* in der Werkzeugzeile → am Griff
    ziehen. Drei Schritte, und der mittlere ist der, den niemand erwartet: In
    PrusaSlicer, OrcaSlicer und Cura zieht man ein Objekt direkt. Ihre Gizmos
    (nachgelesen in ihren eigenen Sprachkatalogen: „Gizmo move: Press to snap
    by 1mm", „Gizmo-Move") sind für das **Genaue** da — für achsweises
    Verschieben und Rasten —, nicht für den ersten Zug.

    **In der Bettebene und nicht frei im Raum.** Ein Körper, den man beim
    Ziehen unbeabsichtigt anhebt, liegt danach nicht mehr auf dem Bett, und das
    merkt man erst beim Schneiden. Die Höhe bleibt dem Griff und dem Dialog.

    **Ein Zug, ein Schritt im Verlauf** (Regel 2, §15.5): Was während des Zugs
    im Bild passiert, ist eine Vorschau; die Operation entsteht beim Loslassen.
    """
    select_plate(window)
    viewport = window.viewport
    chosen = window.object_tree.selected()
    assert chosen is not None, "ohne Auswahl prüft der Test nichts"

    steps: list[Any] = []
    viewport.transformDragged.connect(steps.append)

    # **Über den Weltpunkt und nicht über Bildschirmkoordinaten.** Offscreen
    # rendert VTK nicht, und ein Picker über einem nie gezeichneten Bild trifft
    # nichts — ein Test mit Pixelkoordinaten prüfte hier die Testumgebung.
    entry = window.session.last_result.scene.objects[chosen]
    middle = entry.mesh.bounds.centre

    assert viewport.begin_body_drag_at(middle), "auf dem gewählten Körper beginnt ein Zug"
    viewport.continue_body_drag_at((middle[0] + 12.0, middle[1] + 5.0))
    viewport.finish_body_drag()

    assert steps, "aus dem Zug wurde kein Schritt"
    versatz = steps[-1].offset
    assert versatz[0] != 0.0 or versatz[1] != 0.0, f"nichts bewegt: {versatz}"
    assert versatz[2] == 0.0, f"die Höhe gehört dem Griff, nicht dem Zug: {versatz}"


def test_a_drag_beside_the_body_still_turns_the_camera(window: MainWindow) -> None:
    """Neben dem Körper bleibt Ziehen, was es war.

    Sonst wäre das Verschieben ein Modus mit anderem Namen: Wer die Ansicht
    drehen will, dürfte nicht erst wegklicken müssen. Dieselbe Trennung machen
    die Slicer — auf dem Objekt bewegt es, daneben führt es die Kamera.
    """
    select_plate(window)
    viewport = window.viewport

    # Weit außerhalb: dort liegt kein Körper.
    assert not viewport.begin_body_drag_at((5000.0, 5000.0, 5000.0)), "daneben beginnt kein Zug"
    assert not viewport.begin_body_drag_at(None), "und ohne Treffer erst recht nicht"


def test_a_click_into_a_hole_selects_the_hole(window: MainWindow) -> None:
    """Wer eine Bohrung sieht und hineinklickt, meint sie.

    **Robert am 23.08.2026:** „Wenn ich ein 3D Modell auswähle und dann eine
    Bohrung in dem 3D Modell auswähle, wird die Bohrung nicht selektiert und
    nicht hervorgehoben." Auf die Frage, ob er auf die Wand oder ins Loch
    klickt: „beides, es sollte in beiden fällen gehen."

    **Der Klick auf die Wand ging schon**; gemessen trifft ``_feature_at`` dort
    das Merkmal. Der Klick ins Loch nicht — dort ist kein Dreieck der Bohrung,
    der Strahl trifft die Fläche dahinter oder die Platte darunter, und von der
    Bohrungsmitte aus ist ihre Wand einen **Radius** entfernt: bei dieser
    Bohrung 2,6 mm gegen 0,95 mm Reichweite.

    Die Reichweite dafür zu vergrößern wäre falsch — sie beantwortet „wie weit
    daneben zählt noch als darauf", und die Antwort soll klein bleiben. Gefragt
    wird stattdessen etwas anderes: **Steht der Punkt innerhalb des
    Bohrungszylinders?**
    """
    select_plate(window)
    viewport = window.viewport
    entry = window.session.last_result.scene.objects[window.object_tree.selected()]
    bohrungen = [name for name, feature in entry.features.items() if feature.kind == "hole"]
    assert bohrungen, "ohne Bohrung prüft dieser Test nichts"

    bohrung = entry.features[bohrungen[0]]
    mitte = bohrung.params["centre"]
    radius = float(bohrung.params["diameter"]) / 2.0

    auf_der_wand = (mitte[0] + radius, mitte[1], mitte[2])
    im_loch = (mitte[0], mitte[1], mitte[2])
    assert viewport._feature_at(auf_der_wand) == bohrungen[0], "auf der Wand traf es schon"
    assert viewport._feature_at(im_loch) == bohrungen[0], "und jetzt auch mitten hinein"

    # **Die Gegenprobe, ohne die der Test nichts wert wäre**: Ein Klick neben
    # der Bohrung darf sie nicht wählen. Sonst hätte die neue Frage nur die
    # Reichweite auf den ganzen Körper ausgedehnt.
    daneben = (mitte[0] + radius * 4.0, mitte[1] + radius * 4.0, mitte[2])
    assert viewport._feature_at(daneben) != bohrungen[0], (
        "vier Radien daneben ist nicht mehr diese Bohrung"
    )


class _FakeInteractor:
    """Nur so viel Interactor, wie ``_left_down`` und Verwandte lesen."""

    def __init__(self) -> None:
        self.position = (100, 200)
        self.shift = 0

    def GetEventPosition(self) -> tuple[int, int]:  # noqa: N802 - VTK gibt den Namen
        return self.position

    def GetShiftKey(self) -> int:  # noqa: N802 - VTK gibt den Namen
        return self.shift


def _style_with_mouse(starts: bool = True) -> tuple[Any, _FakeInteractor, list[Any]]:
    """Ein Interaktionsstil, dessen Maus sich von Hand führen lässt.

    Die Kamera-Methoden werden stillgelegt: ohne echten Interactor stürzt VTK
    in ``EndPan`` ab (gemessen, Segmentation fault). Geprüft wird hier die
    Verdrahtung, nicht VTKs Kameraführung.
    """
    from app.ui.viewport import _InteractorStyle

    seen: list[Any] = []
    style = _InteractorStyle(
        None,
        "slicer",
        None,
        lambda x, y: seen.append(("pick", x, y)),
        on_body_drag=lambda phase, x, y: (seen.append((phase, x, y)), starts)[1],
    )
    interactor = _FakeInteractor()
    style.GetInteractor = lambda: interactor
    for name in ("EndPan", "EndRotate", "StartPan", "StartRotate", "OnMouseMove"):
        setattr(style, name, lambda *_: None)
    return style, interactor, seen


def test_the_left_button_reaches_the_body_drag(qt_app: QApplication) -> None:
    """Die Maus ruft den Zug — und nicht bloß die Methode dahinter.

    **Robert am 23.08.2026:** „wenn ich das modell mit linksklick auswähle kann
    ich es immer noch nicht verschieben."

    Alles unterhalb war gebaut: ``begin_body_drag``, ``begin_body_drag_at``,
    ``continue_body_drag``, ``finish_body_drag``, der Rückruf ``on_body_drag``
    und seine Übergabe an ``_ViewCallbacks``. Nur stand ``on_body_drag`` im
    175-Zeilen-Rumpf des Interaktionsstils **genau einmal**: als Parameter. Die
    Kette endete eine Ebene vor der Maus.

    **Warum kein Test das fing**, obwohl es einen gab: Er setzte bei
    ``begin_body_drag_at`` an, also hinter der Lücke, und begründete es
    richtig — offscreen rendert VTK nicht, ein Picker über einem nie
    gezeichneten Bild trifft nichts. Eine zutreffende Begründung, die eine
    Lücke deckt, ist schwerer zu sehen als eine falsche. Testart **Anschluss**
    (AGENTS.md): nicht „der Viewport kann ziehen", sondern „die Maus tut es".
    """
    style, interactor, seen = _style_with_mouse()

    style._left_down()
    interactor.position = (160, 250)
    style._mouse_move()
    style._left_up()

    assert [entry[0] for entry in seen] == ["ready", "start", "move", "end"], (
        "Drücken, Ziehen und Loslassen erreichen den Rückruf nicht vollständig"
    )
    assert seen[1][1:] == (100, 200), (
        "der Zug beginnt nicht dort, wo gedrückt wurde — der Körper spränge um die "
        "bereits zurückgelegte Strecke"
    )


def test_a_click_without_dragging_still_selects(qt_app: QApplication) -> None:
    """Und ein Klick bleibt ein Klick — sonst wäre die Bohrung nicht mehr wählbar.

    Der Zug beginnt schon beim Drücken, weil erst dann feststeht, ob dort der
    gewählte Körper liegt. Ohne diesen Fall zöge ein Klick auf eine Bohrung
    **des gewählten Körpers** künftig den ganzen Körper, statt die Bohrung zu
    wählen — Roberts anderer Auftrag wäre damit rückwärts gegangen.

    Aufgefangen wird das an zwei Stellen: ``finish_body_drag`` verwirft alles
    unterhalb von ``EPS_DRAG``, und das Loslassen läuft danach weiter zu
    ``on_pick``.
    """
    style, _interactor, seen = _style_with_mouse()

    style._left_down()
    style._left_up()

    assert ("pick", 100, 200) in seen, "ein Klick ohne Bewegung wählt weiterhin aus"
    assert [entry[0] for entry in seen] == ["ready", "pick"], (
        f"ein Klick darf keinen Zug erzeugen, auch keinen verworfenen: {seen}"
    )


def test_the_camera_keeps_the_button_where_nothing_is_selected(qt_app: QApplication) -> None:
    """Liegt dort nichts Gewähltes, bleibt die linke Taste, was sie war.

    Der Rückruf urteilt selbst und gibt ``False`` zurück. Ohne diese Trennung
    wäre das Ziehen ein Modus mit anderem Namen: Wer die Ansicht drehen will,
    dürfte nicht erst wegklicken müssen.
    """
    style, interactor, seen = _style_with_mouse(starts=False)

    style._left_down()
    interactor.position = (160, 250)
    style._mouse_move()

    assert [entry[0] for entry in seen] == ["ready"], (
        "nach einem abgelehnten Zug darf kein 'move' mehr kommen — die Kamera führt"
    )


def test_a_wobbly_click_still_selects_instead_of_nudging_the_body(qt_app: QApplication) -> None:
    """Fünf Pixel Wandern beim Klicken bleiben ein Klick.

    **Robert am 23.08.2026:** „wenn ich ein merkmal auswähle und im viewport
    dann wieder auf das modell oder einem anderen merkmal klicke wechseln wir
    auch nicht."

    Zwei Schwellen entschieden dasselbe und waren verschieden: ``EPS_DRAG``
    misst 0,05 mm — je nach Zoom ein Drittel Pixel — und ``CLICK_SLACK`` maß
    zwei Pixel. Dazwischen lag ein Klick, der **beides** verfehlte: Er erzeugte
    einen Verschiebeschritt im Verlauf und wechselte die Auswahl nicht.
    Gemessen kippte es bei drei Pixeln, und drei Pixel sind beim Klicken
    normal.

    Jetzt entscheidet eine einzige Schwelle, und der Zug beginnt genau dort,
    wo der Klick aufhört.
    """
    style, interactor, seen = _style_with_mouse()

    style._left_down()
    interactor.position = (105, 204)
    style._mouse_move()
    style._left_up()

    assert ("pick", 105, 204) in seen, "ein leicht wackliger Klick wählt nicht mehr aus"
    assert "start" not in [entry[0] for entry in seen], (
        f"aus dem Wackeln wurde ein Zug — der Körper rutscht bei jedem Klick: {seen}"
    )


def test_loading_a_model_gives_no_detected_feature_an_originator(
    window: MainWindow,
) -> None:
    """Und die Gegenrichtung: Nach ``load`` ist **jedes** erkannte Merkmal neu.

    Ohne den ``touches_features``-Riegel trüge jede Bohrung jedes importierten
    Modells den Lade-Schritt, und „Diesen Schritt ändern" öffnete den
    Lade-Dialog — der falsche Dialog, nur tausendfach und in Weg 1
    (Messung 3d-druck-61).
    """
    result = window.session.last_result
    assert result is not None
    features = [
        (feature_id, feature)
        for entry in result.scene.objects.values()
        for feature_id, feature in entry.features.items()
    ]

    assert features, "die eingelesene Platte trägt Merkmale — sonst prüft der Test nichts"
    assert all(feature.created_by is None for _name, feature in features), {
        name: feature.created_by for name, feature in features if feature.created_by is not None
    }


def test_the_features_of_a_part_sit_under_its_own_node(window: MainWindow) -> None:
    """Was aus einem Baustein kam, steht im Baum unter ihm.

    Vierzehn Merkmale flach untereinander sagen nicht, welche zusammengehören.
    Der Knoten trägt den Namen des Bausteins und seinen Schritt — und ist damit
    die Zeile, auf die man zeigt, wenn man *ihn* ändern will und nicht eine
    seiner Flächen.
    """
    from app.ui.panels import _STEP_ROLE

    _insert_a_thread(window)
    tree = window.object_tree.tree
    step = next(
        entry.id
        for entry in window.session.project.document.ops
        if entry.op == "insert_printed_thread"
    )

    nodes = []
    for index in range(tree.topLevelItemCount()):
        item = tree.topLevelItem(index)
        for child_index in range(item.childCount()):
            child = item.child(child_index)
            if child.data(0, _STEP_ROLE) == step:
                nodes.append(child)

    assert len(nodes) == 1, f"genau ein Knoten je Baustein, gefunden: {len(nodes)}"
    assert nodes[0].childCount(), "und seine Merkmale hängen darunter"
    assert nodes[0].data(1, Qt.ItemDataRole.UserRole) is None, (
        "der Knoten ist selbst kein Merkmal — er ist ihr Dach"
    )


def test_the_layer_tool_takes_the_only_body_there_is(window: MainWindow) -> None:
    """Nach dem Öffnen gibt es ein Teil — und nichts auszuwählen.

    Wer *Schichten* anklickte, bekam einen Regler, der sich ziehen ließ und
    nichts bewegte. Der Grund stand als „Keine Auswahl" in der Statuszeile am
    unteren Fensterrand, also nicht dort, wo er gerade hinsah — und er war
    obendrein eine Frage mit nur einer möglichen Antwort: Es liegt genau ein
    Körper in der Szene.
    """
    # Das Fixture öffnet ``plate_holes.stl`` bereits — genau die Lage nach dem
    # Öffnen einer Datei, um die es hier geht. Ein zweites Laden machte daraus
    # zwei Körper und prüfte den anderen Fall.
    window.session.wait_for_idle()
    window.session.evaluate_now()
    window.object_tree.tree.clearSelection()
    assert window.object_tree.selected() is None, "nothing is selected on purpose"

    window.layer_bar.set_active(True)
    window.session.wait_for_idle()

    # ``isHidden`` und nicht ``isVisible``: Ein Fenster, das nie gezeigt wurde,
    # meldet jedes Kind als unsichtbar — geprüft wird, was *gesetzt* wurde.
    assert window.layer_bar.note.isHidden(), (
        f"one body needs no choosing, but the bar asks: {window.layer_bar.note.text()!r}"
    )
    assert not window.layer_bar.slider.isHidden(), "the slider is the point of the tool"


def test_with_several_bodies_the_bar_says_what_it_needs(window: MainWindow) -> None:
    """Bei mehreren Körpern muss der Kunde zeigen, welchen er meint.

    Dann steht der Grund **in der Leiste**, nicht in der Statuszeile — und er
    zeigt auf das Teil, nicht auf den Objektbaum: Wer aus einem Slicer kommt,
    klickt das Modell an, nicht eine Zeile in einer Liste.
    """
    # Eines bringt das Fixture mit, das zweite kommt dazu.
    window.session.import_model(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    assert len(result.scene.objects) == 2, "the point of this test is the ambiguity"
    window.object_tree.tree.clearSelection()

    window.layer_bar.set_active(True)
    window.session.wait_for_idle()

    assert not window.layer_bar.note.isHidden(), "two bodies: the bar has to ask"
    assert "Teil" in window.layer_bar.note.text(), (
        f"the note should point at the part: {window.layer_bar.note.text()!r}"
    )
    assert window.layer_bar.slider.isHidden(), (
        "a slider next to a note saying there is nothing to slide is a contradiction"
    )


def test_the_history_shows_what_kind_of_step_each_line_is(qt_app: QApplication) -> None:
    """Der Verlauf war eine reine Textspalte mit halber Nummerierung.

    Siebzehn Kategoriesymbole lagen in ``icons.py`` bereit, und keine
    Verlaufszeile trug eines — wer seine Arbeit daran entlangliest, sucht
    „das mit der Bohrung" und findet lauter gleich aussehende Zeilen. Und die
    Nummern trugen nur die Kinder einer mehrschrittigen Transaktion: „3" und
    „4" eingerückt unter „Kabel und Befestigung", während „Aushöhlen" darüber
    keine hatte, obwohl auch das genau ein Schritt ist.

    Die Nummer ist keine Zierde — der Fehlerdialog nennt „Operation: 4", und
    ein geöffneter Schritt heißt „Bohrung setzen — Operation 4". Sie steht
    deshalb an jeder Zeile, die genau einen Schritt vertritt; eine
    Transaktion aus mehreren bekommt keine, ihre Kinder tragen ihre eigenen.
    """
    from pathlib import Path

    from app.ui.panels import HistoryPanel
    from app.ui.session import Session

    session = Session()
    session.open_project(Path(__file__).parent.parent / "app" / "examples" / "dose-mit-deckel.p3d")
    session.wait_for_idle()

    panel = HistoryPanel()
    try:
        panel.show_document(session.project.document)
        rows = [panel.list.item(index) for index in range(panel.list.count())]
        assert rows, "das Beispielprojekt hat keinen Verlauf — dann prüft dieser Test nichts"

        without_icon = [row.text() for row in rows if row.icon().isNull()]
        assert not without_icon, f"Zeilen ohne Symbol: {without_icon}"

        # Jede Zeile, die genau einen Schritt vertritt, nennt seine Nummer.
        for row in rows:
            single = row.data(Qt.ItemDataRole.UserRole)
            if single is None:
                continue
            assert str(single) in row.text(), (
                f"Schritt {single} nennt seine Nummer nicht: {row.text()!r}"
            )
    finally:
        panel.deleteLater()


def test_the_object_preview_is_large_enough_to_recognise(qt_app: QApplication) -> None:
    """Das Vorschaubild war ein Fleck, in dem auch vergrößert nichts zu sehen war.

    Bei Zeilenhöhe mal 1,2 — bei Standardschrift 19 Bildpunkte — zeigte der
    Objektbaum von einer Platte einen dunklen Punkt (B5). Ein Bild, das man
    nicht erkennt, kostet Spaltenbreite und liefert nichts; der Befund schließt
    „halbe Größe" ausdrücklich als Ausweg aus.

    **Der alte Grund gegen mehr ist nachgemessen und weggefallen.** Im
    Docstring stand, ab Zeilenhöhe mal 1,7 werde der Name gekürzt. Gemessen
    bleibt die Spalte „Objekt" bei 19, 32, 40 und 48 Punkten Vorschau konstant
    165 Punkte breit, und ``elidedText`` kürzt in keinem der vier Fälle. Was
    der Satz beschrieb, war eine Spaltenaufteilung von früher.

    Geprüft wird hier die Rechnung, nicht das Bild: Die Untergrenze, die
    Mitwachsen-Eigenschaft und der Deckel, der das Bild aus der Namensspalte
    heraushält.
    """
    from PySide6.QtGui import QFont
    from PySide6.QtWidgets import QLabel

    from app.ui.panels import _preview_pixels

    probe = QLabel()
    try:
        assert _preview_pixels(probe) >= 40, (
            "unter vierzig Punkten ist ein Quader eine Silhouette ohne Kanten — "
            "gemessen an den Belegbildern der Durchsicht"
        )

        # **Es wächst mit der Schrift** — der ursprüngliche Zweck der Funktion,
        # und er darf beim Vergrößern nicht verlorengehen.
        gross = QFont(probe.font())
        gross.setPointSize(max(probe.font().pointSize(), 1) * 3)
        probe.setFont(gross)
        assert _preview_pixels(probe) > 40, "bei dreifacher Schrift wächst das Bild mit"

        # **Und es hört rechtzeitig auf.** Die Spalte „Objekt" ist 165 Punkte
        # breit; ein Bild über einem Drittel davon nähme dem Namen den Platz,
        # den die Messung ihm als Reserve gelassen hat.
        riesig = QFont(probe.font())
        riesig.setPointSize(max(probe.font().pointSize(), 1) * 4)
        probe.setFont(riesig)
        assert _preview_pixels(probe) <= 56, "über sechsundfünfzig frisst es die Namensspalte"
    finally:
        probe.deleteLater()


def test_a_click_with_a_place_also_selects_the_body(window: MainWindow) -> None:
    """Die drei Stufen eines Klicks schließen einander nicht aus (§18.4).

    **Der Fehler, den das hier fängt.** Die Regel und der Docstring der Funktion
    sagen beide dasselbe: Ort → die Kamera fliegt und eine Marke steht dort;
    Körper → er wird ausgewählt; Schritt → der Verlauf zeigt ihn. Der Code
    führte sie aber als Reihenfolge aus — nach dem Flug stand ein ``return``,
    und die Zeile mit der Auswahl darunter wurde nie erreicht. Wer auf eine
    Warnung mit Ort klickte, bekam den Flug **statt** der Auswahl.

    **Und der Wächter daneben sah es nicht**, weil er den Quelltext nach
    ``select_object`` absucht: Der Aufruf stand da, er lief nur nicht. Ein
    Test, der Anwesenheit prüft, ist gegen eine unerreichbare Zeile blind —
    deshalb misst dieser hier die Wirkung.
    """
    select_plate(window)
    finding = Finding(
        code="etwas.anderes",
        severity="warning",
        message="x",
        object_id="obj_1",
        location=(1.0, 2.0, 3.0),
    )

    window.object_tree.select_object("")
    assert window.object_tree.selected() != "obj_1", "die Auswahl steht nicht schon vorher"

    window._on_finding_activated(finding)

    assert window.object_tree.selected() == "obj_1", (
        "ein Klick mit Ort wählt den Körper trotzdem aus — die Stufen sind "
        "kumulativ, nicht alternativ"
    )


def test_the_camera_keeps_the_body_in_view_after_a_finding_flight(window: MainWindow) -> None:
    """Nach dem Flug steht der Körper im Bild, nicht eine Fläche davon (§18.4).

    **Vermessen, nicht geschätzt.** Die Kamera hielt den Abstand aus der
    Szenengröße geteilt durch drei — bei der Dose 24 mm, und davon war **eine**
    von acht Ecken des Hüllquaders im Bild. Der Kunde klickte auf eine Warnung
    und stand vor einer grauen Fläche.

    Gemessen wurde in Vielfachen der Hüllquader-Diagonale: bei 1,2 sind sechs
    von acht Ecken zu sehen — dort wird aus „irgendeiner Fläche" ein
    erkennbares Teil, und dort wird auch die Beschriftung der Marke sichtbar,
    also der Satz, für den die Marke überhaupt da ist. 1,4 ist der
    Sicherheitsabstand dazu; weiter hinaus (2,5) wird die Marke klein.

    Geprüft wird der Abstand und nicht die Zahl der Ecken: Die Ecken hängen am
    Blickwinkel und am Seitenverhältnis des Fensters, der Abstand ist die
    Größe, die der Code setzt.
    """
    select_plate(window)
    entry = next(iter(window.session.last_result.scene.objects.values()))
    finding = Finding(
        code="etwas.anderes",
        severity="warning",
        message="x",
        object_id=entry.id,
        location=tuple(entry.mesh.bounds.centre),
    )

    # **Gemessen wird der verlangte Abstand, nicht die Kamerastellung.** Im
    # Offscreen-Betrieb gibt es keinen Plotter und damit keine Kamera; was der
    # Code entscheidet, ist die Reichweite, die er `fly_to` mitgibt. Das
    # Umsetzen in eine Position ist Qt-Mechanik und gehört nicht hierher.
    verlangt: list[float | None] = []
    original = window.viewport.fly_to

    def merken(point: Any, distance_factor: float = 3.0, reach: float | None = None) -> None:
        verlangt.append(reach)
        original(point, distance_factor, reach)

    window.viewport.fly_to = merken  # type: ignore[method-assign]
    try:
        window._on_finding_activated(finding)
    finally:
        window.viewport.fly_to = original  # type: ignore[method-assign]

    assert verlangt, "der Klick ist geflogen"
    erwartet = 1.4 * float(entry.mesh.bounds.diagonal)
    assert verlangt[0] is not None and abs(verlangt[0] - erwartet) < 0.01, (
        f"der Flug verlangt {verlangt[0]} statt {erwartet:.1f} Abstand — bei zu"
        " wenig sieht der Kunde eine Fläche statt eines Teils"
    )


def test_the_layer_legend_goes_when_the_layer_does(qt_app: QApplication) -> None:
    """Die Ringlegende verschwindet mit der Schicht, die sie erklärt.

    **Der Fall, der diese Prüfung veranlasst hat** (gemessen 3d-druck-85 am
    03.09.2026): Aufgeräumt wurde die Legende nur am Kopf von ``_show_legend``,
    und das lief nur bei gezeigter Schicht. In vier Lagen stand deshalb die
    Legende des vorigen Körpers da — bei „keine Auswahl", nach dem Schließen
    des Werkzeugs und nach **jeder** Auswertung, weil das Fenster dann
    ``show_result(None)`` ruft. Mitsamt „Insel" und „Überhang", die es in der
    leeren Ansicht nicht gibt.

    Ein Zustand, den niemand abräumt, sieht aus wie eine Auskunft.
    """
    bar = LayerBar()
    bar.setEnabled(True)
    bar._on = True
    layer = SimpleNamespace(z=1.0, area=100.0, islands=[(0.0, 0.0)], overhang_area=5.0)
    bar._result = SimpleNamespace(layers=[layer])
    bar._show_readout()
    assert bar._legend.count() > 1, "die Legende steht, solange die Schicht steht"

    bar.show_result(None)

    assert bar._legend.count() == 0, "ohne Schicht bleibt keine Legende stehen"
