"""Gemeinsame UI-Testhilfen und Exporthilfen; der Qt-Abbau bleibt in conftest."""

from __future__ import annotations

import time
from collections.abc import Callable, Iterator
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QPoint, QPointF, Qt, Signal
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication, QMessageBox, QToolButton, QWidget

from app.core import activation
from app.core.activation import store
from app.core.scene.history import OperationDraft
from app.i18n import tr
from app.ui.dialogs import licence_lock_line
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings
from tools import function_setup

MESHES = Path(__file__).parent / "data" / "meshes"


@pytest.fixture
def session(qt_app: QApplication) -> Session:
    return Session()


@pytest.fixture
def window(qt_app: QApplication, session: Session) -> MainWindow:
    """Ein Hauptfenster ohne Körper auf der Sitzung des Tests.

    Eine Bauart für alle Fenstertests, damit zwei Aufbauten desselben Fensters
    nicht auseinanderlaufen; eingebunden mit ``from tests.ui_helpers import
    window as window`` und ebenso ``session``. Wer eine vorbereitete Sitzung
    braucht, überschreibt ``session`` in seiner Datei, und das Fenster nimmt
    sie. Einen Körper lädt jeder Test selbst (:func:`with_a_body`).
    """
    # Aufgeräumt wird zentral: ``tests/conftest.py`` wartet nach jedem Test
    # auf die Arbeiter jedes offenen Fensters.
    return MainWindow(session, UiSettings())


def shown_window(qt_app: QApplication) -> Iterator[MainWindow]:
    """Ein gezeigtes Fenster ohne Startbildschirm, für eine Fixture mit ``yield from``.

    Gezeigt, weil Qt ein Resize-Ereignis an ein verstecktes Widget erst beim
    Anzeigen zustellt — und die Geometrie der Zonen entsteht genau dort. Ein
    Test auf einem nie gezeigten Fenster misst die Vorgabegröße 640 × 480.
    Offscreen kostet das nichts.
    """
    window = MainWindow(Session(), UiSettings())
    window.show()
    window.resize(1200, 900)
    # Und der Startbildschirm muss weg: solange er im Stapel oben liegt, hat
    # der Träger darunter keine Größe, und alle Zonen lägen auf 100 Pixeln.
    window._show_start_screen(False)
    qt_app.processEvents()
    yield window
    # Aufräumen ist hier Pflicht und nicht Höflichkeit: ein gezeigtes Fenster,
    # das stehen bleibt, bekommt weiter Ereignisse — und riss siebzehn Tests
    # *nach* ``test_overlay.py`` mit ``AttributeError`` aus dem Ereignisfilter.
    window.close()
    window.deleteLater()
    qt_app.processEvents()


def with_a_body(window: MainWindow) -> str:
    """Die saubere Figur aus dem Korpus, ausgewählt wie nach einem Klick — die Vorlage für
    Form- und Skelettsitzung; ihre mittlere Kantenlänge von 2,8 mm macht nebenbei den
    Auflösungshinweis prüfbar.
    """
    window.open_path(MESHES / "clean_figure.stl")
    assert window.session.wait_for_idle(60_000)
    item = window.object_tree.tree.topLevelItem(0)
    assert item is not None
    item.setSelected(True)
    object_id = window.object_tree.selected()
    assert object_id
    return str(object_id)


def two_plates(window: MainWindow) -> tuple[str, str]:
    """Zwei Platten nebeneinander, gerechnet — die Ausgangslage."""
    window.session.start_new("centauri-carbon-2", "petg")
    window.session.history.apply(
        "Zwei Platten",
        [
            OperationDraft(op="create_box", params={"width": 40.0, "depth": 30.0, "height": 10.0}),
            OperationDraft(
                op="create_box",
                params={"width": 40.0, "depth": 30.0, "height": 10.0, "x": 60.0},
            ),
        ],
    )
    window.session.evaluate_now()
    result = window.session.last_result
    assert result is not None
    return tuple(result.scene.objects)[:2]  # type: ignore[return-value]


