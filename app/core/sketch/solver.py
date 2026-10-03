"""Der 2D-Solver für Skizzen (Bauplan §30.1).

Kleinste Quadrate auf scipy — BSD und bereits in der Freigabeliste; SolveSpace
und py-slvs sind GPL und darum keine Option (Regel 15). Deterministisch: der
Startzustand sind die Punkte der Skizze selbst — oder, im Zugmodus
(``dragged``, ``start``), der zuletzt gelöste Stand mit den gezogenen Punkten
am Zeiger —, Zufall kommt nicht vor, und derselbe Aufruf liefert dieselbe
Lösung (Regel 9 greift nicht — es gibt keinen Startwert, weil es keine
Streuung gibt).

Jede Bedingung bringt ihre Residuen **und ihre analytische Ableitung** mit.
Das ist kein Luxus: mit numerischer Differenzenbildung kostet die Jacobimatrix
eine Funktionsauswertung je Variable und verfehlt das Budget aus §31 um eine
Größenordnung — und ihre Näherungsfehler verschmieren die Ranganalyse, an der
die Erkennung überbestimmter Skizzen hängt.

Unterbestimmt ist kein Fehler: die verbleibenden Freiheitsgrade stehen im
Ergebnis, ein Befund daraus wird erst auf Op-Ebene. Überbestimmt oder
widersprüchlich hält an und nennt das kollidierende Bedingungspaar
(Regel 17, §30.1).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Final

import numpy as np

from app.core.deferred import csr_matrix, least_squares
from app.core.errors import SketchConflictError, ValidationError
from app.core.expressions import evaluate
from app.core.types import Point2, Sketch, SketchConstraint, SketchElement, SolvedSketch
from app.core.units import EPS_GEOM
from app.i18n import _

#: Restfehler, ab dem eine Lösung als widersprüchlich gilt. Konsistente Systeme
#: konvergieren um Größenordnungen tiefer; die Lücke dazwischen ist die Antwort.
_TOL: Final[float] = EPS_GEOM

#: Wie viele Punkte ein Element je ``kind`` trägt (§9).
#:
#: Eine Ellipse führt Mitte, das Ende der ersten und das Ende der zweiten
#: Achse; ein Ellipsenbogen dazu Anfang und Ende (RM-188 P6.6a). Sechs
#: beziehungsweise zehn Koordinaten für fünf beziehungsweise sieben echte
#: Freiheitsgrade — den Unterschied tragen die eigenen Gleichungen
#: (:func:`_element_equations`), nicht eine zweite Sorte Variable.
_ELEMENT_POINTS: Final[dict[str, int]] = {
    "point": 1,
    "line": 2,
    "circle": 2,
    "arc": 3,
    "ellipse": 3,
    "elliptical_arc": 5,
}

#: Arten ohne feste Punktzahl, mit ihrem Mindestmaß. Ein Spline läuft durch so
#: viele Punkte, wie jemand gesetzt hat — unter zweien ist er ein Punkt.
_ELEMENT_MINIMUM: Final[dict[str, int]] = {"spline": 2}

#: Wie viele Zielpunkte eine Bedingung je ``kind`` nimmt.
_CONSTRAINT_TARGETS: Final[dict[str, int]] = {
    "distance": 2,
    "radius": 2,
    "diameter": 2,
    "coincident": 2,
    "horizontal": 2,
    "vertical": 2,
    "parallel": 4,
    "perpendicular": 4,
    "tangent": 4,
    "symmetric": 4,
    "fixed": 1,
    "reference": 2,
    "angle": 4,
    # **Eine Art für zwei Fälle.** „Gleich lang" und „gleicher Radius" sind
    # dieselbe Gleichung: Eine Linie führt Anfang und Ende, ein Kreis Mitte
    # und Randpunkt, ein Bogen Mitte und Anfang — in allen drei Fällen ist das
    # Maß der Abstand zweier Punkte. Eine zweite Art ``equal_radius`` wäre ein
    # zweiter Name für dieselbe Zeile und ein zweiter Eintrag im Dateiformat;
    # welche Elemente gemeint sind, entscheidet die Auswahl in der Oberfläche
    # und nicht das Datenmodell.
    "equal": 4,
    "midpoint": 3,
    # **Kurven werden über ihren ersten Punkt genannt** (RM-188 P6.6b). Ein
    # Ziel, das eine Kurve meint, ist der flache Index des ersten Punkts ihres
    # Elements — bei jeder Art einer ihrer Punkte, bei Kreis und Ellipse die
    # Mitte, bei Linie und Spline der Anfang. Welche Kurve das ist, sagt das
    # Element, zu dem der Punkt gehört; so bleibt die Zielzahl fest, auch für
    # einen Spline mit beliebig vielen Punkten. ``on_curve``: (Punkt, Kurve).
    "on_curve": 2,
    # ``smooth`` und ``curvature``: (Punkt an A, Kurve A, Punkt an B, Kurve B)
    # — je Kurve die Stelle, an der sie gelesen wird. An einem gemeinsamen
    # Punkt ist das zweimal derselbe; zwei Splines, die sich an ihren Enden
    # treffen, haben zwei verschiedene, deckungsgleiche Punkte.
    "smooth": 4,
    "curvature": 4,
}

#: Die Elementarten, auf die eine Kurvenbedingung zeigen darf.
_CURVE_KINDS: Final[frozenset[str]] = frozenset(
    {"line", "circle", "arc", "ellipse", "elliptical_arc", "spline"}
)

#: Die Bedingungen, deren Ziele Kurven nennen — und an welcher Stelle der
#: Ziele (``edit`` braucht das, wenn ein Spline Punkte gewinnt oder verliert:
#: Ein Kurvenziel bleibt, ein Punktziel fällt mit seinem Punkt).
CURVE_SLOTS: Final[dict[str, tuple[int, ...]]] = {
    "on_curve": (1,),
    "smooth": (1, 3),
    "curvature": (1, 3),
}

#: Bedingungen, die nichts festlegen. Sie werden geprüft wie jede andere —
#: falsche Zielzahl bleibt ein Fehler — aber sie kommen nie ins
#: Gleichungssystem: ein Referenzmaß misst (§30.1).
_MEASURING_ONLY: Final[frozenset[str]] = frozenset({"reference"})

#: Bedingungen mit Zahl — und womit die Zahl in einen Abstand umgerechnet wird.
#:
#: **Der Kunde denkt in Durchmesser, der Kreis maß Radius.** Ein Kreis wird über
#: Mittelpunkt und Randpunkt bemaßt; bis hierher war das eine ``distance`` und
#: hieß in der Oberfläche „Abstand". Wer für eine M3-Bohrung 3,2 tippte, bekam
#: ein Loch mit **6,4 mm** — und nichts an der Bedienung sagte ihm, dass er
#: einen Radius eingibt. Beide Arten rechnen dieselbe Gleichung; sie
#: unterscheiden sich in einem Faktor und darin, was sie **heißen**.
_LENGTH_FACTOR: Final[dict[str, float]] = {
    "distance": 1.0,
    "radius": 1.0,
    "diameter": 0.5,
}

#: Bedingungen, deren Zahl ein **Winkel in Grad** ist und kein Abstand.
#:
#: Getrennt von :data:`_LENGTH_FACTOR`, weil hier nicht skaliert, sondern die
#: Einheit gewechselt wird: Der Kunde tippt Grad (§11 gilt den Längen), die
#: Gleichung rechnet im Bogenmaß.
_ANGLE_KINDS: Final[frozenset[str]] = frozenset({"angle"})

#: Der größte Winkel, den ein Winkelmaß annimmt.
#:
#: Nicht 360: Die Gleichung ist ``sin(φ - θ)`` und hat die Periode 180° — ein
#: Maß von 200° wäre dieselbe Bedingung wie 20° und hieße trotzdem anders.
#: Beide Ränder sind ausgeschlossen, denn dort steht ``parallel``, und zwei
#: Namen für dieselbe Bedingung sind eine Gelegenheit, sie doppelt zu legen.
MOST_ANGLE_DEGREES: Final[float] = 180.0

_ResidualFn = Callable[[np.ndarray], tuple[float, ...]]
_GradientFn = Callable[[np.ndarray, np.ndarray], None]
"""Schreibt die Zeilen einer Gleichung in die übergebene Jacobimatrix.

