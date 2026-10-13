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
from tools import function_scan as fscan
from tools import function_scenes as fscenes

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
    classes = fscan.window_classes_in(ui_sources)
    assert len(operations) >= 150, f"nur {len(operations)} Operationen im Register"
    assert len(classes) >= 40, f"nur {len(classes)} Dialogklassen unter app/ui"
    assert len(TARGETS) >= 30, f"nur {len(TARGETS)} feste Ziele im Wortschatz"

    kinds = Counter(row.kind for row in rows)
    sources = Counter(row.source for row in rows)
    # Eine Zeile je Operation, der Katalog als eine, und was im Dialog einer
    # anderen steht, in deren Zeile (``SAME_ENTRY``, Probelauf F-21).
    assert kinds["operation"] == len(operations) - len(catalogue_operations()) + 1 - len(
        fl.SAME_ENTRY
    )
    assert sources["dialogklasse"] == len(classes)
    assert sources["wortschatz"] == len(TARGETS) + 1, "dazu start.recent:1"
    assert sources["fensteraktion"] >= 1
    assert sources["befundhandlung"] >= 50, "ohne die Handler nur des Fehlerdialogs"
    assert sources["verlauf"] >= 4
    assert sources["werkzeugzeile"] >= 7 and sources["kontextmenue"] >= 5
    # Seit FD-24 quittiert die Freischaltung im Dialog: sechs Meldungsfenster weniger.
    assert sources["einstellungen"] >= 3 and sources["meldungsfenster"] >= 15
    assert {row.package for row in rows} == set(fl.PACKAGES), "jedes Paket hat Zeilen"


def test_every_row_carries_its_fields(rows: list[fl.Row]) -> None:
    """Art, Quelle und Paket aus den geschlossenen Listen, jede Kennung einmal."""
    assert len({row.id for row in rows}) == len(rows)
    for row in rows:
        assert row.kind in fl.ROW_KINDS, row
        assert row.source in fl.ROW_SOURCES, row
        assert row.package in fl.PACKAGES, row
        assert row.requirement, row
        # Jede Zeile trägt ein Ziel — auch Meldungsfenster und Einstellungsabschnitte
        # (Durchsicht welle4 D-L6: die Duldung ohne Ziel war leer und verdeckte
        # eine Zeile, die ihr Ziel verliert).
        assert row.target, row
        assert row.spec is None or not {"package", "file"} & set(row.spec), row


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
        row = found.get(spec.name) or next(
            row for row in rows if row.kind == "operation" and spec.name in row.covers
        )
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
    classes = fscan.window_classes_in(ui_sources)
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
    from app.core.guides import action_key, action_target
    from app.core.perceive.actions import edge_actions

    variants = {
        action_target(action) for action in edge_actions("probe") if action_key(action) != action.op
    }
    assert variants == {row.id for row in rows if row.id.startswith("edge:")}
    for key in EDGE_VARIANT_KEYS:
        row = found[f"edge:{key}"]
        assert row.package == found[key.split(".")[0]].package and row.requirement == "kante"


def test_the_expired_demo_is_a_row_of_its_own(rows: list[fl.Row]) -> None:
    """„Demo abgelaufen“ startet die Anwendung nicht; das ist eine eigene Zeile in D12.

    Gehalten am Startweg selbst: ``app/ui/app.py`` ruft die Funktion der Tabelle
    unter ``state.over`` und kehrt danach zurück, und die Funktion gibt es.
    """
    import ast
    import importlib

    row = _by_id(rows)["startup.expired_demo"]
    assert row.package == "D12" and row.source == "startablauf"
    module, function = "app.ui.dialogs", "show_expired_demo"
    assert fl.RAW_WINDOW_IDS["show_expired_demo"] == "startup.expired_demo"
    assert callable(getattr(importlib.import_module(module), function))
    tree = ast.parse((fl.UI / "app.py").read_text(encoding="utf-8"))
    guarded = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and ast.unparse(node.test) == "state.over"
        and any(
            isinstance(call, ast.Call) and ast.unparse(call.func) == function
            for call in ast.walk(node)
        )
        and isinstance(node.body[-1], ast.Return)
    ]
    assert len(guarded) == 1


def test_every_surface_row_names_a_target_of_the_vocabulary(rows: list[fl.Row]) -> None:
    """Jede Zeile zeigt auf ein Ziel des Wortschatzes — sonst findet der Prüfstand sie nicht."""
    from app.core.guides import is_target

    wrong = [row.id for row in rows if not is_target(row.target)]
    assert wrong == []
    assert _by_id(rows)["startup.expired_demo"].target == "dialog:expired_demo"


def test_window_actions_outside_the_menu_bar_have_rows(
    rows: list[fl.Row], ui_sources: dict[str, str]
) -> None:
    """Was das Fenster nur in die Auswahlkarte hängt (*Automatisch teilen*), ist eine
    Zeile; die Tabelle trägt keine Kennung, die es nicht mehr gibt."""
    keys = fscan.scan_ui(ui_sources).window_actions
    assert "edit.auto_split" in keys
    assert set(fl.WINDOW_ACTION_PACKAGES) == set(keys)
    assert _by_id(rows)["command:edit.auto_split"].package == "D8"


def test_the_finding_actions_come_from_the_kernel_and_the_table(rows: list[fl.Row]) -> None:
    """Befundhandlung ist, was an einem Befund ankommen kann: ``FINDING_ACTIONS`` und
    die Vorschläge des Kerns, soweit das Fenster sie ausführt (``MainWindow.error_handlers``)
    — ohne die Handlungen, die nur ein Fehlerdialog anbietet (Aktivierung, Chat, Update,
    Speichern, Übergabe). Jeder Handler des Fensters ist genau eines von beiden."""
    from app.ui.panels import FINDING_ACTIONS

    found = {
        row.id.removeprefix("finding.action:") for row in rows if row.source == "befundhandlung"
    }
    handled = fl.report_handlers()
    table = {action.id for actions in FINDING_ACTIONS.values() for action in actions}
    dialog_only = set(fl.ERROR_DIALOG_ACTIONS)
    assert found == ((fl.kernel_action_ids() | table) & handled) - dialog_only
    assert found | dialog_only == handled and not found & dialog_only
    assert len(found) >= 40
    for name in ("activate_offline", "buy_licence", "set_up_chat", "open_download_page"):
        assert fl.ERROR_DIALOG_ACTIONS[name] == "D12", name
    assert fl.ERROR_DIALOG_ACTIONS["save_elsewhere"] == "D1"
    assert set(fl.ERROR_DIALOG_ACTIONS.values()) <= set(fl.PACKAGES)
    by_id = _by_id(rows)
    assert by_id["finding.action:change_selection"].start_scene == "halt"
    assert by_id["finding.action:correct_input"].start_scene == "halt"
    assert by_id["finding.action:use_reachable"].start_scene == "zu_fein.netz"
    assert by_id["finding.action:orient_for_print"].start_scene


