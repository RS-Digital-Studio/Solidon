"""Summen je Gruppe in einem Zug — Bit für Bit dieselben wie je Gruppe einzeln (P5, RM-592).

Die Erkennung summiert vieles je Facette, je Fleck, je Merkmal, und jede
Python-Schleife darüber kostet am großen Körper Sekunden. ``np.add.reduceat``
bündelt das, addiert aber in anderer Folge als ``sum``: Über 3 000 zufällige
Gruppen wichen 1 363 einspaltige und 2 839 dreispaltige Summen in der letzten
Stelle ab (``konzepte/nachweise-oertliche-erkennung-2026-10/p5/summen.py``) —
und an der letzten Stelle hängen Radien und Trennungen.

Deshalb rechnet dieses Modul die Folge nach, in der numpy je Gruppe addiert:

* :func:`group_sums` wie ``values[gruppe].sum()`` an einem zusammenhängenden
  Feld — numpys paarweise Summe (unter acht Werten der Reihe nach, bis 128 in
  acht Teilsummen, darüber halbiert auf ein Vielfaches von acht);
* :func:`group_row_sums` wie ``rows[gruppe].sum(axis=0)`` — Zeile für Zeile
  der Reihe nach.

Gleich große Gruppen rechnen gemeinsam, Zeile für Zeile mit Grundrechenarten;
Gruppen über :data:`ALONE_ABOVE` Werten fragen numpy selbst, je Gruppe. Kein
BLAS, kein ``einsum`` (``kern.md``).
"""

from __future__ import annotations

from typing import Final

import numpy as np

#: Ab welcher Größe eine Gruppe für sich summiert wird: Die Nachrechnung kostet je
#: Größe eine Python-Runde je acht Werte, ``sum`` an einer großen Gruppe eine.
ALONE_ABOVE: Final = 64

#: Die Blockgröße der paarweisen Summe in numpy (``PW_BLOCKSIZE``).
_BLOCK: Final = 128


def _pairwise(columns: np.ndarray) -> np.ndarray:
    """Die paarweise Summe jeder Zeile von ``columns`` (Form ``(gruppen, n)``)."""
    count = columns.shape[1]
    if count < 8:
        result = np.zeros(columns.shape[0], dtype=np.float64)
        for index in range(count):
            result = result + columns[:, index]
        return result
    if count <= _BLOCK:
        partial = columns[:, :8].copy()
        index = 8
        stop = count - count % 8
        while index < stop:
            partial = partial + columns[:, index : index + 8]
            index += 8
        result = ((partial[:, 0] + partial[:, 1]) + (partial[:, 2] + partial[:, 3])) + (
            (partial[:, 4] + partial[:, 5]) + (partial[:, 6] + partial[:, 7])
        )
        while index < count:
            result = result + columns[:, index]
            index += 1
        return np.asarray(result, dtype=np.float64)
    half = count // 2
    half -= half % 8
    return np.asarray(_pairwise(columns[:, :half]) + _pairwise(columns[:, half:]))


def group_sums(values: np.ndarray, starts: np.ndarray, sizes: np.ndarray) -> np.ndarray:
    """Je Gruppe ``values[start : start + size].sum()``, Bit für Bit.

    ``values`` ist einspaltig und ``float64``; jede Gruppe hat mindestens einen Wert.
    """
    values = np.ascontiguousarray(values, dtype=np.float64)
    result = np.empty(len(sizes), dtype=np.float64)
    for size in np.unique(sizes).tolist():
        chosen = np.flatnonzero(sizes == size)
        if size > ALONE_ABOVE:
            for number in chosen.tolist():
                start = int(starts[number])
                result[number] = values[start : start + size].sum()
            continue
        rows = starts[chosen][:, None] + np.arange(size, dtype=np.int64)
        result[chosen] = _pairwise(values[rows])
    return result


def group_row_sums(rows: np.ndarray, starts: np.ndarray, sizes: np.ndarray) -> np.ndarray:
    """Je Gruppe ``rows[start : start + size].sum(axis=0)``, Bit für Bit.

    ``rows`` hat die Form ``(n, k)`` und ``float64``; summiert wird Zeile für Zeile.
    """
    rows = np.ascontiguousarray(rows, dtype=np.float64)
    result = np.empty((len(sizes), rows.shape[1]), dtype=np.float64)
    for size in np.unique(sizes).tolist():
        chosen = np.flatnonzero(sizes == size)
        if size > ALONE_ABOVE:
            for number in chosen.tolist():
                start = int(starts[number])
                result[number] = rows[start : start + size].sum(axis=0)
            continue
        first = starts[chosen]
        total = np.zeros((len(chosen), rows.shape[1]), dtype=np.float64)
        for offset in range(size):
            total = total + rows[first + offset]
        result[chosen] = total
    return result
