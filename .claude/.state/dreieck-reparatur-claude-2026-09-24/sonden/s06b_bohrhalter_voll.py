"""Sonde 6b: Ist die verworfene Vereinigung des Bohrhalters in Wahrheit schnittfrei?"""
import time
import numpy as np
from common import KUNDE, R, MeshData, facts
from app.core.geom import boolean as B, intersections as X
from app.core.geom.mesh import face_components
from app.core.ingest import threemf
from app.core.ingest.loader import normalise

payload = (KUNDE / "drill-holder.3mf").read_bytes()
obj = next(o for o in threemf.read_objects(payload) if str(o.name) == "Körper 1")
m = normalise(obj.mesh, "mm").mesh
pieces = [MeshData.of(m.raw.submesh([p], append=True, repair=False)) for p in face_components(m.raw)]
out = B.boolean("union", pieces, stages=("direct",)).mesh
t0 = time.perf_counter()
full, complete = X.crossing_faces(out.raw.vertices, out.raw.faces)
print("Vereinigung ohne Budget geprüft:", len(full), "Dreiecke schneiden, vollständig", complete, f"{time.perf_counter()-t0:.2f}s")
s = X._surface(out.raw.vertices, out.raw.faces)
plan = X._plan(s.low, s.high)
e = X._entries(s.low, s.high, plan)
print("Sweep-Paare der Vereinigung:", int(e.counts.sum()), "Plan", plan)
print("Teile der Vereinigung:", [len(p) for p in face_components(out.raw)])
