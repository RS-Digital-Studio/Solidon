"""Die Auflösung des Wortschatzes am Fenster (RM-737, Funktionsdurchgang).

Was ``app/ui/guide_targets.py`` aus einem Namen macht: Widget, Ort, der nächste
Klick des Kunden (``next_click``), die Stelle im Bild (``point_for``), die Probe
(``widget_under``), die Zone; dazu die Namen der Menüleiste und der
Kontextmenüs, die Kennzeichen der Dialoge und die Fensterfunde, die der
Prüfstand dabei fand (Abriss des Objektbaums, Überstand der linken Karte).
Getrennt von ``tests/test_guides.py``, das die Bildanleitungen selbst prüft:
eine Testart, eine Datei.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtWidgets import QMenu, QScrollArea, QToolButton

from app.core import guides
from app.core.bootstrap import load_operations
from app.i18n import SOURCE_LANGUAGE

load_operations()


#: Die Arten, die der Funktionsdurchgang dazugebracht hat; die alten neun prüfen
#: die Bildanleitungen beim Release.
NEW_KINDS = frozenset(guides.TARGET_KINDS) - {
    "command",
    "operation",
    "field",
    "part",
    "tool",
    "transform",
    "section",
    "sketch",
    "history",
}


def test_every_kind_of_the_vocabulary_has_its_resolution_in_the_interface() -> None:
    """Eine Art im Kern, die die Oberfläche nicht kennt, scheiterte erst am Prüfstand."""
    from app.ui import guide_targets

    assert frozenset(guides.TARGET_KINDS) == guide_targets.RESOLVED_KINDS


@pytest.mark.parametrize(
    ("class_name", "expected"),
    [
        ("PrintSettingsDialog", "print_settings_dialog"),
        ("SettingsDialog", "settings_dialog"),
        ("LLMKeyDialog", "llm_key_dialog"),
        ("MainWindow", "main_window"),
        ("PartCatalog", "part_catalog"),
        ("_PanelWindow", "panel_window"),
    ],
)
def test_a_dialog_is_named_after_its_class(class_name: str, expected: str) -> None:
    assert guides.dialog_name(class_name) == expected
    assert guides.is_target(f"dialog:{expected}")


#: Die Auflöser, die mit dem Funktionsdurchgang entstanden sind. Sie greifen
#: auf kein privates Attribut zu: Was sie brauchen, trägt die Oberfläche als
#: Kennzeichen oder unter einem öffentlichen Namen (Abnahme D0-W).
NEW_RESOLVERS = (
    "marked_widgets",
    "_marked",
    "_rebuild_button",
    "_search_field",
    "_toolbar_search",
    "_progress_cancel",
    "_preview_banner",
    "_obstacles",
    "_Obstacle",
    "_reveal",
    "_tab_of_a_page_behind",
    "menu_entries",
    "menubar_entries",
    "_menu_name",
    "_bar",
    "_dialog_of_class",
    "_object_and_feature",
    "_spot",
    "_row",
    "_item_rect",
    "_item_area",
    "_row_obstacle",
    "_reveal_row",
    "section_heading",
    "point_of_world",
    "_display_to_global",
    "_shows_the_view",
    "point_for",
    "_grip_point",
    "widget_under",
    "zone_of",
    "search_hits",
    "_hit_row",
    "next_click",
    "_obstacle_click",
    "_widget_click",
    "_scroll_needed",
    "_row_click",
    "_visible_row_click",
    "_expander_click",
    "_row_scroll",
    "_tile_click",
    "_command_click",
    "_actions_below",
    "_in_the_bar",
    "_chain_click",
    "_open_menus",
    "_menu_action_named",
    "_menubar_chain",
    "_menu_click",
)


def private_reads(source: str, names: tuple[str, ...]) -> list[str]:
    """Jeder Zugriff ``x._name`` in den genannten Funktionen und Klassen."""
    import ast

    tree = ast.parse(source)
    found: list[str] = []
    for node in tree.body:
        if not isinstance(node, ast.FunctionDef | ast.ClassDef) or node.name not in names:
            continue
        for inner in ast.walk(node):
            if (
                isinstance(inner, ast.Attribute)
                and inner.attr.startswith("_")
                and not inner.attr.startswith("__")
            ):
                found.append(f"{node.name}: {ast.unparse(inner)}")
    return found


def test_the_new_resolvers_read_no_private_attribute() -> None:
    import inspect

    from app.ui import guide_targets

    source = inspect.getsource(guide_targets)
    defined = {name for name in NEW_RESOLVERS if hasattr(guide_targets, name)}
    assert defined == set(NEW_RESOLVERS), sorted(set(NEW_RESOLVERS) - defined)
    assert private_reads(source, NEW_RESOLVERS) == []


def test_a_private_read_in_a_resolver_turns_the_guard_red() -> None:
    """Gegenprobe: ``window.feature_panel._apply`` wäre ein Zugriff am Kennzeichen vorbei."""
    source = "def next_click(window, name):\n    return window.feature_panel._apply\n"
    assert private_reads(source, ("next_click",)) == ["next_click: window.feature_panel._apply"]


@pytest.fixture
def prepared_window(qt_app: Any) -> Iterator[Any]:
    """Ein Fenster mit einem Quader samt Bohrung, unter das Bett geschoben.

    Die Attrappe des Renderers gibt der Ansicht eine Projektion; offscreen gibt
    es sonst keine, und die Maßgruppe im Bild bliebe aus.
    """
    from app.core.scene.history import OperationDraft
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings
    from tests.render_fakes import RecordingRenderer

    window = MainWindow(Session(), UiSettings())
    window.viewport.renderer = RecordingRenderer(size=(900, 600))
    window.resize(1400, 900)
    window.show()
    window._show_start_screen(False)
    assert window.session.apply(
        "Quader mit Bohrung",
        [
            OperationDraft(op="create_box"),
            OperationDraft(op="drill_hole", inputs=("obj_1",), params={"diameter": 5.0, "z": 12.0}),
            OperationDraft(
                op="translate_object", inputs=("obj_1",), params={"dx": 0.0, "dy": 0.0, "dz": -15.0}
            ),
        ],
    )
    assert window.session.wait_for_idle(60_000)
    window.report.show_result(window.session.last_result, window.session.project.document)
    _settle(qt_app)
    try:
        yield window
    finally:
        for menu in [*window.findChildren(QMenu), *qt_app.topLevelWidgets()]:
            if isinstance(menu, QMenu) and menu.isVisible():
                menu.hide()
        window.hide()
        window.release()
        window.viewport.renderer = None


def _settle(qt_app: Any, rounds: int = 20) -> None:
    for _ in range(rounds):
        qt_app.processEvents()


def _follow(qt_app: Any, window: Any, name: str) -> str:
    """Den Weg zu ``name`` gehen wie der Kunde: Reiter, Klappe, Aufklappen per Klick
    auf das Rechteck aus ``next_click``, bis das Ziel dasteht."""
    from PySide6.QtTest import QTest

    from app.ui import guide_targets

    for _step in range(6):
        step = guide_targets.next_click(window, name)
        if step.why not in {"reiter", "klappe", "aufklappen"}:
            return str(step.why)
        centre = step.rect.center()
        under = guide_targets.widget_under(centre)
        assert under is not None, (name, step)
        QTest.mouseClick(under, Qt.MouseButton.LeftButton, pos=under.mapFromGlobal(centre))
        _settle(qt_app)
    raise AssertionError(f"{name}: kein Ziel nach sechs Klicks")


def _popup(qt_app: Any, menu: Any) -> None:
    menu.popup(QPoint(40, 40))
    _settle(qt_app, 5)
    assert menu.isVisible()


def test_every_menu_line_carries_a_unique_name_from_its_source(qt_app: Any) -> None:
    """Jede Zeile und jedes Menü der Leiste trägt einen gültigen, eindeutigen Namen;
    eine Zeile in zwei Menüs ist **eine** Aktion mit einem Namen."""
    from app.ui import guide_targets
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    try:
        entries = guide_targets.menubar_entries(window)
        assert len(entries) > 60
        by_action: dict[int, str] = {}
        for name, _menus, action in entries:
            assert name.startswith("menubar."), (name, action.text())
            assert guides.is_target(f"menu:{name}"), name
            by_action[id(action)] = name
        names = list(by_action.values())
        assert len(names) == len(set(names)), sorted(
            name for name in names if names.count(name) > 1
        )
        menus = {
            menu.objectName()
            for menu in window.findChildren(QMenu)
            if menu.objectName().startswith("menubar.")
        }
        assert len(menus) >= 8
        assert not menus & set(names)
        assert not [key for key in window.window_commands() if key.startswith("menu.")]
    finally:
        window.deleteLater()


def test_the_command_keys_do_not_follow_the_position_of_a_line(qt_app: Any) -> None:
    """Eine neue Zeile oben im Menü ändert keine Kennung darunter (Prüfbericht S1)."""
    from PySide6.QtGui import QAction

    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    try:
        before = {
            key: title
            for key, (title, _keys, _slot) in window.window_commands().items()
            if key.startswith("menubar.")
        }
        file_menu = next(
            menu for menu in window.findChildren(QMenu) if menu.objectName() == "menubar.datei"
        )
        probe = QAction("Probe", window)
        probe.setObjectName("menubar.probe")
        file_menu.insertAction(file_menu.actions()[0], probe)
        after = {
            key: title
            for key, (title, _keys, _slot) in window.window_commands().items()
            if key.startswith("menubar.")
        }
        assert set(after) == set(before) | {"menubar.probe"}
        assert {key: after[key] for key in before} == before
    finally:
        window.deleteLater()


def test_every_context_action_carries_a_name(
    prepared_window: Any, qt_app: Any, monkeypatch
) -> None:
    """Baum, Verlauf, Prüfbericht und Parameterleiste: Jede Zeile eines Kontextmenüs
    trägt einen ``objectName``, unter dem ``menu:`` sie findet."""
    window = prepared_window

    def names(menu: Any) -> list[str]:
        found: list[str] = []
        for action in menu.actions():
            if action.isSeparator():
                continue
            found.append(action.objectName())
            if action.menu() is not None:
                found.extend(names(action.menu()))
        return found

    window.object_tree.select_object("obj_1")
    _settle(qt_app)
    on_body = names(window.object_tree.context_menu())
    window.object_tree.select_feature("obj_1", "hole_1")
    _settle(qt_app)
    on_feature = names(window.object_tree.context_menu())
    listing = window.history_panel.list
    on_step = names(window.history_panel.context_menu(listing.item(listing.count() - 1)))
    monkeypatch.setattr(window.parameters, "parameter_at", lambda _position: "breite")
    on_parameter = names(window.parameters.context_menu(QPoint(0, 0)))
    shown: list[list[str]] = []

    class ShownMenu(QMenu):
        """Hält fest, was das Menü zeigen würde, statt modal zu warten."""

        def exec(self, *_args: Any) -> None:  # type: ignore[override]
            shown.append(names(self))

    from app.ui import panels

    monkeypatch.setattr(panels, "QMenu", ShownMenu)
    window.right.setCurrentIndex(1)
    _settle(qt_app)
    report = window.report.list
    row = next(
        number
        for number in range(report.count())
        if getattr(report.item(number).data(Qt.ItemDataRole.UserRole), "code", "")
        == "arrange.below_bed"
    )
    window.report._on_menu(report.visualItemRect(report.item(row)).center())

    assert "tree.visibility" in on_body and "delete_object" in on_body
    assert "tree.step" in on_feature
    assert {"history.edit", "history.switch", "history.delete"} <= set(on_step)
    assert on_parameter == ["parameters.edit"]
    assert shown and "report.place_on_bed" in shown[0]
    for found in (on_body, on_feature, on_step, on_parameter, *shown):
        assert all(found), found
        assert all(guides.is_target(f"menu:{name}") for name in found), found


def test_every_new_kind_resolves_on_a_prepared_window(prepared_window: Any, qt_app: Any) -> None:
    """Jede Art aus dem Wortschatz des Funktionsdurchgangs findet ihr Ziel am Fenster."""
    from app.core.perceive.actions import edge_actions
    from app.ui import guide_targets
    from app.ui.print_settings_dialog import PrintSettingsDialog
    from app.ui.settings_dialog import SettingsDialog

    window = prepared_window
    seen: set[str] = set()

    def widget(name: str) -> Any:
        found = guide_targets.widget_for(window, name)
        assert found is not None, name
        seen.add(name.partition(":")[0])
        return found

    def click(name: str) -> Any:
        found = guide_targets.next_click(window, name)
        seen.add(name.partition(":")[0])
        return found

    # Baum, Verlauf, Prüfbericht
    assert click("tree.row:obj_1").why == "ziel"
    assert click("tree.row:obj_1.hole_1").why in {"aufklappen", "ziel"}
    # Drei Schritte in einer Transaktion: Schritt 1 steht in der zugeklappten
    # Gruppe, der Klick auf ihre Zeile klappt sie auf.
    from PySide6.QtTest import QTest

    step = click("history.row:1")
    assert step.why == "aufklappen"
    surface = window.history_panel.list.viewport()
    QTest.mouseClick(
        surface, Qt.MouseButton.LeftButton, pos=surface.mapFromGlobal(step.rect.center())
    )
    _settle(qt_app)
    assert click("history.row:1").why == "ziel"
    with pytest.raises(guide_targets.MissingTargetError):
        guide_targets.next_click(window, "history.row:99")
    assert _follow(qt_app, window, "finding:arrange.below_bed") == "ziel"
    seen.add("finding")
    report = window.report.list
    for number in range(report.count()):
        if getattr(report.item(number).data(Qt.ItemDataRole.UserRole), "code", "") == (
            "arrange.below_bed"
        ):
            report.setCurrentRow(number)
    _settle(qt_app)
    assert widget("finding.action:place_on_bed").isVisible()

    # Merkmalfenster und Maßgruppe an der Bohrung
    window.object_tree.select_object("obj_1")
    window.object_tree.select_feature("obj_1", "hole_1")
    _settle(qt_app, 40)
    assert widget("feature:resize_hole") is not None
    assert widget("feature.field:resize_hole.diameter") is not None
    assert widget("measure.field:diameter").isVisible()
    assert widget("measure.reference") is not None
    for name in ("feature.apply", "feature.in_view", "feature.every"):
        assert guide_targets.widget_for(window, name) is not None, name

    # Kante
    key = "1 2 3 4 5 6"
    window.feature_panel.show_edge(key, "Kante")
    _settle(qt_app)
    for action in edge_actions(key):
        assert widget(guides.action_target(action)) is not None
    if not edge_actions(key):
        seen.add("edge")

    # Menüleiste, und der Name der Anleitungen für das Verlaufsmenü
    assert click("menu:menubar.speichern_unter").why == "menue"
    listing = window.history_panel.list
    history_menu = window.history_panel.context_menu(listing.item(listing.count() - 1))
    _popup(qt_app, history_menu)
    assert click("history:edit") == guide_targets.Click(
        guide_targets.next_click(window, "menu:history.edit").rect,
        Qt.MouseButton.LeftButton,
        "ziel",
        "history:edit",
    )
    history_menu.hide()

    # Leisten, Suche, Fortschritt, Vorschauband, Nachbauen
    window.tools.toggle("section")
    _settle(qt_app)
    assert widget("handle:bar.section").isVisible()
    window.tools.toggle("section")
    for name in (
        "search",
        "toolbar.search",
        "progress.cancel",
        "preview.banner",
        "selection.rebuild",
    ):
        assert guide_targets.widget_for(window, name) is not None, name

    # Druckdialog und Einstellungen, offen neben dem Fenster
    printing = PrintSettingsDialog(window.session, window.settings, window)
    printing.show()
    _settle(qt_app)
    settings = SettingsDialog(window.settings, window)
    settings.show()
    _settle(qt_app)
    try:
        assert widget("print:layers.layer_height") is not None
        assert click("print:layers.layer_height").why in {"ziel", "reiter", "klappe", "rollen"}
        assert widget("setting:language") is not None
        # Jede Zeile der Einstellungen und jedes Feld des Druckdialogs, nicht nur eines
        from app.core.knowledge.print_fields import FIELDS
        from app.ui.settings_dialog import option_titles

        for key in option_titles():
            assert guide_targets.widget_for(window, f"setting:{key}") is not None, key
        for field in FIELDS:
            assert guide_targets.widget_for(window, f"print:{field.path}") is not None, field.path
        assert widget("dialog:settings_dialog") is settings
        assert widget("dialog:print_settings_dialog") is printing
    finally:
        settings.close()
        printing.close()

    # Stelle im Bild und Griffe brauchen Projektion und Pick; sie prüfen die
    # zwei Fälle darunter an der Attrappe und der native Fall am echten Bild.
    # „Zuletzt geöffnet“ steht auf dem Startbildschirm: eigener Fall darunter.
    seen.update({"view", "start.recent"})
    assert seen >= NEW_KINDS, sorted(NEW_KINDS - seen)


def test_every_widget_has_its_zone(prepared_window: Any, qt_app: Any) -> None:
    """Wo ein Bedienelement steht, in den Zonen des Kriteriums E4."""
    from app.ui import guide_targets
    from app.ui.settings_dialog import SettingsDialog

    window = prepared_window
    host = window.overlay
    assert guide_targets.zone_of(window, window.viewport) == "ansicht"
    assert guide_targets.zone_of(window, window.statusBar()) == "statusleiste"
    assert guide_targets.zone_of(window, window.toolbar) == "kopf"
    assert guide_targets.zone_of(window, window.menuBar()) == "menue"
    if host.right is not None:
        assert guide_targets.zone_of(window, host.right) == "karte_rechts"
    if host.left is not None:
        assert guide_targets.zone_of(window, host.left) == "karte_links"
    menu = QMenu(window)
    assert guide_targets.zone_of(window, menu) == "menue"
    dialog = SettingsDialog(window.settings, window)
    try:
        assert guide_targets.zone_of(window, dialog.language) == "dialog"
    finally:
        dialog.deleteLater()
        menu.deleteLater()


def test_next_click_names_each_step_in_order_and_reveals_nothing(
    prepared_window: Any, qt_app: Any
) -> None:
    """Reiter, Klappe, Menütitel, Untermenü, Aufklappen und Rollen — und nach
    jeder Frage steht das Fenster wie vorher: ``next_click`` deckt nicht auf."""
    from app.ui import guide_targets

    window = prepared_window
    tabs = window.right

    def state() -> tuple[Any, ...]:
        tree = window.object_tree.tree
        return (
            tabs.currentIndex(),
            tuple(
                heading.isChecked()
                for heading in window.findChildren(QToolButton, "sectionHeading")
            ),
            tuple(tree.topLevelItem(row).isExpanded() for row in range(tree.topLevelItemCount())),
            tuple(menu.isVisible() for menu in window.findChildren(QMenu)),
            window.selection_operations.hits.verticalScrollBar().value(),
            tuple(area.verticalScrollBar().value() for area in window.findChildren(QScrollArea)),
        )

    def ask(name: str) -> Any:
        before = state()
        found = guide_targets.next_click(window, name)
        assert state() == before, f"{name}: next_click hat aufgedeckt"
        return found

    # Reiter: Die Suche steht auf der Seite *Auswahl*.
    tabs.setCurrentIndex(1)
    _settle(qt_app)
    step = ask("search")
    assert step.why == "reiter"
    bar = tabs.tabBar()
    assert step.rect == QRect(bar.mapToGlobal(bar.tabRect(0).topLeft()), bar.tabRect(0).size())
    tabs.setCurrentIndex(0)
    _settle(qt_app)
    assert ask("search").why == "ziel"

    # Klappe: der Abschnitt *Objekte* links, zugeklappt
    tree = window.object_tree.tree
    heading = next(
        candidate
        for candidate in window.findChildren(QToolButton, "sectionHeading")
        if candidate.parentWidget() is window.object_tree.parentWidget()
    )
    heading.setChecked(False)
    _settle(qt_app)
    step = ask("tree.row:obj_1")
    assert step.why == "klappe"
    assert step.rect == QRect(heading.mapToGlobal(QPoint(0, 0)), heading.size())
    heading.setChecked(True)
    _settle(qt_app)

    # Aufklappen: eine Merkmalszeile unter einem zugeklappten Körper
    body = tree.topLevelItem(0)
    body.setExpanded(False)
    _settle(qt_app)
    assert ask("tree.row:obj_1.hole_1").why == "aufklappen"
    body.setExpanded(True)
    _settle(qt_app)
    assert ask("tree.row:obj_1.hole_1").why == "ziel"

    # Menütitel, Untermenü, Zeile
    assert ask("menu:menubar.vorne").why == "menue"
    view_menu = next(
        menu for menu in window.findChildren(QMenu) if menu.objectName() == "menubar.ansicht"
    )
    _popup(qt_app, view_menu)
    assert ask("menu:menubar.vorne").why == "untermenue"
    camera = next(
        menu for menu in window.findChildren(QMenu) if menu.objectName() == "menubar.kamera"
    )
    _popup(qt_app, camera)
    assert ask("menu:menubar.vorne").why == "ziel"
    camera.hide()
    view_menu.hide()

    # Rollen: der letzte Treffer einer langen Trefferliste
    window.selection_operations.search.setText("e")
    _settle(qt_app)
    hits = guide_targets.search_hits(window)
    assert len(hits) > 20
    step = ask(hits[-1])
    assert (step.why, step.direction, step.button) == ("rollen", 1, Qt.MouseButton.NoButton)
    assert ask(hits[0]).why == "ziel"
    window.selection_operations.search.setText("")


def test_an_operation_without_a_menu_line_resolves_over_its_button(
    prepared_window: Any, qt_app: Any, monkeypatch
) -> None:
    """Erst der Knopf, dann die Menüzeile (RM-737, B3) — vorher scheiterte eine
    Operation ohne Menüzeile, bevor nach ihrem Knopf gefragt war."""
    from app.ui import guide_targets

    window = prepared_window
    window.right.setCurrentIndex(0)
    window.object_tree.select_object("obj_1")
    _settle(qt_app)
    shown = [
        name
        for name in ("hollow_object", "orient_for_print", "split_pinned", "delete_object")
        if (button := window.selection_operations.button_for(name)) is not None
        and button.isVisible()
    ]
    assert shown, "an einem gewählten Körper steht keiner der Knöpfe"
    name = shown[0]
    monkeypatch.delitem(window._op_actions, name, raising=False)
    button = window.selection_operations.button_for(name)
    assert guide_targets.area_for(window, f"operation:{name}") == QRect(
        button.mapToGlobal(QPoint(0, 0)), button.size()
    )
    assert guide_targets.next_click(window, f"operation:{name}").why == "ziel"


def test_point_for_takes_a_facing_triangle_the_pick_confirms(
    prepared_window: Any, monkeypatch
) -> None:
    """Eine Stelle auf den Dreiecken des Merkmals, die der Pick bestätigt — nie die Achse.

    Die Attrappe projiziert x und y; der Pick ist hier nachgestellt und nimmt
    nur Dreiecke der Bohrung an. Ob ein Klick am echten Fenster das Merkmal
    wählt, prüft der native Fall darunter.
    """
    import numpy as np

    from app.core.geom.mesh import as_mesh_data
    from app.ui import guide_targets

    window = prepared_window
    viewport = window.viewport
    entry = window.session.last_result.scene.objects["obj_1"]
    hole = entry.features["hole_1"]
    raw = as_mesh_data(entry.mesh).raw
    wanted = {int(face) for face in hole.face_indices}
    centres = {index: viewport.display_of(tuple(raw.triangles_center[index])) for index in wanted}

    def picked(x: int, y: int) -> Any:
        for index, spot in centres.items():
            if spot is not None and abs(spot[0] - x) <= 1 and abs(spot[1] - y) <= 1:
                return ("obj_1", (0.0, 0.0, 0.0), index, None)
        return None

    monkeypatch.setattr(viewport, "placement_hit", picked)
    monkeypatch.setattr(guide_targets, "_shows_the_view", lambda _window, _point: True)
    point = guide_targets.point_for(window, "obj_1", "hole_1")
    facing = [
        index
        for index in wanted
        if float(raw.face_normals[index] @ np.asarray(viewport.view_direction())) < 0.0
    ]
    expected = {
        (
            viewport.mapToGlobal(QPoint(round(centres[index][0]), round(centres[index][1]))).x(),
            viewport.mapToGlobal(QPoint(round(centres[index][0]), round(centres[index][1]))).y(),
        )
        for index in facing
    }
    assert (point.x(), point.y()) in expected
    monkeypatch.setattr(viewport, "placement_hit", lambda _x, _y: None)
    with pytest.raises(guide_targets.MissingTargetError, match="keine zugewandte Stelle"):
        guide_targets.point_for(window, "obj_1", "hole_1")


def test_a_grip_is_found_by_the_name_the_renderer_gives_it(
    prepared_window: Any, monkeypatch
) -> None:
    """``handle:move.x`` ist die Stelle, an der der Pick den Pfeil der x-Achse meldet."""
    from types import SimpleNamespace

    from app.ui import guide_targets

    window = prepared_window
    viewport = window.viewport
    renderer = viewport.renderer
    monkeypatch.setattr(viewport, "gizmo_reach", lambda: ((0.0, 0.0, 0.0), 20.0))
    tip = viewport.display_of((8.0, 0.0, 0.0))
    arrow = SimpleNamespace(name="gizmo:arrow:0")
    picks: list[tuple[float, float]] = []

    def pick(x: float, y: float) -> Any:
        picks.append((x, y))
        return arrow if abs(x - tip[0]) <= 6 and abs(y - tip[1]) <= 3 else None

    monkeypatch.setattr(renderer, "pick_item", pick)
    monkeypatch.setattr(guide_targets, "_shows_the_view", lambda _window, _point: True)
    found = guide_targets.next_click(window, "handle:move.x")
    # Liegt der Griff auf einer Achse, reicht die erste Runde (Review L9).
    assert len(picks) < 100, len(picks)
    centre = found.rect.center()
    local = viewport.mapFromGlobal(centre)
    assert abs(local.x() - tip[0]) <= 6 and abs(local.y() - tip[1]) <= 3
    with pytest.raises(guide_targets.MissingTargetError):
        guide_targets.next_click(window, "handle:rotate.z")


def test_widget_under_finds_the_child_and_an_open_menu_first(qt_app: Any) -> None:
    """Die Probe vor jedem Klick, offscreen belegt: das Kind an der Stelle, und ein
    offenes Menü darüber geht vor."""
    from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

    from app.ui import guide_targets

    host = QWidget()
    host.resize(300, 200)
    layout = QVBoxLayout(host)
    first = QPushButton("Eins", host)
    second = QPushButton("Zwei", host)
    layout.addWidget(first)
    layout.addWidget(second)
    host.show()
    _settle(qt_app, 5)
    try:
        point = second.mapToGlobal(second.rect().center())
        assert guide_targets.widget_under(point) is second
        menu = QMenu(host)
        menu.addAction("Probe")
        menu.popup(point)
        _settle(qt_app, 5)
        under = guide_targets.widget_under(menu.mapToGlobal(menu.rect().center()))
        assert under is menu or (under is not None and menu.isAncestorOf(under))
        menu.hide()
    finally:
        host.close()
        host.deleteLater()


@pytest.mark.usefixtures("require_graphics_adapter")
def test_a_click_at_point_for_chooses_the_feature(native_window_platform: str) -> None:
    """Am echten Fenster: Klicks an der Stelle aus ``point_for`` wählen erst den
    Körper, dann die Fläche — die Stelle trifft, was sie verspricht. Danach findet
    ``handle:move.*`` die Pfeile des Bewegungsgriffs im echten Bild."""
    import os
    import subprocess
    import sys

    script = r"""
