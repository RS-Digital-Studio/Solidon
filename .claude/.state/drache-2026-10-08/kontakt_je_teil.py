"""RM-583: Kommen Stützabstand und Trennschichten als Objektwert im Slicer an?

Aufruf: python kontakt_je_teil.py <ausgabe> <programm> …   (Material über SONDE_MATERIAL)

Zwei gleiche Stufenkörper — Sockel, Säule, Platte darüber —, beide gestützt. Die
Stütze steht auf dem Sockel und trägt die Platte, so zeigt sich der Kontakt oben
und unten. Das linke Teil (``ziel``) bekommt Abstand, Trennschichten oben und
unten und die Lücke als Objektwert, jeweils weit weg von der Herstellervorgabe;
das rechte (``bezug``) behält die Platte. Gemessen wird im G-Code je Körper
(:mod:`gcode_kontakt` mit Bereich).

Der Rat ist kontrolliert (``writer.part_advice`` ersetzt, wie die Sonde aus
RM-317); Aufteilung, Dateischreiber, Konfiguration und Sliceraufruf bleiben echt.
Mit ``SONDE_NATUERLICH=1`` ist er echt: Das Ziel ist aus PLA, der Bezug aus PETG,
übernommen wird, was der Rat beider Teile zusammen vorschlägt, und jedes Teil
bekommt den Kontakt nach dem Material seiner Spule.
Die Gegenprüfung aus ``F:/solidon-review-reports/gcode/rest`` liefert Programme,
Herstellerprofile und den Mitschnitt des Aufrufs.
"""

from __future__ import annotations

import dataclasses
import importlib.util
import itertools
import json
import os
import re
import sys
import traceback
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = Path(sys.argv[1]).resolve()
TREE = HERE.parents[2]
os.environ.update(PYTHONUTF8="1", ABZUG=str(TREE), GC=str(OUT), GP_LAUF="kontakt")
spec = importlib.util.spec_from_file_location(
    "gp", r"F:\solidon-review-reports\gcode\rest\gegenpruefung.py"
)
assert spec is not None and spec.loader is not None
h = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = h
spec.loader.exec_module(h)
sys.path.insert(0, str(HERE))

import gcode_kontakt  # noqa: E402
import trimesh  # noqa: E402

from app.core.export import writer  # noqa: E402
from app.core.geom.mesh import MeshData  # noqa: E402
from app.core.slice import advise  # noqa: E402
from app.core.types import SceneObject, SettingAdvice  # noqa: E402

h.SLICERS["anycubic"] = Path(r"C:\Program Files\AnycubicSlicerNext\AnycubicSlicerNext.exe")
PROGRAMS = {
    # Der eingebaute CC2 trifft Elegoos Maschinenprofil derzeit nicht (RM-600);
    # gemessen wird mit dem aus dem Slicer übernommenen.
    "elegoo": ("elegooslicer", "slicer-orca-af8733f715e1dfb0606b"),
    "orca": ("orcaslicer", "slicer-orca-af8733f715e1dfb0606b"),
    "bambu": ("bambustudio", "bambu-p1s"),
    "creality": ("crealityprint", "creality-k1"),
    "anycubic": ("anycubicslicernext", "anycubic-kobra-2"),
    "prusa": ("prusaslicer", "prusa-mini"),
    "superslicer": ("superslicer", "prusa-mini"),
    "cura": ("cura", "sovol-sv06"),
}
MATERIAL = os.environ.get("SONDE_MATERIAL", "pla")
NATURAL = os.environ.get("SONDE_NATUERLICH") == "1"
#: Das Material je Körper in der natürlichen Betriebsart.
MATERIALS = dict(
    zip(("ziel", "bezug"), os.environ.get("SONDE_MATERIALIEN", "pla,petg").split(","), strict=True)
)
#: Eine eigene Schichthöhe über dem Standardprozess (RM-622: 0,08 mm).
LAYER = float(os.environ.get("SONDE_SCHICHT", "0") or 0.0)
#: Der Stand vor RM-622: Der Rat weiß nichts vom Reinigungsturm.
WITHOUT_TOWER = os.environ.get("SONDE_OHNE_TURM") == "1"
#: Die Stützart statt ``grid`` (``tree``: organische Bäume des Programms).
STYLE = os.environ.get("SONDE_STIL", "grid")
RUN = (
    ("natuerlich-" + "-".join(MATERIALS.values()) if NATURAL else MATERIAL)
    + (f"-{LAYER:g}" if LAYER else "")
    + ("-ohne-turm" if WITHOUT_TOWER else "")
    + (f"-{STYLE}" if STYLE != "grid" else "")
)
PATHS = (
    "support.z_gap",
    "support.interface_layers",
    "support.bottom_interface_layers",
    "support.interface_spacing",
)


