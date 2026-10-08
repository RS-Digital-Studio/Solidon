"""Die Kopfzeile sagt, was offen ist und worauf es gedruckt wird.

Drucker und Material bestimmen jede Toleranz im Stapel (§12) — eine Passung
ist ein Verweis ins Materialprofil, kein Zahlenwert. Wer sie nicht sieht, weiß
nicht, was seine Bohrung bedeutet, und musste dafür bisher einen Dialog
öffnen.

Geprüft wird der Text, nicht das Aussehen: was dort steht, ist eine Aussage
über das Projekt und muss stimmen.
"""

from __future__ import annotations

from collections.abc import Iterator
from dataclasses import replace

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QLabel

from app.core.knowledge import profiles
from app.core.scene import EvaluationResult
from app.core.types import MaterialSlot, Scene
from app.ui.header import HeaderBar, bounds_text, filament_names, project_name
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings
from tests.helpers import make_object
from tests.ui_helpers import shown_window


def test_the_title_drops_the_suffix_but_keeps_the_star() -> None:
    """Dass ein Projekt ``.p3d`` heißt, unterscheidet keines vom anderen.

    Der Stern dagegen ist eine Aussage — er sagt, dass etwas ungesichert ist,
    und muss die Kürzung überleben.
    """
    assert project_name("halter.p3d") == "halter"
    assert project_name("halter.p3d*") == "halter*"
    assert project_name("Unbenannt") == "Unbenannt"
    assert project_name("Unbenannt*") == "Unbenannt*"


def test_the_measurements_name_their_unit_once() -> None:
    """„80,00 mm × 50,00 mm × 8,00 mm" sagt dreimal dasselbe."""
    assert bounds_text(None, "mm") == "", "ohne Ergebnis behauptet die Zeile nichts"
    empty: EvaluationResult | None = None
    assert bounds_text(empty, "mm") == ""


def test_an_empty_header_says_nothing(qt_app: QApplication) -> None:
    """Vor dem ersten Projekt steht dort nichts — kein „—", kein „0 mm".

    Eine Zeile, die Platzhalter zeigt, behauptet, es gäbe etwas zu sehen.
    """
    header = HeaderBar()
    assert header.state() == ("", "", "")


def test_the_header_names_the_printer_and_no_filament(qt_app: QApplication) -> None:
    """Der Drucker gilt dem ganzen Projekt, ein Filament tut das nicht.

    Hier stand die Projektvorgabe als Materialzusage — und war schon dann
    falsch, wenn ein Körper „Ohne Filament" trug: Die Kopfzeile sagte
    „PETG" über ein Teil, dem nichts zugewiesen war. Bei mehreren Körpern
    mit verschiedenen Spulen half auch die richtige Rechnung nicht mehr,
    denn „2 Filamente" beantwortet keine Frage (Robert, 07.09.2026).
    Welcher Körper welche Spule trägt, sagt der Filamentbereich links.
    """

    header = HeaderBar()
    profile = profiles.make_profile(profiles.DEFAULT_PRINTER, profiles.DEFAULT_MATERIAL)
    result = EvaluationResult(scene=Scene(objects={"obj_1": make_object()}))
    header.show_profile(profile, result)

    _title, _bounds, printer = header.state()
    assert printer == str(profile.printer.title)
    material = str(profile.material.title)
    for label in header.findChildren(QLabel):
        assert material not in label.text(), "die Kopfzeile nennt kein Filament"


def test_empty_measurements_leave_their_room_to_the_printer(qt_app: QApplication) -> None:
    """Ohne Körper gibt die leere Maßangabe ihren Platz dem Drucker.

    Die Spalte der Maße dehnte sich auch leer mit: Bei 1600 Bildpunkten und
    dem Suchfeld in der Leiste (RM-506) stand dort eine leere Fläche, und der
    Drucker las sich „Allge…0 mm · FDM“.
    """
    header = HeaderBar()
    profile = profiles.make_profile(profiles.DEFAULT_PRINTER, profiles.DEFAULT_MATERIAL)
    header.show_project("Unbenannt", None, "mm")
    header.show_profile(profile)
    full = str(profile.printer.title)
    needed = (
        header.printer.fontMetrics().horizontalAdvance(full)
        + header.printer_button.sizeHint().width()
        + 24
    )
    # Titel und Drucker teilen 2 : 3 — breit genug für den Drucker, wenn die
    # leere Spalte nichts nimmt, zu schmal, wenn sie drei Teile behält. Der
    # Knopf *Filamente* steht fest daneben (RM-556).
    header.resize(
        needed * 5 // 3 + 24 + header._filament_width(words=True), header.sizeHint().height()
    )
    header.show()
    QApplication.processEvents()

    assert header.bounds.width() == 0, f"leere Maße {header.bounds.width()} px breit"
    assert header.printer.text() == full, header.printer.text()

    result = EvaluationResult(scene=Scene(objects={"obj_1": make_object()}))
    header.show_project("Halter", result, "mm")
    assert header.bounds.full_text() and header._layout.columnStretch(1) > 0, "Maße dehnen"
    header.show_project("Unbenannt", None, "mm")
    assert header._layout.columnStretch(1) == 0, "wieder leer, wieder ohne Dehnung"


