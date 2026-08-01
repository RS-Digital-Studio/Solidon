"""Die Agenten-Suite gegen ein echtes Modell laufen lassen (Bauplan §35,
§40).

Die Suite in ``tests/`` prüft, was die Mechanik garantiert. Dieser Läufer prüft
die andere Hälfte, die ein Modell braucht: wie oft bekommt eine mehrdeutige
Anfrage eine Frage statt einer Vermutung, wie oft werden Hauptmaße zu
Parametern, wie oft ist eine Operation ungültig.

Braucht einen Schlüssel oder ein lokales Modell — ohne eines sagt er das und
hält an. Er ist nicht Teil der Testsuite: er kostet Geld, und sein Ergebnis ist
eine Quote, kein Bestanden.

    python tools/run_agent_suite.py
    python tools/run_agent_suite.py --backend ollama --model qwen2.5-coder:14b
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.agent.session import AgentSession
from app.core.backends.llm import (
    AnthropicBackend,
    LLMBackend,
    OllamaBackend,
    first_available,
)
from app.core.knowledge import profiles
from app.core.scene import History, OperationDraft
from app.core.scene.project import Project, ProjectSources, new_project
from app.core.types import Source
from tests.agent_cases import ALL_CASES, Case

MESHES = Path(__file__).resolve().parent.parent / "tests" / "data" / "meshes"

#: What §40 expects of a run against a real model.
TARGET_ASKED = 1.0
"""Jede mehrdeutige Anfrage muss fragen. Das hier ist keine Quote, das ist eine Regel."""
TARGET_VALID = 0.95
"""Share of operations that were schema-valid on the first attempt."""


@dataclass(slots=True)
class Outcome:
    case: Case
    asked: bool = False
    operations: tuple[str, ...] = ()
    parameters: int = 0
    invalid: int = 0
    steps: int = 0
    error: str = ""

    @property
    def good(self) -> bool:
        if self.error:
            return False
        if self.case.ambiguous:
            return self.asked
        if self.case.expects_parameter:
            return self.parameters > 0
        if self.case.expects_answer_only:
            return not self.operations
        return bool(set(self.case.expects_ops) & set(self.operations))


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


def run_case(case: Case, backend: LLMBackend) -> Outcome:
    # Pillar A starts on an empty project, pillar C on the plate (§2.2).
    project = new_project("centauri-carbon-2", "petg") if case.empty_scene else project_with_plate()
    outcome = Outcome(case=case)

    def answer(question: str, options: list[str]) -> str:
        outcome.asked = True
        return options[0] if options else "hole_1"

    agent = AgentSession(
        backend=backend,
        document=project.document,
        profile=profiles.make_profile("centauri-carbon-2", "petg"),
        sources=ProjectSources(project),
        ask=answer,
        selection=case.selection,
    )
    try:
        proposal = agent.propose(case.request)
    except Exception as problem:  # ein Lauf gegen ein Netz scheitert auf viele Arten
        outcome.error = str(problem)[:120]
        return outcome

    outcome.operations = tuple(draft.op for draft in proposal.drafts)
    outcome.parameters = len(proposal.parameters)
    outcome.steps = proposal.steps
    outcome.asked = outcome.asked or bool(proposal.questions)
    return outcome


def pick(name: str, model: str) -> LLMBackend | None:
    if name == "anthropic":
        return AnthropicBackend(model=model) if model else AnthropicBackend()
    if name == "ollama":
        return OllamaBackend(model=model) if model else OllamaBackend()
    return first_available()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", default="", choices=["", "anthropic", "ollama"])
    parser.add_argument("--model", default="")
    parser.add_argument("--only", default="", help="Nur einen Fall laufen lassen")
    parser.add_argument(
        "--pillar", default="", choices=["", "A", "C"], help="Nur eine Säule laufen lassen"
    )
    arguments = parser.parse_args()

    backend = pick(arguments.backend, arguments.model)
    if backend is None or not backend.available:
        print("Kein Sprachmodell erreichbar. Schlüssel hinterlegen oder Ollama starten.")
        return 2

    cases = [
        case
        for case in ALL_CASES
        if (not arguments.only or case.id == arguments.only)
        and (not arguments.pillar or case.pillar == arguments.pillar)
    ]
    print(f"{backend.id}:{backend.model} — {len(cases)} Anfragen\n")

    outcomes = []
    for case in cases:
        outcome = run_case(case, backend)
        outcomes.append(outcome)
        marker = "ok " if outcome.good else "-- "
        detail = outcome.error or ", ".join(outcome.operations) or "keine Operation"
        print(f"{marker}{case.id:20} {detail}" + ("  [gefragt]" if outcome.asked else ""))

    ambiguous = [entry for entry in outcomes if entry.case.ambiguous]
    asked = sum(1 for entry in ambiguous if entry.asked)
    good = sum(1 for entry in outcomes if entry.good)

    print("\n--- Quote ---")
    print(f"gut beantwortet: {good}/{len(outcomes)}")
    if ambiguous:
        print(f"bei Mehrdeutigkeit gefragt: {asked}/{len(ambiguous)} (Ziel {TARGET_ASKED:.0%})")

    # §35 für Säule A: wurde ein Baustein statt eigener Geometrie benutzt, und
    # wurden die Hauptmaße zu Parametern?
    building = [entry for entry in outcomes if entry.case.expects_part]
    if building:
        used_parts = sum(
            1 for entry in building if any(name.startswith("insert_") for name in entry.operations)
        )
        print(f"Baustein statt eigener Geometrie: {used_parts}/{len(building)}")
    wanted_parameters = [entry for entry in outcomes if entry.case.expects_parameter]
    if wanted_parameters:
        made = sum(1 for entry in wanted_parameters if entry.parameters)
        print(f"Hauptmaße als Parameter: {made}/{len(wanted_parameters)}")

    print(f"Schritte im Mittel: {sum(e.steps for e in outcomes) / max(len(outcomes), 1):.1f}")
    return 0 if good == len(outcomes) else 1


if __name__ == "__main__":
    raise SystemExit(main())
