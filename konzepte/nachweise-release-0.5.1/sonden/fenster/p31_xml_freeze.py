"""Sonde p31: Modell-XML des Drachen in Häppchen lesen, mit eingefrorenem Speicherbereiniger.

Ein Nebenfaden tickt alle 5 ms und misst seine längste Lücke, während der
Hauptfaden das Modell-XML liest. Varianten, abwechselnd, je drei Läufe:

- ``ganz``: ``ET.fromstring`` (heute)
- ``stuecke``: ``XMLParser.feed`` in 256-KB-Stücken
- ``stuecke_frost``: dasselbe, nach jedem Stück ``gc.freeze()`` — die gebauten
  Elemente zählen für spätere Läufe des Speicherbereinigers nicht mehr mit;
  ``gc.unfreeze()`` erst, wenn der Baum wieder weg ist

Gemessen wird Parsen plus Zahlenlesen (Ecken und Dreiecke als Felder), weil
die Läufe des Speicherbereinigers erst dort teuer wurden.
"""

from __future__ import annotations

import gc
import statistics
import sys
import threading
import time
import zipfile
from itertools import islice
from xml.etree import ElementTree as ET

import numpy as np

MODEL = r"F:\3D Dateien\Mausoleum Dragon.3mf"
CORE = "{http://schemas.microsoft.com/3dmanufacturing/core/2015/02}"
CHUNK = 256 * 1024


class Ticker:
    def __init__(self) -> None:
        self.last = time.perf_counter()
        self.longest = 0.0
        self.stop = False
        self.thread = threading.Thread(target=self.run, daemon=True)
        self.thread.start()

    def run(self) -> None:
        while not self.stop:
            now = time.perf_counter()
            self.longest = max(self.longest, now - self.last)
            self.last = now
            time.sleep(0.005)

    def reset(self) -> None:
        self.last = time.perf_counter()
        self.longest = 0.0


def numbers(root) -> tuple[int, int]:
    total_v = total_t = 0
    for mesh in root.iter(f"{CORE}mesh"):
        vertices = mesh.find(f"{CORE}vertices")
        triangles = mesh.find(f"{CORE}triangles")
        for parent, names, dtype in ((vertices, "xyz", np.float64), (triangles, ("v1", "v2", "v3"), np.int64)):
            a, b, c = names
            source = iter(parent)
            while block := list(islice(source, 65536)):
                array = np.array([(e.get(a), e.get(b), e.get(c)) for e in block], dtype=dtype)
                if dtype is np.float64:
                    total_v += len(array)
                else:
                    total_t += len(array)
    return total_v, total_t


def ganz(data: bytes, frost: bool):
    return ET.fromstring(data)


def stuecke(data: bytes, frost: bool):
    parser = ET.XMLParser()
    for start in range(0, len(data), CHUNK):
        parser.feed(data[start : start + CHUNK])
        if frost:
            gc.freeze()
    return parser.close()


ticker = Ticker()
out = open(sys.argv[1] if len(sys.argv) > 1 else "out/p31_xml_freeze.txt", "w", encoding="utf-8", buffering=1)
with zipfile.ZipFile(MODEL) as container:
    entries = [n for n in container.namelist() if n.endswith(".model")]
    blobs = {entry: container.read(entry) for entry in entries}
out.write(f"Modelldateien: {[(e, len(b)) for e, b in blobs.items()]}\n")
variants = (("ganz", ganz, False), ("stuecke", stuecke, False), ("stuecke_frost", stuecke, True))
results: dict[str, list[tuple[float, float]]] = {name: [] for name, _f, _x in variants}
for round_ in range(3):
    for name, parse, frost in variants:
        gc.collect()
        time.sleep(0.2)
        ticker.reset()
        started = time.perf_counter()
        counted = (0, 0)
        for data in blobs.values():
            root = parse(data, frost)
            if frost:
                gc.freeze()
            found = numbers(root)
            counted = (counted[0] + found[0], counted[1] + found[1])
            del root
        if frost:
            gc.unfreeze()
        took = time.perf_counter() - started
        results[name].append((took, ticker.longest))
        out.write(f"Runde {round_ + 1} {name}: {took:.2f} s, längste Lücke {ticker.longest * 1000:.0f} ms, Ecken/Dreiecke {counted}\n")
for name, values in results.items():
    out.write(
        f"MEDIAN {name}: {statistics.median(v[0] for v in values):.2f} s, "
        f"Lücke {statistics.median(v[1] for v in values) * 1000:.0f} ms\n"
    )
ticker.stop = True
out.close()
