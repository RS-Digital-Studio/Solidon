"""The acceptance criteria of phase P0 (Bauplan §40), one test each.

A phase is finished when its criteria are green — not when it feels complete.
This file is the proof, so each test names the criterion it stands for.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

import pytest

from app.core.errors import ValidationError
from app.core.knowledge import licences, profiles
from app.core.registry import (
    REGISTRY,
    cli_commands,
    context_menu,
    menu_tree,
    palette_entries,
    tool_schemas,
)
from app.core.scene import History, OperationDraft, ResultCache, evaluate
from app.core.scene.expressions import check as check_expression
from app.core.scene.project import PROJECT_ENTRY, ProjectSources, load, new_project, save
from app.core.types import Parameter, Profile, Source
from app.i18n import _

MESHES = Path(__file__).parent / "data" / "meshes"


def project_with(name: str, unit: str = "auto"):
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path=f"sources/{name}", sha256=""
    )
    project.sources["src_1"] = (MESHES / name).read_bytes()
    History(project.document).apply(
        _("Laden"), [OperationDraft(op="load", params={"source": "src_1", "unit": unit})]
    )
    return project


# 1 — core importable without Qt: tests/test_core_isolation.py
# 2 — language rules: tests/test_language_rules.py


def test_operations_are_visible_in_every_surface(qt_app: object) -> None:
    """§40: at least two operations, visible in menu, palette, context menu, CLI, tools."""
    names = {spec.name for spec in REGISTRY.all()}
    assert len(names) >= 2

    assert {spec.name for section in menu_tree() for spec in section.entries} == names
    assert {entry.name for entry in palette_entries()} == names
    assert {command.name for command in cli_commands()} == names
    assert {schema["name"] for schema in tool_schemas()} == names

    # The object context menu offers every operation that works on one object;
    # the feature context menu over applies_to gets its entries in P2/P3.
    from app.ui.panels import ObjectTree

    offered = {spec.name for spec in ObjectTree.operations_for_object(None)}  # type: ignore[arg-type]
    assert offered == {spec.name for spec in REGISTRY.all() if spec.consumes == 1}
    assert context_menu("hole") == ()


def test_saving_and_loading_keeps_the_stack_bit_identical(tmp_path: Path) -> None:
    """§40: project save and load preserves the stack bit for bit."""
    project = project_with("cube_clean.stl", unit="mm")
    first = save(project, tmp_path / "a.p3d")
    second = save(load(first), tmp_path / "b.p3d")

    with zipfile.ZipFile(first) as one, zipfile.ZipFile(second) as two:
        assert one.read(PROJECT_ENTRY) == two.read(PROJECT_ENTRY)


def test_evaluating_twice_gives_identical_geometry(profile: Profile) -> None:
    """§40: two evaluations produce the same geometry."""
    project = project_with("cube_clean.stl", unit="mm")
    sources = ProjectSources(project)

    first = evaluate(project.document, profile, sources=sources)
    second = evaluate(project.document, profile, sources=sources)

    assert first.object_hashes == second.object_hashes
    for object_id, entry in first.scene.objects.items():
        other = second.scene.objects[object_id]
        assert entry.mesh.volume == pytest.approx(other.mesh.volume)
        assert entry.mesh.triangle_count == other.mesh.triangle_count


def test_undo_and_redo_over_ten_transactions() -> None:
    """§40: undo and redo across ten transactions."""
    project = project_with("cube_clean.stl", unit="mm")
    history = History(project.document)
    for index in range(10):
        history.apply(
            _("Umbenennen"),
            [OperationDraft(op="rename_object", inputs=("obj_1",), params={"name": f"T{index}"})],
        )
    assert len(history.transactions) == 11

    for _index in range(11):
        assert history.undo() is not None
    assert history.operations == ()

    for _index in range(11):
        assert history.redo() is not None
    assert len(history.operations) == 11


@pytest.mark.parametrize(
    ("name", "unit", "size"),
    [
        ("cube_clean.stl", "mm", (20.0, 20.0, 20.0)),
        ("bracket_inch.stl", "in", (101.6, 50.8, 6.35)),
        ("plate_cm.stl", "cm", (80.0, 50.0, 5.0)),
    ],
)
def test_import_in_mm_inch_and_cm(
    profile: Profile, name: str, unit: str, size: tuple[float, float, float]
) -> None:
    """§40: import in mm, inch and cm, with the unit question where needed."""
    asked: list[str] = []

    def ask(question: str, choices: list[str]) -> str:
        asked.append(question)
        return unit

    project = project_with(name)
    result = evaluate(project.document, profile, sources=ProjectSources(project), ask=ask)

    assert result.complete
    assert result.scene.objects["obj_1"].mesh.bounds.size == pytest.approx(size)
    if name == "cube_clean.stl":
        assert not asked, "a certain unit is not asked about"
    else:
        assert asked, "an ambiguous unit is asked about instead of guessed"


def test_a_parameter_change_recomputes_only_its_branch(profile: Profile) -> None:
    """§40: a parameter change recomputes only the affected branch."""
    project = project_with("cube_clean.stl", unit="mm")
    document = project.document
    document.parameters["name_suffix"] = Parameter(name="name_suffix", value=1.0)
    history = History(document)
    history.apply(
        _("Umbenennen"),
        [OperationDraft(op="rename_object", inputs=("obj_1",), params={"name": "Deckel"})],
    )
    cache = ResultCache()
    sources = ProjectSources(project)

    evaluate(document, profile, sources=sources, cache=cache)
    before = cache.statistics.misses

    document.parameters["name_suffix"] = Parameter(name="name_suffix", value=2.0)
    evaluate(document, profile, sources=sources, cache=cache)

    assert cache.statistics.misses == before, "nothing depends on that parameter, nothing reruns"
    assert cache.statistics.hits >= 2


def test_the_expression_evaluator_refuses_everything_outside_the_grammar() -> None:
    """§40: the expression evaluator rejects anything outside the grammar."""
    for text in ("=__import__('os')", "=open('x')", "=@a ** 2", "=eval('1')", "=1;2"):
        with pytest.raises(ValidationError):
            check_expression(text)


def test_the_start_screen_has_a_drop_area(qt_app: object) -> None:
    """§40: start screen with a drop area."""
    from app.ui.start_screen import DropArea, StartScreen

    screen = StartScreen()
    assert screen.findChildren(DropArea), "the start screen is not empty"
    assert screen.acceptDrops()


def test_the_printer_starting_set_is_present_and_selectable() -> None:
    """§40: starting set of printer profiles present and selectable."""
    printers = profiles.printer_profiles()
    assert len(printers) >= 10
    chosen = profiles.make_profile("bambu-a1-mini", "pla")
    assert chosen.printer.build_volume == (180.0, 180.0, 180.0)


def test_the_licence_check_is_green() -> None:
    """§40: licence check green."""
    assert licences.check() == []
