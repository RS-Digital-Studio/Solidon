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
    "group_pattern": (
        "drei_zapfen.netz",
        ("tree.row:obj_1", "tree.row:obj_1.pin_1", "tree.row:obj_1.pin_2", "tree.row:obj_1.pin_3"),
    ),
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
    "finding.action:recognize_fully": ("ueber_erkennungsgrenze", ("finding:perceive.too_large",)),
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
    "meldung:_replacement_slot": (
        "sieben_filamente.netz",
        ("tree.row:obj_1", "operation:label_text", "field:slot", "filament.spool"),
    ),
    "filament.spool": (
        "sieben_filamente.netz",
        ("tree.row:obj_1", "operation:label_text", "field:slot"),
    ),
    # D12: Der Druckhinweis vor dem Druckdialog, im eigenen Sprachfall mit offenem Hinweis.
    "dialog:print_disclosure_dialog": ("quader.exakt", ("menu:menubar.an_den_slicer_uebergeben",)),
    # FD-175: die Fenster ohne Weg in D1, D2, D7, D9, D11 und D12, offscreen erreicht
    # (Bericht ``fix-rest-c-claude.md``). Hilfe und Bearbeiten im leeren Projekt.
    "dialog:about_dialog": ("leer", ("menu:menubar.ueber_solidon",)),
    "dialog:activation_dialog": ("leer", ("menu:menubar.solidon_freischalten",)),
    "dialog:changes_dialog": ("leer", ("menu:menubar.neuerungen",)),
    "dialog:donation_dialog": ("leer", ("menu:menubar.app_unterstuetzen",)),
    "dialog:install_dialog": ("leer", ("menu:menubar.zusaetzliche_programme",)),
    "dialog:key_dialog": ("leer", ("menu:menubar.chat_einrichten",)),
    "dialog:manual_window": ("leer", ("menu:menubar.handbuch",)),
    "dialog:settings_dialog": ("leer", ("menu:menubar.einstellungen",)),
    "dialog:shortcuts_window": ("leer", ("menu:menubar.tastenkuerzel",)),
    "dialog:support_dialog": ("leer", ("menu:menubar.rueckmeldung_senden",)),
    "dialog:first_run_dialog": ("startbildschirm", ("menu:menubar.erste_schritte",)),
    "dialog:input_dialog": ("leer", ("menu:menubar.modell_aus_dem_netz",)),
    "dialog:ask_dialog": (
        "gewinde_zwei_reihen.netz",
        ("tree.row:obj_1.thread_1", "tree.row:obj_2.face_1", "menu:menubar.gegenstuecke_setzen"),
    ),
    "dialog:message_dialog": (
        "duenne_huelse.netz",
        ("finding:perceive.thin_wall", "finding.action:show_details"),
    ),
    "meldung:show_details": (
        "duenne_huelse.netz",
        ("finding:perceive.thin_wall", "finding.action:show_details"),
    ),
    "dialog:operation_dialog": ("quader.exakt", ("tree.row:obj_1", "history.row:1")),
    "dialog": ("quader.exakt", ("tree.row:obj_1", "history.row:1")),
    "meldung:show_error": ("einfuegen.netz", ("tree.row:obj_1", "command:edit.auto_split")),
    "dialog:main_window": ("leer", ("report",)),
    "dialog:new_filament_dialog": ("leer", ("menu:menubar.filamentlager", "filament.add")),
    "dialog:print_settings_dialog": (
        "quader.exakt",
        ("tree.row:obj_1", "menu:menubar.an_den_slicer_uebergeben"),
    ),
    "meldung:_choose": (
        "quader.exakt",
        ("tree.row:obj_1", "menu:menubar.an_den_slicer_uebergeben", "print:filament.colour"),
    ),
    "meldung:action_import_url": ("leer", ("menu:menubar.modell_aus_dem_netz",)),
    "meldung:confirm_unsaved": (
        "quader.exakt",
        ("tree.row:obj_1", "operation:delete_object", "menu:menubar.neu", "start.new"),
    ),
    "part:*": ("leer", ("menu:menubar.bausteinkatalog",)),
    "dialog:part_catalog": ("leer", ("menu:menubar.bausteinkatalog",)),
    "dialog:generate_dialog": ("leer", ("menu:menubar.modell_erzeugen",)),
    "dialog:organizer_dialog": ("leer", ("operation:create_organizer", "field:layout")),
    "dialog:rebuild_dialog": ("quader.exakt", ("tree.row:obj_1", "selection.rebuild")),
    "dialog:variants_dialog": (
        "parameter.exakt",
        ("tree.row:obj_1", "menu:menubar.varianten_erzeugen"),
    ),
    "dialog:sketch_editor_dialog": (
        "quader.exakt",
        (
            "menu:menubar.bausteinkatalog",
            "part:seal_gasket",
            "dialog.accept",
            "field:path_sketch",
        ),
    ),
    "meldung:confirm_discard": (
        "kasten_runden.exakt",
        (
            "tree.row:obj_1",
            "menu:menubar.rueckgaengig",
            "menu:menubar.rueckgaengig",
            "history.row:2",
            "history:insert",
        ),
    ),
    "meldung:remove_history_operations": (
        "quader.exakt",
        ("tree.row:obj_1", "history.row:1", "history:delete"),
    ),
    # Die Frage vor dem Export mit Befund: Speichern im Dialog von Qt
    # (``test_guide_dialog_wrapper.py``).
    "meldung:_go_on_despite": (
        "export_gemischt",
        ("tree.row:obj_1", "tree.row:obj_2", "menu:menubar.exportieren", "dialog.accept"),
    ),
}

