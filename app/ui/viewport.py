"""Der Viewport (Bauplan §18, §2.9).

Kein Anzeigefenster, sondern das Prüfwerkzeug: Druckplatte und Bauraum in
echter Größe, Rückseiten eingefärbt, damit umgedrehte Normalen auffallen, und
drei Navigationsschemata, damit niemand seinen Slicer verlernen muss.

Die 3D-Ansicht braucht VTK. Lässt sich das auf einer Maschine nicht starten,
öffnet das Fenster trotzdem und sagt es — alles außer der Ansicht läuft weiter.
"""

from __future__ import annotations

import os
from typing import Any, Literal, cast

from PySide6.QtCore import Signal
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget

from app.branding import ENVIRONMENT_PREFIX
from app.core.geom.measure import Measurement, MeasurementList, distance, snap, wall_thickness
from app.core.geom.mesh_ops import decimate
from app.core.geom.section import SectionPlane, cut
from app.core.geom.transform import TransformSteps, decompose_transform, snap_to_step
from app.core.log import get_logger
from app.core.perceive.maps import AnalysisMap
from app.core.scene import EvaluationResult
from app.core.types import Feature, FeatureId, LayerInfo, ObjectId, Profile, Vec3
from app.core.units import EPS_GEOM
from app.i18n import tr
from app.ui.labels import feature_label
from app.ui.palette import DIFF_PALETTES, VIRIDIS, DiffPalette
from app.ui.theme import viewport_colours

_log = get_logger(__name__)

NavigationScheme = Literal["slicer", "cad", "blender", "orbit"]
"""``slicer`` folgt §2.9 und damit Cura: links wählt, rechts dreht.
``orbit`` ist die Aufteilung von Bambu Studio, OrcaSlicer und PrusaSlicer —
links dreht, rechts schiebt. Ein viertes Schema, keine andere Vorgabe."""

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


#: Schalter für Maschinen und Testläufe ohne brauchbaren OpenGL-Kontext.
HEADLESS_VARIABLE = f"{ENVIRONMENT_PREFIX}_NO_VIEWPORT"


def _available() -> bool:
    """Ob sich hier eine 3D-Ansicht bauen lässt.

    VTK braucht einen echten OpenGL-Kontext; auf der Offscreen-Qt-Plattform
    scheiterte es nicht höflich, sondern nähme den Prozess mit. Also passiert
    die Prüfung davor und nicht in einem except-Zweig.
    """
    if os.environ.get(HEADLESS_VARIABLE):
        return False
    if os.environ.get("QT_QPA_PLATFORM") in ("offscreen", "minimal", "vnc"):
        return False
    try:
        import pyvista  # noqa: F401
        import pyvistaqt  # noqa: F401
    except Exception:  # pragma: no cover - hängt an der Maschine
        return False
    return True


MeasureMode = Literal["off", "distance", "thickness"]

MEASURE_COLOUR = "#f0a54a"

#: Layer analysis (§18.10): contour, island, unsupported region.
LAYER_COLOUR = "#7fb2e5"
ISLAND_COLOUR = "#e0a33c"
OVERHANG_COLOUR = "#d05a5a"

FEATURE_LABEL_COLOUR = "#cfe3f5"

#: Ab wann für die Anzeige dezimiert wird (§18.9, Schwelle aus §31). Darunter
#: kostet die Vereinfachung mehr, als sie beim Zeichnen einspart.
DISPLAY_DECIMATION_ABOVE = 500_000

#: Worauf. Genug, dass eine Fläche noch eine Fläche ist, wenig genug, dass ein
#: Zug am Schnittschieber nicht durch eine Million Dreiecke geht.
DISPLAY_DECIMATION_TARGET = 200_000


