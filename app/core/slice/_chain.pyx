# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True
"""Die Konturverkettung einer Schicht, übersetzt (Bauplan §22.1, §31).

Ein Schnittpunkt gehört genau einer Kante des Netzes, und eine Kante genau
zwei Dreiecken. Damit trägt jeder Knoten genau zwei Segmente, und die Ringe
einer Schicht sind schlicht die Zyklen dieser Zuordnung. Das ist ein
Durchlauf in O(n) ohne eine einzige Fließkommaentscheidung — und trotzdem war
er in Python nicht schneller als ``polygonize`` in GEOS, das die viel
schwerere Aufgabe löst, beliebig kreuzende Linien erst zu noden.

Gemessen an einer Kugel mit 327 680 Dreiecken in 400 Schichten: 608 ms als
Python-Schleife, 11 ms hier. Der Unterschied ist nicht das Verfahren — es ist
dasselbe, Zeile für Zeile — sondern dass 465 000 Interpreterschritte
entfallen.

Dieses Modul ist **optional**. Fehlt es, nimmt ``analysis.py`` weiter den Weg
über GEOS; gebaut wird es mit ``tools/build_slice_core.py``. Die Suite läuft
gegen beide Wege, und ``tests/test_slice_core.py`` hält sie aneinander.
"""


def chain_rings(long long[:, ::1] node,
                long long[:, ::1] incident,
                long long[::1] walk,
                long long[::1] ring_of):
    """Verkettet die Segmente einer Schicht zu geschlossenen Ringen.

    ``node`` nennt je Segment die beiden Knoten seiner Enden, ``incident`` je
    Knoten die beiden Segmente, die an ihm hängen. Beschrieben werden ``walk``
    — je Schritt der Index des Eintrittspunkts in der flachen Punktliste — und
    ``ring_of`` mit der Ringnummer dazu; beide müssen so lang sein wie
    ``node``.

    Zurück kommt ``(Ringe, beschriebene Länge)``. ``(-1, 0)`` heißt, dass sich
    ein Ring nicht geschlossen hat — dann trägt die Voraussetzung nicht, und
    der Aufrufer nimmt GEOS.
    """
    cdef Py_ssize_t count = node.shape[0]
    cdef Py_ssize_t first, written = 0, begin
    cdef long long segment, entry, leaving, neighbour, start_node
    cdef long long ring = 0
    cdef int broken = 0
    cdef char[::1] seen = bytearray(count)

    with nogil:
        for first in range(count):
            if seen[first]:
                continue
            segment = first
            entry = node[first, 0]
            start_node = entry
            begin = written
            while seen[segment] == 0:
                seen[segment] = 1
                # Welches Ende dieses Segments ist der Eintritt — und welches
                # bleibt als Ausgang?
                if node[segment, 0] == entry:
                    walk[written] = 2 * segment
                    leaving = node[segment, 1]
                else:
                    walk[written] = 2 * segment + 1
                    leaving = node[segment, 0]
                ring_of[written] = ring
                written += 1
                neighbour = incident[leaving, 0]
                if neighbour == segment:
                    segment = incident[leaving, 1]
                else:
                    segment = neighbour
                entry = leaving
            if entry != start_node:
                broken = 1
                break
            # Zwei Punkte sind keine Fläche.
            if written - begin < 3:
                written = begin
                continue
            ring += 1

    if broken:
        return -1, 0
    return ring, written
