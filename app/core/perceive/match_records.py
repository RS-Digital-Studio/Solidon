"""Reine Struktur gespeicherter Zuordnungsantworten (§15.7, §21.3).

Projektleser und Wiedererkennung benutzen dieselbe Grenze. Die Prüfung
liest keine Geometrie und ergänzt weder Lage noch Maße historischer Daten.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Collection, Iterable, Mapping


def group_key(object_id: str, old_ids: Iterable[str]) -> str:
    """Bezeichnet einen Körper und die vollständige alte Anspruchsmenge."""
    return "group:" + json.dumps(
        [object_id, sorted(old_ids)], ensure_ascii=False, separators=(",", ":")
    )


def _finite_number(value: object) -> bool:
    """JSON-Zahlen sind endlich; boolesche Werte sind keine Zahlen."""
    if isinstance(value, bool) or not isinstance(value, int | float):
        return False
    try:
        return math.isfinite(value)
    except OverflowError:
        return False


def _vector(value: object) -> bool:
    """Ein gespeicherter Vektor trägt genau drei endliche Komponenten."""
    return (
        isinstance(value, list | tuple)
        and len(value) == 3
        and all(_finite_number(component) for component in value)
    )


def valid_fingerprint(value: object, legacy: bool = False) -> bool:
    """Prüft den vorhandenen Abdruck, ohne eine fehlende Lage zu erfinden.

    Alte Antworten dürfen Achse, Rohmaß oder Richtungsflag auslassen; deren
    historische Vorgaben bleiben beim Leser. Neue Gruppen tragen alle Felder.
    ``diameter`` ist das unveränderte Rohmaß aus ``feature_vector[6]``, auch
    wenn dieses bei einer Fläche deren Flächeninhalt beschreibt.
    """
    if not isinstance(value, Mapping):
        return False
    fields = {"kind", "relative", "axis", "diameter", "directional"}
    if not legacy and set(value) != fields:
        return False
    if not isinstance(value.get("kind"), str) or not _vector(value.get("relative")):
        return False
    if "axis" in value and not _vector(value["axis"]):
        return False
    if "diameter" in value and not _finite_number(value["diameter"]):
        return False
    return "directional" not in value or isinstance(value["directional"], bool)


def _sorted_names(value: object, check_cancelled: Callable[[], None] | None) -> bool:
    """Ansprüche sind vollständig, sortiert und ohne doppelte Kennungen."""
    if not isinstance(value, list) or not value:
        return False
    previous: str | None = None
    for name in value:
        if check_cancelled is not None:
            check_cancelled()
        if not isinstance(name, str) or (previous is not None and name <= previous):
            return False
        previous = name
    return True


def validate_group(
    key: str,
    record: object,
    outputs: Collection[str],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> None:
    """Verlangt eine vollständige, injektive Entscheidung für einen Ausgabekörper."""
    if check_cancelled is not None:
        check_cancelled()
    if not isinstance(record, Mapping) or set(record) != {
        "object_id",
        "old_ids",
        "candidates",
        "decisions",
    }:
        raise ValueError("group")
    object_id = record["object_id"]
    old_ids = record["old_ids"]
    if not isinstance(object_id, str) or object_id not in outputs:
        raise ValueError("object_id")
    if not _sorted_names(old_ids, check_cancelled):
        raise ValueError("old_ids")
    if key != group_key(object_id, old_ids):
        raise ValueError("key")
    candidates = record["candidates"]
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("candidates")
    owners = set(old_ids)
    claimed: set[str] = set()
    for candidate in candidates:
        if check_cancelled is not None:
            check_cancelled()
        if not isinstance(candidate, Mapping) or set(candidate) != {"fingerprint", "claims"}:
            raise ValueError("candidate")
        if not valid_fingerprint(candidate["fingerprint"]):
            raise ValueError("fingerprint")
        claims = candidate["claims"]
        if not _sorted_names(claims, check_cancelled) or not set(claims) <= owners:
            raise ValueError("claims")
        claimed.update(claims)
    if claimed != owners:
        raise ValueError("claims")
    decisions = record["decisions"]
    if not isinstance(decisions, Mapping) or set(decisions) != owners:
        raise ValueError("decisions")
    selected: set[int] = set()
    for old_id, decision in decisions.items():
        if check_cancelled is not None:
            check_cancelled()
        if not isinstance(decision, Mapping):
            raise ValueError("decision")
        if set(decision) == {"not_carried"} and decision["not_carried"] is True:
            continue
        if set(decision) != {"candidate"}:
            raise ValueError("decision")
        index = decision["candidate"]
        if (
            isinstance(index, bool)
            or not isinstance(index, int)
            or not 0 <= index < len(candidates)
        ):
            raise ValueError("candidate_index")
        if index in selected or old_id not in candidates[index]["claims"]:
            raise ValueError("candidate_claim")
        selected.add(index)
    if check_cancelled is not None:
        check_cancelled()


def validate_matches(
    records: object,
    outputs: Collection[str],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> None:
    """Prüft neue Gruppen und erhält lesbare, gegebenenfalls unbrauchbare Altabdrücke."""
    if check_cancelled is not None:
        check_cancelled()
    if not isinstance(records, Mapping):
        raise ValueError("matches")
    for key, record in records.items():
        if check_cancelled is not None:
            check_cancelled()
        if key == "legacy":
            if not isinstance(record, Mapping):
                raise ValueError("legacy")
            for name, value in record.items():
                if check_cancelled is not None:
                    check_cancelled()
                if not isinstance(name, str) or not isinstance(value, Mapping):
                    raise ValueError("legacy")
        elif isinstance(key, str):
            validate_group(key, record, outputs, check_cancelled=check_cancelled)
        else:
            raise ValueError("key")
    if check_cancelled is not None:
        check_cancelled()
