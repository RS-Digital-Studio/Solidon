"""The bridge between the headless core and the surface (Bauplan §7, §15.6).

Everything that computes runs in a worker thread with progress and a cancel
button; the window only reacts to signals. The core never learns that Qt exists —
``progress``, ``ask`` and ``cancelled`` arrive through the ``OpContext`` as they
do on the command line.

Two rules from §15.6 live here: one run per document, and a newer request
replaces a waiting one instead of queueing up behind it.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PySide6.QtCore import QCoreApplication, QObject, QThread, Signal

from app.core.errors import AppError, OperationCancelled
from app.core.knowledge import profiles
from app.core.log import get_logger
from app.core.scene import (
    CancelSignal,
    EvaluationResult,
    History,
    OperationDraft,
    ResultCache,
    orphans,
)
from app.core.scene.evaluate import evaluate
from app.core.scene.project import (
    Project,
    ProjectSources,
    embedded_source_path,
    load,
    new_project,
    save,
    write_autosave,
)
from app.core.types import Finding, Origin, Profile, Quality, Report, Source
from app.i18n import TranslatableText, tr

_log = get_logger(__name__)


@dataclass(slots=True)
class AskRequest:
    """A question travelling from the worker to the window and back.

    The worker blocks on ``answered`` while the window shows the dialog — which
    is what "the chain stops and asks" means in a threaded surface (§21.3).
    """

    question: str
    choices: list[str]
    answered: threading.Event = field(default_factory=threading.Event)
    answer: str | None = None

    def reply(self, answer: str | None) -> None:
        self.answer = answer
        self.answered.set()


class _EvaluationWorker(QThread):
    """One evaluation pass. Owns nothing, reports everything."""

    finishedWith = Signal(object)
    failedWith = Signal(object)
    cancelled = Signal()

    def __init__(self, session: Session) -> None:
        super().__init__()
        self._session = session

    def run(self) -> None:
        session = self._session
        try:
            result = session.run_evaluation()
            if session.pending_orphan_check and result.complete:
                # §21.3: every feature reference of an opened file is checked once,
                # here in the worker where asking may block without freezing the
                # window. A rewritten reference means the scene has to be built
                # again — with the answer in it, not around it.
                session.pending_orphan_check = False
                check = orphans.check(
                    session.project.document, result.scene, session.ask_from_worker
                )
                if check.changed:
                    result = session.run_evaluation()
                result = _with_findings(result, check.findings)
        except OperationCancelled:
            self.cancelled.emit()
        except AppError as error:
            self.failedWith.emit(error)
        else:
            self.finishedWith.emit(result)


def _with_findings(result: EvaluationResult, extra: list[Finding]) -> EvaluationResult:
    """Carry the check's findings into the report the window shows."""
    if not extra:
        return result
    scene = result.scene
    scene.report = Report((*scene.report.findings, *extra))
    return result


