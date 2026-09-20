"""Referenzkörper für P2.5 — unabhängig beschrieben, ohne Erzeugermerkmale.

Jede Funktion baut einen Körper aus benannten Konstruktionsmaßen; die
Sollwerte der Sonden kommen aus **diesen Maßen**, nie aus dem Prüfling.
Die Körper werden von ``s2_reference.py`` als STEP geschrieben und von den
Messsonden frisch eingelesen: Was dann im Körper steckt, ist Geometrie und
sonst nichts — keine Steigung, keine Händigkeit, kein Name.

Der Gewindebolzen kommt aus ``profiles.threaded_rod`` (vorhanden);
Linksgewinde entstehen durch Spiegelung, Innengewinde durch Abzug des um das
Spiel weiteren Bolzens, mehrgängige durch einen eigenen Helix-Sweep je Gang
(dieselbe Bauart wie ``threaded_rod``, mit Vorschub = Gangzahl mal Teilung).
"""

from __future__ import annotations

import math
from typing import Any

import _iso  # noqa: F401
import _probe as pr
import numpy as np

from app.core.brep import edit, profiles
from app.core.brep.kernel import Solid, boolean_builder, copy_shape
from app.core.sketch.profile import Profile, ProfileSegment

ISO_DEPTH_SHARE = 0.6134  # dieselbe Zahl wie profiles._THREAD_DEPTH_SHARE, nur zum Sollwert


def rod(major: float, pitch: float, length: float) -> Solid:
    return profiles.threaded_rod(major, pitch, length)


def mirrored(solid: Solid) -> Solid:
    """Spiegelung an der XZ-Ebene: Achse bleibt Z, aus rechts wird links."""
    matrix = (
        (1.0, 0.0, 0.0, 0.0),
        (0.0, -1.0, 0.0, 0.0),
        (0.0, 0.0, 1.0, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    )
    return edit.transformed(solid, matrix)


def placed(
    solid: Solid,
    degrees: float,
    axis: tuple[float, float, float],
    offset: tuple[float, float, float],
) -> Solid:
    """Gedreht um eine Achse durch den Ursprung, dann verschoben."""
    a = np.asarray(axis, dtype=float)
    a = a / np.linalg.norm(a)
    t = math.radians(degrees)
    c, s = math.cos(t), math.sin(t)
    x, y, z = a
    rot = [
        [c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s, offset[0]],
        [y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s, offset[1]],
        [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c), offset[2]],
        [0.0, 0.0, 0.0, 1.0],
    ]
    matrix = tuple(tuple(float(v) for v in row) for row in rot)
    return edit.transformed(solid, matrix)  # type: ignore[arg-type]


def rotated_axis(degrees: float, axis: tuple[float, float, float]) -> tuple[float, float, float]:
    """Wohin die Z-Achse nach ``placed`` zeigt — der unabhängige Sollwert."""
    a = np.asarray(axis, dtype=float)
    a = a / np.linalg.norm(a)
    t = math.radians(degrees)
    c, s = math.cos(t), math.sin(t)
    x, y, z = a
    column = (x * z * (1 - c) + y * s, y * z * (1 - c) - x * s, c + z * z * (1 - c))
    return (float(column[0]), float(column[1]), float(column[2]))


def internal_block(
    major: float, pitch: float, depth: float, play: float, size: float = 20.0
) -> Solid:
    """Gewindebohrung: Block minus Bolzen mit Spiel, unter der Mündung (z <= 0)."""
    tool = pr.moved(profiles.threaded_rod(major + play, pitch, depth), (0.0, 0.0, -depth))
    block = pr.moved(pr.box(size, size, depth), (0.0, 0.0, -depth))
    return pr.subtract(block, tool)


def _helix_ridge(
    root_radius: float,
    crest_radius: float,
    pitch: float,
    lead: float,
    length: float,
    phase_deg: float,
) -> Solid:
    """Ein Gang als Helix-Sweep mit dem Vierpunktprofil des Netzwegs (P2.7-Prototyp)."""
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
    slab = pr.cylinder(2.0 * crest_radius + 2.0, length)
    trimmed = edit.boolean("intersection", [ridge, slab])
    explorer = TopExp_Explorer(trimmed.shape, TopAbs_SOLID)
    return Solid(TopoDS.Solid(explorer.Current()))


