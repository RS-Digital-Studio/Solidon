"""Der Chat im Fenster (Bauplan §26.3, §26.5, §27).

Offscreen: geprüft wird die Kopplung, nicht das Layout. Sieht ein
zurückgenommener Beitrag zurückgenommen aus, wartet ein Vorschlag auf eine
Entscheidung, und hält sich das Ganze heraus, wenn es kein Modell gibt.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

from PySide6.QtGui import QFont
from PySide6.QtWidgets import QApplication, QPushButton

from app.core.backends.llm import Reply, ToolCall
from app.core.backends.scripted import ScriptedBackend
from app.core.scene.project import new_project
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


# --- die Leiste -------------------------------------------------------------------


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


# --- ein Vorschlag ----------------------------------------------------------------


def test_a_proposal_waits_for_a_decision(window: MainWindow) -> None:
    """§26.5 mit abgeschalteter Übernahme: Vorschlag, Differenzansicht, dann
    annehmen oder verwerfen — die Präferenz stellt das alte Verhalten her.
    """
    window.settings.auto_accept_reversible = False
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
    # isVisibleTo statt isVisible: offscreen ohne show() ist isVisible()
    # konstant False, und die Zusicherung wäre eine Tautologie.
    assert window.chat.decision.isVisibleTo(window.chat)
    assert len(window.session.project.document.ops) == ops_before, "nothing applied yet"


def test_accepting_makes_it_one_transaction(window: MainWindow) -> None:
    window.settings.auto_accept_reversible = False
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


def test_a_reversible_proposal_is_applied_without_asking(window: MainWindow) -> None:
    """§26.5, Regel 19: eindeutig umkehrbare Vorschläge laufen automatisch —
    die Leiste wird zur Übernommen-Leiste mit dem Weg zurück, und der eine
    Knopf nimmt dieselbe Transaktion wie Strg+Z.
    """
    import time

    assert window.settings.auto_accept_reversible, "die Vorgabe ist an"
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

    window.chat.input.setPlainText("Schieb die Platte 5 mm")
    window.chat._send()
    application = QApplication.instance()
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        if application is not None:
            application.processEvents()
        if len(window.session.project.document.transactions) > transactions_before:
            break
        time.sleep(0.01)
    window.session.wait_for_idle()

    document = window.session.project.document
    assert len(document.transactions) == transactions_before + 1
    assert window._proposal is None, "es gibt nichts mehr zu entscheiden"
    # isVisibleTo statt isVisible — siehe oben: offscreen wäre alles False.
    assert window.chat.undo_button.isVisibleTo(window.chat)
    assert not window.chat.accept_button.isVisibleTo(window.chat)
    assert "Übernommen" in window.chat.summary.text()

    window.chat.undoRequested.emit()
    window.session.wait_for_idle()
    assert len(window.session.project.document.transactions) == transactions_before


def test_only_harmless_proposals_run_by_themselves(window: MainWindow) -> None:
    """Die vier Bedingungen aus §26.5, am Kern geprüft: nicht umkehrbar,
    Warnung, Rückfrage, angehaltener Lauf oder eine Rücknahme — jede einzelne
    verhindert die automatische Übernahme.
    """
    from app.core.agent import apply as agent_apply
    from app.core.agent.proposal import Proposal, Question
    from app.core.scene.history import OperationDraft
    from app.core.types import Finding

    good = Proposal(request="x")
    good.drafts.append(OperationDraft(op="translate_object", params={"dx": 1.0}))
    assert agent_apply.auto_acceptable(good)

    empty = Proposal(request="x")
    assert not agent_apply.auto_acceptable(empty), "nichts anzuwenden heißt nichts übernehmen"

    asked = Proposal(request="x")
    asked.drafts.append(OperationDraft(op="translate_object", params={"dx": 1.0}))
    asked.questions.append(Question(text="Welches?"))
    assert not agent_apply.auto_acceptable(asked), "wer fragte, dessen Ergebnis wird angesehen"

    warned = Proposal(request="x")
    warned.drafts.append(OperationDraft(op="translate_object", params={"dx": 1.0}))
    warned.findings.append(Finding(code="a", severity="warning", message="dünn"))
    assert not agent_apply.auto_acceptable(warned)

    stopped = Proposal(request="x")
    stopped.drafts.append(OperationDraft(op="translate_object", params={"dx": 1.0}))
    stopped.stopped = "steps"
    assert not agent_apply.auto_acceptable(stopped), "ein halber Vorschlag braucht den Blick"

    scad = Proposal(request="x")
    scad.drafts.append(OperationDraft(op="create_from_scad", params={"source": "cube(1);"}))
    assert not agent_apply.auto_acceptable(scad), "Quelltext läuft nie ungesehen"

    undo = Proposal(request="x")
    undo.undo_of = "t1"
    assert not agent_apply.auto_acceptable(undo), "eine Rücknahme bleibt eine Entscheidung"


def test_an_answer_only_turn_needs_no_decision(window: MainWindow) -> None:
    """Regel 19 im Geist: ein reiner Auskunftszug bekommt keine
    Übernehmen/Verwerfen-Leiste über „Keine Änderung" — er wird sofort
    aufgezeichnet, das Gespräch behält beide Beiträge, und es gibt nichts
    zu entscheiden.
    """
    import time

    scripted(window, Reply(text="Ich würde nichts ändern."))

    window.chat.input.setPlainText("Was meinst du?")
    window.chat._send()
    document = window.session.project.document
    application = QApplication.instance()
    deadline = time.monotonic() + 10.0
    while time.monotonic() < deadline:
        if application is not None:
            application.processEvents()
        if len(document.chat) >= 2:
            break
        time.sleep(0.01)
    window.session.wait_for_idle()

    assert len(document.chat) == 2
    assert document.chat[-1].transaction_id is None
    assert window._proposal is None, "es gibt nichts zu entscheiden"
    assert not window.chat.decision.isVisibleTo(window.chat)
    assert window.viewport.difference is None


@pytest.mark.skipif(
    sys.platform.startswith("linux"),
    reason=(
        "Stirbt auf den Linux-Runnern im eigenen Fork — ein Segmentierungsfehler "
        "in der ersten Widget-Anweisung des Szenenaufbaus, hier nie. Fünf "
        "Ursachen dieses Absturzbilds sind gefunden und behoben (ROADMAP, "
        "13.08.2026); dieser Rest ist der einzige Test, den es noch trifft, und "
        "mit `--forked` nimmt er niemanden mehr mit. `skipif` und nicht `xfail`, "
        "weil ein gestorbener Prozess kein Ergebnis meldet."
    ),
)
def test_the_applied_bar_clears_when_something_newer_is_on_top(window: MainWindow) -> None:
    """§26.5: die Übernommen-Leiste hängt am Dokument. Liegt eine neuere
    Transaktion obenauf, hat ihr Rückgängig-Knopf sein Versprechen verloren —
    die Leiste verschwindet, statt auf Klick fremde Arbeit zurückzunehmen.
    Und ein zu spät gedrückter Knopf nimmt nie die falsche Transaktion.
    """
    window._applied_transaction = "t1"
    window.chat.decision.setVisible(True)

    # Ein Fernaufruf legt etwas obenauf — projectChanged räumt die Leiste.
    window.run_remote("create_box", {"width": 10.0, "depth": 10.0, "height": 10.0})
    assert window._applied_transaction is None
    assert not window.chat.decision.isVisibleTo(window.chat)

    # Der Selbstschutz des Knopfs selbst: die gemerkte Transaktion existiert,
    # ist aber nicht mehr die oberste — kein Undo, nur eine Ansage.
    window.run_remote("create_box", {"width": 12.0, "depth": 12.0, "height": 12.0})
    transactions = window.session.project.document.transactions
    assert len(transactions) >= 2
    window._applied_transaction = transactions[0].id
    before = len(transactions)

    window._on_applied_undone()

    assert len(window.session.project.document.transactions) == before, (
        "der Knopf nimmt nie eine andere als die versprochene Transaktion"
    )
    assert window._applied_transaction is None


def test_the_applied_undo_refuses_a_transaction_it_cannot_find(window: MainWindow) -> None:
    """Derselbe Selbstschutz wie im Test darüber, ohne Szenenaufbau — und
    deshalb auf **jeder** Plattform.

    Der Test darüber prüft die Zusage auf dem realistischen Weg: zwei
    Fernaufrufe, zwei Auswertungen, zwei Szenenaufbauten. Genau daran stirbt er
    auf den Linux-Runnern (siehe seine ``skipif``-Begründung), und damit war
    §26.5 dort **gar nicht** geprüft — die teure Hälfte des Tests hat die
    billige mit sich genommen.

    Der Kern der Zusage braucht keine Geometrie: Der Knopf merkt sich eine
    Transaktion, und wenn die nicht mehr die oberste ist, nimmt er nichts
    zurück, sondern räumt sich weg. Eine Kennung, die es gar nicht gibt, ist
    davon der härteste Fall.
    """
    window._applied_transaction = "gibt-es-nicht"
    window.chat.decision.setVisible(True)
    before = len(window.session.project.document.transactions)

    window._on_applied_undone()

    assert len(window.session.project.document.transactions) == before, (
        "der Knopf hat etwas zurückgenommen, das er nicht versprochen hatte"
    )
    assert window._applied_transaction is None
    assert not window.chat.decision.isVisibleTo(window.chat)


def test_the_applied_bar_does_not_survive_a_new_project(window: MainWindow) -> None:
    """Die Leiste überlebte sogar den Projektwechsel und stand mit aktivem
    Rückgängig über einem leeren Projekt.
    """
    window._applied_transaction = "t1"
    window.chat.decision.setVisible(True)

    window.session.start_new()

    assert window._applied_transaction is None
    assert not window.chat.decision.isVisibleTo(window.chat)


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


def test_the_key_dialog_offers_the_local_model_too(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§27 nennt zwei Wege zum Sprachmodell. Bisher stand hier nur einer, und
    das lokale Modell ließ sich überhaupt nicht einstellen.
    """
    from app.core.backends import keys, llm
    from app.ui.dialogs import KeyDialog

    monkeypatch.setattr(keys, "_keyring", lambda: None)
    dialog = KeyDialog()

    assert dialog._chosen_model() == llm.configured_ollama_model()
    # Die Empfehlungen stehen zur Auswahl: Wer den Namen tippen soll, muss ihn
    # kennen, und ein Textfeld setzte genau das voraus.
    offered = {dialog.model_field.itemData(index) for index in range(dialog.model_field.count())}
    assert {name for name, _size, _what in llm.OLLAMA_SUGGESTIONS} <= offered


