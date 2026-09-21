"""Die Mausplatzierung reicht echte Werte bis in Operation, Datei und Undo."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
import trimesh
from PySide6.QtCore import QLocale, QThread, Signal
from PySide6.QtWidgets import QApplication, QWidget

from app.core.geom.mesh import MeshData
from app.core.knowledge.parts.ops import depth_field
from app.core.registry import REGISTRY
from app.core.scene.history import OperationDraft
from app.core.scene.project import load, save
from app.ui.op_dialog import OperationDialog
from app.ui.placement_flow import _PICK_IN_MODEL, PlacementFlow
from app.ui.render.api import PointerEvent
from app.ui.session import Session


class _Item:
    def __init__(self) -> None:
        self.visible = True
        self.matrix = np.eye(4)

    def set_visible(self, visible: bool) -> None:
        self.visible = visible

    def set_matrix(self, matrix: np.ndarray) -> None:
        self.matrix = matrix


class _Renderer:
    widget = None
    #: Wird beim Aufbau gesetzt — die Projektion liest darüber den Zoom.
    viewport: Any = None

    def add_surface(self, *_args: Any, **_kwargs: Any) -> _Item:
        return _Item()

    def remove(self, _item: Any) -> None:
        pass

    def world_to_display(self, point: Any) -> tuple[float, float, float]:
        """Eine Projektion, in der auch **z** ankommt.

        Vorher fiel die Höhe weg. Für die Tiefenstufe heißt das: Mündung und
        ein Millimeter darunter landen auf demselben Bildpunkt,
        ``_axis_on_screen`` findet keine Richtung und gibt ``None`` zurück —
        die ganze Tiefenrechnung lief nie, und kein Test hat es gemerkt.
        Zehn Bildpunkte je Millimeter, in y auch für z: eine Seitenansicht.
        """
        scale = _Viewport.SCALE * self.viewport.zoom()
        return (
            320 + point[0] * scale,
            240 - point[1] * scale - point[2] * scale,
            0.5,
        )


class _Viewport(QWidget):
    cameraMoved = Signal()  # noqa: N815 — Qt-Schnittstelle
    sceneApplied = Signal()  # noqa: N815 — Qt-Schnittstelle
    previewDragged = Signal(object)  # noqa: N815 — Qt-Schnittstelle
    placementDragged = Signal(object)  # noqa: N815 — Qt-Schnittstelle
    placementDragStarted = Signal()  # noqa: N815 — Qt-Schnittstelle

    def __init__(self) -> None:
        super().__init__()
        self.renderer = _Renderer()
        #: Woran der Griff der Platzierung gerade hängt — der echte Viewport
        #: baut daran einen Bewegungsgriff; hier zählt nur die Entscheidung.
        self.gripped: Any = None
        # Die Projektion braucht den Zoom, und der steht an der Kamera.
        self.renderer.viewport = self
        self._object_colour = "#aaaaaa"
        self.waiting_slot = False
        """Ob ein gezogenes Langloch auf seine Bestätigung wartet.

        Die Attrappe trug bis zum 11.09.2026 eine echte `SlotBar`, nur damit
        der Fluss `slot_bar.active` fragen konnte — und verdeckte damit, dass
        er das überhaupt tat: Nach dem Ausbau der Leiste blieben die Tests
        hier grün, während 27 andere an `'Viewport' object has no attribute
        'slot_bar'` fielen. Eine Attrappe, die mehr kann als die Sache, prüft
        ihre eigene Nachstellung."""
        self.hit: Any = None
        self.result: Any = None
        self.pointer: Any = None
        #: Ob am Vorschaukörper ein Griff hängen soll. Der echte Viewport baut
        #: ihn an einem Aktor des Renderers; hier zählt nur die Entscheidung.
        self.preview_gizmo = False
        #: Ursprung und Reichweite des Bewegungsgriffs, oder ``None``. Ein Test,
        #: der ihn setzt, prüft, dass die Maßfelder seinen Platz frei lassen.
        self.handle: tuple[tuple[float, float, float], float] | None = None
        #: Kamerastellung und Darstellungsart — die Tiefenstufe fasst beide an.
        self.pose: tuple[Any, Any, Any, float | None] = (
            (0.0, -100.0, 0.0),
            (0.0, 0.0, 0.0),
            (0.0, 0.0, 1.0),
            None,
        )
        self.display = "solid"
        self.resize(900, 600)

    def set_preview_gizmo(self, active: bool) -> None:
        self.preview_gizmo = bool(active)

    def grip_placement(self, item: Any, *, rotation: bool = True) -> None:
        self.gripped = item

    def scene_point_of(self, point: Any, object_id: str = "") -> Any:
        return point

    def gizmo_reach(self) -> tuple[tuple[float, float, float], float] | None:
        """Wo der Bewegungsgriff sitzt — hier keiner, sofern der Test keinen setzt.

        Der echte Viewport hängt ihn an ein gewähltes Merkmal; die Platzierung
        hält seinen Platz frei, damit Pfeile und Ringe bedienbar bleiben.
        """
        return self.handle

    def set_placement_pointer(self, handler: Any) -> None:
        self.pointer = handler

    def placement_hit(self, _x: int, _y: int) -> Any:
        return self.hit

    def is_scene_applied(self, result: Any) -> bool:
        return result is not None and self.result is result

    def show_scene(self, result: Any) -> None:
        self.result = result
        self.sceneApplied.emit()

    def _section_planes(self) -> tuple[None, None]:
        return None, None

    def view_point_of(self, point: Any, _object_id: str) -> Any:
        return point

    def camera_pose(self) -> tuple[Any, Any, Any, float | None]:
        """Standort, Blickpunkt, Oben und der Parallelmaßstab — vier Werte.

        Die Tiefenstufe schwenkt quer zur Werkzeugachse und braucht dafür die
        heutige Stellung. Vier und nicht drei, wie der echte Viewport: Wer die
        Attrappe kürzer hält als den Vertrag, prüft einen Aufruf, den es so
        nicht gibt.
        """
        return self.pose

    def set_camera_pose(
        self, position: Any, focal_point: Any, view_up: Any, parallel_scale: float | None = None
    ) -> None:
        self.pose = (position, focal_point, view_up, parallel_scale)

    def settle_camera(self) -> None:
        pass

    #: Bildpunkte je Millimeter — dieselbe Zahl, mit der ``world_to_display``
    #: projiziert. Zwei verschiedene Maßstäbe in einer Attrappe ergäben eine
    #: Tiefe, die niemand herleiten kann, und einen Test, dessen Sollwert aus
    #: dem Prüfling stammt.
    #:
    #: **Und ausdrücklich nicht zehn.** Die Tiefenstufe fällt ohne Maßstab auf
    #: einen Zehntelmillimeter je Bildpunkt zurück, und bei zehn Bildpunkten je
    #: Millimeter ist der Rückfall vom Ergebnis der Rechnung nicht zu
    #: unterscheiden: Die Gegenprobe blieb damit grün, als die Rechnung durch
    #: genau diesen Rückfall ersetzt wurde. Acht macht beide Wege sichtbar.
    SCALE = 8.0

    #: Der Abstand, bei dem ``SCALE`` gilt. Die echte Ansicht rechnet
    #: perspektivisch (``settings.projection`` steht auf ``perspective``), der
    #: Maßstab hängt dort also am Kameraabstand — und genau das muss die
    #: Attrappe können, sonst ist ein eingefrorener Maßstab von einem je
    #: Bewegung gemessenen nicht zu unterscheiden.
    REFERENCE_DISTANCE = 100.0

    def zoom(self) -> float:
        """Wie stark das Bild gerade vergrößert ist — eins am Bezugsabstand."""
        position = np.asarray(self.pose[0], dtype=np.float64)
        focus = np.asarray(self.pose[1], dtype=np.float64)
        away = float(np.linalg.norm(position - focus))
        if away < 1e-9:
            return 1.0
        return self.REFERENCE_DISTANCE / away

    def _pixels_per_mm_at(self, _point: Any) -> float | None:
        """Der Maßstab an einer Stelle — mit dem Abstand der Kamera.

        Die Tiefenstufe rechnet daraus, wie weit ein Bildpunkt Zug die Bohrung
        wachsen lässt. Was er **nicht** sein darf, ist ``None`` an einer Stelle,
        an der der echte Viewport eine Zahl liefert — sonst prüft der Test den
        Rückfall statt der Rechnung.
        """
        return self.SCALE * self.zoom()

    def set_display_mode(self, mode: str) -> None:
        self.display = mode

    @property
    def display_mode(self) -> str:
        """Eine **Property**, wie im Viewport (``viewport.py``).

        Als Methode gab die Attrappe eine gebundene Methode zurück, und die
        Platzierung merkte sie sich als Darstellungsart, um sie am Ende
        zurückzustellen — geprüft war damit nichts von beidem.
        """
        return self.display

    def _device_ratio(self) -> float:
        return 1.0

    def _draw(self) -> None:
        pass

    def slot_drag_waits(self) -> bool:
        return self.waiting_slot


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

    def add_surface(*_args: Any, **kwargs: Any) -> _Item:
        item = _Item()
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


@pytest.fixture
def flow(qt_app: QApplication) -> Any:
    session = Session()
    viewport = _Viewport()
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
        viewport.close()
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
    QTest.keyClick(viewport, Qt.Key.Key_Escape)
    assert not controller.active
    assert controller._reference_pick is None
    assert session.project.document is document


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
    erwartet = (300 - mouth[1]) / _Viewport.SCALE
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
        return (y - float(mouth[1])) / (_Viewport.SCALE * viewport.zoom())

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

    **Für die fünf Grundkörper nicht.** ``start`` versteckt den Dialog, und
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
            _point(controller, session)
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
    requests = []
    monkeypatch.setattr(
        session, "placement_async", lambda compute, then, failed: requests.append((compute, then))
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
    """Esc aus dem QLineEdit beider Maßgruppen erhält Werte und erzeugt keine Operation."""
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
    viewport = _Viewport()
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
    viewport = _Viewport()
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
    viewport = _Viewport()
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
    from render_fakes import RecordingRenderer

    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    window.viewport.renderer = RecordingRenderer(size=(900, 600))
    return window


def _a_selected_hole(window):
    """Öffnet die Platte, wählt ihre erste Bohrung und wartet die Fläche ab."""
    from PySide6.QtWidgets import QApplication

    window.open_path(MESHES / "plate_holes.stl")
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
        assert flow.pointer(PointerEvent("move", 200, 200)), (
            "nur die freie Bewegung bleibt bei ihr — keine Vorschau am Zeiger"
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
    """Escape ist der Ausgang aus den Maßen — und verwirft, was noch kein Schritt ist.

    Die stille Platzierung hat kein Fenster und kein Kreuz. Bis zum
    11.09.2026 fing ihr Ereignisfilter Escape nur ab, solange kein Langlochzug
    wartete; wartete einer, ließ sie die Taste durch, und die ging eine Stufe
    Auswahl zurück — die Maße blieben stehen (Robert: „kann auch den modus
    nicht mehr verlassen"). Jetzt gilt die Stufung des Fensters: erst das
    Werkzeug, dann die Auswahl.
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
        assert window.object_tree.selected_feature() == hole, (
            "die Auswahl bleibt — erst das Werkzeug"
        )

        window._escape()
        QApplication.processEvents()
        assert window.object_tree.selected_feature() is None, (
            "das zweite Escape geht die Stufe zurück"
        )
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
    assert not controller._accept_pending
    assert session.wait_for_idle(30_000)
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
    assert not controller._accept_pending
    QTest.keyClick(editor, Qt.Key.Key_Escape)
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
    viewport = _Viewport()
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
        assert controller._accept_pending is not preview_required
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
    from PySide6.QtCore import Qt
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
        QTest.keyClick(editor, Qt.Key.Key_Return)
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
        assert window.viewport._slot_handle is None, (
            "die Auswahl allein zeigt nur, was gewählt ist (Robert, 11.09.2026)"
        )
        # **Im Bild einstellen** bringt Maße und Griffe zusammen.
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
    """Der gemeinsame Abbruch verwirft den Entwurf und erhält die Auswahl."""
    window = _window_with_a_renderer()
    try:
        panel = window.feature_panel
        _, _hole = _a_selected_hole(window)
        # ``isHidden``: die Knopfzeile hängt unter dem Rollbereich des Docks
        # und nicht mehr am Panel (13.09.2026, ``FeaturePanel.footer``).
        assert panel._cancel.isHidden(), "der Abschluss steht ausschließlich an den Maßen"
        hole, flow = _a_pulled_slot(window)
        assert panel._cancel.isHidden() and panel._apply.isHidden()
        assert not flow._measure_cancel.isHidden(), "ein gemeinsamer Abschluss an den Maßen"
        steps = len(window.session.history.operations)

        flow._measure_cancel.click()
        QApplication.processEvents()
        assert not flow.active, "die Maße im Bild sind zu"
        assert not window.viewport.slot_drag_waits(), "der Zug ist verworfen"
        assert len(window.session.history.operations) == steps, "und gerechnet ist nichts"
        assert window.viewport._selected_feature == hole, "die Auswahl bleibt"
        assert panel._cancel.isHidden(), "der Knopf geht mit den Maßen"
        assert not panel._in_view.isHidden(), "der Weg zurück ins Bild steht"
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
        assert window.viewport._slot_handle is None, "fremde Griffe fehlen am Größenentwurf"
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
            assert flow.dialog.begun and window.viewport._placement_grip is grip and grip.pressing
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
        assert "Vorgabemaß" in depth.toolTip()
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
        assert not flow._canvas.isVisibleTo(window.viewport)
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

        controller.back()
        assert dialog._placement_hint.isHidden(), "und danach wieder nicht"
    finally:
        controller.dispose()
        dialog.deleteLater()
