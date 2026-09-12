"""Druckkontur, Sperrzonen und Orientierungen an analytischen Fehlerfällen."""

from dataclasses import replace

import pytest
import trimesh
from shapely.geometry import box

from app.core.geom.mesh import MeshData
from app.core.geom.orient import orient_for_print
from app.core.geom.prepare import arrange_on_bed, check_build_volume
from app.core.knowledge.profiles import make_profile
from app.core.slice.orientation import search


def body(size, centre=None):
    mesh = trimesh.creation.box(extents=size)
    mesh.apply_translation(centre or (0.0, 0.0, size[2] / 2.0))
    return MeshData.of(mesh)


def test_cc2_excluded_corner_is_not_printable():
    profile = make_profile("centauri-carbon-2")
    mesh = body((4.0, 4.0, 1.0), (123.0, -118.0, 0.5))
    assert check_build_volume([mesh], profile, about_to_write=True)


def test_arrangement_cannot_hide_an_excluded_corner():
    profile = make_profile("centauri-carbon-2")
    result = arrange_on_bed([body((246.0, 246.0, 1.0))], profile, spacing=5.0)
    mesh = result.meshes[0]
    bounds = mesh.bounds
    overlap = box(*bounds.minimum[:2], *bounds.maximum[:2]).intersection(box(118, -128, 128, -108))
    assert overlap.area <= 0.0 or result.findings


@pytest.mark.parametrize("printer_id", ["bambu-p1s", "bambu-x1c"])
def test_bambu_profiles_use_the_proven_printable_height(printer_id):
    profile = make_profile(printer_id)
    assert check_build_volume([body((20.0, 20.0, 253.0))], profile, about_to_write=True)


def test_search_keeps_the_only_fitting_axis():
    profile = make_profile()
    profile = replace(profile, printer=replace(profile.printer, build_volume=(100, 100, 250)))
    result = search(body((20, 20, 200)), profile=profile, count=8)
    assert result.mesh.bounds.size[2] == pytest.approx(200.0)
    assert not check_build_volume([result.mesh], profile)


def test_search_turns_on_the_plate_before_rejecting_a_flat_body():
    profile = make_profile()
    profile = replace(profile, printer=replace(profile.printer, build_volume=(200, 100, 250)))
    result = search(body((30, 180, 10)), profile=profile, count=8)
    assert result.mesh.bounds.size[2] == pytest.approx(10.0)
    assert not check_build_volume([result.mesh], profile)


def test_search_preserves_a_useful_xy_position_after_tilting():
    profile = make_profile("centauri-carbon-2")
    result = search(body((20, 20, 200)), profile=profile, count=8)
    assert not check_build_volume([result.mesh], profile)


def test_unknown_optional_area_has_a_defined_nominal_rectangle():
    from app.core.build_area import printable_area

    printer = make_profile().printer
    assert printable_area(printer).equals(box(-110, -110, 110, 110))


def test_explicit_profile_area_can_be_larger_than_nominal():
    from app.core.build_area import fits_on_bed

    printer = replace(
        make_profile().printer,
        printable_area=((-115, -115), (115, -115), (115, 115), (-115, 115)),
    )
    assert fits_on_bed(body((228, 228, 1)), printer)
    assert printer.build_volume[0] == 220


def test_job_margin_changes_clearance_without_changing_the_machine():
    from app.core.build_area import fits_on_bed, printable_area

    printer = make_profile("centauri-carbon-2").printer
    mesh = body((4, 4, 1), (115, -118, 0.5))
    area_before = printable_area(printer)
    assert fits_on_bed(mesh, printer)
    assert not fits_on_bed(mesh, printer, margin=2.0)
    assert area_before.equals(printable_area(printer))


def test_a_ring_can_surround_an_exclusion_without_entering_it():
    from app.core.build_area import fits_on_bed

    mesh = MeshData.of(trimesh.creation.annulus(r_min=10, r_max=20, height=2))
    mesh.raw.apply_translation((0, 0, 1))
    printer = replace(
        make_profile().printer,
        bed_exclusions=(((-5, -5), (5, -5), (5, 5), (-5, 5)),),
    )
    assert fits_on_bed(mesh, printer)


