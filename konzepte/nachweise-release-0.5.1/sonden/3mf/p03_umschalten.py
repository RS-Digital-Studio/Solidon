"""Sonde p03 (RM-258): GIL-Griff und Durchsatz je Umschaltintervall und Zeitgeberauflösung.

Ohne Qt, ohne Solidon. Zwei Fragen je Einstellung:

1. **Griff:** Ein rechnender Python-Faden läuft; ein zweiter greift 200 Mal
   nach dem GIL (``time.sleep(0)``). Wie lange dauert ein Griff?
2. **Durchsatz:** Zwei rechnende Python-Fäden 2 s lang gegeneinander — wie
   viel schaffen sie zusammen, verglichen mit einem allein?

``argv[1]``: Umschaltintervall in Sekunden; ``argv[2]``: ``1`` = vorher
``timeBeginPeriod(1)``.
"""

from __future__ import annotations

import ctypes
import statistics
import sys
import threading
import time

interval = float(sys.argv[1])
fine = sys.argv[2] == "1"
if len(sys.argv) > 3 and sys.argv[3] == "1":
    # Windows 11 darf die Auflösung eines unsichtbaren Prozesses übergehen;
    # PROCESS_POWER_THROTTLING_IGNORE_TIMER_RESOLUTION verlangt, dass sie gilt.
    class _State(ctypes.Structure):
        _fields_ = [("Version", ctypes.c_ulong), ("ControlMask", ctypes.c_ulong), ("StateMask", ctypes.c_ulong)]

    state = _State(1, 0x4, 0)
    ok = ctypes.windll.kernel32.SetProcessInformation(
        ctypes.windll.kernel32.GetCurrentProcess(), 4, ctypes.byref(state), ctypes.sizeof(state)
    )
    print("IGNORE_TIMER_RESOLUTION gesetzt:", bool(ok))
if fine:
    ctypes.windll.winmm.timeBeginPeriod(1)
_actual = ctypes.c_ulong()
_ntdll = ctypes.windll.ntdll
_min, _max = ctypes.c_ulong(), ctypes.c_ulong()
_ntdll.NtQueryTimerResolution(ctypes.byref(_min), ctypes.byref(_max), ctypes.byref(_actual))
print("Zeitgeberauflösung jetzt", _actual.value / 10000, "ms")
sys.setswitchinterval(interval)


def spin(stop: threading.Event, counter: list[int]) -> None:
    count = 0
    while not stop.is_set():
        for _ in range(1000):
            count += 1
    counter[0] = count


def grabs() -> list[float]:
    stop = threading.Event()
    counter = [0]
    worker = threading.Thread(target=spin, args=(stop, counter))
    worker.start()
    time.sleep(0.2)
    took = []
    for _ in range(200):
        before = time.perf_counter()
        time.sleep(0)
        took.append(time.perf_counter() - before)
    stop.set()
    worker.join()
    return took


def throughput(threads: int) -> int:
    stop = threading.Event()
    counters = [[0] for _ in range(threads)]
    workers = [threading.Thread(target=spin, args=(stop, counter)) for counter in counters]
    for worker in workers:
        worker.start()
    time.sleep(2.0)
    stop.set()
    for worker in workers:
        worker.join()
    return sum(counter[0] for counter in counters)


took = grabs()
alone = throughput(1)
together = throughput(2)
print(
    f"intervall {interval * 1000:.1f} ms, timeBeginPeriod {int(fine)}:"
    f" Griff Median {statistics.median(took) * 1000:.2f} ms,"
    f" 95 % {sorted(took)[190] * 1000:.2f} ms, 200 Griffe {sum(took) * 1000:.0f} ms;"
    f" Durchsatz zwei gegen einen {together / alone:.2f}"
)
