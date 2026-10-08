"""Körper mit drei Klicks aufziehen — die Rechnung ohne Fenster (RM-559, Bauplan §30.1).

Das Werkzeug *Zeichnen* der oberen Leiste: Klick 1 setzt den Anfang auf das Bett
oder eine ebene Fläche, Klick 2 die Gegenecke (oder den Rand eines Kreises), Klick
3 die Höhe. **Die Richtung des dritten Klicks entscheidet**: aus der Fläche
heraus fügt an, in den Körper hinein schneidet, bis zur Gegenwand ist
durchgehend — ohne Schalter und ohne Zusatztaste. Das Ergebnis ist ein Schritt
der vorhandenen Skizzen-Operationen (``sketch_extrude``, ``sketch_join``,
``sketch_pocket``), dessen Art der Schrittdialog umschaltet.

Hier steht alles, was ein Klick **bedeutet**: Fang, Phasen, Rücknahme, die
Wahl der Operation und was im Bild zu zeichnen ist. Die Ansicht und das Fenster
(``draw_flow.py``) übersetzen nur Mausstellen in diese Aufrufe — dieselbe
Teilung wie ``place``/``grab_point`` im Skizzeneditor, damit ein Test die
Bedeutung ohne Renderer prüft (Regeln in ``zeichenflaeche.md``).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any, Final

from app.core.sketch import shapes
from app.core.sketch.planes import BASE_FRAMES, feature_plane, frame_of, to_world
from app.core.sketch.profile import SketchCurve, curves_of
from app.core.sketch.serialize import sketch_to_text
from app.core.types import ObjectId, PlaneFrame, Point2, Sketch, SolvedSketch
from app.core.units import EPS_GEOM
from app.i18n import tr
from app.ui.labels import circle_measure, circle_shown, circle_sign, circle_stored, length

#: Die zwei Formen des Werkzeugs, mit ihrer Taste (R und C wie im Skizzeneditor).
DRAW_SHAPES: Final = ("rectangle", "circle")
SHAPE_KEYS: Final = {"R": "rectangle", "C": "circle"}

#: Das Kürzel des Werkzeugs (Entwurf RM-559, E9). Im Fusion-Schema kommt E dazu,
#: über ``sketch_extrude`` in :data:`app.ui.shortcut_schemes.FUSION`.
DRAW_KEY: Final = "Ctrl+Shift+E"

#: Die drei Operationen, die ein aufgezogener Körper werden kann.
EXTRUDE_OP: Final = "sketch_extrude"
JOIN_OP: Final = "sketch_join"
POCKET_OP: Final = "sketch_pocket"

#: Wie weit eine Ecke oder Kantenmitte der Fläche das Raster schlägt — in
#: Bildpunkten, wie die Fangmarke des Editors (``viewport.CURSOR_PIXELS``).
MARK_REACH_PIXELS: Final = 10.0

#: Wie viele Fangmarken eine Fläche höchstens anbietet. Ein Kreisrand trägt so
#: viele Ecken, wie er Sehnen hat; jede fängt, aber mehr als diese Zahl ändert
#: am Fang nichts und kostet je Zeigerschritt.
MOST_MARKS: Final = 400

#: Wie lang die Striche der gestrichelten Drahtform sind, als Anteil der Höhe —
#: und höchstens wie viele es je Kante werden.
DASH_SHARE: Final = 0.08
MOST_DASHES: Final = 24


def operation_limits(op_name: str, field: str) -> tuple[float, float]:
    """Unter- und Obergrenze eines gezogenen Maßes — **aus dem Schema**.

    Gefragt statt abgeschrieben: Eine zweite Zahl in der Ansicht fiele erst
    auf, wenn der Schrittdialog einen Wert ablehnt, den der Zeiger gerade
    gezeigt hat. Fehlt eine Grenze im Schema, kommt null zurück — dann wird
    nicht geklemmt, und das ist richtiger als eine erfundene Grenze.
    """
    from app.core.errors import InternalError
    from app.core.registry import REGISTRY

    for entry in REGISTRY.get(op_name).params.spec():
        if entry.name == field:
            return (float(entry.minimum or 0.0), float(entry.maximum or 0.0))
    raise InternalError(detail=f"{op_name!r} has no {field!r} parameter", values={"op": op_name})


def height_limits() -> tuple[float, float]:
    """Grenzen der Höhe nach außen — Hochziehen und Anfügen teilen ihr Schema."""
    return operation_limits(EXTRUDE_OP, "height")


def depth_limits() -> tuple[float, float]:
    """Grenzen der Tiefe nach innen."""
    return operation_limits(POCKET_OP, "depth")


@dataclass(frozen=True, slots=True)
class DrawSurface:
    """Worauf gezeichnet wird: das Bett, eine ebene Fläche oder eine Skizzenebene.

    ``body`` ist der Körper, dem die Fläche gehört — das Ziel (E3). Ohne Körper
    entsteht ein neuer. ``joins`` sagt, ob ein Zug nach außen an ``body``
    anfügt; auf einer Fläche immer (E4), auf einer Grundebene nur, wenn der
    Umriss den Körper trifft (die Entscheidung des Skizzeneditors).
    ``cut_top`` ist der Abstand entlang der Normalen, an dem ein Schnitt nach
    innen beginnt (auf einer Fläche null, unter einem Körper seine Oberkante),
    ``through_depth`` die Tiefe von dort bis zur Gegenwand.
    """

    plane: str
    frame: PlaneFrame
    body: ObjectId | None = None
    joins: bool = False
    cut_top: float = 0.0
    through_depth: float = 0.0
    marks: tuple[Point2, ...] = ()
    name: str = ""
    """Der Name des Körpers für Sätze — „Der neue Körper überdeckt *Name*“."""

    @property
    def on_bed(self) -> bool:
        """Ob auf dem Bett gezeichnet wird: dann gibt es nur nach oben (F-e)."""
        return self.body is None and self.plane == "plane:xy"

    @property
    def cuts(self) -> bool:
        """Ob nach innen etwas zu schneiden ist."""
        return self.body is not None and self.through_depth > EPS_GEOM


def bed_surface() -> DrawSurface:
    """Das Bett der Platte: die Grundebene XY, ohne Körper."""
    return DrawSurface(plane="plane:xy", frame=BASE_FRAMES["plane:xy"])


def face_surface(entry: Any, feature_id: str) -> DrawSurface | None:
    """Die ebene Fläche ``feature_id`` des Körpers ``entry`` — oder nichts.

    Nichts heißt: Sie ist keine ebene Fläche (F-a) oder trägt keine Richtung.
    Der Rahmen ist derselbe, den die Skizzen-Operationen bei der Auswertung
    rechnen (:func:`app.core.sketch.planes.frame_for`): Ursprung in der
    Flächenmitte, Normale aus dem Merkmal.
    """
    feature = entry.features.get(feature_id)
    if feature is None or feature.kind != "face":
        return None
    normal = feature.params.get("normal")
    centre = feature.params.get("centre")
    if normal is None or centre is None or len(normal) != 3 or len(centre) != 3:
        return None
    frame = frame_of(
        (float(normal[0]), float(normal[1]), float(normal[2])),
        (float(centre[0]), float(centre[1]), float(centre[2])),
    )
    marks = face_marks(entry.mesh, feature.face_indices, frame)
    return DrawSurface(
        plane=feature_plane(str(entry.id), feature_id),
        frame=frame,
        body=entry.id,
        joins=True,
        through_depth=reach_inside(entry.mesh.bounds, frame),
        marks=marks,
        name=str(entry.name or entry.id),
    )


def reach_inside(bounds: Any, frame: PlaneFrame, top: float = 0.0) -> float:
    """Wie tief es von der Ebene (plus ``top``) entlang der Gegennormalen bis zur Gegenwand ist.

    Aus den acht Ecken des Hüllquaders, wie ``sketch_pocket`` selbst rechnet
    (``ops._span_along``): Für *durchgehend* braucht es die Spanne des Körpers,
    keine Silhouette.
    """
    low, high = bounds.minimum, bounds.maximum
    normal = frame.normal
    plane = sum(o * n for o, n in zip(frame.origin, normal, strict=True)) + top
    deepest = min(
        x * normal[0] + y * normal[1] + z * normal[2]
        for x in (low[0], high[0])
        for y in (low[1], high[1])
        for z in (low[2], high[2])
    )
    return max(0.0, float(plane - deepest))


def _rim(mesh: Any, face_indices: tuple[int, ...]) -> tuple[Any, Any] | None:
    """Ecken des Anzeigenetzes und die Randkanten einer Fläche — oder nichts.

    Der Rand ist, was nur ein Dreieck der Fläche als Kante trägt. Gelesen am
    Anzeigenetz (``mesh.raw``), das auch der Klick getroffen hat.
    """
    raw = getattr(mesh, "raw", None)
    if raw is None or not face_indices:
        return None
    import numpy as np

    faces = np.asarray(raw.faces)
    chosen = [index for index in face_indices if 0 <= index < len(faces)]
    if not chosen:
        return None
    triangles = faces[chosen]
    edges = np.sort(
        np.concatenate([triangles[:, [0, 1]], triangles[:, [1, 2]], triangles[:, [2, 0]]]), axis=1
    )
    unique, counts = np.unique(edges, axis=0, return_counts=True)
    rim = unique[counts == 1]
    if len(rim) == 0:
        return None
    return np.asarray(raw.vertices, dtype=float), rim


def face_marks(mesh: Any, face_indices: tuple[int, ...], frame: PlaneFrame) -> tuple[Point2, ...]:
    """Ecken und Kantenmitten einer Fläche in ihren Ebenenkoordinaten — sie schlagen das Raster.

    Ohne Dreiecke gibt es keine Marken, und der Fang bleibt beim Raster.
    """
    found = _rim(mesh, face_indices)
    if found is None:
        return ()
    import numpy as np

    vertices, rim = found
    origin = np.asarray(frame.origin, dtype=float)
    axes = np.asarray((frame.x_axis, frame.y_axis), dtype=float)

    def flat(points: Any) -> Any:
        return (points - origin) @ axes.T

    corners = flat(vertices[np.unique(rim)])
    middles = flat((vertices[rim[:, 0]] + vertices[rim[:, 1]]) / 2.0)
    marks = np.concatenate([corners, middles])[:MOST_MARKS]
    return tuple((float(x), float(y)) for x, y in marks)


def face_outline(
    mesh: Any, face_indices: tuple[int, ...]
) -> tuple[tuple[tuple[float, float, float], tuple[float, float, float]], ...]:
    """Der Umriss einer Fläche als Strecken im Raum — er leuchtet mit ihrer Füllung (Phase 0)."""
    found = _rim(mesh, face_indices)
    if found is None:
        return ()
    vertices, rim = found
    return tuple(
        (
            (float(vertices[a][0]), float(vertices[a][1]), float(vertices[a][2])),
            (float(vertices[b][0]), float(vertices[b][1]), float(vertices[b][2])),
        )
        for a, b in rim
    )


def snapped(
    point: Point2, step: float, marks: tuple[Point2, ...] = (), reach: float = 0.0
) -> Point2:
    """Wohin ein Klick an ``point`` fällt: auf eine nahe Marke, sonst auf das Raster.

    Dieselbe Rangfolge wie im Skizzeneditor — ein vorhandener Punkt schlägt
    das Raster (``zeichenflaeche.md``). ``reach`` ist die Fangweite der Marken
    in Millimetern, ``step`` die Rasterweite; null heißt kein Raster.
    """
    if marks and reach > 0.0:
        nearest = min(marks, key=lambda mark: math.dist(mark, point))
        if math.dist(nearest, point) <= reach:
            return nearest
    if step <= 0.0:
        return point
    return (round(point[0] / step) * step, round(point[1] / step) * step)


@dataclass(frozen=True, slots=True)
class Lift:
    """Die Höhe des dritten Klicks: mit Vorzeichen, gefangen und geklemmt.

    Positiv nach außen, negativ nach innen. ``through`` heißt: bis zur
    Gegenwand, *durchgehend*. ``note`` ist ein Satz, wenn die Richtung nicht
    geht (F-e) — dann bleibt die Höhe an der Untergrenze stehen.
    """

    height: float
    through: bool = False
    note: str = ""


def lifted(
    reach: float,
    step: float,
    surface: DrawSurface,
    outward: tuple[float, float],
    inward: tuple[float, float],
) -> Lift:
    """Aus dem Rohmaß am Zeiger die Höhe, die der dritte Klick setzt.

    Gefangen auf das Raster, geklemmt in die Grenzen **des Schemas** der
    jeweiligen Operation (``outward`` für Hochziehen und Anfügen, ``inward``
    für die Tasche). Nach innen rastet die Gegenwand als *durchgehend* ein,
    sobald der Zeiger sie auf einen halben Rasterschritt erreicht. Ohne Körper
    gibt es kein Innen: Die Höhe bleibt an der Untergrenze, und der Satz sagt
    es (F-e).
    """
    if step > 0.0:
        reach = round(reach / step) * step
    if reach >= 0.0 or not surface.cuts:
        least, most = outward
        if reach < 0.0:
            note = (
                tr("Unter das Bett geht nichts — nach oben ziehen.")
                if surface.on_bed
                else tr("Hier ist kein Körper zum Schneiden — nach außen ziehen.")
            )
            return Lift(least, note=note)
        amount = max(reach, least)
        return Lift(min(amount, most) if most > least else amount)
    least, most = inward
    depth = -reach
    wall = surface.through_depth
    if depth >= wall - max(step, EPS_GEOM) / 2.0:
        return Lift(-wall, through=True)
    depth = max(depth, least)
    if most > least:
        depth = min(depth, most)
    return Lift(-depth)


@dataclass(frozen=True, slots=True)
class DrawnStep:
    """Der eine Schritt, den der dritte Klick anlegt (E1, E5)."""

    op: str
    inputs: tuple[ObjectId, ...]
    params: dict[str, Any]


class DrawDraft:
    """Was zwischen dem ersten und dem dritten Klick entsteht — kein Dokumentzustand (Regel 2).

    Drei Phasen: ``0`` wartet auf den Anfang, ``1`` auf die Gegenecke, ``2`` auf
    die Höhe. Strg+Z geht eine Phase zurück (:meth:`back`), Escape verwirft den
    ganzen Entwurf (E7). Ein freier Umriss aus dem Skizzeneditor beginnt
    gleich in Phase 2 (:meth:`with_outline`).
    """

    def __init__(self, shape: str = "rectangle") -> None:
        self.shape = shape if shape in DRAW_SHAPES else "rectangle"
        self.surface: DrawSurface | None = None
        self.first: Point2 | None = None
        self.second: Point2 | None = None
        self.outline: Sketch | None = None
        """Ein Umriss aus dem Editor statt Rechteck oder Kreis — dann fehlt nur die Höhe."""
        self.shift: tuple[float, float, float] = (0.0, 0.0, 0.0)
        """Wie weit das Bild gegen die Szene versetzt steht (mehrere Platten, §25)."""
        self._toward: tuple[float, float] = (1.0, 1.0)
        """In welchen Quadranten getippte Maße von der ersten Ecke aus zeigen."""

    @property
    def phase(self) -> int:
        if self.outline is not None:
            return 2
        if self.surface is None or self.first is None:
            return 0
        if self.second is None:
            return 1
        return 2

    def choose(self, shape: str) -> bool:
        """Rechteck oder Kreis — nur, solange die Grundfläche nicht steht."""
        if shape not in DRAW_SHAPES or self.phase == 2:
            return False
        self.shape = shape
        return True

    def with_outline(self, outline: Sketch, surface: DrawSurface) -> None:
        """Ein Umriss aus dem Skizzeneditor: Es fehlt nur noch die Höhe (RM-561)."""
        self.outline = outline
        self.surface = surface
        self.first = None
        self.second = None

    def begin(self, surface: DrawSurface, point: Point2) -> None:
        """Klick 1: Die Ebene steht fest, der Anfang liegt auf ihr."""
        self.surface = surface
        self.first = point
        self.second = None

    def place(self, point: Point2) -> str:
        """Klick 2: die Gegenecke oder der Rand. Ein Satz statt einer Form, wenn es keine gibt.

        Zwei Klicks am selben Fleck geben keine Form (F-c); der erste bleibt,
        wie beim Formwerkzeug des Editors.
        """
        if self.first is None:
            return ""
        if self.size_of(point) is None:
            return str(tr("Zwei verschiedene Punkte klicken."))
        self.second = point
        return ""

    def type_size(self, first: float, second: float | None = None) -> str:
        """Getippte Maße statt Klick 2 — Breite und Tiefe oder das Kreismaß.

        Die Richtung kommt aus der Lage der Gegenecke, die der Zeiger zuletzt
        zeigte (``toward``); ohne Zeiger geht es nach rechts oben. Beim Kreis
        ist die Zahl, was das Feld zeigt — Durchmesser oder Radius
        (``labels.circle_shown``).
        """
        if self.first is None:
            return ""
        toward = self._toward
        if self.shape == "circle":
            diameter = circle_stored(first)
            return self.place((self.first[0] + diameter / 2.0, self.first[1]))
        depth = second if second is not None else first
        return self.place((self.first[0] + toward[0] * first, self.first[1] + toward[1] * depth))

    def aim(self, point: Point2) -> None:
        """Merkt die Richtung, in die der Zeiger von der ersten Ecke aus zeigt."""
        if self.first is None:
            return
        self._toward = (
            -1.0 if point[0] < self.first[0] else 1.0,
            -1.0 if point[1] < self.first[1] else 1.0,
        )

    def back(self) -> bool:
        """Strg+Z im Entwurf: eine Phase zurück. Falsch, wenn nichts mehr zurückgeht."""
        if self.outline is not None:
            return False
        if self.second is not None:
            self.second = None
            return True
        if self.first is not None:
            self.first = None
            self.surface = None
            return True
        return False

    def size_of(self, point: Point2) -> tuple[float, float] | None:
        """Breite und Tiefe (Rechteck) oder Durchmesser zweimal (Kreis) bis ``point``."""
        if self.first is None:
            return None
        if self.shape == "circle":
            diameter = 2.0 * math.dist(self.first, point)
            return (diameter, diameter) if diameter > EPS_GEOM else None
        width = abs(point[0] - self.first[0])
        depth = abs(point[1] - self.first[1])
        if width <= EPS_GEOM or depth <= EPS_GEOM:
            return None
        return (width, depth)

    def sketch(self, pointer: Point2 | None = None) -> Sketch | None:
        """Der Umriss — fest nach Klick 2, sonst bis zum Zeiger."""
        if self.outline is not None:
            return self.outline
        if self.surface is None or self.first is None:
            return None
        end = self.second if self.second is not None else pointer
        if end is None or self.size_of(end) is None:
            return None
        if self.shape == "circle":
            return shapes.circle_around(
                self.first, 2.0 * math.dist(self.first, end), self.surface.plane
            )
        return shapes.rectangle_between(self.first, end, self.surface.plane)

    def step(self, lift: Lift) -> DrawnStep | None:
        """Der Schritt aus Umriss und Höhe: neuer Körper, anfügen oder schneiden (E1 bis E4)."""
        surface = self.surface
        drawing = self.sketch()
        if surface is None or drawing is None or abs(lift.height) <= EPS_GEOM:
            return None
        text = sketch_to_text(drawing)
        if lift.height < 0.0 and surface.body is not None:
            return DrawnStep(
                POCKET_OP,
                (surface.body,),
                {"sketch": text, "depth": abs(lift.height), "through": lift.through},
            )
        if lift.height < 0.0:
            return None
        if surface.body is not None and surface.joins:
            return DrawnStep(JOIN_OP, (surface.body,), {"sketch": text, "height": lift.height})
        return DrawnStep(EXTRUDE_OP, (), {"sketch": text, "height": lift.height})


@dataclass(frozen=True, slots=True)
class DrawPicture:
    """Was die Ansicht vom Entwurf zeigt — Weltpunkte der Szene, ohne Versatz.

    ``solid`` sind durchgezogene Striche, ``dashed`` gestrichelte: Nach innen
    steht die Drahtform gestrichelt und heißt *Tiefe*, nach außen
    durchgezogen und *Höhe* — Wort und Linienart neben der Farbe (Regel 18).
    """

    solid: tuple[tuple[tuple[float, float, float], tuple[float, float, float]], ...] = ()
    dashed: tuple[tuple[tuple[float, float, float], tuple[float, float, float]], ...] = ()
    labels: tuple[tuple[tuple[float, float, float], str], ...] = ()
    mark: tuple[float, float, float] | None = None
    inward: bool = False


def _dashes(
    start: tuple[float, float, float], end: tuple[float, float, float], dash: float
) -> list[tuple[tuple[float, float, float], tuple[float, float, float]]]:
    """Eine Strecke als Strichfolge: Strich, Lücke, Strich — höchstens :data:`MOST_DASHES`."""
    span = math.dist(start, end)
    if span <= EPS_GEOM or dash <= EPS_GEOM:
        return [(start, end)]
    count = min(MOST_DASHES, max(1, int(span / (2.0 * dash))))
    pieces = []
    for index in range(count):
        a = (2 * index) / (2 * count - 1)
        b = (2 * index + 1) / (2 * count - 1)
        pieces.append(
            (
                tuple(s + (e - s) * a for s, e in zip(start, end, strict=True)),
                tuple(s + (e - s) * b for s, e in zip(start, end, strict=True)),
            )
        )
    return pieces  # type: ignore[return-value]


def _closed(points: tuple[tuple[float, float, float], ...]) -> list[tuple[Any, Any]]:
    return [(points[index], points[index + 1]) for index in range(len(points) - 1)]


def cage(
    curves: tuple[SketchCurve, ...], frame: PlaneFrame, base: float, height: float
) -> tuple[list[tuple[Any, Any]], list[tuple[Any, Any]]]:
    """Die Drahtform eines Umrisses von ``base`` bis ``base + height`` entlang der Normalen.

    Zurück kommen Ober- und Unterkante samt Sprossen an den Umrissecken,
    getrennt in Kanten und Sprossen — die Ansicht strichelt beides, wenn nach
    innen gezogen wird. Dieselbe Bauart wie ``viewport.pull_cage``, nur mit
    eigener Unterkante: Nach innen beginnt die Form an der Oberkante des
    Körpers (``cut_top``).
    """

    def along(point: Any, distance: float) -> tuple[float, float, float]:
        n = frame.normal
        return (point[0] + n[0] * distance, point[1] + n[1] * distance, point[2] + n[2] * distance)

    rims: list[tuple[Any, Any]] = []
    ribs: list[tuple[Any, Any]] = []
    for curve in curves:
        if curve.construction or len(curve.points) < 2:
            continue
        low = tuple(along(point, base) for point in curve.points)
        rims.extend(_closed(low))
        if abs(height) <= EPS_GEOM:
            continue
        high = tuple(along(point, base + height) for point in curve.points)
        rims.extend(_closed(high))
        count = len(curve.points)
        stride = max(1, -(-(count - 1) // 11))
        for index in range(0, count, stride):
            ribs.append((low[index], high[index]))
    return rims, ribs


def picture(
    draft: DrawDraft,
    pointer: Point2 | None = None,
    lift: Lift | None = None,
) -> DrawPicture:
    """Das Bild eines Entwurfs: Grundfläche mit Maßen, nach Klick 2 die Drahtform mit Höhe."""
    surface = draft.surface
    if surface is None:
        return DrawPicture()
    frame = surface.frame
    mark = to_world(frame, pointer) if pointer is not None and draft.phase < 2 else None
    drawing = draft.sketch(pointer)
    if drawing is None:
        return DrawPicture(mark=mark)
    curves = curves_of(SolvedSketch(drawing.elements, 0, 0.0), frame)
    labels: list[tuple[tuple[float, float, float], str]] = []
    if draft.phase < 2 and draft.first is not None:
        end = draft.second if draft.second is not None else pointer
        size = draft.size_of(end) if end is not None else None
        if size is not None and end is not None:
            labels.extend(_size_labels(draft, end, size, frame))
    if draft.phase < 2 or lift is None or abs(lift.height) <= EPS_GEOM:
        rims, _ribs = cage(curves, frame, 0.0, 0.0)
        return DrawPicture(solid=tuple(rims), labels=tuple(labels), mark=mark)
    inward = lift.height < 0.0
    base = surface.cut_top if inward else 0.0
    rims, ribs = cage(curves, frame, base, lift.height)
    flat, _ = cage(curves, frame, 0.0, 0.0)
    top = max(
        (point for pair in rims for point in pair),
        key=lambda point: sum(
            point[index] * frame.normal[index] * (1 if not inward else -1) for index in range(3)
        ),
    )
    word = (
        tr("Durchgehend")
        if lift.through
        else tr("Tiefe {value}").format(value=length(abs(lift.height)))
        if inward
        else tr("Höhe {value}").format(value=length(abs(lift.height)))
    )
    labels.append((top, str(word)))
    if not inward:
        return DrawPicture(solid=tuple(flat + rims + ribs), labels=tuple(labels))
    dash = max(abs(lift.height) * DASH_SHARE, EPS_GEOM)
    dashed = [piece for start, end in rims + ribs for piece in _dashes(start, end, dash)]
    return DrawPicture(solid=tuple(flat), dashed=tuple(dashed), labels=tuple(labels), inward=True)


def _size_labels(
    draft: DrawDraft, end: Point2, size: tuple[float, float], frame: PlaneFrame
) -> list[tuple[tuple[float, float, float], str]]:
    """Die Maßkarten der Grundfläche: zwei Seiten am Rechteck, das Kreismaß am Kreis."""
    first = draft.first
    assert first is not None
    if draft.shape == "circle":
        return [
            (
                to_world(frame, ((first[0] + end[0]) / 2.0, (first[1] + end[1]) / 2.0)),
                f"{circle_sign()} {length(circle_shown(size[0]))}",
            )
        ]
    low_y = min(first[1], end[1])
    high_x = max(first[0], end[0])
    return [
        (to_world(frame, ((first[0] + end[0]) / 2.0, low_y)), length(size[0])),
        (to_world(frame, (high_x, (first[1] + end[1]) / 2.0)), length(size[1])),
    ]


def sentence(draft: DrawDraft, *, free: bool = False) -> str:
    """Was der nächste Klick tut, in einem Satz — je Phase einer."""
    phase = draft.phase
    if phase == 0:
        if free:
            return str(tr("Auf das Bett oder eine ebene Fläche klicken. Dort beginnt die Linie."))
        return str(tr("Auf das Bett oder eine ebene Fläche klicken."))
    if phase == 1:
        if draft.shape == "circle":
            if circle_measure() == "radius":
                return str(tr("Rand klicken oder Radius tippen."))
            return str(tr("Rand klicken oder Durchmesser tippen."))
        return str(tr("Gegenecke klicken oder Breite tippen."))
    surface = draft.surface
    if surface is not None and surface.cuts:
        return str(tr("Höhe ziehen oder tippen — nach innen schneidet."))
    return str(tr("Höhe ziehen oder tippen."))


def outline_surface(
    plane: str,
    frame: PlaneFrame,
    body: Any | None,
    *,
    joins: bool,
    cut_top: float,
) -> DrawSurface:
    """Die Fläche für einen Umriss aus dem Skizzeneditor (RM-561): seine Ebene, sein Ziel."""
    if body is None:
        return DrawSurface(plane=plane, frame=frame)
    return DrawSurface(
        plane=plane,
        frame=frame,
        body=body.id,
        joins=joins,
        cut_top=cut_top,
        through_depth=reach_inside(body.mesh.bounds, frame, cut_top),
        name=str(body.name or body.id),
    )
