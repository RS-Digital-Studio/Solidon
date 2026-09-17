"""Wo läuft die Rechnung zwischen den Plattformen auseinander? (RM-187)

Am 17.09.2026 lieferte derselbe Körper 1224 Dreiecke auf Ubuntu, 1226 auf
Windows und 1228 auf macOS — bei identischen Maßen. Diese Sonde trennt, **wo**
das entsteht, und sie beantwortet die Frage nur, wenn sie auf allen drei
Plattformen läuft und die Fingerabdrücke nebeneinander stehen.

Drei Messpunkte:

1. **Die Eingabe**, Körper für Körper. Der erste Lauf war eindeutig: Der Klotz
   — eine Box ohne jede transzendente Funktion — war auf allen drei bitgleich,
   Hohlraum und Nachbar aus ``cos``/``sin`` auf allen drei verschieden. Die
   Abweichung entstand also vor dem Booleschen Kern, und **kein exakter Kern
   hätte sie geheilt**: Exakt gerechnet geben zwei verschiedene Eingaben zwei
   verschiedene Ergebnisse.
2. **Das Ergebnis der Booleschen Operation.** Bleibt es verschieden, obwohl
   Messpunkt 1 überall gleich ist, liegt der Rest bei ``manifold3d`` — und das
   ist dann die Frage, die an einen anderen Kern zu stellen wäre.
3. **Dasselbe mit quantisierter Eingabe.** Gemessen und verworfen: Das Runden
   schluckt die Abweichung nicht, es macht die Netze **schlechter** — 1422 bis
   1596 Dreiecke statt 1226, weil es die Koplanarität der Klotzflächen
   zerstört. Der Messpunkt bleibt stehen, damit dieselbe Frage nicht ein
   zweites Mal gestellt wird.

**Seit dem 17.09.2026 baut sie ihre Körper über die plattformfreien Ecken**
(``units.circle_cos_sin``, ``geom.lathe``) — dieselbe Bauart wie
``_sloping_bore`` im Test, damit beide denselben Körper messen.

Ausgegeben wird ein Hash je Stufe. Gleiche Hashes heißen bitgleiche Felder.

Aufruf aus dem Wurzelverzeichnis des Arbeitsbaums::

    .venv/Scripts/python.exe .claude/.state/plattformgleichheit-2026-09-17/eingabe_messen.py
"""

from __future__ import annotations

import hashlib
import sys
from pathlib import Path

# Vier Ebenen hinauf ist die Wurzel des Arbeitsbaums — kein fester Pfad, die
# Sonde soll auf jedem Runner laufen und nicht nur auf der Maschine, auf der
# sie entstanden ist.
BAUM = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(BAUM))

import numpy as np  # noqa: E402

from app.core import units  # noqa: E402
from app.core.bootstrap import load_operations  # noqa: E402
from app.core.geom import lathe  # noqa: E402
from app.core.geom.boolean import boolean  # noqa: E402
from app.core.geom.mesh import MeshData  # noqa: E402

load_operations()

from app.core.deferred import trimesh  # noqa: E402


def fingerprint(values: np.ndarray) -> str:
    """Ein Hash über die rohen Bytes — gleiche Zahl heißt bitgleiches Feld."""
    return hashlib.sha256(np.ascontiguousarray(values, dtype=np.float64).tobytes()).hexdigest()[:16]


def bodies() -> tuple[trimesh.Trimesh, trimesh.Trimesh, trimesh.Trimesh]:
    """Die drei Eingangskörper aus ``_sloping_bore`` — ohne die Boolesche Operation."""
    sections = 120
    # Seit dem 17.09.2026 ueber die plattformfreien Ecken — dieselbe Bauart
    # wie ``_sloping_bore`` im Test, damit beide denselben Koerper messen.
    table = np.asarray(units.circle_cos_sin(sections), dtype=float)
    vertices = []
    for radius, height, slope in ((4.5, 3.0, 0.04), (4.5, 17.0, 0.10), (5.5, 18.0, 0.08)):
        x, y = radius * table[:, 0], radius * table[:, 1]
        vertices.extend(zip(x, y, height + slope * x, strict=True))
    faces = []
    for ring in range(2):
        for at in range(sections):
            following = (at + 1) % sections
            lower, upper = ring * sections, (ring + 1) * sections
            faces.extend(
                (
                    (lower + at, lower + following, upper + following),
                    (lower + at, upper + following, upper + at),
                )
            )
    for ring, height in ((0, 3.0), (2, 18.0)):
        hub = len(vertices)
        vertices.append((0.0, 0.0, height))
        for at in range(sections):
            faces.append((ring * sections + at, ring * sections + (at + 1) % sections, hub))
    cavity = trimesh.Trimesh(vertices=vertices, faces=faces, process=True)
    trimesh.repair.fix_normals(cavity)

    stock = trimesh.creation.box(extents=(34.0, 26.0, 18.0))
    stock.apply_translation((5.0, 0.0, 9.0))
    points = np.asarray(stock.vertices).copy()
    top = points[:, 2] > 9.0
    points[top, 2] += 0.08 * points[top, 0]
    stock.vertices = points

    neighbour = lathe.cylinder(radius=4.75, height=20.0, sections=120)
    neighbour.apply_translation((12.0, 0.0, 13.0))
    return stock, cavity, neighbour


def quantised(body: trimesh.Trimesh, step: float) -> trimesh.Trimesh:
    """Dieselbe Form auf einem festen Gitter — plattformunabhängig bitgleich."""
    copy = body.copy()
    copy.vertices = np.round(np.asarray(copy.vertices, dtype=np.float64) / step) * step
    return copy


def main() -> int:
    stock, cavity, neighbour = bodies()
    print(f"Plattform: {sys.platform} {getattr(sys.implementation, '_multiarch', '')}")
    print("\n1. Die Eingabe, wie sie gebaut wird:")
    for name, body in (("Klotz", stock), ("Hohlraum", cavity), ("Nachbar", neighbour)):
        print(f"   {name:9s} {len(body.faces):5d} Dreiecke  {fingerprint(body.vertices)}")

    ergebnis = boolean(
        "difference",
        [MeshData.of(stock), MeshData.of(cavity), MeshData.of(neighbour)],
        quality="fine",
    ).mesh
    print(f"\n2. Nach der Booleschen Operation: {len(ergebnis.raw.faces)} Dreiecke")
    print(f"   Eckpunkte {fingerprint(ergebnis.raw.vertices)}")

    print("\n3. Mit quantisierter Eingabe:")
    for step in (1e-9, 1e-7, 1e-5):
        drei = [quantised(body, step) for body in (stock, cavity, neighbour)]
        marken = " ".join(fingerprint(body.vertices) for body in drei)
        try:
            gerundet = boolean(
                "difference", [MeshData.of(body) for body in drei], quality="fine"
            ).mesh
            zahl = len(gerundet.raw.faces)
            aus = fingerprint(gerundet.raw.vertices)
        except Exception as fehler:
            zahl, aus = -1, f"{type(fehler).__name__}: {fehler}"
        print(f"   Gitter {step:g} mm: Eingabe {marken}")
        print(f"                     Ergebnis {zahl} Dreiecke  {aus}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
