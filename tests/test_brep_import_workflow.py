"""NURBS-Import, Merkmalsaktion und Projektverlauf bleiben ein durchgehender Weg."""

from __future__ import annotations

import math
from collections import Counter
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest

from app.core.bootstrap import load_operations
from app.core.brep import edit, step
from app.core.brep.kernel import Solid
from app.core.errors import OperationCancelled
from app.core.geom.mesh import MeshCodec, as_mesh_data
from app.core.ingest.plan import import_plan
from app.core.perceive.actions import actions_for
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.cache import DiskCache, ResultCache
from app.core.scene.cancel import CancelSignal
from app.core.scene.project import ProjectSources, load, new_project, save
from app.core.types import Profile, SceneObject, Source
from app.core.units import EPS_GEOM
from tests.helpers import exact_kernel


def _step_plate() -> bytes:
    """Analytischer Sollkörper mit vollständig rationalen Trägerflächen in STEP."""
    exact_kernel()
    from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert

    plate = edit.cut_bore(
        edit.box(40.0, 30.0, 10.0),
        position=(0.0, 0.0, 5.0),
        direction=(0.0, 0.0, 1.0),
        diameter=6.0,
        depth=20.0,
    )
    return step.write(Solid(BRepBuilderAPI_NurbsConvert(plate.shape, True).Shape()))


def _check_plate(entry: SceneObject, diameter: float) -> str:
    """Die Rechnung stammt vom Quader minus Kreisbohrung, nicht vom Erkenner."""
    assert entry.kind == "brep"
    assert isinstance(entry.mesh, Solid)
    assert entry.mesh.is_closed and entry.mesh.solid_count == 1
    assert entry.mesh.volume == pytest.approx(12000.0 - 2.5 * math.pi * diameter**2, abs=EPS_GEOM)
    assert Counter(feature.kind for feature in entry.features.values()) == {"face": 6, "hole": 1}
    hole = next(feature for feature in entry.features.values() if feature.kind == "hole")
    assert hole.params["diameter"] == pytest.approx(diameter, abs=EPS_GEOM)
    assert hole.params["depth"] == pytest.approx(10.0, abs=EPS_GEOM)
    assert hole.params["centre"] == pytest.approx((0.0, 0.0, 5.0), abs=EPS_GEOM)
    assert hole.params["through"] is True
    assert len(entry.mesh.faces_of_triangles(hole.face_indices)) == 1
    return hole.id


@pytest.mark.parametrize("cache_mode", ["cold", "memory", "reopened"])
def test_nurbs_step_can_be_edited_saved_reopened_and_undone(
    tmp_path: Path, profile: Profile, cache_mode: str
) -> None:
    """Der Importplan und die angebotene Aktion führen ohne Formumwandlung bis zum Undo."""
    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    payload = _step_plate()
    project.sources["src_1"] = payload
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/nurbs_plate.step", sha256=""
    )
    plan = import_plan("src_1", "nurbs_plate.step", payload)
    assert plan.draft.op == "load_step" and not plan.asks_unit
    history = History(project.document)
    history.apply(plan.title, [plan.draft])
    cache = ResultCache(disk=DiskCache(codec=MeshCodec(), directory=tmp_path / "cache"))
    before = evaluate(project.document, profile, sources=ProjectSources(project), cache=cache)
    assert before.complete
    original = before.scene.objects["obj_1"]
    hole_id = _check_plate(original, 6.0)
    original_features = deepcopy(original.features)
    hole = original.features[hole_id]
    actions = actions_for(hole, original.features, mesh=as_mesh_data(original.mesh))
    assert any(action.op == "resize_hole" for action in actions)

    history.apply(
        "Bohrung ändern",
        [
            OperationDraft(
                op="resize_hole",
                inputs=(original.id,),
                params={"at_feature": hole_id, "diameter": 8.0, "compensate": False},
            )
        ],
    )
    if cache_mode != "memory":
        cache = ResultCache(
            disk=DiskCache(codec=MeshCodec(), directory=tmp_path / "cache")
            if cache_mode == "reopened"
            else None
        )
    after = evaluate(project.document, profile, sources=ProjectSources(project), cache=cache)
    assert after.complete, [
        (finding.code, str(finding.message)) for finding in after.scene.report.findings
    ]
    assert _check_plate(after.scene.objects[original.id], 8.0) == hole_id
    assert not any(finding.converts_exact_body for finding in after.scene.report.findings)
    assert original.features == original_features
    _check_plate(original, 6.0)

    path = save(project, tmp_path / "nurbs.solidon")
    reopened = load(path)
    fresh = evaluate(reopened.document, profile, sources=ProjectSources(reopened))
    assert fresh.complete
    assert _check_plate(fresh.scene.objects[original.id], 8.0) == hole_id
    assert reopened.sources["src_1"] == payload
    reopened_history = History(reopened.document)
    reopened_history.undo()
    back = evaluate(reopened.document, profile, sources=ProjectSources(reopened))
    assert back.complete
    assert _check_plate(back.scene.objects[original.id], 6.0) == hole_id
    reopened_history.redo()
    again = evaluate(reopened.document, profile, sources=ProjectSources(reopened))
    assert again.complete
    assert _check_plate(again.scene.objects[original.id], 8.0) == hole_id


