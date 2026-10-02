"""Die Importauswahl einer STEP-Baugruppe im Fenster (P7.4).

Der Kunde sieht vor der Übernahme jeden Körper mit Namen, Maßen und Farbe und
wählt, welche er übernimmt; dieselbe Auswahl öffnet später „Diesen Schritt
ändern“. Die Sollwerte stehen im Erzeuger des Korpus.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog, QLabel

from app.core.ingest import plan as ingest_plan
from app.core.registry.params import body_keys
from app.ui.session import Session
from app.ui.step_dialog import StepBodiesDialog, StepBodiesField
from tests.helpers import exact_kernel

exact_kernel()

STEPS = Path(__file__).parent / "data" / "step"


def _until(app: QApplication, condition: Callable[[], bool]) -> None:
    deadline = time.monotonic() + 20
    while not condition() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    assert condition(), "dialog did not reach the expected state"


def _dispose(dialog: StepBodiesDialog, app: QApplication) -> None:
    dialog.release()
    dialog.close()
    dialog.deleteLater()
    app.processEvents()


def _payload(name: str) -> bytes:
    return (STEPS / f"{name}.step").read_bytes()


def test_every_body_of_the_file_is_listed_and_chosen(qt_app: QApplication) -> None:
    chosen = ingest_plan.import_plan("src_1", "instances.step", _payload("instances"))
    dialog = StepBodiesDialog(_payload("instances"), "instances", choices=chosen.choices)
    try:
        assert dialog.bodies.count() == 4
        texts = [dialog.bodies.item(index).text() for index in range(4)]
        assert texts[0].startswith("Grundplatte")
        assert "Bolzen liegend" in texts[2]
        assert dialog.keys() == ["1.1", "1.2", "1.3", "1.4"]
        assert dialog.accept_button.isEnabled()
        assert "4 von 4" in dialog.summary.text()
        # Regel 18: Die Farbe steht auch als Wort im Tooltip, nicht nur im Farbfeld.
        assert dialog.bodies.item(0).toolTip()
        _until(qt_app, lambda: dialog.preview.renderer().isValid())
    finally:
        _dispose(dialog, qt_app)


def test_both_columns_use_the_same_heading_level(qt_app: QApplication) -> None:
    """Körperliste und Baugruppenbild beginnen auf derselben visuellen Stufe."""
    chosen = ingest_plan.import_plan("src_1", "instances.step", _payload("instances"))
    dialog = StepBodiesDialog(_payload("instances"), "instances", choices=chosen.choices)
    try:
        expected = {"Körper", "Lage in der Baugruppe"}
        headings = [label for label in dialog.findChildren(QLabel) if label.text() in expected]
        assert {label.text() for label in headings} == expected
        assert all(label.property("level") == "section" for label in headings)
    finally:
        _dispose(dialog, qt_app)


def test_the_customer_takes_what_he_ticks_and_nothing_is_no_choice(
    qt_app: QApplication,
) -> None:
    chosen = ingest_plan.import_plan("src_1", "nested.step", _payload("nested"))
    dialog = StepBodiesDialog(_payload("nested"), "nested", choices=chosen.choices)
    try:
        dialog.select_none.click()
        assert dialog.keys() == []
        assert not dialog.accept_button.isEnabled()
        dialog.accept()
        assert dialog.result() != QDialog.DialogCode.Accepted
        assert dialog.state.label.text()
        dialog.bodies.item(2).setCheckState(Qt.CheckState.Checked)
        dialog.bodies.item(4).setCheckState(Qt.CheckState.Checked)
        assert body_keys(dialog.values()["bodies"]) == ("1.2.1", "1.3")
        assert "2 von 5" in dialog.summary.text()
        dialog.accept()
        assert dialog.result() == QDialog.DialogCode.Accepted
    finally:
        _dispose(dialog, qt_app)


def test_without_a_plan_the_dialog_reads_the_file_and_restores_the_stored_choice(
    qt_app: QApplication,
) -> None:
    dialog = StepBodiesDialog(
        _payload("multibody"),
        "multibody",
        values={"bodies": ingest_plan.selection(["1#2"])},
    )
    try:
        _until(qt_app, lambda: dialog.bodies.count() == 3)
        assert dialog.keys() == ["1#2"]
        assert dialog.bodies.item(1).text().startswith("Deckel")
    finally:
        _dispose(dialog, qt_app)


def test_the_field_shows_the_choice_and_the_old_single_body(qt_app: QApplication) -> None:
    field = StepBodiesField("")
    assert field.valid and "ein Körper" in field.summary.text()
    field.set_value(ingest_plan.selection(["1.1", "1.2"]))
    assert field.valid and "2" in field.summary.text()
    field.set_value("[]")
    assert not field.valid
    field.deleteLater()


def test_the_session_waits_for_the_choice_and_takes_only_that(
    qt_app: QApplication,
) -> None:
    session = Session()
    session.choose_step_bodies = True
    requests: list[tuple[Any, str, int]] = []
    session.stepImportRequested.connect(lambda *args: requests.append(args))

    session.import_payload_async("instances.step", _payload("instances"))

    assert len(requests) == 1, "die Auswahl steht vor dem ersten Schritt"
    plan, source_id, generation = requests[-1]
    assert len(plan.choices) == 4
    assert not session.history.operations
    session.finish_step_import(source_id, generation, ["1.2", "1.4"])
    assert session.wait_for_idle()
    (operation,) = session.history.operations
    assert body_keys(operation.params["bodies"]) == ("1.2", "1.4")
    assert len(operation.outputs) == 2


def test_cancelling_the_choice_leaves_no_source_behind(qt_app: QApplication) -> None:
    session = Session()
    session.choose_step_bodies = True
    requests: list[tuple[Any, str, int]] = []
    session.stepImportRequested.connect(lambda *args: requests.append(args))

    session.import_payload_async("nested.step", _payload("nested"))
    _plan, source_id, generation = requests[-1]
    session.finish_step_import(source_id, generation, None)

    assert not session.history.operations
    assert source_id not in session.project.document.sources
    assert source_id not in session.project.sources


def test_a_file_with_one_body_asks_nothing(qt_app: QApplication) -> None:
    session = Session()
    session.choose_step_bodies = True
    requests: list[tuple[Any, str, int]] = []
    session.stepImportRequested.connect(lambda *args: requests.append(args))

    session.import_payload_async("inch.step", _payload("inch"))

    assert not requests
    assert session.wait_for_idle()
    assert len(session.history.operations) == 1
