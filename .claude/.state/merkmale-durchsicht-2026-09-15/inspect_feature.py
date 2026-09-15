"""Einzelbefunde nachsehen.

inspect_feature.py show <datei> <körpername|index> <merkmal-id> [...]
inspect_feature.py op <datei> <körpername|index> <op> '<json-params>'
"""
# ruff: noqa: E501  -- Sonde: lange Ausgabezeilen sind hier Absicht

from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()

from app.core.ingest.plan import import_plan  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.perceive.digest import _feature_line  # noqa: E402
from app.core.perceive.features import CylinderFit, angular_span  # noqa: E402
from app.core.scene import History, OperationDraft, evaluate  # noqa: E402
from app.core.scene.cache import ResultCache  # noqa: E402
from app.core.scene.project import ProjectSources, new_project  # noqa: E402
from app.core.types import Source  # noqa: E402


def _ask(question, choices):
    return "mm" if "mm" in choices else choices[0]


def load(path: Path):
    payload = path.read_bytes()
    project = new_project("centauri-carbon-2", "petg")
    document = project.document
    document.sources["src_1"] = Source(
        id="src_1", kind="import", path=f"sources/{path.name}", sha256=""
    )
    project.sources["src_1"] = payload
    plan = import_plan("src_1", path.name, payload, unit="auto", first_model=True)
    history = History(document)
    history.apply("Laden", [plan.draft])
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    cache = ResultCache()
    sources = ProjectSources(project)
    result = evaluate(document, profile, sources=sources, ask=_ask, cache=cache)
    return document, history, profile, sources, cache, result


def pick(scene, which: str):
    if which.isdigit():
        return list(scene.objects.items())[int(which)]
    for oid, entry in scene.objects.items():
        if str(entry.name) == which:
            return oid, entry
    raise SystemExit(
        f"Körper {which!r} nicht gefunden: {[str(e.name) for e in scene.objects.values()]}"
    )


def show(entry, fids):
    body = entry.mesh.raw
    features = entry.features
    owner = {}
    for fid, f in features.items():
        for face in f.face_indices:
            owner[face] = fid
    normals = np.asarray(body.face_normals)
    adjacency = np.asarray(body.face_adjacency)
    areas = np.asarray(body.area_faces)
    for fid in fids:
        f = features[fid]
        p = f.params
        print("==", _feature_line(fid, f))
        print("   params:", {k: (round(v, 4) if isinstance(v, float) else v) for k, v in p.items()})
        patch = list(f.face_indices)
        print("   faces:", len(patch), "area:", round(float(areas[patch].sum()), 3))
        pts = np.asarray(body.vertices)[np.unique(np.asarray(body.faces)[patch])]
        print(
            "   bbox:", np.round(pts.min(axis=0), 3).tolist(), np.round(pts.max(axis=0), 3).tolist()
        )
        axis = p.get("axis")
        if (
            axis is not None
            and p.get("centre") is not None
            and (p.get("radius") or p.get("diameter"))
        ):
            r = float(p.get("radius") or float(p["diameter"]) / 2)
            fit = CylinderFit(
                axis=tuple(axis),
                centre=tuple(p["centre"]),
                radius=r,
                residual=0.0,
                inward=bool(p.get("recess", False)),
            )
            print("   span:", round(angular_span(body, fit, patch), 1), "°")
            dots = normals[patch] @ np.asarray(axis, float)
            print(
                "   normal·axis im Fleck: min/max",
                round(float(dots.min()), 3),
                round(float(dots.max()), 3),
            )
        own = set(patch)
        neigh = {}
        for a, b in adjacency.tolist():
            out = b if a in own and b not in own else a if b in own and a not in own else None
            if out is None:
                continue
            key = owner.get(out, "-")
            d = float(normals[out] @ np.asarray(axis, float)) if axis is not None else None
            neigh.setdefault(key, []).append(round(d, 2) if d is not None else None)
        print("   Nachbarn (Merkmal: n·axis der Nachbarflächen):")
        for key, ds in sorted(neigh.items(), key=lambda kv: -len(kv[1])):
            kind = features[key].kind if key in features else "-"
            print(f"      {key:14} {kind:12} n={len(ds)} dots={sorted(set(ds))[:8]}")


def run_op(document, history, profile, sources, cache, base, oid, op, params):
    before = base.scene.objects[oid]
    history.apply(
        op,
        [
            OperationDraft(
                op=op,
                inputs=(oid,),
                outputs=(oid,) if op != "duplicate_feature" else None,
                params=params,
            )
        ],
    )
    result = evaluate(document, profile, sources=sources, ask=_ask, cache=cache)
    print("complete:", result.complete, "stopped_at:", result.stopped_at)
    for f in result.scene.report.findings:
        if f.op_id is not None and f.op_id not in base.completed:
            print(
                "  finding:",
                f.code,
                f.severity,
                str(f.message)[:160],
                {k: str(v)[:60] for k, v in (f.values or {}).items()},
            )
    after = result.scene.objects.get(oid)
    if after is None:
        print("Körper weg")
        return
    print(
        f"vol {before.mesh.volume:.2f} -> {after.mesh.volume:.2f}  wt {before.mesh.is_watertight}->{after.mesh.is_watertight}  comp {before.mesh.component_count}->{after.mesh.component_count}  tri {before.mesh.triangle_count}->{after.mesh.triangle_count}"
    )
    if after.mesh.component_count > 1:
        parts = after.mesh.raw.split(only_watertight=False)
        vols = sorted((round(float(p.volume), 3) for p in parts), reverse=True)
        print("  Komponentenvolumen:", vols[:12])
    b, a = before.features, after.features
    for fid in sorted(set(b) - set(a)):
        print("  weg:   ", _feature_line(fid, b[fid]))
    for fid in sorted(set(a) - set(b)):
        print("  neu:   ", _feature_line(fid, a[fid]))
    for fid in sorted(set(a) & set(b)):
        if _feature_line(fid, a[fid]) != _feature_line(fid, b[fid]):
            print("  anders:", _feature_line(fid, b[fid]), "->", _feature_line(fid, a[fid]))


def main():
    mode, path, which = sys.argv[1], Path(sys.argv[2]), sys.argv[3]
    document, history, profile, sources, cache, base = load(path)
    oid, entry = pick(base.scene, which)
    print(
        f"# {path.name} / {entry.name} ({oid}) tri={entry.mesh.triangle_count} size={np.round(np.asarray(entry.mesh.bounds.maximum) - np.asarray(entry.mesh.bounds.minimum), 2).tolist()}"
    )
    if mode == "show":
        show(entry, sys.argv[4:])
    elif mode == "op":
        run_op(
            document,
            history,
            profile,
            sources,
            cache,
            base,
            oid,
            sys.argv[4],
            json.loads(sys.argv[5]),
        )
    elif mode == "list":
        for fid, f in entry.features.items():
            print(" ", _feature_line(fid, f), "| faces", len(f.face_indices))


if __name__ == "__main__":
    main()
