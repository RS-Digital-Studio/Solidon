"""Körperkanten aus einem Netz, ohne Renderer (§18.1).

PyVistas ``extract_feature_edges`` lieferte die Kanten, an denen sich ein
Körper knickt, dazu seine offenen Ränder — die Linien, die ``solid`` über die
Flächen zeichnet. Dasselbe rechnet :func:`feature_edges` über NumPy: Jede
Kante gehört zu einem oder zwei Dreiecken. Eine mit einem ist ein Rand; eine
mit zweien ist scharf, wenn die Normalen der beiden mehr als ``angle`` Grad
auseinanderstehen. Kanten mit drei und mehr Dreiecken (nicht mannigfaltig)
bleiben weg, wie vorher (``non_manifold_edges=False``).
"""

from __future__ import annotations

from collections.abc import Sequence

import numpy as np

from app.core.units import EPS_GEOM


def feature_edges(vertices: np.ndarray, faces: np.ndarray, angle: float) -> np.ndarray:
    """Die Endpunkte der Körperkanten, paarweise — ``(2m, 3)`` für ``add_lines``.

    ``angle`` ist der Knick in Grad, ab dem eine Kante zwischen zwei Dreiecken
    als Kante des Körpers gilt; Ränder zählen immer.
    """
    triangles = np.asarray(faces, dtype=np.int64).reshape(-1, 3)
    points = np.asarray(vertices, dtype=float).reshape(-1, 3)
    if len(triangles) == 0:
        return np.zeros((0, 3), dtype=float)
    edges = np.concatenate([triangles[:, [0, 1]], triangles[:, [1, 2]], triangles[:, [2, 0]]])
    edges.sort(axis=1)
    owners = np.tile(np.arange(len(triangles)), 3)
    unique, inverse, counts = np.unique(edges, axis=0, return_inverse=True, return_counts=True)
    inverse = np.asarray(inverse).ravel()
    chosen = counts == 1
    shared = np.flatnonzero(counts == 2)
    if len(shared):
        order = np.argsort(inverse, kind="stable")
        starts = np.searchsorted(inverse[order], shared)
        first = owners[order[starts]]
        second = owners[order[starts + 1]]
        normals = _face_normals(points, triangles)
        cosine = np.clip(np.einsum("ij,ij->i", normals[first], normals[second]), -1.0, 1.0)
        sharp = np.degrees(np.arccos(cosine)) >= float(angle)
        chosen[shared[sharp]] = True
    return np.asarray(points[unique[chosen].ravel()], dtype=float)


#: Wie fein zwei Bildabstände noch als verschieden gelten, in Bildpunkten.
#:
#: Darunter entscheidet die Tiefe. Der Fall dafür ist die Silhouette: Ein
#: Quader von vorn zeigt seine vier Rückkanten **genau hinter** den vorderen,
#: und beide sind vom Zeiger gleich weit weg. Ohne diese Schwelle gewänne,
#: wer im Fließkommarest ein Tausendstel näher liegt — also der Zufall, und
#: bei jeder Mausbewegung ein anderer.
SAME_DISTANCE = 1.0

#: Ab welcher quadrierten Bildpunktlänge ein Stück eine Richtung hat.
#:
#: Eine eigene Zahl und **nicht** :data:`~app.core.units.EPS_GEOM`: Die ist
#: „absolut, fürs Fertigen" und meint Millimeter (§11.2). Hier steht auf der
#: anderen Seite eine Fläche in Bildpunkten — es ginge zufällig gut, weil
#: beide Zahlen klein sind, und die Konstante sagte etwas anderes, als sie
#: prüft. (Weiter unten in dieser Datei ist dasselbe ``EPS_GEOM`` richtig:
#: dort sind es Weltlängen.)
SAME_PIXEL = 1e-6


