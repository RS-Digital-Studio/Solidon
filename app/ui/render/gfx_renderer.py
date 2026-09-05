"""Der pygfx-Renderer — dieselbe Schnittstelle, gezeichnet über wgpu (§18).

Der zweite Renderer hinter dem Vertrag aus :mod:`app.ui.render.api`: Netze,
Linien, Punkte und Beschriftungen werden pygfx-Objekte in einer Szene, die
Kamera ist eine ``PerspectiveCamera`` (mit ``fov = 0`` orthografisch), das
Bild entsteht über ``WgpuRenderer`` — auf einer Qt-Leinwand
(``rendercanvas.qt.QRenderWidget``) oder ohne Fenster in einen Puffer.

Was hier anders gelöst ist als bei VTK, weil pygfx es anders kann:

* **Gepickt wird aus dem Bild.** pygfx schreibt je Bildpunkt, welches Objekt
  und welches Dreieck dort steht; ``pick_surface`` und ``pick_item`` lesen das.
  Ein Pick zeichnet deshalb vorher ein Bild — nur mit dem, was pickbar ist,
  damit Unpickbares nicht verdeckt (VTKs Zell-Picker rechnet geometrisch und
  übergeht Unpickbares von selbst).
* **Vorn bleibt, was ohne Tiefentest zeichnet.** ``keep_in_front`` heißt hier
  ``depth_test = False`` in der Überlagerungswarteschlange, nicht ein
  Polygonversatz. Ein Maß im Material ist damit vollständig sichtbar, nicht
  nur nach vorn gerückt.
* **Beschriftungen sind Textobjekte im Bildraum**; das Feld dahinter ist ein
  bildbreiter Linienzug, den jedes Bild an die Kamera anpasst.
* **Umgebungsverdeckung gibt es nicht.** pygfx hat keine SSAO; der Schalter
  merkt sich den Wunsch und tut nichts — ein Loch im Renderer, kein Sonderweg
  im Viewport.
"""

from __future__ import annotations

import logging
import math
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

#: Wie viele Bildpunkte je Zeichen die Breite eines Beschriftungsfelds
#: annimmt, als Anteil der Schriftgröße — für das Feld hinter dem Text.
GLYPH_WIDTH_SHARE = 0.62

#: Abstand der Achsenkreuz-Kamera vom Ursprung, in Pfeillängen.
AXES_CAMERA_DISTANCE = 4.2


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


def _unique_edges(faces: np.ndarray) -> np.ndarray:
    """Jede Dreieckskante einmal, als ``(k, 2)`` Indexpaare."""
    triangles = np.asarray(faces, dtype=np.int64).reshape(-1, 3)
    edges = np.vstack([triangles[:, [0, 1]], triangles[:, [1, 2]], triangles[:, [2, 0]]])
    edges.sort(axis=1)
    return np.unique(edges, axis=0)


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

    def __init__(self, name: str, root: Any, objects: Sequence[Any], colour: Colour) -> None:
        self.name = name
        #: Der Träger des Transforms; Versatz und Matrix stehen hier.
        self.root = root
        #: Die Objekte, die gezeichnet werden — Netz, Rückseite, Kanten …
        self.objects = list(objects)
        self._colour = colour
        self._opacity = 1.0
        self._pickable = True
        self._position: Vec3 = (0.0, 0.0, 0.0)
        self._matrix = np.eye(4)
        #: Kantenpaare für die Kantenlinie, damit ``update_points`` sie nachzieht.
        self.edge_pairs: np.ndarray | None = None
        self.edge_line: Any = None

    # --- Vertrag ------------------------------------------------------------------

    def set_visible(self, visible: bool) -> None:
        self.root.visible = bool(visible)

    def visible(self) -> bool:
        return bool(self.root.visible)

    def set_opacity(self, opacity: float) -> None:
        self._opacity = float(opacity)
        for obj in self._coloured():
            obj.material.opacity = self._opacity
            if not getattr(obj, "_solidon_text", False):
                obj.material.alpha_mode = _alpha_mode(self._opacity)

    def opacity(self) -> float:
        return self._opacity

    def set_colour(self, colour: Colour) -> None:
        self._colour = colour
        for obj in self._coloured():
            obj.material.color = colour

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

    def bounds(self) -> Bounds:
        box = self.root.get_world_bounding_box()
        if box is None:
            return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        low, high = np.asarray(box, dtype=float)
        return (
            float(low[0]),
            float(high[0]),
            float(low[1]),
            float(high[1]),
            float(low[2]),
            float(high[2]),
        )

    def set_pickable(self, pickable: bool) -> None:
        self._pickable = bool(pickable)
        for obj in self.objects:
            obj.material.pick_write = self._pickable

    def pickable(self) -> bool:
        return self._pickable

    def update_points(self, points: np.ndarray) -> None:
        fresh = _positions(points)
        for obj in self._geometry_holders():
            current = obj.geometry.positions
            if fresh.shape[0] != current.nitems:
                raise ValueError(f"{self.name}: {fresh.shape[0]} Punkte für {current.nitems}")
            current.set_data(fresh)
            # Normalen und Hüllquader hängen an den Ecken; ein neues Netz
            # rechnet beides frisch, ein überschriebenes nicht zuverlässig.
            obj.geometry = _geometry_like(obj.geometry, fresh)
        if self.edge_line is not None and self.edge_pairs is not None:
            self.edge_line.geometry = _line_geometry(fresh[self.edge_pairs].reshape(-1, 3))

    def set_line_width(self, width: float) -> None:
        for obj in self.objects:
            material = obj.material
            if hasattr(material, "thickness"):
                material.thickness = float(width)
            elif hasattr(material, "wireframe_thickness"):
                material.wireframe_thickness = float(width)

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
            fields[name] = np.asarray(attribute.data).copy()
    return gfx.Geometry(**fields)


