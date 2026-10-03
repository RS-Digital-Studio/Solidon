"""Typen für den übersetzten Schnittkern (``_chain.pyx``).

Die Erweiterung entsteht erst beim Bauen und ist nicht eingecheckt; ohne diese
Datei wüsste mypy nichts von ihr und meldete den Import als Fehler — auf jeder
Maschine, auf der gerade nichts gebaut wurde, also auch in der CI.
"""

from collections.abc import Callable

import numpy as np
import numpy.typing as npt

PLANE_SEGMENTS_API: int

def ring_nesting(
    coordinates: npt.NDArray[np.float64],
    ring_of: npt.NDArray[np.int64],
) -> (
    tuple[
        npt.NDArray[np.int64],
        npt.NDArray[np.int64],
        npt.NDArray[np.float64],
        npt.NDArray[np.int64],
        npt.NDArray[np.int64],
    ]
    | None
):
    """Ringanfänge/-enden, Umlaufsinn, Tiefe und Eltern bei gesichertem Nachweis."""

def cuts_along(
    across_head: npt.NDArray[np.float64],
    across_tail: npt.NDArray[np.float64],
    along_head: npt.NDArray[np.float64],
    along_tail: npt.NDArray[np.float64],
    positions: npt.NDArray[np.float64],
    normal: npt.NDArray[np.float64],
    direction: npt.NDArray[np.float64],
    epsilon: float,
) -> tuple[npt.NDArray[np.float64], npt.NDArray[np.float64], npt.NDArray[np.float64]] | None:
    """Anfänge, Enden und Längen der Materialstücke je Abtastlage."""

def plane_segments(
    vertices: npt.NDArray[np.float64],
    faces: npt.NDArray[np.int64],
    heights: npt.NDArray[np.float64],
    epsilon: float,
    check_cancelled: Callable[[], None] | None = None,
) -> tuple[
    npt.NDArray[np.float64],
    npt.NDArray[np.int64],
    npt.NDArray[np.int64],
]:
    """Gerichtete Schnittpunkte (Material links), Schichten und Kantenkennungen."""

def chain_rings(
    node: npt.NDArray[np.int64],
    incident: npt.NDArray[np.int64],
    walk: npt.NDArray[np.int64],
    ring_of: npt.NDArray[np.int64],
) -> tuple[int, int]:
    """``(Ringe, beschriebene Länge)``; ``(-1, 0)``, wenn ein Ring offen blieb."""

def orientation_scores(
    vertices: npt.NDArray[np.float64],
    normals: npt.NDArray[np.float64],
    centres: npt.NDArray[np.float64],
    areas: npt.NDArray[np.float64],
    area_steps: npt.NDArray[np.int64],
    area_exponent: int,
    verticals: npt.NDArray[np.float64],
    threshold: float,
) -> npt.NDArray[np.float64]:
    """Auflage, Überhang, Höhe und Stützschätzung je Richtung, bitgleich zur Feldrechnung."""
