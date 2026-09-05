"""Ein Renderer-Doppel für die Tests der Ansicht — es schreibt mit, statt zu zeichnen.

Offscreen gibt es keinen Renderer, und vierzig Methoden des Viewports steigen
an ihrer Wache aus. Dieses Doppel erfüllt den Vertrag aus
:mod:`app.ui.render.api` mit genau dem, was ein Test danach ansehen will:
welche Aktoren unter welchem Namen und mit welchem Stil entstanden sind,
welche Beschriftungen, was entfernt wurde, wohin die Kamera gestellt wurde.
Es rechnet nichts nach — wer das Bild messen will, nimmt den echten Renderer
ohne Fenster (``tests/test_render_vtk.py``).
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any

import numpy as np

from app.ui.render.api import (
    AxesMarkerStyle,
    Bounds,
    CameraPose,
    CellColours,
    Colour,
    Item,
    LabelsItem,
    LabelStyle,
    Pick,
    PointerEvent,
    Renderer,
    SurfaceStyle,
    Vec3,
)


class RecordingItem(Item):
    """Ein Aktor, der seine Eigenschaften nur merkt."""

    def __init__(self, name: str, points: np.ndarray, colour: Colour, opacity: float = 1.0) -> None:
        self.name = name
        self.points = np.asarray(points, dtype=float).reshape(-1, 3)
        self._colour = colour
        self._opacity = opacity
        self._visible = True
        self._position: Vec3 = (0.0, 0.0, 0.0)
        self._matrix = np.eye(4)
        self.pickable = True
        self.line_width: float | None = None

    def set_visible(self, visible: bool) -> None:
        self._visible = bool(visible)

    def visible(self) -> bool:
        return self._visible

    def set_opacity(self, opacity: float) -> None:
        self._opacity = float(opacity)

    def opacity(self) -> float:
        return self._opacity

    def set_colour(self, colour: Colour) -> None:
        self._colour = colour

    def colour(self) -> Colour:
        return self._colour

    def set_position(self, position: Vec3) -> None:
        self._position = (float(position[0]), float(position[1]), float(position[2]))

    def position(self) -> Vec3:
        return self._position

    def set_matrix(self, matrix: np.ndarray) -> None:
        self._matrix = np.asarray(matrix, dtype=float)

    def matrix(self) -> np.ndarray:
        return self._matrix.copy()

    def bounds(self) -> Bounds:
        if len(self.points) == 0:
            return (0.0, 0.0, 0.0, 0.0, 0.0, 0.0)
        moved = self.points + np.asarray(self._position)
        low = moved.min(axis=0)
        high = moved.max(axis=0)
        return (
            float(low[0]),
            float(high[0]),
            float(low[1]),
            float(high[1]),
            float(low[2]),
            float(high[2]),
        )

    def set_pickable(self, pickable: bool) -> None:
        self.pickable = bool(pickable)

    def update_points(self, points: np.ndarray) -> None:
        fresh = np.asarray(points, dtype=float).reshape(-1, 3)
        if len(fresh) != len(self.points):
            raise ValueError(f"{self.name}: {len(fresh)} Punkte für {len(self.points)}")
        self.points = fresh

    def set_line_width(self, width: float) -> None:
        self.line_width = float(width)


class RecordingLabels(RecordingItem, LabelsItem):
    """Beschriftungen — Anker und Texte, sonst nichts."""

    def __init__(
        self, name: str, points: np.ndarray, texts: Sequence[str], style: LabelStyle
    ) -> None:
        super().__init__(name, points, style.text_colour)
        self.texts = [str(text) for text in texts]
        self.style = style

    def update_labels(self, points: np.ndarray, texts: Sequence[str]) -> None:
        self.points = np.asarray(points, dtype=float).reshape(-1, 3)
        self.texts = [str(text) for text in texts]


class RecordingRenderer(Renderer):
    """Der Vertrag, erfüllt mit Buchführung.

    ``drawn`` trägt je Aufruf die Art (``surface``, ``lines``, ``points``,
    ``labels``), den Namen und die Argumente — Stil, Farbe, Breite, Zellfarben —
    und das entstandene Element. ``names()``, ``colour_of()`` und ``style_of()``
    lesen darin; ``labelled`` sammelt die Beschriftungen, ``removed`` die
    entfernten Elemente, ``renders`` zählt die Bilder.

    Die Kamera ist eine Stellung ohne Optik: ``world_to_display`` skaliert x
    und y mit ``scale`` und zählt y von oben; ``display_to_world`` rechnet
    zurück. ``pick_surface`` und ``pick_item`` antworten, was in ``picks``
    hinterlegt ist — sonst nichts.
    """

    def __init__(self, size: tuple[int, int] = (800, 600), scale: float = 2.0) -> None:
        self.widget: Any = None
        self.drawn: list[tuple[str, dict[str, Any]]] = []
        self.items: list[RecordingItem] = []
        self.meshes: list[tuple[np.ndarray, np.ndarray]] = []
        self.labelled: list[list[str]] = []
        self.removed: list[Item] = []
        self.renders = 0
        self.draw_orders: list[list[Item]] = []
        self.reset_bounds: list[Bounds | None] = []
        self.pose = CameraPose((100.0, -100.0, 80.0), (0.0, 0.0, 0.0), (0.0, 0.0, 1.0))
        self.poses: list[CameraPose] = []
        self.parallel = False
        self.scale_value = 50.0
        self.dollied: list[float] = []
        self.background_colour: Colour = "#101418"
        self.background_top: Colour | None = None
        self.headlight: float | None = None
        self.anti_aliasing: bool | None = None
        self.occlusion: list[tuple[bool, float, float]] = []
        self.axes_markers: list[AxesMarkerStyle | None] = []
        self.marker_corners: list[tuple[float, float, float, float]] = []
        self.size = size
        self.scale = scale
        self.picks: dict[tuple[int, int], Pick] = {}
        self.item_picks: dict[tuple[int, int], Item] = {}
        self.listeners: dict[int, Callable[[PointerEvent], None]] = {}
        self.closed = False
        self.clips = 0
        self.pick_calls: list[tuple[float, float, list[Item] | None, float]] = []

    # --- Buchführung -----------------------------------------------------------------

    def names(self) -> list[str]:
        """Die Namen aller Elemente in der Reihenfolge, in der sie entstanden."""
        return [str(kwargs["name"]) for _kind, kwargs in self.drawn]

    def entries(self, name: str) -> list[dict[str, Any]]:
        return [kwargs for _kind, kwargs in self.drawn if str(kwargs.get("name")) == name]

    def colour_of(self, name: str) -> str:
        """Die Farbe, mit der dieses eine Element gezeichnet wurde."""
        for _kind, kwargs in self.drawn:
            if str(kwargs.get("name")) == name:
                style = kwargs.get("style")
                if style is not None:
                    return str(style.colour)
                return str(kwargs.get("colour"))
        raise AssertionError(f"kein Element namens {name!r} — gezeichnet wurde: {self.names()}")

    def style_of(self, name: str) -> SurfaceStyle:
        for kwargs in self.entries(name):
            style = kwargs.get("style")
            if isinstance(style, SurfaceStyle):
                return style
        raise AssertionError(f"keine Fläche namens {name!r} — gezeichnet wurde: {self.names()}")

    def item_of(self, name: str) -> RecordingItem:
        """Das Element, das unter diesem Namen **im Bild steht**.

        Das jüngste, das nicht entfernt wurde — eine Vorschau wird abgeräumt
        und unter demselben Namen neu gezeichnet, und wer das erste nähme,
        läse den Stand vor dem Abräumen.
        """
        for kwargs in reversed(self.entries(name)):
            item = kwargs.get("item")
            if isinstance(item, RecordingItem) and item not in self.removed:
                return item
        raise AssertionError(
            f"kein Element namens {name!r} im Bild — gezeichnet wurde: {self.names()}"
        )

    # --- Der Vertrag ------------------------------------------------------------------

    def add_surface(
        self,
        vertices: np.ndarray,
        faces: np.ndarray,
        *,
        name: str,
        style: SurfaceStyle,
        cell_colours: CellColours | None = None,
    ) -> Item:
        item = RecordingItem(name, vertices, style.colour, style.opacity)
        item.pickable = style.pickable
        self.meshes.append((np.asarray(vertices, dtype=float), np.asarray(faces)))
        self.drawn.append(
            ("surface", {"name": name, "style": style, "cell_colours": cell_colours, "item": item})
        )
        self.items.append(item)
        return item

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
        item = RecordingItem(name, points, colour)
        item.pickable = pickable
        item.line_width = float(width)
        self.drawn.append(
            (
                "lines",
                {
                    "name": name,
                    "colour": colour,
                    "width": width,
                    "pickable": pickable,
                    "keep_in_front": keep_in_front,
                    "connected": connected,
                    "polylines": list(polylines) if polylines is not None else None,
                    "item": item,
                },
            )
        )
        self.items.append(item)
        return item

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
        item = RecordingItem(name, points, colour)
        item.pickable = pickable
        self.drawn.append(
            (
                "points",
                {
                    "name": name,
                    "colour": colour,
                    "size": size,
                    "pickable": pickable,
                    "keep_in_front": keep_in_front,
                    "item": item,
                },
            )
        )
        self.items.append(item)
        return item

    def add_labels(
        self, points: np.ndarray, texts: Sequence[str], *, name: str, style: LabelStyle
    ) -> LabelsItem:
        item = RecordingLabels(name, points, texts, style)
        self.labelled.append([str(text) for text in texts])
        self.drawn.append(("labels", {"name": name, "style": style, "item": item}))
        self.items.append(item)
        return item

    def remove(self, item: Item) -> None:
        self.removed.append(item)

    def set_draw_order(self, items: Sequence[Item]) -> None:
        self.draw_orders.append(list(items))

    def camera_pose(self) -> CameraPose:
        return self.pose

    def set_camera_pose(self, pose: CameraPose) -> None:
        self.pose = pose
        self.poses.append(pose)

    def parallel_projection(self) -> bool:
        return self.parallel

    def set_parallel_projection(self, parallel: bool) -> None:
        self.parallel = bool(parallel)

    def parallel_scale(self) -> float:
        return self.scale_value

    def set_parallel_scale(self, scale: float) -> None:
        self.scale_value = float(scale)

    def view_angle(self) -> float:
        return 30.0

    def dolly(self, factor: float) -> None:
        self.dollied.append(float(factor))

    def reset_camera(self, bounds: Bounds | None = None) -> None:
        self.reset_bounds.append(bounds)

    def reset_clipping_range(self) -> None:
        self.clips += 1

    def view_size(self) -> tuple[int, int]:
        return self.size

    def world_to_display(self, point: Vec3) -> tuple[float, float, float]:
        return (
            float(point[0]) * self.scale + self.size[0] / 2.0,
            self.size[1] / 2.0 - float(point[1]) * self.scale,
            0.5,
        )

    def display_to_world(self, x: float, y: float, depth: float) -> Vec3 | None:
        return (
            (float(x) - self.size[0] / 2.0) / self.scale,
            (self.size[1] / 2.0 - float(y)) / self.scale,
            (float(depth) - 0.5) * 100.0,
        )

    def focal_depth(self) -> float:
        return 0.5

    def pick_surface(
        self,
        x: float,
        y: float,
        *,
        among: Sequence[Item] | None = None,
        tolerance: float = 0.005,
    ) -> Pick | None:
        self.pick_calls.append((x, y, list(among) if among is not None else None, tolerance))
        found = self.picks.get((round(x), round(y)))
        if found is not None and among is not None and found.item not in among:
            return None
        return found

    def pick_item(self, x: float, y: float) -> Item | None:
        return self.item_picks.get((round(x), round(y)))

    def render(self) -> None:
        self.renders += 1

    def screenshot(self) -> np.ndarray:
        return np.zeros((self.size[1], self.size[0], 3), dtype=np.uint8)

    def set_background(self, colour: Colour, top: Colour | None = None) -> None:
        self.background_colour = colour
        self.background_top = top

    def background(self) -> Colour:
        return self.background_colour

    def set_headlight(self, intensity: float) -> None:
        self.headlight = float(intensity)

    def set_anti_aliasing(self, enabled: bool) -> None:
        self.anti_aliasing = bool(enabled)

    def set_ambient_occlusion(self, enabled: bool, *, radius: float, bias: float) -> None:
        self.occlusion.append((bool(enabled), radius, bias))

    def set_axes_marker(self, style: AxesMarkerStyle | None) -> None:
        self.axes_markers.append(style)

    def place_axes_marker(self, corner: tuple[float, float, float, float]) -> None:
        self.marker_corners.append(corner)

    def add_pointer_listener(self, listener: Callable[[PointerEvent], None]) -> int:
        token = len(self.listeners) + 1
        self.listeners[token] = listener
        return token

    def remove_pointer_listener(self, token: int) -> None:
        self.listeners.pop(token, None)

    def close(self) -> None:
        self.closed = True


class BrokenDriverRenderer(RecordingRenderer):
    """Ein Renderer, dessen OpenGL die schönen Sachen nicht kann.

    Genau die Maschine, für die die ``try``-Blöcke geschrieben sind: Sie soll
    ein einfacheres Bild bekommen und keinen Absturz.
    """

    def set_anti_aliasing(self, enabled: bool) -> None:
        raise RuntimeError("kein FXAA auf diesem Treiber")

    def set_ambient_occlusion(self, enabled: bool, *, radius: float, bias: float) -> None:
        raise RuntimeError("kein SSAO auf diesem Treiber")
