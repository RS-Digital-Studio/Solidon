"""Der Skaliergriff am Gizmo (Bauplan §18.11).

§18.11 nennt Verschieben, Drehen **und Skalieren** — pyvistas
``AffineWidget3D`` kann nur die ersten beiden. Dieser Griff ergänzt das
dritte: ein Würfel schräg über dem Gizmo, auf der Raumdiagonale zwischen den
drei Pfeilen. Ziehen vom Zentrum weg vergrößert, zum Zentrum hin verkleinert;
die Vorschau skaliert live um die Mitte des Körpers, und erst das Loslassen
wird eine Operation — dieselbe Zusage wie bei jedem anderen Zug (§2.1).

Die Form trägt die Bedeutung, nicht die Farbe (Regel 18): ein Würfel neben
Pfeilen und Ringen, dazu das S der Beschriftung. Beim Überfahren leuchtet er
in derselben Farbe wie pyvistas eigene Griffe — ein Griff-Satz, eine Sprache.

Die Interaktion folgt Zeile für Zeile dem Muster des ``AffineWidget3D``:
dieselben drei Beobachter am Interactor, derselbe Stilwechsel beim Greifen
(sonst drehte der Zug die Kamera mit), dieselbe Rückgabe beim Loslassen. Wer
dort etwas ändert, prüft hier.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from typing import Any

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

#: Die Hervorhebung beim Überfahren — pyvistas eigener Wert, damit alle
#: Griffe des Gizmos dieselbe Sprache sprechen.
HOVER_COLOUR = "#ffc700"


def ray_plane_hit(
    start: tuple[float, float, float],
    direction: tuple[float, float, float],
    plane_point: tuple[float, float, float],
    normal: tuple[float, float, float],
) -> tuple[float, float, float] | None:
    """Wo ein Strahl eine Ebene trifft — oder nichts, wenn er ihr parallel läuft.

    Selbst gerechnet statt aus pyvistas ``affine_widget`` importiert: das
    Modul ist Innenleben ohne Bestandszusage, und die Rechnung sind vier
    Zeilen.
    """
    denominator = sum(direction[axis] * normal[axis] for axis in range(3))
    if abs(denominator) < 1e-12:
        return None
    offset = sum((plane_point[axis] - start[axis]) * normal[axis] for axis in range(3))
    step = offset / denominator
    return (
        start[0] + direction[0] * step,
        start[1] + direction[1] * step,
        start[2] + direction[2] * step,
    )


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
    die Vorschau ist eine ``user_matrix`` am Actor und verschwindet mit ihm.
    """

    def __init__(
        self,
        plotter: Any,
        actor: Any,
        *,
        colour: str,
        release_callback: Callable[[float], None],
        interact_callback: Callable[[float], None] | None = None,
    ) -> None:
        import pyvista as pv

        from app.core.geom.transform import scaling

        self._plotter = plotter
        self._actor = actor
        self._release = release_callback
        self._interact = interact_callback
        self._scaling = scaling
        self._centre = (
            float(actor.center[0]),
            float(actor.center[1]),
            float(actor.center[2]),
        )
        self._length = float(actor.GetLength())
        self._colour = colour
        self._start: tuple[float, float, float] | None = None
        self._factor = 1.0
        self._hovered = False

        reach = self._length * self.arm_share()
        size = self._length * CUBE_SHARE
        position = tuple(self._centre[axis] + DIAGONAL[axis] * reach for axis in range(3))
        self.grip_position = position
        """Wo der Würfel sitzt — die Beschriftung stellt ihr S dahinter."""
        cube = pv.Cube(center=position, x_length=size, y_length=size, z_length=size)
        self._cube = plotter.add_mesh(
            cube,
            color=colour,
            lighting=False,
            name="scale-handle",
            render=False,
            reset_camera=False,
        )
        # Sichtbar auch vor dem Körper — derselbe Kniff, mit dem pyvista
        # seine Pfeile und Ringe nach vorn holt.
        self._cube.mapper.SetResolveCoincidentTopologyToPolygonOffset()
        self._cube.mapper.SetRelativeCoincidentTopologyPolygonOffsetParameters(0, -20000)

        self._observers = [
            ("MouseMoveEvent", plotter.iren.add_observer("MouseMoveEvent", self._on_move)),
            (
                "LeftButtonPressEvent",
                plotter.iren.add_observer(
                    "LeftButtonPressEvent", self._on_press, interactor_style_fallback=False
                ),
            ),
            (
                "LeftButtonReleaseEvent",
                plotter.iren.add_observer(
                    "LeftButtonReleaseEvent", self._on_release, interactor_style_fallback=False
                ),
            ),
        ]

    @staticmethod
    def arm_share() -> float:
        """Abstand des Würfels vom Zentrum, im Maß der Pfeile des Gizmos.

        pyvista streckt seine Pfeile auf ``scale · 1,15`` der Körperlänge;
        der Würfel liegt im selben Abstand, damit er zwischen den Spitzen
        steht und nicht vor ihnen.
        """
        from app.ui.viewport import GIZMO_SCALE

        return GIZMO_SCALE * 1.15

    def remove(self) -> None:
        """Beobachter abmelden und den Würfel aus dem Bild nehmen."""
        for _event, identifier in self._observers:
            self._plotter.iren.remove_observer(identifier)
        self._observers = []
        self._plotter.remove_actor(self._cube, render=False)

    # --- Interaktion, dem AffineWidget3D nachgebaut -------------------------------

    def _grip_at_pointer(self, interactor: Any) -> bool:
        """Ob der Zeiger auf dem Würfel steht."""
        x, y = interactor.GetEventPosition()
        picker = interactor.GetPicker()
        renderer = interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
        picker.Pick(x, y, 0, renderer)
        return picker.GetActor() is self._cube

    def _pointer_on_plane(self, interactor: Any) -> tuple[float, float, float] | None:
        """Der Zeiger in Weltkoordinaten, auf der Kameraebene durchs Zentrum.

        Auf der Ebene senkrecht zur Blickrichtung, wie beim Drehgriff von
        pyvista: dort ist der Abstand zum Zentrum unabhängig davon, wie tief
        der Strahl in die Szene liefe.
        """
        from vtkmodules.vtkRenderingCore import vtkCoordinate

        x, y = interactor.GetEventPosition()
        coordinate = vtkCoordinate()
        coordinate.SetCoordinateSystemToDisplay()
        coordinate.SetValue(x, y, 0)
        renderer = interactor.GetRenderWindow().GetRenderers().GetFirstRenderer()
        world = coordinate.GetComputedWorldValue(renderer)
        camera = renderer.GetActiveCamera().GetPosition()
        towards = tuple(camera[axis] - self._centre[axis] for axis in range(3))
        span = math.sqrt(sum(value * value for value in towards)) or 1.0
        normal = (towards[0] / span, towards[1] / span, towards[2] / span)
        return ray_plane_hit(
            (float(world[0]), float(world[1]), float(world[2])), towards, self._centre, normal
        )

    def _on_move(self, interactor: Any, _event: Any) -> None:
        if self._start is not None:
            grip = self._pointer_on_plane(interactor)
            if grip is None:
                return
            self._factor = dragged_factor(self._centre, self._start, grip)
            self._actor.user_matrix = self._scaling(
                (self._factor, self._factor, self._factor), about=self._centre
            )
            if self._interact is not None:
                self._interact(self._factor)
            self._plotter.render()
            return
        hovered = self._grip_at_pointer(interactor)
        if hovered != self._hovered:
            self._hovered = hovered
            self._cube.prop.color = HOVER_COLOUR if hovered else self._colour
            self._plotter.render()

    def _on_press(self, interactor: Any, _event: Any) -> None:
        if not self._hovered:
            return
        grip = self._pointer_on_plane(interactor)
        if grip is None or math.dist(self._centre, grip) < 1e-9:
            return
        self._start = grip
        self._factor = 1.0
        # Wie pyvista beim Greifen: der Kamerastil würde den Zug als Drehung
        # der Ansicht lesen. Zurückgestellt wird beim Loslassen — und der
        # Viewport stellt danach sein eigenes Schema wieder her.
        self._plotter.enable_trackball_actor_style()

    def _on_release(self, _interactor: Any, _event: Any) -> None:
        if self._start is None:
            return
        self._start = None
        self._plotter.enable_trackball_style()
        self._release(self._factor)