def test_long_single_word_profile_names_do_not_push_the_header_into_overflow(
    window: MainWindow,
    qt_app: QApplication,
) -> None:
    """Eigene Profilnamen dürfen die ganze Kopfzeile nicht verdrängen."""
    profile = profiles.make_profile(profiles.DEFAULT_PRINTER, profiles.DEFAULT_MATERIAL)
    printer_title = "Druckermodell" * 16
    profile = replace(profile, printer=replace(profile.printer, title=printer_title))

    result = EvaluationResult(scene=Scene(objects={"obj_1": make_object()}))
    window.header.show_profile(profile, result)
    window.header.title.setText("Ein langes eigenes Projekt*")
    window.header.bounds.setText("220,0 × 220,0 × 250,0 mm")
    window.header.show_plates(3)
    window.resize(640, 720)
    window.header.updateGeometry()
    window.toolbar.updateGeometry()
    QApplication.processEvents()

    assert window.header.isVisibleTo(window.toolbar), (
        "die Kopfzeile liegt im Überlaufmenü: "
        f"header min={window.header.minimumSizeHint().width()}, "
        f"printer min={window.header.printer.minimumWidth()}, "
        f"toolbar={window.toolbar.width()}"
    )
    assert window.header.plates.isVisibleTo(window.toolbar)
    for label, full_text in ((window.header.printer, printer_title),):
        assert label.isVisibleTo(window.toolbar) and label.width() > 0
        assert label.full_text() == full_text
        assert label.toolTip() == full_text
        assert label.accessibleName() == full_text
        assert label.text() != full_text and "…" in label.text()


def test_the_plate_filter_shows_its_complete_state_in_every_language(
    qt_app: QApplication,
) -> None:
    """Auch bei 640 Pixeln ist nicht nur der Zweck, sondern die Wahl sichtbar.

    Ein zusammengesetztes „Platte: Alle“ war in drei Sprachen grammatisch
    falsch und schnitt bei schmalen Fenstern ausgerechnet den Zustand ab. Ein
    eigener übersetzter Eintrag und seine echte Zeichenbreite verhindern
    beides für „alle“ und für jede einzelne Platte.
    """
    from PySide6.QtWidgets import QStyle, QStyleOptionComboBox

    from app.i18n import set_language, tr
    from app.i18n.catalog import available_languages, install_language
    from app.ui.style import apply_style

    previous_style = qt_app.styleSheet()
    apply_style(qt_app, "dark")
    try:
        for language in available_languages():
            install_language(language)
            set_language(language)
            header = HeaderBar()
            header.title.setText("Ein sehr langes Beispielprojekt*")
            header.bounds.setText("6,5354 × 3,1496 × 2,0472 in")
            header.printer.setText("Allgemeiner FDM-Drucker 220 mm")
            header.show_plates(3)
            header.show()
            try:
                assert header.plates.itemText(0) == str(tr("Alle Platten"))
                for width in (289, 449, 689, 1125):
                    # Ein freistehendes QWidget darf Qt nicht unter das
                    # Mindestmaß seines *vorigen* Layouts verkleinern. In der
                    # echten QToolBar entscheidet derselbe Vergleich vor der
                    # Zuweisung; hier lösen wir ihn für die Zielbreite aus.
                    header._arrange(header._wide_width() > width)
                    header.resize(width, 80)
                    QApplication.processEvents()
                    assert header.width() == width
                    assert header.title.width() > 0 and header.title.text().endswith("*")
                    assert header.bounds.width() > 0 and header.bounds.text().endswith("in")
                    assert header.printer.width() > 0 and header.printer.text().endswith("220 mm")
                    for index in range(header.plates.count()):
                        header.plates.setCurrentIndex(index)
                        QApplication.processEvents()
                        option = QStyleOptionComboBox()
                        option.initFrom(header.plates)
                        option.currentText = header.plates.currentText()
                        field = header.plates.style().subControlRect(
                            QStyle.ComplexControl.CC_ComboBox,
                            option,
                            QStyle.SubControl.SC_ComboBoxEditField,
                            header.plates,
                        )
                        assert field.width() >= header.plates.fontMetrics().horizontalAdvance(
                            header.plates.currentText()
                        ), f"{language}/{width}: {header.plates.currentText()!r} ist abgeschnitten"
            finally:
                header.deleteLater()
    finally:
        set_language("de")
        qt_app.setStyleSheet(previous_style)


