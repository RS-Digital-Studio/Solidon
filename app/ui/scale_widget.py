"""Der Skaliergriff am Gizmo (Bauplan §18.11).

§18.11 nennt Verschieben, Drehen **und Skalieren** — der Bewegungsgriff
(``render/gizmo.py``) kann die ersten beiden. Dieser Griff ergänzt das
dritte: ein Würfel schräg über dem Gizmo, auf der Raumdiagonale zwischen den
drei Pfeilen. Ziehen vom Zentrum weg vergrößert, zum Zentrum hin verkleinert;
die Vorschau skaliert live um die Mitte des Körpers, und erst das Loslassen
wird eine Operation — dieselbe Zusage wie bei jedem anderen Zug (§2.1).

Die Form trägt die Bedeutung, nicht die Farbe (Regel 18): ein Würfel neben
Pfeilen und Ringen, dazu das S der Beschriftung. Beim Überfahren leuchtet er
in derselben Farbe wie die Pfeile des Bewegungsgriffs — ein Griff-Satz, eine
Sprache.

Bis zum 05.09.2026 war er PyVistas ``AffineWidget3D`` Zeile für Zeile
nachgebaut: drei Beobachter am Interactor, ein Stilwechsel beim Greifen. Auf
dem Renderer-Vertrag ist er gebaut wie der Bewegungsgriff daneben —
:meth:`ScaleHandle.handle` bekommt jede Zeigergeste und sagt mit ``True``,
dass sie ihm gehört; der Viewport gibt sie dann nicht an die Kameraführung
weiter. Wer dort etwas am Gestenmuster ändert, prüft hier.
"""

from __future__ import annotations

import math
from collections.abc import Callable

from app.core.units import EPS_GEOM
from app.ui.render import shapes
from app.ui.render.api import Colour, Item, PointerEvent, Renderer, SurfaceStyle, Vec3
from app.ui.render.gizmo import ARROW_SHARE, HIGHLIGHT, ray_plane_hit

#: Kantenlänge des Würfels als Anteil der Hüllquader-Diagonale des Körpers.
#: Im Maß der Pfeildicke gehalten: greifbar, ohne die Ringe zu verdecken.
CUBE_SHARE = 0.045

#: Wohin der Griff liegt: auf der Raumdiagonale, im selben Abstand wie die
#: Pfeilspitzen — außerhalb des Körpers, zwischen den Achsen.
DIAGONAL = (0.577350269, 0.577350269, 0.577350269)

#: Wie weit ein einzelner Zug den Faktor treiben kann. Die Operation erlaubt
#: 0,01 bis 100; ein Zug bleibt enger, denn wer das Zwanzigfache will, meint
#: eine Zahl und keinen Mausweg.
FACTOR_RANGE = (0.05, 20.0)

#: Die Hervorhebung beim Überfahren — dieselbe wie an Pfeilen und Ringen,
#: damit alle Griffe des Gizmos dieselbe Sprache sprechen.
HOVER_COLOUR: Colour = HIGHLIGHT

__all__ = [
    "CUBE_SHARE",
    "DIAGONAL",
    "FACTOR_RANGE",
    "HOVER_COLOUR",
    "ScaleHandle",
    "dragged_factor",
    "ray_plane_hit",
]


def dragged_factor(
    centre: tuple[float, float, float],
    grip_start: tuple[float, float, float],
    grip_now: tuple[float, float, float],
) -> float:
    """Der Skalierfaktor eines Zugs: Ist-Abstand durch Start-Abstand.

    Eingespannt in ``FACTOR_RANGE`` — ein Zug durchs Zentrum hindurch darf
    das Teil nicht auf null zusammenziehen, und ein ausgerutschter Zeiger
    nicht auf Weltgröße aufblasen.
    """
    start = math.dist(centre, grip_start)
    if start < 1e-9:
        return 1.0
    factor = math.dist(centre, grip_now) / start
    return min(max(factor, FACTOR_RANGE[0]), FACTOR_RANGE[1])


