"""Sonde RM-224: Wie oft ``normalise`` dieselbe Frage an dasselbe Netz stellt.

Zählt je Netz (Identität des ``trimesh.Trimesh``) die Aufrufe von
``face_components``, ``repair._edge_table``, ``unique_edges``,
``is_watertight``, ``face_adjacency`` und ``merge_vertices`` und die Zeit
darin. Zeiten unter Fremdlast sind nur Verhältnisse. Nur lesend.

Aufruf: python zaehl_fragen.py <baum> <datei>
"""

from __future__ import annotations

import collections
import sys
import time
from pathlib import Path

TREE = Path(sys.argv[1])
sys.path.insert(0, str(TREE))

import app  # noqa: E402

where = str(Path(app.__file__).resolve())
if not where.startswith(str(TREE.resolve())):
    raise SystemExit(f"falscher Baum geladen: {where}")
print(f"gemessen wird {where}")

import trimesh  # noqa: E402

import app.core.bootstrap  # noqa: E402,F401
from app.core.geom import mesh as M  # noqa: E402
from app.core.geom import repair as R  # noqa: E402
from app.core.geom.mesh import read_mesh  # noqa: E402
from app.core.ingest import loader  # noqa: E402

calls: dict[str, collections.Counter[int]] = collections.defaultdict(collections.Counter)
spent: collections.Counter[str] = collections.Counter()
names: dict[int, str] = {}


def body_of(argument: object) -> int:
    raw = getattr(argument, "raw", argument)
    key = id(raw)
    names.setdefault(key, f"netz{len(names) + 1}({len(getattr(raw, 'faces', ()))})")
    return key


def wrap_function(module: object, name: str) -> None:
    original = getattr(module, name)

    def counted(first, *args, **kwargs):
        calls[name][body_of(first)] += 1
        started = time.perf_counter()
        try:
            return original(first, *args, **kwargs)
        finally:
            spent[name] += time.perf_counter() - started

    setattr(module, name, counted)


for module in (M, R, loader):
    for name in ("face_components", "unique_edges"):
        if hasattr(module, name):
            wrap_function(module, name)
wrap_function(R, "_edge_table")

for attribute in ("is_watertight", "face_adjacency"):
    original_property = getattr(trimesh.Trimesh, attribute)
    getter = original_property.fget

    def make(getter=getter, attribute=attribute):
        def counted(self):
            calls[attribute][body_of(self)] += 1
            started = time.perf_counter()
            try:
                return getter(self)
            finally:
                spent[attribute] += time.perf_counter() - started

        return property(counted)

    setattr(trimesh.Trimesh, attribute, make())

path = Path(sys.argv[2])
suffix = path.suffix.lower()
payload = path.read_bytes()
mesh = read_mesh(payload, suffix)
started = time.perf_counter()
result = loader.normalise(mesh, unit="mm", weld_is_reading=suffix == ".stl")
total = time.perf_counter() - started
print(f"{path.name}: {mesh.triangle_count} Dreiecke, normalise {total:.3f} s")
for name, counter in calls.items():
    listed = ", ".join(f"{names[key]}×{count}" for key, count in counter.items())
    print(f"  {name}: {sum(counter.values())} Aufrufe, {spent[name]:.3f} s — {listed}")
