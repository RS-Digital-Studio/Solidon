"""Große Merkmalsmengen durch echte Projekte, ohne Leistungsfreigabe (§21.2)."""

from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import trimesh

from app.core.bootstrap import load_operations
from app.core.geom.mesh import MeshCodec
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.cache import DiskCache, ResultCache
from app.core.scene.project import ProjectSources, load, new_project, save
from app.core.types import Profile, Source


def _grid_source(exact: bool) -> tuple[bytes, str, str]:
    """176 getrennte Würfel mit Kantenlänge 2 mm tragen zusammen 1056 echte ebene Flächen."""
    if exact:
        from OCP.BRep import BRep_Builder
        from OCP.BRepPrimAPI import BRepPrimAPI_MakeBox
        from OCP.gp import gp_Pnt
        from OCP.TopoDS import TopoDS_Compound

        from app.core.brep.kernel import Solid
        from app.core.brep.step import write

        compound = TopoDS_Compound()
        builder = BRep_Builder()
        builder.MakeCompound(compound)
        for x in range(11):
            for y in range(16):
                builder.Add(
                    compound,
                    BRepPrimAPI_MakeBox(gp_Pnt(6.0 * x, 6.0 * y, 0.0), 2.0, 2.0, 2.0).Shape(),
                )
        return write(Solid(compound)), "step", "load_step"
    pieces = []
    for x in range(11):
        for y in range(16):
            box = trimesh.creation.box(extents=(2.0, 2.0, 2.0))
            box.apply_translation((6.0 * x + 1.0, 6.0 * y + 1.0, 1.0))
            pieces.append(box)
    return trimesh.util.concatenate(pieces).export(file_type="stl"), "stl", "load"


@pytest.mark.parametrize("exact", [False, True], ids=["facets", "native"])
def test_over_a_thousand_real_faces_keep_their_identity_through_project_lifecycle(
    exact: bool, profile: Profile, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Testfreigabe umgeht nur die noch beim Release zu messende Zahlengrenze.

    Import, Erkennung, Zuordnung, Transformation, Cache und Historie laufen
    unverändert. Der Fall belegt Identität und Quellen, keine Laufzeit oder
    tragfähige neue Produktionsgrenze. Native Transformationen dürfen ihre
    bereits belegte Topologie unmittelbar mitnehmen.
    """
    evaluation = importlib.import_module("app.core.scene.evaluate")
    monkeypatch.setattr(evaluation, "FEATURE_LIMIT_COUNT", 1056)
    load_operations()
    payload, suffix, operation = _grid_source(exact)
    project = new_project("centauri-carbon-2", "petg")
    project.sources["src_1"] = payload
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path=f"sources/grid.{suffix}", sha256=""
    )
    history = History(project.document)
    params = {"source": "src_1"}
    if not exact:
        params["unit"] = "mm"
    history.apply("Flächenraster laden", [OperationDraft(op=operation, params=params)])
    directory = tmp_path / "cache"

    def cache() -> ResultCache:
        """Ein neuer Speichercache liest denselben echten Plattencache."""
        return ResultCache(disk=DiskCache(codec=MeshCodec(), directory=directory))

    active = cache()
    matched_counts: list[tuple[int, int]] = []
    original_match = evaluation.match

    def recorded_match(old: Any, new: Any, *args: Any, **kwargs: Any) -> Any:
        """Der Zähler belegt den echten Anschluss, das Ergebnis bleibt unverändert."""
        matched_counts.append((len(old), len(new)))
        return original_match(old, new, *args, **kwargs)

    monkeypatch.setattr(evaluation, "match", recorded_match)

    def run(current: Any, remembered: ResultCache, offset: np.ndarray) -> Any:
        """Jede einzelne Fläche bleibt am gleichen Würfel und auf derselben Seite."""
        result = evaluate(
            current.document, profile, sources=ProjectSources(current), cache=remembered
        )
        assert result.complete
        assert len(result.scene.objects) == 1
        assert not {"perceive.orphaned", "perceive.too_many"} & {
            finding.code for finding in result.scene.report.findings
        }
        body = result.scene.objects["obj_1"]
        assert body.kind == ("brep" if exact else "mesh")
        assert body.mesh.volume == pytest.approx(176.0 * 2.0**3)
        assert len(body.features) == 1056
        if original:
            assert body.features.keys() == original.keys()
        for name, feature in body.features.items():
            assert feature.kind == "face"
            assert feature.params["area"] == pytest.approx(2.0**2)
            assert feature.measure_sources["area"] == ("native" if exact else "facets")
            assert feature.surface_patches
            assert feature.created_by is None
            if original:
                assert feature.params["centre"] == pytest.approx(
                    np.asarray(original[name].params["centre"]) + offset
                )
                assert feature.params["normal"] == pytest.approx(original[name].params["normal"])
            for patch in feature.surface_patches:
                assert patch.kind == "plane"
                assert patch.source == ("native" if exact else "facets")
                assert set(patch.face_indices) <= set(feature.face_indices)
                assert float(
                    (np.asarray(feature.params["centre"]) - patch.params["centre"])
                    @ np.asarray(patch.params["axis"])
                ) == pytest.approx(0.0, abs=1e-8)
        return body.features

    original: dict[str, Any] = {}
    zero = np.zeros(3)
    original = run(project, active, zero)
    assert run(project, active, zero) == original
    history.apply(
        "Raster verschieben",
        [OperationDraft(op="translate_object", inputs=("obj_1",), params={"dx": 7.0, "dy": -4.0})],
    )
    offset = np.array((7.0, -4.0, 0.0))
    changed = run(project, active, offset)
    restored = load(save(project, tmp_path / "grid.solidon"))
    fresh_cache = cache()
    run(restored, fresh_cache, offset)
    if not exact:
        assert fresh_cache.statistics.disk_hits > 0
        assert any(min(counts) > 1000 for counts in matched_counts)
    history.undo()
    assert run(project, active, zero) == original
    history.redo()
    assert run(project, active, offset) == changed
    assert project.sources["src_1"] == payload
