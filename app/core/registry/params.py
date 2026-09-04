"""Parameterschemata der Operationen (Bauplan §10).

Eine Deklaration trägt Grenzen, Einheit, Vorgabe und die Vorderseiten-Zuordnung
aus §2.4, und dieselbe Definition validiert Dialog, Kommandozeile und
Agentenaufruf.

Als Dataclass deklariert, damit keine Abhängigkeit nötig ist::

    @op_params
    class ResizeHoleParams(BaseParams):
        diameter: float = param(title=_("Durchmesser"), default=5.0, unit="mm", minimum=0.1)

Parameterausdrücke ("=@width/2", §13) löst die Szene auf, bevor eine Operation
läuft; was hier ankommt, ist immer ein nackter Wert.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import MISSING, dataclass, field, fields
from typing import Any, Final

from app.core.errors import InternalError, ValidationError
from app.core.types import BaseParams, ParamKind, ParamPlacement, ParamSpec
from app.core.units import EPS_GEOM, is_greater, is_less
from app.i18n import TranslatableText, _

_METADATA_KEY = "param"

#: Der Satz hinter jedem ``name``-Parameter, den eine Operation anbietet.
#:
#: Bis zum 24.08.2026 stand er neunmal ausgeschrieben in fünf Dateien, dazu
#: einmal als ``_NAME_DOC`` in ``sketch.ops`` — und die Drift war schon
#: eingetreten: ``ingest.ops`` sagt „Leer übernimmt den Dateinamen", weil dort
#: tatsächlich der Dateiname einspringt. Das ist der richtige Text an der
#: richtigen Stelle und bleibt eigen; die übrigen neun sagten dasselbe und
#: hätten beim nächsten Nachschärfen auseinandergelaufen.
NAME_DOC: Final = _("Wie das Objekt im Baum heißt. Leer heißt: Solidon vergibt einen.")

#: Der Satz hinter jedem Maß, das null als „nimm den kalibrierten Wert" liest.
#:
#: Elf Stellen in fünf Dateien, alle wortgleich. Er ist die Erklärung von
#: Regel 7 gegenüber dem Nutzer — keine Zahlenkonstante für eine Toleranz,
#: sondern ein Verweis ins Materialprofil (``auto:<material>``). Eine Regel,
#: die an einer Stelle steht, sollte auch an einer Stelle erklärt werden.
AUTO_FROM_PROFILE_DOC: Final = _("Null heißt: Wert aus dem kalibrierten Materialprofil.")

#: Der Titel des Maßes, das zwei Flächen auf Abstand hält.
PLAY_TITLE: Final = _("Spiel")

#: Und der Titel für die Gegenrichtung: was übersteht statt Luft zu lassen.
GRIP_TITLE: Final = _("Übermaß")


def play_param(
    *,
    title: TranslatableText | str = PLAY_TITLE,
    maximum: float = 1.0,
    depends_on: tuple[str, tuple[str | bool, ...]] | None = None,
) -> Any:
    """Das Spiel einer Passung, wie es dreiundzwanzig Stellen deklarieren.

    Dreiundzwanzig Blöcke in fünf Dateien, und in ``default``, ``unit``,
    ``minimum``, ``placement`` und ``doc`` waren sie alle wortgleich —
    gemessen, nicht vermutet. Verschieden waren nur drei Dinge, und die stehen
    hier als Parameter: der Titel (*Spiel*, *Übermaß*, einmal *Betrag*), die
    Obergrenze (1,0, 1,5 oder 2,0 mm) und die Bedingung, unter der das Feld
    überhaupt wirksam wird.

    Der Grund ist derselbe wie bei :data:`AUTO_FROM_PROFILE_DOC` eine Zeile
    höher: Die Obergrenze eines Spiels ist eine fachliche Aussage, und eine
    Aussage, die an dreiundzwanzig Stellen steht, ändert man nicht an
    dreiundzwanzig Stellen — man vergisst eine.
    """
    return param(
        title=title,
        default=0.0,
        unit="mm",
        minimum=0.0,
        maximum=maximum,
        placement="advanced",
        depends_on=depends_on,
        doc=AUTO_FROM_PROFILE_DOC,
    )


_KIND_BY_ANNOTATION: dict[str, ParamKind] = {
    "float": "float",
    "int": "int",
    "bool": "bool",
    "str": "str",
}


def param(
    *,
    title: TranslatableText | str,
    default: Any = MISSING,
    kind: ParamKind | None = None,
    unit: str | None = None,
    minimum: float | None = None,
    maximum: float | None = None,
    choices: tuple[str, ...] = (),
    placement: ParamPlacement = "front",
    doc: TranslatableText | str | None = None,
    depends_on: tuple[str, tuple[str | bool, ...]] | None = None,
    required: bool | None = None,
    subtractive_on: tuple[str | bool, ...] | None = None,
    targets_feature: bool = False,
) -> Any:
    """Deklariert einen Parameter. Alles, was die Oberflächen brauchen, sitzt
    an einer Stelle.

    ``depends_on`` nennt das Feld, das diesen Parameter wirksam macht, und die
    Werte, bei denen es das tut — siehe :attr:`app.core.types.ParamSpec.depends_on`.

    ``subtractive_on`` nennt die Werte, bei denen ein Baustein abträgt statt
    aufzusetzen — siehe :attr:`app.core.types.ParamSpec.subtractive_on`.

    ``targets_feature`` markiert einen Parameter, der ein Merkmal als **Ziel**
    nennt — siehe :attr:`app.core.types.ParamSpec.targets_feature`.
    """
    metadata = {
        _METADATA_KEY: {
            "title": title,
            "kind": kind,
            "unit": unit,
            "minimum": minimum,
            "maximum": maximum,
            "choices": tuple(choices),
            "placement": placement,
            "doc": doc,
            "depends_on": depends_on,
            "required": required,
            "subtractive_on": subtractive_on,
            "targets_feature": targets_feature,
        }
    }
    if default is MISSING:
        return field(metadata=metadata)
    return field(default=default, metadata=metadata)


def _kind_of(annotation: Any, declared: ParamKind | None, choices: tuple[str, ...]) -> ParamKind:
    if declared is not None:
        return declared
    if choices:
        return "enum"
    name = annotation if isinstance(annotation, str) else getattr(annotation, "__name__", "")
    kind = _KIND_BY_ANNOTATION.get(name)
    if kind is None:
        raise InternalError(
            detail=f"parameter type {name!r} needs an explicit kind",
            values={"annotation": str(annotation)},
        )
    return kind


def op_params[P: BaseParams](cls: type[P]) -> type[P]:
    """Macht aus einer Deklaration einen eingefrorenen Parametersatz mit
    abgeleitetem Schema.

    Nur Schlüsselwörter, damit die Reihenfolge der Deklaration frei bleibt:
    Pflichtparameter dürfen auf welche mit Vorgabe folgen, und übergeben wird
    nie positionell.
    """
    data_class = dataclass(frozen=True, slots=True, kw_only=True)(cls)
    specs: list[ParamSpec] = []
    for entry in fields(data_class):  # type: ignore[arg-type]
        metadata = entry.metadata.get(_METADATA_KEY)
        if metadata is None:
            raise InternalError(
                detail=f"{cls.__name__}.{entry.name} was declared without param()",
                values={"params": cls.__name__, "field": entry.name},
            )
        choices: tuple[str, ...] = metadata["choices"]
        has_default = entry.default is not MISSING
        # **Eine Vorgabe macht ein Feld nicht optional.** Bis zum
        # 27.08.2026 hiess es hier ``required = not has_default``, und
        # das stimmte für fast alles — nicht aber für drei Operationen,
        # die ein Merkmal *brauchen* und trotzdem ``default=""`` tragen,
        # weil der Klick es einsetzt (§21.3). Der Dialog bot deshalb
        # „— keines —" als **vorausgewählte** Möglichkeit an, und beim
        # Übernehmen wurde sie abgelehnt: „Zum Färben gehört eine
        # Fläche." Robert las den Eintrag als „das ganze Teil" — die
        # naheliegendste Lesart, und keine, die irgendwo widersprochen
        # wurde. Wer eine Vorgabe hat und trotzdem Pflicht ist, sagt es
        # jetzt ausdrücklich.
        declared = metadata["required"]
        specs.append(
            ParamSpec(
                name=entry.name,
                kind=_kind_of(entry.type, metadata["kind"], choices),
                title=metadata["title"],
                default=entry.default if has_default else None,
                required=declared if declared is not None else not has_default,
                unit=metadata["unit"],
                minimum=metadata["minimum"],
                maximum=metadata["maximum"],
                choices=choices,
                placement=metadata["placement"],
                doc=metadata["doc"],
                depends_on=metadata["depends_on"],
                subtractive_on=metadata["subtractive_on"],
                targets_feature=metadata["targets_feature"],
            )
        )
    data_class.__param_spec__ = tuple(specs)  # type: ignore[attr-defined]
    return data_class


#: Arten, deren Wert im Kern eine **Zahl** ist.
#:
#: ``filament`` steht hier und nicht bei den Texten: Die Nummer eines
#: Materialslots ist im Kern eine Zahl wie zuvor, der Filamentwähler mit
#: Farbfeld und Namen ist eine Sache der Oberfläche (:data:`ParamKind`).
NUMBER_KINDS: Final[frozenset[str]] = frozenset({"float", "int", "filament"})

#: Arten, deren Wert eine **Zeichenkette** ist — Namen, Kennungen, und die
#: Sammelparameter, die ihren Inhalt als JSON-Text tragen (§30.1).
TEXT_KINDS: Final[frozenset[str]] = frozenset(
    {
        "str",
        "enum",
        "object",
        "feature",
        "part",
        # Der Name des Materials („PETG"), nicht seine Nummer — anders als
        # ``filament``, das eine Slotnummer trägt. Die zwei sehen in der
        # Oberfläche ähnlich aus und sind im Kern verschiedene Dinge.
        "material",
        "source",
        "image",
        "sketch",
        "strokes",
        "armature",
    }
)


def _coerce(spec: ParamSpec, value: Any) -> Any:
    """Prüft einen Wert gegen seinen Schemaeintrag und gibt ihn in Kernform
    zurück.

    **Die Art entscheidet, und sie muss eingeordnet sein.** Hier stand einmal
    „bool, dann float/int, alles Übrige ist Text" — und damit machte eine neue
    Art jedes Feld still zum Textfeld: ``slot`` bekam ``kind="filament"``
    (richtig, die Oberfläche soll dort den Wähler zeigen) und lehnte seitdem
    Zahlen ab. „Bei Auswahl eines Filaments kommt die Meldung Text wird
    erwartet" (Robert, 27.08.2026). Die stille Hälfte war schlimmer als die
    Meldung: Ein Feld im Textzweig hat keine Grenzen mehr, also wäre auch Slot
    99 durchgegangen.

    Wer eine neue Art einführt, trägt sie in :data:`NUMBER_KINDS` oder
    :data:`TEXT_KINDS` ein; ``test_every_parameter_kind_is_sorted_into_a_check``
    hält beide Mengen vollständig.
    """
    if spec.kind == "bool":
        if not isinstance(value, bool):
            raise ValidationError(
                field=spec.name,
                detail=_("Hier wird ja oder nein erwartet."),
                value=value,
                constraint="type",
            )
        return value

    if spec.kind in NUMBER_KINDS:
        if isinstance(value, bool) or not isinstance(value, int | float):
            raise ValidationError(
                field=spec.name,
                detail=_("Hier wird eine Zahl erwartet."),
                value=value,
                constraint="type",
            )
        if spec.kind != "float" and not float(value).is_integer():
            raise ValidationError(
                field=spec.name,
                detail=_("Hier wird eine ganze Zahl erwartet."),
                value=value,
                constraint="type",
            )
        number = float(value) if spec.kind == "float" else int(value)
        if spec.minimum is not None and is_less(float(number), spec.minimum, EPS_GEOM):
            raise ValidationError(
                field=spec.name,
                detail=_("Der Wert liegt unter dem zulässigen Mindestwert."),
                value=value,
                constraint="minimum",
                values={"minimum": spec.minimum},
            )
        if spec.maximum is not None and is_greater(float(number), spec.maximum, EPS_GEOM):
            raise ValidationError(
                field=spec.name,
                detail=_("Der Wert liegt über dem zulässigen Höchstwert."),
                value=value,
                constraint="maximum",
                values={"maximum": spec.maximum},
            )
        return number

    if spec.kind not in TEXT_KINDS:
        # Kein Rückfall auf „dann eben Text": Genau der hat dem Filamentfeld
        # seine Zahl abgelehnt und seine Grenzen genommen, ohne dass jemand es
        # merkte. Eine unbekannte Art ist ein Fehler im Programm und sagt das.
        raise InternalError(
            detail=f"parameter kind {spec.kind!r} is in neither NUMBER_KINDS nor TEXT_KINDS",
            values={"parameter": spec.name, "kind": spec.kind},
        )

    # **Ein übersetzbarer Text ist ein Text** (§4.1). Ein `TranslatableText`
    # kommt dort an, wo die Operation den Parameter als Message-ID vermerkt hat
    # (`Operation.translatable`) — er trägt seinen Übersetzungsschlüssel selbst
    # und löst sich bei der Anzeige auf. Ihn hier abzulehnen hieße, dass ein
    # mitgeliefertes Beispiel seinen Objektnamen nicht in der Sprache des Kunden
    # zeigen darf; die Prüfung darunter gilt für ihn wie für jede Zeichenkette,
    # weil `TranslatableText` sich über seine Message-ID vergleicht.
    if isinstance(value, TranslatableText):
        value = value if spec.kind != "enum" else str(value)
    if not isinstance(value, TranslatableText | str):
        raise ValidationError(
            field=spec.name,
            detail=_("Hier wird ein Text erwartet."),
            value=value,
            constraint="type",
        )
    if spec.kind == "enum" and str(value) not in spec.choices:
        raise ValidationError(
            field=spec.name,
            detail=_("Dieser Wert steht nicht zur Auswahl."),
            value=value,
            constraint="choices",
            values={"choices": list(spec.choices)},
        )
    return value


def validate[P: BaseParams](params_class: type[P], values: Mapping[str, Any]) -> P:
    """Baut einen validierten Parametersatz — oder scheitert mit einem
    korrigierbaren Fehler.
    """
    specs = params_class.spec()
    known = {spec.name for spec in specs}
    unknown = sorted(set(values) - known)
    if unknown:
        raise ValidationError(
            field=unknown[0],
            detail=_("Diesen Parameter gibt es bei dieser Operation nicht."),
            constraint="unknown",
            values={"known": sorted(known)},
        )

    arguments: dict[str, Any] = {}
    for spec in specs:
        if spec.name in values:
            arguments[spec.name] = _coerce(spec, values[spec.name])
        elif spec.required:
            raise ValidationError(
                field=spec.name,
                detail=_("Dieser Parameter fehlt."),
                constraint="required",
                # **Der Name gehört dazu, und zwar der aus dem Dialog.** Im
                # Prüfbericht stand „Dieser Parameter fehlt." und sonst nichts
                # — gemessen an „Relief auflegen" ohne Bild, wo die Auswertung
                # genau daran anhält. Welcher gemeint ist, weiß die Ausnahme
                # (``field``), nur sagte sie es nicht.
                #
                # Als Wert und nicht im Satz: Ein ``{platzhalter}`` im
                # ``detail`` bleibt stehen, wie er dasteht — der Kern
                # formatiert seine Fehlertexte nicht nach.
                values={"parameter": str(spec.title)},
            )
        else:
            arguments[spec.name] = spec.default
    return params_class(**arguments)


_JSON_TYPE: dict[ParamKind, str] = {
    "float": "number",
    "int": "integer",
    "bool": "boolean",
    "str": "string",
    "enum": "string",
    "object": "string",
    "feature": "string",
    "part": "string",
    # Ein Filament ist für den Agenten die Slotnummer, die es immer war — der
    # Wähler mit Farbe und Namen ist Bedienung und keine andere Angabe.
    "filament": "integer",
    # Ein Material ist für den Agenten die Kennung, die es immer war
    # („petg"): Der Wähler zeigt den Titel, gemeint ist der Schlüssel.
    "material": "string",
    "source": "string",
    "image": "string",
    "sketch": "string",
    "strokes": "string",
    "armature": "string",
}

#: Parameterarten, die eine unbegrenzte Zahl von Nutzergesten sammeln (Regel 2,
#: §30.1). Der Agent sieht sie nicht — er verweist auf Merkmale und benutzt
#: Maße, er erzeugt keine Koordinaten (Leitprinzip 5); `agent/session.py`
#: weist ein trotzdem mitgeschicktes Argument auch ab, wenn ein Modell es rät.
#: Beide Stellen lesen diese Menge, ebenso ``tests/test_gesture_ops.py`` — eine
#: zweite Liste wäre am Tag nach der nächsten Geste falsch.
GATHERED_KINDS: Final[frozenset[str]] = frozenset({"sketch", "strokes", "armature"})


def dependency_conditions(
    entry: ParamSpec, schema: tuple[ParamSpec, ...]
) -> tuple[tuple[str, tuple[str | bool, ...]], ...]:
    """Alle Bedingungen eines Feldes, von der direkten bis zur äußersten.

    Ein Steuerfeld kann selbst bedingt sein. Beim Schraubenloch wirkt *Spiel*
    nur mit angehaktem *Unterlegscheibe einlassen*, und dieser Haken wiederum
    nur ohne Senkkopf. Wer allein die direkte Bedingung liest, hält einen
    gespeicherten, aber gerade unwirksamen Haken fälschlich für aktiv.

    Ein Zyklus ist ein fehlerhaftes Schema; die Registerprüfung meldet ihn.
    Hier wird er zusätzlich beendet, damit Handbuch oder Dialog bei einem
    solchen Programmierfehler nicht hängen bleiben.
    """
    declared = {item.name: item for item in schema}
    conditions: list[tuple[str, tuple[str | bool, ...]]] = []
    seen = {entry.name}
    current = entry
    while current.depends_on is not None:
        controller, wanted = current.depends_on
        if controller in seen:
            break
        conditions.append((controller, wanted))
        seen.add(controller)
        parent = declared.get(controller)
        if parent is None:
            break
        current = parent
    return tuple(conditions)


def _same_dependency_value(entered: Any, wanted: str | bool) -> bool:
    """Ein Abhängigkeitswert, ohne die Gleichheit von ``bool`` und ``int``."""
    if isinstance(wanted, bool):
        return isinstance(entered, bool) and entered is wanted
    return isinstance(entered, str) and entered == wanted


def inactive_dependency(
    entry: ParamSpec, schema: tuple[ParamSpec, ...], values: Mapping[str, Any]
) -> tuple[str, tuple[str | bool, ...]] | None:
    """Die erste nicht erfüllte Bedingung eines Feldes, oder ``None``.

    Die Rückgabe nennt bewusst den wirklichen Grund. Ist *Unterlegscheibe*
    noch angehakt, aber wegen *Senkkopf* unwirksam, erklärt der Dialog den
    Senkkopf statt den sichtbar gesetzten und damit scheinbar passenden Haken.
    """
    for controller, wanted in dependency_conditions(entry, schema):
        if not any(_same_dependency_value(values.get(controller), value) for value in wanted):
            return controller, wanted
    return None


def _condition_sentence(
    controller: str,
    wanted: tuple[str | bool, ...],
    titles: Mapping[str, str],
    keys: bool,
) -> str:
    """Eine einzelne Bedingung für Mensch oder Agent formulieren."""
    name = controller if keys else titles.get(controller, controller)
    if any(isinstance(value, bool) for value in wanted):
        if all(value is True for value in wanted):
            return str(_("Gilt bei angehaktem {field}.")).format(field=name)
        return str(_("Gilt bei nicht angehaktem {field}.")).format(field=name)
    shown = ", ".join(str(value) for value in wanted)
    return str(_("Gilt bei {field} = {value}.")).format(field=name, value=shown)


def condition_text(entry: ParamSpec, schema: tuple[ParamSpec, ...], keys: bool = False) -> str:
    """Unter welcher Bedingung dieser Parameter wirkt — als Satz, oder leer.

    Für Handbuch und Agent. Der Dialog formuliert es eigenständig („Wirkt nur,
    wenn …"), weil er einen Tooltip an einem ausgegrauten Feld schreibt und die
    Auswahlwerte durch ``choice_label`` schickt — dasselbe zweimal zu sagen ist
    hier kein Drift, denn die **Quelle** ist eine: ``ParamSpec.depends_on``.

    Der Agent braucht sie so dringend wie ein Mensch: Ein Wert, den die
    Operation im anderen Zweig verwirft, ist ein Zug, der nichts tut, und die
    Prüfung danach sieht nur, dass sich nichts geändert hat.

    ``keys`` entscheidet über die **Anrede**, nicht über den Inhalt. Ein
    Handbuchleser sieht „Gilt bei Art = circular." und findet *Art* im Dialog;
    der Agent kennt kein *Art*, er setzt ``kind`` — und ein Satz, der ihm einen
    Namen nennt, den seine Werkzeugbeschreibung nicht führt, ist eine
    Zuordnung, die er raten müsste.

    Sie steht hier und nicht bei den Oberflächen, weil ``json_schema`` sie
    braucht — und ``surfaces`` importiert dieses Modul, nicht umgekehrt.
    """
    titles = {item.name: str(item.title) for item in schema}
    return " ".join(
        _condition_sentence(controller, wanted, titles, keys)
        for controller, wanted in dependency_conditions(entry, schema)
    )


def json_schema(params_class: type[BaseParams]) -> dict[str, Any]:
    """JSON-Schema für die Werkzeugbeschreibung des Agenten (§10, §26.2)."""
    properties: dict[str, Any] = {}
    required: list[str] = []
    for spec in params_class.spec():
        if spec.kind in GATHERED_KINDS:
            # §26, Leitprinzip 5: der Agent erzeugt Skizzen ausschließlich über
            # benannte Grundformen und Maße, nie über rohe Punktlisten — den
            # Skizzentext bekommt er gar nicht erst angeboten. Für Pinselstriche
            # gilt dasselbe schärfer: ein Strich *ist* eine Koordinate.
            continue
        entry: dict[str, Any] = {"type": _JSON_TYPE[spec.kind]}
        description = str(spec.doc) if spec.doc is not None else str(spec.title)
        if spec.unit:
            description = f"{description} [{spec.unit}]"
        # Wann dieser Wert überhaupt wirkt (§10). Ohne die Angabe setzte der
        # Agent einen Wert, den die Operation im anderen Zweig verwirft — ein
        # Zug, der nichts tut, und die Prüfung danach sieht nur, dass sich
        # nichts geändert hat.
        condition = condition_text(spec, params_class.spec(), keys=True)
        if condition:
            description = f"{description} {condition}"
        entry["description"] = description
        if spec.minimum is not None:
            entry["minimum"] = spec.minimum
        if spec.maximum is not None:
            entry["maximum"] = spec.maximum
        if spec.choices:
            entry["enum"] = list(spec.choices)
        if not spec.required:
            entry["default"] = spec.default
        properties[spec.name] = entry
        if spec.required:
            required.append(spec.name)
    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }
