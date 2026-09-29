"""Sonde: Auswertung von Roberts Minigolf-Projekt, Erkennungsläufe je Schritt.

Aufruf: python sonde_minigolf.py <baum> <ausgabe.json> [<projekt.p3d>]

Liest das Projekt nur (nie schreiben), wertet es ohne Ergebnis-Cache vollständig
aus und zählt je Schritt, wie oft ``detect`` wirklich rechnet (kein Merker-
Treffer), wie lange, und wie oft eine Erkennung übertragen wurde. Am Ende die
Merkmale je Körper (Art, Name, Provenienz, Mitte) für den Vergleich vorher/nachher.
"""

from __future__ import annotations

import json
import logging
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

tree = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2])
project_path = Path(
    sys.argv[3]
    if len(sys.argv) > 3
    else r"F:\3D Dateien\Mini+Golf+All+Set-P1S_stls\falsch liegend.p3d"
)
sys.path.insert(0, str(tree))

import importlib  # noqa: E402

ev = importlib.import_module("app.core.scene.evaluate")
from app.cli.main import profile_of  # noqa: E402
from app.core.bootstrap import load_operations  # noqa: E402
from app.core.perceive import features as feat  # noqa: E402
from app.core.scene.project import ProjectSources, load  # noqa: E402

assert Path(ev.__file__).resolve().is_relative_to(tree), ev.__file__

load_operations()
project = load(project_path)
document = project.document

current: list[str] = ["?"]
fresh: dict[str, list[float]] = defaultdict(list)
carried_log: Counter[str] = Counter()
with_features_time: dict[str, float] = defaultdict(float)


class _Grab(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:
        if record.getMessage().startswith("carried"):
            carried_log[current[0]] += 1


feat._log.addHandler(_Grab())
feat._log.setLevel(logging.INFO)

original_with = ev._with_features
original_detect = ev.detect


def with_features(entry, previous, operation, *args, **kwargs):  # type: ignore[no-untyped-def]
    label = f"{operation.id}:{operation.op}"
    current[0] = label
    start = time.perf_counter()
    try:
        return original_with(entry, previous, operation, *args, **kwargs)
    finally:
        with_features_time[label] += time.perf_counter() - start


def detect(mesh, **kwargs):  # type: ignore[no-untyped-def]
    known = feat.known_detection(mesh)
    start = time.perf_counter()
    found = original_detect(mesh, **kwargs)
    if known is None:
        fresh[current[0]].append(round(time.perf_counter() - start, 3))
    return found


ev._with_features = with_features
ev.detect = detect

start = time.perf_counter()
cpu_start = time.process_time()
result = ev.evaluate(
    document,
    profile_of(project),
    sources=ProjectSources(project, base_dir=project_path.parent),
)
total = time.perf_counter() - start
cpu_total = time.process_time() - cpu_start

objects = {}
for object_id, body in sorted(result.scene.objects.items()):
    entries = []
    for name, feature in sorted(body.features.items()):
        centre = feat.centre_of(feature)
        entries.append(
            {
                "id": name,
                "kind": feature.kind,
                "provenance": feature.provenance,
                "created_by": feature.created_by,
                "centre": None if centre is None else [round(float(v), 4) for v in centre],
                "faces": len(feature.face_indices),
            }
        )
    objects[object_id] = {
        "name": str(body.name),
        "triangles": int(getattr(body.mesh, "triangle_count", 0)),
        "features": entries,
    }

report = {
    "tree": str(tree),
    "total_s": round(total, 2),
    "cpu_s": round(cpu_total, 2),
    "stopped_at": result.stopped_at,
    "steps": [f"{op.id}:{op.op}" for op in sorted(document.ops, key=lambda o: o.id)],
    "fresh_detect": dict(fresh),
    "fresh_detect_count": sum(len(v) for v in fresh.values()),
    "fresh_detect_s": round(sum(sum(v) for v in fresh.values()), 2),
    "carried": dict(carried_log),
    "with_features_s": {key: round(value, 2) for key, value in with_features_time.items()},
    "findings": dict(Counter(f.code for f in result.scene.report.findings)),
    "finding_details": [
        {
            "code": f.code,
            "object": f.object_id,
            "op": f.op_id,
            "values": {k: str(v) for k, v in (f.values or {}).items()},
        }
        for f in result.scene.report.findings
    ],
    "objects": objects,
}
out.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
summary = ("total_s", "cpu_s", "fresh_detect_count", "fresh_detect_s", "carried", "stopped_at")
print(json.dumps({key: report[key] for key in summary}, ensure_ascii=False))
for key in report["steps"]:
    print(
        key,
        "fresh",
        len(fresh.get(key, [])),
        round(sum(fresh.get(key, [])), 1),
        "s; carried",
        carried_log.get(key, 0),
        "; with_features",
        round(with_features_time.get(key, 0.0), 1),
        "s",
    )
