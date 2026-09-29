"""Der Hilfsprozess des Netzkerns (RM-212): dieselben Bytes, echtes Abbrechen, keine Waisen.

``manifold3d`` hält den GIL in jedem Aufruf; große Kernaufrufe rechnet deshalb
``app.core.geom.kernel_process`` in einem eigenen Prozess. Geprüft wird hier:

* **Bitgleich** — jede Rechnung aus ``kernel_jobs.JOBS`` und jeder öffentliche
  Weg dorthin gibt im Hilfsprozess dieselben Felder und Zahlen wie im Prozess.
* **Abbrechen beendet den Hilfsprozess**, auch mitten in einem Kernaufruf.
* **Ein toter Hilfsprozess** ist eine Meldung mit Handlungsvorschlag, ein
  stummer ein Rückfall in den Prozess — nie stilles Warten.
* **Keine Waisen**: ``shutdown`` räumt auf, und ein hart beendeter
  Elternprozess nimmt seinen Hilfsprozess mit.
* **Der Anschluss**: Die grobe Vorschau und das Übernehmen einer großen
  Verfeinerung rechnen, wie ihre Arbeiterfäden sie rufen, im Hilfsprozess.

Was im Prozess bleibt: der Hauptfaden und alles unter ``OFFLOAD_ABOVE``. Die
Suite rechnet deshalb sonst nirgends im Hilfsprozess; wer ihn hier braucht,
setzt die Schwelle auf null und ruft aus einem Nebenfaden.
"""

from __future__ import annotations

import ast
import errno
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import threading
import time
from collections.abc import Callable, Iterator
from multiprocessing import shared_memory
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import trimesh

from app.core.errors import OperationCancelled
from app.core.geom import kernel_jobs, kernel_process
from app.core.geom.mesh import MeshData
from app.core.scene.cancel import CancelSignal

ROOT = Path(__file__).resolve().parent.parent
MESHES = Path(__file__).parent / "data" / "meshes"


@pytest.fixture(autouse=True)
def _no_helper_outlives_a_test() -> Iterator[None]:
    """Jeder Test beginnt und endet ohne Hilfsprozess, und er zählt für sich."""
    kernel_process.shutdown()
    kernel_process._POOL.counts.clear()
    yield
    kernel_process.shutdown()


@pytest.fixture
def offloaded(monkeypatch: pytest.MonkeyPatch) -> None:
    """Schwelle null: jede Rechnung aus einem Nebenfaden geht in den Hilfsprozess."""
    monkeypatch.setattr(kernel_process, "OFFLOAD_ABOVE", 0)


def in_a_worker(work: Callable[[], Any], timeout: float = 120.0) -> Any:
    """``work`` in einem Nebenfaden — wie die Arbeiter von Vorschau, Auswertung und Ansicht."""
    box: dict[str, Any] = {}

    def run() -> None:
        try:
            box["value"] = work()
        except BaseException as problem:
            box["error"] = problem

    worker = threading.Thread(target=run, name="kernel-test")
    worker.start()
    worker.join(timeout)
    assert not worker.is_alive(), f"der Nebenfaden kam in {timeout} s nicht zurück"
    if "error" in box:
        raise box["error"]
    return box["value"]


def welded(name: str) -> MeshData:
    """Ein Korpusnetz, verschweißt wie beim Import — der Kern nimmt nur geschlossene."""
    return MeshData.of(trimesh.load(str(MESHES / name), force="mesh"))


def mesh_input(mesh: MeshData, suffix: str = "") -> dict[str, np.ndarray]:
    return {
        f"vertices{suffix}": np.asarray(mesh.raw.vertices),
        f"faces{suffix}": np.asarray(mesh.raw.faces),
    }


def same_bytes(first: dict[str, np.ndarray], second: dict[str, np.ndarray]) -> None:
    assert first.keys() == second.keys()
    for name in first:
        assert first[name].dtype == second[name].dtype, name
        assert first[name].shape == second[name].shape, name
        assert first[name].tobytes() == second[name].tobytes(), name


def _cylinder_through(mesh: MeshData) -> MeshData:
    low, high = mesh.bounds.minimum, mesh.bounds.maximum
    tool = trimesh.creation.cylinder(radius=3.0, height=float(high[2] - low[2]) + 4.0, sections=48)
    tool.apply_translation([(low[index] + high[index]) / 2.0 for index in range(3)])
    return MeshData.of(tool)


def _job_cases() -> list[tuple[str, Callable[[], tuple[dict[str, np.ndarray], dict[str, Any]]]]]:
    """Je Rechnung ein Eingang, an dem sie etwas tut (nicht nur ``found=False``)."""

    def plate() -> MeshData:
        return welded("plate_holes.stl")

    def display() -> tuple[dict[str, np.ndarray], dict[str, Any]]:
        body = welded("near_sphere_ellipsoid.stl")
        return mesh_input(body), {
            "target": 600,
            "tolerance": 0.05,
            "growth": 4.0,
            "steps": 6,
            "triangles": body.triangle_count,
        }

    def at_most() -> tuple[dict[str, np.ndarray], dict[str, Any]]:
        # Einmal geteilt: Die neuen Ecken liegen in den ebenen Flächen, und
        # ``simplify(0)`` nimmt sie ohne Abweichung wieder heraus.
        source = plate().raw
        vertices, faces = trimesh.remesh.subdivide(
            np.asarray(source.vertices), np.asarray(source.faces)
        )
        body = MeshData.of(trimesh.Trimesh(vertices=vertices, faces=faces, process=False))
        return mesh_input(body), {"tolerance": 0.0, "most": body.triangle_count * 0.95}

    def search() -> tuple[dict[str, np.ndarray], dict[str, Any]]:
        body = welded("near_sphere_ellipsoid.stl")
        return mesh_input(body), {"target": 700, "limit": 1.0, "steps": 32, "resolution": 1e-3}

    def conforming() -> tuple[dict[str, np.ndarray], dict[str, Any]]:
        return mesh_input(plate()), {
            "edge": 2.0,
            "most": 8_000_000,
            "passes": 12,
            "slack": 1e-6,
        }

    def once() -> tuple[dict[str, np.ndarray], dict[str, Any]]:
        return mesh_input(welded("torus_ring.stl")), {"edge": 0.5}

    def simplify_refine() -> tuple[dict[str, np.ndarray], dict[str, Any]]:
        return mesh_input(plate()), {"deviation": 0.01, "edge": 1.0}

    def smooth_refine() -> tuple[dict[str, np.ndarray], dict[str, Any]]:
        return mesh_input(welded("sphere_socket.stl")), {"angle": 52.5, "edge": 1.0}

    def boolean() -> tuple[dict[str, np.ndarray], dict[str, Any]]:
        body = plate()
        return {**mesh_input(body, "0"), **mesh_input(_cylinder_through(body), "1")}, {
            "bodies": 2,
            "kind": "difference",
        }

    def closed() -> tuple[dict[str, np.ndarray], dict[str, Any]]:
        return mesh_input(plate()), {"tolerance": 1e-6}

    def gap() -> tuple[dict[str, np.ndarray], dict[str, Any]]:
        body = plate()
        other = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
        other.apply_translation((0.0, 0.0, 40.0))
        return {**mesh_input(body, "0"), **mesh_input(MeshData.of(other), "1")}, {"search": 50.0}

    def labels() -> tuple[dict[str, np.ndarray], dict[str, Any]]:
        from app.core.geom.mesh import _adjacency_by_place

        body = welded("two_components.stl")
        edges = np.asarray(_adjacency_by_place(body.raw), dtype=np.int64).reshape(-1, 2)
        return {"edges": edges}, {"count": body.triangle_count}

    return [
        ("display_simplify", display),
        ("simplify_at_most", at_most),
        ("simplify_search", search),
        ("refine_conforming", conforming),
        ("refine_once", once),
        ("simplify_and_refine", simplify_refine),
        ("smooth_and_refine", smooth_refine),
        ("boolean", boolean),
        ("simplify_closed", closed),
        ("min_gap", gap),
        ("component_labels", labels),
    ]


