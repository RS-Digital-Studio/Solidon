"""Reading a 3MF as the assembly it is (§17.1, §29, §40).

A slicer keeps its objects in separate files under ``3D/Objects/`` and
references them from the build. Two things went wrong with that before this
reader existed, and both are held down here: a component was resolved to the
whole file it points into instead of to the one object it names, and the parts
were welded into a single body on the way in.

The containers are built in the test rather than kept as fixtures, so the
structure that matters is visible in the file that checks it.
"""

from __future__ import annotations

import zipfile
from io import BytesIO

import pytest
import trimesh

from app.core.export import threemf
from app.core.geom.mesh import MeshData

CORE = threemf.CORE_NAMESPACE
PRODUCTION = threemf.PRODUCTION_NAMESPACE


def mesh_xml(body: trimesh.Trimesh) -> str:
    points = "".join(f'<vertex x="{x:.6f}" y="{y:.6f}" z="{z:.6f}"/>' for x, y, z in body.vertices)
    faces = "".join(f'<triangle v1="{a}" v2="{b}" v3="{c}"/>' for a, b, c in body.faces)
    return f"<mesh><vertices>{points}</vertices><triangles>{faces}</triangles></mesh>"


def objects_file(bodies: dict[str, trimesh.Trimesh]) -> str:
    entries = "".join(
        f'<object id="{identifier}" type="model">{mesh_xml(body)}</object>'
        for identifier, body in bodies.items()
    )
    return (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<model unit="millimeter" xmlns="{CORE}" xmlns:p="{PRODUCTION}">'
        f"<resources>{entries}</resources><build/></model>"
    )


def production_container(
    bodies: dict[str, trimesh.Trimesh],
    *,
    one_file: bool = True,
    names: dict[str, str] | None = None,
    transforms: dict[str, str] | None = None,
    missing: str | None = None,
) -> bytes:
    """A 3MF the way a slicer writes one: geometry outside, components inside.

    ``one_file`` puts every object into a single external model — the case that
    used to multiply, because a component resolved to the file rather than to
    the object it names.
    """
    if one_file:
        externals = {"3D/Objects/parts.model": objects_file(bodies)}
        where = dict.fromkeys(bodies, "3D/Objects/parts.model")
    else:
        externals = {
            f"3D/Objects/part_{identifier}.model": objects_file({identifier: body})
            for identifier, body in bodies.items()
        }
        where = {identifier: f"3D/Objects/part_{identifier}.model" for identifier in bodies}

    wrappers = "".join(
        f'<object id="1{identifier}" type="model"><components>'
        f'<component objectid="{"999" if missing == identifier else identifier}"'
        f' p:path="/{where[identifier]}"/>'
        f"</components></object>"
        for identifier in bodies
    )
    items = "".join(
        f'<item objectid="1{identifier}"'
        + (
            f' transform="{(transforms or {})[identifier]}"'
            if identifier in (transforms or {})
            else ""
        )
        + "/>"
        for identifier in bodies
    )
    root = (
        f'<?xml version="1.0" encoding="UTF-8"?>'
        f'<model unit="millimeter" xmlns="{CORE}" xmlns:p="{PRODUCTION}">'
        f"<resources>{wrappers}</resources><build>{items}</build></model>"
    )

    buffer = BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as container:
        container.writestr(threemf.MODEL_PATH, root)
        for path, text in externals.items():
            container.writestr(path, text)
        if names:
            parts = "".join(
                f'<object id="1{identifier}"><metadata key="name" value="{title}"/>'
                f'<part id="{identifier}"><metadata key="name" value="{title}"/></part>'
                f"</object>"
                for identifier, title in names.items()
            )
            container.writestr(
                threemf.SETTINGS_PATH, f'<?xml version="1.0"?><config>{parts}</config>'
            )
    return buffer.getvalue()


