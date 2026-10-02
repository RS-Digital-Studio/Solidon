"""SVG-Zeichnungen für den Umrissimport lesen (Bauplan §25) — ohne lxml.

Die Elemente liest ``xml.etree``, die Pfaddaten zerlegt svg.path, und heraus
kommen die Argumente eines trimesh-``Path2D``. Linienzüge, Bézierkurven und
Kreisbögen werden zu denselben trimesh-Entitäten wie in trimeshs eigenem
SVG-Leser (``trimesh.path.exchange.svg_io``), in derselben Reihenfolge: erst
alle Pfade, dann alle Grundformen. Eine Zeichnung, die beide Leser verstehen,
ergibt deshalb dieselben Konturen.

**Abweichend von trimesh, mit Absicht** — jede Zeile war dort ein still
falsches Teil:

- ``rotate()`` dreht um Grad. trimesh rechnete den Winkel noch einmal von
  Bogenmaß in Grad um; ``rotate(90)`` drehte um gut 107°.
- ``skewX()`` und ``skewY()`` gelten, statt übergangen zu werden.
- Eine Ellipse, ein abgerundetes Rechteck, ein elliptischer Bogen und jeder
  Bogen unter einer verzerrenden Transformation (ungleich skaliert, geschert)
  wird zur Punktfolge mit höchstens ``units.MAX_FACET_SAG`` Abweichung. Ein
  Kreisbogen durch drei Punkte, wie trimesh ihn legt, ist dort keiner.
- Was nicht gezeichnet wird, fehlt: ``defs``, ``clipPath``, ``mask``,
  ``symbol``, ``marker``, ``pattern`` und ausgeblendete Elemente
  (``display:none``, etwa eine versteckte Ebene). ``use`` setzt das Gemeinte
  an seiner Stelle ein.
- Transformationen gelten über beliebig viele Ebenen, nicht nur über zehn.

Eine Länge mit Einheit außer ``px`` lässt sich ohne die Abbildung der
Datei nicht in ihre Koordinaten umrechnen; sie gilt als unlesbar, wie eine
fehlerhafte Transformation auch. ``outline.read_profiles`` sagt dann, dass die
Zeichnung sich nicht lesen ließ.
"""

from __future__ import annotations

import math
import re
from collections.abc import Iterator, Mapping
from typing import Any, Final
from xml.etree import ElementTree as ET

import numpy as np
from svg.path import Arc, Close, CubicBezier, Line, Move, QuadraticBezier, parse_path

from app.core.units import MAX_FACET_SAG

#: Grundformen, die eine Kontur ergeben.
SHAPES: Final = frozenset({"path", "rect", "circle", "ellipse", "line", "polyline", "polygon"})

#: Behälter, deren Inhalt nur über einen Verweis gezeichnet wird — oder nie.
NOT_RENDERED: Final = frozenset(
    {"defs", "clipPath", "mask", "symbol", "marker", "pattern", "metadata", "title", "desc"}
)

#: Wie viele Grundformen eine Zeichnung höchstens zeichnet. Über ``use`` kann
#: eine kleine Datei sich selbst vervielfachen (zehn Verweise auf zehn Verweise
#: …); die Grenze liegt weit über jedem Logo und jeder Frontplatte.
MAX_SHAPES: Final = 200_000

