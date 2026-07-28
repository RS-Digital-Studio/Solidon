"""Auto split and the explosion view from the window (§25, §18.8)."""

from __future__ import annotations

from pathlib import Path

import pytest
import trimesh
from PySide6.QtWidgets import QApplication

from app.core.geom.mesh import MeshData
from app.core.scene import History, OperationDraft
from app.core.scene.project import new_project
from app.core.types import Source
from app.ui.explode_bar import ExplodeBar
from app.ui.session import Session

MESHES = Path(__file__).parent / "data" / "meshes"


def loaded(session: Session, name: str) -> None:
    payload = (MESHES / name).read_bytes()
    session.project = new_project("centauri-carbon-2", "petg")
    session.project.sources["src_1"] = payload
    session.project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path=f"sources/{name}", sha256=""
    )
    session.history = History(session.project.document)
    session.history.apply(
        "Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
    )
    session.evaluate_async()
    session.wait_for_idle()


def test_the_bar_only_shows_up_when_there_is_something_to_pull_apart(
    qt_app: QApplication,
) -> None:
    bar = ExplodeBar()

    bar.show_for(1)
    assert not bar.isVisible()

    bar.show_for(3)
    assert bar.isVisible()


def test_folding_back_together_resets_the_slider(qt_app: QApplication) -> None:
    """A slider that keeps a value nobody can see any more is a trap."""
    bar = ExplodeBar()
    bar.show_for(2)
    bar.slider.setValue(8)

    bar.show_for(1)

    assert bar.factor == 0.0


def test_the_slider_reports_a_factor(qt_app: QApplication) -> None:
    bar = ExplodeBar()
    seen: list[float] = []
    bar.factorChanged.connect(seen.append)

    bar.slider.setValue(10)

    assert seen == [1.0]
    assert bar.factor == 1.0


def test_the_session_splits_an_oversized_part(qt_app: QApplication) -> None:
    session = Session()
    loaded(session, "oversized.stl")

    applied = session.auto_split("obj_1")
    session.wait_for_idle()

    assert len(applied.object_ids) == 2
    assert len(applied.fits) == 2
    assert session.last_result is not None
    assert set(session.last_result.scene.objects) == set(applied.object_ids)


def test_a_part_that_fits_is_left_alone(qt_app: QApplication) -> None:
    session = Session()
    loaded(session, "cube_clean.stl")

    applied = session.auto_split("obj_1")

    assert applied.transaction is None
    assert applied.object_ids == ["obj_1"]


def test_the_explosion_never_reaches_the_geometry(qt_app: QApplication) -> None:
    """§18.8: it is a way of looking at the parts, not a way of moving them."""
    from app.ui.viewport import Viewport

    session = Session()
    loaded(session, "oversized.stl")
    session.auto_split("obj_1")
    session.wait_for_idle()
    result = session.last_result
    assert result is not None
    before = {
        object_id: tuple(entry.mesh.bounds.centre)
        for object_id, entry in result.scene.objects.items()
    }

    viewport = Viewport()
    viewport.show_scene(result)
    viewport.set_explosion(1.5)

    after = {
        object_id: tuple(entry.mesh.bounds.centre)
        for object_id, entry in result.scene.objects.items()
    }
    assert after == before


def test_the_offset_points_away_from_the_middle(qt_app: QApplication) -> None:
    from app.core.scene import EvaluationResult
    from app.core.types import Scene, SceneObject
    from app.ui.viewport import Viewport

    left = MeshData.of(trimesh.creation.box(extents=(10.0, 10.0, 10.0)))
    right_body = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    right_body.apply_translation((40.0, 0.0, 0.0))
    result = EvaluationResult(
        scene=Scene(
            objects={
                "obj_1": SceneObject(id="obj_1", name="A", mesh=left),
                "obj_2": SceneObject(id="obj_2", name="B", mesh=MeshData.of(right_body)),
            }
        )
    )

    viewport = Viewport()
    viewport._explosion = 1.0
    offset = viewport._exploded(result.scene.objects["obj_2"], result)

    assert offset[0] == pytest.approx(20.0), "half the distance between the two centres"
    assert offset[1] == pytest.approx(0.0)
