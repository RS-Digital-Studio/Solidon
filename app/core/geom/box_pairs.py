"""Hüllquaderpaare zwischen zwei Dreiecksmengen, über zwei Bäume gesucht (RM-381).

Die Selbstdurchdringung eines Netzes zählt Paare **einer** Menge über
Sweep-and-Prune (``intersections``). Zwischen zwei Mengen — zwei Teilen eines
Körpers (``repair.parts_that_cross``), einem Werkzeug und einer Schale
(``boolean._meets_the_shells``) — trägt der Sweep nicht: Entlang einer Achse
zählte er jedes Dreieck des einen Teils gegen alles im Bereich der längsten
Hülle des anderen. Hier stehen beide Mengen in je einem Hüllquaderbaum
(:class:`BoxTree`), und :func:`box_pairs_between` steigt in beiden zugleich ab.

Gerechnet wird aus Minimum, Maximum, Vergleichen und ``floor`` — kein BLAS,
keine Summe (RM-187): Dieselben Eingänge ergeben auf jeder Maschine dieselben
Paare in derselben Folge.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Final

import numpy as np

from app.core.types import CancelToken
from app.core.units import EPS_GEOM

#: Wie viele Knotenpaare der Abstieg in :func:`box_pairs_between` auf einmal als
#: Feld prüft. Eine größere Front wird geteilt und der Reihe nach abgearbeitet:
#: Der Speicher bleibt klein, und ein Treffer im ersten Stück endet früh.
TREE_PAIR_CHUNK: Final = 32_768

#: Wie viele Dreieckspaare :func:`box_pairs_between` höchstens gesammelt
#: herausgibt — so viele prüft der Aufrufer auf einmal genau. Der erste Block
#: hat :data:`TREE_PAIR_FIRST_BLOCK` Paare, jeder weitere doppelt so viele bis
#: hierher: Stecken zwei Teile ineinander, kommt der Treffer nach wenigen
#: genauen Prüfungen; sonst lohnt sich der Feldaufruf.
TREE_PAIR_BLOCK: Final = 8_192
TREE_PAIR_FIRST_BLOCK: Final = 256

#: Bits je Achse des Schlüssels in :func:`_curve_order`: dreimal 21 passen in 63.
_CURVE_BITS: Final = 21
_CURVE_TOP: Final = float((1 << _CURVE_BITS) - 1)


def _spread_bits(cells: np.ndarray) -> np.ndarray:
    """Die unteren 21 Bit jeder Zahl so gespreizt, dass je zwei Nullbits dazwischen stehen."""
    spread = cells.astype(np.uint64) & np.uint64(0x1FFFFF)
    spread = (spread | (spread << np.uint64(32))) & np.uint64(0x1F00000000FFFF)
    spread = (spread | (spread << np.uint64(16))) & np.uint64(0x1F0000FF0000FF)
    spread = (spread | (spread << np.uint64(8))) & np.uint64(0x100F00F00F00F00F)
    spread = (spread | (spread << np.uint64(4))) & np.uint64(0x10C30C30C30C30C3)
    spread = (spread | (spread << np.uint64(2))) & np.uint64(0x1249249249249249)
    return spread


def _curve_order(low: np.ndarray, high: np.ndarray) -> np.ndarray:
    """Die Hüllquader entlang einer Z-Kurve durch ihre Mitten geordnet.

    Nachbarn auf der Kurve liegen nahe beieinander, und darauf baut
    :class:`BoxTree` seine Knoten. Die Zellnummer entsteht elementweise aus
    Grundrechenarten und ``floor``; Gleichstand löst die stabile Sortierung
    nach der Eingangsreihenfolge — auf jeder Maschine dieselbe Folge.
    """
    centre = (low + high) * 0.5
    origin = low.min(axis=0)
    extent = high.max(axis=0) - origin
    scale = np.where(extent > 0.0, extent, 1.0)
    cells = np.floor((centre - origin) / scale * _CURVE_TOP)
    # Eine nicht endliche Ecke hat keinen Platz auf der Kurve; sie geht an den
    # Anfang und überdeckt ohnehin nichts.
    cells = np.clip(np.where(np.isfinite(cells), cells, 0.0), 0.0, _CURVE_TOP).astype(np.int64)
    key = (
        _spread_bits(cells[:, 0])
        | (_spread_bits(cells[:, 1]) << np.uint64(1))
        | (_spread_bits(cells[:, 2]) << np.uint64(2))
    )
    return np.argsort(key, kind="stable")


def boxes_meet(
    first_low: np.ndarray, first_high: np.ndarray, second_low: np.ndarray, second_high: np.ndarray
) -> np.ndarray:
    """Je Zeile, ob sich zwei Hüllquader bis auf ``EPS_GEOM`` überdecken.

    Dieselbe Bedingung wie das Achsfilter der übrigen Suchen: Was hier nicht
    zusammenkommt, schneidet sich auch für :func:`crossing_pairs` nicht.
    """
    return np.asarray(
        np.all(first_low <= second_high + EPS_GEOM, axis=1)
        & np.all(second_low <= first_high + EPS_GEOM, axis=1)
    )


class BoxTree:
    """Ein Hüllquaderbaum über einer Auswahl von Dreiecken — vollständig binär, ohne Zeiger.

    Die Blätter sind die Dreiecke selbst, entlang einer Z-Kurve durch ihre
    Mitten geordnet (:func:`_curve_order`) und auf eine Zweierpotenz
    aufgefüllt. Knoten ``k`` hat die Kinder ``2k`` und ``2k + 1``, die Wurzel
    ist ``1``, Blatt ``i`` der Knoten ``width + i``. Jeder Knoten trägt die
    Hülle seiner Dreiecke; aufgefüllte Knoten tragen eine leere Hülle (unten
    ``+inf``, oben ``-inf``) und überdecken nie etwas.

    Gebaut wird aus Minimum und Maximum, ohne Summe: Eine Hülle ist auf jeder
    Maschine bitgleich, und weil jede die ihrer Kinder enthält, verliert der
    Abstieg kein Paar, das sich überdeckt. Je Knoten liegen unten und oben
    samt ``EPS_GEOM`` in einer Zeile (``box``): Der Abstieg liest zwei Zeilen
    je Paar statt vier Felder, und der Zuschlag ist einmal gerechnet.
    """

    __slots__ = ("box", "items", "size", "width")

    def __init__(self, items: np.ndarray, low: np.ndarray, high: np.ndarray) -> None:
        """``items`` nennt die Dreiecke, ``low``/``high`` sind die Hüllquader aller Dreiecke."""
        chosen = np.asarray(items, dtype=np.int64)
        own_low, own_high = low[chosen], high[chosen]
        order = _curve_order(own_low, own_high) if len(chosen) > 1 else np.arange(len(chosen))
        width = 1 << max(len(chosen) - 1, 0).bit_length()
        node_low = np.full((2 * width, 3), np.inf)
        node_high = np.full((2 * width, 3), -np.inf)
        node_low[width : width + len(chosen)] = own_low[order]
        node_high[width : width + len(chosen)] = own_high[order]
        first = width // 2
        while first:
            node_low[first : 2 * first] = np.minimum(
                node_low[2 * first : 4 * first : 2], node_low[2 * first + 1 : 4 * first : 2]
            )
            node_high[first : 2 * first] = np.maximum(
                node_high[2 * first : 4 * first : 2], node_high[2 * first + 1 : 4 * first : 2]
            )
            first //= 2
        self.items = chosen[order]
        """Je Blatt das Dreieck, in der Nummerierung des Eingangs."""
        self.width = width
        self.box = np.concatenate((node_low, node_high + EPS_GEOM), axis=1)
        """Je Knoten ``(x, y, z)`` unten und ``(x, y, z)`` oben plus ``EPS_GEOM``."""
        # Leer ist ``-inf - +inf = -inf``: kein ungültiger Wert, und kleiner als
        # jeder echte Knoten.
        self.size = (node_high - node_low).max(axis=1)
        """Die längste Kante je Knotenhülle — der größere Knoten wird geteilt."""


def _nodes_meet(first: np.ndarray, second: np.ndarray) -> np.ndarray:
    """Je Zeile, ob sich zwei Knotenhüllen aus :attr:`BoxTree.box` überdecken.

    Dieselbe Bedingung wie :func:`boxes_meet`, spaltenweise: Sechs
    Vergleiche über einzelne Spalten kosten halb so viel wie zwei ``all``
    über ganze Felder.
    """
    return np.asarray(
        (first[:, 0] <= second[:, 3])
        & (first[:, 1] <= second[:, 4])
        & (first[:, 2] <= second[:, 5])
        & (second[:, 0] <= first[:, 3])
        & (second[:, 1] <= first[:, 4])
        & (second[:, 2] <= first[:, 5])
    )


def box_pairs_between(
    one: BoxTree,
    other: BoxTree,
    cancelled: CancelToken | None = None,
    *,
    block: int = TREE_PAIR_BLOCK,
) -> Iterator[tuple[np.ndarray, np.ndarray]]:
    """Blockweise jedes Paar aus ``one`` und ``other``, dessen Hüllquader sich überdecken.

    **Vollständig und ohne Sweep.** Bis RM-381 zählte die Vorfrage über
    Teilegrenzen (``repair.parts_that_cross``) entlang einer Achse jedes
    Dreieck des einen Teils gegen alles im Bereich der *längsten* Hülle des
    anderen: Am Besenhalter mit seinen langen Splitterdreiecken waren das
    55,7 Millionen Grobkandidaten für 14 058 Paare, deren Hüllquader sich
    wirklich überdecken — 3,9 s je Boolescher Operation. Auch eine Ebene
    reicht nicht: In der besten Draufsicht überdecken sich dort noch
    1,85 Millionen. Hier steigen zwei Bäume gemeinsam ab, je Schritt teilt sich
    der größere Knoten, und nur Knotenpaare, deren Hüllen sich überdecken,
    gehen weiter. Heraus kommen genau die Paare mit überdeckenden Hüllquadern
    (:func:`boxes_meet`), jedes einmal, in der Nummerierung des Eingangs.

    Abgebrochen wird je Frontstück (``cancelled``). Die Blöcke wachsen von
    :data:`TREE_PAIR_FIRST_BLOCK` auf ``block``; jeder ist voll, nur der letzte
    kürzer. Die Reihenfolge hängt nur an den Eingängen; wer beim ersten
    Treffer aufhört, findet auf jeder Maschine denselben.
    """
    if not _nodes_meet(one.box[1:2], other.box[1:2])[0]:
        return
    stack = [np.array([[1, 1]], dtype=np.int64)]
    firsts: list[np.ndarray] = []
    seconds: list[np.ndarray] = []
    held = 0
    size = min(TREE_PAIR_FIRST_BLOCK, block)
    while stack:
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        pairs = stack.pop()
        nodes, partners = pairs[:, 0], pairs[:, 1]
        leaf_node = nodes >= one.width
        leaf_partner = partners >= other.width
        both = leaf_node & leaf_partner
        if np.any(both):
            firsts.append(one.items[nodes[both] - one.width])
            seconds.append(other.items[partners[both] - other.width])
            held += int(np.count_nonzero(both))
            if held >= size:
                first, second = np.concatenate(firsts), np.concatenate(seconds)
                start = 0
                while len(first) - start >= size:
                    yield first[start : start + size], second[start : start + size]
                    start += size
                    size = min(2 * size, block)
                firsts, seconds, held = [first[start:]], [second[start:]], len(first) - start
        rest = np.flatnonzero(~both)
        if not len(rest):
            continue
        nodes, partners = nodes[rest], partners[rest]
        # Geteilt wird der größere Knoten; ein Blatt teilt sich nicht.
        split = ~leaf_node[rest] & (leaf_partner[rest] | (one.size[nodes] >= other.size[partners]))
        kept = ~split
        child_nodes = np.concatenate(
            (2 * nodes[split], 2 * nodes[split] + 1, nodes[kept], nodes[kept])
        )
        child_partners = np.concatenate(
            (partners[split], partners[split], 2 * partners[kept], 2 * partners[kept] + 1)
        )
        meet = _nodes_meet(one.box[child_nodes], other.box[child_partners])
        if not np.any(meet):
            continue
        children = np.stack((child_nodes[meet], child_partners[meet]), axis=1)
        # Rückwärts aufgelegt, damit das erste Stück als nächstes drankommt.
        for start in reversed(range(0, len(children), TREE_PAIR_CHUNK)):
            stack.append(children[start : start + TREE_PAIR_CHUNK])
    if held:
        yield np.concatenate(firsts), np.concatenate(seconds)