@pytest.fixture
def window(qt_app: QApplication) -> Iterator[MainWindow]:
    yield from shown_window(qt_app)


def test_the_window_wires_the_header_to_the_session(window: MainWindow) -> None:
    """Die Kette Fenster → Sitzung → Kopfzeile, ohne eine Datei zu laden.

    Geprüft wird die Verdrahtung und nicht das Laden: dass ein Netz ankommt,
    steht in ``test_ui.py``. Hier zählt, dass ``_update_header`` liest, was die
    Sitzung sagt — und dass es an den beiden Stellen hängt, an denen sich das
    ändert (Projektwechsel und Auswertung).

    Rechts steht das Druckziel der Sitzung (RM-090, ``Session.review_target``):
    Drucker und Verfahren, „unvollständig“, wo eine Grundlage fehlt, die
    Einzelheiten im Tooltip — derselbe Drucker wie im Profil der Sitzung.
    """
    window._update_header()

    title, _bounds, printer = window.header.state()
    assert title == project_name(window.session.title)
    target = window.session.review_target()
    assert printer == target.title
    assert printer.startswith(str(window.session.profile.printer.title)), printer
    assert window.header.printer.toolTip() == target.details


def test_the_header_lists_multiple_project_filaments_instead_of_one_global_material(
    qt_app: QApplication,
) -> None:
    """Slotname, Materialart und Farbe bleiben projektbezogen unterscheidbar."""

    profile = profiles.make_profile(profiles.DEFAULT_PRINTER, "petg")
    body = make_object(slots=(0, 1) * 6)
    body.material_slots = [
        MaterialSlot(index=0, name="Gehäuse", material_type="PETG"),
        MaterialSlot(
            index=1,
            name="Schrift Weiß",
            material_type="PLA",
            colour=(1.0, 1.0, 1.0),
        ),
    ]
    names = filament_names(profile, [body])

    assert len(names) == 2
    assert "Gehäuse (PETG)" in names
    assert any("Schrift Weiß (PLA)" in name and "#FFFFFF" in name for name in names)


def test_the_header_ignores_unused_filament_metadata_after_a_complete_repaint(
    qt_app: QApplication,
) -> None:
    """Vollständig übermalte Flächen nennen weder Basis noch frühere Farben."""

    profile = profiles.make_profile(profiles.DEFAULT_PRINTER, "petg")
    body = make_object(slots=(1,) * 12)
    body.material_slots = [
        MaterialSlot(index=0, name="Altes PETG", material_type="PETG"),
        MaterialSlot(
            index=1,
            name="PLA Weiß",
            material_type="PLA",
            colour=(1.0, 1.0, 1.0),
        ),
        MaterialSlot(
            index=2,
            name="Altes Rot",
            material_type="PLA",
            colour=(1.0, 0.0, 0.0),
        ),
    ]
    names = filament_names(profile, [body])

    assert names == ("PLA Weiß · #FFFFFF",)


def test_slot_metadata_without_a_material_uses_only_the_known_project_fallback(
    qt_app: QApplication,
) -> None:
    """Leere Importfelder bleiben sichtbar, eine fremde Art bleibt fremd."""

    profile = profiles.make_profile(profiles.DEFAULT_PRINTER, "petg")
    body = make_object(slots=(0,) * 12)

    body.material_slots = [MaterialSlot(index=0, name="")]
    assert filament_names(profile, [body]) == (str(profile.material.title),)

    body.material_slots = [MaterialSlot(index=0, name="Import Grau", colour=(0.5, 0.5, 0.5))]
    assert filament_names(profile, [body]) == ("Import Grau (PETG) · #808080",)

    body.material_slots = [MaterialSlot(index=0, name="Holzoptik", material_type="Wood")]
    assert filament_names(profile, [body]) == ("Holzoptik (Wood)",)


def test_showing_the_header_reads_large_face_slot_assignments_once(
    qt_app: QApplication,
) -> None:
    """Kurztext und Tooltip teilen eine Erhebung über die Dreieckszuordnung."""

    class CountingSlots(list[int]):
        def __init__(self, values: list[int]) -> None:
            super().__init__(values)
            self.iterations = 0

        def __iter__(self) -> Iterator[int]:
            self.iterations += 1
            return super().__iter__()

    assignments = CountingSlots([0, 1] * 6)
    body = make_object(slots=assignments)
    body.material_slots = [
        MaterialSlot(index=0, name="PETG Schwarz", material_type="PETG"),
        MaterialSlot(index=1, name="PLA Weiß", material_type="PLA"),
    ]

    filament_names(profiles.make_profile(profiles.DEFAULT_PRINTER, "petg"), [body])

    assert assignments.iterations == 1


