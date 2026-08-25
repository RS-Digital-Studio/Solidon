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
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, replace
from typing import Any, Final

from PySide6.QtCore import QPoint, QPointF, QRectF, QSignalBlocker, Qt, Signal
from PySide6.QtGui import QColor, QKeySequence, QPainter, QPainterPath, QPen, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFormLayout,
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMenu,
    QPushButton,
    QSizePolicy,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.core.errors import AppError, SketchConflictError
from app.core.sketch import edit, shapes
from app.core.sketch.profile import regions_of
from app.core.sketch.serialize import sketch_from_text, sketch_to_text
from app.core.sketch.solver import solve_sketch
from app.core.types import (
    Sketch,
    SketchConstraint,
    SketchConstraintKind,
    SketchElement,
    SketchElementKind,
    SolvedSketch,
)
from app.core.units import EPS_DISPLAY
from app.i18n import tr
from app.ui import cursors, icons
from app.ui.labels import LengthSpin, length, localised
from app.ui.leash import weak_slot
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

#: Die feinste Weite, die sich eintippen lässt.
#:
#: Sie stand als Untergrenze am Feld, bis die Null dort gebraucht wurde: Der
#: Sonderwert „Automatisch" sitzt bei Qt immer auf dem Minimum, also musste
#: dieses auf null. Damit war die Grenze weg, und bei zwei Nachkommastellen
#: nahm das Feld 0,01 mm an — ein Fang, der keiner mehr ist, und weit unter
#: allem, was ein Drucker auflöst. Sie steht deshalb hier weiter und wird beim
#: Eintippen angewandt.
LEAST_SNAP_MM = 0.05

#: Wie eng die Rasterlinien im Bild höchstens stehen, in Bildpunkten. Darunter
#: wird die nächstgröbere Stufe genommen — ein Raster, dessen Linien sich
#: berühren, ist eine Fläche.
#:
#: Zwanzig und nicht sieben, und der Wert entscheidet drei Dinge auf einmal.
#:
#: **Die Zahlen.** Beschriftet wird jede fünfte Linie, sie stehen also
#: mindestens hundert Bildpunkte auseinander. Bei sieben waren das
#: fünfunddreißig — auf einem bildschirmfüllenden Fenster stand unter der
#: Zeichnung eine geschlossene Zahlenreihe im Abstand von zweieinhalb
#: Millimetern.
#:
#: **Die Dichte.** Das Raster darüber war ein halber Millimeter fein für ein
#: Rechteck von 120 — Millimeterpapier, auf dem die kräftige fünfte Linie
#: zwischen ihren Nachbarn untergeht.
#:
#: **Die Gleichmäßigkeit.** Jede Linie wird auf einen ganzen Bildpunkt gelegt
#: (:meth:`SketchCanvas._paint_grid`), und wenn ein Kästchen 14,4 Punkte breit
#: ist, wechseln sich 14 und 15 ab: ein Raster, das sichtbar atmet. Der Fehler
#: ist derselbe, sein Anteil aber halb so groß, sobald das Kästchen doppelt so
#: breit ist.
MIN_GRID_PX = 20.0

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


#: Wie ein Element heißt und wie seine Punkte heißen (§30.1).
#:
#: Die Bedingungsliste zeigte die rohen Punktindizes: „Deckung (1, 2)". Das ist
#: die flache Nummerierung der Skizze — Elemente der Reihe nach, Punkte je
#: Element der Reihe nach —, und lesbar ist sie für niemanden, der sie nicht im
#: Kopf hat. Das Aufleuchten beim Überfahren (E19) half dem, der die Maus
#: darüber hielt; die Liste selbst blieb eine Zahlenkolonne.
#:
#: Die Rollen kommen aus dem Docstring von ``SketchElement``: Linie hat Anfang
#: und Ende, Kreis Mitte und einen Punkt auf dem Rand, Bogen Mitte, Anfang und
#: Ende. Der Spline hat keine feste Punktzahl und zählt deshalb durch.
_ELEMENT_NAMES: Final[dict[SketchElementKind, str]] = {
    "point": "Punkt",
    "line": "Linie",
    "circle": "Kreis",
    "arc": "Bogen",
    "spline": "Kurve",
}


def _element_name(kind: SketchElementKind, number: int) -> str:
    """„Linie 2" — der Name eines Elements, je Art durchgezählt."""
    return f"{tr(_ELEMENT_NAMES[kind])} {number}"


def _point_role(kind: SketchElementKind, position: int) -> str:
    """Was ein Punkt seinem Element bedeutet — „Anfang", „Mitte", „Rand"."""
    roles: dict[SketchElementKind, tuple[str, ...]] = {
        "point": (),
        "line": (tr("Anfang"), tr("Ende")),
        "circle": (tr("Mitte"), tr("Rand")),
        "arc": (tr("Mitte"), tr("Anfang"), tr("Ende")),
        "spline": (),
    }
    known = roles[kind]
    if position < len(known):
        return known[position]
    if kind == "spline":
        return f"{tr('Punkt')} {position + 1}"
    return ""


def point_names(sketch: Sketch) -> tuple[str, ...]:
    """Ein Name je Punkt der flachen Punktliste — „Linie 1 Ende".

    Dieselbe Reihenfolge, die ``SketchConstraint.targets`` meint. Ein Punkt für
    sich trägt keine Rolle: „Punkt 1" ist schon der ganze Name.
    """
    names: list[str] = []
    seen: dict[str, int] = {}
    for element in sketch.elements:
        seen[element.kind] = seen.get(element.kind, 0) + 1
        label = _element_name(element.kind, seen[element.kind])
        for position in range(len(element.points)):
            role = _point_role(element.kind, position)
            names.append(f"{label} {role}".strip() if role else label)
    return tuple(names)


