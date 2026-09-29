"""Gemeinsamer Anfang der Sonden des Prüfers rest-merker.

``setup(tree)`` setzt den Baum an ``sys.path[0]``, biegt die
Nutzerverzeichnisse in einen Temp-Ordner um, importiert ``app`` und bricht ab,
wenn ``app`` nicht aus dem Baum kommt. Erst danach darf eine Sonde ``app.*``
importieren. (Übernommen aus den Sonden des Prüfers rest-erkennung2.)
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
KUNDE = Path(r"F:\3D Dateien")
WT = Path(r"F:\3D Druck.review-051\wt-rest-merker")
HEAD = HERE / "head"


def setup(tree: str | Path) -> Path:
    """Baum eintragen, Nutzerordner isolieren, ``app`` prüfen.

    ``wt`` steht für den Arbeitsbaum, ``head`` für den ausgepackten Vergleichsstand
    (Pfade mit Leerzeichen kommen durch ``cmd /c start`` nicht heil an).
    """
    tree = {"wt": WT, "head": HEAD}.get(str(tree), Path(tree)).resolve()
    isolated = tempfile.mkdtemp(prefix="solidon-rest-merker-")
    for variable in ("APPDATA", "LOCALAPPDATA", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
        os.environ[variable] = isolated
    sys.path[:] = [entry for entry in sys.path if entry.rstrip(chr(92) + "/").lower() != r"f:\3d druck"]
    sys.path.insert(0, str(tree))
    import app

    where = Path(app.__file__).resolve()
    print("app aus:", where, flush=True)
    if tree not in where.parents:
        raise SystemExit(f"app kommt nicht aus {tree}: {where}")
    return tree


def activation_free() -> None:
    """Die Lizenzgrenze für die Sonde öffnen, wie die Suite es tut."""
    try:
        from app.core.activation import store as activation_store

        activation_store.DEMO_UNTIL = None
        activation_store.TRIAL_FROM = activation_store.DEMO_FROM
    except Exception as error:  # noqa: BLE001 — alte Bäume kennen das nicht
        print("Lizenzgrenze nicht gesetzt:", error)


def mesh_from_npz(path: Path):
    import numpy as np
    import trimesh

    from app.core.geom.mesh import MeshData

    data = np.load(path)
    return MeshData.of(trimesh.Trimesh(data["vertices"], data["faces"], process=False))


class Clock:
    def __init__(self) -> None:
        self.start = time.perf_counter()

    def __call__(self) -> float:
        now = time.perf_counter()
        spent, self.start = now - self.start, now
        return spent


def kinds(features) -> dict[str, int]:
    counts: dict[str, int] = {}
    for feature in features.values():
        counts[feature.kind] = counts.get(feature.kind, 0) + 1
    return dict(sorted(counts.items()))
