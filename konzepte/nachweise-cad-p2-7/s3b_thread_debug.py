"""S3b: Gewinde-Gegenfälle — Fuzzy-Stufen, private Kopien, Senkkopf und STEP.

Drei Fragen, in der Reihenfolge ihrer Verlässlichkeit:

1. Kegelkopf + ``threaded_rod``: welche Fuzzy-Stufe verschmilzt beide zu einem
   Körper, und welcher Weg überlebt die STEP-Rundreise?
2. Kern + Gang (Netzprofil, Helix-Sweep): welche Fuzzy-Stufe behält den Gang?
   Jede Stufe auf **privaten Kopien** (``copy_shape``) — dieselben Eingaben
   mehrfach durch Fuzzy-Booleans zu schicken riss den Prozess reproduzierbar
   (Exit 139, 3 von 3 Läufen, ``s3b.lauf1-3.out``); ``NonDestructive``
   schützt die Topologie, nicht die Toleranzen an den Kanten.
3. Zuletzt der Gegenfall selbst: die Vereinigung **ohne** Fuzzy verschluckt
   den Gang still (gültig, ein Körper, Volumen = Kern). Auf dieser degenerierten
   Form wird nur noch das Volumen gelesen — ein Punkttest darauf riss den
   Prozess ebenfalls (Exit 139).
"""

from __future__ import annotations

import math

import _probe as pr

from app.core.brep import profiles, step
from app.core.brep.kernel import Solid, boolean_builder, copy_shape
from app.core.knowledge import standards

pr.out("== 1. Senkkopf + threaded_rod: Fuzzy-Stufen und STEP-Rundreise ==")
m5 = standards.screw("M5")
head_height = (m5.countersink - m5.nominal) / 2.0
head = pr.moved(pr.cone(m5.nominal, m5.countersink, head_height), (0.0, 0.0, -head_height))
with pr.Timed("threaded_rod M5 x 12"):
    rod = profiles.threaded_rod(m5.nominal, m5.pitch, 12.0)
threaded = pr.moved(rod, (0.0, 0.0, -head_height - 12.0 + 0.01))
for tol in (None, 1e-4, 1e-3, 1e-2):
    left, _ = copy_shape(head.shape)
    right, _ = copy_shape(threaded.shape)
    op = boolean_builder("union", left, right, tolerance=tol)
    op.Build()
    if not op.IsDone():
        pr.out(f"  tol={tol}: nicht fertig")
        continue
    body = Solid(op.Shape())
    state = f"solids={body.solid_count} closed={body.is_closed} valid={pr.is_valid(body)}"
    line = f"  tol={tol}: {state} V={body.volume:.4f}"
    if body.solid_count == 1:
        back = step.read(step.write(body, "senkkopf"))
        line += f" -> STEP zurück valid={pr.is_valid(back)} solids={back.solid_count}"
        line += f" V={back.volume:.4f}"
    pr.out(line)

pr.out("")
pr.out("== 1b. Senkkopf: Fuzzy 1e-4 mit ShapeFix vor dem STEP-Export ==")
from OCP.ShapeFix import ShapeFix_Shape  # noqa: E402

left, _ = copy_shape(head.shape)
right, _ = copy_shape(threaded.shape)
op = boolean_builder("union", left, right, tolerance=1e-4)
op.Build()
fixer = ShapeFix_Shape(op.Shape())
fixer.Perform()
fixed = Solid(fixer.Shape())
back = step.read(step.write(fixed, "senkkopf"))
pr.out(
    f"  ShapeFix: solids={fixed.solid_count} valid={pr.is_valid(fixed)} V={fixed.volume:.4f}"
    f" -> STEP zurück valid={pr.is_valid(back)} V={back.volume:.4f}"
)

pr.out("")
pr.out("== 2. Kern + Netzprofil-Gang: Fuzzy-Stufen auf privaten Kopien ==")
m6 = standards.screw("M6")
from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeEdge, BRepBuilderAPI_MakeWire  # noqa: E402
from OCP.BRepLib import BRepLib  # noqa: E402
from OCP.BRepOffsetAPI import BRepOffsetAPI_MakePipeShell  # noqa: E402
from OCP.Geom import Geom_CylindricalSurface  # noqa: E402
from OCP.Geom2d import Geom2d_Line  # noqa: E402
from OCP.gp import gp_Ax2d, gp_Ax3, gp_Dir2d, gp_Pnt, gp_Pnt2d  # noqa: E402
from OCP.TopAbs import TopAbs_SOLID  # noqa: E402
from OCP.TopExp import TopExp_Explorer  # noqa: E402
from OCP.TopoDS import TopoDS  # noqa: E402

