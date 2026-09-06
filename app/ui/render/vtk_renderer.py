"""Der VTK-Renderer — direkt auf VTK, ohne die PyVista-Hülle (§18).

Was PyVista dem Viewport bisher abnahm, steht hier in dem Umfang, den der
Viewport tatsächlich benutzt: Netz nach ``vtkPolyData``, Aktor und Mapper mit
Farbleiter oder Direktfarben, Linien, Punkte, Beschriftungen mit Platzierer,
Kamera, Zell-Picking, Bildaufnahme, FXAA und SSAO, das Achsenkreuz. Die
Qt-Einbettung ist VTKs eigene (``QVTKRenderWindowInteractor``), die Zeiger-
gesten laufen als Qt-Ereignisse hindurch und werden als :class:`PointerEvent`
in Qt-Zählung weitergegeben — VTKs Interaktionsstil bleibt ausgeschaltet,
die Kamera führt der Viewport selbst.

Ohne Fenster (``offscreen=True``) zeichnet derselbe Renderer in einen
Puffer: für die Ansichten des Agenten, das Bild im Fehlerbericht und für
Tests, die Bildpunkte messen statt Attrappen zu befragen.
"""

from __future__ import annotations

import logging
import math
import sys
from collections.abc import Callable, Sequence
from typing import Any

import numpy as np

from app.core.units import EPS_GEOM
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
    hex_of,
    rgb,
)

_log = logging.getLogger(__name__)

#: Wie weit ein Aktor, der vorn bleiben soll, im Tiefenpuffer nach vorn rückt.
#: Derselbe Wert, mit dem der Viewport bisher Maßlinien und Fangmarken aus
#: dem Material holte.
FRONT_OFFSET_UNITS = -66000.0
FRONT_OFFSET_POLYGON_UNITS = -20000.0

#: Wie weit neben einem Aktor der Zeiger ihn noch trifft, in Bildpunkten.
#: VTK misst seine Toleranz als Bruchteil der Fensterdiagonale; dieselbe
#: Zahl wäre am Laptop drei und am großen Schirm neunzehn Bildpunkte.
PICK_SLACK_PIXELS = 4.0

#: Einträge einer interpolierten Farbleiter (Analysekarten).
LOOKUP_ENTRIES = 256


def _render_sequence(*passes: Any) -> Any:
    """Eine VTK-Passfolge hält ihre Unterpässe über native Referenzen."""
    from vtkmodules.vtkRenderingOpenGL2 import vtkRenderPassCollection, vtkSequencePass

    collection = vtkRenderPassCollection()
    for render_pass in passes:
        collection.AddItem(render_pass)
    sequence = vtkSequencePass()
    sequence.SetPasses(collection)
    return sequence


def _polydata(vertices: np.ndarray, faces: np.ndarray | None = None) -> Any:
    """Ein ``vtkPolyData`` aus NumPy-Feldern — Ecken immer, Dreiecke wenn da."""
    from vtkmodules.util.numpy_support import numpy_to_vtk, numpy_to_vtkIdTypeArray
    from vtkmodules.vtkCommonCore import vtkPoints
    from vtkmodules.vtkCommonDataModel import vtkCellArray, vtkPolyData

    points = vtkPoints()
    coordinates = np.ascontiguousarray(np.asarray(vertices, dtype=np.float64).reshape(-1, 3))
    points.SetData(numpy_to_vtk(coordinates, deep=True))  # type: ignore[no-untyped-call]
    data = vtkPolyData()
    data.SetPoints(points)
    if faces is not None and len(faces):
        triangles = np.ascontiguousarray(np.asarray(faces, dtype=np.int64).reshape(-1, 3))
        cells = vtkCellArray()
        offsets = np.arange(0, 3 * len(triangles) + 1, 3, dtype=np.int64)
        cells.SetData(
            numpy_to_vtkIdTypeArray(offsets, deep=True),  # type: ignore[no-untyped-call]
            numpy_to_vtkIdTypeArray(triangles.ravel(), deep=True),  # type: ignore[no-untyped-call]
        )
        data.SetPolys(cells)
    return data


def _line_cells(count: int, connected: bool, polylines: Sequence[int] | None = None) -> Any:
    """Die Linienzellen: je zwei Punkte ein Stück, eine Kette über alle, oder
    mehrere Ketten der Längen ``polylines`` hintereinander."""
    from vtkmodules.util.numpy_support import numpy_to_vtkIdTypeArray
    from vtkmodules.vtkCommonDataModel import vtkCellArray

    cells = vtkCellArray()
    if polylines is not None:
        lengths = [int(length) for length in polylines if int(length) >= 2]
        if sum(lengths) > count:
            raise ValueError(f"{sum(lengths)} Kettenpunkte für {count} Punkte")
        offsets = np.concatenate([[0], np.cumsum(lengths)]).astype(np.int64)
        connectivity = np.arange(int(offsets[-1]), dtype=np.int64)
    elif connected:
        offsets = np.array([0, count], dtype=np.int64)
        connectivity = np.arange(count, dtype=np.int64)
    else:
        pairs = count // 2
        offsets = np.arange(0, 2 * pairs + 1, 2, dtype=np.int64)
        connectivity = np.arange(2 * pairs, dtype=np.int64)
    cells.SetData(
        numpy_to_vtkIdTypeArray(offsets, deep=True),  # type: ignore[no-untyped-call]
        numpy_to_vtkIdTypeArray(connectivity, deep=True),  # type: ignore[no-untyped-call]
    )
    return cells


def _vertex_cells(count: int) -> Any:
    from vtkmodules.util.numpy_support import numpy_to_vtkIdTypeArray
    from vtkmodules.vtkCommonDataModel import vtkCellArray

    cells = vtkCellArray()
    offsets = np.arange(0, count + 1, dtype=np.int64)
    cells.SetData(
        numpy_to_vtkIdTypeArray(offsets, deep=True),  # type: ignore[no-untyped-call]
        numpy_to_vtkIdTypeArray(np.arange(count, dtype=np.int64), deep=True),  # type: ignore[no-untyped-call]
    )
    return cells


