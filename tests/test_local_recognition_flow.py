"""Der Kundenweg verbindet Originaltreffer, lokale Auswahl, Vorschau und ein Undo."""

from __future__ import annotations

import copy
import importlib
import threading

import numpy as np
import pytest
from PySide6.QtWidgets import QMenu

from app.core.bootstrap import load_operations
from app.core.registry import REGISTRY
from app.ui.main_window import MainWindow
from app.ui.render.api import PointerEvent
from app.ui.session import Session
from app.ui.settings import UiSettings
from tests.helpers import blind_cylinder, bore_seed
from tests.test_local_recognition_ui import choose_action
from tests.ui_helpers import wait_until


@pytest.fixture
def local_window(qt_app, monkeypatch, tmp_path):
    load_operations()
    evaluation = importlib.import_module("app.core.scene.evaluate")
    monkeypatch.setattr(evaluation, "FEATURE_LIMIT_TRIANGLES", 1)
    monkeypatch.setattr(evaluation, "CONFIRMED_FEATURE_LIMIT_TRIANGLES", 1)
    path = tmp_path / "blind.stl"
    path.write_bytes(blind_cylinder().raw.export(file_type="stl"))
    window = MainWindow(Session(), UiSettings())
    window.open_path(path)
    assert window.session.wait_for_idle(60_000)
    assert window.session.last_result.complete
    entry = next(iter(window.session.last_result.scene.objects.values()))
    assert not entry.features
    return window


def surface_hit(window):
    entry = next(iter(window.session.last_result.scene.objects.values()))
    _seed, point, normal = bore_seed(entry.mesh)
    origin = tuple(np.asarray(point) + np.asarray(normal) * 0.5)
    direction = tuple(-np.asarray(normal))
    # Ein LOD-Treffer hat keine Originaldreieckskennung.
    return entry.id, point, -1, (origin, direction)


def start(window, app):
    flow = window.local_features()
    flow.begin(surface_hit(window))
    dialog = flow.dialog
    assert dialog is not None
    wait_until(app, dialog.save_button.isEnabled)
    return flow, dialog


def test_local_edit_has_one_transaction_and_restores_original_on_undo(local_window, qt_app):
    window, session = local_window, local_window.session
    before, document = session.last_result, copy.deepcopy(session.project.document)
    flow, dialog = start(window, qt_app)
    assert session.last_result is before
    assert session.project.document == document
    assert window.object_tree.tree.topLevelItem(0).childCount() == 0
    assert dialog.inspection.selected
    assert window.viewport.banner.legend.isHidden()
    assert not window.viewport._comparing
    choose_action(dialog, "resize_hole")
    dialog.editor._editors["diameter"].set_value(8)
    wait_until(qt_app, lambda: dialog._preview_valid)
    assert not window.viewport.banner.legend.isHidden()
    assert window.viewport._comparing
    assert session.last_result is before
    assert session.project.document == document
    dialog.editor.accept()
    assert flow.dialog is None
    assert session.wait_for_idle(30000)
    after = session.last_result
    assert after.complete
    assert [op.op for op in session.project.document.ops[-2:]] == ["detect_region", "resize_hole"]
    assert len(session.project.document.transactions) == len(document.transactions) + 1
    assert len(session.project.document.transactions[-1].ops) == 2
    bore = next(
        feature
        for feature in after.scene.objects["obj_1"].features.values()
        if feature.kind == "hole"
    )
    assert bore.params["diameter"] == pytest.approx(8, abs=1e-4)
    session.undo()
    assert session.wait_for_idle(30000)
    assert len(session.project.document.ops) == len(document.ops)
    assert session.last_result.scene.objects["obj_1"].mesh.volume == pytest.approx(
        before.scene.objects["obj_1"].mesh.volume
    )
    session.redo()
    assert session.wait_for_idle(30000)
    assert session.last_result.scene.objects["obj_1"].mesh.volume == pytest.approx(
        after.scene.objects["obj_1"].mesh.volume
    )


