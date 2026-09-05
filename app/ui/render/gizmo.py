"""Der Bewegungsgriff: drei Pfeile zum Schieben, drei Ringe zum Drehen (§18.11).

Bis zum 05.09.2026 war das PyVistas ``AffineWidget3D`` — mit einem
Hardware-Picker, der in dieser Umgebung nichts traf, einem Interaktionsstil,
der beim Greifen auf VTKs Trackball wechselte, und einer Zugrechnung, die
Bildpunkte über einen Faktor „experimentell bestimmt" in Weltmaße brachte.
Dieser Griff tut dasselbe auf dem Renderer-Vertrag, und drei Dinge anders:

* **Er pickt mit dem Zell-Picker des Renderers** (``pick_item``), der hier
  trifft — dieselbe Wahl, die der Viewport für jeden Klick trifft.
* **Der Zug ist geometrisch**: Beim Schieben wird der Sichtstrahl auf die
  Achse gelotet (nächster Punkt zweier Geraden), beim Drehen mit der Ebene
  quer zur Achse geschnitten. Die Spitze folgt dem Zeiger, gleich wie weit
  die Kamera weg ist.
* **Er hält keinen Stil an**: Wer ihn greift, bekommt ``True`` von
  :meth:`handle` zurück, und der Viewport gibt die Geste nicht an den
  Navigator weiter. Das ist die ganze Vorfahrt.

Was der Griff nicht tut: Geometrie ändern. Er setzt eine Matrix an den
Griff des Körpers (:meth:`Item.set_matrix`) — eine Vorschau —, und beim
Loslassen bekommt die Ansicht die Matrix, aus der sie Operationen macht
(Regel 2).
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from typing import Any

import numpy as np

from app.core.units import EPS_GEOM
from app.ui.render import shapes
from app.ui.render.api import Colour, Item, PointerEvent, Renderer, SurfaceStyle, Vec3

#: Die Achsenfarben, wie PyVista sie führte (Rot, Grün, Blau).
AXIS_COLOURS: tuple[Colour, Colour, Colour] = ("#e0483e", "#5cb85c", "#3e8ee0")
#: PyVistas ``DARK_YELLOW`` beim Überfahren — derselbe Ton am Skalierwürfel.
HIGHLIGHT: Colour = "#f6be00"
#: Die Pfeillänge im Maß der Körperdiagonale mal ``scale`` (PyVista: 1,15),
#: der Ringradius entsprechend 1,6 — beide übernommen, damit der Griff nach
#: dem Umbau aussieht wie davor.
ARROW_SHARE = 1.15
RING_SHARE = 1.6
#: Spitze und Schaft im Maß der Pfeillänge (PyVista: ``tip_radius=0.05``).
TIP_RADIUS_SHARE = 0.05
#: Ringbreite in Bildpunkten. PyVista zeichnete Röhren in Weltmaß; Linien
#: in Bildpunkten bleiben bei jedem Zoom greifbar.
RING_WIDTH = 4.0
RING_SEGMENTS = 64


def _unit(vector: Sequence[float]) -> np.ndarray:
    array = np.asarray(vector, dtype=float)
    length = float(np.linalg.norm(array))
    return array / length if length > EPS_GEOM else array


def closest_axis_parameter(
    ray_start: Vec3, ray_direction: Vec3, origin: Vec3, axis: Vec3
) -> float | None:
    """Wo auf der Achse der Sichtstrahl ihr am nächsten kommt — als Parameter
    entlang ``axis`` von ``origin`` aus, oder ``None``, wenn beide parallel
    laufen."""
    p = np.asarray(origin, dtype=float)
    u = _unit(axis)
    q = np.asarray(ray_start, dtype=float)
    v = _unit(ray_direction)
    w = p - q
    a = float(np.dot(u, u))
    b = float(np.dot(u, v))
    c = float(np.dot(v, v))
    d = float(np.dot(u, w))
    e = float(np.dot(v, w))
    denominator = a * c - b * b
    if abs(denominator) <= 1e-12:
        return None
    return (b * e - c * d) / denominator


def ray_plane_hit(
    ray_start: Vec3, ray_direction: Vec3, plane_point: Vec3, normal: Vec3
) -> np.ndarray | None:
    """Wo ein Strahl eine Ebene trifft — oder nichts, wenn er ihr parallel läuft."""
    direction = np.asarray(ray_direction, dtype=float)
    n = np.asarray(normal, dtype=float)
    denominator = float(np.dot(direction, n))
    if abs(denominator) < 1e-12:
        return None
    start = np.asarray(ray_start, dtype=float)
    step = float(np.dot(np.asarray(plane_point, dtype=float) - start, n)) / denominator
    return start + direction * step


def rotation_matrix(axis: Vec3, origin: Vec3, degrees: float) -> np.ndarray:
    """Eine Drehung um eine Achse durch ``origin``, als 4-mal-4-Matrix."""
    u = _unit(axis)
    angle = math.radians(degrees)
    cos, sin = math.cos(angle), math.sin(angle)
    cross = np.array([[0.0, -u[2], u[1]], [u[2], 0.0, -u[0]], [-u[1], u[0], 0.0]])
    rotation = cos * np.eye(3) + sin * cross + (1.0 - cos) * np.outer(u, u)
    o = np.asarray(origin, dtype=float)
    matrix = np.eye(4)
    matrix[:3, :3] = rotation
    matrix[:3, 3] = o - rotation @ o
    return matrix


class Gizmo:
    """Pfeile und Ringe an einem Griff der Szene.

    ``release_callback`` bekommt beim Loslassen die Matrix des Zugs;
    ``interact_callback`` jeden Zwischenstand und darf eine berichtigte
    Matrix zurückgeben (der Magnet auf die Raste, §18.11) — die wird dann
    gesetzt, nicht die rohe.
    """

    def __init__(
        self,
        renderer: Renderer,
        target: Item,
        *,
        origin: Vec3 | None = None,
        scale: float = 0.15,
        line_radius: float = 0.02,
        axes: np.ndarray | None = None,
        release_callback: Callable[[np.ndarray], None] | None = None,
        interact_callback: Callable[[np.ndarray], np.ndarray | None] | None = None,
    ) -> None:
        self._renderer = renderer
        self.target = target
        self._release = release_callback
        self._interact = interact_callback
        self._origin = np.asarray(origin if origin is not None else target.centre(), dtype=float)
        self._axes = np.eye(3) if axes is None else _validated(axes)
        self._cached = target.matrix()
        self._length = float(target.length())
        self._arrow_length = self._length * scale * ARROW_SHARE
        self._ring_radius = self._length * scale * RING_SHARE
        self._line_radius = line_radius * self._arrow_length
        self._arrows: list[Item] = []
        self._rings: list[Item] = []
        self._selected: tuple[str, int] | None = None
        self.pressing = False
        self._init_parameter: float | None = None
        self._init_vector: np.ndarray | None = None
        self._build()

    # --- Aufbau --------------------------------------------------------------------

    def _build(self) -> None:
        for index in range(3):
            colour = AXIS_COLOURS[index]
            vertices, faces = shapes.arrow(
                self._origin,
                self._axes[index],
                self._arrow_length,
                shaft_radius=self._line_radius,
                tip_radius=TIP_RADIUS_SHARE * self._arrow_length,
            )
            self._arrows.append(
                self._renderer.add_surface(
                    vertices,
                    faces,
                    name=f"gizmo:arrow:{index}",
                    style=SurfaceStyle(
                        colour=colour, lighting=False, keep_in_front=True, pickable=True
                    ),
                )
            )
            ring = shapes.closed_ring(
                shapes.circle_points(
                    self._origin, self._axes[index], self._ring_radius, RING_SEGMENTS
                )
            )
            self._rings.append(
                self._renderer.add_lines(
                    ring,
                    name=f"gizmo:ring:{index}",
                    colour=colour,
                    width=RING_WIDTH,
                    pickable=True,
                    keep_in_front=True,
                    connected=True,
                )
            )

    def remove(self) -> None:
        for item in (*self._arrows, *self._rings):
            self._renderer.remove(item)
        self._arrows.clear()
        self._rings.clear()
        self._selected = None
        self.pressing = False

    @property
    def axes(self) -> np.ndarray:
        return self._axes.copy()

    @property
    def origin(self) -> Vec3:
        return (float(self._origin[0]), float(self._origin[1]), float(self._origin[2]))

    @property
    def items(self) -> tuple[Item, ...]:
        return (*self._arrows, *self._rings)

    # --- Gesten ----------------------------------------------------------------------

    def handle(self, event: PointerEvent) -> bool:
        """Eine Zeigergeste — wahr, wenn sie dem Griff gehört."""
        if event.kind == "move":
            if self.pressing:
                self._drag(event)
                return True
            self._hover(event)
            return False
        if event.kind == "press" and event.button == "left":
            if self._selected is None:
                return False
            self.pressing = True
            self._begin(event)
            return True
        if event.kind == "release" and event.button == "left" and self.pressing:
            self.pressing = False
            self._cached = self.target.matrix()
            if self._release is not None:
                self._release(self._cached.copy())
            return True
        if event.kind == "leave" and not self.pressing:
            self._select(None)
        return False

    def _hover(self, event: PointerEvent) -> None:
        found = self._renderer.pick_item(event.x, event.y)
        wanted: tuple[str, int] | None = None
        for index, item in enumerate(self._arrows):
            if found is item:
                wanted = ("arrow", index)
        for index, item in enumerate(self._rings):
            if found is item:
                wanted = ("ring", index)
        if wanted != self._selected:
            self._select(wanted)
            self._renderer.render()

    def _select(self, wanted: tuple[str, int] | None) -> None:
        if self._selected is not None:
            kind, index = self._selected
            (self._arrows if kind == "arrow" else self._rings)[index].set_colour(
                AXIS_COLOURS[index]
            )
        self._selected = wanted
        if wanted is not None:
            kind, index = wanted
            (self._arrows if kind == "arrow" else self._rings)[index].set_colour(HIGHLIGHT)

    def _ray(self, event: PointerEvent) -> tuple[Vec3, Vec3] | None:
        near = self._renderer.display_to_world(event.x, event.y, 0.0)
        far = self._renderer.display_to_world(event.x, event.y, 1.0)
        if near is None or far is None:
            return None
        direction = (far[0] - near[0], far[1] - near[1], far[2] - near[2])
        if math.sqrt(sum(value * value for value in direction)) <= EPS_GEOM:
            return None
        return near, direction

    def _begin(self, event: PointerEvent) -> None:
        assert self._selected is not None
        kind, index = self._selected
        ray = self._ray(event)
        self._init_parameter = None
        self._init_vector = None
        if ray is None:
            return
        if kind == "arrow":
            self._init_parameter = closest_axis_parameter(
                ray[0], ray[1], self.origin, tuple(self._axes[index])
            )
        else:
            hit = ray_plane_hit(ray[0], ray[1], self.origin, tuple(self._axes[index]))
            if hit is not None:
                self._init_vector = self._flatten(hit - self._origin, index)

    def _flatten(self, vector: np.ndarray, index: int) -> np.ndarray | None:
        normal = self._axes[index]
        flat = vector - np.dot(vector, normal) * normal
        length = float(np.linalg.norm(flat))
        return flat / length if length > EPS_GEOM else None

    def _drag(self, event: PointerEvent) -> None:
        assert self._selected is not None
        kind, index = self._selected
        ray = self._ray(event)
        if ray is None:
            return
        matrix: np.ndarray | None = None
        if kind == "arrow" and self._init_parameter is not None:
            now = closest_axis_parameter(ray[0], ray[1], self.origin, tuple(self._axes[index]))
            if now is None:
                return
            shift = np.eye(4)
            shift[:3, 3] = self._axes[index] * (now - self._init_parameter)
            matrix = shift @ self._cached
        elif kind == "ring" and self._init_vector is not None:
            hit = ray_plane_hit(ray[0], ray[1], self.origin, tuple(self._axes[index]))
            if hit is None:
                return
            current = self._flatten(hit - self._origin, index)
            if current is None:
                return
            cosine = float(np.clip(np.dot(self._init_vector, current), -1.0, 1.0))
            angle = math.degrees(math.acos(cosine))
            if float(np.dot(np.cross(self._init_vector, current), self._axes[index])) < 0.0:
                angle = -angle
            matrix = rotation_matrix(tuple(self._axes[index]), self.origin, angle) @ self._cached
        if matrix is None:
            return
        if self._interact is not None:
            corrected = self._interact(matrix)
            if corrected is not None:
                matrix = corrected
        self.target.set_matrix(matrix)
        self._renderer.render()


def _validated(axes: Any) -> np.ndarray:
    """Drei Achsen, rechtshändig und normiert — wie PyVista es verlangte."""
    array = np.asarray(axes, dtype=float)
    if array.shape != (3, 3):
        raise ValueError("Achsen müssen eine 3-mal-3-Matrix sein")
    array = array / np.linalg.norm(array, axis=1, keepdims=True)
    if not np.allclose(np.cross(array[0], array[1]), array[2], atol=1e-6):
        raise ValueError("Achsen folgen nicht der rechten Hand")
    return np.asarray(array, dtype=float)
