"""Gemeinsame Grenzen für JSON aus fremden Vertrauensräumen.

Der Standardleser akzeptiert nicht endliche Zahlen und baut eine vollständig
verschachtelte Struktur auf, bevor der Aufrufer sie fachlich prüfen kann. Diese
Schicht ergänzt deshalb die Grenzen, die alle Netzwege gleichermaßen brauchen.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from typing import Any, Final

DEFAULT_MAX_BYTES: Final = 8 * 1024 * 1024
DEFAULT_MAX_DEPTH: Final = 64
DEFAULT_MAX_NODES: Final = 100_000
DEFAULT_MAX_COLLECTION_ITEMS: Final = 50_000


class StrictJsonError(ValueError):
    """Fremdes JSON überschreitet eine Grenze oder ist nicht eindeutig."""


def loads(
    payload: str | bytes | bytearray,
    *,
    max_bytes: int = DEFAULT_MAX_BYTES,
    max_depth: int = DEFAULT_MAX_DEPTH,
    max_nodes: int = DEFAULT_MAX_NODES,
    max_collection_items: int = DEFAULT_MAX_COLLECTION_ITEMS,
) -> Any:
    """Liest JSON mit Byte-, Struktur- und Zahlenbegrenzung.

    Doppelte Objektschlüssel werden abgewiesen: Zwei verschiedene Auslegungen
    derselben signierten oder autorisierten Nachricht wären keine sichere
    Grundlage für eine Entscheidung.
    """
    if min(max_bytes, max_depth, max_nodes, max_collection_items) < 1:
        raise ValueError("JSON-Grenzen müssen positiv sein")
    if isinstance(payload, str):
        try:
            raw = payload.encode("utf-8")
        except UnicodeError as problem:
            raise StrictJsonError("JSON enthält kein gültiges Unicode") from problem
        text = payload
    else:
        raw = bytes(payload)
        try:
            text = raw.decode("utf-8")
        except UnicodeError as problem:
            raise StrictJsonError("JSON ist nicht als UTF-8 kodiert") from problem
    if len(raw) > max_bytes:
        raise StrictJsonError("JSON überschreitet die Bytegrenze")

    def reject_constant(_value: str) -> None:
        raise StrictJsonError("JSON enthält keine endliche Zahl")

    def object_from_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        if len(pairs) > max_collection_items:
            raise StrictJsonError("JSON-Objekt überschreitet die Eintragsgrenze")
        value: dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise StrictJsonError("JSON enthält einen doppelten Objektschlüssel")
            value[key] = item
        return value

    try:
        value = json.loads(
            text,
            parse_constant=reject_constant,
            object_pairs_hook=object_from_pairs,
        )
    except StrictJsonError:
        raise
    except (RecursionError, UnicodeError, ValueError, json.JSONDecodeError) as problem:
        raise StrictJsonError("JSON ist nicht lesbar") from problem

    nodes = 0
    stack: list[tuple[Any, int]] = [(value, 1)]
    while stack:
        current, depth = stack.pop()
        nodes += 1
        if nodes > max_nodes:
            raise StrictJsonError("JSON überschreitet die Knotengrenze")
        if depth > max_depth:
            raise StrictJsonError("JSON überschreitet die Verschachtelungsgrenze")
        if isinstance(current, float) and not math.isfinite(current):
            raise StrictJsonError("JSON enthält keine endliche Zahl")
        if isinstance(current, str):
            try:
                current.encode("utf-8")
            except UnicodeError as problem:
                raise StrictJsonError("JSON enthält kein gültiges Unicode") from problem
            continue
        if isinstance(current, Mapping):
            if len(current) > max_collection_items:
                raise StrictJsonError("JSON-Objekt überschreitet die Eintragsgrenze")
            for key, item in current.items():
                stack.append((key, depth + 1))
                stack.append((item, depth + 1))
            continue
        if isinstance(current, Sequence) and not isinstance(current, (str, bytes, bytearray)):
            if len(current) > max_collection_items:
                raise StrictJsonError("JSON-Liste überschreitet die Eintragsgrenze")
            stack.extend((item, depth + 1) for item in current)
    return value
