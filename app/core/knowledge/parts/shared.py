"""Die Formatprüfung der geteilten Bausteine (Konzept §3.1, §3.2, §3.6).

**Sie prüft nicht auf Verbotenes, sondern auf Erlaubtes.** Eine Sperrliste
(„kein ``import``, kein ``eval``") muss vollständig sein, um zu wirken, und
niemand kann sie vollständig halten. Eine Erlaubnisliste ist abgeschlossen:
Was hier nicht steht, kommt nicht durch.

Seit Kunden ohne Sichtung hochladen (Robert, 30.08.2026), ist diese Prüfung
nicht mehr die zweite Verteidigungslinie, sondern **die erste und einzige vor
der Veröffentlichung**.

Zwei Seiten prüfen dasselbe — die Anwendung vor dem Hochladen, der Server beim
Empfangen —, und sie sind in verschiedenen Sprachen geschrieben. Deshalb
stehen die Regeln hier als **Daten** und nicht als Code: :func:`rules` gibt
sie als gewöhnliches Wörterbuch, ``tools/make_shared_rules.py`` schreibt sie
neben die PHP-Dateien, und beide Seiten lesen dieselbe Liste. Zwei
handgepflegte Listen wären die teurere Bauart — der Skizzenlöser und sein
Serializer haben am 31.08.2026 vorgeführt, wie das endet: Die eine ließ durch,
was die andere abwies, und niemand merkte es, bis eine Datei nicht mehr
aufging.

**Die Liste der Operationsnamen kommt aus dem Register**, nicht aus einer
Aufzählung: Ein von Hand geführtes Verzeichnis wäre beim nächsten Zuwachs
falsch, und die Börse wiese dann Rezepte ab, die die Anwendung selbst erzeugt
hat.
"""

from __future__ import annotations

import base64
import dataclasses
import json
import re
from typing import Any, Final

from app.core.knowledge.parts.recipe import FORMAT_VERSION, Recipe
from app.core.registry import REGISTRY

#: Wie groß eine hochgeladene Datei höchstens sein darf (Konzept §3.6).
#:
#: Payloads reisen base64-kodiert im JSON und wachsen dabei um ein Drittel; ein
#: 5-MB-Netz wird zu knapp 7 MB Datei. Fünfundzwanzig Megabyte fassen damit
#: auch einen Baustein aus einem eingelesenen Modell — und der Upload-Bereich
#: nennt die Grenze, **bevor** jemand eine Datei wählt, statt sie am Server
#: unvermittelt zuschlagen zu lassen.
MAX_UPLOAD_BYTES: Final = 25 * 1024 * 1024

#: Wie lang Titel und Beschreibung höchstens werden (Konzept §3.2).
#:
#: Das meiste, was eine offene Börse an Müll bekommt, ist Werbung — und Werbung
#: braucht Platz und einen Link. Beides ist hier begrenzt.
MAX_TITLE_CHARS: Final = 120
MAX_DOC_CHARS: Final = 2000

#: Was in einem freien Text nichts zu suchen hat.
#:
#: Kein Wächter gegen einen entschlossenen Angreifer — die Texte werden ohnehin
#: maskiert ausgegeben. Aber Werbung braucht einen anklickbaren Link, und ohne
#: ihn lohnt sie sich nicht.
FORBIDDEN_TEXT: Final = re.compile(r"https?://|www\.|<[a-zA-Z/!]", re.IGNORECASE)

#: Welche Werte in einem Parameter stehen dürfen.
#:
#: Zahl, Zeichenkette, Wahrheitswert — und Listen davon. Ein Wörterbuch ist
#: ausdrücklich nicht dabei: Es ist die Form, in der sich verschachtelte
#: Strukturen einschmuggeln lassen, und kein Parameter braucht eine.
VALUE_KINDS: Final = ("number", "string", "boolean", "list")


