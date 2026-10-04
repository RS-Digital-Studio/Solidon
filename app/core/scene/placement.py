"""Was ein angeklicktes Merkmal für die Parameter einer Operation
bedeutet (Bauplan §18.5, §25).

§25 verlangt „einen Baustein an ein erkanntes Merkmal setzen". Erkennen war
P3, Setzen war P5 — aber verbunden wurden die zwei nie: das Merkmal war im
Baum und in der Ansicht wählbar, und der Dialog, der sich als Nächstes
öffnete, wusste nichts davon. Wer eine Bohrung in der eben angeklickten
Fläche wollte, tippte ihre Koordinaten von Hand ab, von der Analysekarte.

Hier treffen sich die zwei — und zwar im Kern statt im Fenster, weil es eine
Regel über Geometrie und Parameter ist, nicht über Widgets: testbar ohne Qt,
und verfügbar für jede Oberfläche, der später eine Auswahl wächst. Heute ist
das Fenster der einzige Aufrufer: die Kommandozeile hat keine Auswahl, und
der Agent arbeitet vom Steckbrief (§26.1) — darum steht die Position jedes
Merkmals in diesem Steckbrief, statt hier ein zweites Mal hergeleitet zu
werden.

Nichts hier ändert das Dokument. Die Werte werden gewöhnliche Parameter der
Operation, der Stapel bleibt also eine reine Funktion dessen, was in ihm
steht (§11) — eine Auswahl ist ein Zustand der Oberfläche und hat in einer
Projektdatei nichts verloren. Darum nimmt eine Operation, die das Merkmal
*prüfen* will, stattdessen seinen Namen als Parameter: ``at_feature`` steht
in der Datei, und die Operation schlägt es bei jedem Rechnen der Szene nach.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Collection, Mapping, Sequence
from contextlib import suppress
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Final, Literal, cast

import numpy as np

from app.core.errors import CORRECT_INPUT, AmbiguityError, ValidationError
from app.core.geom.mesh import MeshData, as_mesh_data, edge_table, unique_edges
from app.core.geom.transform import along as projected_along
from app.core.geom.transform import composed, inverse_affine, moved_points, turned
from app.core.log import get_logger
from app.core.registry import OperationSpec
from app.core.registry.surfaces import SIDE_NAMES as SIDE_NAMES
from app.core.types import (
    IDENTITY_FRAME,
    AskFn,
    CancelToken,
    Document,
    Feature,
    FeatureRef,
    MeasureStatus,
    ObjectId,
    Operation,
    OpId,
    PlaneFrame,
    Point2,
    Profile,
    SceneObject,
    Vec3,
    measure_status,
    vec3_or_none,
)
from app.core.units import (
    EPS_GEOM,
    MAX_FACET_SAG,
    dot3,
    exact_cos_degrees,
    format_length,
    round_display,
)
from app.i18n import TranslatableText, tr

if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry

    from app.core.geom.section import SectionPlane

_log = get_logger(__name__)

#: Der Parameter, mit dem ein Baustein das Merkmal benennt, an das er gehört.
#: Wo eine Operation ihn hat, ist das die ganze Antwort: die Position daneben
#: zählt als Versatz vom Merkmal und bleibt auf null.
FEATURE_FIELD = "at_feature"

#: Welche Operationen ihre Stelle an einem **bestehenden** Merkmal einstellen.
#:
#: Sie unterscheiden sich von den übrigen darin, dass ``at_feature`` bei ihnen
#: eine **Eingabe** ist und kein Ergebnis: Wer eine Bohrung ändert oder in die
#: Länge zieht, hat sie schon gewählt. :func:`surface_values` gibt die Kennung
#: deshalb zurück, statt sie zu leeren.
#:
#: **Der Unterschied fiel lange nicht auf**, weil der Operationsdialog die
#: Kennung zufällig schützte: ``take_placement`` setzt nur Editoren, und für
#: ``at_feature`` gibt es keinen. Ein Träger ohne Fenster nimmt jeden Wert an
#: — und verlor damit genau die Kennung, aus der er sein Merkmal sucht
#: (gemessen am 11.09.2026 an ``resize_hole``: ``at_feature`` kam als ``''``
#: zurück, und ``_source_feature`` fand danach nichts mehr).
AT_AN_EXISTING_FEATURE: Final = frozenset(
    {"move_feature", "duplicate_feature", "slot_hole", "resize_hole"}
)

#: Die Position, in der Reihenfolge, in der die Parameter überall heißen.
POSITION = ("x", "y", "z")

#: Eine freie Richtung, für die Operationen, die eine nehmen (§25, Beschriftung).
NORMAL = ("nx", "ny", "nz")

#: Der Durchmesser, um den eine Textur läuft. **Nicht** ``diameter``: eine
#: Senkung hat einen eigenen — den des Schraubenkopfs — und dürfte den der
#: Bohrung darunter nicht erben. Der Name sagt deshalb, dass er ein Bezug ist
#: und kein Maß; ihn am bloßen ``diameter`` festzumachen trug in
#: ``countersink_hole`` eine falsche Zahl ein, die wie eine gemessene aussah.
#: Der Test, der das verhindert, stand schon da.
DIAMETER_FIELD = "wrap_diameter"

#: Wie dominant eine Komponente sein muss, bevor die Richtung als Achse zählt.
#: Darunter steht das Merkmal schräg, und ihm eine Achse zu nennen wäre eine
#: Rundung, die jemand hinterher bemerken muss.
AXIS_CLARITY = 0.9

#: Operationen, deren ``diameter`` den **Schraubenkopf** meint und nicht die
#: Bohrung, in der er sitzt.
#:
#: Eine Aufzählung und keine Regel, weil das Register die *Bedeutung* eines
#: Durchmessers nicht führt: ``drill_hole`` und ``plug_hole`` nennen ihr Feld
#: genauso und meinen die Bohrung selbst. Heute steht genau eine Operation
#: darin; wer eine zweite baut, die auf einer Bohrung **sitzt**, trägt sie hier
#: ein — und wer sie vergisst, bekommt die Schemavorgabe und nicht eine falsche
#: Zahl.
HEAD_DIAMETER_OPS: Final[frozenset[str]] = frozenset({"countersink_hole"})

#: Operationen, deren ``diameter`` genau das gemessene Bohrungsmaß ändert.
#: Getrennt von ``HEAD_DIAMETER_OPS``: Dort wäre dasselbe Maß falsch, hier ist
#: es der einzige sichere Ausgangswert.
MEASURED_DIAMETER_OPS: Final[frozenset[str]] = frozenset({"resize_hole"})

#: Beide Körperarten teilen DrillParams, Flächenanker und lokalen Werkzeugkörper.
DRILL_OPERATIONS: Final[frozenset[str]] = frozenset({"drill_hole", "drill_brep_hole"})


def bore_step_of(
    document: Document,
    objects: Mapping[ObjectId, SceneObject],
    selected: FeatureRef,
    *,
    completed: Collection[OpId],
) -> Operation | None:
    """Der belegte ursprüngliche Bohrungsschritt einer einzelnen lebenden Bohrung.

    Die Rückgabe enthält **Schrittwerte**, keine heutigen Weltmaße. Auch nach
    Verschieben, Drehen oder Skalieren bleiben Position, Durchmesser und Tiefe
    im ursprünglichen Bezugsraum. Der Aufrufer ändert diesen Schritt über die
    bestehende historische Vorschau samt vollständiger Folgeauswertung.

    Die sichere Startmenge umfasst die beiden DrillParams-Zwillinge und ihre
    eindeutige Hohlraumkette. Danach sind nur reine Körpertransformationen,
    Umbenennung, Kopien und Senken belegt. Eine Kopie ist nur zulässig, wenn
    allein dieser Nachkomme lebt; mehrere Bohrungen desselben Erzeugers sind
    keine heimliche Gruppenwahl. Spätere Formänderungen wie resize_hole
    erhalten zwar gegebenenfalls created_by, belegen aber nicht mehr, dass
    die ursprünglichen Maße das gewählte Merkmal beschreiben. Sie und
    unbekannte Folgeschritte auf dem Abstammungsweg liefern deshalb None.

    Es wird kein Verlauf gerechnet und keine räumlich nächste Bohrung gewählt.
    Der Aufrufer übergibt Dokument und abgeschlossenen Ergebnisstand zusammen.
    """
    from app.core.perceive.relations import cavity_chain_state_at

    body = objects.get(selected.object_id)
    feature = body.features.get(selected.feature_id) if body is not None else None
    if body is None or feature is None or feature.kind not in {"hole", "cone"}:
        return None
    state = cavity_chain_state_at(feature, body.features, as_mesh_data(body.mesh))
    if state.touches_other and state.chain is None:
        return None
    sections = state.chain or (feature,)
    makers = {part.created_by for part in sections if part.kind == "hole"}
    if len(makers) != 1 or None in makers:
        return None
    maker = next(iter(makers))
    operations = tuple(
        entry for entry in sorted(document.ops, key=lambda entry: entry.id) if entry.id in completed
    )
    candidates = [entry for entry in operations if entry.id == maker]
    if len(candidates) != 1:
        return None
    step = candidates[0]
    if step.op not in DRILL_OPERATIONS or len(step.inputs) != 1:
        return None
    section_ids = {part.id for part in sections}
    if any(
        part.created_by == maker
        and part.kind in {"hole", "cone"}
        and (entry.id != body.id or part.id not in section_ids)
        for entry in objects.values()
        for part in entry.features.values()
    ):
        return None

    suffix = operations[operations.index(step) + 1 :]
    descendants = set(step.outputs)
    for operation in suffix:
        if descendants.intersection(operation.inputs):
            descendants.difference_update(operation.inputs)
            descendants.update(operation.outputs)
    if descendants.intersection(objects) != {selected.object_id}:
        return None

    # Zeitlich rückwärts: Eine Änderung am zurückgebliebenen Original nach
    # dem Kopieren gehört nicht automatisch zur ausgewählten Kopie.
    following = {
        "rename_object",
        "translate_object",
        "rotate_object",
        "scale_object",
        "mirror_object",
        "fit_to_size",
        "place_on_bed",
        "align_to_feature",
        "duplicate_object",
        "pattern",
        "countersink_hole",
    }
    wanted = {selected.object_id}
    for operation in reversed(suffix):
        if not wanted.intersection(operation.outputs):
            continue
        if operation.op not in following or len(operation.inputs) != 1:
            return None
        wanted.difference_update(operation.outputs)
        wanted.update(operation.inputs)
    return step if wanted.intersection(step.outputs) else None


def screw_for_bore(diameter: float) -> str | None:
    """Die Schraube, für die diese **gemessene** Bohrung ein Durchgangsloch ist.

    Die eine Zuordnung von einem Maß auf eine Normgröße, und deshalb steht sie
    hier einmal statt an jeder Stelle, die sie braucht. Zwei Schranken, beide
    aus derselben Zeile der Normteiltabelle und keine davon gegriffen:
    Unterhalb des **Nennmaßes** geht die Schraube nicht hindurch, oberhalb des
    **Durchgangslochs** ist die Bohrung weiter als das Normmaß für diese Größe.

    Die Bänder der Größen berühren sich nicht (M4 endet bei 4,50, M5 beginnt
    bei 5,00), es kann also höchstens eine Antwort geben. Und dazwischen wird
    nichts herbeigerundet: Wer keine bekommt, bekommt :func:`bore_advice` —
    genannt statt geraten (Regel 21). Zwei Konstanten, die dieselbe Frage
    verschieden beantworten, gäbe es damit auch nicht.

    Nicht zu verwechseln mit den Zuordnungen bei den Bausteinen
    (``PartSpec.at_hole_values``): Eine Einpressbuchse fragt, welche Größe die
    Bohrung *aufweitet*, ein Gewinde, welche noch *hineinpasst*. Das sind
    andere Fragen an dieselbe Tabelle, keine zweite Antwort auf diese.
    """
    # Spät importiert: ``knowledge`` kennt ``scene`` nicht, und andersherum soll
    # die Abhängigkeit nur dort entstehen, wo sie gebraucht wird.
    from app.core.knowledge import standards

    for size in standards.screw_sizes():
        entry = standards.screw(size)
        if entry.nominal <= diameter <= entry.clearance:
            return size
    return None


#: Welches Loch einer Schraube eine Bohrung sein kann: das Durchgangsloch
#: in einer der drei Reihen nach ISO 273 oder das Kernloch für ihr Gewinde.
BoreHole = Literal["fine", "medium", "coarse", "tap"]


@dataclass(frozen=True, slots=True)
class BoreMatch:
    """Eine Schraubengröße, zu deren Loch eine Bohrung passt — und welches Loch."""

    size: str
    hole: BoreHole


def bore_matches(low: float, high: float) -> tuple[BoreMatch, ...]:
    """Die Normlöcher, in deren Band das Maßintervall ``[low, high]`` fällt.

    **Für ein Maß mit Unsicherheit**, nicht für ein exaktes — das beantwortet
    :func:`screw_for_bore` mit einer einzigen Größe. Eine gemessene Bohrung
    trägt ein Intervall: Die Kreispassung hat einen Fehler, und zwischen den
    Ecken eines Vielecks liegen seine Seiten weiter innen
    (:func:`measured_interval`). Das Band einer Schraube reicht dabei

    * beim **Durchgangsloch** vom Nennmaß — darunter geht sie nicht hindurch —
      bis zur groben Reihe nach ISO 273. Welche Reihe gemeint ist, sagt der
      nächstgelegene der drei Werte;
    * beim **Kernloch** genau über das Tabellenmaß: Es muss im Intervall liegen.

    Mehrere Treffer sind eine Antwort und kein Fehler. 4,2 mm ist das feine
    Durchgangsloch einer M4 **und** das Kernloch einer M5; wer nur eines
    nennt, hat geraten (Regel 21). Die Reihenfolge ist die der Tabelle.
    """
    from app.core.knowledge import standards

    found: list[BoreMatch] = []
    centre = (low + high) / 2.0
    for size in standards.screw_sizes():
        entry = standards.screw(size)
        coarse = entry.clearance_coarse if entry.clearance_coarse is not None else entry.clearance
        if high >= entry.nominal - EPS_GEOM and low <= coarse + EPS_GEOM:
            series: list[tuple[float, BoreHole]] = [(entry.clearance, "medium")]
            if entry.clearance_fine is not None:
                series.append((entry.clearance_fine, "fine"))
            if entry.clearance_coarse is not None:
                series.append((entry.clearance_coarse, "coarse"))
            nearest = min(series, key=lambda item: abs(item[0] - centre))
            found.append(BoreMatch(size, nearest[1]))
        if low - EPS_GEOM <= entry.tap <= high + EPS_GEOM:
            found.append(BoreMatch(size, "tap"))
    return tuple(found)


def measured_interval(
    diameter: float, feature: Feature | None, status: MeasureStatus
) -> tuple[float, float]:
    """Das Intervall, in dem der Durchmesser einer Bohrung liegen kann.

    Die Quellen, die das Merkmal selbst belegt, und keine erfundene Toleranz:

    * ``fit_error`` ist der größte radiale Fehler der Kreispassung — auf
      beiden Seiten des Durchmessers doppelt;
    * ``radial_min`` und ``radial_max`` sind das Netzband der Wand, der
      kleinste und der größte Abstand ihrer Dreiecke zur Achse. Ein Vieleck
      mit Ecken auf dem Kreis hat seine Seiten weiter innen; welches der
      beiden Maße der Konstrukteur meinte, weiß niemand.

    Ein Vorgabemaß (``parameter``) und ein Wert ohne belegte Quelle bleiben
    ein Punkt: Für sie ist keine Messunsicherheit bekannt, und eine
    ausgedachte wäre eine Toleranz aus dem Nichts (Regel 7).
    """
    if feature is None or status.source not in ("fit", "facets"):
        return (diameter, diameter)
    low, high = diameter, diameter
    band = [feature.params.get("radial_min"), feature.params.get("radial_max")]
    for radius in band:
        if (
            isinstance(radius, (int, float))
            and not isinstance(radius, bool)
            and np.isfinite(radius)
            and radius > 0.0
        ):
            low, high = min(low, 2.0 * radius), max(high, 2.0 * radius)
    error = feature.params.get("fit_error")
    if isinstance(error, (int, float)) and not isinstance(error, bool) and np.isfinite(error):
        low, high = low - 2.0 * abs(error), high + 2.0 * abs(error)
    return (max(low, 0.0), high)


def _hole_title(hole: BoreHole) -> str:
    """Wie ein Normloch im Satz heißt."""
    titles = {
        "fine": tr("Durchgangsloch fein"),
        "medium": tr("Durchgangsloch mittel"),
        "coarse": tr("Durchgangsloch grob"),
        "tap": tr("Kernloch für Gewinde"),
    }
    return titles[hole]


def _matches_said(matches: Sequence[BoreMatch]) -> str:
    """Die Treffer als Aufzählung: „M4 (Durchgangsloch fein) oder M5 (Kernloch …)"."""
    named = [
        tr("{screw} ({hole})")
        .replace("{screw}", entry.size)
        .replace("{hole}", _hole_title(entry.hole))
        for entry in matches
    ]
    if len(named) == 1:
        return named[0]
    return (
        tr("{list} oder {last}")
        .replace("{list}", ", ".join(named[:-1]))
        .replace("{last}", named[-1])
    )


