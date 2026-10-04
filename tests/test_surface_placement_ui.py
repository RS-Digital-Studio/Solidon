"""Die Mausplatzierung reicht echte Werte bis in Operation, Datei und Undo."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
import trimesh
from PySide6.QtCore import QCoreApplication, QEvent, QLocale, QPointF, QSize, QThread
from PySide6.QtWidgets import QApplication, QWidget

from app.core.geom.mesh import MeshData
from app.core.knowledge.parts.ops import depth_field
from app.core.registry import REGISTRY
from app.core.scene.history import OperationDraft
from app.core.scene.project import load, save
from app.ui.labels import LengthSpin
from app.ui.op_dialog import OperationDialog
from app.ui.placement_flow import _PICK_IN_MODEL, SNAP_PIXELS, PlacementFlow
from app.ui.render.api import PointerEvent
from app.ui.session import Session
from tests.ui_helpers import PlacementItem, PlacementViewport


def test_mixed_part_preview_shows_and_removes_both_bodies(flow: Any, monkeypatch: Any) -> None:
    """Die Kabeldurchführung zeigt Schnitt und Anbau am selben gewählten Ort."""
    original, session, viewport, _original_dialog = flow
    original.dispose()
    object_id = original.inputs_of()[0]
    spec = REGISTRY.get("insert_cable_gland")
    dialog = OperationDialog(spec, {object_id: "Würfel"})
    window = SimpleNamespace(
        viewport=viewport, session=session, _clear_preview=session.cancel_preview
    )
    controller = PlacementFlow(dialog, window, lambda: spec, lambda: (object_id,))
    created = []
    removed = []

    def add_surface(*_args: Any, **kwargs: Any) -> PlacementItem:
        item = PlacementItem()
        created.append((item, kwargs))
        return item

    monkeypatch.setattr(viewport.renderer, "add_surface", add_surface)
    monkeypatch.setattr(viewport.renderer, "remove", removed.append)
    try:
        controller.start()
        assert session.wait_for_idle(30_000)
        _point(controller, session)
        assert controller._addition is not None
        assert controller._tool is not None
        assert controller._tool_context.addition is not None
        assert controller._tool.visible and controller._addition.visible
        assert np.allclose(controller._tool.matrix, controller._addition.matrix)
        assert "Hinzugefügt" in controller._tool_legend.text()
        assert "Entfernt" in controller._tool_legend.text()
        by_name = {data["name"]: data["style"] for _item, data in created}
        cut = by_name["surface_placement_tool"]
        addition = by_name["surface_placement_addition"]
        assert cut.colour != addition.colour
        assert cut.opacity < addition.opacity
        actors = (controller._tool, controller._addition)
        controller.back()
        assert all(actor in removed for actor in actors)
        assert controller._tool is None and controller._addition is None
        assert controller._tool_legend.isHidden()
    finally:
        controller.dispose()
        assert session.wait_for_idle(30_000)
        dialog.close()
        dialog.deleteLater()


@pytest.fixture
def flow(qt_app: QApplication) -> Any:
    session = Session()
    viewport = PlacementViewport()
    dialog: OperationDialog | None = None
    controller: PlacementFlow | None = None
    try:
        session.import_model(Path(__file__).parent / "data/meshes/cube_clean.stl")
        assert session.wait_for_idle(30_000)
        result = session.last_result
        assert result is not None and result.complete
        viewport.show_scene(result)
        session.sceneChanged.connect(viewport.show_scene)
        object_id, entry = next(iter(result.scene.objects.items()))
        face = int(np.argmax(entry.mesh.raw.face_normals[:, 2]))
        point = tuple(entry.mesh.raw.triangles_center[face])
        viewport.hit = object_id, point, face, None
        spec = REGISTRY.get("drill_hole")
        dialog = OperationDialog(spec, {object_id: "Würfel"})
        window = SimpleNamespace(
            viewport=viewport, session=session, _clear_preview=session.cancel_preview
        )
        controller = PlacementFlow(dialog, window, lambda: spec, lambda: (object_id,))
        dialog.accepted.connect(
            lambda: session.apply(
                spec.title,
                [OperationDraft(op=spec.name, inputs=(object_id,), params=dialog.values())],
            )
        )
        yield controller, session, viewport, dialog
    finally:
        if controller is not None:
            controller.dispose()
        session.release(30_000)
        if dialog is not None:
            dialog.close()
            dialog.deleteLater()
        viewport.close()
        viewport.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        qt_app.processEvents()


def _point(controller: PlacementFlow, session: Session, *, confirm: bool = False) -> None:
    event = (
        PointerEvent("release", 320, 240, button="left")
        if confirm
        else PointerEvent("move", 320, 240)
    )
    assert controller.pointer(event)
    controller._timer.stop()
    controller._next_surface()
    assert session.wait_for_idle(30_000)


def _place(controller: PlacementFlow, session: Session) -> None:
    """Beide Stufen: der Klick legt die Stelle fest, der zweite bestätigt.

    Seit dem 09.09.2026 setzt ein Klick nicht mehr sofort — er geht in die
    Tiefenstufe, wo die Maus die Tiefe zieht (Robert: „wenn wir klicken wollen
    wir die bohrung von der seitenansicht sehen und dann die tiefe
    runterziehen"). Wer das Ergebnis prüfen will, geht beide.
    """
    _point(controller, session, confirm=True)
    # Nach dem Klick stehen die Maße offen; erst das Übernehmen führt weiter —
    # zur Tiefe, wo es eine gibt, und von dort zum Ergebnis.
    for _ in range(2):
        if not controller.active:
            break
        controller.accept()
        assert session.wait_for_idle(30_000)


def test_reference_choice_changes_no_position_and_keeps_the_selected_edge_on_drag(flow):
    """Der vorhandene Maßeditor bindet Auswahl, Zug und Zahlen an denselben realen Rand."""
    controller, session, viewport, dialog = flow
    controller.start()
    _point(controller, session)
    before = dict(dialog.values())
    document = session.project.document
    surface = controller._surface
    edge = next(
        edge
        for edge in controller._prepared.edges
        if np.dot(edge.inward, surface.edges[0].inward) < -0.9
    )
    # Der Bezug kommt aus dem Menü des Maßes (RM-197) — hier über dessen
    # Eintrag, ohne das Menü aufzuklappen.
    data = next(
        data for _, data in controller._reference_entries(0) if data == (edge.id, edge.kind)
    )
    controller._reference_selected(0, data)
    assert controller._surface.point == surface.point
    assert dialog.values() == before
    assert session.project.document is document
    target = np.asarray(surface.point) + np.asarray(edge.inward)
    assert controller.move_to(tuple(target))
    assert controller._surface.edges[0].id == edge.id
    controller.redraw()
    assert controller._reference_boxes[0].isVisibleTo(viewport)
    assert controller._canvas.references
    assert "Außenkante" in controller._measures[0].prefix()
    # Der Name für den Bildschirmleser trägt denselben Bezug wie das Präfix
    # (Review Ansicht #12), nicht mehr das einmalige „Abstand zu Kante 1".
    assert "Außenkante" in controller._measures[0].accessibleName()


def test_reference_pick_rejects_foreign_body_and_early_enter_never_commits(flow):
    """Der Referenzklick verbraucht weder eine fremde Auswahl noch ein frühes Übernehmen."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    controller, session, viewport, dialog = flow
    controller.start()
    _point(controller, session)
    before = dict(dialog.values())
    document = session.project.document
    original = controller._surface
    controller._reference_selected(0, _PICK_IN_MODEL)
    assert controller._reference_pick == 0
    object_id, point, cell, ray = viewport.hit
    viewport.hit = "foreign_body", point, cell, ray
    controller._pick_reference(320, 240)
    QTest.keyClick(viewport, Qt.Key.Key_Return)
    assert controller.active and not controller._accept_pending
    assert controller._surface is original
    assert dialog.values() == before
    assert session.project.document is document
    viewport.hit = object_id, point, cell, ray
    # Das erste Escape nimmt nur den Bezugswahlmodus zurück, nicht den Entwurf
    # (Review Ansicht #10): Der Fluss bleibt aktiv, die Wartestellung geht.
    QTest.keyClick(viewport, Qt.Key.Key_Escape)
    assert controller.active, "der Entwurf bleibt — nur die Bezugswahl ist zurück"
    assert controller._reference_pick is None
    assert controller._surface is original, "und die Stelle bleibt"
    # Das zweite Escape geht dann wie immer zurück.
    QTest.keyClick(viewport, Qt.Key.Key_Escape)
    assert not controller.active
    assert session.project.document is document


@pytest.mark.parametrize("ratio", [1.0, 1.5, 2.0])
def test_the_reference_pick_reaches_as_far_in_logical_points_at_any_scaling(
    flow: Any, monkeypatch: Any, ratio: float
) -> None:
    """Der Klick auf einen Bezug fängt überall gleich weit — in Logikpunkten.

    :data:`SNAP_PIXELS` sind Logikpunkte, der Maßstab der Ansicht zählt
    Gerätepixel. Bis zum 22.09.2026 fehlte dazwischen das Geräteverhältnis,
    und bei 200 Prozent Skalierung fing der Bezug nur halb so weit wie der
    Tiefenfang in derselben Datei (Koordinator-Zusatz a der Durchsicht).
    Nachgestellt wird ein Bildschirm, auf dem dasselbe Bild doppelt so viele
    Gerätepixel je Millimeter hat.
    """
    import app.core.scene.placement as module

    controller, session, viewport, _dialog = flow
    controller.start()
    _point(controller, session)
    scale = viewport._pixels_per_mm_at(controller._surface.point)
    monkeypatch.setattr(viewport, "_device_ratio", lambda: ratio)
    monkeypatch.setattr(viewport, "_pixels_per_mm_at", lambda _point: scale * ratio)
    asked: list[float] = []
    monkeypatch.setattr(
        module,
        "reference_candidates",
        lambda _prepared, _point, distance, **_kwargs: asked.append(distance) or (),
    )
    controller._reference_selected(0, _PICK_IN_MODEL)
    controller._pick_reference(320, 240)
    assert asked == [pytest.approx(SNAP_PIXELS / scale)], (
        f"der Fang misst in Logikpunkten, gleich bei welchem Verhältnis ({ratio})"
    )


def test_the_reference_menu_hangs_on_the_dimension_and_changes_only_the_reference(
    flow, qt_app: QApplication
) -> None:
    """Rechtsklick auf ein Maß bietet Modellwahl und belegte Bezüge; kein Feld dahinter (RM-197).

    Das Auswahlfeld hinter jedem Maß ist am 21.09.2026 gefallen (Robert: „das
    mit bezug ändern hintendran brauche ich garnicht"). Was bleibt, ist das
    Menü des Maßes — und es ändert den Bezug, nie die Stelle.
    """
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtWidgets import QComboBox, QMenu

    controller, session, _viewport, dialog = flow
    controller.start()
    _point(controller, session)
    before = dict(dialog.values())
    document = session.project.document
    surface = controller._surface
    field = controller._measures[0]
    assert field.contextMenuPolicy() == Qt.ContextMenuPolicy.CustomContextMenu
    assert not controller._reference_boxes[0].findChildren(QComboBox)
    edge = next(
        edge
        for edge in controller._prepared.edges
        if np.dot(edge.inward, surface.edges[0].inward) < -0.9
    )
    field.customContextMenuRequested.emit(QPoint(1, 1))
    menus = [menu for menu in field.findChildren(QMenu) if menu.isVisible()]
    assert len(menus) == 1, "der Rechtsklick öffnet genau ein Menü am Maß"
    offered = [(action.text(), action.data()) for action in menus[0].actions()]
    assert any(data == _PICK_IN_MODEL for _, data in offered)
    assert {data for _, data in offered} >= {data for _, data in controller._reference_entries(0)}
    chosen = next(action for action in menus[0].actions() if action.data() == (edge.id, edge.kind))
    chosen.trigger()
    menus[0].hide()
    qt_app.processEvents()
    assert controller._surface.edges[0].id == edge.id
    assert controller._surface.point == surface.point
    assert dialog.values() == before
    assert session.project.document is document
    assert controller.active


def test_the_placement_worker_returns_in_the_qt_thread(qt_app: QApplication) -> None:
    session = Session()
    threads: list[Any] = []
    failures: list[str] = []
    try:
        session.placement_async(
            lambda: QThread.currentThread(),
            lambda worker_thread: threads.extend((worker_thread, QThread.currentThread())),
            failures.append,
        )
        assert session.wait_for_idle(30_000)
        assert not failures
        assert len(threads) == 2
        assert threads[0] != qt_app.thread()
        assert threads[1] == qt_app.thread()
    finally:
        session.release()


def test_slot_preview_temporarily_hides_the_other_placement_controls(
    flow: Any, qt_app: QApplication
) -> None:
    """Während der Langlochvorschau gibt es nur deren einen Übernehmen-Weg.

    **Gefragt wird der Zustand, nicht ein Widget** (11.09.2026): Die
    Langlochleiste ist gefallen, der Zug wartet trotzdem — mit Umriss im Bild
    und gemerktem Merkmal (`Viewport.slot_drag_waits`). Solange er wartet,
    tritt die Platzierung zurück: Zwei Wege zu demselben Loch sind einer zu
    viel, und der jüngere hat entschieden.
    """
    controller, session, viewport, _dialog = flow
    viewport.show()
    controller.start()
    _point(controller, session)
    qt_app.processEvents()
    assert not controller._bar.isHidden()
    before = len(session.project.document.ops)
    viewport.waiting_slot = True
    controller.redraw()
    qt_app.processEvents()
    assert all(widget.isHidden() for widget in controller._widgets())
    assert not controller.pointer(PointerEvent("release", 320, 240, button="left"))
    assert controller.active
    viewport.waiting_slot = False
    controller.redraw()
    qt_app.processEvents()
    assert not controller._bar.isHidden()
    assert controller.active and len(session.project.document.ops) == before


def test_the_surface_worker_gets_its_own_copy_of_the_mesh(flow: Any, monkeypatch: Any) -> None:
    """Der Platzierungsarbeiter rechnet nicht auf dem Netz, das das Fenster liest.

    **Dieselbe Zusage wie beim Szenenarbeiter** (``test_scene_worker_owns_its_
    mesh_and_evicts_the_least_recently_used_display``): Solange der Arbeiter
    rechnet, bleibt die Auswertung stehen, und der Hauptthread liest an
    demselben ``MeshData`` weiter — Hüllquader beim Zeigerhalt, Dreiecke beim
    Merkmalsfleck, Kanten beim Klick. ``prepare_surface`` füllt dabei im
    Nebenthread dieselben trägen trimesh-Caches (Flächennormalen, Dreiecke,
    Nachbarschaft), und die sind nicht threadsicher.

    Geprüft wird die **Trennung**, nicht das Ergebnis: ein anderes Objekt und
    kein geteilter Speicher. Ein Wettlauf lässt sich nicht als Zusicherung
    schreiben; die Trennung, die ihn ausschließt, schon.
    """
    import app.core.scene.placement as module

    controller, session, _viewport, _dialog = flow
    object_id = controller.inputs_of()[0]
    entry = session.last_result.scene.objects[object_id]
    seen: list[Any] = []
    actual = module.prepare_surface

    def watched(mesh: Any, *args: Any, **kwargs: Any) -> Any:
        seen.append(mesh)
        return actual(mesh, *args, **kwargs)

    monkeypatch.setattr(module, "prepare_surface", watched)
    controller.start()
    assert session.wait_for_idle(30_000)
    _point(controller, session)

    assert seen, "der Arbeiter hat die Fläche gar nicht vorbereitet"
    for mesh in seen:
        assert mesh is not entry.mesh, "der Arbeiter rechnet auf dem Netz der Szene"
        assert not np.shares_memory(mesh.raw.vertices, entry.mesh.raw.vertices)
        assert not np.shares_memory(mesh.raw.faces, entry.mesh.raw.faces)


def test_the_pointer_is_followed_while_it_moves_and_asks_about_its_face_once(
    flow: Any, qt_app: QApplication, monkeypatch: Any
) -> None:
    """Die Stelle folgt dem Zeiger im Takt, und die Fläche wird einmal vorbereitet.

    Zwei Fehler, gemessen am 22.09.2026 an der Senkplatte (311 000 Dreiecke)
    mit einem Ereignis alle 8 ms (RM-203): Jede Bewegung startete den
    16-ms-Zeitgeber neu, und die Frage kam erst, als der Zeiger ruhte — die
    Stelle stand 5,5 s nach der letzten Bewegung. Und jede Frage bereitete die
    ganze Fläche neu vor, an einer frischen Kopie ohne Merker, weil die
    Antwort der vorigen Frage überholt war und verworfen wurde. Danach: 27
    Fragen während der Bewegung, die Stelle steht 64 ms nach ihrem Ende.
    """
    import time

    import app.core.scene.placement as module

    controller, session, _viewport, _dialog = flow
    controller.start()
    assert session.wait_for_idle(30_000)
    controller._frozen = False
    controller._commit_pending = False
    controller._prepared = None
    controller._prepared_mesh = None
    controller._surface_known = None
    seen: list[Any] = []
    actual = module.prepare_surface

    def watched(mesh: Any, *args: Any, **kwargs: Any) -> Any:
        seen.append(mesh)
        return actual(mesh, *args, **kwargs)

    monkeypatch.setattr(module, "prepare_surface", watched)

    assert controller.pointer(PointerEvent("move", 320, 240))
    assert controller._timer.isActive()
    time.sleep(0.012)
    assert controller.pointer(PointerEvent("move", 321, 240))
    assert controller._timer.remainingTime() <= 8, "die nächste Bewegung schob die Frage hinaus"

    controller._timer.stop()
    controller._next_surface()
    assert controller._surface_busy, "die erste Frage läuft"
    # Eine Bewegung, während sie läuft: Ihre Antwort ist überholt, bevor sie kommt.
    assert controller.pointer(PointerEvent("move", 322, 240))
    controller._timer.stop()
    for _round in range(200):
        assert session.wait_for_idle(30_000)
        qt_app.processEvents()
        if not controller._surface_busy and controller._pending is None:
            break
    assert controller._surface is not None, "die jüngste Stelle steht"
    assert len(seen) == 1, f"die Fläche wurde {len(seen)}-mal vorbereitet"
    assert controller._surface_mesh is not None and controller._surface_mesh[1] is seen[0], (
        "jede Frage liest dieselbe Kopie mit ihren Merkern"
    )


def test_a_click_that_did_not_land_does_not_lock_the_next_one(flow: Any) -> None:
    """Ein verlorener Klick mauert den Platzierungsmodus nicht zu.

    **Der Befund** (Robert, 09.09.2026: „einmal hat es geklappt von 20 klicks").
    ``_commit_pending`` sperrt weitere Klicks, damit ein Doppelklick nicht zwei
    Bohrungen setzt — und blieb stehen, wenn der gemerkte Klick nicht zum Setzen
    führte. Danach war der Modus stumm: Jeder Klick lief in

        if self._commit_pending:
            return True

    und kam nie bei der Fläche an. Das erklärt die Quote — nicht ein Klick von
    zwanzig trifft ein Zeitfenster, sondern der erste verliert sich und alle
    weiteren sind ausgesperrt.
    """
    controller, session, _viewport, _dialog = flow
    before = len(session.project.document.transactions)
    controller.start()
    assert session.wait_for_idle(30_000)

    # Genau der Zustand nach einem Klick, der nicht zum Setzen führte: Die
    # Sperre steht, und der gemerkte Klick ist längst verfallen.
    controller._commit_pending = True
    controller._pending = None

    _place(controller, session)

    assert len(session.project.document.transactions) == before + 1, (
        "der Klick kam nicht bei der Fläche an — der Modus war zugemauert"
    )


def test_a_click_before_the_tool_is_ready_still_places_the_hole(flow: Any) -> None:
    """Wer klickt, sobald der Kreis dasteht, setzt die Bohrung — nicht erst
    danach.

    **Der Befund** (Robert, 09.09.2026: „wenn ich bei der Bohrung den Kreis hab
    und ihn setzen will, passiert nichts"). Jeder bestehende Test wartet vor
    dem Klick mit ``wait_for_idle``, bis der Werkzeugbau durch ist; ein Mensch
    tut das nicht. Der Kreis hängt am vorbereiteten Werkzeug, das Setzen hing
    zusätzlich am **gezeichneten** Körper — dazwischen liegt eine
    Ereignisrunde, und in ihr klickt man.

    Kommt der Klick zu früh, merkt ihn ``_pending`` vor, und der Timer holt ihn
    nach, sobald Fläche und Werkzeug stehen. Was den Weg zumauerte, war
    ``_commit_pending``:
    Es sperrt jeden weiteren Klick, damit ein Doppelklick nicht zwei Bohrungen
    setzt — und blieb stehen, wenn das nachgeholte ``accept`` an einer seiner
    sechs Bedingungen ausstieg. Danach war der Platzierungsmodus stumm, und
    genau das beschreibt „passiert nichts".
    """
    controller, session, _viewport, _dialog = flow
    before = len(session.project.document.transactions)
    controller.start()

    # Kein wait_for_idle: der Werkzeugbau läuft noch, wenn der Klick kommt.
    assert controller.pointer(PointerEvent("release", 320, 240, button="left"))
    controller._timer.stop()
    controller._next_surface()
    assert session.wait_for_idle(30_000)
    for _ in range(2):
        if not controller.active:
            break
        controller.accept()
        assert session.wait_for_idle(30_000)

    assert len(session.project.document.transactions) == before + 1, (
        "der Klick hat keine Bohrung gesetzt"
    )
    assert not controller.active, "und die Platzierung ist danach beendet"


def test_placing_a_hole_goes_through_three_stages(flow: Any) -> None:
    """Stelle, Maße, Tiefe — und jede Stufe endet mit einer eigenen Geste.

    Der Ablauf, den Robert am 09.09.2026 gestellt hat: „beim klick sollte man
    die maße dann einstellen die man sieht, dann in die seitenansicht erst
    nachdem man das bestätigt hat und die tiefe einstellen", und am Ende „über
    den dialog zu bestätigen".

    Bis dahin war es **eine** Geste: Der Klick nahm die Stelle und schloss ab,
    mit jeder Vorgabe, die daran hing — bei einer Bohrung also ``depth = 0``,
    was durch das ganze Teil heißt („oder ich bohr komplett durch ohne die
    tiefenbearbeitung").
    """
    controller, session, _viewport, _dialog = flow
    viewport = _viewport
    before = len(session.project.document.transactions)
    controller.start()
    assert session.wait_for_idle(30_000)

    # Stufe 1 → 2: der Klick legt die Stelle fest und schließt **nicht** ab.
    _point(controller, session, confirm=True)
    assert controller.active, "der Klick hat schon gebohrt"
    assert controller._frozen, "die Stelle steht"
    assert not controller._deepening, "die Tiefe kommt erst nach dem Übernehmen"
    assert len(session.project.document.transactions) == before

    # Stufe 2 → 3: Übernehmen führt in die Tiefe, nicht ins Ergebnis.
    controller.accept()
    assert session.wait_for_idle(30_000)
    assert controller.active and controller._deepening, "Stufe 3 ist die Tiefe"
    assert len(session.project.document.transactions) == before

    # In Stufe 3 zieht die Maus die Tiefe — und zwar bis zum Zeiger.
    name = depth_field("drill_hole", REGISTRY.get("drill_hole").params)
    assert name is not None
    assert controller.pointer(PointerEvent("move", 320, 300))
    assert not controller._depth_set
    gezogen = float(controller.dialog.values()[name])
    assert gezogen > 0.0, "die Bewegung hat die Tiefe nicht verstellt"

    # **Die Spitze liegt unter dem Zeiger.** Die Erwartung kommt aus derselben
    # Projektion, die auch das Bild macht — nicht aus einer Handrechnung, die
    # bei der ersten Änderung an der Attrappe still falsch wird.
    mouth = viewport.renderer.world_to_display(controller._surface.point)
    erwartet = (300 - mouth[1]) / PlacementViewport.SCALE
    assert gezogen == pytest.approx(erwartet, abs=0.2), (
        f"die Spitze folgt dem Zeiger nicht — {gezogen} statt {erwartet}"
    )

    # … und der Klick hält sie an, statt zu bohren.
    assert controller.pointer(PointerEvent("release", 320, 300, button="left"))
    assert controller._depth_set, "der Klick hält die Tiefe an"
    assert len(session.project.document.transactions) == before

    # Danach gehört die Maus wieder ganz der Ansicht — auch der Linksklick,
    # der im ``solidon``-Schema die Kamera schiebt.
    assert not controller.pointer(PointerEvent("press", 320, 300, button="left"))
    assert not controller.pointer(PointerEvent("move", 400, 300, buttons=frozenset({"left"})))

    # Und erst der Knopf bohrt.
    # **Gewartet, weil der Knopf so lange gesperrt ist.** Der Klick auf die
    # Tiefe schreibt einen neuen Wert, und der stößt die Werkzeugvorschau neu
    # an; bis sie steht, ist ``_tool_context`` leer und ``_accept`` grau. Wer
    # hier ohne das Warten ``accept()`` ruft, ruft an der Oberfläche vorbei
    # eine Methode, die der Kunde gar nicht auslösen könnte — und bekommt
    # einen roten Test für ein Verhalten, das richtig ist.
    assert session.wait_for_idle(30_000)
    assert controller._accept.isEnabled(), "der Knopf muss den letzten Schritt anbieten"
    controller.accept()
    assert session.wait_for_idle(30_000)
    assert not controller.active
    assert len(session.project.document.transactions) == before + 1


def _escape(controller: PlacementFlow, viewport: Any) -> None:
    """Escape so, wie der Kunde es drückt: als Taste an der Ansicht."""
    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent

    QApplication.sendEvent(
        viewport,
        QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier),
    )


def test_escape_goes_back_exactly_one_stage_and_the_model_leads_back_in(
    flow: Any, qt_app: QApplication
) -> None:
    """Escape geht je Stufe genau eine zurück, und aus dem Dialog führt ein Klick zurück.

    RM-205, gefunden im Review vom 21.09.2026: Escape in der Tiefe übersprang
    die Maße und landete im Dialog, und aus dem Dialog führte kein Weg zurück
    — ``surfaceRequested`` hatte keinen Sender mehr, seit der Knopf gefallen
    war. Jetzt: Tiefe → Maße → Zielen → Dialog, die Werte bleiben, und ein
    Klick auf das Modell setzt dort die Stelle, über ``surfaceRequested``.
    """
    controller, session, viewport, dialog = flow
    controller.start()
    assert session.wait_for_idle(30_000)
    _point(controller, session, confirm=True)
    controller.accept()
    assert session.wait_for_idle(30_000)
    assert controller.active and controller._deepening, "Stufe 3"
    name = depth_field("drill_hole", REGISTRY.get("drill_hole").params)
    assert name is not None
    assert controller.pointer(PointerEvent("move", 320, 300))
    depth = float(dialog.values()[name])
    assert depth > 0.0

    _escape(controller, viewport)
    assert controller.active and not controller._deepening, "aus der Tiefe zurück in die Maße"
    assert controller._frozen and controller._surface is not None, "die Stelle steht noch"
    assert float(dialog.values()[name]) == pytest.approx(depth), "die gezogene Tiefe bleibt"
    assert viewport.display == "solid", "die geliehene Ansicht ist zurückgegeben"

    _escape(controller, viewport)
    assert controller.active and not controller._frozen, "aus den Maßen zurück ins Zielen"
    assert float(dialog.values()[name]) == pytest.approx(depth), "die Werte bleiben"

    _escape(controller, viewport)
    assert not controller.active, "aus dem Zielen in den Dialog"
    assert dialog.isVisible()
    assert viewport.resume is not None, "der Rückweg steht offen"
    assert dialog._placement_hint.isVisibleTo(dialog), "und der Dialog sagt ihn an"

    asked: list[int] = []
    dialog.surfaceRequested.connect(lambda: asked.append(1))
    assert not viewport.resume(PointerEvent("move", 330, 250)), "eine Bewegung gehört der Ansicht"
    assert viewport.resume(PointerEvent("press", 330, 250, button="left"))
    assert viewport.resume(PointerEvent("release", 331, 250, button="left"))
    assert asked == [1], "der Rückweg geht über surfaceRequested"
    assert controller.active and viewport.resume is None
    controller._timer.stop()
    controller._next_surface()
    for _round in range(200):
        assert session.wait_for_idle(30_000)
        qt_app.processEvents()
        if controller._frozen and not controller._surface_busy:
            break
    assert controller._frozen, "derselbe Klick setzt die Stelle — Stufe 2"
    assert float(dialog.values()[name]) == pytest.approx(depth), "und die Tiefe von vorhin bleibt"


