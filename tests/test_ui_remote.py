"""Fernsteuerung: Herkunft, Antwort, Zeitgrenzen und Transaktionen am Fenster (§26.4)."""

from __future__ import annotations

import pytest

pytest.importorskip("PySide6")


from app.core.agent.tools import UNDO_TRANSACTION
from app.core.scene import OperationDraft
from app.ui.main_window import REMOTE_ORIGIN, MainWindow
from app.ui.settings import UiSettings
from tests.ui_helpers import session as session
from tests.ui_helpers import window as window


def test_a_remote_call_is_one_transaction_the_window_can_undo(window: MainWindow) -> None:
    """Die vierte Auflage, und die einzige, die nur am Dokument prüfbar ist.

    Ein Fernaufruf geht denselben Weg wie ein Menüklick: dieselbe Transaktion,
    dieselbe Auswertung, dasselbe Undo. Wäre es ein zweiter Weg ins Dokument,
    stünde hier ein Körper, den kein Strg+Z wegbekommt — und niemand wüsste,
    woher er kam.
    """
    answer = window.run_remote("create_box", {"width": 20.0, "depth": 20.0, "height": 20.0})
    assert "Objekte" in answer

    document = window.session.project.document
    assert [entry.op for entry in document.ops] == ["create_box"]
    assert len(document.transactions) == 1

    window.action_undo()
    window.session.wait_for_idle()
    assert window.session.project.document.ops == []