def top_face(window: MainWindow, object_id: str) -> str:
    """Die Kennung der Oberseite — die Stelle, an die ein Gegenstück kommt."""
    result = window.session.last_result
    assert result is not None
    entry = result.scene.objects[object_id]
    for name, feature in entry.features.items():
        if feature.kind == "face" and name.startswith("face_top"):
            return name
    raise AssertionError(f"{object_id} hat keine Oberseite — dann prüft der Test nichts")


def on_the_bore_wall(window: MainWindow, feature_id: str = "hole_1") -> tuple[float, float, float]:
    """Eine Stelle auf der Wand dieser Bohrung von ``obj_1`` — also eine, die ein Klick
    wirklich trifft.

    Nämlich auf ihrer **Wand**, nicht auf ihrer Achse: Der Mittelpunkt einer
    Bohrung liegt im Leeren, dort ist keine Oberfläche, und ein Picker kann ihn
    nicht zurückgeben. Drei Tests in ``test_analysis_ui.py`` zeigten bis zum
    22.08.2026 dorthin und waren grün, weil ``_feature_at`` damals das Merkmal
    mit dem nächsten Mittelpunkt nahm — sie prüften gegen die Rechenweise,
    nicht gegen einen Klick. Seit die Reichweite an den Dreiecken des Merkmals
    hängt (§18.5), zeigen sie hierher. Die Höhe z = 2 liegt in der Lochplatte
    aus dem Korpus (``plate_holes.stl``, aufgesetzt von z 0 bis 8).
    """
    entry = window.session.last_result.scene.objects["obj_1"]
    feature = entry.features[feature_id]
    centre = feature.params["centre"]
    radius = float(feature.params["diameter"]) * 0.5
    return (float(centre[0]) + radius, float(centre[1]), 2.0)


def wait_for_export(window: MainWindow) -> None:
    """§2.8: Exportiert wird im Arbeiter, der Test wartet also wie das Fenster.

    Nach dem Warten einmal zustellen — ``done`` ist eine Warteschlangen-
    Verbindung, und ohne ``processEvents`` kämen weder Meldung noch Befunde je
    an.

    **Zwei Runden, seit der Export erst prüft und dann schreibt** (§29,
    RM-140): Der erste Lauf endet an der Prüfung, wenn sie etwas findet; die
    Antwort darauf startet den zweiten. Wo nichts gefragt wird, ist die zweite
    Runde ein ``processEvents`` ohne Arbeiter und kostet nichts.

    **Vor jeder Runde die feine Rechnung** (RM-426): Das Fenster rechnet im
    Entwurf, und der Export bestellt erst die feine Rechnung und schreibt,
    wenn sie da ist (``_export_when_current``). Ohne dieses Warten gab es noch
    keinen Arbeiter, und die Datei fehlte.
    """
    for _ in range(2):
        assert window.session.wait_for_idle(60_000)
        QApplication.processEvents()
        worker = window._export_worker
        if worker is not None:
            worker.wait(20_000)
        QApplication.processEvents()


def wait_for_print_findings(window: MainWindow) -> None:
    """Die Berichtsanalyse läuft im Arbeiter nach der Auswertung; der Test
    wartet wie das Fenster, bis sie ihre Zeilen geliefert hat.

    ``wait_for_idle`` sieht sie nicht. Kam ihre Antwort erst später, baute sie
    die Liste des Prüfberichts neu, während der Test eine Zeile hielt — auf dem
    macOS-Läufer riss so ein ``QListWidgetItem`` unter dem Test weg.
    """
    for _round in range(5):
        worker = window._print_findings.worker
        if worker is None or not worker.isRunning():
            QApplication.processEvents()
            worker = window._print_findings.worker
            if worker is None or not worker.isRunning():
                return
        assert worker.wait(60_000), "die Berichtsanalyse endet nicht"
        QApplication.processEvents()
    worker = window._print_findings.worker
    assert worker is None or not worker.isRunning(), "die Berichtsanalyse startet immer neu"


