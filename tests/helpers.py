"""Helfer, die mehr als eine Testdatei braucht — eine Quelle statt Querimporten.

Bis zum 21.09.2026 holten sich Testdateien ihre Prüfkörper und Wächter
gegenseitig aus privaten Namen (``from tests.test_torus_feature_ops import
_ridged_shaft``): Wer die Quelle umbaute, brach den Nachbarn, und wer den
Helfer suchte, fand ihn in der Datei, die ihn zufällig zuerst brauchte. Was
mehr als eine Datei liest, steht hier — öffentlich benannt und ohne
Testfunktion daneben, damit pytest die Datei nicht als Test sammelt.

Hier liegt nur, was **keinen** Fensteraufbau braucht: Ein Helfer, der Qt
zieht, gehört nicht in eine Datei, die auch Kerntests importieren; der steht
in ``tests/ui_helpers.py``.

Eine Fixture, die mehrere Dateien teilen (``project``), steht hier einmal und
wird mit ``from tests.helpers import project as project`` eingebunden: pytest
findet sie im Namensraum der Testdatei, und der doppelte Name sagt ruff, dass
der Import weitergereicht und nicht vergessen ist.
"""

from __future__ import annotations

import dataclasses
import hashlib
import http.server
import io
import json
import math
import os
import shutil
import socketserver
import struct
import subprocess
import time
import zipfile
from collections.abc import Callable, Iterator, Sequence
from contextlib import contextmanager
from datetime import date
from functools import cache
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

import numpy as np
import pytest
import trimesh

from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.geom.transform import place_on_bed
from app.core.scene import History, OperationDraft
from app.core.scene.project import Project, new_project
from app.core.types import (
    BoundingBox,
    Document,
    Feature,
    Finding,
    Mesh,
    Operation,
    OpResult,
    Parameter,
    Profile,
    Quality,
    SceneObject,
    Sketch,
    SketchConstraint,
    SketchElement,
    Source,
)

MESHES = Path(__file__).parent / "data" / "meshes"

#: Profil (Radius, Höhe) um die Z-Achse in einer Platte 44 mal 24 mal 12 mit
#: einer Bohrung Ø 6, die sich unten und oben weitet.
BOTH_ENDS: dict[str, list[tuple[float, float]]] = {
    "Zylindersenkung und Fase": [
        (0, 0),
        (5, 0),
        (5, 6),
        (3, 6),
        (3, 11),
        (4, 12),
        (0, 12),
        (0, 0),
    ],
    "Fase beidseitig": [(0, 0), (4, 0), (3, 1), (3, 11), (4, 12), (0, 12), (0, 0)],
    "Stufen beidseitig": [
        (0, 0),
        (5, 0),
        (5, 3),
        (3, 3),
        (3, 9),
        (4.5, 9),
        (4.5, 12),
        (0, 12),
        (0, 0),
    ],
}


def exact_kernel() -> Any:
    """Überspringt ohne OpenCASCADE und gibt sonst ``app.core.brep.edit`` zurück.

    Der Wächter steht **vor** jedem ``OCP``-Import, auch am Modulanfang: Ein
    Quellklon ohne das Extra ``brep`` überspringt den Test. Das eigene
    Kernelmodul wird regulär importiert, damit ein Importfehler darin nicht
    wie ein fehlendes optionales Paket als Skip aussieht. In der CI, die das
    Extra in jedem Lauf installiert, macht ``tests/conftest.py`` aus dem
    fehlenden Kern einen Fehler, damit sich die Dateien des exakten Kerns
    dort nie still verabschieden.
    """
    from app.core.brep import kernel

    if not kernel.available():
        pytest.skip("ohne OpenCASCADE gibt es den exakten Kern nicht", allow_module_level=True)
    from app.core.brep import edit

    return edit


def open_box() -> Any:
    """Ein Quader 40 × 30 × 20 ohne Deckel: fünf vernähte Flächen, vier freie Randkanten."""
    edit = exact_kernel()
    from OCP.BRepBuilderAPI import BRepBuilderAPI_Sewing
    from OCP.TopAbs import TopAbs_FACE
    from OCP.TopExp import TopExp_Explorer

    from app.core.brep.kernel import Solid
    from app.core.units import EPS_GEOM

    sewing = BRepBuilderAPI_Sewing(EPS_GEOM)
    faces = TopExp_Explorer(edit.box(40.0, 30.0, 20.0).shape, TopAbs_FACE)
    kept = 0
    while faces.More():
        if kept < 5:
            sewing.Add(faces.Current())
        kept += 1
        faces.Next()
    sewing.Perform()
    return Solid(sewing.SewedShape())


def walled_bin() -> MeshData:
    """Ein Kasten 40 × 30 × 20 mit 2 mm Wand und Boden, oben offen: innen 36 × 26 × 18.

    Die Kammer der Gruppentests (RM-184) — Erkennung, *Kammer ändern*, Baum und
    Merkmalfenster fragen denselben Körper.
    """
    from app.core.geom.boolean import boolean

    outer = trimesh.creation.box(extents=(40.0, 30.0, 20.0))
    outer.apply_translation((0.0, 0.0, 10.0))
    inner = trimesh.creation.box(extents=(36.0, 26.0, 20.0))
    inner.apply_translation((0.0, 0.0, 12.0))
    return boolean("difference", [MeshData.of(outer), MeshData.of(inner)]).mesh


#: Die Maße des Puppenhauses aus dem Dateiaudit (§4): Länge und Breite lasen nur den Boden.
DOLLHOUSE: dict[str, float] = {
    "haus_laenge": 180.0,
    "haus_breite": 120.0,
    "wand": 3.0,
    "etage": 90.0,
    "boden": 4.0,
    "fenster": 30.0,
    "tuer_breite": 34.0,
    "tuer_hoehe": 60.0,
}


def rectangle_ring(outer: tuple[float, float], inner: tuple[float, float]) -> str:
    """Zwei achsparallele Rechtecke um den Ursprung als freie Linien — der Wandring des Audits.

    ``outer`` und ``inner`` sind halbe Breite und halbe Höhe.
    """
    from app.core.sketch.serialize import sketch_to_text
    from app.core.types import Sketch, SketchElement

    elements = []
    for half_x, half_y in (outer, inner):
        corners = [(-half_x, -half_y), (half_x, -half_y), (half_x, half_y), (-half_x, half_y)]
        for index, corner in enumerate(corners):
            elements.append(SketchElement("line", (corner, corners[(index + 1) % 4])))
    return sketch_to_text(Sketch(plane="plane:xy", elements=tuple(elements)))


def dollhouse_document(document: Any) -> Any:
    """Das Puppenhaus des Dateiaudits als Stapel: Boden gebunden, Wandring und Fenster fest."""
    from app.core.types import Operation, Parameter

    document.parameters = {
        name: Parameter(name=name, value=value) for name, value in DOLLHOUSE.items()
    }
    document.ops = [
        Operation(
            id=1,
            op="sketch_extrude",
            params={
                "shape": "rectangle",
                "length": "@haus_laenge",
                "width": "@haus_breite",
                "height": "@boden",
                "name": "Boden",
            },
            outputs=("obj_1",),
        ),
        Operation(
            id=2,
            op="sketch_extrude",
            params={
                "sketch": rectangle_ring((90.0, 60.0), (87.0, 57.0)),
                "height": "@etage",
                "name": "Wandring",
            },
            outputs=("obj_2",),
        ),
        Operation(
            id=3,
            op="sketch_pocket",
            inputs=("obj_2",),
            outputs=("obj_2",),
            params={
                "shape": "rectangle",
                "length": 30.0,
                "width": 30.0,
                "through": True,
                "x": -50.0,
                "y": -58.5,
                "z": 45.0,
            },
        ),
    ]
    return document


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


class FakeCodec:
    """Steht für die Geometrieschicht, die den echten später liefert.

    Schreibt nur die Kennzahlen eines :class:`FakeMesh` und liest sie als
    solches zurück: Die Tests des Plattencaches prüfen Ablage, Budget und
    Wiederherstellung, nicht das Netzformat.
    """

    suffix = ".json"

    def stores(self, mesh: Mesh) -> bool:
        return True

    def dumps(self, mesh: Mesh) -> bytes:
        source = mesh  # type: ignore[assignment]
        return json.dumps(
            {
                "triangles": source.triangle_count,
                "vertices": source.vertex_count,
                "size": list(source.bounds.size),
            }
        ).encode("utf-8")

    def loads(self, data: bytes) -> Mesh:
        values = json.loads(data)
        return FakeMesh(  # type: ignore[return-value]
            triangles=values["triangles"],
            vertices=values["vertices"],
            size=tuple(values["size"]),
        )


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


