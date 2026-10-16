"""Ein Sperrgrund des Feldes geht dem Satz zur ersten Änderung vor (D2, Review 2 F2a/D).

*Filament entfernen*, gespeichert am ganzen Körper, im Änderungsweg: Geöffnet
wartet *Übernehmen* mit „Erst „Ganzer Körper“ ändern, dann übernehmen.“ Wer den
Haken abwählt, hat genau das getan — die Liste ist dann leer und ungültig, ihr
Wert bleibt der letzte gültige, und der Knopf wiederholte denselben Satz, statt
zu sagen, dass Flächen fehlen.
"""

from __future__ import annotations

import time

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

from app.core.bootstrap import load_operations
from app.core.registry import REGISTRY
from app.i18n import set_language, tr
from app.i18n.catalog import install_language
from app.ui.feature_set_field import FeatureSetField
from app.ui.op_dialog import OperationDialog


def _settle(qt_app: QApplication, rounds: int = 40) -> None:
    for _ in range(rounds):
        qt_app.processEvents()
        time.sleep(0.005)


def test_unticking_the_whole_body_names_the_faces(qt_app: QApplication) -> None:
    load_operations()
    install_language("de")
    set_language("de")
    dialog = OperationDialog(
        REGISTRY.get("clear_filament"),
        {"obj_1": "Quader"},
        None,
        features={"face_1": "Fläche 1 · oben", "face_2": "Fläche 2 · unten"},
        values={"at_features": (), "at_feature": ""},
        promote_values=False,
        changing=True,
    )
    try:
        dialog.show()
        _settle(qt_app)
        button = dialog._accept_button
        field = next(
            editor for editor in dialog._editors.values() if isinstance(editor, FeatureSetField)
        )
        assert not button.isEnabled() and "Ganzer Körper" in button.toolTip(), (
            "Voraussetzung: geöffnet wartet der Knopf auf die erste Änderung"
        )
        assert field.whole is not None
        field.whole.click()
        _settle(qt_app)
        wanted = tr("Flächen markieren oder den ganzen Körper wählen.")
        assert not button.isEnabled()
        assert button.toolTip() == wanted, button.toolTip()
        assert button.accessibleDescription() == wanted
        field.list.item(0).setCheckState(Qt.CheckState.Checked)
        _settle(qt_app)
        assert button.isEnabled(), button.toolTip()
    finally:
        dialog.reject()
        dialog.deleteLater()
