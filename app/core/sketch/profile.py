"""Vom gelösten Skizzenelement zum geschlossenen Umriss (Bauplan §30.1).

Die Skizzen-Operationen brauchen keinen Punktehaufen, sondern einen Umriss:
eine geschlossene Kette aus Strecken und Bögen — oder einen einzelnen Kreis.
Bögen bleiben Bögen: der B-Rep-Kern bekommt die exakte Kurve, nicht eine
Segmentfolge (§30).

Ein Umriss, der nicht schließt oder sich verzweigt, ist keine Rechengrundlage
und wird mit einem Vorschlag zurückgewiesen — nicht stillschweigend geflickt
(Regel 21).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Literal

from app.core.errors import CORRECT_INPUT, Action, GeometryError
from app.core.types import Point2, SolvedSketch
from app.i18n import TranslatableText, _

#: Wie nah zwei Endpunkte beieinander liegen müssen, um als verbunden zu
#: gelten. Gelöste Koinzidenzen liegen bei 1e-9; das hier ist bewusst gröber,
#: bleibt aber weit unter jedem druckbaren Maß.
_JOIN_TOL = 1e-4


@dataclass(frozen=True, slots=True)
class ProfileSegment:
    """Eine Strecke oder ein Bogen des Umrisses.

    ``via`` ist bei Bögen ein Punkt **auf** der Kurve zwischen Anfang und
    Ende — damit bleibt die Geometrie beim Umdrehen der Laufrichtung
    dieselbe, und der Kern baut den Bogen aus drei Punkten exakt nach."""

    kind: Literal["line", "arc", "spline"]
    start: Point2
    end: Point2
    via: Point2 | None = None
    through: tuple[Point2, ...] = ()
    """Bei einem Spline **alle** Punkte, durch die er läuft, einschließlich
    Anfang und Ende. Der Kern legt daraus eine B-Spline-Kurve, die jeden davon
    trifft — segmentiert wird nichts, und beim Umdrehen der Laufrichtung dreht
    sich diese Liste mit."""


@dataclass(frozen=True, slots=True)
class Profile:
    """Ein geschlossener Umriss: entweder eine Segmentkette oder ein Kreis."""

    segments: tuple[ProfileSegment, ...] = ()
    circle: tuple[Point2, float] | None = None

    @property
    def is_circle(self) -> bool:
        return self.circle is not None


def profile_of(solved: SolvedSketch) -> Profile:
    """Verkettet die Elemente einer gelösten Skizze zu einem Umriss."""
    circles = [element for element in solved.elements if element.kind == "circle"]
    drawable = [element for element in solved.elements if element.kind in ("line", "arc", "spline")]

    if circles and not drawable:
        if len(circles) > 1:
            raise _broken(_("Mehrere Kreise ergeben keinen einzelnen Umriss."))
        centre, rim = circles[0].points
        return Profile(circle=(centre, math.dist(centre, rim)))
    if circles:
        raise _broken(_("Ein Kreis und offene Elemente zusammen ergeben keinen Umriss."))
    if not drawable:
        raise _broken(_("Die Skizze enthält nichts, was einen Umriss ergeben könnte."))

    segments = [_segment(element.kind, element.points) for element in drawable]
    chain = [segments.pop(0)]
    while segments:
        tail = chain[-1].end
        matches = [
            (index, candidate)
            for index, candidate in enumerate(segments)
            if _joins(tail, candidate.start) or _joins(tail, candidate.end)
        ]
        if not matches:
            raise _broken(_("Der Umriss ist nicht geschlossen — ein Ende bleibt frei."))
        if len(matches) > 1:
            raise _broken(_("Der Umriss verzweigt sich — an einem Punkt treffen sich drei Kanten."))
        index, candidate = matches[0]
        segments.pop(index)
        chain.append(candidate if _joins(tail, candidate.start) else _flipped(candidate))
    if not _joins(chain[-1].end, chain[0].start):
        raise _broken(_("Der Umriss ist nicht geschlossen — ein Ende bleibt frei."))
    return Profile(segments=tuple(chain))


def shifted(profile: Profile, dx: float, dy: float) -> Profile:
    """Derselbe Umriss, in der Ebene verschoben — wo er hingehört, entscheidet
    die Operation, nicht die Skizze."""
    if profile.circle is not None:
        centre, radius = profile.circle
        return Profile(circle=((centre[0] + dx, centre[1] + dy), radius))
    return Profile(
        segments=tuple(
            ProfileSegment(
                segment.kind,
                (segment.start[0] + dx, segment.start[1] + dy),
                (segment.end[0] + dx, segment.end[1] + dy),
                via=None if segment.via is None else (segment.via[0] + dx, segment.via[1] + dy),
                # Die Stützpunkte ziehen mit: ohne sie käme der Spline
                # verschoben an seinen Enden und unverschoben dazwischen an.
                through=tuple((x + dx, y + dy) for x, y in segment.through),
            )
            for segment in profile.segments
        )
    )


def _segment(kind: str, points: tuple[Point2, ...]) -> ProfileSegment:
    if kind == "line":
        return ProfileSegment("line", points[0], points[1])
    if kind == "spline":
        return ProfileSegment("spline", points[0], points[-1], through=points)
    centre, start, end = points
    return ProfileSegment("arc", start, end, via=_arc_midpoint(centre, start, end))


def _arc_midpoint(centre: Point2, start: Point2, end: Point2) -> Point2:
    """Der Punkt auf halbem Weg des Bogens, gegen den Uhrzeigersinn gerechnet."""
    radius = math.dist(centre, start)
    begin = math.atan2(start[1] - centre[1], start[0] - centre[0])
    finish = math.atan2(end[1] - centre[1], end[0] - centre[0])
    sweep = (finish - begin) % (2.0 * math.pi)
    if sweep == 0.0:
        sweep = 2.0 * math.pi
    middle = begin + sweep / 2.0
    return (centre[0] + radius * math.cos(middle), centre[1] + radius * math.sin(middle))


def _flipped(segment: ProfileSegment) -> ProfileSegment:
    return ProfileSegment(
        segment.kind,
        segment.end,
        segment.start,
        via=segment.via,
        through=tuple(reversed(segment.through)),
    )


def _joins(a: Point2, b: Point2) -> bool:
    return math.dist(a, b) <= _JOIN_TOL


def _broken(detail: TranslatableText | str) -> GeometryError:
    return GeometryError(
        _("Aus dieser Skizze wird kein Umriss."),
        detail,
        suggestions=(
            Action("open_sketch", _("Skizze ansehen"), primary=True),
            CORRECT_INPUT,
        ),
    )
