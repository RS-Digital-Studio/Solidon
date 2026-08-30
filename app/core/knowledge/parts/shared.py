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

from app.core.knowledge.parts.recipe import FORMAT_VERSION, RECIPE_LICENSES, Recipe
from app.core.knowledge.parts.registry import GROUPS, NAME_PATTERN
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

#: Dasselbe **ohne** die Link-Hälfte — für das Autorenfeld.
#:
#: Ein Autor darf sagen, wo man ihn findet; ``Recipe.author`` ist ausdrücklich
#: „ein Name, ein Kürzel, eine Adresse". Eine Auszeichnung darf er trotzdem
#: nicht einschleusen: Die Börse zeigt das Feld öffentlich, und was für Titel
#: und Erklärtext gilt, gilt für einen Namen genauso. Zwei Muster, weil die
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

    **Der Satz entsteht am Anzeigeort, das Urteil hier.** Beide Prüfseiten —
    diese und ``shared_common.php`` — müssen über dieselbe Datei dasselbe
    sagen, und ``tests/test_shared_php.py`` vergleicht das. Solange der
    Vergleich über **Sätze** lief, war er scharf: Eine Mutation, die in PHP
    ``mb_strlen`` durch ``strlen`` ersetzt, ließ ihn fallen, weil die Zahl im
    Satz stand (200 Zeichen gegen 400 Bytes, gemessen von 50).

    Mit einer gemeinsamen Textquelle wäre genau diese Schärfe verschwunden:
    Zwei Seiten, die denselben Satz aus derselben JSON holen, stimmen immer
    überein — der Test verglich zwei Lesevorgänge einer Datei und wäre grün
    geblieben, für immer und ohne je rot zu werden. Deshalb trägt ein Befund
    **beides**: den Schlüssel für die Übersetzung und die Werte, die zu ihm
    geführt haben.

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
        # Die Wertemenge gehört dem Rezept-Kern, nicht der Börse: Ein Feld an
        # ``Recipe`` mit festen zulässigen Werten ist seine Sache, und die
        # Börse gibt heraus, was sie vorfindet. Andersherum — die Börse führt
        # die Liste, der Kern liest sie — hätte den Kern von ihr abhängig
        # gemacht, und das ist die falsche Richtung (abgestimmt mit d3,
        # 30.08.2026).
        "licenses": list(RECIPE_LICENSES),
        # **Was der Empfänger braucht, um es überhaupt aufnehmen zu können.**
        # Diese drei prüft ``PartRegistry._check`` beim Einsetzen, und wer sie
        # verletzt, hat eine Datei, die durch jede Börsenprüfung kommt und beim
        # ersten, der sie herunterlädt, mit „ließ sich nicht aufnehmen"
        # scheitert. In der Anwendung kann das nicht passieren — dort kommt
        # jedes Rezept aus ``capture``, und das erzwingt alle drei. Eine
        # Börsendatei kommt aber gerade **nicht** von uns.
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
    findings: list[Finding] = []

    if len(payload) > allowed["max_upload_bytes"]:
        findings.append(
            Finding(
                "upload_too_large",
                {"size": len(payload), "limit": allowed["max_upload_bytes"]},
            )
        )
        # Weiter geht es trotzdem: Wer zwei Gründe hat, soll beide erfahren.

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
    Ende-zu-Ende-Lauf): ``for_upload`` gab dreimal hintereinander eine saubere
    Datei aus, die ``adopt`` danach ablehnte — Name nicht ``lower_snake_case``,
    Gruppe unbekannt, kein benanntes Merkmal. Aus Kundensicht klickt jemand
    „Veröffentlichen", bekommt eine Datei, lädt sie hoch, und der Erste, der
    sie holt, liest „Ein mitgereistes Rezept ließ sich nicht aufnehmen."

    Die Frage war, ob das hierhin gehört oder zum Empfänger, und sie
    entscheidet sich an dem, was diese Prüfung **ist**: die erste und einzige
    vor der Veröffentlichung. Was hier durchkommt, steht in der Galerie — und
    ein Baustein, den niemand laden kann, gehört dort nicht hin. Der Empfänger
    prüft weiter (er muss, denn er ist die Stelle, die es einlöst), aber er
    ist nicht mehr der Erste, der es merkt.

    **In der Anwendung kann keiner der drei Fälle entstehen**: Dort kommt jedes
    Rezept aus ``capture``, und das erzwingt alle drei. Eine Börsendatei kommt
    aber gerade nicht von uns — sie kann von Hand geschrieben sein oder aus
    einem anderen Programm stammen, und genau dafür gibt es diese Prüfung.
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
    nie seine Anwesenheit. Eine Pflichtangabe wäre auch die falsche Stelle —
    ob die Börse eine Lizenz verlangt, entscheidet die Börse und nicht das
    Dateiformat.

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
    """Jeder Schritt nennt eine Operation, die der Server kennt (Konzept §3.1)."""
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
            values={"recipe": recipe.name, "findings": " ".join(str(one) for one in findings)},
            constraint="shared_rules",
            suggestions=(CORRECT_INPUT, CANCEL),
        )
    return payload
