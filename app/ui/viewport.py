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
from collections.abc import Callable, Sequence
from contextlib import suppress
from itertools import pairwise
from typing import Any, Final, Literal, NamedTuple, cast

from PySide6.QtCore import QEvent, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QKeySequence
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from app.branding import ENVIRONMENT_PREFIX
from app.core.geom.measure import (
    Measurement,
    MeasurementList,
    angle_between,
    distance,
    snap,
    wall_thickness,
)
from app.core.geom.mesh import distance_to_triangles, hull_planes, ray_span_in_hull
from app.core.geom.mesh_ops import decimate
from app.core.geom.section import SectionPlane, cut, plane_patch
from app.core.geom.transform import (
    Axis,
    TransformSteps,
    along_normal,
    decompose_transform,
    snap_to_step,
)
from app.core.log import get_logger
from app.core.perceive.features import CURVATURE_LIMIT
from app.core.perceive.maps import AnalysisMap
from app.core.scene import EvaluationResult
from app.core.sketch.planes import axis_hit, image_normal, ray_hit, to_plane, to_world
from app.core.sketch.profile import SketchCurve
from app.core.types import (
    Feature,
    FeatureId,
    LayerInfo,
    ObjectId,
    PlaneFrame,
    Profile,
    Vec3,
)
from app.core.units import (
    EPS_DISPLAY,
    EPS_GEOM,
    EPS_MATCH_MINIMUM,
    EPS_MATCH_RELATIVE,
    LengthUnit,
    decimals_for,
    from_mm,
    to_mm,
)
from app.i18n import tr
from app.ui import cursors
from app.ui.icons import icon
from app.ui.labels import display_unit, feature_label, length, localised
from app.ui.leash import weak_slot
from app.ui.palette import (
    DIFF_PALETTES,
    LAYER_WIDTHS,
    ROLES,
    VIRIDIS,
    DiffPalette,
    readable_on,
    text_colour,
)
from app.ui.scale_widget import ScaleHandle
from app.ui.style import ROOMY, TIGHT
from app.ui.theme import THEMES, slot_colour, viewport_colours

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
#: Wie groß die Achsenanzeige ist und wie weit sie von der Ecke absteht — in
#: Bildpunkten, nicht in Anteilen des Fensters.
#:
#: **Anteile waren der Fehler.** Der Wert stand auf ``(0.0, 0.0, 0.16, 0.24)``
#: mit der Begründung, unten links liege keine Karte. Dort liegt die linke
#: Spalte: Objekte, Parameter und Verlauf reichen bis 69 Bildpunkte über den
#: unteren Rand. Die Anzeige war 189 auf 158 Punkte groß und lag damit fast
#: vollständig dahinter; zu sehen war allein die Spitze des roten X-Pfeils,
#: die unter der Karte hervorschaute — auf jedem Bildschirmfoto, in jeder
#: Sprache, und sie sieht aus wie ein Grafikfehler.
#:
#: Ein fester Anteil kann das nicht lösen: Die Karte hält einen Abstand in
#: Bildpunkten, der Anteil daran ändert sich mit jeder Fenstergröße. Gerechnet
#: wird deshalb aus Punkten (:func:`orientation_corner`), und
#: :meth:`Viewport.resizeEvent` zieht nach.
#: Die Größe ist an den Streifen gebunden, den die Karten über dem unteren
#: Rand frei lassen — er misst rund 63 Punkte, und darin muss die Anzeige samt
#: Abstand Platz haben. Wächst die Werkzeugzeile, etwa weil jemand seine
#: Systemschrift größer stellt, schrumpft der Streifen; dann wird
#: ``test_the_axis_marker_does_not_hide_behind_a_card`` rot und sagt, um wie
#: viele Punkte. Das ist der Zweck dieses Tests.
ORIENTATION_SIZE = 52
ORIENTATION_MARGIN = 4


#: Wie viel Luft eine Einpassung um die Zeichnung lässt. Ohne Rand liegt
#: die äußerste Linie genau auf dem Bildrand, und ein Maß daran steht
#: halb außerhalb.
FIT_ROOM = 1.15


def camera_for_span(
    frame: PlaneFrame,
    centre: tuple[float, float],
    span: tuple[float, float],
    distance: float,
    aspect: float,
) -> tuple[Vec3, Vec3, Vec3, float]:
    """Kamerastellung und Ausschnitt für einen Bereich der Zeichenebene.

    Gibt Position, Brennpunkt, Oben-Richtung und ``parallel_scale`` zurück —
    alles, was :meth:`Viewport.show_span_on_plane` setzt, und keines davon dort
    gerechnet: Hinter der Plotter-Wache läuft offscreen nichts, und ein Test
    dahinter besteht, weil er nichts tut. Dieselbe Aufteilung wie bei
    :func:`camera_for_plane`, :func:`bore_span` und :func:`shadow_points`
    (Konzept „Skizze im Raum", Entscheidung G).

    ``aspect`` ist Höhe durch Breite des Bildes. ``parallel_scale`` ist die
    halbe sichtbare **Höhe**; eine breite Zeichnung muss deshalb über die Höhe
    hineingerechnet werden, sonst steht sie seitlich heraus und das Einpassen
    hätte seinen Namen nicht verdient.

    **Der Versatz geht gegen den Brennpunkt der Ebene, nicht gegen den
    Weltursprung.** ``camera_for_plane`` stellt die Kamera über
    ``frame.origin``; wer stattdessen (0, 0, 0) abzieht, addiert diesen
    Ursprung ein zweites Mal und lässt die Kamera schräg blicken. Auf der
    Grundebene ist beides dasselbe — dort liegt der Ursprung im Nullpunkt, und
    genau deshalb fällt es dort nicht auf.
    """
    world = to_world(frame, centre)
    position, focus, up = camera_for_plane(frame, distance)
    offset = tuple(p - f for p, f in zip(position, focus, strict=True))
    needed = max(span[1] / 2.0, (span[0] / 2.0) * aspect)
    return (
        (world[0] + offset[0], world[1] + offset[1], world[2] + offset[2]),
        world,
        up,
        needed * FIT_ROOM,
    )


def camera_for_plane(frame: PlaneFrame, distance: float = 1.0) -> tuple[Vec3, Vec3, Vec3]:
    """Die Kamerastellung, die senkrecht auf eine Zeichenebene sieht (§30.1).

    Position, Blickpunkt und Oben — in der Reihenfolge, die
    ``plotter.camera_position`` erwartet. Die achte Kameravorgabe neben den
    sieben festen aus :data:`VIEW_DIRECTIONS`, nur dass sie nicht in einer
    Tabelle steht, sondern aus dem Rahmen gerechnet wird: Eine Skizzenebene
    kann auf jeder planaren Fläche eines Körpers liegen und beliebig geneigt
    sein.

    **Oben ist die zweite Rahmenachse**, und das ist keine willkürliche Wahl.
    Sie ist dieselbe Achse, die im Zeichenblatt nach oben zeigt; jede andere
    drehte die Skizze beim Betreten des Modus um einen Winkel, den niemand
    erklären kann. Für die XY-Ebene fällt sie mit der vorhandenen Draufsicht
    zusammen — ``VIEW_DIRECTIONS["top"]`` hat ebenfalls ``(0, 1, 0)`` —, und
    das ist die Probe darauf, dass hier nichts verdreht ankommt.

    ``distance`` ist die Entfernung vom Ursprung. Sie entscheidet nichts,
    solange der Aufrufer danach ``reset_camera()`` ruft (so hält es
    :meth:`Viewport.view_from`); sie steht hier, damit die Richtung nicht von
    einer Länge null abhängt.

    **Gestanden wird auf der Bildnormalen, nicht auf der Normalen** — und der
    Unterschied kostet ein spiegelverkehrtes Bild. ``frame.normal`` ist die
    Richtung, in die *extrudiert* wird; bei ``plane:xz`` zeigt sie nach hinten,
    weil man von vorn zeichnet und nach hinten aufzieht. Eine Kamera dort
    stünde hinter der Zeichenebene, und die erste Achse liefe im Bild nach
    links. Für die beiden rechtshändigen Grundebenen und für jede Fläche eines
    Körpers sind beide Richtungen gleich; sie unterscheiden sich genau an der
    einen Stelle, an der es auffällt.

    Der erste Entwurf nahm die Normale und war gegen Flächen-Rahmen und gegen
    ``plane:xy`` geprüft — die zwei Fälle, in denen der Unterschied nicht
    sichtbar wird.

    Eine freie Funktion und keine Methode: Offscreen gibt es keinen Plotter,
    und was hinter dieser Wache liegt, läuft in der Suite nie. Die Rechnung
    davor zu trennen ist der einzige Weg, sie gegen Zahlen zu prüfen —
    dieselbe Aufteilung wie bei :func:`bore_span` und :func:`shadow_points`.
    """
    towards = image_normal(frame)
    position = (
        frame.origin[0] + distance * towards[0],
        frame.origin[1] + distance * towards[1],
        frame.origin[2] + distance * towards[2],
    )
    return position, frame.origin, frame.y_axis


def occluded_view_shift(parallel_scale: float, height: int, bottom: int) -> float:
    """Weltmaß, das den Bildmittelpunkt über einer unteren Karte zentriert.

    ``parallel_scale`` ist die halbe sichtbare Höhe. Eine Karte von ``bottom``
    Bildpunkten verschiebt die Mitte der freien Fläche um ihre halbe Höhe;
    die beiden Halbierungen kürzen sich bei der Umrechnung ins Weltmaß. Das
    Vorzeichen bleibt erhalten, damit dieselbe Rechnung die Verschiebung beim
    Verlassen des Modus zurücknimmt.
    """
    if height <= 0 or parallel_scale <= 0.0:
        return 0.0
    return float(bottom) * parallel_scale / float(height)


#: Wie weit die Kamera im Skizzenmodus mindestens von der Ebene wegsteht, in mm.
#:
#: Zweihundert: So viel Zeichenfläche sieht man dann etwa, und das ist die
#: Größenordnung eines Druckbetts — wer ohne Modell zu zeichnen beginnt (Weg 2),
#: fängt in diesem Rahmen an. Die Zahl greift **nur**, wenn die Kamera noch nie
#: eingepasst wurde; sobald ein Teil in der Szene liegt, gilt der Abstand, den
#: der Nutzer eingestellt hat.
LEAST_PLANE_DISTANCE = 200.0

#: Ab welcher Kantenlänge das Bild groß genug ist, um daran zu messen.
#:
#: Beim Aufbau meldet Qt für ein Widget ohne fertiges Layout **100 mal 30** — das
#: ist sein Startwert und kein Bild. ``pixels_per_mm`` rechnete daran 0,28
#: Bildpunkte je Millimeter aus, was ein Raster von 100 mm ergab; da der Fang
#: seit dem 24.08.2026 dieselbe Zahl nimmt, landete jeder Klick auf demselben
#: Rasterpunkt. Gemessen: drei Klicks, dreimal (0 | 0).
#:
#: Zweihundert, weil darunter kein Ausschnitt steht, in dem man zeichnet — und
#: weil der Startwert mit 100 sicher darunter liegt. Wer sein Fenster wirklich
#: so klein zieht, bekommt den Rückfallwert statt einer absurden Zahl.
LEAST_VIEW_PIXELS = 200

#: Der Maßstab, der gilt, wenn keiner zu messen ist — Bildpunkte je Millimeter.
#:
#: Dieselbe Zahl, die die Zeichenfläche als Startwert führt
#: (``sketch_editor.START_SCALE``). Sie steht hier noch einmal und wird nicht
#: importiert: Der Viewport kennt den Skizzeneditor nicht, und eine
#: Abhängigkeit in diese Richtung wäre teuer erkauft für einen Rückfallwert,
#: der nur greift, wenn es gar kein Bild gibt.
FALLBACK_SCALE = 4.0

#: Wie viele Rasterlinien einer Zeichenebene je Richtung höchstens entstehen.
#:
#: Zweihundert nach jeder Seite sind vierhundertein Linien je Achse und über
#: achthundert Segmente zusammen — mehr als jede Zeichnung braucht, und die
#: Grenze greift ohnehin erst bei einem Verhältnis von Ausdehnung zu
#: Rasterweite über zweihundert. Sie steht hier nicht als Geschmacksfrage,
#: sondern weil ``reach / step`` aus zwei freien Zahlen kommt: Ein Millimeter
#: Raster über einem Meter Ebene wären zweitausend Linien, gezeichnet in einem
#: Bild, in dem sie als Fläche ankommen.
MOST_GRID_LINES = 200

#: Die halbe Diagonale der Fangmarke, in **Bildpunkten**.
#:
#: In Bildpunkten und nicht in Millimetern, und das hat erst das Bild gesagt:
#: Der erste Anlauf koppelte sie an die Rasterweite (ein Drittel davon), was
#: bei 10 mm Raster gut aussah und bei 2 mm ein Kreuz von zwei Bildpunkten
#: ergab — vorhanden, gemessen richtig, und im Fenster kaum zu finden.
#: Eine Marke ist ein Zeiger; sie soll bei jedem Zoom und jeder Rasterweite
#: gleich gut zu sehen sein.
#:
#: Zehn und nicht acht: Der Fangradius der Zeichenfläche ist acht Bildpunkte,
#: und eine Marke, die genau so groß ist wie der Bereich, in dem sie fängt,
#: sieht aus wie seine Berandung. Etwas größer ist sie ein Zeichen.
CURSOR_PIXELS = 10.0

#: Länge des sichtbaren Ziehgriffs in Bildpunkten.
#:
#: Er bleibt beim Zoomen gleich groß wie ein Werkzeuggriff. Achtunddreißig
#: Bildpunkte sind lang genug, dass Pfeilspitze und Kreuz nicht im Umriss
#: verschwinden, aber kurz genug, um neben einem kleinen Profil zu bleiben.
PULL_HANDLE_PIXELS = 38.0

#: Greifweite des ausdrücklichen Pfeil-/Kreuzgriffs in Bildpunkten.
#:
#: Der Griff ist eine primäre Handlung und keine dünne Kante. Vierzehn
#: Bildpunkte geben ihm eine fehlertolerante Trefferfläche, ohne die
#: Zeichnung daneben mitzunehmen. Der Umriss selbst behält die engere
#: Fangweite von :data:`CURSOR_PIXELS`.
PULL_HIT_PIXELS = 14.0

#: Wie weit die Vorschau einer Schnittebene über den Körper hinausragt.
#:
#: Innerhalb eines undurchsichtigen Körpers ist selbst eine durchscheinende
#: Fläche verdeckt. Dreißig Prozent Gesamtzugabe lassen deshalb ringsum einen
#: schmalen, umrandeten Rand stehen; die Ebene bleibt am Teil, wird aber auch
#: in einer schrägen Ansicht als Fläche erkennbar.
SPLIT_PLANE_SCALE = 1.3

#: Die drei Hauptansichten, die der Skizzenleiste entsprechen.
SKETCH_VIEW_DIRECTIONS: dict[str, tuple[Vec3, Vec3]] = {
    "plane:xy": VIEW_DIRECTIONS["top"],
    "plane:xz": VIEW_DIRECTIONS["front"],
    "plane:yz": VIEW_DIRECTIONS["right"],
}


def sketch_view_near(
    position: Sequence[float],
    focus: Sequence[float],
    threshold_degrees: float = 10.0,
) -> str | None:
    """Nahe Hauptansicht der Kamera, sonst ``None`` für eine freie Ansicht.

    Verglichen wird die Blickrichtung, nicht der Ort der Kamera. Dadurch
    bleibt Schieben ohne Einfluss und nur das Kippen entscheidet. Die
    Rückseiten rasten absichtlich nicht auf eine andersherum benannte
    Vorder-, Seiten- oder Draufsicht ein.
    """
    direction = tuple(float(position[axis]) - float(focus[axis]) for axis in range(3))
    length = math.sqrt(sum(value * value for value in direction))
    if length <= EPS_GEOM:
        return None
    unit = tuple(value / length for value in direction)
    best_plane = None
    best_dot = -1.0
    for plane, (wanted, _up) in SKETCH_VIEW_DIRECTIONS.items():
        score = sum(unit[axis] * wanted[axis] for axis in range(3))
        if score > best_dot:
            best_plane, best_dot = plane, score
    limit = math.cos(math.radians(max(0.0, threshold_degrees)))
    return best_plane if best_dot >= limit else None


#: Wie weit ein mitfliegendes Zahlenfeld vom Zeiger wegsteht, in Bildpunkten.
#:
#: Nicht null: Läge es unter dem Zeiger, finge es die Mausbewegungen ab, und
#: der Zug bliebe stehen. Nicht viel mehr: Der Sinn des Ganzen ist, dass Zahl
#: und Zeigerspitze in **einem** Blick liegen — was weiter weg steht, ist
#: wieder die Werkzeugzeile, nur an anderer Stelle.
#:
#: **Zwei Felder hängen daran**, und deshalb steht die Zahl hier statt zweimal:
#: das Maßfeld der Zeichenfläche (``sketch_editor.SketchCanvas._show_pointer``)
#: und die Zahl zum Zug am Ziehgriff (:meth:`DragValueBar.place`). Dieselbe
#: Frage, dieselbe Antwort — und kein Vielfaches von :data:`app.ui.style.SPACE`,
#: denn es ist kein Layoutabstand, sondern der Sicherheitsabstand zu einem
#: Ereignisempfänger.
MEASURE_GAP = 14

#: Der Durchmesser eines gesetzten Skizzenpunkts, in Bildpunkten.
#:
#: Er stand auf sechs, und damit war er **unauffälliger als die Fangmarke**
#: daneben (zwanzig Bildpunkte Spanne): Was schon existiert, sah schwächer aus
#: als das, was gleich entstünde. Im Bild las sich das umgekehrt zur Sache —
#: ein Punkt ist ein Ding in der Zeichnung, die Marke nur ein Zeiger.
#:
#: Zehn, also so groß wie die halbe Diagonale der Marke. Verwechseln kann man
#: die beiden trotzdem nicht: Der Punkt ist eine gefüllte Kugel, die Marke ein
#: Kreuz aus zwei Strichen — zwei Formen und nicht zwei Farben (Regel 18).
SKETCH_POINT_PIXELS = 10

#: Abstand der Achsenbuchstaben vom Ursprung, in Bildpunkten.
#:
#: Die Rasterausdehnung reicht weit über den sichtbaren Ausschnitt; ein
#: Buchstabe am Linienende läge deshalb meist außerhalb des Bildes. Nahe am
#: Ursprung bleibt er bei jedem Zoom sichtbar, ohne den Nullring zu verdecken.
AXIS_LABEL_PIXELS = 64.0

#: Deckkraft des bestehenden Körpers während des Zeichnens.
#:
#: Er bleibt als räumlicher Zusammenhang sichtbar, tritt aber klar hinter
#: Raster, Kurven, Maße und Ziehgriff zurück. Die normale transparente
#: Darstellung mit 45 % war im Handbuchbild lauter als die Skizze selbst.
SKETCH_CONTEXT_OPACITY = 0.16


SketchGridSegment = tuple[tuple[float, float, float], tuple[float, float, float]]


class SketchGridLayers(NamedTuple):
    """Feines Raster, Fünfermarken und die beiden Nullachsen getrennt."""

    minor: tuple[SketchGridSegment, ...]
    major: tuple[SketchGridSegment, ...]
    axes: tuple[SketchGridSegment, ...]


def sketch_grid(
    frame: PlaneFrame, step: float, reach: float
) -> list[tuple[tuple[float, float, float], tuple[float, float, float]]]:
    """Die Rasterlinien einer Zeichenebene, als Paare von Weltpunkten (§30.1).

    Das Raster liegt **in** der Ebene und nicht unter ihr: Es sagt, wo die
    Zeichnung liegt und wie groß sie ist, und beides wäre falsch, wenn es
    woanders läge. Gerechnet wird über
    :func:`app.core.sketch.planes.to_world` — dieselbe Umrechnung, die auch
    die Skizze an ihren Ort legt, denn zwei Rechnungen für dieselbe Ebene
    driften.

    ``step`` ist die Rasterweite in Millimetern, ``reach`` die halbe
    Ausdehnung. Beide kommen von außen: die Weite aus dem Maßstab (der Editor
    wählt sie aus der 1-2-5-Folge), die Ausdehnung aus dem Bauraum.

    Eine freie Funktion aus demselben Grund wie :func:`volume_edges` und
    :func:`bed_scale`: Offscreen gibt es keinen Plotter, und was hinter dieser
    Wache gerechnet wird, prüft in der Suite niemand mehr.

    Nichts kommt zurück, wo nichts zu zeichnen ist — eine Weite oder eine
    Ausdehnung von null ist keine Ausnahme, sondern ein leeres Raster.
    """
    if step <= 0.0 or reach <= 0.0:
        return []
    count = min(int(reach / step), MOST_GRID_LINES)
    span = count * step
    lines: list[tuple[tuple[float, float, float], tuple[float, float, float]]] = []
    for index in range(-count, count + 1):
        offset = index * step
        # Zwei Linien je Schritt: eine entlang der zweiten Achse, eine entlang
        # der ersten. Zusammen ergeben sie das Gitter; einzeln wäre es ein
        # Notenblatt.
        lines.append((to_world(frame, (offset, -span)), to_world(frame, (offset, span))))
        lines.append((to_world(frame, (-span, offset)), to_world(frame, (span, offset))))
    return lines


def sketch_grid_layers(frame: PlaneFrame, step: float, reach: float) -> SketchGridLayers:
    """Das Zeichenraster als ruhiges Netz mit ablesbaren Landmarken.

    Jede fünfte Linie führt das Auge, die beiden Nullachsen verankern den
    Ursprung. Die Geometrie bleibt exakt dieselbe wie in :func:`sketch_grid`;
    getrennt wird nur die Darstellung. So entsteht keine zweite Rechnung für
    denselben Ort.
    """
    lines = sketch_grid(frame, step, reach)
    minor: list[SketchGridSegment] = []
    major: list[SketchGridSegment] = []
    axes: list[SketchGridSegment] = []
    for pair_index in range(0, len(lines), 2):
        index = pair_index // 2 - (len(lines) // 2) // 2
        pair = lines[pair_index : pair_index + 2]
        if index == 0:
            axes.extend(pair)
        elif index % 5 == 0:
            major.extend(pair)
        else:
            minor.extend(pair)
    return SketchGridLayers(tuple(minor), tuple(major), tuple(axes))


def sketch_cursor(
    frame: PlaneFrame, point: tuple[float, float], size: float
) -> list[tuple[tuple[float, float, float], tuple[float, float, float]]]:
    """Das Kreuz, das zeigt, **wohin ein Klick fällt** — als Weltpunktpaare.

    Der Ort ist der schon gefangene (``SketchCanvas.pointer_target``), nicht
    die rohe Zeigerlage. Das ist der ganze Zweck: Gefangen wird auf das
    Raster, also landet ein Klick bis zu einen halben Schritt neben dem
    Mauszeiger — bei 2 mm Raster elf Bildpunkte, bei 10 mm sechzig. Der Canvas
    zeigte dafür seit je ein Kreuz, und seit die Zeichnung im Viewport liegt
    (§30.1, P4), sieht das niemand mehr: Der Canvas rechnet dort unsichtbar
    weiter. Gemeldet wurde es als „die Klicks sind wo anders als ich klick".

    Ein Kreuz und kein Punkt: Ein Punkt sähe aus wie ein gesetzter, und der
    Unterschied zwischen „hier ist etwas" und „hier entstünde etwas" wäre
    allein die Farbe (Regel 18). Die Diagonalen stehen zudem quer zu den
    Rasterlinien, auf denen die Marke meistens sitzt — ein achsparalleles
    Kreuz verschwände genau dort in ihnen.

    ``size`` ist die halbe Diagonale in Millimetern. Nichts kommt zurück, wo
    nichts zu zeichnen ist.
    """
    if size <= 0.0:
        return []
    x, y = point
    return [
        (to_world(frame, (x - size, y - size)), to_world(frame, (x + size, y + size))),
        (to_world(frame, (x - size, y + size)), to_world(frame, (x + size, y - size))),
    ]


def pull_handle(
    frame: PlaneFrame, curves: Sequence[SketchCurve], size: float
) -> list[tuple[tuple[float, float, float], tuple[float, float, float]]]:
    """Pfeil nach außen und Kreuz nach innen am längsten Profilrand.

    Der Fuß sitzt auf dem greifbaren Umriss. Pfeil und Kreuz sind die zweite
    Kodierung neben der Richtung (Regel 18): nach außen entsteht Material,
    nach innen wird es entfernt.
    """
    if size <= 0.0:
        return []
    usable = [curve for curve in curves if not curve.construction and len(curve.points) > 1]
    if not usable:
        return []

    def curve_length(curve: SketchCurve) -> float:
        return sum(math.dist(first, second) for first, second in pairwise(curve.points))

    chosen = max(usable, key=curve_length)
    total = curve_length(chosen)
    if total <= EPS_GEOM:
        return []
    halfway = total / 2.0
    walked = 0.0
    base = chosen.points[0]
    for first, second in pairwise(chosen.points):
        segment = math.dist(first, second)
        if walked + segment >= halfway and segment > EPS_GEOM:
            share = (halfway - walked) / segment
            base = (
                float(first[0] + (second[0] - first[0]) * share),
                float(first[1] + (second[1] - first[1]) * share),
                float(first[2] + (second[2] - first[2]) * share),
            )
            break
        walked += segment

    def shifted(point: Sequence[float], vector: Sequence[float], amount: float) -> Vec3:
        return (
            float(point[0] + vector[0] * amount),
            float(point[1] + vector[1] * amount),
            float(point[2] + vector[2] * amount),
        )

    outward = shifted(base, frame.normal, size)
    inward = shifted(base, frame.normal, -size)
    neck = shifted(outward, frame.normal, -size * 0.32)
    arrow_a = shifted(neck, frame.x_axis, size * 0.24)
    arrow_b = shifted(neck, frame.x_axis, -size * 0.24)
    cross_a = shifted(inward, frame.x_axis, size * 0.18)
    cross_b = shifted(inward, frame.x_axis, -size * 0.18)
    cross_c = shifted(inward, frame.y_axis, size * 0.18)
    cross_d = shifted(inward, frame.y_axis, -size * 0.18)
    return [
        (inward, outward),
        (outward, arrow_a),
        (outward, arrow_b),
        (cross_a, cross_b),
        (cross_c, cross_d),
    ]


#: Wie viele Sprossen die Vorschau des Ziehgriffs je Kurve höchstens zeichnet.
#:
#: Die Sprossen sind die senkrechten Striche zwischen Umriss und angehobener
#: Kopie — sie machen aus zwei Umrissen einen Körper. Bei einem Rechteck sind
#: es fünf Punkte und damit fünf Sprossen, also alle; bei einem Kreis mit
#: vierundsechzig Segmenten wären es vierundsechzig, und das ist keine
#: Drahtform mehr, sondern eine Wand. Zwölf lesen sich als Körper und bleiben
#: durchsichtig genug, um die Zeichnung darunter zu sehen.
MOST_PULL_RIBS = 12


