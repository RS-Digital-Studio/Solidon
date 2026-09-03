"""Der Hinweis vor der ersten Arbeit mit Druckeinstellungen (§29).

Was Solidon rechnet, bleibt nicht im Programm: Eine gespeicherte 3MF trägt
Temperaturen, Geschwindigkeiten und Kühlung mit, und der Slicer übernimmt sie
anstelle seiner eigenen. Der Hinweis sagt das einmal je Textfassung und lässt
dabei wählen, ob es so sein soll.
"""

from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QLabel

from app.ui.print_disclosure import (
    PRINT_DISCLOSURE_VERSION,
    PrintDisclosureDialog,
    PrintDisclosureResult,
    clear_disclosure,
    disclosure_is_current,
    ensure_print_disclosure,
    remember_disclosure,
)
from app.ui.settings import UiSettings


@pytest.fixture(autouse=True)
def _no_real_settings_write(monkeypatch: pytest.MonkeyPatch) -> None:
    """Kein Test schreibt in die echten Oberflächeneinstellungen."""
    monkeypatch.setattr("app.ui.print_disclosure.save_settings", lambda _settings: None)


def test_a_fresh_installation_has_not_seen_the_notice() -> None:
    """Sonst wäre der Hinweis eine Zusicherung über etwas nie Gezeigtes."""
    assert not disclosure_is_current(UiSettings())


def test_the_notice_counts_as_seen_only_in_this_wording() -> None:
    """Ändert sich der Text inhaltlich, wird er wieder gezeigt.

    Eine gemerkte Zustimmung zu einer Fassung, die niemand gelesen hat, wäre
    keine — deshalb steht die Fassung im Merker und nicht nur ein Ja.
    """
    settings = UiSettings()
    remember_disclosure(settings)
    assert disclosure_is_current(settings)
    assert settings.print_disclosure_version == PRINT_DISCLOSURE_VERSION
    assert settings.print_disclosure_at_utc.endswith("Z")

    settings.print_disclosure_version = "0.9"
    assert not disclosure_is_current(settings), "eine ältere Fassung zählt nicht"

    clear_disclosure(settings)
    assert not disclosure_is_current(settings)


def test_a_broken_timestamp_does_not_count_as_seen() -> None:
    """Ein Merker ohne gültigen Zeitpunkt ist kein Beleg.

    Er entsteht, wenn jemand die Einstellungsdatei von Hand ändert — und ein
    halb gefüllter Merker darf den Hinweis nicht unterdrücken.
    """
    settings = UiSettings()
    settings.print_disclosure_version = PRINT_DISCLOSURE_VERSION
    for broken in ("", "gestern", "2026-09-03T06:00:00+02:00"):
        settings.print_disclosure_at_utc = broken
        assert not disclosure_is_current(settings), f"{broken!r} ist kein UTC-Zeitpunkt"


def test_the_notice_says_what_leaves_the_programme(qt_app: QApplication) -> None:
    """Der Text nennt die drei Dinge, für die er da ist.

    Erstens, dass es Erfahrungswerte sind; zweitens, dass sie mit der Datei
    reisen; drittens, was der Kunde deshalb tun soll.

    **Der dritte Punkt ist ein Rat und kein Paragrafenverweis** (Entscheidung
    Robert, 03.09.2026). Die erste Fassung nannte „die Nummern 10 und 11 des
    Lizenzvertrags" — rechtlich wirkungslos, denn ein Vertrag gilt durch den
    Vertragsschluss und nicht dadurch, dass ein Dialog auf ihn zeigt. Was
    trägt, ist die Instruktion; der Vorbehalt selbst steht in EULA §10 und
    gilt unabhängig von diesem Fenster.
    """
    dialog = PrintDisclosureDialog(share=True, parent=None)
    whole = "\n".join(
        [dialog.windowTitle(), dialog.share.text()]
        + [label.text() for label in dialog.findChildren(QLabel)]
    )

    assert "Erfahrungswerte" in whole
    assert "3MF" in whole and "Slicer" in whole
    assert "bevor Sie drucken" in whole, "der Rat ist die eigentliche Schutzwirkung"
    assert "Lizenzvertrag" not in whole, (
        "kein Paragrafenverweis mitten im Arbeitsschritt — er liest sich als "
        "Kleingedrucktes und leistet rechtlich nichts"
    )