def test_the_way_back_ignores_a_drag_and_a_click_beside_the_body(flow: Any) -> None:
    """Der Rückweg nimmt nur den Klick auf den Körper; Zug und Daneben gehören der Kamera."""
    controller, session, viewport, dialog = flow
    controller.start()
    assert session.wait_for_idle(30_000)
    controller.back()
    assert viewport.resume is not None
    asked: list[int] = []
    dialog.surfaceRequested.connect(lambda: asked.append(1))

    assert viewport.resume(PointerEvent("press", 330, 250, button="left"))
    assert viewport.resume(PointerEvent("release", 430, 250, button="left")), (
        "ein Zug verbraucht sein Loslassen, setzt aber nichts"
    )
    assert asked == [] and not controller.active

    hit, viewport.hit = viewport.hit, None
    assert not viewport.resume(PointerEvent("press", 10, 10, button="left")), (
        "neben dem Körper bleibt der Druck der Kamera"
    )
    viewport.hit = hit
    dialog.reject()
    assert viewport.resume is None, "mit dem Dialog geht der Rückweg"


def test_the_depth_stage_never_starts_at_the_value_that_means_through(flow: Any) -> None:
    """Null heißt „durch das ganze Teil" — dort darf die Stufe nicht beginnen.

    Das Schema von ``drill_hole`` gibt ``depth`` mit 0 vor und schreibt dazu
    „Null bohrt durch das ganze Teil". Wer die Tiefenstufe betrat und ohne zu
    ziehen übernahm, bohrte damit weiterhin durch — genau das, was diese Stufe
    abschaffen sollte (Robert, 09.09.2026: „die bohrung ist aber sofort
    komplett durch"). Und wer den Zeiger nach *oben* zieht, um flacher zu
    werden, landete am Ende des Wegs bei derselben Null.
    """
    controller, session, _viewport, _dialog = flow
    controller.start()
    assert session.wait_for_idle(30_000)
    _point(controller, session, confirm=True)
    controller.accept()
    assert session.wait_for_idle(30_000)
    assert controller._deepening

    name = depth_field("drill_hole", REGISTRY.get("drill_hole").params)
    assert name is not None
    anfang = float(controller.dialog.values()[name])
    assert anfang > 0.0, "die Stufe beginnt mit einer Tiefe, nicht mit dem Durchbohren"

    # Weit über die Mündung hinaus nach oben gezogen: auch dort bleibt eine
    # Tiefe stehen, die eine ist.
    assert controller.pointer(PointerEvent("move", 320, 0))
    hochgezogen = float(controller.dialog.values()[name])
    assert hochgezogen > 0.0, f"der Zug fiel auf {hochgezogen} — das bohrt durch"


def test_a_typed_depth_is_not_overwritten_by_the_next_mouse_move(flow: Any) -> None:
    """Wer die Zahl tippt, hat entschieden — der Zeiger sagt danach nichts mehr.

    Der Zug misst absolut von der Mündung; ohne Sperre überschriebe ihn die
    nächste Bewegung über der Renderfläche vollständig. Der Weg zum Knopf führt
    genau darüber (Robert, 09.09.2026: „wenn ich die tiefe setz, komm ich nicht
    in das bearbeitenfeld von der maßeinheit").
    """
    controller, session, _viewport, _dialog = flow
    controller.start()
    assert session.wait_for_idle(30_000)
    _point(controller, session, confirm=True)
    controller.accept()
    assert session.wait_for_idle(30_000)

    name = depth_field("drill_hole", REGISTRY.get("drill_hole").params)
    assert name is not None
    controller._depth_typed(4.25)
    assert float(controller.dialog.values()[name]) == pytest.approx(4.25)

    # Die Maus wandert weiter — über die Renderfläche zum Knopf.
    assert not controller.pointer(PointerEvent("move", 400, 380))
    assert float(controller.dialog.values()[name]) == pytest.approx(4.25), (
        "die getippte Tiefe hat die nächste Mausbewegung nicht überlebt"
    )


def test_the_depth_follows_the_pointer_after_a_zoom(flow: Any) -> None:
    """Zoomen bleibt in der Tiefenstufe frei — der Maßstab muss mitgehen.

    Die Ansicht rechnet perspektivisch, der Maßstab hängt also am Abstand der
    Kamera. Einmal beim Betreten gemessen und dann eingefroren, wäre die Tiefe
    nach einem Zoom um den Faktor k um k daneben, und die Spitze läge nicht
    mehr unter dem Zeiger (Robert, 09.09.2026: „bei weiter zur tiefe passt wohl
    die mausposition zur darstellung noch nicht ganz").
    """
    controller, session, viewport, _dialog = flow
    controller.start()
    assert session.wait_for_idle(30_000)
    _point(controller, session, confirm=True)
    controller.accept()
    assert session.wait_for_idle(30_000)

    name = depth_field("drill_hole", REGISTRY.get("drill_hole").params)
    assert name is not None

    def gezogen_bei(y: int) -> float:
        assert controller.pointer(PointerEvent("move", 320, y))
        return float(controller.dialog.values()[name])

    def erwartet_bei(y: int) -> float:
        mouth = viewport.renderer.world_to_display(controller._surface.point)
        return (y - float(mouth[1])) / (PlacementViewport.SCALE * viewport.zoom())

    nah = gezogen_bei(300)
    assert nah == pytest.approx(erwartet_bei(300), abs=0.2)

    # Die Kamera fährt auf den halben Abstand — alles wird doppelt so groß.
    position, focus, up, scale = viewport.camera_pose()
    mitte = tuple(float(focus[i]) + (float(position[i]) - float(focus[i])) / 2.0 for i in range(3))
    viewport.set_camera_pose(mitte, focus, up, scale)
    assert viewport.zoom() == pytest.approx(2.0)

    fern = gezogen_bei(300)
    assert fern == pytest.approx(erwartet_bei(300), abs=0.2), (
        f"nach dem Zoom zieht die Tiefe {fern} statt {erwartet_bei(300)}"
    )
    assert fern != pytest.approx(nah, abs=0.2), "der Zoom hat den Maßstab nicht verändert"


def test_the_wall_below_is_measured_through_the_hollow(flow: Any) -> None:
    """Bei einem hohlen Teil zählt die Wand, nicht die Ausdehnung des Körpers.

    Hohl ist im Druck der Normalfall. Am Hüllquader gemessen stand in der
    zwei Millimeter starken Decke einer Box „Wand: 18,0 mm" im Bild, die
    Mitte-Marke lag im Hohlraum, und das Einrasten hielt an beiden falschen
    Werten. Gemessen wird deshalb mit einem Strahl bis zum ersten Austritt —
    dieselbe Rechnung, mit der die Stifte ihre Materialtiefe suchen.
    """
    controller, _session, _viewport, _dialog = flow

    # Eine Box mit Hohlraum: außen 20 mm, innen 16 mm, also 2 mm Decke.
    aussen = trimesh.creation.box((20.0, 20.0, 20.0))
    innen = trimesh.creation.box((16.0, 16.0, 16.0))
    innen.invert()
    hohl = MeshData.of(trimesh.util.concatenate([aussen, innen]))

    controller._object_id = "obj_1"
    controller._result = SimpleNamespace(
        scene=SimpleNamespace(objects={"obj_1": SimpleNamespace(mesh=hohl)})
    )
    controller._surface = SimpleNamespace(
        point=(0.0, 0.0, 10.0), frame=SimpleNamespace(normal=(0.0, 0.0, 1.0))
    )

    unten = controller._material_below()
    assert unten == pytest.approx(2.0, abs=1e-6), (
        f"gemessen wurde {unten} — das ist der Hüllquader und nicht die Wand"
    )

    # Und die Marken hängen daran: die Rückseite der Wand und ihre Mitte.
    assert controller._depth_marks() == pytest.approx((1.0, 2.0))


def test_dragging_the_camera_does_not_settle_the_depth(flow: Any) -> None:
    """Wer in der Tiefenstufe die Ansicht schiebt, hat die Tiefe nicht gemeint.

    Im ``solidon``-Schema schiebt die linke Taste die Kamera, und die Stufe
    lässt sie ausdrücklich durch. Zählte jedes Loslassen als Bestätigung, stand
    die Tiefe nach einem Schiebeversuch still fest — die Geste tat nichts und
    beendete nebenbei das Einstellen. Unterschieden wird an der Zugschwelle des
    Systems, wie überall in der Ansicht.
    """
    controller, session, _viewport, _dialog = flow
    controller.start()
    assert session.wait_for_idle(30_000)
    _point(controller, session, confirm=True)
    controller.accept()
    assert session.wait_for_idle(30_000)
    assert controller._deepening

    # Ein Zug über die halbe Ansicht: Druck, Bewegung, Loslassen weit entfernt.
    assert controller.pointer(PointerEvent("press", 320, 300, button="left"))
    assert not controller.pointer(PointerEvent("move", 500, 300, buttons=frozenset({"left"})))
    assert not controller.pointer(PointerEvent("release", 500, 300, button="left"))
    assert not controller._depth_set, "ein Schiebeversuch hat die Tiefe festgesetzt"

    # Ein echter Klick an derselben Stelle hält sie dagegen an.
    assert controller.pointer(PointerEvent("press", 320, 300, button="left"))
    assert controller.pointer(PointerEvent("release", 320, 301, button="left"))
    assert controller._depth_set, "der Klick hält die Tiefe an"


def test_the_depth_stage_gives_back_the_view_it_borrowed(flow: Any) -> None:
    """Darstellungsart und Kamera gehören dem Kunden, nicht der Stufe.

    Die Tiefenstufe macht das Modell durchscheinend und schwenkt quer zur
    Bohrachse, damit man in das Loch sieht. Beides ist geliehen (`ansicht.md`,
    „Was die Ansicht sich merkt"): Wer die Stufe über Escape verlässt, findet
    seine Ansicht vor, wie er sie hatte — sonst bleibt das Modell für immer
    durchscheinend und die Kamera in einem Schwenk, den niemand gewählt hat.
    """
    controller, session, viewport, _dialog = flow
    viewport.set_display_mode("solid")
    controller.start()
    assert session.wait_for_idle(30_000)
    vorher = viewport.camera_pose()

    _point(controller, session, confirm=True)
    controller.accept()
    assert session.wait_for_idle(30_000)
    assert controller._deepening

    assert viewport.display_mode == "transparent", "in das Loch sieht man nur durchscheinend"
    assert viewport.camera_pose() != vorher, "die Stufe schwenkt quer zur Achse"

    controller._leave_depth()
    assert viewport.display_mode == "solid", "die Darstellungsart kam nicht zurück"
    assert viewport.camera_pose() == vorher, "die Kamera blieb im Seitenschwenk stehen"


def test_click_places_one_real_hole_and_undo_removes_it(flow: Any, tmp_path: Path) -> None:
    controller, session, _viewport, dialog = flow
    before = len(session.project.document.transactions)
    controller.start()
    assert session.wait_for_idle(30_000)
    _place(controller, session)
    assert not controller.active
    assert len(session.project.document.transactions) == before + 1
    assert session.last_result.complete
    operation = session.project.document.ops[-1]
    assert operation.op == "drill_hole"
    assert operation.params["nz"] == pytest.approx(1.0)
    assert operation.params["x"] == pytest.approx(dialog.values()["x"])
    path = tmp_path / "placed.p3d"
    save(session.project, path)
    assert load(path).document.ops[-1].params == operation.params
    session.undo()
    assert session.wait_for_idle(30_000)
    assert len(session.project.document.transactions) == before


def test_return_to_values_preserves_position_without_an_operation(flow: Any) -> None:
    controller, session, _viewport, dialog = flow
    before = len(session.project.document.ops)
    controller.start()
    _point(controller, session)
    values = dialog.values()
    controller.back()
    assert not controller.active
    assert dialog.isVisible()
    assert dialog.values() == values
    assert len(session.project.document.ops) == before


def test_escape_forgets_the_target_body(flow: Any) -> None:
    """Nach Escape bohrt der Dialog wieder, was der Nutzer gewählt hat — nicht den
    einen Körper, den die Platzierung getroffen hatte (Review 06.09.2026)."""
    controller, session, _viewport, _dialog = flow
    controller.start()
    assert session.wait_for_idle(30_000)
    _point(controller, session)
    assert controller.target, "der Treffer hat ein Ziel"
    controller.back()
    assert controller.target == "", "Escape gibt das Ziel frei; nur Übernehmen behält es"


def test_escape_leads_back_to_the_dialog_and_the_dialog_back_into_the_view(
    flow: Any,
) -> None:
    """Escape bringt den Dialog, und aus dem Dialog führt ein Knopf zurück in
    die erste Stufe (RM-205).

    ``surfaceRequested`` hatte keinen Sender mehr, seit *Im Modell platzieren*
    fiel: Wer nach dem Nachbessern neu zielen wollte, schloss den Dialog und
    begann von vorn. Der Knopf steht erst da, wenn schon gezielt wurde, und
    die Werte des Dialogs bleiben.
    """
    controller, session, _viewport, dialog = flow
    dialog.show()
    assert not dialog.aim_again.isVisibleTo(dialog), "vor dem ersten Zielen kein Rückweg"
    controller.start()
    assert controller.active
    assert not dialog.aim_again.isVisibleTo(dialog)
    _point(controller, session)
    values = dialog.values()
    controller.back()
    assert not controller.active
    assert dialog.aim_again.isVisibleTo(dialog), "aus dem Dialog führt kein Weg zurück ins Bild"
    assert dialog._placement_hint.isVisibleTo(dialog), "auch der Modellklick bleibt angekündigt"
    assert dialog.aim_again.toolTip()

    dialog.aim_again.click()
    assert controller.active, "der Knopf beginnt die Platzierung wieder in Stufe 1"
    assert not controller._deepening
    assert not dialog.aim_again.isVisibleTo(dialog)
    assert dialog._placement_hint.isVisibleTo(dialog), "beim erneuten Zielen bleibt der Hinweis"
    assert dialog.values() == values

    controller.dispose()
    assert not controller.active
    assert dialog.aim_again.isHidden(), "nach dem Ende gibt es keinen verwaisten Rückweg"
    assert dialog._placement_hint.isHidden()
    assert _viewport.resume is None


def test_invalid_surface_cannot_reuse_the_previous_position(flow: Any) -> None:
    controller, session, viewport, _dialog = flow
    before = len(session.project.document.ops)
    controller.start()
    _point(controller, session)
    assert controller._surface is not None
    viewport.hit = None
    _point(controller, session, confirm=True)
    assert controller._surface is None
    assert not controller._accept.isEnabled()
    assert len(session.project.document.ops) == before


def test_editing_an_edge_distance_keeps_it_exact_until_accept(flow: Any) -> None:
    controller, session, _viewport, dialog = flow
    controller.start()
    _point(controller, session)
    assert len(controller._surface.edges) == 2
    before = len(session.project.document.ops)
    controller._measures[0].set_value_mm(2.3456789)
    controller._distance_changed(2.3456789)
    assert controller._distance_valid
    assert controller._surface.edges[0].distance == pytest.approx(2.3456789)
    assert len(session.project.document.ops) == before
    assert controller._frozen
    assert {name: dialog.values()[name] for name in ("x", "y", "z")} == dict(
        zip(("x", "y", "z"), controller._surface.point, strict=True)
    )


def test_surface_position_replaces_an_old_coordinate_expression(flow: Any) -> None:
    controller, session, _viewport, dialog = flow
    field = dialog._editors["x"]
    field.set_value("=5 + 2")
    assert isinstance(dialog.values()["x"], str)
    controller.start()
    _point(controller, session)
    assert not field.toggle.isChecked()
    assert dialog.values()["x"] == pytest.approx(controller._surface.point[0])


def test_undo_cannot_restart_placement_on_the_previous_result(flow: Any) -> None:
    controller, session, _viewport, _dialog = flow
    controller.start()
    _point(controller, session)
    old = session.last_result
    session.undo()
    assert not controller.active
    assert session.last_result is old
    assert not session.result_current
    controller.start()
    assert not controller.active
    assert not controller.can_place()
    assert session.wait_for_idle(30_000)
    assert not controller.can_place()


def test_edit_uses_the_input_before_later_transforms(flow: Any) -> None:
    controller, session, viewport, _dialog = flow
    object_id = controller.inputs_of()[0]
    assert session.apply(
        "Bohrung", [OperationDraft(op="drill_hole", inputs=(object_id,), params={})]
    )
    assert session.wait_for_idle(30_000)
    drill = session.project.document.ops[-1]
    assert session.apply(
        "Verschieben",
        [OperationDraft(op="translate_object", inputs=(object_id,), params={"dx": 50.0})],
    )
    assert session.wait_for_idle(30_000)
    final = session.last_result
    controller._change_op = drill.id
    controller.start()
    assert session.wait_for_idle(30_000)
    assert controller._result is not final
    original = controller._result.scene.objects[object_id].mesh.raw
    moved = final.scene.objects[object_id].mesh.raw
    assert float(moved.bounds[0, 0] - original.bounds[0, 0]) == pytest.approx(50.0)
    assert viewport.result is controller._result
    _point(controller, session)
    assert controller._surface.point[0] < 20.0
    controller.back()
    assert viewport.result is final


def test_historical_placement_switches_between_input_and_complete_preview(
    flow: Any, monkeypatch: Any
) -> None:
    """Spätere Körper bleiben im Ergebnis; neue Treffer warten auf den Originaleingang."""
    controller, session, viewport, dialog = flow
    object_id = controller.inputs_of()[0]
    assert session.apply(
        "Bohrung", [OperationDraft(op="drill_hole", inputs=(object_id,), params={})]
    )
    assert session.wait_for_idle(30_000)
    drill = session.project.document.ops[-1]
    assert session.apply("Späterer Körper", [OperationDraft(op="create_brep_box", params={})])
    assert session.wait_for_idle(30_000)
    final = session.last_result
    controller._change_op = drill.id
    controller.start()
    assert session.wait_for_idle(30_000)
    prefix = controller._result
    assert set(prefix.scene.objects) == {object_id}
    assert len(final.scene.objects) == 2
    _point(controller, session)
    assert controller._surface is not None
    steps = len(session.project.document.ops)
    shown = []
    apply_scene = viewport.show_scene
    monkeypatch.setattr(viewport, "show_scene", shown.append)

    assert not controller.show_preview_base()
    assert shown == [final]
    assert controller._result is prefix
    controller.redraw()
    assert not controller._accept.isEnabled()
    controller.accept()
    assert controller.active
    assert len(session.project.document.ops) == steps
    assert not controller.show_preview_base()
    assert shown == [final], "do not restart pending scene preparation"

    apply_scene(final)
    assert controller.show_preview_base()
    assert viewport.result is final
    assert set(viewport.result.scene.objects) == set(final.scene.objects)
    assert controller._result is prefix
    controller.redraw()
    assert controller._accept.isEnabled()
    checked = []
    monkeypatch.setattr(dialog, "can_accept", lambda: checked.append(True) or False)
    monkeypatch.setattr(controller, "deepens", lambda: False)
    controller.accept()
    assert checked == [True], "the complete scene must reach the current preview guard"
    assert controller.active

    hits = []
    hit = viewport.placement_hit
    monkeypatch.setattr(
        viewport, "placement_hit", lambda x, y: hits.append(viewport.result) or hit(x, y)
    )
    controller._pending = (320, 240, False)
    controller._next_surface()
    assert shown == [final, prefix]
    assert not hits
    assert controller._pending is not None
    controller._next_surface()
    assert shown == [final, prefix]
    assert not hits
    apply_scene(prefix)
    assert session.wait_for_idle(30_000)
    assert hits == [prefix], "never use final-scene cell indices for the historical input"
    assert controller._surface is not None
    assert controller._result is prefix
    assert len(session.project.document.ops) == steps

    monkeypatch.setattr(viewport, "show_scene", apply_scene)
    controller.back()
    assert viewport.result is final
    assert not controller.active


def test_an_invalid_historical_step_can_be_placed_again(flow: Any) -> None:
    """Die fertige Auswertung darf fehlerhaft sein, ihr gesunder Eingang bleibt bearbeitbar."""
    controller, session, viewport, _dialog = flow
    object_id = controller.inputs_of()[0]
    assert session.apply(
        "Bohrung",
        [
            OperationDraft(
                op="drill_hole",
                inputs=(object_id,),
                params={"diameter": 4.0, "widening_diameter": 1.0},
            )
        ],
    )
    assert session.wait_for_idle(30_000)
    assert not session.last_result.complete
    controller._change_op = session.project.document.ops[-1].id
    controller.start()
    assert session.wait_for_idle(30_000)
    assert controller.active and controller.can_place()
    assert controller._result.complete
    assert viewport.result is controller._result
    _point(controller, session)
    assert controller._surface is not None
    assert controller._accept.isEnabled()


def test_only_what_needs_a_face_goes_into_placement_by_itself() -> None:
    """Ein Erzeuger braucht keine Fläche — und darf seinen Dialog behalten.

    Seit dem 09.09.2026 geht ein platzierbarer Dialog von selbst in die
    Platzierung, statt einen zweiten Klick zu verlangen (Robert: „man soll
    keinen extra Button klicken müssen"). Für alles, was auf etwas sitzt —
    Baustein, Beschriftung, Bohrung —, ist das richtig.

    **Für die Grundkörper nicht.** ``start`` versteckt den Dialog, und
    Breite, Tiefe und Höhe stehen nirgends sonst: Wer die Maße ändern wollte,
    musste Escape drücken, tippen und neu platzieren (Robert, 09.09.2026:
    „wer nur Maße tippen will, ignoriert ihn"). Dort zeigt stattdessen die
    Live-Vorschau den Körper, sobald der Dialog offen ist — sie rechnet ihn
    ohnehin und wird nur übersprungen, solange die Platzierung läuft.

    Gefragt wird nach ``consumes`` und nicht nach einer Namensliste: Eine
    Liste in der Oberfläche schweigt beim nächsten Erzeuger.
    """
    from app.core.bootstrap import load_operations
    from app.core.scene import placement
    from app.ui.placement_flow import starts_by_itself

    load_operations()

    ohne_eingang = [
        spec
        for spec in REGISTRY.all()
        if spec.consumes == 0
        and not spec.takes_whole_scene
        and placement.supports_surface_placement(spec)
    ]
    assert ohne_eingang, "ohne platzierbare Erzeuger prüft der Test nichts"
    for spec in ohne_eingang:
        assert not starts_by_itself(spec), f"{spec.name} behält seinen Dialog"

    mit_eingang = [
        spec
        for spec in REGISTRY.all()
        if spec.consumes != 0 and placement.supports_surface_placement(spec)
    ]
    assert mit_eingang, "und ohne die andere Hälfte auch nicht"
    for spec in mit_eingang:
        assert starts_by_itself(spec), f"{spec.name} sitzt auf einer Fläche und geht gleich hin"


def test_feature_hover_reuses_the_body_prepared_outside_qt(
    flow: Any,
    qt_app: QApplication,
    monkeypatch: Any,
) -> None:
    """Mausbewegungen und Maße dürfen den Merkmalskörper nicht erneut im Qt-Thread berechnen."""
    import app.core.geom.prepare_ops as module
    from app.ui import placement_flow

    # Der Weg über den Arbeiter: Am kleinen Körper entsteht die Fläche beim
    # Start seit ``f01f8b622`` einmal gleich im Hauptfaden (``AT_ONCE_BELOW``);
    # hier geht es darum, dass danach nichts sie noch einmal rechnet.
    monkeypatch.setattr(placement_flow, "AT_ONCE_BELOW", 0)
    original, session, viewport, _dialog = flow
    original.dispose()
    object_id = original.inputs_of()[0]
    assert session.apply(
        "Bohrung", [OperationDraft(op="drill_hole", inputs=(object_id,), params={})]
    )
    assert session.wait_for_idle(30_000)
    entry = session.last_result.scene.objects[object_id]
    feature = next(value for value in entry.features.values() if value.kind == "hole")
    face = int(np.argmax(entry.mesh.raw.face_normals[:, 2]))
    viewport.hit = object_id, tuple(entry.mesh.raw.triangles_center[face]), face, None
    spec = REGISTRY.get("move_feature")
    dialog = OperationDialog(spec, {object_id: "Würfel"}, features={feature.id: "Bohrung"})
    dialog.take_placement({"at_feature": feature.id})
    window = SimpleNamespace(
        viewport=viewport, session=session, _clear_preview=session.cancel_preview
    )
    controller = PlacementFlow(dialog, window, lambda: spec, lambda: (object_id,))
    threads = []
    actual = module.feature_placement_geometry

    def measured(*args: Any, **kwargs: Any) -> Any:
        thread = QThread.currentThread()
        assert thread != qt_app.thread(), "feature geometry reached the Qt thread"
        threads.append(thread)
        return actual(*args, **kwargs)

    monkeypatch.setattr(module, "feature_placement_geometry", measured)
    try:
        controller.start()
        assert session.wait_for_idle(30_000)
        for _ in range(3):
            # Am Merkmal nimmt der Fluss die freie Bewegung nicht (seit dem
            # 21.09.2026 gehört sie dem Hover der Ansicht) — und rechnet
            # darauf erst recht nichts.
            assert not controller.pointer(PointerEvent("move", 320, 240))
            assert session.wait_for_idle(30_000)
            assert controller._surface is not None
            assert controller._tool_context is not None
            assert controller._set_values()
        assert len(threads) == 1
    finally:
        controller.dispose()
        assert session.wait_for_idle(30_000)
        dialog.close()


def test_late_tool_from_a_closed_run_is_discarded(flow: Any, monkeypatch: Any) -> None:
    controller, session, _viewport, _dialog = flow
    from app.ui import placement_flow

    # Der Weg über den Arbeiter: Am kleinen Körper entstünde das Werkzeug beim
    # Start gleich im Hauptfaden (``AT_ONCE_BELOW``), und nichts käme zu spät.
    monkeypatch.setattr(placement_flow, "AT_ONCE_BELOW", 0)
    requests = []
    monkeypatch.setattr(
        session,
        "placement_async",
        lambda compute, then, failed, refused=None: requests.append((compute, then)),
    )
    controller.start()
    compute, then = requests.pop()
    controller.back()
    controller.start()
    then(compute())
    assert controller._tool is None
    assert len(requests) == 1
    current_compute, current_then = requests.pop()
    current_then(current_compute())
    assert controller._tool is not None


