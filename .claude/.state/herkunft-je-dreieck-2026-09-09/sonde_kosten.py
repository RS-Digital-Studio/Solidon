"""Wo die Zeit der Herkunftsübertragung hingeht — je Aufruf gezählt."""

from __future__ import annotations

import time

import numpy as np

from app.core.bootstrap import load_operations
from app.core.geom import attributes
from app.core.knowledge.profiles import make_profile
from app.core.scene.evaluate import evaluate
from app.core.scene.project import ProjectSources
from app.core.scene.project import load as load_project
from pathlib import Path

load_operations()

protokoll: list[tuple[int, int, int, float, float]] = []
echt_exakt = attributes._exact_origins
echt_nah = attributes._near_origins


def gezaehlt_exakt(body, sources, origins):
    start = time.perf_counter()
    offen = echt_exakt(body, sources, origins)
    protokoll.append((len(body.faces), sum(len(m.raw.faces) for m in sources), len(offen),
                      time.perf_counter() - start, 0.0))
    return offen


def gezaehlt_nah(result, sources, origins, rows):
    start = time.perf_counter()
    echt_nah(result, sources, origins, rows)
    letzte = protokoll[-1]
    protokoll[-1] = (*letzte[:4], time.perf_counter() - start)


attributes._exact_origins = gezaehlt_exakt
attributes._near_origins = gezaehlt_nah

projekt = load_project(Path("app/examples/dose-mit-deckel.p3d"))
start = time.perf_counter()
evaluate(projekt.document, make_profile("centauri-carbon-2", "petg"),
         sources=ProjectSources(projekt))
gesamt = time.perf_counter() - start

print(f"Auswertung gesamt: {gesamt:.2f} s, {len(protokoll)} Aufrufe")
print(f"{'Ergebnis':>10} {'Quellen':>10} {'offen':>8} {'exakt s':>9} {'nah s':>9}")
summe_exakt = summe_nah = 0.0
for ergebnis, quellen, offen, t_exakt, t_nah in protokoll:
    summe_exakt += t_exakt
    summe_nah += t_nah
    if t_exakt + t_nah > 0.05:
        print(f"{ergebnis:10d} {quellen:10d} {offen:8d} {t_exakt:9.3f} {t_nah:9.3f}")
print(f"Summe exakt {summe_exakt:.2f} s, Summe nah {summe_nah:.2f} s")
