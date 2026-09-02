"""Große Sammelwerte im Container (Bauplan §12, Konzept P16 §9).

Ein Sammelparameter hält, was ein Editor gesammelt hat: eine Skizze, eine
Strichliste, ein Skelett. Für eine Skizze ist das ein paar Kilobyte; für eine
Sculpting-Sitzung sind es bei viertausend Zügen ein halbes Megabyte, und das
steht dann als eine Zeile Zahlen im ``project.json``.

Das ist zweimal unangenehm: Die Datei lässt sich nicht mehr ansehen, und jede
Änderung an irgendeinem Parameter schreibt sie ganz neu. Ab einer Grenze wandert
der Wert deshalb in eine eigene Quelle im Container, und im Dokument steht ein
Verweis darauf.

**Nur beim Speichern und Laden.** Im Arbeitsspeicher ist ein Sammelparameter
immer sein Text — sonst müsste jede Auswertung, jeder Hash und jeder
Vergleich wissen, ob der Wert gerade ausgelagert ist. Die Auslagerung ist eine
Eigenschaft der Datei, nicht des Dokuments.
"""

from __future__ import annotations

import re
from typing import Any, Final

from app.core.errors import ValidationError
from app.core.log import get_logger
from app.core.types import SourceId
from app.i18n import _

_log = get_logger(__name__)

#: Ab wie vielen Zeichen ein Sammelwert ausgelagert wird.
#:
#: Zweihunderttausend sind etwa zweitausend Pinselzüge und damit in der
#: Größenordnung einer großen Skizze — bis dahin bleibt die Projektdatei eine
#: Datei, die man aufmachen und lesen kann, und das ist mehr wert als die
#: Kilobyte. Darüber kippt das Verhältnis: Der Wert ist dann keine Angabe mehr,
#: die jemand liest, sondern ein Datenblock.
GATHERED_LIMIT: Final = 200_000

#: Woran ein ausgelagerter Wert beginnt. Ein Doppelpunkt kommt in keinem
#: JSON-Text eines Editors an erster Stelle vor — die Sammelwerte beginnen
#: alle mit ``[`` oder ``{``. Erkannt wird ein Verweis trotzdem nicht am
#: Präfix allein, sondern an :data:`_REFERENCE` und :func:`_collects`: Der
#: Satz gilt für Sammelwerte und nicht für jeden anderen Parameter.
GATHERED_PREFIX: Final = "source:"

#: Wo die ausgelagerten Werte im Container liegen.
GATHERED_DIR: Final = "sources/gathered"

#: Genau die Gestalt, die :func:`externalise` schreibt — nicht nur ihr Anfang.
#:
#: Das Präfix allein reichte nicht: Wer sein Objekt ``source:meiner`` nannte,
#: speicherte ein Projekt, das er nicht mehr öffnen konnte. Das Laden hielt
#: mit „Zu diesem Schritt fehlt der ausgelagerte Inhalt im Container" an, und
#: der Container war heil — nur der Name sah aus wie ein Verweis.
_REFERENCE = re.compile(rf"^{re.escape(GATHERED_PREFIX)}gathered_\d+$")


def _is_reference(value: object) -> bool:
    """Ob dieser Wert die Gestalt eines ausgelagerten Verweises hat."""
    return isinstance(value, str) and _REFERENCE.match(value) is not None


def _collects(op_name: object, param_name: str) -> bool:
    """Ob dieser Parameter dieser Operation überhaupt ein Sammelwert ist.

    Die zweite Hälfte derselben Absicherung: Ausgelagert wird, was ein Editor
    gesammelt hat (``GATHERED_KINDS`` — Skizze, Strichliste, Skelett), und
    sonst nichts. Ein Name, ein Text, ein Dateipfad ist nie ein Verweis, wie
    immer er aussieht.

    **Kennt das Register die Operation nicht, gilt der Parameter als
    möglicher Sammelwert.** Das ist die vorsichtigere Antwort: Ein Verweis,
    den niemand auflöst, wäre für die Operation dahinter ein Text ohne Inhalt
    und ein leeres Ergebnis ohne Fehlermeldung — teurer als ein Halt, der
    sagt, was fehlt.
    """
    from app.core.registry import GATHERED_KINDS, REGISTRY

    if not isinstance(op_name, str) or not REGISTRY.has(op_name):
        return True
    return any(
        entry.name == param_name and entry.kind in GATHERED_KINDS
        for entry in REGISTRY.get(op_name).params.spec()
    )


