"""Der Hauptknopf eines Speicherdialogs von Qt bleibt ein lebendes Widget (FD-175).

Im Sprachfall von *Export mit Befund* fand ``dialog.accept`` den Knopf
*Speichern* von ``QFileDialog.getSaveFileName``, und gleich danach brach
``parentWidget`` ab: „Internal C++ object already deleted“. Der Dialog lebte;
verfallen war der Wrapper. ``_open_dialog`` holte den modalen Dialog als
Wrapper, der beim Verlassen der Funktion freigegeben wurde, und mit ihm
verfielen die Wrapper seiner Kinder. Jetzt bleibt der Wrapper gehalten, solange
der Dialog offen ist. Offscreen, kein natives Fenster: Der Fall setzt wie der
Prüfstand ``AA_DontUseNativeDialogs``.
"""

from __future__ import annotations

import gc
from types import SimpleNamespace
from typing import Any


def test_the_save_button_of_a_qt_file_dialog_stays_alive(qt_app: Any, tmp_path: Any) -> None:
    from PySide6.QtCore import QCoreApplication, Qt, QTimer
    from PySide6.QtWidgets import QApplication, QFileDialog, QWidget

    from app.ui import guide_targets

    native = QCoreApplication.testAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs)
    QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs, True)
    window = SimpleNamespace(_op_dialog=None)
    parent = QWidget()
    seen: list[str] = []

    def look() -> None:
        try:
            for _round in range(3):
                button = guide_targets.widget_for(window, "dialog.accept")  # type: ignore[arg-type]
                gc.collect()
                # Wie ``_widget_click``: der Weg nach außen über die Vorfahren.
                seen.append(type(button.parentWidget()).__name__)
                del button
                gc.collect()
        except RuntimeError as error:
            seen.append(f"tot: {error}")
        finally:
            modal = QApplication.activeModalWidget()
            if modal is not None:
                modal.reject()

    try:
        for _dialog in range(2):
            QTimer.singleShot(200, look)
            QFileDialog.getSaveFileName(parent, "Exportieren", str(tmp_path / "teil.step"))
    finally:
        QCoreApplication.setAttribute(Qt.ApplicationAttribute.AA_DontUseNativeDialogs, native)
        parent.deleteLater()
        qt_app.processEvents()  # type: ignore[attr-defined]
    assert seen and not [entry for entry in seen if entry.startswith("tot")], seen
