"""(ii) im exakten Kern: Wand je Kante und ein Aufruf ohne erneute Wandkarte (einmalig)."""

import io
import sys

TREE = sys.argv[1]
path = TREE + "/app/core/brep/edit.py"
text = io.open(path, encoding="utf-8", newline="").read()


def swap(old: str, new: str, count: int = 1) -> None:
    global text
    found = text.count(old)
    assert found == count, (old[:70], found)
    text = text.replace(old, new)


# fillet und chamfer: die Wand darf der Aufrufer schon geprüft haben.
swap(
    """    selected_edges: Sequence[int] | None = None,
    rings_by_plane: bool = True,
    cancelled: CancelToken | None = None,
    law: RadiusLaw | None = None,
) -> Solid:""",
    """    selected_edges: Sequence[int] | None = None,
    rings_by_plane: bool = True,
    cancelled: CancelToken | None = None,
    law: RadiusLaw | None = None,
    wall_checked: bool = False,
) -> Solid:""",
)
swap(
    """    selected_edges: Sequence[int] | None = None,
    rings_by_plane: bool = True,
    shape: ChamferShape | None = None,
    cancelled: CancelToken | None = None,
) -> Solid:""",
    """    selected_edges: Sequence[int] | None = None,
    rings_by_plane: bool = True,
    shape: ChamferShape | None = None,
    cancelled: CancelToken | None = None,
    wall_checked: bool = False,
) -> Solid:""",
)
swap(
    """    _fits_the_wall(working, radius, chosen, "fillet", cancelled=cancelled)""",
    """    if not wall_checked:
        _fits_the_wall(working, radius, chosen, "fillet", cancelled=cancelled)""",
)
swap(
    """    _fits_the_wall(working, widest, chosen, "chamfer", cancelled=cancelled)""",
    """    if not wall_checked:
        _fits_the_wall(working, widest, chosen, "chamfer", cancelled=cancelled)""",
)
swap(
    """    ``rings_by_plane`` wie bei :func:`app.core.geom.edges.choose`: aus nur für
    Schritte, die vor Format 37 gespeichert wurden (RM-279).
""",
    """    ``rings_by_plane`` wie bei :func:`app.core.geom.edges.choose`: aus nur für
    Schritte, die vor Format 37 gespeichert wurden (RM-279). ``wall_checked``
    lässt die Wandprüfung aus, wenn der Aufrufer sie für eine Obermenge dieser
    Kanten schon bestanden hat (:func:`edge_walls`) — eine Teilmenge hat keine
    dünnere Trägerwand, und die Wandkarte kostet an einem Kundenteil 0,7 s.
""",
)

# Die Wand je Kante — dieselbe Messung wie _thinnest_wall, mit einer Wandkarte.
old_start = text.index("def _thinnest_wall(")
old_end = text.index("def _fits_the_wall(")
old = text[old_start:old_end]
closing = '    """' + chr(10)
doc_end = old.index(closing, old.index('"""') + 3) + len(closing)
head = old[:doc_end]
new = head + '''    return min(_walls_of_faces(solid, [edges], cancelled=cancelled)[0])


def edge_walls(
    solid: Solid, edges: Sequence[EdgeInfo], *, cancelled: CancelToken | None = None
) -> list[float]:
    """Je Kante die dünnste belegte Wand ihrer Trägerflächen (RM-279 (ii)).

    Dieselbe Messung wie :func:`_thinnest_wall`, mit **einer** Wandkarte für
    alle Kanten — sie kostet an einem Kundenteil 0,7 s. Eine Gruppe am
    exakten Körper lässt damit die Kanten aus, deren Wand die Rundung nicht
    trägt, statt ganz abzusagen. Eine Kante ohne belegte Wand bekommt null:
    Ohne Messung gibt es keine Freigabe, wie dort.
    """
    return [
        min(values) if values else 0.0
        for values in _walls_of_faces(solid, [[entry] for entry in edges], cancelled=cancelled, lenient=True)
    ]


def _walls_of_faces(
    solid: Solid,
    groups: Sequence[Sequence[EdgeInfo]],
    *,
    cancelled: CancelToken | None,
    lenient: bool = False,
) -> list[list[float]]:
    """Je Kantengruppe die dünnste Wand jeder Trägerfläche — eine Wandkarte für alle.

    ``lenient`` gibt einer Gruppe ohne Beleg eine leere Liste, statt anzuhalten.
    """
    from app.core.geom.measure import wall_thickness
    from app.core.geom.mesh import as_mesh_data
    from app.core.perceive.maps import wall_thickness_map

    try:
        mesh = as_mesh_data(solid)
        _check(cancelled)
        measured = wall_thickness_map(mesh).values
        _check(cancelled)
        if len(measured) != solid.triangle_count:
            raise _wall_not_proven()
        by_face: dict[int, float | None] = {}

        def face_wall(face: int) -> float | None:
            if face in by_face:
                return by_face[face]
            _check(cancelled)
            indices = solid.triangles_of_face(face)
            known = [
                measured[index]
                for index in indices
                if math.isfinite(measured[index]) and measured[index] > 0.0
            ]
            if not known:
                for index in indices:
                    centre = cast(
                        Vec3, tuple(float(value) for value in mesh.raw.triangles_center[index])
                    )
                    inward = cast(
                        Vec3, tuple(-float(value) for value in mesh.raw.face_normals[index])
                    )
                    value = wall_thickness(mesh, centre, inward)
                    if value is not None and math.isfinite(value) and value > 0.0:
                        known.append(value)
            by_face[face] = min(known) if known else None
            return by_face[face]

        found: list[list[float]] = []
        for group in groups:
            try:
                faces = _edge_wall_faces(solid, group)
            except GeometryError:
                if not lenient:
                    raise
                found.append([])
                continue
            values = [face_wall(face) for face in faces]
            if not values or any(value is None for value in values):
                if not lenient:
                    raise _wall_not_proven()
                found.append([])
                continue
            found.append([float(value) for value in values if value is not None])
    except GeometryError, OperationCancelled:
        raise
    except PROGRAMMING_ERRORS:
        raise
    except Exception as problem:  # ohne Messung ist der native Aufruf nicht sicher
        raise _wall_not_proven() from problem
    return found


'''
text = text[:old_start] + new + text[old_end:]
io.open(path, "w", encoding="utf-8", newline="").write(text)
print("ok")
