"""Konturen werden ausdrücklich gewählt; Innenringe gehören zu ihrem Profil."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from app.core.errors import ValidationError
from app.core.ingest import outline
from app.core.types import Profile

SOURCE = b"""<svg xmlns="http://www.w3.org/2000/svg">
<g transform="translate(7,11)">
<path d="M0 0 H20 V10 H0 Z M5 2 H15 V8 H5 Z"/>
<rect x="40" y="0" width="8" height="6"/>
</g></svg>"""


def test_profile_selection_keeps_holes_and_transforms() -> None:
    profiles = outline.read_profiles(SOURCE, ".svg")
    assert len(profiles) == 2
    ring = next(entry for entry in profiles if entry.polygon.interiors)
    assert ring.polygon.bounds == pytest.approx((7, 11, 27, 21))
    selected = json.dumps([ring.id])
    result = outline.extrude(SOURCE, ".svg", 3, contours=selected)
    assert result.mesh.is_watertight
    assert result.mesh.volume == pytest.approx((200 - 60) * 3)
    assert result.mesh.bounds.size == pytest.approx((20, 10, 3))
    assert result.contours == 1
    assert outline.extrude(SOURCE, ".svg", 3, width=40, contours=selected).mesh.volume == (
        pytest.approx((200 - 60) * 3 * 4)
    )


def test_multiple_profiles_keep_relative_positions_and_legacy_default() -> None:
    profiles = outline.read_profiles(SOURCE, ".svg")
    result = outline.extrude(SOURCE, ".svg", 2, contours=json.dumps([p.id for p in profiles]))
    legacy = outline.extrude(SOURCE, ".svg", 2)
    assert result.mesh.is_watertight
    assert result.mesh.volume == pytest.approx((140 + 48) * 2)
    assert result.mesh.bounds.size == pytest.approx((48, 10, 2))
    np.testing.assert_array_equal(result.mesh.raw.vertices, legacy.mesh.raw.vertices)
    np.testing.assert_array_equal(result.mesh.raw.faces, legacy.mesh.raw.faces)
    assert result.contours == 2


@pytest.mark.parametrize("selection", ["[]", '["missing"]', "{}", "[3]", "not json"])
def test_bad_or_empty_selection_never_falls_back_to_all(selection: str) -> None:
    with pytest.raises(ValidationError) as failure:
        outline.extrude(SOURCE, ".svg", 2, contours=selection)
    assert failure.value.field == "contours"


def test_profile_ids_follow_geometry_not_parser_order() -> None:
    a = b'<rect x="0" y="0" width="8" height="6"/>'
    b = b'<rect x="20" y="0" width="4" height="3"/>'
    first, second = b"<svg>" + a + b + b"</svg>", b"<svg>" + b + a + b"</svg>"
    assert {p.id for p in outline.read_profiles(first, ".svg")} == {
        p.id for p in outline.read_profiles(second, ".svg")
    }


def test_thin_invalid_profile_is_visible_with_reason() -> None:
    from shapely.geometry import Polygon

    profile = outline.OutlineProfile("thin", Polygon([(0, 0), (10, 0), (10, 1e-9)]))
    assert outline.profile_reason(profile)
    assert not outline.profile_reason(outline.read_profiles(SOURCE, ".svg")[0])


def test_selection_survives_project_save_open_and_undo(tmp_path: Path, profile: Profile) -> None:
    from app.core.ingest.plan import import_plan
    from app.core.scene import History, evaluate
    from app.core.scene.project import ProjectSources, load, new_project, save
    from app.core.types import Source

    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/contours.svg", sha256=""
    )
    project.sources["src_1"] = SOURCE
    plan = import_plan("src_1", "contours.svg", SOURCE)
    selected = next(p for p in outline.read_profiles(SOURCE, ".svg") if p.polygon.interiors)
    values = {"contours": json.dumps([selected.id]), "height": 4, "width": 40}
    plan.draft.params.update(values)
    History(project.document).apply(plan.title, [plan.draft])
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete, result.scene.report.findings
    body = result.scene.objects["obj_1"].mesh
    assert body.volume == pytest.approx(140 * 4 * 4)
    path = tmp_path / "contours.p3d"
    save(project, path)
    reopened = load(path)
    again = evaluate(reopened.document, profile, sources=ProjectSources(reopened))
    assert again.complete, again.scene.report.findings
    np.testing.assert_array_equal(again.scene.objects["obj_1"].mesh.raw.vertices, body.raw.vertices)
    assert reopened.sources["src_1"] == SOURCE
    history = History(reopened.document)
    history.undo()
    empty = evaluate(reopened.document, profile, sources=ProjectSources(reopened))
    assert not empty.scene.objects
    history.redo()
    restored = evaluate(reopened.document, profile, sources=ProjectSources(reopened))
    assert restored.complete
    assert restored.scene.objects["obj_1"].mesh.volume == pytest.approx(body.volume)


def test_invalid_explicit_profile_does_not_change_legacy_replay() -> None:
    from shapely.geometry import Polygon

    profiles = (outline.OutlineProfile("thin", Polygon([(0, 0), (10, 0), (10, 1e-9)])),)
    legacy = outline.extrude_profiles(profiles, 3)
    assert legacy.contours == 1
    with pytest.raises(ValidationError, match="Kontur"):
        outline.extrude_profiles(profiles, 3, contours='["thin"]')
