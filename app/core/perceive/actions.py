"""Was der Kunde mit einem erkannten Merkmal tun kann — und was nicht, mit Grund.

**Wozu es das gibt.** Robert am 03.09.2026: „evtl noch ein eigenes panel damit
man nicht für alles rechtsklick machen muss übersichtlich, verständlich
innovativ und intuitiv." Der Entwurf dazu ist, dass eine geänderte Zahl **die
Operation ist**: Das Panel zeigt, was Solidon an einem Merkmal gemessen hat,
und der Kunde ändert es direkt — kein Menü, kein Modus, kein Rechtsklick.

**Warum die Auskunft im Kern steht und nicht in der Oberfläche.** „Eine
Verrundung folgt ihrer Kante" ist eine Aussage über Geometrie. Stünde sie im
Panel, wäre sie beim nächsten Kernumbau falsch, ohne dass es jemand merkt
(Vereinbarung mit 3d-druck-d4, 03.09.2026).

**Und warum sie aus dem Register kommt und nicht aus einer Liste daneben.**
Welche Operation für welche Merkmalsart gilt, steht in ihren ``applies_to``.
Eine zweite Tabelle, die dasselbe noch einmal sagt, weiß beim nächsten
Registereintrag die Hälfte — genau die Bauart, an der heute ein halbes Dutzend
Befunde hing: eine Auskunft, die es gibt, und eine Stelle, die sie nicht
abruft.

Was hier **nicht** steht, ist die Merkmalsart als Frage an das Panel. Es
rendert die Liste und sonst nichts; sobald eine Art dazukommt, folgt es von
selbst.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from typing import TYPE_CHECKING, Any, Final

from app.core.registry import REGISTRY
from app.core.registry.surfaces import asked_fields, normal_fields_of
from app.core.types import CancelToken, Feature, FeatureId, MeasureStatus, measure_status
from app.core.units import DEGREE_UNIT
from app.i18n import TranslatableText, _

if TYPE_CHECKING:
    from app.core.geom.mesh import MeshData
    from app.core.perceive.relations import FeatureGroupReason


#: Das eine sichtbare Wort je Maßquelle — Objektbaum, Merkmalfenster,
#: Bohrhinweis und Steckbrief lesen es hier (:func:`measure_qualifier`).
#:
#: **Jede Quelle hat eines**, auch die belegten. Bis zum 22.09.2026 trugen nur
#: der Fit („geschätzt“) und die Vorgabe („Vorgabemaß“) ein Wort; ein am Netz
#: oder an der exakten Fläche gemessenes Maß stand ohne da, und wer nicht mit
#: der Maus darüberfuhr, sah nicht, woher es kam — der Änderungsverlauf von
#: 0.5.0 versprach aber „gemessen, eingepasst oder aus dem Schritt“. Die
#: Wörter sind die eines Kunden, der vom Slicer kommt: Wo die Zahl steht,
#: sagt das Wort, was sie ist; der Satz dazu steht im Tooltip
#: (:func:`measure_explanation`).
MEASURE_SOURCE_WORDS: Final[dict[str, TranslatableText]] = {
    "native": _("aus der Konstruktion"),
    "facets": _("gemessen"),
    "fit": _("eingepasst"),
    "parameter": _("aus dem Schritt"),
}


#: Die Quellen, deren Zahl die vorhandene Oberfläche selbst ist: am Netz
#: gemessen oder aus dem exakten Modell übernommen. Eine **enge** Beschriftung
#: — die Marken in der Ansicht — nennt ihr Wort nicht (:func:`measure_qualifier`
#: mit ``compact``): Dreißig Bohrungen mit dreißigmal „gemessen“ drängten
#: Beschriftungen aus dem Bild. Die übrigen Wörter warnen und bleiben überall.
DIRECT_MEASURE_SOURCES: Final[frozenset[str]] = frozenset({"native", "facets"})


def measure_qualifier(status: MeasureStatus, *, compact: bool = False) -> TranslatableText | None:
    """Das kurze Wort zur Maßquelle — dasselbe in Oberfläche und Steckbrief.

    ``compact`` lässt das Wort einer direkten Quelle weg
    (:data:`DIRECT_MEASURE_SOURCES`), für Stellen mit einer Zeile unter vielen.
    """
    if not status.available:
        return _("Maß nicht bestimmt")
    if status.state == "unknown" or status.source is None:
        return _("Maßherkunft nicht bestimmt")
    if compact and status.source in DIRECT_MEASURE_SOURCES:
        return None
    return MEASURE_SOURCE_WORDS.get(status.source)


def measure_explanation(status: MeasureStatus) -> TranslatableText:
    """Die Herkunft erklärt ein Maß, ohne einen Genauigkeitsbereich zu erfinden."""
    if not status.available:
        return _(
            "Dieses Maß ist nicht zuverlässig bestimmt. Einen Zielwert eingeben "
            "oder einen geeigneten Bezug wählen."
        )
    if status.state == "unknown":
        return _(
            "Für diesen Wert ist nicht belegt, wie er bestimmt wurde. "
            "Er wird deshalb nicht als exaktes Maß ausgegeben."
        )
    if status.source == "parameter":
        return _(
            "Wert aus dem erzeugenden Schritt. Die vorhandene Oberfläche kann davon abweichen."
        )
    if status.source == "fit":
        return _(
            "An die vorhandene Oberfläche eingepasst. Das ursprüngliche "
            "Konstruktionsmaß ist nicht bekannt."
        )
    if status.source == "facets":
        return _(
            "Am vorhandenen Dreiecksnetz gemessen. Eine gerundete Ursprungsfläche "
            "kann davon abweichen."
        )
    return _(
        "Aus der Konstruktion des Modells übernommen. Druckabweichungen und "
        "Passungsspiel sind darin nicht enthalten."
    )


#: Die Zeilen des Panels, je Zeile die Operationen, die sie einlösen können.
#:
#: Die Reihenfolge ist eine Aussage und keine Sortierung: erst wohin, dann wie
#: groß, dann wie herum, zuletzt weg. Sie steht hier und nicht in der
#: Oberfläche, weil sie zur Sache gehört (Bitte 3d-druck-d4, 03.09.2026).
#:
#: **Mehrere Operationen je Zeile, und das ist der Punkt.** „Größe ändern"
#: erledigt für eine Bohrung ``resize_hole`` und für einen Zapfen
#: ``resize_feature`` — zwei Operationen, weil die Bohrung einen eigenen Weg
#: durch den exakten Kern und eine Materialkompensation hat, die für einen
#: Zapfen andersherum liefe. Den Kunden geht das nichts an: Er sieht **eine**
#: Zeile, und sie tut, was sie sagt. Zwei Zeilen, von denen bei jeder
#: Merkmalsart eine ausgegraut wäre, sind genau die Sorte Oberfläche, die
#: Roberts „übersichtlich" ausschließt.
#:
#: Die erste Operation, die für die Art gilt, füllt die Zeile.
#: Die allgemeinere Operation steht **vorn**, und das entscheidet nur eine
#: Sache: Gilt für eine Art keine von beiden, benennt ihr Titel die Zeile.
#: „Merkmal ändern" ist dort die richtige Beschriftung, „Bohrung ändern" nicht.
#: Überschneiden können sie sich nicht — ``resize_hole`` gilt für ``hole``,
#: ``resize_feature`` für alles andere.
#:
#: **Die Fläche wandert in derselben Zeile wie jedes Merkmal** (RM-535, Robert
#: 06.10.2026: „alles einheitlich, Bohrung Vorbild für alle Funktionen“). An
#: ihr heißt die Zeile *Fläche versetzen* und trägt den Weg als Feld; ein Zug
#: am Flächengriff schreibt dorthin, und erst *Übernehmen* legt den Schritt
#: an — wie der Zug an der Bohrung. Überschneiden können sich die beiden
#: nicht: ``push_face`` gilt nur der Fläche, ``move_feature`` nie.
ACTION_ORDER: Final[tuple[tuple[str, ...], ...]] = (
    ("move_feature", "push_face"),
    ("resize_feature", "resize_hole"),
    # **Die Länge steht neben der Größe, nicht hinter dem Entfernen** (Robert,
    # 10.09.2026: „langloch merkmale hat noch in der auswahl keine
    # einstellungen"). Ein erkanntes Langloch trug bis dahin fünf ausgegraute
    # Zeilen und **kein einziges Feld**: Versetzen, Ändern, Drehen, Verdoppeln
    # und Entfernen gelten dort alle nicht, und die eine Operation, die gilt,
    # stand nur als Knopf im Auswahlfenster. Wer es anklickte, sah seine Maße
    # und konnte keines davon ändern.
    #
    # Als Zeile mit Feldern trägt sie beides: Länge und Richtung stehen mit
    # ihren **gemessenen** Werten da (:func:`_value_of`), und der Knopf darunter
    # führt sie aus. An einer runden Bohrung ist dieselbe Zeile der Weg zum
    # Langloch — dort steht in der Länge das Doppelte ihres Durchmessers.
    ("slot_hole",),
    ("rotate_feature",),
    ("duplicate_feature",),
    ("remove_feature",),
)

#: Warum eine **bestimmte** Handlung an einer bestimmten Art nichts tut.
#:
#: Der Grund hängt nicht immer an der Art allein. Eine Kugel lässt sich
#: versetzen, ändern und entfernen — nur nicht drehen, denn sie hat keine
#: Lage. Der Satz aus :data:`NOT_APPLICABLE` („von einer Kugelfläche ist
#: gemessen …") wäre dort schlicht falsch.
#: Ein Gewinde trägt seit P2.6 Ändern und Entfernen (``prepare_ops._resize_thread``,
#: ``_remove_thread``); versetzt, gedreht oder verdoppelt wird der Körper oder die
#: Bohrung, auf der es sitzt — ein Satz für die drei Zeilen.
THREAD_STAYS_WHERE_IT_IS: Final = _(
    "Ein Gewinde sitzt an seinem Schaft oder in seiner Bohrung. "
    "Versetzen, drehen oder verdoppeln Sie den Körper oder die Bohrung."
)

NOT_APPLICABLE_HERE: Final[dict[tuple[str, str], TranslatableText]] = {
    ("sphere", "rotate_feature"): _(
        "Eine Kugelfläche hat keine Lage, die sich drehen ließe — gedreht sähe sie aus wie vorher."
    ),
    # **Drei Arten, die *Zum Langloch ziehen* nicht annimmt** — und jede aus
    # ihrem eigenen Grund. Ohne diese drei Sätze stand die Zeile seit dem
    # 10.09.2026 an Zapfen, Senkung und Kugel mit dem Auffangsatz „Für diese
    # Art von Merkmal gibt es noch keine Handlung", also mit einem Ende ohne
    # Weg nach vorn (Regel 17). Ein Satz je Art und nicht einer für alle drei:
    # Der Zapfen ist Material, die Senkung hängt an ihrer Bohrung, und die
    # Kugel hat gar keine Richtung.
    ("pin", "slot_hole"): _(
        "Gezogen wird ein Loch, und ein Zapfen ist Material. Was ihn länglich "
        "macht, ist seine eigene Form — über „Merkmal ändern“ oder als neuer "
        "Körper."
    ),
    ("cone", "slot_hole"): _(
        "Eine Senkung sitzt auf ihrer Bohrung, und ein Langloch verträgt keine "
        "Aufweitung. Ziehen Sie die Bohrung ohne sie, oder lassen Sie sie rund."
    ),
    ("sphere", "slot_hole"): _(
        "Eine Kugelfläche hat keine Achse, entlang der ein Loch länger würde."
    ),
    # **Die Breite nimmt seit dem 12.09.2026 *Bohrung ändern*** (RM-156) — der
    # Satz, der hier stand, ist mit seiner Lücke gefallen. ``resize_feature``
    # bleibt draußen: Es gilt Materie, und ein Langloch ist ein Hohlraum; wer
    # es dort ruft, liest über ``instead_of`` den Namen der richtigen Zeile.
    ("slot", "resize_feature"): _(
        "Ein Langloch ist ein Hohlraum und keine Materie. Seine Breite ändert "
        "„Bohrung ändern“, Länge und Richtung „Zum Langloch ziehen“."
    ),
    ("torus", "slot_hole"): _(
        "Gezogen wird ein Loch. Ein Ring hat keine Bohrung, die länger würde."
    ),
    ("thread", "slot_hole"): _("Gezogen wird ein Loch. Ein Gewinde wird nicht länglich."),
    ("thread", "move_feature"): THREAD_STAYS_WHERE_IT_IS,
    ("thread", "duplicate_feature"): THREAD_STAYS_WHERE_IT_IS,
    ("thread", "rotate_feature"): THREAD_STAYS_WHERE_IT_IS,
    ("thread", "pattern_feature"): THREAD_STAYS_WHERE_IT_IS,
}

#: Warum an einem Ring, der der ganze Körper ist, jede Handlung absagt: Seine
#: Ringfläche hat keinen Schaft, von dem sie sich trennen ließe — die
#: Operation sagt dasselbe (``prepare_ops.TORUS_IS_THE_BODY``). Ohne Verb,
#: denn ``_folded`` legt die Zeilen zusammen.
TORUS_IS_THE_WHOLE_BODY: Final = _(
    "Ein Ring, der der ganze Körper ist, lässt sich nicht einzeln versetzen, "
    "ändern, drehen, verdoppeln oder entfernen. Bewegen Sie den Körper."
)


def torus_blocked(feature: Feature, mesh: MeshData | None) -> TranslatableText | None:
    """Warum an diesem Ring keine Handlung geht — sonst ``None``.

    Erst die billige Frage, ob die Ringfläche jedes Dreieck des Körpers
    beansprucht; dann dieselbe, an der die Operation absagt
    (``prepare_ops.torus_refusal``, RM-535), damit keine Zeile Felder zeigt,
    die beim Übernehmen nichts tun.
    """
    if feature.kind != "torus" or mesh is None or not feature.face_indices:
        return None
    if len(set(feature.face_indices)) >= mesh.triangle_count:
        return TORUS_IS_THE_WHOLE_BODY
    from app.core.geom.prepare_ops import torus_refusal

    return torus_refusal(mesh, feature)


#: Warum *Merkmal verschieben* an einem Zapfen oder einer Kuppel absagt, die
#: der ganze Körper sind (RM-535): Abgetragen bliebe nichts, woran das Merkmal
#: wieder ansetzen könnte, und die Operation endete mit „Von dem Körper bleibt
#: nichts übrig“ — nach 40 s am dichten Zylinder des Korpus.
FEATURE_SPANS_THE_BODY: Final = _(
    "Dieses Merkmal ist der ganze Körper. Verschieben Sie den Körper als Ganzes."
)

#: Warum *Merkmal verschieben* an einer Bohrung absagt, in der ein Zapfen steht
#: (RM-535, Entscheidung Robert (d)): Versetzt würde nur die Luft um ihn, und
#: der Zapfen stünde danach in der Wand — am Kundenmodell erkannte Solidon nach
#: 0,5 mm zwei Sackbohrungen weniger.
HOLE_HOLDS_A_PIN: Final = _(
    "In dieser Bohrung steht ein Zapfen; versetzt schnitte sie in ihn hinein. "
    "Verschieben Sie den Zapfen allein oder den ganzen Körper."
)


def _pin_inside(feature: Feature, features: Mapping[FeatureId, Feature]) -> bool:
    """Ob in dieser Bohrung ein Zapfen auf derselben Achse steht (RM-535)."""
    import numpy as np

    radius = float(feature.params.get("diameter", 0.0)) / 2.0
    depth = float(feature.params.get("depth", 0.0))
    if feature.kind != "hole" or radius <= 0.0 or depth <= 0.0:
        return False
    centre = np.asarray(feature.params["centre"], dtype=float)
    axis = np.asarray(feature.params.get("axis", (0.0, 0.0, 1.0)), dtype=float)
    axis /= max(float(np.linalg.norm(axis)), 1e-12)
    for other in features.values():
        if other.kind != "pin" or other.params.get("centre") is None:
            continue
        own = np.asarray(other.params.get("axis", (0.0, 0.0, 1.0)), dtype=float)
        own /= max(float(np.linalg.norm(own)), 1e-12)
        offset = np.asarray(other.params["centre"], dtype=float) - centre
        along = float(offset @ axis)
        radial = float(np.linalg.norm(offset - along * axis))
        reach = float(other.params.get("depth", 0.0)) / 2.0
        if (
            abs(float(own @ axis)) > 0.99
            and radial + float(other.params.get("diameter", 0.0)) / 2.0 < radius
            and abs(along) < depth / 2.0 + reach
        ):
            return True
    return False


def spans_the_body(feature: Feature, mesh: MeshData | None) -> bool:
    """Ob ein Zapfen oder eine Kuppel der ganze Körper ist — kein Punkt des
    Netzes liegt außerhalb ihres Zylinders beziehungsweise ihrer Kugel."""
    if (
        mesh is None
        or feature.kind not in ("pin", "sphere")
        or feature.params.get("centre") is None
    ):
        return False
    from app.core.types import is_a_cavity

    if is_a_cavity(feature):
        return False
    import numpy as np

    from app.core.geom.prepare import FEATURE_OVERLAP

    radius = float(feature.params.get("diameter", 0.0)) / 2.0
    if radius <= 0.0:
        return False
    slack = radius * 0.01 + FEATURE_OVERLAP
    relative = np.asarray(mesh.raw.vertices, dtype=float) - np.asarray(
        feature.params["centre"], dtype=float
    )
    if feature.kind == "sphere":
        return float(np.linalg.norm(relative, axis=1).max()) <= radius + slack
    axis = np.asarray(feature.params.get("axis", (0.0, 0.0, 1.0)), dtype=float)
    axis /= max(float(np.linalg.norm(axis)), 1e-12)
    along = relative @ axis
    radial = np.linalg.norm(relative - np.outer(along, axis), axis=1)
    half = float(feature.params.get("depth", 0.0)) / 2.0 + slack
    return float(radial.max()) <= radius + slack and float(np.abs(along).max()) <= half


def move_blocked(
    feature: Feature,
    features: Mapping[FeatureId, Feature] | None,
    mesh: MeshData | None,
) -> TranslatableText | None:
    """Was nur *Merkmal verschieben* an diesem Merkmal absagen lässt — sonst ``None``.

    Steht in :func:`actions_for` vor den übrigen Gründen der Zeile; Karte,
    Operation und Griff lesen es über :func:`move_refusal`.
    """
    if spans_the_body(feature, mesh):
        return FEATURE_SPANS_THE_BODY
    if features is not None and _pin_inside(feature, features):
        return HOLE_HOLDS_A_PIN
    return None


#: Was statt der Handlung hilft, je Merkmalsart, für die keine gilt.
#:
#: Jede Art aus einem eigenen Grund, und jeder Grund nennt, was stattdessen
#: geht — ein Satz, der nur „geht nicht" sagt, ist keiner (Regel 17).
#:
#: **Kugel und Kegel standen hier bis zum 03.09.2026** mit dem Satz, ihre Tiefe
#: im Material sei nicht gemessen. Seit dem Flächenweg ist sie es, beide Arten
#: tragen alle vier Handlungen, und die Sätze waren damit doppelt tot: nicht
#: mehr erreichbar und nicht mehr wahr. Was von der Kugel bleibt, ist ihre eine
#: fehlende Handlung, und die steht in :data:`NOT_APPLICABLE_HERE`.
#: **Ein Satz steht unter allen Handlungen, die er ablehnt.** ``_folded`` legt
#: sie im Panel zu einer Zeile zusammen — „Verschieben, Ändern, Drehen,
#: Verdoppeln und Entfernen — <Satz>" —, und deshalb darf der Satz kein
#: einzelnes Verb tragen. Bei ``face`` und ``torus`` tat er das bis zum
#: 10.09.2026: Unter fünf Titeln stand „lässt sich nicht einzeln **versetzen**"
#: beziehungsweise „nicht direkt **ändern**", also eine Begründung für eines
#: von fünfen (Durchsicht auf Roberts Bitte, „auch alle anderen mal gründlich
#: kontrollieren").
NOT_APPLICABLE: Final[dict[str, TranslatableText]] = {
    # Seit RM-535 steht *Fläche versetzen* als Zeile darüber; der Satz sagte
    # bis dahin „einzeln lässt sich an ihr nichts ändern“ und stand damit
    # unter einer Zeile, die genau das tut.
    "face": _(
        "Eine Fläche ist Oberfläche des Körpers und hat kein eigenes Maß. Sie "
        "wandert als Ganzes über „Fläche versetzen“. Bohren, Beschriften und "
        "Bausteine setzen auf ihr an."
    ),
    "curved_face": _(
        "Eine gerundete Seite gehört zur Oberfläche des Körpers. Bohren sowie "
        "das Platzieren von Grundkörpern und Bausteinen setzen dort am Körper "
        "an. Ein eigenes Filament lässt sich zuweisen. Zum Zeichnen wählen Sie "
        "eine ebene Fläche oder eine Skizzenebene."
    ),
    "pattern": _(
        "Ein Muster liegt auf seiner Fläche und hat dort seinen Platz; versetzt, "
        "gedreht oder verdoppelt wird die Fläche oder der Körper. „Merkmal ändern“ "
        "setzt Teilung, Zellbreite und Tiefe neu, „Merkmal entfernen“ füllt die Zellen."
    ),
    "fillet": _(
        "Eine Verrundung gehört zu ihrer Kante und hat ohne sie keine Lage. "
        "Bewegt oder kopiert man sie allein, bliebe die Kante scharf und die "
        "Rundung läge daneben."
    ),
    "edge_loop": _(
        "Eine offene Kantenschleife ist ein Loch im Netz und kein Körper — sie "
        "hat nichts, was sich bewegen, messen oder herausnehmen ließe. Mit "
        "„Reparieren“ wird sie geschlossen."
    ),
    # **Der Ring stand hier bis zum 21.09.2026** — „hat nichts, woran sich
    # einzeln etwas ändern ließe". Seit P2.6 tragen Wulst und Kehle alle fünf
    # Handlungen in beiden Kernen (``prepare_ops._move_torus`` und
    # Geschwister); was bleibt, ist der Ring, der der ganze Körper ist
    # (:func:`torus_blocked`), und das Langloch (``NOT_APPLICABLE_HERE``).
    # **Das Langloch stand hier bis zum 11.09.2026** — „die Handlungen hier
    # rechnen mit einem Durchmesser und träfen seine Flanken nicht". Sie tun es
    # nicht mehr: Sein Werkzeugkörper wird aufgezogen wie beim Schneiden, und
    # Versetzen, Drehen, Verdoppeln und Entfernen gelten ihm wie einer
    # Bohrung (RM-153). Der Satz ist gefallen, nicht verschoben.
    # **Der Fallback stand hier bis zum 10.09.2026**, und er sagte nichts:
    # „Für diese Art von Merkmal gibt es noch keine Handlung." Ein Ende ohne
    # Weg nach vorn ist genau das, was Regel 17 verbietet. An seine Stelle trat
    # ein Satz über das Gewinde — „trägt kein einzelnes Maß, das sich ändern
    # ließe", mit dem Verweis auf den Bausteinschritt in ``Feature.created_by``
    # —, und **der stand hier bis zum 21.09.2026**: Seit P2.6 ändert *Merkmal
    # ändern* Durchmesser und Steigung und *Merkmal entfernen* nimmt außen den
    # Gang und schließt innen die Bohrung (``prepare_ops._resize_thread``,
    # ``_remove_thread``); Versetzen, Drehen und Verdoppeln sagen ihren Satz in
    # ``NOT_APPLICABLE_HERE``, und ein erkanntes Gewinde aus einer fremden
    # Datei braucht keinen Schritt mehr, auf den man zeigen könnte.
    # **Der erste Entwurf sperrte hier alles, und das war messbar falsch.** Er
    # begründete es damit, an einen eingeschlossenen Hohlraum komme kein
    # Werkzeug heran — dabei versetzt
    # ``test_a_cavity_inside_the_body_moves_without_losing_material`` seit dem
    # 03.09.2026 eine Kugelhöhle in einem Würfel, und an Roberts Bauart
    # nachgemessen (Zylinder Ø 2 auf 9 mm) bleibt das Volumen des Ganzen auf
    # 0,000000 mm³ genau gleich. Was fehlt, ist nicht die Erreichbarkeit,
    # sondern das **Maß**: Ein Einschluss ist, was ein Negativkörper
    # hinterlassen hat, und seine Form steht allein in seinen Flächen.
    "void": _(
        "Ein Lufteinschluss trägt kein Maß, an dem sich Größe oder Drehung "
        "ändern ließen — seine Form steht allein in seinen Flächen; und einen "
        "zweiten Hohlraum im Material legt man nicht an. Was geht: verschieben, "
        "und „Merkmal entfernen“ füllt ihn mit Material auf."
    ),
}

_UNKNOWN_KIND: Final = _("Für diese Art von Merkmal gibt es noch keine Handlung.")

#: Der Satz an einer **runden Wand** für die Zeilen, die eine Verrundung
#: nicht annimmt.
#:
#: ``radial`` heißt: ein mindestens halber Zylindermantel, der zu keiner
#: Kante gehört — das abgerundete Ende einer Lasche, der Nutboden eines
#: Bajonettverschlusses, die Innenwand eines Clips. Der Satz aus
#: :data:`NOT_APPLICABLE` sagt an ihr etwas Falsches: „gehört zu ihrer Kante
#: und hat ohne sie keine Lage" — es gibt keine Kante. Gemessen am Siebhalter
#: eines Kunden (15.09.2026): Der Nutboden Ø 54,36 stand mit vier grauen
#: Zeilen im Panel, und jede nannte die Kante. Wie beim Entfernen
#: (``actions_for``) sagt die Zeile hier, was die Wand ist und was an ihr
#: geht — ohne einzelnes Verb, denn ``_folded`` legt die Zeilen zusammen.
ROUND_WALL_HAS_NO_PLACE: Final = _(
    "Eine runde Wand ist ein Stück des Körpers und hat keine eigene Lage — "
    "sie folgt ihm. Was an ihr geht, ist ihr Radius über „Merkmal ändern“."
)

#: Warum an einer Kegelfläche keine Körperhandlung geht: Ein Kegelstück unter
#: dem vollen Umlauf, das zu keinem Langloch und keiner Bohrung gehört, hat
#: keinen ebenen Rand, aus dem ``_body_from_faces`` ein Werkzeug baute — jede
#: Operation sagte ab, 280 Mal im Lauf über 34 Netzmodelle (15.09.2026).
CONE_PIECE_HAS_NO_BODY: Final = _(
    "Diese Kegelfläche ist ein Stück des Körpers ohne eigenen Rand; sie lässt "
    "sich nicht allein bearbeiten."
)

#: Warum an einer runden Wand, die tangential in ihre Nachbarn übergeht, auch
#: der Radius nicht geht — der Umrissbogen eines Uhrenankers zum Beispiel:
#: Radial verschoben schöbe er seine Flanken aus ihrer Ebene, und
#: ``radial_rounding`` sagt genau das ab. Dasselbe Wort in Panel und Operation.
WALL_BLENDS_INTO_ITS_NEIGHBOURS: Final = _(
    "Diese runde Wand geht ohne Kante in ihre Nachbarn über; ihr Radius lässt "
    "sich nicht allein ändern. Zeichnen Sie die Kontur neu."
)

#: Woher ein Parameter seinen **heutigen** Wert nimmt.
#:
#: Der Schlüssel ist der Parametername der Operation, der Wert sagt, welche
#: Kennzahl des Merkmals ihn füllt. Eine Vorgabe, die nicht der gemessene Wert
#: ist, wäre eine stille Änderung, sobald jemand auf Übernehmen drückt — und
#: genau das meint Roberts „mit sinnvollen einstellungen".
#:
#: Was hier fehlt, behält die Vorgabe aus dem Parameterschema. Für ``angle`` ist
#: das richtig: Es gibt keinen gemessenen Winkel, nur einen gewünschten.
FeatureValueSource = tuple[str, int | None]
"""Kennzahl und gegebenenfalls Komponente, aus der ein Handlungsfeld liest."""


_FROM_FEATURE: Final[dict[str, FeatureValueSource]] = {
    "x": ("centre", 0),
    "y": ("centre", 1),
    "z": ("centre", 2),
    "diameter": ("diameter", None),
    "tube_diameter": ("tube_diameter", None),
    "pitch": ("pitch", None),
    "depth": ("depth", None),
    "cell_width": ("cell_width", None),
    "cell_depth": ("cell_depth", None),
    # Der gelesene Stil eines Musters — ``other`` bei einem, das Solidon nicht
    # selbst zeichnet; dort wählt der Kunde einen der acht.
    "style": ("style", None),
    # Die Länge eines Langlochs hat kein gemessenes Gegenstück — die Bohrung
    # hat noch keines. Genommen wird ihr Durchmesser, und
    # :data:`_SHIFTED_BY` legt denselben noch einmal darauf: Vorbelegt steht
    # damit ein Langloch, in dem sich eine Schraube um einen Durchmesser
    # verschieben lässt. Das ist ein gültiger Wert — ein Feld, das mit einer
    # Absage begrüßt, ist keine Vorgabe (Regel 17).
    "slot_length": ("diameter", None),
}


def feature_value_source(field: str, feature: Feature | None = None) -> FeatureValueSource | None:
    """Die gemessene Kennzahl hinter einem Handlungsfeld.

    Die Gruppenauskunft liest damit dieselbe Zuordnung wie das Panel. Ein
    Index kennzeichnet eine Komponente der Position; ohne Index ist es ein
    Maß des Merkmals — eine Zahl, oder am Langloch seine Richtung.

    **Am Langloch liest das Feld seine Länge und seine Richtung**
    (:func:`_slot_value`), nicht den Durchmesser wie an einer Bohrung. Bis zum
    22.09.2026 stand das nur im Panel; die Gruppe las die allgemeine Tabelle,
    verglich allein die Breite und nahm ein längeres und ein quer liegendes
    Langloch als „gleich" in *Auf alle anwenden* — mit den Werten des
    gewählten hätte das Übernehmen beide still gekürzt und gedreht.
    """
    if feature is not None and feature.kind == "fillet" and field == "diameter":
        return ("radius", None)
    if feature is not None and feature.kind == "slot" and field in _SLOT_SOURCES:
        return _SLOT_SOURCES[field]
    return _FROM_FEATURE.get(field)


#: Woraus die zwei Felder von *Zum Langloch ziehen* an einem **erkannten
#: Langloch** lesen (:func:`_slot_value`).
_SLOT_SOURCES: Final[dict[str, FeatureValueSource]] = {
    "slot_length": ("length", None),
    "slot_angle": ("direction", None),
}


@dataclass(frozen=True, slots=True)
class ActionField:
    """Ein Feld einer Handlung — mit dem Wert, der heute gilt."""

    name: str
    """Der Parametername der Operation."""
    label: TranslatableText | str
    unit: str
    value: float | bool | str
    kind: str
    """``length``, ``angle``, ``count``, ``bool`` oder ``choice`` — davon hängt
    ab, welches Eingabefeld die Oberfläche baut. Ein Längenfeld rechnet Zoll
    zurück, ein Winkelfeld nicht, und eine Anzahl ist eine ganze Zahl ohne
    Einheit."""
    minimum: float | None = None
    maximum: float | None = None
    choices: tuple[tuple[str, TranslatableText | str], ...] = ()
    parameter_factor: float = 1.0
    """Faktor vom sichtbaren Maß zum Operationsparameter, etwa Radius zu Durchmesser."""
    measurement: MeasureStatus | None = None
    """Quelle des Ausgangswerts; der editierte Zielwert ist keine neue Messung."""
    depends_on: tuple[str, tuple[str | bool, ...]] | None = None
    """Welches Feld derselben Handlung dieses wirksam macht, und bei welchen Werten.

    Dieselbe Angabe wie ``ParamSpec.depends_on`` des Parameters, unverändert
    durchgereicht: Das Merkmalfenster blendet das Feld aus, solange die
    Bedingung nicht erfüllt ist — wie der Operationsdialog (P6.2: der zweite
    Abstand nur bei „Zwei Abstände", der Winkel nur bei „Abstand und
    Winkel")."""


@dataclass(frozen=True, slots=True)
class FeatureAction:
    """Eine Handlung am Merkmal — oder der Grund, warum es sie nicht gibt."""

    title: TranslatableText | str
    op: str | None
    reason: TranslatableText | str = ""
    note: TranslatableText | str = ""
    fields: tuple[ActionField, ...] = field(default_factory=tuple)
    step: int | None = None
    """Die Schrittkennung, wenn die Handlung einen bestehenden Schritt ändert.

    Dann startet die Oberfläche keine neue Operation, sondern ändert den
    Schritt, der das Merkmal erzeugt hat (:func:`part_actions`, :func:`texture_actions`). Bei allen
    anderen Handlungen bleibt es ``None``, und ``op`` sagt, was zu starten
    ist."""
    elsewhere: tuple[TranslatableText | str, ...] = field(default_factory=tuple)
    """Was zu diesem Schritt gehört und hier kein Feld bekommt.

    Die Titel der Sammelparameter (:data:`COLLECTED_KINDS`) — eine
    Fachaufteilung, eine Skizze, ein Skelett. Sie haben ihren eigenen Editor
    im vollständigen Dialog; das Panel nennt sie und führt dorthin, statt sie
    zu verschweigen. Ohne diese Zeile stand an einer Organizer-Trennwand
    „Maße ändern" mit drei Außenmaßen, und der Weg zu den Fächern — die
    Sache, um die es geht — war von dort nicht zu finden (Befund Robert,
    18.09.2026)."""
    fixed: tuple[tuple[str, Any], ...] = field(default_factory=tuple)
    """Werte, die die Handlung mitbringt und die niemand eingibt.

    Der Fall dafür ist die **Kante** (:func:`edge_actions`): *Verrunden* an
    einer angeklickten Kante setzt ``edges="named"`` und den Schlüssel dieser
    einen Kante; einzugeben bleibt der Radius. Als Feld stünden beide im
    Fenster — eine Auswahl, die schon beantwortet ist, und eine Kennung aus
    sechs Zahlen, die keine Beschriftung ist (§2.4).

    Sie stehen hier und nicht in der Oberfläche, weil das Panel die
    Merkmalsarten nicht kennt und nicht kennen soll: Wer ``edges="named"``
    dort hineinschriebe, führte die Tabelle des Registers ein zweites Mal."""


#: Parameterarten, für die es hier **kein** Feld gibt.
#:
#: Ein Sammelparameter trägt, was sich nicht in Zahlen fassen lässt: eine
#: Skizze, eine Strichliste, ein Skelett, eine Fachaufteilung. Sein Wert ist
#: ein Text mit eigenem Editor, und :func:`_kind_of` kennt ihn nicht — er
#: bekäme ein Längenfeld und stünde als „Fachaufteilung: 0,00 mm" da.
#: Dieselbe Frage wie bei der Anzahl, die keine Länge ist, eine Stufe weiter:
#: Was das Merkmalfenster nicht zeigen kann, gehört nicht hinein, und der Weg
#: dorthin ist der vollständige Dialog des Schritts.
COLLECTED_KINDS: Final[frozenset[str]] = frozenset({"sketch", "strokes", "armature", "organizer"})


def _kind_of(spec: Any) -> str:
    """Welche Art Eingabefeld dieser Parameter braucht.

    **Eine Anzahl ist keine Länge.** Die Haken des Lochwand-Einhängers und die
    Löcher der Wandhalterung sind ganze Zahlen ohne Einheit; als ``length``
    bekamen sie im Merkmalfenster ein Längenfeld — „Anzahl: 2,00 mm", in Zoll
    „0,08 in" — und gingen als ``4.0`` in den Schritt zurück (gemessen an der
    Sonde vom 14.09.2026).
    """
    if spec.kind == "bool":
        return "bool"
    if spec.kind == "enum":
        return "choice"
    if spec.kind == "int":
        return "count"
    if spec.unit == DEGREE_UNIT:
        return "angle"
    return "length"


#: Wo eine Vorgabe **nicht** der gemessene Wert sein darf, und um welche
#: Kennzahl sie daneben liegt.
#:
#: Sonst gilt hier der gemessene Wert, und zwar mit Absicht (siehe
#: :data:`_FROM_FEATURE`). Beim Verdoppeln wäre er die Stelle, an der das
#: Merkmal schon liegt: eine Boolesche auf sich selbst, ein Schritt im Verlauf
#: und dasselbe Teil im Bild. Um einen Durchmesser versetzt liegt die Kopie
#: neben dem Original und ist zu sehen (Vorschlag 3d-druck-d4, 03.09.2026).
_SHIFTED_BY: Final[dict[tuple[str, str], str]] = {
    ("duplicate_feature", "x"): "diameter",
    ("slot_hole", "slot_length"): "diameter",
}

#: Felder, die bei null beginnen statt bei ihrer Schemavorgabe — ein Weg, den
#: es noch nicht gibt (RM-535). *Fläche versetzen* trägt im Register 2 mm als
#: Vorgabe für den Dialog; im Merkmalfenster stünde damit ein Weg da, den
#: niemand gezogen hat, und ein *Übernehmen* ohne Hinsehen versetzte still.
#: Gemessen ist dabei nichts (``measurement`` bleibt leer).
_STARTS_AT_ZERO: Final[frozenset[tuple[str, str]]] = frozenset({("push_face", "distance")})


def _slot_value(spec: Any, feature: Feature) -> float | None:
    """Länge und Richtung eines **erkannten** Langlochs — sonst ``None``.

    Die allgemeine Zuordnung in :data:`_FROM_FEATURE` gilt je Feld und kennt
    die Merkmalsart nicht; an einer runden Bohrung ist das richtig (dort gibt
    es keine Länge, und genommen wird der doppelte Durchmesser). An einem
    Langloch, das schon eines ist, wäre es eine **stille Änderung**: Das Feld
    stünde auf zwei Durchmessern, und wer übernimmt, ohne hinzusehen, verkürzt
    ein 40er Loch auf 10 — die Zusage lautet aber, dass jedes Feld seinen
    heutigen gemessenen Wert trägt.

    Der Winkel kommt aus derselben Funktion, die die Operation als Vorgabe
    liest (``prepare_ops.slot_angle_of``); zwei Rechnungen für dieselbe
    Richtung liefen auseinander, und der Unterschied wäre ein verdrehtes Loch.
    """
    if feature.kind != "slot":
        return None
    if spec.name == "slot_length":
        measured = feature.params.get("length")
        if measured is not None and feature.params.get("open"):
            from app.core.geom.prepare import shortest_slot

            return max(float(measured), shortest_slot(float(feature.params["diameter"])))
        return float(measured) if measured is not None else None
    if spec.name == "slot_angle":
        from app.core.geom.prepare_ops import slot_angle_of

        axis = feature.params.get("axis")
        if axis is None:
            return None
        return slot_angle_of(feature, (float(axis[0]), float(axis[1]), float(axis[2])))
    return None


def _value_of(spec: Any, feature: Feature, op: str = "") -> float | bool | str:
    """Der heutige Wert dieses Parameters am Merkmal — sonst seine Vorgabe."""
    if (op, spec.name) in _STARTS_AT_ZERO:
        return 0.0
    slotted = _slot_value(spec, feature)
    if slotted is not None:
        return slotted
    reads = feature_value_source(spec.name, feature)
    if reads is None:
        return spec.default  # type: ignore[no-any-return]
    key, index = reads
    measured = feature.params.get(key)
    if measured is None:
        return spec.default  # type: ignore[no-any-return]
    if isinstance(measured, str):
        # Eine Auswahl, keine Zahl — der gelesene Stil eines Musters. Was nicht
        # unter den Wahlen steht, bleibt bei der Vorgabe.
        return measured if not spec.choices or measured in spec.choices else spec.default
    shift = _SHIFTED_BY.get((op, spec.name))
    beside = float(feature.params.get(shift, 0.0)) if shift else 0.0
    try:
        # Eine Richtung (``direction`` am Langloch) ist keine Zahl; ihren Winkel
        # liefert :func:`_slot_value`, und ohne Achse bleibt es die Vorgabe.
        return float(measured if index is None else measured[index]) + beside
    except IndexError, TypeError, ValueError:
        return spec.default  # type: ignore[no-any-return]


def _action_field(entry: Any, feature: Feature, op: str) -> ActionField:
    """Ein gemessenes Maß samt Rückübersetzung in den gespeicherten Parameter."""
    radius = entry.name == "diameter" and feature.kind == "fillet"
    factor = 2.0 if radius else 1.0
    source = feature_value_source(entry.name, feature)
    derived = (op, entry.name) in _STARTS_AT_ZERO or (
        (op, entry.name) in _SHIFTED_BY
        and not (
            feature.kind == "slot"
            and entry.name == "slot_length"
            and not feature.params.get("open")
        )
    )
    label = entry.title
    if radius:
        label = _("Radius")
    elif feature.kind == "pattern" and entry.name == "pitch":
        # Dasselbe Feld, ein anderes Wort: Ein Gewinde hat eine Steigung, ein
        # Muster eine Teilung — so heißt sie im Baum, im Steckbrief und beim
        # Aufbringen, und so soll sie im Merkmalfenster heißen.
        label = _("Teilung")
    return ActionField(
        name=entry.name,
        label=label,
        unit=str(entry.unit or ""),
        value=_value_of(entry, feature, op),
        kind=_kind_of(entry),
        minimum=entry.minimum / factor if entry.minimum is not None else None,
        maximum=entry.maximum / factor if entry.maximum is not None else None,
        choices=tuple((choice, choice) for choice in entry.choices),
        parameter_factor=factor,
        measurement=measure_status(feature, source[0])
        if source is not None and not derived
        else None,
    )


#: Felder, die an einer Art keinen Gegenstand haben, obwohl ihre Vorgabe
#: nicht null ist: Der Durchmesser von *Merkmal ändern* steht auf 8 mm, und
#: ein Muster hat keinen — seine Maße sind Teilung, Zellbreite und Tiefe.
_NOT_A_FIELD: Final[frozenset[tuple[str, str]]] = frozenset(
    {
        ("pattern", "diameter"),
        # Der Musterstil hat eine Vorgabe (``other``), aber nur ein Muster hat
        # einen Stil.
        *((kind, "style") for kind in ("pin", "cone", "sphere", "fillet", "torus", "thread")),
    }
)


def _carried_by(entry: Any, feature: Feature) -> bool:
    """Trägt das Merkmal die Kennzahl, aus der dieses Feld liest?

    Ein Feld, das nur eine Merkmalsart kennt — die Rohrdicke des Rings, die
    Steigung des Gewindes —, stand sonst an jedem änderbaren Merkmal mit
    „0 mm“: eine Frage ohne Gegenstand (Review, 21.09.2026). Was das Merkmal
    nicht misst und wofür das Schema nichts vorgibt, ist dort kein Feld.
    Eine Vorgabe ungleich null bleibt: Sie ist eine Aussage, kein Messwert —
    außer die Art sagt ausdrücklich, dass sie das Maß nicht hat
    (:data:`_NOT_A_FIELD`).
    """
    if (feature.kind, entry.name) in _NOT_A_FIELD:
        return False
    source = feature_value_source(entry.name, feature)
    if source is None or source[0] in feature.params:
        return True
    return bool(getattr(entry, "default", None))


def _fields_of(spec: Any, feature: Feature) -> tuple[ActionField, ...]:
    """Die Felder einer Operation — ohne die Merkmalskennung.

    ``at_feature`` steht nicht dabei: Das Panel weiß, welches Merkmal gewählt
    ist, und ein Feld dafür wäre eine Frage, deren Antwort schon dasteht.
    """
    return tuple(
        _action_field(entry, feature, spec.name)
        for entry in spec.params.spec()
        # Die freie Oberflächenrichtung gehört zum Platzierungsdialog.
        # Die Schnellbearbeitung verschiebt das gewählte Merkmal mit seiner
        # bisherigen Richtung; eine Änderung erfolgt über die eigene Drehzeile.
        # Gefragt wird das Schema nach seinen Richtungsfeldern — ein Rezept
        # mit eigenem Maß ``nx`` nennt sie anders, und die blieben sonst stehen.
        if entry.kind not in {"feature", "features"}
        and entry.name not in normal_fields_of(spec)
        # Ein Marker einer Migration (``ParamSpec.internal``) ist an keinem
        # Merkmal ein Feld: ``measured_frame``, ``legacy_slot_tool``.
        and not entry.internal
        and _carried_by(entry, feature)
        # Was die Operation selbst erfragt, ist hier kein Feld: Die Antwort
        # entsteht beim Ausführen und gilt nur, wo die Frage einen Gegenstand
        # hat (:func:`~app.core.registry.surfaces.asked_fields`). *Merkmal
        # entfernen* wäre sonst an jeder Bohrung ein Knopf mit einem
        # Auswahlfeld darüber, das an den meisten nichts tut.
        and entry.name not in asked_fields(spec)
    )


def actions_for(
    feature: Feature,
    features: Mapping[FeatureId, Feature] | None = None,
    *,
    mesh: MeshData | None = None,
    cavity: tuple[Feature, ...] | None = None,
    touches_other: bool = False,
    reason: FeatureGroupReason | None = None,
    cancelled: CancelToken | None = None,
    only: str | None = None,
) -> list[FeatureAction]:
    """Was sich an diesem Merkmal tun lässt — und was nicht, mit Grund.

    ``only`` beschränkt die Antwort auf die Zeile dieser Operation, ohne
    Kammer und Verschluss — so fragt :func:`move_refusal`.

    Gilt eine Handlung, trägt sie den Registernamen und ihre Felder samt
    heutigem Wert. Gilt sie nicht, steht sie **trotzdem** in der Liste, mit
    ``op=None`` und einem Satz: Ein Panel, das bei einer Verrundung nur den
    Radius zeigt, lässt den Kunden raten, ob der Rest fehlt oder vergessen
    wurde. Mit ``mesh`` folgt der Hinweis aufs gemeinsame Versetzen der echten
    Randringkette; ohne bleibt die bisherige Paar-Auskunft für ältere Aufrufer.

    ``cavity``, ``touches_other`` und ``reason`` sagen, ob das Merkmal seinen
    Hohlraum mit anderen teilt oder seine Ränder unlesbar sind
    (``relations.cavity_chain_state_at``). Dann tragen die
    Handlungen, die daran scheitern würden, ``op=None`` und den Satz, den die
    Operation beim Rechnen sagt — gemessen am 14.09.2026 an
    ``plate_countersunk.stl``: *Drehen* und *Verdoppeln* an der Senkung und
    *Zum Langloch ziehen* an der gesenkten Bohrung öffneten eine Vorschau ohne
    Bild und hielten beim Übernehmen die Kette an.
    """
    if cancelled is not None:
        cancelled.raise_if_cancelled()
    actions: list[FeatureAction] = []
    edge_blocked = fillet_blocked(feature, features, mesh)
    piece_blocked = cone_piece_blocked(feature) or torus_blocked(feature, mesh)
    # **Die Kette einmal gefragt, für alle Zeilen.** Was der Aufrufer mitbringt,
    # gilt; sonst fragt das Netz — und dieselbe Antwort speist die Sperre am
    # geteilten Hohlraum (*Zum Langloch ziehen*) und die am Merkmal ohne
    # eigenen Körper (:func:`no_own_body`).
    if (
        cavity is None
        and not touches_other
        and mesh is not None
        and features is not None
        and feature.kind in ("hole", "cone")
    ):
        from app.core.perceive.relations import cavity_chain_state_at

        state = cavity_chain_state_at(feature, features, mesh)
        touches_other, reason = state.touches_other, state.reason
        cavity = state.chain if state.chain is not None else ()
    own_body_blocked = no_own_body(feature, cavity, touches_other, mesh, reason=reason)
    from app.core.geom.prepare_ops import (
        FILLED_BORE_REASONS,
        HOLE_IS_NOT_EMPTY,
        OTHER_PART_IN_THE_BORE,
        hole_has_separate_contents,
        only_a_rim_inside,
    )

    rows = [row for row in ACTION_ORDER if only is None or only in row]
    # Ein Langloch schneidet fremde Teile nur innerhalb seiner Bohrungstiefe.
    # Die übrigen Handlungen behalten die Absage für Material im Hohlraum.
    separate_contents = (
        own_body_blocked is OTHER_PART_IN_THE_BORE
        and mesh is not None
        and any("slot_hole" in row for row in rows)
        and hole_has_separate_contents(mesh, feature, cancelled=cancelled)
    )
    # **Eine Haltelippe ist kein Inhalt** — für *Merkmal verschieben*, das die
    # Tasche samt Lippe über ihre Luft versetzt (``prepare_ops._tool_for``,
    # BOHRUNG-13). Die Karte sperrte sie, die Operation rechnete (RM-535).
    rim_only = (
        own_body_blocked is HOLE_IS_NOT_EMPTY
        and mesh is not None
        and any("move_feature" in row for row in rows)
        and only_a_rim_inside(mesh, feature)
    )
    moving_blocked = move_blocked(feature, features, mesh)

    for candidates in rows:
        known = [spec for spec in map(_spec_or_none, candidates) if spec is not None]
        if not known:
            # Eine Zeile, deren Operationen es (noch) nicht gibt, ist kein Fehler
            # des Panels — sie fehlt, und die Oberfläche bietet sie nicht an.
            continue
        fitting = next((spec for spec in known if feature.kind in spec.applies_to), None)
        # Ein Kegel, der keine Senkung ist (Verengung, Verjüngung), sagt an den
        # Zeilen, die für die Senkung gebaut sind, seinen eigenen Satz (R3).
        not_this_cone = cone_reason(feature, (fitting or known[0]).name)
        if fitting is not None and piece_blocked is not None:
            actions.append(FeatureAction(title=fitting.title, op=None, reason=piece_blocked))
        elif fitting is not None and fitting.name == "move_feature" and moving_blocked:
            actions.append(FeatureAction(title=fitting.title, op=None, reason=moving_blocked))
        elif not_this_cone is not None:
            actions.append(
                FeatureAction(title=(fitting or known[0]).title, op=None, reason=not_this_cone)
            )
        elif (
            fitting is not None
            and own_body_blocked is not None
            and (fitting.name in _NEED_AN_OWN_BODY or own_body_blocked in FILLED_BORE_REASONS)
            and not (fitting.name == "slot_hole" and separate_contents)
            and not (fitting.name == "move_feature" and rim_only)
        ):
            actions.append(FeatureAction(title=fitting.title, op=None, reason=own_body_blocked))
        elif fitting is not None and edge_blocked is not None and fitting.name in _EDGE_OPS:
            # Was die Operation an dieser Rundung ablehnen würde, steht grau —
            # mit ihrem Satz (:func:`fillet_blocked`).
            actions.append(FeatureAction(title=fitting.title, op=None, reason=edge_blocked))
        elif (
            fitting is not None
            and fitting.name == "remove_feature"
            and feature.kind == "fillet"
            and feature.params.get("radial", False)
        ):
            actions.append(
                FeatureAction(
                    title=fitting.title,
                    op=None,
                    reason=_(
                        "Diese runde Wand ist keine abgerundete Kante. Ändern Sie "
                        "ihren Radius über „Merkmal ändern“."
                    ),
                )
            )
        elif fitting is not None and (lipped := narrowing_reason(fitting.name, cavity)):
            # Die Bohrung einer Kette mit Verengung — deren Satz, nicht der
            # über eine Senkung (:func:`narrowing_reason`).
            actions.append(FeatureAction(title=fitting.title, op=None, reason=lipped))
        elif fitting is not None and (
            shared := _shares_its_cavity(
                fitting.name,
                feature,
                features,
                mesh=mesh,
                cavity=cavity,
                touches_other=touches_other,
                reason=reason,
            )
        ):
            actions.append(FeatureAction(title=fitting.title, op=None, reason=shared))
        elif fitting is not None and (
            unsized := _countersink_unsized(fitting.name, feature, features, mesh, cavity)
        ):
            actions.append(FeatureAction(title=fitting.title, op=None, reason=unsized))
        elif fitting is not None:
            fields = _fields_of(fitting, feature)
            if fitting.name == "resize_hole" and mesh is not None and features is not None:
                from app.core.errors import ValidationError
                from app.core.geom.prepare_ops import bore_entrance

                try:
                    entrance = bore_entrance(
                        mesh, feature, features, cavity=cavity, touches_other=touches_other
                    )
                except ValidationError:
                    entrance = None
                if entrance is not None:
                    fields = tuple(
                        replace(entry, value="follow") if entry.name == "entrance_mode" else entry
                        for entry in fields
                    )
            actions.append(
                FeatureAction(
                    title=fitting.title,
                    op=fitting.name,
                    note=_note_for(fitting.name, feature, features, mesh=mesh, cavity=cavity),
                    fields=fields,
                )
            )
        elif feature.kind == "fillet" and feature.params.get("radial", False):
            # Dieselbe Zeile grau wie an jeder Verrundung — nur der Satz ist
            # ein anderer, denn diese Wand hat keine Kante.
            actions.append(
                FeatureAction(title=known[0].title, op=None, reason=ROUND_WALL_HAS_NO_PLACE)
            )
        else:
            # Der Titel der ersten bekannten Operation benennt die Zeile —
            # deshalb steht in ``ACTION_ORDER`` die allgemeinere vorn.
            #
            # Und der Grund kommt zuerst aus der genaueren Tabelle: Eine Kugel
            # lässt sich versetzen und ändern, nur nicht drehen, und der Satz
            # über ihre Mitte wäre dort falsch.
            actions.append(
                FeatureAction(
                    title=known[0].title, op=None, reason=_no_way(known[0].name, feature.kind)
                )
            )
    if only is not None:
        return actions
    chamber = chamber_action(feature, features, mesh, cancelled=cancelled)
    if chamber is not None:
        actions.append(chamber)
    closure = closure_action(feature, features, mesh, cancelled=cancelled)
    if closure is not None:
        actions.append(closure)
    return actions


def move_refusal(
    feature: Feature,
    features: Mapping[FeatureId, Feature] | None,
    mesh: MeshData | None,
    *,
    cancelled: CancelToken | None = None,
) -> TranslatableText | str | None:
    """Warum *Merkmal verschieben* an diesem Merkmal absagt — sonst ``None``.

    **Die eine Frage für Karte, Operation und Griff** (RM-535): Sie ist die
    Zeile *Merkmal verschieben* aus :func:`actions_for`, also genau das, was
    die Karte zeigt. Die Karte bot an Wulst und Kehle X/Y/Z an, an denen
    ``move_feature`` absagte, und sperrte die Tasche um einen Zapfen, in der
    es rechnete; der Griff fragte nur die Art.
    """
    for row in actions_for(feature, features, mesh=mesh, cancelled=cancelled, only="move_feature"):
        if row.op == "move_feature":
            return None
        if row.op is None:
            return row.reason or reason_against("move_feature", feature.kind)
    return reason_against("move_feature", feature.kind)


#: Welche Maße *Kammer ändern* an welcher Bauart anbietet: Eine Nut, eine
#: Ringkammer und ein offener Kanal haben keine Länge innen.
_CHAMBER_FIELDS: Final[dict[str, tuple[str, ...]]] = {
    "closed": ("width", "length", "depth"),
    "groove": ("width", "depth"),
    "ring": ("width", "depth"),
    "trough": ("width", "depth"),
}


def chamber_action(
    feature: Feature,
    features: Mapping[FeatureId, Feature] | None,
    mesh: MeshData | None,
    *,
    cancelled: CancelToken | None = None,
) -> FeatureAction | None:
    """*Kammer ändern* an jedem Merkmal einer Kammer, einer Nut oder eines Kanals (RM-184).

    Die Felder tragen die Maße der **Gruppe**, nicht die des gewählten Merkmals:
    Wer an einer Wand klickt, ändert das Innenmaß der Kammer. Was sich nicht als
    Ganzes ändern lässt (geteilte Wände, unterbrochener Rand), steht mit dem Satz
    der Operation da (``groups.reason_against_group``) — dieselbe Frage wie im
    Kern, keine zweite Fassung.
    """
    if features is None or mesh is None or feature.kind not in ("face", "fillet", "curved_face"):
        return None
    spec = _spec_or_none("resize_chamber")
    if spec is None:
        return None
    from app.core.perceive.groups import functional_groups, group_of, reason_against_group

    group = group_of(feature.id, functional_groups(features, mesh, cancelled=cancelled))
    if group is None or group.kind not in ("chamber", "channel") or group.variant == "passage":
        return None
    refusal = reason_against_group(group, features)
    if refusal is not None:
        return FeatureAction(title=spec.title, op=None, reason=refusal)
    wanted = _CHAMBER_FIELDS.get(group.variant, ("width", "length", "depth"))
    fields = []
    for entry in spec.params.spec():
        value = group.measure(entry.name)
        if entry.name not in wanted or value is None:
            continue
        fields.append(
            ActionField(
                name=entry.name,
                label=entry.title,
                unit=str(entry.unit or ""),
                value=float(value),
                kind="length",
                minimum=entry.minimum,
                maximum=entry.maximum,
                measurement=MeasureStatus("exact", "facets", available=True),
            )
        )
    return FeatureAction(
        title=spec.title,
        op=spec.name,
        note=_(
            "Ändert die ganze Kammer: Boden, Wände und Rundungen wandern gemeinsam, "
            "außen bleibt sie gleich."
        ),
        fields=tuple(fields),
    )


def closure_action(
    feature: Feature,
    features: Mapping[FeatureId, Feature] | None,
    mesh: MeshData | None,
    *,
    cancelled: CancelToken | None = None,
) -> FeatureAction | None:
    """*Verschluss ändern* an jedem Merkmal eines Bajonetts oder einer Rastung (RM-184).

    Zwei Felder, vorbelegt mit null: um wie viel mehr Spiel und um wie viel
    Grad mehr Drehweg — ein Verschluss trägt kein Spiel, das sich an ihm allein
    messen ließe, die Gegenseite gehört einem anderen Teil. Ein Feld steht nur
    da, wo die Operation es rechnet (``groups.reason_against_play``,
    ``reason_against_turn``), und der Satz zum fehlenden steht darunter. Geht
    keines, steht die Zeile grau mit dem Satz der Operation
    (``groups.reason_against_closure_change``).
    """
    if features is None or mesh is None:
        return None
    spec = _spec_or_none("resize_closure")
    if spec is None:
        return None
    from app.core.perceive.groups import (
        functional_groups,
        group_of,
        reason_against_closure_change,
        reason_against_play,
        reason_against_turn,
    )

    group = group_of(feature.id, functional_groups(features, mesh, cancelled=cancelled))
    if group is None or group.kind != "closure":
        return None
    refusal = reason_against_closure_change(group, features, mesh)
    if refusal is not None:
        return FeatureAction(title=spec.title, op=None, reason=refusal)
    missing = {
        "play": reason_against_play(group, features, mesh),
        "turn": reason_against_turn(group, features, mesh),
    }
    fields = tuple(
        ActionField(
            name=entry.name,
            label=entry.title,
            unit=str(entry.unit or ""),
            value=0.0,
            kind="length" if entry.name == "play" else "angle",
            minimum=entry.minimum,
            maximum=entry.maximum,
            measurement=MeasureStatus("exact", "parameter", available=True),
        )
        for entry in spec.params.spec()
        if entry.name in missing and missing[entry.name] is None
    )
    note = str(
        _(
            "Ändert alle Stellungen zugleich: Nocken schmaler, Mulden und Wege breiter, der "
            "Anschlag weiter — ein negativer Wert umgekehrt."
        )
    )
    absent = [reason for reason in missing.values() if reason is not None]
    return FeatureAction(
        title=spec.title,
        op=spec.name,
        note=" ".join([note, *absent]),
        fields=fields,
    )


#: Die zwei Handlungen an einer Rundung, die eine Kante unter ihr brauchen
#: oder eine Wand, die sich radial versetzen lässt.
_EDGE_OPS: Final = ("remove_feature", "resize_feature")

#: Die Handlungen, die einen Hohlraum als eigenen Körper bauen müssen — und an
#: einem Merkmal absagen, das ohne klare Kette in einen fremden Rand übergeht
#: (``prepare_ops.NO_OWN_BODY``: ``feature_placement_geometry``,
#: ``_stands_alone``, ``_closed_at``).
_NEED_AN_OWN_BODY: Final = (
    "move_feature",
    "duplicate_feature",
    "rotate_feature",
    "remove_feature",
    "resize_feature",
)


def no_own_body(
    feature: Feature,
    cavity: tuple[Feature, ...] | None,
    touches_other: bool,
    mesh: MeshData | None = None,
    *,
    reason: FeatureGroupReason | None = None,
) -> TranslatableText | None:
    """Warum Versetzen, Verdoppeln, Drehen, Entfernen und Ändern an diesem
    Merkmal absagen würden — oder ``None``.

    Drei Gründe, alle aus der Operation und mit ihrem Satz:

    * Eine Bohrung oder Senkung, die einen **fremden Rand berührt, ohne dass
      daraus eine eindeutige Kette wird** (``cavity_chain_state_at`` liefert
      keine Kette und ``touches_other``): Aus ihren Flächen entsteht kein
      Werkzeug, und mitnehmen lässt sich nichts, was nicht benannt ist
      (``NO_OWN_BODY``). Sind es die **eigenen Ränder, die sich nicht lesen
      lassen** (``reason`` ist ``cavity_topology_unavailable``), sagt die
      Zeile das und nicht „geht in einen anderen Hohlraum über"
      (``CAVITY_TOPOLOGY_UNKNOWN``, P1.5).
    * Ein Kegel oder eine Kuppel, aus deren Flächen **kein Körper** entsteht
      — der Rand hat zu viele Ringe oder liegt in keiner Ebene
      (``prepare_ops.has_own_body``, ``NO_BODY_FROM_FACES``): ein Kegelstumpf
      mit einer Querbohrung durch den Mantel, an einem Uhrenteil fünfmal nach
      dem Klick (15.09.2026). Nur mit Netz, denn die Ringe stehen im Netz.
    * Eine Bohrung, in deren Zylinder **Material steht** — die Innenwand
      eines Rades mit Speichen, ein Topf mit Zapfen
      (``prepare_ops.hole_is_clear``, ``HOLE_IS_NOT_EMPTY``): Ihr Werkzeug
      wäre ein voller Zylinder, der die Speichen mitnimmt (Uhrenteil 06,
      minus 49 Prozent Volumen). Hier steht jede Zeile grau, nicht nur die
      Körperhandlungen. Gehört das Material einem anderen Teil, sagt es
      ``OTHER_PART_IN_THE_BORE`` (``prepare_ops.filled_bore_reason``).
    """
    if feature.kind == "hole" and mesh is not None and feature.face_indices:
        # **Vor der Kette gefragt**, denn ``_tool_for`` fragt es an jeder
        # Bohrung: Eine Radinnenwand mit Speichen, an deren Mündung eine Fase
        # erkannt wurde, ist eine Kette — und trotzdem keine Bohrung.
        from app.core.geom.prepare_ops import filled_bore_reason, hole_is_clear

        if not hole_is_clear(mesh, feature):
            return filled_bore_reason(mesh, feature)
    if feature.kind not in ("hole", "cone", "sphere") or cavity:
        return None
    if touches_other and feature.kind != "sphere":
        from app.core.geom.prepare_ops import CAVITY_TOPOLOGY_UNKNOWN, NO_OWN_BODY

        return CAVITY_TOPOLOGY_UNKNOWN if reason == "cavity_topology_unavailable" else NO_OWN_BODY
    if mesh is None or not feature.face_indices:
        return None
    from app.core.geom.prepare_ops import (
        HOLE_IS_NOT_EMPTY,
        NO_BODY_FROM_FACES,
        has_own_body,
        hole_is_clear,
    )

    if feature.kind == "hole":
        # Eine Bohrung, in deren Zylinder Material steht, ist die Innenwand
        # eines Rades oder ein Topf mit Zapfen — jede Zeile sagt es, mit dem
        # Satz aus ``_tool_for``. Ob ihre Flächen einen Körper hergeben, ist
        # dann gleich; ohne Material bleibt der Zylinder aus Kennzahlen ihr
        # Rückfall.
        return None if hole_is_clear(mesh, feature) else HOLE_IS_NOT_EMPTY
    if has_own_body(mesh, feature, alone=not touches_other):
        return None
    return NO_BODY_FROM_FACES


#: Warum *Merkmal ändern* an einer **Verengung** nicht angeboten wird (R3).
#:
#: Eine Verengung ist ein hohler Kegel, der sich zu seiner Bohrung hin öffnet
#: — die Haltelippe einer Magnettasche (``features.narrowings_marked``). Das
#: Maß, das *Merkmal ändern* am Kegel setzt, ist sein weites Ende, und das
#: ist an der Lippe die Tasche selbst: Am exakten Körper stand danach über der
#: Tasche eine Hinterschneidung (Mündung 7,97 → 8,47 mm bei einer Tasche von
#: 8,24), am Netz sagte die Operation ab — mit einem Satz über eine Senkung
#: (gemessen 26.09.2026, Durchsicht 0.5.1). Was an ihr gilt, steht im Satz.
NARROWING_HAS_NO_SIZE: Final = _(
    "Die Weite einer Verengung lässt sich hier nicht ändern. „Merkmal entfernen“ nimmt "
    "sie weg; danach ist die Bohrung bis zur Mündung gleich weit."
)

#: *Zum Langloch ziehen* an einer Verengung — der Satz des Kegels sprach von
#: einer Senkung, die es dort nicht gibt. An der Bohrung darunter ebenso: Dort
#: hieß es „Entfernen Sie zuerst die Senkung“ (:func:`narrowing_reason`).
NARROWING_STAYS_ROUND: Final = _(
    "Ein Langloch nimmt eine Verengung nicht mit. Nehmen Sie sie zuerst mit „Merkmal "
    "entfernen“ weg, oder lassen Sie die Bohrung rund."
)

#: *Merkmal drehen* an einer Verengung und an der Bohrung darunter.
#:
#: Gekippt steht die Lippe schräg zur Fläche: Auf der hohen Seite schneidet
#: die Fläche sie weg, auf der tiefen führt die Öffnung als Schacht bis zur
#: Fläche. Das liest keine der beiden Erkennungen wieder als Verengung.
#: Probeweise zugelassen (Durchsicht 0.5.1, rest-lippe), stand danach am
#: exakten Körper eine „Senkung“ im Baum, am Netz eine gerundete Seite neben
#: einer Tasche ohne Flächen — und jede weitere Handlung rechnete ohne die
#: Lippe: *Bohrung ändern* nahm sie am Netz still weg, ein zweites Drehen ließ
#: Material in der Öffnung stehen, *Nur Bohrungsdurchmesser* ergab am exakten
#: Körper einen undichten Körper. Vorher sagten Panel und Operation mit dem
#: Satz über eine Senkung ab. Ohne Lippe kippt die Tasche.
NARROWING_STAYS_STRAIGHT: Final = _(
    "Eine Verengung lässt sich nicht drehen. Nehmen Sie sie zuerst mit „Merkmal "
    "entfernen“ weg, oder lassen Sie die Bohrung gerade."
)

#: Und an einer **Verjüngung**, einem aufgesetzten Kegel: Gezogen wird ein
#: Loch, und die Verjüngung ist Material — der Satz über die Senkung auf ihrer
#: Bohrung stand bis zur Durchsicht 0.5.1 auch dort.
TAPER_IS_MATERIAL: Final = _(
    "Gezogen wird ein Loch, und eine Verjüngung ist Material. Ihr Maß ändert „Merkmal ändern“."
)

#: Was nur an einer **Senkung** etwas Sinnvolles tut: *Senken* heißt an einem
#: gewählten Kegel „anders senken" (``countersink_hole``, ``applies_to``). An
#: einer Verengung schnitt es einen Trichter, der die Haltelippe mitnahm
#: (Mündung 7,98 → 9,87 mm, gemessen 26.09.2026), an einer Verjüngung einen
#: Trichter in das Material, das sie ist.
_ONLY_AT_A_COUNTERSINK: Final[frozenset[str]] = frozenset({"countersink_hole"})


def narrows_the_mouth(feature: Feature) -> bool:
    """Ob dieser Kegel eine Verengung ist — die Erkennung trägt es als ``narrowing`` (R3)."""
    return feature.kind == "cone" and bool(feature.params.get("narrowing"))


def not_offered_at(feature: Feature) -> frozenset[str]:
    """Die Handlungen, die an diesem Merkmal gar nicht erst angeboten werden (R3).

    ``applies_to`` fragt nach der Art, und ein Kegel war dort eine Senkung.
    Ist er eine Verengung oder eine Verjüngung, fällt weg, was nur an einer
    Senkung etwas tut (:data:`_ONLY_AT_A_COUNTERSINK`). Die Karte rechts liest
    diese Menge (``ui.selection_operations``) — oben in der Schnellzeile wie
    in der Liste darunter.
    """
    if feature.kind != "cone" or feature.params.get("partial"):
        return frozenset()
    if narrows_the_mouth(feature) or not feature.params.get("recess"):
        return _ONLY_AT_A_COUNTERSINK
    return frozenset()


def cone_reason(feature: Feature, op: str) -> TranslatableText | None:
    """Der Satz, wo ein Kegel keine Senkung ist und die Handlung nicht passt — oder ``None``.

    Die Tabellen oben fragen nach der Art, und ein Kegel war dort eine
    Senkung. An einer **Verengung** (:func:`narrows_the_mouth`) gilt *Merkmal
    ändern* nicht, und *Zum Langloch ziehen* und *Merkmal drehen* sagen, warum
    sie sie nicht mitnehmen; an einer **Verjüngung** sagt *Zum Langloch
    ziehen*, dass sie Material ist. Panel und Operation lesen denselben Satz
    (``prepare_ops._movable_feature``).
    """
    if feature.kind != "cone" or feature.params.get("partial"):
        return None
    if narrows_the_mouth(feature):
        # Beide Operationen der Zeile *Größe ändern* — auch die der Bohrung,
        # sonst verwiese deren Absage auf die gesperrte Schwester.
        if op in ("resize_feature", "resize_hole"):
            return NARROWING_HAS_NO_SIZE
        return narrowing_reason(op, (feature,))
    if op == "slot_hole" and not feature.params.get("recess"):
        return TAPER_IS_MATERIAL
    return None


def narrowing_reason(op: str, chain: Sequence[Feature] | None) -> TranslatableText | None:
    """Was eine Kette mit Verengung nicht mitnimmt — an der Verengung selbst
    (:func:`cone_reason`) wie an der Bohrung darunter —, oder ``None``.

    *Zum Langloch ziehen* und *Merkmal drehen*. An der Bohrung einer
    Magnettasche sagten beide bis zur Durchsicht 0.5.1 etwas über eine
    Senkung: das Langloch „Entfernen Sie zuerst die Senkung“, das Drehen, das
    Merkmal gehe in einen anderen Hohlraum über, „etwa eine Senkung in ihre
    Bohrung“. Panel und Operation lesen denselben Satz
    (``prepare_ops.rotate_feature``, ``prepare_ops.slot_hole``).
    """
    if not chain or not any(narrows_the_mouth(member) for member in chain):
        return None
    if op == "slot_hole":
        return NARROWING_STAYS_ROUND
    if op == "rotate_feature":
        return NARROWING_STAYS_STRAIGHT
    return None


def cone_piece_blocked(feature: Feature) -> TranslatableText | None:
    """Warum an einer Kegelfläche jede Körperhandlung absagen würde — oder ``None``.

    Die Erkennung kennzeichnet ein Kegelstück ohne eigenen Körper mit
    ``partial`` (``features._partial_cones_folded``); Panel und
    ``prepare_ops._movable_feature`` lesen dasselbe Kennzeichen und sagen
    denselben Satz.
    """
    if feature.kind == "cone" and feature.params.get("partial", False):
        return CONE_PIECE_HAS_NO_BODY
    return None


def fillet_blocked(
    feature: Feature, features: Mapping[FeatureId, Feature] | None, mesh: MeshData | None
) -> TranslatableText | None:
    """Warum *Entfernen* und *Radius ändern* an dieser Rundung absagen würden —
    oder ``None``.

    Zwei Gründe, beide aus der Operation und mit ihrem Satz:

    * Eine Rundung, die **keine Kante ersetzt** — quer zu ihrer Achse nicht
      genau zwei ebene Flächen neben sich —, lässt sich nicht auf eine Kante
      zurückrechnen (``edges.sharp_corner``, :func:`features.replaces_an_edge`).
      Der Umrissbogen eines Uhrenankers, die Rundung zwischen Klotz und
      Zylinder: 50 von 52 Versuchen an 34 Modellen aus dem Netz endeten so,
      nach dem Klick (15.09.2026).
    * Eine runde Wand, die **tangential in ihre Nachbarn übergeht**
      (``tangent`` aus der Erkennung), lässt sich nicht radial versetzen
      (``edges.radial_rounding``).

    **Nur mit Netz**, wie die Sperre am geteilten Hohlraum: Ohne Netz ist
    die Frage nach den Nachbarn nicht zu beantworten, und eine Vermutung
    stellt keine Zeile grau. Eine **Ecke** braucht keines: Wo verrundete
    Kanten zusammenlaufen, heißt die Kugel an beiden Kernen Verrundung, hat
    aber keine Achse und damit keine Kante, auf die sie sich zurückführen
    ließe (RM-226) — die Operation sagt denselben Satz.
    """
    if feature.kind != "fillet":
        return None
    if feature.params.get("radial", False):
        return WALL_BLENDS_INTO_ITS_NEIGHBOURS if feature.params.get("tangent") else None
    from app.core.geom.edges import NOT_BETWEEN_TWO_PLANES

    axis = feature.params.get("axis")
    if not isinstance(axis, list | tuple) or len(axis) != 3:
        return NOT_BETWEEN_TWO_PLANES
    if mesh is None or features is None or not feature.face_indices:
        return None
    from app.core.perceive.features import (
        nearly_flat_mask,
        planar_mask,
        replaces_an_edge,
    )

    # **Dieselbe Flächenmenge wie die Operation** (``edges._around``): die
    # Ebenen frisch am Netz, nicht die ``face``-Einträge des Baums. Die
    # verschluckt ein Langloch (``SWALLOWED_BY_A_SLOT``), und an einer
    # Freiform stehen gar keine — das Panel hätte dort grau gestellt, was die
    # Operation rechnet. Einmal je Körper gelesen (:func:`planar_mask`), nicht
    # je Klick: Das Panel fragt hier im Hauptfaden.
    planar = planar_mask(mesh) | nearly_flat_mask(mesh.raw, features)
    centre = feature.params.get("centre")
    if replaces_an_edge(
        mesh.raw,
        feature.face_indices,
        [float(v) for v in axis],
        planar,
        centre=[float(v) for v in centre] if isinstance(centre, list | tuple) else None,
    ):
        return None
    return NOT_BETWEEN_TWO_PLANES


#: Die Handlungen, die einen Hohlraum nur nehmen, wenn er dem Merkmal allein
#: gehört — dieselbe Bedingung wie in ``prepare_ops.slot_hole``. *Drehen* und
#: *Verdoppeln* standen bis zum 15.09.2026 mit hier; seither nehmen sie die
#: Kette mit (RM-172), und die Zeile bleibt bedienbar.
_WANT_A_PLAIN_BORE: Final = ("slot_hole",)


def _shares_its_cavity(
    op: str,
    feature: Feature,
    features: Mapping[FeatureId, Feature] | None,
    *,
    mesh: MeshData | None,
    cavity: tuple[Feature, ...] | None,
    touches_other: bool,
    reason: FeatureGroupReason | None = None,
) -> TranslatableText | None:
    """Warum diese Handlung an einem geteilten Hohlraum absagen würde — oder ``None``.

    Dieselbe Bedingung wie in der Operation (``relations.cavity_is_shared``)
    und derselbe Satz (``NEEDS_A_PLAIN_BORE``): *Zum Langloch ziehen* nimmt
    einen Hohlraum nur, wenn er dem Merkmal allein gehört — an der Bohrung
    wie an ihrer Senkung. *Drehen* und *Verdoppeln* standen vom 14. bis zum
    15.09.2026 mit auf der Liste — gemessen hatten sie an der Bohrung einer
    gesenkten Bohrung nur den Stumpf unter der Senkung gekippt oder kopiert;
    seit RM-172 nehmen sie die Kette mit, und die Zeile bleibt bedienbar.

    **Die Sperre kommt aus dem Netz, nie aus einer Schätzung.** Was der
    Aufrufer aus ``cavity_chain_state_at`` mitbringt (``cavity``,
    ``touches_other``), gilt; bringt er nichts mit, fragt die Funktion das
    Netz selbst — dieselbe Zusage also auch für ``actions_for(feature,
    features, mesh=mesh)`` ohne die zwei Schlüsselwörter. Ohne Netz gibt es
    keine Sperre: ``bore_and_widening_at`` schätzt die Kette aus Parametern,
    und eine Schätzung darf keine Zeile grau stellen, die die Operation liefe.
    """
    if op not in _WANT_A_PLAIN_BORE or feature.kind not in ("hole", "cone"):
        return None
    if touches_other:
        shared = True
    elif mesh is None or features is None:
        return None
    elif cavity is None:
        from app.core.perceive.relations import cavity_chain_state_at, cavity_is_shared

        state = cavity_chain_state_at(feature, features, mesh)
        shared, reason = cavity_is_shared(state), state.reason
    else:
        shared = bool(cavity)
    if not shared:
        return None
    from app.core.geom.prepare_ops import CAVITY_TOPOLOGY_UNKNOWN, NEEDS_A_PLAIN_BORE

    # Unlesbare Ränder sind keine „weiteren Abschnitte": derselbe Satz wie an
    # den Körperhandlungen, nicht der Rat, eine Senkung zu entfernen.
    return (
        CAVITY_TOPOLOGY_UNKNOWN if reason == "cavity_topology_unavailable" else NEEDS_A_PLAIN_BORE
    )


def _countersink_unsized(
    op: str,
    feature: Feature,
    features: Mapping[FeatureId, Feature] | None,
    mesh: MeshData | None,
    cavity: tuple[Feature, ...] | None,
) -> TranslatableText | None:
    """Warum *Merkmal ändern* an einem Kegel einer Bohrungskette absagen würde —
    mit dem Satz der Operation (``prepare_ops.countersink_resize_refusal``) —,
    oder ``None``, wo sie die Senkung neu schneidet.

    Bis zur Durchsicht 0.5.1 stand die Zeile an jeder Senkung offen, und am
    Netz sagte die Operation an einer Senkbohrung mit dem Satz über eine
    Senkung ab, die in ihre Bohrung übergeht. **Nur mit Netz und Kette**: Ohne
    die Ringe der Kette gibt es keine Antwort, und eine Vermutung stellt keine
    Zeile grau.
    """
    if op != "resize_feature" or feature.kind != "cone" or not cavity:
        return None
    if mesh is None or features is None:
        return None
    from app.core.geom.prepare_ops import countersink_resize_refusal

    return countersink_resize_refusal(mesh, feature, features, cavity)


def _note_for(
    op: str,
    feature: Feature,
    features: Mapping[FeatureId, Feature] | None,
    *,
    mesh: MeshData | None,
    cavity: tuple[Feature, ...] | None = None,
) -> TranslatableText | str:
    """Eine Folge der Handlung, die erst aus der Nachbarschaft hervorgeht."""
    if op != "move_feature" or features is None:
        return ""
    from app.core.perceive.relations import bore_and_widening_at, cavity_chain_at

    linked = cavity
    if linked is None:
        linked = (
            bore_and_widening_at(feature, features)
            if mesh is None
            else cavity_chain_at(feature, features, mesh)
        )
    if not linked:
        return ""
    return _(
        "Verknüpft: {count} Abschnitte dieser Öffnung werden gemeinsam verschoben.",
        count=len(linked),
    )


def instead_of(op: str, kind: str) -> Any:
    """Die Operation **derselben Panel-Zeile**, die für diese Art gilt.

    *Größe ändern* ist eine Zeile und zwei Operationen: ``resize_hole`` für die
    Bohrung, ``resize_feature`` für alles andere (die Bohrung hat ihren eigenen
    Weg durch den exakten Kern und eine Materialkompensation, die für einen
    Zapfen andersherum liefe). Wer die falsche von beiden ruft, soll den Namen
    der richtigen lesen und nicht „geht nicht".

    ``None``, wenn es in der Zeile keine Schwester für diese Art gibt.
    """
    for candidates in ACTION_ORDER:
        if op not in candidates:
            continue
        for name in candidates:
            spec = _spec_or_none(name)
            if spec is not None and name != op and kind in spec.applies_to:
                return spec
    return None


def _no_way(op: str, kind: str) -> TranslatableText:
    """Der Satz, warum diese Operation für diese Merkmalsart nicht gilt."""
    other = instead_of(op, kind)
    if other is not None:
        return _("Dafür ist „{title}“ da.", title=other.title)
    here = NOT_APPLICABLE_HERE.get((kind, op))
    # Der Satz der Schwester derselben Zeile, wenn diese Operation keinen
    # eigenen hat: *Fläche versetzen* an einem Gewinde sagt, was *Merkmal
    # verschieben* dort sagt (RM-535).
    for row in ACTION_ORDER if here is None and kind not in NOT_APPLICABLE else ():
        if op in row:
            here = next(
                (
                    NOT_APPLICABLE_HERE[(kind, name)]
                    for name in row
                    if (kind, name) in NOT_APPLICABLE_HERE
                ),
                None,
            )
    return here if here is not None else NOT_APPLICABLE.get(kind, _UNKNOWN_KIND)


def reason_against(op: str, kind: str) -> TranslatableText | None:
    """Warum diese Operation diese Merkmalsart nicht annimmt — ``None``, wenn
    sie es tut.

    **Der Kern fragt hier, statt selbst zu entscheiden.** ``applies_to`` stand
    bis zum 03.09.2026 nur im Menü und im Panel; wer eine Operation über Chat
    oder Kommandozeile rief, kam daran vorbei. Und der Satz, den er dann liest,
    ist derselbe, den das Panel in die ausgegraute Zeile schreibt — zwei
    Auskünfte über dieselbe Sache wären eine zu viel.
    """
    spec = _spec_or_none(op)
    if spec is not None and kind in spec.applies_to:
        return None
    return _no_way(op, kind)


def _spec_or_none(name: str) -> Any:
    """Der Registereintrag, oder ``None``, wenn es ihn (noch) nicht gibt."""
    return REGISTRY.get(name) if REGISTRY.has(name) else None


def texture_actions(operation: Any, spec: Any) -> list[FeatureAction]:
    """Bearbeitet die vorhandene Textur und bewahrt Ausdrücke sowie ausgeblendete Werte."""
    from app.core.registry.params import inactive_dependency

    schema = spec.params.spec()
    by_name = {entry.name: entry for entry in schema}
    saved = dict(operation.params)
    effective = {entry.name: saved.get(entry.name, entry.default) for entry in schema}
    fields: list[ActionField] = []
    for name in ("pattern", "width", "height", "pitch", "depth", "mode", "angle"):
        entry = by_name[name]
        if inactive_dependency(entry, schema, effective) is not None:
            continue
        # Bei der ganzen Fläche bleibt deren Ebene maßgeblich, auch wenn
        # vom früheren Rechteck noch eine Wickelart gespeichert ist.
        if name == "angle" and effective["coverage"] == "rectangle" and effective["wrap"] != "flat":
            continue
        fields.append(
            ActionField(
                name=name,
                label=entry.title,
                unit=entry.unit,
                value=effective[name],
                kind=_kind_of(entry),
                minimum=entry.minimum,
                maximum=entry.maximum,
                choices=tuple((choice, choice) for choice in (entry.choices or ())),
            )
        )
    shown = {entry.name for entry in fields}
    return [
        FeatureAction(
            title=_("Textur ändern"),
            op=spec.name,
            step=operation.id,
            note=_("Ändert den Schritt, der diese Textur aufgebracht hat."),
            fields=tuple(fields),
            fixed=tuple((name, value) for name, value in saved.items() if name not in shown),
        ),
        FeatureAction(title=_("Textur entfernen"), op=None, step=operation.id),
    ]


def _saved_fields(
    schema: Mapping[str, Any], values: Mapping[str, Any], names: tuple[str, ...]
) -> tuple[ActionField, ...]:
    """Felder aus gespeicherten Schrittwerten und derselben Schemaauskunft aufbereiten."""
    return tuple(
        ActionField(
            name=name,
            label=entry.title,
            unit=entry.unit,
            value=values.get(name, entry.default),
            kind=_kind_of(entry),
            minimum=entry.minimum,
            maximum=entry.maximum,
            choices=tuple((choice, choice) for choice in (entry.choices or ())),
            measurement=MeasureStatus("exact", "parameter", available=True)
            if _kind_of(entry) in {"length", "angle"}
            else None,
            depends_on=entry.depends_on,
        )
        for name in names
        if (entry := schema.get(name)) is not None
    )


def bore_action(operation: Any, spec: Any) -> FeatureAction:
    """Den von ``bore_step_of`` belegten Bohrungsschritt mit seinen Originalwerten anbieten.

    Die Herkunftsprüfung liegt beim Aufrufer. Diese Handlung misst keine
    Weltmaße zurück: Auch nach einer Transformation gelten die gespeicherten
    Schrittwerte, einschließlich Tiefe null für die durchgehende Bohrung.
    Nicht angezeigte Werte bleiben unverändert im ursprünglichen Auftrag.
    """
    schema = {entry.name: entry for entry in spec.params.spec()}
    values = dict(operation.params)
    names = (
        "diameter",
        "depth",
        *(
            name
            for name, entry in schema.items()
            if entry.placement == "front"
            and name not in {"diameter", "depth"}
            and entry.kind not in COLLECTED_KINDS
        ),
    )
    fields = _saved_fields(schema, values, names)
    shown = {entry.name for entry in fields}
    return FeatureAction(
        title=_("Bohrung im ursprünglichen Schritt ändern"),
        op=spec.name,
        step=operation.id,
        note=_(
            "Zeigt die ursprünglichen Schrittwerte vor späteren Größen- und Lageänderungen. "
            "Tiefe 0 bohrt durch das ganze Teil."
        ),
        fields=fields,
        fixed=tuple((name, value) for name, value in values.items() if name not in shown),
    )


def part_actions(operation: Any, spec: Any) -> list[FeatureAction]:
    """Die Handlungen eines Bausteins — an seinem Schritt, nicht an einer Fläche.

    Ein Schlüsselloch besteht aus zwölf Merkmalen: zwei Bohrungen, zehn
    Verrundungen und der Fläche, auf der es sitzt. Wer eine davon anklickt,
    hat **das Schlüsselloch** gemeint und nicht die Kante des Schlitzes; die
    Verrundung trägt für sich gar keine Handlung, und die Fläche bot die
    Handlungen einer Fläche an (Befund Robert, 10.09.2026: „bei einem
    Schlüsselloch-Aufhängung-Baustein haben wir rechts noch die Auswahl wie
    für eine Fläche, hier sollten wir aber alles für das Schlüsselloch
    sehen").

    **Und die Handlungen gelten dem Schritt, nicht dem einzelnen Merkmal.**
    ``resize_feature`` auf die runde Tasche gesetzt bohrte sie auf und ließe
    den Schlitz stehen — aus einem Schlüsselloch würde ein Loch mit einem
    Fortsatz. Was seine Größe wirklich ändert, ist die Schraubengröße im
    Schritt, und die ändert beide Hälften zusammen.

    Drei Handlungen, in dieser Reihenfolge (Robert: „größe ändern, löschen und
    verschieben sollte es geben"):

    * **Maße** — die Felder, die der Baustein vorn führt, ohne seine Lage.
      Welche das sind, entscheidet der Bausteinautor über ``placement``; eine
      zweite Liste hier wüsste es beim nächsten Baustein nicht.
    * **Verschieben** — ``x``, ``y``, ``z`` aus derselben Quelle.
    * **Entfernen** — ohne Felder; sie nimmt den Schritt aus dem Verlauf.

    Die Werte kommen aus dem **Schritt** und nicht aus dem Merkmal. Das ist
    der Unterschied zu :func:`actions_for`: Dort steht, was gemessen wurde,
    hier steht, was eingegeben war — und nur das lässt sich ohne Verlust
    zurückschreiben. Ein Baustein rechnet aus ``size="M4"`` zwei Durchmesser;
    aus den gemessenen Durchmessern käme keine Schraubengröße zurück.
    """
    from app.core.registry.surfaces import PART_PLACEMENT_PARAMS

    placement_params = frozenset(PART_PLACEMENT_PARAMS)
    schema = {entry.name: entry for entry in spec.params.spec()}
    values = dict(getattr(operation, "params", {}) or {})

    # **Ein Sammelparameter bekommt hier kein Feld.** Eine Fachaufteilung ist
    # ein JSON-Text mit einem eigenen Editor (``kind="organizer"``, ebenso
    # ``sketch`` und ``armature``); ``_kind_of`` kennt ihn nicht und gäbe ihm
    # ein Längenfeld — „Fachaufteilung: 0,00 mm". Dieselbe Frage wie bei der
    # Anzahl, die keine Länge ist, eine Stufe weiter: Was das Merkmalfenster
    # nicht zeigen kann, steht in ``FeatureAction.elsewhere`` und führt in den
    # vollen Dialog.
    measures = tuple(
        name
        for name, entry in schema.items()
        if entry.placement == "front"
        and name not in placement_params
        and entry.kind not in COLLECTED_KINDS
    )
    # **Und genannt wird nur, was vorn stand.** ``measures`` filtert
    # ``placement == "front"``, diese Zeile tat es nicht — am
    # Profilklemmen-Einleger hieß der Knopf „Gegenkontur, Vorhandene
    # Außenkontur ändern …", obwohl die zweite hinter der Klappe steht und im
    # Merkmalfenster nie ein Feld hatte.
    collected = tuple(
        name
        for name, entry in schema.items()
        if entry.kind in COLLECTED_KINDS
        and entry.placement == "front"
        and name not in placement_params
    )
    # **Verschoben wird in der Ebene**: ohne ``x`` und ``y`` keine Lage. Am
    # Deckel ist ``z`` die Höhe der Öffnung, leer heißt Oberkante (RM-526);
    # als „Baustein verschieben“ angeboten stand dort ``None`` in einem
    # Zahlenfeld, und das Merkmalfenster warf beim Klick auf den Kragen.
    placement = (
        tuple(name for name in ("x", "y", "z") if name in schema)
        if {"x", "y"} <= schema.keys()
        else ()
    )

    actions: list[FeatureAction] = []
    if measures:
        actions.append(
            FeatureAction(
                title=_("Maße ändern"),
                op=spec.name,
                step=operation.id,
                note=_("Ändert den Schritt, der diesen Baustein gesetzt hat."),
                fields=_saved_fields(schema, values, measures),
                elsewhere=tuple(schema[name].title for name in collected),
            )
        )
    if placement:
        actions.append(
            FeatureAction(
                title=_("Baustein verschieben"),
                op=spec.name,
                step=operation.id,
                fields=_saved_fields(schema, values, placement),
            )
        )
    actions.append(
        FeatureAction(
            title=_("Baustein entfernen"),
            op=None,
            step=operation.id,
            note=_("Nimmt den Schritt aus dem Verlauf. Strg+Z holt ihn zurück."),
        )
    )
    return actions


#: Die Operationen, die an **einer angeklickten Kante** ansetzen.
#:
#: Beide leben im exakten Kern und tragen dieselbe Auswahl: Fünf Gruppen und
#: ``named`` für einzeln gewählte Kanten (``geom.edges.EDGE_CHOICES``). Wer
#: eine Kante anklickt, hat ``named`` bereits beantwortet — einzugeben bleibt
#: das Maß, das die Zeile führt, und was :data:`EDGE_SHAPE_FIELDS` dazu nennt.
#:
#: Eine Liste und keine Ableitung aus ``applies_to``: Eine Kante ist **kein
#: Merkmal**. Sie trägt keine Kennung, die die Erkennung vergibt, und steht
#: darum in keinem ``applies_to`` — die Frage „welche Operation gilt hier"
#: hat an ihr eine andere Antwort als an einer Bohrung.
EDGE_OPERATIONS: Final[tuple[tuple[str, str], ...]] = (
    ("fillet_edges", "radius"),
    ("chamfer_edges", "distance"),
    # Die Gegenrichtung der beiden: Material kommt dazu, statt wegzugehen.
    # Sie steht hier, weil ``tests/test_registry_consistency.py`` jede
    # Operation mit einem ``edges``-Parameter an einer angeklickten Kante
    # verlangt — eine Handlung, die man dort nicht findet, gibt es für den
    # Kunden nicht.
    ("bead_edges", "radius"),
)

#: Was eine Kantenzeile **neben** ihrem Maß führt — je Operation, in dieser Folge.
#:
#: Das eine Maß aus :data:`EDGE_OPERATIONS` bleibt vorn; hier stehen die
#: Felder, die seine Bedeutung bestimmen. Bei der Fase (P6.2) sind es die Art
#: der Bemaßung, der zweite Abstand, der Winkel und der Seitentausch — die
#: letzten drei mit ihrem ``depends_on`` aus dem Schema, sodass die Zeile nur
#: zeigt, was zur gewählten Art gehört. Eine eigene Tabelle und keine zweite
#: Spalte in :data:`EDGE_OPERATIONS`: Die zählt die Test- und Menüwege als
#: Paar aus Operation und Maß, und eine Operation ohne weitere Felder braucht
#: hier keinen Eintrag.
EDGE_SHAPE_FIELDS: Final[dict[str, tuple[str, ...]]] = {
    "chamfer_edges": ("mode", "second_distance", "angle", "flip_sides"),
}
#: Weitere Zeilen an einer angeklickten Kante: eine Operation aus
#: :data:`EDGE_OPERATIONS` in einer zweiten Bedeutung, mit eigenem Titel,
#: ihren Feldern und den Werten, die die Zeile mitbringt.
#:
#: **Verrunden mit Verlauf** (P6.1) ist dieselbe Operation wie *Verrunden* —
#: ein Radius am Anfang, einer am Ende, ``mode="variable_radius"`` fest. Als
#: eigene Zeile steht sie da, weil der Kunde am Griff „dicker werdend
#: verrunden" sucht und nicht „Verrunden, dann Verlauf umschalten"; die
#: Zwischenstellen und die Richtung stehen im vollständigen Dialog.
EDGE_VARIANTS: Final[
    tuple[tuple[str, TranslatableText, tuple[str, ...], tuple[tuple[str, Any], ...]], ...]
] = (
    (
        "fillet_edges",
        _("Verrunden mit Verlauf"),
        ("radius", "end_radius"),
        (("mode", "variable_radius"),),
    ),
)


def edge_actions(key: str) -> list[FeatureAction]:
    """Was sich an dieser einen Kante tun lässt — verrunden und fasen.

    Bis zum Anklicken einer Kante gab es beides nur über den Dialog und eine
    Liste darin: „Senkrecht · 20 mm · x -20,0, y -15,0", zum Ankreuzen. Wer
    **diese eine Ecke** brechen wollte, musste sie in einer Aufzählung
    wiedererkennen.

    Jede Zeile trägt vorn ihr Maß — den Radius beziehungsweise die Breite —
    und dahinter, was :data:`EDGE_SHAPE_FIELDS` für sie nennt (bei der Fase
    Art, zweiter Abstand, Winkel, Seitentausch). Die übrigen Werte bringt sie
    als :attr:`FeatureAction.fixed` mit: ``edges="named"`` und den Schlüssel.
    Danach folgen die Varianten aus :data:`EDGE_VARIANTS` (*Verrunden mit
    Verlauf*) mit ihren eigenen Feldern und festen Werten.
    Die Vorgabe ist die des Registers und nicht ein Maß der Kante: Anders als
    bei einer Bohrung gibt es hier keinen **gemessenen** Wert, den man
    übernehmen könnte — eine scharfe Kante hat keinen Radius, und der
    gewünschte ist der einzige, der zählt.

    Ohne den exakten Kern steht keine der beiden im Register, und dann ist die
    leere Liste die richtige Antwort: Die Anwendung läuft weiter, es sind die
    Operationen, die verschwinden (§36).
    """
    rows: list[tuple[str, TranslatableText | None, tuple[str, ...], tuple[tuple[str, Any], ...]]]
    rows = [(name, None, (measure,), ()) for name, measure in EDGE_OPERATIONS]
    rows.extend(EDGE_VARIANTS)
    actions: list[FeatureAction] = []
    for name, title, measures, extra in rows:
        if not REGISTRY.has(name):
            continue
        spec = REGISTRY.get(name)
        schema = {item.name: item for item in spec.params.spec()}
        if any(measure not in schema for measure in measures):
            continue
        # Die Grundzeile führt hinter ihrem Maß, was EDGE_SHAPE_FIELDS nennt;
        # eine Variante bringt ihre Felder selbst mit.
        shape_fields = EDGE_SHAPE_FIELDS.get(name, ()) if title is None else ()
        names = (*measures, *shape_fields)
        actions.append(
            FeatureAction(
                title=title if title is not None else spec.title,
                op=name,
                note=spec.doc,
                fields=tuple(_edge_field(schema[item]) for item in names if item in schema),
                fixed=(*extra, ("edges", "named"), ("edge_keys", key)),
            )
        )
    return actions


def _edge_field(entry: Any) -> ActionField:
    """Ein Feld einer Kantenzeile — Vorgabe, Grenzen und Bedingung aus dem Register."""
    return ActionField(
        name=entry.name,
        label=entry.title,
        unit=entry.unit or "",
        value=entry.default,
        kind=_kind_of(entry),
        minimum=entry.minimum,
        maximum=entry.maximum,
        choices=tuple((choice, choice) for choice in (entry.choices or ())),
        depends_on=entry.depends_on,
    )


# --- Sichtflächen (§22.3, RM-080) ----------------------------------------------


@dataclass(frozen=True, slots=True)
class Protection:
    """Ob sich dieses Merkmal als Sichtfläche sperren lässt — und wie das heißt.

    Die Sperre ist keine Operation: Sie schreibt nichts in den Verlauf,
    sondern sagt der Trennebenensuche von *Automatisch teilen*, wo keine Naht
    hin darf. Das Panel zeigt sie als Umschalter, und was auf dem Umschalter
    steht, kommt von hier — aus demselben Grund wie die Handlungen darüber:
    „Eine Naht meidet, was Dreiecke hat" ist eine Aussage über Geometrie.
    """

    possible: bool
    title: TranslatableText | str
    explanation: TranslatableText | str


def protection_of(feature: Feature) -> Protection:
    """Was der Umschalter *Vor Trennnähten schützen* an diesem Merkmal sagt.

    Sperren lässt sich, was Dreiecke trägt: Die Suche vergleicht Ebenen gegen
    die Punkte der Fläche (:func:`app.core.geom.autosplit.cuts_through`), und
    ein Merkmal ohne Dreiecke — eine Kante aus dem exakten Kern, ein
    erzeugtes Merkmal, das die Erkennung nicht wiedergefunden hat — hat
    nichts, woran eine Ebene scheitern könnte. Der Umschalter fehlt dann
    nicht still: Er steht mit dem Satz da, warum er nichts täte.
    """
    if not feature.face_indices:
        return Protection(
            False,
            _("Vor Trennnähten schützen"),
            _(
                "Dieses Merkmal trägt keine Fläche, an der eine Trennebene scheitern "
                "könnte — geschützt wird, was Dreiecke hat."
            ),
        )
    return Protection(
        True,
        _("Vor Trennnähten schützen"),
        _(
            "„Automatisch teilen“ legt keine Naht durch diese Stelle. Die Sperre wird "
            "mit dem Projekt gespeichert; das Bild zeigt sie schraffiert."
        ),
    )
