"""Sonde 7d: generated_figure — Laden, dann Reparieren mit Kleinstteile entfernen: fällt ingest.not_watertight?"""
import hashlib
from pathlib import Path
from common import MESHES, R
import s07_befunde_ueber_schritte as S
print("repair.py", hashlib.sha1(Path(R.__file__).read_bytes()).hexdigest()[:8])
S.run(MESHES / "generated_figure.stl", [{"small_components": True}])