def bore_advice(
    diameter: float,
    *,
    ask: bool = True,
    measured: str | None = None,
    feature: Feature | None = None,
    features: Mapping[str, Feature] | None = None,
    mesh: MeshData | None = None,
    cavity: tuple[Feature, ...] | None = None,
    status: MeasureStatus | None = None,
    spec: OperationSpec | None = None,
) -> tuple[str, list[str]]:
    """Was zu dieser Bohrung zu sagen ist — und, wo nichts passt, zu fragen.

    **Der gemessene Durchmesser steht in beiden Fällen darin.** Er war der
    zweite Teil des gemeldeten Fehlers: Die Anwendung kannte ihn — er steht in
    ``feature.params["diameter"]`` — und schlug wortlos eine Größe vor, die
    nicht dazu passte. Wer ihn liest, sieht selbst, ob der Vorschlag stimmt.

    Die leere Antwortliste ist die Unterscheidung, und sie ist Absicht: Wo eine
    Größe passt, ist die Auskunft ein **Satz**; wo keine passt, eine **Frage**
    mit den beiden Nachbargrößen und einem Ausweg, der keine behauptet. Zu
    fragen, was ohnehin feststeht, wäre eine Rückfrage ohne Mehrdeutigkeit —
    und stumm zu bleiben, wo es zwei Möglichkeiten gibt, wäre Raten.

    Gedacht für ``ctx.ask`` und für den Hinweis über einem Dialog, wie
    ``question_for`` in ``perceive/matching.py``: Der Kern formuliert, der
    Aufrufer zeigt. Das Dezimaltrennzeichen bleibt dabei ein Punkt —
    lokalisiert wird in der Oberfläche.

    **Mit ``spec`` spricht der Satz vom Baustein des Dialogs**
    (``PartSpec.at_hole_advice``): über *Druckbares Gewinde* vom
    Innengewinde, das in die Bohrung passt, über der Einpressbuchse von der
    Buchse — jeweils die Größe, die der Dialog vorwählt. Ohne eigenen Satz
    bleibt der allgemeine über die Schraube, deren Durchgangsloch die Bohrung
    ist (die Senkung).
    """
    from app.core.perceive.actions import measure_explanation, measure_qualifier

    status = status or (
        measure_status(feature, "diameter")
        if feature is not None
        else MeasureStatus("unknown", available=bool(np.isfinite(diameter) and diameter > 0.0))
    )
    if not status.available:
        return str(measure_explanation(status)), [tr("Selbst eintragen")] if ask else []
    measured = measured if measured is not None else format_length(diameter, with_unit=False)
    qualifier = measure_qualifier(status)
    named_measure = f"{measured} mm" + (f" ({qualifier})" if qualifier is not None else "")
    if feature is not None and features is not None:
        from app.core.perceive import relations

        chain = cavity
        if chain is None:
            chain = (
                relations.cavity_chain_at(feature, features, mesh)
                if mesh is not None
                else relations.bore_and_widening_at(feature, features)
            )
        if chain is not None and len(chain) > 1 and chain[0].id != feature.id:
            return tr(
                "Diese Aufweitung misst {measure}. Die Schraubengröße richtet sich "
                "nach der engeren Bohrung."
            ).replace("{measure}", named_measure), []
    advice = _part_advice(spec, diameter, status)
    if advice is not None:
        return f"{tr('Bohrungsmaß: {measure}.').replace('{measure}', named_measure)} {advice}", []
    if status.source != "native":
        # **Eine Messung nennt eine Größe als Einschätzung** (Durchsicht
        # 0.5.0). Bis dahin sagte sie gar keine: An einer Netzbohrung von
        # 5,19 mm stand „nicht sicher bestimmt", obwohl das Maß samt seiner
        # Unsicherheit nur ins Band der M5 fällt — und die Website verspricht
        # genau diesen Satz für eine fremde STL. „Vermutlich" und die Herkunft
        # in Klammern halten die Grenze zur Konstruktionsangabe.
        low, high = measured_interval(diameter, feature, status)
        matches = bore_matches(low, high)
        if matches:
            said = tr("Bohrungsmaß: {measure}. Passt vermutlich zu {matches}.")
            said = said.replace("{measure}", named_measure).replace(
                "{matches}", _matches_said(matches)
            )
        else:
            said = tr(
                "Bohrungsmaß: {measure}. Eine passende Schraubengröße ist damit nicht sicher "
                "bestimmt."
            ).format(measure=named_measure)
        if not ask:
            return said, []
        return (
            f"{said} {tr('Zu welcher Schraube gehört sie?')}",
            [*_sizes_around(diameter, matches), tr("Selbst eintragen")],
        )
    size = screw_for_bore(diameter)
    if size is not None:
        # Ganze Sätze mit Platzhaltern statt zusammengesetzter Halbsätze: Wer
        # nur „das Durchgangsloch für" zu übersetzen bekommt, weiß nicht, was
        # danach steht — und in mancher Sprache steht es davor.
        said = tr("Diese Bohrung misst {measure} mm — das Durchgangsloch für {screw}.")
        if feature is not None and feature.params.get("through") is False:
            said = tr(
                "Diese Sackbohrung misst {measure} mm. Ihr Durchmesser bietet Platz für {screw}."
            )
        return said.replace("{measure}", measured).replace("{screw}", size), []
    if not ask:
        from app.core.knowledge import standards

        for near in standards.screw_sizes():
            nominal = standards.screw(near).nominal
            if diameter < nominal and round_display(diameter) >= nominal:
                return tr(
                    "Die Bohrung liegt knapp unter dem Nennmaß von {screw}. "
                    "Eine passende Größe ist nicht sicher zugeordnet."
                ).replace("{screw}", near), []
        return tr(
            "Diese Bohrung misst {measure} mm. Keine Normgröße ist eindeutig zugeordnet."
        ).replace("{measure}", measured), []
    asked = tr(
        "Diese Bohrung misst {measure} mm und passt zu keiner Normgröße. "
        "Zu welcher Schraube gehört sie?"
    )
    return (
        asked.replace("{measure}", measured),
        [*_sizes_around(diameter, ()), tr("Selbst eintragen")],
    )


def _part_advice(spec: OperationSpec | None, diameter: float, status: MeasureStatus) -> str | None:
    """Der eigene Bausteinsatz mit der Sicherheit der Maßquelle — oder ``None``."""
    if spec is None:
        return None
    from app.core.knowledge.parts.ops import part_of

    part = part_of(spec.name)
    if part is None or part.at_hole_advice is None:
        return None
    said = part.at_hole_advice(float(diameter))
    if said is None:
        return None
    if status.source != "native":
        return tr("Einschätzung anhand dieses Maßes: {advice}", advice=said)
    return str(said)


def advises_on_bores(spec: OperationSpec) -> bool:
    """Ob der Dialog dieser Operation zu einer angeklickten Bohrung einen
    Satz verdient (:func:`bore_advice`).

    Genau die Fälle, in denen aus dem gemessenen Durchmesser eine Größe folgt
    oder folgen sollte: die Senkung (der Kopf über die Schraube) und die
    Bausteine, die in der Bohrung sitzen (``at_hole_values``). Alle anderen
    Dialoge zeigen den Satz nicht — ein Hinweis, der überall steht, steht
    nirgends.
    """
    if spec.name in HEAD_DIAMETER_OPS:
        return True
    from app.core.knowledge.parts.ops import part_of

    part = part_of(spec.name)
    return part is not None and part.at_hole_values is not None


def _head_diameter(feature: Feature) -> float | None:
    """Der Senkkopf der Schraube, die durch diese gemessene Bohrung geht.

    Der Senkkopf (ISO 10642) und nicht der Zylinderkopf: Die Operation heißt
    *Senken* und macht Platz für einen Kopf, der bündig sitzt. Wo keine Größe
    passt, kommt nichts zurück — die Schemavorgabe ist dann ehrlicher als ein
    Kopf, den sich niemand ausgesucht hat.

    **Auch aus der groben Reihe**, wenn sie genau eine Größe nennt: Über
    einem Loch von 5,7 mm sagt der Hinweis „Passt vermutlich zu M5
    (Durchgangsloch grob)"; ein leeres Feld darunter widerspräche ihm.
    Ein Kernloch trägt keine Senkung — seine Schraube geht nicht hindurch.
    """
    diameter = feature.params.get("diameter")
    if diameter is None:
        return None
    size = screw_for_bore(float(diameter))
    if size is None:
        through = {
            entry.size
            for entry in bore_matches(float(diameter), float(diameter))
            if entry.hole != "tap"
        }
        size = next(iter(through)) if len(through) == 1 else None
    if size is None:
        return None
    from app.core.knowledge import standards

    return round(standards.screw(size).countersink, 4)


def _sizes_around(diameter: float, matches: Sequence[BoreMatch]) -> list[str]:
    """Die Größen, die für eine Bohrung infrage kommen — in der Reihenfolge der Tabelle.

    Die, zu deren Loch sie passt (``matches``), dazu je eine Nachbargröße
    darunter und darüber. Beide Nachbarn oder einer — an den Enden der Tabelle
    gibt es keine zweite Seite, und eine erfundene wäre schlechter als eine
    kurze Liste.

    **Die passende Größe gehört dazu.** Bis zur Durchsicht 0.5.0 nannte diese
    Stelle nur die Nachbarn, auch dort, wo sie für eine gemessene Bohrung
    fragte: An 5,19 mm standen M4 und M6 zur Wahl, die M5 nicht.
    """
    from app.core.knowledge import standards

    # Die Reihenfolge der Tabelle ist aufsteigend; die Bausteine rechnen seit je
    # damit (``size_for_insert`` nimmt die erste passende als die kleinste).
    sizes = standards.screw_sizes()
    below = [size for size in sizes if standards.screw(size).clearance < diameter]
    above = [size for size in sizes if standards.screw(size).nominal > diameter]
    wanted = {*below[-1:], *above[:1], *(entry.size for entry in matches)}
    return [size for size in sizes if size in wanted]


def _target_field(spec: OperationSpec) -> str:
    """Der Parameter, der eine Fläche als **Ziel** benennt statt als Ort — oder
    leer, wenn diese Operation keinen hat (§30.1, D14).

    Wie ``at_feature`` eine Kennung, aber kein Ersatz für die Position: die
    Skizze liegt woanders, die Extrusion reicht nur bis dorthin. Gefragt wird
    nach :attr:`~app.core.types.ParamSpec.targets_feature` und nicht nach dem
    Namen ``up_to`` — aus demselben Grund, der acht Zeilen tiefer schon einmal
    aufgeschrieben ist: Eine zweite Operation mit Zielfläche hätte ihr Feld
    sonst exakt so nennen müssen.
    """
    return next(
        (
            entry.name
            for entry in spec.params.spec()
            if entry.targets_feature and not entry.internal
        ),
        "",
    )


def _from_the_bore(spec: OperationSpec, feature: Feature, names: set[str]) -> dict[str, Any]:
    """Was der Baustein aus dem **gemessenen** Durchmesser dieser Bohrung macht.

    Der Docstring von :func:`values_for` sagt, dass die Größe eines Merkmals
    nicht in die Vorgaben gehört, und für eine Senkung stimmt das vollständig:
    Sie nimmt den Kopfdurchmesser der Schraube auf, nicht den der Bohrung, auf
    der sie sitzt. Für einen Baustein, der **in** die Bohrung gesetzt wird,
    stimmt es nicht — dort *ist* der gemessene Durchmesser die Bezugsgröße,
    weil er die Bohrung ersetzt statt auf ihr zu sitzen.

    Der Unterschied ist fachlich, und deshalb steht die Rechnung beim Baustein
    (``PartSpec.at_hole_values``) und nicht hier. Eine Einpressbuchse braucht
    die kleinste Größe, die die Bohrung *aufweitet*, ein Gewinde die größte,
    die noch *hineinpasst* — eine gemeinsame Formel wäre in einem der beiden
    Fälle falsch.

    **Was der Baustein nicht kennt, kommt nicht durch.** Gefiltert wird gegen
    das Parameterschema der Operation: Ein Vorschlag für einen Parameter, den
    es hier nicht gibt, wäre ein stiller Fehlschlag beim Öffnen des Dialogs.
    """
    if feature.kind != "hole":
        return {}
    diameter = feature.params.get("diameter")
    if diameter is None:
        return {}
    # Spät importiert: ``knowledge`` kennt ``scene`` nicht, und andersherum
    # soll die Abhängigkeit nur dort entstehen, wo sie gebraucht wird.
    from app.core.knowledge.parts.ops import part_of

    part = part_of(spec.name)
    if part is None or part.at_hole_values is None:
        return {}
    return {
        name: value for name, value in part.at_hole_values(float(diameter)).items() if name in names
    }


def values_for(
    spec: OperationSpec, feature: Feature, object_id: str | None = None
) -> dict[str, Any]:
    """Die Parameter, die dieses Merkmal für diese Operation vorschlägt.

    Nur, was das Merkmal sicher sagt: wo es ist und wohin es schaut. Nicht
    seine Größe — eine Senkung nimmt den Durchmesser des Schraubenkopfs, nicht
    den der Bohrung, auf der sie sitzt, und eine hilfsbereit eingetragene 5,2
    wäre dort eine falsche Zahl, die wie eine gemessene aussieht.

    **Der Kopf folgt trotzdem aus der Bohrung**, seit dem 25.08.2026: nicht als
    ihr Maß, sondern über die Schraube, die durch sie geht
    (:func:`screw_for_bore`). Aus 5,19 mm wird der Senkkopf der M5 und nicht
    5,19 — und wo keine Größe passt, bleibt das Feld auf seiner Vorgabe und
    :func:`bore_advice` sagt warum. Der Satz oben blieb richtig und deckte den
    Fall zu: Die Schemavorgabe im Feld gehört zu keiner Bohrung des Teils, und
    niemand sagte es.
    """
    names = {entry.name for entry in spec.params.spec()}
    # **Gefragt wird nach der Art, nicht nach dem Namen.** Bis zum 23.08.2026
    # stand hier ``if FEATURE_FIELD in names`` — also „heißt ein Feld
    # *at_feature*?". Damit fiel *An Merkmal ausrichten* durch: Ihre Felder
    # heißen ``feature`` und ``target``, und wer eine Fläche anklickte, bekam
    # bei einundzwanzig Operationen eine Vorbelegung und bei dieser ein leeres
    # Textfeld (gefunden von 3d-druck-33).
    #
    # Es war die zweite von zwei Stellen, die dieselbe Sache verschieden
    # fragten: ``scene/orphans.py`` geht nach ``kind == "feature"``, hier ging
    # es nach dem Namen. Zwei Raster, und eine Operation fiel durch beide.
    # Seit ``5f94f1d`` deklariert sie ihre Art; damit genügt eine Frage.
    feature_field = next(
        (entry for entry in spec.params.spec() if entry.kind in {"feature", "features"}),
        None,
    )
    # Ein Merkmalsfeld, das nur bestimmte Arten annimmt, nimmt einen Klick auf
    # eine andere nicht an (``ParamSpec.feature_kinds``): An einer Bohrung
    # lässt sich nichts öffnen, und die Öffnungen des Aushöhlens sind Flächen.
    if feature_field is not None and (
        feature_field.feature_kinds and feature.kind not in feature_field.feature_kinds
    ):
        feature_field = None
    if feature_field is not None and spec.name != "apply_texture":
        feature_values = {
            feature_field.name: (feature.id,) if feature_field.kind == "features" else feature.id,
            **_from_the_bore(spec, feature, names),
        }
        if spec.name in MEASURED_DIAMETER_OPS and feature.kind == "hole":
            diameter = feature.params.get("diameter")
            if isinstance(diameter, int | float) and "diameter" in names:
                # Der Zahleneditor zeigt passend gerundet, bewahrt aber einen
                # unangetasteten Kernwert vollständig. Hier vorher zu runden
                # würde genau diese sichere Anzeige umgehen und ein bloßes
                # Öffnen und Bestätigen zum Geometrieschritt machen.
                feature_values["diameter"] = float(diameter)
        return feature_values

    values: dict[str, Any] = {}
    # Die Textur bewahrt neben der Fläche auch die freie Rechteckplatzierung.
    # Eine Bohrung liefert deren Wickeldurchmesser, aber keinen ebenen Umriss.
    if spec.name == "apply_texture" and feature.kind == "face":
        values["face"] = feature.id
    target = _target_field(spec)
    if target and feature.kind == "face":
        # „Bis zu dieser Fläche" — die Kennung reicht, den Rahmen rechnet die
        # Auswertung daraus (app.core.sketch.planes). Nur planare Flächen: bis
        # zu einer Bohrung zu extrudieren hat keine Bedeutung.
        values[target] = f"{object_id}:{feature.id}" if object_id else feature.id
    if DIAMETER_FIELD in names and feature.kind == "hole":
        diameter = feature.params.get("diameter")
        if diameter is not None:
            values[DIAMETER_FIELD] = round(float(diameter), 4)
    if spec.name in HEAD_DIAMETER_OPS and "diameter" in names and feature.kind == "hole":
        # **Nur an einer Bohrung**, nicht an einem angeklickten Kegel: Der ist
        # eine vorhandene Senkung, und sein Durchmesser ist schon ein Kopfmaß —
        # daraus noch eine Schraube zu suchen hieße, dieselbe Zahl zweimal
        # durch die Tabelle zu schicken.
        head = _head_diameter(feature)
        if head is not None:
            values["diameter"] = head
    centre = vec3_or_none(feature.params.get("centre"))
    if centre is not None:
        for name, value in zip(POSITION, centre, strict=True):
            if name in names:
                values[name] = float(value)

    direction = vec3_or_none(feature.params.get("normal")) or vec3_or_none(
        feature.params.get("axis")
    )
    if direction is not None:
        for name, value in zip(NORMAL, direction, strict=True):
            if name in names:
                values[name] = float(value)
        axis = dominant_axis(direction)
        if axis is not None and "axis" in names and _allows(spec, "axis", axis):
            values["axis"] = axis

    _log.info("feature %s suggests %d parameter(s) for %s", feature.id, len(values), spec.name)
    return values


#: Die Registerwerte zu :data:`SIDE_NAMES`, in derselben Ordnung.
SIDE_KEYS: Final[tuple[tuple[str, str], ...]] = (
    ("right_side", "left_side"),
    ("back_side", "front_side"),
    ("top_side", "bottom_side"),
)


def side_of(direction: Vec3) -> tuple[str, TranslatableText]:
    """Registerwert und Name der Seite, in die ``direction`` am meisten zeigt.

    Ohne Schwelle: Gefragt wird nach einer von zwei **Gegenrichtungen**, und
    deren größte Komponente liegt auf derselben Achse mit umgekehrtem
    Vorzeichen — zwei Enden einer schrägen Bohrung heißen deshalb nie gleich.
    """
    best = max(range(3), key=lambda index: abs(float(direction[index])))
    which = 0 if float(direction[best]) > 0.0 else 1
    return SIDE_KEYS[best][which], SIDE_NAMES[best][which]


def dominant_axis(direction: Vec3) -> str | None:
    """``x``, ``y`` oder ``z``, wenn die Richtung wirklich eine ist —
    sonst ``None``."""
    length = sum(value * value for value in direction) ** 0.5
    if length <= 0.0:
        return None
    shares = [abs(value) / length for value in direction]
    best = max(range(3), key=lambda index: shares[index])
    return "xyz"[best] if shares[best] >= AXIS_CLARITY else None


def top_face(features: Mapping[str, Feature]) -> Feature | None:
    """Die oberste nach oben schauende Fläche eines Körpers.

    Sie ist die Antwort auf „wohin, wenn niemand gezeigt hat". Ohne diese
    Antwort war es der Ursprung: ``drill_hole`` öffnete auf X/Y/Z = 0,00, und
    ob das traf, hing daran, wo das Teil zufällig lag. Bei einer Platte um den
    Nullpunkt ging es gut; bei einem Körper, der auf dem Bett angeordnet ist —
    und das ist jede Druckvorbereitung — lag der Ursprung fünfundsechzig
    Millimeter daneben, und die Operation meldete hinterher, dass der Schnitt
    nichts abgetragen hat. Ein richtiger Hinweis, eine Operation zu spät.

    Gewählt wird die höchste; bei gleicher Höhe die größere. Die höchste,
    weil eine Bohrung von oben kommt, und nicht die größte, weil das bei
    einem Deckel mit Kragen der Boden wäre.
    """
    candidates = [entry for entry in features.values() if faces_up(entry)]
    if not candidates:
        return None

    def rank(entry: Feature) -> tuple[float, float]:
        centre = vec3_or_none(entry.params.get("centre"))
        height = centre[2] if centre is not None else float("-inf")
        area = entry.params.get("area")
        return (height, float(area) if isinstance(area, int | float) else 0.0)

    return max(candidates, key=rank)


