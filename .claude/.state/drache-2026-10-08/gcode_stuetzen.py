"""Welcher Anteil der Überhänge hat im G-Code Stütze darunter?

Aufruf: python gcode_stuetzen.py <code-wurzel> <netz.stl> <ausgabe.json> <gcode> [<gcode> …]

Solidons Überhangstücke (Schichtanalyse mit dem CC2-Profil, Schwelle wie die
Übergabe) werden über die Stützbahnen des G-Codes gelegt. Ein Stück gilt als
gestützt, wenn in den Schichten bis 1,2 mm unter ihm Stützbahn in seinem
Grundriss (um 1 mm aufgeweitet) liegt. Die Lage des Modells auf dem Bett kommt
aus dem G-Code: Mitte der Modellbahnen gegen Mitte des Netzes.

Ausgabe je Datei: gestützte Fläche gesamt und je 10-mm-Band, Inseln einzeln,
Stützbahn in m.
"""

from __future__ import annotations

import json
import math
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(sys.argv[1]).resolve()
sys.path.insert(0, str(ROOT))

import numpy as np  # noqa: E402
import shapely  # noqa: E402
import trimesh  # noqa: E402
from shapely.geometry import Polygon as ShapelyPolygon  # noqa: E402

from app.core.bootstrap import load_operations  # noqa: E402

load_operations()

from app.core.export import writer  # noqa: E402
from app.core.geom.mesh import MeshData  # noqa: E402
from app.core.knowledge import print_settings, profiles  # noqa: E402
from app.core.types import SceneObject  # noqa: E402

TYPE = re.compile(r"^;\s*(?:TYPE|FEATURE)\s*:\s*(.+?)\s*$", re.IGNORECASE)
WORD = re.compile(r"([XYZEF])(-?(?:\d+\.?\d*|\.\d+))")
SKIP = ("brim", "skirt", "prime", "wipe", "custom", "purge", "flush")


def read(path: Path) -> tuple[list[tuple[float, float, float, float, float]], np.ndarray]:
    """Stützsegmente (x0, y0, x1, y1, z) und Punkte der Modellbahnen."""
    support: list[tuple[float, float, float, float, float]] = []
    model: list[tuple[float, float, float]] = []
    x = y = z = 0.0
    e_abs = 0.0
    relative_e = False
    kind = ""
    with path.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            if line.startswith(";"):
                found = TYPE.match(line.strip())
                if found:
                    kind = found.group(1).lower()
                continue
            code = line.split(";", 1)[0].strip().upper()
            if not code:
                continue
            if code.startswith("M83"):
                relative_e = True
                continue
            if code.startswith("M82"):
                relative_e = False
                continue
            if code.startswith("G92"):
                for letter, value in WORD.findall(code):
                    if letter == "E":
                        e_abs = float(value)
                continue
            if not (code.startswith("G1") or code.startswith("G0")):
                if code.startswith(("G2", "G3")):
                    pass
                else:
                    continue
            values = dict(WORD.findall(code[2:]))
            nx = float(values["X"]) if "X" in values else x
            ny = float(values["Y"]) if "Y" in values else y
            nz = float(values["Z"]) if "Z" in values else z
            extruding = False
            if "E" in values:
                e = float(values["E"])
                delta = e if relative_e else e - e_abs
                if not relative_e:
                    e_abs = e
                extruding = delta > 1e-5
            if extruding and (nx != x or ny != y):
                if "support" in kind or "tree" in kind:
                    support.append((x, y, nx, ny, nz))
                elif kind and not any(word in kind for word in SKIP):
                    model.append((nx, ny, nz))
            x, y, z = nx, ny, nz
    return support, np.asarray(model)


