"""Way 2 from §2.2, end to end (Bauplan §40 for P6).

    New project → describe what is needed → the agent creates parameters and
    places parts → the parameter bar shows the main dimensions → turn a number,
    the model follows immediately → export.

What is checked here is that this way holds together: every step is an
operation, the main dimensions really are parameters, the parts really come out
of the library, and turning a number really rebuilds the model. The model is
scripted (``ScriptedBackend``) — how well a real one plays this is measured by
``tools/run_agent_suite.py``, not by the suite.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import pytest

from app.core.agent import apply as agent_apply
from app.core.agent.session import AgentSession
from app.core.backends.llm import Reply, ToolCall
from app.core.backends.scripted import ScriptedBackend
from app.core.export.writer import plan_export, write_plan
from app.core.knowledge.parts import PARTS
from app.core.scene import History, evaluate
from app.core.scene.project import Project, ProjectSources, new_project
from app.core.types import Profile


@pytest.fixture
def project() -> Project:
    """A new project — way 2 starts on an empty scene."""
    return new_project("centauri-carbon-2", "petg")


def call(index: int, tool: str, **arguments: object) -> ToolCall:
    return ToolCall(id=str(index), name=tool, arguments=arguments)


#: What a model that follows the rule set does with "a bracket with two M4 holes":
#: parameters first, then a primitive, then parts from the library (§39).
BRACKET = [
    Reply(
        text="Ich lege die Hauptmaße als Parameter an.",
        tool_calls=(
            call(1, "add_parameter", name="breite", value=60.0, unit="mm"),
            call(2, "add_parameter", name="tiefe", value=40.0, unit="mm"),
            call(3, "add_parameter", name="staerke", value=6.0, unit="mm"),
        ),
    ),
    Reply(
        text="Grundkörper und zwei Schraubenlöcher.",
        tool_calls=(call(4, "create_box", width=60.0, depth=40.0, height=6.0, name="Halter"),),
    ),
    Reply(
        tool_calls=(
            call(
                5,
                "insert_screw_hole",
                objects=["obj_1"],
                size="M4",
                depth=6.0,
                x=-20.0,
                y=0.0,
                z=6.0,
            ),
            call(
                6,
                "insert_screw_hole",
                objects=["obj_1"],
                size="M4",
                depth=6.0,
                x=20.0,
                y=0.0,
                z=6.0,
            ),
        ),
    ),
    Reply(text="Fertig: ein Halter 60 × 40 × 6 mm mit zwei M4-Löchern."),
]


def agent(project: Project, profile: Profile, answers: list[Reply]) -> AgentSession:
    return AgentSession(
        backend=ScriptedBackend(answers=list(answers)),
        document=project.document,
        profile=profile,
        sources=ProjectSources(project),
    )


def test_way_two_runs_from_a_sentence_to_a_file(
    project: Project, profile: Profile, tmp_path: Path
) -> None:
    """The whole way, in one test, with one assertion per promise of §2.2."""
    session = agent(project, profile, BRACKET)

    # 1. describe what is needed
    proposal = session.propose("Bau mir einen Halter 60 x 40 x 6 mm mit zwei M4-Löchern.")

    # 2. the agent works with parameters and parts, not with loose numbers
    assert set(proposal.parameters) == {"breite", "tiefe", "staerke"}
    assert [draft.op for draft in proposal.drafts] == [
        "create_box",
        "insert_screw_hole",
        "insert_screw_hole",
    ]

    # 3. one proposal is one transaction
    history = History(project.document)
    transaction = agent_apply.accept(proposal, history)
    assert transaction is not None
    assert len(project.document.transactions) == 1

    # 4. the parameter bar shows the main dimensions
    assert project.document.parameters["breite"].value == 60.0

    sources = ProjectSources(project)
    result = evaluate(project.document, profile, sources=sources)
    assert result.complete, [f.message for f in result.scene.report.findings]

    body = result.scene.objects["obj_1"]
    assert body.mesh.is_watertight
    assert body.mesh.bounds.size[0] == pytest.approx(60.0, abs=0.1)
    assert "screw_hole_bore_1" in body.features, "the bores come named out of the library"

    # 5. turning a number rebuilds the model
    parameters = project.document.parameters
    parameters["breite"] = dataclasses.replace(parameters["breite"], value=80.0)
    _bind_width(project)
    wider = evaluate(project.document, profile, sources=sources)

    assert wider.complete
    assert wider.scene.objects["obj_1"].mesh.bounds.size[0] == pytest.approx(80.0, abs=0.1)

    # 6. export
    plan = plan_export(
        list(wider.scene.objects.values()),
        project_name="halter",
        profile=profile,
        export_format="3mf",
    )
    written = write_plan(plan, tmp_path / "export", "3mf")
    assert written and written[0].is_file()


def _bind_width(project: Project) -> None:
    """Tie the box to the parameter — §13: the model follows the number.

    A model that has just created a parameter should write ``=@breite`` into the
    operation itself. The scripted one does not, so the test does it: what is
    being checked here is that the binding works, not that a script remembered.
    """
    for index, operation in enumerate(project.document.ops):
        if operation.op == "create_box":
            project.document.ops[index] = dataclasses.replace(
                operation, params={**operation.params, "width": "=@breite"}
            )


def test_the_agent_prefers_a_part_over_own_geometry(project: Project, profile: Profile) -> None:
    """§39, §40 for P6: parts before primitives, and it is measurable."""
    session = agent(project, profile, BRACKET)
    proposal = session.propose("Halter mit zwei M4-Löchern")

    from_library = [draft.op for draft in proposal.drafts if draft.op.startswith("insert_")]
    own_geometry = [draft.op for draft in proposal.drafts if draft.op.startswith("create_")]

    assert len(from_library) == 2
    assert len(own_geometry) == 1, "one body to put them in, the rest from the library"


def test_the_library_is_searchable_before_building(project: Project, profile: Profile) -> None:
    """§26.2: find_part answers with the operation, not just with a name."""
    session = agent(
        project,
        profile,
        [
            Reply(tool_calls=(call(1, "find_part", description="Mutter einlegen"),)),
            Reply(text="Ich nehme die Mutternfalle."),
        ],
    )
    session.propose("Wie bekomme ich eine Mutter in das Teil?")

    backend = session.backend
    assert isinstance(backend, ScriptedBackend)
    answer = [entry for entry in backend.seen[-1] if entry.role == "tool"][-1].content
    assert "insert_nut_trap" in answer


def test_a_search_without_a_hit_says_so(project: Project, profile: Profile) -> None:
    session = agent(
        project,
        profile,
        [
            Reply(
                tool_calls=(call(1, "find_part", description="Zahnrad mit Evolventenverzahnung"),)
            ),
            Reply(text="Dafür baue ich selbst."),
        ],
    )
    session.propose("Brauche ein Zahnrad")

    backend = session.backend
    assert isinstance(backend, ScriptedBackend)
    answer = [entry for entry in backend.seen[-1] if entry.role == "tool"][-1].content
    assert "keinen Baustein" in answer


def test_a_part_can_be_placed_at_a_feature(project: Project, profile: Profile) -> None:
    """§25: put a part at a recognised feature — by name, not by coordinates."""
    session = agent(
        project,
        profile,
        [
            Reply(tool_calls=(call(1, "create_box", width=40.0, depth=40.0, height=8.0),)),
            Reply(
                tool_calls=(
                    call(
                        2,
                        "insert_magnet_pocket",
                        objects=["obj_1"],
                        size="8x3",
                        at_feature="face_top",
                    ),
                )
            ),
            Reply(text="Magnettasche sitzt in der Oberseite."),
        ],
    )
    proposal = session.propose("Setz eine Magnettasche in die Oberseite")

    history = History(project.document)
    agent_apply.accept(proposal, history)
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete, [f.message for f in result.scene.report.findings]
    pocket = result.scene.objects["obj_1"].features["magnet_pocket_pocket_1"]
    assert pocket.params["centre"][2] > 0.0, "it sits at the top face, not at the origin"


def test_a_part_at_a_feature_that_does_not_exist_stops(project: Project, profile: Profile) -> None:
    """§15.2: no guessing where a named feature is not there."""
    session = agent(
        project,
        profile,
        [
            Reply(tool_calls=(call(1, "create_box", width=20.0, depth=20.0, height=5.0),)),
            Reply(
                tool_calls=(
                    call(
                        2,
                        "insert_magnet_pocket",
                        objects=["obj_1"],
                        size="8x3",
                        at_feature="gibt_es_nicht",
                    ),
                )
            ),
            Reply(text="Das Merkmal gibt es nicht."),
        ],
    )
    proposal = session.propose("Setz die Tasche an gibt_es_nicht")

    assert [draft.op for draft in proposal.drafts] == ["create_box"]


def test_every_primitive_stands_on_the_bed(profile: Profile) -> None:
    """A body that starts below the plate is a body nobody asked for."""
    from app.core.registry import REGISTRY
    from app.core.scene import OperationDraft

    for name in ("create_box", "create_cylinder", "create_sphere"):
        made = new_project("centauri-carbon-2", "petg")
        History(made.document).apply(name, [OperationDraft(op=name, params={})])
        result = evaluate(made.document, profile, sources=ProjectSources(made))

        assert result.complete, name
        body = result.scene.objects["obj_1"]
        assert body.mesh.bounds.minimum[2] == pytest.approx(0.0, abs=1e-6), name
        assert body.mesh.is_watertight, name
        assert REGISTRY.get(name).consumes == 0


def test_a_part_of_the_library_is_used_by_name() -> None:
    """The search the agent uses is the search the catalogue uses (§24.3, §26.2)."""
    assert PARTS.search("Mutter")
    assert PARTS.search("Magnet")
    assert not PARTS.search("Evolventenverzahnung")
