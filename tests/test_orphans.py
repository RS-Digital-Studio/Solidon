"""Feature references that lost their feature (Bauplan §21.3)."""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.errors import AmbiguityError
from app.core.geom.mesh import read_mesh
from app.core.ingest.loader import normalise
from app.core.perceive.features import detect
from app.core.scene import orphans
from app.core.types import Document, FeatureRef, Fit, Profile, Scene, SceneObject

MESHES = Path(__file__).parent / "data" / "meshes"


@pytest.fixture
def scene(profile: Profile) -> Scene:
    mesh = normalise(read_mesh((MESHES / "plate_holes.stl").read_bytes(), ".stl"), "mm").mesh
    entry = SceneObject(id="obj_1", name="Platte", mesh=mesh, features=detect(mesh))
    return Scene(objects={"obj_1": entry}, profile=profile)


def document_with(*fits: Fit) -> Document:
    document = Document(format_version=1, app_version="0.0.1")
    document.fits.extend(fits)
    return document


def fit_to(feature_id: str, name: str = "stift_1") -> Fit:
    """Both sides on the plate, so only the side under test can go missing."""
    return Fit(
        name=name,
        a=FeatureRef("obj_1", feature_id),
        b=FeatureRef("obj_1", "hole_4"),
        kind="clearance",
    )


def refuse(question: str, choices: list[str]) -> str:
    raise AmbiguityError(question, candidates=tuple(choices))


def test_references_that_resolve_are_left_alone(scene: Scene) -> None:
    document = document_with(fit_to("hole_1"))

    result = orphans.check(document, scene, refuse)

    assert result.findings == []
    assert not result.changed


def test_a_lost_reference_is_put_to_the_user(scene: Scene) -> None:
    """§21.3: the chain asks, it never picks a hole by itself."""
    document = document_with(fit_to("hole_9"))
    asked: list[tuple[str, list[str]]] = []

    def answer(question: str, choices: list[str]) -> str:
        asked.append((question, choices))
        return "hole_2"

    result = orphans.check(document, scene, answer)

    assert asked and "hole_9" in asked[0][0]
    assert "hole_1" in asked[0][1], "the candidates are the holes of the same object"
    assert document.fits[0].a.feature_id == "hole_2", "the answer is written into the file"
    assert result.rewritten == 1
    assert result.findings[0].code == "feature.rewritten"


def test_the_question_is_asked_once_not_on_every_run(scene: Scene) -> None:
    document = document_with(fit_to("hole_9"))
    calls: list[str] = []

    def answer(question: str, choices: list[str]) -> str:
        calls.append(question)
        return "hole_2"

    orphans.check(document, scene, answer)
    orphans.check(document, scene, answer)

    assert len(calls) == 1, "after the rewrite the reference resolves by itself"


def test_the_user_can_drop_the_fit_instead(scene: Scene) -> None:
    document = document_with(fit_to("hole_9"))

    result = orphans.check(document, scene, lambda question, choices: orphans.REMOVE_CHOICE)

    assert document.fits == []
    assert result.removed == 1
    assert result.findings[0].code == "feature.orphaned"


def test_a_reference_without_any_candidate_is_an_error(scene: Scene) -> None:
    """Nothing to choose from means nothing to ask — it is reported, not guessed."""
    document = document_with(
        Fit(
            name="weg",
            a=FeatureRef("obj_7", "hole_1"),
            b=FeatureRef("obj_2", "pin_1"),
            kind="clearance",
        )
    )

    result = orphans.check(document, scene, refuse)

    assert result.findings[0].severity == "error"
    assert not result.changed


def test_the_candidates_keep_to_the_kind(scene: Scene) -> None:
    """A hole is replaced by a hole, never by a face."""
    document = document_with(fit_to("hole_9"))
    seen: list[list[str]] = []

    orphans.check(document, scene, lambda question, choices: seen.append(choices) or "hole_1")

    assert all(name.startswith("hole_") for name in seen[0][:-1])
    assert seen[0][-1] == orphans.REMOVE_CHOICE


def test_both_sides_of_a_fit_are_checked(scene: Scene) -> None:
    document = document_with(
        Fit(
            name="stift_1",
            a=FeatureRef("obj_1", "hole_1"),
            b=FeatureRef("obj_1", "hole_9"),
            kind="clearance",
        )
    )

    orphans.check(document, scene, lambda question, choices: "hole_3")

    assert document.fits[0].b.feature_id == "hole_3"


def test_the_references_of_a_document_are_listed() -> None:
    document = document_with(fit_to("hole_1"), fit_to("hole_2", name="stift_2"))

    found = orphans.references(document)

    assert [entry.where for entry in found] == [
        "fit:stift_1:a",
        "fit:stift_1:b",
        "fit:stift_2:a",
        "fit:stift_2:b",
    ]
    assert found[0].fit_name == "stift_1"
    assert found[1].side == "b"


def test_the_candidates_can_be_shown_highlighted(scene: Scene) -> None:
    """§21.3 wants the candidates marked in the view, so they come with their data."""
    found = orphans.candidates_of(scene, FeatureRef("obj_1", "hole_9"))

    assert found and all(feature.kind == "hole" for feature in found.values())
