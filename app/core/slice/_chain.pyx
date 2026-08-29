# cython: language_level=3, boundscheck=False, wraparound=False, cdivision=True
"""Der Schnittkern für Ebenensegmente und Konturverkettung (§22.1, §31).

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

Vor den Ringen liegt noch eine ebenso regelmäßige Rechnung: jedes Dreieck wird
den Höhen zugeordnet, die es kreuzen, und seine zwei Schnittpunkte werden
interpoliert. NumPy brauchte dafür auf dem §31-Körper 203 ms und legte dabei
mehrere Felder über alle Dreieck-Schicht-Paare an. Der übersetzte Weg läuft
zweimal durch dieselben Paare — einmal zum Zählen, einmal zum Schreiben — und
braucht keinen dieser großen Zwischenstände.

Dieses Modul ist **optional**. Fehlt es, nimmt ``analysis.py`` für die Segmente
den NumPy-Weg und für die Ringe GEOS; gebaut wird es mit
``tools/build_slice_core.py``. Die Suite läuft gegen beide Wege, und
``tests/test_slice_core.py`` hält sie aneinander.
"""

import numpy as np

from libc.math cimport fabs


cdef Py_ssize_t _lower_bound(double[::1] values, double target) noexcept nogil:
    """Erster Index mit ``Wert >= target``."""
    cdef Py_ssize_t low = 0
    cdef Py_ssize_t high = values.shape[0]
    cdef Py_ssize_t middle
    while low < high:
        middle = low + (high - low) // 2
        if values[middle] < target:
            low = middle + 1
        else:
            high = middle
    return low


cdef Py_ssize_t _upper_bound(double[::1] values, double target) noexcept nogil:
    """Erster Index mit ``Wert > target``."""
    cdef Py_ssize_t low = 0
    cdef Py_ssize_t high = values.shape[0]
    cdef Py_ssize_t middle
    while low < high:
        middle = low + (high - low) // 2
        if values[middle] <= target:
            low = middle + 1
        else:
            high = middle
    return low


cdef bint _after(double ax, double ay, double az,
                 double bx, double by, double bz) noexcept nogil:
    """Ob A lexikografisch hinter B liegt."""
    return ax > bx or (ax == bx and (ay > by or (ay == by and az > bz)))


