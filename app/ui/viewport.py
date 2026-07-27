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

from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.branding import ENVIRONMENT_PREFIX
from app.core.log import get_logger
from app.core.scene import EvaluationResult
from app.core.types import ObjectId, Profile
from app.i18n import tr

_log = get_logger(__name__)

NavigationScheme = Literal["slicer", "cad", "blender"]

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


class Viewport(QWidget):
    """The 3D view, or a plain hint when VTK is not available."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.plotter: Any | None = None
        self._actors: dict[ObjectId, Any] = {}
        self._frame_actors: list[Any] = []
        self._selected: ObjectId | None = None
        self._scheme: NavigationScheme = "slicer"

        if not _available():
            self._layout.addWidget(
                QLabel(tr("Die 3D-Ansicht steht auf diesem Rechner nicht zur Verfügung."), self)
            )
            return

        from pyvistaqt import QtInteractor

        # Typed as Any: pyvista wraps its plotter methods, so annotations do not survive.
        self.plotter = cast(Any, QtInteractor(self))
        self._layout.addWidget(self.plotter.interactor)
        self.plotter.set_background("#20242b", top="#2c323c")
        self.plotter.add_axes()
        self.set_navigation("slicer")

    # --- scene ------------------------------------------------------------------

    def show_scene(self, result: EvaluationResult | None) -> None:
        """Rebuild the view from the last complete evaluation (§15.3)."""
        if self.plotter is None:
            return
        for actor in self._actors.values():
            self.plotter.remove_actor(actor, render=False)
        self._actors.clear()
        if result is None:
            self.plotter.render()
            return

        import numpy as np
        import pyvista as pv

        for object_id, entry in result.scene.objects.items():
            if not entry.visible:
                continue
            raw = getattr(entry.mesh, "raw", None)
            if raw is None:
                continue
            faces = np.hstack(
                [np.full((len(raw.faces), 1), 3, dtype=np.int64), np.asarray(raw.faces)]
            ).ravel()
            surface = pv.PolyData(np.asarray(raw.vertices, dtype=float), faces)
            actor = self.plotter.add_mesh(
                surface,
                color=OBJECT_COLOUR,
                smooth_shading=False,
                backface_params={"color": BACKFACE_COLOUR},
                name=f"object:{object_id}",
                render=False,
            )
            self._actors[object_id] = actor

        self.select(self._selected)
        self.plotter.render()

    def select(self, object_id: ObjectId | None) -> None:
        """Highlight one object — colour plus the status bar, never colour alone (§19.1)."""
        self._selected = object_id
        if self.plotter is None:
            return
        for identifier, actor in self._actors.items():
            actor.prop.color = SELECTED_COLOUR if identifier == object_id else OBJECT_COLOUR
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
                bed, color=BED_COLOUR, style="wireframe", opacity=0.35, name="bed", render=False
            )
        )
        box = pv.Box(bounds=(-width / 2, width / 2, -depth / 2, depth / 2, 0.0, height))
        self._frame_actors.append(
            self.plotter.add_mesh(
                box,
                color=BED_COLOUR,
                style="wireframe",
                opacity=0.5,
                name="build_volume",
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
