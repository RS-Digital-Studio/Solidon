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
from collections.abc import Mapping, Sequence
from dataclasses import replace
from typing import Any

from PySide6.QtCore import QPoint, QPointF, Qt, Signal
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPainterPath, QPen, QShortcut
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
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
from app.core.sketch import edit, shapes
from app.core.sketch.serialize import sketch_from_text, sketch_to_text
from app.core.sketch.solver import solve_sketch
from app.core.types import (
    Sketch,
    SketchConstraint,
    SketchConstraintKind,
    SketchElement,
    SolvedSketch,
)
from app.core.units import DISPLAY_UNITS, EPS_DISPLAY
from app.i18n import tr
from app.ui.labels import length
from app.ui.palette import ROLES

#: Fangradius in Pixeln: näher als das an einem Punkt heißt „dieser Punkt".
SNAP_PX = 8.0

#: Trefferabstand für Linien und Ränder, in Pixeln.
PICK_PX = 5.0

#: Eine leere Skizze beginnt auf der XY-Ebene — die Ops setzen sie über
#: ihren Flächenparameter dorthin, wo sie hingehört (§30.1).
EMPTY = Sketch(plane="plane:xy", elements=())

#: Ab wann eine Fläche als waagerecht gilt und ab wann als senkrecht, gemessen
#: am Betrag der Z-Komponente ihrer Normalen. Die Werte entsprechen 15° und
#: 75° gegen die Waagerechte — dazwischen ist die Fläche geneigt, und dann ist
#: „parallel" oder „quer" beides falsch. Keine Toleranz im Sinne von Regel 7:
#: es geht um die Wortwahl eines Hinweises, nicht um Geometrie.
_FLAT_ENOUGH = 0.966
_STEEP_ENOUGH = 0.259


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
        "reference": tr("Referenzmaß"),
    }[kind]


def readable_measure(expression: str) -> str:
    """Ein Maß, wie es dastehen soll — nicht, wie es gespeichert ist.

    Grundformen schreiben ihre Maße mit neun Nachkommastellen, damit nie ein
    ``1e-05`` in einem Ausdruck landet (`shapes._number`). Im Speicherformat
    ist das richtig; an einer Bemaßung stand damit ``40.000000000``, wo 40
    gemeint ist. §11.2 sagt es klar: gerundet wird in der Anzeige.

    Ein Ausdruck, der keine reine Zahl ist, bleibt wörtlich stehen —
    ``=@width / 2`` ist die Aussage, und sie auszurechnen würde verbergen,
    dass hier ein Parameter hängt.
    """
    try:
        value = float(expression)
    except ValueError:
        return expression
    return length(value, with_unit=False)


def measure_label(constraint: SketchConstraint, points: list[tuple[float, float]]) -> str:
    """Was an einer Maßbedingung steht.

    Ein treibendes Maß zeigt seinen Ausdruck — das ist die Aussage, und sie
    gilt auch dann, wenn der Solver sie gerade nicht erfüllen konnte. Ein
    Referenzmaß hat keinen Ausdruck: es zeigt, was gerade da ist, in Klammern
    wie in jedem CAD, damit man die beiden nie verwechselt.
    """
    if constraint.kind != "reference":
        return readable_measure(constraint.value)
    first, second = constraint.targets[0], constraint.targets[1]
    if max(first, second) >= len(points):
        return ""
    ax, ay = points[first]
    bx, by = points[second]
    return f"({length(math.hypot(bx - ax, by - ay), with_unit=False)})"


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


