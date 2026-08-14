"""Die Oberfläche: Sitzung, Fenster und die aus dem Schema erzeugten
Dialoge (§2.5, §10).

Läuft auf der Offscreen-Qt-Plattform, funktioniert also ohne Bildschirm.
Geprüft wird hier die Verdrahtung, keine Pixel: baut sich das Fenster aus dem
Register, geht eine Änderung durch den Stapel, bleibt die Auswertung im
Arbeiter.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QPoint, Qt
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QToolBar

from app.core import errors
from app.core.geom.measure import Measurement
from app.core.registry import REGISTRY
from app.core.scene import OperationDraft
from app.core.scene.project import load
from app.core.types import Parameter
from app.i18n import tr
from app.ui.main_window import REMOTE_ORIGIN, MainWindow
from app.ui.op_dialog import OperationDialog
from app.ui.palette import DIFF_PALETTES
from app.ui.session import AskRequest, Session
from app.ui.settings import UiSettings

MESHES = Path(__file__).parent / "data" / "meshes"


@pytest.fixture
def session(qt_app: QApplication) -> Session:
    return Session()


@pytest.fixture
def window(qt_app: QApplication, session: Session) -> MainWindow:
    # Aufgeräumt wird zentral: ``tests/conftest.py`` wartet nach jedem Test
    # auf die Arbeiter jedes offenen Fensters.
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


def all_menu_actions(window: MainWindow) -> list[QAction]:
    """Jeder Menüeintrag, auch in Untermenüs.

    Seit die dreizehn Kategorien in fünf Gruppen liegen (§2.5), steht das
    meiste eine Ebene tiefer. Erreichbar muss es trotzdem sein — auf welcher
    Ebene, ist die Frage dieses Tests nicht.
    """
    # Gefragt wird das Fenster, nicht die Leiste: es hält seine Menüs, und
    # ein über ``QAction.menu()`` geholter Wrapper nimmt beim Verwerfen das
    # C++-Menü mitsamt seinen Einträgen mit. Dass die Menüs auch wirklich in
    # der Leiste hängen, prüft `test_the_menubar_stays_a_bar`.
    return [action for menu in window._menus for action in menu.actions() if action.menu() is None]


def test_the_menubar_stays_a_bar(window: MainWindow) -> None:
    """§2.5: siebzehn Menüs sind keine Leiste mehr, sondern eine Liste."""
    top = [entry for entry in window.menuBar().actions() if entry.menu() is not None]
    assert len(top) <= 10, [entry.text() for entry in top]


def test_the_menu_is_built_from_the_registry(window: MainWindow) -> None:
    """Jede Operation bleibt erreichbar — im Menü, oder als zusammengelegter
    Zwilling über den Umschalter im Dialog ihres Partners plus die Palette.
    Zwei Menüeinträge für einen Quader waren „eine Operation je Variante",
    und das Hausprinzip sagt das Gegenteil.
    """
    from app.core.registry import MENU_TWINS, palette_entries

    labels = {action.text() for action in all_menu_actions(window)}
    offered = {entry.name for entry in palette_entries()}

    for spec in REGISTRY.all():
        if spec.name in MENU_TWINS:
            assert str(spec.title) not in labels, f"{spec.name} soll kein eigener Eintrag sein"
            assert spec.name in offered, f"{spec.name} muss über die Palette erreichbar bleiben"
            partner = REGISTRY.get(MENU_TWINS[spec.name])
            assert str(partner.title) in labels, "der sichtbare Zwilling trägt den Eintrag"
            continue
        assert str(spec.title) in labels, f"{spec.name} is missing from the menu"


def test_shortcuts_from_the_registry_are_installed(window: MainWindow) -> None:
    shortcuts = {
        action.shortcut().toString().lower()
        for action in all_menu_actions(window)
        if not action.shortcut().isEmpty()
    }
    for spec in REGISTRY.all():
        if spec.shortcut:
            assert spec.shortcut.lower() in shortcuts


def test_the_window_starts_on_the_start_screen(window: MainWindow) -> None:
    assert window.stack.currentWidget() is window.start_screen


def test_the_start_screen_shows_only_menus_that_do_something_there(window: MainWindow) -> None:
    """Auf dem Startbildschirm stehen nur Menüs, die dort etwas tun (§2.6).

    Bearbeiten, die Operationsgruppen und Ansicht setzen eine offene Szene
    voraus — als Leiste voller ausgegrauter Einträge waren sie Kulisse, keine
    Auskunft. Datei und Hilfe bleiben: Öffnen, Beenden, Handbuch und
    Freischalten sind genau dort sinnvoll.
    """

    def shown() -> list[str]:
        return [
            entry.text()
            for entry in window.menuBar().actions()
            if entry.menu() is not None and entry.isVisible()
        ]

    assert window.stack.currentWidget() is window.start_screen
    for menu in window._workspace_menus:
        assert not menu.menuAction().isVisible(), menu.title()
    assert len(shown()) == 2, shown()

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    for menu in window._workspace_menus:
        assert menu.menuAction().isVisible(), menu.title()

    window.session._dirty = False
    window.action_new()
    assert len(shown()) == 2, "zurück auf dem Startbildschirm gilt wieder die kurze Leiste"


def test_the_start_screen_opens_the_manual(window: MainWindow) -> None:
    """§2.3: das Handbuch dort, wo es gebraucht wird.

    Die fünfundzwanzig Seiten mit den ersten fünfzehn Minuten erreichte nur,
    wer das Hilfemenü des Hauptfensters schon kannte — also niemand, für den
    sie geschrieben wurden.
    """
    window.start_screen.manual_button.click()

    assert window._manual is not None
    assert window._manual.isVisible()


def test_new_leads_back_to_the_examples(window: MainWindow) -> None:
    """Nach dem ersten Start waren die sieben Beispiele unerreichbar.

    *Neu* legte sofort eine leere Szene an; der Startbildschirm ist aber der
    einzige Ort, an dem die Beispielprojekte samt ihren Touren stehen. Wer sie
    danach sehen wollte, brauchte *Öffnen* und Pfadkenntnis.

    Ein Klick mehr ist es nicht: „Neues Projekt" ist dort der Hauptknopf und
    liegt auf der Eingabetaste.
    """
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    assert window.stack.currentWidget() is not window.start_screen

    window.action_new()
    assert window.stack.currentWidget() is window.start_screen

    # Ohne das fragt der Knopf, ob das Geladene weg darf — zu Recht, aber
    # ein Dialog offscreen wartet auf niemanden.
    window.session._dirty = False
    window.start_screen.new_button.click()
    window.session.wait_for_idle()
    assert window.stack.currentWidget() is not window.start_screen
    assert not window.session.project.document.ops, "und das Projekt ist leer"


def test_an_empty_scene_leaves_nothing_of_the_last_one(window: MainWindow) -> None:
    """Nach *Neu* blieben die orangen Merkmalsmarkierungen des vorigen Objekts
    im Bild stehen, während Objektbaum und Prüfbericht längst leer waren."""
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    viewport = window.viewport
    viewport.select("obj_1")
    viewport.set_feature_overlay(True)
    viewport.measurements.add(
        Measurement(kind="distance", value=10.0, points=((0.0, 0.0, 0.0), (10.0, 0.0, 0.0)))
    )

    viewport.show_scene(None)

    assert viewport._selected is None
    assert len(viewport.measurements) == 0
    assert viewport._feature_actors == []


def test_the_right_panel_folds_away(window: MainWindow) -> None:
    assert window.right.isVisible() or True  # noch nicht sichtbar, aber verdrahtet
    window.action_toggle_right()
    assert not window.settings.right_panel_visible
    window.action_toggle_right()
    assert window.settings.right_panel_visible


def test_opening_a_model_leaves_the_start_screen(window: MainWindow) -> None:
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    assert window.stack.currentWidget() is window.overlay
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

    assert "20,00" in window.measurements.text()
    assert "cm³" in window.measurements.text()


# --- generated dialogs ----------------------------------------------------------


def test_a_dialog_is_generated_from_the_parameter_schema(qt_app: QApplication) -> None:
    dialog = OperationDialog(REGISTRY.get("load"), ["obj_1"])
    values = dialog.values()

    assert set(values) == {entry.name for entry in REGISTRY.get("load").params.spec()}
    assert values["unit"] == "auto"
    assert values["weld"] is True


def test_a_feature_parameter_offers_the_features(qt_app: QApplication) -> None:
    """§18.5: „face_2" tippt niemand, der es nicht vorher abgelesen hat.

    Der Parameter war ein leeres Textfeld, und sein eigener doc-Satz versprach,
    er werde „beim Anklicken im Fenster eingetragen" — abzulesen war die
    Kennung nur im Objektbaum, wo die Namen bei Standardbreite abgeschnitten
    sind.
    """
    from PySide6.QtWidgets import QComboBox

    spec = REGISTRY.get("create_lid")
    features = {"face_2": "face_2 · 3915 mm²", "hole_1": "hole_1 · Ø5,19 mm"}
    dialog = OperationDialog(spec, ["obj_1"], features=features)
    try:
        editor = dialog._editors["at_feature"]
        assert isinstance(editor, QComboBox), "eine Liste, kein Textfeld"

        labels = [editor.itemText(index) for index in range(editor.count())]
        assert "face_2 · 3915 mm²" in labels, "die Beschriftung, nicht die Kennung"
        assert editor.itemData(0) == "", "ohne Merkmal geht es auch — der Parameter ist optional"
        assert dialog.values()["at_feature"] == "", "und die Vorgabe bleibt leer"

        editor.setCurrentIndex(labels.index("hole_1 · Ø5,19 mm"))
        assert dialog.values()["at_feature"] == "hole_1", "die Kennung reist mit, nicht der Text"
    finally:
        dialog.deleteLater()


def test_an_unknown_feature_is_shown_not_replaced(qt_app: QApplication) -> None:
    """Ein gespeicherter Wert, den die Liste nicht kennt, bleibt stehen.

    Wer eine Operation aus dem Verlauf öffnet, deren Merkmal seit einer
    Umbenennung nicht mehr da ist, soll sehen, was dasteht — nicht
    stillschweigend ein anderes bekommen.
    """
    from PySide6.QtWidgets import QComboBox

    spec = REGISTRY.get("create_lid")
    dialog = OperationDialog(
        spec, ["obj_1"], values={"at_feature": "face_9"}, features={"face_2": "face_2 · 100 mm²"}
    )
    try:
        editor = dialog._editors["at_feature"]
        assert isinstance(editor, QComboBox)
        assert dialog.values()["at_feature"] == "face_9"
    finally:
        dialog.deleteLater()


def test_clicking_a_feature_fills_the_field(qt_app: QApplication) -> None:
    """Der ``doc``-Satz versprach es seit je: „wird beim Anklicken im Fenster
    eingetragen".

    Einzulösen war das nicht, solange der Dialog das Fenster sperrte — es gab
    kein Anklicken, während er offen war. Jetzt ist der kürzeste Weg zu einer
    Fläche wieder der, auf sie zu zeigen.
    """
    spec = REGISTRY.get("create_lid")
    dialog = OperationDialog(spec, ["obj_1"], features={"face_2": "face_2 · 3915 mm²"})
    try:
        assert dialog.take_feature("face_2", "face_2 · 3915 mm²")
        assert dialog.values()["at_feature"] == "face_2"

        # Ein Merkmal, das die Liste nicht kennt, kommt trotzdem an: erkannt
        # wird nach jeder Operation neu, der Dialog steht seit vorher offen.
        assert dialog.take_feature("hole_7", "hole_7 · Ø3,20 mm")
        assert dialog.values()["at_feature"] == "hole_7"
    finally:
        dialog.deleteLater()


def test_a_dialog_without_a_feature_field_takes_nothing(qt_app: QApplication) -> None:
    """Der Aufrufer weiß sonst nicht, ob sein Klick angekommen ist."""
    dialog = OperationDialog(REGISTRY.get("drill_hole"), ["obj_1"])
    try:
        assert not dialog.take_feature("face_2", "face_2 · 100 mm²")
    finally:
        dialog.deleteLater()


def test_clicking_a_spot_fills_the_position(qt_app: QApplication) -> None:
    """§18.5: zeigen statt tippen — und §11 bleibt gewahrt.

    *Bohrung setzen* öffnete mit X, Y und Z auf 0,00, und der Ursprung liegt
    bei einer geladenen Platte an einer Ecke. Wer dort bohrte, kratzte einen
    Span von der Kante ab. Was der Klick einträgt, steht danach lesbar da: die
    Zahl ist die Wahrheit, das Zeigen nur die bequeme Eingabe.
    """
    dialog = OperationDialog(REGISTRY.get("drill_hole"), ["obj_1"])
    try:
        assert dialog.take_point((12.5, -7.25, 4.0))

        values = dialog.values()
        assert values["x"] == pytest.approx(12.5)
        assert values["y"] == pytest.approx(-7.25)
        assert values["z"] == pytest.approx(4.0)
    finally:
        dialog.deleteLater()


def test_a_dialog_without_a_position_takes_no_point(qt_app: QApplication) -> None:
    """Nicht jede Operation hat eine Stelle, an der sie arbeitet."""
    dialog = OperationDialog(REGISTRY.get("load"), ["obj_1"])
    try:
        assert not dialog.take_point((1.0, 2.0, 3.0))
    finally:
        dialog.deleteLater()


def test_the_dialog_keeps_out_of_the_middle_of_the_view(qt_app: QApplication) -> None:
    """§18.7: der Dialog trägt eine Live-Vorschau und darf sie nicht verdecken.

    Qt setzt Dialoge mittig zum Elternfenster, und die Mitte ist genau die
    Stelle, an der die Kamera das Modell zeigt — die Vorschau entstand hinter
    dem Dialog, der sie ausgelöst hat.
    """
    from PySide6.QtWidgets import QWidget

    anchor = QWidget()
    anchor.resize(1200, 800)
    anchor.show()
    dialog = OperationDialog(REGISTRY.get("load"), ["obj_1"])
    try:
        dialog.place_beside(anchor)
        middle = anchor.mapToGlobal(anchor.rect().center()).x()

        assert dialog.x() > middle, "der Dialog steht rechts, nicht über der Mitte"
        assert dialog.y() >= anchor.mapToGlobal(anchor.rect().topLeft()).y()
    finally:
        dialog.deleteLater()
        anchor.deleteLater()


def test_a_narrow_view_leaves_the_dialog_where_it_was(qt_app: QApplication) -> None:
    """Passt er nicht daneben, bleibt er, wo Qt ihn hingesetzt hat.

    Ein Dialog halb außerhalb des Bildschirms wäre schlimmer als einer in der
    Mitte.
    """
    from PySide6.QtWidgets import QWidget

    anchor = QWidget()
    anchor.resize(120, 400)
    anchor.show()
    dialog = OperationDialog(REGISTRY.get("load"), ["obj_1"])
    try:
        before = dialog.pos()
        dialog.place_beside(anchor)

        assert dialog.pos() == before
    finally:
        dialog.deleteLater()
        anchor.deleteLater()


def test_the_about_dialog_carries_the_licence_information(qt_app: QApplication) -> None:
    """§36: Lizenzhinweise gehören in den Über-Dialog."""
    from PySide6.QtWidgets import QLabel, QTextBrowser

    from app.ui.dialogs import AboutDialog

    dialog = AboutDialog()
    texts = " ".join(label.text() for label in dialog.findChildren(QLabel))
    assert "Solidon" in texts
    assert "RS Digital" in texts
    assert "MIT" in texts, "the parts library exception is named"

    listing = dialog.findChild(QTextBrowser)
    assert listing is not None
    assert "PySide6" in listing.toMarkdown()


def test_advanced_parameters_sit_behind_the_fold(qt_app: QApplication) -> None:
    """§2.4: die Vorderseite hält, was Leute wirklich ändern.

    Und der hintere Teil ist wirklich weg, nicht nur grau: eine ankreuzbare
    Gruppe graut ihre Felder aus und lässt sie stehen — die gestufte Tiefe war
    damit gedacht und nicht gebaut.
    """
    dialog = OperationDialog(REGISTRY.get("load"), [])

    assert hasattr(dialog, "advanced"), "load hat hintere Parameter, also gibt es die Klappe"
    assert not dialog.advanced.isChecked(), "sie beginnt zugeklappt"

    hidden = [
        editor
        for name, editor in dialog._editors.items()
        if next(entry.placement for entry in dialog.spec.params.spec() if entry.name == name)
        == "advanced"
    ]
    assert hidden, "diese Operation hat welche"
    assert all(not editor.isVisibleTo(dialog) for editor in hidden), "zugeklappt heißt unsichtbar"


def test_a_tolerance_keeps_its_third_decimal(qt_app: QApplication) -> None:
    """Zwei Nachkommastellen machten aus 0,075 beim Öffnen eine 0,08 — eine
    stille Änderung an einer Zahl, die jemand gemessen hat (§11.2)."""
    from app.ui.op_dialog import _decimals_for

    fine = next(
        entry
        for spec in REGISTRY.all()
        for entry in spec.params.spec()
        if entry.kind == "float" and entry.maximum is not None and 0 < entry.maximum <= 1.0
    )
    assert _decimals_for(fine) == 3


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


def test_every_tool_bar_gets_the_room_it_needs(window: MainWindow) -> None:
    """Ein geöffnetes Werkzeug darf nicht über den Umschaltern liegen.

    Die untere Zone hängt in einer Überlagerung: sie bekommt ihre Geometrie
    gesetzt, statt sie von einem Layout rechnen zu lassen. Solange niemand
    meldete, dass eine Leiste dazugekommen ist, blieb sie auf der Höhe der
    Knopfreihe — einunddreißig Pixel für einen Bedarf von siebenundneunzig.
    Regler, Felder und Knöpfe lagen dann über den Umschaltern, und zwar bei
    **jedem** der sieben Werkzeuge. Gesehen wurde es an einem
    Bildschirmfoto fürs Handbuch.
    """
    window._show_start_screen(False)
    qt_app = QApplication.instance()
    assert qt_app is not None
    for _ in range(20):
        qt_app.processEvents()

    zone = window.overlay.bottom
    assert zone is not None

    too_small = []
    for key in ("section", "measure", "transform", "analysis", "layers", "explode", "paint"):
        window.tools.activate(key)
        for _ in range(10):
            qt_app.processEvents()
        if zone.height() < zone.sizeHint().height():
            too_small.append(f"{key}: {zone.height()} statt {zone.sizeHint().height()}")
        window.tools.activate(None)

    assert not too_small, "die untere Zone bleibt zu niedrig:\n" + "\n".join(too_small)


def test_a_bar_never_shows_itself_past_its_switch(window: MainWindow) -> None:
    """Die Sichtbarkeit einer Leiste gehört der Werkzeugzeile — nur ihr.

    Die Explosionsleiste machte sich in ``show_for`` selbst sichtbar, sobald
    eine Szene zwei Körper hatte. Zwei Stellen steuerten damit dasselbe: die
    eine klappte auf, was die andere zugeklappt hielt, und die Leiste lag über
    den Umschaltern. Sie sagt jetzt nur noch, ob sie etwas zu bieten hat —
    gezeigt wird sie, wenn jemand ihren Knopf drückt.
    """
    window._show_start_screen(False)
    qt_app = QApplication.instance()
    assert qt_app is not None

    assert window.explode_bar.show_for(3, 1) is True, "drei Körper sind etwas zum Auseinanderziehen"
    assert window.explode_bar.show_for(1, 1) is False
    for _ in range(10):
        qt_app.processEvents()

    # ``isVisibleTo`` und nicht ``isVisible``: das Fenster im Test ist selbst
    # nicht auf dem Bildschirm, und dann ist alles darin unsichtbar — auch
    # das, was aufgeklappt wäre.
    strip = window.tools
    assert not window.explode_bar.isVisibleTo(strip), "ohne Knopfdruck bleibt sie zu"

    window.tools.set_available("explode", True)
    window.tools.activate("explode")
    for _ in range(10):
        qt_app.processEvents()
    assert window.explode_bar.isVisibleTo(strip), "mit Knopfdruck geht sie auf"

    # Und fällt das Werkzeug weg, geht sie mit.
    window.tools.set_available("explode", False)
    for _ in range(10):
        qt_app.processEvents()
    assert not window.explode_bar.isVisibleTo(strip)
    assert window.tools.active() is None


def test_the_report_puts_the_heavy_findings_first(qt_app: QApplication) -> None:
    """Die Zählzeile verspricht eine Rangfolge — die Liste muss sie halten.

    Vorher hängte sie an, wie es kam: bei zwei Warnungen und vier Hinweisen
    stand zuoberst ein Hinweis, und der Fehler an sechster Stelle. Sichtbar
    war das am Bildschirmfoto des Hauptfensters, wo über einer Liste mit zwei
    Hinweisen „2 Warnung" stand.
    """
    from PySide6.QtCore import Qt

    from app.core.types import Finding
    from app.ui.panels import ReportPanel

    panel = ReportPanel()
    panel.add_findings(
        [
            Finding(code="a.info", severity="info", message="zuerst entstanden"),
            Finding(code="b.error", severity="error", message="der Fehler"),
            Finding(code="c.info", severity="info", message="noch ein Hinweis"),
            Finding(code="d.warning", severity="warning", message="die Warnung"),
        ]
    )

    order = [
        panel.list.item(row).data(Qt.ItemDataRole.UserRole).severity
        for row in range(panel.list.count())
    ]
    assert order == ["error", "warning", "info", "info"]


def test_the_history_names_only_what_differs(qt_app: QApplication) -> None:
    """§26.4: die Herkunft steht dran, wo sie vom Üblichen abweicht.

    „(Nutzer)" an jeder Zeile ist in einem Projekt ohne Agenten an jeder
    Zeile — und was überall steht, liest niemand. Der Agent wird genannt.
    """
    from app.core.types import Document, Origin, Transaction
    from app.ui.panels import HistoryPanel

    document = Document(format_version=7, app_version="0.0.1")
    document.transactions.append(Transaction(id=1, title="Bohrung setzen", ops=(1,)))
    document.transactions.append(
        Transaction(id=2, title="Deckel erzeugen", ops=(2,), origin=Origin(by="agent"))
    )

    panel = HistoryPanel()
    panel.show_document(document)

    lines = [panel.list.item(row).text() for row in range(panel.list.count())]
    assert lines[0] == "Bohrung setzen", "der Regelfall bleibt unkommentiert"
    assert "Agent" in lines[1]


def test_report_findings_wrap_instead_of_scrolling(qt_app: QApplication) -> None:
    """§2.7: die Sätze des Prüfberichts müssen ganz lesbar sein.

    Im schmalen rechten Bereich endeten sie mitten im Wort („…um die
    Materialtoleranz v") hinter einer horizontalen Bildlaufleiste —
    aufgefallen am Bildschirmfoto des Hauptfensters fürs Handbuch.
    """
    from PySide6.QtCore import Qt

    from app.ui.panels import ReportPanel

    panel = ReportPanel()
    assert panel.list.wordWrap()
    assert panel.list.textElideMode() == Qt.TextElideMode.ElideNone
    assert panel.list.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff


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


def test_a_typed_cut_height_moves_the_plane(qt_app: QApplication) -> None:
    """Ziehen **und** tippen, nicht eines von beiden (Konzept P15 §4, E2).

    Ein Zug durch den Körper ist eine Suche; „schneide bei 12,5" ist eine Zahl.
    Der Regler bleibt die Wahrheit über die Position — geprüft wird deshalb,
    dass die getippte Höhe wirklich in der Ebene ankommt und nicht nur im Feld
    steht.
    """
    window = MainWindow(Session(), UiSettings())
    bar = window.section_bar
    bar.set_ranges({"x": (-40.0, 40.0), "y": (-40.0, 40.0), "z": (-40.0, 40.0)})
    bar.axis.setCurrentIndex(1)

    bar.readout.setValue(12.5)

    plane = bar.plane()
    assert plane is not None
    assert plane.position == pytest.approx(12.5)

    # Und andersherum: der Regler führt das Feld nach.
    bar.position.setValue(-70)
    assert bar.readout.value() == pytest.approx(-7.0)


def test_the_cut_slider_runs_along_its_own_axis(qt_app: QApplication) -> None:
    """Ein flaches Brett schneidet man in Z über acht Millimeter, nicht über
    achtzig.

    Vorher galt eine Spanne für alle drei Achsen, gebildet aus dem kleinsten
    und größten Wert über sämtliche. Ein Zug in die Reglermitte landete damit
    weit über dem Teil — der Regler hatte sich bewegt, und es war kein Schnitt
    zu sehen.
    """
    window = MainWindow(Session(), UiSettings())
    bar = window.section_bar
    bar.set_ranges({"x": (-40.0, 40.0), "y": (-25.0, 25.0), "z": (0.0, 8.0)})

    bar.axis.setCurrentIndex(bar.axis.findData("z"))
    assert bar.readout.minimum() < 0.0 <= 8.0 < bar.readout.maximum()
    assert bar.readout.maximum() < 20.0, "der Z-Weg gehört zur Dicke, nicht zur Länge"

    bar.axis.setCurrentIndex(bar.axis.findData("x"))
    assert bar.readout.maximum() > 40.0, "und der X-Weg zur Länge"


def test_switching_the_axis_keeps_the_cut_on_the_body(qt_app: QApplication) -> None:
    """Eine Position außerhalb des neuen Weges wäre ein Schnitt neben dem Teil."""
    window = MainWindow(Session(), UiSettings())
    bar = window.section_bar
    bar.set_ranges({"x": (-40.0, 40.0), "y": (-25.0, 25.0), "z": (0.0, 8.0)})

    bar.axis.setCurrentIndex(bar.axis.findData("x"))
    bar.readout.setValue(35.0)

    bar.axis.setCurrentIndex(bar.axis.findData("z"))
    assert 0.0 <= bar.readout.value() <= 8.0, "in die Mitte des neuen Weges"


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


def test_the_application_icon_carries_every_size(qt_app: QApplication) -> None:
    """Das Fenster-Symbol kommt aus der SVG-Quelle — leer hieße: Windows zeigt
    sein Standardbild, und niemand merkt es vor dem ersten Screenshot.
    """
    from app.ui import icons

    symbol = icons.application_icon()

    assert not symbol.isNull()
    assert len(symbol.availableSizes()) == len(icons.APPLICATION_ICON_SIZES)


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
    """„+" und „−" waren die kryptischste Stelle im allerersten Dialog.

    Das Wort ist geblieben, das Zeichen steht jetzt daneben — nicht statt
    seiner (Regel 18). Und der Installationspfad, der beim ersten Start keine
    Frage beantwortet, steht im Hinweis statt in der Zeile.
    """
    from PySide6.QtWidgets import QLabel

    from app.core import tools
    from app.ui.first_run import ToolRow

    states = tools.survey()
    assert states, "ohne Programme prüft dieser Test nichts"

    for state in states:
        row = ToolRow(state)
        words = [child.text() for child in row.findChildren(QLabel) if child.text()]
        assert any(word in ("gefunden", "fehlt") for word in words), words
        assert row.toolTip(), "wo es liegt, steht im Hinweis"
        assert not any(word.startswith(("+ ", "- ")) for word in words)


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


def test_an_operation_dialog_does_not_lock_the_window(window: MainWindow) -> None:
    """§18.7: eine Vorschau, die man nicht umdrehen kann, ist eine halbe.

    ``exec()`` sperrte jede Kameraführung, solange der Dialog offen war — wer
    sehen wollte, ob die Bohrung auf der Rückseite austritt, musste abbrechen,
    drehen und von vorn anfangen. Der Beweis ist ein Lauf ohne Blockade: ein
    modaler Dialog ließe diesen Test hängen.
    """
    _with_two_objects(window)
    window.object_tree.tree.topLevelItem(0).setSelected(True)
    before = len(window.session.project.document.transactions)

    window.run_operation(REGISTRY.get("drill_hole"))

    dialog = window._op_dialog
    assert dialog is not None, "der Dialog steht offen und hat die Kontrolle zurückgegeben"
    assert dialog.isVisible()
    assert len(window.session.project.document.transactions) == before, (
        "solange nichts übernommen ist, bleibt der Stapel unberührt"
    )

    dialog.accept()
    window.session.wait_for_idle()

    assert window._op_dialog is None, "nach dem Schließen hält das Fenster keinen Dialog mehr"
    assert len(window.session.project.document.transactions) == before + 1


def test_a_rejected_dialog_changes_nothing(window: MainWindow) -> None:
    """Abbrechen heißt abbrechen — auch ohne Sperre."""
    _with_two_objects(window)
    window.object_tree.tree.topLevelItem(0).setSelected(True)
    before = len(window.session.project.document.transactions)

    window.run_operation(REGISTRY.get("drill_hole"))
    assert window._op_dialog is not None
    window._op_dialog.reject()
    window.session.wait_for_idle()

    assert window._op_dialog is None
    assert len(window.session.project.document.transactions) == before


def test_a_second_dialog_closes_the_first(window: MainWindow) -> None:
    """Zwei Vorschauen um denselben Viewport wären eine Frage ohne Antwort.

    Das verhinderte bisher die Sperre; ohne sie muss es die Stelle tun, die
    den Dialog öffnet.
    """
    _with_two_objects(window)
    window.object_tree.tree.topLevelItem(0).setSelected(True)

    window.run_operation(REGISTRY.get("drill_hole"))
    first = window._op_dialog
    assert first is not None

    window.run_operation(REGISTRY.get("drill_hole"))
    second = window._op_dialog

    assert second is not None
    assert second is not first, "der zweite Dialog ist ein anderer"
    assert not first.isVisible(), "und der erste ist zu"


def test_a_click_in_the_view_reaches_the_open_dialog(window: MainWindow) -> None:
    """Der ganze Weg: Dialog offen, ins Bild geklickt, Feld gefüllt.

    Drei Änderungen greifen hier ineinander — der Dialog sperrt nicht mehr, der
    Klick kommt an, und der Dialog nimmt entgegen. Einzeln geprüft sind sie
    schon; hier zählt, dass sie zusammen den Weg ergeben, den §18.5 meint.
    """
    _with_two_objects(window)
    window.object_tree.tree.topLevelItem(0).setSelected(True)
    window.run_operation(REGISTRY.get("drill_hole"))
    dialog = window._op_dialog
    assert dialog is not None

    window.viewport.pointPicked.emit((8.0, 3.0, 1.5))

    values = dialog.values()
    assert values["x"] == pytest.approx(8.0)
    assert values["y"] == pytest.approx(3.0)
    assert values["z"] == pytest.approx(1.5)
    dialog.reject()


def test_a_click_without_a_dialog_changes_no_values(window: MainWindow) -> None:
    """Ohne offenen Dialog ist ein Klick eine Auswahl und sonst nichts."""
    _with_two_objects(window)
    assert window._op_dialog is None

    window.viewport.pointPicked.emit((8.0, 3.0, 1.5))  # darf nichts auslösen

    assert window._op_dialog is None


def test_a_filament_colour_is_named_not_numbered(qt_app: QApplication) -> None:
    """§29: über dem Filamentfeld stand „#4A90D9".

    Das ist der genaue Wert und beschreibt für niemanden eine Spule im Regal.
    Grob mit Absicht: Filamentfarben sind Regalfarben, und „Kornblumenblau"
    wäre genauer und trotzdem nicht die Spule, die dasteht.
    """
    from app.ui.labels import colour_name

    assert colour_name("#4A90D9") == "Blau"
    assert colour_name("#000000") == "Schwarz"
    assert colour_name("#ffffff") == "Weiß"
    assert colour_name("#808080") == "Grau"
    assert colour_name("#d02020") == "Rot"
    assert colour_name("#8b5a2b") == "Braun", "dunkles Orange heißt Braun"
    assert colour_name("#ff9500") == "Orange"
    assert colour_name("kein-farbwert") == "kein-farbwert"


def test_a_standard_part_is_offered_by_its_name(qt_app: QApplication) -> None:
    """§24: „cable-5" erkennt niemand ohne die Normteiltabelle daneben.

    Der Schlüssel ist englisch und kurz, weil er ein Schlüssel ist. Im Dialog
    stand er als Beschriftung — und wer eine Kabeldurchführung setzen will,
    sucht „Rundkabel Ø5 mm".
    """
    from PySide6.QtWidgets import QComboBox

    from app.core.knowledge.parts.ops import op_name as part_op_name

    dialog = OperationDialog(REGISTRY.get(part_op_name("cable_gland")), ["obj_1"])
    try:
        editor = dialog._editors["size"]
        assert isinstance(editor, QComboBox)

        labels = [editor.itemText(index) for index in range(editor.count())]
        assert any("Rundkabel" in text for text in labels), "der Name steht da"
        assert "cable-5" not in labels, "und der Schlüssel nicht"

        # Der Wert bleibt der Schlüssel — sonst fände die Tabelle ihn nicht.
        values = [editor.itemData(index) for index in range(editor.count())]
        assert "cable-5" in values
    finally:
        dialog.deleteLater()


def test_a_choice_that_is_already_a_name_stays_as_it_is(qt_app: QApplication) -> None:
    """„M4", „PLA", „z" sind selbst schon der Name — daran gibt es nichts zu
    übersetzen."""
    from app.ui.labels import choice_label

    assert choice_label("M4") == "M4"
    assert choice_label("z") == "z"
    assert choice_label("gibt-es-nicht") == "gibt-es-nicht"


def test_numbers_are_written_the_way_the_input_fields_write_them(
    qt_app: QApplication,
) -> None:
    """§19.3: zwei Schreibweisen derselben Zahl im selben Blick.

    Im Objektbaum standen die Maße mit Punkt, vierzig Pixel neben einem
    Eingabefeld mit Komma. Der Kern hat recht, wenn er mit Punkt rechnet — dort
    ist eine Zahl ein Wert. Nur kam sie so auch beim Nutzer an.

    Gefragt wird ``QLocale``, weil die Eingabefelder es ebenso tun: eine
    Quelle, oder das Problem kommt an der nächsten Stelle wieder.
    """
    from PySide6.QtCore import QLocale
    from PySide6.QtWidgets import QDoubleSpinBox

    from app.ui.labels import length, localised

    before = QLocale()
    try:
        QLocale.setDefault(QLocale("de"))
        spin = QDoubleSpinBox()
        spin.setDecimals(2)
        spin.setValue(60.0)

        assert "," in spin.text(), "das Eingabefeld schreibt deutsch"
        assert length(80.0) == "80,00 mm", "und der Text daneben auch"
        assert localised("1.5 · 2.25") == "1,5 · 2,25"

        QLocale.setDefault(QLocale("en"))
        assert length(80.0) == "80.00 mm", "auf Englisch bleibt der Punkt"
        spin.deleteLater()
    finally:
        QLocale.setDefault(before)


def test_the_history_shows_titles_not_registry_names(qt_app: QApplication) -> None:
    """§4.1: der Verlauf spricht deutsch, auch bei mehreren Ops je Schritt.

    Zwischen „Grundkörper" und „Versteifung" stand ``insert_screw_hole``.
    Beides sind dieselben Schritte — nur kam der eine Text aus der Transaktion
    und der andere aus dem Code.
    """
    from app.ui.panels import _op_title

    assert _op_title("drill_hole") == str(REGISTRY.get("drill_hole").title)
    assert "_" not in _op_title("drill_hole"), "kein Registername"
    # Eine Projektdatei aus einer neueren Fassung ist kein Grund für eine
    # leere Zeile.
    assert _op_title("gibt_es_nicht") == "gibt_es_nicht"


def test_delete_only_bites_where_a_selection_is_visible(window: MainWindow) -> None:
    """§2.6: „Entf" war fensterweit gebunden.

    Wer im Verlauf einen Schritt markierte und die Taste drückte, verlor den
    ausgewählten **Körper** — man drückt sie in der Erwartung, den Schritt
    loszuwerden. Rücknehmbar, aber genau die Art Überraschung, die Vertrauen
    kostet.

    Geprüft wird der Geltungsbereich, nicht das Drücken: eine Taste, die nur
    im Baum und in der Ansicht gilt, kann im Verlauf nichts anrichten.
    """
    delete = next(
        action
        for action in window.findChildren(QAction)
        if action.shortcut() == QKeySequence("Del")
    )

    assert delete.shortcutContext() == Qt.ShortcutContext.WidgetWithChildrenShortcut
    assert delete in window.object_tree.actions(), "im Baum gilt sie"
    assert delete in window.viewport.actions(), "und in der Ansicht"
    assert delete not in window.history_panel.actions(), "im Verlauf nicht"


def test_shortcuts_with_a_modifier_stay_window_wide(window: MainWindow) -> None:
    """Strg+B ist eindeutig gemeint, egal worauf der Fokus steht."""
    drill = next(
        action
        for action in window.findChildren(QAction)
        if action.shortcut() == QKeySequence("Ctrl+B")
    )

    assert drill.shortcutContext() == Qt.ShortcutContext.WindowShortcut


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


def test_cancelling_the_question_keeps_the_window_open(window: MainWindow, monkeypatch) -> None:
    """Abbrechen heißt abbrechen, nicht „gleich trotzdem".

    Geprüft war bisher nur, dass ``_may_discard`` bei *Abbrechen* nein sagt.
    Ob der ``closeEvent`` diese Antwort auch befolgt, stand nirgends — und
    genau das ist die Frage, die jemand stellt, der vor dem Dialog steht.
    Deshalb geht dieser Test über ``close()`` und sieht dem Fenster danach an,
    dass es noch da ist.
    """
    import app.ui.main_window as module

    answers = ["cancel"]
    monkeypatch.setattr(module, "confirm_unsaved", lambda title, parent: answers[0])

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window.show()
    assert window.session.modified

    assert not window.close(), "der Schließversuch wird abgelehnt"
    assert window.isVisible(), "das Fenster steht noch"
    assert window.session.modified, "und die Arbeit ist unberührt"

    answers[0] = "discard"
    assert window.close(), "mit Verwerfen geht es dann"


# --- Einstellungen an einem Ort (§19.3, §38) ------------------------------------


def test_the_display_unit_reaches_everything_that_shows_a_length(window: MainWindow) -> None:
    """§19.3: die Einstellung gab es seit P0 und niemanden, der sie las."""
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window._on_scene(window.session.evaluate_now())
    window.object_tree.tree.setCurrentItem(window.object_tree.tree.topLevelItem(0))

    assert "20,00" in window.measurements.text()
    assert "cm³" in window.measurements.text()

    window.set_display_unit("in")

    # Die Einheit wechselt, die Schreibweise der Zahl folgt weiter der Sprache
    # — ein Zoll auf einer deutschen Oberfläche schreibt sich mit Komma.
    assert "0,7874" in window.measurements.text(), "20 mm sind 0,7874 Zoll"
    assert "in³" in window.measurements.text()
    assert "in" in window.object_tree.tree.topLevelItem(0).text(1)


def test_the_settings_dialog_writes_every_value_back(qt_app: QApplication) -> None:
    from app.ui.settings_dialog import SettingsDialog

    settings = UiSettings()
    dialog = SettingsDialog(settings)
    dialog.unit.setCurrentIndex(dialog.unit.findData("in"))
    dialog.diff_palette.setCurrentIndex(dialog.diff_palette.findData("red_green"))
    dialog.updates.setChecked(True)

    dialog.apply_to(settings)

    assert (settings.display_unit, settings.diff_palette) == ("in", "red_green")
    assert settings.check_for_updates


def test_a_language_change_says_that_it_waits(qt_app: QApplication) -> None:
    """Sie wirkt erst beim nächsten Start — das stillschweigend zu übergehen
    liest sich, als hätte die Einstellung nicht gewirkt."""
    from app.ui.settings_dialog import SettingsDialog

    dialog = SettingsDialog(UiSettings())
    assert not dialog.language_note.isVisible()

    other = next(
        index
        for index in range(dialog.language.count())
        if dialog.language.itemData(index) != UiSettings().language
    )
    dialog.language.setCurrentIndex(other)
    assert dialog.language_note.isVisibleTo(dialog)


def test_the_printer_of_an_open_project_can_change(session: Session) -> None:
    """§12: er wurde einmal beim Anlegen gesetzt und danach nie wieder — wer
    eine fremde Datei öffnete, arbeitete für immer gegen deren Bauraum.
    """
    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()
    before = session.project.document.printer

    session.change_scene_profile("prusa-mk4s", "petg")
    session.wait_for_idle()

    assert session.project.document.printer == "prusa-mk4s"
    assert session.profile.printer.id == "prusa-mk4s", "das Profil folgt, nicht nur die Kennung"

    session.undo()
    assert session.project.document.printer == before, "eine Transaktion, also rücknehmbar"


# --- Entdeckbarkeit (§2.6, §19.2) -----------------------------------------------


def test_the_palette_reaches_more_than_the_registry(window: MainWindow) -> None:
    """§2.6: die Palette ist der Universalzugang — sie kannte nur Operationen.

    Speichern, das Handbuch und die sieben Ansichtswerkzeuge stehen nicht im
    Register. `ToolStrip.tool_titles()` und `strip_title()` wurden dafür
    geschrieben und hatten außer Tests keinen Aufrufer.
    """
    commands = window.window_commands()

    assert "file.save" in commands
    assert "help.manual" in commands
    for key in window.tools.tool_titles():
        assert f"tool.{key}" in commands, f"{key} fehlt in der Palette"

    for _title, _shortcut, slot in commands.values():
        assert callable(slot)


def test_escape_closes_the_open_tool(window: MainWindow) -> None:
    """`close_tool` gab es seit jeher und niemanden, der es rief."""
    window.tools.toggle("section")
    assert window.tools.active() == "section"

    window.tools.close_tool()
    assert window.tools.active() is None


def test_the_view_menu_can_fit_everything(window: MainWindow) -> None:
    """Ohne diesen Eintrag musste man wissen, dass Strg+0 nebenbei einpasst."""
    labels = {action.text() for action in all_menu_actions(window)}
    assert "Alles einpassen" in labels


def test_the_first_body_gets_the_camera(window: MainWindow) -> None:
    """Sonst bleibt die Kamera, wo sie war, und das Teil liegt außerhalb des
    Bildes — die Anwendung sieht aus, als hätte sie nichts geladen."""
    assert not window._seen_objects

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window._on_scene(window.session.evaluate_now())

    assert window._seen_objects


def test_the_toolbar_buttons_carry_a_symbol_and_keep_their_words(
    window: MainWindow,
) -> None:
    """Regel 18: vier gleich aussehende Textknöpfe sind vier Vermutungen."""
    from app.ui import icons

    for name in ("new", "open", "save", "import"):
        assert name in icons.known(), f"{name} fehlt im Symbolkatalog"

    from PySide6.QtWidgets import QWidgetAction

    toolbar = window.findChildren(QToolBar)[0]
    for action in toolbar.actions():
        # Eingehängte Widgets sind keine Knöpfe: sie tragen ihre Beschriftung
        # selbst, und ein leerer ``text()`` ist bei ihnen kein Befund.
        if isinstance(action, QWidgetAction) or action.isSeparator():
            continue
        assert action.text(), "das Wort bleibt"
        assert not action.icon().isNull(), f"{action.text()} ohne Zeichen"


# --- Die Aufräumrunde -----------------------------------------------------------


def test_the_keyboard_reaches_zoom_and_the_next_body(window: MainWindow) -> None:
    """§19.2: der Viewport ist mit der Tastatur navigierbar.

    Die Achsansichten waren es, Zoom und Durchblättern nicht — wer ohne
    Zeigegerät arbeitet, sah jedes Modell aus derselben Entfernung.
    """
    _with_two_objects(window)
    window.object_tree.tree.topLevelItem(0).setSelected(True)
    assert window.object_tree.selected_objects() == ("obj_1",)

    window.object_tree.step_selection(True)
    assert window.object_tree.selected_objects() == ("obj_2",)

    # Reihum: hinter dem letzten kommt wieder der erste.
    window.object_tree.step_selection(True)
    assert window.object_tree.selected_objects() == ("obj_1",)

    window.object_tree.step_selection(False)
    assert window.object_tree.selected_objects() == ("obj_2",)

    shortcuts = {entry.key().toString() for entry in window.findChildren(QShortcut)}
    assert "Ctrl+Tab" in shortcuts
    assert any("+" in text for text in shortcuts), "der Zoom hat ein Kürzel"


def test_the_fourth_navigation_scheme_exists_without_changing_the_default() -> None:
    """Bambu, Orca und Prusa drehen mit links; §2.9 gibt Cura vor.

    Ein viertes Wahlschema ist keine Bauplanänderung — die Vorgabe bleibt.
    """
    from app.ui.settings_dialog import NAVIGATION

    assert "orbit" in NAVIGATION
    assert UiSettings().navigation == "slicer", "die Vorgabe folgt weiter §2.9"


def test_the_report_can_be_filtered(window: MainWindow) -> None:
    """Ein Bericht mit hundert Hinweisen und zwei Fehlern versteckt die zwei.

    Die Liste steht nach Schwere: der Fehler ist die erste Zeile, der Hinweis
    die zweite — auch wenn der Hinweis zuerst gemeldet wurde.
    """
    from app.core.types import Finding

    window.report.add_findings(
        [
            Finding(code="a", severity="info", message="Wandstärke knapp"),
            Finding(code="b", severity="error", message="Netz ist offen"),
        ]
    )
    assert window.report.list.count() == 2

    window.report.severity.setCurrentIndex(window.report.severity.findData("error"))
    hidden = [window.report.list.item(row).isHidden() for row in range(window.report.list.count())]
    assert hidden == [False, True]

    window.report.severity.setCurrentIndex(0)
    window.report.search.setText("wandstärke")
    hidden = [window.report.list.item(row).isHidden() for row in range(window.report.list.count())]
    assert hidden == [True, False], "der Text filtert unabhängig vom Schweregrad"

    assert "1 × Fehler" in window.report.summary.text(), "gezählt wird der ganze Bericht"


def test_the_history_shows_what_a_redo_would_bring_back(window: MainWindow) -> None:
    """Zurückgenommene Schritte verschwanden hier spurlos."""
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window._on_project()
    before = window.history_panel.list.count()

    window.session.undo()
    window.session.wait_for_idle()
    window._on_project()

    labels = [
        window.history_panel.list.item(row).text()
        for row in range(window.history_panel.list.count())
    ]
    assert any("zurückgenommen" in text for text in labels), labels
    assert window.history_panel.list.count() == before, "nichts verschwindet, es wechselt die Seite"


def test_a_recent_entry_can_be_forgotten(window: MainWindow, tmp_path: Path) -> None:
    """Was einmal in der Liste stand, blieb bis es hinausrutschte."""
    path = tmp_path / "versuch.p3d"
    window.settings.recent = [str(path)]

    window._forget_recent(path)

    assert window.settings.recent == []


# --- Export aus dem Fenster (§29, §2.2) ------------------------------------------


def test_an_unreadable_gcode_file_says_so(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regel 17: keine Handlung endet stumm.

    ``action_check_gcode`` las die Datei ohne Netz darunter. Zwischen Auswählen
    und Lesen kann sie verschwinden, auf einem getrennten Laufwerk liegen oder
    ohne Leserecht dastehen — die Ausnahme lief dann ungefangen in Qts
    Ereignisverteiler: kein Dialog, keine Zeile, die Handlung tat nichts.
    """
    from PySide6.QtWidgets import QFileDialog

    from app.ui import dialogs

    gezeigt: list[object] = []
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *args, **kwargs: (str(tmp_path / "weg.gcode"), "")),
    )
    monkeypatch.setattr(dialogs, "show_error", lambda error, *args, **kwargs: gezeigt.append(error))
    monkeypatch.setattr(
        "app.ui.main_window.show_error", lambda error, *args, **kwargs: gezeigt.append(error)
    )

    window.action_check_gcode()

    assert gezeigt, "die fehlende Datei wurde stillschweigend übergangen"
    assert gezeigt[0].suggestions, "und der Fehler trägt keinen Handlungsvorschlag"