def test_nonrectangular_bed_rejects_a_body_inside_only_the_bounds():
    from app.core.build_area import fits_on_bed, placement_offset

    printer = replace(
        make_profile().printer,
        printable_area=((-100, 0), (0, -100), (100, 0), (0, 100)),
    )
    mesh = body((10, 10, 10), (80, 80, 5))
    assert not fits_on_bed(mesh, printer)
    assert placement_offset(mesh, printer) is not None


def test_fast_orientation_uses_the_same_printable_limits():
    from app.core.build_area import fits_on_bed

    printer = replace(make_profile().printer, build_volume=(100, 100, 250))
    result = orient_for_print(body((20, 20, 200)), printer=printer)
    assert fits_on_bed(result.mesh, printer)
    assert result.mesh.bounds.size[2] == pytest.approx(200)


def test_impossible_orientations_are_never_sliced(monkeypatch):
    from app.core.errors import GeometryError
    from app.core.slice import orientation

    profile = make_profile()
    profile = replace(profile, printer=replace(profile.printer, build_volume=(10, 10, 10)))
    monkeypatch.setattr(orientation, "judge", lambda *_args: pytest.fail("impossible pose sliced"))
    with pytest.raises(GeometryError):
        orientation.search(body((20, 20, 20)), profile=profile)


def test_an_impossible_baseline_has_no_fabricated_support_comparison():
    profile = make_profile()
    profile = replace(profile, printer=replace(profile.printer, build_volume=(100, 100, 250)))
    result = search(body((200, 20, 20)), profile=profile, count=8)
    assert result.baseline is None
    assert result.findings[0].values.get("saved") is None
    assert not check_build_volume([result.mesh], profile)


def test_the_reported_transform_produces_the_exact_chosen_placement():
    import numpy as np

    from app.core.geom.transform import apply

    profile = make_profile()
    profile = replace(profile, printer=replace(profile.printer, build_volume=(200, 100, 250)))
    mesh = body((30, 180, 10))
    result = search(mesh, profile=profile, count=8)
    np.testing.assert_allclose(apply(mesh, result.transform).raw.vertices, result.mesh.raw.vertices)


@pytest.mark.parametrize(
    "extra",
    [
        {"printable_height": -1.0},
        {"printable_height": float("nan")},
        {"printable_area": [[0, 0], [10, 0], [5, 0]]},
        {"printable_area": [[0, 0], [10, 0], [5, float("nan")]]},
        {"printable_area": [[0, 0, 4], [10, 0], [5, 5]]},
        {"bed_exclusions": [[[0, 0], [10, 0]]]},
    ],
)
def test_invalid_optional_printer_geometry_is_rejected(extra):
    from pathlib import Path

    from app.core.errors import ValidationError
    from app.core.knowledge.profiles import _printer_from_table

    with pytest.raises(ValidationError):
        _printer_from_table(
            "custom", {"build_volume": [100, 100, 100], **extra}, Path("printers.toml")
        )


@pytest.mark.parametrize("field", ["printable_height", "printable_area", "bed_exclusions"])
def test_invalid_build_limits_offer_a_printer_profile_change(field):
    """Ein Maschinenfehler verlangt kein Feld, das im Operationsdialog gar nicht existiert."""
    from app.core.build_area import printable_area, printable_height
    from app.core.errors import CHOOSE_PRINTER, ValidationError

    invalid = ((0.0, 0.0), (10.0, 0.0), (5.0, 0.0))
    value = (
        -1.0
        if field == "printable_height"
        else (invalid,)
        if field == "bed_exclusions"
        else invalid
    )
    printer = replace(make_profile().printer, **{field: value})

    with pytest.raises(ValidationError) as caught:
        if field == "printable_height":
            printable_height(printer)
        else:
            printable_area(printer)

    assert caught.value.suggestions == (CHOOSE_PRINTER,)
    assert "Prüfen Sie das Druckerprofil." in str(caught.value)


def test_auto_split_does_not_claim_a_nominally_fitting_body_is_printable():
    from app.core.geom import autosplit

    profile = make_profile("centauri-carbon-2")
    mesh = body((248, 248, 10))
    assert not autosplit.fits(mesh, profile)
    outcome = autosplit.split_to_fit(mesh, profile, max_parts=1, pins=0)
    assert "split.too_many_parts" in {finding.code for finding in outcome.findings}


