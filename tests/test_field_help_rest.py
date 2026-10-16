"""Die letzten Fachfelder ohne Hilfe sagen in Kurzhilfe und Beschreibung, was sie tun (FD-78).

Analyse- und Teilenleiste hat F4 versorgt (``test_bar_field_sentences.py``).
Übrig waren drei Felder: „Beschreibung“ im Generator, der Haken
„Werte mitgeben“ im Hinweis zum Herstellerprofil und die Variantenwahl
„Typ“ im Operationsdialog. Ein Bildschirmleser liest die Beschreibung, das
Auge die Kurzhilfe; beide brauchen denselben Satz.
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtWidgets import QApplication, QComboBox

from app.core.registry import REGISTRY
from app.ui.generate_dialog import GenerateDialog
from app.ui.main_window import MainWindow
from app.ui.print_disclosure import PrintDisclosureDialog
from app.ui.session import Session
from app.ui.settings import UiSettings
from tests.scripted_backend import ScriptedMeshBackend


def _both(widget: object) -> tuple[str, str]:
    return widget.toolTip(), widget.accessibleDescription()  # type: ignore[attr-defined]


def test_the_description_of_the_generator_says_what_it_is_for(qt_app: QApplication) -> None:
    dialog = GenerateDialog(backend=ScriptedMeshBackend())
    try:
        assert dialog.wait_for_readiness(5000)
        qt_app.processEvents()
        tip, description = _both(dialog.prompt)
        assert tip and tip == description, (tip, description)

        # Mit Bild ruht das Feld und sagt warum; ohne Bild gilt der Satz wieder.
        dialog._show_image(b"bild", "bild.png")
        assert dialog.prompt.toolTip() != tip
        dialog.clear_image()
        assert _both(dialog.prompt) == (tip, description)
    finally:
        dialog.release()
        dialog.deleteLater()


def test_the_share_box_carries_its_sentence(qt_app: QApplication) -> None:
    dialog = PrintDisclosureDialog(share=True)
    try:
        tip, description = _both(dialog.share)
        assert tip and tip == description
        assert "3MF" in tip, "der Satz unter dem Haken, nicht ein neuer"
    finally:
        dialog.deleteLater()


@pytest.fixture
def empty_window(qt_app: QApplication) -> Iterator[MainWindow]:
    window = MainWindow(Session(), UiSettings())
    window._show_start_screen(False)
    yield window
    if window._op_dialog is not None:
        window._op_dialog.reject()
    window.wait_for_workers()
    window.deleteLater()
    qt_app.processEvents()


def test_the_variant_choice_explains_itself_to_both_channels(
    empty_window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(empty_window, "_wire_preview", lambda *args, **kwargs: None)
    empty_window.run_operation(REGISTRY.get("sketch_extrude"))
    dialog = empty_window._op_dialog
    assert dialog is not None
    choice = next(
        box for box in dialog.findChildren(QComboBox) if box.findData("sketch_pocket") >= 0
    )
    tip, description = _both(choice)
    assert tip and tip == description, (tip, description)