def test_every_finding_action_has_a_scene_or_a_named_reason(rows: list[fl.Row]) -> None:
    """Jede Befundhandlung beginnt in einer Szene, deren Befund sie trägt — oder sie steht
    mit Grund in ``FINDING_ACTIONS_WITHOUT_SCENE``. Beides zugleich ist ein Widerspruch,
    eine neue Handlung ohne beides fällt auf. Die Tabelle ist leer (Konzept §10, FD-6):
    Keine Zeile bleibt ungeprüft."""
    without = {
        row.id.removeprefix("finding.action:")
        for row in rows
        if row.source == "befundhandlung" and not row.start_scene
    }
    assert without == set(fl.FINDING_ACTIONS_WITHOUT_SCENE)
    assert fl.FINDING_ACTIONS_WITHOUT_SCENE == {}


def test_an_unknown_handler_turns_red(cached_sources: dict[str, str]) -> None:
    """Gegenprobe: Ein Handler des Fensters, der weder Befundhandlung noch nur im
    Fehlerdialog erreichbar ist, hält die Liste an."""
    cached_sources["app/ui/invented/handlers.py"] = (
        "class MainWindow:\n    def error_handlers(self):\n        return {'magic_wand': None}\n"
    )
    found = fl.problems()
    assert any("magic_wand" in issue for issue in found), found


def test_the_tools_under_the_view_are_rows(rows: list[fl.Row], ui_sources: dict[str, str]) -> None:
    """Jedes Werkzeug der Zeile unter der Ansicht (``tools.add``) ist eine Zeile ``tool:``,
    gelesen aus dem Quelltext; die Pakettabelle trägt keinen toten Schlüssel."""
    tools = fscan.scan_ui(ui_sources).tools
    assert {"section", "measure", "transform", "analysis", "layers", "explode", "split"} <= set(
        tools
    )
    assert set(fl.TOOL_PACKAGES) == set(tools)
    found = _by_id(rows)
    assert found["tool:layers"].package == "D8" and found["tool:transform"].package == "D3"
    assert found["tool:section"].package == "D11" and found["tool:split"].package == "D8"


def test_the_named_context_actions_are_rows(rows: list[fl.Row], ui_sources: dict[str, str]) -> None:
    """Die benannten Kontextaktionen von Baum und Parameterleiste sind Zeilen ``menu:``."""
    names = fscan.scan_ui(ui_sources).context_actions
    assert {
        "tree.step",
        "tree.sketch",
        "tree.visibility",
        "tree.isolate",
        "parameters.edit",
    } <= set(names)
    assert set(fl.CONTEXT_PACKAGES) == set(names)
    found = _by_id(rows)
    assert found["menu:tree.sketch"].package == "D7"
    assert found["menu:tree.visibility"].package == "D11"
    assert found["menu:parameters.edit"].package == "D10"


def test_every_settings_section_is_a_row(rows: list[fl.Row], ui_sources: dict[str, str]) -> None:
    """Konzept §3: Die Einstellungen sind eine Zeile je Abschnitt des Dialogs."""
    sections = fscan.scan_ui(ui_sources).settings_sections
    assert {"Anwendung", "Vorgaben für neue Projekte", "Weitere Einstellungen"} <= set(sections)
    found = _by_id(rows)
    assert found["setting.section:vorgaben_fuer_neue_projekte"].package == "D12"
    assert len([row for row in rows if row.source == "einstellungen"]) == len(sections)


def test_every_raw_message_window_is_a_row(rows: list[fl.Row], ui_sources: dict[str, str]) -> None:
    """Jede Funktion, die ein rohes Meldungsfenster baut, ist eine Zeile — darunter
    Wiederherstellen und Speicherfrage (D1) und die Löschnachfrage im Verlauf (D11)."""
    windows = fscan.scan_ui(ui_sources).raw_windows
    assert {
        "confirm_unsaved",
        "_ask_recovery",
        "remove_history_operations",
        "confirm_discard",
        "show_expired_demo",
    } <= set(windows)
    assert set(fl.RAW_WINDOW_PACKAGES) == set(windows)
    found = _by_id(rows)
    assert found["meldung:confirm_unsaved"].package == "D1"
    assert found["meldung:_ask_recovery"].package == "D1"
    assert found["meldung:remove_history_operations"].package == "D11"
    assert found["startup.expired_demo"].package == "D12"
    assert "meldung:show_expired_demo" not in found


