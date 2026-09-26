"""Die Zeitspanne der Vollerkennung auf diesem Rechner, aus einer kurzen Rechenprobe.

Die Referenz ist ein gemessener Lauf auf dem Rechner, auf dem Solidon
entsteht. Ein Kundenrechner kann um ein Mehrfaches langsamer sein — acht
Jahre alte Hardware ist ausdrücklich unterstützt —, und dann stimmte eine feste
Spanne nicht. Eine kurze, deterministische Probe misst deshalb einmal je
Prozess, wie schnell dieser Rechner dieselbe Art Arbeit erledigt, und
skaliert die Referenz damit.

**Aus vergangenen Läufen lernt die Schätzung nicht.** Das hieße, in der
Erkennung die Uhr zu lesen und Laufzeiten in den Nutzerordner zu schreiben —
und die Auswertung ist eine reine Funktion (§15.1,
``test_registry_consistency.test_no_operation_reads_the_clock_the_environment_or_the_machine``).
Die Probe läuft deshalb nur dort, wo eine Spanne angezeigt wird: in der Frage
vor der Vollerkennung und in der Statuszeile danach. Zeit und Probe dienen
ausschließlich der Anzeige.
"""

from __future__ import annotations

import math
import threading
from collections.abc import Callable
from itertools import pairwise
from statistics import median
from time import perf_counter
from typing import Final

import numpy as np

#: Belegte Referenz, allein die Erkennung ohne Einlesen, auf den Referenzrechner
#: umgerechnet (Messzeit mal Referenzprobe durch Probe des Laufs): Der Drache
#: mit 2 330 374 Dreiecken braucht 44 Sekunden, je Dreieck 18,8 µs (Durchsicht
#: 0.5.1, 26.09.2026). Die 72 Sekunden davor stammten aus dem Stand vor den
#: Beschleunigungen vom 25.09.2026, und die Frage nannte dem Drachen „1 bis 7
#: Minuten“ für 36 Sekunden.
RECOGNITION_REFERENCE_TRIANGLES: Final = 2_330_374
RECOGNITION_REFERENCE_SECONDS: Final = 44
#: Die Topologie streut stärker als der Rechner. Je Dreieck, am selben Tag und
#: gleich umgerechnet: 16,4 µs am Voronoi-Spiderman, 18,8 am Drachen, 19,5 an
#: der Katze, 22,0 am Puppenhausbett, 23,2 am Piratenschiff — und 128,4 µs am
#: erzeugten Murmelbrett, einer zur Hälfte ebenen Platte mit verrauschter Haut,
#: deren 167 000 Splitter einzeln eingepasst werden (ERKENNUNG-05). Die obere
#: Schätzung trägt deshalb den siebenfachen Zeitansatz; vorher trug sie den
#: fünffachen, und das Brett brauchte mehr als die angezeigte Obergrenze.
RECOGNITION_TIME_FACTOR: Final = 7
#: Dieselbe Probe auf dem Referenzrechner: Median 17,572 ms, gerundet 18 ms.
PROBE_REFERENCE_SECONDS: Final = 0.018
#: Umfang der Probe: vier Blöcke aus NumPy-Sortierung und Python-Kantenzählung
#: mit festem Speicherbedarf — die zwei Arten Arbeit, aus denen die Erkennung
#: besteht. Zusammen mit Aufwärmen und drei Messungen rund 70 ms.
PROBE_BLOCKS: Final = 4
PROBE_ITEMS: Final = 16_384
PROBE_MODULUS: Final = 65_521
PROBE_STRIDE: Final = 7_919
PROBE_REPEATS: Final = 3

_lock = threading.RLock()
_probe_seconds: float | None = None


def probe_work(check_cancelled: Callable[[], None] | None = None) -> int:
    """Mischt NumPy-Sortierung und Python-Kantenzählung bei festem Speicherbedarf."""
    checksum = 0
    for block in range(PROBE_BLOCKS):
        if check_cancelled is not None:
            check_cancelled()
        indices = np.arange(PROBE_ITEMS, dtype=np.int64)
        points = np.column_stack((indices % 97, indices % 31, indices % 17)).astype(np.float64)
        offsets = points[1:] - points[:-1]
        lengths = np.sort(np.sum(offsets * offsets, axis=1))
        vertices = ((indices * PROBE_STRIDE + block) % PROBE_MODULUS).tolist()
        edges: dict[int, int] = {}
        for left, right in pairwise(vertices):
            first, second = (left, right) if left < right else (right, left)
            code = first * PROBE_MODULUS + second
            edges[code] = edges.get(code, 0) + 1
        checksum += len(sorted(edges)) + int(lengths[-1])
    if check_cancelled is not None:
        check_cancelled()
    return checksum


def calibrate(*, check_cancelled: Callable[[], None] | None = None) -> float:
    """Misst in jedem Prozess frisch; eine abgebrochene Probe wird nie gemerkt.

    Frisch je Prozess, weil sich die Leistung eines Rechners ändert — ein
    Laptop am Netzteil rechnet anders als im Akkubetrieb. Ein Aufwärmlauf
    zuerst, dann der Median dreier Messungen: Eine Lastspitze bestimmt ihn
    nicht.
    """
    global _probe_seconds
    if check_cancelled is not None:
        check_cancelled()
    with _lock:
        if _probe_seconds is None:
            probe_work(check_cancelled)
            durations = []
            for _ in range(PROBE_REPEATS):
                started = perf_counter()
                probe_work(check_cancelled)
                durations.append(perf_counter() - started)
            if check_cancelled is not None:
                check_cancelled()
            _probe_seconds = max(median(durations), math.ulp(1.0))
        return _probe_seconds


def estimate_minutes(
    triangles: int, *, check_cancelled: Callable[[], None] | None = None
) -> tuple[int, int]:
    """Grobe Spanne in Minuten auf diesem Rechner, keine Zusage.

    Die Referenz je Dreieck, mit der Probe auf diesen Rechner skaliert; die
    obere Schätzung trägt den Zeitansatz der Topologie
    (:data:`RECOGNITION_TIME_FACTOR`). Die Minuten werden unten ab- und oben
    aufgerundet, mindestens eine bis zwei.
    """
    probe = calibrate(check_cancelled=check_cancelled)
    basis = triangles * RECOGNITION_REFERENCE_SECONDS / RECOGNITION_REFERENCE_TRIANGLES
    basis *= probe / PROBE_REFERENCE_SECONDS
    lower, upper = basis, basis * RECOGNITION_TIME_FACTOR
    return max(1, math.floor(lower / 60)), max(2, math.ceil(upper / 60))