def test_cancel_restores_committed_view_and_selection(local_window, qt_app, monkeypatch):
    window = local_window
    window.object_tree.tree.topLevelItem(0).setSelected(True)
    before = window.session.last_result
    shown = []
    original = window.viewport.show_scene

    def show(result):
        shown.append(result)
        original(result)

    monkeypatch.setattr(window.viewport, "show_scene", show)
    flow, dialog = start(window, qt_app)
    assert shown[-1] is dialog.inspection.evaluation
    dialog.reject()
    assert not flow.active
    assert shown[-1] is before
    assert window.object_tree.selected() == "obj_1"
    assert len(window.session.project.document.ops) == 1


def test_f1_in_the_local_editor_opens_the_manual_at_its_operation(local_window, qt_app):
    """Der Bearbeitungsdialog der lokalen Suche ist ein eigenes Fenster; sein F1
    geht über die Suche an das Hauptfenster und schlägt die Operation auf
    (Konzept Handbuch §7)."""
    from PySide6.QtGui import QKeySequence, QShortcut

    from app.core import manual

    window = local_window
    _flow, dialog = start(window, qt_app)
    choose_action(dialog, "resize_hole")
    help_key = QKeySequence(QKeySequence.StandardKey.HelpContents)
    shortcut = next(
        item for item in dialog.editor.findChildren(QShortcut) if item.key() == help_key
    )
    shortcut.activated.emit()

    page, spot = manual.help_for("resize_hole")
    opened = window._manual
    assert opened is not None and opened.isVisible()
    assert opened.current_page().key == page
    # Scharf: Bekommt *Bohrung ändern* eine Anleitung, wird ``spot`` leer, und
    # die Markierung wäre ohne dieses Assert nicht mehr geprüft.
    assert spot
    assert opened.text.textCursor().selectedText() == str(REGISTRY.get("resize_hole").title)
    assert spot[1:] in opened.text.textCursor().charFormat().anchorNames()
    dialog.reject()


def test_source_snapshot_does_not_read_later_embedded_payload(local_window, qt_app, monkeypatch):
    import app.ui.local_recognition_flow as module

    captured = []
    original = module.LocalRecognitionDialog

    def make(*args, **kwargs):
        captured.append(kwargs["sources"])
        return original(*args, **kwargs)

    monkeypatch.setattr(module, "LocalRecognitionDialog", make)
    flow, _dialog = start(local_window, qt_app)
    sources = captured[0]
    project = local_window.session.project
    source_id = next(iter(project.sources))
    previous = project.sources[source_id]
    project.sources[source_id] = b"a later document payload"
    assert sources.read(source_id) == previous
    assert sources.project.document is not project.document
    local_window.session.projectChanged.emit()
    assert not flow.active
    assert len(project.document.ops) == 1


def test_palette_click_and_escape_share_the_local_flow(local_window, qt_app, monkeypatch):
    window = local_window
    window.object_tree.tree.clearSelection()
    window._update_actions()
    assert window._palette_availability("detect_region") == (True, "")
    window.launch_operation(REGISTRY.get("detect_region"))
    flow = window.local_features()
    assert flow.armed
    monkeypatch.setattr(window.viewport, "placement_hit", lambda x, y: surface_hit(window))
    assert flow.pointer(PointerEvent(kind="release", x=5, y=7, button="left"))
    assert flow.dialog is not None
    wait_until(qt_app, flow.dialog.save_button.isEnabled)
    window._escape()
    assert not flow.active
    assert len(window.session.project.document.ops) == 1


