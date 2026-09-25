"""Sonde 1: Erkennung am unbeschädigten, am beschädigten und am reparierten Netz.

Die Kundendateien sind fast alle dicht (Sonde 0). Damit die Reparatur etwas
zu tun bekommt, werden typische Netzfehler gezielt eingesetzt — an einem
erkannten Merkmal oder verstreut — und danach mit ``geom.repair.repair`` so
behoben, wie der Reparaturschritt es tut. Verglichen wird die Erkennung
roh (P), beschädigt (D) und repariert (R): Art, Anzahl, Maße, Laufzeit, und
wem die neuen Fülldreiecke zugeschlagen wurden.

Aufruf: python p1_schaden_reparatur.py [modellfilter]
"""

from __future__ import annotations

import math
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, r"F:\3D Druck")

import numpy as np  # noqa: E402
import trimesh  # noqa: E402

from app.core.geom.mesh import MeshData  # noqa: E402
from app.core.geom.repair import open_edge_count, repair  # noqa: E402
from app.core.ingest import threemf  # noqa: E402
from app.core.ingest.loader import normalise, read_model  # noqa: E402
from app.core.perceive.features import detect, forget_cache  # noqa: E402

REPO = Path(r"F:\3D Druck")
KUNDEN = Path(r"F:\3D Dateien")
OUT = Path(__file__).with_suffix(".txt")

MODELS = [
    REPO / "tests/data/meshes/plate_holes.stl",
    REPO / "tests/data/meshes/plate_countersunk.stl",
    REPO / "tests/data/meshes/post_with_fillet.stl",
    REPO / "tests/data/meshes/block_with_rounded_edge.stl",
    REPO / "tests/data/meshes/plate_coarse_slots.stl",
    KUNDEN / "Wedge-Lock (Base).stl",
    KUNDEN / "peg.stl",
    KUNDEN / "1x1-bin.stl",
    KUNDEN / "desk-organizer-v3_desk-organizer-v3_body1.stl",
    KUNDEN / "large-screwdriver-holder-with-honeycomb-pattern.stl",
    KUNDEN / "the-over-engineered-backpack-wall-mount-v2.stl",
    KUNDEN / "broomholdervcd_d35mm.stl",
    KUNDEN / "Siebhalter+X1C.3mf",
]

DIMS = ("diameter", "tube_diameter", "radius", "length", "travel", "angle", "area", "depth")


def load(path: Path) -> list[tuple[str, MeshData]]:
    payload = path.read_bytes()
    if path.suffix.lower() == ".3mf":
        parts = threemf.read_objects(payload, [])
        return [(part.name, normalise(part.mesh, "mm").mesh) for part in parts[:2]]
    return [(path.stem, normalise(read_model(payload, path.suffix), "mm").mesh)]


def timed_detect(mesh: MeshData):
    forget_cache()
    start = time.perf_counter()
    found = detect(mesh)
    return found, time.perf_counter() - start


def dims(feature) -> dict[str, float]:
    return {
        key: float(feature.params[key])
        for key in DIMS
        if isinstance(feature.params.get(key), int | float)
        and not isinstance(feature.params.get(key), bool)
    }


def label(feature) -> str:
    shown = ", ".join(f"{key}={value:.3f}" for key, value in dims(feature).items())
    centre = feature.params.get("centre")
    where = (
        "(" + ", ".join(f"{float(value):.2f}" for value in centre) + ")"
        if isinstance(centre, tuple | list)
        else "?"
    )
    return f"{feature.kind}[{shown}] @ {where} n={len(feature.face_indices)}"


def same(one, two, diagonal: float) -> bool:
    if one.kind != two.kind:
        return False
    a, b = one.params.get("centre"), two.params.get("centre")
    if not isinstance(a, tuple | list) or not isinstance(b, tuple | list):
        return False
    if float(np.linalg.norm(np.asarray(a, float) - np.asarray(b, float))) > max(
        0.3, 0.005 * diagonal
    ):
        return False
    first, second = dims(one), dims(two)
    for key in ("diameter", "tube_diameter", "length", "angle"):
        if key in first and key in second:
            scale = max(abs(first[key]), abs(second[key]), 1e-9)
            if abs(first[key] - second[key]) / scale > 0.02:
                return False
    return True


def compare(reference: dict, other: dict, diagonal: float) -> tuple[list, list]:
    left = list(other.values())
    missing = []
    for feature in reference.values():
        partner = next((entry for entry in left if same(feature, entry, diagonal)), None)
        if partner is None:
            missing.append(feature)
        else:
            left.remove(partner)
    return missing, left