def test_the_searches_find_the_modules_of_their_key_classes(
    ui_sources: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Statt einer Zählprobe (Bauart CS-12): Die Suche unter ``app/ui`` findet die Module
    von Hauptfenster, Ansicht und Einstellungsdialog, die unter ``app/core`` die von
    Handlung, Verlauf und Register. Fehlt eines, ist die Liste rot."""
    assert fl.missing_definitions(ui_sources, fl.UI_CLASSES) == []
    for name in fl.UI_CLASSES:
        without = {
            module: text
            for module, text in ui_sources.items()
            if fl.missing_definitions({module: text}, [name])
        }
        assert fl.missing_definitions(without, fl.UI_CLASSES) == [name]
    assert fl.kernel_action_ids()
    monkeypatch.setattr(fl, "UI_CLASSES", (*fl.UI_CLASSES, "GibtEsNicht"))
    with pytest.raises(fscenes.FunctionListError, match="GibtEsNicht"):
        fl.ui_sources()
    monkeypatch.setattr(fl, "KERNEL_CLASSES", ("Action", "GibtEsAuchNicht"))
    with pytest.raises(fscenes.FunctionListError, match="GibtEsAuchNicht"):
        fl.kernel_action_ids()


def test_two_message_functions_of_one_name_turn_red(cached_sources: dict[str, str]) -> None:
    """Die Kennung eines Meldungsfensters ist sein Funktionsname. Heißen zwei so, hält
    die Liste an und nennt beide Orte — sie teilen sich keine Zeile."""
    cached_sources["app/ui/invented/twin.py"] = (
        "def confirm_unsaved(parent):\n    box = QMessageBox(parent)\n"
    )
    found = fl.problems()
    clash = [issue for issue in found if issue.startswith("meldung:confirm_unsaved:")]
    assert len(clash) == 1 and "app/ui/invented/twin.py" in clash[0], found


def test_a_renamed_module_keeps_every_row_id(
    rows: list[fl.Row], ui_sources: dict[str, str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gegenprobe zur Codestruktur: Eine Kennung nennt die Sache, nie ihren Ort. Ziehen
    Dialoge, Hauptfenster, Einstellungen und Druckeinstellungen in andere Module, bleibt
    jede Kennung gleich — die Meldungsfenster, Abschnitte und Dialogklassen darin
    eingeschlossen."""
    moved = {
        "app/ui/dialogs.py": "app/ui/dialogs/messages.py",
        "app/ui/main_window.py": "app/ui/window/main.py",
        "app/ui/settings_dialog.py": "app/ui/settings/sections.py",
        "app/ui/print_settings_dialog.py": "app/ui/printing/dialog.py",
    }
    assert set(moved) <= set(ui_sources)
    renamed = {moved.get(name, name): text for name, text in ui_sources.items()}
    monkeypatch.setattr(fl, "ui_sources", lambda root=fl.UI: renamed)
    after = fl.rows(with_specs=False)
    assert [row.id for row in after] == [row.id for row in rows]
    for kind in ("meldungsfenster", "einstellungen", "dialogklasse"):
        assert any(row.source == kind for row in after), kind


def test_an_invented_tool_context_action_or_message_window_turns_red(
    cached_sources: dict[str, str],
) -> None:
    """Gegenprobe: Werkzeug, Kontextaktion und Meldungsfenster ohne Paket halten an."""
    cached_sources["app/ui/invented/extra.py"] = (
        "def build(self):\n"
        "    self.tools.add('magnifier', tr('Lupe'), self.bar)\n"
        "    action.setObjectName('tree.magnify')\n"
        "def ask_twice(parent):\n"
        "    box = QMessageBox(parent)\n"
    )
    found = fl.problems()
    assert any("tool:magnifier" in issue for issue in found)
    assert any("menu:tree.magnify" in issue for issue in found)
    assert any(issue.startswith("ask_twice:") for issue in found)


def test_targets_of_raw_windows_and_sections_come_from_the_source(
    rows: list[fl.Row], ui_sources: dict[str, str]
) -> None:
    """Das Ziel einer Meldungsfensterzeile und eines Einstellungsabschnitts steht im
    Quelltext der Fläche — ``setProperty(…TARGET_PROPERTY, …)``, ``target=`` am Bauer im
    Hausstil oder der Abschnittsbauer der Einstellungen. Kontrollfall: das Demo-Ende trägt
    ``dialog:expired_demo``. Eine Zeile ohne Ziel gibt es nicht
    (``test_every_row_carries_its_fields``)."""
    assert _by_id(rows)["startup.expired_demo"].target == "dialog:expired_demo"
    scan = fscan.scan_ui(ui_sources)
    assert scan.raw_targets["show_expired_demo"] == "dialog:expired_demo"


def test_a_marked_surface_without_its_target_turns_red() -> None:
    """Gegenprobe: Jede Form, in der eine Fläche ihr Kennzeichen setzt, kommt als Ziel an —
    ein Meldungsfenster mit ``setProperty`` (auch über eine Modulkonstante), eine Eingabe im
    Hausstil mit ``target=`` und ein Abschnitt über den Abschnittsbauer der Einstellungen,
    in dem Modul, das die Klasse der Einstellungen definiert, wie es auch heißt."""
    windows = fscan.scan_ui(
        {
            "app/ui/extra.py": (
                "NAME = 'message:extra.ask_named'\n"
                "def ask(parent):\n"
                "    box = QMessageBox(parent)\n"
                "    box.setProperty(guides.TARGET_PROPERTY, 'message:extra.ask')\n"
                "def ask_named(parent):\n"
                "    box = QMessageBox(parent)\n"
                "    box.setProperty(guides.TARGET_PROPERTY, NAME)\n"
                "def told(parent):\n"
                "    return ask_text(parent, title='a', target='message:extra.told')\n"
                "def bare(parent):\n"
                "    QMessageBox(parent)\n"
            ),
            "app/ui/irgendwo/einstellungen.py": (
                f"class {fscan.SETTINGS_CLASS}(QDialog):\n"
                "    pass\n"
                "def section(title, content, **options):\n"
                "    wrapper = collapsible(str(title), content, **options)\n"
                "    heading.setProperty(\n"
                "        guides.TARGET_PROPERTY,\n"
                "        f'setting.section:{guides.name_part(title.msgid)}',\n"
                "    )\n"
                "    return wrapper\n"
                "def group(self):\n"
                "    return section(_('Vorgaben für neue Projekte'), box)\n"
                "def plain(self):\n"
                "    return collapsible(tr('Ohne Kennzeichen'), box)\n"
            ),
        }
    )
    assert windows.raw_targets == {
        "ask": "message:extra.ask",
        "ask_named": "message:extra.ask_named",
        "told": "message:extra.told",
    }
    assert set(windows.raw_windows) == {"ask", "ask_named", "told", "bare"}
    assert windows.settings_sections == ("Vorgaben für neue Projekte", "Ohne Kennzeichen")
    assert windows.settings_targets == {
        "Vorgaben für neue Projekte": "setting.section:vorgaben_fuer_neue_projekte"
    }


def test_the_history_entries_come_from_the_context_menu(ui_sources: dict[str, str]) -> None:
    """Die Verlaufszeilen kommen aus den Objektnamen ``history.*`` — die vier, unter denen
    die Bildanleitungen sie schon finden, sind dabei."""
    entries = fscan.history_entries(ui_sources)
    assert {"edit", "insert", "switch", "delete", "up", "down"} <= set(entries)
    # Ein Name aus einem bedingten Ausdruck zählt mit beiden Zweigen.
    probe = 'a.setObjectName("history.up" if x else "history.down")\nb.setObjectName(name)\n'
    assert fscan.history_entries({"probe.py": probe}) == ("down", "up")


# --- Anforderung und Szene --------------------------------------------------------


def test_mesh_operations_start_on_a_fine_mesh(rows: list[fl.Row]) -> None:
    """L6: Ausdünnen, Glätten, Formen und Skelett beginnen an einem fein vernetzten Netz,
    nicht an einem Quader aus zwölf Dreiecken; die Wandlung ins Netz am exakten Körper."""
    found = _by_id(rows)
    scenes = _scenes()
    for name in (
        "decimate_mesh",
        "smooth_mesh",
        "remesh_uniform",
        "sculpt_strokes",
        "pose_armature",
    ):
        scene = scenes[found[name].start_scene]
        assert scene.kernel == "netz" and scene.promises.get("triangles_over", 0) >= 1000, name
    assert found["brep_to_mesh"].start_scene == "quader.exakt"


def test_surfaces_start_where_their_target_stands(rows: list[fl.Row]) -> None:
    """R4: *Diesen Schritt ändern* am Baum steht an einem erzeugten Merkmal; Parameterleiste
    und ihr Kontextmenü brauchen ein Maß — eine Szene mit Projektparameter an beiden Kernen."""
    found = _by_id(rows)
    assert found["menu:tree.step"].requirement == "merkmal:hole"
    assert found["menu:tree.step"].start_scene == "merkmal.hole.exakt"
    scenes = _scenes()
    for row_id in ("menu:parameters.edit", "parameters.first"):
        assert found[row_id].requirement == "parameter"
        scene = scenes[found[row_id].start_scene]
        assert scene.parameters, row_id
    assert {"parameter.exakt", "parameter.netz"} <= set(scenes)


def test_every_operation_has_a_start_scene(rows: list[fl.Row]) -> None:
    """Jede Anforderung einer Operation hat eine Szene im Katalog (§2.5)."""
    scenes = fscenes.load_scenes()
    assert fl.missing_scenes(rows) == []
    for row in rows:
        if row.kind == "operation":
            assert row.start_scene in scenes, row


def test_a_duplicate_surface_is_reported_not_dropped() -> None:
    """L4: Zweimal derselbe Name ergibt zwei Zeilen, und die Prüfung der ganzen Liste meldet
    die doppelte Kennung."""
    doubled = fl.surface_rows(["tree", "tree"], (), (), fscenes.load_scenes())
    assert [row.id for row in doubled].count("tree") == 2
    assert fl.duplicate_ids(doubled) == ["tree: zwei Zeilen mit derselben Kennung"]


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
    found = fscan.window_classes_in(
        {
            "a.py": "class Box(QtWidgets.QMessageBox):\n    pass\n",
            "c.py": "class Plain(QWidget):\n    pass\n",
            "b.py": "def make():\n    class Nested(Box):\n        pass\n",
        }
    )
    assert set(found) == {"Box", "Nested"}


# --- Szenen ------------------------------------------------------------------------


def _scenes() -> dict[str, fscenes.Scene]:
    return fscenes.load_scenes()


def _light(kernel: str) -> list[str]:
    return [
        key
        for key, scene in _scenes().items()
        if scene.project and not scene.heavy and (scene.kernel or "netz") == kernel
    ]


def test_the_recipes_are_valid() -> None:
    """Basis, Operationen, Quellen, Kern und Zusagen jeder Szene, ohne zu rechnen."""
    assert fscenes.validate_scenes(_scenes()) == []


def test_every_feature_kind_has_a_scene_on_both_kernels() -> None:
    """Je Merkmalsart aus ``FEATURE_KINDS`` eine Szene am exakten und am Netzkern; eine
    Art ohne exakten Körper (offener Rand) nur am Netz."""
    scenes = _scenes()
    for kind in FEATURE_KINDS:
        for kernel in fscenes.KERNELS:
            key = f"merkmal.{kind}.{kernel}"
            if kernel == fscenes.EXACT and kind in fl.MESH_ONLY_KINDS:
                assert key not in scenes
                continue
            assert key in scenes, key
            assert kind in scenes[key].promises["kinds"], key


@pytest.mark.parametrize("key", _light(fscenes.MESH))
def test_a_light_mesh_scene_keeps_its_promises(key: str) -> None:
    """Die leichte Szene rechnet und hält, was sie zusagt: Körper, Bauart, Merkmalsarten,
    Körperzustand, Befunde, Halt."""
    scenes = _scenes()
    if fscenes.needs_exact_kernel(key, scenes):
        exact_kernel()
    assert fscenes.check_scene(key, scenes) == []


def test_a_mesh_scene_built_by_the_exact_kernel_knows_it() -> None:
    """L3: ``merkmal.thread.netz`` entsteht über ``thread_exact`` — ohne OpenCASCADE wird
    der Fall übersprungen statt rot; ein reiner Netzquader braucht den Kern nicht."""
    scenes = _scenes()
    assert fscenes.needs_exact_kernel("merkmal.thread.netz", scenes)
    assert not fscenes.needs_exact_kernel("quader.netz", scenes)


@pytest.mark.parametrize("key", _light(fscenes.EXACT))
def test_a_light_exact_scene_keeps_its_promises(key: str) -> None:
    """Dasselbe am exakten Kern — lokal nur mit OpenCASCADE, in der CI Pflicht."""
    exact_kernel()
    assert fscenes.check_scene(key, _scenes()) == []


def test_there_are_light_scenes_on_both_kernels() -> None:
    """Die Parametrisierung darüber ist nicht leer."""
    assert len(_light(fscenes.MESH)) >= 15
    assert len(_light(fscenes.EXACT)) >= 15


@pytest.mark.parametrize("key", [key for key, scene in _scenes().items() if scene.heavy])
def test_a_heavy_scene_is_a_valid_stack(key: str) -> None:
    """Schwere Szenen rechnet nur der Werkzeuglauf; hier nimmt ``History.apply`` jeden
    Schritt an, und die Zusage nennt Dreiecke oder Sekunden."""
    scenes = _scenes()
    project = fscenes.build_scene(key, scenes)
    _sources, steps = fscenes.recipe(key, scenes)
    assert len(project.document.ops) == len(steps) >= 2
    assert {"triangles_over", "seconds_over"} & set(scenes[key].promises)


def test_the_heavy_scenes_of_the_plan_are_there() -> None:
    """§2.5: zwei langsame, eine über der Erkennungsgrenze, eine über der groben Vorschau."""
    heavy = {key for key, scene in _scenes().items() if scene.heavy}
    assert heavy >= {"langsam_2s", "langsam_10s", "ueber_erkennungsgrenze", "ueber_grober_vorschau"}


def test_the_promise_check_sees_a_broken_promise() -> None:
    """Gegenprobe des Prüfers: Ein Quader zeigt keine Bohrung, hat einen Körper und hält nicht."""
    scenes = _scenes()
    scene = dataclasses.replace(
        scenes["quader.netz"],
        promises={"objects": 2, "kinds": ["hole"], "stops": True, "findings": ["x.y"]},
    )
    result = fscenes.evaluate_scene(fscenes.build_scene("quader.netz", scenes))

    broken = fscenes.broken_promises(scene, result)

    assert len(broken) == 4, broken

    # Und eine Handlung, die der Bericht am zugesagten Befund nicht anbietet.
    halt = scenes["halt"]
    wrong = dataclasses.replace(
        halt,
        promises={**halt.promises, "actions": {"arrange_on_bed": "op.fillet_edges.GeometryError"}},
    )
    stopped = fscenes.evaluate_scene(fscenes.build_scene("halt", scenes))
    assert fscenes.broken_promises(halt, stopped) == []
    broken = fscenes.broken_promises(wrong, stopped)
    assert len(broken) == 1 and "arrange_on_bed" in broken[0], broken


def test_what_the_window_adds_is_part_of_the_promise() -> None:
    """Gegenprobe zu ``window_findings``: Ohne Auslöser, Einfügemarke, mitgebrachten
    Drucker oder geschützte Flächen fehlt der Befund, den die Szene zusagt — die
    Zusage wird also am Befund des Fensters geprüft und nicht geschenkt."""
    scenes = _scenes()
    for key, emptied in (
        ("export_gemischt", {"cause": {}}),
        ("einfuegen.netz", {"insert_before": 0}),
        ("fremder_drucker.netz", {"printer": "", "printer_like": ""}),
        ("geschuetzte_leiste.netz", {"protected": {}}),
    ):
        changed = {**scenes, key: dataclasses.replace(scenes[key], **emptied)}
        broken = fscenes.check_scene(key, changed)
        assert any("fehlen" in issue for issue in broken), (key, broken)
        assert fscenes.check_scene(key, scenes) == [], key


def test_a_scene_leaves_nothing_behind() -> None:
    """Eigene Bausteine, mitgereiste Rezepte, mitgebrachte Drucker und ein fehlendes
    OpenCASCADE gelten nur, solange die Szene gebaut und gerechnet wird."""
    from app.core.brep import kernel
    from app.core.knowledge import profiles
    from app.core.knowledge.parts.registry import PARTS
    from app.core.registry import REGISTRY

    scenes = _scenes()
    fscenes.registry()
    parts = {spec.name for spec in PARTS.all()}
    operations = {spec.name for spec in REGISTRY.all()}
    available = kernel.available
    for key in ("baustein_geaendert.netz", "ohne_opencascade.exakt", "fremder_drucker.netz"):
        assert fscenes.check_scene(key, scenes) == [], key
        assert {spec.name for spec in PARTS.all()} == parts, key
        assert {spec.name for spec in REGISTRY.all()} == operations, key
        assert kernel.available is available, key
        assert profiles.only_carried() == (), key
    # Gegenprobe: Ohne den eigenen Baustein im Nutzerordner rechnet das Projekt mit
    # seinem mitgereisten Stand, und es gibt nichts anzubieten.
    alone = {**scenes, "x": dataclasses.replace(scenes["baustein_geaendert.netz"], own_parts=())}
    assert any("parts.own_changed" in issue for issue in fscenes.check_scene("x", alone))


def test_the_setting_of_a_scene_is_checked_without_computing() -> None:
    """Gegenprobe: Datei, Drucker, Material, erzeugte Quelle, Einfügemarke und Auslöser
    werden geprüft, bevor gerechnet wird."""
    base = _scenes()["quader.netz"]
    wrong = {
        "a": dataclasses.replace(base, key="a", opens="projects/gibt_es_nicht.p3d"),
        "b": dataclasses.replace(base, key="b", printer="centauri-carbon-2", printer_like="x"),
        "c": dataclasses.replace(base, key="c", material="kein_material"),
        "d": dataclasses.replace(base, key="d", generated=("src_9",)),
        "e": dataclasses.replace(base, key="e", insert_before=5),
        "f": dataclasses.replace(base, key="f", cause={"kind": "drucken"}),
        "g": dataclasses.replace(base, key="g", cause={"kind": "export", "format": "dwg"}),
        "h": dataclasses.replace(base, key="h", own_parts=("recipes/gibt_es_nicht.json",)),
    }
    issues = fscenes.validate_scenes({"quader.netz": base, **wrong})
    for key in wrong:
        assert any(issue.startswith(f"Szene {key}:") for issue in issues), (key, issues)
    assert fl.scene_precondition_problems(
        {
            "a": dataclasses.replace(base, preconditions={"opencascade": "fehlt"}),
            "b": dataclasses.replace(base, preconditions={"licence": "licensed"}),
            "c": dataclasses.replace(base, preconditions={"comfyui": "kaputt"}),
        }
    ) == [
        "Szene b: Vorbedingung licence = 'licensed' gibt es nicht",
        "Szene c: Vorbedingung comfyui = 'kaputt' gibt es nicht",
    ]


def test_a_scene_from_a_file_is_saved_as_it_is(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eine Korpusdatei, an der die Szene nichts ändert, kommt bytegleich in den Ordner
    des Laufs: Neu gespeichert trüge sie den Abdruck der Bausteine von heute, und der
    geänderte eigene Baustein wäre keiner mehr."""
    scenes = _scenes()
    chosen = {key: scenes[key] for key in ("baustein_geaendert.netz", "passung_pla.netz")}
    monkeypatch.setattr(fscenes, "load_scenes", lambda path=fscenes.SCENES: chosen)
    written = fscenes.save_scenes(tmp_path / "szenen")
    copied, saved = written
    assert copied.read_bytes() == (fscenes.DATA / "projects" / "own_part_v52.p3d").read_bytes()
    assert saved.read_bytes() != (fscenes.DATA / "projects" / "assembly_fit.p3d").read_bytes()


def test_a_broken_recipe_is_named() -> None:
    """Gegenprobe der Rezeptprüfung: unbekannte Operation, fehlende Quelle, Basis im Kreis."""
    scenes = {
        "a": fscenes.Scene(key="a", summary="a", base="b"),
        "b": fscenes.Scene(key="b", summary="b", base="a"),
        "c.netz": fscenes.Scene(
            key="c.netz",
            summary="c",
            kernel="netz",
            sources={"src_1": "meshes/gibt_es_nicht.stl"},
            ops=(fscenes.SceneStep(op="gibt_es_nicht"),),
        ),
    }
    scenes["d.netz"] = fscenes.Scene(
        key="d.netz",
        summary="d",
        kernel="netz",
        ops=(
            fscenes.SceneStep(op="create_box"),
            fscenes.SceneStep(op="remesh_mesh", inputs=("obj_1",), params={"edge": -1.0}),
        ),
    )
    found = fscenes.validate_scenes(scenes)
    assert any("d.netz" in issue and "remesh_mesh" in issue for issue in found), found
    assert any("Kreis" in issue for issue in found)
    assert any("gibt_es_nicht.stl" in issue for issue in found)
    assert any("'gibt_es_nicht'" in issue for issue in found)


def test_generated_scenes_never_land_in_the_tree(tmp_path: Path) -> None:
    """Die Datei aus einem Rezept wird nicht abgelegt (``tests/data/CLAUDE.md``)."""
    with pytest.raises(fscenes.FunctionListError):
        fscenes.save_scenes(DATA / "erzeugt")
    assert not (DATA / "erzeugt").exists()
    written = fscenes.save_scenes(tmp_path)
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
    assert targets("create_box") == []
    # Eine Operation über die ganze Szene steht in der Karte am gewählten Körper
    # (Probelauf F-32: ohne Auswahl fand der Sprachfall sie nicht).
    assert targets("arrange_bed") == [("tree.row:obj_1", "")]
    # Eine Kante wählt ein Klick ins Bild, nachdem der Körper gewählt ist
    # (gestufte Tiefe, §18.5) — vorher wählte der Weg nur den Körper, und keine
    # Kantenzeile lief an einer Kante (Durchsicht welle4 C-M4).
    edge_way = [("tree.row:obj_1", ""), ("view.edge:obj_1", "")]
    for row_id in (
        "fillet_edges",
        "chamfer_edges",
        "bead_edges",
        "edge:fillet_edges.variable_radius",
    ):
        assert targets(row_id) == edge_way, row_id
    steps = [step for row in rows for step in row.route]
    assert len(steps) >= 100
    assert all(is_target(step["target"]) and step["button"] == "left" for step in steps)


def test_a_feature_scene_without_its_selection_turns_red(
    monkeypatch: pytest.MonkeyPatch, cached_sources: dict[str, str]
) -> None:
    """Gegenprobe: Nennt eine Merkmalsszene kein gewähltes Merkmal, fehlt allen Zeilen
    darauf der Auswahlweg — das ist rot, nicht still leer."""
    scenes = fscenes.load_scenes()
    scenes["merkmal.hole.exakt"] = dataclasses.replace(scenes["merkmal.hole.exakt"], select="")
    monkeypatch.setattr(fl, "load_scenes", lambda path=fscenes.SCENES: scenes)

    found = fl.problems()

    assert any(issue.startswith("resize_hole:") and "Auswahlweg" in issue for issue in found)


def test_the_promise_check_sees_a_wrong_selection() -> None:
    """Gegenprobe: Ein gewähltes Merkmal, das es nicht gibt oder das die falsche Art hat."""
    scenes = fscenes.load_scenes()
    result = fscenes.evaluate_scene(fscenes.build_scene("merkmal.hole.netz", scenes))
    missing = dataclasses.replace(scenes["merkmal.hole.netz"], select="obj_1.hole_9")
    wrong = dataclasses.replace(scenes["merkmal.hole.netz"], select="obj_1.face_1")
    assert any("gibt es nicht" in issue for issue in fscenes.broken_promises(missing, result))
    assert any("nicht hole" in issue for issue in fscenes.broken_promises(wrong, result))


# --- Zeilenspezifikationen ---------------------------------------------------------


def test_an_unknown_id_in_a_spec_turns_red(
    monkeypatch: pytest.MonkeyPatch, cached_sources: dict[str, str]
) -> None:
    """Gegenprobe: Eine Spezifikation, die keine erzeugte Zeile trifft, ist rot."""
    monkeypatch.setattr(
        fl,
        "load_specs",
        lambda directory=fl.ROW_SPECS: {
            "gibt_es_nicht": fl.SpecEntry("D4", "d04.toml", {"example_goal": "x"})
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
    probes = ("resize_hole", "finding.action:place_on_bed", "Bearbeiten/Parameter anlegen …")
    assert set(probes) <= set(specs)
    found = _by_id(rows)
    assert found["resize_hole"].kind == "operation" and specs["resize_hole"].package == "D4"
    assert found["finding.action:place_on_bed"].package == "D8"
    assert specs["Bearbeiten/Parameter anlegen …"].package == "D10"
    # Die Eigenschaft der drei Probezeilen, nicht jeder Spezifikation (M4).
    for row_id in probes:
        values = specs[row_id].values
        assert values["example_goal"] and values["search_probes"] and values["expectation"]


def _spec(
    values: dict[str, Any], package: str = "D12", row_id: str = "dialog:about_dialog"
) -> dict[str, fl.SpecEntry]:
    return {row_id: fl.SpecEntry(package, f"d{package[1:]}.toml", values)}


def test_a_valid_spec_without_calculation_stays_green(rows: list[fl.Row]) -> None:
    """M4: Eine nach §2.4 gültige Spezifikation ohne Rechnung — ohne Erwartung, Prüfpunkt 4
    entfällt — macht nichts rot."""
    values = {
        "start_scene": "leer",
        "example_goal": "Den Über-Dialog öffnen.",
        "search_probes": [{"word": "Version", "origin": "slicer"}],
        "not_applicable": {"4": "ohne_rechnung", "E5": "ohne_dialog"},
        "criteria": ["Z1"],
    }
    assert fl.validate_specs(rows, _spec(values), fscenes.load_scenes()) == []


def test_the_spec_format_is_closed(rows: list[fl.Row]) -> None:
    """M5, L7, L11: Prüfpunkte 1–19 und die Kriterien als Schlüssel von ``not_applicable``,
    nur Gründe der geschlossenen Liste, ``criteria`` nur aus den 35 Kennungen, Paket der
    Datei, Erwartung mit Herkunft und Toleranz über null, bekannte Vorbedingungen."""
    scenes = fscenes.load_scenes()
    assert len(fl.CRITERION_IDS) == 35 and len(fl.CHECKPOINT_NUMBERS) == 19
    assert set(fl.NOT_APPLICABLE_REASONS) == {
        "ohne_rechnung",
        "ohne_auswahlbezug",
        "ohne_dialog",
        "ohne_agentenwerkzeug",
        "nur_stufe_c",
    }
    cases = {
        "Grund": ({"not_applicable": {"4": "keine_lust"}}, "D12"),
        "Prüfpunkt": ({"not_applicable": {"20": "ohne_rechnung"}}, "D12"),
        "Kriterium": ({"criteria": ["X9"]}, "D12"),
        "gehört zu": ({}, "D4"),
        "Herkunft": ({"expectation": {"volume": {"value": 1.0, "tolerance": 0.1}}}, "D12"),
        "Toleranz": (
            {"expectation": {"volume": {"value": 1.0, "tolerance": 0.0, "origin": "x"}}},
            "D12",
        ),
        "Vorbedingung": ({"preconditions": {"licence": "demo"}}, "D12"),
        "Lizenzzustand 'over'": ({"preconditions": {"licence": "over"}}, "D12"),
    }
    for word, (values, package) in cases.items():
        issues = fl.validate_specs(rows, _spec({"start_scene": "leer", **values}, package), scenes)
        assert any(word in issue for issue in issues), (word, issues)


def test_a_fault_case_is_checked_like_a_spec(rows: list[fl.Row]) -> None:
    """Der Fehlfall hat ein geschlossenes Format: bekannte Schlüssel, ``during`` aus der
    Liste, Weg und Eingaben aus dem Wortschatz, eine Startszene aus dem Katalog.

    Die Probezeile D8 trägt ihn: *Auf das Bett setzen* ist während einer Neuberechnung
    gesperrt und nennt den Grund (RM-534) — eine Startszene, deren Neuberechnung nicht
    aus dem Zwischenspeicher kommt.
    """
    scenes = fscenes.load_scenes()
    good = {
        "start_scene": "leer",
        "fault_case": {
            "start_scene": "unter_dem_bett_langsam",
            "route": [{"target": "history.row:4", "button": "double"}],
            "inputs": {"field:edge": 0.21},
            "during": "rechnung",
            "expected": "sperrgrund",
        },
    }
    assert fl.validate_specs(rows, _spec(good), scenes) == []
    bad = {
        "start_scene": "leer",
        "fault_case": {
            "start_scene": "gibt_es_nicht",
            "route": [
                {"target": "Knopf"},
                {"target": "tree.row:obj_1", "button": "mitte", "modifier": "alt"},
            ],
            "during": "irgendwann",
            "expected": "sperrgrund",
            "wann": "jetzt",
        },
    }
    issues = fl.validate_specs(rows, _spec(bad), scenes)
    for word in ("gibt_es_nicht", "'Knopf'", "irgendwann", "wann", "'mitte'", "'alt'"):
        assert any(word in issue for issue in issues), (word, issues)
    fault = fl.load_specs()["finding.action:place_on_bed"].values["fault_case"]
    assert fault["during"] == "rechnung" and fault["expected"] == "sperrgrund"
    assert scenes[fault["start_scene"]].heavy


def test_the_licence_preconditions_are_the_states_of_the_application() -> None:
    """Die Lizenzzustände einer Vorbedingung sind Eigenschaften von ``Activation``; ``expired``
    gibt es nur mit Testzeitraum (``TRIAL_FROM``)."""
    from app.core.activation import Activation
    from app.core.activation.store import TRIAL_FROM

    states = fl.licence_states()
    assert set(fl.PRECONDITIONS["licence"]) == {*fl.LICENCE_STATES, fl.STARTUP_LICENCE}
    assert set(states) <= set(fl.LICENCE_STATES)
    for name in (*fl.LICENCE_STATES, fl.STARTUP_LICENCE):
        assert hasattr(Activation, name), name
    assert ("expired" in states) == (TRIAL_FROM is not None)
    assert ("sale_without_trial" in states) == (TRIAL_FROM is None)


def test_a_licence_state_must_be_reachable(
    rows: list[fl.Row], monkeypatch: pytest.MonkeyPatch
) -> None:
    """R2: ``over`` nur an der Startzeile, ``expired`` nur mit Testzeitraum
    (``store.TRIAL_FROM``); ein erreichbarer Zustand geht durch."""
    import datetime

    from app.core.activation import store

    scenes = fscenes.load_scenes()

    def issues(state: str, row_id: str = "dialog:about_dialog") -> list[str]:
        values = {"start_scene": "leer", "preconditions": {"licence": state}}
        return fl.validate_specs(rows, _spec(values, row_id=row_id), scenes)

    monkeypatch.setattr(store, "TRIAL_FROM", None)
    assert issues("licensed") == [] and issues("sale_without_trial") == []
    assert any("expired" in issue for issue in issues("expired"))
    assert any("over" in issue for issue in issues("over"))
    assert issues("over", row_id="startup.expired_demo") == []
    monkeypatch.setattr(store, "TRIAL_FROM", datetime.date(2026, 1, 1))
    assert issues("expired") == []
    assert any("sale_without_trial" in issue for issue in issues("sale_without_trial"))


def test_spec_files_are_read_strictly(tmp_path: Path) -> None:
    """L7: dieselbe Kennung in zwei Dateien und ein Dateiname ohne Paketnummer halten an."""
    (tmp_path / "d04.toml").write_text(
        '[row."resize_hole"]\nexample_goal = "a"\n', encoding="utf-8"
    )
    (tmp_path / "d05.toml").write_text(
        '[row."resize_hole"]\nexample_goal = "b"\n', encoding="utf-8"
    )
    with pytest.raises(fscenes.FunctionListError):
        fl.load_specs(tmp_path)
    (tmp_path / "d05.toml").unlink()
    (tmp_path / "dx.toml").write_text("", encoding="utf-8")
    with pytest.raises(fscenes.FunctionListError):
        fl.load_specs(tmp_path)


def test_a_menu_path_is_checked_against_every_ui_module(
    rows: list[fl.Row], cached_sources: dict[str, str]
) -> None:
    """L8: Ohne Fenster sucht die Prüfung den Text einer Menüzeile in allen Modulen unter
    ``app/ui`` — ein Umzug von ``main_window.py`` in ein Paket macht sie nicht rot."""
    cached_sources["app/ui/window/menus.py"] = "x = _('Ganz neu …')\n"
    values = {"start_scene": "leer", "example_goal": "x"}
    specs = {"Datei/Ganz neu …": fl.SpecEntry("D1", "d01.toml", values)}
    assert fl.validate_specs(rows, specs, fscenes.load_scenes()) == []


def test_the_menubar_is_read_in_the_source_language_only() -> None:
    """L8: Den Weg einer Menüzeile gibt es nur in der Quellsprache; in einer anderen
    Sprache hält ``menubar_of`` an, bevor es ein Fenster anfasst."""
    from app.i18n import set_language

    set_language("en")
    try:
        with pytest.raises(fscenes.FunctionListError):
            fl.menubar_of(object())
    finally:
        set_language("de")


def test_a_spec_with_an_unknown_field_or_target_turns_red(rows: list[fl.Row]) -> None:
    """Gegenprobe: ein Feld, das die Operation nicht hat, ein Ziel außerhalb des Wortschatzes,
    eine Szene, die es nicht gibt, ein Menüpfad, den die Quelle nicht kennt."""
    bad = {
        "resize_hole": fl.SpecEntry(
            "D4",
            "d04.toml",
            {
                "start_scene": "gibt_es_nicht",
                "example_goal": "x",
                "inputs": {"feature.field:resize_hole.durchmesser": 8.0, "Feld:Durchmesser": 1.0},
            },
        ),
        "Bearbeiten/Gibt es nicht …": fl.SpecEntry("D10", "d10.toml", {}),
    }
    found = fl.validate_specs(rows, bad, fscenes.load_scenes())
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
        assert fl.scene_for(selection, fscenes.EXACT), goal
        assert fl.route_for(selection, goal["scene"], scenes), goal
        kind, _colon, name = goal["target"].partition(":")
        assert kind in {"operation", "feature", "edge"}, goal
        assert REGISTRY.has(name.split(".")[0]), goal
        assert is_target(goal["target"]), goal


def test_no_customer_id_reaches_the_corpus() -> None:
    """Der Korpus wird veröffentlicht: keine Kennung eines Fragebogens in den neuen Dateien."""
    files = [VOCABULARY, GOALS, fscenes.SCENES, *sorted(fl.ROW_SPECS.glob("*.toml"))]
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


def test_the_command_line_reports_instead_of_tracing(
    capsys: pytest.CaptureFixture[str], tmp_path: Path
) -> None:
    """L10: Ein Menüleistenformat von früher und ``--out`` im Baum enden mit Meldung und
    Ausgang 1, nicht im Stapelabzug."""
    old = tmp_path / "alt.json"
    old.write_text(json.dumps([{"name": "x", "path": ["Datei"]}]), encoding="utf-8")
    assert fl.main(["--menueleiste", str(old)]) == 1
    assert fl.main(["--szenen", "--out", str(DATA / "erzeugt")]) == 1
    assert "Format" in capsys.readouterr().err


def test_the_scenes_compute_with_the_profile_of_the_application() -> None:
    """L9: kein dritter fest geschriebener Drucker im Werkzeug — die Szene rechnet mit dem
    Profil, das die Anwendung einem Projekt ohne Wahl gibt (``profiles.scene_profile``)."""
    source = Path(fscenes.__file__).read_text(encoding="utf-8")
    assert "centauri-carbon-2" not in source and "scene_profile" in source


def test_the_list_is_built_without_a_window() -> None:
    """Die Liste baut kein Widget: kein ``QApplication``, kein ``show`` in ihren Modulen."""
    for module in (fl, fscan, fscenes):
        source = Path(module.__file__ or "").read_text(encoding="utf-8")
        assert "QApplication" not in source, module.__name__
        assert ".show(" not in source and ".exec(" not in source, module.__name__


# --- Fensterbefehle am gebauten Fenster (Fenster-CI) -------------------------------


def test_every_menubar_line_becomes_a_row_with_a_package(qt_app: Any, tmp_path: Path) -> None:
    """Am gebauten Fenster: Jede Zeile der Menüleiste, die keine Operation ist, wird
    eine Fensterbefehlszeile mit Paket, und jede Spezifikation mit Menüpfad trifft eine.

    Die Leiste entsteht erst in ``_build_menus``; gelesen wird sie über
    ``guide_targets.menubar_entries``, wie der Prüfstand sie liest.
    """
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    written = fl.menubar_of(window)
    assert len(written) >= 60, f"nur {len(written)} Zeilen in der Menüleiste"
    # Der Weg reicht bis zur Zeile selbst, und das Kürzel reist mit.
    assert ("Bearbeiten", "Parameter anlegen …") in {entry.path for entry in written}
    assert any(entry.shortcut for entry in written)
    fl.write_menubar(tmp_path / "menubar.json", written)
    entries = fl.read_menubar(tmp_path / "menubar.json")
    assert entries == written

    found = fl.rows(entries)
    commands = [row for row in found if row.source == "menueleiste"]
    assert len(commands) >= 30, f"nur {len(commands)} Fensterbefehle"
    assert {row.package for row in commands} >= {"D1", "D2", "D11", "D12"}
    from app.core.guides import is_target

    assert all(is_target(row.target) for row in commands)
    # Zwei Handler gibt es nur nach einem gescheiterten Schreiben (*Erneut*, *Anderen
    # Ort wählen*); der statische Leser sieht beide Zweige, das Fenster nach dem Fall.
    window._write_failure = object()
    assert fl.report_handlers() == set(window.error_handlers()), "Handler statisch gelesen"
    by_path = {row.id: row for row in commands}
    assert by_path["Erzeugen/Zeichnen …"].package == "D7"
    assert by_path["Hilfe/Beispiele"].package == "D1"
    by_id = {row.id: row for row in found}
    for row_id, spec in fl.load_specs().items():
        if "/" in row_id:
            assert row_id in by_id, f"{spec.file}: {row_id} ist keine Zeile der Menüleiste"
            assert by_id[row_id].package == spec.package
    assert fl.validate_specs(found, fl.load_specs(), fscenes.load_scenes()) == []
    used = {row.id.rsplit("/", 1)[-1] for row in commands}
    assert set(fl.COMMAND_PACKAGES) <= used, "Ausnahme ohne Menüzeile"
    assert {row.id.split("/")[0] for row in commands} == set(fl.MENU_PACKAGES)


def test_a_window_command_lands_in_the_package_of_its_area() -> None:
    """Konzept §6: *Zeichnen …* ist die Variantengruppe der Skizzenoperationen (D7),
    *Beispiele* steht bei D1 — nicht im Paket ihres Hauptmenüs."""
    assert fl.command_package(fl.MenuEntry("menubar.zeichnen", ("Erzeugen", "Zeichnen …"))) == "D7"
    assert fl.command_package(fl.MenuEntry("menubar.beispiele", ("Hilfe", "Beispiele"))) == "D1"


def test_same_name_different_line_is_not_merged() -> None:
    """Gegenprobe L1: Zwei Zeilen unter einem Objektnamen mit verschiedenem Text sind zwei
    Funktionen, keine — das hält an; ebenso eine Zeile ohne Namen."""
    source = fscenes.registry()
    scenes = fscenes.load_scenes()
    twice = [
        fl.MenuEntry("menubar.neu", ("Datei", "Neu")),
        fl.MenuEntry("menubar.neu", ("Hilfe", "Neuerungen …")),
    ]
    with pytest.raises(fscenes.FunctionListError):
        fl.command_rows(twice, source, scenes)
    with pytest.raises(fscenes.FunctionListError):
        fl.command_rows([fl.MenuEntry("", ("Datei", "Speichern"))], source, scenes)
    same = [
        fl.MenuEntry("menubar.bausteinkatalog", ("Datei", "Bausteinkatalog …")),
        fl.MenuEntry("menubar.bausteinkatalog", ("Erzeugen", "Bausteine", "Bausteinkatalog …")),
    ]
    assert len(fl.command_rows(same, source, scenes)) == 1


def test_the_menubar_format_has_one_shape(tmp_path: Path) -> None:
    """``menubar.json`` schreibt und liest eine Stelle; ein anderes Format — der Weg nur
    bis zum Menü unter ``name`` — hält an, statt still falsche Kennungen zu geben."""
    entries = [
        fl.MenuEntry("menubar.parameter_anlegen", ("Bearbeiten", "Parameter anlegen …")),
        fl.MenuEntry("menubar.speichern", ("Datei", "Speichern"), "Ctrl+S"),
    ]
    fl.write_menubar(tmp_path / "menubar.json", entries)
    assert fl.read_menubar(tmp_path / "menubar.json") == entries
    assert json.loads((tmp_path / "menubar.json").read_text(encoding="utf-8"))[1] == {
        "object_name": "menubar.speichern",
        "path": ["Datei", "Speichern"],
        "shortcut": "Ctrl+S",
    }

    (tmp_path / "alt.json").write_text(
        json.dumps([{"name": "menubar.speichern", "path": ["Datei"]}]), encoding="utf-8"
    )
    with pytest.raises(fscenes.FunctionListError):
        fl.read_menubar(tmp_path / "alt.json")
