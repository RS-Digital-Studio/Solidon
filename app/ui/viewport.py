"""The viewport (Bauplan §18, §2.9).

Not a display window but the inspection tool: build plate and build volume at
real size, back faces coloured so inverted normals stand out, and three
navigation schemes so nobody has to unlearn their slicer.

The 3D view needs VTK. If that cannot start on a machine, the window still opens
and says so — everything except the view keeps working.
"""

from __future__ import annotations

import os
from typing import Any, Literal, cast

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.branding import ENVIRONMENT_PREFIX
from app.core.geom.measure import Measurement, MeasurementList, distance, snap, wall_thickness
from app.core.geom.section import SectionPlane, cut
from app.core.log import get_logger
from app.core.scene import EvaluationResult
from app.core.types import ObjectId, Profile, Vec3
from app.i18n import tr
from app.ui.theme import viewport_colours

_log = get_logger(__name__)

NavigationScheme = Literal["slicer", "cad", "blender"]

DisplayMode = Literal["solid", "solid_edges", "wireframe", "transparent"]
"""How a body is drawn (§18.1)."""

Shading = Literal["flat", "smooth"]
Projection = Literal["perspective", "orthographic"]
"""Orthographic is mandatory for measuring (§18.1)."""

#: Display modes as pyvista arguments: style, edges, opacity.
DISPLAY_MODES: dict[DisplayMode, dict[str, Any]] = {
    "solid": {"style": "surface", "show_edges": False, "opacity": 1.0},
    "solid_edges": {"style": "surface", "show_edges": True, "opacity": 1.0},
    "wireframe": {"style": "wireframe", "show_edges": False, "opacity": 1.0},
    "transparent": {"style": "surface", "show_edges": False, "opacity": 0.45},
}