def _lookup_table(colours: Sequence[Colour], limits: tuple[float, float], nan: Colour) -> Any:
    """Eine Farbleiter aus Stützfarben — interpoliert über den Wertebereich."""
    from vtkmodules.vtkCommonCore import vtkLookupTable

    table = vtkLookupTable()
    stops = np.asarray([rgb(colour) for colour in colours], dtype=float)
    entries = LOOKUP_ENTRIES if len(stops) > 1 else 1
    table.SetNumberOfTableValues(entries)
    table.SetRange(float(limits[0]), float(limits[1]))
    positions = np.linspace(0.0, 1.0, len(stops))
    for index in range(entries):
        share = index / (entries - 1) if entries > 1 else 0.0
        red, green, blue = (np.interp(share, positions, stops[:, channel]) for channel in range(3))
        table.SetTableValue(index, float(red), float(green), float(blue), 1.0)
    table.SetNanColor(*rgb(nan), 1.0)
    table.Build()
    return table


def _categorical_table(colours: Sequence[Colour], limits: tuple[float, float]) -> Any:
    """Eine Farbe je ganzer Zahl — die Materialslots (§20)."""
    from vtkmodules.vtkCommonCore import vtkLookupTable

    table = vtkLookupTable()
    table.SetNumberOfTableValues(len(colours))
    table.SetRange(float(limits[0]), float(limits[1]))
    for index, colour in enumerate(colours):
        table.SetTableValue(index, *rgb(colour), 1.0)
    table.Build()
    return table


def _matrix_of(matrix: np.ndarray) -> Any:
    from vtkmodules.vtkCommonMath import vtkMatrix4x4

    result = vtkMatrix4x4()
    values = np.asarray(matrix, dtype=float).reshape(4, 4)
    for row in range(4):
        for column in range(4):
            result.SetElement(row, column, float(values[row, column]))
    return result


class VtkItem(Item):
    """Ein Aktor samt Mapper und Daten — der Griff des Viewports auf ihn."""

    def __init__(
        self, name: str, actor: Any, mapper: Any, data: Any, *, in_front: bool = False
    ) -> None:
        self.name = name
        self.actor = actor
        self.mapper = mapper
        self.data = data
        #: Vorn gezeichnet (Polygonversatz) — und deshalb auch vorn gepickt.
        self.in_front = in_front

    def props(self) -> list[Any]:
        """Alle VTK-Props, die zum Griff gehören — für Hinzufügen und Entfernen."""
        return [self.actor]

    def set_visible(self, visible: bool) -> None:
        self.actor.SetVisibility(bool(visible))

    def visible(self) -> bool:
        return bool(self.actor.GetVisibility())

    def set_opacity(self, opacity: float) -> None:
        self.actor.GetProperty().SetOpacity(float(opacity))

    def opacity(self) -> float:
        return float(self.actor.GetProperty().GetOpacity())

    def set_colour(self, colour: Colour) -> None:
        self.actor.GetProperty().SetColor(*rgb(colour))

    def colour(self) -> Colour:
        return hex_of(self.actor.GetProperty().GetColor())

    def set_position(self, position: Vec3) -> None:
        self.actor.SetPosition(float(position[0]), float(position[1]), float(position[2]))

    def position(self) -> Vec3:
        x, y, z = self.actor.GetPosition()
        return (float(x), float(y), float(z))

    def set_matrix(self, matrix: np.ndarray) -> None:
        self.actor.SetUserMatrix(_matrix_of(matrix))

    def matrix(self) -> np.ndarray:
        current = self.actor.GetUserMatrix()
        if current is None:
            return np.eye(4)
        return np.array(
            [[current.GetElement(row, column) for column in range(4)] for row in range(4)],
            dtype=float,
        )

    def bounds(self) -> Bounds:
        low_x, high_x, low_y, high_y, low_z, high_z = self.actor.GetBounds()
        return (
            float(low_x),
            float(high_x),
            float(low_y),
            float(high_y),
            float(low_z),
            float(high_z),
        )

    def set_pickable(self, pickable: bool) -> None:
        self.actor.SetPickable(bool(pickable))

    def update_points(self, points: np.ndarray) -> None:
        from vtkmodules.util.numpy_support import numpy_to_vtk

        coordinates = np.ascontiguousarray(np.asarray(points, dtype=np.float64).reshape(-1, 3))
        if coordinates.shape[0] != self.data.GetNumberOfPoints():
            raise ValueError(
                f"{self.name}: {coordinates.shape[0]} Punkte für {self.data.GetNumberOfPoints()}"
            )
        self.data.GetPoints().SetData(numpy_to_vtk(coordinates, deep=True))  # type: ignore[no-untyped-call]
        self.data.Modified()

    def set_line_width(self, width: float) -> None:
        self.actor.GetProperty().SetLineWidth(float(width))


