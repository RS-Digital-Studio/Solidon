"""Helfer, die mehr als eine Testdatei braucht — eine Quelle statt Querimporten.

Bis zum 21.09.2026 holten sich Testdateien ihre Prüfkörper und Wächter
gegenseitig aus privaten Namen (``from tests.test_torus_feature_ops import
_ridged_shaft``): Wer die Quelle umbaute, brach den Nachbarn, und wer den
Helfer suchte, fand ihn in der Datei, die ihn zufällig zuerst brauchte. Was
mehr als eine Datei liest, steht hier — öffentlich benannt und ohne
Testfunktion daneben, damit pytest die Datei nicht als Test sammelt.

Hier liegt nur, was **keinen** Fensteraufbau braucht: Ein Helfer, der Qt
zieht, gehört nicht in eine Datei, die auch Kerntests importieren.

**Noch nicht hier, weil ihre Quelldateien anderen Umbauten gehören**
(Stand 21.09.2026): ``test_thread_feature_ops._studded_plate``/``_tapped_plate``
(``test_filament_on_rings_and_threads``), ``test_cache.FakeCodec``
(``test_native_references``), ``test_features._small_faces``/
``_stud_on_a_plate``/``_plate_with_a_chamfered_slot`` (``test_local_detection``,
``test_round_surface_measurements``, ``test_surface_patches``),
``test_slot_features.a_foreign_slot``, ``test_local_detection.blind_cylinder``/
``bore_seed``, ``test_outline_dialog._until`` (Fensterdateien) und
``test_partial_bores._exact_kernel`` — dieselbe Frage wie :func:`exact_kernel`
hier, dort noch als eigene Kopie.
"""

from __future__ import annotations

import dataclasses
import math
import struct
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import trimesh

from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.scene import History, OperationDraft
from app.core.scene.project import Project, new_project
from app.core.types import (
    BoundingBox,
    Feature,
    OpResult,
    Profile,
    Quality,
    SceneObject,
    Source,
)

MESHES = Path(__file__).parent / "data" / "meshes"


def exact_kernel() -> Any:
    """Überspringt ohne OpenCASCADE und gibt sonst ``app.core.brep.edit`` zurück.

    Der Wächter steht **vor** jedem ``OCP``-Import einer Testfunktion: Ein
    Quellklon ohne das Extra ``brep`` bekam sonst einen ``ImportError`` statt
    eines Skips — und in der CI, die das Extra in jedem Lauf installiert,
    macht ``tests/conftest.py`` aus dem fehlenden Kern einen Fehler, damit
    sich die zweiunddreißig Dateien des exakten Kerns dort nie still
    verabschieden.
    """
    kernel = pytest.importorskip("app.core.brep.kernel")
    if not kernel.available():
        pytest.skip("ohne OpenCASCADE gibt es den exakten Kern nicht")
    from app.core.brep import edit

    return edit


# --- Platzhalter für Szene und Cache ------------------------------------------------


@dataclasses.dataclass(frozen=True, slots=True)
class FakeMesh:
    """Ein Netz-Platzhalter mit festen Kennzahlen."""

    triangles: int = 12
    vertices: int = 8
    size: tuple[float, float, float] = (10.0, 10.0, 10.0)
    watertight: bool = True
    components: int = 1
    slots: tuple[int, ...] = dataclasses.field(default_factory=tuple)

    @property
    def vertex_count(self) -> int:
        return self.vertices

    @property
    def triangle_count(self) -> int:
        return self.triangles

    @property
    def bounds(self) -> BoundingBox:
        return BoundingBox(minimum=(0.0, 0.0, 0.0), maximum=self.size)

    @property
    def volume(self) -> float:
        return self.size[0] * self.size[1] * self.size[2]

    @property
    def area(self) -> float:
        width, depth, height = self.size
        return 2 * (width * depth + width * height + depth * height)

    @property
    def is_watertight(self) -> bool:
        return self.watertight

    @property
    def component_count(self) -> int:
        return self.components

    @property
    def slot_indices(self) -> Sequence[int]:
        return self.slots