class Session(QObject):
    """Holds the open project and keeps the surface in step with it."""

    sceneChanged = Signal(object)
    """An evaluation finished — carries an ``EvaluationResult``."""
    progressChanged = Signal(float, str)
    busyChanged = Signal(bool)
    askRequested = Signal(object)
    """A question for the user — carries an ``AskRequest``."""
    projectChanged = Signal()
    """Stack, path or title changed; panels reload from the document."""
    failed = Signal(object)
    """An ``AppError`` the surface shows as a suggestion (§2.7)."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.project: Project = new_project(profiles.DEFAULT_PRINTER, profiles.DEFAULT_MATERIAL)
        self.history = History(self.project.document)
        self.cache = ResultCache()
        self.cancel_signal = CancelSignal()
        self.path: Path | None = None
        self.quality: Quality = "draft"
        """Draft while iterating; the export and the final report switch to fine (§31)."""
        self.last_result: EvaluationResult | None = None
        self.pending_orphan_check = False
        """Set when a file was opened: §21.3 checks its references once, not always."""
        self._worker: _EvaluationWorker | None = None
        self._rerun_pending = False
        self._dirty = False

    # --- state ------------------------------------------------------------------

    @property
    def profile(self) -> Profile:
        document = self.project.document
        return profiles.make_profile(
            document.printer or profiles.DEFAULT_PRINTER,
            document.material or profiles.DEFAULT_MATERIAL,
        )

    @property
    def base_dir(self) -> Path | None:
        return self.path.parent if self.path else None

    @property
    def modified(self) -> bool:
        return self._dirty

    @property
    def title(self) -> str:
        name = self.path.name if self.path else tr("Unbenannt")
        return f"{name}*" if self._dirty else name

    # --- documents --------------------------------------------------------------

    def start_new(self, printer: str = "", material: str = "") -> None:
        self.project = new_project(
            printer or profiles.DEFAULT_PRINTER, material or profiles.DEFAULT_MATERIAL
        )
        self._reset_for(None)

    def open_project(self, path: Path) -> None:
        self.project = load(path)
        self.pending_orphan_check = True
        self._reset_for(path)

    def save_project(self, path: Path | None = None) -> Path:
        target = path or self.path
        if target is None:
            raise AppError(tr("Für dieses Projekt gibt es noch keinen Dateinamen."))
        save(self.project, target)
        self.path = target
        self._dirty = False
        self.projectChanged.emit()
        return target

    def autosave(self) -> None:
        """Crash recovery container next to the project (§38)."""
        if self._dirty:
            write_autosave(self.project, self.path)

    def _reset_for(self, path: Path | None) -> None:
        self.history = History(self.project.document)
        self.cache.clear()
        self.path = path
        self._dirty = False
        self.last_result = None
        self.projectChanged.emit()
        self.evaluate_async()

    # --- editing ----------------------------------------------------------------

    def apply(
        self,
        title: TranslatableText | str,
        drafts: list[OperationDraft],
        origin: Origin | None = None,
    ) -> None:
        """One transaction, then a fresh evaluation (§15.5)."""
        try:
            self.history.apply(title, drafts, origin or Origin(by="user"))
        except AppError as error:
            self.failed.emit(error)
            return
        self._dirty = True
        self.projectChanged.emit()
        self.evaluate_async()

    def import_model(self, path: Path, unit: str = "auto") -> None:
        """Embed a file and put a ``load`` operation on the stack (§17.1)."""
        document = self.project.document
        source_id = f"src_{len(document.sources) + 1}"
        document.sources[source_id] = Source(
            id=source_id, kind="import", path=embedded_source_path(path.name), sha256=""
        )
        self.project.sources[source_id] = path.read_bytes()
        self.apply(
            tr("Modell laden"),
            [OperationDraft(op="load", params={"source": source_id, "unit": unit})],
        )

    def undo(self) -> None:
        if self.history.undo() is not None:
            self._dirty = True
            self.projectChanged.emit()
            self.evaluate_async()

    def redo(self) -> None:
        if self.history.redo() is not None:
            self._dirty = True
            self.projectChanged.emit()
            self.evaluate_async()

    # --- evaluation -------------------------------------------------------------

    def evaluate_async(self) -> None:
        """One run per document; a newer request replaces a waiting one (§15.6)."""
        if self._worker is not None and self._worker.isRunning():
            self._rerun_pending = True
            self.cancel_signal.cancel()
            return
        self.cancel_signal.reset()
        self.busyChanged.emit(True)
        worker = _EvaluationWorker(self)
        worker.finishedWith.connect(self._on_finished)
        worker.failedWith.connect(self._on_failed)
        worker.cancelled.connect(self._on_cancelled)
        worker.finished.connect(self._on_thread_done)
        self._worker = worker
        worker.start()

    def run_evaluation(self, quality: Quality | None = None) -> EvaluationResult:
        """One pass with everything the core needs. No signals, no state."""
        return evaluate(
            self.project.document,
            self.profile,
            quality=quality or self.quality,
            progress=self.report_progress,
            ask=self.ask_from_worker,
            cancelled=self.cancel_signal,
            cache=self.cache,
            sources=ProjectSources(self.project, base_dir=self.base_dir),
        )

    def evaluate_now(self) -> EvaluationResult:
        """Synchronous pass, for the command line, tests and export (§31, fine)."""
        self.cancel_signal.reset()
        result = self.run_evaluation("fine")
        self.last_result = result
        self.sceneChanged.emit(result)
        return result

    def cancel(self) -> None:
        self.cancel_signal.cancel()

    # --- context callbacks ------------------------------------------------------

    def report_progress(self, fraction: float, text: str) -> None:
        self.progressChanged.emit(fraction, text)

    def ask_from_worker(self, question: str, choices: list[str]) -> str:
        """Hand the question to the window and wait for the answer."""
        request = AskRequest(question=question, choices=list(choices))
        self.askRequested.emit(request)
        request.answered.wait()
        if request.answer is None:
            raise OperationCancelled
        return request.answer

    # --- worker replies ---------------------------------------------------------

    def _on_finished(self, result: Any) -> None:
        self.last_result = result
        # §17.2: keep the fallback stage that carried each operation, so the file
        # recomputes the same way tomorrow.
        self.history.record_solvers(result.solvers)
        self.sceneChanged.emit(result)

    def _on_failed(self, error: Any) -> None:
        _log.warning("evaluation failed: %s", error)
        self.failed.emit(error)

    def _on_cancelled(self) -> None:
        _log.info("evaluation cancelled")

    def _on_thread_done(self) -> None:
        self.busyChanged.emit(False)
        self._worker = None
        if self._rerun_pending:
            self._rerun_pending = False
            self.evaluate_async()

    def wait_for_idle(self, timeout_ms: int = 10_000) -> None:
        """Block until no run is left — including the one a debounce queued up.

        Worker replies arrive as signals, so the event loop has to keep turning
        while waiting; otherwise the queued run would never start.
        """
        deadline = time.monotonic() + timeout_ms / 1000.0
        while time.monotonic() < deadline:
            worker = self._worker
            if worker is None:
                break
            worker.wait(50)
            application = QCoreApplication.instance()
            if application is not None:
                application.processEvents()
