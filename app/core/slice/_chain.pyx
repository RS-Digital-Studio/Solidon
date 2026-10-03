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

from libc.math cimport fabs, frexp, isfinite, ldexp, nearbyint
from libc.float cimport DBL_EPSILON
from libc.stdlib cimport qsort

#: Version 2 nimmt einen optionalen Abbruchrückruf als fünftes Argument an.
#: Version 3 richtet jedes Segment so, dass das Material links liegt (RM-485):
#: Ein Bau der Version 2 liefert ungerichtete Segmente und wird nicht genommen.
PLANE_SEGMENTS_API = 3


cdef int _compare_span(const void* first, const void* second) noexcept nogil:
    cdef double left = (<double*>first)[0]
    cdef double right = (<double*>second)[0]
    return (left > right) - (left < right)


cdef Py_ssize_t _span_bound(const double[::1] values, double target, bint upper) noexcept nogil:
    cdef Py_ssize_t low = 0, high = values.shape[0], middle
    while low < high:
        middle = low + (high - low) // 2
        if values[middle] < target or (upper and values[middle] <= target):
            low = middle + 1
        else:
            high = middle
    return low


def cuts_along(const double[::1] across_head, const double[::1] across_tail,
               const double[::1] along_head, const double[::1] along_tail,
               const double[::1] positions, const double[::1] normal,
               const double[::1] direction, double epsilon):
    """Paritätspaare je Abtastlage, mit denselben Formeln wie im NumPy-Weg.

    Je Kante werden nur die echt gekreuzten Lagen besucht. Der Speicher gehört
    NumPy; auch bei einer Ausnahme bleibt kein manuell reservierter Puffer.
    """
    cdef Py_ssize_t edges = across_head.shape[0], columns = positions.shape[0]
    if (across_tail.shape[0] != edges or along_head.shape[0] != edges
            or along_tail.shape[0] != edges or normal.shape[0] != 2
            or direction.shape[0] != 2):
        raise ValueError("Die Projektionsfelder müssen dieselbe Länge und zwei Achsen haben.")
    order_array = np.argsort(np.asarray(positions), kind="stable")
    sorted_array = np.asarray(positions)[order_array]
    counts_array = np.zeros(columns, dtype=np.intp)
    cdef Py_ssize_t[::1] order = order_array, counts = counts_array
    cdef double[::1] sorted_positions = sorted_array
    cdef Py_ssize_t edge, column, slot, lo, hi, total = 0, start, count, pair, output = 0
    cdef double head, tail, position, lower, upper, share, first, second
    with nogil:
        for edge in range(edges):
            head, tail = across_head[edge], across_tail[edge]
            lower = head if head < tail else tail
            upper = tail if head < tail else head
            lo = _span_bound(sorted_positions, lower, True)
            hi = _span_bound(sorted_positions, upper, False)
            for slot in range(lo, hi):
                position = sorted_positions[slot]
                if (head - position) * (tail - position) < 0.0:
                    counts[order[slot]] += 1
                    total += 1
    if total == 0:
        return None
    fill_array = np.empty(columns, dtype=np.intp)
    along_array = np.empty(total, dtype=np.float64)
    cdef Py_ssize_t[::1] fill = fill_array
    cdef double[::1] along = along_array
    starts_array = np.empty((total // 2, 2), dtype=np.float64)
    ends_array = np.empty((total // 2, 2), dtype=np.float64)
    lengths_array = np.empty(total // 2, dtype=np.float64)
    cdef double[:, ::1] starts = starts_array, ends = ends_array
    cdef double[::1] lengths = lengths_array
    with nogil:
        start = 0
        for column in range(columns):
            fill[column] = start
            start += counts[column]
        for edge in range(edges):
            head, tail = across_head[edge], across_tail[edge]
            lower = head if head < tail else tail
            upper = tail if head < tail else head
            lo = _span_bound(sorted_positions, lower, True)
            hi = _span_bound(sorted_positions, upper, False)
            for slot in range(lo, hi):
                position = sorted_positions[slot]
                if (head - position) * (tail - position) < 0.0:
                    column = order[slot]
                    share = (position - head) / (tail - head)
                    along[fill[column]] = along_head[edge] + share * (along_tail[edge] - along_head[edge])
                    fill[column] += 1
        start = 0
        for column in range(columns):
            count = counts[column]
            if count >= 2:
                qsort(&along[start], count, sizeof(double), _compare_span)
                position = positions[column]
                for pair in range(count // 2):
                    first = along[start + 2 * pair]
                    second = along[start + 2 * pair + 1]
                    if second - first > epsilon:
                        starts[output, 0] = position * normal[0] + first * direction[0]
                        starts[output, 1] = position * normal[1] + first * direction[1]
                        ends[output, 0] = position * normal[0] + second * direction[0]
                        ends[output, 1] = position * normal[1] + second * direction[1]
                        lengths[output] = second - first
                        output += 1
            start += count
    if output == 0:
        return None
    return starts_array[:output], ends_array[:output], lengths_array[:output]


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
                   double epsilon,
                   check_cancelled=None):
    """Schneidet alle Dreiecke mit allen erreichten Ebenen.

    Die Ausgabe ist nach Schicht gruppiert, innerhalb jeder Schicht in
    Flächenreihenfolge. So muss der Aufrufer die Segmente nicht noch einmal
    global sortieren. ``epsilon`` kommt aus dem Einheitenmodul; der übersetzte
    Kern erfindet keine eigene Toleranz (Regel 7).

    **Jedes Segment ist gerichtet**: Es beginnt auf der Kante, die im Umlauf
    des Dreiecks von oberhalb der Ebene nach unten führt, und endet auf der,
    die wieder hinaufführt. Bei nach außen gerichteten Dreiecken liegt das
    Material dann links — ein Außenring läuft gegen den Uhrzeigersinn, ein
    Hohlraum mit ihm. Daraus liest ``analysis`` Material über die
    Umlaufrichtung statt über die Verschachtelungstiefe.
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
    cdef bint first_falls = 1
    cdef long long swap_node
    cdef bint cancellable = check_cancelled is not None
    cdef Py_ssize_t faces_until_check = 8192
    cdef Py_ssize_t layers_until_check = 32768

    if face_count == 0 or height_count == 0:
        return (
            np.empty((0, 2, 2), dtype=np.float64),
            np.empty(0, dtype=np.int64),
            np.empty((0, 2), dtype=np.int64),
        )
    if cancellable:
        check_cancelled()

    layer_counts_array = np.zeros(height_count, dtype=np.int64)
    cdef long long[::1] layer_counts = layer_counts_array

    # Der erste Durchlauf zählt nur. Damit entstehen im zweiten genau große
    # Ausgabefelder statt der großen Zwischenfelder des NumPy-Wegs.
    with nogil:
        for face in range(face_count):
            if cancellable:
                faces_until_check -= 1
                if faces_until_check == 0:
                    with gil:
                        check_cancelled()
                    faces_until_check = 8192
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
                if cancellable:
                    layers_until_check -= 1
                    if layers_until_check == 0:
                        with gil:
                            check_cancelled()
                        layers_until_check = 32768
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

    if cancellable:
        check_cancelled()

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
            if cancellable:
                faces_until_check -= 1
                if faces_until_check == 0:
                    with gil:
                        check_cancelled()
                    faces_until_check = 8192
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
                if cancellable:
                    layers_until_check -= 1
                    if layers_until_check == 0:
                        with gil:
                            check_cancelled()
                        layers_until_check = 32768
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
                    if crossing_index == 0:
                        # Fällt die erste geschnittene Kante im Umlauf des
                        # Dreiecks, beginnt hier das Segment; sonst endet es.
                        first_falls = sz - z > 0.0
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

                if not first_falls:
                    swap_value = points[written, 0, 0]
                    points[written, 0, 0] = points[written, 1, 0]
                    points[written, 1, 0] = swap_value
                    swap_value = points[written, 0, 1]
                    points[written, 0, 1] = points[written, 1, 1]
                    points[written, 1, 1] = swap_value
                    swap_node = nodes[written, 0]
                    nodes[written, 0] = nodes[written, 1]
                    nodes[written, 1] = swap_node
                layers[written] = layer

    if cancellable:
        check_cancelled()
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

    Ein Ring beginnt am Anfang seines ersten Segments und läuft dessen
    Richtung entlang. Ein ungerader Eintrag in ``walk`` heißt, dass ein
    Segment von seinem Ende her betreten wurde — die Richtungen der Dreiecke
    passen dort nicht zusammen.
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


cdef double _project(const double[:, :] points, Py_ssize_t index,
                     double x, double y, double z) noexcept nogil:
    # Getrennte Grundoperationen wie NumPy, auch bei erlaubter FMA-Kontraktion.
    cdef volatile double result = x * points[index, 0]
    cdef volatile double product = y * points[index, 1]
    result = result + product
    product = z * points[index, 2]
    result = result + product
    return result


def orientation_scores(
    const double[:, :] vertices, const double[:, :] normals,
    const double[:, :] centres, const double[:] areas,
    const long long[:] area_steps, int area_exponent,
    const double[:, :] verticals, double threshold,
):
    """Dieselben Grundoperationen und IntegerGrid-Summen ohne große Zwischenfelder."""
    cdef Py_ssize_t count = normals.shape[0]
    cdef Py_ssize_t number, index
    cdef double x, y, z, low, high, value, normal, centre, largest
    cdef double[:] lifted = np.empty(count, dtype=np.float64)
    cdef double[:, :] result = np.zeros((verticals.shape[0], 4), dtype=np.float64)
    cdef long long footprint, overhang, support
    cdef int exponent
    cdef bint flat
    if (vertices.shape[1] != 3 or normals.shape[1] != 3 or centres.shape[1] != 3
        or verticals.shape[1] != 3 or centres.shape[0] != count
        or areas.shape[0] != count or area_steps.shape[0] != count):
        raise ValueError("orientation array shapes")
    if not vertices.shape[0]:
        return np.asarray(result)
    with nogil:
        for number in range(verticals.shape[0]):
            x, y, z = verticals[number, 0], verticals[number, 1], verticals[number, 2]
            low = high = _project(vertices, 0, x, y, z)
            for index in range(1, vertices.shape[0]):
                value = _project(vertices, index, x, y, z)
                if value < low:
                    low = value
                if value > high:
                    high = value
            footprint = overhang = 0
            largest = 0.0
            for index in range(count):
                normal = _project(normals, index, x, y, z)
                centre = _project(centres, index, x, y, z)
                flat = normal < -0.999 and centre < low + 0.05
                lifted[index] = 0.0
                if flat:
                    footprint += area_steps[index]
                if normal < threshold and not flat:
                    overhang += area_steps[index]
                    value = fabs((areas[index] * -normal) * (centre - low))
                    lifted[index] = value
                    if value > largest:
                        largest = value
            result[number, 0] = ldexp(<double>footprint, -area_exponent)
            result[number, 1] = ldexp(<double>overhang, -area_exponent)
            result[number, 2] = high - low
            if largest > 0.0 and isfinite(largest):
                frexp(<double>count * largest, &exponent)
                exponent = 60 - exponent
                support = 0
                for index in range(count):
                    support += <long long>nearbyint(ldexp(lifted[index], exponent))
                result[number, 3] = ldexp(<double>support, -exponent)
    return np.asarray(result)


cdef bint _ring_tree(
    const double[:, ::1] xy,
    const long long[::1] ring_of,
    long long[::1] starts,
    long long[::1] ends,
    double[::1] areas,
    long long[::1] depths,
    long long[::1] parents,
) noexcept nogil:
    # Nur eine kleine Ringgruppe. Bei Randkontakt oder ungesichertem Vorzeichen
    # bleibt die robuste GEOS-Prädikatsrechnung zuständig.
    cdef Py_ssize_t count = xy.shape[0], rings = starts.shape[0]
    cdef Py_ssize_t i, j, k, after, child, container, current
    cdef double px, py, ax, ay, bx, by, left, right, det, bound, total, area_terms
    cdef bint inside
    cdef bint held[16][16]
    if not count or rings > 16 or not rings:
        return False
    starts[0] = 0
    current = 0
    for i in range(count):
        if not isfinite(xy[i, 0]) or not isfinite(xy[i, 1]):
            return False
        if ring_of[i] != current:
            if ring_of[i] != current + 1 or current + 1 >= rings:
                return False
            ends[current] = i
            current += 1
            starts[current] = i
    ends[current] = count
    if current + 1 != rings:
        return False
    for i in range(rings):
        if ends[i] - starts[i] < 3:
            return False
        total = area_terms = 0.0
        for j in range(starts[i], ends[i]):
            after = j + 1 if j + 1 < ends[i] else starts[i]
            left = xy[j, 0] * xy[after, 1]
            right = xy[after, 0] * xy[j, 1]
            total += left - right
            area_terms += fabs(left) + fabs(right)
        # Eine konservative Rundungsschranke sichert auch den Umlaufsinn ab;
        # bei großer Verschiebung und winziger Fläche entscheidet GEOS.
        if not isfinite(total) or not isfinite(area_terms):
            return False
        if fabs(total) <= 16 * DBL_EPSILON * (ends[i] - starts[i]) * area_terms:
            return False
        areas[i] = total
        depths[i] = 0
        parents[i] = -1
    for child in range(rings):
        px = xy[starts[child], 0]
        py = xy[starts[child], 1]
        for container in range(rings):
            held[child][container] = False
            if child == container:
                continue
            inside = False
            for k in range(starts[container], ends[container]):
                after = k + 1 if k + 1 < ends[container] else starts[container]
                ax, ay = xy[k, 0], xy[k, 1]
                bx, by = xy[after, 0], xy[after, 1]
                if (ay > py) != (by > py):
                    left = (bx - ax) * (py - ay)
                    right = (by - ay) * (px - ax)
                    det = left - right
                    bound = 16 * DBL_EPSILON * (fabs(left) + fabs(right))
                    if not isfinite(det) or fabs(det) <= bound:
                        return False
                    if (det > 0) == (by > ay):
                        inside = not inside
                elif min(ax, bx) <= px <= max(ax, bx) and min(ay, by) <= py <= max(ay, by):
                    # Auch ein waagerechter Rand und ein oberer Eckpunkt
                    # sind Kontakte, obwohl der halboffene Strahl sie auslässt.
                    left = (bx - ax) * (py - ay)
                    right = (by - ay) * (px - ax)
                    bound = 16 * DBL_EPSILON * (fabs(left) + fabs(right))
                    if fabs(left - right) <= bound:
                        return False
            held[child][container] = inside
            if inside:
                depths[child] += 1
    for child in range(rings):
        for container in range(rings):
            if held[child][container] and depths[container] == depths[child] - 1:
                parents[child] = container
    return True


def ring_nesting(const double[:, ::1] coordinates, const long long[::1] ring_of):
    """Ringgrenzen und Elternschaft, oder kein Nachweis bei unsicherer Geometrie.

    Die Flächen- und Strahldeterminanten müssen ihren Rundungsfehler deutlich
    übersteigen. Geometrische Randkontakte und mehr als 16 Ringe bleiben beim
    GEOS-Index. Die Gültigkeit der fertig verschachtelten Fläche prüft weiterhin
    der Aufrufer; dieser Helfer ersetzt nur die gleichförmigen Vorarbeiten.
    """
    cdef Py_ssize_t count = coordinates.shape[0], rings
    if coordinates.shape[1] != 2 or ring_of.shape[0] != count:
        raise ValueError("Jede Ringkennung braucht genau einen zweidimensionalen Punkt.")
    if not count or ring_of[count - 1] < 0 or ring_of[count - 1] >= 16:
        return None
    rings = ring_of[count - 1] + 1
    starts_array = np.empty(rings, dtype=np.int64)
    ends_array = np.empty(rings, dtype=np.int64)
    areas_array = np.empty(rings, dtype=np.float64)
    depths_array = np.empty(rings, dtype=np.int64)
    parents_array = np.empty(rings, dtype=np.int64)
    cdef long long[::1] starts = starts_array, ends = ends_array
    cdef long long[::1] depths = depths_array, parents = parents_array
    cdef double[::1] areas = areas_array
    cdef bint proven
    with nogil:
        proven = _ring_tree(coordinates, ring_of, starts, ends, areas, depths, parents)
    if not proven:
        return None
    return starts_array, ends_array, areas_array, depths_array, parents_array
