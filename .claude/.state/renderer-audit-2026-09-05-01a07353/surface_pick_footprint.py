"""Sichert eine lebende Auswahlpose und prüft Originalstrahlen in ihrem Pixelumfeld.

``capture_and_diagnose(probe, pixels, observations=...)`` kann unmittelbar nach
den echten Klicks laufen. Es importiert kein Modell, verändert keine Auswahl
und interpretiert einen Renderer-Pick niemals als Erwartung. ``--replay`` liest
nur die gesicherten Netze und Strahlen, ohne Qt oder einen Renderer zu laden.
``--prepare-native`` erzeugt einen getrennten kurzen Runner aus der vorhandenen
Sonde; aktive Sonde, Vorlagen und Pins bleiben unberührt.
"""

from __future__ import annotations

import argparse
import ast
import dataclasses
import hashlib
import json
import math
from pathlib import Path


HERE = Path(__file__).resolve().parent
HISTORICAL_PIXELS = {("gfx", 18): (831, 390), ("vtk", 18): (676, 499),
                     ("gfx", 19): (878, 448), ("vtk", 19): (472, 583)}


def _sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _write(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _array_hash(values):
    digest = hashlib.sha256()
    digest.update(str((values.shape, values.dtype.str)).encode())
    digest.update(values.tobytes())
    return digest.hexdigest()


def _camera(renderer, engine):
    """Die Pose und beide Projektionsparameter ohne Einpassen oder Rendern lesen."""
    result = {"pose": dataclasses.asdict(renderer.camera_pose()),
              "parallel": renderer.parallel_projection(),
              "parallel_scale": renderer.parallel_scale(),
              "device_size": list(renderer.view_size()),
              "logical_size": [renderer.widget.width(), renderer.widget.height()],
              "dpr": float(renderer.widget.devicePixelRatioF())}
    if engine == "gfx":
        camera = renderer._camera
        result["world_to_clip"] = camera.camera_matrix.tolist()
        result["view_angle"] = float(camera.fov)
        result["depth_convention"] = "pygfx NDC z von 0 bis 1, Qt y nach unten"
        texture = renderer._renderer._blender.get_texture("pick")
        if texture is None:
            raise RuntimeError("Kein GFX-Pickbild vorhanden; ohne Bild ist die Rasterzelle nicht belegbar")
        result["pick_texture_size"] = list(texture.size[:2])
        result["raster_scale"] = [texture.size[index] / result["device_size"][index] for index in (0, 1)]
    elif engine == "vtk":
        camera = renderer.renderer.GetActiveCamera()
        matrix = camera.GetCompositeProjectionTransformMatrix(
            renderer.renderer.GetTiledAspectRatio(), 0.0, 1.0)
        result["world_to_clip"] = [[matrix.GetElement(i, j) for j in range(4)] for i in range(4)]
        result["clipping_range"] = list(camera.GetClippingRange())
        result["view_angle"] = float(camera.GetViewAngle())
        result["window_multisamples"] = int(renderer.window.GetMultiSamples())
        result["depth_convention"] = "VTK Display z von 0 bis 1; Qt y = Höhe - 1 - VTK y"
    else:
        raise ValueError(f"Unbekannter Renderer: {engine}")
    return result


def _geometry(probe, destination):
    """Bereits vorhandene Originalnetze sichern, ohne B-Rep-Bounds oder neue Erkennung."""
    import numpy as np

    view = probe.window.viewport
    scene = probe.session.last_result
    if view._scene_worker is not None or view._actor_scene is not scene or view._result is not scene:
        raise RuntimeError("Dokument und dargestellte Szene sind nicht identisch; diese Probe braucht den fertigen Aufbau")
    if view._section is not None:
        raise RuntimeError("Die Pixelprobe unterstützt keine aktive Schnittebene; Befund bleibt ungeprüft")
    bodies, digest = [], hashlib.sha256()
    for number, (oid, obj) in enumerate(sorted(scene.scene.objects.items())):
        raw = obj.mesh.raw
        vertices = np.asarray(raw.vertices).copy()
        faces = np.asarray(raw.faces).copy()
        actor = view._actors.get(oid)
        offset = np.asarray(view._shown_offset(obj, scene), dtype=float)
        matrix = actor.matrix() if actor is not None else np.eye(4)
        position = actor.position() if actor is not None else (0.0, 0.0, 0.0)
        values = {"vertices": vertices, "faces": faces}
        features, metadata_features = {}, {}
        for index, (fid, feature) in enumerate(sorted(obj.features.items())):
            key = f"feature_{index}"
            cells = np.asarray(feature.face_indices, dtype=np.int64)
            values[key] = cells
            params = probe.plain(dict(feature.params))
            metadata_features[str(fid)] = {"kind": feature.kind, "params": params,
                "face_count": len(cells), "face_hash": hashlib.sha256(cells.tobytes()).hexdigest()}
            features[str(fid)] = {**metadata_features[str(fid)], "indices_key": key}
        metadata = {"id": str(oid), "name": str(obj.name), "kind": obj.kind,
                    "plate": obj.plate, "features": metadata_features}
        body_hash = hashlib.sha256()
        for array in (vertices, faces):
            body_hash.update(str((array.shape, array.dtype.str)).encode())
            body_hash.update(array.tobytes())
        body_hash.update(json.dumps(metadata, ensure_ascii=False, sort_keys=True).encode())
        digest.update(body_hash.hexdigest().encode())
        path = destination / f"original-{number:02d}.npz"
        np.savez(path, **values)
        bodies.append({**metadata, "features": features,
            "array_file": path.name, "file_sha256": _sha(path),
            "geometry_arrays": {key: _array_hash(values[key]) for key in ("vertices", "faces")},
            "body_fingerprint": body_hash.hexdigest(), "visible": actor is not None and actor.visible(),
            "actor_name": actor.name if actor is not None else None,
            "view_offset": offset.tolist(), "actor_matrix": np.asarray(matrix).tolist(),
            "actor_position": list(position), "triangles": len(faces)})
    return {"fingerprint": digest.hexdigest(), "objects": bodies,
            "fingerprint_contract": "feature_checks.fingerprint, ohne Volumen-/B-Rep-Abfragen",
            "current_plate": view._plate, "hidden": sorted(map(str, view.hidden))}


def _pick(renderer, actors, x, y, tolerance):
    """Zusätzliches natives Messergebnis; es bestimmt nie den CPU-Solltreffer."""
    hit = renderer.pick_surface(x, y, among=list(actors.values()), tolerance=tolerance)
    if hit is None:
        return None
    owner = next((str(oid) for oid, item in actors.items() if item is hit.item), None)
    return {"object": owner, "cell": int(hit.cell), "point": list(hit.point),
            "actor": hit.item.name, "tolerance": tolerance}


def _rays_and_picks(renderer, actors, pixel, engine, camera):
    """Exakte Strahlen sichern; die dritte Spalte ist keine geschätzte Kamerapose."""
    x, y = map(float, pixel)
    requested = [(x + dx, y + dy) for dy in (-0.5, 0.0, 0.5) for dx in (-0.5, 0.0, 0.5)]
    # pygfx liest floor(x), floor(y); dessen Fragmentzentrum liegt bei +0,5.
    # Das zusätzliche Raster deckt den tatsächlichen GFX-Pixel ab. Die äußeren
    # Rasterlinien sind geometrische Grenzen, keine behaupteten Rasterfragmente.
    scale_x, scale_y = camera.get("raster_scale", (1.0, 1.0))
    raster = ([((math.floor(x * scale_x) + dx) / scale_x,
                (math.floor(y * scale_y) + dy) / scale_y)
               for dy in (0.0, 0.5, 1.0) for dx in (0.0, 0.5, 1.0)]
              if engine == "gfx" else requested)
    rows = []
    for px, py in dict.fromkeys(requested + raster):
        near = renderer.display_to_world(px, py, 0.0)
        far = renderer.display_to_world(px, py, 1.0)
        row = {"pixel": [px, py], "near": list(near) if near is not None else None,
               "far": list(far) if far is not None else None,
               "pointer_footprint": (px, py) in requested,
               "raster_footprint": (px, py) in raster}
        if engine == "vtk":
            row["native"] = {str(tolerance): _pick(renderer, actors, px, py, tolerance)
                             for tolerance in (0.0, 0.005)}
        elif (px, py) == (x, y):
            row["native"] = {"default": _pick(renderer, actors, px, py, 0.005)}
        rows.append(row)
    return rows


def _loaded_bodies(directory, geometry):
    import numpy as np

    bodies = []
    for body in geometry["objects"]:
        path = directory / body["array_file"]
        if _sha(path) != body["file_sha256"]:
            raise ValueError(f"Gesichertes Originalnetz wurde geändert: {path.name}")
        with np.load(path, allow_pickle=False) as archive:
            vertices, faces = archive["vertices"], archive["faces"]
            for key, array in (("vertices", vertices), ("faces", faces)):
                if _array_hash(array) != body["geometry_arrays"][key]:
                    raise ValueError(f"Originalarray stimmt nicht: {body['id']}/{key}")
            owners = [[] for _ in range(len(faces))]
            for fid, feature in body["features"].items():
                cells = archive[feature["indices_key"]]
                if hashlib.sha256(cells.tobytes()).hexdigest() != feature["face_hash"]:
                    raise ValueError(f"Merkmalsdreiecke stimmen nicht: {fid}")
                for cell in cells:
                    owners[int(cell)].append(fid)
        matrix = np.asarray(body["actor_matrix"])
        shown = (vertices + body["view_offset"]) @ matrix[:3, :3].T
        shown += matrix[:3, 3] + body["actor_position"]
        bodies.append((body, shown, faces, owners))
    return bodies


def _nearest(bodies, row):
    """Vorderstes Originaldreieck per Möller–Trumbore, ohne UI-Auswahlcode."""
    import numpy as np

    if row["near"] is None or row["far"] is None:
        return {"reason": "Kein gespeicherter Kamerastrahl"}
    start = np.asarray(row["near"], dtype=float)
    direction = np.asarray(row["far"], dtype=float) - start
    length = np.linalg.norm(direction)
    if not np.isfinite(length) or length <= 0:
        return {"reason": "Ungültiger gespeicherter Kamerastrahl"}
    direction /= length
    nearest, found = float("inf"), None
    for body, vertices, faces, owners in bodies:
        if not body["visible"]:
            continue
        for offset in range(0, len(faces), 32768):
            triangles = vertices[faces[offset:offset + 32768]]
            edge1, edge2 = triangles[:, 1] - triangles[:, 0], triangles[:, 2] - triangles[:, 0]
            cross = np.cross(np.broadcast_to(direction, edge2.shape), edge2)
            det = np.einsum("ij,ij->i", edge1, cross)
            valid = np.abs(det) > 1e-12
            inverse = np.divide(1.0, det, out=np.zeros_like(det), where=valid)
            delta = start - triangles[:, 0]
            u = np.einsum("ij,ij->i", delta, cross) * inverse
            q = np.cross(delta, edge1)
            v = q @ direction * inverse
            distance = np.einsum("ij,ij->i", edge2, q) * inverse
            valid &= (u >= 0) & (v >= 0) & (u + v <= 1) & (distance >= 0) & (distance < nearest)
            indices = np.flatnonzero(valid)
            if not len(indices):
                continue
            at = indices[np.argmin(distance[indices])]
            nearest = float(distance[at])
            cell = offset + int(at)
            found = {"object": body["id"], "cell": cell,
                     "point": (start + direction * nearest).tolist(), "features": owners[cell],
                     "barycentric_margin": float(min(u[at], v[at], 1 - u[at] - v[at]))}
    return found or {"reason": "Kein Originaldreieck auf dem Strahl"}


def diagnose(capture_path):
    """Nur Originalnetze und bereits gesicherte Strahlen lesen; kein Rendererimport."""
    path = Path(capture_path)
    capture = json.loads(path.read_text(encoding="utf-8"))
    bodies = _loaded_bodies(path.parent, capture["geometry"])
    points = []
    observed = {tuple(row["pixel"]): row.get("expected_cpu", {})
                for row in capture["observations"]}
    for point in capture["points"]:
        rows = [{**row, "original_cpu": _nearest(bodies, row)} for row in point["rays"]]
        groups = {}
        for name in ("pointer_footprint", "raster_footprint"):
            signatures = sorted({(row["original_cpu"].get("object"),
                tuple(row["original_cpu"].get("features", [])))
                for row in rows if row[name]}, key=str)
            groups[name] = {"homogeneous_samples": len(signatures) == 1,
                            "object_feature_signatures": signatures,
                            "limit": "Neun diskrete Strahlen beweisen keine Homogenität jeder Stelle im Pixel"}
        recorded = observed.get(tuple(point["pixel"]))
        centre = next(row["original_cpu"] for row in rows if row["pixel"] == point["pixel"])
        comparison = None
        if recorded and "cell" in recorded:
            comparison = {"same_object": recorded["object"] == centre.get("object"),
                          "same_cell": recorded["cell"] == centre.get("cell"),
                          "point_distance_mm": math.dist(recorded["point"], centre["point"])
                          if "point" in centre else None}
        points.append({**point, "rays": rows, "sample_classification": groups,
                       "recorded_cpu_centre_comparison": comparison})
    return {"capture": str(path), "capture_sha256": _sha(path),
            "geometry_fingerprint": capture["geometry"]["fingerprint"],
            "camera_stable": capture["camera_stable"], "points": points,
            "passed": None, "scope": "Diagnose, keine Umwertung historischer oder aktueller roter Klicktests"}


def capture_and_diagnose(probe, pixels, *, observations=(), name="surface-footprint"):
    """Im lebenden Fenster sichern; Auswahl und Dokument bleiben unverändert.

    Der Aufrufer liefert physische Canvaspixel, wie ``independent_surface``.
    ``observations`` enthält die bereits durch echte QTest-Klicks gewonnenen
    Zeilen. Diese Funktion erzeugt selbst keine Geste und behauptet keine.
    """
    pixels = list(dict.fromkeys(tuple(map(float, pixel)) for pixel in pixels))
    if not pixels:
        return None
    destination = probe.OUT / name
    destination.mkdir(exist_ok=False)
    renderer = probe.window.viewport.renderer
    engine = probe.args.renderer
    scene_before = probe.session.last_result
    before = _camera(renderer, engine)
    geometry = _geometry(probe, destination)
    capture = {"schema": 1, "engine": engine, "run_id": probe.results.get("run_id"),
        "source_directory": str(probe.SOURCE), "source_files_sha256": probe.results.get("source_files_sha256"),
        "helper_sha256": _sha(__file__), "versions": probe.results.get("versions"),
        "geometry": geometry, "camera_before": before, "observations": list(observations),
        "pixel_convention": {"coordinates": "Physische Canvaspixel, Qt y nach unten",
            "pointer": "CPU-Oracle und QTest-Pick verwenden den ganzzahligen Mauspunkt",
            "gfx": "GPU-Zelle floor(x*raster_scale_x), floor(y*raster_scale_y); Fragmentzentrum je Texturzelle bei +0,5",
            "vtk": "Geometrischer Zellpicker am genauen Mauspunkt; Toleranz 0/.005 ist relativ zur Fensterdiagonale",
            "boundary": "±0,5-Raster um den Mauspunkt; zusätzlich tatsächliche GFX-Texturzelle in Canvaspixel zurückgerechnet"},
        "points": []}
    path = destination / "capture.json"
    for pixel in pixels:
        capture["points"].append({"pixel": list(pixel),
            "rays": _rays_and_picks(renderer, probe.window.viewport._actors, pixel, engine, before)})
        _write(path, capture)
    capture["camera_after"] = _camera(renderer, engine)
    capture["camera_stable"] = capture["camera_after"] == before
    capture["scene_identity_unchanged"] = probe.session.last_result is scene_before
    capture["original_arrays_unchanged"] = all(
        _array_hash(getattr(scene_before.scene.objects[body["id"]].mesh.raw, key)) == digest
        for body in geometry["objects"] for key, digest in body["geometry_arrays"].items())
    _write(path, capture)
    diagnosis = diagnose(path)
    _write(destination / "diagnosis.json", diagnosis)
    probe.log("Oberflächenpixel unabhängig gesichert", capture=str(path),
              camera_stable=capture["camera_stable"], fingerprint=geometry["fingerprint"],
              points=len(pixels), diagnostic_only=True)
    return diagnosis


def run_recorded_targets(probe):
    """Nachprobe mit ihren eigenen Klickdaten und historischen Vergleichskoordinaten."""
    check = next(row for row in reversed(probe.results["checks"]) if row["label"] == "Oberflächenklicks")
    red = [row for row in check["hits"] if any(row.get(key) is False for key in
           ("surface_matches", "object_matches", "feature_matches"))]
    historical = HISTORICAL_PIXELS.get((probe.args.renderer, probe.args.index))
    pixels = [row["pixel"] for row in red]
    if historical is not None:
        pixels.append(historical)
    return capture_and_diagnose(probe, pixels, observations=check["hits"])


def prepare_native(destination):
    """Eigenständigen kurzen Runner erzeugen; vorhandene Sonde niemals überschreiben."""
    destination = Path(destination).resolve()
    if destination.parent != HERE or destination.exists():
        raise ValueError("Ein neuer Runnername direkt im privaten Auditordner ist erforderlich")
    original = HERE / "probe.py"
    source = original.read_text(encoding="utf-8")
    main = next(node for node in ast.parse(source).body if isinstance(node, ast.FunctionDef) and node.name == "main")
    segment = ast.get_source_segment(source, main)
    marker = '    if not args.gesture_only:\n'
    if segment.count(marker) != 1:
        raise ValueError("Die vorhandene Main-Funktion hat einen anderen Aufbau")
    prefix = segment.split(marker)[0]
    fresh = prefix + '''    import surface_pick_footprint
    results["diagnostic_runner"] = {"path": __file__, "sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "helper_sha256": hashlib.sha256(Path(surface_pick_footprint.__file__).read_bytes()).hexdigest(),
        "scope": "Import, echte Merkmals-/Oberflächenklicks und unmittelbare Pixelprobe; keine Leistungs-/Bearbeitungsmatrix"}
    feature_selection()
    surface_pick_footprint.run_recorded_targets(sys.modules[__name__])
    log("Originaldatei unverändert", same=hashlib.sha256(Path(entry["path"]).read_bytes()).hexdigest()==entry["sha256"])
    results["complete"] = True
    results["errors"] = errors
    write()
'''
    rewritten = source.replace(segment, fresh, 1)
    ast.parse(rewritten)
    with destination.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(rewritten)
    _write(destination.with_suffix(".manifest.json"), {"runner_sha256": _sha(destination),
        "source_probe_sha256": _sha(original), "footprint_helper_sha256": _sha(__file__),
        "scope": "Nur main verkürzt, Import- und echte Auswahlwege der vorhandenen Sonde erhalten"})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--replay", type=Path)
    group.add_argument("--prepare-native", type=Path)
    args = parser.parse_args()
    if args.prepare_native is not None:
        prepare_native(args.prepare_native)
    else:
        _write(args.replay.with_name("diagnosis-replayed.json"), diagnose(args.replay))