def rules() -> dict[str, Any]:
    """Die Erlaubnisliste als Daten — die eine Quelle für beide Prüfseiten.

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
        "max_upload_bytes": MAX_UPLOAD_BYTES,
        "max_title_chars": MAX_TITLE_CHARS,
        "max_doc_chars": MAX_DOC_CHARS,
        "value_kinds": list(VALUE_KINDS),
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


def inspect(payload: bytes, known: dict[str, Any] | None = None) -> list[str]:
    """Prüft eine hochgeladene Rezeptdatei. Leere Liste heißt: nimmt der Server an.

    Gibt **alle** Befunde zurück und nicht nur den ersten: Wer eine Datei
    ablehnt, sollte sagen können, was alles daran fehlt — eine Ablehnung, die
    nach jedem Berichtigen eine neue nennt, ist eine Kette ohne Ende.

    ``known`` ist die Regelliste; ohne Angabe die aus :func:`rules`. Der
    Parameter ist der Grund, aus dem diese Funktion prüfbar ist, **und** der
    Weg, auf dem der Server dieselbe Prüfung mit der Datei neben seinen
    PHP-Dateien fährt.
    """
    allowed = known if known is not None else rules()
    findings: list[str] = []

    if len(payload) > allowed["max_upload_bytes"]:
        findings.append(
            f"Die Datei ist {len(payload)} Byte groß, erlaubt sind {allowed['max_upload_bytes']}."
        )
        # Weiter geht es trotzdem: Wer zwei Gründe hat, soll beide erfahren.

    try:
        data = json.loads(payload)
    except (UnicodeDecodeError, ValueError):
        findings.append("Die Datei ist kein gültiges JSON.")
        return findings
    if not isinstance(data, dict):
        findings.append("Ein Rezept ist ein Objekt, keine Liste und keine Zahl.")
        return findings

    unknown = sorted(set(data) - set(allowed["recipe_keys"]))
    if unknown:
        findings.append(f"Unbekannte Schlüssel: {', '.join(unknown)}.")

    version = data.get("format_version")
    if version not in allowed["recipe_format_versions"]:
        findings.append(
            f"Die Formatversion {version!r} kennt der Server nicht — "
            f"bekannt sind {allowed['recipe_format_versions']}."
        )

    findings.extend(_text_findings(data, allowed))
    findings.extend(_operation_findings(data, allowed))
    findings.extend(_payload_findings(data))
    return findings


def _text_findings(data: dict[str, Any], allowed: dict[str, Any]) -> list[str]:
    """Titel und Beschreibung: Länge und keine Links (Konzept §3.2)."""
    findings: list[str] = []
    for key, limit in (("title", allowed["max_title_chars"]), ("doc", allowed["max_doc_chars"])):
        text = data.get(key)
        if text is None:
            continue
        if not isinstance(text, str):
            findings.append(f"„{key}“ ist kein Text.")
            continue
        if len(text) > limit:
            findings.append(f"„{key}“ ist {len(text)} Zeichen lang, erlaubt sind {limit}.")
        if FORBIDDEN_TEXT.search(text):
            findings.append(f"„{key}“ enthält einen Link oder Auszeichnung.")
    return findings


def _operation_findings(data: dict[str, Any], allowed: dict[str, Any]) -> list[str]:
    """Jeder Schritt nennt eine Operation, die der Server kennt (Konzept §3.1)."""
    document = data.get("document")
    if document is None:
        return []
    if not isinstance(document, dict):
        return ["„document“ ist kein Objekt."]
    steps = document.get("ops", [])
    if not isinstance(steps, list):
        return ["„ops“ ist keine Liste."]

    findings: list[str] = []
    permitted = set(allowed["operations"])
    for index, step in enumerate(steps):
        where = f"Schritt {index + 1}"
        if not isinstance(step, dict):
            findings.append(f"{where} ist kein Objekt.")
            continue
        name = step.get("op")
        if name not in permitted:
            findings.append(f"{where} nennt die unbekannte Operation {name!r}.")
        params = step.get("params", {})
        if not isinstance(params, dict):
            findings.append(f"{where} hat Parameter, die kein Objekt sind.")
            continue
        for key, value in params.items():
            if not _value_is_allowed(value):
                findings.append(
                    f"{where}, Parameter „{key}“ hat einen Wert, der nicht erlaubt ist."
                )
    return findings


def _payload_findings(data: dict[str, Any]) -> list[str]:
    """Payloads sind base64 und werden nicht ausgeführt — nur gemessen (§3.6)."""
    payloads = data.get("payloads")
    if payloads is None:
        return []
    if not isinstance(payloads, dict):
        return ["„payloads“ ist kein Objekt."]
    findings: list[str] = []
    for key, value in payloads.items():
        if not isinstance(value, str):
            findings.append(f"Der Anhang „{key}“ ist keine Zeichenkette.")
            continue
        try:
            base64.b64decode(value, validate=True)
        except (ValueError, TypeError):
            findings.append(f"Der Anhang „{key}“ ist kein base64.")
    return findings


def for_upload(recipe: Recipe) -> bytes:
    """Die Datei, die zur Börse geht — geprüft, bevor sie herausgeht.

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

    Wirft, statt eine Datei zurückzugeben, die der Server ohnehin abweist: Die
    Anwendung weiß hier mehr als der Server später — sie kennt den Baustein,
    aus dem die Datei entsteht, und kann sagen, welcher Teil das Problem ist.
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
                "Dieser Baustein kann so nicht geteilt werden. Der Server prüft "
                "dasselbe und würde ihn abweisen."
            ),
            values={"recipe": recipe.name, "findings": " ".join(findings)},
            constraint="shared_rules",
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    return payload
