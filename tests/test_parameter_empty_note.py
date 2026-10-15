"""Der Satz der leeren Parameterleiste misst sich an seiner echten Breite (FD-126).

„Noch keine Parameter. …“ maß seine Höhe einmal beim Bau, an der Grundbreite
der Karte und mit der Schrift von damals (``panels.fit_wrapped``). Mit der
echten Schrift und Spaltenbreite brauchte er mehr, und *Parameter anlegen …*
stand über seiner letzten Zeile. Jetzt ist er ein ``style.WrappedNote``, das
bei jeder Breite neu misst und die Leiste nachziehen lässt.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from app.core.types import Document
from app.ui.style import WrappedNote


def test_the_empty_sentence_claims_its_height_at_every_width(qt_app: QApplication) -> None:
    from app.ui.panels import ParameterPanel

    panel = ParameterPanel()
    try:
        panel.show_document(Document(format_version=1, app_version="0.0.1"))
        panel.show()
        for width in (180, 240, 320):
            panel.resize(width, 400)
            for _round in range(5):
                qt_app.processEvents()
            note = panel._empty
            assert note.minimumHeight() >= note.heightForWidth(note.width()), (
                f"bei {width} Punkten {note.minimumHeight()} statt "
                f"{note.heightForWidth(note.width())}"
            )
            bottom = note.mapTo(panel, note.rect().bottomLeft()).y()
            top = panel.add_button.mapTo(panel, panel.add_button.rect().topLeft()).y()
            assert top >= bottom, f"der Knopf steht über dem Satz ({top} < {bottom})"
            assert isinstance(note, WrappedNote), type(note).__name__
    finally:
        panel.deleteLater()