def values_for_object(spec: OperationSpec, features: Mapping[str, Feature]) -> dict[str, Any]:
    """Was ein Körper ohne angeklicktes Merkmal über die Position sagt.

    Dieselbe Herleitung wie bei einem gewählten Merkmal — es wird nur eines
    dafür gewählt, statt zu fragen. Das hält die zwei Wege auf einer Rechnung:
    was hier herauskommt, ließe sich durch einen Klick auf dieselbe Fläche
    genauso erzeugen.

    Die Kennung des Merkmals wird dabei **nicht** eingetragen. Ein
    ``at_feature``, das niemand gewählt hat, wäre eine Behauptung über eine
    Absicht; eine Position ist ein Vorschlag, den man im Feld sieht und
    ändern kann.

    **Ein Erzeuger bekommt hier nichts** (RM-390). Er verbraucht keinen
    Körper, und ein gewählter Körper sagt ihm nicht, wohin: Zylinder anlegen,
    anklicken, *Quader anlegen* — der Quader saß auf dem Zylinder, ohne dass
    jemand eine Fläche gezeigt hatte. Er entsteht auf dem Bett; auf eine Fläche
    kommt er nur, wenn eine gewählt ist (:func:`seat_on_face`).
    """
    if spec.consumes == 0:
        return {}
    face = top_face(features)
    if face is None:
        return {}
    values = values_for(spec, face)
    from app.core.knowledge.parts.ops import placement_fields

    values.pop(placement_fields(spec.params)[FEATURE_FIELD], None)
    for entry in spec.params.spec():
        if entry.kind in {"feature", "features"}:
            values.pop(entry.name, None)
    target = _target_field(spec)
    if target:
        values.pop(target, None)
    return values


def seats_on(spec: OperationSpec, feature: Feature) -> bool:
    """Ob dieser Erzeuger auf diese gewählte Fläche gesetzt wird (RM-390).

    Ein Erzeuger ohne Eingang, mit eigener Position und Richtung und ohne
    Merkmalsfeld — die freistehenden Bausteine benennen ihre Stelle über
    ``at_features`` und gehen den Weg der Platzierung —, auf einer ebenen
    Fläche mit Mitte und Richtung. Eine Bohrung oder Kante trägt keinen
    Körper; an ihr entsteht er auf dem Bett, wie ohne Auswahl.
    """
    entries = spec.params.spec()
    names = {entry.name for entry in entries}
    normal = vec3_or_none(feature.params.get("normal"))
    planar = feature.kind == "face" and normal is not None and math.hypot(*normal) > EPS_GEOM
    curved = (
        "surface_anchor" in names
        and feature.kind in {"hole", "pin", "cone", "sphere", "torus", "fillet", "curved_face"}
        and bool(feature.face_indices)
    )
    return (
        spec.consumes == 0
        and not spec.takes_whole_scene
        and set(POSITION) <= names
        and set(NORMAL) <= names
        and not any(entry.kind in {"feature", "features"} for entry in entries)
        and vec3_or_none(feature.params.get("centre")) is not None
        and (planar or curved)
    )


def seat_on_face(
    spec: OperationSpec, feature: Feature, entered: Mapping[str, Any], profile: Profile
) -> dict[str, float] | None:
    """Position und Richtung eines Erzeugers auf einer ausdrücklich gewählten Fläche.

    Die Grundfläche des Körpers liegt in der Ebene der Fläche, seine Hochachse
    zeigt in ihre Richtung, sein Bezugspunkt sitzt auf ihrer Mitte. **Und
    nichts liegt unter dem Bett** (RM-390): An einer Seitenfläche dehnt sich
    ein Körper um die Mitte der Fläche nach oben und unten aus, und ein Quader
    stand mit z = -4,5 halb darunter. Reicht er unter das Bett, rückt er in der
    Ebene der Fläche nach oben, bis sein tiefster Punkt auf dem Bett steht — er
    bleibt auf der Fläche, nur höher.

    Gemessen wird am Werkzeug, das Vorschau und Platzierung zeigen
    (:func:`prepare_tool`), in der Lage, die die Operation selbst baut, mit den
    Maßen aus ``entered``; was dort fehlt, nimmt die Vorgabe.

    ``None``, wenn der Körper unter das Bett reichte und in der Ebene nicht
    steigen kann: Eine Fläche, die vor allem nach oben oder unten schaut, hat
    keine Steigung, auf der er wandern könnte — etwa die Unterseite eines Teils
    auf dem Bett. Ohne Werkzeug (``thread_exact``) bleibt es bei Mitte und
    Richtung; einen Rest unter dem Bett meldet dann der Endstand
    (``arrange.below_bed``). Leer, wo :func:`seats_on` nein sagt.
    """
    if not seats_on(spec, feature) or feature.kind != "face":
        return {}
    centre = vec3_or_none(feature.params.get("centre"))
    raw = vec3_or_none(feature.params.get("normal"))
    assert centre is not None and raw is not None  # von seats_on belegt
    length = math.hypot(*raw)
    normal = tuple(float(value) / length for value in raw)
    seated: dict[str, float] = {
        **{name: float(value) for name, value in zip(POSITION, centre, strict=True)},
        **dict(zip(NORMAL, normal, strict=True)),
    }
    lowest = _lowest_point(spec, {**entered, **seated}, profile)
    if lowest is None or lowest >= -EPS_GEOM:
        return seated
    if dominant_axis((normal[0], normal[1], normal[2])) == "z":
        return None
    # Die Steigung der Ebene: die Hochachse ohne ihren Anteil längs der
    # Richtung. Ihr z-Anteil ist ihr Längenquadrat, und um ``-lowest`` zu
    # steigen, braucht es genau ``-lowest / |up|²`` von ihr.
    up = np.array((0.0, 0.0, 1.0)) - normal[2] * np.asarray(normal)
    shift = up * (-lowest / float(up @ up))
    for index, name in enumerate(POSITION):
        seated[name] += float(shift[index])
    return seated


def _lowest_point(spec: OperationSpec, values: Mapping[str, Any], profile: Profile) -> float | None:
    """Die Höhe des tiefsten Punkts, den die Operation mit diesen Werten baut.

    ``None``, wo es kein Werkzeug gibt oder die Werte es nicht zulassen — ein
    Feld außerhalb seiner Grenzen sagt der Dialog selbst.
    """
    from app.core.errors import AppError
    from app.core.registry.params import validate

    try:
        tool = prepare_tool(spec, values, profile)
        checked: Any = validate(spec.params, values)
    except AppError:
        return None
    if spec.name in _surface_primitives():
        from app.core.geom.primitive_ops import placement_transform
        from app.core.geom.transform import apply

        placed = apply(tool.mesh, np.asarray(placement_transform(checked)))
    elif spec.name == "create_label":
        from app.core.geom.label_ops import place

        placed = place(
            tool.mesh,
            (float(checked.x), float(checked.y), float(checked.z)),
            (float(checked.nx), float(checked.ny), float(checked.nz)),
        )
    else:
        return None
    vertices = np.asarray(placed.raw.vertices)
    return float(vertices[:, 2].min()) if len(vertices) else None


def faces_up(feature: Feature) -> bool:
    """Liegt diese Fläche flach und schaut nach oben?

    Nicht bloß flach — das hat diese Funktion früher gefragt, und es war zu
    großzügig: die Decke eines Hohlraums ist auch flach, und sie zeigt nach
    unten. Als Höhe einer Öffnung gewählt, baute sie einen Deckel ins Innere
    der Box, auf 26,9 von 30 Millimetern, ohne ein Wort — denn ein Schnitt
    unterhalb dieser Ebene trifft ja die Wand, also sah für keinen der
    folgenden Schritte etwas falsch aus.

    Alles, was eine Öffnung verschließt, greift von ihr nach unten: die
    Platte sitzt auf dem Rand, der Kragen geht in den Hohlraum. Eine Fläche,
    die nach unten schaut, bräuchte all das gespiegelt — und das auf die
    Vermutung zu bauen, dass jemand das meinte, ist schlechter, als zu sagen,
    welche Fläche gewollt ist.
    """
    normal = vec3_or_none(feature.params.get("normal"))
    return normal is not None and dominant_axis(normal) == "z" and normal[2] > 0.0


def _allows(spec: OperationSpec, name: str, value: str) -> bool:
    """Ist das eine der Auswahlmöglichkeiten, die der Parameter anbietet?"""
    for entry in spec.params.spec():
        if entry.name == name:
            return not entry.choices or value in entry.choices
    return False


@dataclass(frozen=True, slots=True)
class EdgeReference:
    """Eine echte gerade Randkante und ihr signierter Lotabstand in Millimetern."""

    id: str
    start: Vec3
    end: Vec3
    inward: Vec3
    distance: float = 0.0
    kind: str = "outer"


@dataclass(frozen=True, slots=True)
class CentreReference:
    """Erkannte Mitte und U/V von ihr zum Ziel in der gewählten Flächenebene."""

    feature_id: str
    point: Vec3
    offset: Point2
    distance: float


@dataclass(frozen=True, slots=True)
class SurfacePlacement:
    """Eine Platzierungsabsicht, kein Dokumentzustand und keine gerundete Anzeige."""

    point: Vec3
    normal: Vec3
    frame: PlaneFrame
    planar: bool
    face_indices: tuple[int, ...]
    edges: tuple[EdgeReference, ...]
    centres: tuple[CentreReference, ...]


@dataclass(frozen=True, slots=True)
class PreparedSurface:
    """Einmal vorbereitete Originalfläche für beliebig viele Punktbewegungen.

    Die GEOS-Fläche einschließlich innerer Ringe ist unveränderlich; ihr
    vorbereiteter Suchindex gehört zum Kontext. Weder Triangulation noch
    Featureerkennung wird bei einer Mausbewegung wiederholt.
    """

    frame: PlaneFrame
    planar: bool
    face_indices: tuple[int, ...]
    edges: tuple[EdgeReference, ...]
    centres: tuple[tuple[str, Vec3], ...]
    area: BaseGeometry


@dataclass(frozen=True, slots=True)
class PlacementTool:
    """Einmal vorbereiteter Werkzeugkörper und sein Bezug zum gewählten Merkmal."""

    mesh: MeshData
    selected_offset: Vec3 | None = None
    feature_id: str = ""
    addition: MeshData | None = None
    outward_axis: Vec3 | None = None
    angle: float | None = None
    position_dependent_axis: bool = False


@dataclass(frozen=True, slots=True)
class SurfaceBinding:
    """Aktuell aufgelöste Lage, Cachebezug und erst nach Erfolg zu speichernde Antworten."""

    values: Mapping[str, Any]
    context: Mapping[str, Any]
    answers: Mapping[str, Any]
    prepared: PreparedSurface | None = None
    placed: SurfacePlacement | None = None
    source_id: ObjectId | None = None


def clear_surface_binding(spec: OperationSpec) -> dict[str, Any]:
    """Den gespeicherten Flächenbezug ausdrücklich lösen; die Ortswerte bleiben."""
    from app.core.knowledge.parts.ops import placement_fields

    names = placement_fields(spec.params)
    declared = {field.name for field in spec.params.spec()}
    return {
        names[name]: ""
        for name in ("surface_target", "surface_anchor")
        if names.get(name) in declared
    }


def _surface_feature(source: SceneObject, indices: Sequence[int]) -> Feature | None:
    """Nur ein eindeutiger erkannter Träger der gewählten Originaldreiecke."""
    wanted = set(indices)
    candidates = [
        entry
        for entry in source.features.values()
        if wanted and wanted.issubset(entry.face_indices)
    ]
    return candidates[0] if len(candidates) == 1 else None


def surface_at_feature(
    source: SceneObject,
    feature: Feature,
    *,
    point: Vec3 | None = None,
    cancelled: CancelToken | None = None,
) -> SurfacePlacement:
    """Ein echter Punkt auf dem gewählten ebenen oder gekrümmten Träger.

    Ein vorhandener Viewporttreffer hat Vorrang. Ohne Treffer wird die
    Flächenmitte genommen, wenn sie auf Material liegt; sonst ein Punkt auf
    dem zur Mitte nächsten Originaldreieck. Die Vorschau zeigt diesen Ansatz.
    """
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    mesh = as_mesh_data(source.mesh)
    indices = np.asarray(feature.face_indices, dtype=np.int64)
    if not len(indices) or int(indices.min()) < 0 or int(indices.max()) >= len(mesh.raw.faces):
        raise _reference_error()
    triangles = np.asarray(mesh.raw.triangles)[indices]
    centres = triangles.mean(axis=1)
    centre = point or vec3_or_none(feature.params.get("centre")) or _vec(centres.mean(axis=0))
    from trimesh.triangles import closest_point

    closest = cast(Callable[[np.ndarray, np.ndarray], np.ndarray], closest_point)
    best = float("inf")
    nearest = np.asarray(centre, dtype=np.float64)
    index = int(indices[0])
    for offset in range(0, len(triangles), PICK_TRIANGLE_BLOCK):
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        block = triangles[offset : offset + PICK_TRIANGLE_BLOCK]
        candidates = closest(block, np.broadcast_to(centre, (len(block), 3)))
        distances = np.linalg.norm(candidates - centre, axis=1)
        chosen = int(np.argmin(distances))
        if distances[chosen] < best:
            best = float(distances[chosen])
            nearest = candidates[chosen]
            index = int(indices[offset + chosen])
    if point is not None and best > MAX_FACET_SAG + EPS_GEOM:
        raise _placement_error()
    prepared = prepare_surface(mesh, index, source.features)
    target = nearest
    normal = np.asarray(prepared.frame.normal)
    target -= dot3(target - prepared.frame.origin, normal) * normal
    try:
        placed = at_point(prepared, _vec(target))
    except ValidationError:
        if point is not None:
            raise
        placed = at_point(prepared, _vec(mesh.raw.triangles[index].mean(axis=0)))
    if not prepared.planar and source.kind == "brep":
        from app.core.brep.canonical import projected_surface_point
        from app.core.brep.kernel import Solid
        from app.core.sketch.planes import frame_of

        if isinstance(source.mesh, Solid):
            native = source.mesh.faces_of_triangles((index,))
            if len(native) == 1:
                projected = projected_surface_point(
                    source.mesh.faces()[native[0]], point or placed.point
                )
                if projected is not None:
                    location, outward = projected
                    placed = replace(
                        placed, point=location, normal=outward, frame=frame_of(outward, location)
                    )
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    return placed


def bound_surface_values(
    spec: OperationSpec, source: SceneObject, placement: SurfacePlacement
) -> dict[str, Any]:
    """Einen Flächentreffer mit seinen wirklichen Bezugskanten dauerhaft speichern.

    Die beiden Abstände bleiben gewöhnliche mm-Parameter und dürfen Ausdrücke
    tragen. Die Beschreibung speichert Koordinaten und den belegten Körperrahmen,
    niemals die vergängliche Nummer einer Dreieckskante.
    """
    from app.core.knowledge.parts.ops import placement_fields

    fields = placement_fields(spec.params)
    if fields.get("surface_anchor") not in {entry.name for entry in spec.params.spec()}:
        raise _reference_error()
    if not np.isfinite((*placement.point, *placement.normal)).all():
        raise _placement_error()
    feature = _surface_feature(source, placement.face_indices)
    mesh = as_mesh_data(source.mesh)
    vertices = np.asarray(mesh.raw.triangles)[list(placement.face_indices)].reshape(-1, 3)
    if not len(vertices):
        raise _placement_error()
    centre = (vec3_or_none(feature.params.get("centre")) if feature is not None else None) or _vec(
        (vertices.min(axis=0) + vertices.max(axis=0)) / 2.0
    )
    record = {
        "version": 1,
        "object": source.id,
        "point": placement.point,
        "normal": placement.normal,
        "centre": centre,
        "frame": source.frame or IDENTITY_FRAME,
        "planar": placement.planar,
        "edges": [
            {"start": edge.start, "end": edge.end, "inward": edge.inward, "kind": edge.kind}
            for edge in placement.edges
        ],
    }
    if feature is not None and feature.kind in {"hole", "pin", "sphere"}:
        radius = feature.params.get("radius")
        if radius is None and isinstance(feature.params.get("diameter"), int | float):
            radius = float(feature.params["diameter"]) / 2.0
        if isinstance(radius, int | float) and math.isfinite(radius) and radius > EPS_GEOM:
            record["radius"] = float(radius)
            if feature.kind in {"hole", "pin"}:
                axis = vec3_or_none(feature.params.get("axis"))
                if axis is not None:
                    record["axis"] = axis
    values = surface_values(spec, placement, source=source)
    values[fields["surface_target"]] = f"{source.id}:{feature.id}" if feature is not None else ""
    values[fields["surface_anchor"]] = json.dumps(record, ensure_ascii=False, separators=(",", ":"))
    for index in range(2):
        values[fields[f"surface_distance_{index + 1}"]] = (
            placement.edges[index].distance if index < len(placement.edges) else 0.0
        )
    return values


def _surface_record(text: Any) -> dict[str, Any]:
    """Fremde Projektdaten nur als begrenzte, endliche Geometriebeschreibung lesen."""
    try:
        if not isinstance(text, str) or len(text) > 65_536:
            raise ValueError
        record = json.loads(text)
        if (
            not isinstance(record, dict)
            or type(record.get("version")) is not int
            or record["version"] != 1
        ):
            raise ValueError
        if not isinstance(record.get("object"), str) or not record["object"]:
            raise ValueError
        for key in ("point", "normal", "centre"):
            if vec3_or_none(record.get(key)) is None or not np.isfinite(record[key]).all():
                raise ValueError
        if math.hypot(*record["normal"]) <= EPS_GEOM:
            raise ValueError
        frame = np.asarray(record.get("frame"), dtype=np.float64)
        if inverse_affine(frame) is None:
            raise ValueError
        if "axis" in record and (
            vec3_or_none(record["axis"]) is None
            or not np.isfinite(record["axis"]).all()
            or math.hypot(*record["axis"]) <= EPS_GEOM
        ):
            raise ValueError
        if not isinstance(record.get("planar"), bool):
            raise ValueError
        if "radius" in record and (
            not isinstance(record["radius"], int | float)
            or not math.isfinite(record["radius"])
            or record["radius"] <= EPS_GEOM
        ):
            raise ValueError
        edges = record.get("edges")
        if not isinstance(edges, list) or len(edges) > 2:
            raise ValueError
        for edge in edges:
            if not isinstance(edge, dict) or edge.get("kind") not in {"outer", "inner", "axis"}:
                raise ValueError
            for key in ("start", "end", "inward"):
                if vec3_or_none(edge.get(key)) is None or not np.isfinite(edge[key]).all():
                    raise ValueError
            if (
                math.hypot(*edge["inward"]) <= EPS_GEOM
                or math.dist(edge["start"], edge["end"]) <= EPS_GEOM
            ):
                raise ValueError
        return record
    except (ValueError, TypeError, OverflowError, np.linalg.LinAlgError) as error:
        raise _reference_error() from error


