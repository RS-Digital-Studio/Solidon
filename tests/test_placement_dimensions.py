"""Maßfelder bleiben am Bildrand getrennt und ihrer Maßlinie zugeordnet.

Die Projektion ist kontrolliert; Widgets, Größen, Fokus und redraw laufen echt.
Kein Renderer und keine Geometrieoperation werden für diese Anordnung benötigt.
"""

from __future__ import annotations

import dataclasses
import math
from itertools import combinations
from types import SimpleNamespace

import numpy as np
import pytest
import trimesh
from PySide6.QtCore import QPoint, QPointF, QRect
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QVBoxLayout, QWidget
from shapely.geometry import Polygon

from app.core.geom.mesh import MeshData
from app.core.registry import REGISTRY
from app.core.scene.evaluate import EvaluationResult
from app.core.scene.placement import (
    CentreReference,
    EdgeReference,
    PlacementTool,
    PreparedSurface,
    SurfacePlacement,
)
from app.core.types import PlaneFrame, Scene, SceneObject
from app.ui.op_dialog import OperationDialog
from app.ui.overlay import OverlayHost
from app.ui.placement_flow import PlacementFlow, _crosses, _Dimensions, _untangle
from app.ui.session import Session
from tests.test_surface_placement_ui import _Item, _Viewport


def test_dimension_ink_lives_in_the_renderer_and_leaves_with_the_surface(
    qt_app: QApplication,
) -> None:
    """Die Maßtinte ist kein Qt-Widget über der Renderfläche (RM-198).

    Bis zum 21.09.2026 lag sie als maskiertes Widget über dem nativen
    Renderfenster; die Maske hatte je schräger Linie ein Rechteck je Bildzeile,
    und bei 1682 Rechtecken verlor der Vulkan-Treiber das Gerät. Jetzt gehen
    Unterlage, Striche, Pfeile und Marken als Elemente vor dem Material in den
    Renderer — **dieselben Elemente bei jedem Aufbau, mit neuen Punkten**:
    Je Kamerageste zehn Elemente abzuräumen und neu anzulegen kostete zwölf
    von zweiundzwanzig Millisekunden an Pipelines (gemessen 21.09.2026). Ohne
    Fläche sind sie ausgeblendet, mit dem Fluss kommen sie heraus.
    """
    flow, session, viewport, dialog = _layout(qt_app, (900, 600), 1.0, "bottom")
    viewport.renderer.world_to_display = lambda point: (80 + point[0] * 20, 80 + point[1] * 20, 0.5)
    flow.redraw()
    canvas = flow._canvas
    renderer = viewport.renderer
    try:
        assert not isinstance(canvas, QWidget), "keine Fenstermaske über der Renderfläche"
        assert canvas.shown
        names = [entry["name"] for entry in renderer.lines]
        assert "dimension_backdrop" in names and "dimension_lines" in names
        assert all(entry["keep_in_front"] for entry in renderer.lines)
        assert all(entry["style"].keep_in_front for entry in renderer.surfaces)
        assert any(entry["name"] == "dimension_arrowheads" for entry in renderer.surfaces)
        # Die Unterlage liegt unter der Tinte: zuerst angelegt, zuerst gezeichnet.
        assert names.index("dimension_backdrop") < names.index("dimension_lines")
        assert all(entry["capacity"] for entry in (*renderer.lines, *renderer.surfaces)), (
            "jedes Element hält Platz — damit der nächste Aufbau nur Zahlen tauscht"
        )
        first_items = [entry["item"] for entry in (*renderer.lines, *renderer.surfaces)]
        before = [entry["item"].points.copy() for entry in renderer.lines]

        viewport.renderer.world_to_display = lambda point: (
            380 + point[0] * 20,
            280 + point[1] * 20,
            0.5,
        )
        flow.redraw()
        assert not renderer.removed, "die alte Maßlage gibt kein Element zurück"
        assert [entry["item"] for entry in (*renderer.lines, *renderer.surfaces)] == first_items, (
            "dieselben Elemente stehen im Renderer"
        )
        assert all(item.updates >= 1 for item in first_items), "und alle bekamen neue Punkte"
        assert any(
            entry["item"].points.shape != old.shape or not np.allclose(entry["item"].points, old)
            for entry, old in zip(renderer.lines, before, strict=True)
        ), "die Punkte sind die der neuen Maßlage"

        flow._surface = None
        flow.redraw()
        assert not canvas.shown, "ohne Fläche steht keine Tinte im Bild"
        assert not any(item.visible for item in first_items), "die Elemente sind ausgeblendet"
        assert not renderer.removed, "und bleiben für den nächsten Aufbau"
        flow.dispose()
        assert all(item in renderer.removed for item in first_items), (
            "mit dem Fluss kommen sie aus dem Renderer"
        )
    finally:
        flow.dispose()
        session.release()
        dialog.close()
        viewport.close()


@pytest.mark.parametrize("with_centre", [False, True])
def test_dimension_fields_stay_visible_widgets_over_the_ink(
    qt_app: QApplication, with_centre: bool
) -> None:
    """Zahlen und Mittelpunkttext bleiben Qt-Fenster über dem Bild; die Tinte liegt darunter.

    Geprüft wird, dass die Tinte im Renderer steht und die Felder sichtbar
    sind — nicht mehr eine Freihaltung ihrer Rechtecke: Die gab es nur bei der
    Fenstermaske, und die ist mit RM-198 gefallen.
    """
    flow, session, viewport, dialog = _layout(qt_app, (900, 600), 1.0, "bottom")
    if not with_centre:
        flow._centre_id = ""
    try:
        for shift in (0, 160):
            viewport.renderer.world_to_display = lambda point, shift=shift: (
                120 + shift + point[0] * 30,
                160 + point[1] * 25,
                0.5,
            )
            flow.redraw()
            assert len(flow._canvas.lines) == (4 if with_centre else 2)
            assert flow._canvas.shown, "die Striche stehen im Renderer"
            assert flow._canvas.segments, "nach Aussparung bleibt Tinte übrig"
            # Die Kantenmaße sitzen seit der Bezugswahl (20.09.2026) in ihren
            # Boxen; im Bild verteilt werden die Boxen, die Felder liegen darin
            # — als Qt-Fenster über dem Bild, die Tinte darunter.
            fields = [flow._bar, *flow._reference_boxes[:2]]
            if with_centre:
                fields.extend([*flow._centre_measures, flow._reference_boxes[2]])
            for field in fields:
                assert field.isVisible()
    finally:
        flow.dispose()
        session.release()
        dialog.close()
        viewport.close()


