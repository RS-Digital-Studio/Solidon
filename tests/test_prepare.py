"""Bores, splitting, arranging and collisions (Bauplan §25, §39, §18.6)."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from app.core.geom.mesh import read_mesh
from app.core.geom.prepare import (
    BOOLEAN_OVERLAP,
    arrange_on_bed,
    bore_diameter,
    check_build_volume,
    check_collisions,
    drill,
    split_at_plane,
)
from app.core.geom.section import SectionPlane
from app.core.geom.transform import apply, translation
from app.core.ingest.loader import normalise
from app.core.knowledge import profiles
from app.core.registry import REGISTRY, VARIABLE
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import ProjectSources, new_project
from app.core.types import Document, Profile, Source
from app.i18n import _

MESHES = Path(__file__).parent / "data" / "meshes"


def plate():
    """80 x 50 x 8 mm, watertight."""
    return normalise(read_mesh((MESHES / "plate_holes.stl").read_bytes(), ".stl"), "mm").mesh


def cube():
    return normalise(read_mesh((MESHES / "cube_clean.stl").read_bytes(), ".stl"), "mm").mesh


# --- bores ----------------------------------------------------------------------


def test_a_bore_is_cut_larger_than_nominal(profile: Profile) -> None:
    """§39: FDM prints holes tight, so the bore is widened — from the profile."""
    petg = profiles.material("petg")
    assert bore_diameter(5.0, profile, compensate=True) == pytest.approx(
        5.0 + petg.hole_compensation
    )
    assert bore_diameter(5.0, profile, compensate=False) == pytest.approx(5.0)


def test_the_compensation_comes_from_the_material_not_from_a_literal() -> None:
    """AGENTS.md rule 7: tolerances are references into the profile."""
    petg = profiles.make_profile("centauri-carbon-2", "petg")
    tpu = profiles.make_profile("centauri-carbon-2", "tpu-95a")

    assert bore_diameter(5.0, petg, True) != bore_diameter(5.0, tpu, True)


def test_drilling_removes_material(profile: Profile) -> None:
    body = cube()
    result = drill(body, position=(0.0, 0.0, 0.0), axis="z", diameter=6.0, profile=profile)

    assert result.mesh.is_watertight
    assert result.mesh.volume < body.volume
    expected = body.volume - math.pi * (result.diameter / 2.0) ** 2 * 20.0
    assert result.mesh.volume == pytest.approx(expected, rel=0.01)


def test_a_blind_bore_does_not_go_through(profile: Profile) -> None:
    body = cube()
    through = drill(body, position=(0.0, 0.0, 0.0), axis="z", diameter=6.0, profile=profile)
    blind = drill(
        body, position=(0.0, 0.0, 5.0), axis="z", diameter=6.0, depth=10.0, profile=profile
    )

    assert blind.mesh.volume > through.mesh.volume, "a blind bore removes less"
    assert blind.mesh.is_watertight


@pytest.mark.parametrize("axis", ["x", "y", "z"])
def test_a_bore_follows_its_axis(axis: str, profile: Profile) -> None:
    result = drill(
        cube(),
        position=(0.0, 0.0, 0.0),
        axis=axis,
        diameter=6.0,
        profile=profile,  # type: ignore[arg-type]
    )
    assert result.mesh.is_watertight
    assert result.mesh.volume < cube().volume


def test_the_boolean_overlap_is_the_one_from_the_rule_set() -> None:
    """§39: always a hundredth of a millimetre, never coincident faces."""
    assert pytest.approx(0.01) == BOOLEAN_OVERLAP


# --- splitting ------------------------------------------------------------------


def test_splitting_yields_two_closed_halves() -> None:
    body = cube()
    first, second, findings = split_at_plane(body, SectionPlane.along("z", 0.0))

    assert first.is_watertight and second.is_watertight
    assert first.volume == pytest.approx(4000.0, rel=1e-6)
    assert second.volume == pytest.approx(4000.0, rel=1e-6)
    assert first.volume + second.volume == pytest.approx(body.volume, rel=1e-6)
    assert not findings


def test_splitting_a_plate_with_holes_stays_closed() -> None:
    body = plate()
    first, second, _findings = split_at_plane(body, SectionPlane.along("x", 0.0))

    assert first.is_watertight and second.is_watertight
    assert first.volume + second.volume == pytest.approx(body.volume, rel=1e-3)


# --- arranging ------------------------------------------------------------------


def test_arranging_puts_the_bodies_on_the_plate(profile: Profile) -> None:
    bodies = [cube(), apply(cube(), translation((200.0, 200.0, 50.0)))]
    result = arrange_on_bed(bodies, profile, spacing=5.0)

    for body in result.meshes:
        assert body.bounds.minimum[2] == pytest.approx(0.0), "everything sits on the bed"
    assert not check_collisions(result.meshes), "arranged bodies do not overlap"
    assert not result.findings, "everything fits on a 256 mm plate"
    assert result.plates == [0, 0], "one plate is enough for two cubes"


def test_arranging_keeps_the_spacing(profile: Profile) -> None:
    arranged = arrange_on_bed([cube(), cube()], profile, spacing=8.0).meshes

    gap = arranged[1].bounds.minimum[0] - arranged[0].bounds.maximum[0]
    assert gap == pytest.approx(8.0, abs=1e-6)


def test_what_sticks_out_of_the_build_volume_is_reported(profile: Profile) -> None:
    """§18.6: reported, never quietly scaled."""
    far_away = apply(cube(), translation((400.0, 0.0, 0.0)))
    findings = check_build_volume([far_away], profile)

    assert findings
    assert findings[0].code == "arrange.out_of_build_volume"
    assert findings[0].severity == "warning"


def test_overlapping_bodies_are_reported() -> None:
    findings = check_collisions([cube(), apply(cube(), translation((5.0, 0.0, 0.0)))])

    assert findings and findings[0].code == "arrange.collision"
    assert not check_collisions([cube(), apply(cube(), translation((40.0, 0.0, 0.0)))])


def test_a_clearance_makes_the_check_stricter() -> None:
    bodies = [cube(), apply(cube(), translation((25.0, 0.0, 0.0)))]

    assert not check_collisions(bodies)
    assert check_collisions(bodies, clearance=10.0), "closer than the clearance counts"


# --- as operations --------------------------------------------------------------


def loaded(document: Document, name: str = "cube_clean.stl", count: int = 1):
    project = new_project("centauri-carbon-2", "petg")
    project.document = document
    drafts = []
    for index in range(1, count + 1):
        source_id = f"src_{index}"
        document.sources[source_id] = Source(
            id=source_id, kind="import", path=f"sources/{index}_{name}", sha256=""
        )
        project.sources[source_id] = (MESHES / name).read_bytes()
        drafts.append(OperationDraft(op="load", params={"source": source_id, "unit": "mm"}))
    history = History(document)
    history.apply(_("Laden"), drafts)
    return project, history


def test_drilling_runs_as_an_operation(document: Document, profile: Profile) -> None:
    project, history = loaded(document)
    history.apply(
        _("Bohren"),
        [OperationDraft(op="drill_hole", inputs=("obj_1",), params={"diameter": 6.0, "axis": "z"})],
    )

    result = evaluate(document, profile, sources=ProjectSources(project))

    assert result.complete
    assert result.scene.objects["obj_1"].mesh.volume < 8000.0
    assert "bore.compensated" in {finding.code for finding in result.scene.report.findings}


def test_splitting_runs_as_an_operation(document: Document, profile: Profile) -> None:
    project, history = loaded(document)
    history.apply(
        _("Teilen"),
        [OperationDraft(op="split_plane", inputs=("obj_1",), params={"axis": "z"})],
    )

    result = evaluate(document, profile, sources=ProjectSources(project))

    assert result.complete
    assert list(result.scene.objects) == ["obj_2", "obj_3"]
    for entry in result.scene.objects.values():
        assert entry.mesh.is_watertight
        assert entry.mesh.volume == pytest.approx(4000.0, rel=1e-6)


def test_arranging_runs_over_every_object(document: Document, profile: Profile) -> None:
    """An operation with a variable object count: as many out as went in."""
    project, history = loaded(document, count=3)
    history.apply(
        _("Anordnen"),
        [OperationDraft(op="arrange_bed", inputs=("obj_1", "obj_2", "obj_3"))],
    )

    result = evaluate(document, profile, sources=ProjectSources(project))

    assert result.complete
    assert list(result.scene.objects) == ["obj_1", "obj_2", "obj_3"], "same objects, moved"
    for entry in result.scene.objects.values():
        assert entry.mesh.bounds.minimum[2] == pytest.approx(0.0)


def test_the_collision_check_only_reports(document: Document, profile: Profile) -> None:
    project, history = loaded(document, count=2)
    history.apply(
        _("Prüfen"),
        [OperationDraft(op="check_collisions", inputs=("obj_1", "obj_2"))],
    )

    result = evaluate(document, profile, sources=ProjectSources(project))

    assert result.complete
    assert "arrange.collision" in {finding.code for finding in result.scene.report.findings}
    assert result.scene.objects["obj_1"].mesh.volume == pytest.approx(8000.0)


def test_the_preparation_operations_are_registered_completely() -> None:
    assert REGISTRY.get("drill_hole").applies_to == ("face",)
    assert REGISTRY.get("drill_hole").requires_seed, "it uses the boolean fallback chain"
    assert REGISTRY.get("split_plane").produces == 2
    assert REGISTRY.get("arrange_bed").produces == VARIABLE
    assert REGISTRY.get("check_collisions").produces == VARIABLE
