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
    # **Und er trennt „nie" von „noch nicht".** Eine Verrundung zu versetzen ist
    # sinnlos — die Kante bliebe scharf zurück. Ihren Radius zu ändern oder sie
    # ganz wegzunehmen ist dagegen sinnvoll und nur nicht gebaut. Beides mit
    # demselben Satz zu beantworten hieße, dem Kunden ein Nein zu geben, wo ein
    # Noch-nicht steht (Bitte 3d-druck-d4, 03.09.2026).
    ("fillet", "resize_feature"): _(
        "Den Radius einer Verrundung zu ändern ist sinnvoll und noch nicht "
        "gebaut. Bis dahin hilft nur, die Kante neu zu verrunden."
    ),
    ("fillet", "remove_feature"): _(
        "Eine Verrundung wegzunehmen heißt, die Kante wieder scharf zu machen — "
        "sinnvoll und noch nicht gebaut."
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
NOT_APPLICABLE: Final[dict[str, TranslatableText]] = {
    "face": _(
        "Eine Fläche gehört zur Oberfläche des Körpers und lässt sich nicht "
        "einzeln versetzen. Mit „Fläche verschieben“ wird sie hinein- oder "
        "herausgezogen."
    ),
    "fillet": _(
        "Eine Verrundung gehört zu ihrer Kante. Versetzt man sie allein, bliebe "
        "die Kante scharf und die Rundung läge daneben."
    ),
    "edge_loop": _(
        "Eine offene Kantenschleife ist ein Loch im Netz und kein Körper. Sie "
        "lässt sich reparieren, aber nicht versetzen."
    ),
    "torus": _(
        "Eine einzelne Ringfläche lässt sich nicht direkt ändern. "
        "Für eine andere Lage bewegen Sie den ganzen Körper. "
        "Für eine neue Rille oder einen Wulst können Sie einen Ring als Werkzeug verwenden."
    ),
}

_UNKNOWN_KIND: Final = _("Für diese Art von Merkmal gibt es noch keine Handlung.")

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
}


def feature_value_source(field: str) -> FeatureValueSource | None:
    """Die gemessene Kennzahl hinter einem Handlungsfeld.

    Die Gruppenauskunft liest damit dieselbe Zuordnung wie das Panel. Ein
    Index kennzeichnet eine Komponente der Position; ohne Index ist es ein
    skalares Maß des Merkmals.
    """
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
    """``length``, ``angle``, ``bool`` oder ``choice`` — davon hängt ab, welches
    Eingabefeld die Oberfläche baut. Ein Längenfeld rechnet Zoll zurück, ein
    Winkelfeld nicht."""
    minimum: float | None = None
    maximum: float | None = None
    choices: tuple[tuple[str, TranslatableText | str], ...] = ()


@dataclass(frozen=True, slots=True)
class FeatureAction:
    """Eine Handlung am Merkmal — oder der Grund, warum es sie nicht gibt."""

    title: TranslatableText | str
    op: str | None
    reason: TranslatableText | str = ""
    note: TranslatableText | str = ""
    fields: tuple[ActionField, ...] = field(default_factory=tuple)


def _kind_of(spec: Any) -> str:
    """Welche Art Eingabefeld dieser Parameter braucht."""
    if spec.kind == "bool":
        return "bool"
    if spec.kind == "enum":
        return "choice"
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
_SHIFTED_BY: Final[dict[tuple[str, str], str]] = {("duplicate_feature", "x"): "diameter"}


def _value_of(spec: Any, feature: Feature, op: str = "") -> float | bool | str:
    """Der heutige Wert dieses Parameters am Merkmal — sonst seine Vorgabe."""
    reads = _FROM_FEATURE.get(spec.name)
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


def _fields_of(spec: Any, feature: Feature) -> tuple[ActionField, ...]:
    """Die Felder einer Operation — ohne die Merkmalskennung.

    ``at_feature`` steht nicht dabei: Das Panel weiß, welches Merkmal gewählt
    ist, und ein Feld dafür wäre eine Frage, deren Antwort schon dasteht.
    """
    return tuple(
        ActionField(
            name=entry.name,
            label=entry.title,
            unit=str(entry.unit or ""),
            value=_value_of(entry, feature, spec.name),
            kind=_kind_of(entry),
            minimum=entry.minimum,
            maximum=entry.maximum,
            choices=tuple((choice, choice) for choice in entry.choices),
        )
        for entry in spec.params.spec()
        # Die freie Oberflächenrichtung gehört zum Platzierungsdialog.
        # Die Schnellbearbeitung verschiebt das gewählte Merkmal mit seiner
        # bisherigen Richtung; eine Änderung erfolgt über die eigene Drehzeile.
        if entry.kind != "feature" and entry.name not in {"nx", "ny", "nz"}
    )


def actions_for(
    feature: Feature,
    features: Mapping[FeatureId, Feature] | None = None,
    *,
    mesh: MeshData | None = None,
    cavity: tuple[Feature, ...] | None = None,
) -> list[FeatureAction]:
    """Was sich an diesem Merkmal tun lässt — und was nicht, mit Grund.

    Gilt eine Handlung, trägt sie den Registernamen und ihre Felder samt
    heutigem Wert. Gilt sie nicht, steht sie **trotzdem** in der Liste, mit
    ``op=None`` und einem Satz: Ein Panel, das bei einer Verrundung nur den
    Radius zeigt, lässt den Kunden raten, ob der Rest fehlt oder vergessen
    wurde. Mit ``mesh`` folgt der Hinweis aufs gemeinsame Versetzen der echten
    Randringkette; ohne bleibt die bisherige Paar-Auskunft für ältere Aufrufer.
    """
    actions: list[FeatureAction] = []
    for candidates in ACTION_ORDER:
        known = [spec for spec in map(_spec_or_none, candidates) if spec is not None]
        if not known:
            # Eine Zeile, deren Operationen es (noch) nicht gibt, ist kein Fehler
            # des Panels — sie fehlt, und die Oberfläche bietet sie nicht an.
            continue
        fitting = next((spec for spec in known if feature.kind in spec.applies_to), None)
        if fitting is not None:
            actions.append(
                FeatureAction(
                    title=fitting.title,
                    op=fitting.name,
                    note=_note_for(fitting.name, feature, features, mesh=mesh, cavity=cavity),
                    fields=_fields_of(fitting, feature),
                )
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
    return _("Verknüpft: Bohrung und Senkung werden gemeinsam verschoben.")


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
    try:
        return REGISTRY.get(name)
    except Exception:
        return None
