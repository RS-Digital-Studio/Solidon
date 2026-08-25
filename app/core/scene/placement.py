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

from collections.abc import Mapping
from typing import Any, Final

from app.core.log import get_logger
from app.core.registry import OperationSpec
from app.core.types import Feature, Vec3
from app.core.units import format_length
from app.i18n import tr

_log = get_logger(__name__)

#: Der Parameter, mit dem ein Baustein das Merkmal benennt, an das er gehört.
#: Wo eine Operation ihn hat, ist das die ganze Antwort: die Position daneben
#: zählt als Versatz vom Merkmal und bleibt auf null.
FEATURE_FIELD = "at_feature"

#: Die Position, in der Reihenfolge, in der die Parameter überall heißen.
POSITION = ("x", "y", "z")

#: Eine freie Richtung, für die Operationen, die eine nehmen (§25, Beschriftung).
NORMAL = ("nx", "ny", "nz")

#: Der Parameter, der eine Fläche als **Ziel** benennt statt als Ort — die Höhe
#: einer Extrusion reicht bis dorthin (§30.1, D14). Wie ``at_feature`` eine
#: Kennung, aber kein Ersatz für die Position: die Skizze liegt woanders.
TARGET_FIELD = "up_to"

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


def bore_advice(diameter: float) -> tuple[str, list[str]]:
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
    measured = format_length(diameter, with_unit=False)
    size = screw_for_bore(diameter)
    if size is not None:
        # Ganze Sätze mit Platzhaltern statt zusammengesetzter Halbsätze: Wer
        # nur „das Durchgangsloch für" zu übersetzen bekommt, weiß nicht, was
        # danach steht — und in mancher Sprache steht es davor.
        said = tr("Diese Bohrung misst {measure} mm — das Durchgangsloch für {screw}.")
        return said.replace("{measure}", measured).replace("{screw}", size), []
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
        return {field: feature.id, **_from_the_bore(spec, feature, names)}

    values: dict[str, Any] = {}
    if TARGET_FIELD in names and feature.kind == "face":
        # „Bis zu dieser Fläche" — die Kennung reicht, den Rahmen rechnet die
        # Auswertung daraus (app.core.sketch.planes). Nur planare Flächen: bis
        # zu einer Bohrung zu extrudieren hat keine Bedeutung.
        values[TARGET_FIELD] = feature.id
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
    centre = _vector(feature.params.get("centre"))
    if centre is not None:
        for name, value in zip(POSITION, centre, strict=True):
            if name in names:
                values[name] = round(float(value), 4)

    direction = _vector(feature.params.get("normal")) or _vector(feature.params.get("axis"))
    if direction is not None:
        for name, value in zip(NORMAL, direction, strict=True):
            if name in names:
                values[name] = round(float(value), 4)
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
        centre = _vector(entry.params.get("centre"))
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
    values.pop(TARGET_FIELD, None)
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
    normal = _vector(feature.params.get("normal"))
    return normal is not None and dominant_axis(normal) == "z" and normal[2] > 0.0


def _allows(spec: OperationSpec, name: str, value: str) -> bool:
    """Ist das eine der Auswahlmöglichkeiten, die der Parameter anbietet?"""
    for entry in spec.params.spec():
        if entry.name == name:
            return not entry.choices or value in entry.choices
    return False


def _vector(value: object) -> Vec3 | None:
    if not isinstance(value, list | tuple) or len(value) != 3:
        return None
    try:
        return (float(value[0]), float(value[1]), float(value[2]))
    except (TypeError, ValueError):
        return None
