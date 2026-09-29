"""Schrägnaht je Teil in jedem Slicer: Rohr und Klotz auf einer Platte.

Aufruf: python naht_abnahme.py <code-wurzel> <ausgabeordner> [slicer ...]

Der Weg der Anwendung: Einrichtung wie die Vorwahl des Druckdialogs,
Grundlage des Herstellers, ``shell.scarf_seam`` übernommen (oder nicht),
``write_assembly`` und ``handover.slice_model``. Gezählt werden je Objekt die
Außenwandschleifen mit einer Z-Rampe — die Schrägnaht — und die Druckzeit.
"""

from __future__ import annotations

import json
import re
import sys
import time
from dataclasses import replace
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv[1]).resolve()))

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()

import trimesh  # noqa: E402

from app.core.export import handover, manufacturer, slicer_profiles, threemf  # noqa: E402
from app.core.export.writer import arrangement_holds, write_assembly  # noqa: E402
from app.core.geom.mesh import MeshData, as_mesh_data  # noqa: E402
from app.core.knowledge import print_settings, profiles  # noqa: E402
from app.core.types import SceneObject  # noqa: E402

SLICERS: dict[str, str] = {
    "elegoo": r"C:\Program Files\ElegooSlicer\elegoo-slicer.exe",
    "orca": r"C:\Program Files\OrcaSlicer\orca-slicer.exe",
    "bambu": r"C:\Program Files\Bambu Studio\bambu-studio.exe",
    "creality": r"C:\Program Files\Creality\Creality Print 7.2\CrealityPrint.exe",
    "prusa": r"C:\Program Files\Prusa3D\PrusaSlicer\prusa-slicer-console.exe",
    "cura": r"C:\Program Files\UltiMaker Cura 5.13.0\CuraEngine.exe",
}
HOME: dict[str, str] = {
    "elegoo": "centauri-carbon-2",
    "orca": "anycubic-kobra-2",
    "bambu": "bambu-p1s",
    "creality": "creality-k1",
    "prusa": "prusa-mk4s",
    "cura": "sovol-sv06",
}
#: Wie die Programme die Außenwand im G-Code nennen — Orca-Familie und Bambu
#: („; FEATURE:“), PrusaSlicer, Cura.
OUTER = frozenset({"Outer wall", "External perimeter", "WALL-OUTER"})
WORD = re.compile(r"([XYZE])(-?[\d.]+)")


def prepared(slicer: str, profile: object) -> handover.SlicerSetup:
    """Der Slicer, wie der Druckdialog ihn vorwählt."""
    exe = Path(SLICERS[slicer])
    setup = handover.detect(exe)
    if setup.flavour not in ("orca", "prusa"):
        return setup
    found = list(slicer_profiles.find_profiles(exe, setup.flavour, ("machine", "process")))
    machine, process = slicer_profiles.match(found, profile.printer)  # type: ignore[attr-defined]
    if machine is None:
        return setup
    roots = slicer_profiles.profile_roots(setup.flavour, exe)
    filaments = list(slicer_profiles.find_profiles(exe, setup.flavour, ("filament",)))
    filament = slicer_profiles.match_filament(filaments, machine, "PLA", roots)
    return replace(
        setup,
        machine_profile=machine.name,
        base_process=process.name if process else "",
        base_filament=slicer_profiles.identity(filament) if filament else "",
    )


def bodies() -> list[SceneObject]:
    """Ein Rohr Ø 25 × 40 mm und ein Klotz 25 × 25 × 40 mm, 60 mm auseinander."""
    tube = trimesh.creation.cylinder(radius=12.5, height=40.0, sections=128)
    tube.apply_translation((-30.0, 0.0, 20.0))
    block = trimesh.creation.box(extents=(25.0, 25.0, 40.0))
    block.apply_translation((30.0, 0.0, 20.0))
    return [
        SceneObject(id="obj_1", name="Rohr", mesh=MeshData.of(tube)),
        SceneObject(id="obj_2", name="Klotz", mesh=MeshData.of(block)),
    ]


