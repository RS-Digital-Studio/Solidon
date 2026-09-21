"""Ausdrücklich gewählte Kanten **vor** dem Verbrauchercache binden (§21.3, P1.4c).

Ein Kantenfeld (``kind="edges"``) trägt Schlüssel, und ein Schlüssel ist eine
gerundete Lage (``geom.edges.edge_key``): Zwei Kanten können denselben tragen
— die zwei Ränder eines Spalts von vier Tausendstel Millimetern, oder ein
alter Rohrschlüssel, der beide konzentrischen Ränder trifft. Bis zum
20.09.2026 hielt die Operation dort mit einem Satz an. Jetzt fragt die
**Auswertung** den Kunden, und zwar an drei Stellen richtig:

* **Vor dem Cache.** ``evaluate`` liest den Ergebniscache vor dem Aufruf der
  Operation; eine Frage erst *in* der Operation wäre bei warmem Cache nie
  gestellt worden. Und eine andere Antwort ist eine andere Geometrie des
  Verbrauchers — deshalb geht der Fingerabdruck der gebundenen Auswahl in
  dessen Schlüssel (``EdgeBinding.context``), nicht bloß der Eingangshash.
* **Am aktuellen Eingang.** Gefragt wird an den Kanten, die die Operation
  gleich sieht — am exakten Körper die Topologie, am Netz die Züge, und bei
  ``edges_on_mesh`` immer das Netz —, und die Antwort erreicht sie als
  Indizes in genau diesen Raum (``OpContext.bound_edges``). Sie löst keinen
  Schlüssel ein zweites Mal auf.
* **Einmal.** Eine Wahl zwischen zwei Kanten mit demselben aktuellen
  Schlüssel liegt als Kantenantwort in ``Operation.matches`` (Domäne
  ``edge-answer:``, gebunden an Eingang, Feld, Schlüsselbündel und die
  Fassung des Eingangs). Eine Wahl, deren Kante einen **eindeutigen**
  aktuellen Schlüssel hat — der Aliasfall —, wird zum Parameter: Das Bündel
  bekommt den eindeutigen Schlüssel, über denselben Antwortenweg wie die
  Einheitenfrage (``OpResult.answered``).

Was hier nicht steht: keine zweite Kopierprimitive, keine zweite
Schlüsselauflösung und kein zweiter Frageweg — ``ask`` und ``announce``
sind die der Auswertung.
"""

from __future__ import annotations

import dataclasses
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from app.core.errors import AmbiguityError
from app.core.geom.edges import (
    EdgeKernel,
    described_by_key,
    edge_fingerprint,
    edge_key,
    edges_in_kernel,
    indices_in_kernel,
    points_in_kernel,
    same_edge,
    wanted,
)
from app.core.perceive.match_decisions import MAPPING_NO_LONGER_VALID
from app.core.perceive.match_records import edge_answer_key, validate_edge_answer
from app.core.registry import OperationSpec
from app.core.types import AskFn, ObjectId, Operation, ParamSpec, SceneObject, Vec3
from app.i18n import tr


@dataclasses.dataclass(frozen=True, slots=True)
class EdgeTarget:
    """Ein Kandidat einer Kantenfrage, wie ihn Dialog und Ansicht zeigen.

    Reine Darstellung, keine zweite Geometrieeinpassung: ``points`` ist der
    Zug, wie ihn die Ansicht ohnehin für die Kantenauswahl abtastet
    (``brep.edit.edge_points`` beziehungsweise ``MeshEdge.points``), die
    übrigen Felder sind die Anzeigefakten von ``ui.labels.edge_label``. Kein
    nativer Handle, kein Index, kein Schlüssel — das ``token`` gilt für diese
    eine Frage und wird nie gespeichert.
    """

    token: str
    object_id: ObjectId
    points: tuple[Vec3, ...]
    middle: Vec3
    length: float
    upright: bool
    flat: bool


AnnounceEdges = Callable[[tuple[EdgeTarget, ...]], None]


@dataclasses.dataclass(frozen=True, slots=True)
class EdgeBinding:
    """Was die Bindung der Auswertung zurückgibt — je Kantenfeld."""

    selections: Mapping[str, tuple[int, ...]]
    """Feld → Indizes im Kantenraum des Kerns; geht als ``bound_edges`` in den
    ``OpContext``."""
    context: Mapping[str, Any]
    """``#<Feld>`` → Fingerabdrücke der gebundenen Kanten; geht in den
    Operationsschlüssel des Verbrauchers."""
    records: Mapping[str, dict[str, Any]]
    """Neue Kantenantworten für ``Operation.matches`` — veröffentlicht erst,
    wenn die Operation vollständig gelungen ist."""
    answers: Mapping[str, str]
    """Feld → neu geschriebenes Schlüsselbündel (Aliasfall), für
    ``EvaluationResult.answers``."""


