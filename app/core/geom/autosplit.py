"""Auto Split: ein Teil schneiden, bis es auf die Platte passt (Bauplan
§22.3, §25).

Die Trennebene wird mit derselben Maschinerie gefunden wie die
Orientierungssuche — der Schichtanalyse (§22.3). Für eine Reihe von
Schnittpositionen wird der Querschnitt gerechnet und beurteilt, der beste
gewinnt. Was einen Schnitt gut macht, ist nicht seine Größe:

* **Eine Kontur, nicht fünf.** Eine Ebene durch fünf dünne Arme hinterlässt
  fünf dünne Brücken, und jede davon ist eine Stelle, an der das Teil bricht.
* **Prismatisch.** Wo sich der Querschnitt über einen Millimeter kaum ändert,
  läuft der Schnitt durch ein gerades Stück — die zwei Flächen treffen sich
  plan, und ein Passstift findet auf beiden Seiten Material. Wo er sich
  schnell ändert, schneidet die Ebene quer durch eine Kurve.
* **Ausgewogen.** Von zwei gleich guten Schnitten gewinnt der näher an der
  Mitte: er braucht weniger Schnitte, bis alles auf der Platte liegt.

Wo gar keine Ebene hilft, wird die konvexe Zerlegung gefragt, wo der Körper
von selbst auseinanderfällt, und der Schnitt dorthin gelegt — als Ebene,
nicht als die Hüllen selbst. Hüllenstücke sind eine Näherung, und eine
Näherung wieder zusammenzukleben ergibt ein genähertes Teil (§11.1).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Final

import numpy as np

from app.core.deferred import trimesh
from app.core.errors import PROGRAMMING_ERRORS
from app.core.geom.mesh import MeshData
from app.core.geom.section import AXIS_NORMALS, Axis, SectionPlane
from app.core.log import get_logger
from app.core.slice.analysis import cross_sections
from app.core.types import CancelToken, Finding, Profile, Vec3
from app.core.units import EPS_GEOM
from app.i18n import _

_log = get_logger(__name__)

#: Wie viele Schnittpositionen je Achse probiert werden. Genug, um die flache
#: Stelle eines echten Teils zu finden, wenig genug, dass die Suche unter
#: einer Sekunde bleibt.
SAMPLES = 33

#: Wie weit das Teil unter dem Bauraum bleiben muss. Keine Dekoration: ein
#: Teil, das die Platte exakt füllt, lässt sich neben nichts mehr anordnen.
MARGIN = 2.0

#: Obergrenze der Stücke. Ein Teil, das mehr braucht, ist kein
#: Teilungsproblem, sondern der falsche Drucker — und der Bericht sagt das,
#: statt loszulaufen.
MAX_PARTS = 12

#: Wie weit über und unter einem Kandidaten der Querschnitt gemessen wird, um
#: zu sehen, ob der Körper dort prismatisch ist.
PRISM_STEP = 0.5

#: Gewichte der drei Kriterien. Konturen dominieren mit Absicht: eine Naht,
#: die in mehrere Brücken zerfällt, ist schlimmer als jede Unwucht.
CONTOUR_WEIGHT = 1.0
PRISM_WEIGHT = 0.6
BALANCE_WEIGHT = 0.25

#: Über dieser Punktzahl sind die abgetasteten Ebenen alle mittelmäßig, und
#: die konvexe Zerlegung wird um eine zweite Meinung gebeten.
HINT_THRESHOLD = 0.3

#: Wie viel der nutzbaren Länge der erste Schnitt von einem Körper nimmt, der
#: mehr als doppelt zu lang ist. Nicht die volle Länge: die Suche braucht
#: Raum für eine Naht, und ein exakt auf die Grenze geschnittenes Stück lässt
#: sich neben nichts anordnen.
FIRST_SLICE_SHARE = 0.7


@dataclass(frozen=True, slots=True)
class Candidate:
    """Eine mögliche Trennebene, und was für sie spricht."""

    axis: Axis
    position: float
    area: float
    contours: int
    score: float

    @property
    def plane(self) -> SectionPlane:
        return SectionPlane(normal=AXIS_NORMALS[self.axis], position=self.position)


@dataclass(frozen=True, slots=True)
class Step:
    """Ein Schnitt des Plans: welches Stück geteilt wurde, entlang welcher
    Ebene.

    Der Index macht aus einem Suchergebnis einen Stapel: der Aufrufer geht
    die Schritte der Reihe nach und weiß an jedem Punkt, auf welches Objekt
    der nächste Schnitt wirkt — ohne es aus der Geometrie zurückzuleiten.
    """

    part_index: int
    plane: Candidate
    source: MeshData | None = None
    """Das Stück, das dieser Schnitt geteilt hat.

    Mitgegeben, weil erst daran zu sehen ist, ob auf die Schnittfläche
    überhaupt Stifte passen — und danach entscheidet sich, ob ein
    Passungspaar entsteht oder ins Leere zeigt (§14). Eine Referenz, keine
    Kopie; wer sie ändert, ändert das Stück, und das tut hier niemand.

    Gerechnet wird es nicht hier: Die Stiftplanung lebt in ``pins.py``, und
    das Modul importiert dieses hier. Der Aufrufer in ``app/core/split.py``
    hat beide."""


@dataclass(slots=True)
class SplitOutcome:
    """Die Stücke, die Schnitte, die sie gemacht haben, und was darüber zu
    sagen ist."""

    parts: list[MeshData]
    cuts: list[Step] = field(default_factory=list)
    findings: list[Finding] = field(default_factory=list)

    @property
    def divided(self) -> bool:
        return len(self.parts) > 1


def oversize(
    mesh: MeshData,
    profile: Profile,
    margin: float = MARGIN,
    *,
    allowance: Vec3 = (0.0, 0.0, 0.0),
) -> tuple[float, float, float]:
    """Wie weit der Körper über den Bauraum hinaussteht, je Achse, in mm.

    ``allowance`` ist die Zugabe je Achse, um die ein Passstift über die
    Schnittfläche hinaussteht (§25): Der Stift reicht aus der einen Hälfte in die
    andere, also ragt die verstiftete Hälfte weiter als ihr nacktes Netz. Wer
    prüft, ob ein Stück aufs Bett passt, rechnet den Überstand mit — sonst kommt
    ein Teil zurück, das nackt passt und mit Stift über die Kante steht. Ohne
    Zugabe (der Regelfall dieser Funktion) misst sie das blanke Netz wie zuvor.
    """
    limits = [value - 2.0 * margin for value in profile.printer.build_volume]
    size = mesh.bounds.size
    return tuple(  # type: ignore[return-value]
        max(0.0, float(size[index]) + float(allowance[index]) - limits[index]) for index in range(3)
    )


#: Wie viele Kandidatenebenen ein Block der Abtastung umfasst.
#:
#: Acht, weil die Abfrage dazwischen liegt: Ein einziger Aufruf über alle
#: Ebenen ist von außen nicht zu unterbrechen, und genau er ist an einem
#: großen Netz die Minute, die der Nutzer wartet. Kleiner wäre die Antwort
#: nicht schneller, nur der Aufbau öfter bezahlt.
JUDGE_BLOCK: Final = 8


def fits(
    mesh: MeshData,
    profile: Profile,
    margin: float = MARGIN,
    *,
    allowance: Vec3 = (0.0, 0.0, 0.0),
) -> bool:
    """Passt der Körper überhaupt auf die Platte, in der Lage, die er hat?

    ``allowance`` rechnet den Stiftüberstand mit, siehe :func:`oversize`.
    """
    return max(oversize(mesh, profile, margin, allowance=allowance)) <= EPS_GEOM


def split_to_fit(
    mesh: MeshData,
    profile: Profile,
    *,
    max_parts: int = MAX_PARTS,
    samples: int = SAMPLES,
    pins: int | None = None,
    cancelled: CancelToken | None = None,
) -> SplitOutcome:
    """Schneidet, bis jedes Stück passt — oder klar ist, dass Schneiden es
    nicht richten wird.

    In der Breite zuerst: das Stück, das am weitesten übersteht, wird als
    Nächstes geschnitten. Das hält die Stückzahl klein — den schlimmsten
    Übeltäter zuerst zu schneiden ist, was ein Mensch mit einer Säge tut, und
    aus demselben Grund.

    **Der Passstift zählt zur Ausdehnung.** Ein Stift steht über die
    Schnittfläche hinaus (§25); eine Hälfte, die nackt genau aufs Bett passt,
    ragt mit Stift darüber. Jeder Schnitt legt darum eine Zugabe auf beide neuen
    Hälften — den Überstand an dieser Naht —, und die Bettprüfung
    (:func:`oversize`) rechnet sie mit. Wo eine Hälfte damit übersteht, wird
    feiner geteilt. ``pins`` ist die gewünschte Stiftzahl; ohne Stifte
    (``pins=0``) gibt es keine Zugabe und die alte Rechnung bleibt.

    ``cancelled`` wird **zwischen** den Schnitten und innerhalb der Abtastung
    abgefragt (§15.6). Ein halb geschnittener Körper entsteht dabei nicht: Der
    Abbruch wirft, und was schon gefunden war, ist ein Plan und noch keine
    Änderung am Dokument.
    """
    if pins is None:
        from app.core.geom.pins import PIN_COUNT

        pins = PIN_COUNT

    outcome = SplitOutcome(parts=[mesh])
    # Die Stiftzugabe je Stück und Achse, in Lockschritt mit ``outcome.parts``.
    # Der ganze Körper trägt keine (er ist nicht verstiftet), erst ein Schnitt
    # legt eine an.
    reserves: list[Vec3] = [(0.0, 0.0, 0.0)]
    if fits(mesh, profile):
        return outcome

    while len(outcome.parts) < max_parts:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        index = _worst(outcome.parts, profile, reserves)
        if index is None:
            return outcome

        part = outcome.parts[index]
        reserve = reserves[index]
        axis = _axis_to_cut(part, profile, reserve)
        if axis is None:
            return outcome
        # Wie weit der Stift dieser Naht überstünde — an einer Ebene durch die
        # Mitte gemessen, weil dort der Querschnitt für ein prismatisches Stück
        # steht. Die Zahl geht in das Suchfenster (damit der Schnitt Raum für den
        # Stift lässt) und in die Reserve der Kinder.
        allowance = _pin_allowance(part, axis, profile, pins)
        candidate = find_plane(
            part, profile, axis=axis, allowance=allowance, samples=samples, cancelled=cancelled
        )
        if candidate is None:
            outcome.findings.append(
                Finding(
                    code="split.no_plane",
                    severity="warning",
                    message=_("Für dieses Teil war keine brauchbare Trennebene zu finden."),
                    values={
                        "oversize_mm": round(max(oversize(part, profile, allowance=reserve)), 1)
                    },
                )
            )
            return outcome

        first, second = _cut_in_two(part, candidate)
        if first is None or second is None:
            outcome.findings.append(
                Finding(
                    code="split.cut_failed",
                    severity="warning",
                    message=_("Der Schnitt hat kein zweites Teil ergeben."),
                    values={"axis": candidate.axis, "position": round(candidate.position, 2)},
                )
            )
            return outcome

        outcome.parts[index : index + 1] = [first, second]
        # Beide Hälften erben die Zugabe des Elternteils und bekommen die des
        # neuen Schnitts auf der Schnittachse dazu. Auf **beide**, weil erst der
        # nächste Schnitt entscheidet, welche die knappe wird — der sichere
        # Fehler ist, einer zu viel Reserve zu geben, nicht einer zu wenig.
        child = _add_on_axis(reserve, axis, allowance)
        reserves[index : index + 1] = [child, child]
        outcome.cuts.append(Step(part_index=index, plane=candidate, source=part))
        _log.info("split along %s at %.2f mm", candidate.axis, candidate.position)

    if _worst(outcome.parts, profile, reserves) is not None:
        outcome.findings.append(
            Finding(
                code="split.too_many_parts",
                severity="warning",
                message=_("Auch nach dem letzten Schnitt passt nicht jedes Teil auf das Bett."),
                values={"parts": len(outcome.parts), "limit": max_parts},
            )
        )
    return outcome


def _worst(parts: list[MeshData], profile: Profile, reserves: list[Vec3]) -> int | None:
    """Welches Stück am weitesten übersteht — oder ``None``, wenn alle passen.

    Gemessen mit der Stiftzugabe je Stück (:func:`oversize`): Ein Teil, das
    nackt aufs Bett passt, aber mit Stift übersteht, ist noch nicht fertig.
    """
    overshoot = [
        max(oversize(part, profile, allowance=reserve))
        for part, reserve in zip(parts, reserves, strict=True)
    ]
    largest = max(overshoot, default=0.0)
    if largest <= EPS_GEOM:
        return None
    return overshoot.index(largest)


def _add_on_axis(reserve: Vec3, axis: Axis, extra: float) -> Vec3:
    """Die Zugabe je Achse, um ``extra`` auf ``axis`` erhöht."""
    values = list(reserve)
    values["xyz".index(axis)] += extra
    return (values[0], values[1], values[2])


def _pin_allowance(mesh: MeshData, axis: Axis, profile: Profile, pins: int) -> float:
    """Wie weit ein Passstift über die Schnittfläche dieser Achse stünde, in mm.

    Der Überstand ist die halbe Stiftlänge (``plan.length / 2``) — der Teil, der
    aus der einen Hälfte in die andere reicht (§25). Gemessen an einer Ebene
    durch die Mitte des Stücks: Dort steht der Querschnitt für ein prismatisches
    Teil, und ein prismatisches ist genau das, was Auto Split zu schneiden sucht.

    Null, wenn keine Stifte gewünscht sind oder die Naht keinen trägt — dann
    steht nichts über, und die Bettprüfung bleibt, wie sie ohne Verstiftung war.
    """
    if pins <= 0:
        return 0.0
    from app.core.geom.pins import plan_pins  # spät: pins importiert dieses Modul

    centre = float(mesh.bounds.centre["xyz".index(axis)])
    plane = SectionPlane(normal=AXIS_NORMALS[axis], position=centre)
    return plan_pins(mesh, plane, count=pins).length / 2.0


def find_plane(
    mesh: MeshData,
    profile: Profile,
    *,
    axis: Axis | None = None,
    allowance: float = 0.0,
    samples: int = SAMPLES,
    cancelled: CancelToken | None = None,
) -> Candidate | None:
    """Die beste Trennebene für diesen Körper, oder ``None``, wenn keine hilft.

    Nur Ebenen zählen, die das Stück wirklich passender machen. Eine schöne
    Naht, die beide Hälften zu groß lässt, ist keine Antwort.

    ``axis`` und ``allowance`` gibt die Suche vor, wenn sie den Stiftüberstand
    schon kennt (:func:`split_to_fit`): Die Achse ist dann mit der Reserve des
    Stücks gewählt, und ``allowance`` engt das Fenster so ein, dass die Hälften
    mitsamt Stift aufs Bett passen. Ohne beides — ein Aufruf von außen —
    entscheidet die Achse die nackte Ausdehnung und das Fenster bleibt weit.
    """
    if axis is None:
        axis = _axis_to_cut(mesh, profile)
    if axis is None:
        return None

    window = _window(mesh, profile, axis, allowance)
    positions = np.linspace(window[0], window[1], samples)
    candidates = [
        entry
        for entry in _judge(mesh, axis, positions, cancelled=cancelled)
        if entry.area > EPS_GEOM
    ]
    best = min(candidates, key=lambda entry: entry.score) if candidates else None
    if best is not None and best.score <= HINT_THRESHOLD:
        return best

    # Nichts Überzeugendes unter den abgetasteten Ebenen: die Zerlegung
    # fragen, wo der Körper von selbst auseinanderfällt, und diese Position
    # nach denselben Regeln beurteilen. Sie ist der zweite teure Schritt, also
    # steht davor die zweite Abfrage.
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    hinted = _from_decomposition(mesh, axis, window)
    if hinted is not None and (best is None or hinted.score < best.score):
        return hinted
    return best


def _axis_to_cut(mesh: MeshData, profile: Profile, reserve: Vec3 = (0.0, 0.0, 0.0)) -> Axis | None:
    """Quer zu der Richtung schneiden, die nicht passt — der längsten, die
    übersteht.

    ``reserve`` ist die Stiftzugabe je Achse: Eine Hälfte kann nackt passen und
    erst mit Stift überstehen, dann ist genau diese Achse die zu schneidende.
    """
    over = oversize(mesh, profile, allowance=reserve)
    if max(over) <= EPS_GEOM:
        return None
    return ("x", "y", "z")[int(np.argmax(over))]


def _window(
    mesh: MeshData, profile: Profile, axis: Axis, allowance: float = 0.0
) -> tuple[float, float]:
    """Der Bereich der Schnittpositionen, die sich zu probieren lohnen.

    Normalerweise ist das, wo *beide* Hälften kurz genug herauskommen. Ein
    Körper, mehr als doppelt so lang wie die Platte, hat keine solche
    Position — dort nimmt der erste Schnitt ein passendes Stück ab und lässt
    den Rest für die nächste Runde. Auch das tut jemand mit einer Säge
    genauso.

    ``allowance`` verkürzt die nutzbare Länge um den Stiftüberstand: Die Hälften
    müssen mitsamt Stift aufs Bett passen, also darf jede höchstens so lang
    werden wie die Platte weniger dieser Zugabe (§25).
    """
    index = "xyz".index(axis)
    limit = profile.printer.build_volume[index] - 2.0 * MARGIN - allowance
    low = float(mesh.bounds.minimum[index])
    high = float(mesh.bounds.maximum[index])

    earliest = high - limit
    latest = low + limit
    if earliest <= latest:
        # Nie so nah am Ende schneiden, dass ein Span abfällt.
        inset = (high - low) * 0.05
        return (max(earliest, low + inset), min(latest, high - inset))
    return (low + limit * FIRST_SLICE_SHARE, low + limit)


def _sections_in_blocks(
    mesh: MeshData,
    axis: Axis,
    positions: np.ndarray,
    cancelled: CancelToken | None,
) -> list[Any]:
    """Die Querschnitte zu allen Positionen — in Blöcken, damit dazwischen
    jemand aufhören darf.

    Zurück kommt dieselbe Liste wie aus einem einzigen Aufruf: erst alle
    unteren, dann alle mittleren, dann alle oberen Schnitte. Ein Block liefert
    diese drei Gruppen für seinen Ausschnitt, und sie werden gruppenweise
    wieder zusammengelegt — nicht blockweise hintereinander, sonst stünde die
    Bewertung gleich daneben vor der falschen Nachbarschaft.
    """
    if cancelled is None:
        heights = np.concatenate([positions - PRISM_STEP, positions, positions + PRISM_STEP])
        return sections_along(mesh, axis, heights)

    below: list[Any] = []
    middle: list[Any] = []
    above: list[Any] = []
    for start in range(0, len(positions), JUDGE_BLOCK):
        cancelled.raise_if_cancelled()
        chunk = positions[start : start + JUDGE_BLOCK]
        cut = sections_along(
            mesh, axis, np.concatenate([chunk - PRISM_STEP, chunk, chunk + PRISM_STEP])
        )
        size = len(chunk)
        below.extend(cut[:size])
        middle.extend(cut[size : 2 * size])
        above.extend(cut[2 * size :])
    return [*below, *middle, *above]


def _judge(
    mesh: MeshData,
    axis: Axis,
    positions: np.ndarray,
    *,
    cancelled: CancelToken | None = None,
) -> list[Candidate]:
    """Schneidet den Körper an jeder Kandidatenposition und bewertet, was
    herauskommt.

    Die Schnitte laufen in **Blöcken** statt in einem Zug: ein einziger Aufruf
    über alle Höhen ist von außen nicht zu unterbrechen, und genau er ist bei
    einem großen Netz die Minute, die der Nutzer wartet. Zwischen den Blöcken
    liegt die Abfrage; die Bewertung danach ist billig.
    """
    sections = _sections_in_blocks(mesh, axis, positions, cancelled)
    count = len(positions)
    below, middle, above = sections[:count], sections[count : 2 * count], sections[2 * count :]

    index = "xyz".index(axis)
    centre = float(mesh.bounds.centre[index])
    span = float(mesh.bounds.size[index]) or 1.0

    judged: list[Candidate] = []
    for position, under, here, over in zip(positions, below, middle, above, strict=True):
        if here is None or here.is_empty:
            continue
        area = float(here.area)
        contours = len(getattr(here, "geoms", (here,)))
        neighbours = [float(entry.area) for entry in (under, over) if entry is not None]
        change = max((abs(area - other) for other in neighbours), default=0.0) / max(area, EPS_GEOM)
        balance = abs(float(position) - centre) / (span / 2.0)
        judged.append(
            Candidate(
                axis=axis,
                position=float(position),
                area=area,
                contours=contours,
                score=(
                    CONTOUR_WEIGHT * (contours - 1)
                    + PRISM_WEIGHT * change
                    + BALANCE_WEIGHT * balance
                ),
            )
        )
    return judged


def upright(axis: Axis) -> np.ndarray:
    """Die Drehung, die ``axis`` auf +Z legt. Für Z selbst die Identität."""
    return upright_normal(AXIS_NORMALS[axis])


def upright_normal(normal: Vec3) -> np.ndarray:
    """Die Drehung, die ``normal`` auf +Z legt — für jede Richtung, nicht nur
    für die drei Achsen.

    Sie hat eine Eigenschaft, auf der alles Weitere ruht: Für einen Punkt ``p``
    ist die dritte Koordinate des gedrehten Punktes genau ``normal · p``. Denn
    die Drehung ``R`` erfüllt ``R n = ẑ``, also ``ẑ · R p = (Rᵀ ẑ) · p = n · p``.
    Der Abstand einer Ebene vom Ursprung entlang ihrer Normalen ist damit
    dieselbe Zahl wie die Höhe, in der im gedrehten Bezugssystem geschnitten
    wird — **ohne Umrechnung**, und das gilt für eine gezeichnete Trennlinie
    genauso wie für eine Achse.
    """
    direction = np.asarray(normal, dtype=float)
    length = float(np.linalg.norm(direction))
    if length <= EPS_GEOM:
        return np.eye(4)
    direction = direction / length
    if abs(direction[2] - 1.0) <= EPS_GEOM:
        return np.eye(4)
    return np.asarray(
        trimesh.geometry.align_vectors(direction, [0.0, 0.0, 1.0]),
        dtype=float,
    )


def sections_along(mesh: MeshData, axis: Axis, heights: np.ndarray) -> list[Any]:
    """Querschnitte entlang einer der drei Achsen."""
    return sections_across(mesh, AXIS_NORMALS[axis], heights)


def sections_across(mesh: MeshData, normal: Vec3, heights: np.ndarray) -> list[Any]:
    """Querschnitte quer zu einer beliebigen Richtung — sie wird erst
    aufgerichtet.

    Die Schichtanalyse schneidet entlang Z und kann das gut; den Körper zu
    drehen ist billiger als eine zweite Umsetzung, und es hält die zwei
    Antworten vergleichbar. Die Polygone liegen im gedrehten Bezugssystem —
    :func:`upright_normal` gibt die Matrix her, ein Punkt darauf lässt sich
    also dorthin legen, wo er in der Welt hingehört.
    """
    turn = upright_normal(normal)
    body = mesh
    if not np.allclose(turn, np.eye(4)):
        turned = mesh.raw.copy()
        turned.apply_transform(turn)
        body = MeshData.of(turned)

    # Die Schichtanalyse sortiert jedes Dreieck in die Schichten, die es
    # erreicht, und erwartet die Höhen darum geordnet. Die Suche fragt sie in
    # der Reihenfolge an, in der sie ihr einfielen — also wird hier sortiert
    # und danach zurückgestellt.
    order = np.argsort(np.asarray(heights, dtype=float))
    sections = cross_sections(body, np.asarray(heights, dtype=float)[order])
    result: list[Any] = [None] * len(order)
    for target, section in zip(order, sections, strict=True):
        result[int(target)] = section
    return result


def _cut_in_two(mesh: MeshData, candidate: Candidate) -> tuple[MeshData | None, MeshData | None]:
    """Beide Hälften eines Schnitts, jede mit geschlossener Fläche (§25)."""
    from app.core.geom.prepare import split_at_plane

    first, second, _findings = split_at_plane(mesh, candidate.plane)
    return (
        first if first.triangle_count else None,
        second if second.triangle_count else None,
    )


def _from_decomposition(
    mesh: MeshData, axis: Axis, window: tuple[float, float]
) -> Candidate | None:
    """Fragt, wo der Körper von selbst auseinanderfällt, und beurteilt einen
    Schnitt dort.

    Die konvexe Zerlegung ist ein Hinweis, nicht das Ergebnis: ihre Hüllen
    nähern den Körper an, und ein aus Näherungen zusammengeklebtes Teil ist
    ein genähertes Teil. Genommen wird von ihr eine Zahl — die Position, an
    der zwei ihrer Stücke entlang der Schnittachse aneinanderstoßen.
    """
    pieces = convex_parts(mesh)
    if len(pieces) < 2:
        return None

    index = "xyz".index(axis)
    edges = {float(piece.bounds.maximum[index]) for piece in pieces}
    edges |= {float(piece.bounds.minimum[index]) for piece in pieces}
    inside = sorted(value for value in edges if window[0] <= value <= window[1])
    if not inside:
        return None

    judged = _judge(mesh, axis, np.array(inside))
    usable = [entry for entry in judged if entry.area > EPS_GEOM]
    return min(usable, key=lambda entry: entry.score) if usable else None


def convex_parts(mesh: MeshData, *, limit: int = 8) -> list[MeshData]:
    """Konvexe Stücke des Körpers, größte zuerst — leer, wenn V-HACD fehlt.

    Kein Startwert: dieses V-HACD bietet keinen Zufallsregler und liefert für
    denselben Körper dieselben Hüllen — genau das, was §11.3 von ihm will.
    Ohne das Modul ist die Antwort eine leere Liste, und der Aufrufer sagt
    es; es ist eine optionale Abhängigkeit und nie ein Absturz.
    """
    try:
        raw = mesh.raw.convex_decomposition(maxConvexHulls=limit)
    except PROGRAMMING_ERRORS:
        raise
    except Exception as problem:  # das Modul ist optional, und V-HACD ist C++
        _log.info("convex decomposition unavailable: %s", problem)
        return []
    pieces = raw if isinstance(raw, list) else [raw]
    bodies = [MeshData.of(entry) for entry in pieces if len(getattr(entry, "faces", ()))]
    return sorted(bodies, key=lambda entry: -abs(entry.volume))
