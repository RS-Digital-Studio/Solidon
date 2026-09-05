"""Die Kameraführung der 3D-Ansicht — aus Zeigergesten, ohne VTK (§2.9, §18).

Was hier steht, war bis zum 05.09.2026 ein VTK-Interaktionsstil im Viewport
(``_InteractorStyle``): Beobachter an ``vtkInteractorStyleTrackballCamera``,
die Drehteller, Kippen, Schieben und Radzoom rechneten und VTKs eigene
Bewegung verdrängten. Mit dem Renderer-Vertrag braucht die Kamera keinen
Stil mehr — sie braucht Zeigergesten (:class:`PointerEvent`) und einen
Renderer, der Kamerapose, Bildpunkte und Weltpunkte kennt. Genau das ist
der :class:`Navigator`: dieselbe Zustandsmaschine, dieselben Rückrufe an die
Ansicht, dieselben Zahlen — nur auf dem Vertrag statt auf VTK, und damit
für beide Renderer gleich und ohne Fenster prüfbar (§35).

Die Tabelle :data:`_NAVIGATION` sagt, welche Taste in welchem Schema was
tut; :func:`turntable_camera` rechnet den Drehteller; :func:`is_click`
trennt Klick von Zug. Alle drei kamen aus ``viewport.py`` und werden dort
weiter unter demselben Namen ausgeführt.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Sequence
from typing import Final, Literal, NamedTuple

import numpy as np

from app.core.units import EPS_GEOM
from app.ui.render.api import CameraPose, MouseButton, PointerEvent, Renderer, Vec3

NavigationScheme = Literal["solidon", "slicer", "cad", "blender", "orbit"]
"""``slicer`` folgt §2.9 und damit Cura: links wählt, rechts dreht.
``orbit`` ist die Aufteilung von Bambu Studio, OrcaSlicer und PrusaSlicer —
links dreht, rechts schiebt. ``cad`` und ``blender`` legen das Drehen auf die
mittlere Taste, wie die Programme, nach denen sie heißen."""

CameraAction = Literal["select", "rotate", "pan", "zoom", "tilt"]

#: Wie weit die Ansicht sich der Senkrechten nähern darf (Grad).
#:
#: Genau über dem Teil gibt es kein Oben mehr: Blickrichtung und Welt-Hochachse
#: fallen zusammen, und jede Aufrichtung wäre eine Division durch nichts. Ein
#: Grad davor ist der Unterschied unsichtbar und die Rechnung wohldefiniert.
POLE_LIMIT_DEGREES: Final = 89.0
#: Die Empfindlichkeit des Drehens, übernommen von dem Stil, den
#: :func:`turntable_camera` ersetzt: ``vtkInteractorStyleTrackballCamera``
#: rechnet 20 Grad je Fensterhälfte mal seinem ``MotionFactor`` von 10.
#: Übernommen und nicht neu gewählt — wer die Neigung abstellt, soll nicht
#: nebenbei die gewohnte Geschwindigkeit ändern.
TURN_PER_PIXEL: Final = 20.0
TURN_MOTION_FACTOR: Final = 10.0

#: Wie weit ein Rasterschritt am Mausrad zoomt. VTKs Vorgabe für den
#: Trackball-Stil, damit sich das Rad wie überall sonst anfühlt.
WHEEL_STEP: Final = 0.1

#: Das Ziehen mit der Zoomtaste, wie VTKs Trackball es rechnet: der
#: senkrechte Weg im Verhältnis zur halben Bildhöhe, mal ``MotionFactor`` 10,
#: als Exponent zur Basis 1,1. Übernommen, damit das CAD-Schema sich anfühlt
#: wie bisher.
DOLLY_MOTION_FACTOR: Final = 10.0
DOLLY_BASE: Final = 1.1

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
CLICK_SLACK: Final = 10

#: Was eine Maustaste in einem Schema an der Kamera tut.
#:
#: **Eine reine Funktion und keine Kette im Interaktionsstil**, aus zwei
#: Gründen. Der eine ist die Prüfbarkeit: Der Stil war eine VTK-Klasse, seine
#: Tastenkette lief offscreen nie, und deshalb konnte „mittlere Taste dreht"
#: zwei Schemata lang im Einstellungsdialog stehen, **ohne dass die mittlere
#: Taste überhaupt einen Beobachter hatte**. Der andere ist die eine Wahrheit:
#: Der Text im Dialog und das Verhalten stammen aus derselben Tabelle.
_NAVIGATION: Final[dict[NavigationScheme, dict[tuple[MouseButton, bool], CameraAction]]] = {
    # **Die Vorgabe** (Entscheidung Robert, 03.09.2026): links verschiebt,
    # rechts dreht um den Mittelpunkt, das gedrückte Rad kippt nach oben und
    # unten. Dazu WASD zum Fliegen und Q/E zum Kippen — die Tastatur ist die
    # eigentliche Neuheit dieses Schemas, die Maustasten ordnen sich ihr zu.
    #
    # Dass links **schiebt** und trotzdem **auswählt**, ist kein Widerspruch:
    # Das Loslassen fragt ``is_click`` und trennt Klick von Zug an der
    # Zugschwelle des Systems. Wer zieht, bewegt die Ansicht; wer klickt,
    # wählt. Auf dem gewählten Körper führt links weiter das Teil selbst.
    "solidon": {
        ("left", False): "pan",
        ("left", True): "pan",
        ("middle", False): "tilt",
        ("middle", True): "tilt",
        ("right", False): "rotate",
        ("right", True): "rotate",
    },
    # Cura: links wählt, rechts dreht, Umschalt und Ziehen schiebt.
    "slicer": {
        ("left", False): "select",
        ("left", True): "pan",
        ("middle", False): "pan",
        ("middle", True): "pan",
        ("right", False): "rotate",
        ("right", True): "rotate",
    },
    # Bambu Studio, OrcaSlicer, PrusaSlicer: links dreht, rechts schiebt.
    "orbit": {
        ("left", False): "rotate",
        ("left", True): "rotate",
        ("middle", False): "pan",
        ("middle", True): "pan",
        ("right", False): "pan",
        ("right", True): "pan",
    },
    # CAD: die mittlere Taste dreht, mit Umschalt schiebt sie; links wählt,
    # damit es überhaupt eine Auswahltaste gibt, und rechts zoomt.
    "cad": {
        ("left", False): "select",
        ("left", True): "pan",
        ("middle", False): "rotate",
        ("middle", True): "pan",
        ("right", False): "zoom",
        ("right", True): "zoom",
    },
    # Blender: links wählt, die mittlere Taste dreht, Umschalt+Mitte schiebt.
    "blender": {
        ("left", False): "select",
        ("left", True): "pan",
        ("middle", False): "rotate",
        ("middle", True): "pan",
        ("right", False): "rotate",
        ("right", True): "rotate",
    },
}


def navigation_action(scheme: NavigationScheme, button: MouseButton, shift: bool) -> CameraAction:
    """Was diese Taste in diesem Schema an der Kamera tut.

    ``select`` heißt: Die Kamera rührt sich nicht — der Klick gehört der
    Auswahl, dem Werkzeug oder dem Körper darunter.
    """
    return _NAVIGATION[scheme][(button, shift)]


def is_click(start: tuple[int, int] | None, end: tuple[int, int]) -> bool:
    """Ob zwischen Drücken und Loslassen genug stillgestanden wurde.

    Eine Rechnung über zwei Punkte; ein Test dafür soll kein Fenster bauen
    müssen. Ohne Anfang gab es keinen Druck, den dieses Loslassen beendet —
    dann zählt es nicht.
    """
    if start is None:
        return False
    return abs(end[0] - start[0]) <= CLICK_SLACK and abs(end[1] - start[1]) <= CLICK_SLACK


def turntable_camera(
    position: Sequence[float],
    focal_point: Sequence[float],
    view_up: Sequence[float],
    dx: int,
    dy: int,
    size: Sequence[int],
) -> tuple[Vec3, Vec3]:
    """Ein Mauszug am Drehteller: neuer Standort und neues Oben (§2.9).

    ``dy`` zählt hier wie VTK — positiv heißt nach oben. Wer Qt-Ereignisse
    hereinreicht, dreht das Vorzeichen (:meth:`Navigator._turn`).

    **Der Fehler, den das behebt** (Robert, 04.09.2026: „das rotieren neigt
    immer noch statt den winkel zur mitte zu lassen"):
    ``vtkInteractorStyleTrackballCamera`` dreht um das **Oben der Kamera** und
    führt es dabei mit; ``OrthogonalizeViewUp`` stellt es hinterher nur wieder
    senkrecht zur Blickrichtung, nicht auf. Über eine Geste summiert sich
    daraus eine sichtbare Schräglage — an einer nackten ``vtkCamera``
    nachgerechnet, zwölf diagonale Züge aus derselben Ausgangslage: **62,7 Grad
    Neigung** gegen **0,0** hier.

    Ein Drehteller dreht stattdessen waagerecht immer um die **Welt-Hochachse**
    und senkrecht um die Bildwaagerechte. Das Oben folgt daraus, statt
    mitgeschleift zu werden — es ist die Welt-Hochachse, auf die Bildebene
    gestellt. So halten es Cura, Bambu Studio und Blender, und deshalb gilt es
    hier für alle fünf Schemata: Ein Nachbau, der neigt, wo sein Vorbild
    aufrecht bleibt, ist keiner.

    **Die Hebung wird begrenzt, nicht abgeschnitten** (:data:`POLE_LIMIT_
    DEGREES`): Wer schon fast senkrecht darüber steht, dreht weiter waagerecht
    und kommt jederzeit wieder herunter — nur über den Pol hinaus geht es
    nicht, denn dort gibt es kein Oben mehr. Aus einer Draufsicht heraus, die
    das Menü setzt, führt der Weg deshalb ebenso zurück.

    Reine Funktion auf Vektoren: Offscreen gibt es kein Fenster, und was
    hinter dieser Wache gerechnet wird, prüft in der Suite sonst niemand.
    """
    # Die Welt-Hochachse steht bei der 3D-Maus, und dort bleibt sie: Zwei
    # Fassungen derselben Zahl wären zwei Wahrheiten.
    from app.ui.spacemouse import WORLD_UP

    width = max(int(size[0]), 1)
    height = max(int(size[1]), 1)
    azimuth = -float(dx) * TURN_PER_PIXEL / width * TURN_MOTION_FACTOR
    elevation = -float(dy) * TURN_PER_PIXEL / height * TURN_MOTION_FACTOR

    focal = np.asarray(focal_point, dtype=float)
    offset = np.asarray(position, dtype=float) - focal
    distance = float(np.linalg.norm(offset))
    up = np.asarray(view_up, dtype=float)
    if distance <= EPS_GEOM:
        return (
            (float(position[0]), float(position[1]), float(position[2])),
            (float(view_up[0]), float(view_up[1]), float(view_up[2])),
        )

    world_up = np.asarray(WORLD_UP, dtype=float)
    offset = _turned_about(offset, world_up, azimuth)
    up = _turned_about(up, world_up, azimuth)

    forward = -offset / distance
    sideways = np.cross(forward, world_up)
    if float(np.linalg.norm(sideways)) <= EPS_GEOM:
        # Senkrechter Blick: Die Welt-Hochachse taugt hier nicht als Bezug,
        # das Oben des Bildes schon.
        sideways = np.cross(forward, up)
    sideways = sideways / float(np.linalg.norm(sideways))

    height_now = math.degrees(math.asin(max(-1.0, min(1.0, float(offset[2]) / distance))))
    height_next = max(-POLE_LIMIT_DEGREES, min(POLE_LIMIT_DEGREES, height_now + elevation))
    offset = _turned_about(offset, sideways, height_now - height_next)

    forward = -offset / float(np.linalg.norm(offset))
    upright = world_up - forward * float(np.dot(forward, world_up))
    if float(np.linalg.norm(upright)) > EPS_GEOM:
        up = upright / float(np.linalg.norm(upright))

    moved = focal + offset
    return (
        (float(moved[0]), float(moved[1]), float(moved[2])),
        (float(up[0]), float(up[1]), float(up[2])),
    )


def _turned_about(vector: np.ndarray, axis: np.ndarray, degrees: float) -> np.ndarray:
    """Einen Vektor um eine Achse drehen (Rodrigues).

    Eigene Rechnung statt ``vtkCamera.Azimuth`` und ``Elevation``: Jene drehen
    um das Oben **der Kamera**, und genau das ist der Unterschied, um den es
    in :func:`turntable_camera` geht.
    """
    axis = np.asarray(axis, dtype=float)
    length = float(np.linalg.norm(axis))
    vector = np.asarray(vector, dtype=float)
    if length <= EPS_GEOM:
        return vector
    axis = axis / length
    angle = math.radians(degrees)
    return (
        vector * math.cos(angle)
        + np.cross(axis, vector) * math.sin(angle)
        + axis * float(np.dot(axis, vector)) * (1.0 - math.cos(angle))
    )


class NavigatorCallbacks(NamedTuple):
    """Die Rückrufe, die der Navigator von der Ansicht bekommt.

    Alle Bildpunkte in Qt-Zählung. ``on_body_drag`` bekommt die Phase
    (``ready``, ``start``, ``move``, ``end``) und antwortet bei ``ready`` und
    ``start``, ob die Geste dem Körper gehört. ``on_end`` kommt nach jeder
    abgeschlossenen Kamerabewegung — Drehen, Schieben, Zoomen —, dort hängen
    Schatten und ``cameraMoved`` (bisher ``EndInteractionEvent``).
    """

    on_context: Callable[[int, int], None]
    on_pick: Callable[[int, int], None]
    on_cursor: Callable[[str | None], None]
    on_paint: Callable[[int, int, bool], None]
    is_sculpting: Callable[[], bool]
    on_body_drag: Callable[[str, int, int], bool]
    on_rotate_start: Callable[[], None]
    on_camera: Callable[[], None]
    on_tilt: Callable[[int], None]
    on_end: Callable[[], None]


class Navigator:
    """Zeigergesten in Kamerabewegung und Rückrufe übersetzen.

    Ein Navigator je Ansicht; die Ansicht meldet ihn beim Renderer an
    (``add_pointer_listener(navigator.handle)``) und tauscht das Schema über
    :meth:`set_scheme`. Er hält keinen Verweis auf die Ansicht — nur die
    Rückrufe, und die hält die Ansicht schwach (``_weak_callbacks``).
    """

    def __init__(
        self, renderer: Renderer, scheme: NavigationScheme, calls: NavigatorCallbacks
    ) -> None:
        self._renderer = renderer
        self._scheme: NavigationScheme = scheme
        self._calls = calls
        self._painting = False
        """Ob die linke Taste gerade malt statt die Kamera zu führen. Nur im
        Formzustand, und nur ohne Umschalt — schieben muss auch mitten in der
        Sitzung gehen."""
        self._right_at: tuple[int, int] | None = None
        """Wo die rechte Taste heruntergegangen ist. In jedem Schema tut
        Rechts auch etwas an der Kamera — das Menü darf nur aufgehen, wenn
        niemand gezogen hat."""
        self._left_at: tuple[int, int] | None = None
        """Dasselbe für links. In drei der fünf Schemata bewegt die linke
        Taste die Kamera; ausgewählt wird deshalb, wo niemand gezogen hat, und
        nicht danach, welches Schema gerade gilt."""
        self._ready_to_drag = False
        """Ob die linke Taste **auf** dem gewählten Körper heruntergegangen
        ist. Noch keine Entscheidung: Erst die Bewegung sagt, ob daraus ein
        Zug wird oder ein Klick."""
        self._dragging_body = False
        self._tilt_at: tuple[int, int] | None = None
        """Wo der Zeiger beim letzten Kippschritt stand — gemeldet wird die
        Strecke seit dem letzten Ereignis, sonst wüchse der Winkel quadratisch."""
        self._turn_at: tuple[int, int] | None = None
        self._pan_at: tuple[int, int] | None = None
        self._dolly_at: tuple[int, int] | None = None
        self._gesture: CameraAction | None = None

    @property
    def scheme(self) -> NavigationScheme:
        return self._scheme

    def set_scheme(self, scheme: NavigationScheme) -> None:
        self._scheme = scheme

    # --- Ereignisse -----------------------------------------------------------------

    def handle(self, event: PointerEvent) -> None:
        """Eine Zeigergeste — der einzige Eingang."""
        if event.kind == "press":
            self._press(event)
        elif event.kind == "move":
            self._move(event)
        elif event.kind == "release":
            self._release(event)
        elif event.kind == "wheel":
            if event.delta > 0:
                self._zoom_at(event.x, event.y, (1.0 + WHEEL_STEP) ** event.delta)
            elif event.delta < 0:
                self._zoom_at(event.x, event.y, (1.0 / (1.0 + WHEEL_STEP)) ** -event.delta)

    def _press(self, event: PointerEvent) -> None:
        position = (event.x, event.y)
        if event.button == "left":
            self._left_at = position
            if self._calls.is_sculpting() and not event.shift:
                # Malen statt Kamera (§18.11): Die Züge folgen dem gedrückten
                # Zeiger, der erste sitzt beim Drücken. Ein Klick je Zug hieß
                # zwanzig Klicks für einen Grat — in jedem Formprogramm ist
                # das ein Zug. Umschalt behält die Kamera, schieben muss auch
                # mitten in der Sitzung gehen.
                self._painting = True
                self._calls.on_paint(event.x, event.y, True)
                return
            if not event.shift and self._calls.on_body_drag("ready", event.x, event.y):
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
                # Pixel, ``CLICK_SLACK`` zehn (Qts eigene Zugschwelle).
                # Dazwischen lag ein Klick, der den Körper um Bruchteile
                # verschob **und** die Auswahl nicht wechselte (gemessen am
                # 23.08.2026 an drei Pixeln Wackeln, wie es beim Klicken
                # normal ist).
                self._ready_to_drag = True
                return
            self._begin("left", event.shift, position)
        elif event.button == "middle":
            self._begin("middle", event.shift, position)
        elif event.button == "right":
            self._right_at = position
            self._begin("right", event.shift, position)

    def _move(self, event: PointerEvent) -> None:
        now = (event.x, event.y)
        if self._painting:
            self._calls.on_paint(event.x, event.y, False)
            return
        if self._ready_to_drag or self._dragging_body:
            if not self._dragging_body:
                if is_click(self._left_at, now):
                    # Noch im Klickbereich — hier passiert nichts, damit
                    # ein Klick keinen Verlaufsschritt hinterlässt.
                    return
                # **Von der Stelle des Drückens aus**, nicht von hier:
                # Sonst spränge der Körper um die zurückgelegte Strecke.
                start = self._left_at or now
                if not self._calls.on_body_drag("start", start[0], start[1]):
                    self._ready_to_drag = False
                    return
                self._dragging_body = True
            # Ohne dieses ``return`` liefe die Kamera mit, und der Körper
            # wanderte vor einer Ansicht, die sich zugleich bewegt.
            self._calls.on_body_drag("move", event.x, event.y)
            return
        if self._tilt_at is not None:
            # Nur die senkrechte Strecke, und nur die seit dem letzten
            # Ereignis. Qt zählt von oben, das Kippen wie VTK von unten.
            step = self._tilt_at[1] - now[1]
            self._tilt_at = now
            if step:
                self._calls.on_tilt(step)
            return
        if self._turn_at is not None:
            step_x = now[0] - self._turn_at[0]
            step_y = self._turn_at[1] - now[1]
            self._turn_at = now
            if step_x or step_y:
                self._turn(step_x, step_y)
            return
        if self._pan_at is not None:
            self._pan(self._pan_at, now)
            self._pan_at = now
            return
        if self._dolly_at is not None:
            step_y = self._dolly_at[1] - now[1]
            self._dolly_at = now
            if step_y:
                self._dolly(step_y)

    def _release(self, event: PointerEvent) -> None:
        now = (event.x, event.y)
        if event.button == "left":
            painted, self._painting = self._painting, False
            self._end()
            started, self._left_at = self._left_at, None
            dragged, self._dragging_body = self._dragging_body, False
            self._ready_to_drag = False
            if dragged:
                # Hier entsteht der Schritt im Verlauf (Regel 2). Ein Zug, der
                # gar nicht erst begonnen hat, kommt hier nicht an — er war ein
                # Klick, und der wählt gleich darunter aus.
                self._calls.on_body_drag("end", event.x, event.y)
            if painted:
                # Die Züge sind schon beim Drücken und Ziehen gesetzt — der
                # Klickpfad malte denselben Punkt ein zweites Mal.
                return
            if is_click(started, now):
                self._calls.on_pick(event.x, event.y)
        elif event.button == "middle":
            self._end()
        elif event.button == "right":
            self._end()
            started, self._right_at = self._right_at, None
            # Ein Zug hat die Kamera bewegt und meint sie; ein Klick meint das,
            # worauf er zeigt.
            if is_click(started, now):
                self._calls.on_context(event.x, event.y)

    # --- die Kamerabewegungen -------------------------------------------------------

    def _begin(self, button: MouseButton, shift: bool, position: tuple[int, int]) -> None:
        """Die Kamerabewegung dieser Taste starten — laut Schema.

        Eine Stelle für alle drei Tasten: Die Zuordnung steht in
        :data:`_NAVIGATION`, hier steht nur, was daraus wird.
        """
        action = navigation_action(self._scheme, button, shift)
        if action == "select":
            return
        if action == "pan":
            self._pan_at = position
            self._gesture = "pan"
            self._calls.on_cursor("panning")
            return
        if action == "zoom":
            self._dolly_at = position
            self._gesture = "zoom"
            self._calls.on_cursor("zoom")
            return
        # Kippen und Drehen bekommen denselben Drehpunkt: die Tiefe dessen,
        # was in der Bildmitte steht, unsichtbar (§2.9, ``_aim_rotation``).
        # Ein Drehpunkt, der bei der rechten Taste die Bildmitte ist und beim
        # gedrückten Rad die Mitte der Körper, wäre eine Inkonsistenz, die
        # sich niemandem erklären ließe.
        self._calls.on_rotate_start()
        if action == "tilt":
            self._tilt_at = position
            self._gesture = "tilt"
            self._calls.on_cursor("tilt")
            return
        self._turn_at = position
        self._gesture = "rotate"
        self._calls.on_cursor("rotate")

    def _end(self) -> None:
        """Jede Bewegung beenden — welche lief, sagt ``_gesture``."""
        gesture, self._gesture = self._gesture, None
        self._tilt_at = None
        self._turn_at = None
        self._pan_at = None
        self._dolly_at = None
        if gesture in ("pan", "zoom", "rotate"):
            # Bisher das ``EndInteractionEvent`` von VTK, das nur Zustände mit
            # ``StartRotate``/``StartPan``/``StartDolly`` auslösten — das
            # Kippen meldet sich je Schritt selbst.
            self._calls.on_end()
        self._calls.on_cursor(None)

    def _turn(self, dx: int, dy: int) -> None:
        """Ein Drehschritt als Drehteller — die Ansicht bleibt aufrecht."""
        pose = self._renderer.camera_pose()
        position, up = turntable_camera(
            pose.position, pose.focal_point, pose.view_up, dx, dy, self._renderer.view_size()
        )
        self._renderer.set_camera_pose(CameraPose(position, pose.focal_point, up))
        self._renderer.render()

    def _pan(self, start: tuple[int, int], now: tuple[int, int]) -> None:
        """Die Ansicht schieben: Der Weltpunkt unter dem Zeiger bleibt unter
        dem Zeiger — gerechnet auf der Fokusebene, wie VTKs Trackball."""
        depth = self._renderer.focal_depth()
        before = self._renderer.display_to_world(start[0], start[1], depth)
        after = self._renderer.display_to_world(now[0], now[1], depth)
        if before is None or after is None:
            return
        shift = tuple(before[axis] - after[axis] for axis in range(3))
        self._shift_camera(shift)
        self._renderer.render()

    def _dolly(self, dy: int) -> None:
        """Zoomen durch Ziehen (CAD-Schema): senkrechter Weg als Exponent."""
        height = max(self._renderer.view_size()[1], 1)
        factor = DOLLY_BASE ** (DOLLY_MOTION_FACTOR * float(dy) / (height / 2.0))
        self._renderer.dolly(factor)
        self._renderer.render()

    def _zoom_at(self, x: int, y: int, factor: float) -> None:
        """Zoomt auf die Stelle unter dem Zeiger, nicht auf die Bildmitte.

        Ein Dolly entlang der Kamera-Achse lässt den Punkt unter dem Zeiger
        wegwandern — man zoomt an dem vorbei, was man ansehen wollte. Handbuch
        und Code-Kommentar behaupteten einmal beide das Gegenteil; nachgemessen
        stimmte keines von beiden.

        Der Weg: den Weltpunkt unter dem Zeiger vorher merken, zoomen, ihn
        danach neu bestimmen und die Kamera um die Differenz verschieben.
        Damit bleibt genau dieser Punkt stehen, wo er war.
        """
        before = self._renderer.display_to_world(x, y, self._renderer.focal_depth())
        self._renderer.dolly(factor)
        after = self._renderer.display_to_world(x, y, self._renderer.focal_depth())
        if before is not None and after is not None:
            self._shift_camera(tuple(before[axis] - after[axis] for axis in range(3)))
        self._renderer.render()
        self._calls.on_camera()

    def _shift_camera(self, shift: Sequence[float]) -> None:
        pose = self._renderer.camera_pose()
        self._renderer.set_camera_pose(
            CameraPose(
                (
                    pose.position[0] + shift[0],
                    pose.position[1] + shift[1],
                    pose.position[2] + shift[2],
                ),
                (
                    pose.focal_point[0] + shift[0],
                    pose.focal_point[1] + shift[1],
                    pose.focal_point[2] + shift[2],
                ),
                pose.view_up,
            )
        )