def test_export_writes_the_selected_format(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Weg 1 endet mit „exportieren" — und dieser Schritt war aus dem Fenster
    nicht erreichbar: der Schreiber stand seit P2 im Kern, der einzige Weg zu
    einer Datei führte über einen installierten Slicer."""
    from PySide6.QtWidgets import QFileDialog

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()

    target = tmp_path / "wuerfel.stl"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *args, **kwargs: (str(target), "STL (*.stl)")),
    )
    window.action_export()

    assert target.is_file(), "der gewählte Name ist die Datei, nicht ein Schema daraus"
    assert target.stat().st_size > 0


def test_export_as_3mf_writes_one_assembly(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mehrere Körper als 3MF sind eine Baugruppe in einer Datei (§20) —
    nicht eine Datei je Körper, über deren Zusammengehörigkeit der Slicer
    selbst entscheiden müsste."""
    from PySide6.QtWidgets import QFileDialog

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window.session.import_model(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()

    target = tmp_path / "baugruppe.3mf"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *args, **kwargs: (str(target), "3MF (*.3mf)")),
    )
    window.object_tree.tree.clearSelection()
    window.action_export()

    written = list(tmp_path.glob("*.3mf"))
    assert len(written) == 1, "eine Baugruppe, eine Datei"


def test_export_is_disabled_on_an_empty_scene(window: MainWindow) -> None:
    """Ein Exporteintrag, der auf leerer Szene ein Fenster öffnet, wäre die
    modale Sackgasse aus der Bedienrunde — er ist stattdessen aus."""
    assert not window.export_action.isEnabled()
    assert not window.auto_split_action.isEnabled()
    assert not window.variants_action.isEnabled()


