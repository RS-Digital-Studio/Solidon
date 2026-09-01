"""Die Formatprüfung lokal weitergegebener Bausteindateien.

**Sie prüft nicht auf Verbotenes, sondern auf Erlaubtes.** Eine Sperrliste
(„kein ``import``, kein ``eval``") muss vollständig sein, um zu wirken, und
niemand kann sie vollständig halten. Eine Erlaubnisliste ist abgeschlossen:
Was hier nicht steht, kommt nicht durch.

Die Prüfung läuft vor dem Speichern und nach dem Einlesen. So entsteht keine
Datei, die der Empfänger anschließend nicht in seinen Projektkatalog aufnehmen
kann. :func:`rules` stellt die Erlaubnisliste als gewöhnliches Wörterbuch für
beide Richtungen bereit.

**Die Liste der Operationsnamen kommt aus dem Register**, nicht aus einer
Aufzählung: Ein von Hand geführtes Verzeichnis wäre beim nächsten Zuwachs
falsch und würde gültige Rezepte der Anwendung ablehnen.
"""

from __future__ import annotations

import base64
import dataclasses
import json
import re
from pathlib import Path
from typing import Any, Final

from app.core.knowledge.parts.recipe import (
    FORMAT_VERSION,
    IMPORTED_SOURCE,
    RECIPE_LICENSES,
    Recipe,
    adopt,
)
from app.core.knowledge.parts.registry import GROUPS, NAME_PATTERN, PartRegistry
from app.core.registry import REGISTRY, Registry

#: Wie groß eine weitergegebene Datei höchstens sein darf.
#:
#: Payloads reisen base64-kodiert im JSON und wachsen dabei um ein Drittel; ein
#: 5-MB-Netz wird zu knapp 7 MB Datei. Fünfundzwanzig Megabyte fassen damit
#: auch einen Baustein aus einem eingelesenen Modell. Die Anwendung prüft die
#: Grenze, bevor sie eine Datei schreibt oder einliest.
MAX_FILE_BYTES: Final = 25 * 1024 * 1024

#: Wie lang Titel und Beschreibung höchstens werden (Konzept §3.2).
#:
#: Unnötig lange Texte und eingebettete Links blähen eine Bausteindatei auf.
#: Beides ist hier begrenzt.
MAX_TITLE_CHARS: Final = 120
MAX_DOC_CHARS: Final = 2000

#: Was in einem freien Text nichts zu suchen hat.
#:
#: Kein Wächter gegen einen entschlossenen Angreifer — die Texte werden ohnehin
#: maskiert ausgegeben. Aber Werbung braucht einen anklickbaren Link, und ohne
#: ihn lohnt sie sich nicht.
FORBIDDEN_TEXT: Final = re.compile(r"https?://|www\.|<[a-zA-Z/!]", re.IGNORECASE)

#: Dasselbe **ohne** die Link-Hälfte — für das Autorenfeld.
#:
#: Ein Autor darf sagen, wo man ihn findet; ``Recipe.author`` ist ausdrücklich
#: „ein Name, ein Kürzel, eine Adresse". Eine Auszeichnung darf er trotzdem
#: nicht einschleusen: Was für Titel und Erklärtext gilt, gilt für einen Namen
#: genauso. Zwei Muster, weil die
#: zwei Felder zwei verschiedene Fragen beantworten — ein gemeinsames hätte
#: entweder die Adresse verboten oder das ``<`` durchgelassen.
FORBIDDEN_MARKUP: Final = re.compile(r"<[a-zA-Z/!]")

#: Welche Werte in einem Parameter stehen dürfen.
#:
#: Zahl, Zeichenkette, Wahrheitswert — und Listen davon. Ein Wörterbuch ist
#: ausdrücklich nicht dabei: Es ist die Form, in der sich verschachtelte
#: Strukturen einschmuggeln lassen, und kein Parameter braucht eine.
VALUE_KINDS: Final = ("number", "string", "boolean", "list")


