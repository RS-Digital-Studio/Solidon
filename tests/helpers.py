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
from typing import Any

import pytest

from app.core.geom.mesh import as_mesh_data
from app.core.types import Feature, SceneObject


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
