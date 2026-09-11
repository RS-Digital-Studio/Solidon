"""Der Langlochgriff am gewählten Loch (Bauplan §18.11, §21.1).

Der Bewegungsgriff (``render/gizmo.py``) schiebt und dreht, der Skalierwürfel
(``scale_widget.py``) skaliert den ganzen Körper. Beide lassen die Frage offen,
die an einer Bohrung als Erstes kommt: **wie wird daraus ein Langloch?** Die
Antwort war bis hierher ein Dialog mit zwei Zahlen — Länge und Winkel —, und
wer eine Richtung meint, meint sie im Bild und nicht in Grad.

Dieser Griff ist die zweite Antwort auf dieselbe Frage: zwei Knöpfe an den
Enden des Lochs, gezogen wird in der Ebene seiner Mündung. Der Zug gibt beides
zugleich — die **Länge** aus dem Abstand zur Mitte, die **Richtung** aus dem
Winkel dazu. An einer runden Bohrung sitzen die Knöpfe auf ihrem Rand: Sie
behaupten damit keine Richtung, sie bieten einen Anfasser.

**Form trägt die Bedeutung, nicht die Farbe** (Regel 18): Pfeil heißt schieben,
Ring heißt drehen, Würfel heißt skalieren — und ein runder Knopf heißt ziehen.
Beim Überfahren leuchtet er in derselben Farbe wie die Pfeile daneben; ein
Griff-Satz, eine Sprache.

**Er ändert keine Geometrie** (Regel 2). Während des Zugs zeigt er den Umriss,
den die Operation schneiden wird; beim Loslassen bekommt die Ansicht Länge und
Winkel, und daraus wird genau ein ``slot_hole`` — eine Geste, eine Transaktion
(§15.5). Der Umriss kommt aus derselben Funktion wie der Schnitt selbst
(:func:`app.core.geom.prepare.slot_profile`): Ein zweiter Umriss daneben liefe
beim nächsten Zuwachs auseinander, und der Kunde sähe eine Form und bekäme eine
andere.
"""

from __future__ import annotations

import math
from collections.abc import Callable

import numpy as np

from app.core.geom.prepare import shortest_slot
from app.core.units import EPS_GEOM, is_close
from app.ui.render import shapes
from app.ui.render.api import Colour, Item, PointerEvent, Renderer, SurfaceStyle, Vec3
from app.ui.render.gizmo import HIGHLIGHT, ray_plane_hit
from app.ui.render.navigator import CLICK_SLACK

# **Wie kurz ein Zug das Loch machen darf, steht im Kern.**
#
# Hier stand bis zum 11.09.2026 eine eigene Zahl (``1.05``), und der Kern hatte
# seine (``Durchmesser + ε``). Zwei Grenzen für eine Frage, und die des Griffs
# lag genau dort, wo die Merkmalserkennung kippt: Wer bis zum Anschlag zurückzog,
# bekam im Objektbaum eine **Bohrung** statt seines Langlochs — oder gar nichts,
# und damit nichts mehr zum Anklicken. Die Begründung der Zahl steht bei
# :data:`app.core.geom.prepare.SLOT_SHORTEST_SHARE`; der Griff fragt.

#: Wie fein der Umriss abgetastet wird — beide Bögen zusammen.
#:
#: Er ist eine Linie im Bild und kein geschnittener Körper; die Sehnen dürfen
#: hier auffallen, wo sie es in der Geometrie nicht dürften. Vierundsechzig
#: Punkte auf zwei Halbkreise sind bei jedem Zoom rund.
OUTLINE_SEGMENTS = 64

