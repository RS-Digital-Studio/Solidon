"""Wo im Änderungsweg laufen die Plattformen auseinander? (RM-187)

Nach der Umstellung der Kreispunkte stimmen Eingangskörper und Boolesche
Operation auf allen drei Plattformen bitgenau überein. Das **Ändern** einer
Bohrung tut es noch nicht — 1174 Dreiecke auf Windows und Ubuntu, 1182 auf
macOS, und drei verschiedene Fingerabdrücke.

Diese Sonde rät nicht, wo das entsteht, sondern zeichnet es auf: Sie legt sich
vor ``geom.boolean.boolean`` und schreibt für **jeden** Aufruf die
Fingerabdrücke aller Eingangskörper und des Ergebnisses. Der erste Schritt, an
dem sich die Plattformen unterscheiden, ist die gesuchte Stelle — liegt schon
eine Eingabe auseinander, ist es unser Werkzeugbau; liegen alle Eingaben
gleich und nur das Ergebnis nicht, ist es der Boolesche Kern.

Aufruf aus dem Wurzelverzeichnis des Arbeitsbaums::

    python .claude/.state/plattformgleichheit-2026-09-17/weg_aufzeichnen.py
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

from app.core.geom import boolean as boolean_module  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402


def fingerprint(values: object) -> str:
    """Ein Hash über die rohen Bytes — gleiche Zahl heißt bitgleiches Feld."""
    raw = np.ascontiguousarray(np.asarray(values, dtype=np.float64))
    return hashlib.sha256(raw.tobytes()).hexdigest()[:16]


def main() -> int:
    print(f"Plattform: {sys.platform} {getattr(sys.implementation, '_multiarch', '')}")

    echt = boolean_module.boolean
    schritt = 0

    def aufzeichnend(kind, meshes, **kwargs):  # type: ignore[no-untyped-def]
        nonlocal schritt
        schritt += 1
        nummer = schritt
        eingang = [
            f"{len(m.raw.faces)}/{fingerprint(m.raw.vertices)}"
            for m in meshes
            if hasattr(m, "raw")
        ]
        ergebnis = echt(kind, meshes, **kwargs)
        raus = ergebnis.mesh
        aus = (
            f"{len(raus.raw.faces)}/{fingerprint(raus.raw.vertices)}"
            if hasattr(raus, "raw")
            else "—"
        )
        import traceback

        woher = [
            f"{rahmen.name}:{rahmen.lineno}"
            for rahmen in traceback.extract_stack()[:-1]
            if "app\core" in rahmen.filename or "app/core" in rahmen.filename
        ][-4:]
        print(f"  {nummer:2d}. {kind:11s} ein: {'  '.join(eingang)}")
        print(f"      {'':11s} von: {' < '.join(reversed(woher))}")
        print(f"      {'':11s} aus: {aus}  (Stufe {ergebnis.solver})")
        return ergebnis

    # Zwischen zwei Booleschen Schritten wird das Netz angefasst — von
    # ``apply`` (eine Transformation) und von ``MeshData.of`` (Verschweissen).
    # Beides gehoert in die Aufzeichnung, sonst endet sie an einer Luecke.
    from app.core.geom import ops as ops_module
    from app.core.geom.mesh import MeshData

    echt_apply = ops_module.apply

    def apply_aufzeichnend(mesh, matrix, **kwargs):  # type: ignore[no-untyped-def]
        ergebnis = echt_apply(mesh, matrix, **kwargs)
        if hasattr(mesh, "raw") and hasattr(ergebnis, "raw"):
            print(
                f"      apply       {len(mesh.raw.faces)}/{fingerprint(mesh.raw.vertices)}"
                f" -> {len(ergebnis.raw.faces)}/{fingerprint(ergebnis.raw.vertices)}"
                f"  Matrix {fingerprint(matrix)}"
            )
        return ergebnis

    ops_module.apply = apply_aufzeichnend
    for name in ("prepare", "prepare_ops", "edges", "hollow", "lid"):
        modul = sys.modules.get(f"app.core.geom.{name}")
        if modul is not None and getattr(modul, "apply", None) is echt_apply:
            modul.apply = apply_aufzeichnend

    echt_of = MeshData.of

    def of_aufzeichnend(raw, **kwargs):  # type: ignore[no-untyped-def]
        ergebnis = echt_of(raw, **kwargs)
        vorher = getattr(raw, "vertices", None)
        if vorher is not None and len(ergebnis.raw.vertices) != len(vorher):
            print(
                f"      MeshData.of {len(raw.faces)}/{fingerprint(vorher)}"
                f" -> {len(ergebnis.raw.faces)}/{fingerprint(ergebnis.raw.vertices)}"
            )
        return ergebnis

    MeshData.of = staticmethod(of_aufzeichnend)  # type: ignore[method-assign]

    boolean_module.boolean = aufzeichnend
    # Die Aufrufer halten eigene Namen auf dieselbe Funktion.
    for name in ("prepare", "prepare_ops", "edges", "hollow", "lid"):
        modul = sys.modules.get(f"app.core.geom.{name}")
        if modul is not None and hasattr(modul, "boolean"):
            modul.boolean = aufzeichnend

    from test_bore_mouth_resize import _resize, _sloping_bore

    print("\nDas Eingangsnetz bauen:")
    mesh, features, hole = _sloping_bore()
    print(f"  Ergebnis: {len(mesh.raw.faces)} Dreiecke  {fingerprint(mesh.raw.vertices)}")

    print("\nDie Bohrung auf 6,0 verkleinern:")
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    changed = _resize(mesh, features, hole, 6.0, profile).outputs[0].mesh
    print(f"  Ergebnis: {len(changed.raw.faces)} Dreiecke  {fingerprint(changed.raw.vertices)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
