"""Der pygfx-Renderer — dieselbe Schnittstelle, gezeichnet über wgpu (§18).

Der zweite Renderer hinter dem Vertrag aus :mod:`app.ui.render.api`: Netze,
Linien, Punkte und Beschriftungen werden pygfx-Objekte in einer Szene, die
Kamera ist eine ``PerspectiveCamera`` (mit ``fov = 0`` orthografisch), das
Bild entsteht über ``WgpuRenderer`` — auf einer Qt-Leinwand
(``rendercanvas.qt.QRenderWidget``) oder ohne Fenster in einen Puffer.

Was hier anders gelöst ist als bei VTK, weil pygfx es anders kann:

* **Gepickt wird aus dem Bild.** Ein eigener Durchgang enthält nur Pickbares;
  unveränderte Szene und Kamera verwenden ihn erneut. Die Treffertoleranz
  liest ein kleines Rechteck in einem Zug statt jeden Nachbarpunkt einzeln.
* **Vorn bleibt, was ohne Tiefentest zeichnet.** ``keep_in_front`` heißt hier
  ``depth_test = False`` in der Überlagerungswarteschlange, nicht ein
  Polygonversatz. Ein Maß im Material ist damit vollständig sichtbar, nicht
  nur nach vorn gerückt.
* **Beschriftungen sind Textobjekte im Bildraum**; das Feld dahinter ist ein
  bildbreiter Linienzug, den jedes Bild an die Kamera anpasst.
* **Umgebungsverdeckung liegt vor der Überlagerung.** Ein eigener
  GPU-Durchgang schattiert nur deckende Flächen; durchscheinende Körper,
  Linien, Beschriftungen und Achsen folgen danach.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict, deque
from collections.abc import Callable, Sequence
from typing import Any

import numpy as np

from app.core.units import EPS_GEOM
from app.ui.render import shapes
from app.ui.render.api import (
    AxesMarkerStyle,
    Bounds,
    CameraPose,
    CellColours,
    Colour,
    Item,
    LabelsItem,
    LabelStyle,
    MouseButton,
    Pick,
    PointerEvent,
    Renderer,
    SurfaceStyle,
    Vec3,
    rgb,
)

_log = logging.getLogger(__name__)

#: Wie weit neben einem Objekt der Zeiger es noch trifft, in Bildpunkten —
#: dieselbe Zahl wie beim VTK-Renderer, damit ein Griff auf beiden gleich
#: greifbar ist.
PICK_SLACK_PIXELS = 4.0

#: Der senkrechte Öffnungswinkel, mit dem die Kamera beginnt — VTKs Vorgabe,
#: damit ``reset_camera`` auf beiden Renderern denselben Abstand wählt.
DEFAULT_VIEW_ANGLE = 30.0

#: Wie stark ein Licht in pygfx-Einheiten leuchtet, wenn der Viewport ``1.0``
#: verlangt. Gemessen am 05.09.2026 an einem Würfel #404040 unter demselben
#: Lichtsatz: pygfx teilt die Stärke durch π und schattiert in linearem
#: Licht, VTK rechnet auf den sRGB-Werten — dieselbe Zahl gibt deshalb bei
#: pygfx eine hellere Fläche, je dunkler die Farbe, desto mehr. Ein Faktor
#: kann das nicht für jede Ansicht ausgleichen; 2,0 trifft die schräge
#: Standardansicht auf 15 Prozent (VTK 98, pygfx 113) und die Draufsicht
#: ebenso (49 gegen 45). Was bleibt, ist ein weicherer Verlauf, kein Fehler.
HEADLIGHT_GAIN = 2.0

#: Das Grundlicht neben dem Lichtsatz. Null wie bei VTK, dessen Aktoren ohne
#: ``ambient`` nur von den Lichtern leben; was ein Stil als ``ambient``
#: verlangt, bekommt er als Eigenleuchten.
AMBIENT_INTENSITY = 0.0

#: Der Lichtsatz, den VTKs ``vtkLightKit`` aufstellt und den PyVista dem
#: Viewport mitgab — je Licht Anteil an der Schlüsselstärke 0,75, Höhe und
#: Seite in Grad gegen die Blickrichtung (Höhe nach oben, Seite nach rechts).
#: Das Frontlicht daneben stellt ``set_headlight``; seine Vorgabe ist ein
#: Drittel des Schlüssellichts, wie im Satz.
LIGHT_KIT: tuple[tuple[str, float, float, float], ...] = (
    ("key", 0.75, 50.0, 10.0),
    ("fill", 0.25, -75.0, -10.0),
    ("back_left", 0.75 / 3.5, 0.0, 110.0),
    ("back_right", 0.75 / 3.5, 0.0, -110.0),
)
DEFAULT_HEADLIGHT = 0.25

#: Die Warteschlange, in der pygfx Überlagerungen zeichnet (nach allem anderen).
OVERLAY_QUEUE = 4000

#: Abstand der Achsenkreuz-Kamera vom Ursprung, in Pfeillängen.
AXES_CAMERA_DISTANCE = 4.2

#: Wie viele verborgene Text-Feld-Paare eine Beschriftung für später behält.
#:
#: Beim Drehen wechselt die sichtbare Namensliste in fast jedem Bild; jedes
#: neue ``gfx.Text`` kostet Glyphenlayout und einen Shaderaufbau (gemessen
#: am Drillholder mit 157 Namen: fünf neue je Bild, rund 25 ms). Ruhende
#: Paare bleiben deshalb verborgen im Baum, bis ihr Name wiederkommt.
IDLE_LABEL_LIMIT = 256


def _vec(values: Sequence[float] | np.ndarray) -> Vec3:
    return (float(values[0]), float(values[1]), float(values[2]))


def _rgba(colour: Colour, alpha: float = 1.0) -> tuple[float, float, float, float]:
    red, green, blue = rgb(colour)
    return (red, green, blue, float(alpha))


def _alpha_mode(opacity: float) -> str:
    """Durchscheinendes mischt gewichtet und reihenfolgeunabhängig.

    pygfx sortiert Objekte nach ihrer Position, und die Körper des Viewports
    tragen ihren Ort in den Ecken — zwei Körper sitzen für pygfx damit am
    selben Punkt, und der zuerst gezeichnete verdeckte den anderen (gemessen
    am 05.09.2026: der ferne rote Würfel fehlte im Bild). Gewichtete Mischung
    braucht keine Reihenfolge; das ist der Maleralgorithmus, den VTK nicht
    lieferte, hier eingebaut.
    """
    return "weighted_blend" if opacity < 1.0 else "auto"


def _positions(points: np.ndarray) -> np.ndarray:
    return np.ascontiguousarray(np.asarray(points, dtype=np.float32).reshape(-1, 3))


def _face_colours(colours: CellColours, count: int) -> np.ndarray:
    """Eine Farbe je Dreieck als ``(m, 4)`` — Farbleiter, Slots oder direkt."""
    values = np.asarray(colours.values)
    result = np.ones((count, 4), dtype=np.float32)
    if colours.colormap is None:
        table = np.clip(values.reshape(-1, 3), 0.0, 1.0)
        result[: len(table), :3] = table[:count]
        return result
    numbers = values.reshape(-1).astype(np.float64)
    stops = np.asarray([rgb(colour) for colour in colours.colormap], dtype=np.float64)
    limits = colours.limits or (
        float(np.nanmin(numbers)) if len(numbers) else 0.0,
        float(np.nanmax(numbers)) if len(numbers) else 1.0,
    )
    low, high = limits
    if high <= low:
        high = low + 1e-6
    missing = ~np.isfinite(numbers)
    if colours.categorical:
        index = np.clip(np.rint(np.nan_to_num(numbers, nan=0.0)), 0, len(stops) - 1).astype(int)
        mapped = stops[index]
    else:
        share = np.clip((np.nan_to_num(numbers, nan=low) - low) / (high - low), 0.0, 1.0)
        positions = np.linspace(0.0, 1.0, len(stops))
        mapped = np.column_stack(
            [np.interp(share, positions, stops[:, channel]) for channel in range(3)]
        )
    mapped[missing] = rgb(colours.nan_colour)
    result[: len(mapped), :3] = mapped[:count]
    return result


class GfxItem(Item):
    """Eine Gruppe von pygfx-Objekten unter einem gemeinsamen Transform."""

    def __init__(
        self,
        name: str,
        root: Any,
        objects: Sequence[Any],
        colour: Colour,
        *,
        opacity: float = 1.0,
        pickable: bool = True,
    ) -> None:
        self.name = name
        #: Der Träger des Transforms; Versatz und Matrix stehen hier.
        self.root = root
        #: Die Objekte, die gezeichnet werden — Netz, Rückseite, Kanten …
        self.objects = list(objects)
        self._colour = colour
        self._opacity = float(opacity)
        self._pickable = bool(pickable)
        self._position: Vec3 = (0.0, 0.0, 0.0)
        self._matrix = np.eye(4)
        #: Das Drahtgitter über der Fläche, wenn Kanten gewünscht sind — es
        #: teilt die Geometrie des Netzes und zieht mit ``update_points`` nach.
        self.edge_line: Any = None
        #: Polylinien tragen zusätzliche NaN-Trenner, die keine Quellpunkte sind.
        self.point_map: np.ndarray | None = None
        self.point_count: int | None = None
        self.changed: Callable[[], None] | None = None
        #: Der zuletzt gerechnete Hüllquader; jede Änderung am Item verwirft ihn.
        self._bounds: Bounds | None = None

    def _changed(self) -> None:
        self._bounds = None
        if self.changed is not None:
            self.changed()

    # --- Vertrag ------------------------------------------------------------------

    def set_visible(self, visible: bool) -> None:
        self.root.visible = bool(visible)
        self._changed()

    def visible(self) -> bool:
        return bool(self.root.visible)

    def set_opacity(self, opacity: float) -> None:
        self._opacity = float(opacity)
        for obj in self._coloured() + ([self.edge_line] if self.edge_line is not None else []):
            obj.material.opacity = self._opacity
            if not getattr(obj, "_solidon_text", False):
                obj.material.alpha_mode = (
                    "solid"
                    if getattr(obj, "_solidon_force_opaque", False)
                    else _alpha_mode(self._opacity)
                )
        self._changed()

    def opacity(self) -> float:
        return self._opacity

    def set_colour(self, colour: Colour) -> None:
        self._colour = colour
        for obj in self._coloured():
            obj.material.color = colour
            ambient = getattr(obj, "_solidon_ambient", None)
            if ambient is not None:
                obj.material.emissive = (*(part * ambient for part in rgb(colour)), 1.0)
        self._changed()

    def colour(self) -> Colour:
        return self._colour

    def set_position(self, position: Vec3) -> None:
        self._position = _vec(position)
        self._apply_transform()

    def position(self) -> Vec3:
        return self._position

    def set_matrix(self, matrix: np.ndarray) -> None:
        self._matrix = np.asarray(matrix, dtype=float).reshape(4, 4).copy()
        self._apply_transform()

    def matrix(self) -> np.ndarray:
        return self._matrix.copy()

    def _apply_transform(self) -> None:
        # Versatz und Matrix wirken zusammen, wie ``SetPosition`` und
        # ``SetUserMatrix`` bei VTK: erst die Matrix, dann der Versatz.
        shift = np.eye(4)
        shift[:3, 3] = self._position
        self.root.local.matrix = shift @ self._matrix
        self._changed()

    def bounds(self) -> Bounds:
        # pygfx rechnet den Quader je Aufruf rekursiv über alle Kinder
        # (rund 65 µs je Item); die Szene fragt ihn zweimal je Bild.
        if self._bounds is not None:
            return self._bounds
        box = self.root.get_world_bounding_box()
        if box is None:
            self._bounds = (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        else:
            low, high = np.asarray(box, dtype=float)
            self._bounds = (
                float(low[0]),
                float(high[0]),
                float(low[1]),
                float(high[1]),
                float(low[2]),
                float(high[2]),
            )
        return self._bounds

    def set_pickable(self, pickable: bool) -> None:
        self._pickable = bool(pickable)
        for obj in self.objects:
            obj.material.pick_write = self._pickable and getattr(obj, "_solidon_pickable", True)
        self._changed()

    def pickable(self) -> bool:
        return self._pickable

    def update_points(self, points: np.ndarray) -> None:
        source = np.asarray(points, dtype=float).reshape(-1, 3)
        fresh = _positions(points)
        if self.point_count is not None and len(fresh) != self.point_count:
            raise ValueError(f"{self.name}: {len(fresh)} Punkte für {self.point_count}")
        if self.point_map is not None:
            mapped = np.full((len(self.point_map), 3), np.nan, dtype=np.float32)
            valid = self.point_map >= 0
            mapped[valid] = fresh[self.point_map[valid]]
            fresh = mapped
        replacements: dict[int, Any] = {}
        for obj in self._geometry_holders():
            geometry = obj.geometry
            current = geometry.positions
            if fresh.shape[0] != current.nitems:
                raise ValueError(f"{self.name}: {fresh.shape[0]} Punkte für {current.nitems}")
            if hasattr(obj, "_solidon_positions"):
                obj._solidon_positions = source
            if id(geometry) in replacements:
                obj.geometry = replacements[id(geometry)]
                continue
            current.set_data(fresh)
            # Normalen und Hüllquader hängen an den Ecken; ein neues Netz
            # rechnet beides frisch, ein überschriebenes nicht zuverlässig.
            obj.geometry = _geometry_like(geometry, fresh)
            replacements[id(geometry)] = obj.geometry
        self._changed()

    def set_line_width(self, width: float) -> None:
        for obj in self.objects:
            material = obj.material
            if hasattr(material, "thickness"):
                material.thickness = float(width)
            elif hasattr(material, "wireframe_thickness"):
                material.wireframe_thickness = float(width)
        self._changed()

    # --- Hilfen -------------------------------------------------------------------

    def _coloured(self) -> list[Any]:
        """Die Objekte, die die Farbe des Griffs tragen — nicht die Kantenlinie
        und nicht die anders gefärbte Rückseite."""
        return [obj for obj in self.objects if getattr(obj, "_solidon_coloured", True)]

    def _geometry_holders(self) -> list[Any]:
        return [obj for obj in self.objects if getattr(obj, "_solidon_mesh", False)]


def _geometry_like(geometry: Any, positions: np.ndarray) -> Any:
    """Dieselbe Geometrie mit neuen Ecken — Indizes und Farben bleiben."""
    import pygfx as gfx

    fields: dict[str, Any] = {"positions": positions}
    for name in ("indices", "colors", "texcoords"):
        attribute = getattr(geometry, name, None)
        if attribute is not None:
            fields[name] = attribute
    return gfx.Geometry(**fields)


def _line_geometry(points: np.ndarray) -> Any:
    import pygfx as gfx

    return gfx.Geometry(positions=_positions(points))


class GfxLabels(GfxItem, LabelsItem):
    """Beschriftungen: je Anker ein Textobjekt im Bildraum, dazu Feld und Punkt."""

    def __init__(self, name: str, root: Any, style: LabelStyle) -> None:
        super().__init__(name, root, [], style.text_colour, pickable=style.pickable)
        self.style = style
        self.texts: list[Any] = []
        self.fields: list[Any] = []
        self.anchors = np.zeros((0, 3), dtype=np.float32)
        self.labels: list[str] = []
        self.dots: Any = None
        self.rebuilt: Callable[[GfxItem], None] | None = None
        self._field_state: tuple[Any, ...] | None = None
        #: Verborgene Paare je Name, in der Reihenfolge ihres Ausscheidens.
        self._idle: deque[tuple[str, Any, Any | None]] = deque()

    def build(self, points: np.ndarray, texts: Sequence[str]) -> None:
        """Sichtbare Namen abgleichen; vorhandene Schrift- und Feldobjekte behalten.

        Ein Name, der gerade nicht sichtbar ist, verliert seine Glyphen nicht:
        Sein Paar bleibt verborgen im Baum (:data:`IDLE_LABEL_LIMIT`) und
        kehrt beim nächsten Bild, das ihn zeigt, ohne neuen Shaderaufbau zurück.
        """
        import pygfx as gfx

        anchors = _positions(points)
        if anchors.shape[0] != len(texts):
            raise ValueError(f"{self.name}: {anchors.shape[0]} Anker für {len(texts)} Texte")
        labels = [str(text) for text in texts]
        available: dict[str, deque[tuple[Any, Any | None]]] = defaultdict(deque)
        for index, (text, label) in enumerate(zip(self.labels, self.texts, strict=True)):
            available[text].append((label, self.fields[index] if self.fields else None))
        idle: dict[str, deque[tuple[Any, Any | None]]] = defaultdict(deque)
        for text, label, field in self._idle:
            idle[text].append((label, field))
        old_objects = set(self.objects)
        objects, label_objects, fields = [], [], []
        for anchor, text in zip(anchors, labels, strict=True):
            matching = available.get(text)
            resting = idle.get(text)
            if matching:
                label, field = matching.popleft()
            elif resting:
                label, field = resting.popleft()
                self._idle.remove((text, label, field))
                self._wake(label, field)
            else:
                label, field = self._new_label(anchor, text)
            label.local.position = anchor
            if field is not None:
                fields.append(field)
                objects.append(field)
            label_objects.append(label)
            objects.append(label)
        for text, pairs in available.items():
            for label, field in pairs:
                self._rest(text, label, field)
        while len(self._idle) > IDLE_LABEL_LIMIT:
            _text, label, field = self._idle.popleft()
            self.root.remove(*([label] if field is None else [field, label]))
        if self.style.show_points and len(anchors):
            if self.dots is None:
                self.dots = gfx.Points(
                    gfx.Geometry(positions=anchors.copy()),
                    gfx.PointsMaterial(
                        size=float(self.style.point_size),
                        color=self.style.point_colour,
                        depth_test=not self.style.always_visible,
                        render_queue=OVERLAY_QUEUE,
                        pick_write=self._pickable,
                    ),
                )
                self.dots._solidon_coloured = False
            elif self.dots.geometry.positions.data.shape == anchors.shape:
                self.dots.geometry.positions.data[:] = anchors
                self.dots.geometry.positions.update_full()
            else:
                self.dots.geometry = gfx.Geometry(positions=anchors.copy())
            objects.append(self.dots)
        else:
            self.dots = None
        new_objects = set(objects)
        resting_objects = {obj for _text, label, field in self._idle for obj in (label, field)}
        for obj in old_objects - new_objects - resting_objects:
            self.root.remove(obj)
        # Gleiche Texte dürfen mehrfach vorkommen. Ihre Reihenfolge bestimmt
        # bei gleicher Tiefe auch die Reihenfolge beim Zeichnen.
        self.root.add(*objects)
        self.objects = objects
        self.texts = label_objects
        self.fields = fields
        self.anchors = anchors
        self.labels = labels
        self._field_state = None
        if old_objects != new_objects and self.rebuilt is not None:
            self.rebuilt(self)
        else:
            self._changed()

    def _rest(self, text: str, label: Any, field: Any | None) -> None:
        """Ein ausgeschiedenes Paar verbergen und für seinen Namen aufheben."""
        label.visible = False
        if field is not None:
            field.visible = False
        self._idle.append((text, label, field))

    def _wake(self, label: Any, field: Any | None) -> None:
        """Ein ruhendes Paar zeigen — mit der Farbe und Deckkraft von heute."""
        label.visible = True
        label.material.color = self._colour
        label.material.opacity = self._opacity
        if field is not None:
            field.visible = True

    def _new_label(self, anchor: np.ndarray, text: str) -> tuple[Any, Any | None]:
        """Nur ein neuer sichtbarer Name braucht neue Glyphen und ein neues Feld."""
        import pygfx as gfx

        style = self.style
        field = None
        if style.background is not None:
            field = gfx.Line(
                gfx.Geometry(positions=np.vstack([anchor, anchor]).astype(np.float32)),
                gfx.LineMaterial(
                    thickness=1.0,
                    color=_rgba(style.background, style.background_opacity),
                    alpha_mode=_alpha_mode(style.background_opacity),
                    depth_test=not style.always_visible,
                    render_queue=OVERLAY_QUEUE + 1,
                    pick_write=False,
                ),
            )
            field._solidon_coloured = False
            field._solidon_pickable = False
        label = gfx.Text(
            text=text,
            font_size=float(style.font_size),
            screen_space=False,
            anchor="bottom-left" if style.show_points else "middle-center",
            anchor_offset=(style.point_size / 2.0 + style.margin + 2.0) if style.show_points else 0,
            material=gfx.TextMaterial(
                color=self._colour,
                opacity=self._opacity,
                weight_offset=300 if style.bold else 0,
                depth_test=not style.always_visible,
                render_queue=OVERLAY_QUEUE + 2,
                pick_write=self._pickable,
            ),
        )
        # Das Layout kennt Glyphenbreite, Umlaute, Schrift und Zeilenhöhe.
        # Im Bildraum gibt get_bounding_box nur den Anker zurück; die
        # wirklichen Textmaße deshalb einmal vor dem Umschalten lesen.
        text_bounds = label.get_bounding_box()
        label._solidon_label_bounds = (
            np.zeros((2, 3)) if text_bounds is None else np.asarray(text_bounds, dtype=float)
        )
        label.screen_space = True
        label._solidon_text = True
        return label, field

    def update_labels(self, points: np.ndarray, texts: Sequence[str]) -> None:
        anchors = _positions(points)
        labels = [str(text) for text in texts]
        if anchors.shape[0] != len(labels):
            raise ValueError(f"{self.name}: {anchors.shape[0]} Anker für {len(labels)} Texte")
        if labels != self.labels:
            self.build(anchors, labels)
            return
        if np.array_equal(anchors, self.anchors):
            return
        # Das Bildlayout verschiebt Texte bei jedem Kamerazug. Schriftlayout,
        # Glyphen und Registrierungen bleiben dabei dieselben.
        self.anchors = anchors
        for label, anchor in zip(self.texts, anchors, strict=True):
            label.local.position = anchor
        if self.dots is not None:
            self.dots.geometry.positions.data[:] = anchors
            self.dots.geometry.positions.update_full()
        self._field_state = None
        self._changed()

    def bounds(self) -> Bounds:
        if not len(self.anchors):
            return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        matrix = np.asarray(self.root.world.matrix, dtype=float)
        world = self.anchors.astype(float) @ matrix[:3, :3].T + matrix[:3, 3]
        low = world.min(axis=0)
        high = world.max(axis=0)
        return (
            float(low[0]),
            float(high[0]),
            float(low[1]),
            float(high[1]),
            float(low[2]),
            float(high[2]),
        )

    def set_line_width(self, width: float) -> None:
        return

    def fit_fields(self, renderer: GfxRenderer) -> None:
        """Die Felder hinter den Texten auf Bildbreite bringen — je Bild neu,
        denn die Weltlänge eines Bildpunkts hängt an Kamera und Anker."""
        if not self.fields or not self.visible():
            return
        matrix = np.asarray(self.root.world.matrix, dtype=float)
        state = (renderer._camera.camera_matrix.tobytes(), renderer.view_size(), matrix.tobytes())
        if state == self._field_state:
            return
        self._field_state = state
        style = self.style
        right = np.asarray(renderer._camera.world.right, dtype=float)
        up = np.asarray(renderer._camera.world.up, dtype=float)
        local_axes = np.linalg.pinv(matrix[:3, :3]) @ np.column_stack((right, up))
        local_right, local_up = local_axes[:, 0], local_axes[:, 1]
        for field, anchor, label in zip(self.fields, self.anchors, self.texts, strict=True):
            world = matrix[:3, :3] @ anchor.astype(float) + matrix[:3, 3]
            # pygfx bemisst Text und Linienstärke in logischen Bildpunkten;
            # der gemeinsame Renderer-Vertrag projiziert in Gerätepixel.
            per_pixel = renderer._world_per_pixel_at(world, right) * renderer._ratio()
            low, high = label._solidon_label_bounds
            text_centre = (low + high) / 2.0
            width = max(float(high[0] - low[0]), 1.0) + 2.0 * float(style.margin)
            height = max(float(high[1] - low[1]), 1.0) + 2.0 * float(style.margin)
            centre = anchor + per_pixel * (text_centre[0] * local_right + text_centre[1] * local_up)
            half = 0.5 * max(width - height, 1.0) * per_pixel
            ends = np.vstack([centre - half * local_right, centre + half * local_right]).astype(
                np.float32
            )
            field.geometry.positions.data[:] = ends
            field.geometry.positions.update_full()
            field.material.thickness = height


class GfxRenderer(Renderer):
    """Die pygfx-Umsetzung des Vertrags aus :mod:`app.ui.render.api`.

    Mit ``parent`` entsteht ein Qt-Widget (``widget``), mit ``offscreen=True``
    ein Puffer der Größe ``size``. Die Kamera beginnt wie bei VTK: Blick
    entlang -z auf den Ursprung, 30 Grad Öffnung.
    """

    def __init__(
        self,
        parent: Any = None,
        *,
        offscreen: bool = False,
        size: tuple[int, int] = (640, 480),
    ) -> None:
        import pygfx as gfx

        self._gfx = gfx
        self._listeners: dict[int, Callable[[PointerEvent], None]] = {}
        self._next_token = 1
        self._items: dict[int, GfxItem] = {}
        self._pick_objects: dict[int, Any] = {}
        self._scene_revision = 0
        self._pick_key: tuple[Any, ...] | None = None
        self._bounds_cache: tuple[int, Bounds | None] | None = None
        self._label_items: list[GfxLabels] = []
        self._focal = np.zeros(3)
        self._parallel_scale = 1.0
        self._background_colour: Colour = "#000000"
        self._axes_corner = (0.0, 0.0, 0.2, 0.2)
        self._axes_scene: Any = None
        self._axes_camera: Any = None
        self._axes_objects: list[Any] = []
        self._occlusion_wanted = False
        self._occlusion: Any = None
        self._occlusion_radius = 0.0
        self._occlusion_bias = 0.0
        self.widget: Any = None
        if offscreen:
            from rendercanvas.offscreen import RenderCanvas

            self._canvas = RenderCanvas(size=(int(size[0]), int(size[1])), pixel_ratio=1.0)
        else:
            self._canvas = self._qt_widget(parent)
            self.widget = self._canvas
        self._renderer = gfx.WgpuRenderer(self._canvas, pixel_scale=1, ppaa="none")
        self._scene = gfx.Scene()
        self._background = gfx.Background(None, gfx.BackgroundMaterial("#000000"))
        self._scene.add(self._background)
        self._ambient = gfx.AmbientLight("#ffffff", AMBIENT_INTENSITY)
        self._scene.add(self._ambient)
        self._camera = gfx.PerspectiveCamera(DEFAULT_VIEW_ANGLE, 1.0)
        self._camera_view_size: tuple[float, float] | None = None
        self._camera.world.reference_up = (0.0, 0.0, 1.0)
        self._headlight = gfx.DirectionalLight("#ffffff", DEFAULT_HEADLIGHT * HEADLIGHT_GAIN)
        self._camera.add(self._headlight)
        self._scene.add(self._camera)
        self._kit: list[tuple[Any, float, float]] = []
        for _name, share, elevation, azimuth in LIGHT_KIT:
            light = gfx.DirectionalLight("#ffffff", share * HEADLIGHT_GAIN)
            self._scene.add(light)
            self._kit.append((light, math.radians(elevation), math.radians(azimuth)))
        self.set_camera_pose(CameraPose((0.0, 0.0, 10.0), (0.0, 0.0, 0.0), (0.0, 1.0, 0.0)))
        if self.widget is not None:
            self._canvas.request_draw(self._draw)

    # --- Qt -------------------------------------------------------------------------

    def _qt_widget(self, parent: Any) -> Any:
        from PySide6.QtCore import Qt
        from rendercanvas.qt import QRenderWidget

        renderer = self

        class _Widget(QRenderWidget):  # type: ignore[misc]
            """Die pygfx-Leinwand als Qt-Widget; Zeigergesten kommen hier an."""

            def mousePressEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Name
                super().mousePressEvent(event)
                renderer._pointer("press", event, _button_of(event.button()))

            def mouseReleaseEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Name
                super().mouseReleaseEvent(event)
                renderer._pointer("release", event, _button_of(event.button()))

            def mouseMoveEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Name
                super().mouseMoveEvent(event)
                renderer._pointer("move", event, None)

            def mouseDoubleClickEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Name
                renderer._pointer("press", event, _button_of(event.button()))

            def wheelEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Name
                steps = round(event.angleDelta().y() / 120.0) if event.angleDelta().y() else 0
                renderer._pointer("wheel", event, None, delta=steps)

            def leaveEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Name
                super().leaveEvent(event)
                renderer._emit(PointerEvent("leave", 0, 0))

            def keyPressEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Name
                event.ignore()

            def keyReleaseEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Name
                event.ignore()

        # **Auf den Schirm, nicht über eine Bitmap.** rendercanvas nimmt für
        # ein Qt-Widget von sich aus den Bitmap-Weg — Bild zurücklesen und mit
        # ``QPainter`` malen —, und der kostete bei 3413 x 1369 rund 20 ms je
        # Bild, gleich wie klein die Szene war; als eigene Grafikfläche
        # (``present_method="screen"``, ``WA_PaintOnScreen``) sind es 1 ms
        # (gemessen am 05.09.2026, 1900 x 1000: 5,5 gegen 1,1 ms).
        # ``vsync=False``, damit ``render()`` nicht auf den Bildwechsel des
        # Schirms wartet; unter einem Fenstermanager mit Komposition
        # (Windows, macOS, Wayland, X11 mit Compositor) reißt der Inhalt
        # dadurch nicht.
        widget = _Widget(parent, update_mode="ondemand", vsync=False, present_method="screen")
        widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        widget.setMouseTracking(True)
        widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        return widget

    def _pointer(self, kind: str, event: Any, button: MouseButton | None, delta: int = 0) -> None:
        from PySide6.QtCore import Qt

        ratio = self._ratio()
        position = event.position()
        modifiers = event.modifiers()
        buttons = event.buttons()
        held = frozenset(
            name
            for name, flag in (
                ("left", Qt.MouseButton.LeftButton),
                ("middle", Qt.MouseButton.MiddleButton),
                ("right", Qt.MouseButton.RightButton),
            )
            if buttons & flag
        )
        self._emit(
            PointerEvent(
                kind,  # type: ignore[arg-type]
                round(position.x() * ratio),
                round(position.y() * ratio),
                button,
                held,  # type: ignore[arg-type]
                bool(modifiers & Qt.KeyboardModifier.ShiftModifier),
                bool(modifiers & Qt.KeyboardModifier.ControlModifier),
                bool(modifiers & Qt.KeyboardModifier.AltModifier),
                delta,
            )
        )
        event.accept()

    def _emit(self, event: PointerEvent) -> None:
        for listener in list(self._listeners.values()):
            listener(event)

    def _ratio(self) -> float:
        if self.widget is not None:
            return float(self.widget.devicePixelRatioF()) or 1.0
        return 1.0

    # --- Inhalt -------------------------------------------------------------------

    def _register(self, item: GfxItem) -> GfxItem:
        self._scene.add(item.root)
        self._register_objects(item)
        if isinstance(item, GfxLabels):
            # Beschriftungen wandern mit jedem Bild (das Layout schiebt ihre
            # Anker); der Hüllquader der Szene bleibt davon unberührt.
            item.changed = self._invalidate_pick
            self._label_items.append(item)
            item.rebuilt = self._refresh_registration
        else:
            item.changed = self._invalidate_scene
            self._bounds_cache = None
        return item

    def _invalidate_pick(self) -> None:
        self._scene_revision += 1
        self._pick_key = None

    def _invalidate_scene(self) -> None:
        self._invalidate_pick()
        self._bounds_cache = None

    def _refresh_registration(self, item: GfxItem) -> None:
        obsolete = {key for key, registered in self._items.items() if registered is item}
        for key, registered in list(self._items.items()):
            if registered is item:
                del self._items[key]
        self._pick_objects = {
            key: obj for key, obj in self._pick_objects.items() if id(obj) not in obsolete
        }
        self._register_objects(item)

    def _register_objects(self, item: GfxItem) -> None:
        for obj in item.objects:
            self._items[id(obj)] = item
            self._pick_objects[obj.id] = obj
        self._invalidate_pick()

    def _material(self, style: SurfaceStyle, colour: Colour, opacity: float, side: str) -> Any:
        gfx = self._gfx
        common: dict[str, Any] = {
            "color": colour,
            "opacity": float(opacity),
            "side": side,
            "pick_write": bool(style.pickable),
            "wireframe": bool(style.wireframe),
            "wireframe_thickness": float(style.line_width or 1.0),
            "flat_shading": not style.smooth,
        }
        if style.keep_in_front:
            common["depth_test"] = False
            common["render_queue"] = OVERLAY_QUEUE
        common["alpha_mode"] = "solid" if style.force_opaque else _alpha_mode(opacity)
        if not style.lighting:
            return gfx.MeshBasicMaterial(**common)
        material = gfx.MeshPhongMaterial(**common)
        # Ohne Glanz, wie VTKs Vorgabe (``Specular = 0``); pygfx glänzte sonst
        # von sich aus mit #494949.
        grey = max(0.0, min(1.0, float(style.specular or 0.0)))
        material.specular = (grey, grey, grey, 1.0)
        if style.ambient is not None:
            red, green, blue = rgb(colour)
            share = max(0.0, min(1.0, float(style.ambient)))
            material.emissive = (red * share, green * share, blue * share, 1.0)
        return material

    def add_surface(
        self,
        vertices: np.ndarray,
        faces: np.ndarray,
        *,
        name: str,
        style: SurfaceStyle,
        cell_colours: CellColours | None = None,
    ) -> Item:
        gfx = self._gfx
        positions = _positions(vertices)
        indices = np.ascontiguousarray(np.asarray(faces, dtype=np.uint32).reshape(-1, 3))
        fields: dict[str, Any] = {"positions": positions, "indices": indices}
        if cell_colours is not None:
            fields["colors"] = _face_colours(cell_colours, len(indices))
        geometry = gfx.Geometry(**fields)
        side = "front" if (style.cull_backfaces or style.backface_colour is not None) else "both"
        material = self._material(style, style.colour, style.opacity, side)
        if cell_colours is not None:
            material.color_mode = "face"
        mesh = gfx.Mesh(geometry, material)
        mesh._solidon_mesh = True
        mesh._solidon_positions = np.asarray(vertices, dtype=float).reshape(-1, 3)
        mesh._solidon_force_opaque = style.force_opaque
        if style.ambient is not None and style.lighting:
            mesh._solidon_ambient = max(0.0, min(1.0, float(style.ambient)))
        root = gfx.Group()
        root.add(mesh)
        objects = [mesh]
        if style.backface_colour is not None and not style.cull_backfaces:
            back = gfx.Mesh(
                geometry,
                self._material(
                    style,
                    style.backface_colour,
                    style.opacity if style.backface_opacity is None else style.backface_opacity,
                    "back",
                ),
            )
            back._solidon_coloured = False
            back._solidon_mesh = True
            back._solidon_positions = mesh._solidon_positions
            back._solidon_force_opaque = style.force_opaque
            root.add(back)
            objects.append(back)
        item = GfxItem(
            name, root, objects, style.colour, opacity=style.opacity, pickable=style.pickable
        )
        if style.show_edges and not style.wireframe:
            # **Die Kanten zeichnet die GPU aus demselben Netz.** Ein zweites
            # Mesh im Drahtgittermodus teilt Geometrie und Tiefe mit der
            # Fläche; ``depth_compare="<="`` lässt seine Kantenpunkte über der
            # eigenen Fläche gewinnen, ohne Versatz und ohne dass eine
            # angehobene Markierung darunter durchscheint. Der Weg davor —
            # jede Dreieckskante einmal als Linienpaar auf der CPU — kostete
            # 285 ms bei 197 000 und 5,8 s bei 3,15 Millionen Dreiecken, dazu
            # 114 MB Linienpuffer, bei jedem Szenenaufbau (gemessen 06.09.2026).
            edges = gfx.Mesh(
                geometry,
                gfx.MeshBasicMaterial(
                    color=style.edge_colour or "#000000",
                    wireframe=True,
                    wireframe_thickness=1.0,
                    side=side,
                    opacity=style.opacity,
                    alpha_mode="solid" if style.force_opaque else _alpha_mode(style.opacity),
                    depth_compare="<=",
                    pick_write=False,
                ),
            )
            edges._solidon_coloured = False
            edges._solidon_mesh = True
            edges._solidon_pickable = False
            edges._solidon_force_opaque = style.force_opaque
            root.add(edges)
            objects.append(edges)
            item.objects = objects
            item.edge_line = edges
        return self._register(item)

    def add_lines(
        self,
        points: np.ndarray,
        *,
        name: str,
        colour: Colour,
        width: float = 2.0,
        pickable: bool = False,
        keep_in_front: bool = False,
        connected: bool = False,
        polylines: Sequence[int] | None = None,
    ) -> Item:
        gfx = self._gfx
        from app.ui.render.gfx_lines import DepthLineMaterial, DepthLineSegmentMaterial

        positions = _positions(points)
        point_map: np.ndarray | None = None
        extra: dict[str, Any] = {"pick_write": bool(pickable), "depth_compare": "<="}
        if keep_in_front:
            extra["depth_test"] = False
            extra["render_queue"] = OVERLAY_QUEUE
        if polylines is not None:
            lengths = [int(length) for length in polylines]
            if any(length < 0 for length in lengths):
                raise ValueError("Eine Linienkette braucht nichtnegative Punktzahlen")
            if sum(lengths) > len(positions):
                raise ValueError(f"{sum(lengths)} Kettenpunkte für {len(positions)} Punkte")
            pieces: list[np.ndarray] = []
            start = 0
            mapping: list[int] = []
            gap = np.full((1, 3), np.nan, dtype=np.float32)
            for length in lengths:
                if length >= 2:
                    pieces.append(positions[start : start + length])
                    pieces.append(gap)
                    mapping.extend(range(start, start + length))
                    mapping.append(-1)
                start += length
            point_map = np.asarray(mapping, dtype=np.int64)
            chained = np.vstack(pieces) if pieces else positions[:0]
            line = gfx.Line(
                _line_geometry(chained),
                DepthLineMaterial(thickness=float(width), color=colour, **extra),
            )
        elif connected:
            line = gfx.Line(
                _line_geometry(positions),
                DepthLineMaterial(thickness=float(width), color=colour, **extra),
            )
        else:
            pairs = positions[: 2 * (len(positions) // 2)]
            line = gfx.Line(
                _line_geometry(pairs),
                DepthLineSegmentMaterial(thickness=float(width), color=colour, **extra),
            )
        root = gfx.Group()
        root.add(line)
        line._solidon_mesh = True
        item = GfxItem(name, root, [line], colour, pickable=pickable)
        item.point_map = point_map
        item.point_count = len(positions)
        return self._register(item)

    def add_points(
        self,
        points: np.ndarray,
        *,
        name: str,
        colour: Colour,
        size: float = 8.0,
        pickable: bool = False,
        keep_in_front: bool = False,
    ) -> Item:
        gfx = self._gfx
        extra: dict[str, Any] = {"pick_write": bool(pickable)}
        if keep_in_front:
            extra["depth_test"] = False
            extra["render_queue"] = OVERLAY_QUEUE
        dots = gfx.Points(
            _line_geometry(points), gfx.PointsMaterial(size=float(size), color=colour, **extra)
        )
        root = gfx.Group()
        root.add(dots)
        dots._solidon_mesh = True
        return self._register(GfxItem(name, root, [dots], colour, pickable=pickable))

    def add_labels(
        self, points: np.ndarray, texts: Sequence[str], *, name: str, style: LabelStyle
    ) -> LabelsItem:
        gfx = self._gfx
        item = GfxLabels(name, gfx.Group(), style)
        item.build(points, texts)
        self._register(item)
        return item

    def remove(self, item: Item) -> None:
        assert isinstance(item, GfxItem)
        self._scene.remove(item.root)
        for obj in item.objects:
            self._items.pop(id(obj), None)
            self._pick_objects.pop(obj.id, None)
        item.changed = None
        if isinstance(item, GfxLabels) and item in self._label_items:
            self._label_items.remove(item)
            item.rebuilt = None
        self._invalidate_scene()

    def set_draw_order(self, items: Sequence[Item]) -> None:
        # pygfx sortiert Durchscheinendes selbst von hinten nach vorn
        # (``sort_objects``), je Bild und nach dem Abstand zur Kamera. Eine
        # eigene Reihenfolge darüberzulegen (``render_order``) höbe genau das
        # auf — gemessen: zwei Bilder je Reihenfolge, 2304 Bildpunkte anders.
        # Der Maleralgorithmus des Viewports ist hier also schon eingebaut.
        return

    # --- Kamera -------------------------------------------------------------------

    def camera_pose(self) -> CameraPose:
        return CameraPose(
            _vec(self._camera.world.position), _vec(self._focal), _vec(self._camera.world.up)
        )

    def set_camera_pose(self, pose: CameraPose) -> None:
        position = np.asarray(pose.position, dtype=float)
        focal = np.asarray(pose.focal_point, dtype=float)
        up = np.asarray(pose.view_up, dtype=float)
        if np.linalg.norm(focal - position) < EPS_GEOM:
            focal = position + np.array([0.0, 0.0, -1.0])
        self._camera.world.position = position
        self._camera.world.reference_up = up / max(np.linalg.norm(up), EPS_GEOM)
        self._camera.look_at(focal)
        self._focal = focal
        self._fit_depth()

    def parallel_projection(self) -> bool:
        return bool(self._camera.fov == 0)

    def set_parallel_projection(self, parallel: bool) -> None:
        if parallel == self.parallel_projection():
            return
        self._sync_camera()
        if parallel:
            # Was jetzt zu sehen ist, bleibt zu sehen: die Bildhöhe am
            # Blickpunkt wird die Höhe der Parallelprojektion.
            distance = self._distance()
            self._parallel_scale = distance / float(self._camera.projection_matrix[1, 1])
            self._camera.fov = 0
            self._set_height(2.0 * self._parallel_scale)
        else:
            height = 2.0 / float(self._camera.projection_matrix[1, 1])
            self._camera.fov = DEFAULT_VIEW_ANGLE
            self._camera.aspect = 1.0
            distance = height * float(self._camera.projection_matrix[1, 1]) / 2.0
            self._camera.world.position = self._focal - self._direction() * distance
        self._fit_depth()

    def parallel_scale(self) -> float:
        if self._camera.fov == 0:
            return float(self._camera.height) / 2.0
        return float(self._parallel_scale)

    def set_parallel_scale(self, scale: float) -> None:
        self._parallel_scale = float(scale)
        if self._camera.fov == 0:
            self._set_height(2.0 * self._parallel_scale)

    def view_angle(self) -> float:
        if self._camera.fov > 0:
            self._sync_camera()
            return math.degrees(2.0 * math.atan(1.0 / self._camera.projection_matrix[1, 1]))
        width, height = self.view_size()
        aspect = max(width, 1) / max(height, 1)
        return math.degrees(
            2.0 * math.atan(math.tan(math.radians(DEFAULT_VIEW_ANGLE) / 2.0) / min(aspect, 1.0))
        )

    def dolly(self, factor: float) -> None:
        factor = float(factor)
        if factor <= 0:
            return
        if self._camera.fov == 0:
            self._set_height(float(self._camera.height) / factor)
        else:
            position = np.asarray(self._camera.world.position, dtype=float)
            self._camera.world.position = self._focal + (position - self._focal) / factor
        self._fit_depth()

    def reset_camera(self, bounds: Bounds | None = None) -> None:
        box = bounds if bounds is not None else self._scene_bounds()
        if box is None:
            return
        low = np.array([box[0], box[2], box[4]], dtype=float)
        high = np.array([box[1], box[3], box[5]], dtype=float)
        centre = (low + high) / 2.0
        radius = float(np.linalg.norm(high - low)) / 2.0
        if radius < EPS_GEOM:
            radius = 1.0
        direction = self._direction()
        if self._camera.fov == 0:
            width, height = self.view_size()
            self._parallel_scale = radius / min(width / max(height, 1), 1.0)
            self._set_height(2.0 * self._parallel_scale)
            distance = self._distance()
        else:
            self._sync_camera()
            projection = self._camera.projection_matrix
            half_angle = min(math.atan(1.0 / projection[0, 0]), math.atan(1.0 / projection[1, 1]))
            distance = radius / math.sin(half_angle)
        self._camera.world.position = centre - direction * distance
        self._camera.look_at(centre)
        self._focal = centre
        self._fit_depth(radius)

    def reset_clipping_range(self) -> None:
        self._fit_depth()

    def view_size(self) -> tuple[int, int]:
        width, height = self._canvas.get_physical_size()
        return int(width), int(height)

    def _logical_size(self) -> tuple[float, float]:
        width, height = self._canvas.get_logical_size()
        return float(width), float(height)

    def _sync_camera(self) -> None:
        width, height = self._logical_size()
        size = (max(width, 1.0), max(height, 1.0))
        if size != self._camera_view_size:
            # Auch identische Werte verwerfen bei pygfx die Projektionsmatrizen.
            self._camera.set_view_size(*size)
            self._camera_view_size = size

    def world_to_display(self, point: Vec3) -> tuple[float, float, float]:
        self._sync_camera()
        clip = self._camera.camera_matrix @ np.array([point[0], point[1], point[2], 1.0])
        if abs(clip[3]) < EPS_GEOM:
            return (0.0, 0.0, 1.0)
        ndc = clip[:3] / clip[3]
        width, height = self.view_size()
        return (
            float((ndc[0] + 1.0) / 2.0 * width),
            float((1.0 - ndc[1]) / 2.0 * height),
            float(ndc[2]),
        )

    def display_to_world(self, x: float, y: float, depth: float) -> Vec3 | None:
        self._sync_camera()
        width, height = self.view_size()
        ndc = np.array(
            [2.0 * x / max(width, 1) - 1.0, 1.0 - 2.0 * y / max(height, 1), float(depth), 1.0]
        )
        world = np.linalg.inv(self._camera.camera_matrix) @ ndc
        if abs(world[3]) < EPS_GEOM:
            return None
        return (float(world[0] / world[3]), float(world[1] / world[3]), float(world[2] / world[3]))

    def _world_per_pixel_at(self, world: np.ndarray, right: np.ndarray) -> float:
        """Wie viele Millimeter ein Bildpunkt an diesem Weltpunkt lang ist."""
        a = self.world_to_display(_vec(world))
        b = self.world_to_display(_vec(world + right))
        pixels = math.hypot(b[0] - a[0], b[1] - a[1])
        return 1.0 / pixels if pixels > EPS_GEOM else 1.0

    def _direction(self) -> np.ndarray:
        forward = np.asarray(self._camera.world.forward, dtype=float)
        norm = float(np.linalg.norm(forward))
        return forward / norm if norm > EPS_GEOM else np.array([0.0, 0.0, -1.0])

    def _distance(self) -> float:
        return float(np.linalg.norm(np.asarray(self._camera.world.position) - self._focal))

    def _set_height(self, height: float) -> None:
        width, view_height = self.view_size()
        aspect = width / view_height if view_height else 1.0
        self._camera.height = max(float(height), EPS_GEOM)
        self._camera.width = max(float(height), EPS_GEOM) * aspect

    def _scene_bounds(self) -> Bounds | None:
        """Der Hüllquader der sichtbaren Geometrie — je Szenenstand einmal gerechnet.

        Jede Kamerastellung fragt ihn zweimal (Stellung und Tiefenbereich), und
        pygfx rechnet ihn je Objekt rekursiv: 76 Objekte kosteten 5 ms je
        Aufruf. Beschriftungen zählen nicht mit — wie VTKs 2D-Aktoren —, denn
        ihre Anker verschiebt das Layout in jedem Bild; jede Änderung an einem
        Geometrie-Item verwirft den Cache (:meth:`_invalidate_scene`).
        """
        if self._bounds_cache is not None:
            return self._bounds_cache[1]
        boxes = [
            item.bounds()
            for item in set(self._items.values())
            if item.visible() and not isinstance(item, GfxLabels)
        ]
        boxes = [box for box in boxes if box[1] > box[0] or box[3] > box[2] or box[5] > box[4]]
        bounds: Bounds | None = None
        if boxes:
            array = np.asarray(boxes, dtype=float)
            bounds = (
                float(array[:, 0].min()),
                float(array[:, 1].max()),
                float(array[:, 2].min()),
                float(array[:, 3].max()),
                float(array[:, 4].min()),
                float(array[:, 5].max()),
            )
        self._bounds_cache = (self._scene_revision, bounds)
        return bounds

    def _fit_depth(self, radius: float | None = None) -> None:
        """Nah- und Fernebene um das, was im Bild steht — wie VTKs
        ``ResetCameraClippingRange``."""
        if radius is None:
            box = self._scene_bounds()
            if box is None:
                radius = max(self._distance(), 1.0)
                centre = self._focal
            else:
                low = np.array([box[0], box[2], box[4]])
                high = np.array([box[1], box[3], box[5]])
                centre = (low + high) / 2.0
                radius = max(float(np.linalg.norm(high - low)) / 2.0, EPS_GEOM)
        else:
            centre = self._focal
        position = np.asarray(self._camera.world.position, dtype=float)
        along = float(np.dot(centre - position, self._direction()))
        far = along + radius * 1.05 + 1.0
        near = along - radius * 1.05 - 1.0
        near = max(near, far * 1e-3, 1e-3) if self._camera.fov > 0 else max(near, -far)
        self._camera.depth_range = (float(near), float(max(far, near + 1e-3)))

    # --- Auswahl ------------------------------------------------------------------

    def _pick_pass(self, among: Sequence[Item] | None) -> list[tuple[Any, bool]]:
        """Ein Bild nur mit dem Pickbaren — Unpickbares darf nicht verdecken."""
        if min(self.view_size()) <= 0:
            self._pick_key = None
            return []
        wanted_items = {id(item) for item in among} if among is not None else None
        self._sync_camera()
        key = (
            self._scene_revision,
            None if wanted_items is None else frozenset(wanted_items),
            self._camera.camera_matrix.tobytes(),
            self.view_size(),
        )
        if key == self._pick_key:
            return []
        restore: list[tuple[Any, bool]] = []
        for item in set(self._items.values()):
            allowed = item.visible() and item.pickable()
            if wanted_items is not None and id(item) not in wanted_items:
                allowed = False
            if item.root.visible != allowed:
                restore.append((item.root, item.root.visible))
                item.root.visible = allowed
            if allowed:
                for obj in item.objects:
                    material = obj.material
                    has_opacity = material.alpha_mode == "solid" or (
                        material.opacity > 0.0 and material.color.a > 0.0
                    )
                    if obj.visible and (not material.pick_write or not has_opacity):
                        restore.append((obj, True))
                        obj.visible = False
        # Ohne Flush merkt sich pygfx den Durchgang als „noch nicht
        # aufgeräumt" und malte das nächste Bild über dieses — der
        # entfernte Körper blieb dann ein Bild lang stehen.
        try:
            self._renderer.render(self._scene, self._camera, clear=True, flush=False)
        except Exception:
            self._restore(restore)
            raise
        self._pick_key = key
        return restore

    def _restore(self, restore: list[tuple[Any, bool]]) -> None:
        for obj, visible in restore:
            obj.visible = visible

    def _info_at(self, x: float, y: float) -> dict[str, Any]:
        if min(self.view_size()) <= 0:
            return {}
        ratio = self._ratio()
        return dict(self._renderer.get_pick_info((float(x) / ratio, float(y) / ratio)))

    def _item_of(self, info: dict[str, Any]) -> GfxItem | None:
        obj = info.get("world_object")
        return self._items.get(id(obj)) if obj is not None else None

    def _info_near(self, x: float, y: float, radius: float) -> dict[str, Any]:
        """Ein Trefferring mit genau einem Rücklesen statt bis zu 17 Wartezeiten.

        pygfx bietet öffentlich nur einzelne Bildpunkte an. Der hier eng
        begrenzte Zugriff liest dasselbe 64-Bit-Pickformat wie ``get_pick_info``;
        die Objekte selbst dekodieren anschließend Dreieck und Koordinaten.
        Bild- und Picktests sichern diese Grenze gegen die festgelegte Version.
        """
        view_width, view_height = self.view_size()
        if min(view_width, view_height) <= 0:
            return {}
        texture = self._renderer._blender.get_texture("pick")
        if texture is None:
            return {}
        width, height, _depth = texture.size
        scale_x, scale_y = width / max(view_width, 1), height / max(view_height, 1)
        px, py = float(x) * scale_x, float(y) * scale_y
        low_x = max(0, math.floor(px - radius * scale_x))
        low_y = max(0, math.floor(py - radius * scale_y))
        high_x = min(width, math.ceil(px + radius * scale_x) + 1)
        high_y = min(height, math.ceil(py + radius * scale_y) + 1)
        if low_x >= high_x or low_y >= high_y:
            return {}
        span_x, span_y = high_x - low_x, high_y - low_y
        data = self._renderer._device.queue.read_texture(
            {"texture": texture, "mip_level": 0, "origin": (low_x, low_y, 0)},
            {"offset": 0, "bytes_per_row": span_x * 8, "rows_per_image": span_y},
            (span_x, span_y, 1),
        )
        values = np.frombuffer(data, dtype=np.uint64).reshape(span_y, span_x)
        rows, columns = np.nonzero(values & ((1 << 20) - 1))
        distances = ((columns + low_x + 0.5 - px) / scale_x) ** 2 + (
            (rows + low_y + 0.5 - py) / scale_y
        ) ** 2
        for candidate in np.argsort(distances):
            if distances[candidate] > radius * radius:
                break
            value = int(values[rows[candidate], columns[candidate]])
            obj = self._pick_objects.get(value & ((1 << 20) - 1))
            if obj is not None:
                return {
                    "world_object": obj,
                    "screen_point": (
                        (columns[candidate] + low_x + 0.5) / scale_x,
                        (rows[candidate] + low_y + 0.5) / scale_y,
                    ),
                    **obj._wgpu_get_pick_info(value),
                }
        return {}

    def _surface_point(self, info: dict[str, Any], x: float, y: float) -> Vec3 | None:
        """Das getroffene Dreieck stammt aus der GPU, der Punkt aus dem Sichtstrahl.

        pygfx speichert baryzentrische Anteile mit neun Bit und rundet auf
        Bildpunkte. Für Maße und Bearbeitung schneiden wir stattdessen den
        genauen Zeigerstrahl mit der ursprünglichen Float64-Dreiecksebene.
        """
        obj = info.get("world_object")
        face = info.get("face_index")
        source = getattr(obj, "_solidon_positions", None)
        if obj is None or source is None or face is None:
            return _picked_point(info)
        indices = np.asarray(obj.geometry.indices.data).reshape(-1, 3)
        if not 0 <= int(face) < len(indices):
            return None
        corners = source[indices[int(face)]]
        matrix = np.asarray(obj.world.matrix, dtype=float)
        triangle = corners @ matrix[:3, :3].T + matrix[:3, 3]
        sample_x, sample_y = info.get("screen_point", (x, y))
        near = self.display_to_world(sample_x, sample_y, 0.0)
        far = self.display_to_world(sample_x, sample_y, 1.0)
        if near is None or far is None:
            return _picked_point(info)
        origin = np.asarray(near)
        direction = np.asarray(far) - origin
        normal = np.cross(triangle[1] - triangle[0], triangle[2] - triangle[0])
        denominator = float(np.dot(normal, direction))
        if abs(denominator) <= np.finfo(float).eps * np.linalg.norm(normal) * np.linalg.norm(
            direction
        ):
            return _picked_point(info)
        distance = float(np.dot(normal, triangle[0] - origin)) / denominator
        point = origin + distance * direction
        # Am Rand kann der Mittelpunkt des Rasterpixels noch im Dreieck
        # liegen, der genaue Zeiger aber schon daneben. Dann liegt der
        # Bearbeitungspunkt auf der nächsten Dreieckskante, nie außerhalb.
        edge_a, edge_b = triangle[1] - triangle[0], triangle[2] - triangle[0]
        offset = point - triangle[0]
        uu, uv, vv = np.dot(edge_a, edge_a), np.dot(edge_a, edge_b), np.dot(edge_b, edge_b)
        determinant = uu * vv - uv * uv
        if determinant <= np.finfo(float).eps * uu * vv:
            return _picked_point(info)
        first = (vv * np.dot(offset, edge_a) - uv * np.dot(offset, edge_b)) / determinant
        second = (uu * np.dot(offset, edge_b) - uv * np.dot(offset, edge_a)) / determinant
        if first >= 0 and second >= 0 and first + second <= 1:
            return _vec(point)
        candidates = []
        for start, end in (
            (triangle[0], triangle[1]),
            (triangle[1], triangle[2]),
            (triangle[2], triangle[0]),
        ):
            edge = end - start
            length_squared = float(np.dot(edge, edge))
            share = float(np.clip(np.dot(point - start, edge) / length_squared, 0.0, 1.0))
            candidates.append(start + share * edge)
        return _vec(min(candidates, key=lambda candidate: float(np.linalg.norm(candidate - point))))

    def pick_surface(
        self,
        x: float,
        y: float,
        *,
        among: Sequence[Item] | None = None,
        tolerance: float = 0.005,
    ) -> Pick | None:
        restore = self._pick_pass(among)
        try:
            info = self._info_at(x, y)
            item = self._item_of(info)
            if item is None and tolerance > 0:
                info = self._info_near(x, y, float(tolerance) * math.hypot(*self.view_size()))
                item = self._item_of(info)
            if item is None:
                return None
            point = self._surface_point(info, x, y)
            if point is None:
                return None
            return Pick(point, item, int(info.get("face_index", -1)))
        finally:
            self._restore(restore)

    def pick_item(self, x: float, y: float) -> Item | None:
        restore = self._pick_pass(None)
        try:
            found = self._item_of(self._info_at(x, y))
            if found is not None:
                return found
            return self._item_of(self._info_near(x, y, PICK_SLACK_PIXELS))
        finally:
            self._restore(restore)

    # --- Bild ---------------------------------------------------------------------

    def _place_lights(self) -> None:
        """Den Lichtsatz um die Kamera stellen — wie VTKs Kameralichter, die
        ihre Winkel gegen die Blickrichtung halten und mit ihr wandern."""
        forward = self._direction()
        right = np.asarray(self._camera.world.right, dtype=float)
        up = np.asarray(self._camera.world.up, dtype=float)
        reach = max(self._distance(), 1.0) * 4.0
        for light, elevation, azimuth in self._kit:
            offset = (
                right * (math.cos(elevation) * math.sin(azimuth))
                + up * math.sin(elevation)
                - forward * (math.cos(elevation) * math.cos(azimuth))
            )
            light.local.position = self._focal + offset * reach
            light.target.local.position = self._focal

    def _draw(self) -> None:
        self._pick_key = None
        self._sync_camera()
        self._place_lights()
        for labels in self._label_items:
            labels.fit_fields(self)
        if self._occlusion_wanted and self._occlusion is not None:
            self._draw_with_occlusion()
            return
        if self._axes_scene is None:
            self._renderer.render(self._scene, self._camera, clear=True)
            return
        self._renderer.render(self._scene, self._camera, clear=True, flush=False)
        self._place_axes()
        self._renderer.render(
            self._axes_scene, self._axes_camera, rect=self._axes_rect(), clear=False, flush=True
        )

    def _draw_with_occlusion(self) -> None:
        """Deckende Flächen schattieren, danach Durchscheinendes und Marken.

        Derselbe Tiefenpuffer bleibt erhalten, damit Überlagerungen ihre
        normale Tiefenprüfung behalten. Der AO-Durchgang ändert ausschließlich
        die Farbe und beeinflusst weder Auswahl noch Geometrie.
        """
        opaque: list[Any] = []
        deferred: list[Any] = []
        for item in set(self._items.values()):
            if not item.visible():
                continue
            for obj in item.objects:
                if not obj.visible:
                    continue
                material = obj.material
                is_opaque = (
                    isinstance(obj, self._gfx.Mesh)
                    and not material.wireframe
                    and material.depth_test
                    and material.render_queue < OVERLAY_QUEUE
                    and (
                        material.alpha_mode == "solid"
                        or (material.opacity >= 1.0 and material.color.a >= 1.0)
                    )
                )
                (opaque if is_opaque else deferred).append(obj)
        try:
            for obj in deferred:
                obj.visible = False
            self._renderer.render(self._scene, self._camera, clear=True, flush=False)
            if opaque:
                self._occlusion.apply(
                    self._renderer, self._camera, self._occlusion_radius, self._occlusion_bias
                )
            if deferred:
                for obj in opaque:
                    obj.visible = False
                for obj in deferred:
                    obj.visible = True
                self._background.visible = False
                self._renderer.render(self._scene, self._camera, clear=False, flush=False)
        finally:
            for obj in opaque + deferred:
                obj.visible = True
            self._background.visible = True
        if self._axes_scene is not None:
            self._place_axes()
            self._renderer.render(
                self._axes_scene,
                self._axes_camera,
                rect=self._axes_rect(),
                clear=False,
                flush=False,
            )
        self._renderer.flush()

    def render(self) -> None:
        if self.widget is not None:
            # Synchron wie VTKs ``Render()``: ``request_draw`` allein stellte
            # nur einen Wunsch in die Ereignisschleife, und der Viewport
            # wüsste nicht, wann das Bild steht — eine Messung zählte dann
            # Wünsche statt Bilder (0,9 ms je Stellung, 05.09.2026). Vor dem
            # ersten Anzeigen gibt es nichts zu erzwingen; dann bleibt der
            # Wunsch stehen, und der erste Aufbau zeichnet ihn.
            self._canvas.request_draw(self._draw)
            if self.widget.isVisible():
                self._canvas.force_draw()
            return
        self._draw()

    def screenshot(self) -> np.ndarray:
        self._draw()
        image = np.asarray(self._renderer.snapshot())
        if image.dtype != np.uint8:
            image = np.clip(image * 255.0, 0, 255).astype(np.uint8)
        return np.ascontiguousarray(image[:, :, :3])

    def set_background(self, colour: Colour, top: Colour | None = None) -> None:
        self._background_colour = colour
        if top is None:
            self._background.material.set_colors(colour)
        else:
            self._background.material.set_colors(colour, top)

    def background(self) -> Colour:
        return self._background_colour

    def set_headlight(self, intensity: float) -> None:
        self._headlight.intensity = float(intensity) * HEADLIGHT_GAIN

    def set_anti_aliasing(self, enabled: bool) -> None:
        self._renderer.ppaa = "ddaa" if enabled else "none"

    def set_ambient_occlusion(self, enabled: bool, *, radius: float, bias: float) -> None:
        self._occlusion_wanted = bool(enabled)
        self._occlusion_radius = max(float(radius), 0.0)
        self._occlusion_bias = max(float(bias), 0.0)
        if enabled and self._occlusion is None:
            from app.ui.render.gfx_occlusion import AmbientOcclusionPass

            self._occlusion = AmbientOcclusionPass()

    def set_axes_marker(self, style: AxesMarkerStyle | None) -> None:
        self._axes_scene = None
        self._axes_camera = None
        self._axes_objects = []
        if style is None:
            return
        gfx = self._gfx
        scene = gfx.Scene()
        scene.add(gfx.AmbientLight("#ffffff", 0.9))
        camera = gfx.PerspectiveCamera(DEFAULT_VIEW_ANGLE, 1.0)
        camera.world.reference_up = (0.0, 0.0, 1.0)
        camera.add(gfx.DirectionalLight("#ffffff", 1.6))
        scene.add(camera)
        length = 1.0
        shaft = 0.045 * style.line_width
        for axis, colour, label in (
            ((1.0, 0.0, 0.0), style.x_colour, "X"),
            ((0.0, 1.0, 0.0), style.y_colour, "Y"),
            ((0.0, 0.0, 1.0), style.z_colour, "Z"),
        ):
            vertices, faces = shapes.arrow(
                (0.0, 0.0, 0.0),
                axis,
                length,
                shaft_radius=shaft,
                tip_radius=shaft * 2.2 * max(style.cone_radius, 0.2) / 0.5,
                tip_share=max(min(style.tip_length, 0.6), 0.1),
            )
            mesh = gfx.Mesh(
                gfx.Geometry(
                    positions=_positions(vertices),
                    indices=np.asarray(faces, dtype=np.uint32).reshape(-1, 3),
                ),
                gfx.MeshPhongMaterial(
                    color=colour,
                    flat_shading=True,
                    depth_test=False,
                    render_queue=OVERLAY_QUEUE,
                    pick_write=False,
                    emissive=(*(part * style.ambient for part in rgb(colour)), 1.0),
                ),
            )
            mesh._solidon_axis_tip = np.asarray(axis, dtype=float) * length
            scene.add(mesh)
            self._axes_objects.append(mesh)
            text = gfx.Text(
                text=label,
                font_size=13.0,
                screen_space=True,
                anchor="middle-center",
                material=gfx.TextMaterial(
                    color=style.label_colour,
                    weight_offset=300,
                    depth_test=False,
                    render_queue=OVERLAY_QUEUE + 1,
                    pick_write=False,
                ),
            )
            text.local.position = np.asarray(axis, dtype=float) * (length * 1.22)
            scene.add(text)
        self._axes_scene = scene
        self._axes_camera = camera

    def _place_axes(self) -> None:
        """Die Achsenkamera dreht wie die Hauptkamera — das Kreuz zeigt die
        Weltrichtungen, nicht die des Bildes."""
        camera = self._axes_camera
        direction = self._direction()
        camera.world.reference_up = self._camera.world.reference_up
        camera.world.position = -direction * AXES_CAMERA_DISTANCE
        camera.look_at(np.zeros(3))
        camera.depth_range = (0.1, AXES_CAMERA_DISTANCE * 3.0)
        camera.set_view_size(1.0, 1.0)
        # Ohne Tiefentest zählt die Reihenfolge: Was ferner liegt, zuerst.
        position = np.asarray(camera.world.position, dtype=float)
        for mesh in self._axes_objects:
            tip = np.asarray(mesh._solidon_axis_tip, dtype=float)
            mesh.render_order = -float(np.linalg.norm(tip - position))

    def _axes_rect(self) -> tuple[float, float, float, float]:
        width, height = self._logical_size()
        left, bottom, right, top = self._axes_corner
        span_x = max((right - left) * width, 1.0)
        span_y = max((top - bottom) * height, 1.0)
        return (left * width, (1.0 - top) * height, span_x, span_y)

    def place_axes_marker(self, corner: tuple[float, float, float, float]) -> None:
        self._axes_corner = corner

    # --- Zeiger -------------------------------------------------------------------

    def add_pointer_listener(self, listener: Callable[[PointerEvent], None]) -> int:
        token = self._next_token
        self._next_token += 1
        self._listeners[token] = listener
        return token

    def remove_pointer_listener(self, token: int) -> None:
        self._listeners.pop(token, None)

    def close(self) -> None:
        self._listeners.clear()
        for item in list(set(self._items.values()) | set(self._label_items)):
            self.remove(item)
        self._axes_scene = None
        self._axes_objects.clear()
        self._occlusion = None
        try:
            self._canvas.close()
        except Exception as problem:  # pragma: no cover - hängt am Treiber
            _log.warning("the render canvas could not close: %s", problem)
        if self.widget is not None:
            self.widget.close()


def _picked_point(info: dict[str, Any]) -> Vec3 | None:
    """Der Weltpunkt eines Treffers — aus Dreieck und baryzentrischen Anteilen
    bei einer Fläche, aus dem getroffenen Eckpunkt bei Linie und Punkt."""
    obj = info.get("world_object")
    if obj is None or getattr(obj, "geometry", None) is None:
        return None
    # Ein Treffer braucht drei Ecken, keine Float64-Kopie des ganzen Netzes.
    positions = np.asarray(obj.geometry.positions.data)
    local: np.ndarray | None = None
    face = info.get("face_index")
    coord = info.get("face_coord")
    indices = getattr(obj.geometry, "indices", None)
    if face is not None and coord is not None and indices is not None:
        corners = np.asarray(indices.data).reshape(-1, 3)
        if 0 <= int(face) < len(corners):
            triangle = np.asarray(positions[corners[int(face)]], dtype=float)
            weights = np.asarray(coord, dtype=float)
            local = weights @ triangle
    vertex = info.get("vertex_index")
    if local is None and vertex is not None and 0 <= int(vertex) < len(positions):
        local = positions[int(vertex)]
    if local is None or not np.all(np.isfinite(local)):
        return None
    world = np.asarray(obj.world.matrix, dtype=float) @ np.array([*local, 1.0])
    if abs(world[3]) < EPS_GEOM:
        return None
    return (float(world[0] / world[3]), float(world[1] / world[3]), float(world[2] / world[3]))


def _button_of(button: Any) -> MouseButton | None:
    from PySide6.QtCore import Qt

    if button == Qt.MouseButton.LeftButton:
        return "left"
    if button == Qt.MouseButton.MiddleButton:
        return "middle"
    if button == Qt.MouseButton.RightButton:
        return "right"
    return None
