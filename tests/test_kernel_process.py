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
import subprocess
import sys
import textwrap
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import suppress
from multiprocessing import shared_memory
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import trimesh

from app.core.errors import InternalError, OperationCancelled
from app.core.geom import kernel_jobs, kernel_process
from app.core.geom.mesh import MeshData
from app.core.scene.cancel import CancelSignal
from app.i18n.catalog import available_languages

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

    Hart beendet liefe sein ``atexit`` nicht, und was er aufräumt, bliebe
    liegen (Durchsicht RM-212, B4). Die Frist
    ist hier weit gesetzt: Geprüft wird, dass er selbst endet, nicht wie
    schnell unter der Last der Suite.
    """
    monkeypatch.setattr(kernel_process, "GRACEFUL_SECONDS", 30.0)
    assert kernel_process.warm_up()
    helper = kernel_process.processes()[0]

    kernel_process.shutdown()

    assert helper.exitcode == 0, f"beendet statt selbst geendet: {helper.exitcode}"


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


# --- Der Pooldeckel gilt auch während Start und Ende (RM-298) -----------------------------


class _PoolFullError(Exception):
    """Die Attrappe meldet Warten, ohne einen Testfaden anhalten zu müssen."""


class _ObservedPoolCondition(threading.Condition):
    def wait(self, timeout: float | None = None) -> bool:
        raise _PoolFullError


class _PoolHelper:
    """Ein sichtbarer Prozessbestand ohne Prozesse oder fremde Handles."""

    def __init__(self) -> None:
        self.ready = True
        self.alive = True
        self.process = self
        self.pid = 42

    def stop(self, *, graceful: bool = False) -> None:
        self.alive = False


@pytest.mark.parametrize("warm", (False, True), ids=("take", "warm-up"))
def test_pool_pending_starts_use_a_slot(monkeypatch: pytest.MonkeyPatch, warm: bool) -> None:
    """Offene Konstruktoren belegen ihren Platz schon vor dem Eintragen."""
    pool = kernel_process._Pool()
    pool._lock = _ObservedPoolCondition()
    made: list[_PoolHelper] = []

    class StartingHelper(_PoolHelper):
        def __init__(self) -> None:
            super().__init__()
            made.append(self)
            if len(made) < 6:
                with suppress(_PoolFullError):
                    pool._reserve(None)

    monkeypatch.setattr(kernel_process, "_Helper", StartingHelper)
    try:
        if warm:
            monkeypatch.setattr(kernel_process, "_POOL", pool)
            assert kernel_process.warm_up()
        else:
            assert pool.take(None) is not None
        assert len(made) == kernel_process.MOST_HELPERS
        assert len(pool.processes()) == kernel_process.MOST_HELPERS
    finally:
        pool.shutdown()
    assert all(not helper.alive for helper in made)


@pytest.mark.parametrize("ending", ("discard", "give_back", "shutdown"))
def test_pool_ending_helpers_keep_their_slot(monkeypatch: pytest.MonkeyPatch, ending: str) -> None:
    """Erst nach dem wirklichen Ende darf ein neuer Prozess denselben Platz nutzen."""
    pool = kernel_process._Pool()
    pool._lock = _ObservedPoolCondition()
    made: list[_PoolHelper] = []
    peak = 0

    class CountedHelper(_PoolHelper):
        def __init__(self) -> None:
            nonlocal peak
            super().__init__()
            made.append(self)
            peak = max(peak, sum(helper.alive for helper in made))

    monkeypatch.setattr(kernel_process, "_Helper", CountedHelper)
    for _index in range(kernel_process.MOST_HELPERS):
        assert pool.take(None) is not None
    victim = made[1]

    def stop_with_a_competing_request(*, graceful: bool = False) -> None:
        for _index in range(kernel_process.MOST_HELPERS):
            try:
                pool.take(None)
            except _PoolFullError:
                break
        victim.alive = False

    monkeypatch.setattr(victim, "stop", stop_with_a_competing_request)
    try:
        if ending == "give_back":
            pool.give_back(made[0])
            pool.give_back(victim)
        elif ending == "discard":
            pool.discard(victim)
        else:
            pool.shutdown()
        assert peak <= kernel_process.MOST_HELPERS
    finally:
        pool.shutdown()
    assert all(not helper.alive for helper in made)


@pytest.mark.parametrize("unexpected", (False, True), ids=("start-error", "unexpected-error"))
def test_pool_failed_starts_release_the_reservation(
    monkeypatch: pytest.MonkeyPatch, unexpected: bool
) -> None:
    """Auch ein weitergeworfener Fehler hinterlässt keinen reservierten Startplatz."""
    pool = kernel_process._Pool()

    def failed_start() -> None:
        if unexpected:
            raise LookupError("Startattrappe")
        raise OSError("Startattrappe")

    monkeypatch.setattr(kernel_process, "_Helper", failed_start)
    if unexpected:
        with pytest.raises(LookupError, match="Startattrappe"):
            pool.take(None)
    else:
        assert pool.take(None) is None
        assert pool.disabled
    assert getattr(pool, "_starting", 0) == 0
    assert pool.processes() == []
    pool.shutdown()
    monkeypatch.setattr(kernel_process, "_Helper", _PoolHelper)
    try:
        assert pool.take(None) is not None
    finally:
        pool.shutdown()


@pytest.mark.parametrize("after_start", (False, True), ids=("before-child", "after-child"))
def test_pool_constructor_failure_closes_the_child_and_both_pipes(
    monkeypatch: pytest.MonkeyPatch, after_start: bool
) -> None:
    """Ein schon gestartetes Kind überlebt keinen Fehler seines Konstruktors."""
    from contextlib import nullcontext
    from types import SimpleNamespace

    class PipeEnd:
        def __init__(self, peer: bool = False) -> None:
            self.closed = False
            self.peer = peer
            self.calls = 0

        def close(self) -> None:
            self.calls += 1
            if self.peer and after_start and self.calls == 1:
                raise OSError("Leitungsattrappe")
            self.closed = True

    class Child:
        def __init__(self) -> None:
            self.pid: int | None = None
            self.alive = False
            self.joined = False

        def start(self) -> None:
            if not after_start:
                raise OSError("Startattrappe")
            self.pid = 42
            self.alive = True

        def is_alive(self) -> bool:
            return self.alive

        def kill(self) -> None:
            self.alive = False

        def join(self, timeout: float | None = None) -> None:
            self.joined = True

    mine, peer, child = PipeEnd(), PipeEnd(peer=True), Child()
    context = SimpleNamespace(Pipe=lambda **_args: (mine, peer), Process=lambda **_args: child)
    monkeypatch.setattr(kernel_process, "_CONTEXT", context)
    monkeypatch.setattr(kernel_process, "_helper_environment", nullcontext)
    monkeypatch.setattr(kernel_process.process_boundary, "bind_helper", lambda _child: None)
    monkeypatch.setattr(kernel_process.process_boundary, "release_helper", lambda _child: None)
    with pytest.raises(OSError, match="Leitungsattrappe" if after_start else "Startattrappe"):
        kernel_process._Helper()
    assert mine.closed and peer.closed
    assert not child.alive
    assert child.joined is after_start


def test_pool_shutdown_collects_a_still_starting_helper(monkeypatch: pytest.MonkeyPatch) -> None:
    """Shutdown wartet auf den offenen Start; dessen Rückgabe wird nicht wieder aufgenommen."""
    started = threading.Event()
    release = threading.Event()
    closing = threading.Event()
    made: list[_PoolHelper] = []
    outcomes: dict[str, Any] = {}

    class ClosingCondition(threading.Condition):
        def __enter__(self) -> Any:
            entered = super().__enter__()
            if threading.current_thread().name == "pool-shutdown":
                closing.set()
            return entered

    pool = kernel_process._Pool()
    pool._lock = ClosingCondition()

    class StartingHelper(_PoolHelper):
        def __init__(self) -> None:
            super().__init__()
            made.append(self)
            started.set()
            assert release.wait(30.0), "Der Test gibt den angehaltenen Konstruktor frei."

    def take() -> None:
        try:
            outcomes["taken"] = pool.take(None)
        except BaseException as problem:
            outcomes["take_error"] = problem

    def close() -> None:
        try:
            outcomes["closed"] = pool.shutdown()
        except BaseException as problem:
            outcomes["close_error"] = problem

    monkeypatch.setattr(kernel_process, "_Helper", StartingHelper)
    creator = threading.Thread(target=take, name="pool-start", daemon=True)
    shutdown = threading.Thread(target=close, name="pool-shutdown", daemon=True)
    creator.start()
    try:
        assert started.wait(30.0), "Der Test beobachtet den begonnenen Konstruktor."
        shutdown.start()
        assert closing.wait(30.0), "Shutdown hält das Poolschloss vor dem Weiterstart."
        release.set()
        creator.join(30.0)
        shutdown.join(30.0)
        assert not creator.is_alive() and not shutdown.is_alive()
        assert "take_error" not in outcomes and "close_error" not in outcomes, outcomes
        assert outcomes["taken"] is None
        assert outcomes["closed"] == 1
        assert not made[0].alive
        assert pool.processes() == []
        pool.give_back(made[0])
        assert pool.processes() == [], "Die alte Rückgabe gehört nicht zum neuen Bestand."
        fresh = pool.take(None)
        assert fresh is not None and fresh is not made[0] and fresh.alive
    finally:
        release.set()
        creator.join(30.0)
        if shutdown.ident is not None:
            shutdown.join(30.0)
        if (
            not creator.is_alive()
            and not shutdown.is_alive()
            and not getattr(pool, "_closing", False)
        ):
            pool.shutdown()


def test_pool_shutdown_does_not_reinsert_a_late_return(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ein Arbeiter kann beim Beenden seinen alten Helfer nicht wieder in idle einhängen."""
    pool = kernel_process._Pool()
    monkeypatch.setattr(kernel_process, "_Helper", _PoolHelper)
    helper = pool.take(None)
    assert helper is not None

    def late_return(*, graceful: bool = False) -> None:
        pool.give_back(helper)
        helper.alive = False

    monkeypatch.setattr(helper, "stop", late_return)
    assert pool.shutdown() == 1
    assert pool.processes() == []