def body(x: float) -> trimesh.Trimesh:
    slab = trimesh.creation.box(extents=(36.0, 36.0, 3.0))
    slab.apply_translation([x, 0.0, 1.5])
    column = trimesh.creation.box(extents=(8.0, 8.0, 10.2))
    column.apply_translation([x, 0.0, 8.0])
    roof = trimesh.creation.box(extents=(36.0, 36.0, 2.0))
    roof.apply_translation([x, 0.0, 14.0])
    return trimesh.boolean.union([slab, column, roof], engine="manifold")


def controls_for(standard) -> dict[str, object]:
    """Je Pfad ein Wert weit weg von der Herstellervorgabe."""
    read = h.print_settings.read_path
    gap = float(read(standard, "support.z_gap"))
    layers = int(read(standard, "support.interface_layers"))
    bottom = int(read(standard, "support.bottom_interface_layers"))
    spacing = float(read(standard, "support.interface_spacing"))
    return {
        "support.z_gap": 0.4 if gap < 0.3 else 0.2,
        "support.interface_layers": 5 if layers <= 3 else 1,
        "support.bottom_interface_layers": 0 if bottom > 0 else 3,
        "support.interface_spacing": 1.2 if spacing < 0.8 else 0.2,
    }


#: Wo ein Programm den Mittelpunkt eines benannten Körpers nennt.
CENTRES = (
    re.compile(r"EXCLUDE_OBJECT_DEFINE NAME=(ziel|bezug)\S* CENTER=([-\d.]+),([-\d.]+)"),
    re.compile(r'"name":"(ziel|bezug)".*?"object_center":\[([-\d.]+),([-\d.]+)'),
)
#: PrusaSlicer: ``objects_info`` mit dem Umriss je Körper.
OBJECTS_INFO = re.compile(r"^; objects_info = (\{.*\})\s*$")
#: Orca-Familie: Beginn eines Körpers in der Schicht.
PRINTING = re.compile(r'^; printing object "?(ziel|bezug)"? ')


def areas(gcode: Path) -> tuple[tuple[float, ...], tuple[float, ...], str]:
    """Die Bereiche beider Körper, getrennt an der größten Lücke zwischen den
    Modellbahnen in X oder Y; welcher das Ziel ist, sagt der Name im G-Code.
    Cura nennt keine Namen, behält aber die Anordnung: Das Ziel liegt links."""
    points: list[tuple[float, float]] = []
    named: dict[str, list[tuple[float, float]]] = {"ziel": [], "bezug": []}
    label = None
    kind = None
    x = y = e = 0.0
    relative = False
    with gcode.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
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


