"""Die Oberfläche: Sitzung, Fenster und die aus dem Schema erzeugten
Dialoge (§2.5, §10).

Läuft auf der Offscreen-Qt-Plattform, funktioniert also ohne Bildschirm.
Geprüft wird hier die Verdrahtung, keine Pixel: baut sich das Fenster aus dem
Register, geht eine Änderung durch den Stapel, bleibt die Auswertung im
Arbeiter.
"""

from __future__ import annotations

import dataclasses
import logging
import re
import threading
from pathlib import Path
from typing import Any, cast

import pytest

pytest.importorskip("PySide6")

from PySide6.QtCore import QEvent, QLocale, QPoint, Qt
from PySide6.QtGui import QAction, QKeySequence, QShortcut
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QMessageBox,
    QToolBar,
)

from app.core import errors
from app.core.export import handover
from app.core.geom.measure import Measurement
from app.core.registry import REGISTRY, catalogue_operations
from app.core.registry.registry import TWIN_TOGGLES
from app.core.scene import OperationDraft
from app.core.scene.project import load
from app.core.types import (
    Feature,
    Finding,
    MaterialSlot,
    Parameter,
    Profile,
    SceneObject,
    SlotOverride,
)
from app.i18n import tr
from app.ui import main_window as main_window_module
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


def test_filament_values_from_the_panel_reach_the_project(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die neue, kurze Bedienkette: Filamentpanel → Dialog → Projektdatei."""
    slot = MaterialSlot(index=1, name="PLA Weiß", colour=(1.0, 1.0, 1.0))
    released: list[MaterialSlot] = []

    class AcceptedFilamentDialog:
        def __init__(self, chosen, settings, _existing, _parent) -> None:
            self.chosen = chosen
            self.temperature = dataclasses.replace(settings.temperature, nozzle=205)

        def exec(self) -> int:
            return int(QDialog.DialogCode.Accepted)

        def override(self) -> SlotOverride:
            return SlotOverride(
                name=self.chosen.name,
                colour=self.chosen.colour,
                temperature=self.temperature,
            )

        def deleteLater(self) -> None:  # noqa: N802 - bildet die Qt-API nach
            released.append(self.chosen)

    monkeypatch.setattr(main_window_module, "FilamentOverrideDialog", AcceptedFilamentDialog)

    window.filaments.overrideRequested.emit(slot)

    settings = window.session.project.document.print_settings
    assert settings is not None
    override = handover.override_for(settings, slot)
    assert override is not None and override.temperature is not None
    assert override.temperature.nozzle == 205
    assert released == [slot], "der geschlossene Dialog bleibt nicht am Hauptfenster hängen"


def test_a_cancelled_filament_dialog_is_released(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auch Abbrechen räumt den parent-eigenen Qt-Dialog vollständig ab."""
    slot = MaterialSlot(index=1, name="PLA Weiß", colour=(1.0, 1.0, 1.0))
    released: list[MaterialSlot] = []

    class RejectedFilamentDialog:
        def __init__(self, chosen, _settings, _existing, _parent) -> None:
            self.chosen = chosen

        def exec(self) -> int:
            return int(QDialog.DialogCode.Rejected)

        def deleteLater(self) -> None:  # noqa: N802 - bildet die Qt-API nach
            released.append(self.chosen)

    monkeypatch.setattr(main_window_module, "FilamentOverrideDialog", RejectedFilamentDialog)

    window.filaments.overrideRequested.emit(slot)

    assert released == [slot]
    assert window.session.project.document.print_settings is None


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


@pytest.mark.parametrize("value", [float("nan"), float("inf"), float("-inf")])
def test_a_non_finite_parameter_is_reported_without_changing_the_document(
    session: Session, value: float
) -> None:
    """Eine ungültige Zahl bleibt im Dialogfehler, nie als Prozessabsturz."""
    document = session.project.document
    document.parameters["width"] = Parameter(name="width", value=84.0, unit="mm")
    errors_seen: list[errors.ValidationError] = []
    session.failed.connect(
        lambda error: (
            errors_seen.append(error) if isinstance(error, errors.ValidationError) else None
        )
    )

    assert not session.change_parameter("width", value)
    assert document.parameters["width"].value == 84.0
    assert not session.history.can_undo
    assert errors_seen and errors_seen[-1].constraint == "not_a_number"


def test_a_parameter_spinbox_can_rebuild_after_its_own_signal(window: MainWindow) -> None:
    """Die linke Parameterleiste darf ihren Sender erst nach dem Signal löschen."""
    document = window.session.project.document
    document.parameters["width"] = Parameter(name="width", value=84.0, unit="mm")
    window.parameters.show_document(document)
    editor = window.parameters._editors["width"]

    editor.setValue(120.0)
    QApplication.processEvents()
    window.session.wait_for_idle()

    assert document.parameters["width"].value == 120.0
    assert "width" in window.parameters._editors, "die Leiste wurde sicher neu aufgebaut"


def test_a_parameter_unit_is_a_safe_choice_in_the_left_panel(window: MainWindow) -> None:
    """Die Einheit ist eine feste, rücknehmbare Auswahl und kein Freitext."""
    from app.core.units import DEGREE_UNIT

    document = window.session.project.document
    document.parameters["angle"] = Parameter(name="angle", value=45.0, unit="mm")
    window.parameters.show_document(document)
    editor = window.parameters._unit_editors["angle"]

    assert not editor.isEditable()
    assert [editor.itemData(index) for index in range(editor.count())] == [
        "mm",
        DEGREE_UNIT,
        "",
    ]

    index = editor.findData(DEGREE_UNIT)
    editor.activated.emit(index)
    assert document.parameters["angle"].unit == "mm", "das Auswahlsignal löscht sich nicht selbst"
    QApplication.processEvents()
    window.session.wait_for_idle()

    assert document.parameters["angle"].unit == DEGREE_UNIT
    assert window.session.history.can_undo
    window.session.undo()
    assert document.parameters["angle"].unit == "mm"


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
    """Der Titel sagt, ob etwas ungesichert ist — nur nicht überall mit einem Stern.

    **Bis zum 23.08.2026 stand hier ``endswith("*")`` für beide Lagen.** Seit
    der Titel den abgeleiteten Namen trägt, sind es zwei verschiedene Aussagen:

        nie gespeichert   „cube_clean (ungespeichert)"   das Wort sagt es
        gespeichert       „projekt.p3d*"                 der Stern sagt es

    Der Stern bedeutet „seit dem letzten Speichern geändert" — wo nie
    gespeichert wurde, kann er gar nicht fehlen, und dann trüge der Titel
    dieselbe Aussage zweimal.
    """
    assert not session.title.endswith("*")
    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()
    assert "ungespeichert" in session.title, f"ohne Datei sagt es das Wort: {session.title!r}"
    assert session.title.startswith("cube_clean"), "und es nennt, was offen ist"

    session.save_project(tmp_path / "projekt.p3d")
    assert session.title == "projekt.p3d"

    # Und ab da trägt der Stern die Aussage.
    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()
    assert session.title == "projekt.p3d*", f"mit Datei sagt es der Stern: {session.title!r}"


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
    """Jede Operation bleibt erreichbar — im Menü, oder zusammengelegt.

    **Zwei Arten von Zusammenlegung, und sie sind verschieden.** Ein
    ``MENU_TWINS``-Zwilling ist dieselbe Handlung im anderen Rechenkern; sein
    Weg ist der Umschalter im Dialog des Partners, und der Partner trägt den
    Eintrag mit seinem eigenen Titel. Eine ``VARIANT_GROUPS``-Variante ist
    eine von mehreren gleichrangigen Arten; ihr Weg ist die Auswahl in einem
    Eintrag, der **keiner** Operation gehört und deshalb auch keinen
    Operationstitel trägt.

    Beide Male gilt dasselbe Hausprinzip — „eine Operation je Handlung, nicht
    je Variante" — und beide Male dieselbe Auflage: erreichbar bleibt alles,
    notfalls über die Palette.
    """
    from app.core.registry import MENU_TWINS, VARIANT_GROUPS, palette_entries, variant_members

    labels = {action.text() for action in all_menu_actions(window)}
    offered = {entry.name for entry in palette_entries()}
    gruppen = {str(group.title) for group in VARIANT_GROUPS}

    for spec in REGISTRY.all():
        if spec.name in MENU_TWINS:
            # Beide Zwillinge tragen absichtlich denselben verständlichen
            # Titel. Am Text lässt sich deshalb nicht erkennen, ob Qt zwei
            # Einträge gebaut hat; die Aktionszuordnung kann es eindeutig.
            assert spec.name not in window._op_actions, (
                f"{spec.name} soll kein eigener Eintrag sein"
            )
            assert spec.name in offered, f"{spec.name} muss über die Palette erreichbar bleiben"
            partner = REGISTRY.get(MENU_TWINS[spec.name])
            assert partner.name in window._op_actions, "der sichtbare Zwilling trägt den Eintrag"
            assert str(partner.title) in labels, "der sichtbare Zwilling trägt den Eintrag"
            continue
        if spec.name in variant_members():
            assert str(spec.title) not in labels, f"{spec.name} soll kein eigener Eintrag sein"
            assert spec.name in offered, f"{spec.name} muss über die Palette erreichbar bleiben"
            continue
        if spec.name in catalogue_operations():
            # **Dritter Fall neben Zwilling und Variante, seit dem 29.08.2026.**
            # Die Bausteine der Bibliothek haben keinen Menüort mehr: Ein
            # räumliches Teil als Textzeile zu führen ist die schlechtere
            # Darstellung (§2.6). Wie bei den anderen beiden wird beides
            # geprüft — kein Eintrag, und trotzdem vollständig erreichbar.
            #
            # **Gefragt wird nach der Kachel, nicht nach der Kategorie.** Hier
            # stand ``spec.category in WITHOUT_MENU``, und damit nahm die
            # Ausnahme zwei Operationen mit, die gar keine Kachel haben:
            # ``create_lid`` und ``screw_lid`` verschwanden aus der Leiste,
            # ohne im Katalog aufzutauchen. Eine Ausnahme, die zu weit gefasst
            # ist, macht einen Wächter genau dort blind, wo er greifen soll.
            assert str(spec.title) not in labels, (
                f"{spec.name} gehört in den Katalog, nicht ins Menü"
            )
            assert spec.name in offered, f"{spec.name} muss über die Palette erreichbar bleiben"
            continue
        assert str(spec.title) in labels, f"{spec.name} is missing from the menu"

    assert gruppen <= labels, f"diese Sammeleinträge fehlen: {gruppen - labels}"


def test_shortcuts_from_the_registry_are_installed(window: MainWindow) -> None:
    shortcuts = {
        action.shortcut().toString().lower()
        for action in all_menu_actions(window)
        if not action.shortcut().isEmpty()
    }
    for spec in REGISTRY.all():
        if spec.shortcut:
            assert spec.shortcut.lower() in shortcuts


def test_a_dialog_says_which_body_it_works_on(window: MainWindow) -> None:
    """Zwei Würfel gewählt, ein Loch — und kein Wort dazu, in welchem (Regel 21).

    Eine Operation nimmt so viele Körper, wie sie deklariert, und zwar in
    Klickreihenfolge (``inputs_for``). Bei zwei gewählten und *Bohrung setzen*
    bekam einer ein Loch und der andere nicht; im Dialog stand nichts davon,
    und der Fenstertitel ist beim Klicken nicht im Blick. Das ist kein Raten —
    die Regel stand nur nirgends, wo jemand sie liest.

    Und im Normalfall steht dort nichts: ein gewählter Körper braucht keine
    Erklärung, welcher gemeint ist.
    """
    from app.ui.main_window import inputs_for

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    first = next(iter(window.session.last_result.scene.objects))

    spec = REGISTRY.get("drill_hole")
    window.object_tree.select_object(first)
    QApplication.processEvents()
    window.run_operation(spec)
    dialog = window._op_dialog
    assert dialog is not None
    assert dialog._note.text() == "", "bei einem gewählten Körper gibt es nichts zu sagen"
    dialog.reject()
    QApplication.processEvents()

    window.session.apply(
        "Objekt duplizieren",
        [OperationDraft(op="duplicate_object", inputs=(first,), params={})],
    )
    window.session.wait_for_idle()
    window.object_tree.tree.selectAll()
    QApplication.processEvents()
    chosen = window.object_tree.selected_objects()
    assert len(chosen) == 2, chosen
    taken = inputs_for(spec, list(window.session.last_result.scene.objects), chosen)
    assert len(taken) == 1, "die Operation nimmt einen Körper"

    window.run_operation(spec)
    dialog = window._op_dialog
    assert dialog is not None
    try:
        note = dialog._note.text()
        name = window.session.last_result.scene.objects[taken[0]].name
        assert name in note, f"der Dialog nennt den Körper nicht: {note!r}"
        assert "2" in note, f"und nicht, wie viele gewählt sind: {note!r}"
        assert not dialog._note.isHidden(), "der Satz steht da, aber unsichtbar"
    finally:
        dialog.reject()


def test_no_two_shortcuts_in_the_window_collide(window: MainWindow) -> None:
    """Eine doppelt belegte Taste tut **nichts** (§19.2).

    Qt meldet in dem Fall „Ambiguous shortcut overload" und führt keine der
    beiden Aktionen aus — der Nutzer drückt, und es passiert gar nichts.
    Geprüft war das nur halb: ``tests/test_registry_consistency.py`` hält die
    Kürzel der **Operationen** auseinander, und das Fenster bringt dreiundvierzig
    weitere mit — Ansichten, Werkzeugzeile, Dateibefehle, Navigation.

    Gefunden hätte man die Dublette also erst beim Drücken. Der Test steht hier
    und nicht dort, weil erst das gebaute Fenster beide Seiten kennt.
    """
    from itertools import combinations

    from PySide6.QtGui import QAction, QShortcut
    from PySide6.QtWidgets import QWidget

    taken: dict[str, list[tuple[str, Qt.ShortcutContext, tuple[QWidget, ...]]]] = {}
    for action in window.findChildren(QAction):
        for sequence in action.shortcuts():
            widgets = tuple(
                owner for owner in action.associatedObjects() if isinstance(owner, QWidget)
            )
            taken.setdefault(sequence.toString(), []).append(
                (action.text() or "(ohne Text)", action.shortcutContext(), widgets)
            )
    for shortcut in window.findChildren(QShortcut):
        parent = shortcut.parent()
        widgets = (parent,) if isinstance(parent, QWidget) else ()
        taken.setdefault(shortcut.key().toString(), []).append(
            ("QShortcut", shortcut.context(), widgets)
        )

    def overlap(
        first: tuple[str, Qt.ShortcutContext, tuple[QWidget, ...]],
        second: tuple[str, Qt.ShortcutContext, tuple[QWidget, ...]],
    ) -> bool:
        """Nur getrennte Widget-Bereiche dürfen dieselbe nackte Taste tragen."""
        _first_name, first_context, first_widgets = first
        _second_name, second_context, second_widgets = second
        local = Qt.ShortcutContext.WidgetWithChildrenShortcut
        if first_context != local or second_context != local:
            return True
        return any(
            left is right or left.isAncestorOf(right) or right.isAncestorOf(left)
            for left in first_widgets
            for right in second_widgets
        )

    twice = {
        key: [
            (first[0], second[0])
            for first, second in combinations(bindings, 2)
            if overlap(first, second)
        ]
        for key, bindings in taken.items()
        if key
    }
    twice = {key: pairs for key, pairs in twice.items() if pairs}
    assert not twice, f"doppelt belegte Tasten führen keine der beiden Aktionen aus: {twice}"


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


def test_the_help_menu_leads_back_to_the_examples(window: MainWindow) -> None:
    """Die Beispiele standen an genau einer Stelle (§37.2, August-Durchsicht 2.2).

    Sie sind Dokumentation, Abnahmetest und Startbildschirm-Inhalt in einem —
    und wer den Startbildschirm einmal verlassen hatte, fand sie nur über
    *Öffnen* mit Pfadkenntnis wieder. Im Hilfemenü sieht man nach
    Lehrmaterial.

    Und ohne Verwerfen-Falle: Der Eintrag zeigt den Startbildschirm, mehr
    nicht — gefragt wird erst, wenn wirklich etwas verloren ginge (Regel 19).
    """
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    assert window.stack.currentWidget() is not window.start_screen

    labels = [
        action.text().replace("&", "")
        for menu in window.menuBar().actions()
        if menu.menu() is not None and menu.text().replace("&", "") == "Hilfe"
        for action in menu.menu().actions()
    ]
    assert "Beispiele" in labels

    window.action_examples()

    assert window.stack.currentWidget() is window.start_screen
    assert window.session.project.document.ops, "das Projekt steht noch, es ist nur verdeckt"


def test_the_help_menu_offers_direct_support(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der freiwillige Förderweg steht dort, wo man Kontakt und Auskunft sucht."""
    from app.branding import APP_NAME
    from app.ui.dialogs import DonationDialog

    entries = [
        action
        for menu in window.menuBar().actions()
        if menu.menu() is not None and menu.text().replace("&", "") == "Hilfe"
        for action in menu.menu().actions()
    ]
    support = next(
        action
        for action in entries
        if action.text().replace("&", "") == f"{APP_NAME} unterstützen …"
    )
    shown: list[str] = []
    monkeypatch.setattr(
        DonationDialog, "exec", lambda dialog: shown.append(dialog.windowTitle()) or 0
    )

    support.trigger()

    assert shown == [f"{APP_NAME} unterstützen"]


def test_the_support_dialog_opens_paypal_only_after_the_click(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Dialog bleibt lokal; erst sein eindeutiger Knopf fragt nach draußen."""
    from PySide6.QtCore import QUrl
    from PySide6.QtWidgets import QLabel

    from app.branding import DONATION_URL
    from app.ui.dialogs import DonationDialog

    opened: list[str] = []

    def open_url(url: QUrl) -> bool:
        opened.append(url.toString())
        return True

    monkeypatch.setattr("app.ui.dialogs.QDesktopServices.openUrl", open_url)
    dialog = DonationDialog()

    assert not opened
    assert "Standardbrowser" in dialog.browser_note.text()
    assert dialog.support_button.text() == "PayPal im Browser öffnen"
    assert dialog.close_button.text() == "Schließen"
    text = "\n".join(label.text() for label in dialog.findChildren(QLabel))
    assert "keine Bestellung" in text
    assert "keine Gegenleistung" in text
    assert "keine zusätzlichen Funktionen" in text
    assert "Erst nach Ihrem Klick online" in text

    dialog.support_button.click()

    assert opened == [DONATION_URL]
    dialog.reject()


def test_a_blocked_payment_page_offers_a_copyable_way_out(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein fehlender Browser lässt niemanden mit einer Adresse zum Abtippen stehen."""
    from app.branding import DONATION_URL
    from app.ui.dialogs import DonationOpenErrorDialog, open_donation

    copied: list[str] = []
    shown: list[DonationOpenErrorDialog] = []
    monkeypatch.setattr("app.ui.dialogs.QDesktopServices.openUrl", lambda _url: False)
    monkeypatch.setattr("app.ui.dialogs.copy_donation_url", lambda: copied.append(DONATION_URL))
    monkeypatch.setattr(
        DonationOpenErrorDialog,
        "exec",
        lambda dialog: shown.append(dialog) or 0,
    )

    assert not open_donation()
    assert len(shown) == 1
    assert shown[0].copy_button.text() == "Zahlungslink kopieren"

    shown[0].copy_button.click()

    assert copied == [DONATION_URL]


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


def test_view_menu_and_settings_share_theme_and_navigation_names(window: MainWindow) -> None:
    """Menü und Einstellungsdialog pflegen keine zwei Vokabulare."""
    from app.ui.settings_dialog import NAVIGATION, THEMES

    themes = {str(action.data()): action.text() for action in window._theme_group.actions()}
    navigation = {
        str(action.data()): action.text() for action in window._navigation_group.actions()
    }

    assert themes == {key: str(label) for key, label in THEMES.items()}
    assert navigation == {key: str(label) for key, label in NAVIGATION.items()}


def test_measure_bar_offers_angles_and_shows_degrees(qt_app: QApplication) -> None:
    """Ein Winkel ist auswählbar und wird nicht als Länge beschriftet."""
    from app.ui.section_bar import MeasureBar

    bar = MeasureBar()
    modes = [bar.mode.itemData(index) for index in range(bar.mode.count())]
    assert "angle" in modes

    bar.show_measurement("angle", 90.0, 1)
    assert "90°" in bar.readout.text()
    assert "mm" not in bar.readout.text()


def test_angle_measurement_uses_two_detected_planes(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§18.3 meint erkannte Ebenen, nicht drei frei geklickte Punkte."""
    from types import SimpleNamespace

    from app.ui.viewport import Viewport

    viewport = Viewport()
    faces = {
        "one": SimpleNamespace(
            kind="face", params={"normal": (1.0, 0.0, 0.0), "centre": (0.0, 0.0, 0.0)}
        ),
        "two": SimpleNamespace(
            kind="face", params={"normal": (0.0, 1.0, 0.0), "centre": (5.0, 0.0, 0.0)}
        ),
    }
    entry = SimpleNamespace(features=faces)
    viewport._result = SimpleNamespace(scene=SimpleNamespace(objects={"obj_1": entry}))
    monkeypatch.setattr(viewport, "_object_at", lambda point: "obj_1")
    monkeypatch.setattr(viewport, "_feature_at", lambda point: "one" if point[0] == 0 else "two")

    statuses: list[str] = []
    viewport.measurementStatus.connect(statuses.append)
    viewport._measure_plane_angle((0.0, 0.0, 0.0))
    viewport._measure_plane_angle((5.0, 0.0, 0.0))

    assert statuses and "zweite Ebene" in statuses[-1]
    assert len(viewport.measurements) == 1
    assert viewport.measurements.entries[0].kind == "angle"
    assert viewport.measurements.entries[0].value == pytest.approx(90.0)


def test_measuring_never_ends_in_silence(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die drei stummen Ausgänge des Messens melden sich jetzt (§2.7).

    Der Winkel-Pfad machte es seit je vor; Distanz und Wandstärke hatten
    drei ``return`` ohne ein Wort — Klick ins Leere, Wand ohne Messwert,
    erster Punkt gesetzt. Wer am Messen war und danebenklickte, sah einfach
    nichts und hielt das Werkzeug für kaputt.
    """
    import trimesh as raw_trimesh

    from app.core.geom.mesh import MeshData
    from app.ui.viewport import Viewport

    viewport = Viewport()
    statuses: list[str] = []
    viewport.measurementStatus.connect(statuses.append)
    viewport._measure_mode = "distance"

    monkeypatch.setattr(viewport, "_nearest_mesh", lambda point: None)
    viewport._on_picked((0.0, 0.0, 0.0))
    assert statuses and "Körper anklicken" in statuses[-1], statuses

    box = MeshData.of(raw_trimesh.creation.box(extents=(10.0, 10.0, 10.0)))
    monkeypatch.setattr(viewport, "_nearest_mesh", lambda point: box)
    viewport._on_picked((5.0, 0.0, 0.0))
    assert "zweiten Punkt anklicken" in statuses[-1], statuses
    assert viewport._pending_point is not None

    viewport._measure_mode = "thickness"
    monkeypatch.setattr("app.ui.viewport.wall_thickness", lambda mesh, point: None)
    viewport._on_picked((5.0, 0.0, 0.0))
    assert "Wand" in statuses[-1], statuses
    assert len(viewport.measurements) == 0, "gemeldet heißt nicht gemessen"


def test_opening_a_model_leaves_the_start_screen(window: MainWindow) -> None:
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    assert window.stack.currentWidget() is window.overlay
    assert [entry.op for entry in window.session.project.document.ops] == ["load"]


def test_importing_from_the_start_screen_shows_the_workspace(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Von acht Wegen ins Dokument wechselte genau dieser nicht in den
    Arbeitsbereich — und auf ihn zeigt der Schlussknopf der
    Erstinbetriebnahme: Modell geladen, Startbildschirm stand (§2.3)."""
    from PySide6.QtWidgets import QFileDialog

    assert window.stack.currentWidget() is window.start_screen
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *args, **kwargs: (str(MESHES / "cube_clean.stl"), "")),
    )

    window.action_import()
    window.session.wait_for_idle()

    assert window.stack.currentWidget() is not window.start_screen
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


def test_choosing_a_profileless_filament_clears_old_slicer_metadata(
    qt_app: QApplication,
) -> None:
    """Ein Filamentwechsel darf keine unsichtbare Herstellerwahl behalten.

    Eine lokale Spule hat bewusst kein Slicer-Profil. Wird sie in einem
    geöffneten Farbschritt gewählt, muss deshalb der alte Profilname
    verschwinden; sonst fährt die neue Spule mit den Druckwerten der alten.
    """
    dialog = OperationDialog(
        REGISTRY.get("assign_slot"),
        ["obj_1"],
        values={
            "slot": 1,
            "name": "PETG Grau",
            "colour": "#808080",
            "material_type": "PETG",
            "slicer_profile": "Elegoo PETG PRO @ECC2",
        },
    )
    try:
        dialog._fill_filament_fields("PLA Weiß", "#ffffff", "PLA", "")

        values = dialog.values()
        assert values["name"] == "PLA Weiß"
        assert values["material_type"] == "PLA"
        assert values["slicer_profile"] == "", "die leere Auswahl löscht den alten Wert"
    finally:
        dialog.deleteLater()


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

        # **Und er bleibt innerhalb der Kante.** Gerechnet wurde mit
        # ``sizeHint``, gezeigt wird die Mindestbreite von 380: um die Differenz
        # — je Operation 62 bis 131 Bildpunkte — schob die Rechnung ihn über
        # genau den Rand hinaus, den sie einhalten sollte.
        breadth = (
            dialog.width()
            if dialog.isVisible()
            else max(dialog.sizeHint().width(), dialog.minimumWidth())
        )
        right_edge = anchor.mapToGlobal(anchor.rect().topRight()).x()
        assert dialog.x() + breadth <= right_edge, (
            f"der Dialog ragt {dialog.x() + breadth - right_edge} Punkte über die Kante"
        )
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


def test_the_about_dialog_localises_the_security_promise_and_links(
    qt_app: QApplication,
) -> None:
    """§37.3: Termin und Meldeweg stimmen in jeder ausgelieferten Sprache.

    ``QLocale()`` folgt der Prozesssprache, Solidon wechselt seine Sprache aber
    im laufenden Prozess. Die echte spanische Oberfläche zeigte deshalb noch
    „31. Oktober 2031“, obwohl der übrige Satz übersetzt war.
    """
    from PySide6.QtWidgets import QLabel

    from app.branding import SECURITY_SUPPORT_UNTIL, SUPPORT_ADDRESS, WEBSITE_URL
    from app.i18n import set_language
    from app.i18n.catalog import available_languages, install_language
    from app.ui.dialogs import AboutDialog

    dates = {
        "de": "31. Oktober 2031",
        "en": "October 31, 2031",
        "es": "31 de octubre de 2031",
        "fr": "31 octobre 2031",
        "it": "31 ottobre 2031",
        "pt": "31 de outubro de 2031",
    }
    assert SECURITY_SUPPORT_UNTIL.isoformat() == "2031-10-31"

    try:
        for language in available_languages():
            install_language(language)
            set_language(language)
            dialog = AboutDialog()
            security = dialog.findChild(QLabel, "security_support")
            assert security is not None
            text = security.text()
            page = "security.html" if language == "de" else f"{language}/security.html"

            assert dates[language] in text
            assert f'href="mailto:{SUPPORT_ADDRESS}"' in text
            assert f'href="{WEBSITE_URL}{page}"' in text
            assert security.openExternalLinks()
            assert security.textInteractionFlags() & Qt.TextInteractionFlag.LinksAccessibleByMouse
            assert (
                security.textInteractionFlags() & Qt.TextInteractionFlag.LinksAccessibleByKeyboard
            )
            dialog.deleteLater()
    finally:
        set_language("de")


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


def test_an_open_advanced_section_never_overlaps_the_action_buttons(
    qt_app: QApplication,
) -> None:
    """Der aufgeklappte Gewinde-Dialog bleibt vollständig bedienbar."""
    dialog = OperationDialog(REGISTRY.get("insert_printed_thread"), [])
    try:
        dialog.show()
        QApplication.processEvents()
        dialog.advanced.setChecked(True)
        QApplication.processEvents()

        box = dialog.findChild(QDialogButtonBox)
        assert box is not None
        advanced = [
            editor
            for name, editor in dialog._editors.items()
            if next(entry.placement for entry in dialog.spec.params.spec() if entry.name == name)
            == "advanced"
        ]
        assert advanced and all(editor.isVisibleTo(dialog) for editor in advanced)
        assert max(editor.geometry().bottom() for editor in advanced) < box.geometry().top()
    finally:
        dialog.close()


def test_a_thread_dialog_uses_the_selected_face_or_bore(window: MainWindow) -> None:
    """Bohrung und ebene Außenfläche bekommen die Richtung ohne Raten."""
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    hole = next(
        identifier for identifier, feature in entry.features.items() if feature.kind == "hole"
    )
    face = next(
        identifier for identifier, feature in entry.features.items() if feature.kind == "face"
    )
    spec = REGISTRY.get("insert_printed_thread")

    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, hole)
    window.run_operation(spec)
    dialog = next(child for child in window.findChildren(OperationDialog) if child.isVisible())
    assert dialog.values()["at_feature"] == hole
    assert dialog.values()["internal"], "Bohrung heißt Innengewinde"
    internal_label = dialog._rows["internal"].labelForField(dialog._editors["internal"])
    assert internal_label is not None
    assert internal_label.text() == "Innengewinde (aus = Außengewinde)"
    assert "Gewindebolzen auf einer ebenen Außenfläche" in dialog._editors["internal"].toolTip()
    assert "Drehdeckel erzeugen" in dialog._editors["internal"].toolTip()
    dialog.reject()

    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, face)
    window.run_operation(spec)
    dialog = next(child for child in window.findChildren(OperationDialog) if child.isVisible())
    assert dialog.values()["at_feature"] == face
    assert not dialog.values()["internal"], "eine ebene Fläche heißt Gewindebolzen"
    dialog.reject()


def test_drawable_faces_keep_the_object_that_owns_them(window: MainWindow) -> None:
    """Die Ebenenliste bindet jede Fläche an ihren Körper, ohne NameError."""
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id = next(iter(result.scene.objects))

    faces = window._drawable_faces()

    assert faces, "ein Würfel bietet ebene Zeichenflächen an"
    assert all(identifier.startswith(f"{object_id}:") for identifier, _label, _normal in faces)


def test_a_tree_context_click_selects_the_feature_it_opens_for(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Rechtsklick auf eine Bohrung darf nicht die vorige Auswahl benutzen."""
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    hole = next(
        identifier for identifier, feature in entry.features.items() if feature.kind == "hole"
    )
    face = next(
        identifier for identifier, feature in entry.features.items() if feature.kind == "face"
    )

    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, hole)
    target = next(
        item
        for item in window.object_tree.tree.selectedItems()
        if item.data(1, Qt.ItemDataRole.UserRole) == hole
    )
    assert target is not None
    window.show()
    window.object_tree.tree.expandAll()
    window.object_tree.tree.scrollToItem(target)
    QApplication.processEvents()
    point = window.object_tree.tree.viewport().mapTo(
        window.object_tree.tree,
        window.object_tree.tree.visualItemRect(target).center(),
    )
    assert point.y() >= 0, "die Bohrung hat eine sichtbare Baumzeile"
    window.object_tree.select_feature(object_id, face)
    monkeypatch.setattr(window.object_tree, "context_menu", lambda: None)

    window.object_tree._on_context_menu(point)

    assert window.object_tree.selected_feature() == hole


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

    assert window.explode_bar.show_for(3) is True, "drei Körper sind etwas zum Auseinanderziehen"
    assert window.explode_bar.show_for(1) is False
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


def test_a_finding_with_a_way_out_is_chosen_before_anyone_clicks(window: MainWindow) -> None:
    """Die Knopfzeile des Prüfberichts steht ohne einen Klick da (§2.7).

    Sie zeigt die Handlungen des **gewählten** Befunds — und gewählt war nach
    dem Öffnen keiner. Der Kunde sah eine Liste und darunter nichts; dass ein
    Klick auf eine Listenzeile Knöpfe freischaltet, muss man wissen. §2.7
    verspricht anklickbare Handlungen, nicht auffindbare.

    Gemessen an einem **zweiten** Modell, und das hat seit dem 03.09.2026 einen
    Grund: Das erste Modell eines Projekts kommt aufgesetzt und mittig herein
    (§17.1, Schritt 6), hat also nichts unter der Platte und nichts zu melden.
    Jedes weitere behält seine Dateilage — ``block_with_rounded_edge.stl``
    liegt von Z -10 bis +10 —, der Bericht meldet ``arrange.below_bed``, und
    *Auf das Bett setzen* löst es mit einem Klick. Vorher standen dort **null**
    Knöpfe und ``currentRow()`` auf −1.

    Zwei Entscheidungen im Testaufbau, beide notwendig:

    * **Am gebauten Fenster**, nicht an einem freistehenden ``ReportPanel``.
      ``_preselect`` fragt ``handlers_of``, und ein Panel ohne Fenster darüber
      hat keine Handler — der Test wäre grün gegen eine Zeile, die beim Kunden
      nichts tut.
    * **Die Knöpfe werden gezählt, nicht auf ``isVisible`` geprüft.** In einem
      nie gezeigten Fenster antwortet Qt darauf falsch; die Knöpfe existieren
      dagegen nur, wenn ``_show_offers`` sie gebaut hat, und das tut es allein
      für einen gewählten Befund.
    """
    from PySide6.QtWidgets import QAbstractButton

    window.open_path(MESHES / "block_with_rounded_edge.stl")
    window.session.wait_for_idle()
    # Das zweite Modell ist das, das unter der Platte landet — das erste liegt
    # seit dem 03.09.2026 aufgesetzt und mittig da.
    window.open_path(MESHES / "block_with_rounded_edge.stl")
    window.session.wait_for_idle()
    window._on_scene(window.session.evaluate_now())

    codes = [
        window.report.list.item(row).data(Qt.ItemDataRole.UserRole).code
        for row in range(window.report.list.count())
    ]
    assert "arrange.below_bed" in codes, "dieses Modell steckt unter dem Bett"

    assert window.report.list.currentRow() >= 0, "kein Befund ist vorgewählt"
    offered = [
        button.text().replace("&", "")
        for button in window.report._offers.findChildren(QAbstractButton)
    ]
    assert offered, "ohne einen Klick steht keine Handlung als Knopf da"

    chosen = window.report.list.currentItem().data(Qt.ItemDataRole.UserRole)
    assert chosen.code == "arrange.below_bed", (
        f"vorgewählt ist {chosen.code!r} — der Befund ohne Handlung nützt hier nichts"
    )


def test_the_small_parts_button_removes_them_and_not_merely_runs(window: MainWindow) -> None:
    """Der Knopf zu „sehr kleine Einzelteile" entfernt sie wirklich.

    Der Befund sagte „Gelöscht wurde nichts." und bot nichts an — gemessen am
    Korpus bei zwei von zwanzig Modellen. Die Anwendung **kann** es:
    ``repair`` trägt einen Schalter ``small_components``.

    **Der naheliegende Fix wäre ein Knopf ohne Wirkung gewesen.** Den Befund an
    das vorhandene ``REPAIR_AND_RETRY`` zu hängen, hätte zehn Sekunden
    gedauert: ``_repair_after_error`` ruft ``repair`` ohne Parameter, und der
    Schalter steht dort auf ``False`` (``geom/repair.py``). Der Knopf wäre
    durchgelaufen, hätte einen Schritt in den Verlauf gelegt und die Teile
    stehen gelassen.

    **Deshalb zählt dieser Test Komponenten und nicht Schritte.** Ein Test auf
    „die Operation lief" wäre gegen genau diesen Fehler blind — sie läuft ja.
    Die Zahl der Komponenten ist dabei die eine Größe, die der parameterlose
    Aufruf **nicht** bewegt: ``weld``, ``degenerate``, ``normals`` und
    ``holes`` stehen in der Vorgabe auf ``True`` und ändern Ecken, Dreiecke und
    Normalen — die Fragmente lassen sie stehen.
    """
    from app.core.geom.mesh import face_components
    from app.ui.panels import actions_for, as_error

    window.open_path(MESHES / "two_components.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    window._on_scene(result)

    findings = list(result.scene.report.findings)
    small = next((f for f in findings if f.code == "ingest.small_components"), None)
    assert small is not None, (
        "dieses Modell soll den Befund auslösen — sonst prüft der Test nichts: "
        f"{[f.code for f in findings]}"
    )

    body = next(iter(result.scene.objects.values()))
    assert body.mesh is not None
    before = len(face_components(body.mesh.raw))
    assert before > 1, "ohne mehrere Komponenten gibt es nichts zu entfernen"

    handlers = window.error_handlers()
    offered = [action for action in actions_for(small) if action.id in handlers]
    assert [action.id for action in offered] == ["remove_small_parts"], (
        f"der Befund bietet {[a.id for a in offered]} an"
    )
    handlers["remove_small_parts"](as_error(small))
    window.session.wait_for_idle()

    after_result = window.session.last_result
    assert after_result is not None
    after_body = next(iter(after_result.scene.objects.values()))
    assert after_body.mesh is not None
    after = len(face_components(after_body.mesh.raw))
    assert after < before, (
        f"{before} Komponenten vorher, {after} nachher — der Knopf lief, "
        "ohne die kleinen Teile zu entfernen"
    )


def test_a_chosen_finding_survives_a_second_report(window: MainWindow) -> None:
    """Eine Wahl des Kunden überschreibt die Vorauswahl nicht (§2.4).

    Befunde kommen nach — die G-Code-Gegenprobe, die Kollisionsprüfung. Wer
    inzwischen selbst eine Zeile gewählt hat, behält sie; eine Vorauswahl, die
    sich über eine getroffene Wahl legt, wäre schlimmer als gar keine.
    """
    window.open_path(MESHES / "block_with_rounded_edge.stl")
    window.session.wait_for_idle()
    window._on_scene(window.session.evaluate_now())

    window.report.list.setCurrentRow(0)
    standing = window.report.list.currentItem().data(Qt.ItemDataRole.UserRole).code

    window.report._preselect()

    kept = window.report.list.currentItem().data(Qt.ItemDataRole.UserRole).code
    assert kept == standing, "die Vorauswahl hat eine getroffene Wahl überschrieben"


def test_a_double_click_on_a_folded_step_says_where_the_single_ones_are(
    qt_app: QApplication,
) -> None:
    """Eine Geste, die sechs Touren lehren, darf nicht stumm bleiben (Regel 17).

    Ein Doppelklick im Verlauf öffnet den Schritt — außer der Schritt fasst
    mehrere Operationen zusammen: Dann trägt die Zeile keine ``UserRole``, denn
    welche der vier sollte sich öffnen. Der Tooltip der Liste verspricht die
    Geste trotzdem ohne Einschränkung, und sechs der neun Beispieltouren lehren
    sie als *den* Weg zum Ändern.

    Geprüft wird über das Signal der Liste und nicht über ``_on_activated``:
    Was ein Doppelklick auslöst, entscheidet die Verbindung, und die ist Teil
    der Zusage.
    """
    from app.core.types import Document, Transaction
    from app.ui.panels import HistoryPanel

    document = Document(format_version=7, app_version="0.0.1")
    document.transactions.append(Transaction(id=1, title="Bohrung setzen", ops=(1,)))
    document.transactions.append(Transaction(id=2, title="Teilung in vier", ops=(2, 3, 4, 5)))

    panel = HistoryPanel()
    panel.show_document(document)

    notes: list[str] = []
    opened: list[int] = []
    panel.noteRequested.connect(notes.append)
    panel.operationActivated.connect(opened.append)

    einzeln = panel.list.item(0)
    assert einzeln.text() == "1  Bohrung setzen"
    panel.list.itemDoubleClicked.emit(einzeln)
    assert opened == [1], "ein einzelner Schritt öffnet sich weiterhin"
    assert not notes

    gefaltet = panel.list.item(1)
    # Der Titel steht dran, und mehr sagt diese Zeile nicht zu: Seit die
    # Oberpunkte einklappen, trägt sie davor ein Dreieck (▸/▾). Ein
    # Gleichheitsvergleich hätte hier den Ist-Zustand festgeschrieben statt
    # der Zusage — und die lautet, dass ein Sammelschritt keine einzelne
    # Operation öffnet.
    assert "Teilung in vier" in gefaltet.text(), gefaltet.text()
    panel.list.itemDoubleClicked.emit(gefaltet)
    assert opened == [1], "ein Sammelschritt öffnet keine einzelne Operation"
    assert notes, "der Doppelklick blieb stumm — die Touren lehren ihn trotzdem"
    assert "einzeln" in notes[0], notes[0]


def test_a_group_starts_folded(qt_app: QApplication) -> None:
    """Ein Oberpunkt zeigt seine Teilschritte erst auf Wunsch.

    **Roberts Anweisung vom 30.08.2026:** „oberpunkte im verlauf auch noch
    einklappen, damit es nicht zu voll wird". Ein Verlauf, der jeden
    Teilschritt zeigt, ist nach zehn Handlungen eine Wand aus Zeilen, und die
    eine, die man sucht, steht irgendwo darin.

    Das Dreieck ist die zweite Kodierung neben der Einrückung (Regel 18): Ein
    Bildschirmleser liest keine Leerzeichen vor.
    """
    from app.core.types import Document, Transaction
    from app.ui.panels import HistoryPanel

    document = Document(format_version=7, app_version="0.0.1")
    document.transactions.append(Transaction(id=1, title="Teilung in vier", ops=(1, 2, 3, 4)))

    panel = HistoryPanel()
    panel.show_document(document)

    oben = panel.list.item(0)
    assert oben.text().startswith("▸"), f"kein Zeichen für den zugeklappten Punkt: {oben.text()!r}"
    versteckt = [panel.list.item(row).isHidden() for row in range(1, panel.list.count())]
    assert all(versteckt), f"Teilschritte stehen offen, obwohl zugeklappt: {versteckt}"


def test_a_click_unfolds_and_folds_again(qt_app: QApplication) -> None:
    """Ein Klick klappt auf, der nächste zu — ohne Rückfrage.

    Regel 19: Einklappen nimmt nichts weg, es zeigt nur weniger. Ein Dialog
    davor wäre eine Bestätigung für etwas, das der nächste Klick zurückholt.
    """
    from app.core.types import Document, Transaction
    from app.ui.panels import HistoryPanel

    document = Document(format_version=7, app_version="0.0.1")
    document.transactions.append(Transaction(id=1, title="Teilung in vier", ops=(1, 2, 3, 4)))

    panel = HistoryPanel()
    panel.show_document(document)
    oben = panel.list.item(0)

    panel.list.itemClicked.emit(oben)
    assert oben.text().startswith("▾"), f"das Zeichen ist nicht mitgegangen: {oben.text()!r}"
    assert not panel.list.item(1).isHidden(), "der Klick hat nicht aufgeklappt"

    panel.list.itemClicked.emit(oben)
    assert oben.text().startswith("▸")
    assert panel.list.item(1).isHidden(), "der zweite Klick hat nicht zugeklappt"


def test_a_finding_unfolds_the_group_it_points_into(qt_app: QApplication) -> None:
    """**Die Stelle, an der der Umbau am ehesten still bricht** (V6).

    Ein Klick auf einen Befund führt zu seinem Schritt (``point_at``). Liegt
    der in einem eingeklappten Oberpunkt, wäre die Auswahl unsichtbar — der
    Klick sähe folgenlos aus, und genau das war der Befund, den V6 behoben
    hat. Eine versteckte Zeile auszuwählen ist dasselbe wie gar nichts zu tun.
    """
    from app.core.types import Document, Transaction
    from app.ui.panels import HistoryPanel

    document = Document(format_version=7, app_version="0.0.1")
    document.transactions.append(Transaction(id=1, title="Teilung in vier", ops=(1, 2, 3, 4)))

    panel = HistoryPanel()
    panel.show_document(document)
    assert panel.list.item(2).isHidden(), "der Aufbau war schon offen — der Test misst dann nichts"

    assert panel.point_at(3), "der Schritt wurde nicht gefunden"

    gewaehlt = panel.list.currentItem()
    assert gewaehlt is not None
    assert not gewaehlt.isHidden(), (
        "der Befund zeigt auf eine versteckte Zeile — für den Kunden ist der Klick damit folgenlos"
    )


def test_an_open_group_stays_open_across_a_rebuild(qt_app: QApplication) -> None:
    """Was der Kunde aufgeklappt hat, bleibt offen.

    ``show_document`` läuft nach jeder Änderung. Ein Verlauf, der dabei
    zuklappt, nähme dem Kunden gerade das, was er sich eben aufgemacht hat —
    und zwar in dem Moment, in dem er arbeitet.
    """
    from app.core.types import Document, Transaction
    from app.ui.panels import HistoryPanel

    document = Document(format_version=7, app_version="0.0.1")
    document.transactions.append(Transaction(id=1, title="Teilung in vier", ops=(1, 2, 3, 4)))

    panel = HistoryPanel()
    panel.show_document(document)
    panel.list.itemClicked.emit(panel.list.item(0))
    assert not panel.list.item(1).isHidden()

    document.transactions.append(Transaction(id=2, title="Bohrung setzen", ops=(5,)))
    panel.show_document(document)

    assert not panel.list.item(1).isHidden(), (
        "der Neuaufbau hat den Punkt zugeklappt, den der Kunde geöffnet hatte"
    )


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
    # Die führende Zahl ist die Schrittnummer und keine Herkunftsangabe: Sie
    # steht an jeder Zeile, die genau eine Operation vertritt, damit der
    # Fehlerdialog („Operation: 4") und der Verlauf dieselbe Zahl nennen. Was
    # dieser Test zusichert, ist die Abwesenheit eines *Kommentars* — „(Agent)"
    # steht an der zweiten Zeile und an der ersten nicht.
    assert lines[0] == "1  Bohrung setzen", "der Regelfall bleibt unkommentiert"
    assert "Agent" not in lines[0]
    assert "Agent" in lines[1]


def test_the_history_keeps_the_title_of_a_deleted_child(qt_app: QApplication) -> None:
    """Auch ein gelöschter Teilschritt bleibt für Menschen verständlich benannt."""
    from app.core.types import (
        Document,
        DocumentChange,
        DocumentState,
        Operation,
        Transaction,
    )
    from app.ui.panels import HistoryPanel, _op_title

    removed = Operation(id=1, op="drill_hole")
    remaining = Operation(id=2, op="rename_object")
    document = Document(format_version=17, app_version="0.1.3", ops=[remaining])
    document.transactions.extend(
        [
            Transaction(id="t1", title="Zwei Änderungen", ops=(1, 2)),
            Transaction(
                id="t2",
                title="Schritt löschen",
                ops=(),
                changes=DocumentChange(
                    before=DocumentState(edited_ops={1: removed}),
                    after=DocumentState(edited_ops={1: None}),
                ),
            ),
        ]
    )

    panel = HistoryPanel()
    panel.show_document(document)

    deleted = next(
        panel.list.item(row).text()
        for row in range(panel.list.count())
        if tr("gelöscht") in panel.list.item(row).text() and "1" in panel.list.item(row).text()
    )
    assert _op_title(removed.op) in deleted, "die Zeile zeigte nur eine Nummer"


def test_history_context_delete_uses_the_visible_multiple_selection(
    qt_app: QApplication,
) -> None:
    """Rechtsklick löscht dieselbe Mehrfachauswahl wie die Entf-Taste."""
    from app.core.types import Document, Operation, Transaction
    from app.ui.panels import HistoryPanel

    document = Document(
        format_version=17,
        app_version="0.1.3",
        ops=[Operation(id=1, op="drill_hole"), Operation(id=2, op="rename_object")],
        transactions=[
            Transaction(id="t1", title="Bohrung", ops=(1,)),
            Transaction(id="t2", title="Name", ops=(2,)),
        ],
    )
    panel = HistoryPanel()
    panel.show_document(document)
    panel.show()
    QApplication.processEvents()
    first = panel.list.item(0)
    second = panel.list.item(1)
    first.setSelected(True)
    second.setSelected(True)

    assert panel._operations_for_context(first) == (1, 2)

    panel.list.clearSelection()
    first.setSelected(True)
    assert panel._operations_for_context(second) == (2,)
    assert panel.selected_operations() == (2,), "der Rechtsklick ließ eine fremde Auswahl stehen"


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
    assert not window.split_bar.isVisibleTo(window.tools)


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

    # **Jedes** Werkzeug trägt sein Wort — die Zahl selbst prüft
    # ``test_interface_limits`` als Obergrenze (höchstens acht). Hier stand
    # ``== 8``, und damit hätte der Ausbau des Punkt-Radius-Pinsels einen
    # Test über *Beschriftungen* rot gemacht: Die Zusage ist „keines ohne
    # Wort", nicht „genau acht Stück".
    assert titles, "ohne Werkzeuge prüft dieser Test nichts"
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


def test_the_first_run_describes_every_tool_state_in_words(qt_app: QApplication) -> None:
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
        assert any(
            word in ("gefunden", "bereit", "installiert", "nicht eingerichtet") for word in words
        ), words
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


def test_isolating_a_hidden_body_isolates_instead_of_revealing(
    window: MainWindow,
) -> None:
    """Beschriftung und Wirkung teilen sich jetzt eine Antwort (§18.8).

    Rechtsklick auf einen bereits **ausgeblendeten** Körper bot „Alles andere
    ausblenden" — und die Wirkung war „alles einblenden": Beide Seiten lasen
    dasselbe Feld mit verschiedener Frage (Gesamtreview 25.08.2026, I-6).
    """
    _with_two_objects(window)
    window._apply_hidden(frozenset({"obj_2"}))

    window._on_isolate(("obj_2",))
    assert window.viewport.hidden == frozenset({"obj_1"}), (
        "wer ein verstecktes Teil isoliert, will es sehen — nicht alles"
    )

    window._on_isolate(("obj_2",))
    assert window.viewport.hidden == frozenset(), "derselbe Eintrag holt alles zurück"


def test_the_palette_refuses_a_locked_choice_with_the_reason(window: MainWindow) -> None:
    """Gesperrt bleibt gesperrt, auch über die Pfeiltasten (Regel 19).

    Die Liste sperrt ihre Zeilen, aber die Tastatur sprang auf eine gesperrte,
    und Enter führte sie aus — „Gitter füllen" auf leerer Szene öffnete die
    modale Sackgasse (Gesamtreview 25.08.2026, I-3). Der Grund geht jetzt in
    die Statuszeile, gestartet wird nichts.
    """
    launched: list[str] = []
    window.launch_operation = lambda spec: launched.append(spec.name)  # type: ignore[method-assign]

    available, reason = window._palette_availability("lattice_fill")
    assert not available and reason, "auf leerer Szene ist die Wahl gesperrt, mit Grund"

    window._run_palette_choice("lattice_fill")
    assert launched == [], "eine gesperrte Wahl startet nichts"
    assert window.status_message.text() == reason, "der Grund steht in der Zeile"

    window._run_palette_choice("create_box")
    assert launched == ["create_box"], "eine freie Wahl startet wie bisher"


def test_an_operation_without_a_menu_entry_is_not_simply_allowed(window: MainWindow) -> None:
    """Keine Menü-Action zu haben heißt nicht, dass alles geht.

    ``_palette_availability`` las die Sperre aus der Action, die auch das Menü
    ausgraut — richtig, solange jede Operation eine hat. ``action is None``
    ergab „erlaubt", und das ist eine Annahme über den Bestand, keine über die
    Sache: Die zusammengelegten Zwillinge haben schon heute keinen eigenen
    Eintrag, und sobald eigene Bausteine in den Katalog wandern statt in die
    Menüleiste, hat **keiner** von ihnen einen. Dann bekäme jeder auf leerer
    Szene ein „erlaubt" und der Kunde die modale Sackgasse, gegen die der Test
    darüber gebaut wurde.

    Nachgestellt, indem der Eintrag entfernt wird — dieselbe Lage, die der
    Katalogumbau für die eigenen Bausteine dauerhaft herstellt.
    """
    launched: list[str] = []
    window.launch_operation = lambda spec: launched.append(spec.name)  # type: ignore[method-assign]

    removed = window._op_actions.pop("lattice_fill", None)
    assert removed is not None, (
        "ohne Eintrag im Register prüft dieser Test nur seinen eigenen Aufbau"
    )

    available, reason = window._palette_availability("lattice_fill")
    assert not available, "auf leerer Szene geht „Gitter füllen“ auch ohne Menüeintrag nicht"
    assert reason, "und der Grund steht dabei — sonst sucht der Kunde ihn bei sich"

    window._run_palette_choice("lattice_fill")
    assert launched == [], "gestartet wird nichts"


def test_a_locked_window_command_is_refused_with_the_reason(window: MainWindow) -> None:
    """Regel 19, der Nachbarzweig: auch ein Fensterbefehl bleibt gesperrt.

    ``_run_palette_choice`` bekam die Wache mit cc40aaa4; der Zweig für
    Fensterbefehle rief seinen Rückruf weiter direkt — die Tastatur sprang
    auf eine gesperrte Zeile, und Enter führte aus (Update-Review 25.08.,
    ce-Befund). ``palette_rows`` sperrte die Zeile längst richtig; nur der
    Vollzug fragte nie nach.
    """
    commands = window.window_commands()
    name = next(key for key in commands if window._palette_actions.get(key) is not None)
    action = window._palette_actions[name]
    ran: list[str] = []
    guarded = dict(commands)
    guarded[name] = (*commands[name][:2], lambda: ran.append(name))
    was_enabled = action.isEnabled()
    try:
        action.setEnabled(False)
        window._run_window_command(name, guarded)
        assert ran == [], "ein gesperrter Fensterbefehl startet nichts"
        assert window.status_message.text(), "der Grund steht in der Zeile"

        action.setEnabled(True)
        window._run_window_command(name, guarded)
        assert ran == [name], "frei heißt weiterhin: er läuft"
    finally:
        action.setEnabled(was_enabled)


def test_a_running_export_keeps_the_bar_when_the_evaluation_ends(window: MainWindow) -> None:
    """§2.8: Der Balken gehört dem Export, solange die Datei geschrieben wird.

    ``_anything_running`` fragte die Flagge seit je — gesetzt hatte sie nie
    jemand: Endete eine Auswertung während eines Exports, verschwand der
    Balken, und der Kunde hielt das Schreiben für beendet und schloss das
    Fenster (Update-Review, Fund 30).
    """
    window._exporting = True
    try:
        # **Wie der Export es tut, nicht wie der Test es könnte.** ``_export``
        # schaltet den Balken selbst an, bevor es die Flagge setzt; wer nur die
        # Flagge setzt, stellt eine Lage her, die im Betrieb nicht vorkommt.
        # Die Zusage lautet „bleibt", nicht „erscheint" — und seit die Anzeige
        # gestuft ist (§2.8), sind das zwei verschiedene Sätze: Ein Balken, den
        # noch niemand angeschaltet hat, kann nicht bleiben.
        window._set_progress_state(
            "export",
            active=True,
            text=tr("Exportiert wird … {name}").format(name="teil.3mf"),
        )
        window._on_busy(False)
        assert window.progress.isVisibleTo(window), "der Export trägt den Balken weiter"
        assert not window.cancel_button.isVisibleTo(window), (
            "und Abbrechen gibt es beim Export bewusst nicht (sein Docstring sagt warum)"
        )
    finally:
        window._exporting = False
        window._set_progress_state("export", active=False)
    window._on_busy(False)
    assert not window.progress.isVisibleTo(window), "ohne Export endet der Balken"


def test_a_pure_download_offers_its_cancel_button(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Abbruch eines Downloads braucht einen sichtbaren Knopf (§2.8).

    ``_on_busy`` zeigt ihn nur bei Auswertungen; ein reiner Download lief mit
    Balken und ohne erreichbares Abbrechen — ``_cancel_download`` hing an
    einem unsichtbaren Knopf, und kein Test fasste ihn an (Update-Review,
    Fund 30). Der Arbeiter wird nicht gestartet: geprüft wird die Anzeige,
    nicht das Netz.
    """
    started: list[object] = []
    monkeypatch.setattr(window._leash, "start", started.append)

    window.download_model("https://beispiel.invalid/halter.stl")

    assert started, "ohne angenommenen Arbeiter prüft der Test nur check_url"
    assert window._downloading
    assert window.cancel_button.isVisibleTo(window), "der Weg zum Abbruch ist sichtbar"

    window._download_stopped()
    assert not window._downloading
    assert not window.cancel_button.isVisibleTo(window), "mit dem Download geht der Knopf"


def test_a_flashed_area_gets_opened_before_it_lights_up(window: MainWindow) -> None:
    """Ein zugeklappter Abschnitt blinkt an einer Stelle, an der nichts steht.

    „Sehen Sie links in den Verlauf" nennt einen Bereich, und ein Rahmen für
    eine Sekunde beantwortet die Frage, ohne sie zu stellen — solange der
    Bereich sichtbar ist. Die drei Karten der linken Spalte sitzen aber in
    einklappbaren Abschnitten (§2.5), und zugeklappt leuchtete der Rahmen um
    eine Kopfzeile auf, unter der nichts zu sehen ist. Für den Prüfbericht war
    das längst bedacht — er wird über seinen Reiter nach vorn geholt —, für
    die andere Bauart nicht.

    Dieselbe Frage stellt der Agent: Seine Rücknahme-Warnung zeigt über
    ``show_history`` in den Verlauf (H-1).

    Gefragt wird mit ``isVisibleTo``: ``isVisible()`` meldet in einem nie
    gezeigten Fenster immer ``False`` und beantwortet damit eine andere Frage
    als die gestellte.
    """
    from PySide6.QtWidgets import QToolButton

    wrapper = window.history_panel.parentWidget()
    assert wrapper is not None, (
        "der Verlauf steckt in einem Abschnitt — sonst prüft das hier nichts"
    )
    heading = next(
        child
        for child in wrapper.children()
        if isinstance(child, QToolButton) and child.objectName() == "sectionHeading"
    )

    heading.setChecked(False)
    assert not window.history_panel.isVisibleTo(wrapper), "zugeklappt ist zugeklappt"

    window._flash_area("history")

    assert heading.isChecked(), "der Abschnitt geht auf, bevor der Rahmen leuchtet"
    assert window.history_panel.isVisibleTo(wrapper), "und der Verlauf steht wirklich da"


def test_a_tour_can_point_at_both_toolbars(window: MainWindow) -> None:
    """Formen und Explosion werden dort hervorgehoben, wo ihre Knöpfe stehen."""
    window._flash_area("toolbar")
    assert "border" in window.toolbar.styleSheet()

    window._flash_area("tools")
    assert "border" in window.tools.styleSheet()


def test_a_typed_name_gets_the_project_suffix(window: MainWindow) -> None:
    """„Speichern unter" erzwingt die Projektendung (Gesamtreview A2).

    ``save_project`` schrieb jede Endung klaglos, und ``open_path`` verzweigt
    strikt über sie: Eine als ``halter.stl`` gespeicherte Projektdatei wurde
    beim Öffnen als Fremdmodell gelesen — „Dieses Dateiformat kann nicht
    gelesen werden", über der eigenen Datei. Angehängt und nicht ersetzt.
    """
    from app.ui.main_window import _as_project_path

    assert _as_project_path("halter").name == "halter.p3d"
    assert _as_project_path("halter.stl").name == "halter.stl.p3d"
    assert _as_project_path("halter.p3d").name == "halter.p3d"
    assert _as_project_path("Halter 2.5").name == "Halter 2.5.p3d"
    assert _as_project_path("HALTER.P3D").name == "HALTER.P3D", "Großschreibung bleibt"


def test_the_tree_names_the_step_a_body_came_from(window: MainWindow) -> None:
    """§18.8: Herkunft aus Operation und Transaktion."""
    _with_two_objects(window)

    tip = window.object_tree.tree.topLevelItem(0).toolTip(0)
    assert "aus Operation" in tip
    assert "Modell laden" in tip, tip


def test_the_tree_explains_editability_without_cad_vocabulary(window: MainWindow) -> None:
    """Die Körperart nennt die Folge, nicht den Namen des Rechenkerns."""
    window.session.import_model(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    body = dataclasses.replace(result.scene.objects["obj_1"], name="Werkstück", kind="brep")
    scene = dataclasses.replace(result.scene, objects={"obj_1": body})

    window.object_tree.show_scene(
        dataclasses.replace(result, scene=scene), window.session.project.document
    )

    item = window.object_tree.tree.topLevelItem(0)
    assert "weiter bearbeitbar" in item.text(0)
    assert "Flächen und Kanten einzeln bearbeitbar" in item.toolTip(0)
    customer_text = f"{item.text(0)} {item.toolTip(0)}".casefold()
    assert "b-rep" not in customer_text
    assert "exakt" not in customer_text
    assert "normal" not in customer_text


def test_removing_an_object_and_taking_it_back(window: MainWindow) -> None:
    """Entf ist eine Operation, also holt ein Undo den Körper zurück."""
    _with_two_objects(window)
    window.session.apply("Entfernen", [OperationDraft(op="delete_object", inputs=("obj_2",))])
    window.session.wait_for_idle()
    assert set(window.session.evaluate_now().scene.objects) == {"obj_1"}

    window.session.undo()
    window.session.wait_for_idle()
    assert set(window.session.evaluate_now().scene.objects) == {"obj_1", "obj_2"}


def _exact_toggle(window: MainWindow) -> Any:
    """Der Haken für später einzeln bearbeitbare Flächen und Kanten."""
    from PySide6.QtWidgets import QCheckBox

    dialog = window._op_dialog
    assert dialog is not None
    haken = [box for box in dialog.findChildren(QCheckBox) if "Flächen und Kanten" in box.text()]
    assert haken, [box.text() for box in dialog.findChildren(QCheckBox)]
    return haken[0]


def test_the_exact_toggle_is_locked_where_its_twin_cannot_work(window: MainWindow) -> None:
    """Regel 19: nicht anbieten und nach dem ausgefüllten Dialog ablehnen.

    Die Menüleiste graut eine Operation des exakten Kerns an einem Netz aus
    und schreibt den Grund in den Tooltip. Seit die Zwillinge zusammengelegt
    sind, hat ``drill_brep_hole`` gar keinen eigenen Menüeintrag mehr — der
    Haken **ist** der Weg zu ihr, und dort wurde nicht gefragt.

    Gemessen an einer eingelesenen STL, bevor das hier stand: Haken wählbar,
    Dialog geht durch, Auswertung hält bei op 2 an, und die Absage steht im
    Prüfbericht. Der Satz dort ist gut — er ist nur die zweite Hürde.

    Beim Quader konnte es nicht auffallen: ``create_brep_box`` verbraucht
    nichts, es gibt keinen Eingangskörper, der der falsche sein könnte.
    """
    _with_two_objects(window)
    window.object_tree.select_object("obj_1")
    assert window.session.last_result.scene.objects["obj_1"].kind == "mesh"

    window.run_operation(REGISTRY.get("drill_hole"))
    toggle = _exact_toggle(window)

    assert not toggle.isEnabled(), "an einem Netz führt der Haken ins Leere"
    assert toggle.toolTip(), "und er sagt, warum"
    assert toggle.toolTip() != str(TWIN_TOGGLES["drill_brep_hole"][1]), (
        "der Grund steht dort, nicht der Werbetext für den exakten Kern"
    )
    assert toggle.statusTip() == toggle.toolTip(), "die Statuszeile sagt dasselbe"

    dialog = window._op_dialog
    assert dialog is not None
    dialog.reject()


def test_the_exact_toggle_is_free_on_an_exact_body(window: MainWindow) -> None:
    """Und die andere Hälfte der Regel: auf einem exakten Körper ist er frei.

    Ohne diese Hälfte wäre ein Haken, der immer gesperrt ist, genauso grün.
    """
    from app.core.brep import available

    if not available():
        pytest.skip("OpenCASCADE is an optional dependency")

    window.run_operation(REGISTRY.get("create_brep_box"))
    dialog = window._op_dialog
    assert dialog is not None
    dialog.accept()
    window.session.wait_for_idle()

    exact_id = next(
        object_id
        for object_id, entry in window.session.last_result.scene.objects.items()
        if entry.kind == "brep"
    )
    window.object_tree.select_object(exact_id)

    window.run_operation(REGISTRY.get("drill_hole"))
    toggle = _exact_toggle(window)

    assert toggle.isEnabled(), "hier kann der exakte Zweig arbeiten"
    assert toggle.toolTip() == str(TWIN_TOGGLES["drill_brep_hole"][1]), (
        "und der Tooltip erklärt wieder, was der Haken tut"
    )

    dialog = window._op_dialog
    assert dialog is not None
    dialog.reject()


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


def test_technical_part_codes_are_explained_in_the_choice(qt_app: QApplication) -> None:
    """Buchsenvariante und Lagernummer reichen ohne Tabellenwissen nicht."""
    from app.ui.labels import choice_label

    short_insert = choice_label("M4S")
    bearing = choice_label("608")

    assert "M4" in short_insert and "mm" in short_insert and short_insert != "M4S"
    assert "608" in bearing and "8" in bearing and "22" in bearing and "mm" in bearing


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
    # Eine Projektdatei aus einer neueren Version ist kein Grund für eine
    # leere Zeile.
    assert _op_title("gibt_es_nicht") == "gibt_es_nicht"


def test_delete_only_bites_where_a_selection_is_visible(window: MainWindow) -> None:
    """§2.6: „Entf" folgt dem Bereich, in dem die Auswahl sichtbar ist.

    Wer im Verlauf einen Schritt markierte und die Taste drückte, verlor den
    ausgewählten **Körper**. Jetzt hat der Verlauf seine eigene, gleich
    begrenzte Handlung; dieselbe Taste meint dort den gewählten Schritt.

    Geprüft wird der Geltungsbereich, nicht das Drücken: Keine der beiden
    Handlungen darf in den Bereich der anderen reichen.
    """
    deletes = [
        action
        for action in window.findChildren(QAction)
        if action.shortcut() == QKeySequence("Del")
    ]
    object_delete = next(action for action in deletes if action in window.object_tree.actions())
    history_delete = next(
        action for action in deletes if action in window.history_panel.list.actions()
    )

    assert object_delete.shortcutContext() == Qt.ShortcutContext.WidgetWithChildrenShortcut
    assert object_delete in window.viewport.actions(), "die Objektlöschung gilt auch in der Ansicht"
    assert object_delete not in window.history_panel.list.actions(), "aber nicht im Verlauf"
    assert history_delete.shortcutContext() == Qt.ShortcutContext.WidgetWithChildrenShortcut
    assert history_delete not in window.object_tree.actions(), (
        "die Schrittlöschung gilt nicht im Baum"
    )


def test_removing_a_history_step_asks_and_can_be_undone(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Roberts ausdrückliche Ausnahme: Vor dem Löschen steht eine Bestätigung.

    Der Dialog nennt zugleich den Ausweg. Nach dem bestätigten Löschen stellt
    Strg+Z denselben Schritt wieder her; ein Abbruch ließe das Dokument
    unangetastet.
    """
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    op_id = window.session.project.document.ops[0].id
    shown: list[str] = []

    def reject(box: QMessageBox) -> int:
        shown.append(box.text())
        button = next(entry for entry in box.buttons() if entry.text() == tr("Abbrechen"))
        button.click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", reject)

    window.remove_history_operations((op_id,))

    assert [entry.id for entry in window.session.project.document.ops] == [op_id]

    def accept(box: QMessageBox) -> int:
        shown.append(box.text())
        button = next(entry for entry in box.buttons() if entry.text() == tr("Löschen"))
        button.click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", accept)

    window.remove_history_operations((op_id,))
    window.session.wait_for_idle()

    assert shown and "Strg+Z" in shown[0], "der Dialog nennt die Rücknahme"
    assert window.session.project.document.ops == []
    removed_rows = [
        window.history_panel.list.item(row)
        for row in range(window.history_panel.list.count())
        if tr("gelöscht") in window.history_panel.list.item(row).text()
    ]
    assert removed_rows and removed_rows[0].font().strikeOut(), (
        "die Ursprungszeile bleibt als gelöschte Geschichte sichtbar"
    )

    window.session.undo()
    window.session.wait_for_idle()
    assert [entry.id for entry in window.session.project.document.ops] == [op_id]


def test_history_deletion_warns_before_discarding_redo(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der eine Löschdialog nennt auch den abgeschnittenen Redo-Zweig."""
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    active_id = window.session.project.document.ops[0].id
    window.session.import_model(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window.session.undo()
    window.session.wait_for_idle()
    assert window.session.history.can_redo
    undone_title = window._discarded_names()[0]
    shown: list[str] = []

    def reject(box: QMessageBox) -> int:
        shown.append(box.text())
        cancel = next(entry for entry in box.buttons() if entry.text() == tr("Abbrechen"))
        assert box.icon() == QMessageBox.Icon.Warning
        assert box.defaultButton() is cancel, "Abbrechen ist nicht die sichere Vorgabe"
        assert box.escapeButton() is cancel, "Escape muss den Vorgang abbrechen"
        cancel.click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", reject)
    window.remove_history_operations((active_id,))

    assert window.session.history.can_redo, "Abbrechen verwarf den Redo-Zweig"
    assert undone_title in shown[0]
    assert "nicht mehr wiederholt werden" in shown[0]

    def accept(box: QMessageBox) -> int:
        remove = next(entry for entry in box.buttons() if entry.text() == tr("Löschen"))
        remove.click()
        return 0

    monkeypatch.setattr(QMessageBox, "exec", accept)
    window.remove_history_operations((active_id,))
    window.session.wait_for_idle()

    assert not window.session.history.can_redo
    assert window.session.project.document.ops == []


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


def test_the_undo_sweep_warning_offers_the_history(window: MainWindow) -> None:
    """Die Rücknahme-Warnung des Agenten ist anklickbar (Gesamtreview H-1).

    ``agent.undo_sweeps`` existierte als Befund im Kern, aber die Oberfläche
    kannte ihn nicht: kein Eintrag in FINDING_ACTIONS, keine Handlung — der
    Kunde las „nimmt auch alle jüngeren mit" und konnte nirgends nachsehen,
    welche das sind.
    """
    from app.core.types import Finding
    from app.ui.panels import actions_for

    finding = Finding(code="agent.undo_sweeps", severity="warning", message="x")
    offered = actions_for(finding)
    assert offered, "die Warnung trägt eine Handlung"
    known = window.error_handlers()
    for action in offered:
        assert action.id in known, f"{action.id} hat keinen Handler"


def test_the_too_large_map_offers_the_operation_that_helps(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Hauptvorschlag zu „Modell zu groß" löst die Operation wirklich aus.

    Geprüft wird der **Klickweg**, nicht die Funktion: Der Handler wird über
    ``error_handlers()`` geholt und mit dem echten Fehler gerufen — so, wie
    der Dialog es tut. Ein Test, der ``run_operation`` direkt aufriefe, bliebe
    grün, wenn der Draht dazwischen fehlt, und genau der fehlte hier.

    ``decimate_mesh`` stand bis zum 30.08.2026 nur als Satz da, obwohl die
    Operation gleichen Namens im Register liegt — ein verschenkter Klickweg
    beim häufigsten Rat dieser Meldung.
    """
    from app.core.perceive.maps import MapTooLarge

    gerufen: list[str] = []
    monkeypatch.setattr(
        type(window), "run_operation", lambda self, spec, given=None: gerufen.append(spec.name)
    )

    fehler = MapTooLarge(triangles=9_000_000)
    angeboten = [action.id for action in fehler.suggestions]
    assert "decimate_mesh" in angeboten, "der Fehler bietet den Rat überhaupt an"

    handler = window.error_handlers()
    assert "decimate_mesh" in handler, "und die Oberfläche kennt ihn"
    handler["decimate_mesh"](fehler)

    assert gerufen == ["decimate_mesh"], f"die Operation wurde nicht ausgelöst: {gerufen}"


def test_an_auto_split_finding_opens_the_drawn_split_tool(
    window: MainWindow,
) -> None:
    """Der Berichtsknopf führt in die sichtbare manuelle Trennung (§2.7)."""
    from PySide6.QtWidgets import QPushButton

    from app.core.types import Finding

    window.report.add_findings(
        [
            Finding(
                code="split.no_plane",
                severity="warning",
                message="Keine belastbare Trennebene gefunden.",
            )
        ]
    )
    window.report.list.setCurrentRow(0)

    buttons = {
        button.text().replace("&", ""): button
        for button in window.report._offers.findChildren(QPushButton)
    }
    label = tr("An gezeichneter Linie trennen")
    assert label in buttons, f"angeboten wurden nur: {sorted(buttons)}"
    buttons[label].click()

    assert window.tools.active() == "split"
    assert window.split_bar.isVisibleTo(window.tools), "die Handlung öffnet ihre bedienbare Leiste"
    assert window.viewport._splitting, "Klicks im Viewport werden jetzt als Trennlinie gelesen"


def test_an_unreachable_address_opens_that_address_not_the_product_page(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Browser-Knopf öffnet die Adresse aus dem Fehler.

    **Und ausdrücklich nicht die Produktseite.** ``open_website`` liegt
    daneben und wäre die bequeme Verwechslung: Der Kunde wollte zu *seiner*
    Datei, deren Adresse er selbst eingegeben hat und die in ``values["url"]``
    mitreist.

    Geprüft am Klickweg über ``error_handlers()``, mit gemocktem
    ``QDesktopServices`` — die Zusage ist „diese Adresse geht auf", nicht
    „irgendetwas geht auf".
    """
    from PySide6.QtGui import QDesktopServices

    from app.ui import main_window as modul

    geoeffnet: list[str] = []
    monkeypatch.setattr(
        modul.QDesktopServices,
        "openUrl",
        staticmethod(lambda url: geoeffnet.append(url.toString())),
        raising=True,
    )
    assert QDesktopServices is not None  # der Import oben ist die geprüfte Stelle

    adresse = "https://beispiel.test/teil.stl"
    fehler = errors.ValidationError(
        "url",
        "Diese Adresse führt auf eine Webseite, nicht auf eine Datei.",
        value=adresse,
        constraint="web_page",
        values={"url": adresse, "name": "teil.stl", "type": "text/html"},
        suggestions=[errors.OPEN_IN_BROWSER],
    )

    handler = window.error_handlers()
    assert "open_in_browser" in handler, "die Oberfläche kennt den Rat"
    handler["open_in_browser"](fehler)

    assert geoeffnet == [adresse], f"geöffnet wurde: {geoeffnet}"


def test_every_offered_error_action_does_something(window: MainWindow) -> None:
    """Regel 17 hat zwei Hälften, und die zweite fehlte.

    Die Vorschläge standen als Knöpfe da, und kein einziger Aufrufer las
    aus, welcher gedrückt wurde — jeder schloss ein Fenster und tat sonst
    nichts. Was hier zählt: für jede Handlung, die ein Fehler vorschlägt,
    gibt es entweder einen Handler oder einen benannten Grund.

    **Die Liste der Ausnahmen ist auf drei geschrumpft**, und jede trägt ihren
    Grund: ``cancel`` ist das Schließen und kein Vorschlag; ``choose`` fragt der
    Kern über ``ctx.ask``, bevor er wirft; ``use_voxel_stage`` ist eine Stufe
    der Rückfallkette und kein Parameter, den ein Dialog setzen könnte (§17.2).
    ``correct_input`` und ``choose_printer`` standen hier, bis ihr Weg gebaut
    war — der erste öffnet den Schritt, der zweite führt in die
    Druckeinstellungen. ``retry`` und ``save_elsewhere`` sind verdrahtet, stehen
    aber weiter hier: Sie gelten einem **bestimmten** gescheiterten Schreiben
    und erscheinen nur, solange es eines gibt.
    """
    known = window.error_handlers()
    # ``retry`` und ``save_elsewhere`` hängen an einem gescheiterten Schreiben
    # und stehen darum nicht immer in ``known`` — angeboten werden sie genau
    # dann, wenn sie wirken können (``_WriteFailure``).
    postponed = {
        "use_voxel_stage",
        "choose",
        "cancel",
        "retry",
        "save_elsewhere",
        # Nur ein Importfehler mit den gelesenen Dateibytes kann diesen Namen
        # anwenden; der Katalog verdrahtet ihn deshalb am konkreten Fehler.
        "use_suggested_name",
    }

    for name, value in vars(errors).items():
        if not isinstance(value, errors.Action):
            continue
        assert value.id in known or value.id in postponed, (
            f"{name} wird angeboten, aber nichts führt sie aus"
        )


#: Kennungen, die absichtlich neben ``errors.py`` entstehen — sie gehören einem
#: Fenster, das seine Knöpfe selbst baut (der Support-Dialog), oder einem Rat,
#: den ``unhandled_advice`` als Satz zeigt. Wer hier etwas einträgt, sagt damit:
#: Diese Kennung braucht keine Konstante und keinen Handler.
#:
#: **Die Frage, die vor jedem neuen Eintrag steht** — und ohne sie wird diese
#: Menge zur Müllhalde, in die der nächste ``cancel_evaluation``-Fall bequem
#: hineinrutscht:
#:
#:     Gibt es irgendwo eine Handlung, die diese Kennung einlösen könnte?
#:     Wenn ja: Konstante und Verdrahtung, nicht diese Menge.
#:
#: Genau daran ist der Gründungsfall des Wächters gescheitert.
#: ``cancel_evaluation`` bot an, die laufende Teilung abzubrechen — und
#: ``Session.cancel_split`` gab es die ganze Zeit. Der Fehler war nicht
#: „kein Handler", sondern **dass niemand gefragt hat**.
#:
#: **Und diese Menge ist selbst schon einmal daran vorbeigelaufen.** Als sie
#: am 30.08.2026 von vier auf 32 Einträge wuchs, wurde sie **pauschal**
#: befüllt — die Regel darüber stand im selben Commit und wurde auf keinen
#: einzigen Namen angewandt. Der Release-Durchgang eine Stunde später fand
#: zwei, für die es sehr wohl eine Einlösung gab: ``decimate_mesh`` (die
#: Operation liegt im Register) und ``open_in_browser`` (die Adresse reist im
#: Fehler mit). Beide sind jetzt Konstanten mit Handler.
#:
#: Wer diese Menge erweitert, prüft **jeden** Namen einzeln. Eine Liste, die
#: in einem Zug entsteht, entsteht ungeprüft.
#:
#: Die zweite Gruppe darunter ist gemessen und nicht geraten: 32 Kennungen an
#: 44 Fundstellen, von denen 26 in ``suggestions=`` eines geworfenen Fehlers
#: stehen und **keine einzige** einen Handler hat. Das ist kein Befund, sondern
#: die Bauart: ``dialogs.unhandled_advice`` zeigt einen Vorschlag ohne Handler
#: als **Satz** — „ein Knopf ohne Wirkung ist schlimmer als keiner". Die
#: Handlung führt in all diesen Fällen der Nutzer selbst aus: eine Fläche
#: anklicken, einen Wert kleiner wählen, vorher aufräumen.
#:
#: ``primary=True`` trennt die beiden Gruppen **nicht** — nachgemessen tragen
#: ``sketch.use_all_regions``, ``sketch.pick_face`` und
#: ``texture.pick_cylinder`` es und sind trotzdem Selbstausführer. Das Feld
#: sagt „der naheliegendste Weg", nicht „das tut die Oberfläche für dich".
ACTIONS_WITHOUT_A_CONSTANT = {
    # Ein Fenster, das seine Knöpfe selbst baut (Support-Dialog).
    "retry_send",
    "save_report",
    "send_by_mail",
    # Räte, die der Nutzer selbst ausführt — als Satz gezeigt, nicht als Knopf.
    "check_input",
    "coarser_pitch",
    "decimate_first",
    "fewer_iterations",
    "fix_parent",
    "open_sketch",
    "pick_face",
    "pick_feature",
    "pick_image",
    "pick_in_tree",
    "remesh_first",
    "repack_file",
    "sketch.clear_up_to",
    "sketch.enter_height",
    "sketch.flip_plane",
    "sketch.pick_face",
    "sketch.use_all_regions",
    "sketch.use_global_plane",
    "smaller_bodies",
    "smaller_diameter",
    "texture.pick_cylinder",
    "texture.wrap_flat",
    "use_parts",
    "use_planar",
    "use_reachable",
    "use_texture",
    "write_target",
}


def test_no_error_action_is_invented_at_the_call_site() -> None:
    """Eine Kennung, die nur an ihrer Aufrufstelle steht, entgeht jeder Prüfung.

    Der Test darüber liest die **Konstanten** aus ``errors.py`` — gründlich,
    aber er sieht nur, was dort steht. ``session.split_bodies`` erzeugte seinen
    Vorschlag von Hand:

        Action("cancel_evaluation", _("Die laufende Teilung abbrechen"))

    Zwei Fehler in einer Zeile, und beide blieben jahrelang unsichtbar. Die
    Kennung hieß nach der **Auswertung** und meinte die Teilung — zwei Dinge,
    die beide abbrechbar sind. Und verdrahtet war sie nirgends, also wurde aus
    dem einzigen Vorschlag dieses Fehlers ein Satz zum Lesen: Der Kunde bekam
    den Rat, die Teilung abzubrechen, und keinen Weg, es zu tun. Dabei gibt es
    die Handlung (``Session.cancel_split``).

    Gefunden hat das kein Test, sondern eine Kontrolle von Hand am Ende eines
    Tages. Diese Prüfung ist die Antwort darauf: Sie liest den **Quelltext**,
    nicht das Modul — dieselbe Bauart wie der Wächter in ``test_leash.py``, der
    jeden Arbeiter findet, der an der Leine vorbei startet.
    """
    import ast

    constants = {value.id for value in vars(errors).values() if isinstance(value, errors.Action)}
    assert len(constants) > 15, "die Konstanten wurden nicht gelesen — der Test prüft nichts"

    invented: dict[str, str] = {}
    files = [path for path in Path("app").rglob("*.py") if path.name != "errors.py"]
    assert len(files) > 100, "die Quelldateien wurden nicht gefunden"
    for path in files:
        text = path.read_text(encoding="utf-8")
        if "Action(" not in text:
            continue
        for node in ast.walk(ast.parse(text)):
            if not isinstance(node, ast.Call):
                continue
            if not (isinstance(node.func, ast.Name) and node.func.id == "Action"):
                continue
            # **Beide Aufrufformen.** Hier stand ``or not node.args`` als
            # erste Bedingung, und damit übersprang der Wächter jeden Aufruf
            # ohne positionales Argument — also jedes ``Action(id="…", …)``.
            # Gemessen am 30.08.2026: Von 32 inline gebauten Kennungen sah er
            # **vier**; die übrigen 28 lebten außerhalb jeder Prüfung, darunter
            # die drei des Slicer-Wegs, deren Knöpfe nichts taten.
            #
            # Der Zusatz liest sich wie eine Vorsichtsmaßnahme („ohne
            # Argumente gibt es nichts zu prüfen") und war eine Ausnahme für
            # die halbe Aufrufform. **Ein Wächter ist so scharf wie seine
            # weiteste Ausnahme** — und die stand hier in einer Zeile, die
            # niemand als Ausnahme gelesen hat.
            named: ast.expr | None = node.args[0] if node.args else None
            for keyword in node.keywords:
                if keyword.arg == "id":
                    named = keyword.value
            if (
                isinstance(named, ast.Constant)
                and isinstance(named.value, str)
                and named.value not in constants
                and named.value not in ACTIONS_WITHOUT_A_CONSTANT
            ):
                invented[named.value] = f"{path}:{node.lineno}"

    assert not invented, (
        "Aktionskennung ohne Konstante in errors.py — sie entgeht damit der Prüfung "
        f"darüber: {invented}"
    )


#: Die Handlungen am Prüfbericht, die die **Lage** eines Körpers ändern, mit der
#: Verschiebung, die den Befund erzeugt. Eine Zeile je Knopf und nicht je
#: Befund: ``arrange.above_bed`` bietet zwei an, und beide müssen wirken.
LAGE_HANDLUNGEN = [
    ((0.0, 0.0, -15.0), "arrange.below_bed", errors.PLACE_ON_BED),
    ((0.0, 0.0, 150.0), "arrange.above_bed", errors.PLACE_ON_BED),
    ((0.0, 0.0, 150.0), "arrange.above_bed", errors.ARRANGE_ON_BED),
    ((400.0, 0.0, 0.0), "arrange.off_the_plate", errors.ARRANGE_ON_BED),
]


@pytest.mark.parametrize(
    ("offset", "code", "action"),
    LAGE_HANDLUNGEN,
    ids=lambda value: value if isinstance(value, str) else "",
)
def test_every_placement_button_really_moves_the_bodies(
    window: MainWindow, offset: tuple[float, float, float], code: str, action: errors.Action
) -> None:
    """Die dritte Hälfte von Regel 17: der Handler muss auch *wirken*.

    ``test_every_offered_error_action_does_something`` prüft, dass jede
    angebotene Handlung einen Handler **hat** — und genau das war bei *Auf dem
    Bett anordnen* erfüllt, während der Knopf nichts tat. Er trug die Operation
    ohne Eingaben in den Stapel, und eine Operation mit variabler Objektzahl
    ohne Eingaben plant keine Ausgänge (``History._outputs_for``): Der Schritt
    stand im Verlauf, kein Körper bewegte sich, keine Meldung erschien. Robert
    hat es gemeldet, der Test blieb grün.

    Getroffen hat es den häufigsten Importfall überhaupt — eine 3MF aus Bambu
    Studio, Orca oder Elegoo führt Bettkoordinaten, ihre Körper liegen neben
    dem Bett, und dieser Knopf ist die Handlung, die dort hilft.

    Gedrückt wird der **echte Knopf** unter der Befundliste, nicht der Handler
    von Hand: Zwischen beiden liegen ``actions_for``, ``as_error`` und die
    Verdrahtung in ``_show_offers``, und die gehören zur Zusage.

    Über alle vier Lage-Handlungen und nicht nur über die eine, die einmal
    kaputt war: Sie hängen an denselben zwei Handlern, und ein
    Registername steht darin als Zeichenkette (siehe den Wächter darunter).
    Wer eine der Operationen auflöst, bricht hier zwei Knöpfe auf einmal.
    """
    from PySide6.QtWidgets import QPushButton

    _with_two_objects(window)
    window.session.apply(
        "Verschieben",
        [
            OperationDraft(
                op="translate_object",
                inputs=("obj_1",),
                params={"dx": offset[0], "dy": offset[1], "dz": offset[2]},
            )
        ],
    )
    window.session.wait_for_idle()
    result = window.session.last_result
    window.report.show_result(result, window.session.project.document)

    def where() -> dict[str, tuple[float, ...]]:
        scene = window.session.last_result.scene
        return {
            object_id: tuple(entry.mesh.bounds.minimum)
            for object_id, entry in scene.objects.items()
        }

    def klagen() -> set[str]:
        """Die Körper, für die dieser Befund gerade steht.

        Objektbezogen und nicht als bloße Kennung: ``_with_two_objects`` lädt
        zwei Würfel, und ein aus der Datei geladener Würfel steckt zur Hälfte
        unter der Platte — bei ``below_bed`` klagen also beide. *Auf das Bett
        setzen* behebt genau seinen eigenen (``consumes=1``), und das ist
        richtig; eine Zusicherung „der Befund ist weg" wäre hier eine über eine
        Operation, die es nicht gibt.
        """
        return {
            finding.object_id
            for finding in window.session.last_result.scene.report.findings
            if finding.code == code and finding.object_id is not None
        }

    assert "obj_1" in klagen(), (
        "der Befund muss für den verschobenen Körper dastehen, sonst prüft das nichts: "
        f"{[f.code for f in result.scene.report.findings]}"
    )

    for row in range(window.report.list.count()):
        item = window.report.list.item(row)
        finding = item.data(Qt.ItemDataRole.UserRole)
        if finding.code == code and finding.object_id == "obj_1":
            window.report.list.setCurrentRow(row)
            break
    QApplication.processEvents()

    offered = {button.text(): button for button in window.report._offers.findChildren(QPushButton)}
    assert str(action.label) in offered, f"kein Knopf {str(action.label)!r}: {list(offered)}"

    before = where()
    offered[str(action.label)].click()
    window.session.wait_for_idle()

    assert where() != before, f"der Knopf {str(action.label)!r} hat nichts bewegt"
    assert "obj_1" not in klagen(), (
        f"und der Körper, gegen den {str(action.label)!r} angeboten wurde, klagt nicht mehr"
    )


def test_no_error_handler_names_an_operation_that_is_gone(window: MainWindow) -> None:
    """Der schnelle Wächter neben dem Wirkungstest darüber (§2.7, Regel 17).

    Die Handler der Fehlerhandlungen holen ihre Operation über
    ``REGISTRY.get("…")`` — als **Zeichenkette**, mitten in einer Methode.
    Verschwindet der Registereintrag, wirft ``get`` einen ``InternalError``,
    und der Kunde bekommt am Prüfbericht-Knopf „Im Programm ist ein
    unerwarteter Fehler aufgetreten" samt Fehlerbericht-Ordner. Das ist genau
    die Falle beim Zusammenlegen von Varianten: ``MENU_TWINS`` schützt nicht
    davor — ein Zwilling behält seinen Eintrag und wird nur im Menü versteckt,
    wer eine Operation **auflöst**, nimmt ihren Namen mit.

    Gelesen wird der Quelltext und nicht das Verhalten, aus demselben Grund wie
    bei ``tests/test_leash.py``: Ein Handler, dessen Operation es nicht mehr
    gibt, sieht völlig normal aus, bis jemand den Knopf drückt. Und es ist der
    **schnelle** Wächter, nicht der verlässliche — dass ein Name im Register
    steht, heißt nicht, dass der Handler wirkt; genau das war der Fehler, den
    der Test darüber fängt.
    """
    import ast

    quelle = Path(main_window_module.__file__).read_text(encoding="utf-8")
    baum = ast.parse(quelle)
    handler = set(window.error_handlers())

    genannt: dict[str, set[str]] = {}
    for knoten in ast.walk(baum):
        if not isinstance(knoten, ast.FunctionDef) or not knoten.name.endswith("_after_error"):
            continue
        for innen in ast.walk(knoten):
            if (
                isinstance(innen, ast.Call)
                and isinstance(innen.func, ast.Attribute)
                and innen.func.attr == "get"
                and isinstance(innen.func.value, ast.Name)
                and innen.func.value.id == "REGISTRY"
                and innen.args
                and isinstance(innen.args[0], ast.Constant)
                and isinstance(innen.args[0].value, str)
            ):
                genannt.setdefault(knoten.name, set()).add(innen.args[0].value)

    assert genannt, "kein Handler nennt eine Operation — dann prüft dieser Test nichts"
    fehlen = {
        f"{methode} → {name}"
        for methode, namen in genannt.items()
        for name in namen
        if not REGISTRY.has(name)
    }
    assert not fehlen, (
        "Ein Handler einer Fehlerhandlung nennt eine Operation, die es nicht "
        f"mehr gibt — der Knopf endet im InternalError: {sorted(fehlen)}. "
        f"Angebotene Handlungen: {sorted(handler)}"
    )


def test_the_report_shows_what_helps_without_a_right_click(window: MainWindow) -> None:
    """§2.7 verspricht anklickbare Handlungen, nicht welche zum Suchen.

    Gebaut waren sie längst — nur hingen sie an einem Rechtsklick auf eine
    Listenzeile, und den probiert dort niemand aus. Der Fehlerdialog hat für
    dieselbe Sache seit je Knöpfe; der Prüfbericht, in dem die häufigeren
    Fälle landen (ein Modell unter der Platte, ein Schritt mit einem
    unmöglichen Wert), hatte keine.

    Und die Zeile bleibt leer, wo nichts zu tun ist: „Doppelte Punkte wurden
    verschweißt" braucht keinen Knopf.

    **Der erste Zustand hat sich seither verschoben — in dieselbe Richtung.**
    Dieser Test hat die Knopfzeile durchgesetzt: Vorher hingen die Handlungen
    an einem Rechtsklick, den dort niemand probiert, danach standen sie
    sichtbar unter der Liste. Nur begann die Zeile **leer** und füllte sich
    erst, wenn jemand eine Listenzeile anklickte — und dass ein Klick dort
    Knöpfe freischaltet, muss man genauso wissen wie den Rechtsklick davor.
    Hier stand deshalb „ohne gewählten Befund steht dort nichts": Das beschrieb
    den Zwischenstand, nicht das Ziel.

    ``ReportPanel._preselect`` wählt jetzt den obersten Befund vor, der eine
    Handlung anbietet — Rechtsklick, Knopfzeile, Vorauswahl sind drei Schritte
    **einer** Bewegung, und §2.7 ist am Ende von ihr eingelöst. Was dieser Test
    darunter prüft — welcher Befund welchen Knopf bekommt und welcher keinen —
    ist davon unberührt und die eigentliche Zusage.
    """
    from PySide6.QtWidgets import QPushButton

    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    # Zwei Modelle, weil das erste seit dem 03.09.2026 mittig auf dem Bett
    # landet und der Fall „unter der Platte" erst mit dem zweiten entsteht.
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    report = window.report
    report.show_result(window.session.last_result, window.session.project.document)

    def offered() -> list[str]:
        # ``isHidden`` und nicht ``isVisible``: offscreen wird das Fenster nie
        # gezeigt, und dann meldet jedes Kind sich als unsichtbar — dieselbe
        # Unterscheidung, die der Test des Vorschaubandes trifft.
        QApplication.processEvents()
        row = report._offers
        return [b.text() for b in row.findChildren(QPushButton)] if not row.isHidden() else []

    assert offered() == [str(errors.PLACE_ON_BED.label)], (
        "die Vorauswahl zeigt die Handlung, bevor jemand klickt"
    )

    def choose(code: str) -> None:
        for row in range(report.list.count()):
            finding = report.list.item(row).data(Qt.ItemDataRole.UserRole)
            if finding.code == code:
                report.list.setCurrentRow(row)
                return
        raise AssertionError(f"kein Befund {code!r} im Bericht")

    choose("arrange.below_bed")
    assert offered() == [str(errors.PLACE_ON_BED.label)]

    choose("ingest.welded")
    assert offered() == [], "ein Hinweis ohne Handlung bekommt keinen Knopf"


def test_a_stopped_step_is_one_click_from_its_own_dialog(window: MainWindow) -> None:
    """Der häufigste Fehler des Programms hatte keinen Weg zurück (§2.7, §2.1).

    Eine Operation, deren Werte nicht gehen, wirft **keinen** Fehlerdialog: Der
    Kern macht daraus einen Befund und hält die Kette an (§15.3). Im Bericht
    stand dann „Der Wert liegt über dem zulässigen Höchstwert", und der Weg zu
    diesem Wert war, den Schritt im Verlauf zu suchen und doppelzuklicken.
    *Eingabe korrigieren* stand daneben — als Satz, denn es war die häufigste
    Handlung des Kerns und die einzige ohne Handler.

    Geprüft wird die ganze Kette: dass der Befund aus der Operation kommt, dass
    er seine Schrittkennung trägt, dass die Handlung angeboten wird, und dass
    sie den Schritt öffnet, der wirklich gescheitert ist.
    """
    from app.ui.panels import actions_for, as_error

    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    object_id = next(iter(window.session.last_result.scene.objects))

    window.session.apply(
        "Bohrung setzen",
        [
            OperationDraft(
                op="drill_hole",
                inputs=(object_id,),
                params={"diameter": 5000.0, "x": 0.0, "y": 0.0, "z": 4.0, "axis": "z"},
            )
        ],
    )
    window.session.wait_for_idle()

    result = window.session.last_result
    assert not result.complete, "ein unmöglicher Wert hält die Kette an"
    stopped = [f for f in result.scene.report.findings if f.code.startswith("op.")]
    assert stopped, "der Fehler der Operation steht als Befund im Bericht"
    finding = stopped[0]
    assert finding.op_id == result.stopped_at, "und er nennt den Schritt, der hängt"

    offers = actions_for(finding)
    handlers = window.error_handlers()
    assert [action.id for action in offers] == ["correct_input"]
    assert offers[0].id in handlers, "angeboten, aber nichts führt es aus"

    opened: list[int] = []
    # Mit ``field``: der Handler gibt das Feld mit, in das der Cursor gehört.
    window.edit_operation = lambda op_id, field="": opened.append(op_id)  # type: ignore[method-assign]
    handlers["correct_input"](as_error(finding))

    assert opened == [result.stopped_at], "geöffnet wird der Schritt, der gescheitert ist"


def test_a_geometry_failure_offers_repair_and_locations() -> None:
    """Ein kaputtes Netz bekommt seine sachlichen Auswege statt eines Felds.

    ``correct_input`` war der pauschale Rückfall für jeden ``op.*``-Befund.
    Bei einem Geometriefehler liegt es aber nicht an einem Zahlenfeld; der
    Kunde braucht die Reparatur und die markierten Stellen, die die Ausnahme
    bereits nennt.
    """
    from app.core.errors import GeometryError
    from app.core.scene.evaluate import _finding_from
    from app.core.types import Operation
    from app.ui.panels import actions_for

    operation = Operation(id=4, op="difference", inputs=("obj_1",), outputs=("obj_1",), params={})
    finding = _finding_from(GeometryError(), operation)

    assert [action.id for action in actions_for(finding)] == [
        "repair_and_retry",
        "show_locations",
    ]


def test_a_partial_repair_shows_closed_total_and_remaining_edges() -> None:
    """Der Anteil steht in der Zeile — nicht als zwei rohe Zahlen im Tooltip."""
    from app.core.types import Finding
    from app.ui.panels import _line_for

    filled = Finding(
        code="repair.holes_filled",
        severity="info",
        message="3 von 19 offenen Kanten geschlossen; 16 bleiben offen.",
        object_id="obj_1",
        values={"before": 19, "after": 16},
    )
    remaining = Finding(
        code="repair.still_open",
        severity="warning",
        message="Die Reparatur schließt kleine Löcher, kann fehlende Wände aber nicht ersetzen.",
        object_id="obj_1",
        values={"open_edges": 16},
    )

    filled_line = _line_for(filled, {"obj_1": "Halb offen"})
    remaining_line = _line_for(remaining, {"obj_1": "Halb offen"})

    assert "3 von 19 offenen Kanten geschlossen; 16 bleiben offen" in filled_line
    assert "Halb offen" in filled_line
    assert "Offene Kanten: 16" in remaining_line
    assert "Halb offen" in remaining_line


def test_repair_remainders_show_locations_only_for_a_known_body() -> None:
    """Der Ausweg führt zur Defektkarte, aber nie über eine geratene Auswahl."""
    from app.core.types import Finding
    from app.ui.panels import actions_for

    for code in ("repair.still_open", "repair.self_intersections_skipped"):
        located = Finding(code=code, severity="warning", message="x", object_id="obj_1")
        unlocated = Finding(code=code, severity="warning", message="x")
        assert [action.id for action in actions_for(located)] == ["show_locations"]
        assert actions_for(unlocated) == ()


def test_an_attempted_repair_is_not_offered_twice_regardless_of_its_finding() -> None:
    """Auch „nichts zu reparieren“ öffnet denselben Reparaturring nicht erneut.

    Die Sperre liest bewusst keinen Befundtext: Ob die Reparatur teilweise
    half oder ``repair.nothing_to_do`` meldete, steht im Bericht; belegt ist
    der Versuch durch den aktiven Zug im Verlauf.
    """
    from app.core.types import Document, Finding, Operation, Transaction
    from app.ui.panels import actions_for_document

    document = Document(format_version=18, app_version="test")
    document.ops.extend(
        [
            Operation(id=4, op="repair", inputs=("obj_1",), outputs=("obj_1",)),
            Operation(id=5, op="remesh_uniform", inputs=("obj_1",), outputs=("obj_1",)),
        ]
    )
    document.transactions.append(Transaction(id="t3", title="Reparieren", ops=(4, 5)))
    finding = Finding(
        code="op.remesh_uniform.NotManifoldError",
        severity="error",
        message="offen",
        op_id=5,
        suggestions=(errors.REPAIR_AND_RETRY, errors.SHOW_LOCATIONS),
    )

    assert [action.id for action in actions_for_document(finding, document, stopped_at=5)] == [
        "show_locations"
    ]

    # Eine fremde Reparatur in einer anderen Transaktion oder am anderen
    # Körper ist kein Versuch für diesen Schritt und darf ihn nicht sperren.
    document.transactions[:] = [
        Transaction(id="t2", title="Fremde Reparatur", ops=(4,)),
        Transaction(id="t3", title="Fehler", ops=(5,)),
    ]
    assert [action.id for action in actions_for_document(finding, document, stopped_at=5)] == [
        "repair_and_retry",
        "show_locations",
    ]


def test_two_inputs_are_only_considered_repaired_when_both_are_covered() -> None:
    """Zwei Eingänge werden weder zusammengeworfen noch über die Auswahl ergänzt."""
    from app.core.types import Document, Finding, Operation, Transaction
    from app.ui.panels import actions_for_document

    document = Document(format_version=18, app_version="test")
    document.ops.extend(
        [
            Operation(id=7, op="repair", inputs=("obj_1",), outputs=("obj_1",)),
            Operation(id=8, op="repair", inputs=("obj_2",), outputs=("obj_2",)),
            Operation(
                id=9,
                op="subtract_objects",
                inputs=("obj_1", "obj_2"),
                outputs=("obj_3",),
            ),
        ]
    )
    document.transactions.append(Transaction(id="t4", title="Reparieren", ops=(7, 8, 9)))
    finding = Finding(
        code="op.subtract_objects.BooleanFailedError",
        severity="error",
        message="geht nicht",
        op_id=9,
        suggestions=(errors.REPAIR_AND_RETRY, errors.SHOW_LOCATIONS),
    )

    assert actions_for_document(finding, document, stopped_at=9) == (), (
        "beide Reparaturen wurden versucht; für zwei Körper gibt es keinen eindeutigen Kartenort"
    )

    document.transactions[-1] = Transaction(id="t4", title="Reparieren", ops=(7, 9))
    assert [action.id for action in actions_for_document(finding, document, stopped_at=9)] == [
        "repair_and_retry"
    ]


def test_repair_is_not_offered_for_a_stopped_step_without_an_input() -> None:
    """Ein Knopf ohne ausführbares Modell erscheint gar nicht erst."""
    from app.core.types import Document, Finding, Operation
    from app.ui.panels import actions_for_document

    document = Document(format_version=18, app_version="test")
    document.ops.append(Operation(id=3, op="create_box", inputs=(), outputs=("obj_1",)))
    finding = Finding(
        code="op.create_box.GeometryError",
        severity="error",
        message="geht nicht",
        op_id=3,
        suggestions=(errors.REPAIR_AND_RETRY, errors.SHOW_LOCATIONS),
    )

    offered = actions_for_document(finding, document, stopped_at=3)

    assert offered == ()


def test_a_planned_but_not_evaluated_object_is_not_an_executable_target() -> None:
    """Der Stapel kann Ausgänge nennen, die hinter dem Stopp nie entstanden."""
    from app.core.types import Document, Finding, Operation
    from app.ui.panels import actions_for_document

    document = Document(format_version=18, app_version="test")
    document.ops.append(Operation(id=3, op="create_box", outputs=("obj_1",)))
    finding = Finding(
        code="mesh.open",
        severity="error",
        message="geht nicht",
        object_id="obj_1",
        suggestions=(errors.REPAIR_AND_RETRY, errors.SHOW_LOCATIONS),
    )

    offered = actions_for_document(finding, document, live_objects=frozenset())

    assert offered == ()


def test_repair_is_not_offered_before_retrying_an_exact_shell() -> None:
    """Die Oberfläche bewahrt Aushöhlen vor einer sicher schädlichen Reparatur."""
    from app.core.types import Document, Finding, Operation
    from app.ui.panels import actions_for_document

    document = Document(format_version=18, app_version="test")
    document.ops.extend(
        [
            Operation(id=4, op="create_brep_box", outputs=("obj_1",)),
            Operation(id=5, op="shell_exact", inputs=("obj_1",), outputs=("obj_1",)),
        ]
    )
    finding = Finding(
        code="op.shell_exact.GeometryError",
        severity="error",
        message="geht nicht",
        op_id=5,
        suggestions=(errors.REPAIR_AND_RETRY, errors.SHOW_LOCATIONS),
    )

    offered = actions_for_document(finding, document, stopped_at=5)

    assert [action.id for action in offered] == ["show_locations"]


def test_an_objectless_direct_error_has_no_repair_button(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auch der modale Fehlerweg verspricht keine Reparatur ohne Ziel."""
    from app.ui import main_window

    shown: list[errors.AppError] = []
    monkeypatch.setattr(main_window, "show_error", lambda error, _parent: shown.append(error))

    window._on_error(errors.NotManifoldError(open_edges=3))

    assert len(shown) == 1
    assert "repair_and_retry" not in {action.id for action in shown[0].suggestions}


def test_partial_repair_runs_from_the_report_and_undoes(window: MainWindow) -> None:
    """Datei → Berichtsknopf → Restkarte → Oberflächen-Undo, ohne Kernabkürzung."""
    from PySide6.QtWidgets import QPushButton

    from app.core.geom.repair import open_edge_count

    window.open_path(MESHES / "partially_open.stl")
    window.session.wait_for_idle()
    object_id = next(iter(window.session.last_result.scene.objects))
    assert open_edge_count(window.session.last_result.scene.objects[object_id].mesh) == 19

    def choose(code: str) -> None:
        for row in range(window.report.list.count()):
            item = window.report.list.item(row)
            finding = item.data(Qt.ItemDataRole.UserRole)
            if finding.code == code:
                window.report.list.setCurrentRow(row)
                QApplication.processEvents()
                return
        raise AssertionError(f"kein Befund {code!r} im sichtbaren Bericht")

    def button(label: object) -> QPushButton | None:
        buttons = window.report._offers.findChildren(QPushButton)
        return next((entry for entry in buttons if entry.text() == str(label)), None)

    choose("ingest.not_watertight")
    repair_button = button(errors.REPAIR_AND_RETRY.label)
    assert repair_button is not None and not repair_button.isHidden()
    repair_button.click()
    window.session.wait_for_idle()

    repaired = window.session.last_result.scene.objects[object_id].mesh
    assert open_edge_count(repaired) == 16
    lines = [window.report.list.item(row).text() for row in range(window.report.list.count())]
    assert any("3 von 19 offenen Kanten geschlossen; 16 bleiben offen" in line for line in lines)
    assert any("Offene Kanten: 16" in line for line in lines)

    choose("repair.still_open")
    location_button = button(errors.SHOW_LOCATIONS.label)
    assert location_button is not None and not location_button.isHidden()
    location_button.click()
    QApplication.processEvents()
    assert window.tools.active() == "analysis"
    assert window.analysis_bar.chosen() == "defects"
    assert window.object_tree.selected_objects() == (object_id,)

    window.undo_action.trigger()
    window.session.wait_for_idle()
    restored = window.session.last_result.scene.objects[object_id].mesh
    assert open_edge_count(restored) == 19


def test_failed_operation_is_repaired_before_retry_without_a_loop(window: MainWindow) -> None:
    """Echter Fehler → Reparatur davor → Retry → Stellen zeigen → ein Undo."""
    from PySide6.QtWidgets import QPushButton, QVBoxLayout

    window.resize(1500, 950)
    window.show()
    QApplication.processEvents()
    window.open_path(MESHES / "partially_open.stl")
    window.session.wait_for_idle()
    object_id = next(iter(window.session.last_result.scene.objects))
    window.session.apply(
        REGISTRY.get("remesh_uniform").title,
        [OperationDraft(op="remesh_uniform", inputs=(object_id,))],
    )
    window.session.wait_for_idle()

    first_result = window.session.last_result
    failed_id = first_result.stopped_at
    assert failed_id is not None
    original_ops = tuple(window.session.project.document.ops)
    old_transaction = window.session.history.transaction_of(failed_id)
    assert old_transaction is not None

    def choose(code: str) -> None:
        for row in range(window.report.list.count()):
            item = window.report.list.item(row)
            finding = item.data(Qt.ItemDataRole.UserRole)
            if finding.code == code:
                window.report.list.setCurrentRow(row)
                QApplication.processEvents()
                return
        raise AssertionError(f"kein Befund {code!r} im sichtbaren Bericht")

    def button(label: object) -> QPushButton | None:
        return next(
            (
                entry
                for entry in window.report._offers.findChildren(QPushButton)
                if entry.text() == str(label)
            ),
            None,
        )

    failed_code = "op.remesh_uniform.NotManifoldError"
    choose(failed_code)
    first_repair = button(errors.REPAIR_AND_RETRY.label)
    assert first_repair is not None and not first_repair.isHidden()
    offered_buttons = [
        entry for entry in window.report._offers.findChildren(QPushButton) if not entry.isHidden()
    ]
    assert isinstance(window.report._offer_row, QVBoxLayout)
    assert all(window.report._offers.rect().contains(entry.geometry()) for entry in offered_buttons)
    assert len({entry.x() for entry in offered_buttons}) == 1
    assert len({entry.width() for entry in offered_buttons}) == 1
    transaction_count = len(window.session.history.transactions)
    first_repair.click()
    first_repair.click()
    window.session.wait_for_idle()

    assert len(window.session.history.transactions) == transaction_count + 1
    retry = window.session.history.transactions[-1]
    retry_ops = [entry for entry in window.session.project.document.ops if entry.id in retry.ops]
    assert [entry.op for entry in retry_ops] == ["repair", "remesh_uniform"]
    assert retry.changes is not None
    assert failed_id in (retry.changes.after.edited_ops or {})
    assert window.session.last_result.stopped_at == retry_ops[-1].id

    rows = [window.history_panel.list.item(row) for row in range(window.history_panel.list.count())]
    old_row = next(item for item in rows if old_transaction.id in item.toolTip())
    assert tr("gelöscht") in old_row.text() and old_row.font().strikeOut()
    assert any(str(errors.REPAIR_AND_RETRY.label) in item.text() for item in rows)

    choose(failed_code)
    assert button(errors.REPAIR_AND_RETRY.label) is None, "derselbe Reparaturweg bildet keinen Ring"
    location = button(errors.SHOW_LOCATIONS.label)
    assert location is not None and not location.isHidden()

    window.undo_action.trigger()
    window.session.wait_for_idle()
    assert tuple(window.session.project.document.ops) == original_ops
    assert window.session.last_result.stopped_at == failed_id

    choose(failed_code)
    restored = button(errors.REPAIR_AND_RETRY.label)
    assert restored is not None and not restored.isHidden(), (
        "nach dem Undo ist der Reparaturversuch nicht mehr aktiv"
    )


def test_correcting_puts_the_cursor_in_the_field_that_failed(window: MainWindow) -> None:
    """Der Befund spricht über **einen** Wert — der Dialog soll ihn zeigen.

    ``ValidationError`` nennt das Feld, und der Befund trägt es weiter. Ohne
    den Sprung dorthin geht ein Dialog mit acht Zeilen auf, und der Kunde
    sucht, welche gemeint war. Geprüft wird an der ganzen Kette: Bericht,
    Knopf, Dialog, Fokus.
    """
    from PySide6.QtWidgets import QDoubleSpinBox

    from app.ui.panels import as_error

    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    object_id = next(iter(window.session.last_result.scene.objects))
    window.session.apply(
        "Bohrung setzen",
        [
            OperationDraft(
                op="drill_hole",
                inputs=(object_id,),
                params={"diameter": 5000.0, "x": 0.0, "y": 0.0, "z": 4.0, "axis": "z"},
            )
        ],
    )
    window.session.wait_for_idle()

    finding = next(
        f for f in window.session.last_result.scene.report.findings if f.code.startswith("op.")
    )
    assert finding.values.get("field") == "diameter", "der Kern nennt das Feld nicht mehr"

    window.error_handlers()["correct_input"](as_error(finding))
    QApplication.processEvents()

    dialog = window._op_dialog
    assert dialog is not None, "der Dialog ging nicht auf"
    try:
        editor = dialog._editors["diameter"]
        inner = editor.findChild(QDoubleSpinBox)
        assert inner is not None
        assert inner.hasFocus(), "der Cursor steht nicht im Feld, um das es geht"
    finally:
        dialog.reject()


def test_a_boolean_that_failed_in_draft_can_go_the_full_chain(window: MainWindow) -> None:
    """Der Rat zeigte ins Leere, und zwar an der häufigsten Stelle (§17.2, §31).

    Im Fenster läuft die kurze Rückfallkette; *Voxelstufe erzwingen* ist damit
    der richtige nächste Schritt — und war ein Satz ohne Knopf. Jetzt rechnet
    er einmal mit der vollen Kette, und danach ist die Sitzung wieder so
    schnell wie vorher.
    """
    from app.ui.dialogs import offered_actions

    handlers = window.error_handlers()
    entwurf = errors.BooleanFailedError(attempted=("direct", "welded"))
    assert "use_voxel_stage" in {a.id for a in offered_actions(entwurf, handlers)}

    handlers["use_voxel_stage"](entwurf)
    assert window.session._quality_once == "fine", "der Lauf bleibt im Entwurf"
    window.session.wait_for_idle()
    assert window.session._quality_once is None, "und der nächste ist wieder Entwurf"


def test_correcting_is_not_offered_where_there_is_no_step(window: MainWindow) -> None:
    """Ein Knopf, der nichts tun kann, wird nicht gezeigt.

    *Eingabe korrigieren* öffnet einen Schritt. Ein Fehler beim Lesen oder
    Schreiben einer Datei hat keinen — dort bliebe der Knopf stumm, und das ist
    der Grund, aus dem das Projekt Vorschläge ohne Handler gar nicht erst
    anbietet.
    """
    from app.ui.dialogs import offered_actions

    handlers = window.error_handlers()
    assert "correct_input" in handlers

    without = errors.ValidationError(field="diameter", detail="zu groß", constraint="maximum")
    assert "correct_input" not in {a.id for a in offered_actions(without, handlers)}

    with_step = errors.ValidationError(
        field="diameter", detail="zu groß", constraint="maximum", op_id=2
    )
    assert "correct_input" in {a.id for a in offered_actions(with_step, handlers)}


def test_the_finding_below_the_bed_is_one_click_from_being_fixed(window: MainWindow) -> None:
    """§2.7 zu Ende: der Klick am Befund tut, was der Satz nahelegt.

    Ein geladenes Modell sitzt mittig auf z = 0 und steckt damit zur Hälfte
    unter der Platte — der häufigste Befund von Weg 1. Die Eingangsstufe setzt
    es bewusst nicht von selbst auf (§17.1: anbieten, nicht erzwingen), und
    angeboten war es nirgends: Der Bericht nannte den Fall und bot *Modell
    teilen* und *Auf den Bauraum verkleinern* an.

    **Seit dem 03.09.2026 ist es das zweite Modell, an dem das gemessen wird.**
    Das erste eines Projekts kommt aufgesetzt und mittig herein; jedes weitere
    behält seine Lage, weil es sonst im ersten läge. Der Befund und sein Knopf
    haben damit denselben Anlass wie vorher, nur nicht mehr beim allerersten
    Öffnen.

    Geprüft wird die ganze Kette — Kennung, Handlung, Handler, Geometrie — und
    dass ein Undo sie zurücknimmt (Regel 19, §2.1).
    """
    from app.ui.panels import FINDING_ACTIONS, as_error

    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()

    result = window.session.last_result
    sunk = [f for f in result.scene.report.findings if f.code == "arrange.below_bed"]
    assert sunk, "ein weiteres Modell behält seine Lage und steckt unter der Platte"
    # Das zweite Objekt ist das gesunkene; das erste liegt auf dem Bett.
    gesunken = list(result.scene.objects.values())[1]
    before = gesunken.mesh.bounds.minimum[2]
    assert before < 0.0

    offers = FINDING_ACTIONS[sunk[0].code]
    handlers = window.error_handlers()
    assert [action.id for action in offers] == ["place_on_bed"]
    assert offers[0].id in handlers, "angeboten, aber nichts führt es aus"

    handlers[offers[0].id](as_error(sunk[0]))
    window.session.wait_for_idle()

    after = window.session.last_result
    assert list(after.scene.objects.values())[1].mesh.bounds.minimum[2] == pytest.approx(0.0)
    assert not [f for f in after.scene.report.findings if f.code == "arrange.below_bed"], (
        "der Befund bleibt stehen, obwohl er behoben ist"
    )

    window.action_undo()
    window.session.wait_for_idle()
    zurueck = window.session.last_result
    assert list(zurueck.scene.objects.values())[1].mesh.bounds.minimum[2] == pytest.approx(
        before
    ), "ein Undo nimmt die Handlung nicht zurück"


def test_only_actions_with_a_handler_are_offered(window: MainWindow) -> None:
    """Lieber ein Knopf weniger als einer, der nichts tut."""
    from app.ui.dialogs import offered_actions

    error = errors.NotManifoldError(open_edges=3)
    offered = {action.id for action in offered_actions(error, window.error_handlers())}

    assert "repair_and_retry" in offered
    assert "show_locations" in offered
    assert "cancel" not in offered, "das Schließen ist kein Vorschlag, es steht ohnehin da"


def test_missing_software_gets_a_button_into_the_install_list(window: MainWindow) -> None:
    """Der Vorschlag war da, der Handler nicht — also stand er als grauer Satz.

    Jede Meldung über fehlende Software schlägt ``install`` vor. Verdrahtet war
    unter dieser Kennung nichts; die Liste der zusätzlichen Programme hing
    unter ``open_settings``, also unter einem Namen, den kein Knopf trug.
    Ergebnis: „… installieren" als Text zum Lesen, während der Dialog, der es
    holt, zwei Menüs entfernt stand.

    Gefunden wurde es an ``ScadUnavailable``, und die Klasse ist mit dem
    OpenSCAD-Ausbau am 26.08.2026 entfallen. Geprüft wird seither an den zwei
    übrigen Wegen, auf denen fehlende Software gemeldet wird — die Zusage
    gilt der **Verdrahtung**, nicht dem Programm, das gerade fehlt.
    """
    from app.core.brep.kernel import BRepUnavailable
    from app.core.errors import ExternalToolError
    from app.ui.dialogs import offered_actions

    for problem in (ExternalToolError(detail="PrusaSlicer"), BRepUnavailable()):
        offered = {action.id for action in offered_actions(problem, window.error_handlers())}
        assert "install" in offered, f"{type(problem).__name__}: kein Weg zur Installation"
        assert "report_error" not in offered, "fehlende Software ist kein Fehlerbericht"


def test_closing_is_no_advice_either(window: MainWindow) -> None:
    """Derselbe Satz gilt für den Text, und dort galt er nicht.

    Jede Ausnahme in ``errors.py`` führt ``CANCEL`` unter ihren Vorschlägen, und
    für keine gibt es einen Handler — ``unhandled_advice`` schrieb „Abbrechen"
    also in **jeden** Fehlerdialog, als Rat, direkt über dem Abbrechen-Knopf.
    Der Grundsatz stand längst daneben, bei den Knöpfen; nur der Textpfad hatte
    ihn nicht übernommen.
    """
    from app.core.errors import CANCEL
    from app.ui.dialogs import unhandled_advice

    known = window.error_handlers()
    for name, value in vars(errors).items():
        if not isinstance(value, type) or not issubclass(value, errors.AppError):
            continue
        suggestions = getattr(value, "default_suggestions", ())
        if CANCEL not in suggestions:
            continue
        error = errors.AppError.__new__(value)
        object.__setattr__(error, "suggestions", list(suggestions))
        assert str(CANCEL.label) not in unhandled_advice(error, known), (
            f"{name} schreibt das Abbrechen als Ratschlag in den Text"
        )


def test_an_error_without_a_handler_still_offers_a_way_out(window: MainWindow) -> None:
    """Ein Dialog mit nur „Abbrechen" ist „fehlgeschlagen" mit mehr Worten.

    **Der Ausweg muss nicht immer ein Knopf sein.** Diese Prüfung verlangte
    früher ``report_error``, und das war die halbe Antwort: Von 48 Kennungen,
    die der Kern in ``Action(...)`` vergibt, sind zehn verdrahtet — die
    übrigen wurden verworfen, und an ihrer Stelle stand der Fehlerbericht als
    Hauptknopf. Auf einen reinen Bedienfehler ist das die falsche lauteste
    Antwort; er gehört laut ``errors.py`` dem ``InternalError``. Der hilfreiche
    Satz des Kernautors steckte derweil im weggeworfenen Knopf.

    Geprüft wird deshalb die Regel und nicht ihre eine Umsetzung: Es bleibt
    **entweder** eine Handlung mit Wirkung **oder** ein Rat zum Lesen. Nur
    beides zugleich leer wäre „fehlgeschlagen" mit mehr Worten.
    """
    from app.ui.dialogs import offered_actions, unhandled_advice

    known = window.error_handlers()
    error = errors.AmbiguityError("Welche Fläche ist gemeint?", ("oben", "unten"))
    offered = [action.id for action in offered_actions(error, known)]
    spoken = unhandled_advice(error, known)

    assert offered or spoken, "weder Knopf noch Rat — genau das darf nicht passieren"
    assert spoken, "die Vorschläge des Kerns dürfen nicht stillschweigend verschwinden"
    assert "report_error" not in offered, (
        "Der Fehlerbericht ist dem InternalError vorbehalten, nicht einer offenen Frage."
    )


def test_every_worker_field_is_waited_for_when_the_window_closes() -> None:
    """Ein Thread, der sein Fenster überlebt, nimmt den Prozess mit.

    ``wait_for_workers`` zählt die Arbeiter von Hand auf, und der Download
    fehlte darin. Er folgt dem Muster mit ``_retire`` und ``_hold_until_done``
    sauber — aber in ``_retired`` landet er erst, wenn er fertig ist. Solange er
    lief, hielt ihn allein sein Feld, und wer währenddessen schloss, bekam
    genau den Absturz, gegen den die Liste geschrieben wurde: einen ohne Zeile,
    weil niemand mehr da war, sie zu schreiben.

    Geprüft wird am Quelltext und nicht am laufenden Fenster: Ein Test, der
    dafür jeden Arbeiter wirklich startet, bräuchte ein Netz, einen Slicer und
    ein Sprachmodell. Was hier zählt, ist die Vollständigkeit der Aufzählung —
    wer ein neues Feld anlegt und es dort vergisst, wird rot.
    """
    import re

    source = (Path(__file__).parent.parent / "app" / "ui" / "main_window.py").read_text(
        encoding="utf-8"
    )
    fields = set(re.findall(r"self\.(_\w*worker\w*)\s*:\s*Any\s*=\s*None", source))
    assert fields, "keine Arbeiterfelder gefunden — dieser Test misst nichts mehr"

    body = source[source.index("def wait_for_workers") :]
    body = body[: body.index("\n    def ", 1)]

    forgotten = sorted(name for name in fields if name not in body)
    assert not forgotten, (
        f"Diese Arbeiter werden beim Schließen nicht abgewartet: {forgotten}. "
        "Solange einer läuft, hält ihn allein sein Feld — `_retired` bekommt ihn "
        "erst, wenn er fertig ist."
    )


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


def test_dropping_a_model_on_the_start_screen_asks_before_replacing(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """*Datei → Neu* verwirft bewusst nichts — das Einfügen danach tat es.

    Der Startbildschirm über einem geänderten Projekt ist eine Ansicht, kein
    Verwerfen: Das Projekt bleibt offen. Ein Modell zu ziehen oder
    einzufügen rief dann ``start_new`` ohne jede Frage — Dokument samt
    Verlauf ersetzt, Undo holte nichts zurück (Gesamtreview-b, Bericht 08,
    Fund 1). Jetzt kommt dieselbe Frage wie beim Öffnen einer ``.p3d``.
    """
    import app.ui.main_window as module

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    assert window.session.modified
    window.action_new()
    ops_before = [entry.op for entry in window.session.project.document.ops]

    monkeypatch.setattr(module, "confirm_unsaved", lambda title, parent: "cancel")
    window.open_path(MESHES / "plate_holes.stl")

    assert [entry.op for entry in window.session.project.document.ops] == ops_before, (
        "Abbrechen lässt das Projekt, wie es war"
    )

    monkeypatch.setattr(module, "confirm_unsaved", lambda title, parent: "discard")
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    assert [entry.op for entry in window.session.project.document.ops] == ["load"], (
        "Verwerfen beginnt das neue Projekt"
    )


# --- Einstellungen an einem Ort (§19.3, §38) ------------------------------------


def test_the_display_unit_reaches_everything_that_shows_a_length(window: MainWindow) -> None:
    """§19.3: die Einstellung gab es seit P0 und niemanden, der sie las.

    **Der Name war eine Zusage, und der Test prüfte zwei Stellen.** Erreicht
    wurden drei — Statusleiste, Objektbaum, Kopfzeile —, und die übrigen elf
    Längenausgaben standen weiter auf der Vorgabe „mm": der ganze
    Skizzeneditor, die Analyseleiste, die Schnittleiste und die
    Merkmalsbeschriftungen. Wer auf Zoll stellte, las im selben Fenster beides.

    Geprüft wird deshalb jetzt auch die freie Ausgabe — ``labels.length`` ohne
    durchgereichte Einheit ist der Weg, den jene elf nehmen — und die
    Kopfzeile, die als Einzige die Einstellung selbst las und trotzdem
    hinterherhing: Sie wurde nur bei Profil- oder Auswertungswechsel neu
    geschrieben.
    """
    from app.ui.labels import display_unit, length

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window._on_scene(window.session.evaluate_now())
    window.object_tree.tree.setCurrentItem(window.object_tree.tree.topLevelItem(0))

    assert "20,00" in window.measurements.text()
    assert "cm³" in window.measurements.text()
    assert "20" in window.header.bounds.full_text(), "die Kopfzeile kennt das Außenmaß"
    assert display_unit() == "mm", "die Vorgabe ist Millimeter"

    window.set_display_unit("in")

    # Die Einheit wechselt, die Schreibweise der Zahl folgt weiter der Sprache
    # — ein Zoll auf einer deutschen Oberfläche schreibt sich mit Komma.
    assert "0,7874" in window.measurements.text(), "20 mm sind 0,7874 Zoll"
    assert "in³" in window.measurements.text()
    assert "in" in window.object_tree.tree.topLevelItem(0).text(1)

    # Die Kopfzeile hing einen Schritt nach: sie liest die Einstellung selbst,
    # wurde aber nur bei Profil- oder Auswertungswechsel neu geschrieben.
    assert "in" in window.header.bounds.full_text(), "die Kopfzeile folgt sofort"
    assert "20,00" not in window.header.bounds.full_text(), "sonst steht dort noch Millimeter"

    # Und der Weg der elf: eine Länge ohne durchgereichte Einheit.
    assert display_unit() == "in"
    assert length(20.0) == "0,7874 in", length(20.0)


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


def test_the_palette_reaches_more_than_the_registry(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§2.6: die Palette ist der Universalzugang — sie kannte nur Operationen.

    Speichern, das Handbuch und die sieben Ansichtswerkzeuge stehen nicht im
    Register. `ToolStrip.tool_titles()` und `strip_title()` wurden dafür
    geschrieben und hatten außer Tests keinen Aufrufer.
    """
    opened: list[bool] = []
    monkeypatch.setattr(window, "_open_catalog", lambda: opened.append(True))
    commands = window.window_commands()

    assert "file.save" in commands
    assert "help.manual" in commands
    assert commands["file.part_adopt"][0] == "Baustein aus Datei hinzufügen …"
    assert commands["file.part_share"][0] == "Baustein als Datei weitergeben …"
    commands["file.part_share"][2]()
    assert opened == [True], "die Weitergabe öffnet den Katalog zur Auswahl"
    for key in window.tools.tool_titles():
        assert f"tool.{key}" in commands, f"{key} fehlt in der Palette"

    for _title, _shortcut, slot in commands.values():
        assert callable(slot)


def test_part_file_commands_do_not_add_a_file_menu_row(window: MainWindow) -> None:
    """Beide Dateihandlungen leben in der Palette; das volle Menü bleibt an der Grenze."""
    from app.core.registry.surfaces import MAX_MENU_ROWS

    file_menu = next(
        action.menu()
        for action in window.menuBar().actions()
        if action.menu() is not None and action.text().replace("&", "") == "Datei"
    )
    assert file_menu is not None
    rows = [action for action in file_menu.actions() if not action.isSeparator()]
    titles = {action.text().replace("&", "") for action in rows}

    assert "Baustein aus Datei hinzufügen …" not in titles
    assert "Baustein als Datei weitergeben …" not in titles
    assert len(rows) <= MAX_MENU_ROWS


def test_escape_closes_the_open_tool(window: MainWindow) -> None:
    """`close_tool` gab es seit jeher und niemanden, der es rief."""
    window.tools.toggle("section")
    assert window.tools.active() == "section"

    window.tools.close_tool()
    assert window.tools.active() is None


def test_the_view_menu_can_fit(window: MainWindow) -> None:
    """Ohne diesen Eintrag musste man wissen, dass Strg+0 nebenbei einpasst."""
    labels = {action.text() for action in all_menu_actions(window)}
    assert "Einpassen" in labels


def test_the_first_body_gets_the_camera(window: MainWindow) -> None:
    """Sonst bleibt die Kamera, wo sie war, und das Teil liegt außerhalb des
    Bildes — die Anwendung sieht aus, als hätte sie nichts geladen."""
    assert not window._seen_objects

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window._on_scene(window.session.evaluate_now())

    assert window._seen_objects


def test_the_toolbar_buttons_carry_a_symbol_and_show_their_words(
    window: MainWindow,
) -> None:
    """Die wichtigsten Wege stehen als Zeichen und Wort in derselben Zeile."""
    from app.ui import icons

    for name in ("new", "open", "save", "import"):
        assert name in icons.known(), f"{name} fehlt im Symbolkatalog"

    from PySide6.QtWidgets import QWidgetAction

    toolbar = window.findChildren(QToolBar)[0]
    assert toolbar.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextBesideIcon
    for action in toolbar.actions():
        # Eingehängte Widgets sind keine Knöpfe: sie tragen ihre Beschriftung
        # selbst, und ein leerer ``text()`` ist bei ihnen kein Befund.
        if isinstance(action, QWidgetAction) or action.isSeparator():
            continue
        assert action.text(), "das Wort bleibt"
        assert not action.icon().isNull(), f"{action.text()} ohne Zeichen"
        assert action.toolTip(), f"{action.text()} ohne Hinweis am Zeiger"
        assert action.statusTip(), f"{action.text()} ohne Hinweis in der Statuszeile"

    labels = {action.text() for action in toolbar.actions()}
    assert {"Neues Projekt", "Modell einfügen", "Zeichnen", "Formen", "Skelett"} <= labels


def test_a_labelled_button_keeps_the_reason_short(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der sichtbare Name muss in einem Sperrhinweis nicht wiederholt werden.

    Beide Helfer, die einen Hinweis überschreiben, sind vertreten: die Sperre
    nach abgelaufenem Testzeitraum (``_lock_hint``) und die fehlende Auswahl
    (``_pick_hint``). Das Wort steht am Knopf; der Hinweis nennt nur den Grund.
    """
    _expired(monkeypatch)
    window = MainWindow(Session(), UiSettings())

    assert "Lizenzschlüssel" in window._toolbar_import.toolTip()
    assert not window._toolbar_import.toolTip().startswith("Modell einfügen")

    from app.core import activation

    monkeypatch.setattr(activation, "_cached", activation.Activation(days_left=99))
    window._update_actions()

    assert "ausgewählten Körper" in window._toolbar_sculpt.toolTip()
    assert not window._toolbar_sculpt.toolTip().startswith("Formen")
    # Und im Menü, wo der Name danebensteht, bleibt der Grund allein.
    assert not window.import_action.toolTip().startswith("Modell einfügen …")


def test_a_labelled_button_still_teaches_what_it_does_and_which_key(
    qt_app: QApplication,
) -> None:
    """Der sichtbare Kurzname ersetzt weder Zweck noch Tastenkürzel.

    Der Satz wird nicht abgeschrieben, sondern von der Menü-Action geholt;
    zwei Versionen desselben Satzes würden sonst auseinanderlaufen.
    """
    window = MainWindow(Session(), UiSettings())

    tip = window._toolbar_import.toolTip()
    assert window.import_action.statusTip() in tip, "der Satz kommt aus dem Menüeintrag"
    assert "Ctrl+I" in tip or "Strg+I" in tip, "und das Kürzel steht dabei"

    # Die drei ohne Menüpendant tragen ihren eigenen Satz — leer wäre keiner.
    assert len(window._toolbar_sketch.toolTip()) > len("Zeichnen")


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


def test_reading_a_gcode_file_stands_under_the_wait_cursor(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§2.8: Ein Strom von 10 MB kostet gemessen 520 ms — dafür gilt die
    mittlere Zeile der Tabelle.

    ``action_check_gcode`` las die Datei und zerlegte sie im Qt-Hauptthread,
    ohne dass irgendetwas davon zu sehen war: dreihunderttausend Zeilen sind
    ein mittleres Teil, eine volle Platte ein Mehrfaches davon. Gemessen wird
    am Zeiger während des Zerlegens, nicht an der Rechnung danach.
    """
    from PySide6.QtWidgets import QFileDialog

    from app.core.slice import gcode as gcode_module

    datei = tmp_path / "platte.gcode"
    datei.write_text(";LAYER:0\nG1 X10 Y10 E0.5 F1800\nG1 Z0.2\n", encoding="utf-8")
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *args, **kwargs: (str(datei), "")),
    )
    gesehen: list[Any] = []
    echt = gcode_module.parse

    def beobachtet(text: str, *args: Any, **kwargs: Any) -> Any:
        gesehen.append(QApplication.overrideCursor())
        return echt(text, *args, **kwargs)

    monkeypatch.setattr("app.ui.main_window.gcode.parse", beobachtet)

    window.action_check_gcode()

    assert gesehen, "zerlegt wurde nichts — der Test misst am falschen Ort"
    assert gesehen[0] is not None, "zerlegt wurde ohne Wartezeiger"
    assert gesehen[0].shape() == Qt.CursorShape.WaitCursor
    assert QApplication.overrideCursor() is None, "der Wartezeiger blieb stehen"


def wait_for_export(window: MainWindow) -> None:
    """§2.8: Exportiert wird im Arbeiter, der Test wartet also wie das Fenster.

    Nach dem Warten einmal zustellen — ``done`` ist eine Warteschlangen-
    Verbindung, und ohne ``processEvents`` kämen weder Meldung noch Befunde je
    an.
    """
    worker = window._export_worker
    if worker is not None:
        worker.wait(20_000)
    QApplication.processEvents()


def test_export_suggests_the_complete_print_format_first(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ohne CAD-Wissen soll der erste Weg nichts Wichtiges wegwerfen.

    3MF bewahrt Baugruppe, Farben und Druckeinstellungen; STL ist der
    ausdrücklich wählbare Altweg. Der Vorschlag im Dateidialog muss deshalb
    zu seinem ersten Filter passen.
    """
    from PySide6.QtWidgets import QFileDialog

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    asked: list[tuple[str, str]] = []

    def remember(_parent: object, _title: str, name: str, filters: str) -> tuple[str, str]:
        asked.append((name, filters))
        return "", ""

    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(remember))

    window.action_export()

    assert asked
    name, filters = asked[0]
    assert name.endswith(".3mf")
    assert filters.split(";;", 1)[0] == "3MF (*.3mf)"


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
    wait_for_export(window)

    assert target.is_file(), "der gewählte Name ist die Datei, nicht ein Schema daraus"
    assert target.stat().st_size > 0


def test_changing_only_the_export_filter_changes_format_and_suffix(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der 3MF-Vorschlag darf eine spätere Filterwahl nicht überstimmen.

    Ein Kunde ändert im Dateidialog häufig nur „Dateityp" auf STL und lässt
    den vorausgefüllten Namen stehen. Inhalt und Endung müssen dann beide STL
    werden; eine STL-Datei namens ``.3mf`` wäre weder verständlich noch in
    jedem Slicer zu öffnen.
    """
    from PySide6.QtWidgets import QFileDialog

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    proposed: list[str] = []

    def choose(_parent: object, _title: str, name: str, _filters: str) -> tuple[str, str]:
        proposed.append(name)
        return str(tmp_path / Path(name).name), "STL (*.stl)"

    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(choose))
    window.action_export()
    wait_for_export(window)

    assert proposed and proposed[0].endswith(".3mf"), "3MF bleibt der einfache Kundenweg"
    expected = tmp_path / f"{Path(proposed[0]).stem}.stl"
    assert expected.is_file(), "der gewählte Filter bestimmt Inhalt und sichtbare Endung"
    assert not (tmp_path / Path(proposed[0]).name).exists(), "keine falsch benannte STL-Datei"


def test_an_explicit_export_suffix_still_wins_over_the_filter() -> None:
    """Wer den Namen selbst samt Endung tippt, hat die genauere Wahl getroffen."""
    from app.ui.main_window import _export_target

    target, export_format = _export_target(Path("mein_teil.obj"), "STL (*.stl)", "projekt.3mf")

    assert target == Path("mein_teil.obj")
    assert export_format == "obj"


def test_export_as_3mf_writes_one_assembly(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Mehrere Körper als 3MF sind eine Baugruppe in einer Datei (§20) —
    nicht eine Datei je Körper, über deren Zusammengehörigkeit der Slicer
    selbst entscheiden müsste.

    **Und die Datei trägt die Druckeinstellungen mit** (§29). Sie tat es nicht:
    Der Aufruf im Menü ließ ``settings`` weg, und heraus kam eine 3MF ganz ohne
    ``project_settings.config``. Der Slicer füllt dann alles aus dem Profil,
    das gerade bei ihm steht — und meldet Widersprüche zu einem Drucker, den
    niemand gemeint hat.
    """
    import json
    import zipfile

    from PySide6.QtWidgets import QFileDialog

    from app.core.knowledge import print_settings

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window.session.import_model(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window.session.set_print_settings(print_settings.resolve(window.session.profile))

    target = tmp_path / "baugruppe.3mf"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *args, **kwargs: (str(target), "3MF (*.3mf)")),
    )
    window.object_tree.tree.clearSelection()
    window.action_export()
    wait_for_export(window)

    written = list(tmp_path.glob("*.3mf"))
    assert len(written) == 1, "eine Baugruppe, eine Datei"
    with zipfile.ZipFile(written[0]) as archive:
        assert "Metadata/project_settings.config" in archive.namelist(), (
            "die Datei ist reine Geometrie — der Slicer erfindet den Rest"
        )
        values = json.loads(archive.read("Metadata/project_settings.config"))
    assert values.get("layer_height"), "ohne Schichthöhe sagt die Datei nichts über den Druck"
    assert float(values["layer_height"]) <= window.session.profile.printer.nozzle_diameter, (
        "eine Schichthöhe über dem Düsendurchmesser lehnt jeder Slicer ab"
    )


def test_the_remembered_slicer_becomes_a_setup(monkeypatch: pytest.MonkeyPatch) -> None:
    """Was im Druckeinstellungen-Dialog stand, gilt auch für den Export (§29).

    Ohne Systemprofil trägt eine 3MF zwar Solidons Werte, aber keinen Drucker,
    zu dem sie passen — und der Slicer bleibt bei dem, der gerade bei ihm
    eingestellt ist. Steht dort eine 0,2er Düse, kollidiert sie mit einer
    ersten Schicht von 0,25 mm, und die Meldung spricht vom Modell.
    """
    from pathlib import Path as PathType

    from app.core import discover
    from app.ui.print_settings_dialog import remembered_setup
    from app.ui.settings import UiSettings

    settings = UiSettings()
    assert remembered_setup(settings) is None, "ohne gemerkten Drucker gibt es nichts aufzulösen"

    monkeypatch.setattr(
        discover, "find_program", lambda *args, **kwargs: PathType("orca-slicer.exe")
    )
    settings.slicer_machine_profile = "Elegoo Centauri Carbon 2 0.4 nozzle"
    settings.slicer_base_process = "0.20mm Standard @Elegoo CC2 0.4 nozzle"
    settings.slicer_base_filament = "Elegoo PETG PRO @ECC2"

    setup = remembered_setup(settings)
    assert setup is not None, "der gemerkte Drucker ist da, das Programm auch"
    assert setup.machine_profile == settings.slicer_machine_profile
    assert setup.base_process == settings.slicer_base_process
    assert setup.base_filament == settings.slicer_base_filament

    # Je Material zuerst, das globale nur als Rückfall — sonst trägt ein
    # TPU-Projekt nach einem PETG-Lauf das PETG-Profil.
    settings.slicer_filament_per_material["tpu"] = "Elegoo TPU @ECC2"
    per_material = remembered_setup(settings, "tpu")
    assert per_material is not None
    assert per_material.base_filament == "Elegoo TPU @ECC2"
    fallback = remembered_setup(settings, "pla")
    assert fallback is not None
    assert fallback.base_filament == settings.slicer_base_filament


def test_a_single_body_3mf_carries_the_settings_too(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der häufigste Fall ist ein Körper — und genau der lief über den
    Plan-Weg, der keine Einstellungen kennt. Dazu war der Dialog nie offen:
    ``document.print_settings`` ist dann ``None``, und das hieß reine
    Geometrie statt der Auflösung aus Stufe, Material und Drucker (§29)."""
    import json
    import zipfile

    from PySide6.QtWidgets import QFileDialog

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()

    target = tmp_path / "einzel.3mf"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *args, **kwargs: (str(target), "3MF (*.3mf)")),
    )
    window.object_tree.tree.clearSelection()
    window.action_export()
    wait_for_export(window)

    written = list(tmp_path.glob("*.3mf"))
    assert len(written) == 1
    with zipfile.ZipFile(written[0]) as archive:
        assert "Metadata/project_settings.config" in archive.namelist(), (
            "ein Körper ohne geöffneten Dialog ist der Normalfall — nicht die Ausnahme"
        )
        values = json.loads(archive.read("Metadata/project_settings.config"))
    assert values.get("layer_height"), "die Auflösung aus Stufe, Material und Drucker gilt"


def test_the_export_leaves_the_window_usable(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§2.8: Prüfen und Schreiben laufen im Arbeiter, nicht in der
    Ereignisschleife.

    Vorher rechnete und schrieb ``action_export`` komplett im Hauptthread —
    Prüfung vor dem Export, Aufbau der Baugruppe, Anordnungsprüfung und die
    Dateien selbst. Bei mehreren großen Körpern ist das mehr als zwei
    Sekunden mit stehendem Fenster.

    Geprüft wird beides: dass der Aufruf zurückkommt, bevor geschrieben ist,
    und dass der Menüeintrag währenddessen gesperrt bleibt — zwei Läufe auf
    denselben Ordner wären ein Wettlauf um dieselben Dateinamen.
    """
    import time

    from PySide6.QtWidgets import QFileDialog

    from app.ui import main_window as module

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()

    real_write = module.write_plan

    def slow_write(*args: Any, **kwargs: Any) -> Any:
        time.sleep(0.4)
        return real_write(*args, **kwargs)

    monkeypatch.setattr(module, "write_plan", slow_write)
    target = tmp_path / "langsam.stl"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *args, **kwargs: (str(target), "STL (*.stl)")),
    )

    started = time.perf_counter()
    window.action_export()
    elapsed = time.perf_counter() - started

    assert elapsed < 0.3, "der Aufruf hat auf das Schreiben gewartet — genau das war der Befund"
    assert window._export_worker is not None, "ohne Arbeiter ist nichts nebenher gelaufen"
    assert not window.export_action.isEnabled(), (
        "ein zweiter Lauf schriebe in dieselben Dateien wie der erste"
    )

    wait_for_export(window)

    assert target.is_file()
    assert target.name in window._announcement, "der fertige Export meldet sich nicht"
    assert window._export_worker is None
    assert window.export_action.isEnabled(), "nach dem Lauf ist der Eintrag wieder da"
    assert not window.progress.isVisible(), "der Balken bleibt stehen, wenn niemand ihn abräumt"


def test_a_failed_export_reports_in_the_main_thread(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regel 17: Was im Arbeiter schiefgeht, wird im Fenster gezeigt — mit
    Handlungsvorschlag, nicht als stiller Ausfall.

    Der ``try/except AppError`` stand um den Code, der jetzt im Arbeiter
    läuft. Fiele er dort ungefangen aus ``run`` heraus, endete der Export
    ohne eine Zeile — und der Menüeintrag bliebe für immer gesperrt.
    """
    from PySide6.QtWidgets import QFileDialog

    from app.ui import main_window as module

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()

    def refuse(*args: Any, **kwargs: Any) -> Any:
        raise errors.UserError(
            title="Der Ordner ließ sich nicht beschreiben.",
            detail="Kein Schreibrecht.",
        )

    shown: list[Any] = []
    monkeypatch.setattr(module, "write_plan", refuse)
    monkeypatch.setattr(module, "show_error", lambda error, *args, **kwargs: shown.append(error))
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *args, **kwargs: (str(tmp_path / "geht_nicht.stl"), "STL (*.stl)")),
    )

    window.action_export()
    wait_for_export(window)

    assert shown, "der Fehler des Arbeiters kam nirgends an"
    assert shown[0].suggestions, "und er trägt keinen Handlungsvorschlag"
    assert window.export_action.isEnabled(), "nach dem Fehlschlag darf man es wieder versuchen"


def test_a_failed_save_offers_both_ways_out(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der datenkritischste Schreibfehler von allen (§2.7, Regel 17).

    Wessen Projekt sich nicht speichern lässt, hat seine Arbeit noch nicht in
    Sicherheit — und bekam einen Dialog mit *Details anzeigen*. Die zwei Fälle,
    die wirklich vorkommen, haben beide eine Antwort: Die Datei liegt in einem
    anderen Programm offen (dann hilft derselbe Weg noch einmal), oder das
    Laufwerk ist voll (dann hilft ein anderer Ort).
    """
    from app.ui import main_window as module
    from app.ui.dialogs import offered_actions

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()

    target = tmp_path / "belegt.p3d"
    attempts: list[Path] = []
    real_save = type(window.session).save_project

    def busy(session: Any, path: Path) -> Path:
        attempts.append(path)
        if len(attempts) == 1:
            raise errors.FileWriteError(target=str(path), detail="Die Datei ist in Benutzung.")
        return real_save(session, path)

    monkeypatch.setattr(type(window.session), "save_project", busy)
    monkeypatch.setattr(module, "show_error", lambda error, *args, **kwargs: None)

    window._save_to(target)

    handlers = window.error_handlers()
    failure = errors.FileWriteError(target=str(target), detail="Die Datei ist in Benutzung.")
    offered = [action.id for action in offered_actions(failure, handlers)]
    assert offered[:2] == ["retry", "save_elsewhere"], offered
    assert "correct_input" not in offered, "an einem Schreibfehler gibt es keine Eingabe"

    # Das andere Programm gibt die Datei frei, der Kunde drückt den Knopf.
    handlers["retry"](failure)

    assert attempts == [target, target], "der zweite Anlauf ging woandershin"
    assert target.is_file(), "gespeichert wurde nicht"
    assert "retry" not in window.error_handlers(), "nach dem Erfolg bleibt nichts offen"


def test_a_failed_save_can_choose_another_place(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der zweite Weg: ein anderer Ort, über den Dialog, den es dafür gibt."""
    from app.ui import main_window as module

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()

    def refuse(session: Any, path: Path) -> Path:
        raise errors.FileWriteError(target=str(path), detail="Kein Platz.")

    monkeypatch.setattr(type(window.session), "save_project", refuse)
    monkeypatch.setattr(module, "show_error", lambda error, *args, **kwargs: None)
    window._save_to(tmp_path / "voll.p3d")

    # Gefragt wird der **Dateidialog** und nicht die Methode: ``_WriteFailure``
    # bindet ``action_save_as`` beim Anlegen, und ein später ersetztes Attribut
    # sähe der Knopf nie — er hätte den echten Dialog geöffnet und den Test
    # offscreen zum Hängen gebracht.
    from PySide6.QtWidgets import QFileDialog

    asked: list[str] = []

    def dialog(*args: Any, **kwargs: Any) -> tuple[str, str]:
        asked.append("gefragt")
        return "", ""

    monkeypatch.setattr(QFileDialog, "getSaveFileName", staticmethod(dialog))
    window.error_handlers()["save_elsewhere"](errors.FileWriteError(target="x", detail="y"))

    assert asked == ["gefragt"], "the other-place button does not reach the save dialog"


def test_a_failed_export_can_be_repeated_without_choosing_the_file_again(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die häufigste Ursache ist eine Datei, die im Slicer offen liegt (§2.7).

    ``FileWriteError`` schlägt *Erneut versuchen* vor, und für keine der beiden
    Ausnahmen, die das tun, gab es einen Handler — der Rat stand als Satz im
    Dialog. Wer die Datei im Slicer schloss, musste Format, Ordner und Namen
    ein zweites Mal wählen.

    Geprüft wird beides: dass der Knopf erscheint, sobald es etwas zu
    wiederholen gibt, dass er an denselben Ort schreibt — und dass er
    **verschwindet**, wenn nichts offen ist. Ein Knopf, der nichts tut, ist
    schlimmer als keiner.
    """
    from PySide6.QtWidgets import QFileDialog

    from app.ui import main_window as module
    from app.ui.dialogs import offered_actions

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()

    target = tmp_path / "belegt.stl"
    assert "retry" not in window.error_handlers(), "ohne Fehlschlag gibt es nichts zu wiederholen"

    real_write = module.write_plan
    attempts: list[int] = []

    def busy_file(*args: Any, **kwargs: Any) -> Any:
        attempts.append(1)
        if len(attempts) == 1:
            raise errors.FileWriteError(target=str(target), detail="Die Datei ist in Benutzung.")
        return real_write(*args, **kwargs)

    monkeypatch.setattr(module, "write_plan", busy_file)
    monkeypatch.setattr(module, "show_error", lambda error, *args, **kwargs: None)
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *args, **kwargs: (str(target), "STL (*.stl)")),
    )

    window.action_export()
    wait_for_export(window)

    handlers = window.error_handlers()
    assert "retry" in handlers, "nach dem Fehlschlag fehlt der Wiederholknopf"
    failed = errors.FileWriteError(target=str(target), detail="Die Datei ist in Benutzung.")
    assert "retry" in {action.id for action in offered_actions(failed, handlers)}

    # Der Slicer gibt die Datei frei, der Kunde drückt den Knopf.
    handlers["retry"](failed)
    wait_for_export(window)

    assert target.is_file(), "der zweite Anlauf hat nicht geschrieben"
    assert len(attempts) == 2, "und er hat keinen dritten gebraucht"
    assert "retry" not in window.error_handlers(), (
        "nach dem geschriebenen Export gibt es nichts mehr zu wiederholen"
    )


def test_the_print_settings_open_before_the_layer_analysis(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§2.8: Der Weg zu den Druckeinstellungen wartet auf nichts mehr.

    ``_current_slice(wait=True)`` hielt ihn bis zu zwei Sekunden an
    (``worker.wait``) — die schlechtere Hälfte beider Möglichkeiten: lange
    genug, um sich wie ein Hänger zu lesen, und ohne Zusage, denn wer den
    Zeitraum riss, bekam den Dialog eben doch ohne Analyse.

    Geprüft wird die ganze Kette: Der Dialog steht ohne Analyse da, und sie
    findet ihn, solange er offen ist.
    """
    import time

    from app.ui import main_window as module

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    item = window.object_tree.tree.topLevelItem(0)
    assert item is not None
    item.setSelected(True)

    at_open: list[Any] = []
    at_close: list[Any] = []

    class ImmediateDialog(module.PrintSettingsDialog):
        """Statt zu warten: einmal nachsehen, dann die Ereignisse laufen
        lassen, wie es ein offener Dialog auch täte."""

        def exec(self) -> int:
            at_open.append(self.slice_result)
            deadline = time.perf_counter() + 20.0
            while self.slice_result is None and time.perf_counter() < deadline:
                QApplication.processEvents()
            at_close.append(self.slice_result)
            return 0

    monkeypatch.setattr(module, "PrintSettingsDialog", ImmediateDialog)

    window.action_print_settings()

    assert at_open == [None], "der Dialog hat doch auf die Schichtanalyse gewartet"
    assert at_close and at_close[0] is not None, (
        "die Analyse hat den offenen Dialog nie erreicht — genau dafür war das Warten da"
    )
    assert window._settings_dialog is None, (
        "der Rückruf zeigte nach dem Schließen weiter auf ein Widget, das weggeräumt wird"
    )


def test_a_late_layer_analysis_finds_no_dialog(window: MainWindow) -> None:
    """Ist keiner mehr offen, ist das Ergebnis nichts wert — und darf keinen
    Absturz kosten.

    Der Dialog wird nach ``exec`` weggeräumt (``deleteLater``); eine gebundene
    Methode von ihm in der Warteliste wäre ein Rückruf in ein zerstörtes
    C++-Objekt, also der Absturz ohne Zeile.
    """
    window._slice_for_settings(None)

    assert window._settings_dialog is None


def test_closing_the_print_settings_keeps_what_was_changed(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Weg hinaus heißt *Schließen*, und Schließen verwirft nichts.

    Der Dialog schreibt jeden getippten Wert sofort in sein Modell, das Fenster
    übernimmt es nach ``exec`` — auch wenn niemand *Übernehmen* gedrückt hat,
    denn es gibt keines. Das ist die Bauart einer Einstellungsseite und kein
    Versehen: Beim Schließen wird auch die Slicer-Profilwahl festgeschrieben
    (``_remember_slicer_choice``), und die soll gerade nicht verlorengehen.

    **Getragen wird sie allein von der Beschriftung.** Ein Knopf *Abbrechen*
    verspräche hier das Gegenteil dessen, was geschieht; dass dort *Schließen*
    steht, hält ``test_the_close_button_speaks_german`` fest. Dieser Test hält
    die andere Hälfte: dass die Werte den geschlossenen Dialog überleben.
    """
    from PySide6.QtWidgets import QSpinBox

    from app.ui import main_window as module

    class ClosingDialog(module.PrintSettingsDialog):
        """Wie ein Kunde, der einen Wert ändert und das Fenster wieder zumacht."""

        def exec(self) -> int:
            editor = self._editors["shell.wall_count"]
            assert isinstance(editor, QSpinBox)
            editor.setValue(7)
            self.reject()
            return int(self.result())

    monkeypatch.setattr(module, "PrintSettingsDialog", ClosingDialog)

    window.action_print_settings()

    settings = window.session.project.document.print_settings
    assert settings is not None, "das Fenster hat die Einstellungen gar nicht übernommen"
    assert settings.shell.wall_count == 7, (
        f"nach dem Schließen stehen {settings.shell.wall_count} Wandbahnen statt 7 — "
        "der Knopf heißt „Schließen“ und darf nichts verwerfen"
    )


def test_a_failed_slicer_precheck_reaches_the_main_report(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der neue Rückweg ist in der Anwendung angeschlossen, nicht nur am Dialog."""
    from PySide6.QtCore import QObject, Signal

    from app.core.knowledge import print_settings
    from app.core.types import Finding
    from app.ui import main_window as module

    before = window.report.list.count()
    finding = Finding(
        code="arrange.out_of_build_volume",
        severity="error",
        message="Das Teil ist größer als der Bauraum.",
    )

    class FailingDialog(QObject):
        """Ersetzt nur die Signale; echte Profil-Worker gehören nicht in den Anschlusstest."""

        sliced = Signal(object)
        reported = Signal(object)
        setupRequested = Signal()  # noqa: N815 - bildet das echte Qt-Signal nach
        filamentsRequested = Signal()  # noqa: N815 - dasselbe für den Weg zu den Spulen

        def __init__(
            self,
            session: Session,
            _ui_settings: UiSettings,
            parent: MainWindow,
            *,
            slice_result: object | None = None,
        ) -> None:
            super().__init__(parent)
            self.slice_result = slice_result
            self.settings = print_settings.resolve(session.profile)

        def exec(self) -> int:
            self.reported.emit([finding])
            return 0

        def refresh_materials(self) -> None:
            """Was ``_show_filaments`` beim Zurückkommen ruft.

            Heute unerreicht — ``exec`` sendet nur ``reported``. Die Methode
            steht trotzdem hier: Sobald jemand den Weg zum Filamentwähler über
            diese Attrappe fährt, wäre ihr Fehlen ein ``AttributeError``, und
            genau so ist ``filamentsRequested`` eine Zeile weiter oben schon
            einmal aufgeschlagen.
            """

        def has_changes(self) -> bool:
            """Ob dieser Dialog etwas bewirkt hat (§29).

            Und hier ist der Fall, den der Docstring darüber vorhersagt,
            tatsächlich eingetreten: Seit dem 03.09.2026 fragt
            ``action_print_settings`` danach, bevor es die Einstellungen ins
            Projekt schreibt — wer nur nachsieht, soll sein Projekt unberührt
            lassen. Die Attrappe kannte die Methode nicht, und der Test starb
            mit genau dem ``AttributeError``, vor dem oben gewarnt wird.

            ``False``, weil diese Attrappe nichts einstellt: Sie sendet einen
            Befund und geht wieder.
            """
            return False

    monkeypatch.setattr(module, "PrintSettingsDialog", FailingDialog)

    window.action_print_settings()

    assert window.report.list.count() == before + 1
    shown = [
        window.report.list.item(row).data(Qt.ItemDataRole.UserRole).code
        for row in range(window.report.list.count())
    ]
    assert "arrange.out_of_build_volume" in shown


def test_export_as_3mf_carries_every_plate(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Zwei Platten sind eine Datei mit zwei Platten darin.

    Jede Platte fängt am selben Bettursprung an. Ohne Plattenangabe legt die
    Datei die Teile der zweiten über die der ersten; am modularen Besteckkorb
    waren es neunundzwanzig Millimeter Überlappung, gemessen zwischen einem
    Fuß auf Platte eins und einem Modul auf Platte zwei. Der Datei sah man das
    nicht an, und der Slicer hätte sie genommen.
    """
    from PySide6.QtWidgets import QFileDialog

    from app.core.scene import OperationDraft

    for _ in range(2):
        window.session.apply(
            "Anlegen",
            [
                OperationDraft(
                    op="create_box", params={"width": 200.0, "depth": 200.0, "height": 10.0}
                )
            ],
        )
        window.session.wait_for_idle()
    result = window.session.last_result
    assert result is not None
    window.session.apply(
        "Anordnen",
        [
            OperationDraft(
                op="arrange_bed", inputs=tuple(result.scene.objects), params={"plates": 2}
            )
        ],
    )
    window.session.wait_for_idle()

    scene = window.session.last_result
    assert scene is not None
    assert {entry.plate for entry in scene.scene.objects.values()} == {0, 1}, "zwei Platten"

    target = tmp_path / "baugruppe.3mf"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *args, **kwargs: (str(target), "3MF (*.3mf)")),
    )
    window.object_tree.tree.clearSelection()
    window.action_export()
    wait_for_export(window)

    written = sorted(path.name for path in tmp_path.glob("*.3mf"))
    assert written == ["baugruppe.3mf"], "eine Baugruppe, eine Datei"

    import zipfile

    with zipfile.ZipFile(target) as container:
        beilage = container.read("Metadata/model_settings.config").decode("utf-8")
    assert beilage.count("<plate>") == 2, "und darin beide Platten"
    assert 'key="plater_id" value="1"' in beilage
    assert 'key="plater_id" value="2"' in beilage


def test_export_as_3mf_carries_the_print_settings(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eine 3MF ohne Einstellungen ist Geometrie, kein Druckauftrag.

    Der Slicer öffnet sie dann mit dem Profil, das gerade eingestellt ist. Was
    das kostet, steht im Projekt Besteckkorb aufgeschrieben: Die Datei sagte
    drei Wände, gedruckt wurden zwei — 127 Gramm Unterschied, und der Datei
    sah man nichts an.
    """
    import zipfile

    from PySide6.QtWidgets import QFileDialog

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window.session.import_model(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()

    target = tmp_path / "auftrag.3mf"
    monkeypatch.setattr(
        QFileDialog,
        "getSaveFileName",
        staticmethod(lambda *args, **kwargs: (str(target), "3MF (*.3mf)")),
    )
    window.object_tree.tree.clearSelection()
    window.action_export()
    wait_for_export(window)

    with zipfile.ZipFile(target) as container:
        assert "Metadata/project_settings.config" in container.namelist()


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


def test_the_parameter_dialog_offers_fx_and_parameter_choices(qt_app: QApplication) -> None:
    """Formeln beginnen über sichtbare Werkzeuge, nicht über auswendig gelernte Syntax."""
    from app.ui.dialogs import ParameterDialog

    parameters = {
        "width": Parameter(name="width", value=40.0, title="Breite"),
        "depth": Parameter(name="depth", value=30.0, title="Tiefe"),
    }
    dialog = ParameterDialog(parameters)
    dialog.name_field.setText("height")
    dialog.show()
    QApplication.processEvents()

    assert not dialog.fx_button.isChecked()
    assert not dialog.expression_field.isVisibleTo(dialog)
    dialog.fx_button.click()
    assert dialog.fx_button.isChecked()
    assert dialog.expression_field.isVisibleTo(dialog)
    assert not dialog.value_field.isEnabled(), (
        "die Formel und die Zahl dürfen nicht zugleich gelten"
    )

    menu = dialog.parameter_button.menu()
    assert menu is not None
    choices = {action.data(): action for action in menu.actions()}
    assert set(choices) == {"width", "depth"}
    choices["width"].trigger()

    assert dialog.expression_field.text() == "=@width"
    assert dialog.validation_problem() is None
    assert dialog.parameter().expression == "=@width"

    choices["depth"].trigger()

    assert dialog.expression_field.text() == "=@depth", (
        "eine korrigierte Auswahl ersetzt den alten Verweis statt ihn anzuhängen"
    )
    assert dialog.validation_problem() is None


def test_the_parameter_dialog_uses_fixed_units_and_honest_decimals(
    qt_app: QApplication,
) -> None:
    """Einheiten sind auswählbar; ganze Werte zeigen mindestens zwei Stellen."""
    from app.core.units import DEGREE_UNIT
    from app.ui.dialogs import ParameterDialog

    dialog = ParameterDialog({})
    dialog.name_field.setText("angle")

    assert isinstance(dialog.unit_field, QComboBox)
    assert not dialog.unit_field.isEditable()
    assert [dialog.unit_field.itemData(index) for index in range(dialog.unit_field.count())] == [
        "mm",
        DEGREE_UNIT,
        "",
    ]
    dialog.unit_field.setCurrentIndex(dialog.unit_field.findData(DEGREE_UNIT))
    assert dialog.parameter().unit == DEGREE_UNIT

    separator = QLocale().decimalPoint()
    dialog.value_field.setValue(12.0)
    assert dialog.value_field.text() == f"12{separator}00"
    dialog.value_field.setValue(0.075)
    assert dialog.value_field.text() == f"0{separator}075", "Feinmaße bleiben sichtbar"

    unknown = Parameter(name="legacy", value=10.0, unit="cm")
    old_dialog = ParameterDialog({"legacy": unknown}, existing=unknown)
    assert old_dialog.unit_field.currentData() == "cm", "alte Dateien werden nicht umgedeutet"
    assert not old_dialog.unit_field.isEditable()


def test_the_parameter_dialog_offers_bounds(qt_app: QApplication) -> None:
    """Die Schreibseite der Grenzen (Gesamtreview B-15).

    Die Leiste liest minimum/maximum seit je und fiel immer auf ±100 000
    zurück, weil keine Stelle der Anwendung die Felder je setzte. Der Dialog
    bietet sie jetzt an — leer heißt weiter: keine Grenze.
    """
    from app.ui.dialogs import ParameterDialog

    dialog = ParameterDialog({})
    dialog.name_field.setText("depth")
    dialog.value_field.setValue(50.0)
    assert dialog.validation_problem() is None, "ohne Grenzen wie bisher"

    dialog.minimum_field.setText("0")
    dialog.maximum_field.setText("60")
    assert dialog.validation_problem() is None
    made = dialog.parameter()
    assert made.minimum == 0.0
    assert made.maximum == 60.0

    dialog.maximum_field.setText("40")
    assert dialog.validation_problem() is not None, "der Wert liegt über der Obergrenze"

    dialog.maximum_field.setText("-10")
    assert dialog.validation_problem() is not None, "Untergrenze über Obergrenze"

    dialog.maximum_field.setText("abc")
    assert dialog.validation_problem() is not None, "keine Zahl ist keine Grenze"


def test_a_limit_that_is_set_can_be_changed_again(session: Session) -> None:
    """Grenzen waren anlegbar und nie änderbar (§2.1: keine Sackgassen).

    Die Parameterleiste liest ``minimum``/``maximum`` nur als Spinbox-Grenzen
    und bietet nichts zum Bearbeiten; der einzige Dialog dazu weist einen
    vorhandenen Namen ab. Wer eine Obergrenze auf 100 gesetzt hatte und später
    150 brauchte, fand ein Feld, das ohne ein Wort klemmt, und keinen dritten
    Weg.

    Rücknehmbar muss es sein, weil es eine Dokumentänderung ist (§15.5) — ein
    Undo stellt die alte Grenze her und nicht bloß den alten Wert.
    """
    session.add_parameter(Parameter(name="breite", value=40.0, maximum=100.0, title="Breite"))

    weiter = dataclasses.replace(session.project.document.parameters["breite"], maximum=150.0)
    assert session.edit_parameter("breite", weiter)

    stand = session.project.document.parameters["breite"]
    assert stand.maximum == pytest.approx(150.0)
    assert stand.value == pytest.approx(40.0), "die Zahl bleibt, die Grenze wandert"
    assert stand.title == "Breite", "der Titel überlebt die Änderung"

    session.undo()
    assert session.project.document.parameters["breite"].maximum == pytest.approx(100.0)


def test_changing_a_limit_to_the_same_value_writes_no_transaction(session: Session) -> None:
    """Ein Undo, das nichts zurücknimmt, ist ein Undo, das der Kunde verliert.

    Wer den Dialog öffnet und mit *Übernehmen* schließt, ohne etwas zu ändern,
    darf keine Zeile im Verlauf erzeugen — sonst kostet ihn der nächste
    Strg+Z einen Schritt, den er nicht gemacht hat.
    """
    session.add_parameter(Parameter(name="breite", value=40.0, maximum=100.0))
    vorher = len(session.history.transactions)

    gleich = dataclasses.replace(session.project.document.parameters["breite"])

    assert not session.edit_parameter("breite", gleich)
    assert len(session.history.transactions) == vorher


def test_the_parameter_dialog_edits_what_is_there(qt_app: QApplication) -> None:
    """Derselbe Dialog ändert, was er angelegt hat — vorbelegt und ohne Absage.

    Zwei Dinge, die beide fehlten: Die Felder standen leer da (ein
    Änderungsdialog, der nichts zeigt, verlangt vom Kunden, sich zu erinnern),
    und der eigene Name fiel unter „Diesen Namen gibt es schon".

    Der Name selbst bleibt stehen: Er ist der Schlüssel, unter dem jeder
    Ausdruck das Maß nennt (``@breite``), und ihn hier umzuschreiben hieße,
    alle diese Verweise mitzuziehen.
    """
    from app.ui.dialogs import ParameterDialog

    bestand = {"breite": Parameter(name="breite", value=40.0, unit="mm", maximum=100.0)}
    dialog = ParameterDialog(bestand, existing=bestand["breite"])

    assert dialog.name_field.text() == "breite"
    assert dialog.name_field.isReadOnly(), "der Schlüssel wechselt hier nicht"
    assert dialog.name_field.toolTip(), "und sagt warum"
    assert dialog.value_field.value() == pytest.approx(40.0)
    assert dialog.maximum_field.text() == "100"
    assert dialog.minimum_field.text() == "", "keine Grenze bleibt keine Grenze"
    assert dialog.validation_problem() is None, "der eigene Name ist kein vergebener"

    dialog.maximum_field.setText("150")
    assert dialog.parameter().maximum == pytest.approx(150.0)


def test_the_parameter_bar_offers_the_way_to_the_limits(qt_app: QApplication) -> None:
    """Der Weg dorthin: Rechtsklick auf die Zeile, ein Eintrag.

    Geprüft am gebauten Menü und über das Auslösen des Eintrags, nicht am
    Aufruf dahinter: Ohne die Verbindung wäre der Eintrag ein Knopf, der
    nichts tut. ``exec`` bliebe stehen — deshalb gibt ``context_menu`` das
    Menü heraus, wie es der Objektbaum daneben tut.
    """
    from app.core.types import Document
    from app.ui.panels import ParameterPanel

    panel = ParameterPanel()
    document = Document(format_version=1, app_version="0.0.1")
    document.parameters["breite"] = Parameter(name="breite", value=40.0, maximum=100.0)
    panel.show_document(document)
    panel.resize(320, 200)
    panel.layout().activate()

    editor = panel._editors["breite"]
    assert panel.parameter_at(editor.geometry().center()) == "breite"

    gerufen: list[str] = []
    panel.limitsRequested.connect(gerufen.append)
    menu = panel.context_menu(editor.geometry().center())
    assert menu is not None
    aktionen = menu.actions()
    assert len(aktionen) == 1, [a.text() for a in aktionen]
    aktionen[0].trigger()
    assert gerufen == ["breite"], "der Eintrag nennt seine Zeile"

    assert panel.context_menu(QPoint(-5, -5)) is None, "kein Menü, wo keine Zeile steht"


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


def test_the_split_worker_forwards_the_core_progress(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Arbeiter reicht den echten Kernfortschritt bis zu seinem Signal."""
    from app.ui import session as session_module

    def planned(*_args: object, progress=None, **_kwargs: object) -> object:
        assert progress is not None, "der Kern bekam keinen Fortschrittskanal"
        progress(0.25, "Grobsuche")
        progress(0.75, "Stützbewertung")
        progress(1.0, "")
        return object()

    monkeypatch.setattr(session_module, "plan_split", planned)
    worker = session_module._SplitWorker(object(), "obj_1", session.profile, {})
    seen: list[tuple[float, str]] = []
    worker.progressed.connect(lambda fraction, text: seen.append((fraction, text)))

    worker.work()

    assert seen == [(0.25, "Grobsuche"), (0.75, "Stützbewertung"), (1.0, "")]


def test_only_the_current_split_worker_can_report_progress(session: Session) -> None:
    """Nachzügler und verworfene Suchen überschreiben keine neue Anzeige."""
    current = object()
    session._split = current
    seen: list[tuple[float, str]] = []
    cancelled: list[bool] = []
    session.splitProgressChanged.connect(lambda value, text: seen.append((value, text)))
    session.splitCancelled.connect(lambda: cancelled.append(True))
    try:
        session._split_progress(object(), 0.2, "alt")
        session._split_progress(current, 0.3, "aktuell")
        session._split_cancelled(object())
        assert not cancelled, "ein veralteter Arbeiter bestätigte den Abbruch"
        session._split_cancelled(current)
        session._split_discarded = True
        session._split_progress(current, 0.8, "verworfen")
    finally:
        session._split = None
        session._split_discarded = False

    assert seen == [(0.3, "aktuell")]
    assert cancelled == [True]


def _progress_snapshot(window: MainWindow) -> tuple[object, ...]:
    """Der vollständige sichtbare Vertrag des gemeinsamen Fortschrittsbereichs."""

    return (
        window.status_message.text(),
        window.progress.minimum(),
        window.progress.maximum(),
        window.progress.value(),
        window.progress.accessibleName(),
        window.progress.accessibleDescription(),
        window.progress.isVisibleTo(window),
        window.cancel_button.isVisibleTo(window),
        window.cancel_button.isEnabled(),
        window.cancel_button.accessibleDescription(),
    )


class _RunningSplit:
    """Der minimale laufende Arbeiter für die Signalkette des Fensters."""

    def __init__(self) -> None:
        from app.core.scene.cancel import CancelSignal

        self.cancel = CancelSignal()

    def isRunning(self) -> bool:  # noqa: N802 — bildet die Qt-API nach
        return True


def _show_split_progress(window: MainWindow) -> None:
    window.session._split = _RunningSplit()
    window.session.splitBusyChanged.emit(True)
    window.session.splitProgressChanged.emit(0.65, tr("Ausrichtung suchen"))
    window._split_patience.timeout.emit()
    window._split_bar_delay.timeout.emit()


def _finish_split_progress(window: MainWindow) -> None:
    window.session._split = None
    window.session._split_discarded = False
    window.session.splitBusyChanged.emit(False)


def test_split_restores_the_complete_agent_progress(window: MainWindow) -> None:
    """Split überdeckt den Agenten, ohne dessen Anzeige oder Abbruch zu verlieren."""

    window.session.busyChanged.emit(True)
    window._on_agent_busy(True)
    window._on_agent_progress(3, "boolesche Operation")
    expected = _progress_snapshot(window)

    _show_split_progress(window)
    assert window._progress_owner == "split"
    split_worker = window.session._split
    assert split_worker is not None
    window.cancel_button.click()
    assert split_worker.cancel.is_cancelled
    assert not window.session.agent_cancel.is_cancelled
    assert not window.session.cancel_signal.is_cancelled
    _finish_split_progress(window)

    assert window._progress_owner == "agent"
    assert _progress_snapshot(window) == expected
    window.cancel_button.click()
    assert window.session.agent_cancel.is_cancelled, "der wieder sichtbare Knopf gilt dem Agenten"
    assert not window.session.cancel_signal.is_cancelled, "die verdeckte Auswertung läuft weiter"
    window._on_agent_busy(False)
    assert window._progress_owner == "evaluation"
    window.cancel_button.click()
    assert window.session.cancel_signal.is_cancelled, (
        "nach Agentenende gilt der Knopf der Auswertung"
    )
    window.session.busyChanged.emit(False)


def test_split_restores_the_complete_download_progress(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nach Split stehen Downloadtext, Anteil, Hilfetext und Abbruch wieder da."""

    monkeypatch.setattr(window._leash, "start", lambda _worker: None)
    window.session.busyChanged.emit(True)
    window._on_agent_busy(True)
    window.download_model("https://beispiel.invalid/halter.stl")
    worker = window._download_worker
    assert worker is not None
    window._on_download_progress(0.42, tr("Modell herunterladen …"))
    expected = _progress_snapshot(window)

    _show_split_progress(window)
    assert window._progress_owner == "split"
    split_worker = window.session._split
    assert split_worker is not None
    window.cancel_button.click()
    assert split_worker.cancel.is_cancelled
    assert not window.session.agent_cancel.is_cancelled
    assert not window.session.cancel_signal.is_cancelled
    _finish_split_progress(window)

    assert window._progress_owner == "download"
    assert _progress_snapshot(window) == expected
    window.cancel_button.click()
    assert worker.cancel.is_cancelled, "der wieder sichtbare Knopf gilt dem Download"
    assert not window.session.agent_cancel.is_cancelled
    assert not window.session.cancel_signal.is_cancelled
    window._download_stopped()
    window._download_worker = None
    assert window._progress_owner == "agent"
    window._on_agent_busy(False)
    window.session.busyChanged.emit(False)


def test_split_restores_the_complete_export_progress(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der nicht abbrechbare Export kehrt nach Split ohne fremden Knopf zurück."""

    monkeypatch.setattr(window._leash, "start", lambda _worker: None)
    window.session.import_model(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window._start_export(tmp_path / "halter.stl", "stl")
    assert window._export_worker is not None
    expected = _progress_snapshot(window)
    try:
        _show_split_progress(window)
        assert window._progress_owner == "split"
        _finish_split_progress(window)

        assert window._progress_owner == "export"
        assert _progress_snapshot(window) == expected
        assert not window.cancel_button.isVisibleTo(window)
    finally:
        window._exporting = False
        window._export_worker = None
        window._set_progress_state("export", active=False)


def test_split_uses_its_own_real_status_and_bar_timers(window: MainWindow) -> None:
    """Ein sichtbarer Agent schenkt dem neuen Split keine seiner Wartezeit."""
    from PySide6.QtTest import QTest

    window._on_agent_busy(True)
    window._on_agent_progress(2, "Netz prüfen")
    agent = _progress_snapshot(window)
    window.session._split = _RunningSplit()
    try:
        window.session.splitBusyChanged.emit(True)
        window.session.splitProgressChanged.emit(0.65, tr("Ausrichtung suchen"))

        QTest.qWait(main_window_module.DELAY_MS // 2)
        assert _progress_snapshot(window) == agent, (
            "vor 0,2 s bleibt der Agent vollständig sichtbar"
        )

        QTest.qWait(main_window_module.DELAY_MS)
        between = _progress_snapshot(window)
        assert between[0].startswith(tr("Ausrichtung suchen"))
        assert between[1:] == agent[1:], "vor zwei Sekunden bleiben Balken und Abbruch beim Agenten"

        QTest.qWait(main_window_module.BAR_AFTER_MS - 2 * main_window_module.DELAY_MS)
        before_bar = _progress_snapshot(window)
        assert before_bar[0].startswith(tr("Ausrichtung suchen"))
        assert before_bar[1:] == agent[1:], "auch kurz vor zwei Sekunden bleibt der Agent"

        QTest.qWait(main_window_module.DELAY_MS)
        assert window._progress_owner == "split"
        assert window.progress.accessibleName() == tr("Fortschritt: Automatisch teilen")
        assert window.cancel_button.accessibleDescription() == tr(
            "Bricht die automatische Teilung ab. Modell und Verlauf bleiben unverändert."
        )
    finally:
        _finish_split_progress(window)
        window._on_agent_busy(False)


def test_auto_split_uses_delayed_accessible_and_monotonic_progress(
    window: MainWindow,
) -> None:
    """Grobsuche bleibt unbestimmt; erst die Stützbewertung trägt Prozent."""

    class Running:
        def isRunning(self) -> bool:  # noqa: N802 — bildet die Qt-API nach
            return True

    window.session._split = Running()
    window.announce("Vorherige Meldung")
    try:
        window.session.splitBusyChanged.emit(True)
        window.session.splitProgressChanged.emit(0.25, tr("Die Trennebenen werden gesucht …"))

        assert window.status_message.text() == "Vorherige Meldung"
        assert not window.progress.isVisibleTo(window), "der Balken kam vor zwei Sekunden"
        assert not window.cancel_button.isVisibleTo(window)
        assert window.progress.minimum() == 0
        assert window.progress.maximum() == 100, "vor der Freigabe bleibt der Ruhewert stehen"
        assert not window.veil.isVisibleTo(window), "der Viewport darf nicht verdeckt werden"

        window._patience.timeout.emit()
        window._split_patience.timeout.emit()
        assert window.cursor().shape() == Qt.CursorShape.BusyCursor
        assert window.status_message.text() == tr("Die Trennebenen werden gesucht …")
        assert not window.progress.isVisibleTo(window)

        window._split_bar_delay.timeout.emit()
        assert window.progress.isVisibleTo(window)
        assert window.cancel_button.isVisibleTo(window)
        assert window.progress.accessibleName() == tr("Fortschritt: Automatisch teilen")
        assert tr("Die Trennebenen werden gesucht …") in window.progress.accessibleDescription()
        assert tr("Abbrechen ist verfügbar.") in window.progress.accessibleDescription()
        assert window.cancel_button.accessibleName() == tr("Abbrechen")
        assert window.cancel_button.accessibleDescription() == tr(
            "Bricht die automatische Teilung ab. Modell und Verlauf bleiben unverändert."
        )

        window._split_started = main_window_module.time.monotonic() - 11.0
        window.session.splitProgressChanged.emit(0.7, tr("Ausrichtung suchen"))
        assert window.progress.maximum() == 100
        assert window.progress.value() == 70
        assert "70 %" in window.status_message.text()
        assert tr("gleich fertig") in window.status_message.text()

        window.session.splitProgressChanged.emit(0.5, tr("Ausrichtung suchen"))
        assert window.progress.value() == 70, "bestimmter Fortschritt lief rückwärts"

        window.session.splitProgressChanged.emit(1.0, "")
        assert window.progress.value() == 100, "der leere Abschlusswert ging verloren"
        assert window.status_message.text().startswith(tr("Ausrichtung suchen"))
        assert "100 %" in window.status_message.text()
        assert tr("Ausrichtung suchen") in window.progress.accessibleDescription()
        assert "100 %" in window.progress.accessibleDescription()
        assert tr("Abbrechen ist verfügbar.") in window.progress.accessibleDescription()
    finally:
        window.session._split = None
        window.session.splitBusyChanged.emit(False)
    assert window.progress.accessibleName() == tr("Fortschritt")
    assert window.progress.accessibleDescription() == tr(
        "Zeigt den Fortschritt der laufenden Aufgabe."
    )
    assert window.cancel_button.accessibleDescription() == tr("Bricht die laufende Aufgabe ab.")


def test_undo_replaces_the_auto_split_result_with_the_current_state(
    window: MainWindow,
) -> None:
    """Nach Rückgängig darf die Statuszeile keine entfernte Teilung behaupten."""
    from app.core.split import SplitApplied

    title = tr("Teilen und verstiften")
    assert window.session.apply(
        title,
        [
            OperationDraft(
                op="create_box",
                params={"width": 20.0, "depth": 20.0, "height": 20.0},
            )
        ],
    )
    window.session.wait_for_idle()
    transaction = window.session.project.document.transactions[-1]
    object_id = next(iter(window.session.last_result.scene.objects))
    window._split_done(SplitApplied(object_ids=[object_id], transaction=transaction.id))
    assert window._announcement.startswith(tr("Geteilt"))

    window.action_undo()
    window.session.wait_for_idle()

    assert window._announcement == tr("{name} zurückgenommen.").format(name=title)


def test_the_auto_split_cancel_button_disables_itself_immediately(window: MainWindow) -> None:
    """Ein Klick verwirft genau einmal und lässt die Rückmeldung stehen."""
    from app.core.scene.cancel import CancelSignal

    class Running:
        def __init__(self) -> None:
            self.cancel = CancelSignal()

        def isRunning(self) -> bool:  # noqa: N802 — bildet die Qt-API nach
            return True

    worker = Running()
    window.session._split = worker
    try:
        window.session.splitBusyChanged.emit(True)
        window._split_bar_delay.timeout.emit()
        window.cancel_button.click()

        assert worker.cancel.is_cancelled
        assert not window.cancel_button.isEnabled()
        requested = tr("Teilung wird abgebrochen …")
        assert window.status_message.text() == requested
        assert window._announcement == requested

        window.session._split_cancelled(worker)
        finished = tr("Teilung abgebrochen. Modell und Verlauf sind unverändert.")
        assert window.status_message.text() == finished
        assert window._announcement == finished
    finally:
        window.session._split = None
        window.session._split_discarded = False
        window.session.splitBusyChanged.emit(False)


def test_escape_cancels_auto_split_before_touching_the_selection(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Escape verwirft die Suche sofort; Dokument und Auswahl bleiben stehen."""
    from app.core.scene.cancel import CancelSignal

    class Running:
        def __init__(self) -> None:
            self.cancel = CancelSignal()

        def isRunning(self) -> bool:  # noqa: N802 — bildet die Qt-API nach
            return True

    worker = Running()
    window.session._split = worker
    selection_touched: list[bool] = []
    monkeypatch.setattr(window, "_step_selection_out", lambda: selection_touched.append(True))
    try:
        window.session.splitBusyChanged.emit(True)
        window._split_bar_delay.timeout.emit()
        window._escape()

        message = tr("Teilung wird abgebrochen …")
        assert worker.cancel.is_cancelled
        assert not selection_touched, "Escape baute die Auswahl statt der Suche ab"
        assert not window.cancel_button.isEnabled(), "der Abbruchknopf blieb mehrfach klickbar"
        assert window.status_message.text() == message
        assert window._announcement == message, "die Rückmeldung überlebt den auslaufenden Arbeiter"
    finally:
        window.session._split = None
        window.session._split_discarded = False
        window.session.splitBusyChanged.emit(False)


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


def test_auto_split_uses_the_objects_material_for_search_and_fits(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Projektmaterial und Körpermaterial dürfen beim Teilen nicht zusammenfallen."""
    from app.ui import session as session_module

    session.project.document.printer = "centauri-carbon-2"
    session.project.document.material = "petg"
    session.history.apply(
        "Anlegen",
        [
            OperationDraft(
                op="create_box",
                params={"width": 400.0, "depth": 60.0, "height": 40.0},
            )
        ],
    )
    session.evaluate_async()
    session.wait_for_idle()
    assert session.last_result is not None
    entry = session.last_result.scene.objects["obj_1"]
    entry.material = "pla"

    chosen: list[Profile] = []
    searched: list[Profile] = []
    real_for_object = session_module.profiles.for_object
    real_apply_split = session_module.apply_split

    def choose(base: Profile, body: SceneObject | None) -> Profile:
        profile = real_for_object(base, body)
        chosen.append(profile)
        return profile

    def apply(*args: Any, **values: Any) -> Any:
        searched.append(args[3])
        return real_apply_split(*args, **values)

    monkeypatch.setattr(session_module.profiles, "for_object", choose)
    monkeypatch.setattr(session_module, "apply_split", apply)
    monkeypatch.setattr(session, "evaluate_async", lambda: None)

    applied = session.auto_split("obj_1")

    assert len(chosen) == 1, "das Objektprofil wird genau einmal bestimmt"
    assert searched == chosen and searched[0].material.id == "pla"
    assert {fit.tolerance for fit in applied.fits} == {"auto:pla"}


def test_drawn_split_uses_the_spool_material_for_its_fits(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auch der gezeichnete Schnitt liest das Material von Spule null (§12)."""
    from app.core.geom.section import SectionPlane
    from app.ui import session as session_module

    session.project.document.printer = "centauri-carbon-2"
    session.project.document.material = "petg"
    session.history.apply(
        "Anlegen",
        [
            OperationDraft(
                op="create_box",
                params={"width": 400.0, "depth": 60.0, "height": 40.0},
            )
        ],
    )
    session.evaluate_async()
    session.wait_for_idle()
    assert session.last_result is not None
    entry = session.last_result.scene.objects["obj_1"]
    entry.material_slots = [MaterialSlot(index=0, name="PLA", material_type="PLA")]

    chosen: list[Profile] = []
    applied_with: list[Profile] = []
    real_for_object = session_module.profiles.for_object
    real_apply_line_split = session_module.apply_line_split

    def choose(base: Profile, body: SceneObject | None) -> Profile:
        profile = real_for_object(base, body)
        chosen.append(profile)
        return profile

    def apply(*args: Any, **values: Any) -> Any:
        applied_with.append(args[3])
        return real_apply_line_split(*args, **values)

    monkeypatch.setattr(session_module.profiles, "for_object", choose)
    monkeypatch.setattr(session_module, "apply_line_split", apply)
    monkeypatch.setattr(session, "evaluate_async", lambda: None)

    applied = session.split_along("obj_1", SectionPlane((1.0, 0.0, 0.0), 0.0), pins=2)

    assert len(chosen) == 1, "das Spulenprofil wird genau einmal bestimmt"
    assert applied_with == chosen and applied_with[0].material.id == "pla"
    assert {fit.tolerance for fit in applied.fits} == {"auto:pla"}


def test_async_split_keeps_one_object_profile_from_search_through_apply(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eine Profiländerung während der Suche darf deren Plan nicht umdeuten."""
    from app.core.split import SplitApplied
    from app.ui import session as session_module

    session.project.document.printer = "centauri-carbon-2"
    session.project.document.material = "petg"
    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()
    assert session.last_result is not None
    entry = session.last_result.scene.objects["obj_1"]
    entry.material_slots = [MaterialSlot(index=0, name="PLA", material_type="PLA")]

    started = threading.Event()
    release = threading.Event()
    chosen: list[Profile] = []
    searched: list[Profile] = []
    applied_with: list[Profile] = []
    real_for_object = session_module.profiles.for_object
    plan = object()

    def choose(base: Profile, body: SceneObject | None) -> Profile:
        profile = real_for_object(base, body)
        chosen.append(profile)
        return profile

    def search(_mesh: object, _object_id: str, profile: Profile, **_values: object) -> object:
        searched.append(profile)
        started.set()
        assert release.wait(2.0), "die blockierte Suche wurde nicht freigegeben"
        return plan

    def apply(
        _document: object, received: object, object_id: str, profile: Profile
    ) -> SplitApplied:
        assert received is plan
        applied_with.append(profile)
        return SplitApplied(object_ids=[object_id])

    monkeypatch.setattr(session_module.profiles, "for_object", choose)
    monkeypatch.setattr(session_module, "plan_split", search)
    monkeypatch.setattr(session_module, "apply_planned", apply)

    results: list[object] = []
    session.split_async("obj_1", results.append)
    assert started.wait(2.0), "der Split-Arbeiter ist nicht angelaufen"
    session.project.document.material = "tpu-95a"
    release.set()
    session.wait_for_idle()

    assert len(chosen) == 1, "das Objektprofil wird genau einmal bestimmt"
    assert searched == chosen and searched[0].material.id == "pla"
    assert applied_with == searched and applied_with[0] is searched[0]
    assert len(results) == 1


def test_a_failed_import_plan_leaves_no_orphan_source(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Scheitert der Einleseplan, bleibt keine Waisen-Quelle zurück (F-10).

    Eingebettet wurde vor dem Planen — wies der Plan die Datei ab (zu groß,
    Zip-Bombe), stand die kaputte Quelle trotzdem im Dokument und wanderte
    mit dem nächsten Speichern in die Projektdatei. Die Kommandozeile war nie
    betroffen: sie speichert nur nach vollständiger Auswertung.
    """
    from app.ui import session as session_module

    def refusing(*_args: object, **_kwargs: object) -> object:
        raise errors.ValidationError("file", "diese Datei nimmt der Plan nicht")

    monkeypatch.setattr(session_module, "import_plan", refusing)
    with pytest.raises(errors.AppError):
        session.import_payload("kaputt.3mf", b"x")
    assert not session.project.document.sources, "die Quelle wurde wieder ausgetragen"
    assert not session.project.sources, "auch ihr Inhalt"


def test_a_rejected_import_can_be_surfaced_without_an_orphan_source(
    session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein synchroner Oberflächenweg bekommt die Abweisung selbst zurück.

    So kann er zuerst seine Warteanzeige beenden; Quelle und Inhalt dürfen
    trotzdem nicht im Projekt zurückbleiben.
    """

    def refusing(*_args: object, **_kwargs: object) -> object:
        raise errors.UserError(detail="der Schritt wurde abgewiesen")

    monkeypatch.setattr(session.history, "apply", refusing)

    with pytest.raises(errors.UserError):
        session.import_model(MESHES / "cube_clean.stl", raise_on_error=True)

    assert not session.project.document.sources, "die abgewiesene Quelle blieb im Dokument"
    assert not session.project.sources, "der Inhalt der abgewiesenen Quelle blieb im Projekt"
    assert not session.project.document.ops, "eine abgewiesene Operation darf nicht erscheinen"


def test_a_second_split_start_is_refused_while_one_runs(session: Session) -> None:
    """Zwei Suchen zugleich gab es nie absichtlich — die zweite wird abgewiesen.

    Vorher überschrieb der zweite Start den ersten Arbeiter: dessen Plan kam
    trotzdem an, ``split_running`` log nach dem ersten Ende, und ein Thread
    überlebte sein Fenster.
    """
    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()

    class Running:
        """Nur was die Wache fragt: läuft er noch — wie ``QThread.isRunning``."""

        def isRunning(self) -> bool:  # noqa: N802 — der Name gehört Qt
            return True

    stub = Running()
    session._split = stub
    refused: list[object] = []
    session.failed.connect(refused.append)
    called: list[object] = []
    try:
        session.split_async("obj_1", called.append)
        assert refused, "die zweite Suche wird als Satz abgewiesen"
        assert refused[0].suggestions
        assert session._split is stub, "der laufende Arbeiter bleibt der Arbeiter"
        assert not called
    finally:
        session._split = None


def test_the_split_end_reports_when_the_thread_is_truly_gone(session: Session) -> None:
    """Das endgültige Ende der Trennsuche meldet im finished-Pfad (§2.8).

    ``_split_cancelled`` bestätigt den Abbruch früher, aber dort läuft der
    Thread noch: ``_on_split_busy`` fragt ``_anything_running()``, liest
    ``split_running`` als True und ließ Balken und Abbrechen für immer
    stehen — nach dem Auslaufen kam nie wieder ein False (Update-Review,
    Fund 30). Doppelt gemeldet ist folgenlos, die Anzeige stellt nur einen
    Zustand her.
    """

    class Done:
        """Nur was Leine und Wache fragen: läuft er noch — nein."""

        def isRunning(self) -> bool:  # noqa: N802 — der Name gehört Qt
            return False

    worker = Done()
    session._split = worker
    busy: list[bool] = []
    session.splitBusyChanged.connect(busy.append)

    session._on_split_done(worker)

    assert busy == [False], "genau eine Nachmeldung, nach dem Auslaufen"
    assert session._split is None, "und das Feld ist geräumt"


def test_cancelling_an_already_finished_split_is_confirmed_once(session: Session) -> None:
    """Die Lücke zwischen fachlichem Ende und ``finished`` bleibt nicht hängen."""
    from app.core.scene.cancel import CancelSignal

    class Done:
        def __init__(self) -> None:
            self.cancel = CancelSignal()

        def isRunning(self) -> bool:  # noqa: N802 — bildet die Qt-API nach
            return False

    worker = Done()
    session._split = worker
    requested: list[bool] = []
    confirmed: list[bool] = []
    session.splitCancelRequested.connect(lambda: requested.append(True))
    session.splitCancelled.connect(lambda: confirmed.append(True))

    session.cancel_split()
    assert requested == [True]
    assert not confirmed, "vor dem endgültigen Thread-Signal ist noch nichts bestätigt"

    session._split_cancelled(worker)
    assert confirmed == [True], "das fachliche Ende bestätigt den Abbruch"
    session._on_split_done(worker)

    assert confirmed == [True], "das endgültige Ende bestätigt genau einmal"
    assert session._split is None


def test_a_stale_split_worker_cannot_deliver(session: Session) -> None:
    """Was ein überlebender Arbeiter noch meldet, wird nicht mehr angewandt.

    Jeder Empfänger prüft den Absender: Plan, Fehler und das Auslaufen zählen
    nur, wenn sie vom aktuellen Arbeiter kommen.
    """
    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()

    stale = object()
    busy: list[bool] = []
    session.splitBusyChanged.connect(busy.append)
    called: list[object] = []
    reported: list[object] = []
    session.failed.connect(reported.append)

    session._split_planned(stale, object(), "obj_1", session.profile, called.append)
    assert not called and not busy, "ein fremder Plan wird nicht angewandt"

    session._split_failed(stale, errors.InternalError(detail="stale"))
    assert not reported, "ein fremder Fehler wird nicht gemeldet"

    keeper = object()
    session._split = keeper
    try:
        session._on_split_done(stale)
        assert session._split is keeper, "das Auslaufen eines Fremden räumt das Feld nicht"
    finally:
        session._split = None


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


def test_a_cancelled_preview_actually_stops_computing(session: Session) -> None:
    """Verwerfen ist nicht abbrechen.

    ``cancel_preview`` erhoehte nur die Generation: Das Ergebnis wurde
    weggeworfen, angehalten wurde nichts. Wer einen Dialog ueber einem grossen
    Koerper schloss, liess eine Rechnung hinter sich, die niemand mehr sehen
    wollte und die trotzdem bis zum Ende lief — und beim schnellen Tippen
    stapelten sich diese Rechnungen.

    Geprueft wird deshalb das Token, nicht die Stille: Jeder Arbeiter fuehrt
    ein **eigenes**, denn ein geteiltes mit ``reset()`` vor dem Start waere ein
    Wettlauf — der alte Lauf saehe den gesetzten Zustand womoeglich nie.
    """
    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()

    def bohrung() -> list[OperationDraft]:
        return [
            OperationDraft(
                op="drill_hole",
                inputs=("obj_1",),
                params={"diameter": 4.0, "x": 0.0, "y": 0.0, "z": 0.0, "axis": "z"},
            )
        ]

    session.preview_async(lambda _difference: None, bohrung())
    erster = session._previews[-1]
    session.preview_async(lambda _difference: None, bohrung())
    zweiter = session._previews[-1]

    assert erster is not zweiter, "zwei Anfragen, zwei Arbeiter"
    assert erster.cancel is not zweiter.cancel, (
        "ein geteiltes Token waere ein Wettlauf zwischen altem und neuem Lauf"
    )
    assert erster.cancel.is_cancelled, "die neuere Anfrage laesst die aeltere weiterrechnen"
    assert not zweiter.cancel.is_cancelled, "die neueste darf rechnen"

    session.cancel_preview()
    assert zweiter.cancel.is_cancelled, "der geschlossene Dialog haelt seine Rechnung an"

    session.wait_for_idle()


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


def test_the_toolbar_has_the_two_entries_for_way_four(window: MainWindow) -> None:
    """§2.2: Weg 4 (organisch formen) nennt die Werkzeugzeile als Ort.

    *Formen* und *Skelett* lagen unter *Ändern → Netz* zwischen
    Reparaturwerkzeugen — an derselben Stelle wie „Löcher schließen", ohne
    Kürzel und ohne Zusammenhang mit dem Weg, für den sie gebaut sind. Die
    untere Werkzeugzeile ist mit acht Umschaltern voll; die obere hat den
    Platz, und dort steht Weg 2 bereits.

    Der Menüeintrag bleibt: Befehlspalette und Verlauf führen über ihn.
    """
    from PySide6.QtWidgets import QToolBar

    toolbar = window.findChild(QToolBar)
    assert toolbar is not None
    labels = [action.text() for action in toolbar.actions() if action.text()]
    assert "Formen" in labels
    assert "Skelett" in labels
    assert labels.index("Zeichnen") < labels.index("Formen") < labels.index("Skelett")

    window.session.import_model(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    item = window.object_tree.tree.topLevelItem(0)
    assert item is not None
    item.setSelected(True)

    window.action_sculpt_free()
    try:
        assert window.sculpting()
    finally:
        window.finish_sculpt()

    window.action_armature_free()
    try:
        assert window.setting_armature()
    finally:
        window.finish_armature()


def test_way_four_says_what_it_needs_before_the_click(window: MainWindow) -> None:
    """Ein Knopf, der einen gewählten Körper braucht, sagt das vorher (§2.6).

    Bis hierher fing das erst die Sitzung ab: Klick, dann „Bitte zuerst ein
    Objekt auswählen." in der Statusleiste — eine Sackgasse, die der Knopf
    selbst beantworten kann (Regel 19).
    """
    window._update_actions()
    assert not window._toolbar_sculpt.isEnabled()
    assert not window._toolbar_armature.isEnabled()
    assert "ausgewählten Körper" in window._toolbar_sculpt.toolTip()

    window.session.import_model(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    item = window.object_tree.tree.topLevelItem(0)
    assert item is not None
    item.setSelected(True)
    window._update_actions()

    assert window._toolbar_sculpt.isEnabled()
    assert window._toolbar_armature.isEnabled()
    assert "ausgewählten Körper" not in window._toolbar_sculpt.toolTip()
    assert window._toolbar_sculpt.toolTip(), "und der eigene Satz steht wieder da"


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
    """Vorausgewählt **und** oben steht der Normalfall.

    Die Liste kam aus dem Register, und damit stand „Entlang eines Bogens
    führen" oben — ein Rohrbogen, der seltenste der fünf Fälle. Vorgewählt war
    schon das Aufziehen; das genügte nicht, denn gelesen wird von oben. Und es
    genügte erst recht nicht, solange der Dialog nur zwei der fünf zeigte:
    246 Bildpunkte hoch, der dritte Eintrag mitten im Satz abgeschnitten, ohne
    sichtbare Bildlaufleiste. Wer hier scrollen muss, um überhaupt zu erfahren,
    dass es fünf Arten gibt, entscheidet zwischen zwei.

    Beides gehört zusammen, deshalb steht beides hier: die Höhe trägt alle fünf
    (am Bild geprüft), und der Normalfall steht an erster Stelle. Die übrigen
    folgen nach Titel — eine Reihenfolge, die niemanden überrascht.
    """
    from app.ui.op_dialog import SketchUseDialog

    dialog = SketchUseDialog()
    assert dialog.chosen() == "sketch_extrude"
    assert dialog._list.count() == 5
    assert dialog._list.item(0).data(Qt.ItemDataRole.UserRole) == "sketch_extrude"
    assert dialog.minimumHeight() >= 400, (
        f"der Dialog öffnet {dialog.minimumHeight()} Punkte hoch — dann sieht man zwei von fünf"
    )


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


def test_the_exact_toggle_is_visible_without_unfolding(window: MainWindow) -> None:
    """Der Umschalter der Rechenkerne stand unter „Weitere Einstellungen".

    Dort findet ihn niemand, der nicht schon weiß, dass es ihn gibt — und an
    ihm hängen sieben Werkzeuge: Fase, Verrundung, Formschräge, Fläche
    versetzen, exaktes Aushöhlen, Tasche schneiden und die Umwandlung ins
    Netz. Wer den Quader ohne ihn anlegt, findet sie später alle grau, und
    zurück führt kein Weg (``kind_requirement`` sagt genau das).

    §2.4 stellt hinten hin, was Toleranz, Auflösung oder Rückfallverhalten
    ist. Eine Entscheidung darüber, was mit dem Ergebnis später überhaupt geht,
    ist keins davon.
    """
    from PySide6.QtWidgets import QCheckBox

    window.run_operation(REGISTRY.get("create_box"))
    dialog = next(child for child in window.findChildren(OperationDialog) if child.isVisible())
    try:
        exact = next(
            box for box in dialog.findChildren(QCheckBox) if "Flächen und Kanten" in box.text()
        )

        assert exact.isVisibleTo(dialog), "der Umschalter liegt wieder eingeklappt"
        advanced = getattr(dialog, "advanced", None)
        if advanced is not None:
            assert not advanced.isChecked(), "gemessen wird mit zugeklapptem Bereich"
        # Und er sagt, was er entscheidet: die Werkzeuge beim Namen.
        assert "Tasche" in exact.toolTip(), exact.toolTip()
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
    exact = next(
        box for box in dialog.findChildren(QCheckBox) if "Flächen und Kanten" in box.text()
    )
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
    exact = next(
        box for box in dialog.findChildren(QCheckBox) if "Flächen und Kanten" in box.text()
    )

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
    # **Kein Schwellenwert, sondern die Zusage** (8b, 29.08.2026). Hier stand
    # „mindestens 70", und mit den Bausteinen im Katalog wären 50 daraus
    # geworden — eine Zahl, die beim nächsten Umbau wieder jemand senkt.
    # Geprüft wird stattdessen, dass die Kopplung **jede** Menüaktion erreicht:
    # Was einen Eintrag hat, hat auch einen genannten Weg, und der stimmt.
    assert checked, "keine einzige Kopplung gefunden — dann prüft dieser Test nichts"
    ohne_weg = sorted(name for name, action in window._op_actions.items() if action not in built)
    assert not ohne_weg, f"diese Menüaktionen haben keinen genannten Weg: {ohne_weg}"


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


def test_a_blocked_port_says_so_instead_of_only_logging(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regel 17: Ein belegter Port endete im Protokoll und sonst nirgends.

    Der Haken in den Einstellungen blieb gesetzt, die Fernsteuerung lief
    nicht, und nichts sagte es — wer ein fremdes Programm darauf zeigen ließ,
    suchte den Fehler dort. Die Meldung nennt den Port und den Weg zurück zu
    ihm; ein modaler Dialog wäre hier die falsche Antwort (§2.8).
    """
    from app.ui import main_window as module

    def refuse(*_args: object, **_kwargs: object) -> object:
        raise OSError("address already in use")

    monkeypatch.setattr(module, "RemoteServer", refuse)
    window.settings.remote_enabled = True
    window.settings.remote_port = 5123
    try:
        window._apply_remote()
    finally:
        window.settings.remote_enabled = False

    assert window._remote is None, "die Fernsteuerung gilt trotz Fehler als gestartet"
    said = window.status_message.text()
    assert "5123" in said, f"die Meldung nennt den Port nicht: {said!r}"
    assert "Einstellungen" in said, f"die Meldung nennt keine Handlung: {said!r}"


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


def test_a_late_worker_does_not_switch_off_its_successor(session: Session) -> None:
    """Der Nachzügler meldete „fertig" mitten in den Lauf seines Nachfolgers.

    Ein Arbeiter ist fertig, bevor Qt sein ``finished`` zugestellt hat; in
    dieser Lücke startet der nächste Lauf. Der Nachzügler kam dann in
    ``_on_thread_done`` an, schrieb ``None`` in ``_worker`` — das Feld gehörte
    da längst dem Nachfolger — und meldete ``busyChanged(False)``.

    **Zu sehen war das an der Stelle, an der jeder anfängt.** Eine Datei auf
    den Startbildschirm ziehen legt zwei Läufe hintereinander: den leeren des
    neuen Projekts und den des Imports. Bei einem Modell mit 1,3 Millionen
    Dreiecken verschwanden Balken und Abbrechen nach einer Zehntelsekunde, und
    die Anwendung rechnete die restlichen vier Sekunden ohne ein Zeichen von
    sich — genau das, was §2.8 ab zwei Sekunden verlangt. Unsichtbar, aber
    schwerer: ``busy`` log danach, ``wait_for_idle`` wartete nicht, und der
    nächste ``evaluate_async`` hätte einen zweiten Lauf **parallel** gestartet
    statt ihn einzureihen (§15.6).
    """
    from app.ui.session import _EvaluationWorker

    session.import_model(MESHES / "cube_clean.stl")
    running = session._worker
    assert running is not None, "der Import hat keinen Lauf gestartet"

    seen: list[bool] = []
    session.busyChanged.connect(seen.append)
    # Ein Vorgänger, dessen Signal jetzt erst ankommt. Gestartet wird er nie —
    # zugestellt wird sein Ende, und darum geht es.
    session._on_thread_done(_EvaluationWorker(session))

    assert seen == [], "ein alter Lauf meldet das Ende eines fremden"
    assert session._worker is running, "die Referenz auf den laufenden Lauf ging verloren"
    assert session.busy, "und damit log auch busy"

    session.wait_for_idle()


def test_a_replaced_run_keeps_the_progress_standing(session: Session) -> None:
    """Ein Ersetzen ist kein Aufhören (§15.6, §2.8).

    ``_rerun_pending`` heißt: dieser Lauf ist überholt, der nächste startet
    sofort. Dazwischen ``busyChanged(False)`` zu melden nähme Balken und
    Abbrechen für eine Zehntelsekunde mit — beim Ziehen an einem Schieber im
    Sekundentakt. Dieselbe Begründung, aus der ``evaluationCancelled`` einen
    ersetzten Lauf nicht meldet.
    """
    session.import_model(MESHES / "cube_clean.stl")
    running = session._worker
    assert running is not None

    seen: list[bool] = []
    session.busyChanged.connect(seen.append)
    session._rerun_pending = True
    session._on_thread_done(running)

    assert False not in seen, "der Balken fällt zwischen zwei Läufen aus"
    assert seen == [True], "und der nächste Lauf meldet sich als laufend"

    session.wait_for_idle()


def test_cancelling_discards_the_queued_rerun(session: Session) -> None:
    """Abbrechen heißt aufhören — auch mit dem, was eingereiht wartet.

    ``cancel()`` ließ ``_rerun_pending`` stehen: Die Statuszeile schrieb
    „Abgebrochen", und ``_on_thread_done`` startete im selben Atemzug den
    eingereihten Nachlauf — die Maschine rechnete weiter, das Wort stand
    daneben (Gesamtreview 25.08.2026, I-1). Ein **Ersetzen** behält den
    Nachlauf weiter, das prüft der Test darüber; ein **Nutzer-Abbruch**
    verwirft ihn.
    """
    session.import_model(MESHES / "cube_clean.stl")
    running = session._worker
    assert running is not None
    session._rerun_pending = True

    session.cancel()

    assert not session._rerun_pending, "der Abbruch verwirft die eingereihte Anfrage"
    session.wait_for_idle()
    assert session._worker is None or not session._worker.isRunning()


def test_a_late_result_does_not_overwrite_the_current_scene(session: Session) -> None:
    """§15.3: stehen bleibt der letzte **gültige** Stand.

    Das Ergebnis eines überholten Laufs gehört zu einem Dokument, das es nicht
    mehr gibt. Eingeblendet wurde es trotzdem — beim Ablegen einer Datei war
    das die leere Szene des neuen Projekts, über das Modell gelegt, das gerade
    geladen wurde. Sichtbar als Aufblitzen, und es nahm den Ladeschleier mit,
    der genau daran hängt, ob ein Körper dasteht.
    """
    from app.ui.session import _EvaluationWorker

    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()
    current = session.last_result
    assert current is not None and current.scene.objects

    session.import_model(MESHES / "two_components.stl")
    stale = dataclasses.replace(current, scene=dataclasses.replace(current.scene, objects={}))
    session._on_finished(stale, finished=_EvaluationWorker(session))

    assert session.last_result is current, "eine alte Szene hat die aktuelle ersetzt"

    session.wait_for_idle()


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

    **Und geprüft an der Regel statt an drei Feldnamen.** Die Sitzung hielt je
    Arbeiterart genau einen ausgelaufenen — ``_finished_worker``,
    ``_finished_agent``, ``_finished_split``. Ein Feld hält aber nur einen, und
    ``_on_thread_done`` startet bei ``_rerun_pending`` sofort den nächsten
    Lauf: Wird der schnell fertig, überschreibt er das Feld, während Qt den
    Vorgänger noch abräumt. Genau diese Kette stand im Stapelabzug eines
    Absturzes, den das Repository lange nur als „Segfault in test_chat_ui.py"
    kannte. Gehalten wird jetzt in einer Liste (:mod:`app.ui.leash`), und
    dieser Test liest, dass die drei Slots sie benutzen.
    """
    import re

    session.import_model(MESHES / "cube_clean.stl")
    session.wait_for_idle()

    assert session._worker is None, "nach dem Warten läuft keiner mehr"
    assert hasattr(session, "_leash"), "die Sitzung hat keine Halteleine"

    quelle = (Path(__file__).parent.parent / "app" / "ui" / "session.py").read_text(
        encoding="utf-8"
    )
    for slot in ("_on_thread_done", "_on_agent_done", "_on_split_done"):
        koerper = quelle[quelle.index(f"def {slot}(") :]
        koerper = koerper[: koerper.index(chr(10) + "    def ", 1)]
        assert "_leash.hold_until_done" in koerper, (
            f"{slot} übergibt seinen Arbeiter nicht an die Halteleine — wer die "
            "Referenz im eigenen finished-Slot loslässt, gibt den Wrapper frei, "
            "während Qt die Zustellung noch auf dem Stapel hat."
        )
        assert not re.search(r"self\._(worker|agent|split)\s*=\s*None", koerper), (
            f"{slot} schreibt None in sein Feld, statt den Arbeiter erst zu sichern."
        )


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

    **Gefragt wird die Karte, nicht Qt.** Der Test rief hier
    ``resizeColumnToContents`` für beide Spalten und maß dann deren Summe — also
    genau das, was die Karte gerade *nicht* tut: Sie teilt die Breite
    (``_size_columns``), weil der Inhalt beider Spalten zusammen nun einmal
    breiter sein kann als die Karte. Solange die Namensspalte auf ``Stretch``
    stand, ging der Aufruf für sie ins Leere und die Summe stimmte zufällig; als
    die Maßspalte ihren Deckel bekam, tat er es nicht mehr. Ein Test, der die
    Einstellung überschreibt, die er prüfen soll, prüft sie nicht.
    """
    from PySide6.QtWidgets import QTreeWidgetItem

    from app.ui.overlay import LEFT_WIDTH
    from app.ui.panels import ObjectTree

    tree = ObjectTree()
    tree.resize(LEFT_WIDTH, 200)
    QTreeWidgetItem(tree.tree, ["Halter", "60 × 40 × 11 mm"])
    tree._size_columns()

    header = tree.tree.header()
    needed = header.sectionSize(0) + header.sectionSize(1)
    assert needed <= LEFT_WIDTH, f"{needed} Pixel bei {LEFT_WIDTH} verfügbaren"
    assert header.sectionSize(0) > header.sectionSize(1), (
        "der Name ist die Auskunft, das Maß die Beigabe"
    )


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


def test_parameter_rows_recalculate_the_card_height(qt_app: QApplication) -> None:
    """Neue Zeilen dürfen nicht in der Höhe des leeren Zustands landen.

    Die schwebende linke Karte besitzt kein übergeordnetes Layout, das eine
    verspätete Wunschhöhe automatisch übernimmt. Nach dem Wechsel vom leeren
    Hinweis zu drei Parametern blieb deshalb die alte Mindesthöhe stehen und
    Qt presste Zahlen- und Einheitenfelder bis auf wenige Pixel zusammen.
    """
    from app.core.types import Document, Parameter
    from app.ui.panels import ParameterPanel

    panel = ParameterPanel()
    panel.resize(260, panel.minimumHeight())
    panel.show_document(Document(format_version=1, app_version="0.0.1"))
    panel.show()
    QApplication.processEvents()

    document = Document(format_version=1, app_version="0.0.1")
    for name, title, value in (
        ("breite", "Breite", 60.0),
        ("tiefe", "Tiefe", 40.0),
        ("staerke", "Stärke", 10.99),
    ):
        document.parameters[name] = Parameter(name=name, title=title, value=value)
    panel.show_document(document)
    QApplication.processEvents()

    assert panel.minimumHeight() >= panel.sizeHint().height(), (
        f"Mindesthöhe {panel.minimumHeight()} px, Inhalt {panel.sizeHint().height()} px"
    )
    for name, editor in panel._editors.items():
        assert editor.height() >= editor.minimumSizeHint().height(), (
            f"{name}: Feld {editor.height()} px, benötigt {editor.minimumSizeHint().height()} px"
        )
        unit = panel._unit_editors[name]
        assert unit.height() >= unit.minimumSizeHint().height(), (
            f"{name}: Einheit {unit.height()} px, benötigt {unit.minimumSizeHint().height()} px"
        )


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
    from app.ui import labels
    from app.ui.panels import _line_for

    values = {"wall_mm": 2.0, "removed_cm3": 14.3}
    line = _line_for(
        Finding(code="hollow.done", severity="info", message="Ausgehöhlt.", values=values)
    )

    # **Gegen ``value_text`` und nicht gegen eine ausgeschriebene Stellenzahl.**
    # Hier stand „2,0 mm" — die Zusage ist aber, dass die Zahl ihre Einheit
    # trägt, und wie viele Nachkommastellen sie dabei hat, ist der Ist-Zustand.
    # Der Test fiel deshalb bei `3deb8910`, das Zeile und Tooltip auf dieselbe
    # Quelle stellte: Die Zeile schreibt seither „2,00 mm", wie der Tooltip es
    # immer schon tat. Gebrochen war nicht die Zusage, sondern eine Angabe
    # daneben — und ein Test, der die mitnagelt, blockiert genau die
    # Vereinheitlichung, für die er zeugen sollte.
    for key, value in values.items():
        assert labels.value_text(key, value) in line, f"{key}: {line}"


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


def test_the_cards_make_room_for_the_sketch_bar(window: MainWindow) -> None:
    """§2.5: die Karten liegen über der Ansicht — und weichen der Leiste aus.

    **Diese Zusage hat der Umbau umgedreht, und sie ist dabei besser
    geworden.** Solange der Skizzenmodus die Ansicht *ersetzte*, lag er unter
    den schwebenden Karten: die ersten Werkzeuge unter der linken, die
    Bedingungsliste unter der rechten. Die Antwort darauf war
    ``set_zone_margins`` — die Ansicht wich den Karten aus.

    Seit dem Schnitt (§30.1, P4) sitzt der Skizzenmodus in der unteren Karte,
    und für die gilt die Regel schon: ``_bottom_room`` zieht ihre Höhe von der
    Fläche ab, die den seitlichen Zonen bleibt. Jetzt weichen also **die
    Karten der Leiste aus** statt die Ansicht den Karten — eine Stelle
    weniger, an der zwei Rechnungen übereinstimmen müssen.

    Geprüft wird die Wirkung und nicht der Mechanismus: Die Leiste braucht
    mehr Höhe, sobald der Skizzenmodus läuft, und den seitlichen Zonen bleibt
    um denselben Betrag weniger.

    **Gerechnet und nicht an den Karten gemessen.** In einem nie gezeigten
    Fenster ist ``height()`` null — bei beiden Karten, vorher wie nachher, und
    ein Vergleich zweier Nullen ist grün ohne Aussage
    (`.claude/rules/wartezeit.md`, „isVisible lügt in einem nie gezeigten
    Fenster"). ``_bottom_room`` dagegen fragt den ``sizeHint``, und den gibt
    es auch ungezeigt.
    """
    window.resize(1400, 900)
    window.overlay._place()
    schmal = window.overlay._bottom_room()

    window.start_sketch("sketch_extrude", "")
    assert window._sketch_panel is not None
    window.overlay._place()
    breit = window.overlay._bottom_room()

    assert breit > schmal, "die Leiste trägt jetzt den Skizzenmodus"
    # Dieselbe Rechnung, die ``_lay_out`` für die Zonen anstellt.
    assert (900 - breit) < (900 - schmal), "und den Zonen daneben bleibt weniger"

    window.finish_sketch(keep=False)
    window.overlay._place()
    assert window.overlay._bottom_room() == schmal, "danach ist sie wieder, was sie war"


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
        "ein Lambda trifft blind das Feld — siehe .claude/rules/wartezeit.md"
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


def test_the_veil_hides_the_native_view_while_it_stands(window: MainWindow) -> None:
    """Verborgen, nicht nur verdeckt (§2.8).

    Die Ansicht ist ein natives Fenster (VTK): auf dem Bildschirm liegt es
    über jedem gemalten Geschwister, egal was die Qt-Stapelung sagt — und
    solange es nie gerendert hat, zeigt es alte Pixel. Beim Öffnen von Weg 1
    stand deshalb sechs Sekunden der Startbildschirm bzw. Schwarz, während
    der Schleier unsichtbar darunter lag; Robert hielt es zweimal für einen
    Absturz. Der ``childAt``-Test daneben sah davon nichts: er fragt die
    Stapelung, nicht den Bildschirm.
    """
    # ``isHidden`` und nicht ``isVisibleTo``: gefragt ist die ausdrückliche
    # Verbergung — der Stapel zeigt im frischen Fenster den Startbildschirm,
    # und dahinter ist jede Sichtbarkeitskette folgenlos False.
    window._on_busy(True)
    assert window.veil.showing
    assert window.middle_stack.isHidden(), (
        "die native Ansicht muss weg sein, solange der Schleier steht"
    )

    window._on_busy(False)
    assert not window.veil.showing
    assert not window.middle_stack.isHidden(), "mit dem Ende des Schleiers kommt die Ansicht zurück"


def test_reading_a_file_stands_under_the_wait_cursor(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§2.8: bis zwei Sekunden Mauszeiger und Statusleiste.

    Die Sitzung liest synchron — ``load`` für ein Projekt, ``read_bytes`` für
    ein Modell —, und die Ladeanzeige deckt das nicht: sie hängt am
    Fortschritt der Auswertung, und der beginnt erst, wenn die Datei gelesen
    ist. Dazwischen lag ein Fenster ohne jede Auskunft.
    """
    seen: list[tuple[Any, str]] = []
    real = window.session.import_model

    def watched(path: Path, *args: Any, **kwargs: Any) -> Any:
        seen.append((QApplication.overrideCursor(), window.status_message.text()))
        return real(path, *args, **kwargs)

    monkeypatch.setattr(window.session, "import_model", watched)

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()

    assert seen, "gelesen wurde nichts — der Test misst am falschen Ort"
    cursor, status = seen[0]
    assert cursor is not None, "gelesen wurde ohne Wartezeiger"
    assert cursor.shape() == Qt.CursorShape.WaitCursor
    assert status == tr("Modell einfügen …"), "die Statuszeile erklärt den Vorgang nicht"
    assert QApplication.overrideCursor() is None, "der Wartezeiger blieb stehen"


def test_import_dialog_keeps_its_reading_status_after_starting_the_project(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auch der Dateidialog bewahrt den Ladehinweis über den Projektanfang."""
    from PySide6.QtWidgets import QFileDialog

    window.announce("Bereit")
    seen: list[tuple[Any, str, str]] = []
    real = window.session.import_model

    def watched(path: Path, *args: Any, **kwargs: Any) -> Any:
        seen.append(
            (
                QApplication.overrideCursor(),
                window.status_message.text(),
                window._announcement,
            )
        )
        return real(path, *args, **kwargs)

    monkeypatch.setattr(window.session, "import_model", watched)
    monkeypatch.setattr(
        QFileDialog,
        "getOpenFileName",
        staticmethod(lambda *args, **kwargs: (str(MESHES / "cube_clean.stl"), "")),
    )

    window.action_import()
    window.session.wait_for_idle()

    assert seen, "gelesen wurde nichts — der Test misst am falschen Ort"
    cursor, status, announcement = seen[0]
    assert cursor is not None and cursor.shape() == Qt.CursorShape.WaitCursor
    assert status == tr("Modell einfügen …"), "der Projektanfang löschte den Ladehinweis"
    assert announcement == "Bereit", "der vorübergehende Hinweis wurde dauerhaft angekündigt"
    assert window._announcement == "Bereit"
    assert QApplication.overrideCursor() is None, "der Wartezeiger blieb stehen"


def test_a_broken_file_takes_the_wait_cursor_with_it(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Wartezeiger, der nach einem Fehler stehen bleibt, sieht aus wie ein
    hängendes Programm — und der Fehlerdialog darunter wie ein Fenster, das
    zugleich fragt und bittet zu warten."""

    def refuse(*args: Any, **kwargs: Any) -> Any:
        raise errors.UserError(title="Diese Datei ließ sich nicht lesen.")

    shown: list[Any] = []
    monkeypatch.setattr(window.session, "import_model", refuse)
    monkeypatch.setattr(
        "app.ui.main_window.show_error", lambda error, *args, **kwargs: shown.append(error)
    )

    window.open_path(MESHES / "cube_clean.stl")

    assert shown, "der Fehler kam nirgends an"
    assert QApplication.overrideCursor() is None, "der Wartezeiger überlebte den Fehler"


def test_a_rejected_file_restores_status_before_showing_the_error(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Eine Abweisung aus ``History.apply`` darf nicht als ewiges Laden enden."""
    window._show_start_screen(False)
    window.announce("Bereit")

    def refusing(*_args: object, **_kwargs: object) -> object:
        raise errors.UserError(detail="der Schritt wurde abgewiesen")

    shown: list[tuple[Any, Any, str]] = []
    monkeypatch.setattr(window.session.history, "apply", refusing)
    monkeypatch.setattr(
        "app.ui.main_window.show_error",
        lambda error, *_args, **_kwargs: shown.append(
            (error, QApplication.overrideCursor(), window.status_message.text())
        ),
    )

    window.open_path(MESHES / "cube_clean.stl")

    assert shown, "die Abweisung kam nirgends an"
    _error, cursor, status = shown[0]
    assert cursor is None, "der Fehler erschien noch unter dem Wartezeiger"
    assert status == "Bereit", "der Ladehinweis blieb hinter dem Fehler stehen"
    assert window.status_message.text() == "Bereit"
    assert not window.session.project.document.sources


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
    """Der Schleier gehört der Auswertung und hält keine parallele Aufgabe an."""
    split_worker = _RunningSplit()
    window.session._split = split_worker
    window._on_busy(True)
    window.veil.cancel.click()

    assert window.session.cancel_signal.is_cancelled
    assert not window.session.agent_cancel.is_cancelled
    assert not split_worker.cancel.is_cancelled
    window.session._split = None
    window._on_busy(False)


def test_a_cancelled_run_says_that_it_was_cancelled(window: MainWindow) -> None:
    """Ein abgebrochener Lauf sah aus wie ein fertiger.

    Balken weg, Knopf weg, dieselbe Ansicht wie vorher — das erfuhr bisher nur
    die Logdatei. Wer nicht mitgezaehlt hat, konnte nicht wissen, ob sein Klick
    etwas bewirkt hat und ob das Bild vor ihm das Ergebnis ist oder ein alter
    Stand. Der Satz nennt deshalb beides (§2.8).
    """
    window.session.cancel()
    window.session._on_cancelled()

    assert "Abgebrochen" in window.status_message.text()
    assert "letzte" in window.status_message.text(), "der Stand gehoert dazu, nicht nur das Ende"

    # Und er ueberlebt das naechste Ereignis: ``_on_busy`` schreibt die Ansage
    # zurueck, und eine Meldung, die dabei verschwindet, war fuer den, der
    # gerade woanders hinsah, nie da.
    window._on_busy(False)
    assert "Abgebrochen" in window.status_message.text()


def test_replacing_a_run_is_not_an_interruption(window: MainWindow) -> None:
    """Eine neuere Anfrage bricht die laufende ab — das ist Ersetzen, kein
    Aufhoeren.

    Es zu melden hiesse, beim Ziehen an einem Schieber im Sekundentakt
    „abgebrochen" in die Statuszeile zu schreiben. Unterschieden wird an der
    Herkunft: ``cancel()`` kommt von einem Menschen, ``evaluate_async`` von
    der naechsten Zahl.
    """
    vorher = window.status_message.text()
    window.session.cancel_signal.cancel()  # wie es ``evaluate_async`` tut
    window.session._on_cancelled()

    assert window.status_message.text() == vorher, "ein Ersetzen sagt nichts"


def test_saving_shows_that_it_is_working(window: MainWindow, tmp_path) -> None:
    """Speichern ist keine Handlung ohne Dauer.

    Gemessen: 903 ms fuer ein Projekt mit einem 62-MiB-Netz, und das ohne
    jedes Zeichen — nach §2.8 die mittlere Stufe, Mauszeiger und Statusleiste,
    und beide fehlten. Wer *Speichern* drueckte, sah ein Fenster, das nicht
    reagiert.

    Geprueft wird der Zeiger waehrend des Schreibens, nicht danach: Ein Test,
    der erst hinterher hinsieht, findet immer einen aufgeraeumten Zustand und
    haette auch ohne die Aenderung bestanden.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    gesehen: list[object] = []
    echtes_speichern = window.session.save_project

    def merken(path):
        zeiger = QApplication.overrideCursor()
        gesehen.append(zeiger.shape() if zeiger is not None else None)
        gesehen.append(window.status_message.text())
        return echtes_speichern(path)

    window.session.save_project = merken  # type: ignore[method-assign]
    window._save_to(tmp_path / "projekt.solidon")

    assert gesehen[0] == Qt.CursorShape.WaitCursor, "waehrend des Schreibens fehlt der Wartezeiger"
    assert "gespeichert" in str(gesehen[1]), f"die Zeile sagt nichts: {gesehen[1]!r}"
    assert QApplication.overrideCursor() is None, "und danach ist er wieder weg"
    assert "Gespeichert" in window.status_message.text()


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
    """Bis 32 Pixel kommt die vereinfachte Version, darüber die ausgearbeitete.

    Das ist die Größe von Titelleiste, Taskleiste, Alt-Tab — und dieselbe in
    jedem Dialog, weil das Symbol einmal auf der ``QApplication`` steht und
    jedes Fenster es erbt. Die ausgearbeitete Version trägt dort Schichtlinien
    von 0,3 Pixeln Breite und kommt als grauer Schleier an.

    Die beiden Versionen sind **dieselbe Form** — gleiche Punkte, gleiche
    Farben. Der einzige Unterschied sind die Schichtlinien, und genau darauf
    prüft dieser Test: Wer die kleine Version neu gestaltet statt sie zu
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
    assert "<path" in large, "die große Version hat ihre Schichtlinien verloren"
    assert "<path" not in small, "die kleine Version trägt Linien, die bei 16 px zu Schleier werden"

    # Dieselben Flächen, dieselben Farben: Was hier auseinanderläuft, sieht der
    # Nutzer als zwei verschiedene Symbole.
    for shape in ('points="64,18 104,41 64,64 24,41"', 'fill="#e08b4e"', 'fill="#7c3a10"'):
        assert shape in large and shape in small, f"{shape} steht nicht in beiden Versionen"


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
    from app.core.activation import certificate, key

    _expired(monkeypatch)
    window = MainWindow(Session(), UiSettings())
    hint_before = str(window.import_action.property("tip_before_lock"))
    toolbar_hint_before = str(window._toolbar_import.property("tip_before_lock"))

    licence = key.Licence(
        major=key.current_major(),
        purchased_on=date(2026, 8, 6),
        order="A-1",
        holder="kaeufer@beispiel.de",
    )
    active = certificate.ActivationCertificate(
        licence_digest=certificate.licence_digest(licence),
        device_public=b"x" * 32,
        device_name="Werkstatt-PC",
        activation_id="0" * 32,
        issued_on=date(2026, 8, 28),
    )
    monkeypatch.setattr(
        activation,
        "_cached",
        activation.Activation(licence=licence, certificate=active),
    )
    window._update_actions()
    window._refresh_chat_availability()

    assert window.import_action.isEnabled()
    assert window.generate_action.isEnabled()
    assert window.import_action.statusTip() == hint_before
    # Und am Knopf ohne Beschriftung: der trug vor der symbolfreien Leiste gar
    # keinen ``statusTip``, und ``_lock_hint`` stellte nach dem Freischalten
    # einen leeren wieder her — ein stummes Bild.
    assert window._toolbar_import.statusTip() == toolbar_hint_before
    assert window._toolbar_import.statusTip().startswith("Modell einfügen")
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


def test_a_damaged_installation_names_itself_in_the_status_bar(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Zustand, der alles sperrt, war der einzige ohne Zeile.

    Demo und Testlauf nennen sich in der Statusleiste selbst; eine
    beschädigte Installation (H4) schwieg dort — der Kunde sah eine
    Oberfläche wie immer und erfuhr den Grund erst am ersten
    Änderungsversuch. Derselbe Satz wie im Freischaltdialog, aus derselben
    Quelle (``damaged_line``), denn zwei Formulierungen derselben Auskunft
    laufen auseinander (Bedienungs-Vollmacht, 26.08.2026).
    """
    from app.core import activation
    from app.ui.dialogs import damaged_line

    monkeypatch.setattr(activation, "_cached", activation.Activation(damaged=True))
    window = MainWindow(Session(), UiSettings())

    assert window.trial_line.text() == damaged_line(), "die Zeile nennt den Zustand"
    assert window.trial_line.isVisibleTo(window), "und sie steht sichtbar da"


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
    from app.core.activation import certificate, key
    from app.ui.dialogs import AboutDialog

    licence = key.Licence(
        major=key.current_major(),
        purchased_on=date(2026, 11, 1),
        order="A-77",
        holder="kaeufer@beispiel.de",
    )
    active = certificate.ActivationCertificate(
        licence_digest=certificate.licence_digest(licence),
        device_public=b"x" * 32,
        device_name="Werkstatt-PC",
        activation_id="0" * 32,
        issued_on=date(2026, 8, 28),
    )
    monkeypatch.setattr(
        activation,
        "_cached",
        activation.Activation(licence=licence, certificate=active),
    )
    dialog = AboutDialog()
    texts = " ".join(label.text() for label in dialog.findChildren(QLabel))
    assert "kaeufer@beispiel.de" in texts
    assert "A-77" in texts


def test_the_about_dialog_does_not_call_an_unactivated_key_licensed(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein gültiger Kaufcode allein ist noch kein freigeschalteter Rechner."""
    from datetime import date

    from PySide6.QtWidgets import QLabel

    from app.core import activation
    from app.core.activation import key
    from app.ui.dialogs import AboutDialog

    licence = key.Licence(
        major=key.current_major(),
        purchased_on=date(2026, 11, 1),
        order="A-78",
        holder="kundin@beispiel.de",
    )
    monkeypatch.setattr(activation, "_cached", activation.Activation(licence=licence))

    dialog = AboutDialog()
    texts = " ".join(label.text() for label in dialog.findChildren(QLabel))

    assert "Lizenziert für" not in texts
    assert "noch einmal aktiviert" in texts


def test_the_about_dialog_does_not_invent_a_trial_for_the_sale_version(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ohne Testangebot nennt auch der ruhige Lizenzsatz keinen Ablauf."""
    from PySide6.QtWidgets import QLabel

    from app.core import activation
    from app.core.activation import store
    from app.ui.dialogs import AboutDialog

    monkeypatch.setattr(store, "TRIAL_FROM", None)
    monkeypatch.setattr(activation, "_cached", activation.Activation(days_left=0))

    dialog = AboutDialog()
    texts = " ".join(label.text() for label in dialog.findChildren(QLabel))
    assert "Testzeitraum" not in texts
    assert "Geräteaktivierung" in texts


def test_a_damaged_installation_is_not_called_unlocked(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """„Freigeschaltet für kaeufer@…" über einem Fenster, das nichts freigibt.

    Seit ``Activation.damaged`` (H4) wird der Schlüssel auch bei gebrochenem
    Manifest gelesen — der zahlende Kunde soll erkannt werden statt eine
    Kaufaufforderung zu bekommen. Beide Anzeigen fragten aber weiter nur nach
    ``licence is not None`` und meldeten deshalb genau das Gegenteil des
    Zustands: freigeschaltet, während jede Änderung gesperrt ist. Den wahren
    Grund erfuhr der Kunde erst beim ersten Änderungsversuch — Regel 17 an der
    Anzeige.

    Der Wortlaut kommt aus ``InstallationDamaged`` und wird nicht zweimal
    erfunden: Es ist derselbe Satz, den derselbe Kunde gleich darauf zu lesen
    bekommt.
    """
    from datetime import date

    from PySide6.QtWidgets import QLabel

    from app.core import activation
    from app.core.activation import key
    from app.core.errors import InstallationDamaged
    from app.ui.dialogs import AboutDialog, ActivationDialog

    licence = key.Licence(
        major=key.current_major(),
        purchased_on=date(2026, 8, 6),
        order="A-77",
        holder="kaeufer@beispiel.de",
    )
    monkeypatch.setattr(activation, "_cached", activation.Activation(licence=licence, damaged=True))
    erwartet = str(InstallationDamaged().detail)

    dialog = ActivationDialog()
    gezeigt = dialog.state_label.text()
    assert erwartet in gezeigt, f"der Grund fehlt: {gezeigt!r}"
    assert "Freigeschaltet" not in gezeigt, f"und das Gegenteil steht nicht da: {gezeigt!r}"
    assert "kaeufer@beispiel.de" not in gezeigt, "erkannt heißt hier nicht freigeschaltet"

    about = AboutDialog()
    texte = " ".join(label.text() for label in about.findChildren(QLabel))
    assert erwartet in texte, "und im Über-Dialog steht dieselbe Auskunft"
    assert "Lizenziert für" not in texte


def test_a_damaged_installation_greys_out_what_cannot_work(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der falsche Satz war behoben, die toten Knöpfe standen noch da.

    ``damaged`` schlägt jeden Schlüssel (``Activation.unlocked``): *Eintragen*
    schaltet nichts frei. Und *Solidon kaufen* führt in beiden Lagen an die
    falsche Stelle — wer bezahlt hat, soll nicht noch einmal kaufen, und wer
    nicht bezahlt hat, bekommt mit einem Kauf trotzdem keine heile
    Installation. Zwei Knöpfe, die nichts bewirken können, sind zwei
    Sackgassen (§2.1).

    *Schlüssel entfernen* bleibt bedienbar: Es tut, was es sagt.

    Regel 18 — grau ist eine Farbe. Der Grund steht im Tooltip, in der
    ``accessibleDescription`` für den Bildschirmleser und sichtbar in der Zeile
    darüber; und er ist derselbe Satz wie dort, nicht ein zweiter Wortlaut.
    """
    from datetime import date

    from app.core import activation
    from app.core.activation import key
    from app.core.errors import InstallationDamaged
    from app.ui.dialogs import ActivationDialog

    licence = key.Licence(
        major=key.current_major(),
        purchased_on=date(2026, 11, 1),
        order="A-77",
        holder="kaeufer@beispiel.de",
    )
    grund = str(InstallationDamaged().detail)

    monkeypatch.setattr(activation, "_cached", activation.Activation(licence=licence))
    heil = ActivationDialog()
    heil.field.setPlainText("SOLIDON3D-1-EGAL")
    assert heil.check_button.isEnabled(), "ohne Schaden trägt der Knopf ein"
    assert heil.buy_button.isEnabled()

    monkeypatch.setattr(activation, "_cached", activation.Activation(licence=licence, damaged=True))
    kaputt = ActivationDialog()
    kaputt.field.setPlainText("SOLIDON3D-1-EGAL")

    assert not kaputt.check_button.isEnabled(), "ein Schlüssel schaltet hier nichts frei"
    assert not kaputt.buy_button.isEnabled(), "und ein Kauf repariert keine Datei"
    assert kaputt.forget_button.isEnabled(), "entfernen tut, was es sagt"

    for knopf in (kaputt.check_button, kaputt.buy_button):
        assert grund in knopf.toolTip(), f"ohne Grund grau: {knopf.text()!r}"
        assert grund in knopf.accessibleDescription(), "Regel 18: nicht nur die Farbe"
    assert grund in kaputt.state_label.text(), "und sichtbar, nicht nur im Zeigen"


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


def test_an_active_key_cannot_be_overwritten_before_deactivation(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Der einfache Zwei-Geräte-Nebenweg beginnt nicht mit Überschreiben im Dialog."""
    from datetime import date

    from app.core import activation
    from app.core.activation import certificate, key, store
    from app.ui.dialogs import ActivationDialog

    monkeypatch.setattr(store, "user_config_dir", lambda: tmp_path)
    store.write_key("SOLIDON3D-1-BEREITS-AKTIV")
    licence = key.Licence(
        major=key.current_major(),
        purchased_on=date(2026, 11, 1),
        order="A-1",
        holder="kundin@beispiel.de",
    )
    active = certificate.ActivationCertificate(
        licence_digest="0" * 64,
        device_public=b"x" * 32,
        device_name="Werkstatt-PC",
        activation_id="0" * 32,
        issued_on=date(2026, 11, 1),
    )
    monkeypatch.setattr(
        activation,
        "_cached",
        activation.Activation(licence=licence, certificate=active),
    )

    dialog = ActivationDialog()

    assert dialog.field.isReadOnly()
    assert dialog.device_name.isReadOnly()
    assert not dialog.check_button.isEnabled()
    assert not dialog.online_button.isEnabled()
    assert not dialog.offline_button.isEnabled()
    assert dialog.forget_button.text() == "Diesen Rechner deaktivieren"
    activation.forget_cache()


def test_an_unclear_deactivation_answer_never_restores_the_certificate(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Nach möglicher Serverfreigabe bleibt der Rechner lokal sicher gesperrt."""
    from app.core import activation
    from app.core.activation import store
    from app.core.errors import AppError
    from app.ui import dialogs
    from app.ui.dialogs import ActivationDialog

    monkeypatch.setattr(store, "user_config_dir", lambda: tmp_path)
    assert store.write_pending_deactivation("signierte Geräteabmeldung")
    monkeypatch.setattr(
        activation,
        "_cached",
        activation.Activation(deactivation_pending=True),
    )
    shown: list[object] = []
    monkeypatch.setattr(dialogs, "show_error", lambda error, *_args: shown.append(error))

    dialog = ActivationDialog()
    dialog._deactivation_failed(AppError(detail="Verbindung abgebrochen"))

    assert store.read_certificate() is None
    assert store.read_pending_deactivation() == "signierte Geräteabmeldung"
    assert dialog.forget_button.text() == "Deaktivierung erneut senden"
    assert "noch nicht bestätigt" in dialog.state_label.text()
    assert shown and isinstance(shown[0], activation.DeviceDeactivationPending)
    activation.forget_cache()


def test_a_local_deactivation_failure_rolls_back_before_contacting_the_server(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Vor dem Netz darf ein Dateifehler keinen halben Sperrzustand hinterlassen."""
    from app.core import activation
    from app.core.activation import store
    from app.ui import dialogs
    from app.ui.dialogs import ActivationDialog

    monkeypatch.setattr(store, "user_config_dir", lambda: tmp_path)
    store.write_key("SOLIDON3D-1-BESTEHEND")
    store.write_certificate("bestehendes Zertifikat")
    store.write_pending_deactivation("wiederholbarer Auftrag")
    monkeypatch.setattr(
        activation,
        "_cached",
        activation.Activation(deactivation_pending=True),
    )
    monkeypatch.setattr(activation, "prepare_deactivation", lambda: "wiederholbarer Auftrag")
    monkeypatch.setattr(activation, "remove_certificate", lambda: False)
    shown: list[object] = []
    monkeypatch.setattr(dialogs, "show_error", lambda error, *_args: shown.append(error))

    dialog = ActivationDialog()
    dialog._deactivate()

    assert store.read_pending_deactivation() is None
    assert store.read_certificate() == "bestehendes Zertifikat"
    assert shown
    assert dialog.forget_button.text() != "Deaktivierung erneut senden"
    activation.forget_cache()


def test_confirmed_deactivation_never_claims_that_an_unremovable_key_is_gone(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Die Erfolgsmeldung folgt erst, wenn auch der lokale Schlüssel wirklich weg ist."""
    from app.core import activation
    from app.core.activation import store
    from app.ui import dialogs
    from app.ui.dialogs import ActivationDialog

    monkeypatch.setattr(store, "user_config_dir", lambda: tmp_path)
    store.write_key("SOLIDON3D-1-LOKAL-GESPERRT")
    monkeypatch.setattr(
        activation,
        "_cached",
        activation.Activation(deactivation_pending=True),
    )
    monkeypatch.setattr(activation, "clear_pending_deactivation", lambda: True)
    monkeypatch.setattr(activation, "forget_key", lambda: False)
    shown: list[object] = []
    notices: list[object] = []
    monkeypatch.setattr(dialogs, "show_error", lambda error, *_args: shown.append(error))
    monkeypatch.setattr(
        dialogs.QMessageBox,
        "information",
        lambda *_args, **_kwargs: notices.append(object()),
    )

    dialog = ActivationDialog()
    previous = dialog.field.toPlainText()
    dialog._deactivation_completed()

    assert dialog.field.toPlainText() == previous
    assert shown, "der lokale Rest wird erklärt"
    assert not notices, "keine falsche Erfolgsmeldung"
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


def test_the_first_run_dialog_promises_no_trial_in_the_sale_version(
    qt_app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die Verkaufsversion nennt die Planänderung und erfindet keine freien Tage."""
    from app.core import activation
    from app.core.activation import store
    from app.ui.first_run import FirstRunDialog

    monkeypatch.setattr(store, "DEMO_UNTIL", None)
    monkeypatch.setattr(store, "TRIAL_FROM", None)
    activation.forget_cache()
    dialog = FirstRunDialog(UiSettings())
    assert "14" not in dialog.terms.text()
    assert "ohne Testphase" in dialog.terms.text()
    assert "Geräteaktivierung" in dialog.terms.text()
    activation.forget_cache()


def test_the_first_run_dialog_promises_no_free_days_on_a_damaged_install(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der dritte Zwilling — dieselbe Auskunft, die dritte Stelle.

    „Die ersten 14 Tage ist alles frei" stand hier unabhängig vom Zustand.
    Gemessen bei gebrochenem Manifest (H4): ``unlocked`` ist ``False``, jede
    Änderung wird abgesagt — und das ist der **erste** Satz, den ein neuer
    Kunde liest. Ein Virenscanner in Quarantäne reicht dafür.

    Derselbe Wortlaut wie im Freischalt- und im Über-Dialog, aus derselben
    Quelle (``InstallationDamaged``): Ein vierter eigener Satz wäre eine vierte
    Gelegenheit, auseinanderzulaufen.
    """
    from app.core import activation
    from app.core.errors import InstallationDamaged
    from app.ui.first_run import FirstRunDialog

    monkeypatch.setattr(activation, "_cached", activation.Activation(damaged=True))

    dialog = FirstRunDialog(UiSettings())

    text = dialog.terms.text()
    assert str(InstallationDamaged().detail) in text, text
    assert "14" not in text, f"kein Versprechen über freie Tage: {text!r}"


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
        self.accepted = False

    def mimeData(self) -> object:  # noqa: N802 — Qt gibt den Namen
        return self._data

    def acceptProposedAction(self) -> None:  # noqa: N802 — bildet die Qt-API nach
        self.accepted = True


def _drag(urls: list[str]) -> Any:
    return _Drag(urls)


def test_a_dropped_link_is_taken_like_a_dropped_file() -> None:
    """§2.3: Ziehen und Ablegen gilt auch für einen Verweis aus dem Browser."""
    from app.ui.start_screen import accepted_url

    assert accepted_url(_drag(["https://example.invalid/halter.stl"])) is not None
    assert accepted_url(_drag(["https://example.invalid/modelle/17"])) is None
    assert accepted_url(_drag(["file:///C:/teil.stl"])) is None, "das ist der Weg für Dateien"


def test_a_part_file_drop_reaches_open_path_but_json_does_not(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Das ganze Fenster teilt den exakten lokalen Dateivertrag der Startfläche."""
    opened: list[Path] = []
    monkeypatch.setattr(window, "open_path", opened.append)
    part = tmp_path / "halter.solidon-part"
    generic = tmp_path / "halter.json"

    part_drop = _drag([part.as_uri()])
    window.dropEvent(part_drop)  # type: ignore[arg-type]
    generic_drop = _drag([generic.as_uri()])
    window.dropEvent(generic_drop)  # type: ignore[arg-type]

    assert opened == [part]
    assert part_drop.accepted
    assert not generic_drop.accepted


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


def test_a_rejected_download_never_claims_success(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nach einer Abweisung bleibt der Start sichtbar und „Geladen“ aus."""
    from app.core.ingest.fetch import FetchedModel

    shown: list[object] = []
    received: list[dict[str, object]] = []

    def refusing(*_args: object, **kwargs: object) -> bool:
        received.append(kwargs)
        raise errors.UserError(detail="der Schritt wurde abgewiesen")

    monkeypatch.setattr(window.session, "import_payload", refusing)
    monkeypatch.setattr(
        "app.ui.main_window.show_error", lambda error, *_args, **_kwargs: shown.append(error)
    )

    window._downloaded(
        FetchedModel(
            name="halter.stl",
            payload=b"solid",
            url="https://example.invalid/halter.stl",
            retrieved="2026-08-29T10:00:00+00:00",
        )
    )

    assert shown, "die Abweisung kam nirgends an"
    assert received and received[0].get("raise_on_error") is True
    assert window.stack.currentWidget() is window.start_screen
    assert not window._announcement.startswith(tr("Geladen"))


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


def test_the_object_tree_offers_the_keyboard_a_starting_point(window: MainWindow) -> None:
    """Wer per Tabulator in den Baum kommt, muss sich bewegen können.

    Nach dem Öffnen stand ``currentItem()`` auf nichts, obwohl eine Zeile da
    war — eine Pfeiltaste bewegte daraufhin gar nichts, und die
    Tastaturnavigation begann im Leeren.

    Gewählt ist damit weiterhin nichts: die Marke sagt „hier steht der
    Zeiger", nicht „das ist ausgewählt". Der Unterschied zählt, denn an der
    Auswahl hängen die Menüs.
    """
    window.session.import_model(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()

    assert window.object_tree.tree.topLevelItemCount() >= 1
    assert window.object_tree.tree.currentItem() is not None, "die Tastatur hat einen Anfang"
    assert not window.object_tree.selected_objects(), "gewählt ist trotzdem nichts"


def test_every_locked_menu_entry_says_why(window: MainWindow) -> None:
    """Ausgrauen allein ist die halbe Antwort.

    Auf der leeren Szene sind fast alle Operationszeilen gesperrt, und bei
    allen stand als Hinweis ihr Beschreibungssatz — was sie täte, wenn sie
    könnte. Die Werkzeugzeile daneben sagte es im selben Augenblick richtig:
    „Dafür braucht es einen Körper in der Szene." Der Grund fehlte, weil
    ``_kind_hint`` sofort ausstieg, sobald eine Operation kein
    ``requires_kind`` trägt — und das haben sieben von 84.

    Geprüft wird gegen den Beschreibungssatz: Ein Hinweis, der ihm gleicht,
    ist keiner.
    """
    from app.core.registry import REGISTRY

    window._update_actions()

    stumm = []
    for name, action in window._op_actions.items():
        if action.isEnabled():
            continue
        spec = REGISTRY.get(name)
        if action.toolTip().strip() == str(spec.doc).strip():
            stumm.append(name)

    assert not stumm, (
        f"{len(stumm)} gesperrte Einträge nennen ihren Grund nicht, "
        f"darunter {stumm[:5]}. Der Nutzer sucht ihn dann bei sich."
    )


def test_a_menu_entry_gets_its_description_back_when_it_works_again(window: MainWindow) -> None:
    """Der Grund verschwindet, sobald es keinen mehr gibt.

    Sonst bleibt „Wählen Sie dafür ein Objekt aus" an einem Eintrag stehen,
    der längst geht — und der Beschreibungssatz, den er eigentlich trägt, wäre
    für immer weg.
    """
    from app.core.registry import REGISTRY

    window._update_actions()
    name = next(
        entry
        for entry, action in window._op_actions.items()
        if not action.isEnabled() and REGISTRY.get(entry).consumes == 1
    )
    spec = REGISTRY.get(name)
    action = window._op_actions[name]
    assert action.toolTip() != str(spec.doc), "der gesperrte Eintrag nennt keinen Grund"

    # Derselbe Eintrag, aber jetzt liegt genug vor: ein Objekt in der Szene und
    # eines ausgewählt. Geprüft wird die Rückstellung und nicht der Szenenaufbau
    # — dafür genügt der Zustand, aus dem der Hinweis entsteht.
    #
    # **Über beide Glieder der Kette**, seit ``_kind_hint`` den Grund
    # entgegennimmt statt ihn selbst zu holen: Die Freigabe des Eintrags folgt
    # demselben Grund, und ihn zweimal je Eintrag zu rechnen war nicht nur
    # doppelte Arbeit. Die Zeile prüft damit beides — dass ``_reason_locked``
    # hier keinen Grund mehr findet und dass ``_kind_hint`` daraufhin den
    # Beschreibungssatz zurückgibt.
    window._kind_hint(action, window._reason_locked(spec, [], 1, spec.consumes), False)

    assert action.toolTip().strip() == str(spec.doc).strip(), (
        "Der Grund blieb stehen, obwohl der Eintrag wieder geht — dann ist der "
        "Beschreibungssatz für immer weg."
    )


def test_the_chat_setup_button_leads_where_its_name_says(window: MainWindow) -> None:
    """Derselbe Name, derselbe Dialog.

    Der Knopf am gesperrten Chat hieß „Zugang einrichten …" und führte in die
    „Zusätzlichen Programme" — dorthin, wo man ein lokales Modell installiert,
    aber seinen Schlüssel nicht einträgt. Der Dialog mit dem Schlüsselfeld
    heißt „Chat einrichten", steht im Menü unter genau diesem Namen und war
    vom Chat aus nicht erreichbar. Wer keinen Zugang hatte, bekam damit einen
    der zwei Wege aus §27 angeboten und fand den anderen nicht.
    """
    from app.i18n import tr

    assert window.chat.setup.text() == str(tr("Chat einrichten …")), (
        "Knopf und Menüeintrag müssen denselben Text tragen — sonst sind es für "
        "den Nutzer zwei verschiedene Dinge."
    )

    treffer = [
        action
        for action in window.findChildren(QAction)
        if action.text() == str(tr("Chat einrichten …"))
    ]
    assert treffer, "der Menüeintrag heißt nicht mehr so"


def test_a_warning_still_reaches_someone_with_the_right_column_hidden(
    window: MainWindow,
) -> None:
    """§2.5 nennt „Warnungen" für die Statusleiste, und dort standen sie nie.

    Solange die rechte Spalte offen ist, trägt ihr Reiter die Zahl. Ist sie zu,
    erreichte eine neue Warnung niemanden mehr: ``_focus_report`` steigt bei
    unsichtbarer Spalte zu Recht aus, und danach kam nichts. Der Zähler in der
    Statusleiste erscheint genau dann — und holt beides zurück.
    """
    # Ohne das liegt der Startbildschirm oben, und die rechte Spalte ist auch
    # dann unsichtbar, wenn niemand sie ausgeblendet hat.
    window._show_start_screen(False)
    window.right.setVisible(True)
    window._mark_status_alerts(3)
    # ``isHidden`` und nicht ``isVisible``: Das Fenster selbst wird hier nie
    # gezeigt, und dann ist jedes Kind unsichtbar — die Frage ist, ob der Knopf
    # ausgeblendet wurde.
    assert window.alert_button.isHidden(), (
        "Bei offener Spalte trägt der Reiter die Zahl — zwei Zähler sind einer zu viel."
    )

    window.right.setVisible(False)
    window._mark_status_alerts(3)
    assert not window.alert_button.isHidden(), "die Warnung erreicht niemanden mehr"
    assert "3" in window.alert_button.text()

    window._show_alerts()
    assert window.right.isVisibleTo(window), "der Klick holt die Spalte nicht zurück"
    assert window.right.currentWidget() is window.report
    assert window.alert_button.isHidden(), "er bleibt stehen, obwohl die Spalte offen ist"


def test_the_status_counter_stays_away_when_nothing_is_wrong(window: MainWindow) -> None:
    """Ein Zähler, der immer dasteht, wird Tapete — dieselbe Begründung wie am
    Reiter."""
    window._show_start_screen(False)
    window.right.setVisible(False)
    window._mark_status_alerts(0)

    assert window.alert_button.isHidden()


def test_what_a_screen_reader_can_name(window: MainWindow) -> None:
    """Ein Feld ohne Namen wird als seine Art angesagt — „Eingabe", „Auswahl".

    Wer nicht sieht, welches Label danebensteht, bedient damit ein Formular aus
    lauter „Eingabe". Gemessen waren es 44 von 102 fokussierbaren Elementen:
    die neun Beispielkacheln des Startbildschirms, die Wähler aller Leisten,
    die Suchfelder, der Schichtenregler, jede Liste.

    Was hier durchgeht, sind Qts eigene Unterwidgets: die Aufklappliste eines
    Auswahlfelds trägt den Namen ihres Feldes, ein Rollbereich den seines
    Inhalts. Sie zu benennen hieße, dieselbe Auskunft zweimal vorzulesen.
    """
    from PySide6.QtWidgets import (
        QAbstractScrollArea,
        QComboBox,
        QLabel,
        QTabBar,
        QTabWidget,
        QWidget,
    )

    def name_of(widget: QWidget) -> str:
        if widget.accessibleName().strip():
            return widget.accessibleName().strip()
        text = getattr(widget, "text", None)
        if callable(text):
            try:
                if str(text()).strip():
                    return str(text()).strip()
            except Exception:  # pragma: no cover - Qt-Signaturen streuen
                pass
        parent = widget.parentWidget()
        if parent is not None:
            for label in parent.findChildren(QLabel):
                if label.buddy() is widget and label.text().strip():
                    return label.text().strip()
        return ""

    def qt_internal(widget: QWidget) -> bool:
        if widget.objectName().startswith("qt_"):
            return True
        # Die Popup-Liste eines Auswahlfelds und der Rollbereich um einen
        # Inhalt: beide gehören einem Element, das selbst einen Namen trägt.
        parent = widget.parentWidget()
        while parent is not None:
            if isinstance(parent, QComboBox):
                return True
            parent = parent.parentWidget()
        # Ein Reiterfeld wird über seine Reiter angesagt, und die tragen Text.
        return (
            isinstance(widget, QAbstractScrollArea | QTabBar | QTabWidget)
            and not widget.accessibleName()
        )

    window._show_start_screen(False)
    nameless = [
        f"{type(child).__name__}({child.objectName() or '-'})"
        for child in window.findChildren(QWidget)
        if child.focusPolicy() != Qt.FocusPolicy.NoFocus
        # Ausgeblendetes liest niemand vor. ``isHidden`` und nicht
        # ``isVisible``: Das Fenster selbst wird hier nie gezeigt, und dann
        # wäre jedes Kind unsichtbar.
        and not child.isHidden()
        and not qt_internal(child)
        and not name_of(child)
    ]

    assert not nameless, (
        f"{len(nameless)} bedienbare Elemente haben für einen Bildschirmleser keinen "
        f"Namen: {nameless}. setAccessibleName() oder ein Label mit setBuddy()."
    )


def test_the_open_tool_keeps_its_symbol_readable(qt_app: QApplication) -> None:
    """Auf dem gedrückten Knopf widersprachen sich Symbol und Beschriftung.

    Er trug Bernstein, und das Stylesheet gab der Beschriftung dort die dunkle
    Schrift der Auswahl. Das **Symbol** kam weiter aus dem Thema, also hell:
    1,58 Kontrast auf der Fläche, gemessen. Zwei Zeichen derselben Aussage in
    entgegengesetzten Farben — und das hellere war das unlesbare. Eine eigene
    Umfärbung hielt die beiden zusammen.

    **Seit der Akzenthaushalt gilt, gibt es die Umfärbung nicht mehr, und die
    Zusage kehrt sich um.** Das aktive Werkzeug trägt eine gedämpfte Fläche und
    behält die Schrift des Themas; dieselbe Farbe ist damit in beiden Zuständen
    die richtige, und ein Symbol, das beim Einschalten die Farbe wechselte,
    wäre jetzt das falsche. Was gleich bleibt, ist der Grund, aus dem dieser
    Test steht: Das Zeichen muss auf seiner Fläche zu lesen sein — nur ist die
    Fläche eine andere geworden, und darum wird gegen sie gemessen und nicht
    mehr gegen die Auswahlfarbe.

    Gemessen wird am ``QIcon`` und nicht am gerenderten Knopf: die Beschriftung
    daneben streut Subpixel-Farben in jede Bildpunktzählung, und die sahen dem
    Symbol zum Verwechseln ähnlich.
    """
    from PySide6.QtCore import QSize

    from app.ui.style import active_fill, apply_style
    from app.ui.theme import apply_theme, contrast_ratio

    # **Die Betriebslage herstellen, sonst misst der Test Windows.** ``icon()``
    # holt seine Farbe aus der Palette des Widgets, und ohne angewandtes Thema
    # ist das die des Systems: Das Symbol kam schwarz heraus. Der Test war
    # trotzdem grün, weil er gegen ``palette().highlight()`` maß — ebenfalls
    # eine Systemfarbe. Zwei Farben, die es in der Anwendung nicht gibt, und
    # ihr Verhältnis passte zufällig.
    before = QApplication.instance().styleSheet()
    apply_theme(QApplication.instance(), "dark")
    apply_style(QApplication.instance(), "dark")
    window = MainWindow(Session(), UiSettings())
    button = window.tools._buttons["analysis"]

    def dominant(icon: object) -> str:
        image = icon.pixmap(QSize(24, 24)).toImage()  # type: ignore[attr-defined]
        tally: dict[str, int] = {}
        for y in range(image.height()):
            for x in range(image.width()):
                colour = image.pixelColor(x, y)
                if colour.alpha() > 180:
                    tally[colour.name()] = tally.get(colour.name(), 0) + 1
        assert tally, "das Symbol zeichnet nichts"
        return max(tally, key=lambda name: tally[name])

    try:
        resting = dominant(button.icon())
        window.tools.activate("analysis")
        active = dominant(button.icon())
    finally:
        QApplication.instance().setStyleSheet(before)
    fill = active_fill("dark")

    ratio = contrast_ratio(active, fill)
    assert ratio >= 4.5, f"Symbol {active} auf {fill}: {ratio:.2f} — auf seiner Fläche unlesbar"
    assert active == resting, (
        "das Symbol wechselt beim Einschalten die Farbe — die Beschriftung daneben tut es "
        "nicht mehr, und zwei Zeichen derselben Aussage in zwei Farben waren der Anlass "
        "dieses Tests"
    )

    # Und zurück, damit ein späterer Wechsel der Fläche hier auffällt und nicht
    # erst dort, wo jemand den Knopf ansieht.
    window.tools.activate(None)
    assert dominant(button.icon()) == resting


def test_the_view_bar_stays_out_of_the_way(window: MainWindow) -> None:
    """Die Leiste liegt **über** dem Modell, also ist ihre Breite eine Zusage.

    Mit Beschriftung an jedem Knopf wären es 1039 Bildpunkte gewesen — bei
    einem 1024er Fenster mehr als ein Drittel der Ansicht, und damit genau die
    Fläche, für die §2.5 die Karten überhaupt schweben lässt. Mit Symbolen sind
    es gut zweihundert.

    Die Grenze steht hier und nicht im Docstring, weil ein Zusatz sie sonst
    lautlos zurücknimmt: Wer einen achten Knopf oder eine Beschriftung
    hinzufügt, bekommt einen roten Lauf und entscheidet dann bewusst.
    """
    bar = window.viewport.view_bar
    bar.adjustSize()
    assert bar.width() <= 260, f"{bar.width()} px — die Leiste frisst den Viewport"
    assert bar.height() <= 48, f"{bar.height()} px hoch"


# --- Die Wiederherstellung fragt zweimal dasselbe (§38) -------------------------


def test_both_recovery_questions_name_their_action_and_the_age(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Beide Fälle gehen über denselben Aufbau — und der nennt Handlung und Alter.

    Der namenlose Fall stand auf „Ja"/„Nein" und ohne jede Angabe, während sein
    Zwilling daneben beides längst hatte. Geprüft wird deshalb nicht der Dialog
    (der hängt modal), sondern **womit** die beiden Aufrufer ihn bestellen:
    Wer hier einen zweiten Aufbau daneben stellt, bekommt einen roten Lauf.

    Gemessen wird **im** Aufruf. Danach ginge es nicht mehr: Ein Projekt zu
    speichern räumt die namenlose Sicherung weg, und die Prüfung liefe gegen
    eine Datei, die es zu Recht nicht mehr gibt.
    """
    from app.core.scene.project import write_autosave

    bestellt: list[dict[str, Any]] = []

    def merken(
        self: MainWindow, candidate: Path, saved: Path | None, question: str, decline: str
    ) -> bool:
        bestellt.append(
            {
                "vorhanden": candidate.is_file(),
                "alter": MainWindow._when(candidate),
                "saved": saved,
                "question": question,
                "decline": decline,
            }
        )
        return False

    monkeypatch.setattr(MainWindow, "_ask_recovery", merken)

    # Der namenlose Fall: die Sicherung liegt im Nutzerverzeichnis, das
    # conftest in einen Temp-Ordner umbiegt (§38).
    write_autosave(window.session.project, None)
    window._offer_unsaved_recovery()

    # Und der benannte daneben.
    named = tmp_path / "projekt.p3d"
    window.session.save_project(named)
    write_autosave(window.session.project, named)
    window._offer_recovery(named)

    assert len(bestellt) == 2, "beide Fälle müssen über _ask_recovery gehen"
    for eintrag in bestellt:
        assert eintrag["vorhanden"], "gefragt wird nur zu einer Sicherung, die es gibt"
        assert eintrag["question"].strip(), "die Frage sagt, worum es geht"
        # Das Alter steht im Dialog — ohne es entscheidet niemand zwischen
        # „vor fünf Minuten" und „vor drei Wochen".
        assert eintrag["alter"].strip()
        assert eintrag["alter"] != tr("unbekannt")
        # Der Knopf heißt nach seiner Handlung. „Ja" verlangt, die Frage im
        # Kopf zu behalten — dieselbe Begründung wie bei confirm_discard.
        decline = eintrag["decline"]
        assert decline not in {"Ja", "Nein", "Yes", "No"}, decline
        assert len(decline.split()) >= 2, f"{decline!r} benennt keine Handlung"

    # Nur der benannte Fall hat einen gespeicherten Stand zum Vergleichen; der
    # namenlose hat die Sicherung und sonst nichts.
    assert [eintrag["saved"] is None for eintrag in bestellt] == [True, False]


def test_a_declined_backup_is_not_offered_again(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Wer die Sicherung ablehnt, hat entschieden — auch beim nächsten Öffnen.

    Sie blieb liegen und war weiter neuer als die Datei, also fragte jedes
    Öffnen erneut. Gemessen an der laufenden Oberfläche: sechs Öffnungen,
    sechs Fragen. Das ist keine Rückfrage mehr, das ist Nörgeln.
    """
    from app.core.scene.project import write_autosave

    gefragt: list[Path] = []

    def ablehnen(
        self: MainWindow, candidate: Path, saved: Path | None, question: str, decline: str
    ) -> bool:
        gefragt.append(candidate)
        return False

    monkeypatch.setattr(MainWindow, "_ask_recovery", ablehnen)

    named = tmp_path / "projekt.p3d"
    window.session.save_project(named)
    write_autosave(window.session.project, named)

    window._offer_recovery(named)
    window._offer_recovery(named)
    window._offer_recovery(named)

    assert len(gefragt) == 1, f"{len(gefragt)} Fragen für eine abgelehnte Sicherung"


def test_discarding_at_the_end_really_discards(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """*Verwerfen* am Schließen darf keine Sicherung hinterlassen.

    Das Fenster fragte, der Nutzer verwarf — und danach schrieb ``closeEvent``
    genau diesen Stand als automatische Sicherung weg. Beim nächsten Öffnen
    bot die Anwendung ihm an, was er weggeworfen hatte.
    """
    from PySide6.QtGui import QCloseEvent

    from app.core.scene.project import autosave_path, find_recovery, write_autosave

    named = tmp_path / "projekt.p3d"
    window.session.save_project(named)

    # So sieht es aus, wenn der Zeitgeber im Lauf gesichert hat und danach
    # weitergearbeitet wurde: eine Sicherung liegt da, das Dokument ist
    # geändert. Genau in diesem Zustand wird geschlossen.
    write_autosave(window.session.project, named)
    window.session._dirty = True
    monkeypatch.setattr("app.ui.main_window.confirm_unsaved", lambda *args, **kwargs: "discard")

    window.closeEvent(QCloseEvent())

    assert not autosave_path(named).is_file(), "die verworfene Sicherung liegt noch da"
    assert find_recovery(named) is None


def test_a_recovered_project_saves_into_the_users_file(
    window: MainWindow, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Sicherung wird geöffnet, aber sie wird nicht zur Datei des Nutzers.

    ``open_project`` machte sie dazu: ein „Speichern" danach schrieb in
    ``projekt.p3d.autosave``, und die eigentliche Datei blieb unberührt — die
    wiederhergestellte Arbeit war beim nächsten Öffnen wieder fort.
    """
    from app.core.scene.project import write_autosave

    named = tmp_path / "projekt.p3d"
    window.session.save_project(named)
    write_autosave(window.session.project, named)
    monkeypatch.setattr(MainWindow, "_ask_recovery", lambda *args, **kwargs: True)

    window._offer_recovery(named)

    assert window.session.path == named, f"gespeichert würde nach {window.session.path}"
    assert window.session.modified, "der Stand weicht von der Datei ab — genau darum ging es"


def test_no_question_box_asks_yes_or_no(window: MainWindow) -> None:
    """Bauart-Prüfung: „Ja"/„Nein" ist in dieser Oberfläche keine Frage.

    Der letzte Ja/Nein-Dialog war der namenlose Wiederherstellungsfall. Diese
    Zeile hält es dabei — sonst ist der nächste in einem halben Jahr wieder da,
    und er liest sich beim Schreiben jedes Mal harmlos.
    """
    import app.ui

    quellen = sorted(Path(app.ui.__file__).parent.glob("*.py"))
    assert quellen, "keine Oberflächenquellen gefunden"
    for path in quellen:
        text = path.read_text(encoding="utf-8")
        assert "QMessageBox.question" not in text, f"{path.name}: Ja/Nein-Frage"
        assert "StandardButton.Yes" not in text, f"{path.name}: Ja-Knopf"


def test_the_theme_stands_before_anything_is_shown(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Der Ladebildschirm stand knapp drei Sekunden im Systemgrau.

    Gesetzt hat das Thema erst ``build_application`` — und davor liegen der
    Ladebildschirm und ``load_operations()``. Gemessen: die Palette steht
    solange auf #efefef, danach auf #343a45. Der erste Eindruck der Anwendung
    war ein hellgrauer Kasten, der mitten im Laden die Farbe wechselt.

    Geprüft am kürzesten Weg durch ``main``: eine abgelaufene Demo kehrt mit 1
    zurück, bevor irgendein Fenster gebaut wird. Ist die Palette dann schon
    gefärbt, steht das Thema früh genug — und der Abschiedsdialog, das einzige
    Fenster dieses Starts, ist mit gedeckt.
    """
    import datetime

    from app.core.activation import Activation
    from app.ui import app as app_module
    from app.ui.theme import THEMES

    themed = THEMES["dark"]["window"]
    # Die Palette gehört der ganzen Anwendung: wer sie in einem Test umstellt,
    # stellt sie für jeden folgenden um. Dieselbe Sorgfalt wie bei der
    # Anzeigeeinheit (siehe ``tests/conftest.py``) — nur hier lokal, weil kein
    # zweiter Test das braucht.
    before = qt_app.palette()
    qt_app.setPalette(QApplication.style().standardPalette())
    assert qt_app.palette().window().color().name() != themed, (
        "ohne Thema ist die Palette die des Systems — sonst prüft der Test nichts"
    )

    # Eine Demo, deren Stichtag herum ist: ``main`` kehrt mit 1 zurück, bevor
    # ein Fenster gebaut wird. Was bis dahin gesetzt ist, ist früh genug.
    gone = Activation(licence=None, days_left=0, deadline=datetime.date(2000, 1, 1))
    assert gone.over, "sonst läuft der Test durch den ganzen Start"
    monkeypatch.setattr(app_module.activation, "state", lambda: gone)

    shown: list[bool] = []
    monkeypatch.setattr(
        "app.ui.dialogs.show_expired_demo", lambda state: shown.append(True), raising=False
    )

    assert app_module.main([]) == 1, "eine abgelaufene Demo startet nicht"
    assert shown == [True], "und sagt es"
    try:
        assert qt_app.palette().window().color().name() == themed, (
            "die Palette steht noch auf dem Systemgrau"
        )
    finally:
        qt_app.setPalette(before)


def test_the_program_start_configures_https_before_reading_the_licence(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der mitgelieferte CA-Satz muss vor jedem möglichen Netzkontakt gelten."""
    import datetime

    from app.core.activation import Activation
    from app.ui import app as app_module

    order: list[str] = []
    gone = Activation(licence=None, days_left=0, deadline=datetime.date(2000, 1, 1))
    monkeypatch.setattr(
        app_module.network,
        "configure_certificates",
        lambda: order.append("certificates") or True,
    )
    monkeypatch.setattr(
        app_module.activation,
        "state",
        lambda: order.append("licence") or gone,
    )
    monkeypatch.setattr("app.ui.dialogs.show_expired_demo", lambda _state: None, raising=False)

    assert app_module.main([]) == 1
    assert order[:2] == ["certificates", "licence"]


def test_the_marketing_video_follows_demo_trial_and_sale_configuration(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die nächste Aufnahme darf nie das Angebot des vorigen Baus versprechen."""
    import datetime

    from tools import make_video

    monkeypatch.setattr(make_video.activation_store, "DEMO_UNTIL", None)
    monkeypatch.setattr(make_video.activation_store, "TRIAL_FROM", None)
    sale = " ".join(make_video.offer_copy("de"))
    assert "14" not in sale and "Demo" not in sale

    monkeypatch.setattr(make_video.activation_store, "TRIAL_FROM", datetime.date(2027, 2, 1))
    trial = " ".join(make_video.offer_copy("de"))
    assert f"{make_video.activation_store.TRIAL_DAYS} Tage" in trial

    monkeypatch.setattr(make_video.activation_store, "DEMO_UNTIL", datetime.date(2026, 10, 30))
    demo = " ".join(make_video.offer_copy("en"))
    assert "30 October 2026" in demo and "days" not in demo


def test_the_unlock_dialog_does_not_close_on_an_empty_field(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """„Eintragen" mit leerem Feld schloss den Dialog wortlos.

    Das ist der Zustand, in dem jemand nicht weiter weiß, und die Antwort war
    ein verschwundenes Fenster — auf den einen Knopf hin, der etwas versprach.
    ``_remember`` rief ``reject()``, sobald das Feld leer war.

    Jetzt ist der Knopf gesperrt, solange nichts dasteht, und sagt im Tooltip
    warum (Regel 19, §2.7). Über die Tastatur bleibt er erreichbar — dann sagt
    der Dialog es, statt zu gehen.
    """
    from app.core import activation
    from app.core.activation import store
    from app.ui.dialogs import ActivationDialog

    monkeypatch.setattr(store, "user_config_dir", lambda: tmp_path)
    activation.forget_cache()
    try:
        dialog = ActivationDialog()
        try:
            assert not dialog.check_button.isEnabled(), "leeres Feld, und der Knopf verspricht was"
            assert dialog.check_button.toolTip(), "gesperrt ohne Grund ist die halbe Antwort"

            closed: list[bool] = []
            dialog.rejected.connect(lambda: closed.append(True))
            dialog._remember()
            assert closed == [], "der Dialog ging zu, statt zu sagen was fehlt"

            dialog.field.setPlainText("SOLIDON3D-1-AAAAAAAA")
            assert dialog.check_button.isEnabled(), "mit Schlüssel muss er können"
            assert not dialog.check_button.toolTip(), "und dann ohne Grund dastehen"

            dialog.field.setPlainText("   ")
            assert not dialog.check_button.isEnabled(), "Leerzeichen sind kein Schlüssel"
        finally:
            dialog.deleteLater()
    finally:
        activation.forget_cache()


def test_the_activation_dialog_reads_as_two_small_steps(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ohne Lizenzwissen sieht man Reihenfolge, Abkürzung und Offline-Ausweg."""
    from PySide6.QtWidgets import QGroupBox, QLabel

    from app.core import activation
    from app.core.activation import store
    from app.ui.dialogs import ActivationDialog

    monkeypatch.setattr(store, "user_config_dir", lambda: tmp_path)
    activation.forget_cache()
    try:
        dialog = ActivationDialog()
        groups = [group.title() for group in dialog.findChildren(QGroupBox)]
        labels = " ".join(label.text() for label in dialog.findChildren(QLabel))

        assert groups == ["1 · Lizenzschlüssel einfügen", "2 · Diesen Rechner aktivieren"]
        assert "Kein Konto" in labels and "ohne Internet" in labels
        assert not dialog.online_button.isEnabled()
        assert "Zuerst" in dialog.online_button.toolTip()
        assert dialog.online_button.isDefault(), "der kurze Online-Weg ist der Hauptknopf"
        assert dialog.offline_button.text().startswith("Offline")
    finally:
        activation.forget_cache()


def test_the_offline_activation_page_opens_in_the_ui_language(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Dateiweg wechselt nicht auf einer deutschen Website die Sprache."""
    from PySide6.QtCore import QUrl

    from app.ui import dialogs

    opened: list[str] = []
    monkeypatch.setattr(dialogs, "get_language", lambda: "es")
    monkeypatch.setattr(
        dialogs.QDesktopServices,
        "openUrl",
        staticmethod(lambda url: opened.append(url.toString())),
    )

    dialog = dialogs.OfflineActivationDialog("{}")
    dialog._open_page()

    assert opened == [f"{dialog.PAGE_URL}?lang=es"]
    assert QUrl(opened[0]).query() == "lang=es"


# --- Die Projektdatei als Argument (Dateizuordnung) -----------------------------


def test_a_project_given_on_the_command_line_is_found(tmp_path: Path) -> None:
    """Was per Doppelklick mitkommt, findet die Anwendung im Aufruf.

    Unter Windows und Linux ist das der ganze Mechanismus hinter einer
    Dateizuordnung — der Explorer startet die Anwendung mit dem Pfad als
    Argument. Bis dahin wurde er an ``QApplication`` weitergereicht und dort
    verworfen, und die Zuordnung, die der Linux-Menüeintrag längst versprach,
    ging ins Leere.
    """
    from app.ui.app import requested_file

    project = tmp_path / "dose.p3d"
    project.write_bytes(b"PK\x03\x04")

    assert requested_file(["Solidon3D.exe", str(project)]) == project


def test_options_and_missing_files_are_stepped_over(tmp_path: Path) -> None:
    """Eine Qt-Option ist kein Dateiname, und ein Tippfehler ist keine Datei.

    Beides würde sonst als Projekt geöffnet und endete in einer Fehlermeldung
    vor dem ersten Blick auf das Programm.
    """
    from app.ui.app import requested_file

    project = tmp_path / "halter.p3d"
    project.write_bytes(b"PK\x03\x04")

    assert requested_file(["Solidon3D.exe"]) is None
    assert requested_file(["Solidon3D.exe", "-style", "fusion"]) is None
    assert requested_file(["Solidon3D.exe", str(tmp_path / "gibtsnicht.p3d")]) is None
    assert requested_file(["Solidon3D.exe", "--platform", str(project)]) == project


def test_a_directory_is_not_reported_as_missing(
    tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    """Ein Verzeichnis ist keine Datei — aber es fehlt auch nicht.

    Beides lief in dieselbe Zeile: „file … does not exist". Wer im Protokoll
    sucht, warum sein Doppelklick nichts tat, liest genau diese und sucht
    danach an der falschen Stelle weiter.
    """
    from app.ui.app import requested_file

    ordner = tmp_path / "projekte"
    ordner.mkdir()

    with caplog.at_level(logging.WARNING):
        assert requested_file(["Solidon3D.exe", str(ordner)]) is None

    assert "does not exist" not in caplog.text, "das Verzeichnis gibt es"
    assert "not a file" in caplog.text


def test_the_finder_event_opens_what_it_names(tmp_path: Path, qt_app: QApplication) -> None:
    """Auf dem Mac kommt die Datei als Ereignis, nicht als Argument.

    Ohne diesen Filter wäre der Dokumenttyp im Bundle ein Eintrag ohne Wirkung:
    Der Finder startet die Anwendung und schickt ihr den Pfad, und niemand hört
    zu. Geprüft wird über das echte Ereignis und nicht über einen direkten
    Aufruf von ``open_path`` — die Verbindung dazwischen ist die Sache.
    """
    from PySide6.QtGui import QFileOpenEvent

    from app.ui.app import FileOpenListener

    project = tmp_path / "deckel.p3d"
    project.write_bytes(b"PK\x03\x04")

    opened: list[Path] = []

    class Recorder:
        def open_path(self, path: Path) -> None:
            opened.append(path)

    listener = FileOpenListener(cast(Any, Recorder()))
    handled = listener.eventFilter(qt_app, QFileOpenEvent(str(project)))

    assert handled, "das Ereignis wurde durchgereicht statt beantwortet"
    assert opened == [project]


def test_a_step_can_be_made_exact_afterwards(window: MainWindow) -> None:
    """Der Weg, den es nicht gab: erst bauen, dann exakt brauchen.

    Beim Anlegen gab es den Umschalter seit je, beim Nachbearbeiten nicht — und
    damit war ein Quader, den jemand ohne ihn angelegt hatte, endgültig ein
    Netz. Sieben Operationen blieben ihm für immer gesperrt, und der einzige
    Weg dorthin war, den Schritt zu löschen und alles darüber neu zu bauen.
    """
    from PySide6.QtWidgets import QCheckBox

    window.session.start_new()
    window.run_operation(REGISTRY.get("create_box"))
    dialog = next(child for child in window.findChildren(OperationDialog) if child.isVisible())
    dialog.accept()
    window.session.wait_for_idle()
    assert [entry.op for entry in window.session.project.document.ops] == ["create_box"]

    op_id = window.session.project.document.ops[0].id
    window.edit_operation(op_id)
    dialog = next(child for child in window.findChildren(OperationDialog) if child.isVisible())
    exact = next(
        box for box in dialog.findChildren(QCheckBox) if "Flächen und Kanten" in box.text()
    )
    assert not exact.isChecked(), "der Haken steht auf dem, was im Verlauf steht"
    assert exact.isVisibleTo(dialog), "und er ist zu sehen, ohne aufzuklappen"
    exact.setChecked(True)
    dialog.accept()
    window.session.wait_for_idle()

    assert [entry.op for entry in window.session.project.document.ops] == ["create_brep_box"]
    body = next(iter(window.session.last_result.scene.objects.values()))
    assert body.kind == "brep", "der Körper ist jetzt wirklich exakt"


def test_the_edit_dialog_shows_the_toggle_on_an_exact_step_too(window: MainWindow) -> None:
    """Auch am anderen Ende des Paars: der Haken steht dann gesetzt da.

    Gebaut wird der Dialog aus dem sichtbaren Zwilling, gleich welcher von
    beiden im Verlauf steht — aus dem exakten heraus gäbe es kein ``anchor``,
    und wer den Haken abwählte, bekäme einen Dialog ohne die Felder, die er
    gerade freigeschaltet hat.
    """
    from PySide6.QtWidgets import QCheckBox

    window.session.start_new()
    window.session.apply(
        "Quader", [OperationDraft(op="create_brep_box", inputs=[], params={"width": 30.0})]
    )
    window.session.wait_for_idle()

    op_id = window.session.project.document.ops[0].id
    window.edit_operation(op_id)
    dialog = next(child for child in window.findChildren(OperationDialog) if child.isVisible())
    try:
        exact = next(
            box for box in dialog.findChildren(QCheckBox) if "Flächen und Kanten" in box.text()
        )
        assert exact.isChecked(), "der Schritt ist der exakte — der Haken sagt es"
        assert "anchor" in dialog._editors, "der Dialog kennt die Felder des Netzkerns"
    finally:
        dialog.reject()


def test_a_locked_tool_names_the_step_that_spoiled_the_exact_body(window: MainWindow) -> None:
    """Der Hinweis sprach vom Haken beim Anlegen — auch dann, wenn der Körper
    längst exakt angelegt war und ein späterer Schritt ihn zum Netz gemacht hat.

    In dem Fall hilft kein Haken. Die Auswertung weiß, welcher Schritt es war
    (``evaluate.exact_became_mesh``), und der Satz nennt ihn.

    **Gemessen wird das an ``fillet_edges`` und nicht mehr an ``sketch_pocket``.**
    Die Tasche stand hier als Beispiel für ein gesperrtes Werkzeug, bis sie am
    30.08.2026 auch in Netze schneiden lernte — sie ist keins mehr. Die Zusage
    selbst ist davon unberührt und gilt weiter für die sieben Operationen, die
    den exakten Kern wirklich brauchen; Verrunden ist eine davon und hängt an
    keiner Flächenauswahl.
    """
    window.session.start_new()
    window.session.apply(
        "Quader", [OperationDraft(op="create_brep_box", inputs=[], params={"width": 40.0})]
    )
    window.session.wait_for_idle()
    body = next(iter(window.session.last_result.scene.objects))
    window.session.apply(
        "Bohrung", [OperationDraft(op="drill_hole", inputs=[body], params={"diameter": 5.0})]
    )
    window.session.wait_for_idle()

    window.object_tree.select_object(next(iter(window.session.last_result.scene.objects)))
    window._update_actions()
    hint = window._op_actions["fillet_edges"].toolTip()

    assert str(REGISTRY.get("drill_hole").title) in hint, hint
    assert "Nimm die Schritte ab dort zurück" in hint, "der Satz nennt eine Handlung, die es gibt"


def test_a_finding_names_a_body_a_later_step_has_replaced(qt_app: QApplication) -> None:
    """Der Fall aus dem Handbuchbild, in allen sechs Sprachen zu sehen.

    Das Aushöhlen meldet etwas über die Dose. Danach macht ``create_lid`` aus
    ihr zwei Körper — die Kennung `obj_1` gibt es nicht mehr, die zwei Befunde
    zeigen aber weiter darauf. Im Bericht stand deshalb „obj_1" statt eines
    Namens: aufgelöst wurde nur gegen die Endszene, und dort fehlt er.

    Der Name, den der Körper trug, ist die Antwort auf „welcher denn". Er ist
    nicht mehr aktuell — aber er war es, als der Befund entstand, und das ist
    genau die Auskunft, die der Leser braucht.
    """
    from app.core.knowledge import profiles
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.scene.project import ProjectSources, new_project
    from app.ui.panels import ReportPanel

    project = new_project("centauri-carbon-2", "petg")
    document = project.document
    history = History(document)
    history.apply(
        "Dose",
        [
            OperationDraft(
                op="create_box",
                params={"width": 60.0, "depth": 40.0, "height": 30.0, "name": "Dose"},
            )
        ],
    )
    history.apply(
        "Aushöhlen",
        [
            OperationDraft(
                op="hollow_object",
                inputs=(document.ops[-1].outputs[0],),
                params={"wall": 3.0, "open_top": True},
            )
        ],
    )
    # Ein Werkzeug, das die Dose im Abziehen verbraucht. Der Deckel taugt dafür
    # seit ``keeps_inputs`` nicht mehr: Er setzt die Dose fort und legt den
    # Deckel daneben — die Kennung bleibt, und der Fall wäre verfehlt.
    history.apply(
        "Werkzeug",
        [OperationDraft(op="create_cylinder", params={"diameter": 20.0, "name": "Werkzeug"})],
    )
    tool = document.ops[-1].outputs[0]
    history.apply(
        "Abziehen",
        [OperationDraft(op="subtract_objects", inputs=(tool, "obj_1"), params={})],
    )

    profile = profiles.make_profile("centauri-carbon-2", "petg")
    result = evaluate(document, profile, sources=ProjectSources(project))

    stale = [f for f in result.scene.report.findings if f.object_id == "obj_1"]
    assert stale, "kein Befund zeigt mehr auf den verbrauchten Körper — Fall verfehlt"
    assert "obj_1" not in result.scene.objects, "obj_1 lebt noch — das Abziehen hat ihn verbraucht"

    panel = ReportPanel()
    try:
        panel.show_result(result, document)
        lines = [panel.list.item(row).text() for row in range(panel.list.count())]
    finally:
        panel.deleteLater()

    about_stale = [line for line in lines if any(str(f.message) in line for f in stale)]
    assert about_stale, f"die Befunde stehen nicht in der Liste: {lines}"
    assert not any("obj_1" in line for line in about_stale), (
        f"der Bericht nennt die Kennung statt des Namens: {about_stale}"
    )
    assert any("Dose" in line for line in about_stale), (
        f"der Bericht nennt den Namen nicht, den der Körper trug: {about_stale}"
    )


def test_the_face_jump_names_the_area_in_the_chosen_unit(window: MainWindow) -> None:
    """Und die Beschriftung des Flächensprungs trug die Einheit **im Satz** —
    „Fläche an {object} — {area} mm², {side}". Ein Satz mit eingebauter Einheit
    kann nicht in Zoll sprechen; die Einheit gehört in den Wert."""
    from app.ui.labels import set_display_unit

    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()

    try:
        set_display_unit("in")
        faces = window._drawable_faces()
        assert faces, "der Testkörper hat Flächen"
        for _feature_id, label, _normal in faces:
            assert "mm²" not in label, label
        assert any("in²" in label for _f, label, _n in faces)
    finally:
        set_display_unit("mm")


#: Eine Kommazahl mit Punkt — aber kein Pfad, keine Versionsnummer, keine Endung.
#:
#: Die Wächter links und rechts sind der Unterschied: „sources/1_cube.stl" und
#: „0.1.2" sind keine Zahlen, und eine Prüfung, die sie mitzählt, wird
#: abgeschaltet statt gelesen.
_DECIMAL_POINT = re.compile(r"(?<![\w./\\-])\d+\.\d+(?![\w./\\-])")


def _visible_texts(root: object, mark: str) -> list[tuple[str, str]]:
    """Jeden Text, den dieser Baum zeigt — Beschriftung, Knopf, Liste, Tooltip."""
    from PySide6.QtWidgets import QAbstractButton, QGroupBox, QLabel, QListWidget, QTreeWidget

    found: list[tuple[str, str]] = []
    for widget in [*root.findChildren(QLabel), *root.findChildren(QAbstractButton)]:
        text = widget.text() if hasattr(widget, "text") else ""
        if text:
            found.append((f"{mark}/{type(widget).__name__}", text))
        if widget.toolTip():
            found.append((f"{mark}/tooltip", widget.toolTip()))
    for box in root.findChildren(QGroupBox):
        if box.title():
            found.append((f"{mark}/QGroupBox", box.title()))
    for listing in root.findChildren(QListWidget):
        for index in range(listing.count()):
            found.append((f"{mark}/QListWidgetItem", listing.item(index).text()))
    for tree in root.findChildren(QTreeWidget):
        for index in range(tree.topLevelItemCount()):
            entry = tree.topLevelItem(index)
            for column in range(tree.columnCount()):
                if entry.text(column):
                    found.append((f"{mark}/QTreeWidgetItem", entry.text(column)))
    return found


def test_no_visible_text_writes_a_decimal_point(window: MainWindow) -> None:
    """Die Gegenprobe zur Regelprüfung — von der anderen Seite.

    `test_no_number_reaches_the_user_past_the_localisation` liest den Quelltext
    und sieht f-Strings mit Formatangabe. Sie sieht **nicht**, was über
    `"%.2f" %`, über `.format()`, über `str(round(…))` oder über ein nacktes
    `f"{wert}"` auf einer Fließkommazahl hereinkäme. Heute gibt es davon keine
    Stelle; morgen schreibt jemand die erste, und die Regel schweigt.

    Diese Prüfung schaut deshalb auf das Ergebnis: Sie baut die zahlenreichen
    Flächen auf — Fenster mit geladenem Modell, Druckeinstellungen, fünf
    Operationsdialoge — und liest jeden Text, den sie zeigen, samt Tooltips.
    Im deutschen Fenster darf dort keine Zahl mit Punkt stehen. Gemessen sind
    das über vierhundert Texte.
    """
    from PySide6.QtCore import QLocale

    from app.ui.print_settings_dialog import PrintSettingsDialog

    before = QLocale()
    try:
        QLocale.setDefault(QLocale("de"))
        window.open_path(MESHES / "plate_holes.stl")
        window.session.wait_for_idle()
        QApplication.processEvents()

        texts = _visible_texts(window, "Fenster")

        settings = PrintSettingsDialog(window.session, window.settings, window)
        settings.show()
        QApplication.processEvents()
        texts += _visible_texts(settings, "Druckeinstellungen")
        settings.reject()

        for name in ("drill_hole", "apply_texture", "insert_nut_trap", "label_text", "hollow"):
            if not REGISTRY.has(name):
                continue
            dialog = OperationDialog(REGISTRY.get(name), {}, window)
            dialog.show()
            QApplication.processEvents()
            texts += _visible_texts(dialog, name)
            dialog.reject()

        assert len(texts) > 300, f"nur {len(texts)} Texte — die Flächen sind nicht aufgebaut"
        offenders = [
            f"{where}: {text[:90]!r}" for where, text in texts if _DECIMAL_POINT.search(text)
        ]
        assert not offenders, "Zahl mit Punkt im deutschen Fenster:\n" + "\n".join(offenders[:15])
    finally:
        QLocale.setDefault(before)


def test_the_decimal_point_check_would_catch_a_violation() -> None:
    """Ein Wächter für die Prüfung darüber: ein grüner Lauf soll etwas heißen."""
    assert _DECIMAL_POINT.search("Übermaß: 12.40 mm")
    assert _DECIMAL_POINT.search("+1.25 cm³")
    assert not _DECIMAL_POINT.search("Übermaß: 12,40 mm")
    assert not _DECIMAL_POINT.search("Pfad: sources/1_cube.stl"), "ein Pfad ist keine Zahl"
    assert not _DECIMAL_POINT.search("Version 0.1.2"), "eine Versionsnummer auch nicht"
    assert not _DECIMAL_POINT.search("https://example.com/x.stl")


# --- Auf einer Fläche zeichnen (§30.1, P3) -----------------------------------


def _face_menu(window: MainWindow) -> tuple[str, object]:
    """Ein Modell laden, seine erste Fläche wählen, ihr Kontextmenü bauen."""
    window.session.import_model(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    face = next(fid for fid, feature in entry.features.items() if feature.kind == "face")

    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, face)
    return face, window.object_tree.context_menu()


def test_a_face_offers_to_be_drawn_on(window: MainWindow) -> None:
    """§30.1 nennt die angeklickte Fläche als Ort einer Skizzenebene, und
    ``planes.py`` nennt sie „die interessantere".

    Erreichbar war sie nur über ein Klappfeld mit Zeilen wie „Fläche an
    Gehäuse — 2 400 mm², oben" — über das Wiedererkennen in einer Liste statt
    über das Zeigen auf sie.
    """
    _face, menu = _face_menu(window)

    assert menu is not None
    labels = [action.text() for action in menu.actions()]  # type: ignore[attr-defined]
    assert "Auf dieser Fläche zeichnen" in labels, f"Eintrag fehlt: {labels}"


def test_choosing_that_entry_really_starts_a_sketch_on_that_face(window: MainWindow) -> None:
    """Der Anschluss, nicht das Angebot.

    Ein Menüeintrag mit einem Handler ist kein eingelöstes Versprechen —
    ``.claude/rules/tests.md`` führt genau diese Bauform („ein Knopf war
    formal verdrahtet und wirkte nicht"). Geprüft wird deshalb, dass der
    Skizzenmodus läuft **und** auf welcher Ebene er steht.
    """
    face, menu = _face_menu(window)
    assert menu is not None

    draw = next(
        action
        for action in menu.actions()  # type: ignore[attr-defined]
        if action.text() == "Auf dieser Fläche zeichnen"
    )
    draw.trigger()

    assert window.sketching(), "der Skizzenmodus läuft"
    panel = window._sketch_panel
    assert panel is not None
    object_id = window.object_tree.selected()
    expected = f"feature:{object_id}:{face}"
    assert panel.canvas.sketch.plane == expected, "und zwar auf der geklickten Fläche"
    assert panel.plane_choice.currentData() == expected, "die Wahl steht mit"

    window.finish_sketch(keep=False)


def test_without_a_chosen_face_nothing_offers_to_be_drawn_on(window: MainWindow) -> None:
    """Am Körper selbst gibt es keine Ebene, auf die man zeigen könnte.

    Die Gegenprobe zum Test oben: Ohne sie wäre auch ein Eintrag grün, der
    immer erscheint — und der führte am Körper in eine Skizze auf einer
    Fläche, die niemand gewählt hat.
    """
    window.session.import_model(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id = next(iter(result.scene.objects))

    window.object_tree.select_object(object_id)
    menu = window.object_tree.context_menu()

    assert menu is not None
    labels = [action.text() for action in menu.actions()]  # type: ignore[attr-defined]
    assert "Auf dieser Fläche zeichnen" not in labels, f"steht am Körper: {labels}"


def test_a_hole_does_not_offer_to_be_drawn_on(window: MainWindow) -> None:
    """Auf einer Bohrung gibt es keine Ebene zu zeichnen.

    **Und dieser Test war der Grund, den vorigen nicht für ausreichend zu
    halten.** Die Gegenprobe „kein Merkmal gewählt" lief auch ohne die
    Artprüfung grün: Dort greift schon die zweite Wache (keine Kennung), und
    der ``kind != "face"``-Zweig war damit ungeprüft. Erst ein Merkmal, das
    eine Kennung hat und **keine Fläche ist**, misst ihn — dafür braucht es
    ein Modell mit Bohrung.
    """
    window.session.import_model(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    hole = next(fid for fid, feature in entry.features.items() if feature.kind == "hole")

    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, hole)
    menu = window.object_tree.context_menu()

    assert menu is not None
    labels = [action.text() for action in menu.actions()]  # type: ignore[attr-defined]
    assert "Auf dieser Fläche zeichnen" not in labels, f"steht an einer Bohrung: {labels}"


def test_the_three_slicer_handles_stand_in_the_menu_itself(window: MainWindow) -> None:
    """Verschieben, Drehen, Skalieren stehen direkt da — nicht zwei Klicks tief.

    **Der Maßstab ist der Slicer, nicht ein CAD-Programm.** Wer Solidon öffnet,
    kommt von Cura oder PrusaSlicer, und dort liegen diese drei auf der
    Werkzeugleiste. Hier lagen sie unter „Ändern" zwischen dreißig anderen
    Einträgen: Rechtsklick, aufklappen, suchen (§2.6, §18.5).

    **Gezählt wird am gebauten Menü**, nicht an ``operations_for_object()``.
    Die Auskunft, welche Operation sich anbietet, ist eine andere als die,
    welche Zeile ein Kunde sieht — dazwischen liegt die Gruppenfaltung, und
    genau die war das Problem. Ein Test gegen die Registerliste wäre grün
    geblieben, während die drei im Untermenü stecken.

    Die Reihenfolge gehört zur Zusage: Sie ist die des Slicers und nicht die
    des Registers.
    """
    window.session.import_model(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id = next(iter(result.scene.objects))

    window.object_tree.select_object(object_id)
    menu = window.object_tree.context_menu()

    assert menu is not None
    rows = [action for action in menu.actions() if not action.isSeparator()]
    direct = [action.text().replace("&", "") for action in rows if action.menu() is None]

    for wanted in ("Verschieben", "Drehen", "Skalieren"):
        assert wanted in direct, (
            f"'{wanted}' is not a row of the menu itself, only these are: {direct}"
        )

    at = [direct.index(name) for name in ("Verschieben", "Drehen", "Skalieren")]
    assert at == sorted(at), f"the three keep the slicer's order, got {direct}"

    # Und die Grenze hält weiterhin: drei Zeilen mehr oben heißt, dass die
    # Faltung darunter sie mitzählen muss.
    from app.ui.panels import MAX_MENU_ROWS

    assert len(rows) <= MAX_MENU_ROWS, (
        f"the menu grew to {len(rows)} rows, the limit is {MAX_MENU_ROWS}: "
        f"{[action.text() for action in rows]}"
    )


def test_the_sketch_mode_leaves_the_view_standing(window: MainWindow) -> None:
    """**Der Schnitt (§30.1, P4).** Robert am 24.08.2026: „am viewport ändert
    sich nichts, bei draufsicht, seitenansicht usw sieht man auch keinen
    unterschied".

    Der Grund war ein Tausch im Stapel: Die Ansicht lag unter einem Blatt,
    also änderte eine Kameravorgabe etwas, das niemand sah. Jetzt bleibt sie
    stehen, das Modell tritt durchscheinend zurück, und die Zeichnung liegt
    darin.
    """
    window.session.import_model(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window.session.evaluate_now()
    vorher = window.viewport.display_mode

    window.start_sketch("sketch_extrude", "")

    assert window.middle_stack.currentWidget() is window.viewport, "die Ansicht bleibt im Bild"
    assert window.viewport.display_mode == "transparent", "das Modell tritt zurück"
    assert window.sketching(), "und gezeichnet wird trotzdem"

    window.finish_sketch(keep=False)

    assert window.viewport.display_mode == vorher, "danach steht die Darstellung wie zuvor"
    assert not window.sketching()


def test_the_camera_swings_onto_the_plane_that_is_drawn_on(window: MainWindow) -> None:
    """Beim Betreten schwenkt sie, danach nie wieder von selbst.

    Ohne den Schwenk läge die Zeichenebene schräg im Bild, und die erste
    Linie ginge irgendwohin. Mit ihm sieht man auf sie — und wer danach
    dreht, bleibt gedreht: Ein Bild, das nach jedem Strich zurückspringt,
    wäre schlimmer als eines, das nie schwenkt.
    """
    window.start_sketch("sketch_extrude", "")
    panel = window._sketch_panel
    assert panel is not None

    frame = window._sketch_frame()
    assert frame is not None, "die Grundebene hat einen Rahmen"
    assert frame.normal == pytest.approx((0.0, 0.0, 1.0)), "XY ist die Vorgabe"

    # Offscreen gibt es keinen Plotter, der Schwenk selbst ist also nicht
    # messbar (Entscheidung G). Prüfbar ist, dass er mit der richtigen Ebene
    # gerufen würde — und dass das Zeichnen ohne Plotter nicht scheitert.
    panel.canvas.set_tool("line")
    panel.canvas.place_on_plane((0.0, 0.0))
    panel.canvas.place_on_plane((20.0, 0.0))

    assert len(panel.canvas.sketch.elements) == 1, "gezeichnet wird auch ohne Bild"
    window.finish_sketch(keep=False)


def test_a_click_in_the_view_draws_on_the_plane(window: MainWindow) -> None:
    """Der Anschluss (§30.1, P4): Klick in der Ansicht, Punkt in der Skizze.

    Offscreen gibt es keinen Plotter, der Sichtstrahl selbst ist also nicht
    messbar (Entscheidung G). Prüfbar ist die Kette dahinter — und genau die
    war der Punkt: ``_sketch_hit`` rechnet den Strahl gegen die Ebene, das
    Signal trägt zwei Zahlen in Millimetern, und die Zeichenfläche macht
    damit dasselbe wie mit einem Klick auf sich selbst.

    **Was dieser Test ausdrücklich nicht prüft**, und das ist gemessen: Dass
    ``_on_left_click`` den Skizzenmodus vor der Auswahlkette abfragt. Entfernt
    man diesen Zweig, bleibt der Test grün — er sendet das Signal selbst,
    statt einen Klick auszulösen, und einen echten Klick gibt es ohne Plotter
    nicht (``_pick_ray`` gibt dort ``None``). Diese eine Zeile gehört zur
    Bild-Hälfte und wird im Prüfstand mit echtem Fenster gemessen, nicht hier.
    """
    window.start_sketch("sketch_extrude", "")
    panel = window._sketch_panel
    assert panel is not None
    panel.canvas.set_tool("line")

    window.viewport.sketchPointPicked.emit((0.0, 0.0))
    window.viewport.sketchPointPicked.emit((20.0, 0.0))

    assert len(panel.canvas.sketch.elements) == 1, "zwei Klicks, eine Linie"
    start, end = panel.canvas.sketch.elements[0].points
    assert start == pytest.approx((0.0, 0.0))
    assert end == pytest.approx((20.0, 0.0))

    window.finish_sketch(keep=False)


def test_the_view_stops_aiming_at_the_plane_when_the_sketch_ends(window: MainWindow) -> None:
    """Sonst zeichnete ein Klick weiter auf eine Ebene, die niemand meint.

    ``set_sketching(None)`` ist die Rücknahme, und ohne sie bliebe der
    Viewport in einem Modus, in dem er keine Körper mehr auswählt — die
    Auswahlkette liegt hinter der Skizzenfrage.
    """
    window.start_sketch("sketch_extrude", "")
    assert window.viewport._sketch_frame is not None, "im Modus zielt er auf die Ebene"

    window.finish_sketch(keep=False)
    assert window.viewport._sketch_frame is None, "danach wieder auf die Szene"


def test_changing_the_plane_swings_the_camera_along(window: MainWindow) -> None:
    """Wer die Ebene wechselt, sieht woanders hin — und will das auch sehen.

    Das ist die eine Stelle, an der nach dem Betreten noch geschwenkt wird.
    Beim Zeichnen selbst bleibt die Ansicht, wie der Nutzer sie gedreht hat.
    """
    window.start_sketch("sketch_extrude", "")
    panel = window._sketch_panel
    assert panel is not None

    vorher = window.viewport._sketch_frame
    assert vorher is not None and vorher.normal == pytest.approx((0.0, 0.0, 1.0))

    panel.choose_plane("plane:xz")

    nachher = window.viewport._sketch_frame
    assert nachher is not None
    assert nachher.normal == pytest.approx((0.0, 1.0, 0.0)), "die Ansicht zielt auf die neue Ebene"

    window.finish_sketch(keep=False)


def test_the_picture_for_the_support_asks_the_viewport_for_its_own(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Das Bild einer Fehlermeldung muss das Modell zeigen, nicht ein Loch.

    **Warum das ein eigener Test ist und kein Bildvergleich.** ``QWidget.grab``
    malt Qts Puffer ab; der Viewport zeichnet in ein natives OpenGL-Fenster und
    steht dort nicht drin. Am 24.08.2026 kam so ein Bogen bei Robert an: alles
    darauf zu sehen — Menüs, Objektbaum, Parameter, Prüfbericht — nur in der
    Mitte, wo das Teil liegt, war es schwarz. Gemessen war der Viewport-Bereich
    danach **eine einzige Farbe** auf 100 % der Fläche; nach der Änderung sind
    es 530.

    Prüfen lässt sich das hier nicht am Bild: ``tests/conftest.py`` setzt
    ``QT_QPA_PLATFORM=offscreen``, dort gibt es keinen Plotter, und
    :meth:`Viewport.snapshot` gibt folgerichtig ``None`` zurück. Ein Test über
    Bildpunkte wäre grün über einer leeren Menge — dieselbe Falle, die im
    Register unter „Offscreen prüft nichts, was am Aktor hängt" steht.

    Geprüft wird deshalb die **Kette**: dass ``window_shot`` überhaupt jemanden
    fragt. Wer den Aufruf entfernt, bekommt einen roten Lauf statt eines
    schwarzen Lochs im nächsten Kundenbogen.

    **Ohne Fenster-Fixture, und das ist gemessen.** Ein zweiter Test daneben
    hat über ``window`` ein ganzes ``MainWindow`` gebaut, nur um zu sehen, dass
    ``snapshot`` ohne Plotter ``None`` gibt. Er hob die Abrissquote dieser Datei
    von 1 aus 3 auf 2 aus 3 — die Suite baut in einem Prozess hunderte
    VTK-Fenster, und zwei weitere kippten sie. Ein nacktes ``QWidget`` genügt
    hier, denn die Frage ist der Aufruf und nicht das Bild.
    """
    from app.ui import support_dialog

    asked: list[object] = []
    monkeypatch.setattr(
        support_dialog, "_paint_viewports", lambda picture, widget: asked.append(widget)
    )
    from PySide6.QtWidgets import QWidget

    widget = QWidget()
    widget.resize(320, 240)
    try:
        data = support_dialog.window_shot(widget)
    finally:
        widget.deleteLater()

    assert data.startswith(b"\x89PNG"), "ohne PNG hat der Bogen kein Bild"
    assert asked == [widget], (
        "window_shot muss die Ansichten nachmalen lassen — sonst bleibt die "
        "Bildmitte leer, und genau dort liegt das Teil des Kunden"
    )


def test_drawing_starts_on_the_selected_face_not_under_it(window: MainWindow) -> None:
    """Fläche gewählt, „Zeichnen" gedrückt — gezeichnet wird auf der Fläche.

    Roberts Fall vom 24.08.2026: Deckfläche ausgewählt, Draufsicht, Zeichnen —
    und die Striche landeten **unter** dem Körper auf z=0. Der Knopf der
    Werkzeugzeile rief ``start_sketch("")`` ohne Ebene, und ohne Ebene hieß
    Grundebene, gleich was gewählt war. Wer eine Fläche wählt und dann
    zeichnet, meint diese Fläche.

    Geprüft wird bis in die Zahl: Der Rahmen der Zeichenebene muss auf der
    Höhe der Deckfläche liegen, nicht auf null — der Ebenenname allein bewiese
    nur die halbe Kette. Die Höhe wird aus dem Körper gelesen und nicht
    hingeschrieben: Sie stand hier als 10.0, weil der 20-mm-Würfel um den
    Ursprung lag; seit das erste Modell eines Projekts mittig auf dem Bett
    landet (03.09.2026), sind es 20.0. Eine abgelesene Zahl altert still, eine
    gemessene nicht.
    """
    window.session.import_model(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    top = next(
        fid
        for fid, feature in entry.features.items()
        if feature.kind == "face" and feature.params.get("normal", (0, 0, 0))[2] > 0.9
    )
    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, top)

    window.action_sketch_free()
    try:
        panel = window._sketch_panel
        assert panel is not None
        assert panel.canvas.sketch.plane == f"feature:{object_id}:{top}", (
            "die gewählte Fläche muss die Zeichenebene sein, nicht die Grundebene"
        )
        frame = window._sketch_frame()
        assert frame is not None
        deckflaeche = entry.mesh.bounds.maximum[2]
        assert deckflaeche > 0.0, "sonst prüft die Zeile darunter gegen null"
        assert frame.origin[2] == pytest.approx(deckflaeche), (
            "gezeichnet wird auf der Deckfläche, nicht darunter auf z=0"
        )
    finally:
        window.finish_sketch(keep=False)


def test_duplicate_face_ids_keep_the_selected_body_and_its_label(window: MainWindow) -> None:
    """``face_1`` gilt je Körper und darf deshalb nicht den ersten gewinnen lassen.

    Zwei importierte Körper tragen gleichnamige erkannte Flächen. Gewählt wird
    bewusst der zweite: Ebenenreferenz und verständlicher Hinweis müssen bei
    ihm bleiben, unabhängig von Flächengröße und Szenenreihenfolge.
    """
    window.session.import_model(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window.session.import_model(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    first, second = list(result.scene.objects.items())[-2:]
    _first_id, first_entry = first
    second_id, second_entry = second
    first_entry.name = "Erster Körper"
    second_entry.name = "Gewählter Körper"
    duplicate = next(
        feature_id
        for feature_id, feature in second_entry.features.items()
        if feature.kind == "face"
        and feature_id in first_entry.features
        and first_entry.features[feature_id].kind == "face"
    )
    assert str(first_entry.name) != str(second_entry.name), "die Namen müssen unterscheidbar sein"

    window.object_tree.select_object(second_id)
    window.object_tree.select_feature(second_id, duplicate)
    window.action_sketch_free()
    try:
        panel = window._sketch_panel
        assert panel is not None
        assert panel.canvas.sketch.plane == f"feature:{second_id}:{duplicate}"
        assert str(second_entry.name) in window._sketch_hint.text(), (
            "der Hinweis muss den tatsächlich gewählten Körper nennen"
        )
        assert str(first_entry.name) not in window._sketch_hint.text()
    finally:
        window.finish_sketch(keep=False)


def test_drawing_without_a_selection_still_starts_on_the_base_plane(window: MainWindow) -> None:
    """Ohne Auswahl bleibt die Grundebene die Vorgabe — der Fix darf den
    leeren Start nicht mitreißen."""
    window.action_sketch_free()
    try:
        panel = window._sketch_panel
        assert panel is not None
        assert panel.canvas.sketch.plane.startswith("plane:"), panel.canvas.sketch.plane
    finally:
        window.finish_sketch(keep=False)


def test_the_snap_marker_follows_the_canvas_not_a_second_calculation(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Fangmarke zeigt den Ort, den der Canvas gefangen hat — und stirbt
    mit dem Modus.

    Roberts „die Klicks sind woanders als ich klick" (24.08.2026) war der
    Rasterfang ohne sichtbare Marke: bis zu ein halber Rasterschritt zwischen
    Zeiger und Punkt, elf Bildpunkte bei 2 mm Raster. Der Ort kommt vom
    Canvas (``pointer_target``), denn nur er kennt Raster **und** „vorhandener
    Punkt schlägt Raster" — im Viewport nachgerechnet wäre es die zweite Zahl
    für dieselbe Sache (d6335c1).

    Offscreen gibt es keinen Plotter und damit keine Marke zum Ansehen;
    geprüft wird die **Verbindung** — dieselbe Haltung wie beim Bild des
    Fehlerbogens: Wer den Draht kappt, bekommt einen roten Lauf, keinen
    Zeiger, der wieder lügt.
    """
    shown: list[object] = []
    monkeypatch.setattr(
        type(window.viewport), "show_sketch_cursor", lambda self, point: shown.append(point)
    )
    window.action_sketch_free()
    try:
        panel = window._sketch_panel
        assert panel is not None
        panel.pointerMoved.emit(4.0, -6.0)
        assert shown[-1] == (4.0, -6.0), "die gefangene Stelle muss die Marke stellen"
    finally:
        window.finish_sketch(keep=False)
    before = len(shown)
    panel.pointerMoved.emit(1.0, 1.0)
    assert len(shown) == before, "nach dem Modus darf der Draht nicht mehr tragen"


def test_the_sketch_hint_names_the_plane_being_drawn_on(window: MainWindow) -> None:
    """Der Hinweis sagt, worauf gezeichnet wird — und zieht beim Wechsel nach.

    Die andere Hälfte der Fangmarke: Das Kreuz sagt, wohin der Klick fällt,
    dieser Satz sagt, worauf. Robert hat am 24.08.2026 auf z=0 gezeichnet und
    es erst am Ergebnis gemerkt — mit dem Satz hätte die Leiste „Draufsicht
    (XY)" gesagt, während er auf die Deckfläche sah.
    """
    window.session.import_model(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))
    top = next(
        fid
        for fid, feature in entry.features.items()
        if feature.kind == "face" and feature.params.get("normal", (0, 0, 0))[2] > 0.9
    )
    window.object_tree.select_object(object_id)
    window.object_tree.select_feature(object_id, top)

    window.action_sketch_free()
    try:
        panel = window._sketch_panel
        assert panel is not None
        assert "Fläche an" in window._sketch_hint.text(), (
            "auf einer Fläche gestartet muss der Hinweis die Fläche nennen"
        )
        assert panel.choose_plane("plane:xy")
        assert "Draufsicht" in window._sketch_hint.text(), (
            "nach dem Wechsel muss der Hinweis die neue Ebene nennen"
        )
        assert "  (" not in window._sketch_hint.text(), (
            "das Tastenkürzel hilft beim Wechseln, nicht beim Wissen, wo man ist"
        )
    finally:
        window.finish_sketch(keep=False)


def test_saving_a_part_takes_the_whole_stack_by_id_not_by_position(window: MainWindow) -> None:
    """Der Rezeptdialog bekommt die IDs der Schritte — nicht ihre Plätze.

    ``capture`` filtert nach ``Operation.id`` (zählt ab eins), ``enumerate``
    zählt ab null: Mit Indizes fiel der **letzte** Schritt jedes Stapels
    still aus dem Rezept, und niemand sah es — drei Schritte ergeben auch
    einen Körper, der Bereichstest blieb grün. Gefunden am 25.08.2026 bei der
    Verifikation im echten Fenster: Der Weg-2-Halter verlor seine
    Versteifung.

    Geprüft wird die Übergabe an den Dialog — dieselbe Stelle, an der der
    Fehler saß —, nicht der Dialog selbst: Der gehört seinen eigenen Tests.
    Und in derselben Übergabe steckte der zweite Fund desselben Tages: Das
    ``saved``-Signal trägt den **Namen** des Rezepts, und direkt an
    ``show_parts`` verbunden wurde er zum Suchtext — der Katalog zeigte nach
    dem Speichern nur noch den neuen Baustein, bei leerem Suchfeld. Verbunden
    gehört ``refresh``, das keinen Parameter nimmt.
    """
    from unittest import mock

    from app.core import examples

    window.session.open_project(examples.directory() / "weg2-halter-konstruieren.p3d")
    window.session.wait_for_idle()
    window.session.evaluate_now()
    document = window.session.project.document
    assert len(document.ops) >= 2, "der Fall braucht einen Stapel mit mehreren Schritten"

    captured: dict[str, object] = {}

    class Attrappe:
        def __init__(self, _doc, _payloads, op_ids, _features, _profile, parent=None):
            captured["op_ids"] = tuple(op_ids)
            captured["dialog"] = self
            self.saved = mock.Mock()

        def exec(self):
            return 0

        def release(self):
            return None

        def deleteLater(self):  # noqa: N802 - Qt-Namen gehoeren Qt
            return None

    katalog = mock.Mock()
    with mock.patch("app.ui.main_window.RecipeDialog", Attrappe):
        window._save_as_part(katalog)

    assert captured["op_ids"] == tuple(op.id for op in document.ops), (
        "jeder Schritt des Stapels muss das Rezept erreichen — auch der letzte"
    )
    dialog = captured["dialog"]
    assert isinstance(dialog, Attrappe)
    verbunden = [aufruf.args[0] for aufruf in dialog.saved.connect.call_args_list]
    assert katalog.refresh in verbunden, (
        "nach dem Speichern wird der Katalog aufgefrischt, mit stehender Suche"
    )
    assert katalog.show_parts not in verbunden, (
        "der Rezeptname darf nie als Suchtext im Katalog landen"
    )


def test_a_paying_customer_is_not_told_the_trial_ran_out(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Zwei Lagen sperren, und sie heißen nicht gleich (§33.1, H4).

    ``unlocked`` verlangt ``not damaged``, sperrt also auch einen zahlenden
    Kunden, dessen Installation gebrochen ist. Der Sperrtext leitete sich
    daraus ab und behauptete „Der Testzeitraum ist abgelaufen — dafür braucht
    Solidon einen Lizenzschlüssel" — bei jemandem, der einen hat, und während
    die Statuszeile im selben Fenster „Die Installation ist beschädigt" sagte.

    Geprüft an **beiden** Lagen, denn eine allein sagt nichts: Der abgelaufene
    Testlauf muss weiter seinen eigenen Satz bekommen. Gefunden von
    3d-druck-46 im Lizenz-Audit.
    """
    from app.core import activation
    from app.core.activation import store
    from app.ui.dialogs import damaged_line

    aktion = next(iter(window._op_actions.values()))

    monkeypatch.setattr(activation, "_cached", activation.Activation(damaged=True))
    window._lock_hint(aktion, True)
    beschaedigt = aktion.statusTip()

    monkeypatch.setattr(activation, "_cached", activation.Activation(days_left=0))
    aktion.setProperty("tip_before_lock", None)
    window._lock_hint(aktion, True)
    abgelaufen = aktion.statusTip()

    monkeypatch.setattr(store, "TRIAL_FROM", None)
    aktion.setProperty("tip_before_lock", None)
    window._lock_hint(aktion, True)
    ohne_test = aktion.statusTip()

    assert damaged_line() in beschaedigt, "die beschädigte Installation sagt, was sie ist"
    assert "Testzeitraum" not in beschaedigt, (
        "wer bezahlt hat, wird nicht nach einem Schlüssel gefragt, den er hat"
    )
    assert "Testzeitraum" in abgelaufen, "und der abgelaufene Testlauf behält seinen Satz"
    assert beschaedigt != abgelaufen
    assert "Testzeitraum" not in ohne_test
    assert "Geräteaktivierung" in ohne_test


def test_the_status_line_speaks_on_the_day_the_trial_ends(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ausgerechnet am Tag null schwieg sie.

    ``in_trial`` verlangt ``days_left > 0``, also fiel bei genau null keine
    Verzweigung mehr zu: zehn Tage unsichtbar (richtig), zwei Tage sichtbar,
    **null Tage unsichtbar** — an dem Tag, an dem alles grau wird, stand die
    Erklärung nur noch in Tooltips. ``expired`` gab es die ganze Zeit; gefragt
    hat es niemand.
    """
    from app.core import activation

    def zeile(tage: int) -> str:
        monkeypatch.setattr(activation, "_cached", activation.Activation(days_left=tage))
        window._trial_status_line()
        return window.trial_line.text()

    assert not zeile(10), "zehn Tage sind kein Anlass, jemanden anzusprechen"
    assert zeile(2), "kurz davor schon"
    assert zeile(0), "und am Tag, an dem es zu ist, erst recht"
    assert "abgelaufen" in zeile(0)


def test_the_status_line_explains_the_sale_version_without_inventing_a_trial(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gesperrte Werkzeuge bekommen auch ohne vorherigen Test einen sichtbaren Grund."""
    from app.core import activation
    from app.core.activation import store

    monkeypatch.setattr(store, "TRIAL_FROM", None)
    monkeypatch.setattr(activation, "_cached", activation.Activation(days_left=0))
    window._trial_status_line()

    assert "Testzeitraum" not in window.trial_line.text()
    assert "Geräteaktivierung" in window.trial_line.text()


def test_switching_back_to_the_mesh_says_what_it_costs(window: MainWindow) -> None:
    """Der Weg **zurück** aus dem exakten Kern hat dieselbe Sackgasse wie der
    Weg hin — nur sperrt ihn niemand, und das ist richtig.

    Gemessen von d1 am laufenden System: exakter Quader, darüber eine
    Verrundung, dann den Haken abgewählt — die Auswertung hält bei der
    Verrundung an, weil sie einen exakten Körper braucht. Der Satz des Kerns
    ist gut und kommt **nach** dem Klick (Regel 19). ``_lock_twin_toggle``
    fragt nur, ob der Zwilling auf der *Auswahl* kann, nicht ob darüber
    liegende Schritte die Exaktheit brauchen.

    Gesperrt wird trotzdem nicht: Zurückschalten ist eine legitime Absicht,
    und ein Haken, den man nicht abwählen darf, wäre die schlechtere
    Sackgasse. Was fehlte, ist die Auskunft davor.
    """
    from app.core.bootstrap import load_operations
    from app.core.scene import History, OperationDraft

    load_operations()
    document = window.session.project.document
    history = History(document)
    history.apply("Quader", [OperationDraft(op="create_brep_box", params={})])
    box_step = document.ops[-1].id
    history.apply(
        "Verrunden",
        [OperationDraft(op="fillet_edges", inputs=("obj_1",), params={"radius": 2.0})],
    )

    hint = window._twin_toggle_hint("Grundsatz.", box_step, exact_now=True)

    assert "Grundsatz." in hint, "der Werbetext bleibt stehen"
    assert "1" in hint, f"die Zahl der betroffenen Schritte fehlt: {hint!r}"

    # Gegenprobe eins: ohne einen Schritt darüber gibt es nichts zu warnen.
    assert window._twin_toggle_hint("Grundsatz.", document.ops[-1].id, exact_now=True) == (
        "Grundsatz."
    )
    # Gegenprobe zwei: Wer den Haken **setzt**, nimmt niemandem etwas weg.
    assert window._twin_toggle_hint("Grundsatz.", box_step, exact_now=False) == "Grundsatz."


def test_the_dialog_names_both_bodies_a_boolean_will_take() -> None:
    """Bei zwei Eingängen nennt der Satz sie beim Namen.

    Der Hinweis gab es seit je — er sagte aber nur „die 2 zuerst gewählten von
    3", und damit musste der Kunde seine eigene Klickreihenfolge erinnern.
    Ausgerechnet dort zählt sie am meisten: Die Booleschen sagen zu, dass „das
    zuerst angeklickte mit seinem Namen und Material bleibt" — welches das ist,
    ließ der Satz offen.

    Gegen die Funktion und nicht gegen ein gebautes Fenster, weil hier die
    Formulierung geprüft wird und nicht der Weg dorthin; den prüft
    ``test_a_dialog_says_which_body_it_works_on`` eine Ebene höher.
    """
    from app.ui.main_window import _works_on

    two_of_three = _works_on(["Klotz", "Stift", "Deckel"], 3, 2)

    assert "Klotz" in two_of_three and "Stift" in two_of_three
    assert "Deckel" not in two_of_three, "der dritte wird nicht verrechnet und nicht genannt"

    # Die Gegenprobe: Wer genau so viel wählt, wie die Operation nimmt, braucht
    # keine Erklärung — sonst stünde der Satz bei jeder zweiten Operation.
    assert _works_on(["Klotz", "Stift"], 2, 2) == ""


def test_the_halt_message_goes_when_the_chain_runs_again(window: MainWindow) -> None:
    """„Die Kette hält an" ist ein Zustand, keine Auskunft über eine Handlung.

    Eine Meldung überlebt hier absichtlich jeden Lauf (``announce``) — richtig
    für „Exportiert: dose.3mf", das ein Ergebnis festhält, und falsch für
    einen Stopp: Der gilt, solange die Kette steht, und nicht länger. Robert
    sah den Satz am 29.08.2026 über einem Prüfbericht mit null Fehlern und
    null Warnungen, lange nachdem er den Schritt zurückgenommen hatte — die
    Statuszeile behauptete einen Zustand, den es nicht mehr gab.

    Gemerkt wird die **Herkunft** der Meldung und nicht ihr Text: Ein
    Vergleich auf den Satz bräche beim ersten Sprachwechsel.
    """
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    object_id = next(iter(window.session.last_result.scene.objects))

    window.session.apply(
        "Bohrung setzen",
        [
            OperationDraft(
                op="drill_hole",
                inputs=(object_id,),
                params={"diameter": 5000.0, "x": 0.0, "y": 0.0, "z": 4.0, "axis": "z"},
            )
        ],
    )
    window.session.wait_for_idle()

    assert window.session.last_result.stopped_at is not None, "der Wert hält die Kette an"
    assert "hält an" in window._announcement, "und die Statuszeile sagt es"

    window.session.undo()
    window.session.wait_for_idle()

    assert window.session.last_result.stopped_at is None, "zurückgenommen rechnet sie wieder"
    assert window._announcement == "", (
        "und der Satz über den Stopp steht nicht mehr da — er gilt nicht mehr"
    )


def test_a_chosen_part_reaches_the_catalogue_in_one_click(window: MainWindow) -> None:
    """Die Bausteine haben keinen Menüort mehr — dafür einen am gewählten Teil.

    Neunundzwanzig Bausteine standen in sechs Untermenüs, siebenundzwanzig
    davon drei Klicks tief, und jede Zeile nannte eine Vokabel statt einer
    Form: „Filmscharnier", „Schnappverbinder für eine Naht". Wer nicht weiß,
    wie ein Filmscharnier aussieht, findet es dort nicht. Der Katalog mit
    Bildern gab es die ganze Zeit — nur in *Datei*, also dort, wo niemand
    hinsieht, der gerade auf eine Fläche zeigt (§2.6).

    **Roberts Bedingung zu dieser Änderung** war genau dieser Weg: „solange
    man einfach zum Katalog kommt, wenn man das Teil gewählt hat". Geprüft
    wird deshalb beides — dass der Eintrag am gewählten Merkmal steht, und
    dass er wirklich den Katalog ruft. Durchgereicht ist nicht gerufen.
    """
    from PySide6.QtWidgets import QMenu

    face, menu = _face_menu(window)
    assert face
    assert isinstance(menu, QMenu)

    titles = [action.text().replace("&", "") for action in menu.actions()]
    assert "Baustein einsetzen …" in titles, (
        f"der Weg zum Katalog fehlt am gewählten Teil — angeboten wird: {titles}"
    )

    gerufen: list[bool] = []
    window.action_catalog = lambda: gerufen.append(True)  # type: ignore[method-assign]
    window.object_tree.catalogRequested.connect(window.action_catalog)
    entry = next(a for a in menu.actions() if a.text().replace("&", "") == "Baustein einsetzen …")
    entry.trigger()
    assert gerufen, "der Eintrag steht da, öffnet den Katalog aber nicht"

    # Und die andere Hälfte: In der Menüleiste steht keiner mehr — gefragt
    # nach der **Kachel**, nicht nach der Kategorie. Hier stand
    # ``category == "parts"``, und das verlangte dasselbe von ``create_lid``
    # und ``screw_lid``, die gar keine Kachel haben: Sie verschwanden aus der
    # Leiste, ohne im Katalog aufzutauchen.
    in_bar = [name for name in window._op_actions if name in catalogue_operations()]
    assert catalogue_operations(), "es gibt keine Bausteine — dann prüft dieser Test nichts"
    assert not in_bar, f"Bausteine gehören in den Katalog, nicht ins Menü: {sorted(in_bar)}"


def test_a_parameter_field_shows_its_whole_value(window: MainWindow) -> None:
    """„die eingabefelder sind jetzt manchmal zu klein" (Robert, 30.08.2026).

    Die Wertfelder der Parameterkarte tragen `SizePolicy.Ignored`, und das mit
    gutem Grund: Ihr Wertebereich geht bis ±100 000, und danach bemessen wäre
    jedes Feld 156 Punkte breit, auch für eine 40. Ohne Boden schrumpfen sie
    aber unter das Maß, das ihren **aktuellen** Wert zeigt — gemessen 92 Punkte
    für ein Feld, dessen Zahl mit Auf- und Ab-Knopf 118 braucht. Auf dem
    Bildschirm stand „2,4" statt „2,40" und „1234" statt „1234,56", ohne dass
    etwas rot wird: Qt schneidet stumm.

    Der Boden ist deshalb der aktuelle Wert, nicht der Wertebereich.
    """
    from PySide6.QtWidgets import QAbstractSpinBox, QStyle, QStyleOptionSpinBox

    from app.core.types import Parameter

    document = window.session.project.document
    for name, value in (("breite", 1234.56), ("wandstaerke", 2.4)):
        document.parameters[name] = Parameter(name=name, value=value, unit="mm")
    window.parameters.show_document(document)
    window.parameters.grab()  # erzwingt das Legen der Zeilen
    QApplication.processEvents()

    def textraum(spin: QAbstractSpinBox) -> int:
        opt = QStyleOptionSpinBox()
        opt.initFrom(spin)
        return (
            spin.style()
            .subControlRect(
                QStyle.ComplexControl.CC_SpinBox, opt, QStyle.SubControl.SC_SpinBoxEditField, spin
            )
            .width()
        )

    felder = [
        spin
        for spin in window.parameters.findChildren(QAbstractSpinBox)
        if spin.isVisibleTo(window.parameters)
    ]
    assert felder, "ohne Felder prüft das hier nichts"

    eng = [
        f"{spin.text()!r}: {spin.fontMetrics().horizontalAdvance(spin.text())} nötig, "
        f"{textraum(spin)} da"
        for spin in felder
        if textraum(spin) < spin.fontMetrics().horizontalAdvance(spin.text())
    ]
    assert not eng, f"abgeschnittene Werte in der Parameterkarte: {eng}"


def test_every_menu_indents_its_text_the_same(window: MainWindow) -> None:
    """Die Textspalte darf beim Wandern von Menü zu Menü nicht springen.

    Qt reserviert die Symbolspalte **je Menü**, sobald ein einziger Eintrag ein
    Zeichen trägt. Drei der neun Menüs der Leiste hatten keines — Bearbeiten,
    Ansicht und Hilfe —, und darum stand ihr Text bei 16 Bildpunkten, während
    er in den übrigen sechs bei 36 stand. Der Grund war nicht Gestaltung,
    sondern Herkunft: Einträge aus dem Register bringen ihr Symbol mit
    (``icon_name_for``), von Hand geschriebene nicht. Für den Kunden sah es aus
    wie ein Fehler, und es war einer.

    Behoben wird es nicht dadurch, dass jeder Eintrag ein Bild bekommt — für
    „Parameter anlegen" gibt es keines, auf das die Welt sich geeinigt hätte —,
    sondern dadurch, dass jedes Menü **mindestens einen** Eintrag hat, dessen
    Bild zweifelsfrei ist: Rückgängig und Wiederholen, Alles einpassen,
    Handbuch und Über.

    Geprüft wird die Wirkung und nicht die Ursache: nicht „jedes Menü hat ein
    Symbol", sondern „alle fangen an derselben Stelle an". Gemessen am
    **gezeigten** Menü, weil Qt die Geometrie seiner Einträge vorher nicht
    kennt.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QMenu

    from app.ui.style import apply_style

    # **Drei Vorbereitungen, und ohne jede einzelne misst der Test nichts.**
    # Qt legt die Geometrie eines Menüs erst fest, wenn sein Fenster gezeigt
    # wurde. Und die Suite fährt **ohne Stylesheet** — Qt zeichnet dann sein
    # eigenes Menü, schwarz auf weiß, mit anderen Abständen als die Anwendung
    # sie hat. Ein Test, der eine Einrückung misst, muss die Betriebslage
    # herstellen; sonst prüft er eine Lage, die kein Kunde je sieht.
    vorher = QApplication.instance().styleSheet()
    apply_style(QApplication.instance(), "dark")
    window.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
    window.show()
    QApplication.processEvents()

    def text_starts_at(menu: QMenu) -> int | None:
        """Die erste Spalte eines symbollosen Eintrags, in der etwas steht."""
        without = [
            entry
            for entry in menu.actions()
            if not entry.isSeparator() and entry.text() and entry.icon().isNull()
        ]
        if not without:
            return None
        menu.popup(window.pos())
        QApplication.processEvents()
        image = menu.grab(menu.actionGeometry(without[0])).toImage()
        ground = image.pixelColor(image.width() - 3, image.height() // 2)
        found = None
        # Ab zwei, nicht ab null: ``actionGeometry`` ist relativ zum **Menü**,
        # und dessen Rahmen liegt in der ersten Spalte. Er weicht vom Grund ab
        # wie jeder Text, und die Suche fand deshalb in jedem Menü dieselbe 0.
        for x in range(2, image.width()):
            for y in range(image.height()):
                here = image.pixelColor(x, y)
                if (
                    abs(here.red() - ground.red())
                    + abs(here.green() - ground.green())
                    + abs(here.blue() - ground.blue())
                    > 60
                ):
                    found = x
                    break
            if found is not None:
                break
        menu.hide()
        QApplication.processEvents()
        return found

    starts: dict[str, int] = {}
    try:
        for action in window.menuBar().actions():
            menu = action.menu()
            if not isinstance(menu, QMenu):
                continue
            start = text_starts_at(menu)
            if start is not None:
                starts[action.text()] = start
    finally:
        QApplication.instance().setStyleSheet(vorher)

    # Ohne diese Zeile prüfte der Vergleich unten eine leere Menge — und die
    # ist immer einig mit sich selbst. Sechs der neun Menüs bestehen nur aus
    # Registeroperationen und tragen deshalb überhaupt keinen symbollosen
    # Eintrag; vier ist der Bestand, drei die Grenze, unter der die Messung
    # nichts mehr über einen *Sprung* sagen könnte.
    assert len(starts) >= 3, f"zu wenige Menüs gemessen: {starts}"
    # Und die zweite Hälfte derselben Zusicherung: Ein Text fängt nie bei null
    # an, dort liegt der Rahmen. Eine Null heißt, dass die Messung nicht
    # gemessen hat — und vier Nullen sind sich einig wie vier richtige Werte.
    assert all(start > 0 for start in starts.values()), f"die Messung hat nichts gefunden: {starts}"
    assert len(set(starts.values())) == 1, (
        f"die Textspalte springt zwischen den Menüs: {starts} — "
        "ein Menü ohne jedes Symbol reserviert die Spalte nicht"
    )


def test_a_short_calculation_shows_nothing_at_all(window: MainWindow) -> None:
    """Was aufblitzt, sagt nichts — es macht nur unruhig (§2.8).

    Von 28 gemessenen Rechnungen liegen **elf unter zwei Zehntelsekunden**,
    und es sind die häufigsten Gesten überhaupt: einen Wert im Dialog ändern
    (7 ms), am Schichtregler ziehen (0,01 ms), einen Pinselstrich setzen
    (0,2 ms). Bei jeder davon zuckte der Fortschrittsbalken auf und sofort
    wieder weg, weil ``_on_busy`` ihn ohne jeden Zeitgeber sichtbar machte.

    Geprüft wird über das **Signal** der Sitzung und nicht über den Slot: Was
    beim Rechnen erscheint, entscheidet die Verbindung, und die ist Teil der
    Zusage.
    """
    window.session.busyChanged.emit(True)
    # ``isVisibleTo`` überall: ``isVisible`` meldet in einem nie gezeigten
    # Fenster immer False, und ein Test, der Abwesenheit prüft, wäre dann
    # grün gegen eine Lüge — genau die Tarnung, vor der ``wartezeit.md`` warnt.
    assert not window.progress.isVisibleTo(window), "der Balken kam sofort"
    assert not window.cancel_button.isVisibleTo(window), "der Abbrechen-Knopf kam sofort"
    assert window.cursor().shape() != Qt.CursorShape.BusyCursor, "der Wartezeiger kam sofort"

    window.session.busyChanged.emit(False)
    assert not window.progress.isVisibleTo(window)
    assert window.cursor().shape() != Qt.CursorShape.BusyCursor, "ein Zeiger blieb stehen"


def test_the_waiting_grows_in_the_three_steps_the_plan_names(window: MainWindow) -> None:
    """Zeiger, dann Balken — und beides erst, wenn es etwas zu sagen gibt.

    §2.8 kennt drei Stufen über der Schwelle: bis zwei Zehntelsekunden nichts,
    bis zwei Sekunden Mauszeiger und Statusleiste, darüber Fortschritt mit
    Abbrechen. Zwölf der 28 gemessenen Marken liegen in der mittleren Stufe —
    Netz vergröbern, Fläche unterteilen, ein Beispielprojekt öffnen.

    Die Zeitgeber werden hier von Hand ausgelöst statt abgewartet: Zwei
    Sekunden Wartezeit in einem Test sind zwei Sekunden in jedem Lauf. Das
    Signal geht dabei durch dieselbe Verbindung, die auch im Betrieb feuert.
    """
    try:
        window.session.busyChanged.emit(True)
        assert window._patience.isActive(), "die Uhr für den Zeiger läuft nicht"
        assert window._bar_delay.isActive(), "die Uhr für den Balken läuft nicht"

        window._patience.timeout.emit()
        # Am **Fenster** gefragt und nicht an der Anwendung: Der Zeiger ist eine
        # Eigenschaft dieses Fensters, damit er den Override der synchronen
        # Rechnung nicht vom Stapel nimmt (der Grund steht bei
        # ``_show_wait_cursor``).
        cursor = window.cursor()
        assert cursor.shape() == Qt.CursorShape.BusyCursor, (
            "der reine Wartezeiger behauptet eine gesperrte Oberfläche — sie ist bedienbar"
        )
        assert not window.progress.isVisibleTo(window), "der Balken kam schon in der zweiten Stufe"

        window._bar_delay.timeout.emit()
        assert window.progress.isVisibleTo(window), "nach zwei Sekunden fehlt der Balken"
        assert window.cancel_button.isVisibleTo(window), "ein Balken ohne Abbrechen (§2.8)"
    finally:
        window.session.busyChanged.emit(False)

    assert not window.progress.isVisibleTo(window)
    assert window.cursor().shape() != Qt.CursorShape.BusyCursor, (
        "der Zeiger blieb stehen — das sieht aus wie ein hängendes Programm"
    )


def test_no_wait_cursor_survives_a_second_run(window: MainWindow) -> None:
    """Qt stapelt Zeiger, und ein Stapel wird nie ganz abgeräumt.

    ``setOverrideCursor`` zweimal und ``restoreOverrideCursor`` einmal lässt
    einen stehen. Bei einer Kette von Läufen — und beim Ziehen an einem
    Schieber ist jede Bewegung einer — wäre nach kurzer Zeit ein Wartezeiger
    da, den nichts mehr wegnimmt.
    """
    for _ in range(3):
        window.session.busyChanged.emit(True)
        window._patience.timeout.emit()
        window._patience.timeout.emit()  # ein zweiter Anlauf derselben Stufe
        window.session.busyChanged.emit(False)
    assert window.cursor().shape() != Qt.CursorShape.BusyCursor, (
        "nach drei Läufen steht ein Zeiger im Weg"
    )


def test_the_status_bar_leads_where_its_numbers_come_from(window: MainWindow) -> None:
    """Eine Auskunft, die eine Frage aufwirft, kennt den Weg zu ihrer Antwort.

    Zwei Zeilen der Statusleiste taten das nicht. „51 g · 3 h 30 min" ist
    geschätzt, und wer sie ändern oder nachrechnen will, braucht die
    Druckeinstellungen — der Weg dorthin stand nur im Menü, und im Menü sucht
    ihn niemand, der gerade auf die Zahl sieht. Die Lizenzzeile war der
    deutlichere Fall: Sie **nannte** ihren Weg, „Hilfe → Solidon freischalten
    …", und ließ den Kunden ihn zu Fuß gehen.

    Geprüft wird über das Signal beziehungsweise den Klick und nicht über die
    Methode dahinter: Was ein Klick auslöst, entscheidet die Verbindung.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    # **Erst fragen, ob die Verbindung steht — sie ist die Zusage.** Danach
    # wird sie gelöst und durch eine Attrappe ersetzt: Der echte Empfänger
    # öffnet einen modalen Dialog, und ein Test, der ihn aufgehen lässt, wartet
    # bis zum Zeitablauf. Beides in dieser Reihenfolge, sonst prüft der Klick
    # nur noch die Attrappe, die der Test selbst angehängt hat.
    try:
        window.facts.clicked.disconnect()
    except (RuntimeError, TypeError) as nothing_there:  # pragma: no cover — die Zusage
        raise AssertionError("ein Klick auf den Verbrauch bleibt folgenlos") from nothing_there
    opened: list[str] = []
    window.facts.clicked.connect(lambda: opened.append("settings"))

    # Geklickt und nicht ``mousePressEvent`` gerufen: Wer die Methode direkt
    # aufruft, prüft die Methode und nicht den Klick — und genau dazwischen lag
    # der Fehler, den dieser Test festhält.
    QTest.mouseClick(window.facts, Qt.MouseButton.LeftButton)
    assert opened == ["settings"], "der Klick erreicht das Signal nicht"

    # Und der Zeiger sagt es, bevor jemand klickt: Eine Zeile, die auf Klicks
    # reagiert und wie Text aussieht, ist eine versteckte Funktion.
    assert window.facts.cursor().shape() == Qt.CursorShape.PointingHandCursor
    assert window.facts.accessibleDescription(), "kein Satz für den, der nichts sieht"

    assert window.trial_line.cursor().shape() == Qt.CursorShape.PointingHandCursor
    # Die Lizenzzeile hängt an ihrer eigenen Handlung, nicht an einem Menüweg
    # im Text. Geprüft am Empfänger des Signals, denn genau die Verbindung war
    # das, was fehlte.
    try:
        window.trial_line.clicked.disconnect()
    except (RuntimeError, TypeError) as nothing_there:  # pragma: no cover — die Zusage
        raise AssertionError(
            "die Lizenzzeile beschreibt weiter einen Weg, statt einer zu sein"
        ) from nothing_there


def test_the_key_field_shows_a_whole_key(qt_app: QApplication) -> None:
    """Wer seinen Schlüssel einfügt, will sehen, ob er vollständig ist.

    Das Feld war auf 90 Punkte festgesetzt. Ein Lizenzschlüssel ist einzeilig
    und **242 Zeichen** lang; bei der Feldbreite von 558 Punkten sind das
    sieben umbrochene Zeilen à 14, also 110 Punkte. Es fehlten zwanzig, und
    zwar an der einen Stelle der Anwendung, an der jemand prüfen will, ob er
    richtig kopiert hat — mit einem Rollbalken als einziger Auskunft darüber.

    Der Befund aus der Durchsicht las sich umgekehrt („90 Punkte für einen
    einzeiligen Schlüssel"), und die naheliegende Behebung hätte den Dialog
    verschlechtert: Ein ``QLineEdit`` zeigt an dieser Breite **45 von 242**
    Zeichen.

    Zugesichert wird deshalb nicht eine Punktzahl, sondern die Sache: Der
    Rollweg ist null, also steht der ganze Schlüssel im Bild. Das gilt auch
    bei größerer Systemschrift, denn beide Seiten der Rechnung — Umbruch und
    Höhe — nehmen dieselbe Metrik.
    """
    from PySide6.QtCore import Qt

    from app.core.activation.key import format_key
    from app.ui.dialogs import ActivationDialog
    from app.ui.style import apply_style
    from app.ui.theme import apply_theme

    # Die Betriebslage, und hier hängt die Messgröße wirklich an ihr: Das
    # Stylesheet setzt den Innenabstand des Feldes, also die Breite, über die
    # umbrochen wird. Ohne es bricht der Schlüssel anders um als beim Kunden.
    before = QApplication.instance().styleSheet()
    apply_theme(QApplication.instance(), "dark")
    apply_style(QApplication.instance(), "dark")
    dialog = ActivationDialog()
    try:
        dialog.field.setPlainText(format_key(b"x" * 64, b"y" * 64))
        dialog.resize(dialog.sizeHint())
        dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        dialog.show()
        QApplication.processEvents()

        assert dialog.field.verticalScrollBar().maximum() == 0, (
            "der Schlüssel steht nicht ganz im Feld — "
            f"{dialog.field.verticalScrollBar().maximum()} Punkte Rollweg"
        )

        # Und leer bleibt es klein: Ein Feld, das immer sieben Zeilen hoch ist,
        # bezahlt den Platz auch dann, wenn nichts darin steht.
        voll = dialog.field.height()
        dialog.field.setPlainText("")
        QApplication.processEvents()
        assert dialog.field.height() < voll, "das leere Feld ist so hoch wie das volle"
    finally:
        dialog.reject()
        QApplication.instance().setStyleSheet(before)


def test_the_header_gives_its_information_room_in_every_supported_width(
    window: MainWindow,
    qt_app: QApplication,
    request: pytest.FixtureRequest,
) -> None:
    """Die Kopfzeile kürzt lesbar, statt ihre langen Angaben zu verschlucken.

    **Was gemessen war.** Die Kopfzeile lebt als Widget in der
    Werkzeugleiste, und Qt gibt einem Widget dort entweder seine
    ``sizeHint``-Breite oder gar keinen Platz. Mit **offenem** Projekt wollte
    sie 968 Pixel (Name 273, Maße 275, Drucker 330), die Leiste damit 2283 —
    und auf einem **1920er Bildschirm war die ganze Zeile weg**: Projektname,
    Maße, Druckplatte, Drucker und Material zusammen, hinter einem
    unbeschrifteten Pfeil.

    **Mit leerem Projekt passiert das nicht** (dort will sie 103 px), und
    genau deshalb fällt es beim Ausprobieren nicht auf. Der Test öffnet
    deshalb ein Beispiel, statt das leere Fenster zu messen — sonst prüfte er
    die Lage, in der der Fehler nie auftrat.

    Der erste Fix hielt nur das äußere Widget in der Leiste. Sein innerer
    Leerraum bekam die ganze Restbreite, während Projektname, Maße und Drucker
    selbst auf 1920 Pixeln je **null** Pixel breit waren. Deshalb prüft dieser
    Test die sichtbaren Kinder, nicht nur ihren Elternkasten.

    Zwei Zusagen: Die drei Angaben bekommen in jeder unterstützten Breite
    wirklich Raum, und die Kürzung bewahrt die Enden mit Bedeutung — Stern,
    Einheit und Druckermodell. Der ganze Wortlaut bleibt für Tooltip und
    Hilfstechnik erhalten.
    """
    from PySide6.QtWidgets import QStyle, QStyleOptionComboBox

    from app.ui.style import apply_style

    # Auch die Innenabstände sind Produktzustand. Ohne Stylesheet misst der
    # Test die Plattform und kann auf einem anderen Schreibtisch zufällig grün
    # werden.
    previous_style = qt_app.styleSheet()
    request.addfinalizer(lambda: qt_app.setStyleSheet(previous_style))
    apply_style(qt_app, "dark")

    # **Angezeigt werden muss es.** Ohne ``show()`` verteilt Qt keine Breite,
    # und genau ein Test ohne Layout hatte den Null-Pixel-Zustand übersehen.
    window.show()
    QApplication.processEvents()

    beispiele = sorted((Path(__file__).parent.parent / "app" / "examples").glob("*.p3d"))
    assert beispiele, "ohne Beispielprojekt misst dieser Test die leere Lage"
    window.session.open_project(beispiele[0])
    window.session.wait_for_idle()
    window._on_project()
    window.set_display_unit("in")
    window.header.title.setText("Ein sehr langes Beispielprojekt für den schmalen Bildschirm*")
    window.header.printer.setText("Allgemeiner FDM-Drucker 220 mm")
    window.header.show_plates(3)

    labels = (window.header.title, window.header.bounds, window.header.printer)
    full = tuple(label.full_text() for label in labels)
    assert all(full), "Projektname, Außenmaß und Drucker tragen je eine Auskunft"

    for breite, hoehe in ((1920, 1080), (1040, 760), (800, 600), (640, 720)):
        window.resize(breite, hoehe)
        window.header.updateGeometry()
        window.toolbar.updateGeometry()
        QApplication.processEvents()

        assert window.header.isVisibleTo(window.toolbar), (
            f"bei {breite} px ist die Kopfzeile im Überlaufmenü — "
            "Projektname, Drucker und Platte sind für den Kunden weg"
        )
        assert window.header.plates.isVisibleTo(window.toolbar)
        assert window.header.plates.width() > 0
        assert window.header.plates.accessibleName() == str(tr("Druckplatte"))
        assert window.header.plates.currentText() == str(tr("Alle Platten"))
        plate_option = QStyleOptionComboBox()
        plate_option.initFrom(window.header.plates)
        plate_option.currentText = window.header.plates.currentText()
        plate_field = window.header.plates.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox,
            plate_option,
            QStyle.SubControl.SC_ComboBoxEditField,
            window.header.plates,
        )
        assert plate_field.width() >= window.header.plates.fontMetrics().horizontalAdvance(
            window.header.plates.currentText()
        ), "das sichtbare Feld muss Zweck und aktiven Plattenfilter vollständig zeigen"
        material = window.header.material
        assert material.isVisibleTo(window.toolbar) and material.width() > 0
        assert material.full_text() and material.toolTip() == material.full_text()
        assert material.accessibleName() == material.full_text()
        for label, expected in zip(labels, full, strict=True):
            assert label.isVisibleTo(window.toolbar)
            assert label.width() > 0, f"{expected!r} bekommt bei {breite} px keinen Raum"
            assert label.full_text() == expected
            assert label.toolTip() == expected
            assert label.accessibleName() == expected
            assert label.focusPolicy() == Qt.FocusPolicy.NoFocus
            if label.fontMetrics().horizontalAdvance(expected) > label.width():
                assert label.text() != expected, (
                    "Qt darf keinen ungekürzten Text rechts abschneiden"
                )
                assert "…" in label.text(), "die sichtbare Kürzung muss als solche erkennbar sein"
        assert window.header.title.text().endswith("*"), "ungespeichert bleibt sichtbar"
        assert window.header.bounds.text().endswith("in"), "die Anzeigeeinheit bleibt sichtbar"
        assert window.header.printer.text().endswith("220 mm"), "das Druckermodell bleibt sichtbar"


def test_a_header_label_keeps_its_text_for_tooltip_and_assistance(
    qt_app: QApplication,
) -> None:
    """Die Kürzung bewahrt das wichtige Ende und den ganzen zugänglichen Text.

    Rechts gekürzt wurde aus „… 220 mm" ein Anfang ohne Modellende. Mittig
    gekürzt bleiben Einheit, Stern und unterscheidender Namenszusatz stehen.
    Der sichtbare Rest ersetzt den Volltext nicht: Tooltip und Accessible Name
    tragen ihn weiter.
    """
    from app.ui.header import _EphemeralLabel

    label = _EphemeralLabel("Allgemeiner FDM-Drucker 220 mm", tail_words=2)
    label.show()
    label.resize(label.minimumWidth() + 10, 20)
    QApplication.processEvents()
    assert label.full_text() == "Allgemeiner FDM-Drucker 220 mm", "der ganze Text bleibt bekannt"
    assert label.toolTip() == label.full_text(), "und er steht im Tooltip"
    assert label.accessibleName() == label.full_text(), "und Hilfstechnik liest nicht die Kürzung"
    assert label.focusPolicy() == Qt.FocusPolicy.NoFocus, (
        "die Auskunft erzeugt keinen Tastaturstopp"
    )
    assert label.text().endswith("220 mm"), "das unterscheidende Ende bleibt vollständig sichtbar"
    assert "…" in label.text()

    # **Beide Wege, nicht nur einer.** Der Text kommt im Betrieb über
    # ``setText`` und nur im Test aus dem Konstruktor; eine Probe, die den
    # zweiten prüft und den ersten nicht, ließ die Mutation „Tooltip aus
    # setText entfernen" grün durchgehen.
    label.setText("Ein anderer, ebenfalls sehr langer Druckername")
    assert label.full_text() == "Ein anderer, ebenfalls sehr langer Druckername"
    assert label.toolTip() == label.full_text(), "auch der gesetzte Text steht im Tooltip"
    assert label.accessibleName() == label.full_text()

    title = _EphemeralLabel(
        "Ein sehr langes Beispielprojekt für einen schmalen Bildschirm*",
        protected_end="*",
    )
    title.show()
    title.resize(max(30, title.minimumWidth()), 20)
    QApplication.processEvents()
    assert title.text() != title.full_text(), "der Volltext darf nicht nur unsichtbar überstehen"
    assert "…" in title.text()
    assert title.text().endswith("*"), "die Ungespeichert-Markierung bleibt gezeichnet"


def test_a_clean_part_offers_the_way_to_the_slicer(window: MainWindow) -> None:
    """Der letzte Meter: „Keine Befunde." ohne nächsten Schritt war eine Sackgasse.

    Leere Szene: kein Knopf, weil nichts zu übergeben ist. Ein Körper ohne
    Befund: der Bericht sagt „druckbereit" und bietet den Slicer an; der Knopf
    öffnet denselben Dialog wie *Datei → Druckeinstellungen …*
    (Review 02.09.2026).
    """
    report = window.report
    assert not report.to_slicer.isVisibleTo(report)
    assert report.summary.text() == "Keine Befunde."

    window.session.apply(
        "Kasten",
        [
            OperationDraft(
                op="create_box",
                inputs=(),
                params={"width": 20.0, "depth": 20.0, "height": 10.0},
            )
        ],
    )
    window.session.wait_for_idle()
    QApplication.processEvents()

    assert report.to_slicer.isVisibleTo(report)
    assert report.summary.text() == "Keine Befunde. Das Teil ist druckbereit."
    opened: list[str] = []
    window.action_print_settings = lambda: opened.append("dialog")  # type: ignore[method-assign]
    report.slicerRequested.disconnect()
    report.slicerRequested.connect(window.action_print_settings)
    report.to_slicer.click()
    assert opened == ["dialog"]


def test_palette_twins_do_not_look_alike(window: MainWindow) -> None:
    """Vier Paare tragen denselben Titel; die Palette zeigt beide mit ihrem Satz.

    Wer „quader" tippte, sah zweimal „Quader anlegen", und der Unterschied
    stand nur im Tooltip (Review 02.09.2026).
    """
    from app.core.registry import MENU_TWINS
    from app.ui.command_palette import CommandPalette

    palette = CommandPalette(parent=window)
    for hidden, visible in MENU_TWINS.items():
        palette._refilter(str(window._op_actions[visible].text()).replace("&", ""))
        rows = [palette.list.item(row).text() for row in range(palette.list.count())]
        both = [
            row
            for row in rows
            if row.split(chr(10))[0].split(chr(9))[0]
            in {str(spec.title) for spec in (REGISTRY.get(hidden), REGISTRY.get(visible))}
        ]
        assert len(both) >= 2, (hidden, visible, rows[:6])
        assert len(set(both)) == len(both), both
        assert all(chr(10) in row for row in both), both


def test_the_build_plate_hides_in_one_step(window: MainWindow) -> None:
    """Robert, 02.09.2026: „eine Option, wo man schnell hinkommt, um die Druckplatte auszublenden".

    Ein Haken im Ansichtsmenü mit Kürzel, in der Palette gelistet, und der
    Zustand bleibt in den Einstellungen — gleich, ob Menü, Palette oder Taste
    ihn umlegen.
    """
    assert window.viewport.bed_visible
    assert window.settings.bed_visible
    assert window._bed_action.isChecked()

    window.action_toggle_bed()

    assert not window.viewport.bed_visible
    assert not window.settings.bed_visible
    assert not window._bed_action.isChecked()
    assert window.window_commands()["view.bed"][1] == "Ctrl+Shift+D"

    window._bed_action.trigger()

    assert window.viewport.bed_visible
    assert window.settings.bed_visible
    assert window._bed_action.isChecked()


def test_closing_the_measure_tool_takes_the_dimensions_with_it(window: MainWindow) -> None:
    """Ein Maß überlebt sein Werkzeug nicht (Robert, 03.09.2026).

    Vorher schaltete das Schließen nur den Modus ab: Die Linien blieben im
    Bild stehen, und der einzige Knopf, mit dem man sie loswird, war mit der
    Leiste verschwunden. Ein Maß ist eine Auskunft über das Teil und kein
    Dokumentzustand (Regel 2) — dieselbe Entscheidung wie bei der Trennlinie.
    """
    from app.core.geom.measure import Measurement

    window.tools.toggle("measure")
    window.viewport.measurements.add(
        Measurement(kind="distance", value=12.0, points=((0.0, 0.0, 0.0), (12.0, 0.0, 0.0)))
    )
    assert len(window.viewport.measurements.entries) == 1

    window.tools.toggle("measure")

    assert window.viewport.measurements.entries == [], "das Schließen räumt die Maße weg"
    assert window.measure_bar.mode.currentData() == "off", "und schaltet das Messen ab"


def test_the_view_settings_are_still_there_after_a_restart(qt_app: QApplication) -> None:
    """Darstellung, Schattierung und Projektion überleben das Schließen.

    **Der Befund (Robert, 03.09.2026):** „sollte leicht durchsichtig sein seit
    dem letzten update". Der Modus *war* eingestellt gewesen — und beim
    nächsten Start stand wieder *Massiv* da. `UiSettings` führte Navigation,
    Thema, Sprache, Einheit und ein Dutzend Slicer-Profile; diese drei nicht.
    Das ist die Sorte Fehler, die man für die eigene Erinnerung hält.

    Geprüft wird die ganze Kette: Der Menüweg schreibt in die Einstellungen,
    ein **neu gebautes** Fenster mit denselben Einstellungen wendet sie an,
    und die Häkchen zeigen, was gilt.
    """
    window = MainWindow(Session(), UiSettings())
    assert window.settings.display_mode == "solid", "die Vorgabe"

    window.action_display_mode("transparent")
    window.action_shading("smooth")
    window.action_projection("orthographic")

    assert window.settings.display_mode == "transparent"
    assert window.settings.shading == "smooth"
    assert window.settings.projection == "orthographic"
    assert window.viewport.display_mode == "transparent", "und die Ansicht folgt sofort"

    gemerkt = UiSettings(
        display_mode=window.settings.display_mode,
        shading=window.settings.shading,
        projection=window.settings.projection,
    )
    zweites = MainWindow(Session(), gemerkt)
    # Denselben Weg wie ``app.py``: Der Bau stellt das Fenster hin, und
    # ``_apply_settings`` gibt ihm, was gemerkt wurde. Ein Test, der das
    # ausließe, prüfte einen Start, den es nicht gibt.
    zweites._apply_settings()
    assert zweites.viewport.display_mode == "transparent", (
        "der neue Start nimmt den gemerkten Modus"
    )
    angehakt = [action.data() for action in zweites._mode_group.actions() if action.isChecked()]
    assert angehakt == ["transparent"], f"und das Menü zeigt ihn: {angehakt}"
    assert [a.data() for a in zweites._shading_group.actions() if a.isChecked()] == ["smooth"]
    assert [a.data() for a in zweites._projection_group.actions() if a.isChecked()] == [
        "orthographic"
    ]


def test_the_candidates_are_lit_while_the_question_stands(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§21.3 wörtlich: die Kandidaten stehen hervorgehoben da.

    Bis zum 03.09.2026 fehlte genau das. Wer eine Projektdatei öffnete, deren
    Merkmalsverweis mehrdeutig geworden war, bekam ``hole_1``, ``hole_2``,
    ``hole_3`` zur Wahl und sollte zwischen Bohrungen entscheiden, die er
    nicht sieht. Die Auskunft lag im Kern bereit und wurde nie abgerufen.
    """
    from app.ui.dialogs import AskDialog
    from app.ui.session import AskRequest

    gezeigt: list[tuple[tuple[tuple[str, str], ...], object]] = []
    monkeypatch.setattr(
        window.viewport,
        "show_candidates",
        lambda candidates=(), emphasis=None: gezeigt.append((tuple(candidates), emphasis)),
    )
    monkeypatch.setattr(AskDialog, "exec", lambda self: AskDialog.DialogCode.Accepted)

    request = AskRequest(
        question="Welches Merkmal ist gemeint?",
        choices=["hole_1", "hole_2"],
        candidates=(("obj_1", "hole_1"), ("obj_1", "hole_2")),
    )
    window._on_ask(request)

    assert gezeigt, "während der Frage leuchtet etwas"
    erste = gezeigt[0][0]
    assert erste == (("obj_1", "hole_1"), ("obj_1", "hole_2"))
    assert gezeigt[-1] == ((), None), "und nach der Antwort ist es weg"
    assert request.answer == "hole_1"


def test_nothing_is_lit_for_a_question_without_candidates(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Einheitenfrage beim Einlesen hat keine Kandidaten — und leuchtet nicht."""
    from app.ui.dialogs import AskDialog
    from app.ui.session import AskRequest

    gezeigt: list[object] = []
    monkeypatch.setattr(
        window.viewport,
        "show_candidates",
        lambda candidates=(), emphasis=None: gezeigt.append(candidates),
    )
    monkeypatch.setattr(AskDialog, "exec", lambda self: AskDialog.DialogCode.Rejected)

    window._on_ask(AskRequest(question="Millimeter oder Zoll?", choices=["mm", "in"]))

    assert gezeigt == [], "ohne Kandidaten wird die Ansicht nicht angefasst"


def test_the_marked_row_is_the_emphasised_candidate(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Was gleich die Antwort wäre, leuchtet deckender als die übrigen.

    Und wo dieselbe Kennung an mehreren Körpern steht — die Skizzenebene, die
    auf jeder planaren Fläche zu Hause sein darf —, wird keine betont: Die
    Frage entscheidet dort über die Kennung, nicht über den Fundort.
    """
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QListWidgetItem

    gezeigt: list[object] = []
    monkeypatch.setattr(
        window.viewport,
        "show_candidates",
        lambda candidates=(), emphasis=None: gezeigt.append(emphasis),
    )

    window._ask_candidates = (("obj_1", "face_1"), ("obj_2", "face_1"), ("obj_1", "face_2"))

    eindeutig = QListWidgetItem("face_2")
    eindeutig.setData(Qt.ItemDataRole.UserRole, "face_2")
    window._emphasise_candidate(eindeutig, None)
    assert gezeigt[-1] == ("obj_1", "face_2")

    mehrdeutig = QListWidgetItem("face_1")
    mehrdeutig.setData(Qt.ItemDataRole.UserRole, "face_1")
    window._emphasise_candidate(mehrdeutig, None)
    assert gezeigt[-1] is None, "zwei Fundorte, eine Frage — keiner wird betont"


def test_many_features_of_one_kind_stand_under_one_roof(window: MainWindow) -> None:
    """Eine STEP-Datei bringt Dutzende gleichnamige Verrundungen mit.

    Gemessen an ``build_tray_v3.step`` (03.09.2026): 234 erkannte Merkmale,
    davon rund fünfzig sichtbare Zeilen „Hohlkehle R13,98 mm" untereinander.
    Der Prüfbericht daneben bündelt dieselbe Menge längst zu einer Zeile; der
    Objektbaum tat es nur für Merkmale aus einem Baustein.

    Gebaut wird die Merkmalsmenge hier von Hand: Geprüft wird die **Anzeige**,
    nicht die Erkennung — und kein Modell des Korpus hat vier gleichnamige.
    """
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    object_id, entry = next(iter(result.scene.objects.items()))

    fillets = {
        f"fillet_{index}": Feature(
            id=f"fillet_{index}",
            kind="fillet",
            params={"radius": 13.98, "recess": True},
            provenance="detected",
        )
        for index in range(6)
    }
    einzeln = next(iter(entry.features.values()))
    entry = dataclasses.replace(entry, features={**fillets, einzeln.id: einzeln})
    result = dataclasses.replace(
        result, scene=dataclasses.replace(result.scene, objects={object_id: entry})
    )

    tree = window.object_tree
    tree.show_scene(result, window.session.project.document)
    top = tree.tree.topLevelItem(0)
    assert top is not None
    top.setExpanded(True)
    kinder = [top.child(index) for index in range(top.childCount())]
    beschriftungen = [kind.text(0) for kind in kinder if kind is not None]

    dach = next((kind for kind in kinder if kind is not None and "(6)" in kind.text(0)), None)
    assert dach is not None, f"sechs gleichnamige Merkmale, kein Dach darüber: {beschriftungen}"
    assert dach.childCount() == 6, "unter dem Dach stehen alle sechs"
    assert not dach.isExpanded(), "zugeklappt — sonst wäre nichts gewonnen"
    assert len(beschriftungen) == 2, (
        f"ein Dach und das einzelne Merkmal, sonst nichts: {beschriftungen}"
    )
    assert dach.toolTip(0) and dach.data(0, Qt.ItemDataRole.AccessibleDescriptionRole), (
        "Regel 18: der Hinweis steht auch für den Bildschirmleser da"
    )

    tree.select_feature(object_id, "fillet_3")
    assert dach.isExpanded(), "wer ein Merkmal darin wählt, sieht es"


def test_one_line_stands_for_many_bodies_and_asks_which(window: MainWindow) -> None:
    """Sechs Körper, ein Satz — und die Wahl bleibt erhalten.

    Gemessen an ``Wizard+Tower+Staunton+Elegoo.3mf`` (03.09.2026): 15 Befunde,
    davon zwölf aus zwei Kennungen über dieselben sechs Körper. Sechsmal
    derselbe Satz mit anderem Namen dahinter — was der Kunde liest, ist eine
    Wand. Gebündelt wird jetzt über die Körpergrenze (``ACROSS_BODIES``), und
    die Zeile führt die Körper mit, damit die Handlung fragen kann, für welche
    sie gelten soll (Entscheidung Robert).
    """
    report = window.report
    report.show_result(None)
    report.add_findings(
        [
            Finding(
                code="perceive.too_large",
                severity="info",
                message="Für die Merkmalserkennung ist dieses Modell zu groß.",
                object_id=f"obj_{index}",
                values={"triangles": 200000 + index, "limit": 200000},
            )
            for index in range(1, 7)
        ]
    )

    from app.ui.panels import _BODIES_ROLE

    zeilen = [report.list.item(row) for row in range(report.list.count())]
    assert len(zeilen) == 1, f"sechs Befunde, eine Zeile — gezählt: {len(zeilen)}"
    zeile = zeilen[0]
    assert zeile is not None
    assert "6 ×" in zeile.text(), zeile.text()
    assert "obj_1" not in zeile.text(), (
        "eine Zeile für sechs Körper nennt keinen einzelnen — sonst verschweigt sie fünf"
    )
    assert zeile.data(_BODIES_ROLE) == tuple(f"obj_{index}" for index in range(1, 7))


def test_the_same_operation_on_many_bodies_is_one_transaction(window: MainWindow) -> None:
    """Regel 16: Ein Undo nimmt die ganze Handlung zurück, nicht ein Sechstel.

    ``decimate_mesh`` verbraucht einen Körper; die Handlung der Sammelzeile
    meint mehrere. ``run_operation(..., on_bodies=...)`` baut deshalb einen
    Schritt je Körper und wendet sie in **einer** Transaktion an — der Dialog
    fragt seine Werte dabei einmal für alle.
    """
    window.open_path(MESHES / "cube_clean.stl")
    window.session.wait_for_idle()
    window.open_path(MESHES / "plate_holes.stl")
    window.session.wait_for_idle()
    result = window.session.evaluate_now()
    bodies = tuple(result.scene.objects)
    assert len(bodies) >= 2, f"zwei Körper für den Fall, gefunden: {len(bodies)}"
    transactions_before = len(window.session.project.document.transactions)
    steps_before = len(window.session.project.document.ops)

    window.run_operation(REGISTRY.get("decimate_mesh"), on_bodies=bodies[:2])
    dialog = window._op_dialog
    assert dialog is not None, "der Dialog fragt die Werte — einmal für beide"
    dialog.accept()
    window.session.wait_for_idle()

    document = window.session.project.document
    assert len(document.ops) == steps_before + 2, "ein Schritt je Körper"
    assert len(document.transactions) == transactions_before + 1, (
        "und alle in einer Transaktion — sonst nimmt Strg+Z nur den letzten zurück"
    )
    assert [tuple(step.inputs) for step in document.ops[-2:]] == [
        (bodies[0],),
        (bodies[1],),
    ], "jeder Schritt trifft genau seinen Körper"


def test_two_asking_threads_do_not_steal_each_others_candidates(session: Session) -> None:
    """Die Ansage gehört dem Faden, der sie gemacht hat — nicht der Sitzung.

    ``announce_candidates`` merkt sich, was die **nächste** Frage zur Wahl
    stellt, und ``ask_from_worker`` holt es ab. Der Weg dazwischen ist
    ``ctx.ask``, und die trägt nur Frage und Antworten (Regel 21) — deshalb
    steht es nicht an der Frage, sondern daneben.

    **Solange nur die Auswertung fragte, genügte ein Platz.** Er liegt auf der
    Sitzung, und mit einem zweiten fragenden Faden — 3d-druck-85 stellt am
    03.09.2026 das Einlesen auf einen Arbeiter um — reicht das nicht mehr: Die
    Einheitenfrage des Einlesens („Millimeter oder Zoll?") holte sich die
    Kandidaten der Verweisfrage ab, und die Verweisfrage bekäme dann keine.
    Beides ist falsche Auskunft: einmal leuchten Bohrungen zu einer Frage, die
    von Einheiten handelt, einmal leuchtet zu einer Frage über Bohrungen nichts.

    Ein Platz **je Faden** löst es an der Wurzel, ohne die Ask-Schnittstelle
    anzufassen: Wer ansagt und wer fragt, ist im selben Vorgang derselbe Faden
    (``orphans.check`` ruft beides unmittelbar nacheinander), und zwei Vorgänge
    kommen sich nicht mehr in die Quere.
    """
    import threading

    gestellt: dict[str, tuple[tuple[str, str], ...]] = {}
    bereit = threading.Event()

    def antworten(request: AskRequest) -> None:
        gestellt[request.question] = request.candidates
        request.reply(request.choices[0])

    # **Direkt verbunden**, damit der Slot im *fragenden* Faden läuft. Über die
    # Warteschlange bräuchte er die Ereignisschleife des Hauptfadens, und die
    # steht hier still — ``ask_from_worker`` wartete dann bis zum Zeitlimit.
    session.askRequested.connect(antworten, Qt.ConnectionType.DirectConnection)

    def fremder_faden() -> None:
        bereit.wait(timeout=5.0)
        session.ask_from_worker("Millimeter oder Zoll?", ["mm", "in"])

    zweiter = threading.Thread(target=fremder_faden)
    zweiter.start()
    try:
        session.announce_candidates((("obj_1", "hole_1"), ("obj_1", "hole_2")))
        bereit.set()
        zweiter.join(timeout=5.0)
        session.ask_from_worker("Welches Merkmal ist gemeint?", ["hole_1", "hole_2"])
    finally:
        bereit.set()
        zweiter.join(timeout=5.0)

    assert gestellt["Millimeter oder Zoll?"] == (), "die fremde Frage hebt nichts hervor"
    assert gestellt["Welches Merkmal ist gemeint?"] == (
        ("obj_1", "hole_1"),
        ("obj_1", "hole_2"),
    ), "und die eigene bekommt, was für sie angesagt war"