pitch, length = m6.pitch, 12.0
depth = pitch * 0.55
root_radius = 3.0 - depth
crest_radius = 3.0
turns = length / pitch + 2.0
surface = Geom_CylindricalSurface(gp_Ax3(), root_radius)
line2d = Geom2d_Line(gp_Ax2d(gp_Pnt2d(0.0, -pitch), gp_Dir2d(2.0 * math.pi, pitch)))
span = math.hypot(2.0 * math.pi, pitch) * turns
helix = BRepBuilderAPI_MakeEdge(line2d, surface, 0.0, span).Edge()
BRepLib.BuildCurves3d_s(helix)
spine = BRepBuilderAPI_MakeWire(helix).Wire()
inward = root_radius - 0.1
corners = (
    (inward, -pitch),
    (root_radius, -pitch),
    (crest_radius, -pitch + pitch * 0.25),
    (crest_radius, -pitch + pitch * 0.55),
    (root_radius, -pitch + pitch * 0.8),
    (inward, -pitch + pitch * 0.8),
)
outline = BRepBuilderAPI_MakeWire()
for index in range(len(corners)):
    a, b = corners[index - 1], corners[index]
    outline.Add(BRepBuilderAPI_MakeEdge(gp_Pnt(a[0], 0.0, a[1]), gp_Pnt(b[0], 0.0, b[1])).Edge())
pipe = BRepOffsetAPI_MakePipeShell(spine)
pipe.SetMode(True)
pipe.Add(outline.Wire())
pipe.Build()
pr.out(f"  pipe IsDone={pipe.IsDone()} MakeSolid={pipe.MakeSolid()}")
ridge = Solid(pipe.Shape())
pr.report("ridge roh", ridge)
slab = pr.cylinder(2 * crest_radius + 2.0, length)
trimmed = pr.intersect(ridge, slab)
explorer = TopExp_Explorer(trimmed.shape, TopAbs_SOLID)
trimmed_solid = Solid(TopoDS.Solid(explorer.Current()))
pr.report("ridge getrimmt (Solid aus dem Compound)", trimmed_solid)
core = pr.cylinder(2 * root_radius + 0.02, length)
for tol in (1e-3, 1e-4, 1e-6):
    left, _ = copy_shape(core.shape)
    right, _ = copy_shape(trimmed_solid.shape)
    op = boolean_builder("union", left, right, tolerance=tol)
    op.Build()
    if not op.IsDone():
        pr.out(f"  tol={tol}: nicht fertig")
        continue
    body = Solid(op.Shape())
    state = f"solids={body.solid_count} valid={pr.is_valid(body)} faces={body.face_count}"
    keeps = body.volume > core.volume * 1.05
    pr.out(f"  tol={tol}: {state} V={body.volume:.4f} Gang erhalten={keeps}")

pr.out("")
pr.out("== 3. Gegenfall: Vereinigung ohne Fuzzy verschluckt den Gang still ==")
left, _ = copy_shape(core.shape)
right, _ = copy_shape(trimmed_solid.shape)
op = boolean_builder("union", left, right, tolerance=None)
op.Build()
body = Solid(op.Shape())
pr.out(
    f"  ohne Fuzzy: solids={body.solid_count} closed={body.is_closed} valid={pr.is_valid(body)}"
    f" faces={body.face_count} V={body.volume:.4f} (Kern allein {core.volume:.4f})"
)

pr.out("")
pr.out("== 1c. Senkkopf als Compound (Kopf + Bolzen, keine Vereinigung): STEP-Rundreise ==")
from OCP.BRep import BRep_Builder  # noqa: E402
from OCP.TopoDS import TopoDS_Compound  # noqa: E402

compound = TopoDS_Compound()
builder = BRep_Builder()
builder.MakeCompound(compound)
builder.Add(compound, head.shape)
builder.Add(compound, threaded.shape)
pair = Solid(compound)
back = step.read(step.write(pair, "senkkopf-compound"))
pr.out(
    f"  Compound: solids={pair.solid_count} valid={pr.is_valid(pair)} V={pair.volume:.4f}"
    f" -> STEP zurück valid={pr.is_valid(back)} solids={back.solid_count} V={back.volume:.4f}"
)
