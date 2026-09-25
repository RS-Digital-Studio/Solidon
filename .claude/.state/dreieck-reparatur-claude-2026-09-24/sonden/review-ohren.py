"""Review-Sonde: Ohrenschneiden an zufälligen einfachen Vielecken (nur lesend).

Je Fall: gültig heißt n-2 Dreiecke, alle in Umlaufrichtung (Fläche > 0 in der Ringebene),
Summe der Flächen gleich der Vieleckfläche (keine Überdeckung), kein Fächer.
Gegen HEAD verglichen.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from common import R, head_repair  # noqa: E402

HEAD = head_repair()
rng = np.random.default_rng(11)


def star(count: int) -> np.ndarray:
    angles = np.sort(rng.random(count)) * 2.0 * math.pi
    radii = 5.0 + 5.0 * rng.random(count)
    return np.column_stack((radii * np.cos(angles), radii * np.sin(angles)))


def comb(teeth: int) -> np.ndarray:
    """Ein Kamm: stark nicht konvex, viele Reflexecken."""
    points = [(0.0, 0.0)]
    for index in range(teeth):
        x = 2.0 * index
        points += [(x + 0.5, 0.0), (x + 0.5, 6.0), (x + 1.5, 6.0), (x + 1.5, 0.0)]
    points += [(2.0 * teeth, 0.0), (2.0 * teeth, -2.0), (0.0, -2.0)]
    return np.asarray(points[::-1][:-1][::-1], dtype=float)


def collinear_rect(per_side: int) -> np.ndarray:
    xs = np.linspace(0.0, 10.0, per_side + 1)[:-1]
    bottom = [(x, 0.0) for x in xs]
    right = [(10.0, y) for y in np.linspace(0.0, 4.0, 3)[:-1]]
    top = [(x, 4.0) for x in xs[::-1] + 10.0 / per_side]
    left = [(0.0, 4.0), (0.0, 2.0)]
    return np.asarray(bottom + right + top + left, dtype=float)


def area2d(points: np.ndarray) -> float:
    ahead = np.roll(points, -1, axis=0)
    return float((points[:, 0] * ahead[:, 1] - points[:, 1] * ahead[:, 0]).sum()) / 2.0


def lift(flat: np.ndarray) -> np.ndarray:
    """In eine schräge Ebene im Raum legen."""
    q, _ = np.linalg.qr(rng.normal(size=(3, 3)))
    local = np.column_stack((flat, np.zeros(len(flat))))
    return local @ q.T + np.array([3.0, -7.0, 11.0])


def check(module, points3: np.ndarray, flat: np.ndarray) -> str:
    count = len(points3)
    loop = list(range(count))
    pieces = module._loop_triangles(points3, loop)
    if len(pieces) and int(pieces.max()) >= count:
        return "fan"
    if len(pieces) != count - 2:
        return f"count {len(pieces)}"
    total = 0.0
    sense = 1.0 if area2d(flat) > 0 else -1.0
    for a, b, c in pieces.tolist():
        signed = sense * area2d(flat[[a, b, c]])
        if signed <= 1e-12:
            return "backwards"
        total += signed
    if abs(total - abs(area2d(flat))) > 1e-6 * abs(area2d(flat)):
        return f"overlap {total:.4f} vs {abs(area2d(flat)):.4f}"
    return "ok"


from collections import Counter  # noqa: E402

for label, maker, runs in (
    ("Stern 12", lambda: star(12), 200),
    ("Stern 40", lambda: star(40), 200),
    ("Stern 200", lambda: star(200), 50),
    ("Kamm 10", lambda: comb(10), 1),
    ("Kamm 60", lambda: comb(60), 1),
    ("Rechteck mit kollinearen Punkten", lambda: collinear_rect(12), 1),
):
    new, old = Counter(), Counter()
    for _run in range(runs):
        flat = maker()
        if area2d(flat) < 0:
            flat = flat[::-1]
        points3 = lift(flat)
        new[check(R, points3, flat)] += 1
        old[check(HEAD, points3, flat)] += 1
        reversed3 = points3[::-1].copy()
        new["rev " + check(R, reversed3, flat[::-1])] += 1
    print(f"{label}: neu {dict(new)} | HEAD {dict(old)}")
