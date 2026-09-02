"""Der KI-Hinweis sperrt jeden echten LLM-Modellaufruf (P0-08).

Die Tests beobachten Chat und Werkzeugprobe an ihrer wirklichen Grenze. Sie
prüfen außerdem Zielwechsel, reale Layout- und Zugänglichkeitsgeometrie,
Tastatur, Rechtslinks und QObject-Leben; die Hilfsfunktion des Dialogs allein
ist kein Nachweis.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

pytest.importorskip("PySide6")

import shiboken6
from PySide6.QtCore import QCoreApplication, QEvent, QPropertyAnimation, Qt
from PySide6.QtGui import QAccessible, QAccessibleActionInterface, QDesktopServices
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog, QWidget

from app.core.backends import llm
from app.core.backends.llm import Message, Reply
from app.i18n import set_language
from app.i18n.catalog import available_languages, install_language, read_catalog
from app.ui.ai_disclosure import (
    AI_DISCLOSURE_VERSION,
    ANTHROPIC_COMMERCIAL_TERMS_URL,
    ANTHROPIC_PRIVACY_URL,
    AiDisclosureDialog,
    AiDisclosureTarget,
    DisclosureResult,
    LocalPrivacyDialog,
    clear_disclosure,
    disclosure_is_current,
    ensure_ai_disclosure,
    remember_disclosure,
    target_for_backend,
    target_for_ollama,
)
from app.ui.dialogs import KeyDialog
from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings, load_settings, save_settings
from app.ui.settings_dialog import SettingsDialog
from tests.scripted_backend import ScriptedBackend


class ProviderSpy(ScriptedBackend):
    """Ein geskriptetes Modell mit der Kennung und Adresse des echten Wegs."""

    def __init__(self, provider: str, url: str | None = None) -> None:
        super().__init__(answers=[Reply(text="Fertig.")])
        self.provider = provider
        self.url = url or llm.OLLAMA_URL

    @property
    def id(self) -> str:
        return self.provider


@pytest.fixture(autouse=True)
def _no_real_settings_write(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.ui.ai_disclosure.save_settings",
        lambda _settings: Path("settings.json"),
    )


@pytest.fixture
def window(qt_app: QApplication) -> MainWindow:
    return MainWindow(Session(), UiSettings())


def _target(backend: str, url: str | None = None) -> AiDisclosureTarget:
    return target_for_backend(ProviderSpy(backend, url))  # type: ignore[return-value]


def _show_until_ready(dialog: AiDisclosureDialog, application: QApplication) -> None:
    dialog.show()
    for _ in range(20):
        application.processEvents()
        if dialog.continue_button.isEnabled():
            break
        QTest.qWait(5)
    assert dialog.continue_button.isEnabled(), "zugänglicher Inhalt schaltet die Handlung frei"
    assert dialog.content_was_shown


def _show_and_accept(dialog: AiDisclosureDialog, application: QApplication) -> int:
    _show_until_ready(dialog, application)
    dialog.accept()
    return int(QDialog.DialogCode.Accepted)


def _flush_deletes(application: QApplication) -> None:
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
    application.processEvents()


def test_the_record_binds_version_backend_target_and_a_real_utc_timestamp() -> None:
    settings = UiSettings()
    anthropic = _target("anthropic")
    local = target_for_ollama("http://localhost:11434/api/chat")
    remote = target_for_ollama("https://ollama.example/api/chat")

    assert not disclosure_is_current(settings, anthropic)
    remember_disclosure(settings, anthropic, now="2026-08-31T12:30:45Z")

    assert settings.ai_disclosure_version == AI_DISCLOSURE_VERSION
    assert settings.ai_disclosure_backend == "anthropic"
    assert settings.ai_disclosure_target == anthropic.record_key
    assert settings.ai_disclosure_at_utc == "2026-08-31T12:30:45Z"
    assert disclosure_is_current(settings, anthropic)
    assert not disclosure_is_current(settings, local), "ein Anbieterwechsel ist neuer Inhalt"

    remember_disclosure(settings, local, now="2026-08-31T12:30:45Z")
    assert disclosure_is_current(settings, local)
    assert not disclosure_is_current(settings, remote), "Loopback zu entfernt öffnet nie weiter"
    assert not disclosure_is_current(
        settings, target_for_ollama("https://other.example/api/chat")
    ), "ein Hostwechsel wird erneut erklärt"

    settings.ai_disclosure_version = "1.1"
    assert not disclosure_is_current(settings, local), "eine neue Textfassung schließt zu"
    settings.ai_disclosure_version = AI_DISCLOSURE_VERSION
    settings.ai_disclosure_at_utc = "irgendwann"
    assert not disclosure_is_current(settings, local), "ein Textschlüssel allein genügt nicht"

    clear_disclosure(settings)
    assert not settings.ai_disclosure_version
    assert not settings.ai_disclosure_backend
    assert not settings.ai_disclosure_target
    assert not settings.ai_disclosure_at_utc


def test_ollama_targets_are_normalised_classified_and_free_of_secrets() -> None:
    local = target_for_ollama(
        "http://name:secret@127.0.0.1:11434/reverse/api/chat?token=hidden#fragment"
    )
    remote = target_for_ollama(
        "https://name:secret@OLLAMA.Example:443/reverse/api/chat?token=hidden#fragment"
    )

    assert local.target_class == "local"
    assert local.address == "http://127.0.0.1:11434"
    assert remote.target_class == "remote"
    assert remote.address == "https://ollama.example"
    assert "secret" not in local.record_key + remote.record_key
    assert "token" not in local.record_key + remote.record_key


@pytest.mark.parametrize(
    ("target", "provider_words"),
    (
        (_target("anthropic"), "textlicher Steckbrief"),
        (target_for_ollama("http://localhost:11434"), "auf diesem Rechner"),
        (target_for_ollama("https://ollama.example"), "anderen Rechner"),
    ),
)
def test_the_dialog_explains_the_actual_path_before_enabling_continue(
    qt_app: QApplication,
    target: AiDisclosureTarget,
    provider_words: str,
) -> None:
    dialog = AiDisclosureDialog(target)

    assert dialog.windowTitle() == "Interaktion mit einem KI-System"
    assert not dialog.continue_button.isEnabled(), "vor dem Anzeigen bleibt die Sperre zu"
    assert "Antworten können falsch" in dialog.general_text.text()
    assert provider_words in dialog.provider_text.text()
    assert dialog.heading.accessibleName()
    assert dialog.general_text.accessibleName()
    assert dialog.provider_text.accessibleName()

    dialog.resize(320, 480)
    _show_until_ready(dialog, qt_app)

    assert dialog.scroll_area.horizontalScrollBarPolicy() == Qt.ScrollBarPolicy.ScrollBarAlwaysOff
    assert dialog.scroll_area.horizontalScrollBar().maximum() == 0
    assert not dialog.findChildren(QPropertyAnimation), "der Hinweis animiert auch ohne Bewegung"
    dialog.reject()


@pytest.mark.parametrize("logical_size", ((320, 480), (600, 460)))
def test_real_layout_paints_and_keeps_both_actions_inside_the_window(
    qt_app: QApplication,
    logical_size: tuple[int, int],
) -> None:
    dialog = AiDisclosureDialog(target_for_ollama("https://ollama.example"))
    dialog.resize(*logical_size)
    dialog.show()
    qt_app.processEvents()

    rendered = dialog.grab()
    ratio = rendered.devicePixelRatio()
    assert not rendered.isNull()
    assert rendered.width() >= round(dialog.width() * ratio)
    assert rendered.height() >= round(dialog.height() * ratio)
    assert dialog.scroll_area.horizontalScrollBar().maximum() == 0
    for button in (dialog.back_button, dialog.continue_button):
        top_left = button.mapTo(dialog, button.rect().topLeft())
        bottom_right = button.mapTo(dialog, button.rect().bottomRight())
        assert dialog.rect().contains(top_left)
        assert dialog.rect().contains(bottom_right)
        assert button.isVisibleTo(dialog)
        assert button.accessibleName()
    dialog.reject()


def test_large_text_needs_no_visual_scroll_and_keeps_keyboard_access(
    qt_app: QApplication,
) -> None:
    dialog = AiDisclosureDialog(target_for_ollama("https://ollama.example"))
    enlarged = dialog.font()
    enlarged.setPointSize(max(enlarged.pointSize(), 18))
    dialog.setFont(enlarged)
    dialog.resize(320, 480)
    dialog.show()
    qt_app.processEvents()
    bar = dialog.scroll_area.verticalScrollBar()

    assert bar.maximum() > 0
    assert bar.value() == bar.minimum()
    assert dialog.continue_button.isEnabled()
    assert dialog.content_was_shown
    assert dialog.scroll_area.hasFocus()
    assert bar.focusPolicy() == Qt.FocusPolicy.NoFocus
    QTest.keyClick(dialog.scroll_area, Qt.Key.Key_End)
    qt_app.processEvents()

    assert bar.value() == bar.maximum()
    assert dialog.continue_button.isEnabled()
    for _ in range(6):
        if dialog.continue_button.hasFocus():
            break
        QTest.keyClick(qt_app.focusWidget(), Qt.Key.Key_Tab)
        qt_app.processEvents()
    assert dialog.continue_button.hasFocus()
    QTest.keyClick(dialog.continue_button, Qt.Key.Key_Return)
    qt_app.processEvents()
    assert dialog.result() == int(QDialog.DialogCode.Accepted)


def test_escape_and_window_close_are_back_paths(qt_app: QApplication) -> None:
    dialog = AiDisclosureDialog(_target("anthropic"))
    dialog.show()
    qt_app.processEvents()
    QTest.keyClick(dialog, Qt.Key.Key_Escape)
    qt_app.processEvents()
    assert dialog.result() == int(QDialog.DialogCode.Rejected)

    closed = AiDisclosureDialog(target_for_ollama())
    closed.show()
    qt_app.processEvents()
    closed.close()
    qt_app.processEvents()
    assert closed.result() == int(QDialog.DialogCode.Rejected)


def test_provider_specific_privacy_paths_do_not_preload_the_web(
    qt_app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened: list[str] = []
    monkeypatch.setattr(
        QDesktopServices,
        "openUrl",
        lambda address: opened.append(address.toString()) or True,
    )

    anthropic = AiDisclosureDialog(_target("anthropic"))
    local = AiDisclosureDialog(target_for_ollama("http://localhost:11434"))
    remote = AiDisclosureDialog(target_for_ollama("https://ollama.example"))
    anthropic.show()
    qt_app.processEvents()

    assert opened == []
    assert len(anthropic.external_links) == 2
    assert all(
        link.description() == "Beim Öffnen erhält der Anbieter übliche Verbindungsdaten."
        and link.isVisibleTo(anthropic)
        for link in anthropic.external_links
    )
    assert local.external_links == [] and local.operator_note is None
    assert remote.external_links == [] and remote.operator_note is not None
    assert "ollama.example" in remote.provider_text.text()
    assert remote.operator_note.text() == "Datenschutz beim Betreiber dieses Ziels klären"
    anthropic.reject()


def test_only_visible_anthropic_links_open_the_exact_legal_pages(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened: list[str] = []
    monkeypatch.setattr(
        QDesktopServices,
        "openUrl",
        lambda address: opened.append(address.toString()) or True,
    )
    dialog = AiDisclosureDialog(_target("anthropic"))

    for link in dialog.external_links:
        link.click()
    dialog._open_notice_link("https://not-allowed.example")

    assert opened == [ANTHROPIC_PRIVACY_URL, ANTHROPIC_COMMERCIAL_TERMS_URL]


def test_local_privacy_opens_only_the_packaged_read_only_document(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shown: list[str] = []
    opened: list[str] = []
    monkeypatch.setattr(
        LocalPrivacyDialog, "exec", lambda dialog: shown.append(dialog.text.toPlainText()) or 0
    )
    monkeypatch.setattr(
        QDesktopServices, "openUrl", lambda address: opened.append(address.toString())
    )
    dialog = AiDisclosureDialog(target_for_ollama("http://localhost:11434"))

    dialog.local_privacy_link.click()

    assert shown and "Datenschutz" in shown[0]
    assert opened == []

    reader = LocalPrivacyDialog("# Datenschutz\n\n[Extern](https://example.com)")
    assert reader.text.isReadOnly()
    assert not reader.text.openLinks()
    assert not reader.text.openExternalLinks()


def test_packaging_includes_the_local_privacy_document() -> None:
    specification = Path("packaging/solidon3d.spec").read_text(encoding="utf-8")
    assert '(str(ROOT / "DATENSCHUTZ.md"), ".")' in specification


def test_packaged_privacy_distinguishes_local_and_remote_ollama() -> None:
    privacy = Path("DATENSCHUTZ.md").read_text(encoding="utf-8")
    assert "Bei einer Loopback-Adresse bleiben sie auf diesem Rechner" in privacy
    assert "bei einer vom Nutzer eingetragenen entfernten Adresse" in privacy
    assert "werden sie an diesen anderen Rechner übertragen" in privacy
    assert "Mit einem lokalen Modell (Ollama) verlässt nichts den Rechner" not in privacy


def test_qt_accessibility_exposes_names_descriptions_and_focusable_actions(
    qt_app: QApplication,
) -> None:
    dialog = AiDisclosureDialog(_target("anthropic"))
    _show_until_ready(dialog, qt_app)

    for widget in (
        dialog,
        dialog.heading,
        dialog.general_text,
        dialog.provider_text,
        dialog.scroll_area,
        dialog.local_privacy_link,
        *dialog.external_links,
        dialog.back_button,
        dialog.continue_button,
    ):
        interface = QAccessible.queryAccessibleInterface(widget)
        assert interface is not None
        assert interface.text(QAccessible.Text.Name)
        assert interface.text(QAccessible.Text.Description)
    for button in (dialog.back_button, dialog.continue_button):
        interface = QAccessible.queryAccessibleInterface(button)
        assert interface is not None and interface.state().focusable
    for link in (dialog.local_privacy_link, *dialog.external_links):
        interface = QAccessible.queryAccessibleInterface(link)
        assert interface is not None and interface.role() == QAccessible.Role.Button
        action = interface.actionInterface()
        assert action is not None
        assert QAccessibleActionInterface.pressAction() in action.actionNames()
    dialog.reject()


def test_real_accessibility_actions_activate_all_visible_privacy_paths(
    qt_app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened: list[str] = []
    local: list[bool] = []
    monkeypatch.setattr(LocalPrivacyDialog, "exec", lambda _dialog: local.append(True) or 0)
    monkeypatch.setattr(
        QDesktopServices,
        "openUrl",
        lambda address: opened.append(address.toString()) or True,
    )
    dialog = AiDisclosureDialog(_target("anthropic"))
    _show_until_ready(dialog, qt_app)

    for link in (dialog.local_privacy_link, *dialog.external_links):
        interface = QAccessible.queryAccessibleInterface(link)
        assert interface is not None
        action = interface.actionInterface()
        assert action is not None
        action.doAction(QAccessibleActionInterface.pressAction())
        QTest.qWait(150)

    assert local == [True]
    assert opened == [ANTHROPIC_PRIVACY_URL, ANTHROPIC_COMMERCIAL_TERMS_URL]
    dialog.reject()


def test_accessible_layout_unlocks_at_scroll_position_zero(qt_app: QApplication) -> None:
    dialog = AiDisclosureDialog(target_for_ollama("https://ollama.example"))
    enlarged = dialog.font()
    enlarged.setPointSize(max(enlarged.pointSize(), 18))
    dialog.setFont(enlarged)
    dialog.resize(320, 480)

    assert not dialog.continue_button.isEnabled()
    assert not dialog.content_was_shown
    dialog.show()
    qt_app.processEvents()

    bar = dialog.scroll_area.verticalScrollBar()
    assert bar.maximum() > 0
    assert bar.value() == bar.minimum()
    assert dialog.continue_button.isEnabled()
    assert dialog.content_was_shown
    dialog.reject()


def test_readiness_never_moves_focus(qt_app: QApplication) -> None:
    dialog = AiDisclosureDialog(_target("anthropic"))
    _show_until_ready(dialog, qt_app)
    assert dialog.scroll_area.hasFocus()

    dialog.local_privacy_link.setFocus(Qt.FocusReason.TabFocusReason)
    assert dialog.local_privacy_link.hasFocus()
    dialog._unlock_after_show()
    qt_app.processEvents()

    assert dialog.local_privacy_link.hasFocus()
    dialog.reject()


def test_resize_preserves_the_reading_position(qt_app: QApplication) -> None:
    dialog = AiDisclosureDialog(_target("anthropic"))
    enlarged = dialog.font()
    enlarged.setPointSize(max(enlarged.pointSize(), 18))
    dialog.setFont(enlarged)
    dialog.resize(320, 480)
    _show_until_ready(dialog, qt_app)
    bar = dialog.scroll_area.verticalScrollBar()
    bar.setValue(max(1, bar.maximum() // 2))
    previous = bar.value()

    dialog.resize(340, 500)
    qt_app.processEvents()

    assert bar.value() == min(previous, bar.maximum())
    assert dialog.continue_button.isEnabled()
    dialog.reject()


def test_tab_order_starts_with_content_and_reaches_all_links_and_actions(
    qt_app: QApplication,
) -> None:
    dialog = AiDisclosureDialog(_target("anthropic"))
    _show_until_ready(dialog, qt_app)
    expected = [
        dialog.local_privacy_link,
        *dialog.external_links,
        dialog.back_button,
        dialog.continue_button,
    ]

    assert dialog.scroll_area.hasFocus()
    for widget in expected:
        QTest.keyClick(qt_app.focusWidget(), Qt.Key.Key_Tab)
        qt_app.processEvents()
        assert widget.hasFocus()

    QTest.keyClick(dialog.continue_button, Qt.Key.Key_Space)
    qt_app.processEvents()
    assert dialog.result() == int(QDialog.DialogCode.Accepted)


def test_accessibility_failure_keeps_the_gate_closed(
    qt_app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    dialog = AiDisclosureDialog(_target("anthropic"))
    original_query = QAccessible.queryAccessibleInterface

    def query(widget: QWidget):
        if widget is dialog.provider_text:
            return None
        return original_query(widget)

    monkeypatch.setattr(QAccessible, "queryAccessibleInterface", query)
    dialog.show()
    qt_app.processEvents()

    assert not dialog.continue_button.isEnabled()
    assert not dialog.content_was_shown
    dialog.reject()


@pytest.mark.parametrize("defect", ("missing_text", "truncated_height", "horizontal_overflow"))
def test_incomplete_content_or_layout_keeps_the_gate_closed(
    qt_app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    defect: str,
) -> None:
    dialog = AiDisclosureDialog(_target("anthropic"))
    if defect == "missing_text":
        dialog.provider_text.setText("")
    elif defect == "truncated_height":
        monkeypatch.setattr(dialog, "_fit_wrapped_paragraphs", lambda: None)
        dialog.provider_text.setFixedHeight(1)
    else:
        dialog.scroll_area.setWidgetResizable(False)
        dialog.content.setFixedWidth(1_000)
    dialog.resize(320, 480)
    dialog.show()
    qt_app.processEvents()

    assert not dialog.continue_button.isEnabled()
    assert not dialog.content_was_shown
    dialog.reject()


def test_accessible_tree_reads_information_before_actions(qt_app: QApplication) -> None:
    dialog = AiDisclosureDialog(_target("anthropic"))
    _show_until_ready(dialog, qt_app)
    root = QAccessible.queryAccessibleInterface(dialog)
    assert root is not None
    names: list[str] = []

    def collect(interface) -> None:
        names.append(interface.text(QAccessible.Text.Name))
        for child_index in range(interface.childCount()):
            child = interface.child(child_index)
            if child is not None:
                collect(child)

    collect(root)
    ordered = (
        dialog.general_text.accessibleName(),
        dialog.provider_text.accessibleName(),
        dialog.local_privacy_link.accessibleName(),
        dialog.back_button.accessibleName(),
        dialog.continue_button.accessibleName(),
    )
    assert all(name in names for name in ordered)
    assert [names.index(name) for name in ordered] == sorted(names.index(name) for name in ordered)
    dialog.reject()


def test_bound_timer_does_not_outlive_a_destroyed_dialog(qt_app: QApplication) -> None:
    dialog = AiDisclosureDialog(_target("anthropic"))
    dialog.show()
    dialog.deleteLater()
    _flush_deletes(qt_app)
    assert not shiboken6.isValid(dialog)


def test_repeated_gate_use_does_not_accumulate_parent_owned_dialogs(
    qt_app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = QWidget()
    parent.show()
    settings = UiSettings()
    target = _target("anthropic")
    monkeypatch.setattr(
        "app.ui.ai_disclosure.AiDisclosureDialog.exec",
        lambda dialog: _show_and_accept(dialog, qt_app),
    )

    for _ in range(3):
        clear_disclosure(settings)
        assert ensure_ai_disclosure(settings, target, parent) is DisclosureResult.ACCEPTED
        _flush_deletes(qt_app)
        assert not parent.findChildren(AiDisclosureDialog)


@pytest.mark.parametrize("backend_id", ("anthropic", "ollama"))
def test_back_blocks_the_actual_first_chat_call_and_restores_every_character(
    qt_app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    window: MainWindow,
    backend_id: str,
) -> None:
    backend = ProviderSpy(backend_id)
    window.session.set_agent_backend(backend)
    setup_opened: list[bool] = []
    monkeypatch.setattr(
        "app.ui.ai_disclosure.AiDisclosureDialog.exec",
        lambda _dialog: int(QDialog.DialogCode.Rejected),
    )
    monkeypatch.setattr(window, "action_llm_key", lambda: setup_opened.append(True))

    original = "  Mach die Wand 3 mm dick.\nLass die Öffnung frei.  "
    window.chat.input.setPlainText(original)
    window.chat._send()

    assert not backend.seen
    assert window.chat.input.toPlainText() == original
    assert window.chat.input.textCursor().selectedText()
    assert setup_opened == [True]


@pytest.mark.parametrize("backend_id", ("anthropic", "ollama"))
def test_accepting_sends_exactly_once_and_the_same_target_needs_no_repeat(
    qt_app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    window: MainWindow,
    backend_id: str,
) -> None:
    backend = ProviderSpy(backend_id)
    window.session.set_agent_backend(backend)
    monkeypatch.setattr(
        window.session,
        "propose_async",
        lambda request, _selection=None, **_kwargs: backend.complete(
            [Message(role="user", content=request)]
        ),
    )
    shown: list[str] = []

    def accept(dialog: AiDisclosureDialog) -> int:
        shown.append(dialog.target.record_key)
        return _show_and_accept(dialog, qt_app)

    monkeypatch.setattr("app.ui.ai_disclosure.AiDisclosureDialog.exec", accept)
    window.chat.input.setPlainText("Baue einen Halter.")
    window.chat._send()

    target = target_for_backend(backend)
    assert target is not None
    assert len(backend.seen) == 1
    assert shown == [target.record_key]
    assert disclosure_is_current(window.settings, target)

    window.chat.input.setPlainText("Mach ihn breiter.")
    window.chat._send()
    assert len(backend.seen) == 2
    assert shown == [target.record_key]


def test_remote_host_change_blocks_the_chat_until_the_new_target_is_shown(
    monkeypatch: pytest.MonkeyPatch,
    window: MainWindow,
) -> None:
    old = target_for_ollama("https://old.example")
    remember_disclosure(window.settings, old, now="2026-08-31T12:30:45Z")
    backend = ProviderSpy("ollama", "https://new.example/api/chat")
    window.session.set_agent_backend(backend)
    monkeypatch.setattr(
        "app.ui.ai_disclosure.AiDisclosureDialog.exec",
        lambda _dialog: int(QDialog.DialogCode.Rejected),
    )
    monkeypatch.setattr(window, "action_llm_key", lambda: None)

    window.chat.input.setPlainText("Prüfe das Teil.")
    window.chat._send()
    assert not backend.seen
    assert window.chat.input.toPlainText() == "Prüfe das Teil."


def test_the_disclosed_backend_is_bound_before_the_busy_signal_can_switch_it(
    qt_app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    window: MainWindow,
) -> None:
    disclosed = ProviderSpy("ollama", "https://approved.example/api/chat")
    replacement = ProviderSpy("ollama", "https://other.example/api/chat")
    window.session.set_agent_backend(disclosed)
    monkeypatch.setattr(
        "app.ui.ai_disclosure.AiDisclosureDialog.exec",
        lambda dialog: _show_and_accept(dialog, qt_app),
    )

    def switch_after_binding(busy: bool) -> None:
        if busy:
            window.session.set_agent_backend(replacement)

    window.session.agentBusyChanged.connect(switch_after_binding)
    window.chat.input.setPlainText("Halte diesen Datenweg fest.")
    window.chat._send()
    worker = window.session._agent
    assert worker is not None and worker.wait(10_000)
    qt_app.processEvents()

    assert disclosed.seen
    assert not replacement.seen
    target = target_for_backend(disclosed)
    assert target is not None
    assert window.settings.ai_disclosure_target == target.record_key


def test_rendering_and_storage_failures_both_fail_closed(
    qt_app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    window: MainWindow,
) -> None:
    backend = ProviderSpy("anthropic")
    window.session.set_agent_backend(backend)
    monkeypatch.setattr(window, "action_llm_key", lambda: None)
    monkeypatch.setattr(
        "app.ui.ai_disclosure.AiDisclosureDialog",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("paint failed")),
    )
    window.chat.input.setPlainText("Bleibt hier.")
    window.chat._send()
    assert not backend.seen
    assert window.chat.input.toPlainText() == "Bleibt hier."

    monkeypatch.undo()
    backend = ProviderSpy("anthropic")
    window.session.set_agent_backend(backend)
    monkeypatch.setattr(window, "action_llm_key", lambda: None)
    monkeypatch.setattr(
        "app.ui.ai_disclosure.AiDisclosureDialog.exec",
        lambda dialog: _show_and_accept(dialog, qt_app),
    )
    monkeypatch.setattr(
        "app.ui.ai_disclosure.save_settings",
        lambda _settings: (_ for _ in ()).throw(OSError("disk full")),
    )
    window.chat.input.setPlainText("Auch hier.")
    window.chat._send()
    assert not backend.seen
    assert window.chat.input.toPlainText() == "Auch hier."
    assert not window.settings.ai_disclosure_target


def test_rendering_failure_notice_survives_the_backend_dialog(
    qt_app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
    window: MainWindow,
) -> None:
    backend = ProviderSpy("anthropic")
    window.session.set_agent_backend(backend)
    window._show_start_screen(False)
    window.right.setCurrentWidget(window.chat)
    window.show()
    qt_app.processEvents()
    opened: list[bool] = []

    def backend_dialog() -> None:
        opened.append(True)
        window.chat.set_notice("")

    monkeypatch.setattr(window, "action_llm_key", backend_dialog)
    monkeypatch.setattr(
        "app.ui.ai_disclosure.AiDisclosureDialog",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("paint failed")),
    )
    window.chat.input.setPlainText("Bleibt sichtbar hier.")
    window.chat._send()

    assert opened == [True]
    assert not backend.seen
    assert window.chat.notice.isVisibleTo(window)
    assert "KI-Hinweis konnte nicht vollständig" in window.chat.notice.text()
    assert window.chat.input.toPlainText() == "Bleibt sichtbar hier."


def test_accept_without_a_successful_display_check_is_blocked(
    monkeypatch: pytest.MonkeyPatch,
    window: MainWindow,
) -> None:
    backend = ProviderSpy("ollama")
    window.session.set_agent_backend(backend)
    monkeypatch.setattr(
        "app.ui.ai_disclosure.AiDisclosureDialog.exec",
        lambda _dialog: int(QDialog.DialogCode.Accepted),
    )
    monkeypatch.setattr(window, "action_llm_key", lambda: None)
    window.chat.input.setPlainText("Nicht senden.")
    window.chat._send()
    assert not backend.seen
    assert window.chat.input.toPlainText() == "Nicht senden."


def test_tool_probe_is_gated_and_uses_the_exact_disclosed_remote_target(
    qt_app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(KeyDialog, "look", lambda _dialog: None)
    monkeypatch.setattr(
        llm,
        "_configured_ollama_url",
        lambda: "https://name:secret@ollama.example/reverse/api/chat?token=hidden",
    )
    calls: list[tuple[str, str | None]] = []
    monkeypatch.setattr(
        llm,
        "ollama_tool_check",
        lambda _model, url=None: calls.append(("tool", url)) or True,
    )
    monkeypatch.setattr(
        llm,
        "ollama_speed",
        lambda _model, url=None: calls.append(("speed", url)) or llm.Speed(200.0),
    )
    dialog = KeyDialog(settings=UiSettings())
    dialog.probe_button.setEnabled(True)
    monkeypatch.setattr(
        "app.ui.ai_disclosure.AiDisclosureDialog.exec",
        lambda _dialog: int(QDialog.DialogCode.Rejected),
    )

    dialog._probe_tools()
    assert not calls
    assert dialog._probe is None

    monkeypatch.setattr(
        "app.ui.ai_disclosure.AiDisclosureDialog.exec",
        lambda disclosure: _show_and_accept(disclosure, qt_app),
    )
    dialog._probe_tools()
    worker = dialog._probe
    assert worker is not None and worker.wait(10_000)
    qt_app.processEvents()

    expected = "https://name:secret@ollama.example/reverse/api/chat?token=hidden"
    assert calls == [("tool", expected), ("speed", expected)]
    target = target_for_ollama(expected)
    assert disclosure_is_current(dialog.settings, target)
    assert "secret" not in dialog.settings.ai_disclosure_target
    dialog.release()


def test_settings_reset_is_applied_only_when_the_dialog_is_saved(qt_app: QApplication) -> None:
    settings = UiSettings()
    target = _target("anthropic")
    remember_disclosure(settings, target, now="2026-08-31T12:30:45Z")
    dialog = SettingsDialog(settings)

    dialog.ai_disclosure_reset.click()
    assert disclosure_is_current(settings, target), "Abbrechen verändert die Einstellung nicht"
    dialog.apply_to(settings)
    assert not disclosure_is_current(settings, target)
    assert not dialog.ai_disclosure_reset.isEnabled()


def test_the_local_settings_file_contains_only_the_four_disclosure_values(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    path = tmp_path / "settings.json"
    monkeypatch.setattr("app.ui.settings.settings_path", lambda: path)
    settings = UiSettings()
    target = target_for_ollama("http://localhost:11434")
    remember_disclosure(settings, target, now="2026-08-31T12:30:45Z")

    save_settings(settings)
    stored = json.loads(path.read_text(encoding="utf-8"))
    disclosure_keys = sorted(key for key in stored if key.startswith("ai_disclosure_"))
    assert disclosure_keys == [
        "ai_disclosure_at_utc",
        "ai_disclosure_backend",
        "ai_disclosure_target",
        "ai_disclosure_version",
    ]
    assert disclosure_is_current(load_settings(), target)


def test_every_catalog_translates_all_three_target_paths_and_actions() -> None:
    required = (
        "Interaktion mit einem KI-System",
        (
            "Sie interagieren mit einem KI-System. Antworten können falsch oder "
            "unvollständig sein. Solidon führt daraus keine Geometrie ungeprüft aus: "
            "Ein Vorschlag bleibt sichtbar, prüfbar und mit einem Schritt rücknehmbar."
        ),
        (
            "Wenn Sie Anthropic wählen, werden Ihre Chatnachricht und die zuvor angezeigte "
            "Projektauswahl nicht allein übertragen. Direkt an Anthropic gehen die aktuelle "
            "Nachricht, bis zu zwölf frühere Chatbeiträge, ein textlicher Steckbrief der "
            "gesamten aktuellen Szene mit Objekt- und Quellnamen, Maßen, Merkmalen, "
            "Parametern, Einstellungen und Auswahl, der Prüfbericht sowie die für den "
            "Agenten nötigen Anweisungen, Regeln und Werkzeugschemata. Unterstützt das "
            "gewählte Modell Bilder, kann Solidon außerdem automatisch gerenderte Ansichten "
            "der Szene mitsenden. Die Projektdatei und die Netzgeometrie selbst werden nicht "
            "übertragen. Sie verwenden Ihren eigenen API-Schlüssel."
        ),
        (
            "Das lokale Ollama-Ziel {target} verarbeitet auf diesem Rechner dieselben "
            "Arbeitsdaten wie der Chat: aktuelle Nachricht, bis zu zwölf frühere "
            "Chatbeiträge, textlichen Steckbrief der gesamten Szene, Prüfbericht, "
            "Anweisungen, Regeln und Werkzeugschemata sowie bei einem Bildmodell "
            "automatisch gerenderte Ansichten. Projektdatei und Netzgeometrie selbst "
            "werden nicht übertragen. Die Werkzeugprobe sendet nur einen festen "
            "technischen Prüfauftrag ohne Projekt- oder Chatinhalt. Installation, Download "
            "oder Update des Modells können gesondert eine Netzverbindung verwenden."
        ),
        (
            "Das Ollama-Ziel {target} liegt auf einem anderen Rechner. An diese Adresse "
            "werden aktuelle Nachricht, bis zu zwölf frühere Chatbeiträge, der textliche "
            "Steckbrief der gesamten Szene, Prüfbericht, Anweisungen, Regeln und "
            "Werkzeugschemata sowie bei einem Bildmodell automatisch gerenderte Ansichten "
            "übertragen. Projektdatei und Netzgeometrie selbst werden nicht übertragen. Die "
            "Werkzeugprobe sendet einen festen technischen Prüfauftrag. Verwenden Sie nur "
            "ein Ziel, dessen Betreiber und Übertragungsweg Sie vertrauen."
        ),
        "Mit Pfeil- und Bildtasten durch den KI-Hinweis blättern.",
        "KI-Anfrage fortsetzen",
        "Setzt den bereits angeforderten KI-Aufruf fort.",
        "Zurück",
        "Solidon-Datenschutz lokal öffnen",
        "Öffnet die mit Solidon ausgelieferte Datenschutzerklärung ohne Netzverbindung.",
        "Anthropic-Datenschutz (öffnet im Browser)",
        "Anthropic-API-Bedingungen (öffnet im Browser)",
        "Beim Öffnen erhält der Anbieter übliche Verbindungsdaten.",
        "Datenschutz beim Betreiber dieses Ziels klären",
        "Solidon-Datenschutz",
        (
            "Diese lokale Fassung wird mit Solidon ausgeliefert. Externe Links sind hier "
            "deaktiviert."
        ),
    )

    assert set(available_languages()) == {"de", "en", "es", "fr", "it", "pt"}
    for language in ("en", "es", "fr", "it", "pt"):
        catalog = read_catalog(language)
        for source in required:
            assert source in catalog, f"{language} fehlt: {source}"
            assert catalog[source] != source, f"{language} fällt auf Deutsch zurück: {source}"


def test_all_languages_targets_sizes_and_text_scales_fit_and_unlock_at_the_top(
    qt_app: QApplication,
) -> None:
    targets = (
        _target("anthropic"),
        target_for_ollama("http://localhost:11434"),
        target_for_ollama("https://ollama.example"),
    )
    try:
        for language in available_languages():
            install_language(language)
            set_language(language)
            for target in targets:
                for logical_size in ((320, 480), (600, 460)):
                    for scale in (1.0, 1.5, 2.0):
                        dialog = AiDisclosureDialog(target)
                        font = dialog.font()
                        font.setPointSizeF(max(font.pointSizeF(), 9.0) * scale)
                        dialog.setFont(font)
                        dialog.resize(*logical_size)
                        _show_until_ready(dialog, qt_app)
                        bar = dialog.scroll_area.verticalScrollBar()
                        assert dialog.scroll_area.horizontalScrollBar().maximum() == 0
                        assert bar.value() == bar.minimum()
                        assert dialog.continue_button.isEnabled()
                        for button in (dialog.back_button, dialog.continue_button):
                            top_left = button.mapTo(dialog, button.rect().topLeft())
                            bottom_right = button.mapTo(dialog, button.rect().bottomRight())
                            assert dialog.rect().contains(top_left)
                            assert dialog.rect().contains(bottom_right)
                        for link in (dialog.local_privacy_link, *dialog.external_links):
                            for label in (link.title_label, link.description_label):
                                top_left = label.mapTo(link, label.rect().topLeft())
                                bottom_right = label.mapTo(link, label.rect().bottomRight())
                                assert link.rect().contains(top_left)
                                assert link.rect().contains(bottom_right)
                                assert label.width() > 0
                                assert label.height() + 1 >= label.heightForWidth(label.width())
                        dialog.reject()
    finally:
        install_language("de")
        set_language("de")