@pytest.fixture
def project() -> Project:
    """Ein Projekt mit einer Platte auf dem Stapel — der Startpunkt von Weg 1.

    Je Test frisch gebaut (:func:`plate_project`), eingebunden mit
    ``from tests.helpers import project as project``.
    """
    return plate_project()


def rounded_pattern_carrier(*, tilted: bool = False) -> SceneObject:
    """96 Zylinderfacetten mit geteilten Kanten nach float32 wie in einer STL.

    Der Träger Ø 40 × 16 wird für die Ausrichtung isoliert: Das Muster nennt
    seine gemessene Lage, seine Zellen braucht erst der separate Operationstest.
    Ein ferner, ebenfalls verfeinerter Quader belegt unberührte Herkunft.
    """
    from app.core.geom import lathe, transform
    from app.core.geom.mesh import remember_refined_units, stable_normals

    cylinder = lathe.cylinder(radius=20.0, height=16.0, sections=96)
    cylinder.vertices = np.asarray(cylinder.vertices) + np.array([0.0, 0.0, 8.0])
    vertices, faces = trimesh.remesh.subdivide(cylinder.vertices, cylinder.faces)
    cylinder = trimesh.Trimesh(vertices.astype(np.float32).astype(np.float64), faces, process=False)
    side_faces = np.flatnonzero(np.abs(stable_normals(cylinder)[0][:, 2]) < 0.5)
    far = trimesh.creation.box(extents=(4.0, 6.0, 8.0))
    far.vertices = np.asarray(far.vertices) + np.array([60.0, 0.0, 4.0])
    far_vertices, far_faces = trimesh.remesh.subdivide(far.vertices, far.faces)
    far = trimesh.Trimesh(far_vertices, far_faces, process=False)
    body = trimesh.util.concatenate((cylinder, far))
    matrix = (
        transform.rotation_about((0.3, 0.5, 0.8), (0.0, 0.0, 0.0), 31.0) if tilted else np.eye(4)
    )
    body.vertices = transform.moved_points(np.asarray(body.vertices), matrix)
    axis = tuple(transform.turned(np.array([0.0, 0.0, 1.0]), matrix))
    normal = tuple(transform.turned(np.array([1.0, 0.0, 0.0]), matrix))
    centres = transform.moved_points(np.array([[0.0, 0.0, 8.0], [20.0, 0.0, 8.0]]), matrix)
    origins = np.arange(len(body.faces), dtype=np.int64) // 4
    remember_refined_units(body, origins)
    carrier = Feature(
        id="pin_1",
        kind="pin",
        provenance="detected",
        face_indices=tuple(side_faces),
        params={"axis": axis, "centre": tuple(centres[0]), "diameter": 40.0},
    )
    pattern = Feature(
        id="pattern_1",
        kind="pattern",
        provenance="detected",
        params={
            "carrier": "cylinder",
            "carrier_axis": axis,
            "carrier_diameter": 40.0,
            "normal": normal,
            "centre": tuple(centres[1]),
        },
    )
    return SceneObject(
        id="obj_1",
        name="Facettenträger",
        mesh=MeshData.of(body, slots=tuple(origins % 3)),
        features={carrier.id: carrier, pattern.id: pattern},
    )


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


# --- Eine gespiegelte Figur, deren Naht neben der Mitte steht -----------------------

#: Wie weit die Ecken der Spiegelnaht neben der Ebene stehen, als Anteil der
#: Spanne, in der ``trimesh`` eine Ecke zur Schnittebene zählt
#: (``section._ON_PLANE``): alle darin, beide Vorzeichen, keines null.
SEAM_NOISE = (0.6, -0.7, 0.9, -0.2, 0.3)


def mirror_seam_sphere(level: float) -> MeshData:
    """Kugel R 20, spiegelsymmetrisch zu ``z = level``; die Ecken ihrer Naht in
    der Spiegelebene stehen Milliardstel Millimeter daneben.

    So kommt eine gespiegelt modellierte Figur aus einer STL: Die Ecken ihrer
    Mittelnaht tragen in float32 Reste wie 2⁻³⁴ statt null, und nach *Auf Maß
    bringen* stehen sie Milliardstel Millimeter neben der Mitte des
    Hüllquaders — genau dort, wo *Teilen* seine Ebene vorschlägt. An Bob
    (CC0, 10 688 Dreiecke) liegen dort 69 Ecken genau auf der Ebene und 26
    bis 1e-8 mm daneben. Die Icosphere hat ihre Naht in ``z = 0`` (die Ecken
    ``(±1, ±φ, 0)`` und die Teilungspunkte ihrer Kanten) und Dreiecke, die mit
    einer Ecke darauf von einer Seite zur anderen reichen
    (``test_section``, ``test_prepare``).
    """
    from app.core.geom import section

    sphere = trimesh.creation.icosphere(subdivisions=3, radius=20.0)
    vertices = np.array(sphere.vertices, dtype=np.float64)
    seam = np.flatnonzero(np.abs(vertices[:, 2]) <= 1e-12)
    assert len(seam) == 32, "die Naht der Icosphere liegt in z = 0"
    vertices[seam, 2] = np.resize(np.asarray(SEAM_NOISE) * section._ON_PLANE, len(seam))
    vertices[:, 2] += level
    return MeshData.of(trimesh.Trimesh(vertices, np.asarray(sphere.faces), process=False))


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
    ``2b83f72a5`` ruft die Reparatur sie direkt und nicht mehr über eine
    Zwischenfunktion; der alte Schalter griff danach ins Leere, und die
    Reparatur schloss alles.
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


# --- Renderer, der Kamerarückrufe sichtbar macht -----------------------------------


class NavigationLog:
    """Zeichnet jeden Navigationsrückruf auf — so viel, wie der Test fragen will."""

    def __init__(self, *, sculpting: bool = False, body: bool = False) -> None:
        self.calls: list[tuple[Any, ...]] = []
        self.sculpting = sculpting
        self.body = body

    def callbacks(self) -> Any:
        from app.ui.render.navigator import NavigatorCallbacks

        return NavigatorCallbacks(
            on_context=lambda x, y: self.calls.append(("context", x, y)),
            on_pick=lambda x, y, add: self.calls.append(("pick", x, y, add)),
            on_cursor=lambda role: self.calls.append(("cursor", role)),
            on_paint=lambda x, y, fresh: self.calls.append(("paint", x, y, fresh)),
            is_sculpting=lambda: self.sculpting,
            on_body_drag=self._body_drag,
            on_rotate_start=lambda: self.calls.append(("rotate_start",)),
            on_camera=lambda: self.calls.append(("camera",)),
            on_tilt=lambda step: self.calls.append(("tilt", step)),
            on_end=lambda: self.calls.append(("end",)),
        )

    def _body_drag(self, phase: str, x: int, y: int) -> bool:
        self.calls.append(("body", phase, x, y))
        return self.body

    def kinds(self) -> list[str]:
        return [str(call[0]) for call in self.calls]


# --- Abbruch, Teilwrite und angehaltene Läufe ---------------------------------------


class CountingToken:
    """Ein Abbruch nach ``limit`` Prüfungen — und ein Zähler, wie oft gefragt wurde."""

    def __init__(self, limit: int | None) -> None:
        self.limit = limit
        self.calls = 0

    @property
    def is_cancelled(self) -> bool:
        return self.limit is not None and self.calls >= self.limit

    def raise_if_cancelled(self) -> None:
        from app.core.errors import OperationCancelled

        self.calls += 1
        if self.limit is not None and self.calls >= self.limit:
            raise OperationCancelled()


def stop_after(count: int) -> tuple[Callable[[], None], list[bool]]:
    """Ein ``check_cancelled``, der beim ``count``-ten Aufruf abbricht, und die Liste seiner
    Aufrufe — wer danach weiterrechnet, verlängert sie.
    """
    from app.core.scene.cancel import CancelSignal

    signal = CancelSignal()
    reached: list[bool] = []

    def stop() -> None:
        reached.append(True)
        if len(reached) == count:
            signal.cancel()
        signal.raise_if_cancelled()

    return stop, reached


