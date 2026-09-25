"""Analysekarten (Bauplan §18.4).

Arten, denselben Körper anzusehen: wie dick er ist, wo er überhängt, wo
das Netz kaputt ist, wie er sich krümmt, was die Erkennung aus ihm gemacht
hat, wie weit Facetten vom belegten Träger abweichen, an welchen Passungen
er beteiligt ist, und wo Stützen wachsen werden.

Die Karten werden hier gerechnet, nicht im Viewport. Die Oberfläche braucht
nur die Zahlen, den Bereich und die Einheit — sie malt sie mit der Rampe aus
§19.1 und zeichnet die Legende. Das hält die Karten ohne Fenster testbar, und
es hält ``core`` frei von Qt.

Jede Zahl trägt ``source="internal"`` (§22.5). Eine Stützschätzung aus der
Schichtanalyse ist kein gemessener Wert aus G-Code, und die Legende sagt das.
"""

from __future__ import annotations

import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Final, Literal

import numpy as np
import shapely
from shapely.geometry import Polygon as ShapelyPolygon

from app.core.deferred import trimesh
from app.core.errors import CANCEL, DECIMATE_MESH, UserError
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.knowledge.profiles import analysis_limits
from app.core.knowledge.rules import OVERHANG_LIMIT_DEGREES
from app.core.log import get_logger
from app.core.perceive.features import CURVATURE_LIMIT, pair_radii
from app.core.slice.analysis import cross_sections, slice_body
from app.core.types import (
    CancelToken,
    Feature,
    FeatureId,
    Finding,
    Fit,
    MetricSource,
    ObjectId,
    Profile,
    ProgressFn,
    Scene,
    SceneObject,
    SliceResult,
    SurfacePatch,
    SurfaceSource,
    Vec3,
)
from app.core.units import DEGREE_UNIT, EPS_DISPLAY, EPS_GEOM
from app.i18n import TranslatableText, _, format_decimal

if TYPE_CHECKING:
    from app.core.geom.deviation import SampledDeviation

_log = get_logger(__name__)

MapKind = Literal[
    "wall", "overhang", "defects", "curvature", "deviation", "features", "fits", "support"
]
MapScale = Literal["linear", "asinh"]

#: Darüber wird eine Karte abgelehnt statt minutenlang gerechnet (§31).
#:
#: **Gemessen am 04.09.2026 über fünf Kundendateien, und die alte Zahl von
#: 120 000 schützte vor der falschen Sache.** Sechs der sieben Karten bleiben
#: selbst bei 885 570 Dreiecken weit unter dem Budget von drei Sekunden —
#: Überhang 0,06 s, Passungen 0,05, Merkmale 0,05, Netzfehler 0,47,
#: Wandstärke 1,68, Krümmung 2,02. Abgelehnt wurden damit zehn von neunzehn
#: heruntergeladenen Modellen für Rechnungen, die in zwei Sekunden fertig
#: gewesen wären.
#:
#: Neunhunderttausend und keine rundere Zahl, weil bis 885 570 gemessen ist
#: und darüber nicht: Der nächste Messpunkt (1 223 836) reißt das Budget bei
#: der Wandstärke mit 7,06 s. Wer höher will, misst dazwischen.
MAP_LIMIT_TRIANGLES = 900_000

#: Wie lange eine Stützkarte rechnen darf, bevor sie einen kleineren
#: Arbeitskörper vorschlägt (§2.8, §31).
#:
#: **Keine Dreiecksgrenze:** Gemessen am 07.09.2026 braucht der Besenhalter
#: mit 59 740 Dreiecken 9,88 Sekunden, ein Segel mit 277 460 dagegen 1,84.
#: Über 18 Kundenmodelle und dieselbe Form in drei Unterteilungen trennte keine
#: vorab bekannte Zahl den schnellen vom langsamen Fall (ROADMAP §31). Die
#: Rechnung selbst kennt ihre Arbeit als einzige zuverlässig und beendet sie
#: deshalb am Interaktionsbudget.
#:
#: Drei Sekunden sind eine UX-Entscheidung aus den vorhandenen Verträgen: §2.8
#: verlangt oberhalb zwei Sekunden Fortschritt und Abbruch, §31 gibt der
#: anderen aufwendigen Karte, der Wandstärke, drei Sekunden. Der Lauf bleibt
#: im Hintergrund; danach erhält der Nutzer einen konkreten Ausweg.
SUPPORT_MAP_BUDGET_SECONDS = 3.0

#: Wie weit über der Mindestwandstärke die Skala der Wandstärkenkarte endet.
#: Fünf mal zwei Extrusionsbreiten sind das Zehnfache einer Bahn — darüber
#: lautet die Antwort ohnehin „dick genug", und jede Farbstufe, die dort
#: verbraucht wird, fehlt unten, wo die Entscheidung fällt.
WALL_SCALE_FACTOR = 5.0

#: Flächenkategorien der Defektkarte, in der Reihenfolge ihrer Werte.
#:
#: Übersetzbar, und das war es sechs Texte lang nicht: Die Stufen standen als
#: feste deutsche Zeichenketten hier und liefen an ``tr()`` vorbei bis in die
#: Legende (Regel 20). Aufgelöst wird erst beim Bauen der Karte
#: (:func:`_named`) — beim Import steht die Sprache noch nicht fest.
#:
#: **Dieselben Wörter wie im Prüfbericht** (Durchsicht 24.09.2026): Die Stufen
#: hießen „offene Kante", „verzweigte Kante" und „Durchdringung", die Befunde
#: daneben sprechen von Löchern, überzähligen Flächen und Überschneidungen.
DEFECT_LEVELS: Final = (
    _("in Ordnung"),
    _("Loch"),
    _("überzählige Fläche"),
    # **Die dritte Stufe ist die einzige räumliche** (RM-143). Die zwei
    # darüber stehen in der Kantentabelle; zwei Wände, die einander
    # schneiden, haben lauter saubere Kanten mit je zwei Flächen.
    _("Überschneidung"),
    # **Die vierte stand im Bericht und fehlte hier** (Durchsicht 24.09.2026):
    # „An 12 Kanten zeigen die Außenseiten gegeneinander" trug „Stellen
    # zeigen", und die Karte kannte diese Kanten nicht.
    _("Außenseiten gegeneinander"),
)

#: Flächenkategorien der Passungskarte, ebenso übersetzbar.
FIT_LEVELS: Final = (
    _("unbeteiligt"),
    _("Teil einer Passung"),
    _("Passung prüfen"),
    _("Passung verletzt"),
)


def _named(levels: tuple[TranslatableText, ...]) -> tuple[str, ...]:
    """Die Stufen einer Karte in der eingestellten Sprache.

    Aufgelöst im Kern und nicht in der Legende, weil ``categories`` neben
    Stufennamen auch Provenienz-IDs trägt (``hole_3``) — die Legende bekommt
    Zeichenketten, und was übersetzt gehört, ist hier schon übersetzt.
    Dieselbe Stelle, an der :func:`feature_map` seit je ``str(_("ohne
    Merkmal"))`` schreibt.
    """
    return tuple(str(level) for level in levels)


