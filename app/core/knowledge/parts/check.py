"""Was gesagt werden muss, wenn ein Projekt geöffnet wird (Bauplan §24.4,
§24.5).

Die Bibliothek ist Teil der Art, wie ein Projekt gerechnet wurde. Ein
korrigierter Baustein darf ein altes Projekt darum nicht still anders
nachrechnen — Leitprinzip 4 wäre gebrochen, und niemand bemerkte es.

Also stellt das Öffnen einer Datei zwei Fragen: welche der Bausteine, die
dieses Projekt benutzt, sich seither geändert haben, und welche davon diese
Installation gar nicht hat. Das erste ist ein Hinweis mit einer Wahl, das
zweite hält die Auswertung an (§15.2).
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, replace
from typing import TYPE_CHECKING

from app.core.errors import KEEP_SAVED_PARTS, PROGRAMMING_ERRORS
from app.core.knowledge.parts.registry import (
    LIBRARY_VERSION,
    PARTS,
    PartChange,
    PartRegistry,
    _as_number,
    changed_since_library,
    used_parts,
)
from app.core.knowledge.parts.user import FINGERPRINT_KEY, fingerprint, travelling_parts
from app.core.log import get_logger
from app.core.registry import Registry
from app.core.types import Document, DocumentState, Finding, Operation, Transaction
from app.i18n import TranslatableText, _, sort_key, source_text

if TYPE_CHECKING:
    from app.core.scene.history import History

_log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class ChangedPart:
    """Ein benutzter Baustein, der sich seit dem Speichern geändert hat (§24.4).

    Die Antwort auf „was ist anders?" für den Öffnen-Dialog: welche Einträge
    des Änderungsverlaufs seit dem gespeicherten Bibliotheksstand dazukamen,
    und ob der frühere Stand noch zu haben ist.

    **Er ist es heute für keinen mitgelieferten Baustein.** §24.4 sagt: „Der
    alte Stand bleibt aufrufbar, solange die Bibliothek ihn führt; wird er
    entfernt, verhält sich das wie eine Migration" — und die Bibliothek führt
    je Baustein genau eine Umsetzung, die heutige. ``earlier_available`` ist
    deshalb ``False``, und der Dialog erklärt die Änderung als Migration,
    statt eine Wahl anzubieten, die nichts auswählen könnte. Wer einen alten
    Stand aufrufbar machen will, hält seine Umsetzung im Register und setzt
    das Feld hier.
    """

    name: str
    saved: str
    now: str
    changes: tuple[PartChange, ...]
    earlier_available: bool = False


def changed_parts(
    document: Document, registry: PartRegistry | None = None
) -> tuple[ChangedPart, ...]:
    """Die benutzten Bausteine mit Änderungen seit dem gespeicherten Stand, samt Verlauf."""
    source = registry or PARTS
    saved = document.parts_version
    since = int(saved) if saved.isdecimal() else 0
    found: list[ChangedPart] = []
    for name in changed_since_library(saved, used_parts(document.ops), source):
        spec = source.get(name)
        changes = tuple(
            change
            for change in spec.changes
            if change.version.isdecimal() and int(change.version) > since
        )
        found.append(ChangedPart(name=name, saved=saved, now=spec.version, changes=changes))
    return tuple(found)


def normalise_legacy_placement(
    document: Document,
    registry: PartRegistry | None = None,
    *,
    operations: Registry | None = None,
) -> None:
    """Erhält beim Laden die doppelte Bedeutung alter kollidierender Ortswerte.

    Erst nach Aufnahme der mitgereisten Rezepte aufrufen. Die Bibliotheksgrenze
    ist ausdrücklich: Frische Dokumente und normale Auswertungen raten keine
    alte Bedeutung. Beide Verlaufsseiten müssen denselben Namensraum tragen.
    """
    from app.core.knowledge.parts.ops import build_params, placement_fields

    if not document.parts_version.isdecimal() or int(document.parts_version) >= 16:
        return
    source = registry or PARTS

    def migrated(operation: Operation) -> Operation:
        if not operation.op.startswith("insert_"):
            return operation
        name = operation.op.removeprefix("insert_")
        if operations is not None:
            if not operations.has(operation.op):
                return operation
            schema = operations.get(operation.op).params
        else:
            if not source.has(name):
                return operation
            schema = build_params(source.get(name))
        fields = placement_fields(schema)
        defaults = {entry.name: entry.default for entry in schema.fields()}
        values = dict(operation.params)
        # Normalen hatten schon zuvor ihren kompatiblen surface_-Namensraum.
        for field in ("x", "y", "z", "axis", "angle", "at_feature"):
            public = fields[field]
            if public != field and public not in values:
                # Früher überschrieb der Ort auch die eigene Maßvorgabe.
                # Fehlende gespeicherte Werte bedeuteten deshalb z.B. x=0.
                values.setdefault(field, defaults[public])
                values[public] = values[field]
        return replace(operation, params=values) if values != operation.params else operation

    def state(current: DocumentState) -> DocumentState:
        if current.edited_ops is None:
            return current
        return replace(
            current,
            edited_ops={
                key: migrated(operation) if operation is not None else None
                for key, operation in current.edited_ops.items()
            },
        )

    document.ops = [migrated(operation) for operation in document.ops]
    document.transactions = [
        replace(
            transaction,
            changes=replace(
                transaction.changes,
                before=state(transaction.changes.before),
                after=state(transaction.changes.after),
            ),
        )
        if transaction.changes is not None
        else transaction
        for transaction in document.transactions
    ]


def check(document: Document, registry: PartRegistry | None = None) -> list[Finding]:
    """Befunde für den Prüfbericht, wenn ein Projekt hereinkommt."""
    source = registry or PARTS
    used = used_parts(document.ops)
    if not used:
        return []

    findings: list[Finding] = []
    missing = tuple(name for name in used if not source.has(name))
    if missing:
        findings.append(
            Finding(
                code="parts.missing",
                severity="error",
                message=_("Dieses Projekt benutzt Bausteine, die es hier nicht gibt."),
                values={"parts": ", ".join(missing)},
            )
        )

    travelled = tuple(
        name
        for name in sorted(set(used))
        if source.has(name) and source.get(name).source == "travelled"
    )
    if travelled:
        findings.append(
            Finding(
                code="parts.travelled",
                severity="info",
                message=_(
                    "Bausteine sind mit dieser Datei mitgereist und stehen im "
                    "Katalog. Sie bleiben bei der Datei und werden nicht auf "
                    "diesem Rechner abgelegt."
                ),
                values={"parts": _titles(travelled, source)},
            )
        )

    # „Lokal schlägt mitgereist" hat eine sichtbare Seite: Rechnet das
    # Projekt mit dem lokalen Stand, steht der mitgereiste als eigener
    # Eintrag daneben — sonst sucht der Kunde, warum sein Ergebnis anders
    # aussieht als beim Absender.
    # Hat die Datei den **gespeicherten** Stand mitgebracht, sagt es der
    # §24.4-Befund weiter unten samt der Wahl, ihn zu verwenden — eine zweite
    # Zeile über dieselben Bausteine wäre nur länger.
    kept = saved_states(document, source)
    shadowed = tuple(
        name
        for name in sorted(set(used))
        if name not in kept
        and source.has(f"{name}_travelled")
        and source.get(f"{name}_travelled").source == "travelled"
    )
    if shadowed:
        findings.append(
            Finding(
                code="parts.travelled_shadowed",
                severity="info",
                message=_(
                    "Für Bausteine dieser Datei gilt Ihr eigener Stand — der "
                    "mitgereiste steht als eigener Eintrag im Katalog."
                ),
                values={"parts": _titles(shadowed, source)},
            )
        )

    # Regel 13 hält nur mit Regel 11 zusammen (§32): Ein Rezept durfte
    # OpenSCAD-Quelltext tragen, und dann erfuhr es der Kunde, bevor er
    # rechnen ließ — dieselbe Auskunft, die ``scene.foreign`` einer
    # Projektdatei über ihre eigenen Schritte gibt. Und dieselbe **Funktion**:
    # Sie sieht durch ein Rezept hindurch, das ein zweites einsetzt, und eine
    # eigene Fassung hier sah genau eine Ebene tief.
    from app.core.knowledge.parts.ops import op_name
    from app.core.scene.foreign import runs_foreign_source

    scripted = tuple(
        name
        for name in sorted(set(used))
        if source.has(name) and runs_foreign_source(op_name(name), source)
    )
    if scripted:
        findings.append(
            Finding(
                code="parts.scripted_recipe",
                severity="warning",
                message=_(
                    "Ein Baustein dieser Datei enthält Quelltext, der beim "
                    "Berechnen ein externes Programm ausführt. Der Quelltext "
                    "wird vor jedem Lauf geprüft."
                ),
                values={"parts": _titles(scripted, source)},
            )
        )

    # **Die Wahl aus §24.4, wo es eine gibt** (RM-138). Den gespeicherten
    # Stand eines eigenen Rezepts bringt die Projektdatei mit; er steht als
    # mitgereister Eintrag im Katalog, und ein Klick rechnet wieder mit ihm.
    # Wo er fehlt — eine eigene ``.py`` reist nie mit (Regel 13), und die
    # Bibliothek führt keine alten Stände —, ist der neue Stand eine
    # Migration: Das sagt der Satz, statt eine Wahl anzubieten, die es nicht
    # gibt.
    own_changed = changed_own_parts(document, used, source)
    available = tuple(name for name in own_changed if name in kept)
    lost = tuple(name for name in own_changed if name not in kept)
    if available:
        findings.append(
            Finding(
                code="parts.own_changed",
                severity="info",
                message=_(
                    "Eigene Bausteine wurden seit dem Speichern geändert. "
                    "Gerechnet wird mit dem neuen Stand."
                ),
                values={"parts": _titles(available, source)},
                suggestions=(KEEP_SAVED_PARTS,),
            )
        )
    if lost:
        findings.append(
            Finding(
                code="parts.own_changed",
                severity="info",
                message=_(
                    "Eigene Bausteine wurden seit dem Speichern geändert; ihr "
                    "alter Stand liegt nicht mehr vor. Prüfen Sie die Maße."
                ),
                values={"parts": _titles(lost, source)},
            )
        )

    changed = changed_since_library(document.parts_version, used, source)
    if changed:
        # Der frühere Stand ist nicht mehr zu haben (``ChangedPart``): Die
        # Meldung sagt das, statt eine Wahl zu versprechen, die es nicht gibt.
        findings.append(
            Finding(
                code="parts.changed",
                severity="info",
                message=_(
                    "Seit dem Speichern haben sich benutzte Bausteine geändert. Ihr "
                    "früherer Stand ist nicht mehr enthalten; das Projekt rechnet mit "
                    "dem aktuellen. Prüfen Sie Lage und Maße dieser Bausteine."
                ),
                values={
                    "parts": _titles(changed, source),
                    "library_saved": document.parts_version,
                    "library_now": LIBRARY_VERSION,
                },
            )
        )
        findings.extend(_changes_since(document.parts_version, changed, source))
    if findings:
        _log.info("part check: %d findings", len(findings))
    return findings


def _changes_since(saved: str, changed: Iterable[str], source: PartRegistry) -> list[Finding]:
    """Je Änderung seit dem Speichern eine Zeile: an welchen Bausteinen, und was sie
    an den Maßen ändert (§24.4, RM-138).

    Robert am 23.09.2026: Alte Bausteinstände reisen nicht mit, die
    Migrationsmeldung reicht — dann muss sie aber sagen, **was** sich geändert
    hat. „Benutzte Bausteine wurden geändert" allein schickte den Kunden auf
    die Suche an jedem Einsatz. Gezeigt wird die Maßwirkung aus dem
    Änderungsverlauf (``PartChange.effect``), nicht der Grund: Der Grund ist
    Entwicklernotiz, die Wirkung ist das, was am gedruckten Teil anders wird.

    **Eine Zeile je Wirkung, nicht je Baustein.** Dieselbe Änderung trifft oft
    mehrere Bausteine (``MATERIAL_OF_TARGET`` sechs auf einmal); sie steht
    einmal da und nennt alle. Einträge ohne Wirkung — die Erstbestückung —
    ändern kein altes Projekt und stehen nicht da.
    """
    since = _as_number(saved)
    affected: dict[str, list[str]] = {}
    effects: dict[str, TranslatableText | str] = {}
    first_version: dict[str, int] = {}
    for name in changed:
        if not source.has(name):
            continue
        for change in source.get(name).changes:
            version = _as_number(change.version)
            if version <= since or not change.effect:
                continue
            key = source_text(change.effect)
            effects.setdefault(key, change.effect)
            first_version[key] = min(first_version.get(key, version), version)
            if name not in affected.setdefault(key, []):
                affected[key].append(name)
    return [
        Finding(
            code="parts.change",
            severity="info",
            message=_(
                "Geändert an {parts}: {change}",
                parts=_titles(sorted(affected[key], key=_title_order(source)), source),
                change=effects[key],
            ),
        )
        for key in sorted(effects, key=lambda entry: (first_version[entry], entry))
    ]


def _title_order(source: PartRegistry) -> Callable[[str], str]:
    """Sortiert Bausteinkennungen nach ihrem angezeigten Titel."""
    return lambda name: sort_key(source.get(name).title) if source.has(name) else name


def _titles(names: Iterable[str], source: PartRegistry) -> str:
    """Die Bausteine, wie der Katalog sie nennt — nicht ihre Kennung.

    Im Bericht stand ``barrel_hinge, dowel, foot``: Kennungen, die in keinem
    Menü stehen (Durchsicht 0.5.0). Die Sprache des Titels ist die beim
    Öffnen, denn der Befund entsteht einmal.
    """
    return ", ".join(str(source.get(name).title) if source.has(name) else name for name in names)


def saved_states(document: Document, registry: PartRegistry | None = None) -> dict[str, str]:
    """Benutzte eigene Rezepte, deren **gespeicherter** Stand mitgekommen ist
    (§24.4, RM-138).

    Zurück kommt je Baustein im Stapel der Katalogeintrag, der genau den
    Stand trägt, mit dem das Projekt gespeichert wurde. Das Speichern legt
    je benutztem Baustein einen Abdruck ab (:func:`stamp`) und bettet das
    Rezept ein (``recipe.for_container``); beim Öffnen nimmt
    ``recipe.adopt`` es auf — unter eigenem Namen, wenn lokal ein anderer
    Stand liegt („lokal schlägt mitgereist"). Weil der Name im Abdruck steckt,
    wird der mitgereiste Eintrag unter dem Namen im Stapel verglichen.

    Leer, wo sich nichts geändert hat, der Abdruck fehlt (ältere Projekte:
    keine Aussage möglich) oder der gespeicherte Stand nicht vorliegt.
    """
    from app.core.knowledge.parts import recipe as part_recipes

    source = registry or PARTS
    travelled = [
        spec
        for spec in source.all()
        if spec.source == part_recipes.TRAVELLED_SOURCE and spec.recipe_data is not None
    ]
    found: dict[str, str] = {}
    for name in sorted(set(used_parts(document.ops))):
        saved = document.libs.get(f"{FINGERPRINT_KEY}{name}")
        now = fingerprint(name, source)
        if not saved or not now or saved == now:
            continue
        for spec in travelled:
            if spec.name == name or spec.recipe_data is None:
                continue
            try:
                arrived = part_recipes.from_data(dict(spec.recipe_data))
            except PROGRAMMING_ERRORS:
                raise
            except Exception as problem:  # Regel 17: keine Wahl statt eines Abbruchs
                _log.warning("travelled recipe %s is unreadable: %s", spec.name, problem)
                continue
            as_saved = part_recipes.fingerprint(replace(arrived, name=name))
            if as_saved[: len(saved)] == saved:
                found[name] = spec.name
                break
    return found


def keep_saved(history: History, registry: PartRegistry | None = None) -> Transaction | None:
    """Rechnet die eigenen Rezepte wieder mit dem gespeicherten Stand (RM-138).

    Eine Transaktion für alle Schritte (:meth:`History.use_part_states`);
    ``None``, wenn kein gespeicherter Stand vorliegt.
    """
    states = saved_states(history.document, registry)
    return history.use_part_states(states) if states else None


def check_outgoing(document: Document, registry: PartRegistry | None = None) -> list[Finding]:
    """Was gesagt werden muss, bevor ein Projekt **zu jemand anderem** geht
    (§24.5, Regel 13).

    **Nicht beim Speichern.** Wer an einem Projekt mit eigenem Baustein
    arbeitet, speichert es zwanzigmal am Abend; eine Meldung, die dabei
    jedes Mal erscheint, wird beim einundzwanzigsten Mal weggeklickt wie die
    zwanzig davor — auch dann, wenn sie zählt. Sie hätte dort auch nichts
    anzubieten (§2.7): Der Nutzer soll seinen eigenen Baustein benutzen, er
    tut nichts falsch.

    **Sondern beim Weggeben.** Ein eigener Baustein reist nie in einer
    Projektdatei mit — sonst führte eine hereinkommende Datei Code aus (§32).
    Der Empfänger bekommt also ein Projekt, das bei ihm **anhält** (§15.2),
    und erfährt den Grund auf einem Rechner, an den niemand mehr herankommt.
    Diese Auskunft gehört auf die Seite des Absenders, solange er noch etwas
    tun kann.
    """
    travelling = travelling_parts(dict.fromkeys(used_parts(document.ops), ""), registry)
    if not travelling:
        return []
    return [
        Finding(
            code="parts.travelling",
            severity="warning",
            message=_(
                "Dieses Projekt benutzt eigene Bausteine. Sie reisen nicht mit — "
                "bei einem anderen Empfänger hält die Auswertung an. Legen Sie die "
                "Dateien aus Ihrem Bausteinordner bei, wenn er damit rechnen soll."
            ),
            values={"parts": ", ".join(travelling)},
        )
    ]


def changed_own_parts(
    document: Document, used: Iterable[str], registry: PartRegistry | None = None
) -> tuple[str, ...]:
    """Eigene Bausteine, deren Datei sich geändert hat, seit dieses Projekt
    gespeichert wurde (§24.4, §24.5).

    Die zweite Quelle neben ``changed_since_library``: Die liest gepflegte
    Änderungsverläufe, und ein eigener Baustein hat keinen — wer an seinem
    Magnettaschen-Maß schraubt, schreibt keinen Eintrag mit Datum dazu.

    **Ein fehlender Abdruck ist kein Befund.** Projekte von vor dieser
    Änderung haben keinen, und eine Datei, die sich nicht lesen lässt, auch
    nicht. Beides heißt „keine Aussage möglich" und schweigt — ein
    Falschbefund bei jedem alten Projekt wäre schlimmer als die Lücke, die er
    schließen soll.
    """
    source = registry or PARTS
    changed: list[str] = []
    for name in sorted(set(used)):
        before = document.libs.get(f"{FINGERPRINT_KEY}{name}")
        now = fingerprint(name, source)
        if before and now and before != now:
            changed.append(name)
    return tuple(changed)


def stamp(document: Document, registry: PartRegistry | None = None) -> None:
    """Hält fest, womit gerechnet wurde — passiert beim Speichern (§16.2).

    Die Bibliotheksversion deckt die mitgelieferten Bausteine ab. Für die
    eigenen kommt je benutztem Baustein ein Abdruck seiner Datei dazu (§24.5),
    denn ihre Version bewegt sich nicht, wenn der Nutzer sie ändert.

    Abdrücke von Bausteinen, die dieses Projekt nicht mehr benutzt, fallen
    dabei weg: Ein Schlüssel, den niemand mehr liest, wird sonst mit jedem
    Speichern älter und sieht irgendwann wie eine Aussage aus.
    """
    document.parts_version = LIBRARY_VERSION
    used = set(used_parts(document.ops))
    for key in [key for key in document.libs if key.startswith(FINGERPRINT_KEY)]:
        if key[len(FINGERPRINT_KEY) :] not in used:
            del document.libs[key]
    for name in sorted(used):
        mark = fingerprint(name, registry)
        if mark:
            document.libs[f"{FINGERPRINT_KEY}{name}"] = mark
