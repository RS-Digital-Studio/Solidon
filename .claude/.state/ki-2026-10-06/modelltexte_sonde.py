"""RM-285: Alle Modelltexte eines Baums auf Deutsch in eine Datei schreiben.

    python modelltexte_sonde.py <baum> <ausgabe.json>

Zwei Bäume, eine Sonde: Ist die Ausgabe gleich, sieht das Modell auf Deutsch
Zeichen für Zeichen dasselbe. Nutzerverzeichnisse gehen in einen Temp-Ordner.
"""

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2])
_scratch = Path(tempfile.mkdtemp(prefix="rm285-"))
os.environ["APPDATA"] = str(_scratch / "roaming")
os.environ["LOCALAPPDATA"] = str(_scratch / "local")
sys.path.insert(0, str(ROOT))

from app.core.activation import store as activation_store  # noqa: E402

activation_store.DEMO_UNTIL = None
activation_store.TRIAL_FROM = activation_store.DEMO_FROM

import app  # noqa: E402

assert Path(app.__file__).resolve().is_relative_to(ROOT), app.__file__

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()

from app.core import examples  # noqa: E402
from app.core.agent import context, tools  # noqa: E402
from app.core.agent.offer import ToolOffer  # noqa: E402
from app.core.agent.session import AgentSession  # noqa: E402
from app.core.backends.llm import Reply, ToolCall  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.perceive.digest import digest  # noqa: E402
from app.core.registry import REGISTRY  # noqa: E402
from app.core.scene import evaluate  # noqa: E402
from app.core.scene.project import ProjectSources, load, new_project  # noqa: E402
from tests.agent_cases import ALL_CASES  # noqa: E402
from tests.scripted_backend import ScriptedBackend  # noqa: E402
from tools.run_agent_suite import project_with_plate  # noqa: E402

profile = profiles.make_profile("centauri-carbon-2", "petg")
texts: dict[str, str] = {}
texts["tools_full"] = json.dumps(tools.tool_schemas(), ensure_ascii=False, sort_keys=True)
texts["tools_compact"] = json.dumps(tools.tool_schemas(compact=True), ensure_ascii=False, sort_keys=True)

for case in ALL_CASES:
    project = new_project("centauri-carbon-2", "petg") if case.empty_scene else project_with_plate()
    scene = evaluate(project.document, profile, sources=ProjectSources(project)).scene
    kind = case.selection[1].rsplit("_", 1)[0] if case.selection and case.selection[1] else None
    offer = ToolOffer.for_turn(REGISTRY, [case.request], selected_kind=kind, empty_scene=case.empty_scene)
    texts[f"offer:{case.id}"] = json.dumps(offer.schemas(), ensure_ascii=False, sort_keys=True)
    for compact in (False, True):
        messages = context.build_messages(
            case.request, project.document, scene, selection=case.selection, compact=compact
        )
        texts[f"context:{case.id}:{compact}"] = "\n----\n".join(m.content for m in messages)

for example in examples.all_examples() if hasattr(examples, "all_examples") else []:
    pass
for path in sorted(examples.directory().glob("*.p3d")):
    project = load(path)
    document = project.document
    result = evaluate(
        document,
        profiles.make_profile(document.printer or "centauri-carbon-2", document.material or "petg"),
        sources=ProjectSources(project),
    )
    texts[f"digest:{path.stem}"] = digest(result.scene, document)
    texts[f"digest:{path.stem}:condensed"] = digest(result.scene, document, condensed=True)

# Werkzeugantworten der Fehler- und Erfolgswege
calls = [
    ToolCall(id="1", name="gibt_es_nicht", arguments={}),
    ToolCall(id="2", name="translate_object", arguments={"objects": ["obj_9"], "x": 1}),
    ToolCall(id="3", name="translate_object", arguments={"objects": ["obj_1"], "x": "abc"}),
    ToolCall(id="4", name="undo_transaction", arguments={"transaction": "t99"}),
    ToolCall(id="5", name="set_parameter", arguments={"name": "fehlt", "value": 3}),
    ToolCall(id="6", name="add_parameter", arguments={"name": "breite", "value": 40}),
    ToolCall(id="7", name="read_analysis", arguments={"kind": "unbekannt"}),
    ToolCall(id="8", name="read_standard", arguments={"kind": "unbekannt", "size": "M3"}),
    ToolCall(id="9", name="read_standard", arguments={"kind": "metric_screw", "size": "M99"}),
    ToolCall(id="10", name="set_print_target", arguments={"printer": "centauri-carbon-2", "material": "pla"}),
    ToolCall(id="11", name="add_fit", arguments={"name": "f", "a": "obj_1:hole_1", "b": "obj_1:hole_2", "kind": "unbekannt"}),
    ToolCall(id="12", name="add_fit", arguments={"name": "f", "a": "obj_1:hole_1", "b": "obj_1:hole_2", "kind": "clearance"}),
    ToolCall(id="13", name="translate_object", arguments={"objects": ["obj_1"], "x": 5}),
    ToolCall(id="14", name="ask_user", arguments={"question": "Welche?", "options": ["a", "b"]}),
]
project = project_with_plate()
backend = ScriptedBackend(answers=[Reply(tool_calls=(call,)) for call in calls] + [Reply(text="Fertig.")])
agent = AgentSession(
    backend=backend,
    document=project.document,
    profile=profile,
    sources=ProjectSources(project),
    ask=lambda question, options: options[0] if options else "a",
    max_steps=40,
)
proposal = agent.propose("Sonde")
answers = [m.content for m in backend.seen[-1] if m.role == "tool"]
for index, answer in enumerate(answers):
    texts[f"answer:{index}"] = answer
texts["proposal_title"] = str(proposal.summary())
OUT.write_text(json.dumps(texts, ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
print(len(texts), "Texte,", len(answers), "Werkzeugantworten")
