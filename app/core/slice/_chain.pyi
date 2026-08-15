"""Typen für die übersetzte Konturverkettung (``_chain.pyx``).

Die Erweiterung entsteht erst beim Bauen und ist nicht eingecheckt; ohne diese
Datei wüsste mypy nichts von ihr und meldete den Import als Fehler — auf jeder
Maschine, auf der gerade nichts gebaut wurde, also auch in der CI.
"""

import numpy as np
import numpy.typing as npt

def chain_rings(
    node: npt.NDArray[np.int64],
    incident: npt.NDArray[np.int64],
    walk: npt.NDArray[np.int64],
    ring_of: npt.NDArray[np.int64],
) -> tuple[int, int]:
    """``(Ringe, beschriebene Länge)``; ``(-1, 0)``, wenn ein Ring offen blieb."""