Erster Parameter sind die Punkte ``(n, 2)``, zweiter die Zeilen dieser
Gleichung als Sicht auf die Matrix ``(rows, n, 2)`` — addiert wird an
``[zeile, punkt, koordinate]``, die Sicht beginnt bei null."""


@dataclass(frozen=True, slots=True)
class _Equation:
    """Eine Gleichungsgruppe: ihr Ursprung, ihre Residuen, ihre Ableitung.

    ``constraint`` ist der Index in ``sketch.constraints`` — oder ``None`` für
    die implizite Bedingung eines Bogens (beide Schenkel gleich lang)."""

    constraint: int | None
    rows: int
    fn: _ResidualFn
    grad: _GradientFn


#: Wie zäh ein gezogener Punkt im **weichen** Zug ist, als Maßstab seiner
#: Koordinaten (``x_scale`` in scipy — die Rechnung läuft in ``x / scale``).
#:
#: Der weiche Zug kommt nur zum Zug, wenn der harte nicht geht: Der gezogene
#: Punkt soll dann so nah wie möglich am Zeiger bleiben, und die übrigen
#: Punkte nehmen die Bewegung auf. Ein Zwanzigstel heißt: Ihn um einen
#: Millimeter zu verrücken kostet den Löser so viel wie zwanzig Millimeter an
#: jedem anderen — die Zahl, mit der SolveSpace seine gezogenen Parameter
#: gewichtet, und gemessen genügt sie: Wo die Bedingungen einen Weg lassen,
#: bleibt der Punkt am Zeiger; wo sie ihn festhalten, kehrt er zurück, ohne
#: die Nachbarn mitzunehmen.
DRAG_STIFFNESS: Final[float] = 1.0 / 20.0

#: Wie viele Auswertungen die **erste** Zugstufe höchstens bekommt.
#:
#: Ist der Zeigerort erreichbar, findet der Löser ihn schnell: gemessen fünf
#: bis zwölf Auswertungen, vom Rechteck über Vieleck, Lochkreis und Lochraster
#: bis zur Kette aus hundert Linien. Ist er es nicht, suchte der Löser ohne
#: Grenze weiter, bis sich der Rest nicht mehr änderte — und das kostete an
#: einer gestreckten Kette aus zwanzig Linien 646 Auswertungen und 2,7
#: Sekunden, aus hundert Linien 103 Sekunden, **je Mausereignis** (Durchsicht
#: 22.09.2026). Nach fünfundzwanzig ist die Antwort „nicht erreichbar", und
#: die zweite Stufe übernimmt — das Doppelte des größten gemessenen Bedarfs.
DRAG_REACH_TRIES: Final = 25

#: Wie viele Auswertungen die **zweite** Zugstufe höchstens bekommt.
#:
#: Sie rutscht so weit, wie die Bedingungen es erlauben, und braucht dafür an
#: gewöhnlichen Zeichnungen gemessen vier bis acht Auswertungen — ein
#: festes Vieleck, ein bemaßtes Langloch, ein Lochkreis, ein verrundetes
#: Rechteck. Nur eine bis zum Anschlag gestreckte Kette braucht an die
#: hundert, weil sie dort singulär steht. Findet die Stufe in dieser Zahl
#: keine Lage, bleibt die Zeichnung, wo sie war: Ein Zug, der nicht folgt,
#: ist eine Auskunft (die Zeile sagt, was hält); ein Zug, der das Fenster für
#: Sekunden anhält, ist keine.
DRAG_SLIDE_TRIES: Final = 50

#: So groß darf die **dichte** Jacobimatrix werden, die die Rangprüfung nach
#: dem Lösen braucht (Zeilen mal 2 Punkte mal 8 Byte). 256 MiB sind rund 4000
#: Bedingungen über 4000 Punkten — das Zwanzigfache des §31-Korpus. Eine
#: Projektdatei bringt ihre Skizze als **einen** Text mit, und weder
#: Skizzenleser noch Projektdeckel zählen darin Punkte: 10 000 Punkte mit
#: 10 000 Fixierungen sind 958 KB Datei und forderten hier 3,2 GB an, bevor
#: eine Zeile gerechnet war (Gesamtreview 05.09.2026, G-09). Der Löser selbst
#: rechnet seither dünn besetzt (:class:`_SparseRows`); die Grenze gilt dem,
#: was danach dicht bleiben muss.
MAX_JACOBIAN_BYTES: Final = 256 * 1024 * 1024


class _SparseRows:
    """Nimmt die Ableitungen einer Gleichung entgegen wie der dichte Block
    ``out[zeile, punkt, koordinate]`` — und legt nur ab, was gesetzt wird.

    Jede Ableitung berührt zwei bis vier Punkte; die dichte Matrix trug
    trotzdem jeden. Die Gleichungen schreiben unverändert
    ``out[0, b, 0] += ux`` — hier landet das als Eintrag, aus dem
    :meth:`_solve` die ``csr_matrix`` direkt baut.
    """

    __slots__ = ("entries", "offset")

    def __init__(self, offset: int) -> None:
        self.entries: dict[tuple[int, int, int], float] = {}
        self.offset = offset

    def __getitem__(self, key: tuple[int, int, int]) -> float:
        return self.entries.get(key, 0.0)

    def __setitem__(self, key: tuple[int, int, int], value: float) -> None:
        self.entries[key] = float(value)


def _unit(points: np.ndarray, tail: int, head: int) -> tuple[float, float, float]:
    """Einheitsrichtung von ``tail`` nach ``head`` und die echte Länge,
    gegen Länge null gesichert."""
    dx = float(points[head][0] - points[tail][0])
    dy = float(points[head][1] - points[tail][1])
    length = max(float(np.hypot(dx, dy)), EPS_GEOM)
    return dx / length, dy / length, length


def _span(points: np.ndarray, tail: int, head: int) -> float:
    return float(np.hypot(points[head][0] - points[tail][0], points[head][1] - points[tail][1]))


def _project(points: np.ndarray, tail: int, head: int, gx: float, gy: float) -> tuple[float, float]:
    """Gradient eines Ausdrucks in der Einheitsrichtung, zurückgeholt auf die
    rohe Differenz: ``(I - ûûᵀ)/L`` angewandt auf ``(gx, gy)``."""
    ux, uy, length = _unit(points, tail, head)
    dot = ux * gx + uy * gy
    return (gx - ux * dot) / length, (gy - uy * dot) / length


def _distance_equation(a: int, b: int, length: float) -> tuple[_ResidualFn, _GradientFn]:
    def fn(pts: np.ndarray) -> tuple[float, ...]:
        return (_span(pts, a, b) - length,)

    def grad(pts: np.ndarray, out: np.ndarray) -> None:
        ux, uy, _ = _unit(pts, a, b)
        out[0, b, 0] += ux
        out[0, b, 1] += uy
        out[0, a, 0] -= ux
        out[0, a, 1] -= uy

    return fn, grad


def _coincident_equation(a: int, b: int) -> tuple[_ResidualFn, _GradientFn]:
    def fn(pts: np.ndarray) -> tuple[float, ...]:
        return (float(pts[b][0] - pts[a][0]), float(pts[b][1] - pts[a][1]))

    def grad(pts: np.ndarray, out: np.ndarray) -> None:
        out[0, b, 0] += 1.0
        out[0, a, 0] -= 1.0
        out[1, b, 1] += 1.0
        out[1, a, 1] -= 1.0

    return fn, grad


def _axis_equation(a: int, b: int, axis: int) -> tuple[_ResidualFn, _GradientFn]:
    """``horizontal`` gleicht die y-Koordinaten an (axis 1), ``vertical`` die x."""

    def fn(pts: np.ndarray) -> tuple[float, ...]:
        return (float(pts[b][axis] - pts[a][axis]),)

    def grad(pts: np.ndarray, out: np.ndarray) -> None:
        out[0, b, axis] += 1.0
        out[0, a, axis] -= 1.0

    return fn, grad


def _parallel_equation(a: int, b: int, c: int, d: int) -> tuple[_ResidualFn, _GradientFn]:
    def fn(pts: np.ndarray) -> tuple[float, ...]:
        ux, uy, _ = _unit(pts, a, b)
        vx, vy, _ = _unit(pts, c, d)
        return (ux * vy - uy * vx,)

    def grad(pts: np.ndarray, out: np.ndarray) -> None:
        ux, uy, _ = _unit(pts, a, b)
        vx, vy, _ = _unit(pts, c, d)
        gux, guy = _project(pts, a, b, vy, -vx)
        gvx, gvy = _project(pts, c, d, -uy, ux)
        out[0, b, 0] += gux
        out[0, b, 1] += guy
        out[0, a, 0] -= gux
        out[0, a, 1] -= guy
        out[0, d, 0] += gvx
        out[0, d, 1] += gvy
        out[0, c, 0] -= gvx
        out[0, c, 1] -= gvy

    return fn, grad


def _perpendicular_equation(a: int, b: int, c: int, d: int) -> tuple[_ResidualFn, _GradientFn]:
    def fn(pts: np.ndarray) -> tuple[float, ...]:
        ux, uy, _ = _unit(pts, a, b)
        vx, vy, _ = _unit(pts, c, d)
        return (ux * vx + uy * vy,)

    def grad(pts: np.ndarray, out: np.ndarray) -> None:
        ux, uy, _ = _unit(pts, a, b)
        vx, vy, _ = _unit(pts, c, d)
        gux, guy = _project(pts, a, b, vx, vy)
        gvx, gvy = _project(pts, c, d, ux, uy)
        out[0, b, 0] += gux
        out[0, b, 1] += guy
        out[0, a, 0] -= gux
        out[0, a, 1] -= guy
        out[0, d, 0] += gvx
        out[0, d, 1] += gvy
        out[0, c, 0] -= gvx
        out[0, c, 1] -= gvy

    return fn, grad


def _angle_equation(
    a: int, b: int, c: int, d: int, radians: float
) -> tuple[_ResidualFn, _GradientFn]:
    """Der Winkel zwischen zwei Linien, als **eine** Zeile.

    Das Residuum ist ``sin(φ - θ)`` mit φ dem orientierten Winkel von der
    ersten Richtung zur zweiten. Ausgeschrieben ist das
    ``cross(û, v̂)·cos θ - dot(û, v̂)·sin θ``, also genau die Gleichung von
    ``parallel`` bei θ = 0 und die von ``perpendicular`` bei θ = 90°, nur
    gedreht — und damit dieselbe Ableitung, gewichtet.

    **Warum nicht ``atan2(cross, dot) - θ``.** Der Bogen springt bei ±180° um
    eine volle Drehung; ein Löser, der über diese Kante läuft, bekommt dort
    einen Sprung im Residuum und keine Ableitung, die davon weiß. Der Sinus
    hat den Sprung nicht. Sein Preis ist die Periode 180: Er sagt nicht, ob
    die zweite Linie im oder gegen den Uhrzeigersinn liegt — dieselbe
    Zweideutigkeit, die ``parallel`` seit je hat, und dieselbe Antwort darauf:
    Der Löser bleibt bei der Lösung, die der Zeichnung am nächsten liegt.
    """
    cosine = math.cos(radians)
    sine = math.sin(radians)

    def fn(pts: np.ndarray) -> tuple[float, ...]:
        ux, uy, _ = _unit(pts, a, b)
        vx, vy, _ = _unit(pts, c, d)
        return ((ux * vy - uy * vx) * cosine - (ux * vx + uy * vy) * sine,)

    def grad(pts: np.ndarray, out: np.ndarray) -> None:
        ux, uy, _ = _unit(pts, a, b)
        vx, vy, _ = _unit(pts, c, d)
        # Der Kreuzanteil wie in ``parallel`` …
        cux, cuy = _project(pts, a, b, vy, -vx)
        cvx, cvy = _project(pts, c, d, -uy, ux)
        # … der Skalaranteil wie in ``perpendicular``.
        dux, duy = _project(pts, a, b, vx, vy)
        dvx, dvy = _project(pts, c, d, ux, uy)
        gux = cosine * cux - sine * dux
        guy = cosine * cuy - sine * duy
        gvx = cosine * cvx - sine * dvx
        gvy = cosine * cvy - sine * dvy
        out[0, b, 0] += gux
        out[0, b, 1] += guy
        out[0, a, 0] -= gux
        out[0, a, 1] -= guy
        out[0, d, 0] += gvx
        out[0, d, 1] += gvy
        out[0, c, 0] -= gvx
        out[0, c, 1] -= gvy

    return fn, grad


def _equal_equation(a: int, b: int, c: int, d: int) -> tuple[_ResidualFn, _GradientFn]:
    """Zwei Spannen gleich lang — Linienlänge gegen Linienlänge, Radius gegen
    Radius (siehe :data:`_CONSTRAINT_TARGETS`)."""

    def fn(pts: np.ndarray) -> tuple[float, ...]:
        return (_span(pts, a, b) - _span(pts, c, d),)

    def grad(pts: np.ndarray, out: np.ndarray) -> None:
        ux, uy, _ = _unit(pts, a, b)
        vx, vy, _ = _unit(pts, c, d)
        out[0, b, 0] += ux
        out[0, b, 1] += uy
        out[0, a, 0] -= ux
        out[0, a, 1] -= uy
        out[0, d, 0] -= vx
        out[0, d, 1] -= vy
        out[0, c, 0] += vx
        out[0, c, 1] += vy

    return fn, grad


def _midpoint_equation(p: int, a: int, b: int) -> tuple[_ResidualFn, _GradientFn]:
    """Ein Punkt in der Mitte einer Linie: ``p = (a + b) / 2``.

    Zwei Zeilen, eine je Koordinate — wie die Deckung, und aus demselben
    Grund: „auf halber Strecke" ist eine Lage und keine Länge.
    """

    def fn(pts: np.ndarray) -> tuple[float, ...]:
        return (
            float(pts[p][0]) - (float(pts[a][0]) + float(pts[b][0])) / 2.0,
            float(pts[p][1]) - (float(pts[a][1]) + float(pts[b][1])) / 2.0,
        )

    def grad(pts: np.ndarray, out: np.ndarray) -> None:
        out[0, p, 0] += 1.0
        out[0, a, 0] -= 0.5
        out[0, b, 0] -= 0.5
        out[1, p, 1] += 1.0
        out[1, a, 1] -= 0.5
        out[1, b, 1] -= 0.5

    return fn, grad


def _tangent_equation(a: int, b: int, centre: int, rim: int) -> tuple[_ResidualFn, _GradientFn]:
    def cross(pts: np.ndarray) -> float:
        ux, uy, _ = _unit(pts, a, b)
        wx = float(pts[centre][0] - pts[a][0])
        wy = float(pts[centre][1] - pts[a][1])
        return ux * wy - uy * wx

    def fn(pts: np.ndarray) -> tuple[float, ...]:
        return (abs(cross(pts)) - _span(pts, centre, rim),)

    def grad(pts: np.ndarray, out: np.ndarray) -> None:
        ux, uy, _ = _unit(pts, a, b)
        wx = float(pts[centre][0] - pts[a][0])
        wy = float(pts[centre][1] - pts[a][1])
        sign = 1.0 if cross(pts) >= 0.0 else -1.0
        # Anteil über die Linienrichtung û …
        gux, guy = _project(pts, a, b, wy, -wx)
        out[0, b, 0] += sign * gux
        out[0, b, 1] += sign * guy
        out[0, a, 0] -= sign * gux
        out[0, a, 1] -= sign * guy
        # … und über den Fußpunktvektor w = Mittelpunkt - a.
        out[0, centre, 0] += sign * -uy
        out[0, centre, 1] += sign * ux
        out[0, a, 0] -= sign * -uy
        out[0, a, 1] -= sign * ux
        # Radiusanteil: -|rim - centre|.
        rx, ry, _ = _unit(pts, centre, rim)
        out[0, rim, 0] -= rx
        out[0, rim, 1] -= ry
        out[0, centre, 0] += rx
        out[0, centre, 1] += ry

    return fn, grad


def _symmetric_equation(p: int, q: int, a: int, b: int) -> tuple[_ResidualFn, _GradientFn]:
    def fn(pts: np.ndarray) -> tuple[float, ...]:
        ux, uy, _ = _unit(pts, a, b)
        mx = (float(pts[p][0]) + float(pts[q][0])) / 2.0 - float(pts[a][0])
        my = (float(pts[p][1]) + float(pts[q][1])) / 2.0 - float(pts[a][1])
        cx = float(pts[q][0] - pts[p][0])
        cy = float(pts[q][1] - pts[p][1])
        return (ux * my - uy * mx, ux * cx + uy * cy)

    def grad(pts: np.ndarray, out: np.ndarray) -> None:
        ux, uy, _ = _unit(pts, a, b)
        mx = (float(pts[p][0]) + float(pts[q][0])) / 2.0 - float(pts[a][0])
        my = (float(pts[p][1]) + float(pts[q][1])) / 2.0 - float(pts[a][1])
        cx = float(pts[q][0] - pts[p][0])
        cy = float(pts[q][1] - pts[p][1])
        # Zeile 1: die Mitte liegt auf der Achse — cross(û, m).
        gux, guy = _project(pts, a, b, my, -mx)
        out[0, b, 0] += gux
        out[0, b, 1] += guy
        out[0, a, 0] -= gux
        out[0, a, 1] -= guy
        out[0, p, 0] += -uy / 2.0
        out[0, p, 1] += ux / 2.0
        out[0, q, 0] += -uy / 2.0
        out[0, q, 1] += ux / 2.0
        out[0, a, 0] -= -uy
        out[0, a, 1] -= ux
        # Zeile 2: die Verbindung steht senkrecht auf der Achse — û · (q - p).
        hux, huy = _project(pts, a, b, cx, cy)
        out[1, b, 0] += hux
        out[1, b, 1] += huy
        out[1, a, 0] -= hux
        out[1, a, 1] -= huy
        out[1, q, 0] += ux
        out[1, q, 1] += uy
        out[1, p, 0] -= ux
        out[1, p, 1] -= uy

    return fn, grad


def _fixed_equation(p: int, anchor_x: float, anchor_y: float) -> tuple[_ResidualFn, _GradientFn]:
    def fn(pts: np.ndarray) -> tuple[float, ...]:
        return (float(pts[p][0]) - anchor_x, float(pts[p][1]) - anchor_y)

    def grad(pts: np.ndarray, out: np.ndarray) -> None:
        out[0, p, 0] += 1.0
        out[1, p, 1] += 1.0

    return fn, grad


def _arc_equation(centre: int, start: int, end: int) -> tuple[_ResidualFn, _GradientFn]:
    def fn(pts: np.ndarray) -> tuple[float, ...]:
        return (_span(pts, centre, start) - _span(pts, centre, end),)

    def grad(pts: np.ndarray, out: np.ndarray) -> None:
        sx, sy, _ = _unit(pts, centre, start)
        ex, ey, _ = _unit(pts, centre, end)
        out[0, start, 0] += sx
        out[0, start, 1] += sy
        out[0, end, 0] -= ex
        out[0, end, 1] -= ey
        out[0, centre, 0] += ex - sx
        out[0, centre, 1] += ey - sy

    return fn, grad


def _ellipse_axes_equation(centre: int, first: int, second: int) -> tuple[_ResidualFn, _GradientFn]:
    """Die zweite Achse einer Ellipse steht senkrecht auf der ersten.

    Das Residuum ist der Anteil der zweiten Achse **entlang** der ersten,
    ``(u · w) / |u|`` mit ``u`` = erste, ``w`` = zweite Achse — eine Länge in
    Millimetern und damit in derselben Größe wie jede andere Zeile. Ein
    Skalarprodukt ohne Teilung hätte Quadratmillimeter und zöge die
    Konfliktprüfung (``_TOL``) bei großen Ellipsen scharf, bei kleinen stumpf.
    """

    def parts(pts: np.ndarray) -> tuple[float, float, float, float, float, float]:
        ux = float(pts[first][0] - pts[centre][0])
        uy = float(pts[first][1] - pts[centre][1])
        wx = float(pts[second][0] - pts[centre][0])
        wy = float(pts[second][1] - pts[centre][1])
        length = max(math.hypot(ux, uy), EPS_GEOM)
        return ux, uy, wx, wy, length, (ux * wx + uy * wy) / length

    def fn(pts: np.ndarray) -> tuple[float, ...]:
        return (parts(pts)[5],)

    def grad(pts: np.ndarray, out: np.ndarray) -> None:
        ux, uy, wx, wy, length, along = parts(pts)
        # Nach w: die Einheitsrichtung der ersten Achse.
        gwx, gwy = ux / length, uy / length
        # Nach u: (w - along · û) / |u|.
        gux = (wx - along * gwx) / length
        guy = (wy - along * gwy) / length
        out[0, first, 0] += gux
        out[0, first, 1] += guy
        out[0, second, 0] += gwx
        out[0, second, 1] += gwy
        out[0, centre, 0] -= gux + gwx
        out[0, centre, 1] -= guy + gwy

    return fn, grad


#: Unterhalb dieser Größe gilt ein Vektor als null — nur als Schutz gegen die
#: Teilung durch null in den Ellipsengleichungen, keine Toleranz (Regel 7).
_TINY: Final[float] = 1e-12


def _on_ellipse_equation(
    point: int, centre: int, first: int, second: int
) -> tuple[_ResidualFn, _GradientFn]:
    """Ein Punkt liegt auf der Ellipse aus Mitte und beiden Achsenenden.

    **Gemessen wird entlang des Strahls von der Mitte durch den Punkt.** Mit
    ``A = [u w]`` (beide Achsen als Spalten) ist ``A⁻¹·d`` der Punkt im
    Einheitskreis der Ellipse, ``d`` sein Abstand zur Mitte; auf dem Strahl
    liegt die Ellipse bei ``d / |A⁻¹·d|``. Das Residuum ist der Abstand
    dazwischen::

        r = |d| · (1 - |det A| / |(cross(d, w), cross(u, d))|)

    Am Kreis ist das genau ``|d| - R``. Es ist nicht der kürzeste Abstand zur
    Kurve, aber nie kleiner als er — ein Rest unter ``_TOL`` heißt also auch
    „höchstens so weit neben der Kurve" —, und es braucht weder eine
    Projektion noch eine Winkelfunktion: Grundrechenarten und Wurzeln, auf
    jeder Maschine dieselbe Zahl (RM-187).
    """

    def fn(pts: np.ndarray) -> tuple[float, ...]:
        return (_radial(pts, point, centre, first, second).residual,)

    def grad(pts: np.ndarray, out: np.ndarray) -> None:
        ray = _radial(pts, point, centre, first, second)
        # r = |d| · (1 - ratio), ratio = |D| / G, also
        #   ∂r = ∂|d| · (1 - ratio) - (|d| / G) · (∂|D| - ratio · ∂G)
        # mit ∂|d|/∂d = d̂, ∂G = (g1 ∂g1 + g2 ∂g2) / G, ∂|D| = ±∂D und
        #   ∂g1/∂d = (wy, -wx), ∂g1/∂w = (-dy, dx),
        #   ∂g2/∂d = (-uy, ux), ∂g2/∂u = (dy, -dx),
        #   ∂D/∂u = (wy, -wx),  ∂D/∂w = (-uy, ux).
        factor = ray.reach / ray.spread
        keep = 1.0 - ray.ratio
        dx, dy, ux, uy, wx, wy = ray.d_x, ray.d_y, ray.u_x, ray.u_y, ray.w_x, ray.w_y
        g1, g2, sign, spread = ray.g1, ray.g2, ray.sign, ray.spread
        # Nach d: nur |d| und G hängen daran.
        spread_x = (g1 * wy - g2 * uy) / spread
        spread_y = (-g1 * wx + g2 * ux) / spread
        gdx = ray.unit_x * keep + factor * ray.ratio * spread_x
        gdy = ray.unit_y * keep + factor * ray.ratio * spread_y
        # Nach u: |D| über ∂D/∂u, G über g2.
        gux = -factor * (sign * wy - ray.ratio * g2 * dy / spread)
        guy = -factor * (-sign * wx + ray.ratio * g2 * dx / spread)
        # Nach w: |D| über ∂D/∂w, G über g1.
        gwx = -factor * (-sign * uy + ray.ratio * g1 * dy / spread)
        gwy = -factor * (sign * ux - ray.ratio * g1 * dx / spread)
        out[0, point, 0] += gdx
        out[0, point, 1] += gdy
        out[0, first, 0] += gux
        out[0, first, 1] += guy
        out[0, second, 0] += gwx
        out[0, second, 1] += gwy
        out[0, centre, 0] -= gdx + gux + gwx
        out[0, centre, 1] -= gdy + guy + gwy

    return fn, grad


@dataclass(frozen=True, slots=True)
class _Ray:
    """Die Zwischengrößen der Strahlmessung an einer Ellipse (:func:`_on_ellipse_equation`)."""

    d_x: float
    d_y: float
    u_x: float
    u_y: float
    w_x: float
    w_y: float
    g1: float
    g2: float
    sign: float
    reach: float
    spread: float
    ratio: float
    unit_x: float
    unit_y: float

    @property
    def residual(self) -> float:
        return self.reach * (1.0 - self.ratio)


def _radial(pts: np.ndarray, point: int, centre: int, first: int, second: int) -> _Ray:
    """Wo ``point`` auf dem Strahl von der Mitte aus zur Ellipse steht."""
    dx = float(pts[point][0] - pts[centre][0])
    dy = float(pts[point][1] - pts[centre][1])
    ux = float(pts[first][0] - pts[centre][0])
    uy = float(pts[first][1] - pts[centre][1])
    wx = float(pts[second][0] - pts[centre][0])
    wy = float(pts[second][1] - pts[centre][1])
    reach = math.hypot(dx, dy)
    if reach < _TINY:
        # Genau auf der Mitte hat der Strahl keine Richtung. Genommen wird die
        # der ersten Achse; der Rest ist dort ohnehin eine ganze Halbachse.
        scale = max(math.hypot(ux, uy), _TINY)
        dx, dy = _TINY * ux / scale, _TINY * uy / scale
        reach = math.hypot(dx, dy)
    g1 = dx * wy - dy * wx
    g2 = ux * dy - uy * dx
    det = ux * wy - uy * wx
    spread = max(math.hypot(g1, g2), _TINY)
    return _Ray(
        d_x=dx,
        d_y=dy,
        u_x=ux,
        u_y=uy,
        w_x=wx,
        w_y=wy,
        g1=g1,
        g2=g2,
        sign=1.0 if det >= 0.0 else -1.0,
        reach=reach,
        spread=spread,
        ratio=abs(det) / spread,
        unit_x=dx / reach,
        unit_y=dy / reach,
    )


def _element_equations(
    kind: str, begin: int
) -> list[tuple[tuple[int, ...], int, _ResidualFn, _GradientFn]]:
    """Die eigenen Gleichungen eines Elements — mit den Punkten, die sie lesen.

    Ein Bogen hält seine Schenkel gleich lang; eine Ellipse hält die zweite
    Achse senkrecht auf der ersten; ein Ellipsenbogen hält dazu Anfang und
    Ende auf der Ellipse. Die Punkte stehen dabei, damit
    :func:`_build_equations` eine Gleichung weglassen kann, deren Punkte alle
    fest sind und an der sie schon gilt (B28, verallgemeinert).
    """
    if kind == "arc":
        return [((begin, begin + 1, begin + 2), 1, *_arc_equation(begin, begin + 1, begin + 2))]
    if kind in ("ellipse", "elliptical_arc"):
        centre, first, second = begin, begin + 1, begin + 2
        equations: list[tuple[tuple[int, ...], int, _ResidualFn, _GradientFn]] = [
            ((centre, first, second), 1, *_ellipse_axes_equation(centre, first, second))
        ]
        if kind == "elliptical_arc":
            for end in (begin + 3, begin + 4):
                equations.append(
                    (
                        (centre, first, second, end),
                        1,
                        *_on_ellipse_equation(end, centre, first, second),
                    )
                )
        return equations
    return []


# --- Kurvenbedingungen (RM-188 P6.6b) --------------------------------------------------
#
# *Punkt auf Kurve*, *glatt* (G1) und *krümmungsstetig* (G2) lesen Normalen und
# Krümmungen von Ellipsen und Splines. Deren Ableitungen von Hand wären
# Seiten voller Kettenregel, und ein Vorzeichenfehler darin ist ein stiller
# Fehler: Der Löser konvergiert langsamer, und die Ranganalyse — an der die
# Meldung „legt fest, was schon festliegt" hängt — irrt. Die Residuen stehen
# deshalb **einmal** als Rechnung über Zahlen da und werden für die Ableitung
# mit Dualzahlen noch einmal gerechnet (Vorwärtsableitung): exakt bis auf die
# Rundung, dieselbe Rechnung wie das Residuum, keine zweite Herleitung.


class _Dual:
    """Eine Zahl mit ihrer Ableitung nach den Koordinaten einer Bedingung.

    Nur die vier Grundrechenarten und die Wurzel — mehr braucht keine der
    Kurvenbedingungen, und mehr soll hier nicht stehen (RM-187: keine
    Winkelfunktion).
    """

    __slots__ = ("slope", "value")

    def __init__(self, value: float, slope: np.ndarray) -> None:
        self.value = value
        self.slope = slope

    def __add__(self, other: Any) -> _Dual:
        if isinstance(other, _Dual):
            return _Dual(self.value + other.value, self.slope + other.slope)
        return _Dual(self.value + other, self.slope)

    __radd__ = __add__

    def __sub__(self, other: Any) -> _Dual:
        if isinstance(other, _Dual):
            return _Dual(self.value - other.value, self.slope - other.slope)
        return _Dual(self.value - other, self.slope)

    def __rsub__(self, other: Any) -> _Dual:
        return _Dual(other - self.value, -self.slope)

    def __neg__(self) -> _Dual:
        return _Dual(-self.value, -self.slope)

    def __mul__(self, other: Any) -> _Dual:
        if isinstance(other, _Dual):
            return _Dual(
                self.value * other.value, self.slope * other.value + other.slope * self.value
            )
        return _Dual(self.value * other, self.slope * other)

    __rmul__ = __mul__

    def __truediv__(self, other: Any) -> _Dual:
        if isinstance(other, _Dual):
            return _Dual(
                self.value / other.value,
                (self.slope * other.value - other.slope * self.value) / (other.value * other.value),
            )
        return _Dual(self.value / other, self.slope / other)

    def __rtruediv__(self, other: Any) -> _Dual:
        return _Dual(other / self.value, -other * self.slope / (self.value * self.value))


def _root(value: Any) -> Any:
    """Die Wurzel einer Zahl oder Dualzahl — gegen null gesichert wie ``_unit``."""
    if isinstance(value, _Dual):
        root = math.sqrt(max(value.value, _TINY * _TINY))
        return _Dual(root, value.slope / (2.0 * root))
    return math.sqrt(max(value, _TINY * _TINY))


def _plain(value: Any) -> float:
    """Der Zahlenwert einer Zahl oder Dualzahl — für Fallunterscheidungen."""
    return float(value.value) if isinstance(value, _Dual) else float(value)


_Vector = tuple[Any, Any]
"""Ein Vektor aus Zahlen oder Dualzahlen."""


@dataclass(frozen=True, slots=True)
class _Curve:
    """Eine Kurve, wie eine Kurvenbedingung sie liest: Art und ihre Punkte."""

    kind: str
    begin: int
    count: int

    @property
    def points(self) -> tuple[int, ...]:
        return tuple(range(self.begin, self.begin + self.count))


def _curve_at(
    elements: Sequence[SketchElement], offsets: Sequence[int], target: int, field: str
) -> _Curve:
    """Die Kurve, die ein Ziel meint — oder die Absage, warum es keine ist."""
    for element, begin in zip(elements, offsets, strict=True):
        if begin == target and element.kind in _CURVE_KINDS:
            return _Curve(element.kind, begin, len(element.points))
    raise ValidationError(
        field,
        _(
            "Die Bedingung zeigt nicht auf eine Kurve — gemeint ist der erste Punkt "
            "einer Linie, eines Kreises, Bogens, einer Ellipse oder Kurve."
        ),
        value=target,
        constraint="not_a_curve",
    )


def _bezier_rows(count: int, piece: int) -> list[list[float]]:
    """Die vier Bézierpunkte eines Splinestücks als Gewichte über seine Punkte.

    Dieselbe Catmull-Rom-Kurve wie ``profile.spline_controls`` — dort mit
    Zahlen, hier mit Gewichten, damit die Kontrollpunkte als Summe über die
    Splinepunkte in jede Rechnung gehen, auch in eine mit Dualzahlen.
    """
    before = max(piece - 1, 0)
    after = min(piece + 2, count - 1)
    rows = [[0.0] * count for _ in range(4)]
    rows[0][piece] = 1.0
    rows[1][piece] += 1.0
    rows[1][piece + 1] += 1.0 / 6.0
    rows[1][before] -= 1.0 / 6.0
    rows[2][piece + 1] += 1.0
    rows[2][after] -= 1.0 / 6.0
    rows[2][piece] += 1.0 / 6.0
    rows[3][piece + 1] = 1.0
    return rows


def _weighted(rows: Sequence[float], values: Sequence[_Vector]) -> _Vector:
    x: Any = 0.0
    y: Any = 0.0
    for weight, (px, py) in zip(rows, values, strict=True):
        if weight:
            x = x + weight * px
            y = y + weight * py
    return x, y


def _spline_derivatives(values: Sequence[_Vector], local: int) -> tuple[_Vector, _Vector]:
    """Erste und zweite Ableitung der Splinekurve an ihrem Punkt ``local``.

    Am Anfang das erste Stück bei t = 0, sonst das Stück, das an diesem Punkt
    **endet**, bei t = 1. Die erste Ableitung ist an jedem Punkt dieselbe von
    beiden Seiten (die Kurve ist tangentenstetig); die zweite nicht — deshalb
    fragt ``curvature`` nur an den Enden.
    """
    count = len(values)
    at_start = local == 0
    piece = 0 if at_start else local - 1
    b0, b1, b2, b3 = (_weighted(row, values) for row in _bezier_rows(count, piece))
    if at_start:
        d1 = (3.0 * (b1[0] - b0[0]), 3.0 * (b1[1] - b0[1]))
        d2 = (6.0 * (b2[0] - 2.0 * b1[0] + b0[0]), 6.0 * (b2[1] - 2.0 * b1[1] + b0[1]))
    else:
        d1 = (3.0 * (b3[0] - b2[0]), 3.0 * (b3[1] - b2[1]))
        d2 = (6.0 * (b3[0] - 2.0 * b2[0] + b1[0]), 6.0 * (b3[1] - 2.0 * b2[1] + b1[1]))
    return d1, d2


def _curvature_vector(d1: _Vector, d2: _Vector) -> _Vector:
    """Der Krümmungsvektor aus erster und zweiter Ableitung.

    ``κ = (d1 kreuz d2) / |d1|³`` in Richtung der Linksnormalen ``J·d1/|d1|`` —
    zusammen ``(d1 kreuz d2) · J·d1 / |d1|⁴``. Er zeigt zum Krümmungsmittelpunkt,
    gleich in welcher Richtung die Kurve durchlaufen wird; zwei Kurven, die
    sich an einem Punkt treffen, vergleicht man deshalb an ihm und nicht an
    einer Zahl mit Vorzeichen.
    """
    cross = d1[0] * d2[1] - d1[1] * d2[0]
    speed = d1[0] * d1[0] + d1[1] * d1[1]
    scale = cross / (speed * speed)
    return (-d1[1] * scale, d1[0] * scale)


def _ellipse_parts(values: Sequence[_Vector], spot: _Vector) -> tuple[_Vector, _Vector, _Vector]:
    """Abstand des Punkts zur Mitte und beide Achsen: ``d``, ``u``, ``w``."""
    (cx, cy), (mx, my), (nx, ny) = values[0], values[1], values[2]
    return (spot[0] - cx, spot[1] - cy), (mx - cx, my - cy), (nx - cx, ny - cy)


def _normal_of(kind: str, values: Sequence[_Vector], spot: _Vector, local: int) -> _Vector:
    """Eine Normale der Kurve an ``spot`` — nicht auf Länge eins gebracht.

    Linie: senkrecht auf ihrer Richtung. Kreis und Bogen: radial. Ellipse und
    Ellipsenbogen: der Gradient ihrer Gleichung ``|A⁻¹·d|²``, bis auf einen
    positiven Faktor ``(w_y g₁ - u_y g₂, u_x g₂ - w_x g₁)`` mit
    ``g₁ = d kreuz w`` und ``g₂ = u kreuz d`` — auch neben der Kurve definiert, ohne
    Projektion. Spline: senkrecht auf seiner Tangente an seinem Punkt ``local``.
    """
    if kind == "line":
        (ax, ay), (bx, by) = values[0], values[1]
        return (-(by - ay), bx - ax)
    if kind in ("circle", "arc"):
        return (spot[0] - values[0][0], spot[1] - values[0][1])
    if kind in ("ellipse", "elliptical_arc"):
        (dx, dy), (ux, uy), (wx, wy) = _ellipse_parts(values, spot)
        g1 = dx * wy - dy * wx
        g2 = ux * dy - uy * dx
        return (wy * g1 - uy * g2, ux * g2 - wx * g1)
    d1, _d2 = _spline_derivatives(values, local)
    return (-d1[1], d1[0])


def _curvature_of(kind: str, values: Sequence[_Vector], spot: _Vector, local: int) -> _Vector:
    """Der Krümmungsvektor der Kurve an ``spot`` (:func:`_curvature_vector`).

    Die Ellipse wird dort gelesen, wo der Strahl von der Mitte durch den Punkt
    sie trifft — für einen Punkt auf ihr genau an ihm. Mit ``e`` dem Parameter
    dort ist ``E' = e_x·w - e_y·u`` und ``E' kreuz E'' = det A``.
    """
    if kind == "line":
        return (0.0, 0.0)
    if kind in ("circle", "arc"):
        (cx, cy), (rx, ry) = values[0], values[1]
        qx, qy = cx - spot[0], cy - spot[1]
        radius = _root((rx - cx) * (rx - cx) + (ry - cy) * (ry - cy))
        reach = _root(qx * qx + qy * qy)
        return (qx / (reach * radius), qy / (reach * radius))
    if kind in ("ellipse", "elliptical_arc"):
        (dx, dy), (ux, uy), (wx, wy) = _ellipse_parts(values, spot)
        g1 = dx * wy - dy * wx
        g2 = ux * dy - uy * dx
        det = ux * wy - uy * wx
        size = _root(g1 * g1 + g2 * g2)
        sign = 1.0 if _plain(det) >= 0.0 else -1.0
        ex, ey = sign * g1 / size, sign * g2 / size
        tangent = (ex * wx - ey * ux, ex * wy - ey * uy)
        return _curvature_vector(tangent, (-(ex * ux + ey * wx), -(ex * uy + ey * wy)))
    return _curvature_vector(*_spline_derivatives(values, local))


def _unit_vector(vector: _Vector) -> _Vector:
    length = _root(vector[0] * vector[0] + vector[1] * vector[1])
    return (vector[0] / length, vector[1] / length)


def _dual_equation(
    indices: Sequence[int], residual: Callable[[list[_Vector]], Any]
) -> tuple[_ResidualFn, _GradientFn]:
    """Ein Residuum über die Punkte ``indices`` — als Zahl und mit Dualzahlen
    abgeleitet (siehe den Abschnitt oben). Jeder Punkt steht in ``indices``
    genau einmal, auch wenn er zwei Rollen trägt."""
    order = tuple(dict.fromkeys(indices))
    size = 2 * len(order)
    unit = np.eye(size)

    def fn(pts: np.ndarray) -> tuple[float, ...]:
        values = [(float(pts[i][0]), float(pts[i][1])) for i in order]
        return (_plain(residual(values)),)

    def grad(pts: np.ndarray, out: np.ndarray) -> None:
        values: list[_Vector] = [
            (
                _Dual(float(pts[i][0]), unit[2 * place]),
                _Dual(float(pts[i][1]), unit[2 * place + 1]),
            )
            for place, i in enumerate(order)
        ]
        result = residual(values)
        if not isinstance(result, _Dual):
            return
        for place, i in enumerate(order):
            out[0, i, 0] += float(result.slope[2 * place])
            out[0, i, 1] += float(result.slope[2 * place + 1])

    return fn, grad


def _on_line_equation(point: int, start: int, end: int) -> tuple[_ResidualFn, _GradientFn]:
    """Ein Punkt liegt auf der **Geraden** durch eine Linie — ihr Abstand mit
    Vorzeichen, ``û kreuz (p - a)``. Die Gerade und nicht die Strecke: So sucht es
    jeder, der eine Bohrung auf eine Mittellinie setzt, die kürzer gezeichnet
    ist als das Teil."""

    def fn(pts: np.ndarray) -> tuple[float, ...]:
        ux, uy, _ = _unit(pts, start, end)
        dx = float(pts[point][0] - pts[start][0])
        dy = float(pts[point][1] - pts[start][1])
        return (ux * dy - uy * dx,)

    def grad(pts: np.ndarray, out: np.ndarray) -> None:
        ux, uy, _ = _unit(pts, start, end)
        dx = float(pts[point][0] - pts[start][0])
        dy = float(pts[point][1] - pts[start][1])
        # Nach der Richtung û, zurückgeholt auf die Enden der Linie …
        gx, gy = _project(pts, start, end, dy, -dx)
        out[0, end, 0] += gx
        out[0, end, 1] += gy
        out[0, start, 0] -= gx
        out[0, start, 1] -= gy
        # … und nach d = p - a.
        out[0, point, 0] += -uy
        out[0, point, 1] += ux
        out[0, start, 0] -= -uy
        out[0, start, 1] -= ux

    return fn, grad


#: Wie oft die Projektion auf einen Spline je Stück nachgebessert wird, und an
#: wie vielen Stellen sie vorher sucht. Acht Newtonschritte von der besten
#: Stelle aus erreichen die Rundung; das Raster verhindert, dass sie auf der
#: falschen Seite einer Schleife beginnt.
_PROJECTION_STEPS: Final = 8
_PROJECTION_SAMPLES: Final = 16


def _bernstein(t: float) -> tuple[tuple[float, ...], tuple[float, ...], tuple[float, ...]]:
    """Die kubischen Bernsteinpolynome bei ``t`` und ihre zwei Ableitungen."""
    r = 1.0 - t
    values = (r * r * r, 3.0 * r * r * t, 3.0 * r * t * t, t * t * t)
    first = (-3.0 * r * r, 3.0 * r * r - 6.0 * r * t, 6.0 * r * t - 3.0 * t * t, 3.0 * t * t)
    second = (6.0 * r, -12.0 * r + 6.0 * t, 6.0 * r - 12.0 * t, 6.0 * t)
    return values, first, second


def _closest_on_spline(spline: np.ndarray, spot: tuple[float, float]) -> tuple[int, float, float]:
    """Stück, Parameter und Abstand des Kurvenpunkts, der ``spot`` am nächsten liegt.

    Deterministisch und ohne Zufall: ein festes Raster je Stück, dann
    Newtonschritte auf ``(s(t) - p) · s'(t) = 0``, am Rand des Stücks
    festgehalten. Unter allen Stücken gewinnt das kleinste — bei Gleichstand
    das erste.
    """
    count = len(spline)
    best: tuple[float, int, float] | None = None
    for piece in range(count - 1):
        controls = np.asarray(_bezier_rows(count, piece), dtype=float) @ spline
        samples = [
            math.dist(tuple(_bernstein(t)[0] @ controls), spot)
            for t in np.linspace(0.0, 1.0, _PROJECTION_SAMPLES + 1)
        ]
        t = float(np.argmin(samples)) / _PROJECTION_SAMPLES
        for _step in range(_PROJECTION_STEPS):
            values, first, second = _bernstein(t)
            place = np.asarray(values) @ controls
            speed = np.asarray(first) @ controls
            bend = np.asarray(second) @ controls
            gap = place - np.asarray(spot)
            slope = float(gap[0] * speed[0] + gap[1] * speed[1])
            steep = float(
                speed[0] * speed[0] + speed[1] * speed[1] + gap[0] * bend[0] + gap[1] * bend[1]
            )
            if steep <= _TINY:
                break
            t = min(1.0, max(0.0, t - slope / steep))
        distance = math.dist(tuple(np.asarray(_bernstein(t)[0]) @ controls), spot)
        if best is None or distance < best[0]:
            best = (distance, piece, t)
    assert best is not None, "ein Spline hat mindestens ein Stück"
    return best[1], best[2], best[0]


def closest_on_spline(points: Sequence[Point2], at: Point2) -> tuple[int, Point2]:
    """Das Stück und der Kurvenpunkt eines Splines, die ``at`` am nächsten liegen.

    Dieselbe Suche wie für *Punkt auf Kurve* — ``edit.spline_point_added``
    setzt dort den neuen Punkt ein, und der liegt damit genau auf der Kurve,
    die der Löser kennt.
    """
    spline = np.asarray(points, dtype=float).reshape(-1, 2)
    piece, t, _distance = _closest_on_spline(spline, (float(at[0]), float(at[1])))
    controls = np.asarray(_bezier_rows(len(spline), piece), dtype=float) @ spline
    x, y = np.asarray(_bernstein(t)[0]) @ controls
    return piece, (float(x), float(y))


def _on_spline_equation(point: int, curve: _Curve) -> tuple[_ResidualFn, _GradientFn]:
    """Ein Punkt liegt auf der Splinekurve — ihr Abstand mit Vorzeichen.

    Gerechnet an der **nächsten Stelle der Kurve** (:func:`_closest_on_spline`):
    ``r = n̂ · (p - s(t*))`` mit der Einheitsnormalen dort. Die Ableitung folgt
    aus dem Hüllensatz: An der nächsten Stelle steht ``p - s`` senkrecht auf
    der Kurve, also hebt sich der Anteil über ``t*`` auf, und es bleibt
    ``∂r/∂p = n̂`` und ``∂r/∂Q_k = -w_k(t*) · n̂`` mit den Gewichten der
    Splinepunkte an dieser Stelle — exakt, ohne Differenzen.

    **Jenseits eines Endes** ist die nächste Stelle das Ende selbst, und die
    Normale dort misst nur den seitlichen Versatz: Ein Punkt in Verlängerung
    der Kurve hätte den Rest null. Dort zählt deshalb der ganze Abstand zum
    Ende, mit dem Vorzeichen der Seite.
    """
    indices = curve.points

    def measure(pts: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
        spline = np.asarray([pts[index] for index in indices], dtype=float)
        spot = (float(pts[point][0]), float(pts[point][1]))
        count = len(spline)
        piece, t, _distance = _closest_on_spline(spline, spot)
        rows = np.asarray(_bezier_rows(count, piece), dtype=float)
        values, first, _second = _bernstein(t)
        weights = np.asarray(values) @ rows
        place = weights @ spline
        speed = (np.asarray(first) @ rows) @ spline
        length = max(math.hypot(float(speed[0]), float(speed[1])), _TINY)
        normal = np.array([-float(speed[1]), float(speed[0])]) / length
        gap = np.asarray(spot) - place
        across = float(normal[0] * gap[0] + normal[1] * gap[1])
        reach = math.hypot(float(gap[0]), float(gap[1]))
        at_end = (piece == 0 and t <= 0.0) or (piece == count - 2 and t >= 1.0)
        if at_end and reach > _TINY and abs(across) < reach * (1.0 - EPS_GEOM):
            side = 1.0 if across >= 0.0 else -1.0
            direction = side * gap / reach
            return side * reach, direction, weights
        return across, normal, weights

    def fn(pts: np.ndarray) -> tuple[float, ...]:
        return (measure(pts)[0],)

    def grad(pts: np.ndarray, out: np.ndarray) -> None:
        _residual, direction, weights = measure(pts)
        out[0, point, 0] += float(direction[0])
        out[0, point, 1] += float(direction[1])
        for weight, index in zip(weights, indices, strict=True):
            out[0, index, 0] -= float(weight * direction[0])
            out[0, index, 1] -= float(weight * direction[1])

    return fn, grad


def _curve_equation(
    constraint: SketchConstraint,
    elements: Sequence[SketchElement],
    offsets: Sequence[int],
    anchors: np.ndarray,
    field: str,
) -> tuple[int, _ResidualFn, _GradientFn]:
    """Die Gleichung einer Kurvenbedingung — nach Prüfung ihrer Ziele."""
    kind = constraint.kind
    if kind == "on_curve":
        point, head = constraint.targets
        curve = _curve_at(elements, offsets, head, field)
        if point in curve.points:
            raise ValidationError(
                field,
                _(
                    "Ein Punkt der Kurve selbst liegt schon auf ihr oder bestimmt "
                    "sie — dafür braucht es keine Bedingung."
                ),
                value=point,
                constraint="own_point",
            )
        if curve.kind == "line":
            return 1, *_on_line_equation(point, curve.begin, curve.begin + 1)
        if curve.kind in ("circle", "arc"):
            centre = curve.begin
            return 1, *_equal_equation(centre, point, centre, centre + 1)
        if curve.kind in ("ellipse", "elliptical_arc"):
            begin = curve.begin
            return 1, *_on_ellipse_equation(point, begin, begin + 1, begin + 2)
        return 1, *_on_spline_equation(point, curve)

    first_spot, first_head, second_spot, second_head = constraint.targets
    first = _curve_at(elements, offsets, first_head, field)
    second = _curve_at(elements, offsets, second_head, field)
    if first.begin == second.begin:
        raise ValidationError(
            field,
            _("Ein Übergang braucht zwei verschiedene Kurven."),
            value=first_head,
            constraint="same_curve",
        )
    for spot, curve in ((first_spot, first), (second_spot, second)):
        if curve.kind != "spline":
            continue
        if spot not in curve.points:
            raise ValidationError(
                field,
                _(
                    "An einer Kurve gilt der Übergang an einem ihrer eigenen Punkte — "
                    "einem Ende oder einem Punkt, durch den sie läuft."
                ),
                value=spot,
                constraint="spline_point",
            )
        if kind == "curvature" and spot not in (curve.begin, curve.begin + curve.count - 1):
            raise ValidationError(
                field,
                _(
                    "Krümmungsstetig gilt an einem Ende der Kurve — innen ist sie nur "
                    "tangentenstetig."
                ),
                value=spot,
                constraint="spline_end",
            )

    order = tuple(dict.fromkeys((first_spot, *first.points, second_spot, *second.points)))
    place = {index: position for position, index in enumerate(order)}

    def read(values: list[_Vector], curve: _Curve, spot: int) -> tuple[list[_Vector], _Vector]:
        return [values[place[index]] for index in curve.points], values[place[spot]]

    if kind == "smooth":

        def smooth(values: list[_Vector]) -> Any:
            one, one_spot = read(values, first, first_spot)
            other, other_spot = read(values, second, second_spot)
            ax, ay = _unit_vector(_normal_of(first.kind, one, one_spot, first_spot - first.begin))
            bx, by = _unit_vector(
                _normal_of(second.kind, other, other_spot, second_spot - second.begin)
            )
            return ax * by - ay * bx

        return 1, *_dual_equation(order, smooth)

    # Krümmungsstetig: der Unterschied der Krümmungsvektoren entlang der
    # Normalen von A, auf eine Länge gebracht (``_curvature_scale``).
    scale = _curvature_scale(first, second, anchors, first_spot, second_spot)

    def curving(values: list[_Vector]) -> Any:
        one, one_spot = read(values, first, first_spot)
        other, other_spot = read(values, second, second_spot)
        nx, ny = _unit_vector(_normal_of(first.kind, one, one_spot, first_spot - first.begin))
        kx, ky = _curvature_of(first.kind, one, one_spot, first_spot - first.begin)
        lx, ly = _curvature_of(second.kind, other, other_spot, second_spot - second.begin)
        return ((kx - lx) * nx + (ky - ly) * ny) * scale

    return 1, *_dual_equation(order, curving)


def _curvature_scale(
    first: _Curve, second: _Curve, anchors: np.ndarray, first_spot: int, second_spot: int
) -> float:
    """Womit ein Krümmungsunterschied zur Länge wird: ``L² / 2``.

    Zwei Schmiegekreise mit den Krümmungen κ₁ und κ₂ laufen nach einer Länge
    L entlang der Tangente um ``(κ₁ - κ₂) · L² / 2`` auseinander. Mit L als
    der größeren Ausdehnung beider Kurven am Übergang — Linienlänge, Radius,
    größere Halbachse, Abstand zum nächsten Splinepunkt — misst der Rest also
    Millimeter wie jede andere Zeile, und ``_TOL`` bedeutet hier dasselbe wie
    sonst. Gerechnet einmal aus den gespeicherten Punkten: Eine Zahl, die sich
    während des Lösens änderte, wäre eine zweite Gleichung im Residuum.
    """

    def reach(curve: _Curve, spot: int) -> float:
        begin = curve.begin
        if curve.kind == "spline":
            neighbour = spot + 1 if spot == begin else spot - 1
            return _span(anchors, spot, neighbour)
        if curve.kind in ("ellipse", "elliptical_arc"):
            return max(_span(anchors, begin, begin + 1), _span(anchors, begin, begin + 2))
        return _span(anchors, begin, begin + 1)

    length = max(reach(first, first_spot), reach(second, second_spot), EPS_GEOM)
    return length * length / 2.0


def _constraint_equation(
    constraint: SketchConstraint, measure: float, anchors: np.ndarray
) -> tuple[int, _ResidualFn, _GradientFn]:
    """Übersetzt eine Bedingung in Residuen, Ableitung und Zeilenzahl.

    ``measure`` trägt die Zahl der Bedingung, schon umgerechnet: bei einem
    Längenmaß den Abstand in Millimetern, bei einem Winkelmaß das Bogenmaß.
    """
    kind = constraint.kind
    targets = constraint.targets
    if kind in _LENGTH_FACTOR:
        # Eine Gleichung für drei Arten: Der Faktor steckt schon in ``measure``
        # (siehe :data:`_LENGTH_FACTOR`), hier bleibt der Abstand zweier Punkte.
        return 1, *_distance_equation(targets[0], targets[1], measure)
    if kind == "angle":
        first, second, third, fourth = targets
        return 1, *_angle_equation(first, second, third, fourth, measure)
    if kind == "equal":
        return 1, *_equal_equation(*targets)
    if kind == "midpoint":
        return 2, *_midpoint_equation(*targets)
    if kind == "coincident":
        return 2, *_coincident_equation(targets[0], targets[1])
    if kind == "horizontal":
        return 1, *_axis_equation(targets[0], targets[1], 1)
    if kind == "vertical":
        return 1, *_axis_equation(targets[0], targets[1], 0)
    if kind == "parallel":
        return 1, *_parallel_equation(*targets)
    if kind == "perpendicular":
        return 1, *_perpendicular_equation(*targets)
    if kind == "tangent":
        return 1, *_tangent_equation(*targets)
    if kind == "symmetric":
        return 2, *_symmetric_equation(*targets)
    # fixed: heftet den Punkt an seine Eingangskoordinaten.
    (p,) = targets
    return 2, *_fixed_equation(p, float(anchors[p][0]), float(anchors[p][1]))


def _build_equations(
    sketch: Sketch, params: Mapping[str, float]
) -> tuple[list[_Equation], np.ndarray]:
    """Validiert die Skizze und übersetzt sie in Gleichungen (§30.1)."""
    offsets: list[int] = []
    coords: list[Point2] = []
    for position, element in enumerate(sketch.elements):
        least = _ELEMENT_MINIMUM.get(element.kind)
        if least is not None:
            if len(element.points) < least:
                raise ValidationError(
                    f"elements[{position}]",
                    _("Das Element hat zu wenige Punkte."),
                    value=len(element.points),
                    constraint="point_count",
                )
        elif len(element.points) != _ELEMENT_POINTS[element.kind]:
            raise ValidationError(
                f"elements[{position}]",
                _("Das Element hat die falsche Zahl von Punkten."),
                value=len(element.points),
                constraint="point_count",
            )
        offsets.append(len(coords))
        coords.extend(element.points)
    anchors = np.asarray(coords, dtype=float).reshape(-1, 2)
    total = len(coords)

    equations: list[_Equation] = []
    for index, constraint in enumerate(sketch.constraints):
        field = f"constraints[{index}]"
        if len(constraint.targets) != _CONSTRAINT_TARGETS[constraint.kind]:
            raise ValidationError(
                field,
                _("Die Bedingung hat die falsche Zahl von Zielpunkten."),
                value=len(constraint.targets),
                constraint="target_count",
            )
        if constraint.kind in _MEASURING_ONLY:
            # Zielprüfung oben gilt weiter; hier endet der Weg, denn ohne
            # Gleichung gibt es weder Rang noch Rest noch Konflikt.
            for target in constraint.targets:
                if not 0 <= target < total:
                    raise ValidationError(
                        field,
                        _("Diese Bedingung zeigt auf einen Punkt, den es nicht gibt."),
                        value=target,
                        constraint="unknown_target",
                    )
            continue
        for target in constraint.targets:
            if not 0 <= target < total:
                raise ValidationError(
                    field,
                    _("Die Bedingung zeigt auf einen Punkt, den es nicht gibt."),
                    value=target,
                    constraint="unknown_target",
                )
        measure = 0.0
        if constraint.kind in _LENGTH_FACTOR:
            if not constraint.value:
                raise ValidationError(
                    field, _("Ein Maß braucht einen Wert."), constraint="required"
                )
            measure = evaluate(constraint.value, params)
            if measure < 0.0:
                raise ValidationError(
                    field,
                    _("Ein Maß unter null gibt es nicht."),
                    value=measure,
                    constraint="negative",
                )
            # **Erst prüfen, dann umrechnen.** Die Meldung nennt sonst den
            # halbierten Wert, und der Kunde sucht eine Zahl, die er nie
            # getippt hat.
            measure *= _LENGTH_FACTOR[constraint.kind]
        elif constraint.kind in _ANGLE_KINDS:
            if not constraint.value:
                raise ValidationError(
                    field, _("Ein Maß braucht einen Wert."), constraint="required"
                )
            measure = evaluate(constraint.value, params)
            if not 0.0 < measure < MOST_ANGLE_DEGREES:
                # Genannt wird die getippte Zahl in Grad und nicht ihr
                # Bogenmaß: Der Kunde sucht die Zahl, die er eingegeben hat.
                raise ValidationError(
                    field,
                    _("Ein Winkelmaß liegt zwischen null und 180 Grad."),
                    value=measure,
                    constraint="angle_range",
                )
            measure = math.radians(measure)
        elif constraint.value:
            raise ValidationError(
                field,
                _("Nur ein Maß trägt einen Wert."),
                value=constraint.value,
                constraint="value_not_allowed",
            )
        if constraint.kind in CURVE_SLOTS:
            rows, fn, grad = _curve_equation(constraint, sketch.elements, offsets, anchors, field)
        else:
            rows, fn, grad = _constraint_equation(constraint, measure, anchors)
        equations.append(_Equation(index, rows, fn, grad))

    # Punkte mit ``fixed`` — für die ganz festen Elemente darunter.
    held = {
        constraint.targets[0] for constraint in sketch.constraints if constraint.kind == "fixed"
    }
    for position, element in enumerate(sketch.elements):
        begin = offsets[position]
        if element.kind in ("circle", "arc") and _span(anchors, begin, begin + 1) < EPS_GEOM:
            # ``positive`` und nicht ``element.kind``: Die Beschränkung sagt,
            # **was** verletzt wurde, nicht **woran**. Hier stand einmal
            # „circle", und weil das keine Spanne ist, las der Kunde über einem
            # Satz mit einer klaren Grenze den vagen Titel der Oberklasse. Um
            # welches Element es geht, steht ohnehin im Feld.
            raise ValidationError(
                f"elements[{position}]",
                _("Ein Kreis braucht einen Radius größer als null."),
                constraint="positive",
            )
        if element.kind in ("ellipse", "elliptical_arc") and (
            _span(anchors, begin, begin + 1) < EPS_GEOM
            or _span(anchors, begin, begin + 2) < EPS_GEOM
        ):
            raise ValidationError(
                f"elements[{position}]",
                _("Eine Ellipse braucht zwei Achsen, die länger als null sind."),
                constraint="positive",
            )
        for points, rows, fn, grad in _element_equations(element.kind, begin):
            if set(points) <= held and all(abs(value) <= _TOL for value in fn(anchors)):
                # **Eine eigene Gleichung, deren Punkte alle fest sind, braucht
                # es nicht** — sie gilt dort schon, und mitgezählt wäre sie
                # eine Zeile zu viel: beim Bogen die siebte über sechs
                # Koordinaten, bei der Ellipse die siebte über sechs, und
                # der Löser meldete „Eine Bedingung legt fest, was schon
                # festliegt" an jeder übernommenen Kontur und an jedem Element,
                # dessen Punkte jemand einzeln festnagelt (B28). Gilt sie an
                # den gespeicherten Punkten nicht, bleibt sie stehen, und der
                # Widerspruch wird gemeldet wie bisher.
                continue
            equations.append(_Equation(None, rows, fn, grad))

    return equations, anchors


def _residuals_at(equations: Sequence[_Equation], points: np.ndarray) -> np.ndarray:
    """Die Residuen aller Gleichungen an diesen Punkten — ohne zu lösen."""
    pts = np.asarray(points, dtype=float).reshape(-1, 2)
    rows: list[float] = []
    for equation in equations:
        rows.extend(equation.fn(pts))
    return np.asarray(rows, dtype=float)


def _solve(
    equations: Sequence[_Equation],
    start: np.ndarray,
    *,
    pinned: Sequence[int] = (),
    stiff: bool = False,
    tries: int | None = None,
) -> tuple[np.ndarray, np.ndarray, Any]:
    """Ein Lauf des Lösers: Koordinaten, Residuen, Jacobimatrix an der Lösung.

    Die Jacobimatrix kommt **dünn besetzt** zurück (``csr_matrix``). Dicht wird
    nur, was die Rangprüfung nach dem Abschälen noch braucht
    (:func:`_matrix_rank`), und im Fehlerfall die Suche nach dem Paar.

    ``pinned`` nennt Punkte, die ein Zug gerade hält (:func:`solve_sketch`).
    Ohne ``stiff`` sind sie **Konstanten**: Ihre Koordinaten stehen in
    ``start`` und verlassen das Gleichungssystem — der Löser rechnet nur die
    übrigen, und der gezogene Punkt landet exakt dort, wo der Zeiger ist. Mit
    ``stiff`` bleiben sie Variablen, nur zähe (:data:`DRAG_STIFFNESS`): Das
    ist der Rückfall, wenn die Bedingungen den Zeigerort nicht zulassen.

    ``tries`` begrenzt die Zahl der Auswertungen — nur der Zug setzt sie
    (:data:`DRAG_REACH_TRIES`, :data:`DRAG_SLIDE_TRIES`). Das gewöhnliche
    Lösen bleibt unbegrenzt: Dort ist die Lösung, was gefragt ist, und nicht
    die Antwort auf die nächste Mausbewegung.
    """
    flat = start.reshape(-1)
    total_rows = sum(equation.rows for equation in equations)
    points = flat.size // 2
    held = np.zeros(flat.size, dtype=bool)
    if pinned and not stiff:
        for point in pinned:
            held[2 * point : 2 * point + 2] = True
    free = ~held

    def fun(x: np.ndarray) -> np.ndarray:
        return _residuals_at(equations, x)

    def sparse_jac(x: np.ndarray) -> csr_matrix:
        # Dünn besetzt von Anfang an: Jede Ableitung berührt eine Handvoll
        # Punkte, und ein dichter Block über alle Punkte wuchs quadratisch —
        # 3,2 GB bei 10 000 Punkten und 10 000 Bedingungen, angefordert
        # bevor eine Zeile gerechnet war (Gesamtreview 05.09.2026, G-09).
        pts = x.reshape(-1, 2)
        rows: list[int] = []
        cols: list[int] = []
        data: list[float] = []
        begin = 0
        for equation in equations:
            block = _SparseRows(begin)
            equation.grad(pts, block)  # type: ignore[arg-type]
            for (row, point, coordinate), value in block.entries.items():
                rows.append(begin + row)
                cols.append(point * 2 + coordinate)
                data.append(value)
            begin += equation.rows
        return csr_matrix((data, (rows, cols)), shape=(total_rows, points * 2))

    if not equations:
        return flat, np.zeros(0), csr_matrix((0, flat.size))
    if not free.any() or tries == 0:
        # Alles hängt am Zeiger — oder gefragt ist nur, wie es an dieser
        # Stelle steht: Es gibt nichts zu rechnen, nur zu prüfen, ob die
        # Bedingungen hier gelten.
        return flat, fun(flat), sparse_jac(flat)

    # Die gehaltenen Koordinaten werden vor dem Lösen aus dem System genommen:
    # ``fun`` und ``sparse_jac`` sehen weiter alle Punkte, der Löser nur die
    # freien Spalten. So bleibt jede Gleichung, wie sie ist.
    full = flat.copy()

    def widened(z: np.ndarray) -> np.ndarray:
        full[free] = z
        return full

    def free_fun(z: np.ndarray) -> np.ndarray:
        return fun(widened(z))

    def free_jac(z: np.ndarray) -> csr_matrix:
        return sparse_jac(widened(z))[:, free]

    scale: float | np.ndarray = 1.0
    if pinned and stiff:
        scale = np.ones(flat.size)
        for point in pinned:
            scale[2 * point : 2 * point + 2] = DRAG_STIFFNESS

    # ``lsmr`` statt der dichten SVD je Iteration: bei 200 Bedingungen der
    # Unterschied zwischen 700 ms und dem Budget aus §31 — nachgemessen.
    result = least_squares(
        free_fun,
        flat[free],
        jac=free_jac,
        method="trf",
        tr_solver="lsmr",
        x_scale=scale,
        # Ohne Grenze läuft LSMR hier bis zur kleineren Matrixkante. Bei der
        # langen, dünn besetzten Kette des §31-Korpus sind das 300 innere
        # Schritte je Versuch und 105 ms insgesamt. Mit 150 Schritten braucht
        # der äußere Löser acht statt achtzehn Versuche, hält denselben Rest
        # weit unter ``_TOL`` und löst die 200 Bedingungen in 42 ms. Die
        # Grenze ist keine Genauigkeitsschranke: TRF setzt mit dem verbleibenden
        # Rest weiter an, statt eine unfertige Antwort zurückzugeben.
        tr_options={"maxiter": 150},
        xtol=1e-10,
        ftol=1e-10,
        gtol=1e-10,
        max_nfev=tries,
    )
    solution = widened(np.asarray(result.x, dtype=float)).copy()
    return (
        solution,
        np.asarray(result.fun, dtype=float),
        sparse_jac(solution),
    )


def _row_blocks(equations: Sequence[_Equation]) -> list[range]:
    """Welche Zeilen des Residuenvektors zu welcher Gleichung gehören."""
    blocks: list[range] = []
    begin = 0
    for equation in equations:
        blocks.append(range(begin, begin + equation.rows))
        begin += equation.rows
    return blocks


#: Wie nah zwei Restfehler beieinander liegen dürfen, um als gleich zu gelten —
#: relativ zum größten. Keine Toleranz im Sinne von Regel 7, sondern die
#: Rundung der Lösung: Ein Gleichstand, den die Rechnung auf die letzte
#: Stelle genau träfe, entschiede sonst das Rauschen.
_TIE_SHARE: Final[float] = 1e-9


def _worst_constraints(
    equations: Sequence[_Equation], blocks: Sequence[range], residuals: np.ndarray
) -> list[int]:
    """Bedingungsindizes nach ihrem größten Restfehler, absteigend, stabil.

    **Bei Gleichstand die später gesetzte zuerst.** Eine Kette aus drei
    Bedingungen, die einander widersprechen, teilt den Fehler gleichmäßig
    auf — ein fester Kreis, ein fester Punkt daneben und *Punkt auf Kurve*
    tragen gemessen je ein Drittel. Mit der früheren zuerst nannte die Meldung
    die beiden Fixierungen und nie die Bedingung, die eben dazukam; die Liste
    ist aber in der Reihenfolge des Setzens, und der Widerspruch kam mit der
    letzten (RM-188 P6.6b)."""
    worst: dict[int, float] = {}
    for equation, block in zip(equations, blocks, strict=True):
        if equation.constraint is None:
            continue
        peak = max((abs(float(residuals[row])) for row in block), default=0.0)
        worst[equation.constraint] = max(worst.get(equation.constraint, 0.0), peak)
    largest = max(worst.values(), default=0.0)
    if largest <= 0.0:
        return sorted(worst)
    step = largest * _TIE_SHARE
    return sorted(worst, key=lambda index: (-round(worst[index] / step), -index))


def _conflict_pair(
    equations: Sequence[_Equation], blocks: Sequence[range], residuals: np.ndarray
) -> tuple[int, int]:
    """Das Paar mit den größten Restfehlern.

    Bei mehr als zwei Beteiligten ist das kein vollständiges Bild, aber der
    ehrliche Einstieg: die beiden Bedingungen, an denen der Löser am
    weitesten scheitert, sind die, die man zuerst ansieht."""
    ranked = _worst_constraints(equations, blocks, residuals)
    first = ranked[0] if ranked else 0
    second = ranked[1] if len(ranked) > 1 else first
    return first, second


#: Ab wann ein Anteil des linken Nullraums an einer Bedingung als null gilt.
#:
#: Keine Toleranz im Sinne von Regel 7: Die Spalten des Nullraums sind
#: orthonormal, ein beteiligter Block trägt Anteile in der Größenordnung eins
#: durch die Wurzel der Beteiligten — bei tausend Bedingungen um drei
#: Hundertstel. Was darunter bleibt, ist Rundung der Zerlegung.
_NULL_SHARE: Final[float] = 1e-9


def _losses(jacobian: np.ndarray, rank: int, blocks: Sequence[range]) -> list[int]:
    """Um wie viel der Rang fiele, nähme man die Zeilen eines Blocks heraus.

    **Eine Zerlegung statt einer je Bedingung.** Hier stand für jede
    Bedingung ein eigenes ``matrix_rank`` über die übrigen Zeilen — an einer
    Skizze mit 200 Bedingungen 200 Zerlegungen, gemessen 3,5 Sekunden im
    Qt-Hauptthread für die Meldung „legt fest, was schon festliegt"
    (Durchsicht 22.09.2026).

    Dieselbe Frage lässt sich am **linken Nullraum** beantworten: Die Zeilen
    eines Blocks liegen genau dann im Raum der übrigen, wenn die
    Nullraumvektoren auf diesem Block den vollen Rang haben — sie schreiben
    jede seiner Zeilen als Summe der anderen. Der Rangverlust ist deshalb die
    Zeilenzahl des Blocks weniger dem Rang des Nullraums auf ihm.
    """
    rows = jacobian.shape[0]
    if rank >= rows:
        return [0 for _ in blocks]
    left, _values, _right = np.linalg.svd(jacobian, full_matrices=True)
    null = left[:, rank:]
    losses: list[int] = []
    for block in blocks:
        share = null[list(block), :]
        values = np.linalg.svd(share, compute_uv=False) if share.size else np.zeros(0)
        losses.append(len(block) - int(np.count_nonzero(values > _NULL_SHARE)))
    return losses


def _redundant_pair(
    constraints: Sequence[SketchConstraint],
    equations: Sequence[_Equation],
    blocks: Sequence[range],
    jacobian: np.ndarray,
    rank: int,
) -> tuple[int, int]:
    """Das Paar, das dasselbe festlegt.

    Kandidatin ist jede Bedingung, deren Entfernen den Rang nicht senkt —
    ihre Zeilen sagen nichts, was die übrigen nicht auch sagen. Zwei
    Kandidatinnen sind das Paar: jede macht die andere überflüssig. Bleibt
    nur eine (sie hängt an einer Kombination mehrerer), wird ihr die erste
    Bedingung zur Seite gestellt, die einen Zielpunkt mit ihr teilt — und
    zwar eine, die im Gleichungssystem steht: Ein Referenzmaß legt nichts
    fest und kann an keiner Redundanz beteiligt sein. Trägt jede Bedingung
    auch Eigenes bei (die Abhängigkeit verteilt sich über einen Verbund),
    wird die mit dem kleinsten eigenen Beitrag benannt — vorher stand hier
    ein ``(0, 0)``, das blind der ersten Bedingung der Skizze die Schuld
    gab, gleich ob sie beteiligt war.

    Den Rangverlust je Bedingung rechnet :func:`_losses` aus **einer**
    Zerlegung."""
    measured: list[tuple[int, int]] = []  # (Rangverlust ohne sie, Index)
    carried: list[tuple[int, range]] = []
    for equation, block in zip(equations, blocks, strict=True):
        if equation.constraint is not None:
            carried.append((equation.constraint, block))
    losses = _losses(jacobian, rank, [block for _index, block in carried])
    for (index, _block), loss in zip(carried, losses, strict=True):
        measured.append((loss, index))
    candidates = [index for loss, index in measured if loss == 0]
    if len(candidates) >= 2:
        return candidates[0], candidates[1]
    if not candidates and measured:
        candidates = [min(measured)[1]]
    if candidates:
        first = candidates[0]
        bearing = {index for _, index in measured}
        touched = set(constraints[first].targets)
        partner = next(
            (
                index
                for index, other in enumerate(constraints)
                if index != first and index in bearing and touched.intersection(other.targets)
            ),
            first,
        )
        return first, partner
    return 0, 0


def solve_sketch(
    sketch: Sketch,
    params: Mapping[str, float] | None = None,
    *,
    dragged: Mapping[int, Point2] | None = None,
    start: Sequence[Point2] | None = None,
) -> SolvedSketch:
    """Löst eine Skizze deterministisch gegen ihre Bedingungen (§30.1).

    Maße werden über die Parametergrammatik (§13) gegen ``params`` aufgelöst.
    Unterbestimmt liefert ein Ergebnis und zählt die Freiheitsgrade;
    überbestimmt oder widersprüchlich wirft :class:`SketchConflictError`
    mit dem kollidierenden Paar.

    **Der Zug** (``dragged``): flache Punktindizes mit dem Ort, an dem der
    Zeiger sie haben will. Ohne ihn beginnt der Löser bei den gespeicherten
    Punkten und findet die **nächste** Lösung — und die ist beim Ziehen die
    falsche: Ein Rechteckpunkt, den jemand um zwanzig Millimeter zog, kam
    bei fünf an, weil die Deckung mit seinem Nachbarn hälftig ausgeglichen
    wurde statt den Nachbarn nachzuziehen (gemessen 13.09.2026, Robert:
    „punkt verschieben geht nicht"). Mit ``dragged`` gilt, was jedes CAD
    tut: Der gezogene Punkt **steht am Zeiger**, alles andere folgt ihm mit
    der kleinsten Bewegung — gerechnet ab ``start``, dem zuletzt gelösten
    Stand, damit die übrige Zeichnung nicht bei jedem Mausereignis zu ihrer
    gespeicherten Lage zurückspringt.

    Zwei Stufen, weil eine nicht reicht: Erst werden die gezogenen Punkte
    **festgesetzt** und nur die übrigen gerechnet — exakt, und deshalb landet
    ein auf das Raster gefangener Punkt auf der Rasterzahl und nicht ein
    Vierhundertstel daneben. Lassen die Bedingungen den Ort nicht zu (ein
    fester Nachbar, ein Maß, eine Waagerechte), rechnet die zweite Stufe die
    gezogenen Punkte als zähe Variablen (:data:`DRAG_STIFFNESS`) mit: Sie
    rutschen so weit, wie die Bedingungen erlauben — ein Punkt auf einer
    Waagerechten folgt dem Zeiger seitlich und bleibt in der Höhe, ein Punkt
    an einem festen Maß läuft auf seinem Kreis. Was die Bedingungen ganz
    festhalten, kehrt zurück, und die Nachbarn bleiben, wo sie waren.

    Ein ``fixed`` hält dabei auch gegen den Zug: Es heftet an die
    gespeicherte Koordinate, und die ändert ein Zug nicht — wer den Punkt
    woandershin will, löst die Bedingung oder tippt Koordinaten."""
    values = params or {}
    equations, anchors = _build_equations(sketch, values)
    variables = anchors.size

    if not sketch.elements:
        return SolvedSketch(elements=(), free_dof=0, max_residual=0.0)

    pinned: list[int] = []
    if dragged:
        points_total = anchors.shape[0]
        for point in dragged:
            if not 0 <= point < points_total:
                raise ValidationError(
                    field="dragged",
                    detail=_("Der gezogene Punkt gehört nicht zu dieser Skizze."),
                    value=point,
                    constraint="unknown_target",
                )
            pinned.append(point)
        begin = np.asarray(anchors, dtype=float)
        if start is not None and len(start) == points_total:
            begin = np.asarray(list(start), dtype=float).reshape(-1, 2)
        begin = begin.copy()
        for point, target in dragged.items():
            begin[point] = (float(target[0]), float(target[1]))
    else:
        begin = anchors

    # Vor der ersten Allokation: Der Löser rechnet dünn besetzt, die
    # Rangprüfung danach braucht dicht, was nach dem Abschälen übrig bleibt —
    # und das wächst mit Bedingungen mal Punkten. Eine Skizze jenseits der
    # Grenze wird benannt statt gerechnet (G-09). Die spätere Rangprüfung
    # ergänzt je Kreis eine Eichzeile, auch wenn überhaupt keine explizite
    # Bedingung vorliegt.
    #
    # **Was ``fixed`` festhält, zählt nicht mit** (RM-188 P3.4): Jede seiner
    # Zeilen hält genau eine Koordinate und fällt im ersten Schälgang samt
    # Spalte heraus (:func:`_matrix_rank`). Gezählt wurde sie trotzdem, und
    # eine übernommene Flächenkontur mit 2624 Strecken (Besenhalter aus
    # ``F:\3D Dateien``, 23.09.2026) machte die Zeichnung unlösbar —
    # „mehr Punkte und Bedingungen, als Solidon auf einmal lösen kann" über
    # Geometrie, die sich nicht bewegen kann.
    total_rows = sum(equation.rows for equation in equations) + sum(
        element.kind == "circle" for element in sketch.elements
    )
    fixed = [
        constraint.targets[0] for constraint in sketch.constraints if constraint.kind == "fixed"
    ]
    dense_rows = total_rows - 2 * len(fixed)
    dense_columns = anchors.size - 2 * len(set(fixed))
    if max(dense_rows, 0) * max(dense_columns, 0) * 8 > MAX_JACOBIAN_BYTES:
        raise _too_large(sketch, anchors)
    solution, residuals, jacobian = _solve(
        equations, begin, pinned=pinned, tries=DRAG_REACH_TRIES if pinned else None
    )
    max_residual = float(np.max(np.abs(residuals))) if residuals.size else 0.0
    if pinned and max_residual > _TOL:
        # Der Zeigerort ist mit den Bedingungen nicht zu haben — zweite Stufe:
        # Die gezogenen Punkte rutschen so weit, wie es geht, und nur so weit
        # (siehe den Docstring). Ihr Rest wird danach wie jeder andere
        # geprüft: Was hier noch übrig bleibt, war schon vor dem Zug ein
        # Widerspruch der Skizze selbst.
        #
        # **Sie beginnt, wo die erste aufgehört hat**, mit den gezogenen
        # Punkten am Zeiger. Dort hat die erste Stufe die übrigen Punkte
        # schon so weit nachgezogen, wie es ohne die gezogenen ging; von der
        # alten Lage aus brauchte die zweite gemessen 116 Auswertungen, von
        # hier aus fünf (Kette aus fünf Linien, über ihre Länge gezogen).
        reached = solution.reshape(-1, 2).copy()
        for point in pinned:
            reached[point] = begin[point]
        solution, residuals, jacobian = _solve(
            equations, reached, pinned=pinned, stiff=True, tries=DRAG_SLIDE_TRIES
        )
        max_residual = float(np.max(np.abs(residuals))) if residuals.size else 0.0
        if max_residual > _TOL:
            # **Findet auch die zweite Stufe keine Lage, bleibt die Zeichnung
            # stehen** — sofern sie vor dem Zug in Ordnung war. Ein
            # Widerspruch der Skizze selbst bleibt einer und wird unten
            # gemeldet; ein Zug, den die Bedingungen nicht zulassen, ist
            # keiner: Der Punkt folgt dann nicht, und die Zeile sagt, was ihn
            # hält.
            held = np.asarray(
                list(start) if start is not None and len(start) == anchors.shape[0] else anchors,
                dtype=float,
            ).reshape(-1, 2)
            held_residuals = _residuals_at(equations, held)
            if not held_residuals.size or float(np.max(np.abs(held_residuals))) <= _TOL:
                solution, residuals, jacobian = _solve(equations, held, pinned=(), tries=0)
                max_residual = float(np.max(np.abs(residuals))) if residuals.size else 0.0
    rank = _matrix_rank(jacobian) if residuals.size else 0
    counted_rank = _rank_with_circle_gauges(sketch, solution, jacobian, rank, variables)
    blocks = _row_blocks(equations)

    # **Beide Zweige darunter greifen in ``sketch.constraints``**, und beide
    # Helfer geben im Rückfall ``0`` zurück, wenn gar keine tragende Bedingung
    # dabei war. Zusammen sähe das nach einem ``IndexError`` bei leerer
    # Bedingungsliste aus. Er ist keiner, und das ist ein Argument und keine
    # Hoffnung: Ohne tragende Bedingung stammt **jede** Zeile aus
    # ``_arc_equation``. Die stehen auf getrennten Punkten, sind einzeln
    # erfüllbar und voneinander unabhängig — Rest null, Rang voll, kein Zweig
    # läuft an. Die beiden ``assert`` halten genau diese Überlegung fest; wer
    # eine implizite Gleichung dazustellt, die das bricht, merkt es hier und
    # nicht als „Im Programm ist ein unerwarteter Fehler aufgetreten".
    if max_residual > _TOL:
        first, second = _conflict_pair(equations, blocks, residuals)
        assert max(first, second) < len(sketch.constraints), "conflict without a bearing constraint"
        raise SketchConflictError(
            first,
            second,
            values={
                "first_kind": sketch.constraints[first].kind,
                "second_kind": sketch.constraints[second].kind,
                "residual": max_residual,
            },
        )

    if residuals.size and rank < residuals.size:
        # Die Suche nach dem Paar braucht die ganze Matrix dicht — nur hier,
        # im Fehlerfall, und mit derselben Grenze.
        if int(np.prod(jacobian.shape)) * 8 > MAX_JACOBIAN_BYTES:
            raise _too_large(sketch, anchors)
        dense = np.asarray(jacobian.toarray(), dtype=float)
        first, second = _redundant_pair(sketch.constraints, equations, blocks, dense, rank)
        assert max(first, second) < len(sketch.constraints), (
            "redundancy without a bearing constraint"
        )
        raise SketchConflictError(
            first,
            second,
            title=_("Eine Bedingung legt fest, was schon festliegt."),
            values={
                "first_kind": sketch.constraints[first].kind,
                "second_kind": sketch.constraints[second].kind,
            },
        )

    solved_points = solution.reshape(-1, 2)
    elements: list[SketchElement] = []
    offset = 0
    for element in sketch.elements:
        count = len(element.points)
        points = tuple(
            (float(solved_points[offset + i][0]), float(solved_points[offset + i][1]))
            for i in range(count)
        )
        # Das Kennzeichen reist mit: der Solver rechnet Hilfsgeometrie wie
        # jede andere — nur die Profilbildung übergeht sie, und die sieht
        # ausschließlich das gelöste Ergebnis.
        elements.append(
            SketchElement(kind=element.kind, points=points, construction=element.construction)
        )
        offset += count

    return SolvedSketch(
        elements=tuple(elements),
        free_dof=variables - counted_rank,
        max_residual=max_residual,
    )


def _too_large(sketch: Sketch, anchors: np.ndarray) -> ValidationError:
    """Die Absage für eine Skizze, deren dichter Teil das Budget sprengt (G-09)."""
    return ValidationError(
        field="sketch",
        detail=_("Die Skizze hat mehr Punkte und Bedingungen, als Solidon auf einmal lösen kann."),
        constraint="too_large",
        values={
            "points": int(anchors.size // 2),
            "constraints": len(sketch.constraints),
            "limit": MAX_JACOBIAN_BYTES,
        },
    )


def _rank_with_circle_gauges(
    sketch: Sketch, solution: Any, jacobian: Any, rank: int, variables: int
) -> int:
    """Der Rang, der die Freiheitsgrade zählt — mit einer Eichzeile je Kreis.

    Ein Kreis führt vier Variablen (Mitte und Randpunkt) bei drei echten
    Freiheitsgraden: Der Randpunkt darf auf seinem Kreis wandern, und wo er
    sitzt, ändert am Kreis nichts. Bis zum 02.09.2026 zählte ``free_dof``
    diese Eichfreiheit mit, und die Statuszeile sagte „Noch ein Maß fehlt"
    über einem Kreis mit fester Mitte und bemaßtem Durchmesser, an dem nichts
    mehr fehlte — ein Lochkreis mit sechs Löchern stand mit sechs freien
    Graden da.

    Die Eichzeile ist die Tangentialrichtung am Randpunkt (am Rand ``+t``, an
    der Mitte ``-t``, damit eine Verschiebung des ganzen Kreises sie nicht
    berührt). Sie geht **nur** in diesen Rang ein — nicht in den Löser, der
    den Randpunkt weiter frei setzt, und nicht in die Redundanzprüfung, die
    nur Bedingungen des Nutzers gegeneinander hält. Wo eine Bedingung den
    Randpunkt schon festhält (waagerecht zur Mitte, auf einem Festpunkt), ist
    die Zeile abhängig und zählt nichts doppelt.
    """
    from scipy import sparse

    gauge_rows: list[int] = []
    gauge_columns: list[int] = []
    gauge_values: list[float] = []
    gauge_count = 0
    offset = 0
    points = np.asarray(solution, dtype=float).reshape(-1, 2)
    for element in sketch.elements:
        if element.kind == "circle":
            centre, rim = offset, offset + 1
            away = points[rim] - points[centre]
            reach = float(np.hypot(away[0], away[1]))
            if reach > EPS_GEOM:
                tangent = (float(-away[1] / reach), float(away[0] / reach))
                for point, sign in ((rim, 1.0), (centre, -1.0)):
                    for coordinate in (0, 1):
                        gauge_rows.append(gauge_count)
                        gauge_columns.append(2 * point + coordinate)
                        gauge_values.append(sign * tangent[coordinate])
                gauge_count += 1
        offset += len(element.points)
    if not gauge_rows:
        return rank
    gauges = sparse.csr_matrix(
        (gauge_values, (gauge_rows, gauge_columns)), shape=(gauge_count, variables)
    )
    stacked = sparse.vstack([sparse.csr_matrix(jacobian), gauges]) if jacobian.shape[0] else gauges
    return _matrix_rank(stacked)


def _matrix_rank(matrix: Any) -> int:
    """Der Rang einer Matrix — Einerzeilen vorweg abgeschält, der Rest zerlegt.

    **Eine Zeile mit genau einem Eintrag trägt genau eins zum Rang bei.** Zieht
    man ihr Vielfaches von den übrigen Zeilen ab, verschwindet ihre Spalte aus
    ihnen, und der Rest der Matrix bleibt, wie er war: Rang gleich eins plus
    Rang ohne diese Zeile und Spalte. Das ist exakt und keine Näherung. Mehrere
    Einerzeilen auf derselben Spalte zählen einmal — die übrigen werden dabei
    zu Nullzeilen.

    Gebraucht wird das für ``fixed``: Jede seiner zwei Zeilen hält genau eine
    Koordinate. Eine übernommene Flächenkontur trägt ein ``fixed`` an jedem
    Punkt, und die dichte Zerlegung über alle Zeilen kostete bei 512 festen
    Linien 1,8 Sekunden je Lösung (gemessen 23.09.2026) — bei jedem Klick in
    der Zeichnung. Abgeschält bleibt nur, was die Zeichnung selbst festlegt.
    Was nach einem Schälgang zur Einerzeile wird (eine Deckung mit einem
    festen Punkt), geht im nächsten mit.

    **Dünn besetzt, und dicht wird nur der Rest.** Geschält wird über die
    Zeilen- und Spaltenlisten der ``csr``-Matrix, in der Zahl ihrer Einträge;
    eine dichte Matrix über alle Punkte hätte bei 2624 festen Strecken
    881 MB gebraucht, bevor die erste Zeile fiel.
    """
    from scipy import sparse

    table = sparse.csr_matrix(matrix)
    table.eliminate_zeros()
    height, width = table.shape
    if not height or not width:
        return 0
    by_column = table.tocsc()
    counts = np.diff(table.indptr).astype(np.int64)
    row_alive = counts > 0
    column_alive = np.ones(width, dtype=bool)
    waiting = [int(row) for row in np.flatnonzero(counts == 1)]
    peeled = 0
    while waiting:
        row = waiting.pop()
        if not row_alive[row] or counts[row] != 1:
            continue
        entries = table.indices[table.indptr[row] : table.indptr[row + 1]]
        column = next(int(entry) for entry in entries if column_alive[entry])
        row_alive[row] = False
        column_alive[column] = False
        peeled += 1
        for other in by_column.indices[by_column.indptr[column] : by_column.indptr[column + 1]]:
            if not row_alive[other]:
                continue
            counts[other] -= 1
            if counts[other] == 1:
                waiting.append(int(other))
            elif counts[other] == 0:
                row_alive[other] = False
    rest = table[np.flatnonzero(row_alive)][:, np.flatnonzero(column_alive)]
    if not rest.shape[0] or not rest.shape[1]:
        return peeled
    return peeled + int(np.linalg.matrix_rank(rest.toarray()))