def make_object(object_id: str = "obj_1", name: str = "Teil", **kwargs: object) -> SceneObject:
    """Ein Szenenobjekt auf einem :class:`FakeMesh` mit den genannten Kennzahlen."""
    return SceneObject(id=object_id, name=name, mesh=FakeMesh(**kwargs))  # type: ignore[arg-type]


# --- Der Schaft mit dem Ring (Wulst oder Kehle) -----------------------------------

#: Schaft Ø 20 auf 40, der Ring R 10 / r 3 in halber Höhe — die Prüfkörper der
#: Torusmerkmale (``test_torus_feature_ops``) und des Filaments darauf
#: (``test_filament_on_rings_and_threads``).
SHAFT_RADIUS = 10.0
SHAFT_HEIGHT = 40.0
TUBE_RADIUS = 3.0
SHAFT_VOLUME = math.pi * SHAFT_RADIUS**2 * SHAFT_HEIGHT


def ridged_shaft(kind: str, *, recess: bool) -> SceneObject:
    """Schaft Ø 20 × 40 mit einem Ring R 10 / r 3 in halber Höhe — Wulst oder Kehle.

    Gebaut wird exakt, auch für ``kind="mesh"``: Das Netz ist die Tessellation
    desselben Körpers, damit beide Kerne dieselbe Geometrie sehen. Ohne
    OpenCASCADE gibt es deshalb auch den Netzfall nicht (:func:`exact_kernel`).
    """
    edit = exact_kernel()
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCylinder, BRepPrimAPI_MakeTorus
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    from app.core.brep.features import features_of
    from app.core.brep.kernel import Solid
    from app.core.perceive.features import detect

    shaft = Solid(BRepPrimAPI_MakeCylinder(SHAFT_RADIUS, SHAFT_HEIGHT).Shape())
    ring = Solid(
        BRepPrimAPI_MakeTorus(
            gp_Ax2(gp_Pnt(0.0, 0.0, SHAFT_HEIGHT / 2.0), gp_Dir(0.0, 0.0, 1.0)),
            SHAFT_RADIUS,
            TUBE_RADIUS,
        ).Shape()
    )
    body = edit.unified(edit.boolean("difference" if recess else "union", [shaft, ring]))
    if kind == "brep":
        return SceneObject(
            id="obj_1", name="Schaft", mesh=body, kind="brep", features=features_of(body)
        )
    mesh = as_mesh_data(body)
    return SceneObject(id="obj_1", name="Schaft", mesh=mesh, kind="mesh", features=detect(mesh))


def the_torus(entry: SceneObject) -> Feature:
    """Das eine Torusmerkmal des Körpers — und die Zusicherung, dass es eines ist."""
    found = [feature for feature in entry.features.values() if feature.kind == "torus"]
    assert len(found) == 1, sorted((f.id, f.kind) for f in entry.features.values())
    return found[0]


# --- Der Laufzeitkern eines AppImage ------------------------------------------------


def tiny_elf_kernel(digest: bytes, body: bytes) -> bytes:
    """Ein kleinstes ELF64 mit ``.digest_md5`` und der Abschnittstabelle am Ende.

    So liegt der AppImage-Laufzeitkern vor dem Dateisystemabbild; die Länge
    liest ``make_sbom.appimage_runtime_sha256`` aus dem Kopf
    (``test_sbom``, ``test_release_evidence``).
    """
    names = b"\0.digest_md5\0.shstrtab\0"
    data = digest + body
    table = 64 + len(data) + len(names)
    header = bytearray(64)
    header[:6] = b"\x7fELF\x02\x01"
    struct.pack_into("<Q", header, 0x28, table)
    struct.pack_into("<HHH", header, 0x3A, 64, 3, 2)
    sections = [
        bytes(64),
        struct.pack("<IIQQQQIIQQ", 1, 1, 0, 0, 64, 16, 0, 0, 1, 0),
        struct.pack("<IIQQQQIIQQ", 13, 3, 0, 0, 64 + len(data), len(names), 0, 0, 1, 0),
    ]
    return bytes(header) + data + names + b"".join(sections)


