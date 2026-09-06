"""Der sichtbare KI-Hinweis unmittelbar vor dem ersten Modellaufruf (P0-08).

Der Hinweis ist Information, keine Einwilligung. Entscheidend ist seine
Position: Erst ein vollständig aufgebauter, erreichbarer und zugänglicher
Inhalt öffnet die Sendegrenze für den gerade ausgewählten Übertragungsweg.
"""

from __future__ import annotations

import ipaddress
import urllib.parse
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer, QUrl, Signal
from PySide6.QtGui import (
    QAccessible,
    QAccessibleActionInterface,
    QDesktopServices,
    QFont,
    QKeyEvent,
    QResizeEvent,
    QShowEvent,
)
from PySide6.QtWidgets import (
    QCommandLinkButton,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.core.backends import llm
from app.core.log import get_logger
from app.i18n import tr
from app.ui.settings import UiSettings, save_settings
from app.ui.style import ROOMY, TIGHT, WIDE, make_primary, set_level

AI_DISCLOSURE_VERSION = "1.4"
SUPPORTED_AI_BACKENDS = frozenset({"anthropic", "ollama"})
ANTHROPIC_PRIVACY_URL = "https://www.anthropic.com/legal/privacy"
ANTHROPIC_COMMERCIAL_TERMS_URL = "https://www.anthropic.com/legal/commercial-terms"
_LOCAL_PRIVACY_LINK = "solidon:privacy"
_ALLOWED_EXTERNAL_LINKS = frozenset({ANTHROPIC_PRIVACY_URL, ANTHROPIC_COMMERCIAL_TERMS_URL})

_log = get_logger(__name__)


@dataclass(frozen=True, slots=True)
class AiDisclosureTarget:
    """Tatsächlicher Modellweg, einschließlich normalisierter Datenadresse."""

    backend: str
    target_class: str
    address: str

    @property
    def record_key(self) -> str:
        return f"{self.backend}:{self.target_class}:{self.address}"


class DisclosureResult(Enum):
    """Warum die Modellgrenze offen blieb oder geschlossen wurde."""

    CURRENT = "current"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    FAILED = "failed"

    @property
    def allowed(self) -> bool:
        return self in {DisclosureResult.CURRENT, DisclosureResult.ACCEPTED}


def target_for_backend(backend: Any) -> AiDisclosureTarget | None:
    """Leitet den effektiven Datenweg aus dem wirklich gewählten Backend ab."""

    backend_id = str(getattr(backend, "id", "")) if backend is not None else ""
    if backend_id == "scripted":
        return None
    if backend_id == "anthropic":
        return AiDisclosureTarget(
            "anthropic", "hosted", _normalised_http_address(llm.ANTHROPIC_URL)
        )
    if backend_id == "ollama":
        configured = getattr(backend, "url", None)
        if not isinstance(configured, str) or not configured.strip():
            configured = llm.OllamaBackend().url
        return target_for_ollama(configured)
    raise ValueError(f"unsupported AI disclosure backend: {backend_id}")


def target_for_ollama(url: str | None = None) -> AiDisclosureTarget:
    """Bindet Ollama an Loopback oder die konkrete entfernte Zieladresse."""

    effective = llm.ollama_endpoint(url)
    address = _normalised_http_address(effective)
    host = urllib.parse.urlsplit(address).hostname
    if host is None:
        raise ValueError("Ollama disclosure target has no host")
    return AiDisclosureTarget("ollama", "local" if _is_loopback(host) else "remote", address)


def _normalised_http_address(url: str) -> str:
    """Normalisiert ein HTTP-Ziel ohne Zugangsdaten, Abfrage oder Fragment."""

    parts = urllib.parse.urlsplit(url.strip())
    scheme = parts.scheme.lower()
    host = (parts.hostname or "").lower().rstrip(".")
    if scheme not in {"http", "https"} or not host:
        raise ValueError("AI disclosure target must be an HTTP(S) address")
    try:
        port = parts.port
    except ValueError as problem:
        raise ValueError("AI disclosure target has an invalid port") from problem
    shown_host = f"[{host}]" if ":" in host else host
    default_port = (scheme == "http" and port == 80) or (scheme == "https" and port == 443)
    netloc = shown_host if port is None or default_port else f"{shown_host}:{port}"
    return urllib.parse.urlunsplit((scheme, netloc, "", "", ""))


def _is_loopback(host: str) -> bool:
    if host == "localhost" or host.endswith(".localhost"):
        return True
    try:
        return ipaddress.ip_address(host).is_loopback
    except ValueError:
        return False


def _title_text() -> str:
    return tr("Interaktion mit einem KI-System")


def _general_text() -> str:
    return tr(
        "Sie interagieren mit einem KI-System. Antworten können falsch oder "
        "unvollständig sein. Solidon führt daraus keine Geometrie ungeprüft aus: "
        "Ein Vorschlag bleibt sichtbar, prüfbar und mit einem Schritt rücknehmbar."
    )


def _provider_text(target: AiDisclosureTarget) -> str:
    if target.backend == "anthropic":
        return tr(
            "Wenn Sie Anthropic wählen, werden Ihre Chatnachricht und die zuvor angezeigte "
            "Projektauswahl nicht allein übertragen. Direkt an Anthropic gehen die aktuelle "
            "Nachricht, bis zu zwölf frühere Chatbeiträge, ein textlicher Steckbrief der "
            "gesamten aktuellen Szene mit Objekt- und Quellnamen, Maßen, Merkmalen, "
            "Parametern, Einstellungen und Auswahl, der Prüfbericht sowie die für den "
            "Agenten nötigen Anweisungen, Regeln und Werkzeugschemata. Unterstützt das "
            "gewählte Modell Bilder, kann Solidon außerdem automatisch gerenderte Ansichten "
            "der Szene mitsenden. Die Projektdatei und die Netzgeometrie selbst werden nicht "
            "übertragen. Sie verwenden Ihren eigenen API-Schlüssel."
        )
    if target.target_class == "local":
        return tr(
            "Das lokale Ollama-Ziel {target} verarbeitet auf diesem Rechner dieselben "
            "Arbeitsdaten wie der Chat: aktuelle Nachricht, bis zu zwölf frühere "
            "Chatbeiträge, textlichen Steckbrief der gesamten Szene, Prüfbericht, "
            "Anweisungen, Regeln und Werkzeugschemata sowie bei einem Bildmodell "
            "automatisch gerenderte Ansichten. Projektdatei und Netzgeometrie selbst "
            "werden nicht übertragen. Die Werkzeugprobe sendet nur einen festen "
            "technischen Prüfauftrag ohne Projekt- oder Chatinhalt. Installation, "
            "Download oder Update des Modells können gesondert eine Netzverbindung "
            "verwenden.",
            target=target.address,
        )
    return tr(
        "Das Ollama-Ziel {target} liegt auf einem anderen Rechner. An diese Adresse "
        "werden aktuelle Nachricht, bis zu zwölf frühere Chatbeiträge, der textliche "
        "Steckbrief der gesamten Szene, Prüfbericht, Anweisungen, Regeln und "
        "Werkzeugschemata sowie bei einem Bildmodell automatisch gerenderte Ansichten "
        "übertragen. Projektdatei und Netzgeometrie selbst werden nicht übertragen. Die "
        "Werkzeugprobe sendet einen festen technischen Prüfauftrag. Verwenden Sie nur ein "
        "Ziel, dessen Betreiber und Übertragungsweg Sie vertrauen.",
        target=target.address,
    )


def disclosure_is_current(settings: Any, target: AiDisclosureTarget) -> bool:
    """Ob Textfassung, Anbieter und tatsächliches Datenziel unverändert sind."""

    return (
        target.backend in SUPPORTED_AI_BACKENDS
        and settings.ai_disclosure_version == AI_DISCLOSURE_VERSION
        and settings.ai_disclosure_backend == target.backend
        and settings.ai_disclosure_target == target.record_key
        and _is_utc_timestamp(settings.ai_disclosure_at_utc)
    )


def remember_disclosure(
    settings: Any, target: AiDisclosureTarget, *, now: str | None = None
) -> None:
    """Merkt Textfassung, Backend, geheimnisbereinigtes Ziel und UTC-Zeitpunkt."""

    if target.backend not in SUPPORTED_AI_BACKENDS or not target.record_key:
        raise ValueError(f"unsupported AI disclosure backend: {target.backend}")
    timestamp = now or datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")
    if not _is_utc_timestamp(timestamp):
        raise ValueError("AI disclosure timestamp must be an ISO-8601 UTC timestamp")
    settings.ai_disclosure_version = AI_DISCLOSURE_VERSION
    settings.ai_disclosure_backend = target.backend
    settings.ai_disclosure_target = target.record_key
    settings.ai_disclosure_at_utc = timestamp


def clear_disclosure(settings: Any) -> None:
    """Schließt die Sendesperre wieder; Projekt und Chat bleiben unangetastet."""

    settings.ai_disclosure_version = ""
    settings.ai_disclosure_backend = ""
    settings.ai_disclosure_target = ""
    settings.ai_disclosure_at_utc = ""


def ensure_ai_disclosure(
    settings: UiSettings,
    backend_or_target: Any,
    parent: QWidget | None = None,
) -> DisclosureResult:
    """Einzige Oberflächengrenze vor jedem echten LLM-Modellaufruf.

    Das geskriptete Testbackend hat kein externes Modell. Unbekannte Backends,
    ungültige Ziele, Darstellungsfehler und Speicherfehler bleiben geschlossen.
    """

    try:
        target = (
            backend_or_target
            if isinstance(backend_or_target, AiDisclosureTarget)
            else target_for_backend(backend_or_target)
        )
    except TypeError, ValueError:
        _log.exception("AI disclosure target could not be resolved")
        return DisclosureResult.FAILED
    if target is None or disclosure_is_current(settings, target):
        return DisclosureResult.CURRENT
    dialog: AiDisclosureDialog | None = None
    try:
        dialog = AiDisclosureDialog(target, parent)
        answer = dialog.exec()
        content_was_shown = dialog.content_was_shown
    except Exception:
        _log.exception("AI disclosure could not be displayed")
        return DisclosureResult.FAILED
    finally:
        if dialog is not None:
            dialog.deleteLater()
    if answer != AiDisclosureDialog.DialogCode.Accepted:
        return DisclosureResult.REJECTED
    if not content_was_shown:
        return DisclosureResult.FAILED
    try:
        remember_disclosure(settings, target)
        stored = save_settings(settings)
    except OSError, TypeError, ValueError:
        _log.exception("AI disclosure record could not be stored")
        clear_disclosure(settings)
        return DisclosureResult.FAILED
    if stored is None:
        # ``save_settings`` wirft bei einem Dateifehler nicht mehr, es gibt
        # ``None`` zurück — und der Nachweis blieb im Speicher: Freigabe
        # erteilt, Datei nie geschrieben, beim nächsten Aufruf „aktuell"
        # (Gesamtreview 05.09.2026, UI-05). Geschlossen bleiben heißt: ohne
        # geschriebenen Nachweis keine Freigabe.
        _log.error("AI disclosure record could not be stored: settings file not written")
        clear_disclosure(settings)
        return DisclosureResult.FAILED
    return DisclosureResult.ACCEPTED


def _is_utc_timestamp(value: Any) -> bool:
    if not isinstance(value, str) or not value.endswith("Z") or "T" not in value:
        return False
    try:
        parsed = datetime.fromisoformat(f"{value[:-1]}+00:00")
    except ValueError:
        return False
    return parsed.tzinfo is not None and parsed.utcoffset() == timedelta(0)


class AiDisclosureDialog(QDialog):
    """Gut wahrnehmbarer, reflow-fähiger Hinweis für genau ein Backend."""

    def __init__(self, target: AiDisclosureTarget, parent: QWidget | None = None) -> None:
        if target.backend not in SUPPORTED_AI_BACKENDS:
            raise ValueError(f"unsupported AI disclosure backend: {target.backend}")
        super().__init__(parent)
        self.target = target
        self.backend = target.backend
        self._privacy_text = _local_privacy_text()
        self._content_was_shown = False
        self._reading_position: int | None = None
        self._required_heights: dict[QWidget, int] = {}
        self.setWindowTitle(_title_text())
        self.setAccessibleName(_title_text())
        self.setAccessibleDescription(_general_text())
        self.setModal(True)
        self.setMinimumSize(300, 340)
        self.resize(600, 460)

        self.heading = QLabel(_title_text(), self)
        self.heading.setObjectName("aiDisclosureHeading")
        self.heading.setWordWrap(True)
        self.heading.setAccessibleName(self.heading.text())
        self.heading.setAccessibleDescription(self.heading.text())
        set_level(self.heading, "title")

        self.general_text = _paragraph(_general_text(), self)
        set_level(self.general_text, "body")

        self.provider_card = QFrame(self)
        self.provider_card.setObjectName("aiDisclosureProvider")
        self.provider_card.setFrameShape(QFrame.Shape.StyledPanel)
        provider_layout = QVBoxLayout(self.provider_card)
        provider_layout.setContentsMargins(WIDE, ROOMY, WIDE, ROOMY)
        self.provider_text = _paragraph(_provider_text(target), self.provider_card)
        provider_layout.addWidget(self.provider_text)

        self.local_privacy_link = _notice_link(
            tr("Solidon-Datenschutz lokal öffnen"),
            _LOCAL_PRIVACY_LINK,
            tr("Öffnet die mit Solidon ausgelieferte Datenschutzerklärung ohne Netzverbindung."),
            self.provider_card,
        )
        self.local_privacy_link.activated.connect(self._open_notice_link)
        provider_layout.addWidget(self.local_privacy_link)

        self.external_links: list[_NoticeLink] = []
        self.operator_note: QLabel | None = None
        if target.backend == "anthropic":
            external_description = tr("Beim Öffnen erhält der Anbieter übliche Verbindungsdaten.")
            for text, address in (
                (
                    tr("Anthropic-Datenschutz (öffnet im Browser)"),
                    ANTHROPIC_PRIVACY_URL,
                ),
                (
                    tr("Anthropic-API-Bedingungen (öffnet im Browser)"),
                    ANTHROPIC_COMMERCIAL_TERMS_URL,
                ),
            ):
                link = _notice_link(text, address, external_description, self.provider_card)
                link.activated.connect(self._open_notice_link)
                provider_layout.addWidget(link)
                self.external_links.append(link)
        elif target.target_class == "remote":
            self.operator_note = _paragraph(
                tr("Datenschutz beim Betreiber dieses Ziels klären"), self.provider_card
            )
            provider_layout.addWidget(self.operator_note)
        self.link_widgets: list[QLabel | _NoticeLink] = [
            self.local_privacy_link,
            *self.external_links,
            *([self.operator_note] if self.operator_note is not None else []),
        ]

        self.content = QWidget(self)
        self.content.setMinimumWidth(0)
        self.content.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
        content_layout = QVBoxLayout(self.content)
        content_layout.setSizeConstraint(QVBoxLayout.SizeConstraint.SetMinimumSize)
        content_layout.setContentsMargins(WIDE, WIDE, WIDE, 0)
        content_layout.setSpacing(WIDE)
        content_layout.addWidget(self.heading)
        content_layout.addWidget(self.general_text)
        content_layout.addWidget(self.provider_card)

        self.scroll_area = _DisclosureScrollArea(self)
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area.setAccessibleName(_title_text())
        self.scroll_area.setAccessibleDescription(
            tr("Mit Pfeil- und Bildtasten durch den KI-Hinweis blättern.")
        )
        self.scroll_area.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.scroll_area.setWidget(self.content)
        scroll_bar = self.scroll_area.verticalScrollBar()
        scroll_bar.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        scroll_bar.setAccessibleName(tr("KI-Hinweis lesen"))
        scroll_bar.setAccessibleDescription(
            tr("Mit Pfeil- und Bildtasten durch den KI-Hinweis blättern.")
        )
        scroll_bar.rangeChanged.connect(self._scroll_range_changed)

        self.continue_button = QPushButton(tr("KI-Anfrage fortsetzen"), self)
        self.continue_button.setAccessibleName(self.continue_button.text())
        self.continue_button.setAccessibleDescription(
            tr("Setzt den bereits angeforderten KI-Aufruf fort.")
        )
        self.continue_button.setEnabled(False)
        make_primary(self.continue_button)
        self.back_button = QPushButton(tr("Zurück"), self)
        self.back_button.setAccessibleName(self.back_button.text())
        self.back_button.setAccessibleDescription(
            tr("Kehrt zur Auswahl des Chat-Zugangs zurück und sendet nichts.")
        )

        self.buttons = QDialogButtonBox(self)
        self.buttons.addButton(self.back_button, QDialogButtonBox.ButtonRole.RejectRole)
        self.buttons.addButton(self.continue_button, QDialogButtonBox.ButtonRole.AcceptRole)
        self.back_button.clicked.connect(self.reject)
        self.continue_button.clicked.connect(self.accept)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, ROOMY)
        layout.addWidget(self.scroll_area, 1)
        layout.addWidget(self.buttons)

        previous: QWidget = self.scroll_area
        for link in (self.local_privacy_link, *self.external_links):
            QWidget.setTabOrder(previous, link)
            previous = link
        QWidget.setTabOrder(previous, self.back_button)
        QWidget.setTabOrder(self.back_button, self.continue_button)

    @property
    def content_was_shown(self) -> bool:
        """Nur wahr, wenn alle Pflichtteile erreichbar und zugänglich waren."""

        return self._content_was_shown

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 - Qt gibt den Namen
        super().showEvent(event)
        self._content_was_shown = False
        self.continue_button.setEnabled(False)
        self._reading_position = self.scroll_area.verticalScrollBar().minimum()
        self.scroll_area.setFocus(Qt.FocusReason.TabFocusReason)
        QTimer.singleShot(0, self, self._unlock_after_show)

    def resizeEvent(self, event: QResizeEvent) -> None:  # noqa: N802 - Qt gibt den Namen
        if hasattr(self, "scroll_area"):
            self._reading_position = self.scroll_area.verticalScrollBar().value()
        super().resizeEvent(event)
        if not hasattr(self, "scroll_area"):
            return
        self._content_was_shown = False
        self.continue_button.setEnabled(False)
        QTimer.singleShot(0, self, self._unlock_after_show)

    def _unlock_after_show(self, _value: int | None = None) -> None:
        bar = self.scroll_area.verticalScrollBar()
        reading_position = bar.value() if self._reading_position is None else self._reading_position
        try:
            self._fit_wrapped_paragraphs()
            bar.setValue(max(bar.minimum(), min(reading_position, bar.maximum())))
            ready = self._accessible_content_is_reachable()
        except RuntimeError, ValueError:
            ready = False
        self._reading_position = None
        if not ready:
            self._content_was_shown = False
        try:
            self.continue_button.setEnabled(ready)
        except RuntimeError:
            ready = False
        self._content_was_shown = ready

    def _scroll_range_changed(self, _minimum: int, _maximum: int) -> None:
        self._unlock_after_show()

    def _open_notice_link(self, address: str) -> None:
        """Öffnet nur die drei ausdrücklich erlaubten, bereits sichtbaren Ziele."""

        if address == _LOCAL_PRIVACY_LINK:
            dialog = LocalPrivacyDialog(self._privacy_text, self)
            try:
                dialog.exec()
            finally:
                dialog.deleteLater()
            return
        if address in _ALLOWED_EXTERNAL_LINKS:
            QDesktopServices.openUrl(QUrl(address))

    def _fit_wrapped_paragraphs(self) -> None:
        """Gibt jedem umgebrochenen Text seine echte Höhe für die aktuelle Breite."""

        provider_layout = self.provider_card.layout()
        content_layout = self.content.layout()
        if provider_layout is None or content_layout is None:
            raise RuntimeError("AI disclosure layouts are incomplete")
        outer = content_layout.contentsMargins()
        provider_margins = provider_layout.contentsMargins()
        content_width = max(self.scroll_area.viewport().width(), 1)
        paragraph_width = max(content_width - outer.left() - outer.right(), 1)
        provider_width = max(
            paragraph_width
            - provider_margins.left()
            - provider_margins.right()
            - 2 * self.provider_card.frameWidth(),
            1,
        )
        heights: list[int] = []
        wrapped = (
            (self.heading, paragraph_width),
            (self.general_text, paragraph_width),
            (self.provider_text, provider_width),
            *((label, provider_width) for label in self.link_widgets),
        )
        for label, width in wrapped:
            height = (
                label.fit_text_for_width(width)
                if isinstance(label, _NoticeLink)
                else label.heightForWidth(width)
                if label.hasHeightForWidth()
                else label.sizeHint().height()
            )
            height = max(height, 1)
            label.setFixedHeight(height)
            self._required_heights[label] = height
            heights.append(height)
        provider_layout.invalidate()
        provider_layout.activate()
        provider_height = (
            sum(heights[2:])
            + provider_margins.top()
            + provider_margins.bottom()
            + provider_layout.spacing() * (len(heights) - 3)
            + 2 * self.provider_card.frameWidth()
        )
        self.provider_card.setFixedHeight(provider_height)
        content_layout.invalidate()
        content_layout.activate()
        content_height = (
            outer.top()
            + outer.bottom()
            + heights[0]
            + heights[1]
            + provider_height
            + 2 * content_layout.spacing()
        )
        self.content.setMinimumHeight(content_height)
        self.content.updateGeometry()

    def _accessible_content_is_reachable(self) -> bool:
        """Prüft die reale Layout- und Scrollgeometrie, nicht nur Textfelder."""

        layout = self.layout()
        content_layout = self.content.layout()
        provider_layout = self.provider_card.layout()
        if layout is None or content_layout is None or provider_layout is None:
            return False
        layout.activate()
        content_layout.activate()
        provider_layout.activate()
        expected = _provider_text(self.target)
        required_labels = (
            self.heading,
            self.general_text,
            self.provider_text,
            *self.link_widgets,
        )
        required_accessible_widgets = (
            self,
            self.scroll_area,
            *required_labels,
            self.back_button,
            self.continue_button,
        )
        content_rect = self.content.rect()
        viewport = self.scroll_area.viewport()
        bar = self.scroll_area.verticalScrollBar()
        button_rect = self.buttons.geometry()
        labels_fit_horizontally = True
        labels_have_full_height = True
        for label in required_labels:
            top_left = label.mapTo(self.content, label.rect().topLeft())
            bottom_right = label.mapTo(self.content, label.rect().bottomRight())
            labels_fit_horizontally &= (
                top_left.x() >= content_rect.left() and bottom_right.x() <= content_rect.right()
            )
            required_height = self._required_heights.get(label, 0)
            labels_have_full_height &= required_height > 0 and label.height() + 1 >= required_height
        scroll_reaches_bottom = self.provider_card.geometry().bottom() <= (
            viewport.height() + bar.maximum() + WIDE
        )
        buttons_inside = self.rect().contains(button_rect.topLeft()) and self.rect().contains(
            button_rect.bottomRight()
        )
        accessible_interfaces = [
            QAccessible.queryAccessibleInterface(widget) for widget in required_accessible_widgets
        ]
        accessible_content_complete = all(
            interface is not None
            and bool(interface.text(QAccessible.Text.Name).strip())
            and bool(interface.text(QAccessible.Text.Description).strip())
            for interface in accessible_interfaces
        )
        actionable_links_complete = all(
            (interface := QAccessible.queryAccessibleInterface(link)) is not None
            and interface.role() == QAccessible.Role.Button
            and interface.actionInterface() is not None
            and QAccessibleActionInterface.pressAction()
            in interface.actionInterface().actionNames()
            for link in (self.local_privacy_link, *self.external_links)
        )
        return bool(
            self.isVisible()
            and self.windowTitle() == _title_text()
            and self.provider_text.text() == expected
            and viewport.width() > 0
            and viewport.height() > 0
            and content_rect.width() <= viewport.width() + 1
            and self.scroll_area.horizontalScrollBar().maximum() == 0
            and labels_fit_horizontally
            and labels_have_full_height
            and scroll_reaches_bottom
            and buttons_inside
            and self.buttons.isVisibleTo(self)
            and self.continue_button.focusPolicy() != Qt.FocusPolicy.NoFocus
            and self.back_button.focusPolicy() != Qt.FocusPolicy.NoFocus
            and accessible_content_complete
            and actionable_links_complete
            and all(
                label.isVisibleTo(self)
                and bool(label.text().strip())
                and bool(label.accessibleName().strip())
                and bool(label.accessibleDescription().strip())
                for label in required_labels
            )
        )


