"""Reine Struktur gespeicherter Zuordnungsantworten (§15.7, §21.3).

Projektleser und Wiedererkennung benutzen dieselbe Grenze. Die Prüfung
liest keine Geometrie und ergänzt weder Lage noch Maße historischer Daten.
"""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Collection, Iterable, Mapping, Sequence

#: Die Domäne einer Netzantwort: Zuordnung neu erkannter Merkmale (§21.3).
GROUP_DOMAIN = "group"
#: Die Domäne einer nativen Neuwahl: Der Kunde hat am umgebauten exakten
#: Körper gewählt, welche aktuelle Fläche einen alten Bezug fortführt. Sie
#: trägt zusätzlich einen ``scope`` — die Fassung des Erzeugers, für die die
#: Wahl gilt — und wird nie aus einer Netzantwort erzeugt.
NATIVE_DOMAIN = "native-group"
#: Die Domäne einer Kantenantwort: Der Kunde hat für einen **Verbraucher**
#: gewählt, welche von mehreren Kanten mit demselben Schlüssel gemeint ist. Sie
#: hängt am Eingang der Operation, nicht an ihrer Ausgabe — am Körper, dem
#: Feld, dem vollständigen Schlüsselbündel und der Fassung dieses Eingangs
#: (``scope``, sein Objekthash). Die Auswertung liest sie vor dem Cache
#: (``scene.edge_binding``).
EDGE_DOMAIN = "edge-answer"


def group_key(object_id: str, old_ids: Iterable[str], *, domain: str = GROUP_DOMAIN) -> str:
    """Bezeichnet Domäne, Körper und die vollständige alte Anspruchsmenge."""
    if domain not in (GROUP_DOMAIN, NATIVE_DOMAIN):
        raise ValueError("domain")
    return f"{domain}:" + json.dumps(
        [object_id, sorted(old_ids)], ensure_ascii=False, separators=(",", ":")
    )


def edge_answer_key(object_id: str, field: str, keys: Sequence[str]) -> str:
    """Bezeichnet Eingangskörper, Kantenfeld und das Schlüsselbündel **in seiner Reihenfolge**.

    Ein anderes Bündel — eine Kante mehr, eine andere Einzelwahl — ist eine
    andere Frage; eine alte Antwort überschreibt sie nie.
    """
    return f"{EDGE_DOMAIN}:" + json.dumps(
        [object_id, field, list(keys)], ensure_ascii=False, separators=(",", ":")
    )


def domain_of(key: str) -> str | None:
    """Die Domäne eines gespeicherten Schlüssels — oder nichts bei fremder Form."""
    for domain in (GROUP_DOMAIN, NATIVE_DOMAIN, EDGE_DOMAIN):
        if key.startswith(f"{domain}:"):
            return domain
    return None


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
    """Verlangt eine vollständige, injektive Entscheidung für einen Ausgabekörper.

    Eine native Neuwahl (``native-group:``) trägt zusätzlich ihren ``scope``;
    eine Netzgruppe (``group:``) trägt keinen. Beide Formen sind strikt: Ein
    Netzdatensatz mit Scope und ein nativer ohne sind keine gültigen Antworten,
    denn dann wüsste niemand, für welche Fassung die Wahl gelten soll.
    """
    if check_cancelled is not None:
        check_cancelled()
    domain = domain_of(key)
    if domain is None or domain == EDGE_DOMAIN:
        raise ValueError("key")
    fields = {"object_id", "old_ids", "candidates", "decisions"}
    if domain == NATIVE_DOMAIN:
        fields.add("scope")
    if not isinstance(record, Mapping) or set(record) != fields:
        raise ValueError("group")
    object_id = record["object_id"]
    old_ids = record["old_ids"]
    if not isinstance(object_id, str) or object_id not in outputs:
        raise ValueError("object_id")
    if not _sorted_names(old_ids, check_cancelled):
        raise ValueError("old_ids")
    if key != group_key(object_id, old_ids, domain=domain):
        raise ValueError("key")
    if domain == NATIVE_DOMAIN and (not isinstance(record["scope"], str) or not record["scope"]):
        raise ValueError("scope")
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


