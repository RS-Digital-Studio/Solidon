"""Dieselbe Geometrie auf jeder Maschine — Bit für Bit (RM-187).

**Der Anlass, gemessen am 17.09.2026.** Derselbe Körper trug 1226 Dreiecke auf
Windows, 1224 auf Ubuntu und 1228 auf macOS, mit demselben Python, demselben
NumPy und demselben Quelltext. Die Ursache lag vor dem Booleschen Kern:
``np.cos`` wählt seine Implementierung nach den Fähigkeiten der CPU — AVX-512,
AVX2, NEON —, und die drei runden die letzte Stelle verschieden. Ein Kunde auf
dem Mac konnte eine Bohrungskette nicht bearbeiten, die auf Windows
bearbeitbar war.

**Was diese Datei ist: der Wächter, der sagt, wann es behoben bleibt.** Sie
schreibt für eine Reihe typischer Körper die Bits fest. Läuft sie auf allen
drei Plattformen grün, gilt die Zusage; wird sie auf einer rot, rechnet dort
etwas anders — und zwar an genau der Stelle, die der Testname nennt.

**Regel 6 gilt hier ausdrücklich nicht.** Die Zusage *ist* die bitgenaue
Gleichheit; ein Vergleich mit Toleranz würde genau den Unterschied
verschlucken, um den es geht. Genau deshalb hat ihn jahrelang niemand gesehen.

**Und die Sollwerte kommen aus einem Lauf.** Das ist erlaubt, weil dies ein
Determinismusnachweis ist und der Test das sagt (`.claude/rules/tests.md`,
„Korpus"). Ein einzelner grüner Lauf auf einer Maschine belegt dabei **nichts**
— die Aussage entsteht erst daraus, dass dieselben Zahlen auf drei
verschiedenen Rechenwerken herauskommen.
"""

from __future__ import annotations

import contextlib
import hashlib
import json
import math
import os
import platform
import subprocess
import sys
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from app.core import units
from app.core.geom import lathe


def fingerprint(values: object) -> str:
    """Ein Hash über die rohen Bytes — gleiche Zahl heißt bitgleiches Feld."""
    raw = np.ascontiguousarray(np.asarray(values, dtype=np.float64))
    return hashlib.sha256(raw.tobytes()).hexdigest()[:16]


@pytest.mark.parametrize(
    ("sections", "digest"),
    [
        (3, "8499ba0788b12dea"),
        (4, "35051fd2bf2a3d2f"),
        (8, "0f4775e181c5061d"),
        (32, "fe8488d27a898c06"),
        (120, "169ba88212acfdba"),
        (192, "5d81998cecab205a"),
        (360, "6796c3e32617a875"),
    ],
)
def test_a_circle_has_the_same_corners_everywhere(sections: int, digest: str) -> None:
    """Die Ecken eines regelmäßigen Vielecks, festgeschrieben.

    Der unterste Baustein: Steht er, kann jede Geometrie darauf stehen. Fällt
    er, ist alles darüber Zufall. Acht und 360 liest die Erkennung: die
    Stichproben der Durchgangsfrage (``features.THROUGH_SAMPLES``) und die
    Richtungen der Stadionsuche über einen halben Kreis
    (``features.STADIUM_SWEEP``) — beide rechneten bis zum 23.09.2026 mit
    ``np.cos``.
    """
    values = units.circle_cos_sin(sections)

    assert len(values) == sections
    assert fingerprint(values) == digest


def test_a_cylinder_has_the_same_corners_everywhere() -> None:
    """Der Drehkörper, an dem der Befund hing.

    ``trimesh`` erzeugt die Topologie weiter; ersetzt sind nur die Ecken
    (:mod:`app.core.geom.lathe`). Dieser Test hält fest, dass das reicht.
    """
    body = lathe.cylinder(radius=4.5, height=10.0, sections=120)

    assert len(body.faces) == 480
    assert len(body.vertices) == 242
    assert fingerprint(body.vertices) == "6e428c71b58c4961"


def test_a_tube_has_the_same_corners_everywhere() -> None:
    """Dasselbe für das Rohr — es hat vier Ringe statt zweien."""
    body = lathe.annulus(r_min=3.0, r_max=5.0, height=8.0, sections=120)

    assert len(body.faces) == 960
    assert fingerprint(body.vertices) == "7cc06943c202be2b"


def test_a_revolved_outline_has_the_same_corners_everywhere() -> None:
    """Eine Kontur, die nicht von einem Primitiv kommt — der allgemeine Fall."""
    outline = np.array(
        [[2.0, 0.0], [5.0, 0.0], [5.0, 3.0], [3.5, 4.5], [2.0, 4.5], [2.0, 0.0]],
        dtype=np.float64,
    )
    body = lathe.revolve(outline, sections=64)

    assert fingerprint(body.vertices) == "9eae755372735f95"


def test_a_plain_circle_outline_has_the_same_points_everywhere() -> None:
    """Der Umriss zum Extrudieren — kein Drehkörper, derselbe Anspruch."""
    points = lathe.circle_points(sections=64, radius=7.5, centre=(1.25, -2.5))

    assert points.shape == (64, 2)
    assert fingerprint(points) == "b71ac55dd467e8cf"


