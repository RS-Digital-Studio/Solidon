"""Die Erkennung auf mehrere Prozesse verteilt (RM-637): dasselbe Ergebnis, Bit für Bit.

Die Arbeiter rechnen Antworten vorab, die die Erkennung der Reihe nach fragt;
die Erkennung findet sie unter ihrem Schlüssel oder rechnet selbst. Geprüft
wird der Zwei-Wege-Vertrag (Bauplan §11.2): mit und ohne Arbeiter dieselben
Merkmale, Arten und Kennungen, typgenau und in derselben Folge.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pytest
import trimesh

from app.core.errors import OperationCancelled
from app.core.geom.mesh import MeshData, read_mesh
from app.core.ingest.loader import normalise
from app.core.perceive import features, parallel

MESHES = Path(__file__).parent / "data" / "meshes"

#: Korpusnetze mit Flecken in allen drei Runden: Mantelnachweis, ganze Flecken,
#: Stücke samt tangentialer Trennung.
CORPUS = (
    "post_with_fillet.stl",
    "plate_coarse_slots.stl",
    "parts_enclosing_air.stl",
    "pocket_with_pin.stl",
    "torus_ring.stl",
    "recognition_bayonet_lid.npz",
    "sphere_socket.stl",
)


def _corpus(name: str) -> MeshData:
    path = MESHES / name
    if path.suffix == ".npz":
        with np.load(path, allow_pickle=False) as data:
            return MeshData(raw=trimesh.Trimesh(data["vertices"], data["faces"], process=False))
    return normalise(read_mesh(path.read_bytes(), path.suffix), "mm").mesh


def _fresh(mesh: MeshData) -> MeshData:
    return MeshData(
        raw=trimesh.Trimesh(mesh.raw.vertices.copy(), mesh.raw.faces.copy(), process=False)
    )


@pytest.fixture
def workers() -> Any:
    """Zwei Arbeiter, auch an kleinen Körpern; danach beendet."""
    before = parallel.use_workers(True, count=2)
    try:
        yield parallel
    finally:
        parallel.use_workers(before[0], count=before[1])
        parallel.shutdown()


def _fits_here(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    """Zählt die Einpassungen, die dieser Prozess selbst rechnet — nicht die der Arbeiter."""
    computed: list[str] = []
    for name in ("_fit_cylinder_measured", "_fit_cone_measured", "_fit_sphere_measured"):
        real = getattr(features, name)

        def counted(*args: Any, _real: Any = real, _name: str = name, **kwargs: Any) -> Any:
            computed.append(_name)
            return _real(*args, **kwargs)

        monkeypatch.setattr(features, name, counted)
    return computed


@pytest.mark.parametrize("name", CORPUS)
def test_workers_recognise_bit_for_bit_like_one_process(
    workers: Any, monkeypatch: pytest.MonkeyPatch, name: str
) -> None:
    """Mit Arbeitern dieselbe Erkennung wie ohne — und dieser Prozess rechnet weniger selbst."""
    mesh = _corpus(name)
    computed = _fits_here(monkeypatch)
    parallel.use_workers(False)
    features.forget_cache()
    alone = features.detect(_fresh(mesh))
    by_itself = len(computed)
    parallel.use_workers(True, count=2)
    features.forget_cache()
    computed.clear()
    shared = features.detect(_fresh(mesh))

    assert repr(shared) == repr(alone)
    assert len(computed) < by_itself, "die Antworten der Arbeiter kamen nicht an"


def test_without_answers_from_the_workers_the_detection_computes_itself(
    workers: Any, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Kommt kein Teil zurück (Arbeiter tot, ohne Speicher), rechnet die Erkennung selbst."""
    mesh = _corpus("post_with_fillet.stl")
    parallel.use_workers(False)
    features.forget_cache()
    alone = features.detect(_fresh(mesh))
    parallel.use_workers(True, count=2)
    asked: list[int] = []

    def nothing_back(_arrays: Any, tasks: Any, **_kwargs: Any) -> list[None]:
        asked.append(len(tasks))
        return [None] * len(tasks)

    monkeypatch.setattr(parallel, "run", nothing_back)
    features.forget_cache()

    assert repr(features.detect(_fresh(mesh))) == repr(alone)
    assert asked, "die Runden haben die Arbeiter gefragt"