class VtkLabels(VtkItem, LabelsItem):
    """Beschriftungen mit gemeinsamem Textstil und optional sichtbaren Ankern."""

    def __init__(
        self,
        name: str,
        actor: Any,
        mapper: Any,
        data: Any,
        points_actor: Any | None,
        text_property: Any,
        style: LabelStyle,
        label_data: Any,
    ) -> None:
        super().__init__(name, actor, mapper, data)
        self.points_actor = points_actor
        self.text_property = text_property
        self._shift: Vec3 = (0.0, 0.0, 0.0)
        self._always_visible = style.always_visible
        self._label_data = label_data
        self.background_actor: Any = None
        self._field_data: Any = None
        self._margin = max(0, int(style.margin))
        self._layout_state: Any = None
        self._metric_state: Any = None
        self._text_bounds: list[tuple[int, ...]] = []
        if style.background is not None and style.background_opacity > 0:
            from vtkmodules.vtkRenderingCore import vtkActor2D, vtkPolyDataMapper2D

            self._field_data = _polydata(np.empty((0, 3)))
            field_mapper = vtkPolyDataMapper2D()
            field_mapper.SetInputData(self._field_data)
            field_mapper.ScalarVisibilityOff()
            self.background_actor = vtkActor2D()
            self.background_actor.SetMapper(field_mapper)
            self.background_actor.GetProperty().SetColor(*rgb(style.background))
            self.background_actor.GetProperty().SetOpacity(float(style.background_opacity))
            self.background_actor.SetPickable(bool(style.pickable))

    def props(self) -> list[Any]:
        return (
            ([self.background_actor] if self.background_actor is not None else [])
            + [self.actor]
            + ([self.points_actor] if self.points_actor is not None else [])
        )

    def prepare_labels(self, renderer: Any) -> None:
        """Schrift und Felder teilen echte Textmaße sowie genau denselben sichtbaren Satz."""
        from vtkmodules.util.numpy_support import vtk_to_numpy
        from vtkmodules.vtkCommonDataModel import vtkCellArray
        from vtkmodules.vtkRenderingCore import vtkTextRenderer

        if (
            self.background_actor is None and self._always_visible
        ) or not self.actor.GetVisibility():
            return
        window = renderer.GetRenderWindow()
        state = (
            self.data.GetMTime(),
            self.text_property.GetMTime(),
            window.GetDPI(),
            renderer.GetActiveCamera().GetMTime(),
            renderer.GetSize(),
            renderer.GetOrigin(),
        )
        if state == self._layout_state or min(renderer.GetSize()) <= 0:
            return
        labels = self.data.GetPointData().GetAbstractArray("labels")
        texts = tuple(labels.GetValue(index) for index in range(labels.GetNumberOfValues()))
        metric_state = (texts, self.text_property.GetMTime(), window.GetDPI())
        if metric_state != self._metric_state:
            text_renderer = vtkTextRenderer.GetInstance()
            self._text_bounds = []
            for text in texts:
                measured = [0, 0, 0, 0]
                text_renderer.GetBoundingBox(self.text_property, text, measured, window.GetDPI())
                self._text_bounds.append(tuple(measured))
            self._metric_state = metric_state
        rectangles: list[tuple[int, int, int, int]] = []
        selected: list[int] = []
        origin_x, origin_y = renderer.GetOrigin()
        width, height = renderer.GetSize()
        for index, bounds in enumerate(self._text_bounds):
            if not texts[index]:
                continue
            renderer.SetWorldPoint(*self.data.GetPoint(index), 1.0)
            renderer.WorldToDisplay()
            display = renderer.GetDisplayPoint()
            if not np.isfinite(display).all():
                continue
            x, y = int(display[0]), int(display[1])
            # vtkTextMapper legt die Textur eine Pixelecke vor die Bounds.
            left, right = x + bounds[0] - self._margin - 1, x + bounds[1] + self._margin
            bottom, top = y + bounds[2] - self._margin - 1, y + bounds[3] + self._margin
            if not self._always_visible and (
                not 0 <= display[2] <= 1
                or right < origin_x
                or left >= origin_x + width
                or top < origin_y
                or bottom >= origin_y + height
                or any(
                    left < other_right
                    and right > other_left
                    and bottom < other_top
                    and top > other_bottom
                    for other_left, other_right, other_bottom, other_top in rectangles
                )
            ):
                continue
            selected.append(index)
            rectangles.append((left, right, bottom, top))
        if not self._always_visible:
            points = np.asarray([self.data.GetPoint(index) for index in selected]).reshape(-1, 3)
            if self._label_data.GetNumberOfPoints() != len(selected):
                self._label_data.SetPoints(_polydata(points).GetPoints())
                self._label_data.SetVerts(_vertex_cells(len(selected)))
            else:
                target = vtk_to_numpy(self._label_data.GetPoints().GetData())  # type: ignore[no-untyped-call]
                target[:] = points
                self._label_data.GetPoints().GetData().Modified()
            self._label_data.GetPointData().RemoveArray("labels")
            self._label_data.GetPointData().AddArray(
                _label_array([texts[index] for index in selected])
            )
            self._label_data.Modified()
        if self.background_actor is not None:
            count = len(rectangles)
            if self._field_data.GetNumberOfPoints() != count * 4:
                self._field_data.SetPoints(_polydata(np.zeros((count * 4, 3))).GetPoints())
                cells = vtkCellArray()
                for index in range(count):
                    cells.InsertNextCell(4)
                    for corner in range(4):
                        cells.InsertCellPoint(index * 4 + corner)
                self._field_data.SetPolys(cells)
            positions = vtk_to_numpy(self._field_data.GetPoints().GetData())  # type: ignore[no-untyped-call]
            for index, (left, right, bottom, top) in enumerate(rectangles):
                positions[index * 4 : index * 4 + 4] = (
                    (left, bottom, 0),
                    (right, bottom, 0),
                    (right, top, 0),
                    (left, top, 0),
                )
            self._field_data.GetPoints().GetData().Modified()
            self._field_data.Modified()
        self._layout_state = state

    def set_visible(self, visible: bool) -> None:
        for prop in self.props():
            prop.SetVisibility(bool(visible))

    def set_opacity(self, opacity: float) -> None:
        self.text_property.SetOpacity(float(opacity))

    def opacity(self) -> float:
        return float(self.text_property.GetOpacity())

    def set_colour(self, colour: Colour) -> None:
        self.text_property.SetColor(*rgb(colour))

    def colour(self) -> Colour:
        return hex_of(self.text_property.GetColor())

    def set_position(self, position: Vec3) -> None:
        # Ein 2D-Aktor kennt keinen Weltversatz; verschoben werden die Anker.
        shift = np.asarray(position, dtype=float) - np.asarray(self._shift, dtype=float)
        self._shift = (float(position[0]), float(position[1]), float(position[2]))
        from vtkmodules.util.numpy_support import numpy_to_vtk, vtk_to_numpy

        current = vtk_to_numpy(self.data.GetPoints().GetData())  # type: ignore[no-untyped-call]
        self.data.GetPoints().SetData(
            numpy_to_vtk(np.ascontiguousarray(current + shift), deep=True)  # type: ignore[no-untyped-call]
        )
        self.data.Modified()
        if self.points_actor is not None:
            self.points_actor.SetPosition(*self._shift)

    def position(self) -> Vec3:
        return self._shift

    def bounds(self) -> Bounds:
        low_x, high_x, low_y, high_y, low_z, high_z = self.data.GetBounds()
        return (
            float(low_x),
            float(high_x),
            float(low_y),
            float(high_y),
            float(low_z),
            float(high_z),
        )

    def set_pickable(self, pickable: bool) -> None:
        for prop in self.props():
            prop.SetPickable(bool(pickable))

    def set_line_width(self, width: float) -> None:
        return

    def update_labels(self, points: np.ndarray, texts: Sequence[str]) -> None:
        from vtkmodules.util.numpy_support import numpy_to_vtk

        coordinates = np.ascontiguousarray(np.asarray(points, dtype=np.float64).reshape(-1, 3))
        if coordinates.shape[0] != len(texts):
            raise ValueError(f"{self.name}: {coordinates.shape[0]} Anker für {len(texts)} Texte")
        self.data.GetPoints().SetData(numpy_to_vtk(coordinates, deep=True))  # type: ignore[no-untyped-call]
        self.data.GetPointData().RemoveArray("labels")
        self.data.GetPointData().AddArray(_label_array(texts))
        self.data.SetVerts(_vertex_cells(len(texts)))
        self.data.Modified()


