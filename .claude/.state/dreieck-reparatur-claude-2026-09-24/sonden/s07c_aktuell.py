"""Sonde 7c: Dokumentweg am aktuellen Stand — broken_selfint (zwei Reparaturschritte), generated_figure (Laden, Laden+Reparieren)."""
import hashlib
from pathlib import Path
from common import MESHES, R
import s07_befunde_ueber_schritte as S
print("repair.py", hashlib.sha1(Path(R.__file__).read_bytes()).hexdigest()[:8])
S.run(MESHES / "broken_selfint.stl", [{}, {"self_intersections": True}])
S.run(MESHES / "generated_figure.stl", [])
S.run(MESHES / "generated_figure.stl", [{}])