def multi_start(major: float, pitch: float, starts: int, length: float) -> Solid:
    """Mehrgängiger Bolzen: ``starts`` Gänge, Vorschub ``starts * pitch``."""
    depth = pitch * 0.55
    root_radius = major / 2.0 - depth
    lead = starts * pitch
    core = pr.cylinder(2.0 * root_radius + 0.02, length)
    body = core
    for start in range(starts):
        ridge = _helix_ridge(root_radius, major / 2.0, pitch, lead, length, 360.0 * start / starts)
        joined = None
        for ratio in (1e-4, 1e-3, 1e-2):
            left, _ = copy_shape(body.shape)
            right, _ = copy_shape(ridge.shape)
            operation = boolean_builder("union", left, right, tolerance=ratio * pitch)
            operation.Build()
            if not operation.IsDone():
                continue
            candidate = Solid(operation.Shape())
            if (
                candidate.solid_count == 1
                and candidate.is_closed
                and candidate.volume > body.volume * 1.02
            ):
                joined = candidate
                break
        if joined is None:
            raise RuntimeError("Gang ließ sich nicht mit dem Kern vereinigen")
        body = joined
    return body


def halved(solid: Solid, keep_from_x: float = -1.0) -> Solid:
    """Angeschnitten: alles unter x = keep_from_x fehlt."""
    box = pr.moved(pr.box(200.0, 200.0, 200.0), (keep_from_x + 100.0, 0.0, -50.0))
    return pr.intersect(solid, box)


def segment(solid: Solid, z0: float, z1: float) -> Solid:
    """Ein kurzes Stück des Bolzens: nur z0..z1 bleibt, beide Enden geschnitten.

    Der kurze Bolzen kommt **nicht** aus ``threaded_rod(6, 1, 2.5)``: Der
    liefert an dieser und weiteren Längen (jede halbzahlige Umlaufzahl des
    Rasters, dazu M8 x 1,25 mit Länge 8) den nackten Kern ohne Gang, ohne
    Fehler — gemessen in ``s4_rod_lengths.py``, Befund B3 im Bericht. Ein
    Zuschnitt aus dem langen Bolzen trägt sein Gewinde sicher.
    """
    # ``edit.box`` steht in X und Y zentriert auf dem Bett — verschoben wird
    # nur in Z. (Mit einem Versatz von -100 blieb ein Quadrant übrig:
    # 13 mm³ statt 53, gemessen.)
    slab = pr.moved(pr.box(200.0, 200.0, z1 - z0), (0.0, 0.0, z0))
    return pr.intersect(solid, slab)


def sector_piece(solid: Solid, z0: float, z1: float, degrees: float) -> Solid:
    """Ein kleiner Ausschnitt: Höhe z0..z1, Winkelsektor 0..degrees."""
    from app.core.brep import profiles as bp

    reach = 100.0
    outline = [
        (0.0, 0.0),
        (reach, 0.0),
        (reach * math.cos(math.radians(degrees)), reach * math.sin(math.radians(degrees))),
    ]
    wedge = pr.moved(bp.extrude(pr.polygon(outline), z1 - z0), (0.0, 0.0, z0))
    return pr.intersect(solid, wedge)


def damaged(solid: Solid, z0: float, z1: float, degrees: float, from_radius: float) -> Solid:
    """Beschädigte Flanken: ein Sektor des Mantels ab ``from_radius`` fehlt."""
    reach = 100.0
    outline = [
        (from_radius, 0.0),
        (reach, 0.0),
        (reach * math.cos(math.radians(degrees)), reach * math.sin(math.radians(degrees))),
        (
            from_radius * math.cos(math.radians(degrees)),
            from_radius * math.sin(math.radians(degrees)),
        ),
    ]
    cutter = pr.moved(profiles.extrude(pr.polygon(outline), z1 - z0), (0.0, 0.0, z0))
    return pr.subtract(solid, cutter)


def smooth_cylinder(diameter: float, height: float) -> Solid:
    return pr.cylinder(diameter, height)