#: Radius des Ursprungsrings in Bildpunkten. Etwas größer als ein
#: Skizzenpunkt, damit die beiden nicht zu verwechseln sind.
ORIGIN_RADIUS = 5.0


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
        self._face_normals: dict[str, tuple[float, float, float]] = {}
        """Die Normalen der Flächen, auf denen gezeichnet werden darf.

        Nur für den Hinweis zur Schichtrichtung — siehe ``offer_faces``."""
        self._bodies: list[Any] = []
        """Die Körper der Szene, für das Projizieren (E18).

        Nur Netze, keine Szene: der Zeichenbereich braucht die Kante, nicht
        das Objekt drumherum, und was er nicht kennt, kann er nicht
        veralten lassen."""
        self._bed: tuple[float, float] | None = None
        """Breite und Tiefe des Druckbetts, oder ``None``.

        Die Zeichenfläche ist der früheste Ort, an dem eine zu große Skizze
        auffallen kann — später kostet es einen Export, einen Slicerlauf und
        die Frage, warum das Teil nicht auf die Platte passt (E1)."""

    def set_bed(self, size: tuple[float, float] | None) -> None:
        """Die Grundfläche des Bauraums, gegen die gezeichnet wird."""
        self._bed = size
        self.update()

    def layer_note(self) -> str:
        """Wie die Schichten zu dieser Ebene liegen (E1).

        Auf XY liegen sie **parallel** zur Zeichenfläche: der Körper wächst aus
        dem Bild heraus, jede gezeichnete Linie ist eine Kontur. Auf XZ und YZ
        stehen sie quer dazu — dann läuft die Schichtung durch die Zeichnung
        hindurch, und was hier waagerecht aussieht, ist im Druck eine Fuge.

        Bei einer angeklickten Fläche entscheidet ihre Neigung, und die ist
        bekannt: die Anwendung reicht sie mit der Fläche herein. Der Satz sagt
        deshalb auch dort etwas, statt sich auf „kommt darauf an"
        zurückzuziehen.

        Das entscheidet über Festigkeit und Überhänge und steht deshalb an der
        Ebenenwahl, wo es jemanden erreicht, bevor er zeichnet. Eine
        Beschriftung und keine Zeichnung: die Richtung ist ein Satz, kein Bild.
        """
        plane = self.sketch.plane
        if plane.startswith("feature:"):
            normal = self._face_normals.get(plane.partition(":")[2])
            if normal is None:
                return tr("Auf einer Fläche des Körpers — die Schichtrichtung folgt ihrer Neigung.")
            upright = abs(normal[2])
            if upright > _FLAT_ENOUGH:
                return tr("Schichten liegen parallel zur Zeichnung — sie wächst nach oben heraus.")
            if upright < _STEEP_ENOUGH:
                return tr(
                    "Schichten stehen quer zur Zeichnung — was hier waagerecht liegt, "
                    "wird eine Fuge."
                )
            return tr("Diese Fläche ist geneigt — der Körper wächst schräg zur Schichtung.")
        if plane == "plane:xy":
            return tr("Schichten liegen parallel zur Zeichnung — sie wächst nach oben heraus.")
        return tr(
            "Schichten stehen quer zur Zeichnung — was hier waagerecht liegt, wird eine Fuge."
        )

    def offer_faces(self, faces: Mapping[str, tuple[float, float, float]]) -> None:
        """Die planaren Flächen, auf denen gezeichnet werden kann.

        Nur die Normalen, nicht die Flächen selbst: der Zeichenbereich rechnet
        nicht in 3D, er braucht die Richtung ausschließlich für den Satz über
        die Schichtung. Alles Weitere macht ``app.core.sketch.planes`` bei der
        Auswertung neu — hier etwas zu speichern hieße, es veralten zu lassen.
        """
        self._face_normals = dict(faces)

    def offer_bodies(self, meshes: Sequence[Any]) -> None:
        """Woraus projiziert werden kann — die Körper der Szene."""
        self._bodies = list(meshes)

    def project_bodies(self) -> None:
        """Holt die Schnittkurven aller Körper als Hilfsgeometrie herein.

        Bei Weg 1 — fremdes Modell anpassen — ist das der Normalfall: eine
        Bohrung soll auf die vorhandene Kante ausgerichtet werden, und ohne
        die Kante in der Zeichnung bleibt nur Abmessen und Abtippen.
        """
        if not self._bodies:
            self.statusChanged.emit(tr("Es gibt keinen Körper, aus dem sich projizieren ließe."))
            return
        current = self.sketch
        problems: list[str] = []
        for mesh in self._bodies:
            try:
                current = edit.project(current, mesh)
            except AppError as error:
                problems.append(str(error.detail or error.title))
        if current is self.sketch:
            self.statusChanged.emit(problems[0] if problems else tr("Nichts zu projizieren."))
            return
        self._apply(current)

    def set_plane(self, plane: str) -> None:
        """Auf welcher Ebene die Skizze liegt (§30.1).

        Sie entscheidet, wohin extrudiert wird — nicht, wie gezeichnet wird:
        die Zeichenfläche bleibt eine Fläche, und die zwei Achsen darauf
        heißen je nach Ebene anders. Das steht in der Beschriftung, nicht in
        einer gedrehten Ansicht.
        """
        self._apply(replace(self.sketch, plane=plane))

    def outside_bed(self) -> bool:
        """Ob die Skizze über den Bauraum hinausragt.

        Gemessen an den gelösten Punkten und nicht am Umriss: ein Punkt
        außerhalb reicht, und ob die Kette dazwischen schließt, ist eine
        andere Frage mit einer anderen Meldung."""
        if self._bed is None:
            return False
        half_x, half_y = self._bed[0] / 2.0, self._bed[1] / 2.0
        return any(abs(x) > half_x or abs(y) > half_y for x, y in self.points())

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

    def toggle_construction(self) -> None:
        """Macht aus der Auswahl Hilfsgeometrie — und zurück (E18).

        Eine Mittellinie, an der zwei Bohrungen symmetrisch hängen, soll
        Bedingungen tragen und keine Kante im Körper werden. Umschalten statt
        zweier Werkzeuge: dieselbe Linie ist mal das eine, mal das andere, und
        wer sich vertut, klickt noch einmal.
        """
        indices = {_located(self.sketch, entry[1][0])[0] for entry in self.selection}
        if not indices:
            self.statusChanged.emit(tr("Erst Elemente auswählen."))
            return
        # Alle auf denselben Stand: sind sie gemischt, werden sie Hilfsgeometrie.
        target = not all(self.sketch.elements[index].construction for index in indices)
        elements = tuple(
            replace(element, construction=target) if at in indices else element
            for at, element in enumerate(self.sketch.elements)
        )
        self._apply(replace(self.sketch, elements=elements))

    def offset_selected(self, distance: float) -> None:
        """Legt eine versetzte Kopie der gewählten Elemente daneben."""
        self._change_selected(lambda indices: edit.offset(self.sketch, indices, distance))

    def mirror_selected(self, axis: str) -> None:
        """Spiegelt die gewählten Elemente an einer der beiden Achsen."""
        self._change_selected(lambda indices: edit.mirror(self.sketch, indices, axis))

    def _change_selected(self, run: Any) -> None:
        """Der gemeinsame Weg für Versetzen und Spiegeln.

        Beide arbeiten auf der Auswahl, beide melden ihren Fehler in die
        Statuszeile, und beide sind ein Schritt für das Rückgängig.
        """
        indices = tuple(sorted({_located(self.sketch, entry[1][0])[0] for entry in self.selection}))
        if not indices:
            self.statusChanged.emit(tr("Erst Elemente auswählen."))
            return
        try:
            self._apply(run(indices))
        except AppError as error:
            self.statusChanged.emit(str(error.detail or error.title))

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

        if self.tool in ("trim", "extend"):
            self.cut_or_grow(position)
            return

        self.place(position)

    def cut_or_grow(self, position: QPointF) -> None:
        """Trimmen und Verlängern: ein Klick auf die Hälfte, die es betrifft.

        Beide arbeiten am angeklickten Element und an derselben Geste — beim
        Trimmen fällt die geklickte Hälfte weg, beim Verlängern wächst sie.
        Gerechnet wird im Kern; hier steht nur, welches Element gemeint war.
        """
        hit = self._hit_element(position)
        if hit is None:
            self.statusChanged.emit(tr("Kein Element getroffen — auf eine Linie klicken."))
            return
        index = _located(self.sketch, hit[1][0])[0]
        world = self._to_world(position)
        try:
            changed = (
                edit.trim(self.sketch, index, world)
                if self.tool == "trim"
                else edit.extend(self.sketch, index, world)
            )
        except AppError as error:
            # Ein Fehler endet nie mit „fehlgeschlagen" (Regel 17) — und er
            # bleibt im Bild stehen, statt einen Dialog aufzumachen, den man
            # wegklickt, bevor man ihn gelesen hat.
            self.statusChanged.emit(str(error.detail or error.title))
            return
        self.selection.clear()
        self._apply(changed)
        self.selectionChanged.emit()

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

        if self.tool == "spline":
            # Ein Spline endet nicht bei einer Punktzahl, sondern wenn jemand
            # sagt, dass er fertig ist: Doppelklick, Eingabetaste oder ein
            # zweiter Klick auf denselben Punkt. Bis dahin sammelt er.
            self.update()
            return

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

    def finish_spline(self) -> None:
        """Den gesammelten Spline abschließen.

        Unter zwei Punkten entsteht nichts — ein Spline durch einen Punkt ist
        ein Punkt, und den gibt es als eigenes Werkzeug. Die gesammelten
        Klicks fallen dann weg statt eine ungültige Skizze zu erzeugen.
        """
        if self.tool != "spline" or len(self._pending_world) < 2:
            self._pending.clear()
            self._pending_world.clear()
            self.update()
            return
        begin = len(_flat_points(self.sketch))
        element = SketchElement("spline", tuple(self._pending_world))
        snapped_pairs = tuple(
            SketchConstraint("coincident", (snapped_flat, begin + local))
            for local, snapped_flat in enumerate(self._pending)
            if snapped_flat >= 0
        )
        self._pending.clear()
        self._pending_world.clear()
        self._apply(
            replace(
                self.sketch,
                elements=(*self.sketch.elements, element),
                constraints=(*self.sketch.constraints, *snapped_pairs),
            )
        )

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
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter) and self.tool == "spline":
            self.finish_spline()
            return
        if event.key() == Qt.Key.Key_Delete:
            self.remove_selected()
            return
        super().keyPressEvent(event)

    def mouseDoubleClickEvent(self, event: Any) -> None:  # noqa: N802 - Qt gibt den Namen
        """Doppelklick schließt den Spline — derselbe Griff wie in jedem CAD."""
        if self.tool == "spline":
            self.finish_spline()
            return
        super().mouseDoubleClickEvent(event)

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
        self._paint_bed(painter)

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
            if element.construction:
                # Gestrichelt und dünner: Hilfsgeometrie bildet kein Profil,
                # und das muss man sehen, bevor man extrudiert. Strichart
                # statt Farbe, damit die Aussage ohne Farbsehen ankommt
                # (Regel 18).
                pen.setStyle(Qt.PenStyle.DashLine)
                pen.setWidthF(1.2)
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

    def _paint_bed(self, painter: QPainter) -> None:
        """Die Grenze des Bauraums als Rechteck um den Ursprung (E1).

        Gestrichelt und beschriftet, nicht nur eingefärbt: Regel 18 gilt hier
        wie überall, und eine Linie, die man für Raster halten kann, sagt
        nichts. Wer darüber hinauszeichnet, sieht es an der Skizze — nicht
        erst, wenn der Slicer das Teil neben die Platte legt.
        """
        if self._bed is None:
            return
        half_x, half_y = self._bed[0] / 2.0, self._bed[1] / 2.0
        outside = self.outside_bed()
        colour = QColor(self.palette().text().color())
        colour.setAlpha(200 if outside else 110)
        pen = QPen(colour, 2.0 if outside else 1.2, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)
        top_left = self._to_screen(-half_x, half_y)
        bottom_right = self._to_screen(half_x, -half_y)
        painter.drawRect(
            int(top_left.x()),
            int(top_left.y()),
            int(bottom_right.x() - top_left.x()),
            int(bottom_right.y() - top_left.y()),
        )
        label = tr("Bauraum {x} × {y}").format(
            x=length(self._bed[0], with_unit=False),
            y=length(self._bed[1], with_unit=False),
        )
        if outside:
            label = f"{label} — {tr('die Skizze ragt darüber hinaus')}"
        painter.drawText(top_left + QPointF(4.0, -4.0), label)

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
        self._paint_scale(painter, step, left, right, bottom, top)
        self._paint_axes(painter)

    def _paint_scale(
        self, painter: QPainter, step: float, left: float, right: float, bottom: float, top: float
    ) -> None:
        """Zahlen an das Raster, alle fünfzig Millimeter.

        Ein Raster ohne Zahlen sagt nur, dass es ein Raster gibt. Fusion
        beschriftet seine Achsen, und ohne das weiß man beim Zeichnen nicht, ob
        ein Kästchen einen Millimeter bedeutet oder zehn — der Maßstab ändert
        sich mit jedem Rad am Zoom.
        """
        labelled = step * 5.0
        painter.setPen(QPen(self.palette().text().color(), 1.0))
        font = painter.font()
        font.setPointSizeF(max(font.pointSizeF() - 1.0, 6.0))
        painter.setFont(font)

        metrics = painter.fontMetrics()
        x = math.floor(left / labelled) * labelled
        while x <= right:
            if abs(x) > EPS_DISPLAY:
                screen = self._to_screen(x, 0.0)
                text = f"{x:.0f}"
                # Nur, wenn die Zahl ganz hinpasst: eine abgeschnittene „1"
                # am rechten Rand ist keine Angabe, sondern ein Fehler.
                if screen.x() + 2.0 + metrics.horizontalAdvance(text) <= self.width():
                    painter.drawText(QPointF(screen.x() + 2.0, self.height() - 4.0), text)
            x += labelled
        y = math.floor(bottom / labelled) * labelled
        while y <= top:
            if abs(y) > EPS_DISPLAY:
                screen = self._to_screen(0.0, y)
                if metrics.height() <= screen.y() - 2.0 <= self.height():
                    painter.drawText(QPointF(4.0, screen.y() - 2.0), f"{y:.0f}")
            y += labelled

    def _paint_axes(self, painter: QPainter) -> None:
        """Ursprung und Achsen, rot für X und grün für Y (E15).

        Vorher lagen beide in der Rasterfarbe: zwei Linien unter vielen, und
        wo der Nullpunkt liegt, musste man aus der Zeichnung erschließen. Die
        Farben sind dieselben wie am Achsenkreuz des Viewports und in jedem
        CAD, das jemand vorher benutzt hat — und weil Farbe nie allein trägt
        (Regel 18), steht der Buchstabe am Ende der Achse.
        """
        origin = self._to_screen(0.0, 0.0)
        for colour, name, line, label in (
            (ROLES["axis_x"], "X", (0.0, origin.y(), float(self.width()), origin.y()), True),
            (ROLES["axis_y"], "Y", (origin.x(), 0.0, origin.x(), float(self.height())), True),
        ):
            painter.setPen(QPen(QColor(colour), 1.6))
            painter.drawLine(QPointF(line[0], line[1]), QPointF(line[2], line[3]))
            if label:
                spot = (
                    QPointF(self.width() - 14.0, origin.y() - 6.0)
                    if name == "X"
                    else QPointF(origin.x() + 6.0, 14.0)
                )
                painter.drawText(spot, name)

        # Der Ursprung selbst: ein Ring, kein Punkt — ein gefüllter Kreis wäre
        # von einem Skizzenpunkt nicht zu unterscheiden.
        painter.setPen(QPen(self.palette().text().color(), 1.6))
        painter.setBrush(Qt.BrushStyle.NoBrush)
        painter.drawEllipse(origin, ORIGIN_RADIUS, ORIGIN_RADIUS)

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
        elif element.kind == "spline":
            # Als Kurve gezeichnet, nicht als Polygonzug: der Kern baut daraus
            # eine B-Spline durch dieselben Punkte, und eine Vorschau, die
            # Ecken zeigt, wo das Ergebnis keine hat, wäre eine Lüge über die
            # Geometrie. Qt kann kubische Bézier — vier Punkte je Stück, die
            # Kontrollpunkte aus den Nachbarn gemittelt (Catmull-Rom).
            path = QPainterPath(self._to_screen(*points[begin]))
            count = len(element.points)
            row = [points[begin + step] for step in range(count)]
            for index in range(count - 1):
                before = row[max(index - 1, 0)]
                first, second = row[index], row[index + 1]
                after = row[min(index + 2, count - 1)]
                path.cubicTo(
                    self._to_screen(
                        first[0] + (second[0] - before[0]) / 6.0,
                        first[1] + (second[1] - before[1]) / 6.0,
                    ),
                    self._to_screen(
                        second[0] - (after[0] - first[0]) / 6.0,
                        second[1] - (after[1] - first[1]) / 6.0,
                    ),
                    self._to_screen(*second),
                )
            painter.drawPath(path)

    def _paint_measures(self, painter: QPainter, points: list[tuple[float, float]]) -> None:
        """Maßbedingungen stehen als Text an ihrer Strecke — der Wert oder
        der Ausdruck, so wie er gilt."""
        painter.setPen(QPen(self.palette().text().color(), 1.0))
        for entry in self.sketch.constraints:
            if entry.kind not in ("distance", "reference") or len(entry.targets) != 2:
                continue
            a = points[entry.targets[0]]
            b = points[entry.targets[1]]
            middle = self._to_screen((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0)
            painter.drawText(middle, measure_label(entry, points))

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
    "reference": (("point", "point"),),
}