_NUMBER: Final = re.compile(r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?")
_TRANSFORM: Final = re.compile(r"\s*,?\s*([A-Za-z]+)\s*\(([^)]*)\)")
_HIDDEN: Final = re.compile(r"(?:^|;)\s*display\s*:\s*none\s*(?:;|$)")
_XLINK_HREF: Final = "{http://www.w3.org/1999/xlink}href"

#: Gleichheit zweier Bogenradien und Prüfung auf eine winkeltreue Abbildung.
_RELATIVE: Final = 1e-9


def path_arguments(payload: bytes) -> dict[str, Any]:
    """Die Argumente für ``trimesh.load_path`` aus einer SVG-Datei.

    Wirft ``ET.ParseError`` für kaputtes XML (auch für jede externe Entität —
    ``xml.etree`` lädt keine) und ``ValueError`` für eine unlesbare Zahl,
    Länge oder Transformation.
    """
    root = ET.fromstring(payload)
    by_id = {str(element.get("id")): element for element in root.iter() if element.get("id")}
    paths: list[tuple[Mapping[str, str], np.ndarray]] = []
    shapes: list[tuple[str, Mapping[str, str], np.ndarray]] = []
    for count, (tag, attrib, matrix) in enumerate(_drawn(root, np.eye(3), by_id, frozenset())):
        if count >= MAX_SHAPES:
            raise ValueError(f"mehr als {MAX_SHAPES} Grundformen")
        if tag == "path":
            paths.append((attrib, matrix))
        else:
            shapes.append((tag, attrib, matrix))

    drawing = _Drawing()
    for attrib, matrix in paths:
        drawing.add_path(attrib.get("d", ""), matrix)
    for tag, attrib, matrix in shapes:
        drawing.add_shape(tag, attrib, matrix)
    return drawing.arguments()


def parse_transform(text: str) -> np.ndarray:
    """Eine SVG-Transformationsliste als homogene 3x3-Matrix (SVG 1.1, Abschnitt 7.6)."""
    result = np.eye(3)
    position = 0
    text = text.strip()
    while position < len(text):
        match = _TRANSFORM.match(text, position)
        if match is None:
            if text[position:].strip(" ,\t\r\n"):
                raise ValueError(f"unlesbare Transformation: {text!r}")
            break
        name, values = match.group(1), [float(v) for v in _NUMBER.findall(match.group(2))]
        result = result @ _transform_matrix(name, values)
        position = match.end()
    return result


def _transform_matrix(name: str, values: list[float]) -> np.ndarray:
    """Eine einzelne Transformation; die Zahl der Werte ist Teil der Grammatik."""
    matrix = np.eye(3)
    count = len(values)
    if name == "matrix" and count == 6:
        a, b, c, d, e, f = values
        matrix[:2] = [[a, c, e], [b, d, f]]
    elif name == "translate" and count in (1, 2):
        matrix[:2, 2] = [values[0], values[1] if count == 2 else 0.0]
    elif name == "scale" and count in (1, 2):
        matrix[0, 0] = values[0]
        matrix[1, 1] = values[1] if count == 2 else values[0]
    elif name == "rotate" and count in (1, 3):
        angle = math.radians(values[0])
        cos, sin = math.cos(angle), math.sin(angle)
        matrix[:2, :2] = [[cos, -sin], [sin, cos]]
        if count == 3:
            centre = np.array(values[1:])
            matrix[:2, 2] = centre - matrix[:2, :2] @ centre
    elif name == "skewX" and count == 1:
        matrix[0, 1] = math.tan(math.radians(values[0]))
    elif name == "skewY" and count == 1:
        matrix[1, 0] = math.tan(math.radians(values[0]))
    else:
        raise ValueError(f"unlesbare Transformation: {name}({', '.join(map(str, values))})")
    return matrix


def _local(tag: object) -> str | None:
    """Der Elementname ohne Namensraum; Kommentare und Anweisungen haben keinen."""
    return tag.rsplit("}", 1)[-1] if isinstance(tag, str) else None


def _hidden(element: ET.Element) -> bool:
    return element.get("display", "").strip() == "none" or bool(
        _HIDDEN.search(element.get("style", ""))
    )


def _drawn(
    element: ET.Element,
    matrix: np.ndarray,
    by_id: Mapping[str, ET.Element],
    chain: frozenset[str],
) -> Iterator[tuple[str, Mapping[str, str], np.ndarray]]:
    """Jede gezeichnete Grundform mit ihrer Gesamttransformation, in Dokumentreihenfolge.

    ``chain`` hält die Kennungen, über die ``use`` gerade hierher geführt hat; ein
    Verweis auf eine davon ist eine Schleife und zeichnet nichts (SVG 1.1, Abschnitt 5.6).
    """
    tag = _local(element.tag)
    if tag is None or tag in NOT_RENDERED or _hidden(element):
        return
    own = element.get("transform")
    if own:
        matrix = matrix @ parse_transform(own)
    if tag == "use":
        reference = (element.get("href") or element.get(_XLINK_HREF) or "").strip()
        key = reference[1:] if reference.startswith("#") else ""
        target = by_id.get(key)
        if target is None or key in chain:
            return
        shift = np.eye(3)
        shift[:2, 2] = [_length(element, "x"), _length(element, "y")]
        inner = chain | {key}
        if _local(target.tag) == "symbol":
            for child in target:
                yield from _drawn(child, matrix @ shift, by_id, inner)
        else:
            yield from _drawn(target, matrix @ shift, by_id, inner)
        return
    if tag in SHAPES:
        yield tag, element.attrib, matrix
    own_id = element.get("id")
    inner = chain | {own_id} if own_id else chain
    for child in element:
        yield from _drawn(child, matrix, by_id, inner)


def _length(attrib: ET.Element | Mapping[str, str], name: str, default: float = 0.0) -> float:
    """Eine Länge in Nutzereinheiten; ``px`` ist die Nutzereinheit selbst."""
    raw = attrib.get(name)
    if raw is None or not raw.strip():
        return default
    return float(raw.strip().removesuffix("px"))


def _similar(matrix: np.ndarray) -> bool:
    """Bildet die Matrix Kreise auf Kreise ab (Drehung, Spiegelung, gleiche Skalierung)?"""
    first, second = matrix[:2, 0], matrix[:2, 1]
    scale = max(float(np.dot(first, first)), float(np.dot(second, second)), 1e-300)
    return (
        abs(float(np.dot(first, first)) - float(np.dot(second, second))) <= _RELATIVE * scale
        and abs(float(np.dot(first, second))) <= _RELATIVE * scale
    )


def _circular(arc: Arc) -> bool:
    radius = arc.radius
    return abs(radius.real - radius.imag) <= _RELATIVE * max(abs(radius.real), abs(radius.imag))


def _pairs(values: list[complex]) -> np.ndarray:
    return np.array([[value.real, value.imag] for value in values], dtype=np.float64)


class _Drawing:
    """Sammelt trimesh-Entitäten und ihre schon transformierten Eckpunkte."""

    def __init__(self) -> None:
        self.vertices: list[np.ndarray] = []
        self.entities: list[Any] = []
        self.count = 0

    def arguments(self) -> dict[str, Any]:
        if not self.vertices:
            return {"vertices": [], "entities": []}
        return {"vertices": np.vstack(self.vertices), "entities": self.entities}

    def _add(self, kind: str, points: np.ndarray, matrix: np.ndarray, **options: Any) -> None:
        index = np.arange(len(points)) + self.count
        self.entities.append(_entity(kind, index, **options))
        self.vertices.append(_transformed(points, matrix))
        self.count += len(points)

    def _add_closed(self, points: np.ndarray, matrix: np.ndarray) -> None:
        """Ein geschlossener Linienzug, dessen letzter Punkt auf den ersten verweist."""
        index = np.arange(len(points) + 1) + self.count
        index[-1] = index[0]
        self.entities.append(_entity("Line", index))
        self.vertices.append(_transformed(points, matrix))
        self.count += len(points)

    def add_path(self, data: str, matrix: np.ndarray) -> None:
        """Ein Pfad, gruppiert wie in trimeshs Leser: Linienläufe, Bogenläufe, Einzelstücke."""
        if not data.strip():
            return
        raw = list(parse_path(data))
        start = 0
        while start < len(raw):
            kind = _kind(raw[start])
            end = start + 1
            while end < len(raw) and _kind(raw[end]) == kind:
                end += 1
            block = raw[start:end]
            start = end
            if kind == "line":
                points = _pairs([segment.start for segment in block] + [block[-1].end])
                self._add("Line", points, matrix)
            elif kind == "arc":
                self._add_arcs([arc for arc in block if isinstance(arc, Arc)], matrix)
            else:
                for segment in block:
                    if isinstance(segment, QuadraticBezier):
                        points = _pairs([segment.start, segment.control, segment.end])
                        self._add("Bezier", points, matrix)
                    elif isinstance(segment, CubicBezier):
                        points = _pairs(
                            [segment.start, segment.control1, segment.control2, segment.end]
                        )
                        self._add("Bezier", points, matrix)

    def _add_arcs(self, block: list[Arc], matrix: np.ndarray) -> None:
        """Ein Lauf von Bögen: ein geschlossener Kreis wird eine Entität wie bei trimesh."""
        exact = _similar(matrix) and all(_circular(arc) for arc in block)
        if exact and len(block) > 1 and _closes_a_circle(block):
            first = block[0]
            points = _pairs([first.start, first.point(0.5), first.end])
            self._add("Arc", points, matrix, closed=True)
            return
        for arc in block:
            if exact:
                points = _pairs([arc.start, arc.point(0.5), arc.end])
                self._add("Arc", points, matrix, closed=False)
            else:
                self._add("Line", _sampled(arc, matrix), matrix)

    def add_shape(self, tag: str, attrib: Mapping[str, str], matrix: np.ndarray) -> None:
        if tag == "rect":
            self._add_rect(attrib, matrix)
        elif tag in ("circle", "ellipse"):
            cx, cy = _length(attrib, "cx"), _length(attrib, "cy")
            if tag == "circle":
                rx = ry = _length(attrib, "r")
            else:
                rx, ry = _length(attrib, "rx", -1.0), _length(attrib, "ry", -1.0)
                rx, ry = (ry if rx < 0 else rx), (rx if ry < 0 else ry)
            if rx <= 0 or ry <= 0:
                return
            if rx == ry and _similar(matrix):
                self._add("Arc", _three_points(cx, cy, rx), matrix, closed=True)
            else:
                self.add_path(
                    f"M {cx + rx},{cy} A {rx},{ry} 0 1 1 {cx - rx},{cy} "
                    f"A {rx},{ry} 0 1 1 {cx + rx},{cy} Z",
                    matrix,
                )
        elif tag in ("polyline", "polygon"):
            values = [float(v) for v in _NUMBER.findall(attrib.get("points", ""))]
            points = np.array(values[: len(values) // 2 * 2], dtype=np.float64).reshape((-1, 2))
            if len(points) < 2:
                return
            if tag == "polygon" and not (points[0] == points[-1]).all():
                self._add_closed(points, matrix)
            else:
                self._add("Line", points, matrix)
        elif tag == "line":
            points = np.array(
                [
                    [_length(attrib, "x1"), _length(attrib, "y1")],
                    [_length(attrib, "x2"), _length(attrib, "y2")],
                ],
                dtype=np.float64,
            )
            self._add("Line", points, matrix)

    def _add_rect(self, attrib: Mapping[str, str], matrix: np.ndarray) -> None:
        """Ein Rechteck; mit ``rx``/``ry`` über seine Bögen (SVG 1.1, Abschnitt 9.2)."""
        x, y = _length(attrib, "x"), _length(attrib, "y")
        width, height = _length(attrib, "width"), _length(attrib, "height")
        if width <= 0 or height <= 0:
            return
        rx, ry = _length(attrib, "rx", -1.0), _length(attrib, "ry", -1.0)
        rx, ry = (ry if rx < 0 else rx), (rx if ry < 0 else ry)
        rx, ry = min(max(rx, 0.0), width / 2), min(max(ry, 0.0), height / 2)
        right, bottom = x + width, y + height
        if rx <= 0 or ry <= 0:
            points = np.array(
                [[x, y], [right, y], [right, bottom], [x, bottom], [x, y]], dtype=np.float64
            )
            self._add("Line", points, matrix)
            return
        self.add_path(
            f"M {x + rx},{y} H {right - rx} A {rx},{ry} 0 0 1 {right},{y + ry} "
            f"V {bottom - ry} A {rx},{ry} 0 0 1 {right - rx},{bottom} "
            f"H {x + rx} A {rx},{ry} 0 0 1 {x},{bottom - ry} "
            f"V {y + ry} A {rx},{ry} 0 0 1 {x + rx},{y} Z",
            matrix,
        )


def _kind(segment: object) -> str:
    """Die Gruppe eines Pfadstücks, wie trimesh sie zusammenfasst."""
    if isinstance(segment, Line | Close):
        return "line"
    if isinstance(segment, Arc):
        return "arc"
    return "move" if isinstance(segment, Move) else "curve"


def _closes_a_circle(block: list[Arc]) -> bool:
    """Bilden die Bögen zusammen einen geschlossenen Kreis? Prüfung wie bei trimesh."""
    rows = np.array(
        [
            [
                arc.start.real,
                arc.start.imag,
                arc.end.real,
                arc.end.imag,
                arc.center.real,
                arc.center.imag,
                arc.radius.real,
                arc.radius.imag,
                arc.rotation,
            ]
            for arc in block
        ],
        dtype=np.float64,
    )
    if np.ptp(rows[:, 4:], axis=0).mean() >= 1e-3:
        return False
    # ``trimesh.util.allclose``: die Spannweite der Differenz, nicht ihr Betrag.
    return float(np.ptp(rows[:, :2] - np.roll(rows[:, 2:4], 1, axis=0))) < 1e-8


def _sampled(arc: Arc, matrix: np.ndarray) -> np.ndarray:
    """Punkte auf dem Bogen, so dicht, dass die Sehne nach der Abbildung ``MAX_FACET_SAG`` hält."""
    stretch = float(np.linalg.svd(matrix[:2, :2], compute_uv=False)[0])
    radius = max(abs(arc.radius.real), abs(arc.radius.imag)) * stretch
    sweep = math.radians(abs(arc.delta))
    if radius > MAX_FACET_SAG:
        step = 2.0 * math.acos(1.0 - MAX_FACET_SAG / radius)
        count = max(2, math.ceil(sweep / step))
    else:
        count = 2
    return _pairs([arc.point(t) for t in np.linspace(0.0, 1.0, count + 1)])


def _entity(kind: str, index: np.ndarray, **options: Any) -> Any:
    """Eine trimesh-Entität; trimesh wird erst hier geladen, nicht beim Import."""
    from trimesh.path import entities

    return getattr(entities, kind)(points=index, **options)


def _transformed(points: np.ndarray, matrix: np.ndarray) -> np.ndarray:
    """Wie ``trimesh.transformations.transform_points``, Rechenweg für Rechenweg."""
    if np.abs(matrix - np.eye(3)).max() < 1e-8:
        return np.ascontiguousarray(points.copy())
    stack = np.column_stack((points, np.ones(len(points))))
    return np.asarray(np.dot(matrix, stack.T).T[:, :2], dtype=np.float64)


def _three_points(cx: float, cy: float, radius: float) -> np.ndarray:
    """Drei Punkte eines Halbkreises wie ``trimesh.path.arc.to_threepoint``."""
    angles = np.array([0.0, np.pi / 2.0, np.pi], dtype=np.float64)
    three = np.column_stack((np.cos(angles), np.sin(angles))) * radius + np.array([cx, cy])
    return np.asarray(three, dtype=np.float64)
