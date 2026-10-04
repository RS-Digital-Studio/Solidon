"""Die Parameterleiste nennt feste Zahlen, die zu Maßen passen; der Dialog wählt (RM-184).

Kern und Bindung prüft ``test_parameter_binding.py``; hier die Oberfläche
daran: ob die Leiste die halb wirkenden Maße erkennbar macht (Dateiaudit §4)
und ob der Dialog nur vorwählt, was ohne Zweifel ist (Regel 21).
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication

from app.core.bootstrap import load_operations
from app.core.scene.parameter_binding import binding_spots
from app.core.types import Document, Profile
from app.ui.main_window import MainWindow
from tests.helpers import dollhouse_document
from tests.ui_helpers import session as session
from tests.ui_helpers import window as window


def test_the_parameter_card_names_fitting_numbers_and_offers_to_bind(
    qt_app: QApplication, document: Document, profile: Profile
) -> None:
    """Die Hauslänge liest nur den Boden; zwei feste Zahlen im Wandring passen zu ihr."""
    from app.core.scene.evaluate import evaluate
    from app.ui.panels import ParameterPanel

    load_operations()
    dollhouse_document(document)
    result = evaluate(document, profile)
    panel = ParameterPanel()
    panel.show_document(document, result)
    assert not panel.bind_button.isHidden()
    assert "feste Zahlen passen zu Projektmaßen" in panel.bind_button.toolTip()
    title = panel._titles["haus_laenge"]
    # Außen 180 = Länge, innen 174 = Länge - 2 * Wand: zwei Stellen.
    assert title.text() == "haus_laenge\n2 feste Zahlen passen"
    assert "passt zu @haus_laenge" in title.toolTip()
    # Ein Maß, das wirkt und zu dem keine feste Zahl passt, behält seine eine
    # Zeile: Die Bodenstärke 4 liest der Boden, sonst steht sie nirgends.
    assert panel._titles["boden"].text() == "boden"
    # Ungenutzt bleibt ungenutzt, auch ohne passende Zahl.
    assert panel._titles["tuer_breite"].text() == "tuer_breite\nNicht verwendet"
    panel.close()


def test_without_fitting_numbers_the_button_stays_away(
    qt_app: QApplication, document: Document, profile: Profile
) -> None:
    """Kein Knopf ohne Anlass — die Karte bleibt so knapp wie vorher."""
    from app.core.scene.evaluate import evaluate
    from app.core.types import Operation, Parameter
    from app.ui.panels import ParameterPanel

    load_operations()
    document.parameters = {"breite": Parameter(name="breite", value=40.0)}
    document.ops = [
        Operation(id=1, op="create_box", params={"width": "@breite"}, outputs=("obj_1",))
    ]
    panel = ParameterPanel()
    panel.show_document(document, evaluate(document, profile))
    assert panel.bind_button.isHidden()
    panel.close()


def test_the_button_binds_the_chosen_numbers_as_one_step(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Weg im Fenster: Knopf, Wahl, eine Transaktion — und ein Undo nimmt sie ganz zurück.

    Der Dialog wird nur bestätigt, nicht bedient: Gebunden wird, was er
    vorwählt — die Fenstermaße (30 = ``fenster``), nicht die Lage y = -58,5,
    die aus zwei Maßen käme.
    """
    from PySide6.QtWidgets import QDialog

    from app.ui.binding_dialog import BindingDialog

    load_operations()
    document = window.session.project.document
    dollhouse_document(document)
    window.session.evaluate_now()
    window._refresh_parameters()
    assert not window.parameters.bind_button.isHidden()
    before = [dict(operation.params) for operation in document.ops]
    count = len(document.transactions)
    monkeypatch.setattr(BindingDialog, "exec", lambda self: QDialog.DialogCode.Accepted)

    window.parameters.bind_button.click()
    assert window.session.wait_for_idle()

    pocket = document.ops[2].params
    assert (pocket["length"], pocket["width"]) == ("@fenster", "@fenster")
    assert pocket["y"] == -58.5
    assert '"distance"' in document.ops[1].params["sketch"]
    assert len(document.transactions) == count + 1
    window.session.undo()
    assert window.session.wait_for_idle()
    assert [dict(operation.params) for operation in document.ops] == before


def test_the_dialog_preselects_only_what_is_certain(
    qt_app: QApplication, document: Document
) -> None:
    """Vorgewählt ist dieselbe Zahl wie genau ein Maß; *Binden* braucht eine Wahl."""
    from app.ui.binding_dialog import BindingDialog

    load_operations()
    spots = binding_spots(dollhouse_document(document))
    dialog = BindingDialog(document, spots)
    chosen = dialog.chosen()
    assert set(chosen) == {spot.key for spot in spots if spot.certain}
    assert all(chosen[spot.key] == spot.choices[0].expression for spot in spots if spot.certain)
    assert dialog.bind_button.isEnabled()
    for check in dialog._checks:
        check.setChecked(False)
    assert not dialog.bind_button.isEnabled()
    assert dialog.bind_button.toolTip() == "Wählen Sie mindestens eine Zahl."
    dialog.deleteLater()