def test_a_cancelled_round_stops_its_workers(workers: Any) -> None:
    """Ein Abbruch beim Warten beendet die rechnenden Arbeiter, statt sie zurückzulegen."""
    mesh = features._one_body(_corpus("recognition_waterfall.npz"))
    body = mesh.raw
    token = features._detection_key(mesh)
    assert parallel.prepare(features._worker_arrays(body), token)
    task = parallel.Task("classify", ((0, 1, 2),), frozenset(), False, token)

    def cancelled() -> None:
        raise OperationCancelled

    try:
        with pytest.raises(OperationCancelled):
            parallel.run(
                lambda: features._worker_arrays(body), [task], most=1, check_cancelled=cancelled
            )
    finally:
        parallel.release()
    assert parallel.statistics()["workers"] <= 1, "der rechnende Arbeiter ist beendet"


def test_after_the_detection_the_workers_let_go_of_the_body(workers: Any) -> None:
    """Der gemeinsame Speicher des Körpers geht mit der Erkennung (Speicher je Prozess)."""
    features.forget_cache()
    features.detect(_fresh(_corpus("post_with_fillet.stl")))

    assert parallel._PREPARED[0] is None


def test_a_round_without_a_prepared_body_asks_no_worker(workers: Any) -> None:
    """Außerhalb einer Erkennung, die den Körper vorbereitet hat, startet keine Runde Arbeiter."""
    mesh = features._one_body(_corpus("post_with_fillet.stl"))
    before = parallel.statistics().get("tasks", 0)

    answers = features._asked_by_workers(
        mesh.raw, "classify", [[0, 1, 2]], [1.0], set(), None, features._UNHEARD
    )

    assert answers == {}
    assert parallel.statistics().get("tasks", 0) == before


def test_the_round_splits_by_weight_without_losing_a_patch() -> None:
    """Zusammenhängende Teile, jeder Fleck genau einmal, höchstens so viele Teile wie verlangt."""
    weights = [5.0, 1.0, 1.0, 1.0, 4.0, 2.0, 2.0, 9.0]
    for parts in range(1, 10):
        ranges = parallel.split(weights, parts)
        assert len(ranges) <= parts
        assert [index for part in ranges for index in part] == list(range(len(weights)))


def _asked_inside_detect(mesh: MeshData, weights: list[float]) -> dict[str, Any]:
    """Eine Runde, wie ``detect`` sie fragt — mit erlaubten Arbeitern."""
    allowed = features._WORKERS_ALLOWED.set(True)
    try:
        return features._asked_by_workers(
            mesh.raw,
            "classify",
            [[0, 1, 2]] * len(weights),
            weights,
            set(),
            None,
            features._UNHEARD,
        )
    finally:
        features._WORKERS_ALLOWED.reset(allowed)


def test_a_light_round_stays_in_this_process(workers: Any) -> None:
    """Unter ``AHEAD_FROM_WEIGHT`` kostet der Weg zu den Arbeitern mehr als die Runde."""
    parallel.use_workers(True)
    mesh = features._one_body(_corpus("post_with_fillet.stl"))
    before = parallel.statistics().get("tasks", 0)

    assert _asked_inside_detect(mesh, [1.0] * 40) == {}
    assert parallel.statistics().get("tasks", 0) == before


def test_a_body_with_a_skin_asks_no_worker(workers: Any, monkeypatch: pytest.MonkeyPatch) -> None:
    """Ein Fleck über der Gedächtnisgrenze hält die ganze Runde im Prozess."""
    mesh = features._one_body(_corpus("post_with_fillet.stl"))
    monkeypatch.setattr(features, "REMEMBERED_PATCH_FACES", 0)
    monkeypatch.setattr(features, "REMEMBERED_PATCH_SHARE", 0.0)
    before = parallel.statistics().get("tasks", 0)

    assert _asked_inside_detect(mesh, [500.0] * 40) == {}
    assert parallel.statistics().get("tasks", 0) == before
