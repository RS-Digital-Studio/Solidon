"""Ein gesperrter Knopf nennt seinen Grund — über alle Dialoge, nicht über einen.

`oberflaeche.md` sagt es für Zeilen eines Dialogs: „Ist eine Zeile gesperrt,
tragen beide Hälften den *Grund* statt des Satzes." Für Knöpfe gilt dasselbe,
und bis zum 03.09.2026 stand die Zusage an genau einem Fenster
(`test_no_locked_button_in_this_dialog_stays_silent` in
`test_print_settings_ui.py`). Dort hat sie beim ersten Lauf **drei** stumme
Knöpfe gefunden, wo die Handmessung einen gesehen hatte — zwei davon im
häufigsten Fall überhaupt, einem Rechner ohne eingerichteten Slicer.

Ein Test je Dialog fängt den nächsten Dialog nicht. Deshalb hier eine Liste,
und wer einen Dialog dazunimmt, trägt ihn ein.

**Warum am gebauten Fenster und nicht am Quelltext:** Der schlimmste der drei
Funde stand im Quelltext richtig da — `self.slice_button.setToolTip(reason)`,
direkt unter dem `setEnabled`. Nur war `reason` in dem Zweig leer, der den
häufigsten Fall trifft. Eine Textsuche hätte ihn abgenickt.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QDialog, QMenu, QPushButton

from app.core import updates
from app.ui.changes_dialog import ChangesDialog
from app.ui.comfy_dialog import ComfySetupDialog
from app.ui.dialogs import (
    AboutDialog,
    ActivationDialog,
    DonationDialog,
    KeyDialog,
    OfflineActivationDialog,
)
from app.ui.filament_picker import NewFilamentDialog, SlicerFilamentDialog
from app.ui.first_run import FirstRunDialog
from app.ui.install_dialog import InstallDialog
from app.ui.main_window import MainWindow
from app.ui.print_disclosure import PrintDisclosureDialog
from app.ui.session import Session
from app.ui.settings import UiSettings
from app.ui.support_dialog import SupportDialog
from app.ui.update_dialog import UpdateDialog
from app.ui.variants_dialog import VariantsDialog

MESHES = Path(__file__).parent / "data" / "meshes"


def _release() -> updates.Release:
    """Eine Fassung, wie sie der Update-Weg vom Server bekommt."""
    return updates.Release(
        version="9.9.9",
        url="https://solidon3d.de/dl/Solidon3D-9.9.9.exe",
        notes="Der erste Punkt.\nDer zweite Punkt.",
    )


#: Wie jeder Dialog gebaut wird. Die Bauanleitungen stammen aus den Tests, die
#: es zu den einzelnen Fenstern schon gibt — zwei Aufbauten desselben Dialogs
#: laufen auseinander, sobald jemand an einem davon etwas ändert.
BUILDERS: dict[str, Callable[[Session], QDialog]] = {
    "SupportDialog": lambda _session: SupportDialog(
        message="Der Deckel sitzt schief.", error=ValueError("kaputt")
    ),
    "UpdateDialog": lambda _session: UpdateDialog(_release()),
    "ChangesDialog": lambda _session: ChangesDialog(),
    "AboutDialog": lambda _session: AboutDialog(),
    "DonationDialog": lambda _session: DonationDialog(),
    "NewFilamentDialog": lambda _session: NewFilamentDialog(
        name="Werkstattrolle", colour="#123456", material_type="PETG"
    ),
    "VariantsDialog": lambda session: VariantsDialog(session),
    "KeyDialog": lambda _session: KeyDialog(settings=UiSettings()),
    "PrintDisclosureDialog": lambda _session: PrintDisclosureDialog(share=True, parent=None),
    # **Mit leerer Liste, und das ist der Fall und nicht die Ausnahme.** Ein
    # Rechner ohne installierten Slicer bringt keine Filamentprofile mit; wer
    # den Dialog nur mit Bestand prüft, prüft den selteneren Zustand.
    "SlicerFilamentDialog": lambda _session: SlicerFilamentDialog(None, []),
    # **Die Freischaltung, und sie ist der Fall mit den meisten Sperren:** vier
    # von fünf Knöpfen sind im Ausgangszustand zu, weil weder Schlüssel noch
    # Lizenz eingetragen sind. Genau die Lage, in der ein neuer Kunde den
    # Dialog zum ersten Mal sieht.
    "ActivationDialog": lambda _session: ActivationDialog(),
    "OfflineActivationDialog": lambda _session: OfflineActivationDialog(UiSettings()),
    "FirstRunDialog": lambda _session: FirstRunDialog(settings=UiSettings()),
    "InstallDialog": lambda _session: InstallDialog(),
    "ComfySetupDialog": lambda _session: ComfySetupDialog(),
}


@pytest.fixture
def session(qt_app: QApplication) -> Session:
    """Eine Sitzung mit einem Körper — ohne ihn hat mancher Dialog nichts zu zeigen."""
    made = Session()
    made.import_model(MESHES / "cube_clean.stl", raise_on_error=True)
    made.evaluate_now()
    return made


@pytest.fixture
def window(qt_app: QApplication, session: Session) -> MainWindow:
    """Das Hauptfenster für die Menüprüfungen.

    Aufgeräumt wird zentral: ``tests/conftest.py`` wartet nach jedem Test auf
    die Arbeiter jedes offenen Fensters — dieselbe Bauart wie in
    ``test_ui.py``, damit zwei Aufbauten desselben Fensters nicht
    auseinanderlaufen.
    """
    return MainWindow(session, UiSettings())


@pytest.mark.parametrize("name", sorted(BUILDERS))
def test_no_locked_button_stays_silent(name: str, session: Session, qt_app: QApplication) -> None:
    """Jeder gesperrte, sichtbare Knopf nennt seinen Grund — an allen drei Kanälen.

    Tooltip für die Maus, Statuszeile für den Blick nach unten, zugängliche
    Beschreibung für den Bildschirmleser: Ein Grund, den nur die Maus findet,
    ist für einen Bildschirmleser keiner (Regel 18).

    **Gezeigt, nicht nur gebaut.** Vor dem ``show()`` steht ein Dialog auf
    halbem Weg — Suchläufe sind nicht angelaufen, Zustände nicht gesetzt, und
    ein Test davor prüfte einen Zustand, den ein Kunde nie sieht.
    """
    dialog = BUILDERS[name](session)
    try:
        dialog.show()
        for _ in range(10):
            qt_app.processEvents()

        silent = [
            button.text()
            for button in dialog.findChildren(QPushButton)
            if button.isVisibleTo(dialog)
            and button.text()
            and not button.isEnabled()
            and not (button.toolTip() and button.statusTip() and button.accessibleDescription())
        ]
        assert not silent, f"{name}: gesperrt und ohne Grund: {silent}"
    finally:
        dialog.close()


# --- dieselbe Zusage an den Menüs ---------------------------------------------------


def _locked_without_reason(menu: QMenu, path: str = "") -> tuple[list[str], list[str]]:
    """Gesperrte Einträge ohne Grund, und Menüs, die Hinweise nicht zeigen.

    Zwei Befunde in einem Durchgang, weil sie zusammengehören: Ein Grund, den
    das Menü nicht anzeigt, ist so gut wie keiner. `QMenu` steht mit
    ``toolTipsVisible == False`` auf der Welt, und das hat schon einmal eine
    ganze Kette umsonst gemacht (siehe `oberflaeche.md`).
    """
    silent: list[str] = []
    hidden: list[str] = []
    if not menu.toolTipsVisible():
        hidden.append(path or "(oberste Ebene)")
    for action in menu.actions():
        if action.isSeparator():
            continue
        deeper = action.menu()
        if deeper is not None:
            more_silent, more_hidden = _locked_without_reason(deeper, f"{path} > {action.text()}")
            silent += more_silent
            hidden += more_hidden
            continue
        if action.isEnabled():
            continue
        reason = action.toolTip() or action.statusTip()
        # Qt setzt den Tooltip auf den Text, wenn keiner gesetzt wurde — ein
        # Eintrag, dessen „Grund" sein eigener Name ist, sagt nichts.
        if not reason or reason == action.text():
            silent.append(f"{path} > {action.text()}")
    return silent, hidden


def test_no_locked_menu_entry_stays_silent(window: MainWindow) -> None:
    """Jeder ausgegraute Eintrag der Menüleiste nennt seinen Grund.

    Gemessen am 03.09.2026 über 117 Einträge in zwei Lagen: ohne Modell 56
    gesperrt, mit geladenem Netz und gewähltem Körper 11 — und beide Male
    trugen **alle** ihren Grund. Der Test hält diesen Stand fest, statt einen
    Fund zu belegen: Dieselbe Zusage galt bei den Dialogknöpfen an einer Stelle
    und drei Stellen weiter nicht, und der Unterschied war, dass sie dort nie
    geprüft wurde.
    """
    for label, prepare in (
        ("ohne Modell", lambda: None),
        ("mit Netz", lambda: _with_a_selected_body(window)),
    ):
        prepare()
        QApplication.processEvents()
        for action in window.menuBar().actions():
            menu = action.menu()
            if menu is None:
                continue
            silent, hidden = _locked_without_reason(menu, action.text())
            assert not silent, f"{label}: gesperrt und ohne Grund: {silent}"
            assert not hidden, f"{label}: Menü zeigt keine Hinweise: {hidden}"


def test_no_locked_context_entry_stays_silent(window: MainWindow) -> None:
    """Dasselbe im Kontextmenü des Objektbaums — der zweite Ort derselben Zusage.

    Er ist der ältere Fundort: Dort fehlte einmal ``toolTipsVisible``, und der
    Grund wurde gesetzt und nie gezeigt. Gemessen sind 47 Einträge am Körper,
    davon 5 gesperrt und 5 mit Grund.
    """
    _with_a_selected_body(window)
    menu = window.object_tree.context_menu()
    assert menu is not None, "ein gewählter Körper hat ein Kontextmenü"
    silent, hidden = _locked_without_reason(menu)
    assert not silent, f"gesperrt und ohne Grund: {silent}"
    assert not hidden, f"Menü zeigt keine Hinweise: {hidden}"


def _with_a_selected_body(window: MainWindow) -> None:
    """Ein Netz laden und seinen Körper wählen — die Lage, in der die meisten
    Operationen überhaupt erst freigegeben werden."""
    if not window.session.project.document.ops:
        window.open_path(MESHES / "plate_holes.stl")
        window.session.wait_for_idle()
    result = window.session.evaluate_now()
    window.object_tree.select_object(next(iter(result.scene.objects)))


def test_the_menu_guard_finds_what_it_looks_for(qt_app: QApplication) -> None:
    """Der Wächter an einem Fall, dessen Ausgang feststeht.

    Die zwei Tests darüber schreiben einen **sauberen** Zustand fest — und ein
    Verbotstest über eine leere Menge ist immer grün. Gemessen ist die Menge
    zwar (117 Einträge, davon 56 gesperrt, auch offscreen), aber das sichert
    nur, dass er etwas *sieht*; ob er einen Verstoß auch *findet*, ist die
    zweite Frage.

    Beides zusammen ist die Zusicherung: Er sieht die Menge, und er meldet den
    gebauten Verstoß.
    """
    menu = QMenu()
    menu.setToolTipsVisible(True)
    fine = menu.addAction("Mit Grund")
    fine.setEnabled(False)
    fine.setToolTip("Dafür fehlt ein Körper.")
    mute = menu.addAction("Ohne Grund")
    mute.setEnabled(False)
    open_one = menu.addAction("Nicht gesperrt")

    silent, hidden = _locked_without_reason(menu)

    assert silent == [" > Ohne Grund"], silent
    assert not hidden, "dieses Menü zeigt seine Hinweise"
    assert open_one.isEnabled(), "ein freier Eintrag braucht keinen Grund"

    # Und die zweite Hälfte: ein Menü, das seine Hinweise nicht zeigt, ist
    # derselbe Mangel — der Grund steht da und erreicht niemanden.
    quiet = QMenu()
    locked = quiet.addAction("Mit unsichtbarem Grund")
    locked.setEnabled(False)
    locked.setToolTip("Steht da und wird nie gezeigt.")

    silent, hidden = _locked_without_reason(quiet)

    assert not silent, "der Grund ist gesetzt"
    assert hidden == ["(oberste Ebene)"], hidden
