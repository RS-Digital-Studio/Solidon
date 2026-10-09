"""Sonde: Untergrenze des Merkers und Wegwerf-Prototyp G1/G3 (nur Schätzung).

python probe_floor.py <modell> [--proto]

1. Netz laden und normalisieren (wie detect_stages.py), kalt erkennen.
2. Zwilling: dieselben Ecken, Dreiecke 0 und 1 vertauscht (neuer Abdruck,
   sonst bitgleich), warm erkennen (Merker über die Körpergrenze trifft).
3. Mit --proto: zusätzlich Lesung und tangentiale Trennung je Fleck über
   einen Inhaltsschlüssel gemerkt; Ergebnis gegen die kalte Erkennung des
   Zwillings verglichen (Abdruck aller Merkmale über feature_to_data).
"""

from __future__ import annotations

import functools
import hashlib
import json
import os
import sys
import tempfile
import time
from collections import Counter
from pathlib import Path

PROFILE_DIR = tempfile.mkdtemp(prefix="solidon-floor-")
for variable in ("APPDATA", "LOCALAPPDATA", "HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
    os.environ[variable] = PROFILE_DIR
sys.dont_write_bytecode = True
TREE = Path("F:/3D Druck")
sys.path.insert(0, str(TREE))

import numpy as np  # noqa: E402

import app  # noqa: E402

assert Path(app.__file__).resolve().parent.parent == TREE.resolve(), app.__file__

STAGES = (
    "_large_facet_faces",
    "_fitted",
    "_tangential_pieces",
    "_read_surface_support",
    "_connected_patches",
    "curvature_jumps",
    "find_helices",
    "_merged_cylinders",
    "slots_instead_of_half_bores",
    "_faces_finished_in",
    "patterns_instead_of_cells",
    "detect_holes",
    "detect_edge_loops",
    "_one_body",
)
spent = {}
calls = Counter()
stack = []
armed = [False]
proto = Counter()


def watch(module, name):
    original = getattr(module, name, None)
    if original is None:
        print("fehlt:", name)
        return

    @functools.wraps(original)
    def wrapped(*args, **kwargs):
        if not armed[0]:
            return original(*args, **kwargs)
        calls[name] += 1
        if name in stack:
            return original(*args, **kwargs)
        stack.append(name)
        started = time.process_time()
        try:
            return original(*args, **kwargs)
        finally:
            spent[name] = spent.get(name, 0.0) + time.process_time() - started
            stack.pop()

    setattr(module, name, wrapped)


def fingerprint(found, feature_to_data):
    rows = [feature_to_data(found[name]) for name in sorted(found)]
    text = json.dumps(rows, sort_keys=True, default=repr)
    return hashlib.blake2b(text.encode("utf-8"), digest_size=8).hexdigest()


def main():
    model = Path(sys.argv[1])
    use_proto = "--proto" in sys.argv[2:]
    from app.core.geom.mesh import MeshData, read_mesh
    from app.core.ingest.loader import normalise
    from app.core.perceive import features
    from app.core.scene.cache import feature_to_data
    import trimesh

    for name in STAGES:
        watch(features, name)

    proto_on = [use_proto]
    supports = {}
    pieces_memo = {}
    original_read = features._read_surface_support

    def read(body, patch, check_cancelled):
        if not proto_on[0]:
            return original_read(body, patch, check_cancelled)
        index = np.asarray(patch, dtype=np.int64)
        corners = np.ascontiguousarray(np.asarray(body.triangles)[index], dtype=np.float64)
        _unused, local = np.unique(np.asarray(body.faces)[index].ravel(), return_inverse=True)
        digest = hashlib.blake2b(digest_size=16)
        digest.update(corners.tobytes())
        digest.update(np.asarray(local, dtype=np.int64).tobytes())
        digest.update(bytes([bool(body.is_watertight), bool(body.is_winding_consistent), bool(features._coincident_vertices(body))]))
        key = digest.digest()
        known = supports.get(key)
        if known is not None:
            proto["Lesung Treffer"] += 1
            return known
        value = original_read(body, patch, check_cancelled)
        supports[key] = value
        proto["Lesung neu"] += 1
        return value

    features._read_surface_support = read
    original_pieces = features._tangential_pieces

    def pieces_of(body, mesh, patch, check_cancelled=None):
        if not proto_on[0]:
            return original_pieces(body, mesh, patch, check_cancelled)
        index = np.unique(np.asarray(list(patch), dtype=np.int64))
        corners = np.ascontiguousarray(np.asarray(body.triangles)[index], dtype=np.float64)
        neighbours, rows = features._neighbour_index(body)
        around = neighbours[index]
        spot = np.minimum(np.searchsorted(index, np.where(around >= 0, around, 0)), len(index) - 1)
        inside = (around >= 0) & (index[spot] == around)
        local = np.where(inside, spot, -1).astype(np.int64)
        seam_rows = np.where(inside, rows[index], -1)
        flat = seam_rows[seam_rows >= 0]
        order = np.argsort(flat, kind="stable").astype(np.int64)
        digest = hashlib.blake2b(digest_size=16)
        digest.update(corners.tobytes())
        digest.update(local.tobytes())
        digest.update(order.tobytes())
        digest.update(np.asarray(body.extents, dtype=np.float64).tobytes())
        key = digest.digest()
        known = pieces_memo.get(key)
        if known is not None:
            proto["Trennung Treffer"] += 1
            return [[int(index[position]) for position in piece] for piece in known]
        found = original_pieces(body, mesh, patch, check_cancelled)
        pieces_memo[key] = [np.searchsorted(index, np.asarray(piece, dtype=np.int64)).tolist() for piece in found]
        proto["Trennung neu"] += 1
        return found

    features._tangential_pieces = pieces_of

    mesh = normalise(read_mesh(model.read_bytes(), model.suffix.lower()), "mm").mesh
    features.forget_cache()
    started = time.process_time()
    cold = features.detect(mesh)
    print(f"{model.name}: {mesh.triangle_count} Dreiecke, kalt {time.process_time() - started:.2f} s, {len(cold)} Merkmale", flush=True)

    faces = np.asarray(mesh.raw.faces).copy()
    faces[[0, 1]] = faces[[1, 0]]
    twin = MeshData.of(trimesh.Trimesh(np.asarray(mesh.raw.vertices).copy(), faces, process=False))
    proto.clear()
    armed[0] = True
    started = time.process_time()
    warm = features.detect(twin)
    elapsed = time.process_time() - started
    armed[0] = False
    print(f"Zwilling warm {elapsed:.2f} s ({'mit' if use_proto else 'ohne'} Prototyp), {len(warm)} Merkmale", flush=True)
    for name, value in sorted(spent.items(), key=lambda item: -item[1]):
        print(f"  {name:30s} {value:7.2f}  {calls[name]}")
    for name, count in sorted(proto.items()):
        print(f"  Prototyp {name:20s} {count}")
    warm_print = fingerprint(warm, feature_to_data)
    if use_proto:
        proto_on[0] = False
        features.forget_cache()
        started = time.process_time()
        check = features.detect(twin)
        print(f"Zwilling kalt ohne Prototyp {time.process_time() - started:.2f} s", flush=True)
        check_print = fingerprint(check, feature_to_data)
        print("Abdruck warm", warm_print, "kalt", check_print, "GLEICH" if warm_print == check_print else "VERSCHIEDEN")
    else:
        print("Abdruck warm", warm_print)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
