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

from PySide6.QtCore import QCoreApplication, QEventLoop, QObject, QThread, Signal

from app.core.agent import apply as agent_apply
from app.core.agent.proposal import Proposal
from app.core.agent.session import AgentSession
from app.core.backends.llm import LLMBackend, first_available
from app.core.backends.mesh import GeneratedMesh
from app.core.brep import step as brep_step
from app.core.errors import AppError, InternalError, OperationCancelled, ValidationError
from app.core.export import threemf
from app.core.generate import into_project as generate_into
from app.core.geom.difference import SceneDifference, compare_scenes
from app.core.geom.mesh import as_mesh_data
from app.core.ingest.outline import is_outline
from app.core.knowledge import profiles
from app.core.knowledge.parts import check as part_check
from app.core.lid_flow import LidApplied, apply_lid
from app.core.log import get_logger
from app.core.scene import (
    CancelSignal,
    EvaluationResult,
    History,
    OperationDraft,
    ResultCache,
    expressions,
    foreign,
    orphans,
)
from app.core.scene.evaluate import evaluate
from app.core.scene.history import change_for
from app.core.scene.project import (
    Project,
    ProjectSources,
    clear_autosave,
    embedded_source_path,
    load,
    new_project,
    save,
    write_autosave,
)
from app.core.split import SplitApplied, apply_planned, apply_split, plan_split
from app.core.types import (
    Finding,
    Fit,
    Origin,
    Parameter,
    PrintSettings,
    Profile,
    Quality,
    Report,
    Source,
)
from app.core.units import is_close
from app.i18n import TranslatableText, _, tr

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
            # §32: was diese Datei außer Geometrie mitbringt, wird am Dokument
            # abgelesen — vor der Auswertung, damit der Hinweis nicht von dem
            # abhängt, was die Auswertung daraus macht.
            outside: list[Finding] = []
            if session.pending_foreign_check:
                session.pending_foreign_check = False
                outside = foreign.findings_for(session.project.document)

            result = session.run_evaluation()
            result = _with_findings(result, outside)
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


class _PreviewWorker(QThread):
    """Eine Dialog-Vorschau, abseits des GUI-Threads (§18.7, §2.8).

    Dieselbe Begründung wie beim Agentenvorschlag: die Differenz sind zwei
    Boolesche Operationen je Körper. ``generation`` stempelt das Ergebnis —
    wer weitertippt, ersetzt die Anfrage, und eine verspätete Antwort auf
    eine alte Frage wird verworfen statt gezeigt.
    """

    done = Signal(int, object)

    def __init__(self, session: Session, generation: int, compute: Any) -> None:
        super().__init__()
        self._session = session
        self._generation = generation
        self._compute = compute

    def run(self) -> None:
        try:
            _scene, difference = self._compute()
        except (AppError, OperationCancelled):
            # Beim Tippen entstehen ungültige Zwischenstände; der echte
            # Fehler kommt beim Anwenden als Vorschlag (§2.7). Die Vorschau
            # zeigt dann schlicht nichts Neues.
            self.done.emit(self._generation, None)
        else:
            self.done.emit(self._generation, difference)


class _SplitWorker(QThread):
    """Die Trennebenensuche, abseits des GUI-Threads (§2.8, §22.3).

    Sie schneidet jede Kandidatenebene durch das ganze Netz — Sekunden bis
    Minuten an einem großen Körper, und sie lief mit einem Wartezeiger im
    Hauptthread. Gerechnet wird hier nur der Plan; das Anwenden mutiert das
    Dokument und bleibt im Thread, dem das Dokument gehört.
    """

    done = Signal(object)
    failedWith = Signal(object)

    def __init__(self, mesh: Any, object_id: str, profile: Profile) -> None:
        super().__init__()
        self._mesh = mesh
        self._object_id = object_id
        self._profile = profile

    def run(self) -> None:
        try:
            self.done.emit(plan_split(self._mesh, self._object_id, self._profile))
        except AppError as error:
            self.failedWith.emit(error)


