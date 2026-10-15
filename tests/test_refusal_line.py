"""Die gefaltete Sperrzeile sagt, dass die genannten Handlungen hier nicht gehen (FD-138).

Am Zapfen stand „Zum Langloch ziehen — Gezogen wird ein Loch, …“, an einer
Fläche „Merkmal ändern, …, verdoppeln und entfernen — Eine Fläche ist …“: eine
Aufzählung von Handlungen, ein Gedankenstrich, ein großgeschriebener Satz. Wer
das liest, erfährt nicht, dass die genannten Handlungen hier fehlen. Die Zeile
beginnt jetzt mit der Absage, und der Grund folgt als eigener Satz — in jeder
Sprache aus einem Katalogsatz.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QLabel

from app.core.perceive.actions import FeatureAction
from app.i18n import get_language, set_language, tr
from app.i18n.catalog import install_language
from app.ui.panels import FeaturePanel

REASON = "Gezogen wird ein Loch, und ein Zapfen ist Material."


@pytest.mark.parametrize("language", ["de", "en", "es", "fr", "it", "pt"])
def test_a_refused_row_starts_with_the_refusal(qt_app: QApplication, language: str) -> None:
    before = get_language()
    install_language(language)
    set_language(language)
    panel = FeaturePanel()
    try:
        refused = FeatureAction(title="Zum Langloch ziehen", op=None, reason=REASON)
        row = panel._build_action(refused)
        (text,) = [label.text() for label in row.findChildren(QLabel)]
        wanted = tr(
            "Hier nicht möglich: {actions}. {reason}", actions="Zum Langloch ziehen", reason=REASON
        )
        if language != "de":
            assert not wanted.startswith("Hier nicht möglich"), "der Katalog wirkt nicht"
        assert text == wanted, text
        assert text.index("Zum Langloch ziehen") < text.index(REASON), text
        assert " — " not in text, f"Gedankenstrich vor einem großen Satz: {text}"
    finally:
        panel.deleteLater()
        set_language(before)
