"""Erzeugt die Sonde nur aus den lokal eingefrorenen Prüfbausteinen."""
from pathlib import Path
import ast
import hashlib
import json

root = Path(__file__).resolve().parent
helpers_path = root / "probe_helpers.py.inc"
pins_path = root / "helper-pins.json"
helper_names = ("probe_helpers.py.inc", "menu_driver.py", "feature_checks.py", "general_checks.py", "analysis_checks.py", "run_context.py", "gesture_checks.py", "stl_export_checks.py", "surface_pick_footprint.py")
if not helpers_path.exists():
    # Einmal aus der bereits verwendeten Sonde übernehmen. Die aktive fremde
    # Prüfsitzung ist ab hier keine Eingangsquelle mehr.
    previous = (root / "probe.py").read_text(encoding="utf-8")
    wanted = {"plain", "write", "log", "settle", "wait", "click", "guard", "scene_data", "tree_items", "select_item"}
    found = {node.name: ast.get_source_segment(previous, node) for node in ast.parse(previous).body
             if isinstance(node, ast.FunctionDef) and node.name in wanted}
    if found.keys() != wanted:
        raise RuntimeError("Die bisherige Sonde enthält nicht alle erwarteten Prüfbausteine")
    with helpers_path.open("x", encoding="utf-8", newline="\n") as output:
        output.write("\n\n".join(found.values()) + "\n")
hashes = {name: hashlib.sha256((root / name).read_bytes()).hexdigest() for name in helper_names}
if pins_path.exists():
    pin_record = json.loads(pins_path.read_text(encoding="utf-8"))
    expected = pin_record.get("hashes", pin_record)
    if expected != hashes:
        changed = [name for name in helper_names if expected.get(name) != hashes[name]]
        raise RuntimeError("Eingefrorene Prüfbausteine wurden geändert: " + ", ".join(changed))
else:
    with pins_path.open("x", encoding="utf-8", newline="\n") as output:
        json.dump(hashes, output, ensure_ascii=False, indent=2)
source = (root / "probe_template.py").read_text(encoding="utf-8")
if source.count("# HELPERS") != 1:
    raise RuntimeError("Die Vorlage braucht genau eine Einfügestelle für Prüfbausteine")
source = source.replace("# HELPERS", helpers_path.read_text(encoding="utf-8"))
ast.parse(source)
temporary = root / "probe.next.py"
temporary.write_text(source, encoding="utf-8", newline="\n")
temporary.replace(root / "probe.py")
print("Prüfstand aus unveränderten lokalen Bausteinen vorbereitet")

