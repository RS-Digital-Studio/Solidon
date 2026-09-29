"""Ein Modell durch Solidons Übergabe — je Slicer und Drucker, wie der Kunde im Druckdialog.

Auftrag Robert, 27.09.2026: „Die neuen Einstellungen aus der neuen datei passen, so
für jedes Modell, slicer und Drucker verifizieren mit der übergabe“. Kein Test,
eine Messung. Ein Prozess je Modell; der Treiber (``treiber.py``) verteilt.

Aufruf: python einheit.py <code-wurzel> <modell> <ausgabeordner> <kombis>

``<kombis>`` ist ``slicer:drucker,slicer:drucker,…``, ``heim`` (je Slicer der
Drucker, für den sein Hersteller ihn baut) oder ``alle`` (je Slicer jeder
Drucker, den er mit einem Herstellerprofil bedient; PrusaSlicer und Cura jeder
FDM-Drucker, weil Solidon dort seinen eigenen Satz schreibt).

Der Weg ist der des Druckdialogs (``print_settings_dialog``):

1. Vorwahl wie der Dialog: Maschine, Standardprozess und Filament des
   Herstellers (``slicer_profiles.match``/``match_filament``).
2. Grundlage ``manufacturer.base_settings`` und die wirksamen Werte
   ``manufacturer.effective`` — ein neues Projekt hat keine eigene Wahl.
3. Vorschläge wie ``_AdviceWorker._calculate``: je Körper und Spule
   ``settings_for_slot``, Winkel und Wand des strengsten Materials,
   ``slice_body``, ``advise.advise``, ``advise.combine``. Filamentvorschläge
   gelten hier der ganzen Platte (der Dialog legt sie auf die Spule; bei einer
   Spule ist das dasselbe).
4. Je Platte ``_prepare_plate`` und ``_SliceWorker``: ``arrangement_holds``,
   ``write_assembly`` mit Platte, ``handover.slice_model``.

Varianten: ``standard`` (ohne Vorschläge), ``vorschlaege`` (alle übernommen) und
``stuetzen_auto`` (nur wenn Solidon Stützen vorschlägt: Stützen an, Art und
Grenze vom Profil — das Urteil des Slicers zum Vergleich).

Gemessen je Platte: Ergebnis und Befunde, Zeit und Material, was der G-Code tut
(``gcode_lesen``), das Tempo der ersten Schicht je Bahnart, und in der
Orca-Familie der ganze Konfigurationsblock gegen die aufgelöste Kette aus
Maschine, Prozess und Filament des Herstellers. Wo Creality Print über die
Konsole keine 3MF rechnet (RM-164), wird die Projektdatei gegen die Kette
gehalten — sie ist, was das Fenster lädt.
"""
# ruff: noqa: E501

from __future__ import annotations

import ctypes
import json
import math
import os
import re
import shutil
import sys
import time
import traceback
import zipfile
from dataclasses import replace
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
MATRIX = HERE.parent / "uebergabe-matrix-2026-09-27"
ROOT = Path(sys.argv[1]).resolve()
MODEL = Path(sys.argv[2]).resolve()
OUT = Path(sys.argv[3]).resolve()
SPEC = sys.argv[4] if len(sys.argv) > 4 else "heim"
sys.path.insert(0, str(ROOT))
sys.path.insert(1, str(MATRIX))

# Kerne: Der Treiber gibt sie vor, die Slicer als Kindprozesse erben sie.
# Mit eigenen Signaturen: Ohne argtypes übergab ctypes das Pseudohandle als
# 32-Bit-Zahl, SetProcessAffinityMask scheiterte mit ERROR_INVALID_HANDLE, und
# bis 27.09.2026 17:45 lief die ganze Matrix auch auf den Kernen 8-11 (RM-272).
_MASK = os.environ.get("GESAMT_KERNE")
if _MASK and os.name == "nt":
    _kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    _kernel.GetCurrentProcess.restype = ctypes.c_void_p
    _kernel.SetProcessAffinityMask.argtypes = (ctypes.c_void_p, ctypes.c_size_t)
    _kernel.SetProcessAffinityMask.restype = ctypes.c_int
    if not _kernel.SetProcessAffinityMask(_kernel.GetCurrentProcess(), int(_MASK, 16)):
        raise OSError(ctypes.get_last_error(), f"Kernbindung {_MASK} gescheitert")

import app  # noqa: E402

assert Path(app.__file__).resolve().is_relative_to(ROOT), app.__file__

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()

import gcode_lesen  # noqa: E402
from app.core.errors import AppError  # noqa: E402
from app.core.export import handover, manufacturer, slicer_profiles, threemf  # noqa: E402
from app.core.export.writer import arrangement_holds, write_assembly  # noqa: E402
from app.core.geom.attributes import used_slots  # noqa: E402
from app.core.geom.mesh import as_mesh_data  # noqa: E402
from app.core.ingest.loader import detect_unit, read_local_payload, read_model  # noqa: E402
from app.core.ingest.plan import import_plan, names_in_use  # noqa: E402
from app.core.knowledge import print_settings, profiles  # noqa: E402
from app.core.scene import History, OperationDraft, evaluate  # noqa: E402
from app.core.scene.project import ProjectSources, embedded_source_path, new_project, next_source_id  # noqa: E402
from app.core.slice import advise  # noqa: E402
from app.core.slice.analysis import slice_body  # noqa: E402
from app.core.types import Source  # noqa: E402

