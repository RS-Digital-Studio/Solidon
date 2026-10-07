"""Die Schnittstelle zwischen der 3D-Ansicht und ihrem Renderer (§18).

Der Viewport beschreibt, **was** im Bild steht — Körper, Kanten, Marken,
Beschriftungen, Kamera, Zeiger —, ein Renderer entscheidet, **wie** es auf den
Schirm kommt. Dahinter steht ``gfx_renderer`` (pygfx über wgpu); bis zum
06.09.2026 zeichnete daneben ``vtk_renderer`` mit VTK direkt, und dass beide
denselben Vertrag erfüllten, hat ihn so knapp gemacht, wie er ist.
Der Viewport kennt nur diese Datei; was hier nicht steht, gibt es für ihn
nicht — und was ein Renderer nicht kann, ist ein Loch in ihm, kein Sonderweg
im Viewport (Entscheidung Robert, 05.09.2026: beide bauen, beide messen).

Drei Festlegungen des Renderervertrags:

* **Bildpunkte zählen wie Qt**: Ursprung oben links, y nach unten, in den
  Gerätepixeln des Widgets. pygfx zählt in logischen Bildpunkten; das
  rechnet der Renderer an seiner Grenze um, damit der Viewport nicht an
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
    ``coplanar_overlay`` rückt nur die Rastertiefe einer Flächenmarkierung
    geringfügig zur Kamera. Sie liegt dadurch sichtbar auf derselben Fläche,
    bleibt aber hinter davorliegenden Körpern verborgen. Weltpunkte und
    Pickkoordinaten bleiben unverändert.
    ``draw_order`` ordnet, was ohne Tiefentest vorn gezeichnet wird: Von zwei
    Flächen mit ``keep_in_front`` liegt die mit der kleineren Zahl unten,
    gleich wo ihr Ursprung steht — die Maßtinte (minus eins) unter Griff und Knöpfen
    (0). Mit Tiefentest sagt die Zahl nichts.
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
    coplanar_overlay: bool = False
    draw_order: int = 0


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

    ``delta`` trägt beim Rad auch Bruchteile einer Raste (positiv heißt heran). ``button``
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
    delta: float = 0.0


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
    def set_face_colours_visible(self, visible: bool) -> None:
        """Ob die Farben je Dreieck gelten oder die eine Körperfarbe.

        **Ohne das bleibt ein Körper mit Filament ungefärbt wählbar.** Wer
        Slots hat, bekommt beim Anlegen ``cell_colours``, und damit steht der
        Werkstoff je Dreieck fest; :meth:`set_colour` schreibt dann in eine
        Farbe, die niemand mehr liest. Genau so verschwand die
        Auswahlhervorhebung, sobald einem Teil ein Filament zugewiesen war
        (Befund Robert, 08.09.2026) — im Objektbaum markiert, im Bild grau wie
        alle anderen.

        Ein Aufruf mit ``False`` schaltet auf die Körperfarbe um und macht
        :meth:`set_colour` wieder wirksam; ``True`` gibt die Dreiecksfarben
        zurück. Ein Körper ohne Zellfarben lässt beides unberührt.
        """

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
    def update_points(self, points: np.ndarray) -> None:
        """Dieselbe Topologie, andere Ecken — die Vorschau beim Formen (§18.11).

        Ein Element mit Kapazität (``capacity`` an :meth:`Renderer.add_lines`
        und :meth:`Renderer.add_surface`) nimmt hier **bis zu** so viele
        Punkte, auch weniger als beim Anlegen, und tauscht nur Zahlen in
        seinen Puffern — keine neue Geometrie, keine neue Pipeline. Mehr als
        die Kapazität ist ein Fehler an der Aufrufstelle: Wer mehr braucht,
        legt das Element neu an. Ohne Kapazität muss die Zahl der Punkte die
        des Anlegens sein.
        """


class LabelsItem(Item):
    """Beschriftungen, deren Anker und Texte sich gemeinsam austauschen lassen."""

    @abstractmethod
    def update_labels(self, points: np.ndarray, texts: Sequence[str]) -> None: ...


class Renderer(ABC):
    """Der Vertrag des Renderers.

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
        capacity: int | None = None,
        normals: np.ndarray | None = None,
    ) -> Item:
        """Eine Fläche aus Ecken ``(n, 3)`` und Dreiecken ``(m, 3)``.

        **``normals`` sind vorbereitete Punktnormalen**, gerechnet mit
        :meth:`surface_normals` desselben Renderers — ein Arbeiter kann sie
        abseits des Qt-Hauptthreads rechnen, und der Aufbau übernimmt sie nur
        noch (RM-203). Passt ihre Zahl nicht zu den Ecken, rechnet der
        Renderer selbst; ein falsch beleuchteter Körper wäre der schlechtere
        Fehler als eine verlorene Millisekunde.

        **Mit ``capacity`` hält das Element Platz für so viele Ecken** und
        :meth:`Item.update_points` tauscht danach nur Zahlen, nie die
        Geometrie. ``faces`` beschreibt dann die Topologie bis zur Kapazität;
        gezeichnet werden die vorderen Dreiecke, deren Ecken alle unter der
        gelieferten Punktzahl liegen — die Dreiecke stehen also in der
        Reihenfolge ihrer höchsten Ecke. Ein solches Element ist unbeleuchtet
        (``lighting`` muss aus sein) und ohne Zellfarben: Die Maßtinte, die
        je Kamerageste ihre Pfeile und Marken neu legt (RM-198), braucht
        genau das, und mehr wäre eine Beleuchtung, die niemand nachrechnet.
        """

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
        draw_order: int = 0,
        capacity: int | None = None,
    ) -> Item:
        """Linien: je zwei Punkte ein Stück, mit ``connected`` eine Kette,
        mit ``polylines`` mehrere Ketten dieser Längen hintereinander.
        ``draw_order`` wie bei :class:`SurfaceStyle` — nur vorn, kleinere
        Zahl unten. **Mit ``capacity`` hält das Element Platz für so viele
        Punkte**, und :meth:`Item.update_points` darf danach weniger bringen
        — nur Zahlen wechseln, keine Geometrie (siehe dort). Nicht zusammen
        mit ``polylines``: Deren Trenner sitzen zwischen den Punkten, und
        eine wechselnde Kettenzahl wäre eine neue Topologie."""

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

    def set_interacting(self, active: bool) -> None:
        """Ob gerade gezogen wird — ein Renderer darf dann leichter zeichnen.

        **Eine Zusage an die Bildzeit, nicht an den Inhalt** (RM-200): Was im
        Bild steht, bleibt dasselbe; nur Darstellungsgüte, die in Bewegung
        niemand sieht, darf weichen — beim pygfx-Renderer die Abtastung der
        Umgebungsverdeckung. Die Ansicht schaltet es mit dem Zug ein und vor
        dessen letztem Bild wieder aus. Ohne Umsetzung tut der Aufruf nichts.
        """
        return None

    def warm_glyphs(self, text: str) -> None:
        """Die Schriftzeichen von ``text`` vorab aufbauen, ohne etwas ins Bild zu stellen.

        Für den Leerlauf nach dem Start (``Viewport._warm_the_glyphs``): Ein
        Renderer, der Beschriftungen aus einem Zeichenatlas baut, bezahlt jedes
        Zeichen beim ersten Gebrauch — und der kam mit dem ersten Klick auf
        ein Merkmal. Ohne Umsetzung tut der Aufruf nichts.
        """
        return None

    def frame_was_reduced(self) -> bool:
        """Ob das zuletzt gezeichnete Bild in der leichten Stufe entstand.

        Die Ansicht fragt es am Ende eines Zugs: Ist das stehende Bild noch
        eines aus der Bewegung, zeichnet sie einmal in voller Güte nach — und
        nur dann, denn ein Bild ohne Anlass kostet dieselbe Zeit wie eines mit.
        """
        return False

    @staticmethod
    def surface_normals(vertices: np.ndarray, faces: np.ndarray) -> np.ndarray | None:
        """Die Punktnormalen, die :meth:`add_surface` für diese Fläche rechnen würde.

        **Eine reine Rechnung ohne Renderer-Zustand**, damit ein Arbeiter sie
        nebenläufig stellen kann (``viewport._SceneMeshWorker``): An einem
        Körper mit 200 000 Dreiecken kostet sie 40 ms, und die gehören nicht in
        den Qt-Hauptthread. ``None`` heißt: Dieser Renderer braucht keine, oder
        er rechnet sie lieber selbst.
        """
        return None

    def device_ratio(self) -> float:
        """Gerätepixel je Logikpunkt des Fensters.

        **Der Umrechnungsfaktor für jede Zahl in Bildpunkten.** Zeiger,
        Projektion und Pickpuffer rechnen in Gerätepixeln (:meth:`view_size`,
        :meth:`world_to_display`); die Trefferflächen, Fangweiten und
        Zugschwellen der Oberfläche stehen in **Logikpunkten**, denn das ist
        die Größe, die ein Mensch am Bildschirm sieht. Wer eine solche Zahl mit
        einem Bildpunkt vergleicht, multipliziert sie vorher hiermit.

        Ohne Fenster — offscreen, in Tests, bei Agentenbildern — ist es 1,0
        und keine Umrechnung. Deshalb steht hier eine Vorgabe und kein
        ``abstractmethod``: Ein Renderer ohne Bildschirm hat kein anderes
        Verhältnis zu melden.
        """
        return 1.0

    @abstractmethod
    def world_to_display(self, point: Vec3) -> tuple[float, float, float]:
        """Bildpunkt (Qt-Zählung) und Tiefe (0 nah, 1 fern) eines Weltpunkts."""

    @abstractmethod
    def display_to_world(self, x: float, y: float, depth: float) -> Vec3 | None:
        """Der Weltpunkt hinter einem Bildpunkt in dieser Tiefe.

        **In einer festen Tiefe affin in den Bildkoordinaten**, perspektivisch
        wie orthografisch: Die Tiefenebene liegt parallel zum Bild, und dort
        bildet die Projektion linear ab. Wer viele Bildpunkte in derselben
        Tiefe braucht, holt drei und rechnet den Rest (`_Dimensions.refresh`).
        """

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
        """Was unter einem Gerätebildpunkt liegt, auch Linien und Punkte.

        Die zusätzliche Fangbreite bleibt in logischen Qt-Bildpunkten gleich,
        unabhängig vom Geräteverhältnis des Fensters.
        """

    # --- Bild ---------------------------------------------------------------------

    @abstractmethod
    def render(self) -> None:
        """Das Bild bestellen; am sichtbaren Fenster zeichnet es die nächste Malrunde.

        Einmal je Ereignisrunde und nach den Layouts des Fensters — ein
        sofortiges Bild malte das ganze Fenster mit, auch halb umgebaute
        Nachbarn (``GfxRenderer.render``). Wer das Bild in derselben Runde auf
        dem Schirm braucht, nimmt :meth:`render_now`.
        """

    def render_now(self) -> None:
        """Das Bild sofort zeichnen — für den, der es in derselben Runde braucht.

        Ohne Fenster ist :meth:`render` schon sofort; das gilt dann für beide.
        """
        self.render()

    def hold_frames(self, milliseconds: int) -> None:
        """Bestellte Bilder zurückhalten — bis :meth:`release_frames`, höchstens so lange.

        Für einen Zustandswechsel, dessen Rest gleich aus einem Arbeiter kommt:
        Ein Bild dazwischen zeigte eine halbe Auswahl und kostete den
        Hauptfaden ein ganzes Bild (``GfxRenderer``). Die Frist gehört dem
        Renderer, nicht dem Aufrufer — ein Anhalten, das niemand freigibt,
        endet trotzdem. Ohne Fenster geschieht nichts.
        """
        return None

    def release_frames(self) -> None:
        """Angehaltene Bilder freigeben: Was bestellt war, kommt jetzt als ein Bild."""
        return None

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
    def add_pointer_listener(self, listener: Callable[[PointerEvent], None]) -> None:
        """Ein Zuhörer für jede Zeigergeste, bis der Renderer schließt.

        Abmelden gibt es nicht: Die Ansicht hört zu, solange der Renderer
        lebt, und ``close`` löst alle (RM-316).
        """

    @abstractmethod
    def deliver_pointer(self, kind: str, event: Any) -> None:
        """Ein Qt-Mausereignis zustellen, das neben der Renderfläche ankam.

        Der Viewport fängt Mausereignisse, die nicht auf der Renderfläche
        landen (Randzonen, durchlässige Kinder), rechnet sie in deren
        Koordinaten um und gibt sie hier ab. Der Renderer macht daraus
        dieselbe :class:`PointerEvent` wie aus einem eigenen Ereignis und ruft
        seine Zuhörer; ``kind`` ist ``press``, ``release`` oder ``move``, die
        Taste liest er selbst aus dem Ereignis. Ein Renderer ohne Fenster
        stellt zu, was er kann — die Attrappe der Tests sieht die Geste damit
        wie der echte, statt dass ein Weiterreichen über ``getattr`` still
        ausfiele.
        """

    @abstractmethod
    def close(self) -> None:
        """Den nativen Renderer vor seinem Qt-Elternfenster abbauen."""
