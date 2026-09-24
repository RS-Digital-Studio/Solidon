import sys, time
sys.path.insert(0, r"F:\3D Druck")
sys.path.insert(0, r"F:\3D Druck\tests")
from tests.test_seal_geometry import path
from app.core.geom.seal import seal_geometry
from app.core.knowledge.parts.range_check import has_self_intersections, local_wall_thickness
for height in (1.2, 12.0):
    t=time.perf_counter()
    r = seal_geometry(path(), groove_width=height, groove_depth=height, protrusion=0, gasket_width=height, section="round", offset=5)
    t1=time.perf_counter()
    print(height, "seal", round(t1-t,2), "faces", len(r.gasket.raw.faces), flush=True)
    w = local_wall_thickness(r.gasket); t2=time.perf_counter()
    print(height, "wall", round(t2-t1,2), w, flush=True)
    s = has_self_intersections(r.gasket); t3=time.perf_counter()
    print(height, "selfint", round(t3-t2,2), s, flush=True)