MATERIAL = "pla"
SLICE_TIMEOUT = float(os.environ.get("GESAMT_ZEITLIMIT", str(45 * 60)))
FILAMENT_GROUPS = ("temperature", "cooling", "retraction", "filament")

SLICERS: dict[str, str] = {
    "elegoo": r"C:\Program Files\ElegooSlicer\elegoo-slicer.exe",
    "bambu": r"C:\Program Files\Bambu Studio\bambu-studio.exe",
    "creality": r"C:\Program Files\Creality\Creality Print 7.2\CrealityPrint.exe",
    "orca": r"C:\Program Files\OrcaSlicer\orca-slicer.exe",
    "prusa": r"C:\Program Files\Prusa3D\PrusaSlicer\prusa-slicer-console.exe",
    "cura": r"C:\Program Files\UltiMaker Cura 5.13.0\CuraEngine.exe",
}
#: Je Slicer der Drucker, für den sein Hersteller ihn baut — bei OrcaSlicer und
#: Cura einer, dessen Hersteller keinen eigenen Slicer liefert.
HOME: dict[str, str] = {
    "elegoo": "centauri-carbon-2",
    "bambu": "bambu-p1s",
    "creality": "creality-k1",
    "orca": "anycubic-kobra-2",
    "prusa": "prusa-mk4s",
    "cura": "sovol-sv06",
}


# --- Laden ----------------------------------------------------------------------------

#: Was beim Laden geschah und in das Ergebnis gehört (die Ausrichtung).
LOADED: dict[str, object] = {}


def load(model: Path) -> tuple[list[Any], list[str]]:
    """Die Körper, wie sie nach ``solidon3d import`` in der Szene stehen, dazu die Befunde."""
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
    history = History(project.document)
    history.apply(plan.title, [plan.draft])
    scene_profile = profiles.scene_profile("centauri-carbon-2", MATERIAL)
    sources = ProjectSources(project, base_dir=model.parent)
    result = evaluate(project.document, scene_profile, sources=sources)
    objects = [entry for entry in result.scene.objects.values() if as_mesh_data(entry.mesh).triangle_count]
    # **Wie ein Kunde dem Prüfbericht folgt**: Sagt er, anders gedreht brauche
    # ein Teil weniger Stützen, klickt der Kunde *Druckoptimal ausrichten*.
    # Die Waschschüssel lag in ihrer Datei auf der gewölbten Seite; in dieser
    # Lage lief jede Übergabe mit 98 % Stütze in Schicht 1 (27.09.2026).
    turned: dict[str, object] = {}
    if os.environ.get("GESAMT_AUSRICHTEN", "1") == "1":
        from app.core.slice.findings import orientation_findings

        for entry in objects:
            for finding in orientation_findings(entry.id, as_mesh_data(entry.mesh), scene_profile):
                if finding.code == "orient.saves_support":
                    turned[str(entry.id)] = dict(finding.values or {})
        if turned:
            history.apply(
                "Druckoptimal ausrichten",
                [OperationDraft(op="orient_for_print", inputs=tuple(entry.id for entry in objects), params={})],
            )
            result = evaluate(project.document, scene_profile, sources=sources)
            objects = [entry for entry in result.scene.objects.values() if as_mesh_data(entry.mesh).triangle_count]
    findings = sorted({f"{f.severity}:{f.code}" for f in result.scene.report.findings if f.severity != "info"})
    LOADED["turned"] = turned
    return objects, findings


def narrow_webs(objects: list[Any]) -> dict[str, Any]:
    """Wie viel der ersten Schicht in schmalen Stegen liegt — je Körper an seinem Fuß.

    Öffnung der Querschnittsfläche 0,1 mm über dem tiefsten Punkt mit dem Radius
    r: Was dabei verschwindet, ist schmaler als 2r. Anlass: Roberts
    Minigolf-Druck, dessen Bodenbahnen an den Stegen zwischen den Löchern bei
    105 mm/s rissen.
    """
    import shapely
    from shapely.geometry import Polygon

    total = 0.0
    lost: dict[str, float] = {"r1.0": 0.0, "r1.5": 0.0, "r2.5": 0.0}
    for entry in objects:
        tm = as_mesh_data(entry.mesh).raw
        z = float(tm.bounds[0][2]) + 0.1
        try:
            section = tm.section(plane_origin=(0, 0, z), plane_normal=(0, 0, 1))
        except Exception:  # noqa: BLE001
            section = None
        if section is None:
            continue
        # Ohne ``rtree`` baut trimesh keine Flächen mit Löchern. Die geschlossenen
        # Ringe genügen: gerade-ungerade über ``symmetric_difference``.
        shape = None
        for ring in section.discrete:
            if len(ring) < 4:
                continue
            polygon = Polygon([(float(p[0]), float(p[1])) for p in ring]).buffer(0)
            if polygon.is_empty:
                continue
            shape = polygon if shape is None else shape.symmetric_difference(polygon)
        if shape is None or shape.is_empty:
            continue
        area = shape.area
        total += area
        for key, radius in (("r1.0", 1.0), ("r1.5", 1.5), ("r2.5", 2.5)):
            opened = shape.buffer(-radius, quad_segs=4).buffer(radius, quad_segs=4)
            lost[key] += max(0.0, area - shapely.intersection(opened, shape).area)
    return {
        "first_layer_mm2": round(total, 1),
        "narrow_share": {key: round(value / total, 3) if total else 0.0 for key, value in lost.items()},
    }


