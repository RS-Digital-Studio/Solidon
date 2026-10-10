"""Wie gut ein Dreiecksnetz geschnitten ist — gemessen wie im Versionsvergleich von Weg 4.

Ein **Splitter** ist ein Dreieck mit einem Winkel unter zehn Grad (RM-671). Auf
Splittern wirkt ein Pinsel ungleichmäßig, und jeder Folgeschritt rechnet an
Dreiecken, die keine Fläche tragen. Gemessen wird über die Kosinusse der drei
Ecken, ohne Winkelfunktion: Ein Winkel liegt unter zehn Grad, wenn sein Kosinus
über dem von zehn Grad liegt. Ein Dreieck mit einer Kante der Länge null zählt
als Splitter.
"""

from __future__ import annotations

import math

import numpy as np

from app.core.geom.mesh import MeshData

#: Unter welchem Winkel ein Dreieck ein Splitter ist, in Grad.
SLIVER_DEGREES = 10.0


def sliver_share(mesh: MeshData) -> float:
    """Der Anteil der Dreiecke mit einem Winkel unter :data:`SLIVER_DEGREES`."""
    corners = np.asarray(mesh.raw.vertices, dtype=float)[np.asarray(mesh.raw.faces, dtype=np.int64)]
    if not len(corners):
        return 0.0
    limit = math.cos(math.radians(SLIVER_DEGREES))
    widest = np.full(len(corners), -1.0)
    for corner in range(3):
        one = corners[:, (corner + 1) % 3] - corners[:, corner]
        two = corners[:, (corner + 2) % 3] - corners[:, corner]
        lengths = np.sqrt((one * one).sum(axis=1) * (two * two).sum(axis=1))
        with np.errstate(divide="ignore", invalid="ignore"):
            cosine = np.where(lengths > 0.0, (one * two).sum(axis=1) / lengths, 1.0)
        widest = np.maximum(widest, cosine)
    return float((widest > limit).mean())
