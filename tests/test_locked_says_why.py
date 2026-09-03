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
from app.core.bootstrap import load_operations
from app.core.export.handover import override_for
from app.core.knowledge import print_settings
from app.core.knowledge.profiles import DEFAULT_MATERIAL
from app.core.registry import REGISTRY
from app.core.types import MaterialSlot
from app.ui.ai_disclosure import AiDisclosureDialog, AiDisclosureTarget, LocalPrivacyDialog
from app.ui.catalog import PartCatalog
from app.ui.changes_dialog import ChangesDialog
from app.ui.comfy_dialog import ComfySetupDialog
from app.ui.command_palette import CommandPalette
from app.ui.dialogs import (
    AboutDialog,
    ActivationDialog,
    AskDialog,
    CalibrationDialog,
    DonationDialog,
    KeyDialog,
    OfflineActivationDialog,
    ParameterDialog,
    StepValuesDialog,
)
from app.ui.filament_picker import NewFilamentDialog, SlicerFilamentDialog
from app.ui.first_run import FirstRunDialog
from app.ui.generate_dialog import GenerateDialog
from app.ui.install_dialog import InstallDialog
from app.ui.main_window import MainWindow
from app.ui.manual_window import ManualWindow
from app.ui.op_dialog import OperationDialog, SketchUseDialog
from app.ui.print_disclosure import PrintDisclosureDialog
from app.ui.print_settings_dialog import FilamentOverrideDialog
from app.ui.recipe_dialog import RecipeDialog
from app.ui.session import Session
from app.ui.settings import UiSettings
from app.ui.shortcuts_window import ShortcutsWindow
from app.ui.sketch_editor import ExpressionDialog, PointDialog, SketchEditorDialog
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


def _wired_catalog() -> PartCatalog:
    """Ein Bausteinkatalog mit den Bedingungen, die das Hauptfenster setzt.

    Beide Gründe sind echte Sätze aus der Anwendung und keine Platzhalter: Ohne
    Szene ist Einsetzen gesperrt, ohne gerechneten Körper das Speichern.
    """
    catalog = PartCatalog()
    catalog.set_can_save(False, "Dafür muss zuerst etwas gerechnet sein.")
    catalog.set_can_insert(
        False,
        "Die Szene ist leer — ein Baustein wird auf einen Körper gesetzt. "
        "Lesen Sie zuerst ein Modell ein oder legen Sie einen Grundkörper an.",
    )
    return catalog


def _first_step(session: Session) -> object:
    """Der erste Schritt des Verlaufs — das Einlesen des Körpers.

    ``StepValuesDialog`` zeigt die Werte einer Operation und bekommt sie im
    Hauptfenster aus ``document.ops``, gesucht über die ID aus dem Fehler. Ein
    selbst gebautes Objekt hätte die Felder, die der Test gerade braucht, und
    keines von denen, an denen er scheitern könnte.
    """
    ops = session.project.document.ops
    assert ops, "die Sitzung hat keinen Schritt — dann zeigt der Dialog nichts"
    return ops[0]


def _op_dialog(session: Session) -> OperationDialog:
    """Der Operationsdialog, wie ``main_window`` ihn zum Anlegen öffnet.

    ``hollow_object`` und nicht der erste Registereintrag: Die Operation hat
    Parameter mit Grenzen und Einheiten, und ihr Dialog ist damit einer mit
    Vorder- und Rückseite statt eines leeren Rahmens. ``load_operations()``
    davor, weil das Register sonst leer ist — die Bausteine tragen sich erst
    beim Laden ein.
    """
    load_operations()
    # ``scene.objects`` ist eine Zuordnung, keine Liste: ``for x in`` gäbe die
    # Schlüssel. Dieselbe Bildung wie ``main_window._object_names``.
    names = {
        object_id: str(entry.name) for object_id, entry in session.last_result.scene.objects.items()
    }
    return OperationDialog(REGISTRY.get("hollow_object"), names)


def _filament_override(session: Session) -> FilamentOverrideDialog:
    """Die Druckwerte einer Spule, wie ``main_window`` sie öffnet.

    Der Slot kommt nicht aus der Szene, sondern wird gebaut: Ein frisch
    eingelesener Würfel hat einen namenlosen Standardslot, und der Dialog zeigt
    dann eine Zeile ohne Inhalt. Name und Material sind die eines Slots, den
    ein Kunde angelegt hätte.
    """
    slot = MaterialSlot(index=0, name="Werkstattrolle", material="PETG")
    settings = print_settings.resolve(session.profile, print_settings.DEFAULT_QUALITY)
    return FilamentOverrideDialog(slot, settings, override_for(settings, slot))