def test_centre_dimensions_keep_the_selected_hole_reference(flow: Any) -> None:
    controller, session, viewport, dialog = flow
    session.start_new()
    assert session.wait_for_idle(30_000)
    session.import_model(Path(__file__).parent / "data/meshes/plate_holes.stl")
    assert session.wait_for_idle(30_000)
    object_id, entry = next(iter(session.last_result.scene.objects.items()))
    face = int(np.argmax(entry.mesh.raw.face_normals[:, 2]))
    point = tuple(entry.mesh.raw.triangles_center[face])
    viewport.hit = object_id, point, face, None
    controller.start()
    _point(controller, session)
    assert controller._centre_id
    old_id = controller._centre_id
    current = next(c for c in controller._surface.centres if c.feature_id == old_id)
    changed = current.offset[0] + 0.123456789
    controller._centre_measures[0].set_value_mm(changed)
    controller._centre_changed(changed)
    assert controller._distance_valid
    assert controller._centre_id == old_id
    updated = next(c for c in controller._surface.centres if c.feature_id == old_id)
    assert updated.offset[0] == pytest.approx(changed)
    assert controller._frozen
    assert dialog.values()["x"] == pytest.approx(controller._surface.point[0])


def _keyboard_placement(flow: Any, qt_app: QApplication) -> Any:
    """Echte Qt-Felder an der Lochplatte öffnen; nur die Raumprojektion ist kontrolliert."""
    controller, session, viewport, dialog = flow
    session.start_new()
    assert session.wait_for_idle(10_000)
    session.import_model(Path(__file__).parent / "data/meshes/plate_holes.stl")
    assert session.wait_for_idle(10_000)
    object_id, entry = next(iter(session.last_result.scene.objects.items()))
    face = int(np.argmax(entry.mesh.raw.face_normals[:, 2]))
    viewport.hit = object_id, tuple(entry.mesh.raw.triangles_center[face]), face, None
    viewport.show()
    dialog.show()
    qt_app.processEvents()
    dialog.surfaceRequested.emit()
    _point(controller, session)
    viewport.activateWindow()
    qt_app.processEvents()
    assert controller.active and controller._accept.isEnabled()
    assert controller._centre_id
    fields = (*controller._measures, *controller._centre_measures)
    assert all(field.isVisible() for field in fields)
    return fields


@pytest.mark.parametrize("position", range(4), ids=("edge-1", "edge-2", "centre-1", "centre-2"))
def test_escape_from_each_inner_dimension_editor_returns_to_values(
    flow: Any, qt_app: QApplication, position: int
) -> None:
    """Esc aus dem QLineEdit beider Maßgruppen erhält Werte und erzeugt keine Operation.

    Seit RM-205 (22.09.2026) geht Escape je Stufe genau eine zurück: aus den
    Maßen an der Stelle erst ins Zielen, das zweite in den Dialog. Geprüft
    wird beides, und nach jedem die Zusage dieses Tests.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    fields = _keyboard_placement(flow, qt_app)
    controller, session, viewport, dialog = flow
    before = len(session.project.document.ops)
    values = dialog.values()
    field = fields[position]
    editor = field.lineEdit()
    assert editor is not None
    editor.setFocus(Qt.FocusReason.OtherFocusReason)
    qt_app.processEvents()
    assert field.hasFocus(), "das innere Eingabefeld muss vor Esc tatsächlich fokussiert sein"
    assert controller._frozen, "die Stelle steht — Stufe 2"

    QTest.keyClick(editor, Qt.Key.Key_Escape)
    qt_app.processEvents()
    assert controller.active and not controller._frozen, "das erste Esc geht ins Zielen"
    assert dialog.values() == values
    assert len(session.project.document.ops) == before

    QTest.keyClick(editor, Qt.Key.Key_Escape)
    qt_app.processEvents()

    assert not controller.active
    assert dialog.isVisible()
    assert not controller._bar.isVisible()
    assert not any(field.isVisible() for field in fields)
    assert viewport.pointer is None
    assert dialog.values() == values
    assert len(session.project.document.ops) == before


def test_tab_reaches_both_dimension_groups_and_returns_to_editable_values(
    flow: Any, qt_app: QApplication
) -> None:
    """Tab erreicht alle Maße; Rückkehr und weitere Wertebearbeitung funktionieren per Taste."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    fields = _keyboard_placement(flow, qt_app)
    controller, session, _viewport, dialog = flow
    before = len(session.project.document.ops)
    placed = {name: dialog.values()[name] for name in ("x", "y", "z")}
    controller._back.setFocus(Qt.FocusReason.OtherFocusReason)
    qt_app.processEvents()
    assert controller._back.hasFocus()
    # Die Kette folgt dem Auge: die zwei Kantenmaße, dann die Mitten. Die
    # Bezugslisten dazwischen sind am 21.09.2026 gefallen (RM-197); der
    # Bezugswechsel hängt seither als Menü am Maß selbst.
    expected = [
        controller._accept,
        fields[0],
        fields[1],
        fields[2],
        fields[3],
        controller._back,
    ]
    seen = []
    for _ in range(len(expected)):
        focused = qt_app.focusWidget()
        assert focused is not None
        QTest.keyClick(focused, Qt.Key.Key_Tab)
        qt_app.processEvents()
        current = next(
            (
                widget
                for widget in (controller._back, controller._accept, *fields)
                if widget.hasFocus()
            ),
            None,
        )
        assert current is not None, "Tab verlor den Fokus außerhalb der Platzierungsbedienung"
        seen.append(current)
    assert seen == expected
    assert controller._frozen, "beim Bearbeiten darf die Maus den Bezug nicht mehr wechseln"

    QTest.keyClick(controller._back, Qt.Key.Key_Space)
    qt_app.processEvents()
    assert not controller.active and dialog.isVisible()
    assert {name: dialog.values()[name] for name in placed} == placed

    diameter = dialog._editors["diameter"].spin
    editor = diameter.lineEdit()
    assert editor is not None
    editor.setFocus(Qt.FocusReason.OtherFocusReason)
    QTest.keyClick(editor, Qt.Key.Key_A, Qt.KeyboardModifier.ControlModifier)
    QTest.keyClicks(editor, "5.5")
    QTest.keyClick(editor, Qt.Key.Key_Tab)
    qt_app.processEvents()
    assert dialog.values()["diameter"] == pytest.approx(5.5)
    assert {name: dialog.values()[name] for name in placed} == placed
    assert len(session.project.document.ops) == before

    dialog.surfaceRequested.emit()
    _point(controller, session)
    assert controller.active and controller._accept.isEnabled()
    assert dialog.values()["diameter"] == pytest.approx(5.5)
    assert len(session.project.document.ops) == before


def test_a_drag_in_the_preview_becomes_numbers_in_the_dialog(qt_app: QApplication) -> None:
    """Der Griff bewegt ein Bild — ankommen muss er in den Feldern.

    Robert am 09.09.2026: „bei erzeugen, Kugel, Quader usw. soll man in der
    Vorschau auch gleich verschieben und drehen können wie unter dem
    Bewegungsmenü." Der Griff liefert die Matrix des Zugs; das Dokument trägt
    Zahlen, und dazwischen steht die Umkehrung des Hinwegs
    (``placement_values_of``).

    Geprüft wird die **Kette**, nicht ihre Mitte: Signal des Viewports, der
    Empfänger im Ablauf, die Felder des Dialogs. Die Rechnung selbst hat ihren
    eigenen Rundreise-Test in ``test_primitive_placement.py``; hier geht es
    darum, dass sie überhaupt aufgerufen wird und ihr Ergebnis irgendwo
    ankommt.
    """
    from app.core.bootstrap import load_operations

    load_operations()
    session = Session()
    viewport = PlacementViewport()
    spec = REGISTRY.get("create_box")
    dialog = OperationDialog(spec, {})
    window = SimpleNamespace(
        viewport=viewport, session=session, _clear_preview=session.cancel_preview
    )
    controller = PlacementFlow(dialog, window, lambda: spec, lambda: ())
    try:
        assert viewport.preview_gizmo, "ein Erzeuger bekommt den Griff an seine Vorschau"

        # Ein Zug: 12 mm in X, dann eine Vierteldrehung um die Hochachse.
        drag = np.eye(4)
        drag[:3, :3] = ((0.0, -1.0, 0.0), (1.0, 0.0, 0.0), (0.0, 0.0, 1.0))
        drag[:3, 3] = (12.0, 0.0, 0.0)
        viewport.previewDragged.emit(drag)
        qt_app.processEvents()

        values = dialog.values()
        assert (values["x"], values["y"], values["z"]) == pytest.approx((12.0, 0.0, 0.0), abs=1e-9)
        apart = abs((float(values["angle"]) - 90.0 + 180.0) % 360.0 - 180.0)
        assert apart == pytest.approx(0.0, abs=1e-6), f"Drehung {values['angle']} statt 90"

        # **Und ein zweiter Zug baut auf dem ersten auf.** Der Griff meldet
        # immer nur, was sich seit dem Anhängen geändert hat; wer das als
        # absolute Lage läse, verlöre die erste Bewegung.
        again = np.eye(4)
        again[:3, 3] = (0.0, 5.0, 0.0)
        viewport.previewDragged.emit(again)
        qt_app.processEvents()
        values = dialog.values()
        assert (values["x"], values["y"], values["z"]) == pytest.approx((12.0, 5.0, 0.0), abs=1e-9)
        apart = abs((float(values["angle"]) - 90.0 + 180.0) % 360.0 - 180.0)
        assert apart == pytest.approx(0.0, abs=1e-6), "die Drehung des ersten Zugs bleibt"
        # **Ein unlesbarer Wert verwirft den Zug, er verschiebt nichts.** Ein
        # Rückfall auf die Einheitsmatrix hätte den Körper in den Nullpunkt
        # gesetzt — mitten im Tippen, ohne dass jemand etwas verlangt hätte.
        dialog._editors["x"].start_expression("=@gibtsnicht")
        viewport.previewDragged.emit(np.eye(4))
        qt_app.processEvents()
        stand = dialog.values()
        assert stand["y"] == pytest.approx(5.0, abs=1e-9), "der Körper bleibt, wo er ist"

        # **Und der Griff gehört dem Dialog.** Bleibt er beim Schließen
        # stehen, hängt ihn die nächste Vorschau wieder an — auch dort, wo er
        # nicht hingehört.
        controller.dispose()
        assert not viewport.preview_gizmo, "der Griff geht mit dem Dialog"
    finally:
        controller.dispose()
        dialog.deleteLater()
        session.release()


def test_only_a_creator_grips_its_own_preview() -> None:
    """Wer mit dem Fadenkreuz zielt, braucht keinen Griff daneben.

    Zwei Gesten für dieselbe Stelle wären eine zu viel: Ein Baustein geht von
    selbst in die Platzierung (``starts_by_itself``), und dort setzt der Klick
    den Ort. Die Erzeuger behalten ihren Dialog — dort ist der Griff der
    einzige Weg, der ohne Zahlen auskommt.

    Und er braucht Felder, in die er schreiben kann: ohne ``angle`` bewegte er
    ein Bild, das beim nächsten Neuzeichnen zurückspringt.
    """
    from app.core.bootstrap import load_operations
    from app.ui.placement_flow import _grips_its_preview, starts_by_itself

    load_operations()

    greifbar = [spec for spec in REGISTRY.all() if _grips_its_preview(spec)]
    assert greifbar, "ohne greifbare Vorschau prüft der Test nichts"
    for spec in greifbar:
        assert not starts_by_itself(spec), f"{spec.name} zielt schon mit dem Fadenkreuz"
        names = {entry.name for entry in spec.params.spec()}
        assert {"x", "y", "z", "nx", "ny", "nz", "angle"} <= names, (
            f"{spec.name}: der Zug hätte keine Felder, in die er schreiben kann"
        )

    # Die Gegenprobe: Was in die Platzierung geht, bekommt keinen.
    for name in ("drill_hole", "insert_screw_hole", "move_feature"):
        assert not _grips_its_preview(REGISTRY.get(name))


@pytest.mark.parametrize(
    ("operation", "werte"),
    [("slot_hole", {"slot_length": 20.0}), ("resize_hole", {"diameter": 8.0})],
)
def test_editing_a_hole_opens_the_same_placement_as_drilling(
    qt_app: QApplication, operation: str, werte: dict[str, float]
) -> None:
    """Bearbeiten zeigt die Maße in der Szene — wie *Bohrung setzen*.

    „einfach wie wenn ich eine bohrung setze … gleiche logik" (Robert,
    10.09.2026). Bis dahin führte der Knopf im Merkmalsfenster die Operation
    sofort aus: ein Schritt im Verlauf, und im Bild kein einziges Maß.

    Gefahren wird der Weg des Kunden: Dialog von *Zum Langloch ziehen* mit der
    Kennung der Bohrung, ``start()`` — und **kein** Zeigerereignis. Danach steht
    die Fläche, ihre Kantenmaße stehen, und die Maßfelder sind da.
    """
    from app.core.bootstrap import load_operations

    load_operations()
    session = Session()
    viewport = PlacementViewport()
    dialog: OperationDialog | None = None
    controller: PlacementFlow | None = None
    try:
        session.import_model(Path(__file__).parent / "data/meshes/plate_holes.stl")
        assert session.wait_for_idle(30_000)
        result = session.last_result
        assert result is not None and result.complete
        viewport.show_scene(result)
        session.sceneChanged.connect(viewport.show_scene)
        object_id, entry = next(iter(result.scene.objects.items()))
        hole = next(name for name, feature in entry.features.items() if feature.kind == "hole")
        mitte = entry.features[hole].params["centre"]

        spec = REGISTRY.get(operation)
        dialog = OperationDialog(
            spec,
            {object_id: "Platte"},
            values={
                "at_feature": hole,
                "x": float(mitte[0]),
                "y": float(mitte[1]),
                "z": float(mitte[2]),
                **werte,
            },
        )
        window = SimpleNamespace(
            viewport=viewport, session=session, _clear_preview=session.cancel_preview
        )
        controller = PlacementFlow(dialog, window, lambda: spec, lambda: (object_id,))
        controller.start()
        assert session.wait_for_idle(30_000)
        qt_app.processEvents()

        assert controller.active, "die Platzierung läuft"
        surface = controller._surface
        assert surface is not None, "die Fläche steht, ohne dass jemand geklickt hat"
        assert controller._frozen, "und die Stelle auch — offen sind die Maße"
        assert surface.edges, "zu den Kanten der Fläche steht ein Maß"
        assert all(edge.distance > 0.0 for edge in surface.edges), (
            "gemessen wird zum Rand des Teils, nicht in die eigene Öffnung"
        )
        assert surface.point[0] == pytest.approx(mitte[0], abs=1e-6)
    finally:
        if controller is not None:
            controller.dispose()
        session.release(30_000)
        if dialog is not None:
            dialog.close()
        viewport.close()
        qt_app.processEvents()


def test_moving_a_feature_starts_where_it_already_sits(qt_app: QApplication) -> None:
    """Wer ein bestehendes Merkmal bewegt, sieht seine Maße — ohne zu zielen.

    Die Platzierung fing bis zum 10.09.2026 immer bei „Auf eine Oberfläche
    zeigen" an. Für ein Werkzeug, das noch nirgends sitzt, ist das richtig; für
    eine Bohrung, die schon da ist, war es der Grund, warum die Maße fehlten
    (Robert, 10.09.2026: „die maße beim langloch ziehen und verschieben sind
    immer noch nicht da zu anderen merkmalen kanten mitten wie beim bohrung
    setzen").

    Gefahren wird der Weg des Kunden bis zur Naht: Dialog von *Merkmal
    verschieben* mit der Kennung der Bohrung, ``start()`` — und **kein**
    Zeigerereignis. Danach steht die Fläche, ihre Kantenmaße stehen, und die
    Stufe ist die zweite: Die Stelle ist entschieden, offen sind die Maße.
    """
    from app.core.bootstrap import load_operations

    load_operations()
    session = Session()
    viewport = PlacementViewport()
    dialog: OperationDialog | None = None
    controller: PlacementFlow | None = None
    try:
        session.import_model(Path(__file__).parent / "data/meshes/plate_holes.stl")
        assert session.wait_for_idle(30_000)
        result = session.last_result
        assert result is not None and result.complete
        viewport.show_scene(result)
        session.sceneChanged.connect(viewport.show_scene)
        object_id, entry = next(iter(result.scene.objects.items()))
        hole = next(name for name, feature in entry.features.items() if feature.kind == "hole")

        spec = REGISTRY.get("move_feature")
        dialog = OperationDialog(spec, {object_id: "Platte"}, values={"at_feature": hole})
        window = SimpleNamespace(
            viewport=viewport, session=session, _clear_preview=session.cancel_preview
        )
        controller = PlacementFlow(dialog, window, lambda: spec, lambda: (object_id,))
        controller.start()
        assert session.wait_for_idle(30_000)
        qt_app.processEvents()

        surface = controller._surface
        assert surface is not None, "die Fläche steht, ohne dass jemand geklickt hat"
        assert controller._frozen, "und die Stelle auch — offen sind die Maße"
        mitte = entry.features[hole].params["centre"]
        assert surface.point[0] == pytest.approx(mitte[0], abs=1e-6)
        assert surface.point[1] == pytest.approx(mitte[1], abs=1e-6)
        assert surface.edges, "zu den Kanten der Fläche steht ein Maß"
        assert all(edge.distance > 0.0 for edge in surface.edges), (
            "gemessen wird zum Rand des Teils, nicht in die eigene Öffnung"
        )
    finally:
        if controller is not None:
            controller.dispose()
        session.release(30_000)
        if dialog is not None:
            dialog.close()
        viewport.close()
        qt_app.processEvents()


MESHES = Path(__file__).parent / "data" / "meshes"


def _window_with_a_renderer():
    """Ein Hauptfenster, dessen Ansicht eine Renderer-Attrappe trägt.

    `MainWindow._measure_in_the_view` steigt an `viewport.renderer is None`
    aus, und offscreen ist das **immer** wahr — der ganze Selbststart wäre in
    der Suite unerreichbar (Fund des Reviews, 11.09.2026). Die Attrappe stellt
    die Betriebslage her, statt sie wegzuräumen (`.claude/rules/tests.md`).
    """
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings
    from tests.render_fakes import RecordingRenderer

    window = MainWindow(Session(), UiSettings())
    window.viewport.renderer = RecordingRenderer(size=(900, 600))
    return window


def _a_selected_hole(window, filename="plate_holes.stl"):
    """Öffnet die Platte, wählt ihre erste Bohrung und wartet die Fläche ab."""
    from PySide6.QtWidgets import QApplication

    window.open_path(MESHES / filename)
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    hole = next(
        identifier for identifier, feature in entry.features.items() if feature.kind == "hole"
    )
    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, hole)
    window.session.wait_for_idle()
    for _ in range(40):
        QApplication.processEvents()
    return object_id, hole


def test_an_imported_slot_opens_its_own_measures_and_keeps_the_handles_in_sync(
    qt_app: QApplication,
) -> None:
    """Importierte Langlöcher zeigen Länge und Breite direkt an den Kantenmaßen."""
    from PySide6.QtTest import QTest

    window = _window_with_a_renderer()
    try:
        window.open_path(MESHES / "plate_coarse_slots.stl")
        window.session.wait_for_idle()
        result = window.session.evaluate_now()
        object_id, entry = next(iter(result.scene.objects.items()))
        feature = next(feature for feature in entry.features.values() if feature.kind == "slot")
        window.object_tree.select_object(object_id)
        window.object_tree.select_feature(object_id, feature.id)
        flow = _measures_in_the_view(window)
        assert flow is not None and flow.active and flow.spec_of().name == "slot_hole"
        assert flow._canvas.shown and flow._canvas.lines
        fields = {
            field.accessibleName().rsplit(" — ", 1)[-1]: field
            for field in flow._measure_group.findChildren(LengthSpin)
        }
        assert {"Länge des Langlochs", "Breite"} <= fields.keys()
        # Getippt, wie der Kunde tippt: Erst eine Taste im Feld beginnt den
        # Entwurf (``QuietHost.begin_edit``), und erst ein begonnener Entwurf
        # führt den Umriss nach. ``set_value_mm`` ging daran vorbei, und der
        # Test war seit seiner Entstehung rot, ohne dass es ein Lauf zeigte.
        editor = fields["Länge des Langlochs"].lineEdit()
        editor.selectAll()
        QTest.keyClicks(editor, QLocale().toString(12.0, "f", 2))
        for _ in range(40):
            QApplication.processEvents()
        handle = window.viewport._slot_handle
        assert handle is not None and handle.length == pytest.approx(12.0)
        # Die Zahl steht im Entwurf, den *Übernehmen* liest. Das Merkmalfenster
        # rechts bekommt sie beim Tippen bewusst nicht zurück („Wer gerade
        # liest, schreibt nicht zurück“, ``MainWindow._place_measures``); sein
        # Zwilling zeigt die Länge ohnehin nicht, solange die Maßgruppe steht.
        armed = window.feature_panel._runs[window.feature_panel._armed]
        assert armed.op == "slot_hole"
        assert flow.dialog.values()["slot_length"] == pytest.approx(12.0)
        _display_measure_preview(window, flow)
        before = len(window.session.project.document.ops)
        flow.accept()
        for _ in range(120):
            QApplication.processEvents()
            window.session.wait_for_idle()
        assert len(window.session.project.document.ops) == before + 1
        added = window.session.project.document.ops[-1]
        assert added.op == "slot_hole" and added.params["slot_length"] == pytest.approx(12.0)
        assert window.session.last_result.stopped_at is None
        window.session.undo()
        window.session.wait_for_idle()
        assert len(window.session.project.document.ops) == before
    finally:
        window.end_quiet_placement()
        QApplication.processEvents()
        window.release()


def _measures_in_the_view(window):
    """Die automatisch angezeigten Maße oder den ausdrücklich gewählten Einstieg abwarten."""
    from PySide6.QtWidgets import QApplication

    if window._quiet_placement is None:
        knopf = window.feature_panel._in_view
        assert not knopf.isHidden(), "die gewählte Handlung bietet Maße im Bild an"
        knopf.click()
    assert window.session.wait_for_idle()
    for _ in range(40):
        QApplication.processEvents()
    return window._quiet_placement


def _display_measure_preview(window, flow):
    """Den normalen Vorschauauftrag bis zur wirklichen Rendereranzeige durchführen."""
    window._feature_preview.stop()
    window._preview_feature_change()
    assert window.session.wait_for_idle(30_000)
    for _ in range(40):
        QApplication.processEvents()
    approval = window._preview_approval
    assert approval is not None and approval.owner is flow.dialog
    assert approval.displayed and window.viewport.is_difference_applied(approval.difference)
    return approval


def _choose_measure_action(window, op):
    """Eine andere vorhandene Handlung wählen, bevor ihr Entwurf begonnen wird."""
    panel = window.feature_panel
    key = next(key for key, entry in panel._runs.items() if entry.op == op)
    panel._arm(key)
    panel.request_in_view()
    return _measures_in_the_view(window)


@pytest.mark.parametrize("angle", [45.0, -30.0])
@pytest.mark.parametrize("handoff_focus", [False, True])
@pytest.mark.parametrize("filename", ["plate_holes.stl", "lower_blind.stl"])
def test_panel_slot_values_survive_the_first_measure_card(
    qt_app: QApplication,
    monkeypatch: Any,
    tmp_path: Path,
    angle: float,
    handoff_focus: bool,
    filename: str,
) -> None:
    """Eine Richtung aus der rechten Spalte steht sofort auch in der Maßkarte."""
    from app.ui.panels import FIELD_PROPERTY, feature_field_values

    window = _window_with_a_renderer()
    try:
        source = MESHES / filename
        if filename == "lower_blind.stl":
            from app.core.knowledge import profiles
            from app.core.scene import History, evaluate
            from app.core.scene.project import new_project

            project = new_project()
            history = History(project.document)
            history.apply(
                "Platte",
                [OperationDraft("create_box", params={"width": 40, "depth": 30, "height": 12})],
            )
            history.apply(
                "Sackbohrung von unten",
                [
                    OperationDraft(
                        "drill_hole",
                        inputs=("obj_1",),
                        params={"diameter": 5, "depth": 6, "nz": -1},
                    )
                ],
            )
            result = evaluate(project.document, profiles.make_profile())
            assert result.complete
            source = tmp_path / filename
            result.scene.objects["obj_1"].mesh.raw.export(source)
        _object_id, hole = _a_selected_hole(window, source)
        panel = window.feature_panel
        key = next(key for key, run in panel._runs.items() if run.op == "slot_hole")
        row = panel._blocks[key][1]
        editor = next(
            widget
            for widget in row.findChildren(QWidget)
            if widget.property(FIELD_PROPERTY) == "slot_angle"
        )
        if handoff_focus:
            panel._arm(key)
            flow = _measures_in_the_view(window)
            target = next(
                widget
                for widget in flow.measure_group.findChildren(QWidget)
                if widget.property(FIELD_PROPERTY) == "slot_angle"
            )
            assert not target.lineEdit().isModified()
            monkeypatch.setattr(QApplication, "focusWidget", lambda: target.lineEdit())
        editor.setValue(angle)
        flow = _measures_in_the_view(window)
        assert flow is not None and flow.dialog.values()["slot_angle"] == pytest.approx(angle)
        assert flow.dialog.begun
        action = next(run.action for run in panel._runs.values() if run.op == "slot_hole")
        editors = {
            widget.property(FIELD_PROPERTY): widget
            for widget in flow.measure_group.findChildren(QWidget)
            if widget.property(FIELD_PROPERTY) is not None
        }
        values = feature_field_values(action.fields, editors, feature_id=hole)
        assert values["slot_angle"] == pytest.approx(angle)
        assert values["slot_length"] == pytest.approx(flow.dialog.values()["slot_length"])
        _display_measure_preview(window, flow)
        assert flow._accept.isEnabled()
        before = len(window.session.project.document.ops)
        flow.accept()
        assert window.session.wait_for_idle(30_000)
        assert len(window.session.project.document.ops) == before + 1
        assert window.session.project.document.ops[-1].params["slot_angle"] == pytest.approx(angle)
    finally:
        window.end_quiet_placement()
        QApplication.processEvents()
        window.release()


