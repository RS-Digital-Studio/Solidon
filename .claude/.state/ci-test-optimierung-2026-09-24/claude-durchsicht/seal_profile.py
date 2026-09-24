import sys, time, cProfile, pstats
sys.path.insert(0, r"F:\3D Druck")
from tests.test_seal_geometry import path
from app.core.geom.seal import seal_geometry
from app.core.geom import mesh as m
from app.core.knowledge.parts.range_check import local_wall_thickness
r = seal_geometry(path(), groove_width=12.0, groove_depth=12.0, protrusion=0, gasket_width=12.0, section="round", offset=5)
pairs=[0]; orig=m._ray_triangle_parameters
def counted(*a):
    t,i=orig(*a); pairs[0]+=t.size; return t,i
m._ray_triangle_parameters=counted
b=r.gasket.raw.bounds; print("bounds", b.tolist())
pr=cProfile.Profile(); pr.enable(); w=local_wall_thickness(r.gasket); pr.disable()
print("wall", w, "pairs", pairs[0], "of", len(r.gasket.raw.faces)**2)
pstats.Stats(pr).sort_stats("tottime").print_stats(8)