class Viewport(QWidget):
    """Die 3D-Ansicht, oder ein schlichter Hinweis, wenn VTK fehlt."""

    measurementTaken = Signal(object)
    """A finished measurement — carries a ``Measurement``."""
    transformDragged = Signal(object)
    """A finished gizmo drag — carries ``TransformSteps`` (§18.11)."""
    featurePicked = Signal(str)
    paintRequested = Signal(object)
    """A point on the surface to paint at (§20). The window turns it into an
    operation — the view never changes geometry itself."""
    """A feature clicked in the view — carries its id (§18.5)."""

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
        self._gizmo: Any | None = None
        self._grid_step = 1.0
        self._angle_step = 15.0
        self._map: AnalysisMap | None = None
        self._map_object: ObjectId | None = None
        self._feature_overlay = False
        self._feature_actors: list[Any] = []
        self._selected_feature: FeatureId | None = None
        self._layer_actors: list[Any] = []
        self._layer: LayerInfo | None = None
        self._difference: Any | None = None
        self._difference_actors: list[Any] = []
        self._diff_palette: DiffPalette = "blue_orange"
        self._ghost: EvaluationResult | None = None
        self._explosion = 0.0
        """§18.8: how far split parts are drawn apart. Display only, never geometry."""
        self._plate = -1
        """Which build plate is shown; -1 is all of them (§25)."""
        self._painting = False
        """§20: clicks are brush strokes while this is on."""
        self._hidden: frozenset[ObjectId] = frozenset()
        """§18.8: was der Nutzer ausgeblendet hat. Ansicht, nicht Szene — die
        Körper werden weiter gerechnet, geprüft und exportiert."""
        self._display_cache: dict[tuple[ObjectId, int], Any] = {}
        """§18.9: die dezimierte Fassung des zuletzt gezeigten Körpers. Sie
        fließt nie in den Kern zurück."""

        if not _available():
            self._layout.addWidget(
                QLabel(tr("Die 3D-Ansicht steht auf diesem Rechner nicht zur Verfügung."), self)
            )
            return

        from pyvistaqt import QtInteractor

        # Als Any typisiert: pyvista umhüllt seine Plotter-Methoden, Annotationen
        # überleben das nicht.
        self.plotter = cast(Any, QtInteractor(self))
        self._layout.addWidget(self.plotter.interactor)
        self.plotter.add_axes()
        self.set_theme("dark")
        self.set_navigation("slicer")

    # --- scene ------------------------------------------------------------------

    def show_scene(self, result: EvaluationResult | None) -> None:
        """Baut die Ansicht aus der letzten vollständigen Auswertung neu (§15.3)."""
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
            if not entry.visible or object_id in self._hidden:
                continue
            if self._plate >= 0 and entry.plate != self._plate:
                continue
            mesh = self._sectioned(self._for_display(object_id, entry.mesh))
            raw = getattr(mesh, "raw", None)
            if raw is None or not len(raw.faces):
                continue
            faces = np.hstack(
                [np.full((len(raw.faces), 1), 3, dtype=np.int64), np.asarray(raw.faces)]
            ).ravel()
            points = np.asarray(raw.vertices, dtype=float) + self._exploded(entry, result)
            surface = pv.PolyData(points, faces)
            scalars = self._scalars_for(object_id, len(raw.faces))
            extra: dict[str, Any] = {}
            if scalars is not None and self._map is not None:
                surface.cell_data[str(self._map.kind)] = scalars
                extra = {
                    "scalars": str(self._map.kind),
                    "cmap": list(VIRIDIS),
                    "clim": (self._map.low, max(self._map.high, self._map.low + 1e-6)),
                    "show_scalar_bar": False,
                    "nan_color": "#4a4f57",
                }
            actor = self.plotter.add_mesh(
                surface,
                color=self._object_colour,
                smooth_shading=self._shading == "smooth",
                backface_params={"color": BACKFACE_COLOUR},
                name=f"object:{object_id}",
                render=False,
                **style,
                **extra,
            )
            self._actors[object_id] = actor

        self.select(self._selected)
        self._redraw_features()
        self._redraw_layer()
        self.plotter.render()

    def set_hidden(self, hidden: frozenset[ObjectId]) -> None:
        """Welche Körper nicht gezeichnet werden (§18.8).

        Ein Filter auf dem Bild wie die Plattenwahl, keiner auf der Szene: ein
        ausgeblendeter Körper wird weiter gerechnet, steht weiter im
        Prüfbericht und wird weiter exportiert. Alles andere wäre ein Löschen
        mit einem harmlosen Namen.
        """
        if hidden == self._hidden:
            return
        self._hidden = hidden
        self.show_scene(self._result)

    @property
    def hidden(self) -> frozenset[ObjectId]:
        return self._hidden

    def set_plate(self, plate: int) -> None:
        """Zeigt eine Druckplatte, oder alle (§25).

        Ein Filter auf dem Bild, nicht auf der Szene: die Objekte der anderen
        Platten sind weiter da, werden weiter exportiert und stehen weiter im
        Prüfbericht.
        """
        self._plate = plate
        self.show_scene(self._result)

    def set_explosion(self, factor: float) -> None:
        """Zeichnet die Teile auseinander, um eine Teilung anzusehen (§18.8).

        Bewegt wird nichts: der Versatz kommt auf dem Weg in die Ansicht zu den
        Punkten hinzu und erreicht das Netz nie. Ein auseinandergezogenes Teil
        ist immer noch dort, wo der Stapel es sagt, und der Export sagt das
        auch.
        """
        self._explosion = max(0.0, factor)
        self.show_scene(self._result)

    def _exploded(self, entry: Any, result: EvaluationResult) -> Any:
        """Wie weit dieser Körper von seinem Sitz weg gezeichnet wird, von der
        Mitte nach außen.
        """
        import numpy as np

        if self._explosion <= 0.0 or len(result.scene.objects) < 2:
            return np.zeros(3)

        centres = [
            np.asarray(other.mesh.bounds.centre, dtype=float)
            for other in result.scene.objects.values()
            if getattr(other.mesh, "raw", None) is not None
        ]
        if len(centres) < 2:
            return np.zeros(3)

        middle = np.mean(centres, axis=0)
        away = np.asarray(entry.mesh.bounds.centre, dtype=float) - middle
        length = float(np.linalg.norm(away))
        if length <= EPS_GEOM:
            return np.zeros(3)
        return away / length * length * self._explosion

    def _scalars_for(self, object_id: ObjectId, faces: int) -> Any:
        """Kartenwerte für diesen Körper, falls es welche gibt, die noch zu ihm
        passen.
        """
        if self._map is None or self._map_object != object_id:
            return None
        if len(self._map.values) != faces:
            return None
        import numpy as np

        return np.asarray(self._map.values, dtype=float)

    def _for_display(self, object_id: ObjectId, mesh: Any) -> Any:
        """Eine für die Anzeige dezimierte Fassung ab der Schwelle aus §31.

        §18.9 verlangt sie, und es gab sie nicht: der Viewport zeichnete immer
        das volle Netz, und jeder Zug am Schnittschieber schnitt durch eine
        Million Dreiecke. Das Original bleibt unangetastet — was hier entsteht,
        erreicht weder Kern noch Export, sondern nur den Bildschirm.

        Eine Karte bekommt ihre Werte je Dreieck des *Originals*; für sie wird
        deshalb nicht dezimiert, sonst passt die Länge nicht mehr (§18.4).
        """
        if mesh.triangle_count <= DISPLAY_DECIMATION_ABOVE:
            return mesh
        if self._map is not None and self._map_object == object_id:
            return mesh

        key = (object_id, mesh.triangle_count)
        found = self._display_cache.get(key)
        if found is None:
            found = decimate(mesh, DISPLAY_DECIMATION_TARGET)
            # Nur die zuletzt gezeigten behalten: ein dezimiertes Netz ist
            # billig zu bauen und teuer zu halten.
            self._display_cache = {key: found}
        return found

    def _sectioned(self, mesh: Any) -> Any:
        """Wendet die Schnittebene an. Schneiden ist Geometrie, also tut es der
        Kern (§18.2).
        """
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
        """Hebt ein Objekt hervor — Farbe plus Statusleiste, nie Farbe
        allein (§19.1).
        """
        self._selected = object_id
        if self.plotter is None:
            return
        for identifier, actor in self._actors.items():
            if self._map is not None and identifier == self._map_object:
                # Eine Karte besitzt die Farbe ihres Körpers; die Auswahl zeigt sich
                # stattdessen im Objektbaum und in der Statusleiste (§19.1).
                continue
            actor.prop.color = SELECTED_COLOUR if identifier == object_id else self._object_colour
        self.plotter.render()

    def show_build_volume(self, profile: Profile) -> None:
        """Das Bett als Raster in echter Größe, der Bauraum als durchsichtiger
        Kasten (§18.6).
        """
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
        """Hintergrund-, Körper- und Bettfarben folgen dem Anwendungsthema."""
        colours = viewport_colours(theme)  # type: ignore[arg-type]
        self._object_colour = colours["object"]
        self._bed_colour = colours["bed"]
        if self.plotter is None:
            return
        self.plotter.set_background(colours["bottom"], top=colours["top"])
        self.show_scene(self._result)

    # --- display (§18.1) --------------------------------------------------------

    def set_display_mode(self, mode: DisplayMode) -> None:
        """Voll, voll mit Kanten, Drahtgitter oder durchsichtig."""
        self._mode = mode
        self.show_scene(self._result)

    def set_shading(self, shading: Shading) -> None:
        self._shading = shading
        self.show_scene(self._result)

    def set_projection(self, projection: Projection) -> None:
        """Orthografisch ist das, was gemessene Längen vertrauenswürdig
        macht (§18.1).
        """
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
        """Schneidet die Ansicht. ``thickness`` macht aus dem Schnitt eine
        Scheibe.
        """
        self._section = plane
        self._slice_thickness = thickness
        self.show_scene(self._result)

    @property
    def section(self) -> SectionPlane | None:
        return self._section

    @property
    def section_uncapped(self) -> bool:
        """True, wenn ein offener Körper die Schnittfläche offen gelassen hat —
        gemeldet, nicht vorgetäuscht.
        """
        return self._uncapped

    def section_range(self) -> tuple[float, float]:
        """Sinnvoller Weg für den Schnittschieber: die Ausdehnung der Szene."""
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
        """Punkt zu Punkt, Wandstärke, oder aus. Klicks rasten ein, bevor sie
        zählen.
        """
        self._measure_mode = mode
        self._pending_point = None
        if self.plotter is None:
            return
        if mode == "off":
            # Das Messen gibt die Klicks an die Merkmals-Überlagerung zurück, falls
            # sie an ist.
            self.plotter.disable_picking()
            self.set_feature_overlay(self._feature_overlay)
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
        """Maße bleiben, bis sie gelöscht werden — das hier ist das
        Löschen (§18.3).
        """
        self.measurements.clear()
        self._pending_point = None
        self._redraw_measurements()

    def set_painting(self, active: bool) -> None:
        """Macht aus Klicks Pinselstriche (§20).

        Dasselbe Picking, das auch das Messen benutzt; was sich ändert, ist, wer
        den Punkt bekommt. Ein eigener Modus statt einer Zusatztaste: das Modell
        zu bemalen, wenn jemand es drehen wollte, ist die Art Überraschung, die
        ein Undo behebt und Vertrauen nicht übersteht.
        """
        self._painting = active
        if self.plotter is None:
            return
        if not active:
            self.plotter.disable_picking()
            self.set_feature_overlay(self._feature_overlay)
            return
        self.plotter.enable_point_picking(
            callback=self._on_picked,
            show_message=False,
            show_point=False,
            left_clicking=True,
            picker="point",
        )

    def _on_picked(self, point: Any) -> None:
        picked = (float(point[0]), float(point[1]), float(point[2]))
        if self._painting:
            self.paintRequested.emit(picked)
            return
        if self._measure_mode == "off":
            # Nicht am Messen: ein Klick ist für das Merkmal darunter gemeint (§18.5).
            feature_id = self._feature_at(picked)
            if feature_id is not None:
                self.select_feature(feature_id)
                self.featurePicked.emit(feature_id)
            return

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
        """Das Objekt, zu dem ein Klick gehört — das, dessen Hüllquader ihm am
        nächsten ist.
        """
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

    # --- analysis maps (§18.4) --------------------------------------------------

    def set_analysis_map(self, analysis: AnalysisMap | None, object_id: ObjectId | None) -> None:
        """Färbt einen Körper nach den Zahlen einer Karte, oder nimmt die Karte
        weg.
        """
        self._map = analysis
        self._map_object = object_id if analysis is not None else None
        self.show_scene(self._result)

    @property
    def analysis_map(self) -> AnalysisMap | None:
        return self._map

    def fly_to(self, point: Vec3, distance_factor: float = 3.0) -> None:
        """Bewegt die Kamera auf eine Stelle, ohne die Blickrichtung zu
        ändern (§18.4).

        Das Modell mitzudrehen kostete die Orientierung, die der Nutzer sich
        gerade aufgebaut hat; entlang der aktuellen Blickachse näher zu kommen
        behält sie.
        """
        if self.plotter is None:
            return
        import numpy as np

        camera = self.plotter.camera
        position = np.asarray(camera.position, dtype=float)
        focus = np.asarray(camera.focal_point, dtype=float)
        direction = position - focus
        length = float(np.linalg.norm(direction))
        if length <= 1e-9:
            direction = np.array([1.0, -1.0, 0.8])
            length = float(np.linalg.norm(direction))
        reach = max(self._scene_size() / distance_factor, 1.0)
        target = np.asarray(point, dtype=float)
        camera.focal_point = tuple(target)
        camera.position = tuple(target + direction / length * reach)
        self.plotter.render()

    def _scene_size(self) -> float:
        if self._result is None or not self._result.scene.objects:
            return 50.0
        return max(
            float(max(entry.mesh.bounds.size)) for entry in self._result.scene.objects.values()
        )

    # --- feature overlay (§18.5) ------------------------------------------------

    def set_feature_overlay(self, active: bool) -> None:
        """Beschriftungen an den erkannten Merkmalen, und Klicken zum Auswählen.

        §18.5 nennt das die wichtigste Einzelfunktion: der Nutzer muss nicht
        wissen, dass eine Bohrung ``hole_3`` heißt — er zeigt darauf.
        """
        self._feature_overlay = active
        if self.plotter is None:
            return
        if active and self._measure_mode == "off":
            self.plotter.enable_point_picking(
                callback=self._on_picked,
                show_message=False,
                show_point=False,
                left_clicking=True,
                picker="point",
            )
        elif not active and self._measure_mode == "off":
            self.plotter.disable_picking()
        self._redraw_features()
        self.plotter.render()

    def select_feature(self, feature_id: FeatureId | None) -> None:
        self._selected_feature = feature_id
        self._redraw_features()
        if self.plotter is not None:
            self.plotter.render()

    @property
    def selected_feature(self) -> FeatureId | None:
        return self._selected_feature

    def _features_of_selection(self) -> dict[FeatureId, Feature]:
        if self._result is None or self._selected is None:
            return {}
        entry = self._result.scene.objects.get(self._selected)
        return dict(entry.features) if entry is not None else {}

    def _redraw_features(self) -> None:
        if self.plotter is None:
            return
        for actor in self._feature_actors:
            self.plotter.remove_actor(actor, render=False)
        self._feature_actors.clear()
        if not self._feature_overlay:
            return

        import numpy as np

        points: list[list[float]] = []
        labels: list[str] = []
        for feature_id, feature in self._features_of_selection().items():
            centre = feature.params.get("centre")
            if centre is None:
                continue
            points.append([float(value) for value in centre])
            labels.append(feature_label(feature_id, feature))
        if not points:
            return

        self._feature_actors.append(
            self.plotter.add_point_labels(
                np.asarray(points, dtype=float),
                labels,
                text_color=FEATURE_LABEL_COLOUR,
                font_size=11,
                show_points=True,
                point_color=MEASURE_COLOUR,
                point_size=10,
                name="features",
                render=False,
            )
        )

    def _feature_at(self, point: Vec3) -> FeatureId | None:
        """Das Merkmal nächst einem Klick — zeigen schlägt einen Namen
        tippen (§18.5).
        """
        import numpy as np

        target = np.asarray(point, dtype=float)
        best: FeatureId | None = None
        best_offset = float("inf")
        for feature_id, feature in self._features_of_selection().items():
            centre = feature.params.get("centre")
            if centre is None:
                continue
            offset = float(np.linalg.norm(np.asarray(centre, dtype=float) - target))
            if offset < best_offset:
                best_offset = offset
                best = feature_id
        return best

    # --- difference view (§18.7) ------------------------------------------------

    def show_difference(
        self, difference: Any | None, ghost: EvaluationResult | None = None
    ) -> None:
        """Hinzugekommenes und entferntes Volumen, mit dem vorigen Zustand als
        Geist.

        Die Farben kommen aus der Palette (§19.1) und sind nie der einzige
        Träger: hinzugekommen und entfernt unterscheiden sich auch in der
        Transparenz und in der Legende des Chat-Panels — die Ansicht bleibt also
        ohne Farbsehen lesbar.
        """
        self._difference = difference
        self._ghost = ghost
        self._redraw_difference()
        if self.plotter is not None:
            self.plotter.render()

    @property
    def difference(self) -> Any | None:
        return self._difference

    def _redraw_difference(self) -> None:
        if self.plotter is None:
            return
        for actor in self._difference_actors:
            self.plotter.remove_actor(actor, render=False)
        self._difference_actors.clear()
        if self._difference is None:
            return

        colours = DIFF_PALETTES[self._diff_palette]
        for entry in self._difference.entries.values():
            self._add_body(entry.added, colours.added.colour, f"added:{entry.object_id}", 0.85)
            self._add_body(
                entry.removed, colours.removed.colour, f"removed:{entry.object_id}", 0.45
            )

    def _add_body(self, mesh: Any, colour: str, name: str, opacity: float) -> None:
        if self.plotter is None or mesh is None or not len(mesh.raw.faces):
            return
        import numpy as np
        import pyvista as pv

        raw = mesh.raw
        faces = np.hstack(
            [np.full((len(raw.faces), 1), 3, dtype=np.int64), np.asarray(raw.faces)]
        ).ravel()
        surface = pv.PolyData(np.asarray(raw.vertices, dtype=float), faces)
        self._difference_actors.append(
            self.plotter.add_mesh(surface, color=colour, opacity=opacity, name=name, render=False)
        )

    def set_difference_palette(self, palette: DiffPalette) -> None:
        """Blau/Orange, Rot/Grün oder Graustufen — die Wahl aus §19.1."""
        self._diff_palette = palette
        self._redraw_difference()
        if self.plotter is not None:
            self.plotter.render()

    # --- layer analysis (§18.10) ------------------------------------------------

    def set_layer(self, layer: LayerInfo | None) -> None:
        """Zeigt die Konturen einer Schicht. Geometrie, keine
        Werkzeugwege (§18.10).
        """
        self._layer = layer
        self._redraw_layer()
        if self.plotter is not None:
            self.plotter.render()

    def _redraw_layer(self) -> None:
        if self.plotter is None:
            return
        for actor in self._layer_actors:
            self.plotter.remove_actor(actor, render=False)
        self._layer_actors.clear()
        layer = self._layer
        if layer is None:
            return

        for index, polygon in enumerate(layer.contours):
            self._add_ring(polygon.outline, layer.z, LAYER_COLOUR, f"layer:{index}")
            for hole_index, ring in enumerate(polygon.holes):
                self._add_ring(ring, layer.z, LAYER_COLOUR, f"layer:{index}:{hole_index}")
        for index, polygon in enumerate(layer.islands):
            self._add_ring(polygon.outline, layer.z, ISLAND_COLOUR, f"island:{index}", width=3)
        for index, polygon in enumerate(layer.overhangs):
            self._add_ring(polygon.outline, layer.z, OVERHANG_COLOUR, f"overhang:{index}", width=3)

    def _add_ring(self, ring: Any, z: float, colour: str, name: str, width: int = 2) -> None:
        if self.plotter is None or len(ring) < 2:
            return
        import numpy as np

        points = np.array([[float(x), float(y), z] for x, y in ring], dtype=float)
        # add_lines will Punktpaare; ein geschlossener Ring ist jeder Punkt
        # zweimal, bis auf die Enden.
        segments = np.repeat(points, 2, axis=0)[1:-1]
        self._layer_actors.append(
            self.plotter.add_lines(segments, color=colour, width=width, name=name)
        )

    # --- direct manipulation (§18.11) -------------------------------------------

    def set_snapping(self, grid_step: float, angle_step: float) -> None:
        """Raster- und Winkeleinrasten für den Gizmo."""
        self._grid_step = grid_step
        self._angle_step = angle_step

    def set_gizmo(self, active: bool) -> None:
        """Hängt den Gizmo an das gewählte Objekt, oder nimmt ihn weg."""
        if self.plotter is None:
            return
        if self._gizmo is not None:
            self._gizmo.Off()
            self._gizmo = None
        if not active or self._selected is None:
            return
        actor = self._actors.get(self._selected)
        if actor is None:
            return
        self._gizmo = self.plotter.add_affine_transform_widget(
            actor, release_callback=self._on_gizmo_released
        )

    def _on_gizmo_released(self, matrix: Any) -> None:
        """Ein Ziehen endet als Operationen, nicht als Matrix (§18.11, §2.1)."""
        import numpy as np

        steps = decompose_transform(np.asarray(matrix, dtype=float))
        snapped = TransformSteps(
            offset=(
                snap_to_step(steps.offset[0], self._grid_step),
                snap_to_step(steps.offset[1], self._grid_step),
                snap_to_step(steps.offset[2], self._grid_step),
            ),
            axis=steps.axis,
            angle=snap_to_step(steps.angle, self._angle_step),
            scale=steps.scale,
        )
        if snapped.moves or snapped.turns or snapped.resizes:
            self.transformDragged.emit(snapped)

    def reset_camera(self) -> None:
        if self.plotter is not None:
            self.plotter.reset_camera()

    def zoom(self, factor: float) -> None:
        """Näher heran oder weiter weg — ohne Maus (§19.2).

        Die Achsansichten gab es auf der Tastatur, den Zoom nicht: wer ohne
        Zeigegerät arbeitet, kam an ein Modell heran, sah es aber immer aus
        derselben Entfernung.
        """
        if self.plotter is None or factor <= 0.0:
            return
        self.plotter.camera.zoom(factor)
        self.plotter.render()

    def view_from(self, direction: str) -> None:
        """Eine der sieben Kameravorgaben (§18.1)."""
        if self.plotter is None or direction not in VIEW_DIRECTIONS:
            return
        position, up = VIEW_DIRECTIONS[direction]
        self.plotter.camera_position = [position, (0.0, 0.0, 0.0), up]
        self.plotter.reset_camera()

    # --- navigation (§2.9) ------------------------------------------------------

    def set_navigation(self, scheme: NavigationScheme) -> None:
        """Slicer-Gewohnheit als Vorgabe; CAD und Blender als Alternativen.

        Die Vorgabe folgt dem, was die meisten ohnehin benutzen: links wählt,
        rechts oder Mitte dreht, Umschalt und Ziehen schiebt, das Rad zoomt auf
        den Zeiger.
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
    """Baut einen VTK-Interaktionsstil mit den Tasten des gewählten Schemas."""
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
            if scheme == "orbit":
                # Links dreht, rechts schiebt — die Aufteilung von Bambu
                # Studio, OrcaSlicer und PrusaSlicer.
                self.StartPan()
                return
            self.StartRotate()

        def _right_up(self, *_: Any) -> None:
            self.EndRotate()
            self.EndDolly()
            self.EndPan()

    return Style()
