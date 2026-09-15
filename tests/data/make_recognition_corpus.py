"""Eigene analytische Erkennungskörper; keine Kundendateien oder fremden Quelltexte.

Die NPZ bewahren Double-Koordinaten und Dreiecksnummern. Die Konstruktionen
reduzieren Erkennungsfehler auf einfache Kreise, Quader und eine Radialwendel.
"""

from pathlib import Path

import numpy as np
import trimesh

ROOT = Path(__file__).parent / "meshes"


def box(extents, centre):
    """Einen Quader an den benannten Mittelpunkt stellen."""
    body = trimesh.creation.box(extents=extents)
    body.apply_translation(centre)
    return body


def cylinder(radius, height, centre):
    """Einen fein facettierten Zylinder mit analytischem Radius erzeugen."""
    body = trimesh.creation.cylinder(radius=radius, height=height, sections=192)
    body.apply_translation(centre)
    return body


def save(name, body, **extra):
    """Nur selbst erzeugte Geometrie ohne Metadaten oder ausführbaren Inhalt speichern."""
    assert body.is_watertight and body.volume > 0
    np.savez_compressed(
        ROOT / f"recognition_{name}.npz", vertices=body.vertices, faces=body.faces, **extra
    )


def thread(internal=False):
    """Ein radialer Trapezverlauf über z/p − θ/2π, mit ebenen Abschlussflächen."""
    pitch, depth, sections = 3.5, 1.4, 80
    turns = 3.0 if internal else 4.0
    rows = int(turns * sections)
    vertices = []
    for row in range(rows + 1):
        z = pitch * row / sections
        for column in range(sections):
            theta = 2.0 * np.pi * column / sections
            phase = (row / sections - column / sections) % 1.0
            height = np.interp(phase, (0.0, 0.1, 0.3, 0.6, 0.8, 1.0), (0, 0, 1, 1, 0, 0))
            radius = 17.45 - depth * height if internal else 15.6 + depth * height
            vertices.append((radius * np.cos(theta), radius * np.sin(theta), z))
    faces = []
    for row in range(rows):
        for column in range(sections):
            a = row * sections + column
            b = row * sections + (column + 1) % sections
            c, d = b + sections, a + sections
            faces.extend(((a, b, c), (a, c, d)))
    if internal:
        faces = [tuple(reversed(face)) for face in faces]
        outer_low = len(vertices)
        for z in (0.0, turns * pitch):
            for column in range(sections):
                theta = 2.0 * np.pi * column / sections
                vertices.append((20.0 * np.cos(theta), 20.0 * np.sin(theta), z))
        for column in range(sections):
            following = (column + 1) % sections
            a, b = outer_low + column, outer_low + following
            c, d = b + sections, a + sections
            faces.extend(((a, b, c), (a, c, d)))
            inner_top, next_top = rows * sections + column, rows * sections + following
            faces.extend(((column, following, b), (column, b, a)))
            faces.extend(((inner_top, d, c), (inner_top, c, next_top)))
    else:
        low, high = len(vertices), len(vertices) + 1
        vertices.extend(((0.0, 0.0, 0.0), (0.0, 0.0, turns * pitch)))
        for column in range(sections):
            following = (column + 1) % sections
            faces.extend(
                (
                    (low, following, column),
                    (high, rows * sections + column, rows * sections + following),
                )
            )
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def main():
    """Die fünf konstruktiv unabhängigen Fehlerbilder schreiben."""
    ring = cylinder(20.0, 3.4, (0.0, 0.0, 1.7))
    cutters = [cylinder(16.4, 5.0, (0.0, 0.0, 1.7))]
    for angle in (0.0, 2.0 * np.pi / 3.0, 4.0 * np.pi / 3.0):
        cutters.append(cylinder(1.1, 5.0, (16.0 * np.cos(angle), 16.0 * np.sin(angle), 1.7)))
    save("spice_base", trimesh.boolean.difference([ring, trimesh.boolean.union(cutters)]))

    wall = box((60.0, 12.0, 30.0), (0.0, 0.0, 15.0))
    lip = box((60.0, 28.0, 3.0), (0.0, 0.0, 1.5))
    save("waterfall", trimesh.boolean.union([wall, lip]))

    lid = cylinder(40.0, 3.0, (0.0, 0.0, 1.5))
    lugs = []
    for angle in (0.0, 2.0 * np.pi / 3.0, 4.0 * np.pi / 3.0):
        lug = box((6.0, 3.8, 0.6), (30.0, 0.0, 3.2))
        lug.apply_transform(trimesh.transformations.rotation_matrix(angle, (0, 0, 1)))
        lugs.append(lug)
    save("bayonet_lid", trimesh.boolean.union([lid, *lugs]))

    cage = trimesh.boolean.difference(
        [
            box((80.0, 80.0, 20.0), (0.0, 0.0, 10.0)),
            box((72.0, 72.0, 22.0), (0.0, 0.0, 13.0)),
        ]
    )
    tunnels = []
    for angle in (0.0, np.pi / 2.0, np.pi):
        tunnel = box((8.0, 5.0, 4.0), (38.0, 0.0, 10.0))
        tunnel.apply_transform(trimesh.transformations.rotation_matrix(angle, (0, 0, 1)))
        tunnels.append(tunnel)
    save("bayonet_cage", trimesh.boolean.difference([cage, trimesh.boolean.union(tunnels)]))
    female = thread(internal=True)
    assert female.is_watertight and female.volume > 0
    save("short_thread", thread(), inner_vertices=female.vertices, inner_faces=female.faces)


if __name__ == "__main__":
    main()
