"""Sonde RM-223: Wohin geht die Zeit, wenn nach *Kanten verfeinern* ausgewertet wird?

Lädt eine Datei über den Kundenweg, hängt *Kanten verfeinern* mit der
genannten Kantenlänge an und profiliert die Auswertung mit ``cProfile``.
Gedruckt werden die dreißig teuersten Funktionen nach Gesamtzeit
einschließlich Aufgerufener. Nur lesend.

Aufruf: python profil_auswertung.py <baum> <datei> <kante>
"""

from __future__ import annotations

import cProfile
import pstats
import sys
import time
from pathlib import Path

TREE = Path(sys.argv[1])
sys.path.insert(0, str(TREE))

import app  # noqa: E402

where = str(Path(app.__file__).resolve())
if not where.startswith(str(TREE.resolve())):
    raise SystemExit(f"falscher Baum geladen: {where}")
print(f"gemessen wird {where}", flush=True)

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()

from app.core.ingest.plan import import_plan  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.scene import History, OperationDraft, evaluate  # noqa: E402
from app.core.scene.project import ProjectSources, new_project  # noqa: E402
from app.core.types import Source  # noqa: E402

path = Path(sys.argv[2])
edge = float(sys.argv[3])
payload = path.read_bytes()
project = new_project("centauri-carbon-2", "petg")
document = project.document
document.sources["src_1"] = Source(id="src_1", kind="import", path=f"sources/{path.name}", sha256="")
project.sources["src_1"] = payload
plan = import_plan("src_1", path.name, payload, unit="auto", first_model=True)
History(document).apply("Laden", [plan.draft])
profile = profiles.make_profile("centauri-carbon-2", "petg")
sources = ProjectSources(project)
base = evaluate(document, profile, sources=sources, ask=lambda q, c: c[0])
object_id = next(iter(base.scene.objects))
History(document).apply(
    "Verfeinern", [OperationDraft(op="remesh_mesh", inputs=(object_id,), params={"edge": edge})]
)

profiler = cProfile.Profile()
started = time.perf_counter()
profiler.enable()
result = evaluate(document, profile, sources=sources, ask=lambda q, c: c[0])
profiler.disable()
spent = time.perf_counter() - started
body = next(iter(result.scene.objects.values()))
print(f"{path.name} bei {edge} mm: {spent:.1f} s, {body.mesh.triangle_count} Dreiecke", flush=True)
for finding in result.scene.report.findings:
    print(f"  {finding.code}: {str(finding.message)[:160]}")
pstats.Stats(profiler).sort_stats("cumulative").print_stats(30)
