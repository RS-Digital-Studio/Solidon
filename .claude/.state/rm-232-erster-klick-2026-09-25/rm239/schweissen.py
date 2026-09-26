"""RM-239 Sonde: Verschweißen je Punktgruppe, nach Flächenblatt getrennt.

Verschweißt wird wie heute (Rundung auf ``digits``); danach wird jede Punktgruppe
in die Blätter zerlegt, zu denen ihre Kopien gehören. Zwei Ecken bleiben eine,
wenn

(a) sie schon in der Datei dieselbe Ecke waren, oder
(b) ihre Dreiecke nach dem Verschweißen eine Kante mit genau zwei Flächen teilen.

Ein Dreieck, das beim Verschweißen zerfällt, zählt für (b) nicht; eine Gruppe
nur aus solchen Ecken schließt sich der größten Klasse ihres Punkts an (so fällt
ein Splitter einer Suppe weiter weg, wie heute).
"""

from __future__ import annotations

import numpy as np
import trimesh
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components


def rim_groups(vertices: np.ndarray, faces: np.ndarray, digits: int) -> np.ndarray:
    """Je Ecke ihre Schweißgruppe — nur Ecken an offenen Rändern teilen eine."""
    edges = np.sort(faces[:, [[0, 1], [1, 2], [2, 0]]].reshape(-1, 2), axis=1)
    n = len(vertices)
    code = edges[:, 0] * n + edges[:, 1]
    _unique, inverse, counts = np.unique(code, return_inverse=True, return_counts=True)
    rim = np.zeros(n, dtype=bool)
    rim[edges[counts[inverse] == 1].reshape(-1)] = True
    group = np.arange(n, dtype=np.int64)
    rim_index = np.flatnonzero(rim)
    if len(rim_index) > 1:
        _u, rim_group = trimesh.grouping.unique_rows(vertices[rim_index], digits=digits)
        rim_group = np.asarray(rim_group, dtype=np.int64).reshape(-1)
        first = np.full(int(rim_group.max()) + 1, n, dtype=np.int64)
        np.minimum.at(first, rim_group, rim_index)
        group[rim_index] = first[rim_group]
    return group


