"""S3: Analytische Form als NURBS — Solidon-Erkennung gegen vorhandenes OCCT."""

from collections import Counter
import _iso  # noqa: F401

from OCP.BRep import BRep_Tool
from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert
from OCP.BRepCheck import BRepCheck_Analyzer
from OCP.BRepPrimAPI import BRepPrimAPI_MakeTorus
from OCP.gp import gp_Cone, gp_Cylinder, gp_Pln, gp_Sphere
from OCP.TopAbs import TopAbs_FACE
from OCP.TopExp import TopExp_Explorer
import OCP.TopoDS as _TD


def to_face(shape):
    for holder in (getattr(_TD, 'TopoDS', None), _TD, getattr(_TD, 'topods', None)):
        if holder is None:
            continue
        for cand in ('Face_s', 'Face', 'face'):
            fn = getattr(holder, cand, None)
            if fn is not None:
                try:
                    return fn(shape)
                except Exception:
                    continue
    raise RuntimeError('kein Face-Cast gefunden: ' + repr([n for n in dir(_TD) if 'ace' in n]))

from app.core.brep import edit, step
from app.core.brep.features import features_of
from app.core.brep.kernel import Solid

body = edit.cut_bore(edit.box(40, 30, 10), position=(0, 0, 5), direction=(0, 0, 1), diameter=6, depth=20)
nurbs = Solid(BRepBuilderAPI_NurbsConvert(body.shape, True).Shape())
roundtrip = step.read(step.write(nurbs))
for label, current in (("analytisch", body), ("nurbs", nurbs), ("nurbs-step-rundreise", roundtrip)):
    print(label, "valid:", BRepCheck_Analyzer(current.shape).IsValid(),
          "features_of:", dict(Counter(f.kind for f in features_of(current).values())))

try:
    from OCP.ShapeAnalysis import ShapeAnalysis_CanonicalRecognition
except ImportError as e:
    print("ShapeAnalysis_CanonicalRecognition: nicht importierbar", e)
    ShapeAnalysis_CanonicalRecognition = None

if ShapeAnalysis_CanonicalRecognition is not None:
    print("Methoden:", [n for n in dir(ShapeAnalysis_CanonicalRecognition) if n.startswith("Is")])
    ex = TopExp_Explorer(roundtrip.shape, TopAbs_FACE)
    found = Counter()
    gaps = []
    radii = []
    while ex.More():
        face = to_face(ex.Current())
        rec = ShapeAnalysis_CanonicalRecognition(face)
        pln, cyl, cone, sph = gp_Pln(), gp_Cylinder(), gp_Cone(), gp_Sphere()
        if rec.IsPlane(1e-6, pln):
            found["plane"] += 1
        elif rec.IsCylinder(1e-6, cyl):
            found["cylinder"] += 1
            radii.append(cyl.Radius())
        elif rec.IsCone(1e-6, cone):
            found["cone"] += 1
        elif rec.IsSphere(1e-6, sph):
            found["sphere"] += 1
        else:
            found["unclassified"] += 1
        try:
            gaps.append(rec.GetGap())
        except Exception:  # noqa: BLE001
            pass
        ex.Next()
    print("CanonicalRecognition am NURBS-STEP-Körper:", dict(found), "Zylinderdurchmesser:", [2 * r for r in radii],
          "max GetGap:", max(gaps) if gaps else None)

# Torus: SurfToAnaSurf
try:
    from OCP.GeomConvert import GeomConvert_SurfToAnaSurf

    torus = Solid(BRepBuilderAPI_NurbsConvert(BRepPrimAPI_MakeTorus(15.0, 3.0).Shape(), True).Shape())
    print("Solidon features_of am NURBS-Torus:", dict(Counter(f.kind for f in features_of(torus).values())))
    print("Solidon features_of am analytischen Torus:",
          dict(Counter(f.kind for f in features_of(Solid(BRepPrimAPI_MakeTorus(15.0, 3.0).Shape())).values())))
    ex = TopExp_Explorer(torus.shape, TopAbs_FACE)
    while ex.More():
        face = to_face(ex.Current())
        surf = BRep_Tool.Surface_s(face)
        conv = GeomConvert_SurfToAnaSurf(surf)
        out = conv.ConvertToAnalytical(1e-6)
        print("SurfToAnaSurf:", type(out).__name__ if out is not None else None,
              "gap:", conv.Gap())
        if out is not None and hasattr(out, "MajorRadius"):
            print("   R:", out.MajorRadius(), "r:", out.MinorRadius())
        ex.Next()
except Exception as e:  # noqa: BLE001
    print("SurfToAnaSurf-Sonde:", repr(e))
