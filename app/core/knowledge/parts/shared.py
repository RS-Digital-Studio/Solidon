"""Die Formatprüfung lokaler Bausteindateien (Bauplan §24.5).

**Sie prüft nicht auf Verbotenes, sondern auf Erlaubtes.** Eine Sperrliste
(„kein ``import``, kein ``eval``") muss vollständig sein, um zu wirken, und
niemand kann sie vollständig halten. Eine Erlaubnisliste ist abgeschlossen:
Was hier nicht steht, kommt nicht durch.

Import und Export prüfen denselben Vertrag. Die Regeln stehen als Daten und
werden von Formprüfung, striktem Leser und Tests gemeinsam verwendet; zwei
handgepflegte Listen würden beim nächsten Format- oder Operationszuwachs
auseinanderlaufen.

**Die Liste der Operationsnamen kommt aus dem Register**, nicht aus einer
Aufzählung: Ein von Hand geführtes Verzeichnis wäre beim nächsten Zuwachs
    falsch, und Solidon wiese dann Dateien ab, die es selbst erzeugt hat.
"""

from __future__ import annotations

import base64
import dataclasses
import json
import math
import re
from typing import Any, Final, NoReturn

from app.core.knowledge.parts.recipe import (
    FORMAT_VERSION,
    RECIPE_LICENSES,
    Recipe,
)
from app.core.knowledge.parts.registry import GROUPS, NAME_PATTERN
from app.core.registry import REGISTRY
from app.core.scene.serialise import has_lone_surrogate

#: Wie groß eine Austauschdatei höchstens sein darf.
#:
#: Payloads reisen base64-kodiert im JSON und wachsen dabei um ein Drittel; ein
#: 5-MB-Netz wird zu knapp 7 MB Datei. Fünfundzwanzig Megabyte fassen damit
#: auch einen Baustein aus einem eingelesenen Modell. Größere Dateien werden
#: vor Base64-Dekodierung und Geometrieprüfung abgewiesen.
MAX_FILE_BYTES: Final = 25 * 1024 * 1024

#: Wie lang Titel und Beschreibung höchstens werden.
MAX_TITLE_CHARS: Final = 120
MAX_DOC_CHARS: Final = 2000

