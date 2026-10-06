"""Ein Modell durch jeden installierten Slicer — so, wie der Kunde es drucken würde.

Auftrag Robert, 27.09.2026: „kontrolle dann über alle slicer und alle modelle
damit alles druckbar ist mit sinnvollen vorschlägen … schauen was jeder slicer
und jedes modell dann macht, wenn es drucken würde“. Kein Test, eine Messung.

Aufruf: python lauf.py <code-wurzel> <modell> <ausgabeordner> [slicer …]

``<code-wurzel>`` ist der Arbeitsbaum, dessen ``app`` gemessen wird. Geladen
wird wie ``solidon3d import``. Je Slicer (mit dem Drucker, für den sein
Hersteller ihn baut) entstehen bis zu vier Druckdateien:

``hersteller``           das Herstellerprofil allein — der Maßstab
``hersteller_stuetzen``  dasselbe mit eingeschalteten Stützen; nur, wenn Solidon
                         Stützen vorschlägt: Stützt der Slicer mit seinem
                         eigenen Urteil überhaupt etwas?
``standard``             Solidons Übergabe ohne Vorschläge
``vorschlaege``          mit allen Vorschlägen übernommen

Jede Datei wird gelesen (``gcode_lesen``), danach gelöscht. Fällt eine erste
Schicht gegen den Hersteller auf, liegt ein Bild daneben. Das Ergebnis ist eine
JSON-Datei je Modell, nach jedem Lauf neu geschrieben — zwei Prozesse teilen
sich keine Datei mehr.
"""
# ruff: noqa: E501

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import time
import traceback
import zipfile
from dataclasses import replace
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = Path(sys.argv[1]).resolve()
MODEL = Path(sys.argv[2]).resolve()
# Absolut: Der Slicer läuft in seinem eigenen Arbeitsordner, und ein relativer
# Pfad besteht jede Vorprüfung und scheitert erst dort („No such file“).
OUT = Path(sys.argv[3]).resolve()
ONLY = set(sys.argv[4:])
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(HERE))

import app  # noqa: E402
from app.core.bootstrap import load_operations  # noqa: E402

assert Path(app.__file__).resolve().is_relative_to(ROOT), app.__file__
load_operations()

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # RM-530: Matrix in tools/
from tools import matrix_gcode as gcode_lesen  # noqa: E402
from app.core.errors import AppError  # noqa: E402
from app.core.export import handover, slicer_profiles  # noqa: E402
from app.core.export.writer import write_assembly  # noqa: E402
from app.core.geom.mesh import as_mesh_data  # noqa: E402
from app.core.ingest.loader import detect_unit, read_local_payload, read_model  # noqa: E402
from app.core.ingest.plan import import_plan, names_in_use  # noqa: E402
from app.core.knowledge import print_settings, profiles  # noqa: E402
from app.core.scene import History, evaluate  # noqa: E402
from app.core.scene.project import (  # noqa: E402
    ProjectSources,
    embedded_source_path,
    new_project,
    next_source_id,
)
from app.core.slice import advise  # noqa: E402
from app.core.slice.analysis import slice_body  # noqa: E402
from app.core.types import Source  # noqa: E402

MATERIAL = "pla"
TIMEOUT = 45 * 60

#: Je Slicer der Drucker, für den sein Hersteller ihn baut — bei OrcaSlicer und
#: Cura einer, dessen Hersteller keinen eigenen Slicer liefert.
SLICERS: dict[str, tuple[str, str]] = {
    "elegoo": (r"C:\Program Files\ElegooSlicer\elegoo-slicer.exe", "centauri-carbon-2"),
    "bambu": (r"C:\Program Files\Bambu Studio\bambu-studio.exe", "bambu-p1s"),
    "creality": (r"C:\Program Files\Creality\Creality Print 7.2\CrealityPrint.exe", "creality-k1"),
    "orca": (r"C:\Program Files\OrcaSlicer\orca-slicer.exe", "anycubic-kobra-2"),
    "prusa": (r"C:\Program Files\Prusa3D\PrusaSlicer\prusa-slicer-console.exe", "prusa-mk4s"),
    "cura": (r"C:\Program Files\UltiMaker Cura 5.13.0\CuraEngine.exe", "sovol-sv06"),
}