def test_the_printer_button_is_a_direct_keyboard_path(qt_app: QApplication) -> None:
    """Der Projektdrucker ist aus der Kopfzeile mit einer Handlung erreichbar."""
    header = HeaderBar()
    requested = []
    header.printerRequested.connect(lambda: requested.append(True))

    header.printer_button.click()

    assert requested == [True]
    assert header.printer_button.focusPolicy() != Qt.FocusPolicy.NoFocus
    assert header.printer_button.toolTip()


def test_the_printer_button_has_one_name_seen_and_read(qt_app: QApplication) -> None:
    """„Drucker …“ sichtbar, „Drucker wechseln“ vorgelesen, „Druckeinstellungen“ im Dialog (RM-507).

    Sichtbarer und zugänglicher Name kommen aus einem Schlüssel — auch nachdem
    die Kopfzeile ihre Lage für eine andere Breite neu gelegt hat.
    """
    from app.ui.header import printer_button_text

    header = HeaderBar()
    header.resize(1600, header.sizeHint().height())
    header.show()
    QApplication.processEvents()
    try:
        assert header.printer_button.text() == printer_button_text()
        assert header.printer_button.accessibleName() == printer_button_text()
    finally:
        header.close()


def test_an_open_project_gives_the_header_readable_room_before_toolbar_words(
    window: MainWindow, qt_app: QApplication
) -> None:
    """Auf Laptopbreite bleiben Projekt, Drucker und Filamentanzahl lesbar."""

    body = make_object(slots=(0, 1) * 6)
    body.material_slots = [
        MaterialSlot(index=0, name="PETG Schwarz", material_type="PETG"),
        MaterialSlot(index=1, name="PLA Weiß", material_type="PLA"),
    ]
    result = EvaluationResult(scene=Scene(objects={"obj_1": body}))
    window.resize(1024, 720)
    window.header.show_project("Halter.p3d*", result, "mm")
    window.header.show_profile(window.session.profile, result)
    window._fit_toolbar()
    qt_app.processEvents()

    assert not window._toolbar_wide
    assert window.header.width() >= 600
    assert window.header.title.text() == "Halter*"
    # Der Knopf trägt seine Beschriftung, nicht nur sein Symbol — das ist
    # der Platz, den diese Breite außer Name und Maß noch hergeben muss.
    assert window.header.printer_button.text()
    assert window.header.printer_button.toolButtonStyle() is not (
        Qt.ToolButtonStyle.ToolButtonIconOnly
    )


def test_the_search_gives_way_to_the_header_and_keeps_its_name(
    window: MainWindow, qt_app: QApplication
) -> None:
    """Die Suche (RM-506) kürzt wie die sieben Knöpfe, bevor die Kopfzeile weicht.

    Mit ihrem festen Wort drückte sie die Kopfzeile bei 1024 Pixeln auf ein
    Drittel und bei 800 ins Überlaufmenü (Durchsicht 0.5.3). In der schmalsten
    Form bleibt die Lupe; Name, Kürzel und Zweck stehen im Tooltip und beim
    Bildschirmleser. Wo Platz ist, trägt sie ihr Wort wieder.
    """
    from PySide6.QtGui import QKeySequence

    from app.i18n import tr

    body = make_object(slots=(0, 1) * 6)
    result = EvaluationResult(scene=Scene(objects={"obj_1": body}))
    window.header.show_project("Halter.p3d*", result, "mm")
    window.header.show_profile(window.session.profile, result)
    search = window.function_search
    keys = window._palette_action.shortcut().toString(QKeySequence.SequenceFormat.NativeText)
    assert keys, "ohne Kürzel prüft der Tooltip nur den Namen"

    window.resize(800, 720)
    qt_app.processEvents()
    assert window.header.isVisibleTo(window.toolbar), "die Kopfzeile bleibt in der Leiste"
    assert search.isVisibleTo(window.toolbar), "die Suche bleibt sichtbar"
    assert not search.text(), "schmal steht nur die Lupe"
    assert search.accessibleName() == tr("Funktion suchen")
    assert tr("Funktion suchen") in search.toolTip() and keys in search.toolTip()

    window.resize(1920, 1080)
    qt_app.processEvents()
    assert search.text().startswith(tr("Funktion suchen …")), "breit trägt sie ihr Wort"
    assert window.header.isVisibleTo(window.toolbar)