def test_bad_surface_can_be_picked_again_without_a_document_change(
    local_window, qt_app, monkeypatch
):
    """Der Fehlerknopf räumt die Erkundung ab und nimmt den nächsten Originaltreffer an."""
    from app.core.perceive.local import local_error

    window = local_window
    flow, dialog = start(window, qt_app)
    document = copy.deepcopy(window.session.project.document)
    dialog._failed(dialog._revision, local_error("seed"))
    button = next(
        button for button in dialog.state._buttons if button.text() == "Andere Stelle wählen"
    )

    button.click()

    assert flow.dialog is None
    assert flow.armed
    assert window.session.project.document == document
    monkeypatch.setattr(window.viewport, "placement_hit", lambda x, y: surface_hit(window))
    assert flow.pointer(PointerEvent(kind="release", x=5, y=7, button="left"))
    assert flow.dialog is not None and flow.dialog is not dialog
    wait_until(qt_app, flow.dialog.save_button.isEnabled)
    assert window.session.project.document == document
    flow.dialog.reject()


def test_failed_preview_stays_visible_and_cannot_be_accepted(local_window, qt_app, monkeypatch):
    flow, dialog = start(local_window, qt_app)

    def crash(*args, **kwargs):
        raise RuntimeError("injected preview failure")

    monkeypatch.setattr(local_window.session, "_preview_outcome", crash)
    choose_action(dialog, "resize_hole")
    wait_until(qt_app, lambda: "Ändern Sie die Werte" in dialog.edit_notice.text())
    assert not dialog._preview_valid
    dialog.editor.accept()
    assert flow.dialog is dialog
    assert len(local_window.session.project.document.ops) == 1
    dialog.reject()


def test_local_search_requires_a_visible_mesh_on_the_current_plate(local_window):
    window = local_window
    window.viewport.set_hidden(frozenset({"obj_1"}))
    window._update_actions()
    assert not window._palette_availability("detect_region")[0]
    window.viewport.set_hidden(frozenset())
    window.viewport.set_plate(1)
    window._update_actions()
    assert not window._palette_availability("detect_region")[0]
    window.viewport.set_plate(-1)
    window._update_actions()
    assert window._palette_availability("detect_region") == (True, "")


def test_context_action_uses_the_clicked_original_instead_of_old_selection(
    local_window, qt_app, monkeypatch
):
    window = local_window
    hit = surface_hit(window)
    clicks = []
    monkeypatch.setattr(window.viewport, "placement_hit", lambda x, y: hit)

    def choose(menu, _point):
        matches = [
            action
            for action in menu.actions()
            if action.text() == str(REGISTRY.get("detect_region").title)
        ]
        assert len(matches) == 1
        clicks.append(matches[0].text())
        matches[0].trigger()

    menu = QMenu(window)
    monkeypatch.setattr(menu, "exec", lambda point: choose(menu, point))
    monkeypatch.setattr(window.object_tree, "context_menu", lambda: menu)
    window._on_viewport_context_menu(20, 30)
    flow = window.local_features()
    assert len(clicks) == 1 and flow.dialog is not None
    wait_until(qt_app, flow.dialog.save_button.isEnabled)
    assert flow.dialog.inspection.object_id == hit[0]
    window.run_operation(REGISTRY.get("scale_object"), on_bodies=(hit[0],))
    assert not flow.active
    assert window._op_dialog is not None
    window._op_dialog.reject()
    assert len(window.session.project.document.ops) == 1


def test_old_worker_crash_cannot_override_new_preview_status(qt_app, monkeypatch):
    session = Session()
    entered, release = threading.Event(), threading.Event()
    errors, results = [], []
    count = 0

    def compute(*args, **kwargs):
        nonlocal count
        count += 1
        if count == 1:
            entered.set()
            assert release.wait(10)
            raise RuntimeError("obsolete preview")
        return None, None, ""

    monkeypatch.setattr(session, "_preview_outcome", compute)
    try:
        session.preview_async(results.append, failed=errors.append)
        wait_until(qt_app, entered.is_set)
        session.preview_async(results.append, failed=errors.append)
        wait_until(qt_app, lambda: results == [None])
        release.set()
        wait_until(qt_app, lambda: not session._previews)
        assert errors == []
    finally:
        release.set()
        session.cancel_preview()
        session.wait_for_idle(30000)