#: Prusas Profile für den MK4S (vorgewählt, wie PrusaSlicer es tut; Prusa-Bericht §0).
PRUSA_VENDOR = ("Original Prusa MK4S HF0.4 nozzle", "0.20mm SPEED @MK4S HF0.4", "Prusament PLA @MK4S HF0.4")
PRUSA_BUNDLE = Path(r"C:\Program Files\Prusa3D\PrusaSlicer\resources\profiles\PrusaResearch.ini")

#: Curas Stapel für den SV06 (Cura-Bericht, Werkzeug ``compare.py``).
CURA_STACK = (
    "sovol_sv06",
    "sovol_planetary_extruder_0",
    "sovol/sovol_sv06_0.4.inst.cfg",
    "sovol/sovol_planetary_global_standard.inst.cfg",
    "generic_pla_175",
    "sovol/PLA/sovol_planetary_0.4_PLA_standard.inst.cfg",
)
CURA_RESOURCES = Path(r"C:\Program Files\UltiMaker Cura 5.13.0\share\cura\resources")

#: ``default_bed_type`` als Nummer führt nur Elegoo, und belegt ist nur „4":
#: alle 34 mit ElegooSlicer 1.5.x gespeicherten Centauri-Projekte tragen
#: „Textured PEI Plate" (27.09.2026). Die übrigen Hersteller schreiben den Namen.
PLATES = {"4": "Textured PEI Plate"}


def load(model: Path) -> list[Any]:
    project = new_project("centauri-carbon-2", MATERIAL)
    payload = read_local_payload(model)
    source_id = next_source_id(project.document.sources)
    project.document.sources[source_id] = Source(id=source_id, kind="import", path=embedded_source_path(model.name, source_id), sha256="")
    project.sources[source_id] = payload
    taken = names_in_use(project.document)
    plan = import_plan(source_id, model.name, payload, "auto", first_model=True, taken=taken)
    if plan.asks_unit:
        guess = detect_unit(read_model(payload, model.suffix).bounds.diagonal)
        plan = import_plan(source_id, model.name, payload, guess.unit or "mm", first_model=True, taken=taken)
    History(project.document).apply(plan.title, [plan.draft])
    result = evaluate(project.document, profiles.scene_profile("centauri-carbon-2", MATERIAL), sources=ProjectSources(project, base_dir=model.parent))
    return [entry for entry in result.scene.objects.values() if as_mesh_data(entry.mesh).triangle_count]


def advised(settings: Any, profile: Any, objects: list[Any]) -> tuple[Any, list]:
    """Wie der Druckdialog: je Körper schneiden, raten, zusammenführen, übernehmen."""
    process = profiles.for_process(profile, settings)
    angle, wall = process.overhang_limit_degrees, process.minimum_wall_thickness
    common = []
    for entry in objects:
        mesh = as_mesh_data(entry.mesh)
        result = slice_body(mesh, settings.layers.layer_height, first_layer_height=settings.layers.first_layer_height, overhang_angle=angle, bridge_from=wall, support_volume=False)
        common.append((settings, advise.advise(settings, profile, result, bounds=mesh.bounds)))
    entries = advise.combine(settings, common)
    return advise.apply(settings, entries), [(e.path, str(e.value), str(e.reason)[:160]) for e in entries]


def run(args: list[str], folder: Path) -> tuple[int, str]:
    done = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=TIMEOUT, cwd=str(folder))
    return done.returncode, (done.stdout + done.stderr)[-1500:]


def newest_gcode(folder: Path) -> Path | None:
    found = sorted(folder.glob("*.gcode"), key=lambda p: p.stat().st_mtime)
    return found[-1] if found else None


# --- Herstellerprofil allein ----------------------------------------------------------


