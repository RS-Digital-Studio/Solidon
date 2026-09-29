"""Sonde p31b: Wo liegt die verbleibende Lücke beim gestückelten Lesen mit Frost?

Phasen einzeln gemessen: Parsen (256-KB-Stücke, Frost je Stück), Zahlen lesen,
Baum freigeben (am Stück gegen stückweise ``del parent[:n]``), ``gc.unfreeze``.
"""
from __future__ import annotations

import gc
import sys
import threading
import time
import zipfile
from xml.etree import ElementTree as ET

sys.path.insert(0, ".")
from p31_xml_freeze import CHUNK, CORE, MODEL, Ticker, numbers  # noqa: E402

ticker = Ticker()
out = open(sys.argv[1], "w", encoding="utf-8", buffering=1)
with zipfile.ZipFile(MODEL) as container:
    data = container.read("3D/3dmodel.model")


def phase(name, action):
    ticker.reset()
    started = time.perf_counter()
    value = action()
    out.write(f"  {name}: {time.perf_counter() - started:.2f} s, Lücke {ticker.longest * 1000:.0f} ms\n")
    return value


def parse():
    parser = ET.XMLParser()
    for start in range(0, len(data), CHUNK):
        parser.feed(data[start : start + CHUNK])
        gc.freeze()
    return parser.close()


def free_in_slices(root):
    for mesh in root.iter(f"{CORE}mesh"):
        for part in list(mesh):
            while len(part):
                del part[:65536]


for mode in ("am_stueck", "in_scheiben", "am_stueck", "in_scheiben"):
    out.write(f"{mode}:\n")
    gc.collect()
    root = phase("parsen", parse)
    phase("zahlen", lambda: numbers(root))
    if mode == "in_scheiben":
        phase("freigeben", lambda: free_in_slices(root))
    holder = [root]
    del root
    phase("baum loslassen", lambda: holder.clear())
    phase("unfreeze", gc.unfreeze)
    phase("collect", gc.collect)
ticker.stop = True
