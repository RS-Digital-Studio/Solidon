"""Sonde RM-223: Trägt *Kanten verfeinern* die Merkmale über die Herkunft der Dreiecke weiter?

Lädt die Datei über den Kundenweg (``import_plan``, ``History``, ``evaluate``),
hängt je Versuch eine Netzoperation an und druckt, wo die Kette anhält, mit
welchem Satz, und wie viele Dreiecke herauskommen — dazu die Vorabschätzung
der Operation gegen ihre Grenze. Nur lesend. Fassung mit Merkmalszahl: je Versuch die Merkmale vorher und nachher.

Aufruf: python probe_netzops.py <baum> <datei> [<datei> ...]
"""

from __future__ import annotations

import copy
import ctypes
import sys
import time
from ctypes import wintypes
from pathlib import Path


class _Counters(ctypes.Structure):
    """``PROCESS_MEMORY_COUNTERS`` — die Spitze des Arbeitssatzes ohne neue Abhängigkeit."""

    _fields_ = [
        ("cb", wintypes.DWORD),
        ("PageFaultCount", wintypes.DWORD),
        ("PeakWorkingSetSize", ctypes.c_size_t),
        ("WorkingSetSize", ctypes.c_size_t),
        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPagedPoolUsage", ctypes.c_size_t),
        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
        ("PagefileUsage", ctypes.c_size_t),
        ("PeakPagefileUsage", ctypes.c_size_t),
    ]


def peak_working_set() -> int:
    counters = _Counters()
    counters.cb = ctypes.sizeof(counters)
    windll = ctypes.windll  # type: ignore[attr-defined]
    # Ohne Prototypen schneidet ctypes den 64-Bit-Handle auf int ab, und die
    # Abfrage liefert still null (so am 25.09.2026 im ersten Lauf).
    windll.kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    windll.psapi.GetProcessMemoryInfo.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(_Counters),
        wintypes.DWORD,
    ]
    windll.psapi.GetProcessMemoryInfo(
        windll.kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb
    )
    return int(counters.PeakWorkingSetSize)


TREE = Path(sys.argv[1])
sys.path.insert(0, str(TREE))

import app  # noqa: E402

where = str(Path(app.__file__).resolve())
if not where.startswith(str(TREE.resolve())):
    raise SystemExit(f"falscher Baum geladen: {where}")
print(f"gemessen wird {where}", flush=True)

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()

from app.core.geom import mesh_ops  # noqa: E402
from app.core.ingest.plan import import_plan  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.scene import History, OperationDraft, evaluate  # noqa: E402
from app.core.scene.project import ProjectSources, new_project  # noqa: E402
from app.core.types import Source  # noqa: E402

TRIALS = [
    ("Kanten verfeinern 1,0 mm", "remesh_mesh", {"edge": 1.0}),
    ("Kanten verfeinern 0,5 mm", "remesh_mesh", {"edge": 0.5}),
]
_ALT = [
    ("Kanten verfeinern 1,0 mm", "remesh_mesh", {"edge": 1.0}),
    ("Kanten verfeinern 0,5 mm", "remesh_mesh", {"edge": 0.5}),
    ("Dreiecke angleichen 1,0 mm", "remesh_uniform", {"edge": 1.0}),
    ("Dreiecke angleichen, Vorgabe", "remesh_uniform", {}),
]

for name in sys.argv[2:]:
    path = Path(name)
    payload = path.read_bytes()
    project = new_project("centauri-carbon-2", "petg")
    document = project.document
    document.sources["src_1"] = Source(
        id="src_1", kind="import", path=f"sources/{path.name}", sha256=""
    )
    project.sources["src_1"] = payload
    plan = import_plan("src_1", path.name, payload, unit="auto", first_model=True)
    History(document).apply("Laden", [plan.draft])
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    sources = ProjectSources(project)
    base = evaluate(document, profile, sources=sources, ask=lambda q, c: c[0])
    object_id, entry = next(iter(base.scene.objects.items()))
    print(
        f"{path.name}: {entry.mesh.triangle_count} Dreiecke, Fläche {entry.mesh.area:.0f} mm², "
        f"Diagonale {entry.mesh.bounds.diagonal:.0f} mm",
        flush=True,
    )
    for label, op, params in TRIALS:
        edge = params.get("edge")
        if edge is not None:
            wanted = mesh_ops.estimated_triangles(entry.mesh, float(edge))
            print(f"  {label}: Schätzung {wanted} (Grenze {mesh_ops.MAX_REMESH_TRIANGLES})")
        trial = copy.deepcopy(document)
        try:
            History(trial).apply(label, [OperationDraft(op=op, inputs=(object_id,), params=params)])
        except Exception as error:
            print(f"    nicht anlegbar: {type(error).__name__}: {error}")
            continue
        started = time.perf_counter()
        try:
            result = evaluate(trial, profile, sources=sources, ask=lambda q, c: c[0])
        except Exception as error:
            print(f"    geworfen: {type(error).__name__}: {error}")
            continue
        spent = time.perf_counter() - started
        peak = peak_working_set()
        codes = [
            f"{finding.code}: {finding.message}"
            for finding in result.scene.report.findings
            if finding.severity in ("warning", "error") or finding.code.startswith("op.")
        ]
        body = next(iter(result.scene.objects.values()), None)
        triangles = body.mesh.triangle_count if body is not None else None
        print(f"    Merkmale vorher {len(entry.features)}, nachher {len(body.features) if body else None}")
        print(
            f"    {spent:.1f} s, Spitze des Prozesses {peak / 2**20:.0f} MiB, angehalten "
            f"{result.stopped_at}, Dreiecke {triangles}",
            flush=True,
        )
        for line in codes[:6]:
            print(f"      {line[:200]}")
