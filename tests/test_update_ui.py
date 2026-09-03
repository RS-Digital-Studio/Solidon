"""Das Update-Fenster (Bauplan §37.2).

Was hier geprüft wird, ist nicht das Herunterladen — das steht in
``test_updates.py`` und braucht kein Qt. Hier geht es um die Zusagen, die das
Fenster gibt: dass es sagt, was neu ist; dass es nichts anbietet, was es nicht
kann; und dass zwischen dem geprüften Paket und dem Start noch ein Klick liegt.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from PySide6.QtWidgets import QApplication

from app.core import updates
from app.ui.update_dialog import UpdateDialog


def release(**changes: object) -> updates.Release:
    """Ein Fund, wie ihn ``updates.check`` liefert."""
    values: dict[str, object] = {
        "version": "99.0.0",
        "url": "https://solidon3d.de/",
        "notes": "Zweiter Bau der Demo.",
        "packages": {
            updates.PLATFORM_WINDOWS: updates.Package(
                file="Solidon3D-Setup-99.0.0.exe",
                url="https://solidon3d.de/dl/Solidon3D-Setup-99.0.0.exe",
                size=179_452_109,
                sha256="a" * 64,
            )
        },
        "changes": {"de": ("Der erste Punkt.", "Der zweite Punkt.")},
    }
    values.update(changes)
    return updates.Release(**values)  # type: ignore[arg-type]


def test_the_window_says_what_is_new(qt_app: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
    """Der Grund, aus dem es diesen Kasten gibt.

    Vorher stand eine Zeile in der Statusleiste: Version und Adresse, die
    Adresse als Text. Wer vor der Frage steht, ob er aktualisieren soll, hatte
    nichts, woran er sie beantworten könnte.
    """
    monkeypatch.setattr(updates, "packaged", lambda: True)
    monkeypatch.setattr(updates.sys, "platform", "win32")

    dialog = UpdateDialog(release())

    assert "Der erste Punkt." in dialog.changes.text()
    assert "Der zweite Punkt." in dialog.changes.text()
    assert dialog.scroller.isVisible() or not dialog.isVisible()


def shown_text(dialog: UpdateDialog) -> str:
    """Was auf dem Schirm steht, nicht was gesetzt wurde.

    Der Kasten trägt seit dieser Fassung Auszeichnung; ``label.text()`` gibt
    dann das **HTML** zurück. Eine Prüfung darauf wäre grün, auch wenn Qt
    daraus nichts machen kann — die bekannte Falle: gesetzt heißt nicht
    gezeigt. ``QTextDocument`` rendert dieselbe Zeichenkette wie das Label und
    gibt den Text, den ein Mensch liest.
    """
    from PySide6.QtGui import QTextDocument

    document = QTextDocument()
    document.setHtml(dialog.changes.text())
    return document.toPlainText()


def test_the_window_shows_the_headings_of_the_changelog(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Dasselbe gegliedert wie unter *Hilfe → Neuerungen* (Roberts Auftrag).

    Der Parser kennt die Gruppen seit 0.2.0 und der Verlaufs-Dialog zeigt sie;
    nur der Weg über die Versionsdatei war flach. Jetzt trägt sie beide
    Sichten, und dieses Fenster nimmt die gegliederte.
    """
    from app.core.changes import Group

    monkeypatch.setattr(updates, "packaged", lambda: True)
    monkeypatch.setattr(updates.sys, "platform", "win32")

    dialog = UpdateDialog(
        release(
            changes={"de": ("Vorn.", "Gezeichnet.")},
            groups={
                "de": (
                    Group(title="", points=("Vorn.",)),
                    Group(title="Zeichnen", points=("Gezeichnet.",)),
                )
            },
        )
    )

    gezeigt = shown_text(dialog)
    assert "Zeichnen" in gezeigt, f"die Überschrift kam nicht an: {gezeigt!r}"
    assert "Gezeichnet." in gezeigt
    assert "Vorn." in gezeigt
    assert "<b>" not in gezeigt, "die Auszeichnung steht als Text da statt zu wirken"


