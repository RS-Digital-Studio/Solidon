"""Der Abschied eines Körpers mitten in einer Schleife über die Merker (FD-167).

``features._forget_body`` läuft als ``weakref.finalize`` aus der
Speicherbereinigung heraus: in jedem Faden, an jeder Stelle, auch unter dem
gehaltenen ``_MEMORY_LOCK``, denn das Schloss ist wiedereintrittsfähig. Lief
die Bereinigung in einer Schleife über einen Merker, schrumpfte ihr
Wörterbuch unter ihr — ``RuntimeError: dictionary changed size during
iteration``, beobachtet an ``forget_cache`` direkt nach einer Zuteilung in
``test_features.py::test_a_face_keeps_its_area_unrounded``; im
Erkennungsarbeiter ruft ``held_body`` dieselbe Funktion, gleich nachdem er den
alten Körper losgelassen hat.

Wann die Bereinigung läuft, bestimmt der Interpreter: seit CPython 3.12 an
einem Prüfpunkt der Auswertungsschleife — Rücksprung einer Schleife, Aufruf —,
sobald genug Objekte zugeteilt sind. Diese Tests legen den Zeitpunkt fest:
Die selbsttätige Bereinigung ist aus, und ein Objekt in der Schleife ruft
``gc.collect()`` — genau das, was die Bereinigung an dieser Stelle von selbst
tun kann. Der sterbende Körper hängt in einem Zyklus, wie jedes trimesh-Netz,
und ist bis dahin tot, aber nicht abgeräumt.
"""

from __future__ import annotations

import ast
import gc
import weakref
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import trimesh

from app.core.geom.mesh import MeshData
from app.core.perceive import features as module

ROOT = Path(__file__).resolve().parent.parent


class _CollectsOnRelease:
    """Ruft die Speicherbereinigung, sobald sein letzter Verweis fällt."""

    def __del__(self) -> None:
        gc.collect()


class _CollectsOnLookup(set[tuple[str, bytes]]):
    """Die Menge der schon geschickten Antworten, die bei jeder Frage aufräumt."""

    def __contains__(self, item: object) -> bool:
        gc.collect()
        return super().__contains__(item)


@contextmanager
def _collector_held() -> Iterator[None]:
    """Die Bereinigung läuft nur, wo der Test sie ruft."""
    enabled = gc.isenabled()
    gc.disable()
    try:
        yield
    finally:
        if enabled:
            gc.enable()


def _doomed(register: Callable[[trimesh.Trimesh], Any]) -> tuple[int, weakref.ref[Any]]:
    """Ein Körper mit Merker im Zyklus, ohne äußeren Verweis: tot, noch nicht abgeräumt."""
    body = trimesh.creation.box(extents=(1.0, 2.0, 3.0))
    body.metadata["self"] = body
    register(body)
    key = id(body)
    alive = weakref.ref(body)
    del body
    assert alive() is not None, "die Vorbedingung: nur die Bereinigung räumt den Körper ab"
    assert key in module._MEMORIES, "und er hat einen Merker"
    return key, alive


def _with_memory(body: trimesh.Trimesh) -> None:
    with module._MEMORY_LOCK:
        module._memory_of(body)


def test_forget_cache_outlives_a_farewell_in_its_sweep() -> None:
    """``forget_cache`` leert jeden Merker, auch wenn mittendrin ein Körper stirbt.

    Der Auslöser hängt im Schlüssel einer gebundenen Antwort des lebenden
    Körpers; sein letzter Verweis fällt, wenn die Schleife dessen Antworten
    leert, und die Bereinigung räumt dort den zweiten Körper ab.
    """
    module.forget_cache()
    with _collector_held():
        keeper = trimesh.creation.box(extents=(4.0, 5.0, 6.0))
        trigger = _CollectsOnRelease()
        assert module.remembered("surface_patch", keeper, [0], lambda: "Antwort", trigger) == (
            "Antwort"
        )
        del trigger
        key, alive = _doomed(_with_memory)

        module.forget_cache()

        assert alive() is None, "die Bereinigung lief in der Schleife"
        assert key not in module._MEMORIES, "der Abschied hat seinen Merker genommen"
        memory = module._MEMORIES[id(keeper)]
        assert not memory.answers and not memory.lineage.answers, "der lebende ist geleert"
        assert not module._SUPPORT_CACHE