def _label_array(texts: Sequence[str]) -> Any:
    from vtkmodules.vtkCommonCore import vtkStringArray

    labels = vtkStringArray()
    labels.SetName("labels")
    labels.SetNumberOfValues(len(texts))
    for index, text in enumerate(texts):
        labels.SetValue(index, str(text))
    return labels


class VtkRenderer(Renderer):
    """Die VTK-Umsetzung des Vertrags aus :mod:`app.ui.render.api`.

    Mit ``parent`` entsteht ein Qt-Widget (``widget``), ohne — bei
    ``offscreen=True`` — ein Puffer der Größe ``size``. Die Kamera steht nach
    dem Aufbau, wo VTK sie stellt; der Viewport setzt seine eigene Vorgabe.
    """

    def __init__(
        self,
        parent: Any = None,
        *,
        offscreen: bool = False,
        size: tuple[int, int] = (640, 480),
    ) -> None:
        # Die OpenGL-Fabrik meldet sich erst durch den Import an; ohne ihn
        # entsteht ein Renderer ohne Bild.
        import vtkmodules.vtkRenderingOpenGL2  # noqa: F401
        from vtkmodules.vtkInteractionStyle import vtkInteractorStyleTrackballCamera  # noqa: F401
        from vtkmodules.vtkRenderingCore import vtkRenderer

        self._listeners: dict[int, Callable[[PointerEvent], None]] = {}
        self._next_token = 1
        self._items: dict[str, VtkItem] = {}
        self._label_items: set[VtkLabels] = set()
        self._axes: Any = None
        self._axes_widget: Any = None
        self._axes_corner = (0.0, 0.0, 0.2, 0.2)
        self._occlusion_pass: Any = None
        self._occlusion_camera: Any = None
        self._occlusion_sequences: tuple[Any, Any] | None = None
        self._occlusion_bias = 0.0
        self.renderer = vtkRenderer()
        self.widget: Any = None
        self.interactor: Any = None
        self._presentation_configured = offscreen or sys.platform != "win32"
        if offscreen:
            self.window = self._offscreen_window(size)
        else:
            self.widget = self._qt_widget(parent)
            self.window = self.widget.GetRenderWindow()
            self.interactor = self.window.GetInteractor()
        self.window.AddRenderer(self.renderer)
        self._label_observer = self.window.AddObserver("StartEvent", self._prepare_labels)
        self._occlusion_observer = self.window.AddObserver("StartEvent", self._prepare_occlusion)
        self.renderer.SetBackground(0.0, 0.0, 0.0)
        # **Der Lichtsatz, nicht ein Frontlicht.** PyVista stellte einen
        # ``vtkLightKit`` auf — Schlüssellicht 50° über und 10° rechts der
        # Kamera, Fülllicht von unten, zwei Rücklichter, dazu das Frontlicht
        # —, und die Themenwerte des Viewports (``HEADLIGHT``) stellen nur das
        # Frontlicht darin. Mit dem Frontlicht allein war ein Körper im
        # Fenster fast schwarz (Robert, 05.09.2026: „beim ersten war alles
        # schwarz").
        from vtkmodules.vtkRenderingCore import vtkLightKit

        self._light_kit = vtkLightKit()
        self._light_kit.AddLightsToRenderer(self.renderer)

    def _offscreen_window(self, size: tuple[int, int]) -> Any:
        from vtkmodules.vtkRenderingCore import vtkRenderWindow

        window = vtkRenderWindow()
        window.SetOffScreenRendering(True)
        window.SetSize(int(size[0]), int(size[1]))
        return window

    def _qt_widget(self, parent: Any) -> Any:
        from vtkmodules.qt.QVTKRenderWindowInteractor import QVTKRenderWindowInteractor

        renderer = self

        class _Widget(QVTKRenderWindowInteractor):
            """VTKs Qt-Widget, dessen Zeigergesten hier ankommen statt bei VTK."""

            def mousePressEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Name
                renderer._pointer("press", event, _button_of(event.button()))

            def mouseReleaseEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Name
                renderer._pointer("release", event, _button_of(event.button()))

            def mouseMoveEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Name
                renderer._pointer("move", event, None)

            def mouseDoubleClickEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Name
                renderer._pointer("press", event, _button_of(event.button()))

            def wheelEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Name
                steps = round(event.angleDelta().y() / 120.0) if event.angleDelta().y() else 0
                renderer._pointer("wheel", event, None, delta=steps)

            def leaveEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Name
                super().leaveEvent(event)  # type: ignore[no-untyped-call]
                renderer._emit(PointerEvent("leave", 0, 0))

            def keyPressEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Name
                # Tasten gehören Qt (Kurzbefehle, Ereignisfilter des Viewports),
                # nicht VTKs Interactor.
                event.ignore()

            def keyReleaseEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Name
                event.ignore()

        from PySide6.QtCore import Qt

        widget = _Widget(parent)  # type: ignore[no-untyped-call]
        widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        widget.setMouseTracking(True)
        widget.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        interactor = widget.GetRenderWindow().GetInteractor()  # type: ignore[no-untyped-call]
        # Kein Stil: Die Kamera führt der Viewport über den Navigator, und
        # VTKs Trackball soll nicht daneben dieselbe Geste ausführen.
        interactor.SetInteractorStyle(None)
        widget.Initialize()
        return widget

    def _pointer(self, kind: str, event: Any, button: MouseButton | None, delta: int = 0) -> None:
        from PySide6.QtCore import Qt

        ratio = float(self.widget.devicePixelRatioF()) if self.widget is not None else 1.0
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

    # --- Inhalt -------------------------------------------------------------------

    def _register(self, item: VtkItem) -> VtkItem:
        for prop in item.props():
            self.renderer.AddActor(prop) if not _is_2d(prop) else self.renderer.AddViewProp(prop)
            self._items[_key(prop)] = item
        if isinstance(item, VtkLabels):
            self._label_items.add(item)
        return item

    def _prepare_labels(self, _caller: Any, _event: str) -> None:
        """Native Neuzeichnung und Bildaufnahme verwenden dieselben aktuellen Textfelder."""
        for item in self._label_items:
            item.prepare_labels(self.renderer)

    def add_surface(
        self,
        vertices: np.ndarray,
        faces: np.ndarray,
        *,
        name: str,
        style: SurfaceStyle,
        cell_colours: CellColours | None = None,
    ) -> Item:
        from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper

        data = _polydata(vertices, faces)
        if style.smooth:
            data = _with_point_normals(data)
        mapper = vtkPolyDataMapper()
        mapper.SetInputData(data)
        actor = vtkActor()
        actor.SetMapper(mapper)
        prop = actor.GetProperty()
        prop.SetColor(*rgb(style.colour))
        prop.SetOpacity(float(style.opacity))
        if style.wireframe:
            prop.SetRepresentationToWireframe()
        if style.show_edges:
            prop.EdgeVisibilityOn()
            prop.SetEdgeColor(*rgb(style.edge_colour or "#000000"))
        prop.SetInterpolationToPhong() if style.smooth else prop.SetInterpolationToFlat()
        prop.SetLighting(bool(style.lighting))
        if style.ambient is not None:
            prop.SetAmbient(float(style.ambient))
        if style.diffuse is not None:
            prop.SetDiffuse(float(style.diffuse))
        if style.specular is not None:
            prop.SetSpecular(float(style.specular))
        if style.line_width is not None:
            prop.SetLineWidth(float(style.line_width))
        if style.cull_backfaces:
            prop.BackfaceCullingOn()
        if style.backface_colour is not None:
            from vtkmodules.vtkRenderingCore import vtkProperty

            back = vtkProperty()
            back.DeepCopy(prop)
            back.SetColor(*rgb(style.backface_colour))
            if style.backface_opacity is not None:
                back.SetOpacity(float(style.backface_opacity))
            actor.SetBackfaceProperty(back)
        actor.SetPickable(bool(style.pickable))
        actor.SetForceOpaque(bool(style.force_opaque))
        if style.keep_in_front:
            mapper.SetResolveCoincidentTopologyToPolygonOffset()
            mapper.SetRelativeCoincidentTopologyPolygonOffsetParameters(
                0.0, FRONT_OFFSET_POLYGON_UNITS
            )
        if cell_colours is not None:
            _apply_cell_colours(data, mapper, cell_colours)
        else:
            mapper.ScalarVisibilityOff()
        return self._register(
            VtkItem(name, actor, mapper, data, in_front=bool(style.keep_in_front))
        )

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
        from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper

        data = _polydata(points)
        data.SetLines(_line_cells(data.GetNumberOfPoints(), connected, polylines))
        mapper = vtkPolyDataMapper()
        mapper.SetInputData(data)
        mapper.ScalarVisibilityOff()
        if keep_in_front:
            mapper.SetResolveCoincidentTopologyToPolygonOffset()
            mapper.SetRelativeCoincidentTopologyLineOffsetParameters(0.0, FRONT_OFFSET_UNITS)
        actor = vtkActor()
        actor.SetMapper(mapper)
        actor.GetProperty().SetColor(*rgb(colour))
        actor.GetProperty().SetLineWidth(float(width))
        actor.GetProperty().SetLighting(False)
        actor.SetPickable(bool(pickable))
        if keep_in_front:
            actor.SetForceOpaque(True)
        return self._register(VtkItem(name, actor, mapper, data, in_front=bool(keep_in_front)))

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
        from vtkmodules.vtkRenderingCore import vtkActor, vtkPolyDataMapper

        data = _polydata(points)
        data.SetVerts(_vertex_cells(data.GetNumberOfPoints()))
        mapper = vtkPolyDataMapper()
        mapper.SetInputData(data)
        mapper.ScalarVisibilityOff()
        if keep_in_front:
            mapper.SetResolveCoincidentTopologyToPolygonOffset()
            mapper.SetRelativeCoincidentTopologyPointOffsetParameter(FRONT_OFFSET_UNITS)
        actor = vtkActor()
        actor.SetMapper(mapper)
        prop = actor.GetProperty()
        prop.SetColor(*rgb(colour))
        prop.SetPointSize(float(size))
        prop.SetRenderPointsAsSpheres(True)
        prop.SetLighting(False)
        actor.SetPickable(bool(pickable))
        if keep_in_front:
            actor.SetForceOpaque(True)
        return self._register(VtkItem(name, actor, mapper, data, in_front=bool(keep_in_front)))

    def add_labels(
        self, points: np.ndarray, texts: Sequence[str], *, name: str, style: LabelStyle
    ) -> LabelsItem:
        from vtkmodules.vtkRenderingCore import (
            vtkActor,
            vtkActor2D,
            vtkPolyDataMapper,
            vtkTextProperty,
        )
        from vtkmodules.vtkRenderingLabel import vtkLabeledDataMapper

        anchors = np.ascontiguousarray(np.asarray(points, dtype=np.float64).reshape(-1, 3))
        if anchors.shape[0] != len(texts):
            raise ValueError(f"{name}: {anchors.shape[0]} Anker für {len(texts)} Texte")
        data = _polydata(anchors)
        data.SetVerts(_vertex_cells(len(texts)))
        data.GetPointData().AddArray(_label_array(texts))
        text = vtkTextProperty()
        text.SetColor(*rgb(style.text_colour))
        text.SetFontSize(int(style.font_size))
        text.SetBold(bool(style.bold))
        text.SetJustificationToCentered()
        text.SetVerticalJustificationToCentered()
        # Der direkte Mapper zeichnet jeden Eintrag genau einmal. Die
        # optionale Kollision filtert Text und Feld gemeinsam, ohne VTKs
        # doppelt gelieferten ersten Hierarchieeintrag erneut zu mischen.
        if style.always_visible:
            label_data = data
        else:
            label_data = _polydata(anchors)
            label_data.SetVerts(_vertex_cells(len(texts)))
            label_data.GetPointData().AddArray(_label_array(texts))
        mapper = vtkLabeledDataMapper()
        mapper.SetInputData(label_data)
        mapper.SetLabelModeToLabelFieldData()
        mapper.SetFieldDataName("labels")
        mapper.SetLabelTextProperty(text)
        actor = vtkActor2D()
        actor.SetMapper(mapper)
        actor.SetPickable(bool(style.pickable))
        points_actor: Any = None
        if style.show_points:
            point_mapper = vtkPolyDataMapper()
            point_mapper.SetInputData(data)
            point_mapper.ScalarVisibilityOff()
            points_actor = vtkActor()
            points_actor.SetMapper(point_mapper)
            points_actor.GetProperty().SetColor(*rgb(style.point_colour))
            points_actor.GetProperty().SetPointSize(float(style.point_size))
            points_actor.GetProperty().SetRenderPointsAsSpheres(True)
            points_actor.GetProperty().SetLighting(False)
            points_actor.SetPickable(bool(style.pickable))
        item = VtkLabels(name, actor, mapper, data, points_actor, text, style, label_data)
        self._register(item)
        return item

    def remove(self, item: Item) -> None:
        assert isinstance(item, VtkItem)
        if isinstance(item, VtkLabels):
            self._label_items.discard(item)
        for prop in item.props():
            if _is_2d(prop):
                self.renderer.RemoveViewProp(prop)
            else:
                self.renderer.RemoveActor(prop)
            self._items.pop(_key(prop), None)

    def set_draw_order(self, items: Sequence[Item]) -> None:
        for item in items:
            assert isinstance(item, VtkItem)
            for prop in item.props():
                self.renderer.RemoveViewProp(prop)
        for item in items:
            assert isinstance(item, VtkItem)
            for prop in item.props():
                self.renderer.AddViewProp(prop)

    # --- Kamera -------------------------------------------------------------------

    def _camera(self) -> Any:
        return self.renderer.GetActiveCamera()

    def camera_pose(self) -> CameraPose:
        camera = self._camera()
        return CameraPose(
            _vec(camera.GetPosition()), _vec(camera.GetFocalPoint()), _vec(camera.GetViewUp())
        )

    def set_camera_pose(self, pose: CameraPose) -> None:
        camera = self._camera()
        camera.SetPosition(*pose.position)
        camera.SetFocalPoint(*pose.focal_point)
        camera.SetViewUp(*pose.view_up)
        camera.OrthogonalizeViewUp()
        self.renderer.ResetCameraClippingRange()
        # pyvistas Lichtsatz hing an der Kamera; ohne das leuchtet ein Körper
        # nach dem ersten Zug von der falschen Seite.
        self.renderer.UpdateLightsGeometryToFollowCamera()

    def parallel_projection(self) -> bool:
        return bool(self._camera().GetParallelProjection())

    def set_parallel_projection(self, parallel: bool) -> None:
        self._camera().SetParallelProjection(bool(parallel))
        self.renderer.ResetCameraClippingRange()

    def parallel_scale(self) -> float:
        return float(self._camera().GetParallelScale())

    def set_parallel_scale(self, scale: float) -> None:
        self._camera().SetParallelScale(float(scale))

    def view_angle(self) -> float:
        return float(self._camera().GetViewAngle())

    def dolly(self, factor: float) -> None:
        camera = self._camera()
        if camera.GetParallelProjection():
            camera.SetParallelScale(camera.GetParallelScale() / float(factor))
        else:
            camera.Dolly(float(factor))
        self.renderer.ResetCameraClippingRange()
        self.renderer.UpdateLightsGeometryToFollowCamera()

    def reset_camera(self, bounds: Bounds | None = None) -> None:
        if bounds is None:
            self.renderer.ResetCamera()
        else:
            self.renderer.ResetCamera(*(float(value) for value in bounds))
        self.renderer.UpdateLightsGeometryToFollowCamera()

    def reset_clipping_range(self) -> None:
        self.renderer.ResetCameraClippingRange()

    def view_size(self) -> tuple[int, int]:
        width, height = self.window.GetSize()
        return int(width), int(height)

    def world_to_display(self, point: Vec3) -> tuple[float, float, float]:
        self.renderer.SetWorldPoint(float(point[0]), float(point[1]), float(point[2]), 1.0)
        self.renderer.WorldToDisplay()
        x, y, depth = self.renderer.GetDisplayPoint()
        return float(x), float(self._flip(y)), float(depth)

    def display_to_world(self, x: float, y: float, depth: float) -> Vec3 | None:
        self.renderer.SetDisplayPoint(float(x), float(self._flip(y)), float(depth))
        self.renderer.DisplayToWorld()
        world = self.renderer.GetWorldPoint()
        if abs(world[3]) < EPS_GEOM:
            return None
        return (
            float(world[0] / world[3]),
            float(world[1] / world[3]),
            float(world[2] / world[3]),
        )

    def _flip(self, y: float) -> float:
        """Qt zählt von oben, VTK von unten — dieselbe Zeile, andere Richtung."""
        return self.view_size()[1] - 1 - y

    # --- Auswahl ------------------------------------------------------------------

    def pick_surface(
        self,
        x: float,
        y: float,
        *,
        among: Sequence[Item] | None = None,
        tolerance: float = 0.005,
    ) -> Pick | None:
        from vtkmodules.vtkRenderingCore import vtkCellPicker

        picker = vtkCellPicker()
        picker.SetTolerance(float(tolerance))
        if among:
            for candidate in among:
                assert isinstance(candidate, VtkItem)
                picker.AddPickList(candidate.actor)
            picker.PickFromListOn()
        if not picker.Pick(float(x), float(self._flip(y)), 0.0, self.renderer):
            return None
        actor = picker.GetActor()
        item = self._items.get(_key(actor)) if actor is not None else None
        if item is None:
            return None
        return Pick(_vec(picker.GetPickPosition()), item, int(picker.GetCellId()))

    def pick_item(self, x: float, y: float) -> Item | None:
        from vtkmodules.vtkRenderingCore import vtkCellPicker

        # Ein Zell-Picker, kein Hardware-Picker: Die treffen in dieser
        # Umgebung nichts (gemessen am 03.09.2026, `vtk-sagt-ja-und-tut-nichts`).
        #
        # **Und in zwei Stufen, weil der Picker geometrisch rechnet.** Ein
        # Griff mit ``keep_in_front`` steht im Bild vor dem Körper, auch wenn
        # er in dessen Hüllquader liegt — der Skalierwürfel an einem
        # würfelförmigen Teil tut das immer. Der Picker sähe zuerst die
        # Körperfläche davor; was vorn gezeichnet wird, wird deshalb zuerst
        # gefragt (gemessen am 05.09.2026, `tests/test_render_vtk.py`).
        picker = vtkCellPicker()
        width, height = self.view_size()
        picker.SetTolerance(PICK_SLACK_PIXELS / max(math.hypot(width, height), 1.0))
        front = [
            item.actor
            for item in self._items.values()
            if item.in_front and item.actor.GetPickable() and item.actor.GetVisibility()
        ]
        for candidates in (front, None):
            picker.InitializePickList()
            if candidates is not None:
                if not candidates:
                    continue
                for actor in candidates:
                    picker.AddPickList(actor)
                picker.PickFromListOn()
            else:
                picker.PickFromListOff()
            if not picker.Pick(float(x), float(self._flip(y)), 0.0, self.renderer):
                continue
            actor = picker.GetActor()
            found = self._items.get(_key(actor)) if actor is not None else None
            if found is not None:
                return found
        return None

    # --- Bild ---------------------------------------------------------------------

    def render(self) -> None:
        self.window.Render()
        if (
            not self._presentation_configured
            and self.widget is not None
            and self.widget.isVisible()
        ):
            # Erst das sichtbare Rendern stellt einen gültigen WGL-Kontext
            # sicher. Windows komponiert die Ausgabe bereits; zusätzlich im
            # Qt-Hauptthread auf den nächsten Bildwechsel zu warten bremst
            # Navigation und Zeigerfeedback. Andere Plattformen und reine
            # Bildpuffer behalten ihre Präsentationseinstellung.
            self._presentation_configured = True
            swap_control = getattr(self.window, "SetSwapControl", None)
            if swap_control is not None:
                self.window.MakeCurrent()
                swap_control(0)

    def screenshot(self) -> np.ndarray:
        from vtkmodules.util.numpy_support import vtk_to_numpy
        from vtkmodules.vtkRenderingCore import vtkWindowToImageFilter

        self.window.Render()
        grab = vtkWindowToImageFilter()
        grab.SetInput(self.window)
        grab.SetInputBufferTypeToRGB()
        grab.ReadFrontBufferOff()
        grab.Update()
        image = grab.GetOutput()
        width, height, _depth = image.GetDimensions()
        raw = vtk_to_numpy(image.GetPointData().GetScalars()).reshape(height, width, 3)  # type: ignore[no-untyped-call]
        # VTK legt die erste Zeile unten ab; ein Bild beginnt oben.
        return np.ascontiguousarray(raw[::-1])

    def set_background(self, colour: Colour, top: Colour | None = None) -> None:
        self.renderer.SetBackground(*rgb(colour))
        if top is None:
            self.renderer.GradientBackgroundOff()
            return
        self.renderer.SetBackground2(*rgb(top))
        self.renderer.GradientBackgroundOn()

    def set_headlight(self, intensity: float) -> None:
        # VTK legt sein Frontlicht erst beim ersten Bild an; wer es vorher
        # sucht, findet keines. Also hier anlegen, wenn es fehlt — genau das
        # täte das erste Bild auch.
        lights = self.renderer.GetLights()
        if lights.GetNumberOfItems() == 0:
            self.renderer.CreateLight()
            lights = self.renderer.GetLights()
        lights.InitTraversal()
        light = lights.GetNextItem()
        while light is not None:
            if light.LightTypeIsHeadlight():
                light.SetIntensity(float(intensity))
            light = lights.GetNextItem()

    def background(self) -> Colour:
        return hex_of(self.renderer.GetBackground())

    def set_anti_aliasing(self, enabled: bool) -> None:
        self.renderer.SetUseFXAA(bool(enabled))
        if self._occlusion_sequences is not None:
            self._occlusion_camera.SetDelegatePass(self._occlusion_sequences[bool(enabled)])

    def set_ambient_occlusion(self, enabled: bool, *, radius: float, bias: float) -> None:
        self.renderer.SetUseSSAO(bool(enabled))
        if enabled:
            if self._occlusion_pass is None:
                self._make_occlusion_pass()
            self._occlusion_bias = float(bias)
            self.renderer.SetSSAORadius(float(radius))
            self.renderer.SetSSAOBias(float(bias))
            self.renderer.SetSSAOKernelSize(128)
            self.renderer.SSAOBlurOn()
            self._occlusion_pass.SetRadius(float(radius))
            self.renderer.SetPass(self._occlusion_camera)
        else:
            # Ein eigener Pass hat Vorrang vor UseSSAO; das Flag allein
            # würde die Umgebungsverdeckung einer Analysekarte nicht entfernen.
            self.renderer.SetPass(None)  # type: ignore[arg-type]  # VTK nimmt nullptr an.

    def _make_occlusion_pass(self) -> None:
        """Verlauf, deckende Geometrie, Transparenz und Überlagerungen in VTK-Reihenfolge."""
        from vtkmodules.vtkRenderingOpenGL2 import (
            vtkCameraPass,
            vtkLightsPass,
            vtkOpaquePass,
            vtkOpenGLFXAAPass,
            vtkOrderIndependentTranslucentPass,
            vtkOverlayPass,
            vtkSSAOPass,
            vtkTranslucentPass,
            vtkVolumetricPass,
        )

        # Der eingebaute SSAO-Pfad löscht seinen Farbpuffer nur einfarbig.
        # CameraPass zeichnet den Hintergrundverlauf im selben Puffer.
        opaque = vtkCameraPass()
        opaque.SetDelegatePass(vtkOpaquePass())
        self._occlusion_pass = vtkSSAOPass()
        self._occlusion_pass.SetDelegatePass(opaque)
        self._occlusion_pass.SetKernelSize(128)
        self._occlusion_pass.SetBlur(True)
        translucent = vtkOrderIndependentTranslucentPass()
        translucent.SetTranslucentPass(vtkTranslucentPass())
        geometry = _render_sequence(vtkLightsPass(), self._occlusion_pass, translucent)
        antialias = vtkOpenGLFXAAPass()
        antialias.SetDelegatePass(geometry)
        antialias.SetFXAAOptions(self.renderer.GetFXAAOptions())
        volume, overlay = vtkVolumetricPass(), vtkOverlayPass()
        self._occlusion_sequences = (
            _render_sequence(geometry, volume, overlay),
            _render_sequence(antialias, volume, overlay),
        )
        self._occlusion_camera = vtkCameraPass()
        self._occlusion_camera.SetDelegatePass(
            self._occlusion_sequences[bool(self.renderer.GetUseFXAA())]
        )

    def _prepare_occlusion(self, _caller: Any, _event: str) -> None:
        """Der SSAO-Abstand berücksichtigt die Genauigkeit des Kamerapositionspuffers."""
        if self._occlusion_pass is None or not self.renderer.GetUseSSAO():
            return
        # VTK 9.6 speichert Kamerapositionen fest in RGBA16F. Unterhalb einer
        # binary16-Abstandsstufe wirft bereits eine ebene Platte Schatten auf
        # sich selbst. frexp enthält das führende Bit; binary16 hat 10 weitere
        # Mantissenbits und als kleinste Abstandsstufe 2**-24.
        far = self.renderer.GetActiveCamera().GetClippingRange()[1]
        precision = math.ldexp(1.0, max(-24, math.frexp(far)[1] - 11))
        self._occlusion_pass.SetBias(max(self._occlusion_bias, precision))

    def set_axes_marker(self, style: AxesMarkerStyle | None) -> None:
        if self._axes_widget is not None:
            self._axes_widget.EnabledOff()
            self._axes_widget = None
            self._axes = None
        if style is None or self.interactor is None:
            return
        from vtkmodules.vtkInteractionWidgets import vtkOrientationMarkerWidget
        from vtkmodules.vtkRenderingAnnotation import vtkAxesActor

        axes = vtkAxesActor()
        axes.SetShaftTypeToCylinder()
        axes.SetNormalizedShaftLength(style.shaft_length, style.shaft_length, style.shaft_length)
        axes.SetNormalizedTipLength(style.tip_length, style.tip_length, style.tip_length)
        axes.SetConeRadius(style.cone_radius)
        for shaft, tip, colour in (
            (axes.GetXAxisShaftProperty(), axes.GetXAxisTipProperty(), style.x_colour),
            (axes.GetYAxisShaftProperty(), axes.GetYAxisTipProperty(), style.y_colour),
            (axes.GetZAxisShaftProperty(), axes.GetZAxisTipProperty(), style.z_colour),
        ):
            for prop in (shaft, tip):
                prop.SetColor(*rgb(colour))
                prop.SetAmbient(style.ambient)
                prop.SetLineWidth(style.line_width)
        for caption in (
            axes.GetXAxisCaptionActor2D(),
            axes.GetYAxisCaptionActor2D(),
            axes.GetZAxisCaptionActor2D(),
        ):
            caption.GetCaptionTextProperty().SetColor(*rgb(style.label_colour))
            caption.GetCaptionTextProperty().SetShadow(False)
            caption.GetCaptionTextProperty().SetItalic(False)
        widget = vtkOrientationMarkerWidget()
        widget.SetOrientationMarker(axes)
        widget.SetInteractor(self.interactor)
        widget.SetViewport(*self._axes_corner)
        widget.EnabledOn()
        widget.InteractiveOff()
        self._axes = axes
        self._axes_widget = widget

    def place_axes_marker(self, corner: tuple[float, float, float, float]) -> None:
        self._axes_corner = corner
        if self._axes_widget is not None:
            self._axes_widget.SetViewport(*corner)

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
        self.window.RemoveObserver(self._label_observer)
        self.window.RemoveObserver(self._occlusion_observer)
        self._label_items.clear()
        if self._axes_widget is not None:
            try:
                self._axes_widget.EnabledOff()
            except Exception as problem:  # pragma: no cover - hängt am Treiber
                _log.info("axes marker did not switch off: %s", problem)
            self._axes_widget = None
        try:
            if self._occlusion_sequences is not None:
                # Auch ein nach AO-aus abgehängter Pass besitzt Texturen.
                # Die vollständige Folge besucht außerdem den derzeit eventuell
                # ausgeschalteten FXAA-Pass, solange der Kontext noch lebt.
                self.window.MakeCurrent()
                self._occlusion_sequences[1].ReleaseGraphicsResources(self.window)
                self.renderer.SetPass(None)  # type: ignore[arg-type]  # VTK nimmt nullptr an.
                self._occlusion_sequences = None
                self._occlusion_camera = None
                self._occlusion_pass = None
            if self.interactor is not None:
                self.interactor.TerminateApp()
            self.window.Finalize()
        except Exception as problem:  # pragma: no cover - hängt am Treiber
            _log.warning("the render window could not close: %s", problem)
        if self.widget is not None:
            self.widget.close()