def pull_cage(
    frame: PlaneFrame,
    curves: Sequence[SketchCurve],
    height: float,
    ribs: int = MOST_PULL_RIBS,
) -> list[tuple[tuple[float, float, float], tuple[float, float, float]]]:
    """Die Drahtform, die beim Ziehen einer Höhe wächst — als Weltpunktpaare.

    Der Ziehgriff (§30.1): In der Querschau zieht man am Umriss, und der Körper
    soll dabei entstehen, nicht erst danach. Gezeichnet wird der angehobene
    Umriss plus Sprossen dorthin — zwei Umrisse und ein paar Striche dazwischen
    sind das Wenigste, das man als Körper liest.

    **Und ausdrücklich keine Fläche.** Eine echte Vorschau ginge über
    ``session.preview_async``, also über den Kern, einen Arbeiter-Thread und
    einen Neuaufbau der Aktoren — gemessen kostet allein das Neuzeichnen der
    Skizze 7,8 ms, und bei sechzig Mausereignissen in der Sekunde ist das der
    Qt-Hauptthread. Die Drahtform kostet nichts dergleichen und sagt dasselbe:
    wie hoch es wird. Der Körper selbst entsteht beim Loslassen, aus der
    Operation, mit ihrer eigenen Vorschau.

    **Konstruktionsgeometrie bleibt draußen.** Sie trägt Bedingungen und bildet
    kein Profil — angehoben wäre sie eine Wand, die im Ergebnis nicht vorkommt.

    ``height`` ist die Höhe entlang ``frame.normal``, also entlang genau der
    Richtung, in die :func:`app.core.brep.profiles.extrude` aufzieht. Nichts
    kommt zurück, wo nichts zu zeichnen ist — eine Höhe von null ist kein
    Sonderfall, sondern ein Körper ohne Ausdehnung.
    """
    if abs(height) <= EPS_GEOM or ribs < 2:
        return []
    lift = (
        frame.normal[0] * height,
        frame.normal[1] * height,
        frame.normal[2] * height,
    )

    def raised(point: Sequence[float]) -> tuple[float, float, float]:
        return (point[0] + lift[0], point[1] + lift[1], point[2] + lift[2])

    lines: list[tuple[tuple[float, float, float], tuple[float, float, float]]] = []
    for curve in curves:
        if curve.construction or len(curve.points) < 2:
            continue
        top = [raised(point) for point in curve.points]
        lines.extend(pairwise(top))
        # Die Sprossen gleichmäßig verteilt, erste und letzte immer dabei: An
        # den Enden hängt die Form, in der Mitte hängt nur der Eindruck.
        count = len(curve.points)
        stride = max(1, -(-(count - 1) // (ribs - 1)))
        chosen = list(range(0, count, stride))
        if chosen[-1] != count - 1:
            chosen.append(count - 1)
        for index in chosen:
            point = curve.points[index]
            lines.append(((point[0], point[1], point[2]), top[index]))
    return lines


def pulled_height(reach: float, step: float, limits: tuple[float, float]) -> float:
    """Aus dem Rohmaß am Zeiger die Höhe, die der Ziehgriff zeigt.

    Zwei Schritte, und beide haben einen doppelten Grund.

    **Gefangen auf das Raster, das im Bild steht.** Eine aufgezogene Höhe soll
    eine runde Zahl sein — 20 mm und nicht 19,7 —, und ein Zug, der zwischen
    zwei Rasterpunkten nichts ändert, muss nicht neu zeichnen: dasselbe Mittel,
    mit dem die Fangmarke ihre 6,9 ms je Mausbewegung los ist. Eine Weite von
    null heißt „kein Raster" und fängt nicht.

    **Geklemmt auf die Grenzen der Operation, mit erhaltenem Vorzeichen.**
    Positiv baut Material auf, negativ schneidet hinein. Beide Richtungen
    tragen ihre eigene Operation, aber dieselbe Maßgrenze; eine erfundene
    Grenze wäre schlechter als keine.

    Eine freie Funktion, weil die Hälfte davor (:meth:`Viewport._pick_ray`)
    offscreen nicht läuft: Was hinter dem Plotter liegt, prüft in der Suite
    niemand mehr (§35).
    """
    if step > 0.0:
        reach = round(reach / step) * step
    least, most = limits
    if most > least:
        direction = -1.0 if reach < 0.0 else 1.0
        return direction * min(max(abs(reach), least), most)
    return reach


def polyline_distance(points: Sequence[tuple[float, float]], at: tuple[float, float]) -> float:
    """Wie weit eine Bildstelle vom Zug durch diese Punkte entfernt ist.

    Gemessen gegen die **Strecken** und nicht gegen die Punkte: Der Umriss
    eines Rechtecks hat vier Ecken, und ein Griff, der nur dort greift,
    verlangt, dass man eine Ecke trifft. Dieselbe Unterscheidung wie bei der
    Merkmalssuche, die gegen die Dreiecke misst statt gegen die Eckpunkte.

    In Bildpunkten, weil der Griff in Bildpunkten gedacht ist: Wie weit daneben
    noch „am Umriss" heißt, hängt am Bild und nicht an der Zeichnung. Ein
    einzelner Punkt zählt als er selbst; eine leere Folge gibt ``inf``, denn
    von nichts ist alles gleich weit weg.
    """
    if not points:
        return math.inf
    if len(points) == 1:
        return math.dist(points[0], at)
    best = math.inf
    for start, end in pairwise(points):
        span = (end[0] - start[0], end[1] - start[1])
        length = span[0] * span[0] + span[1] * span[1]
        # **Gegen null und nicht gegen eine Toleranz.** Hier stand `EPS_GEOM`,
        # und das ist eine Fertigungstoleranz in Millimetern (§11.2), während
        # `length` das Quadrat eines Abstands in **Bildpunkten** ist — zwei
        # Einheiten, von denen keine zur anderen passt. Wirkungslos war es,
        # aber ein Leser hält so etwas für eine geprüfte Wahl. Die Frage
        # lautet „sind das zwei gleiche Punkte", und darauf antwortet null.
        if length <= 0.0:
            best = min(best, math.dist(start, at))
            continue
        # Der Fußpunkt auf der Strecke, geklemmt auf ihre Enden.
        share = ((at[0] - start[0]) * span[0] + (at[1] - start[1]) * span[1]) / length
        share = min(max(share, 0.0), 1.0)
        foot = (start[0] + share * span[0], start[1] + share * span[1])
        best = min(best, math.dist(foot, at))
    return best


def polyline_spans(counts: Sequence[int]) -> list[int]:
    """Die Linienstruktur, mit der VTK mehrere Polylinien in einem Netz führt.

    VTK erwartet je Linie zuerst ihre Punktzahl und dann ihre Indizes, alles
    in **einer** flachen Liste: Zwei Strecken über vier Punkten ergeben
    ``[2, 0, 1, 2, 2, 3]``. Die Zahlen dazwischen sehen aus wie Indizes und
    sind Längen — genau deshalb steht die Rechnung hier und nicht mitten im
    Zeichnen, wo niemand sie prüfen kann.

    Gezählt wird über die Punktzahlen in derselben Reihenfolge, in der die
    Punkte im Netz liegen. Eine Linie mit weniger als zwei Punkten wird
    übergangen — sie hätte keine Strecke, und VTK bekäme eine Länge, die ins
    Leere zeigt.
    """
    spans: list[int] = []
    start = 0
    for count in counts:
        if count >= 2:
            spans.append(count)
            spans.extend(range(start, start + count))
        start += count
    return spans


def axes_widget_of(plotter: Any) -> Any:
    """Das Achsen-Widget eines Plotters — oder ``None``.

    **Es hängt am Renderer, nicht am Plotter.** ``plotter.axes_widget`` gibt es
    in pyvista 0.48 nicht; ein ``getattr`` darauf liefert still ``None``, und
    die Anzeige bliebe für immer dort stehen, wo sie beim Aufbau landete —
    also mitten im Bild, weil das Fenster da noch keine Größe hat. Der Fehler
    fällt an keiner Ausnahme auf, sondern nur im Bild, und genau so ist er
    aufgefallen: als handtellergroßes Achsenkreuz quer über dem Modell.
    """
    renderer = getattr(plotter, "renderer", None) if plotter is not None else None
    return getattr(renderer, "axes_widget", None)


def orientation_corner(width: int, height: int) -> tuple[float, float, float, float]:
    """Wo die Achsenanzeige sitzt, für ein Fenster dieser Größe.

    Unten links, in dem Streifen, den die linke Spalte über dem unteren Rand
    frei lässt. Die Werkzeugzeile beginnt weiter rechts, also bleibt die Ecke
    selbst frei — bei eingeklappten Karten erst recht.

    VTK erwartet Anteile von 0 bis 1, mit dem Ursprung unten links. Bei einem
    Fenster, das kleiner ist als die Anzeige, bleibt sie am Rand kleben statt
    hinauszulaufen.
    """
    span = max(float(ORIENTATION_SIZE), 1.0)
    left = ORIENTATION_MARGIN / max(width, 1)
    bottom = ORIENTATION_MARGIN / max(height, 1)
    return (
        left,
        bottom,
        min(left + span / max(width, 1), 1.0),
        min(bottom + span / max(height, 1), 1.0),
    )


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
#:
#: **Aus dem Kern, nicht als eigene Zahl.** Dieselben dreißig Grad standen an
#: drei Stellen: hier, in der Merkmalserkennung und in der Analysekarte. Was
#: der Viewport zeichnet, ist die Kante, an der der Nutzer klickt, um eine
#: Fläche zu wählen — sagt die Darstellung dreißig Grad und die Erkennung
#: eines Tages fünfunddreißig, wählt der Klick etwas anderes aus, als die
#: Kante zeigt. Die Zahl gehört der Erkennung; hier wird sie nur gezeichnet.
FEATURE_EDGE_ANGLE = CURVATURE_LIMIT

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
#: Ab wann ein Zug am Körper ein Zug ist und kein Klick, in Millimetern.
#:
#: Ohne diese Grenze bekäme jede Auswahl einen Schritt im Verlauf mit null
#: Millimetern Versatz — Einträge, die nichts getan haben, und die dem
#: Rückgängig seinen Sinn nehmen.
EPS_DRAG = 0.05

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

#: Eine Vorschau unter dem Zeiger ist noch keine Auswahl. Sie nimmt deshalb
#: die Merkmalsfarbe und bleibt durchscheinend; die Auswahl selbst ist
#: deckend bernsteinfarben. Der Merkmalszeiger ist die zweite Kodierung nach
#: Regel 18.
HOVERED_FEATURE_OPACITY = 0.5

#: Eine deckende Innenwand wirkt aus schrägem Blick wie ein Deckel über der
#: Bohrung. Auswahl bleibt kräftiger als Hover, beide lassen aber den Blick
#: durch die Öffnung frei.
SELECTED_HOLE_OPACITY = 0.38
HOVERED_HOLE_OPACITY = 0.24

#: Wie hoch der Kontaktschatten über der Platte liegt. Ohne diesen Abstand
#: streiten sich Schatten und Platte um dieselbe Tiefe, und das Bild flimmert
#: beim Drehen.
SHADOW_LIFT = 0.05

#: Farbe und Deckkraft des Kontaktschattens. Dunkler als die Platte, aber
#: nie schwarz: er soll den Ort zeigen, nicht ein Loch in die Platte
#: schneiden.
#:
#: **Halb so stark wie früher** (0,35 → 0,18, Entscheidung Robert,
#: 25.08.2026). Der Anlass war ein Bildschirmfoto, auf dem der Schatten
#: „komisch" aussah — und er war es nicht: Er ist die konvexe Hülle des
#: Körpers, und dort bestand der Körper aus **drei getrennten Teilen** (ein
#: Würfel und zwei Haken, die neben ihm in der Luft hingen). Die Hülle spannte
#: über alle drei und umfasste die Luft dazwischen. Der Schatten hat also den
#: Zerfall angezeigt, bevor der Prüfbericht ihn meldete.
#:
#: Weggelassen wird er deshalb nicht — er beantwortet, ob ein Teil auf der
#: Platte steht oder darüber schwebt (§18.6), und genau diese Frage stellte
#: sich dort. Er tritt nur leiser auf. Die eigentliche Lösung für den Fall
#: wäre ein Schatten **je Zusammenhangskomponente** statt je Körper; das steht
#: im Register und ist eine eigene Entscheidung.
SHADOW_COLOUR = "#11151a"
SHADOW_OPACITY = 0.18

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
#: **Und mehr zur Seite als nach hinten**, denn nach hinten heißt: hinter dem
#: Teil, und das ist von der Kamera aus dort, wo das Teil selbst steht. Bei
#: 0,54 nach hinten und 0,18 zur Seite blieb der Schatten eines 8 mm hohen
#: Bodens ein Streifen von 4 mm hinter einem 70 mm langen Körper — verdeckt.
#: Gemessen an zwei Aufnahmen desselben Bildes, einmal mit und einmal ohne die
#: Schattenaktoren: von 260 000 verglichenen Bildpunkten waren **vier**
#: dunkler. Ein Schatten, den man nicht sieht, beantwortet die Frage nicht, für
#: die er da ist (§18.6): steht das Teil auf der Platte oder darüber?
#:
#: Physikalisch ist ein Licht in der Kamera genau das — ein Schatten, der sich
#: hinter dem Gegenstand versteckt. Deshalb sitzt das Licht hier seitlich über
#: der Kamera, wie in jedem CAD: Der Schatten tritt neben dem Teil hervor, und
#: sein Versatz wächst weiter mit der Höhe.
#:
#: Gemessen wurde auch die Gegenrichtung: Ein Schatten, der auf den Betrachter
#: zu fällt, ist am besten zu sehen (5 053 Punkte) — und er behauptet ein Licht
#: hinter dem Teil, während dessen Vorderseite hell beleuchtet ist. Das war
#: schon einmal der Stand und aus genau diesem Grund verworfen. Seitlich sind
#: es 2 988 Punkte, und die Aussage bleibt richtig.
#:
#: Die Länge bleibt dieselbe (0,63 mm Versatz je Millimeter Höhe), nur ihre
#: Richtung ist gedreht.
SHADOW_REACH = 0.10
SHADOW_SIDE = 0.62

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


#: Der Abstand zwischen zwei Betten, wenn alle Platten zusammen zu sehen sind.
#:
#: Breit genug, dass keine Frage bleibt, welches Teil auf welcher Platte liegt —
#: und schmal genug, dass vier Platten noch in ein Bild passen.
PLATE_GAP = 40.0


def plate_shift(plate: int, width: float, gap: float = PLATE_GAP) -> tuple[float, float, float]:
    """Wohin Platte ``plate`` in der Ansicht rückt (§25).

    Die erste bleibt, wo sie ist, die übrigen reihen sich nach +X daneben. Das
    ist der Grund für die Richtung: eine Szene mit einer Platte sieht danach
    aus wie vorher, Bild für Bild — und wer eine zweite dazubekommt, sieht sie
    kommen, statt die erste wegrutschen zu sehen.

    **Nur Darstellung, wie das Auseinanderziehen (§18.8).** Der Stapel, der
    Export und der Prüfbericht rechnen mit dem Ort, den die Anordnung vergeben
    hat; Platten stehen dort ohnehin übereinander, weil jede ihr eigenes Bett
    hat. Genau das war das Bild, das niemand verstand: zwei Platten, ein Bett,
    die Teile ineinander.

    Als reine Funktion, aus demselben Grund wie :func:`bed_scale`: offscreen
    gibt es keinen Plotter, und die Rechnung ist das, was ein Test prüfen kann.
    """
    return (max(0, plate) * (width + gap), 0.0, 0.0)


def plate_at(x: float, plates: int, width: float, gap: float = PLATE_GAP) -> int:
    """Zu welcher Platte ein Punkt in der Ansicht gehört — die Umkehrung von
    :func:`plate_shift`.

    Gebraucht beim Klicken: was der Nutzer trifft, liegt in der Ansicht, und
    was eine Operation als Ort bekommt, muss in der Szene liegen. Ohne diese
    Umkehrung setzte ein Klick auf Platte 2 die Bohrung um eine Bettbreite
    daneben.
    """
    pitch = width + gap
    if plates <= 1 or pitch <= 0.0:
        return 0
    return max(0, min(plates - 1, round(x / pitch)))


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


def source_colours(mesh: Any, face_count: int) -> Any | None:
    """Darstellungsfarben einer importierten Datei als RGB-Zellenwerte.

    Materialslots sind Druckinformation. OBJ, PLY und GLB können darüber
    hinaus Eckfarben oder eine Textur tragen, und die gehört ins Bild, auch
    bevor jemand sie bewusst auf Filamente reduziert (§20).
    """
    raw = getattr(mesh, "raw", None)
    if raw is None:
        return None
    from app.core.geom.texture import face_colours

    colours = face_colours(raw)
    if colours is None or len(colours) != face_count:
        return None

    import numpy as np

    return np.clip(np.rint(colours * 255.0), 0.0, 255.0).astype(np.uint8)


MeasureMode = Literal["off", "distance", "thickness", "angle"]

MEASURE_COLOUR = ROLES["measure"]

#: Wie weit die Maus zwischen Drücken und Loslassen wandern darf, damit es noch
#: als Klick zählt. In jedem Schema tut die rechte Taste auch etwas an der
#: Kamera; ein Zug meint sie, ein Klick meint das, worauf er zeigt.
#:
#: **Zehn Pixel und nicht zwei.** Die alte Begründung — „eine Maus steht beim
#: Drücken selten ganz still" — war richtig, der Wert dazu zu knapp: Drei Pixel
#: Wandern beim Klicken sind normal, und bis zum 23.08.2026 fiel damit die
#: Auswahl aus. Robert gemeldet als „wenn ich ein merkmal auswähle und im
#: viewport dann wieder auf das modell klicke wechseln wir auch nicht".
#:
#: Zehn ist ``QApplication.startDragDistance()`` auf dieser Plattform — der
#: Wert, ab dem Qt selbst ein Drücken als Ziehen liest, und damit derselbe, den
#: jedes andere Fenster auf dem Bildschirm benutzt. Als Konstante und nicht
#: über Qt abgefragt, damit :func:`is_click` eine reine Rechnung bleibt.
CLICK_SLACK = 10


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

#: Wie weit ein Klick von der **eigenen Fläche** eines Merkmals abliegen darf
#: und noch als Treffer gilt — als Anteil der Objektdiagonale, mit einer
#: Untergrenze in Millimetern.
#:
#: Ohne diese Grenze gab es keine: :meth:`Viewport._feature_at` nahm das
#: Merkmal mit dem **nächsten Mittelpunkt** und traf damit immer eines. An der
#: Platte aus dem Korpus wählte ein Klick auf die Deckfläche sieben Millimeter
#: neben einer Bohrung die Bohrung, und ein Klick in der Nähe der Stirnseite
#: die Stirnfläche — der Mittelpunkt einer 80 mm langen Deckfläche liegt weiter
#: weg als der einer kleinen Fläche daneben. Genau das war „die Auswahl nimmt
#: immer die Bohrung statt des Modells".
#:
#: Der Anteil ist großzügiger als :data:`app.core.units.EPS_MATCH_RELATIVE`,
#: und dafür gibt es einen Grund: gepickt wird im **dezimierten** Anzeigenetz
#: (§18.9), und dessen Oberfläche liegt nicht genau auf der der Szene.
FEATURE_REACH_SHARE = 0.01
FEATURE_REACH_MINIMUM = 0.5


def bore_span(
    origin: Vec3,
    direction: Vec3,
    centre: Vec3,
    axis: Vec3,
    radius: float,
    along: tuple[float, float],
) -> tuple[float, float] | None:
    """Von wo bis wo ein Sichtstrahl im Inneren einer Bohrung läuft.

    Gerechnet wird gegen den Zylinder um ``centre`` mit dieser ``axis`` und
    diesem ``radius``, begrenzt auf den Achsbereich ``along`` — die kleinste
    und größte Projektion der Merkmalsdreiecke auf die Achse. Ohne diese
    Begrenzung reichte der Zylinder unendlich weit, und eine Bohrung am einen
    Ende des Teils fing Klicks am anderen.

    Zurück kommen die beiden Strahlparameter in Millimetern, gemessen von
    ``origin`` entlang ``direction`` (das normiert erwartet wird), oder nichts,
    wenn der Strahl vorbeigeht.

    **Der entartete Fall ist der wichtigste.** Blickt man senkrecht in eine
    Bohrung, läuft der Strahl **parallel** zur Achse: Dann gibt es keinen Ein-
    und Austritt durch den Mantel, der Strahl liegt ganz innen oder ganz außen,
    und die quadratische Gleichung dazu hat keinen Leitkoeffizienten. Genau
    diese Ansicht ist die, in der man Bohrungen anklickt.

    Als freie Funktion und nicht als Methode, aus demselben Grund wie
    :func:`is_click`: eine Rechnung über Vektoren soll ohne VTK prüfbar sein.
    """
    import numpy as np

    start = np.asarray(origin, dtype=float)
    forward = np.asarray(direction, dtype=float)
    line = np.asarray(axis, dtype=float)
    length = float(np.linalg.norm(line))
    if length <= EPS_GEOM:
        return None
    line = line / length

    # Quer zur Achse: der Abstand von ihr, als Funktion von t.
    across = forward - float(forward @ line) * line
    offset = start - np.asarray(centre, dtype=float)
    offset = offset - float(offset @ line) * line
    lead = float(across @ across)
    if lead <= EPS_GEOM:
        # Parallel zur Achse — ganz innen oder ganz außen.
        if float(offset @ offset) > radius * radius:
            return None
        crosswise = (-math.inf, math.inf)
    else:
        middle = 2.0 * float(offset @ across)
        gap = float(offset @ offset) - radius * radius
        under = middle * middle - 4.0 * lead * gap
        if under < 0.0:
            return None
        root = math.sqrt(under)
        crosswise = ((-middle - root) / (2.0 * lead), (-middle + root) / (2.0 * lead))

    # Entlang der Achse: der Bereich, den das Merkmal überhaupt einnimmt.
    at_start = float(start @ line)
    per_step = float(forward @ line)
    if abs(per_step) <= EPS_GEOM:
        if not along[0] <= at_start <= along[1]:
            return None
        lengthwise = (-math.inf, math.inf)
    else:
        first = (along[0] - at_start) / per_step
        second = (along[1] - at_start) / per_step
        lengthwise = (min(first, second), max(first, second))

    enter = max(crosswise[0], lengthwise[0])
    leave = min(crosswise[1], lengthwise[1])
    return (enter, leave) if enter < leave else None


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

#: Ab welcher Abweichung von 1,0 ein Skalierfaktor als Zug zählt — relativ,
#: nicht in Millimetern, darum nicht ``EPS_DISPLAY``. Zweimal als Streuzahl
#: geschrieben, entschied dieselbe Frage an zwei Stellen verschieden, sobald
#: jemand eine der beiden anfasst.
SCALE_UNCHANGED = 1e-4

#: Wie viele dezimierte Netze die Anzeige behält. Eines war zu wenig: Zwei
#: große Körper verdrängten einander, und ``show_scene`` — das bei jeder
#: Auswahl, jedem Themenwechsel und jedem Zug am Schnittschieber läuft —
#: dezimierte beide jedes Mal neu, im Qt-Hauptthread (§2.8).
DISPLAY_CACHE_KEPT = 4

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


def rotation_focus(
    position: Sequence[float], focus: Sequence[float], centre: Sequence[float]
) -> Vec3 | None:
    """Der Fokuspunkt für den Beginn einer Drehung — oder nichts.

    Der Punkt auf dem Sichtstrahl, der der Mitte der Körper am nächsten
    liegt: gleiche Stellung, gleiche Blickrichtung, nur die Fokustiefe
    wechselt. Das Bild ändert sich dadurch um nichts, und der Drehpunkt
    bekommt die Tiefe der Körper. Nichts zurück heißt: so lassen — die Mitte
    liegt hinter der Kamera, oder der Fokus stimmt schon.

    Als eigene Funktion, damit die Regel ohne Plotter prüfbar bleibt —
    dieselbe Begründung wie bei :meth:`Viewport.rotation_centre`.
    """
    import numpy as np

    where = np.asarray(position, dtype=float)
    aim = np.asarray(focus, dtype=float) - where
    span = float(np.linalg.norm(aim))
    if span <= EPS_GEOM:
        return None
    aim /= span
    depth = float(np.dot(np.asarray(centre, dtype=float) - where, aim))
    if depth <= EPS_GEOM:
        return None
    target = where + depth * aim
    if all(abs(float(target[axis]) - float(focus[axis])) < EPS_DISPLAY for axis in range(3)):
        return None
    return (float(target[0]), float(target[1]), float(target[2]))


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


#: Wie viel Luft um das Eingepasste bleibt, als Anteil der Ausdehnung je Achse.
#:
#: ``reset_camera(bounds=…)`` passt **genau** ein. Ein 40 mm großer Quader
#: berührte damit links und rechts den Bildrand, und von der Druckplatte war
#: nichts mehr zu sehen — der Größenvergleich, für den sie in echter Größe
#: dasteht, fiel weg. Zwölf Prozent sind so viel, dass ein Teil freisteht, und
#: so wenig, dass es nicht in der Ferne liegt.
CAMERA_MARGIN = 0.12


def with_margin(
    bounds: tuple[float, float, float, float, float, float], share: float = CAMERA_MARGIN
) -> tuple[float, float, float, float, float, float]:
    """Die Grenzen um ihre Mitte geweitet, im VTK-Format.

    Als eigene Funktion, aus demselben Grund wie :func:`bed_scale`: offscreen
    gibt es keinen Plotter, und was nur im Zeichnen steht, prüft niemand.

    Eine Achse ohne Ausdehnung bleibt, wie sie ist — eine flache Skizze soll
    nicht in die Tiefe wachsen, nur weil sie eingepasst wird.
    """
    widened: list[float] = []
    for low, high in zip(bounds[0::2], bounds[1::2], strict=True):
        air = (high - low) * share / 2.0
        widened.extend((low - air, high + air))
    return (widened[0], widened[1], widened[2], widened[3], widened[4], widened[5])


#: Ab welchem Größenverhältnis eine Szene der eingepassten Ansicht entwachsen
#: ist.
#:
#: Fünf, weil darunter der Grund gilt, aus dem die Kamera in Ruhe bleibt: Wer
#: heranzoomt und eine Bohrung setzt, will seinen Zoom behalten. Ein Körper, der
#: fünfmal so groß ist wie alles bisher, ist kein Nachbessern mehr — gemessen an
#: einem Teil von 2 mm, zu dem ein 400er dazukam: das Verhältnis war 186, die
#: Kamera stand im Inneren des neuen Körpers, und zu sehen war eine rote Fläche.
OUTGROWN_FACTOR = 5.0


def diagonal_of(bounds: tuple[float, float, float, float, float, float]) -> float:
    """Die Raumdiagonale eines Hüllquaders im VTK-Format."""
    spans = [high - low for low, high in zip(bounds[0::2], bounds[1::2], strict=True)]
    return math.sqrt(sum(span * span for span in spans))


def outgrown(
    fitted: tuple[float, float, float, float, float, float] | None,
    current: tuple[float, float, float, float, float, float] | None,
    factor: float = OUTGROWN_FACTOR,
    *,
    moved_only: bool = False,
) -> bool:
    """Ob die Szene nicht mehr zu der Ansicht passt, auf die eingepasst wurde.

    Zwei Fälle, und beide hat jemand vor sich, der nichts falsch gemacht hat:

    **Sie ist gewachsen.** Wer in ein Teil von zwei Millimetern hineingezoomt
    hat und dann einen 400er Körper erzeugt oder einlädt, sah eine dunkelrote
    Fläche — die Kamera stand im Inneren des neuen Körpers. Der Prüfbericht
    warnte richtig („Ein Objekt steht über den Bauraum hinaus"), das Bild sagte
    nichts.

    **Sie ist weggerückt.** Berühren sich der eingepasste und der jetzige
    Hüllquader nicht mehr, steht das Modell außerhalb des Bildes. Auch das ist
    keine Feinarbeit, bei der jemand seinen Zoom behalten will.

    **Aber nicht, wenn der Nutzer selbst geschoben hat** (``moved_only``). Wer
    einen Körper mit der Maus über die Platte zieht, weiß, wohin — und bekam
    bei jedem Loslassen die Kamera neu gerahmt. Robert am 23.08.2026, nachdem
    er es einmal gesehen hatte: „nach jedem verschieben springt die kamera und
    das modell immer komisch … kamera bei aktueller position dann immer
    lassen." Das Größenkriterium darüber gilt weiter: Ein Körper, der beim
    Schieben plötzlich zwanzigmal so groß wäre, ist kein Schieben mehr.

    Die Unterscheidung ist nicht „Maus oder nicht", sondern **ob dieselben
    Objekte dastehen wie beim Einpassen**. Ein neu geladenes Modell, das weit
    neben der Platte liegt, wird weiterhin eingerahmt — dort hat niemand eine
    Ansicht gewählt, die er behalten will.

    Alles darunter bleibt, wie es war (:meth:`Viewport._fit_once_for`): Eine
    Kamera, die bei jeder Bohrung neu einpasst, macht den Zoom zweimal.

    Als reine Funktion, aus demselben Grund wie :func:`with_margin`: offscreen
    gibt es keinen Plotter, und was nur im Zeichnen steht, prüft niemand.
    """
    if fitted is None or current is None:
        return False
    if diagonal_of(current) > factor * diagonal_of(fitted):
        return True
    if moved_only:
        return False
    return any(
        current[axis * 2] > fitted[axis * 2 + 1] or current[axis * 2 + 1] < fitted[axis * 2]
        for axis in range(3)
    )


def bed_scale(width: float, depth: float) -> list[tuple[tuple[float, float, float], str]]:
    """Die Maßzahlen an der vorderen und linken Plattenkante (§18.6).

    Ein Raster ohne Zahlen sagt nur, dass es ein Raster gibt. Erst die Zahl
    daneben macht daraus einen Maßstab, an dem man ein Teil einordnet, ohne
    zu messen — und das ist der Zweck der Platte in echter Größe.

    Als eigene Funktion und nicht im Zeichnen versteckt: offscreen gibt es
    keinen Plotter, und eine Prüfung, die sich dort überspringt, prüft nie
    etwas.

    **Die Zahlen tragen ihr Vorzeichen, und die Null steht in der Mitte ihrer
    Kante.** Beides war falsch, und zusammen ergab es eine Skala, die sich selbst
    widersprach: ``abs()`` nahm beiden Seiten das Vorzeichen, also lag dieselbe
    „100" zweimal im Bild — und die einzige Null stand in der **Ecke** der
    Platte, mit der Begründung, sie gehöre beiden Kanten. Der Nullpunkt der Szene
    ist aber die Mitte der Platte, nicht ihre Ecke: bei 220 mm stand „0" bei
    x = -110 und zehn Millimeter weiter „100". Jede Kante bekommt deshalb ihre
    eigene Null.

    Vorzeichenbehaftet und nicht als Abstand von der Mitte, weil die
    Positionsfelder der Operationsdialoge es auch sind — wer „Position X = -40"
    tippt, soll die -40 auf der Platte finden.
    """
    marks: list[tuple[tuple[float, float, float], str]] = []
    half_width, half_depth = width / 2.0, depth / 2.0
    step = BED_SCALE_STEP

    def along(half: float) -> list[float]:
        """Die Marken einer Kante: die Null, dann schrittweise nach beiden Seiten.

        Eine Platte, die schmaler ist als ein Schritt, behält so ihre Null —
        ohne sie stolpert VTK über eine leere Beschriftungsliste.
        """
        values = [0.0]
        position = step
        while position <= half + EPS_GEOM:
            values.extend((-position, position))
            position += step
        return values

    for value in along(half_width):
        marks.append(((value, -half_depth - BED_SCALE_GAP, 0.0), f"{value:.0f}"))
    for value in along(half_depth):
        marks.append(((-half_width - BED_SCALE_GAP, value, 0.0), f"{value:.0f}"))
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


class ViewBar(QFrame):
    """Die sieben Kameravorgaben, sichtbar statt im Menü (Konzept P15, D4).

    **Warum sie zweimal entstanden ist.** D4 hieß ursprünglich „kein ViewCube,
    keine Ansichtsleiste" und wurde mit dem Würfel geschlossen: Er deckte alle
    sieben Vorgaben ab, und eine Leiste daneben wäre Doppelung gewesen, die
    Bildfläche kostet. Am 12.08.2026 ist der Würfel dem Achsenkreuz gewichen
    (`f04c35d`) — er deckt seither nichts mehr ab, und die Vorgaben lagen
    wieder allein im Menü. Ein Befund, der über eine Zwischenlösung geschlossen
    wurde, geht mit ihr wieder auf.

    **Zeichen ohne Wort — und das ist eine begründete Abweichung.** Der Kopf
    von :mod:`app.ui.icons` sagt „Symbole ergänzen Text, sie ersetzen ihn
    nicht", und das gilt überall, wo Platz ist. Hier ist keiner: Mit
    Beschriftung wird die Leiste **1039 Bildpunkte** breit und verdeckt bei
    einem 1024er Fenster mehr als ein Drittel der Ansicht — genau die Fläche,
    für die §2.5 die Karten schweben lässt. Mit Symbolen allein sind es 196.

    Getragen wird der Text deshalb zweifach woanders: im Tooltip samt Kürzel
    und im zugänglichen Namen, den ein Screenreader liest. Und gelernt wird er
    im Kameramenü — dieselben sieben Wörter, dieselben Kürzel, an dem Ort, an
    dem man ohnehin nachsieht. Die Leiste ist der schnelle Weg für den, der sie
    kennt, nicht die Stelle, an der man sie kennenlernt.

    Die Symbole sind eine Familie: sechsmal dieselbe Bildebene, unterschieden
    nur darin, woher der Blick kommt, dazu der Würfel für die Isometrie.

    **Unten rechts, und das ist keine Geschmacksfrage:** Unten links steht die
    Achsenanzeige, die einzige Orientierungshilfe, die es noch gibt. Zwei
    Anzeigen an derselben Stelle waren der Grund, aus dem der Würfel gehen
    musste — derselbe Fehler zweimal wäre einer zu viel.
    """

    #: Die Vorgaben in der Reihenfolge, in der sie in der Leiste stehen. Die
    #: Schlüssel sind die aus :data:`VIEW_DIRECTIONS`; eine zweite Liste
    #: derselben Namen würde driften, deshalb prüft ein Test beide gegeneinander.
    ORDER: Final = ("iso", "front", "back", "left", "right", "top", "bottom")

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("viewBar")

        layout = QHBoxLayout(self)
        layout.setContentsMargins(TIGHT, TIGHT, TIGHT, TIGHT)
        layout.setSpacing(TIGHT)

        self._buttons: dict[str, QToolButton] = {}
        # **Dieselben Wörter wie im Kameramenü**, nicht kürzere daneben. „Vorn"
        # neben „Vorne" wären zwei Wörter für dieselbe Sache — derselbe Fehler,
        # den die Wegekarten schon einmal hatten, und er kostet in jeder Sprache
        # einen Eintrag mehr, den niemand mit dem Menü abgleicht.
        labels = {
            "iso": (tr("Isometrisch"), "Ctrl+0"),
            "front": (tr("Vorne"), "Ctrl+1"),
            "back": (tr("Hinten"), "Ctrl+2"),
            "left": (tr("Links"), "Ctrl+3"),
            "right": (tr("Rechts"), "Ctrl+4"),
            "top": (tr("Oben"), "Ctrl+5"),
            "bottom": (tr("Unten"), "Ctrl+6"),
        }
        for key in self.ORDER:
            long, shortcut = labels[key]
            button = QToolButton(self)
            button.setIcon(icon(f"view_{key}", self))
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonIconOnly)
            # Der zugängliche Name trägt das Wort, das der Knopf nicht zeigt —
            # ohne ihn hätte ein Screenreader hier sieben namenlose Schaltflächen.
            button.setAccessibleName(long)
            # **Die Taste, wie sie auf der Tastatur heißt.** Hier stand der
            # rohe Deklarationstext, also „Ctrl+0" — während das Ansichtsmenü
            # daneben dasselbe Kürzel als echtes ``QAction`` führt und Qt es
            # als „Strg+0" schreibt. Der Knopf versprach eine Taste, die es auf
            # einer deutschen Tastatur nicht gibt, und zwar an allen sieben.
            # Denselben Fehler hat ``shortcuts_window._native`` schon einmal
            # behoben — dieser Zwilling wurde damals nicht gesucht.
            native = QKeySequence(shortcut).toString(QKeySequence.SequenceFormat.NativeText)
            button.setToolTip(f"{long} ({native})")
            button.setAutoRaise(True)
            # **Kein Lambda mit Vorgabeargument.** Es fängt ``self`` in seiner
            # Zelle, hängt an einem Knopf, der ``self`` gehört, und schließt
            # damit den Ring, den Pythons Speicherbereiniger über die
            # C++-Grenze nicht sieht. Gemessen am 23.08.2026: zehn losgelassene
            # ``ViewBar`` überlebten alle zehn, und ``gc.get_referrers`` nannte
            # als einzigen Halter die Zelle dieses Abschlusses.
            button.clicked.connect(weak_slot(self, ViewBar._request, key))
            layout.addWidget(button)
            self._buttons[key] = button

        self.set_theme("dark")
        self.adjustSize()

    def keys(self) -> tuple[str, ...]:
        """Welche Vorgaben die Leiste anbietet."""
        return tuple(self._buttons)

    def button(self, key: str) -> QToolButton | None:
        """Der Knopf einer Vorgabe, für Tests und Touren."""
        return self._buttons.get(key)

    def _request(self, key: str) -> None:
        parent = self.parentWidget()
        view_from = getattr(parent, "view_from", None)
        if callable(view_from):
            view_from(key)

    def set_theme(self, theme: str) -> None:
        """Farben aus dem Thema — die Leiste liegt über dem Modell, nicht
        neben ihm, und muss auf beiden Hintergründen lesbar sein."""
        colours = THEMES["light" if theme == "light" else "dark"]
        self.setStyleSheet(
            f"#viewBar {{ background: {colours['window']};"
            f" border: 1px solid {colours['disabled']}; border-radius: 4px; }}"
            f"#viewBar QToolButton {{ color: {colours['text']}; background: transparent;"
            # Enger Innenabstand: Die Leiste liegt über dem Modell, und jeder
            # Bildpunkt, den sie nicht braucht, gehört dem Teil.
            f" border: none; padding: {TIGHT}px; }}"
            f"#viewBar QToolButton:hover {{ background: {colours['alternate']};"
            f" border-radius: 3px; }}"
        )

    def place(self) -> None:
        """Unten rechts, mit demselben Rand, den die Achsenanzeige links hält."""
        parent = self.parentWidget()
        if parent is None:
            return
        self.adjustSize()
        self.move(
            max(parent.width() - self.width() - ORIENTATION_MARGIN, 0),
            max(parent.height() - self.height() - ORIENTATION_MARGIN, 0),
        )


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
            # Ein Hinweis ist Nebentext und nicht gesperrt: ``disabled`` bringt
            # im hellen Thema 2,59 gegen das Band, ``muted`` ist dafür da.
            f"#previewBanner #previewHint {{ color: {colours['muted']}; }}"
        )

    def show_preview(self, note: str, palette: DiffPalette, hint: str) -> None:
        """Zeigt das Band mit Text, Legende und dem Griff zum Vergleichen."""
        colours = DIFF_PALETTES[palette]
        self.note.setText(note)
        # **Jede Kodierung in ihrer eigenen Farbe.** Die ganze Zeile stand in
        # der Farbe von „Hinzugefügt" — auch das Wort „Entfernt", dessen
        # Kodierung Orange ist. Eine Farbe, die die Unwahrheit sagt, ist
        # schlechter als keine; Regel 18 war damit formal erfüllt und
        # inhaltlich verkehrt.
        #
        # Das Feld trägt die Kodierungsfarbe, die Schrift darauf wird gerechnet
        # (``readable_on``) — dasselbe Muster wie die Kartenlegende, und es löst
        # den zweiten Teil des Fundes gleich mit: Als bloße Schriftfarbe kam die
        # Legende in Graustufen auf 1,16 gegen ihr Band. Das Zeichen bleibt
        # daneben stehen, denn ohne es hinge die Aussage wieder an der Farbe.
        self.legend.setTextFormat(Qt.TextFormat.RichText)
        self.legend.setText(
            "&nbsp;&nbsp;".join(
                f'<span style="background:{encoding.colour};color:{readable_on(encoding.colour)};">'
                f"&nbsp;{encoding.symbol} {tr(encoding.label_key)}&nbsp;</span>"
                for encoding in (colours.added, colours.removed)
            )
        )
        self.legend.setStyleSheet("")
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
        self.value.setAccessibleName(tr("Wert"))
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
        self.anchor: QPoint | None = None
        """Wo das Feld stehen soll — ``None`` heißt oben mittig.

        **Beim Ziehgriff der Skizze steht es am Zeiger** (§30.1), und das ist
        dieselbe Entscheidung wie beim Maßfeld der Zeichenfläche: Wer eine Höhe
        aufzieht, sieht auf ihre Spitze, und eine Zahl am Fensterrand liest
        dort niemand. Bei den Griffen von §18.11 bleibt es oben — dort zieht
        man an einem Gizmo, den man ansieht, und ein Feld unter dem Zeiger
        verdeckte gerade ihn."""
        self._length_unit: LengthUnit | None = None
        """In welcher Längeneinheit die Zahl gerade steht — ``None`` heißt: Es
        ist keine Länge.

        Dieses Feld zeigt drei Arten von Zahl: eine Strecke, einen Winkel und
        einen Faktor. Ohne die Unterscheidung hätte die Rückrechnung aus einem
        Winkel von 45 Grad eine Strecke von 1143 Millimetern gemacht."""
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
        """Der Live-Wert des Zugs — solange niemand tippt.

        Für alles, was **keine** Länge ist: Winkel und Skalierfaktor. Eine
        Strecke geht über :meth:`follow_length`, damit die Anzeigeeinheit an
        einer Stelle entschieden wird und nicht an drei Aufrufstellen.
        """
        self._length_unit = None
        self._show(label, amount, unit, decimals)

    def follow_length(self, label: str, amount_mm: float) -> None:
        """Eine Strecke — in der Anzeigeeinheit gezeigt, in Millimetern gemeint
        (§19.3, §11.1)."""
        unit = display_unit()
        self._length_unit = unit
        self._show(label, from_mm(amount_mm, unit), unit, decimals_for(unit))

    def _show(self, label: str, amount: float, unit: str, decimals: int) -> None:
        self.label.setText(label)
        self.unit.setText(unit)
        if not self.typing:
            self.value.setText(localised(f"{amount:.{decimals}f}"))
        if not self.isVisible():
            self.show()
        self.adjustSize()
        self.place()

    def typed_value(self) -> float | None:
        """Die getippte Zahl in Kerneinheiten — oder nichts, wenn dort keine steht.

        Bei einer Strecke also Millimeter, gleich was im Feld steht: Wer in Zoll
        arbeitet und „1" tippt, meint 25,4 Millimeter. Winkel und Faktor gehen
        unverändert durch.
        """
        try:
            entered = float(self.value.text().strip().replace(",", "."))
        except ValueError:
            return None
        return to_mm(entered, self._length_unit) if self._length_unit else entered

    def dismiss(self) -> None:
        """Der Zug ist vorbei — auf welche Art auch immer."""
        self.typing = False
        self.anchor = None
        self.value.clearFocus()
        self.hide()

    def place(self) -> None:
        """Oben mittig, unterhalb des Vorschaubands — oder am Anker.

        Am Anker wird mit :data:`MEASURE_GAP` Abstand gesetzt und **nie
        darunter**: Ein Feld unter dem Zeiger fängt die Mausbewegungen ab, und
        der Zug bliebe stehen. An Rand und Ecke kippt es auf die andere Seite,
        wie das Maßfeld der Zeichenfläche — dieselbe Frage, dieselbe Antwort.
        """
        parent = self.parentWidget()
        if parent is None:
            return
        if self.anchor is not None:
            left = self.anchor.x() + MEASURE_GAP
            top = self.anchor.y() + MEASURE_GAP
            if left + self.width() > parent.width():
                left = self.anchor.x() - MEASURE_GAP - self.width()
            if top + self.height() > parent.height():
                top = self.anchor.y() - MEASURE_GAP - self.height()
            self.move(max(left, 0), max(top, 0))
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