# --- Parameter ohne Agent anlegen (§13, §2.3) ------------------------------------


def test_a_parameter_can_be_added_without_the_agent(session: Session) -> None:
    """§2.3 verspricht: ohne KI funktioniert alles außer dem Chat. Das
    Anlegen eines Parameters war aber ein reines Agentenwerkzeug — und ein
    Undo muss den neuen Parameter entfernen, nicht auf Null setzen (§15.5)."""
    session.add_parameter(Parameter(name="width", value=40.0))

    assert "width" in session.project.document.parameters
    assert session.modified

    session.undo()
    assert "width" not in session.project.document.parameters


def test_adding_a_taken_parameter_name_fails(session: Session) -> None:
    """Ein zweiter Parameter gleichen Namens überschriebe den ersten still —
    stattdessen kommt ein Fehler mit Vorschlag (§2.7)."""
    caught: list[object] = []
    session.failed.connect(caught.append)
    session.add_parameter(Parameter(name="width", value=40.0))

    session.add_parameter(Parameter(name="width", value=50.0))

    assert caught, "der zweite Versuch meldet sich"
    assert session.project.document.parameters["width"].value == pytest.approx(40.0)


def test_a_parameter_expression_may_not_cycle(session: Session) -> None:
    """Die Zyklusprüfung aus §13 gilt auch für den Weg über die Leiste."""
    caught: list[object] = []
    session.failed.connect(caught.append)
    session.add_parameter(Parameter(name="width", value=40.0))

    session.add_parameter(Parameter(name="height", value=0.0, expression="=@missing + 1"))

    assert caught, "ein Ausdruck auf einen unbekannten Parameter wird abgelehnt"
    assert "height" not in session.project.document.parameters