def externalise(data: dict[str, Any], next_id: int) -> dict[SourceId, bytes]:
    """Große Sammelwerte aus den Operationsdaten in eigene Quellen holen.

    Ändert ``data`` an Ort und Stelle — es ist die frisch serialisierte Kopie
    des Dokuments und nicht das Dokument selbst. Zurück kommt, was zusätzlich
    in den Container gehört.
    """
    payloads: dict[SourceId, bytes] = {}
    for operation in data.get("ops", ()):
        params = operation.get("params")
        if not isinstance(params, dict):
            continue
        for name, value in list(params.items()):
            if not isinstance(value, str) or len(value) <= GATHERED_LIMIT:
                continue
            if _is_reference(value) or not _collects(operation.get("op"), name):
                continue
            source_id = f"gathered_{next_id}"
            next_id += 1
            payloads[source_id] = value.encode("utf-8")
            params[name] = f"{GATHERED_PREFIX}{source_id}"
            _log.info(
                "moved %s.%s (%d chars) into %s", operation.get("op"), name, len(value), source_id
            )
    return payloads


def gathered_path(source_id: SourceId) -> str:
    """Wo ein ausgelagerter Wert im Container liegt. Immer relativ (Regel 12)."""
    return f"{GATHERED_DIR}/{source_id}.json"


def inline(data: dict[str, Any], payloads: dict[SourceId, bytes]) -> None:
    """Die Verweise wieder durch ihren Inhalt ersetzen.

    Ein Verweis ohne Inhalt ist kein halbes Dokument, sondern ein kaputtes:
    Die Operation dahinter würde mit dem Text ``source:gathered_3`` rechnen und
    ein leeres Ergebnis liefern, ohne dass irgendwo etwas fehlt. Also hält es
    hier an.
    """
    for operation in data.get("ops", ()):
        params = operation.get("params")
        if not isinstance(params, dict):
            continue
        for name, value in list(params.items()):
            if not _is_reference(value) or not _collects(operation.get("op"), name):
                continue
            source_id = str(value)[len(GATHERED_PREFIX) :]
            payload = payloads.get(source_id)
            if payload is None:
                raise ValidationError(
                    field=f"ops.{operation.get('id', '?')}.{name}",
                    detail=_(
                        "Zu diesem Schritt fehlt der ausgelagerte Inhalt im Container — "
                        "die Datei ist unvollständig."
                    ),
                    constraint="missing_gathered",
                    values={"source": source_id},
                )
            params[name] = payload.decode("utf-8")


def references(data: dict[str, Any]) -> set[SourceId]:
    """Welche ausgelagerten Quellen dieses Dokument braucht."""
    found: set[SourceId] = set()
    for operation in data.get("ops", ()):
        params = operation.get("params")
        if not isinstance(params, dict):
            continue
        for name, value in params.items():
            if _is_reference(value) and _collects(operation.get("op"), name):
                found.add(str(value)[len(GATHERED_PREFIX) :])
    return found


def carry_over(data: dict[str, Any]) -> dict[str, Any]:
    """7 → 8: Vor Version 8 gab es keine ausgelagerten Sammelwerte.

    Eine ältere Datei hat sie schlicht nicht — jeder Sammelparameter steht dort
    als Text, wo er hingehört, und das bleibt gültig. Der Schritt ist deshalb
    eine Feststellung und keine Umrechnung, und er bleibt trotzdem eine eigene
    Funktion: Die Kette wird nie zusammengefasst (``AGENTS.md``, Checkliste
    „Dateiformat ändern"), damit sie von der allerersten Version an weiter
    funktioniert.

    Was er prüft, ist der einzige Fall, in dem eine alte Datei doch etwas
    dieser Art enthalten könnte: ein Parameterwert, der zufällig wie ein
    Verweis aussieht. Er wäre in Version 8 einer, und das wäre eine
    Umdeutung — also wird er ausgewiesen.
    """
    for operation in data.get("ops", ()):
        params = operation.get("params")
        if not isinstance(params, dict):
            continue
        for name, value in params.items():
            if _is_reference(value):
                raise ValidationError(
                    field=f"ops.{operation.get('id', '?')}.{name}",
                    detail=_(
                        "Diese ältere Datei enthält einen Wert, der in der neuen Version "
                        "wie ein Verweis auf ausgelagerte Daten aussieht."
                    ),
                    constraint="ambiguous_reference",
                    values={"value": str(value)[:60]},
                )
    return data