def valid_edge_fingerprint(value: object) -> bool:
    """Der ungerundete Abdruck einer Kante: Mitte, Richtung, Ausdehnung, Länge."""
    if not isinstance(value, Mapping) or set(value) != {"middle", "direction", "extent", "length"}:
        return False
    if not _vector(value["middle"]) or not _vector(value["direction"]):
        return False
    return all(_finite_number(value[name]) and value[name] >= 0.0 for name in ("extent", "length"))


def _key_bundle(value: object, check_cancelled: Callable[[], None] | None) -> bool:
    """Ein Schlüsselbündel: nichtleer, jeder Eintrag ein nichtleerer Text, keiner doppelt."""
    if not isinstance(value, list) or not value:
        return False
    seen: set[str] = set()
    for name in value:
        if check_cancelled is not None:
            check_cancelled()
        if not isinstance(name, str) or not name or name in seen:
            return False
        seen.add(name)
    return True


def validate_edge_answer(
    key: str,
    record: object,
    inputs: Collection[str],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> None:
    """Verlangt eine vollständige Kantenantwort für einen **Eingangs**körper.

    Je kollidierendem Schlüssel mindestens zwei Kandidaten und genau eine
    Entscheidung darunter; der Datensatz nennt sein Feld, sein Bündel und die
    Fassung des Eingangs, für die er gilt. Der Projektleser prüft nur die
    Struktur — weder Geometrie noch ob das Feld im Register existiert; das
    tut die Auswertung, wenn sie den Datensatz liest.
    """
    if check_cancelled is not None:
        check_cancelled()
    if domain_of(key) != EDGE_DOMAIN:
        raise ValueError("key")
    fields = {"object_id", "field", "keys", "scope", "candidates", "decisions"}
    if not isinstance(record, Mapping) or set(record) != fields:
        raise ValueError("edge_answer")
    object_id, field, keys = record["object_id"], record["field"], record["keys"]
    if not isinstance(object_id, str) or object_id not in inputs:
        raise ValueError("object_id")
    if not isinstance(field, str) or not field:
        raise ValueError("field")
    if not _key_bundle(keys, check_cancelled):
        raise ValueError("keys")
    if key != edge_answer_key(object_id, field, keys):
        raise ValueError("key")
    if not isinstance(record["scope"], str) or not record["scope"]:
        raise ValueError("scope")
    candidates = record["candidates"]
    if not isinstance(candidates, Mapping) or not candidates:
        raise ValueError("candidates")
    for name, fingerprints in candidates.items():
        if check_cancelled is not None:
            check_cancelled()
        if name not in keys or not isinstance(fingerprints, list) or len(fingerprints) < 2:
            raise ValueError("candidates")
        if any(not valid_edge_fingerprint(entry) for entry in fingerprints):
            raise ValueError("fingerprint")
    decisions = record["decisions"]
    if not isinstance(decisions, Mapping) or set(decisions) != set(candidates):
        raise ValueError("decisions")
    for name, decision in decisions.items():
        if check_cancelled is not None:
            check_cancelled()
        if not isinstance(decision, Mapping) or set(decision) != {"candidate"}:
            raise ValueError("decision")
        index = decision["candidate"]
        if (
            isinstance(index, bool)
            or not isinstance(index, int)
            or not 0 <= index < len(candidates[name])
        ):
            raise ValueError("candidate_index")
    if check_cancelled is not None:
        check_cancelled()


def validate_matches(
    records: object,
    outputs: Collection[str],
    inputs: Collection[str] = (),
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> None:
    """Prüft neue Gruppen und Kantenantworten und erhält lesbare, gegebenenfalls
    unbrauchbare Altabdrücke.

    Gruppen gehören einem Ausgabekörper, Kantenantworten einem Eingangskörper
    — die Domäne im Schlüssel entscheidet, gegen welche Liste geprüft wird.
    """
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
        elif isinstance(key, str) and domain_of(key) == EDGE_DOMAIN:
            validate_edge_answer(key, record, inputs, check_cancelled=check_cancelled)
        elif isinstance(key, str):
            validate_group(key, record, outputs, check_cancelled=check_cancelled)
        else:
            raise ValueError("key")
    if check_cancelled is not None:
        check_cancelled()
