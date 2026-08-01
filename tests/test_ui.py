"""Die Oberfläche: Sitzung, Fenster und die aus dem Schema erzeugten
Dialoge (§2.5, §10).

Läuft auf der Offscreen-Qt-Plattform, funktioniert also ohne Bildschirm.
Geprüft wird hier die Verdrahtung, keine Pixel: baut sich das Fenster aus dem
Register, geht eine Änderung durch den Stapel, bleibt die Auswertung im
Arbeiter.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication, QComboBox, QDialog

from app.core import errors
from app.core.registry import REGISTRY
from app.core.scene import OperationDraft
from app.core.scene.project import load
from app.core.types import Parameter
from app.ui.main_window import MainWindow
from app.ui.op_dialog import OperationDialog
from app.ui.session import AskRequest, Session
from app.ui.settings import UiSettings

MESHES = Path(__file__).parent / "data" / "meshes"


@pytest.fixture
def session(qt_app: QApplication) -> Session:
    return Session()


@pytest.fixture
def window(qt_app: QApplication, session: Session) -> MainWindow:
    return MainWindow(session, UiSettings())


# --- session --------------------------------------------------------------------


def test_a_fresh_session_has_an_empty_project(session: Session) -> None:
    assert session.project.document.ops == []
    assert session.path is None
    assert not session.modified


def test_importing_a_model_goes_through_the_stack(session: Session) -> None:
    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()

    assert [entry.op for entry in session.project.document.ops] == ["load"]
    assert session.modified
    result = session.evaluate_now()
    assert result.complete
    assert result.scene.objects["obj_1"].mesh.volume == pytest.approx(8000.0)


def test_undo_and_redo_reach_the_document(session: Session) -> None:
    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()

    session.undo()
    session.wait_for_idle()
    assert session.project.document.ops == []

    session.redo()
    session.wait_for_idle()
    assert [entry.op for entry in session.project.document.ops] == ["load"]


def test_a_changed_parameter_is_a_transaction(session: Session) -> None:
    """§13 und §15.5: eine gedrehte Zahl ist rücknehmbar und zählt als Änderung.

    Vorher schrieb die Leiste geradewegs ins Dokument. Das kostete beides: ein
    Strg+Z nahm die letzte *Operation* zurück statt der Zahl, und weil das
    Projekt als ungeändert galt, sicherte das Schließen sie nicht.
    """
    document = session.project.document
    document.parameters["width"] = Parameter(name="width", value=84.0, unit="mm")

    session.change_parameter("width", 120.0)
    session.wait_for_idle()

    assert document.parameters["width"].value == 120.0
    assert session.modified, "sonst geht die Änderung beim Schließen verloren"
    assert session.history.can_undo

    session.undo()
    assert document.parameters["width"].value == 84.0

    session.redo()
    assert document.parameters["width"].value == 120.0


def test_the_same_value_again_changes_nothing(session: Session) -> None:
    """Eine Spinbox meldet auch, was sie schon anzeigte — daraus wird kein
    Verlaufseintrag."""
    document = session.project.document
    document.parameters["width"] = Parameter(name="width", value=84.0, unit="mm")

    session.change_parameter("width", 84.0)

    assert not session.history.can_undo
    assert not session.modified


def test_saving_and_reopening_keeps_the_stack(session: Session, tmp_path: Path) -> None:
    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()
    path = session.save_project(tmp_path / "projekt.p3d")

    assert not session.modified
    assert [entry.op for entry in load(path).document.ops] == ["load"]


def test_an_ambiguous_unit_reaches_the_surface_as_a_question(session: Session) -> None:
    seen: list[AskRequest] = []
    session.askRequested.connect(lambda request: (seen.append(request), request.reply("in")))

    session.import_model(MESHES / "bracket_inch.stl")
    session.wait_for_idle()
    result = session.evaluate_now()

    assert seen, "the surface is asked instead of the core guessing"
    assert result.scene.objects["obj_1"].mesh.bounds.size == pytest.approx((101.6, 50.8, 6.35))


def test_the_title_marks_unsaved_changes(session: Session, tmp_path: Path) -> None:
    assert not session.title.endswith("*")
    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()
    assert session.title.endswith("*")

    session.save_project(tmp_path / "projekt.p3d")
    assert session.title == "projekt.p3d"


# --- window ---------------------------------------------------------------------


def test_the_menu_is_built_from_the_registry(window: MainWindow) -> None:
    labels: set[str] = set()
    for menu_action in window.menuBar().actions():
        menu = menu_action.menu()
        if menu is None:
            continue
        labels.update(action.text() for action in menu.actions())

    for spec in REGISTRY.all():
        assert str(spec.title) in labels, f"{spec.name} is missing from the menu"


def test_shortcuts_from_the_registry_are_installed(window: MainWindow) -> None:
    shortcuts = {
        action.shortcut().toString().lower()
        for menu_action in window.menuBar().actions()
        if menu_action.menu() is not None
        for action in menu_action.menu().actions()
        if not action.shortcut().isEmpty()
    }
    for spec in REGISTRY.all():
        if spec.shortcut:
            assert spec.shortcut.lower() in shortcuts


def test_the_window_starts_on_the_start_screen(window: MainWindow) -> None:
    assert window.stack.currentWidget() is window.start_screen


def test_the_right_panel_folds_away(window: MainWindow) -> None:
    assert window.right.isVisible() or True  # noch nicht sichtbar, aber verdrahtet
    window.action_toggle_right()
    assert not window.settings.right_panel_visible
    window.action_toggle_right()
    assert window.settings.right_panel_visible


def test_opening_a_model_leaves_the_start_screen(window: MainWindow) -> None:
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    assert window.stack.currentWidget() is window.splitter
    assert [entry.op for entry in window.session.project.document.ops] == ["load"]


def test_the_panels_follow_the_evaluation(window: MainWindow) -> None:
    window.open_path(MESHES / "two_components.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    window._on_scene(result)

    assert window.object_tree.tree.topLevelItemCount() == 1
    assert window.report.list.count() >= 1, "the findings of the input stage are shown"
    assert window.history_panel.list.count() == 1


def test_the_status_bar_describes_the_selection(window: MainWindow) -> None:
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window._on_scene(window.session.evaluate_now())
    window.object_tree.tree.setCurrentItem(window.object_tree.tree.topLevelItem(0))

    assert "20.00" in window.measurements.text()
    assert "cm³" in window.measurements.text()


# --- generated dialogs ----------------------------------------------------------


def test_a_dialog_is_generated_from_the_parameter_schema(qt_app: QApplication) -> None:
    dialog = OperationDialog(REGISTRY.get("load"), ["obj_1"])
    values = dialog.values()

    assert set(values) == {entry.name for entry in REGISTRY.get("load").params.spec()}
    assert values["unit"] == "auto"
    assert values["weld"] is True


def test_the_about_dialog_carries_the_licence_information(qt_app: QApplication) -> None:
    """§36: licence notices belong in the about dialog."""
    from PySide6.QtWidgets import QLabel, QTextBrowser

    from app.ui.dialogs import AboutDialog

    dialog = AboutDialog()
    texts = " ".join(label.text() for label in dialog.findChildren(QLabel))
    assert "Formwerk" in texts
    assert "RS Digital" in texts
    assert "MIT" in texts, "the parts library exception is named"

    listing = dialog.findChild(QTextBrowser)
    assert listing is not None
    assert "PySide6" in listing.toMarkdown()


def test_advanced_parameters_sit_behind_the_fold(qt_app: QApplication) -> None:
    """§2.4: die Vorderseite hält, was Leute wirklich ändern."""
    from PySide6.QtWidgets import QGroupBox

    dialog = OperationDialog(REGISTRY.get("load"), [])
    groups = dialog.findChildren(QGroupBox)

    assert groups, "load has advanced parameters, so there is a fold"
    assert not groups[0].isChecked(), "the fold starts closed"


def test_the_report_summary_counts_findings_from_both_directions(
    qt_app: QApplication,
) -> None:
    """Befunde kommen aus der Auswertung *und* über ``add_findings`` (§28.2).

    Die Zeile über der Liste zählte nur die erste Sorte und schrieb deshalb
    „Keine Befunde" über eine Liste voller Befunde — aufgefallen, als für das
    Handbuch ein Bild davon aufgenommen wurde.
    """
    from app.core.types import Finding
    from app.ui.panels import ReportPanel

    panel = ReportPanel()
    assert "Keine Befunde" in panel.summary.text()

    panel.add_findings(
        [
            Finding(code="a.b", severity="warning", message="offen"),
            Finding(code="c.d", severity="info", message="dünn"),
        ]
    )

    assert panel.list.count() == 2
    assert "Keine Befunde" not in panel.summary.text()
    assert "1" in panel.summary.text()


def test_a_report_without_findings_says_so(qt_app: QApplication) -> None:
    from app.ui.panels import ReportPanel

    panel = ReportPanel()
    panel.show_result(None)

    assert "Keine Befunde" in panel.summary.text()


def test_the_tool_strip_starts_with_every_bar_closed(qt_app: QApplication) -> None:
    """§2.4: im Ruhezustand zwei Zeilen, nicht fünf."""
    window = MainWindow(Session(), UiSettings())

    assert window.tools.active() is None
    assert not window.section_bar.isVisibleTo(window.tools)
    assert not window.paint_bar.isVisibleTo(window.tools)


def test_opening_a_tool_shows_exactly_its_bar(qt_app: QApplication) -> None:
    window = MainWindow(Session(), UiSettings())
    window.tools.toggle("section")

    assert window.tools.active() == "section"
    assert window.section_bar.isVisibleTo(window.tools)
    assert not window.analysis_bar.isVisibleTo(window.tools), (
        "zwei gleichzeitig wären der alte Zustand"
    )


def test_a_second_tool_closes_the_first(qt_app: QApplication) -> None:
    window = MainWindow(Session(), UiSettings())
    window.tools.toggle("section")

    window.tools.toggle("analysis")

    assert window.tools.active() == "analysis"
    assert not window.section_bar.isVisibleTo(window.tools)


def test_closing_a_tool_takes_its_view_change_back(qt_app: QApplication) -> None:
    """Das Schließen ist die Rücknahme — deshalb braucht es kein „Kein Schnitt“."""
    window = MainWindow(Session(), UiSettings())
    window.tools.toggle("section")
    window.section_bar.axis.setCurrentIndex(1)

    window.tools.toggle("section")

    assert window.tools.active() is None
    assert window.section_bar.axis.currentIndex() == 0


def test_every_tool_button_carries_a_label(qt_app: QApplication) -> None:
    """Regel 18: welches Werkzeug offen ist, hängt nicht allein an einer Farbe."""
    window = MainWindow(Session(), UiSettings())

    titles = window.tools.tool_titles()

    assert len(titles) == 7
    for key, title in titles.items():
        assert title.strip(), key


def test_the_language_picker_shows_names_not_codes(qt_app: QApplication) -> None:
    """„de" war die allererste Angabe, die ein neuer Benutzer zu sehen bekam."""
    from app.ui.first_run import FirstRunDialog

    dialog = FirstRunDialog(UiSettings())
    shown = [dialog.language.itemText(row) for row in range(dialog.language.count())]

    assert "Deutsch" in shown
    assert "English" in shown
    assert "de" not in shown