def _recipe(session: Session) -> RecipeDialog:
    """Der Rezeptdialog über den ganzen Verlauf, wie beim Speichern als Baustein.

    Die Merkmale werden wie in ``main_window._result_features`` gesammelt —
    über ``.values()``, denn Szene und Körper führen ihre Inhalte als
    Wörterbücher, und ``for x in`` gäbe die Kennungen. Derselbe Fehler steht
    dort im Docstring, weil er einmal bis zum ersten echten Klick gekommen ist.
    """
    result = session.last_result
    assert result is not None, "die Sitzung hat nicht gerechnet"
    features = tuple(
        feature for entry in result.scene.objects.values() for feature in entry.features.values()
    )
    document = session.project.document
    return RecipeDialog(
        document,
        dict(session.project.sources),
        tuple(step.id for step in document.ops),
        features,
        session.profile,
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
    # --- die ohne eigenen Aufbau: nur ein Elternfenster, und das ist None ---------
    # **Verdrahtet wie in ``main_window._make_catalog``**, und das ist keine
    # Höflichkeit: Die Anwendung ruft ``set_can_save`` und ``set_can_insert``
    # unmittelbar nach dem Konstruktor, für alle drei Zugänge. Ein Katalog ohne
    # sie zeigt einen Zustand, den kein Kunde je sieht — der Wächter meldete
    # daran zuerst „Auswahl als Baustein speichern …", und das war mein
    # Aufbau und kein Befund. Der Grund für *Einfügen* dagegen fehlte wirklich.
    "PartCatalog": lambda _session: _wired_catalog(),
    "SketchUseDialog": lambda _session: SketchUseDialog(),
    # **Mit leerer Liste, wie beim Filamentdialog:** Eine Befehlspalette ohne
    # Einträge ist der Zustand, in dem ein Suchfeld nichts findet.
    "CommandPalette": lambda _session: CommandPalette(),
    # **Ohne Erzeuger, und das ist der häufigste Fall.** Wer kein ComfyUI
    # eingerichtet hat, bekommt diesen Dialog mit gesperrtem Hauptknopf — genau
    # die Lage, in der ein Grund gebraucht wird.
    "GenerateDialog": lambda _session: GenerateDialog(),
    "SketchEditorDialog": lambda _session: SketchEditorDialog(),
    # ``menu_bar=None``: Das Fenster baut seine Liste dann aus dem Register statt
    # aus einer Menüleiste, und ohne Hauptfenster ist das der Weg.
    "ShortcutsWindow": lambda _session: ShortcutsWindow(None),
    # --- die mit einfachen Werten -------------------------------------------------
    "AskDialog": lambda _session: AskDialog(
        "Welche Fläche ist gemeint?", ["die obere", "die untere"]
    ),
    # ``DEFAULT_MATERIAL`` und kein Handelsname: Der Dialog löst die Angabe
    # gegen die Profiltabelle auf und hält bei allem an, was dort nicht steht
    # — "PETG" ist der Werkstoff, "petg" wäre die Kennung.
    "CalibrationDialog": lambda _session: CalibrationDialog(DEFAULT_MATERIAL),
    "LocalPrivacyDialog": lambda _session: LocalPrivacyDialog(
        "# Hinweis\n\nDie Anfrage bleibt auf diesem Rechner."
    ),
    "PointDialog": lambda _session: PointDialog((12.5, -4.0), ("X", "Y")),
    "ExpressionDialog": lambda _session: ExpressionDialog({"breite": 40.0, "hoehe": 12.0}),
    # Die Parameter des Dokuments, wie ``main_window`` sie übergibt: Der Dialog
    # löst Ausdrücke auf und braucht dafür die Objekte, nicht ihre Zahlen. Bei
    # einer frischen Sitzung ist die Sammlung leer, und das ist der Zustand, in
    # dem ein Kunde sie zum ersten Mal öffnet.
    "ParameterDialog": lambda session: ParameterDialog(session.project.document.parameters),
    # --- die auf die Sitzung angewiesen sind ---------------------------------------
    "StepValuesDialog": lambda session: StepValuesDialog(_first_step(session)),
    "OperationDialog": _op_dialog,
    "ManualWindow": lambda _session: ManualWindow(),
    "FilamentOverrideDialog": _filament_override,
    "RecipeDialog": _recipe,
    "AiDisclosureDialog": lambda _session: AiDisclosureDialog(
        AiDisclosureTarget(backend="ollama", target_class="llm", address="http://localhost:11434")
    ),
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
