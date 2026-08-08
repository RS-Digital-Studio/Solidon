"""Der Viewport (Bauplan §18, §2.9).

Kein Anzeigefenster, sondern das Prüfwerkzeug: Druckplatte und Bauraum in
echter Größe, Rückseiten eingefärbt, damit umgedrehte Normalen auffallen, und
drei Navigationsschemata, damit niemand seinen Slicer verlernen muss.

Die 3D-Ansicht braucht VTK. Lässt sich das auf einer Maschine nicht starten,
öffnet das Fenster trotzdem und sagt es — alles außer der Ansicht läuft weiter.
"""

from __future__ import annotations

import os
import weakref
from typing import Any, Literal, cast

from PySide6.QtCore import QEvent, Qt, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QVBoxLayout, QWidget

from app.branding import ENVIRONMENT_PREFIX
from app.core.geom.measure import Measurement, MeasurementList, distance, snap, wall_thickness
from app.core.geom.mesh_ops import decimate
from app.core.geom.section import SectionPlane, cut
from app.core.geom.transform import (
    TransformSteps,
    along_normal,
    decompose_transform,
    snap_to_step,
)
from app.core.log import get_logger
from app.core.perceive.maps import AnalysisMap
from app.core.scene import EvaluationResult
from app.core.types import Feature, FeatureId, LayerInfo, ObjectId, Profile, Vec3
from app.core.units import EPS_DISPLAY, EPS_GEOM, EPS_MATCH_MINIMUM, EPS_MATCH_RELATIVE
from app.i18n import tr
from app.ui.labels import feature_label
from app.ui.palette import DIFF_PALETTES, ROLES, VIRIDIS, DiffPalette
from app.ui.style import ROOMY, TIGHT
from app.ui.theme import THEMES, viewport_colours

_log = get_logger(__name__)

NavigationScheme = Literal["slicer", "cad", "blender", "orbit"]
"""``slicer`` folgt §2.9 und damit Cura: links wählt, rechts dreht.
``orbit`` ist die Aufteilung von Bambu Studio, OrcaSlicer und PrusaSlicer —
links dreht, rechts schiebt. Ein viertes Schema, keine andere Vorgabe."""

DisplayMode = Literal["solid", "solid_edges", "wireframe", "transparent"]
"""How a body is drawn (§18.1)."""

Shading = Literal["flat", "smooth"]
Projection = Literal["perspective", "orthographic"]
"""Zum Messen ist die orthographische Ansicht Pflicht (§18.1)."""

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

#: Reichweite der Umgebungsverdeckung in Weltmaß, also Millimetern.
#:
#: An einer gebohrten Platte mit einer Tasche nachgemessen, gegen dasselbe Bild
#: ohne Verdeckung: 1 mm → 3,77 mittlere Abweichung, 2 mm → 1,75, 4 mm → 1,07,
#: 8 mm → 0,95, 16 mm → 1,93. Der erste Ansatz stand auf 8 und war damit der
#: **schwächste** Wert der Reihe — die Begründung dafür („die Größenordnung, in
#: der Druckteile ihre Merkmale haben") klang plausibel und war falsch: gesucht
#: wird im Umkreis dieses Radius nach verdeckenden Nachbarn, und wer zu weit
#: sucht, mittelt die Kante weg, um die es geht.
#:
#: Genommen ist trotzdem nicht der stärkste Wert. Bei 1 mm zeigen ebene
#: Seitenflächen im Bild waagerechte Streifen — die Selbstverdeckung, vor der
#: :data:`SSAO_BIAS` warnt; die höhere Zahl ist dort größtenteils Rauschen. Zwei
#: Millimeter ist die Größenordnung einer Fase, einer Nutbreite, eines
#: Bohrungsrands, und das Bild bleibt sauber.
SSAO_RADIUS = 2.0

#: Wie weit zwei Tiefen auseinanderliegen müssen, damit eine die andere
#: verdeckt. Zu klein, und eine ebene Fläche verdeckt sich selbst — das ist
#: das Streifenmuster, an dem man schlecht eingestellte Verdeckung erkennt.
SSAO_BIAS = 0.01

#: Ab welchem Winkel zwischen zwei Dreiecken eine Kante als Kante des Körpers
#: gilt. Dreißig Grad lässt die Facetten eines fein aufgelösten Zylinders in
#: Ruhe — die liegen bei zweihundert Segmenten unter zwei Grad — und nimmt
#: jede Fase mit, denn eine Fase unter dreißig Grad ist keine mehr.
FEATURE_EDGE_ANGLE = 30.0

#: Strichstärke der Körperkanten. Bei 1,0 verschwanden sie neben der
#: Umgebungsverdeckung; die Farbe ist je Thema auf Kontrast 4,5 gegen den
#: Körper gerechnet — dieselbe Schwelle, die WCAG für lesbaren Text nennt, und
#: aus demselben Grund: eine Linie, die man suchen muss, hilft niemandem.
FEATURE_EDGE_WIDTH = 1.5

#: Wie weit ein Klick danebengehen darf, als Anteil der Bilddiagonale.
#:
#: VTKs Vorgabe ist ein Tausendstel — bei einem Fenster von 1300 Pixeln also
#: knapp zwei Pixel, und ein Klick auf eine Kante trifft dann wieder nichts.
#: Fünf Tausendstel sind rund acht Pixel: genug, um eine dünne Wand zu
#: erwischen, zu wenig, um die falsche Fläche zu greifen.
PICK_TOLERANCE = 0.005

#: Was eine Bedeutung trägt, kommt aus ``palette.ROLES`` — dort steht die
#: Auswahlfarbe einmal, und der Objektbaum färbt in derselben. Vorher standen
#: hier neun eigene Werte, die kein Thema kannten und keine andere Stelle.
OBJECT_COLOUR = "#b9c4d0"
SELECTED_COLOUR = ROLES["select"]
BACKFACE_COLOUR = ROLES["backface"]
BED_COLOUR = "#5a6472"

#: Der gefüllte Grund der Platte — dunkler als das Raster darauf und heller
#: als der Hintergrund, damit beides sichtbar bleibt.
BED_SURFACE_COLOUR = "#2a303a"

#: Abstand der Maßzahlen an der Platte, in Millimetern. Fünfzig, weil das
#: Raster bei zehn liegt: eine Zahl an jeder Rasterlinie wäre ein Zaun aus
#: Ziffern, und eine alle hundert ließe eine 220er-Platte mit zwei Zahlen
#: zurück.
BED_SCALE_STEP = 50.0

#: Wie weit die Zahlen neben der Plattenkante stehen. Weit genug, dass sie
#: nicht auf einem Teil liegen, das bis an den Rand geht.
BED_SCALE_GAP = 8.0

#: Wie hoch der Kontaktschatten über der Platte liegt. Ohne diesen Abstand
#: streiten sich Schatten und Platte um dieselbe Tiefe, und das Bild flimmert
#: beim Drehen.
SHADOW_LIFT = 0.05

#: Farbe und Deckkraft des Kontaktschattens. Dunkler als die Platte, aber
#: nie schwarz: er soll den Ort zeigen, nicht ein Loch in die Platte
#: schneiden.
SHADOW_COLOUR = "#11151a"
SHADOW_OPACITY = 0.35

#: Wohin das Licht fällt, als waagerechter Anteil je Millimeter Höhe. Nach
#: hinten rechts, weil die Standardansicht von vorn links kommt — so tritt
#: der Schatten hinter dem Teil hervor statt davor, wo er die Sicht auf die
#: Vorderkante nähme.
SHADOW_DIRECTION = (0.35, 0.45)

#: Wie weit der gefüllte Grund unter dem Raster liegt. Nur so viel, dass
#: beide nicht um dieselbe Tiefe streiten.
BED_SURFACE_DROP = 0.2


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


def _hex(colour: tuple[float, float, float]) -> str:
    """Eine Slotfarbe (0 bis 1 je Kanal, §20) als Hexwert für den Plotter."""
    red, green, blue = (round(max(0.0, min(1.0, part)) * 255) for part in colour)
    return f"#{red:02x}{green:02x}{blue:02x}"


MeasureMode = Literal["off", "distance", "thickness"]

MEASURE_COLOUR = ROLES["measure"]

#: Wie weit die Maus zwischen Drücken und Loslassen wandern darf, damit es noch
#: als Klick zählt. In jedem Schema tut die rechte Taste auch etwas an der
#: Kamera; ein Zug meint sie, ein Klick meint das, worauf er zeigt. Zwei Pixel,
#: weil eine Maus beim Drücken selten ganz stillsteht.
CLICK_SLACK = 2


def is_click(start: tuple[int, int] | None, end: tuple[int, int]) -> bool:
    """Ob zwischen Drücken und Loslassen genug stillgestanden wurde.

    Als Funktion und nicht als Methode des Interaktionsstils: das ist eine
    Rechnung über zwei Punkte, und ein Test dafür soll kein VTK-Objekt bauen
    müssen. Ohne Anfang gab es keinen Druck, den dieses Loslassen beendet —
    dann zählt es nicht.
    """
    if start is None:
        return False
    return abs(end[0] - start[0]) <= CLICK_SLACK and abs(end[1] - start[1]) <= CLICK_SLACK