NO_BINDING = EdgeBinding({}, {}, {}, {})


def bind_edges(
    spec: OperationSpec,
    operation: Operation,
    resolved: Mapping[str, Any],
    inputs: Sequence[SceneObject],
    hashes: Mapping[ObjectId, str],
    *,
    ask: AskFn,
    announce: AnnounceEdges | None,
    check_cancelled: Callable[[], None],
) -> EdgeBinding:
    """Löst jedes aktive Kantenfeld am ersten Eingang auf und fragt bei Kollisionen.

    Aktiv ist ein Feld, wenn sein ``depends_on`` erfüllt ist — für die drei
    Kantenoperationen also bei der Auswahl „einzeln" — und es Schlüssel trägt.
    Alles andere bleibt beim Gruppenweg der Operation.
    """
    selections: dict[str, tuple[int, ...]] = {}
    context: dict[str, Any] = {}
    records: dict[str, dict[str, Any]] = {}
    answers: dict[str, str] = {}
    for entry in spec.params.spec():
        if entry.kind != "edges" or not inputs:
            continue
        keys = _keys_of(resolved.get(entry.name))
        if not keys or not _active(entry, resolved):
            continue
        source = inputs[0]
        check_cancelled()
        kernel, entries = edges_in_kernel(source.mesh, source.kind, on_mesh=spec.edges_on_mesh)
        check_cancelled()
        described = described_by_key(entries)
        colliding = {
            key: list(described[key])
            for key in dict.fromkeys(keys)
            if len(described.get(key, ())) > 1
        }
        bundle = list(keys)
        usable = entries
        if colliding:
            scope = hashes[source.id]
            decisions = resolve_edge_answer(
                operation.matches.get(edge_answer_key(source.id, entry.name, bundle)),
                source.id,
                entry.name,
                bundle,
                scope,
                colliding,
                check_cancelled=check_cancelled,
            )
            newly_chosen = decisions is None
            if decisions is None:
                decisions = _ask_for_each(
                    source,
                    kernel,
                    colliding,
                    ask=ask,
                    announce=announce,
                    check_cancelled=check_cancelled,
                )
            # Der Aliasfall wird zum Parameter: Trägt die gewählte Kante einen
            # eindeutigen aktuellen Schlüssel, steht der von jetzt an im Bündel,
            # und die Frage stellt sich nie wieder — ohne Antwortdatensatz.
            remaining: dict[str, list[Any]] = {}
            for key, chosen in decisions.items():
                current = edge_key(chosen)
                if current != key and len(described.get(current, ())) == 1:
                    bundle = [current if name == key else name for name in bundle]
                else:
                    remaining[key] = colliding[key]
            if bundle != list(keys):
                answers[entry.name] = " ".join(bundle)
            if remaining and newly_chosen:
                records[edge_answer_key(source.id, entry.name, bundle)] = edge_answer_record(
                    source.id,
                    entry.name,
                    bundle,
                    scope,
                    remaining,
                    {key: decisions[key] for key in remaining},
                    check_cancelled=check_cancelled,
                )
            dropped = {
                id(candidate)
                for key, matches in colliding.items()
                for candidate in matches
                if candidate is not decisions[key]
            }
            usable = [candidate for candidate in entries if id(candidate) not in dropped]
        # Dieselbe Auflösung wie in der Operation — fehlende Schlüssel und
        # die leere Wahl tragen dieselben Sätze; nur die Kollision ist weg.
        chosen_all = wanted(usable, _choice_of(entry, resolved), bundle)
        check_cancelled()
        selections[entry.name] = indices_in_kernel(kernel, source.mesh, chosen_all, entries)
        context[f"#{entry.name}"] = [edge_fingerprint(candidate) for candidate in chosen_all]
    if not selections:
        return NO_BINDING
    return EdgeBinding(selections, context, records, answers)


def _keys_of(value: object) -> tuple[str, ...]:
    """Das Schlüsselbündel, wie ``kind="edges"`` es ablegt: Text mit Leerzeichen."""
    if not isinstance(value, str):
        return ()
    return tuple(part for part in value.split() if part)


def _active(entry: ParamSpec, resolved: Mapping[str, Any]) -> bool:
    """Ob das Feld wirkt — dieselbe Auskunft, nach der der Dialog es ausgraut."""
    if entry.depends_on is None:
        return True
    field, values = entry.depends_on
    return resolved.get(field) in values


