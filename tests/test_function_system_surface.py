"""Ein Dateidialog ist eine Systemfläche: nicht nach G2 und Z6 gemessen (FD-122, RM-737).

Der Fallprozess erzwingt Qts eigenen Dateidialog (``file_acceptance.no_native_dialogs``),
weil sich der des Systems nicht bedienen lässt. Gemessen wurde damit ein Fenster,
das der Kunde nie sieht: englische Teile, gekürzte Spalten, Abstände 6 und 11 und
eine Rollleiste wurden zu Funden an *Andere Datei wählen* und *Als Netz
exportieren* (Lauf 043). Den echten Dialog prüft Stufe C am System; Z5 nimmt
``QFileDialog`` ohnehin aus.
"""

from __future__ import annotations

from typing import Any

from tools import function_bench, function_surface
from tools.function_protocol import empty_protocol
from tools.function_setup import Variant


def _flow() -> Any:
    flow = object.__new__(function_bench.FunctionFlow)
    flow.row = {"id": "finding.action:choose_another_file", "target": "x"}
    flow.data = empty_protocol(flow.row, {}, {})
    flow.restless = None
    flow.variant = Variant.of({"set": "sprachen"})
    flow.window = None
    return flow


def test_a_file_dialog_is_a_system_surface_and_not_measured(qt_app: Any) -> None:
    from PySide6.QtWidgets import QFileDialog

    dialog = QFileDialog()
    try:
        assert function_surface.system_surface(dialog) == "QFileDialog"
        flow = _flow()
        flow.capture_surface(dialog)
        for name in function_bench.SURFACE_FIELDS:
            assert "Systemfläche" in flow.data["unmeasured"].get(name, ""), name
            assert not flow.data.get(name), name
    finally:
        dialog.deleteLater()


def test_an_own_dialog_is_measured(qt_app: Any, monkeypatch: Any) -> None:
    """Gegenprobe: ein Dialog der Anwendung ist keine Systemfläche und wird gemessen."""
    from PySide6.QtWidgets import QDialog, QLabel, QVBoxLayout

    from tools import function_capture

    dialog = QDialog()
    QVBoxLayout(dialog).addWidget(QLabel("Bohrung ändern", dialog))
    dialog.show()
    try:
        assert function_surface.system_surface(dialog) == ""
        monkeypatch.setattr(function_capture, "empty_states", lambda window: [])
        flow = _flow()
        flow.window_size = lambda: [800, 600]  # type: ignore[method-assign]
        flow.capture_surface(dialog)
        assert "texts" not in flow.data["unmeasured"]
        assert flow.data["texts"], flow.data["unmeasured"]
    finally:
        dialog.hide()
        dialog.deleteLater()
