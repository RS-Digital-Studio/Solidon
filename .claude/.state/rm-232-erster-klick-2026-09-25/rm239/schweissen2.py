"""RM-239 Sonde, schnelle Fassung: Ränder verschweißen, Punktgruppen nach Flächenblatt trennen.

1. Nur Ecken an offenen Rändern bilden Schweißgruppen (Rundung auf ``digits``);
   eine innere Ecke bleibt, wo und was sie ist.
2. Eine Gruppe wird in die Blätter zerlegt, zu denen ihre Kopien gehören: Zwei
   Ecken bleiben eine, wenn sie schon in der Datei dieselbe waren oder ihre
   Dreiecke nach dem Verschweißen eine Kante mit genau zwei Flächen teilen.
   Zerfallene Dreiecke zählen nicht; deckungsgleiche zählen als eines.
"""

from __future__ import annotations

import numpy as np
import trimesh
from scipy.sparse import coo_matrix
from scipy.sparse.csgraph import connected_components


def _edge_codes(faces: np.ndarray, n: int) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """Je Kantenzeile (drei je Dreieck) Code, Ecke am kleineren und am größeren Ende."""
    a = faces[:, [0, 1, 2]].reshape(-1)
    b = faces[:, [1, 2, 0]].reshape(-1)
    low = np.minimum(a, b)
    high = np.maximum(a, b)
    return low * n + high, low, high