def test_the_key_dialog_remembers_the_model_without_a_key(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Wer nur das Modell wechselt, hat keinen Schlüssel einzutragen — und der
    Dialog darf seine Eingabe darüber nicht wegwerfen.
    """
    from app.core.backends import keys, llm
    from app.ui.dialogs import KeyDialog

    monkeypatch.setattr(keys, "_keyring", lambda: None)
    dialog = KeyDialog()
    dialog.model_field.setEditText("qwen3:14b")
    dialog._save()

    assert llm.configured_ollama_model() == "qwen3:14b"
    llm.remember_ollama_model("")


def test_the_probe_says_what_a_useless_model_means(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """„False" ist kein Ergebnis, mit dem jemand etwas anfangen kann — der Satz
    muss sagen, was passiert und was hilft.
    """
    from app.core.backends import keys
    from app.ui.dialogs import KeyDialog

    monkeypatch.setattr(keys, "_keyring", lambda: None)
    dialog = KeyDialog()

    dialog._probe_done(False)
    assert "führt aber nichts aus" in dialog.probe_result.text()

    dialog._probe_done(True)
    assert "brauchbar" in dialog.probe_result.text()

    dialog._probe_done(None)
    assert "ollama serve" in dialog.probe_result.text(), "kein Ergebnis ist kein Urteil"


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


def test_the_proposal_shows_its_costs_and_questions(qt_app: QApplication) -> None:
    """Konzept Agent-Vertiefung 4.2: Schritte, Token und Rückfragen werden
    längst gezählt — die Entscheidung zeigt sie jetzt auch. Eine erreichte
    Grenze steht ausgeschrieben da, nicht als zwei Worte.
    """
    from app.core.agent.proposal import Proposal, Question
    from app.ui.chat import ChatPanel, costs

    proposal = Proposal(request="x")
    proposal.steps = 8
    proposal.input_tokens = 24512
    proposal.output_tokens = 1830
    proposal.stopped = "steps"
    proposal.questions.append(Question(text="Welches Loch?", options=(), answer="hole_1"))

    line = costs(proposal)
    assert "8 Schritte" in line
    assert "24512 → 1830 Token" in line
    assert "Nach 8 Schritten angehalten" in line

    panel = ChatPanel()
    panel.show_proposal(ProposalPreview(proposal=proposal))
    assert "8 Schritte" in panel.cost_line.text()
    assert panel.questions_toggle.text() == "Rückfragen (1) …"
    assert not panel.questions_view.isVisibleTo(panel)
    panel.questions_toggle.setChecked(True)
    assert "Welches Loch?" in panel.questions_view.text()
    assert "→ hole_1" in panel.questions_view.text()

    panel.show_proposal(None)
    assert panel.cost_line.text() == ""


def test_a_token_stop_is_spelled_out(qt_app: QApplication) -> None:
    from app.core.agent.proposal import Proposal
    from app.ui.chat import costs

    proposal = Proposal(request="x")
    proposal.steps = 3
    proposal.stopped = "tokens"

    assert "Tokenbudget" in costs(proposal)


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


# --- ein Bild als Eingabe (Konzept P15 §7 Etappe 8, E8) -------------------------


def test_an_image_dropped_on_the_chat_becomes_a_request(qt_app: QApplication) -> None:
    """Ein Foto oder eine Skizze ist eine Eingabe wie ein Satz.

    Meshys eine Bedienidee, die ohne Cloud nachbaubar ist. Das Panel weiß
    nichts von Generierung — es meldet den Pfad, und was daraus wird,
    entscheidet das Fenster.

    Geprüft wird die Auswahlregel, nicht das Ziehen: ein Bild wird angenommen,
    ein Modell nicht. Die Endung entscheidet und nicht der angebotene Typ, weil
    Dateimanager Dateien unterschiedlich beschriften und die Endung überall
    dieselbe ist.
    """
    from PySide6.QtCore import QMimeData, QUrl

    from app.ui.chat import _dropped_image

    class _Event:
        def __init__(self, data: QMimeData) -> None:
            self._data = data

        def mimeData(self) -> QMimeData:  # noqa: N802 - Qt gibt den Namen
            return self._data

    picture = QMimeData()
    picture.setUrls([QUrl.fromLocalFile("C:/tmp/skizze.PNG")])
    assert _dropped_image(_Event(picture)) is not None, "Groß- und Kleinschreibung egal"

    model = QMimeData()
    model.setUrls([QUrl.fromLocalFile("C:/tmp/teil.stl")])
    assert _dropped_image(_Event(model)) is None, "ein Modell gehört auf den Viewport"

    assert _dropped_image(_Event(QMimeData())) is None, "und Text ist kein Bild"


def test_the_empty_chat_shows_what_one_can_ask(qt_app: QApplication) -> None:
    """Der Chat ist das Versprechen der Anwendung — und stand leer da.

    Was ein neuer Nutzer sah: eine Zeile mit dem Modellnamen, darunter eine
    schwarze Fläche, darunter „Was soll geändert werden?" und „Senden". Kein
    Beispiel, kein Vorschlag, keine Andeutung dessen, was hier geht. Der
    Erststart-Dialog wirbt für den Chat, das Handbuch hat ein Kapitel, die
    Website zeigt ihn — nur die Stelle selbst sagte nichts.
    """
    from app.ui.chat import STARTERS

    panel = ChatPanel()
    document = new_project().document
    panel.show_document(document)

    assert panel.starters.isVisibleTo(panel), "im leeren Gespräch stehen Beispiele"
    labels = [button.text() for button in panel.starters.findChildren(QPushButton)]
    assert len(labels) == len(STARTERS)
    assert any("M4" in label for label in labels), "mit echten Maßen, nicht in Befehlsform"


def test_a_starter_lands_in_the_field_and_is_not_sent(qt_app: QApplication) -> None:
    """Ein Beispiel ist ein Anfang zum Weiterschreiben, kein Knopf.

    Abschicken kostet Zeit und womöglich Geld; wer ein Beispiel anklickt,
    will es meistens noch anpassen.
    """
    sent: list[str] = []
    panel = ChatPanel()
    panel.requestSent.connect(sent.append)
    panel.show_document(new_project().document)

    button = panel.starters.findChildren(QPushButton)[0]
    button.click()

    assert panel.input.toPlainText() == button.text(), "der Satz steht im Feld"
    assert not sent, "und ist noch nicht unterwegs"


def test_the_starters_step_aside_once_the_talk_begins(qt_app: QApplication) -> None:
    """Sobald etwas im Gespräch steht, weiß der Nutzer, wofür es da ist."""
    panel = ChatPanel()
    document = new_project().document
    document.chat.append(ChatEntry(id="c1", role="user", text="Mach die Wand dicker"))
    panel.show_document(document)

    assert not panel.starters.isVisibleTo(panel)


def test_the_key_dialog_walks_the_three_steps_to_a_local_model(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Installieren war ein Knopf, die zwei Schritte danach waren zwei Sätze.

    Ollama bringt kein Modell mit und läuft nach der Installation nicht
    zwangsläufig. Die Auskunft dazu lautete „«ollama serve» startet es" und
    „«ollama pull» mit dem Modellnamen holt es" — an jemanden gerichtet, der in
    einem Fenster sitzt. Geprüft wird, dass jeder der drei Zustände seinen
    eigenen Satz und den Knopf dazu hat.
    """
    from app.core import tools
    from app.core.backends import keys
    from app.ui.dialogs import KeyDialog

    monkeypatch.setattr(keys, "_keyring", lambda: None)
    ollama = tools.by_id("ollama")
    assert ollama is not None

    seen: dict[str, tuple[str, str, bool]] = {}
    for name, state in (
        ("running", tools.ToolState(tool=ollama, path=None, running=True)),
        ("installed", tools.ToolState(tool=ollama, path=Path("ollama.exe"), running=False)),
        ("absent", tools.ToolState(tool=ollama, path=None, running=False)),
    ):
        monkeypatch.setattr(tools, "state_of", lambda _tool, found=state: found)
        dialog = KeyDialog()
        # Über den echten Weg: Der Zustand kommt aus der Erhebung im Arbeiter,
        # und ob sie ihn überhaupt einträgt, ist die Hälfte der Aussage.
        dialog.wait_for_look()
        qt_app.processEvents()
        seen[name] = (
            dialog.service_state.text(),
            dialog.service_button.text(),
            dialog.pull_button.isEnabled(),
        )

    assert "läuft" in seen["running"][0]
    assert seen["running"][2], "läuft es, kann ein Modell geholt werden"

    assert "läuft aber nicht" in seen["installed"][0]
    assert "starten" in seen["installed"][1], "der Knopf tut, was der Satz nennt"
    assert not seen["installed"][2], "ohne laufenden Dienst gibt es nichts zu holen"

    assert "nicht installiert" in seen["absent"][0]
    assert "Programme" in seen["absent"][1], "von hier führt der Weg in die Liste"


def test_the_pull_shows_a_share_and_a_way_out(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Neun Gigabyte brauchen einen Prozentwert und einen Ausgang (§2.8).

    Gefahren wird der ganze Weg — Knopf, Arbeiter, Signal über die
    Thread-Grenze —, nicht der Slot allein: Ob ``step`` überhaupt verbunden
    ist, ist genau die Hälfte dessen, was hier zu prüfen ist.
    """
    from app.core.backends import keys, llm
    from app.ui.dialogs import KeyDialog

    monkeypatch.setattr(keys, "_keyring", lambda: None)

    class Tags:
        """Die Modell-Liste, die derselbe Dialog beim Aufbau abfragt."""

        def read(self) -> bytes:
            return b'{"models": []}'

    class Server:
        """Ollama, so weit der Dialog es anspricht: Liste und Download.

        Beides über denselben ``urlopen``, also unterscheidet der Server nach
        Adresse — sonst bekäme die Modell-Liste den Zeilenstrom des Downloads.
        """

        lines = (
            b'{"status":"pulling manifest"}\n',
            b'{"status":"pulling 1a2b","total":1000,"completed":420}\n',
            b'{"status":"success"}\n',
        )

        def __init__(self) -> None:
            self.asking_for_tags = False

        def __call__(self, request: object, timeout: float = 0.0) -> object:
            self.asking_for_tags = "/api/tags" in str(getattr(request, "full_url", ""))
            return self

        def __enter__(self) -> object:
            return Tags() if self.asking_for_tags else iter(self.lines)

        def __exit__(self, *_args: object) -> None:
            return None

    monkeypatch.setattr(llm.urllib.request, "urlopen", Server())
    dialog = KeyDialog()
    dialog.pull_button.setEnabled(True)

    dialog.pull_button.click()
    assert dialog.pull_button.text() == "Abbrechen", "ein langer Vorgang hat einen Ausgang"
    for _ in range(200):
        qt_app.processEvents()
        if dialog._pull is None:
            break
        dialog._pull.wait(20)
    qt_app.processEvents()

    assert dialog.pull_progress.isHidden(), "danach ist der Balken weg"
    assert dialog.pull_button.text() == "Modell holen", "der Knopf ist wieder der, der es holt"
    assert "liegt jetzt hier" in dialog.probe_result.text()


def test_a_pull_step_without_numbers_claims_no_percentage(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """„pulling manifest" trägt keine Größe — dann steht der Balken unbestimmt.

    Eine erfundene Prozentzahl wäre schlimmer als keine: Sie behauptet einen
    Fortschritt, den niemand gemessen hat.
    """
    from app.core.backends import keys
    from app.ui.dialogs import KeyDialog

    monkeypatch.setattr(keys, "_keyring", lambda: None)
    dialog = KeyDialog()

    dialog._pull_step("pulling manifest", -1.0)
    assert dialog.pull_progress.maximum() == 0, "ohne Zahl ein unbestimmter Balken"
    assert "%" not in dialog.probe_result.text()

    dialog._pull_step("pulling 1a2b", 0.42)
    assert dialog.pull_progress.value() == 42
    assert "42" in dialog.probe_result.text(), "die Zahl steht neben dem Balken, nicht darin"


def test_a_suggested_entry_hands_over_the_name_and_not_its_line(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Eintrag trägt Größe und Bewertung — als Modellname wäre das falsch.

    „qwen3:14b — 9,3 GB, Bewährt: …" ist ein Name, den Ollama nicht kennt: der
    Download endete mit „Ollama hat den Namen nicht angenommen".
    """
    from app.core.backends import keys, llm
    from app.ui.dialogs import KeyDialog

    monkeypatch.setattr(keys, "_keyring", lambda: None)
    dialog = KeyDialog()
    index = dialog.model_field.findData(llm.DEFAULT_OLLAMA_MODEL)
    assert index >= 0
    dialog.model_field.setCurrentIndex(index)

    assert dialog._chosen_model() == llm.DEFAULT_OLLAMA_MODEL
    assert " — " in dialog.model_field.currentText(), "die Zeile erklärt, der Name nicht"


def test_a_fetched_model_counts_even_without_saving(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Neun Gigabyte, und dann wäre es beim Abbrechen verfallen.

    Der Dialog heißt „Chat einrichten" und hat *Speichern* und *Abbrechen*.
    Wer Ollama startet, ein Modell holt und danach abbricht — weil er gar
    keinen Schlüssel eintragen will —, hatte alles richtig gemacht und einen
    Chat, der weiter auf das alte Modell zeigte. Das Herunterladen ist eine
    Tatsache; nur die Eingabefelder warten auf eine Entscheidung.
    """
    from app.core.backends import keys, llm
    from app.ui.dialogs import KeyDialog

    monkeypatch.setattr(keys, "_keyring", lambda: None)
    llm.remember_ollama_model("")
    dialog = KeyDialog()
    dialog.model_field.setEditText("qwen3:8b")

    dialog._pull_done(None)

    try:
        assert llm.configured_ollama_model() == "qwen3:8b", "gemerkt, ohne Speichern"
    finally:
        llm.remember_ollama_model("")


def test_a_failed_fetch_changes_no_setting(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Was nicht geladen wurde, wird auch nicht eingestellt."""
    from app.core.backends import keys, llm
    from app.ui.dialogs import KeyDialog

    monkeypatch.setattr(keys, "_keyring", lambda: None)
    llm.remember_ollama_model("")
    dialog = KeyDialog()
    dialog.model_field.setEditText("gibtesnicht:1b")

    dialog._pull_done("Ollama hat den Namen nicht angenommen.")

    assert llm.configured_ollama_model() == llm.DEFAULT_OLLAMA_MODEL


def test_the_chat_wakes_up_even_when_the_dialog_was_cancelled(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Dialog nimmt nicht nur einen Schlüssel an.

    Er startet Ollama und holt ein Modell — beides getan, sobald es getan ist.
    Geprüft wurde bis hierhin nur der Rückgabewert von ``exec``, und bei
    *Abbrechen* kehrte das Fenster um, ohne den Chat noch einmal anzusehen.
    """
    from app.ui import main_window as window_module

    class Cancelled:
        DialogCode = window_module.KeyDialog.DialogCode

        def __init__(self, *_args: object, **_kwargs: object) -> None:
            pass

        def exec(self) -> object:
            return window_module.KeyDialog.DialogCode.Rejected

    looked: list[bool] = []
    monkeypatch.setattr(window_module, "KeyDialog", Cancelled)
    monkeypatch.setattr(
        window, "_refresh_chat_availability", lambda probe_local=False: looked.append(probe_local)
    )

    window.action_llm_key()

    assert looked == [True], "nach dem Dialog wird in jedem Fall nachgesehen"


def test_the_chat_dialog_is_there_before_the_answers_are(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§2.8, §38: der Dialog, in dem jemand seinen Chat einrichtet, wartet auf nichts.

    Gemessen 2,98 Sekunden bis auf den Bildschirm, davon 2,07 allein die Frage
    nach den installierten Modellen. Dazu der Zustand des Dienstes (eine
    Dateisuche und eine Socket-Probe) und der Satz darüber, was gerade
    antwortet (ein HTTP-Aufruf) — alles im Oberflächen-Thread.
    """
    from app.core.backends import keys
    from app.ui.dialogs import KeyDialog

    monkeypatch.setattr(keys, "_keyring", lambda: None)

    dialog = KeyDialog()

    assert dialog.field.echoMode() == dialog.field.EchoMode.Password, "die Fragen stehen sofort"
    assert "nachgesehen" in dialog.explanation.text()
    assert "nachgesehen" in dialog.service_state.text()
    assert not dialog.pull_button.isEnabled(), "kein Knopf auf eine Vermutung"

    dialog.wait_for_look()
    qt_app.processEvents()

    assert "nachgesehen" not in dialog.explanation.text()
    assert "nachgesehen" not in dialog.service_state.text()


def test_looking_for_the_chat_does_not_happen_in_the_gui_thread(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die teuerste Frage des Dialogs, gemessen 2,07 Sekunden."""
    import threading

    from app.core.backends import keys, llm
    from app.ui.dialogs import KeyDialog

    monkeypatch.setattr(keys, "_keyring", lambda: None)
    here = threading.get_ident()
    seen: list[int] = []

    def watched(*_args: object, **_kwargs: object) -> tuple[str, ...]:
        seen.append(threading.get_ident())
        return ()

    monkeypatch.setattr(llm, "installed_models", watched)

    dialog = KeyDialog()
    dialog.wait_for_look()
    qt_app.processEvents()

    assert seen, "es wurde überhaupt nicht nachgesehen"
    assert here not in seen, "die Frage lief im Oberflächen-Thread"


def test_the_suggestions_are_there_without_asking_anybody(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Empfehlungen sind Konstanten — sie kosten nichts und stehen sofort da.

    Wer den Dialog öffnet, um ein Modell zu holen, soll die Auswahl nicht erst
    nach zwei Sekunden sehen.
    """
    from app.core.backends import keys, llm
    from app.ui.dialogs import KeyDialog

    monkeypatch.setattr(keys, "_keyring", lambda: None)

    dialog = KeyDialog()

    offered = {dialog.model_field.itemData(index) for index in range(dialog.model_field.count())}
    assert {name for name, _size, _what in llm.OLLAMA_SUGGESTIONS} <= offered
