"""Die Schnittstelle zwischen der 3D-Ansicht und ihrem Renderer (§18).

Der Viewport beschreibt, **was** im Bild steht — Körper, Kanten, Marken,
Beschriftungen, Kamera, Zeiger —, ein Renderer entscheidet, **wie** es auf den
Schirm kommt. Zwei Renderer stehen dahinter: ``vtk_renderer`` zeichnet mit
VTK direkt (ohne die PyVista-Hülle), ``gfx_renderer`` mit pygfx über wgpu.
Der Viewport kennt nur diese Datei; was hier nicht steht, gibt es für ihn
nicht — und was ein Renderer nicht kann, ist ein Loch in ihm, kein Sonderweg
im Viewport (Entscheidung Robert, 05.09.2026: beide bauen, beide messen).

Drei Festlegungen, die beide Renderer teilen:

* **Bildpunkte zählen wie Qt**: Ursprung oben links, y nach unten, in den
  Gerätepixeln des Widgets. VTK zählt von unten; das rechnet der
  VTK-Renderer an seiner Grenze um, damit der Viewport nicht mehr an
  drei Stellen spiegeln muss.
* **Farben sind Hexwerte** (``#rrggbb``), Deckkraft eine Zahl von 0 bis 1.
  Der Kern liefert Slotfarben als Tripel; :func:`hex_of` bringt sie hierher.
* **Netze kommen als NumPy-Felder**: Ecken ``(n, 3)`` in Millimetern,
  Dreiecke ``(m, 3)`` als Indizes. Kein Renderer-Objekt wandert in den
  Viewport zurück — außer als :class:`Item`, und das ist ein Griff.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Any, Literal

import numpy as np

Vec3 = tuple[float, float, float]
Colour = str
Bounds = tuple[float, float, float, float, float, float]
PointerKind = Literal["press", "release", "move", "wheel", "leave"]
MouseButton = Literal["left", "middle", "right"]


def rgb(colour: Colour) -> tuple[float, float, float]:
    """Ein Hexwert als Tripel von 0 bis 1 — die Form, die jeder Renderer nimmt.

    Nimmt ``#rgb`` und ``#rrggbb``, Groß- wie Kleinschreibung. Alles andere
    ist ein Fehler an der Aufrufstelle, kein Rückfall auf Grau: Eine Farbe,
    die still zu einer anderen wird, ist die Sorte Fehler, die im Bild
    niemand sucht.
    """
    text = colour.strip()
    if not text.startswith("#") or len(text) not in (4, 7):
        raise ValueError(f"keine Hexfarbe: {colour!r}")
    digits = text[1:]
    if len(digits) == 3:
        digits = "".join(part * 2 for part in digits)
    try:
        value = int(digits, 16)
    except ValueError as problem:
        raise ValueError(f"keine Hexfarbe: {colour!r}") from problem
    return (((value >> 16) & 255) / 255.0, ((value >> 8) & 255) / 255.0, (value & 255) / 255.0)


def hex_of(colour: Sequence[float]) -> Colour:
    """Ein Tripel von 0 bis 1 als Hexwert — der Weg vom Kern (§20) hierher."""
    parts = (round(max(0.0, min(1.0, float(part))) * 255) for part in colour[:3])
    return "#" + "".join(f"{part:02x}" for part in parts)


@dataclass(frozen=True)
class SurfaceStyle:
    """Wie eine Fläche gezeichnet wird.

    ``wireframe`` zeichnet nur die Dreieckskanten; ``show_edges`` legt sie
    über die gefüllte Fläche (Modus „Massiv mit Kanten", §18.1).
    ``backface_colour`` färbt die Innenseite eines offenen Netzes anders als
    die Außenseite — der Blick in ein undichtes Teil soll sich unterscheiden.
    ``force_opaque`` hält einen Aktor aus der Mischung transluzenter Flächen
    heraus, ``keep_in_front`` zieht ihn im Tiefenpuffer nach vorn (Maßlinien,
    Fangmarken: eine Marke, die im Material verschwindet, sagt nichts über
    die Stelle, die sie meint).
    """

    colour: Colour = "#b9c4d0"
    opacity: float = 1.0
    wireframe: bool = False
    show_edges: bool = False
    edge_colour: Colour | None = None
    smooth: bool = False
    backface_colour: Colour | None = None
    backface_opacity: float | None = None
    lighting: bool = True
    ambient: float | None = None
    diffuse: float | None = None
    specular: float | None = None
    line_width: float | None = None
    pickable: bool = True
    force_opaque: bool = False
    keep_in_front: bool = False
    cull_backfaces: bool = False


@dataclass(frozen=True)
class CellColours:
    """Eine Farbe je Dreieck — Analysekarte oder Materialslots (§18.4, §20).

    Mit ``colormap`` sind ``values`` Zahlen ``(m,)``, die über ``limits`` auf
    die Farbleiter fallen; ``nan_colour`` bekommt, was keine Zahl ist. Ohne
    ``colormap`` sind ``values`` fertige Farben ``(m, 3)`` von 0 bis 1.
    """

    values: np.ndarray
    colormap: tuple[Colour, ...] | None = None
    limits: tuple[float, float] | None = None
    nan_colour: Colour = "#4a4f57"
    categorical: bool = False


@dataclass(frozen=True)
class LabelStyle:
    """Wie Beschriftungen an Weltpunkten stehen.

    ``always_visible`` zeichnet jede, auch wo sie sich überlappen — die
    Marken einer Frage müssen alle da sein, sonst fehlt eine Antwort.
    ``background`` legt ein Feld hinter den Text (Skizzenmaße
    über dem Körper). ``show_points`` setzt einen Punkt an den Anker.
    """

    text_colour: Colour = "#ffffff"
    font_size: int = 12
    bold: bool = False
    always_visible: bool = True
    background: Colour | None = None
    background_opacity: float = 1.0
    margin: int = 0
    show_points: bool = False
    point_colour: Colour = "#ffffff"
    point_size: int = 8
    pickable: bool = False


@dataclass(frozen=True)
class AxesMarkerStyle:
    """Das Achsenkreuz in der Ecke: Pfeilfarben, Schriftfarbe, Proportionen."""

    x_colour: Colour = "#e0483e"
    y_colour: Colour = "#5cb85c"
    z_colour: Colour = "#3e8ee0"
    label_colour: Colour = "#ffffff"
    shaft_length: float = 0.78
    tip_length: float = 0.28
    cone_radius: float = 0.5
    line_width: float = 3.0
    ambient: float = 0.4


@dataclass(frozen=True)
class CameraPose:
    """Standort, Blickpunkt und Oben der Kamera in Weltkoordinaten."""

    position: Vec3
    focal_point: Vec3
    view_up: Vec3


@dataclass(frozen=True)
class PointerEvent:
    """Eine Zeigergeste im Bild, in Qt-Zählung (Ursprung oben links).

    ``delta`` trägt beim Rad die Rasten (positiv heißt heran). ``button``
    nennt beim Drücken und Loslassen die Taste; beim Bewegen ist es ``None``,
    die gedrückten Tasten stehen in ``buttons``.
    """

    kind: PointerKind
    x: int
    y: int
    button: MouseButton | None = None
    buttons: frozenset[MouseButton] = frozenset()
    shift: bool = False
    ctrl: bool = False
    alt: bool = False
    delta: int = 0


@dataclass(frozen=True)
class Pick:
    """Was unter einem Bildpunkt liegt: der Weltpunkt, der Griff, das Dreieck."""

    point: Vec3
    item: Item
    cell: int


class Item(ABC):
    """Ein Griff auf etwas im Bild — Körper, Linie, Punkt, Beschriftung.

    Der Viewport hält Griffe, um sie zu färben, zu versetzen, auszublenden
    und wieder wegzunehmen. Was dahinter steht (ein ``vtkActor``, ein
    pygfx-``WorldObject``), geht ihn nichts an.
    """

    name: str

    @abstractmethod
    def set_visible(self, visible: bool) -> None: ...

    @abstractmethod
    def visible(self) -> bool: ...

    @abstractmethod
    def set_opacity(self, opacity: float) -> None: ...

    @abstractmethod
    def opacity(self) -> float: ...

    @abstractmethod
    def set_colour(self, colour: Colour) -> None: ...

    @abstractmethod
    def colour(self) -> Colour: ...

    @abstractmethod
    def set_position(self, position: Vec3) -> None:
        """Ein Versatz gegenüber der Geometrie — die Zugvorschau (§18.11)."""

    @abstractmethod
    def position(self) -> Vec3: ...

    @abstractmethod
    def set_matrix(self, matrix: np.ndarray) -> None:
        """Eine ganze Transformation (4 mal 4) vor der Geometrie — der Griff."""

    @abstractmethod
    def matrix(self) -> np.ndarray: ...

    @abstractmethod
    def bounds(self) -> Bounds:
        """Der Hüllquader im Bild, mit Versatz und Matrix."""

    def centre(self) -> Vec3:
        low_x, high_x, low_y, high_y, low_z, high_z = self.bounds()
        return ((low_x + high_x) / 2.0, (low_y + high_y) / 2.0, (low_z + high_z) / 2.0)

    def length(self) -> float:
        low_x, high_x, low_y, high_y, low_z, high_z = self.bounds()
        return float(np.linalg.norm([high_x - low_x, high_y - low_y, high_z - low_z]))

    @abstractmethod
    def set_pickable(self, pickable: bool) -> None: ...

    @abstractmethod
    def update_points(self, points: np.ndarray) -> None:
        """Dieselbe Topologie, andere Ecken — die Vorschau beim Formen (§18.11)."""

    @abstractmethod
    def set_line_width(self, width: float) -> None: ...


class LabelsItem(Item):
    """Beschriftungen, deren Anker und Texte sich gemeinsam austauschen lassen."""

    @abstractmethod
    def update_labels(self, points: np.ndarray, texts: Sequence[str]) -> None: ...


class Renderer(ABC):
    """Der Vertrag, den beide Renderer einlösen.

    ``widget`` ist das Qt-Widget, das in den Viewport kommt — ``None`` bei
    einem Renderer ohne Fenster (Bildaufnahmen für den Agenten, Tests).
    Jeder Aufruf, der etwas ins Bild stellt, zeichnet **nicht**; gezeichnet
    wird einmal über :meth:`render`, an der einen Stelle im Viewport.
    """

    widget: Any

    # --- Inhalt -------------------------------------------------------------------

    @abstractmethod
    def add_surface(
        self,
        vertices: np.ndarray,
        faces: np.ndarray,
        *,
        name: str,
        style: SurfaceStyle,
        cell_colours: CellColours | None = None,
    ) -> Item: ...

    @abstractmethod
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
        """Linien: je zwei Punkte ein Stück, mit ``connected`` eine Kette,
        mit ``polylines`` mehrere Ketten dieser Längen hintereinander."""

    @abstractmethod
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
        """Punkte als Kugeln fester Bildgröße."""

    @abstractmethod
    def add_labels(
        self, points: np.ndarray, texts: Sequence[str], *, name: str, style: LabelStyle
    ) -> LabelsItem: ...

    @abstractmethod
    def remove(self, item: Item) -> None: ...

    @abstractmethod
    def set_draw_order(self, items: Sequence[Item]) -> None:
        """Transluzente Flächen von hinten nach vorn — der Maleralgorithmus
        auf Objektebene (§18, ``_order_by_depth``)."""

    # --- Kamera -------------------------------------------------------------------

    @abstractmethod
    def camera_pose(self) -> CameraPose: ...

    @abstractmethod
    def set_camera_pose(self, pose: CameraPose) -> None: ...

    @abstractmethod
    def parallel_projection(self) -> bool: ...

    @abstractmethod
    def set_parallel_projection(self, parallel: bool) -> None: ...

    @abstractmethod
    def parallel_scale(self) -> float: ...

    @abstractmethod
    def set_parallel_scale(self, scale: float) -> None: ...

    @abstractmethod
    def view_angle(self) -> float:
        """Der senkrechte Öffnungswinkel in Grad (perspektivisch)."""

    @abstractmethod
    def dolly(self, factor: float) -> None:
        """Heran (``factor`` > 1) oder weg — in beiden Projektionen."""

    @abstractmethod
    def reset_camera(self, bounds: Bounds | None = None) -> None:
        """Alles ins Bild — oder genau diesen Quader."""

    @abstractmethod
    def reset_clipping_range(self) -> None: ...

    @abstractmethod
    def view_size(self) -> tuple[int, int]:
        """Breite und Höhe des Bildes in Gerätepixeln."""

    @abstractmethod
    def world_to_display(self, point: Vec3) -> tuple[float, float, float]:
        """Bildpunkt (Qt-Zählung) und Tiefe (0 nah, 1 fern) eines Weltpunkts."""

    @abstractmethod
    def display_to_world(self, x: float, y: float, depth: float) -> Vec3 | None:
        """Der Weltpunkt hinter einem Bildpunkt in dieser Tiefe."""

    def focal_depth(self) -> float:
        """Die Tiefe der Fokusebene — dort spannt ein Zoom das Bild auf."""
        return float(self.world_to_display(self.camera_pose().focal_point)[2])

    # --- Auswahl ------------------------------------------------------------------

    @abstractmethod
    def pick_surface(
        self,
        x: float,
        y: float,
        *,
        among: Sequence[Item] | None = None,
        tolerance: float = 0.005,
    ) -> Pick | None:
        """Das Dreieck unter einem Bildpunkt — nur unter ``among``, wenn gesetzt."""

    @abstractmethod
    def pick_item(self, x: float, y: float) -> Item | None:
        """Was auch immer unter einem Bildpunkt liegt, auch Linien und Punkte."""

    # --- Bild ---------------------------------------------------------------------

    @abstractmethod
    def render(self) -> None: ...

    @abstractmethod
    def screenshot(self) -> np.ndarray:
        """Das Bild als ``(h, w, 3)`` uint8."""

    @abstractmethod
    def set_background(self, colour: Colour, top: Colour | None = None) -> None:
        """Eine Farbe — oder ein Verlauf von ``colour`` unten nach ``top`` oben."""

    @abstractmethod
    def background(self) -> Colour: ...

    @abstractmethod
    def set_headlight(self, intensity: float) -> None:
        """Das Frontlicht, das mit der Kamera wandert — je Thema anders hell."""

    @abstractmethod
    def set_anti_aliasing(self, enabled: bool) -> None: ...

    @abstractmethod
    def set_ambient_occlusion(self, enabled: bool, *, radius: float, bias: float) -> None: ...

    @abstractmethod
    def set_axes_marker(self, style: AxesMarkerStyle | None) -> None: ...

    @abstractmethod
    def place_axes_marker(self, corner: tuple[float, float, float, float]) -> None:
        """Wo das Achsenkreuz sitzt, in Anteilen des Bildes (links, unten, rechts, oben)."""

    # --- Zeiger -------------------------------------------------------------------

    @abstractmethod
    def add_pointer_listener(self, listener: Callable[[PointerEvent], None]) -> int: ...

    @abstractmethod
    def remove_pointer_listener(self, token: int) -> None: ...

    @abstractmethod
    def close(self) -> None:
        """Den nativen Renderer vor seinem Qt-Elternfenster abbauen."""
