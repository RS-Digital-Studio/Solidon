"""Phase 2: Merkmalsoperationen an jedem Körper einer Datei, jede einzeln, mit Undo.

Aufruf: probe_ops.py <datei> <ausgabe.json> [max_je_art]
Je Körper und Merkmalsart werden bis zu N Merkmale genommen und die passenden
Operationen einzeln gefahren: Ergebnis vollständig? dicht? Volumen in der
erwarteten Richtung? Merkmal danach wiedergefunden und mit dem Sollmaß?
"""
# ruff: noqa: E501  -- Sonde: lange Ausgabezeilen sind hier Absicht

from __future__ import annotations

import json
import sys
import time
import traceback
from collections import Counter
from pathlib import Path

import numpy as np

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()

from app.core.ingest.plan import import_plan  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.perceive.actions import actions_for  # noqa: E402
from app.core.scene import History, OperationDraft, evaluate  # noqa: E402
from app.core.scene.cache import ResultCache  # noqa: E402
from app.core.scene.project import ProjectSources, new_project  # noqa: E402
from app.core.types import Source  # noqa: E402

MAX_PER_KIND = int(sys.argv[3]) if len(sys.argv) > 3 else 2
MAX_TRIANGLES_FOR_OPS = 1_500_000


def _ask(question: str, choices: list[str]) -> str:
    for choice in choices:
        if choice == "mm":
            return choice
    return choices[0]


def _v(value) -> np.ndarray:
    return np.asarray([float(x) for x in value])