@dataclasses.dataclass(frozen=True, slots=True)
class Finding:
    """Ein Befund als Schlüssel und Werte, nicht als fertiger Satz.

    **Der Satz entsteht am Anzeigeort, das Urteil hier.** Deshalb trägt ein
    Befund **beides**: den Schlüssel für die Übersetzung und die Werte, die zu
    ihm geführt haben.

    ``str()`` gibt den deutschen Satz — für Protokoll, Fehlermeldung und
    Testausgabe. Wer übersetzt ausgeben will, nimmt ``code`` und ``values``.
    """

    code: str
    values: dict[str, Any] = dataclasses.field(default_factory=dict)

    def text(self) -> str:
        """Der Satz in der eingestellten Sprache, mit gefüllten Platzhaltern."""
        from app.core.knowledge.parts.shared_texts import CHECKS

        pattern = CHECKS.get(self.code)
        if pattern is None:
            # Kein stiller Rückfall auf leer: Ein Befund ohne Satz ist ein
            # Programmfehler, und der Schlüssel sagt wenigstens, welcher.
            return self.code
        sentence = str(pattern)
        for name, value in self.values.items():
            sentence = sentence.replace("{" + name + "}", str(value))
        return sentence

    def __str__(self) -> str:
        return self.text()


def rules() -> dict[str, Any]:
    """Die Erlaubnisliste als Daten — eine Quelle für beide Dateirichtungen.

    Alles darin ist **abgeleitet**: die Rezeptschlüssel aus der Dataclass, die
    Operationsnamen aus dem Register, die Formatversion aus dem Modul, das sie
    schreibt. Wer eine Operation hinzufügt, ändert diese Liste, ohne sie
    anzufassen — und wer ein Feld an ``Recipe`` hängt, ebenso.
    """
    return {
        "format": 1,
        "recipe_format_versions": [FORMAT_VERSION],
        "recipe_keys": sorted(field.name for field in dataclasses.fields(Recipe)),
        "operations": sorted(entry.name for entry in REGISTRY.all()),
        "max_file_bytes": MAX_FILE_BYTES,
        "max_title_chars": MAX_TITLE_CHARS,
        "max_doc_chars": MAX_DOC_CHARS,
        "value_kinds": list(VALUE_KINDS),
        # Die Wertemenge gehört dem Rezept-Kern: Ein Feld an ``Recipe`` mit
        # festen zulässigen Werten ist seine Sache. Eine zweite Liste im
        # Dateiprüfer würde beim nächsten Zuwachs auseinanderlaufen.
        "licenses": list(RECIPE_LICENSES),
        # **Was der Empfänger braucht, um es überhaupt aufnehmen zu können.**
        # Diese drei prüft ``PartRegistry._check`` beim Einsetzen, und wer sie
        # verletzt, hat eine Datei, die die Formatprüfung besteht und beim
        # Einlesen dennoch mit „ließ sich nicht aufnehmen" scheitert. Eigene
        # Rezepte kommen aus ``capture``; fremde Dateien können von Hand oder
        # mit einem anderen Programm erstellt worden sein.
        "name_pattern": NAME_PATTERN.pattern,
        "groups": sorted(GROUPS),
        "needs_features": True,
        # Welche Felder ein Rezept haben **muss** — abgeleitet aus der
        # Dataclass: Ein Feld ohne Vorgabewert ist eines, ohne das sich das
        # Rezept nicht bauen lässt. Aufgezählt wäre die Liste beim nächsten
        # Feld falsch.
        "required_keys": sorted(
            field.name
            for field in dataclasses.fields(Recipe)
            if field.default is dataclasses.MISSING and field.default_factory is dataclasses.MISSING
        ),
    }


def _value_is_allowed(value: Any, depth: int = 0) -> bool:
    """Ob ein Parameterwert eine der erlaubten Formen hat.

    ``depth`` bricht die Rekursion nach einer Ebene ab: Eine Liste von Zahlen
    ist ein Parameter, eine Liste von Listen von Listen ist eine Struktur, die
    sich jemand ausgedacht hat.
    """
    if isinstance(value, bool | int | float | str):
        return True
    if isinstance(value, list) and depth == 0:
        return all(_value_is_allowed(item, depth + 1) for item in value)
    return False


