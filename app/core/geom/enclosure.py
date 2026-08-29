"""Konturverschachtelung ohne ``rtree`` — trimeshs Vertrag, GEOS-Kandidaten.

``trimesh.path.polygons.enclosure_tree`` entscheidet, welche Kontur welche
umschließt: die Grundlage für Löcher beim Deckeln eines Schnitts
(``slice_plane(cap=True)``), beim Schließen einer Zeichnung und überall, wo
ein ``Path2D`` seine Flächen baut. Seine Überlappungskandidaten holt es aus
einem ``rtree`` — und warum das Paket den Prozess nicht mehr betreten darf,
steht an :func:`app.core.geom.mesh.on_surface`.

Diese Fassung ist Zeile für Zeile dieselbe Entscheidung — Bounding-Box-
Kandidaten, Polygon-in-Polygon in beiden Richtungen, gerade Umschließerzahl
als Rand, Kinder mit genau einem Umschließer mehr als Löcher, derselbe
beschnittene Graph —, nur liefert die Kandidaten ein ``STRtree`` aus shapely
(GEOS, längst Abhängigkeit).

**Sie ersetzt trimeshs Fassung beim Import dieses Moduls.** Das ist ein
bewusster Eingriff in ein fremdes Modul und die kleinste ehrliche Lösung,
denn beide echten Aufrufer erreichen die Funktion als **Modulglobale** ihrer
eigenen Datei — kein Parameter, keine Unterklasse erreicht sie von außen:
``trimesh/path/polygons.py`` ruft sie in ``edges_to_polygons`` (dorthin
führt ``slice_mesh_plane`` über ``trimesh/intersections.py``), und
``trimesh/path/path.py`` in ``Path2D.enclosure_directed``. Der Vertrag ist
oben festgehalten und wird von ``tests/test_slots.py`` an einem gedeckelten
Schnitt durch eine Platte mit Loch geprüft, in einem Prozess, in dem
``rtree`` unbenutzbar gemacht ist.
"""

from __future__ import annotations

from typing import Any

import numpy as np


def enclosure_tree(polygons: Any) -> tuple[np.ndarray, Any]:
    """Welche Kontur ist Rand, und welche gehört ihr als Loch.

    Rückgabe wie bei trimesh: die Wurzelindizes und ein gerichteter Graph, in
    dem ``tree[root].keys()`` die unmittelbaren Löcher der Wurzel sind.
    """
    import networkx as nx
    from shapely.strtree import STRtree

    contains = nx.DiGraph()
    if len(polygons) == 0:
        return np.array([], dtype=np.int64), contains
    if len(polygons) == 1:
        # ``paths_to_polygons`` liefert ``None`` für Unrettbares — eine
        # einzelne unrettbare Kontur ist keine Wurzel.
        if polygons[0] is None:
            return np.array([], dtype=np.int64), contains
        contains.add_node(0)
        return np.array([0], dtype=np.int64), contains

    keys = [
        index
        for index, polygon in enumerate(polygons)
        if polygon is not None and len(getattr(polygon, "bounds", ())) == 4
    ]
    contains.add_nodes_from(keys)
    if keys:
        tree = STRtree([polygons[key] for key in keys])
        for outer in keys:
            # Kandidaten über die Bounding-Box, wie ``tree.intersection`` beim
            # rtree; die Entscheidung fällt am Polygon. Beide Richtungen, denn
            # jedes Paar läuft hier zweimal durch — auch das wie im Original:
            # zwei deckungsgleiche Konturen umschließen einander wechselseitig
            # und sind danach beide keine Wurzel mehr.
            for found in tree.query(polygons[outer]):
                inner = keys[int(found)]
                if outer == inner:
                    continue
                if polygons[outer].contains(polygons[inner]):
                    contains.add_edge(outer, inner)
                elif polygons[inner].contains(polygons[outer]):
                    contains.add_edge(inner, outer)

    degree = dict(contains.in_degree())
    indexes = np.array(list(degree.keys()))
    degrees = np.array(list(degree.values()))
    roots = indexes[(degrees % 2) == 0]
    if len(degrees) > 0 and degrees.max() > 1:
        # Verschachtelt über Tiefe eins hinaus: je Wurzel nur die eigenen
        # unmittelbaren Kinder behalten — die Insel im Loch wird wieder Rand.
        edges: list[Any] = []
        roots = roots[np.argsort([degree[root] for root in roots])]
        for root in roots:
            children = indexes[degrees == degree[root] + 1]
            edges.extend(contains.subgraph(np.append(children, root)).edges())
        contains = nx.from_edgelist(edges, nx.DiGraph())
        contains.add_nodes_from(roots)
    return roots, contains


def _install() -> None:
    """Trimeshs Fassung durch diese ersetzen — beim Import; die Zuweisung ist
    idempotent, ein zweiter Lauf setzt nur dieselbe Funktion erneut."""
    import trimesh.path.polygons as polygons

    polygons.enclosure_tree = enclosure_tree


_install()