def _choice_of(entry: ParamSpec, resolved: Mapping[str, Any]) -> Any:
    """Die Gruppenauswahl, an der das Kantenfeld hängt — sonst gilt „einzeln"."""
    if entry.depends_on is None:
        return "named"
    return resolved.get(entry.depends_on[0], "named")


def _ask_for_each(
    source: SceneObject,
    kernel: EdgeKernel,
    colliding: Mapping[str, Sequence[Any]],
    *,
    ask: AskFn,
    announce: AnnounceEdges | None,
    check_cancelled: Callable[[], None],
) -> dict[str, Any]:
    """Je kollidierendem Schlüssel eine Frage; die Kandidaten leuchten in der Ansicht."""
    decisions: dict[str, Any] = {}
    for key, matches in colliding.items():
        check_cancelled()
        targets = tuple(
            EdgeTarget(
                token=f"{key}#{number}",
                object_id=source.id,
                points=points_in_kernel(kernel, source.mesh, candidate),
                middle=tuple(float(value) for value in candidate.middle),  # type: ignore[arg-type]
                length=float(candidate.length),
                upright=bool(candidate.upright),
                flat=bool(candidate.flat),
            )
            for number, candidate in enumerate(matches, start=1)
        )
        tokens = [target.token for target in targets]
        question = tr(
            "Körper „{object}“: Die gewählte Kante {key} ist nicht eindeutig — {count} Kanten "
            "tragen diesen Schlüssel. Wählen Sie die gemeinte Kante."
        ).format(object=str(source.name), key=key, count=len(matches))
        try:
            if announce is not None:
                announce(targets)
            chosen = ask(question, tokens)
            check_cancelled()
        finally:
            if announce is not None:
                announce(())
        if chosen not in tokens:
            raise AmbiguityError(MAPPING_NO_LONGER_VALID)
        decisions[key] = matches[tokens.index(chosen)]
    return decisions


def resolve_edge_answer(
    saved: Mapping[str, Any] | None,
    object_id: ObjectId,
    field: str,
    keys: Sequence[str],
    scope: str,
    colliding: Mapping[str, Sequence[Any]],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> dict[str, Any] | None:
    """Eine gespeicherte Kantenantwort gilt ganz oder gar nicht.

    Sie gilt nur für dieselbe Fassung des Eingangs (``scope``), dieselben
    kollidierenden Schlüssel und dieselbe Kandidatenzahl je Schlüssel, und
    jeder gespeicherte Fingerabdruck muss genau **eine** aktuelle Kante
    treffen — verschiedene Fingerabdrücke verschiedene. Fehlt eines davon,
    ist die Antwort keine, und die Frage wird neu gestellt (Regel 21).
    """
    if saved is None:
        return None
    try:
        validate_edge_answer(
            edge_answer_key(object_id, field, keys),
            saved,
            (object_id,),
            check_cancelled=check_cancelled,
        )
    except ValueError:
        return None
    if saved["scope"] != scope or set(saved["candidates"]) != set(colliding):
        return None
    decisions: dict[str, Any] = {}
    for key, matches in colliding.items():
        if check_cancelled is not None:
            check_cancelled()
        stored = saved["candidates"][key]
        if len(stored) != len(matches):
            return None
        found: list[Any] = []
        for fingerprint in stored:
            hits = [candidate for candidate in matches if same_edge(fingerprint, candidate)]
            if len(hits) != 1 or any(hits[0] is earlier for earlier in found):
                return None
            found.append(hits[0])
        decisions[key] = found[saved["decisions"][key]["candidate"]]
    return decisions


def edge_answer_record(
    object_id: ObjectId,
    field: str,
    keys: Sequence[str],
    scope: str,
    colliding: Mapping[str, Sequence[Any]],
    decisions: Mapping[str, Any],
    *,
    check_cancelled: Callable[[], None] | None = None,
) -> dict[str, Any]:
    """Die Kantenantwort als reiner JSON-Datensatz — geprüft, bevor sie gespeichert wird."""
    record: dict[str, Any] = {
        "object_id": object_id,
        "field": field,
        "keys": list(keys),
        "scope": scope,
        "candidates": {
            key: [edge_fingerprint(candidate) for candidate in matches]
            for key, matches in colliding.items()
        },
        "decisions": {
            key: {
                "candidate": next(
                    index
                    for index, candidate in enumerate(colliding[key])
                    if candidate is decisions[key]
                )
            }
            for key in colliding
        },
    }
    try:
        validate_edge_answer(
            edge_answer_key(object_id, field, keys),
            record,
            (object_id,),
            check_cancelled=check_cancelled,
        )
    except ValueError as error:
        raise AmbiguityError(MAPPING_NO_LONGER_VALID) from error
    return record
