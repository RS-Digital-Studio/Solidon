"""Fehlertexte mit Nutzernamen wörtlich übergeben, ohne Qt-Fenster."""

from types import SimpleNamespace

import pytest

from app.core.errors import ExternalToolError, ValidationError
from app.ui import dialogs


@pytest.mark.parametrize("error_type", [ExternalToolError, ValidationError])
def test_show_error_passes_user_names_as_explicit_plain_text(monkeypatch, error_type):
    original = dialogs.QMessageBox
    calls = {}

    class MessageBox:
        Icon = original.Icon
        ButtonRole = original.ButtonRole

        def __new__(cls, *args):
            calls["format"] = dialogs.Qt.TextFormat.AutoText
            button = SimpleNamespace(
                setAutoDefault=lambda value: None, setDefault=lambda value: None
            )
            return SimpleNamespace(
                setTextFormat=lambda value: calls.__setitem__("format", value),
                setText=lambda value: calls.__setitem__("text", value),
                setInformativeText=lambda value: calls.__setitem__("detail", value),
                setIcon=lambda value: None,
                setWindowTitle=lambda value: None,
                addButton=lambda *args: button,
                clickedButton=lambda: None,
                exec=lambda: None,
            )

    monkeypatch.setattr(dialogs, "QMessageBox", MessageBox)
    monkeypatch.setattr(dialogs, "offered_actions", lambda *args: ())
    monkeypatch.setattr(dialogs, "unhandled_advice", lambda *args: ())
    title = '<b>Teil</b> & "Name"'
    detail = "  A  B\u00a0C: <i>Objekt</i> & 'Name'\nZweite Zeile"
    error = error_type(title=title, detail=detail)
    assert dialogs.show_error(error, handlers={}) is None
    assert calls["text"] == title
    assert calls["detail"] == detail
    assert calls["format"] == dialogs.Qt.TextFormat.PlainText