# --- Die Rechenwege, nicht nur ihre Bausteine (RM-187, 22.09.2026) ------------------
#
# Die Tests darüber schreiben die Bits der Bausteine fest — und belegen damit
# erst auf drei Maschinen etwas. Die Tests darunter belegen es auf **einer**:
# Jede Rechnung, die eine andere Maschine in der letzten Stelle anders runden
# darf, bekommt hier ein Rauschen von einer Einheit der letzten Stelle, und der
# Fingerabdruck am Ende eines Weges darf sich davon nicht rühren. Rührt er
# sich, hängt der Weg an der Maschine — und der Testname sagt, an welchem.
#
# **Was als plattformabhängig gilt, ist gemessen oder nachgelesen:**
#
# * BLAS — ``np.dot``, ``matmul``, ``inner``, ``vdot``, ``tensordot`` und die
#   Vektornorm ``np.linalg.norm`` ohne Achse (sie ruft ``dot``). OpenBLAS wählt
#   seinen Kern nach der CPU, der Mac rechnet mit Accelerate. Gemessen hier:
#   ``OPENBLAS_CORETYPE=Sandybridge`` gegen ``Haswell`` ändert ``rotation_about``.
# * ``np.einsum`` — seine Produktsummen nutzen auf ARM FMA, auf x86 nicht.
# * LAPACK — ``svd``, ``eig``, ``eigh``, ``lstsq``, ``solve``, ``inv``, ``det``:
#   andere Bibliothek, andere Pivotierung, bei Eigen- und Singulärvektoren auch
#   ein anderes Vorzeichen.
# * Transzendente Funktionen — ``np.cos`` und Geschwister wählen ihre
#   Umsetzung nach der CPU (SVML mit AVX-512, NEON), ``math.cos`` und
#   Geschwister kommen aus der Mathematikbibliothek der Plattform.
#
# **Nicht darunter, mit Absicht:** Grundrechenarten und ``sqrt`` (IEEE-754,
# korrekt gerundet), ``np.cross`` (Produkte und Differenzen je Element),
# ``np.sum``/``np.mean`` (NumPys paarweise Summe hat eine feste Reihenfolge),
# ``math.hypot`` und ``math.fsum`` (CPython rechnet sie selbst, ohne die
# Plattformbibliothek). Und ``@`` lässt sich nicht verrauschen — es ist ein
# Operator und keine Funktion eines Moduls; dafür steht
# :func:`test_a_way_through_the_kernel_does_not_follow_the_blas_kernel` daneben.
#
# Ein Ergebnis, das auf jeder Maschine exakt ist — eine ganze Zahl, ``π/2``,
# ein Skalarprodukt mit einer Achse, das eine Eingangszahl zurückgibt —,
# bekommt kein Rauschen: Dort wäre ein roter Test ein Fehlalarm.

_BLAS_LIKE = ("dot", "vdot", "inner", "matmul", "einsum", "tensordot")
_NUMPY_TRANSCENDENTAL = (
    "cos",
    "sin",
    "tan",
    "arccos",
    "arcsin",
    "arctan",
    "arctan2",
    "cosh",
    "sinh",
    "tanh",
    "exp",
    "exp2",
    "expm1",
    "log",
    "log2",
    "log10",
    "log1p",
    "hypot",
    "power",
    "cbrt",
)
_LAPACK = ("norm", "svd", "eig", "eigh", "eigvals", "eigvalsh", "lstsq", "solve", "inv", "det")
_MATH = (
    "cos",
    "sin",
    "tan",
    "acos",
    "asin",
    "atan",
    "atan2",
    "cosh",
    "sinh",
    "tanh",
    "exp",
    "expm1",
    "log",
    "log2",
    "log10",
    "log1p",
    "pow",
)
_EXACT_EVERYWHERE = np.array([np.pi, np.pi / 2, np.pi / 4, 3 * np.pi / 4])


class _Noise:
    """Welche Stellen eines Ergebnisses ein ULP wandern — ein festes Muster
    über die Bits des Werts, damit jeder Lauf dasselbe Rauschen trägt."""

    multiplier = np.uint64(0x9E3779B97F4A7C15)

    def __init__(self, pattern: int = 0) -> None:
        # Ein ungerader Faktor je Muster; Muster 0 ist das bisherige Rauschen.
        self.multiplier = np.uint64((0x9E3779B97F4A7C15 * (2 * pattern + 1)) % 2**64)

    def array(self, result: object, operands: np.ndarray | None) -> object:
        values = np.asarray(result)
        if values.dtype.kind != "f":
            return result
        flat = np.array(values, dtype=np.float64, copy=True)
        pick = ((flat.view(np.uint64) * self.multiplier) >> np.uint64(61)) & np.uint64(1)
        exact = ~np.isfinite(flat) | (flat == np.round(flat))
        exact |= np.isin(np.abs(flat), _EXACT_EVERYWHERE)
        if operands is not None and operands.size:
            exact |= np.isin(np.abs(flat), operands)
        move = (pick == 1) & ~exact
        flat[move] = np.nextafter(flat[move], np.inf)
        if values.ndim == 0:
            return float(flat) if isinstance(result, float) else flat.astype(values.dtype)[()]
        return flat.astype(values.dtype, copy=False)

    def scalar(self, value: object) -> object:
        if not isinstance(value, float) or not np.isfinite(value) or value == round(value):
            return value
        if abs(value) in _EXACT_EVERYWHERE:
            return value
        bits = int(np.float64(value).view(np.uint64))
        if ((bits * int(self.multiplier)) & (2**64 - 1)) >> 63:
            return float(np.nextafter(value, np.inf))
        return value


def _operands(args: tuple[object, ...]) -> np.ndarray:
    """Die Beträge der Eingangszahlen — ein Ergebnis unter ihnen ist exakt."""
    found = []
    for value in args:
        if isinstance(value, (np.ndarray, list, tuple, float, int)):
            try:
                array = np.asarray(value, dtype=np.float64).ravel()
            except TypeError, ValueError:
                continue
            if array.size <= 2_000_000:
                found.append(np.abs(array))
    return np.concatenate(found) if found else np.zeros(0)


