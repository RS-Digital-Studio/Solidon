"""Feine Schichten durch die echten Slicer: Übergabe, Kurve in der 3MF, Schichthöhen im G-Code.

Aufruf (aus dem Worktree): python slicer_fein.py <code-wurzel> <modell> <ausgabe> <kombis> [erzwingen]

``<modell>`` ist eine Datei oder ``paar``: die Messplatte aus RM-586, eine Halbkugel R 20
(Ikosphäre, fünf Teilungen) 40 mm neben einem Klotz 20 × 20 × 20 mm.

``<kombis>`` ``slicer:drucker,…`` (Slicer wie ``tools/matrix_config.SLICERS``, dazu
``anycubic`` für Anycubic Slicer Next) oder ``heim``. Je Kombination der Weg des
Druckdialogs (Vorwahl, Grundlage, Rat über ``_AdviceWorker``, ``offered``), zwei Läufe:
``standard`` und ``fein`` — nur die Vorschläge zu feinen Schichten und der
Deckschichtdicke übernommen. ``erzwingen`` setzt die feine Höhe auch dort, wo kein Rat
kommt (Cura), um zu sehen, was das Programm dann tut.

Gemessen aus dem G-Code, nur Modellbahnen (Art aus ``;TYPE:``/``; FEATURE:``): die Höhen
der Schichten (Abstand zur Modellschicht darunter), feine Bereiche, die höchste Lage mit
dünner Füllung (Deckschichtdicke). Liegen mehrere Körper nebeneinander, je Körper getrennt
nach der Lage in x (größte Lücke). Dazu Kurve in der 3MF, Befunde, Druckzeit, Anteil.
"""
# ruff: noqa: E501

from __future__ import annotations

import json
import os
import re
import sys
import time
import zipfile
from array import array
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
MODEL = Path(sys.argv[2]).resolve()
OUT = Path(sys.argv[3]).resolve()
SPEC = sys.argv[4]
FORCE = len(sys.argv) > 5 and sys.argv[5] == "erzwingen"
os.environ.setdefault("GESAMT_AUSRICHTEN", "0")
os.environ.setdefault("GESAMT_BEHALTEN", "1")

sys.argv = [str(ROOT / "tools" / "matrix_unit.py"), str(ROOT), str(MODEL), str(OUT), "heim"]
sys.path.insert(0, str(ROOT))
from tools import matrix_unit as mu  # noqa: E402

assert Path(mu.app.__file__).resolve().is_relative_to(ROOT), mu.app.__file__

from app.core.export import manufacturer, threemf  # noqa: E402
from app.core.knowledge import print_settings, profiles  # noqa: E402
from app.core.slice import advise, fine_layers  # noqa: E402

mu.SLICERS["anycubic"] = r"C:\Program Files\AnycubicSlicerNext\AnycubicSlicerNext.exe"
mu.HOME["anycubic"] = "anycubic-kobra-2"
FINE_PATHS = {"layers.fine_layer_height", "shell.top_thickness"}
MODEL_TYPES = re.compile(
    r"wall|perimeter|infill|surface|bridge|gap|solid|skin|fill|ironing", re.IGNORECASE
)
OTHER_TYPES = re.compile(r"support|skirt|brim|prime|wipe|tower|purge|flush", re.IGNORECASE)
SPARSE_TYPES = re.compile(r"^(sparse infill|internal infill|fill)$", re.IGNORECASE)
NUMBER = re.compile(r"([XYZE])(-?\d*\.?\d+)")


