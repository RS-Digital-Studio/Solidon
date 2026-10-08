"""Ein Reiter, der Fehler und Warnungen zählt und auf neue aufmerksam macht.

Robert, 05.10.2026: Warnungen und Fehler holen den Prüfbericht nicht mehr nach
vorn — sie würden dem Kunden die Felder der Auswahl wegnehmen, die seit RM-511
in derselben Karte stehen. Stattdessen trägt sein Reiter einen Zähler je
Schwere und blinkt bei einer neuen Meldung sanft: gelb bei einer Warnung, rot
bei einem Fehler. Wer im Bericht war, hat sie gesehen; das Blinken ist dann
vorbei.

**Die Zahl ist die Aussage, die Farbe zeigt nur, dass sie neu ist** (Regel
18): Jede Marke trägt das Zeichen ihrer Schwere neben der Zahl, und der Reiter
nennt beides im Tooltip und für den Bildschirmleser. **Dass etwas ungesehen
ist, sagt nicht die Tönung allein** (Durchsicht 0.5.3, Fund 4): Ihr Kontrast
zur Karte lag bei 1,2 bis 1,7 : 1, nach dem Blinken war „neu“ nur noch eine
Farbe. Ein Punkt in der Schriftfarbe vor dem Namen und das Wort „ungelesen“
in Tooltip und zugänglichem Namen stehen dazu, bis der Reiter vorn war.
"""

from __future__ import annotations

import math
from typing import Final

from PySide6.QtCore import QAbstractAnimation, QPointF, QRectF, Qt, QVariantAnimation
from PySide6.QtGui import QColor, QPainter, QPaintEvent, QPalette, QPen
from PySide6.QtWidgets import QHBoxLayout, QLabel, QTabBar, QWidget

from app.i18n import tr
from app.ui.motion import animations_enabled
from app.ui.palette import ROLES, SEVERITY_ENCODING, readable_on
from app.ui.style import SPACE, TIGHT

#: Ein Atemzug des Reiters: von still zur vollen Tönung und zurück.
CYCLE_MS: Final = 1200

#: Wie oft er atmet. Zusammen 4,8 s und damit unter den fünf Sekunden, ab
#: denen WCAG 2.2.2 für Blinken einen Weg zum Anhalten verlangt. Danach bleibt
#: der Reiter getönt, bis er vorn stand — gesehen ist die Meldung erst dann.
CYCLES: Final = 4

#: Wie deckend die Tönung hinter der Beschriftung höchstens liegt, und wie
#: deckend sie nach dem Blinken stehen bleibt.
TINT_MAX: Final = 0.45
TINT_REST: Final = 0.3

#: Der Punkt vor dem Namen eines Reiters mit ungesehenen Meldungen — Halbmesser
#: in Logikpunkten. Er sitzt im linken Polster des Reiters (``ROOMY``).
UNSEEN_DOT: Final = 3.0


def count_phrases(errors: int, warnings: int, infos: int = 0) -> list[str]:
    """„2 Warnungen“, „1 Hinweis“ — je Schwere ein Wort mit Zahl, keine für null.

    Eine Quelle für Reiter und Kopf des Prüfberichts (RM-508): „0 x Fehler“
    stand dort über jedem sauberen Modell.
    """
    parts = []
    if errors:
        parts.append(tr("1 Fehler") if errors == 1 else tr("{count} Fehler", count=errors))
    if warnings:
        parts.append(tr("1 Warnung") if warnings == 1 else tr("{count} Warnungen", count=warnings))
    if infos:
        parts.append(tr("1 Hinweis") if infos == 1 else tr("{count} Hinweise", count=infos))
    return parts


def counted(errors: int, warnings: int) -> str:
    """„2 Fehler, 1 Warnung“ — für Tooltip und Bildschirmleser."""
    return ", ".join(count_phrases(errors, warnings))