def test_the_plate_filter_never_lies_over_the_printer(qt_app: QApplication) -> None:
    """Der Plattenwähler bekommt seine Spalte auch dann, wenn er erst später dasteht.

    **RM-158, Roberts Fenster** (11.09.2026): „Alle Platten" lag über „Elegoo
    Centauri Carbon 2", beide begannen an derselben x-Stelle, der Wähler so
    breit wie sein Mindestmaß. Nachgestellt über den Startweg der Anwendung:
    Das Fenster wird 1280 breit gebaut (Kopfzeile kompakt), bekommt dann
    seine gespeicherte Breite (breit, Wähler versteckt) und zeigt den Wähler
    erst, wenn das Projekt seine Platten hat. Die Spaltendehnung stand nur,
    wenn der Wähler beim Anordnen sichtbar war — und ein ``QGridLayout``
    gibt einer ungedehnten Spalte mit einem ``Ignored``-Widget null Breite,
    Mindestmaß hin oder her.

    Gemessen wird am Ort: Der Wähler endet, bevor der Drucker beginnt — nach
    dem Zeigen, und noch einmal, nachdem er wieder verschwunden und wieder
    gekommen ist. Gegenprobe ohne ``_stretch_the_plate_column`` beim Zeigen:
    der Wähler beginnt bei derselben x-Stelle wie der Drucker, rot.
    """

    window = MainWindow(Session(), UiSettings())
    try:
        window.resize(1280, 820)
        window.show()
        window._show_start_screen(False)
        qt_app.processEvents()
        window.resize(2560, 1369)
        qt_app.processEvents()
        assert not window.header._compact, "breit genug für eine Zeile"
        assert window.header.plates.isHidden(), "ohne Platten kein Wähler"

        result = EvaluationResult(scene=Scene(objects={"obj_1": make_object()}))
        window.header.show_project("Solidon3d", result, "mm")
        window.header.show_profile(window.session.profile, result)
        for plates in (4, 1, 4):
            window.header.show_plates(plates)
            qt_app.processEvents()
            qt_app.processEvents()
            if plates == 1:
                assert window.header.plates.isHidden()
                continue
            header = window.header
            right_edge = header.plates.x() + header.plates.width()
            assert header.plates.width() >= header.plates.minimumWidth()
            assert right_edge <= header.printer_control.x(), (
                f"der Wähler ({header.plates.x()}..{right_edge}) liegt über dem Drucker "
                f"(ab {header.printer_control.x()})"
            )
            # Ob der Druckername ungekürzt dasteht, misst nur die echte
            # Plattform — offscreen hat jede Schrift dieselbe Phantommetrik.
            # Hier zählt der Ort: Der Drucker beginnt hinter dem Trennstrich.
            assert header.printer_control.x() > header._divider.x()
    finally:
        window.close()
        window.deleteLater()
        qt_app.processEvents()


def test_the_header_is_updated_where_the_state_changes() -> None:
    """Beide Auslöser, an der Quelle geprüft.

    Ein Test, der nur einen davon kennt, bleibt grün, während die Zeile nach
    einer Auswertung veraltet dasteht — genau der Fehler, den man erst bemerkt,
    wenn ein Maß nicht mehr stimmt.
    """
    from pathlib import Path

    source = (Path(__file__).parent.parent / "app" / "ui" / "main_window.py").read_text("utf-8")
    body = source.split("def _on_scene(", 1)[1].split("def ", 1)[0]
    assert "_show_scene(" in body, (
        "jede Auswertung — auch eine aufgestaute — geht durch _show_scene"
    )

    body = source.split("def _show_scene(", 1)[1].split("def ", 1)[0]
    assert "_update_header()" in body, "nach jeder Auswertung"

    body = source.split("def _on_project(", 1)[1].split("def ", 1)[0]
    assert "_update_header()" in body, "und bei jedem Projektwechsel"


def test_the_title_names_what_is_open_instead_of_what_is_missing() -> None:
    """„Unbenannt", während der Objektbaum den Namen zeigt.

    **So stand es im Bildschirmfoto des ersten Kunden mit 0.1.3**: oben
    „Unbenannt*", darunter im Baum „GK-Brause" mit seinen Maßen. Der Titel
    wusste den Namen — er sagte ihn nur nicht, sondern nannte stattdessen, was
    fehlt.

    Entschieden von Robert am 23.08.2026: der abgeleitete Name, wie Fusion es
    tut. Ein Titel, der dem Baum widerspricht, ist schlechter als einer, der
    ihn wiederholt.

    **Der Zusatz „(ungespeichert)" bleibt und ist nicht dasselbe wie der
    Stern.** Der Stern sagt „seit dem letzten Speichern geändert", der Zusatz
    sagt „es gibt keine Datei". Ohne ihn sähe „GK-Brause*" aus wie eine
    geöffnete Projektdatei, und der Kunde suchte sie beim nächsten Start.
    """
    session = Session()
    assert session.title == "Unbenannt", "ohne Objekte gibt es nichts abzuleiten"

    _with_object(session, "GK-Brause")
    assert session.title.startswith("GK-Brause"), (
        f"der Baum weiß es, der Titel auch: {session.title}"
    )
    assert "ungespeichert" in session.title, "es gibt keine Datei, und das gehört dazu"


