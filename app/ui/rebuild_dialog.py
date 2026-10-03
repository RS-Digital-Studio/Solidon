"""Nachbau prüfen, vergleichen und bewusst übernehmen (CAD-Konzept §13.5)."""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

from PySide6.QtCore import QSignalBlocker, Qt, QTimer, Signal
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QListWidget,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.errors import AppError, InternalError, OperationCancelled
from app.core.registry import REGISTRY
from app.core.scene.cancel import CancelSignal
from app.core.scene.project import ProjectSources
from app.core.scene.rebuild import (
    RebuildApplication,
    RebuildBudget,
    RebuildCandidate,
    RebuildProposal,
    prepare_application,
    propose,
)
from app.i18n import tr
from app.ui.dialogs import problem_text
from app.ui.labels import BoundedLengthSpin, BoundedSpin, length, localised, wheel_needs_focus
from app.ui.leash import DIALOG_WAIT_MS, Worker, WorkerLeash, weak_slot
from app.ui.style import NORMAL, WIDE, ContentHeight, DialogScrollArea, make_primary


class _RebuildWorker(Worker):
    """Ein eingefrorener Auftrag; ausschließlich der Kern erzeugt die Form."""

    completed = Signal(object)
    failed = Signal(object)
    progressed = Signal(float, str)

    def __init__(
        self,
        project: Any,
        base_dir: Any,
        profile: Any,
        object_id: str,
        budget: RebuildBudget,
        proposal: RebuildProposal | None = None,
        candidate: RebuildCandidate | None = None,
    ) -> None:
        super().__init__()
        self.project, self.base_dir, self.profile = project, base_dir, profile
        self.object_id, self.budget = object_id, budget
        self.proposal, self.candidate = proposal, candidate
        self.cancel = CancelSignal()

    def work(self) -> None:
        sources = ProjectSources(self.project, base_dir=self.base_dir)
        result: RebuildProposal | RebuildApplication
        try:
            if self.proposal is None:
                result = propose(
                    self.project.document,
                    self.object_id,
                    self.profile,
                    sources=sources,
                    budget=self.budget,
                    cancelled=self.cancel,
                    progress=self.progressed.emit,
                )
            else:
                assert self.candidate is not None
                result = prepare_application(
                    self.project.document,
                    self.proposal,
                    self.candidate,
                    self.profile,
                    sources=sources,
                    cancelled=self.cancel,
                    progress=self.progressed.emit,
                )
            self.cancel.raise_if_cancelled()
        except OperationCancelled:
            return
        except AppError as error:
            self.failed.emit(error)
            return
        self.completed.emit(result)


def check_text(candidate: RebuildCandidate) -> str:
    """Der Grund aus der unabhängigen Kernprüfung, ohne neue Annahmeregeln."""
    reasons = {
        "accepted": tr("Formprüfung bestanden"),
        "invalid": tr("Der Nachbau ist kein gültiger geschlossener Körper."),
        "invalid_source": tr("Das ursprüngliche Modell ist nicht eindeutig geschlossen."),
        "topology": tr("Öffnungen oder zusammenhängende Teile stimmen nicht überein."),
        "volume": tr("Die Volumenabweichung überschreitet Ihre Grenze."),
        "surface": tr("Die Formabweichung überschreitet Ihre Grenze."),
        "incomplete": tr("Die Formabweichung konnte nicht vollständig eingegrenzt werden."),
        "unexplained": tr("Einige erkannte Formen fehlen im Nachbau."),
    }
    return reasons.get(
        candidate.check.reason, tr("Dieser Nachbau hat die Formprüfung nicht bestanden.")
    )