@contextlib.contextmanager
def platform_noise(pattern: int = 0) -> Iterator[None]:
    """Legt auf jede plattformabhängige Rechnung ein Rauschen von einem ULP.

    ``pattern`` wählt, welche Stellen wandern — eine andere Maschine in der
    letzten Stelle. Jedes Muster ist fest: derselbe Lauf, dasselbe Rauschen.
    """
    noise = _Noise(pattern)
    undo: list[Callable[[], None]] = []

    def patch(module: Any, name: str, *, exact_on_operands: bool) -> None:
        real = getattr(module, name, None)
        if real is None:
            return

        def noisy(*args: Any, **kwargs: Any) -> Any:
            result = real(*args, **kwargs)
            # ``norm`` über eine Achse ist ``sqrt(add.reduce(x·x))`` — je
            # Element und damit überall gleich. Nur ohne Achse ruft sie ``dot``.
            if name == "norm" and (kwargs.get("axis") is not None or len(args) > 2):
                return result
            operands = _operands(args) if exact_on_operands else None
            if isinstance(result, tuple):
                items = tuple(noise.array(item, operands) for item in result)
                return type(result)(*items) if hasattr(result, "_fields") else items
            if isinstance(result, (np.ndarray, np.floating, float)):
                return noise.array(result, operands)
            return result

        setattr(module, name, noisy)
        undo.append(lambda: setattr(module, name, real))

    def patch_math(name: str) -> None:
        real = getattr(math, name)

        def noisy(*args: Any) -> Any:
            return noise.scalar(real(*args))

        setattr(math, name, noisy)
        undo.append(lambda: setattr(math, name, real))

    try:
        for name in _BLAS_LIKE:
            patch(np, name, exact_on_operands=True)
        for name in _NUMPY_TRANSCENDENTAL:
            patch(np, name, exact_on_operands=False)
        for name in _LAPACK:
            patch(np.linalg, name, exact_on_operands=name == "norm")
        for name in _MATH:
            patch_math(name)
        yield
    finally:
        for step in reversed(undo):
            step()


def _mesh_print(mesh: Any) -> str:
    from app.core.geom.mesh import as_mesh_data

    raw = as_mesh_data(mesh).raw
    return f"{len(raw.faces)}/{fingerprint(raw.vertices)}"


def _plate() -> Any:
    """Eine Platte 60 × 40 × 8 mit zwei Bohrungen — aus festen Maßen, ohne BLAS."""
    from app.core.deferred import trimesh
    from app.core.geom.boolean import boolean
    from app.core.geom.mesh import MeshData

    plate = trimesh.creation.box(extents=(60.0, 40.0, 8.0))
    plate.vertices = np.asarray(plate.vertices) + np.array([3.0, -2.0, 4.0])
    first = lathe.cylinder(radius=3.1, height=20.0, sections=64)
    first.vertices = np.asarray(first.vertices) + np.array([-12.0, 4.0, 4.0])
    second = lathe.cylinder(radius=4.25, height=20.0, sections=96)
    second.vertices = np.asarray(second.vertices) + np.array([17.5, -6.0, 4.0])
    return boolean("difference", [MeshData.of(plate), MeshData.of(first), MeshData.of(second)]).mesh


def _registered(name: str, source: Any, **params: object) -> Any:
    """Eine Operation über ihren Registereintrag, mit dem Vorgabeprofil."""
    from app.core.bootstrap import load_operations
    from app.core.knowledge import profiles
    from app.core.registry import REGISTRY
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene, SceneObject

    load_operations()
    entry = SceneObject(id="obj_1", name="Platte", mesh=source)
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    spec = REGISTRY.get(name)
    result = spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}, profile=profile),
            inputs=[entry],
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=20260922,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )
    return result.outputs[0].mesh


def _changed_bore() -> str:
    """Der Änderungsweg aus RM-187: Senkbohrung mit Nachbarloch, auf Ø 6 verkleinert."""
    from app.core.knowledge import profiles
    from tests.helpers import feature_operation, sloping_bore

    mesh, features, hole = sloping_bore()
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    result = feature_operation(
        "resize_hole", mesh, features, hole, profile, diameter=6.0, compensate=False
    )
    return _mesh_print(result.outputs[0].mesh)


@pytest.mark.parametrize("towards", [np.inf, -np.inf])
def test_resizing_a_bore_does_not_use_lapack_rounding_for_its_centre(
    monkeypatch: pytest.MonkeyPatch,
    towards: float,
) -> None:
    """Ein ULP im Kreisfit darf nicht zur Lage des neuen Schneidkörpers werden.

    Die allgemeine Rauschprobe bewegt nur einen Teil der letzten Stellen.
    Hier wandern gezielt beide Mittelpunktkoeffizienten eines Ausgleichs;
    der vollständige Änderungsweg muss trotzdem dieselben Netzbytes liefern.
    Vor jedem Lauf wird die Erkennung neu gerechnet, damit ihr globaler Cache
    nicht die ungeänderte Antwort des ersten Laufs zurückgibt.
    """
    from app.core.bootstrap import load_operations
    from app.core.perceive.features import forget_cache

    load_operations()
    forget_cache()
    before = _changed_bore()
    original = np.linalg.lstsq

    def rounded(*args: Any, **kwargs: Any) -> Any:
        solution, *rest = original(*args, **kwargs)
        changed = solution.copy()
        changed[:2] = np.nextafter(changed[:2], towards)
        return changed, *rest

    monkeypatch.setattr(np.linalg, "lstsq", rounded)
    forget_cache()
    try:
        assert _changed_bore() == before
    finally:
        forget_cache()


