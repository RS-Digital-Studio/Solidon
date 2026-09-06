"""Der Viewport (Bauplan §18, §2.9).

Kein Anzeigefenster, sondern das Prüfwerkzeug: Druckplatte und Bauraum in
echter Größe, Rückseiten eingefärbt, damit umgedrehte Normalen auffallen, und
drei Navigationsschemata, damit niemand seinen Slicer verlernen muss.

Die 3D-Ansicht braucht einen Renderer (pygfx über wgpu, gebaut in
``app.ui.render.factory``), und der braucht einen wgpu-Adapter
(``factory.available()``). Lässt sich das auf einer Maschine nicht starten,
öffnet das Fenster trotzdem und sagt es — alles außer der Ansicht läuft weiter.
"""

from __future__ import annotations

import math
import os
import weakref
from collections.abc import Callable, Sequence
from dataclasses import replace
from itertools import pairwise, product
from typing import Any, Final, Literal, NamedTuple

from PySide6.QtCore import QElapsedTimer, QEvent, QPoint, Qt, QTimer, Signal
from PySide6.QtGui import QFont, QFontMetricsF, QGuiApplication, QKeySequence
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
    SnapResult,
    angle_between,
    distance,
    snap,
    wall_thickness,
)
from app.core.geom.mesh import (
    distance_to_triangles,
    face_components,
    hull_planes,
    ray_span_in_hull,
)
from app.core.geom.mesh_ops import decimate
from app.core.geom.section import SectionPlane, cut, plane_patch
from app.core.geom.transform import (
    Axis,
    TransformSteps,
    along_normal,
    decompose_transform,
    rotation_about,
    snap_near,
    snap_to_step,
)
from app.core.log import get_logger
from app.core.perceive.features import CURVATURE_LIMIT
from app.core.perceive.maps import AnalysisMap
from app.core.scene import EvaluationResult
from app.core.scene.cancel import CancelSignal
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
from app.ui.labels import (
    display_unit,
    feature_label,
    feature_name,
    length,
    localised,
    read_number,
)
from app.ui.leash import Worker, WorkerLeash, stop_watching_the_dying, weak_slot
from app.ui.motion import ACCENT_MS, animations_enabled, mix, tween
from app.ui.palette import (
    DIFF_PALETTES,
    LAYER_WIDTHS,
    ROLES,
    VIRIDIS,
    DiffPalette,
    readable_on,
    text_colour,
)
from app.ui.render import shapes
from app.ui.render.api import (
    AxesMarkerStyle,
    Bounds,
    CameraPose,
    CellColours,
    Item,
    LabelsItem,
    LabelStyle,
    PointerEvent,
    Renderer,
    SurfaceStyle,
    hex_of,
)
from app.ui.render.edges import feature_edges
from app.ui.render.gizmo import ARROW_SHARE, Gizmo
from app.ui.render.navigator import NavigationScheme, Navigator, NavigatorCallbacks
from app.ui.scale_widget import ScaleHandle
from app.ui.style import ROOMY, TIGHT
from app.ui.theme import THEMES, slot_colour, viewport_colours

_log = get_logger(__name__)

#: Wie viel Kappenausschlag ein Bildpunkt senkrechter Mausbewegung bedeutet.
#:
#: ``camera_step`` erwartet Achsen zwischen -1 und 1 und rechnet sie mit
#: ``ORBIT_RATE`` mal der Zeitspanne. Der Wert hier ist so gewählt, dass eine
#: Bewegung über etwa die halbe Fensterhöhe (rund 400 Bildpunkte) eine
#: Vierteldrehung ergibt — dieselbe Empfindlichkeit, mit der der Drehteller
#: des Navigators dreht (``TURN_PER_PIXEL`` mal ``TURN_MOTION_FACTOR``, von
#: VTKs Trackball übernommen, den er am 05.09.2026 ersetzt hat).
TILT_PER_PIXEL: Final = 0.05
#: Die Zeitspanne, mit der ein einzelner Kippschritt gerechnet wird. Ein
#: Mausereignis hat keine Dauer; genommen wird deshalb ein fester Takt, damit
#: dieselbe Strecke immer denselben Winkel ergibt — unabhängig davon, wie viele
#: Ereignisse das System dafür schickt.
TILT_STEP_SECONDS: Final = 0.05

#: Was eine Flugtaste an den Achsen von ``Motion`` bewegt (§2.9).
#:
#: **Als Tabelle und nicht als Kette von ``if``**, aus demselben Grund wie bei
#: :data:`app.ui.render.navigator._NAVIGATION`: Der Text im Handbuch und das Verhalten sollen aus
#: derselben Quelle kommen, und eine Tabelle lässt sich ohne Fenster prüfen.
#:
#: ``y`` ist negativ für „vorwärts": Die Achse heißt bei der Kappe
#: „wegschieben ist positiv", und ``camera_step`` folgt dem in beiden
#: Auslegungen — beim Zoom wie beim Flug.
FLIGHT_KEYS: Final[dict[str, dict[str, float]]] = {
    "w": {"y": -1.0},
    "s": {"y": 1.0},
    "a": {"x": -1.0},
    "d": {"x": 1.0},
    "q": {"rx": 1.0},
    "e": {"rx": -1.0},
}
#: Takt des Fluges in Millisekunden — derselbe wie bei der 3D-Maus (~60 Hz).
#:
#: **Ein eigener Takt und nicht die Tastaturwiederholung.** Zuerst war ein
#: Anschlag ein Schritt: Qt liefert beim Halten die Wiederholung, und die
#: schien der Takt zu sein, den das System ohnehin hat. Nachgerechnet fliegt
#: das nicht, es springt — rund eine halbe Sekunde Stillstand (die
#: Wiederholverzögerung des Systems, die niemand hier einstellt), danach
#: 31 Schritte je Sekunde und damit das Viereinhalbfache der Entfernung je
#: Sekunde. Der Bauraum wäre in einer Fünftelsekunde durchflogen.
FLIGHT_TICK_MS: Final = 16
#: Wie weit der Flug je Sekunde trägt, gemessen in Entfernungen zum
#: Blickpunkt. Eins heißt: aus 300 mm Abstand 300 mm je Sekunde — der Bauraum
#: von Rand zu Rand in etwa einer Sekunde.
FLIGHT_RATE: Final = 1.0
DisplayMode = Literal["solid", "solid_edges", "wireframe", "transparent"]
"""How a body is drawn (§18.1)."""

Shading = Literal["flat", "smooth"]
Projection = Literal["perspective", "orthographic"]
"""Zum Messen ist die orthographische Ansicht Pflicht (§18.1)."""

#: Darstellungsarten (§18.1): Stil, Kanten, Deckkraft — gelesen in ``_apply_scene``.
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
#: Rand frei lassen — Werkzeugzeile und zweimal ihr Rand, 63 Punkte bei
#: jeder Fenstergröße (gemessen 06.09.2026), und darin muss die Anzeige
#: samt Abstand Platz haben: 60 und 2 sind das Höchstmaß. Wächst die
#: Werkzeugzeile, etwa weil jemand seine Systemschrift größer stellt,
#: schrumpft der Streifen; dann wird
#: ``test_the_axis_marker_does_not_hide_behind_a_card`` rot und sagt, um wie
#: viele Punkte. Das ist der Zweck dieses Tests. Größer als der Streifen
#: kann die Anzeige an dieser Stelle nicht werden; was in das Feld passt,
#: entscheidet die Achsenkamera des Renderers (``AXES_VIEW_SPAN``).
ORIENTATION_SIZE = 60
ORIENTATION_MARGIN = 2


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
    gerechnet: Hinter der Renderer-Wache läuft offscreen nichts, und ein Test
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

    Position, Blickpunkt und Oben — die drei Felder von
    :class:`~app.ui.render.api.CameraPose`, in dieser Reihenfolge. Die achte
    Kameravorgabe neben den
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

    Eine freie Funktion und keine Methode: Offscreen gibt es keinen Renderer,
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


def camera_in_free_area(
    pose: CameraPose,
    bounds: Bounds,
    size: tuple[float, float],
    margins: tuple[float, float, float],
    angle: float,
    scale: float | None,
) -> tuple[CameraPose, float | None]:
    """Rahmt acht Hüllquaderpunkte zwischen den Karten, ohne die Blickrichtung zu ändern.

    Größe und Ränder haben dieselbe Pixeleinheit. Perspektivisch wird jede
    Ecke gegen die vier freien Bildränder gerechnet: Ein bloßes Verschieben
    am Blickpunkt ließe nähere Ecken wieder unter eine Karte ragen.
    """
    import numpy as np

    width, height = size
    left, right, bottom = margins
    if width <= left + right or height <= bottom or not any(margins):
        return pose, scale
    direction = np.asarray(pose.focal_point) - np.asarray(pose.position)
    distance = float(np.linalg.norm(direction))
    if distance <= EPS_GEOM:
        return pose, scale
    direction /= distance
    across = np.cross(direction, pose.view_up)
    across_length = float(np.linalg.norm(across))
    if across_length <= EPS_GEOM:
        return pose, scale
    across /= across_length
    up = np.cross(across, direction)
    corners = np.asarray(list(product(bounds[:2], bounds[2:4], bounds[4:])), dtype=float)
    centre = np.mean(corners, axis=0)
    x, y, z = ((corners - centre) @ np.column_stack((across, up, direction))).T
    low_x, high_x = -1.0 + 2.0 * left / width, 1.0 - 2.0 * right / width
    low_y, high_y = -1.0 + 2.0 * bottom / height, 1.0
    middle_x, middle_y = (low_x + high_x) / 2.0, (low_y + high_y) / 2.0
    half_x, half_y = (high_x - low_x) / 2.0, (high_y - low_y) / 2.0
    aspect = width / height
    if scale is None:
        tangent_y = math.tan(math.radians(angle) / 2.0)
        tangent_x = tangent_y * aspect
        distance = max(
            distance,
            float(np.max((x / tangent_x - high_x * z) / half_x)),
            float(np.max((low_x * z - x / tangent_x) / half_x)),
            float(np.max((y / tangent_y - high_y * z) / half_y)),
            float(np.max((low_y * z - y / tangent_y) / half_y)),
        )
        half_height = distance * tangent_y
    else:
        scale = max(
            scale,
            float(np.max(np.abs(x))) / (aspect * half_x),
            float(np.max(np.abs(y))) / half_y,
        )
        half_height = scale
    focus = centre - across * middle_x * half_height * aspect - up * middle_y * half_height
    position = focus - direction * distance
    return CameraPose(tuple(position), tuple(focus), pose.view_up), scale


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

#: Wie weit ein Messklick von einer Ecke oder Kante entfernt sein darf, um
#: darauf gezogen zu werden — **in Bildpunkten**.
#:
#: Der Kern rechnet die Fangweite in Millimetern (zwei Prozent der Diagonale,
#: :data:`app.core.geom.measure.SNAP_RADIUS_RELATIVE`), und das ist die falsche
#: Einheit für eine Zielgeste: Gezielt wird mit der Maus, also in Bildpunkten.
#: An einem 200 mm langen Teil sind zwei Prozent vier Millimeter — herangezoomt
#: sind das zweihundert Bildpunkte, und der Fang reißt den Punkt quer über die
#: Fläche; herausgezoomt sind es zwei, und es gibt praktisch keinen Fang mehr.
#: Beides hat Robert am 03.09.2026 als „bei messen ist das zielen relativ
#: schwer" gemeldet. Sechzehn Bildpunkte bleiben bei jedem Zoom dieselbe Geste.
MEASURE_SNAP_PIXELS = 16.0

#: Wie lang die Arme der Fangmarke sind, je Fangart und **in Bildpunkten**.
#:
#: **Die Größe ist die Auskunft** (Regel 18): Das Kreuz an einer Ecke ist
#: deutlich größer als das an einer Kante, und eine freie Stelle bekommt nur
#: ein Kreuzchen. Ohne diesen Unterschied sähe jede Stelle gleich aus, und wer
#: eine Ecke treffen will, wüsste vor dem Klick nicht, ob er sie hat.
#:
#: In Bildpunkten und nicht in Millimetern, aus demselben Grund wie die
#: Fangweite darüber — eine Marke, die beim Hineinzoomen quer über das Teil
#: wächst, ist keine Marke mehr. Am gerenderten Fenster gemessen: Weltmaß
#: entlang der Achsen war in der isometrischen Ansicht auf ein Drittel
#: verkürzt und im Bild kaum zu finden.
SNAP_MARK_PIXELS = {"vertex": 13.0, "edge": 9.0, "free": 5.0}

#: Wie dick der Punkt in der Mitte der Marke ist, je Fangart.
#:
#: Das Kreuz sagt „hier", der Punkt sagt „genau hier" — ohne ihn zeigt die
#: Marke auf ihren eigenen Schnittpunkt, und den muss das Auge erst bilden.
SNAP_DOT_PIXELS = {"vertex": 9.0, "edge": 7.0, "free": 5.0}


def snap_sentence(kind: str) -> str:
    """Was die Fangmarke bedeutet, in einem Satz.

    Er steht in der Beschreibung der Ansicht, nicht in der Szene: Ein
    übersetzter Text am Renderer stünde in sechs Sprachen an einer Stelle, die
    keine Prüfung sieht (unter VTK, bis 05.09.2026, ging er dort gar nicht —
    die Beschriftung nahm nur ASCII an, und „Fläche" hat ein ä). Qt nimmt jede
    Sprache, und ein Bildschirmleser liest die Beschreibung vor — damit trägt
    die Auskunft neben der Größe eine zweite Kodierung, die ohne Augen
    auskommt.
    """
    if kind == "vertex":
        return tr("Der Messpunkt rastet auf einer Ecke ein.")
    if kind == "edge":
        return tr("Der Messpunkt rastet auf einer Kante ein.")
    return tr("Der Messpunkt sitzt frei auf der Fläche.")


def rgb_of(colour: str) -> tuple[float, float, float]:
    """Eine Farbe der Palette als drei Zahlen von 0 bis 1.

    Die Palette führt Hex-Zeichenketten (``#f0a54a``), weil das Stylesheet sie
    so braucht. Zum **Mischen** taugen sie nicht: `motion.mix` rechnet, und
    zwischen zwei Zeichenketten gibt es keine Mitte. Der Renderer-Vertrag nimmt
    nur Hexwerte; ``hex_of`` bringt das Gemischte zurück, also kostet die
    Umrechnung nichts außer diesem Paar.
    """
    from PySide6.QtGui import QColor

    value = QColor(colour)
    return (value.redF(), value.greenF(), value.blueF())


def turn_arc(origin: Any, axis: Any, radius: float, angle: float, *, steps: int = 32) -> Any:
    """Die Punkte eines Bogens von 0 bis ``angle`` um ``axis``, im Uhrzeigersinn.

    **Der 45°-Magnet rastet, und niemand sieht es.** Beim Drehen springt die
    Zahl am Zeiger von 40,5 auf 45,0 und bleibt dort, während man weiterzieht
    (gemessen: dreiundzwanzig Schritte lang) — aber im Bild geschieht nichts,
    was das erklärt. Ein Bogen, der vom Ausgangswinkel bis zum aktuellen
    wächst, macht die Drehung sichtbar und das Einrasten dazu.

    Als freie Funktion und ohne Qt, aus demselben Grund wie
    :func:`shadow_points`: Was hinter der Renderer-Wache steht, prüft offscreen
    niemand mehr. Hier ist es reine Rechnung, also ist es hier prüfbar.

    Zurück kommen die Punkte **paarweise** für ``add_lines`` — jeder innere
    doppelt, so wie es die Schichtkonturen schon tun.
    """
    import numpy as np

    centre = np.asarray(origin, dtype=float)
    direction = np.asarray(axis, dtype=float)
    norm = float(np.linalg.norm(direction))
    if norm <= EPS_GEOM or abs(angle) <= EPS_DISPLAY or radius <= EPS_GEOM:
        return None
    direction = direction / norm
    # Zwei Achsen quer zur Drehachse: die erste beliebig, solange sie nicht
    # parallel liegt — sonst wäre das Kreuzprodukt null und der Bogen leer.
    helper = np.array([1.0, 0.0, 0.0]) if abs(direction[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    first = np.cross(direction, helper)
    first = first / float(np.linalg.norm(first))
    second = np.cross(direction, first)
    turns = np.radians(np.linspace(0.0, float(angle), max(int(steps), 2)))
    points = centre + radius * (np.outer(np.cos(turns), first) + np.outer(np.sin(turns), second))
    return np.repeat(points, 2, axis=0)[1:-1]


def gizmo_sentence(feature: Feature | None) -> str:
    """Was der Griff bewegen wird, in einem Satz.

    Der Griff sagte es nicht. Wer eine Bohrung anklickte und ihn einschaltete,
    sah drei Achsen in der Mitte des Teils — und die Anwendung schwieg dazu,
    ob nun die Bohrung oder der Körper gemeint ist. Bei einer Fläche steht der
    Griff sichtbar darauf; bei allem anderen war der Ort die einzige Auskunft,
    und er lag bis zu 28 mm neben dem, was gewählt war.

    **Abgeleitet und nicht behauptet:** Der Satz liest, woran der Griff
    tatsächlich hängt (:meth:`Viewport.gizmo_feature`). Erweitert jemand
    ``move_feature`` um eine Art, sagt er es von selbst — ein Satz, der die
    Grenze aufzählt, wäre am selben Tag falsch (dieselbe Falle wie bei den
    Texten, die eine Abwesenheit versprechen).
    """
    if feature is None:
        return tr("Der Griff bewegt das ganze Teil.")
    if feature.kind == "face":
        return tr("Der Griff versetzt die gewählte Fläche entlang ihrer Normalen.")
    return tr("Der Griff bewegt das gewählte Merkmal, nicht das ganze Teil.")


#: Wie weit der Ziehgriff höchstens gestreckt wird, wenn der Blick flach steht.
#:
#: Er zeigt entlang der Ebenennormalen und erscheint deshalb um den Sinus des
#: Kippwinkels verkürzt. Damit er im Bild seine Länge behält, wird er im Raum
#: gestreckt — und das wächst gegen unendlich, je flacher der Blick steht.
#:
#: **Sechs, und die Zahl kommt aus dem Einrasten:** Unter zehn Grad rastet die
#: Kamera auf die nächste Hauptansicht (``_settle_sketch_view``), dort gibt es
#: also keinen Griff mehr zu strecken. Bei genau zehn Grad ist der nötige
#: Faktor ``1/sin(10°) = 5,76``; sechs liegt knapp darüber, damit die Grenze
#: jenseits des Einrastens greift und nicht davor.
PULL_HANDLE_STRETCH = 6.0

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


#: Die sechs Achsenansichten, auf die eine freie Kamera einrastet.
#:
#: **Ohne ``iso``**, und das ist der Unterschied zur Werkzeugleiste: Die
#: schräge Ansicht liegt mitten im Drehraum, und wer ein Modell dreht, käme
#: dort ständig vorbei. Eine Achsenansicht dagegen ist ein Ziel — man will
#: genau dorthin, und die letzten Grad von Hand zu treffen ist Zielen ohne
#: Gewinn.
AXIS_VIEW_DIRECTIONS: dict[str, tuple[Vec3, Vec3]] = {
    name: VIEW_DIRECTIONS[name] for name in ("front", "back", "left", "right", "top", "bottom")
}


def _nearest_view(
    directions: dict[str, tuple[Vec3, Vec3]],
    position: Sequence[float],
    focus: Sequence[float],
    threshold_degrees: float,
) -> str | None:
    """Der Name der nächsten Ansicht aus ``directions``, sonst ``None``.

    Verglichen wird die **Blickrichtung**, nicht der Ort der Kamera. Dadurch
    bleibt Schieben ohne Einfluss, und nur das Kippen entscheidet.
    """
    direction = tuple(float(position[axis]) - float(focus[axis]) for axis in range(3))
    length = math.sqrt(sum(value * value for value in direction))
    if length <= EPS_GEOM:
        return None
    unit = tuple(value / length for value in direction)
    best_name = None
    best_dot = -1.0
    for name, (wanted, _up) in directions.items():
        score = sum(unit[axis] * wanted[axis] for axis in range(3))
        if score > best_dot:
            best_name, best_dot = name, score
    limit = math.cos(math.radians(max(0.0, threshold_degrees)))
    return best_name if best_dot >= limit else None


def sketch_view_near(
    position: Sequence[float],
    focus: Sequence[float],
    threshold_degrees: float = 10.0,
) -> str | None:
    """Nahe Zeichenebene der Kamera, sonst ``None`` für eine freie Ansicht.

    Nur die drei Ebenen, auf denen gezeichnet wird: Die Rückseiten rasten
    absichtlich nicht auf eine andersherum benannte Vorder-, Seiten- oder
    Draufsicht ein — die Skizze läge dann gespiegelt zu ihrem Namen.
    """
    return _nearest_view(SKETCH_VIEW_DIRECTIONS, position, focus, threshold_degrees)


def axis_view_near(
    position: Sequence[float],
    focus: Sequence[float],
    threshold_degrees: float = 10.0,
) -> str | None:
    """Nahe Achsenansicht der Kamera, sonst ``None`` für eine freie Ansicht.

    **Das Gegenstück zu :func:`sketch_view_near` für das Modell.** Dort geht
    es um die drei Ebenen, auf denen gezeichnet wird, und eine Rückseite wäre
    eine falsch benannte Ebene. Hier geht es um den Blick, und von hinten
    zuzusehen ist so gut wie von vorn — deshalb alle sechs.
    """
    return _nearest_view(AXIS_VIEW_DIRECTIONS, position, focus, threshold_degrees)


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
    :func:`bed_scale`: Offscreen gibt es keinen Renderer, und was hinter dieser
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


def hatch_lines(
    corners: Any, normal: Vec3, spacing: float, limit: int = 40
) -> list[tuple[Vec3, Vec3]]:
    """Parallele Striche über einer Dreiecksfläche — zweite Kodierung nach Regel 18.

    Eine geschützte Sichtfläche trägt eine Tönung. Tönung allein ist Farbe, und
    Farbe allein trägt keine Bedeutung: Wer sie nicht unterscheiden kann, sieht
    eine Fläche wie jede andere. Die Striche sind das zweite Merkmal, und sie
    sind Geometrie wie das Kreuz in :func:`cross_marks` und der Pfeil in
    :func:`pull_handle` — keine Textur, die beim Drehen mitwandert.

    ``corners`` sind die Eckpunkte je Dreieck (drei Zeilen je Dreieck), wie der
    Merkmals-Patch sie ohnehin baut. Geschnitten wird mit einer Schar von
    Ebenen quer zur Fläche; zurück kommen die Segmente, die dabei in den
    Dreiecken liegen.

    **Die Schnittrichtung kommt aus der Normalen und nicht aus einer Achse.**
    Eine Fläche, die in der xy-Ebene liegt, hat mit z-Schnitten keinen
    Schnittpunkt — sie läge in der Ebene. Gewählt wird deshalb die Achse, zu
    der die Normale am wenigsten zeigt; das Kreuzprodukt daraus liegt sicher
    in der Fläche.

    ``limit`` deckelt die Zahl der Striche. Eine große Fläche mit engem Abstand
    ergäbe sonst tausende Segmente, und die kosten beim Drehen mehr, als sie
    dem Auge sagen.
    """
    import numpy as np

    points = np.asarray(corners, dtype=float)
    if len(points) < 3 or spacing <= 0.0:
        return []
    up = np.asarray(normal, dtype=float)
    length = float(np.linalg.norm(up))
    if length <= EPS_GEOM:
        return []
    up = up / length
    # Die Achse, zu der die Normale am wenigsten zeigt: ihr Kreuzprodukt mit
    # der Normalen ist am längsten und damit am stabilsten.
    axis = np.zeros(3)
    axis[int(np.argmin(np.abs(up)))] = 1.0
    across = np.cross(up, axis)
    across /= np.linalg.norm(across)

    reach = points @ across
    low, high = float(reach.min()), float(reach.max())
    if high - low <= spacing:
        return []
    steps = np.arange(low + spacing, high, spacing)
    if len(steps) > limit:
        steps = np.linspace(low + spacing, high - spacing / 2.0, limit)

    triangles = points.reshape(-1, 3, 3)
    away = reach.reshape(-1, 3)
    segments: list[tuple[Vec3, Vec3]] = []
    for level in steps:
        side = away - level
        # Ein Dreieck trägt ein Segment, wenn seine Ecken nicht alle auf
        # derselben Seite liegen.
        touched = (side.min(axis=1) < 0.0) & (side.max(axis=1) > 0.0)
        for triangle, offsets in zip(triangles[touched], side[touched], strict=True):
            crossing = []
            for first, second in ((0, 1), (1, 2), (2, 0)):
                one, other = offsets[first], offsets[second]
                if (one < 0.0) == (other < 0.0):
                    continue
                share = one / (one - other)
                crossing.append(triangle[first] + share * (triangle[second] - triangle[first]))
            if len(crossing) == 2:
                start, end = crossing
                segments.append(
                    (
                        (float(start[0]), float(start[1]), float(start[2])),
                        (float(end[0]), float(end[1]), float(end[2])),
                    )
                )
    return segments


def pull_handle(
    frame: PlaneFrame,
    curves: Sequence[SketchCurve],
    size: float,
    across: float | None = None,
) -> list[tuple[tuple[float, float, float], tuple[float, float, float]]]:
    """Pfeil nach außen und Kreuz nach innen am längsten Profilrand.

    Der Fuß sitzt auf dem greifbaren Umriss. Pfeil und Kreuz sind die zweite
    Kodierung neben der Richtung (Regel 18): nach außen entsteht Material,
    nach innen wird es entfernt.

    **Zwei Größen, weil zwei Richtungen verschieden verkürzt werden.** ``size``
    misst entlang der Normalen — dorthin zeigt der Schaft, und genau die
    Richtung schrumpft im Bild, je flacher der Blick auf die Ebene steht.
    ``across`` misst die Querstücke: Pfeilflügel und Kreuz liegen **in** der
    Ebene und werden dort nicht verkürzt.

    Ohne diese Trennung ging das Strecken schief, und zwar sichtbar: Wer den
    Schaft bei zehn Grad Kippung um das Sechsfache streckt, damit er im Bild
    seine Länge behält, bläst Flügel und Kreuz mit auf — gemessen am
    30.08.2026 eine Griffspanne von 156 statt 69 Bildpunkten. Aus einem Griff,
    den man nicht findet, wurde einer, der das Profil verdeckt.

    ``across`` ohne Wert heißt ``size`` — dann verhält sich die Funktion wie
    vorher, und in der Seitenansicht sind beide ohnehin gleich.
    """
    across = size if across is None else across
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
    arrow_a = shifted(neck, frame.x_axis, across * 0.24)
    arrow_b = shifted(neck, frame.x_axis, -across * 0.24)
    cross_a = shifted(inward, frame.x_axis, across * 0.18)
    cross_b = shifted(inward, frame.x_axis, -across * 0.18)
    cross_c = shifted(inward, frame.y_axis, across * 0.18)
    cross_d = shifted(inward, frame.y_axis, -across * 0.18)
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
    offscreen nicht läuft: Was hinter dem Renderer liegt, prüft in der Suite
    niemand mehr (§35).
    """
    if step > 0.0:
        reach = round(reach / step) * step
    if abs(reach) <= EPS_GEOM:
        # **Ein auf null gefangener Zug ist kein Zug.** Bis zum 02.09.2026
        # hob die Klemmung ihn auf die Untergrenze — und weil ``round(-0.3)``
        # ``-0.0`` ist und ``-0.0 < 0.0`` nicht gilt, wurde aus einem kurzen
        # Zug nach unten ein Aufbau von 0,1 mm nach oben.
        return 0.0
    least, most = limits
    if most > least:
        return math.copysign(min(max(abs(reach), least), most), reach)
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


def orientation_corner(width: int, height: int) -> tuple[float, float, float, float]:
    """Wo die Achsenanzeige sitzt, für ein Fenster dieser Größe.

    Unten links, in dem Streifen, den die linke Spalte über dem unteren Rand
    frei lässt. Die Werkzeugzeile beginnt weiter rechts, also bleibt die Ecke
    selbst frei — bei eingeklappten Karten erst recht.

    Der Renderer erwartet Anteile von 0 bis 1, mit dem Ursprung unten links.
    Bei einem Fenster, das kleiner ist als die Anzeige, bleibt sie am Rand
    kleben statt hinauszulaufen.
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
#: nicht auf einem eigenen Feld — schwarz (die Vorgabe des Renderers, den
#: Solidon bis 06.09.2026 hatte) ist im dunklen Thema unlesbar, und weiß
#: wäre es im hellen.
AXIS_LABEL_DARK = "#e9e6e1"
AXIS_LABEL_LIGHT = "#2b2a28"

#: Wie hell das Frontlicht des Viewports je Thema brennt.
#:
#: Der Renderer stellt fünf Lichter auf (``LIGHT_KIT`` in ``gfx_renderer.py``
#: — der Lichtsatz, den VTKs ``vtkLightKit`` aufstellte): ein *Headlight* aus
#: der Kamerarichtung und vier Kameralichter (Haupt-, Füll- und zwei
#: Gegenlichter). Das Headlight ist das einzige, das die zum Betrachter
#: zeigenden Seitenwände trifft — die Kameralichter stehen über und hinter dem
#: Teil und lassen senkrechte Flächen fast schwarz.
#:
#: **Warum das vom Thema abhängt.** Der Körper ist im hellen Thema ``#78828e``
#: und im dunklen ``#b9c4d0``: 0,217 gegen 0,532 Luminanz, also **2,45-mal
#: dunkler**. Schattierung multipliziert, und deshalb sind auf ihm auch alle
#: Helligkeitsunterschiede 2,45-mal kleiner — gemessen am 30.08.2026 zwischen
#: den zwei sichtbaren Außenwänden der Beispieldose: 0,0155 im hellen gegen
#: 0,0380 im dunklen Thema. Das ist kein Fehler, sondern Multiplikation, und
#: genau deshalb hilft dort nur mehr Licht.
#:
#: Gemessen wurde die ganze Reihe, an denselben Stellen desselben Bildes:
#:
#: | Frontlicht | Wand links | Wand rechts | Unterschied | Körper/Platte |
#: |---|---|---|---|---|
#: | 0,00 | 0,0129 | 0,0228 | 0,0099 | 8,62 |
#: | 0,25 (vorher) | 0,0302 | 0,0457 | 0,0155 | 7,97 |
#: | 0,35 | 0,0388 | 0,0569 | 0,0181 | 7,59 |
#: | 0,45 | 0,0490 | 0,0708 | 0,0218 | 7,29 |
#: | 0,50 | 0,0553 | 0,0768 | 0,0215 | 7,05 |
#:
#: Bei 0,45 ist der Unterschied am größten; darüber wächst nur noch die
#: Grundhelligkeit, und der Körper rückt der Platte näher.
#:
#: **Zwei Wege, die vorher gemessen und verworfen wurden**, damit sie niemand
#: erneut geht: Ein ambienter Anteil am Körper (0,10 bis 0,35) hebt alle
#: Flächen gleich und macht ihn dabei *flacher* — der Wandunterschied fiel von
#: 1,19 auf 1,12, die Abhebung von der Platte von 8,41 auf 5,75. Ein
#: Glanzanteil (0,08 bis 0,25) ändert an den Wänden fast nichts und am Deckel
#: gar nichts; er sitzt an Stellen, an denen dieser Körper keine hat.
#:
#: Das dunkle Thema bleibt bei der Vorgabe des Lichtsatzes (0,25, ein Drittel
#: des Schlüssellichts — ``DEFAULT_HEADLIGHT`` in ``gfx_renderer.py``): Dort
#: ist der Körper hell, die Wände trennen sich deutlich, und mehr Licht ließe
#: ihn nur überstrahlen.
HEADLIGHT = {"light": 0.45, "dark": 0.25}

#: Wie lange die Marke eines angeklickten Befunds stehen bleibt.
#:
#: Lang genug, um sie zu finden, nachdem die Kamera geflogen ist; kurz genug,
#: dass sie nicht zur zweiten Auswahl wird. Sie ist eine **Antwort auf einen
#: Klick** und kein Zustand — was ausgewählt ist, sagen Auswahlfarbe,
#: Objektbaum und Statuszeile, und eine dauerhafte zweite Marke daneben wäre
#: eine zweite Wahrheit.
FINDING_MARK_MS = 2600

#: Wie groß der Ring im Bild ist, als Anteil der sichtbaren Höhe.
#:
#: Am Bild bemessen und nicht am Modell: Eine Marke soll auf jedem Teil gleich
#: groß aussehen, und ein fester Weltradius wäre an einem 200-mm-Gehäuse ein
#: Punkt und an einer M3-Bohrung ein Reifen.
FINDING_RING_SHARE = 0.09

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
#: Ein Tausendstel — die Vorgabe des Zell-Pickers unter VTK, bis 06.09.2026 —
#: wäre bei einem Fenster von 1300 Pixeln knapp zwei Pixel, und ein Klick auf
#: eine Kante trifft dann wieder nichts. Der Wert geht an ``pick_surface``
#: ausdrücklich mit; er hängt an keiner Vorgabe des Renderers.
#: Fünf Tausendstel sind rund acht Pixel: genug, um eine dünne Wand zu
#: Ab wann ein Zug am Körper ein Zug ist und kein Klick, in Millimetern.
#:
#: Ohne diese Grenze bekäme jede Auswahl einen Schritt im Verlauf mit null
#: Millimetern Versatz — Einträge, die nichts getan haben, und die dem
#: Rückgängig seinen Sinn nehmen.
EPS_DRAG = 0.05

#: erwischen, zu wenig, um die falsche Fläche zu greifen.
PICK_TOLERANCE = 0.005

#: Die Farbe, in der die Kandidaten einer mehrdeutigen Frage liegen (§21.3).
#:
#: **Nicht die Auswahlfarbe.** Was hier leuchtet, ist keine Auswahl, sondern
#: eine Frage: „Welches dieser drei Löcher meinst du?" Wer die Auswahlfarbe
#: nähme, sagte dreimal „das hier ist gewählt", und der Kunde suchte den
#: Unterschied. ``info`` ist die Rolle, die auf eine Auskunft zeigt.
CANDIDATE_COLOUR = ROLES["info"]

#: Wie durchscheinend ein Kandidat ist, und wie der betonte.
#:
#: Der Unterschied trägt die Auskunft „diese Zeile im Dialog gehört zu diesem
#: Loch" — zusammen mit der Kennung, die an jedem Kandidaten steht. Farbe
#: allein täte es nicht (Regel 18), und beide sind ohnehin dieselbe.
CANDIDATE_OPACITY = 0.45
EMPHASIS_OPACITY = 0.95

#: Bei welchen Winkeln der Drehgriff kurz einrastet, und wie nah man dafür
#: herankommen muss — beides in Grad.
#:
#: **Frei drehen und trotzdem 45 Grad treffen** (Robert, 03.09.2026: „freies
#: drehen, aber kurzes einrasten bei allen 45 grad winkeln außer man dreht
#: weiter"). Ein Raster, das immer greift, macht aus einer Drehung eine
#: Auswahl aus acht Möglichkeiten; gar kein Raster heißt, dass niemand genau
#: 45 Grad trifft. Der Magnet hat beides: In der Zone gilt das Vielfache, der
#: Körper bleibt einen Moment stehen, und wer weiterzieht, kommt heraus.
#:
#: Vier Grad sind knapp ein Zehntel des Weges zwischen zwei Rasten — weit
#: genug, dass man hineinfällt, ohne die Geste dazwischen zu bremsen.
TURN_MAGNET_STEP = 45.0
TURN_MAGNET_ZONE = 4.0

#: Was eine Bedeutung trägt, kommt aus ``palette.ROLES`` — dort steht die
#: Auswahlfarbe einmal, und der Objektbaum färbt in derselben. Vorher standen
#: hier neun eigene Werte, die kein Thema kannten und keine andere Stelle.
OBJECT_COLOUR = "#b9c4d0"
SELECTED_COLOUR = ROLES["select"]
BACKFACE_COLOUR = ROLES["backface"]
PROTECTED_COLOUR = ROLES["protected"]

#: Wie durchscheinend eine gesperrte Sichtfläche liegt. Deutlich genug, um
#: sie zu sehen, blass genug, dass die Form darunter erkennbar bleibt — sie
#: ist eine Notiz am Werkstück und nicht die Hauptsache.
PROTECTED_OPACITY = 0.32

#: Abstand der Schraffurstriche, als Anteil der Szenengröße. Bei einem
#: 200-mm-Teil sind das fünf Millimeter: nah genug, dass eine kleine Fläche
#: noch Striche trägt, weit genug, dass eine große nicht zugedeckt wird.
PROTECTED_HATCH_SPACING = 0.025

#: Die Striche sind heller als die Tönung, sonst verschwinden sie darin.
PROTECTED_HATCH_COLOUR = "#d6f0ea"
PROTECTED_HATCH_WIDTH = 2
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
#: Wie deckend der Kontaktschatten je Thema liegt.
#:
#: **Dieselbe Deckkraft ist auf hellem Grund viel lauter.** Der Schatten legt
#: :data:`SHADOW_COLOUR` über die Plattenfläche; wie stark das wirkt, hängt
#: davon ab, wie weit nach unten es von dort überhaupt noch geht. Gemessen am
#: 30.08.2026 bei 0,18 in beiden Themen:
#:
#: | | Schatten | Grund | Kontrast |
#: |---|---|---|---|
#: | hell | 0,4094 | 0,6106 | **1,44** |
#: | dunkel | 0,0183 | 0,0219 | **1,05** |
#:
#: Der Unterschied im hellen Thema war damit das Vierundfünfzigfache des
#: dunklen (0,2012 gegen 0,0037 Luminanz). Verschärft hat es die
#: B35-Aufhellung der Plattenfläche: Je heller der Grund, desto weiter der Weg
#: nach unten.
#:
#: **„Der Schatten wie im dunklen Thema reicht"** (Robert, 30.08.2026). Der
#: Zielwert ist also der Kontrast des dunklen Themas, und gemessen trifft ihn
#: 0,03:
#:
#: | Deckkraft | 0,18 | 0,08 | 0,05 | 0,04 | 0,03 |
#: |---|---|---|---|---|---|
#: | Kontrast | 1,44 | 1,17 | 1,10 | 1,08 | **1,06** |
#:
#: Die 0,18 des dunklen Themas bleiben unangetastet — dort ist der Wert seit
#: Roberts Entscheid vom 25.08.2026 bewusst leise, und gemessen ist er genau
#: so laut, wie er sein soll.
SHADOW_OPACITY = {"light": 0.03, "dark": 0.18}

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
#: Der eigentliche Grund liegt tiefer: Das Frontlicht des Renderers hängt an
#: der Kamera.
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

#: Wie deckend die Bettfläche ist, solange ein Körper **unter** ihr liegt.
#:
#: **Ein Teil unter der Platte war unsichtbar, und zwar vollständig.** Gemessen
#: am laufenden Fenster, ein Quader von 40 auf 40 auf 30 mm, 35 mm unter Z=0,
#: von schräg oben gezählt: **1** Bildpunkt von 263 583. Ohne die Fläche wären
#: es alle.
#: Wer sein Modell versenkt oder falsch positioniert hat, sah davon nichts und
#: merkte es beim Slicen (Robert, 03.09.2026: „dass man die Modelle auch unter
#: dem Bett durchsehen sollte").
#:
#: Die Reihe dazu, dieselbe Lage bei fallender Deckkraft:
#:
#: | Deckkraft | sichtbar |
#: |---|---|
#: | 1,00 | 1 Bildpunkt |
#: | 0,80 | 81 675 |
#: | 0,60 | 258 370 |
#: | 0,45 | 262 077 |
#: | 0,30 | 263 773 |
#:
#: Bei 0,45 ist praktisch alles da, und es ist derselbe Wert, den der
#: Darstellungsmodus *Transparent* schon führt — eine Zahl statt zweier.
#:
#: **Nur wenn wirklich etwas darunter liegt** (Robert, ausdrücklich): Sonst
#: bliebe die Frage, was die Durchsicht den Kontaktschatten kostet, und die
#: stellt sich bei einer Platte, unter der nichts ist, gar nicht.
BED_SUNKEN_OPACITY = 0.45


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
    gibt es keinen Renderer, und die Rechnung ist das, was ein Test prüfen kann.
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


#: Schalter für Maschinen und Testläufe ohne brauchbaren Grafikkontext.
HEADLESS_VARIABLE = f"{ENVIRONMENT_PREFIX}_NO_VIEWPORT"


def _available() -> bool:
    """Ob sich hier eine 3D-Ansicht bauen lässt.

    Der Renderer braucht eine echte Grafikfläche und einen wgpu-Adapter; auf
    der Offscreen-Qt-Plattform gibt es die erste nicht, und ein Renderer ohne
    Adapter scheitert nicht höflich, sondern nähme den Prozess mit. Also
    passiert die Prüfung davor und nicht in einem except-Zweig.

    Die Plattform wird beim Aufbau der ``QGuiApplication`` festgelegt. Ein
    späterer Werkzeugaufruf kann die Umgebungsvariable entfernen, ändert Qt
    damit aber nicht mehr. Die wirksame Plattform gewinnt deshalb; nur vor dem
    Anwendungsaufbau bleibt die Variable der Rückfall.
    """
    if os.environ.get(HEADLESS_VARIABLE):
        return False
    platform = _effective_platform().casefold()
    if platform in ("offscreen", "minimal", "vnc"):
        return False
    # Wayland: Der Fensterweg des Renderers ist nur unter X11 und Xwayland
    # geprüft (mit VTK starb Wayland nativ — Martin Donecker, 28.08.2026;
    # den nativen Wayland-Weg von rendercanvas hat noch niemand gefahren,
    # Registerpunkt in ``ROADMAP.md``). Bis hierher kommt Wayland nur, wenn
    # Xwayland fehlt oder jemand es mit ``-platform`` erzwungen hat; sonst
    # hat ``app.ui.qt_platform`` vor dem Anwendungsaufbau X11 gewählt.
    # :func:`unavailable_hint` sagt, was fehlt.
    if platform.startswith("wayland"):
        return False
    from app.ui.render import factory

    return factory.available()


def _effective_platform() -> str:
    """Die Qt-Plattform, die wirklich läuft — vor dem Anwendungsaufbau die
    Umgebungsvariable als Rückfall (siehe :func:`_available`)."""
    return QGuiApplication.platformName() or os.environ.get("QT_QPA_PLATFORM", "")


def unavailable_hint() -> str:
    """Was der Nutzer tun kann, wenn es hier keine 3D-Ansicht gibt — leer, wo
    es nichts zu tun gibt (§2.7: kein Fehler ohne Handlungsvorschlag).

    Auf Wayland ist die Lage benennbar. Mit ``DISPLAY`` hat die Anwendung X11
    selbst an die erste Stelle gesetzt (``app.ui.qt_platform``); läuft sie
    trotzdem auf Wayland, ließ sich Qts X11-Plugin nicht laden — und das
    heißt fast immer: eine der neun Systembibliotheken fehlt, die das
    Linux-Paket nicht mitbringt, allen voran ``libxcb-cursor0`` (Qt warnt seit
    6.5 ausdrücklich davor). Ohne ``DISPLAY`` fehlt Xwayland selbst.
    """
    if _effective_platform().casefold().startswith("wayland"):
        if os.environ.get("DISPLAY", "").strip():
            return tr(
                "Die 3D-Ansicht braucht Qts X11-Anbindung, und die ließ sich nicht laden — "
                "meist fehlt die Systembibliothek libxcb-cursor0 (Paketverwaltung: "
                "„libxcb-cursor0“ oder „xcb-util-cursor“). Installieren Sie sie und starten "
                "Sie das Programm neu; wurde es mit „-platform wayland“ gestartet, lassen "
                "Sie das weg."
            )
        return tr(
            "Die 3D-Ansicht braucht ein X11-Fenster, und diese Sitzung bietet keines: "
            "Xwayland fehlt, oder das Programm wurde mit „-platform wayland“ gestartet. "
            "Schalten Sie Xwayland in Ihrer Arbeitsumgebung ein oder melden Sie sich in "
            "einer X11-Sitzung an; X11 wird dann von selbst gewählt."
        )
    return ""


def _hex(colour: tuple[float, float, float]) -> str:
    """Eine Slotfarbe (0 bis 1 je Kanal, §20) als Hexwert für den Renderer."""
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


def _is_opening_feature(feature: Feature) -> bool:
    """Nur Bohrung, Senkung oder Innengewinde bezeichnen eine axiale Öffnung."""
    return (
        feature.kind == "hole"
        or (feature.kind == "cone" and feature.params.get("recess") is True)
        or (feature.kind == "thread" and feature.params.get("internal") is True)
    )


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
    :func:`is_click`: eine Rechnung über Vektoren soll ohne Renderer prüfbar
    sein.
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

#: Der Schlüssel des Anzeigecaches: Kennung, Dreieckszahl **und** Inhalt.
#: Kennung und Dreieckszahl allein blieben beim Skalieren und Verschieben
#: gleich — und ein anderes Projekt trägt dieselben Kennungen: Eine Icosphere
#: mit 1,3 Millionen Dreiecken zeigte nach dem Skalieren von 20 auf 40 mm
#: weiter 20 mm, aus beiden Zugriffen dasselbe Cacheobjekt (Gesamtreview
#: 05.09.2026, UI-02). Der Objekthash der Auswertung ist die Geometrie.
DisplayKey = tuple[ObjectId, int, str]


def _display_key(object_id: ObjectId, mesh: Any, identity: str) -> DisplayKey:
    """Wonach ein dezimiertes Anzeigenetz abgelegt wird."""
    return (object_id, mesh.triangle_count, identity)


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

    Vom Betrachter weg und ein Stück nach rechts. Das Frontlicht des Renderers
    hängt an der Kamera — ein Körper ist also in jeder Ansicht von vorn
    beleuchtet, und ein Schatten, der das nicht mitmacht, sieht in jeder
    Ansicht falsch aus. Er macht es jetzt mit.

    Steht die Kamera senkrecht darüber, gibt es kein Hinten. Dann fällt der
    Schatten nach hinten rechts, denn eine Draufsicht hat eine Oberkante, und
    die ist dort, wo bei jeder anderen Ansicht das Hinten liegt.

    Als eigene Funktion, damit die Rechnung ohne Renderer prüfbar bleibt.
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

    Als eigene Funktion, damit die Regel ohne Renderer prüfbar bleibt —
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

    Als eigene Funktion, damit die Rechnung ohne Renderer prüfbar bleibt.
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
    """Die Grenzen um ihre Mitte geweitet — ein Sechsertupel wie ``Bounds`` im Vertrag.

    Das Format ist das des Renderer-Vertrags: (xmin, xmax, ymin, ymax, zmin,
    zmax). Als eigene Funktion, aus demselben Grund wie :func:`bed_scale`: offscreen
    gibt es keinen Renderer, und was nur im Zeichnen steht, prüft niemand.

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
    """Die Raumdiagonale eines Hüllquaders (xmin, xmax, ymin, ymax, zmin, zmax)."""
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
    gibt es keinen Renderer, und was nur im Zeichnen steht, prüft niemand.
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
    keinen Renderer, und eine Prüfung, die sich dort überspringt, prüft nie
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
        der Bezug, an dem eine Skala anfängt (und unter VTK, bis 06.09.2026,
        stolperte der Renderer über eine leere Beschriftungsliste).
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

#: Länge der Gizmo-Pfeile als Anteil der Diagonale **dessen, woran der Griff
#: hängt**, und die Dicke ihrer Schäfte im selben Maß. Die Vorgaben von
#: PyVistas Widget (0.15 und 0.02) ergaben auf einem 80-mm-Teil ein Gebilde aus dünnen Linien
#: von etwa vierzig Bildpunkten — zu klein, um es mit der Maus zu treffen.
#:
#: **Der Bezug ist das Gewählte, nicht das Teil** (Entscheidung Robert,
#: 03.09.2026). Am Körper heißt das die Körperdiagonale, an einer Bohrung die
#: Scheibe des Merkmalsgriffs — gemessen an ``broomholdervcd_d35mm.stl``
#: 40,07 mm gegen 6,80 mm. Der Unterschied ist Absicht: Wer eine Ø6-Bohrung
#: gewählt hat, bewegt die Bohrung, und ein Griff in Teilgröße läge weit über
#: sie hinaus und sähe aus, als ginge es um das ganze Teil. Ein Versuch, beide
#: gleich groß zu machen, ist an diesem Tag gebaut, gemessen und wieder
#: zurückgenommen worden.
GIZMO_SCALE = 0.3
GIZMO_LINE_RADIUS = 0.035

#: Wie lang der Griff im Bild mindestens wird, in Bildpunkten.
#:
#: **Weil Treffbarkeit keine Millimeterfrage ist.** Der Anteil oben gilt dem
#: Aktor, an dem der Griff hängt — an einer Merkmalsscheibe ist das der
#: Bohrungsdurchmesser, und bei Ø 4 mm bleiben 1,7 mm Pfeil und 0,20 mm
#: Schaft. Wie viele Bildpunkte daraus werden, entscheidet der Zoom.
#:
#: Achtzig ist doppelt so viel, wie der Kommentar an :data:`GIZMO_SCALE` als
#: „zu klein" nennt (vierzig), und liegt in der Grössenordnung des räumlichen
#: Ziehgriffs (:data:`PULL_HANDLE_PIXELS`, 38 — dort ist es allerdings die
#: **halbe** Länge, gemessen vom Mittelpunkt).
GIZMO_LEAST_PIXELS = 80.0


#: Die Operationen, die ein Merkmal so ändern, wie der Griff es täte.
#:
#: **Beide, weil der Griff beides kann.** Er verschiebt und dreht in derselben
#: Geste; wo nur eines von beidem ginge, ist er trotzdem der richtige Weg
#: dorthin. Heute nehmen beide dieselben Arten — würde sich das je trennen,
#: wäre ein Griff, der nur nach der einen fragt, an der anderen blind.
GIZMO_FEATURE_OPS: Final = ("move_feature", "rotate_feature")


def movable_feature_kinds() -> frozenset[str]:
    """Welche Merkmalsarten sich versetzen lassen — gefragt, nicht aufgezählt.

    Der Griff soll an dem Merkmal sitzen, das gewählt ist (§18.11) — aber nur
    dort, wo ein Zug auch etwas auslösen kann. Welche Arten das sind, weiß das
    Register: die Operationen aus ``GIZMO_FEATURE_OPS`` tragen sie in
    ``applies_to``. Eine Liste hier wäre eine zweite Wahrheit, die beim
    nächsten Zuwachs veraltet.

    **Und sie veraltet schnell — dieser Docstring hat es an einem Tag
    vorgeführt.** Er nannte „heute ``hole`` und ``pin``" und führte Kuppe und
    Kugel als gesperrt; gemessen am selben Nachmittag deckt ``move_feature``
    ``hole``, ``pin``, ``cone`` und ``sphere``, ``rotate_feature`` die ersten
    drei (der Kugel fehlt eine Lage, die sich drehen liesse). Die Zahl war
    beim Aufschreiben richtig und drei Commits später falsch — genau deshalb
    steht sie hier als Beispiel und nicht als Bedingung.

    Fehlt eine Operation, zählt sie nicht mit; fehlen alle, ist die Menge leer
    und der Griff bleibt am Körper. Das ist der ehrliche Rückfall: Ohne
    Operation gäbe es nichts zu ziehen.
    """
    from app.core.registry import REGISTRY

    kinds: set[str] = set()
    for name in GIZMO_FEATURE_OPS:
        if REGISTRY.has(name):
            kinds.update(REGISTRY.get(name).applies_to or ())
    return frozenset(kinds)


#: Wie weit hinter der Pfeilspitze die Achsenbeschriftung steht, als Anteil der
#: Pfeillänge.
GIZMO_LABEL_GAP = 1.2


#: Was am Griff steht, wenn er auf einer Fläche sitzt: vor und zurück.
#:
#: **Reines ASCII, und das ist keine Vorliebe.** Die Grenze kam von PyVista,
#: das in einem ``vtkStringArray`` jedes Zeichen außerhalb von ASCII mit
#: ``ValueError: String array contains non-ASCII characters`` ablehnte — der
#: ganze Griffaufbau stürzte damit ab. Der eigene Renderer nimmt UTF-8 an
#: (gemessen am 05.09.2026); die Regel bleibt aus dem Grund darunter.
#:
#: Hier stand deshalb kurz ein Doppelpfeil „↕" und dahinter der Name der
#: Fläche aus ``feature_name``. Beides ging nicht, und der Name war der
#: schwerere Fehler: Auf Französisch heißen vier der sechs Flächen
#: ``Face supérieure``, ``Arrière``, ``Côté gauche`` und ``Côté droit`` — die
#: Anwendung wäre dort beim Klick auf eine Fläche abgestürzt, in der deutschen
#: Fassung dagegen nie.
#:
#: **Der Name steht deshalb, wo Qt zeichnet:** In der Statusleiste, die bei
#: gewähltem Merkmal ohnehin „Platte · Oberseite" zeigt. Am Griff bleibt die
#: Richtung, und die braucht keine Übersetzung.
FACE_ARROW = "<->"


def gizmo_labels(
    origin: tuple[float, float, float],
    length: float,
    face: tuple[str, tuple[float, float, float]] | None = None,
) -> list[tuple[tuple[float, float, float], str]]:
    """Was am Gizmo steht (Regel 18) — drei Achsen oder eine Fläche.

    Die drei Achsen unterschied allein Rot, Grün und Blau — für jeden, der die
    nicht trennt, waren es drei gleiche Pfeile. Ein Buchstabe an der Spitze
    trägt dieselbe Aussage ohne Farbe.

    **Sitzt der Griff auf einer Fläche, sind X, Y und Z die falsche Auskunft.**
    Er springt dann dorthin und kennt nur vor und zurück (§18.11), aber
    beschriftet war er weiter mit drei Achsen — und was wirklich passiert,
    erfuhr der Kunde erst, während er zog. Wer nicht aus dem CAD kommt, liest
    drei Achsenbuchstaben als „hier geht es in drei Richtungen" und zieht in
    eine, die verfällt.

    ``face`` ist Name und Normale der Fläche. **Gezeichnet wird nur die
    Richtung** (:data:`FACE_ARROW`) — der Name gehört nicht hierher, weil die
    Flächennamen übersetzt werden und ein übersetzter Text am Griff in sechs
    Sprachen an einer Stelle stünde, die keine Prüfung sieht (unter VTK, bis
    05.09.2026, nahm die Beschriftung dazu kein Zeichen außerhalb von ASCII
    an). Er steht in der Statusleiste, wo Qt zeichnet. Der Parameter trägt ihn
    trotzdem: Wer die Beschriftung einmal über Qt legt, hat ihn dann zur Hand,
    und die Auskunft „welche Fläche" wird an *einer* Stelle bestimmt statt an
    zweien.
    """
    reach = length * GIZMO_LABEL_GAP
    if face is not None:
        _name, normal = face
        # Auf der Normalen und im selben Abstand wie die Achsenbuchstaben —
        # ein Griffsatz, eine Schreibweise. Nicht auf der Spitze: dort liegt
        # die Beschriftung, wo man greifen will.
        return [
            (
                (
                    origin[0] + float(normal[0]) * reach,
                    origin[1] + float(normal[1]) * reach,
                    origin[2] + float(normal[2]) * reach,
                ),
                FACE_ARROW,
            )
        ]
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
    keinen Renderer, und eine Prüfung, die sich dort überspringt, prüft nie
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
        entered = read_number(self.value.text())
        if entered is None:
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
            " border-radius: 7px; padding: 7px; }"
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
            " border-radius: 6px; }"
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
            " border-radius: 8px; font-weight: 600; }"
        )

    def place(self) -> None:
        parent = self.parentWidget()
        if parent is None:
            return
        self.adjustSize()
        self.move(max((parent.width() - self.width()) // 2, 0), BANNER_TOP)
        self.raise_()


def layout_feature_labels(
    anchors: Sequence[tuple[float, float]],
    sizes: Sequence[tuple[float, float]],
    priorities: Sequence[int],
    room: tuple[float, float, float, float],
    obstacles: Sequence[tuple[float, float, float, float]] = (),
    *,
    gap: float = 6.0,
) -> list[tuple[int, tuple[float, float, float, float]]]:
    """Platziert Beschriftungen ohne Überlappung; Auswahl und Hover haben Vorrang.

    Automatische Namen bleiben nahe ihrem Anker. Explizite Namen dürfen einen
    freien Platz weiter entfernt nutzen; die Ansicht verbindet ihn mit dem
    unveränderten Merkmalspunkt. Ein Bildraster begrenzt die Kollisionskosten.
    Alle Maße sind Bildpunkte, unabhängig von Renderer und Modellgeometrie.
    """
    left, top, right, bottom = room
    cell = max(64.0, gap * 8.0)
    occupied: dict[tuple[int, int], list[tuple[float, float, float, float]]] = {}

    def cells(rect: tuple[float, float, float, float]) -> Any:
        """Die wenigen Rasterfelder, die eine Beschriftung berührt."""
        for x in range(math.floor(rect[0] / cell), math.floor(rect[2] / cell) + 1):
            for y in range(math.floor(rect[1] / cell), math.floor(rect[3] / cell) + 1):
                yield x, y

    def reserve(rect: tuple[float, float, float, float]) -> None:
        """Ein Feld einschließlich seines Leseabstands für folgende Namen belegen."""
        for key in cells(rect):
            occupied.setdefault(key, []).append(rect)

    def fits(rect: tuple[float, float, float, float]) -> bool:
        """Das ganze Feld muss frei und innerhalb der unverdeckten Ansicht liegen."""
        if rect[0] < left or rect[1] < top or rect[2] > right or rect[3] > bottom:
            return False
        for key in cells(rect):
            for other in occupied.get(key, ()):
                if (
                    rect[0] < other[2]
                    and rect[2] > other[0]
                    and rect[1] < other[3]
                    and rect[3] > other[1]
                ):
                    return False
        return True

    for obstacle in obstacles:
        reserve(obstacle)
    placed = []
    for index in sorted(range(len(anchors)), key=lambda item: (priorities[item], item)):
        x, y = anchors[index]
        width, height = sizes[index]
        if not all(math.isfinite(value) for value in (x, y, width, height)):
            continue
        if width <= 0.0 or height <= 0.0 or width > right - left or height > bottom - top:
            continue
        candidates = [
            (x + gap, y - gap - height),
            (x - gap - width, y - gap - height),
            (x + gap, y + gap),
            (x - gap - width, y + gap),
        ]
        if priorities[index] < 2:
            candidates = [
                (min(max(px, left), right - width), min(max(py, top), bottom - height))
                for px, py in candidates
            ]
            # Erst die Nähe, dann freie Zeilen: zwei explizite Namen am selben
            # Anker bleiben beide lesbar, auch wenn eine Karte danebensteht.

        def options(
            initial: Sequence[tuple[float, float]],
            anchor: tuple[float, float],
            extent: tuple[float, float],
            explicit: bool,
        ) -> Any:
            """Die Fernsuche erst beginnen, wenn die vier nahen Plätze belegt sind."""
            yield from initial
            x, y = anchor
            width, height = extent
            if explicit:
                yield from sorted(
                    (
                        (px, py)
                        for py in range(
                            math.ceil(top),
                            math.floor(bottom - height) + 1,
                            max(math.ceil(height + gap), 1),
                        )
                        for px in range(
                            math.ceil(left),
                            math.floor(right - width) + 1,
                            max(math.ceil(width + gap), 1),
                        )
                    ),
                    key=lambda point: (
                        (point[0] + width / 2.0 - x) ** 2 + (point[1] + height / 2.0 - y) ** 2
                    ),
                )

        for px, py in options(candidates, (x, y), (width, height), priorities[index] < 2):
            rect = (px, py, px + width, py + height)
            if not fits(rect):
                continue
            placed.append((index, rect))
            reserve(
                (px - gap / 2.0, py - gap / 2.0, px + width + gap / 2.0, py + height + gap / 2.0)
            )
            break
    return placed


class _SelectionHit(NamedTuple):
    """Ein Treffer behält Körper und Szeneort bis zur gemeinsamen Auswahlfrage."""

    object_id: ObjectId
    scene_point: Vec3
    view_point: Vec3
    cell: int = -1
    feature_id: FeatureId | None = None


class _BoreTarget(NamedTuple):
    """Die für einen Sichtstrahl nötigen Bohrungsmaße, ohne Dreieckskopien."""

    feature_id: FeatureId
    centre: Vec3
    axis: Any
    radius: float
    bounds: tuple[float, float]


class _PreparedScene(NamedTuple):
    """Für den Renderer vorbereitete Netze samt neuen Cache-Einträgen."""

    meshes: dict[ObjectId, Any]
    cached: dict[DisplayKey, Any]
    uncapped: bool


class _SceneMeshWorker(Worker):
    """Dezimierung und Ansichtsbeschnitt abseits des Qt-Hauptthreads."""

    done = Signal(int, object, object)

    def __init__(
        self,
        generation: int,
        result: EvaluationResult,
        tasks: Sequence[tuple[ObjectId, Any, DisplayKey | None]],
        plane: SectionPlane | None,
        second: SectionPlane | None,
    ) -> None:
        super().__init__()
        self._generation = generation
        self._result = result
        self._tasks = tuple(tasks)
        self._plane = plane
        self._second = second
        self.cancelled = CancelSignal()

    def cancel(self) -> None:
        """Die noch nicht begonnene Aufbereitung des Auftrags verwerfen."""
        self.cancelled.cancel()

    def _was_cancelled(self) -> bool:
        """Den nebenläufig veränderlichen Abbruchzustand frisch lesen."""
        return self.cancelled.is_cancelled

    def work(self) -> None:
        meshes: dict[ObjectId, Any] = {}
        cached: dict[DisplayKey, Any] = {}
        uncapped = False
        for object_id, source, cache_key in self._tasks:
            if self._was_cancelled():
                return
            mesh = source
            if cache_key is not None:
                mesh = decimate(mesh, DISPLAY_DECIMATION_TARGET)
                if self._was_cancelled():
                    return
                cached[cache_key] = mesh
            if self._plane is not None:
                to_mesh = getattr(mesh, "to_mesh", None)
                if callable(to_mesh):
                    mesh = to_mesh()
                section = cut(mesh, self._plane, self._second)
                if self._was_cancelled():
                    return
                mesh = section.mesh
                uncapped = uncapped or not section.capped
            meshes[object_id] = mesh
        self.done.emit(
            self._generation,
            self._result,
            _PreparedScene(meshes, cached, uncapped),
        )


class Viewport(QWidget):
    """Die 3D-Ansicht, oder ein schlichter Hinweis, wenn kein Renderer zu bauen ist."""

    measurementTaken = Signal(object)
    """A finished measurement — carries a ``Measurement``."""
    measurementStatus = Signal(str)
    """Der nächste nötige Klick oder der Grund, warum keiner gezählt hat."""
    transformDragged = Signal(object)
    """A finished gizmo drag — carries ``TransformSteps`` (§18.11)."""
    gizmoStatus = Signal(str)
    """Was der Griff bewegen wird — leer, solange keiner steht.

    Dieselbe Bauart wie ``measurementStatus``: Der Viewport sagt, was gilt,
    und wo der Satz erscheint, entscheidet das Fenster."""
    featureMoved = Signal(str, object)
    """Ein Zug hat ein Merkmal versetzt — Kennung und Zielmitte (§18.11).

    Die Zielmitte kommt **absolut** und nicht als Versatz, weil
    ``move_feature`` sie so verlangt und weil nur die Ansicht sie kennt: Sie
    hält das Merkmal in der Hand, das Fenster nicht. Ein Delta zu schicken
    hiesse, die Mitte auf der anderen Seite noch einmal zu suchen."""
    featureTurned = Signal(str, str, float)
    """Ein Zug hat ein Merkmal gekippt — Kennung, Achse, Winkel in Grad.

    **Der Winkel ist der gerastete**, derselbe, der während des Zugs am Zeiger
    stand: ``_settled_angle`` kennt den harten Fang der Leiste und den
    45°-Magneten. Das Fenster könnte ihn nicht nachrechnen, ohne beides zu
    kennen — und ein Wert, der eine andere Drehung verspricht als die, die
    kommt, ist genau der Fehler, den der Zeiger heute Vormittag hatte."""
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
    """Ein Rechtsklick, der nichts gedreht hat — trägt die Stelle in
    Gerätepixeln, gezählt wie Qt (von oben links). Das Fenster zeigt dort das
    Menü zur Auswahl."""
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
    sceneFailed = Signal(str)
    """Die Ansichtsaufbereitung brach ab; die letzte gültige Ansicht bleibt."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        # **Ohne Fokus kein Tastendruck.** Die Flugtasten (§2.9) kommen als
        # ``keyPressEvent`` an diesem Widget an, und Qt schickt sie nur dorthin,
        # wo der Fokus liegt. ``StrongFocus`` heißt: durch Klick **und** über
        # den Tabulator — wer die Ansicht anklickt, um zu fliegen, hat ihn dann
        # ohnehin.
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        #: Welche Flugtasten gerade liegen, und der Takt, der sie fährt.
        self._flying: set[str] = set()
        self._flight_timer: QTimer | None = None
        self._flight_clock = QElapsedTimer()
        # **Und wer fokussierbar ist, muss sich nennen können** (§19.2).
        # Mit der Fokusrichtlinie ist die Ansicht zum ersten Mal ein Element,
        # das ein Bildschirmleser ansteuert; ohne Namen sagt er ihre Bauart an
        # statt dessen, was sie zeigt. Befund von 3d-druck-d4 am 03.09.2026 —
        # eine Regression, die keine Zeile Bedienlogik berührt und trotzdem
        # eine ist.
        self.setAccessibleName(tr("3D-Ansicht"))
        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self.renderer: Renderer | None = None
        """Der Renderer hinter dem Bild (``app.ui.render``) — ``None`` ohne
        3D-Ansicht: offscreen, Wayland ohne X11, ``SOLIDON_NO_VIEWPORT``.
        Alles, was zeichnet, steigt an dieser Wache aus."""
        self._navigator: Navigator | None = None
        """Die Kameraführung (§2.9); sie bekommt jede Zeigergeste, die kein
        Griff nimmt (:meth:`_on_pointer`)."""
        self._pointer_token: int | None = None
        self._actors: dict[ObjectId, Item] = {}
        self._actor_offsets: dict[ObjectId, Any] = {}
        self._actor_scene: EvaluationResult | None = None
        self._frame_actors: list[Any] = []
        self._bed_visible = True
        self._bed_surfaces: list[Any] = []
        """Die gefüllten Ebenen der Betten, je Platte eine. Eigene Liste, weil
        genau sie durchscheinend wird und die anderen Bettteile nicht: Das
        Raster ist ohnehin ein Drahtgitter, der Bauraum sind Linien."""
        self._explosion_middle: tuple[int, Any] | None = None
        #: Die Teilmenge von ``_frame_actors``, die **flach auf dem Bett** liegt:
        #: Fläche und Raster. Nur sie tritt im Skizzenmodus ab — Bauraumkanten
        #: und Maßskala bleiben stehen, weil sie eine Grenze zeigen und kein
        #: zweites Gitter sind. Warum das ein Unterschied ist, steht an
        #: :meth:`set_sketching`.
        self._ground_actors: list[Any] = []
        self._selected: ObjectId | None = None
        self._selected_more: tuple[ObjectId, ...] = ()
        """Die **weiteren** gewählten Körper — ohne den führenden.

        Zwei Aufgaben hängen an der Auswahl, und sie vertragen keine
        gemeinsame Zahl: Die Färbung fragt „was ist gewählt" und meint
        beliebig viele; Griff, Drehbogen, Schatten und Merkmalsliste
        fragen „woran hänge ich" und brauchen genau einen, sonst zeigt
        der Schatten auf ein anderes Teil als der Griff. ``_selected``
        bleibt deshalb der führende Körper, und die Menge steht daneben
        statt an seiner Stelle."""
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
        self._scheme: NavigationScheme = "solidon"
        self._theme: str | None = None
        """Welches Thema gerade gilt — damit :meth:`set_theme` prüfen kann.

        Es gab das Feld nicht, und deshalb konnte der Setter als Einziger der
        sieben nicht auf Änderung prüfen: Dasselbe Thema zum zweiten Mal
        kostete einen vollen Szenenaufbau (gemessen 03.09.2026). ``None`` und
        nicht ``"dark"``, damit der erste Aufruf immer durchläuft — das Fenster
        setzt das Thema beim Start, und ein vorbelegtes Feld ließe die
        Startfarben ungesetzt."""
        self._mode: DisplayMode = "solid"
        self._shading: Shading = "flat"
        self._shadow_opacity = SHADOW_OPACITY["dark"]
        """Deckkraft des Kontaktschattens, von ``set_theme`` gesetzt."""
        self._finding_actors: list[Any] = []
        """Ring und Beschriftung der zuletzt angeklickten Warnung."""
        self._finding_mark: tuple[Vec3, str, str] | None = None
        """Szenenort, Text und Körper der kurzlebigen Warnungsmarke.

        Die Aktoren im Renderer allein reichen nicht als Zustand: Ein Neuaufbau
        derselben Auswertung kann sie aus dem Renderer nehmen, während ihre
        Python-Referenzen weiterleben. Aus diesen drei Werten lässt sich die
        Marke nach dem Aufbau ehrlich neu zeichnen.
        """
        # **Ein Kind und kein ``QTimer.singleShot``.** Der statische Aufruf
        # hält bis zum Ablauf eine Referenz auf dieses Widget — genau das, was
        # ``leash.py`` an anderer Stelle als Ursache eines Absturzes beim
        # Schließen beschreibt. Ein Kind stirbt mit seinem Elternteil.
        self._finding_timer = QTimer(self)
        self._finding_timer.setSingleShot(True)
        self._finding_timer.timeout.connect(self._hide_finding_mark)
        self._projection: Projection = "perspective"
        self._section: SectionPlane | None = None
        self._slice_thickness: float | None = None
        self._result: EvaluationResult | None = None
        self._requested_result: EvaluationResult | None = None
        """Der jüngste Ansichtsauftrag, solange ``_result`` noch das sichtbare Bild trägt."""
        self._uncapped = False
        """Wahr, wenn ein Schnitt offen blieb, weil der Körper es ist (§18.2)."""
        self._object_colour = OBJECT_COLOUR
        self._shown_colours: dict[ObjectId, str] = {}
        """Welche Farbe jeder Körper zuletzt bekommen hat.

        Ohne diesen Vergleich liefe bei jedem Szenenaufbau eine Blende — und
        ``_apply_selection_colour`` läuft auch dann, wenn sich an der Auswahl
        nichts geändert hat. Animiert wird der **Wechsel**, nicht das
        Zeichnen."""
        self._live_colours: dict[ObjectId, tuple[float, ...]] = {}
        """Welche Farbe gerade wirklich an jedem Aktor steht, als drei Zahlen.

        Nicht dasselbe wie ``_shown_colours``: Das nennt das **Ziel** der
        letzten Auswahl, dies den Wert, der im Bild ist — mitten in einer
        Blende liegt er dazwischen. Wird eine Blende abgelöst, ist genau er
        der richtige Startpunkt der nächsten."""
        self._selection_fade: Any = None
        """Die laufende Auswahlblende, damit die nächste sie ablösen kann."""
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
        #: Was einen begonnenen Zug abschließt — Doppelklick oder Eingabetaste.
        #:
        #: Im gefahrenen Modus ist der Zeichenbereich unsichtbar, und seine
        #: eigenen Empfänger (``mouseDoubleClickEvent``, ``keyPressEvent``)
        #: bekommen deshalb nie ein Ereignis. Der Hinweis in der Leiste
        #: versprach beides trotzdem (Z4).
        self._sketch_finish_stroke: Callable[[], bool] | None = None
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
        self._cursor_mesh: Item | None = None
        """Die Linien der Marke, damit sie nicht je Mausbewegung neu entstehen.

        Ein Kreuz hat immer vier Punkte; bewegt es sich, bekommt es nur neue
        Koordinaten (``update_points``)."""
        self._cursor_count = 0
        self._cursor_at: tuple[tuple[float, float], float] | None = None
        """Wo die Marke zuletzt lag und bei welchem Maßstab.

        Der Vergleich davor spart das Neuzeichnen: Ein Render kostet gemessen
        6,9 ms, und die Marke sitzt am **gefangenen** Ort — zwischen zwei
        Rasterpunkten ändert sie sich nicht."""
        self._preview_actor: Item | None = None
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
        self._sketch_cut_available: Callable[[], bool] | None = None
        self._sketch_cut_top: Callable[[], float] | None = None
        """Wie weit die Oberkante des Zielkörpers über der Zeichenebene liegt —
        dort beginnt die Tasche, also auch ihre Drahtform. Vom Fenster, das den
        Körper kennt; null, wenn die Ebene selbst die Oberkante ist."""
        """Ob der Zug nach innen gerade ein echtes Ziel hat.

        Die Tasche braucht einen ausgewählten, bearbeitbaren Körper. Das weiß
        das Fenster; der Viewport nutzt die Antwort für Griff, Vorschau und
        Richtungsprüfung gemeinsam, damit nichts Sichtbares mehr verspricht
        als die spätere Operation halten kann.
        """
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
        self._pending_owner: str = ""
        """Zu welchem Körper der halb gesetzte Punkt gehört — im Bild gefragt,
        weil zwei Platten in der Szene übereinanderliegen (§25)."""
        self._pending_plane: tuple[Vec3, Vec3] | None = None
        self.measurements = MeasurementList()
        self._measure_actors: list[Any] = []
        self._snap_actors: list[Any] = []
        """Die Fangmarke unter dem Zeiger — sie zeigt vor dem Klick, wohin der
        Punkt fällt."""
        self._candidates: tuple[tuple[str, str], ...] = ()
        """Die Merkmale, zwischen denen eine Frage entscheiden lässt (§21.3) —
        je Eintrag Körper und Merkmal, denn dieselbe Kennung gibt es in
        mehreren Körpern."""
        self._candidate_emphasis: tuple[str, str] | None = None
        self._candidate_actors: list[Any] = []
        self._snap_owner: str = ""
        """Der Körper unter dem Zeiger, im Bild gefragt — damit die Marke dort
        steht, wo das Maß danach steht (§25)."""
        self._snap_shown: SnapResult | None = None
        """Was die Marke gerade zeigt. Auskunft für Tests und Schutz davor,
        dieselbe Stelle bei jeder Ruhepause neu zu zeichnen."""
        self._gizmo: Gizmo | None = None
        self._gizmo_wanted = False
        """Ob der Gizmo eingeschaltet ist — unabhängig davon, ob gerade einer
        im Bild steht. Der Griff selbst wird bei jedem Auswahl- und
        Szenenwechsel neu angehängt; dieser Schalter sagt, ob überhaupt."""
        self._gizmo_labels: LabelsItem | None = None
        """Die Buchstaben an den Gizmo-Achsen. Sie gehen mit ihm — und
        während des Zugs mit der Matrix (``update_labels`` in
        :meth:`_on_gizmo_interacted`)."""
        self._gizmo_label_base: Any | None = None
        """Die Startpositionen der Buchstaben, auf die jede Zug-Matrix
        angewandt wird."""
        self._gizmo_label_texts: list[str] = []
        self._face_actor: Any | None = None
        self._ghost_actor: Any | None = None
        self._shape_actor: Any | None = None
        """Das Merkmal in seiner Gestalt — eigener Aktor, damit der Griff an der
        Öffnung bleibt und nicht am Schwerpunkt eines Zylinders.

        **Nicht zu verwechseln mit ``_preview_actor``**, der die Vorschau einer
        noch nicht gesetzten Bohrung zeigt. Dies hier ist ein **erkanntes**
        Merkmal, das gerade gewählt ist."""
        self._arc_actor: Any | None = None
        """Der Bogen, der beim Drehen zeigt, wie weit — und wo er einrastet."""
        self._face_seat: tuple[tuple[float, ...], tuple[float, ...], float] | None = None
        """Wo die letzte Merkmalsmarke sass und wie gross sie war.

        Der Geisterring braucht dieselbe Stelle und dasselbe Mass; zwei
        Rechnungen dafür liefen beim nächsten Zuwachs auseinander."""
        """Der blasse Ring an der Ausgangsstelle, solange ein Merkmal gezogen wird.

        Ohne ihn zeigt der Zug nur, **wohin** — nicht, von wo. Der Körper steht
        währenddessen still (seine Geometrie ändert sich erst bei der
        Auswertung), und damit sah es aus, als bewege sich gar nichts."""
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
        # Kein Einrasten, solange die Leiste nichts anderes sagt — die
        # Begründung steht bei ``DEFAULT_GRID_STEP`` in ``transform_bar``.
        self._grid_step = 0.0
        self._angle_step = 0.0
        self._map: AnalysisMap | None = None
        self._map_object: ObjectId | None = None
        self._occlusion_applied = False
        self._depth_order_for: tuple[tuple[float, ...], tuple[str, ...], int] | None = None
        """Für welche Kameralage und welche Körper zuletzt nach Tiefe geordnet
        wurde — die Ordnung läuft an der Zeichenstelle und darf dort nichts
        kosten, solange sich nichts bewegt."""
        self._bed_visibility_result: EvaluationResult | None = None
        self._bed_visibility_objects: tuple[ObjectId, ...] = ()
        self._bed_has_sunken_body = False
        self._edge_actors: dict[ObjectId, Item] = {}
        self._shadow_actors: list[Any] = []
        self._shadow_owners: dict[ObjectId, list[Any]] = {}
        """Welche Schattenaktoren zu welchem Körper gehören.

        ``_shadow_actors`` ist die flache Liste zum Abräumen; diese Zuordnung
        braucht der Zug, denn während er läuft bewegt sich **ein** Körper und
        sein Schatten soll mit."""
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
        self._edge_meshes: dict[ObjectId, tuple[Any, Any]] = {}
        """Je Körper das Netz, aus dem seine Körperkanten stammen, und sie selbst.

        Dieselbe Bauart und derselbe Grund wie bei ``_shadow_splits``, nur
        teurer: Die Kantensuche kostete an einem Kundenmodell mit 32 Körpern
        **453 ms bei jedem Aufbau** — und ``show_scene`` läuft bei jeder
        Auswahl, jedem Themenwechsel und jedem Schieberschritt (gemessen
        03.09.2026, siehe :meth:`_feature_edges_for`)."""
        self._shadow_ground: dict[ObjectId, tuple[float, float, Any]] = {}
        """Je Körper Unterkante, Oberkante und sein Umriss von oben. Damit
        steht fest, wer auf wem steht — und damit, welche Fläche den Schatten
        auffängt."""
        self._bed_extent: tuple[float, float] | None = None
        """Breite und Tiefe der Druckplatte, sobald ein Bauraum gezeigt wurde.
        Der Schatten wird an ihrer Kante geschnitten; ohne Bauraum gibt es
        nichts zu schneiden."""
        self._build_volume: tuple[float, float, float] | None = None
        """Der Bauraum des geltenden Profils — Breite, Tiefe, Höhe.

        Getrennt von :attr:`_bed_extent`, weil der Schattenschnitt nur die
        Platte braucht und das Einpassen der leeren Szene die Höhe."""
        self._shadow_cast: tuple[float, float] = (SHADOW_SIDE, SHADOW_REACH)
        """Die Lichtrichtung, mit der die Schatten im Bild stehen. Sie folgt
        der Kamera; wer sie schon getroffen hat, zeichnet nicht neu."""
        self._edge_colour = "#4c5258"
        self._feature_overlay = False
        self._feature_actors: list[Any] = []
        self._feature_label_data: list[tuple[Vec3, str, int]] = []
        self._feature_label_owners: list[ObjectId] = []
        self._feature_label_points: Any = None
        self._feature_marker_item: Item | None = None
        self._feature_preview_state: tuple[Any, ...] | None = None
        self._feature_text_item: LabelsItem | None = None
        self._feature_leader_item: Item | None = None
        self._feature_leader_count = 0
        self._feature_label_state: tuple[Any, ...] | None = None
        self._feature_label_content: Any = None
        self._feature_label_style: LabelStyle | None = None
        self._feature_label_sizes: dict[str, tuple[float, float]] = {}
        self._feature_layout_timer = QTimer(self)
        self._feature_layout_timer.setSingleShot(True)
        self._feature_layout_timer.timeout.connect(self._refresh_feature_label_layout)
        self.cameraMoved.connect(self._queue_feature_label_layout)
        self._selected_feature: FeatureId | None = None
        self._selected_features: tuple[FeatureId, ...] = ()
        self._selected_feature_refs: tuple[tuple[ObjectId, FeatureId], ...] = ()
        self._direct_picking = False
        """Ob ein Klick ohne Zwischenstufe das tiefste Ziel meint.

        Aus, solange betrachtet wird — dann ist ein Klick eine Navigation und
        durchläuft die Stufen (:meth:`_click_target`). An, solange ein
        Operationsdialog nach einem Merkmal fragt: dann ist ein Klick eine
        **Antwort**, und wer zweimal zeigen muss, um zu antworten, hält den
        ersten Klick für verschluckt.
        """
        self._feature_geometry: dict[ObjectId, list[tuple[FeatureId, Any, Any, Any]]] = {}
        self._selection_hit: _SelectionHit | None = None
        self._original_pick_cells: set[ObjectId] = set()
        self._feature_cells: dict[ObjectId, tuple[tuple[FeatureId, ...], Any]] = {}
        self._feature_bores: dict[ObjectId, list[_BoreTarget]] = {}
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
        self._feature_patches: dict[ObjectId, Item] = {}
        self._protected_patch: Any | None = None
        self._protected_hatch: Any | None = None
        # Welche Flächen als Sichtflächen gesperrt sind (§22.3), je Körper.
        # **Sitzungsgebunden, und das ist ein Zwischenstand**: Eine
        # Sichtfläche ist eine Eigenschaft des Werkstücks und gehört ins
        # Dokument, mit ``format_version`` und Migration. Bis dahin merkt
        # der Nutzer beim Schließen, dass die Markierung fort ist — was er
        # nicht merken darf, ist, dass sie fehlt, während er sie glaubt.
        self._protected: dict[ObjectId, set[FeatureId]] = {}
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
        """§20: solange das an ist, sind Klicks Pinselstriche."""
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
        """Wo der letzte Zug eines gezogenen Strichs saß — der Mindestabstand
        (halber Pinselradius) rechnet dagegen."""
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
        self._brush_actor: Any = None
        """Der Ring, der ihn zeigt — als Weltmaß in der Szene und nicht am
        Zeiger: Ein Zeiger hat feste Punktgröße und weiß nichts von der Kamera,
        er behauptete beim ersten Zoom eine Größe, die er nicht mehr hat."""
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
        """Wo die Maus zuletzt stand — in Gerätepixeln, gezählt wie Qt
        (oben links), so wie der Renderer sie meldet und beantwortet."""
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
        self._display_cache: dict[DisplayKey, Any] = {}
        """§18.9: die dezimierte Version des zuletzt gezeigten Körpers. Sie
        fließt nie in den Kern zurück."""
        self._scene_generation = 0
        self._scene_worker: _SceneMeshWorker | None = None
        self._scene_leash = WorkerLeash(self)
        """Die rechenintensive Aufbereitung der nächsten gültigen Ansicht."""

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
            notice = QLabel(
                tr("Die 3D-Ansicht steht auf diesem Rechner nicht zur Verfügung."), self
            )
            if hint := unavailable_hint():
                notice.setText(f"{notice.text()} {hint}")
            notice.setWordWrap(True)
            self._layout.addWidget(notice)
            return

        from app.ui.render.factory import make_renderer

        self.renderer = make_renderer(self)
        widget = self.renderer.widget
        # Qt malt hier nichts, der Renderer malt alles.
        #
        # Die Grafikfläche des Renderers ist ein natives Fenster
        # (``WA_PaintOnScreen``, das rendercanvas mit ``present_method="screen"``
        # setzt), und trotzdem stand ``WA_NoSystemBackground`` auf ``False``:
        # Qt füllte den Bereich also mit dem Hintergrund seines Stils, bevor
        # der Renderer darin zeichnen konnte. Zusammen mit dem Stylesheet am
        # ``OverlayHost`` darüber war das unter VTK der Verdächtige für das
        # Bild, in dem nur die Achsenmarker stehen und der Körper beim Bewegen
        # der Kamera aufblitzt. Der Renderer setzt das Attribut an seiner
        # Grafikfläche inzwischen selbst; hier bleibt es, damit die Zusage
        # nicht an einer Zeile in ``gfx_renderer.py`` hängt.
        widget.setAttribute(Qt.WidgetAttribute.WA_NoSystemBackground, True)
        self._layout.addWidget(widget)
        # Während eines Zugs gehören Ziffern dem Wertfeld, nicht der
        # Grafikfläche — der Filter sitzt deshalb auf dem Fenster, das die
        # Tasten bekommt.
        widget.installEventFilter(self)
        # Ohne das kommt eine Mausbewegung erst, wenn eine Taste unten ist —
        # und der Zeiger wüsste nie, worüber er schwebt, sondern nur, worauf
        # jemand schon geklickt hat.
        widget.setMouseTracking(True)
        widget.setCursor(cursors.cursor(self._cursor_role, self))
        # **Ein Eingang für alle Zeigergesten.** Der Renderer meldet sie in
        # Gerätepixeln, wie Qt zählt; :meth:`_on_pointer` verteilt sie in
        # fester Vorfahrt — Griffe vor der Kamera.
        self._listen_to(self.renderer)
        self._add_orientation_widget()
        self._apply_render_quality()
        self.set_theme("dark")
        # **Das gesetzte Schema, nicht ein fest eingetragenes.** Hier stand
        # ``"slicer"``, und der Renderer entsteht später als
        # ``_apply_settings``: Was der Kunde eingestellt hatte, wurde beim
        # Aufbau überschrieben. Menü und Dialog zeigten sein Schema, die Maus
        # fuhr das andere. Solange die Vorgabe ``slicer`` hieß, traf es nur
        # den, der umstellte; seit dem 03.09.2026 träfe es jeden.
        self.set_navigation(self._scheme)
        # **Die eigene Iso, nicht die des Renderers.** Ohne diese Zeile erbte
        # die Anwendung die Startstellung des Renderers — und ihre eigene
        # Vorgabe aus `VIEW_DIRECTIONS` bekam nur zu sehen, wer „Isometrisch"
        # im Menü wählte. Wer das tat, sprang aus einer Ansicht in eine andere,
        # obwohl er die zu sehen glaubte, in der er stand.
        self.view_from("iso")

    def _listen_to(self, renderer: Renderer) -> None:
        """Die Zeigergesten dieses Renderers abonnieren — schwach.

        Der Renderer hält seine Zuhörer, die Ansicht hält den Renderer; ein
        gebundenes ``_on_pointer`` schlösse den Ring, und eine Ansicht, die auf
        den Speicherbereiniger wartet, stirbt mit ihrem Renderfenster im
        falschen Moment. Dieselbe Regel wie für :func:`_weak_callbacks`.
        """
        weak = weakref.ref(self)

        def on_pointer(event: PointerEvent) -> None:
            found = weak()
            if found is not None:
                found._on_pointer(event)

        self._pointer_token = renderer.add_pointer_listener(on_pointer)

    def release_renderer(self) -> None:
        """Den Renderer schließen, solange sein Grafikkontext noch lebt.

        Gerufen aus dem ``closeEvent`` des Fensters: Qts später Prozessabriss
        käme für den Abbau der Grafikfläche zu spät (unter VTK, bis 06.09.2026,
        meldete er je nach Treiber unvollständige Framebuffer oder
        ``wglMakeCurrent``).
        ``release()`` darf das ausdrücklich nicht tun — es bedient auch den
        Sprachwechsel, bei dem im selben Prozess schon das nächste Fenster
        lebt. Ein zweiter Aufruf tut nichts mehr.
        """
        renderer = self.renderer
        if renderer is None:
            return
        self.renderer = None
        self._navigator = None
        self._pointer_token = None
        try:
            renderer.close()
        except Exception as problem:  # pragma: no cover - hängt am nativen Treiber
            # Der Qt-Abbau muss weiterlaufen. Bliebe die Referenz gesetzt oder
            # die Ausnahme liefe bis ins ``closeEvent``, hielte ein bereits
            # angeschlagener Grafiktreiber zusätzlich die ganze Anwendung
            # offen und der nächste Versuch räumte denselben C++-Besitz erneut
            # ab.
            _log.warning("the viewport renderer could not close: %s", problem)

    def _on_pointer(self, event: PointerEvent) -> None:
        """Jede Zeigergeste des Renderers, in fester Vorfahrt.

        Zuerst der Zeiger selbst (Hover, Skizzenvorschau), dann die Griffe —
        Bewegungsgriff und Skalierwürfel sagen mit ``True``, dass die Geste
        ihnen gehört —, zuletzt die Kameraführung. Was ein Griff nimmt, dreht
        keine Kamera; das ist die ganze Vorfahrt, und sie steht an einer
        Stelle statt in drei Beobachtern am Interactor wie bis zum 05.09.2026.
        """
        if event.kind == "move":
            self._note_pointer(event.x, event.y)
        elif event.kind == "leave":
            self._forget_pointer()
        for handle in (self._gizmo, self._scale_handle):
            if handle is not None and handle.handle(event):
                self._queue_feature_label_layout()
                return
        if self._navigator is not None:
            self._navigator.handle(event)
        if event.kind in ("move", "wheel"):
            self._queue_feature_label_layout()

    def _device_ratio(self) -> float:
        """Gerätepixel je Logikpunkt des Fensters — 1,0 ohne Bild."""
        widget = getattr(self.renderer, "widget", None) if self.renderer is not None else None
        if widget is None:
            return 1.0
        return float(widget.devicePixelRatioF()) or 1.0

    def _settle_sketch_view(self, *, draw: bool = True) -> str | None:
        """Eine nahe Hauptansicht einrasten und ihren Namen melden.

        **Im Skizzenmodus und außerhalb**, und der Unterschied liegt nur in
        der Tabelle: Beim Zeichnen sind es die drei Ebenen, auf denen
        gezeichnet wird (eine Rückseite wäre eine falsch benannte Ebene), am
        Modell alle sechs Achsenansichten.

        Abstand, Fokus und Parallelmaßstab ändern sich nicht; das Einrasten
        korrigiert ausschließlich die letzten Grad. **Warum es das tut:** Die
        letzten fünf Grad von Hand zu treffen ist Zielen ohne Gewinn — der
        Kunde will *in* die Vorderansicht, nicht neben sie. Und im
        Skizzenmodus hängt mehr daran als die Anmutung: Solange die Kamera
        frei steht, bewirbt die Leiste den Ziehgriff (``_sketch_pull_offer``
        vergleicht Blick gegen Zeichenebene), und der ist nahe der Draufsicht
        unbrauchbar empfindlich — bei einem Grad Kippung bedeuten zehn Pixel
        Mausbewegung rund siebzig Millimeter Höhe. Das Einrasten nimmt genau
        den Bereich heraus, in dem die Geste angeboten wird und nicht taugt.

        Gemeldet wird der Name nur für die Skizze: ``sketchViewChanged``
        füllt das Ebenenfeld, und außerhalb gibt es keines.
        """
        if self.renderer is None:
            return None
        pose = self.renderer.camera_pose()
        position, focus = pose.position, pose.focal_point
        sketching = self._sketch_frame is not None
        table = SKETCH_VIEW_DIRECTIONS if sketching else AXIS_VIEW_DIRECTIONS
        found = sketch_view_near(position, focus) if sketching else axis_view_near(position, focus)
        if found is not None:
            direction, up = table[found]
            distance = max(math.dist(tuple(position), tuple(focus)), EPS_GEOM)
            snapped = (
                float(focus[0]) + direction[0] * distance,
                float(focus[1]) + direction[1] * distance,
                float(focus[2]) + direction[2] * distance,
            )
            self.renderer.set_camera_pose(CameraPose(snapped, focus, up))
            self.renderer.reset_clipping_range()
            if draw:
                self._draw()
        if not sketching:
            return found
        self.sketchViewChanged.emit(found or "")
        return found

    # --- Darstellungsqualität (§18.1) -------------------------------------------

    def _add_orientation_widget(self, theme: str = "dark") -> None:
        """Das Achsenkreuz unten links: die Anzeige, wo oben ist.

        Pfeile, keine Kugeln: ein kräftiger Schaft mit einer Spitze darauf ist
        das, was jeder aus einem Konstruktionsprogramm kennt. Die Werte sind
        aufeinander abgestimmt — ein dünner Schaft mit dicker Spitze sieht aus
        wie ein Stecknadelkopf, ein dicker mit kurzer Spitze wie ein abgesägter
        Balken. Die Schriftfarbe wechselt mit dem Thema: Eine feste Farbe ist
        auf einem der beiden Hintergründe unlesbar (VTKs Vorgabe war Schwarz,
        und das auf dem dunklen).
        """
        if self.renderer is None:
            return
        try:
            self.renderer.set_axes_marker(
                AxesMarkerStyle(
                    x_colour=AXIS_X,
                    y_colour=AXIS_Y,
                    z_colour=AXIS_Z,
                    label_colour=AXIS_LABEL_DARK if theme != "light" else AXIS_LABEL_LIGHT,
                    shaft_length=0.78,
                    tip_length=0.28,
                    cone_radius=0.5,
                    line_width=3.0,
                    ambient=0.4,
                )
            )
        except Exception as problem:  # pragma: no cover - hängt am Treiber
            _log.info("orientation widget unavailable: %s", problem)
            return
        self._place_orientation_widget()

    def view_point_of(self, point: Vec3, object_id: str = "") -> Vec3:
        """Einen Ort aus der Szene dorthin rechnen, wo er im Bild liegt (§25).

        **Beide Richtungen gibt es, und beide werden gebraucht.** Ein Klick
        kommt aus der Ansicht und muss in die Szene zurück (``_from_view``);
        ein Ort aus einem Befund kommt aus der Szene und muss in die Ansicht.
        Für die zweite Richtung gab es keine Stelle: ``fly_to`` nimmt seinen
        Punkt roh, und bei einem Körper auf Platte 2 liegt der eine Bettbreite
        neben dem, was der Kunde sieht — dieselbe Verwechslung, die beim Klick
        schon einmal eine Bohrung danebengesetzt hat.

        Ohne Objektkennung oder ohne Auswertung bleibt der Punkt, wie er ist:
        Ein Versatz, den man nicht zuordnen kann, ist keiner.
        """
        if not object_id or self._result is None:
            return point
        entry = self._result.scene.objects.get(object_id)
        if entry is None:
            return point

        import numpy as np

        shift = np.asarray(self._view_offset(entry, self._result), dtype=float)
        moved = np.asarray(point, dtype=float) + shift
        return (float(moved[0]), float(moved[1]), float(moved[2]))

    def mark_finding(self, point: Vec3, title: str, object_id: str = "") -> None:
        """Eine vergängliche Marke an der Stelle, die ein Befund nennt (§18.4).

        **Der Flug allein beantwortet die Frage nicht.** Ein angeklickter
        Befund bringt die Kamera an einen Ort — und dort steht der Kunde vor
        einem Teil, das überall gleich aussieht. Wo eine Analysekarte läuft,
        färbt sie die Stelle ein; die Hälfte der Befunde hat keine.

        **Der Ring liegt in der Bildebene**, anders als der des Pinsels
        (``_ring_points`` mit der Flächennormale). Dort ist die Neigung der
        Fläche die Auskunft; hier ist es die Stelle, und eine Marke, die man
        aus dem falschen Winkel als Strich sieht, zeigt nichts. Der Ort eines
        Befunds liegt außerdem oft **im** Material — die Mitte einer Bohrung
        etwa —, und dort gibt es gar keine Fläche, deren Normale man nehmen
        könnte.

        **Der Titel darf jede Sprache tragen.** Der Renderer nimmt
        Beschriftungen in UTF-8 an; die ASCII-Regel des Griffs
        (:data:`FACE_ARROW`) hat einen anderen Grund und gilt hier nicht.
        (Unter VTK, bis 05.09.2026, galt dessen ASCII-Grenze nur für ein
        Textarray als *Dataset-Feld*, nicht für eine Punktliste an
        ``add_point_labels`` — gemessen am 30.08.2026 ging „Face supérieure"
        hier durch und fiel dort.)
        """
        if self.renderer is None:
            return

        self._finding_timer.stop()
        self._finding_mark = (point, title, object_id)
        self._draw_finding_mark()
        self.renderer.render()
        self._finding_timer.start(FINDING_MARK_MS)

    def _draw_finding_mark(self) -> None:
        """Ring und Beschriftung der gemerkten Warnungsmarke zeichnen.

        Aus ``_finding_mark`` — Szenenort, Text, Körper — und nicht aus alten
        Aktoren: Ein Neuaufbau derselben Auswertung nimmt die aus dem Renderer,
        und aus den drei Werten lässt sich die Marke ehrlich neu zeichnen.
        """
        if self.renderer is None or self._finding_mark is None:
            return

        import numpy as np

        self._remove_finding_actors()
        point, title, object_id = self._finding_mark
        if object_id:
            entry = self._result.scene.objects.get(object_id) if self._result is not None else None
            if entry is None or not self._in_view(object_id, entry):
                # Die Marke darf für ihre kurze Restfrist gemerkt bleiben:
                # Wird der Körper wieder eingeblendet oder seine Platte
                # gewählt, zeichnet der nächste Aufbau sie erneut. Solange
                # der Körper nicht im Bild steht, darf aber auch sein Hinweis
                # nicht körperlos im Raum schweben.
                return
        pose = self.renderer.camera_pose()
        towards = np.asarray(pose.position, dtype=float) - np.asarray(pose.focal_point, dtype=float)
        # Wie hoch das Bild an dieser Stelle ist: orthografisch steht es als
        # Parallelmaßstab, perspektivisch wächst es mit dem Abstand.
        span = float(self.renderer.parallel_scale() or 0.0)
        if span <= 0.0:
            span = float(np.linalg.norm(towards)) * 0.5
        radius = max(span * FINDING_RING_SHARE, EPS_GEOM)

        centre = np.asarray(self.view_point_of(point, object_id), dtype=float)
        # **Der Ring wird nicht nach vorn gezogen, und das ist gemessen.** Der
        # Ort einer Warnung liegt oft im Material — die Mitte einer Bohrung,
        # der Schwerpunkt einer Fläche —, und der Ring verschwindet dort zur
        # Hälfte hinter der Wand. Der naheliegende Ausweg, ihn entlang der
        # Blickachse davorzuziehen, setzt voraus, dass die Projektion
        # orthografisch ist; sie ist es nicht. Im Bild wanderte die Marke damit
        # sichtbar von der Stelle weg, die sie meint, und wurde größer.
        # **Eine Marke neben der Sache ist schlechter als eine halb verdeckte.**
        # Die Beschriftung trägt ``always_visible`` und steht in jedem Fall.
        ring = _ring_points(centre, towards, radius)
        self._finding_actors.append(
            self.renderer.add_lines(
                shapes.closed_ring(ring),
                name="finding_ring",
                colour=SELECTED_COLOUR,
                width=3.0,
                connected=True,
            )
        )
        if title:
            self._finding_actors.append(
                self.renderer.add_labels(
                    np.asarray([centre + np.array([0.0, 0.0, radius])], dtype=float),
                    [title],
                    name="finding_label",
                    style=LabelStyle(
                        text_colour=SELECTED_COLOUR, font_size=12, bold=True, always_visible=True
                    ),
                )
            )

    def _remove_finding_actors(self) -> bool:
        """Nur die nativen Aktoren entfernen, den semantischen Ort behalten."""
        actors = list(self._finding_actors)
        self._finding_actors.clear()
        if self.renderer is None:
            return bool(actors)
        import contextlib

        for actor in actors:
            with contextlib.suppress(Exception):  # hängt am Treiber
                self.renderer.remove(actor)
        return bool(actors)

    def _hide_finding_mark(self, *, render: bool = True) -> None:
        """Die Marke wieder wegnehmen — nach der Zeit oder vor der nächsten."""
        self._finding_timer.stop()
        self._finding_mark = None
        removed = self._remove_finding_actors()
        if render and removed and self.renderer is not None:
            self.renderer.render()

    def _prepare_finding_mark(self, result: EvaluationResult | None) -> bool:
        """Ob dieselbe Auswertung ihre aktive Marke erneut zeichnen darf."""
        if result is not None and result is self._result:
            return self._finding_mark is not None
        # Ein neuer Zustand kann denselben Punkt etwas anderes bedeuten
        # lassen. Deshalb verschwinden Aktoren **und** semantischer Zustand.
        self._hide_finding_mark(render=False)
        return False

    def _light_the_body(self, theme: str) -> None:
        """Das Frontlicht auf den Wert dieses Themas setzen (:data:`HEADLIGHT`).

        Über den Vertrag (``set_headlight``): Welche Lichter der Renderer
        aufstellt und in welcher Reihenfolge, ist seine Sache; dass eines
        davon das Frontlicht ist, ist die Eigenschaft, an der hier etwas
        hängt. Meldet der Treiber einen Fehler, bleibt es beim Vorgabewert —
        ein Körper ohne Frontlicht ist dunkler, aber sichtbar.
        """
        if self.renderer is None:
            return
        wanted = HEADLIGHT["light" if theme == "light" else "dark"]
        try:
            self.renderer.set_headlight(wanted)
        except Exception as problem:  # pragma: no cover - hängt am Treiber
            _log.info("headlight unavailable: %s", problem)

    def _apply_render_quality(self) -> None:
        """Kantenglättung und Umgebungsverdeckung.

        Zwei Zutaten, beide gemessen: Kantenglättung kostet auf dieser Maschine
        nichts Messbares und nimmt jeder schrägen Kante die Treppe.
        **Umgebungsverdeckung** ist die eigentliche Verbesserung — sie
        verdunkelt, was eng beieinander liegt, und macht damit eine Bohrung
        ohne eine einzige Linie als Vertiefung erkennbar.

        Beide laufen in einem ``try``, weil sie am Treiber hängen: eine
        Maschine, deren Grafiktreiber sie nicht kann, soll ein einfacheres Bild
        bekommen und keinen Absturz. Was nicht ging, steht im Protokoll — nicht
        vor dem Nutzer, der hat nichts davon.
        """
        if self.renderer is None:
            return
        try:
            self.renderer.set_anti_aliasing(True)
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

        Als Eigenschaft und nicht als Zustand des Renderers, damit die **Regel**
        prüfbar bleibt: auf der Offscreen-Plattform gibt es keinen Renderer, und
        ein Test, der sich dort überspringt, prüft nie etwas.
        """
        return self._map is None

    def sunken_body(self) -> bool:
        """Ob ein sichtbarer Körper unter die Bettfläche ragt (§18.6).

        Die Frage entscheidet, ob die Platte durchscheinend wird — und sie
        wird an der **Szene** gestellt, nicht am Bild: Ein Körper, der unten
        heraussteht, tut das aus jeder Kamerastellung.

        Maßgeblich bleibt die vollständig aufgebaute Szene, während die nächste
        rechnet. Die Entscheidung gilt bis zu deren Wechsel oder einer anderen
        sichtbaren Körpermenge; ein Kamerabild fragt keine exakten CAD-Grenzen
        erneut ab. Schnitt- und Vorschaunetze ersetzen diese Dokumentgrenzen nicht.
        """
        result = self._actor_scene if self._actor_scene is not None else self._result
        if result is None:
            self._bed_visibility_result = None
            self._bed_visibility_objects = ()
            self._bed_has_sunken_body = False
            return False
        if self._actor_scene is not None:
            visible = tuple(
                object_id
                for object_id in result.scene.objects
                if (actor := self._actors.get(object_id)) is not None and actor.visible()
            )
        else:
            visible = tuple(
                object_id
                for object_id, entry in result.scene.objects.items()
                if self._in_view(object_id, entry)
            )
        if self._bed_visibility_result is result and self._bed_visibility_objects == visible:
            return self._bed_has_sunken_body
        sunken = any(
            float(result.scene.objects[object_id].mesh.bounds.minimum[2])
            < -BED_SURFACE_DROP - EPS_GEOM
            for object_id in visible
        )
        self._bed_visibility_result = result
        self._bed_visibility_objects = visible
        self._bed_has_sunken_body = sunken
        return sunken

    def _apply_bed_transparency(self) -> None:
        """Setzt die Deckkraft der Bettflächen nach dieser Regel.

        Am vorhandenen Aktor und nicht durch Neuaufbau: Der Bauraum wird beim
        Wechsel des Druckers gezeichnet, die Frage stellt sich bei jeder
        Auswertung neu.
        """
        wanted = BED_SUNKEN_OPACITY if self.sunken_body() else 1.0
        for surface in self._bed_surfaces:
            surface.set_opacity(wanted)

    @property
    def sees_through(self) -> bool:
        """Ob gerade durch die Körper hindurchgesehen werden soll.

        Zwei Lagen führen dazu: der Darstellungsmodus *Transparent* (Taste 4)
        und der Skizzenmodus, der den vorhandenen Körper leise stellt, damit
        die Zeichnung darauf lesbar bleibt (:data:`SKETCH_CONTEXT_OPACITY`).

        Als Eigenschaft und nicht als Zustand des Renderers, aus demselben
        Grund wie bei :attr:`ambient_occlusion`: Offscreen gibt es keinen
        Renderer, und eine Regel, die nur dort gilt, wo niemand sie prüfen
        kann, ist keine.
        """
        return (
            self._mode == "transparent"
            or self._sketch_frame is not None
            # Eine durchscheinende Bettfläche ist ein transluzenter Aktor
            # unter **allen** Körpern; ohne die Ordnung wäre gerade das falsch
            # gezeichnet, was sie sichtbar machen soll (Hinweis 3d-druck-85).
            or self.sunken_body()
        )

    def _order_by_depth(self) -> None:
        """Durchsichtige Körper von hinten nach vorn zeichnen — der Maleralgorithmus
        auf Objektebene (Hinweis 3d-druck-85, 03.09.2026).

        Ohne Tiefenschälung mischt ein Renderer halbdurchsichtige Flächen in
        der Reihenfolge der Aktoren — unter VTK, bis 06.09.2026, zweimal
        gemessen und nicht behebbar; pygfx mischt gewichtet und
        reihenfolgeunabhängig, und die Ordnung geht weiter über den Vertrag
        (``set_draw_order``), denn die Regel darunter bleibt dieselbe (siehe
        ``ansicht.md``). Sortiert wird nach dem Abstand des Mittelpunkts zur
        Kamera, der fernste zuerst — richtig für getrennte Körper, machtlos bei
        sich durchdringenden. Die Bettflächen zählen mit, sobald sie
        durchscheinen: Sie liegen unter allen Körpern, und eine falsch
        einsortierte Fläche verdeckt genau das, was sie zeigen soll.

        Hängt an ``_draw`` und merkt sich, wofür sie geordnet hat — an der
        Zeichenstelle darf sie nichts kosten, solange sich nichts bewegt.
        """
        if self.renderer is None or not self.sees_through:
            return
        if len(self._actors) + len(self._bed_surfaces) < 2:
            return

        import numpy as np

        eye = np.asarray(self.renderer.camera_pose().position, dtype=float)
        seen = (tuple(eye.tolist()), tuple(self._actors), len(self._bed_surfaces))
        if seen == self._depth_order_for:
            return
        self._depth_order_for = seen
        ordered = [*self._actors.values(), *self._bed_surfaces]
        ranked = [
            (float(np.linalg.norm(np.asarray(item.centre(), dtype=float) - eye)), index, item)
            for index, item in enumerate(ordered)
        ]
        # Der Index hält die Reihenfolge stabil, wo zwei Körper gleich weit
        # weg sind — sonst tauschten sie bei jedem Zeichnen die Plätze.
        self.renderer.set_draw_order(
            [item for _far, _index, item in sorted(ranked, key=lambda entry: (-entry[0], entry[1]))]
        )

    def _apply_ambient_occlusion(self) -> None:
        """Die Regel an den Renderer geben, wenn es einen gibt."""
        wanted = self.ambient_occlusion
        if self.renderer is None or self._occlusion_applied == wanted:
            return
        try:
            self.renderer.set_ambient_occlusion(wanted, radius=SSAO_RADIUS, bias=SSAO_BIAS)
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
        if self.renderer is None:
            return (SHADOW_SIDE, SHADOW_REACH)
        pose = self.renderer.camera_pose()
        return shadow_direction(pose.position, pose.focal_point)

    def _shadow_hulls_for(
        self, object_id: ObjectId, points: Any, mesh: Any, source: Any
    ) -> list[Any]:
        """Die Schattenhüllen eines Körpers — aus dem Cache, solange sein Netz dasselbe ist.

        Verglichen wird die **Identität** des Netzes (``source``), nicht sein
        Inhalt: Ein Hash über Millionen Dreiecke wäre nicht billiger als die
        Zerlegung, die er spart. ``show_scene`` läuft bei jeder Auswahl, jedem
        Themenwechsel und jedem Schieberschritt; das Netz dahinter bleibt
        dabei dasselbe. **Der Schnittschieber trifft den Cache absichtlich
        nicht**: ``cut`` erzeugt dort wirklich ein neues Netz.
        """
        cached = self._shadow_splits.get(object_id)
        if cached is not None and source is not None and cached[0] is source:
            return cached[1]
        hulls = self._shadow_hulls_of(points, mesh)
        if source is not None:
            self._shadow_splits[object_id] = (source, hulls)
        return hulls

    def _shadow_hulls_of(self, points: Any, mesh: Any) -> list[Any]:
        """Die Punkte, aus denen ein Körper seinen Schatten wirft — je Stück eines.

        Ein Körper aus mehreren Stücken wirft je Stück einen Schatten (Robert,
        25.08.2026, am Bildschirm gesehen). Welche Dreiecke ein Stück bilden,
        sagt der Kern (:func:`face_components`); die Hülle je Stück kommt aus
        seinen Punkten — bereits mit dem Versatz der Ansicht, wie ``points``
        gezeichnet wird.
        """
        import numpy as np

        raw = getattr(mesh, "raw", None)
        pieces = face_components(raw) if raw is not None else []
        if raw is None or len(pieces) <= 1:
            single = self._shadow_hull_of(points)
            return [single] if single is not None else []
        faces = np.asarray(raw.faces, dtype=np.int64)
        grid = np.asarray(points, dtype=float)
        hulls = []
        for piece in pieces:
            used = np.unique(faces[np.asarray(piece, dtype=np.int64)].ravel())
            hull = self._shadow_hull_of(grid[used])
            if hull is not None:
                hulls.append(hull)
        return hulls

    def _shadow_hull_of(self, points: Any) -> Any:
        """Die Punkte, aus denen ein Stück seinen Schatten wirft: seine konvexe Hülle.

        Einmal je Körper statt einer Triangulierung über jeden Punkt des
        Anzeigenetzes bei jedem Ansichtswechsel (gemessen: 31 ms bei
        zwanzigtausend Dreiecken, 127 ms bei zweiundachtzigtausend, je
        Körper). ``_thinned_for_hull`` deckelt die Kosten bei feinen Kugeln.
        """
        import numpy as np
        from scipy.spatial import ConvexHull, QhullError

        thinned = _thinned_for_hull(np.asarray(points, dtype=float))
        if len(thinned) < 4:
            return thinned if len(thinned) >= 3 else None
        try:
            return thinned[ConvexHull(thinned).vertices]
        except QhullError as problem:
            # Ein ebener oder entarteter Körper hat keine räumliche Hülle. Seine
            # Punkte sind dann ohnehin wenige — sie gehen unverändert weiter.
            _log.info("shadow hull unavailable: %s", problem)
            return thinned

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
        """Der Umriss eines Schattens auf der Fläche ``ground`` — als Ecken
        eines konvexen Vielecks, ``(n, 3)``, oder nichts.

        Die Hülle wird schräg projiziert (:func:`shadow_points`), ihr Umriss
        von oben genommen (:func:`outline_of`) und am Umriss der Fläche
        geschnitten, auf die er fällt (:func:`clip_polygon`) — außerhalb lag
        er auf blankem Hintergrund und behauptete Boden, wo keiner ist. Ein
        einziges Vieleck statt einer Triangulierung: Die Punkte liegen bereits
        in der Reihenfolge des Randes, ``shapes.polygon`` fächert sie auf.
        """
        import numpy as np

        if hull_points is None or len(hull_points) < 3:
            return None
        cast_points = shadow_points(hull_points, direction, ground)
        outline = outline_of(cast_points)
        if outline is None:
            return None
        if window is not None:
            outline = clip_polygon(outline, window)
            if len(outline) < 3:
                return None
        return np.column_stack((outline, np.full(len(outline), ground + SHADOW_LIFT)))

    # --- scene ------------------------------------------------------------------

    def show_preview_mesh(self, object_id: str, mesh: Any) -> None:
        """Die Vorschau eines Zugs: dieselben Punkte, anderswo — ohne Neuaufbau.

        Ein Pinselstrich oder ein Skelettzug verschiebt Punkte und ändert die
        Dreiecke nicht; der Aktor bekommt nur neue Koordinaten. Passt die Zahl
        nicht mehr, ist es keine Vorschau, sondern ein Aufbau — dann tut diese
        Methode nichts, und ``show_scene`` übernimmt.
        """
        import numpy as np

        actor = self._actors.get(object_id)
        if actor is None or self.renderer is None:
            return
        points = np.asarray(mesh.raw.vertices, dtype=float)
        try:
            actor.update_points(points)
        except ValueError:
            return
        self.renderer.render()

    def clear_preview_mesh(self) -> None:
        """Zurück zu dem, was wirklich in der Szene steht.

        Über den vollen Neuaufbau und nicht über gemerkte Punkte: Was gezeigt
        wurde, war eine Vorschau, und der Dokumentzustand ist die einzige
        Wahrheit darüber, was danach zu sehen ist.
        """
        self.show_scene(self._scene_for_rebuild())

    def _rebuild_layer(self) -> None:
        """Der aufgeschobene Schnitt, wenn der Schichtschieber zur Ruhe kommt.

        Eine eigene Methode und kein Lambda am Zeitgeber: Qt hält eine
        gebundene Methode schwach, ein Lambda hielte die Ansicht am eigenen
        Kind fest (siehe ``__init__`` und `.claude/rules/oberflaeche.md`).
        """
        self.show_scene(self._scene_for_rebuild())

    def _scene_for_rebuild(self) -> EvaluationResult | None:
        """Die jüngste Szene für einen Neuaufbau aus einer Ansichtsänderung.

        Während ein Arbeiter R2 vorbereitet, bleibt ``_result`` absichtlich
        auf dem sichtbaren R1. Ein Themen-, Filter- oder Schnittwechsel darf
        daraus keinen neuen R1-Auftrag machen und damit R2 verwerfen.
        """

        return self._requested_result if self._scene_worker is not None else self._result

    def show_scene(self, result: EvaluationResult | None) -> None:
        """Bereitet teure Netze im Arbeiter vor und behält bis dahin das Bild."""

        self._requested_result = result
        self._scene_generation += 1
        generation = self._scene_generation
        previous = self._scene_worker
        if previous is not None:
            previous.cancel()
            self._scene_leash.retire(previous)
            self._scene_worker = None
        prepared = self._scene_tasks(result)
        if prepared is None:
            self._apply_scene(result)
            return
        tasks, plane, second = prepared
        assert result is not None
        worker = _SceneMeshWorker(generation, result, tasks, plane, second)
        self._scene_worker = worker
        worker.done.connect(self._scene_ready)
        worker.crashed.connect(weak_slot(self, Viewport._scene_crashed, generation, forward=True))
        worker.finished.connect(
            weak_slot(self, lambda view, done: view._scene_worker_done(done), worker)
        )
        self._scene_leash.start(worker)

    def _scene_tasks(
        self, result: EvaluationResult | None
    ) -> (
        tuple[
            list[tuple[ObjectId, Any, DisplayKey | None]],
            SectionPlane | None,
            SectionPlane | None,
        ]
        | None
    ):
        """Die nötige Aufbereitung, wenn mindestens ein Schritt teuer ist."""

        if result is None or self.renderer is None:
            return None
        plane, second = self._section_planes()

        tasks: list[tuple[ObjectId, Any, DisplayKey | None]] = []
        heavy = plane is not None
        for object_id, entry in result.scene.objects.items():
            if not self._in_view(object_id, entry):
                continue
            mesh = entry.mesh
            cache_key = None
            may_decimate = not (self._map is not None and self._map_object == object_id)
            if mesh.triangle_count > DISPLAY_DECIMATION_ABOVE and may_decimate:
                key = _display_key(object_id, mesh, result.object_hashes.get(object_id, ""))
                found = self._display_cache.get(key)
                if found is None:
                    cache_key = key
                    heavy = True
                else:
                    mesh = found
            tasks.append((object_id, mesh, cache_key))
        return (tasks, plane, second) if heavy else None

    def _scene_ready(
        self,
        generation: int,
        result: EvaluationResult,
        prepared: _PreparedScene,
    ) -> None:
        """Nur das Ergebnis des jüngsten Ansichtsauftrags übernehmen."""

        if generation != self._scene_generation:
            return
        self._apply_scene(result, prepared)

    def _scene_crashed(self, generation: int, detail: str) -> None:
        """Die alte Ansicht stehen lassen und den Fehler nach außen melden."""

        if generation == self._scene_generation:
            self.sceneFailed.emit(detail)

    def _scene_worker_done(self, worker: _SceneMeshWorker) -> None:
        """Den ausgelaufenen Aufbereiter identitätssicher loslassen."""

        if self._scene_worker is worker:
            self._scene_worker = None
        self._scene_leash.hold_until_done(worker)

    def wait_for_workers(self, timeout_ms: int = 2000) -> bool:
        """Die Ansichtsaufbereitung vor dem Fensterabbau auslaufen lassen."""

        # Ein ``done`` kann schon in Qts Ereignisschlange liegen, obwohl der
        # Thread selbst nicht mehr läuft. Das Abbruchsignal erreicht diesen
        # fertigen Auftrag nicht mehr; nur eine neue Generation macht auch
        # seinen bereits eingereihten Rückruf zuverlässig ungültig.
        self._scene_generation += 1
        workers = (
            self._scene_worker,
            *self._scene_leash.pending(),
        )
        unique = {id(worker): worker for worker in workers if worker is not None}
        for worker in unique.values():
            worker.cancel()
        for worker in unique.values():
            if worker.isRunning():
                worker.wait(timeout_ms)
        return not any(worker.isRunning() for worker in unique.values())

    def release(self, timeout_ms: int = 2000) -> None:
        """Die einheitliche Aufräumgrenze für jedes Widget mit Halteleine."""

        self.wait_for_workers(timeout_ms)

    def _apply_scene(
        self,
        result: EvaluationResult | None,
        prepared: _PreparedScene | None = None,
    ) -> None:
        """Baut die Ansicht aus einer vollständig vorbereiteten Auswertung neu (§15.3)."""
        # Ein voller Neuaufbau schneidet an der aktuellen Schichthöhe mit —
        # ein noch ausstehender Schnitt vom Schieber wäre danach derselbe
        # noch einmal.
        self._layer_rebuild.stop()
        restore_finding = self._prepare_finding_mark(result)
        self._result = result
        # Ein Hoverziel gehört ebenso zur Auswertung wie seine vorbereiteten
        # Dreiecke. Nach einer Änderung kann dieselbe Kennung eine andere
        # Fläche meinen oder ganz verschwunden sein.
        self._hover_timer.stop()
        self._hover_feature = False
        self._hovered_object = None
        self._hovered_feature = None
        # Und die Kandidaten einer Frage ebenso: Sie zeigen auf Dreiecke einer
        # bestimmten Auswertung, und nach der nächsten kann dieselbe Kennung
        # eine andere Fläche meinen. Wer die Frage noch offen hat, bekommt sie
        # mit dem nächsten Aufruf zurück.
        self._candidates = ()
        self._candidate_emphasis = None
        # Die Fangmarke gehört zu einer Geometrie, die es gleich nicht mehr
        # gibt. Die Maße bleiben (sie überleben eine Auswertung, §18.3), die
        # Marke nicht: Sie zeigt auf eine Ecke, die dieser Schritt entfernt
        # haben kann. Sie kommt bei der nächsten Ruhepause des Zeigers wieder.
        self._clear_snap_preview()
        # Eine Auswahl gehört zur aktuellen Auswertung. Der Körper darf nach
        # einem Schritt weiter ausgewählt bleiben; ein Merkmal, das dieser
        # Schritt entfernt hat, dagegen nicht. Ohne den Rückfall blieb seine
        # Kennung intern stehen, der Körper verlor die Auswahlfarbe und im Bild
        # war weder die alte Fläche noch eine neue Auswahl zu sehen.
        if result is not None:
            if self._selected_feature_refs:
                self._remember_feature_refs(
                    tuple(
                        (object_id, feature_id)
                        for object_id, feature_id in self._selected_feature_refs
                        if (entry := result.scene.objects.get(object_id)) is not None
                        and feature_id in entry.features
                    )
                )
            # Auch die weiteren: Ein Schritt, der einen von ihnen verschmilzt,
            # ließe seine Kennung sonst in der Menge stehen — unsichtbar, bis
            # eine spätere Auswertung sie unter demselben Namen neu vergibt.
            self._selected_more = tuple(
                other for other in self._selected_more if other in result.scene.objects
            )
        if result is not None and self._selected is not None:
            selected_entry = result.scene.objects.get(self._selected)
            if selected_entry is None:
                self._selected = None
                self._selected_feature = None
                self._selected_features = ()
            elif (
                self._selected_feature is not None
                and self._selected_feature not in selected_entry.features
            ):
                self._selected_feature = None
                self._selected_features = ()
            else:
                self._selected_features = tuple(
                    feature_id
                    for feature_id in self._selected_features
                    if feature_id in selected_entry.features
                )
        # Die vorbereiteten Merkmalsdreiecke gehören der vorigen Auswertung.
        # Eine Op, die eine Bohrung verschiebt, ändert ihre Dreiecke, und ein
        # Klick träfe danach, wo sie war.
        self._feature_geometry.clear()
        self._selection_hit = None
        self._original_pick_cells.clear()
        self._feature_cells.clear()
        self._feature_bores.clear()
        self._object_hulls.clear()
        # Eine Platte mehr heißt ein Bett mehr. Die Kulisse gehört
        # ``show_build_volume``, und die kennt die Szene nicht — hier ist die
        # Stelle, an der die Zahl bekannt wird. Nur bei Änderung, sonst baute
        # jede Auswertung vier Betten neu, die schon stehen.
        if self._profile is not None and self._beds_for_view() != self._beds_drawn:
            self.show_build_volume(self._profile)
        # Vor dem Renderer-Zweig: ob ein Projekt schon einmal im Bild stand, ist
        # eine Aussage über die Szene und nicht über den Renderer — offscreen
        # gibt es keinen, und ein Test, der sich dort überspringt, prüft nie
        # etwas.
        self._fit_once_for(result)
        if result is None:
            # Eine leere Szene hat keine Auswahl, kein gewähltes Merkmal und
            # keine Maße. Vor dem Renderer-Zweig, aus demselben Grund wie das
            # Einpassen: das sind Aussagen über die Szene, nicht über den
            # Renderer.
            self._selected = None
            self._selected_more = ()
            self._selected_feature = None
            self._selected_features = ()
            self._selected_feature_refs = ()
            self._hover_feature = False
            self._hovered_object = None
            self._hovered_feature = None
            self.measurements.clear()
        if self.renderer is None:
            return
        for actor in self._actors.values():
            self.renderer.remove(actor)
        self._actors.clear()
        self._actor_offsets.clear()
        self._actor_scene = result
        # **Und mit ihnen die gemerkten Farben.** Ein neuer Aktor kommt grau
        # aus der Geometrie; stünde hier noch der Stand von vorhin, hielte
        # `_apply_selection_colour` die Auswahl für unverändert und **liesse
        # den gewählten Körper grau** — die Auswahl verschwände beim
        # Neuzeichnen aus dem Bild, ohne dass sich an ihr etwas geändert hat.
        # Eine laufende Blende gehört ebenfalls zu Aktoren, die es nicht mehr
        # gibt.
        self._stop_selection_fade()
        self._shown_colours.clear()
        self._live_colours.clear()
        # **Mit den Aktoren geht auch ihr gemerkter Ausgangsort.** Die neuen
        # kommen aus der Geometrie und tragen keinen Zug mehr; ein
        # stehengebliebener Eintrag würde beim nächsten Ziehen als Basis
        # genommen (:meth:`continue_body_drag`, ``setdefault``) und den Körper
        # doppelt versetzen.
        self._actor_home.clear()
        for actor in self._edge_actors.values():
            self.renderer.remove(actor)
        self._edge_actors.clear()
        for actor in self._shadow_actors:
            self.renderer.remove(actor)
        self._shadow_actors.clear()
        self._shadow_owners.clear()
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
            self._edge_meshes = {
                object_id: entry
                for object_id, entry in self._edge_meshes.items()
                if object_id in result.scene.objects
            }
        else:
            self._shadow_splits.clear()
            self._edge_meshes.clear()
        self._shadow_cast = self._shadow_direction()
        self._uncapped = prepared.uncapped if prepared is not None else False
        if prepared is not None:
            self._display_cache.update(prepared.cached)
            while len(self._display_cache) > DISPLAY_CACHE_KEPT:
                self._display_cache.pop(next(iter(self._display_cache)))
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

        mode = DISPLAY_MODES[self._mode]
        opacity = float(mode["opacity"])
        if self._sketch_frame is not None:
            opacity = min(opacity, SKETCH_CONTEXT_OPACITY)
        for object_id, entry in result.scene.objects.items():
            if not self._in_view(object_id, entry):
                continue
            mesh = (
                prepared.meshes.get(object_id, entry.mesh)
                if prepared is not None
                else self._sectioned(
                    self._for_display(
                        object_id, entry.mesh, result.object_hashes.get(object_id, "")
                    )
                )
            )
            raw = getattr(mesh, "raw", None)
            if raw is None or not len(raw.faces):
                continue
            faces = np.asarray(raw.faces, dtype=np.int64)
            offset = np.asarray(self._view_offset(entry, result), dtype=float)
            local = np.asarray(raw.vertices, dtype=float)
            points = local + offset
            scalars = self._scalars_for(object_id, len(faces))
            cell_colours: CellColours | None = None
            if scalars is not None and self._map is not None:
                cell_colours = CellColours(
                    scalars,
                    colormap=tuple(VIRIDIS),
                    limits=(self._map.low, max(self._map.high, self._map.low + 1e-6)),
                    nan_colour="#4a4f57",
                )
            elif self._map is None:
                cell_colours = self._slot_colours(mesh, entry, len(faces))
            # Eingepasst wird ausdrücklich, in `_fit_once_for` — der Renderer
            # rührt die Kamera beim Einfügen nicht an.
            actor = self.renderer.add_surface(
                points,
                faces,
                name=f"object:{object_id}",
                style=SurfaceStyle(
                    colour=self._object_colour,
                    opacity=opacity,
                    wireframe=mode["style"] == "wireframe",
                    show_edges=bool(mode["show_edges"]),
                    smooth=self._shading == "smooth",
                    backface_colour=BACKFACE_COLOUR,
                    pickable=True,
                ),
                cell_colours=cell_colours,
            )
            self._actors[object_id] = actor
            self._actor_offsets[object_id] = offset.copy()
            # Nur unveränderte Topologie übernimmt Dreiecksnummern aus der
            # Szene. Schnitt- und LOD-Netze benutzen weiterhin den Ortsfang.
            if raw is getattr(entry.mesh, "raw", None):
                self._original_pick_cells.add(object_id)
            # ``mesh`` als Schlüssel, aus demselben Grund wie beim Schatten
            # eine Zeile tiefer: Die Felder entstehen in jeder Runde neu, das
            # Netz dahinter bleibt dasselbe, solange sich nichts geändert hat.
            self._draw_feature_edges(local, faces, offset, object_id, mesh)
            # ``mesh`` und nicht ``points``: Daran erkennt der Schatten, ob er
            # neu zerlegen muss.
            self._remember_shadow(points, mesh, object_id, mesh)

        # Erst jetzt: ein Schatten fällt auf die Fläche, auf der sein Körper
        # steht, und welche das ist, weiß nur die vollständige Szene.
        if self._sketch_frame is None:
            self._place_shadows(self._shadow_direction())
        # **Mit der ganzen Auswahl**, sonst räumt dieser Aufruf sie ab: Ohne
        # ``more`` setzt ``select`` das Feld unbedingt aus seinem Argument, und
        # der sorgfältige Beschnitt weiter oben wäre umsonst gewesen. Gemessen
        # am 04.09.2026 am echten Fenster — zwei gewählte Körper, nach der
        # nächsten Auswertung noch einer gefärbt, und ``_selected_bounds``
        # rahmte wieder einen einzigen.
        self.select(self._selected, more=self._selected_more)
        self._redraw_features()
        self._redraw_layer()
        # **Und alles andere, was durch ``_view_offset`` geht.** Dessen
        # Docstring zählt auf, wer mitwandert: Merkmalsfläche, Beschriftung,
        # Griffscheibe, Differenzvorschau, Maße und Fangmarke. Die Rechnung
        # war gepflegt, die Liste derer, die sie **auslösen**, nicht — hier
        # standen nur die ersten beiden. Ein Maß an einem Körper auf Platte 2
        # blieb beim Umschalten auf „Alle Platten" eine Bettbreite neben
        # seinem Teil stehen; genau der Fehler, den der Kommentar an
        # :meth:`_redraw_measurements` als behoben beschreibt. Behoben war die
        # Rechnung, nicht ihr Auslöser. Beide räumen selbst ab und kehren bei
        # leerem Zustand zurück, kosten hier also nichts.
        self._redraw_measurements()
        self._redraw_difference()
        # Ob ein Körper unter der Platte liegt, entscheidet sich mit jeder
        # Auswertung neu — und die Platte steht schon, seit der Drucker
        # gewählt wurde.
        self._apply_bed_transparency()
        if restore_finding:
            self._draw_finding_mark()
        self._render_now()

    def _aim_rotation(self) -> None:
        """Der Drehpunkt bekommt beim Drehbeginn die Tiefe dessen, was man ansieht (§2.9).

        Der Drehteller des Navigators dreht um den Fokuspunkt der Kamera
        (``CameraPose.focal_point``), wie VTK es tat. Der wurde früher bei jedem
        Szenenaufbau auf die Mitte der Körper gesetzt (``_centre_rotation``),
        und die Kamera rückte mit — nach einem Verschieben sprang damit das
        Bild (Robert, 23.08.2026: „nach jedem verschieben springt die kamera
        und das modell immer komisch"). Die Notlösung ließ den Fokus nach
        einem reinen Verschieben stehen, und ihr Preis war benannt: Gedreht
        wurde um den alten Punkt, bis zum nächsten echten Szenenwechsel.

        Deshalb jetzt hier, im Beginn der Drehung — dem einzigen Moment, in
        dem der Fokuspunkt etwas bedeutet. Und unsichtbar: Der Fokus rückt auf
        einen Punkt des Sichtstrahls (:func:`rotation_focus`). Stellung und
        Blickrichtung der Kamera bleiben unangetastet, das Bild ändert sich um
        nichts; nur die Tiefe des Drehpunkts stimmt wieder. Seitlich bleibt er
        in der Bildmitte: Gedreht wird um das, was man ansieht — nicht um einen
        Punkt daneben, dessen Anfahren mitten in der Geste einen Sprung ins
        Bild brächte.

        **Welche Tiefe, entscheidet die Bildmitte** (Robert, 04.09.2026: „beim
        rotieren der ansicht wollen wir uns um den mittelpunkt des viewports
        drehen"). Liegt dort ein Körper, ist sein Auftreffpunkt der Drehpunkt
        (:meth:`centre_hit`) — wer auf ein Detail zoomt, dreht um dieses Detail
        und nicht um eine Tiefe, die eine halbe Bauhöhe dahinterliegt. Zeigt
        die Mitte auf den Hintergrund, gilt weiter die Mitte der Körper
        (:meth:`rotation_centre`), auf den Sichtstrahl projiziert; dasselbe
        gilt, wo der Zell-Picker nichts findet, weil der Strahl senkrecht in
        eine Bohrung läuft (siehe :meth:`_world_at`).

        Den Fall »Kulisse statt Körper« — Bauraumrahmen 250 mm, Teil 40, die
        Mitte alles Sichtbaren hundert Millimeter über dem Modell — schließen
        beide Quellen auf dieselbe Weise aus: Der Picker sucht nur unter den
        Körperaktoren, und die Mitte kommt aus den Körpern, nie aus dem
        Renderer.
        """
        if self.renderer is None:
            return
        centre = self.centre_hit()
        if centre is None:
            centre = self.rotation_centre()
        if centre is None:
            return
        pose = self.renderer.camera_pose()
        target = rotation_focus(pose.position, pose.focal_point, centre)
        if target is None:
            return
        self.renderer.set_camera_pose(CameraPose(pose.position, target, pose.view_up))
        self.renderer.reset_clipping_range()

    def centre_hit(self) -> Vec3 | None:
        """Der Körperpunkt in der Bildmitte — oder nichts, wo keiner liegt.

        Die erste Quelle des Drehpunkts (:meth:`_aim_rotation`). Gefragt wird
        derselbe Zell-Picker wie bei jedem Klick (:meth:`_world_at`), und der
        sucht nur unter den Körperaktoren: Druckplatte, Bauraum, Griffe und
        Schatten können den Drehpunkt also nicht an sich ziehen.

        **Gezählt wird, wie der Vertrag zählt**: ``view_size`` gibt
        Gerätepixel, und ``pick_surface`` nimmt sie von oben links wie Qt —
        dieselbe Zählung wie bei jedem Klick. (Unter VTK, bis 05.09.2026,
        zählte der Picker Y von unten, und die Mitte war der eine Punkt, der in
        beiden Zählungen dieselbe Zeile ist.) Die Größe kommt vom Renderer —
        seine Bildpunkte zählen in seiner Grafikfläche, nicht im Viewport.

        Vor dem ersten Bild hat der Renderer keine Ausdehnung; dann gibt es
        keine Mitte, und der Aufrufer nimmt seinen anderen Weg.
        """
        if self.renderer is None:
            return None
        width, height = self.renderer.view_size()
        if width < 1 or height < 1:
            return None
        return self._world_at(width // 2, height // 2)

    def rotation_centre(self) -> Vec3 | None:
        """Der Punkt, um den gedreht wird — die Mitte der Körper, oder nichts.

        Der Rückfall hinter :meth:`centre_hit`: Was die Bildmitte nicht
        beantwortet, beantwortet die Ausdehnung der Körper.

        Als eigene Auskunft, damit die Regel ohne Renderer prüfbar bleibt:
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
        if self.renderer is None:
            return
        self.renderer.reset_clipping_range()
        self._draw()

    def _draw(self) -> None:
        """Die eine Stelle, an der die Ansicht neu gezeichnet wird.

        Alles, was etwas geändert hat, geht hier durch — ein Weg statt
        sechzehn. Gezeichnet wird einmal; wenn ein einziger Durchgang nicht
        ankommt, ist das ein Fehler weiter unten und wird dort behoben, nicht
        hier durch Wiederholen verdeckt.
        """
        if self.renderer is None:
            return
        # **Vor jedem Bild, nicht bei jedem Anlass.** Die Tiefenordnung hängt
        # an der Kamera, und die ändert sich an einem Dutzend Stellen —
        # ``view_from``, Radzoom, Zugende, 3D-Maus, Skizzenkamera. Wer sie
        # dort einzeln nachzöge, vergäße eine; hier kommt jede vorbei.
        # ``_order_by_depth`` merkt sich die letzte Lage und tut nichts, wenn
        # sich nichts geändert hat.
        self._order_by_depth()
        self._layout_feature_labels()
        self.renderer.render()

    def _slot_colours(self, mesh: Any, entry: Any, face_count: int) -> CellColours | None:
        """Die Zellfarben eines Körpers — aus seinen Materialslots oder aus der
        Datei, aus der er kam; ``None`` heißt Körperfarbe.

        Ein Slot ohne eigene Farbe bekommt eine aus der Ersatzpalette
        (``theme.slot_colour``): Der Pinsel legt Slots mit ``colour=None`` an,
        und mit der Körperfarbe an dieser Stelle war das Bemalen im Bild
        folgenlos — zwei Striche in zwei Slots sahen aus wie keiner. Ein
        einziger Slot ist kein Mehrfarbdruck, sondern die Vorgabe.
        """
        slots = getattr(entry, "material_slots", None)
        indices = getattr(mesh, "slots", ())
        import numpy as np

        if not slots or len(indices) != face_count:
            colours = source_colours(mesh, face_count)
            if colours is None:
                return None
            return CellColours(np.asarray(colours, dtype=float) / 255.0)

        known = {slot.index: slot for slot in slots}
        highest = max(known)
        table: list[str] = []
        for index in range(highest + 1):
            slot = known.get(index)
            colour = slot.colour if slot is not None else None
            if colour is not None:
                table.append(_hex(colour))
                continue
            table.append(slot_colour(index) or self._object_colour)
        if len(table) < 2:
            return None
        return CellColours(
            np.asarray(indices, dtype=np.int32),
            colormap=tuple(table),
            limits=(0.0, float(highest)),
            categorical=True,
        )

    def _feature_edges_for(
        self, object_id: ObjectId, vertices: Any, faces: Any, source: Any
    ) -> Any:
        """Die Körperkanten eines Netzes — aus dem Cache, solange es dasselbe ist.

        Dieselbe Bauart wie ``_shadow_hulls_for``, aus demselben Grund: Die
        Kantensuche kostete an einem Kundenmodell mit 32 Körpern 453 ms bei
        jedem Aufbau, und ``show_scene`` läuft bei jeder Auswahl, jedem
        Themenwechsel und jedem Schieberschritt. Verglichen wird die Identität
        des Netzes; der Schnittschieber trifft den Cache absichtlich nicht.

        **In Körperkoordinaten, ohne den Versatz der Ansicht.** Der Cache
        überlebt einen Wechsel der Platte oder der Explosion, und ein
        gemerkter Versatz stünde danach falsch; der Versatz kommt beim
        Zeichnen dazu.
        """
        cached = self._edge_meshes.get(object_id)
        if cached is not None and source is not None and cached[0] is source:
            return cached[1]
        try:
            edges = feature_edges(vertices, faces, FEATURE_EDGE_ANGLE)
        except Exception as problem:  # pragma: no cover - hängt an der Geometrie
            _log.info("feature edges unavailable: %s", problem)
            return None
        if source is not None:
            self._edge_meshes[object_id] = (source, edges)
        return edges

    def _draw_feature_edges(
        self, vertices: Any, faces: Any, offset: Any, object_id: ObjectId, source: Any = None
    ) -> None:
        """Die Kanten eines Körpers als Linien über die Flächen — nur in ``solid``.

        Ab :data:`FEATURE_EDGE_LIMIT` Dreiecken gibt es keine: Die Suche läuft
        linear, und Netze dieser Größe sind Scans oder erzeugte Körper, die
        bei dreißig Grad ohnehin fast keine Kanten haben.
        """
        if self.renderer is None or self._mode != "solid":
            return
        if len(faces) > FEATURE_EDGE_LIMIT:
            return
        edges = self._feature_edges_for(object_id, vertices, faces, source)
        if edges is None or len(edges) == 0:
            return
        self._edge_actors[object_id] = self.renderer.add_lines(
            edges + offset,
            name=f"edges:{object_id}",
            colour=self._edge_colour,
            width=float(FEATURE_EDGE_WIDTH),
        )

    def _sync_edge_preview(self, object_id: ObjectId, matrix: Any = None) -> bool:
        """Getrennte Konturen übernehmen nur geänderte Vorschauwerte ihres Körpers."""
        import numpy as np

        edge = self._edge_actors.get(object_id)
        actor = self._actors.get(object_id)
        if edge is None or actor is None:
            return False
        applied = actor.matrix() if matrix is None else matrix
        position = actor.position()
        if np.array_equal(edge.matrix(), applied) and edge.position() == position:
            return False
        # Die Linien tragen bereits denselben Platten-/Explosionsversatz wie
        # der Körper. Nur seine Vorschau folgt; die Originalpunkte bleiben fest.
        edge.set_matrix(applied)
        edge.set_position(position)
        return True

    def _remember_shadow(
        self, points: Any, mesh: Any, object_id: ObjectId, source: Any = None
    ) -> None:
        """Die Hüllen eines Körpers für den Schattenwurf merken (§18.6).

        Gezeichnet wird erst, wenn die ganze Szene steht (``_place_shadows``):
        Ein Schatten fällt auf die Fläche, auf der sein Körper steht, und
        welche das ist, weiß nur die vollständige Szene.
        """
        if self.renderer is None or not self.contact_shadows:
            return
        hulls = self._shadow_hulls_for(object_id, points, mesh, source)
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
        stacked = np.vstack([np.asarray(hull, dtype=float) for hull in usable])
        self._shadow_ground[object_id] = (
            float(stacked[:, 2].min()),
            float(stacked[:, 2].max()),
            outline_of(stacked),
        )

    def _place_shadows(self, direction: tuple[float, float]) -> None:
        """Die Schatten aller Körper aus den gemerkten Hüllen setzen."""
        if self.renderer is None:
            return
        for object_id, hulls in self._shadow_hulls.items():
            for part, hull in enumerate(hulls):
                for index, (ground, window) in enumerate(self._shadow_catchers(object_id)):
                    outline = self._shadow_outline_of(hull, direction, ground, window)
                    if outline is None:
                        continue
                    vertices, faces = shapes.polygon(outline)
                    actor = self.renderer.add_surface(
                        vertices,
                        faces,
                        # Der Name trägt auch das Stück: Zwei Schatten desselben
                        # Körpers auf derselben Fläche hießen sonst gleich.
                        name=f"shadow:{object_id}:{part}:{index}",
                        style=SurfaceStyle(
                            colour=SHADOW_COLOUR,
                            opacity=self._shadow_opacity,
                            lighting=False,
                            pickable=False,
                        ),
                    )
                    self._shadow_actors.append(actor)
                    self._shadow_owners.setdefault(object_id, []).append(actor)

    def _redraw_shadows(self, *, draw: bool = True) -> None:
        """Die Schatten der neuen Kamerastellung anpassen (§18.6).

        Am Ende einer Drehung, nicht während ihr: die Hüllen liegen bereit, die
        Projektion darüber kostet Bruchteile einer Millisekunde — aber sie je
        Bild zu rechnen wäre Arbeit für eine Zwischenstellung, die niemand
        ansieht.
        """
        # Läuft eine Analysekarte, steht hier ohnehin nichts: `_draw_shadow`
        # legt dann keine Hülle ab, und `show_scene` räumt die alten weg.
        if self._sketch_frame is not None or self.renderer is None or not self._shadow_hulls:
            return
        direction = self._shadow_direction()
        if math.dist(self._shadow_cast, direction) < EPS_GEOM:
            return
        self._shadow_cast = direction
        for actor in self._shadow_actors:
            self.renderer.remove(actor)
        self._shadow_actors.clear()
        self._shadow_owners.clear()
        self._place_shadows(direction)
        if draw:
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
        self.show_scene(self._scene_for_rebuild())

    # **Jeder Ansichts-Setter prüft auf Änderung, und das ist keine Feinarbeit.**
    # Gemessen am 03.09.2026 an ``aushoehlen-und-teilen.p3d``, Zähler um
    # ``show_scene`` und alle acht Setter: **sieben von acht Szenenaufbauten in
    # vier gewöhnlichen Handlungen waren unnötig** — ein Klick auf einen Körper
    # baute die ganze Szene neu, ein Themenwechsel dreimal, dasselbe Thema noch
    # einmal ein viertes Mal. An einem Kundenmodell (``chufang.3mf``, 32 Körper)
    # kostet ein Aufbau **0,74 s**; ein Klick also drei Viertel Sekunden für
    # nichts.
    #
    # Sichtbar wurde es an einer anderen Stelle: Nach einem Zug am Griff sprang
    # der Körper an die alte Stelle zurück, bevor er an der neuen landete
    # (Robert, 03.09.2026). Der Grund war ``set_analysis_map(None, None)``,
    # dreimal gerufen, während das Ergebnis der Operation schon vorlag — jeder
    # dieser Aufbauten nahm dem Actor seine Vorschau-Matrix, und für 491 ms
    # stand das Teil dort, wo es hergekommen war.
    #
    # ``set_hidden`` darüber hatte die Prüfung seit je. Die anderen sechs nicht.

    @property
    def hidden(self) -> frozenset[ObjectId]:
        return self._hidden

    def set_plate(self, plate: int) -> None:
        """Zeigt eine Druckplatte, oder alle (§25).

        Ein Filter auf dem Bild, nicht auf der Szene: die Objekte der anderen
        Platten sind weiter da, werden weiter exportiert und stehen weiter im
        Prüfbericht.
        """
        if plate == self._plate:
            return
        self._plate = plate
        # Eine einzelne Platte heißt ein Bett; „Alle" heißt so viele, wie die
        # Szene belegt. ``show_scene`` zieht die Kulisse nach, sobald sich die
        # Zahl ändert — und ``_plate`` ist gesetzt, bevor sie gezählt wird.
        self.show_scene(self._scene_for_rebuild())

    def set_explosion(self, factor: float) -> None:
        """Zeichnet die Teile auseinander, um eine Teilung anzusehen (§18.8).

        Bewegt wird nichts: der Versatz kommt auf dem Weg in die Ansicht zu den
        Punkten hinzu und erreicht das Netz nie. Ein auseinandergezogenes Teil
        ist immer noch dort, wo der Stapel es sagt, und der Export sagt das
        auch.
        """
        # Verglichen wird der normalisierte Wert: Wer zweimal -1 schickt, meint
        # zweimal null, und das ist keine Änderung.
        wanted = max(0.0, factor)
        if wanted == self._explosion:
            return
        self._explosion = wanted
        self.show_scene(self._scene_for_rebuild())

    def _view_offset(self, entry: Any, result: EvaluationResult) -> Any:
        """Alles, was einen Körper in der Ansicht von seinem Ort in der Szene
        wegrückt: das Auseinanderziehen (§18.8) und die Platte (§25).

        An einer Stelle zusammengefasst, damit jede Zeichenstelle beides
        bekommt oder keines. Merkmalsfläche, Merkmalsbeschriftung, Griffscheibe,
        Differenzvorschau, Maße und die Fangmarke gehen mit; was **nicht**
        mitgeht, ist die Schnittebene.

        **Ein Ort braucht dafür seinen Körper**, und den kennt nicht jeder
        Aufrufer. Ein Maß trägt ihn seit dem 03.09.2026 selbst
        (`Measurement.object_ids`, je Punkt einer), gefragt beim Klick über
        :meth:`_object_at_view` — in der Szene liegen zwei Platten
        übereinander, und von dort aus ist die Frage nicht zu beantworten.
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

    def _shown_offset(self, entry: Any, result: EvaluationResult) -> Any:
        """Den Versatz des sichtbaren Aktors lesen, auch während ein neues Bild rechnet."""
        if result is self._result and entry.id in self._actor_offsets:
            return self._actor_offsets[entry.id]
        return self._view_offset(entry, result)

    def _in_pick_view(self, object_id: ObjectId, entry: Any) -> bool:
        """Das letzte aufgebaute Bild bleibt maßgeblich, auch nach einem Arbeiterfehler."""
        if self._actor_scene is not None and self._actor_scene is self._result:
            actor = self._actors.get(object_id)
            return actor is not None and actor.visible()
        return self._in_view(object_id, entry)

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
        hit = self._hit_at(point, view_space=True)
        if hit is not None:
            return hit.scene_point
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

        # Die Mitte der Szene einmal je Auswertung, nicht einmal je Körper:
        # mit n Körpern waren das n Durchläufe über alle n Mittelpunkte.
        cached = self._explosion_middle
        if cached is None or cached[0] != id(result):
            centres = [
                np.asarray(other.mesh.bounds.centre, dtype=float)
                for other in result.scene.objects.values()
                if getattr(other.mesh, "raw", None) is not None
            ]
            cached = (id(result), np.mean(centres, axis=0) if len(centres) >= 2 else None)
            self._explosion_middle = cached
        middle = cached[1]
        if middle is None:
            return np.zeros(3)
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

    def _for_display(self, object_id: ObjectId, mesh: Any, identity: str = "") -> Any:
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

        key = _display_key(object_id, mesh, identity)
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

    def _section_planes(self) -> tuple[SectionPlane | None, SectionPlane | None]:
        """Dieselben sichtbaren Halbräume für Körper und Merkmalsmarkierungen."""
        plane = self._section
        if plane is None and self._layer is not None:
            plane = SectionPlane(normal=(0.0, 0.0, 1.0), position=self._layer.z)
        second = None
        if self._section is not None and self._slice_thickness is not None:
            offset = self._section.position - self._slice_thickness
            second = SectionPlane(normal=self._section.normal, position=offset).flipped()
        return plane, second

    def _sectioned(self, mesh: Any) -> Any:
        """Wendet die Schnittebene an. Schneiden ist Geometrie, also tut es der
        Kern (§18.2).

        Die Schichtanalyse schneidet mit: „Durch die Höhe fahren und den
        Querschnitt ansehen" versprach der Text, und das Modell blieb dabei
        undurchsichtig stehen — sichtbar war nur eine dünne Kontur darunter.
        Wer eine Schicht gewählt hat, will sehen, was auf dieser Höhe steht,
        nicht was darüber liegt.
        """
        plane, second = self._section_planes()
        if plane is None:
            return mesh
        # **Ein B-Rep-Körper wird vorher vernetzt.** ``cut`` arbeitet auf
        # ``MeshData``: Es liest ``mesh.slots`` und setzt das Ergebnis über
        # ``replacing`` ein. Ein ``Solid`` hat weder das eine (er führt
        # ``slot_indices``) noch nimmt sein ``replacing`` ein Netz — es
        # erwartet eine OCC-Form. Der Schnitt warf deshalb
        # ``AttributeError: 'Solid' object has no attribute 'slots'``, der
        # Aufbau der Ansicht brach mittendrin ab, und der Kunde sah eine
        # **leere Bühne** statt seines Modells (gemeldet von Robert,
        # 03.09.2026, am eigenen Teil mit „weiter bearbeitbar").
        #
        # Vernetzt wird hier und nicht im Kern: Ein geschnittener Körper ist
        # eine Ansichtssache und kein bearbeitbarer Stand — die Einbahntür aus
        # §30 wird also nur für das Bild durchschritten, das Dokument behält
        # seine exakte Form.
        to_mesh = getattr(mesh, "to_mesh", None)
        if callable(to_mesh):
            mesh = to_mesh()
        result = cut(mesh, plane, second)
        self._uncapped = self._uncapped or not result.capped
        return result.mesh

    def select(self, object_id: ObjectId | None, *, more: Sequence[ObjectId] = ()) -> None:
        """Hebt ein Objekt hervor — Farbe plus Statusleiste, nie Farbe
        allein (§19.1).

        ``more`` sind die **weiteren** gewählten Körper. Sie tragen dieselbe
        Auswahlfarbe, hängen aber nichts an sich: Der Griff bleibt am
        führenden ``object_id``. Wer sie wegläßt, wählt einen — der Aufruf
        ändert sich für niemanden, der bisher einen übergab.

        **Warum das überhaupt nötig ist:** ``inputs_for_transform`` gab schon
        immer die ganze Auswahl weiter, ein Zug bewegte also beide Körper.
        Gefärbt war einer. Das Bild widersprach damit dem, was der Zug tat,
        und die Statuszeile hatte recht — gemessen 3d-druck-85, abgegeben von
        3d-druck-d4 am 03.09.2026.
        """
        requested = (object_id, *more)
        dropped_refs = bool(self._selected_feature_refs) and (
            object_id != self._selected
            or any(owner not in requested for owner, _feature_id in self._selected_feature_refs)
        )
        if dropped_refs:
            self._remember_feature_refs(())
        self._selected = object_id
        # Der führende Körper steht nicht zweimal in der Auswahl: Sonst zählt
        # ``highlighted_objects`` ihn doppelt, und ein Vergleich auf Gleichheit
        # gegen den Objektbaum schlägt fehl, ohne dass etwas fehlt.
        #
        # **Gegen die Aktoren zu filtern wäre hier falsch.** Ohne Renderer ist
        # ``_actors`` leer, und die Auswahl käme offscreen nie an — eine
        # Bedingung, die genau dort nicht greift, wo geprüft wird. Ob es einen
        # Körper noch gibt, entscheidet die Auswertung in ``show_scene``; dort
        # ist die Szene bekannt und der Renderer unerheblich.
        self._selected_more = tuple(dict.fromkeys(o for o in more if o != object_id))
        if self.renderer is None:
            return
        if dropped_refs:
            self._redraw_features()
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
        if self.renderer is None:
            return
        highlighted = () if self._sketch_frame is not None else self.highlighted_objects()
        wanted = {
            identifier: SELECTED_COLOUR if identifier in highlighted else self._object_colour
            for identifier in self._actors
            # Eine Karte besitzt die Farbe ihres Körpers; die Auswahl zeigt sich
            # stattdessen im Objektbaum und in der Statusleiste (§19.1).
            if not (self._map is not None and identifier == self._map_object)
        }
        changed = {
            identifier: colour
            for identifier, colour in wanted.items()
            if self._shown_colours.get(identifier) != colour
        }
        self._shown_colours = wanted
        if not changed:
            return
        self._fade_selection(changed)

    def _fade_selection(self, changed: dict[ObjectId, str]) -> None:
        """Blendet die Auswahl über, statt sie umzuschalten.

        **Warum überhaupt:** „vom aussehen noch anschaulicher, bzw
        natürlicher" (Robert, 03.09.2026). Im 3D-Fenster gab es bis heute
        keinen einzigen Übergang — die Auswahl war ein Sprung der Aktorfarbe,
        und ein Sprung zwingt das Auge, die Szene neu zu lesen. Eine kurze
        Blende sagt „dasselbe Teil, anderer Zustand".

        **Und beide Seiten zugleich**: Der alte Körper geht auf Grau zurück,
        während der neue die Auswahlfarbe annimmt. Sie nacheinander zu
        schalten sähe aus wie zwei Handlungen.

        Die Dauer ist gemessen und nicht geraten. Ein ``render()`` kostet in
        diesem Fenster **8,2 ms** — und zwar bei 32 328 wie bei 1 803 243
        Dreiecken, weil es an der Bildwiederholung hängt und nicht an der
        Geometrie. Sieben Bilder in :data:`ACCENT_MS` sind damit 58 ms
        Rechenzeit; der Farbwechsel selbst liegt bei 0,03 ms und fällt
        daneben nicht auf.

        **Ist Bewegung abgeschaltet, steht die Zielfarbe sofort** — darum
        kümmert sich ``tween`` selbst, und deshalb ist diese Funktion auch der
        einzige Weg, an dem die Auswahlfarbe gesetzt wird. Ein zweiter Weg
        „für den Fall, dass" wäre die Stelle, an der die beiden auseinander
        laufen.
        """
        if self.renderer is None:
            return
        # Eine noch laufende Blende gehört zu einer Auswahl, die es nicht mehr
        # gibt. Liefe sie weiter, schriebe sie ihre alten Farben über die neuen.
        self._stop_selection_fade()
        # **Die Startfarbe kommt aus dem eigenen Gedächtnis, nicht vom Aktor.**
        # Mitten in einer abgelösten Blende stünde dort ein Zwischenwert,
        # dessen Herkunft niemand kennt. Was `_live_colours` sagt, hat diese
        # Funktion selbst geschrieben. (Bis zum 05.09.2026 kam ein zweiter
        # Grund dazu: Die Attrappen der Prüfstände zeichneten Zuweisungen an
        # VTKs Eigenschaftsobjekt nur auf und gaben nichts zurück.)
        grey = rgb_of(self._object_colour)
        starts = {identifier: self._live_colours.get(identifier, grey) for identifier in changed}
        ends = {identifier: rgb_of(colour) for identifier, colour in changed.items()}
        # **Gezeichnet wird nur, wenn sich auch etwas bewegt.** Ohne Bewegung
        # ruft ``tween`` einmal mit 1,0, und der Aufrufer zeichnet danach
        # ohnehin (``select`` endet auf ``_draw``). Ein ``render`` hier wäre
        # dann ein zweites Bild je Auswahl — in der Suite hunderte, und die
        # Datei riss beim Aufräumen. Ein Bild, das niemand sieht, ist keine
        # Vorsicht, sondern Arbeit.
        moving = animations_enabled()

        def step(fraction: float) -> None:
            renderer = self.renderer
            if renderer is None:
                return
            for identifier, start in starts.items():
                actor = self._actors.get(identifier)
                if actor is None:
                    continue
                blend = mix(start, ends[identifier], fraction)
                actor.set_colour(hex_of(blend))
                self._live_colours[identifier] = blend
            if moving:
                renderer.render()

        # **Die Referenz fällt mit der Animation.** ``tween`` startet mit
        # ``DeleteWhenStopped``: Nach dem letzten Bild ist das C++-Objekt weg,
        # und ein ``stop()`` darauf wirft ``Internal C++ object already
        # deleted``. Offscreen läuft nie eine Animation, also hat die ganze
        # Suite das nie gesehen — gefunden am laufenden Fenster, beim zweiten
        # Auswahlwechsel.
        self._selection_fade = tween(
            self, on_step=step, duration=ACCENT_MS, on_done=self._forget_selection_fade
        )

    def _forget_selection_fade(self) -> None:
        """Die Blende ist fertig — ihre Hülle ist gleich weg, die Referenz auch."""
        self._selection_fade = None

    def _stop_selection_fade(self) -> None:
        """Hält eine laufende Blende an, wenn es noch eine gibt.

        Zwei Fälle, und der zweite ist der, der geknallt hat: Läuft sie noch,
        wird sie gestoppt; ist sie natürlich zu Ende gegangen, hat
        :meth:`_forget_selection_fade` die Referenz schon geräumt. Die
        Gültigkeitsprüfung bleibt trotzdem stehen, denn ein Abbruch zwischen
        beiden Ereignissen ist nicht ausgeschlossen — und sie kostet nichts.
        """
        fade = self._selection_fade
        self._selection_fade = None
        if fade is None:
            return
        from shiboken6 import isValid

        if isValid(fade):
            fade.stop()

    def show_build_volume(self, profile: Profile) -> None:
        """Das Bett als Raster in echter Größe, der Bauraum als Eckwinkel
        (§18.6) — **je Platte eines** (§25).

        **Kein Aufruf hier setzt die Kamera.** Der Bauraum ist Kulisse. PyVista
        (bis 05.09.2026) passte bei der ersten Netzfläche einer leeren Szene
        von selbst ein und machte damit jedes Einpassen auf die Körper
        zunichte, weil die Kulisse danach gezeichnet wurde; der eigene Renderer
        passt nie von selbst ein, und die Regel bleibt, weil sie ihren Anlass
        überlebt: Kulisse stellt keine Kamera.

        **Warum mehrere Betten.** Jede Platte hat ihren eigenen Nullpunkt, und
        die Anordnung setzt Platte 2 an denselben Ort wie Platte 1. Ein Bett
        für alle heißt darum: die Teile stehen ineinander, und wer zwei Platten
        angelegt hat, sieht eine. Gemeldet als „bei Projekten mit mehreren
        Platten sehe ich trotzdem nur eine" — und es war genau das.
        """
        width, depth, height = profile.printer.build_volume
        # Gemerkt, weil der Kontaktschatten an dieser Kante geschnitten wird —
        # und weil ``_fit_once_for`` daran erkennt, ob es auf einer leeren Szene
        # überhaupt etwas einzupassen gibt. Vor dem Renderer-Zweig, aus demselben
        # Grund wie dort: dass ein Bauraum gilt, ist eine Aussage über die
        # Szene und nicht über den Renderer.
        self._bed_extent = (width, depth)
        self._build_volume = (width, depth, height)
        self._profile = profile
        # Die Zahl **vor** dem Renderer-Zweig, damit ``_plate_offset`` offscreen
        # dasselbe sagt wie im Bild: sonst hinge die Verschiebung am Renderer,
        # und kein Test käme an sie heran.
        beds = self._beds_for_view()
        self._beds_drawn = beds
        if self.renderer is None:
            return
        for actor in self._frame_actors:
            self.renderer.remove(actor)
        self._frame_actors.clear()
        self._ground_actors.clear()
        self._bed_surfaces.clear()
        for plate in range(beds):
            self._draw_one_bed(plate, plate_shift(plate, width)[0], width, depth, height)
        # Der Zustand entscheidet, nicht die Aufruf-Reihenfolge: Während des
        # Zeichnens tritt der Boden ab (siehe ``set_sketching``), und ein hier
        # frisch gebautes Bett hat sich daran zu halten — sonst liegen Bett-
        # und Zeichenraster wieder übereinander, sobald eine Platte dazukommt.
        if self._sketch_frame is not None:
            for actor in self._ground_actors:
                actor.set_visible(False)
        if not self._bed_visible:
            for actor in self._frame_actors:
                actor.set_visible(False)
        self._apply_bed_transparency()
        self._draw()

    @property
    def bed_visible(self) -> bool:
        """Ob Bett, Bauraum und Maßstab gerade gezeichnet werden."""
        return self._bed_visible

    def set_bed_visible(self, visible: bool) -> None:
        """Bett, Bauraum und Maßstab ein- oder ausblenden — die Körper bleiben.

        Ein Umschalter, kein Umbau: Die Kulisse wird weiter gezeichnet und
        nur unsichtbar geschaltet, damit :meth:`show_build_volume` beim
        nächsten Profilwechsel nichts anders machen muss. Im Zeichenmodus
        bleibt der Boden ohnehin weg.
        """
        self._bed_visible = bool(visible)
        if self.renderer is None:
            return
        for actor in self._frame_actors:
            hidden_by_sketch = self._sketch_frame is not None and actor in self._ground_actors
            actor.set_visible(self._bed_visible and not hidden_by_sketch)
        self._draw()

    def _draw_one_bed(
        self,
        plate: int,
        shift: float,
        width: float,
        depth: float,
        height: float,
    ) -> None:
        """Ein Bett zeichnen: Grundfläche, Raster, Bauraumkanten, Maßskala.

        Je Platte eines, um ``shift`` nach +X gerückt (§25); die Namen tragen
        die Plattennummer, damit vier Betten vier Aktoren sind.
        """
        if self.renderer is None:
            return

        import numpy as np

        # Ein gefüllter Grund unter dem Raster. Bis hierhin war die Platte ein
        # Drahtgitter über dem Hintergrund — hübsch, aber ohne Fläche: ein
        # Schatten darauf fiel auf nichts und war im Bild schlicht nicht da.
        # Knapp unter null, damit er nicht mit dem Raster um dieselbe Tiefe
        # streitet.
        #
        # **Von unten schaut man hindurch** (Robert, 23.08.2026): Wer eine
        # Unterseite bearbeitet, dreht die Ansicht unter das Teil — und sah
        # dort die Platte statt des Teils. ``cull_backfaces`` und nicht
        # ``opacity``: Die Fläche gibt es, damit ein Schatten auf etwas fällt,
        # und eine durchscheinende Platte nähme ihm den Grund. Die Ebene zeigt
        # nach oben; von unten sieht man ihre **Rückseite**, und die lässt
        # sich wegwerfen, ohne die Vorderseite anzufassen. Gemessen von
        # 3d-druck-3a an einem roten Körper über grauer Platte, in Bildpunkten
        # gezählt:
        #
        #     ohne culling   von unten:    0 rot   von oben: 4014
        #     culling back   von unten: 2417 rot   von oben: 4014
        vertices, faces = shapes.plane((shift, 0.0, -BED_SURFACE_DROP), width, depth)
        surface = self.renderer.add_surface(
            vertices,
            faces,
            name=f"bed_surface_{plate}",
            style=SurfaceStyle(
                colour=self._bed_surface,
                ambient=0.45,
                diffuse=0.55,
                specular=0.0,
                pickable=False,
                cull_backfaces=True,
            ),
        )
        self._bed_surfaces.append(surface)
        self._frame_actors.append(surface)
        self._ground_actors.append(surface)
        grid_points, grid_spans = shapes.grid_lines((shift, 0.0, 0.0), width, depth, 10.0)
        grid = self.renderer.add_lines(
            grid_points,
            name=f"bed_{plate}",
            colour=self._bed_colour,
            width=1.0,
            polylines=grid_spans,
        )
        grid.set_opacity(0.35)
        self._frame_actors.append(grid)
        self._ground_actors.append(grid)

        segments = volume_edges(width, depth, height)
        points = np.asarray([point for pair in segments for point in pair], dtype=float)
        points[:, 0] += shift
        volume = self.renderer.add_lines(
            points, name=f"build_volume_{plate}", colour=self._bed_colour, width=1.0
        )
        volume.set_opacity(0.35)
        self._frame_actors.append(volume)

        marks = bed_scale(width, depth)
        anchors = np.asarray([point for point, _text in marks], dtype=float)
        anchors[:, 0] += shift
        self._frame_actors.append(
            self.renderer.add_labels(
                anchors,
                [text for _point, text in marks],
                name=f"bed_scale_{plate}",
                style=LabelStyle(text_colour=self._bed_colour, font_size=9, always_visible=True),
            )
        )

    # --- theme (§19.3) ----------------------------------------------------------

    def set_theme(self, theme: str) -> None:
        """Hintergrund-, Körper- und Bettfarben folgen dem Anwendungsthema.

        **Die Prüfung steht ganz vorn**, also vor dem Umfärben der Leisten und
        vor der Achsenanzeige: Ändert sich das Thema nicht, ändert sich an
        keiner der Farben etwas, und jede Zeile darunter wäre Arbeit für
        dasselbe Bild. Der teuerste Teil ist der Szenenaufbau am Ende —
        gemessen 0,74 s an einem Kundenmodell mit 32 Körpern.
        """
        if theme == self._theme:
            return
        self._theme = theme
        colours = viewport_colours(theme)  # type: ignore[arg-type]
        self._object_colour = colours["object"]
        self._bed_colour = colours["bed"]
        self._bed_surface = colours["bed_surface"]
        self._shadow_opacity = SHADOW_OPACITY["light" if theme == "light" else "dark"]
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
        if self.renderer is None:
            return
        self.renderer.set_background(colours["bottom"], top=colours["top"])
        self._light_the_body(theme)
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
        self.show_scene(self._scene_for_rebuild())

    # --- display (§18.1) --------------------------------------------------------

    def set_display_mode(self, mode: DisplayMode) -> None:
        """Voll, voll mit Kanten, Drahtgitter oder durchsichtig."""
        if mode == self._mode:
            return
        self._mode = mode
        self.show_scene(self._scene_for_rebuild())

    def set_shading(self, shading: Shading) -> None:
        if shading == self._shading:
            return
        self._shading = shading
        self.show_scene(self._scene_for_rebuild())

    def set_projection(self, projection: Projection) -> None:
        """Orthografisch ist das, was gemessene Längen vertrauenswürdig
        macht (§18.1).
        """
        self._projection = projection
        if self.renderer is None:
            return
        self.renderer.set_parallel_projection(projection == "orthographic")
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
        if plane == self._section and thickness == self._slice_thickness:
            return
        self._section = plane
        self._slice_thickness = thickness
        self.show_scene(self._scene_for_rebuild())

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
        self._pending_owner = ""
        self._pending_plane = None
        # Die Fangmarke gehört zum Werkzeug: Wer es verlässt, lässt keinen
        # Stern im Bild stehen — und wer die Messart wechselt, bekommt sie bei
        # der nächsten Ruhepause neu.
        self._clear_snap_preview()
        self._update_cursor()

    @property
    def measure_mode(self) -> MeasureMode:
        return self._measure_mode

    def undo_measurement(self) -> None:
        """Nimmt das zuletzt gesetzte Maß zurück — nur dieses (§18.3).

        „Bemaßungen löschen" nimmt alle, und wer nach dem fünften Maß einmal
        danebengeklickt hatte, verlor die vier davor mit (Robert,
        03.09.2026). Ein halb gesetztes Maß zählt zuerst: Wer den ersten
        Punkt gesetzt hat und die Rücktaste drückt, meint diesen Punkt und
        nicht das fertige Maß davor.
        """
        if self._pending_point is not None or self._pending_plane is not None:
            self._pending_point = None
            self._pending_owner = ""
            self._pending_plane = None
            self._redraw_measurements()
            return
        if not self.measurements.entries:
            return
        self.measurements.remove(len(self.measurements.entries) - 1)
        self._redraw_measurements()

    def clear_measurements(self) -> None:
        """Maße bleiben, bis sie gelöscht werden — das hier ist das
        Löschen (§18.3).
        """
        self.measurements.clear()
        self._pending_point = None
        self._pending_owner = ""
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
        """Die Enden der Trennlinie, die Linie dazwischen und die Ebene, die
        daraus wird (§25) — als Vorschau, die ein Werkzeugwechsel abräumt.

        Die Operation speichert Szenenkoordinaten. In „Alle Platten" steht
        der Körper für die Anzeige versetzt; Linie und Ebene müssen genau
        denselben reinen Anzeigeversatz bekommen, sonst erscheinen sie auf
        Platte 1 statt auf dem angeklickten Teil.
        """
        import numpy as np

        self.clear_split_line()
        if self.renderer is None or not points:
            return

        entry = self._result.scene.objects.get(target) if self._result and target else None
        shift = (
            self._view_offset(entry, self._result)
            if entry is not None and self._result is not None
            else np.zeros(3)
        )
        marks = np.asarray(points, dtype=float) + shift
        self._split_actors.append(
            self.renderer.add_points(marks, name="split:ends", colour=SELECTED_COLOUR, size=14.0)
        )
        if len(points) >= 2:
            self._split_actors.append(
                self.renderer.add_lines(
                    marks[:2], name="split:line", colour=SELECTED_COLOUR, width=3.0
                )
            )
        if plane is not None and entry is not None:
            bounds = entry.mesh.bounds
            patch = plane_patch(bounds.minimum, bounds.maximum, plane)
            if patch:
                corners = np.asarray(patch, dtype=float)
                centre = np.mean(corners, axis=0)
                corners = centre + SPLIT_PLANE_SCALE * (corners - centre) + shift
                vertices, faces = shapes.polygon(corners)
                self._split_actors.append(
                    self.renderer.add_surface(
                        vertices,
                        faces,
                        name="split:plane",
                        style=SurfaceStyle(
                            colour=SELECTED_COLOUR, opacity=0.22, lighting=False, pickable=False
                        ),
                    )
                )
                # Der Rand als eigene Linie und nicht als Kanten der Fläche:
                # Die Fläche ist ein Fächer aus Dreiecken, und deren Kanten
                # zeichneten die Diagonalen mit.
                self._split_actors.append(
                    self.renderer.add_lines(
                        shapes.closed_ring(corners),
                        name="split:rim",
                        colour=SELECTED_COLOUR,
                        width=2.0,
                        connected=True,
                    )
                )
        self.renderer.render()

    def clear_split_line(self) -> None:
        """Nimmt die Vorschau wieder heraus."""
        if self.renderer is None:
            self._split_actors.clear()
            return
        for actor in self._split_actors:
            self.renderer.remove(actor)
        self._split_actors.clear()
        self.renderer.render()

    def view_direction(self) -> Vec3:
        """Wohin die Kamera schaut — von ihr weg auf den Brennpunkt zu.

        Die Richtung, die aus einer gezeichneten Linie eine Ebene macht
        (:func:`app.core.geom.section.plane_through`). Sie wird **einmal**
        abgefragt, wenn die Linie fertig ist, und wandert dann als Zahl in die
        Operation: Eine Op, die die Kamera läse, gäbe beim zweiten Auswerten
        ein anderes Ergebnis (§11.2).

        Ohne Renderer — offscreen — der Blick aus der Vorgabestellung. Eine
        Ausnahme, die eine Rechnung überspringt, wäre ein Test, der nie etwas
        prüft.
        """
        import numpy as np

        if self.renderer is None:
            return (0.0, 1.0, 0.0)
        pose = self.renderer.camera_pose()
        forward = np.asarray(pose.focal_point, dtype=float) - np.asarray(pose.position, dtype=float)
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
        if self._brush_actor is not None and self.renderer is not None:
            self.renderer.remove(self._brush_actor)
            self.renderer.render()
        self._brush_actor = None

    def _draw_brush(self) -> None:
        """Den Pinselradius als Ring auf der Fläche unter dem Zeiger zeigen (§20).

        Als Weltmaß in der Szene und nicht am Zeiger: Ein Zeiger hat feste
        Punktgröße und weiß nichts von der Kamera. Der Ring liegt in der
        Ebene der nächsten Ecke des Netzes.
        """
        import numpy as np

        if self.renderer is None or self._hover_at is None or self._brush_radius <= 0.0:
            return
        x, y = self._hover_at
        point = self.renderer.display_to_world(x, y, self.renderer.focal_depth())
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
        self._hide_brush()
        self._brush_actor = self.renderer.add_lines(
            shapes.closed_ring(ring),
            name="brush",
            colour=SELECTED_COLOUR,
            width=2.0,
            connected=True,
        )
        self.renderer.render()

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
        if self.renderer is None:
            return
        self.renderer.widget.setCursor(cursors.cursor(role, self))

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
                ready_to_pull = self._pull_is_offered()
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
        if target_changed and self.renderer is not None:
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
        if self.renderer is None or self._hover_at is None or self._dragging_role:
            return
        x, y = self._hover_at
        if self._sculpting:
            # Beim Formen ist unter dem Zeiger nie ein Merkmal gemeint,
            # sondern immer eine Stelle. Der Ring zeigt sie; die Suche nach
            # Merkmalen bliebe hier nur teuer.
            self._draw_brush()
            return
        if self._measure_mode in ("distance", "thickness"):
            # **Beim Messen ist kein Merkmal gemeint, sondern eine Stelle** —
            # und die verschiebt der Fang. Wer nicht sieht, wohin sein Klick
            # fällt, zielt blind: Der Kern zieht den Punkt auf die nächste Ecke
            # oder Kante, und im Bild geschah das bisher erst *nach* dem Klick
            # (Robert, 03.09.2026: „bei messen ist das zielen relativ schwer").
            # Der Winkelmodus bleibt bei der Merkmalssuche — dort wählt man
            # ebene Flächen, und die Hervorhebung ist genau die Zielhilfe.
            self._set_hover_target(None, None)
            self._preview_snap(x, y)
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

    def _note_pointer(self, x: int, y: int) -> None:
        """Wo der Zeiger steht — in Gerätepixeln, gezählt wie Qt (oben links).

        Der Renderer meldet jede Bewegung als ``PointerEvent`` in genau der
        Zählung, in der ``world_to_display`` und ``pick_surface`` antworten;
        eine Umrechnung gibt es hier nicht mehr. Bis zum 05.09.2026 spiegelte
        diese Stelle nach VTKs Zählung von unten, und wer sie vergaß, suchte am
        gespiegelten Ort — in der Bildmitte zufällig richtig.
        """
        if self.renderer is None:
            return
        self._hover_at = (int(x), int(y))
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
        """Die Maus hat das Bild verlassen.

        **Der Pinselring geht mit.** Er zeigt, wo der Pinsel greifen würde —
        eine Aussage über den Zeiger, und der ist fort. Ohne diese Zeile blieb
        er an der letzten Stelle im Modell stehen, und niemand kam mehr an ihn
        heran: :meth:`_draw_brush` kehrt bei ``_hover_at is None`` sofort
        zurück, und ``set_brush_radius`` ruft nur sie. Am Regler der Formleiste
        zu ziehen änderte den Ring danach nicht mehr — er behielt seinen
        Durchmesser, während die Leiste einen anderen anzeigte. Der Weg dorthin
        ist der übliche: Die Leiste liegt unter der Ansicht, und der Weg zum
        Regler führt hinaus.
        """
        self._hover_timer.stop()
        self._hover_at = None
        self._set_hover_target(None, None)
        self._clear_snap_preview()
        self._hide_brush()

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

        snapped = self._snap_for_measure(picked)
        mesh = self._nearest_mesh(picked)
        if snapped is None or mesh is None:
            # Kein stiller Ausgang: Wer am Messen ist und danebenklickt,
            # sieht sonst einfach nichts — derselbe Grund, aus dem der
            # Winkel-Pfad seine Sätze führt (§2.7).
            self.measurementStatus.emit(tr("Zum Messen einen Körper anklicken."))
            return

        # **Welcher Körper das war, wird jetzt gefragt und nicht später.** In
        # der Szene liegen zwei Druckplatten übereinander (§25); von dort aus
        # ist ein Punkt der einen von einem der anderen nicht zu unterscheiden.
        # Der Klick kam aus dem Bild, und dort ist er eindeutig.
        owner = self._object_at_view(point) or ""

        if self._measure_mode == "thickness":
            thickness = wall_thickness(mesh, snapped.point)
            if thickness is not None:
                self._add(
                    Measurement(
                        kind="thickness",
                        value=thickness,
                        points=(snapped.point,),
                        object_ids=(owner,),
                    )
                )
            else:
                self.measurementStatus.emit(
                    tr("Hier ließ sich keine Wandstärke messen — auf eine Wand klicken.")
                )
            return

        if self._pending_point is None:
            self._pending_point = snapped.point
            self._pending_owner = owner
            self.measurementStatus.emit(tr("Erster Punkt gewählt — zweiten Punkt anklicken."))
            return
        self._add(
            Measurement(
                kind="distance",
                value=distance(self._pending_point, snapped.point),
                points=(self._pending_point, snapped.point),
                object_ids=(self._pending_owner, owner),
            )
        )
        self._pending_point = None
        self._pending_owner = ""

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

    # --- wohin ein Messklick fällt (§18.3) --------------------------------------

    def _snap_for_measure(self, point: Vec3) -> SnapResult | None:
        """Wohin ein Messklick an dieser Stelle fiele — die **eine** Rechnung.

        Klick und Zeiger fragen sie beide, und das ist dieselbe Zusage wie bei
        :meth:`_would_pick_feature`: Eine Vorschau, die woanders fängt als der
        Klick, verspricht etwas, das nicht eintritt — sie wäre schlimmer als
        gar keine.

        ``None``, wo kein Körper unter der Stelle liegt; dort gibt es nichts
        zu fangen, und der Aufrufer sagt es auf seine Weise (der Klick mit
        einem Satz, der Zeiger, indem er die Marke wegnimmt).
        """
        mesh = self._nearest_mesh(point)
        if mesh is None:
            return None
        return snap(mesh, point, radius=self._snap_radius_at(point))

    def _snap_radius_at(self, point: Vec3) -> float | None:
        """Die Fangweite in Millimetern, damit sie im Bild immer gleich breit
        ist (:data:`MEASURE_SNAP_PIXELS`).

        ``None`` heißt „keine Angabe" und lässt dem Kern seine eigene Weite —
        ohne Renderer, ohne Projektion, ohne Bild gibt es keine Bildpunkte, in
        denen man rechnen könnte.
        """
        scale = self._pixels_per_mm_at(point)
        if scale is None or scale <= EPS_GEOM:
            return None
        return MEASURE_SNAP_PIXELS * self._device_ratio() / scale

    def _pixels_per_mm_at(self, point: Vec3) -> float | None:
        """Wie viele Gerätepixel ein Millimeter an dieser Stelle im Bild misst.

        **Gemessen, nicht aus der Kamera abgeleitet** — dieselbe Begründung wie
        bei :meth:`pixels_per_mm`: Zwei Punkte, einen Millimeter auseinander
        und quer zur Blickrichtung, durch dieselbe Projektion geschickt, die
        auch das Bild macht. Damit stimmt die Zahl bei Parallel- wie bei
        Zentralprojektion, ohne dass hier stünde, welche gerade gilt.

        Der Punkt kommt aus der **Szene** und die Projektion aus der
        **Ansicht** (§25). Für den Maßstab macht das nichts: Eine Verschiebung
        parallel zur Bildebene ändert ihn nicht, und die Platten stehen
        nebeneinander. Wer hier umrechnete, bräuchte eine Objektkennung, die
        an dieser Stelle niemand hat.
        """
        if self.renderer is None:
            return None
        import numpy as np

        pose = self.renderer.camera_pose()
        position = np.asarray(pose.position, dtype=float)
        focus = np.asarray(pose.focal_point, dtype=float)
        up = np.asarray(pose.view_up, dtype=float)
        sideways = np.cross(focus - position, up)
        span = float(np.linalg.norm(sideways))
        if span <= EPS_GEOM:
            return None
        sideways = sideways / span
        shifted = np.asarray(point, dtype=float) + sideways
        here = self._display_of(point)
        there = self._display_of([float(value) for value in shifted])
        if here is None or there is None:
            return None
        measured = math.dist(here, there)
        return measured if measured > EPS_GEOM else None

    def _preview_snap(self, x: int, y: int) -> None:
        """Zeichnet die Marke dorthin, wo ein Klick jetzt landen würde."""
        view_point = self._world_at(x, y)
        if view_point is None:
            self._clear_snap_preview()
            return
        found = self._snap_for_measure(self._from_view(view_point))
        if found is None:
            self._clear_snap_preview()
            return
        self._snap_owner = self._object_at_view(view_point) or ""
        self._draw_snap_preview(found)

    def _draw_snap_preview(self, found: SnapResult) -> None:
        """Die Fangmarke dort zeichnen, wohin ein Messklick fiele (§18.3).

        Ein Kreuz mit einem Punkt in der Mitte, in der Bildebene und in
        fester Bildgröße — die Größe ist die Auskunft (Regel 18): Ecke groß,
        Kante mittel, freie Stelle klein. Vor dem Material, wie das Maß danach:
        Eine Marke, die im Material verschwindet, sagt nichts über die Stelle,
        die sie meint. Dieselbe Stelle wird nicht zweimal gezeichnet.
        """
        if self.renderer is None:
            return
        if (
            self._snap_shown is not None
            and self._snap_shown.kind == found.kind
            and all(
                abs(before - after) <= EPS_GEOM
                for before, after in zip(self._snap_shown.point, found.point, strict=True)
            )
        ):
            return
        self._remove_snap_actors()

        import numpy as np

        # Dieselbe Umrechnung wie am Maß darüber: Die Marke muss dort stehen,
        # wo der Zeiger ist, und das Maß danach an derselben Stelle.
        centre = np.asarray(self.view_point_of(found.point, self._snap_owner), dtype=float)
        across, upward = self._screen_axes()
        scale = self._pixels_per_mm_at(found.point)
        if across is None or upward is None or scale is None:
            return
        arm = SNAP_MARK_PIXELS.get(found.kind, SNAP_MARK_PIXELS["free"]) / scale
        for index, direction in enumerate((across, upward)):
            step = direction * arm
            self._snap_actors.append(
                self.renderer.add_lines(
                    np.array([centre - step, centre + step], dtype=float),
                    name=f"measure_snap:{index}",
                    colour=MEASURE_COLOUR,
                    width=2.0,
                    keep_in_front=True,
                )
            )
        self._snap_actors.append(
            self.renderer.add_points(
                np.array([centre], dtype=float),
                name="measure_snap:dot",
                colour=MEASURE_COLOUR,
                size=float(SNAP_DOT_PIXELS.get(found.kind, SNAP_DOT_PIXELS["free"])),
                keep_in_front=True,
            )
        )
        self._snap_shown = found
        self.setAccessibleDescription(snap_sentence(found.kind))
        self._draw()

    def _screen_axes(self) -> tuple[Any, Any]:
        """Die beiden Richtungen, die im Bild waagerecht und senkrecht liegen.

        Eine Marke, die entlang der **Weltachsen** gezeichnet wird, ist in
        jeder Ansicht verschieden verkürzt: In der isometrischen war sie auf
        ein Drittel zusammengezogen und im gerenderten Fenster kaum zu finden.
        Entlang dieser beiden steht sie immer als sauberes Kreuz zum
        Betrachter.
        """
        if self.renderer is None:
            return None, None
        import numpy as np

        pose = self.renderer.camera_pose()
        forward = np.asarray(pose.focal_point, dtype=float) - np.asarray(pose.position, dtype=float)
        up = np.asarray(pose.view_up, dtype=float)
        across = np.cross(forward, up)
        span = float(np.linalg.norm(across))
        if span <= EPS_GEOM:
            return None, None
        across = across / span
        upward = np.cross(across, forward)
        height = float(np.linalg.norm(upward))
        if height <= EPS_GEOM:
            return None, None
        return across, upward / height

    def _remove_snap_actors(self) -> None:
        if self.renderer is None:
            self._snap_actors.clear()
            return
        for actor in self._snap_actors:
            self.renderer.remove(actor)
        self._snap_actors.clear()

    def _clear_snap_preview(self) -> None:
        """Nimmt die Marke weg — beim Verlassen des Bildes, des Körpers und
        des Werkzeugs.
        """
        if not self._snap_actors and self._snap_shown is None:
            return
        self._remove_snap_actors()
        self._snap_shown = None
        self.setAccessibleDescription("")
        self._draw()

    @property
    def snap_preview(self) -> SnapResult | None:
        """Was die Fangmarke gerade zeigt — Auskunft für Tests und Oberfläche."""
        return self._snap_shown

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
        hit = self._hit_at(point)
        if hit is not None:
            return self._result.scene.objects[hit.object_id].mesh
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

    def _object_at_view(self, point: Vec3) -> ObjectId | None:
        """Welcher Körper an dieser Stelle **im Bild** liegt.

        Die Schwester von :meth:`_object_at`, und der Unterschied ist der
        ganze Grund: Jene fragt die Szene, und dort stehen zwei Druckplatten
        **übereinander** — `arrange_bed` setzt Platte 2 an denselben Nullpunkt,
        weil beide einzeln gedruckt werden (§25). Ein Punkt in
        Szenenkoordinaten lässt sich damit keiner Platte zuordnen; im Bild
        stehen die Betten nebeneinander, und dort ist er eindeutig.

        Gebraucht wird das überall, wo ein **Ort** gemerkt und später wieder
        gezeigt wird — beim Messen. Wer nur rechnet, braucht es nicht: Ein
        Abstand ist derselbe, gleich auf welcher Platte.
        """
        if self._result is None:
            return None
        hit = self._hit_at(point, view_space=True)
        if hit is not None:
            return hit.object_id
        import numpy as np

        best: ObjectId | None = None
        best_volume = float("inf")
        for object_id, entry in self._result.scene.objects.items():
            if not self._in_view(object_id, entry):
                continue
            shift = np.asarray(self._view_offset(entry, self._result), dtype=float)
            bounds = entry.mesh.bounds
            size = bounds.size
            slack = max(EPS_MATCH_MINIMUM, max(size) * EPS_MATCH_RELATIVE)
            low = np.asarray(bounds.minimum, dtype=float) + shift
            high = np.asarray(bounds.maximum, dtype=float) + shift
            if not all(
                float(a) - slack <= value <= float(b) + slack
                for a, b, value in zip(low, high, point, strict=True)
            ):
                continue
            volume = size[0] * size[1] * size[2]
            if volume < best_volume:
                best_volume = volume
                best = object_id
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
        hit = self._hit_at(point)
        if hit is not None:
            return hit.object_id
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
        """Alle Maße neu zeichnen: Linie, Punkt und Zahl je Eintrag (§18.3).

        **Ein Maß liegt in der Szene und wird im Bild gezeigt** (§25, §18.8).
        Die beiden Orte sind nicht derselbe, sobald ein zweites Bett
        danebensteht oder die Körper auseinandergezogen sind; gerechnet wird
        je Punkt, denn die zwei Enden eines Maßes dürfen zu verschiedenen
        Körpern gehören. **Und ein Maß läuft durch das Material, und dort war
        es weg** (Robert, 03.09.2026): Es ist eine Auskunft über das Teil und
        kein Teil davon — ``keep_in_front`` zeichnet es über das, was davor
        liegt. Die Zahl geht über ``labels`` wie jede Anzeige (Regel 20).
        """
        if self.renderer is None:
            return
        for actor in self._measure_actors:
            self.renderer.remove(actor)
        self._measure_actors.clear()

        import numpy as np

        for index, entry in enumerate(self.measurements.entries):
            owners = entry.object_ids or ("",) * len(entry.points)
            shown = tuple(
                self.view_point_of(spot, owner)
                for spot, owner in zip(entry.points, owners, strict=False)
            )
            if len(shown) == 2:
                self._measure_actors.append(
                    self.renderer.add_lines(
                        np.array([shown[0], shown[1]], dtype=float),
                        name=f"measure:{index}",
                        colour=MEASURE_COLOUR,
                        width=2.0,
                        keep_in_front=True,
                    )
                )
            label = (
                localised(f"{entry.shown:g}°")
                if entry.kind == "angle"
                else length(float(entry.value))
            )
            if shown:
                self._measure_actors.append(
                    self.renderer.add_labels(
                        np.array([shown[-1]], dtype=float),
                        [label],
                        name=f"measure_label:{index}",
                        style=LabelStyle(
                            text_colour=MEASURE_COLOUR,
                            font_size=12,
                            always_visible=True,
                            show_points=True,
                            point_colour=MEASURE_COLOUR,
                            point_size=8,
                        ),
                    )
                )
        self._draw()

    # --- analysis maps (§18.4) --------------------------------------------------

    def set_analysis_map(self, analysis: AnalysisMap | None, object_id: ObjectId | None) -> None:
        """Färbt einen Körper nach den Zahlen einer Karte, oder nimmt die Karte
        weg.
        """
        # **Identität für die Karte, Gleichheit für die Kennung.** Ein ``==``
        # über zwei Karten verglich ihre Zahlenfelder — bei Arrays ist das
        # teuer und im Wahrheitswert nicht eindeutig. ``None is None`` trifft
        # genau den gemessenen Fall: dreimal „keine Karte" hintereinander.
        wanted_object = object_id if analysis is not None else None
        if analysis is self._map and wanted_object == self._map_object:
            return
        self._map = analysis
        self._map_object = wanted_object
        # Solange Farbe eine Zahl bedeutet, darf nichts sie nachdunkeln —
        # weder die Verdeckung noch ein Schatten.
        self._apply_ambient_occlusion()
        self.show_scene(self._scene_for_rebuild())

    @property
    def analysis_map(self) -> AnalysisMap | None:
        return self._map

    def fly_to(self, point: Vec3, distance_factor: float = 3.0, reach: float | None = None) -> None:
        """Bewegt die Kamera auf eine Stelle, ohne die Blickrichtung zu
        ändern (§18.4).

        Das Modell mitzudrehen kostete die Orientierung, die der Nutzer sich
        gerade aufgebaut hat; entlang der aktuellen Blickachse näher zu kommen
        behält sie.

        ``reach`` gibt den Abstand vor, wo der Aufrufer ihn besser kennt als die
        Szene: Ein Befund gehört zu **einem** Körper, und wie weit man von ihm
        weg sein muss, hängt an dessen Größe und nicht an der des größten Teils
        auf dem Bett.
        """
        if self.renderer is None:
            return
        import numpy as np

        pose = self.renderer.camera_pose()
        position = np.asarray(pose.position, dtype=float)
        focus = np.asarray(pose.focal_point, dtype=float)
        direction = position - focus
        length = float(np.linalg.norm(direction))
        if length <= 1e-9:
            direction = np.array([1.0, -1.0, 0.8])
            length = float(np.linalg.norm(direction))
        reach = max(reach or self._scene_size() / distance_factor, 1.0)
        target = np.asarray(point, dtype=float)
        moved = target + direction / length * reach
        self.renderer.set_camera_pose(
            CameraPose(
                (float(moved[0]), float(moved[1]), float(moved[2])),
                (float(target[0]), float(target[1]), float(target[2])),
                pose.view_up,
            )
        )
        # Nah heran heißt: die Nahebene neu legen, sonst schneidet sie ins
        # Material — und der Schatten gehört zur neuen Blickrichtung.
        self.renderer.reset_clipping_range()
        self._draw()
        self._redraw_shadows()
        self.cameraMoved.emit()

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
        if self.renderer is None:
            return
        self._redraw_features()
        self._draw()

    def select_feature(self, feature_id: FeatureId | None) -> None:
        self._selected_feature_refs = ()
        self._selected_feature = feature_id
        self._selected_features = (feature_id,) if feature_id is not None else ()
        self._redraw_features()
        # Der Körper gibt die Auswahlfarbe an das Merkmal ab und holt sie
        # zurück, sobald keines mehr gewählt ist.
        self._apply_selection_colour()
        if self.renderer is not None:
            # Auch der Griff wechselt mit: eine gewählte Fläche bekommt ihn
            # auf die Fläche, eine abgewählte gibt ihn ans Objekt zurück
            # (§18.11) — nicht erst beim nächsten Umschalten.
            self.set_gizmo(self._gizmo_wanted)
            self._draw()

    def select_features(self, feature_ids: Sequence[FeatureId]) -> None:
        """Mehrere Merkmale desselben Körpers gemeinsam hervorheben.

        Die Einzelauswahl bleibt bewusst ``None``: Zwei Bohrungen sind kein
        führendes Merkmal für eine Operation oder den Transformationsgriff.
        Ihre sichtbare Auswahl darf deshalb aber weder verschwinden noch auf
        den ganzen Körper zurückfallen.
        """
        features = self._features_of_selection()
        chosen = tuple(
            feature_id for feature_id in dict.fromkeys(feature_ids) if feature_id in features
        )
        # Der bestehende Weg kann neben einem Merkmal weitere ganze Körper
        # enthalten. Nur die neue vollständige Paarwahl ersetzt diese Menge.
        self._selected_feature_refs = ()
        self._selected_features = chosen
        self._selected_feature = chosen[0] if len(chosen) == 1 else None
        self._refresh_feature_selection()

    def _remember_feature_refs(self, refs: tuple[tuple[ObjectId, FeatureId], ...]) -> None:
        """Vollständige Merkmalsziele und den kompatiblen Einzelzustand gemeinsam merken."""
        self._selected_feature_refs = refs
        if refs:
            owners = tuple(dict.fromkeys(owner for owner, _feature_id in refs))
            self._selected, self._selected_more = owners[0], owners[1:]
        self._selected_features = tuple(
            feature_id for owner, feature_id in refs if owner == self._selected
        )
        self._selected_feature = refs[0][1] if len(refs) == 1 else None

    def select_feature_refs(self, refs: Sequence[tuple[ObjectId, FeatureId]]) -> None:
        """Exakte Merkmale mehrerer Körper wählen; das erste gültige Paar führt."""
        result = self._result
        chosen = tuple(
            (object_id, feature_id)
            for object_id, feature_id in dict.fromkeys(refs)
            if result is not None
            and (entry := result.scene.objects.get(object_id)) is not None
            and feature_id in entry.features
        )
        self._remember_feature_refs(chosen)
        self._refresh_feature_selection()

    def _refresh_feature_selection(self) -> None:
        """Die vollständig gesetzte Auswahl einmal an Markierung und Griff weitergeben."""
        self._redraw_features()
        # Der Körper gibt die Auswahlfarbe an das Merkmal ab und holt sie
        # zurück, sobald keines mehr gewählt ist.
        self._apply_selection_colour()
        if self.renderer is not None:
            # Auch der Griff wechselt mit: eine gewählte Fläche bekommt ihn
            # auf die Fläche, eine abgewählte gibt ihn ans Objekt zurück
            # (§18.11) — nicht erst beim nächsten Umschalten.
            self.set_gizmo(self._gizmo_wanted)
            self._draw()

    @property
    def selected_feature(self) -> FeatureId | None:
        return self._selected_feature

    def highlighted_features(self) -> tuple[FeatureId, ...]:
        """Ausgewählte Merkmalskennungen am führenden Körper, ohne fremde Objektkennungen."""
        # Einige gezielte Viewport-Tests setzen den alten Einzelzustand direkt.
        # Die öffentliche Auswahl läuft immer über ``select_feature`` oder
        # ``select_features`` und hält beide Werte gemeinsam.
        if self._selected_feature is not None:
            return (self._selected_feature,)
        return self._selected_features

    def highlighted_feature_refs(self) -> tuple[tuple[ObjectId, FeatureId], ...]:
        """Die Auswahl mit Körperkennung; nackte Kennungen gelten nur am führenden Körper."""
        if self._selected_feature_refs:
            return self._selected_feature_refs
        if self._selected is None:
            return ()
        return tuple((self._selected, feature_id) for feature_id in self.highlighted_features())

    def highlighted_object(self) -> ObjectId | None:
        """Welcher Körper die Auswahlfarbe trägt — keiner, solange ein Merkmal
        gewählt ist (§19.1).

        Als eigene Auskunft und nicht als Zustand des Renderers, aus demselben
        Grund wie bei :meth:`gizmo_target`: offscreen gibt es keinen, und ein
        Test, der sich dort überspringt, prüft nie etwas.
        """
        if self._selection_marking_hidden() or self.highlighted_feature_refs():
            return None
        return self._selected

    def highlighted_objects(self) -> tuple[ObjectId, ...]:
        """Alle Körper mit Auswahlfarbe, der führende zuerst.

        **Baut auf :meth:`highlighted_object` auf und erbt damit deren
        Ausnahmen** statt sie nachzubauen: Ist ein Merkmal gewählt, liegt die
        Auswahlfarbe auf der Bohrung und kein Körper leuchtet — auch keiner
        der weiteren (§19.1). Dasselbe gilt, solange eine Differenzvorschau
        die Modellfarben besitzt. Eine zweite Fassung dieser Regel wäre die
        Stelle, an der die beiden Antworten eines Tages auseinanderlaufen.
        """
        leading = self.highlighted_object()
        if leading is None:
            return ()
        return (leading, *self._selected_more)

    def highlighted_faces(self) -> tuple[int, ...]:
        """Die Dreiecke, die als gewähltes Merkmal aufleuchten (§18.5).

        Leer heißt: nichts hervorzuheben — kein Merkmal gewählt, der Körper
        ausgeblendet, oder ein Merkmal ohne zugeordnete Dreiecke wie eine
        Kante aus dem exakten Kern. Gezählt wird im Netz der Szene, nicht im
        dezimierten Anzeigenetz (§18.9).
        """
        if self._selection_marking_hidden():
            return ()
        return tuple(
            dict.fromkeys(
                index
                for feature_id in self.highlighted_features()
                for index in self._face_indices(self._selected, feature_id)
            )
        )

    def protected_features(self, object_id: ObjectId | None = None) -> tuple[FeatureId, ...]:
        """Welche Flächen dieses Körpers als Sichtflächen gesperrt sind.

        Ohne ``object_id`` die des gewählten Körpers. Als eigene Auskunft und
        nicht als Zustand des Renderers, aus demselben Grund wie bei
        :meth:`highlighted_faces`: offscreen gibt es keinen Renderer, und ein
        Test, der sich dort überspringt, prüft nie etwas.
        """
        target = object_id if object_id is not None else self._selected
        if target is None:
            return ()
        return tuple(sorted(self._protected.get(target, ())))

    def set_protected(self, object_id: ObjectId, feature_id: FeatureId, on: bool) -> None:
        """Eine Fläche sperren oder freigeben und das Bild nachziehen."""
        marked = self._protected.setdefault(object_id, set())
        if on:
            marked.add(feature_id)
        else:
            marked.discard(feature_id)
        if not marked:
            self._protected.pop(object_id, None)
        self._redraw_features()
        self._draw()

    def protected_patches(self, object_id: ObjectId) -> list[Any]:
        """Die Punktwolken der gesperrten Flächen — Eingabe für die Suche.

        Punkte und keine Dreiecksnummern: ``split_to_fit`` teilt mehrfach,
        und jedes Teilstück ist ein neues Netz mit neuer Nummerierung. Ein
        Verweis über Indizes zeigte nach dem ersten Schnitt ins Leere.
        Umgerechnet wird deshalb hier, einmal beim Suchen.
        """
        import numpy as np

        if self._result is None:
            return []
        entry = self._result.scene.objects.get(object_id)
        raw = getattr(entry.mesh, "raw", None) if entry is not None else None
        if entry is None or raw is None:
            return []
        points = np.asarray(raw.vertices, dtype=float)
        triangles = np.asarray(raw.faces, dtype=np.int64)
        patches: list[Any] = []
        for feature_id in self._protected.get(object_id, ()):
            chosen = self._face_indices(object_id, feature_id)
            if not chosen:
                continue
            patches.append(points[triangles[np.asarray(chosen, dtype=np.int64)].ravel()])
        return patches

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
        if entry is None or not self._in_pick_view(object_id, entry):
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
        if self.renderer is None:
            return
        self._redraw_feature_patch()
        self._redraw_protected_patch()
        self._redraw_hover_patch()
        for actor in self._feature_actors:
            self.renderer.remove(actor)
        self._feature_actors.clear()
        self._feature_label_data.clear()
        self._feature_label_owners.clear()
        self._feature_marker_item = None
        self._feature_preview_state = None
        self._feature_text_item = None
        self._feature_leader_item = None
        self._feature_leader_count = 0
        self._feature_label_state = None
        self._feature_label_content = None
        # Ohne Überlagerung bleibt das **gewählte** Merkmal beschriftet: seine
        # Fläche leuchtet in der Auswahlfarbe, und eine Aussage allein über
        # Farbe wäre genau die, die Regel 18 verbietet.
        shown: dict[tuple[ObjectId, FeatureId], Feature] = {}
        selected_refs = self.highlighted_feature_refs()
        if self._selected is not None:
            for feature_id, feature in self._features_of_selection().items():
                if self._feature_overlay or feature_id in self.highlighted_features():
                    shown[(self._selected, feature_id)] = feature
        for object_id, feature_id in selected_refs:
            selected_feature = self._features_of(object_id).get(feature_id)
            if selected_feature is not None:
                shown[(object_id, feature_id)] = selected_feature
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
        for (object_id, feature_id), feature in shown.items():
            entry = self._result.scene.objects.get(object_id) if self._result is not None else None
            if entry is None or not self._in_pick_view(object_id, entry):
                continue
            explicit = (object_id, feature_id) in selected_refs or (object_id, feature_id) == (
                self._hovered_object,
                self._hovered_feature,
            )
            centre = self._feature_label_anchor(entry, feature_id, feature, explicit=explicit)
            if centre is None:
                continue
            shift = (
                self._shown_offset(entry, self._result)
                if entry is not None and self._result is not None
                else np.zeros(3)
            )
            points.append(
                [float(value) + float(moved) for value, moved in zip(centre, shift, strict=True)]
            )
            priority = 0 if (object_id, feature_id) in selected_refs else 1 if explicit else 2
            shown_point = (points[-1][0], points[-1][1], points[-1][2])
            self._feature_label_data.append(
                (shown_point, feature_label(feature_id, feature), priority)
            )
            self._feature_label_owners.append(object_id)
        if not points:
            return

        # Alle Anker bleiben sichtbar und die Geometrie bleibt auswählbar,
        # auch wenn für einen automatischen Namen gerade kein Leseraum frei ist.
        self._feature_marker_item = self.renderer.add_points(
            np.asarray(points, dtype=float),
            name="feature-markers",
            colour=MEASURE_COLOUR,
            size=8,
            pickable=False,
            keep_in_front=True,
        )
        self._feature_actors.append(self._feature_marker_item)
        self._feature_label_style = LabelStyle(
            text_colour=self._sketch_label_colour,
            font_size=12,
            always_visible=True,
            background=self._sketch_label_background,
            background_opacity=1.0,
            margin=4,
            show_points=False,
            point_colour=MEASURE_COLOUR,
            point_size=8,
        )
        font = QFont(self.font())
        font.setPixelSize(self._feature_label_style.font_size)
        metrics = QFontMetricsF(font)
        # Qt und pygfx formen Text mit verschiedenen Schriften und DPI-Regeln.
        # Die gemeinsame Platzierung reserviert deshalb mehr als die
        # Qt-Glyphenbreite; die sichtbare Schrift selbst bleibt 12 Pixel groß.
        padding = 2.0 * self._feature_label_style.margin + 4.0
        self._feature_label_sizes = {
            text: (
                max(metrics.horizontalAdvance(text), 1.0) * 1.5 + padding,
                max(metrics.height(), float(font.pixelSize())) * 1.5 + padding,
            )
            for _point, text, _priority in self._feature_label_data
        }
        self._layout_feature_labels()

    def _queue_feature_label_layout(self) -> None:
        """Kamera und Kartenänderungen im nächsten Qt-Durchlauf zusammenfassen."""
        if (
            self._feature_label_data
            or self._feature_patch is not None
            or self._feature_patches
            or self._hover_patch is not None
        ) and not self._feature_layout_timer.isActive():
            self._feature_layout_timer.start(0)

    def _refresh_feature_label_layout(self) -> None:
        """Ein verändertes Layout anzeigen, ohne Geometrie oder Hover neu zu berechnen."""
        if self._layout_feature_labels() and self.renderer is not None:
            self.renderer.render()

    def _sync_feature_preview(self) -> bool:
        """Merkmalsmarken folgen der Aktorvorschau, ihre Originalanker bleiben erhalten."""
        import numpy as np

        edges_changed = False
        for owner in self._edge_actors:
            edges_changed = self._sync_edge_preview(owner) or edges_changed
        owners = dict.fromkeys(
            (
                *self._feature_label_owners,
                *self._feature_patches,
                self._selected,
                self._hovered_object,
            )
        )
        transforms = {
            owner: (actor.matrix(), actor.position())
            for owner in owners
            if owner is not None and (actor := self._actors.get(owner)) is not None
        }
        state = (
            tuple(
                (owner, tuple(matrix.ravel()), position)
                for owner, (matrix, position) in transforms.items()
            ),
            id(self._feature_patch),
            tuple((owner, id(patch)) for owner, patch in self._feature_patches.items()),
            id(self._hover_patch),
        )
        if state == self._feature_preview_state:
            return edges_changed
        self._feature_preview_state = state
        self._feature_label_state = None
        points = np.asarray(
            [point for point, _text, _priority in self._feature_label_data], dtype=float
        ).reshape(-1, 3)
        for owner, (matrix, position) in transforms.items():
            indices = [
                index
                for index, identifier in enumerate(self._feature_label_owners)
                if identifier == owner
            ]
            if indices:
                points[indices] = moved_marks(points[indices], matrix) + np.asarray(position)
        self._feature_label_points = points
        if self._feature_marker_item is not None:
            self._feature_marker_item.update_points(points)
        patches: list[tuple[Item | None, ObjectId | None]] = [
            (patch, owner) for owner, patch in self._feature_patches.items()
        ]
        if self._feature_patch is not None and self._selected not in self._feature_patches:
            patches.append((self._feature_patch, self._selected))
        patches.append((self._hover_patch, self._hovered_object))
        for patch, patch_owner in patches:
            if patch is not None and patch_owner is not None:
                matrix, position = transforms.get(patch_owner, (np.eye(4), (0.0, 0.0, 0.0)))
                patch.set_matrix(matrix)
                patch.set_position(position)
        return True

    def _layout_feature_labels(self) -> bool:
        """Textfelder in freiem Bildraum platzieren; Weltanker und Auswahl bleiben gleich."""
        preview_changed = self._sync_feature_preview()
        renderer = self.renderer
        style = self._feature_label_style
        if renderer is None or style is None or not self._feature_label_data:
            return preview_changed
        ratio = self._device_ratio()
        width, height = renderer.view_size()
        left, right, bottom = self._zone_margins
        room = (
            (left + TIGHT) * ratio,
            TIGHT * ratio,
            width - (right + TIGHT) * ratio,
            height - (bottom + TIGHT) * ratio,
        )
        obstacles = []
        for card in (
            self.banner,
            self.view_bar,
            self.drag_bar,
            self.plane_picker,
            self.sketch_selection,
            self.sketch_action,
        ):
            if not card.isVisibleTo(self):
                continue
            at = (
                renderer.widget.mapFromGlobal(card.mapToGlobal(QPoint()))
                if renderer.widget is not None
                else card.pos()
            )
            obstacles.append(
                (
                    at.x() * ratio,
                    at.y() * ratio,
                    (at.x() + card.width()) * ratio,
                    (at.y() + card.height()) * ratio,
                )
            )
        state = (
            renderer.camera_pose(),
            renderer.parallel_projection(),
            renderer.parallel_scale(),
            renderer.view_angle(),
            width,
            height,
            ratio,
            room,
            tuple(obstacles),
        )
        if state == self._feature_label_state:
            return preview_changed
        self._feature_label_state = state
        projected = [
            renderer.world_to_display(tuple(point)) for point in self._feature_label_points
        ]
        sizes = [
            (self._feature_label_sizes[text][0] * ratio, self._feature_label_sizes[text][1] * ratio)
            for _point, text, _priority in self._feature_label_data
        ]
        # Ein Anker hinter der Kamera darf kein scheinbares Merkmal vor ihr
        # erzeugen. Die Kennung bleibt unabhängig davon im Objektbaum wählbar.
        anchors = [
            (x, y) if 0.0 <= depth <= 1.0 else (math.nan, math.nan) for x, y, depth in projected
        ]
        placed = layout_feature_labels(
            anchors,
            sizes,
            [priority for _point, _text, priority in self._feature_label_data],
            room,
            obstacles,
            gap=TIGHT * ratio,
        )
        import numpy as np

        points = []
        texts = []
        leaders: list[Any] = []
        for index, rect in placed:
            _original, text, _priority = self._feature_label_data[index]
            point = self._feature_label_points[index]
            x, y, depth = projected[index]
            centre_x, centre_y = (rect[0] + rect[2]) / 2.0, (rect[1] + rect[3]) / 2.0
            before = renderer.display_to_world(x, y, depth)
            after = renderer.display_to_world(centre_x, centre_y, depth)
            if before is None or after is None:
                continue
            shifted = np.asarray(point) + np.asarray(after) - np.asarray(before)
            points.append(tuple(float(value) for value in shifted))
            texts.append(text)
            # Die Kollisionsbox ist größer als das sichtbare Textfeld. Ihr
            # Rand wäre nur eine kurze Kerbe neben dem Marker. Die Verbindung
            # reicht deshalb bis zum Textanker; das deckende Feld liegt darüber.
            leaders.extend((point, shifted))
        content = (
            tuple(points),
            tuple(texts),
            tuple(tuple(float(value) for value in point) for point in leaders),
        )
        if content == self._feature_label_content:
            return preview_changed
        self._feature_label_content = content
        if self._feature_text_item is not None:
            self._feature_text_item.update_labels(
                np.asarray(points, dtype=float).reshape(-1, 3), texts
            )
            self._feature_text_item.set_visible(bool(points))
        elif points:
            self._feature_text_item = renderer.add_labels(
                np.asarray(points, dtype=float),
                texts,
                name="features",
                style=style,
            )
            self._feature_actors.append(self._feature_text_item)
        if self._feature_leader_item is not None and len(leaders) != self._feature_leader_count:
            renderer.remove(self._feature_leader_item)
            self._feature_actors.remove(self._feature_leader_item)
            self._feature_leader_item = None
        if self._feature_leader_item is not None:
            self._feature_leader_item.update_points(np.asarray(leaders, dtype=float))
        elif leaders:
            self._feature_leader_item = renderer.add_lines(
                np.asarray(leaders, dtype=float),
                name="feature-label-leaders",
                colour=self._sketch_label_colour,
                width=1.0,
                pickable=False,
                keep_in_front=True,
            )
            self._feature_actors.append(self._feature_leader_item)
        self._feature_leader_count = len(leaders)
        return True

    def _feature_label_anchor(
        self, entry: Any, feature_id: FeatureId, feature: Feature, *, explicit: bool
    ) -> Any:
        """Ein Etikett bleibt bei der sichtbaren Geometrie seines Merkmals.

        Die automatische Schichtauflage benennt nur Merkmale am aktuellen
        Schnitt. Auswahl und Hover dürfen auch sichtbare Bereiche darunter
        benennen; vollständig abgeschnittene Merkmale behalten ihre Auswahl
        im Baum, aber keine schwebende Marke in der Ansicht.
        """
        centre = feature.params.get("centre")
        plane, second = self._section_planes()
        if centre is None or plane is None:
            return centre

        import numpy as np

        planes = (plane,) if second is None else (plane, second)
        normals = np.asarray([part.normal for part in planes], dtype=float)
        lengths = np.linalg.norm(normals, axis=1)
        valid = lengths > EPS_GEOM
        if not np.any(valid):
            return centre
        normals = normals[valid] / lengths[valid, None]
        origins = np.asarray([part.origin for part in planes], dtype=float)[valid]
        positions = np.einsum("ij,ij->i", origins, normals)
        on_layer = self._layer is not None and self._section is None and not explicit

        def visible(points: Any) -> Any:
            """Maske für beide sichtbaren Halbräume, bei Schichten für die Ebene."""
            distances = points @ normals.T - positions
            keep = np.all(distances <= EPS_GEOM, axis=1)
            if on_layer:
                keep &= np.abs(distances[:, 0]) <= EPS_GEOM
            return keep

        raw = getattr(entry.mesh, "raw", None)
        indices = self._face_indices(entry.id, feature_id)
        if raw is None or not indices:
            points = np.asarray(centre, dtype=float).reshape(1, 3)
            return points[0] if visible(points)[0] else None
        triangles = np.asarray(raw.vertices[raw.faces[list(indices)]], dtype=float)
        points = triangles.reshape(-1, 3)
        mask = visible(points)
        pieces = [points[mask]]
        # Jede konvexe Kombination bleibt nur innerhalb desselben Dreiecks
        # sicher auf der Fläche. Die Kennungen zählen im ausgewählten Patch,
        # damit große Netze keinen Speicher für unbeteiligte Dreiecke benötigen.
        triangle_ids = np.repeat(np.arange(len(triangles)), 3) if feature.kind == "face" else None
        owners = [triangle_ids[mask]] if triangle_ids is not None else []
        left = triangles[:, [0, 1, 2]].reshape(-1, 3)
        right = triangles[:, [1, 2, 0]].reshape(-1, 3)
        for normal, position in zip(normals, positions, strict=True):
            before = left @ normal - position
            after = right @ normal - position
            crossing = ((before > EPS_GEOM) & (after < -EPS_GEOM)) | (
                (before < -EPS_GEOM) & (after > EPS_GEOM)
            )
            if not np.any(crossing):
                continue
            fraction = before[crossing] / (before[crossing] - after[crossing])
            points = left[crossing] + (right[crossing] - left[crossing]) * fraction[:, None]
            mask = visible(points)
            pieces.append(points[mask])
            if triangle_ids is not None:
                owners.append(triangle_ids[crossing][mask])
        points = np.vstack(pieces)
        if not len(points):
            return None
        if triangle_ids is not None:
            identifiers = np.concatenate(owners)
            counts = np.bincount(identifiers, minlength=len(triangles))
            occupied = counts > 0
            sums = np.column_stack(
                [
                    np.bincount(identifiers, weights=points[:, axis], minlength=len(triangles))
                    for axis in range(3)
                ]
            )
            candidates = sums[occupied] / counts[occupied, None]
            distances = np.sum((candidates - np.asarray(centre, dtype=float)) ** 2, axis=1)
            return candidates[int(np.argmin(distances))]
        anchor = np.asarray(centre, dtype=float).reshape(1, 3)
        return anchor[0] if visible(anchor)[0] else points.mean(axis=0)

    def show_candidates(
        self,
        candidates: Sequence[tuple[str, str]] = (),
        emphasis: tuple[str, str] | None = None,
    ) -> None:
        """Zeigt, zwischen welchen Merkmalen eine Frage entscheiden lässt (§21.3).

        Der Bauplan verlangt es wörtlich: Verweist eine spätere Operation auf
        eine mehrdeutige Kennung, hält die Auswertung an, **zeigt die
        Kandidaten hervorgehoben** und fragt. Gebaut war alles außer der
        Hervorhebung — der Dialog nannte `hole_1`, `hole_2`, `hole_3`, und der
        Kunde sollte zwischen drei Bohrungen entscheiden, die er nicht sieht.

        ``candidates`` sind Paare aus Körper- und Merkmalskennung. **Paare und
        nicht Kennungen**: Merkmalskennungen sind je Körper vergeben, zwei
        Körper haben beide ein ``hole_1``, und über alle hervorzuheben
        leuchtete an zwei Stellen, während die Frage eine meint.

        ``emphasis`` ist der Kandidat, auf dem die Markierung im Dialog steht;
        er wird deckender gezeichnet. Ein zweiter Aufruf ersetzt den ersten —
        der Dialog ruft bei jedem Zeilenwechsel neu, und das kostet nichts.

        Eine leere Folge nimmt alles weg. Kennungen, die es in der laufenden
        Auswertung nicht gibt, werden still übergangen: Die Auswertung, die
        gefragt hat, kann eine andere sein als die, die im Bild steht.
        """
        self._candidates = tuple(candidates)
        self._candidate_emphasis = emphasis
        self._redraw_candidates()

    def _patch_lift(self) -> float:
        """Wie weit eine hervorgehobene Fläche über dem Körper schwebt.

        Mit der Szene skaliert und nach unten begrenzt: Ein festes Maß wäre an
        einem 5-mm-Teil ein Klotz und an einem 300-mm-Teil unsichtbar.
        """
        return max(self._scene_size() * FEATURE_PATCH_LIFT, EPS_GEOM)

    def _lifted_corners(self, raw: Any, chosen: Any, lift: float, offset: Any) -> Any:
        """Gemeinsame Eckpunkte einer Flächenauswahl gemeinsam anheben.

        Der flächengewichtete Versatz benutzt nur ausgewählte Dreiecke.
        Einzelne Dreiecksnormalen öffneten an leicht geneigten Nachbarn
        sichtbare Spalten. Erst nach der Anhebung wird wieder zur bisherigen
        Dreiecksliste expandiert. Gleiche Koordinaten mit verschiedenen
        Originalkennungen bleiben getrennt; die Markierung verschweißt nichts.
        """
        import numpy as np

        triangles = np.asarray(raw.faces, dtype=np.int64)[chosen]
        vertices, inverse = np.unique(triangles, return_inverse=True)
        inverse = inverse.reshape(-1)
        corners = np.asarray(raw.vertices, dtype=float)[vertices]
        selected = corners[inverse].reshape(-1, 3, 3)
        # Das Kreuzprodukt trägt bereits die doppelte Dreiecksfläche. So
        # braucht ein kleiner Patch keine Flächentabelle des gesamten Netzes.
        products = np.cross(selected[:, 1] - selected[:, 0], selected[:, 2] - selected[:, 0])
        areas = np.linalg.norm(products, axis=1)
        weighted = np.repeat(products, 3, axis=0)
        summed = np.column_stack(
            [
                np.bincount(inverse, weights=weighted[:, axis], minlength=len(vertices))
                for axis in range(3)
            ]
        )
        weights = np.bincount(inverse, weights=np.repeat(areas, 3), minlength=len(vertices))
        np.divide(summed, weights[:, None], out=summed, where=weights[:, None] > 0.0)
        lengths = np.linalg.norm(summed, axis=1, keepdims=True)
        averaged = np.divide(summed, lengths, out=np.zeros_like(summed), where=lengths > EPS_GEOM)
        lifted = self._lift_within_section(corners, averaged * lift)
        return self._clip_feature_corners(lifted[inverse]) + offset

    def _lift_within_section(self, corners: Any, displacement: Any) -> Any:
        """Markierungen an Grenzflächen nur innerhalb des sichtbaren Halbraums anheben."""
        import numpy as np

        displacement = np.broadcast_to(displacement, corners.shape).copy()
        plane, second = self._section_planes()
        for part in (plane, second):
            if part is None:
                continue
            normal = np.asarray(part.normal, dtype=float)
            length = float(np.linalg.norm(normal))
            if length <= EPS_GEOM:
                continue
            normal /= length
            boundary = np.abs((corners - np.asarray(part.origin)) @ normal) <= EPS_GEOM
            # Der Abstand gegen Flimmern darf eine echte Grenzfläche nicht
            # aus dem sichtbaren Halbraum heben und dadurch verschwinden lassen.
            outward = np.maximum(displacement[boundary] @ normal, 0.0)
            displacement[boundary] -= outward[:, None] * normal
        return corners + displacement

    def _clip_feature_corners(self, corners: Any) -> Any:
        """Offene Markierungsdreiecke an denselben Ebenen wie den Körper begrenzen."""
        plane, second = self._section_planes()
        if plane is None or not len(corners):
            return corners

        import numpy as np

        inside = True
        for part in (plane,) if second is None else (plane, second):
            normal = np.asarray(part.normal, dtype=float)
            length = float(np.linalg.norm(normal))
            if length <= EPS_GEOM:
                continue
            distances = (corners - np.asarray(part.origin, dtype=float)) @ (normal / length)
            if np.all(distances > EPS_GEOM):
                return np.empty((0, 3), dtype=float)
            inside = inside and bool(np.all(distances <= EPS_GEOM))
        if inside:
            return corners

        from app.core.deferred import trimesh
        from app.core.geom.mesh import MeshData

        # Getrennte Dreiecke sind eine offene Renderfläche. Der vorhandene
        # Kern-Schnitt fügt ihr keine künstlichen Auswahlkappen hinzu und
        # ändert weder Szenennetz noch den Deckelbefund des eigentlichen Körpers.
        patch = MeshData(
            trimesh.Trimesh(corners, _triangle_faces(len(corners) // 3), process=False)
        )
        clipped = cut(patch, plane, second).mesh.raw
        return np.asarray(clipped.vertices[clipped.faces], dtype=float).reshape(-1, 3)

    def _redraw_candidates(self) -> None:
        """Die Merkmale einer offenen Frage im Bild hervorheben (§21.3).

        Je Kandidat seine Dreiecke, etwas über der Fläche, dazu die Kennung
        als Beschriftung; das betonte Merkmal deckender als die anderen.
        """
        if self.renderer is None:
            return
        for actor in self._candidate_actors:
            self.renderer.remove(actor)
        self._candidate_actors.clear()
        if not self._candidates or self._result is None:
            self._draw()
            return

        import numpy as np

        marks: list[tuple[Vec3, str]] = []
        for index, (object_id, feature_id) in enumerate(self._candidates):
            entry = self._result.scene.objects.get(object_id)
            if entry is None or not self._in_pick_view(object_id, entry):
                continue
            feature = entry.features.get(feature_id)
            raw = getattr(entry.mesh, "raw", None)
            if feature is None or raw is None or not feature.face_indices:
                continue
            chosen = np.asarray(feature.face_indices, dtype=np.int64)
            corners = self._lifted_corners(
                raw, chosen, self._patch_lift(), self._shown_offset(entry, self._result)
            )
            if not len(corners):
                continue
            loud = (object_id, feature_id) == self._candidate_emphasis
            self._candidate_actors.append(
                self.renderer.add_surface(
                    corners,
                    _triangle_faces(len(corners) // 3),
                    name=f"candidate:{index}",
                    style=SurfaceStyle(
                        colour=CANDIDATE_COLOUR,
                        opacity=EMPHASIS_OPACITY if loud else CANDIDATE_OPACITY,
                        backface_colour=CANDIDATE_COLOUR,
                        lighting=False,
                        pickable=False,
                    ),
                )
            )
            middle = corners.mean(axis=0)
            marks.append(((float(middle[0]), float(middle[1]), float(middle[2])), feature_id))

        if marks:
            self._candidate_actors.append(
                self.renderer.add_labels(
                    np.asarray([point for point, _text in marks], dtype=float),
                    [text for _point, text in marks],
                    name="candidate-labels",
                    style=LabelStyle(
                        text_colour=CANDIDATE_COLOUR, font_size=12, always_visible=True
                    ),
                )
            )
        self._draw()

    @property
    def candidates(self) -> tuple[tuple[str, str], ...]:
        """Welche Kandidaten gerade leuchten — Auskunft für Tests und Dialog."""
        return self._candidates

    def _redraw_feature_patch(self) -> None:
        """Die Dreiecke des gewählten Merkmals in der Auswahlfarbe über dem Körper.

        Ohne sie hieß „Bohrung gewählt", dass der ganze Körper aufleuchtet —
        die Auswahl zeigte das Objekt und nicht die Stelle. Eine
        Bohrungsmarkierung verschließt die Öffnung nicht: Ihre Innenwand wird
        von beiden Öffnungen durchscheinend gezeichnet; andere Merkmalsflächen
        bleiben deckend und beidseitig sichtbar (``ansicht.md``).
        """
        if self.renderer is None:
            return
        for patch in self._feature_patches.values():
            self.renderer.remove(patch)
        if (
            self._feature_patch is not None
            and self._feature_patch not in self._feature_patches.values()
        ):
            self.renderer.remove(self._feature_patch)
        self._feature_patches.clear()
        self._feature_patch = None
        if self._selection_marking_hidden() or self._result is None:
            return

        import numpy as np

        selected: dict[ObjectId, list[FeatureId]] = {}
        for object_id, feature_id in self.highlighted_feature_refs():
            selected.setdefault(object_id, []).append(feature_id)
        for object_id, feature_ids in selected.items():
            entry = self._result.scene.objects.get(object_id)
            raw = getattr(entry.mesh, "raw", None) if entry is not None else None
            if entry is None or raw is None:
                continue
            highlighted = tuple(
                dict.fromkeys(
                    index
                    for feature_id in feature_ids
                    for index in self._face_indices(object_id, feature_id)
                )
            )
            if not highlighted:
                continue
            chosen = np.asarray(highlighted, dtype=np.int64)
            corners = self._lifted_corners(
                raw, chosen, self._patch_lift(), self._shown_offset(entry, self._result)
            )
            if not len(corners):
                continue
            features = [
                feature
                for feature_id in feature_ids
                if (feature := entry.features.get(feature_id)) is not None
            ]
            hole_surface = bool(features) and all(feature.kind == "hole" for feature in features)
            style = (
                SurfaceStyle(
                    colour=SELECTED_COLOUR,
                    opacity=SELECTED_HOLE_OPACITY,
                    backface_colour=SELECTED_COLOUR,
                    backface_opacity=SELECTED_HOLE_OPACITY,
                    lighting=False,
                    pickable=False,
                )
                if hole_surface
                else SurfaceStyle(
                    colour=SELECTED_COLOUR,
                    backface_colour=SELECTED_COLOUR,
                    lighting=False,
                    pickable=False,
                )
            )
            patch = self.renderer.add_surface(
                corners,
                _triangle_faces(len(corners) // 3),
                name="feature-patch"
                if object_id == self._selected
                else f"feature-patch:{object_id}",
                style=style,
            )
            self._feature_patches[object_id] = patch
            if object_id == self._selected:
                self._feature_patch = patch

    def _redraw_protected_patch(self) -> None:
        """Gesperrte Sichtflächen (§22.3): eine Tönung samt Schraffur darüber.

        Die Striche liegen noch eine Spur höher als die Tönung, sonst
        streiten sie mit ihr um dieselbe Tiefe und flimmern.
        """
        if self.renderer is None:
            return
        for actor in (self._protected_patch, self._protected_hatch):
            if actor is not None:
                self.renderer.remove(actor)
        self._protected_patch = None
        self._protected_hatch = None
        if not self._protected or self._result is None:
            return

        import numpy as np

        lift = max(self._scene_size() * FEATURE_PATCH_LIFT, EPS_GEOM)
        spacing = max(self._scene_size() * PROTECTED_HATCH_SPACING, EPS_GEOM)
        corners: list[Any] = []
        strokes: list[tuple[Vec3, Vec3]] = []
        for object_id, features in self._protected.items():
            entry = self._result.scene.objects.get(object_id)
            raw = getattr(entry.mesh, "raw", None) if entry is not None else None
            if entry is None or raw is None or not self._in_pick_view(object_id, entry):
                continue
            offset = self._shown_offset(entry, self._result)
            for feature_id in features:
                chosen = self._face_indices(object_id, feature_id)
                if not chosen:
                    continue
                index = np.asarray(chosen, dtype=np.int64)
                normals = np.asarray(raw.face_normals, dtype=float)[index]
                patch = self._lifted_corners(raw, index, lift, offset)
                if not len(patch):
                    continue
                corners.append(patch)
                middle = normals.mean(axis=0)
                # Auch der zweite Abstand gegen Flimmern gehört in dieselben
                # Halbräume; die Rechnung benutzt dabei Szenenkoordinaten.
                raised = self._lift_within_section(patch - offset, middle * lift) + offset
                strokes.extend(hatch_lines(raised, tuple(middle), spacing))
        if not corners:
            return

        points = np.vstack(corners)
        self._protected_patch = self.renderer.add_surface(
            points,
            _triangle_faces(len(points) // 3),
            name="protected-patch",
            style=SurfaceStyle(
                colour=PROTECTED_COLOUR,
                opacity=PROTECTED_OPACITY,
                backface_colour=PROTECTED_COLOUR,
                backface_opacity=PROTECTED_OPACITY,
                lighting=False,
                pickable=False,
            ),
        )
        if not strokes:
            return
        ends = np.asarray([end for stroke in strokes for end in stroke], dtype=float)
        self._protected_hatch = self.renderer.add_lines(
            ends,
            name="protected-hatch",
            colour=PROTECTED_HATCH_COLOUR,
            width=float(PROTECTED_HATCH_WIDTH),
        )

    def _redraw_hover_patch(self) -> None:
        """Die durchscheinende Fläche unter dem ruhenden Zeiger (§18.5).

        Schweben und Auswahl sind zwei sichtbare Zustände: halbdurchsichtig
        hier, deckend dort. Was schon gewählt ist, bekommt keine zweite
        Fläche, und eine Vorschau besitzt die Modellfarben allein.
        """
        if self.renderer is None:
            return
        if self._hover_patch is not None:
            self.renderer.remove(self._hover_patch)
            self._hover_patch = None
        if (
            self._selection_marking_hidden()
            or self._hovered_object is None
            or self._hovered_feature is None
            or (self._hovered_object, self._hovered_feature) in self.highlighted_feature_refs()
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

        chosen = np.asarray(indices, dtype=np.int64)
        corners = self._lifted_corners(
            raw, chosen, self._patch_lift(), self._shown_offset(entry, self._result)
        )
        if not len(corners):
            return
        feature = entry.features.get(self._hovered_feature)
        hole_surface = feature is not None and feature.kind == "hole"
        hover_opacity = HOVERED_HOLE_OPACITY if hole_surface else HOVERED_FEATURE_OPACITY
        self._hover_patch = self.renderer.add_surface(
            corners,
            _triangle_faces(len(corners) // 3),
            name="feature-hover",
            style=SurfaceStyle(
                colour=FEATURE_LABEL_COLOUR,
                opacity=hover_opacity,
                backface_colour=FEATURE_LABEL_COLOUR,
                backface_opacity=hover_opacity,
                lighting=False,
                pickable=False,
            ),
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

        hit = self._hit_at(point)
        if hit is not None:
            if hit.feature_id is not None:
                return hit.feature_id, 0.0
            feature_id = self._feature_on_cell(hit.object_id, hit.cell)
            if feature_id is not None:
                return feature_id, 0.0
        target = np.asarray(point, dtype=float)
        # Der Körper unter dem Zeiger, sonst der gewählte — und die Reichweite
        # gehört dem, dessen Merkmale gesucht werden, nicht dem anderen.
        source = self._object_at(point)
        prepared = self._prepared_features(source)
        if not prepared and hit is None:
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

    def _feature_on_cell(self, object_id: ObjectId, cell: int) -> FeatureId | None:
        """Eindeutige Dreieckszuordnung, kompakt je Auswertung vorbereitet.

        Überlappende Merkmale behalten den bestehenden Ortsfang. Ein Index
        aus einem geschnittenen oder dezimierten Anzeigenetz gilt hier nie.
        """
        if self._result is None or object_id not in self._original_pick_cells or cell < 0:
            return None
        entry = self._result.scene.objects.get(object_id)
        raw = getattr(entry.mesh, "raw", None) if entry is not None else None
        if entry is None or raw is None or cell >= len(raw.faces):
            return None
        cached = self._feature_cells.get(object_id)
        if cached is None:
            import numpy as np

            ids = tuple(entry.features)
            cells = np.full(len(raw.faces), -1, dtype=np.int32)
            for number, feature in enumerate(entry.features.values()):
                indices = np.asarray(feature.face_indices, dtype=np.int64)
                indices = indices[(indices >= 0) & (indices < len(cells))]
                previous = cells[indices]
                cells[indices] = np.where(previous == -1, number, -2)
            cached = ids, cells
            self._feature_cells[object_id] = cached
        ids, cells = cached
        number = int(cells[cell])
        return ids[number] if number >= 0 else None

    def _hit_at(self, point: Vec3, *, view_space: bool = False) -> _SelectionHit | None:
        """Nur der aktuelle Treffer an genau diesem Ort ergänzt einen Punkt.

        Jeder Pick und jeder Szenenaufbau ersetzt ihn; andere Raumfragen
        bleiben unabhängig von der letzten Mausposition.
        """
        hit = self._selection_hit
        if hit is None or self._result is None:
            return None
        entry = self._result.scene.objects.get(hit.object_id)
        if entry is None or not self._in_pick_view(hit.object_id, entry):
            return None
        at = hit.view_point if view_space else hit.scene_point
        return hit if math.dist(at, point) <= EPS_GEOM else None

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
            if not _is_opening_feature(feature):
                continue
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

    def _bore_aim(
        self, origin: Vec3, direction: Vec3, until: float, *, view_space: bool = False
    ) -> Vec3 | None:
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
        origin_point = np.asarray(origin, dtype=float)

        best_enter = math.inf
        best_radius = math.inf
        found: Vec3 | None = None
        picked: _SelectionHit | None = None
        for object_id, entry in self._result.scene.objects.items():
            visible = (
                self._in_pick_view(object_id, entry)
                if view_space
                else self._in_view(object_id, entry)
            )
            if not visible:
                continue
            shift = self._shown_offset(entry, self._result) if view_space else np.zeros(3)
            start = origin_point - shift
            # Die Reichweite ist die **Zielhilfe**: Gezielt wird in Pixeln, und
            # der Rand einer M3-Bohrung ist an einem großen Teil wenige davon
            # breit. Derselbe Wert wie beim Klick auf die Fläche eines Merkmals,
            # denn es ist dieselbe Frage — wie weit daneben meint noch dies.
            reach = self._feature_reach(object_id)
            for feature_id, centre, line, radius, bounds in self._prepared_bores(object_id):
                ray_start = (float(start[0]), float(start[1]), float(start[2]))
                ray_direction = (float(forward[0]), float(forward[1]), float(forward[2]))
                ray_axis = (float(line[0]), float(line[1]), float(line[2]))
                span = bore_span(
                    ray_start,
                    ray_direction,
                    centre,
                    ray_axis,
                    radius + reach,
                    bounds,
                )
                if span is None or span[1] <= 0.0 or span[0] > until + EPS_GEOM:
                    continue
                visible_span = bore_span(ray_start, ray_direction, centre, ray_axis, radius, bounds)
                if visible_span is None or visible_span[0] > until + EPS_GEOM:
                    # Die Zielhilfe gilt seitlich am Öffnungsrand. Sie darf
                    # weder eine Rückwand axial verlängern noch seitliches
                    # Material vor der wirklichen Bohrung überbrücken.
                    along_ray = float(forward @ line)
                    if abs(along_ray) <= EPS_GEOM or not math.isfinite(until):
                        continue
                    entrance = bounds[0] if along_ray > 0.0 else bounds[1]
                    at_entrance = (entrance - float(start @ line)) / along_ray
                    if abs(at_entrance - until) > EPS_GEOM:
                        continue
                enter = max(span[0], 0.0)
                leave = min(span[1], until)
                if leave < enter - EPS_GEOM:
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
                scene_point = (float(point[0]), float(point[1]), float(point[2]))
                shown = point + shift
                found = (float(shown[0]), float(shown[1]), float(shown[2]))
                picked = _SelectionHit(object_id, scene_point, found, feature_id=feature_id)
        if view_space and picked is not None:
            self._selection_hit = picked
        return found

    def _prepared_bores(self, object_id: ObjectId) -> list[_BoreTarget]:
        """Achsen und Längsgrenzen einmal berechnen, auch bei vielen Merkmalen.

        Der Hover braucht keine Kopie sämtlicher ebener Merkmalsflächen und
        keine erneute Projektion aller Bohrungsdreiecke bei jedem Zielwechsel.
        Die Grenzen kommen weiter aus der Geometrie, nicht aus einem Tiefenwert.
        """
        cached = self._feature_bores.get(object_id)
        if cached is not None:
            return cached
        entry = self._result.scene.objects.get(object_id) if self._result else None
        if entry is None:
            return []

        import numpy as np

        raw = getattr(entry.mesh, "raw", None)
        prepared: list[_BoreTarget] = []
        for feature_id, feature in entry.features.items():
            # Ein Durchmesser benennt auch Ringrundungen, Kehlen und Zapfen.
            # Ihre Zylinderhülle ist keine Öffnung vor der sichtbaren Fläche.
            if not _is_opening_feature(feature):
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
            indices = [
                index
                for index in feature.face_indices
                if raw is not None and 0 <= index < len(raw.faces)
            ]
            points = (
                raw.vertices[raw.faces[indices]].reshape(-1, 3)
                if raw is not None and indices
                else np.asarray([centre], dtype=float)
            )
            lengthwise = points @ line
            bounds = (float(lengthwise.min()), float(lengthwise.max()))
            prepared.append(_BoreTarget(feature_id, centre, line, float(diameter) / 2.0, bounds))
        self._feature_bores[object_id] = prepared
        return prepared

    def _through_aim(
        self, origin: Vec3, direction: Vec3, *, view_space: bool = False
    ) -> Vec3 | None:
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
        origin_point = np.asarray(origin, dtype=float)

        best_enter = math.inf
        found: Vec3 | None = None
        picked: _SelectionHit | None = None
        for object_id, entry in self._result.scene.objects.items():
            visible = (
                self._in_pick_view(object_id, entry)
                if view_space
                else self._in_view(object_id, entry)
            )
            if not visible:
                continue
            shift = self._shown_offset(entry, self._result) if view_space else np.zeros(3)
            start = origin_point - shift
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
            scene_point = (float(middle[0]), float(middle[1]), float(middle[2]))
            shown = middle + shift
            found = (float(shown[0]), float(shown[1]), float(shown[2]))
            picked = _SelectionHit(object_id, scene_point, found)
        if view_space and picked is not None:
            self._selection_hit = picked
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
        """Der Sichtstrahl durch einen Bildpunkt: Startpunkt und Richtung.

        Aus der nahen und der fernen Schnittebene der Kamera — eine Blickrichtung
        und kein Punkt, damit ein Klick auch das trifft, was der Strahl
        durchquert (:meth:`_aim_at`, „Ein Klick ist eine Blickrichtung").
        """
        if self.renderer is None:
            return None
        near = self.renderer.display_to_world(x, y, 0.0)
        far = self.renderer.display_to_world(x, y, 1.0)
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
        if self.renderer is None:
            return None
        point = self._world_at(x, y)
        ray = self._pick_ray(x, y)
        if ray is None:
            return point
        origin, direction = ray

        import numpy as np

        forward = np.asarray(direction, dtype=float)
        forward = forward / float(np.linalg.norm(forward))
        until = (
            float((np.asarray(point, dtype=float) - np.asarray(origin, dtype=float)) @ forward)
            if point is not None
            else math.inf
        )
        # Jeder Körper hat seinen eigenen Ansichtsversatz. Ein einzelner
        # Versatz vom Auftreffpunkt trifft auf anderen Platten oder bei der
        # Explosionsansicht das falsche Loch.
        aimed = self._bore_aim(origin, direction, until, view_space=True)
        if aimed is None and point is None:
            # Nichts getroffen und keine Bohrung im Weg: Vielleicht geht der
            # Blick durch eine Öffnung des Körpers, und dann ist er gemeint und
            # nicht das Nichts (:meth:`_through_aim`).
            aimed = self._through_aim(origin, direction, view_space=True)
        if aimed is None:
            return point
        return aimed

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
        return 2 if self.highlighted_feature_refs() else 1

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
        if self.renderer is not None:
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
        if self.renderer is not None:
            self._draw()

    @property
    def difference_held(self) -> bool:
        return self._difference_held

    def _redraw_difference(self) -> None:
        if self.renderer is None:
            return
        for actor in self._difference_actors:
            self.renderer.remove(actor)
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
        if self.renderer is None or mesh is None or not len(mesh.raw.faces):
            return
        import numpy as np

        raw = mesh.raw
        self._difference_actors.append(
            self.renderer.add_surface(
                np.asarray(raw.vertices, dtype=float) + shift,
                np.asarray(raw.faces, dtype=np.int64),
                name=name,
                style=SurfaceStyle(colour=colour, opacity=opacity),
            )
        )

    def set_difference_palette(self, palette: DiffPalette) -> None:
        """Blau/Orange, Rot/Grün oder Graustufen — die Wahl aus §19.1."""
        self._diff_palette = palette
        self._redraw_difference()
        if not self.banner.isHidden():
            # Die Legende erklärt Farben; die haben sich gerade geändert.
            self.banner.show_preview(self.banner.note.text(), palette, self.banner.hint.text())
        if self.renderer is not None:
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
        self._queue_feature_label_layout()

    def _place_orientation_widget(self) -> None:
        """Das Achsenkreuz in seine Ecke setzen — in Bildpunkten gerechnet
        (:func:`orientation_corner`), bei jeder Größenänderung neu."""
        if self.renderer is None:
            return
        try:
            self.renderer.place_axes_marker(orientation_corner(self.width(), self.height()))
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
            self.show_scene(self._scene_for_rebuild())
        elif was is not None and layer is not None and was.z != layer.z:
            self._layer_rebuild.start()
        self._redraw_layer()
        if self.renderer is not None:
            self._draw()

    def _redraw_layer(self) -> None:
        if self.renderer is None:
            return
        for actor in self._layer_actors:
            self.renderer.remove(actor)
        self._layer_actors.clear()
        layer = self._layer
        if layer is None:
            return

        # Ein Actor je Rolle, nicht je Ring: eine texturierte Schicht hat
        # tausende Konturen, und ebenso viele einzelne ``add_lines``-Aufrufe
        # machten aus einem Schieberschritt Sekunden — ein Renderer zahlt je
        # Actor, nicht je Linie (unter VTK gemessen; bei pygfx ist jeder Actor
        # ebenso ein eigenes Objekt in der Szene).
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
        """Geschlossene Konturen einer Schicht als **einen** Aktor je Rolle.

        Eine texturierte Schicht hat tausende Konturen, und ebenso viele
        einzelne Aktoren machten aus einem Schieberschritt Sekunden — ein
        Renderer zahlt je Aktor, nicht je Linie (unter VTK gemessen; bei pygfx
        ist jeder Aktor ebenso ein eigenes Objekt in der Szene). Ein
        geschlossener Ring ist jeder Punkt zweimal, bis auf die Enden — und
        Ringe hängen nicht aneinander.
        """
        if self.renderer is None:
            return
        import numpy as np

        pieces = []
        for ring in rings:
            if len(ring) < 2:
                continue
            flat = np.asarray(ring, dtype=float)
            points = np.column_stack([flat, np.full(len(flat), z)])
            pieces.append(np.repeat(points, 2, axis=0)[1:-1])
        if not pieces:
            return
        self._layer_actors.append(
            self.renderer.add_lines(np.vstack(pieces), name=name, colour=colour, width=float(width))
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
        self.show_scene(self._scene_for_rebuild())
        # ``show_scene`` zeichnet die Maße nur im Leer-Zweig neu — nach einem
        # Einheitenwechsel stünden sie sonst in der alten Einheit da.
        self._redraw_measurements()

    def set_snapping(self, grid_step: float, angle_step: float) -> None:
        """Raster- und Winkeleinrasten für den Gizmo."""
        self._grid_step = grid_step
        self._angle_step = angle_step

    def gizmo_target(self) -> Feature | None:
        """Die Fläche, an der der Gizmo hängt — oder ``None`` für das Objekt.

        Als eigene Auskunft und nicht als Zustand des Renderers, damit die
        Regel prüfbar bleibt: offscreen gibt es keinen Renderer, und ein Test,
        der sich dort überspringt, prüft nie etwas.

        **Nur Flächen**, und das ist keine Einschränkung, sondern die Frage:
        Diese Methode beantwortet „geht der Zug entlang einer Normalen"
        (Press/Pull, ``faceDragged``). Wo der Griff *sitzt*, beantwortet
        :meth:`gizmo_feature` — die beiden liefen einmal zusammen und
        deckten damit nur den Fall ab, den die Fläche stellt.
        """
        if self._selected_feature is None:
            return None
        feature = self._features_of_selection().get(self._selected_feature)
        if feature is None or feature.kind != "face":
            return None
        if feature.params.get("normal") is None or feature.params.get("centre") is None:
            return None
        return feature

    def gizmo_feature(self) -> Feature | None:
        """Das Merkmal, an dem der Griff **sitzt** — oder ``None`` für das Objekt.

        „Wenn man die Wulst wählt verschiebt man die Wulst, immer das
        Ausgewählte" (Robert, 03.09.2026). Der Griff hing bis dahin nur an
        Flächen; bei jedem anderen Merkmal sprang er in die Mitte des
        Hüllquaders. Gemessen an ``motor-mountstp.stl`` mit 27 Merkmalen:

            gewählt       Merkmal sitzt bei      Griff sass bei
            Fläche        (-3,0 / 0,4 / 0,0)     auf der Fläche
            Bohrung       (-13 / -13 / 2)        (0 / 0 / 30)
            Verrundung    (-13 / -4,5 / 10)      (0 / 0 / 30)

        Achtundzwanzig Millimeter daneben, am anderen Ende des Teils — und
        nichts sagte es.

        **Welche Arten mitkommen, entscheidet das Register und keine Liste
        hier.** Ein Griff, der nichts auslösen kann, wäre schlimmer als
        keiner: Es zählt, ob es eine Operation gibt, die dieses Merkmal
        versetzt. Wächst deren ``applies_to``, wächst der Griff mit; fällt
        eine Art heraus, verschwindet er dort, ohne dass jemand daran denken
        muss. Welche das gerade sind, sagt :func:`movable_feature_kinds` —
        und nicht dieser Satz, der schon einmal veraltet ist.
        """
        if self._selected_feature is None:
            return None
        feature = self._features_of_selection().get(self._selected_feature)
        if feature is None or feature.params.get("centre") is None:
            return None
        if feature.kind == "face":
            return feature if feature.params.get("normal") is not None else None
        return feature if feature.kind in movable_feature_kinds() else None

    def set_gizmo(self, active: bool) -> None:
        """Den Bewegungsgriff an die Auswahl hängen oder abnehmen (§18.11).

        Frisch gebaut bei jedem Aufruf — ein stehen gelassener Griff rechnete
        gegen die Matrix der vorigen Auswahl, und nach einer Auswertung hinge
        er an einem Aktor, der nicht mehr im Bild ist. Die Griffe nehmen ihre
        Gesten in :meth:`_on_pointer` vor der Kamera.
        """
        self._gizmo_wanted = active
        if self.renderer is None:
            self.gizmoStatus.emit("")
            return
        self._detach_gizmo()
        if not active or self._selected is None:
            self.gizmoStatus.emit("")
            return
        # **Wo er sitzt und was er tut, sind zwei Fragen.** ``gizmo_feature``
        # beantwortet die erste (jedes versetzbare Merkmal), ``gizmo_target``
        # die zweite (nur eine Fläche kennt Press/Pull entlang ihrer Normalen).
        chosen = self.gizmo_feature()
        actor = (
            self._face_handle(chosen) if chosen is not None else self._actors.get(self._selected)
        )
        if actor is None:
            self.gizmoStatus.emit("")
            return
        self.gizmoStatus.emit(gizmo_sentence(chosen))
        scale = self._gizmo_scale_for(
            actor, self._face_seat[0] if chosen is not None and self._face_seat else None
        )
        self._gizmo = Gizmo(
            self.renderer,
            actor,
            scale=scale,
            line_radius=GIZMO_LINE_RADIUS,
            release_callback=self._on_gizmo_released,
            interact_callback=self._on_gizmo_interacted,
        )
        if chosen is None:
            # Das dritte Drittel von §18.11: Der Griff verschiebt und dreht,
            # der Würfel skaliert. **Nur am ganzen Objekt** — ein Merkmal hat
            # keine Größe, die dieser Würfel ändern könnte: Eine Fläche kennt
            # nur vor und zurück, und eine Bohrung wächst über ihren
            # Durchmesser, nicht über einen Hüllquader. Ein Würfel daneben
            # skalierte still das Teil, während der Griff daneben das Loch
            # bewegt — zwei Gesten am selben Ort mit verschiedenen Zielen.
            self._scale_handle = ScaleHandle(
                self.renderer,
                actor,
                scale=scale,
                colour=MEASURE_COLOUR,
                release_callback=self._on_scale_released,
                interact_callback=self._on_scale_interacted,
            )
        self._label_gizmo(actor)

    def _gizmo_scale_for(self, actor: Any, centre: Any = None) -> float:
        """Der Massstab des Griffs — gross genug, um ihn zu treffen.

        **Marke und Werkzeug ziehen gegeneinander, und eine Millimeterzahl kann
        nur eines von beiden.** Die Scheibe soll das Merkmal genau abdecken
        (:meth:`_handle_radius`), also klein sein. Der Griff hängt an ihr, und
        der Griff rechnet seine Pfeillänge aus ``target.length() *
        GIZMO_SCALE`` — bei einer Ø 4-Bohrung sind das 1,7 mm Pfeil und
        0,20 mm Schaft, auf einem 105-mm-Teil rund zehn Bildpunkte lang und
        gut einer dick. Der Kommentar an :data:`GIZMO_SCALE` nennt vierzig
        Bildpunkte ausdrücklich als **zu klein** (3d-druck-85, 03.09.2026).

        **Treffbarkeit ist eine Grösse in Bildpunkten, keine in Millimetern**
        — sie hängt am Zoom. Dieselbe Datei weiss das an drei anderen Stellen
        (:data:`PULL_HIT_PIXELS`, :data:`CURSOR_PIXELS`,
        :data:`PULL_HANDLE_PIXELS`), und hier fehlte es. Der Anteil gilt
        deshalb weiter als Vorgabe; unterschreitet er
        :data:`GIZMO_LEAST_PIXELS`, wächst der Griff auf dieses Mass.

        Damit ist der Widerspruch aufgelöst, an dem heute zwei Fassungen
        gescheitert sind: Die Marke bleibt am Merkmal, der Griff wird
        bedienbar, und keiner von beiden muss dafür der anderen folgen.
        """
        length = float(actor.length())
        wanted = length * GIZMO_SCALE
        if centre is None:
            # Ohne Angabe der Sitz der Marke — und ohne Marke die Mitte des
            # Aktors, an dem der Griff hängt.
            centre = self._face_seat[0] if self._face_seat else actor.centre()
        # **Ohne Projektion gilt der Anteil**, und zwar ohne dass der Griff
        # deshalb ausfällt: Offscreen gibt es keinen Renderer, und dort sieht
        # den Griff ohnehin niemand. Ihn hier von der Projektion abhängig zu
        # machen hiesse, jeden Test, der einen Griff anhängt, an eine
        # vollständige Kamera-Attrappe zu binden — dreizehn wurden dabei rot,
        # keiner davon an der Sache.
        # **Und wenn die Projektion nichts hergibt, gilt der Anteil.** Der
        # Deckel in Bildpunkten ist eine Verbesserung, kein Muss: Offscreen
        # gibt es keinen Renderer, in Prüfständen keine vollständige Kamera,
        # und in beiden Lagen sieht den Griff ohnehin niemand. Ihn davon
        # abhängig zu machen band dreizehn Tests an eine Kamera-Attrappe, und
        # keiner von ihnen wurde an seiner Sache rot.
        try:
            scale = self._pixels_per_mm_at(centre)
        except Exception:
            scale = None
        if scale is None or scale <= EPS_GEOM or length <= EPS_GEOM:
            return GIZMO_SCALE
        least = GIZMO_LEAST_PIXELS / scale
        return max(GIZMO_SCALE, least / length) if wanted < least else GIZMO_SCALE

    def _detach_gizmo(self) -> None:
        """Nimmt Griff, Beschriftung und Flächenscheibe aus dem Bild.

        Über ``Gizmo.remove()``. Bis zum 05.09.2026 stand hier ein ``Off()``
        an PyVistas Widget, das es dort nie gab — der ``AttributeError``
        verschwand in Qts Slot-Behandlung, und der Griff blieb stehen, obwohl
        der Schalter aus war. Anders als :meth:`set_gizmo` lässt das den Schalterzustand in
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
        # **Und alles, was zum Zug gehört.** Bogen, Geisterring und der
        # Schattenversatz hingen nur an `_end_drag`, also am Loslassen — aber
        # ein Zug endet nicht immer dort:
        #
        #   * Ein Undo, ein Werkzeugwechsel oder ein geschlossenes Projekt
        #     hängen den Griff ab, ohne dass jemand losgelassen hat.
        #   * Und wer während des Zugs eine Ziffer tippt, gibt ihn an die
        #     Tastatur ab: ``_on_gizmo_released`` geht bei ``drag_bar.typing``
        #     über ``set_gizmo`` hinaus, und ``_end_drag`` läuft nie
        #     (3d-druck-85, 03.09.2026).
        #
        # Alle drei tragen ``MEASURE_COLOUR`` — dieselbe Farbe wie Auswahl und
        # Messung. Was stehen bleibt, sieht aus wie eine Geste, die noch läuft.
        self._drop_turn_arc()
        self._drop_ghost()
        self._reset_shadow_offset()

    def gizmo_face_label(self) -> tuple[str, tuple[float, float, float]] | None:
        """Name und Richtung der Fläche am Griff — oder ``None`` fürs Objekt.

        **Als eigene Auskunft und nicht als Zeilen in ``_label_gizmo``**, aus
        demselben Grund wie bei :meth:`gizmo_target`: Jene Methode steigt bei
        ``self.renderer is None`` sofort aus, und offscreen gibt es keinen
        Renderer. Ein Test, der sie dort ruft, ist grün, ohne etwas geprüft zu
        haben — und die Verkabelung zwischen Auswahl und Beschriftung wäre
        genau das ungeprüfte Stück zwischen zwei geprüften Enden.
        """
        chosen = self.gizmo_target()
        if chosen is None:
            return None
        normal = chosen.params.get("normal")
        if not isinstance(normal, tuple | list) or len(normal) != 3:
            return None
        return (
            feature_name(self._selected_feature or "", chosen),
            (float(normal[0]), float(normal[1]), float(normal[2])),
        )

    def _label_gizmo(self, actor: Item) -> None:
        """Die Buchstaben an den Achsen des Griffs — X, Y, Z, das S am Würfel,
        der Doppelpfeil an einer Fläche (§18.11).

        Hinter den Spitzen, im Maß der wirklichen Pfeillänge des Griffs.
        Reines ASCII, siehe :data:`FACE_ARROW`. Während des Zugs reisen die
        Buchstaben mit (:meth:`_on_gizmo_interacted`).
        """
        if self.renderer is None:
            return
        import numpy as np

        gizmo = self._gizmo
        length = (
            gizmo.arrow_length
            if gizmo is not None
            else float(actor.length()) * GIZMO_SCALE * ARROW_SHARE
        )
        centre = gizmo.origin if gizmo is not None else actor.centre()
        marks = gizmo_labels(centre, length, self.gizmo_face_label())
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
        base = np.asarray([point for point, _text in marks], dtype=float)
        texts = [text for _point, text in marks]
        self._gizmo_label_base = base
        self._gizmo_label_texts = texts
        self._gizmo_labels = self.renderer.add_labels(
            base.copy(),
            texts,
            name="gizmo_labels",
            # In der Körperfarbe des Themas: hell im dunklen, dunkel im
            # hellen. Die Kantenfarbe war für Text auf dem Hintergrund zu
            # leise — im Bild kaum zu lesen.
            style=LabelStyle(
                text_colour=self._object_colour, font_size=13, bold=True, always_visible=True
            ),
        )

    def _drop_gizmo_labels(self) -> None:
        if self._gizmo_labels is not None and self.renderer is not None:
            self.renderer.remove(self._gizmo_labels)
        self._gizmo_labels = None
        self._gizmo_label_base = None
        self._gizmo_label_texts = []

    def _on_gizmo_interacted(self, matrix: Any) -> Any:
        """Jeder Zwischenstand eines Zugs am Griff — und die Antwort darauf.

        Der Griff ruft mit der rohen Matrix und setzt, was zurückkommt: Hier
        sitzt der Magnet auf die Raste (§18.11, Robert: „freies drehen, aber
        kurzes einrasten bei allen 45 grad winkeln außer man dreht weiter").
        Was der Griff danach zeigt, ist die berichtigte Matrix, und dieselbe
        bekommen Beschriftung, Schatten, Drehbogen und Vorschau — bis zum
        05.09.2026 waren das zwei Beobachter am Interactor, und der eine sah
        noch die Matrix des vorigen Schritts.
        """
        import numpy as np

        applied = np.asarray(matrix, dtype=float)
        steps = decompose_transform(applied)
        corrected: np.ndarray | None = None
        if steps.turns and steps.axis is not None and self._gizmo is not None:
            settled = self._settled_angle(steps.angle)
            difference = settled - steps.angle
            if abs(difference) > EPS_DISPLAY:
                index = ("x", "y", "z").index(steps.axis)
                direction = self._gizmo.axes[index]
                # ``rotation_about`` im Kern, denn die Ansicht rechnet keine
                # Geometrie (§8).
                corrected = (
                    rotation_about(
                        (float(direction[0]), float(direction[1]), float(direction[2])),
                        self._gizmo.origin,
                        difference,
                    )
                    @ applied
                )
                applied = corrected
                steps = decompose_transform(applied)
        if self._gizmo_labels is not None and self._gizmo_label_base is not None:
            self._gizmo_labels.update_labels(
                moved_marks(self._gizmo_label_base, applied), self._gizmo_label_texts
            )
        self._drag_shadow(steps)
        self._draw_turn_arc(steps)
        self._drag_preview(steps)
        if (
            self._gizmo is not None
            and self._selected is not None
            and self._gizmo.target is self._actors.get(self._selected)
        ):
            # Der Griff zeichnet unmittelbar nach seinem Rückruf. Die
            # korrigierte Matrix gilt deshalb schon für dessen Konturen.
            self._sync_edge_preview(self._selected, applied)
        # Der Griff setzt seine Matrix erst nach diesem Rückruf. Im nächsten
        # Ereignisdurchlauf lesen alle Merkmalsmarken denselben neuen Aktorstand.
        self._queue_feature_label_layout()
        # **Der Ring erscheint mit dem ersten sichtbaren Stück des Zugs.** Ihn
        # schon beim Anhängen des Griffs zu zeigen hiesse, eine Bewegung zu
        # behaupten, die noch keine ist.
        if self._ghost_actor is None and (steps.moves or steps.turns):
            chosen = self.gizmo_feature()
            if chosen is not None:
                self._show_ghost(chosen)
        face = self.gizmo_target()
        if face is not None:
            normal = face.params["normal"]
            self._drag_kind = "face"
            self._drag_normal = (float(normal[0]), float(normal[1]), float(normal[2]))
            self.drag_bar.follow_length(tr("Fläche"), along_normal(steps.offset, self._drag_normal))
        elif steps.turns and steps.axis is not None:
            # **Gezeigt wird, was angewandt wird — der gerastete Wert.** Hier
            # stand der rohe, und das Loslassen rastete: Wer bei einem
            # Winkelfang von 15° um fünf Grad drehte, las „5,0°" mit und
            # bekam nichts (Robert, 03.09.2026: „bei bewegen geht das drehen
            # des modells nicht"). Mit dem gerasteten Wert springt die Zahl von
            # 0 auf 15 auf 30, und man sieht, worauf man einrastet.
            self._drag_kind = "turn"
            self._drag_axis = steps.axis
            self.drag_bar.follow(
                f"{tr('Winkel')} {steps.axis.upper()}",
                self._settled_angle(steps.angle),
                "°",
                1,
            )
        elif steps.moves:
            index = max(range(3), key=lambda axis: abs(steps.offset[axis]))
            dominant: Axis = ("x", "y", "z")[index]
            self._drag_kind = "move"
            self._drag_axis = dominant
            # Dieselbe Zusage wie beim Winkel darüber: der gerastete Weg.
            self.drag_bar.follow_length(
                dominant.upper(), snap_to_step(steps.offset[index], self._grid_step)
            )
        # Solange sich nichts bewegt hat, gibt es keine Achse und keine Zahl —
        # das Feld erscheint mit dem ersten sichtbaren Stück des Zugs.
        return corrected
        # Solange sich nichts bewegt hat, gibt es keine Achse und keine Zahl —
        # das Feld erscheint mit dem ersten sichtbaren Stück des Zugs.

    def _draw_turn_arc(self, steps: TransformSteps) -> None:
        """Der Bogen, der beim Drehen zeigt, wie weit — und wo er einrastet.

        **Der Radius ist der des Griffs, nicht der des Körpers.** Hier stand
        der Körperaktor, während ``set_gizmo`` bei einem gewählten Merkmal die
        Scheibe übergibt — der Bogen war damit sechsmal so gross wie das
        Werkzeug, dessen Drehung er zeigt (3d-druck-85, 03.09.2026).
        """
        if self.renderer is None or not steps.turns or steps.axis is None:
            return
        gizmo = self._gizmo
        if gizmo is None:
            return
        index = ("x", "y", "z").index(steps.axis)
        direction = gizmo.axes[index]
        origin = gizmo.origin
        radius = float(gizmo.target.length()) * self._gizmo_scale_for(gizmo.target, origin)
        points = turn_arc(origin, direction, radius, self._settled_angle(steps.angle))
        if points is None:
            return
        if self._arc_actor is not None:
            self.renderer.remove(self._arc_actor)
        self._arc_actor = self.renderer.add_lines(
            points, name="turn-arc", colour=MEASURE_COLOUR, width=3.0
        )

    def _reset_shadow_offset(self) -> None:
        """Stellt die Schatten an ihren Platz zurück.

        Sie standen während des Zugs versetzt (:meth:`_drag_shadow`); was
        danach gilt, entscheidet die Auswertung und zeichnet sie neu.

        **An zwei Wegen und nicht nur an einem.** Bis zum 03.09.2026 hing die
        Rückstellung allein an `_end_drag`, also am Loslassen. Wer *Bewegen*
        mitten im Zug ausschaltet, kommt dort nie an: Der Griff wird über
        `_detach_gizmo` abgehängt, und der Schatten blieb an der Zielstelle
        liegen, während das Teil an seinem Ort steht. Gemessen — nach
        `_detach_gizmo` trug er weiterhin (15,0 / -2,5 / 0).

        Derselbe Fall wie beim Drehbogen eine Stunde vorher, und dieselbe
        Antwort: Was zum Zug gehört, muss auch dann verschwinden, wenn der Zug
        nicht mit Loslassen endet.
        """
        for actors in self._shadow_owners.values():
            for actor in actors:
                actor.set_position((0.0, 0.0, 0.0))

    def _drop_turn_arc(self) -> None:
        """Nimmt den Bogen weg — der Zug ist vorbei."""
        if self._arc_actor is not None and self.renderer is not None:
            self.renderer.remove(self._arc_actor)
        self._arc_actor = None

    def _drag_shadow(self, steps: TransformSteps) -> None:
        """Zieht den Schatten mit, solange das Teil am Griff hängt (§18.6).

        **Er blieb stehen.** Gemessen am 03.09.2026 an einem Zug über 20 mm in
        X und 10 mm nach oben: null von drei Schattenaktoren bewegten sich,
        während der Körper wegwanderte. Ein Teil, dessen Schatten am Boden
        klebt, ist das Unnatürlichste, was ein 3D-Fenster zeigen kann — und
        Robert hat genau danach gefragt („vom aussehen noch anschaulicher, bzw
        natürlicher").

        **Die Rechnung ist eine Translation und sonst nichts.**
        :func:`shadow_points` wirft schräg: Jeder Punkt fällt um seine Höhe mal
        der waagerechten Lichtrichtung zur Seite. Eine Verschiebung um
        ``(dx, dy, dz)`` versetzt den Schatten damit um
        ``(dx + dz·rx, dy + dz·ry, 0)`` — und weil das für **jeden** Punkt
        dieselbe Verschiebung ist, genügt es, den fertigen Aktor zu versetzen.
        Nichts wird neu projiziert, nichts neu vernetzt.

        Dass die Höhe seitlich wirkt, ist dabei kein Nebeneffekt, sondern die
        beste Auskunft der ganzen Geste: Wer ein Teil anhebt, sieht seinen
        Schatten davonlaufen und weiß damit, wie hoch es steht — eine Zahl, die
        sonst nirgends im Bild steht.

        **Nur beim Verschieben.** Eine Drehung ändert die Silhouette, und die
        ließe sich nur durch Neuprojizieren einholen; der Schatten bleibt dann
        stehen, wie er es bisher immer tat, und das Loslassen richtet ihn. Ein
        falsch gedrehter Schatten wäre schlechter als ein stehender.
        """
        # **Eine Drehung schliesst das Mitziehen aus, auch wenn sie mit einer
        # Verschiebung kommt.** Der Versatz allein wäre dann ein halb richtiger
        # Schatten: an der neuen Stelle, in der alten Form. Stehen zu bleiben
        # ist die ehrlichere Vorschau, und das Loslassen richtet beides.
        if steps.turns or not steps.moves or self._selected is None:
            return
        actors = self._shadow_owners.get(self._selected)
        if not actors:
            return
        reach_x, reach_y = self._shadow_cast
        offset = (
            steps.offset[0] + steps.offset[2] * reach_x,
            steps.offset[1] + steps.offset[2] * reach_y,
            0.0,
        )
        for actor in actors:
            actor.set_position(offset)

    def _settled_angle(self, angle: float) -> float:
        """Der Winkel, der wirklich gilt — mit Raster oder mit Magnet.

        Zwei Fälle, und der zweite ist die Vorgabe: Hat die Leiste einen
        Winkelfang eingestellt, gilt er hart (`snap_to_step`) — das ist eine
        Ansage des Nutzers. Steht sie auf null, gilt der Magnet: frei drehen,
        aber bei jedem Vielfachen von :data:`TURN_MAGNET_STEP` kurz einrasten.
        """
        if self._angle_step > EPS_GEOM:
            return snap_to_step(angle, self._angle_step)
        return snap_near(angle, TURN_MAGNET_STEP, TURN_MAGNET_ZONE)

    def _on_scale_interacted(self, factor: float) -> None:
        """Der Zwischenstand am Skalierwürfel — die Zahl zum Zug (§18.11)."""
        self._drag_kind = "scale"
        self.drag_bar.follow(tr("Faktor"), factor, "", 3)
        if self._selected is not None:
            self._sync_edge_preview(self._selected)
        self._queue_feature_label_layout()

    def _face_handle(self, feature: Feature) -> Item | None:
        """Die Scheibe, an der der Griff hängt, wenn ein Merkmal gewählt ist.

        **Der Griff hängt an einer flachen Scheibe an der Öffnung, nicht am
        Zylinder.** Ein Zylinder über die volle Tiefe hat seinen Schwerpunkt
        auf halber Tiefe, und dort säße der Griff im Material (gemessen Mitte
        z = 17,50 statt 35,00). Werkzeug und Marke sind zwei Dinge: Die
        Vorschau in Merkmalsgestalt ist ein eigener Aktor
        (:meth:`_show_preview`), der beim Zug mitgeschoben wird.

        **Nicht anklickbar**, und das ist keine Feinheit: Die Scheibe liegt
        genau auf dem Merkmal, das sie zeigt. Ein Klick auf die Bohrung traf
        damit den Griff statt des Körpers, und die Bohrung liess sich nicht
        mehr auswählen (Robert, 03.09.2026).
        """
        import numpy as np

        if self.renderer is None:
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
        centre = self._handle_seat(feature, centre)
        # Normale bei einer Fläche, Achse bei einer Bohrung — und wo keines
        # von beidem steht, die Z-Achse: Die Scheibe soll das Merkmal zeigen,
        # nicht seine Ausrichtung behaupten.
        direction = feature.params.get("normal") or feature.params.get("axis") or (0.0, 0.0, 1.0)
        normal = np.asarray(direction, dtype=float)
        radius = self._handle_radius(feature)
        # Gemerkt, damit der Geisterring (:meth:`_show_ghost`) dieselbe Stelle
        # und dasselbe Mass nimmt. Zwei Rechnungen für denselben Sitz liefen
        # beim nächsten Zuwachs auseinander, und dann läge der Ring neben der
        # Marke, die er begleiten soll.
        self._face_seat = (tuple(float(v) for v in centre), tuple(float(v) for v in normal), radius)
        self._show_preview(feature, centre, normal, radius)
        vertices, faces = shapes.disc(centre, normal, radius, 24)
        self._face_actor = self.renderer.add_surface(
            vertices,
            faces,
            name="face-handle",
            style=SurfaceStyle(colour=MEASURE_COLOUR, opacity=0.6, pickable=False),
        )
        return self._face_actor

    def _handle_seat(self, feature: Feature, centre: Any) -> Any:
        """Wo der Griff eines Merkmals sitzt — an der Öffnung, nicht in der Mitte.

        „Ich bin mit meinem Mauszeiger auch immer drüber aber es klappt nicht
        … weder Seitenansicht, Schrägansicht noch Draufsicht" (Robert,
        03.09.2026). Gemessen am laufenden Fenster, Bohrung Ø 7,34 durch eine
        35 mm dicke Platte:

            Griffspanne     61,14 mm   — gross genug
            Ursprung z      17,50 mm   — **mitten im Material**
            Pfeil X, Y      getroffen -> der Körper
            Pfeil Z         getroffen -> ein Griff-Aktor

        Die erkannte Mitte einer Bohrung liegt auf halber Tiefe, also im
        Material. Die waagerechten Pfeile stecken damit im Teil, und aus jeder
        Blickrichtung liegt Wand davor — der Zeiger trifft sie, nicht den
        Griff. Bei einer **Fläche** stellt sich die Frage nicht: Ihre Mitte
        liegt auf der Oberfläche.

        Gesetzt wird deshalb auf die Öffnung, und zwar auf die dem Betrachter
        zugewandte: Bei einer durchgehenden Bohrung gibt es zwei, und die
        andere läge wieder hinter dem Teil. Fehlt eine Tiefe oder eine Achse,
        bleibt es bei der Mitte — dann ist sie das Beste, was wir wissen.
        """
        import numpy as np

        axis = feature.params.get("axis")
        depth = feature.params.get("depth")
        if axis is None or depth is None:
            return centre
        direction = np.asarray(axis, dtype=float)
        norm = float(np.linalg.norm(direction))
        if norm <= EPS_GEOM:
            return centre
        direction = direction / norm
        # Zur Kamera hin: Das Vorzeichen entscheidet, welche der beiden
        # Öffnungen vorn liegt. Ohne Renderer (offscreen) gilt die Achsrichtung.
        towards = 1.0
        if self.renderer is not None:
            eye = np.asarray(self.renderer.camera_pose().position, dtype=float)
            towards = (
                1.0
                if float(np.dot(eye - np.asarray(centre, dtype=float), direction)) >= 0
                else -1.0
            )
        return np.asarray(centre, dtype=float) + direction * (float(depth) / 2.0) * towards

    def _handle_radius(self, feature: Feature) -> float:
        """Wie gross die Scheibe wird, die ein gewähltes Merkmal markiert.

        „Ein kleiner Überstand ist noch da" (Robert, 03.09.2026). Die Scheibe
        mass sich an der **Objektdiagonale**, und das ist bei einem Merkmal die
        falsche Bezugsgrösse. Gemessen an seinem Teil (105 x 61,25 x 35, Bohrung
        Ø 7,34):

            Objektdiagonale   126,50 mm
            Scheibe daraus     15,18 mm   -> 2,1-mal die Bohrung
            Überstand je Seite  3,92 mm

        **Hat das Merkmal ein eigenes Mass, gilt das.** Eine Bohrung und ein
        Zapfen kennen ihren Durchmesser; die Scheibe deckt ihn dann genau ab
        und markiert, was gewählt ist, statt darüber hinauszustehen.

        **Eine Fläche hat keines**, und für sie bleibt der Anteil der
        Diagonale — der Grund dafür steht bei :data:`FACE_HANDLE_SHARE` und
        gilt weiter: Ein fester Radius verschwindet an einem Gehäuse und
        verdeckt einen Zapfen vollständig.

        Die Untergrenze bleibt in beiden Fällen: Eine Ø 0,5-Bohrung bekäme
        sonst eine Marke, die niemand sieht.
        """
        import numpy as np

        measure = feature.params.get("diameter") or feature.params.get("width")
        if measure is not None:
            return max(float(measure) / 2.0, FACE_HANDLE_MINIMUM)
        span = float(np.linalg.norm(np.asarray(self.bounds_size(), dtype=float)))
        return max(span * FACE_HANDLE_SHARE, FACE_HANDLE_MINIMUM)

    def _feature_shape(self, feature: Feature, centre: Any, normal: Any, radius: float) -> Any:
        """Die Gestalt eines Merkmals für Vorschau und Geist: eine Scheibe, oder
        bei einer Tiefe ein Zylinder, der vom Sitz aus in den Körper reicht.

        Der Sitz liegt an der Öffnung (:meth:`_handle_seat`); der Zylinder
        reicht von dort in den Körper hinein, also entgegen der Blickachse.
        """
        depth = feature.params.get("depth")
        if depth is None:
            return shapes.disc(centre, normal, radius, 24)
        import numpy as np

        direction = np.asarray(normal, dtype=float)
        axis = np.asarray(centre, dtype=float) - direction * float(depth) / 2.0
        return shapes.cylinder(axis, direction, radius, float(depth), 24)

    def _show_preview(self, feature: Feature, centre: Any, normal: Any, radius: float) -> None:
        """Das gewählte Merkmal in seiner Gestalt — ein eigener Aktor, damit
        der Griff an der Öffnung bleibt und die Vorschau beim Zug mitgeht."""
        self._drop_preview()
        if self.renderer is None:
            return
        vertices, faces = self._feature_shape(feature, centre, normal, radius)
        self._shape_actor = self.renderer.add_surface(
            vertices,
            faces,
            name="feature-preview",
            style=SurfaceStyle(colour=MEASURE_COLOUR, opacity=0.45, lighting=False, pickable=False),
        )

    def _drop_preview(self) -> None:
        """Nimmt die Vorschau weg."""
        if self._shape_actor is not None and self.renderer is not None:
            self.renderer.remove(self._shape_actor)
        self._shape_actor = None

    def _drag_preview(self, steps: TransformSteps) -> None:
        """Schiebt die Vorschau mit, solange gezogen wird.

        Der Griff hängt an der Scheibe und wandert von selbst; die Vorschau ist
        ein eigener Aktor und muss nachgeführt werden. Nur beim Verschieben —
        eine Drehung des Merkmals ändert seine Lage im Raum, und die liesse
        sich nur durch Neuaufbau einholen.
        """
        if self._shape_actor is None or not steps.moves or steps.turns:
            return
        self._shape_actor.set_position((steps.offset[0], steps.offset[1], steps.offset[2]))

    def _show_ghost(self, feature: Feature) -> None:
        """Der blasse Ring an der Ausgangsstelle, solange ein Merkmal gezogen wird.

        Ohne ihn zeigt der Zug nur, **wohin** — nicht, von wo. **Der Geist
        trägt dieselbe Gestalt wie die Marke** — bei einer Bohrung also
        ebenfalls einen Zylinder: Zwei Formen für dasselbe Merkmal an zwei
        Stellen läsen sich wie zwei verschiedene Dinge.
        """
        self._drop_ghost()
        if self.renderer is None:
            return
        seat = self._face_seat
        if seat is None:
            return
        centre, normal, radius = seat
        vertices, faces = self._feature_shape(feature, centre, normal, radius)
        self._ghost_actor = self.renderer.add_surface(
            vertices,
            faces,
            name="feature-ghost",
            style=SurfaceStyle(colour=MEASURE_COLOUR, opacity=0.35, lighting=False, pickable=False),
        )

    def _drop_ghost(self) -> None:
        """Nimmt den Ring weg — der Zug ist vorbei, die Auswertung gilt."""
        if self._ghost_actor is not None and self.renderer is not None:
            self.renderer.remove(self._ghost_actor)
        self._ghost_actor = None

    def _drop_face_handle(self) -> None:
        """Nimmt die Marke am Merkmal weg — **und die Vorschau mit ihr**.

        Sie gehören zusammen: Beide zeigen dasselbe gewählte Merkmal, und beide
        tragen ``MEASURE_COLOUR``, die dieselbe Farbe ist wie
        ``SELECTED_COLOUR``. Blieb die Vorschau stehen, während die Marke ging,
        leuchtete eine Bohrung weiter in der Auswahlfarbe, obwohl Statusleiste
        und Merkmalsfenster „Keine Auswahl" sagten (Robert, 03.09.2026, am
        Beispielprojekt ``weg1-halterung-anpassen.p3d``).

        **Der Hinweis, der es entschieden hat, war die fehlende Beschriftung**
        (3d-druck-85): Ein gewähltes Merkmal wird immer beschriftet. Eine
        orange Fläche ohne Namen ist also keine Auswahl, sondern eine Marke,
        die niemand abgeräumt hat.
        """
        self._drop_preview()
        if self._face_actor is not None and self.renderer is not None:
            self.renderer.remove(self._face_actor)
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
        nicht. Zweierlei hängt daran: Der Griff rechnet gegen die Matrix, die
        sein Ziel beim Anhängen hatte — ein stehen gelassener Griff wendete
        jede Bewegung beim zweiten Mal doppelt an. Und ein Zug unter der
        Fangschwelle erzeugt keine Operation; ohne das Neuanhängen bliebe der
        Körper im Bild dort stehen, wohin gezogen wurde, während die Szene ihn
        nie bewegt hat.

        Die Navigation bleibt dabei in Ruhe. PyVistas Widget (bis 05.09.2026)
        schaltete beim Greifen auf seinen Trackball-Stil um und stellte beim
        Loslassen *seinen* Standard wieder her, nicht unseren — jedes Zugende
        musste ``set_navigation`` rufen. Der eigene Griff nimmt sich die Geste
        vor dem Navigator und gibt sie danach wieder frei.
        """
        if self.drag_bar.typing:
            # Der Zug gehört der Tastatur (§18.11): das Loslassen wendet
            # nichts an, die Eingabetaste wird es tun. Der Griff wird frisch
            # gebaut — das Feld bleibt mit der getippten Zahl stehen.
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
            angle=self._settled_angle(steps.angle),
            scale=steps.scale,
        )
        # **Sitzt der Griff an einem Merkmal, bewegt der Zug das Merkmal.**
        # Ohne diese Abzweigung wäre der Griff eine Lüge: Er stünde auf der
        # gewählten Bohrung, sagte „Der Griff bewegt das gewählte Merkmal" —
        # und ``transformDragged`` verschöbe darunter das ganze Teil. Eine
        # Auskunft, die ankommt und nicht stimmt, ist schlimmer als keine.
        if self._emit_feature_drag(snapped):
            self._end_drag()
            return
        if snapped.moves or snapped.turns or snapped.resizes:
            self.transformDragged.emit(snapped)
        self._end_drag()

    def _emit_feature_drag(self, snapped: TransformSteps) -> bool:
        """Meldet den Zug als Merkmalsbewegung — oder sagt, dass keiner vorlag.

        **Genau eines von beidem**, und die Reihenfolge folgt dem Widget: Ein
        Zug am Ring dreht, ein Zug am Pfeil verschiebt, beides zugleich gibt
        es dort nicht. Zwei Meldungen wären zwei Transaktionen für eine Geste
        (§15.5).

        Der Rückgabewert sagt, ob der Zug hier verbraucht wurde. ``False``
        heisst nicht „nichts passiert", sondern „das gilt dem ganzen Teil" —
        der Aufrufer schickt ihn dann den gewohnten Weg.

        **Skalieren fehlt mit Absicht.** Ein Merkmal hat keine Grösse, die
        dieser Griff ändern könnte; darum steht an ihm auch kein
        Skalierwürfel (siehe :meth:`set_gizmo`).
        """
        chosen = self.gizmo_feature()
        if chosen is None or chosen.kind == "face":
            # Eine Fläche geht ihren eigenen Weg (Press/Pull, oben), und ohne
            # Merkmal gilt der Zug dem Körper.
            return False
        if snapped.turns and snapped.axis is not None:
            self.featureTurned.emit(chosen.id, snapped.axis, float(snapped.angle))
            return True
        if snapped.moves:
            centre = [float(value) for value in chosen.params["centre"]]
            target = (
                centre[0] + snapped.offset[0],
                centre[1] + snapped.offset[1],
                centre[2] + snapped.offset[2],
            )
            self.featureMoved.emit(chosen.id, target)
            return True
        # Ein Zug unter der Fangschwelle: verbraucht ist er trotzdem, denn er
        # gilt dem Merkmal. Ihn durchzulassen verschöbe das ganze Teil um
        # gerundete null — und `_end_drag` stellt das Bild ohnehin zurück.
        return True

    def _on_scale_released(self, factor: float) -> None:
        """Ein Zug am Skalierwürfel endet als Operation (§18.11, §2.1).

        Derselbe Dreischritt wie beim Loslassen des Gizmos, aus denselben
        Gründen: die Zahl melden, den Navigationsstil zurückholen, den Griff
        frisch anhängen — die Vorschau am alten Actor verschwindet mit ihm.
        """
        if self.drag_bar.typing:
            self.set_gizmo(self._gizmo_wanted)
            return
        if abs(factor - 1.0) > SCALE_UNCHANGED:
            self.scaleDragged.emit(float(factor))
        self._end_drag()

    def _end_drag(self) -> None:
        """Der Zug ist vorbei: Zahl weg, Zustand weg, Griff frisch.

        **Der Ziehgriff der Skizze geht einen anderen Weg zurück.** Er hat
        keinen Bewegungsgriff, den es frisch zu bauen gäbe, und keinen Ring,
        Geist oder Schatten abzuräumen; was dort weg muss, ist die Drahtform,
        und die kennt nur :meth:`_end_pull`. (Bis zum 05.09.2026 kam dazu,
        dass ``set_navigation`` von hier aus den VTK-Interaktionsstil mitten
        in der Geste neu gebaut hätte.)
        """
        if self._drag_kind == "pull":
            self._end_pull()
            return
        self._drag_kind = None
        self._drag_axis = None
        self._drag_normal = None
        # Der Ring gehört dem Zug; was danach gilt, zeigt die Auswertung.
        self._drop_ghost()
        self._drop_turn_arc()
        self._drop_preview()
        self._reset_shadow_offset()
        self.drag_bar.dismiss()
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
            # Die getippte Zahl ersetzt den Zeiger, also auch dessen Richtung:
            # Wer tippt, hat die Frage nach der Richtung beantwortet, und
            # ``_pull_takes`` prüft gegen genau diese Höhe.
            self.finish_sketch_pull()
            return
        self._end_drag()

    def eventFilter(self, watched: Any, event: Any) -> bool:  # noqa: N802 — Qt-Name
        """Während eines Zugs gehören Ziffern dem Wertfeld, nicht dem Renderer (§18.11).

        Der Filter sitzt auf der Grafikfläche des Renderers und auf dem Feld
        selbst: die erste Ziffer holt den Fokus ins Feld, Eingabetaste und Esc
        wirken von beiden Seiten. Alles andere geht durch — geschluckt wird
        nur, was zum Zug gehört, und nur solange einer läuft.
        """
        if stop_watching_the_dying(self, watched, event):
            return False
        kind = event.type()
        # Zeigergesten kommen als ``PointerEvent`` vom Renderer
        # (:meth:`_on_pointer`); hier bleibt nur das Betreten, das keine
        # Zeigergeste ist. Und nur vom Renderfenster: Der Filter sitzt auch
        # auf dem Wertfeld.
        renderer = getattr(self, "renderer", None)
        interactor = getattr(renderer, "widget", None) if renderer is not None else None
        if watched is interactor and kind == QEvent.Type.Enter:
            self._update_cursor()
        if watched is interactor and kind == QEvent.Type.Resize:
            self._queue_feature_label_layout()

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

            # **Doppelklick und Eingabetaste schließen einen begonnenen Zug**
            # (Z4). Beides stand im Hinweis der Zeichenleiste und wirkte nicht:
            # Die Empfänger sitzen im Zeichenbereich, und der ist hier
            # unsichtbar. Der Rückruf entscheidet selbst, ob gerade etwas
            # abzuschließen ist — sonst fällt das Ereignis durch wie zuvor.
            if self._sketch_finish_stroke is not None and kind in (
                QEvent.Type.MouseButtonDblClick,
                QEvent.Type.KeyPress,
            ):
                schliessend = kind == QEvent.Type.MouseButtonDblClick or event.key() in (
                    Qt.Key.Key_Return,
                    Qt.Key.Key_Enter,
                )
                if schliessend and self._sketch_finish_stroke():
                    return True

        if (
            kind == QEvent.Type.KeyPress
            and self._measure_mode != "off"
            and event.key() in (Qt.Key.Key_Backspace, Qt.Key.Key_Delete)
        ):
            # Beim Messen nimmt die Rücktaste das letzte Maß zurück. Vor der
            # Zug-Behandlung darunter, denn ein Maß entsteht ohne Zug — dort
            # käme die Taste nie an.
            self.undo_measurement()
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

    def reset_camera(self, *, follow_selection: bool = True) -> None:
        """Passt ausdrücklich ein und zeichnet das fertige Bild genau einmal."""
        self._fit_camera(follow_selection=follow_selection)
        self._draw()

    def _fit_camera(self, *, follow_selection: bool = True) -> None:
        """Passt auf die Körper ein — nicht auf den Bauraum.

        **Auf den gewählten Körper, wenn einer gewählt ist** (Entscheidung
        Robert, 03.09.2026). Wer ein Teil aus einer Baugruppe anklickt und Pos1
        drückt, will dieses Teil formatfüllend sehen, nicht wieder die ganze
        Baugruppe. Ohne Auswahl bleibt es beim Alten — die Szene, mit Luft.

        ``follow_selection=False`` nimmt das zurück, und ``_fit_once_for``
        braucht es: Dort wird gerahmt, *weil* die Szene der Ansicht entwachsen
        ist (ein neuer 400er Körper neben einem Zwei-Millimeter-Teil, die
        Kamera in seinem Inneren). Ein Rahmen um den alten, kleinen Ausgewählten
        beantwortete genau das nicht.

        Ein ``reset_camera()`` ohne Grenzen nimmt alle Elemente, und dazu gehört
        der Rahmen des Bauraums. Bei einem 80-mm-Teil in einem 256er Bauraum füllte
        damit die Kulisse das Bild und das Teil war ein Fleck darin: „Alles
        einpassen" tat sichtbar nichts, weil schon eingepasst war.

        Ohne Körper bleibt der Bauraum das Maß — dann ist er das Einzige, was
        es zu sehen gibt. Gerechnet wird er hier selbst, statt ihn den Renderer
        über alle Elemente suchen zu lassen: nur so bekommt auch die leere Szene ihre
        Luft, und nur so hängt das Ergebnis nicht daran, welche Kulisse gerade
        zusätzlich im Bild steht.

        **Mit Luft** (:data:`CAMERA_MARGIN`). Genau eingepasst berührte ein
        40 mm großer Quader links und rechts den Bildrand.
        """
        bounds = self._object_bounds() or self._volume_bounds()
        # Worauf eingepasst wurde, wird gemerkt: ``_fit_once_for`` vergleicht
        # damit, ob die Szene der Ansicht inzwischen entwachsen ist. **Vor** dem
        # Renderer-Zweig, aus demselben Grund wie bei der Umgebungsverdeckung:
        # offscreen gibt es keinen Renderer, und eine Regel, die nur im Zeichnen
        # gilt, prüft niemand.
        #
        # **Und es bleibt die Szene, auch wenn die Kamera gleich einen
        # einzelnen Körper rahmt.** Die Frage dahinter lautet „ist die Szene
        # gewachsen?" — eine Aussage über die Szene, nicht über die Kamera. Mit
        # den Grenzen des Ausgewählten darin hielte ``outgrown`` jede Auswahl
        # eines kleinen Teils für eine gewachsene Szene und rahmte beim nächsten
        # Aufbau von selbst wieder alles.
        self._fitted_bounds = bounds
        # **Nicht im Skizzenmodus.** Dort ist die Skizze der Gegenstand und der
        # Körper der Zusammenhang; eine Achsansicht auf den zuletzt gewählten
        # Körper zu rahmen, während das Blatt daneben liegt, beantwortet die
        # Frage nicht, die gestellt wurde. Pos1 selbst gehört dort ohnehin dem
        # Blatt (``SketchCanvas.fit_view``) — offen bleibt die ViewBar.
        if follow_selection and self._sketch_frame is None:
            chosen = self._selected_bounds()
            if chosen is not None:
                bounds = chosen
        if self.renderer is None:
            return
        if bounds is None:
            self.renderer.reset_camera()
        else:
            padded = with_margin(bounds)
            self.renderer.reset_camera(padded)
            if self._sketch_frame is None and any(self._zone_margins):
                ratio = self._device_ratio()
                left, right, bottom = self._zone_margins
                pose, scale = camera_in_free_area(
                    self.renderer.camera_pose(),
                    padded,
                    self.renderer.view_size(),
                    (left * ratio, right * ratio, bottom * ratio),
                    self.renderer.view_angle(),
                    self.renderer.parallel_scale() if self.renderer.parallel_projection() else None,
                )
                self.renderer.set_camera_pose(pose)
                if scale is not None:
                    self.renderer.set_parallel_scale(scale)
                self.renderer.reset_clipping_range()

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
            self._fit_camera(follow_selection=False)
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

    def _selected_bounds(self) -> tuple[float, float, float, float, float, float] | None:
        """Der Hüllquader der gewählten Körper **an ihrem Ort im Bild**.

        Nichts, solange keiner gewählt ist — und ebenso, wenn keiner der
        Gewählten gerade im Bild steht (ausgeblendet, unsichtbar, fremde
        Platte, §18.8/§25). Auf etwas einzupassen, das man nicht sieht, wäre
        die schlechteste der drei möglichen Antworten. Steht einer von
        mehreren nicht im Bild, zählt er nicht mit und die übrigen schon.

        Der Versatz gehört dazu: Auseinandergezogen oder auf einer zweiten
        Platte wird ein Körper anderswo gezeichnet, als er in der Szene liegt
        (:meth:`_view_offset`). Ohne ihn rahmte die Kamera die leere Stelle,
        an der er ohne Versatz stünde.
        """
        if self._result is None or self._selected is None:
            return None
        # **Über die ganze Auswahl, nicht über den führenden Körper allein.**
        # Wer zwei Teile wählt und einpassen läßt, bekam eines im Bild — der
        # Zwilling des Fehlers, den die Färbung hatte. Er saß eine Ebene
        # weiter und wäre so lange stehen geblieben, wie niemand fragt, was
        # sonst noch an ``_selected`` hängt.
        #
        # **Und hier ist es die rohe Auswahl, nicht ``highlighted_objects()``.**
        # Die gibt nichts zurück, sobald ein Merkmal gewählt ist — dort liegt
        # die Auswahlfarbe auf der Bohrung (§19.1). Für die Kamera gilt das
        # nicht: Wer ein Merkmal gewählt hat und einpaßt, meint den Körper,
        # in dem es sitzt. Die beiden Fragen sehen gleich aus und sind es
        # nicht, und genau deshalb steht die Färbungsausnahme nicht hier.
        boxes = []
        for identifier in (self._selected, *self._selected_more):
            entry = self._result.scene.objects.get(identifier)
            if entry is None or not self._in_view(identifier, entry):
                continue
            boxes.append((entry.mesh.bounds, self._view_offset(entry, self._result)))
        if not boxes:
            return None
        low = [min(float(b.minimum[a]) + float(o[a]) for b, o in boxes) for a in range(3)]
        high = [max(float(b.maximum[a]) + float(o[a]) for b, o in boxes) for a in range(3)]
        return (low[0], high[0], low[1], high[1], low[2], high[2])

    def _object_bounds(self) -> tuple[float, float, float, float, float, float] | None:
        """Der Hüllquader über alle Körper als Sechsertupel (``Bounds``), oder nichts."""
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
        if self.renderer is None or factor <= 0.0:
            return
        self.renderer.dolly(factor)
        self._draw()

    @property
    def sketch_active(self) -> bool:
        """Ob gerade eine Zeichenebene steht — dann bleibt die Blickrichtung darauf."""
        return self._sketch_frame is not None

    def set_camera_pose(
        self,
        position: tuple[float, float, float],
        focal_point: tuple[float, float, float],
        view_up: tuple[float, float, float],
        parallel_scale: float | None = None,
    ) -> None:
        """Eine Kamerastellung setzen und einmal zeichnen — der eine Weg, auf
        dem die 3D-Maus und die Flugtasten die Ansicht anfassen (§2.9).

        Wer nah heranfährt, schneidet sonst die Nahebene ins Teil: Der Vertrag
        verspricht kein Nachlegen der Schnittebenen von selbst
        (``reset_clipping_range`` ist ein eigener Aufruf, wie unter VTK), also
        wird es hier gesagt.
        """
        if self.renderer is None:
            return
        self.renderer.set_camera_pose(
            CameraPose(
                (float(position[0]), float(position[1]), float(position[2])),
                (float(focal_point[0]), float(focal_point[1]), float(focal_point[2])),
                (float(view_up[0]), float(view_up[1]), float(view_up[2])),
            )
        )
        if parallel_scale is not None:
            self.renderer.set_parallel_scale(float(parallel_scale))
        self.renderer.reset_clipping_range()
        self._draw()

    def camera_pose(self) -> tuple[Vec3, Vec3, Vec3, float | None]:
        """Standort, Blickpunkt, Oben — und der Parallelmaßstab, wenn die
        Projektion parallel ist, sonst ``None``."""
        assert self.renderer is not None
        pose = self.renderer.camera_pose()
        scale = self.renderer.parallel_scale() if self.renderer.parallel_projection() else None
        return (pose.position, pose.focal_point, pose.view_up, scale)

    def settle_camera(self) -> None:
        """Was nach einer Kamerafahrt fällig ist: Schatten neu, Raster neu.

        Der Mauszug erledigt das am Ende der Geste (``EndInteractionEvent``);
        die 3D-Maus ruft es, sobald die Kappe ruht — bei sechzig Takten je
        Sekunde wären neue Schatten je Takt der teuerste Teil des Bildes.
        """
        if self.renderer is None:
            return
        self._redraw_shadows()
        self.cameraMoved.emit()

    def view_from(self, direction: str) -> None:
        """Eine der sieben Kameravorgaben (§18.1).

        Eingepasst wird über :meth:`reset_camera` — auf die Körper, mit Luft,
        und mit gesetztem ``camera_set``. Ein ``reset_camera()`` ohne Grenzen
        stand hier und rahmte alle Elemente samt Bauraum-Kulisse: exakt der Fehler,
        den :meth:`reset_camera` in eigenen Worten beschreibt, nur über die
        Achsansichten (Strg+0 bis Strg+6, ViewBar) wieder offen.
        """
        if self.renderer is None or direction not in VIEW_DIRECTIONS:
            return
        position, up = VIEW_DIRECTIONS[direction]
        self.renderer.set_camera_pose(CameraPose(position, (0.0, 0.0, 0.0), up))
        # Eine absolute Kameravorgabe enthält den bisherigen Ausgleich nicht
        # mehr. Der gespeicherte Weltvektor muss deshalb gleichzeitig fallen;
        # sonst zieht die nächste Größen- oder Zoomänderung einen Versatz ab,
        # der in dieser neuen Kamera gar nicht steckt.
        self._sketch_occlusion_shift = (0.0, 0.0, 0.0)
        self._fit_camera()
        if self._sketch_frame is not None:
            self._apply_sketch_occlusion()
            # Die sichtbare ViewBar bleibt auch im Skizzenmodus bedienbar. Ihr
            # Ansichtsname muss daher denselben Weg ins Ebenenfeld nehmen wie
            # ein eingerasteter Kamerazug.
            self._settle_sketch_view(draw=False)
        else:
            self.cameraMoved.emit()
        self._redraw_shadows(draw=False)
        self._draw()

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
        if self.renderer is None:
            return
        distance = self._plane_distance()
        position, focus, up = camera_for_plane(frame, distance)
        self.renderer.set_camera_pose(CameraPose(position, focus, up))
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
        if self.renderer is None:
            return
        position, focus, up, scale = camera_for_span(
            frame,
            centre,
            span,
            self._plane_distance(),
            (self.height() or 1) / (self.width() or 1),
        )
        self.renderer.set_camera_pose(CameraPose(position, focus, up))
        if self.renderer.parallel_projection():
            self.renderer.set_parallel_scale(scale)
        self._sketch_occlusion_shift = (0.0, 0.0, 0.0)
        self._apply_sketch_occlusion()
        self.renderer.render()
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
        self._queue_feature_label_layout()
        if self._sketch_frame is not None and self._apply_sketch_occlusion():
            self._draw()

    def _apply_sketch_occlusion(self) -> bool:
        """Die Kamera um die verdeckte untere Bildhöhe verschieben; wahr, wenn
        sich dabei etwas geändert hat (§30.1).

        In orthografischer Projektion rücken Standort und Blickpunkt gemeinsam
        um genau die halbe verdeckte Bildhöhe (:func:`occluded_view_shift`).
        Das ändert weder Blickrichtung noch Maßstab; der wirklich angewandte
        Weltvektor steht in ``_sketch_occlusion_shift`` und lässt sich exakt
        wieder abziehen.
        """
        renderer = self.renderer
        if renderer is None or not renderer.parallel_projection():
            return False
        pose = renderer.camera_pose()
        position, focus, up = pose.position, pose.focal_point, pose.view_up
        previous = self._sketch_occlusion_shift
        amount = occluded_view_shift(
            float(renderer.parallel_scale()), self.height(), self._zone_margins[2]
        )
        wanted: Vec3 = (
            -float(up[0]) * amount,
            -float(up[1]) * amount,
            -float(up[2]) * amount,
        )
        if math.dist(previous, wanted) <= EPS_GEOM:
            return False
        renderer.set_camera_pose(
            CameraPose(
                (
                    float(position[0]) - previous[0] + wanted[0],
                    float(position[1]) - previous[1] + wanted[1],
                    float(position[2]) - previous[2] + wanted[2],
                ),
                (
                    float(focus[0]) - previous[0] + wanted[0],
                    float(focus[1]) - previous[1] + wanted[1],
                    float(focus[2]) - previous[2] + wanted[2],
                ),
                up,
            )
        )
        self._sketch_occlusion_shift = wanted
        return True

    def _remove_sketch_occlusion(self) -> bool:
        """Den Kameraausgleich der Skizze exakt zurücknehmen; wahr, wenn einer stand."""
        renderer = self.renderer
        if renderer is None:
            self._sketch_occlusion_shift = (0.0, 0.0, 0.0)
            return False
        shift = self._sketch_occlusion_shift
        if math.dist(shift, (0.0, 0.0, 0.0)) <= EPS_GEOM:
            return False
        pose = renderer.camera_pose()
        renderer.set_camera_pose(
            CameraPose(
                (
                    pose.position[0] - shift[0],
                    pose.position[1] - shift[1],
                    pose.position[2] - shift[2],
                ),
                (
                    pose.focal_point[0] - shift[0],
                    pose.focal_point[1] - shift[1],
                    pose.focal_point[2] - shift[2],
                ),
                pose.view_up,
            )
        )
        self._sketch_occlusion_shift = (0.0, 0.0, 0.0)
        return True

    def _fit_parallel_scale(self, distance: float) -> None:
        """Den Parallelmaßstab so setzen, dass die Ebene aus ``distance`` so
        groß erscheint wie perspektivisch — sonst spränge das Bild beim
        Umschalten der Projektion."""
        if self.renderer is None or not self.renderer.parallel_projection():
            return
        angle = float(self.renderer.view_angle() or 30.0)
        self.renderer.set_parallel_scale(distance * math.tan(math.radians(angle) / 2.0))

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
        """Die Zeichnung in die Szene legen: Raster, Achsen, Kurven, Punkte,
        Maßkarten und der Ziehgriff (§30.1).

        Alles ungreifbar (``pickable=False``): Kein Stück Zeichnung fängt einen
        Klick von Zeichenebene oder Umriss ab. Breite und Deckkraft sind die
        zweite Kodierung neben der Farbe (Regel 18) — Hilfsgeometrie dünn und
        durchscheinend, Gewähltes breit.
        """
        self.clear_sketch()
        # Kameraereignisse melden Zoom und Drehung über ``cameraMoved``. Der
        # anschließende Neuaufbau hält hier den freien Bildbereich stabil,
        # bevor Raster, Maße und Griff projiziert werden.
        self._apply_sketch_occlusion()
        self._sketch_step = step
        # **Vor der Wache gemerkt, nicht danach.** Der Ziehgriff fragt diese
        # Kurven nach dem Umriss im Bild, und offscreen gibt es keinen
        # Renderer: Eine Zuweisung hinter dem ``return`` prüfte in der Suite
        # niemand (§35).
        self._sketch_curves = tuple(curves)
        self._sketch_selected_curves = tuple(selected_curves)
        self._sketch_control_points = tuple(control_points)
        self._sketch_selected_points = tuple(selected_points)
        renderer = self.renderer
        if renderer is None:
            return
        import numpy as np

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
            item = renderer.add_lines(grid, name=name, colour=colour, width=float(width))
            item.set_opacity(opacity)
            self._sketch_actors.append(item)

        def add_label(point: Vec3, label: str, colour: str, name: str) -> None:
            self._sketch_actors.append(
                renderer.add_labels(
                    np.asarray([point], dtype=float),
                    [label],
                    name=name,
                    style=LabelStyle(
                        text_colour=colour, font_size=10, bold=True, always_visible=True
                    ),
                )
            )

        def add_cards(
            points: Sequence[Vec3], labels: Sequence[str], margin: int, name: str
        ) -> None:
            self._sketch_actors.append(
                renderer.add_labels(
                    np.asarray(points, dtype=float),
                    list(labels),
                    name=name,
                    style=LabelStyle(
                        text_colour=self._sketch_label_colour,
                        font_size=10,
                        bold=True,
                        always_visible=True,
                        background=self._sketch_label_background,
                        background_opacity=0.94,
                        margin=margin,
                    ),
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
            if axis_names[0]:
                add_label(
                    to_world(frame, (label_distance, 0.0)),
                    axis_names[0],
                    self._axis_x_colour,
                    "sketch_axis_x_label",
                )
            if axis_names[1]:
                add_label(
                    to_world(frame, (0.0, label_distance)),
                    axis_names[1],
                    self._axis_y_colour,
                    "sketch_axis_y_label",
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
                item = renderer.add_lines(
                    np.asarray([point for curve in chosen for point in curve.points], dtype=float),
                    name=f"sketch_{'help' if construction else 'lines'}",
                    colour=self._sketch_colour,
                    width=1.0 if construction else 3.0,
                    polylines=[len(curve.points) for curve in chosen],
                )
                # Die zweite Kodierung neben der Strichbreite (Regel 18):
                # Hilfsgeometrie ist durchscheinend, und wer den Unterschied in
                # der Breite nicht sieht, sieht ihn hier.
                item.set_opacity(0.45 if construction else 1.0)
                self._sketch_actors.append(item)

        chosen_curves = [
            curve
            for index, curve in enumerate(curves)
            if index in selected_curve_set and len(curve.points) > 1
        ]
        if chosen_curves:
            self._sketch_actors.append(
                renderer.add_lines(
                    np.asarray(
                        [point for curve in chosen_curves for point in curve.points], dtype=float
                    ),
                    name="sketch_selected_lines",
                    colour=SELECTED_COLOUR,
                    # Breite ist die zweite Kodierung neben der Farbe: Auch
                    # ohne Farbunterscheidung bleibt klar, was gewählt ist.
                    width=5.0,
                    polylines=[len(curve.points) for curve in chosen_curves],
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
                renderer.add_points(
                    np.asarray(single, dtype=float),
                    name="sketch_points",
                    colour=self._sketch_colour,
                    size=float(SKETCH_POINT_PIXELS),
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
                renderer.add_points(
                    np.asarray(plain_controls, dtype=float),
                    name="sketch_control_points",
                    colour=self._sketch_colour,
                    size=7.0,
                )
            )
        if chosen_controls:
            self._sketch_actors.append(
                renderer.add_points(
                    np.asarray(chosen_controls, dtype=float),
                    name="sketch_selected_points",
                    colour=SELECTED_COLOUR,
                    size=14.0,
                )
            )
        if measure_labels:
            add_cards(
                [point for point, _text in measure_labels],
                [text for _point, text in measure_labels],
                5,
                "sketch_measures",
            )
        full_handle = self._pull_handle_segments()
        handle = self._visible_pull_handle_segments(full_handle)
        if handle and self._pull_is_offered():
            self._sketch_actors.append(
                renderer.add_lines(
                    np.asarray([point for pair in handle for point in pair], dtype=float),
                    name="sketch_pull_handle",
                    colour=SELECTED_COLOUR,
                    width=5.0,
                )
            )
            inward, outward = full_handle[0]
            size = math.dist(inward, outward) / 2.0
            label_shift = tuple(frame.x_axis[axis] * size * 1.1 for axis in range(3))
            label_points: list[Vec3] = [
                (
                    outward[0] + label_shift[0],
                    outward[1] + label_shift[1],
                    outward[2] + label_shift[2],
                )
            ]
            labels = [str(tr("Hochziehen"))]
            if self._cut_pull_available():
                label_points.append(
                    (
                        inward[0] + label_shift[0],
                        inward[1] + label_shift[1],
                        inward[2] + label_shift[2],
                    )
                )
                labels.append(str(tr("Abtragen")))
            add_cards(label_points, labels, 4, "sketch_pull_labels")
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
        """Die Fangmarke setzen oder wegnehmen; wahr, wenn sich im Bild etwas ändert.

        Das Kreuz hat immer vier Punkte: Steht es schon, bekommt es nur neue
        Koordinaten — ein Render kostet gemessen 6,9 ms, und die Marke sitzt
        am **gefangenen** Ort, zwischen zwei Rasterpunkten ändert sie sich
        nicht. Die Größe ist in Bildpunkten (:data:`CURSOR_PIXELS`) und wird
        über den Maßstab der Ebene in Millimeter umgerechnet.
        """
        frame = self._sketch_frame
        if point is None or frame is None or self.renderer is None:
            changed = bool(self._cursor_actors)
            if self.renderer is not None:
                for actor in self._cursor_actors:
                    self.renderer.remove(actor)
            self._cursor_actors.clear()
            self._cursor_mesh = None
            self._cursor_count = 0
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

        points = np.asarray([end for pair in segments for end in pair], dtype=float)
        if self._cursor_mesh is not None and self._cursor_count == len(points):
            # Der übliche Fall: dasselbe Kreuz, anderswo.
            self._cursor_mesh.update_points(points)
            return True
        self._cursor_mesh = self.renderer.add_lines(
            points, name="sketch_cursor", colour=self._sketch_colour, width=2.0
        )
        self._cursor_count = len(points)
        self._cursor_actors.append(self._cursor_mesh)
        return True

    def _set_sketch_preview(self, curves: Sequence[SketchCurve]) -> bool:
        """Die mitfliegende Geometrie zwischen zwei Klicks; wahr bei Änderung.

        Bleibt die Form gleich, bekommt der Aktor nur neue Punkte — so braucht
        ein Zeigerschritt einen gemeinsamen Render mit der Fangmarke.
        """
        visible = tuple(curve for curve in curves if len(curve.points) > 1)
        signature = tuple(tuple(curve.points) for curve in visible)
        if signature == self._preview_at:
            return False
        self._preview_at = signature
        if self.renderer is None or not visible:
            changed = self._preview_actor is not None
            if self.renderer is not None and self._preview_actor is not None:
                self.renderer.remove(self._preview_actor)
            self._preview_actor = None
            self._preview_shape = ()
            return changed

        import numpy as np

        shape = tuple(len(curve.points) for curve in visible)
        points = np.asarray([point for curve in visible for point in curve.points], dtype=float)
        if self._preview_actor is not None and self._preview_shape == shape:
            self._preview_actor.update_points(points)
            return True
        if self._preview_actor is not None:
            self.renderer.remove(self._preview_actor)
        self._preview_shape = shape
        self._preview_actor = self.renderer.add_lines(
            points,
            name="sketch_preview",
            colour=SELECTED_COLOUR,
            width=2.0,
            polylines=list(shape),
        )
        self._preview_actor.set_opacity(0.82)
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
        if self.renderer is not None:
            for actor in self._sketch_actors:
                self.renderer.remove(actor)
        self._sketch_actors.clear()

    def snapshot(self) -> Any | None:
        """Ein Bild der Szene für den Fehlerbericht (§33.1) — oder nichts.

        Ein eigener Renderer ohne Fenster, in der Größe der Ansicht, mit
        derselben Blickrichtung und **Farbe und Grund aus dem Fenster**: Ein
        türkiser Körper auf weißem Grund wäre ein Bild, das der Support anders
        sieht als der Kunde, und damit eine Auskunft, die in die Irre führt.
        Ein Bild, das nicht entsteht, darf keinen Fehlerbericht verhindern —
        der Bogen ist dann eben ohne Bildmitte, statt gar nicht abzugehen.
        """
        if self.renderer is None or self._result is None or not self._result.scene.objects:
            return None
        import numpy as np
        from PySide6.QtGui import QImage

        from app.core.geom.mesh import as_mesh_data
        from app.ui.render.factory import make_renderer

        size = (max(16, self.width()), max(16, self.height()))
        shot = make_renderer(offscreen=True, size=size)
        try:
            for object_id, entry in self._result.scene.objects.items():
                raw = as_mesh_data(entry.mesh).raw
                shot.add_surface(
                    np.asarray(raw.vertices, dtype=float),
                    np.asarray(raw.faces, dtype=np.int64),
                    name=f"object:{object_id}",
                    style=SurfaceStyle(colour=self._object_colour),
                )
            shot.set_background(self.renderer.background())
            # Dieselbe Blickrichtung wie im Fenster — ein Bild aus einer
            # anderen Richtung beantwortete die Frage nicht, die es stellt.
            shot.set_camera_pose(self.renderer.camera_pose())
            raster = shot.screenshot()
        except Exception:  # pragma: no cover - Treiberlaunen, kein Programmfehler
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
        raw_bytes = np.ascontiguousarray(raster[:, :, :3]).tobytes()
        return QImage(raw_bytes, width, height, width * 3, QImage.Format.Format_RGB888).copy()

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

        Null kommt nie zurück: Ohne Renderer oder bei entarteter Projektion
        steht der Startwert der Zeichenfläche, und der ist eine brauchbare
        Vorgabe statt einer Division durch null.
        """
        return self._span_in_pixels(to_world(frame, (0.0, 0.0)), to_world(frame, (1.0, 0.0)))

    def _span_in_pixels(self, here: Sequence[float], there: Sequence[float]) -> float:
        """Wie weit zwei Weltpunkte im Bild auseinanderliegen, in Bildpunkten.

        Der gemeinsame Kern von :meth:`pixels_per_mm` und
        :meth:`pixels_per_mm_upright` — die beiden unterschieden sich bis zum
        04.09.2026 in genau einer Zeile (welchen zweiten Punkt sie nehmen) und
        führten dieselben neunzehn davor doppelt.

        **Erst messen, wenn es etwas zu messen gibt.** Solange das Layout nicht
        steht, meldet Qt die Startgröße eines Widgets (100 mal 30), und die
        Projektion daran ist keine Aussage über das Bild, das der Nutzer sieht.
        Siehe :data:`LEAST_VIEW_PIXELS`.

        Null kommt nie zurück: Ohne Renderer oder bei entarteter Projektion
        steht :data:`FALLBACK_SCALE`, und der ist eine brauchbare Vorgabe statt
        einer Division durch null.
        """
        if self.renderer is None:
            return FALLBACK_SCALE
        width, height = self.renderer.view_size()
        if min(width, height) < LEAST_VIEW_PIXELS:
            return FALLBACK_SCALE
        first = self._display_of(here)
        second = self._display_of(there)
        if first is None or second is None:
            return FALLBACK_SCALE
        span = math.dist(first, second)
        return span if span > EPS_GEOM else FALLBACK_SCALE

    def pixels_per_mm_upright(self, frame: PlaneFrame) -> float:
        """Wie viele Bildpunkte ein Millimeter **senkrecht** zur Ebene misst.

        Das Gegenstück zu :meth:`pixels_per_mm`, und der Unterschied ist der
        ganze Grund: Jene misst zwei Punkte *auf* der Ebene, diese zwei entlang
        ihrer Normalen. In der Draufsicht sind das zwei verschiedene Welten —
        die Ebene liegt in voller Größe da, ihre Normale zeigt zum Betrachter
        und ist ein Punkt.

        **Wofür das gebraucht wird:** Der Ziehgriff zeigt entlang der Normalen.
        Seine Länge wurde bisher über die Skalierung *in* der Ebene gerechnet,
        und damit stimmte sie nur in der Seitenansicht. Gemessen am
        30.08.2026, bei 38 Bildpunkten Sollgröße:

        | Kippung | Griff im Bild |
        |---|---|
        | 10° | 6,6 px |
        | 20° | 13,0 px |
        | 45° | 26,9 px |
        | 90° | 38,0 px |

        Bis etwa 25° war der Griff damit **kürzer als seine eigene
        Trefferzone** (:data:`PULL_HIT_PIXELS`, 14 Bildpunkte): ein Stummel,
        um den unsichtbar ein Ring lag, der Zeichenklicks schluckte.

        Gemessen und nicht aus dem Kippwinkel gerechnet — dieselbe Begründung
        wie bei :meth:`pixels_per_mm`: Durch die echte Projektion geschickt
        stimmt die Zahl bei Parallel- wie bei Zentralprojektion.
        """
        here = to_world(frame, (0.0, 0.0))
        there = tuple(here[axis] + frame.normal[axis] for axis in range(3))
        return self._span_in_pixels(here, there)

    def _plane_distance(self) -> float:
        """Wie weit die Kamera von der Zeichenebene wegrückt.

        Der bisherige Abstand zum Blickpunkt, damit der Ausschnitt beim
        Schwenken erhalten bleibt.

        **Mit einer Untergrenze, und die ist kein Zierat.** In einem leeren
        Fenster hat ``reset_camera`` nie stattgefunden, und die Startkamera
        steht dicht vor dem Ursprung (unter PyVista, bis 05.09.2026, gemessen:
        1,62 Einheiten).
        Diesen Abstand treu zu
        übernehmen hieße, aus 1,6 Millimetern auf die Zeichenebene zu sehen:
        gemessen 918 Bildpunkte je Millimeter, ein Raster von 0,1 mm und ein
        Bild, in dem nichts von dem steht, was man zeichnet.

        Getroffen hätte es ausgerechnet **Weg 2** — neu konstruieren, ohne
        Modell —, denn nur dort ist die Szene leer, wenn der Skizzenmodus
        beginnt. Mit geladenem Teil ist die Kamera längst eingepasst und die
        Grenze wirkungslos.
        """
        if self.renderer is None:
            return LEAST_PLANE_DISTANCE
        pose = self.renderer.camera_pose()
        span = math.dist(pose.position, pose.focal_point)
        return max(span, LEAST_PLANE_DISTANCE)

    # --- navigation (§2.9) ------------------------------------------------------

    def keyPressEvent(self, event: Any) -> None:  # noqa: N802 - Qt gibt den Namen
        """W/A/S/D fliegen, Q/E kippen — nur im Schema, das sie verspricht (§2.9).

        **Nur in ``solidon``.** Die vier anderen Schemata bilden
        Fremdprogramme nach; eine Bewegung, die es im Vorbild nicht gibt, wäre
        dort eine Überraschung — und in Blender sind die Tasten belegt.

        **Der Anschlag schaltet ein, er bewegt nicht.** Gefahren wird im Takt
        (:data:`FLIGHT_TICK_MS`), solange die Taste liegt; die Wiederholung des
        Systems wird verworfen (``isAutoRepeat``). So hängt die Geschwindigkeit
        an einer Zahl in dieser Datei und nicht an der Tastatureinstellung des
        Kunden — und der Flug beginnt sofort statt nach der halben Sekunde, die
        das System vor der ersten Wiederholung wartet.
        """
        if self._scheme != "solidon" or self.renderer is None:
            super().keyPressEvent(event)
            return
        axes = FLIGHT_KEYS.get(event.text().lower())
        if axes is None or event.isAutoRepeat():
            # Die Wiederholung trägt nichts bei: Die Taste liegt schon im Satz.
            if axes is None:
                super().keyPressEvent(event)
            else:
                event.accept()
            return
        self._flying.add(event.text().lower())
        self._start_flying()
        event.accept()

    def keyReleaseEvent(self, event: Any) -> None:  # noqa: N802 - Qt gibt den Namen
        """Die Taste geht hoch, die Bewegung endet.

        **Die Wiederholung schickt auch Loslass-Ereignisse.** Wer eine Taste
        hält, bekommt von Qt abwechselnd Release und Press; ohne
        ``isAutoRepeat`` endete der Flug damit bei jedem Takt der Tastatur und
        begänne neu — sichtbar als Stottern.
        """
        key = event.text().lower()
        if key not in FLIGHT_KEYS or event.isAutoRepeat():
            super().keyReleaseEvent(event)
            return
        self._flying.discard(key)
        if not self._flying:
            self._stop_flying()
        event.accept()

    def focusOutEvent(self, event: Any) -> None:  # noqa: N802 - Qt gibt den Namen
        """Wer den Fokus verliert, bekommt kein Loslassen mehr zu sehen.

        Ohne das flöge die Ansicht weiter, während der Kunde längst in einem
        Eingabefeld tippt — die Taste ist dort losgelassen worden, und dieses
        Ereignis kommt nie hier an.
        """
        self._flying.clear()
        self._stop_flying()
        super().focusOutEvent(event)

    def _start_flying(self) -> None:
        """Den Takt anwerfen, falls er nicht schon läuft."""
        if self._flight_timer is None:
            timer = QTimer(self)
            timer.setInterval(FLIGHT_TICK_MS)
            timer.timeout.connect(self._fly_one_tick)
            self._flight_timer = timer
        self._flight_clock.restart()
        if not self._flight_timer.isActive():
            self._flight_timer.start()

    def _stop_flying(self) -> None:
        if self._flight_timer is not None:
            self._flight_timer.stop()

    def _fly_one_tick(self) -> None:
        """Ein Takt Flug — mit der Zeit, die wirklich vergangen ist.

        Nicht mit :data:`FLIGHT_TICK_MS`: Unter Last kommt der Takt später,
        und eine feste Zeitspanne machte die Bewegung dann langsamer statt
        gleich schnell. Dasselbe Vorgehen wie bei der 3D-Maus.
        """
        if not self._flying or self.renderer is None:
            self._stop_flying()
            return
        seconds = self._flight_clock.restart() / 1000.0
        if seconds <= 0.0:
            return
        axes: dict[str, float] = {}
        for key in self._flying:
            for axis, amount in FLIGHT_KEYS[key].items():
                # Zwei Tasten auf derselben Achse heben sich auf — wer A und D
                # zugleich hält, steht still, wie in jedem Spiel.
                axes[axis] = axes.get(axis, 0.0) + amount
        self.fly_camera(seconds, **axes)

    def fly_camera(self, seconds: float, **axes: float) -> None:
        """Eine Zeitspanne Flug auf die Kamera legen (§2.9).

        Getrennt von :meth:`keyPressEvent`, damit die Bewegung ohne ein
        Tastenereignis prüfbar ist — dieselbe Trennung wie bei
        ``belongs_to_the_focus``: Was Qt aus einem Anschlag macht, hängt an der
        Fensterhülle, die Bewegung darin nicht.

        Die Geschwindigkeit steht als :data:`FLIGHT_RATE` in Entfernungen je
        Sekunde und wird hier in die Einheit von ``camera_step`` umgerechnet:
        Dessen ``speed`` ist ein Faktor auf ``PAN_RATE``, nicht selbst eine
        Strecke. Eine Zahl, die man lesen kann, ohne die Kappe zu kennen.
        """
        from app.ui.spacemouse import PAN_RATE, Motion, camera_step
        from app.ui.spacemouse import CameraPose as MousePose

        if self.renderer is None:
            return
        pose = MousePose(*self.camera_pose())
        # ``Motion`` führt neben den sechs Achsen die Tastenmaske als
        # ``int``; die Aufweitung eines ``dict[str, float]`` passt für mypy
        # deshalb nicht auf die Signatur. Gebaut wird darum aus den Achsen.
        moved = camera_step(
            pose,
            Motion(
                x=axes.get("x", 0.0),
                y=axes.get("y", 0.0),
                z=axes.get("z", 0.0),
                rx=axes.get("rx", 0.0),
                ry=axes.get("ry", 0.0),
                rz=axes.get("rz", 0.0),
            ),
            seconds,
            speed=FLIGHT_RATE / PAN_RATE,
            fly=True,
        )
        if moved is pose:
            return
        self.set_camera_pose(moved.position, moved.focal_point, moved.view_up)
        self.cameraMoved.emit()

    def tilt_camera(self, step: int) -> None:
        """Die Ansicht um *step* Bildpunkte nach oben oder unten kippen (§2.9).

        **Warum die Anwendung das selbst rechnet.** Das Kippen ist eine eigene
        Rechnung und keine Bewegung des Renderers (unter VTK, bis 05.09.2026,
        kannte der Trackball „nur nach oben und unten" nicht, und ``Rotate``
        dafür zu überschreiben hieße, am Zustand des Interactors zu drehen).
        Gerechnet wird mit :func:`app.ui.spacemouse.camera_step` — derselben
        reinen Funktion, die die Kappe und die Tastatur bedienen, und die ohne
        Fenster prüfbar ist (§35).

        Der Schritt kommt in Bildpunkten und wird auf den Bereich der
        Kappenachsen umgerechnet: :data:`TILT_PER_PIXEL` ist so gewählt, dass
        eine Bewegung über die halbe Fensterhöhe die Ansicht etwa eine
        Vierteldrehung kippt.
        """
        from app.ui.spacemouse import CameraPose as MousePose
        from app.ui.spacemouse import Motion, camera_step

        if self.renderer is None:
            return
        pose = MousePose(*self.camera_pose())
        turned = camera_step(pose, Motion(rx=step * TILT_PER_PIXEL), TILT_STEP_SECONDS)
        if turned is pose:
            return
        self.set_camera_pose(turned.position, turned.focal_point, turned.view_up)
        self.cameraMoved.emit()

    def set_navigation(self, scheme: NavigationScheme) -> None:
        """Das Navigationsschema (§2.9) setzen — am Navigator, der die Kamera
        führt. Die Griffe haben Vorfahrt, siehe :meth:`_on_pointer`."""
        self._scheme = scheme
        if self.renderer is None:
            return
        if self._navigator is None:
            self._navigator = Navigator(self.renderer, scheme, _weak_callbacks(self))
        else:
            self._navigator.set_scheme(scheme)

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
        """Der Weltpunkt unter einem Bildpunkt — auf einem Körper, sonst nichts.

        **Gesucht wird nur unter den Körpern.** Ein Zell-Picker trifft alles,
        was im Bild steht, und im Bild steht mehr als die Szene: die Pfeile
        des Bewegungsgriffs, sein Skalierwürfel, Marken, Schatten, das Bett.
        Mit eingeschaltetem Griff traf ein Klick auf eine Bohrung dessen
        Pfeil, und die Bohrung liess sich nicht mehr auswählen (Robert,
        03.09.2026). Die Liste bleibt leer, wenn es keine Körper gibt
        (Skizzenmodus, leeres Projekt); dann pickt der Renderer über die ganze
        Szene. Die Toleranz ist ein Anteil der Bilddiagonale und geht
        ausdrücklich mit (:data:`PICK_TOLERANCE`): Die Vorgabe des Zell-Pickers
        unter VTK war so klein, dass ein Klick an einer Kante wieder
        danebenging.
        """
        self._selection_hit = None
        if self.renderer is None:
            return None
        hit = self.renderer.pick_surface(
            x, y, among=list(self._actors.values()) or None, tolerance=PICK_TOLERANCE
        )
        if hit is not None and self._result is not None:
            object_id = next(
                (key for key, actor in self._actors.items() if actor is hit.item), None
            )
            entry = self._result.scene.objects.get(object_id) if object_id else None
            if entry is not None and object_id is not None:
                shift = self._shown_offset(entry, self._result)
                scene_point = (
                    float(hit.point[0] - shift[0]),
                    float(hit.point[1] - shift[1]),
                    float(hit.point[2] - shift[2]),
                )
                self._selection_hit = _SelectionHit(object_id, scene_point, hit.point, hit.cell)
        return hit.point if hit is not None else None

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
        point = self._world_at(x, y) if self.renderer is not None else None
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
        zwei Dinge sind: Offscreen gibt es keinen Renderer, und ein Picker über
        einem nie gezeichneten Bild trifft nichts. Ein Test über
        Bildschirmkoordinaten prüfte damit die Testumgebung; über den Weltpunkt
        prüft er die Bedienung.
        """
        if not self.can_drag_body_at(point):
            return False
        assert point is not None
        if not self._selected_more and (
            self._selected_feature is not None or self._selected_features
        ):
            # Bei einem Körper muss die gemeinsame Auswahl vor der Vorschau
            # auf die Körperstufe wechseln, sonst bewegt der Abschluss nur
            # das Merkmal. Eine Mehrfachauswahl bezeichnet bereits die ganze
            # Körpermenge und muss erhalten bleiben.
            self.objectPicked.emit(self._selected or "")
        self._body_drag_from = point
        self._body_drag_offset = (0.0, 0.0)
        # "move", nicht "moving": Eine Rolle, die es nicht gibt, fällt still
        # auf den Systempfeil zurück — die häufigste Zuggeste zeigte den
        # falschen Zeiger, und kein Test sah es, bis der Wächter in
        # tests/test_cursors.py die Literale gegen cursors.known() hält.
        self.set_drag_cursor("move")
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
        # **Alle gewählten Körper, nicht nur der führende.** Beim Loslassen
        # trifft der Schritt die ganze Auswahl (``inputs_for_transform``), also
        # muss die Vorschau sie auch zeigen — sonst folgt einer dem Zeiger und
        # beim Loslassen springen zwei. Jeder bekommt seinen eigenen Eintrag in
        # ``_actor_home``, damit ``_undo_body_preview`` sie alle zurückholt;
        # dessen Schleife über die Einträge trägt das schon.
        moved = False
        for identifier in (self._selected, *self._selected_more):
            actor = self._actors.get(identifier)
            if actor is None:
                continue
            base = self._actor_home.setdefault(identifier, actor.position())
            actor.set_position(
                (base[0] + self._body_drag_offset[0], base[1] + self._body_drag_offset[1], base[2])
            )
            self._sync_edge_preview(identifier)
            moved = True
        # Ein Bildaufbau für alle, nicht einer je Körper.
        if moved and self.renderer is not None:
            self._layout_feature_labels()
            self.renderer.render()

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
        # Der Knopf daneben sagt „Fang — auf welchen Schritt ein Zug einrastet",
        # und der Griff hält sich daran; der freie Zug tat es bis zum
        # 02.09.2026 nicht und schrieb 3,7182 mm in den Verlauf.
        offset = (
            snap_to_step(offset[0], self._grid_step),
            snap_to_step(offset[1], self._grid_step),
        )
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
        cut_available: Callable[[], bool] | None = None,
        cut_top: Callable[[], float] | None = None,
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
        **aus ihren Schemata**. ``cut_available`` beantwortet zusätzlich, ob
        ein ausgewählter Körper die Tasche gerade wirklich aufnehmen kann.
        Beides kommt von außen, damit die Ansicht weder Geometriezustand noch
        Zahlen nachbaut.

        ``None`` löst alles wieder — das Fenster tut es beim Verlassen des
        Modus, sonst hielte die Ansicht einen Rückruf auf ein gestorbenes Panel.
        """
        self._sketch_pull_offer = offer
        self._pull_limits = limits
        self._cut_limits = cut_limits
        self._sketch_cut_available = cut_available
        self._sketch_cut_top = cut_top
        if offer is None:
            self._end_pull()

    def pulling(self) -> bool:
        """Ob gerade eine Höhe gezogen wird.

        Von außen gefragt und nicht abgeleitet: Solange der Zug läuft, meint
        eine Mausbewegung die Höhe und nicht den Zeiger auf der Ebene — die
        Vorschau der Zeichnung muss dann stillhalten."""
        return self._pull_from is not None

    def _display_of(self, world: Sequence[float]) -> tuple[float, float] | None:
        """Ein Weltpunkt im Bild — in Gerätepixeln, gezählt wie Qt (oben links),
        oder nichts ohne Bild."""
        if self.renderer is None:
            return None
        x, y, _depth = self.renderer.world_to_display(
            (float(world[0]), float(world[1]), float(world[2]))
        )
        return (x, y)

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
        # **Gemessen senkrecht zur Ebene, denn dorthin zeigt der Griff.**
        # Über die Skalierung *in* der Ebene gerechnet stimmte die Länge nur
        # in der Seitenansicht; bei zehn Grad Kippung blieben von achtunddreißig
        # Bildpunkten sechseinhalb übrig — weniger als die Trefferzone um ihn
        # herum. Siehe :meth:`pixels_per_mm_upright`.
        upright = self.pixels_per_mm_upright(self._sketch_frame)
        flat = self.pixels_per_mm(self._sketch_frame)
        # **Und eine Grenze nach oben**, sonst wächst der Griff bei flachem
        # Blick ins Unendliche: Bei einem Zehntelgrad wäre er sechshundertmal
        # so lang und läge quer durch den Bauraum. Unter zehn Grad rastet die
        # Kamera ohnehin ein (:meth:`_settle_sketch_view`), und dort ist der
        # Faktor 1/sin(10°) = 5,76 — aufgerundet sechs, damit die Grenze erst
        # jenseits des Einrastens greift und nicht davor.
        least = max(flat, EPS_GEOM) / PULL_HANDLE_STRETCH
        size = PULL_HANDLE_PIXELS / max(upright, least, EPS_GEOM)
        # **Quer bleibt quer.** Flügel und Kreuz liegen in der Ebene und
        # werden nicht verkürzt; mitgestreckt verdeckten sie das Profil.
        across = PULL_HANDLE_PIXELS / max(flat, EPS_GEOM)
        return pull_handle(self._sketch_frame, self._sketch_curves, size, across)

    def _pull_is_offered(self) -> bool:
        """Ob der räumliche Griff in diesem Zustand eine gültige Geste ist."""
        return self._sketch_pull_offer is not None and self._sketch_pull_offer() == "ready"

    def _cut_pull_available(self) -> bool:
        """Ob die sichtbare Richtung nach innen gerade angewandt werden kann."""
        if self._cut_limits is None:
            return False
        return self._sketch_cut_available is None or self._sketch_cut_available()

    def _visible_pull_handle_segments(
        self,
        handle: Sequence[tuple[Vec3, Vec3]] | None = None,
    ) -> list[tuple[Vec3, Vec3]]:
        """Nur die Richtungen des Griffs, die beim Loslassen auch gelten.

        Ohne bearbeitbaren Zielkörper bleibt der Pfeil nach außen stehen. Der
        innere Schaft und das Kreuz verschwinden gemeinsam mit „Abtragen" —
        eine fehlende Handlung wird nicht als bloß gesperrte Dekoration im
        Modell gezeigt.
        """
        complete = list(handle if handle is not None else self._pull_handle_segments())
        if not complete or self._cut_pull_available():
            return complete
        inward, outward = complete[0]
        base: Vec3 = (
            (float(inward[0]) + float(outward[0])) / 2.0,
            (float(inward[1]) + float(outward[1])) / 2.0,
            (float(inward[2]) + float(outward[2])) / 2.0,
        )
        return [(base, outward), *complete[1:3]]

    def pull_handle_reach(self, x: int, y: int) -> float:
        """Wie weit die Bildstelle von Pfeil oder Kreuz des Ziehgriffs liegt."""
        best = math.inf
        for first, second in self._visible_pull_handle_segments():
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
        if reach < 0.0 and not self._cut_pull_available():
            # Ohne ausgewählten, bearbeitbaren Körper gibt es im Bild weder
            # Kreuz noch Tasche. Auch während eines versehentlichen Zugs nach
            # innen darf deshalb kein Drahtkörper samt „Tiefe" aufscheinen,
            # der beim Loslassen kommentarlos wieder verschwindet.
            if abs(self._pull_height) > EPS_GEOM:
                self._pull_height = 0.0
                self._show_pull_cage()
                self.drag_bar.dismiss()
            return
        height = pulled_height(reach, self._sketch_step, self._limits_for(reach))
        if abs(height - self._pull_height) <= EPS_GEOM:
            return
        self._pull_height = height
        # Das Maß steht an der Drahtform selbst, wie beim Zeichnen einer Linie
        # (Robert, 02.09.2026: „ein Maß daneben, wie wenn wir eine Linie
        # zeichnen") — kein Wertfeld am Zeiger, keines in der Leiste. Die
        # genaue Zahl bekommt der Dialog beim Loslassen.
        self._show_pull_cage()

    def _pull_frame(self) -> PlaneFrame:
        """Die Ebene, von der die Drahtform ausgeht.

        Nach außen ist das die Zeichenebene. Nach innen ist es die Oberkante
        des Körpers, der abgetragen wird — ``sketch_pocket`` schneidet dort,
        wenn die Zeichnung tiefer liegt (der Fusion-Weg: Umriss auf dem Bett,
        Teil darüber). Bis zum 02.09.2026 wuchs die Drahtform von der
        Zeichenebene in die Luft unter dem Teil, geschnitten wurde oben:
        Tiefe richtig, Ort falsch.
        """
        frame = self._sketch_frame
        assert frame is not None
        if self._pull_height >= 0.0 or self._sketch_cut_top is None:
            return frame
        shift = float(self._sketch_cut_top())
        if shift <= EPS_GEOM:
            return frame
        normal = frame.normal
        origin = (
            frame.origin[0] + normal[0] * shift,
            frame.origin[1] + normal[1] * shift,
            frame.origin[2] + normal[2] * shift,
        )
        return replace(frame, origin=origin)

    def _show_pull_cage(self) -> None:
        """Legt die Drahtform des Zugs in die Szene — oder nimmt sie weg."""
        actors = tuple(self._pull_actors)
        self._pull_actors.clear()
        if self.renderer is None:
            return
        for actor in actors:
            self.renderer.remove(actor)
        segments = (
            pull_cage(self._pull_frame(), self._sketch_curves, self._pull_height)
            if self._sketch_frame is not None
            else []
        )
        if not segments:
            self._draw()
            return

        import numpy as np

        points = np.asarray([end for pair in segments for end in pair], dtype=float)
        self._pull_actors.append(
            self.renderer.add_lines(
                points, name="sketch_pull", colour=self._sketch_colour, width=2.0
            )
        )
        # Die Maßkarte am oberen Rand der Drahtform — dieselbe Karte, die die
        # Skizze an ihre Linien hängt, damit der Zug aussieht wie das Zeichnen.
        if self._sketch_frame is not None:
            along = points @ np.asarray(self._sketch_frame.normal, dtype=float)
            extreme = along.max() if self._pull_height >= 0.0 else along.min()
            rim = points[np.abs(along - extreme) <= EPS_GEOM]
            self._pull_actors.append(
                self.renderer.add_labels(
                    np.asarray([rim.mean(axis=0)]),
                    [length(abs(self._pull_height))],
                    name="sketch_pull_measure",
                    style=LabelStyle(
                        text_colour=self._sketch_label_colour,
                        font_size=10,
                        bold=True,
                        always_visible=True,
                        background=self._sketch_label_background,
                        background_opacity=0.94,
                        margin=5,
                    ),
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
        if height < 0.0 and not self._cut_pull_available():
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
                actor.set_position(home)
                self._sync_edge_preview(object_id)
        self._actor_home.clear()
        self._queue_feature_label_layout()

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
            actor.set_visible(frame is None and self._bed_visible)
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
            actor.set_opacity(opacity)
        for actor in self._shadow_actors:
            actor.set_visible(frame is None)
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

    def set_sketch_stroke(self, finish: Callable[[], bool] | None) -> None:
        """Verdrahtet den Abschluss eines begonnenen Zugs (Z4).

        Wie :meth:`set_sketch_entry`: Das Fenster setzt den Rückruf beim
        Betreten des Modus und löst ihn beim Verlassen, damit hier keine
        Referenz auf ein gestorbenes Panel liegen bleibt.

        Der Rückruf sagt selbst, ob er zuständig war — nur dann wird das
        Ereignis geschluckt. Eine Eingabetaste, die keinen Zug abschließt,
        gehört weiterhin dem, der sie sonst bekäme.
        """
        self._sketch_finish_stroke = finish

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
        """Ein Zeichenpunkt als Logikpunkt des Fensters — für ein Menü oder ein
        Feld an genau dieser Stelle."""
        if self.renderer is None or self._sketch_frame is None:
            return None
        x, y, _depth = self.renderer.world_to_display(to_world(self._sketch_frame, point))
        ratio = self._device_ratio()
        return QPoint(int(x / ratio), int(y / ratio))

    def _sketch_hit(self, x: int, y: int) -> tuple[float, float] | None:
        """Wo der Sichtstrahl durch diese Bildstelle die Zeichenebene trifft.

        **Gerechnet und nicht gepickt.** Ein Oberflächen-Pick (``pick_surface``)
        trifft nur Geometrie; die Zeichenebene ist keine, und über einer
        Durchgangsbohrung gäbe es nicht einmal ein Dreieck dahinter (gemessen
        von ``formwerk-d1`` am Referenzkorpus).
        :func:`app.core.sketch.planes.ray_hit` trifft sie immer — auch dort, wo
        der Körper ein Loch hat.

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

    @property
    def navigation(self) -> NavigationScheme:
        return self._scheme


def _ring_points(centre: Any, normal: Any, radius: float, count: int = 48) -> Any:
    """Ein Kreis um ``centre``, flach auf der Fläche mit dieser Normale.

    Flach und nicht in der Bildebene: Ein Ring, der immer zum Betrachter zeigt,
    sagt nichts darüber, wie schräg die Stelle unter ihm steht — und schräg ist
    beim Formen der Normalfall.

    Als eigene Funktion, damit die Rechnung ohne Renderer prüfbar bleibt.
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


def _triangle_faces(count: int) -> Any:
    """Die Dreiecksliste für ``count`` Dreiecke mit je eigenen Eckpunkten —
    das Gegenstück zu :meth:`Viewport._lifted_corners`, das jede Ecke je
    Dreieck einzeln hinlegt."""
    return shapes.triangle_soup(count)


def _weak_callbacks(view: Viewport) -> NavigatorCallbacks:
    """Die Rückrufe der Ansicht an den Navigator — alle über ``weakref``.

    Der Navigator hängt am Renderer, der Renderer an der Ansicht; ein starker
    Rückruf schlösse den Ring, und der ist der Absturz ohne Zeile am Ende
    eines Laufs. Jeder Rückruf fragt erst, ob die Ansicht noch lebt.
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
        """Der Körperzug in vier Phasen — ``ready``, ``start``, ``move``, ``end``.

        **Im Skizzenmodus zieht dieselbe Geste eine Höhe** (§30.1). Derselbe
        Rückruf und keine zweite Zustandsmaschine daneben: Drücken, Schwelle,
        Ziehen, Loslassen sind hier wie dort dieselben vier Schritte, und zwei
        Schwellen für „ist das ein Klick oder ein Zug" wären das Loch, das der
        Körperzug schon einmal hatte.
        """
        found = weak()
        if found is None:
            return False
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
            world_point = found._world_at(x, y) if found.renderer is not None else None
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
        # Der Radzoom endet ohne Zugende — dieser Rückruf ist sein Meldeweg.
        found = weak()
        if found is not None:
            found.cameraMoved.emit()

    def on_tilt(step: int) -> None:
        found = weak()
        if found is not None:
            found.tilt_camera(step)

    def on_end() -> None:
        # Dreh-, Kipp- und Schiebezüge enden hier: nahe Hauptansicht
        # einrasten, Schatten nachziehen, die Bewegung melden.
        found = weak()
        if found is not None:
            found._settle_sketch_view()
            found._redraw_shadows()
            found.cameraMoved.emit()

    return NavigatorCallbacks(
        on_context,
        on_pick,
        on_cursor,
        on_paint,
        is_sculpting,
        on_body_drag,
        on_rotate_start,
        on_camera,
        on_tilt,
        on_end,
    )