#: Die Zeichenkürzel, wie Fusion sie belegt (E16). Wer aus einem CAD kommt,
#: hat sie in den Fingern, und wer nicht, lernt sie an den Knöpfen — dort
#: steht jedes neben seinem Werkzeug (§19.2).
#:
#: Sie gelten **nur im Skizzenmodus**. Außerhalb liegen R und C auf Drehen und
#: Fasen; kontextabhängig zu belegen ist genau das, was Fusion tut, und der
#: einzige Weg, beide Sätze widerspruchsfrei zu haben.
TOOL_KEYS: dict[str, str] = {
    "select": "Esc",
    "line": "L",
    "circle": "C",
    "arc": "A",
    "point": "P",
    "spline": "S",
    "trim": "T",
}

#: Kürzel, die kein Werkzeug wählen, sondern etwas tun.
ACTION_KEYS: dict[str, str] = {
    "rectangle": "R",
    "distance": "D",
    "offset": "O",
    "construction": "X",
}


class SketchPanel(QWidget):
    """Zeichenfläche, Werkzeugleiste, Bedingungsliste, Statuszeile (§30.1).

    Der Inhalt ohne den Rahmen darum. Zwei Stellen benutzen ihn: der Dialog
    aus dem Operationsfeld und der Skizzenmodus im Fenster — und weil es
    derselbe ist, kann keiner der beiden ein Werkzeug bekommen, das der andere
    nicht hat.
    """

    sketchChanged = Signal()
    """Weitergereicht von der Zeichenfläche, damit ein Rahmen mithören kann."""

    def __init__(
        self,
        text: str = "",
        parameter_values: Mapping[str, float] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
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
            ("spline", tr("Spline")),
            ("trim", tr("Trimmen")),
            ("extend", tr("Verlängern")),
        ):
            button = QToolButton(self)
            key = TOOL_KEYS.get(name, "")
            button.setText(f"{label}  {key}" if key else label)
            button.setToolTip(label)
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
            (
                f"{tr('Rechteck 40 × 20')}  {ACTION_KEYS['rectangle']}",
                lambda: shapes.rectangle(40.0, 20.0),
            ),
            (tr("Langloch 40 × 10"), lambda: shapes.slot(40.0, 10.0)),
            (tr("Kreis Ø 20"), lambda: shapes.circle(20.0)),
            (tr("Sechseck Ø 20"), lambda: shapes.polygon(20.0, 6)),
            # Muster stehen bei den Grundformen und nicht in einem eigenen
            # Menü: sie sind dasselbe — eine fertige Skizze, die man einfügt
            # und danach bemaßt (Konzept P15, E11).
            (
                tr("Lochkreis Ø 50, 6 × Ø 4"),
                lambda: shapes.bolt_circle(pitch_diameter=50.0, count=6, hole_diameter=4.0),
            ),
            (
                tr("Lochraster 4 × 3, Abstand 10"),
                lambda: shapes.hole_grid(columns=4, rows=3, spacing=10.0, hole_diameter=3.0),
            ),
        ):
            action = shapes_menu.addAction(label)
            action.triggered.connect(
                lambda _checked=False, make=factory: self.canvas.insert_shape(make())
            )
        shapes_button.setMenu(shapes_menu)
        tools.addWidget(shapes_button)

        # Die Ebene gehört vor das Zeichnen, nicht hinter das Ergebnis: sie
        # entscheidet, wohin extrudiert wird (§30.1). Ein Auswahlfeld und
        # keine drei Knöpfe — eine Handlung, eine Stelle (Konzept P15, E11).
        self.plane_choice = QComboBox(self)
        for value, label in (
            ("plane:xy", tr("Ebene XY — liegend")),
            ("plane:xz", tr("Ebene XZ — stehend, nach hinten")),
            ("plane:yz", tr("Ebene YZ — stehend, zur Seite")),
        ):
            self.plane_choice.addItem(label, userData=value)
        self.plane_choice.setCurrentIndex(
            max(0, self.plane_choice.findData(self.canvas.sketch.plane))
        )
        self.plane_choice.currentIndexChanged.connect(
            lambda _index: self.canvas.set_plane(str(self.plane_choice.currentData()))
        )
        # Eigene Zeile: in der Werkzeugzeile bekam der Satz daneben so wenig
        # Breite, dass er auf sieben Zeilen umbrach und die ganze Leiste hoch
        # machte. Er gehört unter die Wahl, auf die er sich bezieht.
        plane_row = QHBoxLayout()
        plane_row.addWidget(self.plane_choice)

        # Was die Ebene für den Druck bedeutet, direkt daneben (E1). Ein Satz
        # an der Wahl erreicht jemanden, bevor er zeichnet; im Prüfbericht
        # stünde er, nachdem alles fertig ist.
        self.layer_note = QLabel(self.canvas.layer_note(), self)
        self.layer_note.setWordWrap(True)
        note_font = self.layer_note.font()
        note_font.setItalic(True)
        self.layer_note.setFont(note_font)
        self.canvas.sketchChanged.connect(lambda: self.layer_note.setText(self.canvas.layer_note()))
        plane_row.addWidget(self.layer_note, stretch=1)
        tools.addStretch(1)

        # Die drei Grundebenen stehen immer; die Flächen des Körpers kommen
        # dazu, sobald einer da ist. Deshalb hier keine feste Liste.
        self._plane_count = self.plane_choice.count()

        # Die Ändern-Gruppe (E17). Trimmen und Verlängern sind Werkzeuge und
        # stehen bei den anderen; Versetzen und Spiegeln sind Handlungen auf
        # der Auswahl und brauchen je eine Angabe — den Abstand und die Achse.
        self.offset_distance = QDoubleSpinBox(self)
        self.offset_distance.setDecimals(2)
        self.offset_distance.setRange(-1000.0, 1000.0)
        self.offset_distance.setValue(2.0)
        # Ein Einheitenzeichen ist keine Übersetzung — es kommt aus der
        # Einheitentabelle (§11.1).
        self.offset_distance.setSuffix(f" {DISPLAY_UNITS[0]}")
        self.offset_distance.setToolTip(tr("Um wie viel versetzt wird. Negativ ist nach innen."))

        offset_button = QToolButton(self)
        offset_button.setText(f"{tr('Versetzen')}  {ACTION_KEYS['offset']}")
        offset_button.setToolTip(tr("Versetzen"))
        offset_button.setAutoRaise(True)
        offset_button.clicked.connect(
            lambda: self.canvas.offset_selected(self.offset_distance.value())
        )

        mirror_button = QToolButton(self)
        mirror_button.setText(tr("Spiegeln"))
        mirror_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        mirror_menu = QMenu(mirror_button)
        for label, axis in ((tr("An der X-Achse"), "x"), (tr("An der Y-Achse"), "y")):
            entry = mirror_menu.addAction(label)
            entry.triggered.connect(
                lambda _checked=False, chosen=axis: self.canvas.mirror_selected(chosen)
            )
        mirror_button.setMenu(mirror_menu)

        construction_button = QToolButton(self)
        construction_button.setText(f"{tr('Hilfsgeometrie')}  {ACTION_KEYS['construction']}")
        construction_button.setToolTip(
            tr("Trägt Bedingungen, bildet aber kein Profil. Nochmal drücken macht es rückgängig.")
        )
        construction_button.setAutoRaise(True)
        construction_button.clicked.connect(self.canvas.toggle_construction)

        project_button = QToolButton(self)
        project_button.setText(tr("Projizieren"))
        project_button.setToolTip(
            tr("Die Kanten der vorhandenen Körper auf dieser Ebene in die Skizze holen.")
        )
        project_button.setAutoRaise(True)
        project_button.clicked.connect(self.canvas.project_bodies)

        tools.addWidget(offset_button)
        tools.addWidget(self.offset_distance)
        tools.addWidget(mirror_button)
        tools.addWidget(construction_button)
        tools.addWidget(project_button)

        undo_button = QToolButton(self)
        undo_button.setText(tr("Rückgängig"))
        undo_button.setAutoRaise(True)
        undo_button.clicked.connect(self.canvas.undo)
        tools.addWidget(undo_button)

        constraints_row = QHBoxLayout()
        self._constraint_buttons: dict[SketchConstraintKind, QPushButton] = {}
        for kind in _NEEDS:
            key = ACTION_KEYS.get(kind, "")
            label = _constraint_label(kind)
            constraint_button = QPushButton(f"{label}  {key}" if key else label, self)
            constraint_button.setToolTip(label)
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

        side = QVBoxLayout()
        side.addWidget(QLabel(tr("Bedingungen"), self))
        side.addWidget(self.constraint_list, stretch=1)

        middle = QHBoxLayout()
        middle.addWidget(self.canvas, stretch=1)
        middle.addLayout(side)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(tools)
        layout.addLayout(plane_row)
        layout.addLayout(constraints_row)
        layout.addLayout(middle, stretch=1)
        layout.addWidget(self.status)

        self.canvas.sketchChanged.connect(self.sketchChanged)
        self.canvas.sketchChanged.connect(self._refresh_constraints)
        self.canvas.selectionChanged.connect(self._refresh_buttons)
        self.canvas.statusChanged.connect(self.status.setText)
        self.constraint_list.installEventFilter(self)
        self._install_shortcuts()
        self._refresh_constraints()
        self._refresh_buttons()

    def _install_shortcuts(self) -> None:
        """Die Zeichenkürzel, solange dieses Panel den Fokus hat (E16).

        ``WidgetWithChildrenShortcut`` ist der Kontext, der aus einer Belegung
        eine **kontextabhängige** macht: außerhalb des Skizzenmodus liegen R
        und C auf Drehen und Fasen, hier auf Rechteck und Kreis. Genau so macht
        es Fusion, und anders lassen sich die beiden Sätze nicht
        widerspruchsfrei halten.
        """
        for name, key in TOOL_KEYS.items():
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(lambda chosen=name: self.choose_tool(chosen))

        rectangle = QShortcut(QKeySequence(ACTION_KEYS["rectangle"]), self)
        rectangle.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        rectangle.activated.connect(lambda: self.canvas.insert_shape(shapes.rectangle(40.0, 20.0)))

        measure = QShortcut(QKeySequence(ACTION_KEYS["distance"]), self)
        measure.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        measure.activated.connect(lambda: self.request_constraint("distance"))

        versetzen = QShortcut(QKeySequence(ACTION_KEYS["offset"]), self)
        versetzen.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        versetzen.activated.connect(
            lambda: self.canvas.offset_selected(self.offset_distance.value())
        )

        helper = QShortcut(QKeySequence(ACTION_KEYS["construction"]), self)
        helper.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        helper.activated.connect(self.canvas.toggle_construction)

    def choose_tool(self, name: str) -> None:
        """Wählt ein Werkzeug — was ein Klick auf seinen Knopf tut.

        Über den Knopf und nicht über die Zeichenfläche: sonst stünde die
        Leiste auf „Auswählen", während gezeichnet wird.
        """
        button = self._tool_buttons.get(name)
        if button is not None:
            button.setChecked(True)

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
            shown = measure_label(entry, self.canvas.points())
            if shown:
                label = f"{label} {shown}"
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

    def set_bed(self, size: tuple[float, float] | None) -> None:
        """Den Bauraum an die Zeichenfläche weiterreichen (E1)."""
        self.canvas.set_bed(size)

    def offer_bodies(self, meshes: Sequence[Any]) -> None:
        """Woraus projiziert werden kann — weitergereicht an die
        Zeichenfläche."""
        self.canvas.offer_bodies(meshes)

    def offer_faces(self, faces: Sequence[tuple[str, str, tuple[float, float, float]]]) -> None:
        """Die planaren Flächen der Szene als weitere Ebenen anbieten (§30.1).

        ID, Beschriftung, Normale — in dieser Reihenfolge. Die drei
        Grundebenen bleiben stehen und vorn: sie gelten immer, die Flächen nur
        solange der Körper sie hat.

        Ein Auswahlfeld und kein zweites Bedienelement daneben. Eine Fläche ist
        eine Ebene wie XY auch, und wer sie in einen eigenen Knopf auslagert,
        behauptet einen Unterschied, den es beim Zeichnen nicht gibt (E11).
        """
        while self.plane_choice.count() > self._plane_count:
            self.plane_choice.removeItem(self.plane_choice.count() - 1)
        for feature_id, label, _normal in faces:
            self.plane_choice.addItem(label, userData=f"feature:{feature_id}")
        self.canvas.offer_faces({feature_id: normal for feature_id, _label, normal in faces})
        # Die Wahl kann durch das Entfernen weggefallen sein — dann steht sie
        # jetzt auf XY, und der Hinweis darunter muss das mitbekommen.
        chosen = self.plane_choice.findData(self.canvas.sketch.plane)
        self.plane_choice.setCurrentIndex(max(0, chosen))
        self.layer_note.setText(self.canvas.layer_note())

    def sketch_text(self) -> str:
        """Der Parameterwert, wie ihn die Skizzen-Ops lesen (§30.1) — leer,
        wenn nichts gezeichnet wurde."""
        if not self.canvas.sketch.elements:
            return ""
        return sketch_to_text(self.canvas.sketch)