def orca_reference(exe: Path, setup: Any, machine: Any, process: Any, support: bool) -> dict[str, object]:
    roots = slicer_profiles.profile_roots(setup.flavour, exe)
    found = slicer_profiles.find_profiles(exe, setup.flavour, ("filament",))
    filament = slicer_profiles.match_filament(found, machine, "PLA", roots)
    document: dict[str, object] = {}
    names = {}
    for kind, entry in (("machine", machine), ("process", process), ("filament", filament)):
        if entry is None:
            raise RuntimeError(f"kein Herstellerprofil: {kind}")
        values = slicer_profiles.resolve_values(entry.path, roots=roots)
        names[kind] = entry.name
        if kind == "filament":
            values = {k: (v if isinstance(v, list) else [v]) for k, v in values.items()}
        document.update(values)
    for key in ("type", "instantiation", "inherits", "setting_id", "filament_id"):
        document.pop(key, None)
    # Dieselbe Platte, die Solidons Grundlage nimmt — sonst vergliche der
    # Lauf zwei Betttemperaturen statt zwei Übergaben.
    try:
        from app.core.export import manufacturer
    except ImportError:
        manufacturer = None
    if manufacturer is not None:
        machine_values = slicer_profiles.resolve_values(machine.path, roots=roots)
        model = manufacturer._machine_model(machine.path, str(machine_values.get("printer_model", "")))
        document["curr_bed_type"] = manufacturer.default_plate(machine_values, model) or manufacturer.SINGLE_PLATE
    else:
        default = str(document.get("default_bed_type", "")).strip()
        if default:
            document["curr_bed_type"] = PLATES.get(default, default)
    document["from"] = "project"
    document["name"] = "project_settings"
    document["printer_settings_id"] = names["machine"]
    document["print_settings_id"] = names["process"]
    document["filament_settings_id"] = [names["filament"]]
    if support:
        document["enable_support"] = "1"
    return document


def with_project_settings(source: Path, target: Path, settings: dict[str, object]) -> None:
    with zipfile.ZipFile(source) as src, zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as dst:
        for item in src.infolist():
            if item.filename == "Metadata/project_settings.config":
                continue
            dst.writestr(item, src.read(item.filename))
        dst.writestr("Metadata/project_settings.config", json.dumps(settings, indent=1))


def prusa_reference(folder: Path, support: bool) -> Path:
    from app.core.export.slicer_profiles import _PrusaStore  # Prüfwerkzeug: dieselbe Auflösung wie Solidon

    meta = {"inherits", "compatible_printers", "compatible_printers_condition", "compatible_prints", "compatible_prints_condition", "renamed_from", "alias"}
    full: dict[str, str] = {}
    for line in (HERE / "prusa_eingebaut.ini").read_text(encoding="utf-8").splitlines():
        if line and not line.startswith(("#", "[")):
            key, sep, value = line.partition(" = ")
            if sep:
                full[key.strip()] = value.strip()
    store = _PrusaStore([PRUSA_BUNDLE.parent], eager=False)
    store.read(PRUSA_BUNDLE)
    for kind, name in zip(("machine", "process", "filament"), PRUSA_VENDOR, strict=True):
        matches = [e for e in store.by_name.get((kind, name), ()) if e.path == PRUSA_BUNDLE]
        if not matches:
            raise RuntimeError(f"Prusa-Profil fehlt: {name}")
        full.update({k: str(v) for k, v in store.resolve(matches[0]).items() if k not in meta})
    full["printer_settings_id"], full["print_settings_id"] = PRUSA_VENDOR[0], PRUSA_VENDOR[1]
    full["filament_settings_id"] = f'"{PRUSA_VENDOR[2]}"'
    full["binary_gcode"] = "0"  # Grund am Werkzeug: gelesen wird Text
    if support:
        full["support_material"], full["support_material_auto"] = "1", "1"
    target = folder / "hersteller.ini"
    target.write_text("\n".join(f"{k} = {v}" for k, v in sorted(full.items())) + "\n", encoding="utf-8")
    return target


def cura_reference(support: bool) -> tuple[list[str], dict[str, object]]:
    """Curas Stapel wie das Fenster ihn schickt, nachgerechnet (Prüfwerkzeug, kein Anwendungscode)."""
    from curastack import stack_for

    machine, extruder, variant, gquality, material, mquality = CURA_STACK
    stack = stack_for(machine, extruder, variant, gquality, material, mquality, user={"support_enable": "true"} if support else None)
    keys = sorted(k for k, d in stack.defs.items() if d.get("type") not in (None, "category"))
    values: dict[str, object] = {}
    for key in keys:
        try:
            value = stack.get(key)
        except (KeyError, RecursionError):
            continue
        if isinstance(value, str) and value.startswith("<nicht auswertbar"):
            continue
        values[key] = value
    # Das Fenster ersetzt die Platzhalter im Startcode, bevor es schickt.
    for key in ("machine_start_gcode", "machine_end_gcode"):
        if isinstance(values.get(key), str):
            values[key] = re.sub(r"\{(\w+)\}", lambda m: str(values.get(m.group(1), m.group(0))), values[key])
    definition = str(CURA_RESOURCES / "definitions" / f"{machine}.def.json")
    return [definition, str(CURA_RESOURCES / "extruders" / f"{extruder}.def.json")], values


