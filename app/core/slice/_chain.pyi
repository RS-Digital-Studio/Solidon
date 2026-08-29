"""Typen für den übersetzten Schnittkern (``_chain.pyx``).

Die Erweiterung entsteht erst beim Bauen und ist nicht eingecheckt; ohne diese
Datei wüsste mypy nichts von ihr und meldete den Import als Fehler — auf jeder
Maschine, auf der gerade nichts gebaut wurde, also auch in der CI.
"""

import numpy as np
import numpy.typing as npt

def plane_segments(
    vertices: npt.NDArray[np.float64],
    faces: npt.NDArray[np.int64],
    heights: npt.NDArray[np.float64],
    epsilon: float,
) -> tuple[
    npt.NDArray[np.float64],
    npt.NDArray[np.int64],
    npt.NDArray[np.int64],
]:
    """Schnittpunkte, Schichtnummern und Kantenkennungen."""

def chain_rings(
    node: npt.NDArray[np.int64],
    incident: npt.NDArray[np.int64],
    walk: npt.NDArray[np.int64],
    ring_of: npt.NDArray[np.int64],
) -> tuple[int, int]:
    """``(Ringe, beschriebene Länge)``; ``(-1, 0)``, wenn ein Ring offen blieb."""