def test_the_derived_name_does_not_leak_into_the_file_dialog() -> None:
    """Der Dateivorschlag nimmt den Namen, nicht den Titel.

    ``main_window`` baut den Vorschlag für *Exportieren* aus dem Titel
    (``safe_name(Path(...).stem)``). Mit dem Zusatz stünde dort
    „GK-Brause (ungespeichert).stl" — ein Dateiname, der eine Eigenschaft des
    Fensters trägt.

    Deshalb zwei Auskünfte statt einer: ``title`` ist für den Menschen,
    ``document_name`` für die Datei.
    """
    session = Session()
    _with_object(session, "GK-Brause")

    assert session.document_name == "GK-Brause"
    assert "ungespeichert" not in session.document_name
    assert "*" not in session.document_name


def _with_object(session: Session, name: str) -> None:
    """Der Sitzung ein Auswertungsergebnis mit einem benannten Körper geben.

    Über das Ergebnis und nicht über das Dokument: Der Titel liest, was
    **dasteht**, und das sind die ausgewerteten Objekte — dieselbe Quelle wie
    der Objektbaum daneben.
    """
    from app.core.scene.evaluate import EvaluationResult
    from app.core.types import Scene

    scene = Scene(objects={"obj_1": make_object(name=name)})
    session.last_result = EvaluationResult(scene=scene)


def test_the_filaments_open_from_the_header_and_lead_into_the_inventory(
    window: MainWindow, qt_app: QApplication
) -> None:
    """RM-556: *Filamente* steht in der Kopfzeile, nicht mehr unten links.

    Robert, 08.10.2026: Ein Klick öffnet eine kleine Liste der Filamente, die
    das Projekt verwendet, und darunter den Weg ins Filamentlager. Die linke
    Spalte trägt nur noch Objekte, Parameter und Verlauf.
    """
    from PySide6.QtWidgets import QAbstractButton

    from app.i18n import tr
    from app.ui.filament_assignment import QuickFilamentPicker

    headings = {
        button.text()
        for button in window.findChildren(QAbstractButton)
        if button.objectName() == "sectionHeading"
    }
    assert tr("Filamente") not in headings, f"links steht keine Filamentgruppe mehr: {headings}"
    assert tr("Verlauf") in headings, "die Klappen werden gefunden"

    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.types import SceneObject

    body = SceneObject(
        id="obj_1",
        name="Teil",
        mesh=MeshData.of(trimesh.creation.box(), slots=(1,) * 12),
        material_slots=[MaterialSlot(index=1, name="PETG Rot", colour=(0.8, 0.1, 0.1))],
    )
    result = EvaluationResult(scene=Scene(objects={"obj_1": body}))
    window._show_project_filaments(result, window.effective_print_settings())
    button = window.header.filament_button
    assert button.text() == tr("Filamente") and button.isVisibleTo(window.toolbar)
    assert "PETG Rot" in button.toolTip(), "die Kurzhilfe nennt die Filamente"

    button.click()
    qt_app.processEvents()
    popup = window.filament_popup
    assert popup.isVisible(), "der Knopf öffnet die Liste"
    rows = [popup.panel.list.item(row).text() for row in range(popup.panel.list.count())]
    assert rows == ["PETG Rot — 1 Körper"], rows
    assert not popup.panel.inventory_button.isHidden(), "darunter der Weg ins Lager"
    assert not popup.findChildren(QuickFilamentPicker), "zugewiesen wird rechts, nicht hier"

    popup.panel.inventory_button.click()
    qt_app.processEvents()
    assert not popup.isVisible(), "die Liste geht mit dem Wechsel ins Lager"
    assert window.stack.currentWidget() is window._inventory_view
    window._inventory_view.backRequested.emit()


def test_the_filament_button_names_exactly_the_rows_of_its_list(window: MainWindow) -> None:
    """Kurzhilfe und Liste hinter *Filamente* sagen dasselbe — eine Quelle (Review U2, Fund 3).

    Die Kurzhilfe las die Projektvorgabe: Über einem Körper ohne Filament
    stand „Im Projekt: PLA“, die Liste sagte „Ohne Filament“, und eine Spule
    ohne Materialangabe hieß in der Kurzhilfe anders als in der Liste. In der
    engen Kopfzeile ist die Kurzhilfe die einzige Auskunft des Knopfs.
    """
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.types import SceneObject
    from app.i18n import tr

    plain = SceneObject(id="obj_1", name="Ohne", mesh=MeshData.of(trimesh.creation.box()))
    red = SceneObject(
        id="obj_2",
        name="Rot",
        mesh=MeshData.of(trimesh.creation.box(), slots=(1,) * 12),
        material_slots=[MaterialSlot(index=1, name="PETG Rot", colour=(0.8, 0.1, 0.1))],
    )
    result = EvaluationResult(scene=Scene(objects={"obj_1": plain, "obj_2": red}))
    window._show_project_filaments(result, window.effective_print_settings())
    panel = window.filaments
    rows = [panel.list.item(row).text() for row in range(panel.list.count())]
    assert any("Ohne Filament" in row for row in rows), rows
    said = window.header.filament_button.toolTip()
    first_line_and_rows = said.split("\n")[: len(rows)]
    expected = tr("Im Projekt: {filament}").format(filament="\n".join(rows)).split("\n")
    assert first_line_and_rows == expected, (said, rows)
    assert window.header.filament_button.accessibleDescription() == said


