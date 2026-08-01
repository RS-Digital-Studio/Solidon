"""Der Chat im Fenster (Bauplan §26.3, §26.5, §27).

Offscreen: geprüft wird die Kopplung, nicht das Layout. Sieht ein
zurückgenommener Beitrag zurückgenommen aus, wartet ein Vorschlag auf eine
Entscheidung, und hält sich das Ganze heraus, wenn es kein Modell gibt.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication

from app.core.backends.llm import Reply, ToolCall
from app.core.backends.scripted import ScriptedBackend
from app.core.types import ChatEntry, Origin
from app.ui.chat import ChatPanel, describe
from app.ui.main_window import MainWindow
from app.ui.session import ProposalPreview, Session
from app.ui.settings import UiSettings

MESHES = Path(__file__).parent / "data" / "meshes"


@pytest.fixture
def window(qt_app: QApplication) -> MainWindow:
    made = MainWindow(Session(), UiSettings())
    made.open_path(MESHES / "plate_holes.stl")
    made.session.wait_for_idle()
    return made


def scripted(window: MainWindow, *answers: Reply) -> ScriptedBackend:
    backend = ScriptedBackend(answers=list(answers))
    window.session.set_agent_backend(backend)
    return backend


# --- the panel --------------------------------------------------------------------


def test_without_a_model_the_chat_says_so_once(qt_app: QApplication) -> None:
    """§27: die Agentenfunktionen grauen aus, alles andere läuft weiter."""
    panel = ChatPanel()
    panel.set_available(False)

    assert not panel.input.isEnabled()
    assert not panel.send.isEnabled()
    assert "Sprachmodell" in panel.hint.text()


def test_with_a_model_the_line_is_open(qt_app: QApplication) -> None:
    panel = ChatPanel()
    panel.set_available(True, "scripted:test")

    assert panel.input.isEnabled()
    assert "scripted:test" in panel.hint.text()


def test_while_the_agent_thinks_nothing_more_is_sent(qt_app: QApplication) -> None:
    panel = ChatPanel()
    panel.set_available(True, "x")
    panel.set_busy(True)

    assert not panel.send.isEnabled()

    panel.set_busy(False)
    assert panel.send.isEnabled()


def test_a_taken_back_turn_is_struck_through(window: MainWindow) -> None:
    """§26.3: verworfen, nicht gelöscht — er ist passiert, er gilt nur nicht."""
    document = window.session.project.document
    document.chat.append(ChatEntry(id="c1", role="user", text="Bohr ein Loch"))
    document.chat.append(ChatEntry(id="c2", role="agent", text="Erledigt", transaction_id="t99"))

    window.chat.show_document(document)

    assert window.chat.turns.count() == 2
    first: QFont = window.chat.turns.item(0).font()
    second: QFont = window.chat.turns.item(1).font()
    assert not first.strikeOut()
    assert second.strikeOut(), "the turn of a transaction that is gone is struck through"
    assert "Erledigt" in window.chat.turns.item(1).text(), "the text stays readable"


def test_a_turn_names_its_transaction(window: MainWindow) -> None:
    document = window.session.project.document
    active = document.transactions[0].id
    document.chat.append(
        ChatEntry(
            id="c1",
            role="agent",
            text="Geladen",
            transaction_id=active,
            origin=Origin(by="agent", model="scripted:test"),
        )
    )

    window.chat.show_document(document)

    tip = window.chat.turns.item(0).toolTip()
    assert active in tip
    assert "scripted:test" in tip


# --- a proposal -------------------------------------------------------------------


def test_a_proposal_waits_for_a_decision(window: MainWindow) -> None:
    """§26.5: Vorschlag, Differenzansicht, dann annehmen oder verwerfen — nie
    von selbst.
    """
    scripted(
        window,
        Reply(
            tool_calls=(
                ToolCall(
                    id="1", name="translate_object", arguments={"objects": ["obj_1"], "dx": 5.0}
                ),
            )
        ),
        Reply(text="Ich habe die Platte verschoben."),
    )
    ops_before = len(window.session.project.document.ops)

    window.chat.input.setPlainText("Schieb die Platte 5 mm")
    window.chat._send()
    window.session.wait_for_idle()
    qt_app_process(window)

    assert window._proposal is not None
    assert window.chat.decision.isVisible() or not window.right.isVisible()
    assert len(window.session.project.document.ops) == ops_before, "nothing applied yet"


def test_accepting_makes_it_one_transaction(window: MainWindow) -> None:
    scripted(
        window,
        Reply(
            tool_calls=(
                ToolCall(
                    id="1", name="translate_object", arguments={"objects": ["obj_1"], "dx": 5.0}
                ),
            )
        ),
        Reply(text="Verschoben."),
    )
    transactions_before = len(window.session.project.document.transactions)

    window.chat.input.setPlainText("Schieb")
    window.chat._send()
    qt_app_process(window)
    window.chat.accepted.emit()
    window.session.wait_for_idle()

    document = window.session.project.document
    assert len(document.transactions) == transactions_before + 1
    assert document.transactions[-1].origin.by == "agent"
    assert window._proposal is None
    assert [entry.role for entry in document.chat] == ["user", "agent"]


def test_discarding_keeps_the_conversation(window: MainWindow) -> None:
    scripted(window, Reply(text="Ich würde nichts ändern."))

    window.chat.input.setPlainText("Was meinst du?")
    window.chat._send()
    qt_app_process(window)
    window.chat.discarded.emit()

    document = window.session.project.document
    assert len(document.chat) == 2
    assert document.chat[-1].transaction_id is None
    assert window.viewport.difference is None


def test_the_key_dialog_never_shows_a_stored_key(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§27: der Schlüssel lebt im Schlüsselbund. Ein Dialog, der ihn
    zurückspiegelte, brächte ihn auf den Bildschirm, in einen Screenshot, in
    einen Fehlerbericht.
    """
    from app.core.backends import keys
    from app.ui.dialogs import KeyDialog

    monkeypatch.setattr(keys, "_keyring", lambda: None)
    dialog = KeyDialog()

    assert dialog.field.text() == "", "nothing stored is ever put back into the field"
    assert dialog.field.echoMode() == dialog.field.EchoMode.Password