def inspect(payload: bytes, known: dict[str, Any] | None = None) -> list[Finding]:
    """Prüft eine Rezeptdatei. Eine leere Liste heißt: lokal verwendbar.

    Gibt **alle** Befunde zurück und nicht nur den ersten: Wer eine Datei
    ablehnt, sollte sagen können, was alles daran fehlt — eine Ablehnung, die
    nach jedem Berichtigen eine neue nennt, ist eine Kette ohne Ende.

    ``known`` ist die Regelliste; ohne Angabe wird :func:`rules` verwendet. Der
    Parameter hält die Prüfung gezielt testbar.
    """
    allowed = known if known is not None else rules()
    findings: list[Finding] = []

    if len(payload) > allowed["max_file_bytes"]:
        return [
            Finding(
                "file_too_large",
                {"limit": allowed["max_file_bytes"]},
            )
        ]

    try:
        data = json.loads(payload)
    except (UnicodeDecodeError, ValueError):
        findings.append(Finding("check_not_json"))
        return findings
    if not isinstance(data, dict):
        findings.append(Finding("check_not_object"))
        return findings

    unknown = sorted(set(data) - set(allowed["recipe_keys"]))
    if unknown:
        findings.append(Finding("check_unknown_keys", {"keys": ", ".join(unknown)}))

    version = data.get("format_version")
    if version not in allowed["recipe_format_versions"]:
        findings.append(
            Finding(
                "check_bad_version",
                {
                    "version": version,
                    # **Ohne Klammern und ohne Anführungszeichen.** Der Kunde
                    # liest einen Satz und keine Python-Liste; „bekannt sind
                    # [19]" erklärt ihm nichts. Das Format ist mit 50
                    # abgestimmt, weil die PHP-Seite denselben Text erzeugen
                    # muss — sonst geht ausgerechnet dieser Befund auseinander.
                    "known": ", ".join(str(one) for one in allowed["recipe_format_versions"]),
                },
            )
        )

    findings.extend(_text_findings(data, allowed))
    findings.extend(_adoptable_findings(data, allowed))
    findings.extend(_operation_findings(data, allowed))
    findings.extend(_payload_findings(data))
    return findings


def _adoptable_findings(data: dict[str, Any], allowed: dict[str, Any]) -> list[Finding]:
    """Ob der Empfänger den Baustein überhaupt aufnehmen kann.

    **Der Fund, der diese Prüfung erzwungen hat** (3a, 31.08.2026, erster
    Ende-zu-Ende-Lauf): ``export_bytes`` gab dreimal hintereinander eine saubere
    Datei aus, die ``adopt`` danach ablehnte — Name nicht ``lower_snake_case``,
    Gruppe unbekannt, kein benanntes Merkmal. Aus Kundensicht klickt jemand
    „Als Datei weitergeben", bekommt eine Datei, und der Empfänger liest beim
    Einlesen „Ein mitgereistes Rezept ließ sich nicht aufnehmen."

    Die Frage war, ob das hierhin gehört oder zum Empfänger, und sie
    entscheidet sich an dem, was diese Prüfung **ist**: die Schranke unmittelbar
    vor dem Speichern. Ein Baustein, den niemand einlesen kann, darf nicht als
    gültige Datei ausgegeben werden. Der Empfänger prüft weiter, weil er die
    Datei tatsächlich einlöst.

    **In der Anwendung kann keiner der drei Fälle entstehen**: Dort kommt jedes
    Rezept aus ``capture``, und das erzwingt alle drei. Eine eingelesene Datei
    kann dagegen von Hand oder mit einem anderen Programm erstellt worden sein.
    """
    findings: list[Finding] = []

    name = data.get("name")
    if isinstance(name, str) and not re.match(allowed["name_pattern"], name):
        findings.append(Finding("check_name_not_snake_case", {"name": name}))

    for field in allowed.get("required_keys") or []:
        if field not in data:
            findings.append(Finding("check_missing_field", {"field": field}))

    group = data.get("group")
    known = allowed.get("groups") or []
    # **Nur wenn die Gruppe da ist.** Fehlt sie ganz, ist das ein fehlendes
    # Pflichtfeld und keine unbekannte Gruppe — „die Gruppe „None" gibt es
    # nicht" wäre eine Meldung, die den Kunden auf die falsche Fährte setzt.
    if known and group is not None and group not in known:
        findings.append(Finding("check_unknown_group", {"group": group, "known": ", ".join(known)}))

    if allowed.get("needs_features") and not data.get("features"):
        findings.append(Finding("check_no_features"))

    return findings


