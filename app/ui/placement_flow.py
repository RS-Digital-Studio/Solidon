"""Werte eingeben, auf eine Fläche zeigen und einen einzelnen Schritt übernehmen.

Die Oberfläche hält ausschließlich eine vergängliche Raumlage. Bezugskanten,
Abstände und Werkzeugkörper berechnet der Kern; die vorhandene Operation
bleibt der einzige Weg ins Dokument.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

import numpy as np
from PySide6.QtCore import QEvent, QObject, QPoint, QPointF, QRect, QSignalBlocker, Qt, QTimer
from PySide6.QtGui import (
    QColor,
    QKeyEvent,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QPolygonF,
    QRegion,
)
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QWidget,
)
from shiboken6 import isValid

from app.core import expressions
from app.core.errors import AppError, ValidationError
from app.core.geom.mesh import as_mesh_data, ray_hit_distances
from app.core.geom.transform import snap_to_marks
from app.core.knowledge.parts.ops import depth_field, normal_fields, placement_fields
from app.core.knowledge.profiles import for_object
from app.core.log import get_logger
from app.core.registry import OperationSpec
from app.core.scene import placement
from app.core.types import Feature, SceneObject, Vec3
from app.core.units import EPS_GEOM
from app.i18n import tr
from app.ui.labels import LengthSpin, feature_name, length
from app.ui.leash import stop_watching_the_dying
from app.ui.op_dialog import OperationDialog
from app.ui.palette import DIFF_PALETTES
from app.ui.render.api import Item, PointerEvent, SurfaceStyle
from app.ui.style import NORMAL, ROOMY, SPACE

#: Wie nah der Zeiger einer Marke kommen muss, damit sie ihn hält — in
#: Bildpunkten, wie jede Fangweite der Oberfläche (siehe ansicht.md,
#: "Die Fangweite gehört in Bildpunkte").
SNAP_PIXELS = 12.0

#: Die flachste Tiefe, auf die der Zug fallen darf. **Nicht null**, denn dort
#: kippt die Bedeutung: ``depth = 0`` heißt „durch das ganze Teil" (siehe das
#: Schema von ``drill_hole``). Wer nach oben zieht, um flacher zu werden, führe
#: sonst am Ende des Wegs geradewegs hindurch. Ein Zehntelmillimeter ist unter
#: jeder Schichthöhe und damit ohne eigene Wirkung; die Null bleibt über das
#: Maßfeld erreichbar, wo sie ausgeschrieben dasteht.
LEAST_DEPTH_MM = 0.1

_log = get_logger(__name__)


def starts_by_itself(spec: OperationSpec) -> bool:
    """Ob dieser Dialog von selbst in die Platzierung geht.

    **Wer eine Fläche braucht, bekommt sie sofort** — ein Baustein, eine
    Beschriftung, eine Bohrung sitzen auf etwas, und der zweite Klick auf
    „Im Modell platzieren" bot nur an, was die Operation ohnehin verlangt
    (Robert, 09.09.2026: „man soll keinen extra Button klicken müssen").

    **Ein Erzeuger braucht keine.** Quader, Zylinder, Kegel, Kugel und Ring
    entstehen aus ihren eigenen Maßen an ihren eigenen Koordinaten; die
    Platzierung ist dort ein Angebot und keine Bedingung. Startet sie von
    selbst, verschwindet der Dialog — und mit ihm Breite, Tiefe und Höhe, die
    nirgends sonst stehen. Wer die Maße ändern wollte, musste Escape drücken,
    tippen und neu platzieren (Robert, 09.09.2026: „wer nur Maße tippen will,
    ignoriert ihn").

    Stattdessen zeigt dort die Live-Vorschau den Körper, sobald der Dialog
    offen ist — sie rechnet ihn ohnehin (``Session.preview_async``), und
    ``OperationDialog.request`` überspringt sie nur, solange die Platzierung
    läuft. Der Knopf bleibt: Wer den Quader auf eine Fläche setzen will,
    findet den Weg an derselben Stelle wie zuvor.

    Gefragt wird nach ``consumes``, nicht nach einer Namensliste: Was nichts
    verbraucht, hat nichts, worauf es sitzen könnte.
    """
    return spec.consumes != 0 or spec.takes_whole_scene


def _grips_its_preview(spec: OperationSpec) -> bool:
    """Ob die Vorschau dieser Operation einen Griff bekommt.

    Genau dort, wo der Dialog offen bleibt und die Live-Vorschau den Körper
    zeigt: an den Erzeugern. Wer in die Platzierung geht, zielt mit dem
    Fadenkreuz — zwei Gesten für dieselbe Stelle wären eine zu viel.

    Und nur, wo es Felder gibt, in die der Zug schreiben kann: ``x/y/z`` für
    den Ort, ``nx/ny/nz`` für die Richtung, ``angle`` für die Drehung. Ein
    Griff über einem Körper, dessen Lage nirgends steht, bewegte ein Bild.
    """
    if starts_by_itself(spec):
        return False
    names = {entry.name for entry in spec.params.spec()}
    return {"x", "y", "z", "nx", "ny", "nz", "angle"} <= names


class _Dimensions(QWidget):
    """Maßpfeile im Bildraum, mit getrennten erreichbaren Zahlenfeldern."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.lines: list[tuple[QPointF, QPointF]] = []
        self.leaders: list[tuple[QPointF, QPointF]] = []
        #: Der Umriss, mit dem das Werkzeug die Oberfläche trifft — ein
        #: geschlossener Zug in Bildkoordinaten. Bei einer Bohrung der Kreis
        #: ihrer Mündung (Befund Robert, 09.09.2026: „es reicht mir, wenn ich
        #: den Kreis auf der Oberfläche in Orange sehe").
        self.outline: list[QPointF] = []
        #: Seine Farbe. Sie kommt aus derselben Palette wie der abgetragene
        #: Anteil der Vorschau — was hier verschwinden wird, ist dort schon
        #: orange, und zwei Farben für dieselbe Aussage wären eine zu viel.
        self.outline_colour: QColor | None = None
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAttribute(Qt.WidgetAttribute.WA_OpaquePaintEvent)
        self.hide()

    @staticmethod
    def _arrowheads(start: QPointF, end: QPointF) -> tuple[QPolygonF, ...]:
        """Zeichnung und Maske verwenden dieselben Pfeilspitzen."""
        vector = end - start
        size = math.hypot(vector.x(), vector.y())
        if size < 1.0:
            return ()
        unit = vector / size
        sideways = QPointF(-unit.y(), unit.x())
        heads = []
        for point, direction in ((start, unit), (end, -unit)):
            base = point + direction * (2 * SPACE)
            heads.append(QPolygonF([point, base + sideways * SPACE, base - sideways * SPACE]))
        return tuple(heads)

    def refresh(self, exclusions: tuple[QRect, ...] = ()) -> None:
        """Nur die wirkliche Tinte belegen; alles andere gehört dem nativen Renderfenster.

        Ein vollflächiges Kind mit WA_NoSystemBackground blitzt hier den alten
        Qt-Backingstore über das native Renderfenster, einschließlich längst
        verborgener Ladeanzeige. Wie bei den Overlaykarten beschränkt eine
        Maske die Fläche.
        Innerhalb dieser kleinen Maske wird jeder Pixel definiert neu gezeichnet.
        """
        strokes = QPainterPath()
        ink = QPainterPath()
        for start, end in (*self.lines, *self.leaders):
            strokes.moveTo(start)
            strokes.lineTo(end)
        stroker = QPainterPathStroker()
        stroker.setWidth(6.0)  # Vier Pixel Unterlage und beidseitig ein Pixel Kantenglättung.
        ink = ink.united(stroker.createStroke(strokes))
        for start, end in self.leaders:
            for point in (start, end):
                marker = QPainterPath()
                marker.addEllipse(point, 5.0, 5.0)
                ink = ink.united(marker)
        if len(self.outline) >= 3:
            ring = QPainterPath()
            ring.addPolygon(QPolygonF(self.outline))
            ring.closeSubpath()
            stroker.setWidth(6.0)
            ink = ink.united(stroker.createStroke(ring))
        for start, end in self.lines:
            for polygon in self._arrowheads(start, end):
                head = QPainterPath()
                head.addPolygon(polygon)
                head.closeSubpath()
                stroker.setWidth(2.0)
                ink = ink.united(head).united(stroker.createStroke(head))
        area = QPainterPath()
        area.addRect(self.rect())
        ink = ink.intersected(area)
        mask = QRegion(ink.toFillPolygon().toPolygon(), Qt.FillRule.WindingFill)
        # Über nativen Renderflächen reicht raise_ der Geschwister nicht aus:
        # Zahlen und Beschriftungen bleiben in jeder Stapelreihenfolge frei.
        for rect in exclusions:
            mask = mask.subtracted(QRegion(rect))
        if mask.isEmpty():
            self.hide()  # Eine leere QWidget-Maske würde das ganze Rechteck freigeben.
            return
        self.setMask(mask)
        self.show()
        self.raise_()
        self.update()

    def paintEvent(self, _event: Any) -> None:  # noqa: N802 — Qt-Schnittstelle
        painter = QPainter(self)
        painter.setClipRegion(self.mask())
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        colour = self.palette().text().color()
        backdrop = self.palette().window().color()
        painter.fillRect(self.rect(), backdrop)
        if len(self.outline) >= 3 and self.outline_colour is not None:
            ring = QPolygonF(self.outline)
            # Dieselbe Unterlage wie bei den Maßlinien: Der Umriss liegt auf
            # dem Modell und muss auf hellem wie dunklem Material lesbar sein.
            painter.setPen(QPen(backdrop, 4.0))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawPolygon(ring)
            painter.setPen(QPen(self.outline_colour, 2.0))
            painter.drawPolygon(ring)
        for start, end in self.leaders:
            # Zuordnungslinien haben keine Maßpfeile. **Eine Marke an jedem
            # Ende**, gefüllt und beide gleich groß: Der Strich verbindet dann
            # sichtbar zwei Punkte, statt irgendwo am Feld anzusetzen. Bis zum
            # 10.09.2026 war er ein Punktstrich von einem Bildpunkt mit einer
            # hohlen Marke — im Fenster kaum zu finden, und bei fünf Feldern
            # nebeneinander gehörte jede Zahl zu jeder Linie (Robert:
            # „es war bisschen undeutlich welcher wert zu welcher linie
            # gehört"). Gestrichelt statt gepunktet aus demselben Grund; sie
            # bleibt damit von einer Maßlinie unterscheidbar, die durchgezogen
            # ist und Pfeile trägt (Regel 18 — nicht die Farbe trennt sie).
            painter.setPen(QPen(backdrop, 4.0))
            painter.drawLine(start, end)
            painter.setPen(QPen(colour, 1.5, Qt.PenStyle.DashLine))
            painter.drawLine(start, end)
            painter.setPen(QPen(backdrop, 1.5))
            painter.setBrush(colour)
            for point in (start, end):
                painter.drawEllipse(point, 3.5, 3.5)
        for start, end in self.lines:
            # Eine helle/dunkle Unterlage hält dieselbe Linie auf dem Modell
            # und auf dem Hintergrund lesbar, ohne Farbe als einzige Kodierung.
            painter.setPen(QPen(backdrop, 4.0))
            painter.drawLine(start, end)
            painter.setPen(QPen(colour, 1.5))
            painter.drawLine(start, end)
            painter.setBrush(colour)
            for polygon in self._arrowheads(start, end):
                painter.drawPolygon(polygon)
        painter.end()


class PlacementFlow(QObject):
    """Eine laufende Platzierung gehört genau einem vorhandenen Operationsdialog."""

    def __init__(
        self,
        dialog: OperationDialog,
        window: Any,
        spec_of: Callable[[], Any],
        inputs_of: Callable[[], tuple[str, ...]],
        *,
        change_op: int | None = None,
    ) -> None:
        super().__init__(dialog)
        self.dialog = dialog
        self.window = window
        self.viewport = window.viewport
        self.session = window.session
        self.spec_of = spec_of
        self.inputs_of = inputs_of
        self._change_op = change_op
        self._result: Any = None
        self._showing_input = False
        self._epoch = 0
        self.active = False
        self._disposed = False
        overlay = getattr(window, "overlay", None)
        self._overlay_zones = tuple(
            zone
            for role in ("left", "right", "bottom")
            if isinstance(zone := getattr(overlay, role, None), QWidget)
        )
        for zone in self._overlay_zones:
            zone.installEventFilter(self)
        self._serial = 0
        self._pending: tuple[int, int, bool] | None = None
        self._surface_busy = False
        self._tool_busy = False
        self._tool_again = False
        self._tool: Item | None = None
        self._addition: Item | None = None
        self._tool_context: placement.PlacementTool | None = None
        self._tool_key = ""
        self._prepared: Any = None
        self._prepared_mesh: Any = None
        self._patch_faces: frozenset[int] = frozenset()
        self._surface: Any = None
        self._object_id = ""
        self._centre_id = ""
        self._frozen = False
        self._distance_valid = True
        self._commit_pending = False
        self._updating = False
        #: Ob die Tiefenstufe läuft — Stufe 2 der Platzierung. Der Klick legt
        #: die Stelle fest, danach zieht die Maus die Tiefe (Robert,
        #: 09.09.2026: „wenn wir klicken wollen wir die bohrung von der
        #: seitenansicht sehen und dann die tiefe runterziehen").
        self._seated_at_feature = False
        """Ob die Stelle einem vorhandenen Merkmal gehört.

        **Dann zielt der Zeiger nicht.** Wer ein Loch anklickt, will seine Maße
        sehen und ändern; die Stelle steht schon, und eine Mausbewegung darüber
        verschob sie samt aller Maßlinien unter der Hand (Robert, 11.09.2026:
        „die maße im viewport gehen beim bearbeiten von dem loch jetzt von dem
        mauszeiger aus, wir wollen aber bei der bohrung das mittelloch").

        Der Merker beginnt beim Rechnen der Trägerfläche und fällt erst bei
        einem **Klick** — der ist die ausdrückliche Ansage, das Loch woanders
        hinzusetzen. Beim Setzen einer neuen Bohrung wird er nie gesetzt, dort
        ändert sich nichts."""
        self._deepening = False
        #: Ob die Tiefe angehalten ist. Der Klick in der Tiefenstufe friert sie
        #: ein, damit die Maus sie nicht weiter verstellt, während man zum Knopf
        #: fährt oder die Zahl nachbessert.
        self._depth_set = False
        #: Der Bildpunkt, an dem das Ziehen begann, und der Wert dazu. Gemessen
        #: wird die Strecke von dort, nicht von Bild zu Bild: Eine Summe aus
        #: Schritten driftet, sobald ein Ereignis ausfällt.
        #: Wie viele Millimeter ein Bildpunkt Zug bedeutet. Wird beim Beginn
        #: aus dem Maßstab der Ansicht gesetzt, damit der Zug am kleinen wie am
        #: großen Teil dasselbe Gefühl hat.
        self._depth_per_pixel = 0.1
        #: Wo die linke Taste in der Tiefenstufe gedrückt wurde — die Strecke
        #: bis zum Loslassen entscheidet, ob es ein Klick war oder ein Zug an
        #: der Kamera.
        self._pressed_at: tuple[int, int] | None = None
        #: Die Darstellungsart vor der Tiefenstufe — geliehen, nicht gesetzt.
        self._display_before: str | None = None
        #: Und die Kamerastellung davor, aus demselben Grund: Der Schwenk quer
        #: zur Werkzeugachse gehört der Stufe, nicht dem Kunden.
        self._camera_before: tuple[Any, Any, Any, float | None] | None = None
        self._canvas = _Dimensions(self.viewport)
        self._bar = QFrame(self.viewport)
        self._bar.setObjectName("surface_placement_bar")
        self._bar.setAutoFillBackground(True)
        layout = QHBoxLayout(self._bar)
        layout.setContentsMargins(ROOMY, NORMAL, ROOMY, NORMAL)
        self._title = QLabel(str(self.spec_of().title), self._bar)
        layout.addWidget(self._title)
        self._note = QLabel(tr("Auf eine Oberfläche zeigen."), self._bar)
        self._note.setWordWrap(True)
        layout.addWidget(self._note, 1)
        self._tool_legend = QLabel(self._bar)
        self._tool_legend.hide()
        layout.addWidget(self._tool_legend)
        self._back = QPushButton(tr("Werte bearbeiten"), self._bar)
        self._back.clicked.connect(self.back)
        layout.addWidget(self._back)
        self._accept = QPushButton(tr("Position übernehmen"), self._bar)
        self._accept.clicked.connect(self.accept)
        layout.addWidget(self._accept)
        self._bar.hide()
        self._measures = [LengthSpin(self.viewport), LengthSpin(self.viewport)]
        for index, field in enumerate(self._measures):
            field.setObjectName(f"placement_distance_{index + 1}")
            field.setAccessibleName(
                tr("Abstand zu Kante {number}").replace("{number}", str(index + 1))
            )
            field.setToolTip(tr("Abstand ändern; die Position bleibt dabei auf dieser Fläche."))
            field.installEventFilter(self)
            field.valueChangedMm.connect(self._distance_changed)
            field.hide()
        #: Die Tiefe als Zahl — dasselbe Feld wie die Kantenabstände, damit
        #: Ausdruck und Einheitenumschaltung mitkommen. Sie steht in Stufe 3 an
        #: der Stelle der Kantenmaße: Die zeigen die Fläche, auf der gesetzt
        #: wurde, und die ist dort entschieden (Robert, 09.09.2026: „die maße
        #: fehlen auch bzw zeigen noch die von der Fläche wo wir die Bohrung
        #: gesetzt haben").
        self._depth_measure = LengthSpin(self.viewport)
        self._depth_measure.setObjectName("placement_depth")
        self._depth_measure.setAccessibleName(tr("Tiefe der Bohrung"))
        self._depth_measure.setToolTip(tr("Tiefe eintippen oder mit der Maus ziehen."))
        self._depth_measure.installEventFilter(self)
        self._depth_measure.valueChangedMm.connect(self._depth_typed)
        self._depth_measure.hide()
        #: Was an Wand stehen bleibt — das Gegenstück zur Tiefe. Eine Zahl und
        #: kein Feld: Sie folgt aus Tiefe und Materialstärke und ist nichts,
        #: was man eintippt.
        self._rest = QLabel(self.viewport)
        self._rest.setObjectName("placement_rest")
        self._rest.setAutoFillBackground(True)
        self._rest.hide()
        self._centre = QLabel(self.viewport)
        self._centre.setAutoFillBackground(True)
        self._centre.hide()
        self._centre_measures = [LengthSpin(self.viewport), LengthSpin(self.viewport)]
        for index, field in enumerate(self._centre_measures):
            field.setObjectName(f"placement_centre_distance_{index + 1}")
            field.setAccessibleName(
                tr("Abstand zum Mittelpunkt – Richtung {number}").format(number=index + 1)
            )
            field.setPrefix(tr("Mitte {number}: ").format(number=index + 1))
            field.setToolTip(tr("Der Maßpfeil zeigt die Richtung auf dieser Fläche."))
            field.installEventFilter(self)
            field.valueChangedMm.connect(self._centre_changed)
            field.hide()
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._next_surface)
        dialog.surfaceRequested.connect(self.start)
        dialog.valuesChanged.connect(self._values_changed)
        dialog.finished.connect(self.dispose)
        self.viewport.installEventFilter(self)
        render_widget = getattr(self.viewport.renderer, "widget", None)
        if render_widget is not None:
            render_widget.installEventFilter(self)
        self.viewport.cameraMoved.connect(self.redraw)
        self.session.sceneChanged.connect(self._scene_changed)
        self.session.projectChanged.connect(self._document_changed)
        self.viewport.sceneApplied.connect(self._scene_applied)
        self.viewport.previewDragged.connect(self._dragged_in_preview)
        self.viewport.set_preview_gizmo(_grips_its_preview(self.spec_of()))
        self.refresh_available()
        # **Wer eine platzierbare Operation wählt, will platzieren.** Der Weg
        # dorthin war ein zweiter Klick auf „Im Modell platzieren" — ein Knopf,
        # der genau das anbietet, was die Operation ohnehin verlangt (Befund
        # Robert, 09.09.2026: „man soll keinen extra Button klicken müssen").
        # Der Dialog bleibt der andere Weg: Esc bringt ihn zurück, und der
        # Knopf steht weiter da, für den Rückweg aus dem Rückweg.
        #
        # **Nicht beim Ändern eines Schritts.** Dort ist die Stelle längst
        # gewählt, und wer den Durchmesser nachbessert, will kein Fadenkreuz.
        # Und nicht sofort, sondern eine Runde später: Der Dialog ist hier
        # noch nicht gezeigt, und ``start`` versteckt ihn.
        if (
            starts_by_itself(self.spec_of())
            and self._change_op is None
            and self.dialog.surface_button.isEnabled()
        ):
            QTimer.singleShot(0, self._start_if_still_possible)

    @property
    def target(self) -> str:
        """Der Körper, auf dem die zuletzt übernommenen Zahlen liegen."""
        return self._object_id

    def refresh_available(self) -> None:
        """Nur fachlich platzierbare Operationen bieten den Einstieg an."""
        supported = placement.supports_surface_placement(self.spec_of())
        self.dialog.surface_button.setVisible(supported)
        result = self.session.last_result
        available = (
            self.viewport.renderer is not None
            and self.session.result_current
            and result is not None
            and (self._change_op is not None or (result.complete and bool(result.scene.objects)))
        )
        self.dialog.surface_button.setEnabled(supported and available)
        if self.active and not supported:
            self.back()

    def _start_if_still_possible(self) -> None:
        """Der Selbststart eine Ereignisrunde später — falls er dann noch gilt.

        Zwischen dem Aufbau und dieser Runde kann alles passiert sein: Der
        Dialog wurde geschlossen, die Auswertung lief neu, jemand hat schon
        selbst geklickt. Geprüft wird deshalb erneut, statt sich auf den
        Zustand von vorhin zu verlassen.
        """
        if self._disposed or self.active or not isValid(self):
            return
        if not self.dialog.isVisible():
            return
        self.start()

    def start(self) -> None:
        self.refresh_available()
        if self._disposed or not self.dialog.surface_button.isEnabled():
            return
        self.active = True
        self._epoch += 1
        self._result = self.session.last_result if self._change_op is None else None
        self._frozen = False
        self._distance_valid = True
        self._commit_pending = False
        self._surface = None
        self._serial += 1
        # **Und der Knopf sagt wieder, was er tut.** Zurückgesetzt wurde sein
        # Text nur beim Verlassen der Tiefenstufe; wer sie über Escape verließ
        # und neu begann, las „Weiter zur Tiefe" über einer Fläche, auf der
        # noch nichts steht.
        self._accept.setText(tr("Weiter zur Tiefe") if self.deepens() else tr("Übernehmen"))
        # **Der Dialog bleibt stehen** (Robert, 09.09.2026: „wenn ich auf
        # bohrung setzen klicke sollte der dialog übrigens da bleiben"). Er
        # trug bis dahin die Maße, die man beim Platzieren braucht, und
        # verschwand genau dann, wenn man sie sehen wollte; wer den
        # Durchmesser nachbessern wollte, musste Escape drücken, tippen und
        # neu zielen.
        self.window._clear_preview()
        self.viewport.set_placement_pointer(self.pointer)
        self._note.setText(tr("Klicken: platzieren · Abstand ändern: Maßfeld · Esc: zurück"))
        self._bar.show()
        self._accept.setEnabled(False)
        self.viewport.setFocus(Qt.FocusReason.OtherFocusReason)
        if self._change_op is None:
            self._request_tool()
            self._begin_at_feature()
        else:
            epoch = self._epoch
            self._note.setText(tr("Die Oberfläche vor diesem Schritt wird vorbereitet …"))

            def ready(result: Any) -> None:
                if not isValid(self) or self._disposed or not self.active or epoch != self._epoch:
                    return
                if result is None or not result.complete:
                    self._invalid(tr("Die Eingabe dieses Schritts prüfen und erneut platzieren."))
                    return
                self._result = result
                self._showing_input = True
                self.viewport.show_scene(result)
                self._request_tool()

            self.session.placement_before(self._change_op, ready, lambda _detail: ready(None))
        self.redraw()

    def back(self) -> None:
        """Escape behält alle Werte, übernimmt aber keinen Schritt.

        Auch kein Ziel: ``run_chosen`` verzweigt an :attr:`target`, und ein
        stehen gebliebener Körper machte aus drei gewählten Körpern still
        einen — der Dialog bohrte dann nur ihn. Nur :meth:`accept` trägt das
        Ziel bis zum Dialog.
        """
        if self._disposed:
            return
        self._stop()
        self._object_id = ""
        self.dialog.show()
        self.dialog.raise_()
        self.dialog.activateWindow()
        self.dialog.valuesChanged.emit()

    def _stop(self) -> None:
        self.active = False
        self._epoch += 1
        self._serial += 1
        self._pending = None
        self._commit_pending = False
        self._leave_depth()
        self._timer.stop()
        self.viewport.set_placement_pointer(None)
        for widget in self._widgets():
            widget.hide()
        self._remove_tools()
        self._tool_context = None
        self._tool_key = ""
        if self._showing_input:
            self._showing_input = False
            self.viewport.show_scene(self.session.last_result)
        self._result = None
        self.viewport._draw()

    def _leave_depth(self) -> None:
        """Die Tiefenstufe verlassen und die geliehene Ansicht zurückgeben.

        Die Darstellungsart ist eine Einstellung des Nutzers (`ansicht.md`,
        „Was die Ansicht sich merkt"); durchscheinend war sie hier geliehen,
        und wer leiht, gibt zurück — auch beim Abbruch über Escape.
        """
        if not self._deepening:
            return
        self._deepening = False
        self._depth_set = False
        if self._display_before is not None:
            self.viewport.set_display_mode(self._display_before)
        self._display_before = None
        # **Und die Kamera genauso.** Sie war ebenso geliehen — der Schwenk
        # quer zur Achse gehört der Stufe, nicht dem Kunden. Der Docstring
        # versprach das von Anfang an („auch beim Abbruch über Escape"), und
        # zurückgestellt wurde nur die Darstellungsart: Nach Escape blieb die
        # Ansicht im Seitenschwenk stehen.
        if self._camera_before is not None and self.viewport.renderer is not None:
            position, focus, up, scale = self._camera_before
            self.viewport.set_camera_pose(position, focus, up, scale)
            self.viewport.settle_camera()
        self._camera_before = None
        self._accept.setText(tr("Position übernehmen"))

    def _remove_tools(self) -> None:
        """Schnitt und Anbau gehören demselben vorübergehenden Werkzeug."""
        renderer = self.viewport.renderer
        if renderer is not None:
            for item in (self._tool, self._addition):
                if item is not None:
                    renderer.remove(item)
        self._tool = None
        self._addition = None
        self._tool_legend.hide()

    def dispose(self, _code: int = 0) -> None:
        if self._disposed:
            return
        self._stop()
        # **Der Griff der Vorschau gehört diesem Dialog.** Ohne diese Zeile
        # blieb er im Bild stehen, und schlimmer: ``_preview_gizmo_wanted``
        # blieb gesetzt, sodass ihn jede künftige Vorschau neu anhängte — auch
        # an einer Bohrung, wo er nicht hingehört.
        self.viewport.set_preview_gizmo(False)
        self._disposed = True
        for widget in self._widgets():
            widget.deleteLater()

    def _widgets(self) -> tuple[QWidget, ...]:
        return (
            self._bar,
            self._canvas,
            self._centre,
            self._depth_measure,
            self._rest,
            *self._measures,
            *self._centre_measures,
        )

    def pointer(self, event: PointerEvent) -> bool:
        """Linksklick gehört der Platzierung, alle Kameragesten bleiben frei."""
        if not self.active:
            return False
        if self._seated_at_feature:
            if event.kind == "move" and not event.buttons:
                # **Die Stelle steht am Merkmal, nicht am Zeiger** — aber nur
                # die freie Bewegung gehört dieser Zusage. Ein Zug mit
                # gedrückter Taste ist eine Kamerageste, und die bleibt frei
                # (Regel dieser Datei: „Was die Platzierung nicht nimmt,
                # gehört der Kamera"). Ohne die Tastenfrage waren Drehen und
                # Schieben mit rechter und mittlerer Taste tot, solange eine
                # Bohrung gewählt war.
                return True
            if event.kind == "press" and event.button == "left":
                # Gemerkt, damit das Loslassen darunter Klick und Zug
                # auseinanderhalten kann; genommen wird die Geste wie bisher,
                # weil ihr Loslassen die Stelle neu ausrichtet.
                self._pressed_at = (event.x, event.y)
                return True
            if event.kind == "release" and event.button == "left":
                # **Ein Zug ist kein Klick** — dieselbe Unterscheidung wie in
                # der Tiefenstufe weiter unten, und aus demselben Grund. Wer
                # am Bewegungsgriff ansetzt und den Pfeil verfehlt, zieht über
                # das Bild; zählte dieses Loslassen als Ansage, sprang die
                # Platzierung dabei vom gewählten Merkmal weg in ihr Zielen —
                # die Bohrungsvorschau klebte danach am Zeiger, als setze man
                # eine neue (Robert, 11.09.2026: „beim verschieben über Gizmo
                # kommen wir in die ansicht vom bohrung setzen"). Gemessen
                # wird an der Zugschwelle des Systems, wie überall in der
                # Ansicht.
                if not self._barely_moved(event):
                    return True
                # **Ein Klick ist die ausdrückliche Ansage, woanders
                # hinzuwollen.** Danach zielt wieder der Zeiger, wie beim
                # Setzen einer neuen Bohrung — und die Geste ist damit
                # verbraucht: Ohne das ``return`` fiele sie in die
                # ``confirm``-Kette weiter unten und **übernähme** die
                # Platzierung, statt sie neu auszurichten. Der eingefrorene
                # Zustand geht mit, sonst bliebe die alte Stelle stehen.
                self._seated_at_feature = False
                self._frozen = False
                return True
        if event.kind == "leave":
            return True
        confirm = event.kind == "release" and event.button == "left"
        # **In der Tiefenstufe zieht die Maus, sie zielt nicht mehr.** Die
        # Stelle steht seit dem ersten Klick; was jetzt zählt, ist die Strecke
        # nach unten, und der nächste Klick bestätigt.
        #
        # **Und diese Frage steht vor allen anderen.** Darüber stand die Zeile
        # aus Stufe 1, die jeden Linksklick für die Platzierung nahm — sie
        # schluckte den Beginn jedes Kamerazugs, bevor die Tiefenstufe
        # überhaupt gefragt wurde. Gemessen am Protokoll: ``press left`` bei
        # 1933,731 und ``release left`` bei 864,809, über tausend Bildpunkte
        # Zug, und die Kamera stand still (Robert, 09.09.2026: „verschieben
        # geht immer noch nicht").
        if self._deepening:
            if self._depth_set:
                # **Steht die Tiefe, gehört die Maus wieder ganz der Ansicht.**
                # Auch der Linksklick: Er hat seine Aufgabe erfüllt, und im
                # ``solidon``-Schema schiebt er die Kamera. Ihn weiter
                # abzufangen nahm dem Navigator den Beginn des Zugs, und
                # Schieben ging nicht mehr (Robert, 09.09.2026: „schieben kann
                # ich die kamera nicht nach dem setzen der tiefe"). Bestätigt
                # wird am Knopf.
                return False
            if event.kind == "move" and not event.buttons:
                self._deepen_to(event.x, event.y)
                return True
            if confirm:
                # **Ein Zug ist kein Klick.** Im ``solidon``-Schema schiebt die
                # linke Taste die Kamera; wer in dieser Stufe schiebt, hat die
                # Tiefe nicht gemeint — und sie stand danach still fest, weil
                # jedes Loslassen als Bestätigung zählte. Gemessen wird wie
                # überall an der Zugschwelle des Systems (`ansicht.md`, „Ein
                # Klick ist ein Klick, auch mit Zittern").
                if not self._barely_moved(event):
                    return False
                # **Der Klick hält die Tiefe an, er setzt sie nicht.** Sonst
                # entscheidet dieselbe Geste zweimal — einmal die Stelle, einmal
                # das ganze Loch —, und wer nach dem Ziehen die Zahl nachbessern
                # will, hat schon gebohrt. Bestätigt wird über den Knopf
                # (Robert, 09.09.2026: „am ende über den dialog zu bestätigen").
                self._depth_set = True
                self._note.setText(
                    tr("Tiefe steht · Übernehmen: ausführen · Maßfeld: Zahl ändern · Esc: zurück")
                )
                self.redraw()
                return True
            # **Alles andere gehört der Kamera** (Robert, 09.09.2026: „hier
            # sollte ich dann auch wieder drehen und allen können"). Der erste
            # Anlauf schluckte jede Geste, die keine Tiefe war — Drehen, Zoomen
            # und Kippen waren in der Stufe tot, in der man sie am ehesten
            # braucht: Wer eine Tiefe beurteilt, dreht das Teil dazu. Nur der
            # Druck der linken Taste bleibt hier, weil sein Loslassen übernimmt.
            if event.kind == "press" and event.button == "left":
                self._pressed_at = (event.x, event.y)
                return True
            return False
        # In den Stufen davor gehört der Linksklick der Platzierung — sein
        # Loslassen setzt die Stelle beziehungsweise übernimmt sie.
        if event.kind == "press" and event.button == "left":
            return True
        if confirm or (event.kind == "move" and not event.buttons):
            if self._commit_pending:
                # **Die Sperre gilt dem laufenden Klick, nicht dem Modus.** Sie
                # verhindert, dass ein zweiter Klick zwischen dem ersten und
                # seiner Ausführung eine zweite Bohrung setzt — und blieb
                # stehen, sobald der gemerkte Klick nicht zum Setzen führte.
                # Danach lief jeder weitere Klick hier hinein und kam nie bei
                # der Fläche an: der Platzierungsmodus war stumm (Befund
                # Robert, 09.09.2026: „einmal hat es geklappt von 20 klicks").
                if self._still_committing():
                    return True
                self._commit_pending = False
            if self._frozen and not confirm:
                return True
            if self._frozen and confirm:
                self.accept()
                return True
            self._pending = event.x, event.y, confirm
            self._commit_pending = confirm
            self._serial += 1
            self._timer.start()
            return True
        return event.buttons == frozenset({"left"})

    def _barely_moved(self, event: PointerEvent) -> bool:
        """War das ein Klick oder das Ende eines Zugs?

        Dieselbe Frage wie im Navigator (`ansicht.md`, „Ein Klick ist ein
        Klick, auch mit Zittern"), und dieselbe Antwort: die Zugschwelle des
        Systems. Ohne gemerkten Druck — etwa wenn die Stufe zwischen Druck und
        Loslassen begann — gilt es als Klick, denn ein verschlucktes Loslassen
        wäre der schlechtere Fehler.
        """
        if self._pressed_at is None:
            return True
        away = max(abs(event.x - self._pressed_at[0]), abs(event.y - self._pressed_at[1]))
        self._pressed_at = None
        schwelle = float(QApplication.startDragDistance()) * self.viewport._device_ratio()
        return bool(away <= schwelle)

    def _still_committing(self) -> bool:
        """Steht wirklich noch ein Klick aus, der gesetzt werden will?

        Drei Zustände, und jeder einzelne bedeutet „gleich passiert es": Die
        Stelle ist gemerkt und wartet auf den Timer, die Flächensuche läuft,
        oder der Werkzeugbau läuft. Steht keiner davon, ist der gemerkte Klick
        verfallen — und dann darf er den nächsten nicht aussperren.

        Ein vierter stand hier: ein Merker, der den zu frühen Klick vormerkte,
        damit der fertige Werkzeugbau ihn nachholt. Den Weg gibt es seit dem
        dreistufigen Ablauf nicht mehr — er läuft über ``_pending`` und den
        Timer —, und ein Zustand, der nie eintritt, macht aus einer Aufzählung
        eine Behauptung.
        """
        return bool(self._pending is not None or self._surface_busy or self._tool_busy)

    def _next_surface(self) -> None:
        if self._surface_busy or self._pending is None or not self.active:
            return
        if not self.session.result_current or not self.viewport.is_scene_applied(self._result):
            self._pending = None
            self._invalid(tr("Die Oberfläche wird noch vorbereitet. Einen Moment warten."))
            return
        x, y, confirm = self._pending
        self._pending = None
        hit = self.viewport.placement_hit(x, y)
        if hit is None:
            self._invalid(tr("Auf eine sichtbare Oberfläche zeigen."))
            return
        object_id, point, cell, ray = hit
        result = self._result
        entry = result.scene.objects.get(object_id) if result is not None else None
        inputs = self.inputs_of()
        if entry is None or (inputs and object_id not in inputs):
            self._invalid(tr("Auf die Oberfläche des gewählten Körpers zeigen."))
            return
        clip_planes = tuple(plane for plane in self.viewport._section_planes() if plane is not None)
        stamp = self._serial
        prepared = (
            self._prepared
            if self._prepared_mesh is entry.mesh and cell in self._patch_faces
            else None
        )
        self._surface_busy = True

        def compute() -> Any:
            mesh = as_mesh_data(entry.mesh)
            at, face = point, cell
            if face < 0 or clip_planes:
                if ray is None:
                    return None
                original = placement.original_surface_hit(mesh, *ray, clip_planes=clip_planes)
                if original is None:
                    return None
                face, at = original
            context = prepared or placement.prepare_surface(mesh, face, entry.features)
            return context, placement.at_point(context, at)

        def done(value: Any) -> None:
            if not isValid(self) or self._disposed:
                return
            self._surface_busy = False
            if self.active and stamp == self._serial:
                if value is None:
                    self._invalid(
                        tr(
                            "Diese Stelle lässt sich nicht sicher zuordnen. "
                            "Eine andere Fläche wählen."
                        )
                    )
                else:
                    self._prepared, self._surface = value
                    self._centre_id = (
                        self._surface.centres[0].feature_id if self._surface.centres else ""
                    )
                    self._prepared_mesh = entry.mesh
                    self._patch_faces = frozenset(self._surface.face_indices)
                    previous_object = self._object_id
                    self._object_id = object_id
                    self._distance_valid = True
                    if previous_object != object_id:
                        self._request_tool()
                    self._set_values()
                    self._note.setText(
                        tr("Klicken: platzieren · Abstand ändern: Maßfeld · Esc: zurück")
                        if self._surface.planar
                        else tr(
                            "Gekrümmte Fläche: lokale Ausrichtung, keine ebenen Kantenabstände."
                        )
                    )
                    self.redraw()
                    if confirm:
                        self._settle()
            self._next_surface()

        def failed(detail: str) -> None:
            done(None)
            if self.active and stamp == self._serial:
                self._note.setText(
                    tr("Andere Fläche wählen oder die Werte bearbeiten.") + " " + detail
                )

        self.session.placement_async(compute, done, failed)

    def _begin_at_feature(self) -> None:
        """Beginnt dort, wo das gewählte Merkmal schon sitzt — ohne Klick (§18.5).

        **Wer ein bestehendes Merkmal bewegt, hat die Stelle nicht zu suchen.**
        Die Platzierung fing bis zum 10.09.2026 immer bei „Auf eine Oberfläche
        zeigen" an — richtig für ein Werkzeug, das noch nirgends sitzt, falsch
        für eine Bohrung, die schon da ist: Ihre Maße stehen fest, und der
        Kunde will sie sehen und ändern, nicht neu zielen (Robert, 10.09.2026:
        „die maße beim langloch ziehen und verschieben sind immer noch nicht da
        zu anderen merkmalen kanten mitten wie beim bohrung setzen").

        Was dafür fehlte, war die Fläche ohne Klick — ``placement.seat_of``
        liefert sie samt Mündung. Der Rest ist derselbe Weg wie nach einem
        Treffer (:meth:`_next_surface`), und er endet gleich in Stufe zwei: Die
        Stelle steht ja, offen sind die **Maße**.

        Wo es kein solches Merkmal gibt — jede Operation, die etwas Neues setzt
        —, geschieht hier nichts, und es bleibt beim Zeigen.
        """
        entry, feature = self._source_feature()
        if entry is None or feature is None or self._surface is not None:
            return
        stamp = self._serial
        object_id = entry.id
        # **Hier zielt der Zeiger nicht, und zwar von jetzt an.** Zwei Gründe,
        # und der zweite ist der dauerhafte: Bis die Fläche gerechnet ist,
        # verwirft jede Mausbewegung sie mit „Auf eine sichtbare Oberfläche
        # zeigen" wieder (gefunden am laufenden Fenster, 10.09.2026: Dialog
        # offen, Leiste „zeigen", kein Maß im Bild). Und danach gehört die
        # Stelle dem Merkmal — sie steht schon, offen sind die **Maße**. Wer
        # sie doch woanders hinsetzen will, klickt; siehe
        # :attr:`_seated_at_feature`.
        self._seated_at_feature = True

        def compute() -> Any:
            mesh = as_mesh_data(entry.mesh)
            seat = placement.seat_of(mesh, feature, entry.features)
            if seat is None:
                return None
            prepared, mouth = seat
            return prepared, placement.at_point(prepared, mouth)

        def done(value: Any) -> None:
            if not isValid(self) or self._disposed or not self.active or stamp != self._serial:
                return
            if value is None:
                # **Kein Fehler, sondern ein Rückfall auf den gewohnten Weg.**
                # Eine Verrundung hat keine Trägerfläche, und ein Merkmal auf
                # einer gekrümmten Fläche gibt keine ebenen Maße her; dort
                # bleibt es beim Zeigen, statt eine Absage zu melden — und dann
                # zielt wieder der Zeiger.
                self._seated_at_feature = False
                return
            self._prepared, self._surface = value
            self._centre_id = self._surface.centres[0].feature_id if self._surface.centres else ""
            self._prepared_mesh = entry.mesh
            self._patch_faces = frozenset(self._surface.face_indices)
            self._object_id = object_id
            self._distance_valid = True
            self._set_values()
            self._settle()

        def failed(_detail: str) -> None:
            # **Ohne Trägerfläche zielt wieder der Zeiger.** Eine Verrundung
            # hat keine, und dort ist das Zeigen der Rückfall, nicht ein
            # Fehler.
            self._seated_at_feature = False

        self.session.placement_async(compute, done, failed)

    def _invalid(self, message: str) -> None:
        self._surface = None
        self._commit_pending = False
        self._note.setText(message)
        self._accept.setEnabled(False)
        self.redraw()

    def _set_values(self) -> bool:
        """Nur die vorberechnete Raumlage übertragen; im Qt-Thread keine Geometrie bauen."""
        if self._surface is None or self._tool_context is None:
            return False
        self._updating = True
        try:
            source, feature = self._source_feature()
            self.dialog.take_placement(
                placement.surface_values(
                    self.spec_of(),
                    self._surface,
                    feature=feature,
                    source=source,
                    prepared_tool=self._tool_context,
                )
            )
            return True
        finally:
            self._updating = False

    def _source_feature(self) -> tuple[SceneObject | None, Feature | None]:
        """Ein vorhandenes Merkmal gehört eindeutig zu einem Eingangskörper."""
        result = self._result
        if result is None:
            return None, None
        candidates = [
            entry
            for object_id, entry in result.scene.objects.items()
            if object_id in self.inputs_of()
        ]
        # **Und *Zum Langloch ziehen* gehört dazu** (10.09.2026): Es sitzt auf
        # einem Loch, das es schon gibt, führt dessen Mitte in x, y, z und
        # bekommt damit dieselbe Platzierung wie *Bohrung setzen* — mit
        # Maßfeldern zu Kanten und Mitten, und einer Änderung, die wirkt.
        if self.spec_of().name not in {
            "move_feature",
            "duplicate_feature",
            "slot_hole",
            "resize_hole",
        }:
            chosen = result.scene.objects.get(self._object_id)
            return chosen or (candidates[0] if len(candidates) == 1 else None), None
        feature_id = self.dialog.values().get("at_feature")
        found = [
            (entry, entry.features[feature_id])
            for entry in candidates
            if feature_id in entry.features
        ]
        return found[0] if len(found) == 1 else (None, None)

    def _dragged_in_preview(self, matrix: Any) -> None:
        """Ein Zug am Griff der Vorschau wird zu Zahlen im offenen Dialog.

        Der Griff liefert die Matrix **des Zugs** — was sich gegenüber der
        Lage beim Anhängen geändert hat. Die neue Lage ist deshalb der Zug
        über der alten, und aus ihr rechnet der Kern wieder Ort, Richtung und
        Winkel (:func:`~app.core.geom.primitive_ops.placement_values_of`, die
        Umkehrung von ``placement_transform``).

        **Beide Richtungen aus einer Quelle.** Der Hinweg legt die Querachse
        über ``frame_of`` fest; wer sie hier anders wählte, verdrehte den
        Körper bei jedem Zug ein Stück weiter. Der Test dazu ist eine
        Rundreise, kein Vergleich mit ausgerechneten Zahlen.
        """
        from app.core.geom.primitive_ops import placement_transform, placement_values_of

        spec = self.spec_of()
        if self._disposed or not _grips_its_preview(spec):
            return
        try:
            entered = expressions.resolve_params(
                self.dialog.values(), expressions.resolve(self.session.project.document.parameters)
            )
            before = np.asarray(placement_transform(spec.params(**entered)), dtype=float)
        except AppError, TypeError, ValueError:
            # **Ein unlesbarer Wert verwirft den Zug, er verschiebt nichts.**
            # Ohne die alte Lage gibt es keine neue: Der Griff meldet nur, was
            # sich geändert hat. Hier stand eine Einheitsmatrix als Rückfall —
            # sie hätte den Körper bei einem halb getippten Ausdruck in den
            # Nullpunkt gesetzt, und der Kommentar daneben behauptete das
            # Gegenteil. Der Zug geht verloren; der Körper bleibt, wo er ist.
            return
        values = placement_values_of(np.asarray(matrix, dtype=float) @ before)
        self._updating = True
        try:
            self.dialog.take_placement(values)
        finally:
            self._updating = False

    def _values_changed(self) -> None:
        if not self._disposed and not self._updating:
            self.refresh_available()
            if self.active:
                self._request_tool()

    def _request_tool(self) -> None:
        if self._tool_busy:
            self._tool_again = True
            self._tool_context = None
            self.redraw()
            return
        spec = self.spec_of()
        source, feature = self._source_feature()
        values = self.dialog.values()
        placed = placement_fields(spec.params)
        for name in (*(placed[axis] for axis in ("x", "y", "z")), *normal_fields(spec.params)):
            if name in values:
                values[name] = 0.0
        if placed["at_feature"] in values and feature is None:
            values[placed["at_feature"]] = ""
        if placed["axis"] in values:
            values[placed["axis"]] = "z"
        profile = for_object(self.session.profile, source)
        key = repr((spec.name, values, profile, id(source.mesh) if source is not None else None))
        if key == self._tool_key and self._tool_context is not None:
            return
        parameters = dict(self.session.project.document.parameters)
        epoch = self._epoch
        self._tool_busy = True
        self._tool_again = False
        self._tool_context = None
        self.redraw()

        def compute() -> Any:
            entered = expressions.resolve_params(values, expressions.resolve(parameters))
            return placement.prepare_tool(spec, entered, profile, source=source, feature=feature)

        def done(context: placement.PlacementTool | None) -> None:
            if not isValid(self) or self._disposed:
                return
            self._tool_busy = False
            if self.active and epoch == self._epoch and not self._tool_again:
                renderer = self.viewport.renderer
                if renderer is not None:
                    self._remove_tools()
                    # **Wo ein Umriss die Stelle zeigt, tritt der Körper
                    # zurück.** Er bleibt für alles, was keinen hat — ein
                    # Baustein, dessen Mündung nicht in der Fläche liegt —,
                    # und für die Tiefe: die sieht man nur an ihm, und
                    # eingestellt wird sie im Dialog, nicht hier (Robert,
                    # 09.09.2026: „höchstens dann, wenn man die Tiefe noch
                    # einstellt, wäre die andere Ansicht interessant").
                    if context is not None:
                        mesh = context.mesh
                        addition = context.addition
                        colours = DIFF_PALETTES[
                            getattr(self.viewport, "_diff_palette", "blue_orange")
                        ]
                        self._tool = renderer.add_surface(
                            np.asarray(mesh.raw.vertices, dtype=np.float64),
                            np.asarray(mesh.raw.faces, dtype=np.int64),
                            name="surface_placement_tool",
                            style=SurfaceStyle(
                                colour=colours.removed.colour
                                if addition is not None
                                else self.viewport._object_colour,
                                opacity=0.45,
                                show_edges=False,
                                pickable=False,
                                keep_in_front=True,
                            ),
                        )
                        if addition is not None:
                            self._addition = renderer.add_surface(
                                np.asarray(addition.raw.vertices, dtype=np.float64),
                                np.asarray(addition.raw.faces, dtype=np.int64),
                                name="surface_placement_addition",
                                style=SurfaceStyle(
                                    colour=colours.added.colour,
                                    opacity=0.85,
                                    show_edges=False,
                                    pickable=False,
                                    keep_in_front=True,
                                ),
                            )
                            self._tool_legend.setText(f"+ {tr('Hinzugefügt')} · - {tr('Entfernt')}")
                            self._tool_legend.show()
                        self._tool_context = context
                        self._tool_key = key
                        self._set_values()
                    else:
                        self._note.setText(
                            tr(
                                "Vorschau nicht verfügbar. "
                                "Die Werte bearbeiten und erneut platzieren."
                            )
                        )
                self.redraw()
            if self._tool_again and self.active:
                self._request_tool()

        self.session.placement_async(compute, done, lambda _detail: done(None))

    def _distance_changed(self, _value: float) -> None:
        if not self.active or self._surface is None or len(self._surface.edges) < 2:
            return
        try:
            changed = placement.point_with_distances(
                self._prepared,
                self._surface,
                (self._measures[0].value_mm(), self._measures[1].value_mm()),
            )
        except ValidationError, ValueError, ArithmeticError:
            self._distance_valid = False
            self._note.setText(
                tr("Diese Abstände liegen außerhalb der Fläche. Kleinere Werte eingeben.")
            )
            self._accept.setEnabled(False)
            return
        self._frozen = True
        self._distance_valid = True
        self._pending = None
        self._serial += 1
        self._surface = changed
        self._set_values()
        self._note.setText(tr("Position festgelegt. Übernehmen oder mit Esc die Werte bearbeiten."))
        self.redraw()

    def _centre_changed(self, _value: float) -> None:
        """Beide signierten Maße halten dieselbe gewählte Mitte als Bezug."""
        if not self.active or self._surface is None or not self._centre_id:
            return
        try:
            changed = placement.point_with_centre(
                self._prepared,
                self._surface,
                self._centre_id,
                (self._centre_measures[0].value_mm(), self._centre_measures[1].value_mm()),
            )
        except ValidationError, ValueError, ArithmeticError:
            self._distance_valid = False
            self._note.setText(
                tr("Diese Abstände liegen außerhalb der Fläche. Andere Werte eingeben.")
            )
            self._accept.setEnabled(False)
            return
        self._frozen = True
        self._distance_valid = True
        self._pending = None
        self._serial += 1
        self._surface = changed
        self._set_values()
        self._note.setText(tr("Position festgelegt. Übernehmen oder mit Esc die Werte bearbeiten."))
        self.redraw()

    def _settle(self) -> None:
        """Der Klick legt die Stelle fest — und danach stehen die Maße offen.

        **Drei Stufen statt zweier** (Robert, 09.09.2026: „beim klick sollte
        man die maße dann einstellen die man sieht, dann in die seitenansicht
        erst nachdem man das bestätigt hat und die tiefe einstellen"). Der
        Klick war bis dahin die ganze Platzierung: Er nahm die Stelle **und**
        schloss ab, mit allen Vorgaben, die daran hingen — bei einer Bohrung
        also mit ``depth = 0``, was durch das ganze Teil heißt.

        Jetzt hält er an. Die Abstände zu den Kanten stehen als Zahlenfelder da
        und lassen sich eintippen; erst das Übernehmen führt weiter — zur
        Tiefe, wo es eine gibt, und sonst zum Ergebnis.
        """
        self._frozen = True
        self._commit_pending = False
        self._pending = None
        self._serial += 1
        self._accept.setText(tr("Weiter zur Tiefe") if self.deepens() else tr("Übernehmen"))
        self._note.setText(
            tr("Maße einstellen · Übernehmen: weiter zur Tiefe · Esc: zurück")
            if self.deepens()
            else tr("Position festgelegt. Übernehmen oder mit Esc die Werte bearbeiten.")
        )
        self.redraw()

    def deepens(self) -> bool:
        """Ob nach dem Klick noch eine Tiefe einzustellen ist.

        Zwei Bedingungen, und beide sind nötig. **Das Werkzeug muss auf etwas
        sitzen**: Ein Quader trägt ein Feld namens ``depth``, und das ist seine
        Bauteiltiefe und keine Eindringtiefe — genau die Verwechslung, vor der
        ``placement_fields`` warnt. **Und es muss eine Tiefe führen**: Ein
        Lochwand-Einhänger hat keine und ist mit dem Ort fertig.
        """
        spec = self.spec_of()
        return starts_by_itself(spec) and self._depth_name() is not None

    def _depth_name(self) -> str | None:
        """Das Feld der Eindringtiefe — oder ``None``, wo es keine gibt.

        Vier Stellen stellen dieselbe Frage; gestellt wird sie einmal, mit den
        **Werten des Dialogs**. Die zählen: Ob eine Beschriftung erhaben oder
        eingelassen ist, entscheidet ihr ``mode``, und nur im zweiten Fall geht
        der Zug nach unten ins Material.
        """
        spec = self.spec_of()
        try:
            values = spec.params(**self.dialog.values())
        except TypeError, ValueError, ValidationError:
            # Ein halb ausgefüllter Dialog ist der Normalfall, solange jemand
            # tippt — dann entscheidet die Vorgabe, nicht ein Fehler.
            values = None
        return depth_field(spec.name, spec.params, values)

    def accept(self) -> None:
        if (
            not self.active
            or not self.session.result_current
            or not self.viewport.is_scene_applied(self._result)
            or self._surface is None
            or self._tool is None
            or self._tool_context is None
            or not self._accept.isEnabled()
        ):
            return
        # **Der Klick legt die Stelle fest, nicht das ganze Loch.** Wer eine
        # Bohrung setzt, hat danach noch eine Tiefe einzustellen; bis zum
        # 09.09.2026 wurde sie mit der Vorgabe gesetzt — bei ``depth = 0``
        # heißt das durch das ganze Teil, ohne dass jemand gefragt hätte
        # (Robert: „oder ich bohr komplett durch ohne die tiefenbearbeitung").
        if self.deepens() and not self._deepening:
            self._begin_depth()
            return
        if not self._set_values():
            return
        self._stop()
        self.dialog.accept()

    # --- Stufe 2: die Tiefe ----------------------------------------------------

    def _begin_depth(self) -> None:
        """Die Stelle steht; jetzt zieht die Maus die Tiefe.

        **Was die zweite Stufe zeigt, kann die erste nicht.** Der Umriss auf
        der Fläche sagt, *wo* das Loch hinkommt, und über die Tiefe schweigt
        er; deshalb tritt hier der Werkzeugkörper wieder vor, und das Modell
        wird durchscheinend, damit man ihn darin sieht (Robert, 09.09.2026:
        „wenn wir klicken wollen wir die bohrung von der seitenansicht sehen
        und dann die tiefe runterziehen").

        Der gemerkte Klick ist damit verbraucht: ``_commit_pending`` fällt,
        sonst wäre der bestätigende Klick der Stufe ausgesperrt.
        """
        self._deepening = True
        self._depth_set = False
        self._commit_pending = False
        self._pending = None
        self._frozen = True
        self._show_the_body_from_the_side()
        # **Der Maßstab wird nach dem Schwenk gemessen, nicht davor.** Die
        # Ansicht rechnet perspektivisch, der Maßstab hängt also am Abstand zur
        # Kamera — und ``_look_along_the_surface`` stellt sie gerade erst auf
        # ihren neuen Abstand. Davor gemessen war der Faktor von der ersten
        # Bewegung an falsch.
        self._depth_per_pixel = self._millimetres_per_pixel()
        # **Und die Stufe beginnt mit einer Tiefe.** Stand im Feld die Null,
        # hieße „übernehmen, ohne zu ziehen" wieder: durch das ganze Teil, und
        # genau das sollte diese Stufe abschaffen (Robert, 09.09.2026: „die
        # bohrung ist aber sofort komplett durch"). Vorbelegt wird mit dem
        # Material unter der Mündung — dieselbe Wirkung wie bisher, aber als
        # Zahl, die dasteht und die man hochziehen kann.
        if self._depth_now(self._depth_name()) <= EPS_GEOM:
            self._set_depth(max(LEAST_DEPTH_MM, self._material_below()))
        self._note.setText(
            tr("Maus bewegen: Tiefe · Klick: übernehmen · Maßfeld: Zahl eingeben · Esc: zurück")
        )
        # Nicht „Bohrung": Acht Operationen erreichen diese Stufe, darunter
        # eine eingelassene Beschriftung und eine Tasche. Das Wort benennt,
        # worum es hier geht, und das ist die Tiefe.
        self._accept.setText(tr("Tiefe übernehmen"))
        self.redraw()

    def _millimetres_per_pixel(self) -> float:
        """Wie viele Millimeter ein Bildpunkt Zug bedeutet.

        Aus dem Maßstab der Ansicht, damit der Zug am kleinen wie am großen
        Teil dasselbe Gefühl hat: Ein fester Faktor zöge bei einem Teil von
        zehn Millimetern durch das ganze Stück, während er an einem von
        dreihundert kaum etwas täte. Findet die Ansicht keinen Maßstab, bleibt
        ein Zehntelmillimeter je Punkt — die Zahl steht daneben und lässt sich
        eintippen.
        """
        if self._surface is None or self.viewport.renderer is None:
            return 0.1
        # **`_pixels_per_mm_at` und nicht `pixels_per_mm`.** Die zweite nimmt
        # einen ``PlaneFrame`` und ist die des Skizzeneditors; mit einem Punkt
        # gefüttert wirft sie. Der erste Anlauf fing das mit ``except
        # Exception`` ab und fiel auf einen Zehntelmillimeter je Bildpunkt
        # zurück — an einem 20-mm-Teil bei zwölf Punkten je Millimeter das
        # Hundertfache dessen, was der Zeiger anzeigt (Robert, 09.09.2026:
        # „bei weiter zur tiefe passt wohl die mausposition zur darstellung
        # noch nicht ganz"). Ein stiller Rückfall verschluckt genau solche
        # Fehler; gefragt wird deshalb ohne ihn.
        scale = self.viewport._pixels_per_mm_at(tuple(self._surface.point))
        if scale is None or scale <= 1e-9:
            return 0.1
        return 1.0 / float(scale)

    def _show_the_body_from_the_side(self) -> None:
        """Modell durchscheinend, Werkzeug sichtbar — der Blick in das Loch.

        Zurückgestellt wird beides in :meth:`_stop`; die Darstellungsart ist
        eine Einstellung des Nutzers (`ansicht.md`, „Was die Ansicht sich
        merkt"), und eine geliehene Ansicht gibt man zurück.
        """
        # Direkt gefragt, nicht über ``getattr`` mit stillem Rückfall: Fehlte
        # der Setzer, bliebe die Ansicht wortlos für immer durchscheinend.
        self._display_before = self.viewport.display_mode
        self.viewport.set_display_mode("transparent")
        for item in (self._tool, self._addition):
            if item is not None:
                item.set_visible(True)
        self._look_along_the_surface()

    def _look_along_the_surface(self) -> None:
        """Die Kamera quer zur Werkzeugachse — der Blick von der Seite.

        Robert, 09.09.2026: „wenn wir klicken wollen wir die bohrung von der
        seitenansicht sehen und dann die tiefe runterziehen". Von vorn auf die
        Mündung gesehen ist eine Tiefe nicht zu beurteilen; quer dazu ist sie
        die Länge, die man zieht.

        Gedreht wird **um die Stelle**, und Abstand wie Bildausschnitt bleiben:
        Wer auf ein Detail gezoomt hat, will es weiter sehen — dieselbe Zusage
        wie bei den Kameravorgaben (`ansicht.md`, „Eine Kameravorgabe dreht um
        den Blickpunkt, sie passt nicht ein").
        """
        if self._surface is None or self.viewport.renderer is None:
            return
        axis = np.asarray(self._surface.frame.normal, dtype=np.float64)
        length_of = float(np.linalg.norm(axis))
        if length_of < 1e-9:
            return
        axis = axis / length_of
        spot = np.asarray(self.viewport.view_point_of(self._surface.point, self._object_id))
        # **Vier Werte, nicht drei.** ``camera_pose`` gibt zusätzlich den
        # Parallelmaßstab zurück, und der wird unverändert weitergereicht —
        # sonst springt in orthografischer Projektion der Bildausschnitt.
        found = self.viewport.camera_pose()
        if self._camera_before is None:
            self._camera_before = found
        position = np.asarray(found[0], dtype=np.float64)
        focus = np.asarray(found[1], dtype=np.float64)
        scale = found[3]
        away = float(np.linalg.norm(position - focus))
        if away < 1e-9:
            return
        # **Die Blickrichtung steht senkrecht auf der Achse und waagerecht in
        # der Welt.** Von der bisherigen Sicht bleibt nur, *von welcher Seite*
        # man schaut — der Anteil entlang der Achse fällt weg, und damit die
        # Schräge von oben. Der erste Anlauf zog nur die Achse ab und ließ die
        # Kamera dort, wo sie war; im Bild war das eine leicht gekippte
        # Draufsicht und keine Seitenansicht (Robert, 09.09.2026:
        # „seitenansicht ist das auch nicht ganz").
        sideways = position - focus
        sideways = sideways - axis * float(sideways @ axis)
        if float(np.linalg.norm(sideways)) < 1e-6:
            # Der Blick steht genau auf der Achse: irgendeine Querrichtung tut es.
            helper = np.array([0.0, 0.0, 1.0]) if abs(axis[2]) < 0.9 else np.array([1.0, 0.0, 0.0])
            sideways = np.cross(axis, helper)
        # Und waagerecht: Steht die Achse aufrecht, liegt die Kamera auf
        # Augenhöhe der Mündung — sonst bliebe die Schräge, aus der man die
        # Tiefe nicht ablesen kann.
        upright = np.array([0.0, 0.0, 1.0], dtype=np.float64)
        if abs(float(axis @ upright)) > 0.9:
            sideways[2] = 0.0
            if float(np.linalg.norm(sideways)) < 1e-6:
                sideways = np.array([0.0, -1.0, 0.0], dtype=np.float64)
        sideways = sideways / float(np.linalg.norm(sideways)) * away
        at = spot + sideways
        self.viewport.set_camera_pose(
            (float(at[0]), float(at[1]), float(at[2])),
            (float(spot[0]), float(spot[1]), float(spot[2])),
            (float(axis[0]), float(axis[1]), float(axis[2])),
            scale,
        )
        self.viewport.settle_camera()

    def _deepen_to(self, x: int, y: int) -> None:
        """Die Tiefe aus der Zeigerstrecke — gemessen vom Beginn, nicht summiert.

        Eine Summe aus Einzelschritten driftet, sobald ein Ereignis ausfällt;
        die Strecke vom Startpunkt kann das nicht. Nach unten heißt tiefer, wie
        Robert es beschrieben hat („die tiefe runterziehen").
        """
        # **Nicht am Werkzeugkörper hängen.** Jede gesetzte Tiefe stößt einen
        # Neubau der Vorschau an, und der setzt ``_tool_context`` für seine
        # Dauer auf ``None``: Mit ihm in dieser Bedingung fiel jede zweite
        # Bewegung aus, die Zahl blieb stehen und der Zug ruckelte. Gerechnet
        # wird aus der Fläche und der Kamera — der Werkzeugkörper ist das Bild
        # dazu und keine Voraussetzung.
        if self._surface is None:
            return
        name = self._depth_name()
        if name is None:
            return
        renderer = self.viewport.renderer
        if renderer is None:
            return
        # **Die Spitze liegt unter dem Zeiger, nicht irgendwo.** Der erste
        # Anlauf zählte die Strecke seit dem Beginn des Zugs zusammen; wo der
        # Zeiger stand, hatte damit nichts mit der Tiefe zu tun, und man zog am
        # unteren Rand, während die Bohrung kaum begonnen hatte (Robert,
        # 09.09.2026: „ich hab den mauszeiger kurz über den unteren panel aber
        # eigentlich müsste ich viel weiter oben sein"). Gemessen wird deshalb
        # **absolut**: der Abstand des Zeigers von der Mündung, im Bild,
        # entlang der Bohrachse.
        mouth = renderer.world_to_display(
            tuple(self.viewport.view_point_of(self._surface.point, self._object_id))
        )
        along = self._axis_on_screen()
        if along is None:
            return
        # **Der Maßstab wird je Bewegung neu gemessen, nicht einmal beim
        # Betreten.** Zoomen bleibt in dieser Stufe frei (`app/ui/CLAUDE.md`,
        # „Drehen, Zoomen und Kippen bleiben frei"), und die Ansicht rechnet
        # perspektivisch: Nach einem Zoom um den Faktor k wäre eine eingefrorene
        # Zahl um k daneben, und die Spitze läge nicht mehr unter dem Zeiger.
        # Die Bildrichtung der Achse (``_axis_on_screen``) wird aus demselben
        # Grund schon immer hier gerechnet; der Maßstab war die Hälfte, die
        # stehen geblieben ist.
        self._depth_per_pixel = self._millimetres_per_pixel()
        # Die Strecke vom Mündungspunkt zum Zeiger, auf die Bildrichtung der
        # Achse projiziert: So weit ist die Spitze unter dem Zeiger.
        #
        # **Alles hier zählt in Gerätepixeln, und zwar durchgehend.**
        # ``PointerEvent.x/y`` kommen bereits so (der Renderer multipliziert
        # beim Erzeugen), ``world_to_display`` liefert sie ebenso, und
        # ``_pixels_per_mm_at`` misst darin. Der erste Anlauf rechnete das
        # Verhältnis an dieser Zeile noch einmal hinein und danach wieder
        # heraus — bei einem Bildschirm ohne Skalierung fällt das nie auf, bei
        # 125 Prozent bleibt ein Versatz, der von der Bildlage der Bohrung
        # abhängt (`ansicht.md`, „Wer die Umrechnung an einer Zeichenstelle
        # wiederholt, rechnet doppelt").
        reach = (x - float(mouth[0])) * along[0] + (y - float(mouth[1])) * along[1]
        # **Nicht bis auf null.** Bei ``depth = 0`` bohrt die Operation durch
        # das ganze Teil (`prepare_ops.py`, „Null bohrt durch das ganze Teil") —
        # wer den Zeiger nach oben zieht, um die Bohrung *flacher* zu machen,
        # bekäme am Ende des Wegs das Gegenteil. Der Zug hält deshalb bei einem
        # zehntel Millimeter an; wer wirklich durch will, zieht nach unten oder
        # tippt die Null ins Feld.
        wanted = max(LEAST_DEPTH_MM, reach * self._depth_per_pixel)
        # **Kurzes Einrasten an den Stellen, die etwas bedeuten** (Robert,
        # 09.09.2026). Die Zone steht in logischen Bildpunkten wie jede
        # Fangweite der Oberfläche und wird über das Geräteverhältnis in
        # Millimeter gebracht — dieselbe Rechnung wie in
        # ``Viewport._snap_radius_at``.
        zone = SNAP_PIXELS * self.viewport._device_ratio() * self._depth_per_pixel
        self._set_depth(snap_to_marks(wanted, self._depth_marks(), zone))

    def _depth_marks(self) -> tuple[float, ...]:
        """Die Tiefen, die etwas bedeuten: Mitte und Rückseite des Materials.

        Mehr nicht — eine lange Liste machte aus dem freien Zug eine Auswahl,
        und genau das soll das kurze Einrasten nicht sein. Was der Kunde selbst
        eintippt, geht ohnehin nicht durch den Magneten (:meth:`_depth_typed`).
        """
        below = self._material_below()
        if below <= EPS_GEOM:
            return ()
        return (below / 2.0, below)

    def _axis_on_screen(self) -> tuple[float, float] | None:
        """Die Bohrachse als Einheitsrichtung im Bild — von der Mündung ins Material.

        Sie sagt, welche Zeigerbewegung „tiefer" bedeutet. Nach dem Schwenk in
        die Seitenansicht steht sie senkrecht, aber die Kamera darf danach
        weitergedreht werden; gerechnet wird deshalb aus der Projektion und
        nicht aus der Annahme.
        """
        renderer = self.viewport.renderer
        if renderer is None or self._surface is None:
            return None
        axis = np.asarray(self._surface.frame.normal, dtype=np.float64)
        span = float(np.linalg.norm(axis))
        if span < 1e-9:
            return None
        axis = axis / span
        point = np.asarray(self._surface.point, dtype=np.float64)
        # Ins Material hinein ist die Gegenrichtung der Flächennormalen.
        mouth = renderer.world_to_display(
            tuple(self.viewport.view_point_of(tuple(point), self._object_id))
        )
        inside = renderer.world_to_display(
            tuple(self.viewport.view_point_of(tuple(point - axis), self._object_id))
        )
        step = np.array([inside[0] - mouth[0], inside[1] - mouth[1]], dtype=np.float64)
        length_of = float(np.linalg.norm(step))
        if length_of < 1e-6:
            return None
        step = step / length_of
        return float(step[0]), float(step[1])

    def _depth_typed(self, millimetres: float) -> None:
        """Eine eingetippte Tiefe zählt wie eine gezogene — und hält den Zug an.

        **Wer eine Zahl eingibt, hat entschieden**, und der Zeiger hat danach
        nichts mehr zu sagen. Der Zug misst absolut von der Mündung: Ohne diese
        Sperre überschriebe die nächste Bewegung über der Renderfläche den
        getippten Wert vollständig — und der Weg zum Knopf führt genau darüber
        (Robert, 09.09.2026: „wenn ich die tiefe setz, komm ich nicht in das
        bearbeitenfeld von der maßeinheit"). ``_depth_set`` ist dieselbe Sperre,
        die auch der bestätigende Klick setzt; von hier führt derselbe Weg
        weiter — Ansicht frei, Knopf übernimmt.
        """
        if self._updating or not self._deepening:
            return
        self._set_depth(max(0.0, millimetres))
        self._depth_set = True

    def _depth_now(self, name: str | None) -> float:
        """Die eingestellte Tiefe in Millimetern — auch wenn dort ein Ausdruck steht.

        ``OperationDialog.values`` gibt zurück, was im Feld steht: eine Zahl
        **oder** einen Parameterausdruck (`=@wand`). Ein ``float()`` darauf
        wirft, und weil ``redraw`` aus einem Qt-Slot läuft, riss die Ausnahme
        die ganze Tiefenstufe mit — noch bevor die erste Mausbewegung kam. Der
        Ausdruck wird deshalb aufgelöst, mit denselben Projektparametern, die
        auch ``_request_tool`` benutzt.

        Was sich nicht auflösen lässt, gilt als null: Die Tiefenstufe ist eine
        Anzeige, und ein unvollständiger Ausdruck ist ein Fall für den Dialog,
        nicht für einen Absturz (Regel 17).
        """
        if name is None:
            return 0.0
        found = self.dialog.values().get(name, 0.0)
        if expressions.is_expression(found):
            parameters = expressions.resolve(dict(self.session.project.document.parameters))
            try:
                found = expressions.resolve_params({name: found}, parameters).get(name, 0.0)
            except AppError:
                return 0.0
        try:
            return float(found or 0.0)
        except TypeError, ValueError:
            return 0.0

    def _material_below(self) -> float:
        """Wie viel Material unter der Mündung liegt, entlang der Werkzeugachse.

        Das Bezugsmaß der Tiefenstufe: Wer bohrt, will wissen, wie viel Wand
        stehen bleibt und wo die Mitte liegt (Robert, 09.09.2026: „bei der
        tiefe fehlen die maße, außenkannten, innenkannten, mitte von
        irgendwas").

        **Gemessen wird mit einem Strahl, nicht am Hüllquader.** Der fernste
        Punkt des Körpers in Bohrrichtung ist bei einem massiven Klotz die
        richtige Antwort und bei einem hohlen die falsche — und hohl ist im
        Druck der Normalfall. In die zwei Millimeter starke Decke einer Box
        gebohrt stand „Wand: 18,0 mm" im Bild, die Mitte-Marke lag in der Luft,
        und das Einrasten hielt an beiden falschen Werten. Der Strahl nimmt den
        **ersten Austritt**, also die Wand, die der Bohrer wirklich vor sich
        hat; dieselbe Rechnung, mit der die Stifte ihre Materialtiefe suchen
        (``geom.pins``).

        Findet der Strahl nichts — die Fläche zeigt nach außen, dahinter ist
        Luft —, bleibt der Hüllquader als Rückfall: Ein Maß von null verböte
        jede Tiefe, und die Marken verschwänden ganz.
        """
        result = self._result
        entry = result.scene.objects.get(self._object_id) if result is not None else None
        if entry is None or self._surface is None:
            return 0.0
        along = np.asarray(self._surface.frame.normal, dtype=np.float64)
        span = float(np.linalg.norm(along))
        if span < 1e-9:
            return 0.0
        along = along / span
        mesh = as_mesh_data(entry.mesh)
        origin = np.asarray(self._surface.point, dtype=np.float64)
        distances = ray_hit_distances(
            np.asarray(mesh.raw.triangles, dtype=np.float64), origin, -along
        )
        # Der Mündungspunkt liegt auf der Fläche selbst; ein Treffer im Abstand
        # null ist sie und nicht die Gegenwand.
        ahead = distances[distances > EPS_GEOM]
        if len(ahead):
            return float(ahead.min())
        points = np.asarray(mesh.raw.vertices, dtype=np.float64)
        if not points.size:
            return 0.0
        mouth = float(origin @ along)
        return max(0.0, mouth - float((points @ along).min()))

    def _set_depth(self, millimetres: float) -> None:
        """Trägt die Tiefe in den Dialog und zeichnet das Werkzeug neu."""
        name = self._depth_name()
        if name is None or self._updating:
            return
        self._updating = True
        try:
            self.dialog.take_placement({name: millimetres})
        finally:
            self._updating = False
        self._request_tool()
        self.redraw()

    def _scene_changed(self, _result: Any) -> None:
        # Eine fremde Operation oder Undo entwertet die alte Oberfläche.
        if self.active:
            self.back()
        self.refresh_available()

    def _scene_applied(self) -> None:
        """Erst der tatsächlich gezeichnete Eingang erlaubt ein neues Ziel."""
        if self.active and self.viewport.is_scene_applied(self._result):
            self._note.setText(tr("Klicken: platzieren · Abstand ändern: Maßfeld · Esc: zurück"))
            self._next_surface()
            self.redraw()

    def _document_changed(self) -> None:
        """Undo und andere Eingriffe entwerten den Bezug vor der nächsten Auswertung."""
        self._prepared = None
        self._prepared_mesh = None
        self._patch_faces = frozenset()
        if self.active:
            self.back()
        self.refresh_available()

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        # Der Fluss hängt an Zonen, Feldern, dem Viewport und dessen
        # Zeichenfläche — alles sterbliche Widgets. Stirbt eines davon, läuft
        # der Filter sonst in den Abbau hinein (``leash.stop_watching_the_dying``).
        if stop_watching_the_dying(self, watched, event):
            return False
        if self.active:
            if watched in self._overlay_zones and event.type() in (
                QEvent.Type.Move,
                QEvent.Type.Resize,
                QEvent.Type.Show,
                QEvent.Type.Hide,
            ):
                # Die Karte beendet zuerst ihren Layoutschritt; dann liest die
                # Platzierung die wirkliche Geometrie statt eines Zwischenstands.
                QTimer.singleShot(0, self.redraw)
                return False
            if (
                isinstance(event, QKeyEvent)
                and event.type() == QEvent.Type.KeyPress
                and event.key() == Qt.Key.Key_Escape
            ):
                self.back()
                return True
            if event.type() == QEvent.Type.FocusIn and watched is self._depth_measure:
                # Dieselbe Zusage wie bei den Kantenmaßen darunter, nur für die
                # Tiefe: Wer in das Feld klickt, will tippen und nicht ziehen.
                self._depth_set = True
            if event.type() == QEvent.Type.FocusIn and watched in (
                *self._measures,
                *self._centre_measures,
            ):
                self._frozen = True
                self._pending = None
                self._commit_pending = False
                self._serial += 1
            if event.type() == QEvent.Type.Resize and (
                watched is self.viewport
                or watched is getattr(self.viewport.renderer, "widget", None)
            ):
                # Nur die Ansichtsfläche bestimmt das Layout. adjustSize der
                # eigenen Maßfelder löst ebenfalls Resize aus; ein Rückruf
                # mitten im Aufbau würde mehrere Linienlisten vermischen.
                self.redraw()
        return super().eventFilter(watched, event)

    def redraw(self) -> None:
        if not self.active or self._disposed:
            return
        area = self.viewport.rect()
        self._canvas.setGeometry(area)
        room = area.adjusted(ROOMY, ROOMY, -ROOMY, -ROOMY)
        overlay = getattr(self.window, "overlay", None)
        for role in ("left", "right", "bottom"):
            zone = getattr(overlay, role, None)
            if (
                not isinstance(overlay, QWidget)
                or not isinstance(zone, QWidget)
                or not isValid(zone)
                or not zone.isVisibleTo(overlay)
            ):
                continue
            obstacle = QRect(self.viewport.mapFromGlobal(zone.mapToGlobal(QPoint())), zone.size())
            if role == "left":
                room.setLeft(max(room.left(), obstacle.right() + NORMAL + 1))
            elif role == "right":
                room.setRight(min(room.right(), obstacle.left() - NORMAL - 1))
            else:
                room.setBottom(min(room.bottom(), obstacle.top() - NORMAL - 1))
        self._bar.setMaximumWidth(max(room.width(), 1))
        self._bar.adjustSize()
        # **Unten mittig, über der Werkzeugzeile** (Robert, 09.09.2026: „das
        # fenster weiter zur tiefe am besten unten mittig über das panel mit
        # schnitt, messen usw setzen"). Oben links lag sie im Weg des Modells
        # und weit weg von dem Ort, an dem beim Platzieren ohnehin jeder
        # hinsieht: der Zeile mit Schnitt, Messen und Bewegen. ``room`` hat die
        # verdeckten Zonen schon abgezogen, die untere Kante ist damit die
        # Oberkante dieser Zeile.
        self._bar.move(
            room.left() + max(0, (room.width() - self._bar.width()) // 2),
            max(room.top(), room.bottom() - self._bar.height()),
        )
        self._bar.raise_()
        surface = self._surface
        renderer = self.viewport.renderer
        valid = (
            surface is not None
            and renderer is not None
            and self.session.result_current
            and self.viewport.is_scene_applied(self._result)
        )
        tool_valid = valid and self._tool_context is not None and not self._tool_busy
        # **Gefragt wird das vorbereitete Werkzeug, nicht der gezeichnete
        # Körper.** Ob gesetzt werden kann, hängt daran, dass die Geometrie
        # steht — nicht daran, wie sie gerade angezeigt wird. Seit der Umriss
        # den Körper an einer Bohrung ersetzt, ist ``_tool`` dort ``None``,
        # und der Knopf blieb grau, obwohl alles bereit war. ``tool_valid``
        # trägt die eigentliche Bedingung (``_tool_context is not None``)
        # bereits.
        self._accept.setEnabled(tool_valid and self._distance_valid)
        self._canvas.lines = []
        self._canvas.leaders = []
        self._canvas.outline = []
        # **Jede Stufe zeigt ihr eigenes Maß.** Die Kantenabstände gehören der
        # Fläche, auf der gesetzt wird — in der Tiefenstufe ist die entschieden,
        # und dort steht die Tiefe an ihrer Stelle.
        for index, field in enumerate(self._measures):
            field.setVisible(valid and not self._deepening and index < len(surface.edges))
        self._centre.hide()
        for field in self._centre_measures:
            field.setVisible(valid and not self._deepening and bool(self._centre_id))
        self._depth_measure.setVisible(valid and self._deepening)
        # **Wo ein Umriss die Stelle zeigt, tritt der Körper zurück.** Der
        # halbtransparente Zylinder steht auch außerhalb des Materials, und
        # beim Drehen der Ansicht war schwer zu sehen, wo das Loch hinkommt
        # (Befund Robert, 09.09.2026). Gebaut wird er weiter — er trägt die
        # Geometrie, an der das Setzen hängt —, gezeigt nur, wo er die
        # einzige Auskunft ist: bei einem Werkzeug ohne Mündung in der Fläche,
        # und für die Tiefe, die man allein an ihm sieht.
        # **In der Tiefenstufe kehrt sich das um.** Dort ist der Körper die
        # einzige Auskunft, die es gibt — der Umriss sagt nichts über die
        # Tiefe, und wer sie zieht, muss sehen, wie weit der Zylinder reicht
        # (Robert, 09.09.2026: „bei weiter zur tiefe sehe ich den zylinder für
        # die bohrung nicht").
        has_outline = (
            not self._deepening
            and self._tool_context is not None
            and bool(placement.mouth_outline(self._tool_context))
        )
        for item in (self._tool, self._addition):
            if item is not None:
                item.set_visible(tool_valid and not has_outline)
        if not valid:
            self._canvas.hide()
            self.viewport._draw()
            return
        point = np.asarray(surface.point, dtype=np.float64)
        if self._tool is not None:
            matrix = np.eye(4, dtype=np.float64)
            matrix[:3, :3] = np.asarray(
                [surface.frame.x_axis, surface.frame.y_axis, surface.normal], dtype=np.float64
            ).T
            matrix[:3, 3] = self.viewport.view_point_of(surface.point, self._object_id)
            self._tool.set_matrix(matrix)
            if self._addition is not None:
                self._addition.set_matrix(matrix)
        ratio = self.viewport._device_ratio()

        def screen(at: Vec3) -> QPointF:
            shown = self.viewport.view_point_of(at, self._object_id)
            x, y, _depth = renderer.world_to_display(shown)
            return QPointF(x / ratio, y / ratio)

        # **Der Umriss der Mündung, dort wo das Werkzeug die Fläche trifft.**
        # Er beantwortet die Frage, die der halbtransparente Körper offenließ:
        # wo genau das Loch hinkommt. Der Körper zeigte dazu den ganzen
        # Zylinder, auch außerhalb des Materials, und beim Drehen der Ansicht
        # war beides schwer auseinanderzuhalten (Befund Robert, 09.09.2026).
        #
        # Gerechnet wird nichts: Der Umriss steht im vorbereiteten Werkzeug,
        # und hier wird er nur in die Ebene der Fläche gelegt und projiziert.
        outline = (
            placement.mouth_outline(self._tool_context) if self._tool_context is not None else ()
        )
        if outline:
            axis_u = np.asarray(surface.frame.x_axis, dtype=np.float64)
            axis_v = np.asarray(surface.frame.y_axis, dtype=np.float64)
            self._canvas.outline = [
                screen(tuple(point + axis_u * u + axis_v * v)) for u, v in outline
            ]
            self._canvas.outline_colour = QColor(
                DIFF_PALETTES[getattr(self.viewport, "_diff_palette", "blue_orange")].removed.colour
            )

        pending: list[tuple[QWidget, QPointF, tuple[QPointF, QPointF]]] = []

        def place(widget: QWidget, start: QPointF, end: QPointF) -> None:
            # **In der Tiefenstufe steht kein Kantenmaß mehr.** Die Schleife
            # unten ruft für jedes gesammelte Feld ``show()`` — eine
            # Sichtbarkeit, die vorher gesetzt wurde, hebt sie damit wieder
            # auf. Wer ein Feld ausblenden will, sammelt es nicht ein (Befund
            # aus Roberts Bild, 09.09.2026: die Abstände der Fläche standen
            # noch da, während unten schon „Maus bewegen: Tiefe" stand).
            if self._deepening and widget is not self._depth_measure:
                return
            widget.setMaximumWidth(max(room.width(), 1))
            if isinstance(widget, QLabel):
                widget.setWordWrap(True)
            widget.adjustSize()
            pending.append((widget, (start + end) / 2, (start, end)))

        if self._deepening and valid:
            # **Die Bezugsmaße der Tiefe** (Robert, 09.09.2026: „bei der tiefe
            # fehlen die maße, außenkannten, innenkannten, mitte von
            # irgendwas"). Von der Mündung zur Spitze steht die Tiefe, von der
            # Spitze zur Rückseite die Wand, die stehen bleibt; die Mitte ist
            # eine eigene Marke, weil an ihr eingerastet wird.
            name = self._depth_name()
            depth = self._depth_now(name)
            below = self._material_below()
            axis = np.asarray(surface.frame.normal, dtype=np.float64)
            span = float(np.linalg.norm(axis))
            if span > EPS_GEOM:
                axis = axis / span
                mouth = screen(surface.point)
                tip = screen(tuple(point - axis * depth))
                self._canvas.lines.append((mouth, tip))
                # **An seiner Maßlinie, wie jedes Kantenmaß.** Über der Leiste
                # allein stand es als Fremdkörper da: Dieselbe Rolle, dieselbe
                # Gestalt (Robert, 09.09.2026: „das maßfeld ist immer noch
                # nicht so wie wenn ich die bohrung auf der oberfläche setze").
                # ``QSignalBlocker`` und nicht zwei Aufrufe: Wirft
                # ``set_value_mm`` dazwischen, bliebe das Feld für immer
                # stumm — es nähme danach keine Eingabe mehr an, ohne dass
                # etwas danach aussieht.
                with QSignalBlocker(self._depth_measure):
                    self._depth_measure.set_value_mm(depth)
                place(self._depth_measure, mouth, tip)
                if below > depth + EPS_GEOM:
                    self._canvas.lines.append((tip, screen(tuple(point - axis * below))))
                    self._rest.setText(
                        tr("Wand: {value}").replace("{value}", length(below - depth))
                    )
                    self._rest.adjustSize()
                    self._rest.move(round(tip.x()) + ROOMY, round(tip.y()))
                    self._rest.show()
                    self._rest.raise_()
                else:
                    self._rest.hide()
                middle = screen(tuple(point - axis * (below / 2.0)))
                self._canvas.leaders.append((middle, middle))
        else:
            self._rest.hide()

        for index, edge in enumerate(surface.edges[:2]):
            foot = point - np.asarray(edge.inward, dtype=np.float64) * edge.distance
            start, end = screen(tuple(foot)), screen(surface.point)
            self._canvas.lines.append((start, end))
            field = self._measures[index]
            if not field.hasFocus():
                with QSignalBlocker(field):
                    bound = max(self._prepared_mesh.bounds.diagonal, abs(edge.distance), 1.0)
                    field.set_range_mm(-bound, bound)
                    field.set_value_mm(edge.distance)
            place(field, start, end)
        centre = next(
            (entry for entry in surface.centres if entry.feature_id == self._centre_id), None
        )
        if centre is not None:
            corner = np.asarray(centre.point) + np.asarray(surface.frame.x_axis) * centre.offset[0]
            vertices = (centre.point, tuple(corner), surface.point)
            for index, field in enumerate(self._centre_measures):
                start, end = screen(vertices[index]), screen(vertices[index + 1])
                self._canvas.lines.append((start, end))
                if not field.hasFocus():
                    with QSignalBlocker(field):
                        bound = max(self._prepared_mesh.bounds.diagonal, 1.0)
                        field.set_range_mm(-bound, bound)
                        field.set_value_mm(centre.offset[index])
                place(field, start, end)
            source = self._result.scene.objects.get(self._object_id)
            feature = source.features.get(centre.feature_id) if source is not None else None
            name = feature_name(centre.feature_id, feature) if feature is not None else tr("Mitte")
            self._centre.setText(
                tr("{feature} · Abstand: {distance}").format(
                    feature=name, distance=length(centre.distance)
                )
            )
            place(self._centre, screen(centre.point), screen(centre.point))
        # Der Platz für die Maßfelder ist der Raum **über** der Leiste, seit
        # sie unten mittig steht. Vorher lag sie oben und der Raum darunter;
        # wer nur die Leiste verschiebt und diese Rechnung stehen lässt, drückt
        # jedem Feld den Boden weg — die Zahlen rutschten aus dem Bild.
        bar = self._bar.geometry()
        bounds = QRect(
            room.left(),
            room.top(),
            max(room.width(), 1),
            max(bar.top() - NORMAL - room.top(), 1),
        )
        # **Der Setzpunkt ist das erste Hindernis, noch vor jedem Feld.** Jedes
        # Maßfeld will in die Mitte seiner eigenen Maßlinie, und die Linien
        # laufen von den Kanten auf genau diesen Punkt zu — je kürzer der
        # Abstand zur Kante, desto näher rückt die Mitte an ihn heran, bis das
        # Feld verdeckt, wohin der Kunde gerade setzt (Befund Robert,
        # 09.09.2026). Als belegtes Rechteck geführt, weicht die Suche ihm nicht
        # nur aus, sondern erzeugt daneben auch die Ausweichplätze — dieselbe
        # Mechanik, mit der die Felder einander schon aus dem Weg gehen.
        # **Und gesperrt wird, was man sieht, nicht ein Punkt.** Ein fester
        # Abstand ließe das Feld neun Bildpunkte neben der Mitte stehen und
        # damit über der Werkzeugvorschau: Eine Bohrung Ø5 mm ist bei zwölf
        # Bildpunkten je Millimeter sechzig breit. Die Sperrfläche kommt
        # deshalb aus der **projizierten** Ausdehnung des Werkzeugs; ohne
        # vorbereitetes Werkzeug bleibt es beim Mindestabstand.
        spot = screen(surface.point)
        # **Und der Mindestabstand ist eine Zeilenhöhe, keine vier Bildpunkte.**
        # Bei einem Merkmal, das schon sitzt, fallen alle Bezugspunkte auf seine
        # Mitte: Die Abstände zur eigenen Stelle sind null, und die drei Felder
        # standen als Stapel auf dem Loch (Robert, 10.09.2026: „dass die maße …
        # ein bisschen entfernt stehen ähnlich wie die angaben mit dem
        # volumen"). Gemessen wird in Zeilenhöhen und nicht in Pixeln, damit der
        # Abstand bei jeder Anzeigeskalierung und Schriftgröße gleich aussieht.
        room_around = max(SPACE, self._centre.sizeHint().height() * 2)
        reach = room_around
        if self._tool_context is not None:
            half = float(np.max(self._tool_context.mesh.bounds.size[:2])) / 2.0
            edge = screen(tuple(point + np.asarray(surface.frame.x_axis) * half))
            reach = max(
                room_around,
                round(math.hypot(edge.x() - spot.x(), edge.y() - spot.y())) + ROOMY,
            )
        # Geklemmt, bevor daraus ein ``QRect`` wird: Eine Projektion aus einer
        # sehr nahen Kamera liefert Werte jenseits von int32, und die Ausnahme
        # führe aus einem Qt-Slot heraus.
        blocked = QRect(
            max(bounds.left() - reach, min(round(spot.x()), bounds.right() + reach)),
            max(bounds.top() - reach, min(round(spot.y()), bounds.bottom() + reach)),
            1,
            1,
        ).adjusted(-reach, -reach, reach, reach)
        occupied: list[QRect] = [blocked]
        # **Der Bewegungsgriff bleibt frei.** Er hängt am selben Merkmal und
        # greift weiter als das Werkzeug; ein Feld darüber nimmt die
        # Zeigerereignisse an, und dann sind Pfeile und Ringe sichtbar und tot
        # (Robert, 10.09.2026). Als eigenes Rechteck und nicht als größeres
        # ``reach``, weil der Griff an der Mitte der Bohrung sitzt und der
        # Setzpunkt an ihrer Mündung.
        handle = self.viewport.gizmo_reach()
        if handle is not None:
            origin, span = handle
            middle = screen(origin)
            rim = screen(tuple(np.asarray(origin) + np.asarray(surface.frame.x_axis) * span))
            around = max(
                SPACE, round(math.hypot(rim.x() - middle.x(), rim.y() - middle.y())) + ROOMY
            )
            occupied.append(
                QRect(
                    max(bounds.left() - around, min(round(middle.x()), bounds.right() + around)),
                    max(bounds.top() - around, min(round(middle.y()), bounds.bottom() + around)),
                    1,
                    1,
                ).adjusted(-around, -around, around, around)
            )
        positions: dict[QWidget, QRect] = {}
        for widget, wanted, _line in sorted(pending, key=lambda entry: -entry[0].width()):
            width, height = widget.width(), widget.height()
            left, right = bounds.left(), bounds.right() - width + 1
            top, bottom = bounds.top(), bounds.bottom() - height + 1
            xs = {left, right, max(left, min(round(wanted.x() - width / 2), right))}
            ys = {top, bottom, max(top, min(round(wanted.y() - height / 2), bottom))}
            for taken in occupied:
                xs.update((taken.left() - width - SPACE, taken.right() + SPACE + 1))
                ys.update((taken.top() - height - SPACE, taken.bottom() + SPACE + 1))
            candidates = [
                QRect(x, y, width, height)
                for x in xs
                for y in ys
                if left <= x <= right
                and top <= y <= bottom
                and not any(
                    QRect(x, y, width, height).intersects(
                        taken.adjusted(-SPACE, -SPACE, SPACE, SPACE)
                    )
                    for taken in occupied
                )
            ]
            if not candidates:
                # Fünf Felder passen im unterstützten Desktopbereich in wenige
                # Zeilen. Diese feste Anordnung löst einen ungünstigen früheren
                # Platz, statt ein weiteres Feld am unteren Rand zu stapeln.
                positions.clear()
                x, y, row_height = bounds.left(), bounds.top(), 0
                for pending_widget, _wanted, _line in pending:
                    if x > bounds.left() and x + pending_widget.width() > bounds.right() + 1:
                        x, y, row_height = bounds.left(), y + row_height + SPACE, 0
                    platz = QRect(x, y, pending_widget.width(), pending_widget.height())
                    # **Auch die Notlage weicht dem Setzpunkt aus — solange
                    # danach noch Platz ist.** Sonst gälte die Zusage „man
                    # sieht, wohin man setzt" genau dort nicht, wo es eng wird.
                    # Die Grenze ist keine Feinheit: Bei starkem Zoom füllt die
                    # Vorschau das ganze Bild, und ein Ausweichen darunter
                    # schöbe die Felder aus der Ansicht heraus (gemessen an
                    # ``test_dimension_fields_do_not_overlap_at_zoomed_view_edges``:
                    # y = 20009 bei 600 px Höhe). Dann ist Überdecken das
                    # kleinere Übel — ein Feld außerhalb des Bildes ist keines.
                    unten = blocked.bottom() + SPACE + 1
                    if platz.intersects(blocked) and (
                        unten + pending_widget.height() - 1 <= bounds.bottom()
                    ):
                        x, y, row_height = bounds.left(), unten, 0
                        platz = QRect(x, y, pending_widget.width(), pending_widget.height())
                    positions[pending_widget] = platz
                    x += pending_widget.width() + SPACE
                    row_height = max(row_height, pending_widget.height())
                break
            chosen = min(
                candidates,
                key=lambda rect: (
                    (QPointF(rect.center()) - wanted).manhattanLength(),
                    rect.y(),
                    rect.x(),
                ),
            )
            positions[widget] = chosen
            occupied.append(chosen)
        for widget, _wanted, (start, end) in pending:
            rect = positions[widget]
            widget.move(rect.topLeft())
            widget.show()
            widget.raise_()
            middle = QPointF(rect.center())
            vector = end - start
            square = QPointF.dotProduct(vector, vector)
            along = (
                max(0.0, min(QPointF.dotProduct(middle - start, vector) / square, 1.0))
                if square
                else 0.0
            )
            anchor = start + vector * along
            direction = anchor - middle
            ratios = [1.0]
            if direction.x():
                ratios.append(rect.width() / (2 * abs(direction.x())))
            if direction.y():
                ratios.append(rect.height() / (2 * abs(direction.y())))
            self._canvas.leaders.append((middle + direction * min(ratios), anchor))
        # **Die Felder der Tiefenstufe gehören in beide Listen.** Aus der Maske
        # genommen, damit die Maßfläche nicht über ihnen liegt, und **nach** der
        # Leiste gehoben, damit sie erreichbar bleiben: Sie steht unten mittig,
        # und das Tiefenfeld sitzt darüber (Robert, 09.09.2026: „wenn ich die
        # tiefe setz, komm ich nicht in das bearbeitenfeld von der maßeinheit").
        shown = [widget for widget in (self._depth_measure, self._rest) if widget.isVisible()]
        self._canvas.refresh(tuple(widget.geometry() for widget in (self._bar, *positions, *shown)))
        self._bar.raise_()
        for widget in (*self._measures, *self._centre_measures, self._centre, *shown):
            widget.raise_()
        self.viewport._draw()
