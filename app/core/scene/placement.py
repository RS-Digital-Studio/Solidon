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

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING, Any, Final

import numpy as np

from app.core.geom.mesh import MeshData
from app.core.log import get_logger
from app.core.registry import OperationSpec
from app.core.types import Feature, PlaneFrame, Point2, Profile, SceneObject, Vec3, vec3_or_none
from app.core.units import EPS_GEOM, format_length, round_display
from app.i18n import tr

if TYPE_CHECKING:
    from shapely.geometry.base import BaseGeometry

    from app.core.geom.section import SectionPlane

_log = get_logger(__name__)

#: Der Parameter, mit dem ein Baustein das Merkmal benennt, an das er gehört.
#: Wo eine Operation ihn hat, ist das die ganze Antwort: die Position daneben
#: zählt als Versatz vom Merkmal und bleibt auf null.
FEATURE_FIELD = "at_feature"

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


def bore_advice(
    diameter: float,
    *,
    ask: bool = True,
    measured: str | None = None,
    feature: Feature | None = None,
    features: Mapping[str, Feature] | None = None,
    mesh: MeshData | None = None,
    cavity: tuple[Feature, ...] | None = None,
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
    """
    measured = measured if measured is not None else format_length(diameter, with_unit=False)
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
                "Diese Aufweitung misst {measure} mm. Die Schraubengröße richtet sich "
                "nach der engeren Bohrung."
            ).replace("{measure}", measured), []
    size = screw_for_bore(diameter)
    if size is not None:
        # Ganze Sätze mit Platzhaltern statt zusammengesetzter Halbsätze: Wer
        # nur „das Durchgangsloch für" zu übersetzen bekommt, weiß nicht, was
        # danach steht — und in mancher Sprache steht es davor.
        said = tr("Diese Bohrung misst {measure} mm — das Durchgangsloch für {screw}.")
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
        [*_sizes_around(diameter), tr("Selbst eintragen")],
    )


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
    """
    diameter = feature.params.get("diameter")
    if diameter is None:
        return None
    size = screw_for_bore(float(diameter))
    if size is None:
        return None
    from app.core.knowledge import standards

    return round(standards.screw(size).countersink, 4)


def _sizes_around(diameter: float) -> list[str]:
    """Die Größen unter und über einer Bohrung, die zu keiner passt.

    Beide oder eine — an den Enden der Tabelle gibt es keine zweite Seite, und
    eine erfundene wäre schlechter als eine kurze Liste.
    """
    from app.core.knowledge import standards

    # Die Reihenfolge der Tabelle ist aufsteigend; die Bausteine rechnen seit je
    # damit (``size_for_insert`` nimmt die erste passende als die kleinste).
    below = [size for size in standards.screw_sizes() if standards.screw(size).clearance < diameter]
    above = [size for size in standards.screw_sizes() if standards.screw(size).nominal > diameter]
    return [*below[-1:], *above[:1]]


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
    return next((entry.name for entry in spec.params.spec() if entry.targets_feature), "")


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


def values_for(spec: OperationSpec, feature: Feature) -> dict[str, Any]:
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
    field = next(
        (entry.name for entry in spec.params.spec() if entry.kind == "feature"),
        None,
    )
    if field is not None:
        feature_values = {field: feature.id, **_from_the_bore(spec, feature, names)}
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
    target = _target_field(spec)
    if target and feature.kind == "face":
        # „Bis zu dieser Fläche" — die Kennung reicht, den Rahmen rechnet die
        # Auswertung daraus (app.core.sketch.planes). Nur planare Flächen: bis
        # zu einer Bohrung zu extrudieren hat keine Bedeutung.
        values[target] = feature.id
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
    """
    face = top_face(features)
    if face is None:
        return {}
    values = values_for(spec, face)
    values.pop(FEATURE_FIELD, None)
    target = _target_field(spec)
    if target:
        values.pop(target, None)
    return values


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


def _vec(values: Any) -> Vec3:
    return (float(values[0]), float(values[1]), float(values[2]))


def _placement_error() -> ValueError:
    return ValueError(
        tr(
            "Dieser Punkt liegt außerhalb der gewählten Fläche. "
            "Wählen Sie einen Punkt auf dem Material oder ändern Sie die Abstände."
        )
    )


def _patch_faces(mesh: MeshData, face_index: int) -> tuple[tuple[int, ...], bool]:
    """Zusammenhängende koplanare Originaldreiecke, ohne Koordinatenrundung."""
    from app.core.perceive.features import CURVATURE_LIMIT, EPS_ANGLE

    raw = mesh.raw
    if face_index < 0 or face_index >= len(raw.faces):
        raise ValueError(
            tr("Diese Fläche ist nicht mehr vorhanden. Klicken Sie das Modell erneut an.")
        )
    vertices = np.asarray(raw.vertices, dtype=np.float64)
    normals = np.asarray(raw.face_normals, dtype=np.float64)
    normal = normals[face_index]
    if not np.isfinite(normal).all() or np.linalg.norm(normal) <= EPS_GEOM:
        raise ValueError(
            tr(
                "Diese Fläche hat keine brauchbare Richtung. "
                "Wählen Sie eine andere Stelle auf dem Modell."
            )
        )
    # Exakte Ortsgleichheit verbindet auch unverschweißte STL-Dreiecke. Kein
    # Abstandsschwellwert darf einen tatsächlichen schmalen Spalt schließen.
    _, inverse = np.unique(vertices, axis=0, return_inverse=True)
    faces = inverse[np.asarray(raw.faces, dtype=np.int64)]
    edges = np.sort(faces[:, [[0, 1], [1, 2], [2, 0]]].reshape(-1, 2), axis=1)
    _, edge_ids = np.unique(edges, axis=0, return_inverse=True)
    owners: dict[int, list[int]] = {}
    for index, edge_id in enumerate(edge_ids):
        owners.setdefault(int(edge_id), []).append(index // 3)
    adjacency: dict[int, list[int]] = {}
    for entries in owners.values():
        if len(entries) == 2:
            a, b = entries
            adjacency.setdefault(a, []).append(b)
            adjacency.setdefault(b, []).append(a)
    origin = vertices[np.asarray(raw.faces)[face_index, 0]]
    triangles = np.asarray(raw.triangles, dtype=np.float64)
    coplanar = (normals @ normal >= np.cos(np.radians(EPS_ANGLE))) & (
        np.max(np.abs((triangles - origin) @ normal), axis=1) <= EPS_GEOM
    )
    found = {face_index}
    pending = [face_index]
    while pending:
        current = pending.pop()
        for other in adjacency.get(current, ()):
            if other not in found and coplanar[other]:
                found.add(other)
                pending.append(other)
    border_angles = [
        float(np.degrees(np.arccos(np.clip(normals[index] @ normals[other], -1.0, 1.0))))
        for index in found
        for other in adjacency.get(index, ())
        if other not in found
    ]
    # Dieselbe Krümmungsgrenze wie die Merkmalsanalyse: Mantelstreifen und
    # kleine Kugeldreiecke versprechen keine Maße einer ebenen Konstruktionsfläche.
    smooth = sum(EPS_ANGLE < angle < CURVATURE_LIMIT for angle in border_angles)
    planar = not border_angles or smooth * 2 < len(border_angles)
    return tuple(sorted(found)), planar


def _straight_boundary(
    coords: Any,
    round_points: Sequence[np.ndarray] = (),
    round_circles: Sequence[tuple[np.ndarray, float]] = (),
) -> list[tuple[np.ndarray, np.ndarray]]:
    """Kollineare Randstücke vereinen; Kreisfacetten sind keine geraden Bezugskanten."""
    points = np.asarray(coords, dtype=np.float64)[:-1]
    if len(points) >= 8 and (round_points or round_circles):
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
            if any(
                np.linalg.norm(centre - known_centre) <= EPS_GEOM
                and abs(radius - known_radius) <= EPS_GEOM
                for known_centre, known_radius in round_circles
            ) or any(
                np.max(cKDTree(known_points).query(points)[0]) <= EPS_GEOM
                for known_points in round_points
            ):
                return []
    keep = []
    for index, point in enumerate(points):
        before, after = points[index - 1], points[(index + 1) % len(points)]
        one, two = point - before, after - point
        cross = one[0] * two[1] - one[1] * two[0]
        if (
            abs(cross) > EPS_GEOM * max(np.linalg.norm(one), np.linalg.norm(two))
            or np.dot(one, two) < 0.0
        ):
            keep.append(point)
    return [(start, keep[(index + 1) % len(keep)]) for index, start in enumerate(keep)]


def prepare_surface(
    mesh: MeshData, face_index: int, features: Mapping[str, Feature] | None = None
) -> PreparedSurface:
    """Originalfläche und Maße einmal vorbereiten; der Aufrufer hält den Kontext im Cache."""
    from shapely import prepare, union_all
    from shapely.geometry import Point, Polygon

    from app.core.sketch.planes import frame_of, to_plane, to_world

    indices, planar = _patch_faces(mesh, face_index)
    normal = _vec(mesh.raw.face_normals[face_index])
    frame = frame_of(normal, _vec(mesh.raw.triangles[face_index, 0]))
    triangles = np.asarray(mesh.raw.triangles)[list(indices)]
    relative = triangles - frame.origin
    xy = np.stack((relative @ frame.x_axis, relative @ frame.y_axis), axis=-1)
    area = union_all([Polygon(triangle) for triangle in xy])
    if area.is_empty or not area.is_valid or area.geom_type != "Polygon":
        raise ValueError(
            tr(
                "Diese Fläche ist nicht eindeutig zusammenhängend. "
                "Wählen Sie eine andere Stelle auf dem Modell."
            )
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
            length = float(np.linalg.norm(vector))
            if length <= EPS_GEOM or abs(float(vector @ frame.normal) / length) < 1.0 - EPS_GEOM:
                continue
            if feature.face_indices:
                vertices = np.asarray(mesh.raw.triangles)[list(feature.face_indices)].reshape(-1, 3)
                relative = vertices - frame.origin
                rim = relative[np.abs(relative @ frame.normal) <= EPS_GEOM]
                if len(rim):
                    round_points.append(np.column_stack((rim @ frame.x_axis, rim @ frame.y_axis)))
            elif feature.kind in {"hole", "pin"}:
                depth = float(feature.params.get("depth", 0.0))
                distance = abs(float((np.asarray(centre) - frame.origin) @ frame.normal))
                if distance <= depth / 2.0 + EPS_GEOM:
                    round_circles.append(
                        (
                            np.asarray(to_plane(frame, centre)),
                            float(feature.params["diameter"]) / 2.0,
                        )
                    )
        for ring in (area.exterior, *area.interiors):
            for start, end in _straight_boundary(ring.coords, round_points, round_circles):
                direction = end - start
                direction /= np.linalg.norm(direction)
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
                    )
                )
    centres = []
    for feature in (features or {}).values():
        centre, axis = (
            vec3_or_none(feature.params.get("centre")),
            vec3_or_none(feature.params.get("axis")),
        )
        if feature.kind != "hole" or centre is None or axis is None:
            continue
        vector = np.asarray(axis, dtype=np.float64)
        length = float(np.linalg.norm(vector))
        if length <= EPS_GEOM or abs(float(vector @ frame.normal) / length) < 1.0 - EPS_GEOM:
            continue
        # Ein Zylinderzentrum liegt meist in der Wandmitte. Sein Achsschnitt
        # mit genau dieser Ebene ist die nutzbare Mitte an der Mündung.
        amount = np.dot(np.asarray(frame.origin) - centre, frame.normal) / np.dot(
            vector, frame.normal
        )
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
    prepare(area)
    return PreparedSurface(frame, planar, indices, tuple(references), tuple(centres), area)


def _vec2(values: Any) -> Point2:
    return (float(values[0]), float(values[1]))


def at_point(prepared: PreparedSurface, point: Vec3) -> SurfacePlacement:
    """Ein bereits belegter Originalpunkt und die nächsten unabhängigen Maße."""
    from shapely.geometry import Point

    from app.core.sketch.planes import to_plane

    if (
        not np.isfinite(point).all()
        or abs(float(np.dot(np.asarray(point) - prepared.frame.origin, prepared.frame.normal)))
        > EPS_GEOM
    ):
        raise _placement_error()
    xy = to_plane(prepared.frame, point)
    query = Point(xy)
    if not prepared.area.covers(query) and prepared.area.distance(query) > EPS_GEOM:
        raise _placement_error()
    # Der bereits am Originalnetz gemessene Wert bleibt unverändert. Schon
    # eine unnötige Hin-/Rückprojektion verliert hier letzte Float64-Bits.
    point = _vec(point)
    ranked = []
    for edge in prepared.edges:
        start, end = np.asarray(edge.start), np.asarray(edge.end)
        step = end - start
        share = float(
            np.clip(np.dot(np.asarray(point) - start, step) / np.dot(step, step), 0.0, 1.0)
        )
        distance = float(np.linalg.norm(np.asarray(point) - (start + share * step)))
        ranked.append(
            (
                distance,
                edge.id,
                replace(edge, distance=float(np.dot(np.asarray(point) - start, edge.inward))),
            )
        )
    chosen: list[EdgeReference] = []
    for _, _, edge in sorted(ranked, key=lambda item: (item[0], item[1])):
        if not chosen or abs(float(np.dot(edge.inward, chosen[0].inward))) < 1.0 - EPS_GEOM:
            chosen.append(edge)
        if len(chosen) == 2:
            break
    centres = []
    for feature_id, centre in prepared.centres:
        difference = np.asarray(point) - centre
        offset = (
            float(difference @ prepared.frame.x_axis),
            float(difference @ prepared.frame.y_axis),
        )
        centres.append(
            CentreReference(feature_id, centre, offset, float(np.linalg.norm(difference)))
        )
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
        raise ValueError(
            tr(
                "Hier fehlen zwei unabhängige Bezugskanten. "
                "Wählen Sie eine ebene Fläche oder setzen Sie den Punkt direkt."
            )
        )
    frame = prepared.frame
    rows, offsets = [], []
    for edge, distance in zip(placement.edges, distances, strict=True):
        rows.append((np.dot(edge.inward, frame.x_axis), np.dot(edge.inward, frame.y_axis)))
        offsets.append(distance + np.dot(np.asarray(edge.start) - frame.origin, edge.inward))
    values = np.linalg.solve(
        np.asarray(rows, dtype=np.float64), np.asarray(offsets, dtype=np.float64)
    )
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
        or not any(identifier == centre_id for identifier, _ in prepared.centres)
        or not np.isfinite(offset).all()
    ):
        raise ValueError(
            tr("Diese Bohrungsmitte ist hier nicht verfügbar. Wählen Sie die Fläche erneut.")
        )
    target = (
        np.asarray(reference.point, dtype=np.float64)
        + offset[0] * np.asarray(prepared.frame.x_axis)
        + offset[1] * np.asarray(prepared.frame.y_axis)
    )
    return at_point(prepared, _vec(target))


_SURFACE_PRIMITIVES = frozenset(
    {"create_box", "create_cylinder", "create_cone", "create_sphere", "create_torus"}
)


def supports_surface_placement(spec: OperationSpec) -> bool:
    """Fachliche absolute Platzierung, unabhängig von zufällig gleich benannten Feldern."""
    from app.core.knowledge.parts.ops import part_of

    return (
        spec.name
        in {"drill_hole", "label_text", "create_label", "move_feature", "duplicate_feature"}
        or spec.name in _SURFACE_PRIMITIVES
        or part_of(spec.name) is not None
    )


def surface_values(
    spec: OperationSpec,
    placement: SurfacePlacement,
    feature: Feature | None = None,
    source: SceneObject | None = None,
    prepared_tool: PlacementTool | None = None,
) -> dict[str, Any]:
    """Reproduzierbare Op-Werte für einen echten Flächentreffer, ohne Feature zu erfinden."""
    from app.core.knowledge.parts.ops import normal_fields

    if not supports_surface_placement(spec):
        raise ValueError(
            tr(
                "Diese Operation setzt kein Element auf eine Fläche. "
                "Wählen Sie eine Bohrung, einen Baustein oder eine Beschriftung."
            )
        )
    target = placement.point
    if spec.name in {"move_feature", "duplicate_feature"}:
        if feature is None or source is None:
            raise ValueError(tr("Wählen Sie zuerst das Merkmal, das an die neue Stelle gehört."))
        if prepared_tool is None:
            from app.core.geom.prepare_ops import feature_placement_geometry

            offset = feature_placement_geometry(source, feature, spec.name).selected_offset
        else:
            if prepared_tool.feature_id != feature.id or prepared_tool.selected_offset is None:
                raise ValueError(
                    tr("Wählen Sie zuerst das Merkmal, das an die neue Stelle gehört.")
                )
            offset = prepared_tool.selected_offset
        matrix = np.column_stack((placement.frame.x_axis, placement.frame.y_axis, placement.normal))
        target = _vec(np.asarray(placement.point) + matrix @ offset)
    values: dict[str, Any] = dict(zip(POSITION, target, strict=True))
    values.update(zip(normal_fields(spec.params), placement.normal, strict=True))
    if spec.name == "drill_hole":
        values["anchor"] = "mouth"
    if any(field.name == FEATURE_FIELD for field in spec.params.spec()):
        values[FEATURE_FIELD] = (
            feature.id
            if spec.name in {"move_feature", "duplicate_feature"} and feature is not None
            else ""
        )
    return values


def original_surface_hit(
    mesh: MeshData,
    origin: Vec3,
    direction: Vec3,
    *,
    clip_origin: Vec3 | None = None,
    clip_normal: Vec3 | None = None,
    clip_planes: Sequence[SectionPlane] = (),
) -> tuple[int, Vec3] | None:
    """Den Sichtstrahl am Originalnetz schneiden; LOD-Zellen liefern keine Modellkoordinaten."""
    from app.core.geom.mesh import on_surface, ray_hit_distances

    vector = np.asarray(direction, dtype=np.float64)
    length = float(np.linalg.norm(vector))
    if not np.isfinite(origin).all() or not np.isfinite(vector).all() or length <= EPS_GEOM:
        return None
    vector /= length
    distances = ray_hit_distances(mesh.raw.triangles, np.asarray(origin, dtype=np.float64), vector)
    points = np.asarray(origin) + distances[:, None] * vector
    if clip_origin is not None and clip_normal is not None:
        visible = (points - clip_origin) @ np.asarray(clip_normal) >= -EPS_GEOM
        distances, points = distances[visible], points[visible]
    for plane in clip_planes:
        # SectionPlane entfernt ihre positive Seite; mehrere Ebenen sind
        # eine Schnittmenge sichtbarer Halbebenen. Kappen entstehen hier nie.
        visible = (points - plane.origin) @ np.asarray(plane.normal) <= EPS_GEOM
        distances, points = distances[visible], points[visible]
    if not len(distances):
        return None
    point = points[int(np.argmin(distances))]
    closest, _, faces = on_surface(mesh.raw, point.reshape(1, 3))
    return int(faces[0]), _vec(closest[0])


def placement_tool(
    spec: OperationSpec,
    entered_values: Mapping[str, Any],
    profile: Profile,
    *,
    source: SceneObject | None = None,
    feature: Feature | None = None,
) -> MeshData:
    """Der wirkliche lokale Werkzeugkörper; ausschließlich für die temporäre Vorschau."""
    return prepare_tool(spec, entered_values, profile, source=source, feature=feature).mesh


def prepare_tool(
    spec: OperationSpec,
    entered_values: Mapping[str, Any],
    profile: Profile,
    *,
    source: SceneObject | None = None,
    feature: Feature | None = None,
) -> PlacementTool:
    """Werkzeug und Merkmalsbezug einmal im Worker berechnen und gemeinsam aufbewahren."""
    if spec.name in {"move_feature", "duplicate_feature"}:
        if feature is None or source is None:
            raise ValueError(tr("Wählen Sie zuerst das Merkmal, das an die neue Stelle gehört."))
        from app.core.geom.prepare_ops import feature_placement_geometry

        geometry = feature_placement_geometry(source, feature, spec.name)
        return PlacementTool(geometry.mesh, geometry.selected_offset, feature.id)
    return PlacementTool(_creation_tool(spec, entered_values, profile, source=source))


def _creation_tool(
    spec: OperationSpec,
    entered_values: Mapping[str, Any],
    profile: Profile,
    *,
    source: SceneObject | None = None,
) -> MeshData:
    """Vorhandene Erzeugungsgeometrie im lokalen Mündungs-/Basisrahmen."""
    from app.core.knowledge.parts.ops import part_of
    from app.core.knowledge.profiles import for_object
    from app.core.registry.params import validate

    profile = for_object(profile, source)
    if spec.name in _SURFACE_PRIMITIVES:
        from app.core.geom.primitive_ops import primitive_local_tool

        checked = validate(spec.params, entered_values)
        return primitive_local_tool(spec.name, checked.as_dict(), "fine")
    part = part_of(spec.name)
    if part is not None:
        from app.core.knowledge.parts.ops import placement_tool as part_tool

        return part_tool(part, entered_values, profile)
    if spec.name == "drill_hole":
        from app.core.geom.prepare import drill_tool

        values: Any = validate(spec.params, entered_values)
        # Die Hülldiagonale reicht in jeder freien Richtung durch den Zielkörper.
        # Ohne Zielkörper bleibt der Bauraum die obere Grenze der Vorschau.
        depth = float(values.depth) or (
            source.mesh.bounds.diagonal
            if source is not None
            else float(np.linalg.norm(profile.printer.build_volume))
        )
        return drill_tool(
            diameter=float(values.diameter),
            depth=depth,
            profile=profile,
            compensate=bool(values.compensate),
            widening_diameter=float(values.widening_diameter),
            widening_depth=float(values.widening_depth),
            transition_angle=float(values.transition_angle),
        )
    if spec.name in {"label_text", "create_label"}:
        from app.core.geom.label_ops import local_text_body

        values = validate(spec.params, entered_values)
        return local_text_body(
            values.text,
            values.size,
            values.font,
            values.depth,
            mode=values.mode if spec.name == "label_text" else "body",
            angle=getattr(values, "angle", 0.0),
        )
    raise ValueError(
        tr(
            "Diese Operation setzt kein Element auf eine Fläche. "
            "Wählen Sie eine Bohrung, einen Baustein oder eine Beschriftung."
        )
    )