def test_leaders_swap_their_fields_until_none_of_them_cross(qt_app: QApplication) -> None:
    """Zwei gestapelte Felder, deren Linien sich kreuzen, tauschen die Plätze (RM-197).

    Robert, 21.09.2026: „aufpassen dass sich die maßlinien nicht kreuzen". Das
    obere Feld zeigt auf den unteren Anker und umgekehrt — getauscht laufen
    beide Linien nebeneinander. Ein drittes Feld daneben bleibt, wo es ist,
    und ein Tausch, der einem Hindernis zu nahe käme, findet nicht statt.
    """
    upper, lower, aside = QWidget(), QWidget(), QWidget()
    positions = {
        upper: QRect(10, 10, 100, 30),
        lower: QRect(10, 60, 100, 30),
        aside: QRect(300, 10, 100, 30),
    }
    pending = [
        (upper, QPointF(), QPointF(200, 200)),
        (lower, QPointF(), QPointF(200, 100)),
        (aside, QPointF(), QPointF(350, 300)),
    ]
    assert _crosses((QPointF(60, 25), QPointF(200, 200)), (QPointF(60, 75), QPointF(200, 100)))
    _untangle(positions, pending, QRect(0, 0, 600, 400), [])
    assert positions[upper] == QRect(10, 60, 100, 30)
    assert positions[lower] == QRect(10, 10, 100, 30)
    assert positions[aside] == QRect(300, 10, 100, 30)
    assert not _crosses(
        (QPointF(positions[upper].center()), QPointF(200, 200)),
        (QPointF(positions[lower].center()), QPointF(200, 100)),
    )
    # Mit einem Hindernis auf dem oberen Platz bleibt die Kreuzung stehen —
    # ein Feld über dem Setzpunkt wäre schlimmer als eine gekreuzte Linie.
    positions[upper], positions[lower] = positions[lower], positions[upper]
    _untangle(positions, pending, QRect(0, 0, 600, 400), [QRect(0, 0, 130, 45)])
    assert positions[upper] == QRect(10, 10, 100, 30)
    for widget in (upper, lower, aside):
        widget.deleteLater()


def test_old_field_places_serve_until_a_slot_is_taken_or_the_view_turns(
    qt_app: QApplication,
) -> None:
    """Die Anordnung des letzten Aufbaus gilt weiter — bis etwas dagegen spricht.

    Vier Gründe, sie zu verlassen: ein Hindernis auf einem alten Platz, ein
    Platz außerhalb des Bildes, ein Maß, das weit weg gewandert ist (die
    Kamera), oder mehr Kreuzungen als in der neuen Anordnung.
    """
    from app.ui.placement_flow import _old_places_still_serve

    upper, lower = QWidget(), QWidget()
    previous = {upper: QRect(10, 10, 100, 30), lower: QRect(10, 60, 100, 30)}
    fresh = {upper: QRect(40, 10, 100, 30), lower: QRect(40, 60, 100, 30)}
    pending = [
        (upper, QPointF(200, 25), QPointF(200, 25)),
        (lower, QPointF(200, 75), QPointF(200, 75)),
    ]
    bounds = QRect(0, 0, 600, 400)
    assert _old_places_still_serve(previous, fresh, pending, bounds, [])
    assert not _old_places_still_serve({}, fresh, pending, bounds, []), "beim ersten Aufbau"
    assert not _old_places_still_serve(previous, fresh, pending, bounds, [QRect(0, 0, 50, 50)]), (
        "ein Hindernis auf dem alten Platz"
    )
    assert not _old_places_still_serve(previous, fresh, pending, QRect(20, 0, 600, 400), []), (
        "ein alter Platz außerhalb des Bildes"
    )
    turned = [
        (upper, QPointF(500, 350), QPointF(500, 350)),
        (lower, QPointF(500, 300), QPointF(500, 300)),
    ]
    far = {upper: QRect(380, 335, 100, 30), lower: QRect(380, 285, 100, 30)}
    assert not _old_places_still_serve(previous, far, turned, bounds, []), (
        "nach einer Kameradrehung liegen die Maße weit weg"
    )
    crossed = [
        (upper, QPointF(200, 75), QPointF(200, 75)),
        (lower, QPointF(200, 25), QPointF(200, 25)),
    ]
    swapped = {upper: QRect(40, 60, 100, 30), lower: QRect(40, 10, 100, 30)}
    assert not _old_places_still_serve(previous, swapped, crossed, bounds, []), (
        "die alte Anordnung kreuzt, die neue nicht"
    )
    for widget in (upper, lower):
        widget.deleteLater()


