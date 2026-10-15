"""Netze, die eine Szene beim Bau erzeugt (FD-101): gleich bei jedem Bau, in der Spanne der Zusage.

*Alle Merkmale erkennen* steht nur an einem geladenen Körper über der automatischen
Erkennungsgrenze, dessen Wahl beim Laden abgelehnt wurde (§21.1). Die Szene
``ueber_erkennungsgrenze`` verfeinerte einen Quader erst nach dem Laden über die
Grenze; ihre Zusage *Alle Merkmale erkennen* stimmte nie. Das Netz der neuen
Szene entsteht beim Bau, zu groß für ``tests/data``.
"""

from __future__ import annotations

import io

from app.core.perceive.local import CONFIRMED_FEATURE_LIMIT_TRIANGLES, FEATURE_LIMIT_TRIANGLES
from tools import function_scenes


def test_the_dense_plate_is_closed_the_same_every_time_and_between_both_limits() -> None:
    import trimesh

    payload, suffix = function_scenes.dense_plate()
    assert suffix == ".ply"
    assert function_scenes.dense_plate()[0] == payload, "der Generator rät"
    body = trimesh.load(io.BytesIO(payload), file_type="ply", process=False)
    assert FEATURE_LIMIT_TRIANGLES < len(body.faces) <= CONFIRMED_FEATURE_LIMIT_TRIANGLES
    assert body.is_watertight and body.is_winding_consistent
    assert body.volume > 0.0
    assert abs(body.volume - 200.0 * 200.0 * 10.0) < 1.0


def test_the_recognition_scene_keeps_its_declined_choice_at_the_load_step() -> None:
    """Die Wahl steht am Ladeschritt, mit dem Netzabdruck des Ladens: Nur dann gibt es
    etwas nachzuholen (``history.recognition_reopenable``)."""
    from app.core.perceive.match_records import recognition_answer_key
    from app.core.scene.history import recognition_reopenable

    project = function_scenes.build_scene("ueber_erkennungsgrenze")
    load = next(entry for entry in project.document.ops if entry.op == "load")
    record = load.matches[recognition_answer_key("obj_1")]
    assert record["allowed"] is False and len(record["scope"]) == 32
    assert recognition_reopenable(project.document, "obj_1", declined_only=True)
