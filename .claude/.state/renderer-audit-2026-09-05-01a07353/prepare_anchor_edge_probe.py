"""Friert die vorhandenen UI-Helfer für die enge Anker-/Kantenprobe ein."""

import ast
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parent
folder = root / "anchor-edge-probe-helpers-v1"
folder.mkdir(exist_ok=True)
pins = {}
for name in ("feature_checks.py", "gesture_checks.py", "analysis_checks.py", "menu_driver.py"):
    data = (root / name).read_bytes()
    destination = folder / name
    if destination.exists() and destination.read_bytes() != data:
        raise RuntimeError(f"Vorhandener Helferpin unterscheidet sich: {name}")
    if not destination.exists():
        destination.write_bytes(data)
    pins[name] = hashlib.sha256(data).hexdigest()

segments = []
for name, wanted in (
    ("probe_helpers.py.inc", {"plain", "write", "log", "pump_events", "settle", "wait", "click", "tree_items", "select_item"}),
    ("probe_template.py", {"canvas_access", "independent_surface", "targeted_surface_points"}),
):
    text = (root / name).read_text(encoding="utf-8")
    found = {node.name: ast.get_source_segment(text, node) for node in ast.parse(text).body if isinstance(node, ast.FunctionDef) and node.name in wanted}
    if found.keys() != wanted:
        raise RuntimeError(f"Unvollständige UI-Helfer in {name}")
    segments.extend(found.values())
    pins[name] = hashlib.sha256(text.encode()).hexdigest()

source = (root / "anchor_edge_probe_template.py").read_text(encoding="utf-8")
source = source.replace("# PINNED_UI_FUNCTIONS", "\n\n".join(segments))
ast.parse(source)
target = root / "anchor_edge_probe.py"
target.write_text(source, encoding="utf-8", newline="\n")
pins["anchor_edge_probe.py"] = hashlib.sha256(target.read_bytes()).hexdigest()
(folder / "pins.json").write_text(json.dumps(pins, indent=2), encoding="utf-8")
print(json.dumps({"prepared": str(target), "pins": pins}, indent=2))
