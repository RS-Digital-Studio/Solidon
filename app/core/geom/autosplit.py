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

from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any, Final

import numpy as np

from app.core.deferred import trimesh
from app.core.errors import PROGRAMMING_ERRORS
from app.core.geom.mesh import MeshData
from app.core.geom.section import AXIS_NORMALS, Axis, SectionPlane
from app.core.log import get_logger
from app.core.slice.analysis import cross_sections
from app.core.slice.orientation import SUPPORT_TIE, best_face_candidate
from app.core.types import CancelToken, Finding, Profile, ProgressFn, Vec3
from app.core.units import EPS_GEOM, is_close
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

#: Gewichte der Kriterien. Konturen dominieren mit Absicht: eine Naht,
#: die in mehrere Brücken zerfällt, ist schlimmer als jede Unwucht.
CONTOUR_WEIGHT = 1.0
PRISM_WEIGHT = 0.6
BALANCE_WEIGHT = 0.25

#: **Eine Naht gehört nicht an die dünnste Stelle** (§22.3, Festigkeit).
#: Quer zur Schicht ist eine geklebte Fuge ohnehin die schwächste Stelle des
#: Teils; sie zusätzlich in den kleinsten Querschnitt zu legen, addiert zwei
#: Schwächen an einem Ort.
#:
#: Der Term ist nötig, weil die drei darüber eine Einschnürung **belohnen**:
#: Sie hat eine Kontur, sie liegt oft mittig, und ``PRISM_WEIGHT`` misst die
#: erste Ableitung des Querschnitts — die an einem Minimum genau null ist. Eine
#: Kerbe sieht für diese Rechnung aus wie ein prismatischer Abschnitt.
#: Gemessen an einer Hantel mit 201 mm² Halsquerschnitt: Punktzahl 1,2·10⁻⁸,
#: also die beste überhaupt erreichbare.
NOTCH_WEIGHT = 0.9

#: Ab welcher relativen Vertiefung eine Stelle als Einschnürung gilt. Darunter
#: ist es Messrauschen einer prismatischen Strecke — ``oversized.stl`` hat eine
#: Taille, die über ihre Länge gleich bleibt, und die bleibt die richtige Naht.
NOTCH_FLOOR = 0.02

#: Wie viele Schnitte die grobe Profilkurve über die **ganze** Achse nimmt.
#:
#: Das Suchfenster ist eng — bei einem 400 mm langen Körper auf einem 220er
#: Bett sind es ±16 mm um die Mitte, weil weiter außen eine Hälfte nicht mehr
#: passt. Darin sind eine prismatische Taille und eine Mulde **nicht zu
#: unterscheiden**: Beide sind auf dieser Länge flach. Über die volle Achse
#: sind sie es sehr wohl, und darauf beruht der Term.
#:
#: Dreizehn Schnitte kosten gemessen drei Millisekunden — gegen die
#: neunundneunzig der eigentlichen Suche fällt das nicht ins Gewicht (§31).
PROFILE_SAMPLES = 13

#: Wie nah am Minimum eine Stelle liegen muss, um als „auch dort dünn" zu
#: zählen. Eine prismatische Taille hat mehrere solche Stellen, eine Mulde
#: genau eine — daran werden sie unterschieden.
PROFILE_PLATEAU = 0.08

#: Über dieser Punktzahl sind die abgetasteten Ebenen alle mittelmäßig, und
#: die konvexe Zerlegung wird um eine zweite Meinung gebeten.
HINT_THRESHOLD = 0.3

#: Wie viel der nutzbaren Länge der erste Schnitt von einem Körper nimmt, der
#: mehr als doppelt zu lang ist. Nicht die volle Länge: die Suche braucht
#: Raum für eine Naht, und ein exakt auf die Grenze geschnittenes Stück lässt
#: sich neben nichts anordnen.
FIRST_SLICE_SHARE = 0.7

