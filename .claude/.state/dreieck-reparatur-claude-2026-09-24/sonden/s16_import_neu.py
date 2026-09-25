"""Sonde 16: Die Korpuskörper, deren Import am Stand 18:04 Löcher gefüllt hat, am aktuellen Stand neu einlesen."""
import json, time, hashlib
from pathlib import Path
from common import KUNDE, R, codes, facts
from app.core.geom.mesh import read_mesh
from app.core.ingest import threemf
from app.core.ingest.loader import normalise

print("repair.py", hashlib.sha1(Path(R.__file__).read_bytes()).hexdigest()[:8])
rows = [json.loads(l) for l in open(Path(__file__).with_name("s02.jsonl"), encoding="utf-8")]
todo = [r for r in rows if "after_ingest" in r and "repair.holes_filled" in r["ingest_codes"]]
for r in todo:
    path = KUNDE / r["file"]
    payload = path.read_bytes()
    if path.suffix.lower() == ".3mf":
        mesh = next(o.mesh for o in threemf.read_objects(payload) if str(o.name) == r["part"])
    else:
        mesh = read_mesh(payload, path.suffix.lower())
    t0 = time.perf_counter()
    res = normalise(mesh, "mm", weld_is_reading=path.suffix.lower() == ".stl")
    f = facts(res.mesh)
    old = r["after_ingest"]
    print(f"{r['file'][-55:]} | {r['part'][:22]}: {time.perf_counter()-t0:.1f}s")
    print(f"   18:04 : tight={old['tight']} open={old['open']} wound={old['wound']} vol={old['vol']}  {r['ingest_codes']}")
    print(f"   jetzt : tight={f['tight']} open={f['open']} wound={f['wound']} vol={f['vol']}  {codes(res.findings)}", flush=True)
