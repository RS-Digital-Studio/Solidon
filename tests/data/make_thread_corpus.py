"""Baut die Gewinde-Referenzkörper des Korpus (P2.5) — aus Konstruktionsmaßen, als STEP.

Dieselbe Bauart wie ``konzepte/nachweise-cad-p2-5/reference.py``: Die
Sollwerte der Tests kommen aus **diesen Maßen**, nie aus dem Prüfling. Die
Körper werden hier einmal gebaut und als STEP abgelegt, denn ein Bolzen
kostet rund zwanzig Sekunden und ein Innengewinde fast eine Minute — im
Tor wäre das zu viel. Alles Abgeleitete (Spiegelung, Lage, Zuschnitt,
Beschädigung, geteilte Träger, NURBS) baut ``tests/test_thread_import.py``
in unter einer Sekunde aus ``m6_rechts`` selbst.

    .venv\\Scripts\\python.exe tests/data/make_thread_corpus.py

Nur laufen lassen, wenn ein Maß sich ändert; die Sollwerte stehen in der
Fallmatrix des Tests.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.core.brep import edit, profiles, step  # noqa: E402
from app.core.brep.kernel import Solid, boolean_builder, copy_shape  # noqa: E402

THREADS = HERE / "threads"


def _helix_ridge(
    root_radius: float,
    crest_radius: float,
    pitch: float,
    lead: float,
    length: float,
    phase_deg: float,
) -> Solid:
    """Ein Gang als Helix-Sweep mit dem Vierpunktprofil des Netzwegs."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire
    from OCP.BRepLib import BRepLib
    from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipeShell
    from OCP.Geom import Geom_CylindricalSurface
    from OCP.Geom2d import Geom2d_Line
    from OCP.gp import gp_Ax2d, gp_Ax3, gp_Dir2d, gp_Pnt, gp_Pnt2d
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    turns = length / lead + 2.0
    surface = Geom_CylindricalSurface(gp_Ax3(), root_radius)
    start = math.radians(phase_deg)
    line = Geom2d_Line(gp_Ax2d(gp_Pnt2d(start, -lead), gp_Dir2d(2.0 * math.pi, lead)))
    span = math.hypot(2.0 * math.pi, lead) * turns
    helix = BRepBuilderAPI_MakeEdge(line, surface, 0.0, span).Edge()
    BRepLib.BuildCurves3d_s(helix)
    spine = BRepBuilderAPI_MakeWire(helix).Wire()
    inward = root_radius - 0.1
    corners = (
        (inward, -lead),
        (root_radius, -lead),
        (crest_radius, -lead + pitch * 0.25),
        (crest_radius, -lead + pitch * 0.55),
        (root_radius, -lead + pitch * 0.8),
        (inward, -lead + pitch * 0.8),
    )
    cs, sn = math.cos(start), math.sin(start)
    outline = BRepBuilderAPI_MakeWire()
    for index in range(len(corners)):
        a, b = corners[index - 1], corners[index]
        outline.Add(
            BRepBuilderAPI_MakeEdge(
                gp_Pnt(a[0] * cs, a[0] * sn, a[1]), gp_Pnt(b[0] * cs, b[0] * sn, b[1])
            ).Edge()
        )
    pipe = BRepOffsetAPI_MakePipeShell(spine)
    pipe.SetMode(True)
    pipe.Add(outline.Wire())
    pipe.Build()
    if not pipe.IsDone():
        raise RuntimeError("Gang: MakePipeShell scheiterte")
    pipe.MakeSolid()
    ridge = Solid(pipe.Shape())
    slab = edit.cylinder(2.0 * crest_radius + 2.0, length)
    trimmed = edit.boolean("intersection", [ridge, slab])
    explorer = TopExp_Explorer(trimmed.shape, TopAbs_SOLID)
    return Solid(TopoDS.Solid(explorer.Current()))


def _fuzzy_union(body: Solid, ridge: Solid, pitch: float, at_least: float) -> Solid:
    """Kern und Gang vereinigen — mit der Stufenleiter und einer Volumenuntergrenze.

    Ohne Toleranz verschluckt die Vereinigung den Gang still (P2.5 B3, P2.7
    B1); jede Stufe läuft auf privaten Kopien, sonst reißt die dritte nativ.
    """
    for ratio in (1e-4, 1e-3, 1e-2):
        left, _faces, _edges = copy_shape(body.shape)
        right, _faces, _edges = copy_shape(ridge.shape)
        operation = boolean_builder("union", left, right, tolerance=ratio * pitch)
        operation.Build()
        if not operation.IsDone():
            continue
        candidate = Solid(operation.Shape())
        if candidate.solid_count == 1 and candidate.is_closed and candidate.volume > at_least:
            return candidate
    raise RuntimeError("Gang ließ sich nicht mit dem Kern vereinigen")


def multi_start(major: float, pitch: float, starts: int, length: float) -> Solid:
    """Mehrgängiger Bolzen: ``starts`` Gänge, Vorschub ``starts * pitch``."""
    depth = pitch * 0.55
    root_radius = major / 2.0 - depth
    lead = starts * pitch
    body = edit.cylinder(2.0 * root_radius + 0.02, length)
    for start in range(starts):
        ridge = _helix_ridge(root_radius, major / 2.0, pitch, lead, length, 360.0 * start / starts)
        body = _fuzzy_union(body, ridge, pitch, body.volume * 1.02)
    return body


def internal_block(
    major: float, pitch: float, depth: float, play: float, size: float = 20.0
) -> Solid:
    """Gewindebohrung: Block minus Bolzen mit Spiel, unter der Mündung (z <= 0)."""
    tool = edit.moved(profiles.threaded_rod(major + play, pitch, depth), (0.0, 0.0, -depth))
    block = edit.moved(edit.box(size, size, depth), (0.0, 0.0, -depth))
    return edit.boolean("difference", [block, tool])


def seam_helix(diameter: float, height: float, pitch: float, depth: float) -> Solid:
    """Eine Wendel ohne Rille: ein hauchdünner Gang (``depth``) auf dem Zylinder."""
    root_radius = diameter / 2.0
    core = edit.cylinder(diameter + 0.02, height)
    ridge = _helix_ridge(root_radius, root_radius + depth, pitch, pitch, height, 0.0)
    return _fuzzy_union(core, ridge, pitch, core.volume * 1.0001)


BODIES = {
    # Name: (Erzeuger, Konstruktionsmaße) — die Sollwerte des Tests folgen daraus.
    "m6_rechts": lambda: profiles.threaded_rod(6.0, 1.0, 12.0),
    "m10_rechts": lambda: profiles.threaded_rod(10.0, 1.5, 20.0),
    "m8_innen": lambda: internal_block(8.0, 1.25, 10.0, 0.2),
    "zweigaengig": lambda: multi_start(8.0, 1.0, 2, 12.0),
    "gegen_naht": lambda: seam_helix(6.0, 12.0, 1.0, 0.02),
}


def main(names: list[str]) -> None:
    """Baut die genannten Körper, ohne Namen alle."""
    THREADS.mkdir(parents=True, exist_ok=True)
    for name, build in BODIES.items():
        if names and name not in names:
            continue
        body = build()
        payload = step.write(body)
        (THREADS / f"{name}.step").write_bytes(payload)
        print(
            f"{name}: {body.face_count} Flächen, {body.edge_count} Kanten, "
            f"Volumen {body.volume:.6f}, {len(payload)} Byte"
        )


if __name__ == "__main__":
    main(sys.argv[1:])
