"""Der sichtbare Hinweis vor der ersten Arbeit mit Druckeinstellungen (§29).

Solidon rechnet Temperaturen, Geschwindigkeiten und Kühlung aus Material-,
Drucker- und Qualitätsprofilen. Diese Werte bleiben nicht im Programm: Eine
gespeicherte 3MF trägt sie als ``Metadata/project_settings.config`` mit, und
der Slicer übernimmt sie anstelle seiner eigenen. Gemessen an einem Würfel
sind das 1472 Byte ohne und 2468 Byte mit Beilage.

**Der Hinweis ist Information und keine Einwilligung**, wie beim KI-Hinweis
daneben. Anders als dort trägt er aber eine Wahl: ob die Werte mitreisen
sollen. Bis zum 03.09.2026 gab es diese Wahl nicht — wer den
Druckeinstellungs-Dialog **einmal geöffnet und wieder geschlossen** hatte,
dessen Projekt trug die Werte danach dauerhaft, und kein Weg führte zurück.
``Session.set_print_settings`` nahm kein ``None`` entgegen.

Der Hinweis erscheint einmal je Textfassung. Wer ihn gesehen hat, sieht ihn
erst wieder, wenn sich der Text ändert; die Wahl selbst liegt danach im
Druckeinstellungs-Dialog.
"""

from __future__ import annotations

import os
from datetime import UTC, datetime
from enum import Enum
from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QVBoxLayout,
    QWidget,
)

from app.core.log import get_logger
from app.i18n import tr
from app.ui.settings import UiSettings, save_settings
from app.ui.style import ROOMY, TIGHT, make_primary, set_level

#: Fassung des Hinweistextes. Ändert sich der Text inhaltlich, steigt sie, und
#: der Hinweis erscheint erneut — sonst hätte jemand einer Aussage zugestimmt,
#: die er nie gelesen hat.
PRINT_DISCLOSURE_VERSION = "1.1"

_log = get_logger(__name__)


def someone_is_watching() -> bool:
    """Sitzt überhaupt jemand davor?

    Unter ``offscreen`` nicht — und ein modaler Hinweis wartet dort auf einen
    Klick, den es nie gibt. Gemessen am 03.09.2026 von 3d-druck-a0 mit
    ``py-spy``: Der Torlauf stand zwanzig Minuten in ``QDialog::exec`` →
    ``NtUserMsgWaitForMultipleObjectsEx``, und es hätte jeden Test getroffen,
    der die Druckeinstellungen öffnet — samt der CI bis zu ihrem
    Sechs-Stunden-Limit.

    Dasselbe Muster wie :func:`app.ui.motion.animations_enabled`, und aus
    demselben Grund: Wer offscreen läuft, prüft Verhalten und wird nicht
    bedient. Der Merker wird dabei **nicht** gesetzt — beim nächsten Start mit
    Bildschirm erscheint der Hinweis, wie er soll.
    """
    return os.environ.get("QT_QPA_PLATFORM", "") != "offscreen"


class PrintDisclosureResult(Enum):
    """Was der Hinweis ergeben hat."""

    ALREADY_SEEN = "already_seen"
    """Der Text in dieser Fassung war schon einmal zu sehen."""

    NO_ONE_THERE = "no_one_there"
    """Kein Bildschirm — gezeigt wird nichts und gemerkt auch nichts."""

    ACKNOWLEDGED = "acknowledged"
    """Gerade gelesen und bestätigt."""

    FAILED = "failed"
    """Der Hinweis ließ sich nicht zeigen oder nicht merken."""

    @property
    def may_continue(self) -> bool:
        """Darf der Druckeinstellungs-Dialog aufgehen?

        Auch nach einem Fehlschlag: Der Hinweis erklärt, er verbietet nichts.
        Anders als beim KI-Hinweis verlässt hier nichts das Gerät, das eine
        Sperre rechtfertigen würde — die Werte reisen erst, wenn jemand
        speichert oder übergibt, und dafür gibt es die Wahl darunter.
        """
        return True


def _is_utc_timestamp(value: str) -> bool:
    """Ein ISO-8601-Zeitpunkt in UTC, wie ihn :func:`remember_disclosure` schreibt."""
    if not value.endswith("Z"):
        return False
    try:
        datetime.fromisoformat(value)
    except ValueError:
        return False
    return True


def disclosure_is_current(settings: Any) -> bool:
    """Ob der Hinweis in **dieser** Textfassung schon gesehen wurde."""
    return settings.print_disclosure_version == PRINT_DISCLOSURE_VERSION and _is_utc_timestamp(
        settings.print_disclosure_at_utc
    )


def remember_disclosure(settings: Any, *, now: str | None = None) -> None:
    """Merkt Textfassung und UTC-Zeitpunkt."""
    timestamp = now or datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    if not _is_utc_timestamp(timestamp):
        raise ValueError("print disclosure timestamp must be an ISO-8601 UTC timestamp")
    settings.print_disclosure_version = PRINT_DISCLOSURE_VERSION
    settings.print_disclosure_at_utc = timestamp


