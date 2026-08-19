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
from dataclasses import dataclass, replace
from typing import Any

from PySide6.QtCore import QPoint, QPointF, Qt, Signal
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPainterPath, QPen, QShortcut
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
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
from app.ui import cursors, icons
from app.ui.labels import length
from app.ui.palette import ROLES, text_colour

#: Was eine widersprüchliche Bedingung in der Liste anschreibt.
#:
#: Ein Zeichen und nicht nur die Farbe (Regel 18): Die Liste wird auch
#: ausgedruckt, und wer Rot nicht von Grau unterscheidet, sähe sonst
#: vierzehn gleiche Zeilen.
CONFLICT_MARKER = "!"

#: Fangradius in Pixeln: näher als das an einem Punkt heißt „dieser Punkt".
SNAP_PX = 8.0

#: Trefferabstand für Linien und Ränder, in Pixeln.
PICK_PX = 5.0

#: Halbe Armlänge des Fangkreuzes am Zeiger, in Pixeln. Kleiner als der
#: Fangradius: es zeigt einen Ort, es greift nicht.
SNAP_MARK_PX = 5.0

#: Der Maßstab in Pixeln je Millimeter, solange nichts einzupassen ist.
START_SCALE = 4.0

#: Wie weit sich der Maßstab drehen lässt. Die Grenzen gelten für das Mausrad
#: und fürs Einpassen: eine Ansicht, aus der kein Zoomschritt herausführt, wäre
#: eine Sackgasse mit Zahlen.
MIN_SCALE = 0.5
MAX_SCALE = 100.0

#: Luft zwischen dem Eingepassten und dem Rand der Fläche, in Pixeln. Ohne sie
#: klebt der äußerste Punkt am Rahmen, und der Bauraumrand liegt genau darauf.
#:
#: Bemessen nicht an der Geometrie, sondern an ihrer Beschriftung: die Maßzahlen
#: stehen **außerhalb** der Kontur, die eingepasst wird. Bei vierundzwanzig
#: Punkten stand im Handbuchbild „60,0(" am rechten Rand — die Zahl war da, das
#: Bild hörte vorher auf.
FIT_MARGIN_PX = 48.0

#: Worauf sich das Einpassen mindestens bezieht, in Millimetern. Ein einzelner
#: Punkt und eine waagerechte Linie haben in einer Richtung keine Ausdehnung —
#: ohne Untergrenze wäre der Maßstab dort unendlich.
MIN_FIT_MM = 20.0

#: Eine leere Skizze beginnt auf der XY-Ebene — die Ops setzen sie über
#: ihren Flächenparameter dorthin, wo sie hingehört (§30.1).
EMPTY = Sketch(plane="plane:xy", elements=())

#: Auf welche Schrittweite ein Klick fällt, solange der Fang an ist, in
#: Millimetern.
#:
#: Ein Millimeter, und nicht das gezeichnete Zehnerraster: gedruckt wird in
#: Millimetern, Wandstärken und Bohrungsabstände sind ganze oder halbe, und
#: ein Klick landete vorher auf -29,75 mm. Wer feiner braucht, stellt die
#: Weite um; wer gar nicht fangen will, nimmt den Haken weg.
DEFAULT_SNAP_MM = 1.0

#: Wie eng die Rasterlinien im Bild höchstens stehen, in Bildpunkten. Darunter
#: wird die nächstgröbere Stufe genommen — ein Raster, dessen Linien sich
#: berühren, ist eine Fläche.
MIN_GRID_PX = 7.0

#: Die Stufen, aus denen die Rasterweite gewählt wird. Millimeterschritte in
#: der Folge 1, 2, 5, wie an jedem Maßband: dazwischen gibt es keine Weite, die
#: sich ablesen ließe.
GRID_STEPS: tuple[float, ...] = (0.1, 0.2, 0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0)

#: Wie die beiden Achsen der Zeichenfläche in jeder Ebene heißen (§30.1).
#:
#: Die Zeichenfläche bleibt eine Fläche; was ihre Waagerechte im Raum bedeutet,
#: hängt an der Ebene. Beschriftet stand dort immer „X" und „Y" — auf der
#: stehenden Ebene ist die Senkrechte aber Z, und wer danach maß, maß in der
#: falschen Richtung.
PLANE_AXES: dict[str, tuple[str, str]] = {
    "plane:xy": ("X", "Y"),
    "plane:xz": ("X", "Z"),
    "plane:yz": ("Y", "Z"),
}

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


def free_dof_phrase(free: int) -> str:
    """Wie viele Freiheitsgrade offen sind, als Halbsatz hinter einem Trenner.

    Mit Singular, weil es ihn gibt: „1 Freiheitsgrade frei" stand in der
    Statuszeile und wäre mit dem ersten Handbuchbild des Skizzenmodus
    gedruckt worden.
    """
    if free == 1:
        return tr("ein Freiheitsgrad frei")
    return tr("{count} Freiheitsgrade frei").format(count=free)


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


def measured_expression(points: Sequence[tuple[float, float]], targets: tuple[int, ...]) -> str:
    """Der Abstand zweier Punkte, wie er im Maßfeld vorstehen soll.

    Das Feld stand leer. Wer zwei Punkte gewählt hatte und ein Maß setzen
    wollte, musste die Zahl kennen, die er gerade selbst gezeichnet hatte —
    und wenn er sie falsch riet, sprang die Zeichnung. Vorbelegt ist das Feld
    eine Ansage: hier stehen 30,25, trag 30 ein, und der Solver zieht es
    dorthin.

    Mit Punkt und ohne Einheit, denn es ist ein Ausdruck der
    Parametergrammatik (§13) und keine Beschriftung. Die abschließenden
    Nullen fallen weg — „30" ist die Aussage, „30,00" nur ihre Formatierung.
    """
    if len(targets) < 2 or max(targets[0], targets[1]) >= len(points):
        return ""
    ax, ay = points[targets[0]]
    bx, by = points[targets[1]]
    text = f"{math.hypot(bx - ax, by - ay):.2f}".rstrip("0").rstrip(".")
    return text or "0"


def _on_multiple(value: float, spacing: float, tolerance: float) -> bool:
    """Ob ein Rasterwert auf einem Vielfachen der Beschriftungsweite liegt.

    Nicht über ``value % spacing == 0``: die Werte entstehen durch
    schrittweises Addieren, und der Rest liegt dann mal knapp über null und
    mal knapp unter der Weite. Gemessen wird der Abstand zum nächsten
    Vielfachen in beide Richtungen — Regel 6, kein Fließkommavergleich.
    """
    if spacing <= 0.0:
        return False
    rest = value % spacing
    return min(rest, spacing - rest) < tolerance / 2.0