def _drilled_along_the_face() -> str:
    """*Bohrung setzen* mit freier Richtung an der schräg liegenden Platte (RM-274).

    Das Werkzeug wandert über den Rahmen der Bohrung in die Welt, die Enden in
    einer Fläche mit Luft dahinter bekommen die Zugabe (``prepare._open_ends``):
    Sackloch, Aufweitung (Übergang über die exakten Winkelfunktionen) und ein
    Boden in der Unterseite. Bis zur Durchsicht 0.5.1 lag der Körper im Rahmen,
    und den Rückweg rechnete ``np.linalg.inv``. **Das Langloch fehlt hier mit
    Grund:** Seine Bögen tastet ``sketch_solid._arc_points`` über ``math.atan2``,
    ``math.cos`` und ``math.sin`` ab, und das ist ein offener Posten von RM-187
    (mit ihm wird dieser Weg rot).
    """
    from app.core.geom.transform import apply, moved_points, rotation, turned

    turn = rotation("x", 33.0)
    tilted = apply(_plate(), turn)
    normal = turned(np.array([[0.0, 0.0, 1.0]]), turn)[0]
    prints = []
    for spot, values in (
        ((5.0, 8.0), {"depth": 3.0}),
        ((-5.0, 12.0), {"depth": 5.0, "widening_diameter": 9.0, "widening_depth": 1.5}),
        ((25.0, 8.0), {"depth": 8.0}),
    ):
        mouth = moved_points(np.array([[spot[0], spot[1], 8.0]]), turn)[0]
        drilled = _registered(
            "drill_hole",
            tilted,
            diameter=4.0,
            x=float(mouth[0]),
            y=float(mouth[1]),
            z=float(mouth[2]),
            nx=float(normal[0]),
            ny=float(normal[1]),
            nz=float(normal[2]),
            **values,
        )
        prints.append(_mesh_print(drilled))
    return "|".join(prints)


def _turned_plate() -> str:
    """*Drehen* um die eigene Mitte — um 37 Grad, also keine Vierteldrehung."""
    return _mesh_print(_registered("rotate_object", _plate(), axis="z", angle=37.0))


def _oriented_plate(thorough: bool) -> str:
    """*Druckoptimal ausrichten* an einer schräg liegenden Platte."""
    from app.core.geom.transform import apply, rotation

    tilted = apply(_plate(), rotation("x", 33.0))
    return _mesh_print(_registered("orient_for_print", tilted, thorough=thorough, arrange=False))


def _slanted_cut() -> str:
    """Ein Schnitt mit einer schrägen Ebene, gedeckelt."""
    from app.core.geom.section import SectionPlane, cut

    normal = (0.3, -0.2, 0.9)
    length = math.hypot(*normal)
    plane = SectionPlane(
        normal=(normal[0] / length, normal[1] / length, normal[2] / length), position=1.7
    )
    return _mesh_print(cut(_plate(), plane).mesh)


def _aligned_plate() -> str:
    """Eine Bohrungsachse auf eine schräge zweite gelegt."""
    from app.core.geom.align import align_matrix
    from app.core.geom.transform import apply
    from app.core.types import Feature

    mover = Feature(
        id="hole_1",
        kind="hole",
        provenance="detected",
        params={"axis": (0.2, 0.3, 0.9), "centre": (1.5, -2.0, 3.0)},
    )
    target = Feature(
        id="hole_2",
        kind="hole",
        provenance="detected",
        params={"axis": (-0.4, 0.8, 0.1), "centre": (7.0, 5.0, -1.0)},
    )
    return _mesh_print(apply(_plate(), align_matrix(mover, target)))


def _turned_closures() -> str:
    """Bajonett und Rastdrehscheibe (RM-184): Schlitze und Sektoren unter krummen Winkeln.

    Der Drehweg von 13 Grad, der halbe Öffnungswinkel eines Schlitzes und die
    Tortenstücke der Sektoren gehen über Winkelfunktionen in die Ecken — das
    ist der Ort, an dem eine Plattformfunktion die letzte Stelle verschöbe.
    """
    from app.core.knowledge.parts import builtin

    parts = builtin.load()
    bayonet, detent = parts.get("bayonet"), parts.get("detent_disc")
    socket = bayonet.fn(bayonet.params(kind="socket", diameter=75.0, turn=13.0, play=0.25))
    disc = detent.fn(detent.params(kind="disc", play=0.25))
    return f"{_mesh_print(socket.mesh)}|{_mesh_print(disc.mesh)}"


def _posed_plate() -> str:
    """Eine Stellung über zwei Knochen, mit Winkeln, die keine rechten sind."""
    from app.core.geom.pose import posed
    from app.core.types import Bone, Pose

    bones = [
        Bone(name="a", head=(-30.0, 0.0, 4.0), tail=(0.0, 0.0, 4.0), parent=""),
        Bone(name="b", head=(0.0, 0.0, 4.0), tail=(30.0, 0.0, 4.0), parent="a"),
    ]
    poses = [Pose(bone="a", angles=(0.0, 12.5, 0.0)), Pose(bone="b", angles=(7.0, 30.0, -11.0))]
    return _mesh_print(posed(_plate(), bones, poses))


def _thickened_skin() -> str:
    """*Offene Fläche schließen* an der Platte ohne ihre Deckfläche."""
    from app.core.geom.mesh import MeshData
    from app.core.geom.mesh_ops import _thickened

    raw = _plate().raw.copy()
    raw.update_faces(np.asarray(raw.triangles_center)[:, 2] <= 7.9)
    raw.remove_unreferenced_vertices()
    return _mesh_print(_thickened(MeshData.of(raw), 1.2))


def _refined_plate() -> str:
    """*Kanten verfeinern* an der Platte — ob ein weiterer Durchgang folgt, entscheidet
    die längste Kante (RM-223)."""
    from app.core.geom.mesh_ops import remesh

    return _mesh_print(remesh(_plate(), 3.0))