@dataclass(frozen=True, slots=True)
class AnalysisMap:
    """Eine Karte über die Dreiecke eines Körpers.

    ``values`` hält eine Zahl je Dreieck. ``nan`` heißt „kann ich nicht sagen" —
    ein Strahl, der den Körper verlassen hat, ohne etwas zu treffen, ist keine
    Dicke von null.
    """

    kind: MapKind
    title: TranslatableText | str
    values: tuple[float, ...]
    unit: str
    low: float
    high: float
    highlighted: tuple[int, ...] = ()
    """Dreiecke, auf die die Karte hinweisen will: zu dünn, zu steil, gebrochen."""
    threshold: float | None = None
    """Ab wo hervorgehoben wird, in der Einheit der Karte."""
    categories: tuple[str, ...] = ()
    """Für Karten, deren Werte Stufen sind und keine Messwerte."""
    source: MetricSource = "internal"
    note: TranslatableText | str | None = None
    """Eine Zeile für die Legende, wenn die Zahl einen Vorbehalt braucht (§22.5)."""
    resolution: float | None = None
    """Rasterweite in mm, wo die Karte abgetastet statt genau gemessen wurde."""
    unknown_note: TranslatableText | str | None = None
    """Warum diese Karte an manchen Stellen nichts sagen kann — in drei Worten.

    Die Fußzeile zählte sie („17 mal nicht bestimmbar") und ließ die Zahl
    unerklärt stehen. Für jede Karte heißt es etwas anderes, also sagt es jede
    selbst; kurz genug, damit es in dieselbe Zeile passt."""
    display_scale: MapScale = "linear"
    """Abbildung physischer Werte auf die Farbrampe.

    Die Werte, Grenzen und Schwellen bleiben immer in der Einheit der Karte.
    Nur Renderer und Legende benutzen diese monotone Anzeigeabbildung.
    """

    maximum_interval: tuple[float, float] | None = None
    """Grenzen des größten Abstands ausschließlich innerhalb bekannter Facetten."""
    numerical_error: float | None = None
    """Größte verbliebene Rechenbreite einer bekannten Facette, in mm."""
    witness_point: Vec3 | None = None
    """Angezeigte Koordinaten einer tatsächlich beprobten Stelle im Originaldreieck."""
    witness_face: int | None = None
    witness_distance: float | None = None
    """Nach unten begrenzter Abstand am Zeugen, keine dort erreichte Obergrenze."""

    @property
    def known(self) -> tuple[float, ...]:
        return tuple(value for value in self.values if not math.isnan(value))

    @property
    def unknown_count(self) -> int:
        return sum(1 for value in self.values if math.isnan(value))

    def display_values(self) -> np.ndarray:
        """Werte für die lineare Farbrampe, ohne die Messwerte zu verändern."""
        values = np.asarray(self.values, dtype=float)
        if self.display_scale == "asinh":
            return np.arcsinh(values / EPS_DISPLAY)
        return values

    @property
    def display_limits(self) -> tuple[float, float]:
        """Grenzen in demselben Raum wie :meth:`display_values`."""
        if self.display_scale == "asinh":
            return (
                math.asinh(self.low / EPS_DISPLAY),
                math.asinh(self.high / EPS_DISPLAY),
            )
        return self.low, self.high

    def value_at_display_fraction(self, fraction: float) -> float:
        """Den physischen Wert an einem Anteil der Farbrampe zurückgeben."""
        if self.high <= self.low:
            return self.low
        low, high = self.display_limits
        displayed = low + (high - low) * fraction
        if self.display_scale == "asinh":
            return math.sinh(displayed) * EPS_DISPLAY
        return displayed


class MapTooLarge(UserError):
    """Der Körper hat mehr Dreiecke, als eine Karte abzulaufen bereit ist (§31).

    Ein ``UserError``, keine nackte ``Exception``: als solche fiel die Klasse
    durch die Regel-17-Prüfung in ``tests/test_errors.py`` — kein Vorschlag,
    kein Warum, und die Oberfläche konnte nur „zu groß" sagen. Die Antwort
    steht seit je in der Eingangsstufe: Dezimieren hilft.
    """

    default_title = _("Für eine Analysekarte ist dieses Modell zu groß.")
    default_suggestions = (
        DECIMATE_MESH,
        CANCEL,
    )

    def __init__(self, triangles: int = 0, limit: int = MAP_LIMIT_TRIANGLES) -> None:
        """``limit`` ist die Grenze, die wirklich gegriffen hat.

        Die Grenze gilt den dreieckgebundenen Karten. Die Stützkarte
        beurteilt ihre tatsächliche Laufzeit, weil ihre Kosten vorab nicht an
        der Dreieckszahl erkennbar sind.
        """
        super().__init__(
            detail=_("Die Karte läuft jedes Dreieck ab, und ihr Budget ist begrenzt."),
            values={"triangles": triangles, "limit": limit},
        )
        self.triangles = triangles
        self.limit = limit


class MapBudgetExceeded(UserError):
    """Eine laufende Karte hat ihr abgeleitetes Interaktionsbudget verbraucht."""

    default_title = _("Die Stützkarte braucht für dieses Modell zu lange.")
    default_suggestions = (DECIMATE_MESH, CANCEL)

    def __init__(self, seconds: float = SUPPORT_MAP_BUDGET_SECONDS) -> None:
        super().__init__(
            detail=_(
                "Die Berechnung wurde nach {seconds} Sekunden beendet. "
                "Verringern Sie die Dreiecke und versuchen Sie es erneut.",
                seconds=format_decimal(seconds, digits=1),
            ),
            values={"seconds": seconds},
        )
        self.seconds = seconds


