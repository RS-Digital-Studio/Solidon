"""Der Viewport (Bauplan §18, §2.9).

Kein Anzeigefenster, sondern das Prüfwerkzeug: Druckplatte und Bauraum in
echter Größe, Rückseiten eingefärbt, damit umgedrehte Normalen auffallen, und
drei Navigationsschemata, damit niemand seinen Slicer verlernen muss.

Die 3D-Ansicht braucht VTK. Lässt sich das auf einer Maschine nicht starten,
öffnet das Fenster trotzdem und sagt es — alles außer der Ansicht läuft weiter.
"""

from __future__ import annotations

import math
import os
import weakref
from typing import Any, Literal, cast

from PySide6.QtCore import QEvent, Qt, QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QLineEdit, QVBoxLayout, QWidget

from app.branding import ENVIRONMENT_PREFIX
from app.core.geom.measure import Measurement, MeasurementList, distance, snap, wall_thickness
from app.core.geom.mesh_ops import decimate
from app.core.geom.section import SectionPlane, cut
from app.core.geom.transform import (
    Axis,
    TransformSteps,
    along_normal,
    decompose_transform,
    snap_to_step,
)
from app.core.log import get_logger
from app.core.perceive.maps import AnalysisMap
from app.core.scene import EvaluationResult
from app.core.types import Feature, FeatureId, LayerInfo, ObjectId, Profile, Vec3
from app.core.units import (
    DISPLAY_UNITS,
    EPS_DISPLAY,
    EPS_GEOM,
    EPS_MATCH_MINIMUM,
    EPS_MATCH_RELATIVE,
)
from app.i18n import tr
from app.ui import cursors
from app.ui.labels import feature_label
from app.ui.palette import DIFF_PALETTES, ROLES, VIRIDIS, DiffPalette
from app.ui.scale_widget import ScaleHandle
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
#: Wo die Achsenanzeige sitzt, in Anteilen des Fensters: unten links, wo
#: keine Karte liegt — rechts steht der Prüfbericht, oben die Werkzeugzeile.
ORIENTATION_CORNER = (0.0, 0.0, 0.16, 0.24)

#: Die drei Achsenfarben. Gedämpft und nicht signalbunt: die Anzeige sagt,
#: wo oben ist, sie ist keine Warnung — und sie steht neben einem Modell,
#: dem sie nicht die Aufmerksamkeit nehmen darf.
AXIS_X = "#d4574e"
AXIS_Y = "#7fb069"
AXIS_Z = "#5b8fd4"

#: Die Beschriftung der Achsen. Sie steht auf dem Hintergrund des Viewports und
#: nicht auf einem eigenen Feld — schwarz, wie VTK sie vorgibt, ist im dunklen
#: Thema unlesbar, und weiß wäre es im hellen.
AXIS_LABEL_DARK = "#e9e6e1"
AXIS_LABEL_LIGHT = "#2b2a28"

SSAO_RADIUS = 2.0

#: Wie lange die Maus stehen muss, bevor unter ihr nach einem Merkmal gesucht
#: wird. Kurz genug, dass es sich sofort anfühlt, lang genug, dass ein Zug quer
#: übers Bild keine hundert Suchen auslöst.
HOVER_DELAY_MS = 90

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

#: Wie weit die Fläche des gewählten Merkmals über dem Körper liegt, als
#: Anteil der Szenengröße. Zwei Gründe, beide zwingend: ohne Abstand streiten
#: Merkmal und Körper um dieselbe Tiefe und das Bild flimmert, und für die
#: Anzeige wird dezimiert (§18.9) — das gröbere Netz darunter läge sonst
#: stellenweise davor.
FEATURE_PATCH_LIFT = 0.0015

#: Wie hoch der Kontaktschatten über der Platte liegt. Ohne diesen Abstand
#: streiten sich Schatten und Platte um dieselbe Tiefe, und das Bild flimmert
#: beim Drehen.
SHADOW_LIFT = 0.05

#: Farbe und Deckkraft des Kontaktschattens. Dunkler als die Platte, aber
#: nie schwarz: er soll den Ort zeigen, nicht ein Loch in die Platte
#: schneiden.
SHADOW_COLOUR = "#11151a"
SHADOW_OPACITY = 0.35

#: Wie weit der Schatten je Millimeter Höhe vom Betrachter weg läuft, und wie
#: weit dabei zur Seite.
#:
#: **Nicht in Weltkoordinaten, sondern zur Kamera.** Hier stand eine feste
#: Richtung (0,35 / 0,45) mit der Begründung, die Standardansicht komme von
#: vorn links und der Schatten trete deshalb hinter dem Teil hervor. Beides
#: war falsch: die eigene Iso-Vorgabe steht vorn **rechts**, und die Ansicht,
#: mit der die Anwendung startete, war ohnehin eine dritte — der Schatten fiel
#: dort mit 0,81 seiner Länge auf den Betrachter zu, also genau davor.
#:
#: Der eigentliche Grund liegt tiefer: pyvistas Lichtsatz hängt an der Kamera.
#: Ein Körper ist in jeder Ansicht von vorn beleuchtet, und eine feste
#: Weltrichtung für den Schatten passt deshalb zu **keinem** Blickwinkel. Die
#: Richtung folgt jetzt der Kamera (:func:`shadow_direction`), und damit tritt
#: er in jeder Ansicht hinter dem Teil hervor — was der alte Kommentar
#: versprach und keine Ansicht einlöste.
#:
#: Die Länge ist die alte: 0,57 mm Versatz je Millimeter Höhe.
SHADOW_REACH = 0.54
SHADOW_SIDE = 0.18

#: Ab wann für die Schattenhülle nur noch eine Stichprobe gerechnet wird.
#:
#: Die Zahl ist ein Kostendeckel, keine Genauigkeitsgrenze: darunter ist die
#: Hülle exakt und billig, darüber wäre sie teurer als das, was sie ersetzt.
#: Siehe :func:`_thinned_for_hull`.
SHADOW_HULL_POINTS = 4096

#: Die vierzehn Hauptrichtungen — sechs Achsen und acht Raumdiagonalen.
#:
#: In jeder davon wird der äußerste Punkt gesucht und behalten, egal wie fein
#: die Stichprobe ist. Damit überlebt jede Ecke eines kantigen Körpers das
#: Ausdünnen, und der Schatten bleibt so groß wie das Teil.
SUPPORT_DIRECTIONS: tuple[tuple[float, float, float], ...] = (
    (1.0, 0.0, 0.0),
    (-1.0, 0.0, 0.0),
    (0.0, 1.0, 0.0),
    (0.0, -1.0, 0.0),
    (0.0, 0.0, 1.0),
    (0.0, 0.0, -1.0),
    (1.0, 1.0, 1.0),
    (1.0, 1.0, -1.0),
    (1.0, -1.0, 1.0),
    (1.0, -1.0, -1.0),
    (-1.0, 1.0, 1.0),
    (-1.0, 1.0, -1.0),
    (-1.0, -1.0, 1.0),
    (-1.0, -1.0, -1.0),
)

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

#: Wie lange der Schichtschieber stehen muss, bevor die Körper an der neuen
#: Höhe gekappt werden. Der Schnitt ist echte Geometrie und kostet an einem
#: texturierten Netz um die Sekunde — kurz genug, dass er nach dem Loslassen
#: sofort wirkt, lang genug, dass er beim Fahren nie dazwischenkommt.
LAYER_REBUILD_DELAY_MS = 200

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


def shadow_direction(position: Any, focal_point: Any) -> tuple[float, float]:
    """Wohin der Schatten aus dieser Kamerastellung fällt (§18.6).

    Vom Betrachter weg und ein Stück nach rechts. Der Lichtsatz von pyvista
    hängt an der Kamera — ein Körper ist also in jeder Ansicht von vorn
    beleuchtet, und ein Schatten, der das nicht mitmacht, sieht in jeder
    Ansicht falsch aus. Er macht es jetzt mit.

    Steht die Kamera senkrecht darüber, gibt es kein Hinten. Dann fällt der
    Schatten nach hinten rechts, denn eine Draufsicht hat eine Oberkante, und
    die ist dort, wo bei jeder anderen Ansicht das Hinten liegt.

    Als eigene Funktion, damit die Rechnung ohne Plotter prüfbar bleibt.
    """
    import numpy as np

    forward = np.asarray(focal_point, dtype=float)[:2] - np.asarray(position, dtype=float)[:2]
    length = float(np.linalg.norm(forward))
    if length < EPS_GEOM:
        return (SHADOW_SIDE, SHADOW_REACH)
    forward /= length
    # Nach rechts im Bild: die Blickrichtung um 90 Grad gedreht.
    side = np.array([-forward[1], forward[0]])
    step = forward * SHADOW_REACH + side * SHADOW_SIDE
    return (float(step[0]), float(step[1]))


def _thinned_for_hull(points: Any) -> Any:
    """So viele Punkte, wie die Schattenhülle braucht — nicht mehr.

    Bei einem Quader ist die Hülle billiger als die Triangulierung, die sie
    ersetzt: acht Punkte statt Tausender. Bei einer feinen Kugel liegt **jeder**
    Punkt auf der Hülle, und die Rechnung kostete mehr als der alte Weg (59 ms
    gegen 33 bei zwanzigtausend Dreiecken). Ein Körper mit so vielen Punkten
    ist rund oder gescannt; für ihn genügt eine Stichprobe.

    Die Stichprobe hält die Form, die Stützpunkte halten die Ecken: was in
    einer der vierzehn Hauptrichtungen am weitesten außen liegt, kommt immer
    mit. Ohne sie fiele der Schatten eines gescannten Halters um Millimeter zu
    klein aus, weil die Stichprobe seine Ecken verfehlt.
    """
    import numpy as np

    if len(points) <= SHADOW_HULL_POINTS:
        return points
    step = len(points) // SHADOW_HULL_POINTS + 1
    corners = np.unique(np.argmax(points @ np.asarray(SUPPORT_DIRECTIONS).T, axis=0))
    return np.vstack((points[::step], points[corners]))


