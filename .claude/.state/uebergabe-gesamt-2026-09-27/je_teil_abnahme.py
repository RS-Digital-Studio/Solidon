"""Abnahme Stufe E (RM-281): Werte je Teil im echten Slicer.

Aufruf: python je_teil_abnahme.py <code-wurzel> <ausgabeordner> [slicer ...]

Der Minigolf-Auftrag (vier Schäfte Ø 25,7 × 200 mm, der Rumpf) und ein Pilz, der
ohne Stützen in die Luft druckt, auf einer Platte. Je Slicer zwei Läufe über
Solidons Weg (``einheit.plate_run`` = ``_prepare_plate`` und ``_SliceWorker``):

``hersteller``   die Grundlage des Herstellers allein, keine Übernahme;
``uebernommen``  jeder Vorschlag, den der Druckdialog anbietet
                 (``_AdviceWorker`` samt Teilenamen, ``einheit.offered``),
                 übernommen wie mit *Vorschläge übernehmen*.

Gemessen je Körper: Stütze und Rand in Metern Bahn, zugeordnet über die Lage im
G-Code (Mitte jeder Bahn in den Hüllquader eines Körpers plus Rand). Soll:
Stütze nur am Pilz, und die Ränder der übrigen wie beim Hersteller.
"""

from __future__ import annotations

import json
import math
import os
import re
import sys
import time
from dataclasses import replace
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
TREE = sys.argv[1]
TARGET = Path(sys.argv[2])
CHOSEN = sys.argv[3:] or ["elegoo", "prusa", "cura"]
MODEL = r"F:\3D Druck\output\review\minigolf-2026-09-27\druckauftrag\solidon-0936.3mf"
sys.argv = [sys.argv[0], TREE, MODEL, str(TARGET), "heim"]
sys.path.insert(0, str(HERE))
os.environ["GESAMT_AUSRICHTEN"] = "0"

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # RM-530: Matrix in tools/
from tools import matrix_unit as einheit  # noqa: E402
import trimesh  # noqa: E402

from app.core.export import manufacturer  # noqa: E402
from app.core.geom.mesh import MeshData, as_mesh_data  # noqa: E402
from app.core.knowledge import profiles  # noqa: E402
from app.core.slice import advise  # noqa: E402
from app.core.types import SceneObject  # noqa: E402
from app.ui.print_settings_dialog import _AdviceWorker, _TargetedAdvice  # noqa: E402

from tools.matrix_gcode import TYPE_MARK, kind_of  # noqa: E402

WORD = re.compile(r"([XYZEF])(-?[\d.]+)")
#: So weit neben dem Hüllquader zählt eine Bahn noch zum Körper (Rand, Stütze).
MARGIN = 12.0


def mushroom() -> SceneObject:
    """Stiel 10 × 10 × 20, Hut 40 × 40 × 3, 15 mm frei auskragend — bei (60, -40)."""
    stem = trimesh.creation.box(extents=(10.0, 10.0, 20.0))
    stem.apply_translation((60.0, -40.0, 10.0))
    cap = trimesh.creation.box(extents=(40.0, 40.0, 3.0))
    cap.apply_translation((60.0, -40.0, 21.5))
    return SceneObject(id="obj_pilz", name="Pilz", mesh=MeshData.of(trimesh.boolean.union([stem, cap])))


def advice_rows(objects: list[Any], settings: Any, profile: Any, setup: Any) -> list[Any]:
    """Was der Druckdialog anbietet, mit den Teilen je Zeile."""
    worker = _AdviceWorker(
        tuple(objects), settings, profile, setup, {}, (), advise.connector_diameters(objects), {},
        flavour=setup.flavour,
    )
    got: list[list[Any]] = []
    failed: list[Any] = []
    worker.done.connect(lambda entries, _results: got.append(entries))
    worker.failed.connect(failed.append)
    worker.work()
    if failed:
        raise RuntimeError(str(failed[0]))
    return [entry for entry in got[0] if einheit.offered(entry, setup.flavour)]


