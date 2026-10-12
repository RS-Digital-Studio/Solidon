"""Die Funktionsliste des Funktionsdurchgangs steht vollständig (Konzept §3, §6; RM-737).

``tools/function_list.py`` erzeugt die Zeilen aus Register, Dialogklassen,
Wortschatz und Befundhandlungen. Hier stehen die Wächter im Tor, ohne Fenster:
Jede Operation hat genau ein Paket und eine Startszene, jede Dialogklasse eine
Zeile mit Paket, die leichten Szenen zeigen ihre Merkmalsart an beiden Kernen,
die schweren sind gültige Stapel, und jede Spezifikation trifft, was es gibt.
Rot ist nur, was fehlt — eine Zeile ohne Spezifikation bleibt „ungeprüft“.

Jeder Wächter hat seine Gegenprobe: eine erfundene Operation mit neuer
Merkmalsart, eine erfundene Dialogklasse, eine Spezifikation zu einer
unbekannten Kennung.
"""

from __future__ import annotations

import dataclasses
import json
import re
import tomllib
from collections import Counter
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from app.core.bootstrap import load_operations
from app.core.guides import TARGETS, dialog_name
from app.core.registry import CATEGORIES, FEATURE_KINDS, REGISTRY
from app.core.registry.surfaces import catalogue_operations
from tests.helpers import exact_kernel
from tools import function_list as fl

DATA = Path(__file__).resolve().parent / "data"
VOCABULARY = DATA / "customer_vocabulary.json"
GOALS = DATA / "common_goals.toml"

#: Kundenkennungen der Fragebögen (``S-20261006-5be329``) gehören nicht in den
#: Korpus — er wird veröffentlicht.
CUSTOMER_ID = re.compile(r"S-\d{8}-[0-9a-f]{6}")


@pytest.fixture(scope="module")
def ui_sources() -> dict[str, str]:
    """Die Quelltexte unter ``app/ui`` einmal je Modul gelesen."""
    return fl.ui_sources()