# --- Vorwahl und Grundlage ------------------------------------------------------------------

_FOUND: dict[str, Any] = {}


def found_profiles(exe: Path, flavour: str, kinds: tuple[str, ...]) -> list[Any]:
    key = f"{exe}|{','.join(kinds)}"
    if key not in _FOUND:
        _FOUND[key] = list(slicer_profiles.find_profiles(exe, flavour, kinds))
    return _FOUND[key]


def prepared(slicer: str, profile: Any) -> tuple[Any, dict[str, Any]]:
    """Der Slicer, wie der Druckdialog ihn vorwählt — oder ``None`` mit dem Grund."""
    exe = Path(SLICERS[slicer])
    if not exe.exists():
        return None, {"skip": "Slicer nicht installiert"}
    setup = handover.detect(exe)
    info: dict[str, Any] = {"flavour": setup.flavour}
    # PrusaSlicer wählt wie die Orca-Familie, sobald der Code die Prusa-Kette kennt
    # (Stufe C); ein älterer Stand bekommt es wie bisher ohne Profile.
    on_bundle = setup.flavour == "prusa" and hasattr(manufacturer, "prusa_chain")
    if setup.flavour != "orca" and not on_bundle:
        return setup, info
    machine, process = slicer_profiles.match(found_profiles(exe, setup.flavour, ("machine", "process")), profile.printer)
    if machine is None:
        if on_bundle:
            # Wie der Dialog: ohne Drucker im Bündel Solidons eigener Satz.
            return setup, {**info, "note": "kein Herstellerprofil für diesen Drucker"}
        return None, {**info, "skip": "kein Herstellerprofil für diesen Drucker"}
    roots = slicer_profiles.profile_roots(setup.flavour, exe)
    filament = slicer_profiles.match_filament(found_profiles(exe, setup.flavour, ("filament",)), machine, "PLA", roots)
    identity = getattr(slicer_profiles, "identity", lambda entry: str(entry.path))
    setup = replace(
        setup,
        machine_profile=machine.name,
        base_process=process.name if process else "",
        base_filament=identity(filament) if filament else "",
    )
    info.update(machine=machine.name, process=process.name if process else "", filament=filament.name if filament else "")
    info["_entries"] = (machine, process, filament, roots)
    return setup, info


def chain(info: dict[str, Any]) -> dict[str, tuple[str, str]]:
    """Maschine, Prozess und Filament des Herstellers, aufgelöst — Schlüssel → (Art, Wert)."""
    machine, process, filament, roots = info["_entries"]
    found: dict[str, tuple[str, str]] = {}
    for kind, entry in (("machine", machine), ("process", process), ("filament", filament)):
        if entry is None:
            continue
        values = (
            slicer_profiles.resolve_profile(entry, roots)
            if getattr(entry, "section", "")
            else slicer_profiles.resolve_values(entry.path, roots=roots)
        )
        for key, value in values.items():
            if key in getattr(manufacturer, "PRUSA_MANAGING_KEYS", ()):
                continue
            found[key] = (kind, printed(value))
    return found


def printed(value: object) -> str:
    """Wie der Slicer einen Wert druckt: Listen je Düsenvariante mit dem ersten Eintrag."""
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value)


def same(left: str, right: str) -> bool:
    """Gleich bis auf die Schreibweise des G-Codes (``gegen_kette.same``)."""

    def plain(text: str) -> str:
        text = text.strip()
        if len(text) >= 2 and text[0] == text[-1] == '"':
            text = text[1:-1]
        if "\n" in text:
            return text.strip()
        out: list[str] = []
        index = 0
        while index < len(text):
            char = text[index]
            if char == "\\" and index + 1 < len(text):
                following = text[index + 1]
                out.append({"n": "\n", "r": "\r", "t": "\t", "\\": "\\", '"': '"'}.get(following, "\\" + following))
                index += 2
                continue
            out.append(char)
            index += 1
        return "".join(out).strip()

    left, right = plain(left), plain(right)
    if left == right or left.replace("x", ",") == right.replace("x", ","):
        return True
    try:
        return abs(float(left.rstrip("%")) - float(right.rstrip("%"))) < 1e-6
    except ValueError:
        return False


#: Was die Konsole an Bambus A1 und A1 mini selbst setzt (RM-282).
BAMBU_CONSOLE_LIMITS = frozenset({"machine_max_acceleration_x", "machine_max_acceleration_y", "machine_max_acceleration_travel"})


