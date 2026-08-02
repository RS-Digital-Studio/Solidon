"""Der grafische Skizzeneditor (Bauplan §30.1, Stufe zwei).

Zeichnen, Bedingungen über Werkzeugleiste und Kontextmenü, der Solver läuft
nach jedem Schritt und die Freiheitsgrade stehen live in der Statuszeile.
Die Skizze bleibt, was sie in Stufe eins war: ein Parameterwert der
Operation, die sie verbraucht — der Editor erzeugt denselben Text, den auch
die Grundformen erzeugen, und alles Weitere (Cache, Undo, Agent-Sperre)
gilt unverändert.

Bei einem Konflikt bleibt die letzte gültige Lage sichtbar und die
Statuszeile nennt das kollidierende Bedingungspaar — nie nur
„fehlgeschlagen" (Regel 17). Eine unterbestimmte Skizze ist kein Fehler,
sondern eine Zahl in der Statuszeile (§30.1).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import replace
from typing import Any

from PySide6.QtCore import QPoint, QPointF, Qt, Signal
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPen, QShortcut
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core.errors import AppError, SketchConflictError
from app.core.sketch import shapes
from app.core.sketch.serialize import sketch_from_text, sketch_to_text
from app.core.sketch.solver import solve_sketch
from app.core.types import (
    Sketch,
    SketchConstraint,
    SketchConstraintKind,
    SketchElement,
    SolvedSketch,
)
from app.i18n import tr

#: Fangradius in Pixeln: näher als das an einem Punkt heißt „dieser Punkt".
SNAP_PX = 8.0

#: Trefferabstand für Linien und Ränder, in Pixeln.
PICK_PX = 5.0

#: Eine leere Skizze beginnt auf der XY-Ebene — die Ops setzen sie über
#: ihren Flächenparameter dorthin, wo sie hingehört (§30.1).
EMPTY = Sketch(plane="plane:xy", elements=())


def _constraint_label(kind: SketchConstraintKind) -> str:
    """Der Name der Bedingung als Wort — die Liste trägt ihn, kein Symbol
    allein (Regel 18)."""
    return {
        "distance": tr("Abstand"),
        "coincident": tr("Deckung"),
        "horizontal": tr("Waagerecht"),
        "vertical": tr("Senkrecht"),
        "parallel": tr("Parallel"),
        "perpendicular": tr("Rechtwinklig"),
        "tangent": tr("Tangential"),
        "symmetric": tr("Symmetrisch"),
        "fixed": tr("Fest"),
    }[kind]


def flat_offsets(sketch: Sketch) -> list[int]:
    """Der flache Punktindex, an dem jedes Element beginnt (§30.1)."""
    offsets: list[int] = []
    total = 0
    for element in sketch.elements:
        offsets.append(total)
        total += len(element.points)
    return offsets


def _flat_points(sketch: Sketch) -> list[tuple[float, float]]:
    return [point for element in sketch.elements for point in element.points]


def _located(sketch: Sketch, flat: int) -> tuple[int, int]:
    """Elementindex und lokaler Punktindex zu einem flachen Index."""
    offsets = flat_offsets(sketch)
    for index in reversed(range(len(offsets))):
        if flat >= offsets[index]:
            return index, flat - offsets[index]
    raise IndexError(flat)


class SketchCanvas(QWidget):
    """Die Zeichenfläche: Raster, Elemente, Auswahl, Werkzeuge.

    Alle Änderungen laufen über Methoden, die auch ein Test rufen kann —
    die Mausereignisse übersetzen nur Klicks in genau diese Aufrufe.
    """

    sketchChanged = Signal()
    selectionChanged = Signal()
    statusChanged = Signal(str)

    def __init__(
        self,
        parent: QWidget | None = None,
        parameter_values: Mapping[str, float] | None = None,
    ) -> None:
        super().__init__(parent)
        self.setMinimumSize(420, 360)
        self.setMouseTracking(True)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self._params = dict(parameter_values or {})
        self.sketch: Sketch = EMPTY
        self.solved: SolvedSketch | None = None
        self.conflict: str = ""
        self.tool = "select"
        self._pending: list[int] = []
        """Beim Zeichnen: die flachen Indizes der schon gesetzten Punkte —
        eine Linie braucht zwei, ein Bogen drei Klicks."""
        self._pending_world: list[tuple[float, float]] = []
        self.selection: list[tuple[str, tuple[int, ...]]] = []
        """Die Auswahl in Klickreihenfolge: („point", (i,)) oder ein Element
        mit seinen flachen Punktindizes — „A parallel B" ist nicht „B
        parallel A"."""
        self._undo: list[Sketch] = []
        self._dragging: int | None = None
        self._scale = 4.0
        self._centre = QPointF(0.0, 0.0)
        self._panning: QPoint | None = None

    # --- Modell -----------------------------------------------------------------

    def set_sketch(self, sketch: Sketch) -> None:
        self.sketch = sketch
        self._pending.clear()
        self._pending_world.clear()
        self.selection.clear()
        self._resolve()

    def set_tool(self, tool: str) -> None:
        self.tool = tool
        self._pending.clear()
        self._pending_world.clear()
        self.update()

    def points(self) -> list[tuple[float, float]]:
        """Die gelösten Koordinaten — oder die gezeichneten, solange der
        Solver nichts Besseres weiß.

        Nach einem gescheiterten Lauf ist ``solved`` der letzte gültige
        Stand (§15.3) — hat die Skizze inzwischen mehr Punkte, zählen die
        gezeichneten, sonst griffe die Anzeige ins Leere."""
        drawn = _flat_points(self.sketch)
        if self.solved is not None:
            solved = [point for element in self.solved.elements for point in element.points]
            if len(solved) == len(drawn):
                return solved
        return drawn

    def _remember(self) -> None:
        self._undo.append(self.sketch)

    def undo(self) -> None:
        """Ctrl+Z gilt auch hier — der Editor ist kein Ort ohne Rückweg."""
        if not self._undo:
            return
        self.set_sketch(self._undo.pop())

    def _apply(self, sketch: Sketch) -> None:
        self._remember()
        self.sketch = sketch
        self._resolve()

    def _resolve(self) -> None:
        """Ein Lauf des Solvers nach jeder Änderung (§30.1).

        Ein Konflikt lässt die letzte gültige Lage stehen (§15.3) und wird
        zur Meldung mit dem benannten Paar; jeder andere Fehler ebenso.
        """
        self.conflict = ""
        if not self.sketch.elements:
            self.solved = None
        else:
            try:
                self.solved = solve_sketch(self.sketch, self._params)
            except SketchConflictError as error:
                self.conflict = str(error.detail or error.title)
            except AppError as error:
                self.conflict = str(error.detail or error.title)
        self.sketchChanged.emit()
        self.statusChanged.emit(self.status_text())
        self.update()

    def status_text(self) -> str:
        if self.conflict:
            return self.conflict
        if self.solved is None:
            return tr("Leere Skizze — zeichnen oder eine Grundform einfügen.")
        if self.solved.free_dof == 0:
            return tr("Bestimmt — alle Freiheitsgrade sind vergeben.")
        return f"{self.solved.free_dof} {tr('Freiheitsgrade frei')}"

    # --- Bearbeitung (auch für Tests) ---------------------------------------------

    def add_element(self, kind: str, points: tuple[tuple[float, float], ...]) -> None:
        element = SketchElement(kind, points)  # type: ignore[arg-type]
        self._apply(replace(self.sketch, elements=(*self.sketch.elements, element)))

    def add_constraint(
        self, kind: SketchConstraintKind, targets: tuple[int, ...], value: str = ""
    ) -> None:
        constraint = SketchConstraint(kind, targets, value)
        self._apply(replace(self.sketch, constraints=(*self.sketch.constraints, constraint)))

    def remove_constraint(self, index: int) -> None:
        remaining = tuple(entry for at, entry in enumerate(self.sketch.constraints) if at != index)
        self._apply(replace(self.sketch, constraints=remaining))

    def insert_shape(self, sketch: Sketch) -> None:
        """Fügt eine Grundform als weitere Elemente ein — mit verschobenen
        Bedingungszielen, denn die flachen Indizes zählen über die ganze
        Skizze."""
        shift = len(_flat_points(self.sketch))
        moved = tuple(
            SketchConstraint(
                entry.kind,
                tuple(target + shift for target in entry.targets),
                entry.value,
            )
            for entry in sketch.constraints
        )
        self._apply(
            replace(
                self.sketch,
                elements=(*self.sketch.elements, *sketch.elements),
                constraints=(*self.sketch.constraints, *moved),
            )
        )

    def remove_selected(self) -> None:
        """Entfernt die gewählten Elemente — und jede Bedingung, die einen
        ihrer Punkte liest; die übrigen Ziele werden umnummeriert."""
        element_indices = {_located(self.sketch, entry[1][0])[0] for entry in self.selection}
        if not element_indices:
            return

        offsets = flat_offsets(self.sketch)
        removed: set[int] = set()
        for index in element_indices:
            begin = offsets[index]
            removed.update(range(begin, begin + len(self.sketch.elements[index].points)))

        mapping: dict[int, int] = {}
        fresh = 0
        for old in range(len(_flat_points(self.sketch))):
            if old in removed:
                continue
            mapping[old] = fresh
            fresh += 1

        elements = tuple(
            element for at, element in enumerate(self.sketch.elements) if at not in element_indices
        )
        constraints = tuple(
            SketchConstraint(
                entry.kind, tuple(mapping[target] for target in entry.targets), entry.value
            )
            for entry in self.sketch.constraints
            if all(target in mapping for target in entry.targets)
        )
        self.selection.clear()
        self._apply(replace(self.sketch, elements=elements, constraints=constraints))
        self.selectionChanged.emit()

    def move_point(self, flat: int, x: float, y: float) -> None:
        """Verschiebt einen Punkt und lässt den Solver den Rest ziehen."""
        element_index, local = _located(self.sketch, flat)
        element = self.sketch.elements[element_index]
        points = list(element.points)
        points[local] = (x, y)
        elements = list(self.sketch.elements)
        elements[element_index] = SketchElement(element.kind, tuple(points))
        self.sketch = replace(self.sketch, elements=tuple(elements))
        self._resolve()

    # --- Auswahl ------------------------------------------------------------------

    def selected_pattern(self) -> tuple[str, ...]:
        """Die Sorte jedes Auswahleintrags, für die Bedingungsknöpfe."""
        return tuple(entry[0] for entry in self.selection)

    def selection_targets(self) -> tuple[int, ...]:
        """Alle flachen Punktindizes der Auswahl, in Klickreihenfolge."""
        collected: list[int] = []
        for entry in self.selection:
            collected.extend(entry[1])
        return tuple(collected)

    def _select(self, entry: tuple[str, tuple[int, ...]], extend: bool) -> None:
        if not extend:
            self.selection.clear()
        if entry in self.selection:
            self.selection.remove(entry)
        else:
            self.selection.append(entry)
        self.selectionChanged.emit()
        self.update()

    # --- Koordinaten --------------------------------------------------------------

    def _to_screen(self, x: float, y: float) -> QPointF:
        return QPointF(
            self.width() / 2.0 + (x - self._centre.x()) * self._scale,
            self.height() / 2.0 - (y - self._centre.y()) * self._scale,
        )

    def _to_world(self, position: QPointF) -> tuple[float, float]:
        return (
            (position.x() - self.width() / 2.0) / self._scale + self._centre.x(),
            -(position.y() - self.height() / 2.0) / self._scale + self._centre.y(),
        )

    def _hit_point(self, position: QPointF) -> int | None:
        best: tuple[float, int] | None = None
        for flat, (x, y) in enumerate(self.points()):
            screen = self._to_screen(x, y)
            distance = math.hypot(screen.x() - position.x(), screen.y() - position.y())
            if distance <= SNAP_PX and (best is None or distance < best[0]):
                best = (distance, flat)
        return best[1] if best is not None else None

    def _hit_element(self, position: QPointF) -> tuple[str, tuple[int, ...]] | None:
        offsets = flat_offsets(self.sketch)
        points = self.points()
        wx, wy = self._to_world(position)
        tolerance = PICK_PX / self._scale
        for index, element in enumerate(self.sketch.elements):
            begin = offsets[index]
            if element.kind == "line":
                a, b = points[begin], points[begin + 1]
                if _segment_distance(a, b, (wx, wy)) <= tolerance:
                    return ("line", (begin, begin + 1))
            elif element.kind in ("circle", "arc"):
                centre = points[begin]
                rim = points[begin + 1]
                radius = math.hypot(rim[0] - centre[0], rim[1] - centre[1])
                span = math.hypot(wx - centre[0], wy - centre[1])
                if abs(span - radius) <= tolerance:
                    flats = tuple(range(begin, begin + len(element.points)))
                    return (element.kind, flats)
        return None

    # --- Mausereignisse -------------------------------------------------------------

    def mousePressEvent(self, event: Any) -> None:  # noqa: N802 - Qt gibt den Namen
        position = QPointF(event.position())
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = event.position().toPoint()
            return
        if event.button() == Qt.MouseButton.RightButton:
            self._context_menu(event)
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return

        if self.tool == "select":
            hit = self._hit_point(position)
            if hit is not None:
                self._select(
                    ("point", (hit,)), bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
                )
                self._remember()
                self._dragging = hit
                return
            element = self._hit_element(position)
            if element is not None:
                self._select(element, bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier))
                return
            if not event.modifiers():
                self.selection.clear()
                self.selectionChanged.emit()
                self.update()
            return

        self.place(position)

    def place(self, position: QPointF) -> None:
        """Ein Klick eines Zeichenwerkzeugs: Punkt setzen, Element schließen.

        Ein Klick nahe eines vorhandenen Punkts fängt — das neue Element
        bekommt dann eine Deckungs-Bedingung statt einer Kopie der Zahl.
        Element und Deckungen kommen als **ein** Schritt an, damit ein
        Rückgängig den ganzen Klickzug nimmt, nicht seine Hälften.
        """
        snapped = self._hit_point(position)
        world = self.points()[snapped] if snapped is not None else self._to_world(position)
        self._pending.append(snapped if snapped is not None else -1)
        self._pending_world.append(world)

        needed = {"point": 1, "line": 2, "circle": 2, "arc": 3}[self.tool]
        if len(self._pending_world) < needed:
            self.update()
            return

        begin = len(_flat_points(self.sketch))
        element = SketchElement(self.tool, tuple(self._pending_world))  # type: ignore[arg-type]
        snapped_pairs = tuple(
            SketchConstraint("coincident", (snapped_flat, begin + local))
            for local, snapped_flat in enumerate(self._pending)
            if snapped_flat >= 0
        )
        kept = self._pending_world[-1]
        self._pending.clear()
        self._pending_world.clear()
        self._apply(
            replace(
                self.sketch,
                elements=(*self.sketch.elements, element),
                constraints=(*self.sketch.constraints, *snapped_pairs),
            )
        )
        if self.tool == "line":
            # Ein Linienzug: das Ende ist der Anfang der nächsten — mit
            # Deckung auf den eben gesetzten Punkt.
            self._pending.append(begin + 1)
            self._pending_world.append(kept)

    def mouseMoveEvent(self, event: Any) -> None:  # noqa: N802 - Qt gibt den Namen
        if self._panning is not None:
            delta = event.position().toPoint() - self._panning
            self._panning = event.position().toPoint()
            self._centre = QPointF(
                self._centre.x() - delta.x() / self._scale,
                self._centre.y() + delta.y() / self._scale,
            )
            self.update()
            return
        if self._dragging is not None and event.buttons() & Qt.MouseButton.LeftButton:
            wx, wy = self._to_world(QPointF(event.position()))
            self.move_point(self._dragging, wx, wy)

    def mouseReleaseEvent(self, event: Any) -> None:  # noqa: N802 - Qt gibt den Namen
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = None
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = None

    def wheelEvent(self, event: Any) -> None:  # noqa: N802 - Qt gibt den Namen
        factor = 1.25 if event.angleDelta().y() > 0 else 0.8
        self._scale = min(max(self._scale * factor, 0.5), 100.0)
        self.update()

    def keyPressEvent(self, event: Any) -> None:  # noqa: N802 - Qt gibt den Namen
        if event.key() == Qt.Key.Key_Escape and self._pending_world:
            self._pending.clear()
            self._pending_world.clear()
            self.update()
            return
        if event.key() == Qt.Key.Key_Delete:
            self.remove_selected()
            return
        super().keyPressEvent(event)

    def _context_menu(self, event: Any) -> None:
        """Bedingungen am Ort der Auswahl — §30.1 nennt das Kontextmenü
        ausdrücklich."""
        dialog = self.parent()
        offers = getattr(dialog, "constraint_offers", None)
        request = getattr(dialog, "request_constraint", None)
        if offers is None or request is None:
            return
        menu = QMenu(self)
        for kind, enabled in offers().items():
            action = menu.addAction(_constraint_label(kind))
            action.setEnabled(enabled)
            action.triggered.connect(lambda _checked=False, chosen=kind: request(chosen))
        menu.exec(event.globalPosition().toPoint())

    # --- Zeichnen -------------------------------------------------------------------

    def paintEvent(self, _event: Any) -> None:  # noqa: N802 - Qt gibt den Namen
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        palette = self.palette()
        painter.fillRect(self.rect(), palette.base())

        self._paint_grid(painter)

        chosen_points = {entry[1][0] for entry in self.selection if entry[0] == "point"}
        chosen_elements: set[int] = set()
        for entry in self.selection:
            if entry[0] != "point":
                chosen_elements.add(_located(self.sketch, entry[1][0])[0])

        points = self.points()
        offsets = flat_offsets(self.sketch)
        line_colour = palette.text().color()
        chosen_colour = palette.highlight().color()
        for index, element in enumerate(self.sketch.elements):
            begin = offsets[index]
            selected = index in chosen_elements
            pen = QPen(chosen_colour if selected else line_colour)
            pen.setWidthF(3.0 if selected else 1.6)
            painter.setPen(pen)
            self._paint_element(painter, element, points, begin)

        for flat, (x, y) in enumerate(points):
            screen = self._to_screen(x, y)
            selected = flat in chosen_points
            painter.setPen(QPen(chosen_colour if selected else line_colour, 1.0))
            painter.setBrush(chosen_colour if selected else palette.base().color())
            radius = 5.0 if selected else 3.5
            painter.drawEllipse(screen, radius, radius)

        self._paint_measures(painter, points)
        self._paint_pending(painter)

    def _paint_grid(self, painter: QPainter) -> None:
        palette = self.palette()
        minor = QColor(palette.mid().color())
        minor.setAlpha(60)
        major = QColor(palette.mid().color())
        major.setAlpha(140)
        left, top = self._to_world(QPointF(0, 0))
        right, bottom = self._to_world(QPointF(self.width(), self.height()))
        step = 10.0
        x = math.floor(left / step) * step
        while x <= right:
            screen = self._to_screen(x, 0.0)
            painter.setPen(QPen(major if abs(x % 50.0) < 1e-9 else minor, 1.0))
            painter.drawLine(QPointF(screen.x(), 0.0), QPointF(screen.x(), float(self.height())))
            x += step
        y = math.floor(bottom / step) * step
        while y <= top:
            screen = self._to_screen(0.0, y)
            painter.setPen(QPen(major if abs(y % 50.0) < 1e-9 else minor, 1.0))
            painter.drawLine(QPointF(0.0, screen.y()), QPointF(float(self.width()), screen.y()))
            y += step
        axis = QPen(major, 1.4)
        painter.setPen(axis)
        origin = self._to_screen(0.0, 0.0)
        painter.drawLine(QPointF(0.0, origin.y()), QPointF(float(self.width()), origin.y()))
        painter.drawLine(QPointF(origin.x(), 0.0), QPointF(origin.x(), float(self.height())))

    def _paint_element(
        self,
        painter: QPainter,
        element: SketchElement,
        points: list[tuple[float, float]],
        begin: int,
    ) -> None:
        if element.kind == "line":
            painter.drawLine(self._to_screen(*points[begin]), self._to_screen(*points[begin + 1]))
        elif element.kind == "circle":
            centre = points[begin]
            rim = points[begin + 1]
            radius = math.hypot(rim[0] - centre[0], rim[1] - centre[1]) * self._scale
            painter.drawEllipse(self._to_screen(*centre), radius, radius)
        elif element.kind == "arc":
            centre, start, end = points[begin], points[begin + 1], points[begin + 2]
            radius = math.hypot(start[0] - centre[0], start[1] - centre[1])
            screen_radius = radius * self._scale
            centre_screen = self._to_screen(*centre)
            from PySide6.QtCore import QRectF

            box = QRectF(
                centre_screen.x() - screen_radius,
                centre_screen.y() - screen_radius,
                screen_radius * 2.0,
                screen_radius * 2.0,
            )
            begin_angle = math.degrees(math.atan2(start[1] - centre[1], start[0] - centre[0]))
            end_angle = math.degrees(math.atan2(end[1] - centre[1], end[0] - centre[0]))
            sweep = (end_angle - begin_angle) % 360.0
            painter.drawArc(box, int(begin_angle * 16), int(sweep * 16))

    def _paint_measures(self, painter: QPainter, points: list[tuple[float, float]]) -> None:
        """Maßbedingungen stehen als Text an ihrer Strecke — der Wert oder
        der Ausdruck, so wie er gilt."""
        painter.setPen(QPen(self.palette().text().color(), 1.0))
        for entry in self.sketch.constraints:
            if entry.kind != "distance" or len(entry.targets) != 2:
                continue
            a = points[entry.targets[0]]
            b = points[entry.targets[1]]
            middle = self._to_screen((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
            painter.drawText(middle, entry.value)

    def _paint_pending(self, painter: QPainter) -> None:
        if not self._pending_world:
            return
        pen = QPen(self.palette().highlight().color(), 1.2, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        for world in self._pending_world:
            painter.drawEllipse(self._to_screen(*world), 4.0, 4.0)


def _segment_distance(
    a: tuple[float, float], b: tuple[float, float], probe: tuple[float, float]
) -> float:
    ax, ay = a
    bx, by = b
    px, py = probe
    dx, dy = bx - ax, by - ay
    length_squared = dx * dx + dy * dy
    if length_squared <= 0.0:
        return math.hypot(px - ax, py - ay)
    t = max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / length_squared))
    return math.hypot(px - (ax + t * dx), py - (ay + t * dy))


class ExpressionDialog(QDialog):
    """Ein Maß als Ausdruck der Parametergrammatik (§13) — mit
    Inline-Prüfung statt eines Fensters auf dem Fenster."""

    def __init__(
        self,
        parameter_values: Mapping[str, float],
        start: str = "",
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Abstand"))
        self.setMinimumWidth(320)
        self._values = dict(parameter_values)

        hint = QLabel(tr("Eine Zahl oder ein Ausdruck — Projektparameter mit @name."), self)
        hint.setWordWrap(True)
        self.field = QLineEdit(start, self)
        self.problem = QLabel("", self)
        self.problem.setWordWrap(True)
        self.problem.setVisible(False)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok is not None:
            ok.setText(tr("Maß setzen"))
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(hint)
        layout.addWidget(self.field)
        layout.addWidget(self.problem)
        layout.addWidget(buttons)

    def _accept(self) -> None:
        from app.core.scene import expressions

        text = self.field.text().strip()
        if not text:
            self.problem.setText(tr("Ein Maß braucht einen Wert."))
            self.problem.setVisible(True)
            return
        try:
            expressions.evaluate(text, self._values)
        except AppError as error:
            self.problem.setText(str(error.detail or error.title))
            self.problem.setVisible(True)
            return
        self.accept()

    def expression(self) -> str:
        return self.field.text().strip()


#: Welche Auswahlmuster eine Bedingung braucht — die Knöpfe folgen dem, statt
#: eine falsche Auswahl mit einem Fehler zu quittieren.
_NEEDS: dict[SketchConstraintKind, tuple[tuple[str, ...], ...]] = {
    "distance": (("point", "point"),),
    "coincident": (("point", "point"),),
    "horizontal": (("line",),),
    "vertical": (("line",),),
    "parallel": (("line", "line"),),
    "perpendicular": (("line", "line"),),
    "tangent": (("line", "circle"), ("line", "arc")),
    "symmetric": (("point", "point", "line"),),
    "fixed": (("point",),),
}


class SketchEditorDialog(QDialog):
    """Zeichenfläche, Werkzeugleiste, Bedingungsliste, Statuszeile (§30.1)."""

    def __init__(
        self,
        text: str = "",
        parameter_values: Mapping[str, float] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Skizze zeichnen"))
        self.resize(860, 560)
        self._params = dict(parameter_values or {})

        self.canvas = SketchCanvas(self, parameter_values=self._params)
        opening = ""
        if text.strip():
            try:
                self.canvas.set_sketch(sketch_from_text(text))
            except AppError as error:
                # Ein beschädigter Text wird nicht still ersetzt: der Editor
                # beginnt leer, die Statuszeile sagt warum, und Verwerfen
                # lässt den alten Wert im Feld unangetastet.
                opening = str(error.detail or error.title)

        tools = QHBoxLayout()
        self._tool_buttons: dict[str, QToolButton] = {}
        for name, label in (
            ("select", tr("Auswählen")),
            ("point", tr("Punkt")),
            ("line", tr("Linie")),
            ("circle", tr("Kreis")),
            ("arc", tr("Bogen")),
        ):
            button = QToolButton(self)
            button.setText(label)
            button.setCheckable(True)
            button.setAutoRaise(True)
            button.toggled.connect(lambda active, chosen=name: self._tool_chosen(chosen, active))
            self._tool_buttons[name] = button
            tools.addWidget(button)
        self._tool_buttons["select"].setChecked(True)

        shapes_button = QToolButton(self)
        shapes_button.setText(tr("Grundform"))
        shapes_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        shapes_menu = QMenu(shapes_button)
        for label, factory in (
            (tr("Rechteck 40 × 20"), lambda: shapes.rectangle(40.0, 20.0)),
            (tr("Langloch 40 × 10"), lambda: shapes.slot(40.0, 10.0)),
            (tr("Kreis Ø 20"), lambda: shapes.circle(20.0)),
            (tr("Sechseck Ø 20"), lambda: shapes.polygon(20.0, 6)),
        ):
            action = shapes_menu.addAction(label)
            action.triggered.connect(
                lambda _checked=False, make=factory: self.canvas.insert_shape(make())
            )
        shapes_button.setMenu(shapes_menu)
        tools.addWidget(shapes_button)
        tools.addStretch(1)

        undo_button = QToolButton(self)
        undo_button.setText(tr("Rückgängig"))
        undo_button.setAutoRaise(True)
        undo_button.clicked.connect(self.canvas.undo)
        tools.addWidget(undo_button)

        constraints_row = QHBoxLayout()
        self._constraint_buttons: dict[SketchConstraintKind, QPushButton] = {}
        for kind in _NEEDS:
            constraint_button = QPushButton(_constraint_label(kind), self)
            constraint_button.clicked.connect(
                lambda _checked=False, chosen=kind: self.request_constraint(chosen)
            )
            self._constraint_buttons[kind] = constraint_button
            constraints_row.addWidget(constraint_button)
        constraints_row.addStretch(1)

        self.constraint_list = QListWidget(self)
        self.constraint_list.setToolTip(tr("Entf entfernt die gewählte Bedingung."))

        self.status = QLabel(opening or self.canvas.status_text(), self)
        self.status.setWordWrap(True)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok is not None:
            ok.setText(tr("Übernehmen"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        side = QVBoxLayout()
        side.addWidget(QLabel(tr("Bedingungen"), self))
        side.addWidget(self.constraint_list, stretch=1)

        middle = QHBoxLayout()
        middle.addWidget(self.canvas, stretch=1)
        middle.addLayout(side)

        layout = QVBoxLayout(self)
        layout.addLayout(tools)
        layout.addLayout(constraints_row)
        layout.addLayout(middle, stretch=1)
        layout.addWidget(self.status)
        layout.addWidget(buttons)

        self.canvas.sketchChanged.connect(self._refresh_constraints)
        self.canvas.selectionChanged.connect(self._refresh_buttons)
        self.canvas.statusChanged.connect(self.status.setText)
        # Undo gilt überall, auch hier (§19.2) — derselbe Griff wie im Fenster.
        QShortcut(QKeySequence.StandardKey.Undo, self, self.canvas.undo)
        self.constraint_list.installEventFilter(self)
        self._refresh_constraints()
        self._refresh_buttons()

    def _tool_chosen(self, name: str, active: bool) -> None:
        if not active:
            return
        for other, button in self._tool_buttons.items():
            if other != name and button.isChecked():
                button.setChecked(False)
        self.canvas.set_tool(name)

    def constraint_offers(self) -> dict[SketchConstraintKind, bool]:
        """Welche Bedingung zur Auswahl passt — Kontextmenü und Knöpfe lesen
        dieselbe Antwort."""
        pattern = self.canvas.selected_pattern()
        return {kind: pattern in patterns for kind, patterns in _NEEDS.items()}

    def request_constraint(self, kind: SketchConstraintKind) -> None:
        if not self.constraint_offers().get(kind):
            return
        targets = self.canvas.selection_targets()
        value = ""
        if kind == "distance":
            dialog = ExpressionDialog(self._params, parent=self)
            if dialog.exec() != ExpressionDialog.DialogCode.Accepted:
                return
            value = dialog.expression()
        if kind == "fixed":
            targets = targets[:1]
        self.canvas.add_constraint(kind, targets, value)

    def _refresh_buttons(self) -> None:
        for kind, button in self._constraint_buttons.items():
            button.setEnabled(self.constraint_offers()[kind])

    def _refresh_constraints(self) -> None:
        self.constraint_list.clear()
        for entry in self.canvas.sketch.constraints:
            label = _constraint_label(entry.kind)
            if entry.value:
                label = f"{label} {entry.value}"
            targets = ", ".join(str(target) for target in entry.targets)
            item = QListWidgetItem(f"{label}  ({targets})")
            self.constraint_list.addItem(item)

    def eventFilter(self, watched: Any, event: Any) -> bool:  # noqa: N802 - Qt gibt den Namen
        from PySide6.QtCore import QEvent

        if (
            watched is self.constraint_list
            and event.type() == QEvent.Type.KeyPress
            and event.key() == Qt.Key.Key_Delete
        ):
            row = self.constraint_list.currentRow()
            if row >= 0:
                self.canvas.remove_constraint(row)
            return True
        handled: bool = super().eventFilter(watched, event)
        return handled

    def sketch_text(self) -> str:
        """Der Parameterwert, wie ihn die Skizzen-Ops lesen (§30.1) — leer,
        wenn nichts gezeichnet wurde."""
        if not self.canvas.sketch.elements:
            return ""
        return sketch_to_text(self.canvas.sketch)


class SketchField(QWidget):
    """Der Editor eines ``kind="sketch"``-Parameters im Operationsdialog.

    Eine Zeile: was die Skizze ist, und der Knopf zum Zeichnen. Der Text
    selbst bleibt unsichtbar — er ist ein Speicherformat, keine Eingabe.
    """

    changed = Signal()

    def __init__(
        self,
        text: str = "",
        parameter_values: Mapping[str, float] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self._text = text
        self._params = dict(parameter_values or {})

        self.summary = QLabel(self)
        self.summary.setWordWrap(True)
        self.edit_button = QPushButton(tr("Zeichnen …"), self)
        self.edit_button.clicked.connect(self._edit)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.summary, stretch=1)
        layout.addWidget(self.edit_button)
        self._describe()

    def text(self) -> str:
        return self._text

    def set_text(self, text: str) -> None:
        self._text = text
        self._describe()
        self.changed.emit()

    def _describe(self) -> None:
        if not self._text.strip():
            self.summary.setText(tr("Keine — die Grundform der Operation gilt."))
            return
        try:
            sketch = sketch_from_text(self._text)
            solved = solve_sketch(sketch, self._params)
        except SketchConflictError as error:
            self.summary.setText(str(error.detail or error.title))
            return
        except AppError as error:
            self.summary.setText(str(error.detail or error.title))
            return
        state = (
            tr("bestimmt")
            if solved.free_dof == 0
            else f"{solved.free_dof} {tr('Freiheitsgrade frei')}"
        )
        self.summary.setText(f"{len(sketch.elements)} {tr('Elemente')} · {state}")

    def _edit(self) -> None:
        dialog = SketchEditorDialog(self._text, self._params, self)
        if dialog.exec() != SketchEditorDialog.DialogCode.Accepted:
            return
        self.set_text(dialog.sketch_text())
