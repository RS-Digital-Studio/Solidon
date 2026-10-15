"""Keine Zeile der Liste FD-101 ohne Weg zu ihrer Fläche (FD-101, FD-151, RM-737).

Im Sprachfall erreichte der Prüfstand eine Reihe von Flächen nie: Dialoge ohne
Weg, Operationen über die ganze Szene, deren Weg einen Körper wählte, Fußknöpfe
des Merkmalfensters ohne offene Handlungszeile, Szenen ohne den Befund oder die
Merkmale der Zeile. Ohne Fenster prüfbar ist, dass jede dieser Zeilen eine
Startszene aus dem Katalog hat, deren Zusagen ihren Weg tragen, und dass der
Weg der ist, der die Fläche öffnet — am Fenster belegt ihn der Probelauf
(Bericht ``fix-f7-claude.md``).
"""

from __future__ import annotations

from dataclasses import asdict
from typing import Any

import pytest

from tools import function_list, function_surface

#: Zeile → (Startszene, Weg der Zeile samt Spezifikation, ohne das Ziel). Der Weg
#: ist der Kundenweg zur Fläche, gemessen offscreen (Bericht, Abschnitt FD-101).
REACHED: dict[str, tuple[str, tuple[str, ...]]] = {
    # D4
    "slot_hole": ("erkannte_bohrung.netz", ("tree.row:obj_1.hole_1",)),
    "feature.apply": ("merkmal.hole.exakt", ("tree.row:obj_1.hole_1", "feature:move_feature")),
    "feature.in_view": ("merkmal.hole.exakt", ("tree.row:obj_1.hole_1", "feature:move_feature")),
    "feature.every": (
        "gleiche_bohrungen.exakt",
        ("tree.row:obj_1.hole_1", "feature:move_feature"),
    ),
    "dialog:local_recognition_dialog": (
        "quader.netz",
        ("tree.row:obj_1", "operation:detect_region", "view:obj_1"),
    ),
    # D8
    "arrange_bed": ("zwei_koerper.exakt", ()),
    "check_collisions": ("zwei_koerper.exakt", ()),
    "orient_for_print": ("zwei_koerper.exakt", ()),
    "dialog:step_values_dialog": (
        "alter_farbschritt.netz",
        ("finding:evaluate.legacy_point_paint", "finding.action:show_step_values"),
    ),
    "dialog:body_choice_dialog": (
        "zwei_unter_dem_bett.netz",
        ("finding:arrange.below_bed", "finding.action:place_on_bed"),
    ),
    "finding.action:install": (
        "ohne_opencascade.exakt",
        ("finding:op.create_brep_box.BRepUnavailable",),
    ),
    "finding.action:keep_saved_parts": ("baustein_geaendert.netz", ("finding:parts.own_changed",)),
    "command:edit.auto_split": ("zu_gross.netz", ("tree.row:obj_1",)),
    "dialog:seal_path_dialog": (
        "merkmal.face.exakt",
        ("tree.row:obj_1.face_6", "operation:create_seal", "field:path_sketch"),
    ),
    # D9
    "filament.add": ("leer", ("menu:menubar.filamentlager",)),
    # D10
    "menu:parameters.edit": ("parameter.exakt", ("parameters.first.label",)),
    "dialog:binding_dialog": ("parameter.exakt", ("parameters.bind",)),
    "dialog:recipe_dialog": (
        "parameter.exakt",
        ("tree.row:obj_1", "menu:menubar.bausteinkatalog", "parts.save"),
    ),
    "dialog:slicer_filament_dialog": (
        "quader_mit_slicer.exakt",
        (
            "tree.row:obj_1",
            "menu:menubar.filamentlager",
            "filament.add",
            "filament.profile",
        ),
    ),
    "meldung:_pick_colour": (
        "quader.exakt",
        ("tree.row:obj_1", "menu:menubar.filamentlager", "filament.add", "filament.colour"),
    ),
    # Die Knöpfe auf diesen Wegen sind selbst Zeilen des Wortschatzes.
    "parameters.first.label": ("parameter.exakt", ()),
    "parameters.bind": ("parameter.exakt", ()),
    "parts.save": ("parameter.exakt", ("menu:menubar.bausteinkatalog",)),
    "filament.profile": ("leer", ("menu:menubar.filamentlager", "filament.add")),
    "filament.colour": ("leer", ("menu:menubar.filamentlager", "filament.add")),
    "dialog:parameter_dialog": ("leer", ("menu:menubar.parameter_anlegen",)),
    "dialog:calibration_dialog": ("leer", ("menu:menubar.material_kalibrieren",)),
    "dialog:counterpart_dialog": (
        "zwei_koerper.exakt",
        (
            "tree.row:obj_1",
            "tree.row:obj_2",
            "tree.row:obj_1.face_1",
            "tree.row:obj_2.face_1",
            "menu:menubar.gegenstuecke_setzen",
        ),
    ),
    "meldung:action_counterpart": (
        "gewinde_zwei_reihen.netz",
        (
            "tree.row:obj_1",
            "tree.row:obj_2",
            "tree.row:obj_1.thread_1",
            "tree.row:obj_2.face_1",
            "menu:menubar.gegenstuecke_setzen",
        ),
    ),
    # D12: Der Druckhinweis vor dem Druckdialog, im eigenen Sprachfall mit offenem Hinweis.
    "dialog:print_disclosure_dialog": ("quader.exakt", ("menu:menubar.an_den_slicer_uebergeben",)),
}