def against_chain(block: dict[str, str], wanted: dict[str, tuple[str, str]]) -> dict[str, Any]:
    """Jeder Schlüssel der Herstellerkette gegen einen Konfigurationsblock.

    Was die Konsole selbst anders druckt, als die Kette sagt, steht getrennt
    unter ``console`` — gemessen, nicht vermutet (27.09.2026): Mit einem
    Filament schaltet sie den Prime Tower ab, eine leere Liste druckt sie mit
    ihrer Vorgabe, und über ``--load-settings`` setzt sie an Bambus A1 und A1
    mini die Grenzen für X, Y und Leerfahrt auf 6000 mm/s², gleich was die
    Datei sagt (15 000, Herstellername, andere Prozesswerte: immer 6000; über
    die Projektdatei allein 12 000). Der Referenzlauf mit den Dateien des
    Herstellers taugt dafür nicht: Die Konsole löst ``inherits`` darin nicht auf.
    """
    differences: dict[str, list[str]] = {}
    normalised: dict[str, list[str]] = {}
    missing = 0
    single = len(str(block.get("filament_settings_id", "")).split(";")) <= 1
    for key, (kind, value) in sorted(wanted.items()):
        if key in gcode_lesen.TECHNICAL or key in slicer_profiles.DESCRIBING_KEYS:
            continue
        # Mit einem Filament setzt die Konsole den Prime Tower selbst auf 0 —
        # auch im Lauf mit dem Herstellerprofil allein (Abnahme Stufe B).
        if key == "enable_prime_tower" and single:
            continue
        # PrusaSlicer: Solidon liest die Druckdatei als Text und setzt deshalb
        # im Konsolenlauf ``binary_gcode = 0`` (Stufe C, technisch nötig).
        if key == "binary_gcode":
            continue
        found = block.get(key)
        if found is None:
            missing += 1
            continue
        if key == "thumbnails":
            # Der G-Code nennt das Format dazu: „144x144/PNG“ für „144x144“.
            found = re.sub(r"/[A-Z_]+", "", str(found))
            value = re.sub(r"/[A-Z_]+", "", value)
        first = str(found).split(",")[0].split(";")[0]
        # PrusaSlicer liest alte Ja/Nein-Werte als Aufzählung: Sovols Bündel
        # schreibt ``ensure_vertical_shell_thickness = 1``, gedruckt wird
        # ``enabled`` — dieselbe Einstellung (27.09.2026).
        if (value, first) in (("1", "enabled"), ("0", "disabled")):
            normalised[key] = [kind, value, first]
            continue
        if not same(first, value) and not same(str(found), value):
            if value == "" or (key in BAMBU_CONSOLE_LIMITS and str(block.get("printer_model", "")).startswith("Bambu Lab A1")):
                normalised[key] = [kind, value[:120], str(found)[:120]]
            else:
                differences[key] = [kind, value[:120], str(found)[:120]]
    return {"keys": len(wanted), "missing": missing, "differences": differences, "console": normalised}


def project_block(threemf_path: Path) -> dict[str, str]:
    """Die Einstellungen einer Orca-Projektdatei als Block wie im G-Code (Listen → erster Eintrag)."""
    with zipfile.ZipFile(threemf_path) as archive:
        try:
            data = json.loads(archive.read("Metadata/project_settings.config"))
        except KeyError:
            return {}
    return {key: printed(value) for key, value in data.items()}


# --- Vorschläge wie der Druckdialog ------------------------------------------------------


def _for_process(profile: Any, settings: Any) -> Any:
    """Wie der Druckdialog: mit den wirksamen Einstellungen (Stufe L), wo der Code das kennt."""
    try:
        return profiles.for_process(profile, settings, effective=True)
    except TypeError:
        return profiles.for_process(profile, settings)


def advised(objects: list[Any], settings: Any, profile: Any, setup: Any, cache: dict) -> tuple[list[Any], list[Any]]:
    """``_AdviceWorker._calculate``: je Körper und Spule, dann zusammengeführt."""
    common: list[tuple[Any, list[Any]]] = []
    materials: dict[Any, tuple[Any, list[tuple[Any, list[Any]]]]] = {}
    for body in objects:
        mesh = as_mesh_data(body.mesh)
        own_profile = profiles.for_object(profile, body)
        slots = threemf.assembly_slots(threemf.AssemblyPart(mesh=mesh, slots=threemf.slots_for_object(body)))
        present = set(used_slots(mesh))
        processes: list[tuple[Any, Any, Any]] = []
        for slot in slots:
            if slot.index not in present:
                continue
            material = profiles.material_id_for_type(slot.material_type or "")
            material_profile = replace(own_profile, material=profiles.material(material)) if material else own_profile
            effective = handover.settings_for_slot(settings, profile, slot, setup)
            processes.append((slot, _for_process(material_profile, effective), effective))
        fallback = _for_process(own_profile, settings)
        angle = min((p.overhang_limit_degrees for _s, p, _e in processes), default=fallback.overhang_limit_degrees)
        wall = max((p.minimum_wall_thickness for _s, p, _e in processes), default=fallback.minimum_wall_thickness)
        key = (body.id, settings.layers.layer_height, settings.layers.first_layer_height, round(angle, 3), round(wall, 3))
        if key not in cache:
            cache[key] = slice_body(
                mesh,
                settings.layers.layer_height,
                first_layer_height=settings.layers.first_layer_height,
                overhang_angle=angle,
                bridge_from=wall,
                support_volume=False,
            )
        result = cache[key]
        for slot, material_profile, effective in processes:
            # Mit der Slicerfamilie wie der Dialog (``_AdviceWorker``): Über Orcas
            # Auto-Brim schlägt Solidon keinen Brim vor (83a8e3de1).
            entries = advise.advise(
                effective, material_profile, result, bounds=mesh.bounds, flavour=setup.flavour
            )
            common.append((effective, [e for e in entries if e.path.partition(".")[0] not in FILAMENT_GROUPS]))
            identity = threemf.slot_identity(slot)
            materials.setdefault(identity, (slot, []))[1].append((effective, [e for e in entries if e.path.partition(".")[0] in FILAMENT_GROUPS]))
    plate_wide = advise.combine(settings, common)
    per_spool: list[Any] = []
    for _slot, groups in materials.values():
        per_spool.extend(advise.combine(groups[0][0], groups))
    return plate_wide, per_spool


