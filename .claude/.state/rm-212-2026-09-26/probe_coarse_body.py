"""Warum lehnt die Boolesche Kette das grobe Netz des Piratenschiffs ab? (RM-212)

Liest das Modell wie die Anwendung (``Session.import_model``), verkleinert es
wie die grobe Vorschau (``_coarse_params``) und prüft das Ergebnis mit den
drei Fragen, die ``boolean._kernel`` stellt — je Schale.
"""

from __future__ import annotations

import os
import sys
import tempfile
import time
from pathlib import Path

TREE = os.environ["SONDE_TREE"]
sys.path.insert(0, TREE)
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
_ISOLATED = tempfile.mkdtemp(prefix="sonde-grob-")
for _variable in ("APPDATA", "LOCALAPPDATA", "HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
    os.environ[_variable] = _ISOLATED

import app  # noqa: E402

assert str(Path(app.__file__).resolve()).startswith(str(Path(TREE).resolve())), app.__file__

from PySide6.QtWidgets import QApplication  # noqa: E402

QT = QApplication.instance() or QApplication([])

from app.core import bootstrap  # noqa: E402

bootstrap.load_operations()

import numpy as np  # noqa: E402

from app.core.geom.mesh import face_components, signed_volume  # noqa: E402
from app.core.geom.mesh_ops import decimate_for_display  # noqa: E402
from app.ui import session as session_module  # noqa: E402
from app.ui.session import Session  # noqa: E402


def report(name, mesh) -> None:
    raw = mesh.raw
    print(
        f"  {name}: {mesh.triangle_count} Dreiecke, dicht={raw.is_watertight}, "
        f"gleichsinnig={raw.is_winding_consistent}, Volumen={signed_volume(raw):.1f}",
        flush=True,
    )
    pieces = face_components(raw)
    print(f"    {len(pieces)} Teile", flush=True)
    negative = 0
    for number, faces in enumerate(pieces):
        piece = raw.submesh([faces], append=True)
        volume = signed_volume(piece)
        if volume <= 0.0 or not piece.is_watertight or not piece.is_winding_consistent:
            negative += 1
            if negative <= 8:
                print(
                    f"    Teil {number}: {len(piece.faces)} Dreiecke, dicht={piece.is_watertight}, "
                    f"gleichsinnig={piece.is_winding_consistent}, Volumen={volume:.2f}"
                )
    print(f"    davon offen oder nicht positiv: {negative}", flush=True)


for path in sys.argv[1:]:
    session = Session()
    started = time.perf_counter()
    session.import_model(Path(path), unit="mm")
    result = session.evaluate_now()
    entry = next(iter(result.scene.objects.values()))
    print(f"{Path(path).name}: geöffnet in {time.perf_counter() - started:.1f} s", flush=True)
    report("eingelesen", entry.mesh)
    np.savez(Path(os.environ.get("SONDE_NPZ", "eingelesen.npz")), vertices=entry.mesh.raw.vertices, faces=entry.mesh.raw.faces)
    started = time.perf_counter()
    coarse = decimate_for_display(entry.mesh, session_module._coarse_params()["triangles"])
    print(f"  verkleinert in {time.perf_counter() - started:.2f} s", flush=True)
    report("grob", coarse)
    session.release(30_000)