class _MapDeadline:
    """Nutzerabbruch und monotones Kartenbudget als ein Abbruchvertrag."""

    def __init__(
        self,
        cancelled: CancelToken | None,
        seconds: float,
        *,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._cancelled = cancelled
        self._clock = clock
        self._started = clock()
        self._deadline = self._started + seconds

    @property
    def is_cancelled(self) -> bool:
        return bool(
            (self._cancelled is not None and self._cancelled.is_cancelled)
            or self._clock() >= self._deadline
        )

    def raise_if_cancelled(self) -> None:
        """Nutzerabbruch bleibt still, das verbrauchte Budget wird erklärt."""
        if self._cancelled is not None:
            self._cancelled.raise_if_cancelled()
        now = self._clock()
        if now >= self._deadline:
            # Ein nativer Aufruf kann erst an seiner nächsten Grenze
            # zurückkehren. Genannt wird deshalb die echte Wartezeit, nicht
            # die nominelle Schwelle.
            raise MapBudgetExceeded(max(0.0, now - self._started))


TITLES: dict[MapKind, TranslatableText] = {
    "wall": _("Wandstärke"),
    "overhang": _("Überhang"),
    "defects": _("Netzfehler"),
    "curvature": _("Krümmung"),
    "deviation": _("Formabweichung"),
    # „Merkmale" und nicht „Feature-Zuordnung": Die Begriffszuordnung aus
    # Bauplan §4.2 sagt Merkmal → feature, und die Nachbarn heißen
    # Wandstärke, Überhang, Netzfehler, Krümmung, Formabweichung, Passungen, Stützbedarf. Ein
    # halb englischer Name in dieser Reihe war der einzige.
    "features": _("Merkmale"),
    "fits": _("Passungen"),
    "support": _("Stützbedarf"),
}


def build(
    kind: MapKind,
    entry: SceneObject,
    *,
    profile: Profile | None = None,
    scene: Scene | None = None,
    cancelled: CancelToken | None = None,
    progress: ProgressFn | None = None,
) -> AnalysisMap:
    """Der eine Einstiegspunkt, den die Oberfläche benutzt; der Rest ist die
    Karte selbst.

    ``cancelled`` bricht in den begrenzten Arbeitsstücken des Schneiders und
    der Kartenrechnung ab. Die Zusage steht in §18.4 — die Karten laufen im
    Hintergrund und sind abbrechbar. Für die Stützkarte kommt dasselbe Signal
    zusätzlich von ihrem Arbeitsbudget; ein Nutzerabbruch bleibt davon
    unterscheidbar und still.
    """
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    budget = _MapDeadline(cancelled, SUPPORT_MAP_BUDGET_SECONDS) if kind == "support" else None
    mesh = _mesh_of(entry)
    wall, angle = analysis_limits(profile, entry) if profile else (None, OVERHANG_LIMIT_DEGREES)
    if kind != "support" and mesh.triangle_count > MAP_LIMIT_TRIANGLES:
        raise MapTooLarge(mesh.triangle_count, MAP_LIMIT_TRIANGLES)

    if kind == "wall":
        return wall_thickness_map(
            mesh,
            wall,
            default_pitch(mesh, profile.printer.smallest_detail if profile else None),
            cancelled=cancelled,
        )
    if kind == "overhang":
        return overhang_map(mesh, angle)
    if kind == "defects":
        return defect_map(mesh, cancelled)
    if kind == "curvature":
        return curvature_map(mesh, entry.features, cancelled=cancelled)
    if kind == "deviation":
        return deviation_map(mesh, entry, cancelled=cancelled, progress=progress)
    if kind == "features":
        return feature_map(mesh, entry.features)
    if kind == "fits":
        return fit_map(mesh, entry, scene)
    return support_map(
        mesh,
        profile.printer.layer_height if profile else 0.2,
        budget,
        overhang_angle=angle,
        pitch=default_pitch(mesh, profile.printer.smallest_detail if profile else None),
    )


def deviation_map(
    mesh: MeshData,
    entry: SceneObject,
    *,
    cancelled: CancelToken | None = None,
    progress: ProgressFn | None = None,
) -> AnalysisMap:
    """Ganze Originalfacetten gegen belegte Teilträger eingrenzen, ohne neue Einpassung.

    **Ein aus dem Netz umgewandelter Körper wird gegen dieses Netz gemessen**
    (P4.0). Seine Flächen sind die eingepassten Träger selbst; sie gegen sich
    zu prüfen zeigte nur die Feinheit seiner Darstellung. Die Frage des Kunden
    ist, wie weit das Ergebnis von dem abliegt, was er hineingegeben hat — und
    wo.
    """
    from app.core.geom.deviation import (
        DeviationTable,
        HasSourceDeviation,
        deviation_bounds_grouped,
    )
    from app.core.perceive.surfaces import PATCH_BLOCK, valid_patch

    def check() -> None:
        if cancelled is not None:
            cancelled.raise_if_cancelled()

    def report(fraction: float) -> None:
        check()
        if progress is not None:
            progress(fraction, str(_("Formabweichung eingrenzen …")))
        check()

    report(0.0)
    if isinstance(entry.mesh, HasSourceDeviation):
        measured = entry.mesh.source_deviation(cancelled=cancelled, progress=report)
        if measured is not None and len(measured.values_mm) == mesh.triangle_count:
            return _source_map(measured)
    owners = np.full(mesh.triangle_count, -1, dtype=np.int32)
    origin_masks = np.zeros(mesh.triangle_count, dtype=np.uint8)
    source_flags: dict[SurfaceSource, int] = {"native": 1, "facets": 2, "fit": 4}
    carriers: list[SurfacePatch] = []
    claims: list[list[tuple[int, ...]]] = []
    # Identische gespeicherte Trägerdaten sind derselbe Beleg. Ähnliche Werte
    # werden weder gemittelt noch nach dem kleineren Abstand ausgesucht.
    identities: dict[tuple[object, ...], int] = {}
    for feature in sorted(entry.features.values(), key=lambda item: item.id):
        check()
        for patch in feature.surface_patches:
            if not valid_patch(
                patch,
                face_count=mesh.triangle_count,
                allowed_indices=feature.face_indices,
                check_cancelled=check,
            ):
                continue
            identity = (patch.kind, *sorted(patch.params.items()))
            group = identities.get(identity)
            if group is None:
                group = len(carriers)
                identities[identity] = group
                carriers.append(patch)
                claims.append([])
            claims[group].append(patch.face_indices)
            for start in range(0, len(patch.face_indices), PATCH_BLOCK):
                check()
                indices = np.asarray(
                    patch.face_indices[start : start + PATCH_BLOCK], dtype=np.int64
                )
                previous = owners[indices]
                origin_masks[indices] |= source_flags[patch.source]
                owners[indices] = np.where(
                    previous == -1, group, np.where(previous == group, group, -2)
                )
    report(0.1)
    values = np.full(mesh.triangle_count, np.nan, dtype=np.float64)
    raw = mesh.raw
    # Je Träger die Dreiecke, die er allein beansprucht — und dann alle Träger
    # zusammen in einen Aufruf: `deviation_bounds_grouped` rechnet je Trägerart
    # einen Stapel über alle Träger, nicht einen je Bohrung.
    selected_per_carrier: list[np.ndarray] = []
    for group in range(len(carriers)):
        check()
        selected: list[np.ndarray] = []
        for claim in claims[group]:
            for start in range(0, len(claim), PATCH_BLOCK):
                check()
                indices = np.asarray(claim[start : start + PATCH_BLOCK], dtype=np.int64)
                owned = indices[owners[indices] == group]
                selected.append(owned)
                owners[owned] = -3
        selected_per_carrier.append(
            np.concatenate(selected) if selected else np.zeros(0, dtype=np.int64)
        )

    def advance(done: int, total: int) -> None:
        report(0.1 + 0.89 * done / max(total, 1))

    tables = deviation_bounds_grouped(
        carriers,
        [raw.vertices[raw.faces[indices]] for indices in selected_per_carrier],
        epsilon_mm=EPS_GEOM,
        cancelled=cancelled,
        progress=advance,
    )
    check()
    # Die Klammern je Dreieck als Arrays: Obergrenze in die Karte, Breite als
    # numerischer Fehler, und der Zeuge ist das Dreieck mit der größten
    # belegten Untergrenze — bei Gleichstand das mit dem kleineren Index.
    face_indices = np.concatenate(selected_per_carrier) if carriers else np.zeros(0, dtype=np.int64)
    joined = DeviationTable.joined(tables, len(face_indices))
    lowers, uppers = joined.lower_mm, joined.upper_mm
    with np.errstate(invalid="ignore"):
        usable = joined.known & (lowers >= 0.0) & (lowers <= uppers)
    face_indices = face_indices[usable]
    lowers, uppers = lowers[usable], uppers[usable]
    witnesses = joined.witness_uv[usable]
    values[face_indices] = uppers
    used_sources = int(np.bitwise_or.reduce(origin_masks[face_indices])) if len(face_indices) else 0
    maximum_lower = float(lowers.max()) if len(lowers) else 0.0
    maximum_upper = float(uppers.max()) if len(uppers) else 0.0
    widths = np.where(uppers > lowers, np.nextafter(uppers - lowers, np.inf), 0.0)
    numerical_error = float(widths.max()) if len(widths) else 0.0
    witness_point: Vec3 | None = None
    witness_face: int | None = None
    witness_distance: float | None = None
    # Der Zeuge nach fallender Untergrenze, bei Gleichstand nach steigendem
    # Index — und nur, wo der Anzeigepunkt endlich ist.
    for position in np.lexsort((face_indices, -lowers)):
        check()
        index = int(face_indices[position])
        first, second, third = raw.vertices[raw.faces[index]]
        u, v = (float(witnesses[position, 0]), float(witnesses[position, 1]))
        # Anzeige der belegten baryzentrischen Stelle. Die Untergrenze
        # gilt für die exakte Linearkombination im Rechner, nicht für
        # den zwangsläufig gerundeten Anzeigepunkt.
        point = (1.0 - u - v) * first + u * second + v * third
        if np.isfinite(point).all():
            witness_point = (float(point[0]), float(point[1]), float(point[2]))
            witness_face = index
            witness_distance = float(lowers[position])
            break
    check()
    known = bool(np.any(np.isfinite(values)))
    sources = [source for source, flag in source_flags.items() if used_sources & flag]
    source_names = {
        "native": _("ursprüngliche exakte Flächen"),
        "facets": _("geprüfte Ebenen der Originaldreiecke"),
        "fit": _("bereits eingepasste Flächen"),
    }
    source_note = (
        _(
            "Bezug: {sources}.",
            sources=", ".join(str(source_names[source]) for source in sorted(sources)),
        )
        if sources
        else _("Keine Fläche konnte mit einem eindeutigen Formbezug ausgewertet werden.")
    )
    body_note = (
        _("Am exakten Körper wird seine Darstellung geprüft; die Originalform bleibt unverändert.")
        if entry.kind == "brep"
        else ""
    )
    report(1.0)
    return AnalysisMap(
        kind="deviation",
        title=TITLES["deviation"],
        values=tuple(float(value) for value in values),
        unit="mm",
        low=0.0,
        high=maximum_upper if maximum_upper > 0.0 else EPS_DISPLAY,
        highlighted=(witness_face,) if witness_face is not None else (),
        note=_(
            "Obere Abstandsgrenzen ganzer Dreiecksflächen; keine neue Einpassung. "
            "{source_note} {body_note}",
            source_note=source_note,
            body_note=body_note,
        ),
        unknown_note=_("kein eindeutiger oder numerisch begrenzbarer Formbezug"),
        maximum_interval=(maximum_lower, maximum_upper) if known else None,
        numerical_error=numerical_error if known else None,
        witness_point=witness_point,
        witness_face=witness_face,
        witness_distance=witness_distance,
    )


def _source_map(measured: SampledDeviation) -> AnalysisMap:
    """Die Karte eines umgewandelten Körpers: gemessene Abstände zu seinem Netz, je Dreieck."""
    values = measured.values_mm
    highest = float(values.max()) if len(values) else 0.0
    return AnalysisMap(
        kind="deviation",
        title=TITLES["deviation"],
        values=tuple(float(value) for value in values),
        unit="mm",
        low=0.0,
        high=highest if highest > 0.0 else EPS_DISPLAY,
        highlighted=(measured.witness_face,) if measured.witness_face is not None else (),
        note=_(
            "Abstand zum Netz vor der Umwandlung, in beiden Richtungen an Stichproben gemessen."
        ),
        witness_point=measured.witness,
        witness_face=measured.witness_face,
        witness_distance=highest if measured.witness is not None else None,
    )


def _mesh_of(entry: SceneObject) -> MeshData:
    """Die Dreiecke des Körpers — auch wenn er exakt ist.

    Hier stand ``raise TypeError("analysis maps need the trimesh backed
    mesh")``, mit dem Kommentar „heute nur ein Kern" daneben. Der Satz war
    richtig, als er geschrieben wurde, und ist mit dem B-Rep-Kern still falsch
    geworden: Ein STEP-Import ist ein exakter Körper, und wer an ihm eine
    Analysekarte wählte, bekam einen **Programmfehler** samt Fehlerbericht —
    für eine gewöhnliche Handlung (Robert, 27.08.2026, Absturzbericht
    S-20260826-594f0f).

    Der Weg von B-Rep zu Mesh steht jederzeit offen (§30): Die Karten rechnen
    auf der Tessellation, wie jede Mesh-Operation an einem exakten Körper.
    ``as_mesh_data`` weist einen Körper, der wirklich keiner der beiden Kerne
    ist, mit einer lesbaren Meldung ab — nicht mit einem ``TypeError``.
    """
    return as_mesh_data(entry.mesh)


# --- Das Voxelfeld, auf dem beide Abstandskarten leben --------------------------


@dataclass(frozen=True, slots=True)
class SolidField:
    """Der Körper als gefülltes Raster, plus der Abstand nach außen je Voxel.

    Beide Abstandskarten brauchen dieselben zwei Fragen beantwortet — „ist hier
    Material" und „wie weit ist es bis zur Oberfläche" — und beide Antworten
    sind auf einem Raster weit billiger als mit einem Strahl je Dreieck: ein
    Strahl je Dreieck wächst mit dem Quadrat des Netzes, das hier wächst mit
    dem Volumen und schert sich nicht darum, wie fein das Netz ist.

    Das Raster kommt aus denselben Querschnitten, die die Schichtanalyse
    benutzt (§22.1), nicht aus einer Netzunterteilung — eine Platte aus zwölf
    großen Dreiecken bräuchte Minuten zum Unterteilen und braucht
    Millisekunden zum Schneiden.

    Der Preis ist die Auflösung: alles, was aus diesem Feld gelesen wird, ist
    auf ``pitch`` quantisiert, und die Legende sagt das, statt etwas anderes
    vorzugeben.
    """

    filled: Any
    origin: Any
    """Weltposition des Voxels (0, 0, 0)."""
    pitch: float


#: Feiner als so viele Schritte entlang der Diagonale wird das Raster nie. Ein
#: feineres Gitter kauft Genauigkeit, die niemand drucken kann, und kostet
#: Speicher, den niemand ausgeben will.
MAX_GRID_STEPS = 300


def solid_field(
    mesh: MeshData, pitch: float | None = None, *, cancelled: CancelToken | None = None
) -> SolidField:
    """Rastert den Körper: welche Zellen Material halten und welche nicht."""
    import shapely

    if cancelled is not None:
        cancelled.raise_if_cancelled()
    step = pitch if pitch is not None else default_pitch(mesh)
    low = np.asarray(mesh.bounds.minimum, dtype=float) - step
    high = np.asarray(mesh.bounds.maximum, dtype=float) + step
    # Ringsum eine leere Zelle, damit ein Lauf, der den Körper verlässt, immer
    # auf etwas Leerem landet, statt vom Raster zu fallen.
    axes = [np.arange(low[axis], high[axis] + step, step) for axis in range(3)]
    filled = np.zeros(tuple(len(axis) for axis in axes), dtype=bool)

    grid_x, grid_y = np.meshgrid(axes[0], axes[1], indexing="ij")
    flat_x, flat_y = grid_x.ravel(), grid_y.ravel()
    # Jede Höhe in einem Durchgang. Schicht für Schicht zu schneiden lief alle
    # Dreiecke einmal je Schicht ab — dreihundert Schichten eines Körpers mit
    # dreihunderttausend Dreiecken sind die Stelle, an der die Wandkarte die
    # meiste Zeit verbrachte.
    for index, shape in enumerate(cross_sections(mesh, axes[2], cancelled=cancelled)):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        if shape is None or shape.is_empty:
            continue
        inside = shapely.contains_xy(shape, flat_x, flat_y)
        filled[:, :, index] = inside.reshape(grid_x.shape)

    if cancelled is not None:
        cancelled.raise_if_cancelled()
    return SolidField(
        filled=filled,
        origin=np.array([axis[0] for axis in axes], dtype=float),
        pitch=step,
    )


def default_pitch(mesh: MeshData, detail: float | None = None) -> float:
    """Ein halbes kleinstes Detail — eine halbe Bahnbreite bei FDM, ein
    halber Bildpunkt bei Resin —, aber nie mehr Schritte, als das Raster
    zulässt. Ohne Druckerprofil bestimmt allein die Modellgröße die Auflösung;
    es wird keine Düse angenommen.
    """
    diagonal = float(mesh.bounds.diagonal)
    return max(
        detail / 2.0 if detail is not None else 0.0,
        diagonal / MAX_GRID_STEPS,
        EPS_GEOM,
    )


def _indices(field: SolidField, points: Any) -> Any:
    """Weltpunkte als Rasterindizes, auf das Raster beschnitten."""
    raw = (np.asarray(points, dtype=float) - field.origin) / field.pitch
    indices = np.rint(raw).astype(int)
    upper = np.asarray(field.filled.shape) - 1
    return np.clip(indices, 0, upper)


# --- Wandstärke -----------------------------------------------------------------


def wall_thickness_map(
    mesh: MeshData,
    minimum: float | None = None,
    pitch: float | None = None,
    *,
    cancelled: CancelToken | None = None,
) -> AnalysisMap:
    """Die Dicke unter jedem Dreieck: einwärts entlang der Normalen bis zur
    gegenüberliegenden Wand.

    Dieselbe Frage, die das Messwerkzeug mit einem einzelnen Strahl beantwortet
    (§18.3) — eine Stelle anzuklicken und auf die Karte zu sehen gibt also
    dieselbe Zahl, bis auf das Raster, auf dem die Karte abgetastet ist. Wo der
    Lauf gar kein Material findet, ist der Wert ``nan``: eine offene Fläche hat
    keine Dicke, und null wäre eine Lüge.

    ``cancelled`` bricht zwischen den Schichten des Rasters und zwischen den
    Schritten des Einwärtslaufs ab. Die Karte kostet an echten Modellen
    Sekunden (gemessen am 22.09.2026: 2,7 bis 5,5 s), und die Wandprüfung der
    Formsitzung stößt nach jedem Zug eine neue an — die alte muss dann gehen
    können, statt den Rechner für eine Antwort zu belegen, die niemand mehr
    will.
    """
    body = mesh.raw
    if not len(body.faces):
        return AnalysisMap(
            kind="wall", title=TITLES["wall"], values=(), unit="mm", low=0.0, high=0.0
        )

    field = solid_field(mesh, pitch, cancelled=cancelled)
    thickness = _inward_thickness(body, field, cancelled)

    highlighted: tuple[int, ...] = ()
    if minimum is not None:
        highlighted = tuple(
            int(index)
            for index, value in enumerate(thickness)
            if not math.isnan(value) and value < minimum
        )
    known = [value for value in thickness if not math.isnan(value)]
    top = max(known) if known else 0.0
    # **Die Skala wird gedeckelt.** An einer Stirnfläche misst der Strahl quer
    # durch das ganze Teil: bei einem Brett von 8 mm Dicke und 80 mm Länge
    # spannte die Legende über 80 mm, und der Bereich, um den es beim Drucken
    # geht — unter zwei Extrusionsbreiten —, fiel in eine einzige Farbstufe.
    # Die Karte konnte ihre eigene Frage nicht beantworten. Alles über dem
    # Deckel ist ohnehin dieselbe Aussage: dick genug.
    capped = min(top, minimum * WALL_SCALE_FACTOR) if minimum else top
    return AnalysisMap(
        kind="wall",
        title=TITLES["wall"],
        values=tuple(thickness),
        unit="mm",
        low=0.0,
        high=capped if capped > 0.0 else top,
        highlighted=highlighted,
        threshold=minimum,
        note=_(
            "Untergrenze sind zwei Extrusionsbreiten. Die Skala endet weit darüber; "
            "alles Dickere trägt dieselbe Farbe."
        )
        if minimum is not None and capped < top
        else _("Untergrenze sind zwei Extrusionsbreiten.")
        if minimum is not None
        else _("Auf einem Raster abgetastet."),
        resolution=field.pitch,
        unknown_note=_("kein Material gegenüber"),
    )


def _inward_thickness(
    body: trimesh.Trimesh, field: SolidField, cancelled: CancelToken | None = None
) -> list[float]:
    """Läuft von jedem Dreieck einwärts, bis das Material ausgeht."""
    centres = np.asarray(body.triangles_center, dtype=float)
    normals = np.asarray(body.face_normals, dtype=float)

    # Nichts kann dicker sein, als der Körper lang ist.
    steps = int(float(body.scale) / field.pitch) + 2
    reached = np.zeros(len(centres), dtype=float)
    upper = np.asarray(field.filled.shape, dtype=int) - 1
    # **Gerechnet wird nur, wer noch im Material ist.** Hat ein Lauf das
    # Material einmal verlassen, hört er auf zu zählen — was jenseits der
    # gegenüberliegenden Wand liegt, gehört zur nächsten Wand, nicht zu dieser.
    # Bis zum 22.09.2026 wurden trotzdem alle Dreiecke jeden Schritt neu
    # abgetastet, bis zur Länge des Körpers: an einer dünnwandigen Schale
    # dreihundert Schritte über alle Dreiecke für Wände, die nach drei zu Ende
    # waren. Die Rechnung je Punkt bleibt dieselbe wie in ``_indices`` —
    # dieselben Operationen in derselben Reihenfolge, nur über die noch
    # laufenden Dreiecke —, und damit bleiben auch Punkte genau auf einer
    # Rasterhälfte auf derselben Seite wie zuvor.
    active = np.arange(len(centres))

    for step in range(steps):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        samples = np.multiply(normals, field.pitch * (step + 0.5))
        np.subtract(centres, samples, out=samples)
        np.subtract(samples, field.origin, out=samples)
        np.divide(samples, field.pitch, out=samples)
        np.rint(samples, out=samples)
        indices = samples.astype(int)
        np.clip(indices, 0, upper, out=indices)
        here = field.filled[indices[:, 0], indices[:, 1], indices[:, 2]]
        # Nur beim Austritt kompaktieren. In einem massiven Körper bleiben
        # fast alle Strahlen lange aktiv; ihre Zentren und Normalen jeden
        # Schritt über Indizes zu kopieren verdoppelte dort den Aufwand.
        # Die erreichten Schritte stehen beim ersten Austritt fest.
        if not here.all():
            reached[active[~here]] = step
            active = active[here]
            if not len(active):
                break
            centres = centres[here]
            normals = normals[here]
    else:
        reached[active] = steps

    values = reached * field.pitch
    return [float(value) if value > 0.0 else float("nan") for value in values]


# --- Überhang -------------------------------------------------------------------


def overhang_map(mesh: MeshData, limit: float = OVERHANG_LIMIT_DEGREES) -> AnalysisMap:
    """Winkel gegen die Baurichtung, null bei einer senkrechten Wand (§18.4).

    Eine Wand parallel zu Z ist 0°, eine Decke, die gerade nach unten schaut,
    90°. Nach oben schauende Dreiecke sind gar keine Überhänge — sie bleiben
    also bei null, statt negativ zu werden.
    """
    body = mesh.raw
    if not len(body.faces):
        return AnalysisMap(
            kind="overhang",
            title=TITLES["overhang"],
            values=(),
            unit=DEGREE_UNIT,
            low=0.0,
            high=0.0,
            threshold=limit,
        )

    downward = -np.asarray(body.face_normals, dtype=float)[:, 2]
    angles = np.degrees(np.arcsin(np.clip(downward, -1.0, 1.0)))
    angles = np.maximum(angles, 0.0)
    return AnalysisMap(
        kind="overhang",
        title=TITLES["overhang"],
        values=tuple(float(value) for value in angles),
        unit=DEGREE_UNIT,
        low=0.0,
        high=90.0,
        highlighted=tuple(int(index) for index in np.nonzero(angles > limit)[0]),
        threshold=limit,
        # Die Grenze, nach der die Karte wirklich hervorhebt — ein kalibriertes
        # Material trägt seinen gemessenen Winkel (``analysis_limits``), und
        # „45 Grad“ fest im Satz widersprach dann der eigenen Färbung.
        note=_(
            "Über {angle} Grad braucht die Fläche in aller Regel eine Stütze.",
            angle=format_decimal(round(limit, 1)),
        ),
    )


# --- Netzdefekte ----------------------------------------------------------------

#: Wie viele Kandidatenpaare die Netzfehlerkarte höchstens prüft — rund vier
#: Sekunden bei zwei Mikrosekunden je Paar; §31 gibt einer Karte drei im
#: Hintergrund. Fest und nicht auf die Uhr, damit dieselbe Datei auf jedem
#: Rechner dieselbe Karte zeigt.
DEFECT_MAP_PAIRS: Final = 2_000_000


def defect_map(mesh: MeshData, cancelled: CancelToken | None = None) -> AnalysisMap:
    """Offene Kanten, verzweigte Kanten und Durchdringungen, je Dreieck (§18.4).

    **Die dritte war zugesagt und fehlte** (RM-143). Die ersten beiden liest
    die Kantentabelle: eine Kante mit einer Fläche ist offen, eine mit dreien
    verzweigt. Eine **Selbstdurchdringung** steht dort nicht — zwei Wände, die
    einander schneiden, haben lauter saubere Kanten mit je zwei Flächen, und
    genau deshalb sah die Karte an `broken_selfint.stl` nichts.

    Sie ist die teuerste der drei und steht deshalb zuletzt: Ihre Suche ist
    räumlich (`repair.crossings_of`), nicht tabellarisch, und deckelt sich an
    :data:`DEFECT_MAP_PAIRS` geprüften Paaren — die Reparatur prüft mit ihrem
    größeren Budget, und hat sie das Netz schon ganz geprüft, liest die Karte
    ihre Antwort. **Was die Suche nicht erreicht hat, ist unbekannt, nicht
    alles** (Befund B3 der Durchsicht 24.09.2026): Bis dahin färbte eine
    vorzeitig beendete Suche jede fehlerfreie Fläche grau, auch die schon
    geprüften.
    """
    from app.core.geom.repair import crossed_edge_faces, crossings_of

    body = mesh.raw
    values = np.zeros(len(body.faces), dtype=float)
    complete = True
    if len(body.faces):
        edges = np.asarray(body.edges_sorted)
        groups = trimesh.grouping.group_rows(edges, require_count=None)
        for group in groups:
            count = len(group)
            if count == 2:
                continue
            level = 1.0 if count == 1 else 2.0
            for edge in np.atleast_1d(np.asarray(group)):
                face = int(edge) // 3
                values[face] = max(values[face], level)
        # Zwischen den Phasen gefragt: Die räumliche Suche fragt erst je
        # Kandidatenblock, und an einem kleinen Körper gibt es womöglich keinen
        # — wer die nächste Karte wählt, wartet trotzdem nicht auf diese.
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        # Gegeneinander zeigende Außenseiten stehen in der Kantentabelle wie
        # offene Ränder; eine Durchdringung darüber wiegt schwerer und färbt.
        for face in crossed_edge_faces(mesh).tolist():
            values[face] = max(values[face], 4.0)
        crossings = crossings_of(mesh, cancelled, budget=DEFECT_MAP_PAIRS)
        complete = crossings.complete
        for face in crossings.faces:
            values[face] = 3.0
        if not complete:
            # Belegte Fehler bleiben sichtbar; unbekannt ist, was die Suche
            # nicht ganz geprüft hat.
            unchecked = (
                np.ones(len(values), dtype=bool)
                if crossings.checked is None
                else ~crossings.checked
            )
            values[unchecked & (values < 1.0)] = np.nan

    return AnalysisMap(
        kind="defects",
        title=TITLES["defects"],
        values=tuple(float(value) for value in values),
        unit="",
        low=0.0,
        high=4.0,
        highlighted=tuple(int(index) for index in np.nonzero(values > 0.0)[0]),
        threshold=1.0,
        categories=_named(DEFECT_LEVELS),
        note=_(
            "Die Suche nach Überschneidungen ist unvollständig. Markierte Fehler sind "
            "bestätigt; weitere sind möglich."
        )
        if not complete
        # Eine Karte ohne Fehler färbte das Modell einfarbig und sagte nichts.
        else _("Keine Netzfehler gefunden.")
        if not np.any(values > 0.0)
        else None,
        unknown_note=_("Überschneidungen nicht vollständig geprüft") if not complete else None,
    )


# --- Krümmung -------------------------------------------------------------------


def curvature_map(
    mesh: MeshData,
    features: dict[FeatureId, Feature] | None = None,
    *,
    cancelled: CancelToken | None = None,
) -> AnalysisMap:
    """Der Radius, mit dem ein Dreieck gekrümmt ist — in Millimetern.

    **Vorher stand hier der schärfste Winkel zu einem Nachbarn, und das misst
    das Netz statt den Körper.** Der Docstring sagte es selbst: „Kanten stechen
    hervor, Verrundungen bleiben glatt." Genau das ist der Zweck einer
    Verrundung — je feiner sie vernetzt ist, desto kleiner der Winkel je
    Facette, obwohl der Radius derselbe bleibt. Eine Karte, deren Aussage an
    der Vernetzungsdichte hängt, beantwortet die Frage nicht, die §18.4 an sie
    stellt: *wie* rund, nicht *dass*.

    Gerechnet wird über :func:`app.core.perceive.features.pair_radii` — dieselbe
    Zahl, mit der die Erkennung ihre Flecken trennt. Was die Karte zeigt, ist
    damit genau das, wonach die Erkennung geht, und die Spalte *Nutzen* in
    §18.4 („Feature-Erkennung prüfen") stimmt wörtlich.

    **Drei Fälle, und zwei davon haben keinen Radius.** Eine ebene Fläche ist
    nicht unendlich rund, sie ist gar nicht rund — sie bekommt ``nan``, das in
    dieser Karte „kann ich nicht sagen" heißt. Eine **Kante** bekommt null und
    wird hervorgehoben: Die Formel gäbe dort 0,2 mm, eine Zahl, die nach einer
    sehr feinen Verrundung aussieht und keine ist.
    """
    body = mesh.raw
    values = np.full(len(body.faces), np.nan, dtype=float)
    pairs = np.asarray(body.face_adjacency, dtype=np.int64).reshape(-1, 2)
    if not len(pairs):
        return _curvature_result(values, set(), _radii_from_features(values, features))

    if cancelled is not None:
        cancelled.raise_if_cancelled()
    degrees = np.degrees(np.asarray(body.face_adjacency_angles, dtype=float))
    radii = np.asarray(pair_radii(body), dtype=float)
    if cancelled is not None:
        cancelled.raise_if_cancelled()

    # **Eine Kante geht nicht in den Wert ein, sie wird markiert.** Sie sagt
    # nichts darüber, wie die Fläche gekrümmt ist, auf der das Dreieck liegt —
    # sie sagt, dass daneben eine andere anfängt. Der kleinste Radius über
    # *alle* Nachbarn, wie es die alte Karte mit dem schärfsten Winkel tat,
    # überschreibt jede Rundung: An einem Zylinder grenzt **jedes**
    # Manteldreieck an den Deckel, und die ganze Wand käme als scharfe Kante
    # heraus.
    edge = degrees >= CURVATURE_LIMIT
    sharp = {int(index) for index in np.unique(pairs[edge])}
    # Unter den **glatten** Nachbarn gewinnt der kleinste: Wo eine Fläche in
    # zwei Richtungen verschieden gekrümmt ist, ist die engere die, nach der
    # gefragt wird. ``fmin`` übergeht das ``nan`` des Anfangs — dieselbe
    # Rechnung wie die Schleife je Paar bis zum 22.09.2026, nur auf einmal:
    # 1,35 Millionen Paare an 900 000 Dreiecken kosteten dort zwei Sekunden.
    smooth = ~edge & np.isfinite(radii)
    np.fmin.at(values, pairs[smooth, 0], radii[smooth])
    np.fmin.at(values, pairs[smooth, 1], radii[smooth])
    if cancelled is not None:
        cancelled.raise_if_cancelled()

    exact = _radii_from_features(values, features)
    return _curvature_result(values, sharp, exact)


#: Woraus sich der Krümmungsradius eines Merkmals ablesen lässt, und mit
#: welchem Faktor. **Kein Kegel:** Sein Radius ändert sich über die Höhe, ein
#: einzelner Wert wäre dort für fast jedes Dreieck der falsche.
#:
#: **Und kein Langloch**, aus genau demselben Grund: Gekrümmt ist es nur an
#: seinen beiden Enden. Die Flanken dazwischen sind eben, und die machen bei
#: einem langen Loch die Mehrzahl der Dreiecke aus — ein eingesetzter Radius
#: färbte dort eine Rundung, wo eine gerade Wand steht.
_FEATURE_RADIUS: Final[dict[str, tuple[str, float]]] = {
    "sphere": ("diameter", 0.5),
    "hole": ("diameter", 0.5),
    "pin": ("diameter", 0.5),
    "fillet": ("radius", 1.0),
    "torus": ("tube_diameter", 0.5),
}
"""

Der Torus stand hier bis zum 23.08.2026 als ``("minor_radius", 1.0)`` — **den
Schlüssel gibt es nicht**, das Merkmal führt ``tube_diameter``. Der Eintrag lief
ins ``continue`` und tat nichts.

Aufgefallen ist es niemandem, weil die Schätzung den Torus ohnehin auf 0,4 %
trifft: Er hat eine ausgezeichnete Hauptkrümmungsrichtung, und seine Vernetzung
folgt ihr. **Ein Eintrag, der nichts bewirkt, sieht dort genauso aus wie einer,
der wirkt** — gefunden hat es 3d-druck-64 beim Nachmessen, nicht ein Test.
``tests/test_maps.py`` prüft die Tabelle jetzt gegen die Merkmale des Korpus.
"""


def _radii_from_features(values: np.ndarray, features: dict[FeatureId, Feature] | None) -> set[int]:
    """Setzt den **gemessenen** Radius ein, wo die Erkennung einen kennt.

    **Die Erkennung hat recht, und das ist kein Zufall.** ``fit_sphere`` und
    Verwandte rechnen einen Ausgleich über *alle* Punkte des Merkmals; die
    Karte schätzt aus je einer einzelnen Nachbarschaft zweier Dreiecke. Eine
    einzelne Nachbarschaft kann schräg zur Hauptkrümmung liegen, eine
    Ausgleichsfläche nicht.

    **Bei einer Kugel liegt jede schräg**, und genau dort brach die Schätzung
    weg. Gemessen am 23.08.2026, Karte gegen Erkennung an den Dreiecken des
    Merkmals:

    ===================== ======== ============ ======= ========
    Korpus                Art      Erkennung    Karte   Abstand
    ===================== ======== ============ ======= ========
    sphere_socket.stl     sphere   7,969        7,211   -9,5 %
    post_with_fillet.stl  pin      6,000        5,996   -0,1 %
    post_with_fillet.stl  torus    2,994        2,992   -0,1 %
    block_with_rounded    fillet   2,999        2,998   -0,0 %
    torus_ring.stl        torus    4,957        4,937   -0,4 %
    ===================== ======== ============ ======= ========

    Zylinder, Verrundung und Torus haben eine ausgezeichnete
    Hauptkrümmungsrichtung, und ihre Vernetzung folgt ihr — es gibt
    Nachbarschaften, die quer liegen und exakt ``r`` liefern. Eine Kugel hat
    keine solche Richtung, und eine Icosphere ist obendrein **selbstähnlich
    verzerrt**: Die Dreiecke an den zwölf Ikosaeder-Ecken sind in jeder
    Auflösung anders geformt als die in der Flächenmitte. Deshalb verschwindet
    der Fehler auch bei 64-facher Verfeinerung nicht — er ist keine
    Diskretisierung, sondern ein Formfaktor der Vernetzung.

    Weder Median noch Perzentil helfen: gemessen liegt der Median am Torus bei
    +100,8 %, und bei p20 ist die Kugel immer noch -9,9 %.

    Gibt zurück, welche Dreiecke ihren Wert von der Erkennung haben — die Karte
    weist beide Herkünfte aus (§22.5).
    """
    if not features:
        return set()
    exact: set[int] = set()
    for feature in features.values():
        entry = _FEATURE_RADIUS.get(feature.kind)
        if entry is None:
            continue
        name, factor = entry
        measured = feature.params.get(name)
        if measured is None:
            continue
        radius = float(measured) * factor
        if radius <= 0.0:
            continue
        indices = np.asarray(feature.face_indices or (), dtype=np.int64)
        indices = indices[(indices >= 0) & (indices < len(values))]
        values[indices] = radius
        exact.update(indices.tolist())
    return exact


def _curvature_result(values: np.ndarray, sharp: set[int], exact: set[int]) -> AnalysisMap:
    known = values[~np.isnan(values)]
    note = _(
        "Der Radius, mit dem eine Fläche gekrümmt ist. Hervorgehoben sind "
        "scharfe Kanten; ebene Flächen haben keinen Radius."
    )
    if exact:
        # **Zwei Herkünfte in einer Karte werden ausgewiesen** (§22.5), und zwar
        # in Worten — nicht über einen Farbton, den niemand ohne Legende deuten
        # kann (Regel 18).
        #
        # **Ohne Platzhalter**, obwohl eine Zahl hier gut stünde: Einen Text aus
        # dem Kern formatiert niemand nach, und ein ``{count}`` erschiene dem
        # Kunden mit geschweiften Klammern. ``tests/test_errors.py`` sucht im
        # ganzen Kern danach.
        note = _(
            "Der Radius, mit dem eine Fläche gekrümmt ist. Hervorgehoben sind "
            "scharfe Kanten; ebene Flächen haben keinen Radius. Wo ein Merkmal "
            "erkannt wurde, steht sein gemessenes Maß — sonst eine Schätzung aus "
            "den Nachbarflächen."
        )
    return AnalysisMap(
        kind="curvature",
        title=TITLES["curvature"],
        values=tuple(float(value) for value in values),
        unit="mm",
        low=float(known.min()) if len(known) else 0.0,
        high=float(known.max()) if len(known) else 0.0,
        highlighted=tuple(sorted(sharp)),
        note=note,
        display_scale="asinh",
    )


# --- Was die Erkennung gesehen hat ----------------------------------------------


def feature_map(mesh: MeshData, features: dict[FeatureId, Feature]) -> AnalysisMap:
    """Jedes Merkmal auf einer eigenen Stufe — „verstehen, was die KI
    sieht" (§18.4).
    """
    body = mesh.raw
    values = np.zeros(len(body.faces), dtype=float)
    names: list[str] = [str(_("ohne Merkmal"))]

    for level, (feature_id, feature) in enumerate(sorted(features.items()), start=1):
        names.append(feature_id)
        for index in feature.face_indices:
            if 0 <= index < len(values):
                values[index] = float(level)

    return AnalysisMap(
        kind="features",
        title=TITLES["features"],
        values=tuple(float(value) for value in values),
        unit="",
        low=0.0,
        high=float(len(names) - 1),
        categories=tuple(names),
    )


# --- Passungen (§14) ------------------------------------------------------------


def fit_map(mesh: MeshData, entry: SceneObject, scene: Scene | None) -> AnalysisMap:
    """Beteiligte, ungeklärte und verletzte Passungen aus demselben Prüfbericht."""
    body = mesh.raw
    values = np.zeros(len(body.faces), dtype=float)
    if scene is not None:
        levels = _fit_feature_levels(scene, entry.id)
        for fit in scene.fits:
            for reference in (fit.a, fit.b):
                if reference.object_id != entry.id:
                    continue
                feature = entry.features.get(reference.feature_id)
                if feature is None:
                    continue
                level = levels.get(reference.feature_id, 1.0)
                for index in feature.face_indices:
                    if 0 <= index < len(values):
                        values[index] = max(values[index], level)

    return AnalysisMap(
        kind="fits",
        title=TITLES["fits"],
        values=tuple(float(value) for value in values),
        unit="",
        low=0.0,
        high=3.0,
        highlighted=tuple(int(index) for index in np.nonzero(values >= 2.0)[0]),
        threshold=2.0,
        categories=_named(FIT_LEVELS),
    )


def _fit_feature_levels(scene: Scene, object_id: ObjectId) -> dict[FeatureId, float]:
    """Der Bericht ist die einzige Quelle; dieselbe Beziehung betrifft beide Gegenstücke."""
    levels: dict[FeatureId, float] = {}
    relationships = {fit.name: fit for fit in scene.fits}
    for finding in scene.report.findings:
        if not finding.code.startswith("fit.") or finding.severity == "info":
            continue
        # Eine fehlende Prüfung oder angenäherte Probe belegt keine Verletzung.
        # Neue unbekannte Warncodes bleiben deshalb ebenfalls ausdrücklich offen.
        level = (
            3.0
            if finding.code
            in {"fit.violated", "fit.collision", "fit.pitch_mismatch", "fit.handedness_mismatch"}
            else 2.0
        )
        name = finding.values.get("fit")
        fit = relationships.get(name) if isinstance(name, str) else None
        if fit is not None:
            names = [ref.feature_id for ref in (fit.a, fit.b) if ref.object_id == object_id]
        elif finding.object_id in (None, object_id):
            names = list(finding.feature_ids)
        else:
            names = []
        for feature_id in names:
            levels[feature_id] = max(levels.get(feature_id, 1.0), level)
    return levels


def fits_of(scene: Scene, object_id: ObjectId) -> tuple[Fit, ...]:
    """Passungen, an denen ein Objekt teilnimmt.

    **Ohne Aufrufer in der Anwendung**, und der Docstring behauptete das
    Gegenteil: „benutzt von Legende und Steckbrief". Beide tun es nicht. Der
    Steckbrief zählt die Passungen des Projekts in einer eigenen Zeile
    (``digest._fit_lines``) und wiederholt sie nicht je Körper — §26.1, jede
    Zeile, die nichts unterscheidet, verdrängt eine, die es tut. Eine Legende
    über Passungen gibt es in der Ansicht nicht; :func:`fit_map` färbt die
    Dreiecke und sucht sich seine Paare selbst.

    Die Funktion bleibt, weil sie diese Suche in einem Ausdruck sagt und
    ``fit_map`` sie nachbaut. Was nicht bleiben durfte, ist der Satz darüber:
    Ein Docstring, der zwei Aufrufer nennt, hält den nächsten Leser davon ab,
    genau das nachzusehen.
    """
    return tuple(fit for fit in scene.fits if object_id in (fit.a.object_id, fit.b.object_id))


# --- Stützen (§22) --------------------------------------------------------------


def support_map(
    mesh: MeshData,
    layer_height: float = 0.2,
    cancelled: CancelToken | None = None,
    *,
    overhang_angle: float | None = None,
    pitch: float | None = None,
) -> AnalysisMap:
    """Wie hoch die Stützsäule unter jedem Dreieck wüchse.

    Das *Urteil* — braucht diese Stelle überhaupt Stützen — kommt aus der
    Schichtanalyse (§22): ein Dreieck zählt nur, wenn seine Mitte in den
    ungestützten Bereich einer Schicht fällt. Die *Höhe* ist der Abfall
    darunter. Beides sind Schätzungen dieser Anwendung, nie aus G-Code gemessene
    Zahlen (§22.5).
    """
    body = mesh.raw
    if not len(body.faces):
        return AnalysisMap(
            kind="support", title=TITLES["support"], values=(), unit="mm", low=0.0, high=0.0
        )

    # **Nur, was die Stützen brauchen.** ``slice_body`` misst per Vorgabe auch
    # die gedruckte Struktur — kleinste Breite, Brückenweite, Konturzahl —, und
    # diese Karte liest davon **nichts**: :func:`_overhang_regions` nimmt allein
    # ``layer.overhangs``. Der Schalter dafür steht seit je da, für die
    # Orientierungssuche (§28.2); hier fehlte er.
    #
    # Gemessen am Besenhalter (59 740 Dreiecke, 27,2 mm hoch, 04.09.2026):
    # 13,81 s für die ganze Karte, davon **12,10 s** in ``_survives_opening``
    # → ``_eroded`` — der morphologischen Öffnung, mit der die kleinste
    # Struktur je Schicht gesucht wird. 916 Aufrufe für 136 Schichten, und
    # kein einziger für eine Zahl, die hier jemand liest.
    result = slice_body(
        mesh, layer_height, detail="support", cancelled=cancelled, overhang_angle=overhang_angle
    )
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    regions = _overhang_regions(result)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    centres = np.asarray(body.triangles_center, dtype=float)
    field = solid_field(mesh, pitch, cancelled=cancelled)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    drops = _drop_below(mesh, field, centres)
    if cancelled is not None:
        cancelled.raise_if_cancelled()

    values = np.zeros(len(centres), dtype=float)
    marked = _marked_by_layer(regions, centres, layer_height, cancelled)
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    values[marked] = drops[marked]

    return AnalysisMap(
        kind="support",
        title=TITLES["support"],
        values=tuple(float(value) for value in values),
        unit="mm",
        low=0.0,
        high=float(values.max()) if len(values) else 0.0,
        highlighted=tuple(marked),
        note=_("Geschätzt aus der Schichtanalyse, nicht aus G-Code gemessen."),
        resolution=field.pitch,
    )


def _overhang_regions(result: SliceResult) -> list[tuple[float, list[Any]]]:
    """Schichthöhe und ihre ungestützten Konturen, als shapely-Formen."""
    regions: list[tuple[float, list[Any]]] = []
    for layer in result.layers:
        shapes = [
            ShapelyPolygon(polygon.outline, polygon.holes)
            for polygon in layer.overhangs
            if len(polygon.outline) >= 4
        ]
        if shapes:
            regions.append((layer.z, shapes))
    return regions


def _marked_by_layer(
    regions: list[tuple[float, list[Any]]],
    centres: Any,
    layer_height: float,
    cancelled: CancelToken | None,
) -> Any:
    """Welche Dreiecke in einem ungestützten Bereich liegen — schichtweise.

    **Die teuerste Schleife der sieben Karten, und sie fragte je Dreieck
    einzeln.** Gemessen am Spiderman (885 570 Dreiecke, 04.09.2026): 85,3 s in
    ``_inside`` und 38,5 s in ``_region_at``, darin 216 Millionen Aufrufe von
    ``abs`` — die lineare Suche nach der passenden Schicht, einmal je Dreieck
    über 244 Schichten.

    Beides fällt weg, wenn man die Frage umdreht: nicht „welche Schicht gehört
    zu diesem Dreieck", sondern „welche Dreiecke gehören zu dieser Schicht".
    Die Schichthöhen sind sortiert, also findet ``searchsorted`` die Gruppe in
    einem Zug; und ``shapely.intersects_xy`` prüft alle Punkte einer Schicht
    gegen eine Kontur auf einmal, statt für jeden ein ``Point``-Objekt zu
    bauen.

    **Die Auswahlregel bleibt Zeichen für Zeichen dieselbe:** Die alte Fassung
    nahm die **erste** Schicht der Liste mit ``|h - z| <= layer_height``, und
    die Liste steht aufsteigend — also die unterste, die in Reichweite liegt.
    ``searchsorted(..., z - layer_height, "left")`` trifft genau sie. Wo zwei
    Schichten in Reichweite sind, bekommt weiterhin die untere den Zuschlag;
    eine „nächstgelegene" wäre eine andere Karte.
    """
    if not regions or not len(centres):
        return np.zeros(0, dtype=int)

    heights = np.asarray([height for height, _ in regions], dtype=float)
    lowest = np.searchsorted(heights, centres[:, 2] - layer_height, side="left")
    # Wo die Einfügestelle hinter das Ende zeigt, gibt es keine Schicht mehr;
    # der Index wird geklemmt und die Reichweite darunter aussortiert.
    clamped = np.clip(lowest, 0, len(heights) - 1)
    in_reach = np.abs(heights[clamped] - centres[:, 2]) <= layer_height

    found: list[Any] = []
    for layer in np.unique(clamped[in_reach]):
        if cancelled is not None:
            # Je Schicht statt je Dreieck: Der Abbruch ist eine Sache von
            # Millisekunden, und eine Schicht ist die Einheit, in der hier
            # gerechnet wird.
            cancelled.raise_if_cancelled()
        members = np.flatnonzero(in_reach & (clamped == layer))
        if not len(members):
            continue
        xs = centres[members, 0]
        ys = centres[members, 1]
        inside = np.zeros(len(members), dtype=bool)
        for shape in regions[int(layer)][1]:
            inside |= shapely.intersects_xy(shape, xs, ys)
        found.append(members[inside])

    return np.concatenate(found) if found else np.zeros(0, dtype=int)


def _drop_below(mesh: MeshData, field: SolidField, centres: Any) -> Any:
    """Wie weit es senkrecht nach unten bis zum nächsten Material geht — oder
    bis zur Druckplatte.

    Vom selben Raster abgelesen, das die Dickenkarte benutzt: in jeder Säule
    ist das höchste gefüllte Voxel unter dem Dreieck die Stelle, an der eine
    Stützsäule aufsetzte.
    """
    filled = field.filled
    height = filled.shape[2]
    ladder = np.arange(height).reshape(1, 1, height)
    # Höchstes gefülltes Voxel auf oder unter jeder Ebene, je Säule; -1, wo es
    # keines gibt.
    below = np.maximum.accumulate(np.where(filled, ladder, -1), axis=2)

    indices = _indices(field, centres)
    rows, columns, layers = indices[:, 0], indices[:, 1], indices[:, 2]
    # Zwei Voxel tiefer, damit das Dreieck nicht die Wand findet, auf der es sitzt.
    start = np.maximum(layers - 2, 0)
    landing = below[rows, columns, start]

    plate = float(mesh.bounds.minimum[2])
    to_plate = centres[:, 2] - plate
    to_surface = (layers - landing) * field.pitch
    return np.maximum(np.where(landing >= 0, to_surface, to_plate), 0.0)


# --- Wohin die Kamera fliegt ----------------------------------------------------


def focus_point(entry: SceneObject, analysis: AnalysisMap) -> Vec3 | None:
    """Die Mitte dessen, was die Karte hervorhebt — wohin die Kamera schauen
    soll (§18.4).
    """
    if analysis.kind == "deviation":
        return analysis.witness_point
    if not analysis.highlighted:
        return None
    mesh = _mesh_of(entry)
    centres = np.asarray(mesh.raw.triangles_center, dtype=float)
    picked = centres[list(analysis.highlighted)]
    middle = picked.mean(axis=0)
    return (float(middle[0]), float(middle[1]), float(middle[2]))


def location_of(entry: SceneObject, finding: Finding) -> Vec3 | None:
    """Wo ein Befund sitzt: an seinem eigenen Ort, oder in der Mitte seiner
    Merkmale.
    """
    if finding.code == "perceive.deviation":
        return None
    if finding.location is not None:
        return finding.location
    mesh = _mesh_of(entry)
    centres = np.asarray(mesh.raw.triangles_center, dtype=float)
    named = [entry.features[key] for key in finding.feature_ids if key in entry.features]
    indices = [
        index for feature in named for index in feature.face_indices if 0 <= index < len(centres)
    ]
    if not indices:
        # **Ein benanntes Merkmal muss keine Flächen führen.** Die Merkmale
        # einer Passung (`lid_cavity`, `lid_collar`) entstehen beim Erzeugen
        # des Deckels und tragen ihre Geometrie als Werte — Mittelpunkt,
        # Normale, Durchmesser —, nicht als Liste von Dreiecken. Ohne diese
        # Zeile fand ein Klick auf eine Passungswarnung keinen Ort, obwohl er
        # danebenstand, und der Kameraflug aus §18.4 fiel aus.
        for feature in named:
            middle = feature.params.get("centre")
            if isinstance(middle, list | tuple) and len(middle) == 3:
                try:
                    return (float(middle[0]), float(middle[1]), float(middle[2]))
                except TypeError, ValueError:
                    continue
        return None
    middle = centres[indices].mean(axis=0)
    return (float(middle[0]), float(middle[1]), float(middle[2]))


def map_for(finding: Finding) -> MapKind | None:
    """Welche Karte einen Befund erklärt — der kürzeste Weg von der Warnung
    zur Stelle (§18.4).
    """
    code = finding.code
    if code in {"perceive.deviation", "brep.from_mesh.deviation"}:
        return "deviation"
    if code.startswith("fit."):
        return "fits"
    # Das Formdetail oder die geschlossene Fehlstelle ist gerade **nicht mehr
    # da**. Eine Merkmalskarte des aktuellen Körpers kann deshalb nur andere,
    # weiterhin erkannte Stellen färben und würde so einen Ort vortäuschen,
    # den der Befund nicht nennt. Körper und erzeugender Schritt bleiben
    # ehrliche Ziele des Klicks.
    if code in {
        "perceive.generated_lost",
        "perceive.referenced_lost",
        "perceive.mended",
        "perceive.orphaned",
    }:
        return None
    if code.startswith("perceive."):
        return "features"
    if code.startswith(("repair.", "ingest.", "mesh.")):
        return "defects"
    if "overhang" in code or code.startswith("orient."):
        return "overhang"
    if "wall" in code or "thin" in code:
        return "wall"
    if "support" in code:
        return "support"
    return None