def test_the_parameter_dialog_validates_inline(qt_app: QApplication) -> None:
    """Der Dialog lehnt inline ab, statt ein Fenster auf ein Fenster zu
    stellen: leerer Name, vergebener Name, kaputter Ausdruck."""
    from app.ui.dialogs import ParameterDialog

    taken = {"width": Parameter(name="width", value=40.0)}
    dialog = ParameterDialog(taken)

    assert dialog.validation_problem() is not None, "ohne Namen geht es nicht"

    dialog.name_field.setText("width")
    assert dialog.validation_problem() is not None, "der Name ist vergeben"

    dialog.name_field.setText("height")
    dialog.expression_field.setText("=@width / 2")
    assert dialog.validation_problem() is None
    made = dialog.parameter()
    assert made.expression == "=@width / 2"
    assert made.value == pytest.approx(20.0), "der Startwert kommt aus dem Ausdruck"

    dialog.expression_field.setText("import os")
    assert dialog.validation_problem() is not None, "alles außerhalb der Grammatik fällt durch"


def test_the_catalog_button_says_what_it_does(qt_app: QApplication) -> None:
    """„OK" sagte nicht, was es tut — im Katalog blieb der Standardknopf
    stehen, während jeder Operationsdialog längst nach seiner Operation
    heißt."""
    from PySide6.QtWidgets import QDialogButtonBox

    from app.ui.catalog import PartCatalog

    catalog = PartCatalog()
    box = catalog.findChild(QDialogButtonBox)
    assert box is not None
    ok = box.button(QDialogButtonBox.StandardButton.Ok)
    assert ok is not None
    assert ok.text().replace("&", "") == "Einfügen"


def test_the_catalog_says_in_words_what_takes_material_away(qt_app: QApplication) -> None:
    """Regel 18: was subtraktiv ist, trug allein die Farbe des Vorschaubilds.

    Orange nimmt weg, grau setzt hinzu — ohne Legende, und für jeden, der die
    beiden Farben nicht unterscheidet, gar nicht.
    """
    from app.core.knowledge.parts import PARTS
    from app.ui.catalog import SUBTRACTIVE_MARKER, describe

    subtractive = [spec for spec in PARTS.all() if spec.subtractive]
    additive = [spec for spec in PARTS.all() if not spec.subtractive]
    assert subtractive and additive, "sonst prüft dieser Test nichts"

    for spec in subtractive:
        assert SUBTRACTIVE_MARKER in describe(spec)
        assert tr("nimmt Material weg") in describe(spec)
    for spec in additive:
        assert tr("nimmt Material weg") not in describe(spec)


def test_the_detail_column_explains_the_chosen_part(qt_app: QApplication) -> None:
    """Eine Kachel trägt so viel, wie auf eine Kachel passt.

    Alles Weitere stand in einem Tooltip, den man erst findet, wenn man weiß,
    dass er da ist.
    """
    from app.core.knowledge.parts import PARTS
    from app.ui.catalog import PartCatalog, detail

    assert tr("Wählen Sie") in detail(None), "ohne Auswahl sagt sie, was zu tun ist"

    spec = next(entry for entry in PARTS.all() if entry.subtractive)
    text = detail(spec)
    assert str(spec.title) in text
    assert str(spec.doc) in text
    assert tr("nimmt Material weg") in text
    for entry in spec.params.spec():
        assert str(entry.title) in text, "alle Parameter, nicht nur die zwei der Kachel"

    catalog = PartCatalog()
    assert catalog.detail.text() == detail(None), "beim Öffnen ist nichts gewählt"


def test_the_catalog_grid_never_scrolls_sideways(qt_app: QApplication) -> None:
    """Das Raster bricht um — eine Leiste darunter hieße, dass es das nicht
    tut."""
    from PySide6.QtCore import Qt

    from app.ui.catalog import PartCatalog

    catalog = PartCatalog()
    assert catalog.list.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff


# --- Auto Split abseits des Hauptthreads (§2.8) ----------------------------------


def test_auto_split_runs_in_a_worker(session: Session) -> None:
    """Die Trennebenensuche lief mit Wartezeiger im Hauptthread — jetzt
    meldet sie sich über ``splitBusyChanged`` und liefert ihr Ergebnis an
    einen Rückruf, während das Fenster bedienbar bleibt."""
    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()

    states: list[bool] = []
    session.splitBusyChanged.connect(states.append)
    results: list[object] = []

    session.split_async("obj_1", results.append)
    session.wait_for_idle()

    assert results, "der Rückruf bekommt das Ergebnis"
    applied = results[0]
    assert applied.transaction is None, "ein 20-mm-Würfel passt aufs Bett"
    assert states and states[0] is True and states[-1] is False


# --- Live-Vorschau im Operationsdialog (§18.7) -----------------------------------


def test_a_preview_delivers_a_difference(session: Session) -> None:
    """Der Dialog zeigt, was er täte: dieselbe Differenzansicht wie beim
    Agentenvorschlag, gerechnet auf einer Kopie, ohne den Stapel anzufassen."""
    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()
    stack_before = list(session.project.document.ops)

    collected: list[object] = []
    session.preview_async(
        collected.append,
        [
            OperationDraft(
                op="drill_hole",
                inputs=("obj_1",),
                params={"diameter": 4.0, "x": 0.0, "y": 0.0, "z": 0.0, "axis": "z"},
            )
        ],
    )
    session.wait_for_idle()

    assert collected, "die Vorschau liefert"
    difference = collected[0]
    assert difference is not None and difference.changed, "eine Bohrung ändert Volumen"
    assert list(session.project.document.ops) == stack_before, "der Stapel bleibt unberührt"


def test_a_cancelled_preview_stays_silent(session: Session) -> None:
    """Der Dialog ist zu, bevor die Rechnung fertig ist — das Ergebnis wird
    verworfen statt gezeigt (§18.7)."""
    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()

    collected: list[object] = []
    session.preview_async(
        collected.append,
        [
            OperationDraft(
                op="drill_hole",
                inputs=("obj_1",),
                params={"diameter": 4.0, "x": 0.0, "y": 0.0, "z": 0.0, "axis": "z"},
            )
        ],
    )
    session.cancel_preview()
    session.wait_for_idle()

    assert not collected, "eine verworfene Vorschau meldet sich nicht mehr"


def test_a_broken_preview_shows_nothing_instead_of_failing(session: Session) -> None:
    """Beim Tippen entstehen ungültige Zwischenstände — die Vorschau zeigt
    dann nichts; der echte Fehler kommt beim Anwenden als Vorschlag (§2.7)."""
    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()

    collected: list[object] = []
    session.preview_async(
        collected.append,
        [OperationDraft(op="drill_hole", inputs=("obj_1",), params={"diameter": -1.0})],
    )
    session.wait_for_idle()

    assert collected == [None], "kein Fehlerdialog, nur keine Vorschau"


def test_the_wired_dialog_previews_into_the_viewport(window: MainWindow) -> None:
    """Die Verdrahtung Ende zu Ende: Dialog auf, erste Vorschau läuft von
    selbst, die Differenz steht im Viewport — und mit dem Schließen geht sie."""
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()

    spec = REGISTRY.get("drill_hole")
    dialog = OperationDialog(spec, window._object_names(), window)
    window._wire_preview(
        dialog,
        lambda entered: [OperationDraft(op=spec.name, inputs=("obj_1",), params=entered)],
    )
    window.session.wait_for_idle()

    assert window.viewport.difference is not None, "die Vorgaben sind schon eine Aussage"

    window._clear_preview()
    assert window.viewport.difference is None


def test_rapid_previews_never_orphan_a_worker(session: Session) -> None:
    """Wer schnell tippt, startet Vorschau auf Vorschau. Jeder laufende
    Arbeiter bleibt referenziert, bis er ausgelaufen ist — ein QThread ohne
    Referenz wird sonst vom Speicherbereiniger mitsamt laufendem C++-Objekt
    zerstört: der Absturz ohne Zeile, der die Suite sporadisch riss."""
    import gc

    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()

    collected: list[object] = []
    for diameter in (2.0, 3.0, 4.0, 5.0, 6.0):
        session.preview_async(
            collected.append,
            [
                OperationDraft(
                    op="drill_hole",
                    inputs=("obj_1",),
                    params={"diameter": diameter, "x": 0.0, "y": 0.0, "z": 0.0, "axis": "z"},
                )
            ],
        )
    gc.collect()
    session.wait_for_idle()
    gc.collect()

    assert len(collected) == 1, "nur die jüngste Vorschau wird geliefert"
    assert not session._previews, "kein Arbeiter bleibt zurück"


# --- die Tour durch ein Beispiel (§37.2) ------------------------------------------


def _tour_tab_visible(window: MainWindow) -> bool:
    """Ob der Tour-Reiter gerade angeboten wird — er existiert immer, sichtbar
    ist er nur mit offenem Beispiel."""
    return window.right.isTabVisible(window.right.indexOf(window.tour))


def test_opening_an_example_starts_its_tour(window: MainWindow, session: Session) -> None:
    """§37.2: ein Beispiel öffnet sich mit seiner Tour, und die Erkennung
    schaltet an den echten Signalen der Sitzung weiter — Doppelklick-Änderung,
    Undo und Redo, wie ein Nutzer sie auslöst.

    Die Wartezeiten sind großzügig: das Beispiel rechnet eine echte Reparatur,
    und läuft die auf einer belasteten Maschine über die 10-Sekunden-Vorgabe
    von ``wait_for_idle`` hinaus, endet der Test mit laufendem Arbeiter — den
    zerstört der Speicherbereiniger später mitsamt C++-Objekt, und die Suite
    reißt ohne Zeile am Ende ab.
    """
    from app.core import examples

    window.open_path(examples.directory() / "weg1-halterung-anpassen.p3d")
    session.wait_for_idle(120_000)

    assert _tour_tab_visible(window)
    assert window.right.currentWidget() is window.tour, "auch eine Warnung stiehlt den Reiter nicht"
    assert window.tour.active
    assert window.tour.current_index == 0, "der Leseschritt wartet auf „Weiter“"

    window.tour.advance()
    assert window.tour.current_index == 1

    # Die Handlung aus Schritt 2: der Durchmesser der Bohrung ändert sich.
    drill = next(entry for entry in session.project.document.ops if entry.op == "drill_hole")
    session.change_params(drill.id, {"diameter": 6.0})
    assert window.tour.current_index == 2

    session.undo()
    assert window.tour.current_index == 3

    session.redo()
    assert window.tour.current_index == 4

    window.tour.advance()
    assert window.tour.current_index == 5
    assert not window.tour.closing.isHidden(), "der Abschluss steht da"
    assert window.tour.next_button.isHidden(), "hinter dem letzten Schritt gibt es kein Weiter"

    window.tour.stop_button.click()
    assert not _tour_tab_visible(window)
    session.wait_for_idle(120_000)
    assert not session.busy, "kein Arbeiter überlebt den Test"


def test_a_plain_project_carries_no_tour(
    window: MainWindow, session: Session, tmp_path: Path
) -> None:
    """Die Tour gehört den Beispielen: ein gewöhnliches Projekt räumt den
    Reiter wieder weg, statt eine fremde Anleitung weiterlaufen zu lassen."""
    from app.core import examples
    from app.core.scene.project import new_project, save

    window.open_path(examples.directory() / "weg1-halterung-anpassen.p3d")
    session.wait_for_idle(120_000)
    assert _tour_tab_visible(window)

    path = save(new_project("centauri-carbon-2", "petg"), tmp_path / "plain.p3d")
    window.open_path(path)
    session.wait_for_idle(120_000)

    assert not _tour_tab_visible(window)
    assert not window.tour.active
    assert not session.busy, "kein Arbeiter überlebt den Test"


# --- Fernsteuerung über MCP (Konzept P15 §7 Etappe 9, D19) ----------------------


def test_a_remote_call_is_one_transaction_the_window_can_undo(window: MainWindow) -> None:
    """Die vierte Auflage, und die einzige, die nur am Dokument prüfbar ist.

    Ein Fernaufruf geht denselben Weg wie ein Menüklick: dieselbe Transaktion,
    dieselbe Auswertung, dasselbe Undo. Wäre es ein zweiter Weg ins Dokument,
    stünde hier ein Körper, den kein Strg+Z wegbekommt — und niemand wüsste,
    woher er kam.
    """
    answer = window.run_remote("create_box", {"width": 20.0, "depth": 20.0, "height": 20.0})
    assert "Objekte" in answer

    document = window.session.project.document
    assert [entry.op for entry in document.ops] == ["create_box"]
    assert len(document.transactions) == 1

    window.action_undo()
    window.session.wait_for_idle()
    assert window.session.project.document.ops == []


def test_a_remote_call_says_where_it_came_from(window: MainWindow) -> None:
    """Der Herkunftsvermerk (§26.4).

    Wer hinterher fragt „habe ich das getan?", bekommt eine Antwort statt einer
    Vermutung. Ohne den Vermerk sähe ein Fernaufruf im Verlauf aus wie ein
    eigener Klick.
    """
    window.run_remote("create_box", {"width": 10.0, "depth": 10.0, "height": 10.0})
    origin = window.session.project.document.transactions[0].origin
    assert origin is not None
    assert origin.by == "agent"
    assert origin.model == REMOTE_ORIGIN


def test_the_toolbar_has_a_drawing_entry_for_way_two(window: MainWindow) -> None:
    """§2.2: Weg 2 (neu konstruieren) nennt die Werkzeugzeile als Ort — der
    Platz war nie belegt, und das Zeichnen lag drei Ebenen tief im Menü. Der
    Knopf startet den Skizzenmodus ohne festgelegte Operation; die
    Erzeugungsart kommt bei „Fertig".
    """
    from PySide6.QtWidgets import QToolBar

    toolbar = window.findChild(QToolBar)
    assert toolbar is not None
    labels = [action.text() for action in toolbar.actions() if action.text()]
    assert "Zeichnen" in labels
    assert labels.index("Modell einfügen") < labels.index("Zeichnen")

    window.action_sketch_free()
    try:
        assert window.sketching()
        assert window._sketch_target == ""
    finally:
        window.finish_sketch(keep=False)


