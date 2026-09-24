"""Verschiebt stabile fachliche Blöcke ohne Änderungen ihrer Testfunktionen."""

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STATE = Path(__file__).resolve().parent
path = ROOT / "tests/test_ui.py"
source = path.read_text(encoding="utf-8")
nodes = ast.parse(source).body
lines = source.splitlines(keepends=True)
definitions = {node.name: node for node in nodes if isinstance(node, ast.FunctionDef)}


def interval(first: str, after: str) -> list[str]:
    return [
        node.name
        for node in nodes
        if isinstance(node, ast.FunctionDef)
        and definitions[first].lineno <= node.lineno < definitions[after].lineno
    ]


exports = interval("test_an_unreadable_gcode_file_says_so", "test_a_parameter_can_be_added") if False else interval(
    "test_an_unreadable_gcode_file_says_so", "test_export_is_disabled_on_an_empty_scene"
)
exports += ["test_export_is_disabled_on_an_empty_scene"]
exports += interval("_asked_dialog", "_top_level_names")
licensing = interval("_expired", "test_a_dropped_link_is_taken_like_a_dropped_file")
licensing += [
    "test_the_about_dialog_carries_the_licence_information",
    "test_the_about_dialog_localises_the_security_promise_and_links",
    "test_the_unlock_dialog_does_not_close_on_an_empty_field",
    "test_the_activation_dialog_reads_as_two_small_steps",
    "test_the_offline_activation_page_opens_in_the_ui_language",
    "test_a_paying_customer_is_not_told_the_trial_ran_out",
    "test_the_status_line_speaks_on_the_day_the_trial_ends",
    "test_the_status_line_explains_the_sale_version_without_inventing_a_trial",
    "test_the_key_field_shows_a_whole_key",
]
licensing.remove("_drag")
dialogs = interval("test_a_dialog_is_generated_from_the_parameter_schema", "test_a_thread_dialog_uses_the_selected_face_or_bore")
dialogs = [name for name in dialogs if name not in licensing]
remote = interval("test_a_remote_call_is_one_transaction_the_window_can_undo", "test_the_toolbar_has_a_drawing_entry_for_way_two")
remote += interval("test_scene_views_render_labelled_pngs", "test_dragging_a_face_reaches_the_document")
remote += ["test_a_remote_undo_takes_the_transaction_it_was_asked_for"]
helpers = ["session", "window", "wait_for_export", "export_anyway", "_expired"]
exports = [name for name in exports if name not in helpers]
licensing = [name for name in licensing if name not in helpers]
groups = {"dialogs": dialogs, "export": exports, "licensing": licensing, "remote": remote}
header = "".join(lines[9:60])
helper_imports = """
from tests.ui_helpers import MESHES, expire_trial as _expired, export_anyway, wait_for_export
from tests.ui_helpers import session as session, window as window
"""


def function_source(name: str) -> str:
    node = definitions[name]
    start = min([node.lineno, *(entry.lineno for entry in node.decorator_list)]) - 1
    return "".join(lines[start:node.end_lineno]).rstrip() + "\n"


descriptions = {
    "dialogs": "Aus dem Operationsschema erzeugte Dialoge: Werte, Auswahl und gestufte Tiefe (§2.5).",
    "export": "Export, G-Code-Prüfung und Slicerübergabe am echten Fenster (§29, §22).",
    "licensing": "Lizenzierung, Aktivierung und lesbare Lizenzhinweise in der Oberfläche (§36).",
    "remote": "Fernsteuerung: Herkunft, Antwort, Zeitgrenzen und Transaktionen am Fenster (§26.4).",
}
pending = {}
for group, names in groups.items():
    target = ROOT / f"tests/test_ui_{group}.py"
    assert not target.exists(), target
    pending[target] = (
        f'"""{descriptions[group]}"""\n\n'
        + header
        + helper_imports
        + "\n\n"
        + "\n\n".join(function_source(name) for name in names)
    )

helper_source = (
    '"""Gemeinsame Fenster-Fixtures und Exporthilfen; der Qt-Abbau bleibt in conftest."""\n\n'
    + header
    + '\nMESHES = Path(__file__).parent / "data" / "meshes"\n\n\n'
    + "\n\n".join(function_source(name) for name in helpers)
)
helper_source = helper_source.replace("def _expired(", "def expire_trial(")
pending[ROOT / "tests/ui_helpers.py"] = helper_source
moved = [*helpers, *(name for names in groups.values() for name in names)]
assert len(moved) == len(set(moved))
for name in moved:
    node = definitions[name]
    start = min([node.lineno, *(entry.lineno for entry in node.decorator_list)]) - 1
    for index in range(start, node.end_lineno):
        lines[index] = ""
remaining = "".join(lines)
remaining = remaining.replace('MESHES = Path(__file__).parent / "data" / "meshes"', helper_imports.strip())
for heading in (
    "# --- Export aus dem Fenster (§29, §2.2) ------------------------------------------",
    "# --- Lizenzierung an der Oberfläche (Konzept V4b) ---------------------------------",
    "# --- der Export beginnt, wo er zuletzt aufgehört hat (RM-141) ---------------------",
):
    remaining = remaining.replace(heading, "")
remaining = remaining.replace("# --- generated dialogs ----------------------------------------------------------", "# --- Auswahl und Merkmalsfenster ------------------------------------------------")
remaining = remaining.replace("# --- Fernsteuerung über MCP (Konzept P15 §7 Etappe 9, D19) ----------------------", "# --- Zeichnen und Operationsmenüs -----------------------------------------------")
while "\n\n\n\n" in remaining:
    remaining = remaining.replace("\n\n\n\n", "\n\n\n")
assert path.read_text(encoding="utf-8") == source, "Die Quelldatei wurde inzwischen bearbeitet."
for target, text in pending.items():
    target.write_text(text, encoding="utf-8")
path.write_text(remaining, encoding="utf-8")
print({group: len(names) for group, names in groups.items()})
