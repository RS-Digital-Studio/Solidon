"""S7: Kantenschlüssel nach einer Verschiebung — bleibt einer gleich?"""

import inspect
import _iso  # noqa: F401

from app.core.brep import edit
from app.core.geom import transform as T

print("transform:", [n for n in dir(T) if not n.startswith("_")][:30])
solid = edit.box(40.0, 30.0, 20.0)
keys_before = [edit.edge_key(e) for e in edit.edges_of(solid)]
print("edge_key Quelle:", inspect.getsource(edit.edge_key)[:600])
fn = getattr(T, "translation", None) or getattr(T, "translate", None)
matrix = fn((1.0, 2.0, 3.0)) if fn else None
print("matrix:", type(matrix).__name__)
moved = edit.transformed(solid, matrix)
keys_after = [edit.edge_key(e) for e in edit.edges_of(moved)]
print("vorher :", len(keys_before), keys_before[:3])
print("nachher:", len(keys_after), keys_after[:3])
print("gemeinsam:", len(set(keys_before) & set(keys_after)))
