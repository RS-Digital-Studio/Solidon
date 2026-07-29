"""The three corpus files that were missing (Bauplan §34).

Each of them exists to make one promise checkable that was previously only
written down: that the fallback chain still copes with a self-intersection,
that a 3MF written here can be read here with its colours, and that a fit pair
notices when the ground under it moves.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.export import threemf
from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData, read_mesh
from app.core.ingest.loader import normalise
from app.core.knowledge import profiles
from app.core.scene import evaluate
from app.core.scene.project import ProjectSources, load
from app.core.types import Profile

DATA = Path(__file__).parent / "data"
MESHES = DATA / "meshes"


def body(name: str) -> MeshData:
    return normalise(read_mesh((MESHES / name).read_bytes(), ".stl"), "mm").mesh


# --- the self-intersection ------------------------------------------------------


def test_a_self_intersecting_body_still_goes_through_a_boolean() -> None:
    """§17.2: the chain exists for exactly this shape.

    That the kernel currently solves it at the first stage is the finding, not
    a problem — and it is worth holding on to, because the day it stops is the
    day stages three and four earn their keep.
    """
    import trimesh

    mesh = body("broken_selfint.stl")
    tool = MeshData.of(trimesh.creation.cylinder(radius=3.0, height=60.0))

    outcome = boolean("difference", [mesh, tool])

    assert outcome.mesh.triangle_count > 0
    assert outcome.mesh.volume > 0.0
    assert outcome.solver.strategy in ("direct", "welded", "jittered", "voxel")


def test_the_two_blocks_really_do_pass_through_each_other() -> None:
    """Otherwise the file would be an ordinary union and prove nothing."""
    mesh = body("broken_selfint.stl")

    assert mesh.triangle_count == 24, "two boxes, untouched by a boolean"
    assert mesh.bounds.size[0] == pytest.approx(28.0)


# --- the colours ----------------------------------------------------------------


def test_the_coloured_file_comes_back_with_its_groups() -> None:
    payload = (MESHES / "colored.3mf").read_bytes()
    mesh = read_mesh(payload, ".3mf")

    groups = threemf.read(payload, mesh.triangle_count)

    assert groups is not None
    assert [entry.name for entry in groups.materials] == ["Rot", "Schwarz"]
    assert len(groups.slots) == mesh.triangle_count
    assert set(groups.slots) == {0, 1}


def test_both_colours_carry_real_area() -> None:
    """A group covering three triangles would pass the check above and mean nothing."""
    payload = (MESHES / "colored.3mf").read_bytes()
    mesh = read_mesh(payload, ".3mf")
    groups = threemf.read(payload, mesh.triangle_count)
    assert groups is not None

    counted = {slot: groups.slots.count(slot) for slot in set(groups.slots)}
    assert min(counted.values()) >= 8, counted


# --- the fit --------------------------------------------------------------------


def project():
    return load(DATA / "projects" / "assembly_fit.p3d")


def test_the_assembly_holds_with_the_material_it_was_built_for(profile: Profile) -> None:
    """6 mm nominal becomes a 6.2 mm bore, the pin is 5.95 — that is 0.25 of play."""
    opened = project()

    result = evaluate(opened.document, profile, sources=ProjectSources(opened))

    assert result.complete
    codes = {finding.code for finding in result.scene.report.findings}
    assert "fit.violated" not in codes, "PETG is what the numbers were chosen for"
    assert "bore.compensated" in codes, "and the bore says it was widened"


def test_the_fit_notices_when_the_ground_moves() -> None:
    """§14: the check runs on every evaluation, not once when it was written.

    Printed in another material the bore comes out differently — the tolerance
    stays what the pair says it is, and the difference is reported rather than
    quietly accepted.
    """
    opened = project()
    other = profiles.make_profile("centauri-carbon-2", "pla")

    result = evaluate(opened.document, other, sources=ProjectSources(opened))

    violations = [
        finding for finding in result.scene.report.findings if finding.code == "fit.violated"
    ]
    assert violations, "a fit written for PETG does not hold in PLA by itself"
    assert violations[0].values["fit"] == "stift_1"


def test_the_pair_points_at_features_that_exist(profile: Profile) -> None:
    opened = project()

    result = evaluate(opened.document, profile, sources=ProjectSources(opened))

    for fit in opened.document.fits:
        for reference in (fit.a, fit.b):
            entry = result.scene.objects[reference.object_id]
            assert reference.feature_id in entry.features, str(reference)