def _text_findings(data: dict[str, Any], allowed: dict[str, Any]) -> list[Finding]:
    """Titel und Beschreibung: Länge und keine Links (Konzept §3.2)."""
    findings: list[Finding] = []
    for key, limit in (("title", allowed["max_title_chars"]), ("doc", allowed["max_doc_chars"])):
        text = data.get(key)
        if text is None:
            continue
        if not isinstance(text, str):
            findings.append(Finding("check_field_not_text", {"field": key}))
            continue
        if len(text) > limit:
            findings.append(
                Finding(
                    "check_field_too_long",
                    {"field": key, "length": len(text), "limit": limit},
                )
            )
        if FORBIDDEN_TEXT.search(text):
            findings.append(Finding("check_field_has_link", {"field": key}))
    return findings + _credit_findings(data, allowed)


def _credit_findings(data: dict[str, Any], allowed: dict[str, Any]) -> list[Finding]:
    """Lizenz und Autor — die zwei Felder, die eine Weitergabe erst erlauben.

    **Abwesend ist kein Fehler.** Ein Rezept ohne Lizenz schreibt den Schlüssel
    gar nicht erst in die Datei; geprüft wird die *Zulässigkeit* eines Wertes,
    nie seine Anwesenheit. Eine Pflichtangabe wäre auch die falsche Stelle:
    Das Dateiformat kann eine fehlende Rechteklärung nicht ersetzen.

    Der Autor darf eine Adresse nennen und keine Auszeichnung: siehe
    :data:`FORBIDDEN_MARKUP`.
    """
    findings: list[Finding] = []

    licence = data.get("license")
    if licence not in (None, ""):
        allowed_licences = allowed.get("licenses") or []
        if not isinstance(licence, str):
            findings.append(Finding("check_licence_not_text"))
        elif allowed_licences and licence not in allowed_licences:
            findings.append(Finding("check_licence_unknown", {"licence": licence}))

    author = data.get("author")
    if author not in (None, ""):
        if not isinstance(author, str):
            findings.append(Finding("check_author_not_text"))
        else:
            limit = allowed["max_title_chars"]
            if len(author) > limit:
                findings.append(
                    Finding("check_author_too_long", {"length": len(author), "limit": limit})
                )
            if FORBIDDEN_MARKUP.search(author):
                findings.append(Finding("check_author_has_markup"))
    return findings


def _operation_findings(data: dict[str, Any], allowed: dict[str, Any]) -> list[Finding]:
    """Jeder Schritt nennt eine Operation, die diese Installation kennt."""
    document = data.get("document")
    if document is None:
        return []
    if not isinstance(document, dict):
        return [Finding("check_document_not_object")]
    steps = document.get("ops", [])
    if not isinstance(steps, list):
        return [Finding("check_ops_not_list")]

    findings: list[Finding] = []
    permitted = set(allowed["operations"])
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            findings.append(Finding("check_step_not_object", {"n": index + 1}))
            continue
        name = step.get("op")
        if name not in permitted:
            findings.append(Finding("check_step_unknown_op", {"n": index + 1, "name": name}))
        params = step.get("params", {})
        if not isinstance(params, dict):
            findings.append(Finding("check_params_not_object", {"n": index + 1}))
            continue
        for key, value in params.items():
            if not _value_is_allowed(value):
                findings.append(Finding("check_value_not_allowed", {"n": index + 1, "key": key}))
    return findings


def _payload_findings(data: dict[str, Any]) -> list[Finding]:
    """Payloads sind base64 und werden nicht ausgeführt — nur gemessen
    (Konzept §3.6)."""
    payloads = data.get("payloads")
    if payloads is None:
        return []
    if not isinstance(payloads, dict):
        return [Finding("check_payloads_not_object")]
    findings: list[Finding] = []
    for key, value in payloads.items():
        if not isinstance(value, str):
            findings.append(Finding("check_payload_not_text", {"name": key}))
            continue
        try:
            base64.b64decode(value, validate=True)
        except (ValueError, TypeError):
            findings.append(Finding("check_payload_not_base64", {"name": key}))
    return findings