class SketchEditorDialog(QDialog):
    """Das Panel in einem Fenster, für den Weg über das Operationsfeld.

    Der Skizzenmodus im Hauptfenster nimmt dasselbe Panel ohne diesen Rahmen
    (§30.1 Stufe zwei). Beide Wege bleiben, weil beide gebraucht werden: wer
    eine Operation im Verlauf wieder öffnet, ist schon in einem Dialog, und ihn
    dafür in einen Modus zu schicken wäre ein Umweg.
    """

    def __init__(
        self,
        text: str = "",
        parameter_values: Mapping[str, float] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Skizze zeichnen"))
        self.resize(860, 560)

        self.panel = SketchPanel(text, parameter_values, self)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok is not None:
            ok.setText(tr("Übernehmen"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addWidget(self.panel, stretch=1)
        layout.addWidget(buttons)

        # Undo gilt überall, auch hier (§19.2) — derselbe Griff wie im Fenster.
        QShortcut(QKeySequence.StandardKey.Undo, self, self.panel.canvas.undo)

    @property
    def canvas(self) -> SketchCanvas:
        """Die Zeichenfläche des Panels. Die Tests greifen darauf zu."""
        return self.panel.canvas

    @property
    def status(self) -> QLabel:
        """Die Statuszeile des Panels — Freiheitsgrade und Konflikte."""
        return self.panel.status

    def constraint_offers(self) -> dict[SketchConstraintKind, bool]:
        return self.panel.constraint_offers()

    def request_constraint(self, kind: SketchConstraintKind) -> None:
        self.panel.request_constraint(kind)

    def sketch_text(self) -> str:
        return self.panel.sketch_text()


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