#: Zeilen, die der Sprachfall noch nicht erreicht, je mit dem Grund (FD-175). Der
#: Wächter unten hält die Liste genau: Eine Zeile, die einen Weg bekommt, muss hier
#: heraus, und keine neue Zeile ohne Weg kommt still dazu.
STILL_WITHOUT: dict[str, str] = {
    "dialog:ai_disclosure_dialog": "Chat-Starter ohne Wortschatznamen",
    "dialog:local_privacy_dialog": "Verweis im KI-Hinweis ohne Wortschatznamen",
    "dialog:offline_activation_dialog": "Zustand „nicht aktiviert“ im Sprachfall",
    "dialog:update_dialog": "neue Version nur über das Netz",
    "dialog:donation_open_error_dialog": "Browser, der nicht öffnet",
    "meldung:open_donation": "Browser, der nicht öffnet",
    "meldung:open_link": "Browser, der nicht öffnet",
    "meldung:_choose_address": "Ort eines Dienstes ohne Wortschatznamen",
    "meldung:_show_details": "Installation, die scheitert",
    "dialog:filament_override_dialog": "Filamentzeile im Kopf ohne Wortschatznamen",
    "dialog:slicer_spool_dialog": "Übernahme aus dem Slicer ohne Wortschatznamen",
    "dialog:usage_dialog": "Spule am Projekt und Export ohne Tippen",
    "meldung:_assign_inventory_spool": "Spule in der Schnellwahl",
    "meldung:_show_slicer_output": "Slicer, der beim Schneiden abbricht",
    "dialog:outline_dialog": "Szene mit SVG-Quelle",
    "dialog:step_bodies_dialog": "Szene mit mehrteiliger STEP-Datei",
    "meldung:_ask_recovery": "Sicherung neben dem zuletzt geöffneten Projekt",
    "dialog:comfy_setup_dialog": "ComfyUI ohne Modell",
    "meldung:confirm_generation_loss": "laufende Erzeugung",
    "dialog:expression_dialog": "Skizzenwortschatz",
    "dialog:point_dialog": "Skizzenwortschatz",
    "dialog:new_plane_dialog": "Skizzenwortschatz",
    "meldung:change_constraint_value": "Skizzenwortschatz",
    "dialog:panel_window": "Reiter rechts ohne Wortschatznamen",
    "startup.expired_demo": "Startfall nur auf Deutsch",
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


def test_no_row_of_any_package_is_without_a_way(rows: dict[str, dict[str, Any]]) -> None:
    """Keine Zeile ohne erreichte Fläche, in allen Paketen (FD-175).

    Vorher hielt der Wächter nur die Liste aus FD-101 (D4, D8, D10); 37 Zeilen in D9
    und D12 und 22 in D1, D2, D7 und D11 hatten keinen Weg, und ihr Sprachfall maß
    sie nie. Was noch fehlt, steht mit Grund in :data:`STILL_WITHOUT` — genau das.
    """
    without = {
        row_id: reason
        for row_id, row in rows.items()
        if (reason := function_surface.without_way(row))
    }
    assert sorted(set(without) - set(STILL_WITHOUT)) == [], without
    assert sorted(set(STILL_WITHOUT) - set(without)) == [], "hat jetzt einen Weg"
    assert not set(REACHED) & set(STILL_WITHOUT)


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


def test_the_three_pins_of_its_scene_are_one_pattern_after_grouping() -> None:
    """``drei_zapfen.netz`` trägt drei Einzelzapfen — weniger, als die Erkennung als
    Muster liest —, und *Als Muster zusammenfassen* macht aus den markierten eines:
    das Beispielziel der Zeile ``group_pattern``. Am Quader ohne gleiche Merkmale
    sagte der Schritt ab."""
    from dataclasses import replace

    from app.core.types import Operation
    from tools import function_scenes

    project = function_scenes.build_scene("drei_zapfen.netz")
    before = function_scenes.evaluate_scene(project).scene.objects["obj_1"].features
    pins = sorted(name for name, feature in before.items() if feature.kind == "pin")
    assert pins == ["pin_1", "pin_2", "pin_3"]
    assert not any(feature.kind == "pattern" for feature in before.values())
    document = project.document
    step = Operation(
        id=max(op.id for op in document.ops) + 1,
        op="group_pattern",
        inputs=("obj_1",),
        outputs=("obj_1",),
        params={"at_features": pins},
    )
    grouped = replace(project, document=replace(document, ops=[*document.ops, step]))
    result = function_scenes.evaluate_scene(grouped)
    assert result.stopped_at is None
    patterns = [
        feature
        for feature in result.scene.objects["obj_1"].features.values()
        if feature.kind == "pattern"
    ]
    assert len(patterns) == 1 and patterns[0].params.get("grouped") is True


def test_every_filament_of_the_body_in_its_scene_is_taken() -> None:
    """``sieben_filamente.netz``: Der Körper trägt die Filamente 1 bis 7 — mehr hat das
    Feld nicht (``MAX_SLOTS``), und eine Spule aus dem Lager bekommt keine freie Nummer.
    Nur dann fragt es, welches Filament sie ersetzt (``message:filament_slot``)."""
    from app.core.export.threemf import slots_for_object
    from app.core.types import MAX_SLOTS
    from tools import function_scenes

    scene = function_scenes.load_scenes()["sieben_filamente.netz"]
    assert scene.spools, "ohne Spule im Lager gibt es nichts zu ersetzen"
    result = function_scenes.evaluate_scene(function_scenes.build_scene(scene.key))
    taken = {slot.index for slot in slots_for_object(result.scene.objects["obj_1"])}
    assert set(range(1, MAX_SLOTS)) <= taken, sorted(taken)
