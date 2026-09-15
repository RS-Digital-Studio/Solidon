"""Phase 1: eine Datei über den echten Ladeweg laden, Merkmale je Körper prüfen.

Aufruf: probe_features.py <datei> <ausgabe.json>
Schreibt je Körper Merkmale, Plausibilitätsbefunde und die Handlungsliste.
"""
# ruff: noqa: E501  -- Sonde: lange Ausgabezeilen sind hier Absicht

from __future__ import annotations

import json
import math
import sys
import time
import traceback
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()

from app.core.ingest.plan import import_plan  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.perceive import relations  # noqa: E402
from app.core.perceive.actions import actions_for  # noqa: E402
from app.core.perceive.digest import _feature_line  # noqa: E402
from app.core.perceive.features import freeform_dropped  # noqa: E402
from app.core.scene import History, evaluate  # noqa: E402
from app.core.scene.project import ProjectSources, new_project  # noqa: E402
from app.core.types import Source  # noqa: E402


def _peak_rss_mb() -> float | None:
    try:
        import ctypes
        from ctypes import wintypes

        class Counters(ctypes.Structure):
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

        counters = Counters()
        counters.cb = ctypes.sizeof(Counters)
        handle = ctypes.windll.kernel32.GetCurrentProcess()
        if ctypes.windll.psapi.GetProcessMemoryInfo(handle, ctypes.byref(counters), counters.cb):
            return round(counters.PeakWorkingSetSize / 1024 / 1024, 1)
    except Exception:
        return None
    return None


def _ask(question: str, choices: list[str]) -> str:
    # Der Kunde würde bei einer STL „mm" antworten.
    for choice in choices:
        if choice == "mm":
            return choice
    return choices[0]


def _vec(value) -> np.ndarray | None:
    if isinstance(value, (list, tuple)) and len(value) == 3:
        try:
            return np.asarray([float(v) for v in value])
        except TypeError, ValueError:
            return None
    return None