#: Harte Strukturgrenzen vor dem Bau eines fremden Rezepts.
#:
#: Die Dateigröße allein begrenzt weder die Zahl kleiner Objekte noch die
#: Arbeit beim Prüfen und Bauen. Diese Grenzen stehen deshalb in derselben
#: Regelliste wie die Operationsnamen und gelten an beiden Dateigrenzen.
MAX_OPERATIONS: Final = 64
MAX_PARAMS_PER_OPERATION: Final = 32
MAX_TOTAL_OPERATION_PARAMS: Final = 128
MAX_PROJECT_PARAMETERS: Final = 128
MAX_SOURCES: Final = 16
MAX_PAYLOADS: Final = 16
MAX_EXPOSED: Final = 32
MAX_FEATURES: Final = 64
MAX_PARAMETER_LIST_ITEMS: Final = 256
MAX_VALUE_CHARS: Final = 2048
MAX_DECODED_PAYLOAD_BYTES: Final = 20 * 1024 * 1024
MAX_OPERATION_INPUTS: Final = 32
MAX_OPERATION_OUTPUTS: Final = 32
MAX_MATCHES_PER_OPERATION: Final = 64
MAX_TRANSLATABLE_PER_OPERATION: Final = 64
MAX_RANGE_FAILURES: Final = 128
MAX_PART_FILE_JSON_DEPTH: Final = 64

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
    Befund beides: den Schlüssel für die Übersetzung und die Werte, die zu ihm
    geführt haben. Die Oberfläche kann alle Ursachen in einem Durchgang zeigen.

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
    """Die Erlaubnisliste als Daten — die eine Quelle für beide Dateirichtungen.

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
        "operation_params": {
            entry.name: sorted(param.name for param in entry.params.spec())
            for entry in REGISTRY.all()
        },
        "max_file_bytes": MAX_FILE_BYTES,
        "max_title_chars": MAX_TITLE_CHARS,
        "max_doc_chars": MAX_DOC_CHARS,
        "max_operations": MAX_OPERATIONS,
        "max_params_per_operation": MAX_PARAMS_PER_OPERATION,
        "max_total_operation_params": MAX_TOTAL_OPERATION_PARAMS,
        "max_project_parameters": MAX_PROJECT_PARAMETERS,
        "max_sources": MAX_SOURCES,
        "max_payloads": MAX_PAYLOADS,
        "max_exposed": MAX_EXPOSED,
        "max_features": MAX_FEATURES,
        "max_parameter_list_items": MAX_PARAMETER_LIST_ITEMS,
        "max_value_chars": MAX_VALUE_CHARS,
        "max_decoded_payload_bytes": MAX_DECODED_PAYLOAD_BYTES,
        "max_operation_inputs": MAX_OPERATION_INPUTS,
        "max_operation_outputs": MAX_OPERATION_OUTPUTS,
        "max_matches_per_operation": MAX_MATCHES_PER_OPERATION,
        "max_translatable_per_operation": MAX_TRANSLATABLE_PER_OPERATION,
        "max_range_failures": MAX_RANGE_FAILURES,
        "max_json_depth": MAX_PART_FILE_JSON_DEPTH,
        "value_kinds": list(VALUE_KINDS),
        # Die Wertemenge gehört dem Rezept-Kern. Der Dateiprüfer liest sie von
        # dort, damit der Kern nicht von seinem Austauschformat abhängt.
        "licenses": list(RECIPE_LICENSES),
        # **Was der Empfänger braucht, um es überhaupt aufnehmen zu können.**
        # Diese drei prüft ``PartRegistry._check`` beim Einsetzen, und wer sie
        # verletzt, hat eine Datei, die formal lesbar ist und sich trotzdem
        # nicht in den Katalog aufnehmen lässt. Ein fremdes Programm kann so
        # eine Datei schreiben; deshalb wird die Einsetzbarkeit hier geprüft.
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


def _value_is_allowed(
    value: Any,
    *,
    max_list_items: int,
    max_value_chars: int,
    depth: int = 0,
) -> bool:
    """Ob ein Parameterwert eine der erlaubten Formen hat.

    ``depth`` bricht die Rekursion nach einer Ebene ab: Eine Liste von Zahlen
    ist ein Parameter, eine Liste von Listen von Listen ist eine Struktur, die
    sich jemand ausgedacht hat.
    """
    if isinstance(value, str):
        return len(value) <= max_value_chars
    if isinstance(value, float):
        return math.isfinite(value)
    if isinstance(value, bool | int):
        return True
    if isinstance(value, list) and depth == 0:
        return len(value) <= max_list_items and all(
            _value_is_allowed(
                item,
                max_list_items=max_list_items,
                max_value_chars=max_value_chars,
                depth=depth + 1,
            )
            for item in value
        )
    return False


def _reject_json_constant(value: str) -> NoReturn:
    """JSON kennt weder NaN noch Unendlich; Python akzeptiert beides sonst still."""

    raise ValueError(value)


def _json_is_too_deep(value: Any, limit: int) -> bool:
    """Misst Container-Tiefe iterativ, bevor fachliche Leser hineinlaufen."""

    pending = [(value, 1)]
    while pending:
        current, depth = pending.pop()
        if not isinstance(current, dict | list):
            continue
        if depth > limit:
            return True
        children = current.values() if isinstance(current, dict) else current
        pending.extend((child, depth + 1) for child in children)
    return False


def inspect(payload: bytes, known: dict[str, Any] | None = None) -> list[Finding]:
    """Prüft eine Austauschdatei. Eine leere Liste heißt: formal zulässig.

    Gibt **alle** Befunde zurück und nicht nur den ersten: Wer eine Datei
    ablehnt, sollte sagen können, was alles daran fehlt — eine Ablehnung, die
    nach jedem Berichtigen eine neue nennt, ist eine Kette ohne Ende.

    ``known`` ist die Regelliste; ohne Angabe die aus :func:`rules`. Der
    Parameter hält Grenzfalltests unabhängig vom globalen Registerzustand.
    """
    allowed = known if known is not None else rules()
    findings: list[Finding] = []

    if len(payload) > allowed["max_file_bytes"]:
        findings.append(
            Finding(
                "file_too_large",
                {"size": len(payload), "limit": allowed["max_file_bytes"]},
            )
        )
        # Weiter geht es trotzdem: Wer zwei Gründe hat, soll beide erfahren.

    try:
        data = json.loads(payload, parse_constant=_reject_json_constant)
    except (UnicodeDecodeError, ValueError, RecursionError):
        findings.append(Finding("check_not_json"))
        return findings
    if _json_is_too_deep(data, int(allowed["max_json_depth"])) or has_lone_surrogate(data):
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
                    # formatiert, damit die Fehlermeldung eine lesbare Liste
                    # statt einer Python-Darstellung zeigt.
                    "known": ", ".join(str(one) for one in allowed["recipe_format_versions"]),
                },
            )
        )

    findings.extend(_text_findings(data, allowed))
    findings.extend(_adoptable_findings(data, allowed))
    findings.extend(_imported_origin_findings(data))
    findings.extend(_resource_findings(data, allowed))
    findings.extend(_operation_findings(data, allowed))
    findings.extend(_payload_findings(data, allowed))
    return findings


def _imported_origin_findings(data: dict[str, Any]) -> list[Finding]:
    """Prüft die abgeschlossene Quittung eines lokalen Dateiimports."""

    origin = data.get("imported_origin")
    if origin is None:
        return []
    if not isinstance(origin, dict):
        return [Finding("check_imported_origin_not_object")]
    expected = {"source_sha256", "imported_at"}
    if set(origin) != expected:
        return [Finding("check_imported_origin_keys")]

    findings: list[Finding] = []
    if not isinstance(origin["source_sha256"], str) or not re.fullmatch(
        r"[0-9a-f]{64}", origin["source_sha256"]
    ):
        findings.append(Finding("check_imported_origin_sha256"))
    if not isinstance(origin["imported_at"], str) or not re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", origin["imported_at"]
    ):
        findings.append(Finding("check_imported_origin_imported_at"))
    return findings


def _resource_findings(data: dict[str, Any], allowed: dict[str, Any]) -> list[Finding]:
    """Begrenzt die Anzahl fremder Strukturelemente vor dem Rezeptbau."""

    findings: list[Finding] = []
    document = data.get("document")
    if isinstance(document, dict):
        for field, rule in (
            ("parameters", "max_project_parameters"),
            ("sources", "max_sources"),
        ):
            value = document.get(field, {})
            if isinstance(value, dict) and len(value) > int(allowed[rule]):
                findings.append(
                    Finding(
                        "check_too_many_entries",
                        {"field": field, "count": len(value), "limit": allowed[rule]},
                    )
                )

    for field, rule in (
        ("payloads", "max_payloads"),
        ("features", "max_features"),
    ):
        value = data.get(field, {})
        if isinstance(value, dict) and len(value) > int(allowed[rule]):
            findings.append(
                Finding(
                    "check_too_many_entries",
                    {"field": field, "count": len(value), "limit": allowed[rule]},
                )
            )

    exposed = data.get("exposed", [])
    if isinstance(exposed, list) and len(exposed) > int(allowed["max_exposed"]):
        findings.append(
            Finding(
                "check_too_many_entries",
                {"field": "exposed", "count": len(exposed), "limit": allowed["max_exposed"]},
            )
        )
    report = data.get("range_report")
    if isinstance(report, dict):
        failures = report.get("failures", [])
        if isinstance(failures, list) and len(failures) > int(allowed["max_range_failures"]):
            findings.append(
                Finding(
                    "check_too_many_entries",
                    {
                        "field": "range_report.failures",
                        "count": len(failures),
                        "limit": allowed["max_range_failures"],
                    },
                )
            )
    return findings


def _adoptable_findings(data: dict[str, Any], allowed: dict[str, Any]) -> list[Finding]:
    """Ob der Empfänger den Baustein überhaupt aufnehmen kann.

    Name, Gruppe und mindestens ein benanntes Merkmal sind Voraussetzungen des
    Katalogs. Ein fremdes Programm kann eine formal lesbare Datei ohne diese
    Angaben schreiben; deshalb prüft der Dateivertrag sie vor der Übernahme.
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
    """Begrenzt die sichtbaren Texte des lokalen Dateiformats."""
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
    return findings + _credit_findings(data, allowed)


