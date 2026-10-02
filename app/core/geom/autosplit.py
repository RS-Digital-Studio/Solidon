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

import threading
import weakref
from collections import OrderedDict
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field, replace
from functools import lru_cache
from typing import TYPE_CHECKING, Any, Final, cast

import numpy as np

from app.core import units
from app.core.build_area import placement_offset, printable_area, printable_height
from app.core.deferred import trimesh
from app.core.errors import PROGRAMMING_ERRORS, SPLIT_ALONG_LINE, GeometryError
from app.core.geom import transform
from app.core.geom.mesh import MeshData
from app.core.geom.orient import NoFittingOrientationError
from app.core.geom.section import AXIS_NORMALS, Axis, CutContactError, SectionPlane
from app.core.log import get_logger
from app.core.slice.analysis import cross_sections
from app.core.slice.orientation import SUPPORT_TIE, best_face_candidate, stands
from app.core.types import CancelToken, Finding, PrinterProfile, Profile, ProgressFn, Vec3
from app.core.units import EPS_GEOM, is_close
from app.i18n import _

if TYPE_CHECKING:
    from app.core.geom.pins import PinPlan

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

#: Um welche Winkel der Normalenfächer der schiefen Ebenen gegen die
#: Schnittachse kippt (RM-080, T3) — als Ecken eines 24-Ecks, also 15, 30 und
#: 45 Grad aus ganzen Zahlen (:func:`units.circle_point`) und damit auf jeder
#: Maschine dieselben Richtungen. Gekippt wird zu beiden Nachbarachsen, in
#: beide Richtungen: zwölf Normalen.
TILT_STEPS: Final = (1, 2, 3)

#: Wie viele Lagen je gekippter Richtung abgetastet werden. Weniger als bei den
#: Achsen, weil es zwölf Richtungen sind und der Fächer nur fragt, wo die
#: achsparallelen Ebenen alle mittelmäßig sind.
TILT_SAMPLES: Final = 17

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

#: **Wie viele Nahtlagen ein Schritt der Schnittfolge gegeneinander plant**
#: (RM-080, T7). Braucht ein Stück mehr als einen Schnitt, entscheidet nicht
#: mehr die schönste erste Naht, sondern die ganze Folge dahinter: Je
#: Nahtlage wird der Rest billig zu Ende geteilt und gezählt. Drei verschiedene
#: Lagen aus der Abtastung, dazu die Spiegelebene, die gleichmäßige Teilung
#: und je übergroße Nebenachse ihre beste Lage — die Breite, mit der das
#: Chopper-Verfahren (SIGGRAPH Asia 2012) seine Strahlsuche fährt, liegt bei
#: vier.
PLAN_BRANCHES: Final = 3

#: **Wie viele Probeschnitte die Planung einer ganzen Teilung höchstens macht.**
#: Eine Zahl und keine Zeit: Nach Uhr begrenzt, teilte dieselbe Datei auf
#: einem belasteten Rechner anders als auf einem ruhigen (§11.3). Ist das
#: Budget verbraucht, entscheidet für die übrigen Schritte die Naht selbst,
#: wie vor der Planung. Gemessen an den Körpern in ``tests/test_autosplit.py``
#: und den Korpusmodellen reicht die Hälfte davon; der Rest ist Reserve für
#: Teile, die zwölf Stücke brauchen.
PLAN_BUDGET: Final = 96

#: Wie viele Lagen je Probeschnitt der Planung abgetastet werden. Die Hälfte
#: der Suche: Die Probe soll zählen, wie viele Stücke eine Folge braucht und
#: wie viele Klebestellen sie hat — die genaue Lage jeder späteren Naht
#: entscheidet ihr eigener Schritt, mit voller Abtastung und Stützvolumen.
PLAN_SAMPLES: Final = 17

#: Wie fein die nutzbare Länge an einer Sperrzone des Betts gesucht wird —
#: Halbierungen des Bereichs, 2⁻¹⁶ der Bettlänge sind unter der Anzeigegenauigkeit.
ROOM_STEPS: Final = 16


@dataclass(frozen=True, slots=True)
class Candidate:
    """Eine mögliche Trennebene, und was für sie spricht."""

    axis: Axis
    position: float
    area: float
    contours: int
    score: float
    pins_on_b: bool = False
    """Ob die Hälfte auf der größeren Seite die Stifte trägt (RM-005).

    Gesetzt von :func:`_best_by_support`, wenn diese Zuordnung am fertigen
    Stützvolumen gewinnt; die Nahtbewertung davor kennt sie nicht."""
    normal: Vec3 | None = None
    """Die Richtung einer schiefen Ebene (RM-080, T3) — ``None`` heißt quer zu
    ``axis``. ``axis`` bleibt die Achse, die das Stück zu lang machte und die
    der Schnitt verkürzt."""
    symmetric: bool = False
    """Ob die Ebene die gemessene Spiegelebene des Stücks ist (RM-080, T6,
    :func:`app.core.geom.symmetry.mirror_plane`)."""
    change: float = 0.0
    """Wie stark sich der Querschnitt einen halben Millimeter daneben ändert,
    relativ — der Anteil ``PRISM_WEIGHT`` der Punktzahl, ungewichtet."""
    notch: float = 0.0
    """Wie tief die Lage in einer Einschnürung liegt (T1) — null, wo keine ist."""

    @property
    def gap(self) -> bool:
        """Ob die Ebene zwischen zwei getrennten Stücken durchgeht und nichts schneidet.

        Keine Naht, keine Klebestelle, kein Verbinder: Ein Stück aus zwei
        losen Teilen, das nur zusammen nicht aufs Bett passt, wird an der
        Lücke getrennt (§22.3).
        """
        return self.contours == 0

    @property
    def plane(self) -> SectionPlane:
        return SectionPlane(
            normal=self.normal if self.normal is not None else AXIS_NORMALS[self.axis],
            position=self.position,
        )


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
    pins_on_b: bool = False
    """Ob Hälfte B die Stifte trägt — die Wahl am fertigen Stützvolumen (RM-005)."""


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
    limits = _limits(profile, margin)
    size = mesh.bounds.size
    return tuple(  # type: ignore[return-value]
        max(0.0, float(size[index]) + float(allowance[index]) - limits[index]) for index in range(3)
    )