def _no_questions(question: str, choices: list[str]) -> str:
    """Die ask-Funktion der stillen Vorschau: sie fragt nicht, sie hält an.

    Eine Rückfrage mitten im Tippen wäre ein Fenster über einem Fenster —
    was eine Antwort braucht, bekommt sie beim Anwenden über den echten Weg."""
    raise OperationCancelled


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
    """Eine Frage an den Nutzer — trägt einen ``AskRequest``."""
    proposalReady = Signal(object)
    """An agent turn finished — carries a ``ProposalPreview`` (§26.5)."""
    agentProgress = Signal(int, str)
    """Was der laufende Zug gerade tut — Schritt und Beschriftung (§2.8).

    Emittiert aus dem Arbeiter-Thread; Qt stellt das als queued Signal im
    Hauptthread zu, wie bei ``progressChanged`` auch."""
    agentBusyChanged = Signal(bool)
    splitBusyChanged = Signal(bool)
    """Die Trennebenensuche läuft oder ist fertig (§2.8)."""
    projectChanged = Signal()
    """Stapel, Pfad oder Titel haben sich geändert; die Leisten laden neu."""
    failed = Signal(object)
    """An ``AppError`` the surface shows as a suggestion (§2.7)."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.project: Project = new_project(profiles.DEFAULT_PRINTER, profiles.DEFAULT_MATERIAL)
        self.history = History(self.project.document)
        self.cache = ResultCache()
        self.cancel_signal = CancelSignal()
        self.agent_cancel = CancelSignal()
        """Ein eigenes Signal für den Agentenzug: Auswertung und Agent laufen
        unabhängig, und ein abgebrochener Vorschlag darf keine laufende
        Berechnung mitreißen (§15.6)."""
        self.path: Path | None = None
        self.quality: Quality = "draft"
        """Entwurf, solange gearbeitet wird; Export und Abschlussbericht schalten
    auf fein (§31)."""
        self.last_result: EvaluationResult | None = None
        self.pending_orphan_check = False
        """Gesetzt, wenn eine Datei geöffnet wurde: §21.3 prüft ihre Verweise
    einmal, nicht immer."""
        self.pending_part_check = False
        """Dasselbe für die Bausteinbibliothek (§24.4): beim Öffnen, nicht bei
    jedem Lauf."""
        self.pending_foreign_check = False
        """Und dasselbe für das, was §32 den Warnhinweis nennt: Quelltext und
        Verweise nach außen werden beim Öffnen einmal gemeldet. Bei jeder
        Auswertung wäre es eine Zeile, die immer dasteht und die deshalb
        niemand mehr liest."""
        self._worker: _EvaluationWorker | None = None
        self._finished_worker: _EvaluationWorker | None = None
        """Der zuletzt ausgelaufene Auswertungs-Arbeiter, festgehalten bis ihn
        der nächste ablöst. ``_on_thread_done`` läuft als Slot seines eigenen
        ``finished``-Signals — die Referenz dort einfach zu überschreiben ließ
        den Wrapper mitsamt C++-Objekt sterben, während Qt die Zustellung noch
        auf dem Stapel hatte. Bei schnellen Ketten (ändern, Undo, Redo auf
        einem schweren Dokument) riss das die Suite Tests später ohne eine
        Zeile Traceback ab."""
        self._agent: _AgentWorker | None = None
        self._finished_agent: _AgentWorker | None = None
        """Derselbe Grund wie bei ``_finished_worker``: ``_on_agent_done``
        läuft als Slot des ``finished``-Signals seines eigenen Arbeiters, und
        die Referenz dort loszulassen nimmt den Wrapper mitsamt C++-QThread mit,
        während Qt die Zustellung noch auf dem Stapel hat. Beim Auswerter hat
        genau das die Suite ohne eine Zeile Traceback abgerissen; hier hämmerte
        bisher nur niemand darauf."""
        self._split: _SplitWorker | None = None
        self._finished_split: _SplitWorker | None = None
        """Und dasselbe für die Teilungssuche — sie ließ ihre Referenz sogar in
        einem Lambda am ``finished``-Signal los."""
        self._split_discarded = False
        """Ob das laufende Split-Ergebnis verworfen wurde — der Arbeiter
        läuft dann aus, ohne dass jemand sein Ergebnis anwendet."""
        self._previews: list[_PreviewWorker] = []
        """Jeder laufende Vorschau-Arbeiter, festgehalten bis ``finished``.

        Eine neuere Anfrage ersetzt die alte nur in der Anzeige — der alte
        Thread rechnet aus. Die Referenz zu überschreiben hieße, ein
        laufendes QThread-Objekt dem Speicherbereiniger zu überlassen, und
        der zerstört das C++-Objekt unter dem Thread: ein Absturz ohne
        Zeile, irgendwann später."""
        self._preview_generation = 0
        """Stempel der jüngsten Vorschau-Anfrage (§18.7) — eine verspätete
        Antwort auf eine ältere wird verworfen statt gezeigt."""
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
    def busy(self) -> bool:
        """True, solange eine Auswertung läuft — der Fortschritt gehört ihr."""
        return self._worker is not None and self._worker.isRunning()

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
        self.pending_foreign_check = True
        self._reset_for(path)

    def recover(self, path: Path) -> None:
        """Öffnet eine automatische Sicherung, ohne sie zum Projekt zu machen.

        Der Pfad bleibt leer: die Sicherung ist nicht die Datei, die der
        Nutzer pflegt, und ein „Speichern" darauf würde sie überschreiben,
        statt nach einem Namen zu fragen.
        """
        self.project = load(path)
        self.pending_orphan_check = True
        self.pending_part_check = True
        self.pending_foreign_check = True
        self._reset_for(None)
        self._dirty = True
        self.projectChanged.emit()

    def save_project(self, path: Path | None = None) -> Path:
        target = path or self.path
        if target is None:
            raise AppError(tr("Für dieses Projekt gibt es noch keinen Dateinamen."))
        # Die Sicherung des Zustands, der gerade gespeichert wird, hat sich
        # damit erledigt — auch die namenlose, aus der eine Wiederherstellung
        # kam (§38).
        clear_autosave(self.path)
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

    def change_parameter(self, name: str, value: float) -> None:
        """Eine gedrehte Zahl der Parameterleiste (§13, §15.5).

        Sie war lange keine Transaktion: die Leiste schrieb geradewegs ins
        Dokument. Damit war die Änderung weder rücknehmbar — ein Strg+Z nahm
        stattdessen die letzte Operation zurück — noch als Änderung erkennbar,
        und weil das Schließen nur sichert, was als geändert gilt, ging sie
        dabei verloren.
        """
        import dataclasses

        parameters = self.project.document.parameters
        existing = parameters.get(name)
        if existing is None or is_close(existing.value, value):
            return

        changed = dataclasses.replace(existing, value=value)
        try:
            self.history.apply(
                f"{tr('Parameter')} {name}",
                changes=change_for(self.project.document, parameters={name: changed}),
            )
        except AppError as error:
            self.failed.emit(error)
            return
        self._dirty = True
        self.projectChanged.emit()
        self.evaluate_async()

    def add_fit(self, fit: Fit) -> None:
        """Eine Passungsbeziehung ins Dokument (§14, §15.5).

        Wie ein Parameter reist sie als ``DocumentChange`` und ist damit
        rücknehmbar, zählt als Änderung und überlebt das Schließen. Bis hierher
        konnte sie nur der Agent anlegen — die Fernsteuerung bot das Werkzeug
        an und hatte niemanden, der es ausführt.
        """
        document = self.project.document
        if any(entry.name == fit.name for entry in document.fits):
            self.failed.emit(
                ValidationError(
                    field="name",
                    detail=tr("Diesen Namen gibt es schon."),
                    constraint="duplicate",
                    values={"name": fit.name},
                )
            )
            return
        try:
            self.history.apply(
                f"{tr('Passung')} {fit.name}",
                changes=change_for(document, fits=[*document.fits, fit]),
            )
        except AppError as error:
            self.failed.emit(error)
            return
        self._dirty = True
        self.projectChanged.emit()
        self.evaluate_async()

    def add_parameter(self, parameter: Parameter) -> None:
        """Ein neues Projektmaß von Hand (§13, §2.3, §15.5).

        Anlegen konnte bisher nur der Agent über sein Werkzeug — wer ohne
        Sprachmodell arbeitet, hatte kein Gegenstück, obwohl §2.3 verspricht,
        dass ohne KI alles außer dem Chat funktioniert. Die Leiste ändert
        Werte; das hier vergibt den Namen. Ein Undo entfernt den Parameter
        wieder, weil er als ``DocumentChange`` reist.
        """
        parameters = self.project.document.parameters
        if parameter.name in parameters:
            self.failed.emit(
                ValidationError(
                    field="name",
                    detail=tr("Diesen Namen gibt es schon."),
                    constraint="duplicate",
                    values={"name": parameter.name},
                )
            )
            return
        try:
            # Der Dialog prüft dasselbe, aber der Weg hierher ist nicht der
            # einzige — was die Grammatik nicht kennt oder im Kreis liest,
            # kommt nicht ins Dokument.
            expressions.check(f"@{parameter.name}")
            if parameter.expression:
                expressions.resolution_order({**parameters, parameter.name: parameter})
            self.history.apply(
                f"{tr('Parameter')} {parameter.name}",
                changes=change_for(self.project.document, parameters={parameter.name: parameter}),
            )
        except AppError as error:
            self.failed.emit(error)
            return
        self._dirty = True
        self.projectChanged.emit()
        self.evaluate_async()

    def change_scene_profile(self, printer: str, material: str) -> None:
        """Drucker und Material des offenen Projekts (§12, §15.5).

        Beide wurden bisher genau einmal gesetzt — beim Anlegen — und danach
        nie wieder. Wer ein Beispielprojekt oder eine fremde Datei öffnete,
        arbeitete dauerhaft gegen einen fremden Bauraum, und Bett, Anordnen,
        Kollisionsprüfung und Auto Split hingen alle daran.

        Eine Transaktion, keine Operation: es entsteht keine Geometrie. Sie
        ändert sich trotzdem — Toleranzen sind Verweise ins Materialprofil
        (§12) —, und was die Auswertung beeinflusst, gehört in den Verlauf.
        """
        document = self.project.document
        if (document.printer, document.material) == (printer, material):
            return
        try:
            self.history.apply(
                _("Drucker und Material"),
                changes=change_for(document, printer=printer, material=material),
            )
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

    def set_print_settings(self, settings: PrintSettings) -> None:
        """Womit dieses Projekt gedruckt wird (§29).

        Keine Operation und keine Transaktion: es entsteht keine Geometrie und
        es ändert sich keine. Das Projekt gilt danach als geändert, damit die
        Einstellung nicht beim nächsten Schließen verloren geht — sichtbar
        wird sie im Titel, wie jede andere Änderung auch.
        """
        if self.project.document.print_settings == settings:
            return
        self.project.document.print_settings = settings
        self._dirty = True
        self.projectChanged.emit()

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
                _("STEP laden"),
                [OperationDraft(op="load_step", params={"source": source_id})],
            )
            return
        if is_outline(path.suffix):
            # Eine flache Zeichnung hat auch keine Einheitenfrage — sie hat keine
            # dritte Dimension, bis jemand sagt, wie dick sie sein soll (§25).
            self.apply(
                _("Zeichnung extrudieren"),
                [OperationDraft(op="load_outline", params={"source": source_id})],
            )
            return
        # Wie viele Körper die Datei hält, entscheidet sich hier, nicht in der
        # Operation: der Stapel vergibt Objekt-IDs, bevor irgendetwas läuft
        # (§11), und bei einer 3MF-Baugruppe steht die Zahl in der Datei.
        # Gezählt, ohne eine einzige Koordinate zu lesen.
        parts = threemf.count_objects(self.project.sources[source_id]) if is_3mf else 1
        self.apply(
            _("Modell laden"),
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

    def create_lid(self, object_id: str, params: dict[str, Any]) -> LidApplied:
        """Deckel erzeugen — als Ablauf, damit die Passung mitkommt (§14).

        Die Operation allein baut nur den Körper. Erst der Ablauf trägt das
        Paar aus Öffnung und Kragen ins Dokument ein, und daran hängen im
        Slicer die genaue Außenwand, die gebremste Beschleunigung und das
        Bügeln — die drei Werte, die über eine Passung entscheiden.
        """
        applied = apply_lid(self.project.document, object_id, params, self.profile)
        self._dirty = True
        self.projectChanged.emit()
        self.evaluate_async()
        return applied

    def preview_async(
        self,
        then: Any,
        drafts: list[OperationDraft] | None = None,
        *,
        change_op: int | None = None,
        change_values: dict[str, Any] | None = None,
    ) -> None:
        """Die Live-Vorschau des Operationsdialogs (§18.7).

        Eine neuere Anfrage ersetzt die wartende — gerechnet wird beides,
        gezeigt nur das Jüngste. ``then`` bekommt die ``SceneDifference``
        oder ``None``, wenn es nichts zu zeigen gibt.
        """
        self._preview_generation += 1
        generation = self._preview_generation

        def compute() -> tuple[Any, SceneDifference | None]:
            return self.preview_scene(
                list(drafts or []), change_op=change_op, change_values=change_values
            )

        worker = _PreviewWorker(self, generation, compute)
        worker.done.connect(lambda stamp, difference: self._preview_done(stamp, difference, then))
        worker.finished.connect(lambda done=worker: self._preview_finished(done))
        self._previews.append(worker)
        worker.start()

    def _preview_finished(self, worker: _PreviewWorker) -> None:
        if worker in self._previews:
            self._previews.remove(worker)

    def _preview_done(self, stamp: int, difference: Any, then: Any) -> None:
        if stamp != self._preview_generation:
            return
        then(difference)

    def cancel_preview(self) -> None:
        """Der Dialog ist zu — was noch rechnet, wird verworfen, nicht gezeigt."""
        self._preview_generation += 1

    def split_async(self, object_id: str, then: Any) -> None:
        """Auto Split, ohne das Fenster anzuhalten (§2.8).

        Die Suche läuft im Arbeiter, das Anwenden danach hier im Thread des
        Dokuments; ``then`` bekommt das ``SplitApplied``. Ein Abbruch über
        :meth:`cancel_split` verwirft den Plan — die Suche kennt keinen
        Abbruch von innen, aber niemand muss auf ein Ergebnis warten, das er
        nicht mehr will.
        """
        self.wait_for_idle()
        result = self.last_result
        entry = result.scene.objects.get(object_id) if result is not None else None
        if entry is None:
            self.failed.emit(
                InternalError(
                    detail="auto split was asked for an object that is not in the scene",
                    values={"object": object_id},
                )
            )
            return

        self._split_discarded = False
        worker = _SplitWorker(as_mesh_data(entry.mesh), object_id, self.profile)
        worker.done.connect(lambda plan: self._split_planned(plan, object_id, then))
        worker.failedWith.connect(self._split_failed)
        worker.finished.connect(self._on_split_done)
        self._split = worker
        self.splitBusyChanged.emit(True)
        worker.start()

    @property
    def split_running(self) -> bool:
        return self._split is not None and self._split.isRunning()

    def cancel_split(self) -> None:
        """Das Ergebnis wird verworfen, wenn es kommt — der Knopf wirkt
        sofort, auch wenn der Arbeiter noch ausläuft."""
        if self._split is None:
            return
        self._split_discarded = True
        self.splitBusyChanged.emit(False)

    def _split_failed(self, error: AppError) -> None:
        self.splitBusyChanged.emit(False)
        if not self._split_discarded:
            self.failed.emit(error)

    def _split_planned(self, plan: Any, object_id: str, then: Any) -> None:
        self.splitBusyChanged.emit(False)
        if self._split_discarded:
            return
        applied = apply_planned(self.project.document, plan, object_id, self.profile)
        if applied.transaction is not None:
            self._dirty = True
            self.projectChanged.emit()
            self.evaluate_async()
        then(applied)

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
        """Der eine Knopf hält beides an, was gerade laufen kann (§2.8)."""
        self.cancel_signal.cancel()
        self.agent_cancel.cancel()

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
        self.agent_cancel.reset()
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
            cancelled=self.agent_cancel,
            progress=self.agentProgress.emit,
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
        return self.preview_scene(
            list(proposal.drafts), origin=proposal.origin, ask=self.ask_from_worker
        )

    def preview_scene(
        self,
        drafts: list[OperationDraft],
        *,
        origin: Origin | None = None,
        ask: Any = None,
        change_op: int | None = None,
        change_values: dict[str, Any] | None = None,
    ) -> tuple[Any, SceneDifference | None]:
        """Wonach die Szene aussähe — die eine Vorschau für Agent und Dialog.

        Auf einer Kopie des Dokuments, in Entwurfsqualität; der Cache trägt
        alle Schritte, die schon gerechnet sind. ``change_op`` mit
        ``change_values`` zeigt statt neuer Schritte eine geänderte Operation
        des Stapels (§15.4). Ohne ``ask`` hält eine Rückfrage die Vorschau an,
        statt mitten ins Tippen ein Fenster zu stellen — was eine Frage
        braucht, hat keine stille Vorschau.
        """
        import copy

        before = self.last_result.scene if self.last_result else None
        working = copy.deepcopy(self.project.document)
        if change_op is not None:
            History(working).change_params(change_op, dict(change_values or {}))
        else:
            History(working).apply(_("Vorschau"), drafts, origin=origin or Origin(by="user"))
        result = evaluate(
            working,
            self.profile,
            quality="draft",
            sources=ProjectSources(self.project, base_dir=self.base_dir),
            ask=ask or _no_questions,
        )
        if result.stopped_at is not None:
            # Eine angehaltene Kette ist keine Vorschau: die leere Differenz
            # sähe aus wie „keine Änderung", und das wäre gelogen.
            return result.scene, None
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
        # Nicht einfach loslassen — siehe ``_finished_agent``.
        self._finished_agent = self._agent
        self._agent = None

    def _on_split_done(self) -> None:
        """Die Teilungssuche ist ausgelaufen — ihr Arbeiter bleibt am Leben.

        Als benannter Slot und nicht als Lambda: das Lambda schrieb ``None`` in
        dasselbe Feld, dessen Objekt es gerade zustellte."""
        self._finished_split = self._split
        self._split = None

    def _on_thread_done(self) -> None:
        self.busyChanged.emit(False)
        # Nicht einfach loslassen: der Aufruf hier kommt vom Signal des
        # Arbeiters selbst, und sein Wrapper muss die Zustellung überleben.
        self._finished_worker = self._worker
        self._worker = None
        if self._rerun_pending:
            self._rerun_pending = False
            self.evaluate_async()

    def wait_for_idle(self, timeout_ms: int = 10_000) -> None:
        """Blockiert, bis kein Lauf mehr übrig ist — auch der nicht, den eine
        Entprellung eingereiht hat.

        Ereignisse werden verarbeitet, weil die Arbeiter ihre Ergebnisse über
        Signale zurückgeben und sonst nie ankämen. Eingaben aber nicht: sonst
        startet ein Menüklick mitten in diesem Warten die nächste Aktion, und
        die trifft auf einen Zustand, den gerade jemand anders umbaut.
        """
        deadline = time.monotonic() + timeout_ms / 1000.0
        while time.monotonic() < deadline:
            # Auch Trennebenensuche und Vorschau zählen: ein Arbeiter, der
            # das Fenster überlebt, nimmt beim Beenden den Prozess mit.
            worker = self._worker or self._split or next(iter(self._previews), None)
            if worker is None:
                break
            worker.wait(50)
            application = QCoreApplication.instance()
            if application is not None:
                application.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
