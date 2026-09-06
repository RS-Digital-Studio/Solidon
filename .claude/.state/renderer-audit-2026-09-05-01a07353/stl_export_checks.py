"""Unabhängige STL-Prüfung nach echtem Dateidialog.

Integration in general_checks:
1. Direkt nach _persistence_move und vor dem ersten Export: expected = capture(probe).
2. Nach erfolgreichem STL-Export: verify(probe, expected, files).
   Dabei nur die tatsächlich neu geschriebenen Dateien dieses Exports übergeben.
   Die Prüfung läuft vor Wiederöffnen/Undo im eigenen CPU-Arbeiter.

STL trägt Dreiecke mit Float32-Koordinaten, keine Objektkennungen und keine
gemeinsam benutzten Vertex-Indizes. Verglichen werden deshalb orientierte
Dreiecksmengen in Weltkoordinaten nach genau dieser Quantisierung. Dateibytes,
Normalenbeilage, Dreiecksreihenfolge und zyklische Eckreihenfolge sind kein
Identitätskriterium. Umgedrehte Flächen und doppelte/fehlende Dreiecke fallen auf.
"""

from __future__ import annotations

import hashlib
import struct
import traceback
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np


def capture(probe):
    """Originale Weltgeometrie vor dem Export isolieren; keine Rendererkoordinaten."""
    result = probe.session.last_result
    if result is None:
        raise ValueError("Für die STL-Prüfung fehlt die ausgewertete Szene")
    snapshots = []
    for oid, entry in sorted(result.scene.objects.items()):
        raw = entry.mesh.raw
        snapshots.append({
            "id": str(oid), "name": str(entry.name), "plate": int(entry.plate),
            "vertices": np.array(raw.vertices, dtype=np.float64, copy=True),
            "faces": np.array(raw.faces, dtype=np.int64, copy=True),
        })
    if not snapshots:
        raise ValueError("Für die STL-Prüfung enthält die Szene keine Körper")
    return snapshots


def _read_binary_stl(path):
    """Binäres STL direkt aus seinem öffentlichen Datensatzformat lesen."""
    payload = path.read_bytes()
    if len(payload) < 84:
        raise ValueError(f"{path.name}: unvollständiger STL-Kopf")
    count = struct.unpack_from("<I", payload, 80)[0]
    if count == 0 or len(payload) != 84 + count * 50:
        raise ValueError(f"{path.name}: keine vollständige binäre STL-Dreiecksliste")
    record = np.dtype([
        ("normal", "<f4", (3,)), ("vertices", "<f4", (3, 3)), ("attribute", "<u2"),
    ])
    triangles = np.frombuffer(payload, dtype=record, count=count, offset=84)["vertices"]
    if not np.isfinite(triangles).all():
        raise ValueError(f"{path.name}: nichtendliche STL-Koordinaten")
    return np.array(triangles, dtype="<f4", copy=True)


def _triangle_keys(triangles):
    """Die orientierte Dreiecksmenge einschließlich jeder mehrfachen Fläche."""
    values = np.array(triangles, dtype="<f4", copy=True).reshape(-1, 3, 3)
    if not np.isfinite(values).all():
        raise ValueError("Die Weltkoordinaten sind nach Float32-Rundung nicht endlich")
    # Vorzeichen von Null hat keine geometrische Bedeutung.
    values[values == 0] = 0
    # Alle drei zyklischen Lagen vergleichen, auch bei entarteten Dreiecken
    # mit zwei identischen Ecken. Die Orientierung wird dabei nicht gespiegelt.
    ordering = tuple(
        np.roll(values[:, :, coordinate], -offset, axis=1)
        for offset in (2, 1, 0) for coordinate in (2, 1, 0)
    )
    first = np.lexsort(ordering, axis=1)[:, 0]
    cycle = (first[:, None] + np.arange(3)[None, :]) % 3
    ordered = np.take_along_axis(values, cycle[:, :, None], axis=1)
    records = np.ascontiguousarray(ordered).reshape(-1, 9).view("V36").reshape(-1)
    return np.sort(records)


def _identity(keys):
    """Ein Hash der kanonischen Welt-Dreiecke, ausdrücklich kein Dateihash."""
    return hashlib.sha256(keys.tobytes()).hexdigest()


def _metrics(vertices, faces):
    """Unabhängige Netzkennzahlen aus Kopien, ohne App-Export- oder Importpfad."""
    import trimesh

    mesh = trimesh.Trimesh(vertices=vertices, faces=faces, process=False)
    if not len(faces):
        raise ValueError("Ein leerer Körper kann keinen vollständigen STL-Export belegen")
    pieces = trimesh.graph.connected_components(
        mesh.face_adjacency, nodes=np.arange(len(faces)), engine="scipy",
    )
    return {
        "triangles": int(len(faces)), "bounds": mesh.bounds.tolist(),
        "volume": float(mesh.volume), "area": float(mesh.area),
        "watertight": bool(mesh.is_watertight),
        "winding_consistent": bool(mesh.is_winding_consistent),
        "components_by_shared_edges": len(pieces),
    }


def _stl_metrics(keys):
    """STL-Topologie beider Seiten identisch aus exakt gleichen Koordinaten ableiten."""
    triangles = keys.view("<f4").reshape(-1, 3, 3).astype(np.float64)
    vertices, inverse = np.unique(triangles.reshape(-1, 3), axis=0, return_inverse=True)
    return _metrics(vertices, inverse.reshape(-1, 3))