def test_placement_ghost_uses_a_filled_surface_without_tessellation_edges(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der echte Werkzeug-Rückruf reicht dem Renderer dieselbe ungestörte Ghost-Fläche."""
    flow, session, viewport, dialog = _layout(qt_app, (900, 600), 1.0, "bottom")
    styles = []

    def add_surface(_points, _faces, *, name, style, capacity=None):
        # Pfeile und Marken der Maßtinte kommen denselben Weg — gezählt wird
        # hier nur der Werkzeugkörper.
        if name == "surface_placement_tool":
            styles.append(style)
        return _Item(_points, capacity)

    # Ein bereits vorbereiteter Körper genügt; geprüft wird hier allein seine
    # Übergabe an den gemeinsamen Renderer-Vertrag, ohne GPU und zweite Geometrie.
    monkeypatch.setattr(
        session,
        "placement_async",
        lambda _compute, done, _failed: done(PlacementTool(flow._prepared_mesh)),
    )
    monkeypatch.setattr(viewport.renderer, "add_surface", add_surface)
    try:
        flow._request_tool()
        assert len(styles) == 1
        assert not styles[0].show_edges and not styles[0].wireframe
        assert 0.0 < styles[0].opacity < 1.0
        assert not styles[0].pickable
        assert styles[0].keep_in_front
        assert flow._tool.visible and flow._accept.isEnabled()
    finally:
        flow.dispose()
        session.release()
        dialog.close()
        viewport.close()


def test_dimension_ink_stays_below_the_grip_and_the_knobs(qt_app: QApplication) -> None:
    """Alle Tinte trägt DRAW_ORDER = -1: unter Griff, Knöpfen und Umriss, die bei 0 liegen.

    pygfx sortiert die Deckschicht nach Ordnung und dann nach dem Abstand des
    Objektursprungs; der Ursprung der Tinte ist die Welt. Ohne die Ordnung
    hinge es davon ab, wo die Platte im Bauraum steht, ob die Maßlinien über
    oder unter dem Griff lägen — und die Linien mit Unterlage verdeckten dann
    den Griff (Robert, 11.09.2026: „das verschieben ist auch schwer durch die
    maßlinien zu treffen"). Der Renderer schreibt die Ordnung seit dem
    21.09.2026 mit, damit ein Test sie überhaupt lesen kann (Review Tests #8).
    """
    from tests.test_surface_placement_ui import _Viewport

    viewport = _Viewport()
    renderer = viewport.renderer
    canvas = _Dimensions(viewport)
    canvas.lines = [(QPointF(20, 40), QPointF(180, 40))]
    canvas.leaders = [(QPointF(20, 60), QPointF(180, 90))]
    canvas.outline = [QPointF(40, 40), QPointF(80, 40), QPointF(60, 80)]
    canvas.outline_colour = QColor("#ff8800")
    try:
        canvas.refresh()
        for entry in renderer.lines:
            assert entry["draw_order"] == _Dimensions.DRAW_ORDER, entry["name"]
        for entry in renderer.surfaces:
            assert entry["style"].draw_order == _Dimensions.DRAW_ORDER, entry["name"]
        assert _Dimensions.DRAW_ORDER == -1, "unter Griff und Knöpfen (die bei 0 liegen)"
    finally:
        canvas.dispose()
        viewport.close()


def test_a_dimension_line_swallowed_by_the_grip_is_drawn_whole(qt_app: QApplication) -> None:
    """Eine Maßlinie, die ganz im Griff läge, kommt ganz — mit beiden Pfeilen.

    Die Aussparung um den Griff ist Kosmetik, die Tinte nimmt keinen Klick an.
    Nach dem Zug zum Langloch greift der Griff über Knöpfe und Umriss hinaus,
    und die 10 mm zur Außenkante lagen ganz darin: ein Feld mit Zahl, aber
    ohne Linie (Robert, 21.09.2026: „manche maßlinien fehlen aber"). Eine
    Linie, die über den Griff hinausreicht, verliert weiter nur das Stück im
    Griff — und den Pfeil, der darin steht.
    """
    from tests.test_surface_placement_ui import _Viewport

    viewport = _Viewport()
    canvas = _Dimensions(viewport)
    canvas.clearing = (QPointF(100, 100), 50.0)
    short = (QPointF(100, 100), QPointF(130, 100))
    long = (QPointF(100, 100), QPointF(300, 100))

    def arrowheads() -> int:
        # Je Pfeil ein Dreieck mit eigenen drei Ecken — das Element hält
        # Platz, gezählt wird, was zuletzt geschrieben wurde.
        heads = [
            entry for entry in viewport.renderer.surfaces if entry["name"] == "dimension_arrowheads"
        ]
        assert len(heads) == 1
        return len(heads[0]["item"].points) // 3

    try:
        canvas.lines = [short]
        canvas.refresh()
        assert canvas.segments == [short], "die verschluckte Linie steht ganz"
        assert arrowheads() == 2, "mit beiden Pfeilen"

        canvas.lines = [long]
        canvas.refresh()
        assert len(canvas.segments) == 1
        ((start, end),) = canvas.segments
        assert start.x() == pytest.approx(150.0) and end == QPointF(300, 100), (
            "die lange Linie verliert nur das Stück im Griff"
        )
        assert arrowheads() == 1, "und den Pfeil darin"

        # Drei Bildpunkte über den Rand hinaus wären ein Stummel ohne Pfeil —
        # bei etwas anderem Zoom dieselbe Lage wie die verschluckte Linie.
        stub = (QPointF(100, 100), QPointF(153, 100))
        canvas.lines = [stub]
        canvas.refresh()
        assert canvas.segments == [stub], "kürzer als ein Pfeil heißt: die ganze Linie"
        assert arrowheads() == 2, "mit beiden Pfeilen"
    finally:
        canvas.dispose()
        viewport.close()


def test_moving_dimension_ink_keeps_its_renderer_items_and_swaps_their_points(
    qt_app: QApplication,
) -> None:
    """Jeder Aufbau schreibt in dieselben acht Elemente — nichts sammelt sich an.

    Bis zum 21.09.2026 tauschte jeder Aufbau zehn Elemente aus; pygfx baute
    je neuem Element eine Pipeline, zwölf Millisekunden je Kamerageste. Jetzt
    halten die Elemente Platz (``capacity``), und nur wenn er reißt,
    entstehen alle acht neu — auf das Doppelte des Bedarfs, in ihrer
    Reihenfolge.
    """
    from tests.test_surface_placement_ui import _Viewport

    viewport = _Viewport()
    renderer = viewport.renderer
    canvas = _Dimensions(viewport)
    canvas.lines = [(QPointF(20, 40), QPointF(180, 40))]
    canvas.leaders = [(QPointF(20, 60), QPointF(180, 90))]
    try:
        canvas.refresh()
        first = [entry["item"] for entry in (*renderer.lines, *renderer.surfaces)]
        assert len(first) == 8, "fünf Linien, drei Flächen"
        assert [entry["name"] for entry in renderer.lines] == [
            "dimension_backdrop",
            "dimension_lines",
            "dimension_leaders",
            "dimension_outline",
            "dimension_focus",
        ]
        assert [entry["name"] for entry in renderer.surfaces] == [
            "dimension_mark_rim",
            "dimension_arrowheads",
            "dimension_marks",
        ]
        assert canvas.shown
        lines_item = renderer.lines[1]["item"]
        outline_item = renderer.lines[3]["item"]
        assert lines_item.visible and not outline_item.visible, (
            "ein Element ohne Punkte ist ausgeblendet, nicht abgeräumt"
        )
        canvas.lines = [(QPointF(20, 140), QPointF(180, 140))]
        canvas.refresh()
        assert not renderer.removed, "kein Element ging zurück"
        assert [entry["item"] for entry in (*renderer.lines, *renderer.surfaces)] == first
        assert lines_item.updates == 1 and lines_item.points.shape == (2, 3), "neue Punkte"
        canvas.hide()
        assert not canvas.shown and not any(item.visible for item in first)
        assert not renderer.removed, "ausgeblendet heißt: bereit für den nächsten Aufbau"

        # Reißt eine Kapazität, entstehen alle acht neu — in Reihenfolge.
        many = [(QPointF(20, 20 + 6 * index), QPointF(180, 20 + 6 * index)) for index in range(400)]
        canvas.lines = many
        canvas.refresh()
        assert all(item in renderer.removed for item in first), "alle acht gingen zurück"
        second = [entry["item"] for entry in (*renderer.lines, *renderer.surfaces)]
        assert len(second) == 8 and not set(second) & set(first)
        assert [entry["name"] for entry in renderer.lines][:2] == [
            "dimension_backdrop",
            "dimension_lines",
        ], "in derselben Reihenfolge"
        assert renderer.lines[1]["capacity"] >= 2 * 800, "auf das Doppelte des Bedarfs"
        canvas.dispose()
        assert all(item in renderer.removed for item in second)
    finally:
        viewport.close()


def test_resizing_a_dimension_field_does_not_mix_nested_line_lists(qt_app: QApplication) -> None:
    """Das eigene adjustSize darf im Würfelfall keine dritte oder weitere Maßlinie anhängen."""
    flow, session, viewport, dialog = _layout(qt_app, (900, 600), 1.0, "bottom")
    flow._centre_id = ""
    flow.redraw()
    try:
        assert len(flow._canvas.lines) == 2
        field = flow._reference_boxes[0]
        # Ein echter synchroner QWidget-Resize, dessen bisheriger Rückruf die
        # Wunschgröße wiederherstellt und dabei mitten im Aufbau erneut eintritt.
        field.resize(field.width() + 31, field.height())
        qt_app.processEvents()
        assert len(flow._canvas.lines) == 2, "eigene Feldgrößenänderung vermischt mehrere Aufbauten"
        assert len(flow._canvas.leaders) == 2
        assert len({(a.x(), a.y(), b.x(), b.y()) for a, b in flow._canvas.lines}) == 2
        viewport.resize(960, 640)
        qt_app.processEvents()
        assert len(flow._canvas.lines) == len(flow._canvas.leaders) == 2
    finally:
        flow.dispose()
        session.release()
        dialog.close()
        viewport.close()


@pytest.mark.parametrize("size", [(900, 600), (1200, 850), (1500, 1000)])
@pytest.mark.parametrize("scale,corner", [(0.01, "bottom"), (1000.0, "bottom"), (1000.0, "top")])
def test_dimension_fields_do_not_overlap_at_zoomed_view_edges(
    qt_app: QApplication, size: tuple[int, int], scale: float, corner: str
) -> None:
    """Vier Maße plus Mittelpunkt bleiben im Bild, auch bei gleichem Wunschplatz."""
    flow, session, viewport, dialog = _layout(qt_app, size, scale, corner)
    try:
        widgets = [*flow._reference_boxes[:2], *flow._centre_measures, flow._reference_boxes[2]]
        assert len(flow._canvas.lines) == 4
        for field in widgets:
            assert field.isVisible()
            assert viewport.rect().contains(field.geometry()), field.objectName()
            assert not field.geometry().intersects(flow._bar.geometry())
        for first, second in combinations(widgets, 2):
            assert not first.geometry().intersects(second.geometry()), (
                first.objectName(),
                second.objectName(),
                first.geometry(),
                second.geometry(),
            )
        # Jeder verschobene Wert trägt einen eigenen Anschluss zur zugehörigen
        # Maßlinie; die Verbindungsmarke bleibt auf dieser Linie.
        assert len(flow._canvas.leaders) == len(widgets)
        for index, (_field_point, anchor) in enumerate(flow._canvas.leaders[:4]):
            start, end = flow._canvas.lines[index]
            vector, offset = end - start, anchor - start
            assert abs(vector.x() * offset.y() - vector.y() * offset.x()) < 1e-6
        first = flow._measures[0]
        first.setFocus()
        qt_app.processEvents()
        assert first.hasFocus()
        positions = [widget.pos() for widget in widgets]
        flow.redraw()
        assert first.hasFocus()
        assert [widget.pos() for widget in widgets] == positions
    finally:
        flow.dispose()
        session.release()
        dialog.close()
        viewport.close()


def test_the_dimension_fields_leave_the_movement_handle_alone(qt_app: QApplication) -> None:
    """Pfeile und Ringe bleiben greifbar — kein Feld liegt über dem Griff.

    Ein Qt-Widget über der Renderfläche nimmt die Zeigerereignisse an, und die
    Vorfahrt in ``Viewport._on_pointer`` kommt gar nicht erst zum Zug: Der Griff
    ist dann sichtbar und tot. Gemeldet an einer angeklickten Bohrung, deren
    Maße genau dort standen, wo der Griff hängt (Robert, 10.09.2026: „ich kann
    die pfeile und das drehen nicht mehr bedienen").

    Die Gegenprobe dazu ist der zweite Teil: Ohne gemeldeten Griff darf dieselbe
    Fläche belegt werden — sonst prüft der Test eine Anordnung und keine Regel.
    """
    flow, session, viewport, dialog = _layout(qt_app, (900, 600), 6.0, "bottom")
    try:
        # Mitten ins Bild, sonst klemmt der Rand die Felder ohnehin weg und die
        # Gegenprobe unten misst die Bildgrenze statt der Regel.
        viewport.renderer.world_to_display = lambda point: (
            450 + (point[0] - 10) * 6.0,
            300 + (point[1] - 10) * 6.0,
            0.5,
        )
        flow.redraw()
        qt_app.processEvents()
        widgets = [*flow._reference_boxes[:2], *flow._centre_measures, flow._reference_boxes[2]]
        frei = [widget.geometry() for widget in widgets]

        # Der Griff reicht über den Körper samt seinem Freiraum hinaus (36 mm bei
        # 20 mm halber Platte und 10 mm Freiraum): Seit dem 22.09.2026 stehen
        # die Felder neben dem ganz sichtbaren Körper, und ein kleinerer Griff
        # träfe dort gar kein Feld — die Gegenprobe unten misst dann nichts.
        viewport.handle = ((10.0, 10.0, 0.0), 36.0)
        flow.redraw()
        qt_app.processEvents()
        mitte = viewport.renderer.world_to_display((10.0, 10.0, 0.0))
        rand = viewport.renderer.world_to_display((46.0, 10.0, 0.0))
        weite = round(math.hypot(rand[0] - mitte[0], rand[1] - mitte[1]))
        griff = QRect(
            round(mitte[0]) - weite, round(mitte[1]) - weite, 2 * weite + 1, 2 * weite + 1
        )
        for widget in widgets:
            assert not widget.geometry().intersects(griff), (
                widget.objectName(),
                widget.geometry(),
                griff,
            )

        assert any(rechteck.intersects(griff) for rechteck in frei), (
            "ohne gemeldeten Griff lagen die Felder gar nicht dort — der Test misst nichts"
        )
    finally:
        flow.dispose()
        session.release()
        dialog.close()
        viewport.close()


def test_the_dimension_lines_leave_the_movement_handle_alone(qt_app: QApplication) -> None:
    """Auch die Linien weichen dem Griff — nicht nur die Felder.

    Die Maßlinien laufen alle in der Mitte des Merkmals zusammen, und dort
    sitzen Pfeile und Ringe: vier Linien mit Unterlage über dem Griff, und er
    war weder zu sehen noch zu treffen (Robert, 11.09.2026: „das verschieben
    ist auch schwer durch die maßlinien zu treffen/sehen"). Die Maßfläche
    zeichnet nur, was außerhalb der Griffspanne liegt — und den Umriss des
    Lochs, der dorthin gehört.

    Die Gegenprobe steht wieder daneben: Ohne gemeldeten Griff liegt die Tinte
    an derselben Stelle.
    """
    from PySide6.QtCore import QPoint

    flow, session, viewport, dialog = _layout(qt_app, (900, 600), 6.0, "bottom")
    try:
        viewport.renderer.world_to_display = lambda point: (
            450 + (point[0] - 10) * 6.0,
            300 + (point[1] - 10) * 6.0,
            0.5,
        )
        flow.redraw()
        qt_app.processEvents()
        canvas = flow._canvas
        mitte = viewport.renderer.world_to_display((10.0, 10.0, 0.0))

        def in_der_mitte(point: QPointF) -> bool:
            return math.hypot(point.x() - mitte[0], point.y() - mitte[1]) < 2.0

        # Die Maßlinie, die in der Mitte endet — und je ein Punkt nahe und fern.
        linie = next(
            ((s, e) if in_der_mitte(e) else (e, s))
            for s, e in canvas.lines
            if in_der_mitte(s) or in_der_mitte(e)
        )
        aussen, innen = linie

        def dazwischen(anteil: float) -> QPoint:
            return QPoint(
                round(innen.x() + (aussen.x() - innen.x()) * anteil),
                round(innen.y() + (aussen.y() - innen.y()) * anteil),
            )

        nahe, fern = dazwischen(0.1), dazwischen(0.9)

        def tinte_bei(point: QPoint) -> bool:
            """Ob ein gezeichneter Strich näher als zwei Bildpunkte am Punkt liegt."""
            for start, end in canvas.segments:
                vector = end - start
                square = QPointF.dotProduct(vector, vector)
                along = (
                    QPointF.dotProduct(QPointF(point) - start, vector) / square if square else 0.0
                )
                foot = start + vector * max(0.0, min(along, 1.0))
                if math.hypot(foot.x() - point.x(), foot.y() - point.y()) < 2.0:
                    return True
            return False

        assert tinte_bei(nahe), "ohne Griff zeichnet die Fläche bis in die Mitte"

        viewport.handle = ((10.0, 10.0, 0.0), 5.0)
        flow.redraw()
        qt_app.processEvents()
        assert canvas.clearing is not None
        assert not tinte_bei(nahe), "mit Griff bleibt seine Spanne frei von Linien"
        assert tinte_bei(fern), "die Linie selbst bleibt — nur der Griff wird frei"
    finally:
        flow.dispose()
        session.release()
        dialog.close()
        viewport.close()


def test_a_stale_tool_context_hides_the_ghost_and_disables_accept(qt_app: QApplication) -> None:
    flow, session, viewport, dialog = _layout(qt_app, (900, 600), 1.0, "bottom")
    try:
        assert flow._tool.visible and flow._accept.isEnabled()
        flow._tool_context = None
        flow.redraw()
        assert not flow._tool.visible
        assert not flow._accept.isEnabled()
    finally:
        flow.dispose()
        session.release()
        dialog.close()
        viewport.close()


@pytest.mark.parametrize("size", [(1280, 800), (1920, 1080), (1920, 1200)])
def test_placement_controls_avoid_real_overlay_zones(
    qt_app: QApplication, size: tuple[int, int]
) -> None:
    """Echte Zonenmaße statt einer angenommenen festen Seitenbreite."""
    flow, session, viewport, dialog = _layout(qt_app, size, 1000.0, "bottom", with_zones=True)
    host = flow.window.overlay
    try:
        widgets = [
            flow._bar,
            *flow._reference_boxes[:2],
            *flow._centre_measures,
            flow._reference_boxes[2],
        ]
        for zone in (host.left, host.right, host.bottom):
            obstacle = QRect(viewport.mapFromGlobal(zone.mapToGlobal(QPoint())), zone.size())
            for widget in widgets:
                assert not widget.geometry().intersects(obstacle), (widget.objectName(), obstacle)
        previous = flow._bar.x()
        host.left.hide()
        qt_app.processEvents()
        qt_app.processEvents()
        assert flow._bar.x() < previous, "a hidden zone returns its actual space"
    finally:
        flow.dispose()
        session.release()
        dialog.close()
        host.close()


def test_dimension_fields_leave_the_placement_point_itself_visible(
    qt_app: QApplication,
) -> None:
    """Wo die Bohrung hinkommt, darf kein Eingabefeld liegen (Befund Robert, 09.09.2026).

    Jedes Maßfeld will in die **Mitte seiner eigenen Maßlinie**, und die Linien
    laufen von den Kanten auf den Setzpunkt zu. Ihre Mitten liegen damit auf
    halbem Weg dorthin — und je kürzer der Abstand zur Kante, desto näher
    rücken sie an den Punkt heran, bis das Feld ihn verdeckt. Die Platzsuche
    kannte bis dahin nur die anderen Felder als Hindernis.

    Geprüft wird der Punkt selbst und kein geratener Radius um ihn: Die Zusage
    lautet, dass der Kunde sieht, wohin er setzt, während er das Maß eintippt.
    """
    flow, session, viewport, dialog = _layout(qt_app, (900, 600), 1.0, "bottom")
    try:
        # **Das Werkzeug ist die Bohrung, nicht die Platte.** ``_layout`` gibt
        # dem Fluss die Platte als Werkzeug mit — hier zählt deren Ausdehnung
        # als Vorschau, und eine 40-mm-Platte bei zwölf Bildpunkten je
        # Millimeter sperrt 480 von 600 Bildpunkten: Kein Feld von 312
        # Bildpunkten Breite (seit der Bezugswahl vom 20.09.2026 mit seiner
        # Bezugsliste) fände daneben Platz. Die Zusage gilt der Bohrung von
        # sechzig Bildpunkten, die der Docstring nennt.
        flow._tool_context = PlacementTool(
            MeshData(trimesh.creation.cylinder(radius=2.5, height=10))
        )
        # Der Setzpunkt in die Bildmitte, damit die Felder ihn überhaupt von
        # allen Seiten umgeben können — am Rand weicht die Suche ohnehin aus.
        viewport.renderer.world_to_display = lambda point: (
            450 + (point[0] - 10) * 12,
            300 + (point[1] - 10) * 12,
            0.5,
        )
        flow.redraw()

        ratio = viewport._device_ratio()
        shown = viewport.view_point_of(flow._surface.point, flow._object_id)
        x, y, _depth = viewport.renderer.world_to_display(shown)
        target = QPoint(round(x / ratio), round(y / ratio))

        # **Gemessen wird gegen die Vorschau, nicht gegen einen Punkt.** Was
        # der Kunde sehen will, ist der Werkzeugkörper an seiner Stelle; ein
        # Feld neun Bildpunkte neben der Mitte deckt eine Bohrung von sechzig
        # Bildpunkten weiterhin zu. Die Ausdehnung kommt aus demselben Netz,
        # das der Fluss vorbereitet hat.
        halb = float(np.max(flow._tool_context.mesh.bounds.size[:2])) / 2.0
        rand = viewport.renderer.world_to_display(
            viewport.view_point_of(
                tuple(
                    np.asarray(flow._surface.point) + np.asarray(flow._surface.frame.x_axis) * halb
                ),
                flow._object_id,
            )
        )
        reach = max(
            1, round(math.hypot(rand[0] / ratio - target.x(), rand[1] / ratio - target.y()))
        )
        preview = QRect(target.x() - reach, target.y() - reach, 2 * reach, 2 * reach)
        assert reach > 1, "ohne ausgedehnte Vorschau prüft der Test nur einen Punkt"

        covering = [
            field.objectName() or type(field).__name__
            for field in (
                flow._bar,
                *flow._reference_boxes[:2],
                *flow._centre_measures,
                flow._reference_boxes[2],
            )
            if field.isVisible() and field.geometry().intersects(preview)
        ]
        assert not covering, (
            f"diese Felder liegen über der Vorschau {preview} am Setzpunkt: {covering}"
        )
    finally:
        flow.dispose()
        session.release()
        dialog.close()
        viewport.close()


def test_dimension_fields_stand_beside_the_body_and_keep_their_leaders(
    qt_app: QApplication,
) -> None:
    """Die Beschriftungen rücken vom Körper ab (Robert, 21.09.2026, RM-197).

    Jedes Maßfeld wollte in die Mitte seiner Maßlinie, und die läuft über das
    Teil: An Weg 1 standen drei Beschriftungen auf der Platte, zwei davon
    aufeinander („einen weiteren abstand zum modell und linien … damit ich
    auch weiß wo etwas hingeht"). Die projizierte Hülle des Trägers ist seither
    belegt; die Verbindungslinie je Feld sagt weiterhin, welches Maß es ist.
    """
    flow, session, viewport, dialog = _layout(qt_app, (900, 600), 1.0, "bottom")
    try:
        flow._tool_context = PlacementTool(
            MeshData(trimesh.creation.cylinder(radius=2.5, height=10))
        )
        # Die 40-mm-Platte mittig im Bild, sechs Bildpunkte je Millimeter:
        # 240 mal 240 Bildpunkte, ringsum bleibt Platz für jedes Feld.
        viewport.renderer.world_to_display = lambda point: (
            450 + point[0] * 6,
            300 + point[1] * 6,
            0.5,
        )
        flow.redraw()

        ratio = viewport._device_ratio()
        low, high = flow._prepared_mesh.bounds.minimum, flow._prepared_mesh.bounds.maximum
        xs, ys = [], []
        for corner in ((low[0], low[1], 0.0), (high[0], high[1], 0.0)):
            x, y, _depth = viewport.renderer.world_to_display(
                viewport.view_point_of(corner, flow._object_id)
            )
            xs.append(round(x / ratio))
            ys.append(round(y / ratio))
        body = QRect(QPoint(min(xs), min(ys)), QPoint(max(xs), max(ys)))
        assert body.width() > 200 and body.height() > 200, "der Körper muss im Bild etwas belegen"

        fields = [*flow._reference_boxes[:2], *flow._centre_measures, flow._reference_boxes[2]]
        for field in fields:
            assert field.isVisible(), field.objectName()
            assert not field.geometry().intersects(body), (field.objectName(), field.geometry())
        # Und jedes versetzte Feld behält seine Verbindungslinie — zur **Mitte**
        # seiner Maßlinie (Robert, 21.09.2026: „schöner wäre noch wenn die
        # linien von den maßen zu den mittellinien jeweils gehen").
        assert len(flow._canvas.leaders) >= len(fields)
        targets = [(start + end) / 2 for start, end in flow._canvas.lines]
        # Die Mitte eines erkannten Lochs hat keine Linie: Ihr Etikett hängt
        # am Punkt selbst.
        for spot in (flow._surface.point, flow._surface.centres[0].point):
            x, y, _depth = viewport.renderer.world_to_display(
                viewport.view_point_of(spot, flow._object_id)
            )
            targets.append(QPointF(x / ratio, y / ratio))
        for _tail, anchor in flow._canvas.leaders:
            near = min((anchor - target).manhattanLength() for target in targets)
            assert near < 1.0, ("Verbindung endet nicht an einer Linienmitte", anchor)
    finally:
        flow.dispose()
        session.release()
        dialog.close()
        viewport.close()


def test_dimension_fields_keep_their_places_when_the_spot_moves_a_little(
    qt_app: QApplication,
) -> None:
    """Ein getippter Wert lässt die Felder stehen (Robert, 22.09.2026: „danach
    springen sie auch alle und tauschen sich").

    Jeder Aufbau suchte jedem Feld den nächsten freien Platz neu; der Setzpunkt
    einen Millimeter weiter, und die Kandidaten lagen anders. Ein Feld behält
    seinen Platz, solange er frei ist und das Maß nicht weit gewandert ist —
    erst ein großer Sprung, etwa eine Kameradrehung, ordnet neu.
    """
    flow, session, viewport, dialog = _layout(qt_app, (900, 600), 1.0, "bottom")
    try:
        flow._tool_context = PlacementTool(
            MeshData(trimesh.creation.cylinder(radius=2.5, height=10))
        )
        viewport.renderer.world_to_display = lambda point: (
            450 + point[0] * 6,
            300 + point[1] * 6,
            0.5,
        )
        flow.redraw()
        fields = [*flow._reference_boxes[:2], *flow._centre_measures, flow._reference_boxes[2]]
        before = {field.objectName(): field.geometry() for field in fields}

        # Der Setzpunkt wandert einen Millimeter — sechs Bildpunkte. Die Felder
        # folgen höchstens diesem Stück; keines springt an eine andere Kante,
        # keines tauscht mit einem anderen den Platz.
        flow._surface = dataclasses.replace(flow._surface, point=(11, 10, 0))
        flow.redraw()
        after = {field.objectName(): field.geometry() for field in fields}
        for name, rect in before.items():
            moved_by = (after[name].topLeft() - rect.topLeft()).manhattanLength()
            assert moved_by <= 6, (name, rect, after[name])

        # Und weit weg neu: Die Kamera schwenkt, alles liegt anders.
        viewport.renderer.world_to_display = lambda point: (
            450 + point[1] * 6,
            300 - point[0] * 6,
            0.5,
        )
        flow.redraw()
        moved = {field.objectName(): field.geometry() for field in fields}
        assert moved != before, "nach einer Kameradrehung ordnet sich das Bild neu"
    finally:
        flow.dispose()
        session.release()
        dialog.close()
        viewport.close()


def test_the_measure_with_the_focus_lights_up_in_the_view(qt_app: QApplication) -> None:
    """Wer in ein Maßfeld klickt, sieht im Bild, was er ändert (Robert,
    22.09.2026: „ich hab hier auch keine ahnung wo welcher wert hingeht").

    Ein Kantenmaß leuchtet mit seiner Maßlinie **und** seiner Bezugskante, ein
    Mittenmaß mit seiner Linie; ohne Fokus leuchtet nichts. Gezeichnet wird es
    als eigenes Element über allen anderen, in der Akzentfarbe.
    """
    flow, session, viewport, dialog = _layout(qt_app, (900, 600), 1.0, "bottom")
    try:
        flow._tool_context = PlacementTool(
            MeshData(trimesh.creation.cylinder(radius=2.5, height=10))
        )
        viewport.renderer.world_to_display = lambda point: (
            450 + point[0] * 6,
            300 + point[1] * 6,
            0.5,
        )
        flow.redraw()
        assert flow._canvas.focus == [], "ohne Fokus leuchtet nichts"
        lit = next(entry for entry in viewport.renderer.lines if entry["name"] == "dimension_focus")
        assert not lit["item"].visible

        edge_field = flow._measures[0]
        edge_field.setFocus()
        qt_app.processEvents()
        flow.redraw()
        assert len(flow._canvas.focus) == 2, "Bezugskante und Maßlinie"
        reference, line = flow._canvas.focus
        assert reference in flow._canvas.references and line in flow._canvas.lines
        assert lit["item"].visible
        assert lit["colour"] == viewport.palette().highlight().color().name()

        centre_field = flow._centre_measures[0]
        centre_field.setFocus()
        qt_app.processEvents()
        flow.redraw()
        assert len(flow._canvas.focus) == 1 and flow._canvas.focus[0] in flow._canvas.lines
        assert flow._canvas.focus[0] != line, "jetzt leuchtet das andere Maß"
    finally:
        flow.dispose()
        session.release()
        dialog.close()
        viewport.close()


def test_fields_stand_at_their_lines_when_the_body_outgrows_the_view(
    qt_app: QApplication,
) -> None:
    """Ragt der Körper über das Bild hinaus, stehen die Felder an ihrer Maßlinie
    (Robert, 22.09.2026: „wo welches maß hinkommt seh ich immer noch nicht" —
    „solange man den körper vollständig sieht").

    Am Halter mit 220 mm, nah herangezoomt, schob die Hülle als Hindernis jedes
    Feld an den Bildrand, dreihundert Punkte von seiner Linie weg. Jetzt: kurze
    Verbindungen, kein Feld über einer Linie, keines unter dem Vorschauband.
    """
    from app.ui.placement_flow import _clear_of_lines

    flow, session, viewport, dialog = _layout(qt_app, (900, 600), 1.0, "bottom")
    try:
        flow._tool_context = PlacementTool(
            MeshData(trimesh.creation.cylinder(radius=2.5, height=10))
        )
        # Dreißig Bildpunkte je Millimeter: Die 40-mm-Platte ist 1200 Punkte
        # breit und ragt an beiden Seiten aus dem 900 Punkte breiten Bild.
        viewport.renderer.world_to_display = lambda point: (
            450 + (point[0] - 10) * 30,
            300 + (point[1] - 10) * 30,
            0.5,
        )
        flow.redraw()
        qt_app.processEvents()
        fields = [*flow._reference_boxes[:2], *flow._centre_measures, flow._reference_boxes[2]]
        ink = [*flow._canvas.lines, *flow._canvas.references, *flow._canvas.extensions]
        assert ink, "ohne Tinte misst der Test nichts"
        for field in fields:
            assert field.isVisible(), field.objectName()
            assert _clear_of_lines(field.geometry(), ink), (field.objectName(), field.geometry())
        # Nicht weiter als anderthalb Feldbreiten: Es steht neben seiner Linie
        # und nicht am Bildrand — ein Feld an einer Ecke des Bildes hängt an
        # seiner eigenen Breite, mehr nicht.
        widest = max(field.width() for field in fields)
        for tail, anchor in flow._canvas.leaders:
            assert (tail - anchor).manhattanLength() <= 1.5 * widest, (
                "die Verbindung ist kurz — das Feld steht an seiner Linie",
                tail,
                anchor,
            )
    finally:
        flow.dispose()
        session.release()
        dialog.close()
        viewport.close()


def test_no_field_hides_under_the_preview_banner(qt_app: QApplication) -> None:
    """Das Vorschauband oben deckte zwei Felder zu (Robert, 22.09.2026)."""
    from PySide6.QtWidgets import QLabel

    flow, session, viewport, dialog = _layout(qt_app, (900, 600), 1.0, "top")
    try:
        flow._tool_context = PlacementTool(
            MeshData(trimesh.creation.cylinder(radius=2.5, height=10))
        )
        banner = QLabel("Vorschau — noch nicht übernommen", viewport)
        banner.setGeometry(0, 0, 900, 60)
        banner.show()
        viewport.banner = banner
        viewport.renderer.world_to_display = lambda point: (
            450 + (point[0] - 10) * 30,
            80 + (point[1] - 10) * 30,
            0.5,
        )
        flow.redraw()
        qt_app.processEvents()
        fields = [*flow._reference_boxes[:2], *flow._centre_measures, flow._reference_boxes[2]]
        for field in fields:
            assert not field.geometry().intersects(banner.geometry()), (
                field.objectName(),
                field.geometry(),
            )
    finally:
        flow.dispose()
        session.release()
        dialog.close()
        viewport.close()


def test_the_mouth_outline_marks_the_spot_instead_of_the_whole_cylinder(
    qt_app: QApplication,
) -> None:
    """Wo das Werkzeug die Fläche trifft, steht ein Umriss — und der Körper tritt zurück.

    Der halbtransparente Werkzeugkörper zeigte den ganzen Zylinder, auch den
    Teil außerhalb des Materials; beim Drehen der Ansicht war damit schwer zu
    sehen, wo das Loch hinkommt (Befund Robert, 09.09.2026: „es reicht mir,
    wenn ich den Kreis auf der Oberfläche in Orange sehe").

    Geprüft wird beides zusammen, weil es eine Entscheidung ist: Der Umriss
    erscheint **und** der Körper wird unsichtbar. Gebaut wird er weiter — an
    ihm hängt, ob gesetzt werden kann.
    """
    flow, session, viewport, dialog = _layout(qt_app, (900, 600), 1.0, "bottom")
    try:
        # Ein Werkzeug mit Mündung in der Fläche: der Zylinder endet bei z = 0,
        # so wie ``prepare_tool`` ihn legt.
        bohrer = trimesh.creation.cylinder(radius=2.5, height=20.0)
        bohrer.apply_translation((0.0, 0.0, -10.0))
        flow._tool_context = PlacementTool(MeshData(bohrer))
        flow._tool = _Item()
        viewport.renderer.world_to_display = lambda point: (
            450 + (point[0] - 10) * 12,
            300 + (point[1] - 10) * 12,
            0.5,
        )
        flow.redraw()

        umriss = flow._canvas.outline
        assert len(umriss) >= 3, "ohne Umriss prüft der Test nichts"
        breite = max(p.x() for p in umriss) - min(p.x() for p in umriss)
        hoehe = max(p.y() for p in umriss) - min(p.y() for p in umriss)
        # Ø5 mm bei zwölf Bildpunkten je Millimeter sind sechzig.
        assert breite == pytest.approx(60.0, abs=2.0), breite
        assert hoehe == pytest.approx(60.0, abs=2.0), hoehe
        assert flow._canvas.outline_colour is not None, "der Umriss braucht seine Farbe"

        assert flow._tool is not None, "der Körper wird weiter gebaut"
        assert flow._tool.visible is False, "neben dem Umriss tritt er zurück"

        # **Und ohne Mündung bleibt es beim Körper.** Ein Werkzeug, dessen
        # Grundfläche nicht in der Ebene liegt, hat keinen Umriss — dort ist
        # der Körper die einzige Auskunft.
        wuerfel = trimesh.creation.box((6.0, 6.0, 6.0))
        flow._tool_context = PlacementTool(MeshData(wuerfel))
        flow.redraw()
        assert not flow._canvas.outline, "ein Würfel um den Ursprung hat keine Mündung"
        assert flow._tool.visible is True, "ohne Umriss zeigt der Körper die Stelle"
    finally:
        flow.dispose()
        session.release()
        dialog.close()
        viewport.close()


def test_placement_refreshes_when_only_a_nested_project_measure_changes(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gleicher Skizzentext darf nach einer Parameteränderung keinen alten Werkzeugcache lesen."""
    import time

    from app.core.types import Parameter
    from app.ui import placement_flow

    flow, session, viewport, dialog = _layout(qt_app, (900, 600), 1.0, "bottom")
    calls = []

    def prepare(_spec, _values, _profile, *, parameters, **_kwargs):
        calls.append(dict(parameters))
        return PlacementTool(MeshData(trimesh.creation.box((parameters["span"], 5, 4))))

    def request():
        flow._request_tool()
        until = time.monotonic() + 5.0
        while flow._tool_busy and time.monotonic() < until:
            qt_app.processEvents()
            time.sleep(0.005)
        assert not flow._tool_busy
        assert flow._tool_context is not None

    monkeypatch.setattr(placement_flow.placement, "prepare_tool", prepare)
    try:
        session.project.document.parameters = {
            "base": Parameter("base", 30),
            "span": Parameter("span", 0, expression="=@base*2"),
        }
        request()
        assert flow._tool_context.mesh.bounds.size == pytest.approx((60, 5, 4))
        request()
        assert len(calls) == 1
        session.project.document.parameters["base"] = Parameter("base", 40)
        request()
        assert flow._tool_context.mesh.bounds.size == pytest.approx((80, 5, 4))
        assert [call["span"] for call in calls] == [60, 80]
    finally:
        flow.dispose()
        session.release()
        dialog.close()
        viewport.close()


def _layout(
    qt_app: QApplication, size: tuple[int, int], scale: float, corner: str, *, with_zones=False
):
    """Eine fertige Platzierungsabsicht; nur ihre Bildprojektion wird gesteuert."""
    session = Session()
    mesh = MeshData(trimesh.creation.box((40, 40, 10)))
    result = EvaluationResult(Scene(objects={"obj_1": SceneObject("obj_1", "Platte", mesh)}))
    session.last_result = result
    session.result_current = True
    viewport = _Viewport()
    viewport.resize(*size)
    viewport.show_scene(result)
    viewport.renderer.world_to_display = lambda point: (
        size[0] - 4 + (point[0] - 10) * scale,
        (size[1] - 4 if corner == "bottom" else 4) + (point[1] - 10) * scale,
        0.5,
    )
    spec = REGISTRY.get("drill_hole")
    dialog = OperationDialog(spec, {"obj_1": "Platte"})
    window = SimpleNamespace(
        viewport=viewport, session=session, _clear_preview=session.cancel_preview
    )
    if with_zones:
        host = OverlayHost(viewport)
        host.resize(*size)
        zones = [QFrame(), QFrame(), QFrame()]
        for index, zone in enumerate(zones):
            layout = QVBoxLayout(zone)
            label = QLabel(
                "Objekte" if index == 0 else "Prüfbericht" if index == 1 else "Werkzeuge"
            )
            label.setMinimumHeight(420 if index < 2 else 48)
            layout.addWidget(label)
        host.set_zones(*zones)
        host.show()
        host.reflow()
        window.overlay = host
    flow = PlacementFlow(dialog, window, lambda: spec, lambda: ("obj_1",))
    flow._result = result
    flow._prepared_mesh = mesh
    flow._object_id = "obj_1"
    flow._centre_id = "hole_1"
    flow._tool = _Item()
    flow._tool_context = PlacementTool(mesh)
    flow._surface = SurfacePlacement(
        point=(10, 10, 0),
        normal=(0, 0, 1),
        frame=PlaneFrame((0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1)),
        planar=True,
        face_indices=(0,),
        edges=(
            EdgeReference("a", (0, 0, 0), (0, 40, 0), (1, 0, 0), 10),
            EdgeReference("b", (0, 0, 0), (40, 0, 0), (0, 1, 0), 10),
        ),
        centres=(CentreReference("hole_1", (0, 0, 0), (10, 10), 14.142135623730951),),
    )
    # **Fläche und Vorbereitung gehen zu zweit**, wie ``at_point`` sie der
    # Anwendung liefert: Seit der Bezugswahl (20.09.2026) nummeriert
    # ``redraw`` jedes Kantenmaß über ``_prepared.edges``. Ohne die
    # Vorbereitung warf das im Ereignisfilter beim Anzeigen — und daraus wurde
    # unter PySide ein nativer Abriss (Exit 139) statt eines roten Tests
    # (gemessen am 21.09.2026, dreizehn Portionen des Release-Tors).
    flow._prepared = PreparedSurface(
        frame=flow._surface.frame,
        planar=True,
        face_indices=(0,),
        edges=flow._surface.edges,
        centres=(("hole_1", (0, 0, 0)),),
        area=Polygon(((-20, -20), (20, -20), (20, 20), (-20, 20))),
    )
    flow.active = True
    viewport.show()
    viewport.activateWindow()
    flow._bar.show()
    qt_app.processEvents()
    flow.redraw()
    return flow, session, viewport, dialog