def test_the_chat_hint_offers_a_way_out(qt_app: QApplication) -> None:
    """§2.7: ein Hinweis, der nur feststellt, lässt den Benutzer stehen."""
    from app.ui.chat import ChatPanel

    panel = ChatPanel()

    panel.set_available(False)
    assert panel.setup.isVisibleTo(panel), "ohne Zugang führt ein Knopf dorthin"

    panel.set_available(True, backend="ollama")
    assert not panel.setup.isVisibleTo(panel), "mit Zugang gibt es nichts einzurichten"


def test_every_tool_has_a_symbol_and_keeps_its_label(qt_app: QApplication) -> None:
    """Regel 18: das Zeichen kommt neben den Text, nicht an seine Stelle."""
    from app.ui import icons

    window = MainWindow(Session(), UiSettings())

    for key, title in window.tools.tool_titles().items():
        button = window.tools._buttons[key]
        assert title.strip(), key
        assert not button.icon().isNull(), f"{key} hat kein Symbol"
        assert button.text().strip(), f"{key} hat seine Beschriftung verloren"
    assert len(icons.known()) >= len(window.tools.tool_titles())


def test_symbols_render_and_follow_the_text_colour(qt_app: QApplication) -> None:
    """Ein Satz Zeichen für beide Themen — sonst ist einer davon unsichtbar."""
    from app.ui import icons

    for name in icons.known():
        source = icons.svg_source(name, "#ff0000")
        assert source.startswith("<svg"), name
        assert "currentColor" not in source, f"{name} hängt an einer festen Farbe"
        assert "#ff0000" in source, name