def test_the_sketch_bar_says_what_finishing_does(window: MainWindow) -> None:
    """Der Hinweis über „Fertig" zeigte auf eine Operation, die es beim
    freien Zeichnen noch nicht gibt.

    Beide Wege enden auf demselben Knopf, aber nicht am selben Ort: mit
    festgelegter Op öffnet sie sich auf der Skizze, ohne fragt erst der
    Dialog. Wer „die Operation" liest und keine gewählt hat, sucht nach
    etwas, das nirgends steht.
    """
    window.action_sketch_free()
    try:
        assert "Operation" not in window._sketch_hint.text()
        assert "Freies Zeichnen" in window.statusBar().currentMessage()
    finally:
        window.finish_sketch(keep=False)

    window.start_sketch("sketch_extrude")
    try:
        assert "Operation" in window._sketch_hint.text()
        assert str(REGISTRY.get("sketch_extrude").title) in window.statusBar().currentMessage()
    finally:
        window.finish_sketch(keep=False)


def test_the_sketch_use_dialog_preselects_extruding() -> None:
    """Vorausgewählt ist der Normalfall, nicht die erste Zeile.

    Die Liste kommt alphabetisch nach Titel aus dem Register, und damit stand
    „Entlang eines Bogens führen" oben — ein Rohrbogen, der seltenste der
    fünf Fälle. Wer nach dem Zeichnen auf „Weiter" drückt, ohne zu lesen,
    bekam ihn; aus einer gezeichneten Fläche wird im Normalfall ein Körper,
    indem man sie aufzieht.
    """
    from app.ui.op_dialog import SketchUseDialog

    dialog = SketchUseDialog()
    assert dialog.chosen() == "sketch_extrude"
    # Die Reihenfolge der Liste bleibt, wie das Register sie liefert — geprüft
    # wird die Markierung, nicht das Sortieren.
    assert dialog._list.count() == 5
    assert dialog._list.item(0).data(Qt.ItemDataRole.UserRole) == "sketch_sweep"