def test_auto_split_counts_the_real_height_without_a_guessed_top_margin():
    from app.core.geom import autosplit

    profile = make_profile("bambu-p1s")
    assert autosplit.oversize(body((20, 20, 253)), profile)[2] == pytest.approx(3)


def test_auto_split_rejects_an_unprintable_support_candidate_without_crashing():
    import math

    from app.core.geom import autosplit

    profile = make_profile()
    profile = replace(profile, printer=replace(profile.printer, build_volume=(10, 10, 10)))
    cost = autosplit._support_after_cut(
        body((40, 40, 40)),
        autosplit.Candidate("x", 0, 1600, 1, 0),
        profile,
        orientation_candidates=3,
        cancelled=None,
    )
    assert math.isinf(cost)


def test_auto_split_finishes_only_after_every_part_fits_the_actual_contour():
    from app.core.geom import autosplit

    profile = make_profile("centauri-carbon-2")
    mesh = body((248, 248, 10))
    result = autosplit.split_to_fit(mesh, profile, max_parts=4, pins=0)
    assert result.divided
    assert all(autosplit.fits(part, profile) for part in result.parts)
    assert sum(part.volume for part in result.parts) == pytest.approx(mesh.volume)


def test_projected_near_collinear_facets_keep_the_valid_footprint():
    """Dreiecksbreiten aus Drehungsrauschen dürfen den Overlay nicht abbrechen."""
    import numpy as np
    from shapely.geometry import Point

    from app.core.build_area import footprint
    from app.core.units import EPS_GEOM

    triangles = np.asarray(
        [
            # Wertebereich aus dem Autosplit-Torfall; die Seitenfläche ist
            # nach der Drehung in XY praktisch eine senkrechte Linie.
            [(5.782e-15, 24.963, 0), (4.359e-15, 16.629, 1), (-4.745e-16, 8.334, 2)],
            [(4.359e-15, 16.629, 1), (5.782e-15, 24.963, 0), (2.1e-15, 20, 3)],
            [(0, 0, 0), (6, 0, 0), (6, 25, 0)],
            [(0, 0, 0), (6, 25, 0), (0, 25, 0)],
            # Die genau linienförmige Projektion bleibt als Geometrie erhalten.
            [(6, 12, 0), (8, 12, 1), (10, 12, 2)],
        ],
        dtype=float,
    )
    mesh = MeshData.of(
        trimesh.Trimesh(
            vertices=triangles.reshape(-1, 3),
            faces=np.arange(triangles.size // 3).reshape(-1, 3),
            process=False,
        )
    )
    before = mesh.raw.vertices.copy()
    projected = footprint(mesh)
    assert projected.is_valid
    assert projected.area == pytest.approx(150.0, abs=EPS_GEOM)
    assert projected.covers(Point(9, 12))
    assert np.array_equal(mesh.raw.vertices, before)


def test_a_real_thin_region_is_not_discarded_by_its_small_area():
    """Ein langer schmaler Bereich bleibt oberhalb des Präzisionsmaßes erhalten."""
    from shapely.geometry import Point

    from app.core.build_area import footprint
    from app.core.units import EPS_GEOM

    width = 4.0 * EPS_GEOM
    projected = footprint(body((25.0, width, 1.0)))
    assert projected.is_valid
    assert projected.area == pytest.approx(25.0 * width, rel=EPS_GEOM)
    assert projected.covers(Point(0.0, width / 4.0))


def test_precision_overlay_keeps_a_ring_hole_and_exclusion_decision():
    """Das Präzisionsraster darf keine Hülle über den ausgesparten Ring legen."""
    from shapely.geometry import Point

    from app.core.build_area import fits_on_bed, footprint
    from app.core.units import EPS_GEOM

    raw = trimesh.creation.annulus(r_min=10.0, r_max=20.0, height=2.0, sections=64)
    raw.apply_translation((0.0, 0.0, 1.0))
    mesh = MeshData.of(raw)
    projected = footprint(mesh)
    assert projected.is_valid
    assert not projected.covers(Point(0.0, 0.0))
    assert projected.covers(Point(15.0, 0.0))
    printer = replace(
        make_profile().printer,
        bed_exclusions=(((-5.0, -5.0), (5.0, -5.0), (5.0, 5.0), (-5.0, 5.0)),),
    )
    assert fits_on_bed(mesh, printer)
    crossed = replace(
        printer,
        bed_exclusions=(((12.0, -2.0), (18.0, -2.0), (18.0, 2.0), (12.0, 2.0)),),
    )
    assert not fits_on_bed(mesh, crossed)
    assert projected.symmetric_difference(footprint(mesh)).area <= EPS_GEOM * EPS_GEOM


def test_split_oversized_fixture_reaches_orientation_without_overlay_error():
    """Der echte Autosplit-Eingang durchläuft Schnitt und Orientierungs-Vorauswahl."""
    from pathlib import Path

    from app.core.geom.mesh import read_mesh
    from app.core.geom.orient import ranked_orientations
    from app.core.geom.prepare import split_at_plane
    from app.core.geom.section import SectionPlane
    from app.core.ingest.loader import normalise

    source = Path(__file__).parent / "data/meshes/oversized.stl"
    mesh = normalise(read_mesh(source.read_bytes(), ".stl"), "mm").mesh
    first, second, _findings = split_at_plane(mesh, SectionPlane.along("x", 0.0))
    printer = make_profile("centauri-carbon-2").printer
    for part in (first, second):
        assert ranked_orientations(part, limit=4, printer=printer)


@pytest.mark.parametrize("area", [box(-10, -10, 10, 10), box(0, 0, 0, 0)])
def test_outside_bounds_never_build_the_triangle_union(monkeypatch, area):
    """Ein bereits außerhalb liegendes Netz braucht keine projizierten Dreiecke."""
    from app.core import build_area

    monkeypatch.setattr(build_area, "footprint", lambda _mesh: pytest.fail("unneeded union"))
    assert not build_area.fits_xy(body((5, 5, 1), (20, 0, 0.5)), area)


@pytest.mark.parametrize(
    ("centre", "expected"),
    [((150, 0, 5), (-50, 0, 0)), ((-150, 140, 5), (50, -40, 0))],
)
def test_moving_into_a_clear_rectangle_needs_no_triangle_union(monkeypatch, centre, expected):
    """Die gleiche Verschiebung bleibt auch für große Dreiecksnetze günstig."""
    from app.core import build_area

    monkeypatch.setattr(build_area, "footprint", lambda _mesh: pytest.fail("unneeded union"))
    result = build_area.placement_offset(body((20, 20, 10), centre), make_profile().printer)
    assert result == pytest.approx(expected)


def test_a_clear_shift_on_a_bed_with_an_exclusion_needs_no_union(monkeypatch):
    from app.core import build_area

    printer = replace(
        make_profile().printer,
        printable_area=((-50, -40), (60, -40), (60, 50), (-50, 50)),
        bed_exclusions=(((-50, -40), (-40, -40), (-40, -30), (-50, -30)),),
    )
    monkeypatch.setattr(build_area, "footprint", lambda _mesh: pytest.fail("unneeded union"))
    assert build_area.placement_offset(body((10, 10, 10), (80, 0, 5)), printer) == (-25, 0, 0)


def test_a_fitting_ring_keeps_its_original_xy_position():
    from app.core.build_area import placement_offset

    raw = trimesh.creation.annulus(r_min=10, r_max=20, height=2)
    raw.apply_translation((25, 30, 4))
    printer = replace(
        make_profile().printer,
        bed_exclusions=(((20, 25), (30, 25), (30, 35), (20, 35)),),
    )
    assert placement_offset(MeshData.of(raw), printer) == pytest.approx((0, 0, -3))


def test_placement_reuses_the_union_when_the_original_pose_hits_an_exclusion(monkeypatch):
    from app.core import build_area
    from app.core.geom.transform import apply, translation

    original = build_area.footprint
    calls = []

    def counted(mesh):
        calls.append(mesh)
        return original(mesh)

    monkeypatch.setattr(build_area, "footprint", counted)
    printer = replace(
        make_profile().printer,
        bed_exclusions=(((-5, -5), (5, -5), (5, 5), (-5, 5)),),
    )
    mesh = body((4, 4, 1))
    offset = build_area.placement_offset(mesh, printer)
    assert offset is not None
    assert len(calls) == 1
    assert build_area.fits_on_bed(apply(mesh, translation(offset)), printer)