def test_import_cancellation_reaches_surface_recognition_without_caching_a_partial_body(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Abbrechen während der ersten Trägerprüfung lässt Quelle und Verlauf vollständig stehen."""
    from app.core.brep import canonical

    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    payload = _step_plate()
    project.sources["src_1"] = payload
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/nurbs_plate.step", sha256=""
    )
    plan = import_plan("src_1", "nurbs_plate.step", payload)
    History(project.document).apply(plan.title, [plan.draft])
    initial = deepcopy(project.document)
    signal = CancelSignal()
    cache = ResultCache()
    original_describe = canonical.describe
    visited = []

    def stop_after_one_surface(face, *, cancelled=None):
        """Der echte erste Träger wird geprüft; dann kommt der äußere Abbruchauftrag."""
        assert cancelled is signal
        result = original_describe(face, cancelled=cancelled)
        visited.append(face)
        signal.cancel()
        return result

    with monkeypatch.context() as during:
        during.setattr(canonical, "describe", stop_after_one_surface)
        with pytest.raises(OperationCancelled):
            evaluate(
                project.document,
                profile,
                sources=ProjectSources(project),
                cache=cache,
                cancelled=signal,
            )
    assert len(visited) == 1
    assert len(cache) == 0
    assert project.document == initial
    assert project.sources["src_1"] == payload
    signal.reset()
    retried = evaluate(
        project.document, profile, sources=ProjectSources(project), cache=cache, cancelled=signal
    )
    assert retried.complete and len(cache) == 1
    _check_plate(retried.scene.objects["obj_1"], 6.0)


def _box_shell(drop: int | None = None) -> Solid:
    """Die sechs Flächen eines Quaders 10 × 20 × 30 als genähte Schale, ohne Körper.

    Mit ``drop`` fehlt diese Fläche — dann ist die Schale offen.
    """
    exact_kernel()
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer

    sewing = BRepBuilderAPI_Sewing(EPS_GEOM)
    faces = TopExp_Explorer(edit.box(10.0, 20.0, 30.0).shape, TopAbs_FACE)
    index = 0
    while faces.More():
        if index != drop:
            sewing.Add(faces.Current())
        index += 1
        faces.Next()
    sewing.Perform()
    return Solid(sewing.SewedShape())


def _loaded(payload: bytes, profile: Profile) -> tuple[SceneObject, list[Any]]:
    """Der echte Einleseweg: Importplan, Verlauf, Auswertung."""
    load_operations()
    project = new_project("centauri-carbon-2", "petg")
    project.sources["src_1"] = payload
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/teil.step", sha256=""
    )
    plan = import_plan("src_1", "teil.step", payload)
    assert plan.draft.op == "load_step"
    History(project.document).apply(plan.title, [plan.draft])
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete
    return result.scene.objects["obj_1"], list(result.scene.report.findings)


def test_a_closed_surface_model_is_read_as_a_solid(profile: Profile) -> None:
    """Ein Flächenmodell (``SHELL_BASED_SURFACE_MODEL``) mit dichter Schale ist ein Körper.

    Manche Programme schreiben ein Teil als dichte Schale ohne Volumenkörper.
    Bis zum 22.09.2026 kam es so an: null Volumenkörper, und jede Handlung,
    die „ein Stück" prüft, sagte ab, obwohl nichts fehlte. Die Datei hier
    schreibt OpenCASCADE selbst aus der genähten Schale eines Quaders.
    """
    payload = step.write(_box_shell())
    assert b"SHELL_BASED_SURFACE_MODEL" in payload
    assert b"MANIFOLD_SOLID_BREP" not in payload
    entry, findings = _loaded(payload, profile)
    body = entry.mesh
    assert isinstance(body, Solid)
    assert body.solid_count == 1 and body.is_closed
    assert body.volume == pytest.approx(6000.0, abs=EPS_GEOM)
    assert "ingest.not_watertight" not in {finding.code for finding in findings}
    moved = edit.moved(body, (5.0, 0.0, 0.0))
    assert moved.solid_count == 1 and moved.volume == pytest.approx(6000.0, abs=EPS_GEOM)


def test_an_open_surface_model_says_so_and_points_to_repair(profile: Profile) -> None:
    """Eine offene Schale kommt an, bleibt offen — und der Befund sagt, was hilft.

    Bis zum 22.09.2026 kam sie ohne Wort an, mit einem „Volumen" aus der
    offenen Hülle und einem ``is_closed``, das immer Ja sagte. Jetzt steht
    derselbe Befund da wie beim offenen Netz, mit der Zahl der offenen
    Kanten: vier, der Rand der fehlenden Fläche.

    **Der Satz sagt den Zustand, der Knopf den Weg** (Bedienweg D4,
    25.09.2026): Der Rat „Reparieren schließt die offenen Stellen" stand im
    Satz und als Knopf darunter. Der Knopf kommt aus ``panels.FINDING_ACTIONS``
    und führt zur Reparatur.
    """
    from app.ui.panels import FINDING_ACTIONS

    payload = step.write(_box_shell(drop=5))
    entry, findings = _loaded(payload, profile)
    body = entry.mesh
    assert isinstance(body, Solid)
    assert not body.is_closed and body.solid_count == 0
    warnings = [finding for finding in findings if finding.code == "ingest.not_watertight"]
    assert len(warnings) == 1
    assert warnings[0].severity == "warning"
    assert warnings[0].values["open_edges"] == 4
    assert str(warnings[0].message) == "Das Modell ist nicht geschlossen."
    assert FINDING_ACTIONS["ingest.not_watertight"][0].id == "repair_and_retry"
