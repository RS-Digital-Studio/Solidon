"""Die Brücke zwischen dem kopflosen Kern und der Oberfläche (Bauplan §7,
§15.6).

Alles, was rechnet, läuft in einem Arbeits-Thread mit Fortschritt und
Abbrechen-Knopf; das Fenster reagiert nur auf Signale. Der Kern erfährt nie,
dass es Qt gibt — ``progress``, ``ask`` und ``cancelled`` kommen über den
``OpContext`` an, wie auf der Kommandozeile.

Zwei Regeln aus §15.6 leben hier: ein Lauf je Dokument, und eine neuere
Anfrage ersetzt eine wartende, statt sich dahinter anzustellen.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from PySide6.QtCore import QCoreApplication, QObject, QThread, Signal

from app.core.agent import apply as agent_apply
from app.core.agent.proposal import Proposal
from app.core.agent.session import AgentSession
from app.core.backends.llm import LLMBackend, first_available
from app.core.backends.mesh import GeneratedMesh
from app.core.brep import step as brep_step
from app.core.errors import AppError, InternalError, OperationCancelled
from app.core.export import threemf
from app.core.generate import into_project as generate_into
from app.core.geom.difference import SceneDifference, compare_scenes
from app.core.geom.mesh import as_mesh_data
from app.core.ingest.outline import is_outline
from app.core.knowledge import profiles
from app.core.knowledge.parts import check as part_check
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
from app.core.split import SplitApplied, apply_split
from app.core.types import Finding, Origin, Profile, Quality, Report, Source
from app.i18n import TranslatableText, tr

_log = get_logger(__name__)


@dataclass(slots=True)
class AskRequest:
    """Eine Frage, die vom Arbeiter zum Fenster reist und zurück.

    Der Arbeiter blockiert an ``answered``, während das Fenster den Dialog
    zeigt — und genau das heißt „die Kette hält an und fragt" in einer
    threaded Oberfläche (§21.3).
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
            if session.pending_part_check:
                # §24.4: was die Bibliothek geändert hat, seit diese Datei gespeichert
                # wurde, wird einmal gesagt — beim Öffnen, nicht bei jeder
                # Auswertung.
                session.pending_part_check = False
                result = _with_findings(result, part_check.check(session.project.document))
            if session.pending_orphan_check and result.complete:
                # §21.3: jeder Merkmalsverweis einer geöffneten Datei wird einmal
                # geprüft, hier im Arbeiter, wo Fragen blockieren darf, ohne das
                # Fenster einzufrieren. Ein umgeschriebener Verweis heißt, dass die
                # Szene neu gebaut werden muss — mit der Antwort darin, nicht
                # darum herum.
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


@dataclass(slots=True)
class ProposalPreview:
    """Ein Vorschlag plus das, wonach er aussähe (§26.5, §18.7).

    Szene und Differenz werden im Arbeiter gerechnet, nicht im Fenster: eine
    Differenz sind zwei Boolesche Operationen je Körper, und das auf dem
    GUI-Thread zu tun fröre genau die Ansicht ein, die sie erklären soll.
    """

    proposal: Proposal
    scene: Any = None
    difference: SceneDifference | None = None

    @property
    def changes_geometry(self) -> bool:
        return bool(self.proposal.drafts)


class _AgentWorker(QThread):
    """Ein Zug des Agenten, abseits des GUI-Threads (§26.5)."""

    finishedWith = Signal(object)
    failedWith = Signal(object)

    def __init__(self, session: Session, request: str) -> None:
        super().__init__()
        self._session = session
        self._request = request

    def run(self) -> None:
        session = self._session
        try:
            preview = session.run_proposal(self._request)
        except OperationCancelled:
            self.failedWith.emit(AppError(tr("Der Vorschlag wurde abgebrochen.")))
        except AppError as error:
            self.failedWith.emit(error)
        else:
            self.finishedWith.emit(preview)


def _with_findings(result: EvaluationResult, extra: list[Finding]) -> EvaluationResult:
    """Trägt die Befunde der Prüfung in den Bericht, den das Fenster zeigt."""
    if not extra:
        return result
    scene = result.scene
    scene.report = Report((*scene.report.findings, *extra))
    return result