def neighbours(mesh: MeshData) -> dict[int, set[int]]:
    table: dict[int, set[int]] = {}
    for a, b in np.asarray(mesh.raw.face_adjacency).tolist():
        table.setdefault(a, set()).add(b)
        table.setdefault(b, set()).add(a)
    return table


def interior_patch(mesh: MeshData, faces: tuple[int, ...], count: int, seed: int) -> list[int]:
    """Eine zusammenhängende Gruppe von Dreiecken ganz im Inneren eines Merkmals."""
    owned = set(faces)
    table = neighbours(mesh)
    inner = [face for face in faces if table.get(face, set()) <= owned]
    if not inner:
        return []
    rng = np.random.default_rng(seed)
    start = inner[int(rng.integers(len(inner)))]
    chosen = [start]
    frontier = [start]
    while frontier and len(chosen) < count:
        face = frontier.pop(0)
        for other in sorted(table.get(face, ())):
            if other in owned and other not in chosen and table.get(other, set()) <= owned:
                chosen.append(other)
                frontier.append(other)
                if len(chosen) >= count:
                    break
    return chosen


def without(mesh: MeshData, gone: list[int]) -> MeshData:
    keep = np.ones(mesh.triangle_count, dtype=bool)
    keep[gone] = False
    return MeshData.of(
        trimesh.Trimesh(
            np.asarray(mesh.raw.vertices), np.asarray(mesh.raw.faces)[keep], process=False
        )
    )


def flipped(mesh: MeshData, faces: list[int]) -> MeshData:
    triangles = np.asarray(mesh.raw.faces).copy()
    triangles[faces] = triangles[faces][:, ::-1]
    return MeshData.of(trimesh.Trimesh(np.asarray(mesh.raw.vertices), triangles, process=False))


def t_junctions(mesh: MeshData, count: int, seed: int) -> MeshData:
    """Je gewählter Kante nur das Dreieck auf einer Seite am Kantenmittelpunkt teilen."""
    body = mesh.raw
    vertices = np.asarray(body.vertices).tolist()
    triangles = np.asarray(body.faces).tolist()
    pairs = np.asarray(body.face_adjacency)
    edges = np.asarray(body.face_adjacency_edges)
    rng = np.random.default_rng(seed)
    used: set[int] = set()
    replaced: dict[int, list[list[int]]] = {}
    for row in rng.permutation(len(pairs))[: count * 4].tolist():
        face = int(pairs[row][0])
        if face in used or int(pairs[row][1]) in used:
            continue
        a, b = (int(value) for value in edges[row])
        corners = triangles[face]
        third = next(value for value in corners if value not in (a, b))
        middle = len(vertices)
        vertices.append(((np.asarray(vertices[a]) + np.asarray(vertices[b])) / 2.0).tolist())
        # Umlauf erhalten: (x, y, z) mit der Kante x->y wird zu (x, m, z) und (m, y, z).
        index = corners.index(a)
        if corners[(index + 1) % 3] == b:
            x, y = a, b
        else:
            x, y = b, a
        replaced[face] = [[x, middle, third], [middle, y, third]]
        used.update((face, int(pairs[row][1])))
        if len(replaced) >= count:
            break
    out = []
    for face, corners in enumerate(triangles):
        out.extend(replaced.get(face, [corners]))
    return MeshData.of(trimesh.Trimesh(np.asarray(vertices), np.asarray(out), process=False))


def seam(mesh: MeshData) -> MeshData:
    """Ein Riss: die Hälfte der Dreiecke bekommt eigene Eckkopien."""
    body = mesh.raw
    vertices = np.asarray(body.vertices)
    triangles = np.asarray(body.faces).copy()
    middle = np.median(np.asarray(body.triangles_center)[:, 0])
    upper = np.asarray(body.triangles_center)[:, 0] > middle
    copy = vertices.copy()
    offset = len(vertices)
    triangles[upper] = triangles[upper] + offset
    return MeshData.of(
        trimesh.Trimesh(np.vstack([vertices, copy]), triangles, process=False)
    )


def owners_of_new(repaired: MeshData, damaged: MeshData, found: dict) -> Counter:
    first_new = damaged.triangle_count
    counted: Counter = Counter()
    if repaired.triangle_count <= first_new:
        return counted
    new = set(range(first_new, repaired.triangle_count))
    claimed: set[int] = set()
    for feature in found.values():
        mine = new.intersection(feature.face_indices)
        if mine:
            counted[label(feature)] += len(mine)
            claimed |= mine
    counted["(niemand)"] = len(new - claimed)
    return counted