#: Wie viele gute Nahtlagen die teure zweite Stufe wirklich teilt. Die Zahl
#: wird gegen drei und fünf gemessen; sie bleibt fest, damit dieselbe Datei
#: nicht je nach Rechnerlast an einer anderen Stelle getrennt wird (§11.3).
SUPPORT_PLANE_CANDIDATES = 3

#: Wie viele Grundflächen je Teilstück nach der billigen Flächenheuristik
#: tatsächlich durch die interne Schichtanalyse laufen.
SUPPORT_ORIENTATION_CANDIDATES = 3


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
    connector_shape: str = "round"
    """Die aus genau dieser Naht gemessene, konkrete Verbinderform.

    ``auto`` steht hier nie: Der Stapel muss beim erneuten Auswerten dieselbe
    Geometrie bekommen, ohne die damalige Suche noch einmal zu wiederholen.
    """
    connector_glue: bool = False
    """Ob die automatische Wahl auf Rundstifte mit Kleber zurückfiel."""


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
    protect: Sequence[Any] = (),
    cancelled: CancelToken | None = None,
    progress: ProgressFn | None = None,
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

    ``protect`` reicht die geschützten Flächen an **jeden** Schnitt weiter,
    nicht nur an den ersten. Sie sind Punktwolken und keine Dreiecksnummern,
    und das ist der Grund: Jedes Teilstück ist ein neues Netz mit neuer
    Nummerierung — ein Verweis über Indizes zeigte nach dem ersten Schnitt
    ins Leere, und mehrfach geteilt wird gerade das, was besonders groß ist.

    ``cancelled`` wird **zwischen** den Schnitten und innerhalb der Abtastung
    abgefragt (§15.6). Ein halb geschnittener Körper entsteht dabei nicht: Der
    Abbruch wirft, und was schon gefunden war, ist ein Plan und noch keine
    Änderung am Dokument.
    """
    if pins is None:
        from app.core.geom.pins import PIN_COUNT

        pins = PIN_COUNT

    outcome = SplitOutcome(parts=[mesh])

    def finish() -> SplitOutcome:
        """Den vollständig gerechneten Plan samt ehrlichem Ende melden."""
        if progress is not None:
            progress(1.0, "")
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        return outcome

    # Die Stiftzugabe je Stück und Achse, in Lockschritt mit ``outcome.parts``.
    # Der ganze Körper trägt keine (er ist nicht verstiftet), erst ein Schnitt
    # legt eine an.
    reserves: list[Vec3] = [(0.0, 0.0, 0.0)]
    if fits(mesh, profile):
        return finish()

    while len(outcome.parts) < max_parts:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        index = _worst(outcome.parts, profile, reserves)
        if index is None:
            return finish()

        part = outcome.parts[index]
        reserve = reserves[index]
        axis = _axis_to_cut(part, profile, reserve)
        if axis is None:
            # Erreichbar ist das nicht — ``_worst`` gibt nur einen Index heraus,
            # wenn dieses Stück übersteht, und dann findet ``_axis_to_cut``
            # seine Achse. Der Ausgang meldet trotzdem das Ende wie jeder
            # andere: Ein Rückweg, der die Fortschrittsanzeige bei 0,99 stehen
            # ließe, wäre der eine Fall, den niemand nachstellt.
            return finish()
        # Wie weit der Stift dieser Naht überstünde — an einer Ebene durch die
        # Mitte gemessen, weil dort der Querschnitt für ein prismatisches Stück
        # steht. Die Zahl geht in das Suchfenster (damit der Schnitt Raum für den
        # Stift lässt) und in die Reserve der Kinder.
        allowance = _pin_allowance(part, axis, profile, pins, cancelled=cancelled)
        candidate = find_plane(
            part,
            profile,
            axis=axis,
            allowance=allowance,
            samples=samples,
            protect=protect,
            cancelled=cancelled,
            connector_count=pins,
            progress=(
                (
                    lambda fraction, text: progress(
                        min(
                            0.99,
                            (len(outcome.cuts) + fraction) / max(max_parts - 1, 1),
                        ),
                        text,
                    )
                )
                if progress is not None
                else None
            ),
        )
        if cancelled is not None:
            cancelled.raise_if_cancelled()
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
            return finish()

        if cancelled is not None:
            cancelled.raise_if_cancelled()
        first, second, cut_findings = _cut_in_two(part, candidate)
        # Einmal je Ursache und nicht je Schnitt: ``capped`` ist genau die
        # Wasserdichtheit der Eingabe, und die Hälfte eines offenen Körpers ist
        # wieder offen. Vierfach im Prüfbericht stünde viermal derselbe Satz.
        outcome.findings.extend(
            finding for finding in cut_findings if finding.code not in _codes(outcome.findings)
        )
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        if first is None or second is None:
            outcome.findings.append(
                Finding(
                    code="split.cut_failed",
                    severity="warning",
                    message=_("Der Schnitt hat kein zweites Teil ergeben."),
                    values={"axis": candidate.axis, "position": round(candidate.position, 2)},
                )
            )
            return finish()

        connector_shape = "round"
        connector_glue = False
        if pins > 0:
            from app.core.geom.pins import AUTO, plan_pins

            if cancelled is not None:
                cancelled.raise_if_cancelled()
            connector_plan = plan_pins(
                part,
                candidate.plane,
                count=pins,
                shape=AUTO,
            )
            if cancelled is not None:
                cancelled.raise_if_cancelled()
            connector_shape = connector_plan.shape
            connector_glue = bool(
                connector_plan.choice is not None and connector_plan.choice.requires_glue
            )
            # Das Suchfenster rechnet mit einer Schätzung an der Mitte. Für
            # die Kinder gilt die wirkliche Einbindung an der gewählten Naht;
            # insbesondere ein Schnapper braucht mindestens acht Millimeter
            # und darf nicht wie ein kurzer Rundstift bilanziert werden.
            allowance = connector_plan.length / 2.0
            outcome.findings.extend(
                finding
                for finding in connector_plan.findings
                if finding.code == "split.connector_glue"
            )

        outcome.parts[index : index + 1] = [first, second]
        # Beide Hälften erben die Zugabe des Elternteils und bekommen die des
        # neuen Schnitts auf der Schnittachse dazu. Auf **beide**, weil erst der
        # nächste Schnitt entscheidet, welche die knappe wird — der sichere
        # Fehler ist, einer zu viel Reserve zu geben, nicht einer zu wenig.
        child = _add_on_axis(reserve, axis, allowance)
        reserves[index : index + 1] = [child, child]
        outcome.cuts.append(
            Step(
                part_index=index,
                plane=candidate,
                source=part,
                connector_shape=connector_shape,
                connector_glue=connector_glue,
            )
        )
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
    return finish()


def _codes(findings: Sequence[Finding]) -> frozenset[str]:
    """Welche Befundarten schon dastehen."""
    return frozenset(finding.code for finding in findings)


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


def _pin_allowance(
    mesh: MeshData,
    axis: Axis,
    profile: Profile,
    pins: int,
    *,
    cancelled: CancelToken | None = None,
) -> float:
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
    from app.core.geom.pins import AUTO, plan_pins  # spät: pins importiert dieses Modul

    centre = float(mesh.bounds.centre["xyz".index(axis)])
    plane = SectionPlane(normal=AXIS_NORMALS[axis], position=centre)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    plan = plan_pins(mesh, plane, count=pins, shape=AUTO)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    return plan.length / 2.0


def cuts_through(plane: SectionPlane, protect: Sequence[Any]) -> bool:
    """Ob diese Ebene eine geschützte Fläche zerteilt (§22.3, Sichtflächen).

    Gerechnet wird über die **Abstände** der geschützten Punkte zur Ebene und
    nicht über eine Achskoordinate: Eine Naht muss auch dann sauber beurteilt
    werden, wenn sie schräg liegt, und `split_line` legt sie schräg. Liegen
    alle Punkte einer Fläche auf derselben Seite, geht die Ebene an ihr
    vorbei — nur wenn beide Seiten belegt sind, schneidet sie hindurch.

    Ein Punkt **auf** der Ebene zerteilt nichts, deshalb die Toleranz. Sie ist
    `EPS_GEOM` und keine eigene Zahl: Dieselbe Grenze entscheidet in dieser
    Datei schon, ob eine Schnittfläche überhaupt Fläche hat.

    Mehrere Flächen werden einzeln geprüft. Eine Ebene, die **zwischen** zwei
    geschützten Flächen hindurchgeht, ist erlaubt — verboten ist nur, durch
    eine hindurchzugehen.
    """
    normal = np.asarray(plane.normal, dtype=float)
    for patch in protect:
        points = np.asarray(patch, dtype=float)
        if not len(points):
            continue
        away = points @ normal - plane.position
        if away.min() < -EPS_GEOM and away.max() > EPS_GEOM:
            return True
    return False


def find_plane(
    mesh: MeshData,
    profile: Profile,
    *,
    axis: Axis | None = None,
    allowance: float = 0.0,
    samples: int = SAMPLES,
    protect: Sequence[Any] = (),
    cancelled: CancelToken | None = None,
    support_planes: int = SUPPORT_PLANE_CANDIDATES,
    support_orientations: int = SUPPORT_ORIENTATION_CANDIDATES,
    connector_count: int | None = None,
    progress: ProgressFn | None = None,
) -> Candidate | None:
    """Die beste Trennebene für diesen Körper, oder ``None``, wenn keine hilft.

    Nur Ebenen zählen, die das Stück wirklich passender machen. Eine schöne
    Naht, die beide Hälften zu groß lässt, ist keine Antwort.

    ``axis`` und ``allowance`` gibt die Suche vor, wenn sie den Stiftüberstand
    schon kennt (:func:`split_to_fit`): Die Achse ist dann mit der Reserve des
    Stücks gewählt, und ``allowance`` engt das Fenster so ein, dass die Hälften
    mitsamt Stift aufs Bett passen. Ohne beides — ein Aufruf von außen —
    entscheidet die Achse die nackte Ausdehnung und das Fenster bleibt weit.

    ``protect`` sind Punktwolken geschützter Flächen (§22.3). Ebenen, die
    durch eine davon gehen, fallen aus der Auswahl — **auf beiden Wegen**,
    dem abgetasteten und dem aus der konvexen Zerlegung. Bleibt danach
    nichts, gibt es keine Naht: ``None``, wie bei einem Körper, den
    Schneiden nicht rettet. Was der Nutzer daraus zu wählen bekommt,
    entscheidet die Ebene darüber.

    ``connector_count`` ist die Zahl der Verbinder im späteren Schritt. Ohne
    ausdrücklichen Wert gilt T4s Vorgabe; null bewertet absichtlich einen
    Schnitt ohne Verbinder. Die Suche rechnet nie eine erzwungene Form,
    sondern lässt ``plan_pins(..., shape="auto")`` an jeder Naht entscheiden.
    """
    if axis is None:
        axis = _axis_to_cut(mesh, profile)
    if axis is None:
        return None
    if connector_count is None:
        from app.core.geom.pins import PIN_COUNT

        connector_count = PIN_COUNT

    if progress is not None:
        progress(0.0, str(_("Die Trennebenen werden gesucht …")))

    window = _window(mesh, profile, axis, allowance)
    positions = np.linspace(window[0], window[1], samples)
    candidates = [
        entry
        for entry in _judge(mesh, axis, positions, cancelled=cancelled)
        if entry.area > EPS_GEOM and not cuts_through(entry.plane, protect)
    ]
    if progress is not None:
        progress(0.25, str(_("Die Trennebenen werden gesucht …")))
    best = min(candidates, key=_candidate_order) if candidates else None
    if best is not None and best.score <= HINT_THRESHOLD:
        return _best_by_support(
            mesh,
            profile,
            candidates,
            plane_candidates=support_planes,
            orientation_candidates=support_orientations,
            connector_count=connector_count,
            cancelled=cancelled,
            progress=progress,
        )

    # Nichts Überzeugendes unter den abgetasteten Ebenen: die Zerlegung
    # fragen, wo der Körper von selbst auseinanderfällt, und diese Position
    # nach denselben Regeln beurteilen. Sie ist der zweite teure Schritt, also
    # steht davor die zweite Abfrage.
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    hinted = _from_decomposition(mesh, axis, window, cancelled=cancelled)
    if hinted is not None and cuts_through(hinted.plane, protect):
        # Auch die zweite Meinung hält sich an die Sperre. Ohne diese Zeile
        # wäre sie der Weg, auf dem eine verbotene Naht doch gewinnt — und
        # zwar genau dann, wenn die abgetasteten Ebenen alle mittelmäßig
        # sind, also im schwierigen Fall.
        hinted = None
    if hinted is not None:
        candidates.append(hinted)
    if not candidates:
        return None
    return _best_by_support(
        mesh,
        profile,
        candidates,
        plane_candidates=support_planes,
        orientation_candidates=support_orientations,
        connector_count=connector_count,
        cancelled=cancelled,
        progress=progress,
    )


def _candidate_order(candidate: Candidate) -> tuple[float, str, float]:
    """Stabile Reihenfolge der billigen Nahtbewertung."""
    return (candidate.score, candidate.axis, candidate.position)


def _best_by_support(
    mesh: MeshData,
    profile: Profile,
    candidates: Sequence[Candidate],
    *,
    plane_candidates: int,
    orientation_candidates: int,
    cancelled: CancelToken | None,
    connector_count: int = 0,
    progress: ProgressFn | None = None,
) -> Candidate:
    """Unter guten Nähten das echte Stützvolumen der fertigen Hälften wählen.

    Die Nahtbewertung und das Stützvolumen haben verschiedene Einheiten und
    werden deshalb nicht addiert. Die erste Stufe begrenzt das Feld auf gute
    Nähte. Darin gewinnt weniger Stützvolumen; innerhalb derselben
    Fünf-Prozent-Grenze wie bei der Orientierung bleibt die bessere Naht vorn.

    Gewertet wird die Geometrie, die Auto Split anschließend wirklich baut:
    ``plan_pins`` entscheidet die konkrete Verbinderform aus den Nahtdaten,
    ``add_pins`` setzt sie in beide Hälften. So darf ein großer
    Schwalbenschwanz die Rangfolge nicht erst nach der Suche umkehren.
    """
    shortlist = sorted(candidates, key=_candidate_order)[: max(1, plane_candidates)]
    best = shortlist[0]
    best_support = _support_after_cut(
        mesh,
        best,
        profile,
        orientation_candidates=orientation_candidates,
        cancelled=cancelled,
        connector_count=connector_count,
    )
    if progress is not None:
        progress(0.25 + 0.75 / len(shortlist), str(_("Ausrichtung suchen")))
    for index, candidate in enumerate(shortlist[1:], start=2):
        support = _support_after_cut(
            mesh,
            candidate,
            profile,
            orientation_candidates=orientation_candidates,
            cancelled=cancelled,
            connector_count=connector_count,
        )
        if not np.isfinite(best_support) and np.isfinite(support):
            best, best_support = candidate, support
        elif np.isfinite(support):
            reference = max(best_support, support, EPS_GEOM)
            if support < best_support - reference * SUPPORT_TIE:
                best, best_support = candidate, support
        if progress is not None:
            progress(0.25 + 0.75 * index / len(shortlist), str(_("Ausrichtung suchen")))
    return best


def _support_after_cut(
    mesh: MeshData,
    candidate: Candidate,
    profile: Profile,
    *,
    orientation_candidates: int,
    cancelled: CancelToken | None,
    connector_count: int = 0,
) -> float:
    """Internes Stützvolumen der zwei fertigen, unabhängig gestellten Stücke.

    ``connector_count=0`` misst bewusst die nackten Hälften für Diagnose und
    Vergleichstests. Ein positiver Wert plant dagegen mit T4 dieselbe
    automatische Form wie der spätere Auto-Split-Schritt und beurteilt deren
    wirklich hinzugefügte bzw. abgetragene Geometrie.
    """
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    # Die Befunde des Schnitts gehören hier nicht hin: Diese Funktion beurteilt
    # eine Ebene, die vielleicht nie geschnitten wird. Ein Prüfbericht über
    # verworfene Kandidaten wäre länger als der über das Ergebnis.
    first, second, _judging_only = _cut_in_two(mesh, candidate)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    if first is None or second is None:
        return float("inf")

    parts = (first, second)
    if connector_count > 0:
        # Späte Importe halten den gegenseitigen Vertrag von ``pins`` und
        # ``autosplit`` importierbar. Der öffentliche PARTS-Zugriff lädt die
        # mitgelieferten Verbinder auch für einen direkten Kernaufruf.
        from app.core.geom.pins import AUTO, add_pins, plan_pins
        from app.core.knowledge.parts import PARTS

        PARTS.all()
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        plan = plan_pins(mesh, candidate.plane, count=connector_count, shape=AUTO)
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        pair = add_pins(
            first,
            second,
            plan,
            profile,
            quality="draft",
            cancelled=cancelled,
            batch=True,
        )
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        parts = (pair.first, pair.second)

    total = 0.0
    for part in parts:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        orientation = best_face_candidate(
            part,
            count=orientation_candidates,
            profile=profile,
            cancelled=cancelled,
        )
        total += orientation.support_volume
    return total


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


def _notch_depth(
    mesh: MeshData,
    axis: Axis,
    *,
    cancelled: CancelToken | None = None,
) -> Callable[[float], float]:
    """Baut die Auskunft „wie tief ist die Einschnürung hier".

    Zurück kommt eine Funktion über die Position: null, wo der Körper nicht
    eingeschnürt ist, sonst der relative Abstand des Querschnitts zum dicksten
    Teil des Körpers.

    **Warum eine eigene Kurve über die ganze Achse.** Das Suchfenster ist eng
    — bei einem 400 mm langen Körper auf einem 220er Bett ±16 mm —, und darin
    sehen die prismatische Taille und die Mulde gleich aus: beide flach. Erst
    über die volle Länge trennen sie sich, und zwar an einer zählbaren
    Eigenschaft:

        ``oversized.stl``   3200 · **1200, fünfmal** · 3200   — eine Strecke
        eine Mulde          5018 · 3978 · **2839** · 3940 · 5018   — ein Tal

    Liegen mehrere Abtastpunkte gemeinsam am Minimum, ist die dünne Stelle
    prismatisch und damit die **richtige** Naht (§22.3). Liegt genau einer
    dort, ist es eine Kerbe, und dort gehört keine Fuge hin: Quer zur Schicht
    ist sie ohnehin die schwächste Stelle des Teils.

    Warum nicht die Nachbarn aus der Suche selbst: Sie liegen einen Millimeter
    auseinander, und eine Kerbe ist ein Extremum — ihre erste Ableitung ist
    null, auf dieser Länge also nichts zu sehen. Dieselbe Blindheit hat der
    ``PRISM_WEIGHT``-Term, der über ``PRISM_STEP`` misst; genau deshalb bekam
    eine Hantel mit 201 mm² Hals die bestmögliche Punktzahl.
    """
    index = "xyz".index(axis)
    low = float(mesh.bounds.minimum[index]) + PRISM_STEP
    high = float(mesh.bounds.maximum[index]) - PRISM_STEP
    if high <= low:
        return lambda _position: 0.0

    stations = np.linspace(low, high, PROFILE_SAMPLES)
    # Die Kurve will die Querschnitte **auf** den Stationen, nicht die
    # Nachbarschaft darum: ``_sections_in_blocks`` liefert drei Gruppen, und
    # ihr erstes Drittel liegt um ``PRISM_STEP`` tiefer. Dreizehn Schnitte
    # kosten drei Millisekunden, also fragt sie sie in einem Zug.
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    sections = sections_along(mesh, axis, stations)
    areas = [
        float(entry.area) if entry is not None and not entry.is_empty else 0.0 for entry in sections
    ]
    usable = [value for value in areas if value > EPS_GEOM]
    if len(usable) < 3:
        return lambda _position: 0.0

    thickest = max(usable)
    thinnest = min(usable)
    if thickest <= EPS_GEOM or thinnest >= thickest:
        return lambda _position: 0.0

    # Eine Strecke oder ein Tal? Gezählt wird, wie viele Stellen gemeinsam
    # unten liegen. Zwei genügen: Sie spannen bereits eine Strecke auf.
    plateau = sum(1 for value in usable if value <= thinnest * (1.0 + PROFILE_PLATEAU))
    if plateau >= 2:
        return lambda _position: 0.0

    def depth_at(position: float) -> float:
        """Wie weit dieser Ort unter dem dicksten Querschnitt liegt."""
        here = float(np.interp(position, stations, areas))
        if here <= EPS_GEOM:
            return 0.0
        shortfall = (thickest - here) / thickest
        return shortfall if shortfall > NOTCH_FLOOR else 0.0

    return depth_at


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

    # Die Einschnürung wird über die **ganze** Achse gemessen, nicht im
    # Suchfenster: Darin sehen eine prismatische Taille und eine Mulde gleich
    # aus. Dreizehn zusätzliche Schnitte, gemessen drei Millisekunden.
    depth_at = _notch_depth(mesh, axis, cancelled=cancelled)

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
                    + NOTCH_WEIGHT * depth_at(float(position))
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
    if is_close(direction[2], 1.0):
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


def _cut_in_two(
    mesh: MeshData, candidate: Candidate
) -> tuple[MeshData | None, MeshData | None, list[Finding]]:
    """Beide Hälften eines Schnitts, jede mit geschlossener Fläche (§25) — und
    was dabei zu sagen war.

    **Die Befunde reisen mit.** Bis zum 03.09.2026 standen sie hier als
    ``_findings`` und wurden weggeworfen. Der Handschnitt meldet
    ``split.uncapped``, wenn eine Hälfte ungedeckelt bleibt; Auto Split rief
    dieselbe Funktion und schwieg. Der Kunde bekam zwei offene Netze auf dem
    einzigen Weg, auf dem er die Teilung nicht selbst gewählt hat — und ein
    ungedeckeltes Netz ist kein Körper, der Slicer füllt es nach eigenem
    Gutdünken oder gar nicht.

    Wer nur misst, wirft sie ausdrücklich weg (:func:`_support_after_cut`).
    """
    from app.core.geom.prepare import split_at_plane

    first, second, findings = split_at_plane(mesh, candidate.plane)
    return (
        first if first.triangle_count else None,
        second if second.triangle_count else None,
        findings,
    )


def _from_decomposition(
    mesh: MeshData,
    axis: Axis,
    window: tuple[float, float],
    *,
    cancelled: CancelToken | None = None,
) -> Candidate | None:
    """Fragt, wo der Körper von selbst auseinanderfällt, und beurteilt einen
    Schnitt dort.

    Die konvexe Zerlegung ist ein Hinweis, nicht das Ergebnis: ihre Hüllen
    nähern den Körper an, und ein aus Näherungen zusammengeklebtes Teil ist
    ein genähertes Teil. Genommen wird von ihr eine Zahl — die Position, an
    der zwei ihrer Stücke entlang der Schnittachse aneinanderstoßen.
    """
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    pieces = convex_parts(mesh)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    if len(pieces) < 2:
        return None

    index = "xyz".index(axis)
    edges = {float(piece.bounds.maximum[index]) for piece in pieces}
    edges |= {float(piece.bounds.minimum[index]) for piece in pieces}
    inside = sorted(value for value in edges if window[0] <= value <= window[1])
    if not inside:
        return None

    judged = _judge(mesh, axis, np.array(inside), cancelled=cancelled)
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