def test_pool_closed_wait_is_a_lost_helper_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Das von Shutdown geschlossene Handle meldet einen verlorenen Helfer, keinen OSError."""
    from types import SimpleNamespace

    helper = object.__new__(kernel_process._Helper)
    helper.connection = SimpleNamespace(poll=lambda _timeout: False)
    helper.process = SimpleNamespace(sentinel=object())

    def closed_wait(*_args: Any, **_kwargs: Any) -> None:
        raise OSError("handle is closed")

    monkeypatch.setattr(kernel_process.multiprocessing.connection, "wait", closed_wait)
    with pytest.raises(kernel_process._HelperLostError, match="handle is closed"):
        helper._receive(None, None)


@pytest.mark.parametrize("ending", ("discard", "shutdown"))
def test_pool_failed_stop_keeps_ownership_and_can_be_retried(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, ending: str
) -> None:
    """Eine verweigerte Beendigung verliert weder den Platz noch den Aufräumweg."""
    pool = kernel_process._Pool()
    monkeypatch.setattr(kernel_process, "_Helper", _PoolHelper)
    helper = pool.take(None)
    assert helper is not None
    stops = 0

    def stop_once_refused(*, graceful: bool = False) -> None:
        nonlocal stops
        stops += 1
        if stops == 1:
            raise OSError("Beendigungsattrappe")
        helper.alive = False

    monkeypatch.setattr(helper, "stop", stop_once_refused)
    with pytest.raises(InternalError) as failed:
        if ending == "discard":
            pool.discard(helper)
        else:
            pool.shutdown()
    assert not failed.value.values, "Die technische PID erscheint nicht als Kundenwert."
    assert "kernel helper 42" in caplog.text
    assert pool.processes() == [helper.process]
    assert pool.counts.get("stopped", 0) == 0
    assert pool.disabled and not pool._closing
    assert pool.shutdown() == 1
    assert pool.processes() == []
    assert not pool.disabled and not pool._closing
    assert stops == 2


def test_pool_join_returning_with_a_live_child_does_not_free_its_slot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """kill und join sind noch kein Nachweis, dass das Kind wirklich beendet ist."""
    from types import SimpleNamespace

    class Child:
        pid = 42

        def __init__(self) -> None:
            self.alive = True

        def is_alive(self) -> bool:
            return self.alive

        def kill(self) -> None:
            pass

        def join(self, timeout: float | None = None) -> None:
            pass

    helper = object.__new__(kernel_process._Helper)
    helper.process = Child()
    helper.ready = True
    helper.connection = SimpleNamespace(close=lambda: None)
    released: list[Any] = []
    monkeypatch.setattr(kernel_process.process_boundary, "release_helper", released.append)
    pool = kernel_process._Pool()
    pool._helpers.add(helper)
    pool._busy.add(helper)
    with pytest.raises(InternalError):
        pool.discard(helper)
    assert helper.alive and pool.processes() == [helper.process]
    assert pool.counts.get("stopped", 0) == 0
    assert not released, "Das Jobobjekt gehört weiter dem noch lebenden Kind."
    assert pool.take(None) is None
    helper.process.alive = False
    assert pool.shutdown() == 1
    assert pool.processes() == [] and released == [helper.process]


def test_pool_parallel_shutdown_retries_after_a_failed_stop(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Der zweite Schließer wird auch beim Stopfehler des ersten wieder freigegeben."""
    stopping, waiting, release = threading.Event(), threading.Event(), threading.Event()
    outcomes: dict[str, Any] = {}
    stops = 0

    class ClosingCondition(threading.Condition):
        def wait(self, timeout: float | None = None) -> bool:
            waiting.set()
            assert super().wait(30.0), "Der erste Schließer gibt den wartenden zweiten frei."
            return True

    pool = kernel_process._Pool()
    pool._lock = ClosingCondition()
    monkeypatch.setattr(kernel_process, "_Helper", _PoolHelper)
    helper = pool.take(None)
    assert helper is not None

    def stop_once_refused(*, graceful: bool = False) -> None:
        nonlocal stops
        stops += 1
        if stops == 1:
            stopping.set()
            assert release.wait(30.0), "Der Test gibt die erste Beendigung frei."
            raise OSError("Beendigungsattrappe")
        helper.alive = False

    def close(name: str) -> None:
        try:
            outcomes[name] = pool.shutdown()
        except BaseException as problem:
            outcomes[name] = problem

    monkeypatch.setattr(helper, "stop", stop_once_refused)
    first = threading.Thread(target=close, args=("first",), daemon=True)
    second = threading.Thread(target=close, args=("second",), daemon=True)
    first.start()
    try:
        assert stopping.wait(30.0)
        second.start()
        assert waiting.wait(30.0)
        release.set()
        first.join(30.0)
        second.join(30.0)
        assert not first.is_alive() and not second.is_alive()
        assert isinstance(outcomes["first"], InternalError), outcomes
        assert outcomes["second"] == 1, outcomes
        assert pool.processes() == []
        assert not pool.disabled and not pool._closing
        assert stops == 2
    finally:
        release.set()
        with pool._lock:
            pool._closing = False
            pool._lock.notify_all()
        first.join(30.0)
        if second.ident is not None:
            second.join(30.0)


