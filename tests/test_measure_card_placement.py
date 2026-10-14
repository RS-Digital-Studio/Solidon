"""Der echte Maßfluss erhält den gewählten Kartenort und hält seine Maßfelder frei."""

import json
import sys
from contextlib import contextmanager
from itertools import combinations

import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtGui import QFont
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QFormLayout, QLabel, QWidget

from app.i18n.catalog import available_languages
from app.ui.labels import LengthSpin
from app.ui.measure_card_drag import MeasureCardDrag
from app.ui.panels import FIELD_PROPERTY
from app.ui.style import NORMAL
from tests.test_feature_front_contract import customer_theme as customer_theme
from tests.test_measure_group_layout import language as language
from tests.test_measure_group_layout import selected_hole as selected_hole
from tests.ui_helpers import (
    begin_card_drag,
    end_card_drag,
    measure_more_heading,
    placement_layout,
    settle_measure_layout,
    wait_until,
)
from tests.ui_helpers import session as session
from tests.ui_helpers import window as window


@contextmanager
def _layout_trace():
    """Nur beobachten, welche echte Suche endet und welche Rechtecke sie erhält."""
    calls = []
    previous = sys.getprofile()

    def observe(frame, event, result):
        if (
            event == "return"
            and frame.f_code.co_name in ("find_places", "emergency_rows")
            and frame.f_code.co_qualname.startswith("PlacementFlow.redraw.<locals>.")
        ):
            values = frame.f_locals
            calls.append(
                {
                    "name": frame.f_code.co_name,
                    "failed": result is None,
                    "bounds": values["bounds"].getRect(),
                    "fields": [
                        widget.size().toTuple()
                        for widget, _wanted, _anchor in values.get(
                            "targets", values.get("pending", ())
                        )
                    ],
                }
            )

    sys.setprofile(observe)
    try:
        yield calls
    finally:
        sys.setprofile(previous)


def _title(flow):
    title = flow._measure_group.layout().itemAt(0, QFormLayout.ItemRole.SpanningRole).widget()
    assert isinstance(title, QLabel)
    return title


def _move_card(flow, destination):
    title = _title(flow)
    drag = flow._measure_box.findChild(MeasureCardDrag)
    assert drag is not None
    print("drag_before", _geometry(flow), "destination", destination.toTuple())
    end = begin_card_drag(title, destination - flow._measure_box.pos())
    print(
        "drag_before_release",
        _geometry(flow),
        "start",
        drag._start.getRect(),
        "moving",
        drag._moving.getRect() if drag._moving is not None else None,
    )
    end_card_drag(title, end)
    print(
        "drag_after_release",
        _geometry(flow),
        "place",
        drag._place,
        "placed_width",
        drag._placed_width,
    )
    assert drag.placed_rect() == flow._measure_box.geometry()
    return drag


def _assert_dimensions_clear(flow):
    fields = [
        field
        for field in (
            *flow._reference_boxes,
            *flow._centre_measures,
            flow._depth_measure,
            flow._rest,
        )
        if field.isVisibleTo(flow.viewport)
    ]
    assert fields, "die Gegenprobe braucht tatsächlich sichtbare Maßfelder"
    for field in fields:
        assert flow.viewport.rect().contains(field.geometry())
        assert flow._measure_drag._room.contains(field.geometry()), (
            field.geometry(),
            flow._measure_drag._room,
        )
        assert not flow._measure_box.geometry().intersects(field.geometry()), (
            field.objectName(),
            field.geometry(),
            flow._measure_box.geometry(),
        )
    for first, second in combinations(fields, 2):
        assert not first.geometry().intersects(second.geometry())
    assert len(flow._canvas.leaders) == len(fields) + 1


def _geometry(flow):
    """Tatsächlicher Kartenraum und alle sichtbaren Maßfelder für den Laufbeleg."""
    overlay = getattr(flow.window, "overlay", None)
    return json.dumps(
        {
            "viewport": flow.viewport.rect().getRect(),
            "available": flow._measure_drag._room.getRect(),
            "card": flow._measure_box.geometry().getRect(),
            "overlay_moves": {
                str(key): {"start": move.startValue().getRect(), "end": move.endValue().getRect()}
                for key, move in getattr(overlay, "_moves", {}).items()
            },
            "fields": [
                {"index": index, "name": field.objectName(), "rect": field.geometry().getRect()}
                for index, field in enumerate(
                    (
                        *flow._reference_boxes,
                        *flow._centre_measures,
                        flow._depth_measure,
                        flow._rest,
                    )
                )
                if field.isVisibleTo(flow.viewport)
            ],
        }
    )


