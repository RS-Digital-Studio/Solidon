"""Lokale Merkmale erkunden und gemeinsam mit ihrer Bearbeitung übernehmen."""

from __future__ import annotations

import copy
import secrets
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.errors import (
    CORRECT_INPUT,
    RETRY,
    AppError,
    InternalError,
    OperationCancelled,
    UserError,
)
from app.core.expressions import resolve_params
from app.core.geom.mesh import MeshData
from app.core.geom.section import SectionPlane
from app.core.perceive.actions import FeatureAction, actions_for
from app.core.perceive.local import features_in_region, local_error
from app.core.perceive.ops import DetectRegionParams
from app.core.registry import REGISTRY
from app.core.scene import EvaluationResult, History, OperationDraft, evaluate
from app.core.scene.cache import ResultCache
from app.core.scene.cancel import CancelSignal
from app.core.scene.placement import original_surface_hit
from app.core.types import Document, Finding, Profile, Scene, SourceAccess, Vec3
from app.i18n import tr
from app.ui.dialogs import AskDialog, ErrorNotice
from app.ui.labels import feature_label
from app.ui.leash import DIALOG_WAIT_MS, WAIT_TIMEOUT_MS, Worker, WorkerLeash, weak_slot
from app.ui.op_dialog import OperationDialog, ValueField
from app.ui.session import AskRequest
from app.ui.style import NORMAL, ROOMY, make_primary, no_primary


@dataclass(frozen=True, slots=True)
class LocalRecognitionResult:
    """Nur Ansichtsdaten; der gespeicherte Auftrag entsteht erst beim Übernehmen."""

    evaluation: EvaluationResult
    detect_draft: OperationDraft
    object_id: str
    features: tuple[str, ...]
    actions: Mapping[str, tuple[FeatureAction, ...]]
    selected: str = ""


class _RecognitionWorker(Worker):
    """Erkennung und Handlungsauskunft am festen Dokumentstand, abseits von Qt."""

    ready = Signal(int, object)
    failed = Signal(int, object)
    aborted = Signal(int)
    progressed = Signal(int, float, str)
    askRequested = Signal(int, object)

    def __init__(
        self,
        document: Document,
        draft: OperationDraft,
        profile: Profile,
        revision: int,
        sources: SourceAccess | None,
        cache: ResultCache | None,
        mesh: MeshData | None = None,
        original_ray: tuple[Vec3, Vec3] | None = None,
        clip_planes: tuple[SectionPlane, ...] = (),
    ) -> None:
        super().__init__()
        self.document, self.draft, self.profile = document, draft, profile
        self.revision, self.sources, self.cache = revision, sources, cache
        self.mesh, self.original_ray, self.clip_planes = mesh, original_ray, clip_planes
        self.cancelled = CancelSignal()

    def _ask(self, question: str, choices: list[str]) -> str:
        """Der vorhandene Fragevertrag wartet abbrechbar auf den Qt-Dialog."""
        request = AskRequest(question, list(choices))
        self.askRequested.emit(self.revision, request)
        while not request.answered.wait(0.05):
            self.cancelled.raise_if_cancelled()
        self.cancelled.raise_if_cancelled()
        if request.answer is None:
            raise OperationCancelled
        return request.answer

    def work(self) -> None:
        try:
            self.cancelled.raise_if_cancelled()
            document = copy.deepcopy(self.document)
            draft = self.draft
            if self.original_ray is not None:
                if self.mesh is None:
                    raise local_error("seed")
                hit = original_surface_hit(
                    self.mesh,
                    *self.original_ray,
                    clip_planes=self.clip_planes,
                    check_cancelled=self.cancelled.raise_if_cancelled,
                )
                if hit is None:
                    raise local_error("seed")
                seed, point = hit
                normal = tuple(float(value) for value in self.mesh.raw.face_normals[seed])
                self.cancelled.raise_if_cancelled()
                draft = replace(
                    draft,
                    params={
                        **draft.params,
                        "seed_face": seed,
                        **dict(
                            zip(("x", "y", "z", "nx", "ny", "nz"), (*point, *normal), strict=True)
                        ),
                    },
                )
            transaction = History(document).apply(
                tr("Merkmale an dieser Stelle erkennen"), (draft,)
            )
            result = evaluate(
                document,
                self.profile,
                quality="fine",
                sources=self.sources,
                cache=self.cache,
                cancelled=self.cancelled,
                ask=self._ask,
                progress=lambda fraction, text: self.progressed.emit(self.revision, fraction, text),
            )
            self.cancelled.raise_if_cancelled()
            if not result.complete:
                problems = [
                    finding
                    for finding in result.scene.report.findings
                    if finding.severity == "error"
                ]
                if problems:
                    finding = problems[-1]
                    raise UserError(
                        finding.message, suggestions=finding.suggestions or (CORRECT_INPUT,)
                    )
                raise UserError(
                    tr("Die Erkennung konnte nicht abgeschlossen werden. Ändern Sie den Radius."),
                    suggestions=(CORRECT_INPUT,),
                )
            answered = result.answers.get(transaction.ops[-1], {})
            draft = replace(draft, params={**draft.params, **answered})
            entry = result.scene.objects[self.draft.inputs[0]]
            assert isinstance(entry.mesh, MeshData)
            values = {
                name: float(parameter.value) for name, parameter in result.scene.parameters.items()
            }
            params = DetectRegionParams(**resolve_params(draft.params, values))
            choices = features_in_region(
                entry.mesh,
                entry.features,
                (params.x, params.y, params.z),
                radius=params.radius,
                check_cancelled=self.cancelled.raise_if_cancelled,
            )
            actions = {}
            for name in choices:
                self.cancelled.raise_if_cancelled()
                actions[name] = tuple(
                    actions_for(
                        entry.features[name],
                        entry.features,
                        mesh=entry.mesh if isinstance(entry.mesh, MeshData) else None,
                    )
                )
            seed = int(draft.params.get("seed_face", -1))
            picked = [name for name in choices if seed in entry.features[name].face_indices]
            selected = picked[0] if len(picked) == 1 else choices[0] if len(choices) == 1 else ""
            self.cancelled.raise_if_cancelled()
            self.ready.emit(
                self.revision,
                LocalRecognitionResult(result, draft, entry.id, choices, actions, selected),
            )
        except OperationCancelled:
            self.aborted.emit(self.revision)
            return
        except AppError as error:
            self.failed.emit(self.revision, error.with_traceback(None))

    def release_finished_references(self) -> None:
        """Den festen Quellstand erst nach bestätigtem Threadende lösen."""
        del self.document, self.sources, self.cache, self.profile, self.mesh
        super().release_finished_references()