def ring_grooves(diameter: float, height: float, count: int, groove_radius: float) -> Solid:
    """Ringrillen: Zylinder minus Tori — periodisch, aber nicht schraubenförmig."""
    body = pr.cylinder(diameter, height)
    for index in range(count):
        z = height * (index + 1) / (count + 1)
        body = pr.subtract(body, pr.torus(diameter / 2.0, groove_radius, z))
    return body


def knurl(diameter: float, height: float, count: int, depth: float) -> Solid:
    """Längsrillen (Rändel): periodisch um die Achse, alle Kanten gerade."""
    body = pr.cylinder(diameter, height)
    for index in range(count):
        bar = pr.moved(pr.box(depth * 2.0, depth * 2.0, height + 2.0), (diameter / 2.0, 0.0, -1.0))
        body = pr.subtract(body, pr.turned(bar, 360.0 * index / count))
    return body


def seam_helix(diameter: float, height: float, pitch: float, depth: float) -> Solid:
    """Eine Wendel ohne Rille: ein hauchdünner Gang (``depth``) auf dem Zylinder."""
    root_radius = diameter / 2.0
    core = pr.cylinder(diameter + 0.02, height)
    ridge = _helix_ridge(root_radius, root_radius + depth, pitch, pitch, height, 0.0)
    for ratio in (1e-4, 1e-3, 1e-2):
        left, _ = copy_shape(core.shape)
        right, _ = copy_shape(ridge.shape)
        operation = boolean_builder("union", left, right, tolerance=ratio * pitch)
        operation.Build()
        if operation.IsDone():
            candidate = Solid(operation.Shape())
            if (
                candidate.solid_count == 1
                and candidate.is_closed
                and candidate.volume > core.volume * 1.0001
            ):
                return candidate
    raise RuntimeError("Naht ließ sich nicht vereinigen")


def wave_profile(diameter: float, height: float, amplitude: float, waves: int) -> Solid:
    """Gewellter Drehkörper (Spline-Meridian): periodisch entlang der Achse, kein Gewinde."""
    steps = waves * 8
    through = tuple(
        (
            diameter / 2.0 + amplitude * math.sin(2.0 * math.pi * waves * index / steps),
            height * index / steps,
        )
        for index in range(steps + 1)
    )
    profile = Profile(
        segments=(
            ProfileSegment("line", (0.0, 0.0), through[0]),
            ProfileSegment("spline", through[0], through[-1], through=through),
            ProfileSegment("line", through[-1], (0.0, height)),
            ProfileSegment("line", (0.0, height), (0.0, 0.0)),
        )
    )
    return profiles.revolve(profile, 360.0)


def reparametrised(solid: Solid) -> Solid:
    """Alle Flächen und Kurven als NURBS — eine andere Darstellung derselben Geometrie."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert

    converter = BRepBuilderAPI_NurbsConvert(solid.shape, True)
    return Solid(converter.Shape())


def split_faces(solid: Solid, z: float) -> Solid:
    """Flächen und Kanten an einer Ebene geteilt, der Körper bleibt einer."""
    from OCP.BOPAlgo import BOPAlgo_Splitter
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.collections import List_TopoDS_Shape
    from OCP.gp import gp_Dir, gp_Pln, gp_Pnt
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    plane = BRepBuilderAPI_MakeFace(
        gp_Pln(gp_Pnt(0.0, 0.0, z), gp_Dir(0.0, 0.0, 1.0)), -100.0, 100.0, -100.0, 100.0
    ).Face()
    splitter = BOPAlgo_Splitter()
    arguments = List_TopoDS_Shape()
    arguments.Append(solid.shape)
    tools = List_TopoDS_Shape()
    tools.Append(plane)
    splitter.SetArguments(arguments)
    splitter.SetTools(tools)
    splitter.Perform()
    shape = splitter.Shape()
    explorer = TopExp_Explorer(shape, TopAbs_SOLID)
    solids: list[Any] = []
    while explorer.More():
        solids.append(Solid(TopoDS.Solid(explorer.Current())))
        explorer.Next()
    # Der Splitter teilt auch den Körper; die Vereinigung macht ihn wieder zu
    # einem und lässt die geteilten Mantelflächen und Kanten stehen.
    body = solids[0]
    for other in solids[1:]:
        body = edit.boolean("union", [body, other])
    return body
