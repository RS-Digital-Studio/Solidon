"""The three example projects (Bauplan §37.2, §40 for P8).

"The three example projects open and compute without errors" — that is the
acceptance criterion, and this is it. They are documentation and acceptance test
at the same time, so a change that breaks one of them fails here rather than in
front of a new user.
"""

from __future__ import annotations

import pytest

from app.core import examples
from app.core.knowledge import profiles
from app.core.registry import REGISTRY
from app.core.scene import evaluate
from app.core.scene.project import ProjectSources, load
from app.core.types import Profile


def test_there_is_one_example_per_way() -> None:
    """§2.2 hat drei Wege, und §37.2 will genau die drei als Beispiele.

    Die weiteren Projekte sind keine vierten Wege — sie zeigen, was auf den
    dreien an Werkzeug bereitliegt. Die drei müssen aber da sein und vorn
    stehen: sie beantworten „wie fange ich an", und das ist die erste Frage.
    """
    ways = [entry.way for entry in examples.EXAMPLES if entry.way]

    assert ways == ["1", "2", "3"]
    assert len({entry.id for entry in examples.EXAMPLES}) == len(examples.EXAMPLES)
    for entry in examples.EXAMPLES:
        assert str(entry.title).strip()
        assert str(entry.doc).strip()


def test_the_examples_reach_most_of_the_catalogue() -> None:
    """Drei Beispiele zeigten acht von zweiundsechzig Operationen (§25).

    Das ist genug, um die Wege zu erklären, und zu wenig, um das Werkzeug zu
    zeigen: die Bausteinbibliothek, die Beschriftung und die Kalibrierung waren
    in keinem davon zu sehen. Die Zahl hier ist kein Selbstzweck — sie hält
    fest, dass ein neuer Bereich auch ein Beispiel bekommt.
    """
    used: set[str] = set()
    for entry in examples.EXAMPLES:
        project = load(examples.directory() / entry.filename)
        used.update(operation.op for operation in project.document.ops)

    categories = {REGISTRY.get(name).category for name in used if REGISTRY.has(name)}

    assert len(used) >= 20, f"nur {len(used)} Operationen in allen Beispielen"
    assert {"parts", "label", "prepare", "holes", "repair", "import"} <= categories


def test_all_three_are_installed() -> None:
    found = {path.name for path in examples.paths()}

    assert found == {entry.filename for entry in examples.EXAMPLES}


@pytest.mark.parametrize("example", examples.EXAMPLES, ids=lambda entry: entry.id)
def test_an_example_opens_and_computes(example: examples.Example, profile: Profile) -> None:
    path = examples.directory() / example.filename
    project = load(path)

    result = evaluate(
        project.document,
        profiles.make_profile(
            project.document.printer or "centauri-carbon-2",
            project.document.material or "petg",
        ),
        sources=ProjectSources(project),
    )

    assert result.complete, [str(f.message) for f in result.scene.report.findings]
    assert result.scene.objects
    for entry in result.scene.objects.values():
        assert entry.mesh.volume > 0.0


def test_the_second_way_really_uses_parameters() -> None:
    """§2.2 way 2: turn a number, the model follows — so there have to be numbers."""
    project = load(examples.directory() / "weg2-halter-konstruieren.p3d")

    assert set(project.document.parameters) >= {"breite", "tiefe", "staerke"}
    bound = [
        entry
        for entry in project.document.ops
        if any(str(value).startswith("=@") for value in entry.params.values())
    ]
    assert bound, "the operations are tied to the parameters, not to fixed numbers"


def test_the_second_way_uses_the_library() -> None:
    """§39: parts before primitives — the example shows it rather than saying it."""
    project = load(examples.directory() / "weg2-halter-konstruieren.p3d")
    names = [entry.op for entry in project.document.ops]

    assert names.count("insert_screw_hole") == 2
    assert "insert_rib" in names


def test_the_third_way_says_where_its_geometry_came_from() -> None:
    """§16.3: a generated mesh is marked as generated, not as drawn."""
    project = load(examples.directory() / "weg3-generiert-aufbereiten.p3d")

    kinds = {source.kind for source in project.document.sources.values()}
    assert kinds == {"generated"}


def test_turning_a_parameter_changes_the_second_example(profile: Profile) -> None:
    """The promise of way 2, checked on the example that demonstrates it."""
    import dataclasses

    project = load(examples.directory() / "weg2-halter-konstruieren.p3d")
    sources = ProjectSources(project)
    before = evaluate(project.document, profile, sources=sources)

    parameters = project.document.parameters
    parameters["breite"] = dataclasses.replace(parameters["breite"], value=90.0)
    after = evaluate(project.document, profile, sources=sources)

    assert after.complete
    assert (
        after.scene.objects["obj_1"].mesh.bounds.size[0]
        > (before.scene.objects["obj_1"].mesh.bounds.size[0])
    )