class LocalRecognitionDialog(QDialog):
    """Suche und Bearbeitung sammeln; ausschließlich der Besitzer schreibt die Transaktion."""

    recognitionReady = Signal(object)
    featureSelected = Signal(str)
    previewRequested = Signal(object)
    previewCleared = Signal()
    draftsReady = Signal(object)

    def __init__(
        self,
        document: Document,
        scene: Scene,
        object_id: str,
        profile: Profile,
        *,
        point: Vec3,
        normal: Vec3,
        seed_face: int = -1,
        radius: float = 10.0,
        sources: SourceAccess | None = None,
        cache: ResultCache | None = None,
        parent: QWidget | None = None,
        original_ray: tuple[Vec3, Vec3] | None = None,
        clip_planes: tuple[SectionPlane, ...] = (),
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(tr("Merkmale an dieser Stelle"))
        self.resize(460, 650)
        self._document, self._profile = copy.deepcopy(document), copy.deepcopy(profile)
        self._sources, self._cache, self._object_id = sources, cache, object_id
        source_mesh = scene.objects[object_id].mesh
        self._mesh = source_mesh if isinstance(source_mesh, MeshData) else None
        self._original_ray, self._clip_planes = original_ray, tuple(clip_planes)
        self._objects = {name: str(entry.name) for name, entry in scene.objects.items()}
        self._parameters = {
            name: float(parameter.value) for name, parameter in scene.parameters.items()
        }
        self._place = dict(zip(("x", "y", "z", "nx", "ny", "nz"), (*point, *normal), strict=True))
        self._place["seed_face"] = seed_face
        self._closed, self._pending = False, False
        self._revision, self._ready_revision = 0, -1
        self._worker: _RecognitionWorker | None = None
        self._leash = WorkerLeash(self)
        self.inspection: LocalRecognitionResult | None = None
        self.editor: OperationDialog | None = None
        self.edit_notice: ErrorNotice | None = None
        self._question: AskDialog | None = None
        self._request: AskRequest | None = None
        self.preview_revision = 0
        self._preview_valid = False
        self._last_drafts: tuple[OperationDraft, ...] = ()
        self._edit_seed: int | None = None
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.setInterval(150)
        self._timer.timeout.connect(self._search)
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.setInterval(150)
        self._preview_timer.timeout.connect(self._send_preview)
        self._wait_timer = QTimer(self)
        self._wait_timer.setSingleShot(True)
        self._wait_timer.setInterval(200)
        self._wait_timer.timeout.connect(self._show_wait)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(ROOMY, ROOMY, ROOMY, ROOMY)
        layout.setSpacing(NORMAL)
        heading = QLabel(
            tr("Vergrößern Sie den Radius, bis das gewünschte Merkmal vollständig erfasst ist."),
            self,
        )
        heading.setWordWrap(True)
        layout.addWidget(heading)
        form = QFormLayout()
        radius_spec = next(entry for entry in DetectRegionParams.spec() if entry.name == "radius")
        self.radius = ValueField(radius_spec, radius, self._parameters, self)
        self.radius.setAccessibleName(str(radius_spec.title))
        form.addRow(str(radius_spec.title), self.radius)
        layout.addLayout(form)
        self.state = ErrorNotice(self)
        layout.addWidget(self.state)
        self.progress = QProgressBar(self)
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setAccessibleName(tr("Merkmale erkennen"))
        self.progress.hide()
        layout.addWidget(self.progress)
        label = QLabel(tr("Vollständige Merkmale"), self)
        self.features = QListWidget(self)
        self.features.setAccessibleName(label.text())
        label.setBuddy(self.features)
        layout.addWidget(label)
        layout.addWidget(self.features, 1)
        self.selection = QLabel(tr("Kein Merkmal ausgewählt."), self)
        self.selection.setWordWrap(True)
        layout.addWidget(self.selection)
        self.action_box = QComboBox(self)
        self.action_box.setAccessibleName(tr("Merkmal bearbeiten"))
        layout.addWidget(self.action_box)
        self.action_note = QLabel(self)
        self.action_note.setWordWrap(True)
        layout.addWidget(self.action_note)
        self.edit_button = QPushButton(tr("Merkmal bearbeiten …"), self)
        make_primary(self.edit_button)
        layout.addWidget(self.edit_button)
        buttons = QDialogButtonBox(self)
        self.save_button = buttons.addButton(
            tr("Nur Merkmale übernehmen"), QDialogButtonBox.ButtonRole.ActionRole
        )
        no_primary(self.save_button)
        cancel = buttons.addButton(tr("Abbrechen"), QDialogButtonBox.ButtonRole.RejectRole)
        no_primary(cancel)
        layout.addWidget(buttons)
        self.radius.changed.connect(self._changed)
        self.features.currentItemChanged.connect(self._selected)
        self.action_box.currentIndexChanged.connect(self._action_selected)
        self.edit_button.clicked.connect(self._edit)
        self.save_button.clicked.connect(self._save_detection)
        buttons.rejected.connect(self.reject)
        self._changed()

    def _changed(self) -> None:
        """Eine neue Suche entwertet die sichtbare Auswahl noch vor dem Debounce."""
        if self._closed:
            return
        self._revision += 1
        self._pending = True
        self._ready_revision = -1
        self.inspection = None
        self.save_button.setEnabled(False)
        self.edit_button.setEnabled(False)
        self.features.clear()
        self.action_box.clear()
        self.selection.setText(tr("Kein Merkmal ausgewählt."))
        self._close_edit()
        self.featureSelected.emit("")
        self.previewCleared.emit()
        self.state.setText(tr("Merkmale werden erkannt …"))
        if self._worker is not None:
            self._worker.cancelled.cancel()
        self._close_question()
        self._timer.start()
        self._wait_timer.start()

    def _search(self) -> None:
        if self._closed or not self._pending or self._worker is not None:
            return
        self._pending = False
        draft = OperationDraft(
            "detect_region", (self._object_id,), {**self._place, "radius": self.radius.value()}
        )
        worker = _RecognitionWorker(
            self._document,
            draft,
            self._profile,
            self._revision,
            self._sources,
            self._cache,
            self._mesh,
            self._original_ray,
            self._clip_planes,
        )
        worker.ready.connect(self._ready)
        worker.failed.connect(self._failed)
        worker.aborted.connect(self._aborted)
        worker.progressed.connect(self._progressed)
        worker.askRequested.connect(self._ask)
        worker.crashed.connect(self._crashed)
        worker.finished.connect(self._finished)
        self._worker = worker
        self._leash.start(worker)

    def _show_wait(self) -> None:
        if not self._closed and (self._pending or self._worker is not None):
            self.progress.show()

    def _progressed(self, revision: int, _fraction: float, message: str) -> None:
        if not self._closed and revision == self._revision:
            self.state.setText(message)

    def _ready(self, revision: int, result: LocalRecognitionResult) -> None:
        if self._closed or revision != self._revision:
            return
        self.inspection, self._ready_revision = result, revision
        for name in self._place:
            self._place[name] = result.detect_draft.params[name]
        self._original_ray = None
        self._wait_timer.stop()
        self.progress.hide()
        self.recognitionReady.emit(result)
        entry = result.evaluation.scene.objects[result.object_id]
        chosen: QListWidgetItem | None = None
        for identifier in result.features:
            item = QListWidgetItem(
                feature_label(identifier, entry.features[identifier]), self.features
            )
            item.setData(Qt.ItemDataRole.UserRole, identifier)
            if identifier == result.selected:
                chosen = item
        if chosen is not None:
            self.features.setCurrentItem(chosen)
        else:
            self.features.setCurrentRow(-1)
        self.save_button.setEnabled(bool(result.features))
        self.state.setText(
            tr("{count} vollständige Merkmale gefunden.").format(count=len(result.features))
        )

    def _selected(self, item: QListWidgetItem | None, _old: QListWidgetItem | None) -> None:
        self._close_edit()
        self.action_box.clear()
        ready = self.inspection
        if self._closed or ready is None or item is None:
            self.selection.setText(tr("Kein Merkmal ausgewählt."))
            self.edit_button.setEnabled(False)
            self.featureSelected.emit("")
            return
        identifier = str(item.data(Qt.ItemDataRole.UserRole))
        self.selection.setText(tr("Ausgewählt: {feature}").format(feature=item.text()))
        self.featureSelected.emit(identifier)
        for action in ready.actions.get(identifier, ()):
            if action.op is not None and action.step is None:
                self.action_box.addItem(str(action.title), action)
        self._action_selected()

    def _action_selected(self, _index: int = -1) -> None:
        action = self.action_box.currentData()
        enabled = isinstance(action, FeatureAction) and action.op is not None and not self._closed
        self.edit_button.setEnabled(enabled)
        self.action_note.setText(
            str(action.note)
            if enabled
            else tr("Für dieses Merkmal ist keine Bearbeitung verfügbar.")
        )

    def _edit(self) -> None:
        ready, item, action = (
            self.inspection,
            self.features.currentItem(),
            self.action_box.currentData(),
        )
        if (
            self._closed
            or ready is None
            or item is None
            or self._ready_revision != self._revision
            or not isinstance(action, FeatureAction)
            or action.op is None
        ):
            return
        self._close_edit()
        identifier = str(item.data(Qt.ItemDataRole.UserRole))
        spec = REGISTRY.get(action.op)
        values = {
            entry.name: entry.value * entry.parameter_factor
            if isinstance(entry.value, (int, float)) and not isinstance(entry.value, bool)
            else entry.value
            for entry in action.fields
        }
        values.update(action.fixed)
        values["at_feature"] = identifier
        entry = ready.evaluation.scene.objects[ready.object_id]
        self._edit_seed = secrets.randbelow(2**31) if spec.requires_seed else None
        self.editor = OperationDialog(
            spec,
            self._objects,
            self,
            values=values,
            parameter_values=self._parameters,
            features={
                name: feature_label(name, feature) for name, feature in entry.features.items()
            },
            note=self.selection.text(),
            slots=entry.material_slots,
            source_objects=(ready.object_id,),
        )
        self.edit_notice = ErrorNotice(self.editor)
        editor_layout = self.editor.layout()
        assert isinstance(editor_layout, QVBoxLayout)
        editor_layout.insertWidget(0, self.edit_notice)
        self.editor.valuesChanged.connect(self._edit_changed)
        self.editor.accepted.connect(self._edit_accepted)
        self.editor.rejected.connect(self._edit_rejected)
        self.editor.show()
        self._edit_changed()

    def _edit_changed(self) -> None:
        if self._closed or self.editor is None or self.inspection is None:
            return
        self.preview_revision += 1
        self._preview_valid = False
        message = tr("Vorschau wird berechnet …")
        self.editor.block_apply(message)
        if self.edit_notice is not None:
            self.edit_notice.setText(message)
        self._last_drafts = (
            self.inspection.detect_draft,
            OperationDraft(
                self.editor.spec.name,
                (self._object_id,),
                self.editor.values(),
                seed=self._edit_seed,
            ),
        )
        self._preview_timer.start()

    def _send_preview(self) -> None:
        if not self._closed and self.editor is not None and self._last_drafts:
            self.previewRequested.emit(self._last_drafts)

    def preview_status(
        self,
        error: AppError | str | None = None,
        findings: Sequence[Finding] = (),
        *,
        revision: int | None = None,
    ) -> None:
        """Nur die aktuelle Vorschau darf freigeben; Warnungen bleiben davor sichtbar."""
        if (
            self._closed
            or self.editor is None
            or self.edit_notice is None
            or (revision is not None and revision != self.preview_revision)
        ):
            return
        errors = [finding for finding in findings if finding.severity == "error"]
        reason = str(error) if error is not None else str(errors[0].message) if errors else None
        self._preview_valid = reason is None
        self.editor.block_apply(reason)
        if isinstance(error, AppError):
            self.edit_notice.set_error(error)
        else:
            lines = [reason] if reason else []
            lines.extend(
                tr("Warnung: {message}").format(message=str(finding.message))
                for finding in findings
                if finding.severity == "warning"
            )
            self.edit_notice.setText(
                "\n".join(lines) if lines else tr("Die Vorschau zeigt das Ergebnis.")
            )

    def _edit_accepted(self) -> None:
        if (
            self._closed
            or not self._preview_valid
            or self.inspection is None
            or self._ready_revision != self._revision
        ):
            return
        self.draftsReady.emit(self._last_drafts)
        super().accept()

    def _edit_rejected(self) -> None:
        self._close_edit()

    def _close_edit(self) -> None:
        self._preview_timer.stop()
        self.preview_revision += 1
        self._preview_valid = False
        self._last_drafts = ()
        editor, self.editor = self.editor, None
        self.edit_notice = None
        if editor is not None:
            editor.close()
            editor.deleteLater()
            self.previewCleared.emit()

    def _save_detection(self) -> None:
        if (
            not self._closed
            and self.inspection is not None
            and self._ready_revision == self._revision
            and self.save_button.isEnabled()
        ):
            self.draftsReady.emit((self.inspection.detect_draft,))
            super().accept()

    def _ask(self, revision: int, request: AskRequest) -> None:
        if self._closed or revision != self._revision:
            request.reply(None)
            return
        self._close_question()
        self._request = request
        self._question = AskDialog(request.question, request.choices, self)
        self._question.finished.connect(self._answered)
        self._question.open()

    def _answered(self, result: int) -> None:
        if self._request is not None and self._question is not None:
            self._request.reply(
                self._question.chosen() if result == QDialog.DialogCode.Accepted else None
            )
        question, self._question, self._request = self._question, None, None
        if question is not None:
            question.deleteLater()

    def _close_question(self) -> None:
        if self._request is not None:
            self._request.reply(None)
        question, self._question, self._request = self._question, None, None
        if question is not None:
            question.close()
            question.deleteLater()

    def _failed(self, revision: int, problem: object) -> None:
        if self._closed or revision != self._revision:
            return
        self._wait_timer.stop()
        self.progress.hide()
        self.state.set_error(
            problem, {"correct_input": weak_slot(self.radius, ValueField.setFocus)}
        )
        self.save_button.setEnabled(False)
        self.edit_button.setEnabled(False)

    def _aborted(self, revision: int) -> None:
        if not self._closed and revision == self._revision:
            self._wait_timer.stop()
            self.progress.hide()
            self.state.set_error(
                UserError(tr("Die lokale Erkennung wurde abgebrochen."), suggestions=(RETRY,)),
                {"retry": weak_slot(self, LocalRecognitionDialog._changed)},
            )

    def _crashed(self, detail: str) -> None:
        worker = self.sender()
        if isinstance(worker, _RecognitionWorker):
            self._failed(worker.revision, InternalError(detail=detail))

    def _finished(self) -> None:
        if self.sender() is self._worker:
            self._worker = None
        if not self._closed and self._pending:
            self._timer.start()

    def invalidate(self) -> None:
        """Projekt- oder Dokumentwechsel beendet den festen Suchstand."""
        self.reject()

    def done(self, result: int) -> None:
        self.release(DIALOG_WAIT_MS)
        super().done(result)

    def release(self, timeout_ms: int = WAIT_TIMEOUT_MS) -> None:
        """Abbrechen hält die Arbeiter bis zum wirklichen Ende an der gemeinsamen Leine."""
        self._closed = True
        self._revision += 1
        self._pending = False
        self._timer.stop()
        self._preview_timer.stop()
        self._wait_timer.stop()
        self.save_button.setEnabled(False)
        self.edit_button.setEnabled(False)
        self._close_edit()
        self._close_question()
        if self._worker is not None:
            self._worker.cancelled.cancel()
        self.previewCleared.emit()
        self._leash.wait_all(timeout_ms)
