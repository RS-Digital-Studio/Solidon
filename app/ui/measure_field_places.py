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


def _least_covering(
    size: QSize, bounds: QRect, fixed: Sequence[QRect], placed: Sequence[QRect]
) -> QRect | None:
    """Der Platz im Bild neben der Karte, der die gelegten Felder am wenigsten deckt.

    Gefragt wird an den Stellen von :func:`_first_free`, dazu am rechten und
    unteren Bildrand und an Anfang und Mitte jedes gelegten Feldes — so kann ein
    Feld seitlich versetzt über einem anderen stehen. Ein Platz, der ein Feld
    ganz deckt oder ganz in einem liegt, kommt nicht in Frage: Dann wäre eines
    der beiden nicht mehr zu sehen. Unter den übrigen gewinnt die kleinste
    Überdeckung eines einzelnen Feldes, dann die kleinste Summe, dann die
    Lesereihenfolge.
    """
    width, height = size.width(), size.height()
    xs = {bounds.left(), bounds.right() - width + 1}
    ys = {bounds.top(), bounds.bottom() - height + 1}
    for rect in (*fixed, *placed):
        xs.add(rect.right() + SPACE + 1)
        ys.add(rect.bottom() + SPACE + 1)
    for rect in placed:
        xs.update({rect.left(), rect.left() + rect.width() // 2})
        ys.update({rect.top(), rect.top() + rect.height() // 2})
    best: tuple[tuple[int, int, int, int], QRect] | None = None
    for y in ys:
        for x in xs:
            rect = QRect(x, y, width, height)
            if not bounds.contains(rect) or any(rect.intersects(card) for card in fixed):
                continue
            covers = [rect.intersected(field) for field in placed]
            if any(part in (field, rect) for part, field in zip(covers, placed, strict=True)):
                continue
            areas = [part.width() * part.height() for part in covers if not part.isEmpty()]
            key = (max(areas, default=0), sum(areas), y, x)
            if best is None or key < best[0]:
                best = (key, rect)
    return best[1] if best is not None else None


def emergency_places(
    sizes: Sequence[QSize],
    bounds: QRect,
    fixed: Sequence[QRect],
    tiers: Sequence[Sequence[QRect]],
) -> list[QRect]:
    """Die Notanordnung: jedes Feld der Reihe nach an den ersten freien Platz im Bild.

    ``fixed`` bleibt frei, solange im Bild neben ihr Platz für das Feld ist —
    die vom Kunden gelegte Karte; die Halter der Kantenmaße liegen unter ihr.
    ``tiers`` sind die übrigen Hindernisse von streng nach nachgiebig: erst mit
    Abstand, dann ohne, zuletzt keine. Ein Feld nimmt den ersten Platz der
    strengsten Stufe, in der es einen gibt; Überdecken ist das kleinere Übel,
    ein Feld außerhalb des Bildes ist keines. Ist neben Karte und gelegten
    Feldern nichts mehr frei, steht es neben der Karte seitlich versetzt über
    den Feldern, ohne eines ganz zu decken (:func:`_least_covering`). Geht auch
    das nicht, rückt es an den ersten Platz neben den Feldern, auch über die
    Karte, zuletzt an die linke obere Ecke: im Bild, nie darunter.
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
                _least_covering(size, bounds, fixed, placed)
                or _first_free(size, bounds, placed)
                or QRect(bounds.topLeft(), size)
            )
        placed.append(rect)
    return placed