def run(name: str) -> dict[str, object]:
    program, printer = PROGRAMS[name]
    folder = OUT / RUN / name
    folder.mkdir(parents=True, exist_ok=True)
    row: dict[str, object] = {"program": name, "material": MATERIAL, "printer": printer}
    original = writer.part_advice
    h.CAPTURE.clear()
    h.CAPTURE["copy_dir"] = str(folder)
    try:
        profile = h.profiles.make_profile(printer, MATERIAL)
        setup, info = h.prepared(name, profile, MATERIAL)
        if setup is None:
            raise RuntimeError(info)
        if setup.flavour != "cura":
            # Die Wahl trägt die Kennung des Profils, nicht seinen Namen (RM-317).
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
        settings = standard
        for path, value in (
            ("support.style", STYLE),
            ("support.placement", "everywhere"),
            ("adhesion.kind", "skirt"),
        ):
            settings = h.print_settings.with_choice(settings, path, value)
        if LAYER:
            settings = h.print_settings.with_choice(settings, "layers.layer_height", LAYER)
        objects = [
            SceneObject(
                id=ident,
                name=ident,
                mesh=MeshData(body(x)),
                material=MATERIALS[ident] if NATURAL else None,
            )
            for ident, x in (("ziel", -26.0), ("bezug", 26.0))
        ]
        if WITHOUT_TOWER:
            writer.tower_plates = lambda *_args, **_kwargs: frozenset()
        towers = writer.tower_plates(objects, setup)
        row["towers"] = sorted(towers)
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
                key: {item.path: item.value for item in entries} for key, entries in genuine.items()
            }
            controls = {
                item.path: item.value
                for item in advise.combine(settings, [(settings, e) for e in genuine.values()])
            }
        else:
            controls = {
                path: value
                for path, value in controls_for(standard).items()
                if h.slicer_keys.takes(setup.flavour, path, program=program)
            }
        for path, value in controls.items():
            settings = h.print_settings.with_accepted(settings, path, value)
        split = h.handover.split_for_parts(settings, profile, setup, setup.flavour)
        row.update(
            controls=controls,
            per_part=sorted(split.per_part),
            unavailable=sorted(split.unavailable),
            plate={path: h.print_settings.read_path(split.plate, path) for path in PATHS},
        )

        def controlled(entry, mesh, base, *_args, **_kwargs):
            if entry.id != "ziel":
                return []
            return [
                SettingAdvice(
                    path=path,
                    value=value,
                    was=h.print_settings.read_path(base, path),
                    reason="Kontrollierte Objektwertprobe RM-583",
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
            project_name="kontakt",
            profile=profile,
            plate=0,
            settings=settings,
            flavour=setup.flavour,
            place_on_bed=True,
            setup=setup,
            job=objects,
        )
        row["findings"] = [entry.code for entry in findings]
        outcome = h.handover.slice_model(
            [project],
            settings,
            profile,
            setup,
            output_dir=folder,
            timeout=600,
            keep_arrangement=True,
            slots=h.handover.with_slot_profiles(slots, settings.slot_profiles),
            model_height=15.0,
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


def off_grid_levels(gcode: Path) -> int:
    """Wie viele Ebenen nicht auf dem Raster der Modellschichten liegen — die
    eigenen Höhen der Stütze (``independent_support_layer_height``)."""
    levels: set[float] = set()
    with gcode.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith((";Z:", "; Z_HEIGHT:")):
                levels.add(round(float(line.split(":", 1)[1]), 4))
    ordered = sorted(levels)
    if len(ordered) < 3:
        return 0
    steps = sorted(round(b - a, 4) for a, b in itertools.pairwise(ordered))
    layer = max(set(steps), key=steps.count)
    first = ordered[0]
    return sum(
        1
        for level in ordered
        if abs((level - first) / layer - round((level - first) / layer)) > 1e-3
    )


def measured(gcode: Path) -> dict[str, object]:
    target, reference, split = areas(gcode)
    return {
        "split": split,
        "off_grid_levels": off_grid_levels(gcode),
        "ziel": gcode_kontakt.measure(gcode, target),
        "bezug": gcode_kontakt.measure(gcode, reference),
    }


def short(side: dict[str, object]) -> str:
    keys = (
        "top_gap",
        "top_interface_layers",
        "bottom_gap",
        "bottom_interface_layers",
        "interface_mm_per_level",
    )
    return " ".join(f"{key}={side.get(key)}" for key in keys)


if __name__ == "__main__":
    for name in sys.argv[2:]:
        if os.environ.get("SONDE_NUR_MESSEN"):
            # Nachmessen ohne neuen Slicerlauf: dieselbe Druckdatei, neue Messung.
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
            print(name, "Werte", result["controls"], "je Teil", result["per_part"], flush=True)
            print("  Teilung", result["split"], flush=True)
            print("  Zwischenebenen", result.get("off_grid_levels"), flush=True)
            print("  ziel ", short(result["ziel"]), flush=True)  # type: ignore[arg-type]
            print("  bezug", short(result["bezug"]), flush=True)  # type: ignore[arg-type]
        else:
            print(name, "FEHLER", result.get("error"), flush=True)
