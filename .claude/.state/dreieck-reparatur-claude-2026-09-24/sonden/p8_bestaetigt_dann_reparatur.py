"""Sonde 8: Großnetz mit bestätigter Vollerkennung, danach ein gewöhnlicher Schritt.

Grenzen wie in den Tests verschoben, damit ein Kundennetz mit 59 740
Dreiecken als „groß“ gilt: automatische Grenze 50 000, bestätigbare Grenze
5 000 000. Beim Laden wird die Vollerkennung bestätigt. Danach „Reparieren“
(ungeschweißt geladen, damit die Reparatur ändert) und — getrennt — nur ein
Verschieben. Gefragt: Läuft der Schritt durch, und was wird aus den Merkmalen?
"""

from __future__ import annotations

import importlib
import os
import sys
import tempfile
import time

_ISOLATED = tempfile.mkdtemp(prefix="solidon-sonde-")
for _variable in ("APPDATA", "LOCALAPPDATA", "HOME", "XDG_DATA_HOME", "XDG_CONFIG_HOME",
                  "XDG_CACHE_HOME"):
    os.environ[_variable] = _ISOLATED
sys.path.insert(0, r"F:\3D Druck")

from pathlib import Path  # noqa: E402

from app.core.activation import store as activation_store  # noqa: E402

activation_store.DEMO_UNTIL = None
activation_store.TRIAL_FROM = activation_store.DEMO_FROM

from app.core.bootstrap import load_operations  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.perceive.features import forget_cache  # noqa: E402
from app.core.scene import History, OperationDraft, evaluate  # noqa: E402
from app.core.scene.project import ProjectSources, new_project  # noqa: E402
from app.core.types import Source  # noqa: E402

load_operations()
PROFILE = profiles.make_profile("centauri-carbon-2", "petg")
OUT = Path(__file__).with_suffix(".txt")


class Confirm:
    def __init__(self) -> None:
        self.questions = []

    def __call__(self, question, choices):
        self.questions.append((question[:90], list(choices)))
        return choices[-1]


def run(out, title, project):
    asked = Confirm()
    forget_cache()
    start = time.perf_counter()
    result = evaluate(project.document, PROFILE, sources=ProjectSources(project), ask=asked)
    took = time.perf_counter() - start
    body = result.scene.objects.get("obj_1")
    out.write(f"\n# {title}: {took:.1f}s complete={result.complete} stopped_at={result.stopped_at} "
              f"Merkmale={len(body.features) if body else '-'} Fragen={asked.questions}\n")
    for finding in result.scene.report.findings:
        if finding.severity != "info" or finding.code.startswith("perceive"):
            out.write(f"  Befund {finding.severity} {finding.code} op={finding.op_id} "
                      f"{str(finding.message)[:140]!r} {dict(finding.values)}\n")
    out.flush()
    return result


def main() -> None:
    evaluation = importlib.import_module("app.core.scene.evaluate")
    evaluation.FEATURE_LIMIT_TRIANGLES = 50_000
    local = importlib.import_module("app.core.perceive.local")
    local.FEATURE_LIMIT_TRIANGLES = 50_000
    path = Path(r"F:\3D Dateien\broomholdervcd_d35mm.stl")
    with OUT.open("w", encoding="utf-8") as out:
        for second in ("repair", "translate_object"):
            project = new_project("centauri-carbon-2", "petg")
            project.sources["src_1"] = path.read_bytes()
            project.document.sources["src_1"] = Source(
                id="src_1", kind="import", path=f"sources/{path.name}", sha256="")
            history = History(project.document)
            history.apply("Laden", [OperationDraft(
                op="load", params={"source": "src_1", "unit": "mm",
                                   "weld": second != "repair"})])
            run(out, f"geladen, Vollerkennung bestätigt (danach {second})", project)
            params = {} if second == "repair" else {"dx": 5.0, "dy": 0.0, "dz": 0.0}
            history.apply("Zweiter Schritt", [OperationDraft(op=second, inputs=("obj_1",),
                                                             params=params)])
            run(out, f"nach {second}", project)


if __name__ == "__main__":
    main()