def test_a_remote_timeout_never_reports_an_old_result_as_finished(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein abgelaufener Fernaufruf darf keinen alten Szenenstand als Erfolg melden."""

    monkeypatch.setattr(window.session, "apply", lambda *args, **kwargs: None)
    monkeypatch.setattr(window.session, "wait_for_idle", lambda timeout_ms: False)

    answer = window.run_remote("create_box", {"width": 20.0, "depth": 20.0, "height": 20.0})

    assert "rechnet noch" in answer
    assert "fertig" not in answer


def test_a_remote_orientation_analysis_is_the_chat_answer_computed_off_the_window(
    window: MainWindow,
) -> None:
    """RM-144: dieselbe Analyse über Chat und MCP — ohne Transaktion und ohne Hauptthread.

    Der Fernaufruf gab bis zum 22.09.2026 nur einen Satz zurück, die
    Orientierungssuche hielte das Fenster an. Jetzt nimmt der Hauptthread
    einen Schnappschuss und gibt die Rechnung an den Faden des Servers.
    """
    from app.core.agent.analysis import analysis_text
    from app.core.scene.cancel import CancelSignal

    window.run_remote("create_box", {"width": 30.0, "depth": 10.0, "height": 40.0})
    before = len(window.session.project.document.transactions)
    result = window.session.last_result
    assert result is not None

    prepared = window.run_remote("read_analysis", {"kind": "orientation"})

    assert callable(prepared), "gerechnet wird nicht im Hauptthread"
    answer = prepared(CancelSignal())
    chat = analysis_text(
        "orientation",
        result.scene,
        window.session.project.document,
        window.session.profile,
        cancelled=CancelSignal(),
    )
    assert answer == chat, "Chat und MCP sagen dasselbe"
    assert answer.startswith("Herkunft") or "Schichtanalyse" in answer.splitlines()[0]
    assert len(window.session.project.document.transactions) == before, "lesend, kein Schritt"


def test_a_remote_call_says_where_it_came_from(window: MainWindow) -> None:
    """Der Herkunftsvermerk (§26.4).

    Wer hinterher fragt „habe ich das getan?", bekommt eine Antwort statt einer
    Vermutung. Ohne den Vermerk sähe ein Fernaufruf im Verlauf aus wie ein
    eigener Klick.
    """
    window.run_remote("create_box", {"width": 10.0, "depth": 10.0, "height": 10.0})
    origin = window.session.project.document.transactions[0].origin
    assert origin is not None
    assert origin.by == "agent"
    assert origin.model == REMOTE_ORIGIN


def test_scene_views_render_labelled_pngs(window: MainWindow) -> None:
    """§23: zwei beschriftete Ansichten als PNG — gerendert von einem
    kurzlebigen Renderer ohne Fenster, der den sichtbaren Viewport nicht
    anfasst.
    """
    from app.ui.snapshots import scene_views

    window.run_remote("create_box", {"width": 20.0, "depth": 20.0, "height": 20.0})
    result = window.session.last_result
    assert result is not None

    views = scene_views(result.scene)

    assert len(views) == 2
    labels = [label for label, _image in views]
    assert any("oben" in label for label in labels)
    for _label, image in views:
        assert image.startswith(b"\x89PNG"), "echte PNG-Bytes, kein rohes Array"

    from app.core.types import Scene

    assert scene_views(Scene()) == (), "eine leere Szene hat nichts zu zeigen"


def test_a_remote_value_that_is_no_number_is_an_answer_not_a_crash(window: MainWindow) -> None:
    """Konzept Agent-Vertiefung 2.4: die Fernsteuerung rief ``float()``
    ungeprüft — ein „abc" von außen war ein Programmfehler statt einer
    Meldung. Jetzt prüft ``parse_number``, dieselbe Funktion wie im Chat.
    """
    from app.core.agent.tools import ADD_PARAMETER

    answer = window.run_remote(ADD_PARAMETER, {"name": "breite", "value": "abc"})

    assert "keine Zahl" in answer
    assert window.session.project.document.transactions == []
    assert "breite" not in window.session.project.document.parameters


def test_the_remote_report_filters_from_a_severity_upwards(window: MainWindow) -> None:
    """Konzept Agent-Vertiefung 2.4: „ab dieser Schwere", wie das
    Werkzeugschema sagt — die Fernsteuerung filterte exakt und lieferte auf
    ``warning`` keine Fehler. Jetzt antwortet ``report_text``, dieselbe
    Funktion wie im Chat.
    """
    from app.core.agent.session import report_text
    from app.core.types import Finding, Report, Scene

    scene = Scene()
    scene.report = Report(
        (
            Finding(code="a", severity="info", message="Hinweis"),
            Finding(code="b", severity="warning", message="Warnung"),
            Finding(code="c", severity="error", message="Fehler"),
        )
    )

    text = report_text(scene, "warning")

    assert "Warnung" in text
    assert "Fehler" in text, "eine Frage nach Warnungen unterschlägt keine Fehler"
    assert "Hinweis" not in text


def test_the_remote_interface_stays_off_unless_it_is_switched_on(window: MainWindow) -> None:
    """Die erste Auflage: aus, bis jemand sie einschaltet.

    Eine offene Schnittstelle, die niemand eingeschaltet hat, stünde auf jedem
    Rechner offen, auf dem die Anwendung installiert ist. Geprüft an der
    Vorgabe **und** am Fenster, denn eine Vorgabe, die beim Start überschrieben
    wird, ist keine.
    """
    assert UiSettings().remote_enabled is False
    window._apply_remote()
    assert window._remote is None


def test_switching_it_on_binds_only_to_this_machine(window: MainWindow) -> None:
    """Und die zweite: nur 127.0.0.1.

    Am gebundenen Sockel geprüft, nicht an der Absicht — eine Konstante sagt
    nichts darüber, woran wirklich gebunden wurde.
    """
    window.settings.remote_enabled = True
    window.settings.remote_port = 0
    window._apply_remote()
    try:
        assert window._remote is not None
        assert window._remote.running
        server = window._remote._server
        assert server is not None
        assert server.server_address[0] == "127.0.0.1"
    finally:
        window.settings.remote_enabled = False
        window._apply_remote()
    assert window._remote is None


def test_a_blocked_port_says_so_instead_of_only_logging(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regel 17: Ein belegter Port endete im Protokoll und sonst nirgends.

    Der Haken in den Einstellungen blieb gesetzt, die Fernsteuerung lief
    nicht, und nichts sagte es — wer ein fremdes Programm darauf zeigen ließ,
    suchte den Fehler dort. Die Meldung nennt den Port und den Weg zurück zu
    ihm; ein modaler Dialog wäre hier die falsche Antwort (§2.8).
    """
    from app.ui import main_window as module

    def refuse(*_args: object, **_kwargs: object) -> object:
        raise OSError("address already in use")

    monkeypatch.setattr(module, "RemoteServer", refuse)
    window.settings.remote_enabled = True
    window.settings.remote_port = 5123
    try:
        window._apply_remote()
    finally:
        window.settings.remote_enabled = False

    assert window._remote is None, "die Fernsteuerung gilt trotz Fehler als gestartet"
    said = window.status_message.text()
    assert "5123" in said, f"die Meldung nennt den Port nicht: {said!r}"
    assert "Einstellungen" in said, f"die Meldung nennt keine Handlung: {said!r}"


def test_a_remote_undo_takes_the_transaction_it_was_asked_for(window: MainWindow) -> None:
    """Der Fernaufruf liest seine Kennung, statt blind das Oberste zu nehmen.

    ``run_remote`` rief ``session.undo()`` **ohne Argument**: Ein Aufruf für
    ``t1`` nahm ``t7`` zurück und meldete „Zurückgenommen.", eine unbekannte
    Kennung meldete ebenfalls Erfolg. Das Schema nennt die Kennung als
    erforderlich, und der Chatweg löst sie seit je auf — nur die Leitung
    tat es nicht (Sicherheitsdurchsicht 04.09.2026, Fix solidon-e9).

    Zurückgenommen wird **nur die oberste**, und das ist strenger als der
    Chatweg, der über ``sweep_for`` auch jüngere mitnimmt: Ein Aufruf, eine
    Transaktion (Regel 16). Wer mehr will, ruft mehrfach.
    """
    session = window.session
    session.apply("Erster", [OperationDraft(op="create_box", inputs=(), params={})])
    session.wait_for_idle()
    session.apply("Zweiter", [OperationDraft(op="create_box", inputs=(), params={})])
    session.wait_for_idle()

    known = [entry.id for entry in session.project.document.transactions]
    assert len(known) == 2, "zwei Transaktionen, sonst prüft der Test nichts"

    # Eine unbekannte Kennung nimmt nichts zurück — und sagt das.
    answer = window.run_remote(UNDO_TRANSACTION, {"transaction": "gibt-es-nicht"})
    assert "gibt-es-nicht" in answer
    assert [entry.id for entry in session.project.document.transactions] == known

    # Die untere von zwei liegt nicht obenauf. Vorher traf dieser Aufruf die
    # obere und meldete Erfolg.
    answer = window.run_remote(UNDO_TRANSACTION, {"transaction": known[0]})
    assert [entry.id for entry in session.project.document.transactions] == known, (
        "was nicht obenauf liegt, bleibt unberührt"
    )

    # Die oberste geht, und die Antwort nennt sie.
    answer = window.run_remote(UNDO_TRANSACTION, {"transaction": known[-1]})
    assert known[-1] in answer
    assert [entry.id for entry in session.project.document.transactions] == known[:1]
