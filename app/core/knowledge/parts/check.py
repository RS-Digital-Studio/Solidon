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

from collections.abc import Iterable
from dataclasses import replace

from app.core.knowledge.parts.registry import (
    LIBRARY_VERSION,
    PARTS,
    PartRegistry,
    changed_since_library,
    used_parts,
)
from app.core.knowledge.parts.user import FINGERPRINT_KEY, fingerprint, travelling_parts
from app.core.log import get_logger
from app.core.registry import Registry
from app.core.types import Document, DocumentState, Finding, Operation
from app.i18n import _

_log = get_logger(__name__)


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
                values={"parts": ", ".join(travelled)},
            )
        )

    # „Lokal schlägt mitgereist" hat eine sichtbare Seite: Rechnet das
    # Projekt mit dem lokalen Stand, steht der mitgereiste als eigener
    # Eintrag daneben — sonst sucht der Kunde, warum sein Ergebnis anders
    # aussieht als beim Absender.
    shadowed = tuple(
        name
        for name in sorted(set(used))
        if source.has(f"{name}_travelled") and source.get(f"{name}_travelled").source == "travelled"
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
                values={"parts": ", ".join(shadowed)},
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
                values={"parts": ", ".join(scripted)},
            )
        )

    own_changed = changed_own_parts(document, used, source)
    if own_changed:
        findings.append(
            Finding(
                code="parts.own_changed",
                severity="info",
                message=_("Seit dem Speichern haben sich eigene Bausteine geändert."),
                values={"parts": ", ".join(own_changed)},
            )
        )

    changed = changed_since_library(document.parts_version, used, source)
    if changed:
        findings.append(
            Finding(
                code="parts.changed",
                severity="info",
                message=_("Seit dem Speichern haben sich benutzte Bausteine geändert."),
                values={
                    "parts": ", ".join(changed),
                    "saved": document.parts_version,
                    "now": LIBRARY_VERSION,
                },
            )
        )
    if findings:
        _log.info("part check: %d findings", len(findings))
    return findings


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