def _credit_findings(data: dict[str, Any], allowed: dict[str, Any]) -> list[Finding]:
    """Lizenz und Autor bleiben verlustfrei erhalten und werden formal geprüft.

    **Abwesend ist kein Fehler.** Ein Rezept ohne Lizenz schreibt den Schlüssel
    gar nicht erst in die Datei; geprüft wird die *Zulässigkeit* eines Wertes,
    nie seine Anwesenheit. Eine Pflichtangabe würde bestehende eigene Rezepte
    nachträglich ungültig machen.
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
    max_operations = int(allowed["max_operations"])
    if len(steps) > max_operations:
        findings.append(
            Finding(
                "check_too_many_entries",
                {"field": "ops", "count": len(steps), "limit": max_operations},
            )
        )
    permitted = set(allowed["operations"])
    total_params = 0
    for index, step in enumerate(steps[:max_operations]):
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
        total_params += len(params)
        operation_params = allowed.get("operation_params") or {}
        known_params = set(operation_params.get(name, ()))
        unknown_params = sorted(set(params) - known_params) if name in operation_params else []
        if unknown_params:
            findings.append(
                Finding(
                    "check_unknown_params",
                    {"n": index + 1, "keys": ", ".join(unknown_params)},
                )
            )
        if len(params) > int(allowed["max_params_per_operation"]):
            findings.append(
                Finding(
                    "check_too_many_params",
                    {
                        "n": index + 1,
                        "count": len(params),
                        "limit": allowed["max_params_per_operation"],
                    },
                )
            )
        for key, value in params.items():
            if not _value_is_allowed(
                value,
                max_list_items=int(allowed["max_parameter_list_items"]),
                max_value_chars=int(allowed["max_value_chars"]),
            ):
                findings.append(Finding("check_value_not_allowed", {"n": index + 1, "key": key}))
        for field, rule in (
            ("in", "max_operation_inputs"),
            ("out", "max_operation_outputs"),
            ("translatable", "max_translatable_per_operation"),
        ):
            collection = step.get(field, [])
            if isinstance(collection, list) and len(collection) > int(allowed[rule]):
                findings.append(
                    Finding(
                        "check_too_many_entries",
                        {
                            "field": f"ops.{index + 1}.{field}",
                            "count": len(collection),
                            "limit": allowed[rule],
                        },
                    )
                )
        matches = step.get("matches", {})
        if isinstance(matches, dict) and len(matches) > int(allowed["max_matches_per_operation"]):
            findings.append(
                Finding(
                    "check_too_many_entries",
                    {
                        "field": f"ops.{index + 1}.matches",
                        "count": len(matches),
                        "limit": allowed["max_matches_per_operation"],
                    },
                )
            )
    if total_params > int(allowed["max_total_operation_params"]):
        findings.append(
            Finding(
                "check_too_many_total_params",
                {"count": total_params, "limit": allowed["max_total_operation_params"]},
            )
        )
    return findings


def _payload_findings(data: dict[str, Any], allowed: dict[str, Any]) -> list[Finding]:
    """Payloads werden nur als eingebettete Quelldaten geprüft und gemessen."""
    payloads = data.get("payloads")
    if payloads is None:
        return []
    if not isinstance(payloads, dict):
        return [Finding("check_payloads_not_object")]
    findings: list[Finding] = []
    decoded_total = 0
    for key, value in payloads.items():
        if not isinstance(value, str):
            findings.append(Finding("check_payload_not_text", {"name": key}))
            continue
        try:
            decoded_total += len(base64.b64decode(value, validate=True))
        except (ValueError, TypeError):
            findings.append(Finding("check_payload_not_base64", {"name": key}))
    if decoded_total > int(allowed["max_decoded_payload_bytes"]):
        findings.append(
            Finding(
                "check_payloads_too_large",
                {"size": decoded_total, "limit": allowed["max_decoded_payload_bytes"]},
            )
        )
    return findings


def for_export(recipe: Recipe) -> bytes:
    """Erzeugt eine lokale Austauschdatei und prüft sie vor der Ausgabe.

    **Der Prüfer, den niemand ruft, prüft nichts.** ``inspect`` stand eine
    Stunde lang vollständig da, mit zwölf Grenzfällen und drei Wächtern, und
    hatte keinen einzigen Aufrufer — genau die Kette, die am letzten Glied
    endet. Diese Funktion ist das Glied: Sie erzeugt die Datei **und** prüft
    sie, und beides lässt sich nicht trennen.

    Wer stattdessen ``json.dumps(file_data(...))`` schreibt, umgeht die
    Prüfung. Import und Export müssen dieselbe Grenze benutzen, sonst kann die
    Anwendung Dateien erzeugen, die sie selbst nicht wieder einliest.
    """
    from app.core.errors import CANCEL, CORRECT_INPUT, ValidationError
    from app.core.knowledge.parts.recipe import file_data
    from app.i18n import _

    data = file_data(recipe)
    # Private Bestandsrezepte dürfen beide Angaben weiter auslassen. An der
    # ausdrücklichen Dateigrenze wird ihr Fehlen dagegen sichtbar gespeichert:
    # Eine leere Lizenz ist keine stillschweigende Erlaubnis zur Weitergabe.
    data.setdefault("license", "")
    data.setdefault("author", "")
    payload = json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    findings = inspect(payload)
    if findings:
        raise ValidationError(
            field="title",
            detail=_(
                "Dieser Baustein entspricht nicht dem sicheren Austauschformat. "
                "Prüfen Sie die genannten Angaben und versuchen Sie es erneut."
            ),
            values={"recipe": recipe.name, "findings": " ".join(str(one) for one in findings)},
            constraint="shared_rules",
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    return payload