def shadow_points(points: Any, direction: tuple[float, float], ground: float = 0.0) -> Any:
    """Wohin die Punkte eines Körpers als Schatten fallen (§18.6).

    Jeder Punkt fällt entlang des Lichts auf die auffangende Fläche: der
    Versatz ist sein Abstand zu ihr mal der waagerechte Anteil der
    Lichtrichtung. Punkte unterhalb der Fläche werfen keinen Schatten nach
    vorn — ihr Abstand zählt als null, sonst zöge ein Teil, das zur Hälfte
    versunken ist, seinen Schatten in die falsche Richtung.

    ``ground`` ist die Höhe dieser Fläche. Null ist die Platte; steht ein
    Körper auf einem anderen, ist es dessen Oberkante — sonst rutschte der
    Schatten um die volle Bauhöhe weg und läge neben dem Körper, der ihn
    auffängt.

    Als eigene Funktion, damit die Rechnung ohne Plotter prüfbar bleibt.
    """
    import numpy as np

    grid = np.asarray(points, dtype=float)
    height = np.maximum(grid[:, 2] - ground, 0.0)
    return np.column_stack(
        (
            grid[:, 0] + height * direction[0],
            grid[:, 1] + height * direction[1],
            np.full(len(grid), ground),
        )
    )


def outline_of(points: Any) -> Any:
    """Der geordnete Umriss einer ebenen Punktwolke — oder ``None``.

    Die konvexe Hülle in zwei Dimensionen, gegen den Uhrzeigersinn. Sie ersetzt
    die frühere Triangulierung: gebraucht wird ein Rand, den sich beschneiden
    lässt, und den gibt Qhull geordnet heraus. Eine Triangulierung gibt Dreiecke
    in beliebiger Folge, und aus denen einen Rand zurückzugewinnen wäre Arbeit
    für ein Ergebnis, das hier schon vorliegt.
    """
    import numpy as np
    from scipy.spatial import ConvexHull, QhullError

    grid = np.asarray(points, dtype=float)[:, :2]
    if len(grid) < 3:
        return None
    try:
        return grid[ConvexHull(grid).vertices]
    except QhullError as problem:
        # Alle Punkte auf einer Linie: das ist kein Umriss, und ein Schatten
        # ohne Fläche ist keiner.
        _log.info("outline unavailable: %s", problem)
        return None


def _edge_crossing(start: Any, end: Any, corner: Any, edge: Any) -> Any:
    """Wo die Strecke von ``start`` nach ``end`` die Gerade durch ``corner``
    kreuzt."""
    import numpy as np

    along = end - start
    denominator = edge[0] * along[1] - edge[1] * along[0]
    if abs(denominator) < EPS_GEOM:
        return np.asarray(start, dtype=float)
    offset = corner - start
    share = (edge[0] * offset[1] - edge[1] * offset[0]) / denominator
    return start + share * along


def clip_polygon(polygon: Any, window: Any) -> Any:
    """Was von einem konvexen Polygon innerhalb eines zweiten übrig bleibt.

    Sutherland und Hodgman: gegen jede Kante des Fensters wird das Polygon
    einmal beschnitten, und was hinter einer Kante liegt, wird an ihr
    abgeschnitten statt weggelassen. Beide Polygone müssen konvex und gegen den
    Uhrzeigersinn geordnet sein — beides liefert :func:`outline_of`.

    Wozu: ein Schatten, der über die Kante seiner Fläche hinausläuft, liegt auf
    nichts. Bei aufgezogener Explosion oder einem Körper weit vom Ursprung war
    das ein dunkler Fleck auf blankem Hintergrund — sichtbar falsch, und der
    einzige Ort, an dem die Ansicht behauptete, es gebe dort Boden.

    Leer heraus heißt: der Schatten fällt ganz daneben. Dann wird keiner
    gezeichnet, und das ist die richtige Aussage.
    """
    import numpy as np

    current = np.asarray(polygon, dtype=float)
    frame = np.asarray(window, dtype=float)
    for index in range(len(frame)):
        if len(current) < 3:
            return np.empty((0, 2))
        corner = frame[index]
        edge = frame[(index + 1) % len(frame)] - corner
        inside = (
            edge[0] * (current[:, 1] - corner[1]) - edge[1] * (current[:, 0] - corner[0])
        ) >= -EPS_GEOM
        if inside.all():
            continue
        kept: list[Any] = []
        for position, point in enumerate(current):
            following = (position + 1) % len(current)
            if inside[position]:
                kept.append(point)
            if bool(inside[position]) != bool(inside[following]):
                kept.append(_edge_crossing(point, current[following], corner, edge))
        current = np.asarray(kept, dtype=float) if len(kept) >= 3 else np.empty((0, 2))
    return current