def _with_point_normals(data: Any) -> Any:
    """Punktnormalen für weiche Schattierung — ohne Kantenaufspaltung, sonst
    zerfiele eine Rundung wieder in Facetten."""
    from vtkmodules.vtkFiltersCore import vtkPolyDataNormals

    normals = vtkPolyDataNormals()
    normals.SetInputData(data)
    normals.ComputePointNormalsOn()
    normals.ComputeCellNormalsOff()
    normals.SplittingOff()
    normals.ConsistencyOff()
    normals.Update()
    return normals.GetOutput()


def _apply_cell_colours(data: Any, mapper: Any, colours: CellColours) -> None:
    from vtkmodules.util.numpy_support import numpy_to_vtk

    values = np.asarray(colours.values)
    if colours.colormap is None:
        table = np.ascontiguousarray(np.clip(values.reshape(-1, 3), 0.0, 1.0) * 255.0).astype(
            np.uint8
        )
        array = numpy_to_vtk(table, deep=True)  # type: ignore[no-untyped-call]
        array.SetName("colours")
        data.GetCellData().SetScalars(array)
        mapper.SetColorModeToDirectScalars()
        mapper.SetScalarModeToUseCellData()
        mapper.ScalarVisibilityOn()
        return
    numbers = np.ascontiguousarray(values.reshape(-1).astype(np.float64))
    array = numpy_to_vtk(numbers, deep=True)  # type: ignore[no-untyped-call]
    array.SetName("values")
    data.GetCellData().SetScalars(array)
    limits = colours.limits or (
        float(np.nanmin(numbers)) if len(numbers) else 0.0,
        float(np.nanmax(numbers)) if len(numbers) else 1.0,
    )
    if limits[1] <= limits[0]:
        limits = (limits[0], limits[0] + 1e-6)
    if colours.categorical:
        mapper.SetLookupTable(_categorical_table(colours.colormap, limits))
    else:
        mapper.SetLookupTable(_lookup_table(colours.colormap, limits, colours.nan_colour))
    mapper.SetScalarRange(float(limits[0]), float(limits[1]))
    mapper.SetScalarModeToUseCellData()
    mapper.SetColorModeToMapScalars()
    mapper.ScalarVisibilityOn()


def _button_of(button: Any) -> MouseButton | None:
    from PySide6.QtCore import Qt

    if button == Qt.MouseButton.LeftButton:
        return "left"
    if button == Qt.MouseButton.MiddleButton:
        return "middle"
    if button == Qt.MouseButton.RightButton:
        return "right"
    return None


def _is_2d(prop: Any) -> bool:
    return bool(prop.IsA("vtkActor2D"))


def _key(prop: Any) -> str:
    return str(prop.GetAddressAsString("vtkProp"))


def _vec(values: Sequence[float]) -> Vec3:
    return (float(values[0]), float(values[1]), float(values[2]))
