"""Wie viel Platz die Maßfelder im Bild brauchen und wohin sie im Notfall gehen.

Reine Rechnung über Rechtecke, ohne Fenster prüfbar: ``PlacementFlow`` fragt
hier, wie viele Feldzeilen die Maßkarte unter sich freihält
(:func:`distance_reserve`, :func:`rows_height`), und wohin die Felder kommen,
wenn die Nähe-Suche keinen Platz mehr fand (:func:`emergency_places`).
"""

from __future__ import annotations

from collections.abc import Sequence

from PySide6.QtCore import QPoint, QRect, QSize

from app.ui.style import SPACE


def rows_height(sizes: Sequence[QSize], width: int) -> int:
    """Wie hoch die Zeilen sind, in denen diese Felder nebeneinander stehen.

    Je Zeile die Höhe ihres höchsten Feldes und ein Abstand — für ein einzelnes
    Feld genau die eine Zeile, die die Maßkarte immer freihielt. Ein Feld, das
    nicht mehr in die Breite passt, beginnt die nächste Zeile wie in
    :func:`emergency_places`.
    """
    height = row = x = 0
    for size in sizes:
        if x and x + size.width() > width:
            height += row + SPACE
            x = row = 0
        x += size.width() + SPACE
        row = max(row, size.height())
    return height + row + SPACE if row else height


def distance_reserve(line: int, rows: int) -> int:
    """Wie viel Höhe die Maßkarte unter sich für die Maßfelder freihält.

    ``line`` ist die Höhe eines Kantenmaßes, ``rows`` die Höhe der Feldzeilen
    des letzten Aufbaus (:func:`rows_height`). Mindestens eine Zeile bleibt
    frei; passen die Felder nicht nebeneinander in den Raum, so viele Zeilen,
    wie sie brauchen. Eine einzige feste Zeile ließ bei hoher, rollender Karte
    das letzte Feld unter den Bildrand fallen (FD-84).
    """
    return max(line + SPACE, rows)


def _first_free(size: QSize, bounds: QRect, taken: Sequence[QRect]) -> QRect | None:
    """Der erste Platz in Lesereihenfolge, der im Bild steht und frei ist.

    Gefragt wird an den Kanten des Bildes und hinter jedem belegten Rechteck —
    dort beginnt jede Lücke. Frei heißt wie bei der Nähe-Suche: mit
    :data:`SPACE` Abstand zu allem Belegten.
    """
    ys = sorted({bounds.top(), *(rect.bottom() + SPACE + 1 for rect in taken)})
    xs = sorted({bounds.left(), *(rect.right() + SPACE + 1 for rect in taken)})
    for y in ys:
        for x in xs:
            rect = QRect(QPoint(x, y), size)
            if not bounds.contains(rect):
                continue
            grown = rect.adjusted(-SPACE, -SPACE, SPACE, SPACE)
            if not any(grown.intersects(other) for other in taken):
                return rect
    return None


def emergency_places(
    sizes: Sequence[QSize],
    bounds: QRect,
    fixed: Sequence[QRect],
    tiers: Sequence[Sequence[QRect]],
) -> list[QRect]:
    """Die Notanordnung: jedes Feld der Reihe nach an den ersten freien Platz im Bild.

    ``fixed`` bleibt frei, solange im Bild neben ihr Platz für das Feld ist —
    die vom Kunden gelegte Karte, unter der ein Maß ganz verschwände.
    ``tiers`` sind die übrigen Hindernisse von streng nach nachgiebig: erst mit
    Abstand, dann ohne, zuletzt keine. Ein Feld nimmt den ersten Platz der
    strengsten Stufe, in der es einen gibt; Überdecken ist das kleinere Übel,
    ein Feld außerhalb des Bildes ist keines. Ist neben Karte und gelegten
    Feldern nichts mehr frei, überdeckt es eher ein Feld als die Karte — beide
    Felder bleiben zu sehen —, und füllt die Karte das Bild, rückt es an den
    ersten Platz neben den Feldern oder an die linke obere Ecke: im Bild, nie
    darunter.
    """
    placed: list[QRect] = []
    for size in sizes:
        rect = next(
            (
                found
                for obstacles in tiers
                if (found := _first_free(size, bounds, [*fixed, *placed, *obstacles])) is not None
            ),
            None,
        )
        if rect is None:
            rect = (
                _first_free(size, bounds, fixed)
                or _first_free(size, bounds, placed)
                or QRect(bounds.topLeft(), size)
            )
        placed.append(rect)
    return placed
