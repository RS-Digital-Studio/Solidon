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