def _mended_import() -> str:
    """Der Import eines Netzes mit Löchern — Ränder werden geohrt und geschlossen."""
    from app.core.geom.mesh import MeshData
    from app.core.ingest.loader import normalise

    raw = _plate().raw.copy()
    centres = np.asarray(raw.triangles_center)
    near = np.hypot(centres[:, 0] + 12.0, centres[:, 1] - 4.0)
    keep = ~((centres[:, 2] > 3.0) & (near < 3.2)) & ~(
        (centres[:, 2] < 1.0) & (near > 6.0) & (near < 20.0)
    )
    raw.update_faces(keep)
    raw.remove_unreferenced_vertices()
    return _mesh_print(normalise(MeshData.of(raw), "mm").mesh)


def _resolved_crossings() -> str:
    """*Reparieren* mit „Überschneidungen auflösen" an zwei ineinandergesteckten Schalen.

    Ob vereinigt wird, entscheiden die Schnittsuche und das Vorzeichen jedes
    Schalenvolumens (Befund B17 der Durchsicht 24.09.2026).
    """
    from app.core.deferred import trimesh
    from app.core.geom.mesh import MeshData
    from app.core.geom.transform import apply, rotation

    peg = MeshData.of(trimesh.creation.box(extents=(14.0, 9.0, 20.0)))
    turned = apply(peg, rotation("z", 23.0)).raw.copy()
    turned.vertices = np.asarray(turned.vertices) + np.array([17.0, 6.0, 5.0])
    crossing = MeshData.of(trimesh.util.concatenate([_plate().raw, turned]))
    return _mesh_print(_registered("repair", crossing, self_intersections=True))


def _differently_split_contact_edge() -> str:
    """Kantenkontakt zweier Quader mit verschiedener Unterteilung."""
    from app.core.deferred import trimesh
    from app.core.geom.repair import parts_that_cross

    first = trimesh.creation.box(extents=(1.0, 1.0, 10.0))
    first.apply_translation((0.5, 0.5, 5.0))
    second = trimesh.creation.box(extents=(1.0, 1.0, 5.0))
    second.apply_translation((-0.5, -0.5, 2.5))
    touching = trimesh.util.concatenate([first, second])
    return repr(
        (
            parts_that_cross(touching),
            parts_that_cross(touching, include_face_contacts=True),
        )
    )


def _plate_without(select: Callable[[np.ndarray, np.ndarray], np.ndarray]) -> Any:
    """Die Platte ohne die Dreiecke, die ``select(mitten, normalen)`` nennt."""
    from app.core.geom.mesh import MeshData

    raw = _plate().raw.copy()
    centres = np.asarray(raw.triangles_center)
    normals = np.asarray(raw.face_normals)
    raw.update_faces(~select(centres, normals))
    raw.remove_unreferenced_vertices()
    return MeshData.of(raw)


def _bore_wall_band() -> str:
    """*Reparieren* an der Platte ohne die Wand der ersten Bohrung — ein Band (Review R11)."""
    from app.core.geom.repair import repair

    def wall(centres: np.ndarray, normals: np.ndarray) -> np.ndarray:
        across = np.hypot(centres[:, 0] + 12.0, centres[:, 1] - 4.0)
        return np.asarray((across < 3.3) & (np.abs(normals[:, 2]) < 0.5))

    return _mesh_print(repair(_plate_without(wall)).mesh)


def _top_with_holes() -> str:
    """*Reparieren* an der Platte ohne ihre Oberseite — eine Fläche mit zwei Löchern."""
    from app.core.geom.repair import repair

    def top(centres: np.ndarray, normals: np.ndarray) -> np.ndarray:
        return np.asarray((centres[:, 2] > 7.99) & (normals[:, 2] > 0.9))

    return _mesh_print(repair(_plate_without(top)).mesh)


def _inverted_hollow() -> str:
    """Ein Hohlkörper, ganz verkehrt herum — der Strahl entscheidet, was sich dreht."""
    from app.core.deferred import trimesh
    from app.core.geom.mesh import MeshData
    from app.core.geom.repair import unify_normals

    cavity = trimesh.creation.box(extents=(5.0, 4.0, 3.0))
    cavity.vertices = np.asarray(cavity.vertices) + np.array([3.5, -2.5, 4.0])
    cavity.invert()
    hollow = trimesh.util.concatenate([_plate().raw.copy(), cavity])
    hollow.invert()
    return _mesh_print(unify_normals(MeshData.of(hollow))[0])


def _step_assembly() -> str:
    """Eine STEP-Baugruppe in Weltlage (P7.4): verschachtelt, eine Instanz gespiegelt.

    Die Lagen rechnet OpenCASCADE (``gp_Trsf``), die Gruppengrenzen fürs Bett
    ``load_step`` in Python — beides darf am Rauschen nicht hängen.
    """
    from pathlib import Path

    from app.core.brep import step
    from app.core.brep.kernel import Solid
    from tests.helpers import exact_kernel

    exact_kernel()
    payload = (Path(__file__).parent / "data" / "step" / "nested.step").read_bytes()
    bodies = step.read_assembly(payload, "nested").bodies
    return "|".join(
        f"{body.key}:{body.name}:{body.face_colours}:{_mesh_print(Solid(body.shape).mesh)}"
        for body in bodies
    )


