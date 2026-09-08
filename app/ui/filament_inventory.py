"""Das lokale Filamentlager: Spulen, Bestand und Rücknahme ohne 3D-Renderer."""

from __future__ import annotations

from collections.abc import Callable
from functools import partial
from typing import Any

from PySide6.QtCore import QEvent, QRectF, QSignalBlocker, QSize, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFontMetrics, QKeyEvent, QPainter, QPen
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGridLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from app.core.errors import AppError, ValidationError
from app.core.knowledge import filaments
from app.i18n import tr
from app.ui.filament_picker import (
    NewFilamentDialog,
    configured_spools,
    spool_label,
    stock_label,
    swatch,
)
from app.ui.labels import NumberSpin, local_timestamp, localised
from app.ui.leash import WAIT_TIMEOUT_MS, Worker, WorkerLeash, stop_watching_the_dying
from app.ui.panels import collapsible
from app.ui.style import NORMAL, WIDE, make_primary, set_level


class _InventoryWork(Worker):
    """Dateizugriff und Slicer-Suche blockieren das Regal nicht."""

    completed = Signal(object)
    rejected = Signal(object)

    def __init__(self, action: Callable[[], object]) -> None:
        super().__init__()
        self._action: Callable[[], object] | None = action

    def work(self) -> None:
        assert self._action is not None
        try:
            result = self._action()
        except AppError as problem:
            self.rejected.emit(problem)
            return
        self.completed.emit(result)

    def release_finished_references(self) -> None:
        self._action = None
        super().release_finished_references()


def paint_spool(
    painter: QPainter,
    rect: QRectF,
    entry: filaments.CatalogueFilament,
    foreground: QColor,
    background: QColor,
) -> None:
    """Der Wickelradius zeigt den Bestand; unbekannt trägt eine Schraffur."""
    painter.save()
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    side = min(rect.width(), rect.height()) * 0.9
    centre = rect.center()
    radius = side / 2
    painter.setPen(QPen(foreground, 2))
    painter.setBrush(background)
    painter.drawEllipse(centre, radius, radius)
    remaining, nominal = entry.remaining_grams, entry.spool_grams
    known = remaining is not None and (remaining <= 0 or (nominal is not None and nominal > 0))
    ratio = (
        (min(1.0, remaining / nominal) if nominal and remaining is not None else 0.0)
        if known
        else 0.7
    )
    coil = radius * (0.3 + 0.56 * ratio**0.5)
    colour = QColor(entry.colour)
    painter.setBrush(colour)
    painter.setPen(QPen(foreground, 1))
    painter.drawEllipse(centre, coil, coil)
    if not known:
        painter.setBrush(Qt.BrushStyle.BDiagPattern)
        painter.drawEllipse(centre, coil, coil)
    else:
        painter.setBrush(Qt.BrushStyle.NoBrush)
        ring = radius * 0.34
        while ring < coil:
            painter.drawEllipse(centre, ring, ring)
            ring += max(3, radius * 0.06)
    painter.setBrush(background)
    painter.setPen(QPen(foreground, 2))
    painter.drawEllipse(centre, radius * 0.26, radius * 0.26)
    painter.drawEllipse(centre, radius * 0.12, radius * 0.12)
    painter.restore()


