"""Shared test scaffolding.

The geometry kernel is not part of P0, so tests use a mesh that only answers the
questions the ``Mesh`` protocol asks. That is enough for the scene, the stack and
the evaluation — and it keeps these tests honest about what they check.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Sequence
from dataclasses import dataclass, field

import pytest

# Surface tests need a Qt platform that works without a screen.
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# The suite must not read or write the user's own data (§38). Without this a
# calibrated material on the developer's machine changes what the tests see —
# and worse, a test run leaves calibrations behind in their profile folder.
# Set before anything imports `app.core.paths`, because that reads these.
_ISOLATED = tempfile.mkdtemp(prefix="formwerk-tests-")
for _variable in ("APPDATA", "LOCALAPPDATA", "XDG_DATA_HOME", "XDG_CONFIG_HOME", "XDG_CACHE_HOME"):
    os.environ[_variable] = _ISOLATED

from app.core.knowledge import profiles
from app.core.types import BoundingBox, Document, Profile, SceneObject


@dataclass(frozen=True, slots=True)
class FakeMesh:
    """A mesh stand-in with fixed metrics."""

    triangles: int = 12
    vertices: int = 8
    size: tuple[float, float, float] = (10.0, 10.0, 10.0)
    watertight: bool = True
    components: int = 1
    slots: tuple[int, ...] = field(default_factory=tuple)

    @property
    def vertex_count(self) -> int:
        return self.vertices

    @property
    def triangle_count(self) -> int:
        return self.triangles

    @property
    def bounds(self) -> BoundingBox:
        return BoundingBox(minimum=(0.0, 0.0, 0.0), maximum=self.size)

    @property
    def volume(self) -> float:
        return self.size[0] * self.size[1] * self.size[2]

    @property
    def area(self) -> float:
        width, depth, height = self.size
        return 2 * (width * depth + width * height + depth * height)

    @property
    def is_watertight(self) -> bool:
        return self.watertight

    @property
    def component_count(self) -> int:
        return self.components

    @property
    def slot_indices(self) -> Sequence[int]:
        return self.slots


@pytest.fixture(scope="session")
def qt_app() -> object:
    """One QApplication for the whole run — widgets crash without it."""
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture
def mesh() -> FakeMesh:
    return FakeMesh()


@pytest.fixture
def profile() -> Profile:
    return profiles.make_profile("centauri-carbon-2", "petg")


@pytest.fixture
def document() -> Document:
    return Document(format_version=1, app_version="0.0.1")


def make_object(object_id: str = "obj_1", name: str = "Teil", **kwargs: object) -> SceneObject:
    return SceneObject(id=object_id, name=name, mesh=FakeMesh(**kwargs))  # type: ignore[arg-type]
