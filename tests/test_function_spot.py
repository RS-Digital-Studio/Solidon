"""E4 an einer Handlung am ganzen Körper: ihr Rahmen im Ergebnisbild (FD-169, M-E4).

*Auf das Bett setzen* hat keine gewählte Stelle; ``spot`` blieb leer, und die
Oberseite nach dem Hub stand außerhalb des Kamerarands, ohne dass Stufe A es
maß (Abweichung 19). Jetzt misst der Prüfstand nach dem Übernehmen den Rahmen
der geänderten Körper und ob er ganz in der Ansicht liegt
(``function_spot.body_spot``); E4 meldet „Stelle nach dem Ergebnis außerhalb des
Bildes“. Ohne Fenster: eine nachgebaute Ansicht mit gerader Projektion.
"""

from __future__ import annotations

import copy
from types import SimpleNamespace
from typing import Any

import pytest

from tools import function_bench, function_spot
from tools.function_judges import OUTSIDE_AFTER_RESULT
from tools.function_points import judge_case
from tools.function_samples import sample_context, sample_protocol


class _Point:
    def __init__(self, x: float, y: float) -> None:
        self._x, self._y = round(x), round(y)

    def x(self) -> int:
        return self._x

    def y(self) -> int:
        return self._y


class _Renderer:
    """Gerade Projektion: x und z eines Weltpunkts in Millimetern, ein Bildpunkt je mm."""

    widget = None

    def __init__(self, width: int, height: int) -> None:
        self.size = (width, height)

    def view_size(self) -> tuple[int, int]:
        return self.size

    def world_to_display(self, world: tuple[float, ...]) -> tuple[float, float, float]:
        return (world[0] + 100.0, self.size[1] - world[2] - 100.0, 0.5)


def _window(offset: tuple[float, float, float], size: tuple[int, int] = (640, 480)) -> Any:
    import trimesh

    from app.core.geom.mesh import MeshData

    box = MeshData(trimesh.creation.box(extents=(40.0, 40.0, 40.0)))
    box = MeshData(box.raw.copy().apply_translation(offset))
    renderer = _Renderer(*size)
    viewport = SimpleNamespace(
        renderer=renderer,
        view_offset_of=lambda object_id: (0.0, 0.0, 0.0),
        mapToGlobal=lambda point: _Point(0, 0),
        rect=lambda: SimpleNamespace(topLeft=lambda: None),
        width=lambda: size[0],
        height=lambda: size[1],
    )
    scene = SimpleNamespace(objects={"obj_1": SimpleNamespace(mesh=box)})
    return SimpleNamespace(
        viewport=viewport, session=SimpleNamespace(last_result=SimpleNamespace(scene=scene))
    )


@pytest.fixture(autouse=True)
def _flat_view(monkeypatch: pytest.MonkeyPatch) -> None:
    """Weltpunkt → globaler Punkt über dieselbe gerade Projektion; keine offenen Fenster."""
    from app.ui import guide_targets
    from tools import function_surface

    def point_of_world(window: Any, world: tuple[float, ...]) -> _Point:
        x, y, _depth = window.viewport.renderer.world_to_display(world)
        return _Point(x, y)

    monkeypatch.setattr(guide_targets, "point_of_world", point_of_world)
    monkeypatch.setattr(function_surface, "windows_to_picture", lambda window: [])


def _data(before: str = "aaaa", after: str = "bbbb") -> dict[str, Any]:
    return {
        "spot": None,
        "unmeasured": {},
        "states": {
            "before": {"bodies": {"obj_1": before}},
            "applied": {"bodies": {"obj_1": after}},
        },
    }


def test_only_bodies_the_result_changed_or_added_count() -> None:
    before = {"bodies": {"obj_1": "a", "obj_2": "b"}}
    applied = {"bodies": {"obj_1": "a", "obj_2": "c", "obj_3": "d"}}
    assert function_spot.changed_bodies(before, applied) == ["obj_2", "obj_3"]
    assert function_spot.changed_bodies(None, None) == []