def test_the_search_keeps_its_word_beside_the_filament_button(
    window: MainWindow, qt_app: QApplication
) -> None:
    """Die Suche behält ihr Wort, wo es neben dem Zeichen von *Filamente* Platz hat.

    Mit dem Wort des Knopfs im Wunschmaß der Kopfzeile trug *Funktion suchen …*
    sein Wort am echten Windows-Fenster erst ab 1415 px — 1366 × 768 ist die
    häufigste Laptopbreite (Review U2, Fund 4; Entscheidung des Koordinators:
    Die Suche geht vor, `grenzen.md`). Gemessen wird an der Breite, die genau
    zwischen beiden Rechnungen liegt, aus den Maßen dieses Laufs: Offscreen
    hat die Schrift eine andere Breite als am Fenster (`tests.md`), die
    Breiten 1366 und 1400 belegt die Sonde am echten Fenster im Bericht.
    """
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.types import SceneObject
    from app.i18n import tr
    from app.ui.header import READABLE_HEADER_WIDTH
    from app.ui.main_window import TOOLBAR_HYSTERESIS
    from app.ui.style import apply_style

    previous_style = qt_app.styleSheet()
    apply_style(qt_app, "dark")
    try:
        body = SceneObject(
            id="obj_1",
            name="Halter",
            mesh=MeshData.of(trimesh.creation.box(extents=(60.0, 40.0, 20.0))),
        )
        result = EvaluationResult(scene=Scene(objects={"obj_1": body}))
        window.header.show_project("Halter.p3d*", result, "mm")
        window.header.show_profile(window.session.profile, result)
        window.resize(1024, 720)
        for _ in range(4):
            qt_app.processEvents()
        window._fit_toolbar()
        search = window.function_search
        assert not search.text(), "die Lage: schmal steht nur die Lupe"
        header = window.header
        # Das Wunschmaß, wie es sein soll: Leseraum plus das Zeichen des Knopfs.
        sign_wish = max(
            header._compact_width(), READABLE_HEADER_WIDTH + header._filament_width(words=False)
        )
        words_wish = (
            sign_wish + header._filament_width(words=True) - header._filament_width(words=False)
        )
        # Der wahre Bedarf der Form mit Suchwort, ohne die gemerkten Bedarfe des
        # Fensters anzufassen: Die stammen aus dem Aufbau ohne Projekt, und
        # genau dort trugen sie das Mindestmaß der Kopfzeile mit.
        remembered = dict(window._toolbar_needs)
        window._set_toolbar_form(1)
        search_need = window.toolbar.sizeHint().width() - header.sizeHint().width()
        window._set_toolbar_form(0)
        window._toolbar_needs = remembered
        between = search_need + sign_wish + TOOLBAR_HYSTERESIS + 2
        assert between < search_need + words_wish + TOOLBAR_HYSTERESIS, (
            "die Breite unterscheidet beide Rechnungen"
        )

        window.resize(between, 768)
        for _ in range(4):
            qt_app.processEvents()
        window._fit_toolbar()
        qt_app.processEvents()
        assert search.text().startswith(tr("Funktion suchen …")), (
            f"bei {between} px ist die Suche nur noch eine Lupe"
        )
        button = header.filament_button
        assert button.isVisibleTo(window.toolbar) and button.width() > 0
        assert button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonIconOnly, (
            "ohne Platz über dem Wunschmaß trägt der Knopf nur sein Zeichen"
        )
        assert button.accessibleName() == tr("Filamente")

        window.resize(2400, 900)
        for _ in range(4):
            qt_app.processEvents()
        window._fit_toolbar()
        qt_app.processEvents()
        assert button.toolButtonStyle() == Qt.ToolButtonStyle.ToolButtonTextBesideIcon, (
            "mit Platz trägt der Knopf sein Wort"
        )
    finally:
        qt_app.setStyleSheet(previous_style)