def _paragraph(text: str, parent: QWidget) -> QLabel:
    label = QLabel(text, parent)
    label.setWordWrap(True)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setAccessibleName(text)
    label.setAccessibleDescription(text)
    label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
    return label


class _DisclosureScrollArea(QScrollArea):
    """Scrollfläche, deren angekündigte Tastaturwege wirklich blättern."""

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 - Qt gibt den Namen
        bar = self.verticalScrollBar()
        key = event.key()
        if key == Qt.Key.Key_Home:
            bar.setValue(bar.minimum())
        elif key == Qt.Key.Key_End:
            bar.setValue(bar.maximum())
        elif key == Qt.Key.Key_PageUp:
            bar.setValue(bar.value() - bar.pageStep())
        elif key == Qt.Key.Key_PageDown:
            bar.setValue(bar.value() + bar.pageStep())
        elif key == Qt.Key.Key_Up:
            bar.setValue(bar.value() - bar.singleStep())
        elif key == Qt.Key.Key_Down:
            bar.setValue(bar.value() + bar.singleStep())
        else:
            super().keyPressEvent(event)
            return
        event.accept()


class _NoticeLink(QCommandLinkButton):
    """Ein umbruchfähiger, semantisch auslösbarer Datenschutzweg."""

    activated = Signal(str)

    def __init__(self, text: str, address: str, description: str, parent: QWidget) -> None:
        super().__init__("", "", parent)
        self._title_text = text
        self._description_text = description
        self.address = address

        self.title_label = QLabel(text, self)
        self.title_label.setWordWrap(True)
        self.title_label.setTextFormat(Qt.TextFormat.PlainText)
        title_font = self.title_label.font()
        title_font.setWeight(QFont.Weight.DemiBold)
        self.title_label.setFont(title_font)

        self.description_label = QLabel(description, self)
        self.description_label.setWordWrap(True)
        self.description_label.setTextFormat(Qt.TextFormat.PlainText)
        for label in (self.title_label, self.description_label):
            label.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
            label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)

        text_layout = QVBoxLayout()
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(TIGHT)
        text_layout.addWidget(self.title_label)
        text_layout.addWidget(self.description_label)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(WIDE * 3, ROOMY, ROOMY, ROOMY)
        layout.addLayout(text_layout)
        self.clicked.connect(self._activate)

    def text(self) -> str:
        """Der sichtbare Titel, obwohl Qt intern nur den Pfeil zeichnet."""

        return self._title_text

    def description(self) -> str:
        """Die sichtbare Beschreibung für Prüfung und Zugänglichkeit."""

        return self._description_text

    def hasHeightForWidth(self) -> bool:  # noqa: N802 - Qt gibt den Namen
        return True

    def heightForWidth(self, width: int) -> int:  # noqa: N802 - Qt gibt den Namen
        """Rechnet beide umgebrochenen Zeilen samt echter Innenkante."""

        layout = self.layout()
        if layout is None:
            return super().heightForWidth(width)
        margins = layout.contentsMargins()
        title_height, description_height = self._line_heights(width)
        return margins.top() + title_height + TIGHT + description_height + margins.bottom()

    def fit_text_for_width(self, width: int) -> int:
        """Gibt beiden Zeilen ihre Umbruchhöhe, bevor Qt sie verteilt."""

        title_height, description_height = self._line_heights(width)
        self.title_label.setFixedHeight(title_height)
        self.description_label.setFixedHeight(description_height)
        layout = self.layout()
        if layout is not None:
            layout.invalidate()
            layout.activate()
        return self.heightForWidth(width)

    def _line_heights(self, width: int) -> tuple[int, int]:
        layout = self.layout()
        if layout is None:
            return 1, 1
        margins = layout.contentsMargins()
        content_width = max(width - margins.left() - margins.right(), 1)
        return (
            max(self.title_label.heightForWidth(content_width), 1),
            max(self.description_label.heightForWidth(content_width), 1),
        )

    def _activate(self) -> None:
        self.activated.emit(self.address)