class RebuildDialog(QDialog):
    """Grenzen, Kandidaten und konkrete Folgen vor genau einer Transaktion."""

    previewRequested = Signal(object)

    def __init__(self, session: Any, object_id: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Modell nachbauen"))
        self.resize(560, 620)
        self.session, self.object_id = session, object_id
        self.project = session.project
        self.snapshot = deepcopy(session.project)
        self.profile = session.evaluation_profile
        self.base_dir = session.base_dir
        self.proposal: RebuildProposal | None = None
        self.application: RebuildApplication | None = None
        self._worker: _RebuildWorker | None = None
        self._closed = False
        self._seen = False
        self._leash = WorkerLeash(self)
        self._height = ContentHeight()
        session.projectChanged.connect(self._invalidate)
        session.sceneChanged.connect(self._invalidate)

        content = QWidget(self)
        layout = QVBoxLayout(content)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(NORMAL)
        self.intro = QLabel(
            tr(
                "Der Nachbau erhält änderbare Maße. "
                "Die ursprünglichen Quelldaten bleiben erhalten; "
                "Strg+Z stellt das Modell wieder her."
            ),
            content,
        )
        self.intro.setWordWrap(True)
        self.intro.setTextFormat(Qt.TextFormat.PlainText)
        current = getattr(session, "last_result", None)
        if current is not None and object_id in current.scene.objects:
            name = str(current.scene.objects[object_id].name)
            self.intro.setText(
                tr("Nachbau prüfen für {name}. Die Maße werden anschließend änderbar.").format(
                    name=name
                )
                + "\n"
                + self.intro.text()
            )
        layout.addWidget(self.intro)
        form = QFormLayout()
        self.local_limit = BoundedLengthSpin(content)
        self.local_limit.set_range_mm(0.01, 1000.0)
        self.local_limit.set_value_mm(0.1)
        self.volume_limit = BoundedSpin(content)
        self.volume_limit.setRange(0.001, 99.999)
        self.volume_limit.setDecimals(3)
        self.volume_limit.setValue(1.0)
        self.volume_limit.setSuffix(tr(" %"))
        for title, editor in (
            (tr("Maximale Formabweichung"), self.local_limit),
            (tr("Maximale Volumenabweichung"), self.volume_limit),
        ):
            label = QLabel(title, content)
            label.setBuddy(editor)
            editor.setAccessibleName(title)
            note = tr(
                "Ihre Grenze für den Vergleich mit dem ursprünglichen Modell. "
                "Fertigungsspiel wird nicht eingerechnet."
            )
            for widget in (label, editor):
                widget.setToolTip(note)
                widget.setAccessibleDescription(note)
            wheel_needs_focus(editor)
            form.addRow(label, editor)
            editor.valueChanged.connect(self._limits_changed)
            editor.valueRefused.connect(self._limits_changed)
        layout.addLayout(form)
        self.start = QPushButton(tr("Nachbau prüfen"), content)
        self.start.clicked.connect(self._start)
        layout.addWidget(self.start)
        self.progress = QProgressBar(content)
        self.progress.setRange(0, 0)
        # Die Zahl stünde über der laufenden Füllung; der Stand steht darunter im Text.
        self.progress.setTextVisible(False)
        self.progress.hide()
        layout.addWidget(self.progress)
        self.status = QLabel("", content)
        self.status.setWordWrap(True)
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.status)
        self.candidates = QListWidget(content)
        self.candidates.setAccessibleName(tr("Nachbauvorschläge"))
        self.candidates.currentRowChanged.connect(self._choose)
        self.candidates.hide()
        layout.addWidget(self.candidates)
        self.details = QLabel("", content)
        self.details.setWordWrap(True)
        self.details.setTextFormat(Qt.TextFormat.PlainText)
        self.details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.details)
        self.original = QCheckBox(tr("Ursprüngliches Modell anzeigen"), content)
        self.original.toggled.connect(self._preview)
        self.original.hide()
        layout.addWidget(self.original)
        self.losses = QLabel("", content)
        self.losses.setWordWrap(True)
        self.losses.setTextFormat(Qt.TextFormat.PlainText)
        layout.addWidget(self.losses)
        self.accept_losses = QCheckBox(tr("Ich übernehme den Nachbau mit diesen Folgen."), content)
        self.accept_losses.toggled.connect(self._update_ready)
        self.accept_losses.hide()
        layout.addWidget(self.accept_losses)
        self._scroll = DialogScrollArea(self)
        self._scroll.setWidget(content)
        self._scroll.contentSizeChanged.connect(self._fit)
        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        self.take = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.take.setText(tr("Nachbau übernehmen"))
        make_primary(self.take)
        self.take.setEnabled(False)
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(WIDE, WIDE, WIDE, WIDE)
        outer.addWidget(self._scroll, 1)
        outer.addWidget(self.buttons)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802
        super().showEvent(event)
        QTimer.singleShot(0, self, weak_slot(self, RebuildDialog._fit))

    def _fit(self) -> None:
        self._height.fit(self, self._scroll, intent="passive")

    def _stop(self) -> None:
        worker, self._worker = self._worker, None
        if worker is not None:
            worker.cancel.cancel()
        self.progress.hide()

    def _limits_changed(self) -> None:
        self._stop()
        self.application = self.proposal = None
        self.candidates.clear()
        self.candidates.hide()
        self.details.clear()
        self.losses.clear()
        self.accept_losses.hide()
        self.accept_losses.setChecked(False)
        self.original.hide()
        self.previewRequested.emit(None)
        self._seen = False
        refusal = self.local_limit.refusal() or self.volume_limit.refusal()
        self.start.setEnabled(not refusal)
        self.status.setText(refusal)
        self._update_ready()

    def _start(self) -> None:
        self.local_limit.interpretText()
        self.volume_limit.interpretText()
        self._limits_changed()
        if not self.start.isEnabled():
            return
        self.status.setText(tr("Das Modell wird geprüft. Sie können jederzeit abbrechen."))
        budget = RebuildBudget(self.local_limit.value_mm(), self.volume_limit.value() / 100.0)
        self._launch(
            _RebuildWorker(self.snapshot, self.base_dir, self.profile, self.object_id, budget)
        )

    def _launch(self, worker: _RebuildWorker) -> None:
        self._stop()
        self._worker = worker
        self.progress.show()
        self.start.setEnabled(False)
        worker.completed.connect(self._completed)
        worker.failed.connect(self._failed)
        worker.crashed.connect(self._crashed)
        worker.progressed.connect(self._progressed)
        self._leash.start(worker)

    def _progressed(self, _share: float, note: str) -> None:
        if self.sender() is self._worker and not self._closed:
            self.status.setText(note)

    def _completed(self, result: Any) -> None:
        if self.sender() is not self._worker or self._closed:
            return
        self._worker = None
        self.progress.hide()
        self.start.setEnabled(True)
        if isinstance(result, RebuildProposal):
            self.proposal = result
            with QSignalBlocker(self.candidates):
                for index, candidate in enumerate(result.candidates, 1):
                    self.candidates.addItem(
                        tr("Vorschlag {number}: {state}").format(
                            number=index, state=check_text(candidate)
                        )
                    )
            self.candidates.setVisible(bool(result.candidates))
            self.status.setText(
                tr("Wählen Sie einen Vorschlag und vergleichen Sie die Formen.")
                if result.accepted
                else tr(
                    "Kein Vorschlag besteht Ihre Grenzen. Behalten Sie das ursprüngliche Modell "
                    "oder ändern Sie die Grenzen bewusst."
                )
            )
            if result.failures:
                self.status.setText(
                    self.status.text()
                    + "\n"
                    + "\n".join(str(finding.message) for finding in result.failures)
                )
            if result.candidates:
                selected = next(
                    (i for i, item in enumerate(result.candidates) if item.check.accepted), 0
                )
                self.candidates.setCurrentRow(selected)
        else:
            self.application = result
            self.losses.setText("\n".join(str(loss) for loss in result.losses))
            self.accept_losses.setChecked(False)
            self.accept_losses.setVisible(bool(result.losses))
            self.original.setChecked(False)
            self.original.show()
            self.status.setText(tr("Vergleichen Sie den Nachbau mit dem ursprünglichen Modell."))
            self._preview()
        self._update_ready()

    def _choose(self, index: int) -> None:
        self._stop()
        self.start.setEnabled(True)
        self.application = None
        self._seen = False
        self.accept_losses.setChecked(False)
        self.accept_losses.hide()
        self.losses.clear()
        self.original.hide()
        self.previewRequested.emit(None)
        self._update_ready()
        proposal = self.proposal
        if proposal is None or not 0 <= index < len(proposal.candidates):
            return
        candidate = proposal.candidates[index]
        lines = [check_text(candidate)]
        check = candidate.check
        if math.isfinite(check.volume_relative):
            lines.append(
                tr("Volumenabweichung: {value} %").format(
                    value=localised(f"{100 * check.volume_relative:.3f}")
                )
            )
        if check.surface is not None:
            lines.append(
                tr("Formabweichung zwischen {lower} und {upper}; geprüfte Grenze {limit}.").format(
                    lower=length(check.surface.lower_mm),
                    upper=(
                        length(check.surface.upper_mm)
                        if math.isfinite(check.surface.upper_mm)
                        else tr("unbekannt")
                    ),
                    limit=length(check.surface.permitted_mm),
                )
            )
            lines.append(
                tr(
                    "Von Ihrer Formgrenze bleiben {value} für die Vernetzung des Nachbaus "
                    "reserviert. Die flachen Dreiecke des ursprünglichen Modells zählen zur "
                    "Abweichung."
                ).format(value=length(proposal.budget.tessellation_mm))
            )
        for draft in candidate.drafts:
            spec = REGISTRY.get(draft.op)
            lines.append(str(spec.title))
            fields = {field.name: field for field in spec.params.spec()}
            for key, value in draft.params.items():
                field = fields.get(key)
                if (
                    field is not None
                    and field.unit == "mm"
                    and isinstance(value, int | float)
                    and not isinstance(value, bool)
                ):
                    lines.append(
                        tr("{name}: {value}").format(name=str(field.title), value=length(value))
                    )
        self.details.setText("\n".join(lines))
        if candidate.check.accepted:
            self.status.setText(tr("Die Übernahme und ihre Folgen werden geprüft …"))
            self._launch(
                _RebuildWorker(
                    self.snapshot,
                    self.base_dir,
                    self.profile,
                    self.object_id,
                    proposal.budget,
                    proposal,
                    candidate,
                )
            )
        else:
            self.status.setText(
                tr(
                    "Dieser Vorschlag wird nicht übernommen. Wählen Sie einen anderen "
                    "oder behalten Sie das ursprüngliche Modell."
                )
            )

    def _preview(self) -> None:
        self.previewRequested.emit(
            None
            if self.original.isChecked() or self.application is None
            else self.application.result
        )

    def preview_ready(self) -> None:
        """Erst das tatsächlich dargestellte Ergebnis gibt die Übernahme frei."""
        if self.application is not None and not self.original.isChecked():
            self._seen = True
            self._update_ready()

    def preview_failed(self, detail: str) -> None:
        self._seen = False
        self.status.setText(problem_text(InternalError(detail=detail)))
        self._update_ready()

    def _update_ready(self) -> None:
        app = self.application
        self.take.setEnabled(
            not self._closed
            and self._worker is None
            and app is not None
            and self._seen
            and (not app.losses or self.accept_losses.isChecked())
        )

    def _failed(self, error: AppError) -> None:
        if self.sender() is not self._worker or self._closed:
            return
        self._stop()
        self.start.setEnabled(True)
        self.status.setText(problem_text(error))
        self._update_ready()

    def _crashed(self, detail: str) -> None:
        self._failed(InternalError(detail=detail))

    def _invalidate(self) -> None:
        self.reject()

    def accept(self) -> None:
        if self.take.isEnabled():
            super().accept()

    def done(self, result: int) -> None:
        if self._closed:
            return
        self._closed = True
        self._stop()
        self.session.projectChanged.disconnect(self._invalidate)
        self.session.sceneChanged.disconnect(self._invalidate)
        super().done(result)

    def release(self) -> None:
        if not self._closed:
            self.session.projectChanged.disconnect(self._invalidate)
            self.session.sceneChanged.disconnect(self._invalidate)
        self._closed = True
        self._stop()
        self._leash.wait_all(DIALOG_WAIT_MS)
