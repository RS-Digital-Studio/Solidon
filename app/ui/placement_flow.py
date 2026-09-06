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
    QKeyEvent,
    QPainter,
    QPainterPath,
    QPainterPathStroker,
    QPen,
    QPolygonF,
    QRegion,
)
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QWidget
from shiboken6 import isValid

from app.core import expressions
from app.core.errors import ValidationError
from app.core.geom.mesh import as_mesh_data
from app.core.knowledge.parts.ops import normal_fields
from app.core.knowledge.profiles import for_object
from app.core.scene import placement
from app.core.types import Feature, SceneObject, Vec3
from app.i18n import tr
from app.ui.labels import LengthSpin, feature_name, length
from app.ui.leash import stop_watching_the_dying
from app.ui.op_dialog import OperationDialog
from app.ui.render.api import Item, PointerEvent, SurfaceStyle
from app.ui.style import NORMAL, ROOMY, SPACE


class _Dimensions(QWidget):
    """Maßpfeile im Bildraum, mit getrennten erreichbaren Zahlenfeldern."""

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.lines: list[tuple[QPointF, QPointF]] = []
        self.leaders: list[tuple[QPointF, QPointF]] = []
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
        for _start, end in self.leaders:
            marker = QPainterPath()
            marker.addEllipse(end, 4.0, 4.0)
            ink = ink.united(marker)
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
        for start, end in self.leaders:
            # Zuordnungslinien haben keine Maßpfeile. Die Endmarke verbindet
            # ein verschobenes Feld eindeutig mit seiner wirklichen Maßlinie.
            painter.setPen(QPen(backdrop, 3.0))
            painter.drawLine(start, end)
            painter.setPen(QPen(colour, 1.0, Qt.PenStyle.DotLine))
            painter.drawLine(start, end)
            painter.setPen(QPen(colour, 1.0))
            painter.setBrush(backdrop)
            painter.drawEllipse(end, 3.0, 3.0)
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
        self._confirm_waiting = False
        self._updating = False
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
        self.refresh_available()

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
        self._confirm_waiting = False
        self._surface = None
        self._serial += 1
        self.dialog.hide()
        self.window._clear_preview()
        self.viewport.set_placement_pointer(self.pointer)
        self._note.setText(tr("Klicken: platzieren · Abstand ändern: Maßfeld · Esc: zurück"))
        self._bar.show()
        self._accept.setEnabled(False)
        self.viewport.setFocus(Qt.FocusReason.OtherFocusReason)
        if self._change_op is None:
            self._request_tool()
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
        self._confirm_waiting = False
        self._timer.stop()
        self.viewport.set_placement_pointer(None)
        for widget in self._widgets():
            widget.hide()
        if self._tool is not None and self.viewport.renderer is not None:
            self.viewport.renderer.remove(self._tool)
        self._tool = None
        self._tool_context = None
        self._tool_key = ""
        if self._showing_input:
            self._showing_input = False
            self.viewport.show_scene(self.session.last_result)
        self._result = None
        self.viewport._draw()

    def dispose(self, _code: int = 0) -> None:
        if self._disposed:
            return
        self._stop()
        self._disposed = True
        for widget in self._widgets():
            widget.deleteLater()

    def _widgets(self) -> tuple[QWidget, ...]:
        return self._bar, self._canvas, self._centre, *self._measures, *self._centre_measures

    def pointer(self, event: PointerEvent) -> bool:
        """Linksklick gehört der Platzierung, alle Kameragesten bleiben frei."""
        if not self.active:
            return False
        if event.kind == "leave":
            return True
        if event.kind == "press" and event.button == "left":
            return True
        confirm = event.kind == "release" and event.button == "left"
        if confirm or (event.kind == "move" and not event.buttons):
            if self._commit_pending:
                return True
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
                        self._confirm_waiting = True
                        self.accept()
            self._next_surface()

        def failed(detail: str) -> None:
            done(None)
            if self.active and stamp == self._serial:
                self._note.setText(
                    tr("Andere Fläche wählen oder die Werte bearbeiten.") + " " + detail
                )

        self.session.placement_async(compute, done, failed)

    def _invalid(self, message: str) -> None:
        self._surface = None
        self._commit_pending = False
        self._confirm_waiting = False
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
        if self.spec_of().name not in {"move_feature", "duplicate_feature"}:
            chosen = result.scene.objects.get(self._object_id)
            return chosen or (candidates[0] if len(candidates) == 1 else None), None
        feature_id = self.dialog.values().get("at_feature")
        found = [
            (entry, entry.features[feature_id])
            for entry in candidates
            if feature_id in entry.features
        ]
        return found[0] if len(found) == 1 else (None, None)

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
        for name in ("x", "y", "z", *normal_fields(spec.params)):
            if name in values:
                values[name] = 0.0
        if "at_feature" in values and feature is None:
            values["at_feature"] = ""
        if "axis" in values:
            values["axis"] = "z"
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
                    if self._tool is not None:
                        renderer.remove(self._tool)
                    self._tool = None
                    if context is not None:
                        mesh = context.mesh
                        self._tool = renderer.add_surface(
                            np.asarray(mesh.raw.vertices, dtype=np.float64),
                            np.asarray(mesh.raw.faces, dtype=np.int64),
                            name="surface_placement_tool",
                            style=SurfaceStyle(
                                colour=self.viewport._object_colour,
                                opacity=0.45,
                                show_edges=False,
                                pickable=False,
                                keep_in_front=True,
                            ),
                        )
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
                if self._confirm_waiting:
                    self.accept()
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
        if not self._set_values():
            return
        self._stop()
        self.dialog.accept()

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
            if event.type() == QEvent.Type.FocusIn and watched in (
                *self._measures,
                *self._centre_measures,
            ):
                self._frozen = True
                self._pending = None
                self._commit_pending = False
                self._confirm_waiting = False
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
        self._bar.move(room.topLeft())
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
        self._accept.setEnabled(tool_valid and self._distance_valid and self._tool is not None)
        self._canvas.lines = []
        self._canvas.leaders = []
        for index, field in enumerate(self._measures):
            field.setVisible(valid and index < len(surface.edges))
        self._centre.hide()
        for field in self._centre_measures:
            field.setVisible(valid and bool(self._centre_id))
        if self._tool is not None:
            self._tool.set_visible(tool_valid)
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
        ratio = self.viewport._device_ratio()

        def screen(at: Vec3) -> QPointF:
            shown = self.viewport.view_point_of(at, self._object_id)
            x, y, _depth = renderer.world_to_display(shown)
            return QPointF(x / ratio, y / ratio)

        pending: list[tuple[QWidget, QPointF, tuple[QPointF, QPointF]]] = []

        def place(widget: QWidget, start: QPointF, end: QPointF) -> None:
            widget.setMaximumWidth(max(room.width(), 1))
            if isinstance(widget, QLabel):
                widget.setWordWrap(True)
            widget.adjustSize()
            pending.append((widget, (start + end) / 2, (start, end)))

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
        bounds = QRect(
            room.left(),
            self._bar.geometry().bottom() + NORMAL,
            max(room.width(), 1),
            max(room.bottom() - self._bar.geometry().bottom() - NORMAL + 1, 1),
        )
        occupied: list[QRect] = []
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
                for item, _wanted, _line in pending:
                    if x > bounds.left() and x + item.width() > bounds.right() + 1:
                        x, y, row_height = bounds.left(), y + row_height + SPACE, 0
                    positions[item] = QRect(x, y, item.width(), item.height())
                    x += item.width() + SPACE
                    row_height = max(row_height, item.height())
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
        self._canvas.refresh(tuple(widget.geometry() for widget in (self._bar, *positions)))
        self._bar.raise_()
        for widget in (*self._measures, *self._centre_measures, self._centre):
            widget.raise_()
        self.viewport._draw()