def _triangle_under(
    mesh: MeshData, indices: np.ndarray, point: np.ndarray, cancelled: CancelToken
) -> int | None:
    """Das Dreieck aus ``indices``, auf dem ``point`` liegt — ``None``, wenn keines.

    „Liegt“ mit derselben Grenze wie ein angeklickter Punkt in
    :func:`surface_at_feature`: höchstens ``MAX_FACET_SAG`` daneben.
    """
    if not len(indices):
        return None
    from trimesh.triangles import closest_point

    closest = cast(Callable[[np.ndarray, np.ndarray], np.ndarray], closest_point)
    triangles = np.asarray(mesh.raw.triangles)[np.asarray(indices, dtype=np.int64)]
    best, found = float("inf"), None
    for offset in range(0, len(triangles), PICK_TRIANGLE_BLOCK):
        cancelled.raise_if_cancelled()
        block = triangles[offset : offset + PICK_TRIANGLE_BLOCK]
        candidates = closest(block, np.broadcast_to(point, (len(block), 3)))
        distances = np.linalg.norm(candidates - point, axis=1)
        chosen = int(np.argmin(distances))
        if distances[chosen] < best:
            best, found = float(distances[chosen]), int(indices[offset + chosen])
    return found if best <= MAX_FACET_SAG + EPS_GEOM else None


def _shares_its_span(edge: EdgeReference, start: np.ndarray, end: np.ndarray) -> bool:
    """Ob ``edge`` entlang ihrer Richtung die Strecke von ``start`` bis ``end`` überdeckt."""
    along = np.asarray(edge.end, dtype=np.float64) - np.asarray(edge.start, dtype=np.float64)
    length = math.hypot(*along)
    if length <= EPS_GEOM:
        return False
    along /= length
    low, high = sorted((dot3(edge.start, along), dot3(edge.end, along)))
    first, second = sorted((dot3(start, along), dot3(end, along)))
    return min(high, second) - max(low, first) > -EPS_GEOM


def _bound_choice(
    source: SceneObject,
    candidates: Sequence[EdgeReference],
    *,
    ask: AskFn,
    announce: Callable[[Any], None] | None,
    cancelled: CancelToken,
) -> EdgeReference:
    """Mehrere geometrisch passende Kanten zeigt derselbe vorhandene Frageweg."""
    from app.core.scene.edge_binding import EdgeTarget

    cancelled.raise_if_cancelled()
    if not candidates:
        raise _reference_error()
    if len(candidates) == 1:
        return candidates[0]
    tokens = [str(index + 1) for index in range(len(candidates))]
    targets = tuple(
        EdgeTarget(
            token,
            source.id,
            (edge.start, edge.end),
            _vec((np.asarray(edge.start) + edge.end) / 2.0),
            math.dist(edge.end, edge.start),
            False,
            True,
        )
        for token, edge in zip(tokens, candidates, strict=True)
    )
    question = tr("Mehrere Kanten passen zum gespeicherten Bezug. Welche Kante ist gemeint?")
    if announce is not None:
        announce(targets)
    try:
        chosen = ask(question, tokens)
        cancelled.raise_if_cancelled()
        if chosen not in tokens:
            raise AmbiguityError(question, tuple(tokens))
        return candidates[tokens.index(chosen)]
    finally:
        if announce is not None:
            announce(())


def bind_surface(
    spec: OperationSpec,
    values: Mapping[str, Any],
    objects: Mapping[ObjectId, SceneObject],
    hashes: Mapping[ObjectId, str],
    *,
    ask: AskFn,
    announce: Callable[[Any], None] | None,
    cancelled: CancelToken,
) -> SurfaceBinding:
    """Die gespeicherte Fläche vor dem Verbrauchercache gegen den aktuellen Träger binden."""
    from app.core.knowledge.parts.ops import normal_fields, placement_fields
    from app.core.perceive.features import EPS_ANGLE

    fields = placement_fields(spec.params)
    text = values.get(fields["surface_anchor"], "")
    if not text:
        return SurfaceBinding(values, {}, {})
    cancelled.raise_if_cancelled()
    record = _surface_record(text)
    named = str(values.get(fields["surface_target"], ""))
    feature = None
    identifier = record["object"]
    if named:
        try:
            reference = FeatureRef.parse(named)
        except ValueError as error:
            raise _reference_error() from error
        identifier = reference.object_id
    source = objects.get(identifier)
    if source is None:
        raise _reference_error()
    if named:
        feature = source.features.get(reference.feature_id)
        if feature is None:
            raise _reference_error()
    mesh = as_mesh_data(source.mesh)
    inverse = inverse_affine(np.asarray(record["frame"]))
    if inverse is None:
        raise _reference_error()
    matrix = composed(np.asarray(source.frame or IDENTITY_FRAME), inverse)

    def point(value: Any) -> np.ndarray:
        return cast(np.ndarray, moved_points(np.asarray([value]), matrix)[0])

    inverse = inverse_affine(matrix)
    if inverse is None:
        raise _reference_error()
    normal = turned(np.asarray(record["normal"]), inverse.T)
    normal /= math.hypot(*normal)
    previous_point = point(record["point"])
    indices = (
        tuple(feature.face_indices) if feature is not None else tuple(range(len(mesh.raw.faces)))
    )
    if not indices:
        raise _reference_error()
    answers: dict[str, Any] = {}
    changed_reference = False
    if record["planar"]:
        normals = np.asarray(mesh.raw.face_normals)[list(indices)]
        parallel = np.asarray(indices)[
            projected_along(normals, normal) >= exact_cos_degrees(EPS_ANGLE)
        ]
        patches: list[PreparedSurface] = []
        covered: set[int] = set()
        # **Gewachsen wird vom gespeicherten Punkt aus, wie beim Setzen**
        # (Fensterabnahme 04.10.2026). Eine eingelesene Fläche ist nur bis auf
        # Gleitkommaspuren eben, und welche Dreiecke dazugehören, hängt dann am
        # Dreieck, von dem aus gewachsen wird. Vom ersten der Liste aus fand die
        # Bindung am *Wedge-Lock* zwei Teilflächen statt der gesetzten, fragte
        # nach einer Kante und scheiterte an jeder Antwort.
        start = _triangle_under(mesh, parallel, previous_point, cancelled)
        if start is not None:
            under = prepare_surface(mesh, start, source.features)
            if under.planar:
                patches.append(under)
                covered.update(int(index) for index in parallel)
        for triangle in parallel:
            cancelled.raise_if_cancelled()
            if int(triangle) not in covered:
                prepared = prepare_surface(mesh, int(triangle), source.features)
                if prepared.planar:
                    patches.append(prepared)
                    covered.update(prepared.face_indices)
        if not patches:
            raise _reference_error()
        if len(patches) > 1:
            exact = [
                entry
                for entry in patches
                if abs(dot3(previous_point - entry.frame.origin, normal)) <= EPS_GEOM
            ]
            if len(exact) == 1:
                patches = exact
            else:
                candidates = [
                    EdgeReference(
                        str(index),
                        entry.frame.origin,
                        _vec(np.asarray(entry.frame.origin) + entry.frame.x_axis),
                        entry.frame.y_axis,
                    )
                    for index, entry in enumerate(patches)
                ]
                chosen = _bound_choice(
                    source, candidates, ask=ask, announce=announce, cancelled=cancelled
                )
                patches = [patches[int(chosen.id)]]
                changed_reference = True
        prepared = patches[0]
        chosen_edges: list[EdgeReference] = []
        for saved in record["edges"]:
            direction = turned(np.asarray(saved["end"]) - saved["start"], matrix)
            inward = np.cross(prepared.frame.normal, direction)
            if dot3(inward, turned(np.asarray(saved["inward"]), matrix)) < 0.0:
                inward = -inward
            inward /= math.hypot(*inward)
            candidates = [
                edge
                for edge in prepared.edges
                if edge.kind == saved["kind"]
                and dot3(edge.inward, inward) >= exact_cos_degrees(EPS_ANGLE)
            ]
            coincident = [
                edge
                for edge in candidates
                if abs(dot3(np.asarray(edge.start) - point(saved["start"]), inward)) <= EPS_GEOM
            ]
            if len(coincident) > 1:
                # **Zwei Stücke derselben Geraden sind zwei Kanten**
                # (Fensterabnahme 04.10.2026): Links und rechts einer
                # Aussparung liegt die Vorderkante zweimal auf einer Linie.
                # Gespeichert ist eines — das, dessen Strecke die
                # gespeicherte überdeckt.
                coincident = [
                    edge
                    for edge in coincident
                    if _shares_its_span(edge, point(saved["start"]), point(saved["end"]))
                ]
            if len(coincident) == 1:
                candidates = coincident
            changed_reference = changed_reference or len(candidates) > 1
            chosen_edges.append(
                _bound_choice(source, candidates, ask=ask, announce=announce, cancelled=cancelled)
            )
        target = previous_point - dot3(previous_point - prepared.frame.origin, normal) * normal
        if len(chosen_edges) == 2:
            rows = _reference_rows(prepared.frame, chosen_edges)
            if not _independent(prepared.frame, chosen_edges):
                raise _reference_error()
            offsets = [
                float(values.get(fields[f"surface_distance_{index + 1}"], 0.0))
                + dot3(np.asarray(edge.start) - prepared.frame.origin, edge.inward)
                for index, edge in enumerate(chosen_edges)
            ]
            uv = _solved_distances(rows, offsets)
            target = (
                np.asarray(prepared.frame.origin)
                + uv[0] * np.asarray(prepared.frame.x_axis)
                + uv[1] * np.asarray(prepared.frame.y_axis)
            )
        elif chosen_edges:
            edge = chosen_edges[0]
            distance = float(values.get(fields["surface_distance_1"], 0.0))
            target += (distance - dot3(target - edge.start, edge.inward)) * np.asarray(edge.inward)
        if values.get("surface_seat") == "centred":
            from app.core.sketch.planes import to_world

            middle = prepared.area.centroid
            target = np.asarray(to_world(prepared.frame, (float(middle.x), float(middle.y))))
        placed = at_point(prepared, _vec(target), references=chosen_edges)
        if changed_reference:
            updated = bound_surface_values(spec, source, placed)
            answers = {
                fields[name]: updated[fields[name]] for name in ("surface_anchor", "surface_target")
            }
    else:
        if values.get("surface_seat") == "centred" and feature is not None:
            placed = surface_at_feature(source, feature, cancelled=cancelled)
        else:
            placed = _bound_curved_surface(
                source, mesh, indices, feature, record, matrix, normal, cancelled
            )
        prepared = prepare_surface(mesh, placed.face_indices[0], source.features)
    resolved = dict(values)
    resolved.update(zip((fields[name] for name in POSITION), placed.point, strict=True))
    resolved.update(zip(normal_fields(spec.params), placed.normal, strict=True))
    if fields[FEATURE_FIELD] in resolved:
        resolved[fields[FEATURE_FIELD]] = ""
    cancelled.raise_if_cancelled()
    return SurfaceBinding(
        resolved,
        {
            "#surface_binding": (
                hashes.get(source.id, ""),
                placed.point,
                placed.normal,
                tuple((edge.start, edge.end, edge.inward) for edge in placed.edges),
            )
        },
        answers,
        prepared,
        placed,
        source.id,
    )


def _bound_curved_surface(
    source: SceneObject,
    mesh: MeshData,
    indices: Sequence[int],
    feature: Feature | None,
    record: Mapping[str, Any],
    matrix: np.ndarray,
    normal: np.ndarray,
    cancelled: CancelToken,
) -> SurfacePlacement:
    """Den gespeicherten Tangentenpunkt auf seinen aktuellen gekrümmten Träger legen."""
    from app.core.geom.mesh import ray_hits_batch
    from app.core.sketch.planes import frame_of

    vertices = np.asarray(mesh.raw.triangles)[list(indices)].reshape(-1, 3)
    centre = (vec3_or_none(feature.params.get("centre")) if feature is not None else None) or _vec(
        (vertices.min(axis=0) + vertices.max(axis=0)) / 2.0
    )
    local_offset = np.asarray(record["point"]) - record["centre"]
    offset = turned(local_offset, matrix)
    if feature is not None and "radius" in record:
        radius = feature.params.get("radius")
        if radius is None and isinstance(feature.params.get("diameter"), int | float):
            radius = float(feature.params["diameter"]) / 2.0
        if isinstance(radius, int | float):
            if feature.kind == "sphere":
                old_span = math.hypot(*local_offset)
                scale = math.hypot(*offset) / old_span if old_span > EPS_GEOM else 1.0
                offset *= float(radius) / (float(record["radius"]) * scale)
            else:
                axis = vec3_or_none(feature.params.get("axis"))
                if axis is not None:
                    direction = np.asarray(axis) / math.hypot(*axis)
                    axial = dot3(offset, direction) * direction
                    radial = offset - axial
                    old_axis = vec3_or_none(record.get("axis"))
                    scale = 1.0
                    if old_axis is not None:
                        old_direction = np.asarray(old_axis) / math.hypot(*old_axis)
                        old_radial = (
                            local_offset - dot3(local_offset, old_direction) * old_direction
                        )
                        span = math.hypot(*old_radial)
                        if span > EPS_GEOM:
                            scale = math.hypot(*radial) / span
                    offset = axial + radial * float(radius) / (float(record["radius"]) * scale)
    expected = np.asarray(centre) + offset
    origin = expected + normal * mesh.bounds.diagonal
    travel, faces = ray_hits_batch(
        np.asarray(mesh.raw.triangles)[list(indices)],
        origin[None, :],
        -normal[None, :],
        cancelled=cancelled,
    )
    cancelled.raise_if_cancelled()
    if not np.isfinite(travel[0]) or faces[0] < 0:
        raise _placement_error()
    triangle = int(indices[int(faces[0])])
    point = origin - normal * float(travel[0])
    outward = _vec(mesh.raw.face_normals[triangle])
    if source.kind == "brep":
        from app.core.brep.canonical import projected_surface_point
        from app.core.brep.kernel import Solid

        if isinstance(source.mesh, Solid):
            native = source.mesh.faces_of_triangles((triangle,))
            if len(native) == 1:
                measured = projected_surface_point(
                    source.mesh.faces()[next(iter(native))], _vec(point)
                )
                if measured is not None:
                    point = np.asarray(measured[0])
                    outward = measured[1]
    return SurfacePlacement(
        _vec(point), outward, frame_of(outward, _vec(point)), False, (triangle,), (), ()
    )


def _vec(values: Any) -> Vec3:
    return (float(values[0]), float(values[1]), float(values[2]))


def _reject(field: str, text: TranslatableText | str) -> ValidationError:
    """Eine abgelehnte Platzierung — mit Feld, Kennung und Handlungsvorschlag.

    Kein nackter ``ValueError``: Der Kunde erreicht diese Stellen mit einer
    gewöhnlichen Geste (Klick neben die Fläche, zu großes Maß), und jede
    Ausnahme trägt hier einen Vorschlag (AGENTS.md, Regel 17). Die Oberfläche
    fängt ``ValidationError`` wie zuvor den ``ValueError``.
    """
    return ValidationError(
        field, text, constraint="surface_placement", suggestions=(CORRECT_INPUT,)
    )


def _placement_error() -> ValidationError:
    return _reject(
        "point",
        tr(
            "Dieser Punkt liegt außerhalb der gewählten Fläche. "
            "Wählen Sie einen Punkt auf dem Material oder ändern Sie die Abstände."
        ),
    )


#: Unter welchem Namen die verschweißte Nachbarschaft im Netz-Cache liegt.
#:
#: ``trimesh`` führt für jedes Netz einen Cache, der beim Ändern der Punkte
#: von selbst verfällt (``Cache.verify``). Das ist genau die Lebensdauer, die
#: diese Auskunft braucht — und der Grund, sie nicht in ein eigenes
#: Wörterbuch neben dem Netz zu legen: Ein Cache über ``id(mesh)`` überlebt
#: sein Netz und liefert danach die Nachbarschaft eines anderen.
_ADJACENCY_KEY: Final = "solidon_patch_adjacency"


def mouth_outline(tool: PlacementTool) -> tuple[Point2, ...]:
    """Der Umriss, mit dem dieses Werkzeug die Oberfläche trifft — lokal, in U/V.

    **Wozu.** Der halbtransparente Werkzeugkörper zeigt den ganzen Zylinder,
    auch den Teil außerhalb des Materials, und beim Drehen der Ansicht ist
    schwer zu sehen, wo das Loch eigentlich hinkommt (Befund Robert,
    09.09.2026: „es reicht mir, wenn ich den Kreis auf der Oberfläche in
    Orange sehe"). Der Umriss beantwortet genau diese Frage und nichts sonst.

    **Warum im Kern und nicht im Fenster.** Er folgt aus der Geometrie des
    Werkzeugs, nicht aus einer Darstellung — dieselbe Regel, nach der schon
    die Platzierung hier liegt und nicht dort. Die Oberfläche projiziert ihn
    nur noch.

    Genommen werden die Punkte in der Mündungsebene: ``prepare_tool`` legt
    die Mündung auf ``z = 0`` (oder die Basis, bei aufsetzenden Bausteinen).
    Ihr Rand ist die konvexe Hülle — für Bohrung, Sechskant und Rechteck der
    Umriss selbst. Ein Werkzeug mit einspringender Mündung bekäme einen zu
    weiten; das ist die bewusste Grenze einer Anzeige, die nichts rechnen
    soll, was der Kunde nicht sieht.

    **Und die Hülle wird wirklich gebaut.** Bis zum 11.09.2026 stand hier eine
    Abtastung in 32 Winkelsektoren um den Schwerpunkt, je Sektor der äußerste
    Punkt. Am Kreis stimmt das; an einem Langloch fallen fast alle Punkte in
    wenige Sektoren, und der äußerste je Sektor ist nicht der Rand — gemessen
    an Ø 5 auf 20: der Werkzeugkörper 19,995 x 5,000 in der Mündungsebene, der
    gezeichnete Umriss 19,995 x **3,890** mit abgeschnittenen Enden, also
    22 Prozent zu schmal (Fund des Reviews). Und genau diesen Umriss sieht der
    Kunde — die Ansicht blendet den Werkzeugkörper aus, sobald einer da ist.

    Vereinfacht wird die Hülle um :data:`~app.core.units.MAX_FACET_SAG` —
    dieselbe Abweichung, mit der der Kern seine Bögen tesselliert. Was im Bild
    rund gezeichnet wird, bekommt hier weder mehr noch weniger Ecken; eine
    feste Punktzahl wäre am kleinen Kreis zu viel und am großen zu wenig.

    Leer, wenn keine Mündungsebene erkennbar ist — dann bleibt es beim Körper.
    """
    from shapely.geometry import MultiPoint

    points = np.asarray(tool.mesh.raw.vertices, dtype=np.float64)
    if not len(points):
        return ()
    at_mouth = points[np.abs(points[:, 2]) <= EPS_GEOM]
    if len(at_mouth) < 3:
        return ()
    hull = MultiPoint(at_mouth[:, :2]).convex_hull
    if hull.geom_type != "Polygon":
        return ()
    ring = list(hull.simplify(MAX_FACET_SAG, preserve_topology=True).exterior.coords)[:-1]
    return tuple((float(x), float(y)) for x, y in ring) if len(ring) >= 3 else ()