def offered(entry: Any, flavour: str) -> bool:
    """``PrintSettingsDialog._current_advice``: nur, was beim Slicer ankommt und dort etwas ändert."""
    from app.core.export import slicer_keys

    caps = getattr(slicer_keys, "caps_volumetric_speed", None)
    limits = getattr(advise, "limits_flow", None)
    if caps is not None and limits is not None and caps(flavour) and limits(entry):
        return False
    return slicer_keys.takes(flavour, entry.path)  # type: ignore[arg-type]


# --- Eine Platte in den Slicer ----------------------------------------------------------------


def plate_run(on_plate: list[Any], plate: int, settings: Any, profile: Any, setup: Any, folder: Path, name: str) -> dict[str, Any]:
    """``_prepare_plate`` und ``_SliceWorker`` für eine Platte."""
    folder.mkdir(parents=True, exist_ok=True)
    row: dict[str, Any] = {"plate": plate, "bodies": len(on_plate)}
    started = time.perf_counter()
    parts = [threemf.AssemblyPart(mesh=as_mesh_data(o.mesh), slots=threemf.slots_for_object(o)) for o in on_plate]
    slots = threemf.merge_slots(parts)
    chosen = tuple("" for _ in slots)
    local = replace(settings, slot_profiles=chosen)
    keep = arrangement_holds([as_mesh_data(o.mesh) for o in on_plate], profile)
    row["keep_arrangement"] = keep
    try:
        written, findings = write_assembly(
            on_plate, folder, project_name=name, profile=profile, plate=plate, settings=local,
            flavour=setup.flavour, place_on_bed=keep, setup=setup,
        )
        row["written"] = str(written)
        row["export_findings"] = sorted({f"{f.severity}:{f.code}" for f in findings if f.severity != "info"})
        outcome = handover.slice_model(
            [written], settings, profile, setup, output_dir=folder, timeout=SLICE_TIMEOUT,
            keep_arrangement=keep, slots=handover.with_slot_profiles(slots, chosen),
            model_height=max((as_mesh_data(o.mesh).bounds.size[2] for o in on_plate), default=None),
            expected_tools=threemf.tools_in_use(parts),
        )
        metrics = outcome.metrics
        row.update(
            ok=True,
            gcode=str(outcome.gcode_path),
            print_minutes=round((metrics.print_seconds or 0) / 60.0, 1),
            filament_g=metrics.filament_grams,
            slice_findings=sorted({f"{f.severity}:{f.code}" for f in outcome.findings if f.severity != "info"}),
            warnings=[
                {"code": f.code, "text": str(f.message)[:240]}
                for f in [*findings, *outcome.findings]
                if f.severity in ("warning", "error")
            ][:12],
        )
    except AppError as problem:
        row.update(
            ok=False,
            error=type(problem).__name__,
            title=str(getattr(problem, "title", ""))[:160],
            detail=str(problem)[:400],
            suggestions=[str(getattr(s, "label", s))[:60] for s in getattr(problem, "suggestions", ())],
        )
    except Exception as problem:  # noqa: BLE001 — eine Messung berichtet alles
        row.update(ok=False, error=type(problem).__name__, detail=str(problem)[:400], trace=traceback.format_exc()[-1500:])
    row["seconds"] = round(time.perf_counter() - started, 1)
    return row


# --- G-Code lesen -----------------------------------------------------------------------------

def first_layer_speeds(path: Path) -> dict[str, Any]:
    """Tempo der ersten Schicht je Bahnart: längengewichteter Median und Höchstwert in mm/s."""
    kind, x, y, feed = "?", 0.0, 0.0, 0.0
    absolute, last_e = True, 0.0
    started, pending, layer = False, False, -1
    samples: dict[str, list[tuple[float, float]]] = {}
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            stripped = line.strip()
            if not stripped:
                continue
            if stripped.startswith(";"):
                if gcode_lesen.LAYER_MARK.match(stripped):
                    started = True
                    pending = True
                    continue
                typed = gcode_lesen.TYPE_MARK.match(stripped)
                if typed:
                    kind = typed.group("type")
                continue
            code = stripped.split(";", 1)[0].strip()
            upper = code.upper()
            if upper.startswith("M83"):
                absolute = False
                continue
            if upper.startswith("M82"):
                absolute = True
                continue
            if upper.startswith("G92"):
                found = {m.group("name").upper(): m.group("value") for m in gcode_lesen.WORD.finditer(code[3:])}
                if "E" in found:
                    last_e = float(found["E"])
                continue
            if not upper.startswith(("G0", "G1", "G2", "G3")) or upper.startswith(("G10", "G11", "G28", "G29")):
                continue
            words = {m.group("name").upper(): float(m.group("value")) for m in gcode_lesen.WORD.finditer(code[2:])}
            if "F" in words:
                feed = words["F"] / 60.0
            nx, ny = words.get("X", x), words.get("Y", y)
            pushed = 0.0
            if "E" in words:
                pushed = (words["E"] - last_e) if absolute else words["E"]
                if absolute:
                    last_e = words["E"]
            moved = nx != x or ny != y
            if started and pending and moved:
                pending = False
                layer += 1
                if layer > 0:
                    break
            if layer == 0 and moved and pushed > 0 and feed > 0:
                samples.setdefault(gcode_lesen.kind_of(kind) if gcode_lesen.kind_of(kind) != "model" else kind, []).append((math.hypot(nx - x, ny - y), feed))
            x, y = nx, ny
    speeds: dict[str, Any] = {}
    for name, values in samples.items():
        length = sum(v[0] for v in values)
        if length < 1.0:
            continue
        ordered = sorted(values, key=lambda v: v[1])
        half, acc, median = length / 2.0, 0.0, ordered[-1][1]
        for part, speed in ordered:
            acc += part
            if acc >= half:
                median = speed
                break
        speeds[name] = {"mm": round(length), "median": round(median, 1), "max": round(max(v[1] for v in values), 1)}
    return speeds