import app.ui
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from app.core.bootstrap import load_operations
load_operations()
application = QApplication([])
assert application.platformName() not in ('offscreen', 'minimal')
from app.core.scene.history import OperationDraft
from app.ui import guide_targets
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings
window = MainWindow(Session(), UiSettings())
window.resize(1400, 900)
window.show()
assert QTest.qWaitForWindowExposed(window)
window._show_start_screen(False)
assert window.session.apply('Quader', [OperationDraft(op='create_box')])
assert window.session.wait_for_idle(60000)
for _ in range(60):
    application.processEvents()
    QTest.qWait(20)
assert window.viewport.renderer is not None
window.viewport.reset_camera()
for _ in range(30):
    application.processEvents()
    QTest.qWait(20)
assert window.object_tree.selected_feature() != 'face_top'
clicks = 0
for click in range(2):
    if window.object_tree.selected_feature() == 'face_top':
        break
    clicks += 1
    point = guide_targets.point_for(window, 'obj_1', 'face_top')
    under = guide_targets.widget_under(point)
    QTest.mouseClick(under, Qt.MouseButton.LeftButton, pos=under.mapFromGlobal(point))
    for _ in range(30):
        application.processEvents()
        QTest.qWait(20)
assert window.object_tree.selected_feature() == 'face_top', window.object_tree.selected_feature()
window.object_tree.select_object('obj_1')
window.tools.toggle('transform')
for _ in range(30):
    application.processEvents()
    QTest.qWait(20)
