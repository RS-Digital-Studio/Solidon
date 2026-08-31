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

pytest.importorskip("PySide6")

from PySide6.QtWidgets import QApplication

from app.core.knowledge import profiles
from app.ui.header import HeaderBar, bounds_text, project_name
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings


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
    from app.core.scene import EvaluationResult

    assert bounds_text(None, "mm") == "", "ohne Ergebnis behauptet die Zeile nichts"
    empty: EvaluationResult | None = None
    assert bounds_text(empty, "mm") == ""


def test_an_empty_header_says_nothing(qt_app: QApplication) -> None:
    """Vor dem ersten Projekt steht dort nichts — kein „—", kein „0 mm".

    Eine Zeile, die Platzhalter zeigt, behauptet, es gäbe etwas zu sehen.
    """
    header = HeaderBar()
    title, bounds, printer, material = header.state()
    assert (title, bounds, printer, material) == ("", "", "", "")


def test_the_header_names_printer_and_material(qt_app: QApplication) -> None:
    """Beide, denn beide ändern das Ergebnis."""
    header = HeaderBar()
    profile = profiles.make_profile(profiles.DEFAULT_PRINTER, profiles.DEFAULT_MATERIAL)
    header.show_profile(profile)

    _title, _bounds, printer, material = header.state()
    assert printer == str(profile.printer.title)
    assert material == str(profile.material.title)


def test_long_single_word_profile_names_do_not_push_the_header_into_overflow(
    window: MainWindow,
    qt_app: QApplication,
) -> None:
    """Eigene Profilnamen dürfen die ganze Kopfzeile nicht verdrängen."""
    profile = profiles.make_profile(profiles.DEFAULT_PRINTER, profiles.DEFAULT_MATERIAL)
    printer_title = "Druckermodell" * 16
    material_title = "Materialbezeichnung" * 12
    profile = replace(
        profile,
        printer=replace(profile.printer, title=printer_title),
        material=replace(profile.material, title=material_title),
    )

    window.header.show_profile(profile)
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
        f"material min={window.header.material.minimumWidth()}, "
        f"toolbar={window.toolbar.width()}"
    )
    assert window.header.plates.isVisibleTo(window.toolbar)
    for label, full_text in (
        (window.header.printer, printer_title),
        (window.header.material, material_title),
    ):
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
            header.material.setText("PLA")
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
                    assert header.material.width() > 0 and header.material.text() == "PLA"
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
    window = MainWindow(Session(), UiSettings())
    window.show()
    window.resize(1200, 900)
    window._show_start_screen(False)
    qt_app.processEvents()
    yield window
    window.close()
    window.deleteLater()
    qt_app.processEvents()


def test_the_window_wires_the_header_to_the_session(window: MainWindow) -> None:
    """Die Kette Fenster → Sitzung → Kopfzeile, ohne eine Datei zu laden.

    Geprüft wird die Verdrahtung und nicht das Laden: dass ein Netz ankommt,
    steht in ``test_ui.py``. Hier zählt, dass ``_update_header`` liest, was die
    Sitzung sagt — und dass es an den beiden Stellen hängt, an denen sich das
    ändert (Projektwechsel und Auswertung).
    """
    window._update_header()

    title, _bounds, printer, material = window.header.state()
    assert title == project_name(window.session.title)
    assert printer == str(window.session.profile.printer.title)
    assert material == str(window.session.profile.material.title)


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
    from conftest import make_object

    scene = Scene(objects={"obj_1": make_object(name=name)})
    session.last_result = EvaluationResult(scene=scene)