def _checks(entry, features: dict) -> list[dict]:
    """Plausibilitätsprüfungen an der Merkmalsliste eines Körpers."""
    found: list[dict] = []
    mesh = entry.mesh
    size = np.asarray(mesh.bounds.maximum) - np.asarray(mesh.bounds.minimum)
    extent = float(np.max(size))

    # 1. Mehrfachbelegung: ein Dreieck in zwei Merkmalen
    owner: dict[int, list[str]] = defaultdict(list)
    for fid, feature in features.items():
        for face in feature.face_indices:
            owner[face].append(fid)
    shared: Counter = Counter()
    for owners in owner.values():
        if len(owners) > 1:
            shared[tuple(sorted(owners))] += 1
    for owners, count in shared.most_common(30):
        kinds = [features[o].kind for o in owners]
        found.append(
            {
                "check": "faces_shared",
                "features": list(owners),
                "kinds": kinds,
                "faces": count,
                "sizes": [len(features[o].face_indices) for o in owners],
            }
        )

    # 2. Nahezu doppelte Merkmale gleicher Art
    items = list(features.items())
    for i, (fid_a, a) in enumerate(items):
        ca = _vec(a.params.get("centre"))
        if ca is None:
            continue
        for fid_b, b in items[i + 1 :]:
            if b.kind != a.kind:
                continue
            cb = _vec(b.params.get("centre"))
            if cb is None:
                continue
            dist = float(np.linalg.norm(ca - cb))
            da = a.params.get("diameter") or a.params.get("radius")
            db = b.params.get("diameter") or b.params.get("radius")
            same_size = (
                da is not None
                and db is not None
                and abs(float(da) - float(db)) <= 0.02 * max(abs(float(da)), 1e-9)
            )
            if dist < 0.05 * max(extent, 1.0) * 0.1 and same_size:
                found.append(
                    {
                        "check": "near_duplicate",
                        "features": [fid_a, fid_b],
                        "kind": a.kind,
                        "distance": round(dist, 4),
                        "size": [da, db],
                    }
                )

    # 3. Langloch so lang wie breit / Fund statt Messung
    for fid, f in features.items():
        p = f.params
        if f.kind == "slot":
            d = float(p.get("diameter", 0.0))
            ln = float(p.get("length", 0.0))
            if d > 0 and abs(ln - d) < 0.02 * d:
                found.append(
                    {"check": "slot_as_long_as_wide", "feature": fid, "d": d, "length": ln}
                )
        if f.kind == "fillet":
            r = float(p.get("radius", 0.0))
            if r > 0.5 * extent:
                found.append({"check": "fillet_larger_than_body", "feature": fid, "radius": r})
            span = p.get("span")
            if span is not None and float(span) > 200.0 and not p.get("radial"):
                found.append({"check": "fillet_over_180deg", "feature": fid, "span": span})
        if f.kind in ("hole", "pin"):
            d = float(p.get("diameter", 0.0))
            if d > extent:
                found.append(
                    {"check": "diameter_larger_than_body", "feature": fid, "kind": f.kind, "d": d}
                )
            if d < 0.5:
                found.append({"check": "tiny_diameter", "feature": fid, "kind": f.kind, "d": d})
        # Mini-Merkmale mit ganz wenigen Dreiecken
        if f.kind not in ("face", "edge_loop") and len(f.face_indices) <= 2:
            found.append(
                {
                    "check": "very_few_faces",
                    "feature": fid,
                    "kind": f.kind,
                    "faces": len(f.face_indices),
                }
            )
        # Unendliche/NaN-Werte
        for key, value in p.items():
            if isinstance(value, float) and not math.isfinite(value):
                found.append({"check": "non_finite_param", "feature": fid, "param": key})
            v = _vec(value)
            if v is not None and not np.all(np.isfinite(v)):
                found.append({"check": "non_finite_param", "feature": fid, "param": key})

    # 4. Koaxiale Bohrungen mit gleichem Durchmesser, die sich auf der Achse berühren → eine Bohrung in Stücken?
    holes = [(fid, f) for fid, f in features.items() if f.kind == "hole"]
    for i, (fa, a) in enumerate(holes):
        ca, xa = _vec(a.params.get("centre")), _vec(a.params.get("axis"))
        if ca is None or xa is None:
            continue
        for fb, b in holes[i + 1 :]:
            cb, xb = _vec(b.params.get("centre")), _vec(b.params.get("axis"))
            if cb is None or xb is None:
                continue
            if abs(abs(float(np.dot(xa, xb))) - 1.0) > 1e-3:
                continue
            da, db = float(a.params.get("diameter", 0)), float(b.params.get("diameter", 0))
            if abs(da - db) > 0.02 * max(da, 1e-9):
                continue
            offset = cb - ca
            lateral = float(np.linalg.norm(offset - np.dot(offset, xa) * xa))
            if lateral > 0.05:
                continue
            gap = abs(float(np.dot(offset, xa))) - 0.5 * (
                float(a.params.get("depth", 0)) + float(b.params.get("depth", 0))
            )
            if gap < 0.5:
                found.append(
                    {
                        "check": "coaxial_same_bore_split",
                        "features": [fa, fb],
                        "d": da,
                        "gap": round(gap, 3),
                    }
                )
    return found


