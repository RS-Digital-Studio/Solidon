"""Sonde: weitere Fehlerbilder, die der Import vermutlich nicht schließen kann."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import trimesh

HERE = Path(__file__).resolve().parent / "netze"
HERE.mkdir(exist_ok=True)


def box(offset=(0.0, 0.0, 0.0)) -> trimesh.Trimesh:
    mesh = trimesh.creation.box((20.0, 20.0, 20.0))
    mesh.apply_translation(offset)
    return mesh


# a — zwei Würfel teilen genau eine Kante
trimesh.util.concatenate([box(), box((20.0, 20.0, 0.0))]).export(HERE / "kante_geteilt.stl")
# b — zwei Würfel teilen eine Fläche (Wand doppelt)
trimesh.util.concatenate([box(), box((20.0, 0.0, 0.0))]).export(HERE / "flaeche_geteilt.stl")
# c — Würfel mit innerer Trennwand
inner = trimesh.Trimesh(
    [[0, -10, -10], [0, 10, -10], [0, 10, 10], [0, -10, 10]], [[0, 1, 2], [0, 2, 3]]
)
trimesh.util.concatenate([box(), inner]).export(HERE / "innere_wand.stl")
# d — Dreieckssuppe: zufällige lose Dreiecke
rng = np.random.default_rng(3)
soup = trimesh.Trimesh(rng.random((60, 3)) * 30.0, rng.integers(0, 60, (40, 3)), process=False)
soup.export(HERE / "suppe.stl")
# e — Würfel, dem zwei benachbarte Seiten fehlen, plus hineinragende Zunge
open_box = box()
keep = ~((open_box.face_normals[:, 0] > 0.5) | (open_box.face_normals[:, 1] > 0.5))
tongue = trimesh.Trimesh([[5, 5, 0], [15, 5, 0], [15, 15, 0]], [[0, 1, 2]])
trimesh.util.concatenate(
    [trimesh.Trimesh(open_box.vertices, open_box.faces[keep]), tongue]
).export(HERE / "offen_mit_zunge.stl")
print("ok")
