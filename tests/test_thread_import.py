"""Gewinde an importierter Geometrie: die Fallmatrix aus P2.5 als Regressionen.

Ein eingelesener STEP-Körper trägt keine Steigung, keine Händigkeit, keine
Gangzahl — nur Kanten, die sich um eine Achse winden. ``app.core.brep.thread``
liest daraus die Auskunft. Die Sollwerte hier kommen aus den
**Konstruktionsmaßen**: für die vier Basiskörper aus
``tests/data/make_thread_corpus.py``, für alles Abgeleitete aus der Ableitung
in diesem Modul (Spiegelung, Lage, Zuschnitt, Beschädigung, geteilte Träger,
NURBS) — nie aus dem Prüfling. Toleranzen wie im Nachweisbericht: Teilung und
Vorschub 1e-4, Radien 1e-3, Achse 1e-6 im Skalarprodukt, Länge 1e-3 nur an
vollständigen Körpern; die Wendelabweichung wird gemeldet, nicht verschluckt.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from app.core.brep.kernel import Solid, available
from app.core.errors import OperationCancelled
from app.core.sketch.profile import Profile, ProfileSegment
from app.core.types import SceneObject

pytestmark = pytest.mark.skipif(not available(), reason="OpenCASCADE is an optional dependency")

THREADS = Path(__file__).parent / "data" / "threads"

#: Der ISO-Profilanteil von ``profiles.threaded_rod`` — die Gangtiefe je Teilung.
ISO_DEPTH_SHARE = 0.6134

#: Die Basiskörper und ihre Konstruktionsmaße (``make_thread_corpus.py``).
BASES: dict[str, dict[str, Any]] = {
    "m6_rechts": {
        "pitch": 1.0,
        "lead": 1.0,
        "starts": 1,
        "handedness": "right",
        "internal": False,
        "diameter": 6.0,
        "depth": ISO_DEPTH_SHARE * 1.0,
        "length": 12.0,
    },
    "m10_rechts": {
        "pitch": 1.5,
        "lead": 1.5,
        "starts": 1,
        "handedness": "right",
        "internal": False,
        "diameter": 10.0,
        "depth": ISO_DEPTH_SHARE * 1.5,
        "length": 20.0,
    },
    "m8_innen": {
        "pitch": 1.25,
        "lead": 1.25,
        "starts": 1,
        "handedness": "right",
        "internal": True,
        # Der Nenn-Ø eines Innengewindes ist sein Grund-Ø: Bolzen Ø 8 plus 0,2 Spiel.
        "diameter": 8.2,
        "depth": ISO_DEPTH_SHARE * 1.25,
        "length": 10.0,
    },
    "zweigaengig": {
        "pitch": 1.0,
        "lead": 2.0,
        "starts": 2,
        "handedness": "right",
        "internal": False,
        "diameter": 8.0,
        # Kamm auf major/2, Fuß auf major/2 - 0,55 p, der Kern liegt 0,01 darüber.
        "depth": 0.55 - 0.01,
        "length": 12.0,
    },
}


def _read(name: str) -> Solid:
    from app.core.brep import step

    return step.read((THREADS / f"{name}.step").read_bytes())


@pytest.fixture(scope="module")
def m6() -> Solid:
    return _read("m6_rechts")


def _reading(solid: Solid) -> Any:
    from app.core.brep.thread import read_thread

    return read_thread(solid)


def _expect(reading: Any, expected: dict[str, Any], *, partial: bool = False) -> None:
    """Die Auskunft gegen die Konstruktionsmaße — mit den Toleranzen des Berichts."""
    assert reading.found, reading.reason
    assert reading.pitch == pytest.approx(expected["pitch"], abs=1e-4)
    assert reading.lead == pytest.approx(expected["lead"], abs=1e-4)
    assert reading.starts == expected["starts"]
    assert reading.handedness == expected["handedness"]
    assert reading.internal is expected["internal"]
    assert reading.diameter == pytest.approx(expected["diameter"], abs=1e-3)
    assert reading.depth == pytest.approx(expected["depth"], abs=1e-3)
    axis = expected.get("axis", (0.0, 0.0, 1.0))
    assert abs(float(np.dot(reading.axis, axis))) == pytest.approx(1.0, abs=1e-6)
    if not partial:
        assert reading.length == pytest.approx(expected["length"], abs=1e-3)
    assert reading.uncertainty < 0.01 * reading.pitch, reading.uncertainty


# --- Ableitungen aus M6: dieselbe Geometrie, anders dargestellt oder beschnitten -----


def _polygon(points: list[tuple[float, float]]) -> Profile:
    segments = tuple(
        ProfileSegment("line", points[index - 1], points[index]) for index in range(len(points))
    )
    return Profile(segments=segments)


def _rotation(
    degrees: float, axis: tuple[float, float, float], offset: tuple[float, float, float]
) -> Any:
    """Drehung um eine Achse durch den Ursprung, dann verschoben — Rodrigues, ausgeschrieben."""
    a = np.asarray(axis, dtype=float)
    a = a / np.linalg.norm(a)
    t = math.radians(degrees)
    c, s = math.cos(t), math.sin(t)
    x, y, z = a
    rows = [
        [c + x * x * (1 - c), x * y * (1 - c) - z * s, x * z * (1 - c) + y * s, offset[0]],
        [y * x * (1 - c) + z * s, c + y * y * (1 - c), y * z * (1 - c) - x * s, offset[1]],
        [z * x * (1 - c) - y * s, z * y * (1 - c) + x * s, c + z * z * (1 - c), offset[2]],
        [0.0, 0.0, 0.0, 1.0],
    ]
    return tuple(tuple(float(v) for v in row) for row in rows)


def _rotated_axis(degrees: float, axis: tuple[float, float, float]) -> tuple[float, float, float]:
    """Wohin die Z-Achse nach ``_rotation`` zeigt — der unabhängige Sollwert."""
    a = np.asarray(axis, dtype=float)
    a = a / np.linalg.norm(a)
    t = math.radians(degrees)
    c, s = math.cos(t), math.sin(t)
    x, y, z = a
    return (x * z * (1 - c) + y * s, y * z * (1 - c) - x * s, c + z * z * (1 - c))


def _mirrored(solid: Solid) -> Solid:
    """Spiegelung an der XZ-Ebene: Achse bleibt Z, aus rechts wird links."""
    from app.core.brep import edit

    matrix = (
        (1.0, 0.0, 0.0, 0.0),
        (0.0, -1.0, 0.0, 0.0),
        (0.0, 0.0, 1.0, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    )
    return edit.transformed(solid, matrix)


def _slab(solid: Solid, z0: float, z1: float) -> Solid:
    """Nur z0..z1 bleibt, beide Enden geschnitten."""
    from app.core.brep import edit

    slab = edit.moved(edit.box(200.0, 200.0, z1 - z0), (0.0, 0.0, z0))
    return edit.boolean("intersection", [solid, slab])


def _halved(solid: Solid) -> Solid:
    """Angeschnitten: alles unter x = −1 fehlt."""
    from app.core.brep import edit

    box = edit.moved(edit.box(200.0, 200.0, 200.0), (99.0, 0.0, -50.0))
    return edit.boolean("intersection", [solid, box])


def _damaged(solid: Solid, z0: float, z1: float, degrees: float, from_radius: float) -> Solid:
    """Beschädigte Flanken: ein Sektor des Mantels ab ``from_radius`` fehlt."""
    from app.core.brep import edit, profiles

    reach = 100.0
    outline = [
        (from_radius, 0.0),
        (reach, 0.0),
        (reach * math.cos(math.radians(degrees)), reach * math.sin(math.radians(degrees))),
        (
            from_radius * math.cos(math.radians(degrees)),
            from_radius * math.sin(math.radians(degrees)),
        ),
    ]
    cutter = edit.moved(profiles.extrude(_polygon(outline), z1 - z0), (0.0, 0.0, z0))
    return edit.boolean("difference", [solid, cutter])


def _sector_piece(solid: Solid, z0: float, z1: float, degrees: float) -> Solid:
    """Ein kleiner Ausschnitt: Höhe z0..z1, Winkelsektor 0..degrees."""
    from app.core.brep import edit, profiles

    reach = 100.0
    outline = [
        (0.0, 0.0),
        (reach, 0.0),
        (reach * math.cos(math.radians(degrees)), reach * math.sin(math.radians(degrees))),
    ]
    wedge = edit.moved(profiles.extrude(_polygon(outline), z1 - z0), (0.0, 0.0, z0))
    return edit.boolean("intersection", [solid, wedge])


def _reparametrised(solid: Solid) -> Solid:
    """Alle Flächen und Kurven als NURBS — eine andere Darstellung derselben Geometrie."""
    from OCP.BRepBuilderAPI import BRepBuilderAPI_NurbsConvert

    return Solid(BRepBuilderAPI_NurbsConvert(solid.shape, True).Shape())


def _split_faces(solid: Solid, z: float) -> Solid:
    """Flächen und Kanten an einer Ebene geteilt, der Körper bleibt einer."""
    from OCP.BOPAlgo import BOPAlgo_Splitter
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.collections import List_TopoDS_Shape
    from OCP.gp import gp_Dir, gp_Pln, gp_Pnt
    from OCP.TopAbs import TopAbs_SOLID
    from OCP.TopExp import TopExp_Explorer
    from OCP.TopoDS import TopoDS

    from app.core.brep import edit

    plane = BRepBuilderAPI_MakeFace(
        gp_Pln(gp_Pnt(0.0, 0.0, z), gp_Dir(0.0, 0.0, 1.0)), -100.0, 100.0, -100.0, 100.0
    ).Face()
    splitter = BOPAlgo_Splitter()
    arguments = List_TopoDS_Shape()
    arguments.Append(solid.shape)
    tools = List_TopoDS_Shape()
    tools.Append(plane)
    splitter.SetArguments(arguments)
    splitter.SetTools(tools)
    splitter.Perform()
    explorer = TopExp_Explorer(splitter.Shape(), TopAbs_SOLID)
    pieces: list[Solid] = []
    while explorer.More():
        pieces.append(Solid(TopoDS.Solid(explorer.Current())))
        explorer.Next()
    body = pieces[0]
    for other in pieces[1:]:
        body = edit.boolean("union", [body, other])
    return body


# --- Die Fallmatrix ----------------------------------------------------------------


@pytest.mark.parametrize("name", sorted(BASES))
def test_an_imported_thread_names_its_measures(name: str) -> None:
    """Rechts, M10, innen, zweigängig: Teilung, Vorschub, Gangzahl, Seite, Ø, Tiefe, Länge."""
    _expect(_reading(_read(name)), BASES[name])


def test_a_left_hand_thread_is_measured_left(m6: Solid) -> None:
    """Die Spiegelung desselben Bolzens ist links — und sonst in jedem Maß gleich."""
    _expect(_reading(_mirrored(m6)), {**BASES["m6_rechts"], "handedness": "left"})


def test_a_turned_and_shifted_thread_keeps_its_axis(m6: Solid) -> None:
    """Um 37° um (1, 1, 0) gedreht und verschoben: die Achse ist die gedrehte, sonst nichts."""
    from app.core.brep import edit

    placed = edit.transformed(m6, _rotation(37.0, (1.0, 1.0, 0.0), (12.0, -7.0, 3.0)))
    _expect(_reading(placed), {**BASES["m6_rechts"], "axis": _rotated_axis(37.0, (1.0, 1.0, 0.0))})


def test_a_halved_thread_still_measures(m6: Solid) -> None:
    """Angeschnitten (unter x = -1 fehlt alles): Maße bleiben, die Länge ist nicht zugesichert."""
    reading = _reading(_halved(m6))
    _expect(reading, BASES["m6_rechts"], partial=True)
    assert reading.turns > 7.0


def test_a_short_thread_of_two_and_a_half_turns_measures(m6: Solid) -> None:
    """2,5 Umläufe reichen — der Netzweg braucht fünf (B2)."""
    reading = _reading(_slab(m6, 4.75, 7.25))
    _expect(reading, {**BASES["m6_rechts"], "length": 2.5})
    assert reading.turns == pytest.approx(2.5, abs=0.02)


def test_damaged_flanks_sum_their_turns(m6: Solid) -> None:
    """Ein fehlender Sektor teilt die Wendel in Stücke; die zählen zusammen."""
    reading = _reading(_damaged(m6, 4.0, 8.0, 60.0, 2.6))
    _expect(reading, BASES["m6_rechts"], partial=True)
    assert reading.turns > 11.0


@pytest.mark.parametrize("derive", [_split_faces, _reparametrised], ids=["geteilt", "nurbs"])
def test_another_representation_gives_the_same_reading(m6: Solid, derive: Any) -> None:
    """Geteilte Träger und eine neue Parametrisierung ändern Geometrie und Auskunft nicht.

    Der Kurvenparameter ist kein Winkel: Abgetastet wird nach Bogenlänge, der
    Winkel kommt aus der Projektion auf die Achse.
    """
    other = _split_faces(m6, 6.0) if derive is _split_faces else _reparametrised(m6)
    reference = _reading(m6)
    reading = _reading(other)
    _expect(reading, BASES["m6_rechts"])
    assert reading.pitch == pytest.approx(reference.pitch, abs=1e-4)
    assert reading.diameter == pytest.approx(reference.diameter, abs=1e-3)
    assert abs(float(np.dot(reading.axis, reference.axis))) == pytest.approx(1.0, abs=1e-6)


def _smooth_cylinder() -> Solid:
    from app.core.brep import edit

    return edit.cylinder(6.0, 12.0)


def _ring_grooves() -> Solid:
    """Ringrillen: Zylinder minus vier Tori — periodisch, aber nicht schraubenförmig."""
    from app.core.brep import edit, profiles

    body = edit.cylinder(6.0, 12.0)
    for index in range(4):
        z = 12.0 * (index + 1) / 5.0
        torus = profiles.revolve(Profile(circle=((3.0, z), 0.4)), 360.0)
        body = edit.boolean("difference", [body, torus])
    return body


def _knurl() -> Solid:
    """Längsrillen (Rändel): periodisch um die Achse, alle Kanten gerade."""
    from app.core.brep import edit

    body = edit.cylinder(6.0, 12.0)
    for index in range(12):
        bar = edit.moved(edit.box(0.6, 0.6, 14.0), (3.0, 0.0, -1.0))
        body = edit.boolean(
            "difference",
            [
                body,
                edit.transformed(bar, _rotation(30.0 * index, (0.0, 0.0, 1.0), (0.0, 0.0, 0.0))),
            ],
        )
    return body


def _wave_profile() -> Solid:
    """Gewellter Drehkörper (Spline-Meridian): periodisch entlang der Achse, kein Gewinde."""
    from app.core.brep import profiles

    waves, steps = 6, 48
    through = tuple(
        (3.0 + 0.3 * math.sin(2.0 * math.pi * waves * index / steps), 12.0 * index / steps)
        for index in range(steps + 1)
    )
    profile = Profile(
        segments=(
            ProfileSegment("line", (0.0, 0.0), through[0]),
            ProfileSegment("spline", through[0], through[-1], through=through),
            ProfileSegment("line", through[-1], (0.0, 12.0)),
            ProfileSegment("line", (0.0, 12.0), (0.0, 0.0)),
        )
    )
    return profiles.revolve(profile, 360.0)


COUNTER_CASES = {
    "glatter Zylinder": (_smooth_cylinder, "keine Kantenzüge"),
    "Ringrillen": (_ring_grooves, "keine Kantenzüge"),
    "Rändel": (_knurl, "keine Kantenzüge"),
    "Wellenprofil": (_wave_profile, "keine Kantenzüge"),
    "Naht ohne Rille": (lambda: _read("gegen_naht"), "Gangtiefe"),
}


@pytest.mark.parametrize("label", sorted(COUNTER_CASES))
def test_bodies_without_a_thread_say_why(label: str) -> None:
    """Sechs Gegenfälle lehnen mit Grund ab — und nie mit einer geratenen Steigung."""
    build, reason = COUNTER_CASES[label]
    reading = _reading(build())
    assert not reading.found
    assert reason in reading.reason, reading.reason
    assert reading.pitch is None or reason == "Gangtiefe"


def test_a_quarter_turn_is_not_enough_for_a_pitch(m6: Solid) -> None:
    """Unter einer Umdrehung wären Achse und Steigung geraten — die Absage sagt das."""
    reading = _reading(_sector_piece(m6, 3.0, 3.4, 90.0))
    assert not reading.found
    assert "unter einer Umdrehung" in reading.reason, reading.reason
    assert reading.pitch is None


# --- Vertrag: Eingabe, Abbruch, Merkmal, Netz-Zwilling ------------------------------


def test_reading_leaves_the_input_untouched(m6: Solid) -> None:
    """Gelesen werden Kanten und Flächen; Flächen, Kanten, Volumen und Abtastpunkte bleiben."""
    from app.core.brep.thread import candidate_chains

    before = (m6.face_count, m6.edge_count, m6.volume, candidate_chains(m6)[0].points.copy())
    _reading(m6)
    after = (m6.face_count, m6.edge_count, m6.volume, candidate_chains(m6)[0].points)
    assert before[:3] == after[:3]
    assert np.array_equal(before[3], after[3])


class _CountingToken:
    """Ein Abbruch nach ``limit`` Prüfungen — und ein Zähler, wie oft gefragt wurde."""

    def __init__(self, limit: int | None) -> None:
        self.limit = limit
        self.calls = 0

    @property
    def is_cancelled(self) -> bool:
        return self.limit is not None and self.calls >= self.limit

    def raise_if_cancelled(self) -> None:
        self.calls += 1
        if self.limit is not None and self.calls >= self.limit:
            raise OperationCancelled()


def test_cancellation_reaches_every_loop(m6: Solid) -> None:
    """Der Token reißt die Messung an ihrer Schleife ab; ohne Grenze wird er laufend gefragt."""
    from app.core.brep.thread import read_thread

    counting = _CountingToken(limit=None)
    assert read_thread(m6, cancelled=counting).found
    assert counting.calls > 100, counting.calls
    early = _CountingToken(limit=50)
    with pytest.raises(OperationCancelled):
        read_thread(m6, cancelled=early)
    assert early.calls == 50


def test_features_of_publishes_one_thread_and_no_phantoms(m6: Solid) -> None:
    """Ein Gewinde im Baum — und keiner der Zapfen und Kegel, die auf seiner Wendel entstünden."""
    from app.core.brep.features import features_of

    found = features_of(m6)
    threads = [feature for feature in found.values() if feature.kind == "thread"]
    assert [feature.id for feature in threads] == ["thread_1"]
    assert not [feature for feature in found.values() if feature.kind in ("pin", "cone", "sphere")]
    thread = threads[0]
    assert thread.provenance == "detected"
    assert thread.params["pitch"] == pytest.approx(1.0, abs=1e-4)
    assert thread.params["diameter"] == pytest.approx(6.0, abs=1e-3)
    assert thread.params["handedness"] == "right"
    assert thread.params["starts"] == 1
    assert thread.params["internal"] is False
    assert thread.params["crest_radius"] == pytest.approx(3.0, abs=1e-3)
    assert thread.params["root_radius"] == pytest.approx(3.0 - ISO_DEPTH_SHARE, abs=1e-3)
    assert thread.measure_sources["pitch"] == "native"
    assert thread.measure_sources["handedness"] == "native"
    assert thread.measure_sources["axis"] in ("native", "fit")
    assert thread.face_indices, "ein Klick auf eine Flanke wählt das Gewinde"
    carriers = m6.faces_of_triangles(thread.face_indices)
    assert len(carriers) >= 13, "Flanken, Kamm und Grund tragen die Züge"
    entry = SceneObject(id="obj_1", name="Bolzen", mesh=m6, kind="brep", features=found)
    assert entry.features["thread_1"].kind == "thread"


def test_an_internal_thread_names_its_root_diameter() -> None:
    """Innen ist der Nenn-Ø der Grund-Ø, und der Kamm liegt innen (B7)."""
    reading = _reading(_read("m8_innen"))
    assert reading.internal is True
    assert reading.crest_radius < reading.root_radius
    assert reading.diameter == pytest.approx(8.2, abs=1e-3)


def test_a_two_start_thread_separates_lead_and_pitch() -> None:
    """Zwei Gänge: Vorschub 2, Teilung 1 — aus der Periodizität aller Wendeln, nicht der Kämme."""
    reading = _reading(_read("zweigaengig"))
    assert reading.starts == 2
    assert reading.lead == pytest.approx(2.0, abs=1e-4)
    assert reading.pitch == pytest.approx(1.0, abs=1e-4)


def test_the_mesh_twin_agrees_where_it_can(m6: Solid) -> None:
    """Der Netzweg misst Teilung und Seite im Raster gleich; Händigkeit und Gangzahl fehlen ihm."""
    from app.core.geom.mesh import as_mesh_data
    from app.core.perceive.helix import PITCH_STEP, find_helices

    helices = find_helices(as_mesh_data(m6))
    assert len(helices) == 1
    exact = _reading(m6)
    # Das Netz sucht die Steigung in einem Raster von 0,01: eine Rasterstufe daneben
    # ist dieselbe Auskunft, zwei wären eine andere.
    assert helices[0].pitch == pytest.approx(exact.pitch, abs=1.5 * PITCH_STEP)
    assert helices[0].internal is exact.internal
    assert helices[0].diameter == pytest.approx(exact.diameter, abs=0.05)