def _decimals_for(step: float) -> int:
    """Wie viele Nachkommastellen eine Rasterzahl braucht.

    Bei einer Weite von zehn Millimetern stand ``f"{x:.0f}"`` richtig; bei
    einer halben stünde dort dreimal dieselbe Null.
    """
    if step >= 1.0:
        return 0
    return 1 if step >= 0.1 else 2


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
    measuringChanged = Signal(float)
    """Das Maß des angefangenen Elements, oder 0 — das Feld in der Leiste
    folgt ihm, solange gezeichnet wird (E19)."""

    pointerChanged = Signal(float, float)
    """Wohin ein Klick gerade fiele, in Millimetern.

    Jede Zeichenfläche eines CAD sagt, wo der Zeiger steht; diese sagte es
    nicht. Wer einen Punkt auf 30 mm ziehen wollte, zog ihn ins Ungefähre und
    maß hinterher nach."""

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
        self._scale = START_SCALE
        self._centre = QPointF(0.0, 0.0)
        self._fitting = False
        """Ob die Ansicht der Einpassung folgt, statt dem eigenen Maßstab.

        Bleibt gesetzt, bis jemand selbst zoomt oder schiebt — dann gehört die
        Ansicht ihm. *Einpassen* schaltet es wieder ein.

        Nicht bloß ein „einmal beim Öffnen": das Layout verteilt in mehreren
        Durchgängen, und der erste bringt oft noch die Mindestgröße. Beim
        leeren Blatt stand der Maßstab danach auf der Größe von vorher, und der
        Bauraumrand — der Grund für das Ganze — lag zur Hälfte daneben."""
        self._panning: QPoint | None = None
        self._face_normals: dict[str, tuple[float, float, float]] = {}
        """Die Normalen der Flächen, auf denen gezeichnet werden darf.

        Nur für den Hinweis zur Schichtrichtung — siehe ``offer_faces``."""
        self._pointer: tuple[float, float] = (0.0, 0.0)
        """Wo der Zeiger zuletzt stand, in Weltkoordinaten."""
        self.highlighted: frozenset[int] = frozenset()
        """Punkte, die gerade aufleuchten sollen — die Ziele der Bedingung
        unter dem Mauszeiger (E19).

        „Deckung (1, 2)" ist ohne das nicht lesbar: welche zwei Punkte das
        sind, weiß nur, wer die flache Nummerierung im Kopf hat."""
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
        self.snapping = True
        """Ob ein Klick auf die Rasterweite fällt.

        An als Vorgabe: ein Klick landete sonst auf -29,75 mm, und aus so
        einem Wert wird kein Maß, sondern eine Bedingung, die man nachträgt.
        Der Haken in der Leiste nimmt ihn weg, wenn jemand frei zeichnen
        will."""
        self.snap_step = DEFAULT_SNAP_MM
        """Auf welche Weite gefangen wird, in Millimetern."""
        self._snap_mark: tuple[float, float] | None = None
        """Der Rasterpunkt unter dem Zeiger, solange ein Werkzeug gewählt
        ist — gemerkt, damit nicht jede Mausbewegung neu zeichnet."""

    def set_bed(self, size: tuple[float, float] | None) -> None:
        """Die Grundfläche des Bauraums, gegen die gezeichnet wird.

        Ein leeres Blatt passt auf den Bauraum ein — kommt der erst nach dem
        Aufbau herein, muss die Einpassung nachziehen. Sonst stand der
        Maßstab auf der Vorgabe, und der Rand, der die früheste Warnung
        tragen soll (E1), lag zur Hälfte außerhalb. Nur solange die Ansicht
        der Einpassung überhaupt folgt: wer selbst gezoomt hat, behält seinen
        Ausschnitt.
        """
        self._bed = size
        if self._fitting:
            self.fit_view(keep_following=True)
        self.update()

    def set_snapping(self, active: bool, step: float | None = None) -> None:
        """Den Rasterfang ein- oder ausschalten, wahlweise mit neuer Weite."""
        self.snapping = active
        if step is not None and step > 0.0:
            self.snap_step = step
        self.update()

    def snapped(self, world: tuple[float, float]) -> tuple[float, float]:
        """Ein Punkt auf der Rasterweite — oder unverändert, wenn der Fang
        aus ist.

        Gerundet, nicht abgeschnitten: abgeschnitten läge jeder Punkt links
        unter dem Zeiger, und bei einer Weite von zehn Millimetern wäre das
        ein sichtbarer Versatz in eine Richtung.
        """
        if not self.snapping or self.snap_step <= 0.0:
            return world
        step = self.snap_step
        return (round(world[0] / step) * step, round(world[1] / step) * step)

    def pointer_target(self) -> tuple[float, float]:
        """Wo ein Klick landen würde — der Wert, den die Anzeige nennt.

        Nicht die rohe Zeigerlage: solange der Fang gilt, fällt der Klick auf
        die Rasterweite, und eine Anzeige, die 29,75 zeigt, wo 30 entsteht,
        wäre schlechter als keine. Beim Ziehen gilt derselbe Fang, also
        dieselbe Zahl.

        Liegt ein Punkt unter dem Zeiger, gilt **seine** Lage: dort greift der
        Klick, und der Punkt sitzt nicht zwangsläufig auf dem Raster. Bei
        20,25 mm und einem Millimeter Weite stand sonst 20,00 in der Zeile,
        während der Klick den Punkt bei 20,25 nahm — derselbe Fehler, nur
        andersherum.
        """
        if self._dragging is None and self.tool in ("select", "point"):
            hit = self._hit_point(self._to_screen(*self._pointer))
            if hit is not None:
                return self.points()[hit]
        if self.tool == "select" and self._dragging is None:
            return self._pointer
        return self.snapped(self._pointer)

    def axis_names(self) -> tuple[str, str]:
        """Wie die waagerechte und die senkrechte Achse hier heißen (§30.1).

        Auf einer angeklickten Fläche des Körpers stehen sie ohne Namen: die
        Fläche kann beliebig geneigt sein, und „X" auf einer schrägen Wand
        wäre eine Angabe, die nicht stimmt.
        """
        return PLANE_AXES.get(self.sketch.plane, ("", ""))

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

    def highlight_points(self, points: frozenset[int]) -> None:
        """Lässt die genannten Punkte aufleuchten — oder keinen mehr."""
        if points == self.highlighted:
            return
        self.highlighted = points
        self.update()

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

    def resizeEvent(self, event: Any) -> None:  # noqa: N802 - Qt gibt den Namen
        """Solange die Ansicht der Einpassung folgt, folgt sie auch der Größe."""
        super().resizeEvent(event)
        if self._fitting:
            self.fit_view(keep_following=True)

    def fit_view(self, *, keep_following: bool = True) -> None:
        """Maßstab und Mitte so setzen, dass alles Wesentliche im Bild liegt.

        Der Maßstab stand fest auf :data:`START_SCALE` und blieb dort: eine
        geöffnete Skizze von 300 mm lag zur Hälfte außerhalb, und der
        Bauraumrahmen — der die früheste Warnung tragen soll (E1) — war beim
        Öffnen überhaupt nicht zu sehen. Eine gute Vorgabe statt eines Knopfes,
        den man erst finden muss; den Knopf gibt es trotzdem, weil man sich
        verzoomt.

        **Was eingepasst wird, hängt davon ab, was da ist.** Eine vorhandene
        Zeichnung gibt das Maß: an ihr wird gearbeitet, und ragt sie über die
        Platte, kommt der Rahmen von selbst mit ins Bild. Ein leeres Blatt
        zeigt den Bauraum — dann sieht man, wohin man zeichnet, bevor der erste
        Strich sitzt. Ohne beides bleibt es beim Startmaßstab.

        ``keep_following`` lässt die Ansicht an der Einpassung hängen: sie geht
        bei jeder Größenänderung mit, bis jemand selbst zoomt oder schiebt.
        """
        if keep_following:
            self._fitting = True
        points = self.points()
        if points:
            xs = [x for x, _y in points]
            ys = [y for _x, y in points]
            span_x, span_y = max(xs) - min(xs), max(ys) - min(ys)
            centre = ((max(xs) + min(xs)) / 2.0, (max(ys) + min(ys)) / 2.0)
        elif self._bed is not None:
            span_x, span_y = self._bed
            centre = (0.0, 0.0)
        else:
            return

        span_x = max(span_x, MIN_FIT_MM)
        span_y = max(span_y, MIN_FIT_MM)
        room_x = max(self.width() - 2 * FIT_MARGIN_PX, FIT_MARGIN_PX)
        room_y = max(self.height() - 2 * FIT_MARGIN_PX, FIT_MARGIN_PX)
        self._scale = min(
            max(min(room_x / span_x, room_y / span_y), MIN_SCALE),
            MAX_SCALE,
        )
        self._centre = QPointF(*centre)
        self.update()

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
        # Der Zeiger sagt, was ein Klick tut. Er stand auf dem Pfeil, gleich
        # ob ein Zeichenwerkzeug lief oder nicht — und ein Werkzeug, dessen
        # Zustand man nur am gedrückten Knopf sieht, ist bei achtunddreißig
        # Bildpunkten Symbolgröße kein Zustand, den jemand bemerkt.
        self.setCursor(cursors.cursor("select" if tool == "select" else "draw", self))
        # Was das gewählte Werkzeug erwartet, steht sofort da und nicht erst
        # nach dem ersten Klick.
        self.statusChanged.emit(self.status_text())
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
        self.conflict_pair: tuple[int, int] | None = None
        """Welche zwei Bedingungen sich widersprechen — für die Liste rechts.

        Der Kern nennt sie seit jeher (``error.first``/``error.second``) und
        bietet sogar an, die eine oder die andere zu entfernen. Nur stand im
        Text nichts davon: „Zwei Bedingungen widersprechen sich." bei
        vierzehn Einträgen in der Liste lässt suchen, welche zwei."""
        if not self.sketch.elements:
            self.solved = None
        else:
            try:
                self.solved = solve_sketch(self.sketch, self._params)
            except SketchConflictError as error:
                self.conflict = str(error.detail or error.title)
                self.conflict_pair = (error.first, error.second)
            except AppError as error:
                self.conflict = str(error.detail or error.title)
        self.sketchChanged.emit()
        self.statusChanged.emit(self.status_text())
        self.update()

    def status_text(self) -> str:
        if self.conflict:
            return self.conflict
        # Ein angefangenes Element geht vor: was der nächste Klick tut, ist
        # dringender als was vorhin ausgewählt wurde. Ohne Angefangenes gewinnt
        # die Auswahl — sonst stünde beim Punktwerkzeug weiter „jeder Klick
        # setzt einen", während der eben gegriffene Punkt dick im Bild liegt.
        drawing = self.drawing_hint()
        if drawing and self._pending_world:
            return drawing
        chosen = self.selection_hint()
        if chosen:
            return chosen
        if drawing:
            return drawing
        if self.solved is None:
            return tr("Leere Skizze — zeichnen oder eine Grundform einfügen.")
        if self.solved.free_dof == 0:
            return tr("Bestimmt — alle Freiheitsgrade sind vergeben.")
        if self.solved.free_dof == 1:
            return tr("Ein Freiheitsgrad ist noch frei.")
        return tr("{count} Freiheitsgrade sind noch frei.").format(count=self.solved.free_dof)

    def selection_hint(self) -> str:
        """Was ausgewählt ist — und wie das Zweite dazukommt.

        Dass Strg mehrere wählt, stand nirgends. Ein Maß zwischen zwei Punkten
        braucht beide ausgewählt; wer den zweiten anklickt, verliert den
        ersten, der Knopf bleibt grau, und der Grund ist eine Taste, die
        niemand genannt hat. Die Zeile sagt sie genau dann, wenn sie gebraucht
        wird: wenn eines dasteht und ein zweites fehlt.

        Leer heißt: nichts ausgewählt — dann gehört die Zeile den
        Freiheitsgraden.
        """
        # Die beiden Werkzeuge, mit denen sich ein Punkt greifen lässt. Beim
        # Zeichnen einer Linie gehört die Zeile dem nächsten Klick, auch wenn
        # von vorhin noch etwas ausgewählt ist.
        if self.tool not in ("select", "point") or not self.selection:
            return ""
        if len(self.selection) == 1:
            return tr("Eines ausgewählt — mit Strg das Nächste dazunehmen.")
        return tr("{count} ausgewählt.").format(count=len(self.selection))

    def drawing_hint(self) -> str:
        """Was der nächste Klick tut, und wie man wieder herauskommt.

        Der Linienzug ist der Fall, an dem es fehlte: nach dem zweiten Klick
        hängt der nächste Strich am Zeiger und läuft weiter, und dass Esc ihn
        beendet, stand nirgends. Ein Werkzeug, das man nur durch Ausprobieren
        verlässt, ist eine Sackgasse mit Ausgang (§2.1).

        Leer heißt: nichts zu sagen — mit dem Auswahlwerkzeug zeichnet
        niemand, und dann gehört die Zeile den Freiheitsgraden.
        """
        if self.tool == "select":
            return ""
        started = len(self._pending_world)
        if self.tool == "spline":
            if started:
                return tr("Spline: weiter klicken. Doppelklick oder Eingabetaste schließt ihn.")
            return tr("Spline: klicken, so oft es die Kurve braucht.")
        if self.tool in ("trim", "extend"):
            return tr("Auf die Hälfte klicken, die es betrifft.")
        if self.tool == "point":
            # Beide Hälften in einem Satz: das Werkzeug bleibt nach dem Klick
            # stehen, und wer einen vorhandenen Punkt greifen will, muss nicht
            # erst herausfinden, wie er herauskommt — er klickt ihn an.
            return tr("Punkt: jeder Klick setzt einen, ein Klick auf einen vorhandenen greift ihn.")
        if self.tool == "line":
            if started:
                return tr("Linie: Klick setzt den nächsten Punkt, Esc beendet den Zug.")
            return tr("Linie: erster Klick setzt den Anfang.")
        if self.tool == "circle":
            if started:
                return tr("Kreis: der nächste Klick setzt den Radius. Oder das Maß eintippen.")
            return tr("Kreis: erster Klick setzt die Mitte.")
        if self.tool == "arc":
            if started >= 2:
                return tr("Bogen: der nächste Klick setzt das Ende.")
            if started:
                return tr("Bogen: der nächste Klick setzt den Anfang.")
            return tr("Bogen: erster Klick setzt die Mitte.")
        return ""

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
        self.statusChanged.emit(self.status_text())
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

    def _on_last_pending(self, position: QPointF) -> bool:
        """Ob der Klick auf dem zuletzt gesetzten, noch offenen Punkt liegt.

        Nicht über ``_hit_point``: die angefangenen Punkte stehen noch nicht in
        der Skizze, und gefangen wird nur, was darin steht. Gemessen wird in
        Bildschirmpunkten und mit derselben Toleranz wie der Fang — bei einem
        weit herausgezoomten Blatt wäre ein Weltabstand etwas anderes.
        """
        if not self._pending_world:
            return False
        screen = self._to_screen(*self._pending_world[-1])
        return math.hypot(screen.x() - position.x(), screen.y() - position.y()) <= SNAP_PX

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
            # Wie beim Zoomen: wer schiebt, will seinen Ausschnitt behalten.
            self._fitting = False
            self._panning = event.position().toPoint()
            return
        if event.button() == Qt.MouseButton.RightButton:
            self._context_menu(event)
            return
        if event.button() != Qt.MouseButton.LeftButton:
            return

        if self.tool == "select":
            # Ein Klick auf einen vorhandenen Punkt greift ihn. Für das
            # Punktwerkzeug steht dieselbe Regel in ``place`` und nur dort —
            # zweimal geschrieben würde sie beim nächsten Nachziehen einmal
            # vergessen, und der Mausweg wiche vom geprüften ab.
            hit = self._hit_point(position)
            if hit is not None:
                self.grab_point(
                    hit, extend=bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier)
                )
                return
            element = self._hit_element(position)
            if element is not None:
                self._select(element, bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier))
                return
            if not event.modifiers():
                self.selection.clear()
                self.selectionChanged.emit()
                self.statusChanged.emit(self.status_text())
                self.update()
            return

        if self.tool in ("trim", "extend"):
            self.cut_or_grow(position)
            return

        self.place(position, extend=bool(event.modifiers() & Qt.KeyboardModifier.ControlModifier))

    def grab_point(self, flat: int, *, extend: bool = False) -> None:
        """Einen vorhandenen Punkt auswählen und zum Ziehen bereitmachen.

        Derselbe Griff, gleich welches der beiden Werkzeuge gerade läuft: wer
        auf einen Punkt klickt, meint diesen Punkt. Mit dem Punktwerkzeug
        entstand dort vorher ein zweiter genau darauf — deckungsgleich und
        unsichtbar —, und um den ersten zu bewegen, musste man erst das
        Werkzeug wechseln.

        Der Undo-Stand wird hier gemerkt, weil das Ziehen gleich beginnen
        kann: ``mouseMoveEvent`` schiebt den Punkt, sobald die Taste unten
        bleibt, und ohne den Merker nähme ein Rückgängig den Schritt davor.

        Am Zeiger hängt er nur, wenn er danach auch ausgewählt ist: ein
        Strg-Klick auf einen bereits gewählten Punkt wählt ihn ab, und einen
        abgewählten Punkt zu verschieben wäre das Gegenteil dessen, was die
        Geste sagt.
        """
        self._select(("point", (flat,)), extend)
        self._remember()
        self._dragging = flat if ("point", (flat,)) in self.selection else None

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

    def place(self, position: QPointF, *, extend: bool = False) -> None:
        """Ein Klick eines Zeichenwerkzeugs: Punkt setzen, Element schließen.

        Ein Klick nahe eines vorhandenen Punkts fängt — das neue Element
        bekommt dann eine Deckungs-Bedingung statt einer Kopie der Zahl.
        Element und Deckungen kommen als **ein** Schritt an, damit ein
        Rückgängig den ganzen Klickzug nimmt, nicht seine Hälften.

        ``extend`` ist die Strg-Taste des Klicks, und sie zählt nur für den
        Griff unten: Ein Maß zwischen zwei Punkten braucht beide ausgewählt,
        und wer den zweiten ohne Strg anklickt, verliert den ersten. Das
        Mausereignis reicht sie herein, statt selbst zu greifen — sonst gäbe es
        zwei Wege zu derselben Geste, und geprüft wäre der, den die Maus nicht
        nimmt.
        """
        # Ein vorhandener Punkt schlägt das Raster: er wird zur Deckung, und
        # eine Deckung hält auch dann, wenn der Punkt später wandert. Erst wo
        # keiner liegt, fällt der Klick auf die Rasterweite.
        snapped = self._hit_point(position)
        world = (
            self.points()[snapped]
            if snapped is not None
            else self.snapped(self._to_world(position))
        )

        # Ein Klick auf einen Punkt greift ihn, statt einen zweiten daraufzu-
        # setzen. Der bekam vorher einen vierten genau auf den mittleren —
        # deckungsgleich, unsichtbar —, und um den ersten zu bewegen, musste
        # man erst das Werkzeug wechseln. Dieselbe Regel wie beim Auswählen,
        # und deshalb steht sie auch hier und nicht nur im Mausereignis: was
        # ein Klick tut, entscheidet die Methode, die auch ein Test ruft.
        #
        # Bei Linie, Kreis und Bogen bleibt der Fang, wie er ist: dort wird der
        # vorhandene Punkt zum Anfang des neuen Elements, und die Deckung ist
        # die Verbindung, für die der Fang da ist.
        if self.tool == "point" and snapped is not None:
            self.grab_point(snapped, extend=extend)
            return

        # Ein Spline endet nicht bei einer Punktzahl, sondern wenn jemand sagt,
        # dass er fertig ist: Doppelklick, Eingabetaste oder ein zweiter Klick
        # auf denselben Punkt. Bis dahin sammelt er.
        #
        # Der dritte Weg stand hier lange als Versprechen und war keiner: der
        # Klick hängte einen weiteren, deckungsgleichen Punkt an die Kurve —
        # still, ohne Ton, und wer den Griff aus einem CAD mitbringt, holte
        # sich damit einen doppelten Punkt.
        if self.tool == "spline" and self._on_last_pending(position):
            self.finish_spline()
            return

        self._pending.append(snapped if snapped is not None else -1)
        self._pending_world.append(world)

        if self.tool == "spline":
            self.statusChanged.emit(self.status_text())
            self.update()
            return

        needed = {"point": 1, "line": 2, "circle": 2, "arc": 3}[self.tool]
        if len(self._pending_world) < needed:
            # Der Hinweis wandert mit dem angefangenen Element: was der
            # nächste Klick tut, ist nach dem ersten eine andere Auskunft als
            # davor.
            self.statusChanged.emit(self.status_text())
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

    def pending_measure(self) -> float:
        """Wie lang die angefangene Linie gerade wäre — oder wie groß der
        Kreis.

        Null heißt: es ist nichts angefangen, für das ein Maß gilt. Die
        Leiste schaltet ihr Feld danach.
        """
        if len(self._pending_world) != 1 or self.tool not in ("line", "circle"):
            return 0.0
        first = self._pending_world[0]
        return math.hypot(self._pointer[0] - first[0], self._pointer[1] - first[1])

    def place_measured(self, value: float) -> None:
        """Schließt das angefangene Element auf ein eingetipptes Maß ab (E19).

        In Fusion zeichnet man selten und bemaßt fast immer — das Maß beim
        Zeichnen einzutippen ist dort der Normalweg, und Solidon hatte
        dafür gar nichts.

        Die Richtung kommt vom Zeiger, die Länge aus dem Feld. Und das Maß
        bleibt als Bedingung stehen, nicht nur als Koordinate: sonst wandert
        die Linie beim nächsten Solverlauf, und die eingetippte Zahl wäre eine
        Angabe gewesen, die nichts hält.
        """
        if value <= 0.0 or len(self._pending_world) != 1 or self.tool not in ("line", "circle"):
            self.statusChanged.emit(tr("Erst einen Punkt setzen, dann das Maß eintippen."))
            return

        first = self._pending_world[0]
        dx, dy = self._pointer[0] - first[0], self._pointer[1] - first[1]
        span = math.hypot(dx, dy)
        # Ohne Richtung nach rechts: eine Länge ohne Richtung ist keine Linie,
        # und die Waagerechte ist die Antwort, die niemanden überrascht.
        direction = (dx / span, dy / span) if span > EPS_DISPLAY else (1.0, 0.0)
        second = (first[0] + direction[0] * value, first[1] + direction[1] * value)

        begin = len(_flat_points(self.sketch))
        element = SketchElement(self.tool, (first, second))  # type: ignore[arg-type]
        snapped = tuple(
            SketchConstraint("coincident", (flat, begin + local))
            for local, flat in enumerate(self._pending)
            if flat >= 0
        )
        measured = SketchConstraint("distance", (begin, begin + 1), value=f"{value:.9f}")
        self._pending.clear()
        self._pending_world.clear()
        self._apply(
            replace(
                self.sketch,
                elements=(*self.sketch.elements, element),
                constraints=(*self.sketch.constraints, *snapped, measured),
            )
        )
        self.measuringChanged.emit(0.0)

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
        position = QPointF(event.position())
        # Wo der Zeiger steht, entscheidet die **Richtung** eines eingetippten
        # Maßes: die Länge kommt aus dem Feld, wohin es geht aus der Hand.
        self._pointer = self._to_world(position)
        self.pointerChanged.emit(*self.pointer_target())
        # Was ein Klick greifen würde — einmal gesucht und an beide gegeben:
        # das Aufleuchten braucht den Punkt, die Fangmarke braucht nur zu
        # wissen, dass es einen gibt. Zweimal zu suchen hieße, bei jeder
        # Mausbewegung zweimal über alle Punkte zu laufen.
        under = self._hit_point(position) if self.tool in ("select", "point") else None
        # Getrennt ausgewertet und nicht mit ``or`` verkettet: eine
        # Kurzschluss-Oder ließe das Zweite ungeprüft, sobald das Erste
        # zutrifft.
        hovered = self._note_hover(under)
        # Die Fangmarke wandert immer mit, auch schon vor dem ersten Klick:
        # das Raster wird gröber gezeichnet, als gefangen wird, und ohne die
        # Marke wäre nicht zu sehen, wohin ein Klick fiele.
        moved = self._note_snap_mark(over_point=under is not None)
        if self._dragging is not None and event.buttons() & Qt.MouseButton.LeftButton:
            # Ein gezogener Punkt fällt auf dieselbe Weite wie ein gesetzter —
            # sonst wäre das Raster eine Zusage, die beim ersten Nachbessern
            # nicht mehr gilt.
            target = self.snapped(self._pointer)
            self.move_point(self._dragging, target[0], target[1])
        elif self._pending_world:
            self.measuringChanged.emit(self.pending_measure())
            self.update()
        elif moved or hovered:
            self.update()

    def _note_hover(self, under: int | None) -> bool:
        """Merkt den Punkt unter dem Zeiger und sagt, ob er gewechselt hat.

        Ohne das ist nicht zu sehen, ob ein Klick den Punkt trifft oder
        danebengeht — man klickt, sieht keinen Unterschied und klickt wieder.
        Der Fangradius ist acht Bildpunkte; wo er greift, gehört ein Zeichen
        hin.

        Wer der Treffer ist, entscheidet der Anrufer: gesucht wird einmal je
        Mausbewegung, und die Fangmarke braucht dasselbe Ergebnis. Bei einem
        Werkzeug, das nicht greift, kommt ``None`` — beim Zeichnen einer Linie
        leuchtet stattdessen die Fangmarke, und zwei Zeichen an derselben Stelle
        sind eines zu viel.
        """
        wanted = frozenset() if under is None else frozenset({under})
        if wanted == self.highlighted:
            return False
        self.highlighted = wanted
        return True

    def _note_snap_mark(self, *, over_point: bool = False) -> bool:
        """Merkt den Rasterpunkt unter dem Zeiger und sagt, ob er gewechselt
        hat.

        Neu gezeichnet wird nur beim Wechsel: bei jeder Mausbewegung wäre es
        ein voller Neuaufbau der Zeichenfläche für ein Kreuz, das an
        derselben Stelle stehen bleibt.

        **Sie weicht, wo ein Punkt gegriffen würde** (``over_point``). Beim
        Punktwerkzeug greift ein Klick den vorhandenen Punkt, statt auf das
        Raster zu fallen — dann stünde die Marke auf einer Stelle, die der Klick
        nicht nimmt, und zwei Zeichen behaupteten zwei verschiedene Ziele.

        Der Treffer kommt als Argument und nicht aus ``self.highlighted``: die
        Menge trägt zwei Bedeutungen, denn ``highlight_points`` setzt sie auch
        für die überfahrene Bedingung in der Liste. Sie hier zu lesen hieße, die
        Fangmarke von der Maus über einer Liste abhängig zu machen.
        """
        if over_point:
            mark = None
        else:
            mark = self.snapped(self._pointer) if self.snapping and self.tool != "select" else None
        if mark == self._snap_mark:
            return False
        self._snap_mark = mark
        return True

    def mouseReleaseEvent(self, event: Any) -> None:  # noqa: N802 - Qt gibt den Namen
        if event.button() == Qt.MouseButton.MiddleButton:
            self._panning = None
        if event.button() == Qt.MouseButton.LeftButton:
            self._dragging = None

    def wheelEvent(self, event: Any) -> None:  # noqa: N802 - Qt gibt den Namen
        """Das Rad zoomt **auf den Zeiger**, nicht auf die Bildmitte.

        Vorher blieb die Mitte stehen: wer an einer Ecke der Zeichnung
        arbeitete und heranzoomte, verlor sie aus dem Bild und musste
        hinterherschieben. Der Punkt unter dem Zeiger bleibt jetzt, wo er ist
        — dieselbe Zusage, die der Viewport für die Ansicht gibt (§2.9).
        """
        # Wer selbst zoomt, hat die Ansicht: von hier an folgt sie keiner
        # Einpassung mehr, bis er sie über den Knopf zurückholt.
        self._fitting = False
        position = QPointF(event.position())
        before = self._to_world(position)
        factor = 1.25 if event.angleDelta().y() > 0 else 0.8
        self._scale = min(max(self._scale * factor, MIN_SCALE), MAX_SCALE)
        after = self._to_world(position)
        self._centre = QPointF(
            self._centre.x() + (before[0] - after[0]),
            self._centre.y() + (before[1] - after[1]),
        )
        self.update()

    def keyPressEvent(self, event: Any) -> None:  # noqa: N802 - Qt gibt den Namen
        if event.key() == Qt.Key.Key_Escape and self._pending_world:
            self._pending.clear()
            self._pending_world.clear()
            self.statusChanged.emit(self.status_text())
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
        ausdrücklich. Und, wo einer liegt, der Punkt selbst."""
        menu = QMenu(self)

        # Was am angeklickten Punkt hängt, steht oben: ein Kontextmenü
        # beantwortet „was kann ich mit *dem hier* tun", und der Punkt unter
        # dem Zeiger ist das Genaueste, was dort liegt.
        hit = self._hit_point(QPointF(event.position()))
        if hit is not None:
            entry = menu.addAction(tr("Koordinaten …"))
            entry.triggered.connect(lambda _checked=False, flat=hit: self.edit_point(flat))
            menu.addSeparator()

        dialog = self.parent()
        offers = getattr(dialog, "constraint_offers", None)
        request = getattr(dialog, "request_constraint", None)
        if offers is not None and request is not None:
            for kind, enabled in offers().items():
                action = menu.addAction(_constraint_label(kind))
                action.setEnabled(enabled)
                action.triggered.connect(lambda _checked=False, chosen=kind: request(chosen))

        if menu.isEmpty():
            return
        menu.exec(event.globalPosition().toPoint())

    def edit_point(self, flat: int) -> None:
        """Einen Punkt auf genaue Koordinaten setzen.

        Ziehen ist der schnelle Weg, und das Raster hält ihn brauchbar. Wo es
        auf den Zehntelmillimeter ankommt, ist Zielen mit der Maus der falsche
        Griff — dann tippt man die Zahl ein, wie überall sonst in dieser
        Anwendung auch.

        Der Undo-Punkt wird hier gesetzt, weil es beim Ziehen der Mausdruck
        tut: der Weg über den Dialog kommt an ihm vorbei, und ohne ihn nähme
        das Rückgängig den Schritt davor.
        """
        points = self.points()
        if not 0 <= flat < len(points):
            return
        dialog = PointDialog(points[flat], self.axis_names(), parent=self)
        if dialog.exec() != PointDialog.DialogCode.Accepted:
            return
        across, up = dialog.point()
        self._remember()
        self.move_point(flat, across, up)

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

        marked = QColor(ROLES["measure"])
        for flat, (x, y) in enumerate(points):
            screen = self._to_screen(x, y)
            selected = flat in chosen_points
            lit = flat in self.highlighted
            # Ein ausgewählter Punkt war 5,0 statt 3,5 groß — drei Bildpunkte
            # im Durchmesser, und die Aussage hing praktisch allein an der
            # Farbe. Er ist jetzt fast doppelt so groß und trägt einen dicken
            # Rand: die Größe ist die zweite Kodierung, und sie muss man auch
            # sehen können (Regel 18).
            painter.setPen(
                QPen(chosen_colour if selected else line_colour, 2.4 if selected else 1.0)
            )
            painter.setBrush(chosen_colour if selected else palette.base().color())
            radius = 6.5 if selected else 3.5
            painter.drawEllipse(screen, radius, radius)
            if lit:
                # Ein Ring darum, nicht eine andere Füllung: die Auswahl hat
                # die Füllung, und zwei Aussagen an derselben Stelle müssen
                # sich unterscheiden lassen.
                painter.setPen(QPen(marked, 2.0))
                painter.setBrush(Qt.BrushStyle.NoBrush)
                painter.drawEllipse(screen, radius + 4.0, radius + 4.0)

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

    def grid_step(self) -> float:
        """Wie weit die Rasterlinien auseinanderstehen, in Millimetern.

        Sie standen fest auf zehn. Beim Herauszoomen wurde daraus eine Fläche
        aus Linien, beim Heranzoomen ein Blatt mit vier Linien darauf — und
        die beschrifteten Fünfziger blieben in beiden Fällen dieselben. Die
        Weite folgt jetzt dem Maßstab: genommen wird die feinste Stufe, deren
        Linien noch :data:`MIN_GRID_PX` auseinanderliegen.
        """
        for step in GRID_STEPS:
            if step * self._scale >= MIN_GRID_PX:
                return step
        return GRID_STEPS[-1]

    def _paint_grid(self, painter: QPainter) -> None:
        palette = self.palette()
        minor = QColor(palette.mid().color())
        minor.setAlpha(60)
        major = QColor(palette.mid().color())
        major.setAlpha(140)
        left, top = self._to_world(QPointF(0, 0))
        right, bottom = self._to_world(QPointF(self.width(), self.height()))
        step = self.grid_step()
        # Jede fünfte Linie kräftiger, und dieselbe trägt die Zahl: so bleibt
        # ablesbar, was ein Kästchen bedeutet, wenn der Maßstab die Weite
        # wechselt.
        marked = step * 5.0
        x = math.floor(left / step) * step
        while x <= right:
            screen = self._to_screen(x, 0.0)
            painter.setPen(QPen(major if _on_multiple(x, marked, step) else minor, 1.0))
            painter.drawLine(QPointF(screen.x(), 0.0), QPointF(screen.x(), float(self.height())))
            x += step
        y = math.floor(bottom / step) * step
        while y <= top:
            screen = self._to_screen(0.0, y)
            painter.setPen(QPen(major if _on_multiple(y, marked, step) else minor, 1.0))
            painter.drawLine(QPointF(0.0, screen.y()), QPointF(float(self.width()), screen.y()))
            y += step
        self._paint_scale(painter, step, left, right, bottom, top)
        self._paint_axes(painter)

    def _paint_scale(
        self, painter: QPainter, step: float, left: float, right: float, bottom: float, top: float
    ) -> None:
        """Zahlen an das Raster, an jede fünfte Linie.

        Ein Raster ohne Zahlen sagt nur, dass es ein Raster gibt. Fusion
        beschriftet seine Achsen, und ohne das weiß man beim Zeichnen nicht, ob
        ein Kästchen einen Millimeter bedeutet oder zehn — der Maßstab ändert
        sich mit jedem Rad am Zoom. Beschriftet wird deshalb die Linie, die
        auch kräftiger gezeichnet ist, und nicht ein fester Fünfzigerabstand:
        beim Hineinzoomen stünde sonst irgendwann keine Zahl mehr im Bild.
        """
        labelled = step * 5.0
        digits = _decimals_for(step)
        painter.setPen(QPen(self.palette().text().color(), 1.0))
        font = painter.font()
        font.setPointSizeF(max(font.pointSizeF() - 1.0, 6.0))
        painter.setFont(font)

        metrics = painter.fontMetrics()
        x = math.floor(left / labelled) * labelled
        while x <= right:
            if abs(x) > EPS_DISPLAY:
                screen = self._to_screen(x, 0.0)
                text = f"{x:.{digits}f}"
                # Nur, wenn die Zahl ganz hinpasst: eine abgeschnittene „1"
                # am rechten Rand ist keine Angabe, sondern ein Fehler. Am
                # linken Rand ebenso — dort stand „00" von einer -200.
                width = metrics.horizontalAdvance(text)
                if screen.x() + 2.0 >= 0.0 and screen.x() + 2.0 + width <= self.width():
                    painter.drawText(QPointF(screen.x() + 2.0, self.height() - 4.0), text)
            x += labelled
        y = math.floor(bottom / labelled) * labelled
        while y <= top:
            if abs(y) > EPS_DISPLAY:
                screen = self._to_screen(0.0, y)
                if metrics.height() <= screen.y() - 2.0 <= self.height():
                    painter.drawText(QPointF(4.0, screen.y() - 2.0), f"{y:.{digits}f}")
            y += labelled

    def _paint_axes(self, painter: QPainter) -> None:
        """Ursprung und Achsen, jede in ihrer Farbe und mit ihrem Buchstaben
        (E15).

        Vorher lagen beide in der Rasterfarbe: zwei Linien unter vielen, und
        wo der Nullpunkt liegt, musste man aus der Zeichnung erschließen. Die
        Farben sind dieselben wie am Achsenkreuz des Viewports und in jedem
        CAD, das jemand vorher benutzt hat — und weil Farbe nie allein trägt
        (Regel 18), steht der Buchstabe am Ende der Achse.

        **Der Buchstabe folgt der Ebene.** Er stand fest auf X und Y, auch auf
        der stehenden XZ-Ebene, wo die Senkrechte Z ist — die Zeichenfläche
        behauptete dann eine Richtung, die es dort nicht gibt. Auf einer
        angeklickten Fläche des Körpers bleibt er weg: sie kann beliebig
        geneigt sein, und ein Buchstabe wäre geraten.
        """
        origin = self._to_screen(0.0, 0.0)
        across, up = self.axis_names()
        for colour, name, line, horizontal in (
            (ROLES["axis_x"], across, (0.0, origin.y(), float(self.width()), origin.y()), True),
            (ROLES["axis_y"], up, (origin.x(), 0.0, origin.x(), float(self.height())), False),
        ):
            painter.setPen(QPen(QColor(colour), 1.6))
            painter.drawLine(QPointF(line[0], line[1]), QPointF(line[2], line[3]))
            if name:
                spot = (
                    QPointF(self.width() - 14.0, origin.y() - 6.0)
                    if horizontal
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
        """Was gerade entsteht — die gesetzten Punkte und die Linie zum Zeiger.

        Der Zug zum Zeiger fehlte, und das war die eigentliche Auskunft: ein
        Klick setzte einen gestrichelten Kreis, dann geschah nichts sichtbares,
        und beim zweiten Klick stand plötzlich eine Linie. Jedes CAD zeigt
        dazwischen, was es zeichnen würde.
        """
        pen = QPen(self.palette().highlight().color(), 1.2, Qt.PenStyle.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.BrushStyle.NoBrush)

        if not self._pending_world:
            self._paint_snap_mark(painter)
            return
        for world in self._pending_world:
            painter.drawEllipse(self._to_screen(*world), 4.0, 4.0)

        target = self.snapped(self._pointer)
        first = self._pending_world[0]
        last = self._pending_world[-1]
        if self.tool in ("line", "spline"):
            painter.drawLine(self._to_screen(*last), self._to_screen(*target))
        elif self.tool == "circle":
            radius = math.hypot(target[0] - first[0], target[1] - first[1]) * self._scale
            painter.drawEllipse(self._to_screen(*first), radius, radius)
        elif self.tool == "arc":
            # Ein Bogen entsteht aus Mitte, Anfang und Ende. Bis der Anfang
            # steht, zeigt die Vorschau den Radius als Strich; danach den
            # Kreis, auf dem der Bogen liegen wird.
            painter.drawLine(self._to_screen(*first), self._to_screen(*target))
            if len(self._pending_world) >= 2:
                radius = math.hypot(last[0] - first[0], last[1] - first[1]) * self._scale
                painter.drawEllipse(self._to_screen(*first), radius, radius)
        self._paint_snap_mark(painter)

    def _paint_snap_mark(self, painter: QPainter) -> None:
        """Ein Kreuz auf dem Rasterpunkt, auf den der nächste Klick fiele.

        Das Raster wird gröber gezeichnet, als gefangen wird — ohne die Marke
        wäre der Fang eine Zusage, die man erst am gesetzten Punkt nachprüfen
        kann. Nur beim Zeichnen: wer auswählt, setzt keinen Punkt.
        """
        if not self.snapping or self.tool == "select" or self._snap_mark is None:
            return
        spot = self._to_screen(*self._snap_mark)
        painter.setPen(QPen(QColor(ROLES["measure"]), 1.2))
        painter.drawLine(
            QPointF(spot.x() - SNAP_MARK_PX, spot.y()), QPointF(spot.x() + SNAP_MARK_PX, spot.y())
        )
        painter.drawLine(
            QPointF(spot.x(), spot.y() - SNAP_MARK_PX), QPointF(spot.x(), spot.y() + SNAP_MARK_PX)
        )


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


class PointDialog(QDialog):
    """Ein Punkt auf genaue Koordinaten — der Weg neben dem Ziehen.

    Zwei Zahlen, vorbelegt mit der Lage, die der Punkt gerade hat: der Dialog
    fragt nicht, wohin es gehen soll, sondern zeigt, wo es ist, und lässt
    ändern, was zu ändern ist. Wer nur die Waagerechte genau braucht, tippt
    eine Zahl und lässt die andere stehen.

    **Ein unangetastetes Feld gibt seinen Wert unverändert zurück.** Das Feld
    zeigt zwei Dezimalstellen, weil die Anzeige das überall tut (§11.2) — der
    Kern rechnet in doppelter Genauigkeit weiter (Regel 6). Ohne diese
    Unterscheidung verschob der Dialog den Punkt allein dadurch, dass man ihn
    ansah: ein projizierter Punkt bei 30,125 mm kam als 30,13 zurück, und bei
    0,001 mm als 0. Gerundet wird also nur, was der Nutzer selbst angefasst
    hat, und dann ist die Zahl seine Ansage und nicht unsere Verkürzung.
    """

    def __init__(
        self,
        point: tuple[float, float],
        axes: tuple[str, str],
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Punkt setzen"))
        self.setMinimumWidth(280)

        #: Die Lage, mit der der Dialog aufgemacht hat — sie kommt unverändert
        #: zurück, wo niemand etwas eingetippt hat.
        self._start = point
        #: Welche Felder der Nutzer angefasst hat. Ein Merker statt eines
        #: Zahlenvergleichs: Qt rundet beim Vorbelegen anders als Python
        #: (30,125 wird zu 30,13 hier und zu 30,12 dort), und ein Vergleich
        #: gegen die eigene Rundung hielte genau den Fall für eine Eingabe, den
        #: er erkennen soll.
        self._touched: set[QDoubleSpinBox] = set()

        self._across = QDoubleSpinBox(self)
        self._up = QDoubleSpinBox(self)
        for box, value in ((self._across, point[0]), (self._up, point[1])):
            box.setDecimals(2)
            box.setRange(-10_000.0, 10_000.0)
            # Ein Einheitenzeichen ist keine Übersetzung (§11.1).
            box.setSuffix(f" {DISPLAY_UNITS[0]}")
            box.setValue(value)
            # **Nach** dem Vorbelegen verbunden, sonst zählte das Vorbelegen
            # selbst als Eingabe.
            box.valueChanged.connect(lambda _value, field=box: self._touched.add(field))

        # Die Achsenbuchstaben der Ebene, wo es welche gibt. Auf einer
        # angeklickten Fläche gibt es keine — sie kann beliebig geneigt sein —,
        # und dann heißen die Felder nach der Richtung im Bild.
        first, second = axes
        form = QFormLayout()
        form.addRow(first or tr("Waagerecht"), self._across)
        form.addRow(second or tr("Senkrecht"), self._up)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
            self,
        )
        ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if ok is not None:
            ok.setText(tr("Punkt setzen"))
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(buttons)

    def point(self) -> tuple[float, float]:
        """Die eingetragene Lage — und für jedes unangetastete Feld die alte.

        Wer etwas eintippt, meint es: dann gilt seine Zahl, auf zwei Stellen,
        wie das Feld sie annimmt. Wer nichts eintippt, hat nichts gesagt, und
        dann bleibt die genaue Lage aus dem Dokument stehen.
        """
        return (
            self._across.value() if self._across in self._touched else self._start[0],
            self._up.value() if self._up in self._touched else self._start[1],
        )


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


def _needs_phrase(kind: SketchConstraintKind) -> str:
    """Was ausgewählt sein muss, damit die Bedingung gilt — als Halbsatz.

    Ein Knopf, der nur seinen Namen kennt, lässt raten, warum er grau ist:
    zehn gleich aussehende Knöpfe, und keiner sagt, was ihm fehlt. Der
    Halbsatz steht im Hinweis am Knopf und in der Meldung, die ein Kürzel
    ohne passende Auswahl auslöst — dieselbe Auskunft an beiden Stellen.

    Ganze Halbsätze statt einer aus ``_NEEDS`` zusammengesetzten Wortkette:
    ein Satz lässt sich übersetzen, eine Kette aus Zahlwort und Mehrzahl
    nicht. Dass zu jeder Bedingung einer existiert, prüft der Test.
    """
    return {
        "distance": tr("zwei Punkte"),
        "coincident": tr("zwei Punkte"),
        "horizontal": tr("eine Linie"),
        "vertical": tr("eine Linie"),
        "parallel": tr("zwei Linien"),
        "perpendicular": tr("zwei Linien"),
        "tangent": tr("eine Linie und einen Kreis oder Bogen"),
        "symmetric": tr("zwei Punkte und eine Linie"),
        "fixed": tr("einen Punkt"),
        "reference": tr("zwei Punkte"),
    }[kind]


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

#: Kürzel, die nur die Ansicht bewegen und nichts an der Zeichnung ändern.
#: Getrennt gehalten, weil sie das auch bei gesperrter Lizenz dürfen — und
#: weil ``Pos1`` dieselbe Taste ist, die in FreeCAD und im Browser „zurück
#: zum Anfang" heißt.
VIEW_KEYS: dict[str, str] = {"fit": "Home"}

#: Die Ziffern für die drei Grundebenen — dieselbe Belegung, die Fusion,
#: SolidWorks und FreeCAD für ihre Standardansichten haben.
#:
#: Die Ebene zu wechseln ist kein seltener Griff: ein Gehäuse zeichnet man von
#: oben, seine Aufhängung von der Seite, und dazwischen liegt jedes Mal ein
#: Klappmenü. Die Ziffern sind frei — die Werkzeuge liegen auf Buchstaben.
PLANE_KEYS: dict[str, str] = {"plane:xy": "1", "plane:xz": "2", "plane:yz": "3"}


@dataclass(frozen=True, slots=True)
class Surroundings:
    """Was die Zeichenfläche von der Szene um sie herum erfährt.

    Drei Angaben, drei Zwecke: der Bauraum wird als Rand eingezeichnet (E1),
    die ebenen Flächen der Körper kommen als weitere Ebenen in die Wahl
    (§30.1), und die Netze sind das, woraus *Projizieren* seine Kanten holt
    (E18).

    Sie stehen zusammen in einem Träger, weil sie zusammen gehören und zusammen
    weitergereicht werden. Ohne ihn hatte der Weg über das Operationsfeld
    nichts von allem dreien: kein Bauraum, keine Fläche des Körpers in der
    Liste, und *Projizieren* antwortete „Es gibt keinen Körper, aus dem sich
    projizieren ließe" — an einem Modell, das im Fenster stand. Der Docstring
    von :class:`SketchPanel` sagt seit je, dass keiner der beiden Wege ein
    Werkzeug bekommt, das der andere nicht hat; erst das hier macht ihn wahr.
    """

    bed: tuple[float, float] | None = None
    """Die Grundfläche des Bauraums in Millimetern."""
    faces: tuple[tuple[str, str, tuple[float, float, float]], ...] = ()
    """Ebene Flächen als Zeichenebenen: Kennung, Beschriftung, Normale."""
    bodies: tuple[Any, ...] = ()
    """Die Netze der Szene — Vorlage für die Projektion, nicht Geometrie."""


class SketchPanel(QWidget):
    """Zeichenfläche, Werkzeugleiste, Bedingungsliste, Statuszeile (§30.1).

    Der Inhalt ohne den Rahmen darum. Zwei Stellen benutzen ihn: der Dialog
    aus dem Operationsfeld und der Skizzenmodus im Fenster — und weil es
    derselbe ist, kann keiner der beiden ein Werkzeug bekommen, das der andere
    nicht hat. Was von der Szene dazugehört, reisen beide über
    :class:`Surroundings` herein.
    """

    sketchChanged = Signal()
    """Weitergereicht von der Zeichenfläche, damit ein Rahmen mithören kann."""

    def __init__(
        self,
        text: str = "",
        parameter_values: Mapping[str, float] | None = None,
        parent: QWidget | None = None,
        surroundings: Surroundings | None = None,
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
            # Nur das Zeichen, ohne Beschriftung — die einzige Stelle der
            # Oberfläche, an der das gilt. Warum es hier trägt und sonst nicht,
            # steht bei den Symbolen selbst (``app/ui/icons.py``, Abschnitt
            # Zeichenwerkzeuge). Vierzehn beschriftete Knöpfe passten nicht in
            # die Zeile: Qt kürzte sie auf „Tri… T" und „Ver…ern", und ein
            # abgeschnittenes Wort ist schlechter zu lesen als ein Bild.
            button.setIcon(icons.icon(f"sketch_{name}", button))
            button.setToolTip(f"{label}  ({key})" if key else label)
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
        # Benannt wie die Ansicht, die man sieht, und nicht wie die Ebene, auf
        # der man rechnet. „Ebene XZ — stehend, nach hinten" beschreibt
        # richtig, was passiert, und beantwortet die Frage nicht, die jemand
        # vor der Zeichenfläche hat: sehe ich das Teil von oben oder von der
        # Seite? Die Ebene steht in Klammern daneben — sie ist die Angabe, die
        # in der Projektdatei landet.
        for value, label in (
            ("plane:xy", tr("Draufsicht (XY) — liegend")),
            ("plane:xz", tr("Vorderansicht (XZ) — stehend, von vorn")),
            ("plane:yz", tr("Seitenansicht (YZ) — stehend, von der Seite")),
        ):
            key = PLANE_KEYS.get(value, "")
            self.plane_choice.addItem(f"{label}  ({key})" if key else str(label), userData=value)
        self.plane_choice.setToolTip(
            tr("Worauf gezeichnet wird. Die Ziffern 1, 2 und 3 wechseln direkt.")
        )
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

        # Der Rasterfang, an derselben Zeile wie die Ebene: beides entscheidet
        # man vor dem ersten Strich, nicht mittendrin. Ein Haken und eine
        # Weite — an ist die Vorgabe, weil ein Klick sonst auf -29,75 mm
        # landet und daraus kein Maß wird, sondern Nacharbeit.
        self.snap_toggle = QCheckBox(tr("Am Raster fangen"), self)
        self.snap_toggle.setChecked(self.canvas.snapping)
        self.snap_toggle.setToolTip(
            tr("Klicks fallen auf die eingestellte Weite. Vorhandene Punkte fangen weiterhin vor.")
        )
        self.snap_step = QDoubleSpinBox(self)
        self.snap_step.setDecimals(2)
        self.snap_step.setRange(0.05, 100.0)
        self.snap_step.setSingleStep(0.5)
        self.snap_step.setValue(self.canvas.snap_step)
        self.snap_step.setSuffix(f" {DISPLAY_UNITS[0]}")
        self.snap_step.setToolTip(tr("Auf welche Weite ein Klick fällt."))
        self.snap_toggle.toggled.connect(self._snapping_changed)
        self.snap_step.valueChanged.connect(lambda _value: self._snapping_changed())
        self._snapping_changed()
        plane_row.addWidget(self.snap_toggle)
        plane_row.addWidget(self.snap_step)
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
        offset_button.setIcon(icons.icon("sketch_offset", offset_button))
        offset_button.setToolTip(f"{tr('Versetzen')}  ({ACTION_KEYS['offset']})")
        offset_button.setAutoRaise(True)
        offset_button.clicked.connect(
            lambda: self.canvas.offset_selected(self.offset_distance.value())
        )

        mirror_button = QToolButton(self)
        mirror_button.setIcon(icons.icon("sketch_mirror", mirror_button))
        mirror_button.setToolTip(tr("Spiegeln"))
        mirror_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        mirror_menu = QMenu(mirror_button)
        for label, axis in ((tr("An der X-Achse"), "x"), (tr("An der Y-Achse"), "y")):
            entry = mirror_menu.addAction(label)
            entry.triggered.connect(
                lambda _checked=False, chosen=axis: self.canvas.mirror_selected(chosen)
            )
        mirror_button.setMenu(mirror_menu)

        construction_button = QToolButton(self)
        construction_button.setIcon(icons.icon("sketch_construction", construction_button))
        construction_button.setToolTip(
            f"{tr('Hilfsgeometrie')}  ({ACTION_KEYS['construction']}) — "
            + tr("Trägt Bedingungen, bildet aber kein Profil.")
        )
        construction_button.setAutoRaise(True)
        construction_button.clicked.connect(self.canvas.toggle_construction)

        project_button = QToolButton(self)
        project_button.setIcon(icons.icon("sketch_project", project_button))
        project_button.setToolTip(
            f"{tr('Projizieren')} — "
            + tr("Die Kanten der vorhandenen Körper auf dieser Ebene in die Skizze holen.")
        )
        project_button.setAutoRaise(True)
        project_button.clicked.connect(self.canvas.project_bodies)

        # Das Maß beim Zeichnen (E19). In Fusion zeichnet man selten und bemaßt
        # fast immer; hier gab es dafür gar nichts. Das Feld ist nur dann
        # bedienbar, wenn ein Element angefangen ist — sonst hätte es nichts,
        # worauf es sich bezieht.
        self.measure_field = QDoubleSpinBox(self)
        self.measure_field.setDecimals(2)
        self.measure_field.setRange(0.0, 10_000.0)
        self.measure_field.setSuffix(f" {DISPLAY_UNITS[0]}")
        self.measure_field.setKeyboardTracking(False)
        self.measure_field.setEnabled(False)
        self.measure_field.setToolTip(
            tr("Länge oder Durchmesser eintippen und mit der Eingabetaste setzen.")
        )
        self.measure_field.editingFinished.connect(
            lambda: self.canvas.place_measured(self.measure_field.value())
        )
        self.canvas.measuringChanged.connect(self._show_pending_measure)

        tools.addWidget(offset_button)
        tools.addWidget(self.offset_distance)
        tools.addWidget(mirror_button)
        tools.addWidget(construction_button)
        tools.addWidget(project_button)
        tools.addWidget(self.measure_field)

        # Einpassen gehört zu den Ansichtsgriffen und nicht zu den Werkzeugen,
        # steht deshalb hinten bei Rückgängig. Als Knopf und nicht nur als
        # Kürzel: eine Belegung, zu der kein sichtbares Ziel gehört, findet
        # niemand (§19.2, Regel 18).
        fit_button = QToolButton(self)
        fit_button.setIcon(icons.icon("sketch_fit", fit_button))
        fit_button.setToolTip(f"{tr('Einpassen')}  ({VIEW_KEYS['fit']})")
        fit_button.setAutoRaise(True)
        fit_button.clicked.connect(self.canvas.fit_view)
        tools.addWidget(fit_button)

        undo_button = QToolButton(self)
        undo_button.setIcon(icons.icon("sketch_undo", undo_button))
        undo_button.setToolTip(tr("Rückgängig"))
        undo_button.setAutoRaise(True)
        undo_button.clicked.connect(self.canvas.undo)
        tools.addWidget(undo_button)

        constraints_row = QHBoxLayout()
        self._constraint_buttons: dict[SketchConstraintKind, QPushButton] = {}
        for kind in _NEEDS:
            key = ACTION_KEYS.get(kind, "")
            label = _constraint_label(kind)
            constraint_button = QPushButton(f"{label}  {key}" if key else label, self)
            # Der Hinweis nennt die Auswahl, nicht noch einmal den Namen: der
            # steht auf dem Knopf. Ein grauer Knopf, dessen Hinweis nur seine
            # Beschriftung wiederholt, sagt nichts über den Grund.
            constraint_button.setToolTip(
                tr("{name} — dazu {what} auswählen.").format(name=label, what=_needs_phrase(kind))
            )
            constraint_button.clicked.connect(
                lambda _checked=False, chosen=kind: self.request_constraint(chosen)
            )
            self._constraint_buttons[kind] = constraint_button
            constraints_row.addWidget(constraint_button)
        constraints_row.addStretch(1)

        self.constraint_list = QListWidget(self)
        self.constraint_list.setToolTip(tr("Entf entfernt die gewählte Bedingung."))
        # Überfahren lässt die betroffene Geometrie aufleuchten (E19). Ohne das
        # ist „Deckung (1, 2)" nicht lesbar: welche zwei Punkte das sind, weiß
        # nur, wer die flache Nummerierung im Kopf hat.
        self.constraint_list.setMouseTracking(True)
        self.constraint_list.itemEntered.connect(self._point_at)
        self.constraint_list.currentItemChanged.connect(lambda item, _old: self._point_at(item))

        self.status = QLabel(opening or self.canvas.status_text(), self)
        self.status.setWordWrap(True)

        # Wo der Zeiger steht, rechts in der Statuszeile — an der Stelle, an
        # der jedes CAD sie hat. Sie beantwortet die Frage, die man beim
        # Zeichnen dauernd hat und für die es hier keine Antwort gab: wo bin
        # ich gerade? Erst mit ihr wird der Rasterfang sichtbar, und erst mit
        # ihr ist ein gezogener Punkt mehr als eine ungefähre Lage.
        self.coordinates = QLabel("", self)
        self.coordinates.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        self.coordinates.setToolTip(tr("Wohin der nächste Klick fällt."))
        self.canvas.pointerChanged.connect(self._show_pointer)

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
        status_row = QHBoxLayout()
        status_row.addWidget(self.status, stretch=1)
        status_row.addWidget(self.coordinates)
        layout.addLayout(status_row)

        self.canvas.sketchChanged.connect(self.sketchChanged)
        self.canvas.sketchChanged.connect(self._refresh_constraints)
        self.canvas.selectionChanged.connect(self._refresh_buttons)
        self.canvas.statusChanged.connect(self.status.setText)
        self.constraint_list.installEventFilter(self)
        self._install_shortcuts()

        # Einmal von Hand nachziehen, was sonst nur ein Signal auslöst: die
        # Skizze ist oben gesetzt worden, also **vor** diesen Verbindungen.
        # Eine geöffnete Skizze mit elf Bedingungen zeigte rechts eine leere
        # Liste, bis irgendetwas geändert wurde — und wer seine Bedingungen
        # nicht sieht, setzt sie ein zweites Mal. Die Knöpfe standen aus
        # demselben Grund alle bedienbar da, ohne dass etwas ausgewählt war.
        self._refresh_constraints()
        self._refresh_buttons()

        # Zuletzt, weil die Flächen in die eben gebaute Ebenenwahl kommen.
        if surroundings is not None:
            self.set_surroundings(surroundings)

        # Und dann einpassen — auf die Zeichnung, wenn eine mitkam, sonst auf
        # den Bauraum. Die Ansicht bleibt daran hängen, bis jemand selbst zoomt:
        # das Layout bemisst die Fläche erst nach diesem Aufruf, und in mehreren
        # Durchgängen.
        self.canvas.fit_view()

    def set_surroundings(self, surroundings: Surroundings) -> None:
        """Bauraum, Zeichenebenen und Projektionsvorlagen auf einmal setzen."""
        self.set_bed(surroundings.bed)
        self.offer_faces(surroundings.faces)
        self.offer_bodies(surroundings.bodies)

    def set_zone_margins(self, left: int, right: int) -> None:
        """Weicht den Karten des Fensters aus (§2.5).

        Im Skizzenmodus füllt dieses Panel die Fläche, und Objektbaum und
        Prüfbericht liegen darüber — die ersten Werkzeuge lagen damit unter der
        linken Karte, also Linie und Rechteck. Im Dialog gibt es keine Karten,
        dort bleibt der Rand null; gesetzt wird er von dem, der die Karten
        platziert.
        """
        layout = self.layout()
        if layout is None:
            return
        margins = layout.contentsMargins()
        if margins.left() == left and margins.right() == right:
            return
        layout.setContentsMargins(left, margins.top(), right, margins.bottom())
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

        offsetting = QShortcut(QKeySequence(ACTION_KEYS["offset"]), self)
        offsetting.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        offsetting.activated.connect(
            lambda: self.canvas.offset_selected(self.offset_distance.value())
        )

        # Rückgängig gehört an das Panel und nicht an einen Rahmen darum: den
        # Rahmen gibt es nur auf einem der beiden Wege. Im Skizzenmodus des
        # Fensters lag Strg+Z damit beim Verlauf — es nahm die letzte
        # Operation zurück, während vor dem Nutzer eine Zeichenfläche stand.
        # Das Fenster graut seine beiden Einträge im Modus dafür aus.
        undo = QShortcut(QKeySequence(QKeySequence.StandardKey.Undo), self)
        undo.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        undo.activated.connect(self.canvas.undo)

        fit = QShortcut(QKeySequence(VIEW_KEYS["fit"]), self)
        fit.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        fit.activated.connect(self.canvas.fit_view)

        helper = QShortcut(QKeySequence(ACTION_KEYS["construction"]), self)
        helper.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        helper.activated.connect(self.canvas.toggle_construction)

        for plane, key in PLANE_KEYS.items():
            view = QShortcut(QKeySequence(key), self)
            view.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            view.activated.connect(lambda chosen=plane: self.choose_plane(chosen))

    def choose_plane(self, plane: str) -> None:
        """Die Zeichenebene wechseln — über die Wahl, nicht an ihr vorbei.

        Die Zeichenfläche direkt zu setzen ließe das Auswahlfeld auf der
        vorigen Ebene stehen, und dann behaupten zwei Stellen zweierlei.
        """
        index = self.plane_choice.findData(plane)
        if index >= 0:
            self.plane_choice.setCurrentIndex(index)

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

    def _snapping_changed(self) -> None:
        """Haken und Weite an die Zeichenfläche geben.

        Das Feld wird mit dem Haken bedienbar: eine Weite einzustellen, die
        nichts tut, sieht aus wie eine Einstellung, die nicht wirkt.
        """
        active = self.snap_toggle.isChecked()
        self.snap_step.setEnabled(active)
        self.canvas.set_snapping(active, self.snap_step.value())

    def constraint_offers(self) -> dict[SketchConstraintKind, bool]:
        """Welche Bedingung zur Auswahl passt — Kontextmenü und Knöpfe lesen
        dieselbe Antwort."""
        pattern = self.canvas.selected_pattern()
        return {kind: pattern in patterns for kind, patterns in _NEEDS.items()}

    def request_constraint(self, kind: SketchConstraintKind) -> None:
        if not self.constraint_offers().get(kind):
            # Nicht stumm zurück: „D" ohne passende Auswahl tat gar nichts —
            # kein Ton, keine Zeile, und woran es lag, stand nirgends. Ein
            # Weg, der gerade nicht geht, nennt seine Bedingung (Regel 17).
            self.canvas.statusChanged.emit(
                tr("{name}: dazu erst {what} auswählen.").format(
                    name=_constraint_label(kind), what=_needs_phrase(kind)
                )
            )
            return
        targets = self.canvas.selection_targets()
        value = ""
        if kind == "distance":
            dialog = ExpressionDialog(
                self._params,
                start=measured_expression(self.canvas.points(), targets),
                parent=self,
            )
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
        # Die zwei, die sich widersprechen, stehen markiert da. Der Kern nennt
        # sie und bietet an, eine davon zu entfernen — welche das wären, war
        # bis hierher nirgends zu sehen.
        conflict = getattr(self.canvas, "conflict_pair", None) or ()
        for index, entry in enumerate(self.canvas.sketch.constraints):
            label = _constraint_label(entry.kind)
            shown = measure_label(entry, self.canvas.points())
            if shown:
                label = f"{label} {shown}"
            targets = ", ".join(str(target) for target in entry.targets)
            text = f"{label}  ({targets})"
            if index in conflict:
                # Das Zeichen trägt die Aussage, die Farbe verstärkt sie nur
                # (Regel 18) — und die Liste ist einfarbig, sobald jemand sie
                # ausdruckt.
                text = f"{CONFLICT_MARKER} {text}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, entry.targets)
            if index in conflict:
                item.setForeground(QColor(text_colour("warning", self._surface())))
                item.setToolTip(
                    tr("Diese Bedingung widerspricht einer anderen. Entf entfernt sie.")
                )
            self.constraint_list.addItem(item)

    def _surface(self) -> str:
        """Die Fläche, auf der die Liste schreibt — für die Farbwahl."""
        return self.constraint_list.palette().base().color().name()

    def _show_pointer(self, x: float, y: float) -> None:
        """Die Zeigerlage rechts in der Statuszeile.

        Die Einheit steht einmal, hinter dem Paar — so schreibt man ein
        Koordinatenpaar. Auf einer angeklickten Fläche fehlen die
        Achsenbuchstaben, und dann stehen dort nur die Zahlen: die Fläche kann
        beliebig geneigt sein, und ein „X" wäre dort eine Angabe, die nicht
        stimmt (siehe ``axis_names``).
        """
        first, second = self.canvas.axis_names()
        across, up = length(x, with_unit=False), length(y)
        self.coordinates.setText(
            f"{first} {across}  ·  {second} {up}" if first and second else f"{across}  ·  {up}"
        )

    def _show_pending_measure(self, value: float) -> None:
        """Das Feld folgt dem, was gerade gezeichnet wird."""
        self.measure_field.setEnabled(value > 0.0)
        blocked = self.measure_field.blockSignals(True)
        self.measure_field.setValue(value)
        self.measure_field.blockSignals(blocked)

    def _point_at(self, item: QListWidgetItem | None) -> None:
        """Lässt die Punkte der überfahrenen Bedingung aufleuchten."""
        targets = item.data(Qt.ItemDataRole.UserRole) if item is not None else None
        self.canvas.highlight_points(frozenset(targets or ()))

    def leaveEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Name
        """Der Zeiger ist weg — dann leuchtet auch nichts mehr."""
        super().leaveEvent(event)
        self.canvas.highlight_points(frozenset())

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
        surroundings: Surroundings | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Skizze zeichnen"))
        self.resize(860, 560)

        self.panel = SketchPanel(text, parameter_values, self, surroundings)

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

        # Undo gilt überall (§19.2) — das Kürzel dafür bringt das Panel
        # selbst mit, weil es auch ohne diesen Rahmen benutzt wird.

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
        surroundings: Surroundings | None = None,
    ) -> None:
        super().__init__(parent)
        self._text = text
        self._params = dict(parameter_values or {})
        self._surroundings = surroundings

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
        state = tr("bestimmt") if solved.free_dof == 0 else free_dof_phrase(solved.free_dof)
        self.summary.setText(f"{len(sketch.elements)} {tr('Elemente')} · {state}")

    def _edit(self) -> None:
        dialog = SketchEditorDialog(self._text, self._params, self, self._surroundings)
        if dialog.exec() != SketchEditorDialog.DialogCode.Accepted:
            return
        self.set_text(dialog.sketch_text())