def test_a_recalculation_in_between_does_not_swallow_the_accepted_edit(local_window, qt_app):
    """Übernehmen nach einer bloßen Neuberechnung übernimmt — still verworfen wurde nichts.

    Die lokale Erkennung ist ein nicht modales Fenster. Wer währenddessen
    exportiert oder neu rechnen lässt, bekommt ein neues Ergebnis desselben
    Dokuments (``evaluate_now``, kein ``projectChanged``). Bis zum 22.09.2026
    verglich das Übernehmen das Ergebnis auf Identität und verwarf die
    Schritte dann ohne ein Wort: Der Kunde klickte *Übernehmen*, und im
    Verlauf stand nichts. Ein geändertes **Dokument** schließt das Fenster
    ohnehin (``invalidate``); was zählt, ist, dass es dasselbe blieb.
    """
    window, session = local_window, local_window.session
    document = copy.deepcopy(session.project.document)
    flow, dialog = start(window, qt_app)
    choose_action(dialog, "resize_hole")
    dialog.editor._editors["diameter"].set_value(8)
    wait_until(qt_app, lambda: dialog._preview_valid)

    session.evaluate_now()
    assert flow.dialog is dialog, "eine Neuberechnung schließt das Fenster nicht"
    dialog.editor.accept()

    assert flow.dialog is None
    assert session.wait_for_idle(30000)
    assert [op.op for op in session.project.document.ops[-2:]] == ["detect_region", "resize_hole"]
    assert len(session.project.document.transactions) == len(document.transactions) + 1


@pytest.mark.parametrize("ratio", (1.0, 1.5, 2.0))
def test_surface_picker_keys_use_device_pixels_and_keep_unrelated_keys(ratio):
    """Der Tastaturtreffer folgt demselben Pixelvertrag wie die Maus, ohne Fenster."""
    from types import SimpleNamespace

    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent

    from app.ui.viewport import Viewport

    picks, placements = [], []
    view = SimpleNamespace(
        _surface_picker=lambda x, y: picks.append((x, y)),
        _surface_picker_point=(100.0, 50.0),
        renderer=object(),
        _device_pixels=lambda value: value * ratio,
        _place_surface_picker=lambda: placements.append(True),
        _draw=lambda: None,
    )

    def press(key, modifier=Qt.KeyboardModifier.NoModifier, repeat=False):
        event = QKeyEvent(QEvent.Type.KeyPress, key, modifier, "", repeat)
        return Viewport._surface_picker_key(view, event)

    assert press(Qt.Key.Key_Right)
    assert press(Qt.Key.Key_Up, Qt.KeyboardModifier.ShiftModifier)
    assert view._surface_picker_point == pytest.approx((100 + 8 * ratio, 50 - ratio))
    assert len(placements) == 2
    assert press(Qt.Key.Key_Return)
    assert picks == [view._surface_picker_point]
    assert press(Qt.Key.Key_Return, repeat=True)
    assert len(picks) == 1
    assert not press(Qt.Key.Key_Escape)
    assert not press(Qt.Key.Key_Z, Qt.KeyboardModifier.ControlModifier)
    assert not press(Qt.Key.Key_Left, Qt.KeyboardModifier.AltModifier)
    view._surface_picker = None
    assert not press(Qt.Key.Key_Right)