class AlertBadge(QWidget):
    """Zwei Marken am Reiter: Fehler und Warnungen, je mit Zeichen und Zahl.

    Eine Marke für null gibt es nicht — ein Zähler, der immer dasteht, wird
    Tapete. Klicks gehen durch auf den Reiter, zu dem die Marken gehören.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("alertBadge")
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, 0, 0, 0)
        row.setSpacing(TIGHT)
        self.errors = self._mark("error")
        self.warnings = self._mark("warning")
        row.addWidget(self.errors)
        row.addWidget(self.warnings)

    def _mark(self, severity: str) -> QLabel:
        mark = QLabel(self)
        colour = ROLES["error" if severity == "error" else "warning"]
        mark.setStyleSheet(
            f"QLabel {{ background: {colour}; color: {readable_on(colour)};"
            f" border-radius: {SPACE + 2}px; padding: 0px {SPACE + 1}px; font-weight: 600; }}"
        )
        mark.setVisible(False)
        return mark

    def show_counts(self, errors: int, warnings: int) -> None:
        """Die Zahlen; eine Marke ohne Zahl verschwindet."""
        for mark, severity, count in (
            (self.errors, "error", errors),
            (self.warnings, "warning", warnings),
        ):
            mark.setText(f"{SEVERITY_ENCODING[severity].symbol} {count}")
            mark.setVisible(count > 0)
        self.adjustSize()


class SignalTabBar(QTabBar):
    """Die Reiterleiste der rechten Karte: Zähler am Prüfbericht, sanftes Blinken.

    Gemalt wird eine Tönung **hinter** der Beschriftung, nicht die Schrift:
    Das Stilblatt setzt jedem Reiter seine Schriftfarbe (``QTabBar::tab
    { color }``), und ``setTabTextColor`` kommt dagegen nicht an. Die stillen
    Reiter haben eine durchsichtige Fläche, also liegt die Tönung darunter,
    und die Schrift behält ihren Kontrast.
    """

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._signalled = -1
        self._colour: QColor | None = None
        self._strength = 0.0
        self._pulse: QVariantAnimation | None = None
        self._badges: dict[int, AlertBadge] = {}
        self._words: dict[int, str] = {}
        """Die Zahlen je Reiter in Worten — für Tooltip und zugänglichen Namen."""
        self._pointed = -1
        """Der Reiter, auf den die Tour gerade zeigt, oder -1 (RM-573)."""
        self.currentChanged.connect(self._seen)

    # --- Zähler --------------------------------------------------------------

    def show_counts(self, index: int, errors: int, warnings: int) -> None:
        """Setzt die Marken am Reiter ``index`` und sagt die Zahlen in Worten.

        **Bei jeder Änderung neu eingehängt**, und ohne Zahl gar nicht: Die
        Leiste misst ihre Reiter nur, wenn ein Knopf gesetzt wird, und zeigt
        ihn dabei selbst. Eine Marke, die erst später sichtbar wurde, stand
        sonst unsichtbar in einem Reiter ohne Platz für sie (gemessen am
        echten Fenster). Derselbe Knopf ein zweites Mal gesetzt verbärge ihn
        dagegen: Qt zeigt den neuen und verbirgt danach den alten.
        """
        badge = self._badges.get(index)
        if badge is None:
            badge = AlertBadge(self)
            self._badges[index] = badge
        badge.show_counts(errors, warnings)
        side = QTabBar.ButtonPosition.RightSide
        self.setTabButton(index, side, None)
        if errors or warnings:
            self.setTabButton(index, side, badge)
        self._words[index] = counted(errors, warnings)
        self._describe(index)

    def badge(self, index: int) -> AlertBadge | None:
        """Die Marken am Reiter ``index`` — für Prüfungen."""
        return self._badges.get(index)

    def unseen(self, index: int) -> bool:
        """Ob der Reiter ``index`` gerade ungesehene Meldungen ankündigt."""
        return index == self._signalled and self._colour is not None

    def _describe(self, index: int) -> None:
        """Tooltip und zugänglicher Name: die Zahlen, und „ungelesen“, solange ungesehen.

        Der Punkt vor dem Namen (:meth:`paintEvent`) sagt es dem Auge, diese
        Sätze sagen es der Maus und dem Bildschirmleser — die Tönung allein
        wäre eine Aussage nur über Farbe (Regel 18).
        """
        if not 0 <= index < self.count():
            return
        words = self._words.get(index, "")
        name = self.tabText(index)
        if index == self._pointed:
            # Die Tour zeigt hierher: in Worten für Maus und Bildschirmleser,
            # der gestrichelte Rahmen sagt es dem Auge (Regel 18).
            pointed = tr("Die Tour zeigt hierher. Ein Klick öffnet den Reiter.")
            self.setTabToolTip(index, f"{words}\n{pointed}" if words else pointed)
            self.setAccessibleTabName(index, tr("{tab}, die Tour zeigt hierher", tab=name))
            return
        if not words:
            self.setTabToolTip(index, "")
            self.setAccessibleTabName(index, name)
            return
        if self.unseen(index):
            self.setTabToolTip(index, tr("{counts}, ungelesen", counts=words))
            self.setAccessibleTabName(
                index, tr("{tab}, {counts}, ungelesen", tab=name, counts=words)
            )
            return
        self.setTabToolTip(index, words)
        self.setAccessibleTabName(index, tr("{tab}, {counts}", tab=name, counts=words))

    # --- Blinken ---------------------------------------------------------------

    def signal(self, index: int, *, error: bool, warning: bool, fresh: bool = True) -> None:
        """Der Reiter ``index`` macht auf ungesehene Meldungen aufmerksam.

        ``error`` und ``warning`` sagen, was ungesehen ansteht: rot, sobald ein
        Fehler dabei ist, sonst gelb. ``fresh`` heißt, dass eben etwas
        dazugekommen ist — nur dann blinkt er von vorn; sonst nimmt er nur die
        Farbe an, die jetzt gilt. Steht er vorn, ist alles gesehen.
        """
        if not (error or warning) or index == self.currentIndex():
            self.calm()
            return
        if not 0 <= index < self.count():
            return
        colour = QColor(ROLES["error"] if error else ROLES["warning"])
        if not fresh and index == self._signalled:
            self._colour = colour
            self.update()
            return
        self._stop()
        before = self._signalled
        self._signalled = index
        self._colour = colour
        self._describe(index)
        if before not in (-1, index):
            self._describe(before)
        if not animations_enabled():
            self._settle()
            return
        animation = QVariantAnimation(self)
        animation.setDuration(CYCLE_MS)
        animation.setLoopCount(CYCLES)
        animation.setStartValue(0.0)
        animation.setEndValue(1.0)
        animation.valueChanged.connect(self._breathe)
        animation.finished.connect(self._settle)
        self._pulse = animation
        # Gelöscht, sobald sie steht: Ohne die Regel blieb jede beendete
        # Animation als Kind der Leiste liegen, eine je neuer Meldung
        # (Durchsicht 0.5.3; ``CLAUDE.md``: Bewegung endet mit DeleteWhenStopped).
        animation.start(QAbstractAnimation.DeletionPolicy.DeleteWhenStopped)

    def calm(self) -> None:
        """Kein Reiter macht mehr auf etwas aufmerksam."""
        self._stop()
        before = self._signalled
        self._signalled = -1
        self._colour = None
        self._strength = 0.0
        if before >= 0:
            self._describe(before)
        self.update()

    def signalled(self) -> int:
        """Welcher Reiter gerade aufmerksam macht, oder -1."""
        return self._signalled

    def tint(self) -> QColor | None:
        """Die Tönung, die gerade hinter dem Reiter liegt — für Prüfungen."""
        if self._signalled < 0 or self._colour is None:
            return None
        colour = QColor(self._colour)
        colour.setAlphaF(self._strength)
        return colour

    def _breathe(self, value: float) -> None:
        # Eine Kosinuswelle: still am Anfang und Ende jedes Atemzugs, keine Kante.
        self._strength = TINT_MAX * (1.0 - math.cos(2.0 * math.pi * float(value))) / 2.0
        self.update()

    def _settle(self) -> None:
        """Nach dem Blinken bleibt die Farbe als ruhige Tönung, bis der Reiter vorn war."""
        self._pulse = None
        self._strength = TINT_REST
        self.update()

    def _stop(self) -> None:
        # Angehalten löscht sie sich selbst (``DeleteWhenStopped``).
        if self._pulse is not None:
            pulse, self._pulse = self._pulse, None
            pulse.stop()

    def _seen(self, index: int) -> None:
        if index == self._signalled:
            self.calm()
        if index == self._pointed:
            self.stop_pointing()

    # --- Hinweis der Tour (RM-573) ---------------------------------------------

    def point_at(self, index: int) -> None:
        """Die Tour zeigt auf den Reiter ``index``, ohne ihn nach vorn zu holen.

        Holte sie ihn nach vorn, verdeckte er die Tour, die sich die Karte mit
        ihm teilt. Ein gestrichelter Rahmen um den Reiter und ein Satz in
        Tooltip und Namen bleiben, bis der Kunde ihn selbst öffnet oder die
        Tour weiterzieht.
        """
        if not 0 <= index < self.count() or index == self.currentIndex():
            self.stop_pointing()
            return
        before, self._pointed = self._pointed, index
        if before not in (-1, index):
            self._describe(before)
        self._describe(index)
        self.update()

    def stop_pointing(self) -> None:
        """Kein Reiter trägt mehr den Hinweis der Tour."""
        before, self._pointed = self._pointed, -1
        if before >= 0:
            self._describe(before)
            self.update()

    def pointed(self) -> int:
        """Auf welchen Reiter die Tour zeigt, oder -1 — für Prüfungen."""
        return self._pointed

    def pointed_frame(self) -> QRectF | None:
        """Wo der Rahmen um den gezeigten Reiter steht — ``None`` ohne. Für Prüfungen."""
        index = self._pointed
        if not 0 <= index < self.count() or not self.isTabVisible(index):
            return None
        return QRectF(self.tabRect(index)).adjusted(1.0, 1.0, -1.0, -1.0)

    # --- Verwaltung ------------------------------------------------------------

    def tabInserted(self, index: int) -> None:  # noqa: N802 - Qt-Name
        super().tabInserted(index)
        if 0 <= index <= self._signalled:
            self._signalled += 1
        if 0 <= index <= self._pointed:
            self._pointed += 1
        self._badges = {
            (spot + 1 if spot >= index else spot): badge for spot, badge in self._badges.items()
        }
        self._words = {
            (spot + 1 if spot >= index else spot): words for spot, words in self._words.items()
        }

    def tabRemoved(self, index: int) -> None:  # noqa: N802 - Qt-Name
        super().tabRemoved(index)
        if index == self._signalled:
            self.calm()
        elif index < self._signalled:
            self._signalled -= 1
        if index == self._pointed:
            self._pointed = -1
        elif index < self._pointed:
            self._pointed -= 1
        self._badges = {
            (spot - 1 if spot > index else spot): badge
            for spot, badge in self._badges.items()
            if spot != index
        }
        self._words = {
            (spot - 1 if spot > index else spot): words
            for spot, words in self._words.items()
            if spot != index
        }

    def unseen_mark(self) -> QRectF | None:
        """Wo der Punkt für Ungesehenes steht — ``None`` ohne. Für Prüfungen."""
        index = self._signalled
        if not self.unseen(index) or not self.isTabVisible(index):
            return None
        tab = QRectF(self.tabRect(index))
        centre = QPointF(tab.left() + UNSEEN_DOT + SPACE, tab.center().y())
        return QRectF(
            centre.x() - UNSEEN_DOT, centre.y() - UNSEEN_DOT, 2 * UNSEEN_DOT, 2 * UNSEEN_DOT
        )

    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: N802 - Qt-Name
        tint = self.tint()
        if tint is not None and tint.alphaF() > 0.0 and self.isTabVisible(self._signalled):
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(tint)
            area = QRectF(self.tabRect(self._signalled)).adjusted(1.0, 1.0, -1.0, 0.0)
            painter.drawRoundedRect(area, SPACE, SPACE)
            painter.end()
        super().paintEvent(event)
        # **Der Punkt ist die zweite Kodierung für „ungesehen“** (Regel 18):
        # eine Form in der Schriftfarbe, über die ganze Zeit, nicht nur während
        # des Blinkens — die ruhende Tönung hatte gegen die Karte 1,2 bis 1,7 : 1.
        mark = self.unseen_mark()
        if mark is not None:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self.palette().color(QPalette.ColorRole.WindowText))
            painter.drawEllipse(mark)
            painter.end()
        # **Der Hinweis der Tour ist eine Form, nicht nur eine Farbe** (Regel 18):
        # ein gestrichelter Rahmen in der Schriftfarbe um den ganzen Reiter.
        frame = self.pointed_frame()
        if frame is not None:
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            pen = QPen(self.palette().color(QPalette.ColorRole.WindowText))
            pen.setWidthF(2.0)
            pen.setStyle(Qt.PenStyle.DashLine)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(frame, SPACE, SPACE)
            painter.end()


__all__ = ["CYCLES", "CYCLE_MS", "AlertBadge", "SignalTabBar", "counted"]
