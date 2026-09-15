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

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Final

from app.core.registry import REGISTRY
from app.core.registry.surfaces import asked_fields, normal_fields_of
from app.core.types import Feature, FeatureId
from app.core.units import DEGREE_UNIT
from app.i18n import TranslatableText, _

if TYPE_CHECKING:
    from app.core.geom.mesh import MeshData

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
ACTION_ORDER: Final[tuple[tuple[str, ...], ...]] = (
    ("move_feature",),
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
}

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
    "face": _(
        "Eine Fläche gehört zur Oberfläche des Körpers; einzeln lässt sich an ihr "
        "nichts ändern. Was an ihr ansetzt, setzt am Körper an: „Fläche versetzen“ "
        "zieht sie hinein oder heraus, und Bohren, Beschriften und jeder Baustein "
        "brauchen sie als Unterlage."
    ),
    "curved_face": _(
        "Eine gerundete Seite ist ein Stück der Oberfläche ohne eigene Ebene — "
        "der Bogen eines D, der Mantel eines o. Versetzen, Bohren und Zeichnen "
        "brauchen eine Ebene; was an ihr geht, ist das Filament: „Filament auf "
        "eine Fläche“ färbt sie, „Filament entfernen“ nimmt es wieder."
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
    "torus": _(
        "Eine einzelne Ringfläche hat nichts, woran sich einzeln etwas ändern "
        "ließe — sie gehört zu der Rille oder dem Wulst, aus dem sie entstanden "
        "ist. Für eine andere Lage bewegen Sie den ganzen Körper; für eine neue "
        "Rille oder einen Wulst nehmen Sie einen Ring als Werkzeug."
    ),
    # **Das Langloch stand hier bis zum 11.09.2026** — „die Handlungen hier
    # rechnen mit einem Durchmesser und träfen seine Flanken nicht". Sie tun es
    # nicht mehr: Sein Werkzeugkörper wird aufgezogen wie beim Schneiden, und
    # Versetzen, Drehen, Verdoppeln und Entfernen gelten ihm wie einer
    # Bohrung (RM-153). Der Satz ist gefallen, nicht verschoben.
    # **Der Fallback stand hier bis zum 10.09.2026**, und er sagte nichts:
    # „Für diese Art von Merkmal gibt es noch keine Handlung." Ein Ende ohne
    # Weg nach vorn ist genau das, was Regel 17 verbietet — und einen Weg gibt
    # es: Ein Gewinde entsteht in einem Baustein (§24.1), und dessen Schritt
    # steht in ``Feature.created_by``. Nur ein **erkanntes** Gewinde, das aus
    # einer fremden Datei kommt, hat keinen; für das nennt der Satz den
    # zweiten Weg.
    "thread": _(
        "Ein Gewinde ist eine Wendelfläche und trägt kein einzelnes Maß, das "
        "sich ändern ließe. Stammt es aus einem Baustein, ändern Sie es über "
        "„Diesen Schritt ändern“. In einem eingelesenen Modell hilft „Bohrung "
        "verschließen“ ohne gewähltes Merkmal, mit Lage und Durchmesser von "
        "Hand — danach setzen Sie ein neues Gewinde."
    ),
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
    "depth": ("depth", None),
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
    skalares Maß des Merkmals.
    """
    if field == "diameter" and feature is not None and feature.kind == "fillet":
        return ("radius", None)
    return _FROM_FEATURE.get(field)


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


@dataclass(frozen=True, slots=True)
class FeatureAction:
    """Eine Handlung am Merkmal — oder der Grund, warum es sie nicht gibt."""

    title: TranslatableText | str
    op: str | None
    reason: TranslatableText | str = ""
    note: TranslatableText | str = ""
    fields: tuple[ActionField, ...] = field(default_factory=tuple)
    step: int | None = None
    """Die Schrittkennung, wenn die Handlung einem **Baustein** gilt.

    Dann startet die Oberfläche keine neue Operation, sondern ändert den
    Schritt, der das Merkmal erzeugt hat (:func:`part_actions`). Bei allen
    anderen Handlungen bleibt es ``None``, und ``op`` sagt, was zu starten
    ist."""
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
    shift = _SHIFTED_BY.get((op, spec.name))
    beside = float(feature.params.get(shift, 0.0)) if shift else 0.0
    if index is None:
        return float(measured) + beside
    try:
        return float(measured[index]) + beside
    except IndexError, TypeError:
        return spec.default  # type: ignore[no-any-return]


def _action_field(entry: Any, feature: Feature, op: str) -> ActionField:
    """Ein gemessenes Maß samt Rückübersetzung in den gespeicherten Parameter."""
    radius = entry.name == "diameter" and feature.kind == "fillet"
    factor = 2.0 if radius else 1.0
    return ActionField(
        name=entry.name,
        label=_("Radius") if radius else entry.title,
        unit=str(entry.unit or ""),
        value=_value_of(entry, feature, op),
        kind=_kind_of(entry),
        minimum=entry.minimum / factor if entry.minimum is not None else None,
        maximum=entry.maximum / factor if entry.maximum is not None else None,
        choices=tuple((choice, choice) for choice in entry.choices),
        parameter_factor=factor,
    )


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
) -> list[FeatureAction]:
    """Was sich an diesem Merkmal tun lässt — und was nicht, mit Grund.

    Gilt eine Handlung, trägt sie den Registernamen und ihre Felder samt
    heutigem Wert. Gilt sie nicht, steht sie **trotzdem** in der Liste, mit
    ``op=None`` und einem Satz: Ein Panel, das bei einer Verrundung nur den
    Radius zeigt, lässt den Kunden raten, ob der Rest fehlt oder vergessen
    wurde. Mit ``mesh`` folgt der Hinweis aufs gemeinsame Versetzen der echten
    Randringkette; ohne bleibt die bisherige Paar-Auskunft für ältere Aufrufer.

    ``cavity`` und ``touches_other`` sagen, ob das Merkmal seinen Hohlraum mit
    anderen teilt (``relations.cavity_chain_state_at``). Dann tragen die
    Handlungen, die daran scheitern würden, ``op=None`` und den Satz, den die
    Operation beim Rechnen sagt — gemessen am 14.09.2026 an
    ``plate_countersunk.stl``: *Drehen* und *Verdoppeln* an der Senkung und
    *Zum Langloch ziehen* an der gesenkten Bohrung öffneten eine Vorschau ohne
    Bild und hielten beim Übernehmen die Kette an.
    """
    actions: list[FeatureAction] = []
    edge_blocked = fillet_blocked(feature, features, mesh)
    piece_blocked = cone_piece_blocked(feature)
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

        chain, touches_other = cavity_chain_state_at(feature, features, mesh)
        cavity = chain if chain is not None else ()
    own_body_blocked = no_own_body(feature, cavity, touches_other, mesh)
    for candidates in ACTION_ORDER:
        known = [spec for spec in map(_spec_or_none, candidates) if spec is not None]
        if not known:
            # Eine Zeile, deren Operationen es (noch) nicht gibt, ist kein Fehler
            # des Panels — sie fehlt, und die Oberfläche bietet sie nicht an.
            continue
        fitting = next((spec for spec in known if feature.kind in spec.applies_to), None)
        if fitting is not None and piece_blocked is not None:
            actions.append(FeatureAction(title=fitting.title, op=None, reason=piece_blocked))
        elif (
            fitting is not None
            and own_body_blocked is not None
            and fitting.name in _NEED_AN_OWN_BODY
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
        elif fitting is not None and (
            shared := _shares_its_cavity(
                fitting.name,
                feature,
                features,
                mesh=mesh,
                cavity=cavity,
                touches_other=touches_other,
            )
        ):
            actions.append(FeatureAction(title=fitting.title, op=None, reason=shared))
        elif fitting is not None:
            actions.append(
                FeatureAction(
                    title=fitting.title,
                    op=fitting.name,
                    note=_note_for(fitting.name, feature, features, mesh=mesh, cavity=cavity),
                    fields=_fields_of(fitting, feature),
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
    return actions


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
) -> TranslatableText | None:
    """Warum Versetzen, Verdoppeln, Drehen, Entfernen und Ändern an diesem
    Merkmal absagen würden — oder ``None``.

    Zwei Gründe, beide aus der Operation und mit ihrem Satz:

    * Eine Bohrung oder Senkung, die einen **fremden Rand berührt, ohne dass
      daraus eine eindeutige Kette wird** (``cavity_chain_state_at`` liefert
      keine Kette und ``touches_other``): Aus ihren Flächen entsteht kein
      Werkzeug, und mitnehmen lässt sich nichts, was nicht benannt ist
      (``NO_OWN_BODY``).
    * Ein Kegel oder eine Kuppel, aus deren Flächen **kein Körper** entsteht
      — der Rand hat zu viele Ringe oder liegt in keiner Ebene
      (``prepare_ops.has_own_body``, ``NO_BODY_FROM_FACES``): ein Kegelstumpf
      mit einer Querbohrung durch den Mantel, an einem Uhrenteil fünfmal nach
      dem Klick (15.09.2026). Nur mit Netz, denn die Ringe stehen im Netz.
    """
    if feature.kind not in ("hole", "cone", "sphere") or cavity:
        return None
    if touches_other and feature.kind != "sphere":
        from app.core.geom.prepare_ops import NO_OWN_BODY

        return NO_OWN_BODY
    if feature.kind == "hole" or mesh is None or not feature.face_indices:
        return None
    from app.core.geom.prepare_ops import NO_BODY_FROM_FACES, has_own_body

    if has_own_body(mesh, feature, alone=not touches_other):
        return None
    return NO_BODY_FROM_FACES


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
    stellt keine Zeile grau.
    """
    if feature.kind != "fillet":
        return None
    if feature.params.get("radial", False):
        return WALL_BLENDS_INTO_ITS_NEIGHBOURS if feature.params.get("tangent") else None
    if mesh is None or features is None or not feature.face_indices:
        return None
    axis = feature.params.get("axis")
    if not isinstance(axis, list | tuple) or len(axis) != 3:
        return None
    from app.core.geom.edges import NOT_BETWEEN_TWO_PLANES
    from app.core.perceive.features import face_mask, replaces_an_edge

    planar = face_mask(mesh, [entry for entry in features.values() if entry.kind == "face"])
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

        shared = cavity_is_shared(*cavity_chain_state_at(feature, features, mesh))
    else:
        shared = bool(cavity)
    if not shared:
        return None
    from app.core.geom.prepare_ops import NEEDS_A_PLAIN_BORE

    return NEEDS_A_PLAIN_BORE


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

    def taken(names: tuple[str, ...]) -> tuple[ActionField, ...]:
        fields: list[ActionField] = []
        for name in names:
            entry = schema.get(name)
            if entry is None:
                continue
            value = values.get(name, entry.default)
            fields.append(
                ActionField(
                    name=name,
                    label=entry.title,
                    unit=entry.unit,
                    value=value,
                    kind=_kind_of(entry),
                    minimum=entry.minimum,
                    maximum=entry.maximum,
                    choices=tuple((choice, choice) for choice in (entry.choices or ())),
                )
            )
        return tuple(fields)

    measures = tuple(
        name
        for name, entry in schema.items()
        if entry.placement == "front" and name not in placement_params
    )
    placement = tuple(name for name in ("x", "y", "z") if name in schema)

    actions: list[FeatureAction] = []
    if measures:
        actions.append(
            FeatureAction(
                title=_("Maße ändern"),
                op=spec.name,
                step=operation.id,
                note=_("Ändert den Schritt, der diesen Baustein gesetzt hat."),
                fields=taken(measures),
            )
        )
    if placement:
        actions.append(
            FeatureAction(
                title=_("Baustein verschieben"),
                op=spec.name,
                step=operation.id,
                fields=taken(placement),
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
#: ``named`` für einzeln gewählte Kanten (``brep.edit.EDGE_CHOICES``). Wer
#: eine Kante anklickt, hat ``named`` bereits beantwortet — einzugeben bleibt
#: das eine Maß, das die Zeile führt.
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


def edge_actions(key: str) -> list[FeatureAction]:
    """Was sich an dieser einen Kante tun lässt — verrunden und fasen.

    Bis zum Anklicken einer Kante gab es beides nur über den Dialog und eine
    Liste darin: „Senkrecht · 20 mm · x -20,0, y -15,0", zum Ankreuzen. Wer
    **diese eine Ecke** brechen wollte, musste sie in einer Aufzählung
    wiedererkennen.

    Jede Zeile trägt genau ein Feld — den Radius beziehungsweise die Breite
    —, und die übrigen Werte bringt sie als :attr:`FeatureAction.fixed` mit:
    ``edges="named"`` und den Schlüssel. Die Vorgabe ist die des Registers und
    nicht ein Maß der Kante: Anders als bei einer Bohrung gibt es hier keinen
    **gemessenen** Wert, den man übernehmen könnte — eine scharfe Kante hat
    keinen Radius, und der gewünschte ist der einzige, der zählt.

    Ohne den exakten Kern steht keine der beiden im Register, und dann ist die
    leere Liste die richtige Antwort: Die Anwendung läuft weiter, es sind die
    Operationen, die verschwinden (§36).
    """
    actions: list[FeatureAction] = []
    for name, measure in EDGE_OPERATIONS:
        if not REGISTRY.has(name):
            continue
        spec = REGISTRY.get(name)
        entry = next((item for item in spec.params.spec() if item.name == measure), None)
        if entry is None:
            continue
        actions.append(
            FeatureAction(
                title=spec.title,
                op=name,
                note=spec.doc,
                fields=(
                    ActionField(
                        name=entry.name,
                        label=entry.title,
                        unit=entry.unit or "",
                        value=entry.default,
                        kind=_kind_of(entry),
                        minimum=entry.minimum,
                        maximum=entry.maximum,
                    ),
                ),
                fixed=(("edges", "named"), ("edge_keys", key)),
            )
        )
    return actions


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
