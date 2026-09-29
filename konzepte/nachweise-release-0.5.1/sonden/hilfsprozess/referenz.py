"""Bitgleich zum alten Weg? Abdrücke der Kernergebnisse vor und nach dem Umbau (RM-212).

Rechnet jede Funktion, deren ``manifold3d``-Teil in den Hilfsprozess wandert, an
Korpus- und Kundennetzen und schreibt je Fall einen SHA-256 über Eckpunkte,
Dreiecke, Slots und gemeldete Zahlen. Vor dem Umbau am unveränderten Stand
gefahren, danach noch einmal — zweimal im Prozess, einmal über den erzwungenen
Hilfsprozess (dritter Parameter ``hilfsprozess``: Schwelle null, Aufruf aus
einem Nebenfaden). Die drei Dateien müssen gleich sein.

Aufruf (gebunden, aus dem Arbeitsbaum):
python ../sonden/hilfsprozess/referenz.py <baum> <ausgabe.json> [hilfsprozess]

Alles Rechnen steht unter ``__main__``: Der Hilfsprozess lädt das Hauptmodul
seines Elternprozesses noch einmal (``spawn``).
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import threading
import time
from pathlib import Path

TREE = Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else Path.cwd()
sys.path.insert(0, str(TREE))
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else Path("referenz.json")
FORCED = len(sys.argv) > 3 and sys.argv[3] == "hilfsprozess"

import numpy as np  # noqa: E402
import trimesh  # noqa: E402

CORPUS = TREE / "tests" / "data" / "meshes"
MODELS = {
    "wuerfel": Path(r"F:\3D Dateien\dice_w6_16mm_v00.stl"),
    "spiderman": Path(r"F:\3D Dateien\spiderman+voronoi+bambu+10cm_stls\obj_1_spiderman.stl"),
    "schuessel": Path(r"F:\3D Dateien\HydroBowl+–+Smart+Fruit+&+Veggie+Washer (1)\washing bowl v1.stl"),
}


def load(path: Path) -> "MeshData":
    # Verschweißt wie beim Import (trimesh ``process=True``): Der Kern nimmt
    # nur geschlossene Netze, ``read_mesh`` liefert die rohe Dreieckssuppe.
    return MeshData.of(trimesh.load(str(path), force="mesh"))


def fingerprint(value: object) -> str:
    from app.core.geom.mesh import MeshData

    digest = hashlib.sha256()

    def feed(item: object) -> None:
        if isinstance(item, MeshData):
            feed(np.asarray(item.raw.vertices))
            feed(np.asarray(item.raw.faces))
            feed(tuple(item.slots))
            return
        if isinstance(item, np.ndarray):
            digest.update(item.dtype.str.encode())
            digest.update(repr(item.shape).encode())
            digest.update(np.ascontiguousarray(item).tobytes())
            return
        if isinstance(item, (tuple, list)):
            digest.update(b"(")
            for part in item:
                feed(part)
            digest.update(b")")
            return
        digest.update(repr(item).encode())

    feed(value)
    return digest.hexdigest()


def subdivided_five(mesh: "MeshData") -> "MeshData":
    body = mesh.raw
    vertices, faces = np.asarray(body.vertices), np.asarray(body.faces)
    for _ in range(5):
        vertices, faces = trimesh.remesh.subdivide(vertices, faces)
    return MeshData.of(trimesh.Trimesh(vertices=vertices, faces=faces, process=False))


def cylinder_through(mesh: "MeshData", radius: float) -> "MeshData":
    low, high = mesh.bounds.minimum, mesh.bounds.maximum
    centre = [(low[0] + high[0]) / 2.0, (low[1] + high[1]) / 2.0, (low[2] + high[2]) / 2.0]
    height = float(high[2] - low[2]) + 4.0
    tool = trimesh.creation.cylinder(radius=radius, height=height, sections=48)
    tool.apply_translation(centre)
    return MeshData.of(tool)


def box(size: float, offset: tuple[float, float, float]) -> "MeshData":
    body = trimesh.creation.box(extents=(size, size, size))
    body.apply_translation(offset)
    return MeshData.of(body)


cases: dict[str, object] = {}
timings: dict[str, float] = {}


def case(name: str, work) -> None:
    started = time.perf_counter()
    try:
        value = work()
        cases[name] = fingerprint(value)
    except Exception as problem:  # noqa: BLE001 — die Ausnahme ist Teil des Abdrucks
        cases[name] = f"{type(problem).__name__}: {problem}"
    timings[name] = time.perf_counter() - started
    print(f"  {name:<40} {timings[name]:7.2f} s  {str(cases[name])[:24]}", flush=True)


def run_all() -> None:
    plate = load(CORPUS / "plate_holes.stl")
    sunk = load(CORPUS / "plate_countersunk.stl")
    socket = load(CORPUS / "sphere_socket.stl")
    torus = load(CORPUS / "torus_ring.stl")
    cube = load(CORPUS / "cube_clean.stl")
    dice = load(MODELS["wuerfel"])
    spider = load(MODELS["spiderman"])
    bowl = load(MODELS["schuessel"])
    plate5 = subdivided_five(plate)
    sunk5 = subdivided_five(sunk)
    print(
        f"geladen: Würfel {dice.triangle_count}, Spiderman {spider.triangle_count}, "
        f"Schüssel {bowl.triangle_count}, Lochplatte x5 {plate5.triangle_count}, "
        f"Senkplatte x5 {sunk5.triangle_count}",
        flush=True,
    )

    case("anzeige wuerfel 50000", lambda: mesh_ops.decimate_for_display(dice, 50_000))
    case("anzeige spiderman 150000", lambda: mesh_ops.decimate_for_display(spider, 150_000))
    case("anzeige lochplatte5 150000", lambda: mesh_ops.decimate_for_display(plate5, 150_000))
    case("anzeige schuessel 50000", lambda: mesh_ops.decimate_for_display(bowl, 50_000))
    case("anzeige senkplatte5 sag", lambda: mesh_ops.decimate_for_display(sunk5, 20_000, sag=0.2))
    case("verringern wuerfel 60000", lambda: mesh_ops._decimate_with_solver(dice, 60_000))
    case("verringern lochplatte5 50000", lambda: mesh_ops._decimate_with_solver(plate5, 50_000))
    case("verringern senkplatte5 30000", lambda: mesh_ops._decimate_with_solver(sunk5, 30_000))
    case("flach lochplatte5", lambda: mesh_ops._exactly_flattened(plate5, None))
    case("rueckfall wuerfel 60000", lambda: mesh_ops._manifold_decimation(dice, 60_000, None))
    case("verfeinern wuerfel 0.5", lambda: mesh_ops.remesh(dice, 0.5))
    case("verfeinern lochplatte 1.0", lambda: mesh_ops.remesh(plate, 1.0))
    case("verfeinern senkplatte 0.5", lambda: mesh_ops.remesh(sunk, 0.5))
    case("angleichen lochplatte 1.0 0", lambda: mesh_ops.uniform(plate, 1.0, 0.0))
    case("angleichen wuerfel 0.5 0.01", lambda: mesh_ops.uniform(dice, 0.5, 0.01))
    case("unterteilen kugelpfanne 1.0", lambda: mesh_ops.subdivided(socket, 1.0, 52.5))
    case("teilen lochplatte 2.0", lambda: mesh_ops.refined(plate, 2.0))
    case("teilen torus 0.5", lambda: mesh_ops.refined(torus, 0.5))
    case(
        "bool differenz lochplatte5",
        lambda: boolean_module.boolean("difference", [plate5, cylinder_through(plate5, 3.0)]).mesh,
    )
    case(
        "bool differenz wuerfel",
        lambda: boolean_module.boolean("difference", [dice, cylinder_through(dice, 1.5)]).mesh,
    )
    case(
        "bool vereinigung torus wuerfel",
        lambda: boolean_module.boolean("union", [torus, cube]).mesh,
    )
    case(
        "bool schnitt kaesten",
        lambda: boolean_module.boolean(
            "intersection", [box(10.0, (0, 0, 0)), box(10.0, (4.0, 3.0, 2.0))]
        ).mesh,
    )
    case(
        "bool kontakt kaesten",
        lambda: boolean_module.boolean(
            "intersection",
            [box(10.0, (0, 0, 0)), box(10.0, (10.0, 0, 0))],
            allow_empty=True,
            stages=("direct",),
        ).mesh,
    )
    case(
        "narben lochplatte5",
        lambda: prepare_ops._without_scars(
            boolean_module.boolean("union", [plate5, cylinder_through(plate5, 2.0)])
        ).mesh,
    )
    case("abstand kaesten", lambda: surface_gap(box(10.0, (0, 0, 0)), box(10.0, (12.5, 0, 0)), 5.0))
    case("abstand lochplatte5", lambda: surface_gap(plate5, box(10.0, (0, 0, 40.0)), 50.0))


def main() -> None:
    import app

    assert str(Path(app.__file__).resolve()).startswith(str(TREE)), app.__file__
    from app.core import bootstrap

    bootstrap.load_operations()
    global boolean_module, mesh_ops, prepare_ops, surface_gap, MeshData
    from app.core.geom import boolean as boolean_module
    from app.core.geom import mesh_ops, prepare_ops
    from app.core.geom.measure import surface_gap
    from app.core.geom.mesh import MeshData

    if FORCED:
        # Der Hilfsprozess rechnet nur für Nebenfäden — im Hauptfaden wartete
        # er genauso wie der Kern selbst.
        from app.core.geom import kernel_process

        kernel_process.OFFLOAD_ABOVE = 0
        worker = threading.Thread(target=run_all, name="sonde")
        worker.start()
        worker.join()
        print("Hilfsprozess:", kernel_process.statistics(), flush=True)
        kernel_process.shutdown()
    else:
        run_all()
    OUT.write_text(json.dumps(cases, indent=1, sort_keys=True), encoding="utf-8")
    print("geschrieben:", OUT, flush=True)


if __name__ == "__main__":
    main()
