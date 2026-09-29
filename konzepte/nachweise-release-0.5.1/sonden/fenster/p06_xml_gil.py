"""Sonde p06: wie lange hält das Lesen des Modell-XML den GIL?

Ein Nebenfaden tickt alle 5 ms; gemessen wird seine längste Lücke, während der
Hauptfaden das Modell-XML des Drachen liest — einmal am Stück
(``ET.fromstring``, der alte Weg), einmal in 1-MB-Häppchen (``XMLParser.feed``),
abwechselnd, je drei Läufe. Dazu die Zahlen: alter ``_read_numbers`` gegen
Blöcke."""

from __future__ import annotations

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


def whole(container, entry):
    return ET.fromstring(container.read(entry))


def chunked(container, entry):
    parser = ET.XMLParser()
    with container.open(entry) as stream:
        while chunk := stream.read(1 << 20):
            parser.feed(chunk)
    return parser.close()


def numbers_old(vertices, triangles):
    points = np.array([(e.get("x"), e.get("y"), e.get("z")) for e in vertices], dtype=np.float64)
    faces = np.array([(e.get("v1"), e.get("v2"), e.get("v3")) for e in triangles], dtype=np.int64)
    return points, faces


def _blocks(parent, names, dtype, size=65536):
    a, b, c = names
    source = iter(parent)
    parts = []
    while block := list(islice(source, size)):
        parts.append(np.array([(e.get(a), e.get(b), e.get(c)) for e in block], dtype=dtype))
    return np.concatenate(parts) if parts else np.array([], dtype=dtype)


def numbers_new(vertices, triangles):
    return _blocks(vertices, "xyz", np.float64), _blocks(triangles, ("v1", "v2", "v3"), np.int64)


ticker = Ticker()
out = open(sys.argv[1] if len(sys.argv) > 1 else "out/p06_xml_gil.txt", "w", encoding="utf-8", buffering=1)
with zipfile.ZipFile(MODEL) as container:
    entries = [n for n in container.namelist() if n.endswith(".model")]
    out.write(f"Modelldateien: {entries}\n")
    results = {"whole": [], "chunked": [], "old": [], "new": []}
    for round_ in range(3):
        for name, fn in (("whole", whole), ("chunked", chunked)) if round_ % 2 == 0 else (("chunked", chunked), ("whole", whole)):
            ticker.reset()
            start = time.perf_counter()
            roots = [fn(container, e) for e in entries]
            took = time.perf_counter() - start
            results[name].append((took, ticker.longest))
            out.write(f"{name:8s} Lauf {round_}: {took:.2f} s, längste Lücke {ticker.longest * 1000:.0f} ms\n")
        mesh = next(m for r in roots for m in r.iter(f"{CORE}mesh"))
        v, t = mesh.find(f"{CORE}vertices"), mesh.find(f"{CORE}triangles")
        for name, fn in (("old", numbers_old), ("new", numbers_new)) if round_ % 2 == 0 else (("new", numbers_new), ("old", numbers_old)):
            ticker.reset()
            start = time.perf_counter()
            p, f = fn(v, t)
            took = time.perf_counter() - start
            results[name].append((took, ticker.longest))
            out.write(f"{name:8s} Lauf {round_}: {took:.2f} s, längste Lücke {ticker.longest * 1000:.0f} ms, {p.shape} {f.shape}\n")
        pa, fa = numbers_old(v, t)
        pb, fb = numbers_new(v, t)
        out.write(f"  gleich: {np.array_equal(pa, pb)} {np.array_equal(fa, fb)}\n")
        del roots
    for name, rows in results.items():
        out.write(f"MEDIAN {name}: {statistics.median(r[0] for r in rows):.2f} s, Lücke {statistics.median(r[1] for r in rows) * 1000:.0f} ms\n")
