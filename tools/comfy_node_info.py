"""Schreibt die Knotenbeschreibungen der mitgelieferten ComfyUI-Abläufe in den Korpus.

``tests/test_mesh_backend.py`` prüft die beiden Abläufe in
``app/core/backends/data`` gegen **diese** Beschreibungen: jeder Pflichteingang
gesetzt, kein unbekannter, jede Verbindung vom richtigen Typ, jeder feste Wert
in seiner Auswahl und seinen Grenzen. Die Suite hat kein ComfyUI; deshalb
liegt hier, was ComfyUI selbst unter ``/object_info`` antworten würde —
erzeugt, nicht getippt.

Gerechnet wird im Python von ComfyUI, ohne Server und **ohne Grafikkarte**
(``CUDA_VISIBLE_DEVICES=-1``, ``--cpu``): Es werden nur die Knotenklassen
geladen und beschrieben. Nach einem ComfyUI-Update, das Solidon voraussetzt,
neu erzeugen:

    python tools/comfy_node_info.py --comfyui "E:/ComfyUI/ComfyUI"
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.core.backends import comfy_setup  # noqa: E402
from app.core.backends.mesh import WORKFLOW_DIR  # noqa: E402

TARGET = ROOT / "tests" / "data" / "comfyui" / "object_info.json"

#: Läuft im Python von ComfyUI. ``server.PromptServer.node_info`` ist eine
#: verschachtelte Funktion; für die Knoten der neuen Bauart liefert
#: ``GET_NODE_INFO_V1`` dasselbe, für die klassischen steht die Abbildung hier.
_DESCRIBE = """
import asyncio, json, sys
root = sys.argv[1]
wanted = json.loads(sys.argv[2])
sys.argv = ["main.py", "--cpu"]
sys.path.insert(0, root)
import comfy.options
comfy.options.enable_args_parsing()
import nodes
from comfy_api.internal import _ComfyNodeInternal
asyncio.run(nodes.init_extra_nodes(init_custom_nodes=False, init_api_nodes=False))
import comfyui_version
out = {"comfyui": comfyui_version.__version__, "nodes": {}}
for name in wanted:
    cls = nodes.NODE_CLASS_MAPPINGS.get(name)
    if cls is None:
        continue
    if issubclass(cls, _ComfyNodeInternal):
        info = cls.GET_NODE_INFO_V1()
    else:
        info = {
            "input": cls.INPUT_TYPES(),
            "output": list(cls.RETURN_TYPES),
            "output_node": bool(getattr(cls, "OUTPUT_NODE", False)),
        }
    out["nodes"][name] = {
        "input": info["input"],
        "output": list(info["output"]),
        "output_node": bool(info.get("output_node", False)),
        "python_module": info.get("python_module", getattr(cls, "RELATIVE_PYTHON_MODULE", "nodes")),
    }
print("@@" + json.dumps(out, default=str))
"""


def wanted_nodes() -> list[str]:
    """Die Knotenarten beider Abläufe, sortiert."""
    found: set[str] = set()
    for path in sorted(WORKFLOW_DIR.glob("*.json")):
        graph = json.loads(path.read_text(encoding="utf-8"))
        found.update(str(node["class_type"]) for node in graph.values())
    return sorted(found)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Schreibt ComfyUIs Knotenbeschreibungen der Abläufe in den Korpus."
    )
    parser.add_argument("--comfyui", help="Pfad zur ComfyUI-Installation")
    parser.add_argument("--out", default=str(TARGET), help="Zieldatei")
    args = parser.parse_args()

    comfyui = comfy_setup.find_comfyui(args.comfyui)
    python = comfy_setup.find_python(comfyui)
    wanted = wanted_nodes()
    environment = dict(os.environ, CUDA_VISIBLE_DEVICES="-1", PYTHONUTF8="1")
    answer = subprocess.run(
        [str(python), "-s", "-c", _DESCRIBE, str(comfyui), json.dumps(wanted)],
        cwd=comfyui,
        env=environment,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    line = next((row for row in answer.stdout.splitlines() if row.startswith("@@")), "")
    if answer.returncode or not line:
        print(answer.stdout[-2000:], answer.stderr[-4000:], sep="\n", file=sys.stderr)
        return 1
    described = json.loads(line[2:])
    missing = sorted(set(wanted) - set(described["nodes"]))
    if missing:
        print("Diese Knoten kennt das ComfyUI nicht: " + ", ".join(missing), file=sys.stderr)
        return 1
    target = Path(args.out)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps(described, indent=1, ensure_ascii=False, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(f"{len(described['nodes'])} Knoten aus ComfyUI {described['comfyui']} → {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