#: Der Knopf im Maß des Bohrungsdurchmessers: Radius und Höhe.
#:
#: Er sitzt auf dem Rand des Lochs und darf es nicht zudecken — und er muss
#: getroffen werden können. Die Ansicht deckelt ihn nach unten über
#: :meth:`app.ui.viewport.Viewport._handle_radius` (Untergrenze
#: ``FACE_HANDLE_MINIMUM``), denn ein Loch von einem Millimeter hat keinen
#: Griff, den man mit der Maus fände; und der Griff selbst deckelt nach oben
#: (:data:`WIDEST_KNOB_SHARE`), damit er das Loch nicht zudeckt.
KNOB_RADIUS_SHARE = 0.22
KNOB_HEIGHT_SHARE = 0.30

#: Wie rund der Knopf gezeichnet wird.
KNOB_SEGMENTS = 24

#: Wie breit die zwei Knöpfe zusammen höchstens werden, im Maß der Länge.
#:
#: **Sonst decken sie zu, was sie anfassen sollen.** Gemessen am Anteil der
#: Mündungsfläche, den sie in Achsrichtung verdecken: bei Ø 1 volle 100 Prozent,
#: bei Ø 2 noch 57,7 — und unter Ø 1,68 überlappten sie einander. Sie sind
#: anklickbar und stehen vorn; damit war die Lehre von ``_face_handle`` zurück
#: („Ein Klick auf die Bohrung traf den Griff statt des Körpers", Robert,
#: 03.09.2026). Vier Zehntel der Länge lassen zwischen den beiden Knöpfen
#: immer eine Lücke, durch die das Loch selbst zu treffen ist.
WIDEST_KNOB_SHARE = 0.4

#: Die Hervorhebung beim Überfahren — dieselbe wie an Pfeilen, Ringen und
#: Würfel, damit alle Griffe dieselbe Sprache sprechen.
HOVER_COLOUR: Colour = HIGHLIGHT

#: Die Breite der Umrisslinie in Bildpunkten.
OUTLINE_WIDTH = 3.0

__all__ = [
    "HOVER_COLOUR",
    "KNOB_HEIGHT_SHARE",
    "KNOB_RADIUS_SHARE",
    "OUTLINE_SEGMENTS",
    "WIDEST_KNOB_SHARE",
    "SlotHandle",
    "dragged_slot",
    "plane_axes",
    "slot_outline",
]


def plane_axes(axis: shapes.Vec) -> tuple[np.ndarray, np.ndarray]:
    """Die beiden Achsen der Mündungsebene, wie der Kern sie zählt.

    Aus :func:`app.core.sketch.planes.frame_of`, und aus keiner zweiten Quelle:
    Der Winkel eines Langlochs wird gegen genau diese x-Achse gemessen — beim
    Schneiden (:func:`app.core.geom.prepare.slot_profile`) wie beim Nachmessen
    an einem erkannten (``prepare_ops.slot_angle_of``). Wer hier eine eigene
    Achse wählte, bekäme einen Griff, der um einen Winkel danebenliegt, den
    niemand erklären kann.
    """
    from app.core.sketch.planes import frame_of

    frame = frame_of((float(axis[0]), float(axis[1]), float(axis[2])), (0.0, 0.0, 0.0))
    return (
        np.asarray(frame.x_axis, dtype=float),
        np.asarray(frame.y_axis, dtype=float),
    )


def dragged_slot(
    centre: shapes.Vec,
    axis: shapes.Vec,
    diameter: float,
    point: shapes.Vec,
    *,
    angle: float = 0.0,
) -> tuple[float, float]:
    """Länge und Richtung, die ein Zug bis ``point`` meint.

    Der Knopf sitzt am Scheitel des Lochs; sein Abstand zur Mitte ist also die
    **halbe** Länge, und die volle ist sein Doppeltes. Die Richtung ist der
    Winkel desselben Abstands in der Mündungsebene, gemessen gegen die x-Achse
    ihres Rahmens — dieselbe Zählung, die die Operation liest.

    ``angle`` ist die Richtung, die gerade gilt. Sie zählt genau dort, wo der
    Zug keine eigene hat: über der Mitte ist jede Richtung gleich weit weg, und
    ein Loch, das dort umspringt, folgt dem Zittern der Hand statt der Absicht.
    """
    x_axis, y_axis = plane_axes(axis)
    offset = np.asarray(point, dtype=float) - np.asarray(centre, dtype=float)
    across = float(offset @ x_axis)
    along = float(offset @ y_axis)
    reach = math.hypot(across, along)
    turned = math.degrees(math.atan2(along, across)) if reach > EPS_GEOM else float(angle)
    return max(2.0 * reach, shortest_slot(diameter)), _normalised_angle(turned)