def _notice_link(text: str, address: str, description: str, parent: QWidget) -> _NoticeLink:
    """Ein zugänglicher Link, der erst auf einen ausdrücklichen Klick reagiert."""

    label = _NoticeLink(text, address, description, parent)
    label.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
    label.setAccessibleName(text)
    label.setAccessibleDescription(description)
    label.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Minimum)
    return label


def _local_privacy_text() -> str:
    """Liest die mit der Anwendung ausgelieferte lokale Datenschutzerklärung."""

    return (Path(__file__).resolve().parents[2] / "DATENSCHUTZ.md").read_text(encoding="utf-8")


class LocalPrivacyDialog(QDialog):
    """Reiner lokaler Leser ohne Webansicht, Remote-Ressourcen oder Linköffnung."""

    def __init__(self, markdown: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Solidon-Datenschutz"))
        self.resize(720, 620)

        note = QLabel(
            tr(
                "Diese lokale Fassung wird mit Solidon ausgeliefert. Externe Links sind "
                "hier deaktiviert."
            ),
            self,
        )
        note.setWordWrap(True)
        note.setAccessibleName(note.text())
        note.setAccessibleDescription(note.text())

        self.text = QTextBrowser(self)
        self.text.setMarkdown(markdown)
        self.text.setOpenLinks(False)
        self.text.setOpenExternalLinks(False)
        self.text.setAccessibleName(tr("Solidon-Datenschutz"))
        self.text.setAccessibleDescription(note.text())

        close = QPushButton(tr("Schließen"), self)
        close.clicked.connect(self.accept)
        close.setAccessibleName(close.text())

        buttons = QDialogButtonBox(self)
        buttons.addButton(close, QDialogButtonBox.ButtonRole.AcceptRole)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(WIDE, WIDE, WIDE, ROOMY)
        layout.addWidget(note)
        layout.addWidget(self.text, 1)
        layout.addWidget(buttons)