for role in ('move.x', 'move.y', 'move.z'):
    step = guide_targets.next_click(window, f'handle:{role}')
    assert step.why == 'ziel', (role, step)
window.release()
print(f'point_for chose the feature after {clicks} clicks', flush=True)
import os
os._exit(0)
"""
    done = subprocess.run(
        [sys.executable, "-c", script],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "QT_QPA_PLATFORM": native_window_platform},
        capture_output=True,
        text=True,
        timeout=240,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert "point_for chose the feature" in done.stdout, done.stdout


def test_the_recent_projects_and_the_dialog_fields_resolve(qt_app: Any, tmp_path: Path) -> None:
    """„Zuletzt geöffnet“ auf dem Startbildschirm (``start.recent:<n>`` ab 1) und die
    Felder des offenen Operationsdialogs (``field:<parameter>``) über ihr Kennzeichen."""
    from app.core.registry import REGISTRY
    from app.ui import guide_targets
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    window.resize(1200, 800)
    window.show()
    try:
        first, second = tmp_path / "eins.p3d", tmp_path / "zwei.p3d"
        window.start_screen.show_recent([first, second])
        _settle(qt_app)
        step = guide_targets.next_click(window, "start.recent:2")
        listing = window.start_screen.recent_list
        place = listing.visualItemRect(listing.item(1))
        assert step.why == "ziel"
        assert step.rect == QRect(listing.viewport().mapToGlobal(place.topLeft()), place.size())
        with pytest.raises(guide_targets.MissingTargetError):
            guide_targets.next_click(window, "start.recent:3")

        window._show_start_screen(False)
        window.run_operation(REGISTRY.get("create_box"))
        _settle(qt_app)
        editor = guide_targets.widget_for(window, "field:width")
        assert editor.property(guides.TARGET_PROPERTY) == "field:width"
        assert editor.window().isVisible()
        assert guide_targets.next_click(window, "field:width").why in {"ziel", "rollen"}
    finally:
        if window._op_dialog is not None:
            window._op_dialog.reject()
        window.hide()
        window.release()


def test_a_menu_hidden_from_the_bar_has_no_way(qt_app: Any) -> None:
    """Auf dem Startbildschirm stehen die Arbeitsmenüs nicht in der Leiste: kein
    Rechteck am Ursprung der Leiste, sondern ``MissingTargetError`` (Review M1)."""
    from app.ui import guide_targets
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    window.resize(1200, 800)
    window.show()
    _settle(qt_app)
    try:
        assert window.start_screen.isVisible()
        for name in ("menu:menubar.vorne", "menu:menubar.einpassen", "menu:menubar.ansicht"):
            with pytest.raises(guide_targets.MissingTargetError, match="nicht in der Leiste"):
                guide_targets.next_click(window, name)
        assert guide_targets.next_click(window, "menu:menubar.oeffnen").why == "menue"
    finally:
        window.hide()
        window.release()


def test_a_window_command_goes_over_its_button_in_the_card(
    prepared_window: Any, qt_app: Any
) -> None:
    """Ein Fensterbefehl mit Knopf in der Karte: erst der Knopf, dann das Menü (Review M4)."""
    from app.ui import guide_targets

    window = prepared_window
    window.right.setCurrentIndex(0)
    window.object_tree.select_object("obj_1")
    _settle(qt_app)
    button = window.selection_operations.button_for("edit.auto_split")
    assert button is not None and button.isVisible(), "Automatisch teilen steht nicht da"
    # area_for rollt den Knopf in den Blick; danach steht er dort, wo next_click ihn nennt.

    def where() -> QRect:
        return QRect(button.mapToGlobal(QPoint(0, 0)), button.size())

    # area_for rollt den Knopf in den Blick (auch um ein paar Punkte zur Seite);
    # verglichen wird je Antwort mit dem Ort des Knopfes in diesem Augenblick.
    assert guide_targets.area_for(window, "command:edit.auto_split") == where()
    _settle(qt_app)
    step = guide_targets.next_click(window, "command:edit.auto_split")
    assert (step.why, step.rect) == ("ziel", where())


def test_an_operation_that_does_not_apply_here_says_so(prepared_window: Any, qt_app: Any) -> None:
    """Ohne Knopf und ohne Menüzeile nennt die Meldung den Grund, nicht ein
    geschlossenes Kontextmenü (Review L4)."""
    from app.ui import guide_targets

    window = prepared_window
    window.right.setCurrentIndex(0)
    window.object_tree.select_object(None)
    _settle(qt_app)
    button = window.selection_operations.button_for("hollow_object")
    assert button is None or not button.isVisible()
    with pytest.raises(guide_targets.MissingTargetError, match="gilt an dieser Auswahl nicht"):
        guide_targets.next_click(window, "operation:hollow_object")


def test_a_closed_submenu_of_an_open_context_menu_is_a_step(
    prepared_window: Any, qt_app: Any
) -> None:
    """*Verschieben vor* im offenen Verlaufsmenü: erst das Untermenü, dann die Zeile
    (Review L5)."""
    from app.core.scene.history import OperationDraft
    from app.ui import guide_targets

    window = prepared_window
    assert window.session.apply("Zweiter Quader", [OperationDraft(op="create_box")])
    assert window.session.wait_for_idle(60_000)
    _settle(qt_app)
    listing = window.history_panel.list
    menu = window.history_panel.context_menu(listing.item(listing.count() - 1))
    further = next(
        action for action in menu.actions() if action.objectName() == "history.move_before"
    )
    entry = further.menu().actions()[0].objectName()
    assert entry.startswith("history.move_before.")
    _popup(qt_app, menu)
    try:
        step = guide_targets.next_click(window, f"menu:{entry}")
        place = menu.actionGeometry(further)
        assert (step.why, step.rect) == (
            "untermenue",
            QRect(menu.mapToGlobal(place.topLeft()), place.size()),
        )
    finally:
        menu.hide()


def test_a_command_of_a_tool_keeps_its_own_name(prepared_window: Any) -> None:
    """``command:tool.section`` antwortet unter seinem eigenen Namen (Review L10)."""
    from app.ui import guide_targets

    step = guide_targets.next_click(prepared_window, "command:tool.section")
    assert step.target == "command:tool.section"


def test_point_for_follows_the_body_where_the_view_draws_it(
    prepared_window: Any, monkeypatch
) -> None:
    """Auseinandergezogen oder auf einer zweiten Platte steht der Körper im Bild
    verschoben (``Viewport.view_offset_of``); die Stelle folgt ihm (Review M2)."""
    from app.core.geom.mesh import as_mesh_data
    from app.ui import guide_targets

    window = prepared_window
    viewport = window.viewport
    entry = window.session.last_result.scene.objects["obj_1"]
    raw = as_mesh_data(entry.mesh).raw
    shift = (40.0, 0.0, 0.0)
    faces = {int(face) for face in entry.features["hole_1"].face_indices}
    drawn = {
        index: viewport.display_of(
            tuple(float(a) + b for a, b in zip(raw.triangles_center[index], shift, strict=True))
        )
        for index in faces
    }

    def picked(x: int, y: int) -> Any:
        for index, spot in drawn.items():
            if spot is not None and abs(spot[0] - x) <= 1 and abs(spot[1] - y) <= 1:
                return ("obj_1", (0.0, 0.0, 0.0), index, None)
        return None

    monkeypatch.setattr(viewport, "view_offset_of", lambda _object_id: shift)
    monkeypatch.setattr(viewport, "placement_hit", picked)
    monkeypatch.setattr(guide_targets, "_shows_the_view", lambda _window, _point: True)
    point = guide_targets.point_for(window, "obj_1", "hole_1")
    local = viewport.mapFromGlobal(point)
    assert any(
        spot is not None and abs(spot[0] - local.x()) <= 1 and abs(spot[1] - local.y()) <= 1
        for spot in drawn.values()
    )


def test_point_for_on_a_coarse_view_takes_only_a_hit_on_its_own_triangle(
    prepared_window: Any, monkeypatch
) -> None:
    """Ohne Dreiecksnummern (grobe Anzeige) gilt ein Pick nur, wenn der getroffene
    Punkt auf dem probierten Dreieck liegt — nicht auf einer Fläche davor."""
    import numpy as np

    from app.core.geom.mesh import as_mesh_data
    from app.ui import guide_targets

    window = prepared_window
    viewport = window.viewport
    entry = window.session.last_result.scene.objects["obj_1"]
    raw = as_mesh_data(entry.mesh).raw
    faces = [int(face) for face in entry.features["hole_1"].face_indices]
    centres = {
        index: (
            viewport.display_of(tuple(raw.triangles_center[index])),
            raw.triangles_center[index],
        )
        for index in faces
    }
    far = np.asarray(raw.bounds[1]) + 50.0

    def picked(near: bool) -> Any:
        def pick(x: int, y: int) -> Any:
            for spot, centre in centres.values():
                if spot is not None and abs(spot[0] - x) <= 1 and abs(spot[1] - y) <= 1:
                    return ("obj_1", tuple(centre if near else far), -1, None)
            return None

        return pick

    monkeypatch.setattr(guide_targets, "_shows_the_view", lambda _window, _point: True)
    monkeypatch.setattr(viewport, "placement_hit", picked(near=False))
    with pytest.raises(guide_targets.MissingTargetError):
        guide_targets.point_for(window, "obj_1", "hole_1")
    monkeypatch.setattr(viewport, "placement_hit", picked(near=True))
    assert guide_targets.point_for(window, "obj_1", "hole_1") is not None


def test_the_menu_names_are_the_same_in_another_language(qt_app: Any) -> None:
    """Die Namen kommen aus der Quelle: auf Englisch gebaut dieselben wie auf Deutsch
    (Review M3) — auf Deutsch sind Anzeige und Quelle gleich und beweisen nichts."""
    from app.i18n import _, set_language
    from app.i18n.catalog import install_language
    from app.ui import guide_targets
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    def names() -> tuple[set[str], set[str], set[str]]:
        window = MainWindow(Session(), UiSettings())
        try:
            entries = guide_targets.menubar_entries(window)
            menus = {
                menu.objectName()
                for menu in window.findChildren(QMenu)
                if menu.objectName().startswith("menubar.")
            }
            return (
                {name for name, _menus, _action in entries},
                menus,
                {text for _name, _menus, action in entries if (text := action.text())},
            )
        finally:
            window.deleteLater()

    german, german_menus, german_texts = names()
    install_language("en")
    set_language("en")
    try:
        english, english_menus, english_texts = names()
        assert guides.menubar_name_of(_("Öffnen …")) == "menubar.oeffnen"
    finally:
        set_language(SOURCE_LANGUAGE)
    assert english_texts != german_texts, "die englische Leiste ist nicht übersetzt"
    assert english == german
    assert english_menus == german_menus


def test_a_widget_below_the_visible_part_is_reached_by_scrolling(qt_app: Any) -> None:
    """Ein Feld unter dem Rand seines Rollbereichs: erst rollen, mit Richtung — und
    ``next_click`` rollt nicht selbst (Review L7)."""
    from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

    from app.ui import guide_targets
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    area = QScrollArea()
    content = QWidget()
    column = QVBoxLayout(content)
    column.addSpacing(900)
    probe = QPushButton("Probe", content)
    probe.setProperty(guides.TARGET_PROPERTY, "setting:probe")
    column.addWidget(probe)
    area.setWidget(content)
    area.resize(300, 200)
    area.show()
    _settle(qt_app)
    try:
        bar = area.verticalScrollBar()
        assert bar.maximum() > 0
        step = guide_targets.next_click(window, "setting:probe")
        assert (step.why, step.direction, step.button) == ("rollen", 1, Qt.MouseButton.NoButton)
        assert step.rect == QRect(area.viewport().mapToGlobal(QPoint(0, 0)), area.viewport().size())
        assert bar.value() == 0, "next_click hat selbst gerollt"
        bar.setValue(bar.maximum())
        _settle(qt_app)
        assert guide_targets.next_click(window, "setting:probe").why == "ziel"
    finally:
        area.close()
        area.deleteLater()
        window.deleteLater()


def test_area_for_opens_the_group_that_next_click_names(prepared_window: Any, qt_app: Any) -> None:
    """Eine Zeile in einer zugeklappten Verlaufsgruppe: ``next_click`` nennt das
    Aufklappen, ``area_for`` nimmt dasselbe Hindernis weg (Review L2)."""
    from app.ui import guide_targets

    window = prepared_window
    assert guide_targets.next_click(window, "history.row:1").why == "aufklappen"
    rect = guide_targets.area_for(window, "history.row:1")
    _settle(qt_app)
    assert guide_targets.next_click(window, "history.row:1") == guide_targets.Click(
        rect, Qt.MouseButton.LeftButton, "ziel", "history.row:1"
    )


def test_open_section_finds_a_heading_in_a_foreign_row(prepared_window: Any, qt_app: Any) -> None:
    """Die Befundliste klappt über eine Überschrift in der Kopfzeile des Berichts
    auf; ``open_section`` und die Hindernisse fragen dieselbe Stelle (Review L3)."""
    from app.ui import guide_targets
    from app.ui.panels import open_section

    window = prepared_window
    content = window.report.list.parentWidget()
    heading = guide_targets.section_heading(content)
    assert heading is not None and heading.parentWidget() is not content.parentWidget()
    heading.setChecked(False)
    _settle(qt_app)
    assert content.isHidden()
    open_section(content)
    _settle(qt_app)
    assert heading.isChecked() and not content.isHidden()


def test_every_reference_under_change_reference_carries_a_name(
    prepared_window: Any, qt_app: Any
) -> None:
    """Unter *Bezug ändern* trägt jeder Bezug einen Namen; der Prüfstand öffnet das
    Menü über ``measure.reference`` und wählt dort (Review L6)."""
    window = prepared_window
    window.object_tree.select_object("obj_1")
    window.object_tree.select_feature("obj_1", "hole_1")
    _settle(qt_app, 40)
    flow = window._quiet_placement
    assert flow is not None
    menu = flow._reference_menu(0)
    assert menu is not None
    try:
        chosen = [action for action in menu.actions() if action.data() is not None]
        assert len(chosen) >= 2, [action.text() for action in menu.actions()]
        names = [action.objectName() for action in chosen]
        assert all(name.startswith("measure.reference.") for name in names), names
        assert len(set(names)) == len(names), names
        assert all(guides.is_target(f"menu:{name}") for name in names), names
    finally:
        menu.hide()


def test_move_before_names_the_numbers_the_history_shows(qt_app: Any) -> None:
    """Nach einem Verschieben zeigen Verlauf und *Verschieben vor* dieselben Nummern —
    das Untermenü nannte die internen Kennungen, und ``history.move_before.<n>``
    übernahm sie (Review U1)."""
    from app.core.scene.history import OperationDraft
    from app.ui import guide_targets
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    window.resize(1400, 900)
    window.show()
    window._show_start_screen(False)
    try:
        for title, draft in (
            ("Quader", OperationDraft(op="create_box")),
            ("Zylinder", OperationDraft(op="create_cylinder")),
            ("Kegel", OperationDraft(op="create_cone")),
            (
                "Verschieben",
                OperationDraft(
                    op="translate_object",
                    inputs=("obj_1",),
                    params={"dx": 0.0, "dy": 0.0, "dz": 5.0},
                ),
            ),
        ):
            assert window.session.apply(title, [draft])
            assert window.session.wait_for_idle(60_000)
        _settle(qt_app)
        listing = window.history_panel.list

        def move_menu() -> Any:
            return window.history_panel.context_menu(listing.item(listing.count() - 1))

        def entries(menu: Any) -> list[Any]:
            further = next(
                action for action in menu.actions() if action.objectName() == "history.move_before"
            )
            return [action for action in further.menu().actions() if action.data() is None]

        # Den letzten Schritt vor Schritt 2 legen: Danach weichen Kennung und Nummer ab.
        target = next(
            action
            for action in entries(move_menu())
            if action.objectName() == "history.move_before.2"
        )
        target.trigger()
        assert window.session.wait_for_idle(60_000)
        _settle(qt_app)
        ids = [listing.item(row).data(Qt.ItemDataRole.UserRole) for row in range(listing.count())]
        assert ids != list(range(1, len(ids) + 1)), f"Kennungen gleich den Nummern: {ids}"

        numbered = [action for action in entries(move_menu()) if action.objectName()[-3:] != "end"]
        assert numbered
        for action in numbered:
            number = action.objectName().rpartition(".")[2]
            shown, _gap, title = action.text().partition("  ")
            assert shown == number, (action.text(), action.objectName())
            _view, row = guide_targets._row(window, "history.row", number, f"history.row:{number}")
            assert title.strip() in row.text(), (action.text(), row.text())
    finally:
        window.hide()
        window.release()


def test_the_window_opens_at_its_start_size(qt_app: Any) -> None:
    """Die Startgröße steht als Konstante; der Prüfstand misst an ihr (Kriterium Z6)."""
    from app.ui.main_window import START_SIZE, MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    try:
        assert (window.width(), window.height()) == START_SIZE
    finally:
        window.deleteLater()


#: Der Kindprozess des Abrisstests: Anwendung wie beim Kunden, Szene vom
#: Startbildschirm öffnen, die Zeile über den Wortschatz suchen und bis zum Ende
#: der Runde halten, dann neu öffnen. ``SOLIDON_PROBE_ITERATOR=1`` setzt die
#: frühere Suche über ``QTreeWidgetItemIterator`` ein — die Gegenprobe.
_TREE_ROUNDS = r"""
import os
import sys
import time
from pathlib import Path
import app.ui
from app.core.bootstrap import load_operations
load_operations()
from app.ui.app import build_application
from app.ui import guide_targets
application, window = build_application([])
window.resize(1280, 820)
window.show()
if os.environ.get('SOLIDON_PROBE_ITERATOR'):
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QTreeWidgetItemIterator
    original = guide_targets._row

    def _row(window, kind, rest, name):
        if kind != 'tree.row':
            return original(window, kind, rest, name)
        tree = window.object_tree.tree
        object_id, feature_id = guide_targets._object_and_feature(rest)
        iterator = QTreeWidgetItemIterator(tree)
        while (item := iterator.value()) is not None:
            if item.data(0, Qt.ItemDataRole.UserRole) == object_id and (
                item.data(1, Qt.ItemDataRole.UserRole) == feature_id
            ):
                return tree, item
            iterator += 1
        raise guide_targets.MissingTargetError(name)

    guide_targets._row = _row


