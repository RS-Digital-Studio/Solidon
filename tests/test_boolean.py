"""Die Boolesche Rückfallkette (Bauplan §17.2, §35).

Jede Stufe wird einmal erzwungen, damit keine von ihnen still verrottet: die
Kette lohnt nur, wenn Stufe 4 an dem Tag noch funktioniert, an dem Stufe 1
aufgibt.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import trimesh

from app.core.errors import BooleanFailedError
from app.core.geom.boolean import DRAFT_CHAIN, FULL_CHAIN, boolean, shared_volume
from app.core.geom.mesh import MeshData, read_mesh
from app.core.ingest.loader import normalise

MESHES = Path(__file__).parent / "data" / "meshes"


def solid(name: str = "cube_clean.stl") -> MeshData:
    return normalise(read_mesh((MESHES / name).read_bytes(), ".stl"), "mm").mesh


def box(size: float, offset: tuple[float, float, float]) -> MeshData:
    body = trimesh.creation.box(extents=(size, size, size))
    body.apply_translation(offset)
    return MeshData.of(body)


def test_union_of_two_overlapping_cubes() -> None:
    result = boolean("union", [solid(), box(20.0, (10.0, 0.0, 0.0))])

    assert result.solver.strategy == "direct"
    assert result.mesh.is_watertight
    assert result.mesh.volume == pytest.approx(12000.0, rel=1e-6), "8000 + 8000 - 4000 overlap"
    assert not result.findings, "the plain case has nothing to report"


def test_difference_removes_the_overlap() -> None:
    result = boolean("difference", [solid(), box(20.0, (10.0, 0.0, 0.0))])

    assert result.mesh.volume == pytest.approx(4000.0, rel=1e-6)
    assert result.solver.strategy == "direct"


def test_intersection_keeps_only_the_overlap() -> None:
    result = boolean("intersection", [solid(), box(20.0, (10.0, 0.0, 0.0))])

    assert result.mesh.volume == pytest.approx(4000.0, rel=1e-6)


def test_the_stage_that_worked_is_recorded() -> None:
    """§17.2: die erfolgreiche Stufe wird in die Operation geschrieben."""
    result = boolean("union", [solid(), box(20.0, (10.0, 0.0, 0.0))])

    assert result.solver.attempted == ("direct",)
    assert result.solver.seed is None


@pytest.mark.parametrize("stage", ["welded", "jittered", "voxel"])
def test_every_stage_can_carry_the_operation_alone(stage: str) -> None:
    """§35: jede Stufe einmal erzwungen — eine Kette, die niemand übt, ist
    eine Kette, die verrottet.
    """
    result = boolean(
        "union",
        [solid(), box(20.0, (10.0, 0.0, 0.0))],
        seed=20260728,
        stages=(stage,),  # type: ignore[arg-type]
    )

    assert result.solver.strategy == stage
    assert result.mesh.triangle_count > 0
    # Jitter bewegt Eckpunkte, Voxel runden auf ein Raster — beide tauschen
    # Genauigkeit gegen eine Antwort, und genau dafür sind die späteren Stufen
    # da (§17.2).
    tolerance = {"welded": 1e-6, "jittered": 1e-3, "voxel": 0.05}[stage]
    assert result.mesh.volume == pytest.approx(12000.0, rel=tolerance)


def test_the_voxel_stage_says_that_it_rounded() -> None:
    """§17.3: Stufe 4 kostet Genauigkeit und wird nie stillschweigend benutzt."""
    result = boolean("union", [solid(), box(20.0, (10.0, 0.0, 0.0))], stages=("voxel",))

    codes = {finding.code for finding in result.findings}
    assert "boolean.voxel" in codes
    assert any(finding.severity == "warning" for finding in result.findings)


def test_the_jitter_stage_carries_its_seed() -> None:
    """§11.3: ohne gespeicherten Startwert wäre das Ergebnis nicht
    reproduzierbar.
    """
    first = boolean("union", [solid(), box(20.0, (10.0, 0.0, 0.0))], seed=42, stages=("jittered",))
    second = boolean("union", [solid(), box(20.0, (10.0, 0.0, 0.0))], seed=42, stages=("jittered",))

    assert first.solver.seed == 42
    assert first.mesh.volume == pytest.approx(second.mesh.volume, rel=1e-12)


def test_draft_quality_stops_after_the_second_stage() -> None:
    """§31: das Iterieren bleibt schnell, der Entwurf gibt also keine Zeit für
    Voxel aus.
    """
    assert DRAFT_CHAIN == ("direct", "welded")
    assert FULL_CHAIN[:2] == DRAFT_CHAIN
    assert "voxel" in FULL_CHAIN and "voxel" not in DRAFT_CHAIN


def test_an_impossible_operation_ends_with_a_finding_and_a_way_forward() -> None:
    """§17.2 Stufe 5: aufgeben ist erlaubt, still aufgeben nicht."""
    with pytest.raises(BooleanFailedError) as caught:
        boolean(
            "intersection",
            [solid(), box(2.0, (500.0, 0.0, 0.0))],
            stages=("direct", "welded"),
        )

    assert caught.value.attempted == ("direct", "welded")
    assert caught.value.suggestions, "an error without a way forward is unfinished"


def test_at_least_two_bodies_are_needed() -> None:
    with pytest.raises(ValueError):
        boolean("union", [solid()])


# --- as operations --------------------------------------------------------------


def two_body_document(document, profile):
    """Zwei überlappende Würfel in einem Dokument, bereit für eine Boolesche
    Operation.
    """
    from app.core.registry import REGISTRY
    from app.core.scene import History, OperationDraft
    from app.core.scene.project import new_project
    from app.core.types import Source
    from app.i18n import _

    project = new_project("centauri-carbon-2", "petg")
    project.document = document
    for index, name in enumerate(("cube_clean.stl", "cube_clean.stl"), start=1):
        document.sources[f"src_{index}"] = Source(
            id=f"src_{index}", kind="import", path=f"sources/{index}_{name}", sha256=""
        )
        project.sources[f"src_{index}"] = (MESHES / name).read_bytes()

    history = History(document)
    history.apply(
        _("Laden"),
        [
            OperationDraft(op="load", params={"source": "src_1", "unit": "mm"}),
            OperationDraft(op="load", params={"source": "src_2", "unit": "mm"}),
        ],
    )
    history.apply(
        _("Verschieben"),
        [OperationDraft(op="translate_object", inputs=("obj_2",), params={"dx": 10.0})],
    )
    assert REGISTRY.has("union_objects")
    return project, history


def test_a_boolean_operation_records_its_stage(document, profile) -> None:
    """§17.2: die Stufe, die die Operation getragen hat, wird in den Stapel
    geschrieben.
    """
    from app.core.scene import OperationDraft, evaluate
    from app.core.scene.project import ProjectSources
    from app.i18n import _

    project, history = two_body_document(document, profile)
    history.apply(
        _("Vereinigen"),
        [OperationDraft(op="union_objects", inputs=("obj_1", "obj_2"))],
    )

    result = evaluate(document, profile, sources=ProjectSources(project))

    assert result.complete
    # Zwei Körper hinein, einer heraus: das Ergebnis ist ein neues Objekt, die
    # Eingaben sind verbraucht.
    assert result.scene.objects["obj_3"].mesh.volume == pytest.approx(12000.0, rel=1e-6)
    assert "obj_1" not in result.scene.objects

    union_op = history.operations[-1]
    assert union_op.seed is not None, "a randomised operation carries a seed (§11.3)"
    assert result.solvers[union_op.id].strategy == "direct"

    history.record_solvers(result.solvers)
    assert history.operation(union_op.id).solver is not None
    assert history.operation(union_op.id).solver.strategy == "direct"


def test_subtracting_and_intersecting_run_as_operations(document, profile) -> None:
    from app.core.scene import OperationDraft, evaluate
    from app.core.scene.project import ProjectSources
    from app.i18n import _

    project, history = two_body_document(document, profile)
    history.apply(
        _("Abziehen"),
        [OperationDraft(op="subtract_objects", inputs=("obj_1", "obj_2"))],
    )

    result = evaluate(document, profile, sources=ProjectSources(project))
    assert result.scene.objects["obj_3"].mesh.volume == pytest.approx(4000.0, rel=1e-6)
    assert "obj_2" not in result.scene.objects, "both inputs were consumed"


def test_intersect_objects_runs_as_an_operation(document, profile) -> None:
    from app.core.scene import OperationDraft, evaluate
    from app.core.scene.project import ProjectSources
    from app.i18n import _

    project, history = two_body_document(document, profile)
    history.apply(
        _("Schnittmenge"),
        [OperationDraft(op="intersect_objects", inputs=("obj_1", "obj_2"))],
    )

    result = evaluate(document, profile, sources=ProjectSources(project))
    assert result.complete
    assert result.scene.objects["obj_3"].mesh.volume == pytest.approx(4000.0, rel=1e-6)


# --- Ein falscher Aufruf ist keine Antwort (§33.1) -------------------------------


def test_a_wrong_call_into_the_kernel_is_not_swallowed(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die Lektion der konvexen Zerlegung, dort festgehalten, wo es geht.

    Handler um einen Kern fangen breit, denn ein Kern scheitert auf Kernarten,
    und das ist eine Antwort. Ein TypeError ist keine: er heißt, dass der
    Aufruf falsch ist, und ihn zu verschlucken macht aus einem Fehler ein leeres
    Ergebnis. Die Zerlegung aus §22.3 tat genau das, zwei Phasen lang, hinter
    einer grünen Suite.
    """

    def wrong(*_args: object, **_kwargs: object) -> None:
        raise TypeError("intersection(): incompatible function arguments")

    monkeypatch.setattr(trimesh.boolean, "intersection", wrong)

    with pytest.raises(TypeError):
        shared_volume(solid().raw, solid().raw)


def test_a_kernel_that_gives_up_is_still_an_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Die andere Hälfte der Regel: wofür der Handler wirklich da ist, bleibt
    gefangen.
    """

    def gave_up(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("manifold: could not solve")

    monkeypatch.setattr(trimesh.boolean, "intersection", gave_up)

    assert shared_volume(solid().raw, solid().raw) == 0.0
