"""Maßfelder bleiben am Bildrand getrennt und ihrer Maßlinie zugeordnet.

Die Projektion ist kontrolliert; Widgets, Größen, Fokus und redraw laufen echt.
Kein Renderer und keine Geometrieoperation werden für diese Anordnung benötigt.
"""

from __future__ import annotations

import math
from itertools import combinations
from types import SimpleNamespace

import numpy as np
import pytest
import trimesh
from PySide6.QtCore import QPoint, QPointF, QRect
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QFrame, QLabel, QVBoxLayout, QWidget

from app.core.geom.mesh import MeshData
from app.core.registry import REGISTRY
from app.core.scene.evaluate import EvaluationResult
from app.core.scene.placement import CentreReference, EdgeReference, PlacementTool, SurfacePlacement
from app.core.types import PlaneFrame, Scene, SceneObject
from app.ui.op_dialog import OperationDialog
from app.ui.overlay import OverlayHost
from app.ui.placement_flow import PlacementFlow, _Dimensions
from app.ui.session import Session
from tests.test_surface_placement_ui import _Item, _Viewport


def test_dimension_ink_does_not_cover_the_empty_viewport_area(qt_app: QApplication) -> None:
    """Eine leere Qt-Overlayfläche darf keinen alten Backingstore über das Renderbild legen."""
    flow, session, viewport, dialog = _layout(qt_app, (900, 600), 1.0, "bottom")
    viewport.renderer.world_to_display = lambda point: (80 + point[0] * 20, 80 + point[1] * 20, 0.5)
    flow.redraw()
    canvas = flow._canvas
    try:
        assert not canvas.mask().isEmpty(), "eine leere Qt-Maske gibt das ganze Rechteck frei"
        assert canvas.mask().contains(QPoint(85, 280)), "die freie Maßlinie bleibt sichtbar"
        assert not canvas.mask().contains(QPoint(850, 550)), "hier muss allein der Renderer malen"

        viewport.renderer.world_to_display = lambda point: (
            380 + point[0] * 20,
            280 + point[1] * 20,
            0.5,
        )
        flow.redraw()
        assert not canvas.mask().contains(QPoint(85, 280)), (
            "die alte Maßlage gibt ihre Pixel zurück"
        )
        assert canvas.mask().contains(QPoint(385, 480))

        flow._surface = None
        flow.redraw()
        assert canvas.isHidden(), "ohne Tinte darf keine unmaskierte Vollfläche erscheinen"
    finally:
        flow.dispose()
        session.release()
        dialog.close()
        viewport.close()


@pytest.mark.parametrize("with_centre", [False, True])
def test_dimension_ink_leaves_the_actual_value_and_caption_rectangles_clear(
    qt_app: QApplication, with_centre: bool
) -> None:
    """Die native Stapelreihenfolge darf keine Pfeile durch Zahlen oder Mittelpunkttext ziehen."""
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
            assert not flow._canvas.mask().isEmpty(), "freie Pfeilstücke bleiben sichtbar"
            fields = [flow._bar, *flow._measures]
            if with_centre:
                fields.extend([*flow._centre_measures, flow._centre])
            for field in fields:
                assert field.isVisible()
                assert not flow._canvas.mask().intersects(field.geometry()), (
                    field.objectName(),
                    field.geometry(),
                )
    finally:
        flow.dispose()
        session.release()
        dialog.close()
        viewport.close()


def test_placement_ghost_uses_a_filled_surface_without_tessellation_edges(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der echte Werkzeug-Rückruf reicht dem Renderer dieselbe ungestörte Ghost-Fläche."""
    flow, session, viewport, dialog = _layout(qt_app, (900, 600), 1.0, "bottom")
    styles = []

    def add_surface(_points, _faces, *, name, style):
        assert name == "surface_placement_tool"
        styles.append(style)
        return _Item()

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


def test_moving_dimension_ink_clears_its_previous_qt_pixels(qt_app: QApplication) -> None:
    """Rasternachweis für Löschen und neue Striche; die GPU-Abnahme bleibt ein eigener Lauf."""
    parent = QWidget()
    parent.resize(320, 240)
    palette = parent.palette()
    background = QColor("#204060")
    palette.setColor(QPalette.ColorRole.Window, background)
    parent.setPalette(palette)
    parent.setAutoFillBackground(True)
    canvas = _Dimensions(parent)
    palette = canvas.palette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#101010"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#ffffff"))
    canvas.setPalette(palette)
    canvas.setGeometry(parent.rect())
    canvas.lines = [(QPointF(20, 40), QPointF(180, 40))]
    try:
        parent.show()
        canvas.refresh()
        qt_app.processEvents()
        first = parent.grab().toImage()
        assert first.pixelColor(80, 40) != background
        assert first.pixelColor(250, 190) == background

        canvas.lines = [(QPointF(20, 140), QPointF(180, 140))]
        canvas.refresh()
        qt_app.processEvents()
        second = parent.grab().toImage()
        assert second.pixelColor(80, 40) == background
        assert second.pixelColor(80, 140) != background
        assert second.pixelColor(250, 190) == background
    finally:
        parent.close()
        parent.deleteLater()


def test_resizing_a_dimension_field_does_not_mix_nested_line_lists(qt_app: QApplication) -> None:
    """Das eigene adjustSize darf im Würfelfall keine dritte oder weitere Maßlinie anhängen."""
    flow, session, viewport, dialog = _layout(qt_app, (900, 600), 1.0, "bottom")
    flow._centre_id = ""
    flow.redraw()
    try:
        assert len(flow._canvas.lines) == 2
        field = flow._measures[0]
        # Ein echter synchroner QWidget-Resize, dessen bisheriger Rückruf die
        # Wunschgröße wiederherstellt und dabei mitten im Aufbau erneut eintritt.
        field.resize(field.width() + 31, field.height())
        qt_app.processEvents()
        assert len(flow._canvas.lines) == 2, "eigene Feldgrößenänderung vermischt mehrere Aufbauten"
        assert len(flow._canvas.leaders) == 2
        assert len({(a.x(), a.y(), b.x(), b.y()) for a, b in flow._canvas.lines}) == 2
        viewport.resize(960, 640)
        qt_app.processEvents()
        assert flow._canvas.size() == viewport.size(), (
            "die echte Ansichtsgröße wird weiter verfolgt"
        )
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
        widgets = [*flow._measures, *flow._centre_measures, flow._centre]
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
        widgets = [*flow._measures, *flow._centre_measures, flow._centre]
        frei = [widget.geometry() for widget in widgets]

        viewport.handle = ((10.0, 10.0, 0.0), 30.0)
        flow.redraw()
        qt_app.processEvents()
        mitte = viewport.renderer.world_to_display((10.0, 10.0, 0.0))
        rand = viewport.renderer.world_to_display((40.0, 10.0, 0.0))
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
        widgets = [flow._bar, *flow._measures, *flow._centre_measures, flow._centre]
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
        # der Kunde sehen will, ist der Werkzeugkoerper an seiner Stelle; ein
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
        assert reach > 1, "ohne ausgedehnte Vorschau prueft der Test nur einen Punkt"

        covering = [
            field.objectName() or type(field).__name__
            for field in (flow._bar, *flow._measures, *flow._centre_measures, flow._centre)
            if field.isVisible() and field.geometry().intersects(preview)
        ]
        assert not covering, (
            f"diese Felder liegen ueber der Vorschau {preview} am Setzpunkt: {covering}"
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
    flow.active = True
    viewport.show()
    viewport.activateWindow()
    flow._bar.show()
    qt_app.processEvents()
    flow.redraw()
    return flow, session, viewport, dialog