class Session(QObject):
    """Hält das offene Projekt und die Oberfläche im Gleichschritt mit ihm."""

    sceneChanged = Signal(object)
    """An evaluation finished — carries an ``EvaluationResult``."""
    progressChanged = Signal(float, str)
    busyChanged = Signal(bool)
    askRequested = Signal(object)
    """A question for the user — carries an ``AskRequest``."""
    proposalReady = Signal(object)
    """An agent turn finished — carries a ``ProposalPreview`` (§26.5)."""
    agentBusyChanged = Signal(bool)
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
        self.pending_part_check = False
        """The same for the part library (§24.4): once on opening, not on every run."""
        self._worker: _EvaluationWorker | None = None
        self._agent: _AgentWorker | None = None
        self._backend: LLMBackend | None = None
        self._selection: tuple[str, str] | None = None
        self._accepted: dict[str, str | None] = {}
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
        self.pending_part_check = True
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
        """Container zur Absturz-Wiederherstellung neben dem Projekt (§38)."""
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
        """Eine Transaktion, dann eine frische Auswertung (§15.5)."""
        try:
            self.history.apply(title, drafts, origin or Origin(by="user"))
        except AppError as error:
            self.failed.emit(error)
            return
        self._dirty = True
        self.projectChanged.emit()
        self.evaluate_async()

    def change_params(self, op_id: int, params: dict[str, Any]) -> None:
        """Andere Parameter für eine Operation, die schon im Stapel steht (§15.4)."""
        try:
            self.history.change_params(op_id, params)
        except AppError as error:
            self.failed.emit(error)
            return
        self._dirty = True
        self.projectChanged.emit()
        self.evaluate_async()

    def import_model(self, path: Path, unit: str = "auto") -> None:
        """Bettet eine Datei ein und legt die passende load-Operation auf den
        Stapel (§17.1).

        STEP nimmt den anderen Kern und trägt seine eigene Einheit — es braucht
        also weder die Einheitenfrage noch die Mesh-Eingangsstufe (§30, §11.1).
        """
        document = self.project.document
        source_id = f"src_{len(document.sources) + 1}"
        document.sources[source_id] = Source(
            id=source_id, kind="import", path=embedded_source_path(path.name), sha256=""
        )
        self.project.sources[source_id] = path.read_bytes()

        is_3mf = path.suffix.lower() == ".3mf"
        if brep_step.is_step(path.suffix):
            self.apply(
                tr("STEP laden"),
                [OperationDraft(op="load_step", params={"source": source_id})],
            )
            return
        if is_outline(path.suffix):
            # Eine flache Zeichnung hat auch keine Einheitenfrage — sie hat keine
            # dritte Dimension, bis jemand sagt, wie dick sie sein soll (§25).
            self.apply(
                tr("Zeichnung extrudieren"),
                [OperationDraft(op="load_outline", params={"source": source_id})],
            )
            return
        # Wie viele Körper die Datei hält, entscheidet sich hier, nicht in der
        # Operation: der Stapel vergibt Objekt-IDs, bevor irgendetwas läuft
        # (§11), und bei einer 3MF-Baugruppe steht die Zahl in der Datei.
        # Gezählt, ohne eine einzige Koordinate zu lesen.
        parts = threemf.count_objects(self.project.sources[source_id]) if is_3mf else 1
        self.apply(
            tr("Modell laden"),
            [
                OperationDraft(
                    op="load",
                    params={"source": source_id, "unit": unit},
                    produces=max(parts, 1),
                )
            ],
        )

    def add_generated(self, result: GeneratedMesh) -> str:
        """Weg 3: einen erzeugten Körper einbetten, laden, reparieren (§2.2).

        Die zwei Transaktionen entstehen im Kern; was hier passiert, ist das
        Neuzeichnen danach — genau wie bei einem Import.
        """
        generation = generate_into(self.project, result)
        self._dirty = True
        self.projectChanged.emit()
        self.evaluate_async()
        return generation.object_id

    def auto_split(self, object_id: str) -> SplitApplied:
        """§25: ein Teil schneiden, bis es passt, mit Stiften und
        Passungspaaren (§14).

        Die Suche braucht den ausgewerteten Körper, also wartet das hier auf den
        letzten Lauf, statt aus dem Stapel zu raten — eine Teilung eines
        veralteten Netzes legte die Trennebene dorthin, wo das Teil nicht mehr
        ist.
        """
        self.wait_for_idle()
        result = self.last_result
        entry = result.scene.objects.get(object_id) if result is not None else None
        if entry is None:
            raise InternalError(
                detail="auto split was asked for an object that is not in the scene",
                values={"object": object_id},
            )

        applied = apply_split(
            self.project.document, as_mesh_data(entry.mesh), object_id, self.profile
        )
        if applied.transaction is not None:
            self._dirty = True
            self.projectChanged.emit()
            self.evaluate_async()
        return applied

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
        """Ein Lauf je Dokument; eine neuere Anfrage ersetzt eine wartende (§15.6)."""
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
        """Ein Durchlauf mit allem, was der Kern braucht. Keine Signale, kein
        Zustand.
        """
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
        """Synchroner Durchlauf, für Kommandozeile, Tests und Export (§38)."""
        self.cancel_signal.reset()
        result = self.run_evaluation("fine")
        self.last_result = result
        self.sceneChanged.emit(result)
        return result

    def cancel(self) -> None:
        self.cancel_signal.cancel()

    # --- the agent (§26) --------------------------------------------------------

    @property
    def agent_backend(self) -> LLMBackend | None:
        """Das Modell, das der Chat benutzt, oder None — dann ist der Chat
        aus (§27).
        """
        if self._backend is None:
            self._backend = first_available()
        return self._backend

    def set_agent_backend(self, backend: LLMBackend | None) -> None:
        """Das Modell von Hand wählen — der Einstellungsdialog und die Suite tun
        das.
        """
        self._backend = backend

    def propose_async(self, request: str, selection: tuple[str, str] | None = None) -> None:
        """Fragt den Agenten. Die Antwort kommt als ``proposalReady`` an."""
        backend = self.agent_backend
        if backend is None:
            self.failed.emit(AppError(tr("Für den Chat fehlt der Zugang zu einem Sprachmodell.")))
            return
        if self._agent is not None and self._agent.isRunning():
            return
        self._selection = selection
        self.agentBusyChanged.emit(True)
        worker = _AgentWorker(self, request)
        worker.finishedWith.connect(self._on_proposal)
        worker.failedWith.connect(self._on_failed)
        worker.finished.connect(self._on_agent_done)
        self._agent = worker
        worker.start()

    def run_proposal(self, request: str) -> ProposalPreview:
        """Ein Agentenzug plus seine Vorschau. Läuft im Arbeiter (§26.5)."""
        backend = self.agent_backend
        if backend is None:  # pragma: no cover - vor dem Start des Arbeiters abgesichert
            raise AppError(tr("Für den Chat fehlt der Zugang zu einem Sprachmodell."))

        agent = AgentSession(
            backend=backend,
            document=self.project.document,
            profile=self.profile,
            sources=ProjectSources(self.project, base_dir=self.base_dir),
            ask=self.ask_from_worker,
            selection=self._selection,
        )
        proposal = agent.propose(request)
        preview = ProposalPreview(proposal=proposal)
        if proposal.drafts:
            preview.scene, preview.difference = self._preview_of(proposal)
        return preview

    def _preview_of(self, proposal: Proposal) -> tuple[Any, SceneDifference | None]:
        """Wonach die Szene aussähe — auf einer Kopie gerechnet, in
        Entwurfsqualität.
        """
        import copy

        before = self.last_result.scene if self.last_result else None
        working = copy.deepcopy(self.project.document)
        History(working).apply(tr("Vorschau"), proposal.drafts, origin=proposal.origin)
        result = evaluate(
            working,
            self.profile,
            quality="draft",
            sources=ProjectSources(self.project, base_dir=self.base_dir),
            ask=self.ask_from_worker,
        )
        difference = compare_scenes(before, result.scene) if before is not None else None
        return result.scene, difference

    def accept_proposal(self, preview: ProposalPreview) -> None:
        """Legt den Vorschlag als eine Transaktion ins Dokument (§26.5)."""
        transaction = agent_apply.accept(preview.proposal, self.history)
        self._accepted[preview.proposal.request] = transaction.id if transaction else None
        self._dirty = True
        self.projectChanged.emit()
        self.evaluate_async()

    def discard_proposal(self, preview: ProposalPreview) -> None:
        """Wirft ihn weg — das Gespräch behält beide Beiträge (§26.3)."""
        agent_apply.discard(preview.proposal, self.project.document)
        self._dirty = True
        self.projectChanged.emit()

    # --- context callbacks ------------------------------------------------------

    def report_progress(self, fraction: float, text: str) -> None:
        self.progressChanged.emit(fraction, text)

    def ask_from_worker(self, question: str, choices: list[str]) -> str:
        """Reicht die Frage ans Fenster und wartet auf die Antwort."""
        request = AskRequest(question=question, choices=list(choices))
        self.askRequested.emit(request)
        request.answered.wait()
        if request.answer is None:
            raise OperationCancelled
        return request.answer

    # --- worker replies ---------------------------------------------------------

    def _on_finished(self, result: Any) -> None:
        self.last_result = result
        # §17.2: die Rückfallstufe behalten, die jede Operation getragen hat —
        # damit die Datei morgen gleich nachrechnet.
        self.history.record_solvers(result.solvers)
        self.sceneChanged.emit(result)

    def _on_failed(self, error: Any) -> None:
        _log.warning("evaluation failed: %s", error)
        self.failed.emit(error)

    def _on_cancelled(self) -> None:
        _log.info("evaluation cancelled")

    def _on_proposal(self, preview: Any) -> None:
        self.proposalReady.emit(preview)

    def _on_agent_done(self) -> None:
        self.agentBusyChanged.emit(False)
        self._agent = None

    def _on_thread_done(self) -> None:
        self.busyChanged.emit(False)
        self._worker = None
        if self._rerun_pending:
            self._rerun_pending = False
            self.evaluate_async()

    def wait_for_idle(self, timeout_ms: int = 10_000) -> None:
        """Blockiert, bis kein Lauf mehr übrig ist — auch der nicht, den eine
        Entprellung eingereiht hat.
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