def plane_segments(double[:, ::1] vertices,
                   long long[:, ::1] faces,
                   double[::1] heights,
                   double epsilon):
    """Schneidet alle Dreiecke mit allen erreichten Ebenen.

    Die Ausgabe ist nach Schicht gruppiert, innerhalb jeder Schicht in
    Flächenreihenfolge. So muss der Aufrufer die Segmente nicht noch einmal
    global sortieren. ``epsilon`` kommt aus dem Einheitenmodul; der übersetzte
    Kern erfindet keine eigene Toleranz (Regel 7).
    """
    cdef Py_ssize_t face_count = faces.shape[0]
    cdef Py_ssize_t vertex_count = vertices.shape[0]
    cdef Py_ssize_t height_count = heights.shape[0]
    cdef Py_ssize_t face, layer, first, last, edge, total = 0, written = 0
    cdef Py_ssize_t crossings, crossing_index
    cdef long long a, b, c, start_id, end_id, swap_id
    cdef double z0, z1, z2, low_z, high_z, z
    cdef double sx, sy, sz, ex, ey, ez, swap_value
    cdef double start_height, end_height, span, fraction

    if face_count == 0 or height_count == 0:
        return (
            np.empty((0, 2, 2), dtype=np.float64),
            np.empty(0, dtype=np.int64),
            np.empty((0, 2), dtype=np.int64),
        )

    layer_counts_array = np.zeros(height_count, dtype=np.int64)
    cdef long long[::1] layer_counts = layer_counts_array

    # Der erste Durchlauf zählt nur. Damit entstehen im zweiten genau große
    # Ausgabefelder statt der großen Zwischenfelder des NumPy-Wegs.
    with nogil:
        for face in range(face_count):
            a, b, c = faces[face, 0], faces[face, 1], faces[face, 2]
            z0, z1, z2 = vertices[a, 2], vertices[b, 2], vertices[c, 2]
            low_z = z0
            if z1 < low_z:
                low_z = z1
            if z2 < low_z:
                low_z = z2
            high_z = z0
            if z1 > high_z:
                high_z = z1
            if z2 > high_z:
                high_z = z2
            if low_z > heights[height_count - 1] or high_z < heights[0]:
                continue
            first = _lower_bound(heights, low_z - epsilon)
            last = _upper_bound(heights, high_z + epsilon) - 1
            if first < 0:
                first = 0
            if last >= height_count:
                last = height_count - 1
            for layer in range(first, last + 1):
                z = heights[layer]
                crossings = 0
                if (z0 - z > 0.0) != (z1 - z > 0.0):
                    crossings += 1
                if (z1 - z > 0.0) != (z2 - z > 0.0):
                    crossings += 1
                if (z2 - z > 0.0) != (z0 - z > 0.0):
                    crossings += 1
                if crossings == 2:
                    total += 1
                    layer_counts[layer] += 1

    points_array = np.empty((total, 2, 2), dtype=np.float64)
    layers_array = np.empty(total, dtype=np.int64)
    nodes_array = np.empty((total, 2), dtype=np.int64)
    cdef double[:, :, ::1] points = points_array
    cdef long long[::1] layers = layers_array
    cdef long long[:, ::1] nodes = nodes_array
    offsets_array = np.empty(height_count + 1, dtype=np.int64)
    cursors_array = np.empty(height_count, dtype=np.int64)
    cdef long long[::1] offsets = offsets_array
    cdef long long[::1] cursors = cursors_array

    offsets[0] = 0
    for layer in range(height_count):
        offsets[layer + 1] = offsets[layer] + layer_counts[layer]
        cursors[layer] = offsets[layer]

    with nogil:
        for face in range(face_count):
            a, b, c = faces[face, 0], faces[face, 1], faces[face, 2]
            z0, z1, z2 = vertices[a, 2], vertices[b, 2], vertices[c, 2]
            low_z = z0
            if z1 < low_z:
                low_z = z1
            if z2 < low_z:
                low_z = z2
            high_z = z0
            if z1 > high_z:
                high_z = z1
            if z2 > high_z:
                high_z = z2
            if low_z > heights[height_count - 1] or high_z < heights[0]:
                continue
            first = _lower_bound(heights, low_z - epsilon)
            last = _upper_bound(heights, high_z + epsilon) - 1
            if first < 0:
                first = 0
            if last >= height_count:
                last = height_count - 1
            for layer in range(first, last + 1):
                z = heights[layer]
                crossings = 0
                if (z0 - z > 0.0) != (z1 - z > 0.0):
                    crossings += 1
                if (z1 - z > 0.0) != (z2 - z > 0.0):
                    crossings += 1
                if (z2 - z > 0.0) != (z0 - z > 0.0):
                    crossings += 1
                if crossings != 2:
                    continue

                written = cursors[layer]
                cursors[layer] += 1
                crossing_index = 0
                for edge in range(3):
                    if edge == 0:
                        start_id, end_id = a, b
                    elif edge == 1:
                        start_id, end_id = b, c
                    else:
                        start_id, end_id = c, a
                    sz, ez = vertices[start_id, 2], vertices[end_id, 2]
                    if (sz - z > 0.0) == (ez - z > 0.0):
                        continue
                    sx, sy = vertices[start_id, 0], vertices[start_id, 1]
                    ex, ey = vertices[end_id, 0], vertices[end_id, 1]
                    if _after(sx, sy, sz, ex, ey, ez):
                        swap_value = sx
                        sx = ex
                        ex = swap_value
                        swap_value = sy
                        sy = ey
                        ey = swap_value
                        swap_value = sz
                        sz = ez
                        ez = swap_value
                        swap_id = start_id
                        start_id = end_id
                        end_id = swap_id

                    start_height = sz - z
                    end_height = ez - z
                    span = start_height - end_height
                    if fabs(span) > epsilon:
                        fraction = start_height / span
                    else:
                        fraction = 0.0
                    points[written, crossing_index, 0] = sx + (ex - sx) * fraction
                    points[written, crossing_index, 1] = sy + (ey - sy) * fraction
                    if start_id < end_id:
                        nodes[written, crossing_index] = start_id * vertex_count + end_id
                    else:
                        nodes[written, crossing_index] = end_id * vertex_count + start_id
                    crossing_index += 1

                layers[written] = layer

    return points_array, layers_array, nodes_array


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