class SpoolCard(QPushButton):
    """Eine tastaturbedienbare Spule mit Zeichnung und lesbaren Angaben."""

    def __init__(
        self,
        entry: filaments.CatalogueFilament,
        parent: QWidget | None = None,
        low_stock_percent: float = 10,
    ) -> None:
        super().__init__(parent)
        self.entry = entry
        self.low_stock_percent = low_stock_percent
        self.setCheckable(True)
        self.setAutoDefault(False)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setAccessibleName(spool_label(entry))
        if self._low_stock():
            self.setAccessibleName(f"{spool_label(entry)} · {tr('Wenig Filament')}")
        self.setToolTip(spool_label(entry))
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setMinimumWidth(160)
        self.setMinimumHeight(self.sizeHint().height())

    def event(self, event: QEvent) -> bool:
        """Nach dem Polieren bleibt die Mindesthöhe am gesamten eigenen Karteninhalt."""
        result = super().event(event)
        if event.type() in (QEvent.Type.Polish, QEvent.Type.StyleChange, QEvent.Type.FontChange):
            self.setMinimumHeight(self.sizeHint().height())
        return result

    def sizeHint(self) -> QSize:  # noqa: N802 — Qt-Name
        font = self.font()
        font.setBold(True)
        return QSize(220, max(260, 128 + (QFontMetrics(font).height() + 3) * 6 + 12))

    def minimumSizeHint(self) -> QSize:  # noqa: N802 — Qt-Name
        """Das globale Knopf-Stylesheet darf die Spulenbeschriftung nicht abschneiden."""
        return QSize(160, self.sizeHint().height())

    def _low_stock(self) -> bool:
        remaining, nominal = self.entry.remaining_grams, self.entry.spool_grams
        return remaining is not None and (
            remaining <= 0
            or (nominal is not None and remaining / nominal * 100 <= self.low_stock_percent)
        )

    def paintEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Name
        super().paintEvent(event)
        painter = QPainter(self)
        foreground = self.palette().buttonText().color()
        paint_spool(
            painter,
            QRectF(12, 12, self.width() - 24, 108),
            self.entry,
            foreground,
            self.palette().button().color(),
        )
        painter.setPen(foreground)
        font = self.font()
        font.setBold(True)
        painter.setFont(font)
        y = 128
        height = painter.fontMetrics().height()
        for text in (
            self.entry.name,
            self.entry.material_type or tr("Unbekannt"),
            stock_label(self.entry),
            self.entry.location or tr("Ohne Lagerort"),
            self.entry.identifier[:8],
        ):
            painter.drawText(
                QRectF(12, y, self.width() - 24, height + 3),
                Qt.AlignmentFlag.AlignHCenter,
                painter.fontMetrics().elidedText(
                    text, Qt.TextElideMode.ElideRight, self.width() - 24
                ),
            )
            y += height + 3
            font.setBold(False)
            painter.setFont(font)
        if self._low_stock():
            font.setBold(True)
            painter.setFont(font)
            painter.drawText(
                QRectF(12, y, self.width() - 24, height + 3),
                Qt.AlignmentFlag.AlignHCenter,
                tr("Wenig Filament"),
            )
        if self.hasFocus() or self.isChecked():
            painter.setPen(QPen(foreground, 2, Qt.PenStyle.DashLine))
            painter.setBrush(Qt.BrushStyle.NoBrush)
            painter.drawRoundedRect(QRectF(self.rect()).adjusted(4, 4, -4, -4), 8, 8)
        painter.end()

    def keyPressEvent(self, event: QKeyEvent) -> None:  # noqa: N802 — Qt-Name
        if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            self.click()
            event.accept()
        else:
            super().keyPressEvent(event)


class SlicerSpoolDialog(QDialog):
    """Die im Slicer eingerichteten Spulen werden einzeln bewusst übernommen."""

    def __init__(
        self, entries: tuple[filaments.CatalogueFilament, ...], parent: QWidget | None = None
    ) -> None:
        super().__init__(parent)
        self._entries = entries
        self.setWindowTitle(tr("Spulen aus dem Slicer übernehmen"))
        self.resize(560, 420)
        layout = QVBoxLayout(self)
        hint = QLabel(
            tr("Markieren Sie nur Spulen, die Sie besitzen. Die Restmenge bleibt unbekannt."), self
        )
        hint.setWordWrap(True)
        layout.addWidget(hint)
        self.list = QListWidget(self)
        self.list.setAccessibleName(tr("Im Slicer eingerichtete Filamente"))
        for index, entry in enumerate(entries):
            item = QListWidgetItem(swatch(entry.colour), spool_label(entry), self.list)
            item.setData(Qt.ItemDataRole.UserRole, index)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Unchecked)
        layout.addWidget(self.list)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, parent=self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self._ok_button = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self._ok_button.setText(tr("Markierte Spulen übernehmen"))
        make_primary(self._ok_button)
        self._ok_button.setEnabled(False)
        self.list.itemChanged.connect(self._selection_changed)
        layout.addWidget(buttons)

    def _selection_changed(self, _item: QListWidgetItem) -> None:
        self._ok_button.setEnabled(bool(self.chosen_spools()))

    def chosen_spools(self) -> list[filaments.CatalogueFilament]:
        """Die ausdrückliche Besitzwahl; keine Markierung wird vorausgesetzt."""
        return [
            self._entries[row]
            for row in range(self.list.count())
            if self.list.item(row).checkState() == Qt.CheckState.Checked
        ]