# --- Das Startprojekt von Weg 1 -------------------------------------------------


def plate_project() -> Project:
    """Ein Projekt mit der Lochplatte auf dem Stapel — der Startpunkt von Weg 1.

    Stand wortgleich in ``test_agent``, ``test_agent_suite``,
    ``test_licence_boundary`` und ``test_parts`` (RM-134, gemessen mit
    ``tools/twin_scan.py`` am 22.09.2026).
    """
    made = new_project("centauri-carbon-2", "petg")
    made.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/plate_holes.stl", sha256=""
    )
    made.sources["src_1"] = (MESHES / "plate_holes.stl").read_bytes()
    History(made.document).apply(
        "Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
    )
    return made


# --- Eine Fläche in fremder Lage ------------------------------------------------


def placed(body: trimesh.Trimesh, scale: float, angle: float) -> trimesh.Trimesh:
    """Eine starre Lage und ein einheitlicher Maßstab für dieselbe Fläche.

    Die Passungsprüfungen für Kegel und Torus (``test_cone_fit_quality``,
    ``test_torus_fit_quality``) fragen, ob ihr Urteil Lage und Maßstab
    übersteht — mit derselben Drehachse, damit beide dasselbe prüfen.
    """
    result = body.copy()
    result.apply_scale(scale)
    result.apply_transform(
        trimesh.transformations.rotation_matrix(
            math.radians(angle),
            direction=(0.3, -0.8, 0.5),
            point=(0.0, 0.0, 0.0),
        )
    )
    result.apply_translation((37.0, -19.0, 83.0))
    return result


# --- Offene Netze nach dem 22.09.2026 -----------------------------------------------


def keep_imports_open(monkeypatch: pytest.MonkeyPatch, session: Any) -> None:
    """Der Import lässt offene Netze offen — wie vor ``ed233f2c`` (22.09.2026).

    Seit diesem Tag schließt ``loader.normalise`` jedes offene Netz, das es
    verschweißen kann (Robert: „Der Import schließt, was offen ist, statt
    darüber zu berichten"). Die Oberfläche kennt den offenen Körper trotzdem
    weiter: Er entsteht, wo die Reparatur eine Öffnung nicht füllen kann, und
    dort müssen *Offene Fläche schließen*, der Satz im Vorschauband und der
    Reparaturweg im Prüfbericht genauso wirken wie vorher. Die Testnetze
    schließt die Reparatur dagegen restlos — ohne diesen Schalter gäbe es in
    der Suite keinen offenen Körper mehr, an dem sich das prüfen ließe.

    Abgeschaltet wird nur das Schließen der Leseoperation (``mend=False``),
    nicht die Reparatur als Operation — und zwar **gegen** das, was die
    Leseoperation übergibt: Seit ``2b83f72a5`` reicht sie ``mend`` aus ihrem
    Parameter selbst weiter (RM-241), und ein ``partial(..., mend=False)``
    wurde davon still überschrieben; vier Fenstertests bekamen danach einen
    geschlossenen Körper. **Und die Sitzung bekommt einen eigenen
    Cache nur im Speicher:** Der Plattencache der Suite ist prozessweit, und
    ein früherer Test hat dieselbe Datei vielleicht schon geschlossen
    eingelesen — sein Ergebnis käme sonst aus dem Cache statt aus der
    Leseoperation.
    """
    from app.core.ingest import loader, ops
    from app.core.scene.cache import ResultCache

    def left_open(*args: Any, **kwargs: Any) -> Any:
        return loader.normalise(*args, **{**kwargs, "mend": False})

    monkeypatch.setattr(ops, "normalise", left_open)
    session.cache = ResultCache()