def test_a_body_inside_the_view_is_inside() -> None:
    data = _data()
    function_spot.body_spot(_window((0.0, 0.0, 20.0)), data)
    spot = data["spot"]
    assert spot["inside"] is True and spot["bodies"] == ["obj_1"]
    # Würfel 40 mm, unten auf z = 0: Bild x 80 bis 120, y 340 (Oberseite) bis 380.
    assert spot["frame"] == [80, 340, 40, 40]
    assert spot["covered_by"] is None


def test_a_body_lifted_over_the_edge_is_outside() -> None:
    """Wie die Oberseite nach dem Hub: Der Rahmen reicht über den oberen Rand."""
    data = _data()
    function_spot.body_spot(_window((0.0, 0.0, 380.0)), data)
    assert data["spot"]["inside"] is False


def test_without_a_picture_of_the_view_it_is_not_measured() -> None:
    window = _window((0.0, 0.0, 20.0))
    window.viewport.renderer = None
    data = _data()
    function_spot.body_spot(window, data)
    assert data["spot"] is None
    assert data["unmeasured"]["spot"] == function_spot.WITHOUT_VIEW


def test_a_chosen_spot_is_not_replaced_by_the_body() -> None:
    """Merkmal und Kante bleiben ihre Stelle — gemessen oder mit Grund nicht gemessen."""
    window = _window((0.0, 0.0, 380.0))
    measured = {**_data(), "spot": {"point": [1, 2], "covered_by": None}}
    function_spot.body_spot(window, measured)
    assert measured["spot"] == {"point": [1, 2], "covered_by": None}
    missing = {**_data(), "unmeasured": {"spot": "view:obj_1.hole_1: nicht im Bild"}}
    function_spot.body_spot(window, missing)
    assert missing["spot"] is None


def test_an_action_that_changes_no_body_has_no_spot() -> None:
    data = _data(after="aaaa")
    function_spot.body_spot(_window((0.0, 0.0, 380.0)), data)
    assert data["spot"] is None and data["unmeasured"] == {}


def test_e4_reports_the_body_outside_the_picture_after_the_result() -> None:
    protocol = copy.deepcopy(sample_protocol())
    protocol["row"]["requirement"] = ""
    protocol["spot"] = {
        "frame": [80, -40, 40, 40],
        "view": [0, 0, 640, 480],
        "inside": False,
        "bodies": ["obj_1"],
        "covered_by": None,
    }
    outcome = judge_case(protocol, sample_context()).criteria["E4"]
    assert outcome.verdict == "fund"
    assert any(issue.text == OUTSIDE_AFTER_RESULT for issue in outcome.issues)
    protocol["spot"]["inside"] = True
    assert judge_case(protocol, sample_context()).criteria["E4"].verdict == "erfuellt"


def test_the_result_picture_measures_the_body_spot(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die Messung hängt am Ergebnisbild: nach ``03-uebernommen`` im Übernehmen."""
    flow = object.__new__(function_bench.FunctionFlow)
    flow.data = {"unmeasured": {}, "states": {}}
    flow.window = object()
    flow.session = SimpleNamespace(last_result=None)
    flow.heartbeat = SimpleNamespace(close=lambda t: 0.0)
    flow.watch = SimpleNamespace(note_after=lambda phase: None, poll=lambda: None)
    order: list[str] = []
    flow.snapshot = lambda label: order.append(f"abdruck {label}") or {"bodies": {}}
    flow.picture = lambda label: order.append(f"bild {label}")
    flow.compare_with_cli = lambda: None
    monkeypatch.setattr(function_bench, "body_spot", lambda window, data: order.append("stelle"))
    flow.measured_apply({"budget_s": None}, {"settled": True, "effect": True, "done": 2.0}, 1.0)
    assert order == ["abdruck applied", "bild 03-uebernommen", "stelle"]