def clear_disclosure(settings: Any) -> None:
    """Zeigt den Hinweis beim nächsten Mal wieder."""
    settings.print_disclosure_version = ""
    settings.print_disclosure_at_utc = ""


def _title_text() -> str:
    return tr("Druckeinstellungen und Verantwortung")


def _body_text() -> str:
    """Was der Hinweis sagt — an einer Stelle, damit Dialog und Test dasselbe lesen.

    **Der dritte Absatz ist ein Rat und kein Rückzug** (Entscheidung Robert,
    03.09.2026). Die erste Fassung verwies auf „die Nummern 10 und 11 des
    Lizenzvertrags", und das leistete nichts: Ein Vertrag gilt durch den
    Vertragsschluss, nicht dadurch, dass ein Dialog auf ihn zeigt — eine
    Klausel wird im laufenden Programm nicht wirksam einbezogen. Was im
    Streitfall zählt, ist die **Instruktion**, also der Satz, der sagt, was zu
    tun ist. Der Vorbehalt selbst steht vollständig in EULA §10 und gilt
    unabhängig von diesem Fenster.

    Und mitten im Arbeitsschritt liest sich ein Paragrafenverweis wie
    Kleingedrucktes: Der Hinweis soll Vertrauen schaffen, dass wir sagen, was
    geschieht — nicht den Eindruck, dass wir uns absichern.
    """
    return tr(
        "Solidon rechnet Temperaturen, Geschwindigkeiten und Kühlung aus den Profilen "
        "für Material, Drucker und Qualitätsstufe. Das sind Erfahrungswerte und keine "
        "geprüften Vorgaben für Ihren Drucker, Ihr Filament und Ihr Teil.\n\n"
        "Speichern Sie eine 3MF-Datei oder öffnen Sie das Projekt im Slicer, reisen "
        "diese Werte mit. Ihr Slicer übernimmt sie dann anstelle seiner eigenen.\n\n"
        "Prüfen Sie die Werte, bevor Sie drucken — besonders bei einem neuen Filament "
        "oder einem Drucker, den Sie noch nicht kalibriert haben."
    )


def _share_label() -> str:
    return tr("Werte beim Speichern und Übergeben mitgeben")


def _share_note() -> str:
    return tr(
        "Ohne Haken enthält eine gespeicherte 3MF nur die Geometrie, und Ihr Slicer "
        "arbeitet mit seinem eigenen Profil. Sie können das jederzeit in den "
        "Druckeinstellungen ändern."
    )


class PrintDisclosureDialog(QDialog):
    """Der Hinweis mit der Wahl darunter."""

    def __init__(self, share: bool, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(_title_text())
        self.setModal(True)

        layout = QVBoxLayout(self)
        layout.setSpacing(ROOMY)

        heading = QLabel(_title_text(), self)
        set_level(heading, "title")
        heading.setWordWrap(True)
        layout.addWidget(heading)

        body = QLabel(_body_text(), self)
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(body)

        self.share = QCheckBox(_share_label(), self)
        self.share.setChecked(share)
        layout.addWidget(self.share)

        note = QLabel(_share_note(), self)
        note.setWordWrap(True)
        set_level(note, "caption")
        note.setContentsMargins(TIGHT, 0, 0, 0)
        layout.addWidget(note)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, self)
        confirm = buttons.button(QDialogButtonBox.StandardButton.Ok)
        if confirm is not None:
            # Qt beschriftet seine Standardknöpfe in der Sprache des Systems;
            # Regel 20 verlangt den eigenen Katalog.
            confirm.setText(tr("Verstanden"))
            make_primary(confirm)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def shares_settings(self) -> bool:
        """Sollen die Werte mit Dateien und an den Slicer gehen?"""
        return self.share.isChecked()


def ensure_print_disclosure(
    settings: UiSettings, parent: QWidget | None = None
) -> PrintDisclosureResult:
    """Zeigt den Hinweis, falls diese Textfassung noch nicht gesehen wurde.

    Die Wahl aus dem Hinweis landet in ``settings.print_settings_in_files``.
    Wer den Hinweis schon kennt, wird nicht gefragt — seine frühere Wahl gilt
    weiter und ist im Druckeinstellungs-Dialog zu ändern.
    """
    if disclosure_is_current(settings):
        return PrintDisclosureResult.ALREADY_SEEN
    if not someone_is_watching():
        return PrintDisclosureResult.NO_ONE_THERE
    try:
        dialog = PrintDisclosureDialog(settings.print_settings_in_files, parent)
        dialog.exec()
        settings.print_settings_in_files = dialog.shares_settings()
        remember_disclosure(settings)
        save_settings(settings)
    except Exception:  # ein Hinweis darf die Arbeit nicht anhalten
        _log.exception("print disclosure could not be shown")
        return PrintDisclosureResult.FAILED
    return PrintDisclosureResult.ACKNOWLEDGED
