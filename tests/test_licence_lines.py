"""Was die Oberfläche über Frist, Lizenzart und laufende Freischaltung sagt.

Die Zeilen stehen an fünf Stellen — Statusleiste, Über-Dialog,
Freischaltdialog, Ersteinrichtung und die Verabschiedung der Demo —, und die
Fehler darin sieht nur, wer den einen Tag erwischt, an dem sie auftreten.
"""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta

import pytest
from PySide6.QtWidgets import QApplication

from app.branding import PLANNED_SALE_START
from app.core import activation
from app.core.activation import key
from app.core.activation.store import DEMO_UNTIL
from app.ui import dialogs, labels

#: Stichtag und Verkaufsstart kommen aus den Konstanten, die die Anwendung
#: liest: Getippt hielten die Tests den 30.10. und den 01.11. fest, als die
#: Entscheidung längst auf den 30.11. und den 01.12. gewandert war. Die
#: Verkaufsversion trägt ``DEMO_UNTIL = None``; dann steht der Tag vor dem
#: Verkaufsstart als Stichtag der Attrappe, statt die Sammlung abzubrechen.
SALE_DAY = PLANNED_SALE_START.date()
LAST_DAY: date = DEMO_UNTIL or SALE_DAY - timedelta(days=1)


def _demo(days: int) -> activation.Activation:
    return activation.Activation(days_left=days, deadline=LAST_DAY)


@pytest.mark.parametrize("days", [1, 2, 14])
def test_a_single_day_left_reads_as_one_day_not_one_days(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, days: int
) -> None:
    """„Demo — noch 1 Tage" stand am letzten Tag der Demo in der Statusleiste.

    Der Stichtag zählt mit (``store.days_left`` lässt an ihm einen Tag
    übrig), und genau an diesem Tag las jeder Demo-Kunde den Fehler — dazu
    im Über- und im Freischaltdialog, und im Testlauf „Testzeitraum: noch 1
    Tage" an den zwei Tagen, an denen die Zeile überhaupt erscheint.
    """
    from app.core.activation import store

    demo = _demo(days)
    trial = activation.Activation(days_left=days)
    monkeypatch.setattr(activation, "_cached", demo)
    demo_lines = [labels.demo_line(demo), dialogs._licence_line()]
    dialog = dialogs.ActivationDialog()
    try:
        demo_lines.append(dialog.state_label.text())
    finally:
        dialog.deleteLater()
    for line in demo_lines:
        assert "1 Tage" not in line, line
        if days == 1:
            # Der letzte Tag heißt, was er ist (Konzept Demo→1.0 §5, Punkt 3).
            assert "heute letzter Tag" in line, line
            assert labels.calendar_date(LAST_DAY) in line, line
        else:
            assert f"noch {days} Tage" in line, line
    monkeypatch.setattr(store, "TRIAL_FROM", date(2026, 9, 1))
    monkeypatch.setattr(activation, "_cached", trial)
    assert trial.in_trial
    lines = [labels.trial_days(days), labels.trial_days(days, way=True)]
    lines.append(dialogs._licence_line())
    dialog = dialogs.ActivationDialog()
    try:
        lines.append(dialog.state_label.text())
    finally:
        dialog.deleteLater()

    for line in lines:
        assert f"noch {days} " in line, line
        if days == 1:
            assert "1 Tage" not in line, line
            assert "1 Tag" in line, line
        else:
            assert f"{days} Tage" in line, line


@pytest.mark.parametrize("kind", list(key.LicenceKind))
def test_the_activation_dialog_names_the_licence_kind(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, kind: key.LicenceKind
) -> None:
    """Die Lizenzart stand im Über-Dialog und nicht dort, wo die Lizenz steht.

    RM-182 gibt der gewerblichen Lizenz zwei Geräteplätze; wer im
    Freischaltdialog nachsieht, auf welchem Platz er steht, erfuhr nicht,
    welche Art er gekauft hat. Benannt wird auch die private — stünde nur
    „gewerblich" da, wäre ihr Fehlen die Aussage (Regel 18).
    """
    licence = key.Licence(
        major=key.current_major(),
        purchased_on=date(2026, 8, 6),
        order="A-77",
        holder="kaeufer@beispiel.de",
        kind=kind,
    )
    monkeypatch.setattr(activation, "_cached", activation.Activation(licence=licence))
    expected = dialogs.licence_kind_text(kind)
    dialog = dialogs.ActivationDialog()
    try:
        shown = dialog.state_label.text()
    finally:
        dialog.deleteLater()

    assert "A-77" in shown
    assert expected in shown, shown
    assert expected in dialogs._licence_line()