def cura_value(value: object) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, float):
        return f"{value:.6g}"
    return str(value)


def reference_run(slicer: str, exe: Path, setup: Any, machine: Any, process: Any, profile: Any, objects: list[Any], folder: Path, support: bool) -> dict:
    folder.mkdir(parents=True, exist_ok=True)
    row: dict[str, Any] = {}
    started = time.perf_counter()
    try:
        flavour = setup.flavour
        path, _ = write_assembly(objects, folder, project_name="geometrie", profile=profile, settings=None, flavour=flavour, place_on_bed=True, setup=setup)
        if flavour == "orca":
            target = folder / "hersteller.3mf"
            with_project_settings(path, target, orca_reference(exe, setup, machine, process, support))
            code, output = run([str(exe), "--arrange", "0", "--slice", "0", "--outputdir", str(folder), str(target)], folder)
        elif flavour == "prusa":
            ini = prusa_reference(folder, support)
            code, output = run([str(exe), "--export-gcode", "--load", str(ini), "--output", str(folder / "hersteller.gcode"), str(path)], folder)
        else:
            _definitions, values = cura_reference(support)
            # Rund 600 Werte je Zug sprengen die Windows-Kommandozeile (32 767
            # Zeichen). CuraEngine liest dieselben Werte aus einer Definition:
            # ``overrides`` mit ``default_value``, ohne Erbkette.
            overrides = {key: {"default_value": value} for key, value in values.items()}
            machine_file = folder / "hersteller.def.json"
            machine_file.write_text(json.dumps({"version": 2, "name": "Hersteller", "overrides": overrides}), encoding="utf-8")
            extruder_file = folder / "hersteller_extruder.def.json"
            extruder_file.write_text(json.dumps({"version": 2, "name": "Hersteller Extruder", "overrides": overrides}), encoding="utf-8")
            args = [str(exe), "slice", "-j", str(machine_file), "-e0", "-j", str(extruder_file), "-l", str(path), "-o", str(folder / "hersteller.gcode")]
            code, output = run(args, folder)
        gcode = newest_gcode(folder)
        row.update(ok=gcode is not None and code == 0, exit=code)
        if not row["ok"]:
            row["output"] = output
        if gcode is not None:
            row["gcode"] = str(gcode)
    except Exception as problem:  # noqa: BLE001
        row.update(ok=False, error=type(problem).__name__, detail=str(problem)[:500], trace=traceback.format_exc()[-1500:])
    row["seconds"] = round(time.perf_counter() - started, 1)
    return row


def solidon_run(objects: list[Any], settings: Any, profile: Any, setup: Any, folder: Path) -> dict:
    folder.mkdir(parents=True, exist_ok=True)
    row: dict[str, Any] = {}
    started = time.perf_counter()
    try:
        path, findings = write_assembly(objects, folder, project_name="solidon", profile=profile, settings=settings, flavour=setup.flavour, place_on_bed=True, setup=setup)
        outcome = handover.slice_model(path, settings, profile, setup, output_dir=folder, keep_arrangement=True)
        row.update(
            ok=True,
            gcode=str(outcome.gcode_path),
            print_minutes=round((outcome.metrics.print_seconds or 0) / 60.0, 1),
            filament_g=outcome.metrics.filament_grams,
            findings=sorted({f"{f.severity}:{f.code}" for f in [*findings, *outcome.findings] if f.severity != "info"}),
        )
    except AppError as problem:
        row.update(ok=False, error=type(problem).__name__, detail=str(problem)[:500], values={k: str(v)[:200] for k, v in (problem.values or {}).items()})
    except Exception as problem:  # noqa: BLE001
        row.update(ok=False, error=type(problem).__name__, detail=str(problem)[:500], trace=traceback.format_exc()[-1500:])
    row["seconds"] = round(time.perf_counter() - started, 1)
    return row


