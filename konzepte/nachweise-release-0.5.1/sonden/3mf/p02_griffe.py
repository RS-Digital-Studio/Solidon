"""Sonde p02 (RM-258): Was kostet ein Griff nach dem GIL, während der Drache gelesen wird?

Ohne Qt. Ein Arbeiter fährt den Ladeweg des 3MF-Lesers wie ``ingest.ops.load``
(``scan_assembly``, dann ``read_objects``). Ein Nebenfaden spielt den
Hauptfaden: Er greift ``GRIFFE`` Mal hintereinander nach dem GIL
(``time.sleep(0)`` gibt ihn ab, der nächste Befehl braucht ihn wieder) — so
wie der Hauptfaden beim Malen für jedes Python-Ereignis, jeden Filter und
jede Python-Überschreibung einmal greift — und wiederholt das alle 50 ms.

Gemessen je Runde: wie lange die ``GRIFFE`` Griffe zusammen brauchen (die
„Malzeit“), der längste einzelne Griff und wo der Arbeiter dabei stand.
Umgebung: ``SONDE_TREE``, ``SONDE_TAG``, ``SONDE_SWITCH`` (Umschaltintervall),
``SONDE_GRIFFE`` (Vorgabe 100).
"""

from __future__ import annotations

import collections
import os
import sys
import threading
import time
from pathlib import Path

TREE = os.environ.get("SONDE_TREE", r"F:\3D Druck.review-051\wt-3mf")
sys.path.insert(0, TREE)
import app  # noqa: E402

assert str(Path(app.__file__).resolve()).lower().startswith(str(Path(TREE).resolve()).lower()), app.__file__
if os.environ.get("SONDE_FEIN"):
    import ctypes as _ctypes

    _ctypes.windll.winmm.timeBeginPeriod(1)
if os.environ.get("SONDE_SWITCH"):
    sys.setswitchinterval(float(os.environ["SONDE_SWITCH"]))
from app.core.ingest import threemf  # noqa: E402

if os.environ.get("SONDE_CHUNK"):
    threemf.XML_CHUNK = int(os.environ["SONDE_CHUNK"])
if os.environ.get("SONDE_BLOCK"):
    threemf.NUMBER_BLOCK = int(os.environ["SONDE_BLOCK"])

GRIFFE = int(os.environ.get("SONDE_GRIFFE", "100"))
tag = os.environ.get("SONDE_TAG", "x")
out = Path(__file__).resolve().parent / "out" / f"p02_{tag}.txt"
MODEL = Path(sys.argv[1] if len(sys.argv) > 1 else r"F:\3D Dateien\Mausoleum Dragon.3mf")
payload = MODEL.read_bytes()
done = threading.Event()
phase = ["vorher"]
worker_ident = [0]


def worker() -> None:
    worker_ident[0] = threading.get_ident()
    started = time.perf_counter()
    phase[0] = "scan"
    threemf.scan_assembly(payload)
    scanned = time.perf_counter()
    phase[0] = "read"
    findings: list = []
    threemf.read_objects(payload, findings)
    phase.append(f"scan {scanned - started:.2f} s, read {time.perf_counter() - scanned:.2f} s")
    done.set()


rounds: list[tuple[float, float, float, str]] = []
where: collections.Counter[str] = collections.Counter()
origin = time.perf_counter()
thread = threading.Thread(target=worker, daemon=True)
thread.start()
while not done.is_set():
    time.sleep(0.05)
    begin = time.perf_counter()
    longest = 0.0
    spot = ""
    for _ in range(GRIFFE):
        before = time.perf_counter()
        time.sleep(0)
        took = time.perf_counter() - before
        if took > longest:
            longest = took
            frame = sys._current_frames().get(worker_ident[0])
            names = []
            while frame is not None and len(names) < 3:
                names.append(f"{frame.f_code.co_name}:{frame.f_lineno}")
                frame = frame.f_back
            spot = " <- ".join(names)
    total = time.perf_counter() - begin
    rounds.append((begin - origin, total, longest, spot))
    if longest > 0.02:
        where[spot.split(" <- ")[0]] += 1
thread.join()
with out.open("w", encoding="utf-8") as stream:
    stream.write(f"Baum {TREE}\nUmschaltintervall {sys.getswitchinterval()}\nGriffe je Runde {GRIFFE}\n")
    stream.write(f"Arbeiter: {phase[-1]}\n")
    totals = sorted(entry[1] for entry in rounds)
    stream.write(
        f"Runden {len(rounds)}; Malzeit Median {totals[len(totals) // 2] * 1000:.0f} ms,"
        f" 95 % {totals[int(len(totals) * 0.95)] * 1000:.0f} ms, längste {totals[-1] * 1000:.0f} ms\n"
    )
    stream.write(f"längster Einzelgriff {max(entry[2] for entry in rounds) * 1000:.0f} ms\n")
    stream.write("Arbeiter bei Griffen über 20 ms: " + repr(where.most_common(12)) + "\n")
    stream.write("Runden über 200 ms (Beginn, Malzeit, längster Griff, Ort):\n")
    for begin, total, longest, spot in rounds:
        if total > 0.2:
            stream.write(f"  {begin:6.2f} s  {total * 1000:5.0f} ms  {longest * 1000:4.0f} ms  {spot}\n")
    stream.write("ERGEBNIS längste Malzeit %.0f ms\n" % (totals[-1] * 1000))