def per_body(gcode: Path, objects: list[Any]) -> dict[str, Any]:
    """Stütze und Rand je Körper in Metern Bahn, dazu was keinem zuzuordnen war."""
    boxes = {}
    for entry in objects:
        bounds = as_mesh_data(entry.mesh).bounds
        boxes[str(entry.name)] = (bounds.minimum[0], bounds.minimum[1], bounds.maximum[0], bounds.maximum[1])
    segments: list[tuple[str, float, float, float]] = []
    kind = "?"
    x = y = e = 0.0
    relative = False
    with gcode.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            mark = TYPE_MARK.match(line)
            if mark:
                kind = kind_of(mark.group("type"))
                continue
            code = line.split(";", 1)[0].strip()
            if not code:
                continue
            if code.startswith("M83"):
                relative = True
            elif code.startswith("M82"):
                relative = False
            elif code.startswith("G92"):
                words = dict(WORD.findall(code))
                if "E" in words:
                    e = float(words["E"])
            elif code.startswith(("G0", "G1", "G2", "G3")):
                words = dict(WORD.findall(code))
                nx = float(words.get("X", x))
                ny = float(words.get("Y", y))
                pushed = 0.0
                if "E" in words:
                    value = float(words["E"])
                    pushed = value if relative else value - e
                    if not relative:
                        e = value
                if pushed > 0.0 and (nx != x or ny != y):
                    segments.append((kind, (x + nx) / 2.0, (y + ny) / 2.0, math.hypot(nx - x, ny - y)))
                x, y = nx, ny
    # Die Lage des Betts: Mitte der Modellbahnen gegen die Mitte der Körper.
    model = [(sx, sy) for kind_, sx, sy, _length in segments if kind_ == "model"]
    if not model:
        return {"error": "keine Modellbahn"}
    gx = (min(p[0] for p in model) + max(p[0] for p in model)) / 2.0
    gy = (min(p[1] for p in model) + max(p[1] for p in model)) / 2.0
    sx0 = (min(b[0] for b in boxes.values()) + max(b[2] for b in boxes.values())) / 2.0
    sy0 = (min(b[1] for b in boxes.values()) + max(b[3] for b in boxes.values())) / 2.0
    dx, dy = gx - sx0, gy - sy0
    totals: dict[str, dict[str, float]] = {}
    for kind_, sx, sy, length in segments:
        if kind_ not in ("support", "rim"):
            continue
        px, py = sx - dx, sy - dy
        owner = "keinem"
        best = math.inf
        for name, (x0, y0, x1, y1) in boxes.items():
            if x0 - MARGIN <= px <= x1 + MARGIN and y0 - MARGIN <= py <= y1 + MARGIN:
                distance = math.hypot(px - (x0 + x1) / 2.0, py - (y0 + y1) / 2.0)
                if distance < best:
                    best, owner = distance, name
        totals.setdefault(owner, {}).setdefault(kind_, 0.0)
        totals[owner][kind_] += length
    return {
        "offset": [round(dx, 1), round(dy, 1)],
        "bodies": {
            name: {kind_: round(value / 1000.0, 2) for kind_, value in sorted(kinds.items())}
            for name, kinds in sorted(totals.items())
        },
    }


def run(slicer: str) -> dict[str, Any]:
    printer = einheit.HOME[slicer]
    profile = profiles.make_profile(printer, einheit.MATERIAL)
    setup, info = einheit.prepared(slicer, profile)
    if setup is None:
        return {"slicer": slicer, "skip": info.get("skip")}
    foundation = manufacturer.base_settings(profile, "standard", setup)
    settings = manufacturer.effective(None, foundation)
    objects, _findings = einheit.load(Path(MODEL))
    objects = [*objects, mushroom()]
    started = time.perf_counter()
    rows = advice_rows(objects, settings, profile, setup)
    shown = [
        {
            "path": entry.path,
            "was": str(entry.was),
            "value": str(entry.value),
            "parts": list(entry.parts) if isinstance(entry, _TargetedAdvice) else [],
            "slot": bool(isinstance(entry, _TargetedAdvice) and entry.slot is not None),
        }
        for entry in rows
    ]
    plate_rows = [e for e in rows if not (isinstance(e, _TargetedAdvice) and e.slot is not None)]
    accepted = advise.apply(settings, plate_rows)
    result: dict[str, Any] = {
        "slicer": slicer,
        "printer": printer,
        "process": setup.base_process,
        "advice": shown,
        "advice_seconds": round(time.perf_counter() - started, 1),
    }
    for variant, chosen in (("hersteller", settings), ("uebernommen", accepted)):
        folder = TARGET / slicer / variant
        row = einheit.plate_run(objects, 0, chosen, profile, setup, folder, "abnahme")
        entry: dict[str, Any] = {
            key: row.get(key)
            for key in ("ok", "error", "detail", "print_minutes", "filament_g", "keep_arrangement", "export_findings", "seconds")
        }
        if row.get("ok"):
            entry["per_body"] = per_body(Path(row["gcode"]), objects)
            entry["gcode"] = row["gcode"]
        result[variant] = entry
    return result


def main() -> None:
    TARGET.mkdir(parents=True, exist_ok=True)
    results = []
    for slicer in CHOSEN:
        try:
            outcome = run(slicer)
        except Exception as problem:  # noqa: BLE001 — eine Abnahme berichtet alles
            outcome = {"slicer": slicer, "error": f"{type(problem).__name__}: {problem}"[:500]}
        results.append(outcome)
        print(json.dumps(outcome, ensure_ascii=False)[:4000], flush=True)
    (TARGET / "ergebnis.json").write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
