"""Sonde 11: Hängt das ausdrückliche Reparieren (mit Durchdringungsprüfung und
Vereinigung) an plattformabhängigen Rechnungen? Mit dem Rauschen aus
tests/test_platform_identity.platform_noise (ein ULP auf BLAS/einsum/LAPACK/
Winkelfunktionen)."""

from __future__ import annotations

import hashlib
import sys

import numpy as np

from common import KUNDE, MESHES, R, ROOT, MeshData, codes, welded

sys.path.insert(0, str(ROOT))
from tests.test_platform_identity import platform_noise  # noqa: E402

from app.core.ingest import threemf  # noqa: E402
from app.core.ingest.loader import normalise  # noqa: E402


def fingerprint(result) -> str:
    body = result.mesh.raw
    digest = hashlib.blake2b(np.ascontiguousarray(body.vertices, dtype=np.float64).tobytes(), digest_size=8)
    digest.update(np.ascontiguousarray(body.faces, dtype=np.int64).tobytes())
    digest.update(repr(result.mesh.slots[:50]).encode())
    return f"{digest.hexdigest()} {codes(result.findings)}"


def cases():
    yield "broken_selfint", welded(MESHES / "broken_selfint.stl")
    for part in ("Kofferschale B",):
        payload = (KUNDE / "3D Drucker" / "15_CC2-Werkzeugbox" / "CC2-Werkzeugbox_Druckbereit.3mf").read_bytes()
        obj = next(o for o in threemf.read_objects(payload) if str(o.name) == part)
        yield part, normalise(obj.mesh, "mm").mesh
    payload = (KUNDE / "drill-holder.3mf").read_bytes()
    obj = next(o for o in threemf.read_objects(payload) if str(o.name) == "Körper 1")
    yield "drill-holder Körper 1", normalise(obj.mesh, "mm").mesh
    yield "generated_figure (roh)", welded(MESHES / "generated_figure.stl")
    yield "partially_open (roh)", welded(MESHES / "partially_open.stl")


for name, mesh in cases():
    quiet = fingerprint(R.repair(mesh, self_intersections=True, inspect_intersections=True))
    with platform_noise():
        noisy = fingerprint(R.repair(mesh, self_intersections=True, inspect_intersections=True))
    print(f"{name}: {'GLEICH' if quiet == noisy else 'VERSCHIEDEN'}\n   ruhig : {quiet}\n   Rausch: {noisy}", flush=True)