def cube(size: float, at: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> trimesh.Trimesh:
    body = trimesh.creation.box(extents=(size, size, size))
    body.apply_translation(at)
    return body


# --- the multiplication ---------------------------------------------------------


def test_three_objects_in_one_file_come_back_three_times_not_nine() -> None:
    """The bug: every component resolved to the whole file it points into.

    Measured on the corpus before the fix — a nozzle of two bodies and 290 120
    triangles arrived as four bodies and 580 240, with twice the volume.
    """
    payload = production_container(
        {"1": cube(10.0), "2": cube(20.0, (40.0, 0.0, 0.0)), "3": cube(30.0, (0.0, 40.0, 0.0))}
    )

    parts = threemf.read_objects(payload)

    assert len(parts) == 3
    volumes = sorted(round(part.mesh.volume) for part in parts)
    assert volumes == [1000, 8000, 27000], "each body once, at its own size"


def test_one_file_per_object_reads_the_same_way() -> None:
    """The other layout a slicer writes. Same answer, or the reader is guessing."""
    bodies = {"1": cube(10.0), "2": cube(20.0, (40.0, 0.0, 0.0))}

    single = threemf.read_objects(production_container(bodies, one_file=True))
    split = threemf.read_objects(production_container(bodies, one_file=False))

    assert [round(part.mesh.volume) for part in single] == [
        round(part.mesh.volume) for part in split
    ]


def test_the_count_matches_what_is_read() -> None:
    """The stack asks for the count before the geometry exists (§11)."""
    payload = production_container({"1": cube(10.0), "2": cube(20.0), "3": cube(30.0)})

    assert threemf.count_objects(payload) == len(threemf.read_objects(payload)) == 3


# --- the transforms -------------------------------------------------------------


def test_a_body_arrives_where_the_build_put_it() -> None:
    """Without the transform the parts of an assembly all sit at the origin."""
    payload = production_container(
        {"1": cube(10.0)}, transforms={"1": "1 0 0 0 1 0 0 0 1 100 50 25"}
    )

    parts = threemf.read_objects(payload)

    assert len(parts) == 1
    centre = parts[0].mesh.bounds.centre
    assert centre[0] == pytest.approx(100.0)
    assert centre[1] == pytest.approx(50.0)
    assert centre[2] == pytest.approx(25.0)


def test_a_rotation_in_the_transform_is_applied() -> None:
    """A 3MF matrix is column-major; read row-major a rotation comes out mirrored."""
    plate = trimesh.creation.box(extents=(30.0, 10.0, 4.0))
    # Ninety degrees about Z: the long side has to end up along Y.
    payload = production_container({"1": plate}, transforms={"1": "0 1 0 -1 0 0 0 0 1 0 0 0"})

    size = threemf.read_objects(payload)[0].mesh.bounds.size

    assert size[0] == pytest.approx(10.0)
    assert size[1] == pytest.approx(30.0)


# --- the names ------------------------------------------------------------------


def test_the_parts_are_called_what_the_slicer_called_them() -> None:
    """The standard leaves ``name`` empty; the slicer writes it beside the model."""
    payload = production_container(
        {"1": cube(10.0), "2": cube(20.0)},
        names={"1": "Wasserfall_1_Koerper.stl", "2": "Wasserfall_2_Deckel.stl"},
    )

    parts = threemf.read_objects(payload)

    assert [part.name for part in parts] == ["Wasserfall_1_Koerper", "Wasserfall_2_Deckel"]


def test_bodies_with_the_same_name_are_told_apart() -> None:
    payload = production_container(
        {"1": cube(10.0), "2": cube(20.0)}, names={"1": "Halter", "2": "Halter"}
    )

    assert [part.name for part in threemf.read_objects(payload)] == ["Halter 1", "Halter 2"]


def test_a_file_without_names_still_names_its_bodies() -> None:
    parts = threemf.read_objects(production_container({"1": cube(10.0)}))

    assert parts[0].name, "an object without a name is not an object without a name"


# --- what is not a readable assembly --------------------------------------------


def test_something_that_is_not_a_3mf_is_not_read() -> None:
    assert threemf.read_objects(b"not a container") == []
    assert threemf.count_objects(b"not a container") == 0


def test_a_component_pointing_at_nothing_drops_that_body_only() -> None:
    """One broken reference does not cost the other three parts."""
    parts = threemf.read_objects(
        production_container({"1": cube(10.0), "2": cube(20.0)}, missing="2")
    )

    assert len(parts) == 1
    assert round(parts[0].mesh.volume) == 1000


def test_our_own_single_body_export_reads_back_as_one_part() -> None:
    """§29 round trip: what this module writes, it reads."""
    body = MeshData.of(cube(10.0))

    parts = threemf.read_objects(threemf.write(body, name="Klotz"))

    assert len(parts) == 1
    assert parts[0].mesh.volume == pytest.approx(1000.0)