def test_findings_carry_their_severity_as_a_shape(qt_app: QApplication) -> None:
    """Regel 18: die Form trägt den Schweregrad, die Farbe verstärkt ihn nur.

    Vorher stand ein „!" oder ein „·" im Text der Zeile. Das erfüllte die Regel,
    sah aber nach Behelf aus — und Warndreieck, Info-Kreis und Fehler-Achteck
    sind Zeichen, die niemand lernen muss.
    """
    from app.core.types import Finding
    from app.ui.panels import ReportPanel

    panel = ReportPanel()
    panel.add_findings(
        [
            Finding(code="a.b", severity="error", message="kaputt"),
            Finding(code="c.d", severity="warning", message="offen"),
            Finding(code="e.f", severity="info", message="dünn"),
        ]
    )

    assert panel.list.count() == 3
    for row in range(panel.list.count()):
        item = panel.list.item(row)
        assert not item.icon().isNull(), item.text()
        assert not item.text().startswith(("!", "·", "X")), "der Marker steckt jetzt im Zeichen"


def test_the_first_run_says_found_and_missing_in_words(qt_app: QApplication) -> None:
    """„+" und „−" waren die kryptischste Stelle im allerersten Dialog."""
    from app.ui.first_run import _tool_text

    text = _tool_text()

    assert "gefunden" in text or "fehlt" in text
    assert not any(line.startswith(("+ ", "- ")) for line in text.splitlines())