class ScaleHandle:
    """Der Würfel, an dem gleichmäßig skaliert wird.

    ``release_callback`` bekommt den Faktor des Zugs, ``interact_callback``
    jeden Zwischenstand — für die Zahl im Eingabefeld, nicht für Geometrie:
    Die Vorschau ist eine Matrix am Griff des Körpers
    (:meth:`Item.set_matrix`) und verschwindet mit ihm.

    ``scale`` ist der Maßstab des Bewegungsgriffs daneben. Der Würfel liegt
    im selben Abstand wie dessen Pfeilspitzen (``scale · ARROW_SHARE`` der
    Körperlänge), damit er zwischen den Spitzen steht und nicht vor ihnen.
    """

    def __init__(
        self,
        renderer: Renderer,
        target: Item,
        *,
        scale: float,
        colour: Colour,
        release_callback: Callable[[float], None],
        interact_callback: Callable[[float], None] | None = None,
    ) -> None:
        from app.core.geom.transform import scaling

        self._renderer = renderer
        self._target = target
        self._release = release_callback
        self._interact = interact_callback
        self._scaling = scaling
        self._centre = target.centre()
        self._length = float(target.length())
        self._colour = colour
        self._start: Vec3 | None = None
        self._factor = 1.0
        self._hovered = False
        self.pressing = False

        reach = self._length * scale * ARROW_SHARE
        size = self._length * CUBE_SHARE
        self.grip_position: Vec3 = (
            self._centre[0] + DIAGONAL[0] * reach,
            self._centre[1] + DIAGONAL[1] * reach,
            self._centre[2] + DIAGONAL[2] * reach,
        )
        """Wo der Würfel sitzt — die Beschriftung stellt ihr S dahinter."""
        vertices, faces = shapes.cube(self.grip_position, size)
        # Sichtbar auch vor dem Körper — derselbe Kniff, mit dem Pfeile und
        # Ringe des Bewegungsgriffs nach vorn kommen.
        self._cube = renderer.add_surface(
            vertices,
            faces,
            name="scale-handle",
            style=SurfaceStyle(colour=colour, lighting=False, keep_in_front=True, pickable=True),
        )

    @property
    def item(self) -> Item:
        """Der Würfel im Renderer — für die Beschriftung und die Tests."""
        return self._cube

    def remove(self) -> None:
        """Den Würfel aus dem Bild nehmen; eine laufende Geste endet damit."""
        self._renderer.remove(self._cube)
        self._hovered = False
        self.pressing = False
        self._start = None

    # --- Gesten, dem Bewegungsgriff nachgebaut ---------------------------------------

    def handle(self, event: PointerEvent) -> bool:
        """Eine Zeigergeste — wahr, wenn sie dem Würfel gehört."""
        if event.kind == "move":
            if self.pressing:
                self._drag(event)
                return True
            self._hover(event)
            return False
        if event.kind == "press" and event.button == "left":
            if not self._hovered:
                return False
            grip = self._pointer_on_plane(event)
            if grip is None or math.dist(self._centre, grip) < 1e-9:
                return False
            self._start = grip
            self._factor = 1.0
            self.pressing = True
            return True
        if event.kind == "release" and event.button == "left" and self.pressing:
            self.pressing = False
            self._start = None
            self._release(self._factor)
            return True
        if event.kind == "leave" and not self.pressing:
            self._set_hovered(False)
        return False

    def _hover(self, event: PointerEvent) -> None:
        hovered = self._renderer.pick_item(event.x, event.y) is self._cube
        if hovered != self._hovered:
            self._set_hovered(hovered)
            self._renderer.render()

    def _set_hovered(self, hovered: bool) -> None:
        self._hovered = hovered
        self._cube.set_colour(HOVER_COLOUR if hovered else self._colour)

    def _pointer_on_plane(self, event: PointerEvent) -> Vec3 | None:
        """Der Zeiger in Weltkoordinaten, auf der Kameraebene durchs Zentrum.

        Auf der Ebene senkrecht zur Blickrichtung, wie beim Drehring des
        Bewegungsgriffs: Dort ist der Abstand zum Zentrum unabhängig davon,
        wie tief der Strahl in die Szene liefe.
        """
        near = self._renderer.display_to_world(event.x, event.y, 0.0)
        far = self._renderer.display_to_world(event.x, event.y, 1.0)
        if near is None or far is None:
            return None
        direction = (far[0] - near[0], far[1] - near[1], far[2] - near[2])
        camera = self._renderer.camera_pose().position
        towards = tuple(camera[axis] - self._centre[axis] for axis in range(3))
        span = math.sqrt(sum(value * value for value in towards))
        if span <= EPS_GEOM:
            return None
        normal = (towards[0] / span, towards[1] / span, towards[2] / span)
        hit = ray_plane_hit(near, direction, self._centre, normal)
        if hit is None:
            return None
        return (float(hit[0]), float(hit[1]), float(hit[2]))

    def _drag(self, event: PointerEvent) -> None:
        if self._start is None:
            return
        grip = self._pointer_on_plane(event)
        if grip is None:
            return
        self._factor = dragged_factor(self._centre, self._start, grip)
        self._target.set_matrix(
            self._scaling((self._factor, self._factor, self._factor), about=self._centre)
        )
        if self._interact is not None:
            self._interact(self._factor)
        self._renderer.render()