def _normalised_angle(angle: float) -> float:
    """Der Winkel in ``(-180, 180]`` — der Bereich, den das Feld führt.

    Ein Zug um die Mitte herum läuft sonst über die Grenze des Parameters
    hinaus, und die Operation lehnte ihn ab, statt das Loch zu drehen.
    """
    turned = (float(angle) + 180.0) % 360.0 - 180.0
    return 180.0 if is_close(turned, -180.0) else turned


def slot_outline(
    centre: shapes.Vec,
    axis: shapes.Vec,
    diameter: float,
    length: float,
    angle: float,
    *,
    segments: int = OUTLINE_SEGMENTS,
) -> np.ndarray:
    """Der Umriss, den dieser Zug schneiden wird — als geschlossener Linienzug.

    Gebaut aus :func:`app.core.geom.prepare.slot_profile`, dem Umriss der
    Operation selbst. Die Bögen kommen über ihre drei Punkte zurück auf den
    Kreis (:func:`app.core.sketch.profile.arc_through`) und werden abgetastet;
    die Geraden bleiben Geraden.
    """
    from app.core.geom.prepare import slot_profile, slot_travel
    from app.core.sketch.planes import frame_of, to_world
    from app.core.sketch.profile import arc_through

    frame = frame_of(
        (float(axis[0]), float(axis[1]), float(axis[2])),
        (float(centre[0]), float(centre[1]), float(centre[2])),
    )
    outline = slot_profile(
        radius=diameter / 2.0,
        travel=slot_travel(diameter=diameter, length=length),
        angle_deg=angle,
    )
    per_arc = max(2, segments // 2)
    flat: list[tuple[float, float]] = []
    for segment in outline.segments:
        start, end = segment.start, segment.end
        if segment.kind != "arc" or segment.via is None:
            flat.append(start)
            continue
        circle = arc_through(start, segment.via, end)
        if circle is None:
            flat.append(start)
            continue
        (mid_x, mid_y), radius, sweep = circle
        begin = math.atan2(start[1] - mid_y, start[0] - mid_x)
        for step in range(per_arc):
            turn = begin + sweep * (step / per_arc)
            flat.append((mid_x + radius * math.cos(turn), mid_y + radius * math.sin(turn)))
    if not flat:
        return np.zeros((0, 3), dtype=float)
    flat.append(flat[0])
    return np.asarray([to_world(frame, point) for point in flat], dtype=float)


class SlotHandle:
    """Die zwei Knöpfe, an denen ein Loch in die Länge gezogen wird.

    ``release_callback`` bekommt beim Loslassen Länge und Winkel des Zugs;
    ``interact_callback`` jeden Zwischenstand — für die Zahl neben dem Zeiger,
    nicht für Geometrie. Was während des Zugs im Bild steht, ist der Umriss des
    künftigen Lochs und eine Vorschau (Regel 2).

    ``centre``, ``axis`` und ``diameter`` beschreiben das gewählte Merkmal in
    den Koordinaten, in denen es **gezeichnet** wird — bei mehreren Platten ist
    das nicht seine Szenenkoordinate (§25). Länge und Winkel gehen ohne diesen
    Versatz zurück: Beide sind Differenzen und kennen ihn nicht.
    """

    def __init__(
        self,
        renderer: Renderer,
        *,
        centre: Vec3,
        axis: Vec3,
        diameter: float,
        length: float,
        angle: float,
        knob_size: float,
        colour: Colour,
        release_callback: Callable[[float, float], None],
        interact_callback: Callable[[float, float], None] | None = None,
        cancel_callback: Callable[[], None] | None = None,
        settle_angle: Callable[[float], float] | None = None,
    ) -> None:
        self._renderer = renderer
        self._release = release_callback
        self._interact = interact_callback
        self._cancel = cancel_callback
        self._settle_angle = settle_angle
        self._press_point = (0, 0)
        self._dragged = False
        self._had_outline = False
        self._centre = np.asarray(centre, dtype=float)
        self._axis = np.asarray(axis, dtype=float)
        self._diameter = float(diameter)
        self._colour = colour
        self.length = max(float(length), shortest_slot(self._diameter))
        self.angle = _normalised_angle(angle)
        self._start_length = self.length
        self._start_angle = self.angle
        # Nach oben gedeckelt: Zwei Knöpfe, die zusammen breiter sind als die
        # Lücke zwischen ihnen, verstecken das Loch, an dem sie sitzen.
        widest = self.length * WIDEST_KNOB_SHARE / (2.0 * KNOB_RADIUS_SHARE)
        self._knob_size = min(float(knob_size), widest)
        self._held: int | None = None
        self._hovered: int | None = None
        self.pressing = False

        self._knobs: list[Item] = []
        self._built_seats: list[Vec3] = []
        """Wo die zwei Zylinder **gebaut** wurden.

        Der Bezug jedes Versatzes, und er gehört der Geometrie und nicht dem
        Zug: ``Item.set_position`` verschiebt gegen das, was einmal in den
        Puffer geschrieben wurde. Gerechnet wurde er bis zum 10.09.2026 gegen
        ``_start_length``/``_start_angle`` — den Stand beim **Drücken**. Beim
        ersten Zug ist das dasselbe, beim zweiten nicht mehr: Der Bezug wandert
        mit, der Puffer bleibt, und die Knöpfe laufen aus dem Umriss heraus, die
        beiden in entgegengesetzte Richtungen (Robert: „wenn ich das langloch
        ziehe driften die ziehpunkte für das langloch ab … sie bewegen sich
        entgegengesetzt")."""
        for index in range(2):
            seat = self._knob_seat(index, self.length, self.angle)
            self._built_seats.append(seat)
            vertices, faces = shapes.cylinder(
                seat,
                tuple(self._axis),
                radius=self._knob_size * KNOB_RADIUS_SHARE,
                height=self._knob_size * KNOB_HEIGHT_SHARE,
                segments=KNOB_SEGMENTS,
            )
            self._knobs.append(
                renderer.add_surface(
                    vertices,
                    faces,
                    name=f"slot-handle:knob:{index}",
                    style=SurfaceStyle(
                        colour=colour, lighting=False, keep_in_front=True, pickable=True
                    ),
                )
            )
        self._outline: Item | None = None

    # --- Aufbau --------------------------------------------------------------------

    def _knob_seat(self, index: int, length: float, angle: float) -> Vec3:
        """Wo ein Knopf sitzt: am Scheitel des Lochs, links und rechts."""
        x_axis, y_axis = plane_axes(self._axis)
        turn = math.radians(angle)
        along = math.cos(turn) * x_axis + math.sin(turn) * y_axis
        reach = (length / 2.0) * (1.0 if index == 0 else -1.0)
        seat = self._centre + along * reach
        return (float(seat[0]), float(seat[1]), float(seat[2]))

    @property
    def items(self) -> tuple[Item, ...]:
        """Was der Griff im Bild hält — für Beschriftung und Tests."""
        return (*self._knobs, *(() if self._outline is None else (self._outline,)))

    @property
    def knobs(self) -> tuple[Item, ...]:
        """Die zwei Anfasser, ohne den Umriss."""
        return tuple(self._knobs)

    @property
    def knob_seats(self) -> tuple[Vec3, ...]:
        """Wo die Knöpfe gerade sitzen — die Beschriftung stellt ihr L dahinter.

        Gerechnet und nicht am Aktor abgelesen: ``Item.position()`` trägt den
        **Versatz** gegen die gebaute Geometrie, nicht den Ort. Wer ihn für
        eine Stelle hält, beschriftet den Weltursprung.
        """
        return tuple(self._knob_seat(index, self.length, self.angle) for index in (0, 1))

    @property
    def clearance(self) -> tuple[Vec3, float]:
        """Mitte und Reichweite der Knöpfe, die Maßfelder frei halten müssen."""
        centre: Vec3 = (float(self._centre[0]), float(self._centre[1]), float(self._centre[2]))
        return centre, self.length / 2.0 + self._knob_size * KNOB_RADIUS_SHARE

    def remove(self) -> None:
        for item in self._knobs:
            self._renderer.remove(item)
        self._knobs.clear()
        self._drop_outline()
        self._held = None
        self._hovered = None
        self.pressing = False

    def _drop_outline(self) -> None:
        if self._outline is not None:
            self._renderer.remove(self._outline)
            self._outline = None

    # --- Gesten --------------------------------------------------------------------

    def handle(self, event: PointerEvent) -> bool:
        """Eine Zeigergeste — wahr, wenn sie dem Griff gehört.

        Dieselbe Vorfahrt wie an Bewegungsgriff und Skalierwürfel: Was ``True``
        zurückgibt, erreicht die Kameraführung nicht mehr
        (:meth:`app.ui.viewport.Viewport._on_pointer`).
        """
        if event.kind == "move":
            if self.pressing:
                self._drag(event)
                return True
            self._hover(event)
            return False
        if event.kind == "press" and event.button == "left":
            if self._hovered is None:
                return False
            self._held = self._hovered
            self.pressing = True
            self._start_length = self.length
            self._start_angle = self.angle
            self._press_point = (event.x, event.y)
            self._dragged = False
            self._had_outline = self._outline is not None
            return True
        if event.kind == "release" and event.button == "left" and self.pressing:
            self.pressing = False
            self._held = None
            # **Der Umriss bleibt stehen.** Was der Zug hinterlässt, ist noch
            # keine Geometrie, sondern ein Vorschlag: Die Leiste daneben trägt
            # seine zwei Maße zum Nachbessern im Merkmalfenster, und
            # wer sie ohne Bild bediente, tippte gegen nichts. Abgeräumt wird
            # er mit dem Griff (:meth:`remove`) — also beim Übernehmen, beim
            # Abbrechen und bei jeder neuen Auswahl.
            #
            # **Ein bloßer Klick ist kein Zug.** Wer einen Knopf antippt, ohne
            # die Maus zu bewegen, hat nichts gewählt — gemeldet würde die
            # Mindestlänge, die niemand meint, und die Leiste ginge über einer
            # Zahl auf, die aus dem Nichts kommt. Gemessen an einer Ø-6-Bohrung:
            # (6,30 | 0°) nach einem Klick ohne Bewegung.
            if not self._dragged:
                return True
            if math.hypot(
                event.x - self._press_point[0], event.y - self._press_point[1]
            ) <= CLICK_SLACK or (
                is_close(self.length, self._start_length)
                and is_close(self.angle, self._start_angle)
            ):
                self.length, self.angle = self._start_length, self._start_angle
                self._redraw()
                if not self._had_outline:
                    self._drop_outline()
                    self._renderer.render()
                if self._cancel is not None:
                    self._cancel()
                return True
            self._release(self.length, self.angle)
            return True
        if event.kind == "leave" and not self.pressing:
            self._select(None)
        return False

    def set_values(self, length: float, angle: float) -> None:
        """Länge und Richtung von außen — die nachgebesserte Zahl aus der Leiste.

        Dieselbe Rechnung wie beim Zug, nur ohne Zeiger: Knöpfe an ihre Stelle,
        Umriss auf die neue Form. Was hier hereinkommt, ist bereits geklemmt
        (das Feld nimmt nichts unter dem Durchmesser an) — geklemmt wird
        trotzdem, denn ein Aufrufer ohne Feld gäbe es sonst frei.
        """
        self.length = max(float(length), shortest_slot(self._diameter))
        self.angle = _normalised_angle(angle)
        self._redraw()

    def _hover(self, event: PointerEvent) -> None:
        found = self._renderer.pick_item(event.x, event.y)
        wanted: int | None = None
        for index, item in enumerate(self._knobs):
            if found is item:
                wanted = index
        if wanted != self._hovered:
            self._select(wanted)
            self._renderer.render()

    def _select(self, wanted: int | None) -> None:
        if self._hovered is not None and self._hovered < len(self._knobs):
            self._knobs[self._hovered].set_colour(self._colour)
        self._hovered = wanted
        if wanted is not None:
            self._knobs[wanted].set_colour(HOVER_COLOUR)

    def _ray(self, event: PointerEvent) -> tuple[Vec3, Vec3] | None:
        near = self._renderer.display_to_world(event.x, event.y, 0.0)
        far = self._renderer.display_to_world(event.x, event.y, 1.0)
        if near is None or far is None:
            return None
        direction = (far[0] - near[0], far[1] - near[1], far[2] - near[2])
        if math.sqrt(sum(value * value for value in direction)) <= EPS_GEOM:
            return None
        return near, direction

    def _drag(self, event: PointerEvent) -> None:
        """Der Zeiger auf der Mündungsebene wird Länge und Winkel.

        **Gerechnet wird gegen die Ebene, nicht gegen den Bildschirm.** Der Zug
        trifft dieselbe Stelle, gleich wie weit die Kamera weg steht und wie
        schräg sie auf das Loch sieht — dieselbe Zusage wie am Bewegungsgriff.
        Steht die Kamera genau in der Ebene, gibt es keinen Schnittpunkt, und
        dann bleibt alles, wie es war.
        """
        if not self._dragged and (
            math.hypot(event.x - self._press_point[0], event.y - self._press_point[1])
            <= CLICK_SLACK
        ):
            return
        ray = self._ray(event)
        if ray is None:
            return
        hit = ray_plane_hit(ray[0], ray[1], tuple(self._centre), tuple(self._axis))
        if hit is None:
            return
        length, angle = dragged_slot(
            self._centre, self._axis, self._diameter, hit, angle=self._start_angle
        )
        # Der gegriffene Knopf folgt dem Zeiger — der andere spiegelt ihn. Das
        # Loch wächst damit um seine Mitte, und die bleibt, wo die Bohrung
        # gemessen wurde: Sie ist der einzige Wert, den die Operation nicht
        # mitbekommt (``slot_hole`` liest sie aus dem Merkmal).
        if self._held == 1:
            angle = _normalised_angle(angle + 180.0)
        if self._settle_angle is not None:
            angle = _normalised_angle(self._settle_angle(angle))
        self._dragged = True
        self.length, self.angle = length, angle
        self._redraw()
        if self._interact is not None:
            self._interact(self.length, self.angle)

    def _redraw(self) -> None:
        """Knöpfe an ihre neue Stelle, Umriss auf die neue Form."""
        for index, item in enumerate(self._knobs):
            seat = np.asarray(self._knob_seat(index, self.length, self.angle), dtype=float)
            offset = seat - np.asarray(self._built_seats[index], dtype=float)
            item.set_position((float(offset[0]), float(offset[1]), float(offset[2])))
        points = slot_outline(self._centre, self._axis, self._diameter, self.length, self.angle)
        if len(points) < 2:
            return
        if self._outline is None:
            self._outline = self._renderer.add_lines(
                points,
                name="slot-handle:outline",
                colour=self._colour,
                width=OUTLINE_WIDTH,
                pickable=False,
                keep_in_front=True,
                connected=True,
            )
        else:
            self._outline.update_points(points)
        self._renderer.render()
