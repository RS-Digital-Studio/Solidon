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
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from functools import partial
from math import isfinite
from pathlib import Path
from typing import Any

from PySide6.QtCore import QCoreApplication, QEventLoop, QObject, Signal

from app.core import activation, expressions
from app.core.agent import apply as agent_apply
from app.core.agent.proposal import Proposal
from app.core.agent.session import AgentSession
from app.core.backends.llm import LLMBackend, first_available
from app.core.backends.mesh import GeneratedMesh
from app.core.errors import (
    CANCEL_SPLIT,
    AppError,
    InternalError,
    OperationCancelled,
    UserError,
    ValidationError,
)
from app.core.generate import into_project as generate_into
from app.core.geom.difference import SceneDifference, compare_scenes
from app.core.geom.mesh import as_mesh_data
from app.core.geom.section import SectionPlane
from app.core.ingest.loader import read_local_payload
from app.core.ingest.plan import import_plan
from app.core.knowledge import profiles
from app.core.knowledge.parts import check as part_check
from app.core.lid_flow import LidApplied, apply_lid
from app.core.log import get_logger
from app.core.scene import (
    CancelSignal,
    EvaluationResult,
    History,
    NeverCancelled,
    OperationDraft,
    disk_backed_cache,
    foreign,
    orphans,
)
from app.core.scene.evaluate import evaluate
from app.core.scene.history import change_for
from app.core.scene.project import (
    Project,
    ProjectSources,
    checksum,
    clear_autosave,
    embedded_source_path,
    load,
    new_project,
    save,
    write_autosave,
)
from app.core.split import SplitApplied, apply_line_split, apply_planned, apply_split, plan_split
from app.core.types import (
    Feature,
    FeatureId,
    Finding,
    Fit,
    Origin,
    Parameter,
    PrintSettings,
    Profile,
    Quality,
    Report,
    Source,
    SourceKind,
    SourceOrigin,
    Transaction,
)
from app.core.units import is_close
from app.i18n import TranslatableText, _, tr
from app.ui.leash import Worker, WorkerLeash, undisturbed

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


class _EvaluationWorker(Worker):
    """Ein Auswertungslauf. Besitzt nichts, meldet alles."""

    finishedWith = Signal(object)
    failedWith = Signal(object)
    cancelled = Signal()

    def __init__(self, session: Session) -> None:
        super().__init__()
        self._session = session

    def work(self) -> None:
        session = self._session
        try:
            # §32: was diese Datei außer Geometrie mitbringt, wird am Dokument
            # abgelesen — vor der Auswertung, damit der Hinweis nicht von dem
            # abhängt, was die Auswertung daraus macht.
            outside: list[Finding] = []
            if session.pending_foreign_check:
                session.pending_foreign_check = False
                outside = foreign.findings_for(session.project.document)
            if session.pending_part_check:
                # §24.4: was die Bibliothek geändert hat, seit diese Datei
                # gespeichert wurde, wird einmal gesagt — beim Öffnen, nicht
                # bei jeder Auswertung. **Vor** der Auswertung wie der
                # foreign-Hinweis darüber, aus demselben Grund: Der
                # ``parts.scripted_recipe``-Satz ist die zweite Hälfte von
                # §32, und er lief hier einst nach ``run_evaluation`` — das
                # fremde Programm war dann längst gestartet, bevor der Satz
                # überhaupt entstand. Gelesen wird ohnehin nur Dokument und
                # Register, nichts aus dem Ergebnis.
                session.pending_part_check = False
                outside.extend(part_check.check(session.project.document))

            result = session.run_evaluation()
            result = _with_findings(result, outside)
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


class _AgentWorker(Worker):
    """Ein Zug des Agenten, abseits des GUI-Threads (§26.5)."""

    finishedWith = Signal(object)
    failedWith = Signal(object)

    def __init__(self, session: Session, request: str, backend: LLMBackend) -> None:
        super().__init__()
        self._session = session
        self._request = request
        self._backend = backend

    def work(self) -> None:
        session = self._session
        try:
            preview = session.run_proposal(self._request, self._backend)
        except OperationCancelled:
            self.failedWith.emit(AppError(tr("Der Vorschlag wurde abgebrochen.")))
        except AppError as error:
            self.failedWith.emit(error)
        else:
            self.finishedWith.emit(preview)


class _PreviewWorker(Worker):
    """Eine Dialog-Vorschau, abseits des GUI-Threads (§18.7, §2.8).

    Dieselbe Begründung wie beim Agentenvorschlag: die Differenz sind zwei
    Boolesche Operationen je Körper. ``generation`` stempelt das Ergebnis —
    wer weitertippt, ersetzt die Anfrage, und eine verspätete Antwort auf
    eine alte Frage wird verworfen statt gezeigt.
    """

    done = Signal(int, object)

    def __init__(
        self, session: Session, generation: int, compute: Any, cancel: CancelSignal
    ) -> None:
        super().__init__()
        self._session = session
        self._generation = generation
        self._compute = compute
        self.cancel = cancel

    def work(self) -> None:
        try:
            _scene, difference = self._compute()
        except (AppError, OperationCancelled):
            # Beim Tippen entstehen ungültige Zwischenstände; der echte
            # Fehler kommt beim Anwenden als Vorschlag (§2.7). Die Vorschau
            # zeigt dann schlicht nichts Neues.
            self.done.emit(self._generation, None)
        else:
            self.done.emit(self._generation, difference)