def _worked_corner(rounded: bool) -> str:
    """*Verrunden* und *Fase* an der schiefen Dreiflächenecke eines Tetraeders (RM-166).

    Die Ecke, an der der Linux-Runner einmal in vier Läufen einen Punkt im
    Normalenkegel bei 6,5 statt 3,0 hatte
    (``test_mesh_edges.test_a_nonorthogonal_trihedral_corner_has_the_tangent_sphere``):
    Stützebenen, Halbraumecken, Kugelmitte und Kugel des Eckanschlusses.
    """
    from app.core.deferred import trimesh
    from app.core.geom.edges import bevel_edges, edge_key, edges_of, round_edges
    from app.core.geom.mesh import MeshData

    body = MeshData(
        trimesh.convex.convex_hull(np.asarray([(0, 0, 0), (40, 0, 0), (0, 40, 0), (0, 0, 40)]))
    )
    corner = (40.0, 0.0, 0.0)
    touching = [
        entry
        for entry in edges_of(body)
        if min(math.dist(corner, entry.points[0]), math.dist(corner, entry.points[-1])) < 1e-7
    ]
    edit = round_edges if rounded else bevel_edges
    return _mesh_print(edit(body, 3.0, "named", [edge_key(entry) for entry in touching]).mesh)


_GROOVED: list[Any] = []


def _curved_mouth() -> str:
    """Stopfen und Werkzeug einer Kette, deren Mündung in einer Rinne liegt (RM-248).

    Die Höhe jeder Ecke des Deckels kommt aus einem Polynom, das an die Fläche
    um den Rand angepasst wurde (``geom.mouth_cap``). Der Körper und seine
    Kette entstehen einmal und außerhalb des Rauschens; unter ihm laufen nur
    Anpassung, Deckel und Werkzeug.
    """
    from app.core.geom import prepare_ops
    from app.core.geom.mesh import as_mesh_data
    from app.core.perceive.relations import cavity_chains
    from tests.helpers import BOTH_ENDS, widened_bore

    if not _GROOVED:
        source = widened_bore("mesh", BOTH_ENDS["Zylindersenkung und Fase"], bottom="Rinne R 40")
        mesh = as_mesh_data(source.mesh)
        _GROOVED.extend((mesh, cavity_chains(source.features, mesh)[0]))
    mesh, chain = _GROOVED
    plug = prepare_ops._cavity_plug(mesh, chain, quality="fine", seed=1, cancelled=None)
    tool = prepare_ops._past_curved_mouths(mesh, chain)
    assert plug is not None and tool is not None, "der Weg muss den fortgesetzten Deckel nehmen"
    return f"{_mesh_print(plug)}|{_mesh_print(tool)}"


def _aligned_pattern_facets(tilted: bool = False) -> str:
    """Die Facettenkorrektur vor einer Musteränderung, mit unabhängig gebautem Eingang."""
    from app.core.geom.prepare_ops import _aligned_facets
    from tests.helpers import rounded_pattern_carrier

    source = rounded_pattern_carrier(tilted=tilted)
    changed, refused = _aligned_facets(source, source.features["pattern_1"])
    assert not refused and changed is not source, "die Probe muss die Ecken tatsächlich ausrichten"
    return _mesh_print(changed.mesh)


def _automatic_support_angle() -> str:
    """PrusaSlicers automatische Stützschwelle, in die Grundlage zurückgelesen.

    Null heißt dort „halbe Außenwand über der Schicht"; der Winkel daraus ist
    ein Arkustangens, und mit ihm entscheidet die Schichtanalyse über
    Überhänge (Stufe C des Konzepts Herstellerprofil).
    """
    from app.core.export import manufacturer

    angle = manufacturer._prusa_support_angle(
        {"support_material_threshold": "0"}, {"layers.layer_height": 0.2}, 0.45
    )
    return repr(angle)


def _support_columns() -> str:
    """Stützvolumen, einzelne Säule und Standorturteil durch denselben Clipper-Weg."""
    from shapely.geometry import box

    from app.core.slice import analysis, findings
    from app.core.types import LayerInfo, SliceResult

    roof = box(-3.17, -2.39, 11.73, 8.91).difference(box(1.11, 0.37, 3.43, 4.27))
    material = box(-4.31, -3.71, 0.63, 9.37)
    shapes = [None, material, None, roof]
    measured = [
        analysis.LayerMetrics(
            z=index + 0.5,
            area=0.0,
            overhang_area=0.0,
            island_area=0.0,
            min_width=0.0,
            bridge_width=0.0,
            contour_count=0,
            overhang=roof if index == 3 else None,
        )
        for index in range(4)
    ]
    volume = analysis._support_volume(shapes, measured, 1.0)
    layers = tuple(
        LayerInfo(
            z=index + 0.5,
            contours=() if shape is None else analysis._to_polygons(shape),
            area=0.0 if shape is None else shape.area,
            overhang_area=roof.area if index == 3 else 0.0,
            islands=(),
            min_width=0.0,
            overhangs=analysis._to_polygons(roof) if index == 3 else (),
        )
        for index, shape in enumerate(shapes)
    )
    result = SliceResult(layers=layers, support_volume=volume, first_layer_area=0.0)
    column = findings._column_under(roof, result, 3, 0.0)
    place = analysis._model_support(result, analysis.CHANNEL_WIDTH, None)
    return fingerprint(
        [volume, column, place.open_area, place.open_patch, place.channel_area]
    ) + repr((sorted(place.channels), place.island_on_model))


def _bound_surface() -> str:
    """Zwei gespeicherte Kantenabstände auf einem schrägen, vergrößerten Träger."""
    import trimesh

    from app.core.bootstrap import load_operations
    from app.core.geom.mesh import MeshData
    from app.core.geom.transform import composed, moved_object, rotation, translation
    from app.core.registry import REGISTRY
    from app.core.scene import placement
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import IDENTITY_FRAME, SceneObject

    load_operations()
    body = MeshData.of(trimesh.creation.box((40.0, 30.0, 10.0)))
    source = SceneObject(id="obj_1", name="Träger", mesh=body, frame=IDENTITY_FRAME)
    top = int(np.argmax(body.raw.face_normals[:, 2]))
    hit = placement.at_point(placement.prepare_surface(body, top, {}), (-12.3, -6.7, 5.0))
    spec = REGISTRY.get("create_box")
    values = placement.bound_surface_values(spec, source, hit)
    matrix = composed(translation((7.0, 11.0, 4.0)), rotation("x", 13.0), rotation("y", 17.0))
    moved = moved_object(source, matrix, cancelled=NeverCancelled())
    bound = placement.bind_surface(
        spec,
        values,
        {source.id: moved},
        {source.id: "moved"},
        ask=lambda *_: pytest.fail("Eindeutiger Flächenbezug"),
        announce=None,
        cancelled=NeverCancelled(),
    )
    assert bound.placed is not None
    return fingerprint(
        [*bound.placed.point, *bound.placed.normal, *(edge.distance for edge in bound.placed.edges)]
    )