def test_every_job_has_a_case() -> None:
    """Eine neue Rechnung in ``JOBS`` bekommt ihren Fall für die Bitgleichheit unten."""
    assert {name for name, _case in _job_cases()} == set(kernel_jobs.JOBS)


@pytest.mark.parametrize(("job", "case"), _job_cases(), ids=[name for name, _ in _job_cases()])
def test_a_job_gives_the_same_bytes_in_the_helper_as_here(
    job: str,
    case: Callable[[], tuple[dict[str, np.ndarray], dict[str, Any]]],
    offloaded: None,
) -> None:
    """Dieselbe Rechnung, dieselben Eingänge, dieselbe ``manifold3d``-Fassung: dieselben Bytes.

    Das ist die Zusage, unter der der Hilfsprozess überhaupt rechnen darf —
    Cache, Determinismus (Regel 6) und jede Zahl im Prüfbericht hängen daran.
    Verglichen wird Byte für Byte, nicht auf eine Toleranz.
    """
    arrays, values = case()
    here = kernel_jobs.JOBS[job](arrays, dict(values), lambda: None)

    there = in_a_worker(lambda: kernel_process.run(job, arrays, values, weight=1))

    same_bytes(here[0], there[0])
    assert here[1] == there[1]
    assert kernel_process.statistics().get(f"helper:{job}") == 1, "im Hilfsprozess gerechnet"
    assert here[0] or here[1].get("gap") is not None, "der Fall tut etwas"


def test_the_public_ways_give_the_same_mesh_through_the_helper(offloaded: None) -> None:
    """Anzeige-Dezimierung, Verfeinern und Boolesches: dasselbe Netz, ob hier oder dort gerechnet.

    Im Hauptfaden bleibt jede Rechnung im Prozess; derselbe Aufruf aus einem
    Nebenfaden geht über den Hilfsprozess. Verglichen werden Eckpunkte,
    Dreiecke und Slots des fertigen Netzes — also auch alles, was der
    Elternprozess danach daraus macht (Verschweißen, Slots, Herkunft).
    """
    from app.core.geom.boolean import boolean
    from app.core.geom.measure import surface_gap
    from app.core.geom.mesh_ops import decimate_for_display, remesh, uniform

    plate = welded("plate_holes.stl")
    ellipsoid = welded("near_sphere_ellipsoid.stl")
    tool = _cylinder_through(plate)
    ways: list[Callable[[], Any]] = [
        lambda: decimate_for_display(ellipsoid, 600),
        lambda: remesh(plate, 2.0),
        lambda: uniform(plate, 1.0, 0.01),
        lambda: boolean("difference", [plate, tool]).mesh,
        lambda: surface_gap(plate, tool, 50.0),
    ]
    for way in ways:
        here = way()
        there = in_a_worker(way)
        if isinstance(here, MeshData):
            assert isinstance(there, MeshData)
            same_bytes(
                {"vertices": np.asarray(here.raw.vertices), "faces": np.asarray(here.raw.faces)},
                {"vertices": np.asarray(there.raw.vertices), "faces": np.asarray(there.raw.faces)},
            )
            assert tuple(here.slots) == tuple(there.slots)
        else:
            assert here == there
    counts = kernel_process.statistics()
    assert counts["helper"] >= len(ways), counts
    assert counts["started"] == 1, "ein Hilfsprozess für alle — er wartet zwischen den Rechnungen"


def test_face_components_are_those_of_trimesh_in_both_places(offloaded: None) -> None:
    """``face_components`` zählt wie ``trimesh.graph.connected_components`` — hier und dort.

    Die Nummern rechnet seit RM-212 ``kernel_jobs.component_labels`` (an großen
    Netzen im Hilfsprozess, ``csgraph`` hält den GIL); die Gruppen danach sind
    dieselben wie aus trimesh: gleiche Teile, gleiche Reihenfolge, gleiche
    Dreiecke.
    """
    from app.core.geom.mesh import _adjacency_by_place, face_components

    for name in ("two_components.stl", "crossing_and_apart.stl", "plate_holes.stl"):
        body = welded(name).raw
        expected = trimesh.graph.connected_components(
            _adjacency_by_place(body), nodes=np.arange(len(body.faces)), engine="scipy"
        )
        for got in (
            face_components(body.copy()),
            in_a_worker(lambda b=body: face_components(b.copy())),
        ):
            assert len(got) == len(expected), name
            for piece, reference in zip(got, expected, strict=True):
                assert np.array_equal(piece, np.asarray(reference, dtype=np.int64)), name
    assert kernel_process.statistics().get("helper:component_labels") == 3