# --- Auswertung ----------------------------------------------------------------------------


def minutes_from(header: dict[str, str]) -> float | None:
    for key in ("estimated printing time (normal mode)", "estimated printing time", "model printing time", "total estimated time"):
        text = header.get(key)
        if text:
            parts = {unit: float(number) for number, unit in re.findall(r"(\d+(?:\.\d+)?)\s*([dhms])", text)}
            if parts:
                return round(parts.get("d", 0) * 1440 + parts.get("h", 0) * 60 + parts.get("m", 0) + parts.get("s", 0) / 60, 1)
    return None


def measured(row: dict, bed: tuple[float, float]) -> dict:
    gcode = row.pop("gcode", None)
    if not gcode or not Path(gcode).exists():
        return row
    reading = gcode_lesen.read(Path(gcode), bed=bed)
    row.update(reading.summary())
    if row.get("print_minutes") is None:
        row["print_minutes"] = minutes_from(row.get("header", {}))
    row["_gcode"] = gcode
    return row


def flags(reference: dict, run: dict) -> list[str]:
    """Wo eine Solidon-Übergabe gegen das Herstellerprofil auffällt."""
    found: list[str] = []
    if not run.get("ok"):
        return ["kein Druck"]
    if not reference.get("ok"):
        return found
    if reference.get("start_levelling") and not run.get("start_levelling"):
        found.append("Bettvermessung fehlt")
    if reference.get("start_purge_mm", 0) > 5 and run.get("start_purge_mm", 0) < 1:
        found.append("Spüllinie fehlt")
    share = run.get("first_layer_support_share", 0)
    if share > 0.15 and reference.get("first_layer_support_share", 0) < 0.05:
        found.append(f"Stütze in Schicht 1 ({share:.0%})")
    ref_first = (reference.get("first_layers") or [{}])[0]
    own_first = (run.get("first_layers") or [{}])[0]
    for kind, runs in own_first.get("runs", {}).items():
        if gcode_lesen.kind_of(kind) == "rim":
            before = sum(v for k, v in ref_first.get("runs", {}).items() if gcode_lesen.kind_of(k) == "rim")
            if before and runs > 3 * before:
                found.append(f"Rand zerrissen ({runs} statt {before} Züge)")
    if run.get("off_bed"):
        found.append("außerhalb des Betts")
    minutes, base = run.get("print_minutes"), reference.get("print_minutes")
    if minutes and base and minutes > 1.5 * base:
        found.append(f"Zeit ×{minutes / base:.1f}")
    return found