def _limits(profile: Profile, margin: float = MARGIN) -> Vec3:
    """Die Ausdehnung der echten Druckkontur; der Rand gilt nur in XY."""
    area = printable_area(profile.printer, margin=margin)
    if area.is_empty:
        return (0.0, 0.0, printable_height(profile.printer))
    left, front, right, back = area.bounds
    return (right - left, back - front, printable_height(profile.printer))


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
    if max(oversize(mesh, profile, margin, allowance=allowance)) > EPS_GEOM:
        return False
    probe = mesh
    if any(extra > EPS_GEOM for extra in allowance):
        # Vor dem endgültigen Verbinderbau ist nur seine achsweise Reserve
        # bekannt. Ihr Hüllraum muss mitpassen; er ist keine neue Geometrie im
        # Dokument. Ohne Reserve wird die tatsächliche Projektion geprüft.
        extent = tuple(
            size + extra for size, extra in zip(mesh.bounds.size, allowance, strict=True)
        )
        probe = MeshData.of(trimesh.creation.box(extents=extent))
    return placement_offset(probe, profile.printer, margin=margin) is not None


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
    margin: float = MARGIN,
) -> SplitOutcome:
    """Schneidet, bis jedes Stück passt — oder klar ist, dass Schneiden es
    nicht richten wird.

    Das Stück, das am weitesten übersteht, wird als Nächstes geschnitten.
    **Wo aber ein Schnitt nicht reicht, entscheidet die ganze Folge** (RM-080,
    T7): Bis zum 23.09.2026 nahm jeder Schritt die schönste Naht für sich, und
    ein Bilderrahmen von 500 mm kam in sieben Stücken zurück, wo vier genügen
    — der erste Schnitt ging durch eine Ecke, weil sie eine Klebestelle
    weniger hatte als der Schnitt durch die Mitte, und danach passte nichts
    mehr. :func:`_plan_step` teilt je Nahtlage den Rest billig zu Ende und
    wählt die Lage, deren ganze Folge die wenigsten Stücke, dann die wenigsten
    Klebestellen hat. Stücke, die ein einziger Schnitt aufs Bett bringt,
    bekommen weiter die volle Suche samt Stützvolumen (:func:`search_plane`).

    **Ein spiegelgleiches Teil wird in seiner Symmetrieebene geteilt** (T6),
    wo das die Konturzahl, die Einschnürung und das Stützvolumen nicht
    verschlechtert — und die Stücke beiderseits werden danach gespiegelt
    geschnitten, nicht jedes für sich gesucht: So bleiben sie gleich, bis zum
    letzten Schnitt.

    **Der Passstift zählt zur Ausdehnung.** Ein Stift steht über die
    Schnittfläche hinaus (§25); eine Hälfte, die nackt genau aufs Bett passt,
    ragt mit Stift darüber. Die Zugabe bekommt die Hälfte, **die die Stifte
    trägt** — die andere hat an dieser Naht nur Bohrungen, und die stehen
    nicht über. Bis zum 23.09.2026 bekamen beide sie, und ein Balken, der in
    drei Stücken passt, brauchte vier. ``pins`` ist die gewünschte Stiftzahl;
    ohne Stifte (``pins=0``) gibt es keine Zugabe.

    ``protect`` reicht die geschützten Flächen an **jeden** Schnitt weiter,
    nicht nur an den ersten. Sie sind Punktwolken und keine Dreiecksnummern,
    und das ist der Grund: Jedes Teilstück ist ein neues Netz mit neuer
    Nummerierung — ein Verweis über Indizes zeigte nach dem ersten Schnitt
    ins Leere, und mehrfach geteilt wird gerade das, was besonders groß ist.

    ``cancelled`` wird **zwischen** den Schnitten, zwischen den Probeschnitten
    der Planung und innerhalb der Abtastung abgefragt (§15.6). Ein halb
    geschnittener Körper entsteht dabei nicht: Der Abbruch wirft, und was schon
    gefunden war, ist ein Plan und noch keine Änderung am Dokument.

    ``margin`` ist der Rand, den jedes Stück zum Bettrand lässt. Die Vorgabe
    ist :data:`MARGIN`; die Oberfläche gibt den Abstand mit, mit dem sie die
    Stücke danach anordnet (:func:`app.core.split.bed_margin`) — sonst passt
    ein Stück zum Teilen, und *Auf dem Bett anordnen* schiebt es über den Rand.
    """
    if pins is None:
        from app.core.geom.pins import PIN_COUNT

        pins = PIN_COUNT
    if margin > MARGIN + EPS_GEOM:
        profile = _narrowed(profile, margin - MARGIN)

    # **Die Suche schneidet ohne Filamente** (RM-266). Jeder Probeschnitt gab
    # seinen Hälften die Slots der Oberfläche mit (``section._keeping_slots``,
    # je Dreieck der nächste Ort auf dem alten Netz), und nichts in der Suche
    # liest sie: Nahtlage, Stifte und Stützvolumen hängen allein an der
    # Geometrie, und die Stücke, die der Kunde bekommt, schneidet der Verlauf
    # danach selbst, samt Farben. Am Besteckeinsatz aus dem Korpus (fünf
    # Teile, farbig) kostete das 4,7 von 4,8 s je Probeschnitt — 14 Schnitte,
    # 65 der 69 s der Suche.
    mesh = MeshData(raw=mesh.raw, cavity=mesh.cavity) if mesh.slots else mesh
    outcome = SplitOutcome(parts=[mesh])
    budget = _Budget(PLAN_BUDGET)
    planned = False
    mirrored_any = False

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
    # Eine feste Kennung je Stück, ebenfalls im Lockschritt: Die Stellung in
    # der Liste verschiebt sich mit jedem Schnitt, und die Spiegelpaare (T6)
    # müssen ihr Gegenüber auch drei Schnitte später noch finden.
    keys: list[int] = [0]
    counter = 0
    mirrors: dict[int, tuple[int, SectionPlane]] = {}
    done: dict[int, tuple[Candidate, int, int, Vec3]] = {}
    if fits(mesh, profile):
        return finish()

    while len(outcome.parts) < max_parts:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        index = _worst(outcome.parts, profile, reserves)
        if index is None:
            _conclude(outcome, mesh, profile, planned=planned, mirrored=mirrored_any)
            return finish()

        part = outcome.parts[index]
        reserve = reserves[index]
        key = keys[index]
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
        # Stift lässt) und in die Reserve der Hälfte, die ihn trägt.
        allowance = _pin_allowance(part, axis, pins, cancelled=cancelled)
        step_progress = (
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
        )
        held = reserve["xyz".index(axis)]
        mirrored = _mirrored_step(key, reserve, mirrors, done, protect)
        flipped = False
        if mirrored is not None:
            # Das Gegenüber ist schon geschnitten: derselbe Schnitt, gespiegelt.
            reflected, flipped = mirrored
            search = PlaneSearch(reflected)
        elif _one_cut_enough(part, profile, reserve, axis, allowance):
            search = search_plane(
                part,
                profile,
                axis=axis,
                allowance=allowance,
                reserve=held,
                samples=samples,
                protect=protect,
                cancelled=cancelled,
                connector_count=pins,
                progress=step_progress,
            )
        else:
            planned = True
            search = _plan_step(
                part,
                profile,
                axis=axis,
                allowance=allowance,
                reserve=reserve,
                samples=samples,
                protect=protect,
                room=max_parts - len(outcome.parts) + 1,
                budget=budget,
                cancelled=cancelled,
                progress=step_progress,
            )
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        candidate = search.candidate
        if candidate is None:
            oversize_mm = round(max(oversize(part, profile, allowance=reserve)), 1)
            if search.blocked:
                # **Nicht „keine Ebene", sondern „keine Ebene neben der
                # Sperre".** Ohne diese Unterscheidung bekäme der Kunde den
                # Rat, die Linie selbst zu zeichnen — dabei hat er die Suche
                # gerade selbst eingeschränkt, und der nächste Weg ist, eine
                # Sperre wieder freizugeben (Regel 17: der Ausweg, der
                # tatsächlich hilft, steht vorn).
                outcome.findings.append(
                    Finding(
                        code="split.blocked_by_protection",
                        severity="warning",
                        message=_(
                            "Neben den geschützten Flächen bleibt für dieses Teil keine "
                            "Trennebene übrig."
                        ),
                        values={"oversize_mm": oversize_mm, "blocked_planes": search.blocked},
                    )
                )
                return finish()
            outcome.findings.append(
                Finding(
                    code="split.no_plane",
                    severity="warning",
                    message=_("Für dieses Teil war keine brauchbare Trennebene zu finden."),
                    values={"oversize_mm": oversize_mm},
                )
            )
            return finish()

        if cancelled is not None:
            cancelled.raise_if_cancelled()
        first, second, cut_findings = (
            search.halves if search.halves is not None else _cut_in_two(part, candidate)
        )
        # Einmal je Ursache und nicht je Schnitt: ``capped`` ist genau die
        # Wasserdichtheit der Eingabe, und die Hälfte eines offenen Körpers ist
        # wieder offen. Vierfach im Prüfbericht stünde viermal derselbe Satz.
        outcome.findings.extend(
            finding for finding in cut_findings if finding.code not in _codes(outcome.findings)
        )
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        if first is None or second is None:
            if not any(finding.code == "split.surface_contact" for finding in cut_findings):
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
        if candidate.gap:
            # Eine Lücke ist keine Naht: Es gibt keine Fläche für einen Stift,
            # und die Hälften stehen um nichts über.
            allowance = 0.0
        elif pins > 0:
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
        else:
            allowance = 0.0

        outcome.parts[index : index + 1] = [first, second]
        reserves[index : index + 1] = list(_child_reserves(reserve, candidate, allowance))
        counter += 2
        first_key, second_key = counter - 1, counter
        keys[index : index + 1] = [first_key, second_key]
        done[key] = (candidate, first_key, second_key, reserve)
        _pair_mirrors(
            mirrors, done, key, candidate, (first_key, second_key), mirrored is not None, flipped
        )
        mirrored_any = mirrored_any or candidate.symmetric or mirrored is not None
        outcome.cuts.append(
            Step(
                part_index=index,
                plane=candidate,
                source=part,
                connector_shape=connector_shape,
                connector_glue=connector_glue,
                pins_on_b=candidate.pins_on_b and pins > 0 and not candidate.gap,
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
    else:
        _conclude(outcome, mesh, profile, planned=planned, mirrored=mirrored_any)
    return finish()


def _conclude(
    outcome: SplitOutcome, mesh: MeshData, profile: Profile, *, planned: bool, mirrored: bool
) -> None:
    """Was der Kunde über eine gelungene Teilung wissen soll — zwei Sätze höchstens.

    **Spiegelgleich** (T6): Die Naht liegt in der Symmetrieebene, die Stücke
    beiderseits sind gleich und drucken sich mit denselben Einstellungen — das
    erklärt, warum sie genau dort liegt, und spart ihm die Frage, ob er beide
    Hälften einzeln einrichten muss.

    **Weniger geht nicht** (T7): Nur wenn die Folge geplant war und die Zahl
    der Stücke die untere Schranke erreicht — je Achse die Länge geteilt durch
    das Bett, aufgerundet. Das ist ein Beweis und keine Einschätzung: Kein Stück
    ist länger als das Bett, also braucht jede Achse mindestens so viele. Wo
    die Schranke nicht erreicht ist, wird nichts behauptet.
    """
    if mirrored:
        outcome.findings.append(
            Finding(
                code="split.symmetric",
                severity="info",
                message=_(
                    "In der Symmetrieebene geteilt: Beide Seiten sind gleich und drucken "
                    "sich mit denselben Einstellungen."
                ),
                values={"parts": len(outcome.parts)},
            )
        )
    if planned and len(outcome.parts) <= fewest_parts(mesh, profile):
        outcome.findings.append(
            Finding(
                code="split.fewest_parts",
                severity="info",
                message=_("Weniger Teile gehen auf diesem Drucker nicht."),
                values={"parts": len(outcome.parts)},
            )
        )


def fewest_parts(mesh: MeshData, profile: Profile) -> int:
    """Die untere Schranke der Stückzahl: je Achse Länge durch Bett, aufgerundet.

    Auto Split dreht kein Stück (§25) — jedes ist also entlang jeder Achse
    höchstens so lang wie das Bett, und die Achse, die am meisten Stücke
    verlangt, verlangt sie von der ganzen Teilung. Stifte machen die Stücke
    länger, nie kürzer; die Schranke gilt mit ihnen erst recht.
    """
    limits = _limits(profile)
    size = mesh.bounds.size
    return max(
        1,
        *(
            int(np.ceil(float(size[index]) / limits[index] - EPS_GEOM)) if limits[index] > 0 else 1
            for index in range(3)
        ),
    )


def _narrowed(profile: Profile, extra: float) -> Profile:
    """Dasselbe Profil mit einem um ``extra`` schmaleren Bett.

    Die freigegebene Fläche wird um den Rand verkleinert und als ausdrückliche
    Kontur eingesetzt, Sperrzonen darin als Löcher; alles in dieser Datei, das
    nach Bett und Rand fragt, rechnet damit ohne eigenen Parameter weiter. Die
    Höhe bleibt: Ein Rand liegt auf dem Bett, nicht darüber.
    """
    from shapely.geometry import Polygon

    area = printable_area(profile.printer, margin=extra)
    if area.is_empty or not isinstance(area, Polygon):
        return profile
    contour = tuple((float(x), float(y)) for x, y in area.exterior.coords[:-1])
    holes = tuple(
        tuple((float(x), float(y)) for x, y in ring.coords[:-1]) for ring in area.interiors
    )
    printer = replace(
        profile.printer,
        printable_area=contour,
        bed_exclusions=holes,
        printable_height=printable_height(profile.printer),
    )
    return replace(profile, printer=printer)


def _codes(findings: Sequence[Finding]) -> frozenset[str]:
    """Welche Befundarten schon dastehen."""
    return frozenset(finding.code for finding in findings)


def _worst(parts: list[MeshData], profile: Profile, reserves: list[Vec3]) -> int | None:
    """Welches Stück am weitesten übersteht — oder ``None``, wenn alle passen.

    Gemessen mit der Stiftzugabe je Stück (:func:`oversize`): Ein Teil, das
    nackt aufs Bett passt, aber mit Stift übersteht, ist noch nicht fertig.
    """
    unfitted = [
        index
        for index, (part, reserve) in enumerate(zip(parts, reserves, strict=True))
        if not fits(part, profile, allowance=reserve)
    ]
    if not unfitted:
        return None
    return max(
        unfitted, key=lambda index: max(oversize(parts[index], profile, allowance=reserves[index]))
    )


def _add_on_axis(reserve: Vec3, axis: Axis, extra: float) -> Vec3:
    """Die Zugabe je Achse, um ``extra`` auf ``axis`` erhöht."""
    values = list(reserve)
    values["xyz".index(axis)] += extra
    return (values[0], values[1], values[2])


def _add_along(reserve: Vec3, candidate: Candidate, extra: float) -> Vec3:
    """Die Zugabe je Achse nach diesem Schnitt — bei einer schiefen Ebene anteilig.

    Ein Stift steht entlang der Normalen über die Naht; auf jede Achse fällt
    davon der Betrag ihrer Komponente. Quer zu einer Achse ist das die alte
    Rechnung.
    """
    if candidate.normal is None:
        return _add_on_axis(reserve, candidate.axis, extra)
    return (
        reserve[0] + abs(candidate.normal[0]) * extra,
        reserve[1] + abs(candidate.normal[1]) * extra,
        reserve[2] + abs(candidate.normal[2]) * extra,
    )


def _child_reserves(reserve: Vec3, candidate: Candidate, extra: float) -> tuple[Vec3, Vec3]:
    """Die Zugabe beider Hälften: der Überstand ``extra`` nur an der, die die Stifte trägt.

    Die andere hat an dieser Naht Bohrungen, und eine Bohrung steht nicht
    über. Was das Elternstück schon trug, erben beide — an welcher seiner
    Flächen es sitzt, weiß hier niemand, und zu viel Reserve ist der sichere
    Fehler. Hälfte A trägt die Stifte, es sei denn, die Suche hat sie ans
    fertige Stützvolumen nach B gelegt (``pins_on_b``, RM-005).
    """
    pinned = _add_along(reserve, candidate, extra)
    return (reserve, pinned) if candidate.pins_on_b else (pinned, reserve)


def _reflected(candidate: Candidate, mirror: SectionPlane) -> tuple[Candidate, bool]:
    """Derselbe Schnitt, an der Spiegelebene ``mirror`` gespiegelt (T6).

    Aus ``n · x = q`` wird ``n' · x = q - 2 p (n · e)`` mit ``n' = n - 2 (n · e) e``
    für die Spiegelebene ``e · x = p``. Zeigt ``n'`` entlang der Schnittachse
    ins Negative, wird die Ebene umgedreht — dieselbe Ebene, die Hälften
    tauschen die Namen, und ``True`` sagt das. Die Stifte wandern mit: Das
    gespiegelte Stück trägt sie an der gespiegelten Stelle.
    """
    normal = np.asarray(candidate.plane.normal, dtype=float)
    across = np.asarray(mirror.normal, dtype=float)
    dot = float(normal @ across)
    turned = normal - 2.0 * dot * across
    position = candidate.position - 2.0 * mirror.position * dot
    flipped = bool(turned["xyz".index(candidate.axis)] < 0.0)
    if flipped:
        turned = -turned
        position = -position
    return (
        replace(
            candidate,
            position=float(position),
            normal=(
                None
                if candidate.normal is None
                else (float(turned[0]), float(turned[1]), float(turned[2]))
            ),
            symmetric=False,
            pins_on_b=candidate.pins_on_b != flipped,
        ),
        flipped,
    )


def _mirrored_step(
    key: int,
    reserve: Vec3,
    mirrors: dict[int, tuple[int, SectionPlane]],
    done: dict[int, tuple[Candidate, int, int, Vec3]],
    protect: Sequence[Any],
) -> tuple[Candidate, bool] | None:
    """Der gespiegelte Schnitt des Gegenübers, wenn es schon geschnitten ist (T6).

    Zwei Stücke beiderseits einer Symmetrieebene sind Spiegelbilder, also
    passt der gespiegelte Schnitt auf das eine, wenn der ursprüngliche auf das
    andere passte. Gesucht wird nicht noch einmal: Eine eigene Suche fände an
    einem Spiegelbild dieselbe Lage nur bis auf Rundung und Gleichstand — und
    dann wären die Stücke nicht mehr gleich. Eine Sperrfläche gilt trotzdem:
    Sie ist nicht gespiegelt, sondern liegt, wo der Kunde sie gesetzt hat.

    **Gespiegelt wird nur, wo beide Stücke dieselbe Aufgabe haben** — dieselbe
    Stiftzugabe. Die Stifte einer Naht in der Symmetrieebene sitzen an einer
    Hälfte, und die ist damit länger als ihr Spiegelbild. Am Rahmen von 500 mm
    mit Stiften brauchte die stiftlose Hälfte, gespiegelt geschnitten, ein
    Stück mehr als mit eigener Suche: neun statt acht.
    """
    partner = mirrors.get(key)
    if partner is None:
        return None
    other, plane = partner
    cut = done.get(other)
    if cut is None:
        return None
    if any(abs(mine - theirs) > EPS_GEOM for mine, theirs in zip(reserve, cut[3], strict=True)):
        return None
    candidate, flipped = _reflected(cut[0], plane)
    if cuts_through(candidate.plane, protect):
        return None
    return candidate, flipped


def _pair_mirrors(
    mirrors: dict[int, tuple[int, SectionPlane]],
    done: dict[int, tuple[Candidate, int, int, Vec3]],
    key: int,
    candidate: Candidate,
    children: tuple[int, int],
    mirrored: bool,
    flipped: bool,
) -> None:
    """Merkt sich, welche neuen Stücke Spiegelbilder voneinander sind.

    Ein Schnitt in der Symmetrieebene macht seine zwei Hälften zu einem Paar.
    Ein gespiegelter Schnitt macht die Hälften zu Paaren mit denen des
    Gegenübers — über Kreuz, wenn die gespiegelte Ebene umgedreht wurde.
    """
    first, second = children
    if candidate.symmetric:
        mirrors[first] = (second, candidate.plane)
        mirrors[second] = (first, candidate.plane)
        return
    if not mirrored:
        return
    partner = mirrors.get(key)
    cut = done.get(partner[0]) if partner is not None else None
    if partner is None or cut is None:
        return
    plane = partner[1]
    _candidate, other_first, other_second, _reserve = cut
    pairs = (
        ((first, other_second), (second, other_first))
        if flipped
        else ((first, other_first), (second, other_second))
    )
    for one, other in pairs:
        mirrors[one] = (other, plane)
        mirrors[other] = (one, plane)


@dataclass(frozen=True, slots=True)
class _PlanCost:
    """Was eine ganze Schnittfolge kostet (T7) — in der Reihenfolge, in der es zählt.

    Zuerst, ob alles aufs Bett kommt; dann die Stückzahl; dann die
    Klebestellen (je Naht ihre Konturen, eine Lücke kostet keine); zuletzt die
    Summe der Nahtbewertungen. Die Stückzahl steht vor den Klebestellen, weil
    ein weiteres Stück immer auch eine weitere Naht ist.
    """

    failed: int = 0
    parts: int = 0
    joints: int = 0
    score: float = 0.0

    def __add__(self, other: _PlanCost) -> _PlanCost:
        return _PlanCost(
            failed=self.failed + other.failed,
            parts=self.parts + other.parts,
            joints=self.joints + other.joints,
            score=self.score + other.score,
        )


class _Budget:
    """Die Zahl der Probeschnitte, die die Planung noch machen darf (:data:`PLAN_BUDGET`)."""

    __slots__ = ("left",)

    def __init__(self, cuts: int) -> None:
        self.left = cuts

    def take(self) -> bool:
        """Einen Probeschnitt nehmen — ``False``, wenn keiner mehr übrig ist."""
        if self.left <= 0:
            return False
        self.left -= 1
        return True


def _pin_allowance(
    mesh: MeshData,
    axis: Axis,
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


@dataclass(frozen=True, slots=True)
class PlaneSearch:
    """Was die Suche nach einer Trennebene ergeben hat — und was sie verworfen hat."""

    candidate: Candidate | None
    blocked: int = 0
    """Wie viele Ebenen mit Schnittfläche allein an einer gesperrten
    Sichtfläche gescheitert sind (§22.3). Null, wenn nichts gesperrt war oder
    keine Sperre eine Ebene getroffen hat. Die Zahl unterscheidet zwei
    Antworten, die sonst gleich aussehen: „nichts gefunden" und „nichts
    gefunden, weil alles gesperrt war" — die zweite hat einen anderen Ausweg."""
    halves: tuple[MeshData, MeshData, list[Finding]] | None = None
    """Der Schnitt an ``candidate``, wenn die Planung ihn schon gemacht hat (T7)."""


def find_plane(
    mesh: MeshData,
    profile: Profile,
    *,
    axis: Axis | None = None,
    allowance: float = 0.0,
    reserve: float = 0.0,
    samples: int = SAMPLES,
    protect: Sequence[Any] = (),
    cancelled: CancelToken | None = None,
    support_planes: int = SUPPORT_PLANE_CANDIDATES,
    support_orientations: int = SUPPORT_ORIENTATION_CANDIDATES,
    connector_count: int | None = None,
    progress: ProgressFn | None = None,
) -> Candidate | None:
    """Die beste Trennebene für diesen Körper, oder ``None``, wenn keine hilft.

    Referenz- und Testweg, wenn nur die Ebene interessiert. Die produktive
    Auto-Split-Planung nutzt :func:`search_plane` direkt, um zusätzlich
    Sperren und bereits berechnete Hälften zu übernehmen.
    """
    return search_plane(
        mesh,
        profile,
        axis=axis,
        allowance=allowance,
        reserve=reserve,
        samples=samples,
        protect=protect,
        cancelled=cancelled,
        support_planes=support_planes,
        support_orientations=support_orientations,
        connector_count=connector_count,
        progress=progress,
    ).candidate


def search_plane(
    mesh: MeshData,
    profile: Profile,
    *,
    axis: Axis | None = None,
    allowance: float = 0.0,
    reserve: float = 0.0,
    samples: int = SAMPLES,
    protect: Sequence[Any] = (),
    cancelled: CancelToken | None = None,
    support_planes: int = SUPPORT_PLANE_CANDIDATES,
    support_orientations: int = SUPPORT_ORIENTATION_CANDIDATES,
    connector_count: int | None = None,
    progress: ProgressFn | None = None,
) -> PlaneSearch:
    """Die beste Trennebene für diesen Körper — samt der Auskunft, was die
    Sperre gekostet hat.

    Nur Ebenen zählen, die das Stück wirklich passender machen. Eine schöne
    Naht, die beide Hälften zu groß lässt, ist keine Antwort.

    ``axis`` und ``allowance`` gibt die Suche vor, wenn sie den Stiftüberstand
    schon kennt (:func:`split_to_fit`): Die Achse ist dann mit der Reserve des
    Stücks gewählt, und ``allowance`` engt das Fenster so ein, dass die Hälften
    mitsamt Stift aufs Bett passen. ``reserve`` ist, was das Stück entlang der
    Achse schon von früheren Nähten trägt — beide Hälften erben es. Ohne all
    das — ein Aufruf von außen — entscheidet die Achse die nackte Ausdehnung
    und das Fenster bleibt weit.

    ``protect`` sind Punktwolken geschützter Flächen (§22.3). Ebenen, die
    durch eine davon gehen, fallen aus der Auswahl — **auf allen Wegen**,
    dem abgetasteten, dem schiefen, dem aus der konvexen Zerlegung und der
    Spiegelebene. Bleibt danach nichts, gibt es keine Naht: ``None``, wie bei
    einem Körper, den Schneiden nicht rettet. Was der Nutzer daraus zu wählen
    bekommt, entscheidet die Ebene darüber.

    ``connector_count`` ist die Zahl der Verbinder im späteren Schritt. Ohne
    ausdrücklichen Wert gilt T4s Vorgabe; null bewertet absichtlich einen
    Schnitt ohne Verbinder. Die Suche rechnet nie eine erzwungene Form,
    sondern lässt ``plan_pins(..., shape="auto")`` an jeder Naht entscheiden.
    """
    if axis is None:
        axis = _axis_to_cut(mesh, profile)
    if axis is None:
        return PlaneSearch(None)
    if connector_count is None:
        from app.core.geom.pins import PIN_COUNT

        connector_count = PIN_COUNT

    if progress is not None:
        progress(0.0, str(_("Die Trennebenen werden gesucht …")))
    candidates, blocked, _window_used = _candidate_pool(
        mesh,
        profile,
        axis,
        allowance=allowance,
        reserve=reserve,
        samples=samples,
        protect=protect,
        cancelled=cancelled,
        progress=progress,
    )
    if not candidates:
        return PlaneSearch(None, blocked)
    return PlaneSearch(
        _best_by_support(
            mesh,
            profile,
            candidates,
            plane_candidates=support_planes,
            orientation_candidates=support_orientations,
            connector_count=connector_count,
            cancelled=cancelled,
            progress=progress,
        ),
        blocked,
    )


def _candidate_pool(
    mesh: MeshData,
    profile: Profile,
    axis: Axis,
    *,
    allowance: float,
    reserve: float,
    samples: int,
    protect: Sequence[Any],
    cancelled: CancelToken | None,
    progress: ProgressFn | None = None,
) -> tuple[list[Candidate], int, tuple[float, float]]:
    """Alle bewerteten Nahtlagen eines Stücks, bevor das Stützvolumen entscheidet.

    Die abgetasteten Ebenen quer zur Achse, dazu die **Lücken** — Lagen, an
    denen kein Dreieck die Ebene kreuzt, weil das Stück aus losen Teilen
    besteht —, dazu die gemessene **Spiegelebene** (T6). Überzeugt keine davon,
    kommen der Fächer schiefer Richtungen (T3) und die zweite Meinung der
    konvexen Zerlegung dazu. Zurück kommen die Lagen, die Zahl der an einer
    Sperre gescheiterten und das Fenster.

    **Eine Lücke schlägt jede Naht.** Bis zum 23.09.2026 kannte die Suche nur
    Ebenen mit Schnittfläche; ein Stück aus zwei losen Zinken, das nur zusammen
    zu breit war, bekam „keine brauchbare Trennebene" — gemessen am Pflock aus
    dem Korpus auf das Anderthalbfache gebracht, dessen oberes Drittel nach
    dem ersten Schnitt aus zwei Armen bestand.
    """
    window = _window(mesh, profile, axis, allowance, reserve)
    positions = np.linspace(window[0], window[1], samples)
    candidates: list[Candidate] = []
    blocked = 0
    for entry in _judge(mesh, axis, positions, cancelled=cancelled):
        if entry.area <= EPS_GEOM:
            continue
        if cuts_through(entry.plane, protect):
            blocked += 1
            continue
        candidates.append(entry)
    candidates.extend(
        entry for entry in _gaps(mesh, axis, positions) if not cuts_through(entry.plane, protect)
    )
    mirror = _mirror_candidate(mesh, axis, window, protect=protect, cancelled=cancelled)
    if mirror is not None:
        # Die Mitte ist oft schon abgetastet; die Spiegelebene ersetzt sie,
        # statt dieselbe Ebene zweimal ins Stützvolumen zu schicken.
        candidates = [
            entry
            for entry in candidates
            if entry.normal is not None or abs(entry.position - mirror.position) > EPS_GEOM
        ]
        candidates.append(mirror)
    if progress is not None:
        progress(0.25, str(_("Die Trennebenen werden gesucht …")))
    best = min(candidates, key=_candidate_order) if candidates else None
    if best is not None and best.score <= HINT_THRESHOLD:
        return candidates, blocked, window

    # **Schiefe Ebenen** (RM-080, T3): Wo keine achsparallele Ebene
    # überzeugt, fragt die Suche einen Fächer gekippter Richtungen — dieselbe
    # Bewertung, dieselbe Sperre, und nur Lagen, die beide Hälften entlang der
    # Achse aufs Bett bringen. Am Z aus zwei Stäben und einer Strebe schnitt
    # jede achsparallele Ebene zwei oder drei Konturen; quer zur Strebe eine.
    #
    # **Eine schiefe Naht muss etwas besser machen, das zählt**: weniger
    # Konturen als jede achsparallele. Bei gleicher Konturzahl bleibt es
    # achsparallel — eine gerade Schnittfläche legt sich ohne Umweg aufs Bett,
    # und eine um Hundertstel bessere Punktzahl ist keine andere Naht. Gemessen
    # am Schraubendreherhalter auf einem 120er Bett: ohne diese Bedingung
    # gewann eine um 15 Grad gekippte Naht mit 0,398 gegen die achsparallele,
    # beide mit einer Kontur.
    upright_best = min((entry.contours for entry in candidates), default=None)
    for entry in _tilted(mesh, profile, axis, allowance, reserve=reserve, cancelled=cancelled):
        if upright_best is not None and entry.contours >= upright_best:
            continue
        if cuts_through(entry.plane, protect):
            blocked += 1
            continue
        candidates.append(entry)
    if progress is not None:
        progress(0.25, str(_("Die Trennebenen werden gesucht …")))

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
        blocked += 1
    if hinted is not None:
        candidates.append(hinted)
    return candidates, blocked, window


def _gaps(
    mesh: MeshData, axis: Axis, positions: np.ndarray, normal: Vec3 | None = None
) -> list[Candidate]:
    """Die Lagen, an denen die Ebene zwischen losen Teilen hindurchgeht.

    Eine Lage ist eine Lücke, wenn **keine Kante** die Ebene kreuzt und kein
    Eckpunkt auf ihr liegt, und wenn auf beiden Seiten Material ist. Dann
    zerfällt das Stück dort ohne Schnittfläche — keine Naht, kein Stift,
    Konturzahl null. Bewertet wird nur die Mittenlage: Eine Lücke hat keinen
    Querschnitt, dessen Änderung oder Einschnürung zählen könnte.

    Gezählt wird über sortierte Kantenenden statt je Lage über alle Kanten:
    Eine Kante kreuzt ``p``, wenn ihr unteres Ende unter und ihr oberes über
    ``p`` liegt.
    """
    direction = np.asarray(normal if normal is not None else AXIS_NORMALS[axis], dtype=float)
    heights = np.asarray(mesh.raw.vertices, dtype=float) @ direction
    edges = np.asarray(mesh.raw.edges_unique, dtype=np.int64)
    if not len(heights) or not len(edges):
        return []
    ends = heights[edges]
    lower = np.sort(ends.min(axis=1))
    upper = np.sort(ends.max(axis=1))
    corners = np.sort(heights)
    low, high = float(corners[0]), float(corners[-1])
    centre = (low + high) / 2.0
    span = (high - low) or 1.0
    found: list[Candidate] = []
    for raw_position in positions:
        position = float(raw_position)
        if not low + EPS_GEOM < position < high - EPS_GEOM:
            continue
        crossing = int(np.searchsorted(lower, position, side="left")) - int(
            np.searchsorted(upper, position, side="right")
        )
        touching = int(np.searchsorted(corners, position + EPS_GEOM, side="right")) - int(
            np.searchsorted(corners, position - EPS_GEOM, side="left")
        )
        if crossing > 0 or touching > 0:
            continue
        found.append(
            Candidate(
                axis=axis,
                position=position,
                area=0.0,
                contours=0,
                score=BALANCE_WEIGHT * abs(position - centre) / (span / 2.0),
                normal=normal,
            )
        )
    return found


#: Die zuletzt gemessenen Spiegelebenen, je Netz und Achse (T6).
#:
#: Ein Stück wird in einem Schritt zweimal gefragt — von der Kandidatenliste
#: und von den Alternativen der Planung —, und an einem spiegelgleichen Netz
#: mit 95 000 Dreiecken kostet die Messung zwei Sekunden (``kumiko``-Schale aus
#: dem Korpus). Gemerkt wird unter der Adresse des Netzes mit einem schwachen
#: Verweis daneben, der sagt, ob dort noch dasselbe Netz liegt (``hash`` eines
#: trimesh-Netzes rechnet je Aufruf). Wenige Einträge genügen: gefragt wird
#: das Stück, das gerade geschnitten wird.
_MIRRORS: OrderedDict[tuple[int, str], tuple[weakref.ref[Any], Any]] = OrderedDict()
_MIRRORS_LIMIT: Final = 16
_MIRRORS_LOCK = threading.Lock()


def _measured_mirror(mesh: MeshData, axis: Axis, cancelled: CancelToken | None) -> Any:
    """:func:`app.core.geom.symmetry.mirror_plane` quer zur Achse, einmal je Netz gemessen."""
    from app.core.geom.symmetry import mirror_plane

    raw = mesh.raw
    key = (id(raw), axis)
    with _MIRRORS_LOCK:
        known = _MIRRORS.get(key)
        if known is not None and known[0]() is raw:
            return known[1]
    found = mirror_plane(mesh, AXIS_NORMALS[axis], cancelled=cancelled)
    with _MIRRORS_LOCK:
        _MIRRORS[key] = (weakref.ref(raw), found)
        while len(_MIRRORS) > _MIRRORS_LIMIT:
            _MIRRORS.popitem(last=False)
    return found


def _mirror_candidate(
    mesh: MeshData,
    axis: Axis,
    window: tuple[float, float],
    *,
    protect: Sequence[Any],
    cancelled: CancelToken | None,
    inside_window: bool = True,
) -> Candidate | None:
    """Die Spiegelebene quer zur Achse als Nahtlage — wenn es sie gibt (T6).

    Gemessen, nicht angenommen (:func:`app.core.geom.symmetry.mirror_plane`).
    Sie wird bewertet wie jede andere Lage und nur als ``symmetric`` markiert;
    ob sie gewinnt, entscheidet :func:`_best_by_support` nach Konturzahl,
    Einschnürung und Stützvolumen. Eine Spiegelebene durch eine Lücke ist
    ebenfalls eine — zwei gleiche lose Teile nebeneinander.
    """
    found = _measured_mirror(mesh, axis, cancelled)
    if found is None:
        return None
    position = found.position
    if inside_window and not window[0] - EPS_GEOM <= position <= window[1] + EPS_GEOM:
        return None
    at = np.asarray([position])
    judged = [
        entry for entry in _judge(mesh, axis, at, cancelled=cancelled) if entry.area > EPS_GEOM
    ]
    entry = judged[0] if judged else next(iter(_gaps(mesh, axis, at)), None)
    if entry is None or cuts_through(entry.plane, protect):
        return None
    return replace(entry, symmetric=True)


def _plan_step(
    part: MeshData,
    profile: Profile,
    *,
    axis: Axis,
    allowance: float,
    reserve: Vec3,
    samples: int,
    protect: Sequence[Any],
    room: int,
    budget: _Budget,
    cancelled: CancelToken | None,
    progress: ProgressFn | None,
) -> PlaneSearch:
    """Der nächste Schnitt eines Stücks, das mehr als einen braucht — als Teil der Folge (T7).

    Die Nahtsuche allein wählt die schönste erste Naht. Welche Folge danach
    kommt, sieht sie nicht: Am Bilderrahmen von 500 mm schnitt sie durch eine
    Ecke, weil dort eine Kontur weniger lag als in der Mitte, und brauchte
    danach sieben Stücke statt vier. Hier werden mehrere Nahtlagen
    gegeneinander geplant (:func:`_alternatives`): Jede wird geschnitten, der
    Rest mit einer billigen Suche zu Ende geteilt (:func:`_rollout`), und die
    Lage gewinnt, deren ganze Folge am wenigsten kostet (:class:`_PlanCost`).
    Bei gleichen Kosten gewinnt die Spiegelebene (T6), sonst die Naht, die
    die Suche allein genommen hätte.

    Das Stützvolumen fragt dieser Schritt nicht: Solange eine Hälfte nicht aufs
    Bett passt, hat sie keine Lage und keinen Stützbedarf. Es entscheidet den
    letzten Schnitt jedes Stücks, dort wie bisher.

    Begrenzt ist das über :data:`PLAN_BUDGET` Probeschnitte je Teilung, nicht
    über die Uhr (§11.3); ist das Budget verbraucht, gilt die Naht, die die
    Suche allein genommen hätte. ``room`` ist, wie viele Stücke dieses Stück
    noch werden darf, ohne die Obergrenze zu reißen.
    """
    held = reserve["xyz".index(axis)]
    if progress is not None:
        progress(0.0, str(_("Die Schnittfolge wird geplant …")))
    candidates, blocked, window = _candidate_pool(
        part,
        profile,
        axis,
        allowance=allowance,
        reserve=held,
        samples=samples,
        protect=protect,
        cancelled=cancelled,
    )
    alternatives = _alternatives(
        part,
        profile,
        candidates,
        axis=axis,
        window=window,
        allowance=allowance,
        reserve=reserve,
        protect=protect,
        cancelled=cancelled,
    )
    if not alternatives:
        return PlaneSearch(None, blocked)

    best: tuple[tuple[Any, ...], Candidate, tuple[MeshData, MeshData, list[Finding]]] | None = None
    for rank, candidate in enumerate(alternatives):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        if progress is not None:
            progress(rank / len(alternatives), str(_("Die Schnittfolge wird geplant …")))
        if not budget.take():
            break
        first, second, findings = _cut_in_two(part, candidate)
        if first is None or second is None:
            continue
        extra = 0.0 if candidate.gap else allowance
        cost = _PlanCost(joints=candidate.contours, score=candidate.score)
        first_reserve, second_reserve = _child_reserves(reserve, candidate, extra)
        head = _rollout(
            first,
            first_reserve,
            profile,
            allowance=allowance,
            room=room - 1,
            budget=budget,
            protect=protect,
            cancelled=cancelled,
        )
        tail = _rollout(
            second,
            second_reserve,
            profile,
            allowance=allowance,
            room=room - head.parts,
            budget=budget,
            protect=protect,
            cancelled=cancelled,
        )
        cost = cost + head + tail
        if cost.parts > room:
            cost = replace(cost, failed=cost.failed + 1)
        order = (
            cost.failed,
            cost.parts,
            cost.joints,
            0 if candidate.symmetric and candidate.notch <= 0.0 else 1,
            round(cost.score, 9),
            rank,
        )
        if best is None or order < best[0]:
            best = (order, candidate, (first, second, findings))
    if best is None:
        # Kein Probeschnitt mehr übrig, bevor der erste lief: die Naht, die
        # die Suche allein genommen hätte.
        return PlaneSearch(alternatives[0], blocked)
    return PlaneSearch(best[1], blocked, halves=best[2])


def _alternatives(
    part: MeshData,
    profile: Profile,
    candidates: Sequence[Candidate],
    *,
    axis: Axis,
    window: tuple[float, float],
    allowance: float,
    reserve: Vec3,
    protect: Sequence[Any],
    cancelled: CancelToken | None,
) -> list[Candidate]:
    """Die Nahtlagen, die :func:`_plan_step` gegeneinander plant — die erste ist die der Suche.

    * Die besten :data:`PLAN_BRANCHES` Lagen der Abtastung, nach Konturzahl
      und Bewertung, aber **verschieden**: je mindestens ein Drittel des
      Fensters auseinander. Drei Nachbarn einen Millimeter voneinander planten
      dreimal dieselbe Folge.
    * Die **Spiegelebene** (T6), auch außerhalb des Fensters: Ein Teil, doppelt
      so lang wie das Bett, lässt sich in der Mitte teilen und jede Hälfte
      noch einmal — gleiche Stücke, wo die Säge vom Rand her ungleiche macht.
    * Die **gleichmäßige Teilung**: Braucht die Achse ``n`` Stücke, die Lage
      bei einem ``n``-tel. Am Rand beginnend nimmt die Suche das größte
      Stück, das passt, und lässt für den Rest manchmal eins zu wenig Platz.
    * Je **weiterer übergroßer Achse** ihre beste Lage — welche Richtung
      zuerst geschnitten wird, gehört zur Folge.
    """
    ordered = sorted(candidates, key=lambda entry: (entry.contours, _candidate_order(entry)))
    spacing = (window[1] - window[0]) / PLAN_BRANCHES
    chosen: list[Candidate] = []
    for entry in ordered:
        if len(chosen) >= PLAN_BRANCHES:
            break
        if any(_same_place(entry, other, spacing) for other in chosen):
            continue
        chosen.append(entry)

    extras: list[Candidate] = []
    mirror = _mirror_candidate(
        part, axis, window, protect=protect, cancelled=cancelled, inside_window=False
    )
    if mirror is not None:
        extras.append(mirror)
    index = "xyz".index(axis)
    length = float(part.bounds.size[index])
    usable = _room(part, profile, axis) - allowance - reserve[index]
    if usable > EPS_GEOM:
        pieces = int(np.ceil(length / usable - EPS_GEOM))
        if pieces >= 3:
            at = np.asarray([float(part.bounds.minimum[index]) + length / pieces])
            extras.extend(
                entry
                for entry in _judge(part, axis, at, cancelled=cancelled)
                if entry.area > EPS_GEOM and not cuts_through(entry.plane, protect)
            )
    over = oversize(part, profile, allowance=reserve)
    for other_index, other in enumerate(("x", "y", "z")):
        if other == axis or over[other_index] <= EPS_GEOM:
            continue
        side = cast(Axis, other)
        other_window = _window(part, profile, side, allowance, reserve[other_index])
        positions = np.linspace(other_window[0], other_window[1], PLAN_SAMPLES)
        found = [
            entry
            for entry in (
                *_judge(part, side, positions, cancelled=cancelled),
                *_gaps(part, side, positions),
            )
            if (entry.area > EPS_GEOM or entry.gap) and not cuts_through(entry.plane, protect)
        ]
        if found:
            extras.append(min(found, key=lambda entry: (entry.contours, _candidate_order(entry))))

    for entry in extras:
        twin = next(
            (other for other in chosen if _same_place(entry, other, EPS_GEOM)),
            None,
        )
        if twin is None:
            chosen.append(entry)
        elif entry.symmetric and not twin.symmetric:
            chosen[chosen.index(twin)] = entry
    return chosen


def _same_place(first: Candidate, second: Candidate, spacing: float) -> bool:
    """Ob zwei Nahtlagen dieselbe Ebene bis auf ``spacing`` sind."""
    return (
        first.axis == second.axis
        and first.normal == second.normal
        and abs(first.position - second.position) <= spacing
    )


def _rollout(
    piece: MeshData,
    reserve: Vec3,
    profile: Profile,
    *,
    allowance: float,
    room: int,
    budget: _Budget,
    protect: Sequence[Any],
    cancelled: CancelToken | None,
) -> _PlanCost:
    """Teilt ein Stück billig zu Ende und sagt, was die Folge kostet (T7).

    Billig heißt: halbe Abtastung (:data:`PLAN_SAMPLES`), nur achsparallel und
    Lücken, kein Fächer, keine konvexe Zerlegung, kein Stützvolumen — und je
    Stück die Naht mit den wenigsten Konturen, dann der besten Bewertung. Die
    Probe soll zählen, nicht entscheiden; entschieden wird jede spätere Naht in
    ihrem eigenen Schritt. Die Stiftzugabe ist die des planenden Schritts, und
    die Stifte sitzen wie ohne Stützvolumen an Hälfte A.

    Was nicht passt, weil keine Lage, kein Budget oder kein Platz unter der
    Obergrenze übrig ist, zählt als ``failed`` — ein Plan, der nicht aufgeht,
    verliert gegen jeden, der aufgeht.
    """
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    if fits(piece, profile, allowance=reserve):
        return _PlanCost(parts=1)
    axis = _axis_to_cut(piece, profile, reserve)
    if axis is None or room <= 1:
        return _PlanCost(failed=1, parts=1)
    index = "xyz".index(axis)
    window = _window(piece, profile, axis, allowance, reserve[index])
    positions = np.linspace(window[0], window[1], PLAN_SAMPLES)
    found = [
        entry
        for entry in (
            *_judge(piece, axis, positions, cancelled=cancelled),
            *_gaps(piece, axis, positions),
        )
        if (entry.area > EPS_GEOM or entry.gap) and not cuts_through(entry.plane, protect)
    ]
    if not found or not budget.take():
        return _PlanCost(failed=1, parts=1)
    choice = min(found, key=lambda entry: (entry.contours, _candidate_order(entry)))
    first, second, _findings = _cut_in_two(piece, choice)
    if first is None or second is None:
        return _PlanCost(failed=1, parts=1)
    first_reserve, second_reserve = _child_reserves(
        reserve, choice, 0.0 if choice.gap else allowance
    )
    head = _rollout(
        first,
        first_reserve,
        profile,
        allowance=allowance,
        room=room - 1,
        budget=budget,
        protect=protect,
        cancelled=cancelled,
    )
    tail = _rollout(
        second,
        second_reserve,
        profile,
        allowance=allowance,
        room=room - head.parts,
        budget=budget,
        protect=protect,
        cancelled=cancelled,
    )
    return _PlanCost(joints=choice.contours, score=choice.score) + head + tail


def _candidate_order(
    candidate: Candidate,
) -> tuple[float, str, tuple[float, ...], float]:
    """Stabile Reihenfolge der billigen Nahtbewertung — achsparallel vor schief bei Gleichstand."""
    return (
        candidate.score,
        candidate.axis,
        tuple(candidate.normal) if candidate.normal is not None else (),
        candidate.position,
    )


def tilted_normals(axis: Axis) -> tuple[Vec3, ...]:
    """Der Fächer schiefer Richtungen um eine Achse (T3) — zwölf, auf jeder Maschine dieselben.

    Gekippt um 15, 30 und 45 Grad (:data:`TILT_STEPS`) zu jeder der beiden
    Nachbarachsen, in beide Richtungen. Die Komponente entlang ``axis`` ist
    immer positiv: Eine Ebene und ihre Gegenrichtung sind dieselbe Ebene.
    """
    index = "xyz".index(axis)
    others = [other for other in range(3) if other != index]
    found: list[Vec3] = []
    for step in TILT_STEPS:
        along, across = units.circle_point(24, step)
        for other in others:
            for sign in (1.0, -1.0):
                values = [0.0, 0.0, 0.0]
                values[index] = along
                values[other] = sign * across
                found.append((values[0], values[1], values[2]))
    return tuple(found)


def _tilted(
    mesh: MeshData,
    profile: Profile,
    axis: Axis,
    allowance: float,
    *,
    reserve: float = 0.0,
    cancelled: CancelToken | None = None,
) -> list[Candidate]:
    """Die bewerteten Lagen des Normalenfächers, die beide Hälften aufs Bett bringen.

    Je Richtung :data:`TILT_SAMPLES` Lagen über die Ausdehnung des Körpers in
    dieser Richtung (fünf Prozent Rand wie bei den Achsen). Behalten wird nur,
    was entlang ``axis`` beide Hälften samt Stiftzugabe unter die Grenze des
    Betts bringt — dieselbe Frage, die :func:`_window` für eine Achse stellt.
    Die Ausdehnung einer Hälfte kommt aus ihren Ecken und den Punkten, an denen
    Kanten die Ebene kreuzen: genau, ohne zu schneiden.
    """
    index = "xyz".index(axis)
    limit = _limits(profile)[index]
    vertices = np.asarray(mesh.raw.vertices, dtype=float)
    edges = np.asarray(mesh.raw.edges_unique, dtype=np.int64)
    found: list[Candidate] = []
    for normal in tilted_normals(axis):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        direction = np.asarray(normal, dtype=float)
        heights = vertices @ direction
        low, high = float(heights.min()), float(heights.max())
        inset = (high - low) * 0.05
        positions = np.linspace(low + inset, high - inset, TILT_SAMPLES)
        room = limit - allowance * abs(normal[index]) - reserve
        usable = [
            float(position)
            for position in positions
            if all(
                extent <= room + EPS_GEOM
                for extent in _half_extents(vertices, edges, heights, float(position), index)
            )
        ]
        if not usable:
            continue
        found.extend(
            entry
            for entry in _judge(mesh, axis, np.asarray(usable), cancelled=cancelled, normal=normal)
            if entry.area > EPS_GEOM
        )
    return found


def _half_extents(
    vertices: np.ndarray, edges: np.ndarray, heights: np.ndarray, position: float, index: int
) -> tuple[float, float]:
    """Die Ausdehnung beider Hälften entlang einer Achse, ohne zu schneiden.

    Eine Hälfte reicht so weit wie ihre Ecken und die Punkte, an denen Kanten
    die Ebene kreuzen — dort beginnt die Schnittfläche.
    """
    first = heights <= position
    crossing = first[edges[:, 0]] != first[edges[:, 1]]
    ends = edges[crossing]
    share = (position - heights[ends[:, 0]]) / (heights[ends[:, 1]] - heights[ends[:, 0]])
    seam = vertices[ends[:, 0], index] + share * (
        vertices[ends[:, 1], index] - vertices[ends[:, 0], index]
    )
    extents = []
    for side in (first, ~first):
        values = np.concatenate([vertices[side, index], seam])
        extents.append(float(values.max() - values.min()) if len(values) else 0.0)
    return extents[0], extents[1]


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

    **Und welche Hälfte die Stifte trägt, gehört zur selben Frage** (RM-005):
    Die Stifte stehen über die Naht, und die Hälfte mit ihnen kann nicht mehr
    auf der Naht liegen. Gemessen am Balken mit zwei gekreuzten Überhängen:
    Bei x = -2 kosten die Stifte an A 5 112 mm³ Stützen, an B 238 325, weil B
    dann auf ihrem fernen Ende steht; an der gewählten Naht x = 3,25 sind es
    3 620 gegen 4 255 (Centauri Carbon 2, PETG). Beide Zuordnungen
    werden deshalb fertig gebaut und gestellt; B gewinnt nur mit derselben
    Fünf-Prozent-Grenze, mit der eine Naht die andere schlägt — sonst bleibt
    es bei A, wie bisher.
    """
    # **Gut heißt zuerst: so wenige Konturen wie möglich.** Eine Naht durch
    # zwei Brücken ist keine gute Naht, auch wenn ihre Hälften weniger Stützen
    # brauchen — das Stützvolumen entscheidet zwischen gleichwertigen Nähten,
    # es kauft keine zweite Klebestelle. Seit dem Normalenfächer (T3) stehen
    # Nähte verschiedener Konturzahl in derselben Liste: Am Z aus zwei Stäben
    # schlug eine schiefe Naht durch zwei Stäbe die durch die Strebe allein.
    ordered: list[Candidate] = []
    # **Die Spiegelebene steht vorn, wenn sie nichts verschlechtert** (T6).
    # Die Konturzahl hält die Gruppierung: Nur eine Spiegelebene mit
    # so wenigen Konturen wie die beste verwendbare Naht gewinnt. Die Einschnürung hält
    # diese Zeile: Eine Hantel ist spiegelgleich, und ihre Mitte ist genau die
    # dünnste Stelle, die T1 meidet. Das Stützvolumen hält die Schleife
    # darunter — eine andere Naht gewinnt nur mit derselben
    # Fünf-Prozent-Grenze, mit der jede Naht die erste schlägt.
    #
    # **Die Querschnittsänderung zählt an der Spiegelebene nicht**, und das mit
    # Grund: Der Term misst, ob die zwei Schnittflächen verschieden
    # ausfallen. In der Spiegelebene sind sie gleich — dieselbe Fläche von
    # beiden Seiten —, auch wenn ein halber Millimeter daneben eine Rippe
    # oder eine Zierrille beginnt.
    for contours in sorted({candidate.contours for candidate in candidates}):
        good = sorted(
            (candidate for candidate in candidates if candidate.contours == contours),
            key=_candidate_order,
        )
        mirror = next(
            (candidate for candidate in good if candidate.symmetric and candidate.notch <= 0.0),
            None,
        )
        if mirror is not None:
            good = [mirror, *(candidate for candidate in good if candidate is not mirror)]
        ordered.extend(good)

    def judged(candidate: Candidate) -> tuple[Candidate, float]:
        """Die bessere Zuordnung der Stifte an dieser Naht, und ihr Stützvolumen."""
        # Eine Lücke hat keine Fläche für einen Verbinder — gemessen werden
        # die nackten Stücke, wie der Schritt sie dann auch baut.
        count = 0 if candidate.gap else connector_count
        # Einmal je Naht geplant, für beide Stiftseiten.
        plan = _connector_plan(mesh, candidate, count) if count > 0 else None
        on_a = _support_after_cut(
            mesh,
            candidate,
            profile,
            orientation_candidates=orientation_candidates,
            cancelled=cancelled,
            connector_count=count,
            plan=plan,
        )
        # **Ohne Platz für einen Verbinder gibt es keine zweite Zuordnung**
        # (RM-266): ``add_pins`` gibt beide Hälften unverändert zurück, und
        # „Stifte an B" hieße dieselben zwei Hälften in anderer Folge — dieselbe
        # Summe, und B gewinnt nur mit weniger. An der Waschschüssel und am
        # Besteckeinsatz aus dem Korpus (Bambu A1 mini) trug keine Naht einen
        # Verbinder, und jede zweite Beurteilung war dieselbe noch einmal.
        if plan is None or not plan.count:
            return candidate, on_a
        on_b = _support_after_cut(
            mesh,
            candidate,
            profile,
            orientation_candidates=orientation_candidates,
            cancelled=cancelled,
            connector_count=count,
            pins_on_b=True,
            plan=plan,
        )
        if np.isfinite(on_b) and (
            not np.isfinite(on_a) or on_b < on_a - max(on_a, on_b, EPS_GEOM) * SUPPORT_TIE
        ):
            return replace(candidate, pins_on_b=True), on_b
        return candidate, on_a

    best: Candidate | None = None
    best_support = float("inf")
    accepted = 0
    for raw in ordered:
        if best is not None and (
            raw.contours != best.contours or accepted >= max(1, plane_candidates)
        ):
            break
        candidate, support = judged(raw)
        if not np.isfinite(support):
            # Nur eine belegte Berührlinie fällt ganz aus der Nahtauswahl.
            # Sonst behält eine nicht bewertbare Lage ihren bisherigen Rang.
            # Das Nachfragen kostet nur am erfolglosen Kandidaten einen Schnitt;
            # eine gewöhnliche Naht wird nicht doppelt auf Kontakt geprüft.
            _first, _second, findings = _cut_in_two(mesh, candidate)
            if any(finding.code == "split.surface_contact" for finding in findings):
                continue
        accepted += 1
        if best is None or (not np.isfinite(best_support) and np.isfinite(support)):
            best, best_support = candidate, support
        elif np.isfinite(support):
            reference = max(best_support, support, EPS_GEOM)
            if support < best_support - reference * SUPPORT_TIE:
                best, best_support = candidate, support
        if progress is not None:
            progress(
                0.25 + 0.75 * accepted / max(1, plane_candidates), str(_("Ausrichtung suchen"))
            )
    if progress is not None:
        progress(1.0, str(_("Ausrichtung suchen")))
    # Sind alle Lagen Berührlinien, reicht diese erste den konkreten Grund
    # an den abschließenden Schnitt weiter. Ein ungeeignetes Netz wird nie gebaut.
    return best if best is not None else ordered[0]


def _support_after_cut(
    mesh: MeshData,
    candidate: Candidate,
    profile: Profile,
    *,
    orientation_candidates: int,
    cancelled: CancelToken | None,
    connector_count: int = 0,
    pins_on_b: bool = False,
    plan: PinPlan | None = None,
) -> float:
    """Internes Stützvolumen der zwei fertigen, unabhängig gestellten Stücke.

    ``connector_count=0`` misst bewusst die nackten Hälften für Diagnose und
    Vergleichstests. Ein positiver Wert plant dagegen mit T4 dieselbe
    automatische Form wie der spätere Auto-Split-Schritt und beurteilt deren
    wirklich hinzugefügte bzw. abgetragene Geometrie. ``pins_on_b`` setzt
    die Stifte an die zweite Hälfte, wie ``split_pinned`` es dann tut.
    ``plan`` ist diese Planung, wenn der Aufrufer sie schon hat
    (:func:`_connector_plan`) — sie hängt nur an Körper und Ebene.
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
        # Später Import: hält den gegenseitigen Vertrag von ``pins`` und
        # ``autosplit`` importierbar.
        from app.core.geom.pins import add_pins

        if plan is None:
            if cancelled is not None:
                cancelled.raise_if_cancelled()
            plan = _connector_plan(mesh, candidate, connector_count)
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        if pins_on_b:
            first, second = second, first
            plan = replace(plan, normal=(-plan.normal[0], -plan.normal[1], -plan.normal[2]))
        try:
            pair = add_pins(
                first,
                second,
                plan,
                profile,
                quality="draft",
                cancelled=cancelled,
                batch=True,
            )
        except GeometryError:
            # **Eine Naht, an der die Stifte nicht zu bauen sind, kostet
            # unbekannt viel** — wie eine Hälfte ohne Lage darunter. Die
            # Ausnahme brach sonst die ganze Suche ab, und der Kunde las über
            # seiner Teilung einen Satz über „die schnelle Vorschau", dessen
            # Knöpfe an ihr nichts ändern konnten (KUNDE-10, Laptopständer).
            # Die übrigen Nähte werden weiter beurteilt; scheitert der
            # Schritt danach selbst, hält er im Verlauf an und sagt, warum.
            #
            # **Jede Absage der Geometrie, nicht nur die der Rückfallkette**
            # (RM-409): Eine Stiftbohrung durch eine Schale, die sich selbst
            # kreuzt, hält vor dem Kern mit ``GeometryError`` an, der
            # Oberklasse von ``BooleanFailedError`` — am Laptop-Ständer brach
            # damit wieder die ganze Suche ab. Abbruch und ein verlorener
            # Hilfsprozess sind keine ``GeometryError`` und gehen weiter.
            return float("inf")
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        parts = (pair.first, pair.second)

    total = 0.0
    for part in parts:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        try:
            orientation = best_face_candidate(
                part,
                count=orientation_candidates,
                profile=profile,
                cancelled=cancelled,
            )
        except NoFittingOrientationError:
            # Ein zu großes Zwischenstück kann weitere Schnitte brauchen;
            # sein unbekannter Stützbedarf ist niemals null.
            return float("inf")
        if not stands(orientation, profile.smallest_first_layer):
            # **Eine Lage, die nicht steht, ist kein Preis.** ``best_of`` nimmt
            # eine solche nur, wenn keine der vorgewählten Lagen steht, und
            # ihr Stützvolumen ist dann eine Zahl über eine Kante: Am Balken
            # mit gekreuzten Überhängen stand die Hälfte B bei x = -6,5 auf
            # 1,4 mm² und „kostete" 2 988 mm³ — billiger als jede Naht, die
            # die Überhänge trennt (gemessen am 22.09.2026, RM-005). Unbekannt
            # heißt hier wie oben: niemals billig.
            return float("inf")
        total += orientation.support_volume
    return total


def _connector_plan(mesh: MeshData, candidate: Candidate, count: int) -> PinPlan:
    """Die Verbinder, die ``split_pinned`` an dieser Naht setzen würde — dieselbe
    automatische Form wie der spätere Schritt (T4)."""
    # Späte Importe halten den gegenseitigen Vertrag von ``pins`` und
    # ``autosplit`` importierbar. Der öffentliche PARTS-Zugriff lädt die
    # mitgelieferten Verbinder auch für einen direkten Kernaufruf.
    from app.core.geom.pins import AUTO, plan_pins
    from app.core.knowledge.parts import PARTS

    PARTS.all()
    return plan_pins(mesh, candidate.plane, count=count, shape=AUTO)


def _axis_to_cut(mesh: MeshData, profile: Profile, reserve: Vec3 = (0.0, 0.0, 0.0)) -> Axis | None:
    """Quer zu der Richtung schneiden, die nicht passt — der längsten, die
    übersteht.

    ``reserve`` ist die Stiftzugabe je Achse: Eine Hälfte kann nackt passen und
    erst mit Stift überstehen, dann ist genau diese Achse die zu schneidende.
    """
    over = oversize(mesh, profile, allowance=reserve)
    if max(over) <= EPS_GEOM:
        if fits(mesh, profile, allowance=reserve):
            return None
        # Hüllmaße passen, aber die echte Kontur oder eine Sperrzone nicht.
        # Ein XY-Schnitt verkleinert die Projektion; Z zu teilen täte das nicht.
        return "x" if mesh.bounds.size[0] >= mesh.bounds.size[1] else "y"
    return ("x", "y", "z")[int(np.argmax(over))]


def _window(
    mesh: MeshData, profile: Profile, axis: Axis, allowance: float = 0.0, reserve: float = 0.0
) -> tuple[float, float]:
    """Der Bereich der Schnittpositionen, die sich zu probieren lohnen.

    Normalerweise ist das, wo *beide* Hälften kurz genug herauskommen. Ein
    Körper, mehr als doppelt so lang wie die Platte, hat keine solche
    Position — dort nimmt der erste Schnitt ein passendes Stück ab und lässt
    den Rest für die nächste Runde. Auch das tut jemand mit einer Säge
    genauso.

    ``allowance`` verkürzt die nutzbare Länge um den Stiftüberstand: Die Hälften
    müssen mitsamt Stift aufs Bett passen, also darf jede höchstens so lang
    werden wie die Platte weniger dieser Zugabe (§25). ``reserve`` ist, was das
    Stück entlang dieser Achse schon von früheren Nähten trägt; beide Hälften
    erben es, also verkürzt es die Länge genauso.

    **Die Länge ist die, die mit der Breite des Stücks wirklich aufs Bett
    geht** (:func:`_room`), nicht die des Hüllrechtecks: Eine Sperrzone in der
    Ecke — beim Centauri Carbon 2 zehn mal zwanzig Millimeter — nimmt einem
    breiten Stück Länge weg. Mit dem Hüllrechteck gerechnet kamen Hälften von
    245 mm heraus, die dort nicht passen, und jede bekam einen zweiten
    Schnitt nahe am Rand: Splitter von 26 bis 35 mm am Keilschloss aus dem
    Korpus, anderthalbfach.
    """
    index = "xyz".index(axis)
    limit = _room(mesh, profile, axis) - allowance - reserve
    low = float(mesh.bounds.minimum[index])
    high = float(mesh.bounds.maximum[index])

    earliest = high - limit
    latest = low + limit
    if earliest <= latest:
        # Nie so nah am Ende schneiden, dass ein Span abfällt.
        inset = (high - low) * 0.05
        return (max(earliest, low + inset), min(latest, high - inset))
    return (low + limit * FIRST_SLICE_SHARE, low + limit)


def _room(mesh: MeshData, profile: Profile, axis: Axis) -> float:
    """Wie lang ein Stück entlang ``axis`` höchstens sein darf, damit es mit seiner
    Breite aufs Bett passt.

    Ohne Sperrzonen und ohne eigene Kontur ist das die Bettlänge. Sonst wird
    die Länge gesucht, bei der ein Quader mit der Breite des Stücks gerade noch
    eine Lage findet — mit :func:`app.core.build_area.placement_offset`, also
    mit genau der Prüfung, die danach über „passt" entscheidet. Ist das Stück
    selbst quer zu breit, ist über seine spätere Breite nichts bekannt, und es
    gilt die Bettlänge.
    """
    index = "xyz".index(axis)
    limits = _limits(profile)
    if index == 2:
        return limits[2]
    other = 1 - index
    across = float(mesh.bounds.size[other])
    if across > limits[other] + EPS_GEOM:
        return limits[index]
    return _room_across(profile.printer, index, round(across, 6))


@lru_cache(maxsize=256)
def _room_across(printer: PrinterProfile, index: int, across: float) -> float:
    """Die längste Strecke entlang der Achse ``index`` bei dieser Breite — gemerkt je Drucker.

    Halbiert wird :data:`ROOM_STEPS`-mal zwischen null und der Bettlänge; die
    Antwort liegt damit unter der Anzeigegenauigkeit neben der wahren. Ein
    Rechteck ohne Sperrzone antwortet sofort mit der Bettlänge.
    """
    area = printable_area(printer, margin=MARGIN)
    if area.is_empty:
        return 0.0
    left, front, right, back = area.bounds
    full = float((right - left, back - front)[index])
    if area.area >= (right - left) * (back - front) - EPS_GEOM:
        return full

    def lies(length: float) -> bool:
        extent = [0.0, 0.0, 1.0]
        extent[index] = max(length, EPS_GEOM)
        extent[1 - index] = max(across, EPS_GEOM)
        probe = MeshData.of(trimesh.creation.box(extents=extent))
        return placement_offset(probe, printer, margin=MARGIN) is not None

    if lies(full):
        return full
    shortest, longest = 0.0, full
    for _step in range(ROOM_STEPS):
        middle = (shortest + longest) / 2.0
        if lies(middle):
            shortest = middle
        else:
            longest = middle
    return shortest


def _one_cut_enough(
    part: MeshData, profile: Profile, reserve: Vec3, axis: Axis, allowance: float
) -> bool:
    """Ob ein einziger Schnitt quer zu ``axis`` dieses Stück aufs Bett bringen kann.

    Dann entscheidet die Naht selbst, mit voller Abtastung und Stützvolumen
    (:func:`search_plane`). Sonst braucht das Stück eine Folge, und die wird
    geplant (:func:`_plan_step`): wenn es auch quer zur Schnittachse übersteht,
    oder wenn es mehr als doppelt so lang ist wie das, was mit Stift und
    geerbter Reserve aufs Bett geht.
    """
    index = "xyz".index(axis)
    over = oversize(part, profile, allowance=reserve)
    if any(over[other] > EPS_GEOM for other in range(3) if other != index):
        return False
    length = _room(part, profile, axis) - allowance - reserve[index]
    return float(part.bounds.size[index]) <= 2.0 * length + EPS_GEOM


def _sections_in_blocks(
    mesh: MeshData,
    axis: Axis,
    positions: np.ndarray,
    cancelled: CancelToken | None,
    normal: Vec3 | None = None,
) -> list[Any]:
    """Die Querschnitte zu allen Positionen — in Blöcken, damit dazwischen
    jemand aufhören darf.

    Zurück kommt dieselbe Liste wie aus einem einzigen Aufruf: erst alle
    unteren, dann alle mittleren, dann alle oberen Schnitte. Ein Block liefert
    diese drei Gruppen für seinen Ausschnitt, und sie werden gruppenweise
    wieder zusammengelegt — nicht blockweise hintereinander, sonst stünde die
    Bewertung gleich daneben vor der falschen Nachbarschaft.
    """
    direction = normal if normal is not None else AXIS_NORMALS[axis]
    if cancelled is None:
        heights = np.concatenate([positions - PRISM_STEP, positions, positions + PRISM_STEP])
        return sections_across(mesh, direction, heights)

    below: list[Any] = []
    middle: list[Any] = []
    above: list[Any] = []
    for start in range(0, len(positions), JUDGE_BLOCK):
        cancelled.raise_if_cancelled()
        chunk = positions[start : start + JUDGE_BLOCK]
        cut = sections_across(
            mesh, direction, np.concatenate([chunk - PRISM_STEP, chunk, chunk + PRISM_STEP])
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
    normal: Vec3 | None = None,
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
    direction = normal if normal is not None else AXIS_NORMALS[axis]
    heights = np.asarray(mesh.raw.vertices, dtype=float) @ np.asarray(direction, dtype=float)
    low = float(heights.min()) + PRISM_STEP
    high = float(heights.max()) - PRISM_STEP
    if high <= low:
        return lambda _position: 0.0

    stations = np.linspace(low, high, PROFILE_SAMPLES)
    # Die Kurve will die Querschnitte **auf** den Stationen, nicht die
    # Nachbarschaft darum: ``_sections_in_blocks`` liefert drei Gruppen, und
    # ihr erstes Drittel liegt um ``PRISM_STEP`` tiefer. Dreizehn Schnitte
    # kosten drei Millisekunden, also fragt sie sie in einem Zug.
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    sections = sections_across(mesh, direction, stations)
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
    normal: Vec3 | None = None,
) -> list[Candidate]:
    """Schneidet den Körper an jeder Kandidatenposition und bewertet, was
    herauskommt.

    Die Schnitte laufen in **Blöcken** statt in einem Zug: ein einziger Aufruf
    über alle Höhen ist von außen nicht zu unterbrechen, und genau er ist bei
    einem großen Netz die Minute, die der Nutzer wartet. Zwischen den Blöcken
    liegt die Abfrage; die Bewertung danach ist billig.
    """
    sections = _sections_in_blocks(mesh, axis, positions, cancelled, normal)
    count = len(positions)
    below, middle, above = sections[:count], sections[count : 2 * count], sections[2 * count :]

    if normal is None:
        index = "xyz".index(axis)
        centre = float(mesh.bounds.centre[index])
        span = float(mesh.bounds.size[index]) or 1.0
    else:
        heights = np.asarray(mesh.raw.vertices, dtype=float) @ np.asarray(normal, dtype=float)
        centre = float(heights.min() + heights.max()) / 2.0
        span = float(heights.max() - heights.min()) or 1.0

    # Die Einschnürung wird über die **ganze** Achse gemessen, nicht im
    # Suchfenster: Darin sehen eine prismatische Taille und eine Mulde gleich
    # aus. Dreizehn zusätzliche Schnitte, gemessen drei Millisekunden.
    depth_at = _notch_depth(mesh, axis, cancelled=cancelled, normal=normal)

    judged: list[Candidate] = []
    for position, under, here, over in zip(positions, below, middle, above, strict=True):
        if here is None or here.is_empty:
            continue
        area = float(here.area)
        contours = len(getattr(here, "geoms", (here,)))
        neighbours = [float(entry.area) for entry in (under, over) if entry is not None]
        change = max((abs(area - other) for other in neighbours), default=0.0) / max(area, EPS_GEOM)
        balance = abs(float(position) - centre) / (span / 2.0)
        notch = depth_at(float(position))
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
                    + NOTCH_WEIGHT * notch
                ),
                normal=normal,
                change=change,
                notch=notch,
            )
        )
    return judged


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
        transform.rotation_between(direction, [0.0, 0.0, 1.0]),
        dtype=float,
    )


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
        transform.moved(turned, turn)
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

    try:
        first, second, findings = split_at_plane(mesh, candidate.plane)
    except CutContactError as problem:
        # Eine tangierende Ebene taugt weder zur Bewertung noch zum Bauen.
        # Die Suche nimmt den nächsten Kandidaten; bleibt nur dieser übrig,
        # nennt das Ergebnis den Grund und den Weg zur eigenen Trennlinie.
        return (
            None,
            None,
            [
                Finding(
                    code="split.surface_contact",
                    severity="warning",
                    message=problem.detail or problem.title,
                    values=problem.values,
                    suggestions=(SPLIT_ALONG_LINE,),
                )
            ],
        )
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
