"""Buchungsangebote nach der Ausgabe, mit ausdrücklich gewählten Spulen (§20)."""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, replace
from functools import partial
from typing import cast, override
from uuid import uuid4

from PySide6.QtCore import QObject, QSignalBlocker, Qt, QTimer, Signal
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFrame,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.core.errors import AppError
from app.core.export.threemf import slot_identity
from app.core.filament_usage import UsageLine, UsageRequest, costs_for
from app.core.knowledge import filaments
from app.core.scene.hashing import digest
from app.i18n import source_text, tr
from app.ui.filament_picker import NewFilamentDialog, hex_of, spool_label, swatch
from app.ui.labels import NumberSpin, local_timestamp, localised
from app.ui.leash import RELEASE_RETRY_MS, Worker, WorkerLeash, weak_slot
from app.ui.settings import UiSettings
from app.ui.style import NORMAL, ROOMY, TARGET_SIZE, TIGHT, WIDE, make_primary, set_level


def _line_key(line: UsageLine) -> str:
    """Die gleiche Druckfilamentidentität wie beim Zusammenlegen der Ausgabe."""
    name, colour, profile, material = slot_identity(line.slot)
    return digest(source_text(name), colour, profile, material)


def _matches(entry: filaments.CatalogueFilament, line: UsageLine) -> bool:
    """Unbekannte Materialtypen werden auch bei gleicher Farbe nicht geraten."""
    material_type = line.slot.material_type
    return (
        material_type is not None
        and bool(material_type)
        and (
            entry.material_type.casefold() == material_type.casefold()
            and entry.colour.lower() == hex_of(line.slot.colour).lower()
            and entry.slicer_profile == (line.slot.material or "")
        )
    )


def _note(line: UsageLine, *, split: bool = False) -> str:
    """Journalwerte sind sprachunabhängig, ihre Beschriftung entsteht erst in der Ansicht."""
    if split:
        return "manual_allocation"
    if line.source == "manual":
        return ""
    if line.source == "internal":
        return "without_supports_and_adhesion"
    return "converted_from_length" if line.converted_from_length else ""


def _source(line: UsageLine) -> str:
    """Herkunft der jeweiligen Zahl, ohne G-Code zu einer Messung zu erklären."""
    if line.source == "internal":
        return tr("Solidon-Schätzung · ohne Stützen und Haftungshilfen")
    if line.source == "manual":
        return tr("Von Hand eingetragen")
    if line.converted_from_length:
        return tr("Aus G-Code geplant · aus Länge, Durchmesser und Dichte umgerechnet")
    return tr("Aus G-Code geplant")


def _previous(
    request: UsageRequest, snapshot: filaments.InventorySnapshot | None = None
) -> list[filaments.InventoryBooking]:
    """Ein Fingerabdruck kann nach ausdrücklichen Wiederholungen mehrere Vorgänge haben."""
    return [
        booking
        for booking in (snapshot or filaments.read_snapshot()).bookings()
        if booking.fingerprint == request.fingerprint and not booking.reversed_at
    ]


@dataclass(frozen=True)
class _Snapshot:
    """Ein Leseergebnis ohne Widgets, im Dateiarbeiter zusammengetragen."""

    entries: tuple[filaments.CatalogueFilament, ...]
    bookings: tuple[filaments.InventoryBooking, ...]


def _snapshot(request: UsageRequest) -> _Snapshot:
    """Die abschließende Buchung prüft diesen Vorschlagsstand nochmals unter Sperre."""
    snapshot = filaments.read_snapshot()
    return _Snapshot(snapshot.catalogue(), tuple(_previous(request, snapshot)))


class _UsageWork(Worker):
    """Auch das Warten auf ein anderes Lagerfenster hält die Oberfläche nicht an."""

    completed = Signal(object)
    rejected = Signal(object)

    def __init__(self, action: Callable[[], object]) -> None:
        super().__init__()
        self.action: Callable[[], object] | None = action

    def work(self) -> None:
        assert self.action is not None
        try:
            result = self.action()
        except AppError as problem:
            self.rejected.emit(problem)
            return
        self.completed.emit(result)

    def release_finished_references(self) -> None:
        self.action = None
        super().release_finished_references()


