"""Performance budget (Bauplan §31).

Two kinds of check, because either alone is misleading. The absolute targets from
§31 say whether the application is fast enough at all. The comparison with the
previous run on this machine catches a regression that stays inside the target —
"a quarter slower" is a defect, not noise.

Measurements are machine dependent, so the baseline is local (``.performance.json``,
not checked in). The absolute targets are generous where a test machine may be
slower than a workstation; they still fail on an order-of-magnitude mistake.
"""

from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from app.core.geom.measure import wall_thickness
from app.core.geom.mesh import MeshData, read_mesh
from app.core.geom.section import SectionPlane, cut
from app.core.ingest.loader import normalise
from app.core.scene import History, OperationDraft, ResultCache, evaluate
from app.core.scene.project import ProjectSources, new_project
from app.core.types import Profile, Source
from app.i18n import _

pytestmark = pytest.mark.performance

MESHES = Path(__file__).parent / "data" / "meshes"
BASELINE = Path(__file__).parent / ".performance.json"

#: How much slower than the last run on this machine counts as a defect (§31).
REGRESSION_LIMIT = 1.25


def dense_mesh() -> MeshData:
    """The million triangle body. Built on first use; it is too big to check in."""
    path = MESHES / "dense_1m.stl"
    if not path.is_file():
        import trimesh

        sphere = trimesh.creation.icosphere(subdivisions=8, radius=40.0)
        path.write_bytes(trimesh.exchange.stl.export_stl(sphere))
    return read_mesh(path.read_bytes(), ".stl")


def measure(name: str, work: Callable[[], Any]) -> float:
    """Run once, record the seconds, compare with the previous run."""
    started = time.perf_counter()
    work()
    taken = time.perf_counter() - started

    history: dict[str, float] = {}
    if BASELINE.is_file():
        history = json.loads(BASELINE.read_text(encoding="utf-8"))
    previous = history.get(name)
    history[name] = taken
    BASELINE.write_text(json.dumps(history, indent=2, sort_keys=True), encoding="utf-8")

    print(
        f"\n{name}: {taken * 1000:.0f} ms"
        + (f" (vorher {previous * 1000:.0f} ms)" if previous else "")
    )
    if previous is not None and previous > 0.02:
        assert taken <= previous * REGRESSION_LIMIT, (
            f"{name} is {taken / previous:.2f} times slower than the last run on this machine"
        )
    return taken


def test_reading_a_million_triangles(profile: Profile) -> None:
    """Not in §31 by name, but the gate to everything else."""
    taken = measure("read_dense", dense_mesh)
    assert taken < 30.0


def test_the_input_stage_on_a_million_triangles() -> None:
    mesh = dense_mesh()
    taken = measure("ingest_dense", lambda: normalise(mesh, "mm"))
    assert taken < 60.0, "welding and cleaning a million triangles"


def test_the_section_cut_stays_interactive() -> None:
    """§18.2: the plane is dragged, so the cut has to keep up."""
    mesh = normalise(read_mesh((MESHES / "two_components.stl").read_bytes(), ".stl"), "mm").mesh
    taken = measure("section_small", lambda: cut(mesh, SectionPlane.along("z", 0.0)))
    assert taken < 1.0


def test_wall_thickness_answers_quickly() -> None:
    mesh = normalise(read_mesh((MESHES / "cube_clean.stl").read_bytes(), ".stl"), "mm").mesh
    taken = measure("thickness_small", lambda: wall_thickness(mesh, (0.0, 0.0, 10.0)))
    assert taken < 0.5


def test_reevaluating_from_the_cache_is_quick(profile: Profile) -> None:
    """§31: opening a project from the disk cache stays under a second."""
    project = new_project("centauri-carbon-2", "petg")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/cube_clean.stl", sha256=""
    )
    project.sources["src_1"] = (MESHES / "cube_clean.stl").read_bytes()
    History(project.document).apply(
        _("Laden"), [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
    )
    cache = ResultCache()
    sources = ProjectSources(project)
    evaluate(project.document, profile, sources=sources, cache=cache)

    taken = measure(
        "evaluate_cached",
        lambda: evaluate(project.document, profile, sources=sources, cache=cache),
    )
    assert taken < 1.0
    assert cache.statistics.hits >= 1