def _container(lid: str, shape: str = "round") -> str:
    """Fächer, Streulöcher, Deckel und Scharnier werden gemeinsam erzeugt."""
    from app.core.bootstrap import load_operations
    from app.core.knowledge import profiles
    from app.core.registry import REGISTRY
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene

    load_operations()
    spec = REGISTRY.get("create_container")
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    result = spec.fn(
        OpContext(
            scene=Scene(profile=profile),
            inputs=[],
            params=spec.params(
                kernel="mesh", shape=shape, lid=lid, columns=2, holes=True, opening_angle=31.0
            ),
            profile=profile,
            quality="fine",
            seed=20261003,
            progress=lambda *_: None,
            ask=lambda *_: pytest.fail("Der vollständig bemaßte Behälter braucht keine Nachfrage"),
            cancelled=NeverCancelled(),
        )
    )
    return "|".join(_mesh_print(body.mesh) for body in result.outputs)


def _rebuilt_box() -> str:
    """Kandidatenmaße eines frei ausgerichteten Nachbaus bleiben plattformgleich."""
    from app.core.brep import edit
    from app.core.brep.features import features_of
    from app.core.geom.transform import composed, rotation, translation
    from app.core.scene.rebuild import _boxed, _oriented_basis
    from app.core.types import SceneObject

    body = edit.transformed(
        edit.box(40.0, 30.0, 20.0),
        composed(translation((15.0, -9.0, 35.0)), rotation("x", 37.0), rotation("y", 13.0)),
    )
    source = SceneObject("obj_1", "Quelle", body, kind="brep", features=features_of(body))
    basis = _oriented_basis(source)
    assert basis is not None
    drafts, explained = _boxed(source, 0.1, basis)
    assert not explained
    return fingerprint([drafts[0].params[key] for key in sorted(drafts[0].params)])


def _tangential_rounds() -> str:
    """Die tangentiale Trennung am rundum verrundeten T (RM-226): wer welche Rundung trägt.

    Gezählt werden die Entscheidungen — Art und Dreiecke je Merkmal —, nicht
    die eingepassten Maße: Die Trennung wählt zwischen Keimen, Bändern,
    Kreisen und Reststücken, und keine dieser Wahlen darf an der letzten
    Stelle einer Rechnung hängen. Der Merker wird vorher geleert, sonst
    antwortete der zweite Lauf aus dem ersten.
    """
    from app.core.brep import edit
    from app.core.geom.mesh import as_mesh_data
    from app.core.perceive.features import detect, forget_cache
    from tests.helpers import exact_kernel

    exact_kernel()
    joined = edit.unified(
        edit.boolean("union", [edit.box(40.0, 10.0, 10.0), edit.box(10.0, 10.0, 40.0)])
    )
    forget_cache()
    found = detect(as_mesh_data(edit.fillet(joined, 3.0, "all")))
    decisions = sorted(
        (feature.kind, tuple(sorted(int(index) for index in feature.face_indices)))
        for feature in found.values()
    )
    assert sum(kind == "fillet" for kind, _faces in decisions) == 36, "die Probe muss trennen"
    return hashlib.sha256(repr(decisions).encode()).hexdigest()[:16]


_WAYS: dict[str, Callable[[], str]] = {
    "align_to_feature": _aligned_plate,
    "bound_surface": _bound_surface,
    "container_hinge": lambda: _container("hinged"),
    "container_screw": lambda: _container("screw"),
    "container_rectangular": lambda: _container("push", "rectangular"),
    "corner_chamfer": lambda: _worked_corner(False),
    "corner_fillet": lambda: _worked_corner(True),
    "curved_mouth": _curved_mouth,
    "differently_split_contact_edge": _differently_split_contact_edge,
    "drill_hole": _drilled_along_the_face,
    "fill_band": _bore_wall_band,
    "fill_bridged": _top_with_holes,
    "import_repair": _mended_import,
    "inverted_hollow": _inverted_hollow,
    "orient_for_print": lambda: _oriented_plate(True),
    "orient_heuristic": lambda: _oriented_plate(False),
    "pattern_facets": _aligned_pattern_facets,
    "pattern_facets_tilted": lambda: _aligned_pattern_facets(True),
    "pose_armature": _posed_plate,
    "turned_closures": _turned_closures,
    "prusa_support_angle": _automatic_support_angle,
    "remesh_mesh": _refined_plate,
    "rebuild_box": _rebuilt_box,
    "repair_selfint": _resolved_crossings,
    "resize_hole": _changed_bore,
    "rotate_object": _turned_plate,
    "section_cut": _slanted_cut,
    "step_assembly": _step_assembly,
    "tangential_rounds": _tangential_rounds,
    "thicken": _thickened_skin,
    "support_columns": _support_columns,
}