def test_the_choice_from_the_notice_reaches_the_settings(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Was im Hinweis gewählt wird, gilt danach beim Speichern und Übergeben.

    Die Gegenprobe steckt im zweiten Durchgang: Wer den Hinweis schon kennt,
    wird nicht erneut gefragt — sonst wäre er eine Frage bei jedem Öffnen des
    Druckdialogs, und Regel 19 kennt keine Bestätigung vor rücknehmbaren
    Handlungen.
    """
    shown: list[bool] = []

    def _answer(dialog: PrintDisclosureDialog) -> int:
        shown.append(True)
        dialog.share.setChecked(False)
        return 0

    monkeypatch.setattr(PrintDisclosureDialog, "exec", _answer)
    # Die Suite läuft offscreen, und dort erscheint der Hinweis mit Absicht
    # nicht. Für diesen Test wird die Lage hergestellt, die er prüft: jemand
    # sitzt davor.
    monkeypatch.setenv("QT_QPA_PLATFORM", "windows")

    settings = UiSettings()
    assert settings.print_settings_in_files, "vorbelegt wie der bisherige Weg"

    result = ensure_print_disclosure(settings, None)
    assert result is PrintDisclosureResult.ACKNOWLEDGED
    assert shown == [True], "einmal gezeigt"
    assert not settings.print_settings_in_files, "die Wahl aus dem Hinweis gilt"

    again = ensure_print_disclosure(settings, None)
    assert again is PrintDisclosureResult.ALREADY_SEEN
    assert shown == [True], "und kein zweites Mal gefragt"
    assert not settings.print_settings_in_files, "die frühere Wahl bleibt"


def test_a_failing_notice_does_not_block_the_dialog(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Hinweis, der nicht aufgeht, hält die Arbeit nicht an.

    Anders als beim KI-Hinweis verlässt hier nichts das Gerät, das eine Sperre
    rechtfertigen würde: Die Werte reisen erst beim Speichern oder Übergeben,
    und dafür steht die Wahl im Druckeinstellungs-Dialog.
    """

    def _broken(_dialog: PrintDisclosureDialog) -> int:
        raise RuntimeError("kein Bildschirm")

    monkeypatch.setattr(PrintDisclosureDialog, "exec", _broken)
    monkeypatch.setenv("QT_QPA_PLATFORM", "windows")  # wie oben: jemand sitzt davor

    settings = UiSettings()
    result = ensure_print_disclosure(settings, None)

    assert result is PrintDisclosureResult.FAILED
    assert result.may_continue, "der Druckdialog geht trotzdem auf"
    assert not disclosure_is_current(settings), "und beim nächsten Mal wird es erneut versucht"


def test_no_dialog_appears_where_no_one_is_sitting(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein modaler Hinweis im Testlauf hält alles an — und zwar unbegrenzt.

    Gemessen am 03.09.2026 von 3d-druck-a0 mit `py-spy`: Der Torlauf stand
    zwanzig Minuten in `QDialog::exec` → `NtUserMsgWaitForMultipleObjectsEx`
    und wartete auf einen Klick, den es offscreen nie gibt. Betroffen war
    jeder Test, der die Druckeinstellungen öffnet, und die CI bis zu ihrem
    Sechs-Stunden-Limit.

    Der Merker bleibt dabei leer: Wer offscreen läuft, hat den Hinweis nicht
    gesehen, und beim nächsten Start mit Bildschirm erscheint er.
    """
    shown: list[bool] = []
    monkeypatch.setattr(PrintDisclosureDialog, "exec", lambda dialog: shown.append(True) or 0)
    monkeypatch.setenv("QT_QPA_PLATFORM", "offscreen")

    settings = UiSettings()
    result = ensure_print_disclosure(settings, None)

    assert result is PrintDisclosureResult.NO_ONE_THERE
    assert shown == [], "kein Dialog, wo niemand klicken kann"
    assert not disclosure_is_current(settings), "und nichts gemerkt, was niemand sah"
    assert settings.print_settings_in_files, "die Wahl bleibt, wie sie war"