def settle(seconds):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        application.processEvents()
        time.sleep(0.005)


scene = Path(sys.argv[1])
if sys.argv[2] == 'build':
    from app.core.scene.history import OperationDraft
    window._show_start_screen(False)
    assert window.session.apply('Quader mit Bohrung', [
        OperationDraft(op='create_brep_box'),
        OperationDraft(op='drill_hole', inputs=('obj_1',), params={'diameter': 5.0, 'z': 12.0}),
    ])
    assert window.session.wait_for_idle(60000)
    window.session.save_project(scene)
    print('built', flush=True)
    os._exit(0)
for round in range(5):
    previous = window.session.last_result
    window.session.forget_changes()
    window.open_path(scene)
    deadline = time.monotonic() + 120
    while time.monotonic() < deadline:
        settle(0.01)
        result = window.session.last_result
        if result is not None and result is not previous and not window.session.busy:
            break
    settle(0.5)
    held = guide_targets._row(window, 'tree.row', 'obj_1.hole_1', 'tree.row:obj_1.hole_1')
    guide_targets.next_click(window, 'tree.row:obj_1.hole_1')
    settle(0.8)
    held = None
print('tree survived', flush=True)
window.session.forget_changes()
from tools.window_bench import shutdown_window
shutdown_window(window, application)
"""


def _tree_rounds(scene: Path, mode: str, extra: dict[str, str] | None = None) -> Any:
    import os
    import subprocess
    import sys

    return subprocess.run(
        [sys.executable, "-X", "faulthandler", "-c", _TREE_ROUNDS, str(scene), mode],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen", **(extra or {})},
        capture_output=True,
        text=True,
        timeout=600,
    )


def test_the_tree_survives_new_scenes_after_a_row_was_found(qt_app: Any, tmp_path: Path) -> None:
    """Nach der Suche einer Baumzeile riss ein späteres ``ObjectTree.show_scene``
    beim Leeren des Baums ab (Zugriffsverletzung in ``tree.clear()``), solange
    ``_row`` sie mit ``QTreeWidgetItemIterator`` suchte (Fund D0-P: 8 von 12
    Läufen des Prüfstands). Im eigenen Prozess, damit ein Abriss ein roter Fall
    ist und nicht die Suite beendet; sechs Prozesse zu je fünf Öffnungen, weil
    er nicht jedes Mal kommt (Gegenprobe mit dem Iterator: 3 von 8 Prozessen)."""
    del qt_app
    scene = tmp_path / "szene.p3d"
    built = _tree_rounds(scene, "build")
    assert built.returncode == 0 and "built" in built.stdout, built.stderr[-3000:]
    for attempt in range(6):
        done = _tree_rounds(scene, "rounds")
        assert done.returncode == 0, (attempt, done.returncode, done.stderr[-4000:])
        assert "tree survived" in done.stdout


def tree_iterator_uses(source: str) -> list[int]:
    """Die Zeilen, in denen ``QTreeWidgetItemIterator`` als Name vorkommt — Import,
    Aufruf oder Attribut, nicht im Kommentar."""
    import ast

    lines: set[int] = set()
    for node in ast.walk(ast.parse(source)):
        named = (
            node.id
            if isinstance(node, ast.Name)
            else node.attr
            if isinstance(node, ast.Attribute)
            else node.name
            if isinstance(node, ast.alias)
            else ""
        )
        if named == "QTreeWidgetItemIterator":
            lines.add(getattr(node, "lineno", 0))
    return sorted(lines)


def test_no_tree_item_iterator_in_the_application() -> None:
    """``QTreeWidgetItemIterator`` hinterlässt in PySide Zeilenhüllen, an denen ein
    späteres ``QTreeWidget.clear()`` abreißt (Fund D0-P); Zeilen werden über
    ``topLevelItem``/``child`` gesucht. Rekursiv über ``app/`` und ``tools/``
    (W4): Prüfstand und Aufnahmen laufen im Prozess der Anwendung, ein Iterator
    dort risse denselben Baum ab (Nachprüfung D0-W, N4)."""
    root = Path(__file__).resolve().parents[1]
    found = [
        f"{path.relative_to(root).as_posix()}:{number}"
        for folder in ("app", "tools")
        for path in sorted((root / folder).rglob("*.py"))
        for number in tree_iterator_uses(path.read_text(encoding="utf-8"))
    ]
    assert found == []


def test_a_tree_item_iterator_turns_the_guard_red() -> None:
    source = (
        "from PySide6.QtWidgets import QTreeWidgetItemIterator\n"
        "# QTreeWidgetItemIterator im Kommentar zählt nicht\n"
        "def walk(tree):\n"
        "    return QtWidgets.QTreeWidgetItemIterator(tree)\n"
    )
    assert tree_iterator_uses(source) == [1, 4]


#: Der Kindprozess des Überstandstests: Anwendung wie beim Kunden (mit Stilblatt
#: und Einstellungen — im nackten Fenster stand *Vorher/Nachher* nicht da), ein
#: Körper mit Bohrung, aufgeklappt, dann Fensterhöhen von 820 bis 640 Punkten.
#: ``SOLIDON_PROBE_OLD_HISTORY=1`` setzt die frühere Höhenmeldung des Verlaufs
#: ohne den Abstand ein — die Gegenprobe.
_SECTIONS = r"""
import os
import time
import app.ui
from PySide6.QtCore import QPoint
from PySide6.QtWidgets import QWidget
from app.core.bootstrap import load_operations
load_operations()
from app.ui.app import build_application
application, window = build_application([])
from app.core.scene.history import OperationDraft
from app.ui.overlay import extra_height, is_room_taker, living
from app.ui.panels import HistoryPanel
if os.environ.get('SOLIDON_PROBE_OLD_HISTORY'):
    def _old(self):
        if self.compare.isHidden():
            return 0
        return self.compare.sizeHint().height() + (
            self.timeline.sizeHint().height() if self.compare.isChecked() else 0
        )
    HistoryPanel._timeline_height = _old


