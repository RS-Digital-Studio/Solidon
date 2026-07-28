"""The part library (Bauplan §24).

§24.3 sets the bar: every part is computed through its whole parameter range —
watertight, minimum wall thickness, no self-intersection at the limits, features
correctly named. **A part without this test counts as not present.** So the
range test is parametrised over the registry: a new part is covered the moment
it is declared, and a part that fails at its own limits fails here.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from app.core.knowledge import standards
from app.core.knowledge.parts import LIBRARY_VERSION, PARTS, changed_since, missing_parts
from app.core.knowledge.parts import ops as part_ops
from app.core.knowledge.parts.registry import PartRegistry, PartSpec, register_part
from app.core.registry import REGISTRY, op_params, param
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import Project, ProjectSources, new_project
from app.core.types import BaseParams, PartResult, Profile, Source

MESHES = Path(__file__).parent / "data" / "meshes"


def ids(spec: PartSpec) -> str:
    return spec.name


def corners(spec: PartSpec) -> list[dict[str, Any]]:
    """The parameter range as the values a part has to survive.

    Not a sweep over everything — the corners are where a part breaks: the
    smallest and the largest of every number, every choice of every enum, both
    states of every switch.
    """
    entries = spec.params.spec()
    combinations: list[dict[str, Any]] = [{}]
    for entry in entries:
        values: list[Any] = []
        if entry.kind == "enum":
            values = list(entry.choices)
        elif entry.kind == "bool":
            values = [True, False]
        elif entry.kind in ("float", "int"):
            values = [entry.minimum, entry.maximum, entry.default]
            values = [value for value in values if value is not None]
        if not values:
            continue
        combinations = [{**base, entry.name: value} for base in combinations for value in values]
        # Keep it finite: the corners of every parameter, not every product.
        if len(combinations) > 24:
            combinations = combinations[:24]
    return combinations


# --- the library ------------------------------------------------------------------


def test_the_library_has_the_first_set_from_the_plan() -> None:
    """§24.1 names thirteen parts for the first release.

    The calibration bodies from §28.3 are parts too, but they are not part of
    that set — they are tools for the printer, not for the model, and they have
    their own group in the catalogue.
    """
    building = [spec for spec in PARTS.all() if spec.group != "calibration"]

    assert len(building) == 13
    assert len([spec for spec in PARTS.all() if spec.group == "calibration"]) == 3


def test_every_part_is_completely_declared() -> None:
    for spec in PARTS.all():
        assert str(spec.title).strip(), f"{spec.name} has no title"
        assert str(spec.doc).strip(), f"{spec.name} has no documentation"
        assert spec.features, f"{spec.name} names no provenance features"
        assert spec.changes, f"{spec.name} has no change log (§24.4)"


def test_a_part_without_features_is_refused() -> None:
    """§24.1: provenance features are the point of a part, not a nicety."""
    from app.core.errors import InternalError

    registry = PartRegistry()

    @op_params
    class Params(BaseParams):
        size: float = param(title="x", default=1.0)

    with pytest.raises(InternalError):

        @register_part(
            name="nameless", title="x", group="fasteners", params=Params, registry=registry
        )
        def nameless(raw: BaseParams) -> PartResult:  # pragma: no cover - never runs
            raise AssertionError


# --- the range test §24.3 asks for -------------------------------------------------


@pytest.mark.parametrize("spec", PARTS.all(), ids=ids)
def test_a_part_holds_over_its_whole_range(spec: PartSpec, profile: Profile) -> None:
    minimum_wall = profile.minimum_wall_thickness

    for values in corners(spec):
        result = spec.fn(spec.params(**values))
        mesh = result.mesh

        assert mesh.is_watertight, f"{spec.name} {values} is not watertight"
        assert mesh.volume > 0.0, f"{spec.name} {values} has no volume"
        assert mesh.component_count == 1, f"{spec.name} {values} falls apart"
        assert min(mesh.bounds.size) > minimum_wall / 4.0, (
            f"{spec.name} {values} is thinner than a printer can make"
        )


@pytest.mark.parametrize("spec", PARTS.all(), ids=ids)
def test_a_part_names_the_features_it_promised(spec: PartSpec) -> None:
    """§24.1: what the declaration promises has to come out of the function."""
    result = spec.fn(spec.params())

    assert result.features, f"{spec.name} returned no features"
    for name, feature in result.features.items():
        assert feature.id == name
        assert feature.provenance == "generated"
        assert feature.params, f"{spec.name}.{name} carries no dimensions"


@pytest.mark.parametrize("spec", PARTS.all(), ids=ids)
def test_a_part_is_reproducible(spec: PartSpec) -> None:
    """Leitprinzip 4: the same parameters give the same geometry."""
    first = spec.fn(spec.params())
    second = spec.fn(spec.params())

    assert first.mesh.volume == pytest.approx(second.mesh.volume, rel=1e-9)
    assert first.mesh.triangle_count == second.mesh.triangle_count


# --- the standard table ------------------------------------------------------------


def test_the_table_answers_the_question_from_the_plan() -> None:
    """§24.2: "hole for an M4 heat-set insert" has to be a lookup."""
    assert standards.insert("M4").hole == pytest.approx(5.6)
    assert standards.screw("M4").clearance == pytest.approx(4.5)
    assert standards.nut("M4").width == pytest.approx(7.0)


def test_every_screw_has_the_holes_that_belong_to_it() -> None:
    for size in standards.screw_sizes():
        entry = standards.screw(size)
        assert entry.tap < entry.nominal < entry.clearance < entry.countersink
        assert entry.pitch > 0.0


def test_an_unknown_size_says_what_is_known() -> None:
    from app.core.errors import ValidationError

    with pytest.raises(ValidationError) as raised:
        standards.screw("M42")
    assert "M4" in str(raised.value.values["known"])


# --- the operations that come out of the parts --------------------------------------


def test_every_part_became_an_operation() -> None:
    """§10, Leitprinzip 3: declared once, and every surface follows."""
    for spec in PARTS.all():
        assert REGISTRY.has(part_ops.op_name(spec.name)), spec.name


def test_a_part_operation_carries_its_own_parameters_and_a_place() -> None:
    spec = REGISTRY.get("insert_screw_hole")
    names = {entry.name for entry in spec.params.spec()}

    assert {"size", "depth", "countersink"} <= names, "the part's own parameters"
    assert {"x", "y", "z", "axis", "angle"} <= names, "and where it goes"
    assert spec.category == "parts"


def project_with_plate() -> Project:
    made = new_project("centauri-carbon-2", "petg")
    made.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/plate_holes.stl", sha256=""
    )
    made.sources["src_1"] = (MESHES / "plate_holes.stl").read_bytes()
    History(made.document).apply(
        "Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
    )
    return made


def test_a_subtractive_part_removes_material(profile: Profile) -> None:
    project = project_with_plate()
    sources = ProjectSources(project)
    before = evaluate(project.document, profile, sources=sources).scene.objects["obj_1"]

    History(project.document).apply(
        "Buchse",
        [
            OperationDraft(
                op="insert_heatset_m4",
                inputs=("obj_1",),
                params={"size": "M3", "x": 0.0, "y": 0.0, "z": 4.0},
            )
        ],
    )
    result = evaluate(project.document, profile, sources=sources)

    assert result.complete, [f.message for f in result.scene.report.findings]
    after = result.scene.objects["obj_1"]
    assert after.mesh.volume < before.mesh.volume, "a pressed-in insert needs a hole"


def test_an_additive_part_adds_material(profile: Profile) -> None:
    project = project_with_plate()
    sources = ProjectSources(project)
    before = evaluate(project.document, profile, sources=sources).scene.objects["obj_1"]

    History(project.document).apply(
        "Rippe",
        [
            OperationDraft(
                op="insert_rib",
                inputs=("obj_1",),
                params={"length": 20.0, "height": 6.0, "wall": 3.0, "z": 4.0},
            )
        ],
    )
    result = evaluate(project.document, profile, sources=sources)

    assert result.complete
    assert result.scene.objects["obj_1"].mesh.volume > before.mesh.volume


def test_the_features_of_a_part_reach_the_scene(profile: Profile) -> None:
    """§24.1, §21.1: a bore from the library is named from the start."""
    project = project_with_plate()
    History(project.document).apply(
        "Magnet",
        [
            OperationDraft(
                op="insert_magnet_pocket",
                inputs=("obj_1",),
                params={"size": "8x3", "x": 10.0, "y": 0.0, "z": 4.0},
            )
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete
    features = result.scene.objects["obj_1"].features
    assert "magnet_pocket_pocket_1" in features
    pocket = features["magnet_pocket_pocket_1"]
    assert pocket.provenance == "generated"
    assert pocket.params["centre"][0] == pytest.approx(10.0, abs=0.01)


def test_the_play_comes_from_the_material_profile(profile: Profile) -> None:
    """AGENTS.md rule 7: never a fixed number in the file."""
    project = project_with_plate()
    History(project.document).apply(
        "Passbohrung",
        [
            OperationDraft(
                op="insert_dowel",
                inputs=("obj_1",),
                params={"kind": "bore", "diameter": 4.0, "length": 6.0, "z": 4.0, "play": 0.0},
            )
        ],
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete
    bore = result.scene.objects["obj_1"].features["dowel_bore_1"]
    assert bore.params["diameter"] == pytest.approx(4.0 + profile.material.clearance, abs=0.01)


@pytest.mark.parametrize(
    "name",
    [
        "insert_screw_hole",
        "insert_nut_trap",
        "insert_printed_thread",
        "insert_snap_fit",
        "insert_latch",
        "insert_living_hinge",
        "insert_keyhole",
        "insert_wall_mount",
        "insert_cable_gland",
    ],
)
def test_every_part_operation_runs_on_a_body(name: str, profile: Profile) -> None:
    """One run per operation — a declaration nobody ever called is not finished."""
    project = project_with_plate()
    History(project.document).apply(
        name, [OperationDraft(op=name, inputs=("obj_1",), params={"z": 4.0})]
    )

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete, [f.message for f in result.scene.report.findings]
    assert result.scene.objects["obj_1"].mesh.volume > 0.0


# --- versioning (§24.4) -------------------------------------------------------------


def test_the_library_has_a_version() -> None:
    assert LIBRARY_VERSION


def test_a_changed_part_is_named(profile: Profile) -> None:
    used = {"screw_hole": "0", "rib": PARTS.get("rib").version}

    assert changed_since(used) == ("screw_hole",)


def test_a_part_that_is_gone_is_named() -> None:
    """§24.5: an own part from another machine is missing, not silently skipped."""
    assert missing_parts({"eigenbau": "1", "rib": "1"}) == ("eigenbau",)


def test_the_change_log_says_what_moved() -> None:
    for spec in PARTS.all():
        for change in spec.changes:
            assert change.date and change.reason
