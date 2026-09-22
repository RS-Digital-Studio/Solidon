"""Unabhängige Kernsonde für Mittelpunkt und Rolle nativer Kugelabschnitte.

Exit 1 hält die tatsächlich beobachteten Vertragsverletzungen fest. Die
Sonde verändert keine Produktdatei und schreibt ausschließlich ihre beiden
Berichte neben dieses Skript. Nutzerverzeichnisse liegen vor jedem
Produktimport in einer privaten temporären Umgebung.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from collections import Counter
from importlib.metadata import version


ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).with_suffix(".json")
SOURCES = (
    "app/core/brep/features.py",
    "app/core/brep/canonical.py",
    "app/core/brep/kernel.py",
    "app/core/brep/properties.py",
    "app/core/perceive/features.py",
    "app/core/geom/mesh.py",
)


def source_hashes() -> dict[str, str]:
    """Den geprüften gemeinsamen Arbeitsstand ohne Produktänderung benennen."""
    return {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCES}


def measure() -> dict:
    """Zwei analytische Körper in drei starren Lagen vollständig erkennen."""
    import numpy as np
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Transform
    from OCP.BRepCheck import BRepCheck_Analyzer
    from OCP.BRepGProp import BRepGProp
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeSphere
    from OCP.BRepTools import BRepTools
    from OCP.GeomAbs import GeomAbs_Sphere
    from OCP.GProp import GProp_GProps
    from OCP.gp import gp_Ax1, gp_Dir, gp_Pnt, gp_Trsf, gp_Vec

    from app.core.brep.features import features_of
    from app.core.brep.kernel import DEFLECTION, Solid
    from app.core.geom.mesh import as_mesh_data
    from app.core.perceive.features import detect, forget_cache
    from app.core.units import EPS_GEOM

    def native_bytes(shape) -> bytes:
        """Die native Form einschließlich ihrer Geometrie vergleichen."""
        stream = io.BytesIO()
        BRepTools.Write_s(shape, stream)
        return stream.getvalue()

    def mesh_hash(mesh) -> str:
        """Echte Punkt- und Dreiecksdaten vor und nach der Erkennung vergleichen."""
        digest = hashlib.sha256(np.asarray(mesh.raw.vertices).tobytes())
        digest.update(np.asarray(mesh.raw.faces).tobytes())
        return digest.hexdigest()

    def described(found, expected) -> dict:
        """Auch ein fehlendes Kugelmerkmal bleibt eine ausdrückliche Auskunft."""
        spheres = []
        for feature in found.values():
            if feature.kind != "sphere":
                continue
            centre = list(feature.params["centre"])
            spheres.append(
                {
                    "id": feature.id,
                    "centre_mm": centre,
                    "centre_error_mm": math.dist(centre, expected),
                    "diameter_mm": float(feature.params["diameter"]),
                    "recess": feature.params.get("recess"),
                    "face_count": len(feature.face_indices or ()),
                }
            )
        return {
            "kind_counts": dict(sorted(Counter(item.kind for item in found.values()).items())),
            "spheres": spheres,
            "sphere_missing": not spheres,
        }

    data = {
        "command": ".venv/Scripts/python.exe .claude/.state/cad-durchsicht-2026-09-19/p12-native-sphere-probe.py",
        "head": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "python": sys.version,
        "versions": {
            name: version(name)
            for name in ("cadquery-ocp-novtk", "cadquery-ocp-proxy", "numpy", "scipy", "trimesh")
        },
        "source_sha256_before": source_hashes(),
        "units": "mm",
        "deflection_mm": DEFLECTION,
        "seed": None,
        "tolerance_mm": EPS_GEOM,
        "scope": "Reine analytische Kernsonde; keine Fenster-, Leistungs- oder Releaseprüfung.",
        "cases": [],
    }
    turn_axis = np.asarray((1.0, 2.0, -0.5))
    turn_axis /= np.linalg.norm(turn_axis)
    poses = (
        ("origin", (0.0, 0.0, 0.0), 0.0),
        ("translated", (37.0, -19.0, 83.0), 0.0),
        ("rotated_translated", (37.0, -19.0, 83.0), 0.73),
    )
    radius = 8.0
    for name, lower in (("hemisphere", 0.0), ("upper_cap", 4.0)):
        for pose_name, offset, angle in poses:
            maker = BRepPrimAPI_MakeSphere(radius, math.asin(lower / radius), math.pi / 2.0)
            original = maker.Shape()
            original_before = native_bytes(original)
            transform = gp_Trsf()
            transform.SetRotation(gp_Ax1(gp_Pnt(0.0, 0.0, 0.0), gp_Dir(*turn_axis)), angle)
            transform.SetTranslationPart(gp_Vec(*offset))
            placed = BRepBuilderAPI_Transform(original, transform, True).Shape()
            solid = Solid(placed)
            before = native_bytes(solid.shape)

            # Die Sollwerte folgen den Konstruktionsparametern, keinem Fit.
            height = radius - lower
            expected_volume = math.pi * height**2 * (3.0 * radius - height) / 3.0
            axis = np.asarray((0.0, 0.0, 1.0))
            turned_axis = (
                axis * math.cos(angle)
                + np.cross(turn_axis, axis) * math.sin(angle)
                + turn_axis * float(turn_axis @ axis) * (1.0 - math.cos(angle))
            )
            expected_face_centre = np.asarray(offset) + turned_axis * (radius + lower) / 2.0
            volume_props = GProp_GProps()
            BRepGProp.VolumeProperties_s(solid.shape, volume_props)
            source_surfaces = []
            for face in solid.faces():
                surface = BRepAdaptor_Surface(face)
                if surface.GetType() == GeomAbs_Sphere:
                    ball = surface.Sphere()
                    source_surfaces.append(
                        {"radius_mm": ball.Radius(), "centre_mm": list(ball.Location().Coord())}
                    )

            native = described(features_of(solid), offset)
            after_native = native_bytes(solid.shape)
            mesh = as_mesh_data(solid)
            after_tessellation = native_bytes(solid.shape)
            mesh_before = mesh_hash(mesh)
            forget_cache()
            meshed = described(detect(mesh), offset)
            preserved = {
                "builder_source": original_before == native_bytes(original),
                "native_after_features": before == after_native,
                "native_after_tessellation": before == after_tessellation,
                "native_after_mesh_detect": before == native_bytes(solid.shape),
                "mesh_after_detect": mesh_before == mesh_hash(mesh),
            }
            violations = []
            if not BRepCheck_Analyzer(solid.shape).IsValid():
                violations.append("invalid_source_solid")
            if abs(volume_props.Mass() - expected_volume) > EPS_GEOM:
                violations.append("source_volume")
            for path, result in (("native", native), ("mesh", meshed)):
                if len(result["spheres"]) != 1:
                    violations.append(f"{path}_sphere_count")
                for sphere in result["spheres"]:
                    if sphere["centre_error_mm"] > EPS_GEOM:
                        violations.append(f"{path}_sphere_centre")
                    if sphere["recess"] is not False:
                        violations.append(f"{path}_sphere_role")
            if not all(preserved.values()):
                violations.append("source_mutated")
            data["cases"].append(
                {
                    "case": f"{name}_{pose_name}",
                    "radius_mm": radius,
                    "lower_z_before_transform_mm": lower,
                    "rotation_axis": turn_axis.tolist(),
                    "rotation_radians": angle,
                    "translation_mm": list(offset),
                    "expected_centre_mm": list(offset),
                    "expected_recess": False,
                    "expected_surface_centroid_mm": expected_face_centre.tolist(),
                    "expected_volume_mm3": expected_volume,
                    "measured_native_volume_mm3": volume_props.Mass(),
                    "native_source_spheres": source_surfaces,
                    "triangle_count": mesh.triangle_count,
                    "native": native,
                    "mesh": meshed,
                    "original_preserved": preserved,
                    "native_sha256_before": hashlib.sha256(before).hexdigest(),
                    "native_sha256_after": hashlib.sha256(native_bytes(solid.shape)).hexdigest(),
                    "violations": violations,
                }
            )
    data["source_sha256_after"] = source_hashes()
    data["product_sources_unchanged_during_probe"] = (
        data["source_sha256_before"] == data["source_sha256_after"]
    )
    return data


def main() -> int:
    """Die Beobachtungen vollständig speichern; Fehler werden nicht übergangen."""
    sys.path.insert(0, str(ROOT))
    with tempfile.TemporaryDirectory(prefix="solidon-p12-native-sphere-") as scratch:
        for key in ("APPDATA", "LOCALAPPDATA", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
            os.environ[key] = str(Path(scratch) / key.lower())
        data = measure()
    lines = [
        "P1.2: Mittelpunkt und Materialseite analytischer R8-Kugelabschnitte",
        f"HEAD: {data['head']}; Tessellierung: {data['deflection_mm']} mm",
        "Soll: Kugelzentrum = Translation; beide massiven Abschnitte recess=False.",
        "",
    ]
    for case in data["cases"]:
        lines.extend(
            [
                case["case"],
                f"  Sollmittelpunkt: {case['expected_centre_mm']}",
                f"  Native Kugeln: {json.dumps(case['native']['spheres'], ensure_ascii=False)}",
                f"  Mesh-Kugeln: {json.dumps(case['mesh']['spheres'], ensure_ascii=False)}",
                f"  Mesh-Arten: {case['mesh']['kind_counts']}",
                f"  Originalerhalt: {case['original_preserved']}",
                f"  Vertragsverletzungen: {case['violations']}",
            ]
        )
    failed = any(case["violations"] for case in data["cases"])
    data["exit_code"] = int(failed or not data["product_sources_unchanged_during_probe"])
    lines.extend(
        [
            "",
            f"Geprüfte Produktquellen während der Sonde unverändert: {data['product_sources_unchanged_during_probe']}",
            f"Exit: {data['exit_code']} (1 bedeutet beobachtete Vertragsverletzungen, kein grüner Prüflauf).",
        ]
    )
    OUTPUT.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    report = "\n".join(lines) + "\n"
    OUTPUT.with_suffix(".txt").write_text(report, encoding="utf-8")
    print(report)
    return data["exit_code"]


if __name__ == "__main__":
    raise SystemExit(main())