def fill_only_small_holes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Das Löcherschließen der Reparatur erreicht nur Ringe aus drei und vier Kanten.

    Bis zum 22.09.2026 war das die ganze Reparatur (``trimesh.repair.fill_holes``);
    seither füllt ``repair.fill_boundary_loops`` jede Öffnung, die eine Fläche
    tragen kann. Eine Reparatur, die nicht alles schließt, gibt es trotzdem —
    an Rändern, die sich selbst berühren oder auf verzweigten Kanten liegen.
    Die Testnetze haben solche Ränder nicht; dieser Schalter stellt den
    Teilerfolg nach, damit sein Weg durch die Oberfläche (Restbefund, *Stellen
    zeigen*, kein Reparaturring) geprüft bleibt.

    Ersetzt wird ``_filled_rounds``, die Runden des Ringfüllers: Seit
    ``2b83f72a5`` ruft die Reparatur sie direkt und nicht mehr über
    ``_filled_with_count``; der alte Schalter griff danach ins Leere, und die
    Reparatur schloss alles. ``fill_holes`` geht weiter über denselben Weg.
    """
    import trimesh

    from app.core.geom import repair

    def rings(mesh: Any) -> int:
        return len(mesh.raw.outline().entities) if repair.open_edge_count(mesh) else 0

    def filled(mesh: Any, cancelled: Any = None, *, keep_wide: bool = False) -> Any:
        if not repair.open_edge_count(mesh):
            return repair._Filled(mesh)
        raw = mesh.raw.copy()
        trimesh.repair.fill_holes(raw)
        result = mesh.replacing(raw)
        return repair._Filled(result, closed=max(0, rings(mesh) - rings(result)))

    monkeypatch.setattr(repair, "_filled_rounds", filled)


# --- Die schräge Senkbohrung (RM-187) ----------------------------------------------
#
# Der Prüfkörper des Änderungswegs: ``test_bore_mouth_resize`` ändert ihn auf
# jede Art, ``test_platform_identity`` hält fest, dass dabei auf jeder Maschine
# dieselben Bits herauskommen. Die Sonden unter
# ``.claude/.state/plattformgleichheit-2026-09-17`` lesen ihn weiter über die
# alten Namen in ``test_bore_mouth_resize``.


def sloping_bore() -> tuple[MeshData, dict[str, Feature], Feature]:
    """Eigene Reproduktion: Ø9, schräge Senkung Ø11 und Nachbarloch Ø9,5.

    Alle Punkte werden hier aus festen Maßen konstruiert. Der Boden liegt
    bei z=3+0,04*x, der Zylinder endet bei z=17+0,10*x und die Senkung an der
    schrägen Außenfläche z=18+0,08*x. Kein Dreieck stammt aus einer Kundendatei.
    """
    from app.core import units
    from app.core.deferred import trimesh
    from app.core.geom import lathe
    from app.core.geom.boolean import boolean
    from app.core.geom.mesh import MeshData
    from app.core.perceive.features import detect

    sections = 120
    # **Über ``circle_cos_sin`` und nicht über ``np.cos``** (17.09.2026,
    # RM-187): Dieser Test prüft die Erkennung, nicht die Mathematikbibliothek.
    # Mit ``np.cos`` baute er auf jeder Plattform ein anderes Eingangsnetz —
    # 1224 Dreiecke auf Ubuntu, 1226 auf Windows, 1228 auf macOS —, und was er
    # danach maß, war nicht mehr dieselbe Frage. Auf dem Mac zerfiel darüber
    # die Bohrungskette, und drei Reparaturen suchten den Fehler in der
    # Erkennung, wo keiner war.
    table = np.asarray(units.circle_cos_sin(sections), dtype=float)
    vertices = []
    for radius, height, slope in ((4.5, 3.0, 0.04), (4.5, 17.0, 0.10), (5.5, 18.0, 0.08)):
        x, y = radius * table[:, 0], radius * table[:, 1]
        vertices.extend(zip(x, y, height + slope * x, strict=True))
    faces = []
    for ring in range(2):
        for at in range(sections):
            following = (at + 1) % sections
            lower, upper = ring * sections, (ring + 1) * sections
            faces.extend(
                (
                    (lower + at, lower + following, upper + following),
                    (lower + at, upper + following, upper + at),
                )
            )
    for ring, height in ((0, 3.0), (2, 18.0)):
        hub = len(vertices)
        vertices.append((0.0, 0.0, height))
        for at in range(sections):
            faces.append((ring * sections + at, ring * sections + (at + 1) % sections, hub))
    cavity = trimesh.Trimesh(vertices=vertices, faces=faces, process=True)
    trimesh.repair.fix_normals(cavity)
    # Verschoben wird elementweise und nicht über ``apply_translation``: Das
    # geht als Matrixprodukt durch BLAS, und dieser Weg ist der Prüfstand für
    # „dieselben Bits auf jeder Maschine" (RM-187, ``test_platform_identity``).
    stock = trimesh.creation.box(extents=(34.0, 26.0, 18.0))
    points = np.asarray(stock.vertices) + np.array([5.0, 0.0, 9.0])
    top = points[:, 2] > 9.0
    points[top, 2] += 0.08 * points[top, 0]
    stock.vertices = points
    neighbour = lathe.cylinder(radius=4.75, height=20.0, sections=120)
    neighbour.vertices = np.asarray(neighbour.vertices) + np.array([12.0, 0.0, 13.0])
    mesh = boolean(
        "difference",
        [MeshData.of(stock), MeshData.of(cavity), MeshData.of(neighbour)],
        quality="fine",
    ).mesh
    features = detect(mesh)
    hole = min(
        (feature for feature in features.values() if feature.kind == "hole"),
        key=lambda feature: abs(float(feature.params["centre"][0])),
    )
    return mesh, features, hole


def feature_operation(
    name: str,
    mesh: MeshData,
    features: dict[str, Feature],
    feature: Feature,
    profile: Profile,
    *,
    quality: Quality = "fine",
    **params: object,
) -> OpResult:
    """Eine Merkmalsoperation durch ihren registrierten Kundenvertrag auswerten."""
    from app.core.registry import REGISTRY
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene

    source = SceneObject(id="obj_1", name="Bohrungsprüfung", mesh=mesh, features=features)
    spec = REGISTRY.get(name)
    return spec.fn(
        OpContext(
            scene=Scene(objects={source.id: source}),
            inputs=[source],
            params=spec.params(at_feature=feature.id, **params),
            profile=profile,
            quality=quality,
            seed=20260915,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def contains(mesh: MeshData, points: Any) -> np.ndarray:
    """Innen/Außen unabhängig aus der Summe der orientierten Raumwinkel.

    Für ein geschlossenes Netz ist die Summe an einem Punkt innen ±4π, außen 0 —
    ohne Strahlen und ohne ``rtree``, das die Umgebung nicht mitbringt.
    """
    inside = []
    for point in np.asarray(points, dtype=float).reshape(-1, 3):
        directions = np.asarray(mesh.raw.triangles) - point
        directions /= np.linalg.norm(directions, axis=2)[:, :, None]
        first, second, third = directions.transpose(1, 0, 2)
        numerator = np.einsum("ij,ij->i", first, np.cross(second, third))
        denominator = (
            1.0
            + np.einsum("ij,ij->i", first, second)
            + np.einsum("ij,ij->i", second, third)
            + np.einsum("ij,ij->i", third, first)
        )
        angle = 2.0 * np.arctan2(numerator, denominator).sum()
        inside.append(abs(angle) > 2.0 * np.pi)
    return np.asarray(inside)


def at_the_start_rule(profile: Profile) -> Profile:
    """Derselbe Drucker mit der Überhang-Startregel (45 Grad) statt der Grenze
    seines Herstellers.

    Für Tests, deren Sollwerte vor dem 27.09.2026 an der Startregel gemessen
    sind und die etwas anderes prüfen als den Winkel — eine Standfläche, eine
    Stiftzuordnung. Am Centauri Carbon 2 gilt seither 60 Grad, und dieselbe
    Geometrie braucht dort weniger Stütze; das ist richtig und nicht die Frage
    dieser Tests.
    """
    printer = dataclasses.replace(profile.printer, overhang_limit=None)
    return dataclasses.replace(profile, printer=printer)