#: Der Griff auf einer Fläche, gemessen an der Diagonale des Objekts, und
#: seine Untergrenze in Millimetern. Mitwachsend, weil ein fester Radius an
#: einem Gehäuse verschwindet und einen Zapfen vollständig verdeckt.
FACE_HANDLE_SHARE = 0.06
FACE_HANDLE_MINIMUM = 2.0

#: Layer analysis (§18.10): contour, island, unsupported region.
LAYER_COLOUR = ROLES["layer"]
ISLAND_COLOUR = ROLES["island"]
OVERHANG_COLOUR = ROLES["overhang"]

FEATURE_LABEL_COLOUR = ROLES["feature"]

#: Ab wann für die Anzeige dezimiert wird (§18.9, Schwelle aus §31). Darunter
#: kostet die Vereinfachung mehr, als sie beim Zeichnen einspart.
DISPLAY_DECIMATION_ABOVE = 500_000

#: Worauf. Genug, dass eine Fläche noch eine Fläche ist, wenig genug, dass ein
#: Zug am Schnittschieber nicht durch eine Million Dreiecke geht.
DISPLAY_DECIMATION_TARGET = 200_000

#: Ab wie vielen Dreiecken ein Körper keine Kantenlinien mehr bekommt.
#:
#: Die Suche läuft linear: rund 0,15 ms je tausend Dreiecke, gemessen an Kugeln
#: von 7 000 bis 350 000 Dreiecken (1,6 · 4,7 · 12,4 · 27,2 · 52,9 ms). Bei
#: dieser Grenze sind es dreißig Millisekunden je Körper und Szenenaufbau —
#: mehr will die Ansicht dafür nicht ausgeben.
#:
#: Dieselbe Zahl wie das Dezimierungsziel, weil es dieselbe Frage ist. Und
#: der Verlust ist gering: Netze dieser Größe sind Scans oder erzeugte Körper,
#: und die haben bei dreißig Grad ohnehin fast keine Kanten — die 350 000er
#: Kugel liefert null.
FEATURE_EDGE_LIMIT = DISPLAY_DECIMATION_TARGET


def shadow_points(points: Any) -> Any:
    """Wohin die Punkte eines Körpers als Schatten fallen (§18.6).

    Jeder Punkt fällt entlang des Lichts auf die Platte: der Versatz ist seine
    Höhe mal der waagerechte Anteil der Lichtrichtung. Punkte unter der Platte
    werfen keinen Schatten nach vorn — ihre Höhe zählt als null, sonst zöge ein
    Teil, das zur Hälfte versunken ist, seinen Schatten in die falsche
    Richtung.

    Als eigene Funktion, damit die Rechnung ohne Plotter prüfbar bleibt.
    """
    import numpy as np

    grid = np.asarray(points, dtype=float)
    height = np.maximum(grid[:, 2], 0.0)
    return np.column_stack(
        (
            grid[:, 0] + height * SHADOW_DIRECTION[0],
            grid[:, 1] + height * SHADOW_DIRECTION[1],
            np.zeros(len(grid)),
        )
    )


def bed_scale(width: float, depth: float) -> list[tuple[tuple[float, float, float], str]]:
    """Die Maßzahlen an der vorderen und linken Plattenkante (§18.6).

    Ein Raster ohne Zahlen sagt nur, dass es ein Raster gibt. Erst die Zahl
    daneben macht daraus einen Maßstab, an dem man ein Teil einordnet, ohne
    zu messen — und das ist der Zweck der Platte in echter Größe.

    Als eigene Funktion und nicht im Zeichnen versteckt: offscreen gibt es
    keinen Plotter, und eine Prüfung, die sich dort überspringt, prüft nie
    etwas.
    """
    marks: list[tuple[tuple[float, float, float], str]] = []
    half_width, half_depth = width / 2.0, depth / 2.0
    step = BED_SCALE_STEP
    position = step
    while position <= half_width + EPS_GEOM:
        for side in (-position, position):
            marks.append(((side, -half_depth - BED_SCALE_GAP, 0.0), f"{abs(side):.0f}"))
        position += step
    position = step
    while position <= half_depth + EPS_GEOM:
        for side in (-position, position):
            marks.append(((-half_width - BED_SCALE_GAP, side, 0.0), f"{abs(side):.0f}"))
        position += step
    # Der Nullpunkt einmal, nicht zweimal — er gehört beiden Kanten.
    marks.append(((-half_width - BED_SCALE_GAP, -half_depth - BED_SCALE_GAP, 0.0), "0"))
    return marks


#: Wie weit die Eckwinkel an der Oberkante des Bauraums in die Kante
#: hineinreichen, als Anteil ihrer Länge.
CORNER_FRACTION = 0.08

#: Länge der Gizmo-Pfeile als Anteil der Körperdiagonale, und die Dicke ihrer
#: Schäfte im selben Maß. pyvistas Vorgaben (0.15 und 0.02) ergaben auf einem
#: 80-mm-Teil ein Gebilde aus dünnen Linien von etwa vierzig Bildpunkten — zu
#: klein, um es mit der Maus zu treffen.
GIZMO_SCALE = 0.3
GIZMO_LINE_RADIUS = 0.035

#: Wie weit hinter der Pfeilspitze die Achsenbeschriftung steht, als Anteil der
#: Pfeillänge.
GIZMO_LABEL_GAP = 1.2


def gizmo_labels(
    origin: tuple[float, float, float], length: float
) -> list[tuple[tuple[float, float, float], str]]:
    """Wo X, Y und Z am Gizmo stehen (Regel 18).

    Die drei Achsen unterschied allein Rot, Grün und Blau — für jeden, der die
    nicht trennt, waren es drei gleiche Pfeile. Ein Buchstabe an der Spitze
    trägt dieselbe Aussage ohne Farbe.
    """
    reach = length * GIZMO_LABEL_GAP
    return [
        ((origin[0] + reach, origin[1], origin[2]), "X"),
        ((origin[0], origin[1] + reach, origin[2]), "Y"),
        ((origin[0], origin[1], origin[2] + reach), "Z"),
    ]


def volume_edges(
    width: float, depth: float, height: float
) -> list[tuple[tuple[float, float, float], tuple[float, float, float]]]:
    """Die Kanten, mit denen der Bauraum angedeutet wird (§18.6).

    **Nicht der ganze Quader.** Als geschlossener Drahtkasten war seine
    Oberkante aus der Vorgabeansicht eine große Raute weit über dem Bett, und
    das 80-mm-Teil darunter ein Fleck — die Kulisse war lauter als das Stück.

    Gebraucht wird zweierlei: wie hoch darf es werden, und wo hört die Fläche
    auf. Das erste tragen vier senkrechte Ecken, das zweite je zwei kurze
    Winkel an der Oberkante. Was dazwischen läge, wäre eine Linie quer durchs
    Bild, die nichts sagt, was der Boden nicht schon sagt.

    Als eigene Funktion und nicht im Zeichnen versteckt: offscreen gibt es
    keinen Plotter, und eine Prüfung, die sich dort überspringt, prüft nie
    etwas.
    """
    half_width, half_depth = width / 2.0, depth / 2.0
    arm_x = width * CORNER_FRACTION
    arm_y = depth * CORNER_FRACTION
    segments: list[tuple[tuple[float, float, float], tuple[float, float, float]]] = []
    for x in (-half_width, half_width):
        for y in (-half_depth, half_depth):
            segments.append(((x, y, 0.0), (x, y, height)))
            # Die Winkel zeigen nach innen, sonst stünden sie außerhalb der
            # Fläche, die sie begrenzen.
            segments.append(((x, y, height), (x - arm_x if x > 0 else x + arm_x, y, height)))
            segments.append(((x, y, height), (x, y - arm_y if y > 0 else y + arm_y, height)))
    return segments


#: Wie weit ein Rasterschritt am Mausrad zoomt. VTKs Vorgabe für den
#: Trackball-Stil, damit sich das Rad wie überall sonst anfühlt.
WHEEL_STEP = 0.1

#: Abstand des Vorschaubands von der Oberkante des Viewports.
BANNER_TOP = 12