def settle(seconds):
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        application.processEvents()
        time.sleep(0.005)


window.resize(800, 800)
window.show()
window._show_start_screen(False)
assert window.session.apply('Quader mit Bohrung', [
    OperationDraft(op='create_box'),
    OperationDraft(op='drill_hole', inputs=('obj_1',), params={'diameter': 5.0, 'z': 12.0}),
])
assert window.session.wait_for_idle(60000)
tree = window.object_tree.tree
tree.topLevelItem(0).setExpanded(True)
zone = window.overlay.left
section = window.object_tree.parentWidget()
checked = 0
problems = []
for height in range(820, 640, -12):
    window.resize(800, height)
    settle(0.4)
    takers = [
        child for child in living(zone, QWidget)
        if is_room_taker(child) and child.isVisibleTo(zone)
    ]
    floors = sum(child.least_height() for child in takers)
    if extra_height(zone) + floors > window.overlay.card_room():
        continue
    checked += 1
    for child in takers:
        holder = child.parentWidget()
        if holder.height() < holder.minimumSizeHint().height():
            least = holder.minimumSizeHint().height()
            problems.append((height, type(child).__name__, holder.height(), least))
    bottom = tree.mapTo(section, QPoint(0, tree.height())).y()
    if bottom > section.height():
        problems.append((height, 'Baum', bottom, section.height()))