def targets_phrase(sketch: Sketch, targets: tuple[int, ...]) -> str:
    """Woran eine Bedingung hängt, in Worten statt in Indizes.

    Liegen alle Ziele auf **einem** Element, steht es einmal da: „Waagerecht —
    Linie 1" und nicht „Linie 1 Anfang, Linie 1 Ende". Das ist der häufigste
    Fall, und er ist auch der, in dem die Aufzählung nur Platz kostet.

    Ein Index, den die Skizze nicht hat, wird übersprungen statt geraten — er
    kommt vor, während ein Element gerade entsteht.
    """
    names = point_names(sketch)
    owners: list[int] = []
    for number, element in enumerate(sketch.elements):
        owners.extend([number] * len(element.points))
    inside = [target for target in targets if 0 <= target < len(names)]
    if not inside:
        return ""
    if len({owners[target] for target in inside}) == 1:
        element = sketch.elements[owners[inside[0]]]
        if len(inside) == len(element.points) or len(element.points) == 1:
            # Alle Punkte des Elements, oder ein Element mit nur einem: dann
            # ist das Element gemeint und nicht eine Auswahl daraus.
            return (
                names[inside[0]].rsplit(" ", 1)[0] if len(element.points) > 1 else names[inside[0]]
            )
    return ", ".join(names[target] for target in inside)


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

    **Mit Einheit.** Hier stand ``with_unit=False``, und in der
    Bedingungsliste las sich das als „Abstand 30,00" — eine Zahl ohne Angabe,
    wovon. Solange alles Millimeter waren, konnte man sie sich denken; seit die
    Anzeigeeinheit umschaltbar ist (§19.3), ist eine nackte Zahl eine Vermutung.
    """
    try:
        value = float(expression)
    except ValueError:
        return expression
    return length(value)


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
    return f"({length(math.hypot(bx - ax, by - ay))})"


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


def grid_step_for(scale: float) -> float:
    """Die Rasterweite zu einem Maßstab, in Millimetern.

    ``scale`` sind Bildpunkte je Millimeter. Genommen wird die feinste Stufe
    der 1-2-5-Folge, deren Linien noch :data:`MIN_GRID_PX` auseinanderliegen:
    Eine feste Weite ist herausgezoomt eine Fläche aus Linien und
    hineingezoomt ein Blatt mit vier Linien darauf.

    **Eine freie Funktion, seit es zwei Maßstäbe gibt.** Als Methode las sie
    ``self._scale`` — den Maßstab der Zeichenfläche. Im Skizzenmodus im
    Viewport ist das der falsche: Die Fläche ist dort unsichtbar und ihr
    Maßstab steht auf dem Startwert, während gezoomt wird an der Kamera.
    Gemessen kam dabei ein Raster von 20 mm heraus, gefangen wurde auf 1 mm —
    zwei Zahlen für dieselbe Sache, und die sichtbare war die falsche.
    """
    for step in GRID_STEPS:
        if step * scale >= MIN_GRID_PX:
            return step
    return GRID_STEPS[-1]


def sheet_point(
    drawing: tuple[float, float],
    centre: tuple[float, float],
    scale: float,
    size: tuple[float, float],
) -> tuple[float, float]:
    """Wo ein Zeichenpunkt auf dem Blatt liegt, in Bildpunkten (§30.1).

    Die Mitte des Blattes zeigt ``centre``, ``scale`` ist der Maßstab in
    Bildpunkten je Millimeter, ``size`` die Größe der Zeichenfläche. **Y läuft
    nach unten** — Qt zählt so, die Zeichnung nicht, und dieses Minus ist die
    ganze Umrechnung dazwischen.

    Eine freie Funktion und keine Methode, aus demselben Grund wie
    :func:`app.ui.viewport.sketch_grid` und ``bed_scale``: Als Methode eines
    Widgets ist sie nur mit einem Widget prüfbar, und ihre Umkehrbarkeit —
    die Eigenschaft, an der die ganze Zeichenfläche hängt — war deshalb nie
    geprüft. Ein Klick landete dort, wo ``_to_screen`` ihn hingelegt hatte,
    und ob beide Richtungen zueinander passen, hat niemand gegen Zahlen
    gehalten.
    """
    return (
        size[0] / 2.0 + (drawing[0] - centre[0]) * scale,
        size[1] / 2.0 - (drawing[1] - centre[1]) * scale,
    )


def drawing_point(
    sheet: tuple[float, float],
    centre: tuple[float, float],
    scale: float,
    size: tuple[float, float],
) -> tuple[float, float]:
    """Welcher Zeichenpunkt unter einer Blattstelle liegt — die Umkehrung von
    :func:`sheet_point`.

    Sie ist der Weg, den jeder Klick nimmt: Was der Nutzer trifft, ist eine
    Stelle in Bildpunkten; was die Skizze speichert, sind Millimeter.
    """
    return (
        (sheet[0] - size[0] / 2.0) / scale + centre[0],
        -(sheet[1] - size[1] / 2.0) / scale + centre[1],
    )


def _decimals_for(step: float) -> int:
    """Wie viele Nachkommastellen eine Rasterzahl braucht.

    Bei einer Weite von zehn Millimetern stand ``f"{x:.0f}"`` richtig; bei
    einer halben stünde dort dreimal dieselbe Null.
    """
    if step >= 1.0:
        return 0
    return 1 if step >= 0.1 else 2


def _located(sketch: Sketch, flat: int) -> tuple[int, int]:
    """Elementindex und lokaler Punktindex zu einem flachen Index."""
    offsets = edit.offsets_of(sketch)
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
    viewFitted = Signal(float, float, float, float)
    """Mitte und Spannweite der Einpassung, in Millimetern der Zeichenebene.

    Seit P4 wird im Viewport gezeichnet, und dort setzt nicht dieses Widget
    den Ausschnitt, sondern die Kamera. Der Canvas rechnet weiter, was ins
    Bild gehört — er sagt es jetzt nur weiter, statt es allein an sich
    selbst zu setzen."""
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
        self.outline: bool = False
        """Ob die Zeichnung schon einen Umriss ergibt (:meth:`_outline_state`)."""
        self.tool = "select"
        self._pending: list[int] = []
        """Beim Zeichnen: die flachen Indizes der schon gesetzten Punkte —
        eine Linie braucht zwei, ein Bogen drei Klicks."""
        self._pending_world: list[tuple[float, float]] = []
        #: Ob der letzte Bogenklick auf einer Geraden lag. Nur für die Zeile:
        #: Ein abgelehnter Klick, der nichts sagt, sieht aus wie ein
        #: verschluckter (Regel 17).
        self._arc_was_flat = False
        self.selection: list[tuple[str, tuple[int, ...]]] = []
        """Die Auswahl in Klickreihenfolge: („point", (i,)) oder ein Element
        mit seinen flachen Punktindizes — „A parallel B" ist nicht „B
        parallel A"."""
        self._undo: list[Sketch] = []
        self._dragging: int | None = None
        self._shift_from: tuple[float, float] | None = None
        """Von wo aus die Auswahl geschoben wird — ``None`` heißt: gar nicht."""
        self._shifting = False
        """Ob die Schwelle schon überschritten ist (:meth:`_shift_selection`)."""
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

        self.measure_field = LengthSpin(self)
        """Das Maß beim Zeichnen — **am Zeiger und nicht in der Leiste** (E19).

        Es stand unten in der Werkzeugzeile, und das ist beim Zeichnen die
        falsche Stelle: Wer eine Linie zieht, sieht auf ihre Spitze, und die
        Zahl, die er eintippen will, stand am Fensterrand. In Fusion steht sie
        am Zeiger, und darum ist das Eintippen dort der Normalweg — hier war es
        eine Funktion, die man kennen musste.

        Nebenbei löst es den breitesten Posten der Werkzeugzeile auf; Schritt
        eins hatte ihn nur ausgeblendet, solange nichts gezeichnet wird.
        """
        self.measure_field.set_range_mm(0.0, 10_000.0)
        self.measure_field.setKeyboardTracking(False)
        self.measure_field.setVisible(False)
        self.measure_field.setToolTip(
            tr("Länge oder Durchmesser eintippen und mit der Eingabetaste setzen.")
        )
        self.measure_field.setAccessibleName(tr("Abstand"))
        self.measure_field.setMaximumWidth(TOOLBAR_FIELD_WIDTH)
        self.measuringChanged.connect(self._place_measure_field)
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
        # **Auch wenn das eigene Bild niemand sieht.** Im Viewport-Modus ist
        # dieses Widget unsichtbar; alles Folgende setzt einen Maßstab, der
        # dort auf nichts wirkt. Die Kamera hört auf dieses Signal, und ohne
        # es war der Einpassen-Knopf im Skizzenmodus folgenlos.
        self.viewFitted.emit(centre[0], centre[1], span_x, span_y)
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
        drawn = edit.flat_points(self.sketch)
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
        self.outline = self._outline_state()
        self.sketchChanged.emit()
        self.statusChanged.emit(self.status_text())
        self.update()

    def _outline_state(self) -> bool:
        """Ob aus der Zeichnung schon ein Umriss wird.

        Ob eine Kontur geschlossen ist, war bis zum Bestätigen der Operation
        nicht zu erfahren: Wer vier Linien zog und den letzten Klick knapp
        neben den ersten Punkt setzte, sah dasselbe Bild wie einer, der
        getroffen hatte. Die Auskunft kam erst danach, als Absage.

        Gefragt wird derselbe Kern, der später rechnet
        (:func:`app.core.sketch.profile.regions_of`) — die Antwort ist damit
        dieselbe und nicht bloß eine ähnliche. Übernommen wird aber nur das
        Ja oder Nein und **nicht** sein Satz: „Der Umriss ist nicht
        geschlossen" ist die Absage einer Operation, die jemand ausgelöst hat.
        In der Zeile stünde sie vom ersten Strich an und wäre bis zum letzten
        Klick eine Warnung vor einem Zustand, den man gerade beabsichtigt.
        """
        if self.solved is None or self.conflict:
            return False
        try:
            regions_of(self.solved)
        except AppError:
            return False
        return True

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
        # Zwei Fragen, eine Zeile, und die erste ist die dringendere: ohne
        # geschlossenen Umriss scheitert die Operation, mit ihm ist ein freier
        # Freiheitsgrad höchstens ungenau. Beide stehen nebeneinander, weil
        # keine die andere beantwortet — ein bestimmtes Rechteck kann offen
        # sein, ein geschlossenes darf wackeln.
        state = tr("Geschlossen") if self.outline else tr("Noch offen")
        if self.solved.free_dof == 0:
            return tr("{state} · bestimmt — alle Freiheitsgrade sind vergeben.").format(state=state)
        if self.solved.free_dof == 1:
            return tr("{state} · ein Freiheitsgrad ist noch frei.").format(state=state)
        return tr("{state} · {count} Freiheitsgrade sind noch frei.").format(
            state=state, count=self.solved.free_dof
        )

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
            # **Anfang, Ende, Wölbung** — die Reihenfolge von Fusion und
            # Onshape. Vorher war der erste Klick die Mitte: ein Punkt, der auf
            # keiner Kante liegt und den beim Zeichnen eines Umrisses niemand
            # im Kopf hat. Gespeichert wird weiterhin (Mitte, Anfang, Ende) —
            # ``edit.arc_through`` rechnet um, das Datenformat bleibt.
            if self._arc_was_flat and started >= 2:
                return tr(
                    "Der Punkt lag auf der Geraden zwischen Anfang und Ende — "
                    "daraus wird kein Bogen. Weiter daneben klicken."
                )
            if started >= 2:
                return tr("Bogen: der nächste Klick sagt, wie weit er sich wölbt.")
            if started:
                return tr("Bogen: der nächste Klick setzt das Ende.")
            return tr("Bogen: erster Klick setzt den Anfang.")
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
        shift = len(edit.flat_points(self.sketch))
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

        offsets = edit.offsets_of(self.sketch)
        removed: set[int] = set()
        for index in element_indices:
            begin = offsets[index]
            removed.update(range(begin, begin + len(self.sketch.elements[index].points)))

        mapping: dict[int, int] = {}
        fresh = 0
        for old in range(len(edit.flat_points(self.sketch))):
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

    def move_selected(self, dx: float, dy: float) -> None:
        """Schiebt die ganze Auswahl — der Griff, den es nicht gab.

        Ohne ihn war eine gezeichnete Form nur punktweise zu bewegen: vier
        Züge für ein Rechteck, und die ersten drei verziehen es. Wie beim
        Ziehen eines einzelnen Punktes wird hier **nicht** gemerkt — den
        Undo-Punkt setzt der Mausdruck, sonst stünden im Rückgängig so viele
        Schritte, wie die Maus Meldungen geschickt hat.
        """
        indices = tuple(sorted({_located(self.sketch, entry[1][0])[0] for entry in self.selection}))
        if not indices:
            return
        self.sketch = edit.move(self.sketch, indices, dx, dy)
        self._resolve()

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

    def _sheet(self) -> tuple[tuple[float, float], float, tuple[float, float]]:
        """Wie die Zeichnung gerade auf dem Blatt liegt: Mitte, Maßstab, Größe.

        Die drei Angaben zusammen, weil die Umrechnung sie zusammen braucht —
        und einmal, weil zwei Aufrufstellen sonst dieselbe Zerlegung von
        ``_centre`` schreiben.
        """
        return (
            (self._centre.x(), self._centre.y()),
            self._scale,
            (float(self.width()), float(self.height())),
        )

    def _to_screen(self, x: float, y: float) -> QPointF:
        place = sheet_point((x, y), *self._sheet())
        return QPointF(place[0], place[1])

    def _to_world(self, position: QPointF) -> tuple[float, float]:
        return drawing_point((position.x(), position.y()), *self._sheet())

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
        offsets = edit.offsets_of(self.sketch)
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
                # Und damit hängt die Auswahl am Zeiger: wer ein Element
                # anklickt und die Maus bewegt, schiebt es. Gemerkt wird der
                # Ort, nicht der Zustand — der Undo-Punkt entsteht erst, wenn
                # wirklich geschoben wird (``_shift_selection``). Sonst legte
                # jeder Auswahlklick einen Schritt ab, der nichts geändert
                # hat, und das Rückgängig zählte Klicks statt Änderungen.
                self._shift_from = self._to_world(position)
                self._shifting = False
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

    def place_on_plane(self, point: tuple[float, float], *, extend: bool = False) -> None:
        """Ein Klick, angegeben in **Zeichenkoordinaten** statt in Bildpunkten.

        Der Weg für den Skizzenmodus im Viewport (§30.1, Stufe zwei): Dort
        kommt der Ort nicht aus einem Mausereignis auf dieser Fläche, sondern
        aus dem Schnitt des Sichtstrahls mit der Zeichenebene
        (:func:`app.core.sketch.planes.ray_hit`). Millimeter sind, was beide
        Wege gemeinsam haben.

        **Umgerechnet wird über :meth:`_to_screen`, und das ist kein Umweg,
        sondern die Zusage aus P2c.** Hin und zurück sind exakt umkehrbar
        (`tests/test_sketch_editor.py`), also landet der Punkt genau dort, wo
        er hingehört — und zwar **unabhängig von der Größe dieser Fläche**:
        Sie kürzt sich aus beiden Richtungen heraus. Deshalb darf der Canvas
        im Viewport-Modus unsichtbar bleiben und trotzdem rechnen.

        Und deshalb geht der Klick durch :meth:`place` statt an ihr vorbei:
        Was ein Klick tut, entscheidet die Methode, die auch ein Test ruft —
        Fang, Deckung und Undo-Punkt hängen daran
        (`.claude/rules/zeichenflaeche.md`).
        """
        self.place(self._to_screen(point[0], point[1]), extend=extend)

    def hover_on_plane(self, point: tuple[float, float]) -> None:
        """Der Zeiger steht auf dieser Stelle der Ebene, ohne zu klicken.

        Dieselbe Übersetzung wie in :meth:`place_on_plane`, für die Vorschau:
        Linie, Kreis und Bogen zeigen, was entsteht, bis der Klick sie
        festmacht — ohne das setzt ein Klick einen gestrichelten Kreis, dann
        geschieht nichts, und beim zweiten steht plötzlich eine Linie da.
        """
        self.note_pointer(self._to_screen(point[0], point[1]))

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
        # Der Hinweis über den flachen Bogen gilt dem einen abgelehnten Klick.
        # Bliebe er stehen, läse er sich wie eine Eigenschaft der Zeichnung.
        self._arc_was_flat = False

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

        begin = len(edit.flat_points(self.sketch))
        points = tuple(self._pending_world)
        # **Wo der wievielte Klick im gespeicherten Element landet.** Bei Linie,
        # Kreis und Punkt in derselben Folge, in der geklickt wurde; beim Bogen
        # nicht, siehe unten.
        seats = {index: index for index in range(len(points))}
        if self.tool == "arc":
            # Geklickt wird Anfang, Ende, Wölbung — gespeichert bleibt
            # (Mitte, Anfang, Ende). Die Reihenfolge im Datenmodell ist
            # unangetastet: Sie steht so in jeder Projektdatei und im Langloch.
            stored = edit.arc_through(*points)
            if stored is None:
                # Drei Punkte auf einer Geraden geben keinen Kreis. Der Klick
                # wird nicht angenommen, und die Zeile sagt warum (Regel 17) —
                # die ersten beiden bleiben stehen, damit nur der eine Klick
                # zu wiederholen ist und nicht der ganze Bogen.
                self._pending_world.pop()
                if self._pending:
                    self._pending.pop()
                self._arc_was_flat = True
                self.statusChanged.emit(self.status_text())
                self.update()
                return
            self._arc_was_flat = False
            points = stored
            # Die Wölbung wird zur Mitte gerechnet und hat keinen eigenen
            # Platz; Anfang und Ende können dabei getauscht sein. Ohne diese
            # Zuordnung setzte eine Deckung auf den falschen Punkt — sichtbar
            # erst, wenn der Löser die Skizze verzieht.
            swapped = stored[1] != self._pending_world[0]
            seats = {0: 2, 1: 1} if swapped else {0: 1, 1: 2}
        element = SketchElement(self.tool, points)  # type: ignore[arg-type]
        snapped_pairs = tuple(
            SketchConstraint("coincident", (snapped_flat, begin + seats[local]))
            for local, snapped_flat in enumerate(self._pending)
            if snapped_flat >= 0 and local in seats
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

    def _place_measure_field(self, value: float) -> None:
        """Das Maßfeld an den Zeiger legen — oder wegnehmen, wenn es nichts misst.

        **Es kippt an den Rändern**, statt hinauszuragen: Ein Feld, das zur
        Hälfte außerhalb der Fläche liegt, zeigt seine Zahl nicht, und
        ausgerechnet in der unteren rechten Ecke wäre das der Regelfall —
        dorthin zieht man die letzte Linie eines Umrisses.

        Der Fokus wird hier **nicht** geholt. Wer zeichnet, soll weiterzeichnen
        können; die erste Ziffer holt ihn (siehe ``keyPressEvent``).

        **Weg statt grau**, und die Hausregel „grau und begründet, nicht
        unsichtbar" gilt hier nicht: Sie steht für Felder eines Dialogs, die
        ein Umschalter wirkungslos macht — wer die Zeile vermisst, sucht sie.
        Dieses Feld vermisst niemand, weil es ohne angefangenes Element nichts
        hätte, worauf es sich bezieht. Es erscheint genau dann, wenn der Blick
        ohnehin dort liegt.
        """
        if value <= 0.0:
            self.measure_field.setVisible(False)
            return

        # Stumm gesetzt: ``editingFinished`` schließt das Element ab, und ein
        # Wert, den die Zeigerbewegung schreibt, ist keine Eingabe.
        blocked = self.measure_field.blockSignals(True)
        self.measure_field.set_value_mm(value)
        self.measure_field.blockSignals(blocked)
        self.measure_field.adjustSize()
        self.measure_field.setVisible(True)

        tip = self._to_screen(*self._pointer)
        width = self.measure_field.width()
        height = self.measure_field.height()
        left = tip.x() + MEASURE_GAP
        top = tip.y() + MEASURE_GAP
        if left + width > self.width():
            left = tip.x() - MEASURE_GAP - width
        if top + height > self.height():
            top = tip.y() - MEASURE_GAP - height
        # Und wenn beides nicht passt, weil die Fläche kleiner ist als das
        # Feld: lieber am Rand kleben als halb draußen.
        left = max(0.0, min(left, float(self.width() - width)))
        top = max(0.0, min(top, float(self.height() - height)))
        self.measure_field.move(int(left), int(top))

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

        begin = len(edit.flat_points(self.sketch))
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
        begin = len(edit.flat_points(self.sketch))
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
        self.note_pointer(QPointF(event.position()), buttons=event.buttons())

    def note_pointer(self, position: QPointF, buttons: Any = Qt.MouseButton.NoButton) -> None:
        """Der Zeiger steht hier — Vorschau, Fangmarke und Aufleuchten nachziehen.

        Aus :meth:`mouseMoveEvent` herausgelöst, damit sie auch ohne
        Mausereignis auf dieser Fläche gerufen werden kann: Im Skizzenmodus im
        Viewport kommt die Stelle aus dem Sichtstrahl
        (:meth:`hover_on_plane`), nicht aus einem Klick auf dieses Widget.

        Dieselbe Aufteilung wie bei :meth:`place` und :meth:`grab_point`, und
        aus demselben Grund: **Was ein Zeiger bewirkt, entscheidet die
        Methode, die auch ein Test ruft** — die Ereignisse übersetzen nur
        (`.claude/rules/zeichenflaeche.md`).
        """
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
        if self._dragging is not None and buttons & Qt.MouseButton.LeftButton:
            # Ein gezogener Punkt fällt auf dieselbe Weite wie ein gesetzter —
            # sonst wäre das Raster eine Zusage, die beim ersten Nachbessern
            # nicht mehr gilt.
            target = self.snapped(self._pointer)
            self.move_point(self._dragging, target[0], target[1])
        elif self._shift_from is not None and buttons & Qt.MouseButton.LeftButton:
            self._shift_selection(position)
        elif self._pending_world:
            self.measuringChanged.emit(self.pending_measure())
            self.update()
        elif moved or hovered:
            self.update()

    def _shift_selection(self, position: QPointF) -> None:
        """Schiebt die Auswahl mit der Hand — aber erst, wenn es eine Geste ist.

        Ohne die Schwelle wäre jeder Auswahlklick ein Verschieben um die zwei
        Bildpunkte, um die eine Hand beim Klicken wandert: die Form säße
        danach ein Zehntelmillimeter daneben, und niemand hätte das gewollt.
        Qt kennt das Maß, ab dem eine Bewegung eine Absicht ist
        (``startDragDistance``) — dieselbe Zahl, die ein Ziehen überall sonst
        im System auslöst.

        Der Undo-Punkt entsteht hier, beim ersten wirklichen Zug, und nur
        einmal: ``move_selected`` merkt nicht, sonst stünden im Rückgängig so
        viele Schritte, wie die Maus Meldungen geschickt hat.
        """
        if self._shift_from is None:
            return
        across, up = self._pointer
        if not self._shifting:
            start = self._to_screen(*self._shift_from)
            moved = math.hypot(position.x() - start.x(), position.y() - start.y())
            if moved < QApplication.startDragDistance():
                return
            self._remember()
            self._shifting = True
        self.move_selected(across - self._shift_from[0], up - self._shift_from[1])
        self._shift_from = (across, up)

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
            self._shift_from = None
            self._shifting = False

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
        # **Die erste Ziffer beginnt die Eingabe, ohne Klick und ohne Tabulator.**
        # Das ist der Grund, warum das Feld überhaupt am Zeiger steht: Ein Feld,
        # das man erst anklicken muss, verlangt genau die Handbewegung, die das
        # Zeichnen unterbricht — und der Zeiger steht danach woanders, also auch
        # das Maß, das er gerade zeigte.
        # **Die Bedingung ist die Sache, nicht ihre Darstellung.** ``isVisible()``
        # wäre hier untauglich: Ein Fenster, das nie gezeigt wurde, meldet für
        # jedes Kind falsch, und der ganze Zweig liefe in der Suite nie.
        # Gefragt wird, ob es etwas zu messen gibt — genau das, wonach sich
        # auch das Feld richtet.
        if self.pending_measure() > 0.0 and event.text()[:1].isdigit():
            self.measure_field.setFocus(Qt.FocusReason.OtherFocusReason)
            # Von vorn und nicht an den Zeigerwert angehängt: Wer „25" tippt,
            # meint 25 und nicht 1025.
            self.measure_field.selectAll()
            editor = self.measure_field.lineEdit()
            # An das Eingabefeld und nicht an das Drehfeld: Qt reicht Tasten
            # dorthin weiter, und ein ``event()`` auf dem Drehfeld selbst
            # landet in der Pfeiltastenbehandlung statt im Text.
            QApplication.sendEvent(editor, event)
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
        menu = self.context_menu_at(self._hit_point(QPointF(event.position())))
        if menu.isEmpty():
            return
        menu.exec(event.globalPosition().toPoint())

    def context_menu_at(self, hit: int | None) -> QMenu:
        """Was das Kontextmenü anbietet — gebaut, nicht gezeigt.

        Getrennt vom Zeigen, weil ein Menü, das sich selbst öffnet, in einem
        Test die Suite anhält: ``QMenu.exec`` blockiert wie ein modaler
        Dialog. Dieselbe Regel wie bei ``place`` — was ein Klick tut,
        entscheidet die Methode, die auch ein Test ruft.
        """
        menu = QMenu(self)
        # Sonst bleibt der Grund an der gesperrten Bedingung ungelesen: ``QMenu``
        # zeigt Hinweise von Haus aus nicht an.
        menu.setToolTipsVisible(True)

        # Was am angeklickten Punkt hängt, steht oben: ein Kontextmenü
        # beantwortet „was kann ich mit *dem hier* tun", und der Punkt unter
        # dem Zeiger ist das Genaueste, was dort liegt.
        if hit is not None:
            entry = menu.addAction(tr("Koordinaten …"))
            entry.triggered.connect(lambda _checked=False, flat=hit: self.edit_point(flat))
            menu.addSeparator()

        # Löschen stand allein auf der Entf-Taste. Wer die nicht rät, wird ein
        # Element nicht los: in der Werkzeugleiste steht es nicht, und ein
        # Kontextmenü ist der Ort, an dem man nachsieht, was mit *dem hier*
        # geht. Das Kürzel steht daneben — so lernt man es nebenbei.
        if self.selection:
            remove = menu.addAction(tr("Löschen  (Entf)"))
            remove.triggered.connect(lambda _checked=False: self.remove_selected())
            menu.addSeparator()

        dialog = self.parent()
        offers = getattr(dialog, "constraint_offers", None)
        request = getattr(dialog, "request_constraint", None)
        if offers is not None and request is not None:
            for kind, enabled in offers().items():
                action = menu.addAction(_constraint_label(kind))
                action.setEnabled(enabled)
                # **Grau allein ist keine Auskunft.** Die halbe Liste steht bei
                # jeder Auswahl gesperrt da, und welche Auswahl fehlt, stand nur
                # am Knopf in der Leiste und in der Meldung nach dem Kürzel. Der
                # Halbsatz kommt aus derselben Quelle wie dort — drei
                # Formulierungen derselben Bedingung wären drei Gelegenheiten,
                # auseinanderzulaufen.
                if not enabled:
                    action.setToolTip(
                        tr("{name} — dazu {what} auswählen.").format(
                            name=_constraint_label(kind), what=_needs_phrase(kind)
                        )
                    )
                action.triggered.connect(lambda _checked=False, chosen=kind: request(chosen))

        return menu

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
        offsets = edit.offsets_of(self.sketch)
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
        """Wie weit die Rasterlinien auseinanderstehen, in Millimetern."""
        return grid_step_for(self._scale)

    def _paint_grid(self, painter: QPainter) -> None:
        palette = self.palette()
        # **Ohne Alpha.** Die beiden Farben stehen in ``theme.THEMES`` und sind
        # dort gegen die Zeichenfläche gerechnet und am Bild geprüft, je Thema
        # eigene Zahlen. Hier stand ``palette.mid()`` mit Alpha 60 und 140 —
        # auf eine Rolle, die das Thema nie gesetzt hat. Angekommen ist Qts
        # Vorgabe ``#282828``, und gemischt waren das 1,02 Kontrast: das Raster
        # wurde gezeichnet und war unsichtbar, während der Fang darauf einrastet.
        minor = palette.midlight().color()
        major = palette.mid().color()
        left, top = self._to_world(QPointF(0, 0))
        right, bottom = self._to_world(QPointF(self.width(), self.height()))
        step = self.grid_step()
        # Jede fünfte Linie kräftiger, und dieselbe trägt die Zahl: so bleibt
        # ablesbar, was ein Kästchen bedeutet, wenn der Maßstab die Weite
        # wechselt.
        marked = step * 5.0
        # **Das Raster wird ohne Kantenglättung gezeichnet, auf halbe Pixel
        # gelegt.** Eine geglättete Linie von einem Pixel Breite liegt auf zwei
        # Spalten, jede zur Hälfte gemischt: aus 1,36 Kontrast werden gemessene
        # 1,26, und die Linie sieht weich aus, wo sie scharf sein soll. Die
        # Kurven weiter unten brauchen die Glättung, das Raster nicht — es
        # besteht nur aus waagerechten und senkrechten Geraden.
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, False)
        x = math.floor(left / step) * step
        while x <= right:
            screen = self._to_screen(x, 0.0)
            painter.setPen(QPen(major if _on_multiple(x, marked, step) else minor, 1.0))
            at = math.floor(screen.x()) + 0.5
            painter.drawLine(QPointF(at, 0.0), QPointF(at, float(self.height())))
            x += step
        y = math.floor(bottom / step) * step
        while y <= top:
            screen = self._to_screen(0.0, y)
            painter.setPen(QPen(major if _on_multiple(y, marked, step) else minor, 1.0))
            at = math.floor(screen.y()) + 0.5
            painter.drawLine(QPointF(0.0, at), QPointF(float(self.width()), at))
            y += step
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
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
                text = localised(f"{x:.{digits}f}")
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
                    painter.drawText(QPointF(4.0, screen.y() - 2.0), localised(f"{y:.{digits}f}"))
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
            # Geklickt wird Anfang, Ende, Wölbung. Bis das Ende steht, zeigt
            # die Vorschau die Sehne; danach den Bogen selbst, wie er mit der
            # Wölbung unter dem Zeiger liefe — nicht den ganzen Kreis, denn
            # gemeint ist eine seiner beiden Hälften.
            if len(self._pending_world) < 2:
                painter.drawLine(self._to_screen(*first), self._to_screen(*target))
            else:
                stored = edit.arc_through(first, last, target)
                if stored is None:
                    # Drei Punkte auf einer Geraden: die Sehne ist die
                    # ehrlichste Vorschau, und der Klick wird sie ablehnen.
                    painter.drawLine(self._to_screen(*first), self._to_screen(*last))
                else:
                    self._paint_arc_preview(painter, stored)
        self._paint_snap_mark(painter)

    def _paint_arc_preview(
        self,
        painter: QPainter,
        stored: tuple[tuple[float, float], tuple[float, float], tuple[float, float]],
    ) -> None:
        """Den Bogen zeigen, der beim nächsten Klick entstünde.

        Gezeichnet wird die **Hälfte**, die die Wölbung unter dem Zeiger
        meint, nicht der ganze Kreis: Durch zwei Punkte gehen zwei Bögen, und
        eine Vorschau, die beide zeigt, beantwortet die Frage nicht, die man
        gerade stellt.

        Qt zählt seine Winkel in Sechzehntelgrad und gegen den Uhrzeigersinn
        auf dem Bildschirm — dort zeigt Y nach unten, in der Zeichnung nach
        oben. Deshalb kehren sich die Vorzeichen um.
        """
        centre, start, end = stored
        radius = math.dist(centre, start)
        if radius <= 0.0:
            return
        begin = math.degrees(math.atan2(start[1] - centre[1], start[0] - centre[0]))
        finish = math.degrees(math.atan2(end[1] - centre[1], end[0] - centre[0]))
        sweep = (finish - begin) % 360.0
        spot = self._to_screen(*centre)
        on_screen = radius * self._scale
        painter.drawArc(
            QRectF(
                spot.x() - on_screen,
                spot.y() - on_screen,
                2.0 * on_screen,
                2.0 * on_screen,
            ),
            round(begin * 16.0),
            round(sweep * 16.0),
        )

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
        from app.core import expressions

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

        # Koordinaten sind Längen und folgen der Anzeigeeinheit (§19.3); die
        # Skizze rechnet in Millimetern weiter (§11.1).
        self._across = LengthSpin(self)
        self._up = LengthSpin(self)
        for box, value in ((self._across, point[0]), (self._up, point[1])):
            box.set_range_mm(-10_000.0, 10_000.0)
            box.set_value_mm(value)
            # **Nach** dem Vorbelegen verbunden, sonst zählte das Vorbelegen
            # selbst als Eingabe.
            # Kein Lambda mit Vorgabeargument: Es hält ``self`` fest, und der
            # Ring über das Drehfeld ließ zehn von zehn ``PointDialog`` stehen.
            box.valueChanged.connect(weak_slot(self, PointDialog._note_touched, box))

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

    def _note_touched(self, box: LengthSpin) -> None:
        """Merken, dass jemand dieses Feld angefasst hat.

        Als Methode und nicht als Lambda im Aufbau: Ein Lambda mit
        Vorgabeargument fängt ``self``, hängt am Drehfeld, das ``self`` gehört,
        und schließt damit den Ring über die C++-Grenze.
        """
        self._touched.add(box)

    def point(self) -> tuple[float, float]:
        """Die eingetragene Lage — und für jedes unangetastete Feld die alte.

        Wer etwas eintippt, meint es: dann gilt seine Zahl, auf zwei Stellen,
        wie das Feld sie annimmt. Wer nichts eintippt, hat nichts gesagt, und
        dann bleibt die genaue Lage aus dem Dokument stehen.
        """
        return (
            self._across.value_mm() if self._across in self._touched else self._start[0],
            self._up.value_mm() if self._up in self._touched else self._start[1],
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

#: Die Größe, die die Zeichenfläche im Viewport-Modus behält, in Bildpunkten.
#:
#: **Sie ist gleichgültig und darf nur nicht null sein.** Der Canvas zeichnet
#: dort nicht mehr, er rechnet; Klicks kommen in Millimetern herein
#: (:meth:`SketchCanvas.place_on_plane`), und weil ``_to_screen`` und
#: ``_to_world`` exakt umkehrbar sind, kürzt sich die Größe aus beiden
#: Richtungen heraus — gemessen an 400 auf 300, 1600 auf 900 und 120 auf 4000, alle drei
#: mit demselben Ergebnis. Ein Widget ohne Bild bekommt vom Layout aber gar
#: keine Größe, und durch null teilt die Umrechnung.
VIEWPORT_CANVAS = 1000

#: Wie hoch die Bedingungsliste in der Leiste höchstens wird, in Bildpunkten.
#:
#: In der Leiste unter der Ansicht ist Höhe teuer — sie geht dem Modell ab.
#: Ganz wegzulassen wäre trotzdem falsch: Die Liste ist die Auskunft darüber,
#: was die Skizze festhält, und sie ist zusammen mit der Zeile „Bestimmt" das,
#: was eine Skizze von einem Umriss unterscheidet.
VIEWPORT_LIST_HEIGHT = 96

#: Wie viele Zeichen das Ebenenfeld zugeklappt breit ist.
#:
#: Zwanzig: „Draufsicht (XY) — l…" — der Anfang trägt die Aussage, und der
#: ganze Eintrag steht aufgeklappt da. Ohne diese Grenze macht Qt das Feld so
#: breit wie den längsten Eintrag, und das waren gemessene 612 Bildpunkte.
PLANE_FIELD_CHARS = 20

#: Wie breit ein Zahlenfeld der Werkzeugzeile höchstens wird.
#:
#: Ihr Bereich reicht bis ±1000 beziehungsweise 10 000, und danach rechnet Qt
#: die bevorzugte Breite: 199 Bildpunkte je Feld, für Werte, die im Regelfall
#: „2,00 mm" heißen. Zwei solche Felder stehen in der Werkzeugzeile.
TOOLBAR_FIELD_WIDTH = 120

#: Wie weit das Maßfeld vom Zeiger wegsteht, in Bildpunkten.
#:
#: Nicht null: Läge es unter dem Zeiger, finge es die Mausbewegungen ab, und
#: die Linie bliebe beim Ziehen stehen. Nicht viel mehr: Der Sinn des ganzen
#: Umbaus ist, dass Zahl und Zeichenspitze in **einem** Blick liegen — was
#: weiter weg steht, ist wieder die Werkzeugzeile, nur an anderer Stelle.
MEASURE_GAP = 14

#: Wie viele Bedingungsknöpfe *mindestens* in eine Zeile kommen.
#:
#: Fünf, weil die zehn zusammen 1332 Bildpunkte brauchen und ein Laptopschirm
#: sie nicht hat: Bei 1366 Fensterbreite bekam jeder Knopf 71 statt 146, bei
#: 1024 noch 36 — alle zehn Beschriftungen abgeschnitten. Zwei Zeilen à fünf
#: brauchen 754 und stehen auf jedem Schirm vollständig da.
#:
#: Wer Platz hat, bekommt mehr: :meth:`SketchPanel._fit_constraint_row` rechnet
#: die Spalten aus der tatsächlichen Breite. Auf einem bildschirmfüllenden
#: Fenster stehen alle zehn nebeneinander — zwei halbleere Zeilen sind dort
#: kein Schutz mehr, sondern nur noch eine Zeile Höhe zu viel.
CONSTRAINTS_PER_ROW = 5

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

    viewFitted = Signal(float, float, float, float)
    """Durchgereicht von der Zeichenfläche — der Rahmen stellt danach die
    Kamera. Mitte und Spannweite in Millimetern der Zeichenebene."""

    pointerMoved = Signal(float, float)
    """Wohin der nächste Klick fällt — der **gefangene** Ort, in Millimetern.

    Ebenfalls weitergereicht von der Zeichenfläche
    (``SketchCanvas.pointerChanged`` → ``pointer_target``). Die Statuszeile
    dieses Panels nennt ihn als Zahl; der Rahmen legt daraus die Marke in die
    Ansicht (``Viewport.show_sketch_cursor``). Beide lesen damit dieselbe
    Antwort — den Fang im Viewport nachzurechnen wäre die zweite Zahl für
    dieselbe Sache, und genau daran ist das Raster schon einmal
    auseinandergelaufen."""

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
        # Als Feld, damit die Breite dieser Zeile prüfbar ist: Sie ist der
        # Grund, aus dem der Skizzenbereich 1007 Bildpunkte verlangt, und eine
        # Zahl, die nur im Bild steht, lässt sich nicht rot werden lassen.
        self._tools_row = tools
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
            button.toggled.connect(weak_slot(self, SketchPanel._tool_chosen, name, forward=True))
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
            action.triggered.connect(weak_slot(self, SketchPanel._insert_made, factory))
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
        # Das Feld so breit wie sein längster Eintrag zu machen ist Qts
        # Vorgabe, und der längste ist hier „Seitenansicht (YZ) — stehend, von
        # der Seite  (3)": gemessene 612 Bildpunkte für eine Zeile, die eine
        # von drei Ansichten nennt. Mit 1129 Bildpunkten Mindestbreite ihrer
        # Zeile drückte sie alles darunter zusammen — bei 1366 Fensterbreite
        # bekamen die zehn Bedingungsknöpfe je 71 statt 146. Aufgeklappt steht
        # der ganze Eintrag weiter da; zugeklappt genügt, was hineinpasst.
        self.plane_choice.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.plane_choice.setMinimumContentsLength(PLANE_FIELD_CHARS)
        self.plane_choice.setCurrentIndex(
            max(0, self.plane_choice.findData(self.canvas.sketch.plane))
        )
        self.plane_choice.currentIndexChanged.connect(self._plane_picked)
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
        self.canvas.sketchChanged.connect(self._show_layer_note)
        plane_row.addWidget(self.layer_note, stretch=1)

        # Der Rasterfang, an derselben Zeile wie die Ebene: beides entscheidet
        # man vor dem ersten Strich, nicht mittendrin. Ein Haken und eine
        # Weite — an ist die Vorgabe, weil ein Klick sonst auf -29,75 mm
        # landet und daraus kein Maß wird, sondern Nacharbeit.
        self.snap_toggle = QCheckBox(tr("Am Raster fangen"), self)
        self.snap_toggle.setChecked(self.canvas.snapping)
        self.snap_toggle.setToolTip(
            tr("Klicks fallen auf das Raster, das im Bild steht. Vorhandene Punkte fangen vor.")
        )
        self.snap_step = LengthSpin(self)
        # Die Null ist kein Maß, sondern der Weg zurück: Wer ganz herunter
        # dreht, gibt die Weite wieder dem Zoom. Ohne sie war die Eingabe eine
        # Einbahnstraße — ``_pinned_step`` wurde gesetzt und nie gelöst, und
        # damit blieb die Weite für den Rest der Sitzung stehen, wie weit man
        # auch heraus- oder hineinzoomte (§2.1: keine Sackgassen).
        self.snap_step.set_range_mm(0.0, 100.0)
        self.snap_step.setSpecialValueText(tr("Automatisch"))
        self.snap_step.set_step_mm(0.5)
        self.snap_step.set_value_mm(self.canvas.snap_step)
        self.snap_step.setToolTip(
            tr(
                "Die Rasterweite — dieselbe Zahl, auf die ein Klick fällt. Ohne "
                "Eingabe folgt sie dem Zoom; eine eingetippte Weite bleibt stehen. "
                'Ganz herunter gedreht steht „Automatisch", und sie folgt wieder.'
            )
        )
        self.snap_step.setMaximumWidth(TOOLBAR_FIELD_WIDTH)
        self.snap_step.setAccessibleName(tr("Raster"))
        #: Ob der Nutzer die Weite selbst eingestellt hat. Solange nicht, folgt
        #: sie dem Zoom (:func:`grid_step_for`); danach steht sie. Ohne diese
        #: Unterscheidung überschriebe der nächste Zoomschritt jede Eingabe.
        self._pinned_step = False
        self.snap_toggle.toggled.connect(self._snapping_changed)
        self.snap_step.valueChanged.connect(self._step_typed)
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
        self.offset_distance = LengthSpin(self)
        self.offset_distance.set_range_mm(-1000.0, 1000.0)
        self.offset_distance.set_value_mm(2.0)
        self.offset_distance.setToolTip(tr("Um wie viel versetzt wird. Negativ ist nach innen."))
        self.offset_distance.setMaximumWidth(TOOLBAR_FIELD_WIDTH)
        # Ohne Namen liest ein Vorleser hier „Drehfeld, 2,00 mm" vor. Der
        # Name ist der des Werkzeugs, zu dem das Feld gehört.
        self.offset_distance.setAccessibleName(tr("Versetzen"))

        offset_button = QToolButton(self)
        offset_button.setIcon(icons.icon("sketch_offset", offset_button))
        offset_button.setToolTip(f"{tr('Versetzen')}  ({ACTION_KEYS['offset']})")
        offset_button.setAutoRaise(True)
        offset_button.clicked.connect(self._offset_selected)

        mirror_button = QToolButton(self)
        mirror_button.setIcon(icons.icon("sketch_mirror", mirror_button))
        mirror_button.setToolTip(tr("Spiegeln"))
        mirror_button.setPopupMode(QToolButton.ToolButtonPopupMode.InstantPopup)
        mirror_menu = QMenu(mirror_button)
        for label, axis in ((tr("An der X-Achse"), "x"), (tr("An der Y-Achse"), "y")):
            entry = mirror_menu.addAction(label)
            entry.triggered.connect(weak_slot(self, SketchPanel._mirror_selected, axis))
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

        # **Das Maß beim Zeichnen steht an der Zeichenfläche, nicht hier** (E19,
        # Schritt zwei). Es hing in dieser Zeile, und beim Zeichnen sieht
        # niemand dorthin; die Fläche besitzt es jetzt und legt es an den
        # Zeiger. Was hier bleibt, ist die Verbindung zum Setzen — das
        # Abschließen ist eine Sache des Panels, weil der Solverlauf danach
        # kommt.
        self.canvas.measure_field.editingFinished.connect(self._place_measured)

        tools.addWidget(offset_button)
        tools.addWidget(self.offset_distance)
        tools.addWidget(mirror_button)
        tools.addWidget(construction_button)
        tools.addWidget(project_button)

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
        # **Das Kürzel gehört an den Knopf**, wie bei *Einpassen* darüber: Eine
        # Belegung, zu der kein sichtbares Ziel gehört, findet niemand (§19.2).
        # Von allen Kürzeln des Skizzenmodus war dieses das einzige, das
        # nirgends an der Oberfläche stand — gemessen am gebauten Fenster.
        #
        # Der Text kommt aus **Qt** und nicht aus einer eigenen Zeichenkette:
        # ``QKeySequence`` kennt die Schreibweise der Anzeigesprache („Strg+Z"
        # gegen „Ctrl+Z"), und er kommt aus derselben Quelle wie die Bindung
        # zwei Bildschirme weiter. Ein von Hand geschriebenes „Strg+Z" wäre ein
        # fester deutscher Text in der Oberfläche (Regel 20) und liefe beim
        # nächsten Umbau von der Bindung weg.
        undo_keys = QKeySequence(QKeySequence.StandardKey.Undo).toString(
            QKeySequence.SequenceFormat.NativeText
        )
        undo_button.setToolTip(f"{tr('Rückgängig')}  ({undo_keys})")
        undo_button.setAutoRaise(True)
        undo_button.clicked.connect(self.canvas.undo)
        tools.addWidget(undo_button)

        # Zehn beschriftete Knöpfe in einer Zeile passen auf keinen
        # Laptopschirm. Gemessen an Qts eigener Rechnung: bei 1366 Bildpunkten
        # Fensterbreite bekam jeder 71 von den 146, die „Abstand  D" braucht,
        # bei 1024 noch 36 — alle zehn Beschriftungen abgeschnitten, und zwar
        # an der Stelle, an der jemand *lernen* soll, was eine Bedingung ist.
        # Fünf je Zeile brauchen zusammen 754 Bildpunkte und stehen damit auch
        # auf einem 1024er Schirm vollständig da.
        # Die Knopfreihe steckt in einem eigenen Kasten, und der gibt seine
        # Breite nicht nach oben weiter. Ohne das wüchse die Mindestbreite des
        # ganzen Bereichs mit der Zahl der Spalten: Ein Fenster, das einmal
        # breit genug für alle zehn war, ließ sich hinterher nicht mehr schmal
        # ziehen — gemessen 1007 statt 812 Bildpunkte. Was in eine Zeile passt,
        # entscheidet :meth:`_fit_constraint_row`; wie schmal das Fenster werden
        # darf, entscheiden die Zeichenfläche und die Werkzeugzeile.
        constraints_box = QWidget(self)
        constraints_box.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
        constraints_box.setMinimumWidth(1)
        constraints_row = QGridLayout(constraints_box)
        constraints_row.setContentsMargins(0, 0, 0, 0)
        self._constraints_row = constraints_row
        self._constraint_columns = CONSTRAINTS_PER_ROW
        self._constraint_buttons: dict[SketchConstraintKind, QPushButton] = {}
        for position, kind in enumerate(_NEEDS):
            key = ACTION_KEYS.get(kind, "")
            label = _constraint_label(kind)
            constraint_button = QPushButton(f"{label}  {key}" if key else label, self)
            # Der Hinweis nennt die Auswahl, nicht noch einmal den Namen: der
            # steht auf dem Knopf. Ein grauer Knopf, dessen Hinweis nur seine
            # Beschriftung wiederholt, sagt nichts über den Grund.
            constraint_button.setToolTip(
                tr("{name} — dazu {what} auswählen.").format(name=label, what=_needs_phrase(kind))
            )
            constraint_button.clicked.connect(weak_slot(self, SketchPanel.request_constraint, kind))
            self._constraint_buttons[kind] = constraint_button
            constraints_row.addWidget(
                constraint_button, position // CONSTRAINTS_PER_ROW, position % CONSTRAINTS_PER_ROW
            )
        # Die Dehnung liegt in der Spalte dahinter: sonst zieht das Gitter die
        # Knöpfe auf einem breiten Schirm auseinander, und aus zehn Knöpfen
        # würde eine Zeile aus zehn Flächen.
        constraints_row.setColumnStretch(CONSTRAINTS_PER_ROW, 1)

        self.constraint_list = QListWidget(self)
        self.constraint_list.setToolTip(tr("Entf entfernt die gewählte Bedingung."))
        # Umbruch, weil die Einträge jetzt sagen, woran sie hängen: „Deckung —
        # Linie 1 Ende, Linie 2 Anfang" ist länger als die 254 Pixel der Spalte,
        # und ein abgeschnittener Eintrag wäre schlechter als die Zahlen vorher.
        self.constraint_list.setWordWrap(True)
        # Überfahren lässt die betroffene Geometrie aufleuchten (E19). Ohne das
        # ist „Deckung (1, 2)" nicht lesbar: welche zwei Punkte das sind, weiß
        # nur, wer die flache Nummerierung im Kopf hat.
        self.constraint_list.setMouseTracking(True)
        self.constraint_list.itemEntered.connect(self._point_at)
        self.constraint_list.currentItemChanged.connect(self._point_at)

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
        self.canvas.pointerChanged.connect(self.pointerMoved)

        self._side_box = QWidget(self)
        side = QVBoxLayout(self._side_box)
        side.setContentsMargins(0, 0, 0, 0)
        # Die Überschrift gehört dem Träger, nicht der Liste: Neben der
        # Zeichenfläche steht sie hier, in der linken Spalte trägt sie der
        # einklappbare Abschnitt. Beides zugleich hieße „Bedingungen" zweimal
        # übereinander — gemessen am Bild, nicht vermutet.
        self._side_title = QLabel(tr("Bedingungen"), self._side_box)
        side.addWidget(self._side_title)
        side.addWidget(self.constraint_list, stretch=1)

        middle = QHBoxLayout()
        middle.addWidget(self.canvas, stretch=1)
        middle.addWidget(self._side_box)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addLayout(tools)
        layout.addLayout(plane_row)
        layout.addWidget(constraints_box)
        layout.addLayout(middle, stretch=1)
        status_row = QHBoxLayout()
        status_row.addWidget(self.status, stretch=1)
        status_row.addWidget(self.coordinates)
        layout.addLayout(status_row)

        self.canvas.sketchChanged.connect(self.sketchChanged)
        self.canvas.viewFitted.connect(self.viewFitted)
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

    def resizeEvent(self, event: Any) -> None:  # noqa: N802 - Qt gibt den Namen
        super().resizeEvent(event)
        self._fit_constraint_row()

    def _fit_constraint_row(self) -> None:
        """So viele Bedingungsknöpfe nebeneinander, wie die Breite hergibt.

        Die feste Aufteilung in zwei Zeilen à fünf war für den kleinen Schirm
        gedacht (:data:`CONSTRAINTS_PER_ROW`) und blieb auch dort stehen, wo
        Platz für alle zehn war: Auf einem bildschirmfüllenden Fenster standen
        fünf Knöpfe in einer Zeile, fünf in der nächsten, und daneben eineinhalb
        Meter Leerraum.

        Gerechnet wird mit dem breitesten Knopf und nicht mit der Summe: Die
        Beschriftungen sind unterschiedlich lang, und wer mit dem Mittel rechnet,
        bekommt eine Spaltenzahl, bei der das längste Wort abgeschnitten wird —
        genau der Fehler, gegen den die feste Aufteilung einmal angetreten ist.
        Die Schätzung fällt damit zu klein aus statt zu groß, und das ist die
        Richtung, in der ein Fehler hier nichts kostet.

        Eine Untergrenze gibt es nicht: Ist das Fenster so schmal, dass nur drei
        nebeneinander passen, sind es eben vier Zeilen. Fünf abgeschnittene
        Knöpfe wären das schlechtere von beidem.
        """
        buttons = list(self._constraint_buttons.values())
        if not buttons:
            return
        widest = max(button.sizeHint().width() for button in buttons)
        gap = max(self._constraints_row.horizontalSpacing(), 0)
        fitting = (self.width() + gap) // (widest + gap)
        columns = max(min(int(fitting), len(buttons)), 1)
        if columns == self._constraint_columns:
            return
        self._constraints_row.setColumnStretch(self._constraint_columns, 0)
        for position, button in enumerate(buttons):
            self._constraints_row.removeWidget(button)
            self._constraints_row.addWidget(button, position // columns, position % columns)
        self._constraints_row.setColumnStretch(columns, 1)
        self._constraint_columns = columns

    def set_surroundings(self, surroundings: Surroundings) -> None:
        """Bauraum, Zeichenebenen und Projektionsvorlagen auf einmal setzen."""
        self.set_bed(surroundings.bed)
        self.offer_faces(surroundings.faces)
        self.offer_bodies(surroundings.bodies)

    def use_viewport(self) -> None:
        """Die Zeichenfläche gibt ihr Bild an die Ansicht ab (§30.1, P4).

        Danach ist dieses Panel eine **Leiste**: Werkzeuge, Ebene,
        Bedingungen und Statuszeile bleiben, gezeichnet wird im Viewport. Die
        Skizze liegt dann dort, wo sie liegt — auf ihrer Ebene, im Raum —
        statt auf einem Blatt, das die Ansicht verdeckt.

        **Der Canvas bleibt und rechnet weiter.** Er trägt Fang, Treffertest,
        Vorschau, Bedingungen und den Undo-Punkt; nur sein Bild wird nicht
        mehr gebraucht. Die Klicks kommen über :meth:`SketchCanvas.place_on_plane`
        in Millimetern herein, und weil ``_to_screen`` und ``_to_world`` exakt
        umkehrbar sind, ist seine Größe dabei gleichgültig — sie kürzt sich
        heraus. Eine feste Größe steht trotzdem, damit sie nicht null wird:
        Ein Widget ohne Bild bekommt vom Layout keine.

        Die Bedingungsliste bleibt sichtbar, aber niedrig. Sie ist die
        Auskunft darüber, was die Skizze festhält, und ohne sie wäre der
        Wechsel in den Raum ein Verlust an anderer Stelle — die Zeile
        „Bestimmt" und die Liste dazu sind das, was eine Skizze von einem
        Umriss unterscheidet.
        """
        self.canvas.setVisible(False)
        self.canvas.resize(VIEWPORT_CANVAS, VIEWPORT_CANVAS)
        # **Die Ziffern müssen im ganzen Fenster gelten, nicht nur hier
        # drinnen.** Sie lagen an ``WidgetWithChildrenShortcut``, und das war
        # richtig, solange dieses Panel die Ansicht *war*: Der Fokus lag dann
        # in ihm. Jetzt liegt er im Viewport — wer dort zeichnet und die 2
        # drückt, meint die Vorderansicht, und ein Kürzel, das nur im
        # unsichtbaren Zeichenbereich feuert, feuert nie.
        #
        # Der Konflikt mit *Ansicht → Darstellung* bleibt damit ausgeschlossen:
        # Deren Einträge sind im Skizzenmodus ausgegraut, und ein gesperrtes
        # Kürzel nimmt keiner Taste den Weg.
        for shortcut in self._plane_shortcuts:
            shortcut.setContext(Qt.ShortcutContext.WindowShortcut)

    def take_constraint_list(self) -> QWidget:
        """Gibt die Bedingungsliste ab — samt ihrer Überschrift.

        Sie zieht im Viewport-Modus in die linke Spalte, zu Objekten,
        Parametern und Verlauf. **Der Grund ist Höhe:** Gemessen nahm die
        Leiste 334 von 900 Bildpunkten, also 37 Prozent des Fensters, und
        allein 96 davon gingen an diese Liste plus ihre Überschrift. Gezeichnet
        wurde damit zur Hälfte hinter der eigenen Bedienung.

        Links ist sie außerdem am richtigen Ort: Dort steht schon, **was das
        Dokument festhält** — Objekte, Parameter, Verlauf. Was die Skizze
        festhält, gehört in dieselbe Spalte und nicht in die Werkzeugleiste.

        Zurückgegeben wird der Träger mit Überschrift und Liste, nicht die
        Liste allein: Wer sie einhängt, soll nicht auch noch wissen müssen,
        dass ein Wort darüber gehört.

        **Nur aus dem Layout, nicht elternlos.** ``setParent(None)`` macht ein
        Kind-Widget zum eigenen Fenster, und ``WindowShortcut`` löst danach
        gegen das falsche auf: Die Ziffern für die Ebene kamen nicht mehr an
        (gemessen — ``plane:xy`` statt ``plane:xz``). Wer sie einhängt, setzt
        den neuen Elternteil ohnehin; dazwischen bleibt sie, wo sie war.
        """
        parent = self._side_box.parentWidget()
        layout = parent.layout() if parent is not None else None
        if layout is not None:
            layout.removeWidget(self._side_box)
        self._side_title.hide()
        return self._side_box

    def _install_shortcuts(self) -> None:
        """Die Zeichenkürzel, solange dieses Panel den Fokus hat (E16).

        ``WidgetWithChildrenShortcut`` ist der Kontext, der aus einer Belegung
        eine **kontextabhängige** macht: außerhalb des Skizzenmodus liegen R
        und C auf Drehen und Fasen, hier auf Rechteck und Kreis. Genau so macht
        es Fusion, und anders lassen sich die beiden Sätze nicht
        widerspruchsfrei halten.
        """
        for name, key in TOOL_KEYS.items():
            if key == "Esc":
                # **Escape bindet hier nicht.** Das Fenster hat dieselbe Taste
                # („die Skizze verlassen"), und Qt entscheidet die
                # Mehrdeutigkeit, bevor irgendein Code von uns läuft: Es meldet
                # ``activatedAmbiguously`` und führt **keines** von beiden aus.
                # Gemessen im offenen Skizzenmodus — Escape tat nichts, weder
                # Werkzeug ablegen noch Skizze schließen, und das ist die Taste,
                # nach der jeder als Erstes greift.
                #
                # Beides tut jetzt ``MainWindow._escape`` in zwei Stufen, über
                # :meth:`drop_tool`. Der Eintrag bleibt in ``TOOL_KEYS``, weil
                # er die Taste am Knopf anschreibt — sie stimmt, nur der Weg
                # dahin führt über das Fenster.
                continue
            shortcut = QShortcut(QKeySequence(key), self)
            shortcut.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            shortcut.activated.connect(weak_slot(self, SketchPanel.choose_tool, name))

        rectangle = QShortcut(QKeySequence(ACTION_KEYS["rectangle"]), self)
        rectangle.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        rectangle.activated.connect(self._insert_rectangle)

        measure = QShortcut(QKeySequence(ACTION_KEYS["distance"]), self)
        measure.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        measure.activated.connect(self._request_distance)

        offsetting = QShortcut(QKeySequence(ACTION_KEYS["offset"]), self)
        offsetting.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        offsetting.activated.connect(self._offset_selected)

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

        self._plane_shortcuts: list[QShortcut] = []
        for plane, key in PLANE_KEYS.items():
            view = QShortcut(QKeySequence(key), self)
            view.setContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
            view.activated.connect(weak_slot(self, SketchPanel._plane_by_key, plane))
            self._plane_shortcuts.append(view)

    def _plane_by_key(self, plane: str) -> None:
        """Ein Tastendruck wählt die Ebene; ob es ging, interessiert hier nicht.

        Die Ziffern liegen auf den drei Grundebenen, und die stehen immer zur
        Wahl — der Rückgabewert von :meth:`choose_plane` gilt dem Weg über
        eine angeklickte Fläche, die der Körper auch verloren haben kann.

        Ein eigener Slot und kein Rückgabewert an ``weak_slot`` vorbei: Es
        nimmt ``Callable[..., None]``, und das ist richtig so — ein Signal hat
        keinen Empfänger für ein Ergebnis. Die Alternative wäre gewesen,
        ``leash.py`` breiter zu typisieren, damit hier eine Zahl im Nichts
        verschwinden darf.
        """
        self.choose_plane(plane)

    def choose_plane(self, plane: str) -> bool:
        """Die Zeichenebene wechseln — über die Wahl, nicht an ihr vorbei.

        Die Zeichenfläche direkt zu setzen ließe das Auswahlfeld auf der
        vorigen Ebene stehen, und dann behaupten zwei Stellen zweierlei.

        **Gibt zurück, ob die Ebene überhaupt zur Wahl stand.** Für die drei
        Grundebenen ist das immer so; eine Fläche steht nur im Feld, solange
        der Körper sie hat (:meth:`offer_faces`). Vorher endete der Aufruf
        dort still, und für die Ziffern 1 bis 3 war das folgenlos — sie
        treffen immer.

        Für den Weg „Fläche anklicken, dann darauf zeichnen" wäre es die
        schlechteste Antwort: Wer auf eine Deckfläche zeigt und danach
        unbemerkt auf der Grundebene zeichnet, merkt es am Ergebnis und sucht
        den Fehler in seiner Zeichnung. Der Aufrufer bekommt jetzt die
        Auskunft und kann es sagen (Regel 17).
        """
        index = self.plane_choice.findData(plane)
        if index < 0:
            return False
        self.plane_choice.setCurrentIndex(index)
        return True

    def drop_tool(self) -> bool:
        """Legt ein laufendes Zeichenwerkzeug ab. ``True``, wenn eines lief.

        Die erste Stufe von Escape: Wer eine Linie zieht und aussteigen will,
        meint das Werkzeug und nicht die ganze Skizze. Lief keines, gibt diese
        Methode ``False`` zurück, und das Fenster verlässt die Skizze — die
        zweite Stufe.
        """
        if self.canvas.tool == "select":
            return False
        self.choose_tool("select")
        return True

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

    def _insert_made(self, make: Callable[[], Sketch]) -> None:
        """Eine Form aus dem Formenmenü einfügen.

        Der Ring lief hier über **drei** Ebenen — Panel → Knopf → Menü →
        Aktion → Rückruf → Panel —, und deshalb hat ihn die statische Suche
        nicht gesehen: Sie prüfte, ob der Sender ein Kind von ``self`` ist, und
        ``action`` ist das Kind eines Menüs, das einem Knopf gehört.
        """
        self.canvas.insert_shape(make())

    def _mirror_selected(self, axis: str) -> None:
        """Das Gewählte an einer Achse spiegeln — derselbe Weg über ein Menü."""
        self.canvas.mirror_selected(axis)

    def _plane_picked(self) -> None:
        """Die Zeichenebene, die im Auswahlfeld steht.

        Als Methode und nicht als Lambda am eigenen Auswahlfeld: Qt hält eine
        gebundene Methode schwach, ein Lambda hielte dieses Feld an seinem
        eigenen Kind fest (`.claude/rules/oberflaeche.md`).
        """
        self.canvas.set_plane(str(self.plane_choice.currentData()))

    def _show_layer_note(self) -> None:
        """Der Satz über der Zeichenfläche, wenn sich die Skizze geändert hat."""
        self.layer_note.setText(self.canvas.layer_note())

    def _offset_selected(self) -> None:
        """Das Gewählte um den eingestellten Abstand versetzen.

        Zwei Auslöser, ein Weg: der Knopf in der Werkzeugzeile und das Kürzel.
        Vorher stand derselbe Ausdruck zweimal als Lambda da.
        """
        self.canvas.offset_selected(self.offset_distance.value_mm())

    def _place_measured(self) -> None:
        """Das eingetippte Maß an die Bedingung legen, die darauf wartet.

        Das Feld gehört seit Schritt zwei der Zeichenfläche; das Abschließen
        bleibt hier, weil danach der Solverlauf und die Liste der Bedingungen
        nachziehen — beides Sachen des Panels.
        """
        self.canvas.place_measured(self.canvas.measure_field.value_mm())

    def _insert_rectangle(self) -> None:
        """Das Rechteck des Kürzels — vierzig auf zwanzig, wie die Zeichenfläche
        es als Vorgabe kennt."""
        self.canvas.insert_shape(shapes.rectangle(40.0, 20.0))

    def _request_distance(self) -> None:
        """Das Kürzel für die häufigste Bedingung: ein Maß zwischen zwei Punkten."""
        self.request_constraint("distance")

    def _snapping_changed(self) -> None:
        """Haken und Weite an die Zeichenfläche geben.

        Das Feld wird mit dem Haken bedienbar: eine Weite einzustellen, die
        nichts tut, sieht aus wie eine Einstellung, die nicht wirkt.
        """
        active = self.snap_toggle.isChecked()
        self.snap_step.setEnabled(active)
        self.canvas.set_snapping(active, self.snap_step.value_mm())
        # **Und das Bild muss es erfahren.** ``set_snapping`` zeichnet den
        # Canvas neu, und der ist im Viewport-Modus unsichtbar — gemeldet als
        # „wenn ich das Raster anpasse ändert es sich im Viewport nicht". Das
        # Raster in der Szene hängt an ``MainWindow._redraw_sketch``, und das
        # hängt an diesem Signal; ohne es blieb die alte Weite stehen, während
        # Feld und Fang längst die neue trugen. Drei Zahlen für dieselbe Sache,
        # und die sichtbare war wieder die falsche.
        #
        # ``sketchChanged`` und kein eigenes: Das Signal heißt der Sache nach
        # „die Ansicht muss nachziehen", und die Rasterweite ist Teil dessen,
        # was dort gezeichnet wird. Ein zweites daneben hieße, dass jede
        # Empfangsstelle künftig beide verbinden muss, um vollständig zu sein.
        self.sketchChanged.emit()

    def _step_typed(self) -> None:
        """Eine eingetippte Weite bleibt stehen, auch beim Zoomen.

        **Und die Null gibt sie wieder her.** Sie steht im Feld als
        „Automatisch" und ist der einzige Weg zurück: Vorher wurde
        ``_pinned_step`` gesetzt und nie gelöst, wer also einmal eine Weite
        eintippte, sah bis zum Verlassen des Modus kein mitwachsendes Raster
        mehr — herausgezoomt eine Fläche aus Linien, hineingezoomt vier Linien
        im Bild. Beim nächsten Neuzeichnen trägt ``follow_grid`` die Weite des
        Maßstabs wieder ein.
        """
        getippt = self.snap_step.value_mm()
        # Zwischen null und der feinsten Weite liegt nichts Brauchbares: Die
        # Null heißt „Automatisch", und 0,01 mm wäre ein Fang, den kein
        # Drucker auflöst. Angehoben statt abgelehnt — ein Feld, das eine
        # Eingabe verschluckt, sagt nicht, dass es sie verschluckt hat.
        if 0.0 < getippt < LEAST_SNAP_MM:
            with QSignalBlocker(self.snap_step):
                self.snap_step.set_value_mm(LEAST_SNAP_MM)
            getippt = LEAST_SNAP_MM
        self._pinned_step = getippt > 0.0
        self._snapping_changed()

    def follow_grid(self, step: float) -> None:
        """Die Rasterweite übernehmen — als Fangweite und als Anzeige.

        **Der Fang ist das Raster, und zwar dasselbe, das im Bild steht.**
        Vorher waren es zwei Zahlen: gezeichnet wurden 5 mm, gefangen wurde
        auf 1 mm, und vier von vier Klicks landeten zwischen zwei sichtbaren
        Linien. Das Kästchen heißt „Am Raster fangen" und hat damit etwas
        versprochen, das nicht eintrat.

        Wer eine Weite eintippt, behält sie (``_pinned_step``) — dann folgt
        umgekehrt das **Raster** ihr, und die beiden bleiben trotzdem eine
        Zahl. Ohne Eingabe folgen beide dem Zoom, damit das Raster lesbar
        bleibt.

        Das Signal wird dabei angehalten: ``setValue`` löst ``valueChanged``
        aus, und das hieße hier „der Nutzer hat etwas eingetippt" — der erste
        Zoomschritt hätte die Weite für immer festgenagelt.
        """
        if self._pinned_step or step <= 0.0:
            return
        with QSignalBlocker(self.snap_step):
            self.snap_step.set_value_mm(step)
        self.canvas.set_snapping(self.snap_toggle.isChecked(), step)

    def snap_is_pinned(self) -> bool:
        """Ob die Weite von Hand steht — für Tests und für die Zeile."""
        return self._pinned_step

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
            # **Woran sie hängt, in Worten.** Hier stand die rohe
            # Punktnummerierung — „Deckung  (1, 2)" —, und die ist die flache
            # Liste der Skizze: Elemente der Reihe nach, Punkte je Element der
            # Reihe nach. Lesbar war sie für niemanden, der sie nicht im Kopf
            # hat; das Aufleuchten beim Überfahren (E19) half nur dem, der die
            # Maus schon dort hatte. Die Nummern stehen weiter im Tooltip: wer
            # eine Bedingung aus einer Fehlermeldung des Solvers sucht, sucht
            # nach ihnen.
            where = targets_phrase(self.canvas.sketch, entry.targets)
            text = f"{label} — {where}" if where else label
            numbers = ", ".join(str(target) for target in entry.targets)
            if index in conflict:
                # Das Zeichen trägt die Aussage, die Farbe verstärkt sie nur
                # (Regel 18) — und die Liste ist einfarbig, sobald jemand sie
                # ausdruckt.
                text = f"{CONFLICT_MARKER} {text}"
            item = QListWidgetItem(text)
            item.setData(Qt.ItemDataRole.UserRole, entry.targets)
            item.setToolTip(f"{text}  ({numbers})")
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