def _line_geometry(points: np.ndarray) -> Any:
    import pygfx as gfx

    return gfx.Geometry(positions=_positions(points))


class GfxLabels(GfxItem, LabelsItem):
    """Beschriftungen: je Anker ein Textobjekt im Bildraum, dazu Feld und Punkt."""

    def __init__(self, name: str, root: Any, style: LabelStyle) -> None:
        super().__init__(name, root, [], style.text_colour)
        self.style = style
        self.texts: list[Any] = []
        self.fields: list[Any] = []
        self.anchors = np.zeros((0, 3), dtype=np.float32)
        self.labels: list[str] = []
        self.dots: Any = None

    def build(self, points: np.ndarray, texts: Sequence[str]) -> None:
        import pygfx as gfx

        anchors = _positions(points)
        if anchors.shape[0] != len(texts):
            raise ValueError(f"{self.name}: {anchors.shape[0]} Anker für {len(texts)} Texte")
        for obj in list(self.objects):
            self.root.remove(obj)
        self.objects.clear()
        self.texts.clear()
        self.fields.clear()
        self.anchors = anchors
        self.labels = [str(text) for text in texts]
        style = self.style
        for anchor, text in zip(anchors, self.labels, strict=True):
            if style.background is not None:
                field = gfx.Line(
                    gfx.Geometry(positions=np.vstack([anchor, anchor]).astype(np.float32)),
                    gfx.LineMaterial(
                        thickness=1.0,
                        color=_rgba(style.background, style.background_opacity),
                        alpha_mode=_alpha_mode(style.background_opacity),
                        depth_test=not style.always_visible,
                        render_queue=OVERLAY_QUEUE,
                        pick_write=False,
                    ),
                )
                field._solidon_coloured = False
                self.root.add(field)
                self.objects.append(field)
                self.fields.append(field)
            label = gfx.Text(
                text=text,
                font_size=float(style.font_size),
                screen_space=True,
                anchor="middle-center",
                material=gfx.TextMaterial(
                    color=style.text_colour,
                    weight_offset=300 if style.bold else 0,
                    depth_test=not style.always_visible,
                    render_queue=OVERLAY_QUEUE,
                    pick_write=bool(style.pickable),
                ),
            )
            label.local.position = anchor
            label._solidon_text = True
            self.root.add(label)
            self.objects.append(label)
            self.texts.append(label)
        if self.dots is not None:
            self.root.remove(self.dots)
            self.dots = None
        if style.show_points and len(anchors):
            self.dots = gfx.Points(
                gfx.Geometry(positions=anchors.copy()),
                gfx.PointsMaterial(
                    size=float(style.point_size),
                    color=style.point_colour,
                    depth_test=not style.always_visible,
                    render_queue=OVERLAY_QUEUE,
                    pick_write=bool(style.pickable),
                ),
            )
            self.dots._solidon_coloured = False
            self.root.add(self.dots)
            self.objects.append(self.dots)
        self.set_opacity(self._opacity)

    def update_labels(self, points: np.ndarray, texts: Sequence[str]) -> None:
        self.build(points, texts)

    def bounds(self) -> Bounds:
        if not len(self.anchors):
            return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        world = self.anchors.astype(float) + np.asarray(self._position, dtype=float)
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
        if not self.fields:
            return
        style = self.style
        height = float(style.font_size) + 2.0 * float(style.margin)
        right = np.asarray(renderer._camera.world.right, dtype=float)
        offset = np.asarray(self._position, dtype=float)
        for field, anchor, text in zip(self.fields, self.anchors, self.labels, strict=True):
            world = anchor.astype(float) + offset
            per_pixel = renderer._world_per_pixel_at(world, right)
            width_pixels = max(len(text), 1) * GLYPH_WIDTH_SHARE * float(style.font_size)
            half = 0.5 * (width_pixels + 2.0 * float(style.margin)) * per_pixel
            ends = np.vstack([anchor - half * right, anchor + half * right]).astype(np.float32)
            field.geometry = gfx_geometry(ends)
            field.material.thickness = height