def test_pool_old_refusal_does_not_disable_a_new_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Eine alte dauerhafte Absage trifft keinen inzwischen frisch gestarteten Bestand."""
    pool = kernel_process._Pool()
    paused, release = threading.Event(), threading.Event()
    outcomes: dict[str, Any] = {}

    class RefusingHelper(_PoolHelper):
        def call(self, *_args: Any, **_kwargs: Any) -> None:
            raise kernel_process._HelperRefusedError("Speicherattrappe", lasting=True)

    original_disable = pool.disable

    def paused_disable(why: str, helper: Any = None) -> None:
        paused.set()
        assert release.wait(30.0), "Der Test gibt die alte Absage frei."
        if helper is None:
            original_disable(why)
        else:
            original_disable(why, helper)

    def run() -> None:
        try:
            outcomes["result"] = kernel_process.run("refusal_probe", {}, {}, weight=1)
        except BaseException as problem:
            outcomes["error"] = problem

    monkeypatch.setattr(kernel_process, "_POOL", pool)
    monkeypatch.setattr(kernel_process, "_Helper", RefusingHelper)
    monkeypatch.setattr(kernel_process, "OFFLOAD_ABOVE", 0)
    monkeypatch.setitem(kernel_jobs.JOBS, "refusal_probe", lambda *_args: ({}, {}))
    monkeypatch.setattr(pool, "disable", paused_disable)
    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    try:
        assert paused.wait(30.0), "Die reale run-Absage wartet direkt vor disable."
        old = pool.processes()
        assert len(old) == 1 and old[0].alive
        assert pool.shutdown() == 1
        assert not old[0].alive
        fresh = pool.take(None)
        assert fresh is not None and fresh.alive
        release.set()
        worker.join(30.0)
        assert not worker.is_alive()
        assert "error" not in outcomes, outcomes
        assert outcomes["result"] == ({}, {})
        assert not pool.disabled, "Die Absage stammt vom alten, bereits beendeten Helfer."
    finally:
        release.set()
        worker.join(30.0)
        pool.shutdown()


def test_pool_failed_constructor_cleanup_keeps_the_live_child(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Scheitert nach dem Start auch das Stoppen, bleibt das Kind sichtbar und belegend."""
    from contextlib import nullcontext
    from types import SimpleNamespace

    class Peer:
        def __init__(self) -> None:
            self.closed = 0

        def close(self) -> None:
            self.closed += 1
            if self.closed == 1:
                raise OSError("Leitungsattrappe")

    class Child:
        pid = 42

        def __init__(self) -> None:
            self.alive = False
            self.kills = 0

        def start(self) -> None:
            self.alive = True

        def is_alive(self) -> bool:
            return self.alive

        def kill(self) -> None:
            self.kills += 1
            if self.kills == 1:
                raise OSError("Beendigungsattrappe")
            self.alive = False

        def join(self, timeout: float | None = None) -> None:
            pass

    peer, child = Peer(), Child()
    context = SimpleNamespace(
        Pipe=lambda **_args: (SimpleNamespace(close=lambda: None), peer),
        Process=lambda **_args: child,
    )
    monkeypatch.setattr(kernel_process, "_CONTEXT", context)
    monkeypatch.setattr(kernel_process, "_helper_environment", nullcontext)
    monkeypatch.setattr(kernel_process.process_boundary, "bind_helper", lambda _child: None)
    monkeypatch.setattr(kernel_process.process_boundary, "release_helper", lambda _child: None)
    pool = kernel_process._Pool()
    with pytest.raises(InternalError) as failed:
        pool.take(None)
    assert not failed.value.values, "Die technische PID erscheint nicht als Kundenwert."
    assert "kernel helper 42" in caplog.text
    assert child.alive and pool.processes() == [child]
    assert pool.disabled and pool._starting == 0
    assert pool.shutdown() == 1
    assert not child.alive and pool.processes() == []


@pytest.mark.parametrize("language", available_languages())
def test_pool_stop_error_has_translated_detail_and_an_action(language: str) -> None:
    """Das verweigerte Ende wird in jeder Sprache mit einem tatsächlichen Ausweg gemeldet."""
    from app.core.errors import REPORT_ERROR
    from app.i18n import get_language, set_language
    from app.i18n.catalog import install_language, read_catalog

    previous = get_language()
    install_language(language)
    set_language(language)
    try:
        error = kernel_process.KernelHelperStopError()
        detail = str(error.detail)
        assert REPORT_ERROR in error.suggestions
        assert isinstance(error, kernel_process.NOT_A_KERNEL_FAILURE)
        set_language("de")
        source = str(error.detail)
        if language == "de":
            assert detail == source
        else:
            assert detail == read_catalog(language)[source]
            assert detail != source
    finally:
        set_language(previous)