def test_a_worker_hands_back_its_answers_while_a_body_says_farewell() -> None:
    """Der Arbeiter schickt seine Antworten über die Körpergrenze, auch wenn dabei einer stirbt.

    ``answered_ahead`` liest am Ende jede Ablage in ``_BY_GEOMETRY``; der
    Abschied eines Körpers nimmt daraus, was nur er hielt
    (``_release_geometric``) — ``OrderedDict mutated during iteration``.
    """
    module.forget_cache()
    token = b"fd167"
    with _collector_held():
        body = trimesh.creation.box(extents=(4.0, 5.0, 6.0))
        module._WORKER_BODY[0] = (token, body, MeshData(raw=body), _CollectsOnLookup())
        try:
            module._keep_across("fit_cone", body, b"lebend", "lebend")
            _key, alive = _doomed(
                lambda dying: module._keep_across("fit_cone", dying, b"tot", "tot")
            )
            task = SimpleNamespace(token=token, kind="classify", items=(), shapes=(), skin=None)

            answers = module.answered_ahead(dict, task)

            assert alive() is None, "die Bereinigung lief beim Einsammeln"
            assert answers["fit_cone"][b"lebend"] == "lebend"
            assert b"tot" not in module._BY_GEOMETRY["fit_cone"], "und nahm die Antwort des Toten"
        finally:
            module._WORKER_BODY[0] = None
            module.forget_cache()


#: Die Merker, aus denen ein Abschied nimmt (``_forget_body``, ``_drop_answers``,
#: ``_release_geometric``).
_FAREWELL_TOUCHES = frozenset(
    {
        "_MEMORIES",
        "_SUPPORT_CACHE",
        "_BY_GEOMETRY",
        "_DIGESTS",
        "_DERIVED_LINEAGES",
        "_GEOMETRY_HOLDERS",
    }
)


def _iterated_live(node: ast.expr) -> str | None:
    """Der Merker, über den ``node`` unmittelbar läuft — ``None`` bei einem Schnappschuss."""
    if (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr in {"items", "values", "keys"}
    ):
        node = node.func.value
    if isinstance(node, ast.Name) and node.id in _FAREWELL_TOUCHES:
        return node.id
    return None


def test_no_loop_runs_over_a_memory_a_farewell_changes() -> None:
    """Wer über einen dieser Merker läuft, läuft über einen Schnappschuss.

    Der Abschied kann an jedem Prüfpunkt der Schleife mitten hinein laufen;
    ``tuple(...)`` liest den Merker in C, ohne einen solchen Punkt. Der
    Wächter hält die Bauart von FD-167 im ganzen Modul fest.
    """
    source = ROOT / "app" / "core" / "perceive" / "features.py"
    tree = ast.parse(source.read_text(encoding="utf-8"))
    loops = [
        node.iter
        for node in ast.walk(tree)
        if isinstance(node, ast.For | ast.AsyncFor | ast.comprehension)
    ]
    assert loops, "der Wächter sieht Schleifen"
    live = [
        f"Zeile {node.lineno}: {name}"
        for node in loops
        if (name := _iterated_live(node)) is not None
    ]
    assert not live, live


def test_the_guard_sees_a_live_loop() -> None:
    """Gegenprobe: dieselbe Lesung findet die Schleife der ersten Fassung."""
    first = ast.parse("for memory in _MEMORIES.values():\n    pass\n").body[0]
    fixed = ast.parse("for memory in tuple(_MEMORIES.values()):\n    pass\n").body[0]
    assert isinstance(first, ast.For) and isinstance(fixed, ast.For)
    assert _iterated_live(first.iter) == "_MEMORIES"
    assert _iterated_live(fixed.iter) is None