def weld_by_sheet(
    vertices: np.ndarray, faces: np.ndarray, digits: int, *, rims_only: bool = False
) -> tuple[np.ndarray, np.ndarray]:
    vertices = np.asarray(vertices, dtype=np.float64)
    faces = np.asarray(faces, dtype=np.int64)
    count = len(faces)
    if not count:
        return vertices, faces
    if rims_only:
        group = rim_groups(vertices, faces, digits)
    else:
        _unique, group = trimesh.grouping.unique_rows(vertices, digits=digits)
        group = np.asarray(group, dtype=np.int64).reshape(-1)
    welded = group[faces]
    degenerate = (welded[:, 0] == welded[:, 1]) | (welded[:, 1] == welded[:, 2]) | (welded[:, 2] == welded[:, 0])
    corners = 3 * count
    corner_of = np.arange(corners, dtype=np.int64).reshape(count, 3)
    rows: list[np.ndarray] = []
    cols: list[np.ndarray] = []
    # Deckungsgleiche Dreiecke (gleich oder gegenläufig) zählen für die Blattfrage als
    # eines: ihre Ecken folgen denen des ersten, und nur das erste zählt Kanten.
    live_rows = np.flatnonzero(~degenerate)
    key = np.sort(welded[live_rows], axis=1)
    _k, first_of, which = np.unique(key, axis=0, return_index=True, return_inverse=True)
    which = np.asarray(which).reshape(-1)
    primary_row = live_rows[first_of[which]]
    doubled = primary_row != live_rows
    if doubled.any():
        copies = live_rows[doubled]
        originals = primary_row[doubled]
        for k in range(3):
            match = welded[originals] == welded[copies, k][:, None]
            position = np.argmax(match, axis=1)
            rows.append(corner_of[copies, k])
            cols.append(corner_of[originals, position])
    primary = np.zeros(count, dtype=bool)
    primary[live_rows[~doubled]] = True
    # (a) dieselbe Ecke der Datei
    flat = faces.reshape(-1)
    order = np.argsort(flat, kind="stable")
    same = flat[order[1:]] == flat[order[:-1]]
    rows.append(order[:-1][same])
    cols.append(order[1:][same])
    # (b) Kanten mit genau zwei Flächen am verschweißten Netz
    keep = np.flatnonzero(primary)
    if len(keep):
        wf = welded[keep]
        pairs = np.stack([wf[:, [0, 1]], wf[:, [1, 2]], wf[:, [2, 0]]], axis=1).reshape(-1, 2)
        positions = np.array([[0, 1], [1, 2], [2, 0]], dtype=np.int64)
        position = np.tile(positions, (len(keep), 1))
        face_row = np.repeat(keep, 3)
        low = pairs.min(axis=1)
        high = pairs.max(axis=1)
        swapped = pairs[:, 0] > pairs[:, 1]
        # Ecke des Dreiecks an ``low`` und an ``high``
        at_low = np.where(swapped, position[:, 1], position[:, 0])
        at_high = np.where(swapped, position[:, 0], position[:, 1])
        n = int(group.max()) + 1
        code = low * n + high
        order = np.argsort(code, kind="stable")
        code_sorted = code[order]
        boundaries = np.r_[True, code_sorted[1:] != code_sorted[:-1]]
        starts = np.flatnonzero(boundaries)
        sizes = np.diff(np.r_[starts, len(code_sorted)])
        two = starts[sizes == 2]
        first = order[two]
        second = order[two + 1]
        f1, f2 = face_row[first], face_row[second]
        rows.append(corner_of[f1, at_low[first]])
        cols.append(corner_of[f2, at_low[second]])
        rows.append(corner_of[f1, at_high[first]])
        cols.append(corner_of[f2, at_high[second]])
    r = np.concatenate(rows)
    c = np.concatenate(cols)
    graph = coo_matrix((np.ones(len(r), dtype=np.int8), (r, c)), shape=(corners, corners))
    _n, label = connected_components(graph, directed=False)
    label = np.asarray(label, dtype=np.int64)
    corner_group = group[flat]
    # Klassen nur aus zerfallenen Dreiecken schließen sich einer lebenden Klasse ihres Punkts an
    # (der der kleinsten lebenden Ecke der Gruppe).
    on_degenerate = np.repeat(degenerate, 3)
    live = np.zeros(int(label.max()) + 1, dtype=bool)
    live[label[~on_degenerate]] = True
    dead_corner = ~live[label]
    if dead_corner.any():
        groups = int(group.max()) + 1
        live_corners = np.flatnonzero(~dead_corner)
        first = np.full(groups, corners, dtype=np.int64)
        np.minimum.at(first, corner_group[live_corners], live_corners)
        idx = np.flatnonzero(dead_corner)
        chosen = first[corner_group[idx]]
        has = chosen < corners
        label[idx[has]] = label[chosen[has]]
        rest = idx[~has]
        if len(rest):
            label[rest] = corners + corner_group[rest]
    # neue Ecken: je Klasse eine, Lage der kleinsten Dateiecke darin
    uniq, new_index = np.unique(label, return_inverse=True)
    lowest = np.full(len(uniq), np.iinfo(np.int64).max, dtype=np.int64)
    np.minimum.at(lowest, new_index, flat)
    return vertices[lowest], new_index.reshape(count, 3)


def weld_the_rims(vertices: np.ndarray, faces: np.ndarray, digits: int) -> tuple[np.ndarray, np.ndarray]:
    """Nur Ecken an offenen Rändern verschweißen; eine innere Ecke bleibt, wo und was sie ist."""
    vertices = np.asarray(vertices, dtype=np.float64)
    faces = np.asarray(faces, dtype=np.int64)
    if not len(faces):
        return vertices, faces
    edges = np.sort(faces[:, [[0, 1], [1, 2], [2, 0]]].reshape(-1, 2), axis=1)
    n = len(vertices)
    code = edges[:, 0] * n + edges[:, 1]
    _unique, inverse, counts = np.unique(code, return_inverse=True, return_counts=True)
    open_rows = counts[inverse] == 1
    rim = np.zeros(n, dtype=bool)
    rim[edges[open_rows].reshape(-1)] = True
    target = np.arange(n, dtype=np.int64)
    rim_index = np.flatnonzero(rim)
    if len(rim_index) > 1:
        _u, group = trimesh.grouping.unique_rows(vertices[rim_index], digits=digits)
        group = np.asarray(group, dtype=np.int64).reshape(-1)
        first = np.full(int(group.max()) + 1, n, dtype=np.int64)
        np.minimum.at(first, group, rim_index)
        target[rim_index] = first[group]
    new_faces = target[faces]
    used, remap = np.unique(new_faces, return_inverse=True)
    return vertices[used], remap.reshape(-1, 3)