def nearest_polyline(
    projected: Sequence[np.ndarray], x: float, y: float, tolerance: float
) -> int | None:
    """Welcher Linienzug unter dem Zeiger liegt — sein Platz in ``projected``.

    Jeder Eintrag ist ein Linienzug in Bildkoordinaten: ``(n, 3)`` aus x, y
    und Tiefe, wie sie ``world_to_display`` zurückgibt. Gemessen wird der
    Abstand zu den **Strecken** dazwischen und nicht zu den Punkten: Eine
    lange gerade Kante hat zwei Punkte und tausend Bildpunkte dazwischen, und
    einen davon meint der Zeiger.

    **Der kleinste Abstand gewinnt, bei gleichem Abstand die kleinere
    Tiefe.** Beide Hälften sind nötig: Der Abstand sagt, worauf jemand zeigt;
    die Tiefe entscheidet, wo zwei Linienzüge im Bild aufeinanderliegen — die
    Silhouette eines Quaders von vorn zeigt seine vier Rückkanten genau hinter
    den vorderen.

    **Was die Tiefe hier nicht leistet: die Rückseite auszuschließen.** Sie
    greift erst bei praktisch gleichem Abstand (:data:`SAME_DISTANCE`), und
    eine verdeckte Kante, die zwei Bildpunkte näher liegt als die sichtbare
    davor, gewinnt. Wer das braucht, filtert vorher — der Viewport tut es
    gegen den getroffenen Oberflächenpunkt (``_edges_near``), denn nur der
    Aufrufer weiß, was er gerade angeklickt hat.

    ``tolerance`` ist der Radius um den Zeiger, in Bildpunkten. Wer nichts
    trifft, bekommt ``None`` — und nicht den entferntesten Linienzug: Ein
    Klick auf die nackte Fläche meint keine Kante.
    """
    pointer = np.array([float(x), float(y)], dtype=float)
    best: tuple[float, float] | None = None
    found: int | None = None
    for place, points in enumerate(projected):
        path = np.asarray(points, dtype=float).reshape(-1, 3)
        if len(path) < 2:
            continue
        distance, depth = _closest_on_path(path, pointer)
        if distance > float(tolerance):
            continue
        # Auf einen Bildpunkt gerundet vergleichen, damit die Tiefe bei
        # praktisch gleicher Entfernung entscheidet und nicht der Rest.
        rank = (round(distance / SAME_DISTANCE), depth)
        if best is None or rank < best:
            best = rank
            found = place
    return found


def _closest_on_path(path: np.ndarray, pointer: np.ndarray) -> tuple[float, float]:
    """Abstand des Zeigers zum Linienzug und die Tiefe an dieser Stelle."""
    start = path[:-1]
    end = path[1:]
    span = end[:, :2] - start[:, :2]
    squared = np.einsum("ij,ij->i", span, span)
    # Ein entartetes Stück — beide Enden derselbe Bildpunkt — hat keine
    # Richtung; dort ist der Anfang selbst die nächste Stelle.
    degenerate = squared <= SAME_PIXEL
    squared[degenerate] = 1.0
    share = np.einsum("ij,ij->i", pointer - start[:, :2], span) / squared
    share[degenerate] = 0.0
    share = np.clip(share, 0.0, 1.0)
    closest = start[:, :2] + share[:, None] * span
    distances = np.linalg.norm(closest - pointer, axis=1)
    place = int(np.argmin(distances))
    depth = start[place, 2] + share[place] * (end[place, 2] - start[place, 2])
    return float(distances[place]), float(depth)


def _face_normals(points: np.ndarray, triangles: np.ndarray) -> np.ndarray:
    """Die Normalen aller Dreiecke, normiert — entartete zeigen nach +Z."""
    corners = points[triangles]
    normals = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    lengths = np.linalg.norm(normals, axis=1)
    flat = lengths <= EPS_GEOM
    normals[flat] = (0.0, 0.0, 1.0)
    lengths[flat] = 1.0
    return normals / lengths[:, None]