def weld_sheets(vertices: np.ndarray, faces: np.ndarray, digits: int) -> tuple[np.ndarray, np.ndarray]:
    vertices = np.asarray(vertices, dtype=np.float64)
    faces = np.asarray(faces, dtype=np.int64)
    count = len(faces)
    n = len(vertices)
    if not count:
        return vertices, faces
    flat = faces.reshape(-1)
    uses = np.bincount(flat, minlength=n)
    soup = int(uses.max()) <= 1
    # 1 — Ränder
    if soup:
        rim_index = np.flatnonzero(uses)
    else:
        code, low, high = _edge_codes(faces, n)
        order = np.argsort(code)
        sorted_code = code[order]
        starts = np.r_[0, np.flatnonzero(sorted_code[1:] != sorted_code[:-1]) + 1]
        sizes = np.diff(np.r_[starts, len(sorted_code)])
        single = order[starts[sizes == 1]]
        rim = np.zeros(n, dtype=bool)
        rim[low[single]] = True
        rim[high[single]] = True
        rim_index = np.flatnonzero(rim)
    group = np.arange(n, dtype=np.int64)
    if len(rim_index) < 2:
        return vertices, faces
    _u, rim_group = trimesh.grouping.unique_rows(vertices[rim_index], digits=digits)
    rim_group = np.asarray(rim_group, dtype=np.int64).reshape(-1)
    first = np.full(int(rim_group.max()) + 1, n, dtype=np.int64)
    np.minimum.at(first, rim_group, rim_index)
    group[rim_index] = first[rim_group]
    merged = group[rim_index] != rim_index
    if not merged.any():
        return vertices, faces
    # 2 — Blätter
    welded = group[faces]
    degenerate = (welded[:, 0] == welded[:, 1]) | (welded[:, 1] == welded[:, 2]) | (welded[:, 2] == welded[:, 0])
    corners = 3 * count
    corner_of = np.arange(corners, dtype=np.int64).reshape(count, 3)
    rows: list[np.ndarray] = []
    cols: list[np.ndarray] = []
    if not soup:
        # (a) dieselbe Ecke der Datei: je Dateiecke an ihre erste Ecke gebunden
        first_corner = np.full(n, corners, dtype=np.int64)
        np.minimum.at(first_corner, flat, np.arange(corners, dtype=np.int64))
        rows.append(np.arange(corners, dtype=np.int64))
        cols.append(first_corner[flat])
    primary = ~degenerate
    code, low, high = _edge_codes(welded, n)
    code[np.repeat(~primary, 3)] = -1
    order = np.argsort(code)
    sorted_code = code[order]
    starts = np.r_[0, np.flatnonzero(sorted_code[1:] != sorted_code[:-1]) + 1]
    sizes = np.diff(np.r_[starts, len(sorted_code)])
    valid = sorted_code[starts] >= 0
    crowded = starts[(sizes > 2) & valid]
    if len(crowded):
        # Deckungsgleiche Dreiecke an überzähligen Kanten zählen als eines.
        suspects = np.unique(np.concatenate([order[s : s + z] // 3 for s, z in zip(crowded, sizes[(sizes > 2) & valid], strict=True)]))
        key = np.sort(welded[suspects], axis=1)
        _k, first_of, which = np.unique(key, axis=0, return_index=True, return_inverse=True)
        which = np.asarray(which).reshape(-1)
        original = suspects[first_of[which]]
        doubled = original != suspects
        if doubled.any():
            copies = suspects[doubled]
            originals = original[doubled]
            for k in range(3):
                position = np.argmax(welded[originals] == welded[copies, k][:, None], axis=1)
                rows.append(corner_of[copies, k])
                cols.append(corner_of[originals, position])
            primary[copies] = False
            code, low, high = _edge_codes(welded, n)
            code[np.repeat(~primary, 3)] = -1
            order = np.argsort(code)
            sorted_code = code[order]
            starts = np.r_[0, np.flatnonzero(sorted_code[1:] != sorted_code[:-1]) + 1]
            sizes = np.diff(np.r_[starts, len(sorted_code)])
            valid = sorted_code[starts] >= 0
    # (b) Kanten mit genau zwei Flächen
    two = starts[(sizes == 2) & valid]
    first_row = order[two]
    second_row = order[two + 1]
    face_one, face_two = first_row // 3, second_row // 3
    slot_one, slot_two = first_row % 3, second_row % 3
    # Ecke eines Dreiecks am kleineren und am größeren Ende der Kante
    ends_one = np.stack([slot_one, (slot_one + 1) % 3], axis=1)
    ends_two = np.stack([slot_two, (slot_two + 1) % 3], axis=1)
    low_one = np.where(welded[face_one, ends_one[:, 0]] <= welded[face_one, ends_one[:, 1]], ends_one[:, 0], ends_one[:, 1])
    high_one = np.where(low_one == ends_one[:, 0], ends_one[:, 1], ends_one[:, 0])
    low_two = np.where(welded[face_two, ends_two[:, 0]] <= welded[face_two, ends_two[:, 1]], ends_two[:, 0], ends_two[:, 1])
    high_two = np.where(low_two == ends_two[:, 0], ends_two[:, 1], ends_two[:, 0])
    rows.append(corner_of[face_one, low_one])
    cols.append(corner_of[face_two, low_two])
    rows.append(corner_of[face_one, high_one])
    cols.append(corner_of[face_two, high_two])
    r = np.concatenate(rows)
    c = np.concatenate(cols)
    keep = c < corners
    graph = coo_matrix((np.ones(int(keep.sum()), dtype=np.int8), (r[keep], c[keep])), shape=(corners, corners))
    _count, label = connected_components(graph, directed=False)
    label = np.asarray(label, dtype=np.int64)
    corner_group = group[flat]
    # Klassen nur aus zerfallenen Dreiecken folgen der ersten lebenden Ecke ihres Punkts.
    on_primary = np.repeat(primary | ~degenerate, 3)
    live = np.zeros(int(label.max()) + 1, dtype=bool)
    live[label[on_primary]] = True
    dead = ~live[label]
    if dead.any():
        live_corners = np.flatnonzero(~dead)
        firsts = np.full(n, corners, dtype=np.int64)
        np.minimum.at(firsts, corner_group[live_corners], live_corners)
        idx = np.flatnonzero(dead)
        chosen = firsts[corner_group[idx]]
        has = chosen < corners
        label[idx[has]] = label[chosen[has]]
        rest = idx[~has]
        if len(rest):
            label[rest] = int(label.max()) + 1 + corner_group[rest]
    used = np.zeros(int(label.max()) + 1, dtype=bool)
    used[label] = True
    remap = np.cumsum(used) - 1
    new_index = remap[label]
    lowest = np.full(int(used.sum()), n, dtype=np.int64)
    np.minimum.at(lowest, new_index, flat)
    return vertices[lowest], new_index.reshape(count, 3)