@pytest.fixture(scope="module")
def rows(ui_sources: dict[str, str]) -> list[fl.Row]:
    """Die erzeugte Liste ohne Fensterbefehle, einmal je Modul."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(fl, "ui_sources", lambda root=fl.UI: ui_sources)
        return fl.rows()


@pytest.fixture
def cached_sources(monkeypatch: pytest.MonkeyPatch, ui_sources: dict[str, str]) -> dict[str, str]:
    """Eine veränderbare Kopie der Quelltexte, die :func:`fl.ui_sources` liefert."""
    copy = dict(ui_sources)
    monkeypatch.setattr(fl, "ui_sources", lambda root=fl.UI: copy)
    return copy


def _by_id(found: list[fl.Row]) -> dict[str, fl.Row]:
    return {row.id: row for row in found}


# --- Zählung -------------------------------------------------------------------


def test_the_list_finds_enough_to_mean_something(
    rows: list[fl.Row], ui_sources: dict[str, str]
) -> None:
    """Zuerst zählen: Wer zu wenig findet, schweigt, und Schweigen sieht grün aus.

    Mindestens 150 Operationen im Register, 40 Dialogklassen und 30 feste
    Ziele (Bauplan D0 §4.2), und jede davon steht in der Liste.
    """
    load_operations()
    operations = list(REGISTRY.all())
    classes = fl.window_classes_in(ui_sources)
    assert len(operations) >= 150, f"nur {len(operations)} Operationen im Register"
    assert len(classes) >= 40, f"nur {len(classes)} Dialogklassen unter app/ui"
    assert len(TARGETS) >= 30, f"nur {len(TARGETS)} feste Ziele im Wortschatz"

    kinds = Counter(row.kind for row in rows)
    sources = Counter(row.source for row in rows)
    assert kinds["operation"] == len(operations) - len(catalogue_operations()) + 1
    assert sources["dialogklasse"] == len(classes)
    assert sources["wortschatz"] == len(TARGETS) + 1, "dazu start.recent:1"
    assert sources["fensteraktion"] >= 1
    assert sources["befundhandlung"] >= 15
    assert sources["verlauf"] >= 4
    assert {row.package for row in rows} == set(fl.PACKAGES), "jedes Paket hat Zeilen"


def test_every_row_carries_its_fields(rows: list[fl.Row]) -> None:
    """Art, Quelle und Paket aus den geschlossenen Listen, jede Kennung einmal."""
    assert len({row.id for row in rows}) == len(rows)
    for row in rows:
        assert row.kind in fl.ROW_KINDS, row
        assert row.source in fl.ROW_SOURCES, row
        assert row.package in fl.PACKAGES, row
        assert row.requirement, row
        assert row.target, row


# --- Pakete --------------------------------------------------------------------


def test_every_category_has_one_package_and_no_more() -> None:
    """Die Kategorieregel aus Konzept §6 deckt jede Kategorie des Registers, ohne Rest."""
    assert set(fl.CATEGORY_PACKAGES) == set(CATEGORIES)
    assert set(fl.CATEGORY_PACKAGES.values()) <= set(fl.PACKAGES)


def test_every_operation_belongs_to_exactly_one_package(rows: list[fl.Row]) -> None:
    """Jede Operation steht in genau einer Zeile — eigener oder ``part:*`` — und hat
    genau ein Paket."""
    found = _by_id(rows)
    covered = Counter(
        name for row in rows if row.kind == "operation" for name in (row.covers or (row.id,))
    )
    names = {spec.name for spec in REGISTRY.all()}
    assert set(covered) == names
    assert all(count == 1 for count in covered.values()), covered.most_common(3)
    for spec in REGISTRY.all():
        row = found.get(spec.name, found[fl.CATALOGUE_ROW])
        assert row.package == fl.package_of_operation(spec)


def test_the_catalogue_is_one_row_over_all_its_tiles(rows: list[fl.Row]) -> None:
    """Konzept §3: Die Kacheln des Bausteinkatalogs sind eine Zeile mit einem Lauf über alle."""
    catalogue = _by_id(rows)[fl.CATALOGUE_ROW]
    assert set(catalogue.covers) == catalogue_operations()
    assert len(catalogue.covers) >= 80
    assert catalogue.package == "D2"


def test_only_gesture_operations_leave_their_category() -> None:
    """Die einzige Ausnahme von der Kategorie ist D6: Operationen mit Gestenparameter."""
    gestures = [
        spec.name
        for spec in REGISTRY.all()
        if any(entry.kind in fl.GESTURE_KINDS for entry in spec.params.spec())
    ]
    assert sorted(gestures) == ["pose_armature", "sculpt_strokes"]
    for spec in REGISTRY.all():
        expected = "D6" if spec.name in gestures else fl.CATEGORY_PACKAGES[spec.category]
        assert fl.package_of_operation(spec) == expected, spec.name


def test_every_dialog_class_has_a_row_with_its_package(
    rows: list[fl.Row], ui_sources: dict[str, str]
) -> None:
    """Jede Dialog- und Fensterklasse unter ``app/ui`` hat eine Zeile; die Tabellen tragen
    keine Klasse, die es nicht mehr gibt, und keine steht in beiden."""
    classes = fl.window_classes_in(ui_sources)
    found = _by_id(rows)
    for name in classes:
        row = found[f"dialog:{dialog_name(name)}"]
        assert row.source == "dialogklasse" and row.package in fl.PACKAGES
    assert not set(fl.DIALOG_OPERATIONS) & set(fl.DIALOG_SURFACES)
    assert set(fl.DIALOG_OPERATIONS) | set(fl.DIALOG_SURFACES) == set(classes)


def test_a_dialog_of_one_operation_goes_with_it(rows: list[fl.Row]) -> None:
    """Konzept §6: Ein Dialog, der genau einer Operation dient, geht in deren Paket.

    Der Dichtweg-Editor entsteht nur für ``create_seal`` (``op_dialog``), die
    Fachaufteilung nur für die Parameterart ``organizer``.
    """
    found = _by_id(rows)
    for name, operation in fl.DIALOG_OPERATIONS.items():
        assert REGISTRY.has(operation), name
        dialog = found[f"dialog:{dialog_name(name)}"]
        assert dialog.package == found[operation].package, name
        assert dialog.requirement == found[operation].requirement, name
    organizers = [
        spec.name
        for spec in REGISTRY.all()
        if any(entry.kind == "organizer" for entry in spec.params.spec())
    ]
    assert organizers == [fl.DIALOG_OPERATIONS["OrganizerDialog"]]


def test_every_fixed_target_has_a_row_and_every_table_line_is_used(rows: list[fl.Row]) -> None:
    """Jedes feste Ziel des Wortschatzes ist eine Zeile; eine Tabellenzeile ohne Ziel fällt auf."""
    found = _by_id(rows)
    assert set(TARGETS) <= set(found)
    assert set(fl.TARGET_SURFACES) <= set(found), "Tabellenzeile ohne erzeugte Zeile"


def test_the_feature_window_rows_come_from_the_action_keys(rows: list[fl.Row]) -> None:
    """Die Handlungen des Merkmalfensters ohne eigene Operation sind Zeilen unter dem
    Schlüssel, den ``FeatureAction.key`` trägt — Baustein in D2, Textur und Kantenvariante
    mit ihrer Operation (Konzept §6)."""
    from app.core.perceive.actions import EDGE_VARIANT_KEYS, PART_ACTION_KEYS, TEXTURE_ACTION_KEYS

    found = _by_id(rows)
    for key in PART_ACTION_KEYS:
        assert found[f"feature:{key}"].package == "D2"
        assert found[f"feature:{key}"].start_scene.startswith("baustein.")
    for key in TEXTURE_ACTION_KEYS:
        assert found[f"feature:{key}"].package == found["apply_texture"].package
        assert found[f"feature:{key}"].start_scene == "merkmal.pattern.netz"
    assert EDGE_VARIANT_KEYS
    for key in EDGE_VARIANT_KEYS:
        row = found[f"edge:{key}"]
        assert row.package == found[key.split(".")[0]].package and row.requirement == "kante"


def test_every_surface_row_names_a_target_of_the_vocabulary(rows: list[fl.Row]) -> None:
    """Jede Zeile zeigt auf ein Ziel des Wortschatzes — sonst findet der Prüfstand sie nicht."""
    from app.core.guides import is_target

    wrong = [row.id for row in rows if not is_target(row.target)]
    # ``guides.dialog_name`` lässt den führenden Unterstrich von ``_PanelWindow``
    # stehen, und ``dialog:`` verlangt einen Buchstaben vorn: Das abgelöste
    # Kartenfenster hat damit kein Ziel (Bericht D0-L, gemeldet an W). Behebt W
    # es, wird diese Zeile rot und fällt weg.
    assert wrong == ["dialog:_panel_window"]


def test_window_actions_outside_the_menu_bar_have_rows(
    rows: list[fl.Row], ui_sources: dict[str, str]
) -> None:
    """Was das Fenster nur in die Auswahlkarte hängt (*Automatisch teilen*), ist eine
    Zeile; die Tabelle trägt keine Kennung, die es nicht mehr gibt."""
    keys = fl.scan_ui(ui_sources).window_actions
    assert "edit.auto_split" in keys
    assert set(fl.WINDOW_ACTION_PACKAGES) == set(keys)
    assert _by_id(rows)["command:edit.auto_split"].package == "D8"


def test_the_history_entries_come_from_the_context_menu(ui_sources: dict[str, str]) -> None:
    """Die Verlaufszeilen kommen aus den Objektnamen ``history.*`` — die vier, unter denen
    die Bildanleitungen sie schon finden, sind dabei."""
    entries = fl.history_entries(ui_sources)
    assert {"edit", "insert", "switch", "delete"} <= set(entries)


# --- Anforderung und Szene --------------------------------------------------------


def test_every_operation_has_a_start_scene(rows: list[fl.Row]) -> None:
    """Jede Anforderung einer Operation hat eine Szene im Katalog (§2.5)."""
    scenes = fl.load_scenes()
    assert fl.missing_scenes(rows) == []
    for row in rows:
        if row.kind == "operation":
            assert row.start_scene in scenes, row


def test_the_whole_list_has_no_problem() -> None:
    """Der Weg des Tors und der Kommandozeile (``--check``) findet am Bestand nichts."""
    assert fl.problems() == []


def test_an_invented_operation_with_a_new_feature_kind_turns_red(
    monkeypatch: pytest.MonkeyPatch, cached_sources: dict[str, str]
) -> None:
    """Gegenprobe: Eine Operation an einer Merkmalsart ohne Szene ist der eine Rotfall."""
    invented = dataclasses.replace(
        REGISTRY.get("drill_hole"), name="cut_gear_teeth", applies_to=("gear",)
    )
    known = list(REGISTRY.all())
    monkeypatch.setattr(REGISTRY, "all", lambda: [*known, invented])

    found = fl.problems()

    assert any(issue.startswith("cut_gear_teeth:") and "merkmal:gear" in issue for issue in found)
    assert all("cut_gear_teeth" in issue for issue in found), found


def test_an_invented_dialog_class_turns_red(cached_sources: dict[str, str]) -> None:
    """Gegenprobe: Eine Dialogklasse ohne Zuordnung hält die Liste an — auch eine, die
    erst über eine eigene Basis in einem anderen Modul ein Dialog ist."""
    cached_sources["app/ui/invented/base.py"] = "class _InventedBase(QDialog):\n    pass\n"
    cached_sources["app/ui/invented/dialog.py"] = "class InventedDialog(_InventedBase):\n    pass\n"

    found = fl.problems()

    assert any("InventedDialog" in issue and "unbekannte Dialogklasse" in issue for issue in found)
    assert any("_InventedBase" in issue for issue in found)


def test_a_class_name_twice_is_not_guessed(cached_sources: dict[str, str]) -> None:
    """Die Zuordnung geht nach dem Klassennamen; zweimal derselbe Name hält an (Regel 21)."""
    cached_sources["app/ui/invented/twin.py"] = "class SettingsDialog(QDialog):\n    pass\n"

    found = fl.problems()

    assert any("SettingsDialog" in issue and "mehreren Modulen" in issue for issue in found)


def test_the_dialog_search_follows_qt_dialog_subclasses() -> None:
    """Ein ``QMessageBox`` ist ein Dialog; eine Klasse ohne Fensterbasis nicht."""
    found = fl.window_classes_in(
        {
            "a.py": "class Box(QtWidgets.QMessageBox):\n    pass\n",
            "c.py": "class Plain(QWidget):\n    pass\n",
            "b.py": "def make():\n    class Nested(Box):\n        pass\n",
        }
    )
    assert set(found) == {"Box", "Nested"}


# --- Szenen ------------------------------------------------------------------------


def _scenes() -> dict[str, fl.Scene]:
    return fl.load_scenes()


def _light(kernel: str) -> list[str]:
    return [
        key
        for key, scene in _scenes().items()
        if scene.project and not scene.heavy and (scene.kernel or "netz") == kernel
    ]


def test_the_recipes_are_valid() -> None:
    """Basis, Operationen, Quellen, Kern und Zusagen jeder Szene, ohne zu rechnen."""
    assert fl.validate_scenes(_scenes()) == []


def test_every_feature_kind_has_a_scene_on_both_kernels() -> None:
    """Je Merkmalsart aus ``FEATURE_KINDS`` eine Szene am exakten und am Netzkern; eine
    Art ohne exakten Körper (offener Rand) nur am Netz."""
    scenes = _scenes()
    for kind in FEATURE_KINDS:
        for kernel in fl.KERNELS:
            key = f"merkmal.{kind}.{kernel}"
            if kernel == fl.EXACT and kind in fl.MESH_ONLY_KINDS:
                assert key not in scenes
                continue
            assert key in scenes, key
            assert kind in scenes[key].promises["kinds"], key


@pytest.mark.parametrize("key", _light(fl.MESH))
def test_a_light_mesh_scene_keeps_its_promises(key: str) -> None:
    """Die leichte Szene rechnet und hält, was sie zusagt: Körper, Bauart, Merkmalsarten,
    Körperzustand, Befunde, Halt."""
    scenes = _scenes()
    result = fl.evaluate_scene(fl.build_scene(key, scenes))
    assert fl.broken_promises(scenes[key], result) == []


@pytest.mark.parametrize("key", _light(fl.EXACT))
def test_a_light_exact_scene_keeps_its_promises(key: str) -> None:
    """Dasselbe am exakten Kern — lokal nur mit OpenCASCADE, in der CI Pflicht."""
    exact_kernel()
    scenes = _scenes()
    result = fl.evaluate_scene(fl.build_scene(key, scenes))
    assert fl.broken_promises(scenes[key], result) == []


def test_there_are_light_scenes_on_both_kernels() -> None:
    """Die Parametrisierung darüber ist nicht leer."""
    assert len(_light(fl.MESH)) >= 15
    assert len(_light(fl.EXACT)) >= 15


@pytest.mark.parametrize("key", [key for key, scene in _scenes().items() if scene.heavy])
def test_a_heavy_scene_is_a_valid_stack(key: str) -> None:
    """Schwere Szenen rechnet nur der Werkzeuglauf; hier nimmt ``History.apply`` jeden
    Schritt an, und die Zusage nennt Dreiecke oder Sekunden."""
    scenes = _scenes()
    project = fl.build_scene(key, scenes)
    _sources, steps = fl.recipe(key, scenes)
    assert len(project.document.ops) == len(steps) >= 2
    assert {"triangles_over", "seconds_over"} & set(scenes[key].promises)


def test_the_four_heavy_scenes_of_the_plan_are_there() -> None:
    """§2.5: zwei langsame, eine über der Erkennungsgrenze, eine über der groben Vorschau."""
    heavy = {key for key, scene in _scenes().items() if scene.heavy}
    assert heavy == {"langsam_2s", "langsam_10s", "ueber_erkennungsgrenze", "ueber_grober_vorschau"}


def test_the_promise_check_sees_a_broken_promise() -> None:
    """Gegenprobe des Prüfers: Ein Quader zeigt keine Bohrung, hat einen Körper und hält nicht."""
    scenes = _scenes()
    scene = dataclasses.replace(
        scenes["quader.netz"],
        promises={"objects": 2, "kinds": ["hole"], "stops": True, "findings": ["x.y"]},
    )
    result = fl.evaluate_scene(fl.build_scene("quader.netz", scenes))

    broken = fl.broken_promises(scene, result)

    assert len(broken) == 4, broken


def test_a_broken_recipe_is_named() -> None:
    """Gegenprobe der Rezeptprüfung: unbekannte Operation, fehlende Quelle, Basis im Kreis."""
    scenes = {
        "a": fl.Scene(key="a", summary="a", base="b"),
        "b": fl.Scene(key="b", summary="b", base="a"),
        "c.netz": fl.Scene(
            key="c.netz",
            summary="c",
            kernel="netz",
            sources={"src_1": "meshes/gibt_es_nicht.stl"},
            ops=(fl.SceneStep(op="gibt_es_nicht"),),
        ),
    }
    found = fl.validate_scenes(scenes)
    assert any("Kreis" in issue for issue in found)
    assert any("gibt_es_nicht.stl" in issue for issue in found)
    assert any("'gibt_es_nicht'" in issue for issue in found)


def test_generated_scenes_never_land_in_the_tree(tmp_path: Path) -> None:
    """Die Datei aus einem Rezept wird nicht abgelegt (``tests/data/CLAUDE.md``)."""
    with pytest.raises(fl.FunctionListError):
        fl.save_scenes(DATA / "erzeugt")
    assert not (DATA / "erzeugt").exists()
    written = fl.save_scenes(tmp_path)
    assert len(written) >= 30
    assert all(path.suffix == ".p3d" and path.stat().st_size > 0 for path in written)
    # Prüfpunkt 16 wechselt aus einer Rechnung in ein zweites Projekt; der
    # Prüfstand öffnet beide als Datei.
    names = {path.name for path in written}
    assert {"leer.p3d", "zweites_projekt.p3d", "merkmal.hole.exakt.p3d"} <= names
    assert not any(name.startswith(("startbildschirm", "langsam_")) for name in names)


# --- Auswahlweg --------------------------------------------------------------------


def test_every_selecting_row_carries_its_selection_clicks(rows: list[fl.Row]) -> None:
    """``next_click`` wählt nichts aus; den Auswahlklick trägt die Zeile, abgeleitet aus
    ihrer Anforderung — Körper, mehrere Körper mit Strg, Merkmal, Befund."""
    from app.core.guides import is_target

    assert fl.missing_selections(rows) == []
    found = _by_id(rows)

    def targets(row_id: str) -> list[tuple[str, str]]:
        return [(step["target"], step["modifier"]) for step in found[row_id].route]

    assert targets("resize_hole") == [("tree.row:obj_1.hole_1", "")]
    assert targets("drill_hole") == [("tree.row:obj_1.face_6", "")]
    assert targets("repair") == [("tree.row:obj_1.edge_loop_1", "")]
    assert targets("union_objects") == [("tree.row:obj_1", ""), ("tree.row:obj_2", "ctrl")]
    assert targets("mirror_object") == [("tree.row:obj_1", "")]
    assert targets("finding.action:place_on_bed") == [("finding:arrange.below_bed", "")]
    assert targets("feature:part.move") == [("tree.row:obj_1.screw_hole_bore_1", "")]
    assert targets("create_box") == [] and targets("arrange_bed") == []
    steps = [step for row in rows for step in row.route]
    assert len(steps) >= 100
    assert all(is_target(step["target"]) and step["button"] == "left" for step in steps)


def test_a_feature_scene_without_its_selection_turns_red(
    monkeypatch: pytest.MonkeyPatch, cached_sources: dict[str, str]
) -> None:
    """Gegenprobe: Nennt eine Merkmalsszene kein gewähltes Merkmal, fehlt allen Zeilen
    darauf der Auswahlweg — das ist rot, nicht still leer."""
    scenes = fl.load_scenes()
    scenes["merkmal.hole.exakt"] = dataclasses.replace(scenes["merkmal.hole.exakt"], select="")
    monkeypatch.setattr(fl, "load_scenes", lambda path=fl.SCENES: scenes)

    found = fl.problems()

    assert any(issue.startswith("resize_hole:") and "Auswahlweg" in issue for issue in found)


def test_the_promise_check_sees_a_wrong_selection() -> None:
    """Gegenprobe: Ein gewähltes Merkmal, das es nicht gibt oder das die falsche Art hat."""
    scenes = fl.load_scenes()
    result = fl.evaluate_scene(fl.build_scene("merkmal.hole.netz", scenes))
    missing = dataclasses.replace(scenes["merkmal.hole.netz"], select="obj_1.hole_9")
    wrong = dataclasses.replace(scenes["merkmal.hole.netz"], select="obj_1.face_1")
    assert any("gibt es nicht" in issue for issue in fl.broken_promises(missing, result))
    assert any("nicht hole" in issue for issue in fl.broken_promises(wrong, result))


# --- Zeilenspezifikationen ---------------------------------------------------------


def test_an_unknown_id_in_a_spec_turns_red(
    monkeypatch: pytest.MonkeyPatch, cached_sources: dict[str, str]
) -> None:
    """Gegenprobe: Eine Spezifikation, die keine erzeugte Zeile trifft, ist rot."""
    monkeypatch.setattr(
        fl,
        "load_specs",
        lambda directory=fl.ROW_SPECS: {
            "gibt_es_nicht": {"package": "D4", "file": "d04.toml", "example_goal": "x"}
        },
    )
    found = fl.problems()
    assert any("gibt_es_nicht" in issue and "keine erzeugte Zeile" in issue for issue in found)


def test_a_row_without_a_spec_stays_green(
    monkeypatch: pytest.MonkeyPatch, cached_sources: dict[str, str]
) -> None:
    """Eine Zeile ohne Spezifikation ist „ungeprüft“ und macht das Tor nicht rot."""
    monkeypatch.setattr(fl, "load_specs", lambda directory=fl.ROW_SPECS: {})
    assert fl.problems() == []
    assert all(row.spec is None for row in fl.rows())


def test_the_probe_rows_cover_every_kind(rows: list[fl.Row]) -> None:
    """Je Art eine Probezeile (Bauplan D0 §1.2): Operation in D4, Befundhandlung in D8,
    Fensterbefehl in D10 — jede mit Beispielziel, Suchproben und Erwartung."""
    specs = fl.load_specs()
    assert {"resize_hole", "finding.action:place_on_bed", "Bearbeiten/Parameter anlegen …"} <= set(
        specs
    )
    found = _by_id(rows)
    assert found["resize_hole"].kind == "operation" and specs["resize_hole"]["package"] == "D4"
    assert found["finding.action:place_on_bed"].package == "D8"
    assert specs["Bearbeiten/Parameter anlegen …"]["package"] == "D10"
    for spec in specs.values():
        assert spec["example_goal"] and spec["search_probes"] and spec["expectation"], spec


def test_a_spec_with_an_unknown_field_or_target_turns_red(rows: list[fl.Row]) -> None:
    """Gegenprobe: ein Feld, das die Operation nicht hat, ein Ziel außerhalb des Wortschatzes,
    eine Szene, die es nicht gibt, ein Menüpfad, den die Quelle nicht kennt."""
    bad = {
        "resize_hole": {
            "package": "D4",
            "file": "d04.toml",
            "start_scene": "gibt_es_nicht",
            "example_goal": "x",
            "inputs": {"feature.field:resize_hole.durchmesser": 8.0, "Feld:Durchmesser": 1.0},
        },
        "Bearbeiten/Gibt es nicht …": {"package": "D10", "file": "d10.toml"},
    }
    found = fl.validate_specs(rows, bad, fl.load_scenes())
    assert any("durchmesser" in issue for issue in found)
    assert any("Feld:Durchmesser" in issue for issue in found)
    assert any("gibt_es_nicht" in issue for issue in found)
    assert any("Gibt es nicht" in issue and "Menüpfad" in issue for issue in found)


# --- Wortliste und Kundenziele -------------------------------------------------------


def _vocabulary() -> dict[str, Any]:
    data: dict[str, Any] = json.loads(VOCABULARY.read_text(encoding="utf-8"))
    return data


def _words(part: str) -> Iterator[dict[str, Any]]:
    yield from _vocabulary()[part]


def test_the_vocabulary_has_its_shape() -> None:
    """Je Eintrag Wort, Sprache, Muster und Wächter; die Muster kompilieren und treffen ihr Wort."""
    negative = list(_words("negative"))
    positive = list(_words("positive"))
    assert len(negative) >= 30 and len(positive) >= 30
    for entry in negative:
        assert entry["language"] in {"de", "en"}, entry
        assert entry["guarded"] in {"konstrukteurswort", "designer_word", "fachwort", None}, entry
        pattern = re.compile(entry["pattern"], re.IGNORECASE if entry["language"] == "en" else 0)
        assert pattern.search(entry.get("example", entry["word"])), entry
    for entry in positive:
        assert entry["language"] in {"de", "en"} and entry["origin"] in {"slicer", "begruendet"}


def test_the_concept_list_is_on_the_negative_list() -> None:
    """Die Negativliste aus Konzept §4 (V1) steht vollständig in der Datei."""
    words = {entry["word"] for entry in _words("negative") if entry["language"] == "de"}
    named = {"Normale", "wasserdicht", "Voxel", "boolesch", "Facette", "deterministisch", "Mesh"}
    named |= {"B-Rep", "Manifold", "Provenienz", "Bezeichner", "Punktpfad", "True", "False"}
    assert named <= words, named - words


def test_no_word_is_on_both_lists() -> None:
    """Ein Wort der Positivliste trifft kein Muster der Negativliste seiner Sprache."""
    for entry in _words("positive"):
        for negative in _words("negative"):
            if negative["language"] != entry["language"]:
                continue
            flags = re.IGNORECASE if entry["language"] == "en" else 0
            assert not re.search(negative["pattern"], entry["word"], flags), (entry, negative)


def test_the_wording_guards_read_the_vocabulary() -> None:
    """``test_wording`` baut seine Muster aus der Datei — dieselben Wörter, kein Zwilling."""
    from tests import test_wording

    for name, guard in (
        ("KONSTRUKTEURSWORT", "konstrukteurswort"),
        ("DESIGNER_WORD", "designer_word"),
        ("FACHWORT", "fachwort"),
    ):
        pattern = getattr(test_wording, name).pattern
        for entry in _words("negative"):
            if entry["guarded"] == guard:
                assert entry["pattern"] in pattern, (name, entry["word"])


def _goals() -> list[dict[str, Any]]:
    goals: list[dict[str, Any]] = tomllib.loads(GOALS.read_text(encoding="utf-8"))["goal"]
    return goals


def test_the_common_goals_name_what_exists() -> None:
    """Jedes Kundenziel nennt eine Szene, eine Auswahl und ein Ziel, das es gibt."""
    from app.core.guides import is_target

    goals = _goals()
    scenes = _scenes()
    assert len(goals) >= 15
    assert len({goal["id"] for goal in goals}) == len(goals)
    for goal in goals:
        assert goal["origin"] in {"bauplan", "fragebogen"} and goal["ref"], goal
        assert goal["scene"] in scenes, goal
        selection = goal["selection"]
        assert selection in {"koerper", "koerper:2", "kante"} or (
            selection.startswith("merkmal:") and selection.removeprefix("merkmal:") in FEATURE_KINDS
        ), goal
        kind, _colon, name = goal["target"].partition(":")
        assert kind in {"operation", "feature", "edge"}, goal
        assert REGISTRY.has(name.split(".")[0]), goal
        assert is_target(goal["target"]), goal


def test_no_customer_id_reaches_the_corpus() -> None:
    """Der Korpus wird veröffentlicht: keine Kennung eines Fragebogens in den neuen Dateien."""
    files = [VOCABULARY, GOALS, fl.SCENES, *sorted(fl.ROW_SPECS.glob("*.toml"))]
    for path in files:
        assert not CUSTOMER_ID.search(path.read_text(encoding="utf-8")), path


# --- Kommandozeile ---------------------------------------------------------------------


def test_the_command_line_lists_one_package(
    capsys: pytest.CaptureFixture[str], cached_sources: dict[str, str]
) -> None:
    """``--paket D4 --format json`` gibt genau die Zeilen von D4 aus, Markdown dasselbe
    als Tabelle."""
    assert fl.main(["--paket", "D4", "--format", "json"]) == 0
    listed = json.loads(capsys.readouterr().out)
    assert listed and {entry["package"] for entry in listed} == {"D4"}
    assert "resize_hole" in {entry["id"] for entry in listed}

    assert fl.main(["--paket", "D4"]) == 0
    table = capsys.readouterr().out
    assert "`resize_hole`" in table and table.count("\n") == len(listed) + 2


def test_the_list_is_built_without_a_window() -> None:
    """Die Liste baut kein Widget: kein ``QApplication``, kein ``show`` im Werkzeug."""
    source = Path(fl.__file__).read_text(encoding="utf-8")
    assert "QApplication" not in source
    assert ".show(" not in source and ".exec(" not in source


# --- Fensterbefehle am gebauten Fenster (Fenster-CI) -------------------------------


def test_every_menubar_line_becomes_a_row_with_a_package(qt_app: Any) -> None:
    """Am gebauten Fenster: Jede Zeile der Menüleiste, die keine Operation ist, wird
    eine Fensterbefehlszeile mit Paket, und jede Spezifikation mit Menüpfad trifft eine.

    Die Leiste entsteht erst in ``_build_menus``; gelesen wird sie über
    ``guide_targets.menubar_entries``, wie der Prüfstand sie liest.
    """
    from app.ui.guide_targets import menubar_entries
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    entries = [
        fl.MenuEntry(object_name=name, path=(*menus, action.text()))
        for name, menus, action in menubar_entries(window)
    ]
    assert len(entries) >= 60, f"nur {len(entries)} Zeilen in der Menüleiste"

    found = fl.rows(entries)
    commands = [row for row in found if row.source == "menueleiste"]
    assert len(commands) >= 30, f"nur {len(commands)} Fensterbefehle"
    assert {row.package for row in commands} >= {"D1", "D2", "D11", "D12"}
    assert len({row.target for row in commands}) == len(commands), "ein Name, zwei Zeilen"
    by_id = {row.id: row for row in found}
    for row_id, spec in fl.load_specs().items():
        if "/" in row_id:
            assert row_id in by_id, f"{spec['file']}: {row_id} ist keine Zeile der Menüleiste"
            assert by_id[row_id].package == spec["package"]
    assert fl.validate_specs(found, fl.load_specs(), fl.load_scenes()) == []
    used = {row.id.rsplit("/", 1)[-1] for row in commands}
    assert set(fl.COMMAND_PACKAGES) <= used, "Ausnahme ohne Menüzeile"
    assert {row.id.split("/")[0] for row in commands} <= set(fl.MENU_PACKAGES)