print('geprüft', checked, flush=True)
print('probleme', problems, flush=True)
window.session.forget_changes()
from tools.window_bench import shutdown_window
shutdown_window(window, application)
"""


def _sections(extra: dict[str, str] | None = None) -> Any:
    import os
    import subprocess
    import sys

    return subprocess.run(
        [sys.executable, "-X", "faulthandler", "-c", _SECTIONS],
        cwd=Path(__file__).resolve().parents[1],
        env={**os.environ, "QT_QPA_PLATFORM": "offscreen", **(extra or {})},
        capture_output=True,
        text=True,
        timeout=600,
    )


def test_the_object_tree_stays_inside_its_section_when_the_card_is_tight(qt_app: Any) -> None:
    """Die linke Karte teilt ihre Höhe auf Baum, Parameter und Verlauf; passt das
    Ganze, ragt kein Abschnitt über seinen Platz. Der Verlauf nahm den Abstand
    zwischen *Vorher/Nachher* und seiner Liste, ohne ihn zu melden — der Baum ragte
    um diese Punkte über seinen Abschnitt, und seine letzte Zeile war
    abgeschnitten (Fund D0-P, 800 × 800). Im eigenen Prozess, weil die Anwendung
    wie beim Kunden gebaut sein muss."""
    del qt_app
    done = _sections()
    assert done.returncode == 0, done.stderr[-3000:]
    assert "probleme []" in done.stdout, done.stdout
    checked = int(done.stdout.split("geprüft", 1)[1].split()[0])
    assert checked >= 5, done.stdout


def test_a_row_cut_off_by_its_parent_is_reached_by_scrolling(qt_app: Any) -> None:
    """Eine Zeile, deren Liste über ihren Elternteil ragt, ist nur halb zu sehen;
    gefragt wird der sichtbare Teil der Liste, nicht ihr ganzes Rechteck (Fund
    D0-P: die letzte Baumzeile hieß „ziel“, obwohl 8 Punkte abgeschnitten waren)."""
    from PySide6.QtWidgets import QListWidget, QWidget

    from app.ui import guide_targets

    host = QWidget()
    host.resize(240, 100)
    listing = QListWidget(host)
    listing.setGeometry(0, 0, 240, 300)
    for number in range(12):
        listing.addItem(f"Zeile {number}")
    host.show()
    _settle(qt_app, 5)
    try:
        visible = listing.viewport().visibleRegion().boundingRect()
        cut = next(
            listing.item(row)
            for row in range(listing.count())
            if listing.visualItemRect(listing.item(row)).bottom() > visible.bottom()
            and listing.visualItemRect(listing.item(row)).top() <= visible.bottom()
        )
        step = guide_targets._visible_row_click(listing, cut, "history.row:1", "ziel")
        assert (step.why, step.direction) == ("rollen", 1)
        whole = listing.item(0)
        assert guide_targets._visible_row_click(listing, whole, "history.row:1", "ziel").why == (
            "ziel"
        )
    finally:
        host.close()
        host.deleteLater()


def test_the_expired_demo_and_the_parameter_dialog_resolve(qt_app: Any, monkeypatch) -> None:
    """Das Fenster nach abgelaufener Demo (ein ``QMessageBox`` ohne eigene Klasse)
    heißt ``dialog:expired_demo``; im Dialog für Projektparameter lösen Name, Wert,
    Einheit, Grenzen und Ausdruck als ``field:`` auf (Funde D0-L)."""
    from PySide6.QtWidgets import QMessageBox

    from app.core import activation
    from app.ui import dialogs, guide_targets
    from app.ui.dialogs import EXPIRED_DEMO_TARGET, ParameterDialog
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    seen: list[Any] = []

    class ShownBox(QMessageBox):
        """Zeigt sich, statt modal zu warten, und hält fest, was der Wortschatz findet."""

        def exec(self) -> int:  # type: ignore[override]
            self.show()
            _settle(qt_app, 3)
            seen.append(guide_targets.widget_for(window, EXPIRED_DEMO_TARGET))
            seen.append(self)
            self.hide()
            return 0

    monkeypatch.setattr(dialogs, "QMessageBox", ShownBox)
    try:
        assert guides.is_target(EXPIRED_DEMO_TARGET)
        dialogs.show_expired_demo(activation.Activation())
        assert seen and seen[0] is seen[1]

        dialog = ParameterDialog({}, window)
        dialog.show()
        _settle(qt_app, 3)
        expected = {
            "name": dialog.name_field,
            "value": dialog.value_field,
            "unit": dialog.unit_field,
            "minimum": dialog.minimum_field,
            "maximum": dialog.maximum_field,
            "expression": dialog.expression_field,
        }
        for key, editor in expected.items():
            assert guide_targets.widget_for(window, f"field:{key}") is editor, key
        dialog.close()
    finally:
        window.deleteLater()


def test_a_field_of_the_modal_dialog_comes_first(qt_app: Any) -> None:
    """Stehen zwei Felder mit demselben Ziel da — ``field:name`` im Operationsdialog
    und im modalen Dialog für Projektparameter —, ist das im modalen Fenster
    gemeint: Nur dort kann der Kunde klicken (Nachprüfung D0-W, N3)."""
    from PySide6.QtWidgets import QDialog, QLineEdit, QVBoxLayout

    from app.ui import guide_targets
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    window = MainWindow(Session(), UiSettings())
    dialogs = []
    fields = []
    for modal in (False, True):
        dialog = QDialog(window)
        field = QLineEdit(dialog)
        QVBoxLayout(dialog).addWidget(field)
        field.setProperty(guides.TARGET_PROPERTY, "field:name")
        dialog.setModal(modal)
        dialog.show()
        dialogs.append(dialog)
        fields.append(field)
    _settle(qt_app, 5)
    try:
        assert qt_app.activeModalWidget() is dialogs[1]
        assert guide_targets.widget_for(window, "field:name") is fields[1]
    finally:
        for dialog in dialogs:
            dialog.close()
            dialog.deleteLater()
        window.deleteLater()
