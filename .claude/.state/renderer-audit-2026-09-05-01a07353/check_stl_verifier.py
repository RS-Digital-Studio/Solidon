"""Prüft den unabhängigen STL-Vergleich auch gegen gezielt beschädigte Exporte."""

from pathlib import Path
import json
import struct
import tempfile

import numpy as np

from stl_export_checks import inspect


def write(path, triangles):
    """Kleine binäre STL ohne irgendeinen App- oder Bibliotheksexporter schreiben."""
    triangles = np.asarray(triangles, dtype="<f4")
    with path.open("wb") as handle:
        handle.write("Unabhängige Formatprüfung".encode("utf-8").ljust(80, b" "))
        handle.write(struct.pack("<I", len(triangles)))
        for triangle in triangles:
            handle.write(struct.pack("<12fH", 0.0, 0.0, 0.0, *triangle.ravel(), 0))


vertices = np.array([[0, 0, 0], [2, 0, 0], [0, 3, 0], [0, 0, 4]], dtype=float)
faces = np.array([[0, 2, 1], [0, 1, 3], [0, 3, 2], [1, 2, 3]])
second = vertices + [7.123456789, -0.234567891, 1.987654321]
snapshots = [
    {"id": "one", "name": "Eins", "plate": 0, "vertices": vertices, "faces": faces},
    {"id": "two", "name": "Zwei", "plate": 1, "vertices": second, "faces": faces},
]
whole = np.concatenate([vertices[faces], second[faces]])
reports = {}
with tempfile.TemporaryDirectory(prefix="solidon-stl-oracle-") as folder:
    folder = Path(folder)
    a, b, combined = folder / "a.stl", folder / "b.stl", folder / "combined.stl"
    write(a, vertices[faces])
    write(b, second[faces])
    reports["individual"] = inspect(snapshots, [b, a])
    assert reports["individual"]["passed"]
    assert reports["individual"]["grouping"] == "one_file_per_body"
    write(combined, np.roll(whole[::-1], 1, axis=1))
    reports["combined_reordered"] = inspect(snapshots, [combined])
    assert reports["combined_reordered"]["passed"]
    assert reports["combined_reordered"]["grouping"] == "combined_stl"

    changed = whole.copy()
    changed[-1] = changed[-1, [0, 2, 1]]
    variants = {
        "flipped_face": changed,
        "wrong_translation": whole + [0.001, 0, 0],
        "missing_body": vertices[faces],
        "duplicate_face": np.concatenate([whole, whole[:1]]),
        "missing_face": whole[:-1],
    }
    for name, triangles in variants.items():
        write(combined, triangles)
        reports[name] = inspect(snapshots, [combined])
        assert not reports[name]["passed"], name
        assert not reports[name]["world_triangles_match"], name

print(json.dumps({name: {key: report[key] for key in
    ("passed", "world_triangles_match", "grouping", "metric_checks")}
    for name, report in reports.items()}, ensure_ascii=False, indent=2))