class _UsageTasks(QObject):
    """Eine laufende Lagerhandlung mit einer Halteleine für beide Buchungsansichten."""

    completed = Signal(object)
    rejected = Signal(object)
    busyChanged = Signal(bool)

    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.worker: _UsageWork | None = None
        self.leash = WorkerLeash(self)

    def run(self, action: Callable[[], object]) -> None:
        if self.worker is not None:
            return
        worker = _UsageWork(action)
        self.worker = worker
        worker.completed.connect(self._completed)
        worker.rejected.connect(self._rejected)
        worker.crashed.connect(self._crashed)
        self.busyChanged.emit(True)
        self.leash.start(worker)

    def _completed(self, result: object) -> None:
        self.worker = None
        self.busyChanged.emit(False)
        self.completed.emit(result)

    def _rejected(self, problem: object) -> None:
        self.worker = None
        self.busyChanged.emit(False)
        self.rejected.emit(problem)

    def _crashed(self, _reason: str) -> None:
        self._rejected(
            tr(
                "Das Lager konnte nicht aktualisiert werden. Prüfen Sie die Angaben "
                "und versuchen Sie es erneut."
            )
        )

    def release(self, timeout_ms: int = 2000) -> None:
        self.leash.wait_all(timeout_ms)


class UsageDialog(QDialog):
    """Mengen und Aufteilungen bestätigen; die Ausgabe ist bereits erfolgt."""

    def __init__(self, request: UsageRequest, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.request = request
        self._lines = list(request.lines)
        self._manual: set[int] = set()
        self._new_operation_id = uuid4().hex
        self._entries: dict[str, filaments.CatalogueFilament] = {}
        self._bookings: dict[str, filaments.InventoryBooking] = {}
        self._loaded = False
        self._created_identifier = ""
        self._pending = "load"
        self._tasks = _UsageTasks(self)
        self._tasks.completed.connect(self._completed)
        self._tasks.rejected.connect(self._rejected)
        self._tasks.busyChanged.connect(self._validate)
        self.setWindowTitle(tr("Filamentverbrauch buchen"))
        self.resize(680, 520)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(WIDE, WIDE, WIDE, WIDE)
        layout.setSpacing(NORMAL)
        self.title = QLabel(tr("Filamentverbrauch buchen"), self)
        set_level(self.title, "title")
        self.title.setWordWrap(True)
        layout.addWidget(self.title)
        self.project_label = QLabel(
            tr("{project} · Platte {plate}").format(
                project=request.project_name, plate=request.plate + 1
            ),
            self,
        )
        self.project_label.setTextFormat(Qt.TextFormat.PlainText)
        self.project_label.setWordWrap(True)
        set_level(self.project_label, "section")
        layout.addWidget(self.project_label)
        intro = QLabel(
            tr(
                "Die Datei wurde ausgegeben. Buchen Sie den "
                "vorgesehenen Druck oder lassen Sie den Bestand unverändert."
            ),
            self,
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)
        self.operation = QComboBox(self)
        self.operation.setAccessibleName(tr("Druckvorgang"))
        layout.addWidget(self.operation)
        self.content = QWidget(self)
        form = QVBoxLayout(self.content)
        form.setContentsMargins(0, 0, NORMAL, 0)
        form.setSpacing(NORMAL)
        self.cards: list[QGroupBox] = []
        self.choices: list[QComboBox] = []
        self.amounts: list[NumberSpin] = []
        self.sources: list[QLabel] = []
        self.suggestions: list[QLabel] = []
        self.costs: list[QLabel] = []
        self.split_checks: list[QCheckBox] = []
        self.split_panels: list[QWidget] = []
        self.allocations: list[list[tuple[QComboBox, NumberSpin, QWidget]]] = []
        for index, line in enumerate(request.lines):
            card = QGroupBox(self.content)
            card.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
            row = QVBoxLayout(card)
            row.setContentsMargins(ROOMY, ROOMY, ROOMY, ROOMY)
            row.setSpacing(NORMAL)
            heading = QHBoxLayout()
            marker = QLabel(card)
            marker.setPixmap(swatch(hex_of(line.slot.colour)).pixmap(NORMAL * 3, NORMAL * 3))
            name = QLabel(str(line.slot.name) or tr("Ohne Filamentzuweisung"), card)
            name.setTextFormat(Qt.TextFormat.PlainText)
            name.setWordWrap(True)
            set_level(name, "section")
            heading.addWidget(marker)
            heading.addWidget(name, 1)
            choice = QComboBox(self.content)
            choice.setSizeAdjustPolicy(
                QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
            )
            choice.setMinimumContentsLength(12)
            choice.currentTextChanged.connect(choice.setToolTip)
            choice.setAccessibleName(tr("Spule für {name}").format(name=str(line.slot.name)))
            choice.setMinimumHeight(TARGET_SIZE)
            amount = self._amount_widget(line.grams, self.content)
            amount.setAccessibleName(tr("Verbrauch für {name}").format(name=str(line.slot.name)))
            set_level(amount, "section")
            heading.addWidget(amount)
            row.addLayout(heading)
            source = QLabel(_source(line), self.content)
            source.setWordWrap(True)
            suggestion = QLabel("", self.content)
            suggestion.setWordWrap(True)
            cost = QLabel("", self.content)
            cost.setWordWrap(True)
            split = QCheckBox(tr("Auf mehrere Spulen aufteilen"), self.content)
            split.setAccessibleDescription(
                tr("Die Gesamtmenge wird über einzeln eingetragene Spulenmengen verteilt.")
            )
            panel = QWidget(self.content)
            split_layout = QVBoxLayout(panel)
            split_layout.setContentsMargins(0, 0, 0, 0)
            add = QPushButton(tr("Weitere Spule"), panel)
            add.clicked.connect(lambda _checked=False, row=index: self._add_allocation(row))
            split_layout.addWidget(add)
            panel.hide()
            for widget in (source, choice, suggestion, split, panel, cost):
                row.addWidget(widget)
            set_level(cost, "section")
            form.addWidget(card)
            self.cards.append(card)
            self.choices.append(choice)
            self.amounts.append(amount)
            self.sources.append(source)
            self.suggestions.append(suggestion)
            self.costs.append(cost)
            self.split_checks.append(split)
            self.split_panels.append(panel)
            self.allocations.append([])
            amount.valueChanged.connect(lambda _value, row=index: self._amount_changed(row))
            choice.currentIndexChanged.connect(lambda _value, row=index: self._choice_changed(row))
            split.toggled.connect(lambda checked, row=index: self._toggle_split(row, checked))
        scroll = QScrollArea(self)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidgetResizable(True)
        form.addStretch()
        scroll.setWidget(self.content)
        layout.addWidget(scroll, 1)
        self.add_button = QPushButton(tr("Spule anlegen …"), self)
        self.add_button.clicked.connect(self._create_spool)
        self.allow_unverified = QCheckBox(
            tr("Trotz unklarem Bestand buchen; die Restmenge danach bleibt unbekannt."), self
        )
        self.allow_unverified.toggled.connect(self._validate)
        layout.addWidget(self.allow_unverified)
        self.state = QLabel("", self)
        self.state.setWordWrap(True)
        layout.addWidget(self.state)
        self.reload_button = QPushButton(tr("Lager neu laden"), self)
        self.reload_button.clicked.connect(self._load)
        utilities = QHBoxLayout()
        utilities.addWidget(self.add_button)
        utilities.addWidget(self.reload_button)
        utilities.addStretch()
        self.repeat_button = QPushButton(tr("Noch einmal gedruckt"), self)
        utilities.addWidget(self.repeat_button)
        layout.addLayout(utilities)
        buttons = QDialogButtonBox(self)
        self.book_button = buttons.addButton(tr("Abziehen"), QDialogButtonBox.ButtonRole.AcceptRole)
        self.correct_button = buttons.addButton(
            tr("Mengenaufteilung korrigieren"), QDialogButtonBox.ButtonRole.ActionRole
        )
        buttons.addButton(tr("Nicht buchen"), QDialogButtonBox.ButtonRole.RejectRole)
        self.book_button.clicked.connect(self._book)
        make_primary(self.book_button)
        self.correct_button.clicked.connect(lambda: self._book(correct_manual=True))
        self.repeat_button.clicked.connect(self._repeat)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.operation.currentIndexChanged.connect(self._operation_changed)
        self._load()

    @staticmethod
    def _amount_widget(grams: float | None, parent: QWidget) -> NumberSpin:
        """Unbekannt ist ein eigener Zustand und wird nie zu null umgedeutet."""
        amount = NumberSpin(parent)
        amount.setRange(-1.0, 1_000_000.0)
        amount.setDecimals(3)
        amount.setSpecialValueText(tr("Unbekannt"))
        amount.setSuffix(" " + tr("g"))
        amount.setValue(grams if grams is not None else -1.0)
        return amount

    def _load(self) -> None:
        if self._tasks.worker is not None:
            return
        self._pending = "load"
        self._tasks.run(partial(_snapshot, self.request))

    def _completed(self, result: object) -> None:
        if self._pending == "book":
            self.accept()
            return
        if self._pending == "create":
            self._created_identifier = cast(filaments.CatalogueFilament, result).identifier
            self._load()
            return
        snapshot = cast(_Snapshot, result)
        self._entries = {entry.identifier: entry for entry in snapshot.entries}
        self._bookings = {booking.operation_id: booking for booking in snapshot.bookings}
        selected = self.operation.currentData()
        with QSignalBlocker(self.operation):
            self.operation.clear()
            if len(snapshot.bookings) > 1:
                self.operation.addItem(tr("Druckvorgang zuordnen …"), None)
            self.operation.addItem(tr("Neuer Druck"), "")
            for booking in snapshot.bookings:
                self.operation.addItem(
                    tr("Bereits gebucht · {time}").format(time=local_timestamp(booking.created_at)),
                    booking.operation_id,
                )
            if selected and self.operation.findData(selected) >= 0:
                self.operation.setCurrentIndex(self.operation.findData(selected))
            elif len(snapshot.bookings) == 1:
                self.operation.setCurrentIndex(1)
        self._loaded = True
        for index, choice in enumerate(self.choices):
            self._fill_choice(
                choice,
                self._lines[index],
                choice.currentData() or self._lines[index].spool_identifier,
                suggest=True,
            )
        for index, rows in enumerate(self.allocations):
            for choice, _amount, _widget in rows:
                self._fill_choice(
                    choice, self._lines[index], choice.currentData() or "", suggest=False
                )
        if self._created_identifier:
            free_choice = next((one for one in self.choices if not one.currentData()), None)
            if free_choice is not None:
                free_choice.setCurrentIndex(free_choice.findData(self._created_identifier))
            self._created_identifier = ""
            self._validate()
        else:
            self._operation_changed()

    def _rejected(self, problem: object) -> None:
        self._validate()
        self.state.setText(str(problem))
        self.state.show()
        self.reload_button.show()

    def _fill_choice(
        self, choice: QComboBox, line: UsageLine, selected: str, *, suggest: bool
    ) -> bool:
        """Bindung gewinnt; ungebundene Vorschläge werden ausdrücklich beschriftet."""
        with QSignalBlocker(choice):
            choice.clear()
            choice.addItem(tr("Spule wählen …"), "")
            ordered = sorted(
                self._entries.values(),
                key=lambda entry: (
                    not _matches(entry, line),
                    entry.remaining_grams is None,
                    line.grams is not None
                    and entry.remaining_grams is not None
                    and entry.remaining_grams < line.grams,
                    entry.remaining_grams if entry.remaining_grams is not None else float("inf"),
                    entry.name.casefold(),
                    entry.identifier,
                ),
            )
            for entry in ordered:
                choice.addItem(swatch(entry.colour), spool_label(entry), entry.identifier)
                choice.setItemData(
                    choice.count() - 1, spool_label(entry), Qt.ItemDataRole.ToolTipRole
                )
            suggested = False
            found = choice.findData(selected)
            if found >= 0:
                choice.setCurrentIndex(found)
            if not selected and suggest:
                candidate = next((entry for entry in ordered if _matches(entry, line)), None)
                if candidate is not None:
                    choice.setCurrentIndex(choice.findData(candidate.identifier))
                    suggested = True
        choice.setToolTip(choice.currentText())
        if suggest:
            index = self.choices.index(choice)
            self.suggestions[index].setText(
                tr("Vorschlag: {spool}. Erst „Abziehen“ bestätigt diese Wahl.").format(
                    spool=choice.currentText()
                )
                if suggested
                else (
                    tr("Die zugewiesene Spule fehlt. Wählen Sie ausdrücklich eine andere.")
                    if selected and found < 0
                    else ""
                )
            )
            self.suggestions[index].setVisible(bool(self.suggestions[index].text()))
        return suggested

    def _operation_changed(self) -> None:
        if not self._loaded:
            return
        self._manual.clear()
        self._lines = list(self.request.lines)
        booking = self._bookings.get(self.operation.currentData())
        for index, line in enumerate(self._lines):
            matching = (
                [one for one in booking.positions if one.filament_key == _line_key(line)]
                if booking
                else []
            )
            if (
                matching
                and line.source == "internal"
                and any(one.source != "internal" for one in matching)
            ):
                source: filaments.BookingSource = (
                    "gcode" if all(one.source == "gcode" for one in matching) else "manual"
                )
                line = replace(
                    line,
                    grams=math.fsum(one.grams for one in matching),
                    source=source,
                    converted_from_length=any(
                        one.note == "converted_from_length" for one in matching
                    ),
                )
                self._lines[index] = line
            with QSignalBlocker(self.amounts[index]):
                self.amounts[index].setValue(line.grams if line.grams is not None else -1)
            self.sources[index].setText(_source(line))
            if matching:
                self._fill_choice(
                    self.choices[index], line, matching[0].spool_identifier, suggest=False
                )
            with QSignalBlocker(self.split_checks[index]):
                self.split_checks[index].setChecked(len(matching) > 1)
            if len(matching) > 1:
                self._clear_allocations(index)
                for one in matching:
                    self._add_allocation(index, one.spool_identifier, one.grams)
            self._toggle_split(index, len(matching) > 1)
        self._validate()

    def _clear_allocations(self, index: int) -> None:
        for _choice, _amount, widget in self.allocations[index]:
            widget.deleteLater()
        self.allocations[index].clear()

    def _toggle_split(self, index: int, checked: bool) -> None:
        self.split_panels[index].setVisible(checked)
        self.choices[index].setVisible(not checked)
        if checked and not self.allocations[index]:
            self._add_allocation(index, self.choices[index].currentData() or "")
            self._add_allocation(index)
        self._validate()

    def _add_allocation(self, index: int, identifier: str = "", grams: float | None = None) -> None:
        panel = self.split_panels[index]
        widget = QWidget(panel)
        row = QHBoxLayout(widget)
        row.setContentsMargins(0, 0, 0, 0)
        choice = QComboBox(widget)
        choice.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        choice.setMinimumContentsLength(8)
        choice.currentTextChanged.connect(choice.setToolTip)
        choice.setAccessibleName(
            tr("Spule für {name}").format(name=str(self._lines[index].slot.name))
        )
        self._fill_choice(choice, self._lines[index], identifier, suggest=False)
        amount = self._amount_widget(grams, widget)
        amount.setAccessibleName(tr("Teilmenge dieser Spule"))
        remove = QPushButton(tr("Entfernen"), widget)
        row.addWidget(choice, 1)
        row.addWidget(amount)
        row.addWidget(remove)
        layout = cast(QVBoxLayout, panel.layout())
        layout.insertWidget(layout.count() - 1, widget)
        allocation = (choice, amount, widget)
        self.allocations[index].append(allocation)
        choice.currentIndexChanged.connect(self._validate)
        amount.valueChanged.connect(self._validate)
        remove.clicked.connect(lambda: self._remove_allocation(index, allocation))
        self._validate()

    def _remove_allocation(
        self, index: int, allocation: tuple[QComboBox, NumberSpin, QWidget]
    ) -> None:
        self.allocations[index].remove(allocation)
        allocation[2].deleteLater()
        self._validate()

    def _amount_changed(self, index: int) -> None:
        self._manual.add(index)
        self.sources[index].setText(tr("Von Hand eingetragen"))
        self._validate()

    def _choice_changed(self, index: int) -> None:
        """Eine ausdrückliche Wahl ersetzt den vorherigen automatischen Vorschlag."""
        self.suggestions[index].clear()
        self.suggestions[index].hide()
        self._validate()

    def _repeat(self) -> None:
        self._new_operation_id = uuid4().hex
        self.operation.setCurrentIndex(self.operation.findData(""))
        self._validate()

    def _positions(self) -> tuple[filaments.BookingPosition, ...]:
        """Nur ausdrücklich eingetragene Anteile werden auf mehrere Spulen verteilt."""
        positions = []
        for index, line in enumerate(self._lines):
            if self.split_checks[index].isChecked():
                for choice, amount, _widget in self.allocations[index]:
                    positions.append(
                        filaments.BookingPosition(
                            choice.currentData() or "",
                            amount.value(),
                            "manual",
                            _note(line, split=True),
                            filament_key=_line_key(line),
                        )
                    )
                continue
            effective = replace(line, source="manual") if index in self._manual else line
            grams = self.amounts[index].value() if index in self._manual else line.grams
            positions.append(
                filaments.BookingPosition(
                    self.choices[index].currentData() or "",
                    grams if grams is not None else -1,
                    effective.source,
                    _note(effective),
                    filament_key=_line_key(line),
                )
            )
        return tuple(positions)

    def _needs_manual_correction(self, positions: tuple[filaments.BookingPosition, ...]) -> bool:
        existing = self._bookings.get(self.operation.currentData())
        return bool(
            existing and any(one.source == "manual" for one in (*existing.positions, *positions))
        )

    def _validate(self, _changed: object = None) -> None:
        if not hasattr(self, "book_button"):
            return
        busy = self._tasks.worker is not None
        self.operation.setEnabled(not busy)
        self.content.setEnabled(not busy)
        self.add_button.setEnabled(not busy)
        self.reload_button.setEnabled(not busy)
        reason = ""
        positions = self._positions()
        existing = self._bookings.get(self.operation.currentData())
        if busy:
            reason = tr("Der Lagerbestand wird geprüft und gespeichert …")
        elif not self._loaded:
            reason = tr("Laden Sie das Lager, um Spulen und Mengen zu prüfen.")
        elif not self._lines:
            reason = tr("Für diese Ausgabe liegt kein Filamentbedarf vor.")
        elif self.operation.currentData() is None:
            reason = tr("Wählen Sie den Druckvorgang, zu dem die neue Angabe gehört.")
        elif any(not one.spool_identifier for one in positions) or not positions:
            reason = tr("Wählen Sie für jedes Druckfilament eine Spule oder legen Sie sie an.")
        elif any(one.grams < 0 for one in positions) or any(
            amount.value() < 0 for amount in self.amounts
        ):
            reason = tr(
                "Eine Einzelmenge fehlt. Slicen Sie das Modell oder tragen Sie die Menge ein."
            )
        elif len({one.key for one in positions}) != len(positions):
            reason = tr("Wählen Sie in einer Aufteilung jede Spule nur einmal.")
        for index, rows in enumerate(self.allocations):
            if self.split_checks[index].isChecked() and not reason:
                total = math.fsum(amount.value() for _choice, amount, _widget in rows)
                expected = self.amounts[index].value()
                if len(rows) < 2 or not math.isclose(total, expected):
                    reason = tr(
                        "Die Teilmengen müssen zusammen die angegebene Gesamtmenge ergeben."
                    )
        self._update_costs(positions)
        if not reason and existing and self._unchanged(existing, positions):
            reason = tr(
                "Dieser Druck wurde bereits gebucht. Für einen weiteren Druck "
                "wählen Sie „Noch einmal gedruckt“."
            )
        if not reason and not self.allow_unverified.isChecked():
            demand: dict[str, float] = {}
            for one in positions:
                demand[one.spool_identifier] = demand.get(one.spool_identifier, 0) + one.grams
            if existing:
                for one in existing.positions:
                    demand[one.spool_identifier] = demand.get(one.spool_identifier, 0) - one.grams
            if any(
                identifier not in self._entries
                or self._entries[identifier].remaining_grams is None
                or cast(float, self._entries[identifier].remaining_grams) < grams
                for identifier, grams in demand.items()
            ):
                reason = tr(
                    "Der Bestand ist unbekannt oder reicht nicht aus. Wählen Sie eine andere "
                    "Spule, korrigieren Sie den Bestand im Lager oder bestätigen Sie den "
                    "Abzug ausdrücklich."
                )
        manual_correction = self._needs_manual_correction(positions)
        self.correct_button.setVisible(manual_correction)
        self.correct_button.setEnabled(not reason)
        self.book_button.setVisible(not manual_correction)
        make_primary(self.correct_button if manual_correction else self.book_button)
        self.book_button.setText(tr("G-Code-Angabe übernehmen") if existing else tr("Abziehen"))
        self.book_button.setEnabled(not reason)
        self.repeat_button.setVisible(bool(self._bookings))
        self.repeat_button.setEnabled(not busy)
        self.book_button.setToolTip(reason)
        self.book_button.setAccessibleDescription(reason)
        self.correct_button.setAccessibleDescription(
            tr(
                "Die bisher gebuchten Mengen werden durch diese ausdrücklich eingegebenen "
                "Mengen ersetzt. Der Verlauf bleibt erhalten."
            )
        )
        self.state.setText(reason)
        self.state.setVisible(bool(reason))
        self.reload_button.setVisible(not self._loaded or bool(reason))

    @staticmethod
    def _unchanged(
        existing: filaments.InventoryBooking, positions: tuple[filaments.BookingPosition, ...]
    ) -> bool:
        old = {one.key: one for one in existing.positions}
        return len(old) == len(positions) and all(
            one.key in old
            and one.source == old[one.key].source
            and math.isclose(one.grams, old[one.key].grams)
            for one in positions
        )

    def _update_costs(self, positions: tuple[filaments.BookingPosition, ...]) -> None:
        for line, label in zip(self._lines, self.costs, strict=True):
            rows = [one for one in positions if one.filament_key == _line_key(line)]
            totals = costs_for(rows, self._entries)
            label.setText(
                tr("Materialkosten: {cost}").format(
                    cost=" + ".join(
                        localised(f"{value:.2f}") + " " + currency
                        for currency, value in sorted(totals.items())
                    )
                )
                if totals
                else ""
            )
            label.setVisible(bool(label.text()))

    def _create_spool(self) -> None:
        dialog = NewFilamentDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._pending = "create"
            self._tasks.run(partial(filaments.save, dialog.entry()))

    def _book(self, _checked: bool = False, *, correct_manual: bool = False) -> None:
        self._validate()
        if self._needs_manual_correction(self._positions()) and not correct_manual:
            return
        button = self.correct_button if correct_manual else self.book_button
        if not button.isEnabled():
            return
        self._pending = "book"
        existing = self._bookings.get(self.operation.currentData())
        self._tasks.run(
            partial(
                filaments.book,
                self.operation.currentData() or self._new_operation_id,
                self.request.fingerprint,
                self._positions(),
                project_name=self.request.project_name,
                allow_unverified_stock=self.allow_unverified.isChecked(),
                correct_manual_allocation=correct_manual,
                expected_booking_updated_at=existing.updated_at if existing else None,
            )
        )

    def release(self, timeout_ms: int = 2000) -> None:
        self._tasks.release(timeout_ms)

    def wait_for_workers(self, timeout_ms: int = 0) -> bool:
        """Auch ein schon geschlossener Dialog hält bestätigte Lagerarbeit bis zum Ende."""
        if timeout_ms > 0:
            self.release(timeout_ms)
        return self._tasks.worker is None and all(
            not worker.isRunning() and worker.wait(0) for worker in self._tasks.leash.pending()
        )

    def reject(self) -> None:
        """Ein bereits bestätigter atomarer Schreibvorgang wird nicht als Abbruch ausgegeben."""
        if self._pending != "book" or self._tasks.worker is None:
            super().reject()

    @override
    def closeEvent(self, event: QCloseEvent) -> None:
        if self._pending == "book" and self._tasks.worker is not None:
            event.ignore()
        else:
            super().closeEvent(event)


def _preferred_request(previous: UsageRequest | None, current: UsageRequest) -> UsageRequest:
    """Eine spätere interne Schätzung verdrängt keine bereits bekannte G-Code-Angabe."""
    if previous is None:
        return current
    old = {_line_key(line): line for line in previous.lines}
    current_keys = {_line_key(line) for line in current.lines}
    extra = (
        tuple(
            line
            for line in previous.lines
            if line.source == "gcode" and _line_key(line) not in current_keys
        )
        if all(line.source == "internal" for line in current.lines)
        else ()
    )
    return replace(
        current,
        lines=tuple(
            old[_line_key(line)]
            if _line_key(line) in old
            and old[_line_key(line)].source == "gcode"
            and (
                line.source != "gcode"
                or (line.grams is None and old[_line_key(line)].grams is not None)
            )
            else line
            for line in current.lines
        )
        + extra,
    )


def _auto_book(request: UsageRequest) -> filaments.InventoryBooking | None:
    """Nur vorhandene Bindungen, vollständige Mengen und sichere Bestände buchen von selbst."""
    existing = _previous(request)
    if len(existing) > 1 or not request.lines:
        return None
    if existing and any(one.source == "manual" for one in existing[0].positions):
        return None
    positions = []
    for line in request.lines:
        if not line.spool_identifier or line.grams is None:
            return None
        entry = filaments.get(line.spool_identifier)
        if (
            entry is None
            or entry.archived
            or entry.remaining_grams is None
            or not _matches(entry, line)
        ):
            return None
        if existing:
            prior = [one for one in existing[0].positions if one.filament_key == _line_key(line)]
            if len(prior) != 1 or prior[0].spool_identifier != line.spool_identifier:
                return None
            if prior[0].source == "gcode" and line.source != "gcode":
                positions.append(prior[0])
                continue
        positions.append(
            filaments.BookingPosition(
                line.spool_identifier,
                line.grams,
                line.source,
                _note(line),
                filament_key=_line_key(line),
            )
        )
    return filaments.book(
        existing[0].operation_id
        if existing
        else digest("automatic_filament_usage", request.fingerprint),
        request.fingerprint,
        positions,
        project_name=request.project_name,
    )


class UsageNotice(QWidget):
    """Das Ausgabeergebnis behält seinen Buchungsweg, ohne Zeitlimit."""

    changed = Signal()

    def __init__(self, settings: UiSettings, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.requests: dict[str, UsageRequest] = {}
        self._pending: dict[str, UsageRequest] = {}
        self._booked: set[str] = set()
        self._dialogs: list[UsageDialog] = []
        self._tasks = _UsageTasks(self)
        self._tasks.completed.connect(self._completed)
        self._tasks.rejected.connect(self._rejected)
        self.choice = QComboBox(self)
        self.choice.setAccessibleName(tr("Offene Filamentbuchung"))
        self.choice.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.choice.setMinimumContentsLength(10)
        self.choice.currentTextChanged.connect(self.choice.setToolTip)
        self.review = QPushButton(tr("Filament abziehen …"), self)
        self.review.clicked.connect(self._review)
        self.choice.currentIndexChanged.connect(self._sync_review)
        row = QHBoxLayout(self)
        row.setContentsMargins(0, TIGHT, 0, TIGHT)
        row.setSpacing(NORMAL)
        row.addWidget(self.choice, 1)
        row.addWidget(self.review)
        self.hide()

    def offer(self, request: UsageRequest, *, auto_book: bool = True) -> None:
        """Ein erfolgreiches Ergebnis oder dessen Weitergabe erzeugt höchstens ein Angebot."""
        if self.settings.inventory_booking_mode == "never":
            return
        request = _preferred_request(self.requests.get(request.fingerprint), request)
        self.requests[request.fingerprint] = request
        existing = self.choice.findData(request.fingerprint)
        label = tr("{project} · Platte {plate}").format(
            project=request.project_name, plate=request.plate + 1
        )
        if existing < 0:
            self.choice.addItem(label, request.fingerprint)
            existing = self.choice.count() - 1
        else:
            self.choice.setItemText(existing, label)
        if request.lines:
            self.choice.setItemIcon(existing, swatch(hex_of(request.lines[0].slot.colour)))
        self.choice.setCurrentIndex(existing)
        self.show()
        if auto_book and self.settings.inventory_booking_mode == "auto":
            self._pending[request.fingerprint] = request
            self._start_pending()

    def _start_pending(self) -> None:
        if self._tasks.worker is not None or not self._pending:
            return
        key = next(iter(self._pending))
        request = self._pending.pop(key)
        self.review.setEnabled(False)
        self.review.setText(tr("Bestand wird geprüft …"))
        self._tasks.run(partial(_auto_book, request))

    def _completed(self, result: object) -> None:
        if result is not None:
            self._booked.add(cast(filaments.InventoryBooking, result).fingerprint)
            self.changed.emit()
        self._sync_review()
        self._start_pending()

    def _sync_review(self, _index: int = -1) -> None:
        """Die Handlung gehört zur ausgewählten Ausgabe, nicht zum letzten Arbeiterergebnis."""
        busy = self._tasks.worker is not None
        self.review.setEnabled(not busy)
        self.review.setText(
            tr("Bestand wird geprüft …")
            if busy
            else (
                tr("Buchung ansehen …")
                if self.choice.currentData() in self._booked
                else tr("Filament abziehen …")
            )
        )

    def _rejected(self, problem: object) -> None:
        self.review.setToolTip(str(problem))
        self.review.setAccessibleDescription(str(problem))
        self._completed(None)

    def _review(self) -> None:
        request = self.requests.get(self.choice.currentData())
        if request is None:
            return
        dialog = UsageDialog(request, self)
        self._dialogs.append(dialog)
        try:
            if dialog.exec() == QDialog.DialogCode.Accepted:
                self._booked.add(request.fingerprint)
                self._sync_review()
                self.changed.emit()
        finally:
            self._release_dialog(dialog)

    def _release_dialog(self, dialog: UsageDialog) -> None:
        """Ein beendeter Dialog verschwindet erst nach seiner letzten Lagerrückmeldung."""
        if dialog.wait_for_workers(0):
            self._dialogs.remove(dialog)
            dialog.deleteLater()
        else:
            QTimer.singleShot(
                RELEASE_RETRY_MS, self, weak_slot(self, UsageNotice._release_dialog, dialog)
            )

    def release(self, timeout_ms: int = 2000) -> None:
        self._tasks.release(timeout_ms)
        for dialog in tuple(self._dialogs):
            dialog.release(timeout_ms)

    def wait_for_workers(self, timeout_ms: int = 0) -> bool:
        """Auch die eingereihten Buchungen enden, bevor ihr Besitzer geschlossen wird."""
        if timeout_ms > 0:
            self.release(timeout_ms)
        return (
            self._tasks.worker is None
            and not self._pending
            and all(dialog.wait_for_workers(0) for dialog in self._dialogs)
        )