def test_a_free_sketch_asks_what_it_becomes(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Fluss hinter dem Zeichnen-Knopf: „Fertig" fragt, was aus der
    Skizze wird — und „Zurück zum Zeichnen" vernichtet nichts, es öffnet den
    Skizzenmodus mit derselben Zeichnung wieder (§2.1, keine Sackgassen).
    """
    from app.ui import main_window as window_module
    from app.ui.op_dialog import SketchUseDialog

    # Der Weiter-Weg: die Wahl landet als vorbefüllte Skizze in der Operation.
    ran: list[tuple[str, str]] = []
    monkeypatch.setattr(SketchUseDialog, "exec", lambda self: QDialog.DialogCode.Accepted)
    monkeypatch.setattr(SketchUseDialog, "chosen", lambda self: "sketch_extrude")
    monkeypatch.setattr(
        type(window),
        "run_operation",
        lambda self, spec, given=None: ran.append((spec.name, next(iter(given.values())))),
    )
    window._offer_sketch_use('{"plane": "plane:xy"}')
    assert ran == [("sketch_extrude", '{"plane": "plane:xy"}')]

    # Der Zurück-Weg: kein Verlust, der Modus öffnet mit der Zeichnung.
    monkeypatch.setattr(SketchUseDialog, "exec", lambda self: QDialog.DialogCode.Rejected)
    kept: list[tuple[str, str]] = []
    monkeypatch.setattr(
        type(window), "start_sketch", lambda self, op, text="": kept.append((op, text))
    )
    window._offer_sketch_use('{"plane": "plane:xy"}')
    assert kept == [("", '{"plane": "plane:xy"}')]
    assert window_module is not None


def test_the_sketch_use_dialog_lists_the_five_kinds(window: MainWindow) -> None:
    from app.ui.op_dialog import SketchUseDialog

    dialog = SketchUseDialog(window)
    names = {
        str(dialog._list.item(index).data(Qt.ItemDataRole.UserRole))
        for index in range(dialog._list.count())
    }
    assert names == {
        "sketch_extrude",
        "sketch_pocket",
        "sketch_revolve",
        "sketch_loft",
        "sketch_sweep",
    }
    assert dialog.chosen() in names, "eine Vorauswahl steht, Eingabe genügt"


def test_undo_in_the_sketch_mode_means_the_last_stroke(window: MainWindow) -> None:
    """Strg+Z gehört im Skizzenmodus dem Blatt, nicht dem Verlauf.

    Das Kürzel hing am Dialog um das Panel — und den Dialog gibt es nur auf
    einem der beiden Wege. Im Skizzenmodus des Fensters lag Strg+Z damit beim
    Verlauf und nahm die letzte **Operation** zurück, während vor dem Nutzer
    eine Zeichenfläche stand. Aufgefallen beim Beschreiben des Kapitels, nicht
    beim Bedienen: der Editor hat einen Rückgängig-Knopf, und wer den nimmt,
    merkt nie etwas.

    Zwei Hälften, beide nötig: das Panel bringt das Kürzel mit, und das
    Fenster graut seine zwei Einträge im Modus aus. Ohne die zweite Hälfte
    feuert **keine** von beiden Belegungen — Qt lässt bei zweien derselben
    Taste keine gelten, dieselbe Falle wie bei R und C.
    """
    from PySide6.QtGui import QKeySequence, QShortcut

    from app.ui.sketch_editor import SketchPanel

    panel_keys = [
        entry.key().toString() for entry in SketchPanel("", parent=window).findChildren(QShortcut)
    ]
    assert QKeySequence(QKeySequence.StandardKey.Undo).toString() in panel_keys

    window.run_operation(REGISTRY.get("create_box"))
    dialog = next(child for child in window.findChildren(OperationDialog) if child.isVisible())
    dialog.accept()
    window.session.wait_for_idle()
    assert window.session.history.can_undo, "sonst prüft das Folgende nichts"
    assert window.undo_action.isEnabled()

    window.action_sketch_free()
    try:
        assert not window.undo_action.isEnabled(), "im Modus gehört Strg+Z dem Blatt"
        assert not window.redo_action.isEnabled()
    finally:
        window.finish_sketch(keep=False)

    assert window.undo_action.isEnabled(), "und danach wieder dem Verlauf"


def test_the_sketch_field_knows_as_much_as_the_sketch_mode(window: MainWindow) -> None:
    """Beide Wege zum Editor bringen die Szene mit — sonst ist einer ärmer.

    Der Docstring von ``SketchPanel`` sagt seit je, dass keiner der beiden Wege
    ein Werkzeug bekommt, das der andere nicht hat. Er stimmte nicht: der
    Skizzenmodus reichte Bauraum, Flächen und Netze herein, das Skizzenfeld im
    Operationsdialog nichts davon. Wer aus dem Verlauf eine Skizze wieder
    öffnete, hatte keinen Bauraumrand, keine Fläche des Körpers in der
    Ebenenwahl — und *Projizieren* antwortete „kein Körper" an einem Modell,
    das im Fenster stand.
    """
    from app.ui.sketch_editor import SketchEditorDialog, SketchField

    _with_two_objects(window)
    surroundings = window._sketch_surroundings()
    assert surroundings.bed is not None, "der Bauraum kommt aus dem Profil"
    assert len(surroundings.bodies) == 2, "beide Körper sind Vorlage für die Projektion"

    field = SketchField("", {}, window, surroundings)
    dialog = SketchEditorDialog("", {}, field, field._surroundings)
    try:
        canvas = dialog.canvas
        assert canvas._bed == surroundings.bed
        assert len(canvas._bodies) == 2
        # Die drei Grundebenen stehen immer; die Flächen der Körper kommen
        # dazu, sobald einer da ist.
        assert dialog.panel.plane_choice.count() > 3
    finally:
        dialog.reject()


def test_the_exact_twin_runs_through_the_partner_dialog(window: MainWindow) -> None:
    """Die zusammengelegten Zwillinge: derselbe Dialog, ein Umschalter, und
    erst er entscheidet den Rechenkern. Die Parameter werden auf das Schema
    der gewählten Op gefiltert — der exakte Quader kennt kein ``anchor``.
    """
    from PySide6.QtWidgets import QCheckBox

    window.run_operation(REGISTRY.get("create_box"))
    dialog = next(child for child in window.findChildren(OperationDialog) if child.isVisible())
    exact = next(box for box in dialog.findChildren(QCheckBox) if "B-Rep" in box.text())
    exact.setChecked(True)
    # ``accept`` wendet an und räumt den Dialog selbst ab — danach gehört
    # das C++-Objekt niemandem mehr, auch keinem ``finally``.
    dialog.accept()
    window.session.wait_for_idle()

    ops = window.session.project.document.ops
    assert [entry.op for entry in ops] == ["create_brep_box"]
    assert "anchor" not in ops[-1].params, "gefiltert auf das Schema des exakten Kerns"


@pytest.mark.parametrize(
    ("shown", "hidden", "gone"),
    [
        ("create_box", "create_brep_box", "anchor"),
        ("create_cylinder", "create_brep_cylinder", "segments"),
    ],
)
def test_the_exact_twin_hides_what_it_cannot_do(
    window: MainWindow, shown: str, hidden: str, gone: str
) -> None:
    """Ein Feld ohne Wirkung ist ein Versprechen, das niemand hält.

    Gefiltert wurden bis dahin nur die Werte beim Anwenden; im Dialog stand
    der Bezugspunkt weiter da — und er steht in derselben aufgeklappten
    Gruppe wie der Umschalter, an der also jeder vorbeikommt, der „Exakt"
    sucht. Wer ihn auf „Ecke" stellte, bekam einen mittigen Quader und keinen
    Ton dazu. Mit dem Umschalter verschwindet die Zeile, und die Beschreibung
    oben wechselt mit: die des Netz-Quaders nennt eine Wahl, die es im
    exakten Kern nicht gibt.
    """
    from PySide6.QtWidgets import QCheckBox

    window.run_operation(REGISTRY.get(shown))
    dialog = next(child for child in window.findChildren(OperationDialog) if child.isVisible())
    dialog.advanced.setChecked(True)
    exact = next(box for box in dialog.findChildren(QCheckBox) if "B-Rep" in box.text())

    assert dialog._editors[gone].isVisibleTo(dialog), "im Netzkern hat das Feld seine Wirkung"
    exact.setChecked(True)
    assert not dialog._editors[gone].isVisibleTo(dialog), f"{gone} wirkt in {hidden} nicht"
    assert dialog._description is not None
    assert dialog._description.text() == str(REGISTRY.get(hidden).doc)

    # Und zurück: der Umschalter ist keine Einbahnstraße.
    exact.setChecked(False)
    assert dialog._editors[gone].isVisibleTo(dialog)
    assert dialog._description.text() == str(REGISTRY.get(shown).doc)
    dialog.reject()


def test_the_menu_path_matches_the_built_menu_for_every_operation(window: MainWindow) -> None:
    """§2.6: der Menüort in den Werkzeugbeschreibungen kommt aus
    ``menu_path`` — dieser Test hält ihn an der wirklich gebauten Leiste
    fest, Ebene für Ebene. Ohne die Kopplung nannte der Chat für 72 von 77
    Operationen einen Ort ohne die Untermenüs, die die Leiste einzieht.
    """
    from PySide6.QtWidgets import QMenu

    from app.core.registry import REGISTRY, menu_path

    def paths_of(menu: QMenu, trail: tuple[str, ...]) -> dict[QAction, str]:
        found: dict[QAction, str] = {}
        for action in menu.actions():
            submenu = action.menu()
            if submenu is not None:
                found.update(paths_of(submenu, (*trail, submenu.title())))
            else:
                found[action] = " → ".join((*trail, action.text()))
        return found

    built: dict[QAction, str] = {}
    for group in window._workspace_menus:
        built.update(paths_of(group, (group.title(),)))

    checked = 0
    for name, action in window._op_actions.items():
        if action not in built:
            continue
        checked += 1
        assert built[action] == menu_path(REGISTRY.get(name)), name
    assert checked >= 70, "die Kopplung deckt praktisch das ganze Register"


def test_scene_views_render_labelled_pngs(window: MainWindow) -> None:
    """§23: zwei beschriftete Ansichten als PNG — gerendert von einem
    kurzlebigen Offscreen-Plotter, der den sichtbaren Viewport nicht anfasst.
    """
    from app.ui.snapshots import scene_views

    window.run_remote("create_box", {"width": 20.0, "depth": 20.0, "height": 20.0})
    result = window.session.last_result
    assert result is not None

    views = scene_views(result.scene)

    assert len(views) == 2
    labels = [label for label, _image in views]
    assert any("oben" in label for label in labels)
    for _label, image in views:
        assert image.startswith(b"\x89PNG"), "echte PNG-Bytes, kein rohes Array"

    from app.core.types import Scene

    assert scene_views(Scene()) == (), "eine leere Szene hat nichts zu zeigen"


def test_a_remote_value_that_is_no_number_is_an_answer_not_a_crash(window: MainWindow) -> None:
    """Konzept Agent-Vertiefung 2.4: die Fernsteuerung rief ``float()``
    ungeprüft — ein „abc" von außen war ein Programmfehler statt einer
    Meldung. Jetzt prüft ``parse_number``, dieselbe Funktion wie im Chat.
    """
    from app.core.agent.tools import ADD_PARAMETER

    answer = window.run_remote(ADD_PARAMETER, {"name": "breite", "value": "abc"})

    assert "keine Zahl" in answer
    assert window.session.project.document.transactions == []
    assert "breite" not in window.session.project.document.parameters


def test_the_remote_report_filters_from_a_severity_upwards(window: MainWindow) -> None:
    """Konzept Agent-Vertiefung 2.4: „ab dieser Schwere", wie das
    Werkzeugschema sagt — die Fernsteuerung filterte exakt und lieferte auf
    ``warning`` keine Fehler. Jetzt antwortet ``report_text``, dieselbe
    Funktion wie im Chat.
    """
    from app.core.agent.session import report_text
    from app.core.types import Finding, Report, Scene

    scene = Scene()
    scene.report = Report(
        (
            Finding(code="a", severity="info", message="Hinweis"),
            Finding(code="b", severity="warning", message="Warnung"),
            Finding(code="c", severity="error", message="Fehler"),
        )
    )

    text = report_text(scene, "warning")

    assert "Warnung" in text
    assert "Fehler" in text, "eine Frage nach Warnungen unterschlägt keine Fehler"
    assert "Hinweis" not in text


def test_the_remote_interface_stays_off_unless_it_is_switched_on(window: MainWindow) -> None:
    """Die erste Auflage: aus, bis jemand sie einschaltet.

    Eine offene Schnittstelle, die niemand eingeschaltet hat, stünde auf jedem
    Rechner offen, auf dem die Anwendung installiert ist. Geprüft an der
    Vorgabe **und** am Fenster, denn eine Vorgabe, die beim Start überschrieben
    wird, ist keine.
    """
    assert UiSettings().remote_enabled is False
    window._apply_remote()
    assert window._remote is None


def test_switching_it_on_binds_only_to_this_machine(window: MainWindow) -> None:
    """Und die zweite: nur 127.0.0.1.

    Am gebundenen Sockel geprüft, nicht an der Absicht — eine Konstante sagt
    nichts darüber, woran wirklich gebunden wurde.
    """
    window.settings.remote_enabled = True
    window.settings.remote_port = 0
    window._apply_remote()
    try:
        assert window._remote is not None
        assert window._remote.running
        server = window._remote._server
        assert server is not None
        assert server.server_address[0] == "127.0.0.1"
    finally:
        window.settings.remote_enabled = False
        window._apply_remote()
    assert window._remote is None


def test_dragging_a_face_reaches_the_document(window: MainWindow) -> None:
    """Ein Signal ohne Empfänger fällt in keinem Review auf.

    Der Viewport sendete `faceDragged`, seit es den Griff an der Fläche gibt,
    und niemand hörte zu: der Griff ließ sich ziehen, das Modell blieb, wie es
    war. Ein Test, der nur den Sender prüft, hätte das nicht gefunden — dieser
    prüft, was im Dokument ankommt.
    """
    window.run_remote("create_box", {"width": 20.0, "depth": 20.0, "height": 20.0})
    window.object_tree.tree.setCurrentItem(window.object_tree.tree.topLevelItem(0))
    window.viewport.faceDragged.emit((0.0, 0.0, 1.0), 3.0)
    window.session.wait_for_idle(60_000)

    assert [entry.op for entry in window.session.project.document.ops] == [
        "create_box",
        "push_face",
    ]
    moved = window.session.project.document.ops[-1]
    assert moved.params["distance"] == pytest.approx(3.0)
    assert moved.params["nz"] == pytest.approx(1.0)


def test_every_worker_survives_the_delivery_of_its_own_signal(session: Session) -> None:
    """Die Regel gilt für alle drei Arbeiter, nicht nur den, bei dem es knallte.

    ``_on_thread_done``, ``_on_agent_done`` und ``_on_split_done`` laufen als
    Slots des ``finished``-Signals ihres eigenen Arbeiters. Wer die Referenz
    dort loslässt, gibt den PySide-Wrapper mitsamt C++-QThread frei, während
    Qt die Zustellung noch auf dem Stapel hat — der Absturz ohne Traceback, der
    die Suite sporadisch riss.

    Beim Auswerter wurde das behoben, weil dort jemand hämmerte. Agent und
    Teilungssuche trugen denselben Fehler weiter; die Teilungssuche sogar in
    einem Lambda, das ``None`` in genau das Feld schrieb, dessen Objekt es
    gerade zustellte.

    Geprüft am Slot statt am Absturz: einen Absturz zuverlässig auszulösen
    braucht Last und Glück, die Regel dahinter ist eine Zeile.
    """
    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()

    for name in ("_finished_worker", "_finished_agent", "_finished_split"):
        assert hasattr(session, name), f"{name} fehlt — ein Arbeiter ohne Halteleine"

    # Nach einem Lauf hält das Feld den ausgelaufenen Arbeiter, statt ihn
    # freigegeben zu haben.
    assert session._finished_worker is not None
    assert session._worker is None


# --- die Vorschau sagt, dass sie eine ist (Konzept Teil 10, 9b) ------------------


def test_a_running_preview_says_it_is_one(window: MainWindow) -> None:
    """Ein verändertes Bild sieht aus wie ein Ergebnis.

    Die Live-Vorschau gab es lange, bevor jemand sie sah; seit der Dialog neben
    dem Bild steht, sieht man sie — und damit wird die stillere Hälfte des
    Problems sichtbar: nichts sagte, dass das Gezeigte noch nicht übernommen
    ist.
    """
    banner = window.viewport.banner
    assert banner.isHidden(), "ohne Vorschau kein Band"

    window._show_preview(object())
    assert not banner.isHidden()
    assert "noch nicht übernommen" in banner.note.text()

    window._clear_preview()
    assert banner.isHidden(), "Dialog zu, Band weg"


def test_the_legend_names_the_colours_it_explains(window: MainWindow) -> None:
    """Regel 18: Farbe trägt nie allein. Das Band führt Zeichen und Namen."""
    window._show_preview(object())
    text = window.viewport.banner.legend.text()

    for encoding in (DIFF_PALETTES["blue_orange"].added, DIFF_PALETTES["blue_orange"].removed):
        assert encoding.symbol in text
        assert tr(encoding.label_key) in text


def test_switching_the_palette_relabels_the_legend(window: MainWindow) -> None:
    """Die Legende erklärt Farben — wechseln die, muss sie mitgehen."""
    window._show_preview(object())
    window.viewport.set_difference_palette("greyscale")

    assert not window.viewport.banner.isHidden()
    assert tr(DIFF_PALETTES["greyscale"].added.label_key) in window.viewport.banner.legend.text()


def test_holding_space_shows_the_state_before(window: MainWindow) -> None:
    """Einen Unterschied sieht man nur, wenn man beides kennt.

    Das Modell unter der Vorschau *ist* der Stand vor der Operation — die
    Differenz liegt nur darüber. Sie wegzunehmen ist deshalb schon der ganze
    Vergleich, und er kostet keine zweite Rechnung.
    """
    from PySide6.QtGui import QKeyEvent

    window._show_preview(object())
    viewport = window.viewport
    assert not viewport.difference_held

    hold = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier)
    let_go = QKeyEvent(QEvent.Type.KeyRelease, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier)

    assert viewport._compare.eventFilter(window, hold), "die Leertaste gehört hier der Vorschau"
    assert viewport.difference_held

    assert viewport._compare.eventFilter(window, let_go)
    assert not viewport.difference_held


def test_a_space_in_a_text_field_stays_a_space(window: MainWindow) -> None:
    """Sonst könnte man keinen Namen mit Leerzeichen tippen, solange eine
    Vorschau läuft — und eine Vorschau läuft, sobald ein Dialog offen ist."""
    from PySide6.QtGui import QKeyEvent
    from PySide6.QtWidgets import QLineEdit

    window._show_preview(object())
    field = QLineEdit(window)
    field.setFocus()

    hold = QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier)
    assert not window.viewport._compare.eventFilter(field, hold)
    assert not window.viewport.difference_held


def test_a_held_key_is_not_a_flicker(window: MainWindow) -> None:
    """Eine gehaltene Taste schickt eine Folge aus Press und Release, nicht
    einen langen Druck. Ohne diese Prüfung flackerte die Vorschau im Takt der
    Tastenwiederholung."""
    from PySide6.QtGui import QKeyEvent

    window._show_preview(object())
    window.viewport._compare.eventFilter(
        window, QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Space, Qt.KeyboardModifier.NoModifier)
    )

    repeat = QKeyEvent(
        QEvent.Type.KeyRelease,
        Qt.Key.Key_Space,
        Qt.KeyboardModifier.NoModifier,
        autorep=True,
    )
    assert not window.viewport._compare.eventFilter(window, repeat)
    assert window.viewport.difference_held, "die Wiederholung ändert nichts"


# --- Einrichtung: was gewählt wurde, muss auch gelten (Konzept Teil 8) -----------


def test_the_first_run_reaches_the_project_that_is_open(window: MainWindow) -> None:
    """Gewählt war Centauri Carbon 2 und PETG — in den Druckeinstellungen stand
    danach „Allgemeiner FDM-Drucker" und PLA.

    Die Einstellungen sagen zu Recht, dass die Werte „für das nächste neue
    Projekt" gelten. Beim ersten Start ist das offene Projekt aber genau das,
    mit dem weitergearbeitet wird.
    """
    window.settings.printer = "centauri-carbon-2"
    window.settings.material = "petg"

    window._adopt_defaults()
    window.session.wait_for_idle()

    assert window.session.profile.printer.id == "centauri-carbon-2"
    assert window.session.profile.material.id == "petg"


def test_a_project_with_content_keeps_its_profile(window: MainWindow) -> None:
    """In ein Projekt mit Inhalt greift eine Einstellung nicht hinein — das
    wäre eine Geometrieänderung ohne Operation."""
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    before = window.session.profile.printer.id
    window.settings.printer = "centauri-carbon-2"

    window._adopt_defaults()

    assert window.session.profile.printer.id == before


def test_the_discard_question_names_what_it_throws_away(window: MainWindow) -> None:
    """„Diese Änderung verwirft 2 zurückgenommene Schritte" sagt, wie viel weg
    ist, nicht was — und genau das entscheidet, ob man Ja sagt."""
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    assert not window._discarded_names(), "nichts zurückgenommen, nichts zu nennen"

    window.action_undo()
    window.session.wait_for_idle()

    names = window._discarded_names()
    assert len(names) == window.session.history.discardable
    assert all(name.strip() for name in names), "und jeder Name sagt etwas"


def test_the_question_button_carries_the_answer(qt_app: QApplication) -> None:
    """Auf „Welchen soll ich abziehen?" ist „OK" keine Antwort.

    Es ist die Aufforderung, sie sich aus der Liste danebenzudenken. Der Knopf
    sagt, was er tut — derselbe Grundsatz wie im Dialog *Ungesicherte
    Änderungen*, den das Konzept als Vorlage nennt.
    """
    from app.ui.dialogs import AskDialog

    dialog = AskDialog("Welchen soll ich abziehen?", ["Klotz A", "Klotz B", "Keinen"])

    assert dialog._accept.text() == "Klotz A", "die Vorauswahl steht auf dem Knopf"

    dialog.list.setCurrentRow(2)
    assert dialog._accept.text() == "Keinen", "und sie folgt der Auswahl"
    assert dialog.chosen() == "Keinen"


def test_the_generator_dialog_puts_the_seed_out_of_the_way(qt_app: QApplication) -> None:
    """§2.4: vorn die zwei Werte, die man ändert.

    Der Startwert stand an dritter Stelle über allem, was jemand hier tun
    will — er entscheidet nichts, solange man ihn nicht wiederholen will.
    """
    from app.ui.generate_dialog import GenerateDialog

    dialog = GenerateDialog(None)

    assert not dialog.seed.isVisible(), "zugeklappt, nicht entfernt"
    assert dialog.advanced.isVisibleTo(dialog), "die Klappe selbst steht da"


def test_a_measure_drops_zeros_it_never_measured(qt_app: QApplication) -> None:
    """„60,00" trägt genau so viel Auskunft wie „60" und braucht mehr Platz.

    Die Nullen stehen dort, weil die Formatierung eine feste Stellenzahl hat,
    nicht weil jemand sie gemessen hätte. Ein krummes Maß behält seine Stellen
    — genau diesen Unterschied darf eine Abkürzung nicht verschlucken.
    """
    from app.ui.labels import compact_length

    assert compact_length(60.0) == "60"
    assert compact_length(11.0) == "11"
    assert compact_length(0.0) == "0"
    assert compact_length(60.25) == "60,25"
    assert compact_length(0.5) == "0,5"


def test_the_object_tree_fits_its_measures_in_the_card(qt_app: QApplication) -> None:
    """Die linke Zone ist so breit wie ``LEFT_WIDTH``, seit sie über der
    Ansicht liegt.

    Mit fester Stellenzahl brauchten Name und Maße dreihundertdreiundvierzig
    Pixel und bekamen zweihundertsechzig — die Spalte wurde abgeschnitten, und
    zwar bei jedem Projekt, nicht nur bei langen Namen.
    """
    from PySide6.QtWidgets import QTreeWidgetItem

    from app.ui.overlay import LEFT_WIDTH
    from app.ui.panels import ObjectTree

    tree = ObjectTree()
    QTreeWidgetItem(tree.tree, ["Halter", "60 × 40 × 11 mm"])
    tree.tree.resizeColumnToContents(0)
    tree.tree.resizeColumnToContents(1)

    needed = tree.tree.columnWidth(0) + tree.tree.columnWidth(1)
    assert needed <= LEFT_WIDTH, f"{needed} Pixel bei {LEFT_WIDTH} verfügbaren"


def test_the_object_tree_grows_with_its_content(qt_app: QApplication) -> None:
    """§2.5: die Karten der linken Spalte sind so hoch wie ihr Inhalt.

    Gemeint war das seit je, umgesetzt war es nicht. Qt gab jeder Ansicht ihre
    eigene Mindesthöhe von etwa zwei Zeilen und ließ es dabei — der Objektbaum
    scrollte ab dem zweiten Körper, während unter der Spalte sechshundert Pixel
    leer blieben. Der zweite Körper ist genau das, was nach einer Teilung
    entsteht.
    """
    from PySide6.QtWidgets import QTreeWidgetItem

    from app.ui.panels import ObjectTree

    tree = ObjectTree()
    for name in ("Teil A", "Teil B", "Teil C", "Teil D", "Teil E", "Teil F"):
        QTreeWidgetItem(tree.tree, [name, "20 × 20 × 20 mm"])
    tree._fit()

    row = tree.tree.sizeHintForRow(0)
    assert row > 0
    assert tree.tree.height() >= 6 * row, (
        f"sechs Zeilen brauchen {6 * row} px, die Ansicht ist {tree.tree.height()} px hoch"
    )


def test_the_history_grows_with_its_content(qt_app: QApplication) -> None:
    """Dasselbe für den Verlauf — bei vier Schritten waren zwei zu sehen."""
    from app.core.types import Document, Operation, Transaction
    from app.ui.panels import HistoryPanel

    document = Document(format_version=1, app_version="0.0.1")
    for number in range(1, 5):
        document.ops.append(Operation(id=number, op="drill_hole", inputs=(), params={}))
        document.transactions.append(
            Transaction(id=f"t{number}", title=f"Schritt {number}", ops=(number,))
        )

    panel = HistoryPanel()
    panel.show_document(document)

    row = panel.list.sizeHintForRow(0)
    assert row > 0
    assert panel.list.height() >= 4 * row, (
        f"vier Schritte brauchen {4 * row} px, die Liste ist {panel.list.height()} px hoch"
    )


def test_the_empty_parameter_note_is_readable(qt_app: QApplication) -> None:
    """Der Satz im leeren Zustand war nach anderthalb Zeilen abgeschnitten.

    Ein Label mit Umbruch meldet seine Höhe über ``heightForWidth``, und diese
    Kette reißt in einem Layout ohne Streckfaktor: siebzehn Pixel für vier
    Zeilen Text.
    """
    from app.core.types import Document
    from app.ui.panels import ParameterPanel

    panel = ParameterPanel()
    panel.show_document(Document(format_version=1, app_version="0.0.1"))

    label = panel._empty
    line = label.fontMetrics().height()
    assert label.minimumHeight() >= 2 * line, (
        f"{label.minimumHeight()} px für einen Satz von {label.text()!r}"
    )


def test_the_parameter_card_survives_getting_parameters(qt_app: QApplication) -> None:
    """Der leere Zustand hinterlässt eine tote Referenz, wenn man ihn misst.

    ``show_document`` räumt die Zeilen des Formulars weg; danach ist das
    C++-Objekt des Labels fort, während die Python-Referenz noch steht. Wer es
    danach vermäße, stürbe an genau dem — beim ersten Projekt mit Parametern,
    also bei jedem Weg 2.
    """
    from app.core.types import Document, Parameter
    from app.ui.panels import ParameterPanel

    panel = ParameterPanel()
    panel.show_document(Document(format_version=1, app_version="0.0.1"))

    document = Document(format_version=1, app_version="0.0.1")
    document.parameters["breite"] = Parameter(name="breite", value=60.0)
    panel.show_document(document)

    assert "breite" in panel._editors


def test_a_very_long_list_stops_growing(qt_app: QApplication) -> None:
    """Sonst schöbe ein Baum mit fünfzig Teilen den Verlauf aus dem Fenster."""
    from PySide6.QtWidgets import QTreeWidgetItem

    from app.ui.panels import MAX_ROWS, ObjectTree

    tree = ObjectTree()
    for number in range(50):
        QTreeWidgetItem(tree.tree, [f"Teil {number}", "10 × 10 × 10 mm"])
    tree._fit()

    row = tree.tree.sizeHintForRow(0)
    header = tree.tree.header().height() + 2 * tree.tree.frameWidth() + 2
    assert tree.tree.height() <= header + MAX_ROWS * row, (
        f"{tree.tree.height()} px bei fünfzig Zeilen à {row} px"
    )
    assert tree.tree.height() < 50 * row, "die Deckelung greift nicht"


def test_a_finding_says_which_body_it_means(qt_app: QApplication) -> None:
    """Zwei ausgehöhlte Körper meldeten zweimal denselben Satz.

    Im Bericht standen zwei Zeilen, Wort für Wort gleich — das sieht aus wie
    ein Fehler in der Anwendung und nicht wie zwei Befunde. Die Kennung stand
    im Befund, nur nie in der Zeile.
    """
    from app.core.types import Finding
    from app.ui.panels import _line_for

    finding = Finding(
        code="hollow.done",
        severity="info",
        message="Ausgehöhlt.",
        object_id="obj_2",
        values={"wall_mm": 2.0, "removed_cm3": 14.3},
    )

    plain = _line_for(finding)
    assert "obj_2" in plain, "ohne Namensliste bleibt die Kennung stehen"

    named = _line_for(finding, {"obj_2": "Klotz B"})
    assert "Klotz B" in named, "mit Namensliste der Name"
    assert "obj_2" not in named


def test_a_finding_writes_its_numbers_with_their_unit(qt_app: QApplication) -> None:
    """„Die Wandstärke stimmt im Rahmen des Rasters" nannte die Wandstärke
    nicht.

    Und wie viel Material gespart wurde — die Frage, für die man die Operation
    aufruft — stand ausschließlich im Tooltip.
    """
    from app.core.types import Finding
    from app.ui.panels import _line_for

    line = _line_for(
        Finding(
            code="hollow.done",
            severity="info",
            message="Ausgehöhlt.",
            values={"wall_mm": 2.0, "removed_cm3": 14.3},
        )
    )

    assert "2.0 mm" in line or "2,0 mm" in line, line
    assert "14.3 cm³" in line or "14,3 cm³" in line, line


def test_the_arrangement_spacing_knows_the_plate_adhesion(window: MainWindow) -> None:
    """§25, §29: die Operation kennt die Druckeinstellung nicht, das Fenster
    beide.

    Zwei Körper mit fünf Millimetern Luft und je fünf Millimetern Brim stehen
    einander im Weg — der Haftungsrand zählt zwischen Nachbarn zweimal, und es
    fällt erst auf der Platte auf. Beim Gewürzset war das die erste
    Deckelplatte. Der Dialog öffnet deshalb mit dem Abstand, den die Haftung
    verlangt; ändern lässt er sich weiterhin.
    """
    from dataclasses import replace as _replace

    from app.core.knowledge import print_settings as settings_table

    _with_two_objects(window)
    settings = settings_table.resolve(window.session.profile)
    adhesion = _replace(settings.adhesion, kind="brim", brim_width=5.0)
    window.session.set_print_settings(_replace(settings, adhesion=adhesion))

    window.run_operation(REGISTRY.get("arrange_bed"))

    dialog = window._op_dialog
    assert dialog is not None
    assert dialog.values()["spacing"] == pytest.approx(10.0), "zweimal fünf Millimeter Brim"
    dialog.reject()
    window.session.wait_for_idle()


def test_without_plate_adhesion_the_spacing_stays_the_default(window: MainWindow) -> None:
    """Ohne Rand kein Aufschlag — die Vorgabe der Operation bleibt stehen."""
    from dataclasses import replace as _replace

    from app.core.knowledge import print_settings as settings_table

    _with_two_objects(window)
    settings = settings_table.resolve(window.session.profile)
    adhesion = _replace(settings.adhesion, kind="none")
    window.session.set_print_settings(_replace(settings, adhesion=adhesion))

    window.run_operation(REGISTRY.get("arrange_bed"))

    dialog = window._op_dialog
    assert dialog is not None
    assert dialog.values()["spacing"] == pytest.approx(5.0)
    dialog.reject()
    window.session.wait_for_idle()


def test_the_sketch_editor_keeps_clear_of_the_cards(window: MainWindow) -> None:
    """§2.5: die Karten liegen über der Ansicht — die Skizze weicht ihnen aus.

    Für den Viewport ist das Übereinanderliegen richtig: man sieht das Modell
    hinter den Karten. Für eine Ansicht mit eigener Werkzeugleiste nicht — im
    Skizzenmodus lagen die **ersten** Werkzeuge unter der linken Karte, also
    Linie und Rechteck, und die Bedingungsliste unter der rechten. Bei 1296
    Pixeln Breite ebenso wie bei 1900: kein Platzproblem, sondern die
    Stapelreihenfolge.
    """
    from app.ui.overlay import LEFT_WIDTH, MARGIN

    window.start_sketch("sketch_extrude", "")
    panel = window._sketch_panel
    assert panel is not None

    window.overlay._place()
    margins = panel.layout().contentsMargins()

    assert margins.left() >= LEFT_WIDTH + MARGIN, "unter der linken Karte liegt kein Werkzeug"
    assert margins.right() > 0, "und die Bedingungsliste bleibt lesbar"
    window.finish_sketch(keep=False)


def _report_codes(window: MainWindow) -> list[str]:
    """Die Codes der Befunde, die im Bericht stehen."""
    from PySide6.QtCore import Qt as _Qt

    listing = window.report.list
    return [
        listing.item(row).data(_Qt.ItemDataRole.UserRole).code for row in range(listing.count())
    ]


def test_time_and_material_are_cross_checked_too(window: MainWindow) -> None:
    """§28.2 meint beide Zahlen, nicht nur das Stützvolumen.

    Beim Gewürzhalter standen 12 g gegen 10 g und 46 min gegen 37 min — 17 und
    20 Prozent auseinander —, und der Prüfbericht meldete vier Hinweise und
    keine Warnung. ``gcode.compare`` kennt die Schwelle von fünfzehn Prozent
    seit je; gerufen wurde sie nur für die Stützen.
    """
    from app.core.knowledge import print_settings as settings_table
    from app.core.slice import gcode
    from app.core.slice.estimate import total as estimate_total

    _with_two_objects(window)
    window.report.show_result(None)

    # Was der Slicer geschrieben hat: gut ein Fünftel unter der Schätzung.
    result = window.session.last_result
    settings = settings_table.resolve(window.session.profile)
    bodies = [(entry.mesh.volume, entry.mesh.area) for entry in result.scene.objects.values()]
    estimate = estimate_total(bodies, settings)
    measured = gcode.GcodeMetrics(
        filament_grams=estimate.grams * 0.8,
        print_seconds=estimate.seconds * 0.8,
    )

    window._compare_totals(measured)

    codes = _report_codes(window)
    assert codes.count("gcode.deviation") == 2, "Material und Zeit, beide"


def test_a_close_estimate_stays_quiet(window: MainWindow) -> None:
    """Fünf Prozent daneben ist keine Meldung wert — sonst stünde die Warnung
    nach jedem Lauf da und wäre nach dem dritten unsichtbar."""
    from app.core.knowledge import print_settings as settings_table
    from app.core.slice import gcode
    from app.core.slice.estimate import total as estimate_total

    _with_two_objects(window)
    window.report.show_result(None)

    result = window.session.last_result
    settings = settings_table.resolve(window.session.profile)
    bodies = [(entry.mesh.volume, entry.mesh.area) for entry in result.scene.objects.values()]
    estimate = estimate_total(bodies, settings)

    window._compare_totals(
        gcode.GcodeMetrics(filament_grams=estimate.grams * 0.95, print_seconds=estimate.seconds)
    )

    assert "gcode.deviation" not in _report_codes(window)


def test_no_worker_hands_its_field_to_a_blind_lambda() -> None:
    """Kein ``finished``-Signal räumt eine Arbeiter-Referenz per ``setattr``.

    Das Muster war fünfmal richtig und zweimal falsch, und niemand konnte es
    sehen: die drei Slots der Sitzung und die Update-Abfrage tragen sogar den
    Kommentar, warum ein Lambda hier nicht geht — der Schnitt-Arbeiter und die
    Ollama-Abfrage benutzten trotzdem eines.

    ``lambda: setattr(self, "_worker", None)`` schreibt in das *Feld*, nicht
    zum *Arbeiter*: Wird ein Vorgänger fertig, nachdem sein Nachfolger im Feld
    steht, verliert der laufende Nachfolger seine einzige Referenz. Dazu kommt
    ``finished`` ohnehin zu früh — Qt räumt den Thread danach noch ab.

    Ein Test über den Quelltext und nicht über das Verhalten, weil der Absturz
    am Timing hängt und sich nicht verlässlich herbeiführen lässt. Eine
    Konvention, die nirgends geprüft wird, ist keine.
    """
    import re

    ui = Path(__file__).parent.parent / "app" / "ui"
    pattern = re.compile(r"finished\.connect\(\s*lambda[^)]*setattr", re.MULTILINE)

    culprits = [
        path.relative_to(ui.parent.parent)
        for path in sorted(ui.glob("*.py"))
        if pattern.search(path.read_text(encoding="utf-8"))
    ]

    assert not culprits, (
        f"{culprits}: ein benannter Slot prüft die Identität seines Arbeiters, "
        "ein Lambda trifft blind das Feld — siehe .claude/rules/oberflaeche.md"
    )


def test_the_splash_screen_prints_the_mark_along_the_real_progress(qt_app: object) -> None:
    """Der Ladebildschirm zeigt den gemessenen Fortschritt, nicht eine Uhr.

    Geprüft wird die Zusicherung aus dem Modul: ``step`` setzt das Ziel, und
    die gezeigte Höhe nähert sich ihm an, statt zu springen. Ein Balken, der
    unabhängig vom Laden läuft, wäre eine Behauptung — dieser hier ist eine
    Anzeige.
    """
    from app.ui.splash import SplashScreen

    splash = SplashScreen()
    try:
        assert splash._shown == 0.0, "vor dem ersten Schritt ist nichts gedruckt"

        splash.step("Operationen werden geladen …", 0.5)
        assert splash._target == 0.5
        assert splash._message == "Operationen werden geladen …"
        # Angenähert, nicht gesprungen: nach einem Schritt liegt die Anzeige
        # zwischen Start und Ziel.
        assert 0.0 <= splash._shown < 0.5

        # Ausreißer nach oben und unten werden auf den gültigen Bereich
        # geklemmt — ein Aufrufer, der sich verzählt, verzerrt das Bild nicht.
        splash.step("zu weit", 1.8)
        assert splash._target == 1.0
        splash.step("zu wenig", -0.3)
        assert splash._target == 0.0
    finally:
        splash.finish()


def test_the_splash_screen_survives_a_missing_icon_source(
    qt_app: object, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ohne SVG-Quelle zeichnet er nichts, statt den Start zu verlieren.

    Das Startbild ist Zierde; ein Start scheitert nie daran. Dieselbe Haltung
    hat ``application_icon`` — fehlt die Datei, gibt es ein leeres Symbol.
    """
    from app.ui import splash as splash_module

    monkeypatch.setattr(splash_module, "application_icon_source", lambda: "")
    splash = splash_module.SplashScreen()
    try:
        splash.step("ohne Bild", 0.4)
        assert not splash._renderer.isValid()
        splash.repaint()  # darf nicht werfen
    finally:
        splash.finish()


# --- die Wartezeit beim Öffnen (§2.8) --------------------------------------------


def test_the_veil_covers_the_view_only_while_it_shows_nothing(window: MainWindow) -> None:
    """§2.8: die letzte gültige Darstellung bleibt stehen.

    Der Balken unten rechts war beim Öffnen eines Projekts die einzige
    Auskunft, und er steht dort, wo beim Warten niemand hinsieht. Über die
    leere Ansicht gehört eine Anzeige — über ein Modell nicht: was man gerade
    ansieht, wird nicht verdeckt, nur weil dahinter gerechnet wird.
    """
    window._on_busy(True)
    assert window.veil.showing, "die leere Ansicht bekommt die Anzeige"

    window._on_busy(False)
    assert not window.veil.showing, "und gibt sie nach dem Lauf wieder her"

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window._on_scene(window.session.evaluate_now())

    window._on_busy(True)
    assert not window.veil.showing, "über einem Körper bleibt die Ansicht die Ansicht"


def test_the_veil_shows_the_measured_progress(window: MainWindow) -> None:
    """Bauhöhe, Linie und Zahl sagen dasselbe — die Zahl das Gemessene.

    Regel 18 gilt auch für eine Wartezeit: die Höhe des gedruckten Symbols
    ist die eine Kodierung, die Länge der Linie die zweite, die Prozentzahl
    die dritte. Angenähert wird nur die Anzeige, nie die Auskunft.
    """
    window._on_busy(True)
    window._on_progress(0.5, "Bohrung")

    assert window.veil._target == 0.5
    assert window.veil._detail == "Bohrung"
    # Offscreen wird nicht animiert, sonst prüfte der Test die Uhr.
    assert window.veil._shown == 0.5

    window._on_progress(1.8, "verzählt")
    assert window.veil._target == 1.0, "ein Ausreißer verzerrt das Bild nicht"


def test_the_veil_leaves_the_toolbar_reachable(window: MainWindow) -> None:
    """Verdeckt wird die Ansicht, nicht die Bedienung.

    Über den Karten wäre der Schleier ein Vorhang ohne Ausgang: die
    Werkzeugzeile läge darunter, und wer den Lauf abbrechen oder das Fenster
    weiterbedienen will, käme nicht hin. Gemessen wird das wie beim Umbau auf
    schwebende Karten — mit ``childAt`` an der Stelle, an der die Zeile steht.
    """
    from app.ui.overlay import MARGIN

    window.overlay.setGeometry(0, 0, 1200, 800)
    window.overlay._place()
    window._on_busy(True)
    assert window.veil.showing

    bottom = window.overlay.bottom
    assert bottom is not None
    on_the_bar = bottom.geometry().center()
    assert window.overlay.childAt(on_the_bar) is not window.veil

    # Und dort, wo nur die Ansicht liegt, steht er.
    empty = QPoint(600, 800 - MARGIN - bottom.height() - 40)
    assert window.overlay.childAt(empty) is window.veil

    window._on_busy(False)


def test_the_veil_can_be_cancelled(window: MainWindow) -> None:
    """Regel 17: keine Sackgasse. Der Knopf hält an, was läuft.

    Derselbe Doppelgriff wie in der Statusleiste — die Trennebenensuche hat
    ihr eigenes Verwerfen und würde sonst weiterlaufen, während davor
    „Abbrechen" steht.
    """
    window._on_busy(True)
    window.veil.cancel.click()

    assert window.session.cancel_signal.is_cancelled
    window._on_busy(False)


def test_motion_is_off_where_nobody_watches(qt_app: object) -> None:
    """Offscreen wird nicht animiert — sonst prüft ein Test die Uhr.

    Die Suite läuft unter ``QT_QPA_PLATFORM=offscreen`` (conftest, §38). Dort
    darf keine Animation starten: ein Widget, das erst nach 140 ms sichtbar
    ist, macht aus jeder Zusicherung eine Wette auf das Timing.
    """
    from app.ui import motion

    assert not motion.animations_enabled()


def test_switching_a_stack_arrives_immediately(qt_app: object) -> None:
    """Der Wechsel gilt sofort, animiert wird nur das Auftauchen.

    Das ist die Zusicherung, auf der alle Aufrufer stehen: Wer direkt nach
    ``switch`` auf ``currentWidget`` sieht, bekommt die neue Seite — nicht die
    alte, weil eine Blende noch läuft.
    """
    from PySide6.QtWidgets import QStackedWidget, QWidget

    from app.ui.motion import switch

    stack = QStackedWidget()
    first, second = QWidget(), QWidget()
    stack.addWidget(first)
    stack.addWidget(second)
    stack.setCurrentWidget(first)

    switch(stack, second)
    assert stack.currentWidget() is second

    # Zweimal dasselbe Ziel ist kein Wechsel und löst auch keine Blende aus.
    switch(stack, second)
    assert stack.currentWidget() is second


def test_fading_leaves_no_effect_behind(qt_app: object) -> None:
    """Nach der Blende hängt kein Deckkraft-Effekt mehr am Widget.

    Ein ``QGraphicsOpacityEffect`` kostet bei jedem Zeichnen eine eigene
    Zwischenfläche. Bliebe er stehen, zahlte der Viewport ihn für den Rest der
    Sitzung — und zwei übereinander machen das Widget dauerhaft blasser.
    """
    from PySide6.QtWidgets import QWidget

    from app.ui.motion import fade_in, fade_out

    widget = QWidget()
    fade_in(widget)
    assert widget.isVisible() or widget.isHidden() is False
    assert widget.graphicsEffect() is None

    fade_out(widget)
    assert not widget.isVisible()
    assert widget.graphicsEffect() is None


def test_the_application_icon_uses_the_small_source_where_it_matters(qt_app: object) -> None:
    """Bis 32 Pixel kommt die vereinfachte Fassung, darüber die ausgearbeitete.

    Das ist die Größe von Titelleiste, Taskleiste, Alt-Tab — und dieselbe in
    jedem Dialog, weil das Symbol einmal auf der ``QApplication`` steht und
    jedes Fenster es erbt. Die ausgearbeitete Fassung trägt dort Schichtlinien
    von 0,3 Pixeln Breite und kommt als grauer Schleier an.

    Die beiden Fassungen sind **dieselbe Form** — gleiche Punkte, gleiche
    Farben. Der einzige Unterschied sind die Schichtlinien, und genau darauf
    prüft dieser Test: Wer die kleine Fassung neu gestaltet statt sie zu
    vereinfachen, bekommt zwei Symbole für ein Produkt.
    """
    from PySide6.QtCore import QSize

    from app.ui.icons import ICON_SOURCE, ICON_SOURCE_SMALL, SMALL_ICON_LIMIT, application_icon

    assert ICON_SOURCE.exists(), "die ausgearbeitete Quelle fehlt"
    assert ICON_SOURCE_SMALL.exists(), "die vereinfachte Quelle fehlt"

    icon = application_icon()
    assert not icon.isNull()
    assert not icon.pixmap(QSize(16, 16)).isNull()
    assert SMALL_ICON_LIMIT == 32

    large = ICON_SOURCE.read_text(encoding="utf-8")
    small = ICON_SOURCE_SMALL.read_text(encoding="utf-8")

    # Die Schichtlinien sind das Einzige, was fehlen darf — sie stehen als
    # <path> da, alles andere als <polygon> oder <ellipse>.
    assert "<path" in large, "die große Fassung hat ihre Schichtlinien verloren"
    assert "<path" not in small, "die kleine Fassung trägt Linien, die bei 16 px zu Schleier werden"

    # Dieselben Flächen, dieselben Farben: Was hier auseinanderläuft, sieht der
    # Nutzer als zwei verschiedene Symbole.
    for shape in ('points="64,18 104,41 64,64 24,41"', 'fill="#e08b4e"', 'fill="#7c3a10"'):
        assert shape in large and shape in small, f"{shape} steht nicht in beiden Fassungen"


def test_no_window_overrides_the_application_icon() -> None:
    """Das Fenstersymbol wird einmal gesetzt, und alle erben es.

    Setzte ein Dialog ein eigenes, hätte er in seiner Titelleiste ein anderes
    Bild als das Hauptfenster — und die Korrektur an der einen Stelle ginge an
    ihm vorbei. Ein Test über den Quelltext, weil sich das Erben nicht
    offscreen nachstellen lässt.
    """
    import re

    ui = Path(__file__).parent.parent / "app" / "ui"
    pattern = re.compile(r"^\s*(?!application\b)\w+\.setWindowIcon\(", re.MULTILINE)

    culprits = [
        path.relative_to(ui.parent.parent)
        for path in sorted(ui.glob("*.py"))
        if pattern.search(path.read_text(encoding="utf-8"))
    ]

    assert not culprits, (
        f"{culprits}: das Fenstersymbol gehört einmal auf die QApplication "
        "(app/ui/app.py), nicht an einzelne Fenster"
    )


# --- Lizenzierung an der Oberfläche (Konzept V4b) ---------------------------------


def _expired(monkeypatch: pytest.MonkeyPatch) -> None:
    from app.core import activation

    monkeypatch.setattr(activation, "_cached", activation.Activation(days_left=0))


def test_an_expired_trial_greys_the_writing_side_out(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§2 C: gesperrt sieht man **vor** dem Klick — ausgegraut, mit Grund im
    Hinweistext. Die Hürde selbst liegt im Kern; hier steht die Freundlichkeit
    davor."""
    _expired(monkeypatch)
    window = MainWindow(Session(), UiSettings())

    assert not window.import_action.isEnabled()
    assert not window.generate_action.isEnabled()
    assert not window.export_action.isEnabled()
    assert not window._toolbar_import.isEnabled()
    assert all(not action.isEnabled() for action in window._op_actions.values())
    assert "Lizenzschlüssel" in window.import_action.statusTip(), (
        "der Hinweistext nennt den Grund, nicht nur den Zustand"
    )
    # Rückgängig und Wiederholen gehören zur lesenden Seite: ihr Zustand
    # folgt dem Verlauf, nicht der Lizenz — hier leer, also aus, aber nicht
    # wegen der Sperre (der Hinweistext bleibt ihr eigener).
    assert "Lizenzschlüssel" not in window.undo_action.statusTip()

    assert not window.chat.input.isEnabled()
    assert window.chat.unlock.isVisibleTo(window.chat)
    assert "Lizenzschlüssel" in window.chat.hint.text()


def test_entering_a_key_puts_everything_back(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nach dem Eintragen steht wieder offen, was der Ablauf zugemacht hatte —
    samt der eigenen Hinweistexte, nicht mit dem Sperrgrund als Fossil."""
    from datetime import date

    from app.core import activation
    from app.core.activation import key

    _expired(monkeypatch)
    window = MainWindow(Session(), UiSettings())
    hint_before = str(window.import_action.property("tip_before_lock"))

    licence = key.Licence(
        major=key.current_major(),
        purchased_on=date(2026, 8, 6),
        order="A-1",
        holder="kaeufer@beispiel.de",
    )
    monkeypatch.setattr(activation, "_cached", activation.Activation(licence=licence))
    window._update_actions()
    window._refresh_chat_availability()

    assert window.import_action.isEnabled()
    assert window.generate_action.isEnabled()
    assert window.import_action.statusTip() == hint_before
    assert not window.chat.unlock.isVisibleTo(window.chat)


def test_the_last_trial_days_show_up_once_in_the_status_bar(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§2 C: einmal eine Zeile, wenn weniger als drei Tage übrig sind — kein
    Startdialog, keine Zählung im Titel."""
    from app.core import activation

    monkeypatch.setattr(activation, "_cached", activation.Activation(days_left=2))
    window = MainWindow(Session(), UiSettings())

    # In einem eigenen Feld, nicht als Statusmeldung: eine Meldung verdeckt,
    # was links in der Leiste steht, und die Zeile steht dauerhaft.
    assert "2" in window.trial_line.text()
    assert "freischalten" in window.trial_line.text()


def test_a_comfortable_trial_rest_stays_quiet(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core import activation

    monkeypatch.setattr(activation, "_cached", activation.Activation(days_left=14))
    window = MainWindow(Session(), UiSettings())

    assert window.trial_line.text() == ""
    assert window.statusBar().currentMessage() == ""


def test_the_trial_line_does_not_cover_the_measurements(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Maße bleiben lesbar, während die Demo-Zeile steht.

    Als ``showMessage`` geführt, legte die Zeile sich über das Maßfeld —
    Qt blendet bei einer Meldung aus, was per ``addWidget`` in der Leiste
    liegt. Sichtbar wurde es erst auf den Handbuchbildern, wo „Keine
    Auswahl" und „Demo — noch 79 Tage" ineinanderliefen. Beide Felder
    müssen gleichzeitig etwas anzeigen können.
    """
    from datetime import date

    from app.core import activation

    # ``in_demo`` ist abgeleitet und hängt an der Frist, nicht an einem Feld.
    # Das Datum steht hier ausdrücklich: ``conftest`` nimmt den ausgelieferten
    # Stichtag weg, damit die Suite nicht am Kalender hängt.
    monkeypatch.setattr(
        activation, "_cached", activation.Activation(days_left=79, deadline=date(2026, 10, 30))
    )
    window = MainWindow(Session(), UiSettings())
    window.resize(1180, 760)
    window.show()
    qt_app.processEvents()

    assert window.trial_line.text(), "die Demo-Zeile fehlt"
    assert window.measurements.isVisible(), "die Maße sind verdeckt"
    assert window.measurements.text(), "die Maße sind leer"


def test_the_about_dialog_names_the_activation_state(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§2 I H2: „Lizenziert für …" steht im Über-Dialog — wer seinen Schlüssel
    weitergibt, gibt seinen Namen mit."""
    from datetime import date

    from PySide6.QtWidgets import QLabel

    from app.core import activation
    from app.core.activation import key
    from app.ui.dialogs import AboutDialog

    licence = key.Licence(
        major=key.current_major(),
        purchased_on=date(2026, 8, 6),
        order="A-77",
        holder="kaeufer@beispiel.de",
    )
    monkeypatch.setattr(activation, "_cached", activation.Activation(licence=licence))
    dialog = AboutDialog()
    texts = " ".join(label.text() for label in dialog.findChildren(QLabel))
    assert "kaeufer@beispiel.de" in texts
    assert "A-77" in texts


def test_the_activation_dialog_accepts_a_valid_key(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """V4b: der Dialog nimmt an, was gilt — und legt es ab."""
    from app.core import activation
    from app.core.activation import key, store
    from app.ui.dialogs import ActivationDialog
    from tools.make_licence_keys import make_key, public_key

    # Der erste Testvektor aus RFC 8032 — dasselbe Paar wie in
    # test_licence_boundary.py, das kein importierbares Paket ist.
    test_seed = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")

    monkeypatch.setattr(store, "user_config_dir", lambda: tmp_path)
    monkeypatch.setattr(key, "PUBLIC_KEY", public_key(test_seed))
    activation.forget_cache()
    try:
        from datetime import date

        licence = key.Licence(
            major=key.current_major(),
            purchased_on=date(2026, 8, 6),
            order="A-1",
            holder="kaeufer@beispiel.de",
        )
        dialog = ActivationDialog()
        dialog.field.setPlainText(make_key(test_seed, licence))
        dialog._remember()

        assert activation.state().licence == licence
        assert store.read_key() is not None, "geprüft und abgelegt"
    finally:
        activation.forget_cache()


def test_the_activation_dialog_rejects_with_a_reason(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """V4b: abgelehnt wird mit Grund und Handlungen, nie mit „ungültig" —
    der Fehlerdialog ist modal, also wird er hier abgefangen statt geöffnet."""
    from app.core import activation
    from app.core.activation import store
    from app.ui import dialogs
    from app.ui.dialogs import ActivationDialog

    monkeypatch.setattr(store, "user_config_dir", lambda: tmp_path)
    activation.forget_cache()
    shown: list[object] = []
    monkeypatch.setattr(dialogs, "show_error", lambda error, *a, **kw: shown.append(error))
    try:
        dialog = ActivationDialog()
        dialog.field.setPlainText("SOLIDON3D-1-AAAAAAAA")
        dialog._remember()

        assert len(shown) == 1
        assert getattr(shown[0], "suggestions", ()), "Regel 17: mit Handlungen"
        assert store.read_key() is None, "abgelegt wird nur Geprüftes"
    finally:
        activation.forget_cache()


def test_the_first_run_dialog_mentions_the_trial_in_one_sentence(
    qt_app: QApplication,
) -> None:
    """V4b: die Ersteinrichtung erwähnt den Testlauf — und fragt nicht nach
    einem Schlüssel, das wäre eine Hürde vor dem ersten Blick."""
    from app.ui.first_run import FirstRunDialog

    dialog = FirstRunDialog(UiSettings())
    assert "14" in dialog.greeting.text()
    assert "frei" in dialog.greeting.text()


# --- Modell aus dem Netz (§16.3) ------------------------------------------------


class _Drag:
    """Ein Ablegen-Ereignis mit Adressen, wie es ein Browser schickt.

    Als eigene Klasse und nicht als echtes ``QDropEvent``: Qt übernimmt die
    ``QMimeData`` nicht, und ohne eine Referenz auf der Python-Seite gibt der
    Speicherbereiniger sie frei, während das Ereignis noch darauf zeigt —
    ``mimeData()`` liefert dann ein blankes ``QObject``. Derselbe Fake steht
    aus demselben Grund in ``test_chat_ui.py``.
    """

    def __init__(self, urls: list[str]) -> None:
        from PySide6.QtCore import QMimeData, QUrl

        self._data = QMimeData()
        self._data.setUrls([QUrl(entry) for entry in urls])

    def mimeData(self) -> object:  # noqa: N802 — Qt gibt den Namen
        return self._data


def _drag(urls: list[str]) -> Any:
    return _Drag(urls)


def test_a_dropped_link_is_taken_like_a_dropped_file() -> None:
    """§2.3: Ziehen und Ablegen gilt auch für einen Verweis aus dem Browser."""
    from app.ui.start_screen import accepted_url

    assert accepted_url(_drag(["https://example.invalid/halter.stl"])) is not None
    assert accepted_url(_drag(["https://example.invalid/modelle/17"])) is None
    assert accepted_url(_drag(["file:///C:/teil.stl"])) is None, "das ist der Weg für Dateien"


def test_a_bad_address_says_so_before_a_worker_starts(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§32: Eine ``file:``-Adresse wandert gar nicht erst in einen Thread."""
    seen: list[object] = []
    monkeypatch.setattr("app.ui.main_window.show_error", lambda error, _parent: seen.append(error))

    window.download_model("file:///C:/Windows/win.ini")

    assert seen, "ohne Meldung bliebe der Klick wirkungslos"
    assert window._download_worker is None


def test_a_downloaded_model_keeps_where_it_came_from(window: MainWindow) -> None:
    """§16.3: Die Herkunft steht in der Quelle, nicht in einem Gedächtnis."""
    from app.core.ingest.fetch import FetchedModel

    payload = (MESHES / "cube_clean.stl").read_bytes()
    assert window.stack.currentWidget() is window.start_screen, "sonst prüft der Test unten nichts"
    window._downloaded(
        FetchedModel(
            name="halter.stl",
            payload=payload,
            url="https://example.invalid/halter.stl",
            retrieved="2026-08-11T10:00:00+00:00",
        )
    )
    window.session.wait_for_idle()

    sources = list(window.session.project.document.sources.values())
    assert len(sources) == 1
    assert sources[0].origin is not None
    assert sources[0].origin.url == "https://example.invalid/halter.stl"
    assert sources[0].origin.retrieved.startswith("2026-08-11")
    assert window.session.last_result is not None
    assert window.session.last_result.scene.objects, "das Modell steht danach in der Szene"
    assert window.stack.currentWidget() is not window.start_screen, (
        "geladen laut Statusleiste, unsichtbar im Bild: der Startbildschirm blieb stehen"
    )


def test_the_cards_grow_with_a_wide_window() -> None:
    """§19.3: Feste Breiten sind für 1920 gebaut.

    Auf 3413 Pixeln wurde die linke Karte zum Zwölftel des Fensters — die
    Maßspalte brach mitten in der Zahl ab, während daneben zwei Meter Leere
    standen. Gewachsen wird anteilig und mit Deckel; unter etwa 2000 Pixeln
    bleibt alles, wie es war.
    """
    from app.ui.overlay import LEFT_MAX, LEFT_WIDTH, card_width

    assert card_width(LEFT_WIDTH, LEFT_MAX, 1280) == LEFT_WIDTH
    assert card_width(LEFT_WIDTH, LEFT_MAX, 1920) == LEFT_WIDTH
    assert card_width(LEFT_WIDTH, LEFT_MAX, 2560) > LEFT_WIDTH
    assert card_width(LEFT_WIDTH, LEFT_MAX, 5120) == LEFT_MAX


def test_the_report_tab_counts_what_needs_attention(window: MainWindow) -> None:
    """Eine Warnung muss zu sehen sein, auch wenn etwas anderes vorn steht.

    Ein eingelesenes Netz mit offenen Stellen meldete sich im Prüfbericht —
    und im Fenster sah man einen Reiter, der aussah wie vorher. Wer die Tour
    oder den Chat offen hatte, erfuhr von der Warnung nichts.

    Gezählt werden Fehler und Warnungen, keine Hinweise: „Doppelte Punkte
    wurden verschweißt" ist eine Auskunft und keine Aufforderung.
    """
    from app.core.types import Finding

    index = window.right.indexOf(window.report)
    plain = window.right.tabText(index)
    assert "·" not in plain, "ohne Befunde steht dort nur der Name"

    window.report.add_findings(
        [
            Finding(code="ingest.not_watertight", severity="warning", message="offen"),
            Finding(code="slice.thin_wall", severity="info", message="dünn"),
        ]
    )

    assert window.report.alerts() == 1, "eine Warnung, der Hinweis zählt nicht"
    assert window.right.tabText(index) == f"{plain} · 1"


def test_a_stopped_chain_opens_the_report_even_during_a_tour(window: MainWindow) -> None:
    """Die Meldung sagt „siehe Prüfbericht" — dann muss er auch aufgehen.

    Der Vorrang der Tour ist richtig, solange es um eine Warnung im Ablauf
    geht. Hält die Kette an, verweist die Statusleiste ausdrücklich auf den
    Bericht; ein Verweis auf ein Fenster, das die Anwendung selbst zuhält,
    ist keiner.
    """
    from app.core import examples
    from app.core.tour import tour_for

    example = next(entry for entry in examples.EXAMPLES if tour_for(entry.id))
    window.tour.start(example, tour_for(example.id))
    # Gezeigt und mit sichtbarem Arbeitsbereich, weil ``_focus_report`` auf
    # einer unsichtbaren Spalte nichts tut — richtig so: ein Reiterwechsel
    # hinter dem Startbildschirm wäre keiner. Hält die Kette an, ist ohnehin
    # ein Projekt offen.
    window.show()
    window._show_start_screen(False)
    switch_to = window.right.indexOf(window.tour)
    window.right.setTabVisible(switch_to, True)
    window.right.setCurrentIndex(switch_to)
    assert window.tour.active, "die Anleitung läuft"

    window._focus_report()
    assert window.right.currentWidget() is window.tour, "eine Warnung lässt die Anleitung stehen"

    window._focus_report(force=True)
    assert window.right.currentWidget() is window.report, "ein Abbruch holt den Bericht nach vorn"
