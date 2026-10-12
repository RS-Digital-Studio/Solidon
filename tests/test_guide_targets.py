"""Die Auflösung des Wortschatzes am Fenster (RM-737, Funktionsdurchgang).

Was ``app/ui/guide_targets.py`` aus einem Namen macht: Widget, Ort, der nächste
Klick des Kunden (``next_click``), die Stelle im Bild (``point_for``), die Probe
(``widget_under``), die Zone; dazu die Namen der Menüleiste und der
Kontextmenüs und die Kennzeichen der Dialoge. Die Fensterfunde, die der
Prüfstand dabei fand, stehen in ``tests/test_bench_findings.py``.
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
    "_message_button",
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
    "_can_roll",
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
        for name in (
            "setting.section:anwendung",
            "setting.section:weitere_einstellungen",
            "setting.section:vorgaben_fuer_neue_projekte",
        ):
            heading = widget(name)
            assert heading.objectName() == "sectionHeading", name
    finally:
        settings.close()
        printing.close()

    # Stelle im Bild und Griffe brauchen Projektion und Pick; sie prüfen die
    # zwei Fälle darunter an der Attrappe und der native Fall am echten Bild.
    # „Zuletzt geöffnet“ steht auf dem Startbildschirm: eigener Fall darunter.
    # Die rohen Meldungsfenster und ihre Knöpfe gehen modal auf: eigene Fälle darunter.
    seen.update({"view", "start.recent", "message", "message.button"})
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


#: Woran ein rohes Meldungsfenster zu erkennen ist: ``QMessageBox(…)`` oder ein
#: statischer Aufruf (``QMessageBox.information``, ``QInputDialog.getText``,
#: ``QColorDialog.getColor``).
_RAW_STATIC = {
    ("QMessageBox", "information"),
    ("QMessageBox", "question"),
    ("QMessageBox", "warning"),
    ("QMessageBox", "critical"),
    ("QMessageBox", "about"),
    ("QInputDialog", "getItem"),
    ("QInputDialog", "getText"),
    ("QInputDialog", "getInt"),
    ("QInputDialog", "getDouble"),
    ("QInputDialog", "getMultiLineText"),
    ("QColorDialog", "getColor"),
}


def raw_window_names(source: str) -> tuple[list[str], list[str]]:
    """Die rohen Meldungsfenster einer Datei: die ohne Kennzeichen und die Namen.

    Ein statischer Aufruf steht in ``with raw_window("message:<sache>")``; ein
    ``QMessageBox(…)`` bekommt in derselben Funktion ``setProperty`` mit
    ``guides.TARGET_PROPERTY`` und einem Namen (oder einer Konstanten wie
    ``EXPIRED_DEMO_TARGET``). Die Funktion ist die innerste, die den Aufruf trägt.
    """
    import ast

    tree = ast.parse(source)
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    missing: list[str] = []
    names: list[str] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        instance = isinstance(func, ast.Name) and func.id in {
            "QMessageBox",
            "QInputDialog",
            "QColorDialog",
        }
        static = (
            isinstance(func, ast.Attribute)
            and isinstance(func.value, ast.Name)
            and (func.value.id, func.attr) in _RAW_STATIC
        )
        if not (instance or static):
            continue
        chain = []
        probe: ast.AST = node
        while probe in parents:
            probe = parents[probe]
            chain.append(probe)
        function = next(
            (item for item in chain if isinstance(item, ast.FunctionDef | ast.AsyncFunctionDef)),
            None,
        )
        given: list[ast.expr] = []
        if static:
            given = [
                entry.context_expr.args[0]
                for item in chain
                if isinstance(item, ast.With)
                for entry in item.items
                if isinstance(entry.context_expr, ast.Call)
                and ast.unparse(entry.context_expr.func) == "raw_window"
            ]
        elif function is not None:
            given = [
                call.args[1]
                for call in ast.walk(function)
                if isinstance(call, ast.Call)
                and isinstance(call.func, ast.Attribute)
                and call.func.attr == "setProperty"
                and len(call.args) == 2
                and ast.unparse(call.args[0]) == "guides.TARGET_PROPERTY"
                and (
                    isinstance(call.args[1], ast.Name)
                    or (
                        isinstance(call.args[1], ast.Constant)
                        and str(call.args[1].value).startswith("message:")
                    )
                )
            ]
        if not given:
            label = function.name if function else "<modul>"
            missing.append(f"{label} (Zeile {node.lineno})")
        names.extend(str(value.value) for value in given[:1] if isinstance(value, ast.Constant))
    return missing, names


def test_every_raw_message_window_carries_its_name() -> None:
    """Jedes rohe Meldungsfenster unter ``app/ui`` trägt ``message:<sache>`` (Nachtrag
    D0-W): Sonst findet der Prüfstand Wiederherstellen, Speicherfrage und
    Löschnachfrage nur als „irgendein Meldungsfenster“. Jeder Name ist gültig und
    gehört genau einem Fenster."""
    root = Path(__file__).resolve().parents[1] / "app" / "ui"
    missing: list[str] = []
    names: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if path.name == "window_names.py":
            continue
        lacking, named = raw_window_names(path.read_text(encoding="utf-8"))
        missing.extend(f"{path.relative_to(root).as_posix()}: {entry}" for entry in lacking)
        names.extend(sorted(set(named)))
    assert missing == []
    assert [name for name in names if not guides.is_target(name)] == []
    assert sorted(name for name in set(names) if names.count(name) > 1) == []
    assert len(names) >= 25, "die Suche nach rohen Fenstern greift nicht mehr"


def test_an_unnamed_raw_window_turns_the_guard_red() -> None:
    source = (
        "def ask(parent):\n"
        "    return QMessageBox.question(parent, 'a', 'b')\n"
        "def named(parent):\n"
        "    with raw_window('message:sample_named'):\n"
        "        return QInputDialog.getText(parent, 'a', 'b')\n"
        "def boxed(parent):\n"
        "    box = QMessageBox(parent)\n"
        "    return box.exec()\n"
    )
    assert raw_window_names(source) == (
        ["ask (Zeile 2)", "boxed (Zeile 7)"],
        ["message:sample_named"],
    )


def test_a_raw_message_window_resolves_while_it_is_open(qt_app: Any) -> None:
    """Ein rohes Fenster, statisch oder mit Objekt, heißt im Wortschatz nach seiner
    Funktion, solange es offen ist — geprüft aus dem Lauf des modalen Fensters."""
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QDialog, QInputDialog, QMessageBox

    from app.ui import dialogs, guide_targets
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings
    from app.ui.window_names import raw_window

    window = MainWindow(Session(), UiSettings())
    window.show()
    found: dict[str, Any] = {}

    def look(name: str) -> None:
        def inside() -> None:
            modal = qt_app.activeModalWidget()
            try:
                found[name] = (guide_targets.widget_for(window, name), modal)
                found[name + "/why"] = guide_targets.next_click(window, name).why
            except guide_targets.MissingTargetError as problem:
                found[name] = (problem, modal)
            finally:
                # Erst schließen, dann prüfen: Ein offenes modales Fenster hielte
                # den Test an, statt ihn rot zu machen.
                if isinstance(modal, QDialog):
                    modal.reject()

        QTimer.singleShot(50, inside)

    try:
        look("message:sample_text")
        with raw_window("message:sample_text"):
            QInputDialog.getText(window, "Probe", "Name")
        look("message:sample_box")
        with raw_window("message:sample_box"):
            QMessageBox.information(window, "Probe", "Satz")
        look("message:unsaved_changes")
        dialogs.confirm_unsaved("Probe", window)
        for name in (
            "message:sample_text",
            "message:sample_box",
            "message:unsaved_changes",
        ):
            widget, modal = found[name]
            assert widget is modal and modal is not None, name
            assert found.get(name + "/why") == "ziel", name
    finally:
        window.hide()
        window.release()


def unnamed_message_buttons(source: str) -> list[str]:
    """Jeder Knopf eines rohen ``QMessageBox(…)``, der keinen Namen bekommt.

    In einer Funktion, die ein ``QMessageBox`` baut, steht jedes ``addButton`` in
    einer Zuweisung, und derselbe Knopf geht an ``name_button``
    (``message.button:<sache>.<knopf>``, ``app/ui/window_names.py``) — ein Knopf
    mit Text wie ein Standardknopf: Der Prüfstand drückt ihn über seinen Namen,
    nicht über die Beschriftung, die mit der Sprache wechselt."""
    import ast

    tree = ast.parse(source)
    parents = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    missing: list[str] = []
    for function in ast.walk(tree):
        if not isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef):
            continue
        calls = [node for node in ast.walk(function) if isinstance(node, ast.Call)]
        if not any(
            isinstance(call.func, ast.Name) and call.func.id == "QMessageBox" for call in calls
        ):
            continue
        named = {
            ast.unparse(call.args[0])
            for call in calls
            if isinstance(call.func, ast.Name) and call.func.id == "name_button" and call.args
        }
        for call in calls:
            if not (isinstance(call.func, ast.Attribute) and call.func.attr == "addButton"):
                continue
            holder = parents.get(call)
            target = (
                ast.unparse(holder.targets[0])
                if isinstance(holder, ast.Assign) and len(holder.targets) == 1
                else None
            )
            if target is None or target not in named:
                missing.append(f"{function.name} (Zeile {call.lineno})")
    return missing


def test_every_button_of_a_raw_message_window_carries_its_name() -> None:
    """Die Speicherfrage, die Löschnachfrage und die Handlungen einer Fehlermeldung
    haben Knöpfe mit Namen (``message.button:<sache>.<knopf>``); die Knöpfe
    statischer Aufrufe heißen nach ihrem Standardknopf."""
    root = Path(__file__).resolve().parents[1] / "app" / "ui"
    found = [
        f"{path.relative_to(root).as_posix()}: {entry}"
        for path in sorted(root.rglob("*.py"))
        for entry in unnamed_message_buttons(path.read_text(encoding="utf-8"))
    ]
    assert found == []
    counted = sum(
        source.count('"message.button:') + source.count('f"message.button:')
        for source in (path.read_text(encoding="utf-8") for path in root.rglob("*.py"))
    )
    assert counted >= 15, "die Suche nach Knöpfen greift nicht mehr"


def test_an_unnamed_message_button_turns_the_guard_red() -> None:
    source = (
        "def ask(parent):\n"
        "    box = QMessageBox(parent)\n"
        "    keep = box.addButton('a', role)\n"
        "    name_button(keep, 'message.button:sample_ask.keep')\n"
        "    box.addButton(QMessageBox.StandardButton.Close)\n"
        "    other = box.addButton('b', role)\n"
        "    return box.exec()\n"
        "def outside(dialog):\n"
        "    return dialog.buttons.addButton('b', role)\n"
    )
    assert unnamed_message_buttons(source) == ["ask (Zeile 5)", "ask (Zeile 6)"]


#: Die Stämme der Module unter ``app/ui`` — ein Ziel nennt keinen davon als Ort.
_UI_STEMS = frozenset(
    path.stem
    for path in (Path(__file__).resolve().parents[1] / "app" / "ui").rglob("*.py")
    if path.stem != "__init__"
)


def placed_in_a_module(name: str) -> bool:
    """Ob ``name`` einen Modulstamm als Ort nennt: als Glied, auf das noch etwas
    folgt (``message:dialogs.confirm_unsaved``). Ein Name, der selbst wie ein
    Modul heißt (``tour``, ``dialog:settings_dialog`` nach der Klasse), nennt die
    Sache und nicht ihren Ort."""
    import re

    parts = [part for part in re.split(r"[:.]", name) if part]
    return any(part in _UI_STEMS for part in parts[:-1])


def _names_in_the_sources() -> list[str]:
    """Jeder Zielname, der als Text im Quelltext von ``app/`` und ``tools/`` steht,
    dazu die festen Ziele; aus einem f-String der feste Anfang."""
    import ast

    root = Path(__file__).resolve().parents[1]
    found: set[str] = set(guides.TARGETS)
    kinds = tuple(f"{kind}:" for kind in guides.TARGET_KINDS)
    for folder in ("app", "tools"):
        for path in sorted((root / folder).rglob("*.py")):
            for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
                if isinstance(node, ast.Constant) and isinstance(node.value, str):
                    if guides.is_target(node.value):
                        found.add(node.value)
                elif isinstance(node, ast.JoinedStr) and node.values:
                    head = node.values[0]
                    if (
                        isinstance(head, ast.Constant)
                        and isinstance(head.value, str)
                        and head.value.startswith(kinds)
                    ):
                        found.add(head.value + "x")
    return sorted(found)


def test_no_target_names_the_module_it_lives_in() -> None:
    """Ein Ziel nennt die Sache, nie Datei oder Modul: Die Codestruktur teilt
    ``dialogs.py`` und ``main_window.py`` auf, und ein Name mit Modul verlöre
    Tour, Anleitungen und Funktionsdurchgang (Koordinator D0, L stellte seine
    Kennungen ebenso um)."""
    names = _names_in_the_sources()
    assert len(names) >= 100, "die Suche nach Zielnamen greift nicht mehr"
    assert [name for name in names if placed_in_a_module(name)] == []


def test_a_target_with_a_module_turns_the_guard_red() -> None:
    assert placed_in_a_module("message:dialogs.confirm_unsaved")
    assert placed_in_a_module("message.button:main_window.recovery.restore")
    assert placed_in_a_module("menu:panels.history.up")
    assert not placed_in_a_module("message:unsaved_changes")
    assert not placed_in_a_module("message.button:unsaved_changes.save")
    assert not placed_in_a_module("tour")
    assert not placed_in_a_module("dialog:print_settings_dialog")


def test_the_buttons_of_a_message_window_resolve_while_it_is_open(qt_app: Any) -> None:
    """Speicherfrage, Fehlermeldung mit Handlung und ein statischer Aufruf: Jeder
    Knopf ist über seinen Namen zu finden, solange sein Fenster offen ist, und
    ist dann selbst der nächste Klick."""
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QAbstractButton, QDialog, QMessageBox

    from app.core.errors import RETRY, AppError
    from app.ui import dialogs, guide_targets
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings
    from app.ui.window_names import raw_window

    window = MainWindow(Session(), UiSettings())
    window.show()
    found: dict[str, Any] = {}

    def look(*names: str) -> None:
        def inside() -> None:
            modal = qt_app.activeModalWidget()
            try:
                for name in names:
                    try:
                        widget = guide_targets.widget_for(window, name)
                        why = guide_targets.next_click(window, name).why
                        # Gelesen, solange das Fenster lebt: Ein statischer
                        # Aufruf löscht seine Knöpfe beim Schließen.
                        found[name] = (
                            isinstance(widget, QAbstractButton) and widget.window() is modal,
                            why,
                            widget.text() if isinstance(widget, QAbstractButton) else repr(widget),
                        )
                    except guide_targets.MissingTargetError as problem:
                        found[name] = (False, "", str(problem))
            finally:
                if isinstance(modal, QDialog):
                    modal.reject()

        QTimer.singleShot(50, inside)

    unsaved = tuple(
        f"message.button:unsaved_changes.{key}" for key in ("save", "discard", "cancel")
    )
    failed = ("message.button:error.retry", "message.button:error.cancel")
    asked = ("message.button:sample_ask.yes", "message.button:sample_ask.no")
    try:
        look(*unsaved)
        dialogs.confirm_unsaved("Probe", window)
        look(*failed)
        dialogs.show_error(
            AppError("Probe", suggestions=(RETRY,)), window, handlers={"retry": lambda error: None}
        )
        look(*asked)
        with raw_window("message:sample_ask"):
            QMessageBox.question(window, "Probe", "Satz")
        for name in (*unsaved, *failed, *asked):
            inside_modal, why, label = found[name]
            assert inside_modal, (name, label)
            assert why == "ziel", name
        assert found[failed[0]][2] == str(RETRY.label)
    finally:
        window.hide()
        window.release()


def test_chat_and_tour_are_pages_of_the_right_card(prepared_window: Any, qt_app: Any) -> None:
    """*Chat* und *Tour* sind feste Ziele; hinter einem anderen Reiter ist der Reiter
    der nächste Klick."""
    from app.ui import guide_targets

    window = prepared_window
    window.right.setCurrentIndex(0)
    _settle(qt_app)
    for name, page in (("chat", window.chat), ("tour", window.tour)):
        assert guide_targets.widget_for(window, name) is page
        index = window.right.indexOf(page)
        if index >= 0 and not window.right.tabBar().isTabVisible(index):
            continue
        assert guide_targets.next_click(window, name).why == "reiter", name
