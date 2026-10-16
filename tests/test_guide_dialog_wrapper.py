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


def test_the_probe_in_an_open_list_stays_alive(qt_app: Any) -> None:
    """Die Probe in einer aufgeklappten Liste trifft ein lebendes Widget (FD-175).

    *Neue Ebene …* im Ebenenfeld des Skizzeneditors: Nach dem Aufklappen fand
    ``widget_under`` die Zeile in der Liste, und schon die Mausbewegung darauf brach
    mit „Internal C++ object already deleted“ ab. Der Wrapper des aufgeklappten
    Fensters fiel beim Verlassen der Probe, und mit ihm der Wrapper des Treffers.
    """
    from PySide6.QtCore import QTimer
    from PySide6.QtWidgets import QApplication, QComboBox, QDialog, QVBoxLayout

    from app.ui import guide_targets

    dialog = QDialog()
    field = QComboBox(dialog)
    field.addItems(["Oben", "Vorn", "Neue Ebene …"])
    QVBoxLayout(dialog).addWidget(field)
    seen: list[str] = []

    def look() -> None:
        try:
            field.showPopup()
            QApplication.processEvents()
            for _round in range(3):
                popup = QApplication.activePopupWidget()
                if popup is None:
                    seen.append("keine Liste")
                    return
                point = popup.mapToGlobal(popup.rect().center())
                del popup
                gc.collect()
                hit = guide_targets.widget_under(point)
                gc.collect()
                seen.append(type(hit.mapFromGlobal(point)).__name__ if hit else "nichts")
                del hit
                gc.collect()
        except RuntimeError as error:
            seen.append(f"tot: {error}")
        finally:
            field.hidePopup()
            dialog.reject()

    QTimer.singleShot(200, look)
    dialog.exec()
    dialog.deleteLater()
    qt_app.processEvents()
    assert seen == ["QPoint"] * 3, seen


def test_a_held_window_goes_free_when_the_surface_and_the_case_end(
    qt_app: Any, monkeypatch: Any
) -> None:
    """RC-11: ``_HELD`` und ``_PROBED`` hielten das letzte Fenster über die Fläche hinaus.

    Ein Python-eigener Dialog ohne Elternteil lebte verborgen als Fenster der
    obersten Ebene weiter, bis jemand die Listen leerte; das tat niemand. Jetzt
    geben sie das Ende einer Fläche (``LanguageFlow.close_surfaces``) und das
    Ende eines Falls (``FunctionFlow.finish``) frei.
    """
    import weakref

    from PySide6.QtCore import SIGNAL, SLOT, QObject, QTimer
    from PySide6.QtWidgets import QDialog, QPushButton, QVBoxLayout

    from app.ui import guide_targets
    from tools import function_bench, function_language, function_surface

    window = SimpleNamespace(_op_dialog=None)

    def held_dialog() -> weakref.ref[QDialog]:
        dialog = QDialog()
        QVBoxLayout(dialog).addWidget(QPushButton("OK", dialog))
        dialog.resize(200, 100)

        def look() -> None:
            try:
                held = guide_targets._open_dialog(window)  # type: ignore[arg-type]
                guide_targets.widget_under(held.mapToGlobal(held.rect().center()))
            finally:
                dialog.reject()

        QTimer.singleShot(50, look)
        # Wachhund am Dialog selbst, ohne Python-Verweis auf ihn: nie ein hängender Fall.
        guard = QTimer(dialog)
        guard.setSingleShot(True)
        QObject.connect(guard, SIGNAL("timeout()"), dialog, SLOT("reject()"))
        guard.start(5000)
        del guard
        dialog.exec()
        return weakref.ref(dialog)

    def gone(reference: weakref.ref[QDialog]) -> bool:
        gc.collect()
        qt_app.processEvents()
        return reference() is None

    flow = object.__new__(function_bench.FunctionFlow)
    flow.watch = SimpleNamespace(
        poll=lambda: None, modal_entries=list, raw_entries=list, windows=[]
    )
    flow._timers = []
    flow.data = {}
    flow.persist = lambda: None
    first = held_dialog()
    assert not gone(first), "der Dialog wird gehalten, solange der Fall läuft"
    flow.finish()
    assert gone(first), "nach dem Fall lebt der gehaltene Dialog weiter"
    assert guide_targets._HELD == [] and guide_targets._PROBED == []

    monkeypatch.setattr(function_surface, "windows_to_picture", lambda window: [])
    surface = object.__new__(function_language.LanguageFlow)
    surface.window = window
    second = held_dialog()
    assert not gone(second)
    assert surface.close_surfaces(flow) is True
    assert gone(second), "nach der Fläche lebt der gehaltene Dialog weiter"
