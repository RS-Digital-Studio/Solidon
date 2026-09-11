"""Die Mausplatzierung reicht echte Werte bis in Operation, Datei und Undo."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest
import trimesh
from PySide6.QtCore import QThread, Signal
from PySide6.QtWidgets import QApplication, QWidget

from app.core.geom.mesh import MeshData
from app.core.knowledge.parts.ops import depth_field
from app.core.registry import REGISTRY
from app.core.scene.history import OperationDraft
from app.core.scene.project import load, save
from app.ui.op_dialog import OperationDialog
from app.ui.placement_flow import PlacementFlow
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

    def __init__(self) -> None:
        super().__init__()
        from app.ui.slot_bar import SlotBar

        self.slot_bar = SlotBar(self)
        self.renderer = _Renderer()
        # Die Projektion braucht den Zoom, und der steht an der Kamera.
        self.renderer.viewport = self
        self._object_colour = "#aaaaaa"
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
    """Während der Langlochvorschau gibt es nur deren einen Übernehmen-Weg."""
    controller, session, viewport, _dialog = flow
    viewport.show()
    controller.start()
    _point(controller, session)
    qt_app.processEvents()
    assert not controller._bar.isHidden()
    before = len(session.project.document.ops)
    viewport.slot_bar.begin(20.0, 0.0, shortest_mm=6.0)
    qt_app.processEvents()
    assert all(widget.isHidden() for widget in controller._widgets())
    assert not controller.pointer(PointerEvent("release", 320, 240, button="left"))
    assert controller.active
    viewport.slot_bar.dismiss()
    qt_app.processEvents()
    assert not controller._bar.isHidden()
    assert controller.active and len(session.project.document.ops) == before


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
    seen = []
    for _ in range(6):
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
    assert seen == [controller._accept, *fields, controller._back]
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


def test_a_clicked_hole_can_really_be_accepted(qt_app: QApplication) -> None:
    """Ein angeklicktes Loch zeigt seine Maße — und lässt sich übernehmen.

    Der Knopf gibt nur frei, wenn ein **Werkzeugkörper** steht
    (`PlacementFlow.redraw`), und `placement.prepare_tool` kannte die zwei
    Operationen nicht: Der Dialog ging auf, die Maßlinien standen, die Leiste
    sagte „Übernehmen oder mit Esc die Werte bearbeiten" — und *Übernehmen* war
    grau (Fund des Reviews, 11.09.2026). Ein Text, der etwas verspricht, das
    die Oberfläche nicht einlöst, ist schlimmer als kein Text.

    Geprüft wird deshalb bis zum Ende: Fläche, Werkzeug **und** der Knopf.
    """
    from app.ui.op_dialog import OperationDialog

    window = _window_with_a_renderer()
    try:
        _a_selected_hole(window)
        dialog = window._op_dialog
        assert dialog is not None and dialog.spec.name == "resize_hole", (
            "ein angeklicktes Loch bringt seine Maße von selbst ins Bild"
        )
        flow = dialog.placement_flow
        assert flow.active and flow._surface is not None, "die Trägerfläche steht"
        assert flow._tool_context is not None, "und ihr Werkzeugkörper auch"
        assert flow._accept.isEnabled(), "sonst verspricht die Leiste etwas, das nicht geht"
    finally:
        for dialog in window.findChildren(OperationDialog):
            dialog.reject()
        QApplication.processEvents()
        window.release()


def test_the_measures_start_once_per_chosen_feature(qt_app: QApplication) -> None:
    """Der Dialog kommt einmal je Auswahl — nicht nach jedem Neuaufbau.

    Das Panel füllt sich auch nach der eigenen Operation wieder, weil die
    Auswahl stehen bleibt; ohne Merker ging der Dialog nach jedem Übernehmen
    sofort neu auf (Robert, 10.09.2026: „bei dem bohrung ändern kommt der
    dialog auch immer wieder").

    **Und die Gegenprobe steht dabei:** Eine Geste im Bild löscht den Merker,
    denn danach will man sehen, wo das Merkmal jetzt sitzt.
    """
    from app.ui.op_dialog import OperationDialog

    window = _window_with_a_renderer()
    try:
        _, hole = _a_selected_hole(window)
        assert window._measured_for == hole, "der Merker steht am gewählten Merkmal"
        for dialog in window.findChildren(OperationDialog):
            dialog.reject()
        # Das Fenster leert seine Buchhaltung erst, wenn Qt das
        # ``finished``-Signal zustellt — gewartet wird auf die Sache, nicht auf
        # eine Zahl von Durchläufen.
        for _ in range(50):
            if window._op_dialog is None:
                break
            QApplication.processEvents()
        assert window._op_dialog is None, "der erste Dialog ist wirklich zu"
        assert window._measured_for == hole, "der Merker überlebt das Zumachen"

        # **Dasselbe Merkmal noch einmal — und es bleibt bei nichts.** Gefragt
        # wird die Buchhaltung des Fensters: `isHidden()` beantwortet
        # Sichtbarkeit offscreen falsch, und ein abgewiesener Dialog lebt bis zu
        # seinem `deleteLater` im Widgetbaum weiter (`.claude/rules/ansicht.md`,
        # „Qt lügt vor dem Anzeigen").
        result = window.session.evaluate_now()
        _object_id, entry = next(iter(result.scene.objects.items()))
        window._measure_in_the_view(entry.features[hole])
        QApplication.processEvents()
        assert window._op_dialog is None, "derselbe Aufbau bringt keinen zweiten Dialog"

        # Und nach einer Geste im Bild steht er wieder zur Verfügung — der
        # Merker fällt in `_feature_step`, also bei jedem Zug am Griff.
        window._measured_for = ""
        window._measure_in_the_view(entry.features[hole])
        QApplication.processEvents()
        assert window._op_dialog is not None, "nach einer Geste im Bild stehen die Maße wieder da"
        assert window._op_dialog.spec.name == "resize_hole"
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


def test_a_drag_beside_the_handle_keeps_the_measures_at_the_feature(
    qt_app: QApplication,
) -> None:
    """Ein Zug im Bild schickt die Platzierung nicht zurück ans Zielen.

    Wer eine Bohrung wählt, bekommt ihre Maße von selbst — die Platzierung
    sitzt dabei **am Merkmal** und zielt nicht. Ein Klick daneben ist die
    ausdrückliche Ansage, woanders hinzuwollen; ein **Zug** ist das nicht.

    Bis zum 11.09.2026 zählte jedes Loslassen der linken Taste als diese
    Ansage. Wer am Bewegungsgriff ansetzte und den Pfeil verfehlte, zog damit
    die Platzierung vom Merkmal weg: Die Bohrungsvorschau klebte danach am
    Zeiger, als setze man eine neue (Robert: „beim verschieben über Gizmo
    kommen wir in die ansicht vom bohrung setzen statt dass wir es über das
    gizmo verschieben").

    Gemessen wird an der Zugschwelle des Systems — dieselbe Unterscheidung,
    die `test_dragging_the_camera_does_not_settle_the_depth` eine Stufe später
    prüft. Der Klick daneben bleibt dabei erhalten, sonst wäre die Behebung
    eine neue Sperre.
    """
    from app.ui.op_dialog import OperationDialog
    from app.ui.render.api import PointerEvent

    window = _window_with_a_renderer()
    try:
        _a_selected_hole(window)
        dialog = window._op_dialog
        assert dialog is not None and dialog.spec.name == "resize_hole"
        flow = dialog.placement_flow
        assert flow._seated_at_feature, "die Maße stehen am gewählten Merkmal"

        # Ein Zug über das halbe Bild, der keinen Griff trifft: Druck,
        # Bewegung, Loslassen weit entfernt.
        for event in (
            PointerEvent("press", 200, 200, button="left"),
            PointerEvent("move", 320, 260, buttons=frozenset({"left"})),
            PointerEvent("release", 440, 320, button="left"),
        ):
            window.viewport._on_pointer(event)
        QApplication.processEvents()
        assert flow._seated_at_feature, "ein Zug hat die Maße vom Merkmal weg ins Zielen geschickt"
        assert flow._frozen, "und die festgelegte Stelle gleich mit"

        # Ein echter Klick daneben richtet sie dagegen weiterhin neu aus.
        for event in (
            PointerEvent("press", 200, 200, button="left"),
            PointerEvent("release", 201, 200, button="left"),
        ):
            window.viewport._on_pointer(event)
        QApplication.processEvents()
        assert not flow._seated_at_feature, "der Klick daneben zielt wieder"
    finally:
        for open_dialog in window.findChildren(OperationDialog):
            open_dialog.reject()
        QApplication.processEvents()
        window.release()


def test_the_measures_come_back_after_a_gesture_in_the_view(qt_app: QApplication) -> None:
    """Nach einem Zug am Griff stehen die Maße wieder in der Szene.

    Jede Operation beendet die laufende Platzierung (`_scene_changed` ruft
    `back()`), und ihr Dialog bleibt stehen — mit den Zahlen von vorher. Der
    Merker allein reichte deshalb nicht: Er erlaubt den Neustart, und der
    prüft als Erstes, ob ein Dialog offen steht — und fand genau diesen toten.

    Gemessen am 11.09.2026, bevor der Dialog mitging: nach *Merkmal
    verschieben* `flow.active = False`, Maßlinien verborgen, Dialog sichtbar
    mit X 25,00 gegen 29,90 im Merkmalfenster (Robert: „wenn ich das langloch
    zieh, fehlen die Maße zu den kanten usw die wir bei bohrungen sehen";
    „werte im dialog und in der rechten merkmalleiste doppelt").
    """
    from app.ui.op_dialog import OperationDialog
    from app.ui.render.api import PointerEvent

    window = _window_with_a_renderer()
    try:
        _a_selected_hole(window)
        erster = window._op_dialog
        assert erster is not None and erster.placement_flow.active, "die Maße stehen"

        # Ein Zug am Pfeil des Bewegungsgriffs: eine Merkmalsoperation entsteht.
        gizmo = window.viewport._gizmo
        assert gizmo is not None, "ohne Griff prüft der Test nichts"
        window.viewport.renderer.item_picks[(400, 300)] = gizmo.items[0]
        window.viewport.renderer.item_picks[(460, 300)] = gizmo.items[0]
        for event in (
            PointerEvent("move", 400, 300),
            PointerEvent("press", 400, 300, button="left"),
            PointerEvent("move", 460, 300, buttons=frozenset({"left"})),
            PointerEvent("release", 460, 300, button="left"),
        ):
            window.viewport._on_pointer(event)
        window.session.wait_for_idle()
        for _ in range(80):
            QApplication.processEvents()

        assert [o.op for o in window.session.history.operations][-1] == "move_feature", (
            "ohne die Operation prüft der Rest nichts"
        )
        danach = window._op_dialog
        assert danach is not None, "nach der Geste stehen die Maße wieder da"
        assert danach is not erster, "und zwar in einer frischen Platzierung"
        assert danach.placement_flow.active, "sonst zeigt der Dialog nur alte Zahlen"
    finally:
        for open_dialog in window.findChildren(OperationDialog):
            open_dialog.reject()
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