@pytest.mark.parametrize("way", sorted(_WAYS))
def test_a_way_through_the_kernel_does_not_hang_on_the_machine(way: str) -> None:
    """Derselbe Weg mit und ohne Plattformrauschen — derselbe Fingerabdruck.

    **Der Anlass ist der Änderungsweg aus RM-187**: Am 17.09.2026 trug die
    geänderte Senkbohrung auf Windows, Ubuntu und macOS drei verschiedene
    Fingerabdrücke, und die Bohrungskette zerfiel auf dem Mac. Nach der
    Umstellung der Kreispunkte blieb eine letzte Stelle offen, und dieser Test
    hat sie auf einer einzigen Maschine gefunden: Die Ebene einer schrägen
    Mündung kam aus ``np.linalg.svd`` (``prepare_ops._bore_end_planes``), ihre
    Lage aus ``np.dot`` (``prepare.resize_bore``). Rot war er außerdem für
    *Drehen*, *Druckoptimal ausrichten*, den schrägen Schnitt, *An Merkmal
    ausrichten*, *Stellung geben* und *Offene Fläche schließen* (22.09.2026).
    """
    quiet = _WAYS[way]()
    with platform_noise():
        noisy = _WAYS[way]()

    assert noisy == quiet, f"{way} hängt an einer plattformabhängigen Rechnung"


def test_the_noise_reaches_what_it_should() -> None:
    """Die Gegenprobe: Das Rauschen trifft, was eine andere Maschine anders rechnet.

    Ohne sie wäre der Test darüber auch mit einem Rauschen grün, das nichts
    ändert — eine Zusicherung über die leere Menge.
    """
    values = np.array([0.1, 0.2, 0.3, 0.7])

    def asked() -> tuple[float, float, float]:
        return (
            float(np.dot(values, values[::-1])),
            math.cos(0.3),
            float(np.linalg.norm(values)),
        )

    quiet = asked()
    with platform_noise():
        noisy = asked()
        exact = (float(np.dot([0.0, 0.0, 1.0], [2.5, 3.5, 4.25])), math.cos(0.0))

    assert noisy != quiet
    assert exact == (4.25, 1.0), "was überall exakt ist, bekommt kein Rauschen"


def platform_fingerprints() -> dict[str, str]:
    """Alle Wege auf einmal — für den Vergleich über zwei BLAS-Kerne."""
    return {way: _WAYS[way]() for way in sorted(_WAYS)}


def test_a_way_through_the_kernel_does_not_follow_the_blas_kernel() -> None:
    """Dieselben Wege mit einem anderen BLAS-Kern — dieselben Fingerabdrücke.

    ``@`` lässt sich nicht verrauschen, aber der Kern lässt sich tauschen:
    OpenBLAS wählt ihn nach der CPU und nimmt mit ``OPENBLAS_CORETYPE`` einen
    anderen. ``Nehalem`` rechnet ohne AVX und ohne FMA — gemessen ändert das
    Matrixprodukte, ``rotation_about`` bis zum 22.09.2026 eingeschlossen.
    Wo NumPy nicht auf OpenBLAS steht (Accelerate auf dem Mac) oder die CPU
    kein x86 ist, gibt es diesen Kern nicht, und der Test sagt es.
    """
    blas = str(np.show_config(mode="dicts")["Build Dependencies"]["blas"]["name"])
    if "openblas" not in blas.lower() or platform.machine().lower() not in ("x86_64", "amd64"):
        pytest.skip(f"kein austauschbarer OpenBLAS-Kern ({blas}, {platform.machine()})")
    here = platform_fingerprints()
    root = str(Path(__file__).resolve().parents[1])
    script = (
        "import json, sys\n"
        "sys.path.insert(0, sys.argv[1])\n"
        "from tests.test_platform_identity import platform_fingerprints\n"
        "print(json.dumps(platform_fingerprints()))\n"
    )
    finished = subprocess.run(
        [sys.executable, "-c", script, root],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=dict(os.environ, OPENBLAS_CORETYPE="Nehalem", PYTHONUTF8="1"),
        cwd=root,
        timeout=600,
        check=False,
    )
    assert finished.returncode == 0, finished.stderr[-2000:]

    assert json.loads(finished.stdout.strip().splitlines()[-1]) == here


def test_a_pocket_circle_takes_the_same_corners_as_the_lathe() -> None:
    """Der Kreis, den eine Tasche oder ein Feld ins Netz schneidet (RM-187).

    ``sketch_solid.outline_points`` rechnete seine 72 Ecken über
    ``math.cos(2π·i/72)`` — gemessen am 22.09.2026 trugen 62 davon eine andere
    letzte Stelle als die exakte Teilung, und ``math.cos`` hängt an der
    Mathematikbibliothek der Maschine. Jetzt ist es dieselbe Tafel wie beim
    Drehkörper, Bit für Bit.
    """
    from app.core.geom.sketch_solid import ARC_STEPS, outline_points
    from app.core.sketch.profile import Profile

    ring = outline_points(Profile(circle=((1.25, -2.5), 7.5)))
    table = lathe.circle_points(sections=ARC_STEPS, radius=7.5, centre=(1.25, -2.5))

    assert fingerprint(ring) == fingerprint(table)


def test_a_mirrored_revolve_still_points_outward() -> None:
    """Eine Spiegelung dreht auch den Umlaufsinn, nicht nur die Ecken.

    ``revolve(transform=…)`` setzte allein die Ecken; ``apply_transform``, das
    hier ersetzt worden war, drehte bei einer Spiegelung auch die Dreiecke um.
    Ohne das zeigte der Körper nach innen, und sein Volumen war negativ.
    """
    outline = np.array([[0.0, 0.0], [4.0, 0.0], [4.0, 6.0], [0.0, 6.0]], dtype=np.float64)
    mirror = np.diag([-1.0, 1.0, 1.0, 1.0])

    body = lathe.revolve(outline, sections=48, transform=mirror)

    assert body.volume > 0.0
    assert body.is_winding_consistent