def test_a_release_without_groups_still_lists_its_points(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Rückfall, und er ist der Regelfall für jede ältere Versionsdatei.

    Eine ``version.json`` ohne ``groups`` — jede, die vor dieser Fassung
    geschrieben wurde — muss dieselbe Liste zeigen wie bisher. Der Rückfall
    liegt im Kern (``Release.grouped``), nicht im Fenster; geprüft wird er
    hier, weil hier steht, was der Kunde sieht.
    """
    monkeypatch.setattr(updates, "packaged", lambda: True)
    monkeypatch.setattr(updates.sys, "platform", "win32")

    dialog = UpdateDialog(release())

    gezeigt = shown_text(dialog)
    assert "Der erste Punkt." in gezeigt
    assert "Der zweite Punkt." in gezeigt


def test_the_changelog_box_opens_no_browser_and_lets_you_copy(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Zwei Zusagen an einem Kasten, der seit dieser Fassung Auszeichnung trägt.

    **Keine Verweise nach draußen.** Der Verlauf unter *Hilfe → Neuerungen*
    nennt diese Zurückhaltung sein Vorbild („dieselbe wie beim
    Update-Fenster") — und hier stand sie nicht. Das war harmlos, solange der
    Kasten Klartext zeigte: Ein Verweis konnte gar nicht wirken. Mit der
    Auszeichnung ändert sich das, und der Unterschied zum Verlauf ist die
    Herkunft: Der liest aus dem eigenen Paket, dieser Kasten zeigt einen Text
    **vom Server**. ``groups_html`` maskiert jeden Punkt, es entsteht also kein
    ``<a>``; der Schalter ist die zweite Linie.

    **Und markieren muss man können.** Wer eine Neuerung nachschlagen will,
    nimmt den Satz mit — im Verlauf geht das seit je. Zwei Fenster, die
    dieselbe Auskunft zeigen, sollen sich auch gleich anfassen lassen.
    """
    from PySide6.QtCore import Qt

    monkeypatch.setattr(updates, "packaged", lambda: True)
    monkeypatch.setattr(updates.sys, "platform", "win32")

    dialog = UpdateDialog(release())

    assert not dialog.changes.openExternalLinks(), (
        "ein Verweis aus der Versionsdatei öffnete ungefragt einen Browser"
    )
    assert dialog.changes.textInteractionFlags() & Qt.TextInteractionFlag.TextSelectableByMouse, (
        "der Text lässt sich nicht markieren — im Verlauf geht es"
    )


def test_a_link_from_the_server_stays_a_harmless_sentence(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Auszeichnung aus der Antwort wird gezeigt, nicht ausgeführt.

    Die erste Linie, und die tragende: ``groups_html`` maskiert. Ein Punkt, der
    wie ein Verweis aussieht, steht danach als **Text** da — samt spitzer
    Klammern, die man lesen kann. Das ist auch der Grund, aus dem maskiert
    wird: Ein Satz mit einem ``<`` verschwände sonst bis zum nächsten ``>``,
    und das ist kein Angriff, nur ein fehlender Satz.
    """
    from app.core.changes import Group

    monkeypatch.setattr(updates, "packaged", lambda: True)
    monkeypatch.setattr(updates.sys, "platform", "win32")

    dialog = UpdateDialog(
        release(
            changes={"de": ('Ein <a href="https://fremd.test">Verweis</a>.',)},
            groups={
                "de": (Group(title="", points=('Ein <a href="https://fremd.test">Verweis</a>.',)),)
            },
        )
    )

    gezeigt = shown_text(dialog)
    assert "fremd.test" in gezeigt, "der Satz kam gar nicht an"
    assert "<a href=" in gezeigt, "die Auszeichnung wurde gedeutet statt gezeigt"


def test_without_points_the_list_stays_away(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein leerer Kasten ist eine Überschrift ohne Inhalt."""
    monkeypatch.setattr(updates, "packaged", lambda: True)
    monkeypatch.setattr(updates.sys, "platform", "win32")

    dialog = UpdateDialog(release(changes={}))

    assert not dialog.changes.text()
    assert dialog.scroller.isHidden()


def test_the_offer_names_the_size(qt_app: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(updates, "packaged", lambda: True)
    monkeypatch.setattr(updates.sys, "platform", "win32")

    dialog = UpdateDialog(release())

    assert "171" in dialog.state.text(), "179 452 109 Bytes sind 171 MB"
    assert dialog.get_button.isVisible() or not dialog.isVisible()


def test_where_nothing_can_be_started_the_page_takes_the_lead(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unter Linux und aus den Quellen gibt es nichts zu holen.

    Ein Knopf, der nichts kann, ist schlimmer als keiner — also verschwindet
    er, und der Weg zur Seite bekommt den Hauptknopf.
    """
    monkeypatch.setattr(updates, "packaged", lambda: True)
    monkeypatch.setattr(updates.sys, "platform", "linux")

    dialog = UpdateDialog(release())

    assert dialog.get_button.isHidden()
    assert dialog.page_button.isDefault()


def test_a_ready_package_still_needs_a_click(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Geladen und geprüft heißt nicht gestartet (§37.2).

    Zwischen der fertigen Datei und dem Installationsprogramm liegt der Klick,
    der die ganze Regel trägt — und das Fenster sagt vorher, was danach
    passiert.
    """
    monkeypatch.setattr(updates, "packaged", lambda: True)
    monkeypatch.setattr(updates.sys, "platform", "win32")
    package = tmp_path / "Solidon3D-Setup-99.0.0.exe"
    package.write_bytes(b"ein Paket")

    dialog = UpdateDialog(release())
    gemeldet: list[object] = []
    dialog.installRequested.connect(gemeldet.append)

    dialog._downloaded(package)

    assert not gemeldet, "die fertige Datei allein startet nichts"
    assert "beendet" in dialog.state.text()

    dialog._start()

    assert gemeldet == [package]


def test_cancelling_says_that_nothing_is_left(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein Abbruch ist kein Fehler (§15.6) — und die Auskunft, dass nichts
    liegen bleibt, nimmt die Frage vorweg."""
    monkeypatch.setattr(updates, "packaged", lambda: True)
    monkeypatch.setattr(updates.sys, "platform", "win32")

    dialog = UpdateDialog(release())
    dialog._was_cancelled()

    assert "Abgebrochen" in dialog.state.text()
    assert dialog.get_button.isVisible() or not dialog.isVisible()


def test_a_problem_offers_the_page(qt_app: QApplication, monkeypatch: pytest.MonkeyPatch) -> None:
    """Regel 17: Ein Fehler endet nie mit „fehlgeschlagen"."""
    monkeypatch.setattr(updates, "packaged", lambda: True)
    monkeypatch.setattr(updates.sys, "platform", "win32")
    from app.core.errors import ExternalToolError

    dialog = UpdateDialog(release())
    dialog._failed(ExternalToolError(tool="update", detail="Die Leitung riss ab."))

    assert "Leitung" in dialog.state.text()
    assert dialog.page_button.isEnabled()


def test_the_progress_counts_in_the_bar(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(updates, "packaged", lambda: True)
    monkeypatch.setattr(updates.sys, "platform", "win32")

    dialog = UpdateDialog(release())
    dialog._stepped(0.5, "90 / 179 MB")

    assert dialog.progress.value() == 50
    assert "90" in dialog.state.text()


def test_a_capped_list_points_at_the_full_changelog(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Der Kunde soll sehen, dass er eine Auswahl liest — und wo die ganze steht.

    Die Versionsdatei muss unter die Lesegrenze der ausgelieferten Fassungen
    passen und trägt deshalb nicht alle Punkte. In 0.3.0 fiel dabei
    ausgerechnet der Punkt weg, der einen gemeldeten Absturz beantwortete;
    ohne diesen Satz sähe die gekürzte Liste aus wie die ganze.
    """
    monkeypatch.setattr(updates, "packaged", lambda: True)
    monkeypatch.setattr(updates.sys, "platform", "win32")

    dialog = UpdateDialog(release(changes_total=115))

    text = dialog.more.text()
    assert dialog.more.isVisibleTo(dialog)
    assert "2" in text and "115" in text, "die Zahlen sagen, wie viel fehlt"
    assert 'href="https://solidon3d.de/changelog.html"' in text
    assert dialog.more.openExternalLinks(), "der Verweis soll auch wirken"


def test_a_complete_list_says_nothing_about_a_website(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Wo nichts fehlt, schickt auch nichts nach draußen.

    Beide Fälle, die „vollständig" heißen: Die Datei nennt die Gesamtzahl und
    sie stimmt, oder sie nennt gar keine — eine Versionsdatei von vor dieser
    Fassung.
    """
    monkeypatch.setattr(updates, "packaged", lambda: True)
    monkeypatch.setattr(updates.sys, "platform", "win32")

    for total in (2, 0):
        dialog = UpdateDialog(release(changes_total=total))

        assert not dialog.more.isVisibleTo(dialog), f"changes_total={total}"
        assert not dialog.more.text()


def test_the_link_follows_the_language_of_the_window(
    qt_app: QApplication, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Ein deutscher Satz mit einer englischen Seite dahinter wäre halb übersetzt."""
    monkeypatch.setattr(updates, "packaged", lambda: True)
    monkeypatch.setattr(updates.sys, "platform", "win32")
    monkeypatch.setattr("app.ui.update_dialog.get_language", lambda: "pt")

    dialog = UpdateDialog(release(changes_total=115))

    assert 'href="https://solidon3d.de/pt/changelog.html"' in dialog.more.text()