def export_bytes(recipe: Recipe) -> bytes:
    """Die weiterzugebende Datei — geprüft, bevor sie gespeichert wird.

    **Der Prüfer, den niemand ruft, prüft nichts.** ``inspect`` stand eine
    Stunde lang vollständig da, mit zwölf Grenzfällen und drei Wächtern, und
    hatte keinen einzigen Aufrufer — genau die Kette, die am letzten Glied
    endet. Diese Funktion ist das Glied: Sie erzeugt die Datei **und** prüft
    sie, und beides lässt sich nicht trennen.

    Wer stattdessen ``json.dumps(file_data(...))`` schreibt, umgeht die
    Prüfung. Das ist der Fall, den ein Wächter über eine gemeinsame Regelliste
    **nicht** fängt: Zwei Prüfer aus einer Quelle sind gut, ein Weg, der an
    beiden vorbeiführt, hebt sie auf. 50 hat denselben Fehler am selben Tag in
    ihrem Gebiet gefunden — eine Eigenschaft, die nur im einen von zwei Zweigen
    gefragt wurde, und der andere Zweig lieferte wasserdichte, plausible,
    falsche Geometrie.

    Wirft, statt eine Datei zurückzugeben, die der Empfänger ohnehin ablehnt:
    Die Anwendung kennt den Baustein, aus dem die Datei entsteht, und kann
    sagen, welcher Teil das Problem ist.
    """
    from app.core.errors import CANCEL, CORRECT_INPUT, ValidationError
    from app.core.knowledge.parts.recipe import file_data
    from app.i18n import _

    payload = json.dumps(file_data(recipe), ensure_ascii=False, indent=2, sort_keys=True).encode(
        "utf-8"
    )
    findings = inspect(payload)
    if findings:
        raise ValidationError(
            field="title",
            detail=_(
                "Dieser Baustein kann so nicht weitergegeben werden. Die Dateiprüfung weist ihn ab."
            ),
            values={"recipe": recipe.name, "findings": " ".join(str(one) for one in findings)},
            constraint="part_file_invalid",
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    return payload


def read_recipe_file(path: str | Path) -> bytes:
    """Liest eine Bausteindatei höchstens bis zur festen Formatgrenze.

    ``Path.read_bytes`` wäre hier eine offene Speicherzusage an eine fremde
    Datei. Ein zusätzliches Byte reicht, um „zu groß" sicher zu unterscheiden,
    ohne den Rest der Datei einzulesen.
    """
    from app.core.errors import CANCEL, CHOOSE, ValidationError
    from app.i18n import _

    source = Path(path)
    try:
        with source.open("rb") as stream:
            payload = stream.read(MAX_FILE_BYTES + 1)
    except OSError as problem:
        raise ValidationError(
            field="file",
            detail=_("Diese Bausteindatei ließ sich nicht lesen."),
            values={"file": source.name, "reason": str(problem)[:200]},
            constraint="part_file_unreadable",
            suggestions=(CHOOSE, CANCEL),
        ) from problem
    if len(payload) > MAX_FILE_BYTES:
        _refuse_import([Finding("file_too_large", {"limit": MAX_FILE_BYTES})])
    return payload


def import_file(
    path: str | Path,
    parts: PartRegistry | None = None,
    registry: Registry | None = None,
) -> list[Any]:
    """Prüft und importiert genau eine lokale Bausteindatei.

    Die Erlaubnisliste läuft **vor** ``adopt``. Dadurch werden unbekannte
    Schlüssel und Operationsnamen nicht bloß ignoriert oder erst beim späteren
    Einsetzen bemerkt. Ein Aufnahmefehler wird zur Ausnahme; der UI-Handler kann
    danach keine Erfolgsmeldung mehr anzeigen.
    """
    payload = read_recipe_file(path)
    findings = inspect(payload)
    if findings:
        _refuse_import(findings)

    data = json.loads(payload)
    if not isinstance(data, dict):  # Durch ``inspect`` abgesicherte Invariante.
        _refuse_import([Finding("check_not_object")])
    adopted = adopt(data, parts, registry, catalog_source=IMPORTED_SOURCE)
    failures = [
        finding for finding in adopted if getattr(finding, "code", "") == "parts.recipe_failed"
    ]
    if failures:
        _refuse_import(failures)
    return adopted


def _refuse_import(findings: list[Any]) -> None:
    """Macht eine abgelehnte Datei zu einem bedienbaren Fehler."""
    from app.core.errors import CANCEL, CHOOSE, ValidationError
    from app.i18n import _

    raise ValidationError(
        field="file",
        detail=_("Diese Bausteindatei kann nicht importiert werden."),
        values={"findings": " ".join(str(finding) for finding in findings)},
        constraint="part_file_invalid",
        suggestions=(CHOOSE, CANCEL),
    )
