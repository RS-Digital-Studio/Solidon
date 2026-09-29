"""Eine Ebene an einer Bohrungswand erzeugt keine druckbare Berührlinie (RM-310).

Der Korpusfall trägt vier Durchgänge Ø 5,2 mm bei x = ±25 und y = ±15 mm.
Die STL speichert die untere Mantellinie der oberen Bohrungen als float32:
12,399999618530273 mm. Die im Bericht gerundete Zahl 12,3999996 liegt bereits
daneben und löst den Fehler nicht aus. Soll ist eine Absage mit Handgriff,
bevor Stift-Boolesche die ungeeignete Hälfte verändern oder aufs Raster fallen.
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest
import trimesh

from app.core.errors import GeometryError, UserError
from app.core.geom import autosplit, pins, prepare_ops
from app.core.geom.mesh import MeshData, read_mesh
from app.core.geom.prepare import split_at_plane
from app.core.geom.repair import branching_edge_count, open_edge_count
from app.core.geom.section import SectionPlane, cut
from app.core.ingest.loader import normalise
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import OpContext, OpResult, Profile, Quality, Scene, SceneObject

MESHES = Path(__file__).parent / "data" / "meshes"
TANGENT = float(np.float32(15.0 - 2.6))


@pytest.fixture
def plate() -> MeshData:
    return normalise(read_mesh((MESHES / "plate_holes.stl").read_bytes(), ".stl"), "mm").mesh


def run_operation(
    name: str, mesh: MeshData, profile: Profile, quality: Quality, **values: object
) -> OpResult:
    source = SceneObject(id="obj_1", name="Platte", mesh=mesh)
    spec = REGISTRY.get(name)
    return spec.fn(
        OpContext(
            scene=Scene(objects={source.id: source}),
            inputs=[source],
            params=spec.params(**values),
            profile=profile,
            quality=quality,
            seed=41,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def split_values(name: str, position: float) -> dict[str, object]:
    if name == "split_pinned":
        return {"axis": "y", "position": position}
    return {"normal_x": 0.0, "normal_y": 1.0, "normal_z": 0.0, "position": position}


def assert_contact_is_explained(problem: GeometryError | UserError) -> None:
    """Der Satz nennt die Berührlage und den Ausweg, nie einen kaputten Eingang."""
    text = f"{problem.title} {problem.detail}".lower()
    assert "wand" in text and "linie" in text
    assert "ebene" in text and "verschieb" in text
    assert "offen" not in text and "reparier" not in text
    assert "correct_input" in {action.id for action in problem.suggestions}
    assert problem.values["field"] == "position", "der Handgriff muss das Ebenenfeld öffnen"


def no_connector_calculation(*args: object, **kwargs: object) -> None:
    pytest.fail("Die ungeeignete Schnittlage muss vor dem Bau der Stifte abgesagt werden.")


@pytest.mark.parametrize("quality", ["draft", "fine"])
@pytest.mark.parametrize("name", ["split_pinned", "split_line"])
@pytest.mark.parametrize("count", [0, 2])
def test_a_tangent_cut_is_refused_before_building_connectors(
    plate: MeshData,
    profile: Profile,
    monkeypatch: pytest.MonkeyPatch,
    quality: Quality,
    name: str,
    count: int,
) -> None:
    """Beide Kundenwege und Güten sagen dieselbe Geometrie ab, auch ohne Stifte."""
    vertices, faces = plate.raw.vertices.copy(), plate.raw.faces.copy()
    assert plate.is_watertight
    monkeypatch.setattr(prepare_ops, "add_pins", no_connector_calculation)

    with pytest.raises((GeometryError, UserError)) as problem:
        run_operation(name, plate, profile, quality, pins=count, **split_values(name, TANGENT))

    assert_contact_is_explained(problem.value)
    np.testing.assert_array_equal(plate.raw.vertices, vertices)
    np.testing.assert_array_equal(plate.raw.faces, faces)


@pytest.mark.parametrize("flipped", [False, True])
def test_the_shared_split_rejects_the_new_contact(plate: MeshData, flipped: bool) -> None:
    """Das Urteil gehört zum gemeinsamen Schnitt, unabhängig von der Stiftseite."""
    plane = SectionPlane.along("y", TANGENT)
    with pytest.raises((GeometryError, UserError)) as problem:
        split_at_plane(plate, plane.flipped() if flipped else plane)
    assert_contact_is_explained(problem.value)


@pytest.mark.parametrize("quality", ["draft", "fine"])
def test_cut_away_rejects_the_contact_only_on_the_retained_side(
    plate: MeshData,
    profile: Profile,
    quality: Quality,
) -> None:
    """Oberhalb berührt die Wand den Deckel; unterhalb bleibt eine gewöhnliche Platte."""
    with pytest.raises((GeometryError, UserError)) as problem:
        run_operation("cut_away", plate, profile, quality, axis="y", position=TANGENT, keep="above")
    assert_contact_is_explained(problem.value)

    result = run_operation(
        "cut_away", plate, profile, quality, axis="y", position=TANGENT, keep="below"
    )
    assert len(result.outputs) == 1
    assert result.outputs[0].mesh.is_watertight
    # Kasten bis zur Ebene minus zwei der vier gleichen Bohrungen. Deren
    # Volumen kommt vom fehlenden Material der Eingabe, nicht vom Schnitt;
    # so bleibt die Polygonform der STL statt eines angenäherten Kreises maßgebend.
    two_bores = (80.0 * 50.0 * 8.0 - plate.volume) / 2.0
    expected = 80.0 * (25.0 + TANGENT) * 8.0 - two_bores
    assert result.outputs[0].mesh.volume == pytest.approx(expected, rel=1e-10)


@pytest.mark.parametrize("quality", ["draft", "fine"])
@pytest.mark.parametrize("name", ["split_pinned", "split_line"])
@pytest.mark.parametrize("position", [12.39, 12.3999996, 12.41])
def test_moving_the_plane_either_way_makes_the_pinned_cut_work(
    plate: MeshData,
    profile: Profile,
    quality: Quality,
    name: str,
    position: float,
) -> None:
    """Der vorgeschlagene Handgriff funktioniert beiderseits der Mantellinie."""
    result = run_operation(name, plate, profile, quality, pins=2, **split_values(name, position))
    assert len(result.outputs) == 2
    assert all(output.mesh.is_watertight for output in result.outputs)
    assert {"pin_1", "pin_2"} <= result.outputs[0].features.keys()
    assert {"bore_1", "bore_2"} <= result.outputs[1].features.keys()
    assert result.solver is not None and result.solver.strategy == "direct"


@pytest.mark.parametrize("name", ["split_pinned", "cut_away"])
@pytest.mark.parametrize("damage", ["open", "branched"])
def test_an_input_that_was_already_open_keeps_its_own_diagnosis(
    plate: MeshData,
    profile: Profile,
    name: str,
    damage: str,
) -> None:
    """Alte offene oder verzweigte Kanten belegen keine tangierende Schnittlage."""
    raw = plate.raw.copy()
    if damage == "open":
        raw.update_faces(np.arange(1, len(raw.faces)))
    else:
        raw.faces = np.vstack((raw.faces, raw.faces[:1]))
    mesh = MeshData(raw)
    assert not mesh.is_watertight
    if damage == "branched":
        assert open_edge_count(mesh) == 0 and branching_edge_count(mesh) > 0
    values: dict[str, object] = {"axis": "y", "position": TANGENT}
    if name == "split_pinned":
        values["pins"] = 0
    result = run_operation(name, mesh, profile, "draft", **values)
    expected = "split.uncapped" if name == "split_pinned" else "cut_away.uncapped"
    finding = next(entry for entry in result.findings if entry.code == expected)
    assert "vor" in str(finding.message) and "Reparieren" in str(finding.message)


def test_auto_split_discards_contact_before_judging_connectors(
    plate: MeshData,
    profile: Profile,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Eine ungeeignete Kandidatenebene ist unbrauchbar, kein Raster- oder Stiftversuch."""
    candidate = autosplit.Candidate(axis="y", position=TANGENT, area=1.0, contours=1, score=0.0)
    monkeypatch.setattr(pins, "add_pins", no_connector_calculation)
    first, second, findings = autosplit._cut_in_two(plate, candidate)
    assert first is None and second is None
    assert any("Wand" in str(finding.message) for finding in findings)
    assert all("uncapped" not in finding.code for finding in findings)
    assert autosplit._support_after_cut(
        plate, candidate, profile, orientation_candidates=1, cancelled=None, connector_count=2
    ) == float("inf")


