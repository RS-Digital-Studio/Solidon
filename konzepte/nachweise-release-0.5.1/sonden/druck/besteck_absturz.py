"""RM-252: Warum stürzt die Orca-Familie am Besteckeinsatz mit Gitterstützen ab?

    python besteck_absturz.py <baum> <arbeitsordner> <slicer> [variante,...]

Varianten, je ein Lauf über ``write_assembly`` + ``handover.slice_model`` wie das
Korpuswerkzeug: ``gitter`` (Solidons Übergabe, ``support_base_pattern =
rectilinear-grid``), ``gitter_ohne_muster`` (dieselbe, aber das Muster schweigt —
das Herstellerprofil gilt), ``gitter_rectilinear`` (Muster ``rectilinear``),
``baum``, ``standard``.
"""

import sys
from dataclasses import replace
from pathlib import Path

TREE = sys.argv[1]
sys.path.insert(0, TREE)
sys.path.insert(0, str(Path(TREE) / ".claude/.state/uebergabe-korpus-2026-09-26"))
import app  # noqa: E402

print("app:", app.__file__, flush=True)
assert Path(app.__file__).resolve().is_relative_to(Path(TREE).resolve()), app.__file__
import lauf  # noqa: E402

from app.core.bootstrap import load_operations  # noqa: E402
from app.core.export import handover, slicer_keys, slicer_profiles  # noqa: E402
from app.core.knowledge import print_settings, profiles  # noqa: E402

load_operations()
work = Path(sys.argv[2])
slicer = sys.argv[3]
chosen = sys.argv[4].split(",") if len(sys.argv) > 4 else [
    "standard",
    "gitter",
    "gitter_ohne_muster",
    "gitter_rectilinear",
    "baum",
]
objects, _ = lauf.imported_objects(Path("F:/3D Dateien/Modern++Cutlery+Organizer+with+Divider.3mf"))
for entry in objects:
    print("Körper", entry.name, [round(float(v), 1) for v in entry.mesh.bounds.size], flush=True)
executable, printer = lauf.SLICERS[slicer]
profile = profiles.make_profile(printer, "pla")
setup = handover.detect(executable)
machine, process = slicer_profiles.match(
    list(slicer_profiles.find_profiles(Path(executable), setup.flavour, ("machine", "process"))),
    profile.printer,
)
setup = replace(
    setup,
    machine_profile=machine.name if machine else "",
    base_process=process.name if process else "",
)
standard = print_settings.resolve(profile)
grid = print_settings.with_path(standard, "support.style", "grid")
tree = print_settings.with_path(standard, "support.style", "tree")
original = slicer_keys.TABLES["orca"]


def with_pattern(value: str | None) -> tuple:
    rows = []
    for entry in original:
        if entry.key == "support_base_pattern":
            if value is None:
                continue
            rows.append(entry._replace(write=lambda _v, value=value: value))
        else:
            rows.append(entry)
    return tuple(rows)


def only_switch() -> tuple:
    """Von allen Stützschlüsseln nur ``enable_support`` und ``support_type`` —
    der Rest kommt aus dem Herstellerprofil."""
    return tuple(
        entry
        for entry in original
        if not entry.key.startswith("support_") or entry.key == "support_type"
    )


variants = {
    "standard": (standard, None),
    "gitter": (grid, None),
    "gitter_ohne_muster": (grid, with_pattern(None)),
    "gitter_rectilinear": (grid, with_pattern("rectilinear")),
    "baum": (tree, None),
    "gitter_nur_an": (grid, only_switch()),
}
import trimesh  # noqa: E402

from app.core.geom.mesh import MeshData  # noqa: E402

raw = trimesh.load(
    "F:/3D Dateien/Modern++Cutlery+Organizer+with+Divider.3mf", force="mesh", process=False
)
print("Original ohne Solidons Reparatur:", len(raw.faces), "Dreiecke, dicht", raw.is_watertight)
original_objects = objects
for name in chosen:
    objects = original_objects
    if name.endswith("_roh"):
        # Dasselbe, aber mit dem Netz, wie es in der Datei steht — ohne
        # Einlesen und Reparatur, auf dieselbe Lage gelegt.
        body = raw.copy()
        body.apply_translation(
            original_objects[0].mesh.bounds.centre - body.bounds.mean(axis=0)
        )
        objects = [replace(original_objects[0], mesh=MeshData.of(body))]
        name = name[: -len("_roh")]
    settings, table = variants[name]
    slicer_keys.TABLES["orca"] = table if table is not None else original
    row = lauf.one_run(name, objects, settings, profile, setup, work / f"{slicer}_{name}")
    slicer_keys.TABLES["orca"] = original
    print(
        f"{slicer} {name}: ok={row.get('ok')} {row.get('print_minutes')} min "
        f"Stütze {row.get('support_m')} m {row.get('seconds')} s {row.get('error', '')} "
        f"{str(row.get('values', {}).get('output', ''))[-200:]}",
        flush=True,
    )