def read_extrusions(path: Path) -> tuple[array, array, array, array]:
    """Die Modellbahnen: je Extrusion x, y, z und ob sie dünne Füllung ist."""
    absolute = True
    last_e = 0.0
    x = y = z = 0.0
    model = sparse = False
    xs, ys, zs, flags = array("d"), array("d"), array("d"), array("b")
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            first = line[:1]
            if first == ";":
                kind = None
                if line.startswith(";TYPE:"):
                    kind = line[6:].strip()
                elif line.startswith("; FEATURE:"):
                    kind = line[10:].strip()
                if kind is not None:
                    model = bool(MODEL_TYPES.search(kind)) and not OTHER_TYPES.search(kind)
                    sparse = bool(SPARSE_TYPES.match(kind))
                continue
            if first == "M":
                if line.startswith("M82"):
                    absolute = True
                elif line.startswith("M83"):
                    absolute = False
                continue
            if first != "G":
                continue
            if line.startswith("G92"):
                match = re.search(r"\bE(-?[\d.]+)", line)
                if match:
                    last_e = float(match.group(1))
                continue
            if not line.startswith(("G0", "G1", "G2", "G3")) or line[2:3] not in (" ", "\t"):
                continue
            code = line.split(";", 1)[0]
            e_value = None
            for letter, value in NUMBER.findall(code):
                if letter == "X":
                    x = float(value)
                elif letter == "Y":
                    y = float(value)
                elif letter == "Z":
                    z = float(value)
                elif letter == "E":
                    e_value = float(value)
            if e_value is None:
                continue
            extruding = e_value > 1e-6 if not absolute else e_value > last_e + 1e-6
            if absolute:
                last_e = e_value
            if extruding and model:
                xs.append(x)
                ys.append(y)
                zs.append(z)
                flags.append(1 if sparse else 0)
    return xs, ys, zs, flags


def layer_stats(zs: list[float], sparse_z: list[float]) -> dict:
    ordered = sorted({round(value, 3) for value in zs})
    layers = [(value, round(value - (ordered[i - 1] if i else 0.0), 3)) for i, value in enumerate(ordered)]
    heights = [h for _z, h in layers[1:]]
    if not heights:
        return {"layers": len(layers)}
    normal = max(set(heights), key=heights.count)
    ranges: list[list[float]] = []
    for z, height in layers[1:]:
        if height < normal - 0.015:
            if ranges and z - height - ranges[-1][1] < 0.6:
                ranges[-1][1] = z
            else:
                ranges.append([round(z - height, 2), z])
    top = layers[-1][0]
    return {
        "layers": len(layers),
        "first": layers[0][0],
        "normal": normal,
        "smallest": min(heights),
        "fine_layers": sum(1 for h in heights if h < normal - 0.015),
        "fine_heights": sorted({h for h in heights if h < normal - 0.015}),
        "fine_ranges": ranges,
        "top_z": top,
        "sparse_top": _sparse_top(sparse_z),
    }


def _sparse_top(sparse_z: list[float]) -> float | None:
    """Die höchste Schicht, in der dünne Füllung nennenswert liegt: wenigstens ein
    Zehntel der mittleren Zahl an Bahnen je Schicht und drei (einzelne Krümel
    am Rand zählen nicht)."""
    from collections import Counter
    from statistics import median

    if not sparse_z:
        return None
    counts = Counter(round(value, 3) for value in sparse_z)
    floor = max(3.0, 0.1 * median(counts.values()))
    tops = [z for z, n in counts.items() if n >= floor]
    return max(tops) if tops else None


def per_body(xs: array, ys: array, zs: array, flags: array) -> list[dict]:
    """Die Bahnen nach Körpern getrennt: an der größten Lücke in x oder, wo keine
    über 3 mm ist, in y. Ohne Lücke ein Körper ("alle")."""
    if not xs:
        return []
    groups: list[tuple[array, float, str, str]] = []
    for axis, coords, names in (("x", xs, ("links", "rechts")), ("y", ys, ("vorn", "hinten"))):
        cells = sorted({round(value) for value in coords})
        gaps = [(b - a, a, b) for a, b in zip(cells, cells[1:], strict=False)]
        widest = max(gaps, default=(0, 0, 0))
        if widest[0] > 1:
            groups = [(coords, (widest[1] + widest[2]) / 2.0, names[0], names[1])]
            break
    found = []
    selections = (
        [("alle", list(range(len(xs))))]
        if not groups
        else [
            (groups[0][2], [i for i, value in enumerate(groups[0][0]) if value < groups[0][1]]),
            (groups[0][3], [i for i, value in enumerate(groups[0][0]) if value >= groups[0][1]]),
        ]
    )
    for name, chosen in selections:
        body_x = [xs[i] for i in chosen]
        body_y = [ys[i] for i in chosen]
        stats = layer_stats([zs[i] for i in chosen], [zs[i] for i in chosen if flags[i]])
        stats["name"] = name
        stats["size"] = [
            round(max(body_x) - min(body_x), 1) if body_x else 0.0,
            round(max(body_y) - min(body_y), 1) if body_y else 0.0,
        ]
        found.append(stats)
    return found