def test_escape_does_not_close_a_running_activation(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Das Fensterkreuz wartete auf die Freischaltung, Esc und *Schließen* nicht.

    ``closeEvent`` hält den Dialog, solange der Server antwortet — aber
    ``QDialog`` schließt über Esc und den Knopf *Schließen* mit ``reject()``,
    und daran kommt kein ``closeEvent`` vorbei. Der Dialog verschwand, die
    Antwort kam in ein verborgenes Fenster, und das Fenster dahinter zeigte
    den alten Zustand.
    """
    import threading

    from PySide6.QtCore import QEvent, Qt
    from PySide6.QtGui import QKeyEvent

    gate = threading.Event()

    class Slow(dialogs.Worker):
        def work(self) -> None:
            gate.wait(10)

    monkeypatch.setattr(activation, "_cached", activation.Activation())
    dialog = dialogs.ActivationDialog()
    try:
        dialog.show()
        worker = Slow()
        dialog._worker = worker
        dialog._leash.start(worker)
        QApplication.sendEvent(
            dialog,
            QKeyEvent(QEvent.Type.KeyPress, Qt.Key.Key_Escape, Qt.KeyboardModifier.NoModifier),
        )
        assert dialog.isVisible(), "Esc schloss den Dialog mitten in der Freischaltung"
        dialog.reject()
        assert dialog.isVisible(), "Schließen schloss den Dialog mitten in der Freischaltung"
        assert "warten" in dialog.state_label.text()
    finally:
        gate.set()
        worker.wait(5000)
        qt_app.processEvents()
        dialog._worker = None
        dialog.reject()
        dialog.release()
        dialog.deleteLater()


@pytest.mark.parametrize(
    ("now", "planned"),
    [
        pytest.param(
            datetime.combine(LAST_DAY + timedelta(days=1), time(0, 30), UTC),
            True,
            id="nach dem letzten Demotag",
        ),
        pytest.param(
            PLANNED_SALE_START - timedelta(minutes=1), True, id="eine Minute vor dem Start"
        ),
        pytest.param(PLANNED_SALE_START, False, id="ab dem geplanten Start"),
    ],
)
def test_the_farewell_of_the_demo_knows_the_pause_before_the_sale(
    qt_app: QApplication, now: datetime, planned: bool
) -> None:
    """„Die aktuelle Version gibt es auf solidon3d.de" — zwischen dem letzten
    Demotag und dem Verkaufsstart gibt es dort keine (RM-061, Konzept Demo→1.0
    §6.2).

    Vor dem geplanten Start nennt der Abschied das Datum, danach verweist er
    auf die Website; die Verfügbarkeit behauptet er nie. Beide sagen, dass
    die Projekte bleiben.
    """
    assert now < PLANNED_SALE_START or not planned
    state = _demo(0)
    text = dialogs.expired_demo_text(state, now)

    assert labels.calendar_date(LAST_DAY) in text or not planned
    assert (labels.calendar_date(SALE_DAY) in text and "10:00" in text) == planned
    assert "solidon3d.de" in text
    assert "aktuelle Version gibt es" not in text
    assert "Projekte bleiben erhalten" in text
    if not planned:
        assert "Lizenz" in text, "nach dem Start: 1.0 braucht eine Lizenz"


@pytest.mark.parametrize(("days", "shown"), [(8, False), (7, True), (1, True), (0, False)])
def test_the_last_demo_week_is_announced_once_per_session(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, days: int, shown: bool
) -> None:
    """In der letzten Woche sagt die Demo einmal je Sitzung, was danach kommt
    (Konzept Demo→1.0 §5, Punkt 2) — als Quittung, nicht als Dialog, und nicht
    ein zweites Mal. Gestellt wird das Datum über die Resttage, so wie
    ``store.days_left`` es eine Woche vor dem Stichtag (sieben) und an ihm
    (einen) ausrechnet."""
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    monkeypatch.setattr(activation, "_cached", _demo(days))
    window = MainWindow(Session(), UiSettings())
    said: list[str] = []
    monkeypatch.setattr(window, "announce", lambda text, **_kw: said.append(text))
    try:
        window._announce_the_sale()
        window._announce_the_sale()
        if not shown:
            assert said == []
            return
        assert len(said) == 1, "einmal je Sitzung"
        text = said[0]
        assert labels.calendar_date(LAST_DAY) in text
        assert labels.calendar_date(SALE_DAY) in text and "10:00" in text
        assert "Projekte bleiben erhalten" in text
        assert "Hilfe → Solidon freischalten" in text
    finally:
        window.close()