def test_a_remembered_toolbar_need_does_not_carry_the_header(
    window: MainWindow, qt_app: QApplication
) -> None:
    """Was die Leiste ohne Kopfzeile braucht, gilt mit und ohne offenes Projekt gleich.

    Gemerkt wird je Form der Bedarf ohne die Kopfzeile (``_fit_toolbar``). Ohne
    Projekt ist ihr Wunschmaß null, ihr Mindestmaß nicht — und die Leiste rechnet
    mit dem größeren. Der beim Aufbau gemerkte Bedarf der Suchform lag damit am
    echten Fenster 57 px zu hoch, und die Suche bekam ihr Wort bei 1366 und
    1400 px nie zurück (Review U2, Fund 4).
    """
    import trimesh

    from app.core.geom.mesh import MeshData
    from app.core.types import SceneObject

    window.resize(900, 720)
    for _ in range(4):
        qt_app.processEvents()
    window._set_toolbar_form(1)
    window._fit_toolbar()
    assert window.header.minimumSizeHint().width() > window.header.sizeHint().width(), (
        "die Lage: ohne Projekt ist das Mindestmaß größer als der Wunsch"
    )
    window._set_toolbar_form(1)
    window._toolbar_needs.clear()
    window._fit_toolbar()
    empty = window._toolbar_needs.get(1)
    assert empty is not None

    body = SceneObject(id="obj_1", name="Halter", mesh=MeshData.of(trimesh.creation.box()))
    result = EvaluationResult(scene=Scene(objects={"obj_1": body}))
    window.header.show_project("Halter.p3d*", result, "mm")
    window.header.show_profile(window.session.profile, result)
    window.resize(3000, 900)
    for _ in range(4):
        qt_app.processEvents()
    window._set_toolbar_form(1)
    window._toolbar_needs.clear()
    window._fit_toolbar()
    with_project = window._toolbar_needs.get(1)
    assert empty == with_project, (empty, with_project)


def test_a_second_click_on_filaments_closes_the_list(
    window: MainWindow, qt_app: QApplication
) -> None:
    """Wie ein Menü: Der zweite Klick auf *Filamente* schließt die Liste (Review U2, Fund 5).

    Qt schließt ein Popup beim Druck daneben und spielt den Druck dem Knopf
    noch einmal zu — der öffnete die Liste sofort wieder. ``QMenu`` verhindert
    das über ``WA_NoMouseReplay``.
    """
    from PySide6.QtTest import QTest

    button = window.header.filament_button
    popup = window.filament_popup
    window.show()
    qt_app.processEvents()
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    qt_app.processEvents()
    assert popup.isVisible(), "der erste Klick öffnet"
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    qt_app.processEvents()
    assert not popup.isVisible(), "der zweite Klick schließt"
    QTest.mouseClick(button, Qt.MouseButton.LeftButton)
    qt_app.processEvents()
    assert popup.isVisible(), "der dritte öffnet wieder"
    popup.hide()


def test_the_way_back_to_the_print_settings_stands_only_after_coming_from_there(
    window: MainWindow, qt_app: QApplication
) -> None:
    """*Zurück zu Druckeinstellungen* nur nach dem Weg aus den Druckeinstellungen (Fund 6)."""
    back = window.filaments.return_to_print_button
    popup = window.filament_popup
    window._focus_filaments()
    qt_app.processEvents()
    assert popup.isVisible() and not back.isHidden(), "aus den Druckeinstellungen: Rückweg"
    popup.hide()
    window.header.filament_button.click()
    qt_app.processEvents()
    assert popup.isVisible() and back.isHidden(), "aus der Kopfzeile: kein Rückweg ohne Hinweg"
    popup.hide()


@pytest.mark.parametrize("corner", ["bottom-right", "top-left"])
def test_the_filament_list_stays_on_the_screen(qt_app: QApplication, corner: str) -> None:
    """Am Schirmrand weicht die Liste nach oben aus und bleibt ganz sichtbar (Fund 9)."""
    from PySide6.QtWidgets import QPushButton, QWidget

    from app.ui.filament_picker import POPUP_WIDTH, FilamentPopup

    host = QWidget()
    popup = FilamentPopup(host)
    anchor = QPushButton("Filamente")
    anchor.resize(90, 28)
    screen = qt_app.primaryScreen().availableGeometry()
    if corner == "bottom-right":
        anchor.move(screen.right() - 40, screen.bottom() - 30)
    else:
        anchor.move(screen.left() + 2, screen.top() + 2)
    anchor.show()
    qt_app.processEvents()
    try:
        popup.show_below(anchor)
        qt_app.processEvents()
        frame = popup.geometry()
        assert screen.contains(frame), (frame.getRect(), screen.getRect())
        assert frame.width() >= POPUP_WIDTH
        top_of_anchor = anchor.mapToGlobal(anchor.rect().topLeft()).y()
        bottom_of_anchor = anchor.mapToGlobal(anchor.rect().bottomLeft()).y()
        if corner == "bottom-right":
            assert frame.bottom() < top_of_anchor + 1, "unten fehlt Platz: die Liste steht darüber"
        else:
            assert frame.top() > bottom_of_anchor, "oben am Rand: die Liste steht darunter"
    finally:
        popup.hide()
        anchor.close()
        host.deleteLater()
        anchor.deleteLater()