def picture(reference: dict, run: dict, target: Path, bed: tuple[float, float]) -> None:
    """Die erste Schicht beider Dateien nebeneinander."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, 2, figsize=(16, 8))
    for ax, row, title in ((axes[0], reference, "Herstellerprofil"), (axes[1], run, "Solidon")):
        path = row.get("_gcode")
        if not path or not Path(path).exists():
            ax.set_title(f"{title}: keine Datei")
            continue
        segments = first_layer_segments(Path(path))
        colours = {"model": "#1c7ed6", "support": "#e8590c", "rim": "#862e9c", "other": "#aaaaaa"}
        for kind, lines in segments.items():
            for x0, y0, x1, y1 in lines:
                ax.plot([x0, x1], [y0, y1], color=colours[kind], lw=0.6)
        ax.set_aspect("equal")
        ax.set_xlim(0, bed[0])
        ax.set_ylim(0, bed[1])
        ax.set_title(f"{title}: Schicht 1")
    plt.tight_layout()
    plt.savefig(target, dpi=55)
    plt.close(fig)


def first_layer_segments(path: Path) -> dict[str, list[tuple[float, float, float, float]]]:
    return gcode_lesen.first_layer_segments(path)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w.-]+", "_", MODEL.stem)[:80]
    result_path = OUT / f"{safe}.json"
    work = OUT / "arbeit" / safe
    result: dict[str, Any] = {"model": str(MODEL), "code": ROOT.name, "runs": []}

    def save() -> None:
        temporary = result_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        temporary.replace(result_path)

    started = time.perf_counter()
    try:
        objects = load(MODEL)
    except Exception as problem:  # noqa: BLE001
        result["load_error"] = f"{type(problem).__name__}: {str(problem)[:400]}"
        result["trace"] = traceback.format_exc()[-1500:]
        save()
        return 1
    meshes = [as_mesh_data(o.mesh) for o in objects]
    result.update(bodies=len(objects), triangles=int(sum(m.triangle_count for m in meshes)), load_seconds=round(time.perf_counter() - started, 1))
    save()
    for slicer, (exe_text, printer) in SLICERS.items():
        if ONLY and slicer not in ONLY:
            continue
        exe = Path(exe_text)
        if not exe.exists():
            continue
        profile = profiles.make_profile(printer, MATERIAL)
        bed = (float(profile.printer.build_volume[0]), float(profile.printer.build_volume[1]))
        setup = handover.detect(exe)
        machine = process = None
        if setup.flavour == "orca":
            # Wie der Druckdialog: Maschine, Prozess und Filament des Herstellers vorwählen.
            machine, process = slicer_profiles.match(list(slicer_profiles.find_profiles(exe, setup.flavour, ("machine", "process"))), profile.printer)
            filament = slicer_profiles.match_filament(list(slicer_profiles.find_profiles(exe, setup.flavour, ("filament",))), machine, "PLA", slicer_profiles.profile_roots(setup.flavour, exe))
            setup = replace(setup, machine_profile=machine.name if machine else "", base_process=process.name if process else "", base_filament=str(filament.path) if filament else "")
        standard = print_settings.resolve(profile)
        try:
            taken, entries = advised(standard, profile, objects)
            advice_error = None
        except Exception as problem:  # noqa: BLE001
            taken, entries, advice_error = None, [], f"{type(problem).__name__}: {str(problem)[:300]}"
        wants_support = taken is not None and taken.support.style != "none"
        base = {"slicer": slicer, "printer": printer, "machine": setup.machine_profile, "process": setup.base_process, "advice": entries, "advice_error": advice_error}
        folder = work / slicer
        reference = measured(reference_run(slicer, exe, setup, machine, process, profile, objects, folder / "hersteller", False), bed)
        rows = [("hersteller", reference)]
        if wants_support:
            rows.append(("hersteller_stuetzen", measured(reference_run(slicer, exe, setup, machine, process, profile, objects, folder / "hersteller_stuetzen", True), bed)))
        rows.append(("standard", measured(solidon_run(objects, standard, profile, setup, folder / "standard"), bed)))
        if taken is not None:
            rows.append(("vorschlaege", measured(solidon_run(objects, taken, profile, setup, folder / "vorschlaege"), bed)))
        for variant, row in rows:
            if variant in ("standard", "vorschlaege"):
                row["flags"] = flags(reference, row)
                if row["flags"] and row.get("_gcode"):
                    (OUT / "bilder").mkdir(exist_ok=True)
                    picture(reference, row, OUT / "bilder" / f"{safe}__{slicer}__{variant}.png", bed)
            result["runs"].append({**base, "variant": variant, **{k: v for k, v in row.items() if k != "_gcode"}})
        # Die ganze Konfiguration gegen den Herstellerlauf: ohne Vorschläge soll
        # nichts abweichen als das technisch Nötige (Konzept Herstellerprofil, Stufe B).
        reference_path = reference.get("_gcode")
        if reference_path:
            reference_block = gcode_lesen.config_block(Path(reference_path))
            for entry in result["runs"][-len(rows):]:
                row = dict(rows)[entry["variant"]]
                if entry["variant"] in ("standard", "vorschlaege") and row.get("_gcode"):
                    difference = gcode_lesen.config_difference(reference_block, gcode_lesen.config_block(Path(row["_gcode"])))
                    entry["config_difference"] = {key: list(pair) for key, pair in difference.items()}
        for _variant, row in rows:
            path = row.get("_gcode")
            if path and not os.environ.get("KEEP_GCODE"):
                Path(path).unlink(missing_ok=True)
        save()
    result["seconds"] = round(time.perf_counter() - started, 1)
    save()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