def _perp(axis: np.ndarray) -> np.ndarray:
    axis = axis / np.linalg.norm(axis)
    trial = np.array([1.0, 0.0, 0.0]) if abs(axis[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    perp = np.cross(axis, trial)
    return perp / np.linalg.norm(perp)


def _kinds(features) -> dict:
    return dict(Counter(f.kind for f in features.values()))


def _nearest(features, kind: str, centre: np.ndarray):
    best, best_d = None, float("inf")
    for fid, f in features.items():
        if f.kind != kind:
            continue
        c = f.params.get("centre")
        if c is None:
            continue
        d = float(np.linalg.norm(_v(c) - centre))
        if d < best_d:
            best, best_d = (fid, f), d
    return best, best_d


def _plans(fid: str, feature, features, mesh) -> list[dict]:
    """Welche Operationen an diesem Merkmal probiert werden, mit Sollwerten."""
    p = feature.params
    kind = feature.kind
    plans: list[dict] = []
    centre = _v(p["centre"]) if p.get("centre") is not None else None
    axis = _v(p["axis"]) if p.get("axis") is not None else None
    offered = {row.op for row in actions_for(feature, features, mesh=mesh) if row.op}
    d = float(p.get("diameter", 0.0) or 0.0)
    r = float(p.get("radius", 0.0) or 0.0)
    size = np.asarray(mesh.bounds.maximum) - np.asarray(mesh.bounds.minimum)
    step = max(0.5, min(2.0, 0.02 * float(np.max(size))))

    if kind in ("hole", "slot") and "resize_hole" in offered and d > 0:
        plans.append(
            {
                "op": "resize_hole",
                "params": {"at_feature": fid, "diameter": round(d + 1.0, 3)},
                "expect": {"volume": "smaller", "kind": kind, "diameter": round(d + 1.0, 3)},
            }
        )
        if d > 1.5:
            plans.append(
                {
                    "op": "resize_hole",
                    "params": {"at_feature": fid, "diameter": round(d * 0.8, 3)},
                    "expect": {"volume": "larger", "kind": kind, "diameter": round(d * 0.8, 3)},
                }
            )
    if kind in ("pin", "cone", "sphere", "fillet") and "resize_feature" in offered:
        measure = d if kind != "fillet" else 2.0 * r
        if measure > 0:
            plans.append(
                {
                    "op": "resize_feature",
                    "params": {"at_feature": fid, "diameter": round(measure + 1.0, 3)},
                    "expect": {"kind": kind, "diameter": round(measure + 1.0, 3)},
                }
            )
    if "move_feature" in offered and centre is not None:
        direction = _perp(axis) if axis is not None else np.array([1.0, 0.0, 0.0])
        target = centre + step * direction
        params = {
            "at_feature": fid,
            "x": float(target[0]),
            "y": float(target[1]),
            "z": float(target[2]),
        }
        plans.append(
            {
                "op": "move_feature",
                "params": params,
                "expect": {"volume": "same", "kind": kind, "centre": [float(t) for t in target]},
            }
        )
    if "duplicate_feature" in offered and centre is not None:
        direction = _perp(axis) if axis is not None else np.array([1.0, 0.0, 0.0])
        target = centre + max(step, d * 1.5 if d else step) * direction
        params = {
            "at_feature": fid,
            "x": float(target[0]),
            "y": float(target[1]),
            "z": float(target[2]),
        }
        plans.append(
            {"op": "duplicate_feature", "params": params, "expect": {"kind": kind, "count": +1}}
        )
    if "remove_feature" in offered:
        plans.append(
            {
                "op": "remove_feature",
                "params": {"at_feature": fid, "sections": "chain"},
                "expect": {
                    "kind": kind,
                    "count": -1,
                    "volume": "larger"
                    if kind in ("hole", "slot", "cone", "void") and p.get("recess", True)
                    else None,
                },
            }
        )
    if "rotate_feature" in offered and axis is not None:
        # Um eine Weltachse quer zur Merkmalsachse, kleiner Winkel
        world = min(("x", "y", "z"), key=lambda a: abs(axis["xyz".index(a)]))
        plans.append(
            {
                "op": "rotate_feature",
                "params": {"at_feature": fid, "axis": world, "angle": 15.0},
                "expect": {"kind": kind},
            }
        )
    if kind == "hole" and "slot_hole" in offered and d > 0:
        plans.append(
            {
                "op": "slot_hole",
                "params": {"at_feature": fid, "slot_length": round(d * 2.0, 3), "slot_angle": 0.0},
                "expect": {"kind": "slot", "count_slot": +1, "count_hole": -1, "volume": "smaller"},
            }
        )
    return plans


def main() -> int:
    path = Path(sys.argv[1])
    out = Path(sys.argv[2])
    report: dict = {"file": path.name, "bodies": [], "errors": []}
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
        history = History(document)
        history.apply("Laden", [plan.draft])
        profile = profiles.make_profile("centauri-carbon-2", "petg")
        cache = ResultCache()
        sources = ProjectSources(project)
        base = evaluate(document, profile, sources=sources, ask=_ask, cache=cache)
        report["complete"] = base.complete
        if not base.complete:
            report["errors"].append(f"load stopped at {base.stopped_at}")
        for oid, entry in base.scene.objects.items():
            mesh = entry.mesh
            body: dict = {
                "id": oid,
                "name": str(entry.name),
                "triangles": mesh.triangle_count,
                "watertight": bool(mesh.is_watertight),
                "kinds": _kinds(entry.features),
                "ops": [],
            }
            if mesh.triangle_count > MAX_TRIANGLES_FOR_OPS:
                body["skipped"] = "zu viele Dreiecke für den Operationslauf"
                report["bodies"].append(body)
                continue
            taken: Counter = Counter()
            for fid, feature in entry.features.items():
                if feature.kind in ("face", "edge_loop", "curved_face", "thread", "void"):
                    continue
                if taken[feature.kind] >= MAX_PER_KIND:
                    continue
                taken[feature.kind] += 1
                for step in _plans(fid, feature, entry.features, mesh):
                    record: dict = {"feature": fid, "kind": feature.kind, "line": None, **step}
                    t1 = time.perf_counter()
                    try:
                        history.apply(
                            step["op"],
                            [
                                OperationDraft(
                                    op=step["op"],
                                    inputs=(oid,),
                                    outputs=(oid,) if step["op"] != "duplicate_feature" else None,
                                    params=step["params"],
                                )
                            ],
                        )
                        result = evaluate(document, profile, sources=sources, ask=_ask, cache=cache)
                        record["complete"] = result.complete
                        record["seconds"] = round(time.perf_counter() - t1, 2)
                        new_findings = [
                            {
                                "code": f.code,
                                "severity": f.severity,
                                "message": str(f.message)[:200],
                                "values": {k: str(v)[:80] for k, v in (f.values or {}).items()},
                            }
                            for f in result.scene.report.findings
                            if f.op_id is not None and f.op_id not in base.completed
                        ]
                        record["findings"] = new_findings
                        after = result.scene.objects.get(oid)
                        if after is None:
                            record["problem"] = "Körper nach der Operation nicht mehr da"
                        else:
                            record["watertight"] = bool(after.mesh.is_watertight)
                            record["components"] = [
                                mesh.component_count,
                                after.mesh.component_count,
                            ]
                            record["triangles_after"] = after.mesh.triangle_count
                            dv = float(after.mesh.volume) - float(mesh.volume)
                            record["volume_delta"] = round(dv, 3)
                            record["volume_rel"] = (
                                round(dv / float(mesh.volume), 5) if mesh.volume else None
                            )
                            record["kinds_after"] = _kinds(after.features)
                            expect = step["expect"]
                            problems: list[str] = []
                            if result.complete:
                                if not after.mesh.is_watertight and mesh.is_watertight:
                                    problems.append("Körper danach undicht")
                                if after.mesh.component_count != mesh.component_count:
                                    problems.append(
                                        f"Komponenten {mesh.component_count}→{after.mesh.component_count}"
                                    )
                                want = expect.get("volume")
                                if want == "smaller" and dv > -1e-6:
                                    problems.append("Volumen nicht kleiner")
                                if want == "larger" and dv < 1e-6:
                                    problems.append("Volumen nicht größer")
                                if want == "same" and abs(dv) > 0.02 * float(mesh.volume):
                                    problems.append(f"Volumen um {dv / mesh.volume:.1%} geändert")
                                kind = expect.get("kind", feature.kind)
                                before_n = body["kinds"].get(feature.kind, 0)
                                after_n = record["kinds_after"].get(feature.kind, 0)
                                if "count" in expect and after_n != before_n + expect["count"]:
                                    problems.append(
                                        f"Anzahl {feature.kind}: {before_n}→{after_n}, erwartet {before_n + expect['count']}"
                                    )
                                if "count_slot" in expect:
                                    if (
                                        record["kinds_after"].get("slot", 0)
                                        != body["kinds"].get("slot", 0) + 1
                                    ):
                                        problems.append("kein neues Langloch")
                                    if (
                                        record["kinds_after"].get("hole", 0)
                                        != body["kinds"].get("hole", 0) - 1
                                    ):
                                        problems.append("Bohrung nicht verschwunden")
                                if (
                                    "count" not in expect
                                    and "count_slot" not in expect
                                    and after_n != before_n
                                ):
                                    problems.append(f"Anzahl {feature.kind}: {before_n}→{after_n}")
                                # Das bearbeitete Merkmal wiederfinden
                                survivor = after.features.get(fid)
                                record["id_survives"] = survivor is not None
                                if step["op"] == "slot_hole":
                                    survivor = None
                                    wanted_centre = _v(feature.params["centre"])
                                    hit, dist = _nearest(after.features, "slot", wanted_centre)
                                    if hit is not None and dist < 1.0:
                                        survivor = hit[1]
                                        record["slot_after"] = {
                                            k: (round(v, 3) if isinstance(v, float) else v)
                                            for k, v in hit[1].params.items()
                                            if k in ("diameter", "length", "through")
                                        }
                                    else:
                                        problems.append("Langloch nicht an der Stelle gefunden")
                                if survivor is None and step["op"] not in (
                                    "remove_feature",
                                    "slot_hole",
                                ):
                                    # Vielleicht an der neuen Mitte unter neuem Namen
                                    target_c = expect.get("centre") or feature.params.get("centre")
                                    if target_c is not None:
                                        hit, dist = _nearest(after.features, kind, _v(target_c))
                                        if hit is not None and dist < 0.5:
                                            survivor = hit[1]
                                            record["renamed_to"] = hit[0]
                                            problems.append(f"Kennung verloren: {fid}→{hit[0]}")
                                        else:
                                            problems.append("Merkmal danach nicht wiedergefunden")
                                if survivor is not None:
                                    sp = survivor.params
                                    if "diameter" in expect:
                                        got = (
                                            float(sp.get("diameter", 0.0))
                                            if kind != "fillet"
                                            else 2.0 * float(sp.get("radius", 0.0))
                                        )
                                        record["diameter_after"] = round(got, 4)
                                        if (
                                            abs(got - expect["diameter"])
                                            > 0.05 + 0.01 * expect["diameter"]
                                        ):
                                            problems.append(
                                                f"Maß danach {got:.3f} statt {expect['diameter']:.3f}"
                                            )
                                    if "centre" in expect and sp.get("centre") is not None:
                                        dist = float(
                                            np.linalg.norm(_v(sp["centre"]) - _v(expect["centre"]))
                                        )
                                        record["centre_error"] = round(dist, 4)
                                        if dist > 0.1:
                                            problems.append(
                                                f"Mitte danach {dist:.3f} mm neben dem Ziel"
                                            )
                                if step["op"] == "remove_feature" and fid in after.features:
                                    problems.append("Merkmal nach Entfernen noch da")
                            else:
                                stop = [
                                    f
                                    for f in result.scene.report.findings
                                    if f.op_id == result.stopped_at
                                ]
                                record["stopped_message"] = [str(f.message)[:300] for f in stop][:3]
                                record["stopped_values"] = [
                                    {k: str(v)[:100] for k, v in (f.values or {}).items()}
                                    for f in stop
                                ][:3]
                            record["problems"] = problems
                    except Exception as error:
                        record["exception"] = f"{type(error).__name__}: {str(error)[:400]}"
                        record["trace"] = traceback.format_exc()[-1500:]
                        record["seconds"] = round(time.perf_counter() - t1, 2)
                    finally:
                        if history.can_undo and len(document.transactions) > 1:
                            history.undo()
                    body["ops"].append(record)
            report["bodies"].append(body)
    except Exception as error:
        report["errors"].append(f"{type(error).__name__}: {error}\n{traceback.format_exc()}")
    report["total_seconds"] = round(time.perf_counter() - t0, 2)
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    n_ops = sum(len(b["ops"]) for b in report["bodies"])
    n_bad = sum(
        1
        for b in report["bodies"]
        for o in b["ops"]
        if o.get("problems") or o.get("exception") or o.get("complete") is False
    )
    print(
        f"{path.name}: bodies={len(report['bodies'])} ops={n_ops} auffällig={n_bad} errors={len(report['errors'])} {report['total_seconds']}s"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