def main() -> int:
    mesh_path = Path(sys.argv[2])
    out = Path(sys.argv[3])
    raw = trimesh.load(mesh_path, process=False)
    mesh = MeshData.of(raw)
    entry = SceneObject(id="obj_1", name="Drache", mesh=mesh)
    profile = profiles.make_profile("centauri-carbon-2", "pla")
    settings = print_settings.resolve(profile)
    result = writer._body_analysis(entry, mesh, settings, profile, None, detail="support")
    # Kanaldecken nach dem Stand der Code-Wurzel: Ihre Stütze soll fehlen (eine
    # Sperre hält sie heraus), also zählt der Anteil ohne sie getrennt.
    from app.core.slice.analysis import model_support

    channels = model_support(result).channels
    pieces = []
    for index, layer in enumerate(result.layers):
        for number, piece in enumerate(layer.overhangs):
            shape = ShapelyPolygon(piece.outline, piece.holes)
            if shape.area >= 0.5:
                pieces.append((float(layer.z), shape, (index, number) in channels))
    islands = []
    for layer in result.layers:
        for piece in layer.islands:
            shape = ShapelyPolygon(piece.outline, piece.holes)
            if shape.area >= 0.5:
                islands.append((float(layer.z), shape))
    footprint = None
    section = raw.section(plane_origin=[0.0, 0.0, 0.1], plane_normal=[0.0, 0.0, 1.0])
    for loop in section.discrete:
        if len(loop) >= 4:
            ring = shapely.Polygon(loop[:, :2]).buffer(0)
            footprint = ring if footprint is None else footprint.symmetric_difference(ring)
    grown_foot = footprint.buffer(0.6)
    shapely.prepare(grown_foot)
    foot_low, foot_high = np.array(footprint.bounds[:2]), np.array(footprint.bounds[2:])
    foot_centre = (foot_low + foot_high) / 2.0
    report = {}
    for name in sys.argv[4:]:
        path = Path(name)
        support, model = read(path)
        # Die Lage auf dem Bett: Drehung um die Hochachse und Verschiebung, so
        # dass die erste Schicht des G-Codes auf der Standfläche des Netzes
        # liegt — manche Slicer drehen beim Anordnen (Creality Print).
        first = model[model[:, 2] <= model[:, 2].min() + 0.05][:, :2]
        if len(first) > 3000:
            first = first[:: len(first) // 3000]

        def placed(points, angle):
            turn = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
            turned = points @ turn.T
            low, high = turned.min(axis=0), turned.max(axis=0)
            return (
                turned + (foot_centre - (low + high) / 2.0),
                turn,
                foot_centre - (low + high) / 2.0,
            )

        def score(angle):
            moved, _turn, _shift = placed(first, angle)
            return float(shapely.contains_xy(grown_foot, moved[:, 0], moved[:, 1]).mean())

        coarse = max(np.radians(np.arange(0.0, 360.0, 1.0)), key=score)
        fine = max(coarse + np.radians(np.arange(-1.0, 1.01, 0.1)), key=score)
        fit = score(fine)
        _moved, turn, offset = placed(first, fine)
        segments = np.asarray(support) if support else np.zeros((0, 5))
        centres = np.column_stack(
            ((segments[:, 0] + segments[:, 2]) / 2.0, (segments[:, 1] + segments[:, 3]) / 2.0)
        )
        aligned = centres @ turn.T + offset
        mids = np.column_stack((aligned[:, 0], aligned[:, 1], segments[:, 4]))
        shift = [float(np.degrees(fine)) % 360.0, fit]
        lengths = np.hypot(segments[:, 2] - segments[:, 0], segments[:, 3] - segments[:, 1])
        by_layer: dict[float, np.ndarray] = defaultdict(lambda: np.zeros((0, 2)))
        levels = np.round(mids[:, 2], 2)
        for level in np.unique(levels):
            by_layer[float(level)] = mids[levels == level][:, :2]
        heights = np.array(sorted(by_layer))

        def supported(z: float, shape: ShapelyPolygon) -> bool:
            near = heights[(heights <= z - 0.05) & (heights >= z - 1.2)]
            if not len(near):
                return False
            grown = shape.buffer(1.0)
            shapely.prepare(grown)
            for level in near:
                points = by_layer[float(level)]
                if len(points) and shapely.contains_xy(grown, points[:, 0], points[:, 1]).any():
                    return True
            return False

        bands: dict[int, list[float]] = defaultdict(lambda: [0.0, 0.0])
        total = held = 0.0
        open_total = open_held = 0.0
        loose: list[list[float]] = []
        for z, shape, channel in pieces:
            ok = supported(z, shape)
            if not channel:
                open_total += shape.area
                open_held += shape.area if ok else 0.0
            band = int(z // 10) * 10
            bands[band][0] += shape.area
            total += shape.area
            if ok:
                bands[band][1] += shape.area
                held += shape.area
            else:
                point = shape.representative_point()
                loose.append(
                    [round(z, 2), round(point.x, 1), round(point.y, 1), round(shape.area, 2)]
                )
        island_rows = [
            (round(z, 2), round(shape.area, 1), supported(z, shape))
            for z, shape in islands
            if shape.area >= 2.0
        ]
        report[str(path)] = {
            "support_m": round(float(lengths.sum()) / 1000.0, 2),
            "overhang_mm2": round(total, 1),
            "supported_share": round(held / total, 3) if total else math.nan,
            "open_share": round(open_held / open_total, 3) if open_total else math.nan,
            "channel_mm2": round(total - open_total, 1),
            "bands": {
                band: [round(value[0], 1), round(value[1] / value[0], 2) if value[0] else None]
                for band, value in sorted(bands.items())
            },
            "islands_supported": f"{sum(1 for row in island_rows if row[2])}/{len(island_rows)}",
            "islands_unsupported": [row[:2] for row in island_rows if not row[2]][:20],
            "shift": [round(float(value), 2) for value in shift],
        }
        print(path, json.dumps(report[str(path)], ensure_ascii=False), flush=True)
        report[str(path)]["unsupported_pieces"] = sorted(loose, key=lambda row: -row[3])
    out.write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