@pytest.mark.parametrize("phase", ("constructor", "ready"))
@pytest.mark.parametrize("worker_request", (False, True), ids=("main-thread", "worker-thread"))
def test_pool_warmup_stop_error_reaches_the_next_kernel_request(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
    phase: str,
    worker_request: bool,
) -> None:
    """Auch nach dem echten Warmup-Crash meldet run das noch lebende Kind mit einem Ausweg."""
    from app.core.errors import REPORT_ERROR
    from app.ui.app import _ImportWarmup, _warmup_failed

    pool = kernel_process._Pool()
    made: list[_PoolHelper] = []
    may_stop = False
    local_calls = 0

    class FailedWarmupHelper(_PoolHelper):
        def __init__(self) -> None:
            super().__init__()
            self.ready = False
            made.append(self)
            if phase == "constructor":
                raise kernel_process._HelperStopError(self)

        def wait_ready(self, _cancelled: Any) -> None:
            raise kernel_process._HelperSilentError("Warmup-Attrappe")

        def stop(self, *, graceful: bool = False) -> None:
            if not may_stop:
                raise OSError("Beendigungsattrappe")
            self.alive = False

    def local_job(*_args: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        nonlocal local_calls
        local_calls += 1
        return {}, {}

    monkeypatch.setattr(kernel_process, "_POOL", pool)
    monkeypatch.setattr(kernel_process, "_Helper", FailedWarmupHelper)
    monkeypatch.setitem(kernel_jobs.JOBS, "warmup_probe", local_job)
    warmup = _ImportWarmup()
    crashed: list[str] = []
    warmup.crashed.connect(_warmup_failed)
    warmup.crashed.connect(crashed.append)
    try:
        warmup.run()
        assert len(crashed) == 1 and crashed[0].startswith("KernelHelperStopError:")
        assert "the import warmup did not come back" in caplog.text
        assert made[0].alive and pool.processes() == [made[0]]
        assert pool.disabled

        def request() -> Any:
            weight = kernel_process.OFFLOAD_ABOVE + 1 if worker_request else 0
            return kernel_process.run("warmup_probe", {}, {}, weight=weight)

        for _attempt in range(2):
            with pytest.raises(kernel_process.KernelHelperStopError) as failed:
                if worker_request:
                    in_a_worker(request)
                else:
                    request()
            assert REPORT_ERROR in failed.value.suggestions
            assert not failed.value.values
        assert local_calls == 0, "Der Neustartbedarf wird nicht vom lokalen Rückfall verschluckt."
        may_stop = True
        assert pool.shutdown() == 1
        assert kernel_process.run("warmup_probe", {}, {}, weight=0) == ({}, {})
        assert local_calls == 1
    finally:
        may_stop = True
        pool.shutdown()


def test_pool_waiting_kernel_request_keeps_a_new_stop_error_visible(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ein beim Warten auf einen Platz entstandener Stopfehler verbietet den lokalen Rückfall."""
    pool = kernel_process._Pool()
    may_stop = False
    local_calls = 0
    monkeypatch.setattr(kernel_process, "_Helper", _PoolHelper)
    helpers = [pool.take(None) for _index in range(kernel_process.MOST_HELPERS)]
    victim = helpers[0]
    assert victim is not None

    def stop_refused(*, graceful: bool = False) -> None:
        if not may_stop:
            raise OSError("Beendigungsattrappe während der Platzsuche")
        victim.alive = False

    class StopWhileWaiting(threading.Condition):
        def wait(self, timeout: float | None = None) -> bool:
            with pytest.raises(kernel_process.KernelHelperStopError):
                pool.discard(victim)
            return True

    def local_job(*_args: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        nonlocal local_calls
        local_calls += 1
        return {}, {}

    pool._lock = StopWhileWaiting()
    monkeypatch.setattr(victim, "stop", stop_refused)
    monkeypatch.setattr(kernel_process, "_POOL", pool)
    monkeypatch.setattr(kernel_process, "OFFLOAD_ABOVE", 0)
    monkeypatch.setitem(kernel_jobs.JOBS, "waiting_probe", local_job)
    try:
        with pytest.raises(kernel_process.KernelHelperStopError):
            in_a_worker(lambda: kernel_process.run("waiting_probe", {}, {}, weight=1))
        assert local_calls == 0
        assert pool.disabled and victim in pool.processes()
    finally:
        may_stop = True
        pool.shutdown()


@pytest.mark.parametrize("refusal", ("silent", "lasting-refusal"))
def test_pool_call_fallback_keeps_another_helpers_stop_error_visible(
    monkeypatch: pytest.MonkeyPatch, refusal: str
) -> None:
    """Auch nach einer stummen oder ablehnenden Antwort darf kein Stopfehler verschwinden."""
    pool = kernel_process._Pool()
    may_stop = False
    local_calls = 0

    class AnsweringHelper(_PoolHelper):
        stubborn = False

        def call(self, *_args: Any, **_kwargs: Any) -> None:
            other = pool.take(None)
            assert other is not None
            other.stubborn = True
            with pytest.raises(kernel_process.KernelHelperStopError):
                pool.discard(other)
            if refusal == "silent":
                raise kernel_process._HelperSilentError("Antwortattrappe")
            raise kernel_process._HelperRefusedError("Antwortattrappe", lasting=True)

        def stop(self, *, graceful: bool = False) -> None:
            if self.stubborn and not may_stop:
                raise OSError("Beendigungsattrappe des anderen Helfers")
            self.alive = False

    def local_job(*_args: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        nonlocal local_calls
        local_calls += 1
        return {}, {}

    monkeypatch.setattr(kernel_process, "_POOL", pool)
    monkeypatch.setattr(kernel_process, "_Helper", AnsweringHelper)
    monkeypatch.setattr(kernel_process, "OFFLOAD_ABOVE", 0)
    monkeypatch.setitem(kernel_jobs.JOBS, "answer_probe", local_job)
    try:
        with pytest.raises(kernel_process.KernelHelperStopError):
            in_a_worker(lambda: kernel_process.run("answer_probe", {}, {}, weight=1))
        assert local_calls == 0
        assert pool.disabled and len(pool.processes()) == 1
    finally:
        may_stop = True
        pool.shutdown()


@pytest.mark.parametrize("failure", ("optional-import", "clean-start"))
def test_pool_harmless_warmup_failure_keeps_the_local_kernel_path(
    monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    """Ein fehlender Vorabimport oder ein Start ohne Kind verlangt keinen Neustart."""
    from types import SimpleNamespace

    from app.ui import app as ui_app

    pool = kernel_process._Pool()
    original_import = ui_app.importlib.import_module

    def import_with_a_missing_optional_module(name: str) -> Any:
        if name == "scipy.spatial":
            raise ImportError("Importattrappe")
        return original_import(name)

    def clean_start_failure() -> None:
        raise OSError("Startattrappe ohne Kind")

    monkeypatch.setattr(kernel_process, "_POOL", pool)
    if failure == "optional-import":
        monkeypatch.setattr(
            ui_app,
            "importlib",
            SimpleNamespace(import_module=import_with_a_missing_optional_module),
        )
        monkeypatch.setattr(kernel_process, "_Helper", _PoolHelper)
    else:
        monkeypatch.setattr(kernel_process, "_Helper", clean_start_failure)
    monkeypatch.setitem(kernel_jobs.JOBS, "warmup_probe", lambda *_args: ({}, {}))
    warmup = ui_app._ImportWarmup()
    crashed: list[str] = []
    warmup.crashed.connect(ui_app._warmup_failed)
    warmup.crashed.connect(crashed.append)
    try:
        warmup.run()
        assert crashed == []
        assert kernel_process.run("warmup_probe", {}, {}, weight=0) == ({}, {})
    finally:
        pool.shutdown()


# --- Später bestätigtes Helferende löst nur seine eigene Sperre (RM-384) -----------------


@pytest.fixture
def late_stop_pool(
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[tuple[kernel_process._Pool, list[_PoolHelper], dict[str, int]]]:
    """Ein kontrolliert spät endender Bestand ohne echte Kindprozesse."""
    pool = kernel_process._Pool()
    made: list[_PoolHelper] = []
    calls = {"local": 0, "helper": 0}

    class LateHelper(_PoolHelper):
        def __init__(self) -> None:
            super().__init__()
            self.pid += len(made)
            made.append(self)

        def stop(self, *, graceful: bool = False) -> None:
            if self.alive:
                raise kernel_process._HelperStopError(self)
            super().stop(graceful=graceful)

        def call(self, *_args: Any, **_kwargs: Any) -> tuple[dict[str, Any], dict[str, Any]]:
            calls["helper"] += 1
            return {}, {"executed": "helper"}

    def local_job(*_args: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        calls["local"] += 1
        return {}, {"executed": "local"}

    monkeypatch.setattr(kernel_process, "_POOL", pool)
    monkeypatch.setattr(kernel_process, "_Helper", LateHelper)
    monkeypatch.setattr(kernel_process, "OFFLOAD_ABOVE", 0)
    monkeypatch.setitem(kernel_jobs.JOBS, "late_stop_probe", local_job)
    try:
        yield pool, made, calls
    finally:
        # Auch ein rotes Assert darf die autouse-Bereinigung nicht rot machen.
        # Alle Wiederaufnahmezusagen werden vor diesem shutdown geprüft.
        for helper in made:
            helper.alive = False
        pool.shutdown()


@pytest.mark.parametrize("entry", ("local", "worker", "take"))
def test_pool_late_stop_end_recovers_without_shutdown(
    late_stop_pool: tuple[kernel_process._Pool, list[_PoolHelper], dict[str, int]],
    entry: str,
) -> None:
    """Nach bestätigtem Tod funktioniert schon der erste neue Aufruf wieder."""
    pool, made, calls = late_stop_pool
    helper = pool.take(None)
    assert helper is not None
    with pytest.raises(kernel_process.KernelHelperStopError):
        pool.discard(helper)
    assert pool.processes() == [helper] and pool.disabled
    assert pool.counts.get("stopped", 0) == 0

    with pytest.raises(kernel_process.KernelHelperStopError):
        kernel_process.run("late_stop_probe", {}, {}, weight=0)
    with pytest.raises(kernel_process.KernelHelperStopError):
        in_a_worker(lambda: kernel_process.run("late_stop_probe", {}, {}, weight=1), timeout=10.0)
    assert calls == {"local": 0, "helper": 0}
    assert pool.take(None) is None
    assert len(made) == 1

    helper.alive = False
    if entry == "local":
        assert kernel_process.run("late_stop_probe", {}, {}, weight=0) == (
            {},
            {"executed": "local"},
        )
        assert calls == {"local": 1, "helper": 0}
        assert pool.processes() == []
    elif entry == "worker":
        assert in_a_worker(
            lambda: kernel_process.run("late_stop_probe", {}, {}, weight=1), timeout=10.0
        ) == ({}, {"executed": "helper"})
        assert calls == {"local": 0, "helper": 1}
        assert len(made) == 2 and pool.processes() == [made[-1]]
    else:
        fresh = pool.take(None)
        assert fresh is not None and fresh is not helper
        assert calls == {"local": 0, "helper": 0}
        assert pool.processes() == [fresh]
    assert not pool.disabled
    assert helper not in pool.processes()
    assert pool.counts.get("stopped", 0) == 1


@pytest.mark.parametrize("entry", ("worker", "take"))
@pytest.mark.parametrize(
    ("start_type", "stop_mode"),
    (
        pytest.param(None, "alive", id="normal"),
        pytest.param(OSError, "alive", id="constructor-error"),
        pytest.param(OSError, "raises", id="constructor-stop-error"),
        pytest.param(LookupError, "alive", id="constructor-unexpected-error"),
        pytest.param(LookupError, "raises", id="constructor-unexpected-stop-error"),
        pytest.param(OSError, "ended-error", id="constructor-ended-error"),
        pytest.param(LookupError, "ended-error", id="constructor-unexpected-ended-error"),
    ),
)
def test_pool_late_stop_end_releases_the_real_helper_once(
    monkeypatch: pytest.MonkeyPatch,
    entry: str,
    start_type: type[BaseException] | None,
    stop_mode: str,
) -> None:
    """Das echte Stoppen gibt frei; erwartete Fehlstarts bleiben auch danach gezählt."""
    from contextlib import nullcontext
    from types import SimpleNamespace

    start_problem = None if start_type is None else start_type("Leitungsattrappe")
    expected_start = start_type is OSError
    ended_in_cleanup = stop_mode == "ended-error"

    class PipeEnd:
        def __init__(self, *, fail_first: bool = False) -> None:
            self.closed = 0
            self.fail_first = fail_first

        def close(self) -> None:
            self.closed += 1
            if self.fail_first and self.closed == 1:
                assert start_problem is not None
                raise start_problem

    class Child:
        pid = 42

        def __init__(self) -> None:
            self.alive = False
            self.kills = 0
            self.joins = 0

        def start(self) -> None:
            self.alive = True

        def is_alive(self) -> bool:
            return self.alive

        def kill(self) -> None:
            self.kills += 1
            if stop_mode == "ended-error":
                self.alive = False
            if stop_mode != "alive":
                raise OSError("Beendigungsattrappe")

        def join(self, timeout: float | None = None) -> None:
            self.joins += 1

    mine, peer = PipeEnd(), PipeEnd(fail_first=start_problem is not None)
    child = Child()
    pool = kernel_process._Pool()
    bound: list[Child] = []
    released: list[Child] = []
    fresh: list[_PoolHelper] = []
    local_calls = 0
    helper_calls = 0
    context = SimpleNamespace(Pipe=lambda **_args: (mine, peer), Process=lambda **_args: child)

    def release(process: Child) -> None:
        assert not process.alive, "Ein lebendes Kind darf seinen Jobgriff nicht verlieren."
        released.append(process)

    def ready(helper: Any, _cancelled: Any) -> None:
        helper.ready = True

    def local_job(*_args: Any) -> tuple[dict[str, Any], dict[str, Any]]:
        nonlocal local_calls
        local_calls += 1
        return {}, {"executed": "local"}

    class FreshHelper(_PoolHelper):
        def __init__(self) -> None:
            super().__init__()
            fresh.append(self)

        def call(self, *_args: Any) -> tuple[dict[str, Any], dict[str, Any]]:
            nonlocal helper_calls
            helper_calls += 1
            return {}, {"executed": "helper"}

    monkeypatch.setattr(kernel_process, "_POOL", pool)
    monkeypatch.setattr(kernel_process, "_CONTEXT", context)
    monkeypatch.setattr(kernel_process, "_helper_environment", nullcontext)
    monkeypatch.setattr(kernel_process, "OFFLOAD_ABOVE", 0)
    monkeypatch.setattr(kernel_process, "STARTS_BEFORE_GIVING_UP", 1)
    monkeypatch.setattr(kernel_process._Helper, "wait_ready", ready)
    monkeypatch.setattr(kernel_process.process_boundary, "bind_helper", bound.append)
    monkeypatch.setattr(kernel_process.process_boundary, "release_helper", release)
    monkeypatch.setitem(kernel_jobs.JOBS, "late_release_probe", local_job)
    stop_problem: kernel_process.KernelHelperStopError | None = None
    try:
        if ended_in_cleanup:
            if expected_start:
                assert pool.take(None) is None
            else:
                with pytest.raises(LookupError) as unexpected:
                    pool.take(None)
                assert unexpected.value is start_problem
            assert not child.alive and pool.processes() == []
            assert released == [child] and pool.counts.get("stopped", 0) == 0
        else:
            if start_problem is None:
                helper = pool.take(None)
                assert helper is not None
                with pytest.raises(kernel_process.KernelHelperStopError):
                    pool.discard(helper)
                assert bound == [child]
            else:
                with pytest.raises(kernel_process.KernelHelperStopError) as failed:
                    pool.take(None)
                stop_problem = failed.value
                assert not bound, "Der Konstruktor scheitert vor dem Binden."
            assert child.alive and pool.processes() == [child]
            assert not released and pool.counts.get("stopped", 0) == 0
            assert pool.disabled and pool._starting == 0
            with pytest.raises(kernel_process.KernelHelperStopError):
                kernel_process.run("late_release_probe", {}, {}, weight=0)
            assert local_calls == 0
            child.alive = False

        assert child.kills == 1 and child.joins == int(stop_mode == "alive")
        assert mine.closed >= 1 and peer.closed >= 1
        assert kernel_process.run("late_release_probe", {}, {}, weight=0) == (
            {},
            {"executed": "local"},
        )
        assert local_calls == 1 and pool.processes() == []
        assert released == [child]
        assert child.kills == 1
        assert child.joins == int(stop_mode == "alive") + int(not ended_in_cleanup)
        stopped = int(not ended_in_cleanup)
        assert pool.counts.get("stopped", 0) == stopped
        pool.raise_if_stop_failed()

        # Der nächste echte Startweg muss die Ursache prüfen, nicht nur weight=0.
        monkeypatch.setattr(kernel_process, "_Helper", FreshHelper)
        if entry == "worker":
            outcome = in_a_worker(
                lambda: kernel_process.run("late_release_probe", {}, {}, weight=1), timeout=10.0
            )
            assert outcome == ({}, {"executed": "local" if expected_start else "helper"})
            assert helper_calls == int(not expected_start)
        else:
            taken = pool.take(None)
            if expected_start:
                assert taken is None
            else:
                assert taken is not None and fresh == [taken]
                pool.give_back(taken)
            assert helper_calls == 0
        assert len(fresh) == int(not expected_start)
        assert pool.disabled is expected_start
        assert pool._failed_starts == int(expected_start)
        if stop_problem is not None:
            assert stop_problem.__cause__ is not None
            assert stop_problem.__cause__.__cause__ is start_problem
        assert pool.counts.get("stopped", 0) == stopped and released == [child]

        # shutdown ist der bewusste Sitzungsreset und darf wieder einen Helfer starten.
        pool.shutdown()
        assert not pool.disabled and pool._failed_starts == 0
        assert pool.take(None) is not None
        assert len(fresh) == int(not expected_start) + 1
    finally:
        child.alive = False
        pool.shutdown()
    assert released == [child], "Auch die abschließende Bereinigung gibt nicht doppelt frei."


def test_pool_reaps_dead_orphans_while_a_live_orphan_keeps_the_kernel_locked(
    late_stop_pool: tuple[kernel_process._Pool, list[_PoolHelper], dict[str, int]],
) -> None:
    """Tote werden vollständig gesammelt; ein Lebender hält die Rechensperre."""
    pool, made, calls = late_stop_pool
    assert kernel_process.MOST_HELPERS >= 2
    old = [pool.take(None) for _index in range(kernel_process.MOST_HELPERS)]
    assert all(helper is not None for helper in old)
    for helper in old:
        with pytest.raises(kernel_process.KernelHelperStopError):
            pool.discard(helper)
    for helper in old[:-1]:
        helper.alive = False

    with pytest.raises(kernel_process.KernelHelperStopError):
        kernel_process.run("late_stop_probe", {}, {}, weight=0)
    assert pool.processes() == [old[-1]] and pool.disabled
    assert pool.counts.get("stopped", 0) == len(old) - 1
    assert calls == {"local": 0, "helper": 0} and len(made) == len(old)

    old[-1].alive = False
    pool._lock = _ObservedPoolCondition()
    fresh = [pool.take(None) for _index in range(kernel_process.MOST_HELPERS)]
    assert all(helper is not None and helper not in old for helper in fresh)
    assert set(pool.processes()) == set(fresh)
    assert not pool.disabled and pool.counts.get("stopped", 0) == len(old)
    with pytest.raises(_PoolFullError):
        pool.take(None)
    assert len(made) == 2 * kernel_process.MOST_HELPERS


@pytest.mark.parametrize("cause", ("disable", "start-error"))
def test_pool_late_stop_end_keeps_a_permanent_disabling_cause(
    monkeypatch: pytest.MonkeyPatch,
    late_stop_pool: tuple[kernel_process._Pool, list[_PoolHelper], dict[str, int]],
    cause: str,
) -> None:
    """Die Stop-Sperre endet; eine zusätzliche bleibende Absage bleibt erhalten."""
    pool, made, calls = late_stop_pool
    helper = pool.take(None)
    assert helper is not None
    if cause == "disable":
        pool.disable("Dauerhafte Absageattrappe", helper)
    else:
        assert kernel_process.MOST_HELPERS >= 2

        def failed_start() -> None:
            raise OSError("Startattrappe")

        monkeypatch.setattr(kernel_process, "_Helper", failed_start)
        for _index in range(kernel_process.STARTS_BEFORE_GIVING_UP):
            assert pool.take(None) is None
        monkeypatch.setattr(kernel_process, "_Helper", type(helper))
    assert pool.disabled
    with pytest.raises(kernel_process.KernelHelperStopError):
        pool.discard(helper)
    helper.alive = False

    assert kernel_process.run("late_stop_probe", {}, {}, weight=0) == (
        {},
        {"executed": "local"},
    )
    assert in_a_worker(
        lambda: kernel_process.run("late_stop_probe", {}, {}, weight=1), timeout=10.0
    ) == ({}, {"executed": "local"})
    assert calls == {"local": 2, "helper": 0}
    assert pool.disabled and pool.processes() == []
    assert pool.take(None) is None and len(made) == 1
    assert pool.counts.get("stopped", 0) == 1


def test_pool_retry_of_a_live_failed_stop_never_unlocks_the_kernel(
    monkeypatch: pytest.MonkeyPatch,
    late_stop_pool: tuple[kernel_process._Pool, list[_PoolHelper], dict[str, int]],
) -> None:
    """Auch während des erneuten Stopps darf kein lokaler Rückfall beginnen."""
    pool, _made, calls = late_stop_pool
    helper = pool.take(None)
    assert helper is not None
    with pytest.raises(kernel_process.KernelHelperStopError):
        pool.discard(helper)
    entered, release = threading.Event(), threading.Event()
    outcome: dict[str, Any] = {}

    def delayed_stop(*, graceful: bool = False) -> None:
        entered.set()
        assert release.wait(10.0), "Der Test gibt den Wiederholungsstopp frei."
        helper.alive = False

    def retry() -> None:
        try:
            outcome["value"] = pool.discard(helper)
        except BaseException as problem:
            outcome["error"] = problem

    monkeypatch.setattr(helper, "stop", delayed_stop)
    worker = threading.Thread(target=retry, name="late-stop-retry", daemon=True)
    worker.start()
    try:
        assert entered.wait(10.0), "Der erneut aufgerufene Stopp ist bestätigt."
        assert helper.alive and pool.disabled
        with pytest.raises(kernel_process.KernelHelperStopError):
            kernel_process.run("late_stop_probe", {}, {}, weight=0)
        with pytest.raises(kernel_process.KernelHelperStopError):
            in_a_worker(
                lambda: kernel_process.run("late_stop_probe", {}, {}, weight=1), timeout=10.0
            )
        assert calls == {"local": 0, "helper": 0}
        assert pool.take(None) is None
        release.set()
        worker.join(10.0)
        assert not worker.is_alive() and outcome == {"value": None}, outcome
        assert pool.processes() == [] and not pool.disabled
        assert pool.counts.get("stopped", 0) == 1
        assert kernel_process.run("late_stop_probe", {}, {}, weight=0) == (
            {},
            {"executed": "local"},
        )
        assert calls == {"local": 1, "helper": 0}
    finally:
        release.set()
        worker.join(10.0)
        assert not worker.is_alive(), "Der Wiederholungsstopp muss vor dem Fixture-Ende ruhen."


def test_pool_reservation_before_reaping_does_not_cross_shutdown_generation(
    monkeypatch: pytest.MonkeyPatch,
    late_stop_pool: tuple[kernel_process._Pool, list[_PoolHelper], dict[str, int]],
) -> None:
    """Eine alte Reservierung liefert nach parallelem Schließen keinen neuen Helfer."""
    pool, made, _calls = late_stop_pool
    helper = pool.take(None)
    assert helper is not None
    with pytest.raises(kernel_process.KernelHelperStopError):
        pool.discard(helper)
    helper.alive = False
    stopping, release, stop_returned, reaped = (threading.Event() for _index in range(4))
    closing_waits, closed = threading.Event(), threading.Event()
    outcomes: dict[str, Any] = {}
    original_stop = helper.stop

    def delayed_stop(*, graceful: bool = False) -> None:
        stopping.set()
        assert release.wait(10.0), "Der Test gibt das Einsammeln frei."
        original_stop(graceful=graceful)
        stop_returned.set()

    def reserve() -> None:
        try:
            outcomes["reserve"] = pool.take(None)
        except BaseException as problem:
            outcomes["reserve_error"] = problem

    def close() -> None:
        try:
            outcomes["close"] = pool.shutdown()
        except BaseException as problem:
            outcomes["close_error"] = problem
        finally:
            closed.set()

    taker = threading.Thread(target=reserve, name="late-stop-reserve", daemon=True)
    closer = threading.Thread(target=close, name="late-stop-close", daemon=True)

    class OrderedCondition(threading.Condition):
        def __enter__(self) -> bool:
            if threading.current_thread() is taker and reaped.is_set():
                # Außerhalb des Schlosses warten: shutdown schließt vollständig,
                # bevor die alte Reservierung ihre nächste Entscheidung trifft.
                assert closed.wait(10.0), "Das parallele Schließen wird abgeschlossen."
            return super().__enter__()

        def __exit__(self, *args: Any) -> None:
            super().__exit__(*args)
            if threading.current_thread() is taker and stop_returned.is_set():
                reaped.set()

        def wait(self, timeout: float | None = None) -> bool:
            if threading.current_thread() is closer:
                closing_waits.set()
            assert super().wait(10.0), "Der laufende Stopp gibt den wartenden Schließer frei."
            return True

    pool._lock = OrderedCondition()
    monkeypatch.setattr(helper, "stop", delayed_stop)
    taker.start()
    try:
        assert stopping.wait(10.0), "Die alte Reservierung sammelt den Toten ein."
        closer.start()
        assert closing_waits.wait(10.0), "shutdown wartet auf genau diesen laufenden Stopp."
        release.set()
        taker.join(10.0)
        closer.join(10.0)
        assert not taker.is_alive() and not closer.is_alive()
        assert outcomes == {"reserve": None, "close": 1}, outcomes
        assert pool.processes() == [] and not pool.disabled and len(made) == 1
        fresh = pool.take(None)
        assert fresh is not None and fresh is not helper
        pool.discard(helper)
        pool.give_back(helper)
        assert pool.processes() == [fresh] and pool.counts.get("stopped", 0) == 1
    finally:
        release.set()
        taker.join(10.0)
        if closer.ident is not None:
            closer.join(10.0)
        assert not taker.is_alive() and not closer.is_alive()


def test_pool_reaping_failure_does_not_strand_an_unvisited_dead_helper(
    monkeypatch: pytest.MonkeyPatch,
    late_stop_pool: tuple[kernel_process._Pool, list[_PoolHelper], dict[str, int]],
) -> None:
    """Eine unerwartete Ausnahme lässt den nächsten Toten weiterhin einsammelbar."""
    pool, _made, calls = late_stop_pool
    assert kernel_process.MOST_HELPERS >= 2
    old = [pool.take(None), pool.take(None)]
    assert all(helper is not None for helper in old)
    for helper in old:
        with pytest.raises(kernel_process.KernelHelperStopError):
            pool.discard(helper)
        helper.alive = False
    stops = 0

    def stop_once_raising(*, graceful: bool = False) -> None:
        nonlocal stops
        stops += 1
        if stops == 1:
            raise RuntimeError("Bereinigungsattrappe")

    for helper in old:
        monkeypatch.setattr(helper, "stop", stop_once_raising)
    try:
        with pytest.raises(RuntimeError, match="Bereinigungsattrappe"):
            pool.raise_if_stop_failed()
        assert len(pool.processes()) == 1 and pool.counts.get("stopped", 0) == 1
        assert kernel_process.run("late_stop_probe", {}, {}, weight=0) == (
            {},
            {"executed": "local"},
        )
        assert pool.processes() == [] and not pool.disabled
        assert pool.counts.get("stopped", 0) == 2 and stops == 2
        assert calls == {"local": 1, "helper": 0}
    finally:
        # Die gezielte Gegenvariante kann den unbesuchten in _stopping belassen.
        # Ohne Testfäden lösen wir nur die Fixture-Bereinigung; alle Asserts stehen davor.
        with pool._lock:
            for helper in old:
                pool._stopping.discard(helper)
            pool._lock.notify_all()
        # Vor dem Fix wird die gestellte Ausnahme erst im Teardown erreicht.
        for helper in old:
            monkeypatch.setattr(helper, "stop", type(helper).stop.__get__(helper))


@pytest.mark.parametrize("worker_request", (False, True), ids=("main-thread", "worker-thread"))
def test_pool_local_choice_checks_a_stop_error_from_the_path_decision(
    monkeypatch: pytest.MonkeyPatch,
    late_stop_pool: tuple[kernel_process._Pool, list[_PoolHelper], dict[str, int]],
    worker_request: bool,
) -> None:
    """Ein Stopfehler nach dem frühen Guard darf nicht den lokalen Job freigeben."""
    pool, _made, calls = late_stop_pool
    helper = pool.take(None)
    assert helper is not None and not pool.disabled
    original_offloaded = kernel_process.offloaded
    decisions = 0

    def choose_while_a_stop_fails(weight: int) -> bool:
        nonlocal decisions
        decisions += 1
        with pytest.raises(kernel_process.KernelHelperStopError):
            pool.discard(helper)
        return original_offloaded(weight)

    monkeypatch.setattr(kernel_process, "offloaded", choose_while_a_stop_fails)
    with pytest.raises(kernel_process.KernelHelperStopError):
        if worker_request:
            in_a_worker(
                lambda: kernel_process.run("late_stop_probe", {}, {}, weight=1), timeout=10.0
            )
        else:
            kernel_process.run("late_stop_probe", {}, {}, weight=0)
    assert decisions == 1 and calls == {"local": 0, "helper": 0}
    assert helper.alive and pool.processes() == [helper] and pool.disabled


def test_pool_lasting_refusal_survives_a_failed_stop_on_public_run(
    monkeypatch: pytest.MonkeyPatch,
    late_stop_pool: tuple[kernel_process._Pool, list[_PoolHelper], dict[str, int]],
) -> None:
    """Die dauerhafte Absage des run-Wegs bleibt nach späterem Helferende bestehen."""
    pool, made, calls = late_stop_pool
    late_helper = kernel_process._Helper
    refusals = 0

    class RefusingHelper(late_helper):
        def call(self, *_args: Any, **_kwargs: Any) -> None:
            nonlocal refusals
            refusals += 1
            raise kernel_process._HelperRefusedError("Dauerhafte Absageattrappe", lasting=True)

    monkeypatch.setattr(kernel_process, "_Helper", RefusingHelper)
    with pytest.raises(kernel_process.KernelHelperStopError):
        in_a_worker(lambda: kernel_process.run("late_stop_probe", {}, {}, weight=1), timeout=10.0)
    assert len(made) == 1 and refusals == 1
    assert made[0].alive and pool.processes() == [made[0]] and pool.disabled
    assert calls == {"local": 0, "helper": 0}
    assert pool.counts.get("stopped", 0) == 0

    made[0].alive = False
    assert in_a_worker(
        lambda: kernel_process.run("late_stop_probe", {}, {}, weight=1), timeout=10.0
    ) == ({}, {"executed": "local"})
    assert pool.disabled and pool.processes() == []
    assert pool.take(None) is None
    assert len(made) == 1 and refusals == 1
    assert calls == {"local": 1, "helper": 0}
    assert pool.counts.get("stopped", 0) == 1


def test_pool_ready_failures_survive_failed_stops_on_public_take(
    monkeypatch: pytest.MonkeyPatch,
    late_stop_pool: tuple[kernel_process._Pool, list[_PoolHelper], dict[str, int]],
) -> None:
    """Jeder wirkliche Bereitschaftsfehler zählt trotz verweigertem Stopp."""
    pool, made, calls = late_stop_pool
    late_helper = kernel_process._Helper
    ready_failures = 0

    class UnreadyHelper(late_helper):
        def __init__(self) -> None:
            super().__init__()
            self.ready = False

        def wait_ready(self, _cancelled: Any) -> None:
            nonlocal ready_failures
            ready_failures += 1
            raise kernel_process._HelperSilentError("Bereitschaftsattrappe")

    monkeypatch.setattr(kernel_process, "_Helper", UnreadyHelper)
    limit = kernel_process.STARTS_BEFORE_GIVING_UP
    assert limit >= 1
    for index in range(limit):
        # Der nächste take muss zuerst den inzwischen Toten einsammeln und
        # den folgenden Start versuchen; es gibt kein Zwischen-shutdown.
        with pytest.raises(kernel_process.KernelHelperStopError):
            pool.take(None)
        assert len(made) == ready_failures == index + 1
        assert made[-1].alive and pool.processes() == [made[-1]] and pool.disabled
        assert pool.counts.get("stopped", 0) == index
        assert calls == {"local": 0, "helper": 0}
        made[-1].alive = False

    assert in_a_worker(
        lambda: kernel_process.run("late_stop_probe", {}, {}, weight=1), timeout=10.0
    ) == ({}, {"executed": "local"})
    assert pool.disabled and pool.processes() == []
    assert pool.take(None) is None
    assert len(made) == ready_failures == limit
    assert calls == {"local": 1, "helper": 0}
    assert pool.counts.get("stopped", 0) == limit


_TRANSFER_FAILURES = (
    "enospc",
    "enomem",
    "windows-8",
    "windows-14",
    "windows-1450",
    "windows-1455",
    "memory",
)


def _transfer_allocation_problem(failure: str) -> BaseException:
    """Stellt Fehlercodes ohne plattformabhängigen OSError-Konstruktor."""
    if failure == "enospc":
        return OSError(errno.ENOSPC, "Platzattrappe")
    if failure == "enomem":
        return OSError(errno.ENOMEM, "Speicherattrappe")
    if failure == "memory":
        return MemoryError("Eigenständige Speicherattrappe")
    code = int(failure.removeprefix("windows-"))

    class ReportedWindowsError(OSError):
        @property
        def winerror(self) -> int:
            return code

    # errno trägt absichtlich keinen Speicherfehler: Nur winerror zählt.
    # Diese lokale Klasse wird nur als Ursache genutzt; _opened wandelt
    # sie vor dem Helferprotokoll in den gewöhnlichen MemoryError um.
    return ReportedWindowsError(errno.EINVAL, "Windows-Speicherattrappe")


@pytest.mark.parametrize("entry", ("pack", "copied"))
@pytest.mark.parametrize("failure", _TRANSFER_FAILURES)
def test_shared_memory_transfer_keeps_space_and_memory_failures_distinct(
    monkeypatch: pytest.MonkeyPatch, entry: str, failure: str
) -> None:
    """ENOSPC bleibt derselbe OSError; Speichermangel behält seine Ursache."""
    problem = _transfer_allocation_problem(failure)
    attempts: list[dict[str, Any]] = []
    source = {"marker": np.array([11, 22], dtype=np.int64)}

    def refusing(**arguments: Any) -> Any:
        attempts.append(arguments)
        raise problem

    def transfer() -> Any:
        if entry == "pack":
            return kernel_jobs.pack(source)
        layout = [("marker", source["marker"].dtype.str, (2,), 0)]
        return kernel_jobs.copied("input-attrappe", layout)

    monkeypatch.setattr(kernel_jobs.shared_memory, "SharedMemory", refusing)
    if failure == "enospc":
        with pytest.raises(OSError) as caught:
            transfer()
        assert caught.value is problem and caught.value.errno == errno.ENOSPC
    else:
        with pytest.raises(MemoryError) as caught:
            transfer()
        assert caught.value.args == (str(problem),)
        if failure == "memory":
            assert caught.value is problem and caught.value.__cause__ is None
        else:
            assert caught.value.__cause__ is problem
    expected = (
        {"track": False, "create": True, "size": source["marker"].nbytes}
        if entry == "pack"
        else {"track": False, "name": "input-attrappe"}
    )
    assert attempts == [expected]


class _TransferBufferHandle:
    """Nur NumPy-Puffer und Aufrufzähler, keine echten Speichergriffe."""

    def __init__(self, owner: Any, name: str, buf: bytearray) -> None:
        self.owner, self.name, self.buf = owner, name, buf
        self.closed = 0
        self.unlinked = 0

    def close(self) -> None:
        self.closed += 1

    def unlink(self) -> None:
        self.unlinked += 1
        self.owner.buffers.pop(self.name, None)


class _TransferMemory:
    """Unterscheidet die drei tatsächlichen Aufrufe des Speicherherstellers."""

    def __init__(self, stage: str, problem: BaseException) -> None:
        self.stage, self.problem = stage, problem
        self.in_helper = False
        self.buffers: dict[str, bytearray] = {}
        self.handles: list[_TransferBufferHandle] = []
        self.attempts: list[str] = []

    def __call__(self, **arguments: Any) -> _TransferBufferHandle:
        assert arguments.get("track") is False
        creating = arguments.get("create", False)
        where = "parent-input"
        if self.in_helper:
            where = "helper-output" if creating else "helper-input"
        self.attempts.append(where)
        if where == self.stage:
            raise self.problem
        if creating:
            name = f"transfer-{len(self.buffers)}"
            self.buffers[name] = bytearray(arguments["size"])
        else:
            name = arguments["name"]
        handle = _TransferBufferHandle(self, name, self.buffers[name])
        self.handles.append(handle)
        return handle


@pytest.mark.parametrize("stage", ("parent-input", "helper-input", "helper-output"))
@pytest.mark.parametrize("failure", _TRANSFER_FAILURES)
def test_public_run_distinguishes_enospc_from_memory_in_both_transfers(
    monkeypatch: pytest.MonkeyPatch, stage: str, failure: str
) -> None:
    """Der echte Call-/Serve-Anschluss fällt nur bei ENOSPC dauerhaft lokal zurück."""
    from types import SimpleNamespace

    problem = _transfer_allocation_problem(failure)
    memory = _TransferMemory(stage, problem)
    pool = kernel_process._Pool()
    made: list[_PoolHelper] = []
    calls = {"local": 0, "helper": 0}
    source = {"marker": np.array([11, 22], dtype=np.int64)}
    actual_call = kernel_process._Helper.call

    def job(arrays: Any, _values: Any, check: Callable[[], None]) -> Any:
        check()
        same_bytes(source, arrays)
        where = "helper" if memory.in_helper else "local"
        calls[where] += 1
        marker = 222 if memory.in_helper else 111
        return {"marker": np.array([marker], dtype=np.int64)}, {"executed": where}

    class TransferHelper(_PoolHelper):
        call = actual_call

        def __init__(self) -> None:
            super().__init__()
            made.append(self)
            self.connection = SimpleNamespace(send=self.send)
            self.lines: list[_Line] = []
            self.replies: list[tuple[Any, ...]] = []

        def send(self, message: tuple[Any, ...]) -> None:
            assert message[0] == "job", "Diese Fälle enden vor einer Ergebnisbestätigung."
            line = _Line([message], broken_at="")
            self.lines.append(line)
            memory.in_helper = True
            try:
                # Ein wirklicher serve-Aufruf bis EOF: kein nachgebautes
                # refused-Protokoll, aber auch kein Prozess oder OS-Speicher.
                kernel_jobs.serve(line)
            finally:
                memory.in_helper = False
            self.replies = [reply for reply in line.sent if reply[0] != "ready"]

        def _receive(self, _cancelled: Any, _deadline: float | None) -> tuple[Any, ...]:
            assert self.replies, "serve hat eine tatsächliche Antwort geliefert."
            return self.replies.pop(0)

    monkeypatch.setattr(kernel_process, "_POOL", pool)
    monkeypatch.setattr(kernel_process, "_Helper", TransferHelper)
    monkeypatch.setattr(kernel_process, "OFFLOAD_ABOVE", 0)
    monkeypatch.setitem(kernel_jobs.JOBS, "enospc_transfer_probe", job)
    monkeypatch.setattr(kernel_jobs.shared_memory, "SharedMemory", memory)
    monkeypatch.setattr(kernel_jobs, "_yield_to_the_window", lambda: None)
    monkeypatch.setattr(kernel_jobs.multiprocessing, "parent_process", lambda: None)

    def run() -> Any:
        return in_a_worker(
            lambda: kernel_process.run("enospc_transfer_probe", source, {}, weight=1),
            timeout=10.0,
        )

    helper_calls = int(stage == "helper-output")
    expected_attempts = ["parent-input"]
    if stage != "parent-input":
        expected_attempts.append("helper-input")
    if stage == "helper-output":
        expected_attempts.append("helper-output")
    try:
        if failure == "enospc":
            got = run()
            same_bytes({"marker": np.array([111], dtype=np.int64)}, got[0])
            assert got[1] == {"executed": "local"}
            assert calls == {"local": 1, "helper": helper_calls}
            assert pool.counts == {"started": 1, "stopped": 1, "fallback": 1}
            assert pool.disabled and pool.processes() == []
            got = run()
            same_bytes({"marker": np.array([111], dtype=np.int64)}, got[0])
            assert got[1] == {"executed": "local"}
            assert calls == {"local": 2, "helper": helper_calls}
            assert pool.counts == {"started": 1, "stopped": 1, "fallback": 1, "in_process": 1}
            assert pool.disabled and pool.take(None) is None
        else:
            with pytest.raises(MemoryError) as caught:
                run()
            assert caught.value.args == (str(problem),)
            if stage == "parent-input":
                if failure == "memory":
                    assert caught.value is problem and caught.value.__cause__ is None
                else:
                    assert caught.value.__cause__ is problem
            else:
                assert any(
                    "im Hilfsprozess des Kerns (42)" in note
                    for note in getattr(caught.value, "__notes__", ())
                )
            assert calls == {"local": 0, "helper": helper_calls}
            assert pool.counts == {"started": 1, "stopped": 1}
            assert not pool.disabled and pool.processes() == []
        assert len(made) == 1 and not made[0].alive
        assert memory.attempts == expected_attempts and not memory.buffers
        assert all(handle.closed == 1 for handle in memory.handles)
        assert [handle.unlinked for handle in memory.handles] == (
            [] if stage == "parent-input" else [1] if stage == "helper-input" else [1, 0]
        )
        if stage == "parent-input":
            assert made[0].lines == []
        else:
            assert len(made[0].lines) == 1
            assert [reply[0] for reply in made[0].lines[0].sent] == (
                ["ready", "refused"]
                if stage == "helper-input"
                else ["ready", "accepted", "refused"]
            )
    finally:
        pool.shutdown()
