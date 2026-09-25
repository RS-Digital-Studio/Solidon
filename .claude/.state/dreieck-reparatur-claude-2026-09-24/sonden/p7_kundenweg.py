"""Sonde 7: Kundenweg über die Auswertung an echten Dateien.

Laden (einmal regulär, einmal ungeschweißt, damit „Reparieren“ wirklich
etwas tut), Reparieren, dann einen Schritt, der eine erkannte Bohrung beim
Namen nennt. Gemessen: Namen und Maße vor/nach der Reparatur, Rückfragen,
Laufzeit je Auswertung.
"""

from __future__ import annotations

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
FILES = [
    Path(r"F:\3D Dateien\large-screwdriver-holder-with-honeycomb-pattern.stl"),
    Path(r"F:\3D Dateien\the-over-engineered-backpack-wall-mount-v2.stl"),
    Path(r"F:\3D Dateien\broomholdervcd_d35mm.stl"),
]


class Asked:
    def __init__(self) -> None:
        self.questions = []

    def __call__(self, question, choices):
        self.questions.append((question, list(choices)))
        return choices[0]


def run(project):
    asked = Asked()
    forget_cache()
    start = time.perf_counter()
    result = evaluate(project.document, PROFILE, sources=ProjectSources(project), ask=asked)
    return result, asked.questions, time.perf_counter() - start


def features_of(result):
    body = result.scene.objects["obj_1"]
    return {name: (f.kind, round(float(f.params.get("diameter", f.params.get("area", 0.0))), 3),
                   tuple(round(float(v), 2) for v in f.params.get("centre", ())))
            for name, f in body.features.items() if f.kind != "edge_loop"}


def main() -> None:
    with OUT.open("w", encoding="utf-8") as out:
        for path in FILES:
            for weld in (True, False):
                project = new_project("centauri-carbon-2", "petg")
                project.sources["src_1"] = path.read_bytes()
                project.document.sources["src_1"] = Source(
                    id="src_1", kind="import", path=f"sources/{path.name}", sha256="")
                history = History(project.document)
                history.apply("Laden", [OperationDraft(
                    op="load", params={"source": "src_1", "unit": "mm", "weld": weld})])
                loaded, questions, took = run(project)
                before = features_of(loaded)
                holes = sorted(n for n, v in before.items() if v[0] == "hole")
                out.write(f"\n# {path.name} weld={weld}: geladen {took:.1f}s, "
                          f"{len(before)} Merkmale, Bohrungen {holes}, Fragen {len(questions)}\n")
                history.apply("Reparieren", [OperationDraft(
                    op="repair", inputs=("obj_1",), params={})])
                if holes:
                    history.apply("Bohrung ändern", [OperationDraft(
                        op="resize_hole", inputs=("obj_1",),
                        params={"at_feature": holes[-1], "diameter": before[holes[-1]][1] + 0.5})])
                after, questions, took = run(project)
                repaired = features_of(after)
                codes = [f.code for f in after.scene.report.findings
                         if f.op_id == 2 or f.severity != "info"]
                out.write(f"  nach Reparatur{' + Bohrung ändern' if holes else ''}: {took:.1f}s, "
                          f"complete={after.complete} stopped_at={after.stopped_at}, "
                          f"Fragen {len(questions)}, Befunde {codes}\n")
                for question, choices in questions:
                    out.write(f"  FRAGE {question[:200]!r} {choices}\n")
                lost = sorted(set(before) - set(repaired))
                gained = sorted(set(repaired) - set(before))
                moved = sorted(n for n in set(before) & set(repaired)
                               if before[n][0] != repaired[n][0]
                               or (n not in holes[-1:] and before[n][2] != repaired[n][2]))
                out.write(f"  verloren {lost}\n  neu {gained}\n  Art/Lage geändert {moved}\n")
                if holes:
                    out.write(f"  {holes[-1]}: {before[holes[-1]]} -> {repaired.get(holes[-1])}\n")
                out.flush()


if __name__ == "__main__":
    main()
