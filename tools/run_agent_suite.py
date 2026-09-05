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
    python tools/run_agent_suite.py --backend ollama --model qwen3:14b
"""

from __future__ import annotations

import argparse
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.agent.session import AgentSession
from app.core.backends.llm import (
    AnthropicBackend,
    LLMBackend,
    Message,
    OllamaBackend,
    first_available,
)
from app.core.bootstrap import load_operations
from app.core.knowledge import profiles
from app.core.scene import History, OperationDraft
from app.core.scene.project import Project, ProjectSources, new_project
from app.core.types import Source
from tests.agent_cases import ALL_CASES, Case

MESHES = Path(__file__).resolve().parent.parent / "tests" / "data" / "meshes"

#: Was §40 von einem Lauf gegen ein echtes Modell erwartet.
TARGET_ASKED = 1.0
"""Jede mehrdeutige Anfrage muss fragen. Das hier ist keine Quote, das ist eine Regel."""
TARGET_VALID = 0.95
"""Anteil der Operationen, die schon im ersten Versuch schemagültig waren."""


@dataclass(slots=True)
class Outcome:
    case: Case
    asked: bool = False
    operations: tuple[str, ...] = ()
    parameters: int = 0
    calls: int = 0
    invalid: int = 0
    steps: int = 0
    readings: tuple[str, ...] = ()
    target: bool = False
    answer: str = ""
    error: str = ""

    @property
    def good(self) -> bool:
        if self.error:
            return False
        # **Was ein Fall verbietet, verbietet er auch einem sonst guten Zug.**
        # ``forbids_ops`` stand seit je am Fall und wurde hier nie gelesen:
        # ``tests/test_agent_suite.py`` prüft, dass das Feld *dasteht*, und die
        # Auswertung sah es nicht an. Gesetzt ist es auf genau einem Fall, und
        # zwar auf ``create_from_scad`` — der Operation, die fremden Quelltext
        # ausführt (§32). Ein Modell, das das erwartete Werkzeug **und**
        # zusätzlich diese Operation rief, zählte als Treffer: Die Quote
        # schützte den Wächter nicht, für den es sie gibt.
        #
        # Als frühes Veto, noch vor der Mehrdeutigkeit: Fragen und *dann*
        # Verbotenes rufen ist kein Erfolg. Gefunden von 3d-druck-46 beim
        # Gegenlesen der Bewertung, bevor der erste Modelllauf sie benutzt hat.
        if self.case.forbids_ops and set(self.case.forbids_ops) & set(self.operations):
            return False
        if self.case.ambiguous:
            return self.asked
        if self.case.expects_target and not self.target:
            # Ein Veto wie die Nachbarn darunter, kein früher Erfolg: ein
            # Fall, der Druckziel UND Erwähnung erwartet, überspränge sonst
            # die zweite Prüfung stillschweigend.
            return False
        if self.case.expects_reading and not (set(self.case.expects_reading) & set(self.readings)):
            # Nachsehen statt raten: eine Antwort ohne den Blick in Analyse
            # oder Tabelle ist geraten, auch wenn die Zahl zufällig stimmt.
            return False
        if self.case.expects_mention and not all(
            word in self.answer for word in self.case.expects_mention
        ):
            return False
        # **Ein Veto, kein Freispruch.** Hier stand ``return self.parameters > 0``
        # — und das beendete die Prüfung. Der Fall ``bracket`` erwartet drei
        # Operationen *und* einen Parameter; geprüft wurde nur der Parameter,
        # die Operationen sah niemand an. Ausgerechnet der komplexeste Fall der
        # Suite hing damit an „irgendein Parameter ist entstanden".
        #
        # Dieselbe Bauart wie ``expects_target`` und ``expects_reading``
        # darüber, die als Veto geschrieben sind und weiterfallen lassen. Die
        # beiden reinen Parameterfälle (``parameter``, ``parameterise``) haben
        # ``expects_ops=()``; für sie ist die Op-Prüfung danach die leere
        # Teilmenge und damit erfüllt — sie verlieren nichts.
        if self.case.expects_parameter and self.parameters <= 0:
            return False
        if self.case.expects_answer_only:
            return not self.operations
        # **Alle erwarteten Arten, nicht irgendeine.** Hier stand eine
        # Schnittmenge, und die ist grün, sobald *ein* erwarteter Op dabei ist.
        # Auf den zehn mehrteiligen Fällen — durchweg „Grundkörper plus
        # Baustein", von ``bracket`` bis ``pocket_plate`` — hieß das: Wer den
        # Quader anlegt und die Schraubenlöcher vergisst, zählt als Treffer.
        #
        # Das ist die gefährlichere Hälfte derselben Lockerheit, die auch
        # Zusätzliches durchlässt: Eine Verschlechterung des Werkzeugsatzes
        # zeigt sich zuerst als **Teilarbeit** — der Grundkörper ist leicht zu
        # finden, der Baustein steht unter hundert anderen. Genau die maskierte
        # der Vergleich, mit dem gemessen werden soll, ob eine Kürzung schadet.
        #
        # Teilmenge und nicht Gleichheit: Der mechanische Test daneben
        # (``tests/test_agent_suite.py``) verlangt die exakte Liste, hier zählt,
        # dass keine erwartete Art fehlt — **und zwar so oft, wie sie erwartet
        # ist.** Als Menge verglichen galt der Halter mit zwei M4-Löchern schon
        # mit einem Schraubenloch als erfüllt (Gesamtreview 05.09.2026, R36).
        # Gefunden von 3d-druck-46 beim Gegenlesen, vor dem ersten Modelllauf.
        return Counter(self.case.expects_ops) <= Counter(self.operations)


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
    # Säule A beginnt auf einem leeren Projekt, Säule C auf der Platte (§2.2).
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
    outcome.calls = proposal.tool_calls
    outcome.invalid = proposal.invalid_calls
    outcome.steps = proposal.steps
    outcome.readings = tuple(proposal.readings)
    outcome.target = proposal.print_target is not None
    outcome.answer = proposal.answer
    outcome.asked = outcome.asked or bool(proposal.questions)
    return outcome


def pick(name: str, model: str) -> LLMBackend | None:
    if name == "anthropic":
        return AnthropicBackend(model=model) if model else AnthropicBackend()
    if name == "ollama":
        return OllamaBackend(model=model) if model else OllamaBackend()
    return first_available()


def why_unreachable(backend: LLMBackend) -> tuple[str, ...]:
    """Ein Probeaufruf, bevor neununddreißig Anfragen hinausgehen — oder ().

    **``available`` ist für diesen Läufer zu wenig.** Es fragt, ob ein Socket
    lauscht, und ``OllamaBackend.available`` sagt auch warum: Die Antwort wird
    gebraucht, während ein Fenster gebaut wird, und ein HTTP-Aufruf an einen
    geschlossenen Port kostet dort zu viel. Für ein Fenster ist das richtig.

    Hier nicht. Ein laufendes Ollama ohne geladenes Modell ließ diesen Läufer
    neununddreißig Mal gegen dieselbe Wand laufen — neununddreißig gleiche
    Zeilen und am Ende Exit 0. Der Docstring oben versprach das Gegenteil:
    „ohne eines sagt er das und hält an." Mit einem Schlüssel statt eines
    lokalen Modells wären es neununddreißig **bezahlte** Fehlversuche.

    Ein Aufruf kostet also einen von vierzig und spart im Fehlerfall alle.
    """
    try:
        backend.complete([Message(role="user", content="ping")], max_output_tokens=1)
    except Exception as problem:  # jede Art von Fehlschlag zählt hier gleich
        detail = str(problem)
        if "not found" in detail and backend.id == "ollama":
            return (
                f"Das Modell '{backend.model}' ist nicht installiert.",
                f"    ollama pull {backend.model}",
                "Oder ein anderes wählen: --model <name>.",
            )
        return (f"Das Sprachmodell antwortet nicht: {detail[:160]}",)
    return ()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", default="", choices=["", "anthropic", "ollama"])
    parser.add_argument("--model", default="")
    parser.add_argument("--only", default="", help="Nur einen Fall laufen lassen")
    parser.add_argument(
        "--pillar", default="", choices=["", "A", "C"], help="Nur eine Säule laufen lassen"
    )
    arguments = parser.parse_args()

    # Ohne das ist das Register leer, und der erste Fall stirbt an einem
    # `load`, das es angeblich nicht gibt. Die Anwendung und die Kommandozeile
    # tun das beim Start; dieser Läufer hat es nie getan und lief deshalb seit
    # der Umstellung auf explizites Laden überhaupt nicht mehr — er ist kein
    # Testlauf, also hat es niemandem etwas gesagt.
    load_operations()

    backend = pick(arguments.backend, arguments.model)
    if backend is None or not backend.available:
        print("Kein Sprachmodell erreichbar. Schlüssel hinterlegen oder Ollama starten.")
        return 2

    unreachable = why_unreachable(backend)
    if unreachable:
        for line in unreachable:
            print(line)
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
        notes = ("  [gefragt]" if outcome.asked else "") + (
            f"  [{outcome.invalid} ungültig]" if outcome.invalid else ""
        )
        print(f"{marker}{case.id:20} {detail}{notes}")

    ambiguous = [entry for entry in outcomes if entry.case.ambiguous]
    asked = sum(1 for entry in ambiguous if entry.asked)
    good = sum(1 for entry in outcomes if entry.good)

    print("\n--- Quote ---")
    print(f"gut beantwortet: {good}/{len(outcomes)}")
    if ambiguous:
        print(f"bei Mehrdeutigkeit gefragt: {asked}/{len(ambiguous)} (Ziel {TARGET_ASKED:.0%})")

    # §40: Anteil der Aufrufe, die schon im ersten Versuch schemagültig waren.
    calls = sum(entry.calls for entry in outcomes)
    invalid = sum(entry.invalid for entry in outcomes)
    if calls:
        ratio = (calls - invalid) / calls
        print(
            f"schemagültig im ersten Versuch: {calls - invalid}/{calls}"
            f" = {ratio:.0%} (Ziel {TARGET_VALID:.0%})"
        )

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