def test_the_main_thread_and_small_jobs_stay_in_this_process(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Der Hauptfaden wartete auf den Hilfsprozess wie auf den Kern selbst; Kleines lohnt nicht.

    Die Schwelle kommt aus der Messung (``OFFLOAD_ABOVE``); darunter und im
    Hauptfaden startet kein Prozess.
    """
    plate = welded("plate_holes.stl")
    arrays, values = mesh_input(plate), {"tolerance": 1e-6}

    kernel_process.run("simplify_closed", arrays, values, weight=10**9)
    in_a_worker(
        lambda: kernel_process.run(
            "simplify_closed", arrays, values, weight=kernel_process.OFFLOAD_ABOVE
        )
    )

    assert kernel_process.statistics()["started"] == 0
    assert kernel_process.processes() == []
    monkeypatch.setattr(kernel_process, "OFFLOAD_ABOVE", 0)
    assert not kernel_process.offloaded(1), "im Hauptfaden nie"
    assert in_a_worker(lambda: kernel_process.offloaded(1)), "im Nebenfaden über der Schwelle"


def test_a_kernel_error_in_the_helper_comes_back_as_it_would_here(offloaded: None) -> None:
    """Was der Kern selbst wirft, kommt unverändert an — die Rückfallkette fängt genau das.

    Ein offenes Netz nimmt der Kern nicht (``status`` ist kein ``NoError``); das
    ist ein ``ValueError`` mit demselben Text wie im Prozess, und der
    Hilfsprozess bleibt für die nächste Rechnung.
    """
    open_mesh = welded("broken_open.stl")
    plate = welded("plate_holes.stl")
    arrays = {**mesh_input(open_mesh, "0"), **mesh_input(plate, "1")}
    values = {"bodies": 2, "kind": "union"}
    with pytest.raises(ValueError) as here:
        kernel_jobs.boolean(arrays, dict(values), lambda: None)

    with pytest.raises(ValueError) as there:
        in_a_worker(lambda: kernel_process.run("boolean", arrays, values, weight=1))

    assert str(there.value) == str(here.value)
    assert any("Hilfsprozess" in note for note in getattr(there.value, "__notes__", ()))
    assert len(kernel_process.processes()) == 1, "der Hilfsprozess lebt weiter"


# --- Abbrechen, Tod, Stille --------------------------------------------------------------


def _answers_nothing(connection: Any) -> None:
    """Ein Hilfsprozess, der nach dem Start nie antwortet."""
    time.sleep(600.0)


def _never_accepts(connection: Any) -> None:
    """Ein Hilfsprozess, der bereit meldet und dann keine Rechnung annimmt."""
    connection.send(("ready", os.getpid()))
    time.sleep(600.0)


def _dies_mid_job(connection: Any) -> None:
    """Ein Hilfsprozess, der eine Rechnung annimmt und dabei stirbt."""
    connection.send(("ready", os.getpid()))
    connection.recv()
    connection.send(("accepted",))
    os._exit(3)


def _computes_forever(connection: Any) -> None:
    """Ein Hilfsprozess, der annimmt und nie fertig wird — ein Kernaufruf ohne Ende.

    Die Datei aus ``KERNEL_TEST_MARK`` sagt dem Test, dass die Rechnung läuft.
    """
    connection.send(("ready", os.getpid()))
    connection.recv()
    connection.send(("accepted",))
    Path(os.environ["KERNEL_TEST_MARK"]).write_text("rechnet", encoding="utf-8")
    time.sleep(600.0)


def _small_job() -> tuple[dict[str, np.ndarray], dict[str, Any]]:
    return mesh_input(welded("plate_holes.stl")), {"tolerance": 1e-6}


def test_a_helper_that_never_starts_falls_back_to_this_process(
    offloaded: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nach der Startfrist wird der stumme Hilfsprozess beendet, und die Rechnung läuft hier.

    Das ist der Fall eines eingefrorenen Pakets ohne ``freeze_support``: Der
    Kindprozess startet die Anwendung, statt zu antworten. Nach dem
    gescheiterten Start rechnet die Sitzung ohne Hilfsprozess weiter.
    """
    monkeypatch.setattr(kernel_process, "_SERVE", _answers_nothing)
    monkeypatch.setattr(kernel_process, "STARTUP_SECONDS", 1.0)
    arrays, values = _small_job()
    expected = kernel_jobs.simplify_closed(arrays, dict(values), lambda: None)

    started = time.monotonic()
    got = in_a_worker(lambda: kernel_process.run("simplify_closed", arrays, values, weight=1))

    assert time.monotonic() - started < 20.0
    same_bytes(expected[0], got[0])
    counts = kernel_process.statistics()
    assert counts["fallback"] == 1 and counts["helper"] == 0
    assert kernel_process.processes() == [], "der stumme Hilfsprozess ist beendet"
    assert kernel_process._POOL.disabled, "nach dem Fehlstart ohne Hilfsprozess"
    in_a_worker(lambda: kernel_process.run("simplify_closed", arrays, values, weight=1))
    assert kernel_process.statistics()["started"] == 1, "kein zweiter Versuch"


def test_a_helper_that_does_not_accept_a_job_falls_back_to_this_process(
    offloaded: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nimmt ein Hilfsprozess eine Rechnung nicht an, hängt er — beendet, und hier gerechnet."""
    monkeypatch.setattr(kernel_process, "_SERVE", _never_accepts)
    monkeypatch.setattr(kernel_process, "ACCEPT_SECONDS", 1.0)
    arrays, values = _small_job()
    expected = kernel_jobs.simplify_closed(arrays, dict(values), lambda: None)

    got = in_a_worker(lambda: kernel_process.run("simplify_closed", arrays, values, weight=1))

    same_bytes(expected[0], got[0])
    assert kernel_process.statistics()["fallback"] == 1
    assert kernel_process.processes() == []


def test_a_helper_that_dies_mid_job_is_a_message_with_a_way_forward(
    offloaded: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stirbt der Hilfsprozess in einer Rechnung, kommt sofort eine Meldung — kein stilles Warten.

    Im Prozess der Anwendung hätte derselbe Absturz sie mitgerissen. Die
    Meldung trägt Handlungsvorschläge (Regel 17), und die nächste Rechnung
    startet einen frischen Hilfsprozess.
    """
    monkeypatch.setattr(kernel_process, "_SERVE", _dies_mid_job)
    arrays, values = _small_job()

    started = time.monotonic()
    with pytest.raises(kernel_process.KernelHelperLostError) as lost:
        in_a_worker(lambda: kernel_process.run("simplify_closed", arrays, values, weight=1))

    assert time.monotonic() - started < 20.0, "der Tod meldet sich sofort, nicht nach einer Frist"
    assert lost.value.suggestions, "Regel 17"
    assert lost.value.detail
    assert lost.value.values["triangles"] == 1
    assert kernel_process.processes() == []
    monkeypatch.setattr(kernel_process, "_SERVE", kernel_jobs.serve)
    in_a_worker(lambda: kernel_process.run("simplify_closed", arrays, values, weight=1))
    assert kernel_process.statistics()["helper"] == 1, "der nächste Hilfsprozess rechnet"


def test_cancelling_ends_the_helper_even_inside_a_kernel_call(
    offloaded: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``ctx.cancelled`` beendet den Hilfsprozess wirklich.

    Ein Kernaufruf ist anders nicht anzuhalten; der wartende Faden kehrt binnen
    Sekunden mit ``OperationCancelled`` zurück.
    """
    mark = tmp_path / "rechnet"
    monkeypatch.setenv("KERNEL_TEST_MARK", str(mark))
    monkeypatch.setattr(kernel_process, "_SERVE", _computes_forever)
    arrays, values = _small_job()
    signal = CancelSignal()
    outcome: dict[str, Any] = {}

    def compute() -> None:
        try:
            kernel_process.run("simplify_closed", arrays, values, weight=1, cancelled=signal)
        except OperationCancelled:
            outcome["cancelled"] = time.monotonic()

    worker = threading.Thread(target=compute)
    worker.start()
    deadline = time.monotonic() + 60.0
    while not mark.exists() and time.monotonic() < deadline:
        time.sleep(0.01)
    assert mark.exists(), "die Rechnung hat nie begonnen"
    helper = kernel_process.processes()[0]
    asked = time.monotonic()
    signal.cancel()
    worker.join(30.0)

    assert "cancelled" in outcome
    assert outcome["cancelled"] - asked < 2.0, "abgebrochen wird binnen Sekunden"
    helper.join(10.0)
    assert not helper.is_alive(), "der rechnende Hilfsprozess ist beendet, nicht zurückgelassen"
    assert kernel_process.processes() == []


def test_cancelling_a_real_kernel_call_in_the_helper(offloaded: None) -> None:
    """Dasselbe am echten Hilfsprozess, mitten in ``simplify``.

    Die Bisektion über eine Kugel mit 327 680 Dreiecken rechnet 32
    ``simplify``-Läufe (gemessen 0,15 bis 0,3 s je Lauf an 327 680 Dreiecken,
    ``schwelle.py``) — abgebrochen wird eine Sekunde nach dem Start der
    Rechnung im schon bereiten Hilfsprozess, also mitten darin. Der Prozess
    endet, der Faden kehrt zurück.
    """
    sphere = MeshData.of(trimesh.creation.icosphere(subdivisions=7, radius=20.0))
    arrays = mesh_input(sphere)
    values = {"target": 5000, "limit": 5.0, "steps": 32, "resolution": 1e-12}
    signal = CancelSignal()
    outcome: dict[str, Any] = {}
    # Bereit, bevor die Uhr läuft: Abgebrochen wird in der Rechnung, nicht im Start.
    assert kernel_process.warm_up()

    def compute() -> None:
        try:
            outcome["result"] = kernel_process.run(
                "simplify_search", arrays, values, weight=1, cancelled=signal
            )
        except OperationCancelled:
            outcome["cancelled"] = True

    helper = kernel_process.processes()[0]
    worker = threading.Thread(target=compute)
    worker.start()
    time.sleep(1.0)
    signal.cancel()
    worker.join(30.0)

    assert outcome == {"cancelled": True}, "die Bisektion lief noch, als abgebrochen wurde"
    helper.join(10.0)
    assert not helper.is_alive()


# --- Was nicht hinein- oder herauskommt (Durchsicht RM-212, B2) ---------------------------


def _memory_refusal() -> OSError:
    """Wie das Betriebssystem einen gemeinsamen Speicher ablehnt, für den der Speicher nicht reicht.

    Unter Windows ``WinError 1455`` (Zusagegrenze) — gemessen an einem Speicher
    über der Grenze, als ``OSError`` und nicht als ``MemoryError``.
    """
    if sys.platform == "win32":
        return OSError(0, "Die Auslagerungsdatei ist zu klein.", None, 1455)
    return OSError(errno.ENOMEM, "Cannot allocate memory")


def _refusing(creating: OSError | None = None, opening: OSError | None = None) -> Any:
    """Ein ``SharedMemory``, das Anlegen oder Öffnen mit dem genannten Fehler ablehnt."""
    real = shared_memory.SharedMemory

    def made(name: str | None = None, create: bool = False, size: int = 0, **rest: Any) -> Any:
        problem = creating if create else opening
        if problem is not None:
            raise problem
        return real(name=name, create=create, size=size, **rest)

    return made


def _cannot_open_the_input(connection: Any) -> None:
    """Ein Hilfsprozess, dem das Betriebssystem den Speicher des Elternprozesses verweigert."""
    kernel_jobs.shared_memory.SharedMemory = _refusing(
        opening=PermissionError(13, "Zugriff verweigert")
    )
    kernel_jobs.serve(connection)


def _cannot_map_the_input(connection: Any) -> None:
    """Ein Hilfsprozess, dem für den Speicher des Elternprozesses der Speicher fehlt."""
    kernel_jobs.shared_memory.SharedMemory = _refusing(opening=_memory_refusal())
    kernel_jobs.serve(connection)


def _no_room_for_the_result(connection: Any) -> None:
    """Ein Hilfsprozess, dem das Betriebssystem den Speicher für Ergebnisse verweigert."""
    kernel_jobs.shared_memory.SharedMemory = _refusing(creating=_memory_refusal())
    kernel_jobs.serve(connection)


def _cannot_make_the_result(connection: Any) -> None:
    """Ein Hilfsprozess, der für Ergebnisse keinen Speicher anlegen kann, aus anderem Grund."""
    kernel_jobs.shared_memory.SharedMemory = _refusing(
        creating=OSError(errno.EMFILE, "Too many open files")
    )
    kernel_jobs.serve(connection)


def _closes_its_end(connection: Any) -> None:
    """Ein Hilfsprozess, der bereit meldet und seine Leitung schließt, ohne zu enden.

    Das ist ein untätiger Hilfsprozess, der zwischen dem Blick auf ``alive``
    und dem Senden der Rechnung stirbt: Der Elternprozess sieht ihn leben und
    schreibt in eine geschlossene Leitung.
    """
    connection.send(("ready", os.getpid()))
    connection.close()
    time.sleep(600.0)


def test_a_shared_memory_this_process_cannot_make_is_computed_here(
    offloaded: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Lässt sich der Speicher für die Rechnung nicht anlegen, rechnet sie hier.

    Bis dahin kam ein roher ``OSError`` beim Kunden an.

    Der Grund bleibt (ein Speicher, den das System nicht anlegt), die Sitzung
    rechnet danach ohne Hilfsprozess.
    """
    arrays, values = _small_job()
    expected = kernel_jobs.simplify_closed(arrays, dict(values), lambda: None)
    assert kernel_process.warm_up()
    monkeypatch.setattr(
        kernel_jobs.shared_memory,
        "SharedMemory",
        _refusing(creating=OSError(errno.EMFILE, "Too many open files")),
    )

    got = in_a_worker(lambda: kernel_process.run("simplify_closed", arrays, values, weight=1))

    same_bytes(expected[0], got[0])
    counts = kernel_process.statistics()
    assert counts["fallback"] == 1 and counts["helper"] == 0, counts
    assert kernel_process._POOL.disabled, "der Grund bleibt — die Sitzung rechnet ohne ihn"
    assert kernel_process.processes() == []


def test_a_shared_memory_the_system_cannot_commit_is_the_memory_hint(
    offloaded: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Sagt das System den Speicher nicht zu, kommt ``MemoryError`` — und damit der Hinweis.

    Unter Windows ist das ``OSError`` 1455 oder 8; ohne Umsetzung griff
    ``except MemoryError`` in ``uniform`` nie, und der Kunde las „unerwarteter
    Fehler“ mit ``WinError 1455`` statt „Für diese Kantenlänge reicht der
    Arbeitsspeicher nicht“ samt Vorschlag.
    """
    from app.core.errors import ValidationError
    from app.core.geom.mesh_ops import uniform

    plate = welded("plate_holes.stl")
    arrays, values = mesh_input(plate), {"tolerance": 1e-6}
    monkeypatch.setattr(
        kernel_jobs.shared_memory, "SharedMemory", _refusing(creating=_memory_refusal())
    )

    with pytest.raises(MemoryError):
        in_a_worker(lambda: kernel_process.run("simplify_closed", arrays, values, weight=1))
    with pytest.raises(ValidationError) as caught:
        in_a_worker(lambda: uniform(plate, 1.0, 0.01))

    assert caught.value.field == "edge"
    assert "reachable" in caught.value.values, "der Vorschlag mit der doppelten Kantenlänge"


@pytest.mark.skipif(sys.platform != "win32", reason="die Zusagegrenze ist die von Windows")
def test_windows_refuses_an_uncommittable_shared_memory_as_memory_error() -> None:
    """Am echten System: 64 TiB gemeinsamer Speicher über der Zusagegrenze sind ``MemoryError``.

    Angelegt wird nichts — Windows lehnt den Speicher beim Anlegen ab.
    """
    with pytest.raises(MemoryError):
        segment = kernel_jobs._opened(create=True, size=2**46)
        segment.close()
        segment.unlink()


@pytest.mark.parametrize(
    ("serve", "expected"),
    [(_cannot_open_the_input, None), (_cannot_map_the_input, MemoryError)],
    ids=["verweigert", "speicher"],
)
def test_a_helper_that_cannot_open_the_input_does_not_take_the_job(
    offloaded: None,
    monkeypatch: pytest.MonkeyPatch,
    serve: Callable[[Any], None],
    expected: type[BaseException] | None,
) -> None:
    """Kann der Hilfsprozess den Speicher nicht öffnen, rechnet die Rechnung hier.

    Bis dahin kam seine Ausnahme roh beim Kunden an (``PermissionError``).
    Fehlt ihm der Speicher dafür, kommt ``MemoryError`` wie aus dem Prozess.
    """
    monkeypatch.setattr(kernel_process, "_SERVE", serve)
    arrays, values = _small_job()
    expected_bytes = kernel_jobs.simplify_closed(arrays, dict(values), lambda: None)

    if expected is not None:
        with pytest.raises(expected):
            in_a_worker(lambda: kernel_process.run("simplify_closed", arrays, values, weight=1))
        return
    got = in_a_worker(lambda: kernel_process.run("simplify_closed", arrays, values, weight=1))
    same_bytes(expected_bytes[0], got[0])
    assert kernel_process.statistics()["fallback"] == 1
    assert kernel_process._POOL.disabled
    assert kernel_process.processes() == []


def test_a_helper_whose_line_broke_does_not_take_the_job(
    offloaded: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein untätiger Hilfsprozess mit geschlossener Leitung: Die Rechnung rechnet hier.

    Bis dahin kam ein roher ``BrokenPipeError`` beim Kunden an.

    Kein bleibender Grund — die nächste Rechnung startet einen frischen.
    """
    monkeypatch.setattr(kernel_process, "_SERVE", _closes_its_end)
    arrays, values = _small_job()
    expected = kernel_jobs.simplify_closed(arrays, dict(values), lambda: None)
    assert kernel_process.warm_up()
    time.sleep(0.5)

    got = in_a_worker(lambda: kernel_process.run("simplify_closed", arrays, values, weight=1))

    same_bytes(expected[0], got[0])
    assert kernel_process.statistics()["fallback"] == 1
    assert not kernel_process._POOL.disabled, "kein bleibender Grund"
    assert kernel_process.processes() == []


@pytest.mark.parametrize(
    ("serve", "expected"),
    [(_no_room_for_the_result, MemoryError), (_cannot_make_the_result, None)],
    ids=["speicher", "anderes"],
)
def test_a_result_without_room_is_no_lost_helper(
    offloaded: None,
    monkeypatch: pytest.MonkeyPatch,
    serve: Callable[[Any], None],
    expected: type[BaseException] | None,
) -> None:
    """Fehlt im Hilfsprozess der Speicher für das Ergebnis, kommt ``MemoryError`` — er stirbt nicht.

    Bis dahin fiel die Ausnahme aus ``serve``, der Hilfsprozess starb, und der
    Kunde las ``KernelHelperLostError`` statt des Speicherhinweises (im
    Windows-Paket dazu ein Traceback-Fenster von PyInstaller). Aus anderem
    Grund rechnet die Rechnung hier.
    """
    monkeypatch.setattr(kernel_process, "_SERVE", serve)
    arrays, values = _small_job()
    expected_bytes = kernel_jobs.simplify_closed(arrays, dict(values), lambda: None)

    if expected is not None:
        with pytest.raises(expected):
            in_a_worker(lambda: kernel_process.run("simplify_closed", arrays, values, weight=1))
    else:
        got = in_a_worker(lambda: kernel_process.run("simplify_closed", arrays, values, weight=1))
        same_bytes(expected_bytes[0], got[0])
        assert kernel_process.statistics()["fallback"] == 1
    assert kernel_process.statistics()["lost"] == 0


class _Line:
    """Eine Leitung für ``serve`` im selben Prozess: liest aus einer Liste, schreibt in eine."""

    def __init__(self, incoming: list[Any], broken_at: str) -> None:
        self.incoming = incoming
        self.sent: list[tuple[Any, ...]] = []
        self.broken_at = broken_at

    def send(self, message: tuple[Any, ...]) -> None:
        if message[0] == self.broken_at:
            raise BrokenPipeError(32, "Broken pipe")
        self.sent.append(message)

    def recv(self) -> Any:
        if not self.incoming:
            raise EOFError
        return self.incoming.pop(0)


@pytest.mark.parametrize("broken_at", ["ready", "accepted", "done"])
def test_serve_ends_quietly_when_nobody_listens(
    monkeypatch: pytest.MonkeyPatch, broken_at: str
) -> None:
    """Hört der Elternprozess nicht mehr zu, endet ``serve`` still — nichts fällt heraus.

    Eine Ausnahme aus ``serve`` schriebe ``multiprocessing`` nach
    ``sys.stderr``, und das ist im Windows-Fensterpaket ``None``: PyInstaller
    zeigte dann einen Traceback in einem eigenen Fenster.
    """
    monkeypatch.setattr(kernel_jobs, "_yield_to_the_window", lambda: None)
    arrays, values = _small_job()
    segment, layout = kernel_jobs.pack(arrays)
    assert segment is not None
    try:
        line = _Line([("job", "simplify_closed", segment.name, layout, values)], broken_at)
        kernel_jobs.serve(line)
    finally:
        segment.close()
        segment.unlink()
    assert all(message[0] != broken_at for message in line.sent)


# --- Die Boolesche Kette und ein verlorener Hilfsprozess (Durchsicht RM-212, B3) ----------


def _dies_in_booleans(connection: Any) -> None:
    """Ein Hilfsprozess, der jede Boolesche Rechnung annimmt und darin stirbt — wie am Speicher.

    Die übrigen Rechnungen (der Zusammenhang vor der Kette) rechnet er: Die
    Kette selbst soll den Tod sehen, nicht ein Aufruf davor.
    """

    def dies(arrays: Any, values: Any, check: Any) -> Any:
        os._exit(3)

    kernel_jobs.JOBS["boolean"] = dies
    kernel_jobs.serve(connection)


def test_the_boolean_chain_stops_at_a_lost_helper(
    offloaded: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Stirbt der Hilfsprozess in einer Stufe, hält der Schritt mit dieser Meldung an.

    Bis dahin nahm die Kette die nächste Stufe: drei Hilfsprozesse gestartet
    und verloren, das Ergebnis still aus der Voxelstufe — in der Vorschau
    (zwei Stufen) der Rat, das Modell sei offen und gehöre repariert.
    """
    from app.core.geom.boolean import boolean

    monkeypatch.setattr(kernel_process, "_SERVE", _dies_in_booleans)
    plate = welded("plate_holes.stl")
    tool = _cylinder_through(plate)

    with pytest.raises(kernel_process.KernelHelperLostError):
        in_a_worker(lambda: boolean("difference", [plate, tool]))

    counts = kernel_process.statistics()
    assert counts["lost"] == 1, counts
    assert counts.get("helper:boolean", 0) == 0, counts


def test_a_lost_helper_is_no_answer_about_shared_volume(
    offloaded: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein gestorbener Hilfsprozess heißt nicht „nichts gemeinsam“.

    Eine Passung hieße sonst still frei.
    """
    from app.core.geom.boolean import shared_volume

    monkeypatch.setattr(kernel_process, "_SERVE", _dies_in_booleans)
    plate = welded("plate_holes.stl")
    tool = _cylinder_through(plate)

    with pytest.raises(kernel_process.KernelHelperLostError):
        in_a_worker(lambda: shared_volume(plate.raw, tool.raw))


def test_tidying_a_union_does_not_hide_a_lost_helper(
    offloaded: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Das Aufräumen nach einer Vereinigung reicht einen gestorbenen Hilfsprozess weiter."""
    from app.core.geom.boolean import boolean
    from app.core.geom.prepare_ops import _without_scars

    plate = welded("plate_holes.stl")
    joined = boolean("union", [plate, _cylinder_through(plate)])
    monkeypatch.setattr(kernel_process, "_SERVE", _dies_mid_job)

    with pytest.raises(kernel_process.KernelHelperLostError):
        in_a_worker(lambda: _without_scars(joined))


# --- Keine Waisen ------------------------------------------------------------------------


def test_shutdown_leaves_no_helper_behind(offloaded: None) -> None:
    """``shutdown`` (am Ende der Anwendung an ``aboutToQuit``) beendet untätige und rechnende."""
    arrays, values = _small_job()
    in_a_worker(lambda: kernel_process.run("simplify_closed", arrays, values, weight=1))
    assert kernel_process.warm_up(), "ein bereiter Hilfsprozess wartet"
    helpers = kernel_process.processes()
    assert helpers

    assert kernel_process.shutdown() == len(helpers)

    for helper in helpers:
        helper.join(10.0)
        assert not helper.is_alive()
    assert kernel_process.processes() == []


def test_shutdown_lets_an_idle_helper_end_by_itself(
    offloaded: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein untätiger Hilfsprozess endet beim ``shutdown`` selbst, auf dem gewöhnlichen Weg.

    Hart beendet liefe sein ``atexit`` nicht — im Paket blieb dann der Ordner
    des Laufzeithakens für matplotlib liegen (Durchsicht RM-212, B4). Die Frist
    ist hier weit gesetzt: Geprüft wird, dass er selbst endet, nicht wie
    schnell unter der Last der Suite.
    """
    monkeypatch.setattr(kernel_process, "GRACEFUL_SECONDS", 30.0)
    assert kernel_process.warm_up()
    helper = kernel_process.processes()[0]

    kernel_process.shutdown()

    assert helper.exitcode == 0, f"beendet statt selbst geendet: {helper.exitcode}"


def _frozen_with_a_temp_folder(connection: Any) -> None:
    """Ein Hilfsprozess wie im Paket: ``sys.frozen`` und der Ordner des Laufzeithakens.

    ``pyi_rth_mplconfig`` legt jedem Prozess des Pakets einen leeren Ordner im
    Temp-Verzeichnis an und setzt ``MPLCONFIGDIR`` darauf.
    """
    sys.frozen = True  # type: ignore[attr-defined]
    folder = tempfile.mkdtemp()
    os.environ["MPLCONFIGDIR"] = folder
    Path(os.environ["KERNEL_TEST_MARK"]).write_text(folder, encoding="utf-8")
    kernel_jobs.serve(connection)


def test_a_frozen_helper_leaves_no_temp_folder(
    offloaded: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Im Paket räumt der Hilfsprozess den Ordner des Laufzeithakens gleich beim Start weg.

    Am gebauten ``Solidon3D.exe``: drei Starts, drei Ordner, alle liegen
    geblieben — Abbrechen und ``shutdown`` beenden einen Hilfsprozess hart,
    und ``atexit`` räumt dann nichts mehr (Durchsicht RM-212, B4).
    """
    mark = tmp_path / "ordner"
    monkeypatch.setenv("KERNEL_TEST_MARK", str(mark))
    monkeypatch.setattr(kernel_process, "_SERVE", _frozen_with_a_temp_folder)

    assert kernel_process.warm_up()

    folder = Path(mark.read_text(encoding="utf-8"))
    try:
        assert not folder.exists(), "der Ordner des Laufzeithakens liegt noch"
    finally:
        shutil.rmtree(folder, ignore_errors=True)


def _alive(pid: int) -> bool:
    """Ob ein Prozess noch lebt — ohne ihm etwas zu tun (unter Windows beendete ``os.kill`` ihn)."""
    if os.name == "nt":
        import ctypes

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = ctypes.c_void_p
        handle = kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            kernel32.GetExitCodeProcess(ctypes.c_void_p(handle), ctypes.byref(code))
            return code.value == 259
        finally:
            kernel32.CloseHandle(ctypes.c_void_p(handle))
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    return True


_PARENT = textwrap.dedent(
    """
    import sys, threading
    sys.path.insert(0, {root!r})
    from app.core.geom import kernel_process

    def main():
        assert kernel_process.warm_up()
        print(kernel_process.processes()[0].pid, flush=True)
        threading.Event().wait()

    if __name__ == "__main__":
        main()
    """
)


def test_a_helper_ends_with_a_parent_that_is_killed(tmp_path: Path) -> None:
    """Stirbt Solidon hart (Absturz, Task-Manager), endet sein Hilfsprozess mit.

    Unter Windows überlebt ein Kind seinen Elternprozess; das Jobobjekt
    (``process.bind_helper``) beendet es mit dem letzten Griff. Unter POSIX
    endet ein untätiger Hilfsprozess an der geschlossenen Leitung.
    """
    script = tmp_path / "eltern.py"
    script.write_text(_PARENT.format(root=str(ROOT)), encoding="utf-8")
    parent = subprocess.Popen(
        [sys.executable, str(script)], stdout=subprocess.PIPE, text=True, cwd=str(tmp_path)
    )
    try:
        assert parent.stdout is not None
        line = parent.stdout.readline()
        helper = int(line.strip())
        assert _alive(helper)
    finally:
        parent.kill()
        parent.wait(30.0)
        if parent.stdout is not None:
            parent.stdout.close()
    deadline = time.monotonic() + 20.0
    while _alive(helper) and time.monotonic() < deadline:
        time.sleep(0.05)
    assert not _alive(helper), "der Hilfsprozess ist mit seinem Elternprozess gegangen"


# --- Was der Hilfsprozess mitträgt -------------------------------------------------------


def _notes_its_environment(connection: Any) -> None:
    """Ein Hilfsprozess, der vor der Arbeit notiert, wie viele BLAS-Fäden er bekam."""
    Path(os.environ["KERNEL_TEST_MARK"]).write_text(
        os.environ.get("OPENBLAS_NUM_THREADS", "-"), encoding="utf-8"
    )
    kernel_jobs.serve(connection)


@pytest.mark.parametrize("ours", [None, "7"], ids=["ohne", "gesetzt"])
def test_a_helper_starts_with_one_blas_thread_and_ours_stay(
    ours: str | None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """OpenBLAS legt beim Laden je Rechenkern einen Puffer an — der Hilfsprozess bekommt einen.

    Gemessen 758 MB privater Speicher je Bibliothek an 32 Kernen, mit einem
    Faden 19 MB (``HELPER_ENVIRONMENT``). Die Anwendung behält ihren Wert,
    auch einen gesetzten.
    """
    mark = tmp_path / "umgebung"
    monkeypatch.setenv("KERNEL_TEST_MARK", str(mark))
    if ours is None:
        monkeypatch.delenv("OPENBLAS_NUM_THREADS", raising=False)
    else:
        monkeypatch.setenv("OPENBLAS_NUM_THREADS", ours)
    monkeypatch.setattr(kernel_process, "_SERVE", _notes_its_environment)

    assert kernel_process.warm_up()

    assert mark.read_text(encoding="utf-8") == "1"
    assert os.environ.get("OPENBLAS_NUM_THREADS") == ours


#: Was ``numpy`` über BLAS oder LAPACK rechnet. Mit der Zahl der Fäden ändert sich
#: dort die Reihenfolge einer Summe und damit das letzte Bit.
_BLAS_CALLS = frozenset(
    {
        "cholesky",
        "cond",
        "det",
        "dot",
        "eig",
        "eigh",
        "eigvals",
        "eigvalsh",
        "einsum",
        "inner",
        "inv",
        "lstsq",
        "matmul",
        "matrix_power",
        "matrix_rank",
        "multi_dot",
        "pinv",
        "qr",
        "slogdet",
        "solve",
        "svd",
        "tensordot",
        "tensorinv",
        "tensorsolve",
        "vdot",
    }
)


def test_the_jobs_call_no_blas() -> None:
    """Eine Rechnung in ``kernel_jobs`` ruft kein BLAS.

    Der Hilfsprozess rechnet mit einem BLAS-Faden, die Anwendung mit einem je
    Kern (``HELPER_ENVIRONMENT``). Über BLAS hinge ein Ergebnis an der
    Fadenzahl, und dieselbe Rechnung gäbe hier und dort verschiedene Bytes.
    Eine Norm entlang einer Achse rechnet ``numpy`` als Summe ohne BLAS, ohne
    ``axis`` über ``dot``.
    """
    source = (ROOT / "app" / "core" / "geom" / "kernel_jobs.py").read_text(encoding="utf-8")
    found = []
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, (ast.BinOp, ast.AugAssign)) and isinstance(node.op, ast.MatMult):
            found.append(f"@ in Zeile {node.lineno}")
        if not isinstance(node, ast.Call):
            continue
        function = node.func
        name = (
            function.attr
            if isinstance(function, ast.Attribute)
            else function.id
            if isinstance(function, ast.Name)
            else ""
        )
        if name in _BLAS_CALLS:
            found.append(f"{name} in Zeile {node.lineno}")
        if name == "norm" and not any(keyword.arg == "axis" for keyword in node.keywords):
            found.append(f"norm ohne axis in Zeile {node.lineno}")
    assert found == []


# --- Eingefrorenes Paket -----------------------------------------------------------------


def test_the_entry_point_hands_a_helper_start_to_freeze_support_first() -> None:
    """Im Paket startet ``sys.executable`` die Anwendung selbst — als Hilfsprozess.

    ``multiprocessing.freeze_support()`` muss das erkennen, bevor
    Absturzprotokoll, Qt oder ein Fenster entstehen: der erste Aufruf im
    ``__main__``-Block von ``app/ui/app.py``, dem Einstieg der PyInstaller-Spec.
    """
    source = (ROOT / "app" / "ui" / "app.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    guards = [
        node
        for node in tree.body
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "__name__"
    ]
    first_guard = guards[0]
    calls = [
        statement.value.func
        for statement in first_guard.body
        if isinstance(statement, ast.Expr) and isinstance(statement.value, ast.Call)
    ]
    assert isinstance(calls[0], ast.Name) and calls[0].id == "freeze_support"
    before = tree.body[: tree.body.index(first_guard)]
    imported = {
        alias.name if isinstance(node, ast.Import) else (node.module or "")
        for node in before
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in node.names
    }
    assert not any("PySide6" in name for name in imported), "kein Qt vor freeze_support"
    spec = (ROOT / "packaging" / "solidon3d.spec").read_text(encoding="utf-8")
    assert '"app" / "ui" / "app.py"' in spec, "die Spec startet genau diese Datei"
    start = spec.index("excludes=[")
    excluded = spec[start : spec.index("]", start)]
    assert '"multiprocessing"' not in excluded, "der Hilfsprozess braucht multiprocessing im Paket"


def test_the_helper_side_loads_nothing_but_numpy_and_the_kernel() -> None:
    """Der Hilfsprozess lädt ``kernel_jobs`` und sonst kein Modul des Kerns — ein kurzer Start.

    Im Paket läuft vor ``freeze_support`` nur der Kopf von ``app/ui/app.py``;
    was ``kernel_jobs`` nachzieht, verlängert jeden Start des Hilfsprozesses.
    """
    probe = (
        "import sys; import app.core.geom.kernel_jobs; "
        "print(sorted(n for n in sys.modules if n.startswith('app.')))"
    )
    loaded = subprocess.run(
        [sys.executable, "-c", probe],
        capture_output=True,
        text=True,
        check=True,
        cwd=str(ROOT),
    ).stdout
    assert loaded.strip() == "['app.core', 'app.core.geom', 'app.core.geom.kernel_jobs']"


# --- Der Anschluss: die Anwendung tut es -------------------------------------------------


def _ellipsoid_session() -> tuple[Any, str, MeshData]:
    """Eine Sitzung mit dem Ellipsoid aus dem Korpus: 1 280 Dreiecke, geschlossen.

    Der Import startet einen Auswertungsarbeiter (``Session.apply``), und der
    rechnet beim Ladeweg zweimal (Bild, dann Erkennung). Er ist fertig, bevor
    ein Test rechnet: Begann sein zweiter Lauf erst nach dem nächsten Schritt
    des Tests, rechnete er ihn mit — und kam er zuerst an, fand der Test das
    Ergebnis im Cache
    (``konzepte/nachweise-release-0.5.1/sonden/hilfsprozess/zweimal_verfeinert.py``). Die
    Frist von ``wait_all`` (2 s) reichte dafür unter Last nicht.
    """
    from app.ui.session import Session

    session = Session()
    assert session.import_model(MESHES / "near_sphere_ellipsoid.stl", unit="mm")
    session._leash.wait_all(timeout_ms=120_000)
    assert not any(worker.isRunning() for worker in session._leash.pending())
    result = session.evaluate_now()
    body, entry = next(iter(result.scene.objects.items()))
    return session, body, entry.mesh


def test_the_coarse_preview_reduces_and_drills_in_the_helper(
    offloaded: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die grobe Vorschau, wie ihr Arbeiter sie rechnet, verkleinert und bohrt im Hilfsprozess.

    ``Session._preview_outcome`` ist die Arbeit des ``_PreviewWorker`` — hier in
    einem Nebenfaden gerufen wie dort. Die Schwellen sind so gesetzt, dass das
    Ellipsoid aus dem Korpus die grobe Stufe nimmt (RM-212: die erste grobe
    Vorschau stand sonst je Körper im Hauptfaden). Dieselbe Vorschau im
    Hauptfaden rechnet im Prozess, und beide tragen dasselbe ab.
    """
    from app.core.geom.mesh_ops import DECIMATE_FLOOR
    from app.core.scene import OperationDraft
    from app.ui import session as session_module

    session, body, _mesh = _ellipsoid_session()
    monkeypatch.setattr(session_module, "COARSE_PREVIEW_ABOVE", DECIMATE_FLOOR)
    monkeypatch.setattr(session_module, "COARSE_PREVIEW_TARGET", DECIMATE_FLOOR)
    draft = OperationDraft(
        op="drill_hole",
        params={"diameter": 5.0, "x": 0.0, "y": 0.0, "z": 20.0, "depth": 0.0},
        inputs=(body,),
    )

    def preview() -> tuple[Any, list[int]]:
        seen: list[int] = []
        _scene, difference, _reason = session._preview_outcome(
            [draft], coarsened=seen.append, detect_features=False
        )
        return difference, seen

    there, seen_there = in_a_worker(preview)
    counts = kernel_process.statistics()
    kernel_process.shutdown()
    session.cancel_preview()
    here, seen_here = preview()

    assert seen_there and seen_here, "grob gerechnet"
    assert counts["helper:display_simplify"] >= 1, counts
    assert counts["helper:boolean"] >= 1, counts
    assert there is not None and here is not None
    assert there.removed_volume == here.removed_volume


def test_applying_a_large_refinement_refines_in_the_helper(
    offloaded: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Das Übernehmen von *Kanten verfeinern*, wie der Auswertungsarbeiter es rechnet.

    ``Session.run_evaluation`` ist die Arbeit des ``_EvaluationWorker``. Am
    Spielwürfel (0,05 mm, 5,8 Mio. Dreiecke) stand der Hauptfaden dabei 15,0
    und 22,7 s in ``refine_to_length`` (RM-212); hier teilt der Hilfsprozess,
    und das Netz ist dasselbe wie im Prozess geteilt.

    Gefragt wird der Faden dieser Auswertung, nicht die Zählung des Prozesses:
    Die zählt jede Rechnung jedes Nebenfadens, der gerade läuft.
    """
    from app.core.geom.mesh_ops import remesh
    from app.core.scene import OperationDraft

    asked: list[tuple[str, bool]] = []
    original = kernel_process.run

    def noted(job: str, arrays: Any, values: Any, *, weight: int, cancelled: Any = None) -> Any:
        if job == "refine_conforming":
            asked.append((threading.current_thread().name, kernel_process.offloaded(weight)))
        return original(job, arrays, values, weight=weight, cancelled=cancelled)

    monkeypatch.setattr(kernel_process, "run", noted)
    session, body, mesh = _ellipsoid_session()
    session.history.apply(
        "Verfeinern", [OperationDraft(op="remesh_mesh", params={"edge": 0.8}, inputs=(body,))]
    )

    result = in_a_worker(session.run_evaluation)

    assert result.stopped_at is None
    counts = kernel_process.statistics()
    assert ("kernel-test", True) in asked, asked
    assert counts["helper:refine_conforming"] >= 1, counts
    assert counts["fallback"] == 0, counts
    refined = next(iter(result.scene.objects.values())).mesh
    expected = remesh(mesh, 0.8)
    same_bytes(
        {"vertices": np.asarray(expected.raw.vertices), "faces": np.asarray(expected.raw.faces)},
        {"vertices": np.asarray(refined.raw.vertices), "faces": np.asarray(refined.raw.faces)},
    )


def test_the_workers_of_the_window_use_the_helper(
    qt_app: object, offloaded: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dasselbe über die echten Arbeiter: ``preview_async`` und die Auswertung nach dem Übernehmen.

    Ein Fenstertest (``qt_app``), gefahren beim Release. Belegt, dass die
    ``QThread``-Arbeiter der Sitzung — nicht nur ein Nebenfaden der Suite —
    den Kern im Hilfsprozess rechnen lassen.
    """
    from app.core.geom.mesh_ops import DECIMATE_FLOOR
    from app.core.scene import OperationDraft
    from app.ui import session as session_module

    session, body, _mesh = _ellipsoid_session()
    monkeypatch.setattr(session_module, "COARSE_PREVIEW_ABOVE", DECIMATE_FLOOR)
    monkeypatch.setattr(session_module, "COARSE_PREVIEW_TARGET", DECIMATE_FLOOR)
    collected: list[object] = []
    coarsened: list[int] = []
    try:
        # ``coarse`` wie der Operationsdialog (``MainWindow``): Erst dieser
        # Rückruf schaltet die grobe Stufe frei (``_preview_outcome``). Ohne
        # ihn rechnete die Vorschau genau, und verkleinert wurde nichts, das
        # der Hilfsprozess hätte zählen können.
        session.preview_async(
            collected.append,
            [
                OperationDraft(
                    op="drill_hole",
                    params={"diameter": 5.0, "x": 0.0, "y": 0.0, "z": 20.0, "depth": 0.0},
                    inputs=(body,),
                )
            ],
            coarse=coarsened.append,
        )
        assert session.wait_for_idle(60_000)
        assert collected and collected[-1] is not None
        assert coarsened, "die Vorschau nahm die grobe Stufe"
        assert kernel_process.statistics()["helper:display_simplify"] >= 1

        # ``Session.apply`` wie das Übernehmen im Fenster: Es trägt den Schritt
        # ein **und** startet den Auswertungsarbeiter. ``history.apply`` allein
        # ändert nur den Stapel, und gerechnet würde nichts.
        before = session.last_result
        session.apply(
            "Verfeinern", [OperationDraft(op="remesh_mesh", params={"edge": 0.8}, inputs=(body,))]
        )
        assert session.wait_for_idle(60_000)
        assert session.last_result is not before, "die Auswertung nach dem Übernehmen lief"
        assert session.last_result is not None and session.last_result.stopped_at is None
        assert kernel_process.statistics()["helper:refine_conforming"] == 1
    finally:
        session.cancel_preview()
        session.wait_for_idle(30_000)