class _SplitWorker(Worker):
    """Die Trennebenensuche, abseits des GUI-Threads (§2.8, §22.3).

    Sie schneidet jede Kandidatenebene durch das ganze Netz — Sekunden bis
    Minuten an einem großen Körper, und sie lief mit einem Wartezeiger im
    Hauptthread. Gerechnet wird hier nur der Plan; das Anwenden mutiert das
    Dokument und bleibt im Thread, dem das Dokument gehört.
    """

    done = Signal(object)
    failedWith = Signal(object)
    cancelled = Signal()
    progressed = Signal(float, str)

    def __init__(
        self,
        mesh: Any,
        object_id: str,
        profile: Profile,
        features: Mapping[FeatureId, Feature],
    ) -> None:
        super().__init__()
        self._mesh = mesh
        self._object_id = object_id
        self._profile = profile
        self._features = dict(features)
        #: Ein eigenes Token, wie bei der Vorschau: Die Suche kann Minuten
        #: laufen, und wer sie abbricht, will nicht auf sie warten.
        self.cancel = CancelSignal()

    def work(self) -> None:
        try:
            plan = plan_split(
                self._mesh,
                self._object_id,
                self._profile,
                features=self._features,
                cancelled=self.cancel,
                progress=self.progressed.emit,
            )
        except OperationCancelled:
            self.cancelled.emit()
        except AppError as error:
            self.failedWith.emit(error)
        else:
            self.done.emit(plan)


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
    splitProgressChanged = Signal(float, str)
    """Fortschritt ausschließlich der aktuellen Trennebenensuche (§2.8)."""
    splitCancelRequested = Signal()
    """Der Nutzer hat den Abbruch der laufenden Trennebenensuche verlangt."""
    splitCancelled = Signal()
    """Der aktuelle Arbeiter hat den verlangten Abbruch bestätigt (§2.8)."""
    evaluationCancelled = Signal()
    """Ein Mensch hat die Auswertung angehalten (§2.8).

    **Nicht** bei jedem Abbruch: Eine neuere Anfrage bricht die laufende
    ebenfalls ab (``_rerun_pending``), und das ist ein Ersetzen, kein
    Aufhören — es zu melden hieße, beim Ziehen an einem Schieber im
    Sekundentakt „abgebrochen" in die Statuszeile zu schreiben."""
    projectChanged = Signal()
    """Stapel, Pfad oder Titel haben sich geändert; die Leisten laden neu."""
    failed = Signal(object)
    """An ``AppError`` the surface shows as a suggestion (§2.7)."""
    backendChanged = Signal()
    """Der Chat spricht ab jetzt mit einem anderen Modell — die Kopfzeile lädt neu.

    Ausgelöst, wenn die Gegenseite einen Zugang ablehnt: Dann fällt der Chat
    auf das nächste verfügbare Modell zurück, und das muss dranstehen. Ohne
    dieses Signal behielt die Kopfzeile den Namen dessen, der gerade abgelehnt
    hatte — genau der Anblick, der einen Kunden am 24.08.2026 drei Stunden
    lang glauben ließ, seine Einstellung sei nicht angekommen."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.project: Project = new_project(profiles.DEFAULT_PRINTER, profiles.DEFAULT_MATERIAL)
        self.history = History(self.project.document)
        self.cache = disk_backed_cache()
        self.cancel_signal = CancelSignal()
        self._cancel_by_user = False
        """Ob der laufende Abbruch von einem Menschen kommt — siehe
        ``evaluationCancelled``."""
        self.agent_cancel = CancelSignal()
        """Ein eigenes Signal für den Agentenzug: Auswertung und Agent laufen
        unabhängig, und ein abgebrochener Vorschlag darf keine laufende
        Berechnung mitreißen (§15.6)."""
        self.path: Path | None = None
        self.quality: Quality = "draft"
        """Entwurf, solange gearbeitet wird; Export und Abschlussbericht schalten
    auf fein (§31)."""
        self._quality_once: Quality | None = None
        """Die Qualität für **einen** Lauf — siehe :meth:`recompute_fully`."""
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
        self._agent: _AgentWorker | None = None
        self._split: _SplitWorker | None = None
        self._leash = WorkerLeash(self)
        """Hält jeden ausgelaufenen Arbeiter, bis Qt mit ihm durch ist.

        **Vorher hielt jede Art genau einen** — ``_finished_worker``,
        ``_finished_agent``, ``_finished_split`` —, und der nächste löste ihn
        ab. Bei einer Kette geht das schief: ``_on_thread_done`` startet bei
        ``_rerun_pending`` sofort den nächsten Lauf, und wird der schnell
        fertig, überschreibt er das Feld, während Qt den Vorgänger noch
        abräumt. Genau diese Kette steht im Stapelabzug eines Absturzes, den
        das Repository lange nur als „Segfault in test_chat_ui.py" kannte:
        ``start_new`` → ``_reset_for`` → ``evaluate_async`` →
        ``_EvaluationWorker.__init__``, Zugriffsverletzung.

        Die Halteleine hält eine Liste statt eines Feldes und lässt erst los,
        wenn ``isRunning`` nein sagt — dasselbe Muster, das Fenster und Dialoge
        seit dem Umbau benutzen (siehe :mod:`app.ui.leash`)."""
        self._split_discarded = False
        """Ob das laufende Split-Ergebnis verworfen wurde — der Arbeiter
        läuft dann aus, ohne dass jemand sein Ergebnis anwendet."""
        self._split_cancel_confirmed = False
        """Ob der Abbruch des aktuellen Split-Arbeiters schon bestätigt wurde."""
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
        self._pending_views: tuple[tuple[str, bytes], ...] = ()
        """Die Ansichten des nächsten Zuges (§23) — im Hauptthread gerendert,
        vom Arbeiter nur gelesen; VTK gehört nie in einen zweiten Thread."""
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
    def document_name(self) -> str:
        """Wie das Projekt heißt — ohne Stern, ohne Zusatz, für Dateinamen.

        Getrennt von :attr:`title`, weil beides auseinanderläuft: Der Titel ist
        für den Menschen und trägt, was das Fenster über sich sagen muss; dies
        hier landet in Dateidialogen. Ohne die Trennung stünde beim Exportieren
        „GK-Brause (ungespeichert).stl" — ein Dateiname mit einer Eigenschaft
        des Fensters darin.
        """
        if self.path is not None:
            return self.path.stem
        result = self.last_result
        objects = list(result.scene.objects.values()) if result is not None else []
        if not objects:
            return ""
        # **Der erste und nicht „N Objekte".** Wer eine Baugruppe baut, fängt
        # mit einem Teil an, und die späteren sind meist Werkzeuge oder
        # Gegenstücke dazu; der erste Name ist das, woran jemand denkt, wenn er
        # an dieses Projekt denkt. Eine Zahl im Titel beantwortet keine Frage,
        # die jemand hat.
        return str(objects[0].name)

    @property
    def title(self) -> str:
        """Was im Fenstertitel steht.

        **„Unbenannt" nennt, was fehlt, statt was da ist.** Im Bildschirmfoto
        des ersten Kunden mit 0.1.3 stand oben „Unbenannt*" und darunter im
        Baum „GK-Brause" mit seinen Maßen — der Titel wusste den Namen und
        sagte ihn nicht. Entschieden von Robert am 23.08.2026: der abgeleitete
        Name, wie Fusion es tut. Ein Titel, der dem Baum widerspricht, ist
        schlechter als einer, der ihn wiederholt.

        **Der Zusatz „(ungespeichert)" ist nicht dasselbe wie der Stern.** Der
        Stern sagt „seit dem letzten Speichern geändert", der Zusatz sagt „es
        gibt keine Datei". Ohne ihn sähe „GK-Brause*" aus wie eine geöffnete
        Projektdatei, und der Kunde suchte sie beim nächsten Start auf der
        Platte.
        """
        if self.path is None:
            # **Kein Stern ohne Datei.** Er sagt „seit dem letzten Speichern
            # geändert" — und wo nie gespeichert wurde, kann er gar nicht
            # fehlen. „GK-Brause (ungespeichert)*" trägt dieselbe Aussage
            # zweimal, einmal als Wort und einmal als Zeichen.
            if not self.document_name:
                return str(tr("Unbenannt"))
            return str(tr("{name} (ungespeichert)").format(name=self.document_name))
        return f"{self.path.name}*" if self._dirty else self.path.name

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

    def recover(self, path: Path, into: Path | None = None) -> None:
        """Öffnet eine automatische Sicherung, ohne sie zum Projekt zu machen.

        Die Sicherung ist nicht die Datei, die der Nutzer pflegt, und ein
        „Speichern" darauf würde sie überschreiben, statt die eigentliche
        Datei zu schreiben.

        ``into`` ist genau diese Datei: die Sicherung gehört zu ihr, also
        speichert ein „Speichern" dorthin. Ohne ``into`` bleibt der Pfad leer
        — der namenlose Fall hat keine Datei, und dort fragt „Speichern" nach
        einem Namen.

        Geändert ist der Stand in beiden Fällen: er weicht von dem ab, was auf
        der Platte liegt. Genau das war der Grund, ihn wiederherzustellen.
        """
        self.project = load(path)
        self.pending_orphan_check = True
        self.pending_part_check = True
        self.pending_foreign_check = True
        self._reset_for(into)
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
        *,
        raise_on_error: bool = False,
        bundle: bool = False,
    ) -> bool:
        """Eine Transaktion, dann eine frische Auswertung (§15.5).

        Normalerweise meldet die Sitzung eine Abweisung über ``failed``. Ein
        synchroner Oberflächenweg kann sie stattdessen nach außen reichen,
        damit Wartezeiger und Statusanzeige zuerst sicher beendet werden.

        ``bundle`` bietet den Zug der vorigen Transaktion an, statt einen
        eigenen Schritt anzulegen (§15.5) — für Handlungen, die ein Kunde als
        eine empfindet, obwohl sie aus mehreren Zügen besteht. Ob es dazu
        kommt, entscheidet die ``History``: Nur gleichartige Züge auf
        denselben Eingängen mit demselben Anker verschmelzen.
        """
        try:
            self.history.apply(title, drafts, origin or Origin(by="user"), bundle=bundle)
        except AppError as error:
            if raise_on_error:
                raise
            self.failed.emit(error)
            return False
        self._dirty = True
        self.projectChanged.emit()
        self.evaluate_async()
        return True

    def repair_and_retry(self, stopped_at: int) -> bool:
        """Setzt Reparatur und erneuten Versuch als einen Zug vor den Fehler.

        Die Reihenfolge und das Undo gehören dem Verlauf; die Sitzung meldet
        nur eine Abweisung oder stößt nach dem atomaren Umbau die neue
        Auswertung an.
        """
        try:
            self.history.repair_and_retry(stopped_at)
        except AppError as error:
            self.failed.emit(error)
            return False
        self._dirty = True
        self.projectChanged.emit()
        self.evaluate_async()
        return True

    def change_parameter(self, name: str, value: float, origin: Origin | None = None) -> bool:
        """Eine gedrehte Zahl der Parameterleiste (§13, §15.5).

        Sie war lange keine Transaktion: die Leiste schrieb geradewegs ins
        Dokument. Damit war die Änderung weder rücknehmbar — ein Strg+Z nahm
        stattdessen die letzte Operation zurück — noch als Änderung erkennbar,
        und weil das Schließen nur sichert, was als geändert gilt, ging sie
        dabei verloren. ``origin`` und Rückgabewert: siehe :meth:`add_fit`.
        """
        import dataclasses

        parameters = self.project.document.parameters
        existing = parameters.get(name)
        if existing is None:
            return False
        if not isfinite(value):
            self.failed.emit(
                ValidationError(
                    field=name,
                    detail=tr("Dieser Wert ist keine endliche Zahl"),
                    value=value,
                    constraint="not_a_number",
                )
            )
            return False
        if is_close(existing.value, value):
            return False

        changed = dataclasses.replace(existing, value=value)
        try:
            self.history.apply(
                f"{tr('Parameter')} {name}",
                changes=change_for(self.project.document, parameters={name: changed}),
                origin=origin or Origin(by="user"),
            )
        except AppError as error:
            self.failed.emit(error)
            return False
        self._dirty = True
        self.projectChanged.emit()
        self.evaluate_async()
        return True

    def add_fit(self, fit: Fit, origin: Origin | None = None) -> bool:
        """Eine Passungsbeziehung ins Dokument (§14, §15.5).

        Wie ein Parameter reist sie als ``DocumentChange`` und ist damit
        rücknehmbar, zählt als Änderung und überlebt das Schließen. Bis hierher
        konnte sie nur der Agent anlegen — die Fernsteuerung bot das Werkzeug
        an und hatte niemanden, der es ausführt.

        ``origin`` trägt die Herkunft (§26.4, §26.6 Auflage 4): ein Fernaufruf
        ohne sie sah im Verlauf aus wie ein eigener Klick. Der Rückgabewert
        sagt, ob wirklich etwas geschah — eine Antwort, die Erfolg behauptet,
        während ``failed`` feuerte, ist eine Lüge an die Gegenstelle.
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
            return False
        try:
            self.history.apply(
                f"{tr('Passung')} {fit.name}",
                changes=change_for(document, fits=[*document.fits, fit]),
                origin=origin or Origin(by="user"),
            )
        except AppError as error:
            self.failed.emit(error)
            return False
        self._dirty = True
        self.projectChanged.emit()
        self.evaluate_async()
        return True

    def add_parameter(self, parameter: Parameter, origin: Origin | None = None) -> bool:
        """Ein neues Projektmaß von Hand (§13, §2.3, §15.5).

        Anlegen konnte bisher nur der Agent über sein Werkzeug — wer ohne
        Sprachmodell arbeitet, hatte kein Gegenstück, obwohl §2.3 verspricht,
        dass ohne KI alles außer dem Chat funktioniert. Die Leiste ändert
        Werte; das hier vergibt den Namen. Ein Undo entfernt den Parameter
        wieder, weil er als ``DocumentChange`` reist. ``origin`` und
        Rückgabewert: siehe :meth:`add_fit`.
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
            return False
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
                origin=origin or Origin(by="user"),
            )
        except AppError as error:
            self.failed.emit(error)
            return False
        self._dirty = True
        self.projectChanged.emit()
        self.evaluate_async()
        return True

    def edit_parameter(self, name: str, parameter: Parameter, origin: Origin | None = None) -> bool:
        """Grenzen, Einheit, Titel und Ausdruck eines vorhandenen Maßes (§13,
        §15.5).

        :meth:`change_parameter` dreht die **Zahl**, das hier schreibt die
        **Beschreibung** neu. Ohne diesen Weg waren Grenzen anlegbar und nie
        änderbar: Wer eine Obergrenze auf 100 gesetzt hatte und später 150
        brauchte, fand ein Feld, das ohne Erklärung klemmt, und einen Dialog,
        der „Diesen Namen gibt es schon" sagt (§2.1: keine Sackgassen).

        **Der Name ist der Schlüssel und wechselt hier nicht.** Ein anderer
        wäre nicht dieselbe Zeile, sondern ein zweites Maß neben dem alten —
        und jeder Ausdruck, der ``@name`` nennt, zeigte danach ins Leere.
        Umbenennen ist eine eigene Handlung; sie gibt es noch nicht.

        Wie jede Dokumentänderung reist sie als ``DocumentChange``, ist also
        rücknehmbar und zählt als Änderung. ``origin`` und Rückgabewert: siehe
        :meth:`add_fit`.
        """
        parameters = self.project.document.parameters
        existing = parameters.get(name)
        if existing is None or parameter.name != name:
            return False
        if parameter == existing:
            # Nichts geändert heißt keine Zeile im Verlauf: Ein Undo, das
            # nichts zurücknimmt, ist ein Undo, das der Kunde verliert.
            return False
        try:
            if parameter.expression:
                # Ein Ausdruck, der sich selbst oder im Kreis liest, kommt
                # nicht ins Dokument — dieselbe Prüfung wie beim Anlegen, und
                # hier ist sie schärfer: Der Parameter steht schon darin, also
                # kann er sich jetzt selbst nennen.
                expressions.resolution_order({**parameters, name: parameter})
            self.history.apply(
                f"{tr('Parameter')} {name}",
                changes=change_for(self.project.document, parameters={name: parameter}),
                origin=origin or Origin(by="user"),
            )
        except AppError as error:
            self.failed.emit(error)
            return False
        self._dirty = True
        self.projectChanged.emit()
        self.evaluate_async()
        return True

    def change_scene_profile(
        self, printer: str, material: str, origin: Origin | None = None
    ) -> bool:
        """Drucker und Material des offenen Projekts (§12, §15.5).

        Beide wurden bisher genau einmal gesetzt — beim Anlegen — und danach
        nie wieder. Wer ein Beispielprojekt oder eine fremde Datei öffnete,
        arbeitete dauerhaft gegen einen fremden Bauraum, und Bett, Anordnen,
        Kollisionsprüfung und Auto Split hingen alle daran.

        Eine Transaktion, keine Operation: es entsteht keine Geometrie. Sie
        ändert sich trotzdem — Toleranzen sind Verweise ins Materialprofil
        (§12) —, und was die Auswertung beeinflusst, gehört in den Verlauf.
        ``origin`` und Rückgabewert: siehe :meth:`add_fit`.
        """
        document = self.project.document
        if (document.printer, document.material) == (printer, material):
            return False
        try:
            self.history.apply(
                _("Drucker und Material"),
                changes=change_for(document, printer=printer, material=material),
                origin=origin or Origin(by="user"),
            )
        except AppError as error:
            self.failed.emit(error)
            return False
        self._dirty = True
        self.projectChanged.emit()
        self.evaluate_async()
        return True

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

    def removal_closure(self, op_ids: Sequence[int]) -> tuple[int, ...]:
        """Gewählte und davon abhängige Schritte für die Nachfrage bestimmen."""
        try:
            return self.history.removal_closure(op_ids)
        except AppError as error:
            self.failed.emit(error)
            return ()

    def remove_operations(self, op_ids: Sequence[int]) -> bool:
        """Verlaufsschritte als eine rücknehmbare Transaktion löschen."""
        try:
            self.history.remove_operations(op_ids)
        except AppError as error:
            self.failed.emit(error)
            return False
        self._dirty = True
        self.projectChanged.emit()
        self.evaluate_async()
        return True

    def change_inputs(self, op_id: int, inputs: list[str]) -> None:
        """Andere Objekte für einen Schritt, der schon im Stapel steht (§15.4).

        Derselbe Weg wie :meth:`change_params`, nur für die andere Hälfte einer
        Operation: Was sie *tut*, steht in den Parametern; woran sie es tut, in
        den Eingängen. Für das eine öffnet der Dialog, für das andere gibt es
        nichts aufzuklappen — man wählt im Objektbaum.
        """
        try:
            self.history.change_inputs(op_id, inputs)
        except AppError as error:
            self.failed.emit(error)
            return
        self._dirty = True
        self.projectChanged.emit()
        self.evaluate_async()

    def change_kernel(self, op_id: int, op_name: str, params: dict[str, Any]) -> None:
        """Denselben Schritt im anderen Rechenkern (§15.4, ``MENU_TWINS``).

        Derselbe Weg wie :meth:`change_params` — der Umschalter im Dialog
        entscheidet nur, welche der beiden Operationen es wird.
        """
        try:
            self.history.change_kernel(op_id, op_name, params)
        except AppError as error:
            self.failed.emit(error)
            return
        self._dirty = True
        self.projectChanged.emit()
        self.evaluate_async()

    def bake_strokes(self, op_id: int) -> bool:
        """Den Stand einer Formsitzung festschreiben (Entscheidung D).

        Das aktuelle Ergebnis wandert als Quelle ins Projekt, und die Operation
        bekommt sie als ``baked``. Danach wird sie nicht mehr gerechnet — bei
        zwanzig Etappen kostet jede Auswertung zwanzig Durchgänge, und genau
        das ist der Grund für diese Handlung.

        **Einer von zwei Fällen, in denen eine Nachfrage richtig ist.** Neben
        dem ausdrücklich gewünschten Löschen aus der Mitte des Verlaufs ist
        diese Handlung nicht folgenlos rücknehmbar, denn danach lässt sich an
        den Zügen nichts mehr ändern. Die Nachfrage stellt der Aufrufer, nicht
        diese Methode — der Kern fragt nie selbst (Regel 21).
        """
        result = self.last_result
        operation = next((entry for entry in self.project.document.ops if entry.id == op_id), None)
        if result is None or operation is None or operation.op != "sculpt_strokes":
            return False
        # Ein Körper hinein, einer heraus: Die Operation behält die
        # Objektkennung ihrer Eingabe, und das gesuchte Ergebnis steht unter
        # derselben in der Szene.
        entry = result.scene.objects.get(operation.inputs[0]) if operation.inputs else None
        if entry is None:
            return False

        source_id = self._embed_source("generated", None, as_mesh_data(entry.mesh).to_stl())
        self.change_params(op_id, {"baked": source_id})
        return True

    def _embed_source(
        self,
        kind: SourceKind,
        filename: str | None,
        payload: bytes,
        origin: SourceOrigin | None = None,
    ) -> str:
        """Nimmt einen Inhalt ins Projekt auf und gibt seine Kennung zurück.

        **Jede Quelle kennt ihren Inhalt von Anfang an**, und das ist der Grund,
        warum es diese Methode gibt. Vorher stand der Vorgang dreimal
        nebeneinander — gebackene Züge, Import, Bild — und alle drei schrieben
        ``sha256=""``. Gefüllt wurde die Prüfsumme erst beim **Speichern**
        (`project.py`, §16.1), und bis dahin wusste ein Projekt nicht, was in
        seinen Quellen steht.

        Das war lange folgenlos und ist es seit dem 22.08.2026 nicht mehr: Der
        Cache-Schlüssel fragt die Quelle, was sie inhaltlich ist
        (``SourceAccess.identity``), weil ihr Bezeichner in jedem Projekt
        ``src_1`` heißt. Eine leere Prüfsumme heißt dort „rechne es aus", und
        ausgerechnet wird sie dann bei jeder Auswertung neu. Hier kostet sie
        einmal das, was der Inhalt ohnehin schon im Speicher ist.

        Drei Kopien einer Zeile werden nicht dreimal richtig — dies ist die
        Stelle, an der die Zusage steht, und die einzige.
        """
        document = self.project.document
        source_id = f"src_{len(document.sources) + 1}"
        # ``None`` heißt „nenn sie nach ihrer Kennung". Die Aufrufstelle darf
        # diese Regel nicht nachrechnen — sie stand dort einmal, und eine
        # Kennung, die an zwei Stellen gebildet wird, geht irgendwann
        # auseinander.
        document.sources[source_id] = Source(
            id=source_id,
            kind=kind,
            path=embedded_source_path(filename or f"{source_id}.stl", source_id),
            sha256=checksum(payload),
            origin=origin,
        )
        self.project.sources[source_id] = payload
        return source_id

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

    def import_model(
        self,
        path: Path,
        unit: str = "auto",
        *,
        raise_on_error: bool = False,
    ) -> bool:
        """Bettet eine Datei von der Platte ein und legt die passende
        load-Operation auf den Stapel (§17.1).

        Eine GLTF mit ``.bin``- oder Bilddateien wird hier zu einer
        eigenständigen Quelle. Die Operation bleibt dieselbe; sie sieht nur
        die eingebetteten Daten statt eines Verweises auf den Ursprungsordner.
        """
        return self.import_payload(
            path.name,
            read_local_payload(path),
            unit=unit,
            raise_on_error=raise_on_error,
        )

    def import_payload(
        self,
        name: str,
        payload: bytes,
        *,
        unit: str = "auto",
        origin: SourceOrigin | None = None,
        raise_on_error: bool = False,
    ) -> bool:
        """Derselbe Weg für eine Datei, die nicht von der Platte kommt (§16.3).

        Getrennt von :meth:`import_model`, weil ein heruntergeladenes Modell
        keinen Pfad hat und dafür eine Herkunft — und weil beide danach genau
        dieselbe Operation auf denselben Stapel legen sollen. Zwei Importwege
        wären zwei Stellen, an denen die Einheitenfrage vergessen werden kann.

        STEP nimmt den anderen Kern und trägt seine eigene Einheit — es braucht
        also weder die Einheitenfrage noch die Mesh-Eingangsstufe (§30, §11.1).
        """
        path = Path(name)
        source_id = self._embed_source("import", path.name, payload, origin)

        # Welche Operation eine Datei einliest, entscheidet der Kern
        # (``ingest.plan``) — dieselbe Stelle, die die Kommandozeile fragt. Sie
        # stand hier vollständig und dort gar nicht: ``solidon3d import`` legte
        # immer ``load`` auf den Stapel und antwortete auf eine STEP-Datei
        # „Dieses Dateiformat kann nicht gelesen werden."
        #
        # Weist der Plan die Datei ab (zu groß, Zip-Bombe), wird die eben
        # eingebettete Quelle wieder ausgetragen (Gesamtreview F-10): sonst
        # bleibt sie als Waise im Dokument und wandert mit dem nächsten
        # Speichern in die Projektdatei. Eingebettet wird trotzdem zuerst —
        # die Kennungsregel ``src_<n>`` lebt in ``_embed_source``, und eine
        # Aufrufstelle, die sie vorwegnimmt, hätte zwei Wahrheiten.
        #
        # **Der Rücknahmepfad galt nur dem Plan, nicht dem Anwenden**, und
        # damit war die Zusage darüber nur die halbe. `History.apply` fragt
        # als Erstes die Lizenzgrenze (`activation.require`); wird dort
        # abgelehnt, bleibt das Dokument unberührt — bis auf die Quelle, die
        # eine Zeile vorher hineinkam. Gemessen mit `days_left=0`: kein
        # Bypass, keine Geometrie, aber ein 300-MB-STL wandert unsichtbar in
        # die Projektdatei, und weil `_embed_source` kein `_dirty` setzt,
        # schließt der Kunde ohne Nachfrage. Seine Datei trägt danach etwas,
        # das er nie hineingetan hat und von dem ihm niemand erzählt hat —
        # dasselbe Argument, mit dem §32 die Ansage fremder Inhalte
        # begründet. Gefunden von 3d-druck-46 im Lizenz-Audit.
        try:
            plan = import_plan(source_id, path.name, payload, unit)
        except AppError:
            self._drop_source(source_id)
            raise

        # Die Sitzung kann eine Abweisung entweder melden oder nach außen
        # reichen. In beiden Fällen wird die Quelle zurückgenommen; nur so
        # bleiben lokaler Import und Download derselbe, vollständige Vorgang.
        try:
            accepted = self.apply(
                plan.title,
                [plan.draft],
                raise_on_error=raise_on_error,
            )
        except AppError:
            self._drop_source(source_id)
            raise
        if not accepted:
            self._drop_source(source_id)
        return accepted

    def _drop_source(self, source_id: str) -> None:
        """Eine eben eingebettete Quelle wieder austragen.

        Zwei Wörterbücher, und beide gehören dazu: das Dokument nennt sie,
        das Projekt hält ihren Inhalt. Wer nur eines räumt, lässt entweder
        einen Namen ohne Datei oder hunderte Megabyte ohne Namen zurück.
        """
        self.project.document.sources.pop(source_id, None)
        self.project.sources.pop(source_id, None)

    def embed_model(self, path: Path) -> str:
        """Eine Modelldatei ins Projekt holen, ohne sie auf den Stapel zu legen.

        **Der Gegenpart zum Quellenfeld im Operationsdialog.** Wer *Modell
        laden* aus dem Menü öffnet, sieht dort eine Auswahl der Quellen, die
        das Projekt schon hat — und in einem frischen Projekt ist die leer.
        Die Liste klappte auf und zeigte nichts; das liest sich nicht als „hier
        fehlt etwas", sondern als kaputt (Regel 19: keine Sackgassen).

        Anders als :meth:`import_payload` legt diese Methode **keine**
        Operation an: Der Dialog, der sie ruft, ist ja gerade dabei, eine zu
        bauen. Zwei ``load``-Schritte für eine Datei wären das Gegenteil dessen,
        was der Kunde wollte.

        Dieselbe Bauart wie :meth:`import_image`, und aus demselben Grund an
        derselben Grenze: Der Weg ändert das Dokument, also gilt Konzept §2 C.
        """
        activation.require(activation.CHANGE)
        source_id = self._embed_source("import", path.name, path.read_bytes())
        self._dirty = True
        self.projectChanged.emit()
        return source_id

    def import_image(self, path: Path) -> str:
        """Ein Bild als Quelle fürs Relief (§25, ``displace_image``).

        Eingebettet wie ein Modell, aber ohne load-Operation: ein Bild wird
        kein Körper, es gehört einer Operation als Wert. Ohne diesen Weg
        führte kein Bildformat in die Quellen — das Feld „Bild" bot STLs an,
        und der Befund schlug eine Handlung vor, die es nicht gab.

        **Die Grenze steht hier ausdrücklich**, obwohl keine Operation folgt.
        Der Weg ändert das Dokument, also gilt Konzept §2 C — und dass er
        praktisch nur aus einem Operationsdialog erreichbar ist, der ohnehin
        gesperrt ist, ist ein Zufall der Oberfläche und keine Grenze. Wer sich
        darauf verlässt, hat eine Zusage, die beim nächsten neuen Aufrufer
        still verschwindet (`kern.md`: jede Stelle holt den Zustand selbst und
        wirft selbst).
        """
        activation.require(activation.CHANGE)
        source_id = self._embed_source("image", path.name, path.read_bytes())
        self._dirty = True
        self.projectChanged.emit()
        return source_id

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
        object_profile = profiles.for_object(self.profile, entry)

        applied = apply_split(
            self.project.document,
            as_mesh_data(entry.mesh),
            object_id,
            object_profile,
            features=entry.features,
        )
        if applied.transaction is not None:
            self._dirty = True
            self.projectChanged.emit()
            self.evaluate_async()
        return applied

    def split_along(
        self, object_id: str, plane: SectionPlane, *, pins: int, shape: str = "round"
    ) -> SplitApplied:
        """§25: an einer gezeichneten Ebene trennen — als Ablauf, damit die
        Passung mitkommt (§14).

        Dieselbe Bauart wie *Deckel erzeugen* daneben und aus demselben Grund:
        Die Operation allein macht die zwei Hälften. Erst der Ablauf trägt das
        Paar aus Stift und Bohrung ins Dokument ein, und daran hängen im
        Slicer die Werte, die über eine Passung entscheiden.

        Der ausgewertete Körper geht mit: An ihm entscheidet sich, wie viele
        Stifte auf die Schnittfläche passen — und damit, wie viele Passungen
        entstehen. Ohne ihn entstünden Paare, die auf Merkmale zeigen, die es
        nicht gibt.
        """
        result = self.last_result
        entry = result.scene.objects.get(object_id) if result is not None else None
        object_profile = profiles.for_object(self.profile, entry)
        applied = apply_line_split(
            self.project.document,
            object_id,
            plane,
            object_profile,
            mesh=as_mesh_data(entry.mesh) if entry is not None else None,
            features=entry.features if entry is not None else None,
            pins=pins,
            shape=shape,
        )
        self._dirty = True
        self.projectChanged.emit()
        self.evaluate_async()
        return applied

    def create_lid(
        self,
        object_id: str,
        params: dict[str, Any],
        *,
        op: str = "create_lid",
    ) -> LidApplied:
        """Deckel erzeugen — als Ablauf, damit die Passung mitkommt (§14).

        Die Operation allein baut nur den Körper. Erst der Ablauf trägt das
        Paar aus Öffnung und Kragen ins Dokument ein, und daran hängen im
        Slicer die genaue Außenwand, die gebremste Beschleunigung und das
        Bügeln — die drei Werte, die über eine Passung entscheiden.
        """
        applied = apply_lid(self.project.document, object_id, params, self.profile, op=op)
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
        # **Ein Token je Arbeiter, kein geteiltes.** Ein gemeinsames mit
        # ``reset()`` vor dem Start wäre ein Wettlauf: der alte Lauf fragt es
        # womöglich erst nach dem Zurücksetzen ab und sähe den gesetzten
        # Zustand nie — dann rechnet er zu Ende, und beim schnellen Tippen
        # stapeln sich Boolesche Operationen für Ergebnisse, die schon
        # niemand mehr sehen will.
        cancel = CancelSignal()

        def compute() -> tuple[Any, SceneDifference | None]:
            return self.preview_scene(
                list(drafts or []),
                change_op=change_op,
                change_values=change_values,
                cancelled=cancel,
            )

        # Was jetzt noch rechnet, rechnet für eine Frage von gestern: die
        # Generation hätte sein Ergebnis ohnehin verworfen (``_preview_done``).
        self.cancel_previews()
        worker = _PreviewWorker(self, generation, compute, cancel)
        worker.done.connect(lambda stamp, difference: self._preview_done(stamp, difference, then))
        # Die Vorschau hat keinen Fehlerpfad — sie ist eine Zugabe (§18.7). Was
        # hier schiefgeht, gehört ins Protokoll und sonst nirgendwohin: ein
        # Fehlerdialog über einer Vorschau wäre lauter als die Sache.
        worker.crashed.connect(lambda detail: _log.warning("preview crashed: %s", detail))
        worker.finished.connect(lambda done=worker: self._preview_finished(done))
        self._previews.append(worker)
        self._leash.start(worker)

    def _preview_finished(self, worker: _PreviewWorker) -> None:
        if worker in self._previews:
            self._previews.remove(worker)
        # Nicht einfach loslassen: ``finished`` heißt „``run`` ist zurück",
        # nicht „das Objekt darf weg" (siehe :mod:`app.ui.leash`).
        self._leash.hold_until_done(worker)

    def cancel_previews(self) -> None:
        """Jedem laufenden Vorschau-Arbeiter sagen, dass er aufhören darf."""
        for worker in list(self._previews):
            worker.cancel.cancel()

    def _preview_done(self, stamp: int, difference: Any, then: Any) -> None:
        if stamp != self._preview_generation:
            return
        then(difference)

    def cancel_preview(self) -> None:
        """Der Dialog ist zu — was noch rechnet, hört auf.

        Die Generation allein genügte nicht: Sie **verwarf** das Ergebnis,
        angehalten hat sie nichts. Wer einen Dialog über einem großen Körper
        schloss, ließ eine Rechnung hinter sich, die niemand mehr sehen wollte
        und die trotzdem bis zum Ende lief.
        """
        self._preview_generation += 1
        self.cancel_previews()

    def split_async(self, object_id: str, then: Any) -> None:
        """Auto Split, ohne das Fenster anzuhalten (§2.8).

        Die Suche läuft im Arbeiter, das Anwenden danach hier im Thread des
        Dokuments; ``then`` bekommt das ``SplitApplied``. :meth:`cancel_split`
        hält sie an **und** verwirft, was doch noch käme: Der Knopf wirkt
        sofort, und die Maschine hört auf zu rechnen.
        """
        if self.split_running:
            # Ein zweiter Start überschriebe den laufenden Arbeiter: sein Plan
            # käme trotzdem an, ``split_running`` löge nach dessen Ende, und
            # ein Thread überlebte sein Fenster. Die Aktion im Fenster ist
            # gesperrt; das hier ist das zweite Netz (Gesamtreview I-10).
            self.failed.emit(
                UserError(
                    _("Die Teilung läuft schon."),
                    _("Eine zweite Suche zugleich hätte zwei Antworten auf eine Frage."),
                    suggestions=(CANCEL_SPLIT,),
                )
            )
            return
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

        object_profile = profiles.for_object(self.profile, entry)
        self._split_discarded = False
        self._split_cancel_confirmed = False
        worker = _SplitWorker(as_mesh_data(entry.mesh), object_id, object_profile, entry.features)
        # Jeder Empfänger bekommt den Absender mit: Was ein überlebender
        # Arbeiter eines früheren Starts noch meldet, zählt nicht mehr.
        worker.done.connect(
            lambda plan: self._split_planned(worker, plan, object_id, object_profile, then)
        )
        worker.failedWith.connect(lambda error: self._split_failed(worker, error))
        worker.crashed.connect(
            lambda detail: self._split_failed(worker, InternalError(detail=detail))
        )
        worker.cancelled.connect(lambda: self._split_cancelled(worker))
        worker.progressed.connect(
            lambda fraction, text: self._split_progress(worker, fraction, text)
        )
        worker.finished.connect(lambda: self._on_split_done(worker))
        self._split = worker
        self.splitBusyChanged.emit(True)
        self._leash.start(worker)

    @property
    def split_running(self) -> bool:
        return self._split is not None and self._split.isRunning()

    def cancel_split(self) -> None:
        """Anhalten und verwerfen — beides, und in dieser Reihenfolge.

        Verwerfen allein war die halbe Antwort: Der Knopf wirkte sofort, die
        Suche schnitt aber weiter jede Kandidatenebene durch das ganze Netz,
        Minuten lang, für einen Plan, den schon niemand mehr wollte. Das Token
        erreicht sie zwischen den Blöcken der Abtastung (§15.6).
        """
        if self._split is None or self._split_discarded:
            return
        self._split.cancel.cancel()
        self._split_discarded = True
        self.splitCancelRequested.emit()

    def _split_progress(self, worker: object, fraction: float, text: str) -> None:
        """Reicht nur Meldungen des noch gültigen Split-Arbeiters weiter.

        Ein verworfener oder ausgelaufener Arbeiter kann bereits zugestellte
        Qt-Signale hinterlassen. Sie dürfen weder den neuen Lauf noch die
        dauerhafte Abbruchmeldung überschreiben.
        """
        if worker is not self._split or self._split_discarded:
            return
        self.splitProgressChanged.emit(fraction, text)

    def _split_failed(self, worker: object, error: AppError) -> None:
        if worker is not self._split:
            return
        self.splitBusyChanged.emit(False)
        if not self._split_discarded:
            self.failed.emit(error)

    def _split_cancelled(self, worker: object) -> None:
        """Die Suche hat aufgehört, weil jemand es wollte — kein Fehler.

        Ein abgebrochener Lauf als Fehlermeldung zu zeigen wäre eine Antwort
        auf eine Frage, die der Nutzer selbst schon beantwortet hat.
        """
        if worker is not self._split:
            return
        self._confirm_split_cancelled(worker)
        self.splitBusyChanged.emit(False)

    def _confirm_split_cancelled(self, worker: object) -> None:
        """Bestätigt den Abbruch des aktuellen Arbeiters höchstens einmal."""

        if worker is not self._split or self._split_cancel_confirmed:
            return
        self._split_cancel_confirmed = True
        self.splitCancelled.emit()

    def _split_planned(
        self,
        worker: object,
        plan: Any,
        object_id: str,
        profile: Profile,
        then: Any,
    ) -> None:
        if worker is not self._split:
            return
        self.splitBusyChanged.emit(False)
        if self._split_discarded:
            return
        applied = apply_planned(self.project.document, plan, object_id, profile)
        if applied.transaction is not None:
            self._dirty = True
            self.projectChanged.emit()
            self.evaluate_async()
        then(applied)

    def undo(self) -> Transaction | None:
        transaction = self.history.undo()
        if transaction is None:
            return None
        self._dirty = True
        self.projectChanged.emit()
        self.evaluate_async()
        return transaction

    def undo_applied(self, transaction: str) -> bool:
        """Der Weg zurück aus der Übernommen-Leiste (§26.5) — genau diese
        Transaktion, oder gar nichts.

        Die Regel wohnt im Kern (``agent_apply.undo_applied``); hier stehen
        nur die Folgen eines echten Undo. Das Fenster prüfte dieselbe
        Bedingung von Hand, während die Kernfunktion keinen Aufrufer hatte —
        die Bauart, die ``proposal.py`` als Drift-Quelle beschreibt: dieselbe
        Regel, dreimal ausgeschrieben, und die dritte Stelle läuft davon.
        """
        if not agent_apply.undo_applied(self.history, transaction):
            return False
        self._dirty = True
        self.projectChanged.emit()
        self.evaluate_async()
        return True

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
        self._cancel_by_user = False
        self.busyChanged.emit(True)
        worker = _EvaluationWorker(self)
        # **Jeder Slot erfährt, von welchem Lauf er kommt.** Ein Arbeiter ist
        # fertig, bevor Qt seine Signale zugestellt hat — und in dieser Lücke
        # startet der nächste. Ohne den Absender hielt der Nachzügler seine
        # Meldung für die aktuelle: Er löschte ``_worker`` (das Feld gehörte da
        # längst dem Nachfolger), meldete ``busyChanged(False)`` mitten in
        # dessen Lauf und schob seine alte Szene ins Fenster. Genau das
        # passierte beim häufigsten Weg überhaupt — eine Datei auf den
        # Startbildschirm ziehen legt zwei Läufe hintereinander: den leeren des
        # neuen Projekts und den des Imports.
        worker.finishedWith.connect(partial(self._on_finished, finished=worker))
        worker.failedWith.connect(partial(self._on_failed, finished=worker))
        # **Und das Unerwartete.** Ohne diese Zeile blieb die Ladeanzeige des
        # Fensters für immer stehen: Ein ``run``, das eine Ausnahme durchlässt,
        # sendet weder ``finishedWith`` noch ``failedWith``, und ``busyChanged``
        # kam nie zurück. Aus dem Unerwarteten wird ein ``InternalError`` — §33.1
        # ordnet ihm den Fehlerbericht zu, und genau der gehört hierher.
        worker.crashed.connect(
            lambda detail, done=worker: self._on_failed(InternalError(detail=detail), finished=done)
        )
        worker.cancelled.connect(partial(self._on_cancelled, finished=worker))
        worker.finished.connect(partial(self._on_thread_done, worker))
        self._worker = worker
        self._leash.start(worker)

    def run_evaluation(self, quality: Quality | None = None) -> EvaluationResult:
        """Ein Durchlauf mit allem, was der Kern braucht. Keine Signale, kein
        Zustand.
        """
        # Ein einmalig angeforderter Lauf gilt für diesen und keinen weiteren:
        # Wer die volle Kette braucht, braucht sie an einer Stelle, und alles
        # danach soll wieder so schnell sein wie vorher (§31).
        once, self._quality_once = self._quality_once, None
        return evaluate(
            self.project.document,
            self.profile,
            quality=quality or once or self.quality,
            progress=self.report_progress,
            ask=self.ask_from_worker,
            cancelled=self.cancel_signal,
            cache=self.cache,
            sources=ProjectSources(self.project, base_dir=self.base_dir),
        )

    def recompute_fully(self) -> None:
        """Einmal mit der vollen Rückfallkette rechnen (§17.2).

        Im Fenster läuft die kurze Kette — direkt und verschweißt —, weil sie
        beim Arbeiten schnell sein muss; die Stufen *Störung* und *Voxel* laufen
        erst beim Export (§31). Scheitert eine Boolesche Operation, ist der
        nächste sinnvolle Schritt genau der: dieselbe Kette einmal zu Ende
        gehen. Bis hierher war das ein Ratschlag ohne Knopf — *Voxelstufe
        erzwingen* stand im Fehlerdialog, und nichts führte ihn aus.
        """
        self._quality_once = "fine"
        self.evaluate_async()

    def evaluate_now(self) -> EvaluationResult:
        """Synchroner Durchlauf, für Kommandozeile, Tests und Export (§38)."""
        self.cancel_signal.reset()
        result = self.run_evaluation("fine")
        self.last_result = result
        self.sceneChanged.emit(result)
        return result

    def cancel(self) -> None:
        """Der eine Knopf hält beides an, was gerade laufen kann (§2.8).

        **Auch den eingereihten Nachlauf.** Ein Ersetzen behält ihn mit
        Absicht (siehe ``_on_thread_done``) — ein Nutzer-Abbruch nicht: Wer
        Abbrechen drückt, während ein zweiter Zug am Schieber wartet, las
        „Abgebrochen" in der Statuszeile, und im selben Atemzug lief der
        eingereihte Lauf an. Die Maschine rechnete weiter, das Wort stand
        daneben.
        """
        self.cancel_evaluation()
        self.cancel_agent()

    def cancel_evaluation(self) -> None:
        """Hält nur die Auswertung samt eingereihtem Nachlauf an."""

        self._cancel_by_user = True
        self._rerun_pending = False
        self.cancel_signal.cancel()

    def cancel_agent(self) -> None:
        """Hält nur den laufenden Agentenzug an."""

        self.agent_cancel.cancel()

    # --- der Agent (§26) --------------------------------------------------------

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

    def propose_async(
        self,
        request: str,
        selection: tuple[str, str] | None = None,
        *,
        backend: LLMBackend | None = None,
    ) -> None:
        """Fragt genau das an der Sendegrenze gebundene Modell.

        ``backend`` ist der unveränderliche Zug-Schnappschuss aus dem Fenster.
        Ohne ausdrückliche Übergabe bleibt der Aufruf für interne Werkzeuge und
        Tests abwärtskompatibel, liest den Zugang aber nur hier ein einziges Mal.
        """
        backend = backend if backend is not None else self.agent_backend
        if backend is None:
            self.failed.emit(AppError(tr("Für den Chat fehlt der Zugang zu einem Sprachmodell.")))
            return
        if self._agent is not None and self._agent.isRunning():
            return
        self._selection = selection
        # §23: die Ansichten entstehen HIER, im Hauptthread — VTK ist nicht
        # threadsicher, und ein zweiter OpenGL-Kontext im Arbeiter neben dem
        # lebenden Viewport ist genau die Familie von Abstürzen, die dieses
        # Projekt schon zweimal gejagt hat. Zwei kleine Bilder kosten deutlich
        # unter 200 ms (§2.8); scheitert das Rendern, läuft der Zug ohne
        # Bilder statt gar nicht (Leitprinzip 8).
        self._pending_views = ()
        if backend.supports_images and self.last_result is not None:
            from app.ui.snapshots import scene_views

            try:
                self._pending_views = scene_views(self.last_result.scene)
            except Exception:
                _log.warning("scene views failed, proposing without images", exc_info=True)
        self.agent_cancel.reset()
        self.agentBusyChanged.emit(True)
        worker = _AgentWorker(self, request, backend)
        worker.finishedWith.connect(self._on_proposal)
        worker.failedWith.connect(self._on_failed)
        worker.crashed.connect(lambda detail: self._on_failed(InternalError(detail=detail)))
        worker.finished.connect(self._on_agent_done)
        self._agent = worker
        self._leash.start(worker)

    def run_proposal(self, request: str, backend: LLMBackend | None = None) -> ProposalPreview:
        """Ein Agentenzug plus seine Vorschau. Läuft im Arbeiter (§26.5)."""
        backend = backend if backend is not None else self.agent_backend
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
            views=self._pending_views,
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
        cancelled: Any = None,
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
            # **Der Docstring versprach den Cache, der Aufruf reichte ihn nie
            # durch.** Eine Vorschau rechnete damit jedes Mal den ganzen Stapel
            # neu — bei einem Dokument mit zwanzig Schritten also
            # neunzehn Schritte, die längst gerechnet dastanden, für jede
            # Änderung an einer einzigen Zahl. Der Cache ist seit dieser Runde
            # thread-sicher; ohne das wäre es hier gefährlich, weil Auswertung,
            # Agent und Vorschau in eigenen Fäden laufen.
            cache=self.cache,
            cancelled=cancelled or NeverCancelled(),
        )
        if result.stopped_at is not None:
            # Eine angehaltene Kette ist keine Vorschau: die leere Differenz
            # sähe aus wie „keine Änderung", und das wäre gelogen.
            return result.scene, None
        difference = compare_scenes(before, result.scene) if before is not None else None
        return result.scene, difference

    def accept_proposal(self, preview: ProposalPreview) -> Transaction | None:
        """Legt den Vorschlag als eine Transaktion ins Dokument (§26.5).

        Gibt die Transaktion zurück — die automatische Übernahme (§26.5)
        zeigt ihre Kennung in der Übernommen-Leiste.
        """
        transaction = agent_apply.accept(preview.proposal, self.history)
        self._accepted[preview.proposal.request] = transaction.id if transaction else None
        self._dirty = True
        self.projectChanged.emit()
        self.evaluate_async()
        return transaction

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

    def _outdated(self, finished: _EvaluationWorker | None) -> bool:
        """Ob diese Meldung von einem Lauf kommt, den ein neuerer ersetzt hat.

        ``None`` heißt „kein Absender bekannt" und gilt als aktuell: Tests und
        die Kommandozeile rufen die Slots direkt, und ein Aufruf ohne Arbeiter
        ist keine Nachzüglermeldung, sondern der Normalfall dort.
        """
        return finished is not None and finished is not self._worker

    def _on_finished(self, result: Any, finished: _EvaluationWorker | None = None) -> None:
        if self._outdated(finished):
            # §15.3: stehen bleibt der letzte **gültige** Stand. Das Ergebnis
            # eines überholten Laufs gehört zu einem Dokument, das es nicht
            # mehr gibt — es einzublenden hieß, die leere Szene des neuen
            # Projekts über das Modell zu legen, das gerade geladen wird.
            return
        self.last_result = result
        # §17.2: die Rückfallstufe behalten, die jede Operation getragen hat —
        # damit die Datei morgen gleich nachrechnet.
        self.history.record_solvers(result.solvers)
        # §15.7: Was eine Operation über eine Rückfrage entschieden hat, gehört
        # in den Stapel — sonst wird dieselbe Frage bei jeder Auswertung erneut
        # gestellt (gemessen 99 Fenster für 7 Entscheidungen), und sobald ein
        # Ergebnis von der Platte kommt, irgendwann gar nicht mehr.
        #
        # **Ohne `_dirty` wäre es die halbe Arbeit.** Die Antwort stünde im
        # Stapel, der Titel zeigte kein `*`, und `closeEvent` sichert nur ein
        # geändertes Dokument — beim Schließen wäre sie weg und die Frage beim
        # nächsten Öffnen wieder da. Derselbe Weg wie bei `change_params`.
        #
        # Und **kein** neuer Lauf: Die Antwort ist in diesem Ergebnis schon
        # angewandt. Ein `evaluate_async()` hier wäre eine Auswertung, die nur
        # bestätigt, was gerade herauskam — beim ersten Öffnen eines Modells mit
        # unklarer Einheit also das doppelte Warten.
        # Dasselbe für die Antworten der **Zuordnung** (§21.3), und aus
        # demselben Grund — nur an einer anderen Stelle im Stapel: Was die
        # Zuordnung entscheidet, ist keine Eingabe der Operation und steht
        # darum in `matches` statt in `params`. Zwei Aufrufe statt eines
        # gemeinsamen, weil die beiden Felder verschiedene Fragen beantworten
        # und der eine ohne den anderen richtig bleibt.
        answered = self.history.record_answers(result.answers)
        matched = self.history.record_matches(result.matches)
        if answered or matched:
            self._dirty = True
            self.projectChanged.emit()
        self.sceneChanged.emit(result)

    def _on_failed(self, error: Any, finished: _EvaluationWorker | None = None) -> None:
        if self._outdated(finished):
            # Der Fehler gilt einem Stapel, an dem niemand mehr arbeitet. Ins
            # Protokoll gehört er trotzdem — nur nicht als Dialog vor einem
            # Lauf, der gerade gut läuft.
            _log.info("evaluation failed after being superseded: %s", error)
            return
        _log.warning("evaluation failed: %s", error)
        if self._backend is not None and not self._backend.available:
            # Die Gegenseite hat den Zugang abgelehnt (``llm.reject``). Das
            # gemerkte Backend wird verworfen, damit der nächste Zug neu
            # wählt — sonst schickte der Chat bis zum Neustart denselben
            # abgelehnten Schlüssel und meldete jedes Mal denselben Fehler.
            _log.info("backend %s is no longer available, choosing again", self._backend.id)
            self._backend = None
            self.backendChanged.emit()
        self.failed.emit(error)

    def _on_cancelled(self, finished: _EvaluationWorker | None = None) -> None:
        """Der Lauf hat aufgehört — und das erfuhr bisher nur die Logdatei.

        Der Balken verschwand, der Knopf verschwand, die Ansicht blieb auf dem
        Stand von vorher stehen: dasselbe Bild wie bei einer Rechnung, die
        *fertig* geworden ist. Wer nicht mitgezählt hat, konnte nicht wissen,
        ob sein Klick etwas bewirkt hat — und ob das, was er sieht, das
        Ergebnis ist oder ein alter Stand.
        """
        _log.info("evaluation cancelled")
        if self._outdated(finished):
            return
        if self._cancel_by_user:
            self._cancel_by_user = False
            self.evaluationCancelled.emit()

    def _on_proposal(self, preview: Any) -> None:
        self.proposalReady.emit(preview)

    def _on_agent_done(self) -> None:
        self.agentBusyChanged.emit(False)
        # Nicht einfach loslassen — siehe ``_leash``.
        worker, self._agent = self._agent, None
        self._leash.hold_until_done(worker)

    def _on_split_done(self, worker: Any) -> None:
        """Die Teilungssuche ist ausgelaufen — ihr Arbeiter bleibt am Leben.

        Der Absender kommt mit: Nur der aktuelle Arbeiter räumt das Feld,
        das Auslaufen eines überschriebenen räumt nichts, was ihm nicht
        gehört. (Der Vorgänger dieser Stelle war ein Lambda, das ``None`` in
        dasselbe Feld schrieb, dessen Objekt es gerade zustellte — deshalb
        reist der Arbeiter als Argument und wird nicht aus dem Feld gelesen.)
        """
        current = worker is self._split
        if current and self._split_discarded:
            # ``cancel_split`` kann den Arbeiter in der Lücke nach seinem
            # fachlichen Ende, aber vor ``finished`` treffen. Dann kommt kein
            # ``cancelled`` mehr; das endgültige Thread-Ende bestätigt trotzdem
            # genau einmal, dass der verlangte Abbruch abgeschlossen ist.
            self._confirm_split_cancelled(worker)
        if current:
            # Die Tauschform, kein nacktes Nullen des Feldes: Der Wächter in
            # test_ui verbietet jenes Muster, weil es andernorts die letzte
            # Referenz vor der Übergabe an die Leine fallen ließ.
            worker, self._split = self._split, None
        self._leash.hold_until_done(worker)
        if current:
            # Erst jetzt ist der Thread vollständig ausgelaufen.
            # ``_split_cancelled`` bestätigt vorher den fachlichen Abbruch,
            # aber dort läuft der Thread
            # noch, und ``_on_split_busy`` fragt ``_anything_running()`` —
            # das liest ``split_running`` als True und lässt Balken und
            # Abbrechen-Knopf stehen, für immer, denn danach kam nichts mehr.
            # Doppelt gemeldet ist dagegen folgenlos: Die Anzeige stellt nur
            # einen Zustand her.
            self.splitBusyChanged.emit(False)

    def _on_thread_done(self, finished: _EvaluationWorker | None = None) -> None:
        """Ein Lauf ist ausgelaufen — und nur der aktuelle darf das melden.

        **Der Nachzügler löschte die Arbeit seines Nachfolgers.** Ein Arbeiter
        ist fertig, bevor Qt sein ``finished`` zugestellt hat; in dieser Lücke
        startet der nächste Lauf und trägt sich in ``_worker`` ein. Der
        Nachzügler kam dann hier an, schrieb ``None`` in dieses Feld und
        meldete ``busyChanged(False)`` — mitten in einem Lauf, der noch fünf
        Sekunden rechnete. Sichtbar war das an der Stelle, an der jeder Nutzer
        anfängt: Eine Datei auf den Startbildschirm gezogen, verschwanden
        Balken und Abbrechen nach einer Zehntelsekunde, und die Anwendung
        rechnete den Rest ohne ein Zeichen von sich (§2.8). Unsichtbar, aber
        schwerer: ``busy`` log danach, ``wait_for_idle`` wartete nicht, und der
        nächste ``evaluate_async`` hätte einen zweiten Lauf **parallel**
        gestartet, statt ihn einzureihen (§15.6).
        """
        if self._outdated(finished):
            # Nur an die Leine — halten muss ihn jemand, melden darf er nichts.
            self._leash.hold_until_done(finished)
            return
        # Nicht einfach loslassen: der Aufruf hier kommt vom Signal des
        # Arbeiters selbst, und sein Wrapper muss die Zustellung überleben.
        # **An die Leine, nicht in ein Feld** — der nächste Lauf startet gleich
        # darunter, und ein Feld hält nur einen.
        worker, self._worker = self._worker, None
        self._leash.hold_until_done(worker)
        if self._rerun_pending:
            # Ein Ersetzen, kein Aufhören: ``busyChanged(False)`` bliebe hier
            # eine Zehntelsekunde stehen und nähme Balken und Abbrechen mit —
            # beim Ziehen an einem Schieber im Sekundentakt. Derselbe Grund,
            # aus dem ``evaluationCancelled`` einen ersetzten Lauf nicht meldet.
            self._rerun_pending = False
            self.evaluate_async()
            return
        self.busyChanged.emit(False)

    def release(self, timeout_ms: int = 10_000) -> None:
        """Alles loslassen, was diese Sitzung außerhalb von Qt hält.

        **Kein Widget und trotzdem hier**: Die Sitzung hält eine
        ``WorkerLeash`` wie die zehn Fenster, und wer eine davon aufräumt,
        soll nicht wissen müssen, ob er ein Fenster oder eine Sitzung vor
        sich hat. ``MainWindow.release`` ruft heute ``cancel`` und
        ``wait_for_idle`` einzeln — beides steht jetzt auch unter dem Namen,
        unter dem der Rest des Hauses aufräumt.

        Der fachliche Name daneben bleibt: ``wait_for_idle`` beantwortet die
        Frage „rechnet noch jemand?" und wird an Stellen gebraucht, die nicht
        aufräumen, sondern abwarten.
        """
        self.cancel()
        self.wait_for_idle(timeout_ms)
        self._leash.wait_all()

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
            # Auch Trennebenensuche, Vorschau **und der Agent** zählen: ein
            # Arbeiter, der das Fenster überlebt, nimmt beim Beenden den
            # Prozess mit.
            #
            # Der Agent fehlte hier, und das war der letzte offene Rest des
            # Absturzes, der die CI eine Woche rot hielt: Ein Vorschlag, der
            # nach dem Testende fertig wurde, stellte sein Ergebnis in ein
            # Fenster zu, das der Speicherbereiniger abgeräumt hatte. In
            # `test_chat_ui.py` traf es reproduzierbar den zehnten Test —
            # nicht den, der den Arbeiter gestartet hatte.
            worker = self._worker or self._agent or self._split or next(iter(self._previews), None)
            if worker is None:
                break
            worker.wait(50)
            application = QCoreApplication.instance()
            if application is not None:
                # Ohne `undisturbed` räumt der Speicherbereiniger hier Fenster
                # ab, während Qt ihnen gerade Ereignisse zustellt — sechs von
                # acht Läufen starben daran mit Heap Corruption. Die Messung
                # steht am Kontextmanager.
                with undisturbed():
                    application.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