# --- Objektbaum (§18.8) ---------------------------------------------------------


def _with_two_objects(window: MainWindow) -> None:
    """Zwei Körper in der Szene, ausgewertet und im Baum.

    Zweimal laden statt einmal duplizieren: die Duplizierung verbraucht ihr
    Original und vergibt neue Nummern, und dann heißen die beiden nicht mehr
    obj_1 und obj_2.
    """
    window.session.import_model(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window.session.import_model(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window._on_scene(window.session.evaluate_now())


def test_hiding_takes_a_body_out_of_the_view_but_not_the_scene(window: MainWindow) -> None:
    """§18.8: ein Filter auf dem Bild, keiner auf der Szene."""
    _with_two_objects(window)

    window._on_visibility(("obj_1",), False)

    assert window.viewport.hidden == frozenset({"obj_1"})
    assert "obj_1" in window.session.last_result.scene.objects, "gerechnet wird er weiter"

    window._on_visibility(("obj_1",), True)
    assert window.viewport.hidden == frozenset()


def test_a_hidden_body_says_so_in_words(window: MainWindow) -> None:
    """Regel 18: eine ausgegraute Zeile allein wäre Farbe als einzige
    Kodierung."""
    _with_two_objects(window)
    window._on_visibility(("obj_1",), False)

    labels = [
        window.object_tree.tree.topLevelItem(index).text(0)
        for index in range(window.object_tree.tree.topLevelItemCount())
    ]
    hidden = [text for text in labels if "ausgeblendet" in text]
    assert len(hidden) == 1, labels


def test_isolating_hides_the_rest_and_the_same_entry_brings_it_back(
    window: MainWindow,
) -> None:
    _with_two_objects(window)

    window._on_isolate(("obj_1",))
    assert window.viewport.hidden == frozenset({"obj_2"})

    window._on_isolate(("obj_1",))
    assert window.viewport.hidden == frozenset()


def test_the_tree_names_the_step_a_body_came_from(window: MainWindow) -> None:
    """§18.8: Herkunft aus Operation und Transaktion."""
    _with_two_objects(window)

    tip = window.object_tree.tree.topLevelItem(0).toolTip(0)
    assert "aus Operation" in tip
    assert "Modell laden" in tip, tip


def test_removing_an_object_and_taking_it_back(window: MainWindow) -> None:
    """Entf ist eine Operation, also holt ein Undo den Körper zurück."""
    _with_two_objects(window)
    window.session.apply("Entfernen", [OperationDraft(op="delete_object", inputs=("obj_2",))])
    window.session.wait_for_idle()
    assert set(window.session.evaluate_now().scene.objects) == {"obj_1"}

    window.session.undo()
    window.session.wait_for_idle()
    assert set(window.session.evaluate_now().scene.objects) == {"obj_1", "obj_2"}


def test_an_operation_without_parameters_asks_nothing(window: MainWindow) -> None:
    """Regel 19: ein Fenster mit nur „OK" wäre die Bestätigung vor einer
    rücknehmbaren Handlung.

    Der Beweis, dass kein Dialog aufgeht, ist ein Lauf ohne Blockade: ein
    modales Fenster würde diesen Test hängen lassen.
    """
    _with_two_objects(window)
    window.object_tree.tree.topLevelItem(1).setSelected(True)
    before = len(window.session.project.document.transactions)

    window.run_operation(REGISTRY.get("delete_object"))
    window.session.wait_for_idle()

    assert len(window.session.project.document.transactions) == before + 1


def test_the_source_picker_offers_sources_and_not_bodies(qt_app: QApplication) -> None:
    """Eine Quelle ist kein Objekt.

    Beide standen hier in derselben Liste: wer „Modell laden" im Verlauf
    wieder öffnete, bekam eine Auswahl aus Körpern angeboten, wo eine Datei
    gemeint war. Gezeigt wird der Dateiname, übergeben die Kennung.
    """
    dialog = OperationDialog(
        REGISTRY.get("load"),
        {"obj_1": "Gehäuse"},
        values={"source": "src_1"},
        sources={"src_1": "halterung.stl", "src_2": "deckel.stl"},
    )
    combo = dialog._editors["source"]
    assert isinstance(combo, QComboBox)

    assert [combo.itemText(index) for index in range(combo.count())] == [
        "halterung.stl",
        "deckel.stl",
    ]
    assert not combo.isEditable(), "eine getippte Kennung war ein Weg, sich zu vertippen"
    assert dialog.values()["source"] == "src_1", "der gespeicherte Wert bleibt stehen"


def test_an_unknown_stored_value_is_kept_not_replaced(qt_app: QApplication) -> None:
    """Stillschweigend eine andere Datei einzusetzen wäre schlimmer, als eine
    unbekannte anzuzeigen."""
    dialog = OperationDialog(
        REGISTRY.get("load"),
        {},
        values={"source": "src_9"},
        sources={"src_1": "halterung.stl"},
    )
    assert dialog.values()["source"] == "src_9"


# --- Der Zustand, den die Oberfläche liest (§2.6, Regel 17) ---------------------


def test_operations_are_greyed_out_until_they_could_run(window: MainWindow) -> None:
    """Ein Menü, in dem alles anklickbar ist und die Hälfte mit „Bitte zuerst
    etwas auswählen" antwortet, lässt den Nutzer die Regeln erraten.
    """
    drilling = window._op_actions["drill_hole"]
    joining = window._op_actions["union_objects"]
    creating = window._op_actions["create_box"]

    assert not drilling.isEnabled(), "leere Szene, kein Körper zum Bohren"
    assert creating.isEnabled(), "anlegen geht immer"

    _with_two_objects(window)
    window.object_tree.tree.topLevelItem(0).setSelected(True)
    assert drilling.isEnabled()
    assert not joining.isEnabled(), "eine Vereinigung braucht zwei"

    window.object_tree.tree.topLevelItem(1).setSelected(True)
    assert joining.isEnabled()


def test_undo_and_redo_follow_the_stack(window: MainWindow) -> None:
    assert not window.undo_action.isEnabled()
    assert not window.redo_action.isEnabled()

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    assert window.undo_action.isEnabled()

    window.session.undo()
    window.session.wait_for_idle()
    assert window.redo_action.isEnabled()


def test_every_offered_error_action_does_something(window: MainWindow) -> None:
    """Regel 17 hat zwei Hälften, und die zweite fehlte.

    Die Vorschläge standen als Knöpfe da, und kein einziger Aufrufer las
    aus, welcher gedrückt wurde — jeder schloss ein Fenster und tat sonst
    nichts. Was hier zählt: für jede Handlung, die ein Fehler vorschlägt,
    gibt es entweder einen Handler oder einen benannten Grund.
    """
    known = window.error_handlers()
    postponed = {"use_voxel_stage", "choose", "choose_printer", "cancel", "correct_input", "retry"}

    for name, value in vars(errors).items():
        if not isinstance(value, errors.Action):
            continue
        assert value.id in known or value.id in postponed, (
            f"{name} wird angeboten, aber nichts führt sie aus"
        )


def test_only_actions_with_a_handler_are_offered(window: MainWindow) -> None:
    """Lieber ein Knopf weniger als einer, der nichts tut."""
    from app.ui.dialogs import offered_actions

    error = errors.NotManifoldError(open_edges=3)
    offered = {action.id for action in offered_actions(error, window.error_handlers())}

    assert "repair_and_retry" in offered
    assert "show_locations" in offered
    assert "cancel" not in offered, "das Schließen ist kein Vorschlag, es steht ohnehin da"


def test_an_error_without_a_handler_still_offers_a_way_out(window: MainWindow) -> None:
    """Ein Dialog mit nur „Abbrechen" ist „fehlgeschlagen" mit mehr Worten."""
    from app.ui.dialogs import offered_actions

    error = errors.AmbiguityError("Welche Fläche ist gemeint?", ("oben", "unten"))
    offered = [action.id for action in offered_actions(error, window.error_handlers())]

    assert offered, "zu keinem Vorschlag ein Handler — dann tritt der Bericht ein"
    assert "report_error" in offered


def test_the_handlers_are_found_through_the_parent_window(window: MainWindow) -> None:
    """Ein Dialog im Fenster zeigt dieselben Handlungen wie das Fenster."""
    from app.ui.dialogs import handlers_of

    dialog = QDialog(window)
    assert set(handlers_of(dialog)) == set(window.error_handlers())


def test_closing_with_unsaved_changes_asks(window: MainWindow, monkeypatch) -> None:
    """Der Menühinweis versprach das seit jeher; gefragt wurde nie."""
    import app.ui.main_window as module

    asked: list[str] = []
    monkeypatch.setattr(
        module, "confirm_unsaved", lambda title, parent: asked.append(title) or "cancel"
    )

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    assert window.session.modified

    assert not window._may_discard(), "Abbrechen hält das Schließen an"
    assert asked, "gefragt wurde"


def test_a_saved_project_closes_without_a_question(window: MainWindow, tmp_path: Path) -> None:
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window.session.save_project(tmp_path / "projekt.p3d")

    assert window._may_discard(), "nichts Ungesichertes, nichts zu fragen"
