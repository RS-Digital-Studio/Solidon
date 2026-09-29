"""Sonde p05 (RM-258): ein Wächter außerhalb des Prozesses für Lücken, in denen niemand den GIL bekommt.

Der Beobachterfaden in ``p01_nativ.py`` braucht selbst den GIL: Hält ihn ein
Faden in C-Code am Stück, sieht er die Lücke erst hinterher. Dieser Prozess
liest den letzten Qt-Takt aus einer gemeinsamen Datei (``mmap``, ein
``double`` aus ``time.monotonic()`` — unter Windows dieselbe Uhr in allen
Prozessen) und holt ``py-spy dump --native``, sobald er länger als die
Schwelle steht.

Aufruf (von p01): ``p05_waechter.py <pid> <mmap-datei> <ausgabeordner> <schwelle> <ab_s> <ursprung>``
"""

from __future__ import annotations

import mmap
import struct
import subprocess
import sys
import time
from pathlib import Path

PYSPY = r"F:\3D Druck\.venv\Scripts\py-spy.exe"
pid, shared, target_dir = int(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3])
limit, after, origin = float(sys.argv[4]), float(sys.argv[5]), float(sys.argv[6])
target_dir.mkdir(exist_ok=True)
with shared.open("r+b") as handle:
    view = mmap.mmap(handle.fileno(), 8)
count = 0
while count < 40:
    time.sleep(0.01)
    (last,) = struct.unpack_from("d", view, 0)
    if last < 0:
        break
    now = time.monotonic()
    if now - origin < after or last == 0.0 or now - last < limit:
        continue
    count += 1
    for _attempt in range(4):
        # Ein Faden, der gerade endet, lässt py-spy mit "Zugriff verweigert"
        # abbrechen; gleich noch einmal.
        result = subprocess.run(
            [PYSPY, "dump", "--native", "--pid", str(pid)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        if result.returncode == 0:
            break
    name = f"{count:02d}_{now - origin:06.2f}s_steht{now - last:.2f}.txt"
    (target_dir / name).write_text(f"exit {result.returncode}\n{result.stdout}\n--- stderr\n{result.stderr}", "utf-8")
    # Bis der Takt wieder läuft, nicht dieselbe Lücke zweimal.
    while True:
        (again,) = struct.unpack_from("d", view, 0)
        if again != last or again < 0:
            break
        time.sleep(0.01)
