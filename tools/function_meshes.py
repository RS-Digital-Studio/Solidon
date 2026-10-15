"""Netze, die eine Szene beim Bau erzeugt, statt sie aus ``tests/data`` zu lesen (FD-101).

Ein Netz über der automatischen Erkennungsgrenze (``perceive.local.FEATURE_LIMIT_TRIANGLES``,
anderthalb Millionen Dreiecke) wäre als Datei zig Megabyte groß; ins Repository
gehört es nicht. Erzeugt wird es aus einer festen Vorschrift ohne Zufall — gleiche
Eingabe, gleiche Bytes —, wenn ``function_scenes.build_scene`` die Szene baut.
Eine Szene nennt ihren Generator unter ``built`` (Quellkennung → Name hier).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Final

#: Kanten der Oberseite und der Unterseite der dichten Platte. 4 · n² + 8 · n
#: Dreiecke: bei 620 sind es 1 542 560 — über der automatischen Grenze von
#: 1 500 000 und unter der bestätigbaren von 5 000 000 (§21.1).
DENSE_PLATE_CELLS: Final = 620


def dense_plate() -> tuple[bytes, str]:
    """Eine geschlossene Platte 200 x 200 x 10 mm, Ober- und Unterseite fein gerastert.

    Gibt die Datei als binäres PLY und ihre Endung zurück. Die Seiten verbinden
    die Randpunkte beider Raster; alle Dreiecke zeigen nach außen.
    """
    import io

    import numpy as np
    import trimesh

    cells = DENSE_PLATE_CELLS
    side = cells + 1
    axis = np.linspace(-100.0, 100.0, side)
    xs, ys = np.meshgrid(axis, axis, indexing="xy")
    flat = np.column_stack([xs.ravel(), ys.ravel()])
    top = np.column_stack([flat, np.full(len(flat), 10.0)])
    bottom = np.column_stack([flat, np.zeros(len(flat))])
    vertices = np.vstack([top, bottom])
    offset = side * side

    rows, columns = np.meshgrid(np.arange(cells), np.arange(cells), indexing="ij")
    a = (rows * side + columns).ravel()
    b = a + 1
    c = a + side
    d = c + 1
    top_faces = np.vstack([np.column_stack([a, b, d]), np.column_stack([a, d, c])])
    bottom_faces = np.vstack([np.column_stack([a, d, b]), np.column_stack([a, c, d])]) + offset

    # Der Rand im Umlauf gegen den Uhrzeigersinn, von oben gesehen.
    steps = np.arange(cells)
    ring = np.concatenate(
        [
            steps,  # unten: y = -100, x wächst
            cells + steps * side,  # rechts: x = +100, y wächst
            side * side - 1 - steps,  # oben: y = +100, x fällt
            (cells - steps) * side,  # links: x = -100, y fällt
        ]
    )
    following = np.roll(ring, -1)
    upper, upper_next = ring, following
    lower, lower_next = ring + offset, following + offset
    side_faces = np.vstack(
        [
            np.column_stack([lower, lower_next, upper_next]),
            np.column_stack([lower, upper_next, upper]),
        ]
    )
    faces = np.vstack([top_faces, bottom_faces, side_faces]).astype(np.int64)
    body = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    payload = io.BytesIO()
    body.export(payload, file_type="ply", encoding="binary")
    return payload.getvalue(), ".ply"


#: Name → Generator; ``function_scenes`` ruft ihn beim Bau der Szene.
GENERATORS: Final[dict[str, Callable[[], tuple[bytes, str]]]] = {
    "dichte_platte": dense_plate,
}