def gfx_geometry(points: np.ndarray) -> Any:
    return _line_geometry(points)


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
        self._label_items: list[GfxLabels] = []
        self._focal = np.zeros(3)
        self._parallel_scale = 1.0
        self._background_colour: Colour = "#000000"
        self._axes_corner = (0.0, 0.0, 0.2, 0.2)
        self._axes_scene: Any = None
        self._axes_camera: Any = None
        self._axes_objects: list[Any] = []
        self._occlusion_wanted = False
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
        for obj in item.objects:
            self._items[id(obj)] = item
        if isinstance(item, GfxLabels):
            self._label_items.append(item)
        return item

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
        common["alpha_mode"] = _alpha_mode(opacity)
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
            root.add(back)
            objects.append(back)
        item = GfxItem(name, root, objects, style.colour)
        if style.show_edges and not style.wireframe:
            pairs = _unique_edges(indices)
            edges = gfx.Line(
                _line_geometry(positions[pairs].reshape(-1, 3)),
                gfx.LineSegmentMaterial(
                    thickness=1.0,
                    color=style.edge_colour or "#000000",
                    pick_write=False,
                ),
            )
            edges._solidon_coloured = False
            root.add(edges)
            objects.append(edges)
            item.objects = objects
            item.edge_pairs = pairs
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
        positions = _positions(points)
        extra: dict[str, Any] = {"pick_write": bool(pickable)}
        if keep_in_front:
            extra["depth_test"] = False
            extra["render_queue"] = OVERLAY_QUEUE
        if polylines is not None:
            lengths = [int(length) for length in polylines if int(length) >= 2]
            if sum(lengths) > len(positions):
                raise ValueError(f"{sum(lengths)} Kettenpunkte für {len(positions)} Punkte")
            pieces: list[np.ndarray] = []
            start = 0
            gap = np.full((1, 3), np.nan, dtype=np.float32)
            for length in lengths:
                pieces.append(positions[start : start + length])
                pieces.append(gap)
                start += length
            chained = np.vstack(pieces) if pieces else positions[:0]
            line = gfx.Line(
                _line_geometry(chained),
                gfx.LineMaterial(thickness=float(width), color=colour, **extra),
            )
        elif connected:
            line = gfx.Line(
                _line_geometry(positions),
                gfx.LineMaterial(thickness=float(width), color=colour, **extra),
            )
        else:
            pairs = positions[: 2 * (len(positions) // 2)]
            line = gfx.Line(
                _line_geometry(pairs),
                gfx.LineSegmentMaterial(thickness=float(width), color=colour, **extra),
            )
        root = gfx.Group()
        root.add(line)
        return self._register(GfxItem(name, root, [line], colour))

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
        return self._register(GfxItem(name, root, [dots], colour))

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
        if isinstance(item, GfxLabels) and item in self._label_items:
            self._label_items.remove(item)

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
        if parallel:
            # Was jetzt zu sehen ist, bleibt zu sehen: die Bildhöhe am
            # Blickpunkt wird die Höhe der Parallelprojektion.
            distance = self._distance()
            self._parallel_scale = distance * math.tan(math.radians(self._camera.fov) / 2.0)
            self._camera.fov = 0
            self._set_height(2.0 * self._parallel_scale)
        else:
            self._camera.fov = DEFAULT_VIEW_ANGLE
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
        return float(self._camera.fov) if self._camera.fov > 0 else DEFAULT_VIEW_ANGLE

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
            self._set_height(2.0 * radius)
            self._parallel_scale = radius
            distance = self._distance()
        else:
            width, height = self.view_size()
            angle = math.radians(self._camera.fov)
            aspect = width / height if height else 1.0
            if aspect < 1.0:
                angle = 2.0 * math.atan(math.tan(angle / 2.0) / aspect)
            distance = radius / math.sin(angle / 2.0)
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
        self._camera.set_view_size(max(width, 1.0), max(height, 1.0))

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
        boxes = [item.bounds() for item in set(self._items.values()) if item.visible()]
        boxes = [box for box in boxes if box[1] > box[0] or box[3] > box[2] or box[5] > box[4]]
        if not boxes:
            return None
        array = np.asarray(boxes, dtype=float)
        return (
            float(array[:, 0].min()),
            float(array[:, 1].max()),
            float(array[:, 2].min()),
            float(array[:, 3].max()),
            float(array[:, 4].min()),
            float(array[:, 5].max()),
        )

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
        wanted_items = {id(item) for item in among} if among is not None else None
        restore: list[tuple[Any, bool]] = []
        for item in set(self._items.values()):
            allowed = item.visible() and item.pickable()
            if wanted_items is not None and id(item) not in wanted_items:
                allowed = False
            if item.root.visible != allowed:
                restore.append((item.root, item.root.visible))
                item.root.visible = allowed
        self._sync_camera()
        # Ohne Flush merkt sich pygfx den Durchgang als „noch nicht
        # aufgeräumt" und malte das nächste Bild über dieses — der
        # entfernte Körper blieb dann ein Bild lang stehen.
        self._renderer.render(self._scene, self._camera, clear=True, flush=False)
        return restore

    def _restore(self, restore: list[tuple[Any, bool]]) -> None:
        for obj, visible in restore:
            obj.visible = visible

    def _info_at(self, x: float, y: float) -> dict[str, Any]:
        ratio = self._ratio()
        return dict(self._renderer.get_pick_info((float(x) / ratio, float(y) / ratio)))

    def _item_of(self, info: dict[str, Any]) -> GfxItem | None:
        obj = info.get("world_object")
        return self._items.get(id(obj)) if obj is not None else None

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
            if item is None:
                return None
            point = _picked_point(info)
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
            # Ein Zeiger neben einer Linie trifft sie noch — dieselbe Toleranz
            # wie beim VTK-Renderer, hier als Ring von Nachbarpunkten.
            for radius in (PICK_SLACK_PIXELS / 2.0, PICK_SLACK_PIXELS):
                for step in range(8):
                    angle = math.tau * step / 8.0
                    found = self._item_of(
                        self._info_at(x + radius * math.cos(angle), y + radius * math.sin(angle))
                    )
                    if found is not None:
                        return found
            return None
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
        self._sync_camera()
        self._place_lights()
        for labels in self._label_items:
            labels.fit_fields(self)
        if self._axes_scene is None:
            self._renderer.render(self._scene, self._camera, clear=True)
            return
        self._renderer.render(self._scene, self._camera, clear=True, flush=False)
        self._place_axes()
        self._renderer.render(
            self._axes_scene, self._axes_camera, rect=self._axes_rect(), clear=False, flush=True
        )

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
        # pygfx kennt keine Umgebungsverdeckung im Bild (nur vorgerechnete
        # AO-Karten). Der Wunsch wird gemerkt, damit die Messung ihn nennt.
        self._occlusion_wanted = bool(enabled)

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
    positions = np.asarray(obj.geometry.positions.data, dtype=float)
    local: np.ndarray | None = None
    face = info.get("face_index")
    coord = info.get("face_coord")
    indices = getattr(obj.geometry, "indices", None)
    if face is not None and coord is not None and indices is not None:
        corners = np.asarray(indices.data).reshape(-1, 3)
        if 0 <= int(face) < len(corners):
            triangle = positions[corners[int(face)]]
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
