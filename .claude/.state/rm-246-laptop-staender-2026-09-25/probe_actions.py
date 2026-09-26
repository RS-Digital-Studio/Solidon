"""Sonde RM-181: Handlungsliste je Merkmal an echten Modellen messen.

Aufruf: probe_actions.py <datei> [<ausgabe.json>] [--limit N]

Lädt die Datei über den Kundenweg (Importplan, Verlauf, Auswertung), misst
je Körper ``actions_for`` mit Netz je Merkmal (kalt, dann warm), die
Gruppenauskunft ``alike_for_actions`` und den Steckbrief zur Auswahl.
"""

from __future__ import annotations

import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

import os

TREE = os.environ.get("PROBE_TREE", r"F:\3D Druck.review-050\wt-beziehungen")
sys.path.insert(0, TREE)

import app  # noqa: E402

print("app:", app.__file__, flush=True)

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()

from app.core.geom.mesh import as_mesh_data  # noqa: E402
from app.core.ingest.plan import import_plan  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.perceive import relations  # noqa: E402
from app.core.perceive.actions import actions_for  # noqa: E402
from app.core.scene import History, evaluate  # noqa: E402
from app.core.scene.project import ProjectSources, new_project  # noqa: E402
from app.core.types import Source  # noqa: E402


def _ask(question: str, choices: list[str]) -> str:
    for choice in choices:
        if choice == "mm":
            return choice
    return choices[0]


def load(path: Path):
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
    started = time.perf_counter()
    result = evaluate(document, profile, sources=ProjectSources(project), ask=_ask)
    return project, profile, result, time.perf_counter() - started


def main() -> int:
    path = Path(sys.argv[1])
    out = Path(sys.argv[2]) if len(sys.argv) > 2 and not sys.argv[2].startswith("--") else None
    limit = None
    if "--limit" in sys.argv:
        limit = int(sys.argv[sys.argv.index("--limit") + 1])
    project, profile, result, seconds = load(path)
    report: dict = {"file": path.name, "load_seconds": round(seconds, 2), "bodies": []}
    print(f"geladen in {seconds:.2f}s, {len(result.scene.objects)} Körper", flush=True)
    for object_id, entry in result.scene.objects.items():
        features = entry.features
        mesh = as_mesh_data(entry.mesh)
        kinds = Counter(feature.kind for feature in features.values())
        chosen = [f for f in features.values() if f.kind not in ("face", "edge_loop")]
        if limit is not None:
            chosen = chosen[:limit]
        cold: list[float] = []
        warm: list[float] = []
        group_times: list[float] = []
        offered: Counter = Counter()
        greyed: Counter = Counter()
        for feature in chosen:
            t0 = time.perf_counter()
            rows = actions_for(feature, features, mesh=mesh)
            cold.append(time.perf_counter() - t0)
            t0 = time.perf_counter()
            actions_for(feature, features, mesh=mesh)
            warm.append(time.perf_counter() - t0)
            t0 = time.perf_counter()
            relations.alike_for_actions(
                [str(row.op) for row in rows if row.op], feature.id, features, mesh
            )
            group_times.append(time.perf_counter() - t0)
            for row in rows:
                if row.op:
                    offered[(feature.kind, row.op)] += 1
                else:
                    greyed[(feature.kind, str(row.title), str(row.reason)[:70])] += 1
        body = {
            "id": object_id,
            "name": str(entry.name),
            "triangles": mesh.triangle_count,
            "features": len(features),
            "kinds": dict(kinds),
            "measured": len(chosen),
            "actions_cold_median_ms": round(1000 * statistics.median(cold), 1) if cold else None,
            "actions_cold_max_ms": round(1000 * max(cold), 1) if cold else None,
            "actions_cold_total_s": round(sum(cold), 2),
            "actions_warm_median_ms": round(1000 * statistics.median(warm), 1) if warm else None,
            "groups_median_ms": round(1000 * statistics.median(group_times), 1)
            if group_times
            else None,
            "groups_max_ms": round(1000 * max(group_times), 1) if group_times else None,
            "groups_total_s": round(sum(group_times), 2),
            "offered": {f"{k}:{op}": n for (k, op), n in offered.most_common()},
            "greyed": [
                {"kind": k, "title": t, "reason": r, "count": n}
                for (k, t, r), n in greyed.most_common()
            ],
        }
        report["bodies"].append(body)
        print(
            f"{object_id} {entry.name}: {mesh.triangle_count} Dreiecke, {len(features)} Merkmale "
            f"{dict(kinds)}; actions kalt Median {body['actions_cold_median_ms']} ms "
            f"(max {body['actions_cold_max_ms']}, Summe {body['actions_cold_total_s']} s), "
            f"warm {body['actions_warm_median_ms']} ms; Gruppen Median "
            f"{body['groups_median_ms']} ms (max {body['groups_max_ms']}, Summe "
            f"{body['groups_total_s']} s)",
            flush=True,
        )
    if out is not None:
        out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