def _welded_adjacency(raw: Any, vertices: Any) -> np.ndarray:
    """Welche Dreiecke sich eine Kante teilen — über **exakte** Ortsgleichheit.

    Zurück kommt je geteilter Kante ein Paar Dreiecksnummern, das kleinere
    zuerst, als Feld mit zwei Spalten; die Reihenfolge der Paare sagt nichts.
    Eine Kante mit mehr als zwei Besitzern verbindet nichts; sie ist keine
    Fläche, sondern eine Verzweigung. Ebenso wenig ein Dreieck, das mit sich
    selbst eine Kante teilt.

    Exakte Gleichheit verbindet auch unverschweißte STL-Dreiecke, und kein
    Abstandsschwellwert darf dabei einen tatsächlichen schmalen Spalt
    schließen. Deshalb nicht ``trimesh.face_adjacency``: das verschweißt mit
    Toleranz.

    **Gerechnet wird einmal je Netz, nicht einmal je Klick.** Die Auskunft
    hängt allein am Netz — die angeklickte Fläche kommt erst danach ins Spiel.
    Ohne Cache lief sie bei jeder Mausbewegung über das Modell erneut:
    gemessen an ``Filamenthalter-Solidon3D.p3d`` (2 428 Dreiecke) 4,4 ms im
    Median und 52 ms im schlechtesten Fall, also unter zwanzig Bildern je
    Sekunde beim bloßen Zeigen (Befund Robert, 09.09.2026: „bei der Vorschau
    mit der Bohrung ist es noch relativ langsam").

    **Und ohne Python-Schleife je Kante.** Bis zum 22.09.2026 zählte ein
    Wörterbuch die Besitzer jeder Kante: An ``plate_holes.stl``, fünfmal
    unterteilt (815 104 Dreiecke), dauerte der erste Klick auf eine Bohrung
    darin 8,2 s, bevor Griff und Maße kamen (RM-200). Nach Kante sortiert
    stehen die zwei Besitzer einer geteilten Kante nebeneinander.

    **Und über die Punktnummer des Körpers** (``features.vertex_rank``,
    RM-232): Sie liegt nach der Erkennung schon im Cache des Netzes, wo diese
    Nachbarschaft ihre Ecken noch einmal als Zeilen sortierte. Trägt kein
    Ort zwei Ecken, sind die gespeicherten Nummern die Orte, und die
    Kantenzählung des Einlesens beantwortet die Frage schon
    (``mesh.edge_table``). An der dichten Platte kostete die erste
    Platzierung darauf 114 ms allein hierfür, jetzt rund 30.
    """
    try:
        cache = raw._cache
        cached = cache.cache.get(_ADJACENCY_KEY) if cache.verify() is None else None
    except AttributeError, TypeError, KeyError:
        cache = None
    else:
        if isinstance(cached, np.ndarray):
            return cached
    from app.core.perceive.features import vertex_rank

    adjacency: np.ndarray | None = None
    try:
        rank = vertex_rank(raw)
    except AttributeError, TypeError, KeyError:
        # Die Punktnummer liegt im Cache des Netzes; ohne ihn zählt der Ort selbst.
        rank = np.unique(vertices, axis=0, return_inverse=True)[1].reshape(-1)
    else:
        if len(rank) and int(rank.max()) + 1 == len(rank):
            with suppress(AttributeError, TypeError, KeyError):
                adjacency = edge_table(raw).face_pairs()
    if adjacency is None:
        faces = rank[np.asarray(raw.faces, dtype=np.int64)]
        _, edge_ids = unique_edges(
            faces[:, [[0, 1], [1, 2], [2, 0]]].reshape(-1, 2), return_inverse=True
        )
        edge_ids = np.asarray(edge_ids, dtype=np.int64).reshape(-1)
        order = np.argsort(edge_ids, kind="stable")
        shared = np.bincount(edge_ids)[edge_ids[order]] == 2
        pairs = (order[shared] // 3).reshape(-1, 2)
        adjacency = pairs[pairs[:, 0] != pairs[:, 1]]
    if cache is not None:
        # Die private Cacheform darf die berechnete Auskunft nicht verhindern.
        with suppress(AttributeError, TypeError, KeyError):
            cache[_ADJACENCY_KEY] = adjacency
    return adjacency


def _patch_faces(mesh: MeshData, face_index: int) -> tuple[tuple[int, ...], bool]:
    """Zusammenhängende koplanare Originaldreiecke, ohne Koordinatenrundung."""
    from app.core.perceive.features import CURVATURE_LIMIT, EPS_ANGLE

    raw = mesh.raw
    if face_index < 0 or face_index >= len(raw.faces):
        raise _reject(
            "point", tr("Diese Fläche ist nicht mehr vorhanden. Klicken Sie das Modell erneut an.")
        )
    vertices = np.asarray(raw.vertices, dtype=np.float64)
    normals = np.asarray(raw.face_normals, dtype=np.float64)
    normal = normals[face_index]
    if not np.isfinite(normal).all() or math.hypot(*normal) <= EPS_GEOM:
        raise _reject(
            "point",
            tr(
                "Diese Fläche hat keine brauchbare Richtung. "
                "Wählen Sie eine andere Stelle auf dem Modell."
            ),
        )
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components

    pairs = _welded_adjacency(raw, vertices)
    origin = vertices[np.asarray(raw.faces)[face_index, 0]]
    triangles = np.asarray(raw.triangles, dtype=np.float64)
    coplanar = (projected_along(normals, normal) >= exact_cos_degrees(EPS_ANGLE)) & (
        np.max(np.abs(projected_along(triangles - origin, normal)), axis=1) <= EPS_GEOM
    )
    # Das angeklickte Dreieck gehört immer dazu — auch wenn es an der
    # Genauigkeitsgrenze aus der eigenen Ebene fiele.
    coplanar[face_index] = True
    # Das Stück ist die Zusammenhangskomponente des Klicks im Graphen der
    # koplanaren Nachbarn — dieselbe Menge, die die Breitensuche bis zum
    # 22.09.2026 Dreieck für Dreieck fand.
    inner = pairs[coplanar[pairs[:, 0]] & coplanar[pairs[:, 1]]]
    count = len(normals)
    graph = coo_matrix(
        (np.ones(len(inner), dtype=np.int8), (inner[:, 0], inner[:, 1])), shape=(count, count)
    )
    _, labels = connected_components(graph, directed=False)
    found = labels == labels[face_index]
    border = pairs[found[pairs[:, 0]] != found[pairs[:, 1]]]
    alignment = np.sum(normals[border[:, 0]] * normals[border[:, 1]], axis=1)
    # Dieselbe Krümmungsgrenze wie die Merkmalsanalyse: Mantelstreifen und
    # kleine Kugeldreiecke versprechen keine Maße einer ebenen Konstruktionsfläche.
    smooth = int(
        np.count_nonzero(
            (alignment < exact_cos_degrees(EPS_ANGLE))
            & (alignment > exact_cos_degrees(CURVATURE_LIMIT))
        )
    )
    planar = not len(alignment) or smooth * 2 < len(alignment)
    return tuple(int(index) for index in np.flatnonzero(found)), planar


def _straight_boundary(
    coords: Any,
    round_points: Sequence[np.ndarray] = (),
    round_circles: Sequence[tuple[np.ndarray, float]] = (),
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Kollineare Randstücke vereinen; Kreisfacetten sind keine geraden Bezugskanten."""
    points = np.asarray(coords, dtype=np.float64)[:-1]
    if len(points) >= 8:
        local = points - points.mean(axis=0)
        solution = np.linalg.lstsq(
            np.column_stack((local * 2.0, np.ones(len(local)))),
            np.sum(local * local, axis=1),
            rcond=None,
        )[0]
        radii = np.linalg.norm(local - solution[:2], axis=1)
        if np.ptp(radii) <= EPS_GEOM:
            from scipy.spatial import cKDTree

            centre, radius = solution[:2] + points.mean(axis=0), float(radii.mean())
            # Ein dicht kreisförmiger Ring belegt keine unabhängigen Geraden,
            # auch wenn die globale Lochanalyse dieses kleine Loch nicht kennt.
            # Daraus entsteht ausdrücklich weder Lochmerkmal noch Mittenbezug.
            from app.core.units import MAX_FACET_ANGLE

            radial = points - centre
            lengths = np.linalg.norm(radial, axis=1)
            dense_circle = radius > EPS_GEOM and bool(np.all(lengths > EPS_GEOM))
            if dense_circle:
                radial /= lengths[:, None]
                dense_circle = bool(
                    np.all(
                        np.sum(radial * np.roll(radial, -1, axis=0), axis=1)
                        >= np.cos(MAX_FACET_ANGLE)
                    )
                )
            if (
                dense_circle
                or any(
                    np.linalg.norm(centre - known_centre) <= EPS_GEOM
                    and abs(radius - known_radius) <= EPS_GEOM
                    for known_centre, known_radius in round_circles
                )
                or any(
                    np.max(cKDTree(known_points).query(points)[0]) <= EPS_GEOM
                    for known_points in round_points
                )
            ):
                return []
    keep = []
    for index, point in enumerate(points):
        before, after = points[index - 1], points[(index + 1) % len(points)]
        one, two = point - before, after - point
        cross = one[0] * two[1] - one[1] * two[0]
        if (
            abs(cross) > EPS_GEOM * max(math.hypot(*one), math.hypot(*two))
            or float(np.sum(one * two)) < 0.0
        ):
            keep.append(point)
    return [(start, keep[(index + 1) % len(keep)]) for index, start in enumerate(keep)]


def _boundary_area(xy: np.ndarray) -> BaseGeometry | None:
    """Die Fläche aus dem Rand der Dreiecke — oder ``None``, wenn er nicht trägt.

    Eine Kante, die genau ein Dreieck des Stücks trägt, liegt am Rand; die
    anderen teilt sie mit dem Nachbarn und verschwinden in der Vereinigung.
    Gezählt wird nach Ort, nicht nach Eckennummer: Dieselbe Ecke zweier
    Dreiecke hat in Ebenenkoordinaten dieselben zwei Zahlen. Aus den
    Randkanten baut GEOS die Fläche mit ihren Löchern (``build_area``).

    Das trägt nur bei einem sauberen Netz, und ob es eines war, sagt das
    Ergebnis, nicht eine Annahme: Jede Randecke hat genau zwei Randkanten
    (eine T-Kreuzung oder eine Ecke, an der zwei Löcher sich berühren, hätte
    mehr), keine Kante gehört zu mehr als zwei Dreiecken, und die Fläche ist
    ein gültiges Polygon mit der Summe der Dreiecksflächen — ein überlappendes
    Dreieck zählte doppelt. Sonst ``None``.
    """
    import shapely

    corners = np.asarray(xy, dtype=float).reshape(-1, 2)
    if not len(corners):
        return None
    # Als komplexe Zahl ist ein Ort ein Wert: ``np.unique`` sortiert dann eine
    # Spalte statt Zeilen (an 620 000 Ecken 0,10 statt 0,54 s), mit derselben
    # Ordnung — erst x, dann y.
    unique_places, ids = np.unique(
        np.ascontiguousarray(corners).view(np.complex128).ravel(), return_inverse=True
    )
    places = unique_places.view(np.float64).reshape(-1, 2)
    ids = ids.reshape(-1, 3).astype(np.int64)
    edges = np.sort(ids[:, [0, 1, 1, 2, 2, 0]].reshape(-1, 2), axis=1)
    count = np.int64(len(places))
    keys, uses = np.unique(edges[:, 0] * count + edges[:, 1], return_counts=True)
    if uses.max(initial=0) > 2:
        return None
    rim = keys[uses == 1]
    if not len(rim):
        return None
    first, second = np.divmod(rim, count)
    if np.any(
        np.bincount(np.concatenate((first, second)), minlength=int(count))[
            np.unique(np.concatenate((first, second)))
        ]
        != 2
    ):
        return None
    lines = shapely.multilinestrings(
        shapely.linestrings(np.stack((places[first], places[second]), axis=1))
    )
    area = shapely.build_area(lines)
    triangles = np.asarray(xy, dtype=float)
    along, across = triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]
    total = float(np.abs(along[:, 0] * across[:, 1] - along[:, 1] * across[:, 0]).sum()) / 2.0
    if (
        area.is_empty
        or area.geom_type != "Polygon"
        or not area.is_valid
        or not math.isclose(float(area.area), total, rel_tol=1e-9, abs_tol=0.0)
    ):
        return None
    return area


def _patch_area(xy: np.ndarray) -> BaseGeometry:
    """Die Dreiecke eines Flächenstücks in Ebenenkoordinaten als eine GEOS-Fläche.

    **Erst der Rand, dann die allgemeine Vereinigung.** Bis zum 22.09.2026
    entstand jedes Dreieck als eigenes ``Polygon`` und alle zusammen gingen
    durch ``union_all``: An der Oberseite von ``plate_holes.stl``, fünfmal
    unterteilt (206 848 Dreiecke), dauerte das 17 bis 28 s — so lange standen
    nach dem Klick auf eine Bohrung weder Griff noch Maße (RM-200). GEOS'
    Überdeckungsvereinigung brauchte noch 3,8 s; der Rand aus
    :func:`_boundary_area` kommt mit Zählen aus. Am Korpus gleich dem alten
    Ergebnis, Punkt für Punkt nach Normalisierung; nur wo er ablehnt, rechnet
    ``union_all``.
    """
    import shapely

    area = _boundary_area(xy)
    if area is not None:
        return area
    return shapely.union_all(shapely.polygons(np.asarray(xy, dtype=float)))


def prepare_surface(
    mesh: MeshData, face_index: int, features: Mapping[str, Feature] | None = None
) -> PreparedSurface:
    """Originalfläche und Maße einmal vorbereiten — je Netz, Dreieck und Merkmalen einmal.

    **Die Antwort wird am Netz gemerkt** (``perceive.features.remembered``,
    RM-232, 25.09.2026) und stirbt mit ihm. An der dichten Platte kostet die
    Oberseite 105 ms, und :func:`seat_of` fragt sie für jede Bohrung darauf
    neu — bei jedem Klick, denn jede Bohrung sitzt auf derselben Fläche und
    fragt ihr erstes Dreieck. Zur Frage gehören die Merkmale, soweit der
    Rumpf sie liest (:func:`_surface_question`): Die Mittenbezüge tragen ihre
    Namen, und nach einer Auswertung kann dasselbe Netz anders benannte —
    oder dieselben Namen an vertauschten — Merkmalen tragen. Die vorbereitete
    Fläche ist unveränderlich; wer sie erweitert, legt ``replace`` darüber.
    """
    from app.core.perceive.features import remembered

    prepared: PreparedSurface = remembered(
        "prepared_surface",
        mesh.raw,
        (),
        lambda: _prepared_surface(mesh, face_index, features),
        extra=(int(face_index), _surface_question(features)),
    )
    return prepared


def _surface_question(features: Mapping[str, Feature] | None) -> tuple[Any, ...] | None:
    """Was :func:`_prepared_surface` aus den Merkmalen liest — als Teil des Merkerschlüssels.

    **Die Namen allein reichen nicht** (Review 25.09.2026): Ein Netz kommt
    unverändert aus dem Ergebniscache, und eine neu beantwortete Zuordnung
    kann dieselben Namen an vertauschten Bohrungen tragen. Die gemerkte
    Fläche nannte dann die eigene Mitte als die der Nachbarbohrung, und
    :func:`seat_of` nahm die falsche heraus. Genommen werden je Merkmal die
    Felder, die der Rumpf liest — Kennung, Art, Mitte, Achse, Richtung,
    Tiefe, Durchmesser, Länge — und die Zahl seiner Dreiecke. Die
    Dreiecksnummern selbst gehen nicht ein: Am selben Netz gehören zu
    derselben Art, Lage und denselben Maßen dieselben Dreiecke, und ein
    Schlüssel über sie kostete an 1,5 Millionen Nummern beim ersten Klick
    8 bis 12 ms (gemessen am 25.09.2026; der ganze Schlüssel an 5 000
    Merkmalen 16 ms, gegen 105 ms für die Vorbereitung der dichten Platte).
    """
    if features is None:
        return None

    def number(value: Any) -> float | None:
        try:
            return float(value)
        except TypeError, ValueError:
            return None

    return tuple(
        (
            name,
            feature.id,
            feature.kind,
            vec3_or_none(feature.params.get("centre")),
            vec3_or_none(feature.params.get("axis")),
            vec3_or_none(feature.params.get("direction")),
            number(feature.params.get("depth")),
            number(feature.params.get("diameter")),
            number(feature.params.get("length")),
            len(feature.face_indices),
        )
        for name, feature in sorted(features.items())
    )


def _prepared_surface(
    mesh: MeshData, face_index: int, features: Mapping[str, Feature] | None
) -> PreparedSurface:
    """Der Rumpf von :func:`prepare_surface`, ohne Merker."""
    from shapely import prepare
    from shapely.geometry import Point

    from app.core.sketch.planes import frame_of, to_plane, to_world

    indices, planar = _patch_faces(mesh, face_index)
    normal = _vec(mesh.raw.face_normals[face_index])
    frame = frame_of(normal, _vec(mesh.raw.triangles[face_index, 0]))
    triangles = np.asarray(mesh.raw.triangles)[list(indices)]
    relative = triangles - frame.origin
    xy = np.stack(
        (projected_along(relative, frame.x_axis), projected_along(relative, frame.y_axis)), axis=-1
    )
    area = _patch_area(xy)
    if area.is_empty or not area.is_valid or area.geom_type != "Polygon":
        raise _reject(
            "point",
            tr(
                "Diese Fläche ist nicht eindeutig zusammenhängend. "
                "Wählen Sie eine andere Stelle auf dem Modell."
            ),
        )
    matching = [
        feature for feature in (features or {}).values() if face_index in feature.face_indices
    ]
    if any(feature.kind in {"hole", "pin", "cone", "sphere", "fillet"} for feature in matching):
        planar = False
    elif any(feature.kind == "face" for feature in matching):
        planar = True
    references: list[EdgeReference] = []
    if planar:
        round_points: list[np.ndarray] = []
        round_circles: list[tuple[np.ndarray, float]] = []
        for feature in (features or {}).values():
            if feature.kind not in {"hole", "pin", "cone"}:
                continue
            axis = vec3_or_none(feature.params.get("axis"))
            centre = vec3_or_none(feature.params.get("centre"))
            if axis is None or centre is None:
                continue
            vector = np.asarray(axis)
            length = math.hypot(*vector)
            if length <= EPS_GEOM or abs(dot3(vector, frame.normal) / length) < 1.0 - EPS_GEOM:
                continue
            if feature.face_indices:
                vertices = np.asarray(mesh.raw.triangles)[list(feature.face_indices)].reshape(-1, 3)
                relative = vertices - frame.origin
                rim = relative[np.abs(projected_along(relative, frame.normal)) <= EPS_GEOM]
                if len(rim):
                    round_points.append(
                        np.column_stack(
                            (projected_along(rim, frame.x_axis), projected_along(rim, frame.y_axis))
                        )
                    )
            elif feature.kind in {"hole", "pin"}:
                depth = float(feature.params.get("depth", 0.0))
                distance = abs(dot3(np.asarray(centre) - frame.origin, frame.normal))
                if distance <= depth / 2.0 + EPS_GEOM:
                    round_circles.append(
                        (
                            np.asarray(to_plane(frame, centre)),
                            float(feature.params["diameter"]) / 2.0,
                        )
                    )
        for ring_index, ring in enumerate((area.exterior, *area.interiors)):
            for start, end in _straight_boundary(ring.coords, round_points, round_circles):
                direction = end - start
                direction /= math.hypot(*direction)
                inward = np.array([-direction[1], direction[0]])
                midpoint = (start + end) / 2.0
                # Die GEOS-Ringorientierung ist nicht Teil unseres Vertrags.
                # Ein Punkt auf der Materialseite legt das Vorzeichen fest.
                if not area.covers(Point(midpoint + inward * EPS_GEOM)):
                    inward = -inward
                vector = inward[0] * np.asarray(frame.x_axis) + inward[1] * np.asarray(frame.y_axis)
                references.append(
                    EdgeReference(
                        f"edge_{len(references)}",
                        to_world(frame, _vec2(start)),
                        to_world(frame, _vec2(end)),
                        _vec(vector),
                        kind="outer" if ring_index == 0 else "inner",
                    )
                )
    centres = []
    for feature in (features or {}).values():
        centre, axis = (
            vec3_or_none(feature.params.get("centre")),
            vec3_or_none(feature.params.get("axis")),
        )
        if feature.kind not in {"hole", "pin", "slot"} or centre is None or axis is None:
            continue
        vector = np.asarray(axis, dtype=np.float64)
        length = math.hypot(*vector)
        if length <= EPS_GEOM or abs(dot3(vector, frame.normal) / length) < 1.0 - EPS_GEOM:
            continue
        # Ein Zylinderzentrum liegt meist in der Wandmitte. Sein Achsschnitt
        # mit genau dieser Ebene ist die nutzbare Mitte an der Mündung.
        amount = dot3(np.asarray(frame.origin) - centre, frame.normal) / dot3(vector, frame.normal)
        feature_depth = feature.params.get("depth")
        if (
            isinstance(feature_depth, int | float)
            and abs(float(amount)) * length > feature_depth / 2.0 + EPS_GEOM
        ):
            continue
        projected = _vec(np.asarray(centre) + amount * vector)
        point2 = to_plane(frame, projected)
        if area.envelope.covers(Point(point2)):
            centres.append((feature.id, projected))
            direction = vec3_or_none(feature.params.get("direction"))
            feature_length = feature.params.get("length")
            if (
                feature.kind == "slot"
                and direction is not None
                and isinstance(feature_length, int | float)
            ):
                along = np.asarray(direction, dtype=np.float64)
                span = float(np.linalg.norm(along))
                if (
                    span > EPS_GEOM
                    and abs(float(along @ frame.normal)) <= EPS_GEOM * span
                    and feature_length > EPS_GEOM
                ):
                    along /= span
                    references.append(
                        EdgeReference(
                            f"axis_{feature.id}",
                            _vec(np.asarray(projected) - along * feature_length / 2.0),
                            _vec(np.asarray(projected) + along * feature_length / 2.0),
                            _vec(np.cross(frame.normal, along)),
                            kind="axis",
                        )
                    )
    prepare(area)
    return PreparedSurface(frame, planar, indices, tuple(references), tuple(centres), area)


def seat_for_bore_step(
    mesh: MeshData,
    spec: OperationSpec,
    resolved_params: Mapping[str, Any],
    features: Mapping[str, Feature],
) -> tuple[PreparedSurface, Vec3] | None:
    """Die belegte ursprüngliche Bohrfläche am Körper vor dem historischen Schritt.

    Die Werte sind bereits aufgelöste Originalparameter. Eine endliche
    Bohrung braucht ihre tatsächliche Mündungsebene; ein Mittenanker wird
    dafür um die halbe ursprüngliche Tiefe versetzt. Eine gerade durchgehende
    Bohrung besitzt dagegen keine gespeicherte Eintrittshöhe: Ihr Achsstrahl
    muss genau eine zusammenhängende Materialsäule treffen. Mehrere getrennte
    Abschnitte, keine Fläche oder ein nicht ebener Sitz liefern None.

    Die Rückgabe dient der Anzeige und den Abstandsbezügen. Sie ersetzt weder
    Originalposition noch Anker im Entwurf, solange niemand die Lage ändert.
    Es werden kein Merkmal erfunden und keine späteren Weltmaße zurückgerechnet.
    """
    from app.core.geom.mesh import ray_hits
    from app.core.geom.prepare import _into_the_material
    from app.core.geom.prepare_ops import bore_shape
    from app.core.registry.params import validate

    if spec.name not in DRILL_OPERATIONS:
        return None
    values: Any = validate(spec.params, resolved_params)
    position = np.asarray((values.x, values.y, values.z), dtype=np.float64)
    direction = np.asarray((values.nx, values.ny, values.nz), dtype=np.float64)
    length = float(np.linalg.norm(direction))
    if length <= EPS_GEOM:
        direction["xyz".index(values.axis)] = -_into_the_material(mesh, values.axis, _vec(position))
    else:
        direction /= length
    # Ein Ursprung jenseits der Hülle trifft dieselbe Achslinie, ohne dass
    # ein gespeicherter Nullpunkt als bereits gewählte Oberfläche gilt.
    reach = float(np.linalg.norm(position - mesh.bounds.centre)) + mesh.bounds.diagonal
    origin = position + direction * reach
    distances, indices = ray_hits(np.asarray(mesh.raw.triangles), origin, -direction)
    if not len(distances):
        return None
    shape = bore_shape(values, within=mesh)
    if values.depth <= EPS_GEOM and not (
        shape.widening_diameter > EPS_GEOM and values.anchor == "mouth"
    ):
        levels: list[float] = []
        for distance in sorted(distances):
            if not levels or distance - levels[-1] > EPS_GEOM:
                levels.append(float(distance))
        if len(levels) != 2:
            return None
        mouth = origin - direction * levels[0]
    else:
        offset = values.depth / 2.0 if values.anchor == "centre" else 0.0
        mouth = position + direction * offset
    points = origin - distances[:, None] * direction
    at_mouth = np.linalg.norm(points - mouth, axis=1) <= EPS_GEOM
    seats: dict[tuple[int, ...], PreparedSurface] = {}
    for index in indices[at_mouth]:
        if float(mesh.raw.face_normals[index] @ direction) < _SEAT_PARALLEL:
            continue
        try:
            prepared = prepare_surface(mesh, int(index), features)
            if not prepared.planar:
                continue
            at_point(prepared, _vec(mouth))
        except ValidationError:
            continue
        seats[prepared.face_indices] = prepared
    if len(seats) != 1:
        return None
    return next(iter(seats.values())), _vec(mouth)


def seat_of(
    mesh: MeshData, feature: Feature, features: Mapping[str, Feature]
) -> tuple[PreparedSurface, Vec3] | None:
    """Die Fläche, auf der ein **erkanntes** Merkmal sitzt — und seine Mündung.

    :func:`prepare_surface` beantwortet „wohin darf ich setzen" und braucht
    dafür einen Klick auf Material. Diese Funktion beantwortet die Frage
    danach: „**wo** sitzt das, was schon da ist" — für die Maßlinien am
    gewählten Merkmal (Robert, 10.09.2026: „maße zu außenkanten oder
    mittelpunkt wie bohrung anlegen").

    Zwei Dinge unterscheiden sie von ihrer Schwester, und beide sind der
    Grund, warum es sie gibt:

    * **Die Fläche wird gesucht, nicht angeklickt.** Genommen wird die ebene
      Fläche, deren Normale auf der Achse des Merkmals liegt und deren Ebene
      eine seiner Mündungen enthält — **beide Enden werden gefragt.** Die
      gemessene Achse trägt kein Vorzeichen (``units.positive_axis`` normiert
      sie an beiden Kernen), also sagt sie nicht, an welchem Ende die
      Öffnung liegt: Ein Sackloch von unten gebohrt zeigte mit ihr vom Boden
      weg ins Material, dort lag keine Fläche, und im Bild stand kein Maß
      (gemessen 11.09.2026, Platte 60 x 40 x 10, Sackloch Ø 6, 4 mm tief,
      Fund des Reviews). Bei einem durchgehenden Loch tragen beide Enden eine
      Fläche; genommen wird die, auf die die Achse zeigt — dieselbe Wahl wie
      bisher.
    * **Die Öffnung wird gefüllt.** Die Mitte einer Bohrung liegt in der
      Aussparung, die sie in ihre Trägerfläche geschnitten hat; ``at_point``
      lehnt sie deshalb als „außerhalb der Fläche" ab. Gemessen an einer Platte
      60 x 40 mit einer Bohrung bei (10, 5): mit den inneren Ringen eine
      Absage, ohne sie 15,0 mm zur oberen und 20,0 mm zur rechten Kante. Für
      die Frage nach den **Außenmaßen** ist das Loch ohnehin ohne Belang.

    **Und eine Fase an der Mündung verschiebt die Mündung nicht von der
    Fläche.** Gemessen wird die zylindrische Wand; eine Fase, Rundung oder
    Senkung davor gehört nicht dazu, und die gemessene Mündung liegt dann
    unter der Ebene der Trägerfläche — an der Magnettasche eines Schabers
    0,19 mm, am Langloch eines Wedge-Lock 0,76 mm (24.09.2026). Findet keine
    Mündung eine Fläche in ihrer Ebene, gilt die nächste Fläche dahinter,
    höchstens :func:`mouth_reach` entfernt, **wenn ihre Öffnung die Achse
    umschließt**; eine Fläche ohne Öffnung dort ist Material und kein Sitz.

    ``None`` heißt: Zu diesem Merkmal gibt es keine solche Fläche — eine
    Verrundung an einer Kante hat keine, und ein Merkmal ohne Achse oder Tiefe
    ebenso wenig. Der Aufrufer zeigt dann keine Maße statt falscher.
    """
    mouths = _ends(feature)
    for mouth, outward in mouths:
        seated = _seat_at(mesh, feature, features, mouth, outward)
        if seated is not None:
            return seated
    reach = mouth_reach(feature)
    if reach <= EPS_GEOM:
        return None
    for mouth, outward in mouths:
        seated = _seat_at(mesh, feature, features, mouth, outward, reach=reach)
        if seated is not None:
            return seated
    return None


def mouth_on(
    prepared: PreparedSurface, feature: Feature, features: Mapping[str, Feature]
) -> Vec3 | None:
    """Die eigene Mündung eines Lochs auf dieser Fläche — ``None`` für eine fremde.

    Die Frage vor der Fasenkorrektur in :func:`surface_values`: Ist die
    Fläche, auf die gerade gezielt wird, die Mündungsfläche des Lochs, oder
    eine fremde, die nur parallel daneben liegt? Beantwortet wie
    :func:`seat_of` je Ende — die Ebene der gemessenen Mündung selbst, sonst
    eine bis :func:`mouth_reach` dahinter, deren Öffnung die Achse
    umschließt; liegt an diesem Ende eine Fläche genau in der Mündung, ist
    nur sie die eigene. Gefragt wird an einer **frisch vorbereiteten** Fläche
    mit ihren Öffnungen. Die Fläche aus :func:`seat_of` hat die eigene
    Öffnung gefüllt und bestünde die Prüfung nicht; wer von dort kommt, nimmt
    deren Mündung.

    Bis zum 25.09.2026 galt jede parallele Fläche im Fenster als die eigene
    (G5): Ein Sackloch von unten, mit einem Klick auf die 2 mm darüber
    liegende Oberseite versetzt, behielt die Höhe seiner Mitte und wurde ein
    Hohlraum im Material statt einer Bohrung.
    """
    if not prepared.planar:
        return None
    normal = prepared.frame.normal
    origin = prepared.frame.origin
    reach = mouth_reach(feature)
    for mouth, outward in _ends(feature):
        aligned = dot3(normal, outward)
        if not _faces_outward(aligned, feature):
            continue
        offset = dot3(tuple(o - m for o, m in zip(origin, mouth, strict=True)), normal)
        point = _vec(np.asarray(mouth) + np.asarray(outward) * (offset / aligned))
        exact = abs(offset) <= EPS_GEOM
        if not exact and not (
            -MAX_FACET_SAG <= offset <= reach
            and not _seat_candidates(feature, features, mouth, outward)
        ):
            continue
        if not _openings(prepared):
            if exact:
                return point
            continue
        if _opening_around(prepared, point) is not None:
            return point
    return None


def _ends(feature: Feature) -> tuple[tuple[Vec3, Vec3], ...]:
    """Die beiden Mündungen eines Merkmals, je mit der Richtung nach außen.

    Die gemessene Achse trägt kein Vorzeichen (:func:`seat_of`), also sind
    es immer beide Enden: zuerst das, auf das die Achse zeigt. Leer, wenn
    Achse, Mitte oder Tiefe fehlen.
    """
    axis = feature.params.get("axis")
    depth = feature.params.get("depth")
    centre = feature.params.get("centre")
    if axis is None or centre is None or not isinstance(depth, int | float):
        return ()
    direction = np.asarray(axis, dtype=float)
    length = math.sqrt(dot3(direction, direction))
    if length <= EPS_GEOM:
        return ()
    direction = direction / length
    middle = np.asarray(centre, dtype=float)
    half = direction * (float(depth) / 2.0)
    return (
        (_vec(middle + half), _vec(direction)),
        (_vec(middle - half), _vec(-direction)),
    )


def _faces_outward(aligned: float, feature: Feature) -> bool:
    """Ob eine Fläche mit dieser Ausrichtung zur Achse eine Mündung tragen kann.

    Der Sacklochboden liegt ebenfalls auf einer Endebene, zeigt aber zum
    Hohlraum zurück. Nur die äußere Mündung zeigt von der Mitte weg.
    """
    return (aligned if feature.kind in ("hole", "slot") else abs(aligned)) >= _SEAT_PARALLEL


def _seat_candidates(
    feature: Feature,
    features: Mapping[str, Feature],
    mouth: Vec3,
    direction: Vec3,
    *,
    reach: float = 0.0,
) -> list[tuple[float, Feature, Vec3]]:
    """Die ebenen Flächen, die an diesem Ende die Mündung tragen könnten, die nächste zuerst.

    Ohne ``reach`` nur Flächen, deren Ebene die Mündung enthält; mit ``reach``
    die bis dahin nach außen dahinter, jede mit dem Durchstoßpunkt der Achse.
    Gefragt wird an den Merkmalen, ohne eine Fläche vorzubereiten.
    """
    beyond = reach > EPS_GEOM
    candidates: list[tuple[float, Feature, Vec3]] = []
    for entry in features.values():
        if entry.kind != "face" or not entry.face_indices:
            continue
        normal = entry.params.get("normal")
        seat = entry.params.get("centre")
        if normal is None or seat is None:
            continue
        aligned = dot3(normal, direction)
        if not _faces_outward(aligned, feature):
            continue
        offset = dot3(tuple(float(s) - m for s, m in zip(seat, mouth, strict=True)), normal)
        if not beyond:
            if abs(offset) > EPS_GEOM:
                continue
            candidates.append((0.0, entry, mouth))
        elif -MAX_FACET_SAG <= offset <= reach:
            # **Auch knapp davor.** Die Wand ist eingepasst, nicht abgelesen:
            # Am gekürzten Langloch des Wedge-Lock lag die gemessene Mündung
            # 3,5 µm über ihrer Fläche — für ``EPS_GEOM`` eine andere Ebene.
            # Entlang der Achse bis in die Ebene, nicht entlang der Normalen:
            # Die Mitte bleibt auf der Achse, auch wo die Fläche um die
            # Messgenauigkeit schief steht.
            candidates.append(
                (
                    abs(offset),
                    entry,
                    _vec(np.asarray(mouth) + np.asarray(direction) * (offset / aligned)),
                )
            )
    # Die nächste Ebene zuerst; in der Mündung selbst gilt die Reihenfolge
    # der Merkmale wie bisher (stabil sortiert, alle Abstände null).
    return sorted(candidates, key=lambda candidate: candidate[0])


def _openings(prepared: PreparedSurface) -> tuple[Any, ...]:
    """Die inneren Ringe einer vorbereiteten Fläche — leer ohne Aussparung."""
    from shapely.geometry import Polygon

    area = prepared.area
    if not isinstance(area, Polygon):
        return ()
    return tuple(area.interiors)


def _opening_around(prepared: PreparedSurface, point: Vec3) -> Any:
    """Die eine Öffnung der Fläche, die den Durchstoßpunkt der Achse umschließt.

    ``None``, wenn es keine oder mehr als eine ist — dann ist die Fläche an
    dieser Stelle Material oder die Frage nicht eindeutig.
    """
    from shapely.geometry import Point, Polygon

    from app.core.sketch.planes import to_plane

    pierced = Point(to_plane(prepared.frame, point))
    own = [ring for ring in _openings(prepared) if Polygon(ring).covers(pierced)]
    return own[0] if len(own) == 1 else None


def mouth_reach(feature: Feature) -> float:
    """Wie weit hinter der gemessenen Mündung eines Lochs seine Fläche liegen darf.

    Ein Radius: Eine Fase, Rundung oder Senkung, die tiefer reicht als das
    Loch breit ist, ist kein Rand der Mündung mehr, sondern eine eigene Stufe.
    :func:`seat_of` sucht die Trägerfläche höchstens so weit, und
    :func:`surface_values` nimmt eine Fläche in dieser Reichweite als die
    eigene Mündung — sonst rückte die Mitte um die Fase in die Achse. Null
    für alles, was kein Loch oder Langloch ist.
    """
    diameter = feature.params.get("diameter")
    if feature.kind not in ("hole", "slot") or not isinstance(diameter, int | float):
        return 0.0
    return max(0.0, float(diameter) / 2.0)


def _seat_at(
    mesh: MeshData,
    feature: Feature,
    features: Mapping[str, Feature],
    mouth: Vec3,
    direction: Vec3,
    *,
    reach: float = 0.0,
) -> tuple[PreparedSurface, Vec3] | None:
    """Die ebene Fläche, deren Ebene diese Mündung enthält — mit gefüllter Öffnung.

    Der Rumpf von :func:`seat_of`, je Mündungskandidat einmal gerufen. Mit
    ``reach`` liegt die Ebene nicht in der Mündung, sondern bis dahin nach
    außen hinter ihr; die zurückgegebene Mündung ist dann der Durchstoßpunkt
    der Achse durch diese Ebene, und nur eine Fläche zählt, deren eigene
    Öffnung die Achse umschließt.
    """
    from shapely.geometry import Point, Polygon

    from app.core.sketch.planes import to_plane

    beyond = reach > EPS_GEOM
    for _distance, entry, point in _seat_candidates(
        feature, features, mouth, direction, reach=reach
    ):
        try:
            prepared = prepare_surface(mesh, entry.face_indices[0], features)
        except ValidationError:
            continue
        if not _openings(prepared):
            if beyond:
                # Ohne Öffnung um die Achse ist die Fläche dahinter Material —
                # der Deckel über einem flachen Sackloch, kein Sitz.
                continue
            return replace(prepared, centres=_others(prepared, feature)), point
        # **Und die Kanten der eigenen Öffnung zählen nicht mit.** Ein Langloch
        # hat zwei gerade Flanken, und die sind vom Merkmal aus die nächsten
        # Bezugskanten überhaupt: Gemessen an einer Platte 60 x 40 mit einem
        # Langloch Ø 6 auf 20 kamen minus 3,00 und minus 3,30 zurück, also seine eigene
        # halbe Breite. Gefragt ist der Abstand zum **Rand des Teils**; was in
        # einer Aussparung liegt, ist keine Antwort darauf.
        border = _opening_around(prepared, point)
        if border is None:
            continue
        area = prepared.area
        available = Polygon(area.exterior, [ring for ring in area.interiors if ring != border])
        edges = tuple(
            edge
            for edge in prepared.edges
            if edge.id != f"axis_{feature.id}"
            and not (
                border.distance(Point(to_plane(prepared.frame, edge.start))) <= EPS_GEOM
                and border.distance(Point(to_plane(prepared.frame, edge.end))) <= EPS_GEOM
            )
        )
        return replace(
            prepared, area=available, edges=edges, centres=_others(prepared, feature)
        ), point
    return None


def _others(prepared: PreparedSurface, feature: Feature) -> tuple[tuple[str, Vec3], ...]:
    """Die Mittenbezüge der Fläche ohne den des Merkmals selbst.

    Der Abstand eines Lochs zu seiner eigenen Mitte ist null, und zwar immer.
    Er stand als zwei Zahlenfelder im Bild und beantwortete keine Frage
    (Robert, 10.09.2026: „die 2 mit mitte 0 brauchen wir hier nicht oder was
    sollen sie zeigen"). Was bleibt, sind die Mitten der **anderen** Löcher —
    genau das, was man beim Versetzen wissen will.
    """
    return tuple(entry for entry in prepared.centres if entry[0] != feature.id)


#: Wie genau die Normale einer Fläche auf der Achse eines Merkmals liegen muss,
#: damit sie seine Trägerfläche sein kann.
#:
#: Der Kosinus von rund 2,6 Grad. Eine gemessene Normale kommt aus dem Netz und
#: trifft die Achse nicht auf die Stelle; strenger wäre eine Grenze gegen die
#: Tesselierung, weiter nähme eine schräge Nachbarfläche die Rolle ein.
_SEAT_PARALLEL: Final = 0.999


def _vec2(values: Any) -> Point2:
    return (float(values[0]), float(values[1]))


#: Bediengrenze: Ein Anzeigeschritt darf durch das Bezugspaar höchstens um
#: Faktor zehn verstärkt werden. Das ist keine Unsicherheit der Originalfläche
#: und keine Fertigungstoleranz. Die dimensionslose Kondition bleibt beim
#: Drehen und Skalieren gleich; schlechtere Paare brauchen einen anderen Bezug.
MAX_REFERENCE_CONDITION: Final = 10.0

#: In welchen Stufen :func:`_nearest_references` vergleicht, wie quer ein
#: zweiter Randbezug zum ersten steht: als Kosinus zwischen den
#: Einwärtsrichtungen, 0,05 je Stufe (rund drei Grad um die Senkrechte). So
#: gelten die Gleitkommaspuren einer eingelesenen STL nicht als „weniger quer“,
#: und unter gleich queren entscheidet der Abstand. Eine Bedienentscheidung,
#: keine Geometrietoleranz.
CROSSING_STEP: Final = 0.05


def _reference_rows(frame: PlaneFrame, edges: Sequence[EdgeReference]) -> np.ndarray:
    return np.asarray(
        [(dot3(edge.inward, frame.x_axis), dot3(edge.inward, frame.y_axis)) for edge in edges],
        dtype=np.float64,
    )


def _independent(frame: PlaneFrame, edges: Sequence[EdgeReference]) -> bool:
    if len(edges) < 2:
        return True
    rows = _reference_rows(frame, edges)
    a, b = float(np.sum(rows[0] * rows[0])), float(np.sum(rows[1] * rows[1]))
    c = float(np.sum(rows[0] * rows[1]))
    high = (a + b + math.sqrt((a - b) * (a - b) + 4.0 * c * c)) / 2.0
    determinant = float(rows[0, 0] * rows[1, 1] - rows[0, 1] * rows[1, 0])
    return high <= MAX_REFERENCE_CONDITION * abs(determinant)


def _solved_distances(rows: np.ndarray, offsets: Sequence[float]) -> Point2:
    """Zwei unabhängige Ebenenkoordinaten direkt lösen, ohne LAPACK-Rundung."""
    a, b, c, d = (float(value) for value in rows.reshape(-1))
    determinant = a * d - b * c
    if abs(determinant) <= EPS_GEOM:
        raise _reference_error()
    first, second = offsets
    return ((first * d - b * second) / determinant, (a * second - first * c) / determinant)


def _reference_error() -> ValidationError:
    return _reject(
        "references",
        tr(
            "Diese Bezüge fehlen oder liegen zu parallel. "
            "Wählen Sie eine andere Kante oder Mitte als Bezug."
        ),
    )


def _checked_references(prepared: PreparedSurface, edges: Sequence[EdgeReference]) -> None:
    """Vergängliche Kennungen gelten nur mit unveränderter belegter Geometrie."""
    available = {edge.id: edge for edge in prepared.edges}
    if len(edges) > 2 or len({edge.id for edge in edges}) != len(edges):
        raise _reference_error()
    for edge in edges:
        original = available.get(edge.id)
        if original is None or any(
            not np.allclose(old, new, atol=EPS_GEOM, rtol=0.0)
            for old, new in (
                (original.start, edge.start),
                (original.end, edge.end),
                (original.inward, edge.inward),
            )
        ):
            raise _reference_error()
    if not _independent(prepared.frame, edges):
        raise _reference_error()


def with_reference(
    prepared: PreparedSurface, surface: SurfacePlacement, index: int, edge_id: str
) -> SurfacePlacement:
    """Einen echten Bezug ausdrücklich ersetzen; Punkt und anderer Bezug bleiben stehen."""
    if index not in (0, 1) or index > len(surface.edges):
        raise _reference_error()
    edge = next((edge for edge in prepared.edges if edge.id == edge_id), None)
    if edge is None:
        raise _reference_error()
    edges = list(surface.edges)
    if index == len(edges):
        edges.append(edge)
    else:
        edges[index] = edge
    return at_point(prepared, surface.point, references=edges)


def reference_candidates(
    prepared: PreparedSurface,
    point: Vec3,
    maximum_distance: float,
    *,
    ray: tuple[Vec3, Vec3] | None = None,
) -> tuple[tuple[str, str], ...]:
    """Alle nahen echten Bezüge liefern; gleiche Nähe entscheidet niemals heimlich.

    Der Aufrufer belegt zuvor den ersten sichtbaren Originaltreffer dieses Körpers.
    Ein Strahl darf die Trägerfläche von vorn vor diesem Treffer schneiden:
    So bleibt eine Öffnungsmitte vor ihrem Sacklochboden wählbar, eine
    verdeckte oder abgewandte Ebene aber nicht. Der Fangradius kommt
    aus Bildpunkten, die Abstandsrechnung aus der unveränderten Originalfläche.
    Mitten und Achsen dürfen innerhalb ihrer eigenen Öffnung liegen.
    """
    if not np.isfinite(point).all() or not np.isfinite(maximum_distance) or maximum_distance <= 0.0:
        return ()
    query = np.asarray(point, dtype=np.float64)
    normal = np.asarray(prepared.frame.normal)
    if ray is not None:
        origin, direction = (np.asarray(vector, dtype=np.float64) for vector in ray)
        denominator = float(direction @ normal)
        span = float(np.linalg.norm(direction))
        if (
            not np.isfinite(origin).all()
            or not np.isfinite(direction).all()
            or denominator >= -EPS_GEOM * span
        ):
            return ()
        amount = float((np.asarray(prepared.frame.origin) - origin) @ normal) / denominator
        hit_amount = float((query - origin) @ direction) / float(direction @ direction)
        if amount < 0.0 or amount > hit_amount + EPS_GEOM / span:
            return ()
        query = origin + amount * direction
    elif abs(float((query - prepared.frame.origin) @ normal)) > EPS_GEOM:
        return ()
    found: list[tuple[float, str, str]] = []
    for edge in prepared.edges:
        start, end = np.asarray(edge.start), np.asarray(edge.end)
        step = end - start
        square = float(step @ step)
        if square <= EPS_GEOM * EPS_GEOM:
            continue
        foot = start + np.clip(np.dot(query - start, step) / square, 0.0, 1.0) * step
        distance = float(np.linalg.norm(query - foot))
        if distance <= maximum_distance:
            found.append((distance, edge.id, edge.kind))
    for identifier, centre in prepared.centres:
        distance = float(np.linalg.norm(query - centre))
        if distance <= maximum_distance:
            found.append((distance, identifier, "centre"))
    return tuple((identifier, kind) for _, identifier, kind in sorted(found))


def reference_extension(edge: EdgeReference, point: Vec3) -> tuple[Vec3, Vec3] | None:
    """Nur den nötigen Verlängerungsabschnitt zum Lotfuß ausweisen."""
    start, end = np.asarray(edge.start), np.asarray(edge.end)
    step = end - start
    square = float(step @ step)
    if square <= EPS_GEOM * EPS_GEOM:
        return None
    share = float(np.dot(np.asarray(point) - start, step) / square)
    if 0.0 <= share <= 1.0:
        return None
    return (_vec(start if share < 0.0 else end), _vec(start + share * step))


def _nearest_references(prepared: PreparedSurface, point: Vec3) -> list[EdgeReference]:
    """Zwei unabhängige Randkanten, Außenkanten vor inneren und Achsen.

    Die erste ist die nächste, die zweite die am meisten querstehende, bei
    gleicher Lage die nächste davon (:data:`CROSSING_STEP`).
    Gerechnet wird je Kante derselbe Abstand wie immer; nur der Lotabstand,
    der mit der Kante weiterreist, entsteht erst für die, die gewählt wird —
    nicht als Kopie jeder Kante der Fläche.
    """
    order = {"outer": 0, "inner": 1, "axis": 2}
    here = np.asarray(point)
    ranked = []
    for index, edge in enumerate(prepared.edges):
        start, end = np.asarray(edge.start), np.asarray(edge.end)
        step = end - start
        share = float(np.clip(dot3(here - start, step) / dot3(step, step), 0.0, 1.0))
        distance = math.hypot(*(here - (start + share * step)))
        ranked.append(((order[edge.kind], distance), edge.id, index))
    if not ranked:
        return []
    ranked.sort()
    _rank, _name, first_index = ranked[0]
    first = prepared.edges[first_index]
    chosen = [replace(first, distance=dot3(here - np.asarray(first.start), first.inward))]
    # **Der zweite Bezug ist die Seite, die am meisten quer steht — bei gleicher
    # Lage die nähere.** Bis zum 04.10.2026 war es die nächste unabhängige
    # Kante. An einer eingelesenen Fläche mit gerundeten Ecken ist das ein
    # Facettenstück der Rundung: Am Wedge-Lock und am Tray standen beide Maße an
    # derselben Kante, „Außenkante 56“ und „Außenkante 50“ (Fensterabnahme
    # 04.10.2026). An Quader und Platte wählt die neue Folge dieselbe Kante wie
    # die alte: Dort ist die nächste unabhängige zugleich die querste.
    best: tuple[tuple[int, int, float], EdgeReference] | None = None
    for (kind, distance), _name, index in ranked[1:]:
        edge = prepared.edges[index]
        across = round(abs(dot3(first.inward, edge.inward)) / CROSSING_STEP)
        key = (kind, across, distance)
        if best is not None and key >= best[0]:
            continue
        edge = replace(edge, distance=dot3(here - np.asarray(edge.start), edge.inward))
        if _independent(prepared.frame, [*chosen, edge]):
            best = (key, edge)
    if best is not None:
        chosen.append(best[1])
    return chosen


def at_point(
    prepared: PreparedSurface, point: Vec3, *, references: Sequence[EdgeReference] | None = None
) -> SurfacePlacement:
    """Originalpunkt mit bevorzugten Außenkanten oder ausdrücklich festgehaltenen Bezügen."""
    from shapely.geometry import Point

    from app.core.sketch.planes import to_plane

    if (
        not np.isfinite(point).all()
        or abs(dot3(np.asarray(point) - prepared.frame.origin, prepared.frame.normal)) > EPS_GEOM
    ):
        raise _placement_error()
    xy = to_plane(prepared.frame, point)
    query = Point(xy)
    if not prepared.area.covers(query) and prepared.area.distance(query) > EPS_GEOM:
        raise _placement_error()
    # Der bereits am Originalnetz gemessene Wert bleibt unverändert. Schon
    # eine unnötige Hin-/Rückprojektion verliert hier letzte Float64-Bits.
    point = _vec(point)
    if references is not None:
        # **Festgehaltene Bezüge brauchen keine Rangfolge.** Bis zum 22.09.2026
        # wurde sie trotzdem über jede Randkante gebildet und danach verworfen:
        # An ``plate_holes.stl``, fünfmal unterteilt (815 104 Dreiecke, 2 452
        # Randkanten auf der Oberseite), kostete das 85 ms je Aufruf — im
        # Qt-Hauptthread, beim Loslassen des Platzierungsgriffs (RM-200).
        _checked_references(prepared, references)
        chosen = [
            replace(edge, distance=dot3(np.asarray(point) - edge.start, edge.inward))
            for edge in references
        ]
    else:
        chosen = _nearest_references(prepared, point)
    centres = []
    for feature_id, centre in prepared.centres:
        difference = np.asarray(point) - centre
        offset = (
            dot3(difference, prepared.frame.x_axis),
            dot3(difference, prepared.frame.y_axis),
        )
        centres.append(CentreReference(feature_id, centre, offset, math.hypot(*difference)))
    return SurfacePlacement(
        point,
        prepared.frame.normal,
        replace(prepared.frame, origin=point),
        prepared.planar,
        prepared.face_indices,
        tuple(chosen),
        tuple(sorted(centres, key=lambda centre: (centre.distance, centre.feature_id))),
    )


def point_with_distances(
    prepared: PreparedSurface, placement: SurfacePlacement, distances: tuple[float, float]
) -> SurfacePlacement:
    """Zwei angezeigte Kantenbezüge bearbeiten, ohne zur nächsten Kante zu springen."""
    if len(placement.edges) != 2 or not np.isfinite(distances).all():
        raise _reject(
            "distances",
            tr(
                "Hier fehlen zwei unabhängige Bezugskanten. "
                "Wählen Sie eine ebene Fläche oder setzen Sie den Punkt direkt."
            ),
        )
    frame = prepared.frame
    _checked_references(prepared, placement.edges)
    rows, offsets = [], []
    for edge, distance in zip(placement.edges, distances, strict=True):
        rows.append((dot3(edge.inward, frame.x_axis), dot3(edge.inward, frame.y_axis)))
        offsets.append(distance + dot3(np.asarray(edge.start) - frame.origin, edge.inward))
    values = _solved_distances(np.asarray(rows, dtype=np.float64), offsets)
    from app.core.sketch.planes import to_world

    result = at_point(prepared, to_world(frame, _vec2(values)))
    return replace(
        result,
        edges=tuple(
            replace(edge, distance=float(distance))
            for edge, distance in zip(placement.edges, distances, strict=True)
        ),
    )


def point_with_centre(
    prepared: PreparedSurface,
    surface: SurfacePlacement,
    centre_id: str,
    offset: Point2,
) -> SurfacePlacement:
    """U/V vom benannten Bohrungsmittelpunkt zum Zielpunkt, in der wirklichen Flächenebene."""
    reference = next((item for item in surface.centres if item.feature_id == centre_id), None)
    if (
        not prepared.planar
        or reference is None
        or not any(
            identifier == centre_id and np.allclose(point, reference.point, atol=EPS_GEOM, rtol=0.0)
            for identifier, point in prepared.centres
        )
        or not np.isfinite(offset).all()
    ):
        raise _reject(
            "centre",
            tr("Diese Bohrungsmitte ist hier nicht verfügbar. Wählen Sie die Fläche erneut."),
        )
    target = (
        np.asarray(reference.point, dtype=np.float64)
        + offset[0] * np.asarray(prepared.frame.x_axis)
        + offset[1] * np.asarray(prepared.frame.y_axis)
    )
    return at_point(prepared, _vec(target), references=surface.edges)


def _surface_primitives() -> frozenset[str]:
    """Die fünf Grundkörper in beiden Kernen — seit P2.8 ist der sichtbare der exakte."""
    from app.core.registry import PRIMITIVE_TWINS

    return frozenset(name for pair in PRIMITIVE_TWINS for name in pair)


def _mesh_primitive_name(name: str) -> str:
    """Der Netzname eines Grundkörpers — ``primitive_local_tool`` kennt nur diese."""
    from app.core.registry import PRIMITIVE_TWINS

    return next((mesh for mesh, brep in PRIMITIVE_TWINS if brep == name), name)


def supports_surface_placement(spec: OperationSpec) -> bool:
    """Fachliche absolute Platzierung, unabhängig von zufällig gleich benannten Feldern."""
    from app.core.knowledge.parts.ops import part_of

    return (
        spec.name in DRILL_OPERATIONS
        or spec.name
        in {
            "label_text",
            "create_label",
            # Die bündige Einlage sitzt wie die Beschriftung (RM-184).
            "inlay_text",
            "move_feature",
            "duplicate_feature",
            # **Ein Langloch wird gesetzt wie eine Bohrung** (Robert,
            # 10.09.2026: „einfach wie wenn ich eine bohrung setze"). Es sitzt
            # auf einer Fläche, es hat eine Mitte, und seine Maße zu den Kanten
            # sind dieselbe Frage — also bekommt es dieselbe Bedienung, statt
            # einer zweiten daneben.
            "slot_hole",
            # Und dasselbe beim Ändern: Wer den Durchmesser einer Bohrung
            # bewegt, will dabei sehen, wo sie sitzt.
            "resize_hole",
        }
        or spec.name in _surface_primitives()
        or part_of(spec.name) is not None
    )


def surface_values(
    spec: OperationSpec,
    placement: SurfacePlacement,
    feature: Feature | None = None,
    source: SceneObject | None = None,
    prepared_tool: PlacementTool | None = None,
    mouth: Vec3 | None = None,
) -> dict[str, Any]:
    """Reproduzierbare Op-Werte für einen echten Flächentreffer, ohne Feature zu erfinden.

    ``mouth`` ist bei *Zum Langloch ziehen* und *Bohrung ändern* die eigene
    Mündung des Lochs auf der Fläche des Treffers, der Durchstoßpunkt seiner
    Achse — aus :func:`seat_of`, wo die Platzierung am Merkmal begann, sonst
    aus :func:`mouth_on`. Nur auf ihrer Ebene rückt die Mitte nicht um eine
    Fase in die Achse; ``None`` heißt: Die Fläche ist nicht die eigene, und
    die Mündung liegt auf ihr.
    """
    from app.core.knowledge.parts.ops import normal_fields, placement_fields

    if not supports_surface_placement(spec):
        raise _reject(
            "operation",
            tr(
                "Diese Operation setzt kein Element auf eine Fläche. "
                "Wählen Sie eine Bohrung, einen Baustein oder eine Beschriftung."
            ),
        )
    target = placement.point
    if spec.name in {"slot_hole", "resize_hole"} and feature is not None:
        # **Die Mündung ist nicht die Mitte.** Ein durchgehendes Loch hat seine
        # Mitte auf halber Tiefe; die Fläche, auf die gezeigt wird, liegt
        # darüber. ``slot_hole`` führt die **Mitte**, also wird hier
        # umgerechnet — dieselbe Rechnung wie ``anchor="mouth"`` bei
        # *Bohrung setzen*, nur an einem Loch, das es schon gibt.
        depth = feature.params.get("depth")
        axis = feature.params.get("axis")
        if not isinstance(depth, int | float) or axis is None:
            # **Ohne Tiefe oder Achse gibt es keine Mitte** (Regel 21). Bis zum
            # 11.09.2026 blieb `target` dann die **Mündung** und wanderte als
            # Mitte weiter — das Loch saß um die halbe Tiefe daneben, ohne
            # Befund und ohne Absage. `seat_of` beantwortet dieselbe Frage seit
            # je mit `None`; hier steht sie jetzt genauso.
            raise _reject(
                "at_feature",
                tr("Zu diesem Merkmal sind Tiefe und Achse nicht bekannt."),
            )
        along = np.asarray(axis, dtype=float)
        span = float(np.linalg.norm(along))
        if span <= EPS_GEOM:
            raise _reject(
                "at_feature",
                tr("Zu diesem Merkmal ist keine Achse bekannt."),
            )
        # **Die Mündung liegt auf der Seite, auf die die Achse zeigt** — und
        # nach einem freien Klick muss das nicht mehr gelten: Wer die
        # Gegenfläche trifft, bekäme das Loch um die volle Tiefe versetzt.
        # Das Vorzeichen kommt deshalb aus der Fläche, auf der gerade gezielt
        # wird, nicht aus der Achse allein.
        facing = float(np.asarray(placement.frame.normal, dtype=float) @ (along / span))
        towards = 1.0 if facing >= 0.0 else -1.0
        half = float(depth) / 2.0
        centre = feature.params.get("centre")
        if centre is not None and mouth is not None:
            # **Hinter einer Fase liegt die Fläche weiter draußen als die
            # Mündung** (:func:`seat_of`). Auf der eigenen Mündungsfläche
            # ersetzt ihr Abstand zur Mitte die halbe Tiefe, sonst rückte die
            # Mitte um die Fase in die Achse — an einem Sackloch hieße das ein
            # anderes Loch. **Nur dort** (G5, 25.09.2026): Eine fremde Fläche
            # parallel im selben Fenster ist keine Fase, und wer auf sie
            # versetzt, meint die Mündung auf ihr.
            #
            # **Gemessen wird an der Mündung, nicht am Ziel.** Die gemessene
            # Achse steht um Rechenrauschen schief (am Schaber 1,5 µrad), und
            # der Abstand des *versetzten* Punkts zur alten Mitte entlang
            # dieser Achse wuchs mit dem Versatz: 43 mm weiter lag die Mitte
            # 2,9 µm höher, und ``move_to`` las das beim nächsten Tastendruck
            # als getippte Tiefe — die Maßgruppe ging ans Merkmalfenster.
            lifted = sum(
                (float(target[index]) - float(mouth[index])) * float(placement.frame.normal[index])
                for index in range(3)
            )
            beyond = towards * sum(
                (float(mouth[index]) - float(centre[index])) * float(along[index]) / span
                for index in range(3)
            )
            if abs(lifted) <= MAX_FACET_SAG and (
                half - MAX_FACET_SAG <= beyond <= half + mouth_reach(feature)
            ):
                half = beyond
        target = _vec(np.asarray(target) - along / span * towards * half)
    elif spec.name in {"move_feature", "duplicate_feature"}:
        if feature is None or source is None:
            raise _reject(
                "feature", tr("Wählen Sie zuerst das Merkmal, das an die neue Stelle gehört.")
            )
        if prepared_tool is None:
            from app.core.geom.prepare_ops import feature_placement_geometry

            offset = feature_placement_geometry(source, feature, spec.name).selected_offset
        else:
            if prepared_tool.feature_id != feature.id or prepared_tool.selected_offset is None:
                raise _reject(
                    "feature", tr("Wählen Sie zuerst das Merkmal, das an die neue Stelle gehört.")
                )
            offset = prepared_tool.selected_offset
        matrix = np.column_stack((placement.frame.x_axis, placement.frame.y_axis, placement.normal))
        target = _vec(np.asarray(placement.point) + matrix @ offset)
    placed_fields = placement_fields(spec.params)
    values: dict[str, Any] = dict(
        zip((placed_fields[name] for name in POSITION), target, strict=True)
    )
    values.update(zip(normal_fields(spec.params), placement.normal, strict=True))
    if spec.name in DRILL_OPERATIONS:
        values["anchor"] = "mouth"
    if any(field.name == placed_fields[FEATURE_FIELD] for field in spec.params.spec()):
        values[placed_fields[FEATURE_FIELD]] = (
            feature.id if spec.name in AT_AN_EXISTING_FEATURE and feature is not None else ""
        )
    return values


#: Arbeitsbudget der Originalauswahl; keine geometrische Auflösungsgrenze.
PICK_TRIANGLE_BLOCK: Final = 65_536


def original_surface_hit(
    mesh: MeshData,
    origin: Vec3,
    direction: Vec3,
    *,
    clip_origin: Vec3 | None = None,
    clip_normal: Vec3 | None = None,
    clip_planes: Sequence[SectionPlane] = (),
    check_cancelled: Callable[[], None] | None = None,
) -> tuple[int, Vec3] | None:
    """Den Sichtstrahl am Originalnetz schneiden; LOD-Zellen liefern keine Modellkoordinaten."""
    from app.core.geom.mesh import ray_hits

    vector = np.asarray(direction, dtype=np.float64)
    length = float(np.linalg.norm(vector))
    if not np.isfinite(origin).all() or not np.isfinite(vector).all() or length <= EPS_GEOM:
        return None
    vector /= length
    eye = np.asarray(origin, dtype=np.float64)
    vertices, faces = np.asarray(mesh.raw.vertices), np.asarray(mesh.raw.faces)
    nearest = float("inf")
    selected: tuple[int, Vec3] | None = None
    for start in range(0, len(faces), PICK_TRIANGLE_BLOCK):
        if check_cancelled is not None:
            check_cancelled()
        triangles = vertices[faces[start : start + PICK_TRIANGLE_BLOCK]]
        distances, indices = ray_hits(triangles, eye, vector)
        points = eye + distances[:, None] * vector
        visible = distances < nearest
        if clip_origin is not None and clip_normal is not None:
            visible &= (points - clip_origin) @ np.asarray(clip_normal) >= -EPS_GEOM
        for plane in clip_planes:
            # SectionPlane entfernt ihre positive Seite; mehrere Ebenen sind
            # eine Schnittmenge sichtbarer Halbebenen. Kappen entstehen hier nie.
            visible &= (points - plane.origin) @ np.asarray(plane.normal) <= EPS_GEOM
        distances, indices, points = distances[visible], indices[visible], points[visible]
        if len(distances):
            closest = int(np.argmin(distances))
            nearest = float(distances[closest])
            selected = (start + int(indices[closest]), _vec(points[closest]))
    if check_cancelled is not None:
        check_cancelled()
    return selected


def placement_tool(
    spec: OperationSpec,
    entered_values: Mapping[str, Any],
    profile: Profile,
    *,
    source: SceneObject | None = None,
    feature: Feature | None = None,
    parameters: Mapping[str, float] | None = None,
) -> MeshData:
    """Der wirkliche lokale Werkzeugkörper; ausschließlich für die temporäre Vorschau."""
    return prepare_tool(
        spec, entered_values, profile, source=source, feature=feature, parameters=parameters
    ).mesh


def prepare_tool(
    spec: OperationSpec,
    entered_values: Mapping[str, Any],
    profile: Profile,
    *,
    source: SceneObject | None = None,
    feature: Feature | None = None,
    parameters: Mapping[str, float] | None = None,
) -> PlacementTool:
    """Werkzeug und Merkmalsbezug einmal im Worker berechnen und gemeinsam aufbewahren."""
    if spec.name in {"move_feature", "duplicate_feature"}:
        if feature is None or source is None:
            raise _reject(
                "feature", tr("Wählen Sie zuerst das Merkmal, das an die neue Stelle gehört.")
            )
        from app.core.geom.prepare_ops import feature_placement_geometry

        geometry = feature_placement_geometry(source, feature, spec.name)
        return PlacementTool(geometry.mesh, geometry.selected_offset, feature.id)
    from app.core.knowledge.parts.ops import part_of, placement_tools
    from app.core.knowledge.profiles import for_object

    part = part_of(spec.name)
    if part is not None:
        primary, addition = placement_tools(
            part,
            entered_values,
            for_object(profile, source),
            standalone=spec.consumes == 0,
            parameters=parameters,
        )
        return PlacementTool(primary, addition=addition)
    return _creation_tool(spec, entered_values, profile, source=source)


def _feature_named(source: SceneObject | None, name: str) -> Feature | None:
    """Das erkannte Merkmal dieses Körpers — oder ``None``.

    Die Vorschau eines vorhandenen Lochs liest seine Maße von dort; ohne
    Körper oder ohne Kennung gibt es nichts zu lesen, und geraten wird nichts
    (Regel 21).
    """
    if source is None or not name:
        return None
    return source.features.get(name)


def _outward_drill_axis(values: Any, source: SceneObject | None) -> Vec3:
    """Die gespeicherte oder am Kernpfad aufgelöste Außenachse einer Bohrung."""
    from app.core.geom.prepare import (
        AXIS_INDEX,
        drill_outward_axis,
        drill_outward_axis_from_bounds,
    )

    normal = (float(values.nx), float(values.ny), float(values.nz))
    length = math.hypot(*normal)
    if length > EPS_GEOM:
        return (normal[0] / length, normal[1] / length, normal[2] / length)

    axis = values.axis
    index = AXIS_INDEX[axis]
    position = (float(values.x), float(values.y), float(values.z))
    if source is None:
        direction = [0.0, 0.0, 0.0]
        direction[index] = 1.0
        return (direction[0], direction[1], direction[2])
    elif source.kind == "brep":
        # Dieselbe Kernentscheidung liegt im BRep-Werkzeugweg über dem Netz.
        bounds_centre = source.mesh.bounds.centre
        centre = (
            float(bounds_centre[0]),
            float(bounds_centre[1]),
            float(bounds_centre[2]),
        )
        return drill_outward_axis_from_bounds(axis, position, centre)
    else:
        # Der Netzkern prüft zuerst die offene Strahlseite, dann die Materialsäule.
        return drill_outward_axis(as_mesh_data(source.mesh), axis, position)


def _creation_tool(
    spec: OperationSpec,
    entered_values: Mapping[str, Any],
    profile: Profile,
    *,
    source: SceneObject | None = None,
) -> PlacementTool:
    """Werkzeug samt den Achsen und Winkeln der tatsächlichen Vorschau vorbereiten."""
    from app.core.knowledge.parts.ops import part_of
    from app.core.knowledge.profiles import for_object
    from app.core.registry.params import validate

    profile = for_object(profile, source)
    if spec.name in _surface_primitives():
        from app.core.geom.primitive_ops import primitive_local_tool
        from app.core.registry import REGISTRY

        # Die Vorschau ist ein Netz, auch für den exakten Erzeuger: dasselbe
        # Werkzeug wie beim Netz-Zwilling, gegen dessen Schema geprüft (die
        # Vorgaben füllen ``segments`` und ``anchor``, wo der exakte sie nicht hat).
        mesh_name = _mesh_primitive_name(spec.name)
        checked = validate(REGISTRY.get(mesh_name).params, entered_values)
        return PlacementTool(primitive_local_tool(mesh_name, checked.as_dict(), "fine"))
    part = part_of(spec.name)
    if part is not None:
        from app.core.knowledge.parts.ops import placement_tool as part_tool

        return PlacementTool(part_tool(part, entered_values, profile))
    if spec.name in DRILL_OPERATIONS:
        from app.core.geom.prepare import drill_tool
        from app.core.geom.prepare_ops import bore_shape

        values: Any = validate(spec.params, entered_values)
        # Die Hülldiagonale reicht in jeder freien Richtung durch den Zielkörper.
        # Ohne Zielkörper bleibt der Bauraum die obere Grenze der Vorschau.
        depth = float(values.depth) or (
            source.mesh.bounds.diagonal
            if source is not None
            else float(np.linalg.norm(profile.printer.build_volume))
        )
        # Dieselbe Abwägung wie in der Operation: Was der Haken *Langloch*
        # abschaltet, darf auch die Vorschau nicht zeigen — sonst steht dort
        # eine Senkung, die der fertige Schnitt nicht hat.
        shape = bore_shape(values)
        raw_axis = (float(values.nx), float(values.ny), float(values.nz))
        position_dependent_axis = (
            bool(values.measured_frame) and source is not None and math.hypot(*raw_axis) <= EPS_GEOM
        )
        return PlacementTool(
            drill_tool(
                diameter=float(values.diameter),
                depth=depth,
                profile=profile,
                compensate=bool(values.compensate),
                widening_diameter=shape.widening_diameter,
                widening_depth=shape.widening_depth,
                transition_angle=float(values.transition_angle),
                slot_length=shape.slot_length,
                slot_angle=shape.slot_angle,
            ),
            outward_axis=(_outward_drill_axis(values, source) if values.measured_frame else None),
            angle=shape.slot_angle if shape.slot_length > EPS_GEOM else None,
            position_dependent_axis=position_dependent_axis,
        )
    if spec.name in {"slot_hole", "resize_hole"}:
        from app.core.geom.prepare import (
            bore_diameter,
            drill_tool,
            is_round_length,
            slot_angle_from_measured_frame,
            slot_travel,
        )

        # **Ein Loch, das schon da ist, hat seine Maße am Merkmal.** Die zwei
        # Operationen tragen nur, was sich ändern soll — die Länge, den
        # Durchmesser —, und lesen Mitte, Achse und Tiefe aus dem erkannten
        # Merkmal. Die Vorschau braucht denselben Körper, und ohne ihn blieb
        # *Übernehmen* grau: `PlacementFlow` gibt den Knopf nur frei, wenn ein
        # Werkzeug steht (Fund des Reviews, 11.09.2026).
        values = validate(spec.params, entered_values)
        feature = _feature_named(source, str(getattr(values, "at_feature", "") or ""))
        if feature is None:
            raise _reject(
                "at_feature",
                tr("Zu dieser Kennung gibt es kein Merkmal. Wählen Sie es im Bild erneut."),
            )
        measured = float(feature.params.get("diameter") or 0.0)
        depth = float(feature.params.get("depth") or 0.0)
        if measured <= 0.0 or depth <= 0.0:
            raise _reject(
                "at_feature",
                tr("Zu diesem Merkmal sind Durchmesser und Tiefe nicht bekannt."),
            )
        if spec.name == "resize_hole":
            cut = bore_diameter(
                float(values.diameter), profile, bool(getattr(values, "compensate", False))
            )
            length = 0.0
            angle = 0.0
            if feature.kind == "slot":
                from app.core.geom.prepare_ops import slot_angle_of

                # Die Breitenänderung erhält wie die Op den vorhandenen Weg.
                length = float(feature.params["travel"]) + cut
                angle = slot_angle_of(feature, tuple(feature.params["axis"]))
        else:
            cut = (
                measured
                if values.diameter is None
                else bore_diameter(float(values.diameter), profile, bool(values.compensate))
            )
            length = float(values.slot_length)
            angle = float(values.slot_angle)
            if values.measured_frame:
                angle = slot_angle_from_measured_frame(tuple(feature.params["axis"]), angle)
            # **Genau die Breite heißt rund** (:func:`prepare.is_round_length`),
            # dieselbe Frage wie im Kern und am Griff: Die Vorschau zeigt die
            # Bohrung, zu der das Langloch zurückgeht. Sonst ist eine Länge
            # unter dem Durchmesser kein Langloch; der Kern lehnt sie ab, und
            # die Vorschau soll nicht zeigen, was danach nicht kommt.
            width = measured if values.diameter is None else float(values.diameter)
            if (
                is_round_length(length, width)
                or is_round_length(length, cut)
                or slot_travel(diameter=cut, length=length) <= 0.0
            ):
                length = 0.0
        return PlacementTool(
            drill_tool(
                diameter=cut,
                depth=depth,
                profile=profile,
                # **Schon gerechnet.** ``bore_diameter`` oben hat die Toleranz
                # aufgeschlagen, wo sie gilt; ein zweites Mal wäre sie zweimal drauf.
                compensate=False,
                slot_length=length,
                slot_angle=angle,
            ),
            angle=angle if length > EPS_GEOM else None,
        )
    if spec.name in {"label_text", "create_label", "inlay_text"}:
        from app.core.geom.label_layout import wrapped
        from app.core.geom.label_ops import local_text_body

        values = validate(spec.params, entered_values)
        modes = {
            "label_text": values.mode if spec.name == "label_text" else "",
            "inlay_text": "engraved",
        }
        letters = local_text_body(
            values.text,
            values.size,
            values.font,
            values.depth,
            # Der Schnitt gehört zur Form, nicht zur Farbe: Fett ist rund
            # anderthalbmal so breit wie normal. Ohne ihn zeigte die Vorschau
            # den normalen und die Operation baute den gewählten.
            style=values.style,
            mode=cast(Literal["raised", "engraved", "body"], modes.get(spec.name) or "body"),
            angle=getattr(values, "angle", 0.0),
            # Bogen und Rundung gehören zur Form wie der Schnitt (RM-184).
            arc_radius=getattr(values, "arc_radius", 0.0),
        )
        # Eine genannte Rundung biegt auch die Vorschau; eine erst zu messende
        # zeigt sie flach, bis der Schritt den Radius festhält.
        if getattr(values, "wrap", "flat") != "flat" and getattr(values, "wrap_radius", 0.0):
            letters = wrapped(letters, float(values.wrap_radius), values.wrap)
        return PlacementTool(letters)
    raise _reject(
        "operation",
        tr(
            "Diese Operation setzt kein Element auf eine Fläche. "
            "Wählen Sie eine Bohrung, einen Baustein oder eine Beschriftung."
        ),
    )