def case(out, name: str, pristine: MeshData, reference: dict, damaged: MeshData, what: str):
    diagonal = pristine.bounds.diagonal
    broken, took_d = timed_detect(damaged)
    fixed = repair(damaged)
    healed, took_r = timed_detect(fixed.mesh)
    out.write(f"\n## {name} — {what}\n")
    out.write(
        f"  D: tri={damaged.triangle_count} open={open_edge_count(damaged)} "
        f"wt={damaged.is_watertight}  R: tri={fixed.mesh.triangle_count} "
        f"open={open_edge_count(fixed.mesh)} wt={fixed.mesh.is_watertight} "
        f"changed={fixed.changed} codes={[entry.code for entry in fixed.findings]}\n"
    )
    out.write(
        f"  Arten P={dict(Counter(f.kind for f in reference.values()))}\n"
        f"        D={dict(Counter(f.kind for f in broken.values()))} ({took_d:.2f}s)\n"
        f"        R={dict(Counter(f.kind for f in healed.values()))} ({took_r:.2f}s)\n"
    )
    for tag, found in (("D", broken), ("R", healed)):
        missing, extra = compare(reference, found, diagonal)
        for feature in missing:
            if feature.kind in {"edge_loop"}:
                continue
            out.write(f"  {tag} fehlt:   {label(feature)}\n")
        for feature in extra:
            out.write(f"  {tag} neu:     {label(feature)}\n")
    for owner, count in owners_of_new(fixed.mesh, damaged, healed).most_common(8):
        out.write(f"  Fülldreiecke {count:4d} -> {owner}\n")
    out.flush()


def main() -> None:
    wanted = sys.argv[1] if len(sys.argv) > 1 else ""
    with OUT.open("a", encoding="utf-8") as out:
        for path in MODELS:
            if wanted and wanted.lower() not in path.name.lower():
                continue
            for name, pristine in load(path):
                reference, took = timed_detect(pristine)
                out.write(
                    f"\n# {path.name} / {name}: tri={pristine.triangle_count} "
                    f"wt={pristine.is_watertight} Erkennung {took:.2f}s "
                    f"{dict(Counter(f.kind for f in reference.values()))}\n"
                )
                out.flush()
                rng = np.random.default_rng(20260924)
                # 1: verstreute Einzellöcher
                count = max(3, pristine.triangle_count // 400)
                scattered = sorted(
                    set(rng.choice(pristine.triangle_count, size=count, replace=False).tolist())
                )
                table = neighbours(pristine)
                apart: list[int] = []
                for face in scattered:
                    if not table.get(face, set()) & set(apart):
                        apart.append(face)
                case(out, name, pristine, reference, without(pristine, apart),
                     f"{len(apart)} verstreute Einzeldreiecke fehlen")
                # 2: Loch mitten in je einem Merkmal jeder Art
                targets: dict[str, object] = {}
                for feature in reference.values():
                    if feature.kind in {"hole", "pin", "fillet", "cone", "torus", "slot", "face",
                                        "curved_face", "sphere"} and feature.kind not in targets:
                        if len(feature.face_indices) >= 12:
                            targets[feature.kind] = feature
                for kind, feature in targets.items():
                    for size in (2, 6):
                        patch = interior_patch(pristine, feature.face_indices, size, 7)
                        if len(patch) < size:
                            continue
                        case(out, name, pristine, reference, without(pristine, patch),
                             f"{size} Dreiecke fehlen in {label(feature)}")
                    region = list(feature.face_indices)
                    case(out, name, pristine, reference, flipped(pristine, region),
                         f"Normalen gedreht in {label(feature)}")
                # 3: T-Stöße verstreut
                case(out, name, pristine, reference,
                     t_junctions(pristine, max(3, pristine.triangle_count // 300), 11),
                     "T-Stöße verstreut")
                # 4: Riss mit doppelten Ecken
                case(out, name, pristine, reference, seam(pristine), "Riss (Ecken doppelt)")
                # 5: 5 % Normalen verstreut gedreht
                flips = rng.choice(pristine.triangle_count,
                                   size=max(1, pristine.triangle_count // 20),
                                   replace=False).tolist()
                case(out, name, pristine, reference, flipped(pristine, flips),
                     "5 % Normalen verstreut gedreht")


if __name__ == "__main__":
    main()
