"""Fehlertexte mit Nutzernamen wörtlich übergeben, ohne Qt-Fenster."""

from types import SimpleNamespace

import pytest

from app.core.errors import ExternalToolError, ValidationError
from app.ui import dialogs


@pytest.mark.parametrize("error_type", [ExternalToolError, ValidationError])
def test_show_error_passes_user_names_as_explicit_plain_text(monkeypatch, error_type):
    """Titel und Detail kommen unverändert im Meldungsdialog an (FD-21).

    Der Dialog selbst setzt beide Zeilen als Klartext (``MessageDialog``,
    geprüft am Fenster in ``test_message_dialog_keeps_text_plain``); hier wird
    geprüft, dass ``show_error`` nichts davon umschreibt.
    """
    calls = {}

    class MessageDialog:
        def __init__(self, parent=None, **values):
            calls.update(values)

        def add_action(self, *args, **values):
            raise AssertionError("ohne Handler bietet show_error keine Handlung an")

        def add_exit(self, label, name):
            calls["exit"] = label
            return SimpleNamespace()

        def exec(self):
            return 0

        def clicked_button(self):
            return None

        def deleteLater(self):  # noqa: N802 - Qt-Name
            calls["freed"] = True

    monkeypatch.setattr(dialogs, "MessageDialog", MessageDialog)
    monkeypatch.setattr(dialogs, "offered_actions", lambda *args: ())
    monkeypatch.setattr(dialogs, "unhandled_advice", lambda *args: ())
    title = '<b>Teil</b> & "Name"'
    detail = "  A  B C: <i>Objekt</i> & 'Name'\nZweite Zeile"
    error = error_type(title=title, detail=detail)
    assert dialogs.show_error(error, handlers={}) is None
    assert calls["headline"] == title
    assert calls["body"] == detail
    assert calls["kind"] == "error"
    assert calls["target"] == "message:error"
    # Ohne Handlung gibt es nichts abzubrechen (RM-771): Der Ausgang heißt *Schließen*.
    assert calls["exit"] == dialogs.tr("Schließen")
    assert calls["freed"], "nach exec gibt show_error den Dialog frei (A-L1)"


@pytest.mark.parametrize(
    ("line", "error_type"),
    [
        ("damaged_line", "InstallationDamaged"),
        ("deactivation_pending_line", "DeviceDeactivationPending"),
    ],
)
def test_a_licence_line_joins_title_and_detail_like_the_error(monkeypatch, line, error_type):
    """Die Zeilen des Freischaltdialogs fügen Titel und Detail wie ``str(error)`` (B-L7).

    Eine eigene Fügung ``f"{title} {detail}"`` verlor den Doppelpunkt hinter
    einem Titel ohne Satzzeichen; ``errors.title_and_detail`` ist die eine Quelle.
    """
    from app.core import errors

    kind = getattr(errors, error_type)
    monkeypatch.setattr(kind, "default_title", "Titel ohne Satzzeichen")
    assert getattr(dialogs, line)() == str(kind())