def break_writes_after_a_first_piece(monkeypatch: pytest.MonkeyPatch, module: Any) -> None:
    """``module.os.write`` schreibt beim ersten Aufruf ein Viertel und scheitert danach."""
    original_write = module.os.write
    calls = 0

    def break_after_first_piece(descriptor: int, payload: bytes | memoryview) -> int:
        nonlocal calls
        calls += 1
        if calls == 1:
            piece = bytes(payload[: max(1, len(payload) // 4)])
            return original_write(descriptor, piece)
        raise OSError("erzwungener Teilwrite")

    monkeypatch.setattr(module.os, "write", break_after_first_piece)


def stop_evaluation(session: Any) -> None:
    """Den Lauf, den eine Änderung oder Rücknahme anstößt, anhalten und abwarten — ohne
    Ereignisschleife meldet er nichts zurück, gerechnet wird im Test.
    """
    running = session._worker
    session.cancel_evaluation()
    if running is not None:
        assert running.wait(60_000)
    session.cancel_signal.reset()


# --- Kleine Prüfkörper ----------------------------------------------------------------


def two_cubes(offset: float) -> MeshData:
    """Ein Körper aus zwei Würfeln mit 20 mm Kante, der zweite um ``offset`` entlang X."""
    first = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    second = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    second.apply_translation((offset, 0.0, 0.0))
    return MeshData.of(trimesh.util.concatenate([first, second]))


def brep_bytes(shape: Any) -> bytes:
    """Die vollständige native Form samt Geometrie und vorhandener Triangulation."""
    exact_kernel()
    from OCP.BRepTools import BRepTools

    stream = io.BytesIO()
    BRepTools.Write_s(shape, stream)
    return stream.getvalue()


def assert_sketch_gradients(sketch: Sketch, *, step: float, atol: float) -> None:
    """Jede analytische Ableitung des Skizzenlösers gegen zentrale Differenzen."""
    from app.core.sketch import solver

    equations, anchors = solver._build_equations(sketch, {})
    pts = anchors.copy()
    total = sum(equation.rows for equation in equations)
    assert total, "ohne Gleichung prüft dieser Test nichts"
    analytic = np.zeros((total, pts.shape[0], 2))
    begin = 0
    for equation in equations:
        equation.grad(pts, analytic[begin : begin + equation.rows])
        begin += equation.rows
    analytic_flat = analytic.reshape(total, pts.size)

    def stacked(flat: np.ndarray) -> np.ndarray:
        shaped = flat.reshape(-1, 2)
        rows: list[float] = []
        for equation in equations:
            rows.extend(equation.fn(shaped))
        return np.asarray(rows)

    flat = pts.reshape(-1).copy()
    numeric = np.zeros_like(analytic_flat)
    for column in range(flat.size):
        forward = flat.copy()
        backward = flat.copy()
        forward[column] += step
        backward[column] -= step
        numeric[:, column] = (stacked(forward) - stacked(backward)) / (2.0 * step)
    assert np.allclose(analytic_flat, numeric, atol=atol), (
        f"größte Abweichung: {float(np.max(np.abs(analytic_flat - numeric))):.2e}"
    )


# --- Eine Operation direkt am Register fahren ------------------------------------------


def run_operation(
    op: str, entry: SceneObject | None, profile: Profile, **params: object
) -> OpResult:
    """Eine registrierte Operation an ``entry`` fahren, ohne Szene und Verlauf drumherum."""
    from app.core.registry import REGISTRY
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene

    spec = REGISTRY.get(op)
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry} if entry else {}),
            inputs=[entry] if entry else [],
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def run_with_parameters(
    op: str,
    entry: SceneObject | None = None,
    parameters: dict[str, Parameter] | None = None,
    **params: object,
) -> OpResult:
    """Wie :func:`run_operation`, aber ohne Profil und mit Projektparametern in der Szene."""
    from app.core.registry import REGISTRY
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene

    spec = REGISTRY.get(op)
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry} if entry else {}, parameters=parameters or {}),
            inputs=[entry] if entry else [],
            params=spec.params(**params),
            profile=None,
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def evaluated_operation(
    source: SceneObject, profile: Profile, op: str, **params: Any
) -> tuple[SceneObject, list[Finding]]:
    """Eine Operation samt der Merkmalszuordnung, die die Auswertung danach setzt."""
    import importlib

    from app.core.bootstrap import load_operations
    from app.core.registry import REGISTRY
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Operation, Scene

    load_operations()
    spec = REGISTRY.get(op)
    result = spec.fn(
        OpContext(
            scene=Scene(objects={source.id: source}),
            inputs=[source],
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=7,
            progress=lambda *_args: None,
            ask=lambda _question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )
    findings: list[Finding] = list(result.findings)
    evaluation = importlib.import_module("app.core.scene.evaluate")
    changed = evaluation._with_features(
        result.outputs[0],
        source.features,
        Operation(9, op, params=params),
        lambda *_args: pytest.fail("unerwartete Zuordnungsfrage"),
        findings,
        previous_bounds=source.mesh.bounds,
        source_mesh=source.mesh,
        transform=result.transform,
        touches_features=spec.touches_features,
        continuations=result.feature_continuations[0] if result.feature_continuations else (),
    )
    return changed, findings


# --- Geteilte Prüfkörper und kleine Geometriehelfer ----------------------------------

SOURCE = b"""<svg xmlns=\"http://www.w3.org/2000/svg\">
<g transform=\"translate(7,11)\">
<path d=\"M0 0 H20 V10 H0 Z M5 2 H15 V8 H5 Z\"/>
<rect x=\"40\" y=\"0\" width=\"8\" height=\"6\"/>
</g></svg>"""


def cube_mesh() -> MeshData:
    """Der saubere Würfel aus dem Korpus, in Millimetern."""
    from app.core.geom.mesh import read_mesh
    from app.core.ingest.loader import normalise

    return normalise(read_mesh((MESHES / "cube_clean.stl").read_bytes(), ".stl"), "mm").mesh


def cube(size: float, at: tuple[float, float, float] = (0.0, 0.0, 0.0)) -> trimesh.Trimesh:
    """Ein verschiebbarer Würfel für 3MF-Baugruppen."""
    body = trimesh.creation.box(extents=(size, size, size))
    body.apply_translation(at)
    return body


def cube_surface(
    edge: float = 20.0,
    origin: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> tuple[np.ndarray, np.ndarray]:
    """Ein Würfel als Eckpunkte und Dreiecke für den Renderer ohne Fenster."""
    base = np.array(
        [
            [0, 0, 0],
            [1, 0, 0],
            [1, 1, 0],
            [0, 1, 0],
            [0, 0, 1],
            [1, 0, 1],
            [1, 1, 1],
            [0, 1, 1],
        ],
        dtype=float,
    )
    faces = np.array(
        [
            [0, 2, 1],
            [0, 3, 2],
            [4, 5, 6],
            [4, 6, 7],
            [0, 1, 5],
            [0, 5, 4],
            [1, 2, 6],
            [1, 6, 5],
            [2, 3, 7],
            [2, 7, 6],
            [3, 0, 4],
            [3, 4, 7],
        ]
    )
    return base * edge + np.asarray(origin, dtype=float), faces


def rectangle(width_value: str = "@width", height_value: str = "@height") -> Sketch:
    """Ein leicht verzogenes Rechteck mit Maßen aus Projektparametern.

    Die flachen Punktindizes liegen unten (0, 1), rechts (2, 3), oben (4, 5)
    und links (6, 7).
    """
    return Sketch(
        plane="plane:xy",
        elements=(
            SketchElement("line", ((0.3, -0.2), (39.5, 0.4))),
            SketchElement("line", ((40.2, 0.1), (39.8, 19.7))),
            SketchElement("line", ((40.1, 20.3), (0.2, 19.8))),
            SketchElement("line", ((-0.3, 20.1), (0.1, 0.2))),
        ),
        constraints=(
            SketchConstraint("coincident", (1, 2)),
            SketchConstraint("coincident", (3, 4)),
            SketchConstraint("coincident", (5, 6)),
            SketchConstraint("coincident", (7, 0)),
            SketchConstraint("horizontal", (0, 1)),
            SketchConstraint("vertical", (2, 3)),
            SketchConstraint("horizontal", (4, 5)),
            SketchConstraint("vertical", (6, 7)),
            SketchConstraint("distance", (0, 1), width_value),
            SketchConstraint("distance", (2, 3), height_value),
        ),
    )


def inside(mesh: MeshData, points: Sequence[tuple[float, float, float]]) -> np.ndarray:
    """Prüft Innenpunkte über die Summe orientierter Raumwinkel, ohne ``rtree``."""
    inside_points = []
    for point in points:
        directions = np.asarray(mesh.raw.triangles) - np.asarray(point)
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
        inside_points.append(abs(angle) > 2.0 * np.pi)
    return np.asarray(inside_points)


def blind_cylinder(*, dense: bool = False) -> MeshData:
    """Sackloch-Prüfkörper aus ``local_detection.json``, ohne Booleschen Kern."""
    import json

    spec = json.loads(
        (Path(__file__).parent / "data" / "local_detection.json").read_text(encoding="utf-8")
    )
    count = spec["sections"] if dense else 64
    levels = spec["outer_levels"] if dense else 2
    angles = np.arange(count) * (2 * np.pi / count)
    radial = np.column_stack((np.cos(angles), np.sin(angles)))
    outer = np.empty((levels + 1, count, 3))
    outer[:, :, :2] = radial * spec["outer_radius"]
    outer[:, :, 2] = np.linspace(0, spec["height"], levels + 1)[:, None]
    top = np.column_stack((radial * spec["bore_radius"], np.full(count, spec["height"])))
    floor_z = spec["height"] - spec["bore_depth"]
    floor = np.column_stack((radial * spec["bore_radius"], np.full(count, floor_z)))
    vertices = np.vstack((outer.reshape(-1, 3), top, floor, [[0, 0, 0], [0, 0, floor_z]]))
    ti, bi, ci = (levels + 1) * count, (levels + 2) * count, (levels + 3) * count
    k, following = np.arange(count), np.roll(np.arange(count), -1)
    lower = np.arange(levels)[:, None] * count + k
    after = np.arange(levels)[:, None] * count + following
    faces = np.vstack(
        (
            np.stack((lower, after, lower + count), axis=-1).reshape(-1, 3),
            np.stack((after, after + count, lower + count), axis=-1).reshape(-1, 3),
            np.column_stack((levels * count + k, levels * count + following, ti + k)),
            np.column_stack((levels * count + following, ti + following, ti + k)),
            np.column_stack((following, k, np.full(count, ci))),
            np.column_stack((ti + k, ti + following, bi + k)),
            np.column_stack((ti + following, bi + following, bi + k)),
            np.column_stack((bi + k, bi + following, np.full(count, ci + 1))),
        )
    )
    return MeshData.of(trimesh.Trimesh(vertices, faces, process=False))


def bore_seed(mesh: MeshData) -> tuple[int, tuple[float, ...], tuple[float, ...]]:
    """Wählt eine echte Dreiecksmitte auf der nach innen gerichteten Bohrungswand."""
    triangles = np.asarray(mesh.raw.triangles)
    radial = np.linalg.norm(triangles[:, :, :2], axis=2)
    face = int(
        np.flatnonzero(
            np.all(np.isclose(radial, 3), axis=1)
            & (triangles[:, :, 2].max(axis=1) > 19)
            & (triangles[:, :, 2].min(axis=1) < 16)
        )[0]
    )
    return (
        face,
        tuple(float(value) for value in mesh.raw.triangles_center[face]),
        tuple(float(value) for value in mesh.raw.face_normals[face]),
    )


def bore_plate(
    kernel: str,
    outline: Sequence[tuple[float, float]],
    *,
    box: tuple[float, float, float] = (60.0, 40.0, 10.0),
) -> SceneObject:
    """Baut eine Platte mit dem genannten Bohrungsprofil an beiden Kernarten."""
    edit = exact_kernel()
    from app.core.brep.features import features_of
    from app.core.perceive.features import detect
    from app.core.sketch.planes import frame_of

    solid = edit.bore_profile(edit.box(*box), list(outline), frame_of((0, 0, 1), (0, 0, 0)))
    if kernel == "brep":
        return SceneObject("plate", "Platte", solid, kind="brep", features=features_of(solid))
    mesh = as_mesh_data(solid)
    return SceneObject("plate", "Platte", mesh, features=detect(mesh))


def blind_bore(kernel: str) -> SceneObject:
    """Platte mit Sackloch Ø 6 und 6 mm Tiefe, Boden bei z = 4."""
    return bore_plate(kernel, [(0, 4), (3, 4), (3, 10), (0, 10), (0, 4)])


def two_bores(
    spacing: float, *, upper: bool = False
) -> tuple[MeshData, dict[str, Feature], Feature]:
    """Zwei bekannte Sacklöcher, auf Wunsch ohne gemeinsame Tiefenlage."""
    from app.core.geom import lathe
    from app.core.geom.boolean import boolean
    from app.core.perceive.features import detect

    stock = trimesh.creation.box(extents=(36.0, 24.0, 24.0))
    stock.apply_translation((6.0, 0.0, 12.0))
    first = lathe.cylinder(radius=3.0, height=8.0, sections=96)
    first.apply_translation((0.0, 0.0, 4.0))
    second = lathe.cylinder(radius=3.0, height=8.0, sections=96)
    second.apply_translation((spacing, 0.0, 20.0 if upper else 4.0))
    mesh = boolean(
        "difference", [MeshData.of(stock), MeshData.of(first), MeshData.of(second)], quality="fine"
    ).mesh
    features = detect(mesh)
    hole = min(
        (feature for feature in features.values() if feature.kind == "hole"),
        key=lambda feature: abs(float(feature.params["centre"][0])),
    )
    return mesh, features, hole


def surface_mesh(name: str) -> trimesh.Trimesh:
    """Lädt eine Testfläche mit verbundenen Ecken aus dem Mesh-Korpus."""
    from app.core.geom.mesh import read_mesh

    body = read_mesh((MESHES / name).read_bytes(), ".stl").raw
    body.merge_vertices()
    return body


def round_surface(kind: str) -> trimesh.Trimesh:
    """Baut eine Kugel-, Torus- oder Kegelfläche mit festgelegten Maßen."""
    if kind == "sphere":
        return trimesh.creation.icosphere(subdivisions=2, radius=7.234567)
    if kind == "torus":
        return trimesh.creation.torus(
            major_radius=17.125, minor_radius=3.234567, major_sections=48, minor_sections=24
        )
    angles = np.linspace(0.0, math.tau, 48, endpoint=False)
    heights = (4.0, 12.0)
    vertices = np.asarray(
        [
            (
                z * math.tan(math.pi / 6) * math.cos(angle),
                z * math.tan(math.pi / 6) * math.sin(angle),
                z,
            )
            for z in heights
            for angle in angles
        ]
    )
    faces = []
    for lower in range(len(angles)):
        following = (lower + 1) % len(angles)
        faces.extend(
            (
                (lower, following, following + len(angles)),
                (lower, following + len(angles), lower + len(angles)),
            )
        )
    return trimesh.Trimesh(vertices=vertices, faces=faces, process=False)


def partial_cone(angular_sections: int, height_sections: int, *, reverse: bool) -> trimesh.Trimesh:
    """45°-Teilbogen eines 60°-Kegels ohne Deckflächen."""
    angles = np.linspace(-math.radians(22.5), math.radians(22.5), angular_sections + 1)
    heights = np.linspace(5.0, 15.0, height_sections + 1)
    vertices = []
    for height in heights:
        radius = height * math.tan(math.radians(30.0))
        vertices.extend(
            (radius * math.cos(angle), radius * math.sin(angle), height) for angle in angles
        )
    faces: list[tuple[int, int, int]] = []
    row = len(angles)
    for height_index in range(height_sections):
        for angle_index in range(angular_sections):
            lower = height_index * row + angle_index
            if (height_index + angle_index) % 2:
                faces.extend(
                    [(lower, lower + row, lower + 1), (lower + 1, lower + row, lower + row + 1)]
                )
            else:
                faces.extend(
                    [(lower, lower + row, lower + row + 1), (lower, lower + row + 1, lower + 1)]
                )
    if reverse:
        faces = [(first, third, second) for first, second, third in faces]
    return trimesh.Trimesh(vertices=np.asarray(vertices), faces=faces, process=False)


def partial_torus(major_sections: int, minor_sections: int) -> tuple[trimesh.Trimesh, list[int]]:
    """Echter Torus mit begrenztem Bogen in beiden Richtungen."""
    ring = trimesh.creation.torus(
        major_radius=20.0,
        minor_radius=5.0,
        major_sections=major_sections,
        minor_sections=minor_sections,
    )
    centres = np.asarray(ring.triangles_center, dtype=float)
    major_angle = np.arctan2(centres[:, 1], centres[:, 0])
    radial = np.linalg.norm(centres[:, :2], axis=1)
    minor_angle = np.arctan2(centres[:, 2], radial - 20.0)
    patch = np.flatnonzero(
        (np.abs(major_angle) <= math.radians(45.0)) & (np.abs(minor_angle) <= math.radians(60.0))
    )
    return ring, [int(index) for index in patch]


def stud_on_a_plate() -> trimesh.Trimesh:
    """Netzplatte 40 × 30 × 4 mit einem 1-mm-Nocken."""
    base = trimesh.creation.box(extents=(40.0, 30.0, 4.0))
    base.apply_translation((0.0, 0.0, 2.0))
    post = trimesh.creation.box(extents=(1.0, 1.0, 2.0))
    post.apply_translation((0.0, 0.0, 4.0))
    return trimesh.boolean.union([base, post])


def small_faces(found: dict[str, Feature]) -> dict[tuple[float, float, float], Feature]:
    """Nennt kleine ebene Flächen nach ihrem Mittelpunkt."""
    from app.core.perceive import features as features_module

    return {
        tuple(round(float(value), 3) for value in entry.params["centre"]): entry
        for entry in found.values()
        if entry.kind == "face" and float(entry.params["area"]) < features_module.MIN_FACE_AREA
    }


STUD_CENTRES = {
    (0.0, 0.0, 5.0),
    (0.5, 0.0, 4.5),
    (-0.5, 0.0, 4.5),
    (0.0, 0.5, 4.5),
    (0.0, -0.5, 4.5),
}


def plate_with_a_chamfered_slot() -> MeshData:
    """Platte mit einem Langloch Ø 6 × 26 und gefaster Mündung."""
    from shapely.geometry import LineString

    from app.core.geom.boolean import boolean

    plate = MeshData.of(trimesh.creation.box(extents=(60.0, 30.0, 8.0)))
    outline = LineString([(-10.0, 0.0), (10.0, 0.0)]).buffer(3.0, quad_segs=16)
    cutter = trimesh.creation.extrude_polygon(outline, height=20.0)
    cutter.apply_translation((0.0, 0.0, -10.0))
    lower = np.asarray(outline.exterior.coords, dtype=float)
    upper = np.asarray(outline.buffer(1.5, quad_segs=16).exterior.coords, dtype=float)
    chamfer = trimesh.convex.convex_hull(
        np.vstack(
            (
                np.column_stack((lower, np.full(len(lower), 3.0))),
                np.column_stack((upper, np.full(len(upper), 4.5))),
            )
        )
    )
    body = boolean("difference", [plate, MeshData.of(cutter)]).mesh
    return boolean("difference", [body, MeshData.of(chamfer)]).mesh


def a_foreign_slot(diameter: float, travel: float) -> MeshData:
    """Ein Langloch, wie es ein eingelesenes Netz hat — ohne Solidon-Operation.

    ``drill`` lässt seit dem 11.09.2026 kein so knappes Langloch mehr zu
    (:func:`app.core.geom.prepare.shortest_slot`); wer den Streifen darunter
    prüfen will, muss schneiden wie ein fremdes Programm: Quader minus
    aufgezogenes Stadion (RM-155).
    """
    from app.core.geom.boolean import boolean
    from app.core.geom.prepare import slot_profile
    from app.core.geom.sketch_solid import extrude_profile
    from app.core.types import PlaneFrame

    plate_body = MeshData.of(trimesh.creation.box(extents=(160.0, 120.0, 12.0)))
    outline = slot_profile(radius=diameter / 2.0, travel=travel, angle_deg=0.0)
    frame = PlaneFrame(
        origin=(0.0, 0.0, -10.0),
        x_axis=(1.0, 0.0, 0.0),
        y_axis=(0.0, 1.0, 0.0),
        normal=(0.0, 0.0, 1.0),
    )
    tool = extrude_profile(outline, 20.0, frame)
    return boolean("difference", [plate_body, MeshData.of(tool)]).mesh


def countersunk_plate(profile: Profile) -> SceneObject:
    """Exakte Platte mit durchgehender Bohrung Ø 6 und Senkung Ø 12."""
    edit = exact_kernel()
    from app.core.brep.features import features_of
    from app.core.geom.prepare import drill_outline
    from app.core.sketch.planes import frame_of

    outline = drill_outline(
        diameter=6.0,
        depth=12.0,
        profile=profile,
        compensate=False,
        widening_diameter=12.0,
        widening_depth=0.0,
        transition_angle=90.0,
    )
    body = edit.bore_profile(
        edit.box(60.0, 40.0, 10.0), outline, frame_of((0.0, 0.0, 1.0), (0.0, 0.0, 10.0))
    )
    cavity = math.pi * 3.0**2 * 7.0 + math.pi * 3.0 * (36.0 + 18.0 + 9.0) / 3.0
    assert body.volume == pytest.approx(24000.0 - cavity, rel=1e-9)
    entry = SceneObject(
        id="obj_1", name="Platte", mesh=body, kind="brep", features=features_of(body)
    )
    kinds = sorted(feature.kind for feature in entry.features.values())
    assert kinds == ["cone"] + ["face"] * 6 + ["hole"], kinds
    return entry


def material_plate(kind: str) -> SceneObject:
    """Platte mit einem Stift, Halbkugel oder Kegelstumpf als Materialmerkmal."""
    edit = exact_kernel()
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeCone, BRepPrimAPI_MakeSphere
    from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt

    from app.core.brep.features import features_of
    from app.core.brep.kernel import Solid

    plate = edit.box(60.0, 40.0, 10.0)
    if kind == "pin":
        part = edit.moved(edit.cylinder(6.0, 8.0), (0.0, 0.0, 10.0))
        added = math.pi * 3.0**2 * 8.0
    elif kind == "sphere":
        part = Solid(BRepPrimAPI_MakeSphere(gp_Pnt(20.0, 0.0, 10.0), 4.0).Shape())
        added = 2.0 * math.pi * 4.0**3 / 3.0
    else:
        part = Solid(
            BRepPrimAPI_MakeCone(
                gp_Ax2(gp_Pnt(-20.0, 0.0, 10.0), gp_Dir(0.0, 0.0, 1.0)), 5.0, 2.0, 6.0
            ).Shape()
        )
        added = math.pi * 6.0 * (25.0 + 10.0 + 4.0) / 3.0
    body = edit.boolean("union", [plate, part])
    assert body.volume == pytest.approx(24000.0 + added, rel=1e-9)
    entry = SceneObject(
        id="obj_1", name="Platte", mesh=body, kind="brep", features=features_of(body)
    )
    assert [feature.kind for feature in entry.features.values() if feature.kind != "face"] == [kind]
    return entry


def narrowest_hole(source: SceneObject) -> Feature:
    """Die schmalste Bohrung einer Kette oder deren Senkung."""
    holes = [feature for feature in source.features.values() if feature.kind == "hole"]
    if not holes:
        holes = [feature for feature in source.features.values() if feature.kind == "cone"]
    return min(holes, key=lambda feature: float(feature.params["diameter"]))


def widened_bore(
    kernel: str, outline: Sequence[tuple[float, float]], *, bottom: str = "eben"
) -> SceneObject:
    """Platte mit einer Bohrung am Ursprung und ebener oder gekrümmter Unterseite."""
    edit = exact_kernel()
    from app.core.brep.features import features_of
    from app.core.perceive.features import detect
    from app.core.sketch.planes import frame_of

    plate = edit.box(44.0, 24.0, 12.0)
    if bottom != "eben":
        axis_height = -39.5 if bottom == "Rinne R 40" else 40.0
        roll = edit.revolved_bore_tool(
            [(0.0, -30.0), (40.0, -30.0), (40.0, 30.0), (0.0, 30.0), (0.0, -30.0)],
            frame_of((1.0, 0.0, 0.0), (0.0, 0.0, axis_height)),
        )
        if bottom == "Rinne R 40":
            plate = edit.unified(edit.boolean("difference", [plate, roll]))
        elif bottom == "Zylinder R 40":
            plate = edit.unified(edit.boolean("intersection", [plate, roll]))
        else:
            flat = edit.moved(edit.box(60.0, 12.0, 20.0), (0.0, -6.0, 0.0))
            support = edit.unified(edit.boolean("union", [roll, flat]))
            plate = edit.unified(edit.boolean("intersection", [plate, support]))
    solid = edit.bore_profile(plate, list(outline), frame_of((0, 0, 1), (-8.0, 0, 0)))
    if kernel == "brep":
        return SceneObject("plate", "Platte", solid, kind="brep", features=features_of(solid))
    mesh = as_mesh_data(solid)
    return SceneObject("plate", "Platte", mesh, features=detect(mesh))


def cavity_under(bottom: str, outline: Sequence[tuple[float, float]]) -> float:
    """Berechnet das Hohlraumvolumen oberhalb einer gekrümmten Unterseite."""
    from itertools import pairwise

    turn = np.linspace(-np.pi / 2.0, np.pi / 2.0, 20001)
    width = 50.0 * np.cos(turn) ** 2
    y = 5.0 * np.sin(turn)
    arc = np.sqrt(1600.0 - y * y)
    if bottom == "Zylinder R 40":
        raised = 40.0 - arc
    elif bottom == "Rinne R 40":
        raised = np.maximum(arc - 39.5, 0.0)
    elif bottom == "Naht Ebene-Zylinder":
        raised = np.where(y > 0.0, 40.0 - arc, 0.0)
    else:
        raised = np.zeros_like(y)
    profile_volume = sum(
        np.pi * (z1 - z0) * (r0 * r0 + r0 * r1 + r1 * r1) / 3.0
        for (r0, z0), (r1, z1) in pairwise(outline[1:-1])
    )
    return profile_volume - float(np.trapezoid(width * raised, turn))


def sloped_slot_plate(*, chamfer: bool, slotted: bool = True) -> Any:
    """Platte mit um 4° geneigter Unterseite und optional gefastem Langloch."""
    exact_kernel()
    from app.core.brep import edit
    from app.core.geom.transform import composed, rotation, translation

    plate = edit.box(40.0, 40.0, 6.0)
    below = edit.moved(edit.box(120.0, 120.0, 30.0), (0.0, 0.0, -30.0))
    matrix = np.asarray(composed(translation((0.0, 0.0, 2.0)), rotation("x", 4.0)))
    below = edit.transformed(
        below,
        tuple(tuple(float(value) for value in row) for row in matrix),
    )
    plate = edit.boolean("difference", [plate, below])
    if not slotted:
        return plate
    plate = edit.slot_bore(
        plate,
        position=(0.0, 0.0, 3.0),
        direction=(0.0, 0.0, 1.0),
        diameter=6.0,
        depth=12.0,
        length=20.0,
        angle_deg=90.0,
        overlap=0.0,
    )
    if not chamfer:
        return plate
    rims = [
        entry
        for entry in edit.edges_of(plate)
        if not entry.upright
        and all(
            abs(point[0]) <= 3.01 and abs(point[1]) <= 13.01 for point in edit.edge_points(entry)
        )
    ]
    return edit.chamfer(plate, 0.75, selected_edges=edit.native_edge_indices(plate, rims))


def slanted_plate(width: float = 20.0, length: float = 40.0) -> Any:
    """Exakte Platte ``length`` x ``width``, Unterseite z = 0, Oberseite schräg z = 10 + x/4.

    Der Träger aus RM-411 und RM-226: Ihre mittlere Höhe ist 10, das Volumen
    also ``10 · length · width``; eine Kopie längs X landet unter einer höheren
    Fläche. Unter 80 mm Länge bleibt die Oberseite über der Unterseite.
    """
    exact_kernel()
    from OCP.BRepBuilderAPI import BRepBuilderAPI_MakeFace
    from OCP.BRepPrimAPI import BRepPrimAPI_MakeHalfSpace
    from OCP.gp import gp_Dir, gp_Pln, gp_Pnt

    from app.core.brep import edit
    from app.core.brep.kernel import Solid, boolean_builder

    base = edit.box(length, width, 20.0)
    plane = BRepBuilderAPI_MakeFace(gp_Pln(gp_Pnt(0.0, 0.0, 10.0), gp_Dir(-0.25, 0.0, 1.0))).Face()
    below = BRepPrimAPI_MakeHalfSpace(plane, gp_Pnt(0.0, 0.0, 0.0)).Solid()
    builder = boolean_builder("intersection", base.shape, below)
    builder.Build()
    return Solid(builder.Shape())


def stepped_plate() -> Any:
    """Exakte Grundplatte 40 x 20 x 10 mit Aufsatz x 5 … 15 bis z = 20 (RM-411), 10 000 mm³."""
    edit = exact_kernel()
    return edit.boolean(
        "union",
        [edit.box(40.0, 20.0, 10.0), edit.moved(edit.box(10.0, 20.0, 10.0), (10, 0, 10))],
    )


def seal_cube(kind: str = "mesh") -> SceneObject:
    """Baut den Trägerkörper der Dichtungsprüfungen an beiden Kernarten."""
    if kind == "brep":
        edit = exact_kernel()
        from app.core.brep import profiles
        from app.core.sketch import shapes
        from app.core.sketch.profile import profile_of
        from app.core.sketch.solver import solve_sketch

        body = edit.moved(
            profiles.extrude(profile_of(solve_sketch(shapes.rectangle(20, 20))), 20),
            (0, 0, -10),
        )
    else:
        body = MeshData.of(trimesh.load_mesh(MESHES / "cube_clean.stl"))
    return SceneObject("body", "Träger", body, kind=kind)


def primitive_operation(
    name: str, values: dict[str, Any], profile: Profile, quality: Quality = "fine"
) -> OpResult:
    """Fährt eine registrierte Grundkörper-Op ohne Dokument oder Verlauf."""
    from app.core.bootstrap import load_operations
    from app.core.registry import REGISTRY
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene

    load_operations()
    spec = REGISTRY.get(name)
    return spec.fn(
        OpContext(
            scene=Scene(),
            inputs=[],
            params=spec.params(**values),
            profile=profile,
            quality=quality,
            seed=None,
            progress=lambda _fraction, _text: None,
            ask=lambda _question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def thread_volume(diameter: float, pitch: float, length: float, *, internal: bool) -> float:
    """Analytisches Volumen eines Bausteingewindes nach Pappus."""
    from itertools import pairwise

    from app.core.knowledge.parts import shapes

    profile = list(shapes.ridge_profile(diameter, pitch, internal=internal))
    root = profile[0][0]
    corners = [*profile, profile[0]]
    area = 0.0
    moment = 0.0
    for (r_a, z_a), (r_b, z_b) in pairwise(corners):
        cross = r_a * z_b - r_b * z_a
        area += cross
        moment += (r_a + r_b) * cross
    area, moment = abs(area) / 2.0, abs(moment) / 6.0
    return math.pi * root**2 * length + 2.0 * math.pi * moment * (length / pitch)


@cache
def studded_thread_plate(kind: str, handedness: str = "right") -> SceneObject:
    """Baut eine Platte mit aufgesetztem M6 × 1, dessen Gang leicht einsinkt."""
    edit = exact_kernel()
    from app.core.geom.boolean import BOOLEAN_OVERLAP, boolean
    from app.core.knowledge.parts import build
    from app.core.knowledge.parts.shapes import building

    plate_size = (40.0, 40.0, 10.0)
    length = 8.0
    bottom = plate_size[2] - BOOLEAN_OVERLAP
    if kind == "brep":
        with building("brep"):
            stud = build.threaded(6.0, 1.0, length, bottom=bottom)
        body = edit.unified(edit.boolean("union", [edit.box(*plate_size), stud]))
    else:
        stud = build.threaded(6.0, 1.0, length, bottom=bottom)
        mesh_plate = as_mesh_data(edit.box(*plate_size))
        body = boolean("union", [mesh_plate, stud], quality="fine").mesh
    feature = Feature(
        id="thread_1",
        kind="thread",
        provenance="generated",
        params={
            "diameter": 6.0,
            "pitch": 1.0,
            "handedness": handedness,
            "centre": (0.0, 0.0, bottom + length / 2.0),
            "axis": (0.0, 0.0, 1.0),
            "internal": False,
            "length": length,
        },
        measure_sources=dict.fromkeys(
            ("diameter", "pitch", "centre", "axis", "length"), "parameter"
        ),
    )
    return SceneObject(
        id="obj_1", name="Platte", mesh=body, kind=kind, features={feature.id: feature}
    )


@cache
def tapped_thread_plate(kind: str) -> SceneObject:
    """Baut eine Platte mit durchgehendem M6 × 1 Innengewinde."""
    edit = exact_kernel()
    from app.core.geom.boolean import BOOLEAN_OVERLAP, boolean
    from app.core.knowledge.parts import build, shapes
    from app.core.knowledge.parts.shapes import building

    plate_size = (40.0, 40.0, 10.0)
    diameter, pitch, length = 6.0, 1.0, plate_size[2] + 2.0 * BOOLEAN_OVERLAP
    bore = diameter - 2.0 * pitch * shapes.RIDGE_SHARE
    if kind == "brep":
        with building("brep"):
            tap = build.threaded(bore, pitch, length, internal=True, bottom=-BOOLEAN_OVERLAP)
        body = edit.unified(edit.boolean("difference", [edit.box(*plate_size), tap]))
    else:
        tap = build.threaded(bore, pitch, length, internal=True, bottom=-BOOLEAN_OVERLAP)
        mesh_plate = as_mesh_data(edit.box(*plate_size))
        body = boolean("difference", [mesh_plate, tap], quality="fine").mesh
    feature = Feature(
        id="thread_1",
        kind="thread",
        provenance="generated",
        params={
            "diameter": diameter,
            "pitch": pitch,
            "handedness": "right",
            "centre": (0.0, 0.0, plate_size[2] / 2.0),
            "axis": (0.0, 0.0, 1.0),
            "internal": True,
            "length": plate_size[2],
        },
        measure_sources=dict.fromkeys(
            ("diameter", "pitch", "centre", "axis", "length"), "parameter"
        ),
    )
    return SceneObject(
        id="obj_1", name="Platte", mesh=body, kind=kind, features={feature.id: feature}
    )


def mirrored_thread(solid: Any) -> Any:
    """Spiegelt einen exakten Gewindekörper an der XZ-Ebene."""
    edit = exact_kernel()
    matrix = (
        (1.0, 0.0, 0.0, 0.0),
        (0.0, -1.0, 0.0, 0.0),
        (0.0, 0.0, 1.0, 0.0),
        (0.0, 0.0, 0.0, 1.0),
    )
    return edit.transformed(solid, matrix)


def bash_executable() -> Path | None:
    """Findet Bash im Suchpfad oder relativ zur tatsächlich installierten Git-Ausgabe."""
    executable = shutil.which("bash")
    if executable and "system32" not in Path(executable).parts[-2].lower():
        return Path(executable)
    git = shutil.which("git")
    roots = [Path(git).parent.parent] if git else []
    for variable, suffix in (("ProgramFiles", "Git"), ("LOCALAPPDATA", "Programs/Git")):
        value = os.environ.get(variable)
        if value:
            roots.append(Path(value) / suffix)
    return next(
        (root / "bin" / "bash.exe" for root in roots if (root / "bin" / "bash.exe").is_file()),
        None,
    )


def set_test_license(monkeypatch: Any, *, active: bool) -> None:
    """Setzt den Freischaltzustand für Lizenzgrenztests."""
    from app.core import activation

    if not active:
        monkeypatch.setattr(activation, "_cached", activation.Activation(days_left=0))
        return

    from app.core.activation import key

    licence = key.Licence(
        major=key.current_major(),
        purchased_on=date(2026, 8, 6),
        order="A-1234",
        holder="kaeufer@beispiel.de",
    )
    certificate = activation.ActivationCertificate(
        licence_digest="test-licence",
        device_public=b"\x01" * 32,
        device_name="Prüfrechner",
        activation_id="test-activation",
        issued_on=date(2026, 8, 28),
    )
    monkeypatch.setattr(
        activation,
        "_cached",
        activation.Activation(licence=licence, certificate=certificate),
    )


@contextmanager
def php_server(
    tmp_path: Path,
    extra_environment: dict[str, str] | None = None,
    *,
    prepend: Path | None = None,
    error_log: Path | None = None,
    ini: dict[str, str] | None = None,
    docroot: Path | None = None,
    extensions: tuple[str, ...] = (),
) -> Iterator[str]:
    """Startet einen isolierten lokalen PHP-Testserver ohne ausgehende E-Mail."""
    from tests.php_probe import free_port, php_command

    php = php_command(*extensions)
    port = free_port()
    environment = os.environ.copy()
    environment["SOLIDON_STATS_DIR"] = str(tmp_path / "stats")
    environment["SOLIDON_ACTIVATION_RATE_FILE"] = str(tmp_path / "activation-rate.json")
    environment["SOLIDON_SUPPORT_RATE_FILE"] = str(tmp_path / "support-rate.json")
    if extra_environment:
        environment.update(extra_environment)
    command = [
        *php,
        "-d",
        "sendmail_path=/nonexistent/solidon-keine-post",
        "-d",
        "SMTP=127.0.0.1",
        "-d",
        "smtp_port=1",
    ]
    if prepend is not None:
        command.extend(["-d", f"auto_prepend_file={prepend}"])
    if error_log is not None:
        command.extend(["-d", "log_errors=1", "-d", f"error_log={error_log}"])
    for key, value in (ini or {}).items():
        command.extend(["-d", f"{key}={value}"])
    command.extend(["-S", f"127.0.0.1:{port}", "-t", str(docroot or "website")])
    root = Path(__file__).parent.parent
    process = subprocess.Popen(
        command,
        cwd=root,
        env=environment,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    base = f"http://127.0.0.1:{port}/api"
    try:
        for _attempt in range(50):
            try:
                with urlopen(f"{base}/activation_common.php", timeout=5):
                    break
            except HTTPError as response:
                response.close()
                break
            except URLError:
                time.sleep(0.05)
        else:
            pytest.fail("der lokale PHP-Prüfserver ist nicht gestartet")
        yield base
    finally:
        process.terminate()
        process.wait(timeout=5)


def product_tree(root: Path, monkeypatch: Any) -> Path:
    """Baut einen kleinen Windows-Bau und schreibt die Signierübergabe."""
    from tools import make_installer

    app = make_installer.APP_NAME
    source = root / "dist" / app
    packaging = root / "packaging"
    build = packaging / "build"
    for path, content in (
        (source / f"{app}.exe", b"Programm"),
        (source / "_internal" / "python313.dll", b"Python-Laufzeit"),
        (source / "_internal" / f"{app}.cdx.json", b"{}"),
        (source / "THIRD-PARTY-NOTICES.md", b"Lizenzbeilage"),
        (packaging / "solidon3d.iss", b"Skript"),
        (packaging / "eula.txt", b"Vertrag"),
        (packaging / "solidon3d.ico", b"Symbol"),
        (build / "licence.manifest", b"Manifest"),
    ):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)
    monkeypatch.setattr(make_installer, "ROOT", root)
    monkeypatch.setattr(make_installer, "SOURCE_DIR", source)
    monkeypatch.setattr(make_installer, "OUTPUT_DIR", root / "dist")
    monkeypatch.setattr(make_installer, "SCRIPT", packaging / "solidon3d.iss")
    monkeypatch.setattr(make_installer, "SIGNING_HANDOFF", build / "windows-signing.json")
    monkeypatch.setattr(make_installer, "_licence_file", lambda: packaging / "eula.txt")
    monkeypatch.setattr(make_installer, "stale_reason", lambda: "")
    assert make_installer.write_signing_handoff() == 0
    return root


def pack_release(tree: Path, target_dir: Path) -> Path:
    """Packt den Produktbaum wie der Paketjob und schreibt seine Prüfsumme."""
    from tools import sign_release

    archive = target_dir / sign_release.ARCHIVE_NAME
    target_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for path in sorted(tree.rglob("*")):
            if path.is_file():
                zip_file.write(path, path.relative_to(tree).as_posix())
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    archive.with_name(archive.name + ".sha256").write_text(
        f"{digest}  {archive.name}\n", encoding="ascii"
    )
    return archive


def recipe_document_seed(width: float = 30.0) -> Document:
    """Ein Quaderdokument, dessen Breite am Projektparameter ``w`` hängt."""
    from app.core.scene.migrations import FORMAT_VERSION

    return Document(
        format_version=FORMAT_VERSION,
        app_version="test",
        parameters={"w": Parameter(name="w", value=width)},
        ops=[
            Operation(
                id=1,
                op="create_box",
                outputs=("obj_1",),
                params={
                    "width": "@w",
                    "depth": 20.0,
                    "height": 8.0,
                    "anchor": "corner",
                    "name": "",
                },
            )
        ],
    )


def clean_recipe_globals(*names: str) -> None:
    """Entfernt ausschließlich die benannten Rezept- und Ops-Registrierungen."""
    from app.core.knowledge.parts import ops as part_ops
    from app.core.knowledge.parts.registry import PARTS
    from app.core.registry import REGISTRY

    for name in names:
        PARTS._parts.pop(name, None)
        REGISTRY._ops.pop(part_ops.op_name(name), None)


def recipe_with_halter(width_default: float, profile: Profile) -> Any:
    """Ein Probehalter-Rezept mit der angegebenen Vorgabebreite."""
    from app.core.knowledge.parts import recipe

    return recipe.capture(
        recipe_document_seed(),
        {},
        name="probe_halter",
        title="Probehalter",
        group="structure",
        op_ids=(1,),
        exposed=(
            recipe.ExposedParam(
                name="w", title="Breite", default=width_default, minimum=10.0, maximum=90.0
            ),
        ),
        features={"top": "face_top"},
        profile=profile,
    )


def pbr_glb() -> bytes:
    """Ein GLB-Quader 20 × 16 × 12 mm mit roter und blauer PBR-Textur."""
    from PIL import Image

    body = trimesh.creation.box(extents=(20.0, 16.0, 12.0))
    span = np.ptp(body.vertices[:, :2], axis=0)
    uv = (body.vertices[:, :2] - body.vertices[:, :2].min(axis=0)) / span
    image = Image.new("RGB", (2, 2))
    image.putdata([(255, 0, 0), (0, 0, 255), (255, 0, 0), (0, 0, 255)])
    material = trimesh.visual.material.PBRMaterial(name="Rot und Blau", baseColorTexture=image)
    body.visual = trimesh.visual.TextureVisuals(uv=uv, material=material)
    value = trimesh.Scene({"Farbig": body}).export(file_type="glb")
    return value if isinstance(value, bytes) else value.encode("utf-8")


class LoopbackServer(http.server.HTTPServer):
    """Ein Testserver auf der Rückschleife, ohne Namensauflösung beim Binden.

    ``HTTPServer.server_bind`` fragt ``socket.getfqdn`` nach dem Namen der
    Adresse. Am macOS-Runner dauerte diese Rückwärtsauflösung 35 s, auf
    Ubuntu 2 ms (RM-104); den Namen liest kein Test.
    """

    def server_bind(self) -> None:
        socketserver.TCPServer.server_bind(self)
        host, port = self.server_address[:2]
        self.server_name = str(host)
        self.server_port = int(port)


# --- Der erste Start eines Slicers der Orca-Familie als AppImage ------------------

#: Wo die Orca-Familie ihre Konfiguration ablegt, unter ``slicer_profiles.config_base``.
#: Creality Print 7 legt unter seinem Anwendungsschlüssel und der Version ab.
ORCA_CONFIG_FOLDERS = {
    "orcaslicer": "OrcaSlicer",
    "bambustudio": "BambuStudio",
    "elegooslicer": "ElegooSlicer",
    "crealityprint": "Creality/Creality Print/7.2",
}


def first_start(executable: Path) -> Path | None:
    """Was der erste Start eines AppImage der Orca-Familie beim Kunden hinterlässt.

    Ein solches AppImage trägt seinen Herstellerbestand nur im Abbild, das zur
    Laufzeit eingehängt ist; lesbar wird er erst, wenn der Slicer einmal lief
    und die Bündel nach ``<Konfiguration>/<Programm>/system/`` kopiert hat,
    neben ``user/default/``. Genau das legt diese Funktion an, aus dem
    ausgepackten Abbild — ohne Bilder und Bettmodelle, die Solidon nicht
    liest. Gibt den angelegten ``system``-Ordner zurück, sonst ``None``.
    """
    from app.core import discover
    from app.core.export import slicer_profiles

    folder = ORCA_CONFIG_FOLDERS.get(discover.program_mark(executable.name))
    base = slicer_profiles.config_base(executable)
    if folder is None or not base or executable.suffix.lower() != ".appimage":
        return None
    system = Path(base) / folder / "system"
    if system.is_dir():
        return system
    unpacked = Path(base) / ".erststart"
    unpacked.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [str(executable), "--appimage-extract"],
        cwd=unpacked,
        capture_output=True,
        timeout=600,
        check=True,
    )
    profiles = next(
        (
            candidate
            for candidate in sorted((unpacked / "squashfs-root").rglob("profiles"))
            if candidate.is_dir() and any(candidate.glob("*.json"))
        ),
        None,
    )
    if profiles is None:
        return None
    (Path(base) / folder / "user" / "default").mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        profiles, system, ignore=shutil.ignore_patterns("*.stl", "*.png", "*.svg", "*.jpg")
    )
    shutil.rmtree(unpacked, ignore_errors=True)
    return system


def plate_on_a_sloped_foot(angle: float) -> MeshData:
    """Eine Platte 60 mm im Quadrat, deren untere 4 mm ringsum unter ``angle``
    gegen die Senkrechte nach außen laufen — die Bodenkante des Bahnteils
    ``Gövde59`` aus dem Minigolf-Satz (``F:\\3D Dateien``, 27.09.2026):
    2 mm Bodenplatte mit gut 50 Grad Fase, darüber 45 bis 50 Grad nach außen
    geneigte Wände, zusammen 320 mm² Überhang über 45 Grad in Stücken bis
    25 mm², darüber nichts. Rat und Randfrage messen ihn beide."""
    reach = 4.0 * math.tan(math.radians(angle))
    foot = [(x, y, 0.0) for x in (-30.0, 30.0) for y in (-30.0, 30.0)]
    wide = 30.0 + reach
    top = [(x, y, z) for x in (-wide, wide) for y in (-wide, wide) for z in (4.0, 10.0)]
    return MeshData.of(trimesh.convex.convex_hull(np.array(foot + top)))


def object_values(written: Path, member: str) -> dict[str, dict[str, str]]:
    """Die Objektwerte einer Baugruppe je Objektname — aus
    ``model_settings.config`` (Orca-Familie) oder ``Slic3r_PE_model.config``
    (PrusaSlicer)."""
    from xml.etree import ElementTree as ET

    config = ET.fromstring(zipfile.ZipFile(written).read(member))
    values: dict[str, dict[str, str]] = {}
    for node in config.iter("object"):
        own = {meta.get("key", ""): meta.get("value", "") for meta in node.findall("metadata")}
        values[own.pop("name", node.get("id", ""))] = own
    return values


def supported_table(index: int) -> trimesh.Trimesh:
    """Sockel, Säule und Platte darüber: Die Stütze steht auf dem Sockel. Je
    ``index`` 45 mm weiter rechts, damit mehrere auf einer Platte Platz haben."""
    parts = []
    for extents, z in (
        ((30.0, 30.0, 3.0), 1.5),
        ((8.0, 8.0, 10.2), 8.0),
        ((30.0, 30.0, 2.0), 14.0),
    ):
        brick = trimesh.creation.box(extents=extents)
        brick.apply_translation([index * 45.0, 0.0, z])
        parts.append(brick)
    return trimesh.boolean.union(parts, engine="manifold")


def on_bed(*parts: trimesh.Trimesh) -> MeshData:
    """Die Teile vereint und auf das Bett gestellt."""
    body = parts[0] if len(parts) == 1 else trimesh.boolean.union(list(parts))
    return place_on_bed(MeshData.of(body))


def brick(x: float, y: float, z: float, at: tuple[float, float, float]) -> trimesh.Trimesh:
    """Ein Quader der Kanten ``x``, ``y``, ``z`` mit der Mitte in ``at``."""
    body: trimesh.Trimesh = trimesh.creation.box(extents=(x, y, z))
    body.apply_translation(at)
    return body


def column_table() -> MeshData:
    """Bodenplatte 40 auf 40, darauf eine Säule 10 auf 10, darauf eine Platte.

    Keine Insel, 1 500 mm² Überhang auf einer Schicht — und jede Stütze
    darunter endet auf der Bodenplatte, nicht auf dem Bett.
    """
    return on_bed(
        brick(40.0, 40.0, 5.0, (0.0, 0.0, 2.5)),
        brick(10.0, 10.0, 20.0, (0.0, 0.0, 15.0)),
        brick(40.0, 40.0, 5.0, (0.0, 0.0, 27.5)),
    )


def chin(underside_at_wall: float) -> trimesh.Trimesh:
    """Der Kopf mit schräger Unterseite: an der Rückwand auf ``underside_at_wall``,
    an der Spitze 18 mm davor auf 50 mm."""
    return trimesh.convex.convex_hull(
        [
            (x, y, z)
            for x in (-8.0, 8.0)
            for y, z in ((15.0, underside_at_wall), (-3.0, 50.0), (15.0, 56.0), (-3.0, 56.0))
        ]
    )


def chin_over_chest() -> MeshData:
    """Eine Figur im Kleinen: ein Kinn mit schräger Unterseite über der Brust,
    dessen Streifen auf dem Modell aufsetzen — kleine, gewölbte Überhänge."""
    return on_bed(
        brick(80.0, 60.0, 4.0, (0.0, 0.0, 2.0)),
        brick(40.0, 10.0, 60.0, (0.0, 20.0, 34.0)),
        brick(60.0, 30.0, 20.0, (0.0, 0.0, 14.0)),
        chin(44.0),
    )