def measured(row: dict[str, Any], bed: tuple[float, float]) -> dict[str, Any]:
    path = row.get("gcode")
    if not path or not Path(path).exists():
        return row
    reading = gcode_lesen.read(Path(path), bed=bed)
    summary = reading.summary()
    header = summary.pop("header", {})
    row.update(summary)
    row["header"] = {k: header[k] for k in ("curr_bed_type", "printer_settings_id", "print_settings_id", "support_threshold_angle", "enable_support", "support_material") if k in header}
    row["first_layer_speeds"] = first_layer_speeds(Path(path))
    if row.get("print_minutes") in (None, 0.0):
        row["print_minutes"] = minutes_from(header)
    return row


def minutes_from(header: dict[str, str]) -> float | None:
    for key in ("estimated printing time (normal mode)", "estimated printing time", "model printing time", "total estimated time"):
        text = header.get(key)
        if text:
            parts = {unit: float(number) for number, unit in re.findall(r"(\d+(?:\.\d+)?)\s*([dhms])", text)}
            if parts:
                return round(parts.get("d", 0) * 1440 + parts.get("h", 0) * 60 + parts.get("m", 0) + parts.get("s", 0) / 60, 1)
    return None


# --- Bewertung ------------------------------------------------------------------------------------


def flags_for(variant: str, row: dict[str, Any], base: dict[str, Any] | None, narrow: dict[str, Any]) -> list[str]:
    """Wo ein Lauf auffällt — gegen den Standardlauf (der ohne Vorschläge das Herstellerprofil ist)."""
    found: list[str] = []
    if not row.get("ok"):
        if "nur in seinem Fenster" in str(row.get("detail", "")):
            # Creality Print rechnet über die Konsole keine 3MF (RM-164); der
            # Kunde geht über „Im Slicer öffnen“, und das Fenster lädt die
            # Projektdatei — die ist hier gegen die Kette gehalten.
            project = row.get("chain_project") or {}
            found.append("nur im Fenster (RM-164)")
            if variant == "standard" and project.get("differences"):
                found.append(f"Projektdatei weicht von der Herstellerkette ab: {', '.join(sorted(project['differences'])[:6])}")
            return found
        return [f"kein Druck: {row.get('title') or row.get('error')}"]
    if row.get("off_bed"):
        found.append("außerhalb des Betts")
    if variant == "standard":
        # Der Startcode ist, was die Maschine vorgibt. Gleicht der Lauf der
        # Herstellerkette, ist es auch der des Herstellers (Kobra 2: keine
        # Vermessung, das Netz kommt aus LeviQ am Drucker).
        chain_check = row.get("chain")
        differing = chain_check.get("differences", {}) if chain_check else {}
        vendor = "wie Hersteller: " if chain_check and "machine_start_gcode" not in differing and "start_gcode" not in differing else ""
        if not row.get("start_levelling"):
            found.append(f"{vendor}keine Bettvermessung im Startcode")
        if row.get("start_purge_mm", 0) < 1:
            found.append(f"{vendor}keine Spüllinie")
    share = row.get("first_layer_support_share", 0)
    if base is not None and base.get("ok"):
        if share > 0.15 and base.get("first_layer_support_share", 0) < 0.05:
            found.append(f"Stütze in Schicht 1 ({share:.0%})")
        own = (row.get("first_layers") or [{}])[0].get("runs", {})
        ref = (base.get("first_layers") or [{}])[0].get("runs", {})
        rim_own = sum(v for k, v in own.items() if gcode_lesen.kind_of(k) == "rim")
        rim_ref = sum(v for k, v in ref.items() if gcode_lesen.kind_of(k) == "rim")
        if rim_ref and rim_own > 3 * rim_ref:
            found.append(f"Rand zerrissen ({rim_own} statt {rim_ref} Züge)")
        minutes, before = row.get("print_minutes"), base.get("print_minutes")
        if minutes and before and minutes > 1.5 * before:
            found.append(f"Zeit ×{minutes / before:.1f}")
    elif share > 0.15:
        found.append(f"Stütze in Schicht 1 ({share:.0%})")
    fast = max((v["median"] for k, v in (row.get("first_layer_speeds") or {}).items() if k not in ("rim", "support", "other")), default=0.0)
    if narrow.get("narrow_share", {}).get("r1.5", 0) >= 0.05 and fast > 60:
        found.append(f"schmale Stege mit {fast:.0f} mm/s in Schicht 1")
    chain_check = row.get("chain") or row.get("chain_project")
    if variant == "standard" and chain_check and chain_check.get("differences"):
        found.append(f"weicht von der Herstellerkette ab: {', '.join(sorted(chain_check['differences'])[:6])}")
    return found


def significant(flags: list[str]) -> bool:
    """Ob ein Befund Solidon gilt — nicht dem Fensterweg von Creality Print oder dem Hersteller."""
    return any(not flag.startswith(("nur im Fenster", "wie Hersteller")) for flag in flags)