def bed_outline(width: float, depth: float) -> Any:
    """Die vier Ecken der Druckplatte, gegen den Uhrzeigersinn.

    Solidon rechnet um den Ursprung, die Platte liegt also mittig — dieselbe
    Annahme wie in :func:`bed_scale` und beim Zeichnen.
    """
    import numpy as np

    half_width, half_depth = width / 2.0, depth / 2.0
    return np.array(
        [
            [-half_width, -half_depth],
            [half_width, -half_depth],
            [half_width, half_depth],
            [-half_width, half_depth],
        ]
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


def moved_marks(points: Any, matrix: Any) -> Any:
    """Wohin Beschriftungspunkte unter der Matrix eines Zugs wandern.

    Die Buchstaben standen fest an der Startposition, und je weiter man zog,
    desto weiter lag das X von dem Pfeil weg, den es benennt — die zweite
    Kodierung (Regel 18) löste sich beim Benutzen von der ersten. Als eigene
    Funktion, weil die Rechnung das ist, was ein Test offscreen prüfen kann.
    """
    import numpy as np

    m = np.asarray(matrix, dtype=float)
    base = np.asarray(points, dtype=float)
    return base @ m[:3, :3].T + m[:3, 3]


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


class DragValueBar(QFrame):
    """Die Zahl zum Zug — lesbar während des Ziehens, tippbar statt zu zielen
    (§18.11 „Zahleneingabe während des Ziehens").

    Solange die Maus zieht, zeigt das Feld den Live-Wert. Sobald jemand eine
    Ziffer tippt, gehört der Zug der Tastatur: das Feld hört auf, dem Zeiger
    zu folgen, die Eingabetaste wendet genau die getippte Zahl an — ohne
    Rasterfang, denn wer tippt, meint es exakt —, und Esc verwirft den Zug.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dragValueBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(ROOMY, TIGHT, ROOMY, TIGHT)
        layout.setSpacing(TIGHT)

        self.label = QLabel("", self)
        self.value = QLineEdit(self)
        self.value.setFixedWidth(88)
        self.value.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.value.setToolTip(
            tr("Zahl tippen: die Eingabetaste übernimmt genau diesen Wert, Esc verwirft den Zug.")
        )
        self.unit = QLabel("", self)
        layout.addWidget(self.label)
        layout.addWidget(self.value)
        layout.addWidget(self.unit)

        self.typing = False
        """Ob die Tastatur den Zug übernommen hat — dann folgt das Feld nicht
        mehr dem Zeiger."""
        self.value.textEdited.connect(self._took_over)
        self.set_theme("dark")
        self.hide()

    def _took_over(self, _text: str) -> None:
        self.typing = True

    def set_theme(self, theme: str) -> None:
        """Dieselbe Zeichnung wie das Vorschauband — beides sind Aussagen über
        einen Zwischenstand, nicht über das Ergebnis."""
        colours = THEMES["light" if theme == "light" else "dark"]
        self.setStyleSheet(
            f"#dragValueBar {{ background: {colours['window']};"
            f" border: 1px dashed {colours['disabled']}; border-radius: 4px; }}"
            f"#dragValueBar QLabel {{ color: {colours['text']}; background: transparent; }}"
        )

    def follow(self, label: str, amount: float, unit: str, decimals: int) -> None:
        """Der Live-Wert des Zugs — solange niemand tippt."""
        self.label.setText(label)
        self.unit.setText(unit)
        if not self.typing:
            self.value.setText(f"{amount:.{decimals}f}".replace(".", ","))
        if not self.isVisible():
            self.show()
        self.adjustSize()
        self.place()

    def typed_value(self) -> float | None:
        """Die getippte Zahl — oder nichts, wenn dort keine steht."""
        try:
            return float(self.value.text().strip().replace(",", "."))
        except ValueError:
            return None

    def dismiss(self) -> None:
        """Der Zug ist vorbei — auf welche Art auch immer."""
        self.typing = False
        self.value.clearFocus()
        self.hide()

    def place(self) -> None:
        """Oben mittig, unterhalb des Vorschaubands, wenn eines steht."""
        parent = self.parentWidget()
        if parent is None:
            return
        top = BANNER_TOP
        banner = getattr(parent, "banner", None)
        if banner is not None and banner.isVisible():
            top = banner.geometry().bottom() + TIGHT
        self.move(max((parent.width() - self.width()) // 2, 0), top)


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
    scaleDragged = Signal(float)
    """Ein Zug am Skalierwürfel — trägt den Faktor (§18.11). Das Fenster
    macht daraus die Operation; die Ansicht ändert nie selbst Geometrie."""
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
    boneRequested = Signal(object)
    """Eine Stelle, an der ein Knochenpunkt gesetzt wird (§25).

    Derselbe Vertrag wie beim Formen und beim Bemalen: Die Ansicht meldet
    einen Ort, das Fenster macht daraus einen Knochen, und Geometrie ändert
    einzig die Operation."""
    sculptRequested = Signal(object)
    """Eine Stelle, an der ein Pinselzug gesetzt wird (§25).

    Derselbe Vertrag wie beim Bemalen und aus demselben Grund: Die Ansicht
    meldet einen Ort, das Fenster macht daraus einen Zug, und Geometrie ändert
    einzig die Operation (Regel 2). Was der Viewport währenddessen zeigt, ist
    eine Vorschau."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.plotter: Any | None = None
        self._actors: dict[ObjectId, Any] = {}
        self._frame_actors: list[Any] = []
        self._selected: ObjectId | None = None
        self._fitted_to: Literal["", "bed", "objects"] = ""
        """Worauf die Kamera zuletzt eingepasst wurde — auf nichts, auf den
        Bauraum oder auf die Körper. Wechselt der Zustand, wird einmal neu
        eingepasst; innerhalb desselben Zustands bleibt jeder Zoom stehen."""
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
        self._gizmo_label_data: Any | None = None
        """Die Punkte hinter den Buchstaben, als lebendes PolyData: wer sie
        setzt, bewegt die Beschriftung — so reisen die Buchstaben während
        des Zugs mit."""
        self._gizmo_label_base: Any | None = None
        """Die Startpositionen der Buchstaben, auf die jede Zug-Matrix
        angewandt wird."""
        self._face_actor: Any | None = None
        """Die Scheibe, an der der Gizmo hängt, wenn eine Fläche gewählt ist."""
        self._scale_handle: ScaleHandle | None = None
        """Der Würfel zum Skalieren (§18.11) — nur am Objekt-Gizmo. Eine
        Fläche kennt nur vor und zurück, sie hat keine Größe zu ändern."""
        self._drag_kind: str | None = None
        """Was gerade gezogen wird — ``move``, ``turn``, ``face`` oder
        ``scale``, ``None`` heißt kein Zug. Entscheidet, was eine getippte
        Zahl bedeutet (§18.11)."""
        self._drag_axis: Axis | None = None
        """Die Achse des laufenden Zugs, sobald sie sich gezeigt hat."""
        self._drag_normal: Vec3 | None = None
        """Die Flächennormale, wenn der Zug an einer Fläche hängt."""
        self._grid_step = 1.0
        self._angle_step = 15.0
        self._map: AnalysisMap | None = None
        self._map_object: ObjectId | None = None
        self._occlusion_applied = False
        self._edge_actors: list[Any] = []
        self._shadow_actors: list[Any] = []
        self._shadow_hulls: dict[ObjectId, Any] = {}
        """Je Körper die konvexe Hülle seiner Punkte, für den Schattenwurf.
        Einmal je Szenenaufbau gerechnet — ein Ansichtswechsel projiziert nur
        noch daraus (§18.6)."""
        self._shadow_ground: dict[ObjectId, tuple[float, float, Any]] = {}
        """Je Körper Unterkante, Oberkante und sein Umriss von oben. Damit
        steht fest, wer auf wem steht — und damit, welche Fläche den Schatten
        auffängt."""
        self._bed_extent: tuple[float, float] | None = None
        """Breite und Tiefe der Druckplatte, sobald ein Bauraum gezeigt wurde.
        Der Schatten wird an ihrer Kante geschnitten; ohne Bauraum gibt es
        nichts zu schneiden."""
        self._shadow_cast: tuple[float, float] = (SHADOW_SIDE, SHADOW_REACH)
        """Die Lichtrichtung, mit der die Schatten im Bild stehen. Sie folgt
        der Kamera; wer sie schon getroffen hat, zeichnet nicht neu."""
        self._edge_colour = "#4c5258"
        self._feature_overlay = False
        self._feature_actors: list[Any] = []
        self._selected_feature: FeatureId | None = None
        self._feature_patch: Any | None = None
        """Die Dreiecke des gewählten Merkmals, in der Auswahlfarbe über dem
        Körper. Ohne sie hieß „Bohrung gewählt", dass der ganze Körper
        aufleuchtet — die Auswahl zeigte das Objekt und nicht die Stelle."""
        self._layer_actors: list[Any] = []
        self._layer: LayerInfo | None = None
        self._layer_rebuild = QTimer(self)
        """Der Körperschnitt zum Schieber, aufgeschoben bis zur Ruhe: die
        Körper an der Schichthöhe zu kappen ist ein echter Geometrieschnitt
        und kostet an einem texturierten Netz um die Sekunde — je Schritt im
        Hauptthread wäre das die Blockade, die §2.8 ausschließt. Beim Fahren
        folgen nur die Konturen; der Schnitt kommt, sobald der Schieber
        stehen bleibt, und bis dahin bleibt die letzte Darstellung stehen."""
        self._layer_rebuild.setSingleShot(True)
        self._layer_rebuild.setInterval(LAYER_REBUILD_DELAY_MS)
        self._layer_rebuild.timeout.connect(lambda: self.show_scene(self._result))
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
        self._sculpting = False
        self._boning = False
        self._brush_radius = 0.0
        """Der Pinselradius in Millimetern, solange geformt wird."""
        self._brush_actor: Any = None
        """Der Ring, der ihn zeigt — als Weltmaß in der Szene und nicht am
        Zeiger: Ein Zeiger hat feste Punktgröße und weiß nichts von der Kamera,
        er behauptete beim ersten Zoom eine Größe, die er nicht mehr hat."""
        """§20: solange das an ist, sind Klicks Pinselstriche."""
        self._cursor_role = "select"
        """Welcher Zeiger gerade über dem Bild steht. Gemerkt, damit nicht bei
        jeder Mausbewegung derselbe neu gesetzt wird — Qt zeichnet ihn sonst
        jedes Mal neu, und das flackert auf langsamen Treibern."""
        self._dragging_role: str | None = None
        """Was die Kamera gerade tut, solange eine Taste unten ist. Schlägt
        jede andere Rolle: wer dreht, will nicht wissen, was unter dem Zeiger
        liegt."""
        self._hover_timer = QTimer(self)
        self._hover_timer.setSingleShot(True)
        self._hover_timer.setInterval(HOVER_DELAY_MS)
        self._hover_timer.timeout.connect(self._look_under_pointer)
        """Sucht das Merkmal unter dem Zeiger — erst, wenn die Maus steht.
        Bei jeder Bewegung zu suchen hieße, den Tiefenpuffer hunderte Male in
        der Sekunde zu lesen, und zwar im Qt-Hauptthread."""
        self._hover_at: tuple[int, int] | None = None
        """Wo die Maus zuletzt stand, in VTK-Koordinaten."""
        self._hover_feature = False
        """Ob unter dem Zeiger ein benanntes Merkmal liegt (§18.5)."""
        self._hidden: frozenset[ObjectId] = frozenset()
        """§18.8: was der Nutzer ausgeblendet hat. Ansicht, nicht Szene — die
        Körper werden weiter gerechnet, geprüft und exportiert."""
        self._display_cache: dict[tuple[ObjectId, int], Any] = {}
        """§18.9: die dezimierte Fassung des zuletzt gezeigten Körpers. Sie
        fließt nie in den Kern zurück."""

        self.banner = PreviewBanner(self)
        """Das Band über dem Bild, wenn eine Vorschau läuft."""
        self.drag_bar = DragValueBar(self)
        """Die Zahl zum Zug (§18.11): lesen beim Ziehen, tippen statt zielen."""
        self.drag_bar.value.installEventFilter(self)
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
        # Qt malt hier nichts, VTK malt alles.
        #
        # Das Fenster des Interactors ist ein natives OpenGL-Fenster
        # (``WA_PaintOnScreen``), und trotzdem stand ``WA_NoSystemBackground``
        # auf ``False``: Qt füllte den Bereich also mit dem Hintergrund seines
        # Stils, bevor VTK darin zeichnen konnte. Zusammen mit dem Stylesheet
        # am ``OverlayHost`` darüber ist das der Verdächtige für das Bild, in
        # dem nur die Achsenmarker stehen und der Körper beim Bewegen der
        # Kamera aufblitzt.
        self.plotter.interactor.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self._layout.addWidget(self.plotter.interactor)
        # Während eines Zugs gehören Ziffern dem Wertfeld, nicht VTK — der
        # Filter sitzt deshalb auf dem Fenster, das die Tasten bekommt.
        self.plotter.interactor.installEventFilter(self)
        # Ohne das kommt eine Mausbewegung erst, wenn eine Taste unten ist —
        # und der Zeiger wüsste nie, worüber er schwebt, sondern nur, worauf
        # jemand schon geklickt hat.
        self.plotter.interactor.setMouseTracking(True)
        self.plotter.interactor.setCursor(cursors.cursor(self._cursor_role, self))
        self._add_orientation_widget()
        self._apply_render_quality()
        self.set_theme("dark")
        # Schaltet das Picking gleich mit ein — ein Stilwechsel und der erste
        # Aufbau sind für die Ansicht dasselbe.
        self.set_navigation("slicer")
        self._watch_camera()
        # **Die eigene Iso, nicht die von pyvista.** Ohne diese Zeile erbte die
        # Anwendung pyvistas Stellung über (1, 1, 1) — und ihre eigene Vorgabe
        # aus `VIEW_DIRECTIONS` bekam nur zu sehen, wer „Isometrisch" im Menü
        # wählte. Wer das tat, sprang aus einer Ansicht in eine andere, obwohl
        # er die zu sehen glaubte, in der er stand.
        self.view_from("iso")

    def _watch_camera(self) -> None:
        """Am Ende jeder Kamerabewegung die Schatten nachziehen (§18.6).

        Am Interactor und nicht am Interaktionsstil: den Stil tauscht jeder
        Schemawechsel aus, und der Orientierungswürfel dreht die Kamera an ihm
        vorbei. ``EndInteractionEvent`` bekommt beides mit.

        Schwach gehalten wie bei :meth:`set_navigation` — VTK hält den
        Beobachter, und eine starke Referenz von dort auf den Viewport überlebt
        jedes Schließen.
        """
        if self.plotter is None:
            return
        weak = weakref.ref(self)

        def on_end(*_: Any) -> None:
            view = weak()
            if view is not None:
                view._redraw_shadows()

        self.plotter.interactor.AddObserver("EndInteractionEvent", on_end)

    # --- Darstellungsqualität (§18.1) -------------------------------------------

    def _add_orientation_widget(self, theme: str = "dark") -> None:
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
        # Die Schriftfarbe kommt aus dem Thema des Plotters — ``add_axes``
        # nimmt sie von dort und lässt sich daneben kein zweites Mal sagen.
        # VTKs Vorgabe ist Schwarz, und das ist auf dem dunklen Hintergrund,
        # mit dem die Anwendung startet, unlesbar.
        try:
            self.plotter.theme.font.color = (
                AXIS_LABEL_DARK if theme != "light" else AXIS_LABEL_LIGHT
            )
        except Exception as problem:  # pragma: no cover - hängt an pyvista
            _log.info("axis labels keep their colour: %s", problem)
        try:
            self.plotter.add_axes(
                viewport=ORIENTATION_CORNER,
                # Pfeile, keine Kugeln: ein kräftiger Schaft mit einer Spitze
                # darauf ist das, was jeder aus einem Konstruktionsprogramm
                # kennt. Die Werte sind aufeinander abgestimmt — ein dünner
                # Schaft mit dicker Spitze sieht aus wie ein Stecknadelkopf,
                # ein dicker mit kurzer Spitze wie ein abgesägter Balken.
                cone_radius=0.5,
                shaft_length=0.78,
                tip_length=0.28,
                line_width=3,
                x_color=AXIS_X,
                y_color=AXIS_Y,
                z_color=AXIS_Z,
                label_size=(0.3, 0.16),
                ambient=0.4,
            )
        except Exception as problem:  # pragma: no cover - hängt am Treiber
            _log.info("orientation widget unavailable: %s", problem)
            return

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

    def _shadow_direction(self) -> tuple[float, float]:
        """Die Lichtrichtung, die zur aktuellen Kamerastellung gehört."""
        if self.plotter is None:
            return (SHADOW_SIDE, SHADOW_REACH)
        camera = self.plotter.camera
        return shadow_direction(camera.position, camera.focal_point)

    def _shadow_hull_of(self, surface: Any) -> Any:
        """Die Punkte, aus denen ein Körper seinen Schatten wirft.

        Die konvexe Hülle in **drei** Dimensionen, und zwar einmal je Körper und
        Szenenaufbau. Sie hängt nicht an der Lichtrichtung: welcher Punkt den
        Umriss des Schattens bestimmt, wechselt mit ihr, aber es ist immer
        einer von diesen. Damit kostet ein Ansichtswechsel nur noch die
        Projektion und die ebene Hülle darüber — statt einer Triangulierung
        über jeden Punkt des Anzeigenetzes (gemessen: 31 ms bei zwanzigtausend
        Dreiecken, 127 ms bei zweiundachtzigtausend, je Körper).
        """
        import numpy as np
        from scipy.spatial import ConvexHull, QhullError

        points = _thinned_for_hull(np.asarray(surface.points, dtype=float))
        if len(points) < 4:
            return points if len(points) >= 3 else None
        try:
            return points[ConvexHull(points).vertices]
        except QhullError as problem:
            # Ein ebener oder entarteter Körper hat keine räumliche Hülle. Seine
            # Punkte sind dann ohnehin wenige — sie gehen unverändert weiter.
            _log.info("shadow hull unavailable: %s", problem)
            return points

    def _shadow_catchers(self, object_id: ObjectId) -> list[tuple[float, Any]]:
        """Die Flächen, die den Schatten dieses Körpers auffangen (§18.6).

        Immer die Platte, und dazu jeder Körper, dessen Oberkante nicht höher
        liegt als die Unterkante dieses hier. Ohne das fiel jeder Schatten auf
        die Platte, auch der eines Turms auf einer zwölf Millimeter hohen
        Grundplatte: er tauchte erst neben ihr auf, als Fleck ohne Verbindung
        zu dem, was ihn wirft.

        Beides zusammen ist kein Widerspruch. Licht, das an der Grundplatte
        vorbeigeht, trifft die Druckplatte — und weil das Stück auf der
        Druckplatte am Umriss der Grundplatte geschnitten wird, verdeckt diese
        genau den Teil, der sonst doppelt läge.

        Zurück kommt je Fläche ihre Höhe und ihr Umriss von oben; ``None`` als
        Umriss heißt „unbeschnitten" und tritt nur auf, wenn kein Bauraum
        gezeigt wurde — dann gibt es keine Kante, an der zu schneiden wäre.
        """
        mine = self._shadow_ground.get(object_id)
        catchers: list[tuple[float, Any]] = [
            (0.0, bed_outline(*self._bed_extent) if self._bed_extent is not None else None)
        ]
        if mine is None:
            return catchers
        floor = mine[0]
        for other, (_low, high, outline) in self._shadow_ground.items():
            if other == object_id or outline is None:
                continue
            if EPS_GEOM < high <= floor + EPS_GEOM:
                catchers.append((high, outline))
        return catchers

    def _shadow_outline_of(
        self,
        hull_points: Any,
        direction: tuple[float, float],
        ground: float = 0.0,
        window: Any = None,
    ) -> Any:
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
        Bild war er schlicht nicht da. Entlang der Lichtrichtung geworfen tritt
        er seitlich hervor, und weil sein Versatz mit der Höhe wächst,
        beantwortet er nebenbei die Frage, die er beantworten soll: ein
        schwebendes Teil hat seinen Schatten weiter weg.

        Die konvexe Hülle ist bewusst gröber als der echte Umriss — ein Schatten
        zeigt den Ort, nicht die Form; wer die Form sucht, dreht die Ansicht.

        ``window`` ist der Rand der auffangenden Fläche. Was darüber hinausläuft,
        wird abgeschnitten: ein Schatten neben der Platte lag auf blankem
        Hintergrund und behauptete Boden, wo keiner ist.
        """
        import numpy as np
        import pyvista as pv

        if hull_points is None or len(hull_points) < 3:
            return None
        cast = shadow_points(hull_points, direction, ground)
        outline = outline_of(cast)
        if outline is None:
            return None
        if window is not None:
            outline = clip_polygon(outline, window)
            if len(outline) < 3:
                return None
        corners = np.column_stack((outline, np.full(len(outline), ground + SHADOW_LIFT)))
        # Ein einziges konvexes Vieleck statt einer Triangulierung: die Punkte
        # liegen bereits in der Reihenfolge des Randes, und VTK zeichnet es als
        # Fläche. Delaunay darüber wäre dieselbe Fläche aus mehr Zellen.
        return pv.PolyData(corners, faces=np.hstack(([len(corners)], np.arange(len(corners)))))

    # --- scene ------------------------------------------------------------------

    def show_preview_mesh(self, object_id: str, mesh: Any) -> None:
        """Einen Körper zeigen, wie er nach dem laufenden Werkzeug aussähe.

        **Nur die Punkte, kein Neuaufbau** — das ist der Weg, den P16.2
        gemessen hat: Ein Pinselzug trifft zehntausend von vier Millionen
        Eckpunkten, und die Vollkopie kostet das Vierzigfache. Ein neuer Actor
        je Zug wäre noch teurer und würde nebenbei Auswahl, Kanten und Schatten
        neu aufbauen.

        Die Dreiecke bleiben dieselben; passt die Punktzahl nicht, ist das
        keine Vorschau derselben Sache, und es passiert nichts.
        """
        import numpy as np

        actor = self._actors.get(object_id)
        if actor is None or self.plotter is None:
            return
        data = actor.mapper.dataset
        points = np.asarray(mesh.raw.vertices, dtype=float)
        if len(points) != data.n_points:
            return
        data.points = points
        data.Modified()
        self.plotter.render()

    def clear_preview_mesh(self) -> None:
        """Zurück zu dem, was wirklich in der Szene steht.

        Über den vollen Neuaufbau und nicht über gemerkte Punkte: Was gezeigt
        wurde, war eine Vorschau, und der Dokumentzustand ist die einzige
        Wahrheit darüber, was danach zu sehen ist.
        """
        self.show_scene(self._result)

    def show_scene(self, result: EvaluationResult | None) -> None:
        """Baut die Ansicht aus der letzten vollständigen Auswertung neu (§15.3)."""
        # Ein voller Neuaufbau schneidet an der aktuellen Schichthöhe mit —
        # ein noch ausstehender Schnitt vom Schieber wäre danach derselbe
        # noch einmal.
        self._layer_rebuild.stop()
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
        # Die Hüllen gehören zu den Körpern, die gerade weggeräumt wurden. Ein
        # Rest davon hieße: ein gelöschter Körper wirft beim nächsten Drehen
        # weiter seinen Schatten.
        self._shadow_hulls.clear()
        self._shadow_ground.clear()
        self._shadow_cast = self._shadow_direction()
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
            self._draw()
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
            self._remember_shadow(surface, object_id)

        # Erst jetzt: ein Schatten fällt auf die Fläche, auf der sein Körper
        # steht, und welche das ist, weiß nur die vollständige Szene.
        self._place_shadows(self._shadow_direction())
        self.select(self._selected)
        self._redraw_features()
        self._redraw_layer()
        self._centre_rotation()
        self._render_now()

    def _centre_rotation(self) -> None:
        """Gedreht wird um das, was man ansieht (§2.9).

        VTK dreht um den Fokuspunkt der Kamera, und der stand auf dem
        Weltursprung: ein Teil, das neben dem Ursprung liegt — und das tut
        jedes heruntergeladene Modell —, wanderte beim Drehen im Bogen durch
        das Bild, statt sich zu drehen. Der Fokus wandert deshalb in die Mitte
        der **Körper**.

        Nicht in die Mitte dessen, was der Renderer sieht: dazu gehören der
        Bauraumrahmen und die Druckplatte. Der Rahmen ist 250 mm hoch, das
        Teil 40 — die Mitte lag hundert Millimeter über dem Modell, die Kamera
        rückte dorthin mit, und im Bild stand die Kulisse, während das Teil
        unten aus der Ecke ragte. Genau das zeigte das Handbuchbild des
        Hauptfensters. Dieselbe Quelle wie beim Einpassen (`_object_bounds`),
        aus demselben Grund.

        Die Blickrichtung und der Abstand bleiben dabei erhalten: die Kamera
        rückt mit, statt sich zu verdrehen. Wer gerade von vorn schaut, schaut
        danach immer noch von vorn.
        """
        if self.plotter is None:
            return
        renderer = getattr(self.plotter, "renderer", None)
        if renderer is None:
            return
        centre = self.rotation_centre()
        if centre is None:
            return
        camera = renderer.GetActiveCamera()
        focus = camera.GetFocalPoint()
        if all(abs(centre[i] - focus[i]) < EPS_DISPLAY for i in range(3)):
            return
        position = camera.GetPosition()
        camera.SetFocalPoint(*centre)
        camera.SetPosition(*(position[i] + centre[i] - focus[i] for i in range(3)))
        renderer.ResetCameraClippingRange()

    def rotation_centre(self) -> Vec3 | None:
        """Der Punkt, um den gedreht wird — die Mitte der Körper, oder nichts.

        Als eigene Auskunft, damit die Regel ohne Plotter prüfbar bleibt:
        offscreen gibt es keinen, und ein Test, der sich dort überspringt,
        prüft nie etwas.
        """
        bounds = self._object_bounds()
        if bounds is None:
            return None
        return (
            (bounds[0] + bounds[1]) / 2.0,
            (bounds[2] + bounds[3]) / 2.0,
            (bounds[4] + bounds[5]) / 2.0,
        )

    def _render_now(self) -> None:
        """Zeichnen nach dem Aufbau einer Szene.

        Der Clipping-Bereich davor ist keine Zugabe: die Szene hat gerade ihre
        Ausdehnung geändert, und die alten Ebenen können den neuen Körper
        wegschneiden.
        """
        if self.plotter is None:
            return
        renderer = getattr(self.plotter, "renderer", None)
        if renderer is not None:
            renderer.ResetCameraClippingRange()
        self._draw()

    def _draw(self) -> None:
        """Die eine Stelle, an der die Ansicht neu gezeichnet wird.

        Alles, was etwas geändert hat, geht hier durch — ein Weg statt
        sechzehn. Gezeichnet wird einmal; wenn ein einziger Durchgang nicht
        ankommt, ist das ein Fehler weiter unten und wird dort behoben, nicht
        hier durch Wiederholen verdeckt.
        """
        if self.plotter is None:
            return
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

    def _remember_shadow(self, surface: Any, object_id: ObjectId) -> None:
        """Was dieser Körper zum Schattenwurf beiträgt — geworfen wird später.

        Getrennt vom Setzen, weil ein Schatten wissen muss, worauf er fällt:
        welcher Körper unter welchem steht, steht erst fest, wenn alle
        gezeichnet sind.
        """
        if self.plotter is None or not self.contact_shadows:
            return
        hull = self._shadow_hull_of(surface)
        self._shadow_hulls[object_id] = hull
        if hull is None or len(hull) < 3:
            return

        import numpy as np

        heights = np.asarray(hull, dtype=float)[:, 2]
        self._shadow_ground[object_id] = (
            float(heights.min()),
            float(heights.max()),
            outline_of(hull),
        )

    def _place_shadows(self, direction: tuple[float, float]) -> None:
        """Die Schatten aller Körper aus den gemerkten Hüllen setzen."""
        if self.plotter is None:
            return
        for object_id, hull in self._shadow_hulls.items():
            for index, (ground, window) in enumerate(self._shadow_catchers(object_id)):
                outline = self._shadow_outline_of(hull, direction, ground, window)
                if outline is None:
                    continue
                self._shadow_actors.append(
                    self.plotter.add_mesh(
                        outline,
                        color=SHADOW_COLOUR,
                        opacity=SHADOW_OPACITY,
                        lighting=False,
                        name=f"shadow:{object_id}:{index}",
                        render=False,
                        pickable=False,
                    )
                )

    def _redraw_shadows(self) -> None:
        """Die Schatten der neuen Kamerastellung anpassen (§18.6).

        Am Ende einer Drehung, nicht während ihr: die Hüllen liegen bereit, die
        Projektion darüber kostet Bruchteile einer Millisekunde — aber sie je
        Bild zu rechnen wäre Arbeit für eine Zwischenstellung, die niemand
        ansieht.
        """
        # Läuft eine Analysekarte, steht hier ohnehin nichts: `_draw_shadow`
        # legt dann keine Hülle ab, und `show_scene` räumt die alten weg.
        if self.plotter is None or not self._shadow_hulls:
            return
        direction = self._shadow_direction()
        if math.dist(self._shadow_cast, direction) < EPS_GEOM:
            return
        self._shadow_cast = direction
        for actor in self._shadow_actors:
            self.plotter.remove_actor(actor, render=False)
        self._shadow_actors.clear()
        self._place_shadows(direction)
        self._draw()

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
        self._apply_selection_colour()
        # Der Griff folgt der Auswahl (§18.11): wer ein anderes Objekt wählt,
        # will es auch bewegen — nicht das vorige. Und weil `show_scene` hier
        # durchkommt, hängt der Griff nach jeder Auswertung am neuen Actor
        # statt am entfernten der letzten.
        self.set_gizmo(self._gizmo_wanted)
        self._draw()

    def _apply_selection_colour(self) -> None:
        """Welcher Körper die Auswahlfarbe trägt — und wann keiner.

        Ist ein **Merkmal** gewählt, bleibt der Körper grau: die Auswahlfarbe
        liegt dann auf der Bohrung, und derselbe Ton am ganzen Teil hieße,
        dass die Stelle keine Auskunft mehr trägt. Dass der Körper trotzdem
        ausgewählt ist, steht im Objektbaum und in der Statusleiste — dieselbe
        Ausnahme, die für einen Körper unter einer Analysekarte längst gilt
        (§19.1).
        """
        if self.plotter is None:
            return
        highlighted = self.highlighted_object()
        for identifier, actor in self._actors.items():
            if self._map is not None and identifier == self._map_object:
                # Eine Karte besitzt die Farbe ihres Körpers; die Auswahl zeigt sich
                # stattdessen im Objektbaum und in der Statusleiste (§19.1).
                continue
            actor.prop.color = SELECTED_COLOUR if identifier == highlighted else self._object_colour

    def show_build_volume(self, profile: Profile) -> None:
        """Das Bett als Raster in echter Größe, der Bauraum als Eckwinkel
        (§18.6).

        **Kein Aufruf hier setzt die Kamera.** Der Bauraum ist Kulisse, und
        pyvista passt bei der ersten Netzfläche einer leeren Szene von selbst
        ein — das machte jedes Einpassen auf die Körper wieder zunichte, weil
        die Kulisse danach gezeichnet wurde.
        """
        width, depth, height = profile.printer.build_volume
        # Gemerkt, weil der Kontaktschatten an dieser Kante geschnitten wird —
        # und weil ``_fit_once_for`` daran erkennt, ob es auf einer leeren Szene
        # überhaupt etwas einzupassen gibt. Vor dem Plotter-Zweig, aus demselben
        # Grund wie dort: dass ein Bauraum gilt, ist eine Aussage über die
        # Szene und nicht über VTK.
        self._bed_extent = (width, depth)
        if self.plotter is None:
            return
        import pyvista as pv

        for actor in self._frame_actors:
            self.plotter.remove_actor(actor, render=False)
        self._frame_actors.clear()

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
        self._draw()

    # --- theme (§19.3) ----------------------------------------------------------

    def set_theme(self, theme: str) -> None:
        """Hintergrund-, Körper- und Bettfarben folgen dem Anwendungsthema."""
        colours = viewport_colours(theme)  # type: ignore[arg-type]
        self._object_colour = colours["object"]
        self._bed_colour = colours["bed"]
        self._bed_surface = colours["bed_surface"]
        self._edge_colour = colours["edge"]
        self.banner.set_theme(theme)
        self.drag_bar.set_theme(theme)
        if self.plotter is None:
            return
        self.plotter.set_background(colours["bottom"], top=colours["top"])
        # Die Achsenanzeige trägt eine Schriftfarbe und muss deshalb mit dem
        # Thema wechseln — eine schwarze Beschriftung auf dunklem Grund ist
        # keine Auskunft.
        self._add_orientation_widget(theme)
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
        self._draw()

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
        self._update_cursor()

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

    def set_boning(self, active: bool) -> None:
        """Macht aus Klicks Knochenpunkte (§25).

        Ein eigener Zustand neben dem Formen, obwohl beide dasselbe Picking
        benutzen: Wer ein Skelett setzt, will keinen Zug malen, und ein Modus,
        der beides gleichzeitig kann, kann keines von beidem verlässlich.
        """
        self._boning = active
        self._update_cursor()

    def set_sculpting(self, active: bool, radius: float = 0.0) -> None:
        """Macht aus Klicks Pinselzüge (§25).

        Dasselbe Picking wie beim Bemalen und beim Messen; was sich ändert,
        ist, wer den Punkt bekommt. Solange die Sitzung läuft, wird gemalt und
        nicht gewählt — sonst hätte jeder Zug nebenbei die Auswahl geändert.
        """
        self._sculpting = active
        self._brush_radius = radius if active else 0.0
        if not active:
            self._hide_brush()
        self._update_cursor()

    def set_brush_radius(self, radius: float) -> None:
        """Der Ring folgt dem Regler, nicht erst dem nächsten Zug."""
        self._brush_radius = radius
        if self._sculpting:
            self._draw_brush()

    def _hide_brush(self) -> None:
        if self._brush_actor is not None and self.plotter is not None:
            self.plotter.remove_actor(self._brush_actor, render=True)
        self._brush_actor = None

    def _draw_brush(self) -> None:
        """Den Ring dorthin legen, wo der Pinsel greifen würde.

        Flach auf die Fläche, nicht in die Bildebene: Ein Kreis, der immer zum
        Betrachter zeigt, sagt nichts darüber, wie schräg die Stelle unter ihm
        steht — und schräg ist beim Formen der Normalfall.
        """
        import numpy as np
        import pyvista as pv

        if self.plotter is None or self._hover_at is None or self._brush_radius <= 0.0:
            return
        x, y = self._hover_at
        point = _world_under(self.plotter.renderer, x, y)
        if point is None:
            self._hide_brush()
            return
        mesh = self._nearest_mesh(point)
        if mesh is None:
            self._hide_brush()
            return
        vertices = np.asarray(mesh.raw.vertices, dtype=float)
        nearest = int(np.argmin(np.linalg.norm(vertices - np.asarray(point), axis=1)))
        normal = np.asarray(mesh.raw.vertex_normals, dtype=float)[nearest]
        ring = _ring_points(np.asarray(point, dtype=float), normal, self._brush_radius)
        line = pv.PolyData(ring)
        line.lines = np.hstack([[len(ring) + 1], np.arange(len(ring)), [0]])
        self._hide_brush()
        self._brush_actor = self.plotter.add_mesh(
            line, color=SELECTED_COLOUR, line_width=2, render=False, reset_camera=False
        )
        self.plotter.render()

    def set_painting(self, active: bool) -> None:
        """Macht aus Klicks Pinselstriche (§20).

        Dasselbe Picking, das auch das Messen benutzt; was sich ändert, ist, wer
        den Punkt bekommt. Ein eigener Modus statt einer Zusatztaste: das Modell
        zu bemalen, wenn jemand es drehen wollte, ist die Art Überraschung, die
        ein Undo behebt und Vertrauen nicht übersteht.
        """
        self._painting = active
        self._update_cursor()

    # --- der Zeiger (§19.3) -----------------------------------------------------

    def _update_cursor(self) -> None:
        """Setzt den Zeiger, der zum jetzigen Zustand gehört.

        Eine Stelle für alle Auslöser — Werkzeugwechsel, Kamerazug, Merkmal
        unter der Maus. Verteilt auf die Aufrufer wäre jeder Pfad für sich
        richtig und das Ergebnis trotzdem falsch: Wer beim Loslassen den
        Auswahlzeiger setzt, überschreibt damit den Pinsel.
        """
        role = self._dragging_role or self._resting_role()
        if role == self._cursor_role:
            return
        self._cursor_role = role
        if self.plotter is None:
            return
        self.plotter.interactor.setCursor(cursors.cursor(role, self))

    def _resting_role(self) -> str:
        """Was ein Klick jetzt täte, wenn die Kamera stillsteht.

        Die Reihenfolge ist die der Vorrangigkeit im Klick selbst
        (:meth:`_on_picked`): erst Formen, dann Pinsel, dann Messen, dann das
        Merkmal darunter. Ein Zeiger, der eine andere Reihenfolge behauptet als
        die Behandlung, lügt genau dann, wenn zwei Werkzeuge zugleich anstehen.
        """
        if self._boning:
            # Derselbe Zeiger wie beim Formen: Beide setzen einen Punkt auf der
            # Fläche, und ein dritter Ring wäre eine Unterscheidung ohne
            # Unterschied.
            return "sculpt"
        if self._sculpting:
            return "sculpt"
        if self._painting:
            return "paint"
        if self._measure_mode != "off":
            return "measure"
        return "feature" if self._hover_feature else "select"

    def set_drag_cursor(self, role: str | None) -> None:
        """Meldet, was die Kamera gerade tut — vom Interaktionsstil gerufen.

        ``None`` heißt: Taste losgelassen, zurück zum Ruhezustand.
        """
        self._dragging_role = role
        if role is not None:
            # Während eines Zugs ist gleichgültig, was unter dem Zeiger liegt,
            # und die Suche danach wäre die teuerste Stelle im Zug.
            self._hover_timer.stop()
            self._hover_feature = False
        self._update_cursor()

    def _look_under_pointer(self) -> None:
        """Sucht nach der Ruhepause, ob unter dem Zeiger ein Merkmal liegt.

        Über den Tiefenpuffer (:func:`_world_under`) und nicht über einen
        Aktor-Pick: Der Tiefenwert steht ohnehin im Bild, ein Pick würde die
        Szene erneut durchlaufen.
        """
        if self.plotter is None or self._hover_at is None or self._dragging_role:
            return
        x, y = self._hover_at
        point = _world_under(self.plotter.renderer, x, y)
        if self._sculpting:
            # Beim Formen ist unter dem Zeiger nie ein Merkmal gemeint,
            # sondern immer eine Stelle. Der Ring zeigt sie; die Suche nach
            # Merkmalen bliebe hier nur teuer.
            self._draw_brush()
            return
        found = point is not None and self._feature_at(point) is not None
        if found != self._hover_feature:
            self._hover_feature = found
            self._update_cursor()

    def _note_pointer(self, position: Any) -> None:
        """Merkt sich, wo die Maus steht, und stößt die Suche neu an.

        VTK zählt seine Y-Achse von unten, Qt von oben — ohne die Umrechnung
        findet die Suche das Merkmal am gespiegelten Ort, was in der Mitte des
        Bildes zufällig oft genug stimmt, um lange nicht aufzufallen.
        """
        if self.plotter is None:
            return
        height = self.plotter.interactor.height()
        self._hover_at = (int(position.x()), int(height - position.y()))
        self._hover_timer.start()

    def _forget_pointer(self) -> None:
        """Die Maus hat das Bild verlassen."""
        self._hover_timer.stop()
        self._hover_at = None
        if self._hover_feature:
            self._hover_feature = False
            self._update_cursor()

    def _on_picked(self, point: Any) -> None:
        picked = (float(point[0]), float(point[1]), float(point[2]))
        if self._boning:
            self.boneRequested.emit(picked)
            return
        if self._sculpting:
            self.sculptRequested.emit(picked)
            return
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
        self._draw()

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
        self._draw()

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
        self._draw()

    def select_feature(self, feature_id: FeatureId | None) -> None:
        self._selected_feature = feature_id
        self._redraw_features()
        # Der Körper gibt die Auswahlfarbe an das Merkmal ab und holt sie
        # zurück, sobald keines mehr gewählt ist.
        self._apply_selection_colour()
        if self.plotter is not None:
            # Auch der Griff wechselt mit: eine gewählte Fläche bekommt ihn
            # auf die Fläche, eine abgewählte gibt ihn ans Objekt zurück
            # (§18.11) — nicht erst beim nächsten Umschalten.
            self.set_gizmo(self._gizmo_wanted)
            self._draw()

    @property
    def selected_feature(self) -> FeatureId | None:
        return self._selected_feature

    def highlighted_object(self) -> ObjectId | None:
        """Welcher Körper die Auswahlfarbe trägt — keiner, solange ein Merkmal
        gewählt ist (§19.1).

        Als eigene Auskunft und nicht als Zustand des Plotters, aus demselben
        Grund wie bei :meth:`gizmo_target`: offscreen gibt es keinen, und ein
        Test, der sich dort überspringt, prüft nie etwas.
        """
        if self._selected_feature is not None:
            return None
        return self._selected

    def highlighted_faces(self) -> tuple[int, ...]:
        """Die Dreiecke, die als gewähltes Merkmal aufleuchten (§18.5).

        Leer heißt: nichts hervorzuheben — kein Merkmal gewählt, der Körper
        ausgeblendet, oder ein Merkmal ohne zugeordnete Dreiecke wie eine
        Kante aus dem exakten Kern. Gezählt wird im Netz der Szene, nicht im
        dezimierten Anzeigenetz (§18.9).
        """
        if self._selected_feature is None or self._result is None or self._selected is None:
            return ()
        entry = self._result.scene.objects.get(self._selected)
        if entry is None or not entry.visible or self._selected in self._hidden:
            return ()
        feature = entry.features.get(self._selected_feature)
        raw = getattr(entry.mesh, "raw", None)
        if feature is None or raw is None:
            return ()
        return tuple(index for index in feature.face_indices if 0 <= index < len(raw.faces))

    def _features_of_selection(self) -> dict[FeatureId, Feature]:
        if self._result is None or self._selected is None:
            return {}
        entry = self._result.scene.objects.get(self._selected)
        return dict(entry.features) if entry is not None else {}

    def _redraw_features(self) -> None:
        if self.plotter is None:
            return
        self._redraw_feature_patch()
        for actor in self._feature_actors:
            self.plotter.remove_actor(actor, render=False)
        self._feature_actors.clear()
        # Ohne Überlagerung bleibt das **gewählte** Merkmal beschriftet: seine
        # Fläche leuchtet in der Auswahlfarbe, und eine Aussage allein über
        # Farbe wäre genau die, die Regel 18 verbietet.
        shown = (
            self._features_of_selection()
            if self._feature_overlay
            else {
                feature_id: feature
                for feature_id, feature in self._features_of_selection().items()
                if feature_id == self._selected_feature
            }
        )
        if not shown:
            return

        import numpy as np

        points: list[list[float]] = []
        labels: list[str] = []
        for feature_id, feature in shown.items():
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

    def _redraw_feature_patch(self) -> None:
        """Die Dreiecke des gewählten Merkmals in der Auswahlfarbe (§18.5).

        Ein Klick auf eine Bohrung wählt zweierlei aus: den Körper und die
        Stelle. Zu sehen war nur das Erste — der ganze Körper nahm die
        Auswahlfarbe an, und die Bohrung, die gemeint war, unterschied sich
        von der Wand daneben durch nichts. Gefärbt wird deshalb, was das
        Merkmal ausmacht: die Dreiecke, die die Erkennung ihm zugeordnet hat
        (``face_indices``).

        Gegen das **Originalnetz**, nicht gegen das gezeigte: dezimiert und
        geschnitten wird für die Anzeige (§18.9), die Indizes des Merkmals
        zählen aber im Netz der Szene. Ein paar hundert Dreiecke kosten
        nichts, und die Abweichung zum dezimierten Körper darunter fängt der
        Versatz entlang der Flächennormalen ab.
        """
        if self.plotter is None:
            return
        if self._feature_patch is not None:
            self.plotter.remove_actor(self._feature_patch, render=False)
            self._feature_patch = None
        highlighted = self.highlighted_faces()
        if not highlighted or self._result is None or self._selected is None:
            return
        entry = self._result.scene.objects.get(self._selected)
        raw = getattr(entry.mesh, "raw", None) if entry is not None else None
        if entry is None or raw is None:
            return

        import numpy as np
        import pyvista as pv

        chosen = np.asarray(highlighted, dtype=np.int64)
        triangles = np.asarray(raw.faces, dtype=np.int64)[chosen]
        normals = np.asarray(raw.face_normals, dtype=float)[chosen]
        # Je Dreieck eigene Punkte: die Fläche wird entlang **ihrer** Normalen
        # angehoben, und geteilte Eckpunkte würden das über die Kante hinaus
        # in den Nachbarn ziehen.
        corners = np.asarray(raw.vertices, dtype=float)[triangles.ravel()]
        lift = max(self._scene_size() * FEATURE_PATCH_LIFT, EPS_GEOM)
        corners += np.repeat(normals, 3, axis=0) * lift
        corners += self._exploded(entry, self._result)
        count = len(triangles)
        faces = np.hstack(
            [np.full((count, 1), 3, dtype=np.int64), np.arange(count * 3).reshape(count, 3)]
        ).ravel()
        self._feature_patch = self.plotter.add_mesh(
            pv.PolyData(corners, faces),
            color=SELECTED_COLOUR,
            # Beidseitig: die Wand einer Bohrung sieht man von innen, und ihre
            # Normale zeigt zur Achse — ohne das wäre die gewählte Bohrung
            # genau aus der Richtung unsichtbar, aus der man sie ansieht.
            backface_params={"color": SELECTED_COLOUR},
            lighting=False,
            name="feature-patch",
            render=False,
            reset_camera=False,
            pickable=False,
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
            self._draw()

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
            self._draw()

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
            self._draw()

    def resizeEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Name
        super().resizeEvent(event)
        self.banner.place()
        self.drag_bar.place()

    # --- layer analysis (§18.10) ------------------------------------------------

    def set_layer(self, layer: LayerInfo | None) -> None:
        """Zeigt die Konturen einer Schicht. Geometrie, keine
        Werkzeugwege (§18.10).
        """
        was = self._layer
        self._layer = layer
        # Die Körper werden neu gebaut, weil sie jetzt anders geschnitten sind
        # — aber nicht bei jedem Schritt: der Schnitt ist echte Geometrie und
        # kostet an einem texturierten Netz um die Sekunde. Sofort geschnitten
        # wird nur beim Ein- und Ausschalten des Werkzeugs; beim Fahren folgen
        # die Konturen sofort, und die Körper folgen, sobald der Schieber
        # stehen bleibt.
        if (was is None) != (layer is None):
            self._layer_rebuild.stop()
            self.show_scene(self._result)
        elif was is not None and layer is not None and was.z != layer.z:
            self._layer_rebuild.start()
        self._redraw_layer()
        if self.plotter is not None:
            self._draw()

    def _redraw_layer(self) -> None:
        if self.plotter is None:
            return
        for actor in self._layer_actors:
            self.plotter.remove_actor(actor, render=False)
        self._layer_actors.clear()
        layer = self._layer
        if layer is None:
            return

        # Ein Actor je Rolle, nicht je Ring: eine texturierte Schicht hat
        # tausende Konturen, und ebenso viele einzelne ``add_lines``-Aufrufe
        # machten aus einem Schieberschritt Sekunden — VTK zahlt je Actor,
        # nicht je Linie.
        contours = [
            ring for polygon in layer.contours for ring in (polygon.outline, *polygon.holes)
        ]
        self._add_rings(contours, layer.z, LAYER_COLOUR, "layer")
        self._add_rings(
            [polygon.outline for polygon in layer.islands],
            layer.z,
            ISLAND_COLOUR,
            "island",
            width=3,
        )
        self._add_rings(
            [polygon.outline for polygon in layer.overhangs],
            layer.z,
            OVERHANG_COLOUR,
            "overhang",
            width=3,
        )

    def _add_rings(
        self, rings: list[Any], z: float, colour: str, name: str, width: int = 2
    ) -> None:
        if self.plotter is None:
            return
        import numpy as np

        pieces = []
        for ring in rings:
            if len(ring) < 2:
                continue
            flat = np.asarray(ring, dtype=float)
            points = np.column_stack([flat, np.full(len(flat), z)])
            # add_lines will Punktpaare; ein geschlossener Ring ist jeder Punkt
            # zweimal, bis auf die Enden — und Ringe hängen nicht aneinander.
            pieces.append(np.repeat(points, 2, axis=0)[1:-1])
        if not pieces:
            return
        self._layer_actors.append(
            self.plotter.add_lines(np.vstack(pieces), color=colour, width=width, name=name)
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
            interact_callback=self._on_gizmo_interacted,
            scale=GIZMO_SCALE,
            line_radius=GIZMO_LINE_RADIUS,
        )
        if face is None:
            # Das dritte Drittel von §18.11: pyvistas Widget verschiebt und
            # dreht, der Würfel skaliert. Nur am Objekt — eine Fläche kennt
            # nur vor und zurück.
            self._scale_handle = ScaleHandle(
                self.plotter,
                actor,
                colour=MEASURE_COLOUR,
                release_callback=self._on_scale_released,
                interact_callback=self._on_scale_interacted,
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
        if self._scale_handle is not None:
            self._scale_handle.remove()
            self._scale_handle = None
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
        import pyvista as pv

        length = float(actor.GetLength()) * GIZMO_SCALE * 1.15
        centre = (float(actor.center[0]), float(actor.center[1]), float(actor.center[2]))
        marks = gizmo_labels(centre, length)
        if self._scale_handle is not None:
            # Das S hinter dem Würfel, im selben Abstand wie X, Y und Z
            # hinter ihren Spitzen — ein Griffsatz, eine Schreibweise.
            grip = self._scale_handle.grip_position
            marks.append(
                (
                    (
                        centre[0] + (grip[0] - centre[0]) * GIZMO_LABEL_GAP,
                        centre[1] + (grip[1] - centre[1]) * GIZMO_LABEL_GAP,
                        centre[2] + (grip[2] - centre[2]) * GIZMO_LABEL_GAP,
                    ),
                    "S",
                )
            )
        # Als lebendes PolyData mit dem Textarray darin, nicht als Punktliste:
        # nur so geht das Dataset selbst in die Label-Pipeline ein (eine
        # Punktliste kopiert pyvista), und nur dann folgt die Beschriftung,
        # wenn `_on_gizmo_interacted` die Punkte während des Zugs versetzt.
        base = np.asarray([point for point, _text in marks], dtype=float)
        data = pv.PolyData(base.copy())
        # pyvistas Stubs kennen nur Zahlenarrays; Textarrays nimmt das
        # Dataset trotzdem — als vtkStringArray, genau was die Labels wollen.
        data["labels"] = [text for _point, text in marks]  # type: ignore[type-var]
        self._gizmo_label_base = base
        self._gizmo_label_data = data
        self._gizmo_labels = self.plotter.add_point_labels(
            data,
            "labels",
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
        self._gizmo_label_data = None
        self._gizmo_label_base = None

    def _on_gizmo_interacted(self, matrix: Any) -> None:
        """Während des Zugs reisen Achsbuchstaben und Zahl mit (Regel 18, §18.11).

        pyvista bewegt Griff und Körper, aber Beschriftung und Wertfeld sind
        unsere: die Buchstaben standen fest an der Startposition, und die Zahl
        zum Zug gab es gar nicht — wie weit man gezogen hatte, stand erst
        hinterher im Verlauf. Gerendert wird nicht hier: pyvistas Move-Callback
        rendert am Ende ohnehin, und die Matrix hinkt seinem Ereignis um eines
        hinterher — beim Loslassen stellt das Neuanhängen alles exakt.
        """
        if self._gizmo_label_data is not None and self._gizmo_label_base is not None:
            self._gizmo_label_data.points = moved_marks(self._gizmo_label_base, matrix)

        import numpy as np

        steps = decompose_transform(np.asarray(matrix, dtype=float))
        face = self.gizmo_target()
        if face is not None:
            normal = face.params["normal"]
            self._drag_kind = "face"
            self._drag_normal = (float(normal[0]), float(normal[1]), float(normal[2]))
            self.drag_bar.follow(
                tr("Fläche"),
                along_normal(steps.offset, self._drag_normal),
                DISPLAY_UNITS[0],
                2,
            )
        elif steps.turns and steps.axis is not None:
            self._drag_kind = "turn"
            self._drag_axis = steps.axis
            self.drag_bar.follow(f"{tr('Winkel')} {steps.axis.upper()}", steps.angle, "°", 1)
        elif steps.moves:
            index = max(range(3), key=lambda axis: abs(steps.offset[axis]))
            dominant: Axis = ("x", "y", "z")[index]
            self._drag_kind = "move"
            self._drag_axis = dominant
            self.drag_bar.follow(dominant.upper(), steps.offset[index], DISPLAY_UNITS[0], 2)
        # Solange sich nichts bewegt hat, gibt es keine Achse und keine Zahl —
        # das Feld erscheint mit dem ersten sichtbaren Stück des Zugs.

    def _on_scale_interacted(self, factor: float) -> None:
        """Der Zwischenstand am Skalierwürfel — die Zahl zum Zug (§18.11)."""
        self._drag_kind = "scale"
        self.drag_bar.follow(tr("Faktor"), factor, "", 3)

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

        Und der Navigationsstil wird wiederhergestellt: pyvistas Widget schaltet
        beim Greifen auf seinen Trackball-Stil um und stellt beim Loslassen
        *seinen* Standard wieder her, nicht unseren — ohne diesen Aufruf waren
        nach dem ersten Zug Auswahl-Klick, Kontextmenü und das gewählte Schema
        verschwunden.
        """
        if self.drag_bar.typing:
            # Der Zug gehört der Tastatur (§18.11): das Loslassen wendet
            # nichts an, die Eingabetaste wird es tun. Griff frisch, Stil
            # zurück — das Feld bleibt mit der getippten Zahl stehen.
            self.set_navigation(self._scheme)
            self.set_gizmo(self._gizmo_wanted)
            return

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
            self._end_drag()
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
        self._end_drag()

    def _on_scale_released(self, factor: float) -> None:
        """Ein Zug am Skalierwürfel endet als Operation (§18.11, §2.1).

        Derselbe Dreischritt wie beim Loslassen des Gizmos, aus denselben
        Gründen: die Zahl melden, den Navigationsstil zurückholen, den Griff
        frisch anhängen — die Vorschau am alten Actor verschwindet mit ihm.
        """
        if self.drag_bar.typing:
            self.set_navigation(self._scheme)
            self.set_gizmo(self._gizmo_wanted)
            return
        if abs(factor - 1.0) > 1e-4:
            self.scaleDragged.emit(float(factor))
        self._end_drag()

    def _end_drag(self) -> None:
        """Der Zug ist vorbei: Zahl weg, Zustand weg, Stil zurück, Griff frisch."""
        self._drag_kind = None
        self._drag_axis = None
        self._drag_normal = None
        self.drag_bar.dismiss()
        self.set_navigation(self._scheme)
        self.set_gizmo(self._gizmo_wanted)

    def _apply_typed(self) -> None:
        """Die Eingabetaste wendet die getippte Zahl an — genau die (§18.11).

        Ohne Rasterfang, denn wer tippt, meint es exakt. Eine Zahl, mit der
        sich nichts anfangen lässt, bleibt markiert im Feld stehen — angewandt
        wird dann nichts.
        """
        value = self.drag_bar.typed_value()
        kind = self._drag_kind
        if value is None or kind is None or (kind == "scale" and value <= 0.0):
            self.drag_bar.value.selectAll()
            return
        if kind == "face" and self._drag_normal is not None:
            if abs(value) > EPS_DISPLAY:
                self.faceDragged.emit(self._drag_normal, float(value))
        elif kind == "turn" and self._drag_axis is not None:
            if abs(value) > EPS_DISPLAY:
                self.transformDragged.emit(TransformSteps(axis=self._drag_axis, angle=float(value)))
        elif kind == "move" and self._drag_axis is not None:
            if abs(value) > EPS_DISPLAY:
                index = ("x", "y", "z").index(self._drag_axis)
                offset = [0.0, 0.0, 0.0]
                offset[index] = float(value)
                self.transformDragged.emit(TransformSteps(offset=(offset[0], offset[1], offset[2])))
        elif kind == "scale" and abs(value - 1.0) > 1e-4:
            self.scaleDragged.emit(float(value))
        self._end_drag()

    def eventFilter(self, watched: Any, event: Any) -> bool:  # noqa: N802 — Qt-Name
        """Während eines Zugs gehören Ziffern dem Wertfeld, nicht VTK (§18.11).

        Der Filter sitzt auf dem Interactor-Fenster und auf dem Feld selbst:
        die erste Ziffer holt den Fokus ins Feld, Eingabetaste und Esc wirken
        von beiden Seiten. VTKs eigene Tastenkürzel bleiben unangetastet —
        geschluckt wird nur, was zum Zug gehört, und nur solange einer läuft.
        """
        kind = event.type()
        # Der Zeiger zuerst, und immer: Er hängt an der Mausbewegung und nicht
        # daran, ob gerade ein Zug läuft. Nichts davon wird geschluckt — VTK
        # bekommt jede dieser Bewegungen weiterhin.
        if kind == QEvent.Type.MouseMove:
            self._note_pointer(event.position())
        elif kind == QEvent.Type.Leave:
            self._forget_pointer()
        elif kind == QEvent.Type.Enter:
            self._update_cursor()

        if self._drag_kind is None or kind != QEvent.Type.KeyPress:
            return False
        key = event.key()
        if key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self._apply_typed()
            return True
        if key == Qt.Key.Key_Escape:
            # Esc verwirft den Zug: nichts angewandt, das Bild zurück zur Szene.
            self._end_drag()
            return True
        if watched is self.drag_bar.value:
            return False
        text = str(event.text())
        if text and (text.isdigit() or text in "-,."):
            self.drag_bar.typing = True
            self.drag_bar.value.setText(text)
            self.drag_bar.value.setFocus()
            self.drag_bar.value.setCursorPosition(len(text))
            return True
        return False

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

        **Die leere Szene hat auch etwas zu zeigen: den Bauraum.** Ohne diesen
        Zweig stand die Kamera nach *Neues Projekt* auf (1, -1, 0,8) — also
        anderthalb Millimeter vom Ursprung entfernt in einem 220er Bauraum. Die
        Druckplatte lag außerhalb des Bildes, und der erste Blick eines neuen
        Nutzers ging auf eine leere Fläche. Der Aufruf ist derselbe, den *Alles
        einpassen* macht; ohne Körper nimmt er den Bauraum.

        **Nur wenn es den Bauraum schon gibt.** Das Fenster baut die Ansicht
        einmal auf, bevor ein Profil gilt — dort wäre nichts einzupassen, und
        der Zustand stünde danach trotzdem auf „erledigt". Genau so gemessen:
        ``_fitted_to`` sagte „bed", und die Kamera stand weiter auf (1, -1, 0,8).
        """
        if result is not None and result.scene.objects:
            wanted = "objects"
        elif self._bed_extent is not None:
            wanted = "bed"
        else:
            return
        if wanted != self._fitted_to:
            self.reset_camera()
            self._fitted_to = wanted  # type: ignore[assignment]

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
        self._draw()

    def view_from(self, direction: str) -> None:
        """Eine der sieben Kameravorgaben (§18.1)."""
        if self.plotter is None or direction not in VIEW_DIRECTIONS:
            return
        position, up = VIEW_DIRECTIONS[direction]
        self.plotter.camera_position = [position, (0.0, 0.0, 0.0), up]
        self.plotter.reset_camera()
        self._redraw_shadows()

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

        def on_cursor(role: str | None) -> None:
            view = weak()
            if view is not None:
                view.set_drag_cursor(role)

        style = _InteractorStyle(self.plotter, scheme, on_context, on_pick, on_cursor)
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


def _ring_points(centre: Any, normal: Any, radius: float, count: int = 48) -> Any:
    """Ein Kreis um ``centre``, flach auf der Fläche mit dieser Normale.

    Flach und nicht in der Bildebene: Ein Ring, der immer zum Betrachter zeigt,
    sagt nichts darüber, wie schräg die Stelle unter ihm steht — und schräg ist
    beim Formen der Normalfall.

    Als eigene Funktion, damit die Rechnung ohne Plotter prüfbar bleibt.
    """
    import numpy as np

    axis = np.asarray(normal, dtype=float)
    length = float(np.linalg.norm(axis))
    axis = axis / length if length > EPS_GEOM else np.array([0.0, 0.0, 1.0])
    # Irgendein Vektor, der nicht parallel zur Normale liegt: die Achse, in der
    # sie am schwächsten ist. Ein fester Startvektor wäre genau dort entartet,
    # wo er parallel zu ihr steht.
    other = np.zeros(3)
    other[int(np.argmin(np.abs(axis)))] = 1.0
    first = np.cross(axis, other)
    first /= np.linalg.norm(first)
    second = np.cross(axis, first)
    angles = np.linspace(0.0, 2.0 * np.pi, count, endpoint=False)
    return (
        np.asarray(centre, dtype=float)
        + radius * (np.outer(np.cos(angles), first) + np.outer(np.sin(angles), second))
        # Ein Stück über der Fläche, sonst kämpft der Ring mit ihr um den
        # Tiefenpuffer und zerfällt beim Drehen in Striche.
        + axis * radius * 0.02
    )


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
    plotter: Any,
    scheme: NavigationScheme,
    on_context: Any = None,
    on_pick: Any = None,
    on_cursor: Any = None,
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

        def _tell(self, role: str | None) -> None:
            """Was die Kamera jetzt tut — der Zeiger hängt daran."""
            if on_cursor is not None:
                on_cursor(role)

        def _left_down(self, *_: Any) -> None:
            self._left_at = self._position()
            if scheme == "slicer":
                # Left selects; panning is shift plus drag.
                if self._shift():
                    self.StartPan()
                    self._tell("panning")
                return
            if scheme == "blender" and self._shift():
                self.StartPan()
                self._tell("panning")
                return
            self.StartRotate()
            self._tell("rotate")

        def _left_up(self, *_: Any) -> None:
            self.EndPan()
            self.EndRotate()
            self._tell(None)
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
                self._tell("zoom")
                return
            if scheme == "orbit":
                # Links dreht, rechts schiebt — die Aufteilung von Bambu
                # Studio, OrcaSlicer und PrusaSlicer.
                self.StartPan()
                self._tell("panning")
                return
            self.StartRotate()
            self._tell("rotate")

        def _right_up(self, *_: Any) -> None:
            self.EndRotate()
            self.EndDolly()
            self.EndPan()
            self._tell(None)
            started, self._right_at = self._right_at, None
            if on_context is None:
                return
            # Ein Zug hat die Kamera bewegt und meint sie; ein Klick meint das,
            # worauf er zeigt.
            x, y = self._position()
            if is_click(started, (x, y)):
                on_context(x, y)

    return Style()