def main() -> int:
    path = Path(sys.argv[1])
    out = Path(sys.argv[2])
    report: dict = {"file": path.name, "bytes": path.stat().st_size, "bodies": [], "errors": []}
    t0 = time.perf_counter()
    try:
        payload = path.read_bytes()
        project = new_project("centauri-carbon-2", "petg")
        document = project.document
        document.sources["src_1"] = Source(
            id="src_1", kind="import", path=f"sources/{path.name}", sha256=""
        )
        project.sources["src_1"] = payload
        plan = import_plan("src_1", path.name, payload, unit="auto", first_model=True)
        report["plan"] = {
            "op": plan.draft.op,
            "produces": plan.draft.produces,
            "asks_unit": plan.asks_unit,
        }
        History(document).apply("Laden", [plan.draft])
        profile = profiles.make_profile("centauri-carbon-2", "petg")
        t1 = time.perf_counter()
        result = evaluate(document, profile, sources=ProjectSources(project), ask=_ask)
        report["load_seconds"] = round(time.perf_counter() - t1, 2)
        report["complete"] = result.complete
        report["stopped_at"] = result.stopped_at
        report["answers"] = {str(k): dict(v) for k, v in result.answers.items()}
        report["findings"] = [
            {
                "code": f.code,
                "severity": f.severity,
                "object": str(f.object_id) if getattr(f, "object_id", None) else None,
                "values": {
                    k: (v if isinstance(v, (int, float, str, bool)) else str(v))
                    for k, v in (f.values or {}).items()
                },
            }
            for f in result.scene.report.findings
        ]
        for oid, entry in result.scene.objects.items():
            mesh = entry.mesh
            size = np.asarray(mesh.bounds.maximum) - np.asarray(mesh.bounds.minimum)
            body: dict = {
                "id": oid,
                "name": str(entry.name),
                "triangles": mesh.triangle_count,
                "watertight": bool(mesh.is_watertight),
                "components": mesh.component_count,
                "volume": round(float(mesh.volume), 2),
                "size": [round(float(s), 2) for s in size],
                "slots": len(entry.material_slots),
            }
            features = entry.features
            body["feature_count"] = len(features)
            body["kinds"] = dict(Counter(f.kind for f in features.values()))
            try:
                body["freeform_dropped"] = freeform_dropped(mesh)
            except Exception as error:
                body["freeform_dropped"] = f"error: {error}"
            body["features"] = []
            for fid, f in features.items():
                line = _feature_line(fid, f)
                item = {
                    "id": fid,
                    "kind": f.kind,
                    "line": line,
                    "faces": len(f.face_indices),
                    "params": {
                        k: (
                            round(v, 4)
                            if isinstance(v, float)
                            else (list(np.round(v, 4)) if _vec(v) is not None else v)
                        )
                        for k, v in f.params.items()
                        if k != "face_indices"
                    },
                }
                body["features"].append(item)
            body["checks"] = _checks(entry, features)
            # Handlungsliste
            t2 = time.perf_counter()
            actions: dict = {}
            reasons: Counter = Counter()
            try:
                for fid, f in features.items():
                    if f.kind in ("face", "edge_loop"):
                        continue
                    rows = actions_for(f, features, mesh=mesh)
                    actions[fid] = [
                        {
                            "title": str(r.title),
                            "op": r.op,
                            "reason": str(r.reason) if r.reason else None,
                        }
                        for r in rows
                    ]
                    for r in rows:
                        if r.op is None and r.reason:
                            reasons[(f.kind, str(r.title), str(r.reason)[:80])] += 1
            except Exception as error:
                body["actions_error"] = f"{type(error).__name__}: {error}"
            body["actions"] = actions
            body["greyed_reasons"] = [
                {"kind": k, "title": t, "reason": r, "count": c}
                for (k, t, r), c in reasons.most_common()
            ]
            body["actions_seconds"] = round(time.perf_counter() - t2, 2)
            # Ketten und Rohrwände
            try:
                chains = relations.cavity_chains(features, mesh)
                body["cavity_chains"] = [[f.id for f in chain] for chain in chains]
            except Exception as error:
                body["cavity_chains"] = f"error: {error}"
            try:
                sleeves = relations.sleeves_of(features)
                body["sleeves"] = {
                    fid: {
                        "bore": s.bore,
                        "wall": s.wall,
                        "bore_d": round(float(s.bore_diameter), 3),
                        "outer_d": round(float(s.outer_diameter), 3),
                        "travel": round(float(s.bore_travel), 3),
                    }
                    for fid, s in sleeves.items()
                }
            except Exception as error:
                body["sleeves"] = f"error: {error}"
            report["bodies"].append(body)
    except Exception as error:
        report["errors"].append(f"{type(error).__name__}: {error}\n{traceback.format_exc()}")
    report["total_seconds"] = round(time.perf_counter() - t0, 2)
    report["peak_rss_mb"] = _peak_rss_mb()
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    print(
        f"{path.name}: bodies={len(report['bodies'])} errors={len(report['errors'])} {report['total_seconds']}s"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