def picture(rows: list[tuple[str, dict[str, Any]]], target: Path, bed: tuple[float, float]) -> None:
    """Die erste Schicht der Läufe nebeneinander."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, axes = plt.subplots(1, len(rows), figsize=(8 * len(rows), 8))
    if len(rows) == 1:
        axes = [axes]
    colours = {"model": "#1c7ed6", "support": "#e8590c", "rim": "#862e9c", "other": "#aaaaaa"}
    for ax, (title, row) in zip(axes, rows, strict=True):
        path = row.get("gcode")
        if not path or not Path(path).exists():
            ax.set_title(f"{title}: keine Datei")
            continue
        for kind, lines in first_layer_segments(Path(path)).items():
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
    out: dict[str, list[tuple[float, float, float, float]]] = {"model": [], "support": [], "rim": [], "other": []}
    kind, x, y, last_e, absolute = "?", 0.0, 0.0, 0.0, True
    started, pending, layer = False, False, -1
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            stripped = line.strip()
            if stripped.startswith(";"):
                if gcode_lesen.LAYER_MARK.match(stripped):
                    started, pending = True, True
                typed = gcode_lesen.TYPE_MARK.match(stripped)
                if typed:
                    kind = typed.group("type")
                continue
            upper = stripped.split(";", 1)[0].strip().upper()
            if upper.startswith("M83"):
                absolute = False
            elif upper.startswith("M82"):
                absolute = True
            if not upper.startswith(("G0", "G1", "G2", "G3")) or upper.startswith(("G10", "G11", "G28", "G29")):
                continue
            words = {m.group("name").upper(): float(m.group("value")) for m in gcode_lesen.WORD.finditer(upper[2:])}
            nx, ny = words.get("X", x), words.get("Y", y)
            pushed = 0.0
            if "E" in words:
                pushed = (words["E"] - last_e) if absolute else words["E"]
                if absolute:
                    last_e = words["E"]
            if started and pending and (nx != x or ny != y):
                pending = False
                layer += 1
                if layer > 0:
                    break
            if layer == 0 and pushed > 0 and (nx != x or ny != y):
                out[gcode_lesen.kind_of(kind)].append((x, y, nx, ny))
            x, y = nx, ny
    return out


# --- Ablauf -----------------------------------------------------------------------------------------


def combos(spec: str) -> list[tuple[str, str]]:
    if spec == "heim":
        return list(HOME.items())
    if spec == "alle":
        printers = [key for key, value in profiles.printer_profiles().items() if value.technology != "resin"]
        return [(slicer, printer) for slicer in SLICERS for printer in printers]
    pairs = []
    for part in spec.split(","):
        slicer, _sep, printer = part.partition(":")
        pairs.append((slicer.strip(), printer.strip()))
    return pairs


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    safe = re.sub(r"[^\w.-]+", "_", MODEL.stem)[:80]
    result_path = OUT / f"{safe}.json"
    work = OUT / "arbeit" / safe
    result: dict[str, Any] = {"model": str(MODEL), "code": str(ROOT), "spec": SPEC, "combos": [], "done": False}
    if result_path.exists():
        # Wieder aufnehmen: fertige Kombinationen bleiben stehen.
        try:
            previous = json.loads(result_path.read_text(encoding="utf-8"))
            if previous.get("code") == str(ROOT):
                result = previous
                result["done"] = False
        except (OSError, ValueError):
            pass
    finished = {(c["slicer"], c["printer"]) for c in result["combos"] if c.get("complete")}

    def save() -> None:
        temporary = result_path.with_suffix(".tmp")
        temporary.write_text(json.dumps(result, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
        temporary.replace(result_path)

    started = time.perf_counter()
    try:
        objects, load_findings = load(MODEL)
    except Exception as problem:  # noqa: BLE001
        result.update(load_error=f"{type(problem).__name__}: {str(problem)[:400]}", trace=traceback.format_exc()[-1500:], done=True)
        save()
        return 1
    meshes = [as_mesh_data(o.mesh) for o in objects]
    plates = sorted({int(getattr(o, "plate", 0) or 0) for o in objects})
    result.update(
        bodies=len(objects),
        triangles=int(sum(m.triangle_count for m in meshes)),
        plates=plates,
        size_mm=[round(float(v), 1) for v in (max(m.bounds.size[i] for m in meshes) for i in range(3))] if meshes else [],
        load_findings=load_findings,
        load_seconds=round(time.perf_counter() - started, 1),
        oriented=LOADED.get("turned", {}),
    )
    if "narrow" not in result:
        try:
            result["narrow"] = narrow_webs(objects)
        except Exception as problem:  # noqa: BLE001
            result["narrow"] = {"error": f"{type(problem).__name__}: {problem}"}
    save()
    cache: dict = {}
    for slicer, printer in combos(SPEC):
        if (slicer, printer) in finished:
            continue
        if os.environ.get("GESAMT_PAUSE") and Path(os.environ["GESAMT_PAUSE"]).exists():
            while Path(os.environ["GESAMT_PAUSE"]).exists():
                time.sleep(30)
        entry: dict[str, Any] = {"slicer": slicer, "printer": printer}
        combo_started = time.perf_counter()
        result["combos"] = [c for c in result["combos"] if (c["slicer"], c["printer"]) != (slicer, printer)]
        result["combos"].append(entry)
        try:
            profile = profiles.make_profile(printer, MATERIAL)
            setup, info = prepared(slicer, profile)
            entries = info.pop("_entries", None)
            entry.update(info)
            if setup is None:
                entry["complete"] = True
                save()
                continue
            bed = (float(profile.printer.build_volume[0]), float(profile.printer.build_volume[1]))
            quality = print_settings.resolve(profile).quality
            foundation = manufacturer.base_settings(profile, quality, setup)
            entry["foundation"] = {
                "has_profile": foundation.has_profile,
                "plate": foundation.plate,
                "from_profile": len(foundation.from_profile),
                "foreign": dict(foundation.foreign),
                "staged": sorted(foundation.staged),
                "findings": [f"{f.severity}:{f.code}" for f in manufacturer.findings(foundation)],
            }
            standard = manufacturer.effective(None, foundation)
            try:
                plate_wide, per_spool = advised(objects, standard, profile, setup, cache)
                everything = [*plate_wide, *per_spool]
                shown = [e for e in everything if offered(e, setup.flavour)]
                entry["advice"] = [[e.path, str(e.value), str(e.reason)[:140]] for e in shown]
                entry["advice_hidden"] = [[e.path, str(e.value), str(e.reason)[:80]] for e in everything if e not in shown]
                taken = advise.apply(standard, shown) if shown else None
            except Exception as problem:  # noqa: BLE001
                entry["advice_error"] = f"{type(problem).__name__}: {str(problem)[:300]}"
                entry["advice_trace"] = traceback.format_exc()[-1200:]
                taken = None
            variants: list[tuple[str, Any]] = [("standard", standard)]
            if taken is not None:
                variants.append(("vorschlaege", taken))
                if taken.support.style != "none" and standard.support.style == "none":
                    variants.append(("stuetzen_auto", print_settings.with_choice(standard, "support.style", "auto")))
            wanted = chain({"_entries": entries}) if entries is not None else None
            folder = work / f"{slicer}__{printer}"
            entry["variants"] = {}
            for variant, settings in variants:
                runs = []
                for plate in plates:
                    on_plate = [o for o in objects if int(getattr(o, "plate", 0) or 0) == plate]
                    row = measured(plate_run(on_plate, plate, settings, profile, setup, folder / variant / f"p{plate}", safe), bed)
                    if row.get("gcode") and Path(row["gcode"]).exists() and wanted is not None:
                        row["chain"] = against_chain(gcode_lesen.config_block(Path(row["gcode"])), wanted)
                    elif row.get("written") and Path(row["written"]).exists() and wanted is not None and Path(row["written"]).suffix == ".3mf":
                        # Kein G-Code (Creality Print rechnet über die Konsole keine 3MF):
                        # dann die Projektdatei, die das Fenster lädt.
                        row["chain_project"] = against_chain(project_block(Path(row["written"])), wanted)
                    runs.append(row)
                entry["variants"][variant] = runs
            # Bewerten je Platte gegen den Standardlauf derselben Platte.
            flagged = []
            base_runs = {r["plate"]: r for r in entry["variants"]["standard"]}
            for variant, runs in entry["variants"].items():
                for row in runs:
                    base = None if variant == "standard" else base_runs.get(row["plate"])
                    row["flags"] = flags_for(variant, row, base, result.get("narrow", {}))
                    if significant(row["flags"]):
                        flagged.append((variant, row))
            if flagged:
                (OUT / "bilder").mkdir(exist_ok=True)
                for plate in plates:
                    rows = [(v, r) for v, runs in entry["variants"].items() for r in runs if r["plate"] == plate and r.get("gcode")]
                    if rows and any(significant(r["flags"]) for _v, r in rows):
                        try:
                            picture(rows, OUT / "bilder" / f"{safe}__{slicer}__{printer}__p{plate}.png", bed)
                        except Exception as problem:  # noqa: BLE001
                            entry.setdefault("picture_errors", []).append(str(problem)[:200])
            # Vorschläge gegen den Standardlauf: welche Schlüssel sie ändern.
            for variant in ("vorschlaege", "stuetzen_auto"):
                for row in entry["variants"].get(variant, []):
                    before = base_runs.get(row["plate"], {})
                    if row.get("gcode") and before.get("gcode") and Path(row["gcode"]).exists() and Path(before["gcode"]).exists():
                        difference = gcode_lesen.config_difference(gcode_lesen.config_block(Path(before["gcode"])), gcode_lesen.config_block(Path(row["gcode"])))
                        row["changed_keys"] = {k: [str(a)[:80], str(b)[:80]] for k, (a, b) in difference.items()}
            entry["complete"] = True
        except Exception as problem:  # noqa: BLE001
            entry.update(error=f"{type(problem).__name__}: {str(problem)[:400]}", trace=traceback.format_exc()[-1500:], complete=True)
        entry["seconds"] = round(time.perf_counter() - combo_started, 1)
        # Aufräumen: G-Code und Projektdateien nur behalten, wenn etwas auffiel.
        keep_files = os.environ.get("GESAMT_BEHALTEN") or any(significant(r.get("flags", [])) for runs in entry.get("variants", {}).values() for r in runs)
        for runs in entry.get("variants", {}).values():
            for row in runs:
                for key in ("gcode", "written"):
                    if row.get(key) and not keep_files:
                        Path(row[key]).unlink(missing_ok=True)
        if not keep_files:
            shutil.rmtree(work / f"{slicer}__{printer}", ignore_errors=True)
        save()
    result["seconds"] = round(time.perf_counter() - started, 1)
    result["done"] = True
    save()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
