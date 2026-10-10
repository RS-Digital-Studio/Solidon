"""RM-587: Kommen Brückenstütze, dicke Brücken, Brückenfluss, Zusatzwände und Umkehr
je Teil im Slicer an — und nur dort?

Aufruf: python bruecken_je_teil.py <wurzel> <ausgabe> <fall> <programm> …

Eine Platte mit zwei Teilen, ``ziel`` links und ``bezug`` rechts. Fälle:

- ``stuetze``, ``dick``, ``fluss``, ``rand``, ``trichter`` (kontrolliert): zwei gleiche Körper,
  nur ``ziel`` bekommt den Wert als Objektwert (``writer.part_advice`` ersetzt wie in
  ``kontakt_je_teil.py``), jeweils weg von der Grundlage des Herstellerprofils.
  ``stuetze``: Brücke 36 mm unter Gitterstütze überall, ``support.bridges`` gekippt;
  ``dick``: dieselbe Brücke ohne Stütze, ``shell.thick_bridges`` gekippt
  (``fluss``: ``shell.bridge_flow`` 0,7); ``rand``: Säule mit 3-mm-Auskragung ohne Stütze,
  ``shell.overhang_walls``; ``trichter``: ABS-Trichter 50 Grad, ``shell.overhang_reverse``.
- ``nat-frei``, ``nat-stuetze``, ``nat-abs`` (echter Rat, wie der Kunde): ``ziel``
  trägt die lange Brücke mit Auskragung (``nat-abs``: den Trichter), ``bezug`` eine
  kurze Brücke von 8 mm (``nat-abs``: einen Zylinder). Übernommen wird, was der Rat
  beider Teile zusammen vorschlägt, außer der Stützart; der Export fragt je Teil.

Gemessen je Teil im G-Code (Bereich aus der größten Lücke der Modellbahnen, welcher
das Ziel ist, sagt der Name im G-Code, bei Cura die Lage links): Stützbahn, äußere
Brückenbahn (Länge, Förderung je mm, Tempo, Lüfter), Drehsinnwechsel der Außenwand.
Dazu, was die Übergabe je Teil und für die Platte schrieb.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import itertools
import json
import math
import os
import re
import statistics
import sys
import traceback
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
TREE = Path(sys.argv[1]).resolve()
OUT = Path(sys.argv[2]).resolve()
CASE = sys.argv[3]
os.environ.update(PYTHONUTF8="1", ABZUG=str(TREE), GC=str(OUT), GP_LAUF="bruecken")
spec = importlib.util.spec_from_file_location(
    "gp", r"F:\solidon-review-reports\gcode\rest\gegenpruefung.py"
)
assert spec is not None and spec.loader is not None
h = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = h
spec.loader.exec_module(h)
sys.path.insert(1, str(HERE))

import app  # noqa: E402

assert Path(app.__file__).resolve().is_relative_to(TREE), app.__file__

import gcode_kontakt  # noqa: E402
import numpy as np  # noqa: E402
import trimesh  # noqa: E402

from app.core.export import writer  # noqa: E402
from app.core.geom.mesh import MeshData  # noqa: E402
from app.core.slice import advise  # noqa: E402
from app.core.types import SceneObject, SettingAdvice  # noqa: E402

h.SLICERS["anycubic"] = Path(r"C:\Program Files\AnycubicSlicerNext\AnycubicSlicerNext.exe")
PROGRAMS = {
    "orca": ("orcaslicer", "creality-k1-max"),
    "elegoo": ("elegooslicer", "elegoo-neptune-4"),
    "bambu": ("bambustudio", "bambu-a1"),
    "creality": ("crealityprint", "creality-k1-max"),
    "anycubic": ("anycubicslicernext", "anycubic-kobra-2"),
    "prusa": ("prusaslicer", "prusa-mk4s"),
    "superslicer": ("superslicer", "prusa-mini"),
    "cura": ("cura", "creality-ender3-v3-se"),
}
RM587 = (
    "support.bridges",
    "shell.thick_bridges",
    "shell.bridge_flow",
    "shell.overhang_walls",
    "shell.overhang_reverse",
)
#: Die Schlüssel der fünf Pfade in allen Familien, dazu Brückentempo und -lüfter.
KEYS = (
    "dont_support_bridges",
    "bridge_no_support",
    "thick_bridges",
    "bridge_flow_ratio",
    "bridge_flow",
    "extra_perimeters_on_overhangs",
    "extra_perimeters_overhangs",
    "overhang_reverse",
    "bridge_type",
    "bridge_speed",
    "bridge_fan_speed",
    "support_material",
    "enable_support",
    "support_type",
    "support_on_build_plate_only",
    "bridge_settings_enabled",
    "bridge_skin_density",
)
MATERIAL = "abs" if CASE in ("trichter", "nat-abs") else "pla"
SUPPORTED = CASE in ("stuetze", "nat-stuetze")
NATURAL = CASE.startswith("nat-")
NO_VENDOR = os.environ.get("SONDE_OHNE_HERSTELLER") == "1"
#: Ein anderer Drucker je Programm, etwa ``orca:anycubic-kobra-2`` (dort stützt das
#: Herstellerprofil Brücken nicht, ``bridge_no_support = 1``).
PRINTERS = dict(
    entry.split(":", 1) for entry in os.environ.get("SONDE_DRUCKER", "").split(",") if entry
)
#: Die Spannweite der kurzen Brücke am Bezug (Vorgabe 8 mm).
SHORT = float(os.environ.get("SONDE_KURZ", "8"))
RUN = (
    CASE
    + (f"-kurz{SHORT:g}" if SHORT != 8.0 else "")
    + ("-ohne-hersteller" if NO_VENDOR else "")
    + "".join(f"-{value}" for value in PRINTERS.values())
)
(OUT / "bruecken").mkdir(parents=True, exist_ok=True)


def box(extents: tuple[float, float, float], centre: tuple[float, float, float]) -> trimesh.Trimesh:
    mesh = trimesh.creation.box(extents=extents)
    mesh.apply_translation(centre)
    return mesh


def bridge(span: float, ledge: float = 0.0) -> trimesh.Trimesh:
    """Zwei Säulen 6 x 20 x 12 mm, darüber ein Deck 3 mm; ``span`` frei dazwischen,
    ``ledge`` ragt am rechten Ende einseitig über die Säule hinaus."""
    half = span / 2.0
    left = box((6.0, 20.0, 12.0), (-half - 3.0, 0.0, 6.0))
    right = box((6.0, 20.0, 12.0), (half + 3.0, 0.0, 6.0))
    start, stop = -half - 6.0, half + 6.0 + ledge
    deck = box((stop - start, 20.0, 3.0), ((start + stop) / 2.0, 0.0, 13.5))
    return trimesh.boolean.union([left, right, deck], engine="manifold")


def rim() -> trimesh.Trimesh:
    post = box((20.0, 20.0, 20.0), (0.0, 0.0, 10.0))
    slab = box((26.0, 20.0, 3.0), (0.0, 0.0, 21.5))
    return trimesh.boolean.union([post, slab], engine="manifold")


def funnel(angle: float = 50.0, bottom: float = 6.0, height: float = 20.0) -> trimesh.Trimesh:
    top = bottom + height * math.tan(math.radians(angle))
    sides = 128
    turn = np.linspace(0.0, 2.0 * np.pi, sides, endpoint=False)
    lower = np.c_[bottom * np.cos(turn), bottom * np.sin(turn), np.zeros(sides)]
    upper = np.c_[top * np.cos(turn), top * np.sin(turn), np.full(sides, height)]
    vertices = np.vstack([lower, upper, [[0.0, 0.0, 0.0], [0.0, 0.0, height]]])
    faces = []
    for index in range(sides):
        following = (index + 1) % sides
        faces += [
            [index, following, sides + following],
            [index, sides + following, sides + index],
            [2 * sides, following, index],
            [2 * sides + 1, sides + index, sides + following],
        ]
    raw = trimesh.Trimesh(vertices, faces)
    raw.fix_normals()
    return raw


def cylinder() -> trimesh.Trimesh:
    raw = trimesh.creation.cylinder(radius=6.0 + 20.0 * math.tan(math.radians(50.0)), height=20.0)
    raw.apply_translation((0.0, 0.0, 10.0))
    return raw


def bodies() -> dict[str, trimesh.Trimesh]:
    if CASE in ("stuetze", "dick", "fluss"):
        return {"ziel": bridge(36.0), "bezug": bridge(36.0)}
    if CASE == "rand":
        return {"ziel": rim(), "bezug": rim()}
    if CASE == "trichter":
        return {"ziel": funnel(), "bezug": funnel()}
    if CASE in ("nat-frei", "nat-stuetze"):
        return {"ziel": bridge(36.0, ledge=3.0), "bezug": bridge(SHORT)}
    if CASE == "nat-abs":
        return {"ziel": funnel(), "bezug": cylinder()}
    raise SystemExit(f"unbekannter Fall {CASE}")


def controls_for(standard) -> dict[str, object]:
    read = h.print_settings.read_path
    if CASE == "stuetze":
        return {"support.bridges": not bool(read(standard, "support.bridges"))}
    if CASE == "dick":
        return {"shell.thick_bridges": not bool(read(standard, "shell.thick_bridges"))}
    if CASE == "fluss":
        return {"shell.bridge_flow": 0.7}
    if CASE == "rand":
        return {"shell.overhang_walls": not bool(read(standard, "shell.overhang_walls"))}
    if CASE == "trichter":
        return {"shell.overhang_reverse": not bool(read(standard, "shell.overhang_reverse"))}
    raise AssertionError(CASE)


def written(project: Path) -> dict[str, object]:
    """Was die Übergabe schrieb: Objektwerte je Teil und die Platte (nur :data:`KEYS`)."""
    found: dict[str, object] = {"objects": {}, "plate": {}}
    if project.suffix.lower() != ".3mf":
        # Cura: je Netz eine STL, die Netzwerte in <name>.meshes.json, das Ziel zuerst.
        for sidecar in project.parent.glob("*.meshes.json"):
            meshes = json.loads(sidecar.read_text(encoding="utf-8"))["meshes"]
            # part-1 ist das Ziel, part-2 der Bezug; Sperrkörper stehen unter ihrem Dateinamen.
            labels = {"part-1": "ziel", "part-2": "bezug"}
            for mesh in meshes:
                stem = Path(mesh["file"]).stem.split("-", 1)[-1]
                found["objects"][labels.get(stem, stem)] = mesh.get("settings", {})
        commands = h.CAPTURE.get("commands", [])
        if commands:
            words = commands[-1]["command"]
            found["plate"] = {
                word.split("=", 1)[0]: word.split("=", 1)[1]
                for word in words
                if "=" in word and word.split("=", 1)[0] in KEYS
            }
        return found
    with zipfile.ZipFile(project) as archive:
        names = set(archive.namelist())
        for name in ("Metadata/model_settings.config", "Metadata/Slic3r_PE_model.config"):
            if name in names:
                root = ET.fromstring(archive.read(name))
                for element in root.iter("object"):
                    values = {
                        item.get("key"): item.get("value") for item in element.findall("metadata")
                    }
                    found["objects"][values.get("name") or element.get("id")] = {
                        key: value for key, value in values.items() if key in KEYS
                    }
        if "Metadata/project_settings.config" in names:
            plate = json.loads(archive.read("Metadata/project_settings.config"))
            found["plate"] = {key: plate[key] for key in KEYS if key in plate}
        if "Metadata/Slic3r_PE.config" in names:
            text = archive.read("Metadata/Slic3r_PE.config").decode("utf-8", "replace")
            for line in text.splitlines():
                match = re.match(r"^; (\w+) = (.*)$", line)
                if match and match.group(1) in KEYS:
                    found["plate"][match.group(1)] = match.group(2)
        model = next((n for n in names if n.endswith(".model") and n.startswith("3D/")), None)
        if model is not None:
            text = archive.read(model).decode("utf-8", "replace")
            cura = re.findall(r'name="cura:(\w+)"[^>]*>([^<]*)<', text)
            if cura:
                found["cura"] = sorted({f"{k}={v}" for k, v in cura if k in KEYS})
    return found


def run(name: str) -> dict[str, object]:
    program, printer = PROGRAMS[name]
    printer = PRINTERS.get(name, printer)
    folder = OUT / RUN / name
    folder.mkdir(parents=True, exist_ok=True)
    row: dict[str, object] = {
        "program": name,
        "case": CASE,
        "material": MATERIAL,
        "printer": printer,
    }
    original = writer.part_advice
    h.CAPTURE.clear()
    h.CAPTURE["copy_dir"] = str(folder)
    try:
        profile = h.profiles.make_profile(printer, MATERIAL)
        setup, info = h.prepared(name, profile, MATERIAL)
        if setup is None:
            raise RuntimeError(info)
        if NO_VENDOR:
            # Solidons eigener Satz ohne Herstellerprofil (wie vendor=False im Slicertest).
            setup = h.handover.detect(h.SLICERS[name])
            info = {"flavour": setup.flavour, "note": "ohne Herstellerprofil"}
        elif setup.flavour != "cura":
            entries = h.found_profiles(setup.executable, setup.flavour, ("machine", "process"))
            machine, process = h.slicer_profiles.match(entries, profile.printer)
            if machine is None:
                raise RuntimeError("Kein Maschinenprofil des Herstellers")
            setup = dataclasses.replace(
                setup,
                machine_profile=h.slicer_profiles.identity(machine),
                base_process=h.slicer_profiles.identity(process) if process else "",
            )
        setup = h.manufacturer.for_stage(setup, profile, "standard")
        foundation = h.manufacturer.base_settings(profile, "standard", setup)
        standard = h.manufacturer.effective(None, foundation)
        row["profile"] = info
        row["base"] = {path: h.print_settings.read_path(standard, path) for path in RM587}
        settings = standard
        for path, value in (
            ("support.style", "grid" if SUPPORTED else "none"),
            ("support.placement", "everywhere"),
            ("adhesion.kind", "skirt"),
        ):
            settings = h.print_settings.with_choice(settings, path, value)
        shapes = bodies()
        # Nebeneinander, mit Luft: das Ziel links.
        for ident, x in (("ziel", -34.0), ("bezug", 34.0)):
            shapes[ident].apply_translation((x, 0.0, 0.0))
        objects = [
            SceneObject(id=ident, name=ident, mesh=MeshData(shapes[ident]))
            for ident in ("ziel", "bezug")
        ]
        towers = writer.tower_plates(objects, setup)
        if NATURAL:
            limit = h.profiles.for_process(profile, settings, effective=True)
            genuine = {
                obj.id: original(
                    obj,
                    obj.mesh,
                    settings,
                    profile,
                    setup,
                    {},
                    result=h.slice_body(
                        obj.mesh,
                        settings.layers.layer_height,
                        first_layer_height=settings.layers.first_layer_height,
                        overhang_angle=limit.overhang_limit_degrees,
                    ),
                    fit_kinds=(),
                    flavour=setup.flavour,
                    whole_layers=obj.plate in towers,
                )
                for obj in objects
            }
            row["genuine"] = {
                key: {item.path: item.value for item in entries if item.path in RM587}
                for key, entries in genuine.items()
            }
            combined = advise.combine(settings, [(settings, e) for e in genuine.values()])
            controls = {
                item.path: item.value
                for item in combined
                if item.path != "support.style"
                and h.slicer_keys.takes(setup.flavour, item.path, program=program)
            }
            row["offered_rm587"] = sorted(item.path for item in combined if item.path in RM587)
        else:
            controls = {
                path: value
                for path, value in controls_for(standard).items()
                if h.slicer_keys.takes(setup.flavour, path, program=program)
            }
            row["asked"] = controls_for(standard)
        for path, value in controls.items():
            settings = h.print_settings.with_accepted(settings, path, value)
        split = h.handover.split_for_parts(settings, profile, setup, setup.flavour)
        row.update(
            controls={k: v for k, v in controls.items() if k in RM587 or not NATURAL},
            per_part=sorted(set(split.per_part) & set(RM587)),
            unavailable=sorted(set(split.unavailable) & set(RM587)),
            plate={path: h.print_settings.read_path(split.plate, path) for path in RM587},
        )

        def controlled(entry, mesh, base, *_args, **_kwargs):
            if entry.id != "ziel":
                return []
            return [
                SettingAdvice(
                    path=path,
                    value=value,
                    was=h.print_settings.read_path(base, path),
                    reason="Kontrollierte Objektwertprobe RM-587",
                )
                for path, value in controls.items()
            ]

        writer.part_advice = original if NATURAL else controlled
        parts = [
            h.threemf.AssemblyPart(mesh=obj.mesh, slots=h.threemf.slots_for_object(obj))
            for obj in objects
        ]
        slots = h.threemf.merge_slots(parts)
        settings = dataclasses.replace(settings, slot_profiles=tuple("" for _ in slots))
        project, findings = writer.write_assembly(
            objects,
            folder,
            project_name="bruecken",
            profile=profile,
            plate=0,
            settings=settings,
            flavour=setup.flavour,
            place_on_bed=True,
            setup=setup,
            job=objects,
        )
        row["findings"] = [entry.code for entry in findings]
        row["written"] = written(project)
        outcome = h.handover.slice_model(
            [project],
            settings,
            profile,
            setup,
            output_dir=folder,
            timeout=600,
            keep_arrangement=True,
            slots=h.handover.with_slot_profiles(slots, settings.slot_profiles),
            model_height=max(float(obj.mesh.bounds.maximum[2]) for obj in objects),
            expected_tools=h.threemf.tools_in_use(parts),
        )
        row["gcode"] = str(outcome.gcode_path)
        row.update(measured(Path(outcome.gcode_path)))
        row["ok"] = True
    except Exception as error:
        row.update(ok=False, error=f"{type(error).__name__}: {error}", trace=traceback.format_exc())
    finally:
        writer.part_advice = original
        row["commands"] = [
            {key: entry.get(key) for key in ("command", "returncode", "seconds")}
            for entry in h.CAPTURE.get("commands", [])
        ]
        (folder / "ergebnis.json").write_text(
            json.dumps(row, ensure_ascii=False, indent=1, default=str), encoding="utf-8"
        )
    return row


CENTRES = (
    re.compile(r"EXCLUDE_OBJECT_DEFINE NAME=(ziel|bezug)\S* CENTER=([-\d.]+),([-\d.]+)"),
    re.compile(r'"name":"(ziel|bezug)".*?"object_center":\[([-\d.]+),([-\d.]+)'),
)
OBJECTS_INFO = re.compile(r"^; objects_info = (\{.*\})\s*$")
PRINTING = re.compile(r'^; printing object "?(ziel|bezug)"? ')
#: Bambu Studio nennt keine Namen, nur Kennungen in Ladefolge: die erste ist das Ziel.
BAMBU_IDS = re.compile(r"^; model label id: (\d+),(\d+)", re.MULTILINE)
BAMBU_START = re.compile(r"^; start printing object, unique label id: (\d+)")
LAYER = re.compile(r"^;\s*(?:LAYER\s*:\s*-?\d+|LAYER_CHANGE|CHANGE_LAYER)\s*$", re.IGNORECASE)
BRIDGE_TYPES = ("bridge", "bridge infill", "overhang bridge")
OUTER_TYPES = ("outer wall", "external perimeter", "wall-outer")
FAN = re.compile(r"^M106(?:\s+P(\d+))?.*?\sS(\d+(?:\.\d+)?)")


def areas(gcode: Path) -> tuple[tuple[float, ...], tuple[float, ...], str]:
    """Die Bereiche beider Körper (wie ``kontakt_je_teil.areas``)."""
    points: list[tuple[float, float]] = []
    named: dict[str, list[tuple[float, float]]] = {"ziel": [], "bezug": []}
    label = None
    kind = None
    x = y = e = 0.0
    relative = False
    bambu: dict[str, str] = {}
    with gcode.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            ids = BAMBU_IDS.match(line)
            if ids:
                bambu = {ids.group(1): "ziel", ids.group(2): "bezug"}
            started = BAMBU_START.match(line)
            if started and started.group(1) in bambu:
                label = bambu[started.group(1)]
            for pattern in CENTRES:
                found = pattern.search(line)
                if found:
                    named[found.group(1)].append((float(found.group(2)), float(found.group(3))))
            info = OBJECTS_INFO.match(line)
            if info:
                for entry in json.loads(info.group(1))["objects"]:
                    if entry["name"] in named:
                        corners = entry["polygon"]
                        named[entry["name"]].append(
                            (
                                sum(c[0] for c in corners) / len(corners),
                                sum(c[1] for c in corners) / len(corners),
                            )
                        )
            printing = PRINTING.match(line)
            if printing:
                label = printing.group(1)
            elif line.startswith("; stop printing object"):
                label = None
            typed = gcode_kontakt.TYPED.match(line)
            if typed:
                kind = gcode_kontakt.kind_of(typed.group(1))
                continue
            if line.startswith("M83"):
                relative = True
            elif line.startswith("M82"):
                relative = False
            if not gcode_kontakt.MOVE.match(line):
                continue
            values = {k: float(v) for k, v in gcode_kontakt.NUMBER.findall(line.split(";")[0])}
            new_x, new_y = values.get("X", x), values.get("Y", y)
            extruded = "E" in values and (values["E"] > 0.0 if relative else values["E"] > e)
            if "E" in values and not relative:
                e = values["E"]
            if extruded and kind == "model" and (new_x, new_y) != (x, y):
                points.append((new_x, new_y))
                if label is not None:
                    named[label].append((new_x, new_y))
            x, y = new_x, new_y
    best = (0.0, 0, 0.0)
    for axis in (0, 1):
        ordered = sorted({round(point[axis], 1) for point in points})
        for low, high in itertools.pairwise(ordered):
            if high - low > best[0]:
                best = (high - low, axis, (low + high) / 2.0)
    _gap, axis, threshold = best
    low_box = (-1e9, threshold, -1e9, 1e9) if axis == 0 else (-1e9, 1e9, -1e9, threshold)
    high_box = (threshold, 1e9, -1e9, 1e9) if axis == 0 else (-1e9, 1e9, threshold, 1e9)
    if named["ziel"]:
        mean = sum(point[axis] for point in named["ziel"]) / len(named["ziel"])
        source = "Name"
    else:
        mean, source = threshold - 1.0, "links (Cura)"
    target_low = mean < threshold
    target, reference = (low_box, high_box) if target_low else (high_box, low_box)
    return target, reference, f"{'XY'[axis]} {threshold:g}, Ziel über {source}"


def inside(area: tuple[float, ...], x: float, y: float) -> bool:
    return area[0] <= x <= area[1] and area[2] <= y <= area[3]


def toolpath(
    gcode: Path, area: tuple[float, ...] | None, label: str | None = None
) -> dict[str, object]:
    """Stütze, äußere Brücke und Drehsinn der Außenwand eines Körpers: zwischen seinen
    Objektmarken (label) oder, ohne Marken, innerhalb eines Bereichs."""
    current = None
    bambu: dict[str, str] = {}
    support = 0.0
    bridge_length = bridge_feed = 0.0
    speeds: list[float] = []
    fans: list[float] = []
    turns: list[bool] = []
    wall_area = 0.0
    kind_name = ""
    x = y = e = 0.0
    feed = 0.0
    fan = 0.0
    relative = False
    with gcode.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            ids = BAMBU_IDS.match(line)
            if ids:
                bambu = {ids.group(1): "ziel", ids.group(2): "bezug"}
            started = BAMBU_START.match(line)
            printing = PRINTING.match(line)
            if started and started.group(1) in bambu:
                current = bambu[started.group(1)]
            elif printing:
                current = printing.group(1)
            elif line.startswith("; stop printing object"):
                current = None
            if LAYER.match(line):
                if abs(wall_area) > 1.0:
                    turns.append(wall_area > 0.0)
                wall_area = 0.0
                continue
            typed = gcode_kontakt.TYPED.match(line)
            if typed:
                kind_name = typed.group(1).strip().lower()
                continue
            if line.startswith("M83"):
                relative = True
            elif line.startswith("M82"):
                relative = False
            elif line.startswith("G92") and " E" in line:
                e = float(re.search(r"E(-?[\d.]+)", line).group(1))
            elif line.startswith("M107"):
                fan = 0.0
            elif line.startswith("M106"):
                found = FAN.match(line)
                if found and (found.group(1) in (None, "0", "1")):
                    fan = float(found.group(2))
            if not re.match(r"^G[0-3]\b", line):
                continue
            values = {k: float(v) for k, v in gcode_kontakt.NUMBER.findall(line.split(";")[0])}
            if "F" in values:
                feed = values["F"]
            new_x, new_y = values.get("X", x), values.get("Y", y)
            amount = 0.0
            if "E" in values:
                amount = values["E"] if relative else values["E"] - e
                if not relative:
                    e = values["E"]
            moved = math.hypot(new_x - x, new_y - y)
            mine = (
                current == label
                if label is not None
                else area is not None and inside(area, (x + new_x) / 2, (y + new_y) / 2)
            )
            if amount > 0.0 and moved > 0.0 and mine:
                kind = gcode_kontakt.kind_of(kind_name)
                if kind in ("support", "interface"):
                    support += moved
                if kind_name in BRIDGE_TYPES:
                    bridge_length += moved
                    bridge_feed += amount
                    speeds.append(feed / 60.0)
                    fans.append(fan)
                if kind_name in OUTER_TYPES:
                    wall_area += x * new_y - new_x * y
            x, y = new_x, new_y
    if abs(wall_area) > 1.0:
        turns.append(wall_area > 0.0)
    return {
        "support_mm": round(support),
        "bridge_mm": round(bridge_length, 1),
        "bridge_feed": round(bridge_feed, 2),
        "bridge_feed_per_mm": round(bridge_feed / bridge_length, 4) if bridge_length else None,
        "bridge_speed": statistics.median(speeds) if speeds else None,
        "bridge_fan": statistics.median(fans) if fans else None,
        "wall_layers": len(turns),
        "wall_changes": sum(1 for a, b in itertools.pairwise(turns) if a != b),
    }


def measured(gcode: Path) -> dict[str, object]:
    text = gcode.read_text(encoding="utf-8", errors="replace")
    marked = re.search(r'^; printing object "?(ziel|bezug)', text, re.MULTILINE) or (
        BAMBU_IDS.search(text) is not None
    )
    if marked:
        return {
            "split": "Objektmarken",
            "ziel": toolpath(gcode, None, "ziel"),
            "bezug": toolpath(gcode, None, "bezug"),
        }
    target, reference, split = areas(gcode)
    return {
        "split": split,
        "ziel": toolpath(gcode, target),
        "bezug": toolpath(gcode, reference),
    }


if __name__ == "__main__":
    for name in sys.argv[4:]:
        if os.environ.get("SONDE_NUR_MESSEN"):
            stored = OUT / RUN / name / "ergebnis.json"
            result = json.loads(stored.read_text(encoding="utf-8"))
            if result.get("gcode"):
                result.update(measured(Path(result["gcode"])), ok=True)
                stored.write_text(
                    json.dumps(result, ensure_ascii=False, indent=1, default=str),
                    encoding="utf-8",
                )
        else:
            result = run(name)
        if result.get("ok"):
            print(
                CASE,
                name,
                "Werte",
                result["controls"],
                "je Teil",
                result["per_part"],
                "nicht",
                result["unavailable"],
                flush=True,
            )
            print(
                "  geschrieben",
                json.dumps(result["written"]["objects"], ensure_ascii=False),
                flush=True,
            )
            print("  Teilung", result["split"], flush=True)
            print("  ziel ", result["ziel"], flush=True)
            print("  bezug", result["bezug"], flush=True)
        else:
            print(CASE, name, "FEHLER", result.get("error"), flush=True)
