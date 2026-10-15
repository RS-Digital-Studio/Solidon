"""*Objekt umbenennen* beginnt beim jetzigen Namen (FD-114).

Der Dialog stand mit leerem Feld „Name“ da; für eine kleine Änderung tippte
man den ganzen Namen neu. Die Vorgabe setzt ``MainWindow.run_operation`` für
jede Operation, die nur den Namen ändert (``OperationSpec.unchanged_effect``).
"""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from PySide6.QtWidgets import QApplication

from app.core.registry import REGISTRY
from app.core.scene import OperationDraft
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings


@pytest.fixture
def two_bodies(qt_app: QApplication) -> Iterator[MainWindow]:
    window = MainWindow(Session(), UiSettings())
    window._show_start_screen(False)
    window.session.apply(
        "Zwei Körper",
        [
            OperationDraft(op="create_box", params={"name": "Deckel"}),
            OperationDraft(op="create_box", params={"name": "Boden"}),
        ],
    )
    assert window.session.wait_for_idle(60_000)
    QApplication.processEvents()
    yield window
    if window._op_dialog is not None:
        window._op_dialog.reject()
    window.wait_for_workers()
    window.deleteLater()
    QApplication.processEvents()


def _body(window: MainWindow, name: str) -> str:
    result = window.session.last_result
    assert result is not None
    return next(key for key, entry in result.scene.objects.items() if entry.name == name)


def test_rename_offers_the_current_name(
    two_bodies: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(two_bodies, "_wire_preview", lambda *args, **kwargs: None)
    two_bodies.object_tree.select_object(_body(two_bodies, "Boden"))

    two_bodies.run_operation(REGISTRY.get("rename_object"))

    dialog = two_bodies._op_dialog
    assert dialog is not None
    assert dialog.values()["name"] == "Boden"


def test_a_given_name_still_wins(two_bodies: MainWindow, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(two_bodies, "_wire_preview", lambda *args, **kwargs: None)
    two_bodies.object_tree.select_object(_body(two_bodies, "Deckel"))

    two_bodies.run_operation(REGISTRY.get("rename_object"), {"name": "Haube"})

    dialog = two_bodies._op_dialog
    assert dialog is not None
    assert dialog.values()["name"] == "Haube"


def test_rename_waits_for_a_new_name(
    two_bodies: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Übernehmen erst nach einer echten Änderung (RA-13): kein leerer Schritt.

    Mit dem jetzigen Namen vorgegeben legte Enter einen Schritt „Objekt
    umbenennen“ auf denselben Namen an. Dieselbe Regel wie in der Maßgruppe
    (FD-31): grau, und der Satz nennt das Feld.
    """
    from PySide6.QtWidgets import QLineEdit

    monkeypatch.setattr(two_bodies, "_wire_preview", lambda *args, **kwargs: None)
    two_bodies.object_tree.select_object(_body(two_bodies, "Boden"))
    steps = len(two_bodies.session.project.document.ops)

    two_bodies.run_operation(REGISTRY.get("rename_object"))

    dialog = two_bodies._op_dialog
    assert dialog is not None
    button = dialog._accept_button
    assert not button.isEnabled(), "derselbe Name ist nichts zum Übernehmen"
    assert "Name" in button.toolTip() and button.toolTip() == button.accessibleDescription()
    assert not dialog.can_accept()
    field = next(line for line in dialog.findChildren(QLineEdit) if line.text() == "Boden")
    field.setText("Bodenplatte")
    QApplication.processEvents()
    assert button.isEnabled(), "ein neuer Name gibt den Knopf frei"
    field.setText("Boden")
    QApplication.processEvents()
    assert not button.isEnabled(), "zurück auf den alten Namen: wieder nichts zu tun"
    dialog.accept()
    QApplication.processEvents()
    assert len(two_bodies.session.project.document.ops) == steps, "kein leerer Schritt"
