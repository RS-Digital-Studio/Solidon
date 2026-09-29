"""Sonde p06 (RM-258): Wie lange braucht ``hid.enumerate()`` auf dieser Maschine?

Die Suche nach einer 3D-Maus läuft im Hauptfaden (``spacemouse.HidReader.open``);
am Drachen stand der Qt-Takt bei 7,3 s darin (``p05_waechter.py``, Hauptfaden in
``HidD_GetProductString``). Fünf Läufe nacheinander, Anzahl der Geräte dazu.
"""
import time

import hid

for run in range(5):
    begin = time.perf_counter()
    devices = list(hid.enumerate())
    print(f"Lauf {run + 1}: {len(devices)} Geräte, {(time.perf_counter() - begin) * 1000:.0f} ms")