def export_anyway(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die Frage vor dem Schreiben bejahen (§29, RM-140).

    Zwei Körper genau übereinander sind ein Befund, und seit RM-140 fragt der
    Export danach, bevor er schreibt. Ein Test, dessen Szene eine Warnung
    trägt, beantwortet sie — sonst stünde die Suite offscreen an einem modalen
    Dialog, und zwar ohne rot zu werden (siehe ``.claude/rules/oberflaeche.md``).
    """

    def trotzdem(box: QMessageBox) -> int:
        next(entry for entry in box.buttons() if entry.text() == tr("Trotzdem exportieren")).click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", trotzdem)


def expire_trial(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core import activation

    monkeypatch.setattr(activation, "_cached", activation.Activation(days_left=0))


def set_licence(monkeypatch: pytest.MonkeyPatch, state: str) -> str:
    """Den Freischaltzustand über die Nahtstelle der Suite setzen; zurück kommt der
    Sperrgrund — für ``test_licence_lock_offers.py`` und ``test_lock_reason_once.py``.
    """
    monkeypatch.setattr(store, "DEMO_UNTIL", None)
    if state == "sale_without_trial":
        monkeypatch.setattr(store, "TRIAL_FROM", None)
    cached = function_setup.licence_activation(state, date.today())
    assert getattr(cached, state), f"der Zustand {state} ließ sich nicht herstellen"
    monkeypatch.setattr(activation, "_cached", cached)
    return "" if cached.unlocked else licence_lock_line(cached)


def wait_until(app: QApplication, condition: Callable[[], bool]) -> None:
    """Stellt Qt-Ereignisse zu, bis eine Bedingung erfüllt ist oder abläuft.

    **Eine Minute, wie ``assert ….wait_for_idle(60_000)``:** Mit zehn Sekunden
    lief die Verlaufsvorschau von ``dose-mit-deckel.p3d`` auf dem Intel-Mac-
    Läufer in die Frist (Fensterauswahl 37743748780). Die Frist kostet nur,
    wenn die Bedingung ausbleibt.
    """
    deadline = time.monotonic() + 60
    while not condition() and time.monotonic() < deadline:
        app.processEvents()
        # QTest.qWait hält hier den GIL; der kalte SciPy-Import im Arbeiter
        # käme zwischen den kurzen Python-Takten sonst nicht weiter.
        time.sleep(0.01)
    assert condition(), "dialog did not reach the expected state"


class PlacementItem:
    def __init__(self, points: Any = None, capacity: int | None = None) -> None:
        self.visible = True
        self.matrix = np.eye(4)
        self.points = np.zeros((0, 3)) if points is None else np.asarray(points, dtype=float)
        #: Platz in den Puffern (Vertrag ``capacity``) — ``update_points``
        #: darf dann weniger bringen, und der Test zählt die Tausche.
        self.capacity = capacity
        self.updates = 0
        self.colour: str | None = None

    def set_visible(self, visible: bool) -> None:
        self.visible = visible

    def set_matrix(self, matrix: np.ndarray) -> None:
        self.matrix = matrix

    def set_colour(self, colour: str) -> None:
        self.colour = colour

    def update_points(self, points: Any) -> None:
        fresh = np.asarray(points, dtype=float).reshape(-1, 3)
        if self.capacity is not None and len(fresh) > self.capacity:
            raise ValueError(f"{len(fresh)} Punkte für eine Kapazität von {self.capacity}")
        self.points = fresh
        self.updates += 1


class _PlacementRenderer:
    widget = None
    #: Wird beim Aufbau gesetzt — die Projektion liest darüber den Zoom.
    viewport: Any = None

    def __init__(self) -> None:
        #: Was die Maßtinte anlegt und wieder abräumt — je Aufruf Name und
        #: Argumente, damit ein Test fragen kann, was im Bild steht.
        self.lines: list[dict[str, Any]] = []
        self.surfaces: list[dict[str, Any]] = []
        self.removed: list[Any] = []
        #: Angehaltene Bilder und Freigaben — wie ``render_fakes.RecordingRenderer``.
        #: Der Fluss hält das Bild an, solange die Fläche am Merkmal entsteht
        #: (``PlacementFlow._hold_frames``, seit ``a255b14f8``).
        self.holds: list[int] = []
        self.releases = 0

    def hold_frames(self, milliseconds: int) -> None:
        self.holds.append(int(milliseconds))

    def release_frames(self) -> None:
        self.releases += 1

    def add_surface(self, *_args: Any, **_kwargs: Any) -> PlacementItem:
        item = PlacementItem(_args[0] if _args else None, _kwargs.get("capacity"))
        self.surfaces.append({"args": _args, "item": item, **_kwargs})
        return item

    def add_lines(self, points: Any, **kwargs: Any) -> PlacementItem:
        item = PlacementItem(points, kwargs.get("capacity"))
        self.lines.append({"points": np.asarray(points, dtype=float), "item": item, **kwargs})
        return item

    def remove(self, item: Any) -> None:
        self.removed.append(item)
        self.lines = [entry for entry in self.lines if entry["item"] is not item]
        self.surfaces = [entry for entry in self.surfaces if entry["item"] is not item]

    def device_ratio(self) -> float:
        return 1.0

    def display_to_world(self, x: float, y: float, _depth: float) -> tuple[float, float, float]:
        """Die Umkehrung von ``world_to_display`` in der Ebene z = 0."""
        scale = PlacementViewport.SCALE * self.viewport.zoom()
        return ((x - 320) / scale, (240 - y) / scale, 0.0)

    def world_to_display(self, point: Any) -> tuple[float, float, float]:
        """Eine Projektion, in der auch **z** ankommt.

        Vorher fiel die Höhe weg. Für die Tiefenstufe heißt das: Mündung und
        ein Millimeter darunter landen auf demselben Bildpunkt,
        ``_axis_on_screen`` findet keine Richtung und gibt ``None`` zurück —
        die ganze Tiefenrechnung lief nie, und kein Test hat es gemerkt.
        Zehn Bildpunkte je Millimeter, in y auch für z: eine Seitenansicht.
        """
        scale = PlacementViewport.SCALE * self.viewport.zoom()
        return (
            320 + point[0] * scale,
            240 - point[1] * scale - point[2] * scale,
            0.5,
        )


class PlacementViewport(QWidget):
    cameraMoved = Signal()  # noqa: N815 — Qt-Schnittstelle
    sceneApplied = Signal()  # noqa: N815 — Qt-Schnittstelle
    previewDragged = Signal(object)  # noqa: N815 — Qt-Schnittstelle
    placementDragged = Signal(object)  # noqa: N815 — Qt-Schnittstelle
    placementDragStarted = Signal()  # noqa: N815 — Qt-Schnittstelle
    slotProposed = Signal(str, float, float)  # noqa: N815 — Qt-Schnittstelle

    def __init__(self) -> None:
        super().__init__()
        self.renderer = _PlacementRenderer()
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

    def set_placement_resume(self, handler: Any) -> None:
        self.resume = handler

    def clear_placement_resume(self, handler: Any) -> None:
        if getattr(self, "resume", None) == handler:
            self.resume = None

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


def scene_with_a_hole_and_a_fillet() -> Any:
    """Ein Körper mit einer Bohrung und einer Verrundung.

    Die kleinste Szene für die Frage „an welchem Merkmal hängt der Griff":
    Eine Bohrung lässt sich versetzen, eine Verrundung nicht — sie hängt an
    ihrer Kante, und versetzt bliebe die Kante scharf.
    """
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.scene import EvaluationResult
    from app.core.types import Feature, Scene, SceneObject

    mesh = MeshData(trimesh.creation.box(extents=(40.0, 40.0, 10.0)))
    features = {
        "hole_1": Feature(
            id="hole_1",
            kind="hole",
            provenance="detected",
            params={"diameter": 5.0, "centre": (-10.0, 0.0, 5.0), "axis": (0.0, 0.0, 1.0)},
        ),
        "fillet_1": Feature(
            id="fillet_1",
            kind="fillet",
            provenance="detected",
            params={"radius": 2.0, "centre": (10.0, 0.0, 5.0)},
        ),
        "face_1": Feature(
            id="face_1",
            kind="face",
            provenance="detected",
            params={"centre": (0.0, 0.0, 5.0), "normal": (0.0, 0.0, 1.0)},
        ),
    }
    return EvaluationResult(
        scene=Scene(
            objects={"obj_1": SceneObject(id="obj_1", name="A", mesh=mesh, features=features)}
        )
    )


def wait_for_catalogue(widget: Any) -> None:
    """Ein Lagerauftrag muss im Widget ankommen, nicht nur auf der Platte."""
    from PySide6.QtTest import QTest

    deadline = time.monotonic() + 5
    while not widget.wait_for_workers(0) and time.monotonic() < deadline:
        QTest.qWait(10)
    assert widget.wait_for_workers(0)


def send_mouse_event(
    widget, kind, global_pos, *, button=Qt.MouseButton.NoButton, buttons=Qt.MouseButton.LeftButton
):
    """Ein Qt-Mausereignis mit unverändertem Bildschirmbezug trotz Kartenbewegung."""
    event = QMouseEvent(
        kind,
        QPointF(widget.mapFromGlobal(global_pos)),
        QPointF(global_pos),
        button,
        buttons,
        Qt.KeyboardModifier.NoModifier,
    )
    QCoreApplication.sendEvent(widget, event)


def begin_card_drag(widget, delta=None):
    if delta is None:
        delta = QPoint(-210, 170)
    start = widget.mapToGlobal(widget.rect().center())
    send_mouse_event(widget, QEvent.Type.MouseButtonPress, start, button=Qt.MouseButton.LeftButton)
    send_mouse_event(widget, QEvent.Type.MouseMove, start + delta)
    return start + delta


def end_card_drag(widget, end):
    send_mouse_event(
        widget,
        QEvent.Type.MouseButtonRelease,
        end,
        button=Qt.MouseButton.LeftButton,
        buttons=Qt.MouseButton.NoButton,
    )


def settle_measure_layout(qt_app):
    """Layoutaufträge zustellen, ohne die Produktanordnung von Hand anzustoßen."""
    for _ in range(20):
        qt_app.processEvents()


def measure_more_heading(flow):
    group = flow._measure_group
    assert group is not None
    flap = group.findChild(QWidget, "feature-measure-more")
    assert flap is not None
    heading = flap.findChild(QToolButton, "sectionHeading")
    assert heading is not None
    return heading


def placement_layout(
    qt_app: QApplication, size: tuple[int, int], scale: float, corner: str, *, with_zones=False
):
    """Eine fertige Platzierungsabsicht; nur ihre Bildprojektion wird gesteuert."""
    from types import SimpleNamespace

    import trimesh
    from PySide6.QtWidgets import QFrame, QLabel, QVBoxLayout
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
    from app.ui.placement_flow import PlacementFlow

    session = Session()
    mesh = MeshData(trimesh.creation.box((40, 40, 10)))
    result = EvaluationResult(Scene(objects={"obj_1": SceneObject("obj_1", "Platte", mesh)}))
    session.last_result = result
    session.result_current = True
    viewport = PlacementViewport()
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
    flow._tool = PlacementItem()
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
