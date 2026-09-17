"""Sichert das Netz, an dem die Bohrungskette auf dem Mac zerfällt (RM-187).

**Wozu.** Der Fall existiert nur auf ARM64, und jede Reparatur daran kostete
bisher einen vollen CI-Lauf — dreimal hintereinander wurde blind geraten und
dreimal kam der Mac einen Schritt weiter, aber nicht ans Ziel. Diese Sonde
holt das echte Netz aus dem Runner heraus, damit die Behebung lokal und mit
Blick auf den Fall entsteht statt auf Verdacht.

Sie läuft denselben Weg wie
``test_bore_mouth_resize.test_shrinking_keeps_the_countersink_and_recognises_the_new_shoulder``:
Bohrung mit Senkung bauen, auf 6,0 verkleinern, erkennen, Kette suchen. Danach
schreibt sie **beide** Netze (vorher und nachher) als ``.npz`` und die
Diagnose als Text.

Aufruf aus dem Wurzelverzeichnis des Arbeitsbaums::

    python .claude/.state/plattformgleichheit-2026-09-17/netz_sichern.py <ziel-ordner>
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

BAUM = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BAUM))
sys.path.insert(0, str(BAUM / "tests"))

import numpy as np  # noqa: E402

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()

from app.core.geom.mesh import MeshData  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.perceive.features import detect  # noqa: E402
from app.core.perceive.relations import cavity_chain_at  # noqa: E402


def fingerprint(values: np.ndarray) -> str:
    """Ein Hash über die rohen Bytes — gleiche Zahl heißt bitgleiches Feld."""
    return hashlib.sha256(np.ascontiguousarray(values, dtype=np.float64).tobytes()).hexdigest()[:16]


def main() -> int:
    ziel = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    ziel.mkdir(parents=True, exist_ok=True)

    # Die Testhilfen sind die Quelle: Ein eigener Nachbau wäre eine
    # Nachstellung und würde seine eigene Nachstellung messen.
    from test_bore_mouth_resize import _resize, _sloping_bore, _why_no_chain

    mesh, features, hole = _sloping_bore()
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    changed = _resize(mesh, features, hole, 6.0, profile).outputs[0].mesh
    assert isinstance(changed, MeshData)

    detected = detect(changed)
    smaller = min(
        (f for f in detected.values() if f.kind == "hole"), key=lambda f: f.params["diameter"]
    )
    chain = cavity_chain_at(smaller, detected, changed)

    bericht = [
        f"Plattform: {sys.platform} {getattr(sys.implementation, '_multiarch', '')}",
        f"Eingangsnetz : {len(mesh.raw.faces)} Dreiecke, {len(mesh.raw.vertices)} Ecken,"
        f" {fingerprint(mesh.raw.vertices)}",
        f"nach dem Ändern: {len(changed.raw.faces)} Dreiecke, {len(changed.raw.vertices)} Ecken,"
        f" {fingerprint(changed.raw.vertices)}",
        f"Kette: {'—' if chain is None else [f.kind for f in chain]}",
        "",
    ]
    if chain is None:
        bericht.append(_why_no_chain(changed, detected, smaller))
    (ziel / "bericht.txt").write_text("\n".join(bericht), encoding="utf-8")

    for name, data in (("eingang", mesh), ("geaendert", changed)):
        np.savez_compressed(
            ziel / f"{name}.npz",
            vertices=np.asarray(data.raw.vertices, dtype=np.float64),
            faces=np.asarray(data.raw.faces, dtype=np.int64),
        )

    print("\n".join(bericht))
    print(f"\ngeschrieben nach {ziel}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
