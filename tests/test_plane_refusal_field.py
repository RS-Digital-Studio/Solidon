"""Eine Ebenenabsage einer Skizzenoperation nennt ein Feld, das ihr Dialog hat (FD-182).

Der Kern nannte ``plane``; keine Skizzenoperation führt ein Feld dieses
Namens, die Ebene steht in ``sketch``. *Eine andere Ebene wählen* lief damit
im Dialog als Knopf ins Leere und öffnete aus dem Fenster den Schritt ohne
Cursor. Der Dialogteil steht in ``test_refusal_field_ways_window.py``.
"""

from __future__ import annotations

import pytest

from app.core.bootstrap import load_operations
from app.core.errors import PICK_PLANE
from app.core.registry import REGISTRY
from app.core.sketch.planes import feature_plane, offset_plane
from tests.plane_refusals import sketch_plane_refusal


@pytest.mark.parametrize(
    "plane",
    [
        "through:0,0,20;10,0,20;20,0,20",
        "offset:plane:xy:@missing",
        feature_plane("obj_9", "face_1"),
        offset_plane(feature_plane("obj_9", "face_1"), 5.0),
    ],
)
def test_a_sketch_operation_names_its_sketch_field(plane: str) -> None:
    assert sketch_plane_refusal(plane).values.get("field") == "sketch"
    names = {entry.name for entry in REGISTRY.get("sketch_extrude").params.spec()}
    assert "sketch" in names


def test_the_plane_way_is_still_offered_where_the_plane_is_unreadable() -> None:
    refusal = sketch_plane_refusal("through:0,0,20;10,0,20;20,0,20")
    assert PICK_PLANE in refusal.suggestions


def test_every_sketch_operation_carries_the_field_its_refusals_name() -> None:
    """``sketch.ops._frame_of`` nennt fest ``sketch``; jede Operation des Moduls führt es."""
    load_operations()
    missing = [
        spec.name
        for spec in REGISTRY.all()
        if spec.fn.__module__ == "app.core.sketch.ops"
        and "sketch" not in {entry.name for entry in spec.params.spec()}
    ]
    sketch_operations = [
        spec.name for spec in REGISTRY.all() if spec.fn.__module__ == "app.core.sketch.ops"
    ]
    assert sketch_operations, "Voraussetzung: es gibt Skizzenoperationen"
    assert not missing, missing