@pytest.fixture(scope="module")
def rows() -> dict[str, dict[str, Any]]:
    return {row.id: asdict(row) for row in function_list.rows()}


def _way(row: dict[str, Any]) -> tuple[str, ...]:
    steps = [*(row.get("route") or ()), *((row.get("spec") or {}).get("route") or ())]
    return tuple(str(step["target"]) for step in steps)


def test_the_list_is_the_list_of_the_finding(rows: dict[str, dict[str, Any]]) -> None:
    """Jede Zeile der Liste ist eine erzeugte Zeile — eine umbenannte fiele sonst still heraus."""
    assert sorted(set(REACHED) - set(rows)) == []


@pytest.mark.parametrize("row_id", sorted(REACHED))
def test_every_row_of_the_list_has_its_scene_and_its_way(
    rows: dict[str, dict[str, Any]], row_id: str
) -> None:
    from tools.function_setup import walk_target

    row = rows[row_id]
    scene, way = REACHED[row_id]
    assert (row.get("spec") or {}).get("start_scene", row["start_scene"]) == scene
    assert _way(row) == way, _way(row)
    assert function_surface.without_way(row) == "", function_surface.without_way(row)
    assert walk_target(row) not in way


def test_an_operation_over_the_whole_scene_is_walked_without_a_selection(
    rows: dict[str, dict[str, Any]],
) -> None:
    """Seit RM-735 stehen sie nur ohne Auswahl in der Karte; ein Weg mit Auswahl fand sie nie."""
    whole = [row for row in rows.values() if row["requirement"] == "szene"]
    assert len(whole) >= 3
    for row in whole:
        assert not any(name.startswith(("tree.row:", "view")) for name in _way(row)), row["id"]


def test_a_way_over_a_finding_the_scene_does_not_promise_is_no_way(
    rows: dict[str, dict[str, Any]],
) -> None:
    """Gegenprobe: Ein Befund, den die Startszene nicht zusagt, ist kein Weg — kein Fund."""
    row = {**rows["dialog:step_values_dialog"]}
    row["spec"] = {**row["spec"], "route": [{"target": "finding:arrange.below_bed"}]}
    assert "sagt den Befund arrange.below_bed nicht zu" in function_surface.without_way(row)
    row["spec"] = {**row["spec"], "route": [{"target": "finding.action:place_on_bed"}]}
    assert "sagt die Handlung place_on_bed nicht zu" in function_surface.without_way(row)


def test_the_thread_of_its_scene_asks_for_its_size() -> None:
    """``gewinde_zwei_reihen.netz`` trägt ein Gewinde, das M4 und #8-36 UNF nicht trennt:
    Nur dann stellt *Gegenstücke setzen …* die Rückfrage, deren Fenster die Zeile
    ``meldung:action_counterpart`` misst."""
    from app.core import counterpart
    from app.core.errors import AppError
    from app.core.knowledge import standards
    from tests.helpers import exact_kernel
    from tools import function_scenes

    exact_kernel()
    result = function_scenes.evaluate_scene(function_scenes.build_scene("gewinde_zwei_reihen.netz"))
    thread = result.scene.objects["obj_1"].features["thread_1"]
    with pytest.raises(AppError) as asked:
        counterpart.thread_values_for(thread, families=standards.shown_thread_families())
    assert asked.value.constraint == counterpart.AMBIGUOUS_THREAD
    assert set(asked.value.values["choices"]) == {"M4", "#8-36 UNF"}