def test_a_clicked_hole_can_really_be_accepted(qt_app: QApplication) -> None:
    """Ein angeklicktes Loch zeigt seine Maße — und lässt sich übernehmen.

    Der Knopf gibt nur frei, wenn ein **Werkzeugkörper** steht
    (`PlacementFlow.redraw`), und `placement.prepare_tool` kannte die zwei
    Operationen nicht: Der Dialog ging auf, die Maßlinien standen, die Leiste
    sagte „Übernehmen oder mit Esc die Werte bearbeiten" — und *Übernehmen* war
    grau (Fund des Reviews, 11.09.2026). Ein Text, der etwas verspricht, das
    die Oberfläche nicht einlöst, ist schlimmer als kein Text.

    Geprüft wird deshalb bis zum Ende: Fläche, Werkzeug **und** der Knopf.

    **Und seit dem 11.09.2026 über den Knopf im Merkmalfenster**, nicht mehr
    von selbst: Der Dialog, der die Platzierung trug, zeigte dieselben Zahlen
    ein zweites Mal (Robert: „werte im dialog und in der rechten
    merkmalleiste doppelt").
    """
    from app.ui.op_dialog import OperationDialog

    window = _window_with_a_renderer()
    try:
        _a_selected_hole(window)
        assert window._op_dialog is None, "ein angeklicktes Loch öffnet keinen Dialog mehr"
        # Zugemacht **nach** der Auswahl: Eine neue Auswahl bringt das Fenster
        # zurück (Konzept D, ``_on_selection``); der Weg ins Bild tut es nicht.
        window.feature_dock.hide()
        flow = _measures_in_the_view(window)
        assert flow is not None and flow.active, "die Auswahl zeigt die Maße im Bild"
        assert window.feature_dock.isHidden(), "das geschlossene Panel bleibt geschlossen"
        assert flow._surface is not None, "die Trägerfläche steht"
        assert flow._tool_context is not None, "und ihr Werkzeugkörper auch"
        assert flow._accept.isEnabled(), "sonst verspricht die Leiste etwas, das nicht geht"
        assert not flow.dialog.begun
        assert not flow._measure_box.isHidden()
        assert not flow._measure_accept.isEnabled(), "bloße Auskunft ist noch kein Entwurf"
    finally:
        for dialog in window.findChildren(OperationDialog):
            dialog.reject()
        QApplication.processEvents()
        window.release()


def test_the_next_hole_takes_over_the_floating_widgets_of_the_last(qt_app: QApplication) -> None:
    """Von Bohrung zu Bohrung bleiben Maßkarte, Kantenmaße und Maßtinte dieselben (RM-232).

    Jeder Merkmalklick baut einen neuen Fluss, und bis zum 25.09.2026 baute
    jeder auch seine Widgets über der Grafikfläche neu: am echten Fenster neun
    native Fenster anlegen, zeigen, verbergen und löschen, rund 40 ms je
    Klick. Der Vorgänger legt sie beim Abbau ab (``_park_floating``), der
    Nachfolger übernimmt sie — dieselben Objekte, ohne eine Verbindung zum
    alten Fluss, und ihre Felder arbeiten für den neuen Träger.
    """
    from PySide6.QtCore import SIGNAL

    from app.ui.labels import _WheelNeedsFocus

    window = _window_with_a_renderer()
    try:
        object_id, first_hole = _a_selected_hole(window)
        first = _measures_in_the_view(window)
        assert first is not None and first.active and first._surface is not None
        kept = (first._measure_box, first._canvas, *first._measures, *first._reference_boxes)
        listeners = (
            first._measure_cancel.receivers(SIGNAL("clicked(bool)")),
            first._measures[0].receivers(SIGNAL("valueChangedMm(double)")),
        )
        entry = window.session.last_result.scene.objects[object_id]
        second_hole = next(
            identifier
            for identifier, feature in entry.features.items()
            if feature.kind == "hole" and identifier != first_hole
        )
        window.object_tree.select_feature(object_id, second_hole)
        second = _measures_in_the_view(window)
        assert second is not None and second is not first and second.active
        assert not first.active and first._links == [], "der alte Fluss hält nichts mehr"
        assert (
            second._measure_box,
            second._canvas,
            *second._measures,
            *second._reference_boxes,
        ) == kept, "dieselben Widgets und dieselbe Tinte"
        assert (
            second._measure_cancel.receivers(SIGNAL("clicked(bool)")),
            second._measures[0].receivers(SIGNAL("valueChangedMm(double)")),
        ) == listeners, "je Signal genau die Verbindungen eines Flusses"
        assert all(
            len(field.findChildren(_WheelNeedsFocus)) == 1
            for field in (*second._measures, second._depth_measure, *second._centre_measures)
        ), "der Radfilter wird nicht verdoppelt"
        assert second._surface is not None and not second._measure_box.isHidden()
        heard: list[str] = []
        first.dialog.valuesChanged.connect(lambda *_args: heard.append("alt"))
        second.dialog.valuesChanged.connect(lambda *_args: heard.append("neu"))
        field = second._measures[0]
        assert not field.isHidden(), "das Kantenmaß steht für die neue Bohrung"
        field.set_value_mm(field.value_mm() + 1.0)
        for _ in range(20):
            QApplication.processEvents()
        assert "neu" in heard and "alt" not in heard, "das Feld arbeitet für den neuen Träger"
    finally:
        window.end_quiet_placement()
        QApplication.processEvents()
        window.release()


def _another_hole(window, object_id: str, hole: str) -> str:
    """Eine zweite Bohrung desselben Körpers."""
    entry = window.session.last_result.scene.objects[object_id]
    return next(
        identifier
        for identifier, feature in entry.features.items()
        if feature.kind == "hole" and identifier != hole
    )