class SketchPlanePicker(QFrame):
    """Drei greifbare Ebenenkarten direkt im Bild.

    Das Auswahlfeld in der Leiste bleibt für Genauigkeit und Flächen eines
    Körpers erhalten. Beim freien Start beantworten diese Karten aber die
    erste Frage dort, wo ihr Ergebnis liegt: in der Ansicht.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sketchPlanePicker")
        outer = QVBoxLayout(self)
        outer.setContentsMargins(ROOMY, ROOMY, ROOMY, ROOMY)
        outer.setSpacing(TIGHT)
        title = QLabel(
            tr("Worauf gezeichnet wird. Die Ziffern 1, 2 und 3 wechseln direkt."),
            self,
        )
        title.setObjectName("sketchPlaneTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignCenter)
        outer.addWidget(title)

        row = QHBoxLayout()
        row.setSpacing(TIGHT)
        self._buttons: dict[str, QToolButton] = {}
        choices = (
            ("plane:xy", tr("Draufsicht (XY) — liegend"), "view_top", "1"),
            ("plane:xz", tr("Vorderansicht (XZ) — stehend, von vorn"), "view_front", "2"),
            ("plane:yz", tr("Seitenansicht (YZ) — stehend, von der Seite"), "view_right", "3"),
        )
        for plane, label, image, key in choices:
            button = QToolButton(self)
            button.setText(f"{label}\n{key}")
            button.setIcon(icon(image, button))
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            button.setMinimumSize(142, 76)
            button.setToolTip(str(label))
            button.setAccessibleName(str(label))
            button.clicked.connect(weak_slot(self, SketchPlanePicker._choose, plane))
            row.addWidget(button)
            self._buttons[plane] = button
        outer.addLayout(row)
        self.set_theme("dark")
        self.hide()

    def _choose(self, plane: str) -> None:
        parent = self.parentWidget()
        chosen = getattr(parent, "sketchPlaneChosen", None)
        if chosen is not None:
            chosen.emit(plane)

    def set_theme(self, theme: str) -> None:
        """Kartenfarben aus dem Thema; Fokus und Hover bleiben sichtbar."""
        colours = THEMES["light" if theme == "light" else "dark"]
        self.setStyleSheet(
            f"#sketchPlanePicker {{ background: {colours['window']};"
            f" border: 1px solid {colours['disabled']}; border-radius: 10px; }}"
            f"#sketchPlanePicker QLabel {{ color: {colours['text']}; }}"
            f"#sketchPlanePicker QToolButton {{ color: {colours['text']};"
            f" background: {colours['alternate']}; border: 1px solid {colours['disabled']};"
            " border-radius: 7px; padding: 7px; }}"
            f"#sketchPlanePicker QToolButton:hover, #sketchPlanePicker QToolButton:focus {{"
            f" border: 2px solid {colours['accent_line']}; }}"
        )

    def place(self) -> None:
        """Mittig im Bild, ohne von einer Bildschirmgröße abzuhängen."""
        parent = self.parentWidget()
        if parent is None:
            return
        self.adjustSize()
        self.move(
            max((parent.width() - self.width()) // 2, 0),
            max((parent.height() - self.height()) // 2, 0),
        )
        self.raise_()


class SketchSelectionBadge(QLabel):
    """Ruhige Auswahlquittung am unteren Bildrand, zusätzlich zur Farbe."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("", parent)
        self.setObjectName("sketchSelectionBadge")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setContentsMargins(ROOMY, TIGHT, ROOMY, TIGHT)
        self.set_theme("dark")
        self.hide()

    def set_theme(self, theme: str) -> None:
        colours = THEMES["light" if theme == "light" else "dark"]
        self.setStyleSheet(
            f"#sketchSelectionBadge {{ color: {colours['text']};"
            f" background: {colours['window']}; border: 1px solid {colours['disabled']};"
            " border-radius: 6px; }}"
        )

    def place(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        self.adjustSize()
        covered = getattr(parent, "_zone_margins", (0, 0, 0))[2]
        self.move(
            max((parent.width() - self.width()) // 2, 0),
            max(parent.height() - self.height() - covered - ORIENTATION_MARGIN, 0),
        )
        self.raise_()


class SketchActionBadge(QLabel):
    """Der nächste räumliche Schritt, als ruhige Karte im Blickfeld.

    Der Ziehgriff ist eine Fusion-artige Geste. Wer sie nicht schon kennt,
    entdeckt sie nicht in einer langen Zeile unterhalb des Viewports. Die
    Karte steht deshalb nur dann im Bild, wenn aus dem geschlossenen Umriss
    tatsächlich Material aufgebaut oder entfernt werden kann.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("", parent)
        self.setObjectName("sketchActionBadge")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setContentsMargins(ROOMY, TIGHT, ROOMY, TIGHT)
        self.set_theme("dark")
        self.hide()

    def set_theme(self, theme: str) -> None:
        colours = THEMES["light" if theme == "light" else "dark"]
        self.setStyleSheet(
            f"#sketchActionBadge {{ color: {colours['text']};"
            f" background: {colours['window']}; border: 2px solid {colours['accent_line']};"
            " border-radius: 8px; font-weight: 600; }}"
        )

    def place(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        self.adjustSize()
        self.move(max((parent.width() - self.width()) // 2, 0), BANNER_TOP)
        self.raise_()


class Viewport(QWidget):
    """Die 3D-Ansicht, oder ein schlichter Hinweis, wenn VTK fehlt."""

    measurementTaken = Signal(object)
    """A finished measurement — carries a ``Measurement``."""
    measurementStatus = Signal(str)
    """Der nächste nötige Klick oder der Grund, warum keiner gezählt hat."""
    transformDragged = Signal(object)
    """A finished gizmo drag — carries ``TransformSteps`` (§18.11)."""
    sketchMenuAt = Signal(object, int, int)
    """Ein Rechtsklick im Skizzenmodus — trägt den Ebenenpunkt in Millimetern
    und die Fensterstelle für das Menü. Ohne diese Naht lief der Rechtsklick
    beim Zeichnen in die Objektauswahl, und das Skizzen-Kontextmenü
    (Koordinaten, Löschen, Bedingungen) war im Viewport-Modus unerreichbar."""
    sketchPointPicked = Signal(object)
    """Ein Klick auf die Zeichenebene — trägt den Punkt in Millimetern.

    Zwei Zahlen und kein Weltpunkt: Was die Skizze speichert, sind
    Zeichenkoordinaten, und die Umrechnung gehört an eine Stelle."""
    sketchPointHovered = Signal(object)
    """Der Zeiger steht auf der Zeichenebene — für die Vorschau."""
    sketchPulled = Signal(float)
    """Aus der Querschau ist eine Höhe gezogen worden — in Millimetern (§30.1).

    Das Fenster macht daraus ``sketch_extrude``; die Ansicht ändert nie selbst
    Geometrie (Regel 2). Was während des Zugs im Bild steht, ist eine
    Drahtform (:func:`pull_cage`) und kein Dokumentzustand."""
    sketchPlaneChosen = Signal(str)
    """Eine der drei Ebenenkarten im Bild wurde angeklickt."""
    sketchPullBlocked = Signal(str)
    """Am Ziehgriff wurde gezogen, und es ging nicht — trägt den Grund.

    Ein Griff, der stumm nichts tut, ist die schlechtere Hälfte von
    „fehlgeschlagen": Er sagt nicht einmal, dass etwas nicht ging (Regel 17).
    Der Satz kommt vom Fenster, das die Frage auch beantwortet
    (:meth:`set_sketch_pull`)."""
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
    boneRequested = Signal(object)
    """Eine Stelle, an der ein Knochenpunkt gesetzt wird (§25).

    Derselbe Vertrag wie beim Formen und beim Bemalen: Die Ansicht meldet
    einen Ort, das Fenster macht daraus einen Knochen, und Geometrie ändert
    einzig die Operation."""
    splitPointRequested = Signal(object)
    """Ein Ende der Trennlinie (§25).

    Derselbe Vertrag wie beim Bemalen, beim Formen und beim Skelett: Die
    Ansicht meldet einen Ort, das Fenster sammelt zwei davon zu einer Linie,
    und getrennt wird einzig in der Operation (Regel 2)."""
    sculptRequested = Signal(object)
    """Eine Stelle, an der ein Pinselzug gesetzt wird (§25).

    Derselbe Vertrag wie beim Bemalen und aus demselben Grund: Die Ansicht
    meldet einen Ort, das Fenster macht daraus einen Zug, und Geometrie ändert
    einzig die Operation (Regel 2). Was der Viewport währenddessen zeigt, ist
    eine Vorschau."""
    cameraMoved = Signal()
    """Die Kamera hat sich bewegt — Rad, Dreh- oder Schiebezug, Einpassen.

    Für alles, was seine Größe aus dem Bild rechnet und nicht aus der Szene:
    Das Skizzenraster wählt seine Weite aus ``pixels_per_mm`` (§30.1), und
    ohne dieses Signal veraltete sie mit jedem Zoom — das Bild zeigte die
    Weite vom Betreten, der nächste Strich ließ sie springen. Gesendet wird
    **nach** der Bewegung, nie währenddessen; wer daran zeichnet, zeichnet
    einmal je Bewegung und nicht sechzigmal je Sekunde."""
    sketchViewChanged = Signal(str)
    """Eingerastete Skizzenansicht, oder leer für eine freie Kameralage.

    Die Combo im Panel spiegelt dieses Signal. Vor dem ersten Element wird
    daraus zugleich die Zeichenebene, danach ausschließlich die Ansicht.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.plotter: Any | None = None
        self._actors: dict[ObjectId, Any] = {}
        self._frame_actors: list[Any] = []
        #: Die Teilmenge von ``_frame_actors``, die **flach auf dem Bett** liegt:
        #: Fläche und Raster. Nur sie tritt im Skizzenmodus ab — Bauraumkanten
        #: und Maßskala bleiben stehen, weil sie eine Grenze zeigen und kein
        #: zweites Gitter sind. Warum das ein Unterschied ist, steht an
        #: :meth:`set_sketching`.
        self._ground_actors: list[Any] = []
        self._selected: ObjectId | None = None
        self._fitted_to: Literal["", "bed", "objects"] = ""
        """Worauf die Kamera zuletzt eingepasst wurde — auf nichts, auf den
        Bauraum oder auf die Körper. Wechselt der Zustand, wird einmal neu
        eingepasst; innerhalb desselben Zustands bleibt jeder Zoom stehen."""
        self._fitted_bounds: tuple[float, float, float, float, float, float] | None = None
        #: Welche Objekte dastanden, als zuletzt eingepasst wurde. Stehen
        #: dieselben noch da, hat der Nutzer nur geschoben, und die Kamera
        #: bleibt (:func:`outgrown`, ``moved_only``).
        self._fitted_objects: frozenset[str] = frozenset()
        #: Ob der letzte Aufbau nur ein Verschieben war. Gesetzt und gelesen
        #: in :meth:`_fit_once_for` (für :func:`outgrown`).
        self._moved_only: bool = False
        """Die Maße, auf die eingepasst wurde — der Vergleich für
        :func:`outgrown`. „Innerhalb desselben Zustands" hat eine Grenze: Ein
        Körper, der fünfmal so groß ist wie alles bisher, ist kein Zoom mehr,
        den man behalten will."""
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
        self._sketch_frame: PlaneFrame | None = None
        self._zone_margins: tuple[int, int, int] = (0, 0, 0)
        """Verdeckte Bildränder links, rechts und unten, in Bildpunkten."""
        self._sketch_occlusion_shift: Vec3 = (0.0, 0.0, 0.0)
        """Der wirklich angewandte Kameraausgleich, in Weltkoordinaten.

        Ein Pixelrand allein genügt nicht: Nach Zoom oder Größenänderung meint
        dieselbe Pixelzahl ein anderes Weltmaß. Der gespeicherte Vektor lässt
        sich exakt entfernen und für den neuen Maßstab neu berechnen.
        """
        self._sketch_measure_pending: Callable[[], float] | None = None
        """Ob gerade ein Maß aussteht — vom Fenster je Skizzenmodus gesetzt
        und beim Verlassen gelöst, sonst hielte die Ansicht den Canvas fest
        (ein aufbewahrter Rückruf ist eine Referenz, siehe oberflaeche.md)."""
        self._sketch_measure_begin: Callable[[Any], bool] | None = None
        """Die Ebene, auf die ein Klick gerade zielt — oder nichts.

        Sie ist der Modusschalter des Skizzenmodus in der Ansicht: Solange
        sie steht, meint ein Klick eine Stelle auf ihr und kein Ding in der
        Szene (§30.1, P4)."""
        self._sketch_actors: list[Any] = []
        """Was die Skizze gerade in die Szene legt — Raster, Kurven, Punkte.

        Eigene Liste neben ``_frame_actors``: Die Zeichnung kommt und geht mit
        dem Skizzenmodus, der Bauraum bleibt. Eine gemeinsame Liste hieße,
        beim Verlassen des Modus auch die Platte wegzuräumen."""
        self._cursor_actors: list[Any] = []
        """Die Marke, die zeigt, wohin der nächste Klick fällt.

        Getrennt von ``_sketch_actors``, weil sie an der Maus hängt und nicht
        an der Zeichnung — der Grund steht bei :meth:`clear_sketch`."""
        self._cursor_mesh: Any = None
        """Das Netz der Marke, damit sie nicht je Mausbewegung neu entsteht.

        Ein Kreuz hat immer vier Punkte; bewegt es sich, ändern sich nur deren
        Koordinaten."""
        self._cursor_at: tuple[tuple[float, float], float] | None = None
        """Wo die Marke zuletzt lag und bei welchem Maßstab.

        Der Vergleich davor spart das Neuzeichnen: Ein Render kostet gemessen
        6,9 ms, und die Marke sitzt am **gefangenen** Ort — zwischen zwei
        Rasterpunkten ändert sie sich nicht."""
        self._preview_actor: Any | None = None
        self._preview_mesh: Any | None = None
        self._preview_shape: tuple[int, ...] = ()
        self._preview_at: tuple[tuple[Vec3, ...], ...] = ()
        """Die mitfliegende Geometrie zwischen zwei Klicks.

        Wie die Fangmarke gehört sie der Maus und nicht dem Dokument. Das
        Netz bleibt stehen und bekommt neue Punkte, solange die Form gleich
        bleibt; so braucht ein Zeigerschritt nur einen gemeinsamen Render."""
        self._sketch_curves: tuple[SketchCurve, ...] = ()
        """Die Kurven, die zuletzt gezeigt wurden — für den Ziehgriff.

        Er muss zwei Dinge aus ihnen wissen: wo der Umriss im **Bild** liegt
        (dort wird gegriffen) und wie die Drahtform aussieht, die beim Ziehen
        wächst. Beides steht in denselben Punkten, die :meth:`show_sketch`
        ohnehin bekommt — sie ein zweites Mal vom Fenster zu erfragen wäre die
        zweite Zahl für dieselbe Sache."""
        self._sketch_selected_curves: tuple[int, ...] = ()
        """Welche Kurven im letzten Skizzenbild ausgewählt gezeichnet wurden."""
        self._sketch_control_points: tuple[Vec3, ...] = ()
        """Greifpunkte der Skizze, unabhängig von der Kurvenabtastung."""
        self._sketch_selected_points: tuple[int, ...] = ()
        """Ausgewählte flache Punktindizes für die größere Griffdarstellung."""
        self._sketch_edit_ready: Callable[[tuple[float, float]], bool] | None = None
        self._sketch_edit_begin: Callable[[tuple[float, float]], bool] | None = None
        self._sketch_edit_move: Callable[[tuple[float, float]], None] | None = None
        self._sketch_edit_end: Callable[[], None] | None = None
        """Die vier Phasen eines Skizzenzugs im sichtbaren Viewport."""
        self._sketch_gesture: Literal["pull", "edit"] | None = None
        """Welcher Griff den laufenden Linkszug besitzt."""
        self._sketch_pull_offer: Callable[[], str] | None = None
        """Ob der Ziehgriff gerade angeboten wird — vom Fenster gesetzt.

        Es beantwortet die Frage, weil sie am Zustand der Zeichnung hängt:
        Querschau, geschlossener Umriss, und eine Operation, für die eine Höhe
        überhaupt etwas bedeutet. Die Ansicht kennt davon nichts, sie kennt die
        Geste (siehe :meth:`set_sketch_pull`)."""
        self._pull_limits: tuple[float, float] = (0.0, 0.0)
        """Die Grenzen der Höhe, aus dem Schema von ``sketch_extrude``.

        Vom Fenster mitgegeben und nicht hier eingetippt: Wer sie abschreibt,
        hat die zweite Wahrheit gebaut, und die fällt erst auf, wenn der Dialog
        eine Zahl ablehnt, die der Griff gerade gezeigt hat."""
        self._cut_limits: tuple[float, float] | None = None
        """Grenzen der Taschentiefe; ``None`` heißt: nach innen nicht angeboten."""
        self._pull_from: tuple[float, float] | None = None
        """Wo der Zug begann, in Zeichenkoordinaten — ``None`` heißt: keiner.

        Die Aufzugsachse läuft durch diesen Punkt; die Höhe ist der Ort, an dem
        der Sichtstrahl ihr am nächsten kommt (:func:`axis_hit`)."""
        self._pull_height = 0.0
        """Die Höhe, die der Zug gerade zeigt — gefangen auf das Raster."""
        self._pull_raw: float | None = None
        """Dasselbe Maß **ungeklemmt**, oder ``None`` vor der ersten Bewegung.

        Es ist die einzige Auskunft darüber, in welche **Richtung** gezogen
        wurde: :func:`pulled_height` hebt ein negatives Maß auf die Untergrenze,
        und danach sieht ein Zug nach unten aus wie ein sehr kurzer nach oben —
        gemeldet als Körper von 0,1 mm, den niemand gemeint hat."""
        self._pull_actors: list[Any] = []
        """Die Drahtform des Zugs. Eigene Liste wie die Fangmarke: Sie hängt an
        der Maus, die Zeichnung ändert sich beim Zeichnen."""
        self._sketch_step = 0.0
        """Die Rasterweite, die zuletzt **gezeichnet** wurde.

        Nicht die eingestellte und nicht die gefangene — die, die im Bild
        steht. Ohne sie war „ändert sich das Raster im Viewport?" von außen
        nicht zu beantworten: Man sah Linien und musste sie zählen, und ein
        Test darüber hätte den Actor auseinandergenommen."""
        self._grid_minor_colour = THEMES["dark"]["grid_minor"]
        self._grid_major_colour = THEMES["dark"]["grid_major"]
        self._sketch_colour = ROLES["info"]
        self._axis_x_colour = ROLES["axis_x"]
        self._axis_y_colour = ROLES["axis_y"]
        self._sketch_label_colour = THEMES["dark"]["text"]
        self._sketch_label_background = THEMES["dark"]["window"]
        self._measure_mode: MeasureMode = "off"
        self._pending_point: Vec3 | None = None
        self._pending_plane: tuple[Vec3, Vec3] | None = None
        self.measurements = MeasurementList()
        self._measure_actors: list[Any] = []
        self._gizmo: Any | None = None
        self._gizmo_wanted = False
        """Ob der Gizmo eingeschaltet ist — unabhängig davon, ob gerade einer
        im Bild steht. Der Griff selbst wird bei jedem Auswahl- und
        Szenenwechsel neu angehängt; dieser Schalter sagt, ob überhaupt."""
        self._coincident_before: int | None = None
        """Die globale Tiefen-Auflösung von VTK, bevor der Gizmo sie umstellte.

        ``SetResolveCoincidentTopologyToPolygonOffset()`` sieht aus wie eine
        Mapper-Eigenschaft und ist eine **statische**: pyvistas Widget und der
        Skaliergriff stellen damit prozessweit jeden Mapper um. Ohne
        Rückstellung stachen nach dem ersten Bewegen-Besuch die Kantenlinien
        aller Körper dauerhaft durch die Flächen — Striche an den
        Kantenmitten, die in keiner Aktor-Eigenschaft standen."""
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
        """Was gerade gezogen wird — ``move``, ``turn``, ``face``, ``scale``
        oder ``pull``, ``None`` heißt kein Zug. Entscheidet, was eine getippte
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
        self._shadow_hulls: dict[ObjectId, list[Any]] = {}
        """Je Körper die konvexe Hülle seiner Punkte, für den Schattenwurf.
        Einmal je Szenenaufbau gerechnet — ein Ansichtswechsel projiziert nur
        noch daraus (§18.6)."""
        self._shadow_splits: dict[ObjectId, tuple[Any, list[Any]]] = {}
        """Je Körper das Netz, aus dem seine Hüllen stammen, und sie selbst.

        Überlebt den Szenenaufbau, anders als ``_shadow_hulls``: Er ist genau
        dafür da, das Zerlegen zu sparen, wenn sich am Netz nichts geändert
        hat. Verglichen wird die Identität des Netzes (siehe
        ``_shadow_hulls_for``)."""
        self._shadow_ground: dict[ObjectId, tuple[float, float, Any]] = {}
        """Je Körper Unterkante, Oberkante und sein Umriss von oben. Damit
        steht fest, wer auf wem steht — und damit, welche Fläche den Schatten
        auffängt."""
        self._bed_extent: tuple[float, float] | None = None
        self._build_volume: tuple[float, float, float] | None = None
        """Der Bauraum des geltenden Profils — Breite, Tiefe, Höhe.

        Getrennt von :attr:`_bed_extent`, weil der Schattenschnitt nur die
        Platte braucht und das Einpassen der leeren Szene die Höhe."""
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
        self._direct_picking = False
        """Ob ein Klick ohne Zwischenstufe das tiefste Ziel meint.

        Aus, solange betrachtet wird — dann ist ein Klick eine Navigation und
        durchläuft die Stufen (:meth:`_click_target`). An, solange ein
        Operationsdialog nach einem Merkmal fragt: dann ist ein Klick eine
        **Antwort**, und wer zweimal zeigen muss, um zu antworten, hält den
        ersten Klick für verschluckt.
        """
        self._feature_geometry: dict[ObjectId, list[tuple[FeatureId, Any, Any, Any]]] = {}
        # Die konvexe Hülle je Körper, für den Blick durch eine Öffnung
        # (:meth:`_through_aim`). Wie die Merkmalsdreiecke gehört sie einer
        # Auswertung und wird mit ihnen geleert.
        self._object_hulls: dict[ObjectId, Any] = {}
        """Je Körper die Dreiecke jedes Merkmals mit ihrem Hüllquader —
        vorbereitet, weil die Trefferfrage bei jeder Ruhepause des Zeigers neu
        gestellt wird (90 ms, :data:`HOVER_DELAY_MS`).

        Der Quader ist die billige Vorprüfung: Ein Modell mit fünfhundert
        Merkmalen hat fünfhundert Dreiecksmengen, und der genaue Abstand ist
        nur für die eine oder zwei nötig, deren Quader den Zeiger überhaupt
        erreicht. Geleert wird beim Szenenwechsel — die Dreiecke gehören einer
        Auswertung, nicht dem Viewport.
        """
        self._feature_patch: Any | None = None
        """Die Dreiecke des gewählten Merkmals, in der Auswahlfarbe über dem
        Körper. Ohne sie hieß „Bohrung gewählt", dass der ganze Körper
        aufleuchtet — die Auswahl zeigte das Objekt und nicht die Stelle."""
        self._hover_patch: Any | None = None
        """Die durchscheinende Fläche unter dem ruhenden Zeiger (§18.5)."""
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
        # Eine Methode und **kein Lambda**: Der Zeitgeber ist ein Kind dieser
        # Ansicht, und ein Lambda darin hielte sie stark — Viewport → QTimer →
        # Rückruf → Viewport. Diese Schleife läuft über die C++-Grenze, Pythons
        # Speicherbereiniger sieht die mittlere Kante nicht und kann sie nicht
        # brechen. Eine gebundene Methode hält Qt von sich aus schwach.
        # Gemessen: Mit dem Lambda überlebten **zwanzig von zwanzig**
        # losgelassenen Viewports ihr `del` samt `gc.collect()`, so keiner.
        self._layer_rebuild.timeout.connect(self._rebuild_layer)
        self._difference: Any | None = None
        self._difference_actors: list[Any] = []
        self._difference_held = False
        """Ob die Vorschau gerade weggehalten wird, um das Vorher zu sehen."""
        self._diff_palette: DiffPalette = "blue_orange"
        self._explosion = 0.0
        """§18.8: wie weit geteilte Stücke auseinandergezogen gezeichnet werden.
        Nur Darstellung, nie Geometrie."""
        self._plate = -1
        """Welche Druckplatte gezeigt wird; -1 heißt alle (§25)."""
        self._profile: Profile | None = None
        """Das Profil, mit dem der Bauraum gezeichnet wurde — gebraucht, wenn
        eine Platte dazukommt und die Kulisse neu muss."""
        self._beds_drawn = 0
        """Wie viele Betten gerade im Bild stehen. Ändert sich die Zahl, wird
        die Kulisse neu gebaut; bleibt sie, wird nichts angefasst."""
        self._sculpting = False
        self._boning = False
        self._splitting = False
        """§25: solange das an ist, setzen Klicks die Enden einer Trennlinie."""
        self._split_actors: list[Any] = []
        """Was von der gezeichneten Linie im Bild steht. Eine eigene Liste, weil
        sie ein anderes Leben hat als die Körper: Ein Szenenaufbau räumt sie
        nicht weg, ein Werkzeugwechsel schon."""
        self._brush_radius = 0.0
        """Der Pinselradius in Millimetern, solange geformt wird."""
        self._last_drag_stroke: Vec3 | None = None
        self._body_drag_from: Vec3 | None = None
        """Wo ein Zug am gewählten Körper begonnen hat, in Ansichtskoordinaten.

        ``None`` heißt: Es wird gerade keiner gezogen — dann bleibt die linke
        Taste, was das Navigationsschema aus ihr macht."""
        self._body_drag_offset: tuple[float, float] = (0.0, 0.0)
        """Wie weit der Zug bisher trägt, in Millimetern auf dem Bett."""
        self._actor_home: dict[str, tuple[float, float, float]] = {}
        """Wo die verschobenen Actors standen, bevor die Vorschau sie bewegte.

        Die Vorschau wird zurückgenommen, bevor die Auswertung den Körper an
        seine neue Stelle setzt — sonst stünde er doppelt versetzt da."""
        """Wo der letzte Zug eines gezogenen Strichs saß — der Mindestabstand
        (halber Pinselradius) rechnet dagegen."""
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
        self._hovered_object: ObjectId | None = None
        self._hovered_feature: FeatureId | None = None
        """Das genaue Merkmal hinter :attr:`_hover_feature`.

        Der Wahrheitswert steuert den Zeiger; die Kennungen steuern die
        sichtbare Hervorhebung. Nur ein Wahrheitswert könnte beim Wechsel von
        einer Bohrung zur nächsten nichts neu zeichnen.
        """
        self._hidden: frozenset[ObjectId] = frozenset()
        """§18.8: was der Nutzer ausgeblendet hat. Ansicht, nicht Szene — die
        Körper werden weiter gerechnet, geprüft und exportiert."""
        self._display_cache: dict[tuple[ObjectId, int], Any] = {}
        """§18.9: die dezimierte Version des zuletzt gezeigten Körpers. Sie
        fließt nie in den Kern zurück."""

        self.banner = PreviewBanner(self)
        """Das Band über dem Bild, wenn eine Vorschau läuft."""
        self.view_bar = ViewBar(self)
        """Die sieben Kameravorgaben, unten rechts (D4). Vor ihr lagen sie
        allein im Menü — der Würfel, der sie einmal abdeckte, ist am 12.08.2026
        dem Achsenkreuz gewichen."""
        self.drag_bar = DragValueBar(self)
        """Die Zahl zum Zug (§18.11): lesen beim Ziehen, tippen statt zielen."""
        self.drag_bar.value.installEventFilter(self)
        self.plane_picker = SketchPlanePicker(self)
        """Die drei greifbaren Grundebenen beim freien Einstieg."""
        self.sketch_selection = SketchSelectionBadge(self)
        """Was in der Skizze gewählt ist — ruhig am Bildrand."""
        self.sketch_action = SketchActionBadge(self)
        """Aufziehen und Abtragen dort erklären, wo Umriss und Griff stehen."""
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
                view._settle_sketch_view()
                view._redraw_shadows()
                # Dreh- und Schiebezüge enden hier; der Radzoom meldet sich
                # selbst (``on_camera`` im Interaktionsstil), weil er kein
                # ``EndInteractionEvent`` auslöst.
                view.cameraMoved.emit()

        self.plotter.interactor.AddObserver("EndInteractionEvent", on_end)

    def _settle_sketch_view(self) -> str | None:
        """Eine nahe Hauptansicht einrasten und ihren Namen melden.

        Nur im Skizzenmodus: Außerhalb soll eine frei gedrehte Modellansicht
        frei bleiben. Abstand, Fokus und Parallelmaßstab ändern sich nicht;
        das Einrasten korrigiert ausschließlich die letzten wenigen Grad.
        """
        if self._sketch_frame is None or self.plotter is None:
            return None
        camera = getattr(self.plotter, "camera", None)
        position = getattr(camera, "position", None)
        focus = getattr(camera, "focal_point", None)
        if position is None or focus is None:
            return None
        plane = sketch_view_near(position, focus)
        if plane is not None:
            direction, up = SKETCH_VIEW_DIRECTIONS[plane]
            distance = max(math.dist(tuple(position), tuple(focus)), EPS_GEOM)
            snapped = tuple(float(focus[axis]) + direction[axis] * distance for axis in range(3))
            self.plotter.camera_position = [snapped, tuple(focus), up]
            with suppress(Exception):  # pragma: no cover - hängt an der VTK-Version
                self.plotter.renderer.ResetCameraClippingRange()
            self.plotter.render()
        self.sketchViewChanged.emit(plane or "")
        return plane

    # --- Darstellungsqualität (§18.1) -------------------------------------------

    def _add_orientation_widget(self, theme: str = "dark") -> None:
        """Das Achsenkreuz unten links: die Anzeige, wo oben ist.

        **Der Docstring stand hier lange auf dem Kopf.** Er beschrieb einen
        anklickbaren Würfel und schloss mit „er ersetzt aber ``add_axes``" —
        während die Zeilen darunter genau ``add_axes`` aufrufen und einen
        Würfel im ganzen Quelltext niemand findet. Von den zwei Anzeigen, die
        damals doppelt im Bild standen, ist der Würfel gegangen und dieses
        Kreuz geblieben; nachgezogen wurde der Text nicht. Wer ihn las, hielt
        die einzige Orientierungsanzeige der Anwendung für abgeschafft.

        Sie ist die einzige, also muss man sie sehen — wo sie sitzt und warum
        das ausgerechnet in Bildpunkten gerechnet wird, steht bei
        :func:`orientation_corner`.
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
                viewport=orientation_corner(self.width(), self.height()),
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

    def _shadow_hulls_for(self, object_id: ObjectId, surface: Any, source: Any) -> list[Any]:
        """Die Hüllen dieses Körpers — neu gerechnet nur bei einem anderen Netz.

        ``_shadow_hulls_of`` zerlegt den Körper, und das kostet 21 ms bei
        zweiundachtzigtausend Dreiecken. Sein Docstring nannte das „einmal je
        Szenenaufbau" und meinte damit „selten" — das stimmte nicht.
        ``show_scene`` läuft auch bei jeder Auswahl, jedem Themenwechsel und
        **bei jedem Schritt der Schieber** für Explosion, Schnitt und Schicht.
        Bei zwanzig Teilen auf der Platte sind das über vierhundert
        Millisekunden je Schieberschritt, im Qt-Hauptthread.

        Verglichen wird die **Identität** des Netzes, nicht sein Inhalt: Ein
        Hash über zweiundachtzigtausend Dreiecke wäre nicht billiger als die
        Zerlegung, die er sparen soll. Solange die Auswertung steht, ist das
        Netz dasselbe Objekt — unter der Dezimierungsschwelle reicht
        ``_for_display`` es unverändert durch, darüber kommt es aus seinem
        Cache.

        **Der Schnittschieber trifft den Cache absichtlich nicht.** ``cut``
        erzeugt dort wirklich ein neues Netz, und ein Körper, der zerschnitten
        wurde, zerfällt womöglich in andere Stücke als vorher — die Zerlegung
        ist dann keine Ersparnis, sondern die richtige Antwort.
        """
        cached = self._shadow_splits.get(object_id)
        if cached is not None and source is not None and cached[0] is source:
            return cached[1]
        hulls = self._shadow_hulls_of(surface)
        if source is not None:
            self._shadow_splits[object_id] = (source, hulls)
        return hulls

    def _shadow_hulls_of(self, surface: Any) -> list[Any]:
        """Die Punkte, aus denen ein Körper seinen Schatten wirft — je Stück eines.

        **Ein Körper ist nicht immer ein Stück.** Ein Baustein, dessen Träger zu
        schmal ist, hinterlässt drei: den Träger und zwei Haken daneben. Eine
        gemeinsame Hülle darüber spannt über die Luft dazwischen und wirft
        einen Schatten in der Form eines Dings, das es nicht gibt (Befund
        Robert, 25.08.2026, am Bildschirm gesehen).

        Der übliche Fall bleibt der billige: ``split_bodies`` gibt bei einem
        einteiligen Körper ein Stück zurück, und dann ist das hier genau die
        Rechnung von vorher. Gemessen kostet das Zerlegen 1,5 ms bei
        eintausendzweihundert Dreiecken und 21 ms bei zweiundachtzigtausend.

        Hier stand „einmal je Szenenaufbau, nicht je Bild", und das war als
        Beruhigung gemeint und als Behauptung falsch: Ein Szenenaufbau ist
        nicht selten — jede Auswahl und jeder Schritt der Schieber ist einer.
        Gerufen wird deshalb über ``_shadow_hulls_for``, das die Zerlegung
        behält, solange das Netz dasselbe ist. **Wer hier vorbei ruft, zahlt
        die Millisekunden je Aufbau.**
        """
        bodies = surface.split_bodies()
        if len(bodies) <= 1:
            single = self._shadow_hull_of(surface)
            return [single] if single is not None else []
        # Die Punkte genügen — ``_shadow_hull_of`` liest ohnehin nur ``points``,
        # und ein ``extract_surface`` je Stück wäre eine Umwandlung für nichts.
        hulls = []
        for block in bodies:
            hull = self._shadow_hull_of(block)
            if hull is not None:
                hulls.append(hull)
        return hulls

    def _shadow_hull_of(self, surface: Any) -> Any:
        """Die Punkte, aus denen ein Stück seinen Schatten wirft.

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
        # Die Platte dieses Körpers, nicht die erste: die Umrisse der Körper
        # stehen dort, wo gezeichnet wurde (§25), und ein Schatten, der am
        # Umriss von Platte 1 geschnitten wird, verschwindet für jeden Körper
        # auf Platte 2 restlos.
        catchers: list[tuple[float, Any]] = [
            (0.0, self._bed_outline_for(object_id) if self._bed_extent is not None else None)
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

    def _rebuild_layer(self) -> None:
        """Der aufgeschobene Schnitt, wenn der Schichtschieber zur Ruhe kommt.

        Eine eigene Methode und kein Lambda am Zeitgeber: Qt hält eine
        gebundene Methode schwach, ein Lambda hielte die Ansicht am eigenen
        Kind fest (siehe ``__init__`` und `.claude/rules/oberflaeche.md`).
        """
        self.show_scene(self._result)

    def show_scene(self, result: EvaluationResult | None) -> None:
        """Baut die Ansicht aus der letzten vollständigen Auswertung neu (§15.3)."""
        # Ein voller Neuaufbau schneidet an der aktuellen Schichthöhe mit —
        # ein noch ausstehender Schnitt vom Schieber wäre danach derselbe
        # noch einmal.
        self._layer_rebuild.stop()
        self._result = result
        # Ein Hoverziel gehört ebenso zur Auswertung wie seine vorbereiteten
        # Dreiecke. Nach einer Änderung kann dieselbe Kennung eine andere
        # Fläche meinen oder ganz verschwunden sein.
        self._hover_timer.stop()
        self._hover_feature = False
        self._hovered_object = None
        self._hovered_feature = None
        # Eine Auswahl gehört zur aktuellen Auswertung. Der Körper darf nach
        # einem Schritt weiter ausgewählt bleiben; ein Merkmal, das dieser
        # Schritt entfernt hat, dagegen nicht. Ohne den Rückfall blieb seine
        # Kennung intern stehen, der Körper verlor die Auswahlfarbe und im Bild
        # war weder die alte Fläche noch eine neue Auswahl zu sehen.
        if result is not None and self._selected is not None:
            selected_entry = result.scene.objects.get(self._selected)
            if selected_entry is None:
                self._selected = None
                self._selected_feature = None
            elif (
                self._selected_feature is not None
                and self._selected_feature not in selected_entry.features
            ):
                self._selected_feature = None
        # Die vorbereiteten Merkmalsdreiecke gehören der vorigen Auswertung.
        # Eine Op, die eine Bohrung verschiebt, ändert ihre Dreiecke, und ein
        # Klick träfe danach, wo sie war.
        self._feature_geometry.clear()
        self._object_hulls.clear()
        # Eine Platte mehr heißt ein Bett mehr. Die Kulisse gehört
        # ``show_build_volume``, und die kennt die Szene nicht — hier ist die
        # Stelle, an der die Zahl bekannt wird. Nur bei Änderung, sonst baute
        # jede Auswertung vier Betten neu, die schon stehen.
        if self._profile is not None and self._beds_for_view() != self._beds_drawn:
            self.show_build_volume(self._profile)
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
            self._hover_feature = False
            self._hovered_object = None
            self._hovered_feature = None
            self.measurements.clear()
        if self.plotter is None:
            return
        for actor in self._actors.values():
            self.plotter.remove_actor(actor, render=False)
        self._actors.clear()
        # **Mit den Aktoren geht auch ihr gemerkter Ausgangsort.** Die neuen
        # kommen aus der Geometrie und tragen keinen Zug mehr; ein
        # stehengebliebener Eintrag würde beim nächsten Ziehen als Basis
        # genommen (:meth:`continue_body_drag`, ``setdefault``) und den Körper
        # doppelt versetzen.
        self._actor_home.clear()
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
        # Die Zerlegungen überleben das — sie zu leeren hieße, sie bei jedem
        # Aufbau neu zu rechnen, und genau das sollen sie sparen. Was einem
        # Körper gehört, den es nicht mehr gibt, fällt hier weg: Der Cache
        # wächst sonst über eine lange Sitzung mit jedem gelöschten Körper.
        if result is not None:
            self._shadow_splits = {
                object_id: entry
                for object_id, entry in self._shadow_splits.items()
                if object_id in result.scene.objects
            }
        else:
            self._shadow_splits.clear()
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

        style = dict(DISPLAY_MODES[self._mode])
        if self._sketch_frame is not None:
            style["opacity"] = min(float(style.get("opacity", 1.0)), SKETCH_CONTEXT_OPACITY)
        for object_id, entry in result.scene.objects.items():
            if not self._in_view(object_id, entry):
                continue
            mesh = self._sectioned(self._for_display(object_id, entry.mesh))
            raw = getattr(mesh, "raw", None)
            if raw is None or not len(raw.faces):
                continue
            faces = np.hstack(
                [np.full((len(raw.faces), 1), 3, dtype=np.int64), np.asarray(raw.faces)]
            ).ravel()
            points = np.asarray(raw.vertices, dtype=float) + self._view_offset(entry, result)
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
            # ``mesh`` und nicht ``surface``: Das PolyData entsteht in jeder
            # Runde neu, das Netz dahinter bleibt dasselbe, solange sich nichts
            # geändert hat. Daran erkennt der Schatten, ob er neu zerlegen muss.
            self._remember_shadow(surface, object_id, mesh)

        # Erst jetzt: ein Schatten fällt auf die Fläche, auf der sein Körper
        # steht, und welche das ist, weiß nur die vollständige Szene.
        if self._sketch_frame is None:
            self._place_shadows(self._shadow_direction())
        self.select(self._selected)
        self._redraw_features()
        self._redraw_layer()
        self._render_now()

    def _aim_rotation(self) -> None:
        """Der Drehpunkt bekommt beim Drehbeginn die Tiefe der Körper (§2.9).

        VTK dreht um den Fokuspunkt der Kamera. Der wurde früher bei jedem
        Szenenaufbau auf die Mitte der Körper gesetzt (``_centre_rotation``),
        und die Kamera rückte mit — nach einem Verschieben sprang damit das
        Bild (Robert, 23.08.2026: „nach jedem verschieben springt die kamera
        und das modell immer komisch"). Die Notlösung ließ den Fokus nach
        einem reinen Verschieben stehen, und ihr Preis war benannt: Gedreht
        wurde um den alten Punkt, bis zum nächsten echten Szenenwechsel.

        Deshalb jetzt hier, im Beginn der Drehung — dem einzigen Moment, in
        dem der Fokuspunkt etwas bedeutet. Und unsichtbar: Der Fokus rückt auf
        den Punkt des Sichtstrahls, der der Mitte der Körper am nächsten liegt
        (:func:`rotation_focus`). Stellung und Blickrichtung der Kamera
        bleiben unangetastet, das Bild ändert sich um nichts; nur die Tiefe
        des Drehpunkts stimmt wieder. Seitlich bleibt er in der Bildmitte:
        Gedreht wird um das, was man ansieht — nicht um einen Punkt daneben,
        dessen Anfahren mitten in der Geste einen Sprung ins Bild brächte.

        Den Fall »Kulisse statt Körper« — Bauraumrahmen 250 mm, Teil 40, die
        Mitte alles Sichtbaren hundert Millimeter über dem Modell — löst
        :meth:`rotation_centre`: Die Mitte kommt aus den Körpern, nie aus dem
        Renderer.
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
        target = rotation_focus(camera.GetPosition(), camera.GetFocalPoint(), centre)
        if target is None:
            return
        camera.SetFocalPoint(*target)
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
            colours = source_colours(mesh, face_count)
            if colours is None:
                return {}
            surface.cell_data["source_colour"] = colours
            return {
                "scalars": "source_colour",
                "rgb": True,
                "show_scalar_bar": False,
            }

        import numpy as np

        known = {slot.index: slot for slot in slots}
        highest = max(known)
        table = []
        for index in range(highest + 1):
            slot = known.get(index)
            colour = slot.colour if slot is not None else None
            if colour is not None:
                table.append(_hex(colour))
                continue
            # **Ein Slot ohne eigene Farbe bekommt eine aus der Palette.** Hier
            # stand die Körperfarbe, und damit war das ganze Bemalen im Bild
            # folgenlos: Der Pinsel legt einen Slot mit ``colour=None`` an, zwei
            # Striche in zwei Slots ergaben zwei gleiche Einträge in dieser
            # Tabelle, und das Teil sah aus wie vorher. Dieselbe Lücke bei der
            # Schrift und bei „Slot zuweisen" ohne Farbeingabe — drei der vier
            # Stellen, die Slots anlegen. Der Docstring oben beschreibt das als
            # behoben; behoben war es nur für Slots, die schon eine Farbe hatten.
            table.append(slot_colour(index) or self._object_colour)
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

    def _remember_shadow(self, surface: Any, object_id: ObjectId, source: Any = None) -> None:
        """Was dieser Körper zum Schattenwurf beiträgt — geworfen wird später.

        Getrennt vom Setzen, weil ein Schatten wissen muss, worauf er fällt:
        welcher Körper unter welchem steht, steht erst fest, wenn alle
        gezeichnet sind.

        ``source`` ist das Netz, aus dem ``surface`` gebaut wurde — der
        Schlüssel, an dem ``_shadow_hulls_for`` erkennt, ob sich überhaupt
        etwas geändert hat.
        """
        if self.plotter is None or not self.contact_shadows:
            return
        hulls = self._shadow_hulls_for(object_id, surface, source)
        self._shadow_hulls[object_id] = hulls
        usable = [hull for hull in hulls if hull is not None and len(hull) >= 3]
        if not usable:
            return

        import numpy as np

        # **Der Auffang-Eintrag bleibt körperweise.** Er beantwortet „wer steht
        # unter wem" (§18.6), und das ist eine Frage über den Körper, nicht
        # über seine Stücke: Ein Turm auf einer Grundplatte wirft auf sie, und
        # ob die Platte aus einem Stück besteht, ändert daran nichts. Der
        # Umriss dafür kommt weiter aus allen Punkten zusammen.
        points = np.vstack([np.asarray(hull, dtype=float) for hull in usable])
        self._shadow_ground[object_id] = (
            float(points[:, 2].min()),
            float(points[:, 2].max()),
            outline_of(points),
        )

    def _place_shadows(self, direction: tuple[float, float]) -> None:
        """Die Schatten aller Körper aus den gemerkten Hüllen setzen."""
        if self.plotter is None:
            return
        for object_id, hulls in self._shadow_hulls.items():
            for part, hull in enumerate(hulls):
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
                            # Der Name trägt jetzt auch das Stück: Zwei Schatten
                            # desselben Körpers auf derselben Fläche hätten sonst
                            # denselben Namen, und pyvista ersetzt gleichnamige
                            # Aktoren — von drei Haken bliebe einer.
                            name=f"shadow:{object_id}:{part}:{index}",
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
        # Eine einzelne Platte heißt ein Bett; „Alle" heißt so viele, wie die
        # Szene belegt. ``show_scene`` zieht die Kulisse nach, sobald sich die
        # Zahl ändert — und ``_plate`` ist gesetzt, bevor sie gezählt wird.
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

    def _view_offset(self, entry: Any, result: EvaluationResult) -> Any:
        """Alles, was einen Körper in der Ansicht von seinem Ort in der Szene
        wegrückt: das Auseinanderziehen (§18.8) und die Platte (§25).

        An einer Stelle zusammengefasst, damit jede Zeichenstelle beides
        bekommt oder keines. Merkmalsfläche, Merkmalsbeschriftung, Griffscheibe
        und Differenzvorschau gehen inzwischen mit; was weiter **nicht**
        mitgeht, sind Maße und Schnittebene — sie folgten schon dem
        Auseinanderziehen nicht, und das gehört zusammen behoben, nicht halb.
        """
        return self._exploded(entry, result) + self._plate_offset(entry)

    def _plate_offset(self, entry: Any) -> Any:
        """Die Verschiebung, mit der die Platte dieses Körpers gezeichnet wird.

        Null, solange eine einzelne Platte betrachtet wird: dann steht ein Bett
        im Bild, und darauf gehört das, was darauf liegt — an seinen Ort.
        """
        import numpy as np

        if self._plate >= 0 or self._beds_drawn < 2 or self._bed_extent is None:
            return np.zeros(3)
        return np.asarray(plate_shift(getattr(entry, "plate", 0), self._bed_extent[0]), dtype=float)

    def _bed_outline_for(self, object_id: ObjectId) -> Any:
        """Der Umriss des Bettes, auf dem dieser Körper gezeichnet wird."""
        assert self._bed_extent is not None
        outline = bed_outline(*self._bed_extent)
        entry = self._result.scene.objects.get(object_id) if self._result else None
        if entry is None:
            return outline
        return outline + self._plate_offset(entry)[:2]

    def _from_view(self, point: Vec3) -> Vec3:
        """Ein Punkt aus der Ansicht zurück in die Szene (§25).

        Was der Nutzer trifft, liegt auf dem Bett, das er sieht; was eine
        Operation als Ort bekommt, muss auf dem Bett liegen, das die Szene
        kennt. Ohne diese Umkehrung setzte ein Klick auf Platte 2 die Bohrung
        eine Bettbreite daneben — und weil dort meistens nichts ist, hätte er
        stumm nichts getan.
        """
        if self._plate >= 0 or self._beds_drawn < 2 or self._bed_extent is None:
            return point
        width = self._bed_extent[0]
        plate = plate_at(point[0], self._beds_drawn, width)
        shift = plate_shift(plate, width)
        return (point[0] - shift[0], point[1] - shift[1], point[2] - shift[2])

    def _plate_count(self) -> int:
        """Wie viele Platten die Szene belegt (§25)."""
        if self._result is None:
            return 1
        plates = {entry.plate for entry in self._result.scene.objects.values()}
        return max(plates, default=0) + 1

    def _beds_for_view(self) -> int:
        """Wie viele Betten gezeichnet werden sollen — eines, wenn eine einzelne
        Platte betrachtet wird.
        """
        return 1 if self._plate >= 0 else self._plate_count()

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
        if float(np.linalg.norm(away)) <= EPS_GEOM:
            return np.zeros(3)
        # Der Versatz wächst mit dem Abstand von der Mitte — das ist die
        # Absicht, keine fehlende Normierung: Weiter außen liegende Teile
        # rücken weiter, und die Anordnung bleibt ähnlich.
        return away * self._explosion

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
        """Eine für die Anzeige dezimierte Version ab der Schwelle aus §31.

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
        found = self._display_cache.pop(key, None)
        if found is None:
            found = decimate(mesh, DISPLAY_DECIMATION_TARGET)
        # Die zuletzt gezeigten behalten, den ältesten verdrängen: ein
        # dezimiertes Netz ist teuer zu halten — aber genau eines zu halten
        # hieß, dass zwei große Körper einander bei jedem Aufbau verdrängten.
        self._display_cache[key] = found
        while len(self._display_cache) > DISPLAY_CACHE_KEPT:
            self._display_cache.pop(next(iter(self._display_cache)))
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
        highlighted = None if self._sketch_frame is not None else self.highlighted_object()
        for identifier, actor in self._actors.items():
            if self._map is not None and identifier == self._map_object:
                # Eine Karte besitzt die Farbe ihres Körpers; die Auswahl zeigt sich
                # stattdessen im Objektbaum und in der Statusleiste (§19.1).
                continue
            actor.prop.color = SELECTED_COLOUR if identifier == highlighted else self._object_colour

    def show_build_volume(self, profile: Profile) -> None:
        """Das Bett als Raster in echter Größe, der Bauraum als Eckwinkel
        (§18.6) — **je Platte eines** (§25).

        **Kein Aufruf hier setzt die Kamera.** Der Bauraum ist Kulisse, und
        pyvista passt bei der ersten Netzfläche einer leeren Szene von selbst
        ein — das machte jedes Einpassen auf die Körper wieder zunichte, weil
        die Kulisse danach gezeichnet wurde.

        **Warum mehrere Betten.** Jede Platte hat ihren eigenen Nullpunkt, und
        die Anordnung setzt Platte 2 an denselben Ort wie Platte 1. Ein Bett
        für alle heißt darum: die Teile stehen ineinander, und wer zwei Platten
        angelegt hat, sieht eine. Gemeldet als „bei Projekten mit mehreren
        Platten sehe ich trotzdem nur eine" — und es war genau das.
        """
        width, depth, height = profile.printer.build_volume
        # Gemerkt, weil der Kontaktschatten an dieser Kante geschnitten wird —
        # und weil ``_fit_once_for`` daran erkennt, ob es auf einer leeren Szene
        # überhaupt etwas einzupassen gibt. Vor dem Plotter-Zweig, aus demselben
        # Grund wie dort: dass ein Bauraum gilt, ist eine Aussage über die
        # Szene und nicht über VTK.
        self._bed_extent = (width, depth)
        self._build_volume = (width, depth, height)
        self._profile = profile
        # Die Zahl **vor** dem Plotter-Zweig, damit ``_plate_offset`` offscreen
        # dasselbe sagt wie im Bild: sonst hinge die Verschiebung an VTK, und
        # kein Test käme an sie heran.
        beds = self._beds_for_view()
        self._beds_drawn = beds
        if self.plotter is None:
            return
        import pyvista as pv

        for actor in self._frame_actors:
            self.plotter.remove_actor(actor, render=False)
        self._frame_actors.clear()
        self._ground_actors.clear()
        for plate in range(beds):
            self._draw_one_bed(pv, plate, plate_shift(plate, width)[0], width, depth, height)
        # Der Zustand entscheidet, nicht die Aufruf-Reihenfolge: Während des
        # Zeichnens tritt der Boden ab (siehe ``set_sketching``), und ein hier
        # frisch gebautes Bett hat sich daran zu halten — sonst liegen Bett-
        # und Zeichenraster wieder übereinander, sobald eine Platte dazukommt.
        if self._sketch_frame is not None:
            for actor in self._ground_actors:
                actor.SetVisibility(False)
        self._draw()

    def _draw_one_bed(
        self,
        pv: Any,
        plate: int,
        shift: float,
        width: float,
        depth: float,
        height: float,
    ) -> None:
        """Ein Bett samt Bauraum und Maßstab, ``shift`` Millimeter nach +X.

        Die Namen der Actors tragen die Plattennummer: ``name=`` ersetzt in
        pyvista, was denselben Namen hat — mit festen Namen bliebe von vier
        Betten eines übrig.
        """
        if self.plotter is None:
            return

        # Ein gefüllter Grund unter dem Raster. Bis hierhin war die Platte ein
        # Drahtgitter über dem Hintergrund — hübsch, aber ohne Fläche: ein
        # Schatten darauf fiel auf nichts und war im Bild schlicht nicht da.
        # Knapp unter null, damit er nicht mit dem Raster um dieselbe Tiefe
        # streitet.
        surface = self.plotter.add_mesh(
            pv.Plane(
                center=(shift, 0.0, -BED_SURFACE_DROP),
                direction=(0.0, 0.0, 1.0),
                i_size=width,
                j_size=depth,
            ),
            color=self._bed_surface,
            ambient=0.45,
            diffuse=0.55,
            specular=0.0,
            name=f"bed_surface_{plate}",
            render=False,
            reset_camera=False,
            pickable=False,
        )
        # **Von unten schaut man hindurch** (Robert, 23.08.2026): Wer eine
        # Unterseite bearbeitet, dreht die Ansicht unter das Teil — und sah
        # dort die Platte statt des Teils.
        #
        # ``culling`` und nicht ``opacity``: Die Fläche gibt es, damit ein
        # Schatten auf etwas fällt, und eine durchscheinende Platte nähme ihm
        # den Grund. Die Ebene zeigt mit ``direction=(0, 0, 1)`` nach oben;
        # von unten sieht man ihre **Rückseite**, und die lässt sich wegwerfen,
        # ohne die Vorderseite anzufassen. Gemessen von 3d-druck-3a an einem
        # roten Körper über grauer Platte, in Bildpunkten gezählt:
        #
        #     ohne culling   von unten:    0 rot   von oben: 4014
        #     culling back   von unten: 2417 rot   von oben: 4014
        #
        # Von oben ändert sich nichts — dieselbe Zahl, also bleiben Fläche und
        # Schatten, wie sie waren.
        surface.prop.culling = "back"
        self._frame_actors.append(surface)
        self._ground_actors.append(surface)
        bed = pv.Plane(
            center=(shift, 0.0, 0.0),
            direction=(0.0, 0.0, 1.0),
            i_size=width,
            j_size=depth,
            i_resolution=max(1, int(width // 10)),
            j_resolution=max(1, int(depth // 10)),
        )
        grid = self.plotter.add_mesh(
            bed,
            color=self._bed_colour,
            style="wireframe",
            opacity=0.35,
            name=f"bed_{plate}",
            render=False,
            reset_camera=False,
        )
        self._frame_actors.append(grid)
        self._ground_actors.append(grid)
        import numpy as np

        segments = volume_edges(width, depth, height)
        points = np.asarray([point for pair in segments for point in pair], dtype=float)
        points[:, 0] += shift
        lines = np.hstack([[2, 2 * index, 2 * index + 1] for index in range(len(segments))])
        self._frame_actors.append(
            self.plotter.add_mesh(
                pv.PolyData(points, lines=lines),
                color=self._bed_colour,
                opacity=0.35,
                line_width=1,
                name=f"build_volume_{plate}",
                render=False,
                reset_camera=False,
                pickable=False,
            )
        )

        marks = bed_scale(width, depth)
        anchors = np.asarray([point for point, _text in marks], dtype=float)
        anchors[:, 0] += shift
        self._frame_actors.append(
            self.plotter.add_point_labels(
                anchors,
                [text for _point, text in marks],
                text_color=self._bed_colour,
                font_size=9,
                show_points=False,
                shape=None,
                always_visible=True,
                name=f"bed_scale_{plate}",
                render=False,
                reset_camera=False,
            )
        )

    # --- theme (§19.3) ----------------------------------------------------------

    def set_theme(self, theme: str) -> None:
        """Hintergrund-, Körper- und Bettfarben folgen dem Anwendungsthema."""
        colours = viewport_colours(theme)  # type: ignore[arg-type]
        self._object_colour = colours["object"]
        self._bed_colour = colours["bed"]
        self._bed_surface = colours["bed_surface"]
        self._edge_colour = colours["edge"]
        # **Direkt aus THEMES und nicht über ``viewport_colours``**, wie es
        # ``ViewBar.set_theme`` daneben auch tut. Der Grund ist eine Zusage:
        # ``test_theme_and_palette`` nagelt die Schlüsselmenge von
        # ``viewport_colours`` auf genau sechs fest, und das ist richtig so —
        # sie beschreibt, was die *Szene* braucht. Raster und Zeichnung der
        # Skizze sind dieselben Farben, die die Zeichenfläche benutzt
        # (``grid_minor`` und ``text``); sie hier zu einer siebten und achten
        # Szenenfarbe zu machen, hieße denselben Wert zweimal zu benennen.
        exact = THEMES["light" if theme == "light" else "dark"]
        # Gegen den Verlauf trägt ``grid_minor`` nicht zuverlässig. Beide
        # Rasterstufen benutzen deshalb den sichtbaren Farbton; ihre Deckkraft
        # und Breite machen daraus leise Zwischenlinien und klare Fünfermarken.
        self._grid_minor_colour = exact["grid_major"]
        self._grid_major_colour = exact["grid_major"]
        self._sketch_colour = text_colour("info", colours["top"])
        self._axis_x_colour = text_colour("axis_x", colours["top"])
        self._axis_y_colour = text_colour("axis_y", colours["top"])
        self._sketch_label_colour = exact["text"]
        self._sketch_label_background = exact["window"]
        self.banner.set_theme(theme)
        self.view_bar.set_theme(theme)
        self.drag_bar.set_theme(theme)
        self.plane_picker.set_theme(theme)
        self.sketch_selection.set_theme(theme)
        self.sketch_action.set_theme(theme)
        if self.plotter is None:
            return
        self.plotter.set_background(colours["bottom"], top=colours["top"])
        # Die Achsenanzeige trägt eine Schriftfarbe und muss deshalb mit dem
        # Thema wechseln — eine schwarze Beschriftung auf dunklem Grund ist
        # keine Auskunft.
        self._add_orientation_widget(theme)
        # Bett und Bauraum sind eigene Aktoren, und ``show_scene`` baut sie nur
        # bei geänderter Plattenzahl neu — ein Themenwechsel ließe sie sonst in
        # den alten Farben stehen, bis die nächste Auswertung kommt: eine fast
        # schwarze Bettfläche auf hellem Grund.
        if self._profile is not None:
            self.show_build_volume(self._profile)
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
        self._pending_plane = None
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
        self._pending_plane = None
        self._redraw_measurements()

    def set_splitting(self, active: bool) -> None:
        """Macht aus Klicks die Enden einer Trennlinie (§25).

        Dasselbe Picking wie beim Messen; was sich ändert, ist, wer den Punkt
        bekommt. Beim Ausschalten geht die gezeichnete Linie weg — sie ist eine
        Vorschau und kein Dokumentzustand (Regel 2), und eine Linie, die ein
        geschlossenes Werkzeug überlebte, wäre ein Strich ohne Knopf dazu.
        """
        self._splitting = active
        if not active:
            self.clear_split_line()
        self._update_cursor()

    def show_split_line(
        self,
        points: Sequence[Vec3],
        *,
        plane: SectionPlane | None = None,
        target: ObjectId | None = None,
    ) -> None:
        """Zeichnet, was bisher geklickt wurde.

        Ein Punkt ist eine Kugel in der Auswahlfarbe, zwei sind eine Linie mit
        einer Kugel an jedem Ende. Ohne die erste Kugel sieht ein Klick auf ein
        großes Teil aus, als sei nichts passiert — und der zweite Klick landet
        dann irgendwo, weil niemand weiß, wo der erste war.

        Sobald die Linie vollständig ist, liegt zusätzlich die **ganze
        Schnittebene** als durchscheinende, umrandete Fläche im Zielkörper. Eine
        Linie allein beantwortet nicht, welche Seite und welche Neigung durch
        das Modell laufen; die Fläche tut es. Farbe und Umriss kodieren dieselbe
        Aussage doppelt (Regel 18).

        Beide Actors tragen einen Namen: Wo ``clear_split_line`` einmal nicht
        gelaufen ist, ersetzt pyvista den gleichnamigen, statt einen zweiten
        danebenzulegen.
        """
        import numpy as np

        self.clear_split_line()
        if self.plotter is None or not points:
            return

        entry = self._result.scene.objects.get(target) if self._result and target else None
        shift = (
            self._view_offset(entry, self._result)
            if entry is not None and self._result is not None
            else np.zeros(3)
        )
        # Die Operation speichert Szenenkoordinaten. In „Alle Platten“ steht
        # der Körper für die Anzeige versetzt; Linie und Ebene müssen genau
        # denselben reinen Anzeigeversatz bekommen, sonst erscheinen sie auf
        # Platte 1 statt auf dem angeklickten Teil.
        marks = np.asarray(points, dtype=float) + shift
        self._split_actors.append(
            self.plotter.add_points(
                marks,
                color=SELECTED_COLOUR,
                point_size=14,
                render_points_as_spheres=True,
                name="split:ends",
                render=False,
                reset_camera=False,
                pickable=False,
            )
        )
        if len(points) >= 2:
            line = self.plotter.add_lines(
                marks[:2], color=SELECTED_COLOUR, width=3, name="split:line"
            )
            if hasattr(line, "PickableOff"):
                line.PickableOff()
            self._split_actors.append(line)
        if plane is not None and entry is not None:
            bounds = entry.mesh.bounds
            patch = plane_patch(bounds.minimum, bounds.maximum, plane)
            if patch:
                import pyvista as pv

                corners = np.asarray(patch, dtype=float)
                centre = np.mean(corners, axis=0)
                corners = centre + SPLIT_PLANE_SCALE * (corners - centre) + shift
                face = np.concatenate(
                    (np.asarray([len(corners)], dtype=np.int64), np.arange(len(corners)))
                )
                surface = pv.PolyData(corners, faces=face)
                self._split_actors.append(
                    self.plotter.add_mesh(
                        surface,
                        color=SELECTED_COLOUR,
                        opacity=0.22,
                        show_edges=True,
                        edge_color=SELECTED_COLOUR,
                        line_width=2,
                        lighting=False,
                        name="split:plane",
                        render=False,
                        reset_camera=False,
                        pickable=False,
                    )
                )
        self.plotter.render()

    def clear_split_line(self) -> None:
        """Nimmt die Vorschau wieder heraus."""
        if self.plotter is None:
            self._split_actors.clear()
            return
        for actor in self._split_actors:
            self.plotter.remove_actor(actor, render=False)
        self._split_actors.clear()
        self.plotter.render()

    def view_direction(self) -> Vec3:
        """Wohin die Kamera schaut — von ihr weg auf den Brennpunkt zu.

        Die Richtung, die aus einer gezeichneten Linie eine Ebene macht
        (:func:`app.core.geom.section.plane_through`). Sie wird **einmal**
        abgefragt, wenn die Linie fertig ist, und wandert dann als Zahl in die
        Operation: Eine Op, die die Kamera läse, gäbe beim zweiten Auswerten
        ein anderes Ergebnis (§11.2).

        Ohne Plotter — offscreen — der Blick aus der Vorgabestellung. Eine
        Ausnahme, die eine Rechnung überspringt, wäre ein Test, der nie etwas
        prüft.
        """
        import numpy as np

        if self.plotter is None:
            return (0.0, 1.0, 0.0)
        camera = self.plotter.camera
        forward = np.asarray(camera.focal_point, dtype=float) - np.asarray(
            camera.position, dtype=float
        )
        length = float(np.linalg.norm(forward))
        if length <= 0.0:
            return (0.0, 1.0, 0.0)
        forward = forward / length
        return (float(forward[0]), float(forward[1]), float(forward[2]))

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
        if self._sketch_frame is not None:
            if self._hover_at is not None:
                x, y = self._hover_at
                ready_to_pull = (
                    self._sketch_pull_offer is not None and self._sketch_pull_offer() == "ready"
                )
                # Der ausdrückliche Pfeil/Kreuz-Griff gewinnt immer. So kann
                # seine sichtbare Fläche nicht in einen Kamerazug fallen.
                if ready_to_pull and self.pull_handle_reach(x, y) <= PULL_HIT_PIXELS:
                    return "move"
                # Danach vorhandene Geometrie: Im Auswahlwerkzeug bedeutet
                # ein Griff auf Linie oder Punkt bearbeiten, nicht die Kamera
                # bewegen und nicht versehentlich eine Höhe ziehen.
                hit = self._sketch_hit(x, y)
                if (
                    hit is not None
                    and self._sketch_edit_ready is not None
                    and self._sketch_edit_ready(hit)
                ):
                    return "move"
                if ready_to_pull and self.grip_reach(x, y) <= CURSOR_PIXELS:
                    return "move"
            # **Ganz vorn, wie im Klick selbst.** Im Skizzenmodus meint jeder
            # Klick eine Stelle auf der Ebene; ein Zeiger, der daneben ein
            # Merkmal verspricht, verspricht etwas, das nicht eintritt. Die
            # Rolle ist dieselbe wie auf der Zeichenfläche (`draw`), damit
            # derselbe Handgriff dasselbe Bild hat.
            return "draw"
        if self._splitting:
            # Das Fadenkreuz des Messens: Beide setzen einen Punkt, der eine
            # Strecke aufspannt, und derselbe Handgriff soll denselben Zeiger
            # haben.
            return "measure"
        if self._boning:
            # Derselbe Zeiger wie beim Formen: Beide setzen einen Punkt auf der
            # Fläche, und ein dritter Ring wäre eine Unterscheidung ohne
            # Unterschied.
            return "sculpt"
        if self._sculpting:
            return "sculpt"
        if self._measure_mode != "off":
            return "measure"
        return "feature" if self._hover_feature else "select"

    def _means_a_feature(self) -> bool:
        """Ob ein Klick jetzt **auswählt**, statt eine Stelle zu setzen.

        Gelesen aus :meth:`_resting_role` und nicht aus den Flaggen selbst: Die
        Rangfolge der Werkzeuge steht dort schon, und eine zweite Aufzählung
        daneben liefe irgendwann auseinander — dann setzte ein Pinselstrich
        seine Farbe an der Stelle, an der der Zeiger eine Bohrung versprach.
        """
        return self._resting_role() in {"feature", "select"}

    def set_drag_cursor(self, role: str | None) -> None:
        """Meldet, was die Kamera gerade tut — vom Interaktionsstil gerufen.

        ``None`` heißt: Taste losgelassen, zurück zum Ruhezustand.
        """
        self._dragging_role = role
        if role is not None:
            # Während eines Zugs ist gleichgültig, was unter dem Zeiger liegt,
            # und die Suche danach wäre die teuerste Stelle im Zug.
            self._hover_timer.stop()
            self._set_hover_target(None, None)
        self._update_cursor()

    def _set_hover_target(self, object_id: ObjectId | None, feature_id: FeatureId | None) -> None:
        """Hover-Zeiger, sichtbare Fläche und Beschriftung gemeinsam setzen."""
        found = feature_id is not None
        target_changed = (object_id, feature_id) != (
            self._hovered_object,
            self._hovered_feature,
        )
        role_changed = found != self._hover_feature
        if not target_changed and not role_changed:
            return
        self._hover_feature = found
        self._hovered_object = object_id if found else None
        self._hovered_feature = feature_id
        if target_changed and self.plotter is not None:
            self._redraw_features()
            self._draw()
        if role_changed:
            self._update_cursor()

    def _look_under_pointer(self) -> None:
        """Sucht nach der Ruhepause, ob unter dem Zeiger ein Merkmal liegt.

        Gefragt wird :meth:`_aim_at` — dieselbe Rechnung wie beim Klick, samt
        dem Blick durch eine Bohrung hindurch. Vorher stand hier der
        Tiefenpuffer (:func:`_world_under`), weil er ohnehin im Bild steht und
        ein Pick die Szene erneut durchläuft. Das kostet nun einen Zell-Pick,
        aber **nur nach einer Ruhepause** und nicht bei jeder Mausbewegung —
        und die Zusage darunter ist es wert: Ein Zeiger, der die Merkmalsform
        über einer Bohrung zeigt, wo der Klick sie nicht wählt, verspricht
        etwas, das nicht eintritt.
        """
        if self.plotter is None or self._hover_at is None or self._dragging_role:
            return
        x, y = self._hover_at
        if self._sculpting:
            # Beim Formen ist unter dem Zeiger nie ein Merkmal gemeint,
            # sondern immer eine Stelle. Der Ring zeigt sie; die Suche nach
            # Merkmalen bliebe hier nur teuer.
            self._draw_brush()
            return
        point = self._aim_at(x, y)
        # Dieselbe Frage, die der Klick stellt, und mit derselben Rechnung: Ein
        # Zeiger, der die Merkmalsform über einer Bohrung zeigt, während der
        # Klick den Körper wählt, verspricht etwas, das nicht eintritt. So wird
        # die gestufte Tiefe zugleich sichtbar, ohne dass irgendwo ein Satz
        # darüber stehen muss.
        # ``_from_view`` aus demselben Grund wie beim Klick (§25): Der Zeiger
        # muss dieselbe Stelle befragen, die der Klick trifft, sonst zeigt er
        # auf Platte 2 die Form für einen Körper, der dort nicht liegt.
        object_id: ObjectId | None = None
        feature_id: FeatureId | None = None
        if point is not None:
            object_id, feature_id = self._click_target(self._from_view(point))
        self._set_hover_target(object_id, feature_id)

    def _note_pointer(self, position: Any) -> None:
        """Merkt sich, wo die Maus steht, und stößt die Suche neu an.

        VTK zählt seine Y-Achse von unten, Qt von oben — ohne die Umrechnung
        findet die Suche das Merkmal am gespiegelten Ort, was in der Mitte des
        Bildes zufällig oft genug stimmt, um lange nicht aufzufallen.
        """
        if self.plotter is None:
            return
        # Dieselbe Rechnung wie pyvistas ``rwi``: Es multipliziert jede
        # Mausposition mit ``devicePixelRatio``, bevor sie an VTK geht, und
        # setzt die Renderfenstergröße ebenso. Wer hier in Qt-Logikpunkten
        # rechnet, fragt auf einem skalierten Bildschirm die falsche Stelle —
        # Fangkreuz und Vorschau stünden neben dem Klick. Bei dpr 1,0 ändert
        # der Faktor nichts.
        ratio = float(self.plotter.interactor.devicePixelRatioF())
        height = self.plotter.interactor.height() * ratio
        self._hover_at = (int(position.x() * ratio), int(height - position.y() * ratio))
        # **Die Skizzenvorschau wartet nicht auf die Ruhepause** (§30.1, P4).
        # Die Merkmalssuche darunter tut es aus gutem Grund: Sie kostet einen
        # Zell-Pick, und den bei jeder Bewegung zu zahlen hieße, den
        # Tiefenpuffer hundertmal in der Sekunde im Qt-Hauptthread zu lesen.
        # Der Schnitt mit der Zeichenebene kostet nichts dergleichen — er ist
        # eine Division —, und eine Linie, die dem Zeiger erst nach neunzig
        # Millisekunden folgt, sieht aus wie ein hängendes Programm.
        if self._sketch_frame is not None:
            if self._pull_from is not None:
                # **Während eines Zugs am Ziehgriff hält die Zeichnung still.**
                # Sonst zöge die Vorschau der angefangenen Linie dem Zug
                # hinterher, und im Bild wüchsen zwei Dinge zugleich.
                return
            # **Und der Zeiger wird hier gesetzt, nicht nach einer Ruhepause.**
            # Der Weg über ``_hover_timer`` gilt der Merkmalssuche und läuft im
            # Skizzenmodus gar nicht; ohne diese Zeile erfuhr niemand, dass der
            # Umriss ein Griff ist. Teuer ist das nicht: Die Frage kostet erst
            # etwas, wenn der Griff überhaupt angeboten wird (Querschau), und
            # gesetzt wird nur, wenn die Rolle wechselt.
            self._update_cursor()
            hit = self._sketch_hit(*self._hover_at)
            if hit is not None:
                self.sketchPointHovered.emit(hit)
            return
        self._hover_timer.start()

    def _forget_pointer(self) -> None:
        """Die Maus hat das Bild verlassen."""
        self._hover_timer.stop()
        self._hover_at = None
        self._set_hover_target(None, None)

    def _on_paint_drag(self, x: int, y: int, fresh: bool) -> None:
        """Ein Zug des gedrückten Pinsels — einer je halbem Radius (§18.11).

        Der Mindestabstand hält die Zugzahl im Zaum: hundert Züge je
        Zentimeter wären Rauschen, kein Strich. Er gilt je Strich, nicht
        darüber hinaus — sonst schluckte ein neuer Ansatz neben dem alten
        Endpunkt seinen ersten Zug. Die Kosten sprechen nicht dagegen:
        ``apply_strokes`` liegt gemessen bei zwei Millisekunden für 25 Züge.
        """
        if fresh:
            self._last_drag_stroke = None
        point = self._world_at(x, y)
        if point is None:
            return
        last = self._last_drag_stroke
        spacing = self._brush_radius * 0.5
        if last is not None and spacing > 0.0 and math.dist(last, point) < spacing:
            return
        self._last_drag_stroke = point
        self._on_picked(point)

    def _on_picked(self, point: Any) -> None:
        picked = self._from_view((float(point[0]), float(point[1]), float(point[2])))
        if self._splitting:
            self.splitPointRequested.emit(picked)
            return
        if self._boning:
            self.boneRequested.emit(picked)
            return
        if self._sculpting:
            self.sculptRequested.emit(picked)
            return
        if self._measure_mode == "off":
            # Nicht am Messen: die Auswahl, gestuft (:meth:`_click_target`).
            # Ein Klick daneben hebt sie auf — sonst gäbe es keinen Weg, sie
            # ohne den Baum wieder loszuwerden.
            if not self._select_at(picked):
                # Die Stelle selbst geht nur hinaus, wenn der Klick kein
                # Merkmal getroffen hat: Ein offener Dialog, der nach einer
                # Position fragt, trägt sie ein. Wer ein Merkmal anklickt,
                # meint das Merkmal und bekommt ``featurePicked``.
                self.pointPicked.emit(picked)
            return

        if self._measure_mode == "angle":
            self._measure_plane_angle(picked)
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

    def _measure_plane_angle(self, point: Vec3) -> None:
        """Nimmt zwei erkannte Ebenen und misst ihre Normalen (§18.3)."""
        object_id = self._object_at(point) or self._selected
        entry = self._result.scene.objects.get(object_id) if self._result and object_id else None
        feature_id = self._feature_at(point)
        feature = entry.features.get(feature_id) if entry is not None and feature_id else None
        normal = feature.params.get("normal") if feature is not None else None
        centre = feature.params.get("centre") if feature is not None else None
        if feature is None or feature.kind != "face" or normal is None or centre is None:
            self.measurementStatus.emit(
                tr("Für eine Winkelmessung zwei erkannte ebene Flächen anklicken.")
            )
            return

        direction = tuple(float(value) for value in normal)
        anchor = tuple(float(value) for value in centre)
        if len(direction) != 3 or len(anchor) != 3:
            self.measurementStatus.emit(
                tr("Für eine Winkelmessung zwei erkannte ebene Flächen anklicken.")
            )
            return
        plane = (direction, anchor)
        if self._pending_plane is None:
            self._pending_plane = plane
            self.measurementStatus.emit(tr("Erste Ebene gewählt — zweite Ebene anklicken."))
            return

        first_direction, first_anchor = self._pending_plane
        self._add(
            Measurement(
                kind="angle",
                value=angle_between(first_direction, plane[0]),
                points=(first_anchor, plane[1]),
            )
        )
        self._pending_plane = None

    def _add(self, measurement: Measurement) -> None:
        self.measurements.add(measurement)
        self._redraw_measurements()
        self.measurementTaken.emit(measurement)

    def _in_view(self, object_id: ObjectId, entry: Any) -> bool:
        """Ob dieser Körper gerade im Bild ist — und damit ein Klickziel.

        Dieselbe Dreifach-Bedingung, mit der :meth:`show_scene` zeichnet:
        ``visible``, nicht ausgeblendet (§18.8), auf der betrachteten Platte
        (§25). Jede Klick-Rechnung fragt sie, denn was nicht im Bild ist, kann
        niemand meinen — ohne den Filter wählte ein Klick ausgeblendete Körper
        und Körper fremder Platten, und die nächste Operation traf ein Teil,
        das niemand sieht.
        """
        if not entry.visible or object_id in self._hidden:
            return False
        return self._plate < 0 or entry.plate == self._plate

    def _nearest_mesh(self, point: Vec3) -> Any:
        """Das Objekt, zu dem ein Klick gehört — das, dessen Hüllquader ihm am
        nächsten ist.
        """
        if self._result is None:
            return None
        best: Any = None
        best_offset = float("inf")
        for object_id, entry in self._result.scene.objects.items():
            if not self._in_view(object_id, entry):
                continue
            centre = entry.mesh.bounds.centre
            offset = sum((a - b) ** 2 for a, b in zip(centre, point, strict=True))
            if offset < best_offset:
                best_offset = offset
                best = entry.mesh
        return best

    def object_at(self, point: Vec3) -> ObjectId | None:
        """Welcher Körper an dieser Stelle liegt.

        Für Werkzeuge, die ihr Ziel aus einem Klick ableiten statt aus der
        Auswahl — das Trennen tut das (§25). Die Ansicht weiß es ohnehin; sie
        behielt es bisher nur für sich.
        """
        return self._object_at(point)

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
            if not self._in_view(object_id, entry):
                continue
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
            # Über ``labels`` wie jede Anzeige: Die MeasureBar schrieb
            # „2,3622 in", das Bild daneben „60 mm" — zwei Zahlen für dieselbe
            # Messung, und ``grad`` stand fest deutsch da (Regel 20).
            label = (
                localised(f"{entry.shown:g}°")
                if entry.kind == "angle"
                else length(float(entry.value))
            )
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
        if self._selection_marking_hidden() or self._selected_feature is not None:
            return None
        return self._selected

    def highlighted_faces(self) -> tuple[int, ...]:
        """Die Dreiecke, die als gewähltes Merkmal aufleuchten (§18.5).

        Leer heißt: nichts hervorzuheben — kein Merkmal gewählt, der Körper
        ausgeblendet, oder ein Merkmal ohne zugeordnete Dreiecke wie eine
        Kante aus dem exakten Kern. Gezählt wird im Netz der Szene, nicht im
        dezimierten Anzeigenetz (§18.9).
        """
        if self._selection_marking_hidden():
            return ()
        return self._face_indices(self._selected, self._selected_feature)

    def _selection_marking_hidden(self) -> bool:
        """Ob die Differenzfarben gerade Vorrang vor Auswahl und Hover haben.

        „Entfernt" ist orange und die Auswahl bernsteinfarben. Beides zugleich
        auf derselben Bohrung ergibt keine dritte, lesbare Bedeutung. Während
        die Vorschau sichtbar ist, tragen deshalb nur hinzugefügt/entfernt die
        Modellfarben; Objektbaum, Beschriftung und Statuszeile halten die
        Auswahl weiter fest. Beim gehaltenen Vorher-Vergleich kehrt die
        Auswahlmarkierung zurück.
        """
        return self._difference is not None and not self._difference_held

    def _face_indices(
        self, object_id: ObjectId | None, feature_id: FeatureId | None
    ) -> tuple[int, ...]:
        """Gültige Dreiecke eines sichtbaren Merkmals, unabhängig von seiner Rolle."""
        if feature_id is None or self._result is None or object_id is None:
            return ()
        entry = self._result.scene.objects.get(object_id)
        if entry is None or not self._in_view(object_id, entry):
            return ()
        feature = entry.features.get(feature_id)
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
        self._redraw_hover_patch()
        for actor in self._feature_actors:
            self.plotter.remove_actor(actor, render=False)
        self._feature_actors.clear()
        # Ohne Überlagerung bleibt das **gewählte** Merkmal beschriftet: seine
        # Fläche leuchtet in der Auswahlfarbe, und eine Aussage allein über
        # Farbe wäre genau die, die Regel 18 verbietet.
        shown: dict[tuple[ObjectId, FeatureId], Feature] = {}
        if self._selected is not None:
            for feature_id, feature in self._features_of_selection().items():
                if self._feature_overlay or feature_id == self._selected_feature:
                    shown[(self._selected, feature_id)] = feature
        # Beim Überfahren bleibt der Name auch bei ausgeschalteter
        # Überlagerung sichtbar. Farbe plus Merkmalszeiger allein würden sagen,
        # *dass* dort etwas liegt, aber nicht *was* (§19.1).
        if self._hovered_object is not None and self._hovered_feature is not None:
            hovered = self._features_of(self._hovered_object).get(self._hovered_feature)
            if hovered is not None:
                shown[(self._hovered_object, self._hovered_feature)] = hovered
        if not shown:
            return

        import numpy as np

        # Beschriftet wird dort, wo gezeichnet wird: Die Merkmalsfläche geht
        # durch ``_view_offset``, ihr Etikett stand daneben auf den nackten
        # Szenenkoordinaten — dieselbe Bohrung, zwei Orte, eine Bettbreite
        # auseinander (§25, §18.8).
        points: list[list[float]] = []
        labels: list[str] = []
        for (object_id, feature_id), feature in shown.items():
            centre = feature.params.get("centre")
            if centre is None:
                continue
            entry = self._result.scene.objects.get(object_id) if self._result is not None else None
            if entry is None or not self._in_view(object_id, entry):
                continue
            shift = (
                self._view_offset(entry, self._result)
                if entry is not None and self._result is not None
                else np.zeros(3)
            )
            points.append(
                [float(value) + float(moved) for value, moved in zip(centre, shift, strict=True)]
            )
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
        corners += self._view_offset(entry, self._result)
        count = len(triangles)
        faces = np.hstack(
            [np.full((count, 1), 3, dtype=np.int64), np.arange(count * 3).reshape(count, 3)]
        ).ravel()
        feature = (
            entry.features.get(self._selected_feature)
            if self._selected_feature is not None
            else None
        )
        hole_surface = feature is not None and feature.kind == "hole"
        side_kwargs: dict[str, Any] = (
            {
                "opacity": SELECTED_HOLE_OPACITY,
                "backface_params": {
                    "color": SELECTED_COLOUR,
                    "opacity": SELECTED_HOLE_OPACITY,
                },
            }
            if hole_surface
            else {"backface_params": {"color": SELECTED_COLOUR}}
        )
        self._feature_patch = self.plotter.add_mesh(
            pv.PolyData(corners, faces),
            color=SELECTED_COLOUR,
            **side_kwargs,
            lighting=False,
            name="feature-patch",
            render=False,
            reset_camera=False,
            pickable=False,
        )

    def _redraw_hover_patch(self) -> None:
        """Das Merkmal unter dem Zeiger zeigen, ohne es als gewählt auszugeben.

        Die Auswahl ist deckend bernsteinfarben, Hover durchscheinend in der
        Merkmalsfarbe. Ist dasselbe Merkmal bereits gewählt oder zeigt die
        Differenzansicht ihre eigenen Rollen, kommt keine zweite Fläche hinzu.
        """
        if self.plotter is None:
            return
        if self._hover_patch is not None:
            self.plotter.remove_actor(self._hover_patch, render=False)
            self._hover_patch = None
        if (
            self._selection_marking_hidden()
            or self._hovered_object is None
            or self._hovered_feature is None
            or (
                self._hovered_object == self._selected
                and self._hovered_feature == self._selected_feature
            )
        ):
            return
        indices = self._face_indices(self._hovered_object, self._hovered_feature)
        if not indices or self._result is None:
            return
        entry = self._result.scene.objects.get(self._hovered_object)
        raw = getattr(entry.mesh, "raw", None) if entry is not None else None
        if entry is None or raw is None:
            return

        import numpy as np
        import pyvista as pv

        chosen = np.asarray(indices, dtype=np.int64)
        triangles = np.asarray(raw.faces, dtype=np.int64)[chosen]
        normals = np.asarray(raw.face_normals, dtype=float)[chosen]
        corners = np.asarray(raw.vertices, dtype=float)[triangles.ravel()]
        lift = max(self._scene_size() * FEATURE_PATCH_LIFT, EPS_GEOM)
        corners += np.repeat(normals, 3, axis=0) * lift
        corners += self._view_offset(entry, self._result)
        count = len(triangles)
        faces = np.hstack(
            [np.full((count, 1), 3, dtype=np.int64), np.arange(count * 3).reshape(count, 3)]
        ).ravel()
        feature = entry.features.get(self._hovered_feature)
        hole_surface = feature is not None and feature.kind == "hole"
        hover_opacity = HOVERED_HOLE_OPACITY if hole_surface else HOVERED_FEATURE_OPACITY
        self._hover_patch = self.plotter.add_mesh(
            pv.PolyData(corners, faces),
            color=FEATURE_LABEL_COLOUR,
            opacity=hover_opacity,
            backface_params={
                "color": FEATURE_LABEL_COLOUR,
                "opacity": hover_opacity,
            },
            lighting=False,
            name="feature-hover",
            render=False,
            reset_camera=False,
            pickable=False,
        )

    def _feature_at(self, point: Vec3) -> FeatureId | None:
        """Das Merkmal **unter** einem Klick — zeigen schlägt einen Namen
        tippen (§18.5).

        Gesucht wird im Körper unter dem Zeiger, nicht im gerade ausgewählten.
        Andersherum wäre es ein Ring: den Körper wählt man aus, indem man ihn
        anklickt, und der Klick fände sein Merkmal erst, wenn er schon
        ausgewählt wäre. Ohne Treffer bleibt der gewählte Körper die Quelle —
        dann ist der Klick daneben gegangen, und die Merkmale, die man vor
        Augen hat, sind seine.

        **„Unter" heißt auf seiner Fläche**, und das ist der Unterschied zu
        vorher. Bis hierher gewann das Merkmal mit dem nächsten *Mittelpunkt*,
        ohne jede Grenze — es gab also immer einen Gewinner, sobald der Körper
        ein Merkmal hatte. Ein Klick mitten auf die Platte wählte die Bohrung
        in der Ecke, und ein Klick auf die Deckfläche die Stirnfläche, deren
        Mittelpunkt näher lag. Gemessen wird jetzt der Abstand zu den
        **Dreiecken** des Merkmals (:data:`FEATURE_REACH_SHARE`): Ein Klick auf
        die Bohrungswand landet auf ihren Dreiecken und trifft, ein Klick
        daneben landet auf denen der Deckfläche und trifft die.

        Ein Merkmal ohne eigene Dreiecke — eine offene Kantenschleife hat
        keine — bleibt über seinen Mittelpunkt erreichbar, sonst wäre es nicht
        anklickbar. Auch dort gilt die Reichweite.
        """
        found = self._feature_hit(point)
        return found[0] if found is not None else None

    def _feature_hit(self, point: Vec3) -> tuple[FeatureId, float] | None:
        """Merkmal und Abstand — die Rechnung hinter :meth:`_feature_at`.

        Getrennt, weil der Zeiger dieselbe Frage stellt wie der Klick und die
        beiden nie auseinanderlaufen dürfen (:meth:`_would_pick_feature`).
        """
        import numpy as np

        target = np.asarray(point, dtype=float)
        # Der Körper unter dem Zeiger, sonst der gewählte — und die Reichweite
        # gehört dem, dessen Merkmale gesucht werden, nicht dem anderen.
        source = self._object_at(point)
        prepared = self._prepared_features(source)
        if not prepared:
            source = self._selected
            prepared = self._prepared_features(source)
        if not prepared:
            return None
        reach = self._feature_reach(source)
        best: FeatureId | None = None
        best_offset = float("inf")
        for feature_id, triangles, low, high in prepared:
            # Der Hüllquader zuerst: Er kostet sechs Vergleiche, der genaue
            # Abstand eine Rechnung über jedes Dreieck des Merkmals.
            if np.any(target < low - reach) or np.any(target > high + reach):
                continue
            offset = distance_to_triangles(triangles, target)
            if offset < best_offset:
                best_offset = offset
                best = feature_id
        if best is not None and best_offset <= reach:
            return best, best_offset
        # **Mitten im Loch ist kein Dreieck, und der Klick meint es trotzdem.**
        # Robert am 23.08.2026, auf die Frage, welcher der beiden Fälle gilt:
        # „beides, es sollte in beiden fällen gehen." Wer eine Bohrung sieht
        # und hineinklickt, meint sie — und trifft dort die Fläche dahinter
        # oder die Platte darunter, jedenfalls kein Dreieck der Bohrung. Von
        # ihrer Mitte aus ist ihre Wand einen **Radius** entfernt, und der ist
        # bei einer M5-Bohrung fast dreimal so weit wie die Reichweite.
        #
        # Deshalb die zweite Frage: Steht der Punkt **innerhalb** des
        # Bohrungszylinders? Das ist keine gelockerte Reichweite, sondern eine
        # andere Aussage — „auf dem Rand" gegen „im Loch" —, und sie gilt nur
        # für Merkmale, die einen Durchmesser und eine Achse haben.
        return self._feature_inside(target)

    def _feature_inside(self, target: Any) -> tuple[FeatureId, float] | None:
        """Das Loch, in dem dieser Punkt steht — oder nichts.

        Gerechnet wird der Abstand zur **Achse**: Ein Punkt im Zylinder liegt
        näher an ihr als der Radius. Die Länge entlang der Achse wird nicht
        geprüft, und das ist Absicht — wer von schräg oben in eine Bohrung
        klickt, trifft die Platte darunter, also einen Punkt jenseits der
        Tiefe. Die Bohrung ist trotzdem gemeint.

        Bei mehreren gewinnt die engste: Eine Senkung um eine Bohrung herum
        enthält denselben Punkt, und gemeint ist das, worauf man gezeigt hat.
        """
        import numpy as np

        source = self._object_at(tuple(float(value) for value in target))  # type: ignore[arg-type]
        entry = self._result.scene.objects.get(source) if self._result and source else None
        if entry is None:
            return None
        best: FeatureId | None = None
        best_radius = float("inf")
        for feature_id, feature in entry.features.items():
            diameter = feature.params.get("diameter")
            axis = feature.params.get("axis")
            centre = feature.params.get("centre")
            if not diameter or axis is None or centre is None:
                continue
            radius = float(diameter) / 2.0
            if radius >= best_radius:
                continue
            direction = np.asarray(axis, dtype=float)
            length = float(np.linalg.norm(direction))
            if length <= 0.0:
                continue
            direction = direction / length
            offset = target - np.asarray(centre, dtype=float)
            # Der Abstand zur Achse: die Länge dessen, was senkrecht auf ihr steht.
            sideways = offset - float(np.dot(offset, direction)) * direction
            if float(np.linalg.norm(sideways)) <= radius:
                best = feature_id
                best_radius = radius
        return (best, 0.0) if best is not None else None

    def _feature_reach(self, object_id: ObjectId | None) -> float:
        """Wie weit ein Klick neben einem Merkmal noch dessen Merkmal meint.

        Mitwachsend wie der Flächengriff: eine halbe Millimeter-Grenze ist an
        einem 300-mm-Gehäuse zu streng für ein dezimiertes Anzeigenetz und an
        einem 8-mm-Zapfen zu großzügig.
        """
        entry = self._result.scene.objects.get(object_id) if self._result and object_id else None
        if entry is None:
            return FEATURE_REACH_MINIMUM
        size = entry.mesh.bounds.size
        diagonal = math.sqrt(float(sum(value * value for value in size)))
        return max(FEATURE_REACH_MINIMUM, diagonal * FEATURE_REACH_SHARE)

    def _bore_aim(self, origin: Vec3, direction: Vec3, until: float) -> Vec3 | None:
        """Die Stelle in der Bohrung, auf die dieser Sichtstrahl zeigt.

        **Der Klick ist eine Blickrichtung und nicht nur ein Punkt**, und das
        ist der Unterschied zu allem, was hier vorher stand. Ein Punkt setzt
        voraus, dass unter dem Zeiger ein Dreieck liegt — bei einer Bohrung tut
        es das oft nicht:

        * Gemessen am echten ``vtkCellPicker``, Platte aus dem Korpus in der
          Draufsicht, Bohrung 32 Pixel breit: Klicks 0 bis 8 Pixel neben der
          Bohrungsmitte gaben **keinen Treffer**. Die Zylinderwand liegt
          parallel zum Strahl, und hinter der Durchgangsbohrung kommt nichts
          mehr. Ein Klick mitten in die Bohrung hob damit die Auswahl auf.
        * Landet der Strahl daneben auf der Deckfläche, gewinnt sie **immer**:
          ihr Abstand ist null, der der Bohrung größer. Damit war
          :data:`FEATURE_REACH_SHARE` für Bohrungen wirkungslos — gemessen gab
          schon ein Punkt 0,4 mm neben dem Bohrungsrand ``face_2``, bei einer
          Reichweite von 0,95 mm.

        Zusammen war das „wir erwischen oft nur die Oberfläche und kommen nicht
        zur Bohrung".

        ``until`` ist der Strahlparameter des sichtbaren Auftreffpunkts und die
        Grenze, ohne die das Ganze falsch wird: Was der Strahl erst **hinter**
        dem Sichtbaren durchquert, hat niemand gemeint — in der Vorderansicht
        liegt hinter der Stirnfläche jede Bohrung der Platte. Ohne Auftreffpunkt
        (der Blick geht durch das Loch hindurch ins Leere) steht dort
        ``inf``.

        Zurück kommt ein Punkt **auf der Bohrungsachse**, nicht der
        Auftreffpunkt: Von dort führt die schon vorhandene Rechnung
        (:meth:`_feature_inside`, „mitten im Loch ist kein Dreieck") zur
        Bohrung, und die Stufung, das Kontextmenü und der Zeiger bleiben
        unverändert — sie bekommen einen Punkt wie immer.
        """
        import numpy as np

        if self._result is None:
            return None
        forward = np.asarray(direction, dtype=float)
        length = float(np.linalg.norm(forward))
        if length <= EPS_GEOM:
            return None
        forward = forward / length
        start = np.asarray(origin, dtype=float)

        best_enter = math.inf
        best_radius = math.inf
        found: Vec3 | None = None
        for object_id, entry in self._result.scene.objects.items():
            if not self._in_view(object_id, entry):
                continue
            # Die Reichweite ist die **Zielhilfe**: Gezielt wird in Pixeln, und
            # der Rand einer M3-Bohrung ist an einem großen Teil wenige davon
            # breit. Derselbe Wert wie beim Klick auf die Fläche eines Merkmals,
            # denn es ist dieselbe Frage — wie weit daneben meint noch dies.
            reach = self._feature_reach(object_id)
            for feature_id, triangles, _low, _high in self._prepared_features(object_id):
                feature = entry.features.get(feature_id)
                if feature is None:
                    continue
                diameter = feature.params.get("diameter")
                axis = feature.params.get("axis")
                centre = feature.params.get("centre")
                if not diameter or axis is None or centre is None:
                    continue
                line = np.asarray(axis, dtype=float)
                extent = float(np.linalg.norm(line))
                if extent <= EPS_GEOM:
                    continue
                line = line / extent
                # Wie weit das Merkmal entlang seiner Achse reicht — aus seinen
                # eigenen Dreiecken und nicht aus ``depth``: Der Hüllquader
                # kennt die Achse nicht, und eine schräge Bohrung hat beides.
                lengthwise = triangles.reshape(-1, 3) @ line
                bounds = (float(lengthwise.min()), float(lengthwise.max()))
                radius = float(diameter) / 2.0
                span = bore_span(
                    (float(start[0]), float(start[1]), float(start[2])),
                    (float(forward[0]), float(forward[1]), float(forward[2])),
                    centre,
                    (float(line[0]), float(line[1]), float(line[2])),
                    radius + reach,
                    (bounds[0] - reach, bounds[1] + reach),
                )
                if span is None or span[1] <= 0.0 or span[0] >= until:
                    continue
                enter = max(span[0], 0.0)
                leave = min(span[1], until)
                if leave <= enter:
                    continue
                nearer = enter < best_enter - EPS_GEOM
                tied = abs(enter - best_enter) <= EPS_GEOM and radius < best_radius
                if not (nearer or tied):
                    continue
                # Der Punkt auf der Achse, auf der Höhe, in der der Strahl die
                # Bohrung durchläuft — geklemmt auf ihre eigene Länge, damit er
                # nicht über der Öffnung im Leeren steht, wo die Deckfläche
                # wieder näher wäre als die Bohrungswand.
                middle = float(
                    np.clip(float(start @ line) + forward @ line * (enter + leave) / 2.0, *bounds)
                )
                point = np.asarray(centre, dtype=float)
                point = point + line * (middle - float(point @ line))
                best_enter = enter
                best_radius = radius
                found = (float(point[0]), float(point[1]), float(point[2]))
        return found

    def _through_aim(self, origin: Vec3, direction: Vec3) -> Vec3 | None:
        """Der Punkt in der Öffnung, durch die dieser Strahl hindurchgeht.

        **Die zweite Hälfte desselben Fundes, und sie brauchte eine andere
        Rechnung.** Eine Bohrung ist ein Merkmal, auf das man zeigen kann
        (:meth:`_bore_aim`). Ein rechteckiger Ausschnitt ist keines: Er besteht
        aus vier Wandflächen, von denen keine „richtiger" ist als die andere —
        und bei senkrechtem Blick liegen sie **parallel** zum Strahl, dort ist
        also so wenig ein Dreieck zu treffen wie an der Bohrungswand. Der
        Picker gab nichts zurück, und `_on_left_click` machte daraus
        ``objectPicked.emit("")``: Ein Klick in einen Ausschnitt **hob die
        Auswahl auf**.

        Was hier entschieden wird, ist deshalb nicht „welches Merkmal", sondern
        „welcher **Körper**": Wer in eine Öffnung zeigt, hat auf das Teil
        gezeigt. Gefragt wird die **konvexe Hülle** (:func:`hull_planes`) und
        nicht der Hüllquader, und dieser Unterschied trägt die Zusage aus §18.5,
        dass ein Klick daneben die Auswahl aufhebt — der Quader eines
        L-Profils reicht weit ins Leere, seine Hülle nicht.

        **Die Kerbe zählt dabei mit**, und das ist die gewollte Seite der
        Abwägung: Durch den fehlenden Quadranten eines L-Profils läuft der
        Strahl in der Hülle, ohne das Netz zu treffen, und der Klick wählt das
        Teil. Ein Kriterium, das das ausnimmt, müsste „Loch" von „Einbuchtung"
        unterscheiden — eine Unterscheidung, die niemand trifft, der auf ein
        Teil zeigt und zwei Bildpunkte neben die Silhouette kommt.

        Zurück kommt die Mitte des Durchtritts. Sie liegt im Hüllquader des
        Körpers, also findet :meth:`_object_at` ihn; und sie liegt weit von
        jeder Wand, also findet :meth:`_feature_at` dort kein Merkmal — der
        Klick landet auf der ersten Stufe, beim Körper, und erfindet nichts.
        """
        import numpy as np

        if self._result is None:
            return None
        forward = np.asarray(direction, dtype=float)
        length = float(np.linalg.norm(forward))
        if length <= EPS_GEOM:
            return None
        forward = forward / length
        start = np.asarray(origin, dtype=float)

        best_enter = math.inf
        found: Vec3 | None = None
        for object_id, entry in self._result.scene.objects.items():
            if not self._in_view(object_id, entry):
                continue
            planes = self._hull_of(object_id)
            if planes is None:
                continue
            span = ray_span_in_hull(planes, start, forward)
            if span is None:
                continue
            enter = max(span[0], 0.0)
            if span[1] <= enter or enter >= best_enter:
                continue
            middle = start + forward * (enter + span[1]) / 2.0
            best_enter = enter
            found = (float(middle[0]), float(middle[1]), float(middle[2]))
        return found

    def _hull_of(self, object_id: ObjectId) -> Any:
        """Die konvexe Hülle eines Körpers als Halbräume, je Auswertung einmal.

        Gerechnet wird sie erst, wenn ein Klick sie braucht — also wenn er
        weder eine Fläche noch eine Bohrung getroffen hat. Das ist selten, und
        an einem großen Scan kostet sie zwanzig Millisekunden
        (:data:`app.core.geom.mesh.HULL_SAMPLE_LIMIT`).
        """
        if object_id in self._object_hulls:
            return self._object_hulls[object_id]
        entry = self._result.scene.objects.get(object_id) if self._result else None
        planes = hull_planes(entry.mesh) if entry is not None else None
        self._object_hulls[object_id] = planes
        return planes

    def _pick_ray(self, x: int, y: int) -> tuple[Vec3, Vec3] | None:
        """Der Sichtstrahl durch eine Bildschirmstelle, in Ansichtskoordinaten.

        Über die nahe und die ferne Ebene und nicht über die Kamerastellung:
        Bei einer Parallelprojektion — jeder Ansicht von vorn, von oben, von
        der Seite — läuft der Strahl nicht durch das Kameraauge, und eine
        Richtung aus ``GetPosition()`` wäre dort falsch.

        **Die Richtung ist der Schritt von nah nach fern und damit nicht
        normiert** — sie ist hunderte Millimeter lang. Wer gegen sie
        schwellwertet, prüft eine Länge und keinen Winkel: Bei einem Strahl
        ``(1000, 0, -0,5)`` auf die XY-Ebene steht im Skalarprodukt 0,5, also
        das Fünfhundertfache einer Schwelle von 1e-3, während der Winkel zur
        Ebene ein halbes Tausendstel beträgt — die Prüfung löste nie aus.
        (Gefunden von der Nachbarsitzung an ``sketch.planes.ray_hit``, die
        denselben Strahl benutzt.) Wer einen Winkel braucht, teilt vorher durch
        die Länge; :meth:`_bore_aim` tut genau das.
        """
        if self.plotter is None:
            return None
        renderer = self.plotter.renderer
        near = _world_at_depth(renderer, x, y, 0.0)
        far = _world_at_depth(renderer, x, y, 1.0)
        if near is None or far is None:
            return None
        step = (far[0] - near[0], far[1] - near[1], far[2] - near[2])
        if math.sqrt(sum(value * value for value in step)) <= EPS_GEOM:
            return None
        return near, step

    def _aim_at(self, x: int, y: int) -> Vec3 | None:
        """Die Stelle, die ein Klick hier meint — durch eine Bohrung hindurch
        gesehen, wenn dort eine liegt.

        Der Ersatz für :meth:`_world_at` überall, wo es um **Auswahl** geht:
        Klick, Kontextmenü und Zeiger. Nicht beim Messen, Bemalen und Ziehen —
        dort ist eine Stelle auf der Oberfläche gemeint und keine Bohrung, und
        ein Punkt in der Luft wäre dort falsch.
        """
        if self.plotter is None:
            return None
        point = self._world_at(x, y)
        ray = self._pick_ray(x, y)
        if ray is None:
            return point
        origin, direction = ray

        import numpy as np

        # Die Merkmale stehen in Szenenkoordinaten, der Strahl kommt aus der
        # Ansicht (§25). Verschoben wird um dasselbe Stück wie ein Punkt —
        # welches das ist, sagt die Stelle, auf die gezeigt wird. Ohne
        # Auftreffpunkt sagt es die Fokusebene, wie beim Zeiger.
        reference = point if point is not None else _world_under(self.plotter.renderer, x, y)
        if reference is None:
            return point
        scene = self._from_view(reference)
        shift = np.asarray(reference, dtype=float) - np.asarray(scene, dtype=float)
        forward = np.asarray(direction, dtype=float)
        forward = forward / float(np.linalg.norm(forward))
        start = np.asarray(origin, dtype=float) - shift
        until = (
            float((np.asarray(point, dtype=float) - np.asarray(origin, dtype=float)) @ forward)
            if point is not None
            else math.inf
        )
        ray = (
            (float(start[0]), float(start[1]), float(start[2])),
            (float(forward[0]), float(forward[1]), float(forward[2])),
        )
        aimed = self._bore_aim(ray[0], ray[1], until)
        if aimed is None and point is None:
            # Nichts getroffen und keine Bohrung im Weg: Vielleicht geht der
            # Blick durch eine Öffnung des Körpers, und dann ist er gemeint und
            # nicht das Nichts (:meth:`_through_aim`).
            aimed = self._through_aim(ray[0], ray[1])
        if aimed is None:
            return point
        back = np.asarray(aimed, dtype=float) + shift
        return (float(back[0]), float(back[1]), float(back[2]))

    def _prepared_features(
        self, object_id: ObjectId | None
    ) -> list[tuple[FeatureId, Any, Any, Any]]:
        """Die Dreiecke der Merkmale eines Körpers, je Auswertung einmal
        gerechnet (:attr:`_feature_geometry`).

        Gezählt wird im Netz der **Szene** und nicht im dezimierten
        Anzeigenetz — dieselbe Trennung wie bei :meth:`highlighted_faces`
        (§18.9).
        """
        if object_id is None or self._result is None:
            return []
        cached = self._feature_geometry.get(object_id)
        if cached is not None:
            return cached
        entry = self._result.scene.objects.get(object_id)
        raw = getattr(entry.mesh, "raw", None) if entry is not None else None
        if entry is None:
            return []

        import numpy as np

        vertices = np.asarray(raw.vertices, dtype=float) if raw is not None else None
        faces = np.asarray(raw.faces) if raw is not None else None
        prepared: list[tuple[FeatureId, Any, Any, Any]] = []
        for feature_id, feature in entry.features.items():
            indices = [
                index
                for index in feature.face_indices
                if faces is not None and 0 <= index < len(faces)
            ]
            if indices and vertices is not None and faces is not None:
                triangles = vertices[faces[indices]]
            else:
                # Ohne eigene Dreiecke bleibt der Mittelpunkt — als
                # entartetes Dreieck, damit dieselbe Rechnung ihn erreicht.
                centre = feature.params.get("centre")
                if centre is None:
                    continue
                point = np.asarray(centre, dtype=float)
                triangles = np.repeat(point.reshape(1, 1, 3), 3, axis=1)
            flat = triangles.reshape(-1, 3)
            prepared.append((feature_id, triangles, flat.min(axis=0), flat.max(axis=0)))
        self._feature_geometry[object_id] = prepared
        return prepared

    def set_direct_picking(self, active: bool) -> None:
        """Schaltet die Auswahltiefe ab, solange ein Dialog nach einem Merkmal
        fragt (§18.5).

        Ein Klick ist dann eine **Antwort** und keine Navigation: Wer *Bohrung
        vergrößern* offen hat und auf die Bohrung zeigt, meint sie und nicht
        ihren Körper. Zweimal zeigen zu müssen, um zu antworten, sähe aus wie
        ein verschluckter Klick — genau der Eindruck, aus dem §18.5 mit dem
        Anklicken herausführen soll.
        """
        self._direct_picking = active

    def _click_target(
        self, point: Vec3, *, direct: bool = False
    ) -> tuple[ObjectId | None, FeatureId | None]:
        """Was ein Klick an dieser Stelle auswählen würde — Körper und, wenn
        die Auswahl schon dort steht, das Merkmal darunter (§18.5).

        **Die gestufte Tiefe.** Der erste Klick auf einen Körper meint den
        Körper, der nächste das Merkmal unter dem Zeiger. Bis hierher gewann
        sofort das Merkmal, und ein Körper mit erkannten Bohrungen war per Klick
        überhaupt nicht auswählbar: Wer die Platte verschieben wollte, bekam
        eine Bohrung und musste in den Objektbaum ausweichen.

        Das ist das Modell von Figma, Illustrator und Sketch — erst die Gruppe,
        dann das Element darin —, und es ist auch das von Fusion 360, wo *Select
        Other* eine zweite Geste braucht, um in die Tiefe zu gehen. Zwei
        Eigenschaften davon sind übernommen und beide sind Absicht:

        * **Die Tiefe hängt am Körper, nicht am Pixel.** Wer in einem Körper
          angekommen ist, wählt mit dem nächsten Klick direkt die nächste
          Bohrung — er muss nicht erst wieder heraus. Blender setzt beim
          Weiterschalten zurück, sobald die Maus sich bewegt; für Bohrungen an
          einem Teil wäre das eine Stufe zu viel.
        * **Ein anderer Körper fängt von vorn an.** Sonst führte der Weg von
          einer Bohrung zum Nachbarteil über das Merkmal des Nachbarteils, das
          niemand gemeint hat.

        Gelesen wird die Stufe aus der Auswahl selbst und nicht aus einem
        eigenen Zustand: „im Körper drin" heißt genau „ein Merkmal dieses
        Körpers ist gewählt". Ein zweiter Zustand daneben wäre eine zweite
        Wahrheit, und die Auswahl kommt auch aus dem Objektbaum.

        **Zwei Ausnahmen gehen ohne Stufen ans tiefste Ziel**, und beide sind
        keine Navigation: ``direct`` für den Rechtsklick (siehe
        :meth:`_on_right_click`) und :meth:`set_direct_picking` für einen
        Dialog, der nach einem Merkmal fragt.
        """
        object_id = self._object_at(point)
        if object_id is None:
            return None, None
        if direct or self._direct_picking:
            return object_id, self._feature_at(point)
        if object_id != self._selected:
            # Erste Stufe: ein anderer Körper wird als Ganzes gewählt.
            return object_id, None
        # Derselbe Körper, also eine Stufe tiefer. Steht dort kein Merkmal,
        # bleibt es beim Körper — und ein gewähltes Merkmal fällt weg, denn
        # der Klick ging auf die nackte Fläche.
        return object_id, self._feature_at(point)

    def selection_depth(self) -> int:
        """Wie tief die Auswahl steht: 0 nichts, 1 ein Körper, 2 ein Merkmal.

        Als eigene Auskunft, damit der Weg heraus (:meth:`step_selection_out`)
        und der Weg hinein (:meth:`_click_target`) dieselbe Stufenzählung
        benutzen und nicht zwei.
        """
        if self._selected is None:
            return 0
        return 2 if self._selected_feature is not None else 1

    def _would_pick_feature(self, point: Vec3) -> bool:
        """Ob der **nächste** Klick hier ein Merkmal wählen würde.

        Der Zeiger stellt genau diese Frage (:meth:`_look_under_pointer`), und
        er muss sie mit derselben Rechnung stellen wie der Klick: Ein Zeiger,
        der die Bohrungsform zeigt, wo ein Klick den Körper wählt, verspricht
        etwas, das nicht eintritt. So wird die Stufe auch sichtbar — über einer
        Bohrung am noch nicht gewählten Teil steht der Auswahlzeiger, nach dem
        ersten Klick der Merkmalszeiger.
        """
        return self._click_target(point)[1] is not None

    def _features_of(self, object_id: ObjectId | None) -> dict[FeatureId, Feature]:
        """Die Merkmale eines Körpers, oder nichts."""
        if object_id is None or self._result is None:
            return {}
        entry = self._result.scene.objects.get(object_id)
        return dict(entry.features) if entry is not None else {}

    # --- difference view (§18.7) ------------------------------------------------

    def show_difference(self, difference: Any | None) -> None:
        """Hinzugekommenes und entferntes Volumen.

        Die Farben kommen aus der Palette (§19.1) und sind nie der einzige
        Träger: hinzugekommen und entfernt unterscheiden sich auch in der
        Transparenz und in der Legende des Chat-Panels — die Ansicht bleibt also
        ohne Farbsehen lesbar.
        """
        self._difference = difference
        # Die Differenz besitzt die Modellfarben, solange sie sichtbar ist.
        # Auswahl und Hover bleiben in Baum, Text und Zeiger erhalten, färben
        # aber nicht über „hinzugefügt/entfernt" hinweg.
        self._apply_selection_colour()
        self._redraw_features()
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
        self._apply_selection_colour()
        self._redraw_features()
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

        import numpy as np

        colours = DIFF_PALETTES[self._diff_palette]
        for entry in self._difference.entries.values():
            # Die Vorschau liegt über dem gezeichneten Körper — der geht durch
            # ``_view_offset``, also muss sie es auch (§25, §18.8).
            scene_entry = (
                self._result.scene.objects.get(entry.object_id)
                if self._result is not None
                else None
            )
            shift = (
                np.asarray(self._view_offset(scene_entry, self._result), dtype=float)
                if scene_entry is not None and self._result is not None
                else np.zeros(3)
            )
            self._add_body(
                entry.added, colours.added.colour, f"added:{entry.object_id}", 0.85, shift
            )
            self._add_body(
                entry.removed, colours.removed.colour, f"removed:{entry.object_id}", 0.45, shift
            )

    def _add_body(self, mesh: Any, colour: str, name: str, opacity: float, shift: Any) -> None:
        if self.plotter is None or mesh is None or not len(mesh.raw.faces):
            return
        import numpy as np
        import pyvista as pv

        raw = mesh.raw
        faces = np.hstack(
            [np.full((len(raw.faces), 1), 3, dtype=np.int64), np.asarray(raw.faces)]
        ).ravel()
        surface = pv.PolyData(np.asarray(raw.vertices, dtype=float) + shift, faces)
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
        self.view_bar.place()
        self.drag_bar.place()
        self.plane_picker.place()
        self.sketch_selection.place()
        self.sketch_action.place()
        if self._sketch_frame is not None and self._apply_sketch_occlusion():
            self._draw()
        self._place_orientation_widget()

    def _place_orientation_widget(self) -> None:
        """Zieht die Achsenanzeige an ihre Ecke nach.

        Sie steht in Anteilen des Fensters, gemeint ist aber eine Größe in
        Bildpunkten — ohne das Nachziehen wüchse sie mit dem Fenster und
        verschwände wieder hinter der linken Spalte, sobald jemand das Fenster
        aufzieht.
        """
        widget = axes_widget_of(self.plotter)
        if widget is None:
            return
        try:
            widget.SetViewport(*orientation_corner(self.width(), self.height()))
        except Exception as problem:  # pragma: no cover - hängt am Treiber
            _log.info("orientation widget keeps its place: %s", problem)

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
        self._add_rings(contours, layer.z, LAYER_COLOUR, "layer", LAYER_WIDTHS["layer"])
        self._add_rings(
            [polygon.outline for polygon in layer.islands],
            layer.z,
            ISLAND_COLOUR,
            "island",
            LAYER_WIDTHS["island"],
        )
        self._add_rings(
            [polygon.outline for polygon in layer.overhangs],
            layer.z,
            OVERHANG_COLOUR,
            "overhang",
            LAYER_WIDTHS["overhang"],
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

    def refresh_labels(self) -> None:
        """Zeichnet die Szene neu, damit ihre Beschriftungen die Anzeigeeinheit
        übernehmen (§19.3).

        Dasselbe Mittel, mit dem der Schichtaufbau und der Palettenwechsel
        daneben arbeiten: Die Beschriftungen entstehen in ``show_scene``, und
        das Ergebnis liegt hier. Ohne den Anstoß stünde am Merkmal weiter das
        Maß in der alten Einheit — bis irgendwann etwas anderes ein Neuzeichnen
        auslöst.
        """
        self.show_scene(self._result)
        # ``show_scene`` zeichnet die Maße nur im Leer-Zweig neu — nach einem
        # Einheitenwechsel stünden sie sonst in der alten Einheit da.
        self._redraw_measurements()

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
        from vtkmodules.vtkRenderingCore import vtkMapper

        # Vor dem Widget gemerkt: Es stellt die statische Tiefen-Auflösung um
        # (siehe ``_coincident_before``), und zurückstellen kann nur, wer den
        # Stand von vorher kennt.
        self._coincident_before = int(vtkMapper.GetResolveCoincidentTopology())
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
        if self._coincident_before is not None:
            from vtkmodules.vtkRenderingCore import vtkMapper

            # Die statische Umstellung des Widgets zurücknehmen — sie gilt
            # prozessweit und überlebte sonst den Modus (Striche an allen
            # Kantenmitten, siehe ``_coincident_before``).
            vtkMapper.SetResolveCoincidentTopology(self._coincident_before)
            self._coincident_before = None

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
            self.drag_bar.follow_length(tr("Fläche"), along_normal(steps.offset, self._drag_normal))
        elif steps.turns and steps.axis is not None:
            self._drag_kind = "turn"
            self._drag_axis = steps.axis
            self.drag_bar.follow(f"{tr('Winkel')} {steps.axis.upper()}", steps.angle, "°", 1)
        elif steps.moves:
            index = max(range(3), key=lambda axis: abs(steps.offset[axis]))
            dominant: Axis = ("x", "y", "z")[index]
            self._drag_kind = "move"
            self._drag_axis = dominant
            self.drag_bar.follow_length(dominant.upper(), steps.offset[index])
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
        # Der Griff sitzt auf der gezeichneten Fläche, nicht auf der
        # Szenenkoordinate — sonst steht er eine Bettbreite daneben (§25).
        entry = (
            self._result.scene.objects.get(self._selected)
            if self._result is not None and self._selected is not None
            else None
        )
        if entry is not None and self._result is not None:
            centre = centre + np.asarray(self._view_offset(entry, self._result), dtype=float)
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
        if abs(factor - 1.0) > SCALE_UNCHANGED:
            self.scaleDragged.emit(float(factor))
        self._end_drag()

    def _end_drag(self) -> None:
        """Der Zug ist vorbei: Zahl weg, Zustand weg, Stil zurück, Griff frisch.

        **Der Ziehgriff der Skizze geht einen anderen Weg zurück.** Er hängt
        nicht an einem pyvista-Widget, das den Navigationsstil vertauscht hätte;
        ihn hier durch ``set_navigation`` zu schicken baute den Interaktionsstil
        mitten in der Geste neu auf, und das Loslassen käme bei einem Stil an,
        der von seinem Drücken nichts weiß. Abzuräumen ist dort die Drahtform,
        und die kennt nur :meth:`_end_pull`.
        """
        if self._drag_kind == "pull":
            self._end_pull()
            return
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
        unusable = (kind == "scale" and value is not None and value <= 0.0) or (
            kind == "pull" and value is not None and not self._pull_takes(value)
        )
        if value is None or kind is None or unusable:
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
        elif kind == "scale" and abs(value - 1.0) > SCALE_UNCHANGED:
            self.scaleDragged.emit(float(value))
        elif kind == "pull":
            # Der Ziehgriff: Getippt wird die Höhe, und die geht denselben Weg
            # wie die gezogene — über :meth:`finish_sketch_pull`, damit die
            # Grenze der Operation an **einer** Stelle geprüft wird.
            #
            # **Vorher gibt die Tastatur den Zug zurück.** Solange ``typing``
            # steht, wendet ``finish_sketch_pull`` nichts an — das ist die
            # Zusage gegenüber dem *Loslassen*, und die Eingabetaste ist genau
            # der Moment, in dem sie endet. Ohne diese Zeile lief die getippte
            # Zahl in dieselbe Wache und verschwand.
            self.drag_bar.typing = False
            self._pull_height = float(value)
            # **Die getippte Zahl ersetzt den Zeiger, also auch dessen
            # Richtung.** Ohne diese Zeile war ein Fehlzug per Tastatur nicht
            # mehr zu retten: ``_pull_raw`` stand noch auf dem Maß von vorhin,
            # und die Richtungsprüfung im Loslassen lehnte die eingetippte Höhe
            # mit „andersherum ziehen" ab (gefunden von der Review-Sitzung,
            # 27.08.2026). Wer tippt, hat die Frage nach der Richtung beantwortet.
            self._pull_raw = None
            self.finish_sketch_pull()
            return
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
        # bekommt jede dieser Bewegungen weiterhin. Aber nur vom Interactor:
        # Der Filter sitzt auch auf dem Wertfeld, und dessen Positionen als
        # Viewport-Koordinaten gelesen setzten den Zeiger an den oberen Rand —
        # falscher Hover nach der Ruhepause, Vorschausprung im Skizzenmodus.
        plotter = getattr(self, "plotter", None)
        interactor = getattr(plotter, "interactor", None) if plotter is not None else None
        if watched is interactor:
            if kind == QEvent.Type.MouseMove:
                self._note_pointer(event.position())
            elif kind == QEvent.Type.Leave:
                self._forget_pointer()
            elif kind == QEvent.Type.Enter:
                self._update_cursor()

        # Qt kann den Filter schon während ``QWidget.__init__`` aufrufen. In
        # diesem kurzen Zustand gibt es weder Skizzen- noch Zugfelder; die
        # Eingabe gehört dann vollständig Qt.
        if not hasattr(self, "_sketch_frame"):
            return False

        # **E19 im gefahrenen Modus: die erste Ziffer beginnt die Eingabe.**
        # Der Fokus liegt auf der Ansicht; ``ShortcutOverride`` nimmt den
        # Ebenen-Kürzeln 1 bis 3 die Vorfahrt, solange ein Maß aussteht, und
        # der Tastendruck geht an das verliehene Feld des Canvas.
        if self._sketch_frame is not None and watched is interactor:
            if (
                kind == QEvent.Type.ShortcutOverride
                and self._sketch_measure_pending is not None
                and self._sketch_measure_pending() > 0.0
                and str(event.text())[:1].isdigit()
            ):
                event.accept()
                return True
            if (
                kind == QEvent.Type.KeyPress
                and self._sketch_measure_begin is not None
                and self._sketch_measure_begin(event)
            ):
                return True

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
        es zu sehen gibt. Gerechnet wird er hier selbst, statt ihn pyvista über
        alle Aktoren suchen zu lassen: nur so bekommt auch die leere Szene ihre
        Luft, und nur so hängt das Ergebnis nicht daran, welche Kulisse gerade
        zusätzlich im Bild steht.

        **Mit Luft** (:data:`CAMERA_MARGIN`). Genau eingepasst berührte ein
        40 mm großer Quader links und rechts den Bildrand.
        """
        bounds = self._object_bounds() or self._volume_bounds()
        # Worauf eingepasst wurde, wird gemerkt: ``_fit_once_for`` vergleicht
        # damit, ob die Szene der Ansicht inzwischen entwachsen ist. **Vor** dem
        # Plotter-Zweig, aus demselben Grund wie bei der Umgebungsverdeckung:
        # offscreen gibt es keinen Plotter, und eine Regel, die nur im Zeichnen
        # gilt, prüft niemand.
        self._fitted_bounds = bounds
        if self.plotter is None:
            return
        if bounds is None:
            self.plotter.reset_camera()
        else:
            self.plotter.reset_camera(bounds=with_margin(bounds))
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
        # **Zuerst das Urteil, dann die Rücksprünge.** Stünde es hinter einem
        # ``return``, trüge es beim nächsten Leser den Wert des vorigen
        # Aufbaus.
        here = frozenset(result.scene.objects) if result is not None else frozenset()
        self._moved_only = bool(here) and here == self._fitted_objects

        if result is not None and result.scene.objects:
            wanted = "objects"
        elif self._bed_extent is not None:
            wanted = "bed"
        else:
            return
        # **Und noch einmal, wenn die Szene der Ansicht entwachsen ist.** Der
        # Satz darüber schützt die Feinarbeit, und dabei bleibt es; was er nicht
        # beantwortet, ist der Sprung: Wer in ein Teil von zwei Millimetern
        # hineingezoomt hatte und einen 400er Körper dazu erzeugte, bekam eine
        # dunkelrote Fläche zu sehen — die Kamera stand in dessen Innerem. Die
        # Blickrichtung bleibt dabei, wo sie war: ``reset_camera`` rahmt neu, es
        # dreht nichts. Wann es genug ist, entscheidet :func:`outgrown`.
        #
        # **Und der Nutzer, der selbst schiebt, behält seine Ansicht.** Stehen
        # dieselben Objekte da wie beim letzten Einpassen, war es ein
        # Verschieben und kein neuer Inhalt — dann zählt nur noch, ob die Szene
        # gewachsen ist. Ohne das rahmte jedes Loslassen neu.
        if wanted != self._fitted_to or outgrown(
            self._fitted_bounds, self._object_bounds(), moved_only=self._moved_only
        ):
            self.reset_camera()
            self._fitted_to = wanted  # type: ignore[assignment]
            self._fitted_objects = here

    def _volume_bounds(self) -> tuple[float, float, float, float, float, float] | None:
        """Der Bauraum als Hüllquader, oder nichts, solange kein Profil gilt.

        Der Rückfall für die leere Szene. Ein Slicer zeigt dort denselben
        Kasten — die Platte in seinem Boden, die Höhe darüber leer —, und das
        ist die Gewohnheit, an der sich die Navigation ohnehin ausrichtet
        (§2.9).
        """
        if self._build_volume is None:
            return None
        width, depth, height = self._build_volume
        return (-width / 2.0, width / 2.0, -depth / 2.0, depth / 2.0, 0.0, height)

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
        """Eine der sieben Kameravorgaben (§18.1).

        Eingepasst wird über :meth:`reset_camera` — auf die Körper, mit Luft,
        und mit gesetztem ``camera_set``. ``plotter.reset_camera()`` stand
        hier und rahmte alle Aktoren samt Bauraum-Kulisse: exakt der Fehler,
        den :meth:`reset_camera` in eigenen Worten beschreibt, nur über die
        Achsansichten (Strg+0 bis Strg+6, ViewBar) wieder offen.
        """
        if self.plotter is None or direction not in VIEW_DIRECTIONS:
            return
        position, up = VIEW_DIRECTIONS[direction]
        self.plotter.camera_position = [position, (0.0, 0.0, 0.0), up]
        self.reset_camera()
        self._redraw_shadows()

    def view_on_plane(self, frame: PlaneFrame) -> None:
        """Die Kamera senkrecht auf eine Zeichenebene stellen (§30.1).

        Der Gegenstück zu :meth:`view_from` für eine Ebene, die in keiner
        Tabelle steht: Eine Skizze kann auf jeder planaren Fläche eines
        Körpers liegen. Gerechnet wird die Stellung in
        :func:`camera_for_plane`; hier wird sie nur gesetzt.

        **Ohne ``reset_camera``.** ``view_from`` ruft es, weil eine
        Achsansicht das ganze Modell zeigen soll. Hier wäre es falsch: Wer den
        Skizzenmodus betritt, will auf *seine* Ebene sehen, und ein Zoom auf
        die Hüllbox aller Objekte schöbe eine Skizze auf einer kleinen
        Deckfläche an den Bildrand. Der Ausschnitt bleibt, wie er war — es
        dreht sich nur die Blickrichtung.
        """
        if self.plotter is None:
            return
        distance = self._plane_distance()
        position, focus, up = camera_for_plane(frame, distance)
        self.plotter.camera_position = [position, focus, up]
        self._fit_parallel_scale(distance)
        self._sketch_occlusion_shift = (0.0, 0.0, 0.0)
        self._apply_sketch_occlusion()
        self._redraw_shadows()

    def show_span_on_plane(
        self, frame: PlaneFrame, centre: tuple[float, float], span: tuple[float, float]
    ) -> None:
        """Die Kamera so stellen, dass dieser Ausschnitt der Ebene im Bild liegt.

        Das Gegenstück zu :meth:`view_on_plane`, das den Ausschnitt
        ausdrücklich **nicht** anfasst: Wer den Skizzenmodus betritt, will auf
        seine Ebene sehen, ohne dass der Zoom springt. Wer dagegen *Einpassen*
        drückt, will genau das Gegenteil.

        ``centre`` und ``span`` kommen in Millimetern der Zeichenebene, so wie
        die Zeichenfläche sie rechnet; hierher gelangen sie über das Signal
        ``SketchCanvas.viewFitted``. Gerechnet wird in
        :func:`app.core.sketch.planes.to_world` — die Umrechnung gehört dem
        Kern, nicht der Ansicht (Konzept „Skizze im Raum", Entscheidung G).

        **Ohne diesen Weg war der Knopf tot.** ``fit_view`` setzte den Maßstab
        der Zeichenfläche, und die ist seit P4 unsichtbar. Gemessen am
        25.08.2026: Kamera vor und nach dem Aufruf identisch, bei einer Skizze,
        die zu drei Vierteln außerhalb des Bildes lag.
        """
        if self.plotter is None:
            return
        camera = getattr(self.plotter, "camera", None)
        position, focus, up, scale = camera_for_span(
            frame,
            centre,
            span,
            self._plane_distance(),
            (self.height() or 1) / (self.width() or 1),
        )
        self.plotter.camera_position = [position, focus, up]
        if camera is not None and getattr(camera, "parallel_projection", False):
            camera.parallel_scale = scale
        self._sketch_occlusion_shift = (0.0, 0.0, 0.0)
        self._apply_sketch_occlusion()
        self.plotter.render()
        self.cameraMoved.emit()

    def set_zone_margins(self, left: int, right: int, bottom: int = 0) -> None:
        """Die schwebenden Karten melden, welchen Bildraum sie verdecken.

        Links und rechts bleiben im normalen Viewport bewusst über dem Modell.
        Im Skizzenmodus darf die untere Werkzeugkarte dagegen weder den Umriss
        noch Pfeil und Kreuz verdecken: Die Kamera zentriert die Zeichenebene
        in der tatsächlich freien Höhe.
        """
        self._zone_margins = (
            max(int(left), 0),
            max(int(right), 0),
            max(int(bottom), 0),
        )
        if not self.sketch_selection.isHidden():
            self.sketch_selection.place()
        if self._sketch_frame is not None and self._apply_sketch_occlusion():
            self._draw()

    def _apply_sketch_occlusion(self) -> bool:
        """Den unteren Bildrand beim heutigen Maßstab ausgleichen.

        Zoom, Fenstergröße und Kameradrehung können sich ändern, obwohl die
        Werkzeugkarte gleich hoch bleibt. Deshalb wird der vorige Weltvektor
        zuerst exakt entfernt und der neue aus dem aktuellen Bild berechnet.
        """
        plotter = self.plotter
        if plotter is None:
            return False
        camera = getattr(plotter, "camera", None)
        if camera is None or not getattr(camera, "parallel_projection", False):
            return False
        position, focus, up = plotter.camera_position
        previous = self._sketch_occlusion_shift
        amount = occluded_view_shift(
            float(camera.parallel_scale), self.height(), self._zone_margins[2]
        )
        wanted: Vec3 = (
            -float(up[0]) * amount,
            -float(up[1]) * amount,
            -float(up[2]) * amount,
        )
        if math.dist(previous, wanted) <= EPS_GEOM:
            return False
        base_position = tuple(float(position[axis]) - previous[axis] for axis in range(3))
        base_focus = tuple(float(focus[axis]) - previous[axis] for axis in range(3))
        plotter.camera_position = [
            tuple(base_position[axis] + wanted[axis] for axis in range(3)),
            tuple(base_focus[axis] + wanted[axis] for axis in range(3)),
            up,
        ]
        self._sketch_occlusion_shift = wanted
        return True

    def _remove_sketch_occlusion(self) -> bool:
        """Den angewandten Kameraausgleich ohne neue Maßrechnung entfernen."""
        plotter = self.plotter
        if plotter is None:
            self._sketch_occlusion_shift = (0.0, 0.0, 0.0)
            return False
        shift = self._sketch_occlusion_shift
        if math.dist(shift, (0.0, 0.0, 0.0)) <= EPS_GEOM:
            return False
        position, focus, up = plotter.camera_position
        plotter.camera_position = [
            tuple(float(position[axis]) - shift[axis] for axis in range(3)),
            tuple(float(focus[axis]) - shift[axis] for axis in range(3)),
            up,
        ]
        self._sketch_occlusion_shift = (0.0, 0.0, 0.0)
        return True

    def _fit_parallel_scale(self, distance: float) -> None:
        """Den Ausschnitt der Parallelprojektion an den perspektivischen angleichen.

        VTK führt für beide Projektionen **getrennte** Größen: die
        Zentralprojektion lebt vom Blickwinkel, die Parallelprojektion von
        ``parallel_scale`` — der halben sichtbaren Höhe in Weltmaßen. Wer
        umschaltet, ohne die eine aus der anderen zu rechnen, springt auf
        VTKs Startwert von 1,0: ein sichtbarer Ausschnitt von zwei
        Millimetern.

        Die Umrechnung gilt in der Fokusebene, und dort liegt die Zeichnung —
        genau der Ort, an dem beide Projektionen dasselbe zeigen sollen.
        """
        camera = getattr(self.plotter, "camera", None) if self.plotter else None
        if camera is None or not getattr(camera, "parallel_projection", False):
            return
        angle = float(getattr(camera, "view_angle", 30.0))
        camera.parallel_scale = distance * math.tan(math.radians(angle) / 2.0)

    def show_sketch(
        self,
        curves: Sequence[SketchCurve],
        frame: PlaneFrame,
        step: float = 0.0,
        reach: float = 0.0,
        *,
        selected_curves: Sequence[int] = (),
        control_points: Sequence[Vec3] = (),
        selected_points: Sequence[int] = (),
        axis_names: tuple[str, str] = ("", ""),
        measure_labels: Sequence[tuple[Vec3, str]] = (),
        preview: Sequence[SketchCurve] = (),
    ) -> None:
        """Die Skizze und ihr Raster in die Szene legen (§30.1, Stufe zwei).

        Sie liegt damit **da, wo sie liegt** — auf ihrer Ebene, im Raum, und
        sie dreht sich mit der Kamera. Genau das war der Unterschied zum
        Zeichenblatt: Dort war die Ebenenwahl eine Beschriftung, hier ist sie
        zu sehen.

        Nichts hier rechnet: Die Punkte kommen aus
        :func:`app.core.sketch.profile.curves_of`, die Rasterlinien aus
        :func:`sketch_grid`. Beides ist ohne Plotter prüfbar, und was diese
        Methode hinzufügt, ist ausschließlich das Weiterreichen an VTK.

        **Alles unpickbar** (``pickable=False``), und das ist keine
        Feinheit: Der Zeiger fragt die Ebene rechnerisch
        (:func:`app.core.sketch.planes.ray_hit`), nicht über einen Treffer auf
        dem Raster. Ein pickbares Raster stünde der Auswahl von Körpern im
        Weg — und der Merkmalssuche, die den Sichtstrahl gegen die Hüllen der
        Szenenkörper prüft.

        Konstruktionsgeometrie bekommt ihren eigenen Actor: Sie trägt
        Bedingungen und bildet kein Profil, also darf sie auch nicht wie eine
        Kante aussehen.
        """
        self.clear_sketch()
        # Kameraereignisse melden Zoom und Drehung über ``cameraMoved``. Der
        # anschließende Neuaufbau hält hier den freien Bildbereich stabil,
        # bevor Raster, Maße und Griff projiziert werden.
        self._apply_sketch_occlusion()
        self._sketch_step = step
        # **Vor der Wache gemerkt, nicht danach.** Der Ziehgriff fragt diese
        # Kurven nach dem Umriss im Bild, und offscreen gibt es keinen Plotter:
        # Eine Zuweisung hinter dem ``return`` prüfte in der Suite niemand
        # (§35).
        self._sketch_curves = tuple(curves)
        self._sketch_selected_curves = tuple(selected_curves)
        self._sketch_control_points = tuple(control_points)
        self._sketch_selected_points = tuple(selected_points)
        plotter = self.plotter
        if plotter is None:
            return
        import numpy as np
        import pyvista as pv

        layers = sketch_grid_layers(frame, step, reach)

        def add_segments(
            segments: Sequence[SketchGridSegment],
            colour: str,
            width: int,
            opacity: float,
            name: str,
        ) -> None:
            """Eine Rasterstufe als einen ungreifbaren Aktor einfügen."""
            if not segments:
                return
            grid = np.asarray([point for pair in segments for point in pair], dtype=float)
            spans = np.hstack([[2, 2 * index, 2 * index + 1] for index in range(len(segments))])
            self._sketch_actors.append(
                plotter.add_mesh(
                    pv.PolyData(grid, lines=spans),
                    color=colour,
                    line_width=width,
                    opacity=opacity,
                    name=name,
                    render=False,
                    reset_camera=False,
                    pickable=False,
                )
            )

        add_segments(layers.minor, self._grid_minor_colour, 1, 0.32, "sketch_grid_minor")
        add_segments(layers.major, self._grid_major_colour, 1, 0.72, "sketch_grid_major")
        if layers.axes:
            # ``sketch_grid`` liefert erst die senkrechte Y-, dann die
            # waagerechte X-Achse. Buchstaben ergänzen die Farben (Regel 18).
            add_segments((layers.axes[0],), self._axis_y_colour, 2, 0.92, "sketch_axis_y")
            add_segments((layers.axes[1],), self._axis_x_colour, 2, 0.92, "sketch_axis_x")
            label_distance = AXIS_LABEL_PIXELS / max(self.pixels_per_mm(frame), EPS_GEOM)
            for point, label, colour, name in (
                (
                    to_world(frame, (label_distance, 0.0)),
                    axis_names[0],
                    self._axis_x_colour,
                    "sketch_axis_x_label",
                ),
                (
                    to_world(frame, (0.0, label_distance)),
                    axis_names[1],
                    self._axis_y_colour,
                    "sketch_axis_y_label",
                ),
            ):
                if not label:
                    continue
                self._sketch_actors.append(
                    plotter.add_point_labels(
                        np.asarray([point], dtype=float),
                        [label],
                        text_color=colour,
                        font_size=10,
                        bold=True,
                        show_points=False,
                        shape=None,
                        always_visible=True,
                        name=name,
                        render=False,
                        reset_camera=False,
                        pickable=False,
                    )
                )

        selected_curve_set = set(selected_curves)
        for construction in (False, True):
            chosen = [
                curve
                for index, curve in enumerate(curves)
                if index not in selected_curve_set
                and curve.construction is construction
                and len(curve.points) > 1
            ]
            if chosen:
                drawn = np.asarray(
                    [point for curve in chosen for point in curve.points], dtype=float
                )
                self._sketch_actors.append(
                    plotter.add_mesh(
                        pv.PolyData(
                            drawn,
                            lines=polyline_spans([len(curve.points) for curve in chosen]),
                        ),
                        color=self._sketch_colour,
                        line_width=1 if construction else 3,
                        # Die zweite Kodierung neben der Strichbreite (Regel
                        # 18): Hilfsgeometrie ist durchscheinend, und wer den
                        # Unterschied in der Breite nicht sieht, sieht ihn hier.
                        opacity=0.45 if construction else 1.0,
                        name=f"sketch_{'help' if construction else 'lines'}",
                        render=False,
                        reset_camera=False,
                        pickable=False,
                    )
                )

        chosen_curves = [
            curve
            for index, curve in enumerate(curves)
            if index in selected_curve_set and len(curve.points) > 1
        ]
        if chosen_curves:
            drawn = np.asarray(
                [point for curve in chosen_curves for point in curve.points], dtype=float
            )
            self._sketch_actors.append(
                plotter.add_mesh(
                    pv.PolyData(
                        drawn,
                        lines=polyline_spans([len(curve.points) for curve in chosen_curves]),
                    ),
                    color=SELECTED_COLOUR,
                    # Breite ist die zweite Kodierung neben der Farbe: Auch
                    # ohne Farbunterscheidung bleibt klar, was gewählt ist.
                    line_width=5,
                    name="sketch_selected_lines",
                    render=False,
                    reset_camera=False,
                    pickable=False,
                )
            )

        single = [curve.points[0] for curve in curves if len(curve.points) == 1]
        if control_points:
            # Dieselben Punkte kommen gleich als greifbare Kontrollpunkte;
            # ein Punkt-Element zweimal übereinander zu zeichnen macht es nur
            # ungleich groß, ohne eine zusätzliche Aussage zu tragen.
            single = []
        if single:
            self._sketch_actors.append(
                plotter.add_points(
                    np.asarray(single, dtype=float),
                    color=self._sketch_colour,
                    point_size=SKETCH_POINT_PIXELS,
                    render_points_as_spheres=True,
                    name="sketch_points",
                    render=False,
                    reset_camera=False,
                    pickable=False,
                )
            )
        selected_point_set = set(selected_points)
        plain_controls = [
            point for index, point in enumerate(control_points) if index not in selected_point_set
        ]
        chosen_controls = [
            point for index, point in enumerate(control_points) if index in selected_point_set
        ]
        if plain_controls:
            self._sketch_actors.append(
                plotter.add_points(
                    np.asarray(plain_controls, dtype=float),
                    color=self._sketch_colour,
                    point_size=7,
                    render_points_as_spheres=True,
                    name="sketch_control_points",
                    render=False,
                    reset_camera=False,
                    pickable=False,
                )
            )
        if chosen_controls:
            self._sketch_actors.append(
                plotter.add_points(
                    np.asarray(chosen_controls, dtype=float),
                    color=SELECTED_COLOUR,
                    point_size=14,
                    render_points_as_spheres=True,
                    name="sketch_selected_points",
                    render=False,
                    reset_camera=False,
                    pickable=False,
                )
            )
        if measure_labels:
            self._sketch_actors.append(
                plotter.add_point_labels(
                    np.asarray([point for point, _text in measure_labels], dtype=float),
                    [text for _point, text in measure_labels],
                    text_color=self._sketch_label_colour,
                    font_size=10,
                    bold=True,
                    show_points=False,
                    shape="rounded_rect",
                    shape_color=self._sketch_label_background,
                    fill_shape=True,
                    margin=5,
                    shape_opacity=0.94,
                    always_visible=True,
                    name="sketch_measures",
                    render=False,
                    reset_camera=False,
                    pickable=False,
                )
            )
        handle = self._pull_handle_segments()
        if handle and self._sketch_pull_offer is not None and self._sketch_pull_offer() == "ready":
            handle_points = np.asarray([point for pair in handle for point in pair], dtype=float)
            handle_lines = np.hstack(
                [[2, 2 * index, 2 * index + 1] for index in range(len(handle))]
            )
            self._sketch_actors.append(
                plotter.add_mesh(
                    pv.PolyData(handle_points, lines=handle_lines),
                    color=SELECTED_COLOUR,
                    line_width=5,
                    name="sketch_pull_handle",
                    render=False,
                    reset_camera=False,
                    pickable=False,
                )
            )
            inward, outward = handle[0]
            size = math.dist(inward, outward) / 2.0
            label_shift = tuple(frame.x_axis[axis] * size * 1.1 for axis in range(3))
            label_points = np.asarray(
                [
                    tuple(outward[axis] + label_shift[axis] for axis in range(3)),
                    tuple(inward[axis] + label_shift[axis] for axis in range(3)),
                ],
                dtype=float,
            )
            self._sketch_actors.append(
                plotter.add_point_labels(
                    label_points,
                    [str(tr("Hochziehen")), str(tr("Abtragen"))],
                    text_color=self._sketch_label_colour,
                    font_size=10,
                    bold=True,
                    show_points=False,
                    shape="rounded_rect",
                    shape_color=self._sketch_label_background,
                    fill_shape=True,
                    margin=4,
                    shape_opacity=0.94,
                    always_visible=True,
                    name="sketch_pull_labels",
                    render=False,
                    reset_camera=False,
                    pickable=False,
                )
            )
        self._set_sketch_preview(preview)
        self._draw()

    def show_sketch_planes(self, visible: bool) -> None:
        """Zeigt oder verbirgt die drei greifbaren Grundebenen im Bild."""
        self.plane_picker.setVisible(visible)
        if visible:
            self.plane_picker.place()

    def show_sketch_selection(self, text: str) -> None:
        """Quittiert die Auswahl in Worten; leer nimmt die Zeile weg."""
        self.sketch_selection.setText(text)
        self.sketch_selection.setVisible(bool(text))
        if text:
            self.sketch_selection.place()

    def show_sketch_action(self, text: str) -> None:
        """Zeigt den nächsten räumlichen Schritt; leer nimmt die Karte weg."""
        self.sketch_action.setText(text)
        self.sketch_action.setVisible(bool(text))
        if text:
            self.sketch_action.place()

    def _set_sketch_cursor(self, point: tuple[float, float] | None) -> bool:
        """Die Marke setzen, die zeigt, wohin der nächste Klick fällt.

        ``point`` ist der **gefangene** Ort in Zeichenkoordinaten, so wie ihn
        ``SketchCanvas.pointer_target`` liefert; ``None`` nimmt die Marke weg.
        Warum sie sein muss, steht bei :func:`sketch_cursor`.

        **Eigene Actorliste**, nicht ``_sketch_actors``: Die Marke folgt der
        Maus, die Zeichnung ändert sich beim Zeichnen. Lägen beide zusammen,
        räumte jedes ``_redraw_sketch`` die Marke weg, und sie käme erst mit
        der nächsten Mausbewegung wieder — ein Flackern genau während des
        Zeichnens.

        **Die Größe steht in Bildpunkten** (:data:`CURSOR_PIXELS`) und wird
        über den gemessenen Maßstab in Millimeter zurückgerechnet. Eine feste
        Zahl in Millimetern wäre herausgezoomt ein Punkt und hineingezoomt ein
        Kreuz über das halbe Bild; an die Rasterweite gekoppelt — der erste
        Anlauf — war sie bei 10 mm Raster gut und bei 2 mm zwei Bildpunkte
        groß. Gesehen hat das keine Rechnung, sondern die Aufnahme.

        **Ein Zeigerschritt, der nichts ändert, zeichnet nicht.** Das ist die
        Hälfte, an der die Sache steht: Ein Neuzeichnen der Szene kostet hier
        gemessen **6,9 ms**, und bei sechzig Mausereignissen in der Sekunde
        wären das 41 % eines Kerns im Qt-Hauptthread. Nicht die Rechnung ist
        teuer (``pixels_per_mm`` misst 0,004 ms, der Schnitt mit der Ebene
        0,006) und auch nicht der Actor — es ist ``render()`` selbst, und
        gegen das hilft nur, es seltener zu rufen.

        Das geht, weil die Marke am **gefangenen** Ort sitzt: Zwischen zwei
        Rasterpunkten ändert sie sich nicht, und bei 2 mm Raster sind das rund
        vierundzwanzig Bildpunkte Mausweg je Sprung. Verglichen wird Ort **und**
        Maßstab — beim Zoomen bleibt der Ort gleich und die Marke müsste ihre
        Größe ändern.

        **Das Netz entsteht dabei einmal, danach wandern nur seine vier
        Punkte.** Das allein hat nichts gebracht (gemessen 6,95 gegen 6,92 ms),
        aber es ist die richtige Bauart und macht den Sprung billig, wenn er
        kommt.
        """
        frame = self._sketch_frame
        if point is None or frame is None or self.plotter is None:
            changed = bool(self._cursor_actors)
            if self.plotter is not None:
                for actor in self._cursor_actors:
                    self.plotter.remove_actor(actor, render=False)
            self._cursor_actors.clear()
            self._cursor_mesh = None
            self._cursor_at = None
            return changed
        scale = self.pixels_per_mm(frame)
        if self._cursor_at == (point, scale):
            return False
        self._cursor_at = (point, scale)
        segments = sketch_cursor(frame, point, CURSOR_PIXELS / max(scale, EPS_GEOM))
        if not segments:
            return False

        import numpy as np
        import pyvista as pv

        points = np.asarray([end for pair in segments for end in pair], dtype=float)
        if self._cursor_mesh is not None and self._cursor_mesh.n_points == len(points):
            # Der übliche Fall: dasselbe Kreuz, anderswo.
            self._cursor_mesh.points = points
            self._cursor_mesh.Modified()
            return True

        spans = np.hstack([[2, 2 * index, 2 * index + 1] for index in range(len(segments))])
        mesh = pv.PolyData(points, lines=spans)
        self._cursor_mesh = mesh
        self._cursor_actors.append(
            self.plotter.add_mesh(
                mesh,
                color=self._sketch_colour,
                line_width=2,
                name="sketch_cursor",
                render=False,
                reset_camera=False,
                pickable=False,
            )
        )
        return True

    def _set_sketch_preview(self, curves: Sequence[SketchCurve]) -> bool:
        """Die mitfliegende Geometrie ändern, ohne selbst zu rendern."""
        visible = tuple(curve for curve in curves if len(curve.points) > 1)
        signature = tuple(tuple(curve.points) for curve in visible)
        if signature == self._preview_at:
            return False
        self._preview_at = signature
        if self.plotter is None or not visible:
            changed = self._preview_actor is not None
            if self.plotter is not None and self._preview_actor is not None:
                self.plotter.remove_actor(self._preview_actor, render=False)
            self._preview_actor = None
            self._preview_mesh = None
            self._preview_shape = ()
            return changed

        import numpy as np
        import pyvista as pv

        shape = tuple(len(curve.points) for curve in visible)
        points = np.asarray([point for curve in visible for point in curve.points], dtype=float)
        if self._preview_mesh is not None and self._preview_shape == shape:
            self._preview_mesh.points = points
            self._preview_mesh.Modified()
            return True
        if self._preview_actor is not None:
            self.plotter.remove_actor(self._preview_actor, render=False)
        mesh = pv.PolyData(points, lines=polyline_spans(shape))
        self._preview_mesh = mesh
        self._preview_shape = shape
        self._preview_actor = self.plotter.add_mesh(
            mesh,
            color=SELECTED_COLOUR,
            line_width=2,
            opacity=0.82,
            name="sketch_preview",
            render=False,
            reset_camera=False,
            pickable=False,
        )
        return True

    def show_sketch_cursor(self, point: tuple[float, float] | None) -> None:
        """Die Fangmarke setzen und nur bei sichtbarer Änderung zeichnen."""
        changed = self._set_sketch_cursor(point)
        if point is None:
            changed = self._set_sketch_preview(()) or changed
        # ``show_sketch_pointer`` bündelt Marke und Vorschau in einen Render,
        # führt diese öffentliche Schnittstelle aber weiterhin aus. Damit
        # bleiben bestehende Beobachter der Fangmarke verlässlich angebunden.
        self._sketch_cursor_changed = changed
        if changed and not getattr(self, "_sketch_pointer_batch", False):
            self._draw()

    def show_sketch_pointer(
        self,
        point: tuple[float, float] | None,
        preview: Sequence[SketchCurve] = (),
    ) -> None:
        """Fangmarke und Live-Vorschau mit genau einem Render nachziehen."""
        self._sketch_pointer_batch = True
        self._sketch_cursor_changed = False
        try:
            self.show_sketch_cursor(point)
        finally:
            self._sketch_pointer_batch = False
        changed = self._sketch_cursor_changed
        changed = self._set_sketch_preview(preview if point is not None else ()) or changed
        if changed:
            self._draw()

    def clear_sketch(self) -> None:
        """Nimmt die Zeichnung wieder aus der Szene.

        Der Bauraum bleibt: Er hängt an ``_frame_actors`` und gehört der
        Ansicht, nicht dem Modus.

        **Die Marke des Zeigers bleibt auch.** Sie hängt an der Maus und nicht
        an der Zeichnung; hier mitgeräumt verschwände sie bei jedem
        ``_redraw_sketch``, also bei jedem Strich, und käme erst mit der
        nächsten Mausbewegung wieder — ein Flackern genau während des
        Zeichnens. Weggenommen wird sie, wo der Modus endet:
        :meth:`set_sketching` mit ``None``.
        """
        if self.plotter is not None:
            for actor in self._sketch_actors:
                self.plotter.remove_actor(actor, render=False)
        self._sketch_actors.clear()

    def snapshot(self) -> Any | None:
        """Der Inhalt der Ansicht als Bild — oder ``None``, wenn keiner da ist.

        **Warum es das braucht.** Ein ``QWidget.grab`` über das Hauptfenster
        bekommt hier nichts: Der Plotter zeichnet in ein natives
        OpenGL-Kindfenster, und das malt nicht in Qts Puffer. Genau deshalb war
        die Bildmitte auf jedem Bild leer, das der Fehlerbogen mitschickte —
        ausgerechnet das Modell, um das es geht. Gemessen am 24.08.2026: eine
        einzige Farbe auf 100 % der Fläche.

        **Ein eigener Plotter, nicht der lebende.** ``self.plotter.screenshot``
        wäre der kürzere Weg und liefert sogar das genauere Bild — Druckplatte,
        Raster und Auswahl inbegriffen. Er greift aber in das Fenster, das der
        Kunde gerade vor sich hat: VTK meldete dabei
        ``FRAMEBUFFER_INCOMPLETE_ATTACHMENT``, und über die Suite stieg die
        Abrissquote von 2 aus 9 auf 2 aus 3. Beweisen ließ sich der
        Zusammenhang bei diesen Zahlen nicht — aber ein Bild für einen
        Fehlerbericht darf die Lage nicht verschlimmern, in der es entsteht.
        :mod:`app.ui.snapshots` geht denselben Weg und begründet ihn genauso:
        kurzlebig, weil festgehaltene VTK-Objekte den Abbau mitreißen.

        Der Preis ist ein Bild ohne Bauraum und Raster — das Modell aus der
        Blickrichtung des Kunden, nicht seine ganze Kulisse. Für die Frage
        „was hatte er vor sich?" ist das der Kern; die Kulisse steht in jedem
        anderen Bild derselben Anwendung.

        Ohne Plotter oder ohne Auswertung kommt ``None`` und kein schwarzes
        Bild: Offscreen gibt es beides nicht, und der Aufrufer soll den
        Unterschied sehen können.
        """
        if self.plotter is None or self._result is None or not self._result.scene.objects:
            return None
        import pyvista as pv
        from PySide6.QtGui import QImage

        from app.core.geom.mesh import as_mesh_data

        size = [max(16, self.width()), max(16, self.height())]
        shot = pv.Plotter(off_screen=True, window_size=size)
        try:
            for entry in self._result.scene.objects.values():
                # **Farbe und Grund kommen aus dem Fenster, nicht von
                # pyvista.** Mit den Vorgaben stünde ein türkiser Körper auf
                # weißem Grund — ein Bild, das der Support anders sieht als der
                # Kunde, und damit eine Auskunft, die in die Irre führt.
                shot.add_mesh(pv.wrap(as_mesh_data(entry.mesh).raw), color=self._object_colour)
            shot.set_background(self.plotter.background_color)
            # Dieselbe Blickrichtung wie im Fenster — ein Bild aus einer
            # anderen Richtung beantwortete die Frage nicht, die es stellt.
            shot.camera_position = self.plotter.camera_position
            # ``transparent_background=False`` macht die Drei-Kanal-Annahme
            # darunter zur **Zusage**: Die globale Theme-Einstellung könnte
            # sonst vier Kanäle liefern, und dann stimmte die Zeilenlänge nicht.
            raster = shot.screenshot(transparent_background=False, return_img=True)
        except Exception:  # pragma: no cover - Treiberlaunen, kein Programmfehler
            # Ein Bild, das nicht entsteht, darf keinen Fehlerbericht
            # verhindern — der Bogen ist dann eben ohne Bildmitte, statt gar
            # nicht abzugehen.
            _log.warning("the viewport could not render itself for a screenshot")
            return None
        finally:
            shot.close()
        if raster is None or getattr(raster, "ndim", 0) != 3 or raster.shape[2] < 3:
            return None
        height, width = int(raster.shape[0]), int(raster.shape[1])
        # ``copy`` ist Pflicht, nicht Vorsicht: ``QImage`` **borgt** den Puffer,
        # und ``raw`` fällt beim Verlassen dieser Funktion weg. Ohne die Kopie
        # zeigte das zurückgegebene Bild auf freigegebenen Speicher.
        raw = raster[:, :, :3].tobytes()
        return QImage(raw, width, height, width * 3, QImage.Format.Format_RGB888).copy()

    def pixels_per_mm(self, frame: PlaneFrame) -> float:
        """Wie viele Bildpunkte ein Millimeter auf dieser Ebene gerade misst.

        Der Maßstab, den die Zeichenfläche im Viewport-Modus braucht — für die
        Rasterweite und für alles, was in Bildpunkten gedacht ist. Sie kann ihn
        nicht selbst kennen: Ihr eigener steht auf dem Startwert, weil dort
        niemand mehr zoomt.

        **Gemessen und nicht aus der Kamera abgeleitet.** Zwei Punkte auf der
        Ebene, einen Millimeter auseinander, durch dieselbe Projektion
        geschickt, die auch das Bild macht — damit stimmt die Zahl bei
        Parallel- wie bei Zentralprojektion, ohne dass hier stünde, welche
        gerade gilt. Ein Kehrwert aus ``parallel_scale`` wäre die halbe
        Antwort und bei perspektivischer Ansicht die falsche.

        Null kommt nie zurück: Ohne Plotter oder bei entarteter Projektion
        steht der Startwert der Zeichenfläche, und der ist eine brauchbare
        Vorgabe statt einer Division durch null.
        """
        if self.plotter is None:
            return FALLBACK_SCALE
        # **Erst messen, wenn es etwas zu messen gibt.** Solange das Layout
        # nicht steht, meldet Qt die Startgröße eines Widgets (100 mal 30), und
        # die Projektion daran ist keine Aussage über das Bild, das der Nutzer
        # sieht. Siehe :data:`LEAST_VIEW_PIXELS`.
        interactor = getattr(self.plotter, "interactor", None)
        if interactor is not None:
            size = interactor.size()
            if min(size.width(), size.height()) < LEAST_VIEW_PIXELS:
                return FALLBACK_SCALE
        renderer = self.plotter.renderer
        here = to_world(frame, (0.0, 0.0))
        there = to_world(frame, (1.0, 0.0))
        seen = []
        for point in (here, there):
            renderer.SetWorldPoint(point[0], point[1], point[2], 1.0)
            renderer.WorldToDisplay()
            spot = renderer.GetDisplayPoint()
            seen.append((float(spot[0]), float(spot[1])))
        span = math.dist(seen[0], seen[1])
        return span if span > EPS_GEOM else FALLBACK_SCALE

    def _plane_distance(self) -> float:
        """Wie weit die Kamera von der Zeichenebene wegrückt.

        Der bisherige Abstand zum Blickpunkt, damit der Ausschnitt beim
        Schwenken erhalten bleibt.

        **Mit einer Untergrenze, und die ist kein Zierat.** In einem leeren
        Fenster hat ``reset_camera`` nie stattgefunden, und pyvista startet mit
        einer Kamera 1,62 Einheiten vor dem Ursprung. Diesen Abstand treu zu
        übernehmen hieße, aus 1,6 Millimetern auf die Zeichenebene zu sehen:
        gemessen 918 Bildpunkte je Millimeter, ein Raster von 0,1 mm und ein
        Bild, in dem nichts von dem steht, was man zeichnet.

        Getroffen hätte es ausgerechnet **Weg 2** — neu konstruieren, ohne
        Modell —, denn nur dort ist die Szene leer, wenn der Skizzenmodus
        beginnt. Mit geladenem Teil ist die Kamera längst eingepasst und die
        Grenze wirkungslos.
        """
        camera = getattr(self.plotter, "camera", None) if self.plotter else None
        position = getattr(camera, "position", None)
        focus = getattr(camera, "focal_point", None)
        if position is None or focus is None:
            return LEAST_PLANE_DISTANCE
        span = math.dist(tuple(position), tuple(focus))
        return max(span, LEAST_PLANE_DISTANCE)

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
        calls = _weak_callbacks(self)
        style = _InteractorStyle(
            self.plotter,
            scheme,
            calls.on_context,
            calls.on_pick,
            calls.on_cursor,
            on_paint=calls.on_paint,
            is_sculpting=calls.is_sculpting,
            on_body_drag=calls.on_body_drag,
            on_rotate_start=calls.on_rotate_start,
            on_camera=calls.on_camera,
        )
        self.plotter.interactor.SetInteractorStyle(style)
        # Ein neuer Stil bringt seine eigenen Beobachter mit; was beim Wechsel
        # sonst noch einzuschalten wäre, steht dort.
        self._enable_picking()

    def _on_right_click(self, x: int, y: int) -> None:
        """Ein Rechtsklick wählt aus und fragt nach dem Menü — und **ohne
        Stufen**, anders als der Linksklick.

        §18.5 nennt das Kontextmenü am Merkmal den Ort für Weg 1: ein fremdes
        Modell wird angepasst, indem man auf die Stelle zeigt, die stört. Bis
        hierher zeigte ein Rechtsklick auf einen Körper gar nichts — das Menü
        gab es nur im Objektbaum, wo die Merkmale `hole_3` heißen.

        **Die Aufteilung zwischen den Tasten.** Links wandert durch die Tiefe:
        erst das Teil, dann das Merkmal darin. Rechts fragt, was hier liegt,
        und meint immer das Genaueste — sonst wäre die Zusage aus §18.5 an eine
        Vorbedingung geknüpft, die niemand kennt: Man müsste die Bohrung erst
        linksklicken, um ihr Menü zu bekommen. Dieselbe Trennung hat Fusion
        360, wo der Rechtsklick auf das zeigt, was unter dem Zeiger liegt.

        Die Stufe geht dabei nicht verloren: Ein Rechtsklick, der eine Bohrung
        wählt, setzt die Auswahl auf sie — der nächste Linksklick daneben führt
        also von dort weiter und nicht von vorn.
        """
        # **Der Skizzenmodus kommt vor allem anderen**, wie beim Linksklick:
        # Ein Rechtsklick beim Zeichnen meint eine Stelle der Zeichenebene und
        # ihr Menü — nicht die Objektauswahl, die er sonst verstellt hätte.
        if self._sketch_frame is not None:
            hit = self._sketch_hit(x, y)
            if hit is not None:
                self.sketchMenuAt.emit(hit, x, y)
            return
        point = self._aim_at(x, y)
        if point is None:
            self.objectPicked.emit("")
            return
        # Zurück in die Szene, wie beim Linksklick (:meth:`_on_picked`, §25).
        # Hier fehlte es: Auf Platte 2 fragte der Rechtsklick eine Bettbreite
        # daneben nach dem Körper, fand dort meistens keinen und hob die
        # Auswahl auf, statt das Menü zu ihr zu zeigen.
        self._select_at(self._from_view(point), direct=True)
        self.contextMenuAt.emit(x, y)

    def _select_at(self, point: Vec3, *, direct: bool = False) -> bool:
        """Was ein Klick auswählt: der Körper, und eine Stufe tiefer sein
        Merkmal (§18.5). Gibt zurück, ob ein Merkmal dabei war.

        Welche Stufe ansteht, entscheidet :meth:`_click_target`. Was hier
        steht, ist die Reihenfolge des Sendens, und die ist keine
        Geschmacksfrage: **der Körper zuerst, das Merkmal danach.** Ein Merkmal
        gehört einem Objekt, und der Baum kann es nur unter dessen Zeile
        zeigen — ohne die Auswahl des Körpers tat ein Klick auf eine Bohrung
        nichts, weil noch nichts ausgewählt war. Der Weg zurück durch den Baum
        setzt das gewählte Merkmal dabei zurück, und deshalb kommt es
        anschließend.

        Linksklick und Rechtsklick nehmen denselben Weg, nur nicht dieselbe
        Stufe: ``direct`` überspringt sie (:meth:`_on_right_click`). Das Menü
        fragt danach nur noch, was zur Auswahl passt (§18.5).
        """
        object_id, feature_id = self._click_target(point, direct=direct)
        self.objectPicked.emit(object_id or "")
        if feature_id is None:
            # **Zurück auf den Körper, und zwar hier.** Bis zum 23.08.2026
            # stand hier nur ein ``return``, und der Docstring verließ sich
            # darauf, dass der Weg durch den Objektbaum das gewählte Merkmal
            # zurücksetzt. Das tut er nur, wenn sich die **Baumauswahl**
            # ändert — bei einem Klick auf die nackte Fläche desselben Körpers
            # bleibt sie gleich, der Baum sieht nichts und meldet nichts.
            #
            # Die Folge war eine Sackgasse: Ein einmal gewähltes Merkmal blieb
            # gewählt, ``selection_depth()`` stand weiter auf 2, und weder ein
            # weiterer Klick noch das Ziehen des Körpers kamen noch an. Der
            # Kommentar in ``_click_target`` sagte die Absicht bereits
            # („ein gewähltes Merkmal fällt weg"); eingelöst wurde sie nicht.
            if self._selected_feature is not None:
                self.select_feature(None)
            return False
        self.select_feature(feature_id)
        self.featurePicked.emit(feature_id)
        return True

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

    # --- den gewählten Körper direkt ziehen (§18.11) ---------------------------

    def begin_body_drag(self, x: int, y: int) -> bool:
        """Beginnt ein Ziehen, wenn dort der gewählte Körper liegt.

        **Der Weg, den jeder Slicer geht, und den Solidon nicht hatte.** Hier
        war es: Körper anklicken, *Bewegen* in der Werkzeugzeile holen, am
        Griff ziehen. Drei Schritte, und der mittlere ist der, den niemand
        erwartet — in PrusaSlicer, OrcaSlicer und Cura zieht man ein Objekt
        einfach. Deren Gizmos sind für das **Genaue** da; nachgelesen in ihren
        eigenen Sprachkatalogen heißen die Einträge „Gizmo move: Press to snap
        by 1mm" und „Gizmo-Move", also achsweise und rastend.

        Gibt ``False`` zurück, wenn dort nichts Gewähltes liegt — dann bleibt
        die linke Taste, was sie war. **Ohne diese Trennung wäre das Ziehen ein
        Modus mit anderem Namen:** Wer die Ansicht drehen will, dürfte nicht
        erst wegklicken müssen.
        """
        point = self._world_at(x, y) if self.plotter is not None else None
        return self.begin_body_drag_at(point)

    def can_drag_body_at(self, point: Vec3 | None) -> bool:
        """Ob an dieser Stelle der **gewählte** Körper liegt.

        Getrennt von :meth:`begin_body_drag_at`, weil die Frage vor der
        Entscheidung kommt: Beim Drücken steht noch nicht fest, ob daraus ein
        Zug wird oder ein Klick — das sagt erst die Bewegung. Gestartet wird
        deshalb später, geprüft aber sofort, denn nur wenn hier etwas
        Gewähltes liegt, darf die linke Taste überhaupt für den Körper
        reserviert werden statt für die Kamera.
        """
        if self._selected is None or point is None:
            return False
        return self._object_at(self._from_view(point)) == self._selected

    def begin_body_drag_at(self, point: Vec3 | None) -> bool:
        """Dasselbe, aber ab dem Weltpunkt — die Stelle, an der geprüft wird.

        Getrennt von :meth:`begin_body_drag`, weil das Ablesen und das Urteilen
        zwei Dinge sind: Offscreen rendert VTK nicht, und ein Picker über einem
        nie gezeichneten Bild trifft nichts. Ein Test über Bildschirmkoordinaten
        prüfte damit die Testumgebung; über den Weltpunkt prüft er die
        Bedienung.
        """
        if not self.can_drag_body_at(point):
            return False
        assert point is not None
        self._body_drag_from = point
        self._body_drag_offset = (0.0, 0.0)
        self.set_drag_cursor("moving")
        return True

    def continue_body_drag(self, x: int, y: int) -> None:
        """Der Körper folgt dem Zeiger — als Vorschau, nicht als Zustand.

        **In der Bettebene und nicht frei im Raum.** Ein Körper, den man beim
        Ziehen unbeabsichtigt anhebt, liegt danach nicht mehr auf dem Bett, und
        das merkt man erst beim Schneiden. Die Höhe bleibt dem Griff und dem
        Dialog — dieselbe Aufteilung wie in den Slicern.

        Verschoben wird der **Actor**, nicht die Geometrie (Regel 2): Was hier
        zu sehen ist, ist eine Vorschau. Der Schritt im Verlauf entsteht beim
        Loslassen.
        """
        self.continue_body_drag_at(self._plane_point(x, y))

    def continue_body_drag_at(self, now: tuple[float, float] | None) -> None:
        """Dasselbe ab den Bettkoordinaten — siehe :meth:`begin_body_drag_at`."""
        if self._body_drag_from is None or self._selected is None:
            return
        start = self._plane_point_of(self._body_drag_from)
        if now is None or start is None:
            return
        self._body_drag_offset = (now[0] - start[0], now[1] - start[1])
        actor = self._actors.get(self._selected)
        if actor is not None:
            base = self._actor_home.setdefault(self._selected, tuple(actor.GetPosition()))
            actor.SetPosition(
                base[0] + self._body_drag_offset[0], base[1] + self._body_drag_offset[1], base[2]
            )
            if self.plotter is not None:
                self.plotter.render()

    def finish_body_drag(self) -> None:
        """Aus dem Zug wird ein Schritt im Verlauf — oder gar nichts.

        **Die Vorschau bleibt stehen, bis das Ergebnis sie ersetzt.** Vorher
        wurde sie hier zurückgenommen, *bevor* das Signal ging — mit der
        Begründung, ein Actor, der den Zug noch zusätzlich trägt, stünde danach
        doppelt versetzt da. Das trifft nicht zu: :meth:`show_scene` räumt alle
        Aktoren ab (``self._actors.clear()``) und baut sie aus der Geometrie
        neu; einen Zug kann dabei keiner mitbringen.

        Was stattdessen zutraf, hat Robert am 23.08.2026 gesehen: „nach jedem
        verschieben springt die kamera und das modell immer komisch." Der
        Körper sprang beim Loslassen **an den Ausgangsort zurück** und erst
        eine bis zwei Sekunden später an sein Ziel — solange die Auswertung
        rechnete, zeigte das Bild das Gegenteil dessen, was der Nutzer gerade
        getan hatte.

        **Zurückgenommen wird nur, wenn kein Signal geht** — dann kommt auch
        keine neue Szene, und die Vorschau bliebe für immer stehen.
        """
        offset, self._body_drag_offset = self._body_drag_offset, (0.0, 0.0)
        self._body_drag_from = None
        self.set_drag_cursor(None)
        if abs(offset[0]) < EPS_DRAG and abs(offset[1]) < EPS_DRAG:
            # Ein Klick ist kein Zug. Ohne diese Grenze bekäme jede Auswahl
            # einen Schritt „Direkt bewegt" mit null Millimetern — und weil
            # dann kein Signal geht, wird hier auch die Vorschau abgeräumt.
            self._undo_body_preview()
            return
        self.transformDragged.emit(TransformSteps(offset=(offset[0], offset[1], 0.0)))

    # --- die Höhe aus der Querschau ziehen (§30.1, Ziehgriff) -----------------

    def set_sketch_pull(
        self,
        offer: Callable[[], str] | None,
        limits: tuple[float, float] = (0.0, 0.0),
        cut_limits: tuple[float, float] | None = None,
    ) -> None:
        """Verdrahtet den Ziehgriff des Skizzenmodus.

        ``offer()`` beantwortet, ob am Umriss gerade gezogen werden darf, und
        gibt eines von drei Dingen zurück:

        * ``"ready"`` — die Geste gilt,
        * einen **Grund** (übersetzt), wenn sie gerade nicht kann,
        * eine leere Zeichenkette, wenn sie hier gar nicht angeboten wird.

        **Die Frage stellt das Fenster, weil sie am Zustand der Zeichnung
        hängt** — Querschau, geschlossener Umriss, eine Operation, für die eine
        Höhe etwas bedeutet. Die Ansicht kennt davon nichts; sie kennt die
        Geste, den Griff im Bild und die Zahl am Zeiger.

        ``limits`` und ``cut_limits`` sind die Grenzen von Aufbau und Tasche
        **aus ihren Schemata**. Sie kommen von außen, damit keine Zahl hier
        abgeschrieben wird.

        ``None`` löst alles wieder — das Fenster tut es beim Verlassen des
        Modus, sonst hielte die Ansicht einen Rückruf auf ein gestorbenes Panel.
        """
        self._sketch_pull_offer = offer
        self._pull_limits = limits
        self._cut_limits = cut_limits
        if offer is None:
            self._end_pull()

    def pulling(self) -> bool:
        """Ob gerade eine Höhe gezogen wird.

        Von außen gefragt und nicht abgeleitet: Solange der Zug läuft, meint
        eine Mausbewegung die Höhe und nicht den Zeiger auf der Ebene — die
        Vorschau der Zeichnung muss dann stillhalten."""
        return self._pull_from is not None

    def _display_of(self, world: Sequence[float]) -> tuple[float, float] | None:
        """Wo ein Weltpunkt im Bild liegt — in VTKs Zählung, von unten.

        **Nicht** :meth:`sketch_screen_at`: Das rechnet in Qt-Logikpunkte um,
        weil es ein Qt-Kind platziert. Hier wird gegen die Stelle eines
        Mausereignisses verglichen, und die kommt aus dem Interactor, also in
        Bildpunkten des Geräts und von unten gezählt.
        """
        if self.plotter is None:
            return None
        renderer = self.plotter.renderer
        renderer.SetWorldPoint(float(world[0]), float(world[1]), float(world[2]), 1.0)
        renderer.WorldToDisplay()
        spot = renderer.GetDisplayPoint()
        return (float(spot[0]), float(spot[1]))

    def grip_reach(self, x: int, y: int) -> float:
        """Wie weit diese Bildstelle vom Umriss der Zeichnung entfernt ist.

        In Bildpunkten, und über **alle** Kurven: Der Griff ist der Umriss
        selbst. In der Querschau liegt er als Strich im Bild — dort ist „am
        Umriss" eine Handbreit Genauigkeit und keine Zielübung.

        Konstruktionsgeometrie zählt nicht mit: An ihr entsteht kein Körper,
        also gibt es dort nichts zu ziehen — dieselbe Grenze wie in
        :func:`pull_cage`.

        ``inf``, wenn es kein Bild oder keine Zeichnung gibt.
        """
        best = math.inf
        for curve in self._sketch_curves:
            if curve.construction:
                continue
            spots = [self._display_of(point) for point in curve.points]
            inside = [spot for spot in spots if spot is not None]
            if len(inside) != len(spots):
                # Ein Punkt, der nicht projiziert werden konnte, macht die
                # ganze Kurve unbrauchbar: Der Abstand zu einem Zug mit einem
                # fehlenden Glied wäre eine Zahl über einer anderen Form.
                continue
            best = min(best, polyline_distance(inside, (float(x), float(y))))
        return best

    def _pull_handle_segments(
        self,
    ) -> list[tuple[tuple[float, float, float], tuple[float, float, float]]]:
        """Die sichtbare Griffgeometrie in genau der gezeichneten Größe."""
        if self._sketch_frame is None:
            return []
        size = PULL_HANDLE_PIXELS / max(
            self.pixels_per_mm(self._sketch_frame),
            EPS_GEOM,
        )
        return pull_handle(self._sketch_frame, self._sketch_curves, size)

    def pull_handle_reach(self, x: int, y: int) -> float:
        """Wie weit die Bildstelle von Pfeil oder Kreuz des Ziehgriffs liegt."""
        best = math.inf
        for first, second in self._pull_handle_segments():
            spots = (self._display_of(first), self._display_of(second))
            if any(spot is None for spot in spots):
                continue
            best = min(
                best,
                polyline_distance(
                    [spot for spot in spots if spot is not None],
                    (float(x), float(y)),
                ),
            )
        return best

    def _pull_handle_base(self, x: int, y: int) -> tuple[float, float] | None:
        """Der Fuß des Griffs, wenn Pfeil oder Kreuz getroffen wurden."""
        if self._sketch_frame is None or self.pull_handle_reach(x, y) > PULL_HIT_PIXELS:
            return None
        handle = self._pull_handle_segments()
        if not handle:
            return None
        inward, outward = handle[0]
        base: Vec3 = (
            (inward[0] + outward[0]) / 2.0,
            (inward[1] + outward[1]) / 2.0,
            (inward[2] + outward[2]) / 2.0,
        )
        return to_plane(self._sketch_frame, base)

    def sketch_pull_ready(self, x: int, y: int) -> bool:
        """Ob hier ein Zug am Ziehgriff beginnen darf (§30.1).

        Zwei Bedingungen, und die Reihenfolge ist Absicht: **erst der Griff im
        Bild**, dann die Frage an das Fenster. Umgekehrt käme der Grund („der
        Umriss ist noch nicht geschlossen") bei jedem Druck irgendwo in der
        Ansicht, und ein Hinweis, der zu allem erscheint, sagt nichts.

        Der Griff reicht so weit wie die Fangmarke groß ist
        (:data:`CURSOR_PIXELS`) — was man sieht, kann man greifen. Eine zweite
        Zahl daneben wäre ein Bereich, in dem die Marke steht und der Griff
        nicht hält.

        **Und dass sich von hier aus überhaupt eine Höhe ablesen lässt**
        (:meth:`pull_height_at`). Das ist die dritte Bedingung, und sie fehlte:
        Angeboten wurde der Griff über die Ebenen**wahl**, gearbeitet wird mit
        der Blick**richtung**, und die beiden fallen bei einer Skizze auf einer
        angeklickten Fläche auseinander — dort hat der Blick nie denselben
        Namen wie die Zeichenebene, und bei frontaler Ansicht gab ``axis_hit``
        nichts zurück: Der Griff nahm die Taste und tat stumm nichts (gefunden
        von der Review-Sitzung, 27.08.2026). Keine zweite Schwelle, sondern
        dieselbe wie in :func:`axis_hit` — gefragt wird die Rechnung selbst.

        ``False`` heißt: Die linke Taste bleibt, was sie im jeweiligen
        Navigationsschema war. Ohne diese Trennung wäre der Ziehgriff ein Modus
        mit anderem Namen — wer die Ansicht drehen will, dürfte nicht erst
        wegklicken müssen.
        """
        if self._sketch_frame is None or self._sketch_pull_offer is None:
            return False
        on_outline = self.grip_reach(x, y) <= CURSOR_PIXELS
        on_handle = self.pull_handle_reach(x, y) <= PULL_HIT_PIXELS
        if not on_outline and not on_handle:
            return False
        base = self.pull_base_at(x, y)
        if base is None or self.pull_height_at(base, x, y) is None:
            return False
        answer = self._sketch_pull_offer()
        if answer == "ready":
            return True
        if answer and on_outline:
            self.sketchPullBlocked.emit(answer)
        return False

    def pull_base_at(self, x: int, y: int) -> tuple[float, float] | None:
        """Der Ort auf der Zeichenebene, durch den die Aufzugsachse läuft.

        Die Stelle, an der gegriffen wurde — nicht der Ursprung der Skizze. Das
        ist der Unterschied, den man sieht: Wer am rechten Rand eines Umrisses
        greift, zieht dort, und die Zahl am Zeiger gehört zu seiner Hand.

        Gefragt von :meth:`sketch_pull_ready` **und** von
        :meth:`begin_sketch_pull`, damit beide dieselbe Achse meinen: Eine
        Bereitschaft, die eine andere Stelle prüft als der Zug danach benutzt,
        wäre keine.
        """
        if self._sketch_frame is None:
            return None
        handle_base = self._pull_handle_base(x, y)
        if handle_base is not None:
            return handle_base
        base = self._sketch_hit(x, y)
        if base is not None:
            return base
        # In der Querschau streift der Blick die Ebene, und ``ray_hit`` gibt
        # dort nichts. Gegriffen wurde trotzdem am Umriss, also wird der Zug
        # nicht abgesagt: Die Achse bekommt den Punkt der Zeichnung, der im
        # Bild am nächsten liegt.
        return self._nearest_sketch_point(x, y)

    def pull_height_at(self, base: tuple[float, float], x: int, y: int) -> float | None:
        """Welche Höhe der Zeiger an dieser Bildstelle bedeutet — **ungeklemmt**.

        Die eine Stelle, an der aus einem Mausereignis ein Maß entlang der
        Aufzugsachse wird (:func:`axis_hit`). ``None`` heißt: von hier aus ist
        keine Höhe ablesbar — es gibt kein Bild, oder der Blick läuft entlang
        der Achse, und dann liegt sie als Punkt im Bild.

        Rasterfang und Grenzen kommen erst danach (:func:`pulled_height`); wer
        die **Richtung** eines Zugs beurteilen will, braucht das rohe Maß
        (:meth:`_pull_takes` im Loslassen).
        """
        if self._sketch_frame is None:
            return None
        ray = self._pick_ray(x, y)
        if ray is None:
            return None
        start, step = ray
        return axis_hit(self._sketch_frame, base, self._from_view(start), step)

    def begin_sketch_pull(self, x: int, y: int) -> bool:
        """Der Zug beginnt: Die Aufzugsachse steht ab jetzt fest."""
        base = self.pull_base_at(x, y) if self._sketch_frame is not None else None
        if base is None:
            return False
        self._pull_from = base
        self._pull_height = 0.0
        self._pull_raw = None
        self._drag_kind = "pull"
        # Der Zeiger auf der Ebene hält still, solange gezogen wird — sonst
        # zeichnete die Vorschau der Skizze dem Zug hinterher.
        self.show_sketch_cursor(None)
        self.set_drag_cursor("move")
        return True

    def _nearest_sketch_point(self, x: int, y: int) -> tuple[float, float] | None:
        """Der Zeichenpunkt, der im Bild dieser Stelle am nächsten liegt.

        Der Rückfall für :meth:`begin_sketch_pull`: Er braucht einen Ort auf
        der Ebene, und genau in der Querschau — dort, wo gezogen wird — liefert
        der Schnitt mit ihr keinen. Gefragt werden die Punkte, die ohnehin im
        Bild stehen; einer davon ist immer der richtige, denn gegriffen wurde
        am Umriss.
        """
        if self._sketch_frame is None:
            return None
        best: tuple[float, float] | None = None
        closest = math.inf
        for curve in self._sketch_curves:
            if curve.construction:
                continue
            for point in curve.points:
                spot = self._display_of(point)
                if spot is None:
                    continue
                reach = math.dist(spot, (float(x), float(y)))
                if reach < closest:
                    closest = reach
                    best = to_plane(self._sketch_frame, (point[0], point[1], point[2]))
        return best

    def continue_sketch_pull(self, x: int, y: int) -> None:
        """Die Höhe folgt dem Zeiger — als Drahtform und als Zahl.

        Gerechnet wird die Höhe in :func:`pulled_height` (Rasterfang und die
        Grenzen der Operation, mit Begründung); hier steht der Weg vom
        Mausereignis dorthin und zurück ins Bild.

        **Neu gezeichnet wird nur, wenn sich die Höhe geändert hat.** Sie sitzt
        am gefangenen Ort, ändert sich also zwischen zwei Rasterpunkten nicht —
        dieselbe Ersparnis, an der die Fangmarke hängt.
        """
        if self._pull_from is None:
            return
        reach = self.pull_height_at(self._pull_from, x, y)
        if reach is None:
            return
        # **Das rohe Maß wird gemerkt, nicht nur das geklemmte.** Beim
        # Loslassen entscheidet es, ob überhaupt in die Richtung gezogen wurde,
        # in die der Körper wächst — geklemmt sind beide Richtungen gleich weit
        # von null entfernt.
        self._pull_raw = reach
        height = pulled_height(reach, self._sketch_step, self._limits_for(reach))
        if abs(height - self._pull_height) <= EPS_GEOM:
            return
        self._pull_height = height
        self._show_pull_cage()
        if not self.drag_bar.typing:
            self.drag_bar.anchor = self._pointer_spot(x, y)
        self.drag_bar.follow_length(tr("Tiefe") if height < 0.0 else tr("Höhe"), abs(height))

    def _pointer_spot(self, x: int, y: int) -> QPoint:
        """Die Stelle des Zeigers in Qt-Logikpunkten, für das Wertfeld.

        Der Interactor zählt von unten und in Gerätepunkten, ein Qt-Kind wird
        von oben und in Logikpunkten gesetzt — dieselbe Umrechnung wie in
        :meth:`sketch_screen_at`, nur in der anderen Richtung.
        """
        if self.plotter is None:
            return QPoint(int(x), int(y))
        ratio = float(self.plotter.interactor.devicePixelRatioF()) or 1.0
        height = float(self.plotter.interactor.height())
        return QPoint(int(x / ratio), int(height - y / ratio))

    def _show_pull_cage(self) -> None:
        """Legt die Drahtform des Zugs in die Szene — oder nimmt sie weg."""
        actors = tuple(self._pull_actors)
        self._pull_actors.clear()
        if self.plotter is None:
            return
        for actor in actors:
            self.plotter.remove_actor(actor, render=False)
        segments = (
            pull_cage(self._sketch_frame, self._sketch_curves, self._pull_height)
            if self._sketch_frame is not None
            else []
        )
        if not segments:
            self._draw()
            return

        import numpy as np
        import pyvista as pv

        points = np.asarray([end for pair in segments for end in pair], dtype=float)
        spans = np.hstack([[2, 2 * index, 2 * index + 1] for index in range(len(segments))])
        self._pull_actors.append(
            self.plotter.add_mesh(
                pv.PolyData(points, lines=spans),
                color=self._sketch_colour,
                line_width=2,
                name="sketch_pull",
                render=False,
                reset_camera=False,
                pickable=False,
            )
        )
        self._draw()

    def finish_sketch_pull(self) -> None:
        """Aus dem Zug wird eine Operation — oder gar nichts.

        Die Drahtform bleibt stehen, bis das Ergebnis sie ersetzt; dieselbe
        Begründung wie beim Körperzug (:meth:`finish_body_drag`). Nur wenn kein
        Signal geht, wird hier abgeräumt — dann kommt auch keine neue Szene.
        """
        if self.drag_bar.typing:
            # Der Zug gehört der Tastatur (§18.11): Loslassen wendet nichts an,
            # die Eingabetaste wird es tun. Dieselbe Zusage wie beim Gizmo —
            # das Feld bleibt mit der getippten Zahl stehen.
            return
        height = self._pull_height
        if self._pull_from is None or not self._pull_takes(height):
            # Ein Klick ist kein Zug.
            self._end_pull()
            return
        self._pull_from = None
        self._drag_kind = None
        self.drag_bar.dismiss()
        self.set_drag_cursor(None)
        self.sketchPulled.emit(float(height))

    def _pull_takes(self, height: float) -> bool:
        """Ob diese Höhe eine Operation ergibt — die Grenze an **einer** Stelle.

        Gefragt vom Loslassen und von der Eingabetaste, und zwar über die Höhe,
        die auch angewandt würde. Vorher stand die Untergrenze an zwei Stellen
        und die Obergrenze an keiner: Eine getippte Höhe von 4000 mm ging bei
        einem Höchstwert von 1000 durch, und der Dialog klemmte sie danach
        kommentarlos — genau die Zusage, die der Kommentar an
        :func:`pulled_height` gibt.

        **Nicht** gefragt von der Richtungsprüfung. Die sieht das ungeklemmte
        Maß und hat nur eine Grenze: Ein Zug bis zum Anschlag liegt über der
        Obergrenze und ist trotzdem gemeint.

        Die Obergrenze **lehnt ab statt zu klemmen**, anders als beim Ziehen.
        Das ist kein Widerspruch, sondern die Regel von :meth:`_apply_typed`:
        Wer zieht, meint eine Bewegung, und die darf am Anschlag stehen bleiben;
        wer tippt, meint genau diese Zahl, und sie stillschweigend zu ändern
        wäre eine Antwort auf eine andere Frage.
        """
        if height < 0.0 and self._cut_limits is None:
            return False
        least, most = self._limits_for(height)
        amount = abs(height)
        if amount < max(least, EPS_GEOM):
            return False
        return not (most > least and amount > most)

    def _limits_for(self, height: float) -> tuple[float, float]:
        """Grenzen der Richtung: außen aufziehen, innen ausschneiden."""
        if height < 0.0:
            return self._cut_limits or (0.0, 0.0)
        return self._pull_limits

    def _end_pull(self) -> None:
        """Der Zug ist vorbei, ohne Ergebnis: Drahtform weg, Zahl weg."""
        self._pull_from = None
        self._pull_height = 0.0
        self._pull_raw = None
        if self._drag_kind == "pull":
            self._drag_kind = None
        self.drag_bar.dismiss()
        self._show_pull_cage()
        self.set_drag_cursor(None)

    def cancel_sketch_pull(self) -> None:
        """Verwirft die Drahtvorschau, wenn das Fenster den Zug ablehnt."""
        self._end_pull()

    def _undo_body_preview(self) -> None:
        """Setzt gezogene Aktoren an ihren Ausgangsort zurück."""
        for object_id, home in self._actor_home.items():
            actor = self._actors.get(object_id)
            if actor is not None:
                actor.SetPosition(*home)
        self._actor_home.clear()

    def _plane_point(self, x: int, y: int) -> tuple[float, float] | None:
        """Wo der Zeiger auf der Bettebene steht, in Weltkoordinaten."""
        point = self._world_at(x, y)
        return self._plane_point_of(point) if point is not None else None

    def _plane_point_of(self, point: Vec3) -> tuple[float, float] | None:
        """Die Bettkoordinaten eines Ansichtspunkts."""
        world = self._from_view((float(point[0]), float(point[1]), float(point[2])))
        return (float(world[0]), float(world[1]))

    def set_sketching(self, frame: PlaneFrame | None) -> None:
        """Von jetzt an trifft ein Klick die Zeichenebene, nicht die Szene.

        ``None`` beendet den Modus. Solange ein Rahmen steht, gehen Klick und
        Zeigerbewegung nicht mehr durch die Auswahlkette, sondern durch
        :meth:`_sketch_hit` — dort ist eine **Stelle auf der Ebene** gemeint
        und kein Ding in der Szene.
        """
        if frame is None:
            self._remove_sketch_occlusion()
        self._sketch_frame = frame
        if frame is not None:
            self._apply_sketch_occlusion()
        # **Die Marke gehört der Ebene, auf der sie liegt** — sie ist das
        # einzige Stück Zeichnung, das ``clear_sketch`` absichtlich stehen
        # lässt (dort steht der Grund), und deshalb muss sie hier weg. Nicht
        # nur beim Ende des Modus: Ein Ebenenwechsel ruft dieselbe Methode mit
        # einem **neuen** Rahmen, und eine Marke, die dann stehen bleibt,
        # schwebt auf der vorigen Ebene im Raum, bis die Maus sich das nächste
        # Mal bewegt. Wer die Ebene über die Ziffern wechselt und die Hand
        # stillhält, sieht genau das.
        self.show_sketch_cursor(None)
        # **Der Boden des Bauraums tritt ab, seine Kanten bleiben.** Zwei
        # Gitter übereinander sind eines zu viel: Bettraster und Zeichenraster
        # sind beide graue Linien in derselben Größenordnung, und welches die
        # Ebene ist, auf der gerade gezeichnet wird, sähe man nicht mehr. Bei
        # einer Skizze auf ``plane:xy`` liegen sie sogar exakt ineinander.
        #
        # **Die Kanten und die Maßskala gehen deshalb nicht mit**, und das ist
        # der Unterschied, der beim ersten Anlauf verlorenging: Sie sind kein
        # zweites Gitter, sondern eine **Grenze**. Das Handbuch verspricht
        # genau sie — „wer darüber hinauszeichnet, liest es an derselben
        # Linie" —, und beim Zeichnen ist das die früheste Stelle, an der
        # auffällt, dass ein Teil nicht auf das Bett passt. Wer sie mit
        # ausblendet, nimmt dem Kunden die Auskunft dort, wo sie am meisten
        # wert ist.
        for actor in self._ground_actors:
            actor.SetVisibility(frame is None)
        # **Der Körper ist Zusammenhang, nicht Zeichenfläche.** 45 %
        # Deckkraft ließen im Handbuchbild selbst eine eingeprägte Schrift
        # lauter erscheinen als die weiße Skizze. Beim Eintritt wird der
        # bestehende Aktor sofort gedämpft; ein späterer Szenenaufbau nimmt
        # denselben Wert in ``show_scene``. Beim Verlassen gilt wieder der
        # gewählte Darstellungsmodus.
        opacity = (
            SKETCH_CONTEXT_OPACITY
            if frame is not None
            else float(DISPLAY_MODES[self._mode]["opacity"])
        )
        for actor in self._actors.values():
            actor.prop.opacity = opacity
        for actor in self._shadow_actors:
            actor.SetVisibility(frame is None)
        self._apply_selection_colour()
        # Und ein Zug am Ziehgriff endet mit der Ebene, auf der er begann —
        # aus demselben Grund wie die Marke darüber.
        self._end_pull()
        self._update_cursor()
        self._draw()

    def set_sketch_entry(
        self,
        pending: Callable[[], float] | None,
        begin: Callable[[Any], bool] | None,
    ) -> None:
        """Verdrahtet die Maßeingabe des Skizzenmodus (E19).

        Beides zusammen oder beides ``None`` — das Fenster setzt sie beim
        Betreten und löst sie beim Verlassen, damit hier keine Referenz auf
        ein gestorbenes Panel liegen bleibt.
        """
        self._sketch_measure_pending = pending
        self._sketch_measure_begin = begin

    def set_sketch_edit(
        self,
        ready: Callable[[tuple[float, float]], bool] | None,
        begin: Callable[[tuple[float, float]], bool] | None,
        move: Callable[[tuple[float, float]], None] | None,
        end: Callable[[], None] | None,
    ) -> None:
        """Auswählen und Ziehen der Skizzengeometrie im Viewport verdrahten.

        Die Ansicht übersetzt nur Mausstellen in Ebenenkoordinaten und führt
        die Geste. Auswahl, Fang, Solver und Undo bleiben beim Canvas. Vier
        ``None`` lösen die Verbindung beim Verlassen des Modus vollständig.
        """
        self._sketch_edit_ready = ready
        self._sketch_edit_begin = begin
        self._sketch_edit_move = move
        self._sketch_edit_end = end
        if ready is None:
            self._sketch_gesture = None

    def sketch_screen_at(self, point: tuple[float, float]) -> QPoint | None:
        """Wo eine Stelle der Zeichenebene im Bild liegt — in Qt-Logikpunkten.

        Die Umkehrung von :meth:`_sketch_hit`, für das verliehene Maßfeld:
        Es liegt als Qt-Kind über der Ansicht und braucht deren Koordinaten.
        ``None``, wenn es kein Bild gibt oder keine Ebene steht.
        """
        if self.plotter is None or self._sketch_frame is None:
            return None
        world = to_world(self._sketch_frame, point)
        renderer = self.plotter.renderer
        renderer.SetWorldPoint(world[0], world[1], world[2], 1.0)
        renderer.WorldToDisplay()
        display = renderer.GetDisplayPoint()
        ratio = float(self.plotter.interactor.devicePixelRatioF()) or 1.0
        height = float(self.plotter.interactor.height())
        return QPoint(int(display[0] / ratio), int(height - display[1] / ratio))

    def _sketch_hit(self, x: int, y: int) -> tuple[float, float] | None:
        """Wo der Sichtstrahl durch diese Bildstelle die Zeichenebene trifft.

        **Gerechnet und nicht gepickt.** Ein ``vtkCellPicker`` trifft nur
        Geometrie; die Zeichenebene ist keine, und über einer Durchgangsbohrung
        gäbe es nicht einmal ein Dreieck dahinter (gemessen von ``formwerk-d1``
        am Referenzkorpus). :func:`app.core.sketch.planes.ray_hit` trifft sie
        immer — auch dort, wo der Körper ein Loch hat.

        **Der Strahl wird in die Szene zurückgerechnet**, und zwar nur sein
        Ursprung: Die Richtung ist ein Vektor und von der Plattenverschiebung
        unberührt. Ohne das läge eine Skizze auf Platte 2 eine Bettbreite
        daneben — derselbe Fehler, den :meth:`_from_view` für den Klick auf
        einen Körper abfängt (§25).
        """
        if self._sketch_frame is None:
            return None
        ray = self._pick_ray(x, y)
        if ray is None:
            return None
        start, step = ray
        return ray_hit(self._sketch_frame, self._from_view(start), step)

    def _on_left_click(self, x: int, y: int) -> None:
        """Ein Linksklick, der keiner Kamerabewegung galt (§18.5).

        Der Weg ist derselbe wie beim Rechtsklick, nur ohne Menü danach: erst
        das Merkmal unter dem Zeiger, sonst der Körper, und ein Klick daneben
        hebt die Auswahl auf.

        **Gefragt wird :meth:`_aim_at` und nicht :meth:`_world_at`**: Ein Klick
        in eine Bohrung trifft dort oft kein Dreieck, und ohne diesen Umweg hob
        er die Auswahl auf, statt die Bohrung zu wählen (:meth:`_bore_aim`).

        **Aber nur, wenn der Klick auswählt.** Formen, Bemalen, Messen,
        Trennen und Skelett setzen eine **Stelle**, und die liegt auf der
        Oberfläche: Ein Punkt auf der Bohrungsachse wäre dort einer in der Luft
        — bemalt würde nichts, und der Pinselring stünde im Leeren. Welche
        Werkzeuge das sind, sagt :meth:`_resting_role` und nicht eine zweite
        Aufzählung derselben Flaggen.
        """
        # **Der Skizzenmodus kommt vor allem anderen** (§30.1, P4). Dort
        # meint ein Klick eine Stelle auf der Zeichenebene, und die liegt
        # oft dort, wo gar keine Geometrie ist — über einem Loch, neben dem
        # Teil, in der Luft. Die Auswahlkette darunter fragt nach Dingen
        # und hätte dort nichts zu antworten.
        if self._sketch_frame is not None:
            hit = self._sketch_hit(x, y)
            if hit is not None:
                self.sketchPointPicked.emit(hit)
            return
        point = self._aim_at(x, y) if self._means_a_feature() else self._world_at(x, y)
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
    return _world_at_depth(renderer, x, y, renderer.GetDisplayPoint()[2])


def _world_at_depth(
    renderer: Any, x: int, y: int, depth: float
) -> tuple[float, float, float] | None:
    """Der Weltpunkt hinter einer Bildschirmstelle in dieser Bildtiefe.

    ``depth`` ist die Tiefe, in der VTK sein Bild aufspannt: 0 ist die nahe,
    1 die ferne Ebene. Zwei Punkte daraus sind der Sichtstrahl
    (:meth:`Viewport._pick_ray`), einer auf der Fokusebene ist der Ort unter
    dem Zeiger (:func:`_world_under`).
    """
    renderer.SetDisplayPoint(float(x), float(y), float(depth))
    renderer.DisplayToWorld()
    point = renderer.GetWorldPoint()
    if abs(point[3]) < EPS_GEOM:
        return None
    return (point[0] / point[3], point[1] / point[3], point[2] / point[3])


def apply_wheel_zoom(camera: Any, factor: float) -> None:
    """Ein Radschritt an der Kamera — in **beiden** Projektionen.

    ``vtkCamera.Dolly`` bewegt nur die Position, und in der Parallelprojektion
    bestimmt allein ``parallel_scale`` die Bildgröße — die Position ist ihr
    gleichgültig. Das Rad war damit überall tot, wo orthografisch gearbeitet
    wird, im Skizzenmodus also immer (§30.1 stellt dort orthografisch):
    gemessen am 26.08.2026, acht Radschritte, Bild byteweise unverändert.
    VTKs eigener Trackball-Dolly (rechte Taste im CAD-Schema) trägt dieselbe
    Fallunterscheidung — nur der direkte ``Dolly``-Aufruf trug sie nicht.

    Eine freie Funktion aus demselben Grund wie :func:`sketch_grid`:
    Offscreen gibt es keinen Plotter, und was hinter dieser Wache gerechnet
    wird, prüft in der Suite niemand mehr.
    """
    if camera.GetParallelProjection():
        camera.SetParallelScale(camera.GetParallelScale() / factor)
    else:
        camera.Dolly(factor)


class _ViewCallbacks(NamedTuple):
    """Die Rückrufe, die der Interaktionsstil von der Ansicht bekommt."""

    on_context: Callable[[int, int], None]
    on_pick: Callable[[int, int], None]
    on_cursor: Callable[[str | None], None]
    on_paint: Callable[[int, int, bool], None]
    is_sculpting: Callable[[], bool]
    on_body_drag: Callable[[str, int, int], bool]
    on_rotate_start: Callable[[], None]
    on_camera: Callable[[], None]


def _weak_callbacks(view: Viewport) -> _ViewCallbacks:
    """Rückrufe an die Ansicht, die sie **nicht** am Leben halten.

    Schwach gehalten, mit Absicht: VTK hält den Stil, der Stil hielte sonst den
    Viewport, und der hält den Plotter, der den Interactor hält. Diese Schleife
    überlebt jedes Schließen — der Speicherbereiniger räumt sie später ab, und
    dann steht ein C++-Objekt hinter einer Python-Referenz, die es nicht mehr
    gibt. Das ist der Absturz ohne Zeile, den die Suite als Access Violation am
    Ende eines Laufs zeigt.

    **Als eigene Funktion, damit die Aussage prüfbar ist.** Sie stand in
    ``set_navigation`` hinter dem Plotter-Zweig und lief damit offscreen nie:
    Die einzige Vorkehrung gegen den bekanntesten Absturz des Projekts war die
    einzige, die kein Test erreichte. Hier braucht sie kein VTK — der Stil
    schon, die Rückrufe an ihn nicht (§35).
    """
    weak = weakref.ref(view)

    def on_context(x: int, y: int) -> None:
        found = weak()
        if found is not None:
            found._on_right_click(x, y)

    def on_pick(x: int, y: int) -> None:
        found = weak()
        if found is not None:
            found._on_left_click(x, y)

    def on_cursor(role: str | None) -> None:
        found = weak()
        if found is not None:
            found.set_drag_cursor(role)

    def on_paint(x: int, y: int, fresh: bool) -> None:
        found = weak()
        if found is not None:
            found._on_paint_drag(x, y, fresh)

    def is_sculpting() -> bool:
        found = weak()
        return found is not None and found._sculpting

    def on_body_drag(phase: str, x: int, y: int) -> bool:
        """Beginn, Fortgang und Ende eines Zugs am gewählten Körper.

        Eine Funktion für drei Schritte statt drei Rückrufe: Der Stil hält sie
        schwach, und drei schwache Verweise auf dieselbe Ansicht sind dreimal
        dieselbe Prüfung auf ``None``.
        """
        found = weak()
        if found is None:
            return False
        # **Im Skizzenmodus zieht dieselbe Geste eine Höhe** (§30.1). Derselbe
        # Rückruf und keine zweite Zustandsmaschine daneben: Drücken, Schwelle,
        # Ziehen, Loslassen sind hier wie dort dieselben vier Schritte, und zwei
        # Schwellen für „ist das ein Klick oder ein Zug" wären das Loch, das der
        # Körperzug schon einmal hatte.
        if found._sketch_frame is not None:
            if phase == "ready":
                found._sketch_gesture = None
                # Der gezeichnete Pfeil und das Kreuz sind der ausdrückliche
                # Höhen-Griff. Sie haben Vorrang vor jeder Kurve, die im Bild
                # zufällig darunterliegt, und vor der Kameranavigation.
                if found.pull_handle_reach(x, y) <= PULL_HIT_PIXELS and found.sketch_pull_ready(
                    x, y
                ):
                    found._sketch_gesture = "pull"
                    return True
                point = found._sketch_hit(x, y)
                if (
                    point is not None
                    and found._sketch_edit_ready is not None
                    and found._sketch_edit_ready(point)
                ):
                    found._sketch_gesture = "edit"
                    return True
                if found.sketch_pull_ready(x, y):
                    found._sketch_gesture = "pull"
                    return True
                return False
            if phase == "start":
                if found._sketch_gesture == "edit":
                    point = found._sketch_hit(x, y)
                    started = bool(
                        point is not None
                        and found._sketch_edit_begin is not None
                        and found._sketch_edit_begin(point)
                    )
                    if not started:
                        # Zwischen Vorprüfung und Zugbeginn kann sich die
                        # Auswahl ändern. Dann darf die abgewiesene Geste
                        # keinen späteren Mauszug mehr als Bearbeitung deuten.
                        found._sketch_gesture = None
                    return started
                return found.begin_sketch_pull(x, y)
            if phase == "move":
                if found._sketch_gesture == "edit":
                    point = found._sketch_hit(x, y)
                    if point is not None and found._sketch_edit_move is not None:
                        found._sketch_edit_move(point)
                else:
                    found.continue_sketch_pull(x, y)
                return True
            if found._sketch_gesture == "edit":
                if found._sketch_edit_end is not None:
                    found._sketch_edit_end()
            else:
                found.finish_sketch_pull()
            found._sketch_gesture = None
            return True
        if phase == "ready":
            # Nur die Frage, ob hier der gewählte Körper liegt — der Zug
            # beginnt erst, wenn die Bewegung die Klickschwelle verlässt.
            world_point = found._world_at(x, y) if found.plotter is not None else None
            return found.can_drag_body_at(world_point)
        if phase == "start":
            return found.begin_body_drag(x, y)
        if phase == "move":
            found.continue_body_drag(x, y)
            return True
        found.finish_body_drag()
        return True

    def on_rotate_start() -> None:
        found = weak()
        if found is not None:
            found._aim_rotation()

    def on_camera() -> None:
        # Der Radzoom läuft am Interactor-Ereignis vorbei (kein
        # ``EndInteractionEvent``) — dieser Rückruf ist sein Meldeweg.
        found = weak()
        if found is not None:
            found.cameraMoved.emit()

    return _ViewCallbacks(
        on_context,
        on_pick,
        on_cursor,
        on_paint,
        is_sculpting,
        on_body_drag,
        on_rotate_start,
        on_camera,
    )


def _InteractorStyle(  # noqa: N802
    plotter: Any,
    scheme: NavigationScheme,
    on_context: Any = None,
    on_pick: Any = None,
    on_cursor: Any = None,
    on_paint: Any = None,
    is_sculpting: Any = None,
    on_body_drag: Any = None,
    on_rotate_start: Any = None,
    on_camera: Any = None,
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
            self.AddObserver("MouseMoveEvent", self._mouse_move)
            self._painting = False
            """Ob die linke Taste gerade malt statt die Kamera zu führen.
            Nur im Formzustand, und nur ohne Umschalt — schieben muss auch
            mitten in der Sitzung gehen."""
            self._right_at: tuple[int, int] | None = None
            """Wo die rechte Taste heruntergegangen ist. In jedem Schema tut
            Rechts auch etwas an der Kamera — das Menü darf nur aufgehen, wenn
            niemand gezogen hat."""
            self._left_at: tuple[int, int] | None = None
            """Dasselbe für links. In drei der vier Schemata dreht die linke
            Taste; ausgewählt wird deshalb, wo niemand gezogen hat, und nicht
            danach, welches Schema gerade gilt."""
            self._ready_to_drag = False
            """Ob die linke Taste **auf** dem gewählten Körper heruntergegangen
            ist. Noch keine Entscheidung: Erst die Bewegung sagt, ob daraus ein
            Zug wird oder ein Klick."""
            self._dragging_body = False
            """Ob der Zug tatsächlich läuft — also die Klickschwelle
            überschritten wurde."""

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
            if is_sculpting is not None and is_sculpting() and not self._shift():
                # Malen statt Kamera (§18.11): Die Züge folgen dem gedrückten
                # Zeiger, der erste sitzt beim Drücken. Ein Klick je Zug hieß
                # zwanzig Klicks für einen Grat — in jedem Formprogramm ist
                # das ein Zug. Umschalt behält die Kamera, schieben muss auch
                # mitten in der Sitzung gehen.
                self._painting = True
                if on_paint is not None:
                    on_paint(*self._left_at, True)
                return
            grabs = on_body_drag is not None and not self._shift()
            if grabs and on_body_drag("ready", *self._left_at):
                # **Auf dem gewählten Körper führt Links ihn, nicht die
                # Kamera** (§18.11). Der Rückruf urteilt selbst und gibt
                # ``False`` zurück, wenn dort nichts Gewähltes liegt — dann
                # bleibt die linke Taste, was sie im jeweiligen Schema war.
                #
                # **Vorgemerkt, nicht gestartet.** Ob dies ein Klick oder ein
                # Zug wird, entscheidet erst die Bewegung — und zwar an
                # derselben Schwelle, an der auch :func:`is_click` urteilt.
                # Zwei verschiedene Schwellen ergaben ein Loch: ``EPS_DRAG``
                # misst 0,05 mm und entspricht je nach Zoom einem Drittel
                # Pixel, ``CLICK_SLACK`` misst zwei Pixel. Dazwischen lag ein
                # Klick, der den Körper um Bruchteile verschob **und** die
                # Auswahl nicht wechselte (gemessen am 23.08.2026 an drei
                # Pixeln Wackeln, wie es beim Klicken normal ist).
                self._ready_to_drag = True
                return
            if scheme == "slicer":
                # Links wählt; geschoben wird mit Umschalt und Ziehen.
                if self._shift():
                    self.StartPan()
                    self._tell("panning")
                return
            if scheme == "blender" and self._shift():
                self.StartPan()
                self._tell("panning")
                return
            if on_rotate_start is not None:
                # Vor dem Start, nicht danach: Der Drehpunkt bekommt die
                # Tiefe der Körper, unsichtbar (§2.9, ``_aim_rotation``).
                on_rotate_start()
            self.StartRotate()
            self._tell("rotate")

        def _mouse_move(self, *_: Any) -> None:
            if self._painting:
                if on_paint is not None:
                    on_paint(*self._position(), False)
                return
            if self._ready_to_drag or self._dragging_body:
                now = self._position()
                if not self._dragging_body:
                    if is_click(self._left_at, now):
                        # Noch im Klickbereich — hier passiert nichts, damit
                        # ein Klick keinen Verlaufsschritt hinterlässt.
                        return
                    # **Von der Stelle des Drückens aus**, nicht von hier:
                    # Sonst spränge der Körper um die zurückgelegte Strecke.
                    if on_body_drag is None or not on_body_drag("start", *(self._left_at or now)):
                        self._ready_to_drag = False
                        return
                    self._dragging_body = True
                # **Ohne das ``return`` liefe die Kamera mit**: ``OnMouseMove``
                # unten führt sie weiter, und der Körper wanderte vor einer
                # Ansicht, die sich zugleich dreht.
                if on_body_drag is not None:
                    on_body_drag("move", *now)
                return
            # Der Beobachter verdrängt die eingebaute Verarbeitung — ohne
            # diesen Aufruf stünde die Kamera bei jedem Ziehen still.
            self.OnMouseMove()

        def _left_up(self, *_: Any) -> None:
            painted, self._painting = self._painting, False
            self.EndPan()
            self.EndRotate()
            self._tell(None)
            started, self._left_at = self._left_at, None
            dragged, self._dragging_body = self._dragging_body, False
            self._ready_to_drag = False
            if dragged and on_body_drag is not None:
                # Hier entsteht der Schritt im Verlauf (Regel 2). Ein Zug, der
                # gar nicht erst begonnen hat, kommt hier nicht an — er war ein
                # Klick, und der wählt gleich darunter aus.
                on_body_drag("end", *self._position())
            if painted:
                # Die Züge sind schon beim Drücken und Ziehen gesetzt — der
                # Klickpfad malte denselben Punkt ein zweites Mal.
                return
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
            apply_wheel_zoom(camera, factor)
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
            if on_camera is not None:
                on_camera()

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
            if on_rotate_start is not None:
                # Vor dem Start, nicht danach: Der Drehpunkt bekommt die
                # Tiefe der Körper, unsichtbar (§2.9, ``_aim_rotation``).
                on_rotate_start()
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
