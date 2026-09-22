"""Bereitet den nächsten Flächenanschluss vor, ohne Produktdateien zu verändern."""

import difflib
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
STATE = Path(__file__).parent
patches = []
snapshots = {}


def changed(path: str, replacements: list[tuple[str, str]]) -> None:
    original = (ROOT / path).read_bytes()
    before = original.decode("utf-8").replace("\r\n", "\n")
    after = before
    for source, target in replacements:
        assert after.count(source) == 1, (path, source)
        after = after.replace(source, target)
    assert (ROOT / path).read_bytes() == original
    snapshots[path] = hashlib.sha256(original).hexdigest()
    patches.extend(difflib.unified_diff(
        before.splitlines(keepends=True), after.splitlines(keepends=True),
        fromfile=f"a/{path}", tofile=f"b/{path}"))


changed("app/core/geom/face_ops.py", [
    ('from app.core.geom.faces import draft_vertical, face_normal, push_face',
     'from app.core.geom.faces import draft_vertical, push_face'),
    ('from app.core.types import BaseParams, Feature, OpContext, OpResult, SceneObject, Vec3',
     'from app.core.types import BaseParams, Feature, OpContext, OpResult, SceneObject'),
    ('name="push_face",\n    cache_version="3",',
     'name="push_face",\n    cache_version="4",'),
    ('''    centre: Vec3 | None = None
    if chosen is not None:
        direction = face_normal(chosen)
        spot = chosen.params.get("centre")
        if spot is not None:
            measured = [float(value) for value in spot]
            centre = (measured[0], measured[1], measured[2])
    moved = profiles.push_faces(
        body, direction, params.distance, centre=centre, cancelled=ctx.cancelled
    )''',
     '''    selected_faces: tuple[int, ...] | None = None
    if chosen is not None:
        ctx.cancelled.raise_if_cancelled()
        selected_faces = body.complete_faces_of_triangles(chosen.face_indices)
        ctx.cancelled.raise_if_cancelled()
    moved = profiles.push_faces(
        body, direction, params.distance, selected_faces=selected_faces, cancelled=ctx.cancelled
    )'''),
])
changed("app/core/geom/prepare_ops.py", [
    ('name="remove_feature",\n    cache_version="3",',
     'name="remove_feature",\n    cache_version="4",'),
    ('''    solid = (
        edit.unround(body, spot, was, cancelled=ctx.cancelled)
        if radius is None
        else edit.reround(body, spot, was, radius, cancelled=ctx.cancelled)
    )''',
     '''    if radius is None:
        ctx.cancelled.raise_if_cancelled()
        selected_faces = body.complete_faces_of_triangles(feature.face_indices)
        ctx.cancelled.raise_if_cancelled()
        solid = edit.unround(
            body, spot, was, selected_faces=selected_faces, cancelled=ctx.cancelled
        )
    else:
        solid = edit.reround(body, spot, was, radius, cancelled=ctx.cancelled)'''),
])
(STATE / "p14c-face-consumers.patch").write_text("".join(patches), encoding="utf-8")
(STATE / "p14c-face-consumers-base.json").write_text(json.dumps(snapshots, indent=2), encoding="utf-8")
print(json.dumps({"draft": "p14c-face-consumers.patch", "paths": list(snapshots), "applied": False}))