def inspect(snapshots, paths):
    """Die gesamte exportierte Weltgeometrie und ihre zulässige Dateiaufteilung prüfen."""
    paths = tuple(Path(path) for path in paths)
    if not paths or len(set(paths)) != len(paths):
        raise ValueError("Die STL-Prüfung braucht eine eindeutige Liste neu geschriebener Dateien")
    if any(path.suffix.lower() != ".stl" for path in paths):
        raise ValueError("Die STL-Prüfung bekam eine Datei in einem anderen Format")
    expected_parts = []
    expected_keys = []
    for entry in snapshots:
        vertices, faces = entry["vertices"], entry["faces"]
        keys = _triangle_keys(vertices[faces])
        expected_keys.append(keys)
        expected_parts.append({
            "id": entry["id"], "name": entry["name"], "plate": entry["plate"],
            "triangles": len(keys), "geometry_sha256": _identity(keys),
            "source_topology": _metrics(vertices, faces),
        })
    actual_parts = []
    actual_keys = []
    for path in paths:
        keys = _triangle_keys(_read_binary_stl(path))
        actual_keys.append(keys)
        actual_parts.append({
            "file": str(path), "triangles": len(keys), "geometry_sha256": _identity(keys),
        })
    whole_expected = np.sort(np.concatenate(expected_keys))
    whole_actual = np.sort(np.concatenate(actual_keys))
    geometry_matches = np.array_equal(whole_expected, whole_actual)
    remaining = list(range(len(actual_parts)))
    matches = []
    for before in expected_parts:
        chosen = next((index for index in remaining
                       if actual_parts[index]["triangles"] == before["triangles"]
                       and actual_parts[index]["geometry_sha256"] == before["geometry_sha256"]), None)
        matches.append({"expected_object": before["id"],
                        "file": actual_parts[chosen]["file"] if chosen is not None else None})
        if chosen is not None:
            remaining.remove(chosen)
    individual_files = (
        len(paths) == len(snapshots) and not remaining
        and all(row["file"] is not None for row in matches)
    )
    aggregate_file = len(paths) == 1 and geometry_matches
    grouping_matches = individual_files or aggregate_file
    expected_metrics = _stl_metrics(whole_expected)
    actual_metrics = _stl_metrics(whole_actual)
    scale = max(1.0, float(np.max(np.abs(expected_metrics["bounds"]))))
    coordinate_ulp = float(np.spacing(np.float32(scale)))
    # Volumensummen dürfen durch eine andere Summierfolge letzte Bits wechseln.
    # Die strengere Dreiecksmengenprüfung darüber bleibt unabhängig davon zwingend.
    volume_tolerance = coordinate_ulp * max(expected_metrics["area"], 1.0)
    metric_checks = {
        "triangles": expected_metrics["triangles"] == actual_metrics["triangles"],
        "bounds": bool(np.allclose(expected_metrics["bounds"], actual_metrics["bounds"],
                                   rtol=0, atol=coordinate_ulp)),
        "volume": bool(np.isclose(expected_metrics["volume"], actual_metrics["volume"],
                                  rtol=0, atol=volume_tolerance)),
        "watertight": expected_metrics["watertight"] == actual_metrics["watertight"],
        "winding": expected_metrics["winding_consistent"] == actual_metrics["winding_consistent"],
        "components": expected_metrics["components_by_shared_edges"] == actual_metrics["components_by_shared_edges"],
    }
    return {
        "passed": geometry_matches and grouping_matches and all(metric_checks.values()),
        "world_triangles_match": geometry_matches, "grouping_matches": grouping_matches,
        "grouping": "one_file_per_body" if individual_files else "combined_stl" if aggregate_file else "unmatched",
        "source_body_count": len(snapshots), "stl_file_count": len(paths),
        "matches": matches if individual_files else [],
        "expected_parts": expected_parts, "actual_files": actual_parts,
        "expected_float32_world": expected_metrics, "actual_stl_world": actual_metrics,
        "metric_checks": metric_checks,
        "coordinate_ulp_mm": coordinate_ulp, "volume_tolerance_mm3": volume_tolerance,
        "format_contract": {
            "object_ids_preserved": False,
            "world_coordinates": "Szenenkoordinaten ohne Ansichts-/Platten-/Explosionsversatz",
            "float32": "Erwartung wird genau einmal auf die STL-Koordinatengenauigkeit gerundet",
            "topology": "Für beide Seiten exakte gleiche Float32-Orte zusammenführen; Komponenten über gemeinsame Kanten",
            "body_count": "Objektzahl wird über Dateizuordnung oder vollständige gemeinsame Dreiecksmenge belegt; STL-Komponenten sind keine Objektkennungen",
            "source_topology": "Originale Objektkennzahlen sind separat ausgewiesen; identische Orte verschiedener Objekte können im STL zusammenfallen",
            "volume": "Gerichtetes Netzvolumen; als physisches Volumen nur bei geschlossenem, konsistent orientiertem Netz interpretieren",
        },
    }


def verify(probe, snapshots, paths):
    """Nach echtem STL-Dateiexport unabhängig prüfen und vollständig protokollieren."""
    try:
        with ThreadPoolExecutor(max_workers=1, thread_name_prefix="stl-export-check") as executor:
            future = executor.submit(inspect, snapshots, tuple(paths))
            probe.wait("STL unabhängig wieder eingelesen", future.done, 300)
            report = future.result()
        probe.log("STL-Geometrie unabhängig wieder eingelesen", **report)
        return report
    except Exception:
        probe.log("STL-Geometrie nicht geprüft", passed=False, traceback=traceback.format_exc())
        return None