@pytest.mark.parametrize("contours", [1, 2])
def test_auto_split_replaces_contact_candidates_beyond_the_first_shortlist(
    plate: MeshData,
    profile: Profile,
    monkeypatch: pytest.MonkeyPatch,
    contours: int,
) -> None:
    """Ein ungültiger Erstplatz sperrt weder die nächste Naht noch die nächste Konturzahl."""
    touching = autosplit.Candidate(axis="y", position=TANGENT, area=640.0, contours=1, score=0.0)
    usable = replace(touching, position=12.39, contours=contours, score=1.0)
    monkeypatch.setattr(
        autosplit, "_candidate_pool", lambda *args, **kwargs: ([touching, usable], 0, (12.3, 12.5))
    )
    search = autosplit.search_plane(
        plate, profile, axis="y", support_planes=1, support_orientations=1, connector_count=0
    )
    assert search.candidate == usable
    first, second, _findings = split_at_plane(plate, search.candidate.plane)
    assert first.is_watertight and second.is_watertight


def test_the_sequence_planner_skips_a_contact_candidate(
    plate: MeshData,
    profile: Profile,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die Schnittfolgensuche nimmt denselben geometrisch gültigen Ersatz."""
    touching = autosplit.Candidate(axis="y", position=TANGENT, area=640.0, contours=1, score=0.0)
    usable = replace(touching, position=12.39, score=1.0)
    choices = [touching, usable]
    monkeypatch.setattr(
        autosplit, "_candidate_pool", lambda *args, **kwargs: (choices, 0, (12.3, 12.5))
    )
    monkeypatch.setattr(autosplit, "_alternatives", lambda *args, **kwargs: choices)
    search = autosplit._plan_step(
        plate,
        profile,
        axis="y",
        allowance=0.0,
        reserve=(0.0, 0.0, 0.0),
        samples=2,
        protect=(),
        room=2,
        budget=autosplit._Budget(2),
        cancelled=None,
        progress=None,
    )
    assert search.candidate == usable
    assert search.halves is not None
    assert search.halves[0].is_watertight and search.halves[1].is_watertight


def test_auto_split_reports_contact_when_no_candidate_is_usable(
    plate: MeshData,
    profile: Profile,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Auch am Ende der Suche steht der konkrete Grund; die Platte bleibt unangetastet."""
    touching = autosplit.Candidate(axis="y", position=TANGENT, area=640.0, contours=1, score=0.0)
    monkeypatch.setattr(
        autosplit, "_candidate_pool", lambda *args, **kwargs: ([touching], 0, (12.3, 12.5))
    )
    small = replace(profile, printer=replace(profile.printer, build_volume=(100.0, 40.0, 30.0)))
    outcome = autosplit.split_to_fit(plate, small, pins=0, margin=0.0)
    assert not outcome.divided and not outcome.cuts
    assert outcome.parts == [plate]
    problems = [finding for finding in outcome.findings if finding.code == "split.surface_contact"]
    assert len(problems) == 1
    assert "Wand" in str(problems[0].message) and "Verschieben" in str(problems[0].message)
    assert "split_along_line" in {action.id for action in problems[0].suggestions}
    assert "split.cut_failed" not in {finding.code for finding in outcome.findings}


@pytest.mark.parametrize("name", ["split_pinned", "cut_away"])
@pytest.mark.parametrize("quality", ["draft", "fine"])
def test_touching_closed_shells_remain_usable(
    profile: Profile,
    name: str,
    quality: Quality,
) -> None:
    """Zwei eigene geschlossene Schalen dürfen sich flächig berühren: kein neuer Defekt."""
    first = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    second = first.copy()
    second.apply_translation((20.0, 0.0, 0.0))
    mesh = MeshData(trimesh.util.concatenate([first, second]))
    values: dict[str, object] = {"axis": "z", "position": 0.0}
    if name == "split_pinned":
        values["pins"] = 0
    result = run_operation(name, mesh, profile, quality, **values)
    for output in result.outputs:
        assert output.mesh.is_watertight
        assert output.mesh.component_count == 2
        assert output.mesh.volume == pytest.approx(8000.0, rel=1e-9)


def test_the_diagnostic_slice_keeps_the_exact_geometry_visible(plate: MeshData) -> None:
    """Eine reine Schnittansicht darf die Berührlage zeigen; sie ändert kein Modell."""
    visible = cut(plate, SectionPlane.along("y", TANGENT).flipped())
    assert visible.mesh.triangle_count > 0
    assert visible.mesh.bounds.minimum[1] == pytest.approx(TANGENT, abs=1e-12)
    # Die obere Hälfte trägt die anderen zwei gleichen Bohrungen der Eingabe.
    two_bores = (80.0 * 50.0 * 8.0 - plate.volume) / 2.0
    expected = 80.0 * (25.0 - TANGENT) * 8.0 - two_bores
    assert visible.mesh.volume == pytest.approx(expected, rel=1e-10)
