"""Eine aufgeklappte Maßgruppe muss ihren neuen Platzbedarf an die Karte melden."""

from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QRect, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QWidget

from app.i18n import set_language, tr
from app.i18n.catalog import available_languages, install_language
from app.ui.panels import FIELD_PROPERTY
from app.ui.style import apply_style
from app.ui.theme import apply_theme
from tests.render_fakes import RecordingRenderer
from tests.ui_helpers import (
    measure_more_heading,
    settle_measure_layout,
    wait_for_print_findings,
    wait_until,
)
from tests.ui_helpers import session as session
from tests.ui_helpers import window as window


@pytest.fixture(autouse=True)
def language(request):
    """Auch geparkte Fußknöpfe entstehen bereits in der tatsächlichen Prüfsprache."""
    chosen = getattr(request, "param", "de")
    install_language(chosen)
    set_language(chosen)
    yield chosen
    set_language("de")


@pytest.fixture
def selected_hole(window, qt_app):
    """Der Produktweg von der Körperdatei bis zur angedockten Maßkarte."""
    apply_theme(qt_app, "dark")
    apply_style(qt_app, "dark")
    window.viewport.renderer = RecordingRenderer(size=(1920, 1080))
    window.resize(1920, 1080)
    window.show()
    window.open_path(Path(__file__).parent / "data" / "meshes" / "plate_holes.stl")
    assert window.session.wait_for_idle(60_000)
    wait_for_print_findings(window)
    result = window.session.last_result
    assert result is not None and result.complete
    object_id, body = next(iter(result.scene.objects.items()))
    hole_ids = [name for name, feature in body.features.items() if feature.kind == "hole"]
    assert len(hole_ids) >= 2
    window.object_tree.select_feature(object_id, hole_ids[0])
    assert window.session.wait_for_idle(30_000)
    wait_until(
        qt_app,
        lambda: (
            window._quiet_placement is not None
            and window._quiet_placement.active
            and window._quiet_placement._measure_box.isVisibleTo(window.viewport)
        ),
    )
    try:
        yield window, object_id, hole_ids
    finally:
        window.end_quiet_placement()
        assert window.session.wait_for_idle(30_000)
        settle_measure_layout(qt_app)


def _assert_contents_reachable(flow):
    group = flow._measure_group
    scroll = flow._measure_scroll
    viewport = scroll.viewport()
    fields = [
        widget
        for widget in group.findChildren(QWidget)
        if widget.property(FIELD_PROPERTY) and widget.isVisibleTo(group)
    ]
    assert {field.property(FIELD_PROPERTY) for field in fields} >= {
        "diameter",
        "depth",
        "entrance_mode",
        "compensate",
    }
    for field in fields:
        rect = QRect(field.mapTo(viewport, QPoint()), field.size())
        assert viewport.rect().contains(rect), (
            field.property(FIELD_PROPERTY),
            rect,
            viewport.rect(),
            scroll.verticalScrollBarPolicy(),
            scroll.verticalScrollBar().maximum(),
        )
    assert not scroll.verticalScrollBar().isVisibleTo(scroll), "vorhandener Bildraum reicht aus"
    box = flow._measure_box
    assert flow.viewport.rect().contains(QRect(box.pos(), box.size()))
    for button in (flow._measure_accept, flow._measure_cancel):
        assert box.rect().contains(QRect(button.mapTo(box, QPoint()), button.size()))


@pytest.mark.parametrize("language", available_languages(), indirect=True)
def test_fold_changes_card_height_and_settles(selected_hole, qt_app, language):
    """Alle Sprachen: echte Klappklicks wachsen und schrumpfen ohne verlorene Felder."""
    window, object_id, hole_ids = selected_hole
    # Die Wiederverwendung behält die bereits korrekt übersetzten Fußknöpfe.
    window.object_tree.select_feature(object_id, hole_ids[1])
    assert window.session.wait_for_idle(30_000)
    flow = window._quiet_placement
    assert flow is not None and flow.active
    settle_measure_layout(qt_app)
    heading = measure_more_heading(flow)
    for widget, source in (
        (heading, "Weitere Werte"),
        (flow._measure_accept, "Übernehmen"),
        (flow._measure_cancel, "Abbrechen"),
    ):
        assert widget.text() == str(tr(source))
        if language != "de":
            assert widget.text() != source, (language, source)
    assert not heading.isChecked()
    before = flow._measure_box.height()
    for _ in range(2):
        QTest.mouseClick(heading, Qt.MouseButton.LeftButton)
        settle_measure_layout(qt_app)
        assert heading.isChecked()
        _assert_contents_reachable(flow)
        assert flow._measure_box.height() > before
        settled = window.viewport.renderer.renders
        settle_measure_layout(qt_app)
        assert window.viewport.renderer.renders == settled, (
            "die Größenanpassung löst keine eigene Dauerschleife aus"
        )
        QTest.mouseClick(heading, Qt.MouseButton.LeftButton)
        settle_measure_layout(qt_app)
        assert not heading.isChecked()
        assert flow._measure_box.height() == before


@pytest.mark.parametrize("ending", ["replace", "cancel", "delete"])
def test_queued_fold_layout_survives_replacement_and_end(selected_hole, qt_app, ending):
    """Eine angeforderte Größenrunde darf weder alte Gruppen halten noch Tote aufrufen."""
    window, object_id, hole_ids = selected_hole
    flow = window._quiet_placement
    assert flow is not None and flow.active
    group = flow._measure_group
    QTest.mouseClick(measure_more_heading(flow), Qt.MouseButton.LeftButton)
    # Den Layoutauftrag vor dem Rückweg ausliefern, den verzögerten Rückruf noch nicht.
    QCoreApplication.sendPostedEvents(group, QEvent.Type.LayoutRequest)
    if ending == "replace":
        window.object_tree.select_feature(object_id, hole_ids[1])
        assert window.session.wait_for_idle(30_000)
        current = window._quiet_placement
        assert current is not None and current.active
        settle_measure_layout(qt_app)
        assert not measure_more_heading(current).isChecked()
        QTest.mouseClick(measure_more_heading(current), Qt.MouseButton.LeftButton)
        settle_measure_layout(qt_app)
        _assert_contents_reachable(current)
    elif ending == "cancel":
        QTest.mouseClick(flow._measure_cancel, Qt.MouseButton.LeftButton)
        settle_measure_layout(qt_app)
        assert not flow.active
        assert not flow._watched and not flow._measure_targets
    else:
        flow.dispose()
        flow.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        settle_measure_layout(qt_app)