def test_a_click_at_a_hole_holds_the_picture_until_its_surface_is_there(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Bild je Bohrungsklick statt zweier (RM-232).

    Nach dem synchronen Teil malte die Ansicht die neue Auswahl ohne Maße,
    und die Fläche aus dem Arbeiter wartete hinter diesem Bild; das zweite
    brachte die Maße. Der Fluss hält das Bild an, solange er die Fläche am
    Merkmal rechnet, und gibt es frei, sobald sie steht — ein Anhalten, eine
    Freigabe, mit der Frist aus ``FRAME_HOLD_MS``.

    Das gilt für den Weg über den Arbeiter. An einem kleinen Körper entsteht
    die Fläche seit ``f01f8b622`` gleich im Klick (``AT_ONCE_BELOW``); dort
    sind Anhalten und Freigabe beide schon vorbei, wenn der Klick zurückkehrt.
    Die Platte liegt unter der Grenze, der Arbeiterweg wird deshalb mit
    ``AT_ONCE_BELOW = 0`` erzwungen und danach der Klickweg geprüft.
    """
    from app.ui import placement_flow
    from app.ui.placement_flow import FRAME_HOLD_MS

    at_once_below = placement_flow.AT_ONCE_BELOW
    monkeypatch.setattr(placement_flow, "AT_ONCE_BELOW", 0)
    window = _window_with_a_renderer()
    try:
        object_id, first_hole = _a_selected_hole(window)
        renderer = window.viewport.renderer
        first = _measures_in_the_view(window)
        assert first is not None and first._surface is not None
        entry = window.session.last_result.scene.objects[object_id]
        assert entry.mesh.triangle_count < at_once_below, "die Platte ist ein kleiner Körper"
        assert renderer.holds and set(renderer.holds) == {FRAME_HOLD_MS}
        assert renderer.releases == len(renderer.holds), "freigegeben, sobald die Fläche steht"
        second_hole = _another_hole(window, object_id, first_hole)
        window.object_tree.select_feature(object_id, second_hole)
        assert renderer.releases == len(renderer.holds) - 1, "angehalten, solange sie rechnet"
        second = _measures_in_the_view(window)
        assert second is not None and second is not first and second._surface is not None
        assert renderer.releases == len(renderer.holds) and not second._frames_held

        # Am kleinen Körper rechnet der Klick selbst: angehalten und
        # freigegeben, bevor er zurückkehrt, und die Fläche steht schon.
        monkeypatch.setattr(placement_flow, "AT_ONCE_BELOW", at_once_below)
        holds_before = len(renderer.holds)
        window.object_tree.select_feature(object_id, first_hole)
        assert len(renderer.holds) > holds_before, "auch der Klickweg hält das Bild an"
        assert renderer.releases == len(renderer.holds), "und gibt es im Klick wieder frei"
        third = window._quiet_placement
        assert third is not None and third is not second and third._surface is not None
        assert not third._frames_held
    finally:
        window.end_quiet_placement()
        QApplication.processEvents()
        window.release()


def test_the_feature_panel_keeps_measuring_from_hole_to_hole(qt_app: QApplication) -> None:
    """Zwischen zwei Bohrungen schaltet das Merkmalfenster nicht aus und wieder an (RM-232).

    Der Baum meldet die Auswahl in drei Signalen derselben Runde; das erste
    räumte die alte Maßgruppe ab und nahm das Fenster aus dem Messen, das
    zweite schaltete es für die neue wieder hinein — 87 Sichtbarkeitswechsel
    je Klick am Wabenhalter. Entschieden wird jetzt nach dem letzten Signal
    (``MainWindow._release_measuring``). Gegenprobe: Wer den Körper wählt,
    hat danach kein Messen mehr.
    """
    window = _window_with_a_renderer()
    try:
        object_id, first_hole = _a_selected_hole(window)
        assert _measures_in_the_view(window) is not None
        panel = window.feature_panel
        assert panel.measuring
        switched: list[bool] = []
        original = panel.set_measuring

        def recording(active: bool, **kwargs: Any) -> None:
            switched.append(bool(active))
            original(active, **kwargs)

        panel.set_measuring = recording  # type: ignore[method-assign]
        window.object_tree.select_feature(object_id, _another_hole(window, object_id, first_hole))
        assert False not in switched and panel.measuring, (
            "die Maßgruppe wechselt, das Messen bleibt"
        )
        assert _measures_in_the_view(window) is not None and panel.measuring
        window.object_tree.select_object(object_id)
        window.session.wait_for_idle()
        for _ in range(20):
            QApplication.processEvents()
        assert window._quiet_placement is None and not panel.measuring, "ohne Bohrung kein Messen"
    finally:
        window.end_quiet_placement()
        QApplication.processEvents()
        window.release()


def test_passive_measures_can_be_replaced_but_a_begun_draft_cannot(
    qt_app: QApplication,
) -> None:
    """Zweimal derselbe Knopf legt keine zweite Platzierung übereinander.

    Bis zum 11.09.2026 hielt ein Merker (`_measured_for`) den **Selbststart**
    davon ab, nach jeder Auswertung neu anzuspringen. Den Selbststart gibt es
    nicht mehr; was bleibt, ist dieselbe Frage an den Knopf: Wer ihn zweimal
    drückt, meint eine Platzierung und nicht zwei übereinander.

    Die Antwort steckt in `end_quiet_placement` — jeder neue Anlauf räumt den
    alten ab. Ohne das lägen zwei Träger über demselben Loch, und welcher
    beim Übernehmen gewinnt, entschiede die Reihenfolge.
    """
    from app.ui.op_dialog import OperationDialog

    window = _window_with_a_renderer()
    try:
        _a_selected_hole(window)
        erste = _measures_in_the_view(window)
        assert erste is not None and erste.active, "die Maße erscheinen bei der Auswahl"

        zweite = _choose_measure_action(window, "slot_hole")
        assert zweite is not None and zweite.active, "und beim zweiten Mal wieder"
        assert zweite is not erste, "es ist eine frische Platzierung"
        assert not erste.active, "die erste ist abgeräumt, nicht liegengeblieben"
        assert window._quiet_placement is zweite, "und das Fenster führt genau eine"
        assert window._op_dialog is None, "ein Dialog geht dabei nie auf"
        zweite.dialog.begin_edit()
        before = zweite.dialog.values()
        window.run_operation(REGISTRY.get("create_box"))
        assert window._quiet_placement is zweite and zweite.active
        assert zweite.dialog.values() == before and window._op_dialog is None
    finally:
        for dialog in window.findChildren(OperationDialog):
            dialog.reject()
        QApplication.processEvents()
        window.release()


def test_an_open_dialog_keeps_the_click(qt_app: QApplication) -> None:
    """Steht ein Dialog offen, gehört der Klick ihm — nicht dem Selbststart.

    §18.5 sagt zu: Ein Klick auf ein Merkmal ist dann eine **Eingabe**.
    `run_operation` verwirft aber jeden offenen Operationsdialog, und der
    Selbststart lief darüber — der Dialog, den der Kunde gerade beantworten
    wollte, war weg, samt seiner getippten Werte (Fund des Reviews,
    11.09.2026).
    """
    from app.core.registry import REGISTRY
    from app.ui.op_dialog import OperationDialog

    window = _window_with_a_renderer()
    try:
        window.open_path(MESHES / "plate_holes.stl")
        window.session.wait_for_idle()
        result = window.session.evaluate_now()
        object_id, entry = next(iter(result.scene.objects.items()))
        hole = next(
            identifier for identifier, feature in entry.features.items() if feature.kind == "hole"
        )
        window.object_tree.select_object(object_id)
        QApplication.processEvents()

        # Ein fremder Dialog, der auf ein Merkmal wartet.
        window.run_operation(REGISTRY.get("countersink_hole"))
        QApplication.processEvents()
        assert window._op_dialog is not None, "der Dialog steht"
        assert window._op_dialog.spec.name == "countersink_hole"

        window.object_tree.select_feature(object_id, hole)
        window.session.wait_for_idle()
        for _ in range(40):
            QApplication.processEvents()

        danach = window._op_dialog
        assert danach is not None and danach.spec.name == "countersink_hole", (
            f"der offene Dialog überlebt den Klick nicht: {danach}"
        )
    finally:
        for dialog in window.findChildren(OperationDialog):
            dialog.reject()
        QApplication.processEvents()
        window.release()


def test_neither_a_drag_nor_a_click_beside_the_grip_sends_the_measures_aiming(
    qt_app: QApplication,
) -> None:
    """Ein begonnener Maßentwurf bleibt am Merkmal, auch bei verfehltem Griff."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.ui.labels import LengthSpin
    from app.ui.op_dialog import OperationDialog
    from app.ui.render.api import PointerEvent

    window = _window_with_a_renderer()
    try:
        _a_selected_hole(window)
        flow = _measures_in_the_view(window)
        assert flow is not None and flow._seated_at_feature, "die Maße stehen am gewählten Merkmal"
        field = flow._measure_group.findChildren(LengthSpin)[0]
        QTest.mouseClick(field.lineEdit(), Qt.MouseButton.LeftButton)
        assert flow.dialog.begun

        # Ein Zug über das halbe Bild, der keinen Griff trifft.
        for event in (
            PointerEvent("press", 200, 200, button="left"),
            PointerEvent("move", 320, 260, buttons=frozenset({"left"})),
            PointerEvent("release", 440, 320, button="left"),
        ):
            window.viewport._on_pointer(event)
        QApplication.processEvents()
        assert flow._seated_at_feature, "ein Zug hat die Maße vom Merkmal weg ins Zielen geschickt"

        # Und ein Klick daneben ebenso wenig.
        for event in (
            PointerEvent("press", 200, 200, button="left"),
            PointerEvent("release", 201, 200, button="left"),
        ):
            window.viewport._on_pointer(event)
        QApplication.processEvents()
        assert flow._seated_at_feature, "der Klick daneben zielt nicht — es gibt kein Zielen"
        assert not flow.pointer(PointerEvent("press", 200, 200, button="left")), (
            "der Auswahlwächter entscheidet, der Fluss startet keine neue Flächensuche"
        )
        # Die freie Bewegung nimmt der Fluss nicht — sie gehört dem Hover der
        # Ansicht (bis zum 21.09.2026 verschluckte er sie, und bei gewählter
        # Bohrung gab es keinen Tooltip mehr). Vorschau am Zeiger gibt es
        # trotzdem keine: kein wartender Klick, kein laufender Zeitgeber.
        assert not flow.pointer(PointerEvent("move", 200, 200)), (
            "die freie Bewegung bleibt der Ansicht — der Fluss meldet sie nicht als seine"
        )
        assert flow._pending is None and not flow._timer.isActive(), (
            "und sie löst keine Vorschau am Zeiger aus"
        )
    finally:
        for open_dialog in window.findChildren(OperationDialog):
            open_dialog.reject()
        QApplication.processEvents()
        window.release()


def test_pulling_a_slot_and_moving_it_at_the_grip_is_one_step(qt_app: QApplication) -> None:
    """Langloch ziehen, dann am Griff versetzen, dann übernehmen — ein Schritt für beides.

    Bis zum Abend des 11.09.2026 warf der Zug am Bewegungsgriff das eben
    gezogene Langloch weg: Jeder Neuaufbau des Griffs leerte den wartenden
    Langlochzug, der Umriss sprang zurück (Robert: „das langloch ziehe und
    dann das langloch nochmal über das gizmo verschieben will ist es wie
    abbrechen"). Jetzt warten beide zusammen: Der Griff trägt die gezogene
    Länge an der versetzten Stelle, die Felder von *Zum Langloch ziehen*
    kennen Länge **und** Stelle, und ``slot_hole`` schneidet beides in einem
    Schritt.

    **Und danach ist das Langloch gewählt**, obwohl es seinen Namen gewechselt
    hat (``hole_1`` → ``slot_1``): Es wird an der Stelle wiedergefunden, die
    der Schritt genannt hat, und die Maße und Griffe stehen dort wieder.
    """
    from app.core.geom.transform import translation
    from app.ui.op_dialog import OperationDialog
    from app.ui.render.api import PointerEvent

    window = _window_with_a_renderer()
    try:
        _, hole = _a_selected_hole(window)
        erster = _choose_measure_action(window, "slot_hole")
        assert erster is not None and erster.active
        for _ in range(200):
            QApplication.processEvents()
            window.session.wait_for_idle()
            if erster._tool_context is not None:
                break
        feature = window.viewport._features_of_selection()[hole]
        centre = tuple(float(value) for value in feature.params["centre"])

        # Erst am Langlochknopf ziehen …
        handle = window.viewport._slot_handle
        assert handle is not None
        renderer = window.viewport.renderer
        seat = renderer.world_to_display(handle.knob_seats[0])
        x, y = round(seat[0]), round(seat[1])
        renderer.item_picks[(x, y)] = handle.knobs[0]
        for event in (
            PointerEvent("move", x, y),
            PointerEvent("press", x, y, button="left"),
            PointerEvent("move", x + 12, y, buttons=frozenset({"left"})),
            PointerEvent("release", x + 12, y, button="left"),
        ):
            window.viewport._on_pointer(event)
        QApplication.processEvents()
        assert window.viewport.slot_drag_waits()
        pulled = window.viewport._slot_handle
        assert pulled is not None
        length = pulled.length

        mark = window.viewport._shape_actor
        assert mark is not None
        span = mark.points.max(axis=0) - mark.points.min(axis=0)
        assert max(span[0], span[1]) == pytest.approx(length, abs=0.05), (
            "nach dem Zug ist die Marke das Langloch, nicht mehr die Bohrung"
        )

        # … dann am Bewegungsgriff versetzen. Unterwegs gehen Umriss und
        # Marke mit, danach stehen beide an der neuen Stelle.
        window.viewport._on_gizmo_interacted(translation((6.0, 4.0, 0.0)))
        assert pulled._outline is not None
        assert np.allclose(pulled._outline.position(), (6.0, 4.0, 0.0)), "der Umriss geht mit"
        window.viewport._on_gizmo_released(translation((6.0, 4.0, 0.0)))
        QApplication.processEvents()
        assert window.viewport.slot_drag_waits(), "der Langlochzug wartet weiter"
        assert window.viewport.move_proposal_waits(), "und das Versetzen dazu"
        again = window.viewport._slot_handle
        assert again is not None and again.length == pytest.approx(length), (
            "der neue Griff trägt die gezogene Länge"
        )
        assert again._outline is not None, "und seinen Umriss — nicht nur zwei Knöpfe um nichts"
        seat = window.viewport._face_seat
        assert seat is not None
        assert np.allclose(again._outline.points.mean(axis=0)[:2], seat[0][:2], atol=0.1), (
            "der Umriss steht um die versetzte Stelle"
        )
        moved = window.viewport._shape_actor
        assert moved is not None and moved is not mark
        span = moved.points.max(axis=0) - moved.points.min(axis=0)
        assert max(span[0], span[1]) == pytest.approx(length, abs=0.05), (
            "die Marke an der neuen Stelle ist das Langloch"
        )
        assert np.allclose(moved.points.mean(axis=0)[:2], seat[0][:2], atol=0.1)
        armed = window.feature_panel._runs.get(window.feature_panel._armed or "")
        assert armed is not None and armed.op == "slot_hole", "*Zum Langloch ziehen* steht scharf"

        vorher = [o.op for o in window.session.history.operations]
        _display_measure_preview(window, erster)
        erster._measure_accept.click()
        window.session.wait_for_idle()
        for _ in range(120):
            QApplication.processEvents()
        assert [o.op for o in window.session.history.operations] == [*vorher, "slot_hole"], (
            "ein Schritt für beides"
        )
        slots = {
            name: entry
            for name, entry in window.viewport._features_of_selection().items()
            if entry.kind == "slot"
        }
        assert len(slots) == 1, slots
        name, slot = next(iter(slots.items()))
        assert float(slot.params["length"]) == pytest.approx(length, abs=0.1)
        assert slot.params["centre"] == pytest.approx(
            (centre[0] + 6.0, centre[1] + 4.0, centre[2]), abs=0.1
        ), "an der versetzten Stelle"
        assert window.object_tree.selected_feature() == name, "und danach gewählt"
        danach = window._quiet_placement
        assert danach is not None and danach.active, "mit den Maßen im Bild"
        assert window.viewport._slot_handle is not None, "und den Griffen"
    finally:
        window.end_quiet_placement()
        for open_dialog in window.findChildren(OperationDialog):
            open_dialog.reject()
        QApplication.processEvents()
        window.release()


def test_escape_leaves_the_measures_and_discards_what_waits(qt_app: QApplication) -> None:
    """Escape ist der Ausgang aus den Maßen — es verwirft und wählt ab wie Abbrechen.

    Die stille Platzierung hat kein Fenster und kein Kreuz. Bis zum
    11.09.2026 fing ihr Ereignisfilter Escape nur ab, solange kein Langlochzug
    wartete; wartete einer, ließ sie die Taste durch, und die ging eine Stufe
    Auswahl zurück — die Maße blieben stehen (Robert: „kann auch den modus
    nicht mehr verlassen"). Bis zum 25.09.2026 blieb danach die Auswahl
    stehen, und rechts stand der verworfene Entwurf scharf; seither nimmt
    Escape zurück und wählt ab (Entscheidung Robert).
    """
    from app.ui.op_dialog import OperationDialog

    window = _window_with_a_renderer()
    try:
        _, hole = _a_selected_hole(window)
        flow = _choose_measure_action(window, "slot_hole")
        assert flow is not None and flow.active
        handle = window.viewport._slot_handle
        assert handle is not None
        handle._release(14.0, 0.0)
        QApplication.processEvents()
        assert window.viewport.slot_drag_waits(), "ein Langlochzug wartet"
        vorher = [o.op for o in window.session.history.operations]

        window._escape()
        QApplication.processEvents()

        assert not flow.active and window._quiet_placement is None, "die Maße sind weg"
        assert not window.viewport.slot_drag_waits(), "und der wartende Zug mit ihnen"
        assert window.viewport._slot_handle is None, "ohne Platzierung keine Griffe"
        assert [o.op for o in window.session.history.operations] == vorher, (
            "verworfen, nicht gerechnet"
        )
        assert window.object_tree.selected() is None, "und abgewählt wie bei Abbrechen"
        assert window.object_tree.selected_feature() != hole
    finally:
        window.end_quiet_placement()
        for open_dialog in window.findChildren(OperationDialog):
            open_dialog.reject()
        QApplication.processEvents()
        window.release()


def test_the_bound_placement_grip_changes_the_same_measure_order(qt_app: QApplication) -> None:
    """Der Griff ändert denselben Größenauftrag; Loslassen übernimmt ihn noch nicht."""
    from app.ui.render.api import PointerEvent

    window = _window_with_a_renderer()
    try:
        object_id, hole = _a_selected_hole(window)
        flow = _measures_in_the_view(window)
        assert flow is not None and flow.active
        before = len(window.session.history.operations)
        original = tuple(flow._surface.point)
        grip = window.viewport._placement_grip
        assert grip is not None and not grip._rings
        window.viewport.renderer.item_picks[(400, 300)] = grip.items[0]
        window.viewport.renderer.item_picks[(412, 300)] = grip.items[0]
        for event in (
            PointerEvent("move", 400, 300),
            PointerEvent("press", 400, 300, button="left"),
            PointerEvent("move", 412, 300, buttons=frozenset({"left"})),
            PointerEvent("release", 412, 300, button="left"),
        ):
            window.viewport._on_pointer(event)
        assert window.session.wait_for_idle(30_000)
        assert flow.dialog.begun and flow.active
        assert len(window.session.history.operations) == before
        values = flow.dialog.values()
        assert not np.allclose((values["x"], values["y"]), original[:2])
        _display_measure_preview(window, flow)
        flow._measure_accept.click()
        assert window.session.wait_for_idle(30_000)
        assert len(window.session.history.operations) == before + 1
        step = window.session.history.operations[-1]
        assert step.op == "resize_hole" and step.params["at_feature"] == hole
        assert (step.params["x"], step.params["y"]) == pytest.approx((values["x"], values["y"]))
        assert window.session.last_result.complete
        assert object_id in window.session.last_result.scene.objects
    finally:
        window.end_quiet_placement()
        QApplication.processEvents()
        window.release()


def test_a_click_on_the_grip_leaves_the_next_hole_free(qt_app: QApplication) -> None:
    """Ein Klick ohne Weg auf den Bewegungsgriff bindet nichts und bewegt nichts.

    Der Griff sitzt in der Mitte der gewählten Bohrung. Ein Klick dorthin —
    mit dem Zittern, das Klicken hat — meldete bis zum 27.09.2026 schon beim
    Drücken den Beginn eines Zugs, band den Maßentwurf, und danach ließ sich
    keine andere Bohrung mehr wählen (Wabenhalter, Durchsicht 0.5.1).
    """
    from app.ui.render.api import PointerEvent

    window = _window_with_a_renderer()
    try:
        object_id, hole = _a_selected_hole(window)
        flow = _measures_in_the_view(window)
        assert flow is not None and flow.active and not flow.dialog.begun
        values = dict(flow.dialog.values())
        grip = window.viewport._placement_grip
        assert grip is not None
        window.viewport.renderer.item_picks[(400, 300)] = grip.items[0]
        dragged: list[object] = []
        window.viewport.placementDragged.connect(dragged.append)
        for event in (
            PointerEvent("move", 400, 300),
            PointerEvent("press", 400, 300, button="left"),
            PointerEvent("move", 403, 302, buttons=frozenset({"left"})),
            PointerEvent("release", 403, 302, button="left"),
        ):
            window.viewport._on_pointer(event)
        assert window.session.wait_for_idle(30_000)
        assert not flow.dialog.begun and flow.active, "der Klick beginnt keinen Entwurf"
        assert dragged == [] and flow.dialog.values() == values, "und bewegt nichts"
        assert window.viewport.user_selection_allowed()
        assert window.object_tree.tree.selection_allowed()

        other = next(
            identifier
            for identifier, feature in window.session.last_result.scene.objects[
                object_id
            ].features.items()
            if feature.kind == "hole" and identifier != hole
        )
        window.object_tree.select_feature(object_id, other)
        window.session.wait_for_idle()
        for _ in range(40):
            QApplication.processEvents()
        assert window.object_tree.selected_feature() == other
        assert window._quiet_target == (object_id, other), "die Maße gehen mit"
    finally:
        window.end_quiet_placement()
        QApplication.processEvents()
        window.release()


def test_the_button_shows_the_answer_it_no_longer_holds(flow: Any) -> None:
    """Ob platziert werden darf, weiß der Fluss — nicht ein Knopf im Dialog.

    Die Frage stand bis zum 11.09.2026 als `surface_button.isEnabled()` im
    Dialog, und drei Stellen lasen sie von dort: der Selbststart, `start()`
    und `refresh_available` selbst. Ein Widget als Zustandsspeicher hält nur,
    solange es das Widget gibt — und der Knopf soll fallen (Robert,
    11.09.2026: „im dialog das im modell platzieren brauchen wir auch nicht").

    Geprüft wird die Umkehrung der alten Lage: Wer den Knopf von außen
    umschaltet, ändert die Antwort **nicht**; wer die Lage ändert, schon.
    """
    controller, _session, viewport, dialog = flow
    try:
        assert controller.can_place(), "mit Renderer und gerechneter Szene geht es"

        # Den Knopf gibt es nicht mehr; was er trug, steht hier.
        assert not hasattr(dialog, "surface_button"), "der Knopf ist gefallen"

        # Die Lage dagegen trägt sie. Ohne Renderer ist nichts da, worauf man
        # zeigen könnte — dieselbe Bedingung wie eh und je, nur an ihrem Ort.
        renderer, viewport.renderer = viewport.renderer, None
        try:
            assert not controller.can_place(), "ohne Ansicht gibt es keine Fläche"
        finally:
            viewport.renderer = renderer
        assert controller.can_place(), "und mit ihr wieder"

        # Und `refresh_available` bleibt die Stelle, an der die fachliche
        # Hälfte nachgezogen wird — ohne ein Widget dazwischen.
        controller.refresh_available()
        assert controller.can_place()
    finally:
        controller.dispose()


def test_quiet_host_consumes_only_a_successful_callback(qt_app: QApplication) -> None:
    """Eine Absage erhält den begonnenen Wertestand; der nächste Erfolg verbraucht ihn einmal."""
    from app.ui.placement_flow import QuietHost

    calls: list[Any] = []
    finished: list[int] = []
    starts: list[bool] = []

    def take(values: Any) -> bool:
        assert host.committing
        assert not host.can_accept()
        calls.append(values)
        host.accept()
        return len(calls) > 1

    host = QuietHost({"diameter": 5.0}, take)
    host.finished.connect(finished.append)
    host.editStarted.connect(lambda: starts.append(host.begun))
    host.take_placement({"diameter": 6.0})
    assert not host.begun
    host.begin_edit()
    host.begin_edit()
    assert starts == [True]
    assert host.accept() is None
    assert not finished and host.begun and not host.committing
    assert host.values() == {"diameter": 6.0}
    assert host.accept() is None
    assert finished == [1] and not host.begun
    host.accept()
    assert calls == [{"diameter": 6.0}, {"diameter": 6.0}]
    assert finished == [1]


@pytest.fixture
def quiet_measure_flow(flow: Any) -> Any:
    """Echte Sitzung und Platzierung mit zwei lesbaren Fachfeldern, ohne Hauptfenster."""
    from PySide6.QtCore import QSignalBlocker
    from PySide6.QtWidgets import QFormLayout

    from app.ui.labels import LengthSpin
    from app.ui.placement_flow import QuietHost

    original, session, viewport, _dialog = flow
    original.dispose()
    object_id = original.inputs_of()[0]
    spec = REGISTRY.get("drill_hole")
    during: list[Any] = []

    def take(values: Any) -> bool:
        before = controller._surface
        assert controller.active and host.committing
        success = session.apply(
            spec.title, [OperationDraft(op=spec.name, inputs=(object_id,), params=values)]
        )
        # projectChanged ist bereits gesendet, der Callback aber noch nicht fertig.
        during.append((controller.active, controller._surface is before, host.committing))
        return success

    host = QuietHost(
        {"diameter": 5.0, "depth": 4.0}, take, known=[field.name for field in spec.params.spec()]
    )
    window = SimpleNamespace(
        viewport=viewport, session=session, _clear_preview=session.cancel_preview
    )
    controller = PlacementFlow(host, window, lambda: spec, lambda: (object_id,))
    group = QWidget()
    layout = QFormLayout(group)
    fields = {name: LengthSpin(group) for name in ("diameter", "depth")}
    for name, field in fields.items():
        field.set_range_mm(0.1, 30.0)
        field.set_value_mm(host.values()[name])
        field.setKeyboardTracking(False)
        field.setAccessibleName(name)
        layout.addRow(name, field)
        field.valueChangedMm.connect(lambda value, key=name: host.take_placement({key: value}))

    def interpret() -> bool:
        valid = all(field.hasAcceptableInput() for field in fields.values())
        for field in fields.values():
            if field.hasAcceptableInput():
                field.interpretText()
        if valid:
            host.take_placement({name: field.value_mm() for name, field in fields.items()})
        return valid

    def refresh(values: Any) -> None:
        for name, field in fields.items():
            if field.hasFocus() or field.lineEdit().isModified():
                continue
            with QSignalBlocker(field):
                field.set_value_mm(values[name])

    controller.set_measure_fields(
        group, editors=fields.values(), interpret=interpret, refresh=refresh
    )
    host.valuesChanged.connect(lambda: host.block_apply("Die Vorschau wird berechnet."))
    try:
        viewport.show()
        controller.start()
        assert session.wait_for_idle(30_000)
        _point(controller, session)
        host.block_apply(None)
        yield controller, session, viewport, host, group, fields, during
    finally:
        controller.dispose()
        assert session.wait_for_idle(30_000)
        host.deleteLater()


def test_measure_fields_wait_for_a_second_enter_and_commit_all_texts(
    quiet_measure_flow: Any,
) -> None:
    """Frühes Enter liest beide Texte; erst ein neuer Klick nach Freigabe schreibt einen Schritt."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    controller, session, _viewport, host, _group, fields, during = quiet_measure_flow
    before = len(session.project.document.ops)
    assert not host.begun
    assert host.requires_displayed_preview and not host.preview_required
    for name, text in (("diameter", "6"), ("depth", "7")):
        editor = fields[name].lineEdit()
        editor.selectAll()
        QTest.keyClicks(editor, text)
    QTest.keyClick(fields["depth"].lineEdit(), Qt.Key.Key_Return)
    assert host.begun and controller.active
    assert host.values()["diameter"] == pytest.approx(6.0)
    assert host.values()["depth"] == pytest.approx(7.0)
    # Das frühe Enter wartet auf das Werkzeug (``5a90d4361``, Kunde Weg b) —
    # und schreibt trotzdem keinen Schritt, solange die Pflicht zur gezeigten
    # Vorschau nicht erfüllt ist: Die prüft :meth:`accept` selbst.
    assert controller._accept_pending
    assert session.wait_for_idle(30_000)
    for _ in range(20):
        QApplication.processEvents()
    assert len(session.project.document.ops) == before
    assert controller.active and not during
    host.block_apply(None)
    QTest.keyClick(fields["depth"].lineEdit(), Qt.Key.Key_Return)
    assert during == [(True, True, True)]
    assert not controller.active and not host.begun
    assert session.wait_for_idle(30_000)
    assert len(session.project.document.ops) == before + 1
    step = session.project.document.ops[-1]
    assert step.op == "drill_hole"
    assert step.params["diameter"] == pytest.approx(6.0)
    assert step.params["depth"] == pytest.approx(7.0)
    session.undo()
    assert session.wait_for_idle(30_000)
    assert len(session.project.document.ops) == before


def test_refused_measure_commit_keeps_the_flow_and_its_fields(
    quiet_measure_flow: Any, monkeypatch: Any
) -> None:
    """Eine fachliche Absage verliert weder die Fläche noch die aktive Feldgruppe."""
    controller, session, _viewport, host, group, _fields, _during = quiet_measure_flow
    before = len(session.project.document.ops)
    surface = controller._surface
    finished: list[int] = []
    host.finished.connect(finished.append)
    host.begin_edit()
    monkeypatch.setattr(host, "_accepted", lambda _values: False)
    controller._measure_accept.click()
    assert controller.active and host.begun
    assert controller._surface is surface and controller._measure_group is group
    assert group.isVisibleTo(controller._measure_box)
    assert not finished and len(session.project.document.ops) == before
    assert controller._measure_accept.isEnabled()


@pytest.mark.parametrize("replace_document", [False, True], ids=["same-document", "new-document"])
def test_document_change_inside_a_refused_callback_still_invalidates_the_draft(
    quiet_measure_flow: Any, monkeypatch: Any, replace_document: bool
) -> None:
    """Nur die erfolgreiche eigene Änderung darf den Entwurf bis zum Abschluss behalten."""
    controller, session, _viewport, host, _group, _fields, _during = quiet_measure_flow
    during: list[bool] = []

    def changed_but_refused(_values: Any) -> bool:
        if replace_document:
            session.start_new()
        else:
            session.apply("Körper", [OperationDraft(op="create_box")])
        during.append(controller.active)
        return False

    host.begin_edit()
    monkeypatch.setattr(host, "_accepted", changed_but_refused)
    controller.accept()
    assert during == [not replace_document]
    assert not controller.active and not host.begun


def test_measure_fields_keep_draft_on_tab_camera_and_release_but_escape_discards(
    quiet_measure_flow: Any,
) -> None:
    """Navigation schreibt nichts; Escape verwirft auch während der Werkzeugrechnung."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    controller, session, viewport, host, _group, fields, during = quiet_measure_flow
    before = len(session.project.document.ops)
    editor = fields["diameter"].lineEdit()
    QTest.mouseClick(editor, Qt.MouseButton.LeftButton)
    editor.selectAll()
    QTest.keyClicks(editor, "6")
    QTest.keyClick(editor, Qt.Key.Key_Tab)
    viewport.cameraMoved.emit()
    controller._frozen = True
    controller.pointer(PointerEvent("release", 320, 240, button="left"))
    assert session.wait_for_idle(30_000)
    assert host.begun and controller.active and not during
    assert len(session.project.document.ops) == before
    editor.selectAll()
    QTest.keyClicks(editor, "7")
    QTest.keyClick(editor, Qt.Key.Key_Return)
    # Die Eingabetaste gleich nach der letzten Ziffer wartet auf das Werkzeug,
    # statt still zu verfallen (``5a90d4361``, Durchsicht 0.5.1, Kunde Weg b);
    # Escape nimmt auch den wartenden Abschluss mit.
    assert controller._accept_pending
    QTest.keyClick(editor, Qt.Key.Key_Escape)
    assert not controller._accept_pending
    assert not controller.active and not host.begun
    assert not controller._watched and not controller._field_targets
    assert session.wait_for_idle(30_000)
    assert len(session.project.document.ops) == before and not during
    assert controller._tool is None and viewport.pointer is None


def test_measure_field_replacement_removes_the_old_editor_filters(quiet_measure_flow: Any) -> None:
    """Ein ersetztes oder zerstörtes Feld kann den weiterlebenden Entwurf nicht mehr beginnen."""
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QVBoxLayout

    from app.ui.labels import LengthSpin

    controller, _session, _viewport, host, _group, fields, _during = quiet_measure_flow
    previous = fields["diameter"]
    replacement = QWidget()
    layout = QVBoxLayout(replacement)
    current = LengthSpin(replacement)
    layout.addWidget(current)
    controller.set_measure_fields(
        replacement, editors=[current], interpret=lambda: True, refresh=lambda _values: None
    )
    assert previous not in controller._watched
    assert previous not in controller._field_targets
    current.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    assert current not in controller._watched
    assert current not in controller._field_targets
    assert not host.begun


@pytest.mark.parametrize("size,point_size", [((900, 650), 14), ((1200, 850), 22)])
def test_measure_group_keeps_scope_below_its_controls_and_inside_the_view(
    quiet_measure_flow: Any, size: tuple[int, int], point_size: int
) -> None:
    """Große Schrift und lange Gruppenbeschriftung verdrängen keine erreichbaren Knöpfe."""
    from PySide6.QtCore import QPoint, QRect
    from PySide6.QtWidgets import QCheckBox

    controller, _session, viewport, _host, group, fields, _during = quiet_measure_flow
    scope = QCheckBox("Auf alle vier gleichartigen Bohrungen anwenden", group)
    controller.set_measure_fields(
        group,
        editors=fields.values(),
        interpret=controller._measure_interpret,
        refresh=controller._measure_refresh,
        scope=scope,
    )
    font = controller._measure_box.font()
    font.setPointSize(point_size)
    controller._measure_box.setFont(font)
    viewport.resize(*size)
    QApplication.processEvents()
    controller.redraw()
    # Die Kantenmaße sitzen seit der Bezugswahl (20.09.2026) in ihren Boxen;
    # im Bild verteilt werden die Boxen, ihre Felder liegen darin bei (0, 0).
    widgets = [controller._measure_box, *controller._reference_boxes[:2]]
    visible = [widget for widget in widgets if widget.isVisibleTo(viewport)]
    for widget in visible:
        assert viewport.rect().contains(widget.geometry()), (widget.objectName(), widget.geometry())
    for index, first in enumerate(visible):
        for second in visible[index + 1 :]:
            assert not first.geometry().intersects(second.geometry())
    button = controller._measure_cancel
    assert (
        scope.mapTo(viewport, QPoint()).y() > button.mapTo(viewport, QPoint(0, button.height())).y()
    )
    for child in (scope, controller._measure_accept, button):
        rectangle = QRect(child.mapTo(controller._measure_box, QPoint()), child.size())
        assert controller._measure_box.rect().contains(rectangle)
    assert scope in controller._field_targets
    controller.dispose()
    assert scope not in controller._watched


def test_a_measure_group_that_fits_shows_every_row_without_a_scroll_bar(
    quiet_measure_flow: Any,
) -> None:
    """Passt die Gruppe ins Bild, rollt sie nicht (Fensterabnahme 04.10.2026, RM-197).

    Am echten Fenster stand die Karte *Bohrung ändern* mit Rollbalken, die Zeile
    *Materialtoleranz* halb abgeschnitten und „Nur Bohrungsdurchmesser“ gekürzt,
    obwohl darunter das halbe Bild frei war: Die Höhe war für die volle Breite
    gerechnet, der Rollbalken nahm die Breite weg, die umbrechenden Beschriftungen
    wurden höher — und der Balken blieb, weil er sich selbst begründete.
    """
    from PySide6.QtWidgets import QFormLayout, QLabel

    controller, _session, viewport, _host, _group, _fields, _during = quiet_measure_flow
    group = QWidget()
    layout = QFormLayout(group)
    editors = []
    for index in range(7):
        label = QLabel(f"Beschriftung {index}, die umbricht, sobald es eng wird", group)
        label.setWordWrap(True)
        field = LengthSpin(group)
        field.set_value_mm(float(index))
        layout.addRow(label, field)
        editors.append(field)
    controller.set_measure_fields(
        group,
        editors=editors,
        interpret=lambda: True,
        refresh=lambda _values: None,
    )
    viewport.resize(1600, 1000)
    for _round in range(5):
        QApplication.processEvents()
        controller.redraw()
    scroll = controller._measure_scroll
    assert controller._measure_box.isVisibleTo(viewport)
    assert not scroll.verticalScrollBar().isVisibleTo(scroll), "die Gruppe passt und rollt doch"
    assert group.height() <= scroll.viewport().height(), (group.height(), scroll.viewport().size())


def test_a_measure_group_with_room_shows_its_choices_whole(quiet_measure_flow: Any) -> None:
    """Eine schmal gehaltene Auswahl zeigt in der Karte ihren ganzen Eintrag.

    ``panels.column_choice`` hält die Auswahl in der Spalte rechts schmal
    (RM-488); in der Karte im Bild ist dafür Platz, und dort stand am echten
    Fenster „Nur Bohrungsdurchm…“ (Fensterabnahme 04.10.2026). Die Karte nimmt
    die Breite, die der längste Eintrag braucht, solange das Bild sie hat.
    """
    from PySide6.QtWidgets import QComboBox, QFormLayout, QStyle, QStyleOptionComboBox

    from app.ui.panels import column_choice

    controller, _session, viewport, _host, _group, _fields, _during = quiet_measure_flow
    group = QWidget()
    layout = QFormLayout(group)
    field = LengthSpin(group)
    layout.addRow("Durchmesser", field)
    combo = column_choice(QComboBox(group))
    for text in ("Nur Bohrungsdurchmesser", "Senkung, Stufen und Verengung mitnehmen"):
        combo.addItem(text)
    layout.addRow("Änderungsumfang", combo)
    controller.set_measure_fields(
        group, editors=[field], interpret=lambda: True, refresh=lambda _values: None
    )
    viewport.resize(1600, 1000)
    for _round in range(5):
        QApplication.processEvents()
        controller.redraw()
    option = QStyleOptionComboBox()
    combo.initStyleOption(option)
    metrics = combo.fontMetrics()
    longest = max(metrics.horizontalAdvance(combo.itemText(i)) for i in range(combo.count()))
    needed = combo.style().sizeFromContents(
        QStyle.ContentsType.CT_ComboBox, option, QSize(longest, metrics.height()), combo
    )
    assert combo.width() >= needed.width(), (combo.width(), needed.width())


def test_quiet_host_keeps_permission_for_identical_known_values(qt_app: QApplication) -> None:
    """Nur echte Wertänderungen verwerfen die Freigabe; gesperrt endet nichts."""
    from app.ui.placement_flow import QuietHost

    accepted: list[Any] = []
    finished: list[int] = []
    changes: list[Any] = []

    def take(values: Any) -> bool:
        accepted.append(values)
        return True

    host = QuietHost({"diameter": 5.0}, take, known={"diameter"})
    host.finished.connect(finished.append)

    def changed() -> None:
        changes.append(host.values())
        host.block_apply("Die Vorschau wird berechnet. Bitte das Ergebnis abwarten.")

    host.valuesChanged.connect(changed)
    host.take_placement({"diameter": 6.0, "nx": 1.0})
    assert changes == [{"diameter": 6.0}]
    assert not host.can_accept()
    host.accept()
    assert not accepted and not finished
    host.block_apply(None)
    host.take_placement({"diameter": 6.0, "nx": 0.0})
    assert changes == [{"diameter": 6.0}]
    assert host.can_accept()
    host.preview_check = lambda: False
    host.accept()
    assert not accepted and not finished
    host.preview_check = None
    host.accept()
    assert accepted == [{"diameter": 6.0}]
    assert finished == [1]


@pytest.mark.parametrize("preview_required", [False, True], ids=["mesh", "protected-preview"])
def test_the_flow_runs_on_a_host_without_a_window(
    qt_app: QApplication, preview_required: bool
) -> None:
    """Dieselbe Platzierung, nur ohne Dialog darunter.

    `PlacementFlow` hing an einem `OperationDialog`: Er war sein Qt-Elternteil,
    lieferte die Werte, nahm sie zurück und führte am Ende aus. Am gewählten
    Merkmal soll kein Dialog mehr aufgehen — seine Zahlen stehen rechts im
    Merkmalfenster (Robert, 11.09.2026: „werte im dialog und in der rechten
    merkmalleiste doppelt, sehr verwirrend für den Kunden").

    Geprüft wird der **Vertrag an der Sache**, nicht am Namen: Ein `QuietHost`
    trägt eine echte Platzierung von ihrem Start bis zum Übernehmen, und was
    dabei herauskommt, sind dieselben Werte. Ein Protokoll ohne zweiten
    Erfüller wäre Zierat — diese Zeilen sind sein Beleg.
    """
    from app.ui.placement_flow import PlacementHost, QuietHost

    session = Session()
    viewport = PlacementViewport()
    controller: PlacementFlow | None = None
    übernommen: list[Any] = []
    try:
        session.import_model(Path(__file__).parent / "data/meshes/cube_clean.stl")
        assert session.wait_for_idle(30_000)
        result = session.last_result
        assert result is not None and result.complete
        viewport.show_scene(result)
        session.sceneChanged.connect(viewport.show_scene)
        object_id, entry = next(iter(result.scene.objects.items()))
        face = int(np.argmax(entry.mesh.raw.face_normals[:, 2]))
        viewport.hit = object_id, tuple(entry.mesh.raw.triangles_center[face]), face, None
        spec = REGISTRY.get("drill_hole")

        def take(values: Any) -> bool:
            übernommen.append(values)
            return True

        host = QuietHost({"diameter": 5.0, "depth": 4.0}, take)
        host.preview_required = preview_required
        if preview_required:
            host.valuesChanged.connect(
                lambda: host.block_apply(
                    "Die Vorschau wird berechnet. Bitte das Ergebnis abwarten."
                )
            )
        assert isinstance(host, PlacementHost), "der Träger erfüllt den Vertrag"
        assert not host.isVisible(), "und zeigt nie ein Fenster"

        window = SimpleNamespace(
            viewport=viewport, session=session, _clear_preview=session.cancel_preview
        )
        controller = PlacementFlow(host, window, lambda: spec, lambda: (object_id,))
        controller.start()
        assert session.wait_for_idle(30_000)
        assert controller.active, "die Platzierung läuft auch ohne Dialog"

        _point(controller, session)
        assert controller._surface is not None, "die Trägerfläche steht"
        assert host.values()["diameter"] == pytest.approx(5.0), "die Werte kommen vom Träger"
        # Der Ort wandert hinein wie beim Dialog — über `take_placement`, und
        # zwar als die Felder, die das Schema führt (`x`, `y`, `z`), nicht als
        # ein Tripel: Die Vorgabe kannte sie nicht, der Zug hat sie gesetzt.
        assert {"x", "y", "z"} <= set(host.values()), "die Stelle wandert zurück"

        controller._deepening = True
        controller._depth_set = True
        host.take_placement({"diameter": 6.0})
        assert controller._tool_busy, "die neue Größe wird noch vorbereitet"
        controller.accept()
        # Der frühe Klick wartet auf das Werkzeug — auch dort, wo eine gezeigte
        # Vorschau Pflicht ist; die Pflicht prüft danach :meth:`accept` selbst
        # (Durchsicht 0.5.1, Kunde Weg b).
        assert controller._accept_pending
        assert session.wait_for_idle(30_000)
        if preview_required:
            assert not übernommen and controller.active
            surface = controller._surface
            controller.accept()
            assert not übernommen and controller.active and controller._surface is surface
            host.block_apply(None)
            controller.accept()
        assert übernommen, "das Übernehmen erreicht den Rückruf"
        assert übernommen[-1]["diameter"] == pytest.approx(6.0)
        assert not controller.active
    finally:
        if controller is not None:
            controller.dispose()
        session.release(30_000)
        viewport.close()
        qt_app.processEvents()


def test_measure_group_has_the_only_apply_and_cancel_controls(qt_app: QApplication) -> None:
    """Die Maßgruppe und der gemeinsame Abschluss bleiben bei geschlossenem Panel nutzbar."""
    from PySide6.QtTest import QTest

    from app.ui.labels import LengthSpin

    window = _window_with_a_renderer()
    try:
        window.feature_dock.hide()
        _a_selected_hole(window)
        flow = _measures_in_the_view(window)
        assert flow is not None and flow.active
        assert not flow._bar.isVisibleTo(window.viewport)
        assert window.feature_panel._apply.isHidden() and window.feature_panel._cancel.isHidden()
        field = flow._measure_group.findChildren(LengthSpin)[0]
        editor = field.lineEdit()
        # Getippt wird, wie der Kunde tippt: mit dem Dezimalzeichen der Sprache.
        # ``str(5.7)`` liefert einen Punkt, und der fällt in einer deutschen
        # Anzeige aus dem Feld — übrig blieb „57000“ Millimeter.
        diameter = round(field.value_mm() + 0.5, 2)
        editor.selectAll()
        QTest.keyClicks(editor, QLocale().toString(diameter, "f", 2))
        # Ohne Eingabetaste: Die übernimmt seit ``5a90d4361`` selbst, sobald
        # Werkzeug und Vorschau stehen (Kunde Weg b). Geprüft wird hier der
        # Knopf der Maßgruppe bei geschlossenem Panel.
        assert flow.dialog.begun and flow.active
        before = len(window.session.project.document.ops)
        _display_measure_preview(window, flow)
        window.feature_dock.show()
        window.feature_dock.close()
        assert flow.active and window._quiet_placement is flow
        assert window.viewport.is_difference_applied(window._preview_approval.difference)
        flow._measure_accept.click()
        assert window.session.wait_for_idle(30_000)
        assert len(window.session.project.document.ops) == before + 1
        assert window.session.project.document.ops[-1].params["diameter"] == pytest.approx(diameter)
    finally:
        window.end_quiet_placement()
        QApplication.processEvents()
        window.release()


def test_a_slot_drag_puts_its_numbers_into_the_panel(qt_app: QApplication) -> None:
    """Der Zug am Langlochgriff schreibt nach rechts, nicht in eine Leiste.

    Bis zum 11.09.2026 ging er in eine eigene Leiste unten mit Länge,
    Richtung, Abbrechen und Übernehmen — dieselben zwei Zahlen, die rechts
    unter *Zum Langloch ziehen* stehen, und ein zweites Übernehmen daneben
    (Robert: „auch 2 mal übernehmen einmal unten und einmal rechts … die
    untere leiste uns sparen und nur die rechte verwenden mit dem was schon
    drin ist").

    Geprüft wird die ganze Kette: Der Zug schlägt vor, die Felder nehmen an,
    und **derselbe** Knopf rechts macht daraus einen Schritt. Ohne das letzte
    Stück wäre der Zug eine Sackgasse.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.ui.labels import LengthSpin
    from app.ui.op_dialog import OperationDialog

    window = _window_with_a_renderer()
    try:
        _a_selected_hole(window)
        # Seit die Maße mit der Auswahl kommen (20.09.2026), stehen die zwei
        # Knöpfe mit ihnen — der gesperrte Bewegungsgriff nimmt sie nicht mit
        # (Robert, 21.09.2026: „wo sind eigentlich die markierungen um es zum
        # langloch zu ziehen?").
        assert window.viewport._slot_handle is not None, "die Maße bringen die Knöpfe mit"
        assert window.viewport._gizmo is None, "aber keinen zweiten Satz Pfeile"
        # ``isHidden`` statt ``isVisible``: Das Fenster ist offscreen nie gezeigt.
        flow = _choose_measure_action(window, "slot_hole")
        assert flow is not None and flow.active
        for _ in range(20):
            QApplication.processEvents()
        handle = window.viewport._slot_handle
        assert handle is not None, "mit dem Knopf stehen die zwei Knöpfe"

        vorher = [step.op for step in window.session.project.document.ops]
        handle._release(12.0, 0.0)
        QApplication.processEvents()

        assert window.viewport.slot_drag_waits(), "der Zug wartet auf seine Bestätigung"
        assert [step.op for step in window.session.project.document.ops] == vorher, (
            "und schreibt bis dahin nichts"
        )
        armed = window.feature_panel._runs.get(window.feature_panel._armed or "")
        assert armed is not None and armed.op == "slot_hole", "die Handlung des Zugs steht scharf"

        _display_measure_preview(window, flow)
        assert flow._measure_box.isVisibleTo(window.viewport)
        editor = flow._measure_group.findChildren(LengthSpin)[0].lineEdit()
        QTest.keyClick(editor, Qt.Key.Key_Return)
        window.session.wait_for_idle()
        for _ in range(60):
            QApplication.processEvents()
        nachher = [step.op for step in window.session.project.document.ops]
        assert nachher == [*vorher, "slot_hole"], f"Enter übernimmt denselben Entwurf: {nachher}"
    finally:
        window.end_quiet_placement()
        for dialog in window.findChildren(OperationDialog):
            dialog.reject()
        QApplication.processEvents()
        window.release()


def _a_selected_plate(window, *, face_normal: tuple[float, float, float] | None = None):
    """Öffnet die Platte und wählt sie — oder eine ihrer Flächen nach Normale."""
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    window.object_tree.select_object(object_id)
    if face_normal is not None:
        face = next(
            identifier
            for identifier, feature in entry.features.items()
            if feature.kind == "face"
            and all(
                abs(float(a) - b) < 0.1
                for a, b in zip(feature.params["normal"], face_normal, strict=True)
            )
        )
        window.object_tree.select_feature(object_id, face)
    window.session.wait_for_idle()
    for _ in range(40):
        QApplication.processEvents()
    return object_id, entry


def _a_part_placement(window, name: str):
    """Öffnet den Dialog eines Bausteins und wartet, bis seine Platzierung sitzt."""
    import time

    window.run_operation(REGISTRY.get(name))
    for _ in range(20):
        QApplication.processEvents()
    dialog = window._op_dialog
    assert dialog is not None and dialog.spec.name == name
    flow = dialog.placement_flow
    assert flow is not None and flow.active, "ein Baustein geht von selbst in die Platzierung"
    for _ in range(300):
        QApplication.processEvents()
        window.session.wait_for_idle()
        if flow._surface is not None and flow._tool is not None:
            break
        time.sleep(0.02)
    assert flow._surface is not None and flow._tool is not None, (
        "Die Bausteinplatzierung lieferte vor Ablauf der Wartezeit weder Fläche noch Werkzeug."
    )
    for _ in range(20):
        QApplication.processEvents()
    return dialog, flow


def test_a_part_sits_on_the_top_face_at_once_and_carries_a_grip(qt_app: QApplication) -> None:
    """Ein Baustein an einem gewählten Körper steht sofort im Bild — mit Griff.

    Bis zum 11.09.2026 zeigte die Platzierung ihn erst unter dem Zeiger über
    einer Fläche; mit gewähltem Körper und der Maus daneben stand nichts im
    Bild, und *Übernehmen* schrieb einen roten Schritt ohne Position (Robert:
    „im viewport gab es weder vorschau, noch das gizmo dazu"). Jetzt sitzt er
    auf der größten Fläche, die nach oben zeigt — der Oberseite —, die Felder
    tragen die Stelle, und am Körper hängt der Bewegungsgriff.

    **Gemessen über alle 24 einsetzbaren Bausteine** (Sonde, 11.09.2026):
    jeder saß auf (0 | 0 | 8) mit Griff. Hier steht einer davon stellvertretend
    — die Regel liegt im Fluss, nicht im Baustein.
    """
    window = _window_with_a_renderer()
    try:
        _object_id, entry = _a_selected_plate(window)
        top = float(entry.mesh.bounds.maximum[2])
        dialog, flow = _a_part_placement(window, "insert_wall_mount")

        assert flow._surface is not None, "die Stelle steht ohne Klick"
        assert flow._surface.point[2] == pytest.approx(top, abs=0.01), "auf der Oberseite"
        assert flow._frozen and flow._seated_by_default
        values = dialog.values()
        assert (values["x"], values["y"], values["z"]) == pytest.approx(
            (0.0, 0.0, top), abs=0.05
        ), "die Felder kennen die Stelle — Übernehmen schreibt keinen roten Schritt mehr"
        assert flow._tool is not None and flow._tool.visible(), "der Körper steht im Bild"
        assert window.viewport._placement_grip is not None, "und der Griff daran"
        assert window.viewport._gizmo is None, "kein zweiter Griff der Auswahl darunter"
        assert "Klick: umsetzen" in flow._note.text(), (
            "der Satz sagt, was hier anders ist: Griff verschiebt, Klick setzt um"
        )
    finally:
        for dialog in window.findChildren(OperationDialog):
            dialog.reject()
        QApplication.processEvents()
        window.release()


def test_a_part_for_a_hole_sits_in_the_chosen_hole(qt_app: QApplication) -> None:
    """Eine gewählte Bohrung, ein Baustein für Bohrungen — er sitzt darin.

    Einpressbuchse, Mutternfalle, Lagersitz und Gewinde gehören *in* eine
    Bohrung, die gedruckte Schraube nirgends sonst. Bis zum 14.09.2026 saß
    jeder von ihnen trotzdem auf der Mitte der Deckfläche, obwohl ``hole_1``
    angeklickt war: Der Sitz von selbst fragte nur nach Flächen, und die
    gewählte Bohrung wurde dabei stumm aus ``at_feature`` geräumt (Sonde über
    alle fünf, 14.09.2026). Jetzt liefert ``seat_of`` die Mündung — derselbe
    Weg wie bei *Bohrung ändern* — und der Satz sagt, wo der Baustein sitzt.
    """
    window = _window_with_a_renderer()
    try:
        object_id, hole = _a_selected_hole(window)
        result = window.session.last_result
        assert result is not None
        centre = result.scene.objects[object_id].features[hole].params["centre"]
        dialog, flow = _a_part_placement(window, "insert_heatset_m4")

        assert flow._surface is not None
        assert flow._surface.point[:2] == pytest.approx(
            (float(centre[0]), float(centre[1])), abs=0.05
        ), "in der Bohrung, nicht auf der Flächenmitte"
        values = dialog.values()
        assert (values["x"], values["y"]) == pytest.approx(
            (float(centre[0]), float(centre[1])), abs=0.05
        ), "die Felder kennen die Bohrung"
        assert flow._seated_by_default, "ein Klick setzt um, er übernimmt nicht"
        assert window.viewport._placement_grip is not None, "mit Griff"
        assert flow._note.text().startswith("Sitzt in der Bohrung"), flow._note.text()
    finally:
        for dialog in window.findChildren(OperationDialog):
            dialog.reject()
        QApplication.processEvents()
        window.release()


def test_a_screw_hole_on_a_chosen_hole_stays_on_the_face(qt_app: QApplication) -> None:
    """Ein Baustein, der nicht in Bohrungen gehört, folgt der Bohrung nicht.

    Ein Schraubenloch auf eine Bohrung zu setzen ergäbe ein Loch im Loch;
    dort bleibt der Sitz auf der größten Fläche nach oben — wie bisher.
    """
    window = _window_with_a_renderer()
    try:
        object_id, hole = _a_selected_hole(window)
        result = window.session.last_result
        assert result is not None
        centre = result.scene.objects[object_id].features[hole].params["centre"]
        _dialog, flow = _a_part_placement(window, "insert_screw_hole")
        assert flow._surface is not None
        assert flow._surface.point[:2] != pytest.approx(
            (float(centre[0]), float(centre[1])), abs=0.05
        )
        assert flow._note.text().startswith("Sitzt auf der Fläche"), flow._note.text()
    finally:
        for dialog in window.findChildren(OperationDialog):
            dialog.reject()
        QApplication.processEvents()
        window.release()


def test_a_part_sits_on_the_selected_face_and_the_selection_grip_comes_back(
    qt_app: QApplication,
) -> None:
    """Ist eine Fläche gewählt, sitzt der Baustein auf ihr — nicht auf der Oberseite.

    Und der Griff der Auswahl, der an der Fläche stand, geht, solange der
    Griff am Baustein steht: Beide säßen an derselben Stelle. Nach Escape
    kommt er zurück.
    """
    window = _window_with_a_renderer()
    try:
        _a_selected_plate(window, face_normal=(0.0, -1.0, 0.0))
        window.viewport.set_gizmo(True)
        QApplication.processEvents()
        assert window.viewport._gizmo is not None, "an der gewählten Fläche steht der Griff"

        _dialog, flow = _a_part_placement(window, "insert_foot")
        assert flow._surface is not None
        assert flow._surface.point[1] == pytest.approx(-25.0, abs=0.01), "auf der Vorderseite"
        assert window.viewport._placement_grip is not None
        assert window.viewport._gizmo is None, "der Griff der Auswahl weicht dem am Baustein"

        flow.back()
        QApplication.processEvents()
        assert window.viewport._placement_grip is None, "Escape nimmt den Griff am Baustein"
        assert window.viewport._gizmo is not None, "und der Griff der Auswahl steht wieder"
    finally:
        for dialog in window.findChildren(OperationDialog):
            dialog.reject()
        QApplication.processEvents()
        window.release()


def test_the_part_grip_moves_the_place_and_a_click_replaces_before_it_applies(
    qt_app: QApplication,
) -> None:
    """Der Zug am Griff setzt den Baustein um; ein Klick setzt um, statt zu übernehmen.

    Der Griff liefert die Matrix des Körpers nach dem Zug; ihre Verschiebung
    ist die neue Stelle, und Felder und Maßlinien folgen (``move_to``). Ein Zug
    neben die Fläche lässt alles stehen. **Ein Klick bestätigt eine Stelle
    nicht, die niemand gewählt hat**: Nach dem Sitz von selbst setzt er um —
    erst der Klick danach übernimmt, wie nach jeder geklickten Platzierung.
    """
    import time

    import numpy as np

    from app.ui.render.api import Pick, PointerEvent

    window = _window_with_a_renderer()
    try:
        object_id, entry = _a_selected_plate(window)
        top = float(entry.mesh.bounds.maximum[2])
        dialog, flow = _a_part_placement(window, "insert_wall_mount")
        grip = window.viewport._placement_grip
        assert grip is not None

        matrix = np.asarray(grip.target.matrix(), dtype=float).copy()
        matrix[:3, 3] += (10.0, 5.0, 0.0)
        window.viewport._on_placement_grip_released(matrix)
        QApplication.processEvents()
        assert flow._surface is not None
        assert flow._surface.point[:2] == pytest.approx((10.0, 5.0), abs=0.05), "der Zug setzt um"
        values = dialog.values()
        assert (values["x"], values["y"]) == pytest.approx((10.0, 5.0), abs=0.05), (
            "die Felder folgen"
        )
        assert window.viewport._placement_grip is not grip, "der Griff hängt frisch am neuen Ort"

        matrix = np.asarray(window.viewport._placement_grip.target.matrix(), dtype=float).copy()
        matrix[:3, 3] += (500.0, 0.0, 0.0)
        window.viewport._on_placement_grip_released(matrix)
        QApplication.processEvents()
        assert flow._surface.point[:2] == pytest.approx((10.0, 5.0), abs=0.05), (
            "neben der Fläche bleibt alles stehen"
        )

        # Ein Klick auf die Platte: setzt um, kein Schritt.
        steps = len(window.session.history.operations)
        renderer = window.viewport.renderer
        hit = (-20.0, -10.0, top)
        x, y, _depth = renderer.world_to_display(hit)
        x, y = round(x), round(y)
        cell = int(np.argmax(np.asarray(entry.mesh.raw.face_normals)[:, 2]))
        renderer.picks[(x, y)] = Pick(hit, window.viewport._actors[object_id], cell)
        for event in (
            PointerEvent("move", x, y),
            PointerEvent("press", x, y, button="left"),
            PointerEvent("release", x, y, button="left"),
        ):
            window.viewport._on_pointer(event)
        for _ in range(200):
            # Der Klick geht über den Zeitgeber des Flusses — der braucht Zeit.
            QApplication.processEvents()
            window.session.wait_for_idle()
            if flow._surface is not None and abs(flow._surface.point[0] + 20.0) < 0.5:
                break
            time.sleep(0.02)
        assert flow._surface is not None
        assert flow._surface.point[:2] == pytest.approx((-20.0, -10.0), abs=0.05), (
            "der erste Klick setzt um"
        )
        assert len(window.session.history.operations) == steps, "und übernimmt nicht"
        assert not flow._seated_by_default, "ab jetzt hat jemand geklickt"
    finally:
        for dialog in window.findChildren(OperationDialog):
            dialog.reject()
        QApplication.processEvents()
        window.release()


def _a_pulled_slot(window):
    """Bohrung gewählt, Maße im Bild, Langloch auf 18 gezogen — der wartende Zug."""
    from app.ui.render.api import PointerEvent

    _, hole = _a_selected_hole(window)
    flow = _choose_measure_action(window, "slot_hole")
    assert flow is not None and flow.active
    for _ in range(200):
        QApplication.processEvents()
        window.session.wait_for_idle()
        if flow._tool_context is not None:
            break
    handle = window.viewport._slot_handle
    assert handle is not None
    renderer = window.viewport.renderer
    seat = renderer.world_to_display(handle.knob_seats[0])
    x, y = round(seat[0]), round(seat[1])
    renderer.item_picks[(x, y)] = handle.knobs[0]
    for event in (
        PointerEvent("move", x, y),
        PointerEvent("press", x, y, button="left"),
        PointerEvent("move", x + 12, y, buttons=frozenset({"left"})),
        PointerEvent("release", x + 12, y, button="left"),
    ):
        window.viewport._on_pointer(event)
    QApplication.processEvents()
    assert window.viewport.slot_drag_waits()
    return hole, flow


def _span_of(item) -> tuple[float, float]:
    import numpy as np

    points = np.asarray(item.points, dtype=float)
    extent = points.max(axis=0) - points.min(axis=0)
    return float(extent[0]), float(extent[1])


def test_the_ring_about_the_axis_turns_the_slot_and_its_mark(qt_app: QApplication) -> None:
    """Der Ring um die Bohrachse dreht das Langloch — Marke und Griff drehen mit.

    Bis zum 11.09.2026 drehte der Ring nur die Griffscheibe; Umriss, Knöpfe
    und Marke blieben stehen, und das Loslassen schlug *Merkmal drehen* vor —
    eine Kippung der Achse, die niemand gemeint hat (Robert: „bei gizmo vom
    langloch dreht sich die vorschau vom langloch noch nicht"). Jetzt ist der
    Ring um die Achse dasselbe wie ein Zug an den Knöpfen: Während des Zugs
    folgen Griff und Marke, das Loslassen ist ein Vorschlag für *Zum Langloch
    ziehen*, und die Felder rechts tragen die neue Richtung.
    """
    from app.core.geom.transform import rotation_about

    window = _window_with_a_renderer()
    try:
        _hole, _flow = _a_pulled_slot(window)
        handle = window.viewport._slot_handle
        assert handle is not None and handle.angle == pytest.approx(0.0)
        mark = window.viewport._shape_actor
        assert mark is not None
        along, across = _span_of(mark)
        assert along == pytest.approx(handle.length, abs=0.05) and across < along

        gizmo = window.viewport._gizmo
        assert gizmo is not None
        turn = rotation_about((0.0, 0.0, 1.0), gizmo.origin, 30.0)
        window.viewport._on_gizmo_interacted(turn)
        assert handle.angle == pytest.approx(30.0), "der Griff dreht mit dem Ring"
        turned = window.viewport._shape_actor
        assert turned is not None
        x_now, y_now = _span_of(turned)
        assert x_now < along - 1.0 and y_now > across + 1.0, "und die Marke dreht mit"

        window.viewport._on_gizmo_released(turn)
        QApplication.processEvents()
        assert window.viewport.slot_drag_waits(), "der Langlochzug wartet weiter"
        assert window.viewport._slot_waiting is not None
        assert window.viewport._slot_waiting[1] == pytest.approx(30.0), "mit der neuen Richtung"
        armed = window.feature_panel._runs.get(window.feature_panel._armed or "")
        assert armed is not None and armed.op == "slot_hole", (
            "ein Vorschlag für Zum Langloch ziehen"
        )
        again = window.viewport._slot_handle
        assert again is not None and again.angle == pytest.approx(30.0)
    finally:
        window.end_quiet_placement()
        QApplication.processEvents()
        window.release()


def test_a_begun_slot_keeps_its_values_on_model_and_outside_clicks(
    qt_app: QApplication,
) -> None:
    """Modell- und Außenklick erhalten den begonnenen Zug bis zum gemeinsamen Abschluss."""
    import numpy as np

    from app.ui.render.api import Pick

    window = _window_with_a_renderer()
    try:
        hole, flow = _a_pulled_slot(window)
        renderer = window.viewport.renderer
        object_id = window.object_tree.selected()
        assert object_id is not None
        entry = window.session.last_result.scene.objects[object_id]
        feature = entry.features[hole]
        centre = feature.params["centre"]
        hit = (float(centre[0]) + 8.0, float(centre[1]) + 6.0, float(entry.mesh.bounds.maximum[2]))
        x, y, _depth = renderer.world_to_display(hit)
        x, y = round(x), round(y)
        cell = int(np.argmax(np.asarray(entry.mesh.raw.face_normals)[:, 2]))
        renderer.picks[(x, y)] = Pick(hit, window.viewport._actors[object_id], cell)

        window.viewport._on_left_click(x, y)
        QApplication.processEvents()
        assert flow.active, "der Klick auf das Modell lässt die Maße stehen"
        assert window.viewport._selected_feature == hole, "und die Auswahl"
        assert window.viewport.slot_drag_waits(), "und den wartenden Zug"

        window.viewport._on_left_click(5, 5)
        QApplication.processEvents()
        assert flow.active and flow.dialog.begun, "auch außen bleibt der begonnene Entwurf"
        assert window.viewport.slot_drag_waits(), "der wartende Zug bleibt erhalten"
        assert window.viewport._selected_feature == hole
        flow._measure_cancel.click()
        assert not flow.active and not window.viewport.slot_drag_waits()
    finally:
        window.end_quiet_placement()
        QApplication.processEvents()
        window.release()


def test_cancel_below_apply_discards_what_waits(qt_app: QApplication) -> None:
    """Der gemeinsame Abbruch verwirft den Entwurf und hebt die Auswahl auf.

    Bis zum 24.09.2026 blieb die Auswahl stehen, und rechts war die Handlung
    des verworfenen Entwurfs weiter scharf; seither gilt „abbrechen =
    deselektieren" (Robert). Escape geht weiter stufenweise.
    """
    window = _window_with_a_renderer()
    try:
        panel = window.feature_panel
        _, _hole = _a_selected_hole(window)
        # ``isHidden``: die Knopfzeile hängt unter dem Rollbereich des Docks
        # und nicht mehr am Panel (13.09.2026, ``FeaturePanel.footer``).
        assert panel._cancel.isHidden(), "der Abschluss steht ausschließlich an den Maßen"
        _hole, flow = _a_pulled_slot(window)
        assert panel._cancel.isHidden() and panel._apply.isHidden()
        assert not flow._measure_cancel.isHidden(), "ein gemeinsamer Abschluss an den Maßen"
        steps = len(window.session.history.operations)

        flow._measure_cancel.click()
        QApplication.processEvents()
        assert not flow.active, "die Maße im Bild sind zu"
        assert not window.viewport.slot_drag_waits(), "der Zug ist verworfen"
        assert len(window.session.history.operations) == steps, "und gerechnet ist nichts"
        assert window.object_tree.selected() is None, "abbrechen = deselektieren"
        assert window.viewport._selected_feature is None
        assert panel._armed is None and not panel._runs, "rechts steht nichts scharf"
        assert panel._cancel.isHidden(), "der Knopf geht mit den Maßen"
    finally:
        window.end_quiet_placement()
        QApplication.processEvents()
        window.release()


def test_a_drag_at_the_chosen_hole_pulls_the_slot_instead_of_moving_the_body(
    qt_app: QApplication,
) -> None:
    """Wer das gewählte Loch anfasst und zieht, zieht es zum Langloch — nicht den Körper.

    Die Knöpfe kommen mit *Im Bild einstellen*; wer vorher am Loch zog, zog den
    ganzen Körper — im ``solidon``-Schema führt die linke Taste das gewählte
    Teil (Robert, 11.09.2026: „wenn ich jetzt eine bohrung an einer ecke zum
    langloch ziehen will verschiebe ich immer den körper"). Jetzt baut der
    Druck auf das Loch den Griff für diesen Zug, der Zug rechnet wie am Knopf,
    und das Loslassen holt die Maße ins Bild — Knöpfe, Umriss, Griff und der
    Vorschlag rechts stehen wie nach dem Knopf. Daneben bleibt es beim Körper.
    """
    import numpy as np

    from app.ui.render.api import Pick, PointerEvent

    window = _window_with_a_renderer()
    try:
        object_id, hole = _a_selected_hole(window)
        assert window._quiet_placement is not None, "die Auswahl zeigt passive Maße"
        assert window.viewport._slot_handle is not None, "und die Knöpfe stehen am Loch"
        assert window.viewport._gizmo is None, "ohne einen zweiten Satz Pfeile"
        chosen = _choose_measure_action(window, "slot_hole")
        assert chosen is not None and chosen.active
        entry = window.session.last_result.scene.objects[object_id]
        feature = entry.features[hole]
        centre = feature.params["centre"]
        top = (float(centre[0]), float(centre[1]), float(entry.mesh.bounds.maximum[2]))
        renderer = window.viewport.renderer
        x, y, _depth = renderer.world_to_display(top)
        x, y = round(x), round(y)
        # Der Druck landet auf einem Dreieck der Bohrung — so findet
        # ``_feature_at`` das Loch, nicht die Fläche daneben.
        cell = int(feature.face_indices[0])
        renderer.picks[(x, y)] = Pick(top, window.viewport._actors[object_id], cell)
        steps = len(window.session.history.operations)

        for event in (
            PointerEvent("move", x, y),
            PointerEvent("press", x, y, button="left"),
            PointerEvent("move", x + 14, y + 4, buttons=frozenset({"left"})),
            PointerEvent("release", x + 14, y + 4, button="left"),
        ):
            window.viewport._on_pointer(event)
            QApplication.processEvents()
        for _ in range(120):
            QApplication.processEvents()
            window.session.wait_for_idle()

        assert len(window.session.history.operations) == steps, "kein Schritt — der Körper steht"
        assert window.viewport.slot_drag_waits(), "der Zug zum Langloch wartet"
        handle = window.viewport._slot_handle
        assert handle is not None and handle.length > feature.params["diameter"], "gezogen"
        assert handle._outline is not None, "mit Umriss"
        flow = window._quiet_placement
        assert flow is not None and flow.active, "und die Maße sind im Bild — wie nach dem Knopf"
        armed = window.feature_panel._runs.get(window.feature_panel._armed or "")
        assert armed is not None and armed.op == "slot_hole", "rechts wartet der Vorschlag"
        assert np.allclose(window.viewport._actors[object_id].matrix(), np.eye(4)), (
            "der Körper ist nicht verschoben"
        )
    finally:
        window.end_quiet_placement()
        QApplication.processEvents()
        window.release()


def test_a_press_on_the_chosen_hole_places_the_part_that_sits_in_it(
    qt_app: QApplication,
) -> None:
    """Sitzt ein Baustein aus dem Dialog in der gewählten Bohrung, setzt ein Druck aufs Loch ihn um.

    Die Einpressbuchse sitzt in der gewählten Bohrung, die Knöpfe des
    Langlochs stehen nicht (der Dialog hat die Platzierung, nicht die
    Maßgruppe). Seit dem 21.09.2026 galt „Loch ist der Griff" auch hier: Der
    Druck lieh sich einen Langlochgriff, der Zug wuchs zum Langloch, und der
    Fluss bekam nie einen Klick (Sonde ``probe_pull_during_dialog.py``). Das
    Loch ist nur dann der Griff, wenn Knöpfe und Platzierung zusammen da
    sind — oder zusammen fehlen.
    """
    from app.ui.render.api import Pick, PointerEvent

    window = _window_with_a_renderer()
    try:
        object_id, hole = _a_selected_hole(window)
        # Der Dialog übernimmt die Platzierung; die stillen Maße gehen vorher.
        window.end_quiet_placement()
        QApplication.processEvents()
        _dialog, flow = _a_part_placement(window, "insert_heatset_m4")
        viewport = window.viewport
        assert viewport._slot_handle is None and viewport._placement_pointer is not None, (
            "Dialogplatzierung ohne Langlochknöpfe — die Lage, um die es geht"
        )
        entry = window.session.last_result.scene.objects[object_id]
        feature = entry.features[hole]
        centre = feature.params["centre"]
        top = (float(centre[0]), float(centre[1]), float(entry.mesh.bounds.maximum[2]))
        renderer = viewport.renderer
        x, y, _depth = renderer.world_to_display(top)
        x, y = round(x), round(y)
        renderer.picks[(x, y)] = Pick(
            top, viewport._actors[object_id], int(feature.face_indices[0])
        )

        viewport._on_pointer(PointerEvent("press", x, y, button="left"))
        assert viewport._slot_handle is None and not viewport._slot_borrowed, (
            "kein geliehener Langlochgriff — der Druck gehört der Platzierung"
        )
        viewport._on_pointer(PointerEvent("move", x + 14, y + 4, buttons=frozenset({"left"})))
        viewport._on_pointer(PointerEvent("release", x + 14, y + 4, button="left"))
        assert not viewport.slot_drag_waits(), "kein Langlochzug wartet"
        assert flow._pending is not None and flow._pending[:2] == (x + 14, y + 4), (
            "der Fluss setzt den Baustein dorthin, wo losgelassen wurde"
        )
    finally:
        for open_dialog in window.findChildren(OperationDialog):
            open_dialog.reject()
        QApplication.processEvents()
        window.release()


def test_a_redraw_during_a_grip_drag_keeps_the_grip_and_the_drag(qt_app: QApplication) -> None:
    """Wer am Griff zieht, zieht weiter — auch wenn der Fluss dazwischen neu zeichnet.

    Radraste, Vorschau oder ein Overlay, das seine Größe ändert: Jedes davon
    lässt den Fluss neu zeichnen, und ``grip_placement`` baute den Griff bis
    zum 21.09.2026 bedingungslos neu — auch einen im Zug. Der neue kannte den
    Zug nicht, die nächste Bewegung wurde ein Kameraschwenk, und beim
    Loslassen kam keine Stelle (Sonde ``probe_grip_drag.py``).
    """
    from app.ui.render.api import PointerEvent

    window = _window_with_a_renderer()
    try:
        _a_selected_hole(window)
        flow = _measures_in_the_view(window)
        assert flow is not None and flow.active
        viewport = window.viewport
        grip = viewport._placement_grip
        assert grip is not None
        viewport.renderer.item_picks[(400, 300)] = grip.items[0]
        tool = flow._tool
        assert tool is not None
        viewport._on_pointer(PointerEvent("move", 400, 300))
        viewport._on_pointer(PointerEvent("press", 400, 300, button="left"))
        assert grip.pressing, "der Zug hat begonnen"
        before = tool.matrix()[:3, 3].copy()

        # Mitten im Zug zeichnet der Fluss neu — wie nach einer Radraste.
        viewport.cameraMoved.emit()
        QApplication.processEvents()
        assert viewport._placement_grip is grip, "derselbe Griff steht noch"
        assert grip.pressing, "und er ist noch im Zug"

        viewport._on_pointer(PointerEvent("move", 440, 300, buttons=frozenset({"left"})))
        assert not np.allclose(tool.matrix()[:3, 3], before), "die Bewegung zieht das Werkzeug"
        dragged: list[Any] = []
        viewport.placementDragged.connect(dragged.append)
        viewport._on_pointer(PointerEvent("release", 440, 300, button="left"))
        assert dragged, "und das Loslassen meldet die Stelle"
    finally:
        window.end_quiet_placement()
        QApplication.processEvents()
        window.release()


def test_the_placement_grip_stays_at_the_mouth_of_a_long_drill(qt_app: QApplication) -> None:
    """Der Griff gehört zur gewählten Stelle, nicht zur Mitte des langen Bohrwerkzeugs."""
    window = _window_with_a_renderer()
    try:
        _a_selected_hole(window)
        flow = _measures_in_the_view(window)
        assert flow is not None and flow.active and flow._surface is not None
        tool = flow._tool
        grip = window.viewport._placement_grip
        assert tool is not None and grip is not None
        mouth = window.viewport.view_point_of(flow._surface.point, flow._object_id)
        assert np.allclose(grip.origin, mouth), "die Pfeile beginnen an der sichtbaren Mündung"
        assert not np.allclose(tool.centre(), mouth), "der Fall enthält ein langes Werkzeug"
        before = tool.matrix().copy()
        flow.redraw()
        assert window.viewport._placement_grip is grip
        assert np.allclose(tool.matrix(), before), "der Griff ändert die Werkzeuglage nicht"
        moved = before.copy()
        moved[:3, 3] += (7.0, -4.0, 2.0)
        tool.set_matrix(moved)
        window.viewport.grip_placement(tool, rotation=False)
        after = window.viewport._placement_grip
        assert after is not None and after is not grip
        assert np.allclose(after.origin, moved[:3, 3]), "auch nach dem Zug gilt der Ansatzpunkt"
    finally:
        window.end_quiet_placement()
        QApplication.processEvents()
        window.release()


def test_a_grip_that_still_fits_is_kept_across_a_redraw(qt_app: QApplication) -> None:
    """Ein Griff, der schon passt, wird nicht abgebaut und neu gebaut.

    Gleiches Ziel, gleiche Ringe, gleicher Maßstab, gleiche Matrix: Der neue
    stünde genau da, wo der alte steht. Jedes ``redraw`` — je Kamerageste,
    Radraste, Tastendruck in einem Feld — kostete bis zum 21.09.2026 sechs
    Renderer-Objekte für nichts (gemessen 5,7 ms von 22). Versetzt der Zug
    das Ziel, kommt ein frischer Griff — er rechnet gegen die Matrix, die
    sein Ziel beim Anhängen hatte.
    """
    window = _window_with_a_renderer()
    try:
        _a_selected_hole(window)
        flow = _measures_in_the_view(window)
        assert flow is not None and flow.active
        viewport = window.viewport
        grip = viewport._placement_grip
        assert grip is not None
        flow.redraw()
        assert viewport._placement_grip is grip, "derselbe Griff nach einem Neuzeichnen"
        assert not set(grip.items) & set(viewport.renderer.removed), "nichts davon abgebaut"

        tool = flow._tool
        assert tool is not None
        moved = tool.matrix()
        moved[0, 3] += 3.0
        tool.set_matrix(moved)
        viewport.grip_placement(tool, rotation=False)
        assert viewport._placement_grip is not grip, "ein versetztes Ziel bekommt einen frischen"
    finally:
        window.end_quiet_placement()
        QApplication.processEvents()
        window.release()


def test_the_wheel_over_a_floating_measure_field_zooms_unless_the_field_has_focus(
    qt_app: QApplication,
) -> None:
    """Eine Radraste über einem schwebenden Maßfeld ist Zoom — bis jemand hineinklickt.

    Die Felder schweben über dem Bild, und Qt gibt eine Raste über einem
    Drehfeld dem Feld: Bis zum 21.09.2026 verstellte sie das Maß um einen
    Millimeter und band den Entwurf, wo der Kunde zoomen wollte (Sonde
    ``probe_wheel_over_field.py``). Dieselbe Regel wie im Merkmalfenster
    (``wheel_needs_focus``): ohne Fokus geht die Raste weiter, mit Fokus
    dreht sie den Wert.
    """
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtGui import QWheelEvent
    from PySide6.QtTest import QTest

    def wheel(field: QWidget) -> QWheelEvent:
        local = QPointF(field.width() / 2, field.height() / 2)
        return QWheelEvent(
            local,
            field.mapToGlobal(local.toPoint()).toPointF(),
            QPoint(0, 0),
            QPoint(0, 120),
            Qt.MouseButton.NoButton,
            Qt.KeyboardModifier.NoModifier,
            Qt.ScrollPhase.NoScrollPhase,
            False,
        )

    window = _window_with_a_renderer()
    try:
        _a_selected_hole(window)
        flow = _measures_in_the_view(window)
        assert flow is not None and flow.active
        fields = [
            *flow._measures,
            *flow._centre_measures,
            flow._depth_measure,
            *(editor for editor in flow._measure_targets if isinstance(editor, LengthSpin)),
        ]
        assert flow._measure_group is not None
        assert len(fields) > 5, "die fünf eigenen Felder und die Editoren der Maßgruppe"
        for field in fields:
            assert field.focusPolicy() == Qt.FocusPolicy.StrongFocus, field.objectName()

        field = flow._measures[0]
        assert field.isVisibleTo(window.viewport) and not field.hasFocus()
        value = field.value_mm()
        event = wheel(field)
        QApplication.sendEvent(field, event)
        QApplication.processEvents()
        assert not event.isAccepted(), "die Raste geht weiter — an die Ansicht, die zoomt"
        assert field.value_mm() == pytest.approx(value), "das Maß steht"
        assert not flow.dialog.begun, "und kein Entwurf ist begonnen"

        window.show()
        window.activateWindow()
        QApplication.processEvents()
        QTest.mouseClick(field.lineEdit(), Qt.MouseButton.LeftButton)
        QApplication.processEvents()
        assert field.hasFocus(), "der Klick ins Feld gibt ihm den Fokus"
        QApplication.sendEvent(field, wheel(field))
        QApplication.processEvents()
        assert field.value_mm() != pytest.approx(value), "mit Fokus dreht die Raste den Wert"
        assert flow.dialog.begun
    finally:
        window.end_quiet_placement()
        QApplication.processEvents()
        window.release()


def test_a_drag_at_a_foreign_tool_grip_leaves_the_other_flow_alone(qt_app: QApplication) -> None:
    """Zwei Flüsse an einer Ansicht: Der Zug am Griff des einen bewegt den anderen nicht.

    Die Signale der Ansicht sind ungerichtet — ``placementDragStarted`` und
    ``placementDragged`` kommen bei jedem Fluss an. Stehen die stillen Maße
    einer Bohrung und ein Baustein aus dem Dialog, der in ihr sitzt, verschob
    ein Zug am Bausteingriff bis zum 21.09.2026 auch den stillen Fluss: Der
    Bohrungsentwurf war begonnen und an eine fremde Stelle gebunden (Sonde
    ``probe_two_flows.py``: stiller Fluss x = −6,53 statt −25). Der Griff
    sagt, wessen Werkzeug er trägt; der Fluss hört nur auf den eigenen.
    """
    window = _window_with_a_renderer()
    try:
        _a_selected_hole(window)
        flow = _measures_in_the_view(window)
        assert flow is not None and flow.active and flow._surface is not None
        viewport = window.viewport
        host = flow.dialog
        before = tuple(flow._surface.point)
        foreign = PlacementItem()
        moved = np.eye(4)
        moved[:3, 3] = (before[0] + 18.0, before[1], before[2])

        # Der Griff der Ansicht hängt an einem fremden Werkzeug.
        viewport._placement_grip_item = foreign
        viewport.placementDragStarted.emit()
        viewport.placementDragged.emit(moved)
        QApplication.processEvents()
        assert not host.begun, "der fremde Zug beginnt den eigenen Entwurf nicht"
        assert tuple(flow._surface.point) == pytest.approx(before), "und versetzt ihn nicht"

        # Am eigenen Werkzeug gilt derselbe Zug.
        viewport._placement_grip_item = flow._tool
        viewport.placementDragStarted.emit()
        viewport.placementDragged.emit(moved)
        QApplication.processEvents()
        assert host.begun, "der eigene Zug beginnt den Entwurf"
        assert flow._surface.point[0] == pytest.approx(before[0] + 18.0, abs=0.1), (
            "und versetzt ihn"
        )
    finally:
        window.end_quiet_placement()
        QApplication.processEvents()
        window.release()


def test_a_camera_move_with_measures_in_the_view_draws_exactly_one_frame(
    qt_app: QApplication,
) -> None:
    """Radraste, Zugende, Ruhen der 3D-Maus, Ansichtswahl: je eines ein Bild — nicht zwei oder drei.

    Bis zum 21.09.2026 zeichnete der Navigator die Raste, dann hörte die
    Maßtinte ``cameraMoved`` und zeichnete noch einmal; am Zugende kamen
    Einrasten, Schatten und Tinte auf drei Bilder (gemessen 21,7 ms je Raste
    zusätzlich). Jetzt meldet, wer die Kamera bewegt, zuerst — die Hörer legen
    ihre Punkte neu und zeichnen nicht — und zeichnet danach genau einmal.
    """
    from app.ui.render.api import PointerEvent

    window = _window_with_a_renderer()
    try:
        _a_selected_hole(window)
        flow = _measures_in_the_view(window)
        assert flow is not None and flow.active and flow._canvas.shown
        viewport = window.viewport
        renderer = viewport.renderer
        # Der Navigator entsteht mit dem Renderer; die Attrappe kam nach dem
        # Fensterbau, also hier ausdrücklich.
        viewport.set_navigation(viewport._scheme)
        assert viewport._navigator is not None
        ink = flow._canvas.items[0]

        for label, move in (
            ("Radraste", lambda: viewport._on_pointer(PointerEvent("wheel", 300, 200, delta=1.0))),
            ("Zugende", lambda: viewport._navigator._calls.on_end()),
            ("3D-Maus ruht", viewport.settle_camera),
            ("Ansichtswahl", lambda: viewport.view_from("front")),
        ):
            renders, updates = renderer.renders, ink.updates
            move()
            assert renderer.renders == renders + 1, f"{label}: genau ein Bild"
            assert ink.updates == updates + 1, f"{label}: und die Tinte liegt neu"
    finally:
        window.end_quiet_placement()
        QApplication.processEvents()
        window.release()


def test_a_blocked_grip_keeps_the_knobs_only_when_the_caller_says_so(
    qt_app: QApplication,
) -> None:
    """Die Griffsperre allein nimmt die Knöpfe mit; nur der Maßeditor sagt ``knobs=True``.

    Der Erkennungsdialog und eine Textur über der ganzen Fläche sperren
    denselben Griff und wollen keinen Knopf — ein Zug daran endete in
    ``slotProposed`` und damit im Merkmalfenster, mitten im fremden Dialog.
    """
    window = _window_with_a_renderer()
    try:
        _a_selected_hole(window)
        viewport = window.viewport
        assert viewport._slot_handle is not None, "der Maßeditor sagt es an"
        viewport.set_feature_gizmo_blocked(True)
        assert viewport._slot_handle is None and viewport._gizmo is None, (
            "dieselbe Sperre ohne Ansage nimmt die Knöpfe mit"
        )
        viewport.set_feature_gizmo_blocked(True, knobs=True)
        assert viewport._slot_handle is not None and viewport._gizmo is None, (
            "mit Ansage stehen sie wieder — ohne Pfeile"
        )
        viewport.set_feature_gizmo_blocked(False)
        assert viewport._slot_handle is None and viewport._gizmo is None, (
            "der Platzierungsgriff des Editors ersetzt den Griff der Auswahl, "
            "und ohne Ansage steht auch kein Knopf"
        )
    finally:
        window.end_quiet_placement()
        QApplication.processEvents()
        window.release()


def test_the_measures_stay_in_the_view_while_a_pulled_slot_waits(qt_app: QApplication) -> None:
    """Nach dem Zug zum Langloch bleiben die Maße stehen — auch wenn die Kamera dreht.

    Die Länge wächst um die Mitte; die Kantenmaße gelten ihr weiter. Bis zum
    21.09.2026 blendete der wartende Zug Felder und Linien der gebundenen
    Maßgruppe aus, sobald irgendetwas neu zeichnete: Nach dem Zug standen sie
    noch, und die nächste Kameradrehung nahm sie mit (Robert: „wenn wir das
    langloch ziehen und dann die ansicht drehen sind die maße weg"). Der runde
    Umriss der Mündung tritt dabei zurück — den gezogenen zeigt der Griff.
    """
    from app.ui.render.api import Pick, PointerEvent

    window = _window_with_a_renderer()
    try:
        object_id, hole = _a_selected_hole(window)
        flow = window._quiet_placement
        assert flow is not None and flow.active and flow._canvas.shown
        assert flow._canvas.outline, "vor dem Zug steht der runde Umriss der Mündung"
        shown_fields = [field for field in flow._measures if not field.isHidden()]
        assert shown_fields, "und die Kantenmaße stehen"
        lines_before = len(flow._canvas.lines)
        assert lines_before, "mit ihren Maßlinien"

        entry = window.session.last_result.scene.objects[object_id]
        feature = entry.features[hole]
        centre = feature.params["centre"]
        top = (float(centre[0]), float(centre[1]), float(entry.mesh.bounds.maximum[2]))
        renderer = window.viewport.renderer
        x, y, _depth = renderer.world_to_display(top)
        x, y = round(x), round(y)
        renderer.picks[(x, y)] = Pick(
            top, window.viewport._actors[object_id], int(feature.face_indices[0])
        )
        for event in (
            PointerEvent("move", x, y),
            PointerEvent("press", x, y, button="left"),
            PointerEvent("move", x + 14, y + 4, buttons=frozenset({"left"})),
            PointerEvent("release", x + 14, y + 4, button="left"),
        ):
            window.viewport._on_pointer(event)
            QApplication.processEvents()
        for _ in range(120):
            QApplication.processEvents()
            window.session.wait_for_idle()
        assert window.viewport.slot_drag_waits(), "der Zug zum Langloch wartet"
        assert not flow.active, "der alte Bohrungseditor ist abgelöst"
        flow = window._quiet_placement
        assert flow is not None and flow.active and flow.spec_of().name == "slot_hole"
        assert flow.dialog.begun, "der Zug hat den gemeinsamen Entwurf begonnen"

        def lage() -> tuple[bool, int, int, int]:
            return (
                flow._canvas.shown,
                len([field for field in flow._measures if not field.isHidden()]),
                len(flow._canvas.lines),
                len(flow._canvas.outline),
            )

        assert lage() == (True, len(shown_fields), lines_before, 0), (
            "nach dem Zug: Linien und Felder stehen, der runde Umriss ist weg"
        )
        window.viewport.cameraMoved.emit()
        QApplication.processEvents()
        assert lage() == (True, len(shown_fields), lines_before, 0), (
            "und die Kamera nimmt sie nicht mit"
        )
    finally:
        window.end_quiet_placement()
        QApplication.processEvents()
        window.release()


def test_accepting_the_measures_takes_a_pulled_slot_along(qt_app: QApplication) -> None:
    """Übernehmen in der Maßgruppe meint das gezogene Langloch (Robert, 22.09.2026:
    „warum geht zum langloch nicht mehr").

    Die Gruppe ist an *Bohrung ändern* gebunden; ihr Übernehmen fuhr die
    gebundene Handlung mit unverändertem Durchmesser — „Die Bohrung hat bereits
    diesen Durchmesser" — und das Langloch blieb ein Umriss. Jetzt entsteht
    daraus der Langlochschritt, mit der Stelle aus den Feldern.
    """
    from app.ui.render.api import Pick, PointerEvent

    window = _window_with_a_renderer()
    try:
        object_id, hole = _a_selected_hole(window)
        flow = window._quiet_placement
        assert flow is not None and flow.active and flow.spec_of().name == "resize_hole"
        entry = window.session.last_result.scene.objects[object_id]
        feature = entry.features[hole]
        centre = feature.params["centre"]
        top = (float(centre[0]), float(centre[1]), float(entry.mesh.bounds.maximum[2]))
        renderer = window.viewport.renderer
        x, y, _depth = renderer.world_to_display(top)
        x, y = round(x), round(y)
        renderer.picks[(x, y)] = Pick(
            top, window.viewport._actors[object_id], int(feature.face_indices[0])
        )
        for event in (
            PointerEvent("move", x, y),
            PointerEvent("press", x, y, button="left"),
            PointerEvent("move", x + 14, y + 4, buttons=frozenset({"left"})),
            PointerEvent("release", x + 14, y + 4, button="left"),
        ):
            window.viewport._on_pointer(event)
            QApplication.processEvents()
        for _ in range(120):
            QApplication.processEvents()
            window.session.wait_for_idle()
        assert window.viewport.slot_drag_waits(), "der Zug zum Langloch wartet"
        pulled = window.viewport.waiting_slot_drag(hole)
        assert pulled is not None and pulled[0] > 0.0
        flow = window._quiet_placement
        assert flow is not None and flow.active and flow.spec_of().name == "slot_hole"

        before = len(window.session.project.document.ops)
        flow.accept()
        for _ in range(200):
            QApplication.processEvents()
            window.session.wait_for_idle()
            if len(window.session.project.document.ops) > before:
                break
        steps = window.session.project.document.ops
        assert len(steps) == before + 1, "genau ein Schritt"
        assert steps[-1].op == "slot_hole", steps[-1].op
        assert steps[-1].params["slot_length"] == pytest.approx(pulled[0])
        assert not window.viewport.slot_drag_waits(), "der Zug ist eingelöst"
        assert not any(step.op == "resize_hole" for step in steps[before:]), (
            "kein Schritt mit unverändertem Durchmesser"
        )
    finally:
        window.end_quiet_placement()
        QApplication.processEvents()
        window.release()


def test_a_new_diameter_beside_a_pulled_slot_is_one_step_with_the_new_width(
    qt_app: QApplication,
) -> None:
    """Ein Zug wartet, und die Felder tragen einen neuen Durchmesser: Übernehmen
    macht daraus **einen** Schritt — *Zum Langloch ziehen* mit der Stelle und
    der neuen Breite (Entscheidung Robert, 22.09.2026: „Ja eine transaktion").

    Zwei Funde des Reviews vom selben Tag stehen dahinter: Die Route mischte
    ``surface_values`` ungefiltert in die Werte, und *Bohrung ändern* lehnte
    ``nx``/``ny``/``nz`` ab — kein Schritt, der Zug stand weiter. Und die
    Statuszeile versprach ein zweites Übernehmen, das nichts vorfindet: Der
    Szenenaufbau nach dem Schritt verwirft den Zug. Zwei Schritte in einer
    Transaktion gingen auch nicht — das Langloch heißt nach dem Zug neu, und
    der zweite Schritt kennte seinen Namen erst nach der Auswertung. Jetzt:
    ein Übernehmen, ein Schritt, ein Strg+Z.
    """
    from app.ui.render.api import Pick, PointerEvent

    window = _window_with_a_renderer()
    said: list[str] = []
    original_announce = window.announce

    def spy(text: str, *args: object, **kwargs: object) -> None:
        said.append(str(text))
        original_announce(text, *args, **kwargs)

    window.announce = spy  # type: ignore[method-assign]
    try:
        object_id, hole = _a_selected_hole(window)
        flow = window._quiet_placement
        assert flow is not None and flow.active and flow.spec_of().name == "resize_hole"
        entry = window.session.last_result.scene.objects[object_id]
        feature = entry.features[hole]
        centre = feature.params["centre"]
        top = (float(centre[0]), float(centre[1]), float(entry.mesh.bounds.maximum[2]))
        renderer = window.viewport.renderer
        x, y, _depth = renderer.world_to_display(top)
        x, y = round(x), round(y)
        renderer.picks[(x, y)] = Pick(
            top, window.viewport._actors[object_id], int(feature.face_indices[0])
        )
        for event in (
            PointerEvent("move", x, y),
            PointerEvent("press", x, y, button="left"),
            PointerEvent("move", x + 14, y + 4, buttons=frozenset({"left"})),
            PointerEvent("release", x + 14, y + 4, button="left"),
        ):
            window.viewport._on_pointer(event)
            QApplication.processEvents()
        for _ in range(120):
            QApplication.processEvents()
            window.session.wait_for_idle()
        pulled = window.viewport.waiting_slot_drag(hole)
        assert pulled is not None and pulled[0] > 0.0, "der Zug wartet"
        flow = window._quiet_placement
        assert flow is not None and flow.active and flow.spec_of().name == "slot_hole"

        fields = {
            field.accessibleName().rsplit(" — ", 1)[-1]: field
            for field in flow._measure_group.findChildren(LengthSpin)
            if "Zum Langloch ziehen" in field.accessibleName()
        }
        wider = float(feature.params["diameter"]) + 1.0
        fields["Breite"].set_value_mm(wider)
        for _ in range(200):
            QApplication.processEvents()
            window.session.wait_for_idle()
        assert flow.dialog.values()["diameter"] == pytest.approx(wider)
        assert flow.dialog.values()["slot_length"] == pytest.approx(pulled[0])

        before = len(window.session.project.document.ops)
        transactions = len(window.session.project.document.transactions)
        flow.accept()
        for _ in range(300):
            QApplication.processEvents()
            window.session.wait_for_idle()
            if len(window.session.project.document.ops) > before:
                break
        for _ in range(60):
            QApplication.processEvents()
            window.session.wait_for_idle()
        document = window.session.project.document
        steps = document.ops
        assert [step.op for step in steps[before:]] == ["slot_hole"], (
            [step.op for step in steps[before:]],
            said,
        )
        assert len(document.transactions) == transactions + 1, "eine Transaktion"
        assert document.transactions[-1].ops == (steps[-1].id,)
        assert steps[-1].params["slot_length"] == pytest.approx(pulled[0])
        assert steps[-1].params["at_feature"] == hole
        assert steps[-1].params["diameter"] == pytest.approx(wider)
        assert steps[-1].params["x"] == pytest.approx(float(centre[0]), abs=0.05)
        assert not window.viewport.slot_drag_waits(), "der Zug ist eingelöst"
        # Das Ergebnis ist ein Langloch mit der neuen Breite.
        result = window.session.last_result
        assert result is not None and result.stopped_at is None
        slots = [f for f in result.scene.objects[object_id].features.values() if f.kind == "slot"]
        assert len(slots) == 1 and hole not in result.scene.objects[object_id].features
        assert slots[0].params["diameter"] == pytest.approx(wider, abs=0.05)
        assert slots[0].params["length"] == pytest.approx(pulled[0], abs=0.1)
        assert not any("wartet auf ein weiteres" in text for text in said), said
        assert not any("Ziehen Sie das Langloch danach erneut" in text for text in said), said
        assert not any("Diesen Parameter gibt es" in text for text in said), said
        # Und ein Strg+Z nimmt beides.
        window.session.undo()
        for _ in range(120):
            QApplication.processEvents()
            window.session.wait_for_idle()
        assert len(window.session.project.document.ops) == before
    finally:
        window.end_quiet_placement()
        QApplication.processEvents()
        window.release()


@pytest.mark.parametrize("begun", [False, True], ids=["passive", "begun"])
@pytest.mark.parametrize("where", ["tree", "viewport"])
def test_real_selection_clicks_keep_only_a_begun_measure_draft(
    qt_app: QApplication, begun: bool, where: str
) -> None:
    """Baum und Modell prüfen vor der Mutation; reine Auskunft bleibt abwählbar."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.ui.labels import LengthSpin

    window = _window_with_a_renderer()
    try:
        window.show()
        object_id, hole = _a_selected_hole(window)
        flow = _measures_in_the_view(window)
        assert flow is not None and flow.active and not flow.dialog.begun
        if begun:
            field = flow._measure_group.findChildren(LengthSpin)[0]
            QTest.mouseClick(field.lineEdit(), Qt.MouseButton.LeftButton)
            assert flow.dialog.begun
        before = flow.dialog.values()
        steps = len(window.session.project.document.ops)
        tree = window.object_tree.tree
        selected = tree.currentIndex()
        if where == "tree":
            body = tree.topLevelItem(0)
            tree.scrollToItem(body)
            QApplication.processEvents()
            position = tree.visualItemRect(body).center()
            assert tree.viewport().rect().contains(position)
            QTest.mouseClick(tree.viewport(), Qt.MouseButton.LeftButton, pos=position)
        else:
            window.viewport._on_left_click(5, 5)
        QApplication.processEvents()
        if begun:
            assert window._quiet_placement is flow and flow.active
            assert flow.dialog.values() == before
            assert window.object_tree.selected() == object_id
            assert window.object_tree.selected_feature() == hole
            assert window.viewport._selected_feature == hole
            assert tree.currentIndex() == selected
        else:
            assert not flow.active and window._quiet_placement is None
            assert window.object_tree.selected_feature() is None
        assert len(window.session.project.document.ops) == steps
    finally:
        window.end_quiet_placement()
        QApplication.processEvents()
        window.release()


def test_mesh_measure_waits_until_its_real_difference_has_been_drawn(
    qt_app: QApplication, monkeypatch: Any
) -> None:
    """Auch eine Netzbohrung braucht die dargestellte Vorschau, nicht nur fertige Rechenwerte."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.ui.labels import LengthSpin

    window = _window_with_a_renderer()
    try:
        _a_selected_hole(window)
        flow = _measures_in_the_view(window)
        assert flow is not None and flow.active
        show = window.viewport.show_difference
        waiting: list[Any] = []
        monkeypatch.setattr(window.viewport, "show_difference", waiting.append)
        field = flow._measure_group.findChildren(LengthSpin)[0]
        field.lineEdit().selectAll()
        QTest.keyClicks(
            field.lineEdit(), QLocale().toString(round(field.value_mm() + 0.5, 2), "f", 2)
        )
        QTest.keyClick(field.lineEdit(), Qt.Key.Key_Return)
        window._feature_preview.stop()
        window._preview_feature_change()
        assert window.session.wait_for_idle(30_000)
        approval = window._preview_approval
        assert approval is not None and approval.required and not approval.displayed
        assert waiting and not flow.dialog.can_accept()
        steps = len(window.session.project.document.ops)
        flow.accept()
        assert flow.active and len(window.session.project.document.ops) == steps
        show(waiting[-1])
        QApplication.processEvents()
        assert approval.displayed and window.viewport.is_difference_applied(approval.difference)
        flow._measure_accept.click()
        assert window.session.wait_for_idle(30_000)
        assert len(window.session.project.document.ops) == steps + 1
    finally:
        window.end_quiet_placement()
        QApplication.processEvents()
        window.release()


def test_an_early_accept_in_the_measure_group_waits_for_the_preview_and_applies_once(
    qt_app: QApplication, monkeypatch: Any
) -> None:
    """Wert tippen, sofort Übernehmen, Vorschau kommt — genau ein Schritt, ohne zweiten Klick.

    ``can_accept`` verneint, solange die erwartete Vorschau nicht steht; bis
    zum 22.09.2026 verfiel der Klick stumm, und wer nach dem Tippen sofort
    übernahm, musste es nach dem Bild noch einmal tun. Der Träger meldet den
    frühen Klick jetzt über ``preview_defer`` an das Fenster, das ihn an die
    Freigabe hängt (``_PreviewApproval.pending_click``) und nach dem Bild
    einmal ausführt.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    window = _window_with_a_renderer()
    try:
        _a_selected_hole(window)
        flow = _measures_in_the_view(window)
        assert flow is not None and flow.active
        assert flow.dialog.preview_defer is not None, "das Fenster hängt seinen Haken an"
        show = window.viewport.show_difference
        waiting: list[Any] = []
        monkeypatch.setattr(window.viewport, "show_difference", waiting.append)
        field = flow._measure_group.findChildren(LengthSpin)[0]
        field.lineEdit().selectAll()
        QTest.keyClicks(
            field.lineEdit(), QLocale().toString(round(field.value_mm() + 0.5, 2), "f", 2)
        )
        QTest.keyClick(field.lineEdit(), Qt.Key.Key_Return)
        window._feature_preview.stop()
        window._preview_feature_change()
        assert window.session.wait_for_idle(30_000)
        approval = window._preview_approval
        assert approval is not None and approval.required and not approval.displayed
        assert waiting and not flow.dialog.can_accept()
        steps = len(window.session.project.document.ops)

        flow._measure_accept.click()
        assert len(window.session.project.document.ops) == steps, "vor dem Bild kein Schritt"
        assert approval.pending_click is not None, "der Klick wartet an der Freigabe"

        show(waiting[-1])
        QApplication.processEvents()
        assert window.session.wait_for_idle(30_000)
        for _ in range(40):
            QApplication.processEvents()
        assert len(window.session.project.document.ops) == steps + 1, "genau ein Schritt"
    finally:
        window.end_quiet_placement()
        QApplication.processEvents()
        window.release()


def test_a_refused_click_in_the_view_says_so_and_keeps_the_selection(qt_app: QApplication) -> None:
    """Begonnene Maßgruppe, Klick auf ein anderes Merkmal: der Satz kommt, die Auswahl bleibt.

    Bis zum 22.09.2026 verschluckten ``_select_at``, Rechtsklick und Linksklick
    den Klick stumm; nur der Menüweg sprach (Review Fenster #6). Die Ansicht
    ruft jetzt ``selection_refused`` — einmal je Klick —, und das Fenster sagt
    den Satz.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    from app.ui.render.api import Pick

    window = _window_with_a_renderer()
    try:
        object_id, hole = _a_selected_hole(window)
        flow = _measures_in_the_view(window)
        assert flow is not None and flow.active
        field = flow._measure_group.findChildren(LengthSpin)[0]
        QTest.mouseClick(field.lineEdit(), Qt.MouseButton.LeftButton)
        assert flow.dialog.begun
        viewport = window.viewport
        refusals: list[None] = []
        viewport.selection_refused = lambda: refusals.append(None)
        assert not viewport.user_selection_allowed(), "die begonnene Maßgruppe hält die Auswahl"

        entry = window.session.last_result.scene.objects[object_id]
        other = next(
            identifier
            for identifier, feature in entry.features.items()
            if feature.kind == "hole" and identifier != hole
        )
        centre = entry.features[other].params["centre"]
        top = (float(centre[0]), float(centre[1]), float(entry.mesh.bounds.maximum[2]))
        x, y, _depth = viewport.renderer.world_to_display(top)
        x, y = round(x), round(y)
        viewport.renderer.picks[(x, y)] = Pick(
            top, viewport._actors[object_id], int(entry.features[other].face_indices[0])
        )

        viewport._on_left_click(x, y)
        assert len(refusals) == 1, "der Linksklick sagt es einmal"
        viewport._on_right_click(x, y)
        assert len(refusals) == 2, "der Rechtsklick ebenso"
        assert viewport._select_at(top) is True and len(refusals) == 3
        assert window.object_tree.selected_feature() == hole, "die Auswahl steht unverändert"
        assert flow.active and flow.dialog.begun
    finally:
        window.end_quiet_placement()
        QApplication.processEvents()
        window.release()


@pytest.mark.parametrize("kind", ["mesh", "brep"])
@pytest.mark.parametrize("case", ["mouth", "fields-only", "grip-then-depth", "centre", "through"])
def test_historical_bore_fields_preview_all_following_steps_and_preserve_original_values(
    qt_app: QApplication, monkeypatch: Any, kind: str, case: str
) -> None:
    """Originalwerte, neuer Flächensitz und Folgeschritte bleiben derselbe Auftrag."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest
    from PySide6.QtWidgets import QLabel

    from app.core.brep import Solid
    from app.core.scene import placement
    from app.core.types import Parameter
    from app.ui.labels import LengthSpin

    window = _window_with_a_renderer()
    try:
        initial = {
            "diameter": 6.0,
            "depth": 8.0,
            "z": "@surface_height",
            "anchor": "mouth",
            "compensate": False,
        }
        edited_depth = 12.0
        if case == "centre":
            initial.update(anchor="centre", z=16.0)
            edited_depth = 6.0
        elif case == "through":
            initial.update(depth=0.0, z=10.0)
            edited_depth = 8.0
        seat_available = case != "fields-only"
        session = window.session
        assert session.add_parameter(Parameter("surface_height", 20.0))
        assert session.apply(
            "Platte",
            [
                OperationDraft(
                    op="create_brep_box" if kind == "brep" else "create_box",
                    params={"width": 40.0, "depth": 30.0, "height": 20.0},
                )
            ],
        )
        assert session.wait_for_idle(30_000)
        owner = session.project.document.ops[-1].outputs[0]
        assert session.apply(
            "Bohrung",
            [
                OperationDraft(
                    op="drill_brep_hole" if kind == "brep" else "drill_hole",
                    inputs=(owner,),
                    params=initial,
                )
            ],
        )
        assert session.wait_for_idle(30_000)
        drill = session.project.document.ops[-1]
        original = dict(drill.params)
        assert session.apply(
            "Danach",
            [
                OperationDraft(op="translate_object", inputs=(owner,), params={"dx": 25.0}),
                OperationDraft(op="create_box", params={"x": 90.0}),
            ],
        )
        assert session.wait_for_idle(30_000)
        result = session.last_result
        assert result is not None and result.complete and len(result.scene.objects) == 2
        hole = next(
            name
            for name, feature in result.scene.objects[owner].features.items()
            if feature.kind == "hole" and feature.created_by == drill.id
        )
        if not seat_available:
            monkeypatch.setattr(placement, "seat_for_bore_step", lambda *_args: None)
        window.object_tree.select_object(owner)
        window.object_tree.select_feature(owner, hole)
        # Zugemacht **nach** der Auswahl (Konzept D: die nächste Auswahl bringt
        # das Fenster zurück, der Weg ins Bild nicht).
        window.feature_dock.hide()
        flow = _measures_in_the_view(window)
        assert flow is not None and flow._change_op == drill.id
        assert flow.dialog.values() == original
        caption = flow._measure_group.findChild(QLabel, "feature-measure-source")
        assert caption is not None and "Am fertigen Teil:" in caption.text()
        assert not flow.dialog.begun and window.feature_dock.isHidden()
        assert set(flow._result.scene.objects) == {owner}
        assert not any(
            f.kind == "hole" for f in flow._result.scene.objects[owner].features.values()
        )
        assert (flow._surface is not None) is seat_available
        assert flow._measure_without_surface is not seat_available
        if not seat_available:
            assert window.viewport._placement_grip is None
            assert "Flächenmaße" in flow._measure_note.text()
        expected = dict(original)
        if case == "grip-then-depth":
            grip = window.viewport._placement_grip
            assert grip is not None and not grip._rings
            renderer = window.viewport.renderer
            x, y, _depth = renderer.world_to_display(flow._surface.point)
            x, y = round(x), round(y)
            renderer.item_picks[(x, y)] = grip.items[0]
            window.viewport._on_pointer(PointerEvent("move", x, y))
            window.viewport._on_pointer(PointerEvent("press", x, y, button="left"))
            assert window.viewport._placement_grip is grip and grip.pressing
            # Der Druck allein bindet nichts — erst der Weg über die
            # Klickschwelle (``CLICK_SLACK``) ist ein Zug; gerechnet wird er
            # vom Druckpunkt aus, zurück auf acht Punkte endet er dort.
            assert not flow.dialog.begun, "ein Druck ohne Weg beginnt keinen Entwurf"
            window.viewport._on_pointer(
                PointerEvent("move", x + 16, y, buttons=frozenset({"left"}))
            )
            assert flow.dialog.begun and grip.dragging
            window.viewport._on_pointer(PointerEvent("move", x + 8, y, buttons=frozenset({"left"})))
            window.viewport._on_pointer(PointerEvent("release", x + 8, y, button="left"))
            assert session.wait_for_idle(30_000)
            expected = dict(flow.dialog.values())
            assert abs(expected["x"]) > 1.0
        depth = next(
            field
            for field in flow._measure_group.findChildren(LengthSpin)
            if "Tiefe" in field.accessibleName()
        )
        assert "aus dem Schritt" in depth.toolTip()
        assert "erzeugenden Schritt" in depth.accessibleDescription()
        depth.lineEdit().selectAll()
        QTest.keyClicks(depth.lineEdit(), QLocale().toString(float(edited_depth), "f", 2))
        QTest.keyClick(depth.lineEdit(), Qt.Key.Key_Return)
        assert session.history.operation(drill.id).params == original
        expected["depth"] = edited_depth
        assert flow.dialog.values() == expected
        approval = _display_measure_preview(window, flow)
        assert not flow._showing_input
        assert window.viewport._placement_grip is None
        assert not flow._canvas.shown
        assert all(field.isHidden() for field in flow._measures)
        if case in {"fields-only", "centre", "through"}:
            assert flow._surface is None and flow._measure_without_surface
        after = approval.difference.entries[owner].result
        assert after is not None
        assert after.mesh.bounds.minimum[0] == pytest.approx(5.0)
        assert isinstance(after.mesh, Solid) is (kind == "brep")
        assert len(window.viewport._result.scene.objects) == 2
        before = len(session.project.document.ops)
        flow._measure_accept.click()
        assert session.wait_for_idle(30_000)
        assert len(session.project.document.ops) == before
        changed = session.history.operation(drill.id)
        assert changed.params == expected
        assert session.last_result.complete
        session.undo()
        assert session.wait_for_idle(30_000)
        assert session.history.operation(drill.id).params == original
        session.redo()
        assert session.wait_for_idle(30_000)
        assert session.history.operation(drill.id).params == expected
    finally:
        window.end_quiet_placement()
        QApplication.processEvents()
        window.release()


def test_the_dialog_learns_from_the_flow_when_it_is_aiming(flow: Any) -> None:
    """Der Satz kommt und geht mit der Platzierung — durchs Fenster gemessen.

    „Bohrung setzen sollte doch über den Viewport gehen, wenn das
    dialogfenster da ist, keine Info dass es über den Viewport geht" (Robert,
    18.09.2026). Der Satz steht seither im Dialog, **und nur solange wirklich
    gezielt wird**: Beim Ändern eines bestehenden Schritts ist die Stelle
    längst gewählt, und ein Dialog, der dann zum Klicken auffordert, schickt
    den Kunden auf eine Geste, die es dort nicht gibt.

    Wer das an ``show_placement_hint`` allein prüft, prüft die Hälfte, die
    nicht ausfallen kann: Die andere ist die **Meldung** des Flusses. Sie
    stillzulegen blieb bis zum 18.09.2026 in 793 Tests unbemerkt (Fund der
    zweiten Durchsicht) — deshalb geht dieser Test über ``start`` und
    ``back`` und nicht über die Methode.
    """
    original, session, viewport, _dialog = flow
    original.dispose()
    object_id = original.inputs_of()[0]
    spec = REGISTRY.get("drill_hole")
    dialog = OperationDialog(spec, {object_id: "Würfel"})
    window = SimpleNamespace(
        viewport=viewport, session=session, _clear_preview=session.cancel_preview
    )
    controller = PlacementFlow(dialog, window, lambda: spec, lambda: (object_id,))
    try:
        # ``isHidden`` und nicht ``isVisible``: Das Fenster wird nie gezeigt.
        assert dialog._placement_hint.isHidden(), "vor dem Zielen sagt er nichts"

        controller.start()
        assert session.wait_for_idle(30_000)
        assert not dialog._placement_hint.isHidden(), (
            "solange gezielt wird, sagt der Dialog, wo die Stelle herkommt"
        )

        # **Nach Escape bleibt er stehen** (RM-205, 22.09.2026): Ein Klick auf
        # das Modell holt die Platzierung zurück, der Satz stimmt also weiter.
        controller.back()
        assert not dialog._placement_hint.isHidden(), "der Klick ins Modell führt zurück"
        assert viewport.resume is not None

        # Beim Ändern eines Schritts gibt es diese Geste nicht — dort sagt er
        # nach Escape nichts.
        controller._change_op = session.project.document.ops[-1].id
        controller.back()
        assert dialog._placement_hint.isHidden(), "ohne Rückweg kein Satz"
    finally:
        controller.dispose()
        dialog.deleteLater()


def test_several_redraws_in_one_event_round_draw_one_frame(
    flow: Any, qt_app: QApplication, monkeypatch: Any
) -> None:
    """Drei Neuzeichnungen derselben Ereignisrunde, ein Bild.

    Ein Anschlag im Maßfeld zeichnete den Fluss drei Mal neu — über das Maß,
    über die Wertemeldung des Trägers und über den fertigen Werkzeugbau — und
    jedes Mal ein ganzes Bild: an der Senkplatte bei 3163 mal 1259 Bildpunkten
    14 ms je Bild (22.09.2026). Die Lage der Felder entsteht sofort, das Bild
    einmal, wenn die Runde leer ist.
    """
    controller, session, viewport, _dialog = flow
    controller.start()
    assert session.wait_for_idle(30_000)
    _point(controller, session)
    qt_app.processEvents()
    frames: list[int] = []
    monkeypatch.setattr(viewport, "_draw", lambda: frames.append(1))
    for _ in range(3):
        controller.redraw()
    assert frames == [], "gezeichnet wird nach der Runde, nicht je Aufruf"
    qt_app.processEvents()
    assert frames == [1], f"{len(frames)} Bilder für eine Runde"


def test_a_released_measure_group_goes_back_only_without_a_parent(qt_app: QApplication) -> None:
    """Wer die Gruppe ausgab, bekommt sie zurück — sonst wird sie gelöscht wie bisher (RM-232).

    Der Fluss gibt sie ohne Elternteil ab, so wie ``QScrollArea.takeWidget``
    sie herausnimmt. Nimmt der Geber sie (``True``), bleibt sie verborgen am
    Leben; lehnt er ab, fehlt er oder hat sie noch einen Elternteil, geht sie
    mit ``deleteLater``.
    """
    from PySide6.QtCore import QEvent, QObject
    from PySide6.QtWidgets import QScrollArea
    from shiboken6 import isValid

    from app.ui.placement_flow import _release_measure_group

    def settle() -> None:
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)

    asked: list[QObject] = []
    scroll = QScrollArea()
    try:
        kept = QWidget()
        scroll.setWidget(kept)
        taken = scroll.takeWidget()
        assert taken is kept and kept.parentWidget() is None, "die Voraussetzung: ohne Elternteil"
        _release_measure_group(kept, lambda group: asked.append(group) or True)
        settle()
        assert asked == [kept] and isValid(kept) and kept.isHidden()

        refused = QWidget()
        _release_measure_group(refused, lambda group: asked.append(group) or False)
        settle()
        assert not isValid(refused)

        orphan = QWidget()
        _release_measure_group(orphan, None)
        settle()
        assert not isValid(orphan)

        parented = QWidget(scroll)
        _release_measure_group(parented, lambda group: asked.append(group) or True)
        settle()
        assert not isValid(parented) and asked[-1] is not parented
        kept.deleteLater()
    finally:
        scroll.deleteLater()
        settle()


def test_a_refusal_of_the_core_is_a_state_and_not_a_crash(caplog: pytest.LogCaptureFixture) -> None:
    """Eine Absage beim Start der Platzierung schreibt keinen Traceback.

    *Text aufbringen* startet mit leerem Textfeld (``label_text`` hat bewusst
    keine Vorgabe), und das Werkzeug entsteht an einem kleinen Körper gleich im
    Hauptfaden. Die ``ValidationError`` „Ohne Text gibt es nichts
    aufzubringen.“ landete mit vollem Traceback im Protokoll, und in der Leiste
    stand „Vorschau nicht verfügbar“. Ohne Fenster: nur die Weiche.
    """
    import logging

    from app.core.errors import ValidationError
    from app.i18n import _
    from app.ui.placement_flow import _answer_now, refusal_sentence

    def leer() -> Any:
        raise ValidationError(
            field="text", detail=_("Ohne Text gibt es nichts aufzubringen."), constraint="empty"
        )

    fertig: list[Any] = []
    gescheitert: list[str] = []
    abgesagt: list[str] = []
    with caplog.at_level(logging.DEBUG, logger="app.ui.placement_flow"):
        _answer_now(
            leer,
            fertig.append,
            gescheitert.append,
            lambda error: abgesagt.append(refusal_sentence(error)),
        )
    assert abgesagt == ["Ohne Text gibt es nichts aufzubringen."]
    assert fertig == [None], "der Fluss erfährt, dass es kein Werkzeug gibt"
    assert gescheitert == []
    assert not [r for r in caplog.records if r.levelno >= logging.WARNING], caplog.records

    # Gegenprobe: Das Unerwartete bleibt ein Fehler mit Protokollzeile.
    def kaputt() -> Any:
        raise RuntimeError("unerwartet")

    caplog.clear()
    with caplog.at_level(logging.DEBUG, logger="app.ui.placement_flow"):
        _answer_now(kaputt, fertig.append, gescheitert.append, abgesagt.append)
    assert gescheitert == ["RuntimeError: unerwartet"]
    assert [r for r in caplog.records if r.exc_info], "ein echter Fehler behält seinen Traceback"


def test_label_text_starts_with_the_sentence_of_the_empty_field(
    flow: Any, caplog: pytest.LogCaptureFixture
) -> None:
    """Am Fluss: leeres Textfeld → der Satz der Absage, dann ein Buchstabe → weiter.

    Vorher stand in der Leiste „Vorschau nicht verfügbar. Die Werte bearbeiten
    und erneut platzieren.“, bevor jemand getippt hatte, und das Protokoll
    trug „placement answer did not come back“ mit Traceback.
    """
    import logging

    from PySide6.QtWidgets import QLineEdit

    original, session, viewport, _original_dialog = flow
    original.dispose()
    object_id = original.inputs_of()[0]
    spec = REGISTRY.get("label_text")
    dialog = OperationDialog(spec, {object_id: "Würfel"})
    window = SimpleNamespace(
        viewport=viewport, session=session, _clear_preview=session.cancel_preview
    )
    controller = PlacementFlow(dialog, window, lambda: spec, lambda: (object_id,))
    try:
        with caplog.at_level(logging.DEBUG, logger="app.ui.placement_flow"):
            controller.start()
            assert session.wait_for_idle(30_000)
            QApplication.processEvents()
        assert controller._note.text() == "Ohne Text gibt es nichts aufzubringen."
        assert not [r for r in caplog.records if r.exc_info], "kein Traceback für ein leeres Feld"

        editor = dialog._editors["text"]
        line = editor if isinstance(editor, QLineEdit) else editor.findChild(QLineEdit)
        assert line is not None
        line.setText("A")
        for _round in range(50):
            QApplication.processEvents()
            session.wait_for_idle(30_000)
            if controller._tool_context is not None:
                break
        assert controller._tool_context is not None, "mit Text entsteht das Werkzeug"
        assert controller._note.text() != "Ohne Text gibt es nichts aufzubringen."
    finally:
        controller.dispose()
        assert session.wait_for_idle(30_000)
        dialog.close()


@pytest.mark.parametrize(
    "operation", ("insert_magnet_pocket", "insert_screw_hole", "insert_heatset_m4")
)
def test_part_placement_keeps_the_surface_and_edge_distances(
    flow: Any, operation: str, tmp_path: Path
) -> None:
    """Der sichtbare Klickweg speichert seinen Flächenbezug bis zur Projektdatei."""
    import json

    original, session, viewport, _original_dialog = flow
    original.dispose()
    object_id = original.inputs_of()[0]
    spec = REGISTRY.get(operation)
    dialog = OperationDialog(spec, {object_id: "Würfel"})
    window = SimpleNamespace(
        viewport=viewport, session=session, _clear_preview=session.cancel_preview
    )
    controller = PlacementFlow(dialog, window, lambda: spec, lambda: (object_id,))
    try:
        controller.start()
        assert session.wait_for_idle(30_000)
        _point(controller, session, confirm=True)
        surface = controller._surface
        assert surface is not None and len(surface.edges) == 2
        values = dialog.values()
        record = json.loads(values["surface_anchor"])
        assert record["object"] == object_id
        assert values["surface_distance_1"] == pytest.approx(surface.edges[0].distance)
        assert values["surface_distance_2"] == pytest.approx(surface.edges[1].distance)
        assert len(record["edges"]) == 2
        expression = f"={surface.edges[0].distance}"
        dialog._editors["surface_distance_1"].start_expression(expression)
        assert session.wait_for_idle(30_000)
        QApplication.processEvents()
        assert controller._set_values()
        assert dialog.values()["surface_distance_1"] == expression
        values = dialog.values()
        controller.back()
        session.apply(
            spec.title, [OperationDraft(op=operation, inputs=(object_id,), params=values)]
        )
        assert session.wait_for_idle(30_000)
        assert session.last_result is not None and session.last_result.complete
        stored = session.project.document.ops[-1]
        assert stored.params["surface_anchor"] == values["surface_anchor"]
        path = tmp_path / "surface.p3d"
        save(session.project, path)
        reopened = load(path)
        assert reopened.document.ops[-1].params == stored.params
        assert session.undo()
        assert session.wait_for_idle(30_000)
        session.redo()
        assert session.wait_for_idle(30_000)
        assert session.project.document.ops[-1].params == stored.params
        controller.dispose()
        dialog.close()
        dialog.deleteLater()
        dialog = OperationDialog(spec, {object_id: "Würfel"}, values=stored.params)
        controller = PlacementFlow(
            dialog, window, lambda: spec, lambda: (object_id,), change_op=stored.id
        )
        controller.start()
        assert session.wait_for_idle(30_000)
        QApplication.processEvents()
        assert controller._surface is not None
        assert controller.target == object_id
        assert controller._surface.edges == surface.edges
        assert dialog.values()["surface_distance_1"] == expression
        assert controller._set_values()
        assert dialog.values()["surface_distance_1"] == expression
        dialog._editors["surface_distance_1"].start_expression("=4")
        assert session.wait_for_idle(30_000)
        QApplication.processEvents()
        assert controller._surface is not None
        assert controller._surface.edges[0].distance == pytest.approx(4)
        assert dialog.values()["surface_distance_1"] == "=4"
        dialog._editors["x"].set_value(9)
        assert not dialog.values()["surface_anchor"]
        assert not controller.active
    finally:
        controller.dispose()
        assert session.wait_for_idle(30_000)
        dialog.close()


@pytest.mark.parametrize("exact", (False, True))
@pytest.mark.parametrize("painted", (False, True))
def test_surface_worker_snapshot_preserves_the_shown_triangles(profile, exact, painted):
    """Der UI-Anschluss kopiert den Träger vor dem Arbeiter samt nativer Flächennormale."""
    from dataclasses import replace

    import numpy as np

    from app.core.brep.kernel import Solid
    from app.core.geom.mesh import as_mesh_data
    from app.core.scene import History, evaluate
    from app.core.scene.placement import surface_at_feature
    from app.core.scene.project import new_project
    from app.ui.placement_flow import on_the_copy, surface_object_for_worker

    project = new_project("centauri-carbon-2", "petg")
    operation = "create_brep_cylinder" if exact else "create_cylinder"
    History(project.document).apply(
        "Träger", [OperationDraft(op=operation, params={"diameter": 20, "height": 20})]
    )
    source = evaluate(project.document, profile).scene.objects["obj_1"]
    body = source.mesh
    if painted:
        if isinstance(body, Solid):
            slots = tuple(int(index) % 2 for index in body.raw.face_attributes["solidon_brep_face"])
            body = body.with_triangle_slots(slots)
        else:
            body = replace(body, slots=tuple(1 for _ in range(body.triangle_count)))
        source = replace(source, mesh=body)
    snapshot = surface_object_for_worker(source)
    assert snapshot is not source and snapshot.mesh is not body
    assert isinstance(snapshot.mesh, Solid) is exact
    assert snapshot.features is source.features and snapshot.frame is source.frame
    original, copied = as_mesh_data(body), as_mesh_data(snapshot.mesh)
    assert copied.raw._cache is not original.raw._cache
    assert np.array_equal(copied.raw.vertices, original.raw.vertices)
    assert np.array_equal(copied.raw.faces, original.raw.faces)
    assert copied.slot_indices == original.slot_indices
    if exact:
        assert not snapshot.mesh.shape.IsPartner(body.shape)
        feature = next(entry for entry in source.features.values() if entry.kind == "pin")
        hit = surface_at_feature(snapshot, feature, point=(6.0, 8.0, 10.0))
        assert hit.normal == pytest.approx((0.6, 0.8, 0.0), abs=1e-6)
    keys = set(original.raw._cache.cache)
    on_the_copy(snapshot.mesh, lambda: copied.raw.vertex_faces)()
    assert set(original.raw._cache.cache) == keys


def test_bound_surface_worker_keeps_locks_after_copy_cache_eviction(flow, monkeypatch):
    """Ein großer Szenenstand verliert beim Kopieren keine Sperre eines auslaufenden Arbeiters."""
    from dataclasses import replace

    from app.ui import placement_flow as module

    original, session, viewport, _original_dialog = flow
    original.dispose()
    object_id = original.inputs_of()[0]
    spec = REGISTRY.get("insert_magnet_pocket")
    dialog = OperationDialog(spec, {object_id: "Würfel"})
    window = SimpleNamespace(
        viewport=viewport, session=session, _clear_preview=session.cancel_preview
    )
    controller = PlacementFlow(dialog, window, lambda: spec, lambda: (object_id,))
    try:
        controller.start()
        assert session.wait_for_idle(30_000)
        _point(controller, session, confirm=True)
        assert dialog.values()["surface_anchor"]
        result = controller._result
        assert result is not None
        source = result.scene.objects[object_id]
        objects = dict(result.scene.objects)
        for number in range(4):
            extra = replace(
                source,
                id=f"extra_{number}",
                mesh=source.mesh.replacing(source.mesh.raw.copy()),
            )
            objects[extra.id] = extra
        controller._result = replace(result, scene=replace(result.scene, objects=objects))
        monkeypatch.setattr(module, "WORKER_COPIES_KEPT", 2)
        scheduled, locks = [], []
        original_guard = module.on_the_copy

        def guard(mesh, compute):
            lock = next(held[2] for held in module._worker_copies.values() if held[1] is mesh)
            locks.append(lock)
            return original_guard(mesh, compute)

        def bind(*args, **kwargs):
            assert len(locks) == 5
            assert all(lock.locked() for lock in locks)
            assert len(module._worker_copies) == 2
            return None

        monkeypatch.setattr(module, "on_the_copy", guard)
        monkeypatch.setattr(module.placement, "bind_surface", bind)
        monkeypatch.setattr(
            session, "placement_async", lambda compute, *callbacks: scheduled.append(compute)
        )
        assert controller._begin_bound_surface()
        assert not any(lock.locked() for lock in locks)
        scheduled[0]()
        assert not any(lock.locked() for lock in locks)
    finally:
        controller.dispose()
        assert session.wait_for_idle(30_000)
        dialog.close()
        dialog.deleteLater()
