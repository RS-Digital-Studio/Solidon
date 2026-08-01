"""Die Agenten-Suite für Säule C (Bauplan §35, §40 für P4).

Zwei Hälften, und es zählt, klar zu sein, welche welche ist.

**Ohne Modell** — was hier läuft — prüft die Suite, was die *Mechanik*
garantiert, und nur das: dass jede Anfrage das Modell mit dem Kontext erreicht,
den sie braucht, dass jede Operation, die ein Fall erwartet, existiert und als
Werkzeug angeboten wird, dass eine gute Antwort genau eine Transaktion wird,
dass ein mehrdeutiger Fall, der fragt, mit seiner Frage die Oberfläche
erreicht, und dass eine Operation schemageprüft ist, bevor gerechnet wird. Ein
geskriptetes Backend spielt die gute Antwort; das sagt nichts über ein echtes
Modell, und die Suite behauptet das auch nicht.

**Mit Modell** — ``tools/run_agent_suite.py`` — gehen dieselben Fälle an das
konfigurierte Backend, und heraus kommt die Quote, die §40 verlangt: wie oft
wurde gefragt, wo die Anfrage mehrdeutig war, wie oft wurden Hauptmaße zu
Parametern, wie oft war eine Operation ungültig. Dieser Lauf braucht einen
Schlüssel und ist nicht Teil der Testsuite.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.core.agent import apply as agent_apply
from app.core.agent import tools
from app.core.agent.session import AgentSession
from app.core.backends.llm import Reply, ToolCall
from app.core.backends.scripted import ScriptedBackend
from app.core.registry import REGISTRY
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import Project, ProjectSources, new_project
from app.core.types import Profile, Source
from tests.agent_cases import AMBIGUOUS, CASES, Case

MESHES = Path(__file__).parent / "data" / "meshes"


@pytest.fixture
def project() -> Project:
    made = new_project("centauri-carbon-2", "petg")
    made.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/plate_holes.stl", sha256=""
    )
    made.sources["src_1"] = (MESHES / "plate_holes.stl").read_bytes()
    History(made.document).apply(
        "Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
    )
    return made


def good_answer(case: Case) -> list[Reply]:
    """Was ein Modell, das den Regeln folgt, mit diesem Fall täte."""
    if case.ambiguous:
        return [
            Reply(
                tool_calls=(
                    ToolCall(
                        id="1",
                        name=tools.ASK_USER,
                        arguments={"question": case.request, "options": ["hole_1", "hole_2"]},
                    ),
                )
            ),
            Reply(text="Ich nehme hole_1."),
        ]
    if case.expects_parameter:
        return [
            Reply(
                tool_calls=(
                    ToolCall(
                        id="1",
                        name=tools.ADD_PARAMETER,
                        arguments={"name": "breite", "value": 80.0, "unit": "mm"},
                    ),
                )
            ),
            Reply(text="Breite ist jetzt ein Parameter."),
        ]
    if case.expects_answer_only:
        return [Reply(text="Die Platte ist 8 mm dick.")]
    return [
        Reply(
            tool_calls=tuple(_call(index, name) for index, name in enumerate(case.expects_ops, 1))
        ),
        Reply(text="Erledigt."),
    ]


def _call(index: int, name: str) -> ToolCall:
    arguments: dict[str, object] = {"objects": ["obj_1"]}
    if name == "translate_object":
        arguments["dx"] = 10.0
    elif name == "rotate_object":
        arguments.update({"axis": "z", "angle": 90.0})
    elif name == "scale_object":
        arguments["factor"] = 1.2
    elif name == "split_plane":
        arguments.update({"axis": "z", "position": 0.0})
    elif name == "drill_hole":
        arguments.update({"diameter": 5.0, "x": 0.0, "y": 0.0, "z": 4.0, "axis": "z"})
    elif name == "orient_for_print":
        # Die Suche über hunderte Kandidaten wird in der Leistungs-Suite gemessen;
        # hier machte sie jeden Lauf nur langsamer, ohne mehr zu prüfen.
        arguments["thorough"] = False
    return ToolCall(id=str(index), name=name, arguments=arguments)


def run(case: Case, project: Project, profile: Profile) -> tuple[AgentSession, object]:
    asked: list[str] = []

    def answer(question: str, options: list[str]) -> str:
        asked.append(question)
        return options[0] if options else "hole_1"

    agent = AgentSession(
        backend=ScriptedBackend(answers=good_answer(case)),
        document=project.document,
        profile=profile,
        sources=ProjectSources(project),
        ask=answer,
        selection=case.selection,
    )
    proposal = agent.propose(case.request)
    return agent, proposal


# --- Der Korpus der Anfragen ------------------------------------------------------


def test_the_suite_has_the_size_the_plan_asks_for() -> None:
    """§35: 33 Referenzanfragen — 15 zu Säule C, 18 zu Säule A seit den
    Skizzenfällen aus P13. §40 zu P4: drei davon mehrdeutig."""
    from tests.agent_cases import ALL_CASES, CASES_A

    assert len(CASES) == 15
    assert len(CASES_A) == 18
    assert len(ALL_CASES) == 33, "§35 nennt 33 Referenzanfragen"
    assert len(AMBIGUOUS) == 3
    assert len({case.id for case in ALL_CASES}) == 33


def test_every_expected_operation_exists() -> None:
    """Ein Fall, der eine Operation erwartet, die niemand deklariert hat,
    ginge aus Versehen durch.
    """
    known = {spec.name for spec in REGISTRY.all()}

    for case in CASES:
        for name in case.expects_ops:
            assert name in known, f"{case.id} expects {name}"


def test_every_expected_operation_is_offered_as_a_tool() -> None:
    offered = set(tools.names())

    for case in CASES:
        for name in case.expects_ops:
            assert name in offered, f"{case.id}: {name} is not a tool"


# --- Was die Mechanik garantiert --------------------------------------------------


@pytest.mark.parametrize("case", CASES, ids=[case.id for case in CASES])
def test_every_request_reaches_the_model_with_its_context(
    case: Case, project: Project, profile: Profile
) -> None:
    """§26.1: Steckbrief, Prüfbericht, Regeln — und die Auswahl, wo es eine
    gibt.
    """
    agent, _proposal = run(case, project, profile)
    backend = agent.backend
    assert isinstance(backend, ScriptedBackend)

    first = backend.seen[0]
    system = " ".join(entry.content for entry in first if entry.role == "system")
    world = first[1].content

    assert "Formwerk" in system
    assert "Mindestwandstärke" in system, "the rule set travels along (§39)"
    assert "obj_1" in world
    assert first[-1].content == case.request
    if case.selection is not None:
        assert case.selection[1] in world


@pytest.mark.parametrize("case", CASES, ids=[case.id for case in CASES])
def test_a_good_answer_becomes_one_transaction(
    case: Case, project: Project, profile: Profile
) -> None:
    """AGENTS.md Regel 16: ein Vorschlag, eine Transaktion, ein Undo."""
    _agent, proposal = run(case, project, profile)
    history = History(project.document)
    before = len(project.document.transactions)

    transaction = agent_apply.accept(proposal, history)  # type: ignore[arg-type]

    if proposal.drafts:  # type: ignore[attr-defined]
        assert transaction is not None
        assert len(project.document.transactions) == before + 1
        agent_apply.undo(proposal, history, transaction.id)  # type: ignore[arg-type]
        assert len(project.document.transactions) == before
    else:
        assert transaction is None


@pytest.mark.parametrize("case", AMBIGUOUS, ids=[case.id for case in AMBIGUOUS])
def test_an_ambiguous_request_can_ask_and_the_question_arrives(
    case: Case, project: Project, profile: Profile
) -> None:
    """§26.2: die Frage muss die Oberfläche erreichen, nicht im Modell
    bleiben.
    """
    _agent, proposal = run(case, project, profile)

    assert proposal.asked, f"{case.id} is ambiguous and the harness has to carry the question"
    assert proposal.questions[0].answer, "the answer travels back"  # type: ignore[attr-defined]


@pytest.mark.parametrize(
    "case", [entry for entry in CASES if entry.expects_ops], ids=lambda case: case.id
)
def test_the_expected_operations_end_up_in_the_proposal(
    case: Case, project: Project, profile: Profile
) -> None:
    _agent, proposal = run(case, project, profile)

    assert [draft.op for draft in proposal.drafts] == list(case.expects_ops)  # type: ignore[attr-defined]


def test_a_parameter_case_produces_a_parameter(project: Project, profile: Profile) -> None:
    """§39: Hauptmaße werden Parameter, und die Suite misst es."""
    case = next(entry for entry in CASES if entry.expects_parameter)
    _agent, proposal = run(case, project, profile)

    assert proposal.parameters  # type: ignore[attr-defined]


def test_a_question_about_the_model_changes_nothing(project: Project, profile: Profile) -> None:
    case = next(entry for entry in CASES if entry.expects_answer_only)
    _agent, proposal = run(case, project, profile)

    assert proposal.empty  # type: ignore[attr-defined]
    assert proposal.answer  # type: ignore[attr-defined]


def test_an_invalid_operation_never_reaches_the_geometry(
    project: Project, profile: Profile
) -> None:
    """§40 für P4: schemagültig, bevor irgendetwas gerechnet wird."""
    agent = AgentSession(
        backend=ScriptedBackend(
            answers=[
                Reply(
                    tool_calls=(
                        ToolCall(
                            id="1",
                            name="rotate_object",
                            arguments={"objects": ["obj_1"], "axis": "q", "angle": 90.0},
                        ),
                    )
                ),
                Reply(text="Ich korrigiere."),
            ]
        ),
        document=project.document,
        profile=profile,
        sources=ProjectSources(project),
    )

    proposal = agent.propose("Dreh um die Q-Achse")

    assert proposal.drafts == []
    assert len(project.document.ops) == 1, "only the load operation, nothing added"


# --- Säule A (§40 für P6) ---------------------------------------------------------


def test_pillar_a_prefers_parts_over_own_geometry() -> None:
    """§35, §40 zu P6: wird ein Baustein benutzt statt eigener Geometrie?

    Gemessen über den Korpus, nicht über eine Antwort: dreizehn der achtzehn
    Anfragen zu Säule A beantwortet ein Baustein aus der Bibliothek. Die fünf
    ohne sind die, für die es keinen gibt: eine reine Parameterfrage und vier
    Formen, die seit P13 die Skizzen-Ops bauen (§30.1)."""
    from tests.agent_cases import CASES_A

    with_part = [case for case in CASES_A if case.expects_part]
    without = [case for case in CASES_A if not case.expects_part]

    assert len(with_part) == 13
    assert {case.id for case in without} == {
        "parameterise",
        "free_shape",
        "hex_base",
        "pocket_plate",
        "handrail_bend",
    }
    for case in with_part:
        assert any(name.startswith("insert_") for name in case.expects_ops), case.id


def test_pillar_a_turns_main_dimensions_into_parameters() -> None:
    """§39, §35: Hauptmaße werden Parameter, und es ist messbar."""
    from tests.agent_cases import CASES_A

    assert [case.id for case in CASES_A if case.expects_parameter] == [
        "bracket",
        "parameterise",
    ]


def test_every_operation_pillar_a_expects_exists() -> None:
    from tests.agent_cases import CASES_A

    known = {spec.name for spec in REGISTRY.all()}
    for case in CASES_A:
        for name in case.expects_ops:
            assert name in known, f"{case.id} expects {name}"


def test_the_free_shape_no_longer_needs_the_fallback() -> None:
    """Der Trichter war der Vorzeigefall des OpenSCAD-Rückfalls (§24.1).

    Seit P13 spannt ``sketch_loft`` ihn im Haus auf (§30.1) — die gute Antwort
    benutzt die eigene Operation, und der Rückfall wäre jetzt die falsche
    Wahl. Genau diese Umkehr hält der Fall fest."""
    from tests.agent_cases import by_id

    case = by_id("free_shape")

    assert case.expects_ops == ("sketch_loft",)
    assert case.forbids_ops == ("create_from_scad",)
    assert not case.expects_part


def test_the_scene_stays_evaluable_after_every_case(project: Project, profile: Profile) -> None:
    """Ein Vorschlag, der sich nicht rechnen lässt, ist schlechter als keiner —
    also lassen sich alle rechnen.
    """
    for case in CASES:
        made = new_project("centauri-carbon-2", "petg")
        made.document.sources["src_1"] = project.document.sources["src_1"]
        made.sources["src_1"] = project.sources["src_1"]
        History(made.document).apply(
            "Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
        )
        _agent, proposal = run(case, made, profile)
        agent_apply.accept(proposal, History(made.document))  # type: ignore[arg-type]

        result = evaluate(made.document, profile, sources=ProjectSources(made))
        assert result.complete, f"{case.id} left the stack in a state that stops"