class PreviewBanner(QFrame):
    """Ein Band über dem Bild: was hier steht, ist noch nicht übernommen.

    Die Live-Vorschau gab es lange, bevor jemand sie sah — der Dialog stand
    mittig darüber und war modal. Beides ist weg; geblieben war die stillere
    Hälfte des Problems: ein verändertes Bild sieht aus wie ein Ergebnis. Also
    sagt das Bild selbst, dass es keins ist.

    Die Legende steht mit im Band, nicht anderswo: sie erklärt Farben, die
    genau hier liegen. Farbe allein trägt nichts (Regel 18) — jedes Feld führt
    sein Zeichen und seinen Namen.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("previewBanner")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(ROOMY, TIGHT, ROOMY, TIGHT)
        layout.setSpacing(ROOMY)

        self.note = QLabel("", self)
        self.legend = QLabel("", self)
        self.hint = QLabel("", self)
        self.hint.setObjectName("previewHint")
        layout.addWidget(self.note)
        layout.addWidget(self.legend)
        layout.addWidget(self.hint)
        self.set_theme("dark")
        self.hide()

    def set_theme(self, theme: str) -> None:
        """Farben aus dem Thema, damit das Band auf beiden Hintergründen liegt.

        Der Rahmen ist **gestrichelt**, und das ist keine Verzierung: „noch
        nicht übernommen" ist ein Zustand, und gestrichelt heißt in jeder
        Oberfläche vorläufig. Damit trägt die Aussage auch, wenn jemand die
        Farben nicht unterscheiden kann (Regel 18).
        """
        colours = THEMES["light" if theme == "light" else "dark"]
        self.setStyleSheet(
            f"#previewBanner {{ background: {colours['window']};"
            f" border: 1px dashed {colours['disabled']}; border-radius: 4px; }}"
            f"#previewBanner QLabel {{ color: {colours['text']}; background: transparent; }}"
            f"#previewBanner #previewHint {{ color: {colours['disabled']}; }}"
        )

    def show_preview(self, note: str, palette: DiffPalette, hint: str) -> None:
        """Zeigt das Band mit Text, Legende und dem Griff zum Vergleichen."""
        colours = DIFF_PALETTES[palette]
        self.note.setText(note)
        self.legend.setText(
            "   ".join(
                f"{encoding.symbol} {tr(encoding.label_key)}"
                for encoding in (colours.added, colours.removed)
            )
        )
        self.legend.setStyleSheet(f"color: {colours.added.colour};")
        self.hint.setText(hint)
        self.show()
        self.adjustSize()
        self.place()

    def place(self) -> None:
        """Oben mittig — dort verdeckt es am wenigsten vom Körper."""
        parent = self.parentWidget()
        if parent is None:
            return
        self.move(max((parent.width() - self.width()) // 2, 0), BANNER_TOP)


def types_text(widget: QWidget | None) -> bool:
    """Ob in diesem Feld ein Leerzeichen ein Leerzeichen ist."""
    from PySide6.QtWidgets import QAbstractSpinBox, QComboBox, QLineEdit, QTextEdit

    if isinstance(widget, QLineEdit | QTextEdit | QAbstractSpinBox):
        return True
    return isinstance(widget, QComboBox) and widget.isEditable()


class HoldToCompare(QWidget):
    """Leertaste halten heißt: kurz das Vorher sehen.

    Als Filter auf der Anwendung, nicht als Tastenkürzel — ein Kürzel feuert
    beim Drücken und weiß vom Loslassen nichts. Und nicht am Viewport selbst:
    solange ein Operationsdialog offen ist, liegt der Fokus dort, und genau
    dann will man vergleichen.

    Auto-Repeat wird verworfen. Eine gehaltene Taste schickt eine Folge aus
    Press und Release, nicht einen langen Druck; ohne diese Prüfung flackerte
    die Vorschau im Takt der Tastenwiederholung.
    """

    def __init__(self, viewport: Viewport) -> None:
        super().__init__(viewport)
        self.hide()
        self._viewport = viewport

    def eventFilter(self, watched: Any, event: Any) -> bool:  # noqa: N802 — Qt-Name
        kind = event.type()
        if kind not in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            return False
        if event.key() != Qt.Key.Key_Space or event.isAutoRepeat():
            return False
        # ``watched`` ist bei einer Taste das Widget mit dem Fokus. Es zu
        # nehmen statt ``QApplication.focusWidget()`` ist nicht nur kürzer: es
        # ist die Frage, um die es geht — wer bekommt diesen Anschlag?
        if types_text(watched):
            return False
        self._viewport.hold_before(kind == QEvent.Type.KeyPress)
        return True


class Viewport(QWidget):
    """Die 3D-Ansicht, oder ein schlichter Hinweis, wenn VTK fehlt."""

    measurementTaken = Signal(object)
    """A finished measurement — carries a ``Measurement``."""
    transformDragged = Signal(object)
    """A finished gizmo drag — carries ``TransformSteps`` (§18.11)."""
    faceDragged = Signal(object, float)
    """Ein Zug an einer Fläche — Normale und Weg entlang ihr (§18.11)."""
    featurePicked = Signal(str)
    """Ein in der Ansicht angeklicktes Merkmal — trägt seine ID (§18.5)."""
    objectPicked = Signal(str)
    """Ein angeklickter Körper — trägt seine Kennung. Leer heißt: daneben
    geklickt, die Auswahl fällt weg."""
    contextMenuAt = Signal(int, int)
    """Ein Rechtsklick, der nichts gedreht hat — trägt die Position in VTKs
    Zählung (von unten). Das Fenster zeigt dort das Menü zur Auswahl."""
    pointPicked = Signal(object)
    """Ein Klick auf eine Stelle ohne Merkmal — trägt den Punkt in
    Weltkoordinaten. Ein offener Dialog, der nach einer Position fragt, trägt
    ihn ein; wer ein Merkmal anklickt, meint das Merkmal und bekommt
    ``featurePicked``."""
    paintRequested = Signal(object)
    """A point on the surface to paint at (§20). The window turns it into an
    operation — the view never changes geometry itself."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.plotter: Any | None = None
        self._actors: dict[ObjectId, Any] = {}
        self._frame_actors: list[Any] = []
        self._selected: ObjectId | None = None
        self._fitted = False
        """Ob die Kamera schon einmal auf die Körper eingepasst wurde. Fällt
        zurück, sobald die Szene leer ist — das nächste Projekt wird wieder
        eingepasst."""
        self._scheme: NavigationScheme = "slicer"
        self._mode: DisplayMode = "solid"
        self._shading: Shading = "flat"
        self._projection: Projection = "perspective"
        self._section: SectionPlane | None = None
        self._slice_thickness: float | None = None
        self._result: EvaluationResult | None = None
        self._uncapped = False
        """Wahr, wenn ein Schnitt offen blieb, weil der Körper es ist (§18.2)."""
        self._object_colour = OBJECT_COLOUR
        self._bed_colour = BED_COLOUR
        self._bed_surface = BED_SURFACE_COLOUR
        self._measure_mode: MeasureMode = "off"
        self._pending_point: Vec3 | None = None
        self.measurements = MeasurementList()
        self._measure_actors: list[Any] = []
        self._gizmo: Any | None = None
        self._gizmo_wanted = False
        """Ob der Gizmo eingeschaltet ist — unabhängig davon, ob gerade einer
        im Bild steht. Der Griff selbst wird bei jedem Auswahl- und
        Szenenwechsel neu angehängt; dieser Schalter sagt, ob überhaupt."""
        self._gizmo_labels: Any | None = None
        """Die Buchstaben an den Gizmo-Achsen. Sie gehen mit ihm."""
        self._face_actor: Any | None = None
        """Die Scheibe, an der der Gizmo hängt, wenn eine Fläche gewählt ist."""
        self._grid_step = 1.0
        self._angle_step = 15.0
        self._map: AnalysisMap | None = None
        self._map_object: ObjectId | None = None
        self._occlusion_applied = False
        self._edge_actors: list[Any] = []
        self._shadow_actors: list[Any] = []
        self._edge_colour = "#4c5258"
        self._feature_overlay = False
        self._feature_actors: list[Any] = []
        self._selected_feature: FeatureId | None = None
        self._layer_actors: list[Any] = []
        self._layer: LayerInfo | None = None
        self._difference: Any | None = None
        self._difference_actors: list[Any] = []
        self._difference_held = False
        """Ob die Vorschau gerade weggehalten wird, um das Vorher zu sehen."""
        self._diff_palette: DiffPalette = "blue_orange"
        self._ghost: EvaluationResult | None = None
        self._explosion = 0.0
        """§18.8: wie weit geteilte Stücke auseinandergezogen gezeichnet werden.
        Nur Darstellung, nie Geometrie."""
        self._plate = -1
        """Welche Druckplatte gezeigt wird; -1 heißt alle (§25)."""
        self._painting = False
        """§20: solange das an ist, sind Klicks Pinselstriche."""
        self._hidden: frozenset[ObjectId] = frozenset()
        """§18.8: was der Nutzer ausgeblendet hat. Ansicht, nicht Szene — die
        Körper werden weiter gerechnet, geprüft und exportiert."""
        self._display_cache: dict[tuple[ObjectId, int], Any] = {}
        """§18.9: die dezimierte Fassung des zuletzt gezeigten Körpers. Sie
        fließt nie in den Kern zurück."""

        self.banner = PreviewBanner(self)
        """Das Band über dem Bild, wenn eine Vorschau läuft."""
        self._compare = HoldToCompare(self)
        """Der Filter für die Leertaste. Er hängt an der Anwendung, solange das
        Band steht — nicht länger, sonst schluckt er anderswo Leerzeichen."""
        self._comparing = False

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
        self._add_orientation_widget()
        self._apply_render_quality()
        self.set_theme("dark")
        # Schaltet das Picking gleich mit ein — ein Stilwechsel und der erste
        # Aufbau sind für die Ansicht dasselbe.
        self.set_navigation("slicer")

    # --- Darstellungsqualität (§18.1) -------------------------------------------

    def _add_orientation_widget(self) -> None:
        """Der Würfel oben rechts: anfassbare Achsen statt eines Menüwegs.

        `add_axes` zeigt nur an, wo Norden ist; dieser Würfel lässt sich
        **anklicken** und dreht die Kamera auf die getroffene Seite. Damit ist
        der häufigste aller Ansichtswechsel — „zeig mir das von oben" — eine
        Mausbewegung statt zweier Menüebenen.

        Er ersetzt die Kürzel nicht und die Kameraeinträge auch nicht: dasselbe
        Ziel auf drei Wegen ist bei einer Ansicht kein Widerspruch, sondern die
        Regel aus §19.2 (alles über die Palette, Kürzel lernen sich nebenbei).
        Was genau eine Stelle haben muss, sind Operationen — und der Würfel ist
        keine.

        **Er ersetzt aber `add_axes`.** Das kleine Achsenkreuz unten links sagt
        dasselbe und lässt sich nicht anfassen; zwei Anzeigen für dieselbe
        Auskunft in einem Bild sind eine zu viel. Aufgefallen ist es erst auf
        dem neu aufgenommenen Handbuchbild — im Code standen die beiden Zeilen
        untereinander und sahen wie zwei verschiedene Dinge aus.
        """
        if self.plotter is None:
            return
        try:
            self.plotter.add_camera_orientation_widget()
        except Exception as problem:  # pragma: no cover - hängt am Treiber
            _log.info("orientation widget unavailable: %s", problem)

    def _apply_render_quality(self) -> None:
        """Kantenglättung und Umgebungsverdeckung.

        Zwei Zutaten, beide gemessen: Kantenglättung kostet auf dieser Maschine
        nichts Messbares und nimmt jeder schrägen Kante die Treppe.
        **Umgebungsverdeckung** ist die eigentliche Verbesserung — sie
        verdunkelt, was eng beieinander liegt, und macht damit eine Bohrung
        ohne eine einzige Linie als Vertiefung erkennbar.

        Beide laufen in einem ``try``, weil sie am Treiber hängen: eine
        Maschine, deren OpenGL sie nicht kann, soll ein einfacheres Bild
        bekommen und keinen Absturz. Was nicht ging, steht im Protokoll — nicht
        vor dem Nutzer, der hat nichts davon.
        """
        if self.plotter is None:
            return
        try:
            self.plotter.enable_anti_aliasing("fxaa")
        except Exception as problem:  # pragma: no cover - hängt am Treiber
            _log.info("anti-aliasing unavailable: %s", problem)
        self._apply_ambient_occlusion()

    @property
    def ambient_occlusion(self) -> bool:
        """Ob die Umgebungsverdeckung gerade gelten soll.

        **Sie muss aus, solange eine Analysekarte läuft.** Die Karte färbt
        nach Zahlen und stellt eine Legende mit Wertebereich daneben (§18.4);
        eine Verdeckung, die Vertiefungen nachdunkelt, verschöbe genau dort die
        Farbe, wo die Karte etwas aussagt — der abgelesene Wert wäre ein
        anderer als der gemeldete. Schönheit vor Ablesbarkeit gibt es nicht.

        Als Eigenschaft und nicht als Zustand des Plotters, damit die **Regel**
        prüfbar bleibt: auf der Offscreen-Plattform gibt es keinen Plotter, und
        ein Test, der sich dort überspringt, prüft nie etwas.
        """
        return self._map is None

    def _apply_ambient_occlusion(self) -> None:
        """Die Regel an den Plotter geben, wenn es einen gibt."""
        wanted = self.ambient_occlusion
        if self.plotter is None or self._occlusion_applied == wanted:
            return
        try:
            if wanted:
                self.plotter.enable_ssao(radius=SSAO_RADIUS, bias=SSAO_BIAS)
            else:
                self.plotter.disable_ssao()
        except Exception as problem:  # pragma: no cover - hängt am Treiber
            _log.info("ambient occlusion unavailable: %s", problem)
            return
        self._occlusion_applied = wanted

    @property
    def contact_shadows(self) -> bool:
        """Ob ein Kontaktschatten auf der Platte liegen soll.

        Ein Körper ohne Schatten schwebt, und die Frage „steht das Teil auf der
        Platte oder darüber?" ist genau die, die der Viewport beantworten soll
        (§18.6).

        Dieselbe Ausnahme wie bei der Umgebungsverdeckung: solange eine
        Analysekarte läuft, bleibt er aus. Er dunkelt nach, und die Karte färbt
        nach Zahlen — der abgelesene Wert wäre ein anderer als der gemeldete.
        """
        return self._map is None

    def _shadow_outline_of(self, surface: Any) -> Any:
        """Der Schatten eines Körpers auf der Platte, entlang der Lichtrichtung.

        **Nicht** über ``enable_shadows``. Der VTK-Schattenwurf wurde in vier
        Anläufen geprüft und in allen verworfen: mit drei Lichtern verschattet
        er ganze Seitenflächen des Körpers schwarz, mit einem einzelnen
        genauso, und die Schattenkarte deckt die Platte nicht ab — ihre Ränder
        laufen schwarz aus. Mit gefüllter Platte kam ein richtiger Schatten
        heraus, die schwarzen Ränder blieben.

        Die Projektion kann alles, was hier gebraucht wird, und nichts davon
        hängt am Treiber. **Schräg und nicht senkrecht:** senkrecht projiziert
        liegt der Schatten exakt unter dem Körper und ist von ihm verdeckt — im
        Bild war er schlicht nicht da. Entlang einer festen Lichtrichtung
        geworfen tritt er seitlich hervor, und weil sein Versatz mit der Höhe
        wächst, beantwortet er nebenbei die Frage, die er beantworten soll:
        ein schwebendes Teil hat seinen Schatten weiter weg.

        Die konvexe Hülle ist bewusst gröber als der echte Umriss — ein Schatten
        zeigt den Ort, nicht die Form; wer die Form sucht, dreht die Ansicht.
        """
        import numpy as np
        import pyvista as pv

        points = np.asarray(surface.points, dtype=float)
        if len(points) < 3:
            return None
        cast = shadow_points(points)
        try:
            hull = pv.PolyData(cast).delaunay_2d()
        except Exception as problem:  # pragma: no cover - hängt an der Punktlage
            _log.info("shadow outline unavailable: %s", problem)
            return None
        if hull.n_cells == 0:
            return None
        hull.points[:, 2] = SHADOW_LIFT
        return hull

    # --- scene ------------------------------------------------------------------

    def show_scene(self, result: EvaluationResult | None) -> None:
        """Baut die Ansicht aus der letzten vollständigen Auswertung neu (§15.3)."""
        self._result = result
        # Vor dem Plotter-Zweig: ob ein Projekt schon einmal im Bild stand, ist
        # eine Aussage über die Szene und nicht über VTK — offscreen gibt es
        # keinen Plotter, und ein Test, der sich dort überspringt, prüft nie
        # etwas.
        self._fit_once_for(result)
        if result is None:
            # Eine leere Szene hat keine Auswahl, kein gewähltes Merkmal und
            # keine Maße. Vor dem Plotter-Zweig, aus demselben Grund wie das
            # Einpassen: das sind Aussagen über die Szene, nicht über VTK.
            self._selected = None
            self._selected_feature = None
            self.measurements.clear()
        if self.plotter is None:
            return
        for actor in self._actors.values():
            self.plotter.remove_actor(actor, render=False)
        self._actors.clear()
        for actor in self._edge_actors:
            self.plotter.remove_actor(actor, render=False)
        self._edge_actors.clear()
        for actor in self._shadow_actors:
            self.plotter.remove_actor(actor, render=False)
        self._shadow_actors.clear()
        self._uncapped = False
        if result is None:
            # Und im Bild dasselbe: ohne dieses Aufräumen blieben die orangen
            # Markierungen des vorigen Objekts stehen, während Objektbaum und
            # Prüfbericht längst leer waren — die Anwendung sah aus, als hätte
            # sie das Projekt halb behalten.
            self._redraw_features()
            self._redraw_measurements()
            self._redraw_layer()
            # Nur den Griff wegnehmen, nicht die Entscheidung: der Schalter in
            # der Leiste bleibt an, und das nächste Projekt bekommt den Griff
            # wieder, sobald etwas ausgewählt ist.
            self._detach_gizmo()
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
            elif self._map is None:
                extra = self._slot_colours(surface, mesh, entry, len(raw.faces))
            actor = self.plotter.add_mesh(
                surface,
                color=self._object_colour,
                smooth_shading=self._shading == "smooth",
                backface_params={"color": BACKFACE_COLOUR},
                name=f"object:{object_id}",
                render=False,
                # Die Ansicht wird bei jeder Änderung neu aufgebaut, und pyvista
                # setzt die Kamera zurück, sobald es den ersten Aktor bekommt —
                # nach dem Leerräumen ist jeder Körper der erste. Damit sprang
                # die Ansicht bei jeder Auswahl auf Anfang, und ein
                # Heranzoomen überlebte keinen Klick. Eingepasst wird
                # ausdrücklich, in `_fit_once_for`.
                reset_camera=False,
                **style,
                **extra,
            )
            self._actors[object_id] = actor
            self._draw_feature_edges(surface, object_id)
            self._draw_shadow(surface, object_id)

        self.select(self._selected)
        self._redraw_features()
        self._redraw_layer()
        self.plotter.render()

    def _slot_colours(self, surface: Any, mesh: Any, entry: Any, face_count: int) -> dict[str, Any]:
        """Ein bemalter Körper wird in seinen Filamentfarben gezeichnet (§20).

        Solidon kennt Materialslots seit P9: ``paint_slot`` setzt sie,
        ``slots_from_texture`` leitet sie ab, der 3MF-Export macht daraus den
        Farbwechsel für den Drucker. Die Ansicht malte trotzdem alles grau —
        wer ein Teil zweifarbig bemalte, sah das Ergebnis zum ersten Mal im
        Slicer.

        Das ist keine Dekoration: die Farbe steht im Dokument, sie ist der
        Wert, der exportiert wird, und sie hier zu zeigen ist die einzige
        Gelegenheit, einen Fehlgriff zu bemerken, solange er noch billig ist.

        Eine Analysekarte hat Vorrang; sie färbt nach Zahlen, und zwei
        Bedeutungen auf derselben Fläche wären keine.
        """
        slots = getattr(entry, "material_slots", None)
        indices = getattr(mesh, "slots", ())
        if not slots or len(indices) != face_count:
            return {}

        import numpy as np

        known = {slot.index: slot for slot in slots}
        highest = max(known)
        table = []
        for index in range(highest + 1):
            slot = known.get(index)
            colour = slot.colour if slot is not None else None
            table.append(_hex(colour) if colour is not None else self._object_colour)
        if len(table) < 2:
            # Ein einziger Slot ist kein Mehrfarbdruck, sondern die Vorgabe.
            return {}
        surface.cell_data["slot"] = np.asarray(indices, dtype=np.int32)
        return {
            "scalars": "slot",
            "cmap": table,
            "clim": (0, highest),
            "show_scalar_bar": False,
        }

    def _draw_feature_edges(self, surface: Any, object_id: ObjectId) -> None:
        """Die Kanten des *Körpers*, nicht die des Netzes (§18.1).

        „Massiv mit Kanten" zeichnet jede Dreieckskante — das beantwortet die
        Frage, wie fein das Netz ist, und dafür ist es da. Es beantwortet
        nicht, wo das Teil eine Kante hat: bei einem Zylinder aus zweihundert
        Segmenten geht die eine Kante, auf die es ankommt, in
        zweihundertneunundneunzig anderen unter.

        Hier stehen deshalb nur Kanten, an denen zwei Flächen wirklich
        aufeinandertreffen, dazu die offenen Ränder — bei einem undichten Netz
        also genau die Stellen, die der Prüfbericht meldet. Ein rundes Teil
        bekommt gar keine: eine Kugel hat keine Kante, und eine erfundene wäre
        schlimmer als keine.

        Nur im massiven Modus. In den anderen drei ist entweder alles schon
        gezeichnet oder man sieht hindurch, und dann wäre eine zweite
        Linienlage nur Gitter.
        """
        if self.plotter is None or self._mode != "solid":
            return
        if surface.n_cells > FEATURE_EDGE_LIMIT:
            return
        try:
            edges = surface.extract_feature_edges(
                feature_angle=FEATURE_EDGE_ANGLE,
                boundary_edges=True,
                non_manifold_edges=False,
                feature_edges=True,
                manifold_edges=False,
            )
        except Exception as problem:  # pragma: no cover - hängt an der Geometrie
            _log.info("feature edges unavailable: %s", problem)
            return
        if edges.n_cells == 0:
            return
        self._edge_actors.append(
            self.plotter.add_mesh(
                edges,
                color=self._edge_colour,
                line_width=FEATURE_EDGE_WIDTH,
                name=f"edges:{object_id}",
                render=False,
                pickable=False,
            )
        )

    def _draw_shadow(self, surface: Any, object_id: ObjectId) -> None:
        """Den Kontaktschatten dieses Körpers auf die Platte legen."""
        if self.plotter is None or not self.contact_shadows:
            return
        hull = self._shadow_outline_of(surface)
        if hull is None:
            return
        self._shadow_actors.append(
            self.plotter.add_mesh(
                hull,
                color=SHADOW_COLOUR,
                opacity=SHADOW_OPACITY,
                lighting=False,
                name=f"shadow:{object_id}",
                render=False,
                pickable=False,
            )
        )

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

        Die Schichtanalyse schneidet mit: „Durch die Höhe fahren und den
        Querschnitt ansehen" versprach der Text, und das Modell blieb dabei
        undurchsichtig stehen — sichtbar war nur eine dünne Kontur darunter.
        Wer eine Schicht gewählt hat, will sehen, was auf dieser Höhe steht,
        nicht was darüber liegt.
        """
        plane = self._section
        if plane is None and self._layer is not None:
            plane = SectionPlane(normal=(0.0, 0.0, 1.0), position=self._layer.z)
        if plane is None:
            return mesh
        second = None
        if self._section is not None and self._slice_thickness is not None:
            offset = plane.position - self._slice_thickness
            second = SectionPlane(normal=plane.normal, position=offset).flipped()
        result = cut(mesh, plane, second)
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
        # Der Griff folgt der Auswahl (§18.11): wer ein anderes Objekt wählt,
        # will es auch bewegen — nicht das vorige. Und weil `show_scene` hier
        # durchkommt, hängt der Griff nach jeder Auswertung am neuen Actor
        # statt am entfernten der letzten.
        self.set_gizmo(self._gizmo_wanted)
        self.plotter.render()

    def show_build_volume(self, profile: Profile) -> None:
        """Das Bett als Raster in echter Größe, der Bauraum als Eckwinkel
        (§18.6).

        **Kein Aufruf hier setzt die Kamera.** Der Bauraum ist Kulisse, und
        pyvista passt bei der ersten Netzfläche einer leeren Szene von selbst
        ein — das machte jedes Einpassen auf die Körper wieder zunichte, weil
        die Kulisse danach gezeichnet wurde.
        """
        if self.plotter is None:
            return
        import pyvista as pv

        for actor in self._frame_actors:
            self.plotter.remove_actor(actor, render=False)
        self._frame_actors.clear()

        width, depth, height = profile.printer.build_volume
        # Ein gefüllter Grund unter dem Raster. Bis hierhin war die Platte ein
        # Drahtgitter über dem Hintergrund — hübsch, aber ohne Fläche: ein
        # Schatten darauf fiel auf nichts und war im Bild schlicht nicht da.
        # Knapp unter null, damit er nicht mit dem Raster um dieselbe Tiefe
        # streitet.
        self._frame_actors.append(
            self.plotter.add_mesh(
                pv.Plane(
                    center=(0.0, 0.0, -BED_SURFACE_DROP),
                    direction=(0.0, 0.0, 1.0),
                    i_size=width,
                    j_size=depth,
                ),
                color=self._bed_surface,
                ambient=0.45,
                diffuse=0.55,
                specular=0.0,
                name="bed_surface",
                render=False,
                reset_camera=False,
                pickable=False,
            )
        )
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
                reset_camera=False,
            )
        )
        import numpy as np

        segments = volume_edges(width, depth, height)
        points = np.asarray([point for pair in segments for point in pair], dtype=float)
        lines = np.hstack([[2, 2 * index, 2 * index + 1] for index in range(len(segments))])
        self._frame_actors.append(
            self.plotter.add_mesh(
                pv.PolyData(points, lines=lines),
                color=self._bed_colour,
                opacity=0.35,
                line_width=1,
                name="build_volume",
                render=False,
                reset_camera=False,
                pickable=False,
            )
        )

        marks = bed_scale(width, depth)
        self._frame_actors.append(
            self.plotter.add_point_labels(
                np.asarray([point for point, _text in marks], dtype=float),
                [text for _point, text in marks],
                text_color=self._bed_colour,
                font_size=9,
                show_points=False,
                shape=None,
                always_visible=True,
                name="bed_scale",
                render=False,
                reset_camera=False,
            )
        )
        self.plotter.render()

    # --- theme (§19.3) ----------------------------------------------------------

    def set_theme(self, theme: str) -> None:
        """Hintergrund-, Körper- und Bettfarben folgen dem Anwendungsthema."""
        colours = viewport_colours(theme)  # type: ignore[arg-type]
        self._object_colour = colours["object"]
        self._bed_colour = colours["bed"]
        self._bed_surface = colours["bed_surface"]
        self._edge_colour = colours["edge"]
        self.banner.set_theme(theme)
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

    def section_ranges(self) -> dict[str, tuple[float, float]]:
        """Der Weg des Schnittschiebers, **je Achse einzeln**.

        Vorher galt eine Spanne für alle drei, gebildet aus dem kleinsten und
        größten Wert über sämtliche Achsen. Bei einem Brett von 80 auf 50 auf 8
        lief der Z-Regler damit über achtzig Millimeter, und das Teil belegte
        ein Zehntel seiner Länge: ein Zug in die Mitte landete auf 23 mm, weit
        über dem Brett, und man sah keinen Schnitt.
        """
        empty = {"x": (-100.0, 100.0), "y": (-100.0, 100.0), "z": (-100.0, 100.0)}
        if self._result is None or not self._result.scene.objects:
            return empty

        boxes = [entry.mesh.bounds for entry in self._result.scene.objects.values()]
        return {
            axis: (
                min(box.minimum[index] for box in boxes),
                max(box.maximum[index] for box in boxes),
            )
            for index, axis in enumerate(("x", "y", "z"))
        }

    # --- measuring (§18.3) ------------------------------------------------------

    def set_measure_mode(self, mode: MeasureMode) -> None:
        """Punkt zu Punkt, Wandstärke, oder aus. Klicks rasten ein, bevor sie
        zählen.
        """
        self._measure_mode = mode
        self._pending_point = None

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

    def _on_picked(self, point: Any) -> None:
        picked = (float(point[0]), float(point[1]), float(point[2]))
        if self._painting:
            self.paintRequested.emit(picked)
            return
        if self._measure_mode == "off":
            # Nicht am Messen: erst das Merkmal darunter (§18.5), sonst der
            # Körper. Ein Klick daneben hebt die Auswahl auf — sonst gäbe es
            # keinen Weg, sie ohne den Baum wieder loszuwerden.
            if self._feature_at(picked) is not None:
                self._select_at(picked)
                return
            self.objectPicked.emit(self._object_at(picked) or "")
            self.pointPicked.emit(picked)
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

    def _object_at(self, point: Vec3) -> ObjectId | None:
        """Der Körper unter einem Klick, oder nichts.

        Anders als ``_nearest_mesh`` antwortet das hier auch mit „daneben": wer
        neben das Modell klickt, will die Auswahl loswerden, nicht das nächste
        Objekt bekommen. Geprüft wird gegen den Hüllquader mit einer Toleranz in
        der Größe der Fangweite — der Picker liefert einen Punkt auf der
        Oberfläche, und der liegt bauartbedingt auf dem Rand des Quaders.

        Bei mehreren Treffern gewinnt der kleinste Körper: eine Schraube in
        einem Gehäuse ist das, was jemand meint, wenn er auf sie zeigt.
        """
        if self._result is None:
            return None
        best: ObjectId | None = None
        best_volume = float("inf")
        for object_id, entry in self._result.scene.objects.items():
            bounds = entry.mesh.bounds
            size = bounds.size
            slack = max(EPS_MATCH_MINIMUM, max(size) * EPS_MATCH_RELATIVE)
            inside = all(
                low - slack <= value <= high + slack
                for low, high, value in zip(bounds.minimum, bounds.maximum, point, strict=True)
            )
            if not inside:
                continue
            volume = size[0] * size[1] * size[2]
            if volume < best_volume:
                best_volume = volume
                best = object_id
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
        # Solange Farbe eine Zahl bedeutet, darf nichts sie nachdunkeln —
        # weder die Verdeckung noch ein Schatten.
        self._apply_ambient_occlusion()
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
        """Schaltet die **Beschriftungen** an den erkannten Merkmalen um.

        Das Anklicken hängt nicht daran. §18.5 nennt das Zeigen auf ein Merkmal
        die wichtigste Einzelfunktion — sie hinter einem Häkchen zu verstecken
        hieße, sie für jeden abzuschalten, der das Häkchen nicht findet. Der
        Klick trifft immer; was sichtbar wird, ist die Frage der Beschriftung.
        """
        self._feature_overlay = active
        if self.plotter is None:
            return
        self._redraw_features()
        self.plotter.render()

    def select_feature(self, feature_id: FeatureId | None) -> None:
        self._selected_feature = feature_id
        self._redraw_features()
        if self.plotter is not None:
            # Auch der Griff wechselt mit: eine gewählte Fläche bekommt ihn
            # auf die Fläche, eine abgewählte gibt ihn ans Objekt zurück
            # (§18.11) — nicht erst beim nächsten Umschalten.
            self.set_gizmo(self._gizmo_wanted)
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
                point_size=8,
                # **Auch was im Material steckt.** Eine Bohrung hat ihren
                # Mittelpunkt auf halber Höhe im Körper; ohne das blieb ihre
                # Beschriftung dahinter verborgen, und beschriftet waren nur
                # die drei Flächen — bei einem Teil, das nach seinen vier
                # Bohrungen benannt ist.
                always_visible=True,
                shape=None,
                name="features",
                render=False,
                reset_camera=False,
            )
        )

    def _feature_at(self, point: Vec3) -> FeatureId | None:
        """Das Merkmal nächst einem Klick — zeigen schlägt einen Namen
        tippen (§18.5).

        Gesucht wird im Körper **unter** dem Zeiger, nicht im gerade
        ausgewählten. Andersherum wäre es ein Ring: den Körper wählt man aus,
        indem man ihn anklickt, und der Klick fände sein Merkmal erst, wenn er
        schon ausgewählt wäre. Ohne Treffer bleibt der gewählte Körper die
        Quelle — dann ist der Klick daneben gegangen, und die Merkmale, die man
        vor Augen hat, sind seine.
        """
        import numpy as np

        target = np.asarray(point, dtype=float)
        features = self._features_of(self._object_at(point)) or self._features_of_selection()
        best: FeatureId | None = None
        best_offset = float("inf")
        for feature_id, feature in features.items():
            centre = feature.params.get("centre")
            if centre is None:
                continue
            offset = float(np.linalg.norm(np.asarray(centre, dtype=float) - target))
            if offset < best_offset:
                best_offset = offset
                best = feature_id
        return best

    def _features_of(self, object_id: ObjectId | None) -> dict[FeatureId, Feature]:
        """Die Merkmale eines Körpers, oder nichts."""
        if object_id is None or self._result is None:
            return {}
        entry = self._result.scene.objects.get(object_id)
        return dict(entry.features) if entry is not None else {}

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

    def mark_preview(self, note: str, hint: str = "") -> None:
        """Sagt im Bild, dass die gezeigte Änderung noch nicht übernommen ist.

        Leerer Text nimmt das Band wieder weg. Der Text kommt von außen: der
        Viewport weiß nicht, ob er eine Operation vorführt oder einen
        Agentenvorschlag, und beides heißt etwas anderes.
        """
        from PySide6.QtWidgets import QApplication

        application = QApplication.instance()
        if note:
            self.banner.show_preview(note, self._diff_palette, hint)
            if application is not None and not self._comparing:
                application.installEventFilter(self._compare)
                self._comparing = True
        else:
            self.banner.hide()
            self.hold_before(False)
            if application is not None and self._comparing:
                application.removeEventFilter(self._compare)
                self._comparing = False

    def hold_before(self, held: bool) -> None:
        """Blendet die Vorschau weg, solange jemand den Vergleich hält.

        Einen Unterschied sieht man nur, wenn man beides kennt. Das Modell
        darunter ist ohnehin der Stand *vor* der Operation — die Vorschau liegt
        nur darüber. Sie wegzunehmen ist also schon der ganze Vergleich, und er
        kostet keine zweite Rechnung.
        """
        if held == self._difference_held:
            return
        self._difference_held = held
        self._redraw_difference()
        if self.plotter is not None:
            self.plotter.render()

    @property
    def difference_held(self) -> bool:
        return self._difference_held

    def _redraw_difference(self) -> None:
        if self.plotter is None:
            return
        for actor in self._difference_actors:
            self.plotter.remove_actor(actor, render=False)
        self._difference_actors.clear()
        if self._difference is None or self._difference_held:
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
        if not self.banner.isHidden():
            # Die Legende erklärt Farben; die haben sich gerade geändert.
            self.banner.show_preview(self.banner.note.text(), palette, self.banner.hint.text())
        if self.plotter is not None:
            self.plotter.render()

    def resizeEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Name
        super().resizeEvent(event)
        self.banner.place()

    # --- layer analysis (§18.10) ------------------------------------------------

    def set_layer(self, layer: LayerInfo | None) -> None:
        """Zeigt die Konturen einer Schicht. Geometrie, keine
        Werkzeugwege (§18.10).
        """
        was = self._layer
        self._layer = layer
        # Die Körper werden neu gebaut, weil sie jetzt anders geschnitten sind
        # — aber nur, wenn sich das ändert. Beim Ziehen am Schieber ist das
        # jeder Schritt; ohne die Prüfung wäre es auch jedes Ausschalten eines
        # bereits ausgeschalteten Schiebers.
        if (was is None) != (layer is None) or (
            was is not None and layer is not None and was.z != layer.z
        ):
            self.show_scene(self._result)
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

    def gizmo_target(self) -> Feature | None:
        """Die Fläche, an der der Gizmo hängt — oder ``None`` für das Objekt.

        Als eigene Auskunft und nicht als Zustand des Plotters, damit die
        Regel prüfbar bleibt: offscreen gibt es keinen Plotter, und ein Test,
        der sich dort überspringt, prüft nie etwas.
        """
        if self._selected_feature is None:
            return None
        feature = self._features_of_selection().get(self._selected_feature)
        if feature is None or feature.kind != "face":
            return None
        if feature.params.get("normal") is None or feature.params.get("centre") is None:
            return None
        return feature

    def set_gizmo(self, active: bool) -> None:
        """Hängt den Gizmo an die gewählte Fläche — sonst an das Objekt.

        Ist ein Merkmal gewählt, ist es das Genauere von beidem: wer eine
        Fläche angeklickt hat, will sie versetzen und nicht den Körper
        verschieben (§18.11). Am Griff sieht man den Unterschied, denn er
        sitzt dann auf der Fläche.

        Der Griff wird hier immer frisch gebaut, nie weiterbenutzt: pyvistas
        Widget rechnet gegen die ``user_matrix`` seines Actors und merkt sie
        sich über Züge hinweg — ein weitergereichter Griff trüge den vorigen
        Zug in den nächsten hinein, und einer am Actor der letzten Auswertung
        zöge an einem Körper, der längst nicht mehr im Bild ist.
        """
        self._gizmo_wanted = active
        if self.plotter is None:
            return
        self._detach_gizmo()
        if not active or self._selected is None:
            return
        face = self.gizmo_target()
        actor = self._face_handle(face) if face is not None else self._actors.get(self._selected)
        if actor is None:
            return
        self._gizmo = self.plotter.add_affine_transform_widget(
            actor,
            release_callback=self._on_gizmo_released,
            scale=GIZMO_SCALE,
            line_radius=GIZMO_LINE_RADIUS,
        )
        self._label_gizmo(actor)

    def _detach_gizmo(self) -> None:
        """Nimmt Griff, Beschriftung und Flächenscheibe aus dem Bild.

        Über ``remove()`` — eine ``Off``-Methode hat pyvistas
        ``AffineWidget3D`` nicht, der Aufruf endete als ``AttributeError``,
        den Qt schluckte: der Griff blieb stehen, obwohl der Schalter aus
        war. Anders als :meth:`set_gizmo` lässt das den Schalterzustand in
        Ruhe — eine leere Szene nimmt den Griff weg, aber nicht die
        Entscheidung, dass einer gewünscht ist.
        """
        if self._gizmo is not None:
            self._gizmo.remove()
            self._gizmo = None
        self._drop_gizmo_labels()
        self._drop_face_handle()

    def _label_gizmo(self, actor: Any) -> None:
        """Schreibt X, Y und Z an die Achsen (Regel 18).

        Der Gizmo unterschied sie allein über Rot, Grün und Blau. Die
        Buchstaben sitzen etwas hinter den Spitzen — auf ihnen läge die
        Beschriftung dort, wo man greifen will.
        """
        if self.plotter is None:
            return
        import numpy as np

        length = float(actor.GetLength()) * GIZMO_SCALE * 1.15
        marks = gizmo_labels(tuple(float(value) for value in actor.center), length)  # type: ignore[arg-type]
        self._gizmo_labels = self.plotter.add_point_labels(
            np.asarray([point for point, _text in marks], dtype=float),
            [text for _point, text in marks],
            # In der Körperfarbe des Themas: hell im dunklen, dunkel im
            # hellen. Die Kantenfarbe war für Text auf dem Hintergrund zu
            # leise — im Bild kaum zu lesen.
            text_color=self._object_colour,
            font_size=13,
            bold=True,
            show_points=False,
            shape=None,
            always_visible=True,
            name="gizmo_labels",
            render=False,
            reset_camera=False,
        )

    def _drop_gizmo_labels(self) -> None:
        if self._gizmo_labels is not None and self.plotter is not None:
            self.plotter.remove_actor(self._gizmo_labels, render=False)
        self._gizmo_labels = None

    def _face_handle(self, feature: Feature) -> Any:
        """Ein Griff auf der Fläche, an dem der Gizmo sitzen kann.

        Der Gizmo braucht einen Actor. Die Fläche selbst ist Teil des
        Körperactors und lässt sich nicht einzeln greifen, also bekommt sie
        eine kleine Scheibe an ihrem Mittelpunkt — sichtbar, damit klar ist,
        woran gezogen wird, und flach, damit sie nichts verdeckt.
        """
        import numpy as np
        import pyvista as pv

        if self.plotter is None:
            return None
        centre = np.asarray(feature.params["centre"], dtype=float)
        normal = np.asarray(feature.params["normal"], dtype=float)
        span = float(np.linalg.norm(np.asarray(self.bounds_size(), dtype=float)))
        radius = max(span * FACE_HANDLE_SHARE, FACE_HANDLE_MINIMUM)
        disc = pv.Disc(center=centre, normal=normal, inner=0.0, outer=radius, c_res=24)
        self._face_actor = self.plotter.add_mesh(
            disc, color=MEASURE_COLOUR, opacity=0.6, name="face-handle", render=False
        )
        return self._face_actor

    def _drop_face_handle(self) -> None:
        if self._face_actor is not None and self.plotter is not None:
            self.plotter.remove_actor(self._face_actor, render=False)
        self._face_actor = None

    def bounds_size(self) -> Vec3:
        """Wie groß das gewählte Objekt ist — für Griffe, die mitwachsen."""
        if self._result is None or self._selected is None:
            return (100.0, 100.0, 100.0)
        entry = self._result.scene.objects.get(self._selected)
        if entry is None:
            return (100.0, 100.0, 100.0)
        size = entry.mesh.bounds.size
        return (float(size[0]), float(size[1]), float(size[2]))

    def _on_gizmo_released(self, matrix: Any) -> None:
        """Ein Ziehen endet als Operationen, nicht als Matrix (§18.11, §2.1).

        Am Ende wird der Griff immer neu angehängt, ob ein Zug herauskam oder
        nicht. Zweierlei hängt daran: pyvista reicht beim nächsten Zug die
        Matrix *einschließlich* des vorigen mit — ein stehen gelassener Griff
        wendete jede Bewegung beim zweiten Mal doppelt an. Und ein Zug unter
        der Fangschwelle erzeugt keine Operation; ohne das Neuanhängen bliebe
        der Körper im Bild dort stehen, wohin gezogen wurde, während die Szene
        ihn nie bewegt hat.
        """
        import numpy as np

        steps = decompose_transform(np.asarray(matrix, dtype=float))
        face = self.gizmo_target()
        if face is not None:
            # Eine Fläche wandert nur entlang ihrer Normalen. Was quer dazu
            # gezogen wurde, ist keine Bewegung dieser Fläche — sonst wäre
            # Press/Pull ein Verschieben mit anderem Namen.
            normal = tuple(float(value) for value in face.params["normal"])
            distance = snap_to_step(
                along_normal(steps.offset, (normal[0], normal[1], normal[2])), self._grid_step
            )
            if abs(distance) > EPS_DISPLAY:
                self.faceDragged.emit(normal, distance)
            self.set_gizmo(self._gizmo_wanted)
            return
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
        self.set_gizmo(self._gizmo_wanted)

    def reset_camera(self) -> None:
        """Passt auf die Körper ein — nicht auf den Bauraum.

        ``plotter.reset_camera()`` nimmt alle Aktoren, und dazu gehört der
        Rahmen des Bauraums. Bei einem 80-mm-Teil in einem 256er Bauraum füllte
        damit die Kulisse das Bild und das Teil war ein Fleck darin: „Alles
        einpassen" tat sichtbar nichts, weil schon eingepasst war.

        Ohne Körper bleibt der Bauraum das Maß — dann ist er das Einzige, was
        es zu sehen gibt.
        """
        if self.plotter is None:
            return
        bounds = self._object_bounds()
        if bounds is None:
            self.plotter.reset_camera()
        else:
            self.plotter.reset_camera(bounds=bounds)
        # **Ohne diese Zeile war das Einpassen wirkungslos.** pyvistas
        # ``reset_camera`` lässt ``camera_set`` auf False stehen, und der
        # nächste Zugriff auf ``plotter.camera`` — beim Rendern, beim
        # Stilwechsel, bei jeder Achsansicht — passt dann von selbst noch
        # einmal ein, diesmal über *alle* Aktoren. Der Bauraum gewann also
        # jedes Mal, obwohl hier die Maße der Körper standen.
        self.plotter.camera_set = True

    def _fit_once_for(self, result: EvaluationResult | None) -> None:
        """Passt ein, wenn die Ansicht zum ersten Mal etwas zu zeigen hat.

        Ein geöffnetes Projekt soll im Bild stehen, ohne dass jemand Pos1
        drückt. Jeder weitere Aufbau lässt die Kamera in Ruhe: wer heranzoomt,
        eine Bohrung setzt und die Ansicht dabei verliert, hat den Zoom
        zweimal gemacht.
        """
        has_objects = result is not None and bool(result.scene.objects)
        if has_objects and not self._fitted:
            self.reset_camera()
        self._fitted = has_objects

    def _object_bounds(self) -> tuple[float, float, float, float, float, float] | None:
        """Der Hüllquader über alle Körper, im Format von VTK, oder nichts."""
        if self._result is None or not self._result.scene.objects:
            return None
        boxes = [entry.mesh.bounds for entry in self._result.scene.objects.values()]
        low = [min(box.minimum[axis] for box in boxes) for axis in range(3)]
        high = [max(box.maximum[axis] for box in boxes) for axis in range(3)]
        return (low[0], high[0], low[1], high[1], low[2], high[2])

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
        # Schwach gehalten, mit Absicht: VTK hält den Stil, der Stil hielte
        # sonst den Viewport, und der hält den Plotter, der den Interactor hält.
        # Diese Schleife überlebt jedes Schließen — der Speicherbereiniger räumt
        # sie später ab, und dann steht ein C++-Objekt hinter einer Python-
        # Referenz, die es nicht mehr gibt. Das ist der Absturz ohne Zeile, den
        # die Suite als Access Violation am Ende eines Laufs zeigt.
        weak = weakref.ref(self)

        def on_context(x: int, y: int) -> None:
            view = weak()
            if view is not None:
                view._on_right_click(x, y)

        def on_pick(x: int, y: int) -> None:
            view = weak()
            if view is not None:
                view._on_left_click(x, y)

        style = _InteractorStyle(self.plotter, scheme, on_context, on_pick)
        self.plotter.interactor.SetInteractorStyle(style)
        # Ein neuer Stil bringt seine eigenen Beobachter mit; was beim Wechsel
        # sonst noch einzuschalten wäre, steht dort.
        self._enable_picking()

    def _on_right_click(self, x: int, y: int) -> None:
        """Ein Rechtsklick wählt aus wie ein Linksklick und fragt nach dem Menü.

        §18.5 nennt das Kontextmenü am Merkmal den Ort für Weg 1: ein fremdes
        Modell wird angepasst, indem man auf die Stelle zeigt, die stört. Bis
        hierher zeigte ein Rechtsklick auf einen Körper gar nichts — das Menü
        gab es nur im Objektbaum, wo die Merkmale `hole_3` heißen.
        """
        point = self._world_at(x, y)
        if point is None:
            self.objectPicked.emit("")
            return
        self._select_at(point)
        self.contextMenuAt.emit(x, y)

    def _select_at(self, point: Vec3) -> None:
        """Was ein Klick auswählt: erst das Merkmal, dann der Körper darunter.

        Beides, und in dieser Reihenfolge. Ein Merkmal gehört einem Objekt, und
        der Baum kann es nur unter dessen Zeile zeigen — ohne die Auswahl des
        Körpers tat ein Klick auf eine Bohrung nichts, weil noch nichts
        ausgewählt war. Linksklick und Rechtsklick nehmen denselben Weg; das
        Menü fragt danach nur noch, was zur Auswahl passt (§18.5).
        """
        feature_id = self._feature_at(point)
        self.objectPicked.emit(self._object_at(point) or "")
        if feature_id is not None:
            self.select_feature(feature_id)
            self.featurePicked.emit(feature_id)

    def _world_at(self, x: int, y: int) -> Vec3 | None:
        """Der Punkt auf dem Körper unter einer Bildschirmposition.

        VTK zählt von unten, Qt von oben — umgerechnet wird beim Aufrufer, denn
        hier kommt die Position aus dem Interactor und ist schon in VTKs
        Zählung.

        Gepickt wird die **Zelle** und nicht der Punkt. Ein ``vtkPointPicker``
        trifft nur Eckpunkte: der Halter aus dem Beispielprojekt hat acht davon,
        und ein Klick mitten auf eine Fläche fand nichts. Auswählen,
        Kontextmenü am Merkmal (§18.5), Messen und Bemalen hingen alle daran und
        taten nichts — nachgestellt an der laufenden Anwendung, während Rad und
        Rechtsziehen die Kamera bewegten. Ein ``vtkCellPicker`` trifft das
        Dreieck und damit jede Stelle, auf die jemand zeigen kann.
        """
        if self.plotter is None:
            return None
        from vtkmodules.vtkRenderingCore import vtkCellPicker

        picker = vtkCellPicker()
        # Die Toleranz ist ein Anteil der Bilddiagonale; die Vorgabe von VTK
        # ist so klein, dass ein Klick an einer Kante wieder danebengeht.
        picker.SetTolerance(PICK_TOLERANCE)
        if not picker.Pick(float(x), float(y), 0.0, self.plotter.renderer):
            return None
        position = picker.GetPickPosition()
        return (float(position[0]), float(position[1]), float(position[2]))

    def _on_left_click(self, x: int, y: int) -> None:
        """Ein Linksklick, der keiner Kamerabewegung galt (§18.5).

        Der Weg ist derselbe wie beim Rechtsklick, nur ohne Menü danach: erst
        das Merkmal unter dem Zeiger, sonst der Körper, und ein Klick daneben
        hebt die Auswahl auf.
        """
        point = self._world_at(x, y)
        if point is None:
            self.objectPicked.emit("")
            return
        self._on_picked(point)

    def _enable_picking(self) -> None:
        """Nichts mehr zu tun — der eigene Stil löst das Picking selbst aus.

        Vorher stand hier ``plotter.enable_point_picking``. Das hat nie
        funktioniert und es auch nie gesagt: pyvista sucht sich den Renderer
        über ``GetInteractorStyle()._parent()``, also über seinen eigenen Stil,
        und Solidon setzt einen eigenen für die vier Navigationsschemata.
        Jeder Klick endete in einem ``AttributeError``, den pyvistaqt zu einer
        Warnung macht — im Fenster sah es aus, als käme der Klick nicht an, und
        genau so stand es in zwei Durchsichten.

        Die Methode bleibt als Ort für den Fall, dass doch wieder etwas beim
        Wechsel des Schemas einzuschalten ist; gerufen wird sie von dort.
        """
        return

    @property
    def navigation(self) -> NavigationScheme:
        return self._scheme


def _world_under(renderer: Any, x: int, y: int) -> tuple[float, float, float] | None:
    """Der Weltpunkt unter einer Bildschirmstelle, auf der Fokusebene.

    Auf der Fokusebene und nicht auf der Geometrie: gezoomt wird auch über
    leerem Hintergrund, und dort gäbe ein Picker nichts zurück.
    """
    camera = renderer.GetActiveCamera()
    renderer.SetWorldPoint(*camera.GetFocalPoint(), 1.0)
    renderer.WorldToDisplay()
    depth = renderer.GetDisplayPoint()[2]

    renderer.SetDisplayPoint(float(x), float(y), depth)
    renderer.DisplayToWorld()
    point = renderer.GetWorldPoint()
    if abs(point[3]) < EPS_GEOM:
        return None
    return (point[0] / point[3], point[1] / point[3], point[2] / point[3])


def _InteractorStyle(  # noqa: N802
    plotter: Any, scheme: NavigationScheme, on_context: Any = None, on_pick: Any = None
) -> Any:
    """Baut einen VTK-Interaktionsstil mit den Tasten des gewählten Schemas.

    ``on_pick`` bekommt einen Linksklick, der keiner Kamerabewegung galt. Das
    steht hier und nicht bei pyvista, und dafür gibt es einen Grund: dessen
    ``enable_point_picking`` sucht sich den Renderer über
    ``GetInteractorStyle()._parent()``, also über seinen **eigenen** Stil. Mit
    diesem hier scheiterte es bei jedem Klick an einem ``AttributeError``, den
    pyvistaqt zu einer Warnung macht — die Auswahl im Viewport hat deshalb nie
    funktioniert, und im Fenster sah es aus, als käme der Klick nicht an.
    """
    from vtkmodules.vtkInteractionStyle import vtkInteractorStyleTrackballCamera

    base = vtkInteractorStyleTrackballCamera

    class Style(base):  # type: ignore[misc, valid-type]
        def __init__(self) -> None:
            super().__init__()
            self.AddObserver("LeftButtonPressEvent", self._left_down)
            self.AddObserver("LeftButtonReleaseEvent", self._left_up)
            self.AddObserver("RightButtonPressEvent", self._right_down)
            self.AddObserver("RightButtonReleaseEvent", self._right_up)
            self.AddObserver("MouseWheelForwardEvent", self._wheel_in)
            self.AddObserver("MouseWheelBackwardEvent", self._wheel_out)
            self._right_at: tuple[int, int] | None = None
            """Wo die rechte Taste heruntergegangen ist. In jedem Schema tut
            Rechts auch etwas an der Kamera — das Menü darf nur aufgehen, wenn
            niemand gezogen hat."""
            self._left_at: tuple[int, int] | None = None
            """Dasselbe für links. In drei der vier Schemata dreht die linke
            Taste; ausgewählt wird deshalb, wo niemand gezogen hat, und nicht
            danach, welches Schema gerade gilt."""

        def _shift(self) -> bool:
            return bool(self.GetInteractor().GetShiftKey())

        def _position(self) -> tuple[int, int]:
            x, y = self.GetInteractor().GetEventPosition()
            return int(x), int(y)

        def _left_down(self, *_: Any) -> None:
            self._left_at = self._position()
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
            started, self._left_at = self._left_at, None
            if on_pick is None:
                return
            x, y = self._position()
            if is_click(started, (x, y)):
                on_pick(x, y)

        def _wheel_in(self, *_: Any) -> None:
            self._zoom_at_pointer(1.0 + WHEEL_STEP)

        def _wheel_out(self, *_: Any) -> None:
            self._zoom_at_pointer(1.0 / (1.0 + WHEEL_STEP))

        def _zoom_at_pointer(self, factor: float) -> None:
            """Zoomt auf die Stelle unter dem Zeiger, nicht auf die Bildmitte.

            VTKs Trackball-Stil dollyt entlang der Kamera-Achse — der Punkt
            unter dem Zeiger wandert dabei weg, und man zoomt an dem vorbei,
            was man ansehen wollte. Handbuch und Code-Kommentar behaupteten
            beide das Gegenteil; nachgemessen stimmte keines von beiden.

            Der Weg: den Weltpunkt unter dem Zeiger vorher merken, dollyn, ihn
            danach neu bestimmen und die Kamera um die Differenz verschieben.
            Damit bleibt genau dieser Punkt stehen, wo er war.
            """
            renderer = plotter.renderer
            camera = renderer.GetActiveCamera()
            x, y = self._position()

            before = _world_under(renderer, x, y)
            camera.Dolly(factor)
            renderer.ResetCameraClippingRange()
            after = _world_under(renderer, x, y)

            if before is not None and after is not None:
                shift = tuple(before[axis] - after[axis] for axis in range(3))
                position = camera.GetPosition()
                focus = camera.GetFocalPoint()
                camera.SetPosition(*(position[axis] + shift[axis] for axis in range(3)))
                camera.SetFocalPoint(*(focus[axis] + shift[axis] for axis in range(3)))
                renderer.ResetCameraClippingRange()
            plotter.render()

        def _right_down(self, *_: Any) -> None:
            self._right_at = self._position()
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
            started, self._right_at = self._right_at, None
            if on_context is None:
                return
            # Ein Zug hat die Kamera bewegt und meint sie; ein Klick meint das,
            # worauf er zeigt.
            x, y = self._position()
            if is_click(started, (x, y)):
                on_context(x, y)

    return Style()