def test_the_key_dialog_names_the_state(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    from PySide6.QtWidgets import QLabel

    from app.core.backends import keys
    from app.ui.dialogs import KeyDialog

    monkeypatch.setattr(keys, "_keyring", lambda: None)
    monkeypatch.delenv(keys.ENVIRONMENT_VARIABLE, raising=False)
    monkeypatch.delenv(f"{keys.ENVIRONMENT_VARIABLE}_ANTHROPIC", raising=False)

    dialog = KeyDialog()
    text = " ".join(label.text() for label in dialog.findChildren(QLabel))

    assert "kein Schlüssel" in text
    assert "Schlüsselbund" in text


def test_the_summary_names_what_would_change(qt_app: QApplication) -> None:
    from app.core.agent.proposal import Proposal
    from app.core.geom.difference import Difference, SceneDifference

    difference = SceneDifference()
    difference.entries["obj_1"] = Difference(
        object_id="obj_1", added_volume=2000.0, removed_volume=500.0
    )
    proposal = Proposal(request="x")
    proposal.drafts.append(object())  # type: ignore[arg-type]

    text = describe(ProposalPreview(proposal=proposal, difference=difference))

    assert "Operation" in text
    assert "+2.00 cm³" in text
    assert "-0.50 cm³" in text


def qt_app_process(window: MainWindow) -> None:
    """Die Signale des Arbeiters ankommen lassen — der Agent läuft in seinem
    eigenen Thread.
    """
    import time

    application = QApplication.instance()
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        if application is not None:
            application.processEvents()
        if window._proposal is not None:
            return
        time.sleep(0.01)
