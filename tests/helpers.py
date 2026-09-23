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

import math
import struct
from pathlib import Path
from typing import Any

import pytest
import trimesh

from app.core.geom.mesh import as_mesh_data
from app.core.scene import History, OperationDraft
from app.core.scene.project import Project, new_project
from app.core.types import Feature, SceneObject, Source

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
    nicht die Reparatur als Operation. **Und die Sitzung bekommt einen eigenen
    Cache nur im Speicher:** Der Plattencache der Suite ist prozessweit, und
    ein früherer Test hat dieselbe Datei vielleicht schon geschlossen
    eingelesen — sein Ergebnis käme sonst aus dem Cache statt aus der
    Leseoperation.
    """
    from functools import partial

    from app.core.ingest import loader, ops
    from app.core.scene.cache import ResultCache

    monkeypatch.setattr(ops, "normalise", partial(loader.normalise, mend=False))
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
    """
    import trimesh

    from app.core.geom import repair

    def filled(mesh: Any) -> tuple[Any, bool, int]:
        before = repair.open_edge_count(mesh)
        if not before:
            return mesh, False, 0
        raw = mesh.raw.copy()
        trimesh.repair.fill_holes(raw)
        result = mesh.replacing(raw)
        return result, repair.open_edge_count(result) < before, 0

    monkeypatch.setattr(repair, "_filled_with_count", filled)