class InventoryView(QWidget):
    """Regal und Spulendetail lesen denselben Datensatz über seine Kennung."""

    backRequested = Signal()
    catalogueChanged = Signal()
    bookingModeChanged = Signal(str)
    lowStockThresholdChanged = Signal(float)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._entries: tuple[filaments.CatalogueFilament, ...] = ()
        self._selected_id = ""
        self._columns = 0
        self._low_stock_percent = 10.0
        self._worker: _InventoryWork | None = None
        self._leash = WorkerLeash(self)
        self._callback: Callable[[object], None] | None = None
        self._wait_cursor = QTimer(self)
        self._wait_cursor.setSingleShot(True)
        self._wait_cursor.timeout.connect(self._show_wait_cursor)
        self._wait_progress = QTimer(self)
        self._wait_progress.setSingleShot(True)
        self._wait_progress.timeout.connect(self._show_wait_progress)
        self.cards: list[SpoolCard] = []
        outer = QVBoxLayout(self)
        outer.setContentsMargins(WIDE, NORMAL, WIDE, NORMAL)
        self.back_button = QPushButton(tr("Zurück"), self)
        self.back_button.clicked.connect(self.backRequested)
        outer.addWidget(self.back_button, alignment=Qt.AlignmentFlag.AlignLeft)
        title = QLabel(tr("Filamentlager"), self)
        set_level(title, "title")
        outer.addWidget(title)
        self.summary = QLabel(self)
        self.summary.setWordWrap(True)
        outer.addWidget(self.summary)
        self.pages = QStackedWidget(self)
        outer.addWidget(self.pages, 1)
        shelf = QWidget(self)
        layout = QVBoxLayout(shelf)
        layout.setContentsMargins(0, 0, 0, 0)
        self.search = QLineEdit(shelf)
        self.search.setPlaceholderText(tr("Spulen nach Name, Typ oder Lagerort suchen"))
        self.search.setAccessibleName(tr("Spulen suchen"))
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self._refill)
        layout.addWidget(self.search)
        self.grouping = QComboBox(shelf)
        self.grouping.addItem(tr("Nach Material gruppieren"), userData="material_type")
        self.grouping.addItem(tr("Nach Lagerort gruppieren"), userData="location")
        self.grouping.setAccessibleName(tr("Spulen gruppieren"))
        self.grouping.currentIndexChanged.connect(self._refill)
        layout.addWidget(self.grouping)
        self.archived = QCheckBox(tr("Archivierte Spulen anzeigen"), shelf)
        self.archived.toggled.connect(self.refresh)
        layout.addWidget(self.archived)
        settings_area = QWidget(shelf)
        settings_layout = QVBoxLayout(settings_area)
        self.booking_mode = QComboBox(settings_area)
        self.booking_mode.setAccessibleName(tr("Bestand nach der Ausgabe buchen"))
        self.booking_mode.addItem(tr("Nachfragen"), userData="ask")
        self.booking_mode.addItem(tr("Nie buchen"), userData="never")
        self.booking_mode.addItem(tr("Ohne Rückfrage buchen"), userData="auto")
        self.booking_mode.setToolTip(
            tr(
                "Automatisch nur bei eindeutiger Spule, bekanntem ausreichendem Bestand "
                "und belegtem Verbrauch."
            )
        )
        self.booking_mode.currentIndexChanged.connect(self._booking_mode_changed)
        settings_layout.addWidget(self.booking_mode)
        self.low_stock_threshold = NumberSpin(shelf)
        self.low_stock_threshold.setRange(0, 100)
        self.low_stock_threshold.setDecimals(0)
        self.low_stock_threshold.setSuffix(f" {tr('%')}")
        self.low_stock_threshold.setValue(self._low_stock_percent)
        self.low_stock_threshold.setAccessibleName(tr("Warnschwelle für niedrigen Bestand"))
        self.low_stock_threshold.setToolTip(
            tr("Spulen unter diesem Anteil ihrer Nennfüllung als Wenig Filament kennzeichnen.")
        )
        self.low_stock_threshold.valueChanged.connect(self._threshold_changed)
        threshold_label = QLabel(tr("Warnschwelle für niedrigen Bestand"), shelf)
        threshold_label.setBuddy(self.low_stock_threshold)
        settings_layout.addWidget(threshold_label)
        settings_layout.addWidget(self.low_stock_threshold)
        layout.addWidget(collapsible(tr("Lager-Einstellungen"), settings_area, open_now=False))
        self.add_button = QPushButton(tr("Spule von Hand anlegen"), shelf)
        self.add_button.clicked.connect(self._add)
        self.import_button = QPushButton(tr("Aus dem Slicer übernehmen"), shelf)
        self.import_button.clicked.connect(self._import)
        actions = QVBoxLayout()
        actions.addWidget(self.add_button)
        actions.addWidget(self.import_button)
        layout.addLayout(actions)
        self.empty = QLabel(
            tr(
                "Ihr Regal ist noch leer. Eine Spule von Hand anlegen "
                "oder bewusst aus dem Slicer übernehmen."
            ),
            shelf,
        )
        self.empty.setWordWrap(True)
        layout.addWidget(self.empty)
        self.page_scroll = QScrollArea(shelf)
        self.page_scroll.setWidgetResizable(True)
        self.page_scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.shelves = QWidget(self.page_scroll)
        self.grid = QGridLayout(self.shelves)
        self.grid.setSpacing(NORMAL)
        self.page_scroll.setWidget(self.shelves)
        self.page_scroll.viewport().installEventFilter(self)
        layout.addWidget(self.page_scroll, 1)
        self.pages.addWidget(shelf)
        self.detail = QWidget(self)
        detail_scroll = QScrollArea(self)
        detail_scroll.setWidgetResizable(True)
        detail_scroll.setWidget(self.detail)
        self.detail_layout = QVBoxLayout(self.detail)
        self.pages.addWidget(detail_scroll)
        self.message = QLabel(self)
        self.message.setWordWrap(True)
        outer.addWidget(self.message)
        self.retry_button = QPushButton(tr("Erneut laden"), self)
        self.retry_button.clicked.connect(self.refresh)
        self.retry_button.hide()
        outer.addWidget(self.retry_button)
        self.keep_count_button = QPushButton(tr("Rücknahme mit aktuellem Bestand"), self)
        self.keep_count_button.setToolTip(
            tr(
                "Jüngere Bestandsfeststellungen bleiben unverändert. "
                "Der gesamte Druckvorgang wird zurückgenommen."
            )
        )
        self.keep_count_button.clicked.connect(self._reverse_preserving_counts)
        self.keep_count_button.hide()
        outer.addWidget(self.keep_count_button)
        self.progress = QProgressBar(self)
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setAccessibleName(tr("Filamentlager wird aktualisiert"))
        self.progress.hide()
        outer.addWidget(self.progress)
        self.cancel_button = QPushButton(tr("Abbrechen"), self)
        self.cancel_button.clicked.connect(self._cancel)
        self.cancel_button.hide()
        outer.addWidget(self.cancel_button)
        self.refresh()

    def set_booking_mode(self, mode: str) -> None:
        """Die gespeicherte Vorgabe zeigt sich ohne erneutes Speichersignal."""
        with QSignalBlocker(self.booking_mode):
            self.booking_mode.setCurrentIndex(max(0, self.booking_mode.findData(mode)))

    def _booking_mode_changed(self, _index: int) -> None:
        self.bookingModeChanged.emit(str(self.booking_mode.currentData()))

    def set_low_stock_threshold(self, percent: float) -> None:
        """Eine gespeicherte Warnschwelle verändert keine Bestandsmenge."""
        self._low_stock_percent = max(0.0, min(100.0, percent))
        with QSignalBlocker(self.low_stock_threshold):
            self.low_stock_threshold.setValue(self._low_stock_percent)
        self._refill()

    def _threshold_changed(self, percent: float) -> None:
        self._low_stock_percent = percent
        self._refill()
        self.lowStockThresholdChanged.emit(percent)

    def refresh(self, *_args: object) -> None:
        """Lagerdaten neu lesen, ohne gespeicherte Projektwerte anzufassen."""
        try:
            self._entries = filaments.catalogue(
                include_archived=self.archived.isChecked(), strict=True
            )
        except Exception:
            self._failed("")
            return
        self.summary.setText(tr("{count} Spulen im Lager").format(count=len(self._entries)))
        self.retry_button.hide()
        self._refill()
        if self._selected_id:
            self.show_spool(self._selected_id)

    def _refill(self, *_args: object) -> None:
        """Suche und Gruppierung verändern die Auswahl der sichtbaren Spulen."""
        focused = next((card.entry.identifier for card in self.cards if card.hasFocus()), "")
        for row in range(self.grid.rowCount()):
            self.grid.setRowStretch(row, 0)
        while self.grid.count():
            item = self.grid.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.hide()
                widget.deleteLater()
        self.cards = []
        query = self.search.text().strip().casefold()
        entries = [entry for entry in self._entries if query in spool_label(entry).casefold()]
        field = str(self.grouping.currentData())
        groups: dict[str, list[filaments.CatalogueFilament]] = {}
        for entry in entries:
            key = getattr(entry, field) or (
                tr("Unbekannt") if field == "material_type" else tr("Ohne Lagerort")
            )
            groups.setdefault(key, []).append(entry)
        columns = max(1, self.page_scroll.viewport().width() // 230)
        self._columns = columns
        row = 0
        for group, group_entries in sorted(groups.items()):
            heading = QLabel(group, self.shelves)
            set_level(heading, "section")
            self.grid.addWidget(heading, row, 0, 1, columns)
            row += 1
            for index, entry in enumerate(group_entries):
                card = SpoolCard(entry, self.shelves, self._low_stock_percent)
                card.clicked.connect(partial(self._open_card, entry.identifier))
                self.grid.addWidget(card, row + index // columns, index % columns)
                self.cards.append(card)
                if entry.identifier == focused:
                    card.setFocus(Qt.FocusReason.OtherFocusReason)
            row += (len(group_entries) + columns - 1) // columns
            rail = QFrame(self.shelves)
            rail.setFrameShape(QFrame.Shape.HLine)
            self.grid.addWidget(rail, row, 0, 1, columns)
            row += 1
        self.grid.setRowStretch(row, 1)
        self.empty.setVisible(not entries)
        self.empty.setText(
            tr("Keine Spule passt zur Suche. Suchfeld leeren oder eine Spule anlegen.")
            if self._entries
            else tr(
                "Ihr Regal ist noch leer. Eine Spule von Hand anlegen "
                "oder bewusst aus dem Slicer übernehmen."
            )
        )

    def resizeEvent(self, event: Any) -> None:  # noqa: N802 — Qt-Name
        super().resizeEvent(event)
        if max(1, self.page_scroll.viewport().width() // 230) != self._columns:
            self._refill()

    def eventFilter(self, watched: Any, event: Any) -> bool:  # noqa: N802 — Qt-Name
        """Die tatsächliche Breite des Rollbereichs bestimmt das Regalraster."""
        if stop_watching_the_dying(self, watched, event):
            return False
        if (
            event.type() == QEvent.Type.Resize
            and hasattr(self, "page_scroll")
            and max(1, self.page_scroll.viewport().width() // 230) != self._columns
        ):
            self._refill()
        return super().eventFilter(watched, event)

    def _open_card(self, identifier: str, _checked: bool = False) -> None:
        self.show_spool(identifier)

    def show_spool(self, identifier: str) -> None:
        """Das Detail bleibt auch bei gleichen Etiketten genau an dieser Spule."""
        entry = filaments.get(identifier)
        if entry is None:
            self.show_shelf()
            return
        self._selected_id = identifier
        while self.detail_layout.count():
            item = self.detail_layout.takeAt(0)
            widget = item.widget() if item is not None else None
            if widget is not None:
                widget.deleteLater()
        back = QPushButton(tr("Zurück zum Regal"), self.detail)
        back.clicked.connect(self.show_shelf)
        self.detail_layout.addWidget(back)
        card = SpoolCard(entry, self.detail, self._low_stock_percent)
        card.setMaximumWidth(400)
        self.detail_layout.addWidget(card)
        description = QLabel(spool_label(entry), self.detail)
        description.setWordWrap(True)
        self.detail_layout.addWidget(description)
        for text, action in (
            (tr("Angaben ändern"), self._edit),
            (tr("Noch eine davon"), self._duplicate),
            (tr("Wiederherstellen") if entry.archived else tr("Archivieren"), self._archive),
        ):
            button = QPushButton(text, self.detail)
            button.clicked.connect(action)
            self.detail_layout.addWidget(button)
        heading = QLabel(tr("Buchungsverlauf"), self.detail)
        set_level(heading, "section")
        self.detail_layout.addWidget(heading)
        self.history = QListWidget(self.detail)
        self.history.setAccessibleName(tr("Buchungsverlauf dieser Spule"))
        self.detail_layout.addWidget(self.history)
        self.reverse_button = QPushButton(tr("Gewählten Vorgang zurücknehmen"), self.detail)
        self.reverse_button.clicked.connect(self._reverse)
        self.detail_layout.addWidget(self.reverse_button)
        self._fill_history(entry)
        self.pages.setCurrentIndex(1)

    def _fill_history(self, entry: filaments.CatalogueFilament) -> None:
        """Jede Herkunft bleibt sichtbar; Rücknahme gilt dem gesamten Vorgang."""
        source_names = {
            "internal": tr("Solidon-Schätzung"),
            "gcode": tr("Aus G-Code geplant"),
            "manual": tr("Von Hand eingetragen"),
        }
        for booking in reversed(filaments.bookings(entry.identifier)):
            lines = [
                booking.project_name or tr("Druckvorgang"),
                local_timestamp(booking.created_at),
            ]
            for position in booking.positions:
                if position.spool_identifier == entry.identifier:
                    lines.append(
                        tr("{grams} g · {source}").format(
                            grams=localised(f"{position.grams:.1f}"),
                            source=source_names[position.source],
                        )
                    )
            for correction in booking.corrections:
                previous = sum(
                    position.grams
                    for position in correction.previous_positions
                    if position.spool_identifier == entry.identifier
                )
                fresh = sum(
                    position.grams
                    for position in correction.positions
                    if position.spool_identifier == entry.identifier
                )
                lines.append(
                    tr("Korrektur: {before} g → {after} g").format(
                        before=localised(f"{previous:.1f}"), after=localised(f"{fresh:.1f}")
                    )
                )
            if booking.reversed_at:
                lines.append(tr("Zurückgenommen"))
            if any(
                count.spool_identifier == entry.identifier for count in booking.preserved_counts
            ):
                lines.append(tr("Jüngere Bestandsfeststellung beibehalten"))
            item = QListWidgetItem(" · ".join(lines), self.history)
            item.setData(Qt.ItemDataRole.UserRole, booking.operation_id)
            item.setData(int(Qt.ItemDataRole.UserRole) + 1, bool(booking.reversed_at))
            item.setToolTip(
                tr("Nimmt den gesamten Druckvorgang mit allen beteiligten Spulen zurück.")
            )
        self.history.currentRowChanged.connect(self._history_selected)
        self.reverse_button.setEnabled(False)
        if not self.history.count():
            item = QListWidgetItem(tr("Noch keine Buchungen für diese Spule."), self.history)
            item.setFlags(Qt.ItemFlag.NoItemFlags)

    def _history_selected(self, row: int) -> None:
        self.reverse_button.setEnabled(
            row >= 0 and not bool(self.history.item(row).data(int(Qt.ItemDataRole.UserRole) + 1))
        )

    def show_shelf(self) -> None:
        self._selected_id = ""
        self.pages.setCurrentIndex(0)

    def release(self, timeout_ms: int = WAIT_TIMEOUT_MS) -> None:
        """Die gemeinsame Aufräumstelle wartet auf noch laufende Lageränderungen."""
        self._leash.wait_all(timeout_ms)

    def wait_for_workers(self, timeout_ms: int = 0) -> bool:
        """Laufende Lageränderungen enden vor dem Schließen des Hauptfensters."""
        self.release(timeout_ms)
        return not any(worker.isRunning() for worker in self._leash.pending())

    def _add(self) -> None:
        dialog = NewFilamentDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._run(partial(filaments.save, dialog.entry()), self._saved)

    def _edit(self) -> None:
        entry = filaments.get(self._selected_id)
        if entry is None:
            return
        dialog = NewFilamentDialog(self, entry=entry)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._run(partial(filaments.save, dialog.entry()), self._saved)

    def _duplicate(self) -> None:
        self._run(partial(filaments.duplicate, self._selected_id), self._saved)

    def _archive(self) -> None:
        entry = filaments.get(self._selected_id)
        if entry is not None:
            action = filaments.restore if entry.archived else filaments.archive
            self._run(partial(action, entry.identifier), self._saved)

    def _reverse(self) -> None:
        item = self.history.currentItem()
        if item is not None:
            identifier = str(item.data(Qt.ItemDataRole.UserRole))
            self._run(partial(filaments.reverse_booking, identifier), self._saved)

    def _reverse_preserving_counts(self) -> None:
        """Die erklärte Ausnahme wird erst auf diesen zweiten bewussten Klick ausgeführt."""
        item = self.history.currentItem()
        if item is not None:
            identifier = str(item.data(Qt.ItemDataRole.UserRole))
            self._run(
                partial(filaments.reverse_booking, identifier, preserve_newer_counts=True),
                self._saved,
            )

    def _import(self) -> None:
        self._run(configured_spools, self._choose_import)

    def _choose_import(self, result: object) -> None:
        entries = tuple(result) if isinstance(result, (tuple, list)) else ()
        if not entries:
            self.message.setText(
                tr(
                    "Kein Slicer-Profil gefunden. Unter Datei → Einstellungen einen Slicer "
                    "einrichten oder eine Spule von Hand anlegen."
                )
            )
            return
        dialog = SlicerSpoolDialog(entries, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self._run(partial(filaments.synchronise, dialog.chosen_spools()), self._saved)

    def _run(self, action: Callable[[], object], callback: Callable[[object], None]) -> None:
        """Schreiben und Suchen halten die letzte gültige Ansicht sichtbar."""
        if self._worker is not None:
            return
        self._callback = callback
        self.keep_count_button.hide()
        worker = _InventoryWork(action)
        self._worker = worker
        worker.completed.connect(self._completed)
        worker.rejected.connect(self._rejected)
        worker.crashed.connect(self._failed)
        self._wait_cursor.start(200)
        self._wait_progress.start(2000)
        self._leash.start(worker)

    def _show_wait_cursor(self) -> None:
        if self._worker is not None:
            self.setCursor(Qt.CursorShape.BusyCursor)

    def _show_wait_progress(self) -> None:
        if self._worker is not None:
            self.progress.show()
            self.cancel_button.setVisible(self._callback == self._choose_import)

    def _stop_waiting(self) -> None:
        self._wait_cursor.stop()
        self._wait_progress.stop()
        self.unsetCursor()
        self.progress.hide()
        self.cancel_button.hide()

    def _completed(self, result: object) -> None:
        callback = self._callback
        self._worker = None
        self._callback = None
        self._stop_waiting()
        if callback is not None:
            callback(result)

    def _failed(self, _reason: str) -> None:
        self._worker = None
        self._callback = None
        self._stop_waiting()
        self.message.setText(
            tr(
                "Das Lager konnte nicht aktualisiert werden. Angaben und Schreibrechte prüfen "
                "und die Handlung erneut wählen."
            )
        )
        self.retry_button.show()

    def _rejected(self, problem: object) -> None:
        """Fachliche Konflikte nennen ihren Grund; Angaben ändern bleibt erreichbar."""
        self._failed("")
        self.message.setText(str(problem))
        self.keep_count_button.setVisible(
            isinstance(problem, ValidationError) and problem.constraint == "stock_conflict"
        )

    def _cancel(self) -> None:
        if self._worker is not None:
            self._worker.requestInterruption()
        self._callback = None
        self.message.setText(
            tr(
                "Suche abgebrochen. Bereits gespeicherte Lageränderungen bleiben "
                "im Verlauf erreichbar."
            )
        )
        self._stop_waiting()

    def _saved(self, _result: object) -> None:
        if isinstance(_result, filaments.CatalogueFilament):
            self._selected_id = _result.identifier
        self.refresh()
        self.catalogueChanged.emit()
