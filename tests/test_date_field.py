"""Ein Datum der Spule über die Tastatur und zurück auf „Unbekannt“ (RM-502).

Offen war am Fenster der Ziffernweg in jeder Sprache und der Rückweg auf
„Unbekannt“. Geprüft wird über den echten Spulendialog bis in seinen Eintrag
(``NewFilamentDialog.entry``), nicht nur am Feld: Was gespeichert würde, ist
die Zusage. Die Reihenfolge der Abschnitte liest der Test aus dem Anzeigeformat,
das die Sprache dem Feld gibt.
"""

from __future__ import annotations

import re

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

LANGUAGES = ["de", "en", "es", "fr", "it", "pt"]


def _typed(display_format: str, day: str, month: str, year: str) -> str:
    """Die Ziffern in der Folge, in der das Feld seine Abschnitte zeigt."""
    order = re.findall(r"d+|M+|y+", display_format)
    assert len(order) == 3, display_format
    return "".join({"d": day, "M": month, "y": year}[token[0]] for token in order)


@pytest.fixture
def spool_dialog(qt_app, request):
    from app.i18n import get_language, set_language
    from app.i18n.catalog import install_language
    from app.ui.filament_picker import NewFilamentDialog

    before = get_language()
    language = request.param
    if language != "de":
        install_language(language)
    set_language(language)
    dialog = NewFilamentDialog(name="Werkstattrolle")
    dialog.show()
    for _ in range(6):
        qt_app.processEvents()
    try:
        yield dialog
    finally:
        dialog.release()
        dialog.close()
        dialog.deleteLater()
        set_language(before)


@pytest.mark.parametrize("spool_dialog", LANGUAGES, indirect=True)
def test_digits_typed_in_the_languages_order_store_an_iso_date(spool_dialog, qt_app):
    """Vom Sonderwert aus getippt: zwei Ziffern je Abschnitt, ohne Trennzeichen."""
    field = spool_dialog.bought_on
    assert field.text() == ""
    assert not field.clear_button.isEnabled()
    field.editor.setFocus()
    QTest.keyClicks(field.editor, _typed(field.editor.displayFormat(), "05", "09", "2026"))
    qt_app.processEvents()
    assert field.text() == "2026-09-05", (field.editor.displayFormat(), field.editor.text())
    assert spool_dialog.entry().bought_on == "2026-09-05"
    assert field.clear_button.isEnabled()


@pytest.mark.parametrize("spool_dialog", LANGUAGES, indirect=True)
def test_single_digits_with_separators_store_the_same_day(spool_dialog, qt_app):
    """„7.3.2025“: Ein Trennzeichen schließt den Abschnitt, die Ziffer verfällt nicht."""
    field = spool_dialog.opened_on
    field.editor.setFocus()
    order = re.findall(r"d+|M+|y+", field.editor.displayFormat())
    parts = {"d": "7", "M": "3", "y": "2025"}
    for index, token in enumerate(order):
        QTest.keyClicks(field.editor, parts[token[0]])
        if index < len(order) - 1:
            QTest.keyClicks(field.editor, ".")
    qt_app.processEvents()
    assert field.text() == "2025-03-07", (field.editor.displayFormat(), field.editor.text())


@pytest.mark.parametrize("spool_dialog", LANGUAGES, indirect=True)
def test_the_way_back_to_unknown_clears_the_stored_date(spool_dialog, qt_app):
    """Der Knopf neben dem Feld setzt zurück; gespeichert würde kein Datum."""
    from app.i18n import tr

    field = spool_dialog.bought_on
    field.setText("2026-09-05")
    assert spool_dialog.entry().bought_on == "2026-09-05"
    QTest.mouseClick(field.clear_button, Qt.MouseButton.LeftButton)
    qt_app.processEvents()
    assert field.text() == ""
    assert field.editor.text() == tr("Unbekannt")
    assert not field.clear_button.isEnabled()
    assert spool_dialog.entry().bought_on == ""
    field.editor.setFocus()
    QTest.keyClicks(field.editor, _typed(field.editor.displayFormat(), "01", "02", "2027"))
    assert spool_dialog.entry().bought_on == "2027-02-01", "nach dem Rückweg tippt es sich neu"
