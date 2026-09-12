"""Der Hinweis vor der ersten Arbeit mit Druckeinstellungen (§29).

Was Solidon rechnet, bleibt nicht im Programm: Eine gespeicherte 3MF trägt
Temperaturen, Geschwindigkeiten und Kühlung mit, und der Slicer übernimmt sie
anstelle seiner eigenen. Der Hinweis sagt das einmal je Textfassung und lässt
dabei wählen, ob es so sein soll.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication, QLabel

import app.ui.ai_disclosure as ai_disclosure_module
import app.ui.print_disclosure as print_disclosure_module
import app.ui.settings
from app.ui.print_disclosure import (
    PRINT_DISCLOSURE_VERSION,
    PrintDisclosureDialog,
    PrintDisclosureResult,
    clear_disclosure,
    disclosure_is_current,
    ensure_print_disclosure,
    remember_disclosure,
)
from app.ui.settings import UiSettings, is_utc_timestamp


@pytest.fixture(autouse=True)
def _no_real_settings_write(monkeypatch: pytest.MonkeyPatch) -> None:
    """Kein Test schreibt in die echten Oberflächeneinstellungen."""
    monkeypatch.setattr(
        "app.ui.print_disclosure.save_settings", lambda _settings: Path("settings.json")
    )


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

    **Die letzten drei Werte kamen am 07.09.2026 dazu, und einer davon ist
    der eigentliche Ertrag:** Dieses Modul brachte seine eigene Prüfung mit,
    und die war laxer als die des KI-Hinweises daneben — sie sah nur das ``Z``
    am Ende. ``"2026-09-03 06:00:00Z"`` ging damit als UTC-Zeitpunkt durch,
    denn ``datetime.fromisoformat`` nimmt das Leerzeichen als Trenner an; der
    KI-Hinweis verlangte daneben ein ``T``. Gemessen, nicht vermutet — und
    die Messung hat zwei Drittel der Annahme widerlegt: Ein blankes Datum mit
    ``Z`` und ein Zeitpunkt ohne ``Z`` fielen bei **beiden** Prüfungen durch.
    Sie stehen als Absicherung dabei, nicht als Beleg. Beide Module fragen
    jetzt :func:`app.ui.settings.is_utc_timestamp`.
    """
    settings = UiSettings()
    settings.print_disclosure_version = PRINT_DISCLOSURE_VERSION
    broken_values = (
        "",
        "gestern",
        "2026-09-03T06:00:00+02:00",
        "2026-09-03Z",
        "2026-09-03 06:00:00Z",
        "2026-09-03T06:00:00",
    )
    for broken in broken_values:
        settings.print_disclosure_at_utc = broken
        assert not disclosure_is_current(settings), f"{broken!r} ist kein UTC-Zeitpunkt"


def test_both_notices_ask_the_same_source_what_a_utc_timestamp_is() -> None:
    """Die Frage „ist das ein UTC-Zeitpunkt" wird an **einer** Stelle beantwortet.

    Beide Hinweise merken Textfassung und Zeitpunkt in denselben
    Einstellungen, und beide brachten bis zum 07.09.2026 ihre eigene Prüfung
    mit — kopiert und dabei abgeschwächt (siehe den Test darüber). Zwei
    Wahrheiten darüber, was ein Merker ist, in zwei Modulen, die
    nebeneinanderliegen.

    Geprüft wird der Quelltext und nicht das Verhalten: Ein zweites Modul mit
    eigener Prüfung verhält sich am Tag seiner Entstehung richtig, und der
    Test wäre grün. Auffallen soll die **Bauart**.
    """
    ui = Path(app.ui.settings.__file__).parent
    dateien = sorted(path for path in ui.rglob("*.py") if path.name != "settings.py")
    assert len(dateien) > 30, f"nur {len(dateien)} Dateien gefunden — sucht der Test noch etwas?"

    stellen = [
        f"{path.name}:{nummer}"
        for path in dateien
        for nummer, zeile in enumerate(path.read_text(encoding="utf-8").splitlines(), 1)
        if ("utcoffset" in zeile or 'endswith("Z")' in zeile)
        and not zeile.lstrip().startswith(("#", "*", '"""'))
    ]
    assert not stellen, (
        "eine zweite Zeitstempelprüfung in der Oberfläche — sie gehört nach "
        f"app.ui.settings.is_utc_timestamp: {', '.join(stellen)}"
    )

    for modul in (print_disclosure_module, ai_disclosure_module):
        assert modul.is_utc_timestamp is is_utc_timestamp, (
            f"{modul.__name__} prüft nicht mit der geteilten Funktion"
        )


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
        return int(PrintDisclosureDialog.DialogCode.Accepted)

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


@pytest.mark.parametrize("answer", ["escape", "close"])
def test_leaving_the_print_notice_keeps_the_previous_choice(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, answer: str
) -> None:
    """Ein verworfener Haken entscheidet weder die Dateibeilage noch den Nachweis."""
    from PySide6.QtCore import Qt
    from PySide6.QtTest import QTest

    stored: list[object] = []
    monkeypatch.setattr("app.ui.print_disclosure.someone_is_watching", lambda: True)
    monkeypatch.setattr("app.ui.print_disclosure.save_settings", lambda value: stored.append(value))

    def leave(dialog: PrintDisclosureDialog) -> int:
        dialog.show()
        dialog.share.setChecked(False)
        if answer == "escape":
            QTest.keyClick(dialog, Qt.Key.Key_Escape)
        else:
            dialog.close()
        return int(dialog.result())

    monkeypatch.setattr(PrintDisclosureDialog, "exec", leave)
    settings = UiSettings()
    result = ensure_print_disclosure(settings)
    assert settings.print_settings_in_files
    assert not settings.print_disclosure_version
    assert not settings.print_disclosure_at_utc
    assert not stored
    assert result.may_continue
    assert result is not PrintDisclosureResult.ACKNOWLEDGED


def test_a_failed_print_notice_save_remains_retryable(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Ein echter Schreibfehler meldet FAILED und lässt keinen bloßen Speichermerker gelten."""
    from app.ui import settings as settings_module

    settings = UiSettings()
    destination = tmp_path / "settings.json"
    monkeypatch.setattr(settings_module, "settings_path", lambda: destination)
    monkeypatch.setattr("app.ui.print_disclosure.someone_is_watching", lambda: True)
    monkeypatch.setattr("app.ui.print_disclosure.save_settings", settings_module.save_settings)
    original_replace = Path.replace

    def refuse(path: Path, target: Path) -> Path:
        if Path(target) == destination:
            raise OSError("disk full")
        return original_replace(path, target)

    shown: list[bool] = []

    def accept(dialog: PrintDisclosureDialog) -> int:
        shown.append(True)
        dialog.share.setChecked(False)
        return int(PrintDisclosureDialog.DialogCode.Accepted)

    monkeypatch.setattr(PrintDisclosureDialog, "exec", accept)
    monkeypatch.setattr(Path, "replace", refuse)
    result = ensure_print_disclosure(settings)
    assert result is PrintDisclosureResult.FAILED
    assert result.may_continue
    assert not disclosure_is_current(settings)
    assert not destination.exists()
    monkeypatch.setattr(Path, "replace", original_replace)
    assert ensure_print_disclosure(settings) is PrintDisclosureResult.ACKNOWLEDGED
    assert shown == [True, True]
    assert disclosure_is_current(settings_module.load_settings())
    assert not settings_module.load_settings().print_settings_in_files


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