#: Camera presets (§18.1). Position direction and up vector.
VIEW_DIRECTIONS: dict[str, tuple[tuple[float, float, float], tuple[float, float, float]]] = {
    "front": ((0.0, -1.0, 0.0), (0.0, 0.0, 1.0)),
    "back": ((0.0, 1.0, 0.0), (0.0, 0.0, 1.0)),
    "left": ((-1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
    "right": ((1.0, 0.0, 0.0), (0.0, 0.0, 1.0)),
    "top": ((0.0, 0.0, 1.0), (0.0, 1.0, 0.0)),
    "bottom": ((0.0, 0.0, -1.0), (0.0, 1.0, 0.0)),
    "iso": ((1.0, -1.0, 0.8), (0.0, 0.0, 1.0)),
}

OBJECT_COLOUR = "#b9c4d0"
SELECTED_COLOUR = "#f0a54a"
BACKFACE_COLOUR = "#8b3a3a"
BED_COLOUR = "#5a6472"


#: Switch for machines and test runs without a usable OpenGL context.
HEADLESS_VARIABLE = f"{ENVIRONMENT_PREFIX}_NO_VIEWPORT"


def _available() -> bool:
    """Whether a 3D view can be built here.

    VTK needs a real OpenGL context; on the offscreen Qt platform it would not
    fail politely but take the process with it. So the check happens before,
    not in an except branch.
    """
    if os.environ.get(HEADLESS_VARIABLE):
        return False
    if os.environ.get("QT_QPA_PLATFORM") in ("offscreen", "minimal", "vnc"):
        return False
    try:
        import pyvista  # noqa: F401
        import pyvistaqt  # noqa: F401
    except Exception:  # pragma: no cover - depends on the machine
        return False
    return True


MeasureMode = Literal["off", "distance", "thickness"]

MEASURE_COLOUR = "#f0a54a"


class Viewport(QWidget):
    """The 3D view, or a plain hint when VTK is not available."""

    measurementTaken = Signal(object)
    """A finished measurement — carries a ``Measurement``."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.plotter: Any | None = None
        self._actors: dict[ObjectId, Any] = {}
        self._frame_actors: list[Any] = []
        self._selected: ObjectId | None = None
        self._scheme: NavigationScheme = "slicer"
        self._mode: DisplayMode = "solid"
        self._shading: Shading = "flat"
        self._projection: Projection = "perspective"
        self._section: SectionPlane | None = None
        self._slice_thickness: float | None = None
        self._result: EvaluationResult | None = None
        self._uncapped = False
        """True when a cut could not be closed because the body is open (§18.2)."""
        self._object_colour = OBJECT_COLOUR
        self._bed_colour = BED_COLOUR
        self._measure_mode: MeasureMode = "off"
        self._pending_point: Vec3 | None = None
        self.measurements = MeasurementList()
        self._measure_actors: list[Any] = []

        if not _available():
            self._layout.addWidget(
                QLabel(tr("Die 3D-Ansicht steht auf diesem Rechner nicht zur Verfügung."), self)
            )
            return

        from pyvistaqt import QtInteractor

        # Typed as Any: pyvista wraps its plotter methods, so annotations do not survive.
        self.plotter = cast(Any, QtInteractor(self))
        self._layout.addWidget(self.plotter.interactor)
        self.plotter.add_axes()
        self.set_theme("dark")
        self.set_navigation("slicer")

    # --- scene ------------------------------------------------------------------

    def show_scene(self, result: EvaluationResult | None) -> None:
        """Rebuild the view from the last complete evaluation (§15.3)."""
        self._result = result
        if self.plotter is None:
            return
        for actor in self._actors.values():
            self.plotter.remove_actor(actor, render=False)
        self._actors.clear()
        self._uncapped = False
        if result is None:
            self.plotter.render()
            return

        import numpy as np
        import pyvista as pv

        style = DISPLAY_MODES[self._mode]
        for object_id, entry in result.scene.objects.items():
            if not entry.visible:
                continue
            mesh = self._sectioned(entry.mesh)
            raw = getattr(mesh, "raw", None)
            if raw is None or not len(raw.faces):
                continue
            faces = np.hstack(
                [np.full((len(raw.faces), 1), 3, dtype=np.int64), np.asarray(raw.faces)]
            ).ravel()
            surface = pv.PolyData(np.asarray(raw.vertices, dtype=float), faces)
            actor = self.plotter.add_mesh(
                surface,
                color=self._object_colour,
                smooth_shading=self._shading == "smooth",
                backface_params={"color": BACKFACE_COLOUR},
                name=f"object:{object_id}",
                render=False,
                **style,
            )
            self._actors[object_id] = actor

        self.select(self._selected)
        self.plotter.render()

    def _sectioned(self, mesh: Any) -> Any:
        """Apply the section plane. Cutting is geometry, so the core does it (§18.2)."""
        if self._section is None:
            return mesh
        second = None
        if self._slice_thickness is not None:
            offset = self._section.position - self._slice_thickness
            second = SectionPlane(normal=self._section.normal, position=offset).flipped()
        result = cut(mesh, self._section, second)
        self._uncapped = self._uncapped or not result.capped
        return result.mesh

    def select(self, object_id: ObjectId | None) -> None:
        """Highlight one object — colour plus the status bar, never colour alone (§19.1)."""
        self._selected = object_id
        if self.plotter is None:
            return
        for identifier, actor in self._actors.items():
            actor.prop.color = SELECTED_COLOUR if identifier == object_id else self._object_colour
        self.plotter.render()

    def show_build_volume(self, profile: Profile) -> None:
        """Bed as a grid at real size, build volume as a transparent box (§18.6)."""
        if self.plotter is None:
            return
        import pyvista as pv

        for actor in self._frame_actors:
            self.plotter.remove_actor(actor, render=False)
        self._frame_actors.clear()

        width, depth, height = profile.printer.build_volume
        bed = pv.Plane(
            center=(0.0, 0.0, 0.0),
            direction=(0.0, 0.0, 1.0),
            i_size=width,
            j_size=depth,
            i_resolution=max(1, int(width // 10)),
            j_resolution=max(1, int(depth // 10)),
        )
        self._frame_actors.append(
            self.plotter.add_mesh(
                bed,
                color=self._bed_colour,
                style="wireframe",
                opacity=0.35,
                name="bed",
                render=False,
            )
        )
        box = pv.Box(bounds=(-width / 2, width / 2, -depth / 2, depth / 2, 0.0, height))
        self._frame_actors.append(
            self.plotter.add_mesh(
                box,
                color=self._bed_colour,
                style="wireframe",
                opacity=0.5,
                name="build_volume",
                render=False,
            )
        )
        self.plotter.render()

    # --- theme (§19.3) ----------------------------------------------------------

    def set_theme(self, theme: str) -> None:
        """Background, body and bed colours follow the application theme."""
        colours = viewport_colours(theme)  # type: ignore[arg-type]
        self._object_colour = colours["object"]
        self._bed_colour = colours["bed"]
        if self.plotter is None:
            return
        self.plotter.set_background(colours["bottom"], top=colours["top"])
        self.show_scene(self._result)

    # --- display (§18.1) --------------------------------------------------------

    def set_display_mode(self, mode: DisplayMode) -> None:
        """Solid, solid with edges, wireframe or transparent."""
        self._mode = mode
        self.show_scene(self._result)

    def set_shading(self, shading: Shading) -> None:
        self._shading = shading
        self.show_scene(self._result)

    def set_projection(self, projection: Projection) -> None:
        """Orthographic is what makes measured lengths trustworthy (§18.1)."""
        self._projection = projection
        if self.plotter is None:
            return
        if projection == "orthographic":
            self.plotter.enable_parallel_projection()
        else:
            self.plotter.disable_parallel_projection()
        self.plotter.render()

    @property
    def display_mode(self) -> DisplayMode:
        return self._mode

    @property
    def projection(self) -> Projection:
        return self._projection

    # --- section plane (§18.2) --------------------------------------------------

    def set_section(self, plane: SectionPlane | None, thickness: float | None = None) -> None:
        """Cut the view. ``thickness`` turns the cut into a slice."""
        self._section = plane
        self._slice_thickness = thickness
        self.show_scene(self._result)

    @property
    def section(self) -> SectionPlane | None:
        return self._section

    @property
    def section_uncapped(self) -> bool:
        """True when an open body kept the cut face open — reported, not faked."""
        return self._uncapped

    def section_range(self) -> tuple[float, float]:
        """Sensible travel for the section slider: the extent of the scene."""
        if self._result is None or not self._result.scene.objects:
            return (-100.0, 100.0)
        lows: list[float] = []
        highs: list[float] = []
        for entry in self._result.scene.objects.values():
            bounds = entry.mesh.bounds
            lows.append(min(bounds.minimum))
            highs.append(max(bounds.maximum))
        return (min(lows), max(highs))

    # --- measuring (§18.3) ------------------------------------------------------

    def set_measure_mode(self, mode: MeasureMode) -> None:
        """Point to point, wall thickness, or off. Clicks snap before they count."""
        self._measure_mode = mode
        self._pending_point = None
        if self.plotter is None:
            return
        if mode == "off":
            self.plotter.disable_picking()
            return
        self.plotter.enable_point_picking(
            callback=self._on_picked,
            show_message=False,
            show_point=False,
            left_clicking=True,
            picker="point",
        )

    @property
    def measure_mode(self) -> MeasureMode:
        return self._measure_mode

    def clear_measurements(self) -> None:
        """Dimensions stay until they are deleted — this is the deleting (§18.3)."""
        self.measurements.clear()
        self._pending_point = None
        self._redraw_measurements()

    def _on_picked(self, point: Any) -> None:
        picked = (float(point[0]), float(point[1]), float(point[2]))
        mesh = self._nearest_mesh(picked)
        if mesh is None:
            return
        snapped = snap(mesh, picked)

        if self._measure_mode == "thickness":
            thickness = wall_thickness(mesh, snapped.point)
            if thickness is not None:
                self._add(Measurement(kind="thickness", value=thickness, points=(snapped.point,)))
            return

        if self._pending_point is None:
            self._pending_point = snapped.point
            return
        self._add(
            Measurement(
                kind="distance",
                value=distance(self._pending_point, snapped.point),
                points=(self._pending_point, snapped.point),
            )
        )
        self._pending_point = None

    def _add(self, measurement: Measurement) -> None:
        self.measurements.add(measurement)
        self._redraw_measurements()
        self.measurementTaken.emit(measurement)

    def _nearest_mesh(self, point: Vec3) -> Any:
        """The object a click belongs to — the one whose bounds it is closest to."""
        if self._result is None:
            return None
        best: Any = None
        best_offset = float("inf")
        for entry in self._result.scene.objects.values():
            centre = entry.mesh.bounds.centre
            offset = sum((a - b) ** 2 for a, b in zip(centre, point, strict=True))
            if offset < best_offset:
                best_offset = offset
                best = entry.mesh
        return best

    def _redraw_measurements(self) -> None:
        if self.plotter is None:
            return
        for actor in self._measure_actors:
            self.plotter.remove_actor(actor, render=False)
        self._measure_actors.clear()

        import numpy as np

        for index, entry in enumerate(self.measurements.entries):
            if len(entry.points) == 2:
                line = np.array([entry.points[0], entry.points[1]], dtype=float)
                self._measure_actors.append(
                    self.plotter.add_lines(
                        line, color=MEASURE_COLOUR, width=2, name=f"measure:{index}"
                    )
                )
            label = f"{entry.shown:g} {'mm' if entry.kind != 'angle' else 'grad'}"
            anchor = np.array([entry.points[-1]], dtype=float) if entry.points else None
            if anchor is not None:
                self._measure_actors.append(
                    self.plotter.add_point_labels(
                        anchor,
                        [label],
                        text_color=MEASURE_COLOUR,
                        font_size=12,
                        show_points=True,
                        point_color=MEASURE_COLOUR,
                        point_size=8,
                        name=f"measure_label:{index}",
                        render=False,
                    )
                )
        self.plotter.render()

    def reset_camera(self) -> None:
        if self.plotter is not None:
            self.plotter.reset_camera()

    def view_from(self, direction: str) -> None:
        """One of the seven camera presets (§18.1)."""
        if self.plotter is None or direction not in VIEW_DIRECTIONS:
            return
        position, up = VIEW_DIRECTIONS[direction]
        self.plotter.camera_position = [position, (0.0, 0.0, 0.0), up]
        self.plotter.reset_camera()

    # --- navigation (§2.9) ------------------------------------------------------

    def set_navigation(self, scheme: NavigationScheme) -> None:
        """Slicer habit by default; CAD and Blender as alternatives.

        The default follows what most people already use: left selects, right or
        middle rotates, shift and drag pans, the wheel zooms on the pointer.
        """
        self._scheme = scheme
        if self.plotter is None:
            return
        style = _InteractorStyle(self.plotter, scheme)
        self.plotter.interactor.SetInteractorStyle(style)

    @property
    def navigation(self) -> NavigationScheme:
        return self._scheme


def _InteractorStyle(plotter: Any, scheme: NavigationScheme) -> Any:  # noqa: N802
    """Build a VTK interactor style with the buttons of the chosen scheme."""
    from vtkmodules.vtkInteractionStyle import vtkInteractorStyleTrackballCamera

    base = vtkInteractorStyleTrackballCamera

    class Style(base):  # type: ignore[misc, valid-type]
        def __init__(self) -> None:
            super().__init__()
            self.AddObserver("LeftButtonPressEvent", self._left_down)
            self.AddObserver("LeftButtonReleaseEvent", self._left_up)
            self.AddObserver("RightButtonPressEvent", self._right_down)
            self.AddObserver("RightButtonReleaseEvent", self._right_up)

        def _shift(self) -> bool:
            return bool(self.GetInteractor().GetShiftKey())

        def _left_down(self, *_: Any) -> None:
            if scheme == "slicer":
                # Left selects; panning is shift plus drag.
                if self._shift():
                    self.StartPan()
                return
            if scheme == "blender" and self._shift():
                self.StartPan()
                return
            self.StartRotate()

        def _left_up(self, *_: Any) -> None:
            self.EndPan()
            self.EndRotate()

        def _right_down(self, *_: Any) -> None:
            if scheme == "cad":
                self.StartDolly()
                return
            self.StartRotate()

        def _right_up(self, *_: Any) -> None:
            self.EndRotate()
            self.EndDolly()

    return Style()
