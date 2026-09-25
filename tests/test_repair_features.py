"""Reparierte Netze führen nur Merkmale ihrer tatsächlich verbliebenen Geometrie (§21)."""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest
import trimesh

from app.core.geom.mesh import MeshCodec
from app.core.perceive.features import forget_cache
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.cache import DiskCache, ResultCache
from app.core.scene.project import ProjectSources, load, new_project, save
from app.core.types import Profile, Quality, Source

DATA = Path(__file__).parent / "data"


@pytest.mark.parametrize("quality", ["draft", "fine"])
def test_repair_removes_a_previously_edited_pin_from_features_and_cached_replay(
    profile: Profile, tmp_path: Path, quality: Quality
) -> None:
    """Ein geänderter Zapfen verschwindet auch als Merkmal, wenn sein Teilchen entfernt wird."""
    dimensions = json.loads((DATA / "repair_features.json").read_text(encoding="utf-8"))
    stock = trimesh.creation.box(extents=dimensions["stock_size"])
    pin = trimesh.creation.cylinder(
        radius=dimensions["pin_diameter"] / 2.0,
        height=dimensions["pin_depth"],
        sections=dimensions["pin_sections"],
    )
    pin.apply_translation(dimensions["pin_centre"])
    source = trimesh.util.concatenate([stock, pin])
    assert source.is_watertight and source.is_winding_consistent
    assert len(source.split(only_watertight=False)) == 2

    project = new_project("centauri-carbon-2", "petg")
    project.sources["src_1"] = source.export(file_type="stl")
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/repair_features.stl", sha256=""
    )
    history = History(project.document)
    history.apply(
        "Prüfkörper laden",
        [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})],
    )
    directory = tmp_path / "cache"
    cache = ResultCache(disk=DiskCache(codec=MeshCodec(), directory=directory))
    loaded = evaluate(
        project.document, profile, sources=ProjectSources(project), cache=cache, quality=quality
    )
    assert loaded.complete
    original = loaded.scene.objects["obj_1"]
    feature = next(entry for entry in original.features.values() if entry.kind == "pin")
    assert feature.params["diameter"] == pytest.approx(dimensions["pin_diameter"], abs=1e-5)
    history.apply(
        "Zapfen ändern",
        [
            OperationDraft(
                op="resize_feature",
                inputs=(original.id,),
                params={"at_feature": feature.id, "diameter": dimensions["changed_diameter"]},
                seed=20260924,
            )
        ],
    )
    altered = evaluate(
        project.document, profile, sources=ProjectSources(project), cache=cache, quality=quality
    )
    assert altered.complete
    generated = altered.scene.objects[original.id].features[feature.id]
    assert generated.provenance == "generated" and generated.recognised
    assert generated.params["diameter"] == pytest.approx(dimensions["changed_diameter"])
    history.apply(
        "Kleine Teile entfernen",
        [OperationDraft(op="repair", inputs=(original.id,), params={"small_components": True})],
    )

    def checked(current, remembered: ResultCache) -> None:
        """Die wirkliche Ausgabe bleibt ein Würfel mit gültigen aktuellen Merkmalsflächen."""
        result = evaluate(
            current.document,
            profile,
            sources=ProjectSources(current),
            cache=remembered,
            quality=quality,
        )
        assert result.complete
        body = result.scene.objects[original.id]
        assert body.mesh.is_watertight and body.mesh.component_count == 1
        assert body.mesh.volume == pytest.approx(math.prod(dimensions["stock_size"]))
        assert feature.id not in body.features
        assert feature.id in body.reserved_feature_ids
        assert {entry.kind for entry in body.features.values()} == {"face"}
        assert len(body.features) == 6
        for entry in body.features.values():
            assert entry.recognised
            assert entry.face_indices and max(entry.face_indices) < body.mesh.triangle_count
        assert "repair.components_removed" in {
            finding.code for finding in result.scene.report.findings
        }

    checked(project, cache)
    checked(project, cache)
    save(project, tmp_path / "repair.p3d")
    forget_cache()
    reopened = load(tmp_path / "repair.p3d")
    checked(reopened, ResultCache(disk=DiskCache(codec=MeshCodec(), directory=directory)))
    history.undo()
    restored = evaluate(
        project.document, profile, sources=ProjectSources(project), cache=cache, quality=quality
    )
    assert restored.complete
    assert restored.scene.objects[original.id].mesh.component_count == 2
    assert restored.scene.objects[original.id].features[feature.id].recognised
    history.redo()
    checked(project, cache)
    history.apply(
        "Entfernten Zapfen ändern",
        [
            OperationDraft(
                op="resize_feature",
                inputs=(original.id,),
                params={"at_feature": feature.id, "diameter": dimensions["pin_diameter"]},
                seed=20260924,
            )
        ],
    )
    missing = evaluate(
        project.document, profile, sources=ProjectSources(project), cache=cache, quality=quality
    )
    assert missing.stopped_at == project.document.ops[-1].id
    blocker = next(
        finding
        for finding in missing.scene.report.findings
        if finding.op_id == missing.stopped_at and finding.severity == "error"
    )
    assert blocker.suggestions
    assert missing.scene.objects[original.id].mesh.volume == pytest.approx(
        math.prod(dimensions["stock_size"])
    )