@pytest.mark.parametrize("ratio", (1.0, 1.5, 2.0))
def test_surface_picker_position_is_clamped_and_drawn_in_logical_pixels(ratio):
    """Die Grafik trägt vier zweifarbige Arme; Mitte und Tastatur bleiben frei."""
    from types import SimpleNamespace

    import numpy as np

    from app.ui.viewport import RETICLE_ARM, RETICLE_GAP, RETICLE_THICKNESS, Viewport
    from tests.render_fakes import RecordingRenderer

    placed: list[tuple[int, int, int, int]] = []
    mark = SimpleNamespace(
        setGeometry=lambda *geometry: placed.append(geometry),
        show=lambda: None,
        raise_=lambda: None,
    )
    renderer = RecordingRenderer()
    renderer.size = (201, 101)
    view = SimpleNamespace(
        _surface_picker=lambda x, y: None,
        _surface_picker_point=(500.0, -10.0),
        _surface_picker_mark=mark,
        _surface_picker_items=[],
        renderer=renderer,
        _device_ratio=lambda: ratio,
    )
    Viewport._place_surface_picker(view)
    assert view._surface_picker_point == (200.0, 0.0)
    assert len(placed) == 1 and placed[0][2:] == (1, 1), "nur ein Fokuspunkt bleibt als Widget"
    assert len(renderer.items) == 2
    for inset, item in enumerate(renderer.items):
        screen = np.asarray([renderer.world_to_display(tuple(p))[:2] for p in item.points])
        screen = (screen - (200.0, 0.0)) / ratio
        assert np.all(np.max(np.abs(screen), axis=1) >= RETICLE_GAP + inset)
        assert np.max(np.abs(screen)) == pytest.approx(RETICLE_GAP + RETICLE_ARM - inset)
        assert np.ptp(screen[:6, 0]) == pytest.approx(RETICLE_THICKNESS - 2 * inset)
        style = renderer.drawn[inset][1]["style"]
        assert style.keep_in_front and not style.pickable and not style.lighting
    before = [item.points.copy() for item in renderer.items]
    view._surface_picker_point = (60.0, 40.0)
    Viewport._place_surface_picker(view)
    assert len(renderer.items) == 2, "Bewegen verwendet dieselben Grafikpuffer"
    for old, item in zip(before, renderer.items, strict=True):
        assert item.updates == 1 and not np.array_equal(item.points, old)


def test_ending_the_surface_picker_gives_the_keyboard_back_to_the_view():
    """Nach der Stellenwahl gehört die Tastatur wieder der Ansicht.

    Das Fadenkreuz hält den Fokus, solange gewählt wird. Verbirgt Qt ein
    fokussiertes Widget, gibt es den Fokus dem nächsten der Kette — das
    Kreuz entsteht spät und steht dort zuletzt, also bekam ihn das erste
    Feld des Fensters, und die Pfeiltasten flogen nach Escape oder Enter
    nicht mehr die Kamera. Gefragt wird das Fenster, nicht ``hasFocus``:
    In einem inaktiven Fenster merkt es sich das Kreuz trotzdem.
    """
    from types import SimpleNamespace

    from app.ui.viewport import Viewport

    happened: list[str] = []
    holder: dict[str, object] = {}
    mark = SimpleNamespace(
        hide=lambda: happened.append("Kreuz verborgen"),
        window=lambda: SimpleNamespace(focusWidget=lambda: holder["focus"]),
    )
    view = SimpleNamespace(
        _surface_picker=lambda x, y: None,
        _surface_picker_mark=mark,
        _surface_picker_items=(),
        _draw=lambda: None,
        setFocus=lambda _reason: happened.append("Ansicht fokussiert"),
    )
    holder["focus"] = mark

    Viewport.set_surface_picker(view, None)

    assert happened == ["Ansicht fokussiert", "Kreuz verborgen"], "erst zurück, dann verbergen"
    assert view._surface_picker is None
    happened.clear()
    holder["focus"] = object()
    Viewport.set_surface_picker(view, None)
    assert happened == ["Kreuz verborgen"], "ein Fokus anderswo bleibt, wo er ist"


