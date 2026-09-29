"""Sonde p04 (RM-258): wie lange hält ein Block den GIL am Stück?

Ohne Qt. Misst je Blockgröße die Zeit von ``np.array`` über die Tupel eines
Blocks, von ``del node[:n]`` und von ``XMLParser.feed`` je Stückgröße — das sind
die Strecken, in denen der Leser nie nach wartenden Fäden sieht.
"""
import gc
import time
import xml.etree.ElementTree as ET

import numpy as np

vertex = b'<vertex x="12.345678" y="-3.2109876" z="45.678901"/>'
xml = b"<vertices>" + vertex * 300_000 + b"</vertices>"
for chunk in (256 * 1024, 64 * 1024, 32 * 1024, 16 * 1024):
    parser = ET.XMLParser()
    worst = 0.0
    for start in range(0, len(xml), chunk):
        begin = time.perf_counter()
        parser.feed(xml[start : start + chunk])
        gc.freeze()
        worst = max(worst, time.perf_counter() - begin)
    root = parser.close()
    gc.unfreeze()
    print(f"feed {chunk // 1024:4d} KB: längstes Stück {worst * 1000:6.2f} ms")
children = list(root)
for block in (65536, 16384, 8192, 4096, 2048):
    rows = [(entry.get("x"), entry.get("y"), entry.get("z")) for entry in children[:block]]
    begin = time.perf_counter()
    np.array(rows, dtype=np.float64)
    took = time.perf_counter() - begin
    print(f"np.array {block:6d}: {took * 1000:6.2f} ms")
for block in (65536, 8192, 4096):
    node = ET.fromstring(b"<v>" + vertex * block + b"</v>")
    begin = time.perf_counter()
    del node[:block]
    print(f"del {block:6d}: {(time.perf_counter() - begin) * 1000:6.2f} ms")