@pytest.mark.parametrize("language", available_languages(), indirect=True)
def test_chosen_place_survives_fold_value_and_missing_surface(
    selected_hole, qt_app, language, monkeypatch
):
    """Vollständige Sprachkarten: Titel, Klappe, Wert und beide Anordnungswege."""
    window, _object_id, _hole_ids = selected_hole
    flow = window._quiet_placement
    settle_measure_layout(qt_app)
    group = flow._measure_group
    title = _title(flow)
    diameter = next(
        widget
        for widget in group.findChildren(LengthSpin)
        if widget.property(FIELD_PROPERTY) == "diameter"
    )
    origin = group.findChild(QLabel, "feature-measure-source")
    assert title.property("level") == "section"
    assert title.font().pointSizeF() > diameter.font().pointSizeF()
    assert title.font().weight() >= QFont.Weight.DemiBold
    assert origin is not None and origin.property("level") == "caption"
    assert origin.font().pointSizeF() < diameter.font().pointSizeF()
    assert group.layout().verticalSpacing() == NORMAL

    before = flow._measure_box.pos()
    destination = QPoint(window.viewport.width() // 2, 90)
    _move_card(flow, destination)
    settle_measure_layout(qt_app)
    chosen = flow._measure_box.pos()
    print("geometry_after_drag", _geometry(flow))
    assert chosen != before
    assert (chosen - destination).manhattanLength() <= 1
    _assert_dimensions_clear(flow)
    heading = measure_more_heading(flow)
    for expanded in (True, False):
        QTest.mouseClick(heading, Qt.MouseButton.LeftButton)
        settle_measure_layout(qt_app)
        print(f"geometry_expanded_{expanded}", _geometry(flow))
        assert heading.isChecked() is expanded
        assert flow._measure_box.pos() == chosen
        _assert_dimensions_clear(flow)

    old_value = diameter.value_mm()
    diameter.set_value_mm(old_value + 1.0)
    assert window.session.wait_for_idle(30_000)
    settle_measure_layout(qt_app)
    assert diameter.value_mm() == pytest.approx(old_value + 1.0)
    assert window._quiet_placement is flow and flow.active
    assert flow._measure_box.pos() == chosen
    _assert_dimensions_clear(flow)
    with monkeypatch.context() as patch:
        patch.setattr(flow, "_surface", None)
        flow.redraw()
        assert flow._measure_box.isVisibleTo(window.viewport)
        assert flow._measure_box.pos() == chosen
    flow.redraw()
    assert flow._measure_box.pos() == chosen


def test_cancel_and_new_order_reuse_the_card_without_old_place(selected_hole, qt_app):
    """Abbrechen löst den alten Fluss; seine abgelegte Karte beginnt ohne Nutzerort."""
    window, object_id, hole_ids = selected_hole
    old = window._quiet_placement
    settle_measure_layout(qt_app)
    card = old._measure_box
    drag = _move_card(old, QPoint(window.viewport.width() // 2, 100))
    QTest.mouseClick(old._measure_cancel, Qt.MouseButton.LeftButton)
    settle_measure_layout(qt_app)
    assert not old.active and not old._links
    window.object_tree.select_feature(object_id, hole_ids[1])
    assert window.session.wait_for_idle(30_000)
    wait_until(
        qt_app, lambda: window._quiet_placement is not None and window._quiet_placement.active
    )
    current = window._quiet_placement
    settle_measure_layout(qt_app)
    assert current is not old
    assert current._measure_box is card
    assert current._measure_box.findChild(MeasureCardDrag) is drag
    assert drag.placed_rect() is None
    _move_card(current, QPoint(window.viewport.width() // 2, 150))
    assert not old.active and not old._links


def test_drag_boundary_and_growing_card_keep_the_saved_place(selected_hole, qt_app):
    """Die Karte endet vor Seiten-/Bodenkarten und kehrt nach dem Zuklappen zurück."""
    window, _object_id, _hole_ids = selected_hole
    flow = window._quiet_placement
    settle_measure_layout(qt_app)
    print("boundary_before_settling", _geometry(flow))
    wait_until(qt_app, lambda: not window.overlay._moves and window.overlay._pending is None)
    settle_measure_layout(qt_app)
    drag = _move_card(flow, QPoint(10_000, 10_000))
    assert drag._place.edge == "bottom-right"
    place = drag._place
    wait_until(qt_app, lambda: not window.overlay._moves and window.overlay._pending is None)
    settle_measure_layout(qt_app)
    chosen = flow._measure_box.pos()
    chosen_room = QRect(drag._room)
    print("boundary_chosen", _geometry(flow))
    for expanded in (True, False):
        QTest.mouseClick(measure_more_heading(flow), Qt.MouseButton.LeftButton)
        wait_until(qt_app, lambda: not window.overlay._moves and window.overlay._pending is None)
        settle_measure_layout(qt_app)
        print(f"boundary_expanded_{expanded}", _geometry(flow))
        assert measure_more_heading(flow).isChecked() is expanded
        rect = flow._measure_box.geometry()
        assert drag._place == place
        assert drag._room == chosen_room
        assert rect.bottomRight() == drag._room.bottomRight()
        assert window.viewport.rect().contains(rect)
        for role in ("left", "right", "bottom"):
            zone = getattr(window.overlay, role)
            if zone.isVisibleTo(window.overlay):
                occupied = QRect(
                    window.viewport.mapFromGlobal(zone.mapToGlobal(QPoint())), zone.size()
                )
                assert not rect.intersects(occupied), (role, rect, occupied)
    assert flow._measure_box.pos() == chosen


@pytest.mark.parametrize("crowded", [False, True])
@pytest.mark.parametrize("destination", [(50, 50), (800, 100), (1500, 500), (700, 650)])
def test_manually_placed_card_is_an_obstacle_also_in_the_emergency_path(
    qt_app, monkeypatch, crowded, destination
):
    """Normale und durch großen Griff verstellte Fläche lassen alle Zahlen erreichbar."""
    flow, session, viewport, dialog = placement_layout(qt_app, (1920, 1080), 1.0, "bottom")
    moving = None
    try:
        monkeypatch.setattr(dialog, "values_stand_elsewhere", True)
        group = QWidget(viewport)
        layout = QFormLayout(group)
        title = QLabel("Bohrung ändern", group)
        title.setMinimumSize(300, 200)
        layout.addRow(title)
        if crowded:
            # Ein breiter, hoher Inhalt rollt nach den vorhandenen Größenregeln.
            # Fünf gleich breite Felder passen oberhalb in eine volle Zeile;
            # die Nähe-Suche zerteilt diese freie Zeile dagegen ungünstig.
            title.setMinimumSize(viewport.width(), 30)
            contents = QWidget(group)
            contents.setMinimumHeight(2000)
            layout.addRow(contents)
            for field in (*flow._reference_boxes, *flow._centre_measures):
                field.setMinimumWidth(370)
        flow.set_measure_fields(
            group, editors=(), interpret=lambda: True, refresh=lambda _values: None
        )
        viewport.renderer.world_to_display = lambda point: (
            960 + point[0] * 10,
            540 + point[1] * 10,
            0.5,
        )
        if crowded:
            # Ein sehr großer projizierter Griff sperrt die normale Suche.
            monkeypatch.setattr(viewport, "gizmo_reach", lambda: ((0.0, 0.0, 0.0), 1000.0))
        flow.redraw()
        _move_card(flow, QPoint(*destination))
        if crowded:
            # Während des zweiten echten Zugs an die Oberkante liegt die freie
            # Zeile unter der Karte. Erst Loslassen rastet die sehr hohe Karte
            # wieder unten ein; auch unterwegs dürfen keine Felder verschwinden.
            moving = begin_card_drag(_title(flow), QPoint(12, 12) - flow._measure_box.pos())
        chosen = flow._measure_box.pos()
        with _layout_trace() as calls:
            flow.redraw()
        print("layout_calls", json.dumps(calls))
        if crowded:
            searches = [call for call in calls if call["name"] == "find_places"]
            assert len(searches) == 2 and all(call["failed"] for call in searches)
            assert any(call["name"] == "emergency_rows" for call in calls)
        print("geometry_after_drag", _geometry(flow))
        _assert_dimensions_clear(flow)
        for _ in range(3):
            flow.redraw()
            assert flow._measure_box.pos() == chosen
            _assert_dimensions_clear(flow)
    finally:
        if moving is not None:
            end_card_drag(_title(flow), moving)
        flow.dispose()
        session.release()
        dialog.close()
        viewport.close()
