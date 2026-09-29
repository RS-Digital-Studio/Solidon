"""Sonde: welche Kurvenart hat die Lochkante nach der Booleschen Operation?"""
import sys
sys.path.insert(0, r"F:/3D Druck.review-050/wt-p66")
sys.path.insert(0, r"F:/3D Druck.review-050/wt-p66/tests")
from OCP.BRepAdaptor import BRepAdaptor_Curve, BRepAdaptor_Surface
from OCP.GeomAbs import GeomAbs_CurveType, GeomAbs_SurfaceType
from app.core.brep import profiles as brep_profiles
from app.core.sketch.profile import regions_of
from app.core.sketch.solver import solve_sketch
from app.core.types import Sketch
from test_sketch_curves import _ellipse_element
from helpers import exact_kernel

brep = exact_kernel()
opening = Sketch("plane:xy", (_ellipse_element(9.0, 4.0, 25.0, (3.0, 2.0)),))
hole = brep_profiles.extrude(regions_of(solve_sketch(opening))[0], 20.0)
print("Loch allein:", sorted(str(GeomAbs_CurveType(BRepAdaptor_Curve(e).GetType())) for e in hole.edges()))
print("Loch Flächen:", sorted(str(GeomAbs_SurfaceType(BRepAdaptor_Surface(f).GetType())) for f in hole.faces()))
drilled = brep.boolean("difference", [brep.box(40.0, 30.0, 8.0), brep.moved(hole, (0.0, 0.0, -5.0))])
print("gebohrt:", sorted(str(GeomAbs_CurveType(BRepAdaptor_Curve(e).GetType())) for e in drilled.edges()))
print("gebohrt Flächen:", sorted(str(GeomAbs_SurfaceType(BRepAdaptor_Surface(f).GetType())) for f in drilled.faces()))

from OCP.BRep import BRep_Tool
from OCP.TopoDS import TopoDS
from app.core.brep.edit import face_loops
for edge in drilled.edges():
    curve = BRepAdaptor_Curve(edge)
    if str(GeomAbs_CurveType(curve.GetType())).endswith("BSplineCurve"):
        print("Kantentoleranz:", BRep_Tool.Tolerance_s(TopoDS.Edge(edge)))
for index in range(len(drilled.faces())):
    for loop in face_loops(drilled, index):
        for piece in loop.pieces:
            if piece.kind in ("ellipse", "elliptical_arc", "curve"):
                print(index, piece.kind, piece.centre, piece.radius, piece.major_end, piece.minor_end)