def ramps(gcode: Path, flavour: str) -> dict[str, int]:
    """Außenwandschleifen mit Z-Rampe je Objekt (Cura: je Netz, Bambu: je
    Kennung)."""
    del flavour
    counted: dict[str, int] = {}
    owner = ""
    in_outer = False
    heights: set[float] = set()
    z = 0.0

    def close() -> None:
        nonlocal heights
        if in_outer and len(heights) > 1:
            counted[owner] = counted.get(owner, 0) + 1
        heights = set()

    with gcode.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith("; printing object "):
                close()
                owner = line[18:].split(" id:")[0].strip()
                continue
            if line.startswith("; start printing object, unique label id:"):
                close()
                owner = "id " + line.rsplit(":", 1)[1].strip()
                continue
            if line.startswith(";MESH:"):
                close()
                owner = Path(line[6:].strip()).name
                continue
            if line.startswith((";TYPE:", "; FEATURE:")):
                close()
                in_outer = line.split(":", 1)[1].strip() in OUTER
                continue
            if not line.startswith(("G1", "G2", "G3")):
                continue
            words = dict(WORD.findall(line.split(";")[0]))
            if "Z" in words:
                z = float(words["Z"])
            if in_outer and float(words.get("E", 0)) > 0 and ("X" in words or "Y" in words):
                heights.add(round(z, 3))
            elif "X" in words or "Y" in words:
                close()
    close()
    return counted


def run(slicer: str, scarf: bool, folder: Path) -> dict[str, object]:
    profile = profiles.make_profile(HOME[slicer], "pla")
    setup = prepared(slicer, profile)
    foundation = manufacturer.base_settings(profile, "standard", setup)
    settings = manufacturer.effective(None, foundation)
    if scarf:
        settings = print_settings.with_accepted(settings, "shell.scarf_seam", True)
    objects = bodies()
    folder.mkdir(parents=True, exist_ok=True)
    meshes = [as_mesh_data(entry.mesh) for entry in objects]
    keep = arrangement_holds(meshes, profile)
    parts = [threemf.AssemblyPart(mesh=mesh, slots=threemf.slots_for_object(entry)) for entry, mesh in zip(objects, meshes, strict=True)]
    slots = threemf.merge_slots(parts)
    chosen = tuple("" for _ in slots)
    started = time.perf_counter()
    written, findings = write_assembly(
        objects, folder, project_name="naht", profile=profile,
        settings=replace(settings, slot_profiles=chosen), flavour=setup.flavour,
        place_on_bed=keep, setup=setup,
    )
    outcome = handover.slice_model(
        [written], settings, profile, setup, output_dir=folder, keep_arrangement=keep,
        slots=handover.with_slot_profiles(slots, chosen), model_height=40.0,
        expected_tools=threemf.tools_in_use(parts),
    )
    return {
        "slicer": slicer,
        "printer": HOME[slicer],
        "scarf": scarf,
        "process": setup.base_process,
        "minutes": round((outcome.metrics.print_seconds or 0) / 60.0, 2),
        "ramps": ramps(Path(outcome.gcode_path), setup.flavour),
        "part_setting": [
            (f.values.get("objects"), f.values.get("setting"))
            for f in findings
            if f.code == "export.part_setting"
        ],
        "gcode": str(outcome.gcode_path),
        "seconds": round(time.perf_counter() - started, 1),
    }


def main() -> None:
    target = Path(sys.argv[2])
    chosen = sys.argv[3:] or list(SLICERS)
    rows = []
    for slicer in chosen:
        for scarf in (False, True):
            try:
                row = run(slicer, scarf, target / slicer / ("mit" if scarf else "ohne"))
            except Exception as problem:  # noqa: BLE001 — eine Abnahme berichtet alles
                row = {"slicer": slicer, "scarf": scarf, "error": f"{type(problem).__name__}: {problem}"[:400]}
            rows.append(row)
            print(json.dumps(row, ensure_ascii=False), flush=True)
    (target / "ergebnis.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
