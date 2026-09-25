"""Sonde 7b: Naht-zusammengesetzt.stl im Dokumentweg — Import allein, Import + Reparieren."""
from pathlib import Path
from common import KUNDE
import s07_befunde_ueber_schritte as S

naht = KUNDE / "3D Drucker" / "16_CC2-Auffangrinne" / "Naht-zusammengesetzt.stl"
S.run(naht, [])
S.run(naht, [{}])
S.run(naht, [{}, {"self_intersections": True}])
