"""Lizenzierung, Aktivierung und lesbare Lizenzhinweise in der Oberfläche (§36)."""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QApplication,
)

from app.ui.main_window import MainWindow
from app.ui.session import Session
from app.ui.settings import UiSettings
from tests.ui_helpers import expire_trial as _expired
from tests.ui_helpers import session as session
from tests.ui_helpers import window as window


def test_an_expired_trial_greys_the_writing_side_out(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§2 C: gesperrt sieht man **vor** dem Klick — ausgegraut, mit Grund im
    Hinweistext. Die Hürde selbst liegt im Kern; hier steht die Freundlichkeit
    davor."""
    _expired(monkeypatch)
    window = MainWindow(Session(), UiSettings())

    assert not window.import_action.isEnabled()
    assert not window.generate_action.isEnabled()
    assert not window.export_action.isEnabled()
    assert not window._toolbar_import.isEnabled()
    assert all(not action.isEnabled() for action in window._op_actions.values())
    assert "Lizenzschlüssel" in window.import_action.statusTip(), (
        "der Hinweistext nennt den Grund, nicht nur den Zustand"
    )
    # Rückgängig und Wiederholen gehören zur lesenden Seite: ihr Zustand
    # folgt dem Verlauf, nicht der Lizenz — hier leer, also aus, aber nicht
    # wegen der Sperre (der Hinweistext bleibt ihr eigener).
    assert "Lizenzschlüssel" not in window.undo_action.statusTip()

    assert not window.chat.input.isEnabled()
    assert window.chat.unlock.isVisibleTo(window.chat)
    assert "Lizenzschlüssel" in window.chat.access_hint.text()


def test_entering_a_key_puts_everything_back(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Nach dem Eintragen steht wieder offen, was der Ablauf zugemacht hatte —
    samt der eigenen Hinweistexte, nicht mit dem Sperrgrund als Fossil."""
    from datetime import date

    from app.core import activation
    from app.core.activation import certificate, key

    _expired(monkeypatch)
    window = MainWindow(Session(), UiSettings())
    hint_before = str(window.import_action.property("tip_before_lock"))
    toolbar_hint_before = str(window._toolbar_import.property("tip_before_lock"))

    licence = key.Licence(
        major=key.current_major(),
        purchased_on=date(2026, 8, 6),
        order="A-1",
        holder="kaeufer@beispiel.de",
    )
    active = certificate.ActivationCertificate(
        licence_digest=certificate.licence_digest(licence),
        device_public=b"x" * 32,
        device_name="Werkstatt-PC",
        activation_id="0" * 32,
        issued_on=date(2026, 8, 28),
    )
    monkeypatch.setattr(
        activation,
        "_cached",
        activation.Activation(licence=licence, certificate=active),
    )
    window._update_actions()
    window._refresh_chat_availability()

    assert window.import_action.isEnabled()
    assert window.generate_action.isEnabled()
    assert window.import_action.statusTip() == hint_before
    # Und am Knopf ohne Beschriftung: der trug vor der symbolfreien Leiste gar
    # keinen ``statusTip``, und ``_lock_hint`` stellte nach dem Freischalten
    # einen leeren wieder her — ein stummes Bild.
    assert window._toolbar_import.statusTip() == toolbar_hint_before
    assert window._toolbar_import.statusTip().startswith("Modell einfügen")
    assert not window.chat.unlock.isVisibleTo(window.chat)


def test_the_last_trial_days_show_up_once_in_the_status_bar(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§2 C: einmal eine Zeile, wenn weniger als drei Tage übrig sind — kein
    Startdialog, keine Zählung im Titel."""
    from app.core import activation

    monkeypatch.setattr(activation, "_cached", activation.Activation(days_left=2))
    window = MainWindow(Session(), UiSettings())

    # In einem eigenen Feld, nicht als Statusmeldung: eine Meldung verdeckt,
    # was links in der Leiste steht, und die Zeile steht dauerhaft.
    assert "2" in window.trial_line.text()
    assert "freischalten" in window.trial_line.text()


def test_a_damaged_installation_names_itself_in_the_status_bar(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Zustand, der alles sperrt, war der einzige ohne Zeile.

    Demo und Testlauf nennen sich in der Statusleiste selbst; eine
    beschädigte Installation (H4) schwieg dort — der Kunde sah eine
    Oberfläche wie immer und erfuhr den Grund erst am ersten
    Änderungsversuch. Derselbe Satz wie im Freischaltdialog, aus derselben
    Quelle (``damaged_line``), denn zwei Formulierungen derselben Auskunft
    laufen auseinander (Bedienungs-Vollmacht, 26.08.2026).
    """
    from app.core import activation
    from app.ui.dialogs import damaged_line

    monkeypatch.setattr(activation, "_cached", activation.Activation(damaged=True))
    window = MainWindow(Session(), UiSettings())

    assert window.trial_line.text() == damaged_line(), "die Zeile nennt den Zustand"
    assert window.trial_line.isVisibleTo(window), "und sie steht sichtbar da"


def test_a_comfortable_trial_rest_stays_quiet(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core import activation

    monkeypatch.setattr(activation, "_cached", activation.Activation(days_left=14))
    window = MainWindow(Session(), UiSettings())

    assert window.trial_line.text() == ""
    assert window.statusBar().currentMessage() == ""


def test_the_trial_line_does_not_cover_the_measurements(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Die Maße bleiben lesbar, während die Demo-Zeile steht.

    Als ``showMessage`` geführt, legte die Zeile sich über das Maßfeld —
    Qt blendet bei einer Meldung aus, was per ``addWidget`` in der Leiste
    liegt. Sichtbar wurde es erst auf den Handbuchbildern, wo „Keine
    Auswahl" und „Demo — noch 79 Tage" ineinanderliefen. Beide Felder
    müssen gleichzeitig etwas anzeigen können.
    """
    from datetime import date

    from app.core import activation

    # ``in_demo`` ist abgeleitet und hängt an der Frist, nicht an einem Feld.
    # Das Datum steht hier ausdrücklich: ``conftest`` nimmt den ausgelieferten
    # Stichtag weg, damit die Suite nicht am Kalender hängt.
    monkeypatch.setattr(
        activation, "_cached", activation.Activation(days_left=79, deadline=date(2026, 10, 30))
    )
    window = MainWindow(Session(), UiSettings())
    window.resize(1180, 760)
    window.show()
    qt_app.processEvents()

    assert window.trial_line.text(), "die Demo-Zeile fehlt"
    assert window.measurements.isVisible(), "die Maße sind verdeckt"
    assert window.measurements.text(), "die Maße sind leer"


def test_the_about_dialog_names_the_activation_state(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """§2 I H2: „Lizenziert für …" steht im Über-Dialog — wer seinen Schlüssel
    weitergibt, gibt seinen Namen mit."""
    from datetime import date

    from PySide6.QtWidgets import QLabel

    from app.core import activation
    from app.core.activation import certificate, key
    from app.ui.dialogs import AboutDialog

    licence = key.Licence(
        major=key.current_major(),
        purchased_on=date(2026, 11, 1),
        order="A-77",
        holder="kaeufer@beispiel.de",
    )
    active = certificate.ActivationCertificate(
        licence_digest=certificate.licence_digest(licence),
        device_public=b"x" * 32,
        device_name="Werkstatt-PC",
        activation_id="0" * 32,
        issued_on=date(2026, 8, 28),
    )
    monkeypatch.setattr(
        activation,
        "_cached",
        activation.Activation(licence=licence, certificate=active),
    )
    dialog = AboutDialog()
    texts = " ".join(label.text() for label in dialog.findChildren(QLabel))
    assert "kaeufer@beispiel.de" in texts
    assert "A-77" in texts


def test_the_about_dialog_does_not_call_an_unactivated_key_licensed(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein gültiger Kaufcode allein ist noch kein freigeschalteter Rechner."""
    from datetime import date

    from PySide6.QtWidgets import QLabel

    from app.core import activation
    from app.core.activation import key
    from app.ui.dialogs import AboutDialog

    licence = key.Licence(
        major=key.current_major(),
        purchased_on=date(2026, 11, 1),
        order="A-78",
        holder="kundin@beispiel.de",
    )
    monkeypatch.setattr(activation, "_cached", activation.Activation(licence=licence))

    dialog = AboutDialog()
    texts = " ".join(label.text() for label in dialog.findChildren(QLabel))

    assert "Lizenziert für" not in texts
    assert "noch einmal aktiviert" in texts


def test_a_licensed_state_uses_the_success_mark_without_a_leading_dot(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    from datetime import date

    from app.core import activation
    from app.core.activation import certificate, key
    from app.ui.dialogs import ActivationDialog

    licence = key.Licence(
        major=key.current_major(),
        purchased_on=date(2026, 8, 6),
        order="A-77",
        holder="kaeufer@beispiel.de",
    )
    active = certificate.ActivationCertificate(
        licence_digest=certificate.licence_digest(licence),
        device_public=b"x" * 32,
        device_name="Werkstatt-PC",
        activation_id="0" * 32,
        issued_on=date(2026, 8, 28),
    )
    monkeypatch.setattr(
        activation, "_cached", activation.Activation(licence=licence, certificate=active)
    )

    dialog = ActivationDialog()

    assert dialog.state_label.property("role") == "ok"
    assert "✓" in dialog.state_label.text()
    assert not dialog.state_label.text().startswith("·")


def test_the_about_dialog_does_not_invent_a_trial_for_the_sale_version(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ohne Testangebot nennt auch der ruhige Lizenzsatz keinen Ablauf."""
    from PySide6.QtWidgets import QLabel

    from app.core import activation
    from app.core.activation import store
    from app.ui.dialogs import AboutDialog

    monkeypatch.setattr(store, "TRIAL_FROM", None)
    monkeypatch.setattr(activation, "_cached", activation.Activation(days_left=0))

    dialog = AboutDialog()
    texts = " ".join(label.text() for label in dialog.findChildren(QLabel))
    assert "Testzeitraum" not in texts
    assert "Geräteaktivierung" in texts


def test_a_damaged_installation_is_not_called_unlocked(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """„Freigeschaltet für kaeufer@…" über einem Fenster, das nichts freigibt.

    Seit ``Activation.damaged`` (H4) wird der Schlüssel auch bei gebrochenem
    Manifest gelesen — der zahlende Kunde soll erkannt werden statt eine
    Kaufaufforderung zu bekommen. Beide Anzeigen fragten aber weiter nur nach
    ``licence is not None`` und meldeten deshalb genau das Gegenteil des
    Zustands: freigeschaltet, während jede Änderung gesperrt ist. Den wahren
    Grund erfuhr der Kunde erst beim ersten Änderungsversuch — Regel 17 an der
    Anzeige.

    Der Wortlaut kommt aus ``InstallationDamaged`` und wird nicht zweimal
    erfunden: Es ist derselbe Satz, den derselbe Kunde gleich darauf zu lesen
    bekommt.
    """
    from datetime import date

    from PySide6.QtWidgets import QLabel

    from app.core import activation
    from app.core.activation import key
    from app.core.errors import InstallationDamaged
    from app.ui.dialogs import AboutDialog, ActivationDialog

    licence = key.Licence(
        major=key.current_major(),
        purchased_on=date(2026, 8, 6),
        order="A-77",
        holder="kaeufer@beispiel.de",
    )
    monkeypatch.setattr(activation, "_cached", activation.Activation(licence=licence, damaged=True))
    erwartet = str(InstallationDamaged().detail)

    dialog = ActivationDialog()
    gezeigt = dialog.state_label.text()
    assert erwartet in gezeigt, f"der Grund fehlt: {gezeigt!r}"
    assert "Freigeschaltet" not in gezeigt, f"und das Gegenteil steht nicht da: {gezeigt!r}"
    assert "kaeufer@beispiel.de" not in gezeigt, "erkannt heißt hier nicht freigeschaltet"

    about = AboutDialog()
    texte = " ".join(label.text() for label in about.findChildren(QLabel))
    assert erwartet in texte, "und im Über-Dialog steht dieselbe Auskunft"
    assert "Lizenziert für" not in texte


def test_a_damaged_installation_greys_out_what_cannot_work(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der falsche Satz war behoben, die toten Knöpfe standen noch da.

    ``damaged`` schlägt jeden Schlüssel (``Activation.unlocked``): *Eintragen*
    schaltet nichts frei. Und *Solidon kaufen* führt in beiden Lagen an die
    falsche Stelle — wer bezahlt hat, soll nicht noch einmal kaufen, und wer
    nicht bezahlt hat, bekommt mit einem Kauf trotzdem keine heile
    Installation. Zwei Knöpfe, die nichts bewirken können, sind zwei
    Sackgassen (§2.1).

    *Schlüssel entfernen* bleibt bedienbar: Es tut, was es sagt.

    Regel 18 — grau ist eine Farbe. Der Grund steht im Tooltip, in der
    ``accessibleDescription`` für den Bildschirmleser und sichtbar in der Zeile
    darüber; und er ist derselbe Satz wie dort, nicht ein zweiter Wortlaut.
    """
    from datetime import date

    from app.core import activation
    from app.core.activation import key
    from app.core.errors import InstallationDamaged
    from app.ui.dialogs import ActivationDialog

    licence = key.Licence(
        major=key.current_major(),
        purchased_on=date(2026, 11, 1),
        order="A-77",
        holder="kaeufer@beispiel.de",
    )
    grund = str(InstallationDamaged().detail)

    monkeypatch.setattr(activation, "_cached", activation.Activation(licence=licence))
    heil = ActivationDialog()
    heil.field.setPlainText("SOLIDON3D-1-EGAL")
    assert heil.check_button.isEnabled(), "ohne Schaden trägt der Knopf ein"
    assert heil.buy_button.isEnabled()

    monkeypatch.setattr(activation, "_cached", activation.Activation(licence=licence, damaged=True))
    kaputt = ActivationDialog()
    kaputt.field.setPlainText("SOLIDON3D-1-EGAL")

    assert not kaputt.check_button.isEnabled(), "ein Schlüssel schaltet hier nichts frei"
    assert not kaputt.buy_button.isEnabled(), "und ein Kauf repariert keine Datei"
    assert kaputt.forget_button.isEnabled(), "entfernen tut, was es sagt"

    for knopf in (kaputt.check_button, kaputt.buy_button):
        assert grund in knopf.toolTip(), f"ohne Grund grau: {knopf.text()!r}"
        assert grund in knopf.accessibleDescription(), "Regel 18: nicht nur die Farbe"
    assert grund in kaputt.state_label.text(), "und sichtbar, nicht nur im Zeigen"


def test_the_activation_dialog_accepts_a_valid_key(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """V4b: der Dialog nimmt an, was gilt — und legt es ab."""
    from app.core import activation
    from app.core.activation import key, store
    from app.ui.dialogs import ActivationDialog
    from tools.make_licence_keys import make_key, public_key

    # Der erste Testvektor aus RFC 8032 — dasselbe Paar wie in
    # test_licence_boundary.py, das kein importierbares Paket ist.
    test_seed = bytes.fromhex("9d61b19deffd5a60ba844af492ec2cc44449c5697b326919703bac031cae7f60")

    monkeypatch.setattr(store, "user_config_dir", lambda: tmp_path)
    monkeypatch.setattr(key, "PUBLIC_KEY", public_key(test_seed))
    activation.forget_cache()
    try:
        from datetime import date

        licence = key.Licence(
            major=key.current_major(),
            purchased_on=date(2026, 8, 6),
            order="A-1",
            holder="kaeufer@beispiel.de",
        )
        dialog = ActivationDialog()
        dialog.field.setPlainText(make_key(test_seed, licence))
        dialog._remember()

        assert activation.state().licence == licence
        assert store.read_key() is not None, "geprüft und abgelegt"
    finally:
        activation.forget_cache()


def test_an_active_key_cannot_be_overwritten_before_deactivation(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Der einfache Zwei-Geräte-Nebenweg beginnt nicht mit Überschreiben im Dialog."""
    from datetime import date

    from app.core import activation
    from app.core.activation import certificate, key, store
    from app.ui.dialogs import ActivationDialog

    monkeypatch.setattr(store, "user_config_dir", lambda: tmp_path)
    store.write_key("SOLIDON3D-1-BEREITS-AKTIV")
    licence = key.Licence(
        major=key.current_major(),
        purchased_on=date(2026, 11, 1),
        order="A-1",
        holder="kundin@beispiel.de",
    )
    active = certificate.ActivationCertificate(
        licence_digest="0" * 64,
        device_public=b"x" * 32,
        device_name="Werkstatt-PC",
        activation_id="0" * 32,
        issued_on=date(2026, 11, 1),
    )
    monkeypatch.setattr(
        activation,
        "_cached",
        activation.Activation(licence=licence, certificate=active),
    )

    dialog = ActivationDialog()

    assert dialog.field.isReadOnly()
    assert dialog.device_name.isReadOnly()
    assert not dialog.check_button.isEnabled()
    assert not dialog.online_button.isEnabled()
    assert not dialog.offline_button.isEnabled()
    assert dialog.forget_button.text() == "Diesen Rechner deaktivieren"
    activation.forget_cache()


def test_an_unclear_deactivation_answer_never_restores_the_certificate(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Nach möglicher Serverfreigabe bleibt der Rechner lokal sicher gesperrt."""
    from app.core import activation
    from app.core.activation import store
    from app.core.errors import AppError
    from app.ui import dialogs
    from app.ui.dialogs import ActivationDialog

    monkeypatch.setattr(store, "user_config_dir", lambda: tmp_path)
    assert store.write_pending_deactivation("signierte Geräteabmeldung")
    monkeypatch.setattr(
        activation,
        "_cached",
        activation.Activation(deactivation_pending=True),
    )
    shown: list[object] = []
    monkeypatch.setattr(dialogs, "show_error", lambda error, *_args: shown.append(error))

    dialog = ActivationDialog()
    dialog._deactivation_failed(AppError(detail="Verbindung abgebrochen"))

    assert store.read_certificate() is None
    assert store.read_pending_deactivation() == "signierte Geräteabmeldung"
    assert dialog.forget_button.text() == "Deaktivierung erneut senden"
    assert "noch nicht bestätigt" in dialog.state_label.text()
    assert shown and isinstance(shown[0], activation.DeviceDeactivationPending)
    activation.forget_cache()


def test_a_local_deactivation_failure_rolls_back_before_contacting_the_server(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Vor dem Netz darf ein Dateifehler keinen halben Sperrzustand hinterlassen."""
    from app.core import activation
    from app.core.activation import store
    from app.ui import dialogs
    from app.ui.dialogs import ActivationDialog

    monkeypatch.setattr(store, "user_config_dir", lambda: tmp_path)
    store.write_key("SOLIDON3D-1-BESTEHEND")
    store.write_certificate("bestehendes Zertifikat")
    store.write_pending_deactivation("wiederholbarer Auftrag")
    monkeypatch.setattr(
        activation,
        "_cached",
        activation.Activation(deactivation_pending=True),
    )
    monkeypatch.setattr(activation, "prepare_deactivation", lambda: "wiederholbarer Auftrag")
    monkeypatch.setattr(activation, "remove_certificate", lambda: False)
    shown: list[object] = []
    monkeypatch.setattr(dialogs, "show_error", lambda error, *_args: shown.append(error))

    dialog = ActivationDialog()
    dialog._deactivate()

    assert store.read_pending_deactivation() is None
    assert store.read_certificate() == "bestehendes Zertifikat"
    assert shown
    assert dialog.forget_button.text() != "Deaktivierung erneut senden"
    activation.forget_cache()


def test_confirmed_deactivation_never_claims_that_an_unremovable_key_is_gone(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Die Erfolgsmeldung folgt erst, wenn auch der lokale Schlüssel wirklich weg ist."""
    from app.core import activation
    from app.core.activation import store
    from app.ui import dialogs
    from app.ui.dialogs import ActivationDialog

    monkeypatch.setattr(store, "user_config_dir", lambda: tmp_path)
    store.write_key("SOLIDON3D-1-LOKAL-GESPERRT")
    monkeypatch.setattr(
        activation,
        "_cached",
        activation.Activation(deactivation_pending=True),
    )
    monkeypatch.setattr(activation, "clear_pending_deactivation", lambda: True)
    monkeypatch.setattr(activation, "forget_key", lambda: False)
    shown: list[object] = []
    notices: list[object] = []
    monkeypatch.setattr(dialogs, "show_error", lambda error, *_args: shown.append(error))
    monkeypatch.setattr(
        dialogs.QMessageBox,
        "information",
        lambda *_args, **_kwargs: notices.append(object()),
    )

    dialog = ActivationDialog()
    previous = dialog.field.toPlainText()
    dialog._deactivation_completed()

    assert dialog.field.toPlainText() == previous
    assert shown, "der lokale Rest wird erklärt"
    assert not notices, "keine falsche Erfolgsmeldung"
    activation.forget_cache()


def test_the_activation_dialog_rejects_with_a_reason(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """V4b: abgelehnt wird mit Grund und Handlungen, nie mit „ungültig" —
    der Fehlerdialog ist modal, also wird er hier abgefangen statt geöffnet."""
    from app.core import activation
    from app.core.activation import store
    from app.ui import dialogs
    from app.ui.dialogs import ActivationDialog

    monkeypatch.setattr(store, "user_config_dir", lambda: tmp_path)
    activation.forget_cache()
    shown: list[object] = []
    monkeypatch.setattr(dialogs, "show_error", lambda error, *a, **kw: shown.append(error))
    try:
        dialog = ActivationDialog()
        dialog.field.setPlainText("SOLIDON3D-1-AAAAAAAA")
        dialog._remember()

        assert len(shown) == 1
        assert getattr(shown[0], "suggestions", ()), "Regel 17: mit Handlungen"
        assert store.read_key() is None, "abgelegt wird nur Geprüftes"
    finally:
        activation.forget_cache()


def test_the_first_run_dialog_promises_no_trial_in_the_sale_version(
    qt_app: QApplication,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die Verkaufsversion nennt die Planänderung und erfindet keine freien Tage."""
    from app.core import activation
    from app.core.activation import store
    from app.ui.first_run import FirstRunDialog

    monkeypatch.setattr(store, "DEMO_UNTIL", None)
    monkeypatch.setattr(store, "TRIAL_FROM", None)
    activation.forget_cache()
    dialog = FirstRunDialog(UiSettings())
    assert "14" not in dialog.terms.text()
    assert "ohne Testphase" in dialog.terms.text()
    assert "Geräteaktivierung" in dialog.terms.text()
    activation.forget_cache()


def test_the_first_run_dialog_promises_no_free_days_on_a_damaged_install(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der dritte Zwilling — dieselbe Auskunft, die dritte Stelle.

    „Die ersten 14 Tage ist alles frei" stand hier unabhängig vom Zustand.
    Gemessen bei gebrochenem Manifest (H4): ``unlocked`` ist ``False``, jede
    Änderung wird abgesagt — und das ist der **erste** Satz, den ein neuer
    Kunde liest. Ein Virenscanner in Quarantäne reicht dafür.

    Derselbe Wortlaut wie im Freischalt- und im Über-Dialog, aus derselben
    Quelle (``InstallationDamaged``): Ein vierter eigener Satz wäre eine vierte
    Gelegenheit, auseinanderzulaufen.
    """
    from app.core import activation
    from app.core.errors import InstallationDamaged
    from app.ui.first_run import FirstRunDialog

    monkeypatch.setattr(activation, "_cached", activation.Activation(damaged=True))

    dialog = FirstRunDialog(UiSettings())

    text = dialog.terms.text()
    assert str(InstallationDamaged().detail) in text, text
    assert "14" not in text, f"kein Versprechen über freie Tage: {text!r}"


def test_the_about_dialog_carries_the_licence_information(qt_app: QApplication) -> None:
    """§36: Lizenzhinweise gehören in den Über-Dialog."""
    from PySide6.QtWidgets import QLabel, QTextBrowser

    from app.ui.dialogs import AboutDialog

    dialog = AboutDialog()
    texts = " ".join(label.text() for label in dialog.findChildren(QLabel))
    assert "Solidon" in texts
    assert "RS Digital" in texts
    assert "MIT" in texts, "the parts library exception is named"
    assert "P3D- und SVG-Dateien" in texts and "gesonderte Erlaubnis" in texts

    listing = dialog.findChild(QTextBrowser)
    assert listing is not None
    assert "PySide6" in listing.toMarkdown()


def test_the_about_dialog_localises_the_security_promise_and_links(
    qt_app: QApplication,
) -> None:
    """§37.3: Termin und Meldeweg stimmen in jeder ausgelieferten Sprache.

    ``QLocale()`` folgt der Prozesssprache, Solidon wechselt seine Sprache aber
    im laufenden Prozess. Die echte spanische Oberfläche zeigte deshalb noch
    „31. Oktober 2031“, obwohl der übrige Satz übersetzt war.
    """
    from PySide6.QtWidgets import QLabel

    from app.branding import SECURITY_SUPPORT_UNTIL, SUPPORT_ADDRESS, WEBSITE_URL
    from app.i18n import set_language
    from app.i18n.catalog import available_languages, install_language
    from app.ui.dialogs import AboutDialog

    dates = {
        "de": "31. Oktober 2031",
        "en": "October 31, 2031",
        "es": "31 de octubre de 2031",
        "fr": "31 octobre 2031",
        "it": "31 ottobre 2031",
        "pt": "31 de outubro de 2031",
    }
    assert SECURITY_SUPPORT_UNTIL.isoformat() == "2031-10-31"

    try:
        for language in available_languages():
            install_language(language)
            set_language(language)
            dialog = AboutDialog()
            security = dialog.findChild(QLabel, "security_support")
            assert security is not None
            text = security.text()
            page = "security.html" if language == "de" else f"{language}/security.html"

            assert dates[language] in text
            assert f'href="mailto:{SUPPORT_ADDRESS}"' in text
            assert f'href="{WEBSITE_URL}{page}"' in text
            assert security.openExternalLinks()
            assert security.textInteractionFlags() & Qt.TextInteractionFlag.LinksAccessibleByMouse
            assert (
                security.textInteractionFlags() & Qt.TextInteractionFlag.LinksAccessibleByKeyboard
            )
            dialog.deleteLater()
    finally:
        set_language("de")


def test_the_unlock_dialog_does_not_close_on_an_empty_field(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """„Eintragen" mit leerem Feld schloss den Dialog wortlos.

    Das ist der Zustand, in dem jemand nicht weiter weiß, und die Antwort war
    ein verschwundenes Fenster — auf den einen Knopf hin, der etwas versprach.
    ``_remember`` rief ``reject()``, sobald das Feld leer war.

    Jetzt ist der Knopf gesperrt, solange nichts dasteht, und sagt im Tooltip
    warum (Regel 19, §2.7). Über die Tastatur bleibt er erreichbar — dann sagt
    der Dialog es, statt zu gehen.
    """
    from app.core import activation
    from app.core.activation import store
    from app.ui.dialogs import ActivationDialog

    monkeypatch.setattr(store, "user_config_dir", lambda: tmp_path)
    activation.forget_cache()
    try:
        dialog = ActivationDialog()
        try:
            assert not dialog.check_button.isEnabled(), "leeres Feld, und der Knopf verspricht was"
            assert dialog.check_button.toolTip(), "gesperrt ohne Grund ist die halbe Antwort"

            closed: list[bool] = []
            dialog.rejected.connect(lambda: closed.append(True))
            dialog._remember()
            assert closed == [], "der Dialog ging zu, statt zu sagen was fehlt"

            dialog.field.setPlainText("SOLIDON3D-1-AAAAAAAA")
            assert dialog.check_button.isEnabled(), "mit Schlüssel muss er können"
            assert not dialog.check_button.toolTip(), "und dann ohne Grund dastehen"

            dialog.field.setPlainText("   ")
            assert not dialog.check_button.isEnabled(), "Leerzeichen sind kein Schlüssel"
        finally:
            dialog.deleteLater()
    finally:
        activation.forget_cache()


def test_the_activation_dialog_reads_as_two_small_steps(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ohne Lizenzwissen sieht man Reihenfolge, Abkürzung und Offline-Ausweg."""
    from PySide6.QtWidgets import QGroupBox, QLabel

    from app.core import activation
    from app.core.activation import store
    from app.ui.dialogs import ActivationDialog

    monkeypatch.setattr(store, "user_config_dir", lambda: tmp_path)
    activation.forget_cache()
    try:
        dialog = ActivationDialog()
        groups = [group.title() for group in dialog.findChildren(QGroupBox)]
        labels = " ".join(label.text() for label in dialog.findChildren(QLabel))

        assert groups == ["1 · Lizenzschlüssel einfügen", "2 · Diesen Rechner aktivieren"]
        assert "Kein Konto" in labels and "ohne Internet" in labels
        assert not dialog.online_button.isEnabled()
        assert "Zuerst" in dialog.online_button.toolTip()
        assert dialog.online_button.isDefault(), "der kurze Online-Weg ist der Hauptknopf"
        assert dialog.offline_button.text().startswith("Offline")
    finally:
        activation.forget_cache()


def test_the_offline_activation_page_opens_in_the_ui_language(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Dateiweg wechselt nicht auf einer deutschen Website die Sprache."""
    from PySide6.QtCore import QUrl

    from app.ui import dialogs

    opened: list[str] = []
    monkeypatch.setattr(dialogs, "get_language", lambda: "es")
    monkeypatch.setattr(
        dialogs.QDesktopServices,
        "openUrl",
        staticmethod(lambda url: opened.append(url.toString())),
    )

    dialog = dialogs.OfflineActivationDialog("{}")
    dialog._open_page()

    assert opened == [f"{dialog.PAGE_URL}?lang=es"]
    assert QUrl(opened[0]).query() == "lang=es"


def test_a_paying_customer_is_not_told_the_trial_ran_out(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Zwei Lagen sperren, und sie heißen nicht gleich (§33.1, H4).

    ``unlocked`` verlangt ``not damaged``, sperrt also auch einen zahlenden
    Kunden, dessen Installation gebrochen ist. Der Sperrtext leitete sich
    daraus ab und behauptete „Der Testzeitraum ist abgelaufen — dafür braucht
    Solidon einen Lizenzschlüssel" — bei jemandem, der einen hat, und während
    die Statuszeile im selben Fenster „Die Installation ist beschädigt" sagte.

    Geprüft an **beiden** Lagen, denn eine allein sagt nichts: Der abgelaufene
    Testlauf muss weiter seinen eigenen Satz bekommen. Gefunden von
    3d-druck-46 im Lizenz-Audit.
    """
    from app.core import activation
    from app.core.activation import store
    from app.ui.dialogs import damaged_line

    aktion = next(iter(window._op_actions.values()))

    monkeypatch.setattr(activation, "_cached", activation.Activation(damaged=True))
    window._lock_hint(aktion, True)
    beschaedigt = aktion.statusTip()

    monkeypatch.setattr(activation, "_cached", activation.Activation(days_left=0))
    aktion.setProperty("tip_before_lock", None)
    window._lock_hint(aktion, True)
    abgelaufen = aktion.statusTip()

    monkeypatch.setattr(store, "TRIAL_FROM", None)
    aktion.setProperty("tip_before_lock", None)
    window._lock_hint(aktion, True)
    ohne_test = aktion.statusTip()

    assert damaged_line() in beschaedigt, "die beschädigte Installation sagt, was sie ist"
    assert "Testzeitraum" not in beschaedigt, (
        "wer bezahlt hat, wird nicht nach einem Schlüssel gefragt, den er hat"
    )
    assert "Testzeitraum" in abgelaufen, "und der abgelaufene Testlauf behält seinen Satz"
    assert beschaedigt != abgelaufen
    assert "Testzeitraum" not in ohne_test
    assert "Geräteaktivierung" in ohne_test


def test_the_status_line_speaks_on_the_day_the_trial_ends(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ausgerechnet am Tag null schwieg sie.

    ``in_trial`` verlangt ``days_left > 0``, also fiel bei genau null keine
    Verzweigung mehr zu: zehn Tage unsichtbar (richtig), zwei Tage sichtbar,
    **null Tage unsichtbar** — an dem Tag, an dem alles grau wird, stand die
    Erklärung nur noch in Tooltips. ``expired`` gab es die ganze Zeit; gefragt
    hat es niemand.
    """
    from app.core import activation

    def zeile(tage: int) -> str:
        monkeypatch.setattr(activation, "_cached", activation.Activation(days_left=tage))
        window._trial_status_line()
        return window.trial_line.text()

    assert not zeile(10), "zehn Tage sind kein Anlass, jemanden anzusprechen"
    assert zeile(2), "kurz davor schon"
    assert zeile(0), "und am Tag, an dem es zu ist, erst recht"
    assert "abgelaufen" in zeile(0)


def test_the_status_line_explains_the_sale_version_without_inventing_a_trial(
    window: MainWindow, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gesperrte Werkzeuge bekommen auch ohne vorherigen Test einen sichtbaren Grund."""
    from app.core import activation
    from app.core.activation import store

    monkeypatch.setattr(store, "TRIAL_FROM", None)
    monkeypatch.setattr(activation, "_cached", activation.Activation(days_left=0))
    window._trial_status_line()

    assert "Testzeitraum" not in window.trial_line.text()
    assert "Geräteaktivierung" in window.trial_line.text()


def test_the_key_field_shows_a_whole_key(qt_app: QApplication) -> None:
    """Wer seinen Schlüssel einfügt, will sehen, ob er vollständig ist.

    Das Feld war auf 90 Punkte festgesetzt. Ein Lizenzschlüssel ist einzeilig
    und **242 Zeichen** lang; bei der Feldbreite von 558 Punkten sind das
    sieben umbrochene Zeilen à 14, also 110 Punkte. Es fehlten zwanzig, und
    zwar an der einen Stelle der Anwendung, an der jemand prüfen will, ob er
    richtig kopiert hat — mit einem Rollbalken als einziger Auskunft darüber.

    Der Befund aus der Durchsicht las sich umgekehrt („90 Punkte für einen
    einzeiligen Schlüssel"), und die naheliegende Behebung hätte den Dialog
    verschlechtert: Ein ``QLineEdit`` zeigt an dieser Breite **45 von 242**
    Zeichen.

    Zugesichert wird deshalb nicht eine Punktzahl, sondern die Sache: Der
    Rollweg ist null, also steht der ganze Schlüssel im Bild. Das gilt auch
    bei größerer Systemschrift, denn beide Seiten der Rechnung — Umbruch und
    Höhe — nehmen dieselbe Metrik.
    """
    from PySide6.QtCore import Qt

    from app.core.activation.key import FORMAT_VERSION, format_key
    from app.ui.dialogs import ActivationDialog
    from app.ui.style import apply_style
    from app.ui.theme import apply_theme

    # Die Betriebslage, und hier hängt die Messgröße wirklich an ihr: Das
    # Stylesheet setzt den Innenabstand des Feldes, also die Breite, über die
    # umbrochen wird. Ohne es bricht der Schlüssel anders um als beim Kunden.
    before = QApplication.instance().styleSheet()
    apply_theme(QApplication.instance(), "dark")
    apply_style(QApplication.instance(), "dark")
    dialog = ActivationDialog()
    try:
        # Mit lesbarer Formatnummer vorn: ``format_key`` lehnt eine Nutzlast ab,
        # die nicht mit einer beginnt, und die Länge bleibt dieselbe.
        dialog.field.setPlainText(format_key(bytes([FORMAT_VERSION]) + b"x" * 63, b"y" * 64))
        dialog.resize(dialog.sizeHint())
        dialog.setAttribute(Qt.WidgetAttribute.WA_DontShowOnScreen, True)
        dialog.show()
        QApplication.processEvents()

        assert dialog.field.verticalScrollBar().maximum() == 0, (
            "der Schlüssel steht nicht ganz im Feld — "
            f"{dialog.field.verticalScrollBar().maximum()} Punkte Rollweg"
        )

        # Und leer bleibt es klein: Ein Feld, das immer sieben Zeilen hoch ist,
        # bezahlt den Platz auch dann, wenn nichts darin steht.
        voll = dialog.field.height()
        dialog.field.setPlainText("")
        QApplication.processEvents()
        assert dialog.field.height() < voll, "das leere Feld ist so hoch wie das volle"
    finally:
        dialog.reject()
        QApplication.instance().setStyleSheet(before)