def curves_in(path: Path) -> dict[str, list[str]]:
    found: dict[str, list[str]] = {}
    if path.suffix != ".3mf" or not path.exists():
        return found
    with zipfile.ZipFile(path) as archive:
        for name in (threemf.ORCA_LAYER_HEIGHTS_PATH, threemf.PRUSA_LAYER_HEIGHTS_PATH):
            if name in archive.namelist():
                found[name] = archive.read(name).decode("utf-8").splitlines()
        settings = "Metadata/model_settings.config"
        if settings in archive.namelist():
            text = archive.read(settings).decode("utf-8")
            found["top_shell_thickness"] = re.findall(r'key="top_shell_thickness" value="([^"]*)"', text)
        prusa = threemf.PRUSA_MODEL_CONFIG_PATH
        if prusa in archive.namelist():
            text = archive.read(prusa).decode("utf-8")
            found["top_solid_min_thickness"] = re.findall(r'key="top_solid_min_thickness" value="([^"]*)"', text)
    return found


def _pair() -> list:
    """Kuppe und Klotz wie ``paar.3mf`` des Bauberichts RM-586."""
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.types import SceneObject

    sphere = trimesh.creation.icosphere(subdivisions=5, radius=20.0)
    floor = trimesh.creation.box(extents=(60.0, 60.0, 30.0))
    floor.apply_translation((0.0, 0.0, 15.0))
    dome = trimesh.boolean.intersection([sphere, floor], engine="manifold")
    block = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    block.apply_translation((40.0, 0.0, 10.0))
    return [
        SceneObject(id="kuppe", name="Kuppe", mesh=MeshData.of(dome), material="pla"),
        SceneObject(id="klotz", name="Klotz", mesh=MeshData.of(block), material="pla"),
    ]


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    objects = _pair() if MODEL.name == "paar" else mu.load(MODEL)[0]
    summary: list[dict] = []
    pairs = [tuple(item.split(":", 1)) for item in SPEC.split(",")] if SPEC != "heim" else [*mu.HOME.items()]
    for slicer, printer in pairs:
        entry: dict = {"slicer": slicer, "printer": printer}
        summary.append(entry)
        started = time.perf_counter()
        try:
            profile = profiles.make_profile(printer, "pla")
            setup, info = mu.prepared(slicer, profile)
            info.pop("_entries", None)
            entry.update({k: v for k, v in info.items() if isinstance(v, str)})
            if setup is None:
                continue
            quality = print_settings.resolve(profile).quality
            foundation = manufacturer.base_settings(profile, quality, setup)
            standard = manufacturer.effective(None, foundation)
            entry["layer_height"] = standard.layers.layer_height
            entry["top_layers"] = standard.shell.top_layers
            entry["top_thickness_profile"] = standard.shell.top_thickness
            entry["support_style"] = standard.support.style
            combo_objects, _arranged = mu.arranged_for(objects, profile, standard)
            advice_started = time.process_time()
            everything, _results = mu.advised(combo_objects, standard, profile, setup)
            entry["advice_cpu_s"] = round(time.process_time() - advice_started, 1)
            shown = mu.offered(everything, setup, info, foundation)
            chosen = [e for e in shown if e.path in FINE_PATHS]
            entry["advice"] = [[e.path, str(e.value), str(e.reason), list(getattr(e, "parts", ()))] for e in chosen]
            entry["advice_all"] = [[e.path, str(e.value)] for e in shown]
            entry["advice_hidden"] = [
                [e.path, str(e.value), str(e.reason)] for e in everything if e.path in FINE_PATHS and e not in shown
            ]
            fine_settings = advise.apply(standard, chosen) if chosen else None
            if fine_settings is None and FORCE:
                fine = fine_layers.fine_height(standard.layers.layer_height, profile.printer.nozzle_diameter) or 0.1
                fine_settings = print_settings.with_accepted(standard, "layers.fine_layer_height", fine)
                entry["forced"] = fine
            if fine_settings is not None and os.environ.get("SOLIDON_FEIN_DECKE"):
                fine_settings = print_settings.with_accepted(fine_settings, "shell.top_thickness", float(os.environ["SOLIDON_FEIN_DECKE"]))
                entry["forced_top"] = os.environ["SOLIDON_FEIN_DECKE"]
            variants = [("standard", standard)] + ([("fein", fine_settings)] if fine_settings is not None else [])
            if any(e.path == "shell.top_thickness" for e in chosen):
                # Ohne die Deckschichtdicke: zeigt, was sie allein bewirkt.
                variants.append(("nur_fein", advise.apply(standard, [e for e in chosen if e.path != "shell.top_thickness"])))
            entry["runs"] = {}
            for variant, settings in variants:
                plates = sorted({int(getattr(o, "plate", 0) or 0) for o in combo_objects})
                row = mu.plate_run(
                    combo_objects, plates[0], tuple(plates), settings, profile, setup,
                    OUT / "arbeit" / f"{slicer}__{printer}" / variant, MODEL.stem,
                )
                run = {
                    k: row.get(k)
                    for k in ("ok", "print_minutes", "printing_minutes", "estimated_minutes", "export_findings", "slice_findings", "title", "detail", "written", "gcode", "seconds")
                }
                run["warnings"] = row.get("warnings", [])
                run["curves"] = {k: [line[:300] for line in v] for k, v in curves_in(Path(str(row.get("written") or ""))).items()}
                gcode = Path(str(row.get("gcode") or ""))
                if row.get("ok") and gcode.exists():
                    xs, ys, zs, flags = read_extrusions(gcode)
                    run["all"] = layer_stats(list(zs), [zs[i] for i in range(len(zs)) if flags[i]])
                    run["bodies"] = per_body(xs, ys, zs, flags) if len(combo_objects) > 1 else []
                entry["runs"][variant] = run
            base = entry["runs"].get("standard", {}).get("print_minutes")
            fine_minutes = entry["runs"].get("fein", {}).get("print_minutes")
            if base and fine_minutes:
                entry["share"] = round(100.0 * (fine_minutes / base - 1.0), 1)
        except Exception as problem:  # noqa: BLE001
            import traceback

            entry["error"] = f"{type(problem).__name__}: {problem}"
            entry["trace"] = traceback.format_exc()[-1500:]
        entry["seconds"] = round(time.perf_counter() - started, 1)
        (OUT / "fein.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    for entry in summary:
        runs = entry.get("runs", {})
        std, fine = runs.get("standard", {}).get("all", {}), runs.get("fein", {}).get("all", {})
        print(
            f"{entry['slicer']:11} {entry['printer']:18} Rat {[a[:2] for a in entry.get('advice', [])]} "
            f"std {std.get('layers')} Sch. {runs.get('standard', {}).get('print_minutes')} min | fein {fine.get('layers')} Sch. "
            f"{runs.get('fein', {}).get('print_minutes')} min, Höhen {fine.get('fine_heights')} n={fine.get('fine_layers')} "
            f"Anteil {entry.get('share')} % Bereiche {fine.get('fine_ranges')} "
            f"{entry.get('error', '')} {runs.get('fein', {}).get('title') or ''} {runs.get('standard', {}).get('title') or ''}"
        )
        for variant in ("standard", "fein", "nur_fein"):
            for body in runs.get(variant, {}).get("bodies", []):
                print(f"    {variant:8} {body['name']:6} Größe {body['size']} Schichten {body.get('layers')} fein {body.get('fine_layers')} {body.get('fine_heights')} Bereiche {body.get('fine_ranges')} dünne Füllung bis {body.get('sparse_top')}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