def test_keyboard_surface_choice_opens_local_recognition_and_cancel_hides_the_crosshair(
    local_window, qt_app, monkeypatch
):
    """Pfeile und Eingabe erreichen dieselbe Vorschau wie ein Modellklick."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from tests.render_fakes import RecordingRenderer

    window = local_window
    viewport = window.viewport
    flow = window.local_features()
    # Der echte Renderer gehört zur visuellen Release-Abnahme; hier wird nur
    # der Anschluss der Qt-Tasten an die bestehende Originaltrefferprüfung geprüft.
    renderer = RecordingRenderer()
    renderer.size = (800, 600)
    monkeypatch.setattr(viewport, "renderer", renderer)
    monkeypatch.setattr(viewport, "_draw", lambda: None)
    hits = []
    original_hit = surface_hit(window)

    def hit(x, y):
        hits.append((x, y))
        return original_hit

    monkeypatch.setattr(viewport, "placement_hit", hit)
    chosen = []
    monkeypatch.setattr(flow, "begin", lambda found: chosen.append(found))
    flow.arm()
    assert viewport._surface_picker_mark is not None
    assert not viewport._surface_picker_mark.isHidden()
    QTest.keyClick(viewport, Qt.Key.Key_Right)
    QTest.keyClick(viewport, Qt.Key.Key_Return)
    assert hits == [(408.0, 300.0)]
    assert chosen == [original_hit]
    flow.invalidate()
    assert viewport._surface_picker_mark.isHidden()
    assert viewport._surface_picker is None
    assert all(not item.visible() for item in viewport._surface_picker_items)


def test_recognize_fully_reopens_the_question_of_its_load_step(local_window, monkeypatch):
    """*Alle Merkmale erkennen* geht an den Ladeschritt und Körper des Befunds.

    Nie an die Auswahl: Ohne Körper oder Schritt im Befund geschieht nichts,
    statt die Wahl eines anderen Körpers zurückzunehmen.
    """
    from app.core.errors import AppError

    window = local_window
    calls = []
    monkeypatch.setattr(
        window.session,
        "reopen_recognition",
        lambda object_ids: calls.append(tuple(object_ids)),
    )
    handler = window.error_handlers()["recognize_fully"]

    handler(AppError(title="Großes Modell", object_id="obj_1", op_id=1))
    handler(AppError(title="Großes Modell", op_id=1))
    handler(AppError(title="Großes Modell", values={"recognition_objects": ("a", "b")}))

    assert calls == [("obj_1",), ("a", "b")]


def test_a_local_way_to_decimate_closes_the_search_and_opens_the_operation(
    local_window, qt_app, monkeypatch
):
    """*Dreiecke verringern* am Budgetfehler: Suche zu, Operation für genau diesen Körper."""
    from app.core.perceive.local import local_error

    window = local_window
    flow, dialog = start(window, qt_app)
    body = next(iter(window.session.last_result.scene.objects))
    opened = []
    monkeypatch.setattr(window, "run_operation", lambda spec, *a, **k: opened.append(spec.name))
    document = copy.deepcopy(window.session.project.document)

    dialog._failed(dialog._revision, local_error("budget"))
    button = next(
        button for button in dialog.state._buttons if button.text() == "Dreiecke verringern"
    )
    button.click()

    assert flow.dialog is None
    assert opened == ["decimate_mesh"]
    assert tuple(window.object_tree.selected_objects()) == (body,)
    assert window.session.project.document == document


def test_the_search_reuses_what_the_session_already_computed(local_window, qt_app, monkeypatch):
    """Die Suche an einer Stelle rechnet in der Qualität der Sitzung, nicht „fein“.

    Die Sitzung rechnet im Entwurf; mit „fein“ traf die Suche keinen Schritt im
    Cache und las am Mausoleum-Drachen zuerst das ganze Modell neu ein — 40 s
    vor jeder Suche, solange keine gelang (Durchsicht 0.5.1). Gezählt wird, ob
    der Ladeschritt in der Suche noch einmal gerechnet wird.
    """
    from app.ui import local_recognition as recognition_module

    session = local_window.session
    assert session.quality == "draft", "die Sitzung rechnet im Entwurf"
    qualities: list[str] = []
    real = recognition_module.evaluate

    def watched(document, profile, **kwargs):
        qualities.append(kwargs.get("quality"))
        return real(document, profile, **kwargs)

    monkeypatch.setattr(recognition_module, "evaluate", watched)
    before = session.cache.statistics.misses
    _flow, dialog = start(local_window, qt_app)
    assert qualities and set(qualities) == {session.quality}, qualities
    # Nur der neue Suchschritt fehlt im Cache, nicht der Ladeschritt davor.
    assert session.cache.statistics.misses - before <= 1
    dialog.reject()
