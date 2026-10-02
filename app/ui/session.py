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

import copy
import dataclasses
import threading
import time
import traceback
import weakref
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from dataclasses import dataclass, field
from functools import partial
from math import isfinite
from pathlib import Path
from typing import Any, BinaryIO, Final, NamedTuple, cast

from PySide6.QtCore import QCoreApplication, QEventLoop, QObject, Signal

from app.core import activation, expressions
from app.core.agent import apply as agent_apply
from app.core.agent.proposal import Proposal
from app.core.agent.session import AgentSession
from app.core.backends.llm import LLMBackend, first_available
from app.core.backends.mesh import GeneratedMesh
from app.core.counterpart import (
    CounterpartApplied,
    Pair,
    apply_counterpart,
    apply_thread_counterpart,
    attach_fit,
    attach_thread_fit,
)
from app.core.errors import (
    CANCEL,
    CANCEL_SPLIT,
    CHOOSE_ANOTHER_FILE,
    RETRY,
    SHOW_HISTORY,
    STOP_INSERTING,
    AppError,
    FileWriteError,
    GeometryError,
    InternalError,
    OperationCancelled,
    QuestionDeclined,
    UserError,
    ValidationError,
)
from app.core.generate import into_project as generate_into
from app.core.geom.autosplit import MARGIN
from app.core.geom.difference import SceneDifference, compare_scenes
from app.core.geom.mesh import MeshData, as_mesh_data
from app.core.geom.section import SectionPlane
from app.core.ingest.archive import is_archive, model_from_archive
from app.core.ingest.loader import read_local_payload, unreadable_file
from app.core.ingest.plan import (
    ImportPlan,
    import_plan,
    is_only_imported,
    names_in_use,
    with_selection,
)
from app.core.knowledge import print_settings, profiles
from app.core.knowledge.parts import check as part_check
from app.core.knowledge.parts.recipe import Recipe
from app.core.lid_flow import LidApplied, apply_lid
from app.core.log import get_logger
from app.core.perceive.local import CONFIRMED_FEATURE_LIMIT_TRIANGLES, forget_out_of_memory
from app.core.registry import REGISTRY, validate
from app.core.scene import (
    CancelSignal,
    EdgeTarget,
    EvaluationResult,
    History,
    NeverCancelled,
    OperationDraft,
    bundling,
    disk_backed_cache,
    foreign,
    orphans,
)
from app.core.scene.evaluate import conversion_finding, evaluate
from app.core.scene.history import Dependencies, MoveTarget, RevisionPlan, StepNeed, change_for
from app.core.scene.parameter_usage import bounds_refusal, bounds_refusal_with
from app.core.scene.project import (
    Project,
    ProjectSources,
    autosave_path,
    checksum,
    claim_recovery,
    clear_autosave,
    discard_recovery,
    embedded_source_path,
    load,
    new_project,
    next_source_id,
    recovery_token,
    save,
    write_autosave,
)
from app.core.scene.revision import Revision, revise, searched_at_the_end, step_needs
from app.core.scene.revision import commit as commit_revision
from app.core.scene.revision import dependencies as revision_dependencies
from app.core.split import (
    SplitApplied,
    SplitTarget,
    apply_line_split,
    apply_pinned_split,
    apply_planned,
    apply_split,
    bed_margin,
    plan_split,
    protected_patches,
)
from app.core.types import (
    DocumentChange,
    Feature,
    FeatureId,
    Finding,
    Fit,
    Operation,
    OpId,
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
    kind_of,
)
from app.core.units import is_close
from app.i18n import TranslatableText, _, tr
from app.ui.leash import Worker, WorkerLeash, undisturbed

_log = get_logger(__name__)


def _evaluation_busy_error() -> UserError:
    """Meldet, dass eine Folgeaktion noch kein aktuelles Ergebnis hat."""
    return UserError(
        _("Ein Auftrag läuft noch. Der Knopf wird frei, sobald er fertig ist."),
        suggestions=(RETRY,),
    )


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

    preview: EvaluationResult | None = None
    """Der Zwischenstand, gegen den die Kandidaten aufgelöst wurden."""

    candidates: tuple[tuple[str, str] | EdgeTarget, ...] = ()
    """Die Merkmale oder Kanten, zwischen denen die Frage entscheidet (§21.3).

    Je Merkmalskandidat ein Paar aus Körper und Kennung — Kennungen sind je
    Körper vergeben, und zwei Körper tragen beide ein ``hole_1``. Kennungen und
    keine Merkmalsobjekte: Die Ansicht löst sie gegen die Szene auf, die sie
    gerade zeigt; ein Objekt aus einer anderen Auswertung wäre eine zweite
    Wahrheit über dieselbe Fläche. Ein Kantenkandidat ist ein
    :class:`EdgeTarget` (P1.4c): Antworttoken, Körper und der Zug, wie ihn die
    Auswertung am aktuellen Eingang abgetastet hat — kein Schlüssel und kein
    nativer Index, denn beide könnten wieder zwei Kanten treffen.
    """

    temporary_preview: bool = False
    """Die ungeklärte Operationsausgabe gehört ausschließlich in die Ansicht."""

    project_generation: int | None = None
    worker: _EvaluationWorker | None = None
    """Der beim Auftrag gebundene Projektstand und sein Auswertungsarbeiter."""

    def reply(self, answer: str | None) -> None:
        self.answer = answer
        self.answered.set()


#: Was das Fenster nach jeder Auswertung je Körper liest — in dieser Reihenfolge.
_READ_IN_THE_WINDOW: Final = ("volume", "area", "is_watertight", "component_count")


def _warm_metrics(result: EvaluationResult, cancelled: CancelSignal) -> None:
    """Die Kennzahlen, die das Fenster liest, hier im Arbeiter anfassen.

    Volumen, Oberfläche, Wasserdichtheit und Teilezahl sind gemerkte
    Eigenschaften der Körper — beim ersten Zugriff gerechnet, danach gelesen.
    Der erste Zugriff kam aus dem Hauptthread: ``describe_selection`` beim
    Wiederherstellen der Auswahl, ``_measure_up`` über dem Prüfbericht,
    ``_update_facts`` für die Kostenzeile. Gemessen am 21.09.2026 (Review
    Leistung B1/B2): 1,5 s Hauptthread beim zweiten Öffnen von ``dense_1m``,
    15,6 s an einem STEP-Gewinde. Der Plattencache liefert frische Körper
    mit kaltem Gedächtnis; wo er sie nicht vorwärmt, tut es diese Schleife —
    ein zweites Mal kostet sie nichts.
    """
    from app.core.perceive.relations import cavity_chains

    for entry in result.scene.objects.values():
        cancelled.raise_if_cancelled()
        mesh = entry.mesh
        for name in _READ_IN_THE_WINDOW:
            try:
                getattr(mesh, name)
            except Exception as problem:  # eine Kennzahl, die nicht geht, sagt es später am Ort
                _log.info("metric %s of %s not available: %s", name, entry.id, problem)
                break
        # **Und die Merkmalsketten des Objektbaums.** ``ObjectTree.show_scene``
        # fragt je Körper ``cavity_chains``, und die Antwort liegt danach im
        # Cache des Netzes (``relations._cavity_links``) — aber der erste
        # Aufruf kam aus dem Hauptthread: 414 ms je Szenenaufbau an der
        # unterteilten Lochplatte, bei jedem Verschieben wieder, weil ein
        # bewegtes Netz ein neues Netz ist (gemessen am 22.09.2026). Hier
        # gerechnet, dort gelesen — dieselbe Frage mit denselben Merkmalen,
        # sonst trifft der Merker nicht.
        if len(entry.features) > 1:
            cancelled.raise_if_cancelled()
            try:
                cavity_chains(entry.features, as_mesh_data(mesh))
            except Exception as problem:  # die Ketten sagen es später am Ort
                _log.info("cavity chains of %s not available: %s", entry.id, problem)


#: Ab so vielen Dreiecken zeigt der Ladeweg einen Körper vor seiner
#: Merkmalserkennung (KUNDE-14). Die Erkennung braucht je Dreieck 31 µs am
#: Referenzrechner und bis zu 118 µs je nach Topologie
#: (``perceive.recognition_time``) — hier also mindestens 1,5 s, auf acht
#: Jahre alter Hardware ein Mehrfaches. Darunter wäre ein zweiter Aufbau von
#: Baum, Bericht und Ansicht Unruhe ohne Gewinn.
PICTURE_FIRST_TRIANGLES: Final = 50_000

#: Wie beim Sitzungsabbau muss ein alter Auswertungsarbeiter sein Ende bestätigen.
SYNC_EVALUATION_END_WAIT_MS: Final = 10_000

#: Eine überholte Frage bemerkt den Abbruch auch ohne Qt-Zustellung einer Antwort.
QUESTION_CANCEL_POLL_S: Final = 0.05


def _recognition_follows(picture: EvaluationResult) -> bool:
    """Ob nach diesem Bild eine Erkennung von Sekunden läuft.

    Welche Körper noch nicht erkannt sind, sagt der Lauf ohne Erkennung selbst
    (``EvaluationResult.recognition_left_out``): Was der Merker schon kennt,
    bringt auch das Bild mit, und ein Körper kann Merkmale seiner Operation
    tragen und trotzdem unerkannt sein. Über der bestätigbaren Grenze erkennt
    niemand vollständig, und ein angehaltener Stapel wird nicht erkannt.
    """
    if picture.stopped_at is not None:
        return False
    return any(
        entry.kind == "mesh"
        and isinstance(entry.mesh, MeshData)
        and entry.id in picture.recognition_left_out
        and PICTURE_FIRST_TRIANGLES
        <= entry.mesh.triangle_count
        <= CONFIRMED_FEATURE_LIMIT_TRIANGLES
        for entry in picture.scene.objects.values()
    )


def _as_picture(picture: EvaluationResult) -> EvaluationResult:
    """Das Bild, wie der Prüfbericht es zeigt, solange die Erkennung läuft.

    Der Satz über die ausgelassene Vollerkennung (``perceive.too_large``) gilt
    noch nicht: Ob erkannt wird, fragt der Lauf danach. An seiner Stelle sagt
    eine Zeile, dass die Merkmale noch kommen — der Kunde klickt sonst auf
    eine Bohrung, und nichts wird gewählt.
    """
    findings = [
        entry for entry in picture.scene.report.findings if entry.code != "perceive.too_large"
    ]
    findings.append(
        Finding(
            code="perceive.pending",
            severity="info",
            # Wahr, solange die Erkennung läuft, und auch nach einem Abbruch:
            # Die Statuszeile sagt, welches von beiden.
            message=_(
                "Die Merkmale sind noch nicht erkannt — Bohrungen und Flächen lassen "
                "sich danach einzeln wählen."
            ),
        )
    )
    scene = dataclasses.replace(picture.scene, report=Report(tuple(findings)))
    return dataclasses.replace(picture, scene=scene)


class _EvaluationWorker(Worker):
    """Ein Auswertungslauf. Besitzt nichts, meldet alles.

    **Ein großer Import zeigt sein Modell vor der Erkennung** (KUNDE-14,
    :meth:`Session.picture_first`). Das Piratenschiff mit 1,2 Mio. Dreiecken
    stand in 0.5.1 erst nach 60 s im Bild — 8 s Einlesen, danach 51 s
    Merkmalserkennung unter dem Ladeschleier. Der Arbeiter rechnet dann
    zweimal: erst ohne Erkennung (``detect_features=False``, derselbe Weg wie
    die Live-Vorschau) und meldet das über ``pictureWith``; dann den ganzen
    Lauf, der die Geometrie aus dem Cache nimmt — dort liegt die rohe Ausgabe,
    nicht die erkannte. Eine Rückfrage des ersten Laufs beantwortet der zweite
    aus dem Gedächtnis (``_pending.replay``), nicht noch einmal am Bildschirm.
    """

    finishedWith = Signal(object)
    failedWith = Signal(object)
    cancelled = Signal()
    pictureWith = Signal(object)

    def __init__(self, session: Session, *, picture_first: bool = False) -> None:
        super().__init__()
        self._session = session
        self._project_generation = session._project_generation
        self._picture_first = picture_first

    def _evaluate(self, session: Session) -> EvaluationResult:
        """Der ganze Lauf — beim Ladeweg mit dem Bild davor."""
        if not self._picture_first:
            return session.run_evaluation()
        asked: dict[tuple[str, tuple[str, ...]], str | None] = {}
        session._pending.asked = asked
        try:
            picture = session.run_evaluation(detect_features=False)
        finally:
            session._pending.asked = None
        if picture.stopped_at is not None and not picture.scene.objects:
            # Schon der erste Schritt hielt an: Es gibt nichts zu erkennen, und
            # ein zweiter Lauf käme nur ein zweites Mal an derselben Stelle an.
            return picture
        if _recognition_follows(picture):
            _warm_metrics(picture, session.cancel_signal)
            self.pictureWith.emit(_as_picture(picture))
        session._pending.replay = asked
        try:
            result = session.run_evaluation()
        finally:
            session._pending.replay = None
        # Die Antworten des ersten Laufs trägt auch der zweite: Den Ladeschritt
        # findet er im Cache, und der Eintrag reist mit ihnen (§15.7).
        return result

    def work(self) -> None:
        session = self._session
        session._pending.project_generation = self._project_generation
        session._pending.worker = self
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

            result = self._evaluate(session)
            if session.pending_orphan_check:
                # **Einmal** geprüft, auch wenn der Nutzer die Frage abbricht:
                # Der Merker fällt vor der Schleife, nicht danach — sonst
                # warf ``OperationCancelled`` uns vor die Zeile, und jede
                # weitere Auswertung stellte dieselbe Frage neu (§21.3).
                session.pending_orphan_check = False
                rewritten = False
                while True:
                    session._pending.preview = result
                    try:
                        check = orphans.check(
                            session.project.document,
                            result.scene,
                            session.ask_from_worker,
                            announce=session.announce_candidates,
                            pending=orphans.pending_references(
                                session.project.document, result.stopped_at
                            ),
                            blocked=result.blocked_references,
                        )
                    finally:
                        session._pending.preview = None
                    outside.extend(check.findings)
                    if not check.changed:
                        break
                    rewritten = True
                    result = session.run_evaluation()
                if rewritten:
                    # Erst melden, wenn der Arbeiter mit dem Dokument fertig
                    # ist: Die Slots lesen es im Hauptthread, und die nächste
                    # Runde von ``orphans._rewrite`` schrieb sonst noch daran.
                    session._dirty = True
                    session.projectChanged.emit()
            result = _with_findings(result, outside)
            _warm_metrics(result, session.cancel_signal)
        except OperationCancelled:
            self.cancelled.emit()
        except AppError as error:
            self.failedWith.emit(error)
        else:
            self.finishedWith.emit(result)
        finally:
            session.announce_question(None, ())
            session._pending.project_generation = None
            session._pending.worker = None

    def release_finished_references(self) -> None:
        """Den nur für diesen Lauf gehaltenen Sitzungsbezug lösen.

        Der Arbeiter besitzt während der Rechnung die Sitzung. Seine
        Ergebnissignale tragen zusätzlich Partials zurück zu ihr und zu ihm
        selbst. Nach der von :class:`WorkerLeash` bestätigten letzten
        Ereignisrunde werden genau diese eigenen Verbindungen gelöst; Qts
        ``destroyed``-Vertrag bleibt unangetastet.
        """
        del self._session
        super().release_finished_references()


class _ArchiveWorker(Worker):
    """Holt das Modell aus einem ZIP, bevor irgendetwas eingebettet wird.

    Im Arbeiter, weil ein Archiv bis zur Importgrenze entpackt werden kann,
    und mit der Frage des Kerns, weil ein Archiv mehrere Modelle tragen kann
    (Regel 21): ``ask`` ist :meth:`Session.ask_from_worker` — derselbe Dialog
    wie jede andere Rückfrage.
    """

    readyWith = Signal(str, object)
    failedWith = Signal(object)
    dropped = Signal()

    def __init__(self, name: str, payload: bytes, ask: Any) -> None:
        super().__init__()
        self._name = name
        self._payload = payload
        self._ask = ask

    def work(self) -> None:
        try:
            name, payload = model_from_archive(self._name, self._payload, self._ask)
        except OperationCancelled:
            self.dropped.emit()
        except AppError as error:
            self.failedWith.emit(error)
        else:
            self.readyWith.emit(name, payload)

    def release_finished_references(self) -> None:
        """Das Archiv nach seiner Zustellung lösen — es kann Hunderte MB tragen."""
        del self._payload, self._ask
        super().release_finished_references()


#: Wie lange das Öffnen eines Projekts ohne Ereignisrunde auf das Lesen
#: wartet — eine lokale Platte antwortet darunter, und dann gibt es kein
#: Zwischenbild (dieselbe Zahl wie ``MainWindow.RECENT_WAIT_S``).
PROJECT_READ_WAIT_S: Final = 0.05


def _load_beside_the_window(path: Path) -> Project:
    """Eine Projektdatei lesen, ohne dass das Fenster dabei stillsteht.

    **Ein Dateizugriff ist eine Netzfrage** (RM-224) — auch für ein Projekt aus
    „Zuletzt geöffnet“ auf einem Netzlaufwerk. ``load`` lief im Hauptfaden: Um
    5 s verzögertes Lesen hielt das Fenster 5,1 s an, ein totes Laufwerk bis
    zu seinem Zeitlimit (Durchsicht 0.5.1,
    ``konzepte/nachweise-release-0.5.1/sonden/fenster/p22_projekt_oeffnen.py``). Gelesen
    wird deshalb in einem Daemon-Faden; solange er liest, stellt der
    Hauptfaden Ereignisse zu — Malen, Größe, Zeitgeber —, aber **keine
    Eingaben**: Das Öffnen bleibt ein Schritt, mitten in dem niemand das alte
    Projekt weiterbearbeitet. Ein ``stat``, das hängt, lässt sich ohnehin nicht
    abbrechen; der Faden hält das Beenden nicht auf.

    Ohne laufende Anwendung (Kommandozeile) und bei einer lokalen Platte, die
    unter :data:`PROJECT_READ_WAIT_S` antwortet, ist es derselbe gerade Aufruf
    wie vorher. Was ``load`` wirft, wirft auch dies.
    """
    application = QCoreApplication.instance()
    if application is None:
        return load(path)
    box: list[tuple[bool, object]] = []

    def read() -> None:
        try:
            box.append((True, load(path)))
        except BaseException as problem:  # im Hauptfaden neu geworfen
            box.append((False, problem))

    reader = threading.Thread(target=read, name="project-read", daemon=True)
    reader.start()
    reader.join(PROJECT_READ_WAIT_S)
    while reader.is_alive():
        with undisturbed():
            application.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
        reader.join(0.02)
    succeeded, value = box[0]
    if not succeeded:
        raise cast(BaseException, value)
    return cast(Project, value)


class _ReadWorker(Worker):
    """Liest eine Modelldatei von der Platte, bevor irgendetwas eingebettet wird.

    **Ein Dateizugriff ist eine Netzfrage** (RM-224). Liegt das Modell auf
    einem Laufwerk, das gerade nicht antwortet, wartet Windows sein Zeitlimit
    ab — gemessen 21 s an einer nicht erreichbaren Adresse —, und so lange
    stand das Fenster, das die Datei öffnen sollte. Auch im Normalfall ist es
    Arbeit im Hauptthread, die dort nicht hingehört: rund 180 ms an der
    Siebhalter-3MF.

    Erwartete Fehler (verschoben, gesperrt, zu groß) kommen aus
    :func:`read_local_payload` schon als Hinweis mit Weg und gehen über
    ``failedWith`` hinaus; eingebettet wird im Hauptthread.

    **Und *Abbrechen* wirkt, auch wenn das Laufwerk nicht antwortet.** Ein
    ``stat`` oder ``read`` lässt sich nicht unterbrechen; stand es direkt in
    ``work``, galt der Klick erst, wenn das System aufgab — gemessen an einem
    um 8 s verzögerten Lesen: frei nach 6,1 s statt sofort, bei einem toten
    Netzlaufwerk nach dessen Zeitlimit. Gelesen wird deshalb in einem
    **Daemon-Thread** (dieselbe Begründung wie bei „Zuletzt geöffnet“,
    ``MainWindow._show_recent``), und der Arbeiter sieht alle 50 ms nach
    :attr:`cancel`. Abgebrochen meldet er ``stopped`` und endet; der
    Daemon-Thread läuft aus, und seine Antwort holt niemand ab. So hält auch
    das Schließen des Fensters keinen ``QThread`` fest, der in einem ``stat``
    hängt.
    """

    readyWith = Signal(object)
    failedWith = Signal(object)
    stopped = Signal()

    #: Wie oft der Arbeiter nach *Abbrechen* sieht, während der Lesefaden wartet.
    POLL_S: Final = 0.05

    def __init__(self, path: Path) -> None:
        super().__init__()
        self._path = path
        self.cancel = CancelSignal()

    def work(self) -> None:
        box: list[tuple[str, object]] = []
        reader = threading.Thread(
            target=self._read_into, args=(box,), name="model-read", daemon=True
        )
        reader.start()
        while reader.is_alive():
            if self.cancel.is_cancelled:
                self.stopped.emit()
                return
            reader.join(self.POLL_S)
        if self.cancel.is_cancelled or not box:
            self.stopped.emit()
            return
        kind, value = box[0]
        if kind == "ready":
            self.readyWith.emit(value)
        elif kind == "failed":
            self.failedWith.emit(value)
        else:
            # Was niemand erwartet hat, geht den Weg jedes Arbeiters
            # (``crashed``) — nur aus dem Lesefaden hierher getragen.
            raise RuntimeError(str(value))

    def _read_into(self, box: list[tuple[str, object]]) -> None:
        """Im Lesefaden: das Ergebnis oder den Hinweis in ``box`` legen."""
        try:
            payload = read_local_payload(self._path)
        except AppError as error:
            box.append(("failed", error))
        except OSError as problem:
            # Wie in der Quellenwahl: Das Lesen selbst meldet sich schon als
            # Hinweis, was hier ankommt, stammt aus dem Weg um die Datei.
            box.append(("failed", unreadable_file(self._path, problem)))
        except Exception:  # wird im Arbeiter zu ``crashed``
            box.append(("crashed", traceback.format_exc()))
        else:
            box.append(("ready", payload))


class _AutosaveWorker(Worker):
    """Schreibt die automatische Sicherung, ohne das Fenster anzuhalten (§38).

    **Die Sicherung lief im Zeitgeber des Hauptfadens** und schrieb das ganze
    Projekt samt eingebetteter Modelle neu. Gemessen am Mausoleum-Drachen
    (33 MB Sicherung): 0,8 bis 1,0 s stand das Fenster, alle zwei Minuten,
    solange das Projekt ungespeichert war — und nach einem Import ist es das
    (Durchsicht 0.5.1,
    ``konzepte/nachweise-release-0.5.1/sonden/fenster/p08_sicherung.py``). Geschrieben wird
    eine Kopie des Dokuments von jetzt; die Quelldaten sind unveränderliche
    Bytes und werden geteilt.

    Ein Schreibfehler (volles Laufwerk, gesperrte Datei) ist ein Ergebnis und
    kein Absturz: Er kommt über ``done`` zurück, und das Fenster sagt es.
    """

    done = Signal(object)
    """``None`` oder der ``AppError`` des Schreibens."""

    def __init__(self, project: Project, path: Path | None, token: str) -> None:
        super().__init__()
        self._project = project
        self._path = path
        self._token = token

    def work(self) -> None:
        try:
            write_autosave(self._project, self._path, self._token)
        except AppError as error:
            self.done.emit(error)
        except (OSError, ValueError) as problem:
            self.done.emit(
                FileWriteError(
                    target=autosave_path(self._path, self._token).name,
                    detail=getattr(problem, "strerror", None) or str(problem),
                )
            )
        else:
            self.done.emit(None)


class _PlanWorker(Worker):
    """Der Einleseplan einer Datei. Besitzt nichts, meldet alles.

    **Warum überhaupt ein Arbeiter für einen Plan.** ``import_plan`` klingt
    billig und ist es bei einer STL auch. Bei einer 3MF zählt es die Körper
    und Dreiecke der ganzen Baugruppe, bevor eine Operation entsteht (§11,
    §32) — und das dauert: An einer Datei von 63 MB mit 32 Körpern und
    5 476 596 Dreiecken sind es 14,1 s, gemessen am 03.09.2026. Das Lesen von
    der Platte dagegen kostet 0,09 s.

    Vierzehn Sekunden im Hauptthread sind kein Wartezeiger, sondern ein
    eingefrorenes Fenster; Windows schreibt ab etwa fünf Sekunden „Keine
    Rückmeldung" in die Titelleiste. Deshalb hier.

    Der Plan ändert nichts am Dokument — er liest die Nutzlast und gibt einen
    ``ImportPlan`` zurück. Was danach kommt (``apply``), gehört in den
    Hauptthread und steht in ``Session._on_plan_ready``.
    """

    readyWith = Signal(object, str)
    failedWith = Signal(object, str)

    def __init__(
        self,
        source_id: str,
        name: str,
        payload: bytes,
        unit: str,
        first_model: bool,
        taken: tuple[str, ...],
        progress: Any,
    ) -> None:
        super().__init__()
        self._source_id = source_id
        self._name = name
        self._payload = payload
        self._unit = unit
        self._first_model = first_model
        self._taken = taken
        self._progress = progress

    def work(self) -> None:
        try:
            plan = import_plan(
                self._source_id,
                self._name,
                self._payload,
                self._unit,
                first_model=self._first_model,
                taken=self._taken,
                progress=self._progress,
            )
        except AppError as error:
            self.failedWith.emit(error, self._source_id)
        else:
            self.readyWith.emit(plan, self._source_id)

    def release_finished_references(self) -> None:
        """Eingabedaten und Fortschrittsziel nach ihrer Zustellung lösen."""
        del self._payload, self._progress
        super().release_finished_references()


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


class _AgentWorker(Worker):
    """Ein Zug des Agenten, abseits des GUI-Threads (§26.5)."""

    finishedWith = Signal(object)
    failedWith = Signal(object)

    def __init__(
        self, session: Session, request: str, backend: LLMBackend, snapshot: _Snapshot
    ) -> None:
        super().__init__()
        self._session = session
        self._request = request
        self._backend = backend
        self._snapshot = snapshot

    def work(self) -> None:
        session = self._session
        try:
            preview = session.run_proposal(self._request, self._backend, snapshot=self._snapshot)
        except OperationCancelled:
            self.failedWith.emit(AppError(tr("Der Vorschlag wurde abgebrochen.")))
        except AppError as error:
            self.failedWith.emit(error)
        else:
            self.finishedWith.emit(preview)

    def release_finished_references(self) -> None:
        """Sitzung und Anfrage nach dem zugestellten Agentenzug lösen."""
        del self._session, self._request, self._backend, self._snapshot
        super().release_finished_references()


class _PreviewWorker(Worker):
    """Eine Dialog-Vorschau, abseits des GUI-Threads (§18.7, §2.8).

    Dieselbe Begründung wie beim Agentenvorschlag: die Differenz sind zwei
    Boolesche Operationen je Körper. ``generation`` stempelt das Ergebnis —
    wer weitertippt, ersetzt die Anfrage, und eine verspätete Antwort auf
    eine alte Frage wird verworfen statt gezeigt.
    """

    done = Signal(int, object)
    #: Warum es keine Vorschau gibt — der Satz aus dem Kern, den der Dialog
    #: sonst erst beim Übernehmen zu sehen bekäme.
    explained = Signal(int, str)
    #: Dass auf einem vergröberten Netz gerechnet wurde, samt der Dreieckszahl
    #: davor — das Band sagt es, statt ein genaues Bild vorzutäuschen.
    coarse = Signal(int, int)
    #: Wie weit die Rechnung ist, samt dem laufenden Schritt — ab zwei Sekunden
    #: zeigt das Fenster daraus Balken und *Abbrechen* (§2.8).
    progressed = Signal(int, float, str)
    #: Die Handlung, die der Kern dem Grund mitgab (``Action.id``) — kommt
    #: **vor** :attr:`explained`, damit das Fenster beim Satz schon weiß, ob
    #: *Übernehmen* danach noch eine sinnvolle Handlung ist. Was die Kennung
    #: bedeutet, entscheidet die Oberfläche; hier reist nur weiter, was die
    #: Ausnahme ohnehin trägt (§2.7).
    advised = Signal(int, str)
    #: Die Absage selbst, mit Werten und Handlungen — ein ``AppError`` aus der
    #: Vorabzählung oder der ``Finding`` des Halts. Das Band trägt den Satz, der
    #: Dialog die Knöpfe, die dort etwas bewirken (*Die kleinste Kantenlänge
    #: nehmen, die noch geht.*, RESTVERLAUF-04). Kommt vor :attr:`explained`.
    refused = Signal(int, object)
    #: Wie viele Dreiecke der vorgeschaute Schritt dem Körper gibt — ``(davor,
    #: danach, Obergrenze, gezählt)``, wo die Operation die Form zusagt
    #: (``OperationSpec.retriangulates``). Das ist die Auskunft ihrer Vorschau.
    counted = Signal(int, object)
    #: Die Vorschau hielt an einer Rückfrage (:class:`_QuestionPending`) — kommt
    #: **vor** :attr:`explained`. Das ist keine Absage: Die Frage stellt erst
    #: *Übernehmen*, und deshalb darf der Satz im Band den Knopf nicht sperren
    #: (RM-389).
    asked = Signal(int)

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
            _scene, difference, reason = self._compute()
        except _QuestionPending:
            self.asked.emit(self._generation)
            self.explained.emit(
                self._generation,
                str(_("Eine Rückfrage steht an — sie kommt beim Übernehmen.")),
            )
            self.done.emit(self._generation, None)
        except OperationCancelled:
            self.done.emit(self._generation, None)
        except AppError as error:
            # Beim Tippen entstehen ungültige Zwischenstände; der echte
            # Fehler kommt beim Anwenden als Vorschlag (§2.7). Die Vorschau
            # zeigt dann nichts Neues — **sagt aber, warum** (13.09.2026):
            # Gemessen über alle Operationsdialoge standen elf mit leerem Bild
            # und dem Band „Vorschau — noch nicht übernommen" da, und der
            # Grund — „Diese Ebene teilt das Objekt nicht", „Der Körper ist
            # auf dieser Höhe massiv" — wartete bis zum Übernehmen.
            #
            # **Und die Handlung reist mit** (14.09.2026): „Erst reparieren,
            # dann aushöhlen" nennt einen Schritt, der *vor* das Übernehmen
            # gehört — der Knopf daneben blieb trotzdem anklickbar.
            self.refused.emit(self._generation, error)
            advice = _advice_of(error)
            if advice:
                self.advised.emit(self._generation, advice)
            self.explained.emit(self._generation, _reason_of(error))
            self.done.emit(self._generation, None)
        else:
            if reason:
                self.explained.emit(self._generation, reason)
            self.done.emit(self._generation, difference)

    def release_finished_references(self) -> None:
        """Vorschaukontext nach Ergebnis und Fertigsignal lösen."""
        del self._session, self._compute
        super().release_finished_references()


@dataclass(frozen=True, slots=True)
class _Snapshot:
    """Der Stand, auf dem eine Vorschau oder ein Agentenzug rechnet — im Hauptfaden gezogen.

    Vorschau und Agent rechnen im Arbeiter; das Dokument gehört dem
    Hauptfaden, der es währenddessen ändern darf (ein Übernehmen, ein
    Import, eine Antwort). Bis zum 22.09.2026 kopierte der **Arbeiter** das
    lebende Dokument (``copy.deepcopy`` in ``_preview_outcome``, in
    ``_coarse_before`` und im Agentenzug) und las Profil und Szene davor
    ebenfalls erst dort: Traf die Kopie auf eine Änderung, rechnete die
    Vorschau einen Stand, den es nie gab — mit dem Schritt von gleich, aber
    der Szene von vorhin —, und ein Wörterbuch, das sich beim Kopieren
    änderte, riss den Arbeiter mit „dictionary changed size during
    iteration" ab. Die Kopie kostet an den Beispielprojekten unter einer
    halben Millisekunde; gezogen wird sie dort, wo das Dokument lebt.
    """

    document: Any
    before: Any
    profile: Profile

    @classmethod
    def of(cls, session: Session, change_op: OpId | None = None) -> _Snapshot:
        """Zieht den Stand jetzt — nur im Hauptfaden aufrufen.

        Bei einer Einfügemarke der Stand davor (P7.1): Vorschau und Agent
        rechnen dort, wo der neue Schritt hinkommt. Wer einen Schritt hinter
        der Marke ändert, bekommt den ganzen Verlauf — dort steht der Schritt.
        """
        import copy

        result = session.last_result
        shown = session.displayed_document()
        if change_op is not None and all(entry.id != change_op for entry in shown.ops):
            shown = session.project.document
        return cls(
            document=copy.deepcopy(shown),
            before=result.scene if result is not None else None,
            profile=session.evaluation_profile,
        )


def _parameter_title(parameter: Parameter) -> TranslatableText:
    """Der Verlaufseintrag einer Parameteränderung — mit der Beschriftung der Leiste.

    Im Verlauf stand „Parameter breite“: der Schlüssel, den der Kunde nirgends
    sieht, während die Parameterleiste „Breite“ zeigt (``parameter.title or
    name``, ``ParameterPanel.show_document``). Übersetzbar gespeichert, wie die
    Titel des Löschens: Der Eintrag folgt der Sprache, auch nach dem Laden.
    """
    return _("Parameter {name}", name=parameter.title or parameter.name)


def _reason_of(error: AppError) -> str:
    """Der Satz, der den Fehler erklärt — das Detail, wo es eines gibt.

    Dieselbe Regel wie ``evaluate._finding_from``: Der Titel nennt die Art
    („Ein Wert liegt außerhalb des zulässigen Bereichs"), das übersetzte
    Detail den Grund. Eine blanke Zeichenkette als Detail ist eine Notiz für
    das Protokoll und kein Satz für den Kunden.
    """
    detail = error.detail
    if isinstance(detail, TranslatableText):
        return str(detail)
    return str(error.title)


def _advice_of(error: AppError) -> str:
    """Die vorrangige Handlung dieses Fehlers — ihre Kennung, sonst leer.

    Der Satz sagt, was nicht geht; die Handlung sagt, was hilft. Das Band
    trägt den Satz, und das Fenster entscheidet an dieser Kennung, ob
    *Übernehmen* überhaupt noch etwas bewirken kann
    (``MainWindow._APPLY_BLOCKING_ADVICE``). Hier wird nicht gewertet — jede
    Ausnahme trägt ihre Vorschläge ohnehin (Regel 17), und welche davon eine
    Sperre wert ist, ist eine Frage der Bedienung und keine des Kerns.

    Die **erste vorrangige**: ``suggestions`` steht nach Rang, und
    ``primary`` markiert die, die der Kern empfiehlt. *Abbrechen* ist
    ausdrücklich kein Rat und trägt die Marke nicht.
    """
    for action in error.suggestions:
        if action.primary:
            return str(action.id)
    return ""


def _warning_of(result: EvaluationResult, previewed: tuple[OpId, ...]) -> str:
    """Was die vorgeschauten Schritte selbst gemeldet haben — Warnung zuerst.

    Gefragt wird nur über einer **leeren** Differenz, und dort ist jeder
    Befund des Schritts die bessere Auskunft als „am Volumen ändert sich
    nichts": Er sagt, *warum* nichts geschah. Bis zum 14.09.2026 zählten hier
    nur Warnungen und Fehler, mit der Begründung, ein Info-Befund
    („Ausgehöhlt. Die Wandstärke stimmt …") sei eine Zusage. Über einer leeren
    Differenz gibt es diese Zusage nicht — dort steht Info für „der Körper hat
    schon weniger Dreiecke als das Ziel" (``mesh.already_below_target``),
    „hier war nichts zu reparieren", „es gibt kein Skelett".

    Warnung und Fehler behalten den Vortritt: Sie wiegen schwerer, und ein
    Schritt kann beides melden.
    """
    plain = ""
    for finding in result.scene.report.findings:
        if finding.op_id not in previewed:
            continue
        if finding.severity in ("warning", "error"):
            return str(finding.message)
        if not plain:
            plain = str(finding.message)
    return plain


#: Ab wie vielen Dreiecken ein Körper für die Vorschau verkleinert wird (§2.8).
#:
#: Gemessen am 14.09.2026 über ``Session._preview_outcome`` — eine Bohrung
#: Ø 5 durch eine Kugel, Entwurfsqualität, warmer Cache:
#:
#: ===========  ==========  ==========  =========
#: Dreiecke     zusammen    evaluate    compare
#: ===========  ==========  ==========  =========
#: 20 480       0,16 s      0,11 s      0,05 s
#: 81 920       0,63 s      0,47 s      0,16 s
#: 327 680      2,16 s      1,58 s      0,58 s
#: ===========  ==========  ==========  =========
#:
#: Die Reihe ist linear — rund 6,6 µs je Dreieck —, und die Sekunde aus §2.8
#: fällt bei etwa 150 000. Das ist diese Zahl: nicht die Grenze, ab der es
#: langsam *wirkt*, sondern die, ab der die Zusage „unter einer Sekunde ein
#: Bild" ohne Hilfe nicht mehr zu halten ist.
COARSE_PREVIEW_ABOVE: Final = 150_000

#: Worauf verkleinert wird: auf die Schranke selbst.
#:
#: Der Anzeigeweg nimmt zuerst den exakten Kern, beginnend beim Sehnenfehler,
#: mit dem beide Kerne tessellieren (0,05 mm), und hält an, sobald das Ziel
#: erreicht ist; nur wo das nicht gelingt, legt er im Raster zusammen. Das
#: Kernergebnis ist geschlossen, das Raster oft nicht — und auf einem offenen
#: groben Netz scheitert jede Bohrung, die Vorschau rechnet dann genau.
#:
#: Bis zum 26.09.2026 stand hier 50 000. Figuren bringt der Kern nicht so
#: weit: den Spiderman nicht unter 122 952 Dreiecke, das Piratenschiff nicht
#: unter 64 468, den Eiffelturm nicht unter 57 680 — jenseits dieses
#: Minimums steigt die Zahl mit der Toleranz wieder. Alle drei gingen ins
#: Raster, und jede Zahl im Bohrdialog rechnete genau, 13 bis 37 s (RM-212).
#: Mit der Schranke als Ziel nimmt die grobe Vorschau das geschlossene
#: Kernergebnis, und das bleibt unter der Größe, ab der eine Vorschau die
#: Sekunde nicht mehr hält. Genauer wird sie dabei auch: Ein höheres Ziel
#: hält den Kern öfter beim ersten, feinsten Schritt.
COARSE_PREVIEW_TARGET: Final = COARSE_PREVIEW_ABOVE


def _quiet_progress(_fraction: float, _text: str) -> None:
    """Keine Fortschrittsmeldung — Agentenweg und Aufrufe ohne Fenster fragen nicht."""


def _coarse_params() -> dict[str, Any]:
    """Womit die grobe Stufe verkleinert — eine Stelle für beide Wege.

    **Der Anzeigeweg** (``method="fast"``, Entscheidung Robert vom 23.09.2026):
    Kern nach Sehnenfehler, dann Raster, ohne Messung. Die Vorschau ist ein
    Bild und kein Dokumentstand; übernommen wird genau. Der Weg der Operation
    stand an der Lochplatte mit 815 104 Dreiecken 24 s im Quadrik-Solver und
    in der Messung danach — und sein Netz war offen, sodass jede Bohrung
    darauf die Boolesche Kette hinunterlief (grob 22 s je Zahl, genau 13 s).
    """
    return {"triangles": COARSE_PREVIEW_TARGET, "method": "fast"}


#: Werte, mit denen ein Schritt ein Merkmal, eine Fläche oder Kanten **des
#: Eingangsnetzes** benennt. Eine vorgeschaltete Verkleinerung erkennt das
#: Netz neu, und die Kennung gibt es danach nicht mehr — oder sie meint ein
#: anderes Loch.
FEATURE_REFERENCE_PARAMS: Final = ("at_feature", "at_features", "face", "edges")


def _names_a_feature(params: Mapping[str, Any]) -> bool:
    """Ob diese Werte etwas am Eingangsnetz beim Namen nennen.

    **Dann rechnet die Vorschau genau.** Bis zum 22.09.2026 lag die grobe
    Stufe auch vor *Bohrung ändern* und *Merkmal versetzen*: Ab 150 000
    Dreiecken verkleinerte sie den Körper, die Erkennung lief auf dem groben
    Netz neu, und der Schritt fand sein Merkmal nicht mehr — an der
    Senkplatte mit 311 296 Dreiecken stand statt einer Vorschau „Dieses
    Merkmal gibt es an diesem Objekt nicht.", und Übernehmen blieb gesperrt,
    weil es eine dargestellte Vorschau verlangt (Maßeditor im Bild, Weg 1).
    """
    return any(params.get(name) not in (None, "", (), []) for name in FEATURE_REFERENCE_PARAMS)


def _triangles_of(scene: Any) -> int:
    """Wie viele Dreiecke die Szene trägt — für das Band über der Vorschau."""
    if scene is None:
        return 0
    return sum(int(getattr(entry.mesh, "triangle_count", 0)) for entry in scene.objects.values())


def _coarse_steps_before(working: Any, index: int, scene: Any) -> list[Operation]:
    """Verkleinerungsschritte **vor** den Schritt an ``index`` einer Dokumentkopie legen.

    Das Gegenstück zu :func:`_coarse_drafts` für das Ändern eines Schritts
    (§15.4): Dort hängen die Verkleinerungen ans Ende des Stapels, hier
    müssen sie vor den geänderten Schritt, damit **er** auf dem groben Netz
    rechnet. Ein Stapel kennt keine Lücken zwischen seinen Nummern; die
    Schritte ab ``index`` rücken um so viele Nummern auf, wie Verkleinerungen
    davor kommen, und die neuen Schritte nehmen die frei gewordenen. Das geht
    nur in der Kopie, die niemand speichert — Transaktionen und Verweise auf
    Schrittnummern bleiben dort unbenutzt, ``evaluate`` liest nur den Stapel.

    Verkleinert wird je Netz-Eingang des Schritts über der Schwelle, gemessen
    an der Szene, die das Fenster zeigt: Ob ein Körper vor dem Schritt schon
    so groß war, ist ohne Auswertung nicht zu wissen, und ein Schritt an einem
    Körper unter dem Ziel gibt ihn unverändert zurück. Ein Textur-Schritt mit
    Flächenbezug bleibt aus demselben Grund genau wie bei den Entwürfen.
    Zurück kommen die eingefügten Schritte; leer, wenn es nichts zu
    verkleinern gibt.
    """
    step = working.ops[index]
    if step.op == "apply_texture" and step.params.get("coverage") == "whole_face":
        return []
    targets = [
        object_id
        for object_id in step.inputs
        if (entry := scene.objects.get(object_id)) is not None
        and kind_of(entry.mesh) == "mesh"
        and int(getattr(entry.mesh, "triangle_count", 0)) > COARSE_PREVIEW_ABOVE
    ]
    if not targets:
        return []
    shift = len(targets)
    first_id = int(step.id)
    working.ops[index:] = [
        dataclasses.replace(entry, id=OpId(int(entry.id) + shift)) for entry in working.ops[index:]
    ]
    inserted = [
        Operation(
            id=OpId(first_id + offset),
            op="decimate_mesh",
            inputs=(object_id,),
            outputs=(object_id,),
            params=_coarse_params(),
        )
        for offset, object_id in enumerate(targets)
    ]
    working.ops[index:index] = inserted
    return inserted


def _coarse_drafts(scene: Any) -> list[OperationDraft]:
    """Welche Körper vor der Vorschau verkleinert werden — und womit.

    Nur Netze werden vergröbert. Ein exakter Körper besitzt ebenfalls eine
    Tessellierung für die Anzeige; ihre Größe rechtfertigt keine Umwandlung
    des Eingabekörpers vor der eigentlichen Vorschau.
    """
    if scene is None:
        return []
    return [
        OperationDraft(op="decimate_mesh", params=_coarse_params(), inputs=(object_id,))
        for object_id, entry in scene.objects.items()
        if kind_of(entry.mesh) == "mesh"
        and int(getattr(entry.mesh, "triangle_count", 0)) > COARSE_PREVIEW_ABOVE
    ]


def _kernel_gave_up(result: EvaluationResult) -> bool:
    """Ob die Kette an einer Grenze des Rechenkerns hielt — und nicht an einem Wert.

    ``evaluate`` schreibt den Halt als ``op.<Operation>.<Ausnahme>``
    (``_finding_from``). Eine ``GeometryError`` — die Boolesche Kette ist
    erschöpft, ein Körper ist keiner — hängt am Netz, und in der groben Stufe
    ist das Netz nicht das des Kunden. Gemessen am 23.09.2026: Am Eiffelturm
    (312 938 Dreiecke), am Voronoi-Spiderman und am Piratenschiff sagte die
    grobe Vorschau „Auch die letzte Rückfallstufe hat kein brauchbares
    Ergebnis geliefert", wo die genaue Vorschau ein Ergebnis hat. Ein
    ungültiger Wert dagegen bleibt am groben Netz derselbe und braucht keine
    zweite Rechnung.
    """
    if result.stopped_at is None:
        return False
    kinds: set[str] = set()
    pending: list[type] = [GeometryError]
    while pending:
        kind = pending.pop()
        kinds.add(kind.__name__)
        pending.extend(kind.__subclasses__())
    return any(
        finding.op_id == result.stopped_at and finding.code.rsplit(".", 1)[-1] in kinds
        for finding in result.scene.report.findings
    )


def _stop_reason(result: EvaluationResult) -> str:
    """Warum die Kette anhielt — der Befund, der den Halt trägt.

    Alle Stellen, die ``stopped_at`` setzen, hängen vorher einen Befund mit
    dieser ``op_id`` an (``evaluate._why_it_stopped`` liest ihn fürs
    Protokoll). Hier derselbe Befund für das Band über der Vorschau.
    """
    if result.stopped_at is None:
        return ""
    blamed = [
        finding for finding in result.scene.report.findings if finding.op_id == result.stopped_at
    ]
    return str(blamed[-1].message) if blamed else ""


def _stop_advice(result: EvaluationResult) -> str:
    """Die vorrangige Handlung desselben Befunds — ihre Kennung, sonst leer.

    Der Befund, der den Halt trägt, trägt auch die Auswege (Regel 17). Das
    Band zeigt den Satz; die Kennung entscheidet im Fenster darüber, ob
    *Übernehmen* noch etwas bewirken kann — „Erst reparieren, dann aushöhlen"
    nennt einen Schritt, der davor gehört.
    """
    if result.stopped_at is None:
        return ""
    blamed = [
        finding for finding in result.scene.report.findings if finding.op_id == result.stopped_at
    ]
    if not blamed:
        return ""
    for action in blamed[-1].suggestions:
        if action.primary:
            return str(action.id)
    return ""


def _stop_finding(result: EvaluationResult) -> Finding | None:
    """Der Befund, der den Halt trägt — mit Werten und Handlungen, für die Knöpfe im Dialog."""
    if result.stopped_at is None:
        return None
    blamed = [
        finding for finding in result.scene.report.findings if finding.op_id == result.stopped_at
    ]
    return blamed[-1] if blamed else None


class TriangleCounts(NamedTuple):
    """Was die Vorschau eines Schritts sagt, der nur das Netz ändert (RESTVERLAUF-04).

    ``before`` und ``after`` zählen die Dreiecke der Körper, die er anfasst.
    ``estimated`` heißt: vorab gezählt und nicht gerechnet — dann ist
    ``after`` eine Schätzung, oder mit ``at_most`` eine Obergrenze.
    """

    before: int
    after: int
    at_most: bool = False
    estimated: bool = False


@dataclass
class _Counting:
    """Was die Vorabzählung am Original über eine Vorschau entschieden hat.

    ``bodies`` sind die Körper, an denen gezählt wurde — sie bekommen keine
    verkleinerte Kopie. ``refusal`` ist die Absage der Operation, ``enough``
    heißt: Die Zahl ist die ganze Vorschau, gerechnet wird nichts.
    """

    bodies: frozenset[str] = frozenset()
    refusal: AppError | None = None
    before: int = 0
    after: int = 0
    at_most: bool = False
    enough: bool = False

    def numbers(self) -> TriangleCounts:
        return TriangleCounts(self.before, self.after, self.at_most, estimated=True)


def _reshaped_only(working: Any, previewed: Sequence[OpId]) -> frozenset[str]:
    """Die Körper, an denen jeder vorgeschaute Schritt nur das Netz ändert.

    Eine Neuvernetzung, nach der noch ein Schritt die Form ändert, ist nicht
    mehr die ganze Änderung — solche Körper bekommen ihren Vergleich wie
    bisher. Leer, wenn kein vorgeschauter Schritt ``retriangulates`` trägt.
    """
    wanted = set(previewed)
    reshaped: set[str] = set()
    reshaping: set[str] = set()
    for entry in working.ops:
        if entry.id not in wanted:
            continue
        touched = {*entry.inputs, *entry.outputs}
        if REGISTRY.has(entry.op) and REGISTRY.get(entry.op).retriangulates:
            reshaped |= set(entry.outputs)
        else:
            reshaping |= touched
    return frozenset(reshaped - reshaping)


def _counts_of(before: Any, after: Any, bodies: frozenset[str]) -> TriangleCounts:
    """Die Dreiecke der genannten Körper davor und danach — gerechnet, nicht geschätzt."""

    def total(scene: Any) -> int:
        return sum(
            int(getattr(scene.objects[name].mesh, "triangle_count", 0))
            for name in bodies
            if name in scene.objects
        )

    return TriangleCounts(total(before), total(after))


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
        protect: Sequence[Any] = (),
        margin: float = MARGIN,
    ) -> None:
        super().__init__()
        self._mesh = mesh
        #: Der Rand zum Bettrand, mit dem danach angeordnet wird (``bed_margin``).
        self._margin = margin
        self._object_id = object_id
        self._profile = profile
        self._features = dict(features)
        #: Die Punktwolken der gesperrten Sichtflächen (§22.3) — fertig
        #: gerechnet, bevor der Faden startet: Sie kommen aus dem ausgewerteten
        #: Körper, und der gehört dem Hauptthread.
        self._protect = tuple(protect)
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
                protect=self._protect,
                cancelled=self.cancel,
                progress=self.progressed.emit,
                margin=self._margin,
            )
        except OperationCancelled:
            self.cancelled.emit()
        except AppError as error:
            self.failedWith.emit(error)
        else:
            self.done.emit(plan)

    def release_finished_references(self) -> None:
        """Große Suchdaten nach der vollständig zugestellten Antwort lösen."""
        del self._mesh, self._profile, self._features, self._protect
        super().release_finished_references()


#: Plant einen Umbau erst im Arbeiter: mit dem Verlauf, seinen Abhängigkeiten
#: am Grundstand und einer Auswertung wie der des Arbeiters — Einfügen sucht
#: damit die freie Stelle am Endstand (:func:`searched_at_the_end`).
_Planner = Callable[[History, Dependencies, Callable[[Any], EvaluationResult]], RevisionPlan]


class _RevisionWorker(Worker):
    """Ein Umbau des Verlaufs, isoliert gerechnet (P7) — besitzt nichts, meldet alles.

    Gerechnet wird an einer Kopie, die beim Start im Hauptfaden gezogen wurde
    (:class:`_Snapshot`, dieselbe Begründung): Der Hauptfaden darf das
    Dokument währenddessen ändern, und dann ist der Plan veraltet — das sagt
    ``History.commit`` beim Übernehmen, nicht eine halbe Kopie im Arbeiter.
    Fehlt ein gerechneter Grundstand (eine Auswertung lief noch, oder die
    Einfügemarke zeigt den Stand davor), rechnet der Arbeiter ihn zuerst; der
    Cache trägt, was schon gerechnet ist. Abbrechen hält ihn an, und nichts
    ist geändert (§15.6).
    """

    revisedWith = Signal(object)
    failedWith = Signal(object)
    cancelled = Signal()

    def __init__(
        self,
        session: Session,
        document: Any,
        planned: RevisionPlan | _Planner,
        baseline: EvaluationResult | None,
        cancel: CancelSignal,
    ) -> None:
        super().__init__()
        self._session = session
        self._document = document
        self._planned = planned
        self._baseline = baseline
        self.cancel = cancel
        self._project_generation = session._project_generation
        self._profile = session.evaluation_profile
        self._quality = session.quality
        self._sources = ProjectSources(session.project, base_dir=session.base_dir)

    def work(self) -> None:
        session = self._session
        session._pending.project_generation = self._project_generation

        def run(document: Any) -> EvaluationResult:
            return evaluate(
                document,
                self._profile,
                quality=self._quality,
                progress=session.report_progress,
                ask=session.ask_from_worker,
                question_context=session.announce_question,
                cancelled=self.cancel,
                cache=session.cache,
                sources=self._sources,
            )

        try:
            history = History(self._document)
            baseline = self._baseline if self._baseline is not None else run(self._document)
            context = revision_dependencies(self._document, baseline)
            plan = (
                self._planned
                if isinstance(self._planned, RevisionPlan)
                else self._planned(history, context, run)
            )
            revision = revise(
                history,
                plan,
                evaluate=run,
                baseline=baseline,
                context=context,
                ask=session.ask_from_worker,
                announce=lambda preview, candidates: session.announce_question(preview, candidates),
            )
        except OperationCancelled:
            self.cancelled.emit()
        except AppError as error:
            self.failedWith.emit(error)
        else:
            self.revisedWith.emit(revision)
        finally:
            session.announce_question(None, ())
            session._pending.project_generation = None
            session.report_progress(1.0, "")

    def release_finished_references(self) -> None:
        """Sitzung, Kopie und Plan nach der Zustellung lösen."""
        del self._session, self._document, self._planned, self._baseline, self._sources
        super().release_finished_references()


class _QuestionPending(OperationCancelled):
    """Die stille Vorschau ist an einer Rückfrage stehengeblieben.

    Ein eigener Typ, damit das Band es sagen kann: Bis zum 14.09.2026 kam
    dort „am Volumen ändert sich nichts" — gemessen an *Merkmal entfernen*
    an einer gesenkten Bohrung, wo die Auswertung fragt, ob die Senkung
    mitgeht. Nichts hatte sich geändert; es war noch nichts entschieden."""


def _no_questions(question: str, choices: list[str]) -> str:
    """Die ask-Funktion der stillen Vorschau: sie fragt nicht, sie hält an.

    Eine Rückfrage mitten im Tippen wäre ein Fenster über einem Fenster —
    was eine Antwort braucht, bekommt sie beim Anwenden über den echten Weg."""
    raise _QuestionPending


def _unresolvable(parameters: Mapping[str, Parameter]) -> AppError | None:
    """Der Fehler, an dem dieser Parametersatz scheitert — oder ``None``.

    Dieselbe Rechnung, die die Auswertung als Erstes macht (§13). Sie hier
    vorwegzunehmen kostet Mikrosekunden und erspart dem Kunden den Umweg über
    den Prüfbericht: Wer eine Zahl dreht, an der ein fremder Ausdruck hängt,
    bekommt den Satz an der Leiste, an der er gerade steht.
    """
    try:
        expressions.resolve(parameters)
    except AppError as error:
        return error
    return None


def _with_findings(result: EvaluationResult, extra: list[Finding]) -> EvaluationResult:
    """Trägt die Befunde der Prüfung in den Bericht, den das Fenster zeigt."""
    if not extra:
        return result
    scene = result.scene
    scene.report = Report((*scene.report.findings, *extra))
    return result


#: Ab dieser Nutzlast wird der Einleseplan in einem Arbeiter gerechnet — für
#: eine Nutzlast ohne Pfad (ein Download). Eine Datei vom Pfad liest
#: :class:`_ReadWorker`, und ihr Plan läuft danach immer im Arbeiter (RM-224).
#:
#: **Gemessen, nicht geschätzt** (03.09.2026, ``import_plan`` über echte
#: Kundendateien):
#:
#:     cube_clean.stl          0,00 MB    0,00 s
#:     garden-hose-holder.3mf  5,19 MB    0,92 s
#:     Wizard Tower.3mf       27,87 MB    3,98 s
#:     chufang.3mf            66,65 MB   11,88 s
#:
#: Das ist linear, rund 0,18 s je MB. Acht MB sind damit etwa 1,4 s — noch in
#: dem Bereich, den ``main_window.waiting`` für sich beschreibt („bis zu zwei
#: Sekunden"), und darüber beginnt der, den derselbe Docstring dem Arbeiter
#: zuweist.
#:
#: **Warum überhaupt eine Grenze und nicht immer ein Arbeiter.** Er kostet
#: einen Fadenwechsel und macht aus einem Aufruf einen Vorgang mit Signalen.
#: Für eine Datei, deren Plan in Mikrosekunden steht, ist das der teurere Weg,
#: und er verschöbe das Ergebnis hinter die Ereignisschleife, obwohl niemand
#: darauf gewartet hat.
PLAN_IN_WORKER_ABOVE: Final = 8 * 1024 * 1024

#: Dieselbe Grenze für eine STEP-Datei, und sie liegt tiefer. Der Plan liest
#: dort die ganze Baugruppe (P7.4, ``brep.step.read_assembly``), um die Körper
#: zu zählen: gemessen 0,28 s an ``build_tray_v3.step`` (0,45 MB) und 1,1 s an
#: einer Baugruppe mit 1000 Instanzen (2 MB) — rund 0,6 s je MB, also bei zwei
#: MB etwa so lange wie eine 3MF an der Grenze darüber.
STEP_PLAN_IN_WORKER_ABOVE: Final = 2 * 1024 * 1024


def _plans_in_worker(name: str, size: int) -> bool:
    """Ob der Einleseplan dieser Datei in einen Arbeiter gehört."""
    from app.core.brep import step as brep_step

    limit = PLAN_IN_WORKER_ABOVE
    if brep_step.is_step(Path(name).suffix):
        limit = min(limit, STEP_PLAN_IN_WORKER_ABOVE)
    return size > limit


@dataclass(slots=True)
class _Gathering:
    """Was :meth:`Session.one_step` einsammelt, bevor es eine Transaktion wird."""

    title: TranslatableText | str | None
    drafts: list[OperationDraft] = field(default_factory=list)
    origin: Origin | None = None

    def add(
        self,
        title: TranslatableText | str,
        drafts: Sequence[OperationDraft],
        origin: Origin | None,
    ) -> None:
        """Die Schritte eines Aufrufs anhängen; Titel und Herkunft gibt der erste."""
        if self.title is None:
            self.title = title
        if self.origin is None:
            self.origin = origin
        self.drafts.extend(drafts)


class Session(QObject):
    """Hält das offene Projekt und die Oberfläche im Gleichschritt mit ihm."""

    sceneChanged = Signal(object)
    """Eine Auswertung ist fertig — trägt ein ``EvaluationResult``."""
    progressChanged = Signal(float, str)
    busyChanged = Signal(bool)
    askRequested = Signal(object)
    """Eine Frage an den Nutzer — trägt einen ``AskRequest``."""
    recognitionAnswered = Signal(int, int, str, object)
    """Die Antwort auf die Frage vor der Vollerkennung, aus dem Arbeiter gemeldet
    (Projektgeneration, Ladeschritt, Schlüssel, Eintrag)."""
    questionInvalidated = Signal()
    """Abbruch oder Nachlauf hat den bisherigen Auswertungsauftrag entwertet."""
    proposalReady = Signal(object)
    """Ein Agentenzug ist fertig — trägt eine ``ProposalPreview`` (§26.5)."""
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
    importFailed = Signal(object)
    """Der asynchrone Einleseweg ist gescheitert — trägt eine ``AppError``.

    Das Gegenstück zum ``raise`` des synchronen Wegs: Wer im Arbeiter plant,
    kann nicht in den Aufrufer werfen, der längst weitergelaufen ist."""
    autosaveFailed = Signal(object)
    """Die automatische Sicherung ließ sich nicht schreiben — trägt den ``AppError``."""
    pictureChanged = Signal(object)
    """Das Bild vor der Erkennung (:meth:`picture_first`): Geometrie und Befunde
    eines großen Imports, noch ohne Merkmale — kein Dokumentstand."""
    importRejected = Signal(object)
    """Ein angenommener Import hielt schon beim Laden an und ist zurückgenommen
    (KUNDE-12) — trägt den ``UserError`` mit *Andere Datei wählen*."""
    importConfirmed = Signal()
    """Der zuletzt angenommene Import hat sein Modell geliefert — jetzt gehört
    er nach „Zuletzt geöffnet“ (KUNDE-12)."""
    importFinished = Signal(bool)
    """Der asynchrone Einleseweg ist durch — ``True``, wenn etwas ankam.

    Die Auswertung läuft danach noch; dieses Signal sagt nur, dass Plan und
    Stapel fertig sind und das Fenster seinen Wartezustand auflösen darf."""
    outlineImportRequested = Signal(object, str, int)
    """Eine Zeichnung wartet auf Konturen und Höhe: Plan, Quelle, Projektgeneration."""
    stepImportRequested = Signal(object, str, int)
    """Eine STEP-Baugruppe wartet auf die Körperauswahl: Plan, Quelle, Projektgeneration."""
    evaluationCancelled = Signal()
    """Ein Mensch hat die Auswertung angehalten (§2.8).

    **Nicht** bei jedem Abbruch: Eine neuere Anfrage bricht die laufende
    ebenfalls ab (``_rerun_pending``), und das ist ein Ersetzen, kein
    Aufhören — es zu melden hieße, beim Ziehen an einem Schieber im
    Sekundentakt „abgebrochen" in die Statuszeile zu schreiben."""
    projectChanged = Signal()
    """Stapel, Pfad oder Titel haben sich geändert; die Leisten laden neu."""
    failed = Signal(object)
    revisionDone = Signal(object)
    """Ein Umbau des Verlaufs ist übernommen (P7) — trägt die ``Revision`` samt Befunden."""
    insertionChanged = Signal(object)
    """Die Einfügemarke ist gesetzt oder weg (P7.1) — trägt die Schrittkennung oder ``None``."""
    revisionCancelled = Signal()
    """Ein Umbau des Verlaufs wurde abgebrochen — geändert ist nichts."""
    """Eine ``AppError``, die die Oberfläche als Vorschlag zeigt (§2.7)."""
    counterpartFinished = Signal(object)
    """Die Passung eines Gegenstücks ist nachgetragen — trägt die neuen Befunde.

    Das Paar selbst steht sofort im Dokument (:meth:`create_counterpart`,
    :meth:`create_thread_counterpart`); die Passung braucht die Kennungen der
    erzeugten Merkmale, und die kennt erst die Auswertung. Sie läuft im
    Arbeiter, und dieses Signal sagt dem Fenster, was dabei herauskam."""
    backendChanged = Signal()
    """Der Chat spricht ab jetzt mit einem anderen Modell — die Kopfzeile lädt neu.

    Ausgelöst, wenn die Gegenseite einen Zugang ablehnt: Dann fällt der Chat
    auf das nächste verfügbare Modell zurück, und das muss dranstehen. Ohne
    dieses Signal behielt die Kopfzeile den Namen dessen, der gerade abgelehnt
    hatte — genau der Anblick, der einen Kunden am 24.08.2026 drei Stunden
    lang glauben ließ, seine Einstellung sei nicht angekommen."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.choose_outline = False
        """Das Hauptfenster beantwortet Zeichnungsimporte vor dem ersten Schritt."""
        self._outline_imports: dict[tuple[int, str], ImportPlan] = {}
        self.choose_step_bodies = False
        """Das Hauptfenster lässt vor dem ersten Schritt die Körper einer STEP-Baugruppe wählen."""
        self._step_imports: dict[tuple[int, str], ImportPlan] = {}
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
        self._recovery_owner: BinaryIO | None = None
        self._recovery_finalizer: Callable[[], object] | None = None
        self.recovery_token: str = recovery_token()
        """Unter welcher Kennung dieses Dokument gesichert wird, solange es
        keinen Namen hat — je Dokument eine, damit zwei Fenster ihre
        Sicherungen nicht teilen (:func:`app.core.scene.project.recovery_token`)."""
        self.quality: Quality = "draft"
        """Entwurf, solange gearbeitet wird; Export und Abschlussbericht schalten
        auf fein (§31)."""
        self._quality_once: Quality | None = None
        """Die Qualität für **einen** Lauf — siehe :meth:`recompute_fully`."""
        self.last_result: EvaluationResult | None = None
        self.result_current = False
        """Ob die Szene bereits zum aktuellen Auswertungsauftrag gehört."""
        self._unconfirmed_import: tuple[str, frozenset[int], str] | None = None
        """Transaktion, Ladeschritte und Quelle des letzten Imports, bis seine
        Auswertung zeigt, ob die Datei ein Modell enthält (KUNDE-12)."""
        self.picture: EvaluationResult | None = None
        """Das gezeigte Bild vor der Erkennung, solange sie läuft — sonst ``None``.

        Ist es gesetzt, ist es auch ``last_result``; ``result_current`` ist dann
        falsch, weil die Merkmale noch fehlen (siehe :meth:`picture_first`)."""
        self.pending_orphan_check = False
        """Gesetzt, wenn eine Datei geöffnet wurde: §21.3 prüft ihre Verweise
        einmal, nicht immer."""
        self._pending = threading.local()
        """Was die nächste Frage **dieses Fadens** zur Wahl stellt (§21.3) —
        von :meth:`announce_candidates` gesetzt.

        Je Faden und nicht je Sitzung: siehe :meth:`announce_candidates`.
        ``getattr`` mit Vorgabe beim Lesen, weil ein frisch gestarteter Faden
        das Feld noch nicht hat — eine Frage ohne vorherige Ansage ist der
        Regelfall (die Einheitenfrage etwa) und kein Sonderfall.
        """
        self.pending_part_check = False
        """Dasselbe für die Bausteinbibliothek (§24.4): beim Öffnen, nicht bei
        jedem Lauf."""
        self.pending_foreign_check = False
        """Und dasselbe für das, was §32 den Warnhinweis nennt: Quelltext und
        Verweise nach außen werden beim Öffnen einmal gemeldet. Bei jeder
        Auswertung wäre es eine Zeile, die immer dasteht und die deshalb
        niemand mehr liest."""
        self.draft_origin: Recipe | None = None
        """Aus welchem Baustein dieses Dokument als Entwurf geöffnet wurde (E6).

        Ein Zustand des **Projekts** und keiner des Fensters: Er gilt genau so
        lange wie das Dokument, und ``_reset_for`` ist die eine Stelle, an der
        ein Dokument wechselt. Im Fenster gehalten müsste ihn jeder der vier
        Wege dorthin (neu, öffnen, wiederherstellen, Entwurf) einzeln löschen,
        und der fünfte vergäße es.

        Der Rezeptdialog belegt seine Felder daraus vor — Titel, Gruppe,
        Lizenz, die freigegebenen Maße, die benannten Stellen — und reicht die
        Importquittung weiter, damit ein fremder Baustein fremd bleibt."""
        self._worker: _EvaluationWorker | None = None
        # Ein Arbeiter, der bei einem synchronen Lauf noch rechnete: Sein
        # Ergebnis ist danach älter als der Stand, den ``evaluate_now`` liefert.
        self._superseded: _EvaluationWorker | None = None
        self._plan: _PlanWorker | _ArchiveWorker | _ReadWorker | None = None
        """Der laufende Einleseplan (§2.8) — siehe ``import_payload_async``."""
        self._autosaving: _AutosaveWorker | None = None
        """Die laufende automatische Sicherung — siehe :meth:`autosave_async`."""
        self._autosave_epoch = 0
        """Zählt jedes Speichern und Verwerfen: Eine Sicherung, die danach
        fertig wird, gilt einem Stand, den niemand mehr braucht."""
        self._agent: _AgentWorker | None = None
        self._split: _SplitWorker | None = None
        self._revision: _RevisionWorker | None = None
        """Der laufende Umbau des Verlaufs (P7), höchstens einer."""
        self._revision_cancel = CancelSignal()
        self._insert_before: OpId | None = None
        """Die Einfügemarke (P7.1): Neue Schritte kommen vor diesen, und die
        Oberfläche zeigt den Stand davor. Kein Dokumentzustand — sie gehört
        der Sitzung und reist nicht in die Datei."""
        self._gathering: _Gathering | None = None
        """Die laufende Sammlung von :meth:`one_step`, sonst ``None``."""
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
        self._coarse_scene: tuple[Any, OpId | None, Any] | None = None
        """Die zuletzt verkleinerte Szene davor, samt der Szene, zu der sie
        gehört (§2.8).

        Ein Platz und nicht mehr: Solange ein Dialog offen ist, bleibt die
        Szene davor dieselbe, und ihre grobe Kopie ändert sich nicht. Die
        nächste Auswertung liefert ein neues ``Scene``-Objekt — der Vergleich
        auf Identität merkt das, ohne dass jemand ein Feld zurücksetzen muss."""
        self._coarse_lock = threading.Lock()
        """Eine Vorbereitung der groben Stufe zur Zeit (:meth:`_coarse_before`).

        Wer tippt, startet je Zahl einen Arbeiter. Ohne die Sperre rechneten
        zwei davon dieselbe Verkleinerung nebeneinander, und keiner fände den
        Merker, den der andere gleich anlegt."""
        self._coarse_cancel = CancelSignal()
        """Das Abbruchsignal der Vorbereitung — nicht das der einzelnen Vorschau.

        Eine neue Zahl ersetzt die laufende Vorschau (:meth:`supersede_preview`),
        die Verkleinerung des unveränderten Eingangs aber braucht die nächste
        genauso. Sie rechnet deshalb zu Ende und wird gemerkt; angehalten wird
        sie erst, wenn niemand mehr auf eine Vorschau wartet
        (:meth:`cancel_preview`) oder ein anderes Dokument offen ist."""
        self._placements: list[_PreviewWorker] = []
        """Jeder laufende Vorschau-Arbeiter, festgehalten bis ``finished``.

        Eine neuere Anfrage ersetzt die alte nur in der Anzeige — der alte
        Thread rechnet aus. Die Referenz zu überschreiben hieße, ein
        laufendes QThread-Objekt dem Speicherbereiniger zu überlassen, und
        der zerstört das C++-Objekt unter dem Thread: ein Absturz ohne
        Zeile, irgendwann später."""
        self._preview_generation = 0
        """Stempel der jüngsten Vorschau-Anfrage (§18.7) — eine verspätete
        Antwort auf eine ältere wird verworfen statt gezeigt."""
        self._project_generation = 0
        """Welches Dokument gerade offen ist, als Zähler: ``_reset_for`` zählt
        hoch, und ein Arbeiter, der für ein früheres gestartet wurde, erkennt
        seine Meldung als veraltet (UI-01)."""
        self._recognition_answers: list[tuple[int, str, dict[str, Any]]] = []
        """Die Antworten auf die Frage vor der Vollerkennung, die noch auf ihr
        Ergebnis warten — sofort festgehalten, geleert mit dem fertigen Lauf."""
        self.recognitionAnswered.connect(self._record_recognition_answer)
        self._analysis_memory: tuple[tuple[Any, ...], tuple[object, ...], dict[str, Any]] | None = (
            None
        )
        """Die zuletzt im Druckdialog gemessenen Schichten (:meth:`remember_analyses`)."""
        self.result_generation = 0
        """Zählt jedes neue ``last_result``. Wer wissen will, ob seit seinem
        Blick eine andere Auswertung kam, vergleicht diese Zahl — nicht
        ``id(last_result)``: CPython vergibt die Adresse eines freigegebenen
        Ergebnisses wieder, und zwei Auswertungen später sah der Druckdialog
        „dasselbe" Ergebnis (UI-21)."""
        self._backend: LLMBackend | None = None
        self._backend_probed = False
        """Ob ``first_available`` schon einmal gefragt wurde — auch ein „keins"
        ist eine Antwort, die nicht bei jedem Fensteraufbau neu kostet."""
        self._selection: tuple[str, str] | None = None
        self._pending_views: tuple[tuple[str, bytes], ...] = ()
        """Die Ansichten des nächsten Zuges (§23) — im Hauptthread gerendert,
        vom Arbeiter nur gelesen; der Renderer gehört nie in einen zweiten
        Thread."""
        self._accepted: dict[str, str | None] = {}
        self._rerun_pending = False
        self._dirty = False
        self._effective_print_settings: weakref.WeakMethod[Callable[[], PrintSettings]] | None = (
            None
        )
        """Woher die Druckeinstellungen kommen, die gedruckt werden
        (:meth:`follow_print_settings`) — schwach, das Fenster besitzt die Sitzung."""
        self._evaluation_settings: PrintSettings | None = None
        """Die wirksamen Druckeinstellungen, mit denen die letzte Auswertung
        begann (:meth:`evaluation_profile`) — im Hauptthread geholt, vom
        Arbeiter nur gelesen."""
        self._after_evaluation: list[tuple[int, Callable[[Any], None]]] = []
        """Was nach der nächsten gültigen Auswertung dieses Dokuments noch zu tun
        ist — je Eintrag der Projektstempel und der Abschluss (:meth:`_finish_after`)."""

    # --- state ------------------------------------------------------------------

    @property
    def profile(self) -> Profile:
        # ``scene_profile`` und nicht ``make_profile``: Ein Drucker, den dieser
        # Rechner nicht kennt, hielt sonst alles an — keine Szene, keine
        # Druckeinstellungen. Der Prüfbericht sagt, womit gerechnet wird
        # (``profiles.carried_findings`` in ``run_evaluation``).
        document = self.project.document
        return profiles.for_process(
            profiles.scene_profile(
                document.printer or profiles.DEFAULT_PRINTER,
                document.material or profiles.DEFAULT_MATERIAL,
            ),
            document.print_settings,
        )

    @property
    def evaluation_profile(self) -> Profile:
        """Das Profil, mit dem ausgewertet wird: dazu die Stützschwelle, mit
        der der Slicer stützt (Konzept Herstellerprofil, Entscheidung L).

        :attr:`profile` kennt nur den gespeicherten Satz; die Schwelle des
        gewählten Herstellerprozesses kennt das Fenster (:meth:`follow_print_settings`).
        :meth:`evaluate_async` holt dessen wirksame Einstellungen im
        Hauptthread; ohne Fenster bleibt es beim gespeicherten Satz.
        """
        settings = self._evaluation_settings
        if settings is None:
            return self.profile
        return profiles.for_process(self.profile, settings, effective=True)

    def evaluation_follows(self, settings: PrintSettings) -> bool:
        """Rechnet die letzte Auswertung schon mit diesen Einstellungen?

        Nur was das Profil der Auswertung ändert, zählt: Schichthöhe,
        Bahnbreite und Stützschwelle. Kommt die Grundlage aus dem
        Herstellerprofil erst nach dem ersten Lauf, sagt die Antwort, ob ein
        zweiter nötig ist.
        """
        before = self.evaluation_profile.printer
        after = profiles.for_process(self.profile, settings, effective=True).printer
        return (before.layer_height, before.extrusion_width, before.overhang_limit) == (
            after.layer_height,
            after.extrusion_width,
            after.overhang_limit,
        )

    def _current_effective_settings(self) -> PrintSettings | None:
        """Die wirksamen Einstellungen des Fensters — nur im Hauptthread fragen."""
        reference = self._effective_print_settings
        source = reference() if reference is not None else None
        return source() if source is not None else None

    def adopt_carried_printers(self) -> tuple[str, ...]:
        """Übernimmt die Drucker, die das Projekt mitbringt, in die eigenen.

        Danach stehen sie auf diesem Rechner in jedem Projekt zur Wahl; die
        Kennung bleibt dieselbe, also rechnet dieses Projekt unverändert.
        """
        adopted = profiles.adopt_carried()
        if adopted:
            self.evaluate_async()
        return adopted

    def keep_saved_parts(self) -> bool:
        """Rechnet eigene Bausteine wieder mit dem gespeicherten Stand (§24.4).

        Den Stand hat die Projektdatei mitgebracht
        (``part_check.saved_states``). Alle Schritte wechseln in einer
        Transaktion; ein Strg+Z führt zum neuen Stand zurück (RM-138).
        """
        try:
            transaction = part_check.keep_saved(self.history)
        except AppError as error:
            self.failed.emit(error)
            return False
        if transaction is None:
            return False
        self._changed()
        return True

    @property
    def project_generation(self) -> int:
        """Welches Dokument offen ist, als Zähler — jeder Dokumentwechsel zählt hoch.

        Für die Oberfläche, die sich merken will, zu welchem Dokument eine
        Anzeige gehört (die Zahlenzeile vergleicht nur innerhalb eines).
        """
        return self._project_generation

    @property
    def base_dir(self) -> Path | None:
        return self.path.parent if self.path else None

    @property
    def modified(self) -> bool:
        return self._dirty

    @property
    def only_imported(self) -> bool:
        """Ob hier nichts liegt, was nicht in seinen Dateien steht (RM-130).

        Zwei Bedingungen, und die zweite steht im Kern
        (:func:`app.core.ingest.plan.is_only_imported`): Es gibt **keine
        Projektdatei** — sonst geht es um Änderungen an etwas, das der Kunde
        pflegt —, und das Dokument besteht aus nichts als eingelesenen
        Dateien.

        :attr:`modified` bleibt davon unberührt, und das ist Absicht: Die
        automatische Sicherung (§38) hängt daran, und ein Absturz nach einem
        vierzehn Sekunden langen Import soll den Stand nicht kosten. Was sich
        ändert, ist die Frage beim **bewussten** Schließen.
        """
        return self.path is None and is_only_imported(self.project.document)

    @property
    def busy(self) -> bool:
        """Auswertung und Einleseplan teilen sich den Fortschritt bis zum Ende.

        Auch ein fertiger Faden zählt bis zur Zustellung seines Endsignals:
        Sein Ergebnis kann noch die nächste Auswertung anstoßen.
        """
        return self._worker is not None or self._plan is not None or self._revision is not None

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
        self.project = _load_beside_the_window(path)
        self.pending_orphan_check = True
        self.pending_part_check = True
        self.pending_foreign_check = True
        self._reset_for(path)

    def open_draft(self, project: Project, origin: Recipe) -> None:
        """Öffnet einen Baustein als bearbeitbares Projekt (E6, RM-147).

        Der Entwurf ist ein **namenloses** Projekt: Er hat keine Datei, und ein
        „Speichern" fragt deshalb nach einem Namen, statt in die Rezeptdatei zu
        schreiben. Denselben Grund nennt :meth:`recover` für ihren Fall — was
        der Kunde pflegt, ist die Projektdatei, und die Ablage des Bausteins
        ist keine.

        Als **geändert** gilt er nicht: Der Stand steht vollständig im Katalog,
        es geht nichts verloren, wenn jemand ihn ansieht und wieder schließt.
        Erst der erste eigene Zug macht ihn geändert, und dann fragt das
        Fenster wie bei jedem anderen Projekt.

        Die drei Prüfungen laufen wie beim Öffnen einer Datei: Ein Rezept kann
        Schritte enthalten, die selbst Bausteine einsetzen (§24.4), es kann
        Merkmale nennen, die der frische Lauf anders zuordnet (§21.3), und ein
        eingelesenes kam von außen (§32). Sie sind hier nicht teurer als dort
        — wo nichts zu melden ist, meldet keine.
        """
        self.project = project
        self.pending_orphan_check = True
        self.pending_part_check = True
        self.pending_foreign_check = True
        self._reset_for(None)
        # **Nach** ``_reset_for`` — es räumt die Herkunft des vorigen Dokuments
        # weg und träfe sonst die gerade gesetzte.
        self.draft_origin = origin

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
        self.project = _load_beside_the_window(path)
        self.pending_orphan_check = True
        self.pending_part_check = True
        self.pending_foreign_check = True
        self._reset_for(into)
        self._dirty = True
        if into is None:
            # Die Sicherung gehört jetzt diesem Fenster: unter der eigenen
            # Kennung neu geschrieben und die angebotene weggeräumt — sonst
            # böte der nächste Start sie noch einmal an, und ein zweites
            # Fenster hielte sie für seine (CORE-09).
            self._claim_recovery()
            write_autosave(self.project, None, self.recovery_token)
            discard_recovery(path)
        self.projectChanged.emit()

    def save_project(self, path: Path | None = None) -> Path:
        target = path or self.path
        if target is None:
            raise AppError(tr("Für dieses Projekt gibt es noch keinen Dateinamen."))
        try:
            save(self.project, target)
        except ValueError as problem:
            # **Was die Serialisierung ablehnt, ist ein fachlicher Fehler.**
            # ``non_finite_number`` und die Größengrenzen der Projektdatei
            # kamen als nackter ValueError bis in den Speichern-Slot, der nur
            # AppError fängt: keine Datei, keine Meldung (Gesamtreview
            # 05.09.2026, UI-26). Die Grenze im Parameterdialog fängt den
            # häufigsten Fall vorher; hier steht der Vertrag für alle anderen.
            raise AppError(
                tr("Das Projekt lässt sich so nicht speichern."),
                tr(
                    "Ein Wert darin ist keine endliche Zahl oder sprengt die Projektdatei. "
                    "Prüfen Sie Parameter mit Grenzen wie unendlich, und speichern Sie "
                    "danach erneut."
                ),
                values={"reason": str(problem)},
            ) from problem
        # Die Sicherung des Zustands, der gerade gespeichert wird, hat sich
        # damit erledigt — auch die namenlose, aus der eine Wiederherstellung
        # kam (§38). **Erst jetzt**: Bis zum 05.09.2026 fiel sie vor dem
        # Schreiben, und ein volles oder gesperrtes Laufwerk ließ die neuen
        # Änderungen nur noch im Speicher zurück — die Projektdatei trug den
        # alten Stand, die Sicherung war weg (Gesamtreview, UI-06).
        self.forget_autosave()
        self.path = target
        self._dirty = False
        self.projectChanged.emit()
        return target

    def forget_changes(self) -> None:
        """Bestätigt das bewusst verworfene Dokument, ohne seine Quelle zu schreiben.

        Für Aufnahmewerkzeuge nach Abschluss ihrer Arbeit: Die eigene
        Wiederherstellung verschwindet ebenfalls. Dies speichert keine
        Änderungen und ersetzt keine Verwerfentscheidung des Nutzers.
        """
        self.forget_autosave()
        self.release_recovery()
        self._dirty = False
        self.projectChanged.emit()

    def autosave(self) -> None:
        """Container zur Absturz-Wiederherstellung neben dem Projekt (§38).

        Der gerade Weg, der wirft — für Tests und Werkzeuge. Das Fenster
        nimmt :meth:`autosave_async`.
        """
        if self._dirty:
            self._claim_recovery()
            write_autosave(self.project, self.path, self.recovery_token)

    def autosave_async(self) -> None:
        """Die automatische Sicherung im Arbeiter — der Zeitgeber des Fensters.

        Die Kopie des Dokuments entsteht hier, im Hauptfaden, wo es sich ändert;
        geschrieben wird sie im Arbeiter (:class:`_AutosaveWorker`). Läuft noch
        eine, wartet diese Runde auf die nächste. Ein Fehler kommt über
        :attr:`autosaveFailed` — bis zur Durchsicht 0.5.1 warf er im Slot des
        Zeitgebers, wo ihn kein Kunde sah (RM-233).
        """
        if not self._dirty or self._autosaving is not None:
            return
        try:
            self._claim_recovery()
        except AppError as error:
            self.autosaveFailed.emit(error)
            return
        snapshot = Project(
            document=copy.deepcopy(self.project.document),
            sources=dict(self.project.sources),
            report=self.project.report,
            thumbnail=self.project.thumbnail,
        )
        worker = _AutosaveWorker(snapshot, self.path, self.recovery_token)
        epoch, path, token = self._autosave_epoch, self.path, self.recovery_token
        self._autosaving = worker

        def done(error: object) -> None:
            if self._autosaving is worker:
                self._autosaving = None
            if epoch != self._autosave_epoch:
                # Gespeichert oder verworfen, während geschrieben wurde: Die
                # Sicherung gilt einem Stand, den es so nicht mehr zu retten
                # gibt, und böte sich beim nächsten Start sonst an.
                clear_autosave(path, token)
                return
            if isinstance(error, AppError):
                self.autosaveFailed.emit(error)

        worker.done.connect(done)
        worker.crashed.connect(lambda detail: done(InternalError(detail=detail)))
        self._leash.start(worker)

    def forget_autosave(self) -> None:
        """Die Sicherung des offenen Dokuments räumen — auch eine, die noch entsteht."""
        self._autosave_epoch += 1
        clear_autosave(self.path, self.recovery_token)

    def _claim_recovery(self) -> None:
        """Belegt die namenlose Sicherung vor dem ersten Schreibversuch."""
        if self.path is None and self._recovery_owner is None:
            self._recovery_owner = claim_recovery(self.recovery_token)
            self._recovery_finalizer = weakref.finalize(self, self._recovery_owner.close)

    def release_recovery(self) -> None:
        """Gibt die Sicherung beim Dokumentwechsel oder endgültigen Schließen frei."""
        if self._recovery_owner is not None:
            self._recovery_owner.close()
            self._recovery_owner = None
        if self._recovery_finalizer is not None:
            self._recovery_finalizer()
            self._recovery_finalizer = None

    def _reset_for(self, path: Path | None) -> None:
        # Eine Sicherung, die noch für das vorige Dokument schreibt, gilt nichts mehr.
        self._autosave_epoch += 1
        # Was dieses Projekt an eigenen Druckern und Materialien mitbringt,
        # ist ab jetzt bekannt — und das des vorigen nicht mehr.
        profiles.carry(self.project.document.carried_profiles)
        self.release_recovery()
        # Ein anderes Dokument kommt aus keinem Baustein, bis jemand es sagt —
        # ``open_draft`` setzt die Herkunft danach wieder (E6).
        self.draft_origin = None
        self.history = History(self.project.document)
        self.cache.clear()
        self.path = path
        # Ein anderes Dokument, eine andere Kennung — die Sicherung des
        # vorigen bleibt liegen, bis ``_may_discard`` sie geräumt hat.
        self.recovery_token = recovery_token()
        # Und ein anderer Stempel: Was ein Arbeiter für das vorige Dokument
        # noch meldet, gilt diesem nicht (UI-01).
        self._project_generation += 1
        self._recognition_answers.clear()
        # Ein anderes Projekt ist eine neue Entscheidung, auch über den Speicher.
        forget_out_of_memory()
        self._dirty = False
        self.last_result = None
        self.picture = None
        self._unconfirmed_import = None
        self._coarse_scene = None
        self._stop_coarse_preparation()
        if self._insert_before is not None:
            self._insert_before = None
            self.insertionChanged.emit(None)
        self.projectChanged.emit()
        self.evaluate_async()

    # --- editing ----------------------------------------------------------------

    def _changed(self) -> None:
        """Was nach jeder angenommenen Änderung geschieht — und zwar dreierlei.

        Als geändert merken (sonst geht die Arbeit beim Schließen verloren, das
        nur sichert, was als geändert gilt), die Oberflächen anstoßen, und neu
        auswerten. Die drei standen bis zum 04.09.2026 zwanzigmal in dieser
        Datei untereinander; wer ein viertes hinzufügen wollte — ein Signal,
        eine Sicherung, eine Kennzahl —, musste zwanzig Stellen finden und
        durfte keine übersehen.
        """
        self._bind_filament_profiles()
        self._dirty = True
        self.result_current = False
        self._keep_insertion_valid()
        self.projectChanged.emit()
        self.evaluate_async()

    def apply(
        self,
        title: TranslatableText | str,
        drafts: list[OperationDraft],
        origin: Origin | None = None,
        *,
        raise_on_error: bool = False,
        bundle: bool = False,
        changes: DocumentChange | None = None,
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

        **Solange die Kette hält, nimmt sie keinen neuen Schritt an** — eine
        Änderung ohne Schritt (Parameter, Passung, Drucker) aber sehr wohl,
        denn die kann den Halt lösen. Warum, steht an :meth:`halt_in_the_way`.

        **Steht eine Einfügemarke, kommen die Schritte dorthin** (P7.1) — als
        isoliert gerechneter Umbau (:meth:`_insert`). Der Rückgabewert heißt
        dann: angenommen und unterwegs; ein ungültiger Vorschlag meldet sich
        über ``failed`` und ändert nichts.

        **Innerhalb von** :meth:`one_step` wird gesammelt statt geschrieben:
        Die Schritte gehen am Ende als eine Transaktion in den Verlauf.
        """
        gathering = self._gathering
        if gathering is not None and drafts and changes is None:
            gathering.add(title, drafts, origin)
            return True
        if self._insert_before is not None and drafts:
            return self._insert(title, drafts, origin, changes, raise_on_error=raise_on_error)
        try:
            refusal = self.halt_in_the_way() if drafts else None
            if refusal is not None:
                raise refusal
            if bundle and not self._bundle_stays_exact():
                # Die Summe zweier Züge stimmt nur, wenn die Auswertung den
                # vorigen genau so gerechnet hat, wie er gezogen wurde.
                self.history.end_bundle()
            self.history.apply(
                title, drafts, origin or Origin(by="user"), bundle=bundle, changes=changes
            )
        except AppError as error:
            if raise_on_error:
                raise
            self.failed.emit(error)
            return False
        self._changed()
        return True

    @contextmanager
    def one_step(self, title: TranslatableText | str | None = None) -> Iterator[None]:
        """Was darin über :meth:`apply` geht, wird **eine** Transaktion (§15.5, RM-372).

        Für einen Ablauf, den der Kunde als eine Handlung empfindet, der aber
        mehrere Aufrufe macht: Eine Sammelzeile des Prüfberichts führt *Kleine
        Teile entfernen* oder *Auf den Bauraum verkleinern* je gewähltem
        Körper aus, und jeder Körper war ein eigener Rückgängig-Schritt — ein
        Strg+Z nahm einen von dreien zurück. Gesammelt werden die Schritte und
        am Ende mit einem Aufruf angewandt; Halt, Einfügemarke und Absage
        gelten dann für alle zusammen, und gerechnet wird einmal.

        ``title`` ist der Titel im Verlauf, ohne ihn der des ersten Aufrufs.
        Eine Änderung ohne Schritt (``changes``) geht ihren eigenen Weg, und
        verschachtelt sammelt der äußere Aufruf. Wirft der Block, wird nichts
        angewandt.
        """
        if self._gathering is not None:
            yield
            return
        gathering = _Gathering(title)
        self._gathering = gathering
        try:
            yield
        finally:
            self._gathering = None
        if gathering.drafts:
            self.apply(gathering.title or "", gathering.drafts, gathering.origin)

    def _bundle_stays_exact(self) -> bool:
        """Ob der nächste Zug in den vorigen aufgehen darf (§15.5).

        Gefragt wird am **aktuellen** Ergebnis: Ist die Auswertung des vorigen
        Zugs noch nicht zurück, weiß niemand, ob sie ihn zurückgeschoben hat —
        dann wird es ein eigener Schritt. Ein Bündel zu wenig kostet einen
        Eintrag im Verlauf, eines zu viel verschiebt das Teil
        (:func:`app.core.scene.bundling.stays_exact`).
        """
        result = self.last_result
        document = self.project.document
        if result is None or not self.result_current or not document.transactions:
            return False
        by_id = {entry.id: entry for entry in document.ops}
        ops = [by_id[op_id] for op_id in document.transactions[-1].ops if op_id in by_id]
        return bundling.stays_exact(ops, result.scene)

    def halted_step(self) -> tuple[int, TranslatableText | str] | None:
        """Der Schritt, an dem die letzte Auswertung hält — Kennung und Titel.

        ``None``, solange die Kette durchläuft. Fenster und Sitzung fragen
        hier, bevor sie einen neuen Schritt anbieten oder annehmen (§15.3):
        Das Bild zeigt den letzten vollständig gerechneten Zustand, und was
        hinter dem angehaltenen Schritt steht, wird nicht gerechnet.
        """
        result = self.last_result
        if result is None or result.stopped_at is None:
            return None
        step = next(
            (entry for entry in self.project.document.ops if entry.id == result.stopped_at),
            None,
        )
        title: TranslatableText | str = (
            REGISTRY.get(step.op).title
            if step is not None and REGISTRY.has(step.op)
            else str(result.stopped_at)
        )
        return result.stopped_at, title

    def halt_in_the_way(self) -> UserError | None:
        """Die Absage für einen neuen Schritt, solange die Kette hält — mit dem
        Ausweg des Halts als Handlungen.

        **Roberts Fall** (11.09.2026: „da geht nichts mehr wenn ich die
        operation ausführe"): Nach einem Schriftwechsel hielt die Kette an der
        Zerlegung an — elf Teile verlangt, zehn da. Jede Operation, die er
        danach ausführte, noch einmal zerlegen, noch einmal ausrichten, ging
        ohne Widerspruch durch ihren Dialog und stand danach als Schritt 4 und
        5 **hinter** dem angehaltenen zweiten: nie gerechnet, im Bild nichts,
        im Verlauf eine Zeile mehr. Ein Schritt hinter dem Halt ist ein
        Schritt, den es nicht gibt (§15.3) — also sagt die Sitzung das, statt
        ihn zu schreiben.

        **Und sie sagt, wie es weitergeht** (Regel 17): Die Absage trägt die
        Handlungen des Halts selbst — dieselben Knöpfe, die der Prüfbericht an
        seiner Zeile zeigt —, dazu Schrittkennung, Werte und Körper, damit sie
        hier genauso tragen wie dort (``MainWindow.error_handlers``). Der
        Körper wird aufgelöst wie in ``panels.as_error``: aus dem Befund, sonst
        der einzige Eingang des Schritts.
        """
        if self._insert_before is not None:
            # **Und während einer Einfügemarke kommt nichts ans Ende** (P7.1):
            # Abläufe mit eigener Buchführung — Teilen mit Stiften, Deckel,
            # Gegenstück, Auto Split, Erzeugen, ein Agentenvorschlag — hängen
            # ihre Schritte an. Hinter der Marke gezeigt, vor ihr gerechnet,
            # wäre das ein Schritt an einer Stelle, die der Kunde nicht sieht.
            return self._inserting_refusal()
        halted = self.halted_step()
        if halted is None:
            return None
        op_id, title = halted
        result = self.last_result
        assert result is not None
        halt = next(
            (
                finding
                for finding in result.scene.report.findings
                if finding.severity == "error" and finding.op_id == op_id
            ),
            None,
        )
        step = next((entry for entry in self.project.document.ops if entry.id == op_id), None)
        object_id = halt.object_id if halt is not None else None
        if object_id is None and step is not None and len(step.inputs) == 1:
            object_id = step.inputs[0]
        # Die Werte des Halts, ohne die zwei, die der Satz schon sagt: „Art“
        # ist bei einem Fehler des Schritts dessen Titel (``_finding_from``),
        # die Nummer steht als „Schritt 1“ im Satz — der Dialog zeigte beide
        # noch einmal als „Art: Die Eingabe war so nicht verwendbar.“ und
        # „Operation: 1“ (KUNDE-12). Die Handler lesen ``op_id``.
        values = dict(halt.values) if halt is not None else {}
        if halt is not None and halt.code.startswith("op."):
            values.pop("kind", None)
        values.pop("op", None)
        return UserError(
            _("Die Kette hält an — ein neuer Schritt dahinter würde nicht gerechnet."),
            _(
                "Angehalten ist Schritt {number} ({step}): {reason}",
                number=op_id,
                step=title,
                reason=halt.message,
            )
            if halt is not None
            else _("Angehalten ist Schritt {number} ({step}).", number=op_id, step=title),
            suggestions=(halt.suggestions if halt is not None else (SHOW_HISTORY, CANCEL))
            or (CANCEL,),
            values=values,
            object_id=object_id,
            op_id=op_id,
        )

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
        self._changed()
        return True

    def split_and_retry(self, stopped_at: int, target: str, count: int) -> bool:
        """Setzt die Zerlegung und den erneuten Versuch als einen Zug vor den Fehler.

        Das Gegenstück zu :meth:`repair_and_retry` für einen Körper aus losen
        Teilen, der als Ganzes nirgends hinpasst; Reihenfolge und Undo gehören
        auch hier dem Verlauf.
        """
        try:
            self.history.split_and_retry(stopped_at, target, count)
        except AppError as error:
            self.failed.emit(error)
            return False
        self._changed()
        return True

    def recount_and_retry(self, op_id: int, count: int) -> bool:
        """Setzt die Stückzahl eines Schritts auf die gemessene und plant den Rest neu.

        Das dritte Geschwister von :meth:`repair_and_retry`; Reihenfolge und
        Undo gehören dem Verlauf.
        """
        try:
            self.history.recount_and_retry(op_id, count)
        except AppError as error:
            self.failed.emit(error)
            return False
        self._changed()
        return True

    def decimate_and_retry(
        self, stopped_at: int, triangles: int, values: Mapping[str, Any] | None = None
    ) -> bool:
        """Setzt *Dreiecke verringern* und den erneuten Versuch als einen Zug vor den Fehler.

        Das vierte Geschwister von :meth:`repair_and_retry`, für ein Netz, das
        zum Teilen schon zu dicht ist; die Zahl nennt der Befund, Reihenfolge
        und Undo gehören dem Verlauf. ``values`` gibt dem Schritt dabei die
        Werte aus dem offenen Dialog (``History.decimate_and_retry``).
        """
        try:
            self.history.decimate_and_retry(stopped_at, triangles, values)
        except AppError as error:
            self.failed.emit(error)
            return False
        self._changed()
        return True

    def remesh_and_retry(
        self, stopped_at: int, edge: float, values: Mapping[str, Any] | None = None
    ) -> bool:
        """Setzt *Kanten verfeinern* und den erneuten Versuch als einen Zug vor den Fehler.

        Für ein *Glätten*, das umschlug, weil die Dreiecke für die Wand zu grob
        sind; die Länge nennt der Befund (``values["remesh_to_mm"]``),
        Reihenfolge und Undo gehören dem Verlauf (``History.remesh_and_retry``).
        """
        try:
            self.history.remesh_and_retry(stopped_at, edge, values)
        except AppError as error:
            self.failed.emit(error)
            return False
        self._changed()
        return True

    def change_parameter(self, name: str, value: float, origin: Origin | None = None) -> bool:
        """Eine gedrehte Zahl der Parameterleiste (§13, §15.5).

        Sie war lange keine Transaktion: die Leiste schrieb geradewegs ins
        Dokument. Damit war die Änderung weder rücknehmbar — ein Strg+Z nahm
        stattdessen die letzte Operation zurück — noch als Änderung erkennbar,
        und weil das Schließen nur sichert, was als geändert gilt, ging sie
        dabei verloren. ``origin`` und Rückgabewert: siehe :meth:`add_fit`.
        """
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
        # Die Zahl selbst ist harmlos — was an ihr hängt, nicht: Steht
        # ``=10/@a`` in einem zweiten Maß, macht eine Null hier die ganze Szene
        # unauswertbar. Der Kern hält deswegen an und schreibt einen Befund
        # (§15.3); hier lässt sich der Satz aber noch dort sagen, wo der Kunde
        # gerade dreht, statt ihn im Prüfbericht zu suchen.
        #
        # **Nur, wenn genau diese Zahl das Problem ist.** Eine Datei, deren
        # Ausdrücke schon vorher nicht aufgingen, muss änderbar bleiben — sonst
        # wäre die einzige Stelle gesperrt, an der man sie repariert (§2.1).
        problem = _unresolvable({**parameters, name: changed})
        if problem is not None and _unresolvable(parameters) is None:
            self.failed.emit(problem)
            return False
        # **Und an den Grenzen der Felder, die das Maß lesen** (RM-354). Breite
        # 5000 lief durch, die Kette hielt an *Quader* an, und die Ansicht stand
        # leer. Wie oben nur, wenn genau diese Zahl das Problem ist.
        document = self.project.document
        beyond = bounds_refusal(document, name, value)
        if beyond is not None and bounds_refusal(document, name, existing.value) is None:
            self.failed.emit(beyond)
            return False
        try:
            self.history.apply(
                _parameter_title(changed),
                changes=change_for(self.project.document, parameters={name: changed}),
                origin=origin or Origin(by="user"),
            )
        except AppError as error:
            self.failed.emit(error)
            return False
        self._changed()
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
        self._changed()
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
                _parameter_title(parameter),
                changes=change_for(self.project.document, parameters={parameter.name: parameter}),
                origin=origin or Origin(by="user"),
            )
        except AppError as error:
            self.failed.emit(error)
            return False
        self._changed()
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
            # Ein neuer Ausdruck treibt ein lesendes Feld so über seine Grenze
            # wie eine getippte Zahl (RM-354) — gesagt nur, wenn erst diese
            # Änderung das Problem ist.
            document = self.project.document
            beyond = bounds_refusal_with(document, {**parameters, name: parameter}, name)
            if beyond is not None and bounds_refusal_with(document, parameters, name) is None:
                raise beyond
            self.history.apply(
                _parameter_title(parameter),
                changes=change_for(self.project.document, parameters={name: parameter}),
                origin=origin or Origin(by="user"),
            )
        except AppError as error:
            self.failed.emit(error)
            return False
        self._changed()
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
        self._changed()
        return True

    def change_params(self, op_id: int, params: dict[str, Any]) -> bool:
        """Andere Parameter für eine Operation, die schon im Stapel steht (§15.4).

        Gibt zurück, ob die Änderung im Dokument steht — der Verlauf lehnt
        ab (abgelaufene Demo, ungültiger Wert, geänderte Objektzahl), und die
        Absage kommt über ``failed``. Wer sich etwas für die folgende
        Auswertung merkt, tut es nur bei ``True``: Nach einer Absage kommt
        keine, und der Merker träfe die nächste beliebige.
        """
        try:
            self.history.change_params(op_id, params)
        except AppError as error:
            self.failed.emit(error)
            return False
        self._changed()
        return True

    def reopen_recognition(self, object_ids: Sequence[str]) -> None:
        """Die Frage vor der Vollerkennung geladener Körper erneut stellen (§21.1).

        Die gespeicherte Wahl fällt (``History.reopen_recognition``), und die
        folgende Auswertung fragt mit Zeitschätzung und Speicherbedarf — je
        Körper, eine Auswertung für alle; ihre Antwort schreibt
        ``_on_finished`` wie beim Laden fest. **Ohne gespeicherte Wahl
        geschieht nichts** (Review N3): Es gäbe nichts zurückzunehmen, und ein
        neuer Lauf stellte keine Frage — er markierte nur das Projekt.

        Der Speichermerker des Prozesses fällt dabei mit
        (``local.forget_out_of_memory``): Wer nach einem Speicherfehler
        Programme schließt und es erneut versucht, bekam sonst ohne einen
        Versuch denselben Satz (Review N2).
        """
        if not self.history.reopen_recognition(object_ids):
            return
        forget_out_of_memory()
        self._changed()

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
        self._changed()
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
        self._changed()

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
        self._changed()

    def bake_strokes(self, op_id: int) -> bool:
        """Den Stand einer Formsitzung festschreiben (Entscheidung D).

        Das aktuelle Ergebnis wandert als Quelle ins Projekt, und die Operation
        bekommt sie als ``baked``. Danach wird sie nicht mehr gerechnet — bei
        zwanzig Etappen kostet jede Auswertung zwanzig Durchgänge, und genau
        das ist der Grund für diese Handlung.

        **Rücknehmbar wie jede Parameteränderung:** Das Festschreiben läuft
        über :meth:`change_params`, also als Transaktion, und ein Strg+Z gibt
        der Sitzung ihre Züge zurück. Eine Nachfrage davor gibt es deshalb
        nicht (Regel 19, nachgemessen am 22.09.2026).
        """
        document = self.project.document
        operation = next((entry for entry in document.ops if entry.id == op_id), None)
        if operation is None or operation.op != "sculpt_strokes":
            return False
        # Der Stand **unmittelbar nach dieser Formsitzung**, nicht der am Ende
        # des Stapels: ``last_result`` trug auch, was danach auf dem Körper
        # geschah — Verschieben um 10 mm steckte in der eingebetteten STL und
        # lief bei der nächsten Auswertung ein zweites Mal, aus 5…15 wurden
        # 15…25 (Gesamtreview 05.09.2026, UI-17). Gerechnet wird bis zu diesem
        # Schritt; die Auswertung sortiert nach Kennung, und der Cache kennt
        # jeden Schritt davor.
        up_to = dataclasses.replace(
            document, ops=[entry for entry in document.ops if entry.id <= op_id]
        )
        result = evaluate(
            up_to,
            self.evaluation_profile,
            quality=self.quality,
            cache=self.cache,
            sources=ProjectSources(self.project, base_dir=self.base_dir),
        )
        if result.stopped_at is not None:
            return False
        # Ein Körper hinein, einer heraus: Die Operation behält die
        # Objektkennung ihrer Eingabe, und das gesuchte Ergebnis steht unter
        # derselben in der Szene.
        entry = result.scene.objects.get(operation.inputs[0]) if operation.inputs else None
        if entry is None:
            return False

        source_id = self._embed_source(
            "generated", "sculpt.npz", as_mesh_data(entry.mesh).to_bytes()
        )
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
        source_id = next_source_id(document.sources)
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

    def _bind_filament_profiles(self) -> None:
        """Alte Profilplätze behalten die Identität der letzten vollständigen Szene."""
        from app.core.export import handover, threemf

        settings = self.project.document.print_settings
        result = self.last_result
        if (
            settings is None
            or settings.slot_profile_bindings is not None
            or not settings.slot_profiles
            or result is None
            or result is self.picture
            or result.stopped_at is not None
            or not result.scene.objects
        ):
            return
        slots = threemf.merge_slots(
            [
                threemf.AssemblyPart(as_mesh_data(body.mesh), slots=threemf.slots_for_object(body))
                for body in result.scene.objects.values()
            ]
        )
        self.project.document.print_settings = handover.bind_slot_profiles(settings, slots)

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
        self._bind_filament_profiles()
        self._dirty = True
        self.projectChanged.emit()

    def protected_features(self, object_id: str) -> tuple[FeatureId, ...]:
        """Welche Merkmale dieses Körpers als Sichtflächen gesperrt sind (§22.3)."""
        return self.project.document.protected.get(object_id, ())

    def set_protected(self, object_id: str, feature_id: str, on: bool) -> bool:
        """Ein Merkmal vor Trennnähten schützen oder wieder freigeben (RM-080).

        Dieselbe Bauart wie :meth:`set_print_settings` und aus demselben
        Grund: keine Operation, keine Transaktion — es entsteht keine
        Geometrie. Das Projekt gilt danach als geändert, damit die Sperre
        nicht beim nächsten Schließen verloren geht; die Ansicht holt sich den
        Stand über ``projectChanged``. Der Umschalter ist sein eigener Rückweg.

        Gibt zurück, ob sich etwas geändert hat — ein zweites „schützen" an
        derselben Fläche schreibt nichts und markiert nichts als geändert.
        """
        document = self.project.document
        marked = set(document.protected.get(object_id, ()))
        if on == (feature_id in marked):
            return False
        if on:
            marked.add(feature_id)
        else:
            marked.discard(feature_id)
        if marked:
            document.protected[object_id] = tuple(sorted(marked))
        else:
            document.protected.pop(object_id, None)
        self._dirty = True
        self.projectChanged.emit()
        return True

    def release_protection(self, object_id: str) -> int:
        """Alle Sperren dieses Körpers aufheben — der Ausweg, wenn neben ihnen
        keine Trennebene bleibt (``split.blocked_by_protection``).

        Gibt zurück, wie viele Merkmale frei geworden sind; null heißt, es
        war nichts gesperrt, und dann ändert sich auch nichts am Dokument.
        """
        document = self.project.document
        released = document.protected.pop(object_id, ())
        if not released:
            return 0
        self._dirty = True
        self.projectChanged.emit()
        return len(released)

    def set_export_choice(self, export_format: str, scheme: str | None = None) -> None:
        """Was dieses Projekt beim nächsten Export vorschlägt (§29, RM-141).

        Dieselbe Bauart wie :meth:`set_print_settings` daneben und aus
        demselben Grund: keine Operation, keine Transaktion — es entsteht
        keine Geometrie. Das Projekt gilt danach als geändert, damit die Wahl
        nicht beim nächsten Schließen verloren geht.

        ``scheme=None`` heißt „unverändert lassen": Wer ein 3MF schreibt,
        benutzt kein Namensschema, und sein Export soll das gemerkte nicht
        stillschweigend wegwerfen.
        """
        document = self.project.document
        wanted = document.export_scheme if scheme is None else scheme
        if (document.export_format, document.export_scheme) == (export_format, wanted):
            return
        document.export_format = export_format
        document.export_scheme = wanted
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

        Ein ZIP mit genau einem Modell geht hier durch; mehrere verlangen eine
        Wahl, und die gibt es nur auf dem Weg mit Arbeiter und Dialog.
        """
        if is_archive(name):
            name, payload = model_from_archive(name, payload, None)
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
        #: Das erste Modell eines Projekts kommt **mittig auf die Platte**, jedes
        #: weitere an die erste freie Stelle (§17.1, Schritt 6). Gefragt wird
        #: der Stapel, nicht die ausgewertete Szene: Er steht fest, bevor
        #: gerechnet wird, und die Entscheidung landet in den Parametern der
        #: Operation statt in einem Zustand, den die nächste Auswertung anders
        #: vorfindet (§15.1).
        first_model = not self.history.operations
        # **Wie der Körper heißen soll, entscheidet der Stapel**: Steht der
        # Dateiname dort schon, bekommt dieser eine Nummer dahinter. Die eben
        # eingebettete Quelle zählt sich dabei nicht selbst mit — gefragt sind
        # die Operationen, und ihre entsteht erst eine Zeile weiter unten.
        taken = names_in_use(self.project.document)
        try:
            plan = import_plan(
                source_id, path.name, payload, unit, first_model=first_model, taken=taken
            )
        except AppError:
            self._drop_source(source_id)
            raise

        # Die Sitzung kann eine Abweisung entweder melden oder nach außen
        # reichen. In beiden Fällen wird die Quelle zurückgenommen; nur so
        # bleiben lokaler Import und Download derselbe, vollständige Vorgang.
        before = {entry.id for entry in self.project.document.ops}
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
        else:
            self._track_import(before, source_id)
        return accepted

    def import_model_async(self, path: Path, unit: str = "auto") -> None:
        """Wie :meth:`import_model`, aber ohne den Hauptthread zu belegen.

        **Warum es diesen zweiten Weg gibt.** Gemessen an einer 3MF von 63 MB
        mit 32 Körpern: Das Lesen von der Platte kostet 0,09 s, das Zählen der
        Körper und Dreiecke in ``import_plan`` **14,1 s** — und das steht vor
        jeder Operation, weil der Stapel seine Objekt-IDs vorher vergibt (§11)
        und die Größengrenze vor dem Parsen greifen muss (§32).

        Vierzehn Sekunden im Hauptthread sind kein Wartezeiger, sondern ein
        eingefrorenes Fenster; Windows schreibt ab etwa fünf Sekunden „Keine
        Rückmeldung" in die Titelleiste.

        Der synchrone Weg bleibt daneben stehen: Die Kommandozeile und die
        Tests brauchen einen, der wirft statt zu melden.

        **Und schon das Lesen läuft im Arbeiter** (RM-224, :class:`_ReadWorker`):
        Eine Datei auf einem Laufwerk, das nicht antwortet, hielt das Fenster
        bis zum Zeitlimit des Systems an. Danach wird im Hauptthread
        eingebettet und **immer** im Arbeiter geplant: Der Grund für den
        geraden Weg unter :data:`PLAN_IN_WORKER_ABOVE` — ein Arbeiter
        verschiebe das Ergebnis hinter die Ereignisschleife, obwohl niemand
        wartet — gilt nicht mehr, wenn schon das Lesen nachgereicht wird. Damit
        verlässt auch die Strukturdurchsicht einer 3MF den Hauptthread
        (Siebhalter 290 bis 634 ms).
        """
        worker = _ReadWorker(path)
        self._plan = worker
        self.busyChanged.emit(True)
        worker.finished.connect(partial(self._on_plan_done, worker))
        stamp = self._project_generation

        def ready(data: object, stamp: int = stamp) -> None:
            if stamp != self._project_generation:
                return
            if self._cancel_by_user and self.cancel_signal.is_cancelled:
                # Abgebrochen, bevor etwas eingebettet war: Es gibt nichts
                # zurückzunehmen, nur das Signal zu verbrauchen — wie beim Plan.
                self._cancel_by_user = False
                self.cancel_signal.reset()
                self.importFinished.emit(False)
                return
            self._import_payload(
                path.name, cast(bytes, data), unit=unit, origin=None, in_worker=True
            )

        def failed(error: object, stamp: int = stamp) -> None:
            if stamp == self._project_generation:
                self.importFailed.emit(error)

        def stopped(stamp: int = stamp) -> None:
            # Abgebrochen, während das Laufwerk noch las: Eingebettet ist
            # nichts, und das Signal gehört niemandem mehr — es sei denn, eine
            # Auswertung läuft daneben und verbraucht es selbst (``_on_cancelled``).
            if stamp != self._project_generation:
                return
            if self._worker is None:
                self._cancel_by_user = False
                self.cancel_signal.reset()
            self.importFinished.emit(False)

        worker.readyWith.connect(ready)
        worker.failedWith.connect(failed)
        worker.stopped.connect(stopped)
        worker.crashed.connect(lambda detail: failed(InternalError(detail=detail)))
        self._leash.start(worker)

    def import_payload_async(
        self,
        name: str,
        payload: bytes,
        *,
        unit: str = "auto",
        origin: SourceOrigin | None = None,
    ) -> None:
        """Derselbe Weg für eine Datei ohne Pfad (§16.3), asynchron.

        **Eingebettet wird im Hauptthread, geplant im Arbeiter.** Die
        Kennungsregel ``src_<n>`` lebt in ``_embed_source`` und hängt am
        Dokument; sie in einen Arbeiter zu verlegen hieße, das Dokument aus
        zwei Fäden zu ändern. Teuer ist sie ohnehin nicht — teuer ist das
        Zählen danach.

        **Ein ZIP wird vorher aufgelöst** (:mod:`app.core.ingest.archive`):
        eingebettet wird das Modell darin, nie das Archiv mit Bildern und
        Anleitung.
        """
        self._import_payload(
            name,
            payload,
            unit=unit,
            origin=origin,
            in_worker=_plans_in_worker(name, len(payload)),
        )

    def _import_payload(
        self,
        name: str,
        payload: bytes,
        *,
        unit: str,
        origin: SourceOrigin | None,
        in_worker: bool,
    ) -> None:
        """Einbetten und planen — ``in_worker`` sagt, wo der Plan entsteht.

        Eine Datei vom Pfad kommt mit ``True`` (:meth:`import_model_async`),
        eine Nutzlast ohne Pfad nach ihrer Größe (:func:`_plans_in_worker`).
        """
        if is_archive(name):
            self._unpack_archive(name, payload, unit=unit, origin=origin)
            return
        path = Path(name)
        source_id = self._embed_source("import", path.name, payload, origin)
        first_model = not self.history.operations
        taken = names_in_use(self.project.document)

        # **Unter der Grenze bleibt es beim geraden Weg.** Ein Arbeiter für
        # einen Plan, der in Mikrosekunden steht, verschöbe das Ergebnis hinter
        # die Ereignisschleife, ohne dass jemand darauf gewartet hätte — und
        # jeder Aufrufer müsste danach auf ein Signal warten, auch wenn es
        # nichts zu warten gab. Wer schon gewartet hat, weil die Datei erst
        # gelesen wurde, plant immer im Arbeiter.
        if not in_worker:
            try:
                plan = import_plan(
                    source_id, path.name, payload, unit, first_model=first_model, taken=taken
                )
            except AppError as error:
                self._drop_source(source_id)
                self.importFailed.emit(error)
                return
            self._on_plan_ready(plan, source_id)
            return

        worker = _PlanWorker(
            source_id, path.name, payload, unit, first_model, taken, self.report_progress
        )
        self._plan = worker
        self.busyChanged.emit(True)
        # **An die Leine, wie jeder andere Arbeiter auch.** Ohne diese Zeile
        # holt der Speicherbereiniger den Arbeiter, während sein Faden noch
        # läuft: Der Lauf starb dann irgendwo später mit einer
        # Zugriffsverletzung — bei mir im Konstruktor des *nächsten*
        # Arbeiters, also weit weg von der Ursache. ``hold_until_done`` hält
        # ihn, bis ``isRunning`` nein sagt.
        worker.finished.connect(partial(self._on_plan_done, worker))
        # **Jede Meldung trägt das Dokument, für das sie gilt.** Zwischen Start
        # und Antwort kann der Nutzer ein neues Projekt anlegen oder ein anderes
        # öffnen — und das trägt wieder eine eigene ``src_1``. Ein verspäteter
        # Fehler räumte dann diese Quelle aus dem **neuen** Dokument samt
        # Nutzdaten (Gesamtreview 05.09.2026, UI-01). Der Zähler steht im
        # Aufruf, nicht im Arbeiter: Er ist die Zusage, dass die Antwort zu
        # dem Dokument gehört, das sie verändert.
        stamp = self._project_generation
        worker.readyWith.connect(
            lambda plan, src, stamp=stamp: self._on_plan_ready(plan, src, stamp)
        )
        worker.failedWith.connect(
            lambda error, src, stamp=stamp: self._on_plan_failed(error, src, stamp)
        )
        # Wie bei der Auswertung: Was niemand erwartet hat, wird zu einem
        # ``InternalError`` — sonst bliebe der Wartezustand für immer stehen.
        worker.crashed.connect(
            lambda detail, src=source_id, stamp=stamp: self._on_plan_failed(
                InternalError(detail=detail), src, stamp
            )
        )
        self._leash.start(worker)

    def _unpack_archive(
        self, name: str, payload: bytes, *, unit: str, origin: SourceOrigin | None
    ) -> None:
        """Das Modell aus dem Archiv holen und danach denselben Weg einlesen."""
        worker = _ArchiveWorker(name, payload, self.ask_from_worker)
        self._plan = worker
        self.busyChanged.emit(True)
        worker.finished.connect(partial(self._on_plan_done, worker))
        stamp = self._project_generation

        def ready(inner: str, data: object, stamp: int = stamp) -> None:
            if stamp != self._project_generation:
                return
            self._import_payload(inner, cast(bytes, data), unit=unit, origin=origin, in_worker=True)

        def failed(error: object, stamp: int = stamp) -> None:
            if stamp == self._project_generation:
                self.importFailed.emit(error)

        def dropped(stamp: int = stamp) -> None:
            if stamp == self._project_generation:
                self.importFinished.emit(False)

        worker.readyWith.connect(ready)
        worker.failedWith.connect(failed)
        worker.dropped.connect(dropped)
        worker.crashed.connect(lambda detail: failed(InternalError(detail=detail)))
        self._leash.start(worker)

    def _on_plan_done(self, worker: Any) -> None:
        """Der Faden ist ausgelaufen — halten, bis Qt wirklich fertig ist.

        Das Gegenstück zu ``_on_thread_done`` für den Einleseplan. Das Feld
        wird nur geleert, wenn es noch diesem Arbeiter gehört: Ein Nachzügler
        darf nicht den Nachfolger austragen.
        """
        if self._plan is worker:
            self._plan = None
            self.busyChanged.emit(self.busy)
        self._leash.hold_until_done(worker)

    def _stale_import(self, source_id: str, generation: int | None) -> bool:
        """Ob diese Meldung einem Dokument gilt, das nicht mehr offen ist.

        ``None`` ist der gerade Weg ohne Arbeiter: Er antwortet im selben
        Aufruf, in dem er gestartet wurde, und kann nicht veralten.
        """
        if generation is None or generation == self._project_generation:
            return False
        _log.info("import result for %s arrived after the project changed — ignored", source_id)
        return True

    def _on_plan_ready(self, plan: Any, source_id: str, generation: int | None = None) -> None:
        """Der Plan steht — anwenden gehört in den Hauptthread.

        ``History.apply`` ändert das Dokument und fragt die Lizenzgrenze; beides
        gehört dorthin, wo auch alles andere am Dokument geschieht.
        """
        if self._stale_import(source_id, generation):
            return
        if generation is not None and self._cancel_by_user and self.cancel_signal.is_cancelled:
            # **Abbrechen gilt auch dem Plan.** Der Knopf und die Wartefläche
            # führen zu ``cancel_evaluation``; das setzte das Signal, aber der
            # fertige Plan wurde trotzdem angewandt, und die Auswertung danach
            # setzte das Signal still zurück — das Objekt stand, das Dokument
            # war geändert (Gesamtreview 05.09.2026, UI-08). Ein abgebrochener
            # Einleseplan verwirft seine Quelle und wird nicht mehr angewandt.
            self._cancel_by_user = False
            self.cancel_signal.reset()
            self._drop_source(source_id)
            self.importFinished.emit(False)
            return
        if self.choose_outline and plan.draft.op == "load_outline":
            stamp = self._project_generation
            self._outline_imports[stamp, source_id] = plan
            self.outlineImportRequested.emit(plan, source_id, stamp)
            return
        # **Eine Baugruppe wird gewählt, bevor sie ankommt** (P7.4): Der Kunde
        # sieht jeden Körper und übernimmt, was er braucht. Mit einem Körper
        # gibt es nichts zu wählen.
        if self.choose_step_bodies and plan.draft.op == "load_step" and len(plan.choices) > 1:
            stamp = self._project_generation
            self._step_imports[stamp, source_id] = plan
            self.stepImportRequested.emit(plan, source_id, stamp)
            return
        self._apply_import_plan(plan, source_id)

    def finish_outline_import(
        self, source_id: str, generation: int, values: Mapping[str, Any] | None
    ) -> None:
        """Die Konturwahl genau einmal übernehmen oder ihre eingebettete Quelle verwerfen."""
        plan = self._outline_imports.pop((generation, source_id), None)
        if plan is None or self._stale_import(source_id, generation):
            return
        if values is None:
            self._drop_source(source_id)
            self.importFinished.emit(False)
            return
        draft = dataclasses.replace(plan.draft, params={**plan.draft.params, **values})
        self._apply_import_plan(dataclasses.replace(plan, draft=draft), source_id)

    def finish_step_import(
        self, source_id: str, generation: int, keys: Sequence[str] | None
    ) -> None:
        """Die Körperauswahl genau einmal übernehmen oder ihre eingebettete Quelle verwerfen.

        ``None`` heißt abgebrochen: Die Quelle geht wieder aus dem Dokument,
        wie bei jedem abgewiesenen Import — sonst reiste sie beim nächsten
        Speichern unsichtbar mit.
        """
        plan = self._step_imports.pop((generation, source_id), None)
        if plan is None or self._stale_import(source_id, generation):
            return
        if not keys:
            self._drop_source(source_id)
            self.importFinished.emit(False)
            return
        self._apply_import_plan(with_selection(plan, keys), source_id)

    def _apply_import_plan(self, plan: ImportPlan, source_id: str) -> None:
        """Den fertig gewählten Import anwenden; abgewiesene Quellen reisen nicht mit.

        Angenommen ist er damit noch nicht endgültig: Ob die Datei ein Modell
        enthält, sagt erst die Auswertung (:meth:`_settle_import`).
        """
        before = {entry.id for entry in self.project.document.ops}
        try:
            accepted = self.apply(plan.title, [plan.draft], raise_on_error=True)
        except AppError as error:
            self._drop_source(source_id)
            self.importFailed.emit(error)
            return
        if not accepted:
            self._drop_source(source_id)
        else:
            self._track_import(before, source_id)
        self.importFinished.emit(accepted)

    def _track_import(self, before: set[int], source_id: str) -> None:
        """Den eben angenommenen Import bis zu seinem ersten Ergebnis vormerken."""
        added = frozenset(entry.id for entry in self.project.document.ops) - before
        last = self.history.transactions[-1] if self.history.transactions else None
        # Nur ein Import, der eine eigene Transaktion ist: Ein gebündelter
        # nähme mit der Rücknahme fremde Schritte mit.
        self._unconfirmed_import = (
            (last.id, added, source_id)
            if last is not None and added and frozenset(last.ops) == added
            else None
        )

    @property
    def import_unconfirmed(self) -> bool:
        """Ob der zuletzt angenommene Import noch auf sein erstes Ergebnis wartet."""
        return self._unconfirmed_import is not None

    def _settle_import(self, result: EvaluationResult) -> bool:
        """Nach dem ersten Stand, der den Import enthält: behalten oder zurücknehmen.

        **Eine Datei ohne Modell wird kein Schritt** (KUNDE-12). Eine STL, die
        nur Text ohne gültige Ecken enthält — ein abgebrochener Download —,
        passiert den Einleseplan und scheitert erst am Ladeschritt. Bis zur
        Durchsicht 0.5.1 blieb sie dann als Schritt 1 stehen: leerer
        Arbeitsbereich, „Die Kette hält an“, jede weitere abgelegte Datei
        abgewiesen, und sie stand in „Zuletzt geöffnet“. Jetzt geht sie den
        Weg jedes anderen Lesefehlers: Der Import wird zurückgenommen (ohne
        Redo, die Quelle geht mit), und das Fenster zeigt den Grund mit
        *Andere Datei wählen*.

        Zurückgenommen wird nur, was eindeutig an der Datei liegt — ein
        ``ValidationError`` des Ladeschritts — und nur, solange der Import die
        letzte Transaktion ist. Gibt ``True`` zurück, wenn er zurückgenommen
        wurde; das Ergebnis gilt dann nichts mehr.
        """
        pending = self._unconfirmed_import
        if pending is None:
            return False
        self._unconfirmed_import = None
        transaction_id, op_ids, source_id = pending
        if result.stopped_at not in op_ids:
            self.importConfirmed.emit()
            return False
        halt = next(
            (
                entry
                for entry in result.scene.report.findings
                if entry.severity == "error"
                and entry.op_id == result.stopped_at
                and entry.code.endswith(".ValidationError")
            ),
            None,
        )
        if halt is None:
            return False
        source = self.project.document.sources.get(source_id)
        name = Path(source.path).name if source is not None else ""
        if self.history.withdraw(transaction_id) is None:
            return False
        self._drop_source(source_id)
        fresh = self.path is None and not self.history.can_undo
        self._changed()
        if fresh:
            # Ein neues Projekt, in dem nie etwas ankam, ist nicht geändert.
            self._dirty = False
            self.projectChanged.emit()
        self.importRejected.emit(
            UserError(
                title=_("Diese Datei ließ sich nicht lesen."),
                detail=halt.message,
                values={"path": name} if name else {},
                suggestions=(CHOOSE_ANOTHER_FILE, CANCEL),
            )
        )
        return True

    def _on_plan_failed(self, error: Any, source_id: str, generation: int | None = None) -> None:
        """Die Quelle wird zurückgenommen, wie im synchronen Weg auch.

        Sonst bliebe sie als Waise im Dokument und wanderte mit dem nächsten
        Speichern in die Projektdatei — bei einer abgewiesenen 63-MB-Datei ist
        das nicht theoretisch.

        **Aber nur aus dem Dokument, für das der Import lief.** Nach einem
        Projektwechsel trägt das neue womöglich dieselbe Kennung, und die
        gehört ihm (UI-01).
        """
        if self._stale_import(source_id, generation):
            return
        self._drop_source(source_id)
        self.importFailed.emit(error)

    def _drop_source(self, source_id: str) -> None:
        """Eine eben eingebettete Quelle wieder austragen.

        Zwei Wörterbücher, und beide gehören dazu: das Dokument nennt sie,
        das Projekt hält ihren Inhalt. Wer nur eines räumt, lässt entweder
        einen Namen ohne Datei oder hunderte Megabyte ohne Namen zurück.
        """
        self.project.document.sources.pop(source_id, None)
        self.project.sources.pop(source_id, None)

    def embed_model_payload(self, name: str, payload: bytes) -> str:
        """Bettet einen bereits begrenzt gelesenen Modellinhalt ein.

        Dieser zweite Eingang trennt Arbeiterarbeit von Dokumentänderung: Der
        Arbeiter liest die Datei, der Hauptthread reicht nur noch Bytes und
        Namen herein. Die Freischaltung wird an beiden öffentlichen Grenzen
        selbst geprüft; kein Aufrufer muss ihren Zustand weiterreichen.
        """
        activation.require(activation.CHANGE)
        source_id = self._embed_source("import", name, payload)
        self._dirty = True
        self.projectChanged.emit()
        return source_id

    def import_image_payload(self, name: str, payload: bytes) -> str:
        """Bettet einen bereits begrenzt gelesenen Bildinhalt ein.

        Der Aufrufer darf damit das Plattenlesen in einen Arbeiter verlegen,
        ohne das Dokument außerhalb seines Hauptthreads anzufassen.
        """
        activation.require(activation.CHANGE)
        source_id = self._embed_source("image", name, payload)
        self._dirty = True
        self.projectChanged.emit()
        return source_id

    def add_generated(self, result: GeneratedMesh) -> str:
        """Weg 3: einen erzeugten Körper einbetten, laden, reparieren (§2.2).

        Die eine Transaktion entsteht im Kern (RM-372); was hier passiert,
        ist das Neuzeichnen danach — genau wie bei einem Import. Und wie dort
        kommt hinter einen Halt kein Schritt (:meth:`halt_in_the_way`).
        """
        refusal = self.halt_in_the_way()
        if refusal is not None:
            raise refusal
        generation = generate_into(self.project, result)
        self._changed()
        return generation.object_id

    def follow_print_settings(self, source: Callable[[], PrintSettings]) -> None:
        """Woher die Druckeinstellungen kommen, die gedruckt werden.

        Das Fenster kennt die Grundlage aus dem Herstellerprofil, die Sitzung
        nicht: Gespeichert ist die eigene Wahl samt dem Stand der Grundlage
        vom letzten Speichern (Review Stufe A+B, R3). Gehalten wird schwach,
        über ``WeakMethod`` — das Fenster besitzt die Sitzung, und ein
        Rückverweis schlösse einen Ring.
        """
        self._effective_print_settings = weakref.WeakMethod(source)

    def split_margin(self) -> float:
        """Der Rand, den *Automatisch teilen* zum Bettrand lässt (:func:`bed_margin`).

        Aus den Druckeinstellungen, die gedruckt werden
        (:meth:`follow_print_settings`), sonst aus denen des Projekts oder,
        ohne sie, aus denen, die das Profil vorgibt — dieselbe Quelle wie die
        Vorbelegung des Anordnens.
        """
        reference = self._effective_print_settings
        source = reference() if reference is not None else None
        if source is not None:
            return bed_margin(source())
        settings = self.project.document.print_settings
        if settings is None:
            settings = print_settings.resolve(self.profile)
        return bed_margin(settings)

    def auto_split(self, object_id: str) -> SplitApplied:
        """§25: ein Teil schneiden, bis es passt, mit Stiften und
        Passungspaaren (§14).

        Die Suche braucht den ausgewerteten Körper, also wartet das hier auf den
        letzten Lauf, statt aus dem Stapel zu raten — eine Teilung eines
        veralteten Netzes legte die Trennebene dorthin, wo das Teil nicht mehr
        ist.
        """
        if not self.wait_for_idle():
            raise _evaluation_busy_error()
        refusal = self.halt_in_the_way()
        if refusal is not None:
            raise refusal
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
            margin=self.split_margin(),
        )
        if applied.transaction is not None:
            self._changed()
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
        refusal = self.halt_in_the_way()
        if refusal is not None:
            raise refusal
        result = self.last_result
        entry = result.scene.objects.get(object_id) if result is not None else None
        applied = apply_line_split(
            self.project.document,
            object_id,
            plane,
            mesh=as_mesh_data(entry.mesh) if entry is not None else None,
            features=entry.features if entry is not None else None,
            pins=pins,
            shape=shape,
        )
        self._changed()
        return applied

    def split_pinned(
        self, object_ids: Sequence[str], params: Mapping[str, Any], *, title: Any
    ) -> SplitApplied:
        """*Teilen* aus dem Dialog — mit den Passungspaaren jeder Naht (§14).

        Derselbe Ablauf wie :meth:`split_along`, nur mit der Ebene aus Achse
        und Position: Bis zum 22.09.2026 legte der Dialog allein den Schritt
        an, und die Stifte standen ohne Passung da.
        """
        refusal = self.halt_in_the_way()
        if refusal is not None:
            raise refusal
        result = self.last_result
        targets = []
        for object_id in object_ids:
            entry = result.scene.objects.get(object_id) if result is not None else None
            targets.append(
                SplitTarget(
                    object_id,
                    mesh=as_mesh_data(entry.mesh) if entry is not None else None,
                    features=entry.features if entry is not None else None,
                )
            )
        applied = apply_pinned_split(self.project.document, targets, params, title=title)
        self._changed()
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
        refusal = self.halt_in_the_way()
        if refusal is not None:
            raise refusal
        applied = apply_lid(self.project.document, object_id, params, op=op)
        self._changed()
        return applied

    def create_counterpart(
        self,
        pair: Pair,
        first_object: str,
        second_object: str,
        shared: Mapping[str, Any],
        first_place: Mapping[str, Any],
        second_place: Mapping[str, Any],
    ) -> CounterpartApplied:
        """Beide Gegenstücke samt Passung als eine ungespeicherte Änderung übernehmen."""
        refusal = self.halt_in_the_way()
        if refusal is not None:
            raise refusal
        applied = apply_counterpart(
            self.project.document,
            pair,
            first_object,
            second_object,
            shared,
            first_place,
            second_place,
        )
        # Erst die Auswertung liefert die Kennungen der erzeugten Merkmale.
        # Die Passung gehört an dieselbe Transaktion wie die beiden Hälften.
        self._finish_after(
            lambda scene: attach_fit(self.project.document, applied, pair, scene), applied
        )
        self._changed()
        return applied

    def create_thread_counterpart(
        self,
        feature: Any,
        first_object: str,
        second_object: str,
        second_place: Mapping[str, Any],
    ) -> CounterpartApplied:
        """Das Gegenstück zu einem vorhandenen Gewinde samt Passung, eine Änderung (P2.6)."""
        refusal = self.halt_in_the_way()
        if refusal is not None:
            raise refusal
        applied = apply_thread_counterpart(
            self.project.document, feature, first_object, second_object, second_place
        )
        self._finish_after(
            lambda scene: attach_thread_fit(self.project.document, applied, feature, scene),
            applied,
        )
        self._changed()
        return applied

    def _finish_after(self, attach: Callable[[Any], Any], applied: CounterpartApplied) -> None:
        """Die Passung nachtragen, sobald die Auswertung im Arbeiter durch ist.

        **Bis zum 21.09.2026 lief hier ``evaluate_now``** — im Hauptthread,
        ohne Fortschritt, ohne Abbrechen: 0,34 s an zwei Netzplatten, 18,6 s
        an zwei exakten (gemessen, Review Fenster #2). Die Schritte stehen mit
        ``_changed`` sofort im Dokument; die Auswertung geht ihren gewohnten
        Weg mit Balken und Abbrechen, und der Abschluss läuft, sobald ein
        gültiges Ergebnis **dieses** Dokuments da ist (:meth:`_run_finishers`).
        Ein Projektwechsel dazwischen lässt ihn verfallen — dieselbe Zusage,
        die ``_stale_import`` dem Einleseplan gibt (UI-01).
        """
        known = len(applied.findings)

        def finish(scene: Any) -> None:
            attach(scene)
            self.counterpartFinished.emit(tuple(applied.findings[known:]))

        self._after_evaluation.append((self._project_generation, finish))

    def _run_finishers(self, result: Any) -> None:
        """Die wartenden Abschlüsse dieses Dokuments — jeder genau einmal.

        Ein Abschluss darf das Dokument ändern und ruft dann ``_changed``;
        die nächste Auswertung rechnet aus dem Cache und prüft die Passung.
        Abschlüsse eines früheren Dokuments werden verworfen, nicht gefahren.
        """
        if not self._after_evaluation:
            return
        pending, self._after_evaluation = self._after_evaluation, []
        for generation, finish in pending:
            if generation != self._project_generation:
                _log.info("counterpart finish arrived after the project changed — dropped")
                continue
            finish(result.scene)
            self._changed()

    def preview_async(
        self,
        then: Any,
        drafts: list[OperationDraft] | None = None,
        *,
        change_op: int | None = None,
        change_values: dict[str, Any] | None = None,
        change_name: str | None = None,
        changes: DocumentChange | None = None,
        explained: Any = None,
        coarse: Any = None,
        advised: Any = None,
        failed: Any = None,
        progressed: Any = None,
        refused: Any = None,
        counted: Any = None,
        asked: Any = None,
    ) -> None:
        """Die Live-Vorschau des Operationsdialogs (§18.7).

        Eine neuere Anfrage ersetzt die wartende — gerechnet wird beides,
        gezeigt nur das Jüngste. ``then`` bekommt die ``SceneDifference``
        oder ``None``, wenn es nichts zu zeigen gibt. ``explained`` bekommt
        davor den Grund als Satz, wenn es einen gibt — ein Fehler der
        Operation oder der Befund, an dem die Kette anhielt. ``coarse``
        bekommt die Dreieckszahl davor, wenn die Vorschau auf einer
        verkleinerten Kopie gerechnet wurde (:data:`COARSE_PREVIEW_ABOVE`).
        ``advised`` bekommt vor dem Satz die Kennung der vorrangigen Handlung,
        die der Fehler dazu trägt — ``repair_and_retry`` und seinesgleichen
        nennen einen Schritt, der vor das Übernehmen gehört.
        ``failed`` meldet einen unerwarteten Arbeiterfehler an den aktuellen
        Editor, damit dessen Übernahme gesperrt bleibt und ein Hinweis erscheint.
        ``progressed`` bekommt ``(Anteil, laufender Schritt)`` der Auswertung —
        das Fenster zeigt daraus ab zwei Sekunden Balken und *Abbrechen*
        (§2.8), und :meth:`cancel_preview` hält die Rechnung an.
        ``refused`` bekommt die Absage samt Werten und Handlungen (ein
        ``AppError`` oder den ``Finding`` des Halts), ``counted`` die
        Dreieckszahlen eines Schritts, der nur das Netz ändert. ``asked``
        bekommt ``None``, wenn die Vorschau an einer Rückfrage anhielt — vor
        dem Satz dazu, der dann keine Absage ist (RM-389).
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
        snapshot = _Snapshot.of(self, change_op)

        def compute() -> tuple[Any, SceneDifference | None, str]:
            # ``worker`` steht unten und ist beim **Aufruf** gebunden — die
            # Rechnung läuft im Arbeiter, nicht hier. Gemeldet wird über sein
            # Signal und nicht über einen nackten Rückruf: Was in ``work``
            # geschieht, geschieht im fremden Faden, und ein direkter Aufruf
            # ins Fenster hinein wäre genau der Fehler, den ``done`` und
            # ``explained`` vermeiden.
            return self._preview_outcome(
                list(drafts or []),
                change_op=change_op,
                change_values=change_values,
                change_name=change_name,
                changes=changes,
                cancelled=cancel,
                coarsened=(
                    None
                    if coarse is None
                    else (lambda triangles: worker.coarse.emit(generation, triangles))
                ),
                counselled=(
                    None
                    if advised is None
                    else (lambda action: worker.advised.emit(generation, action))
                ),
                progress=(
                    None
                    if progressed is None
                    else (lambda fraction, text: worker.progressed.emit(generation, fraction, text))
                ),
                refused=(
                    None if refused is None else (lambda why: worker.refused.emit(generation, why))
                ),
                counted=(
                    None
                    if counted is None
                    else (lambda numbers: worker.counted.emit(generation, numbers))
                ),
                # Der Dialog zeigt Geometrie und Differenz, keine Merkmale:
                # Eine Erkennung je getippter Zahl wäre eine Sekunde für nichts.
                detect_features=False,
                snapshot=snapshot,
            )

        # Was jetzt noch rechnet, rechnet für eine Frage von gestern: die
        # Generation hätte sein Ergebnis ohnehin verworfen (``_preview_done``).
        self.cancel_previews()
        worker = _PreviewWorker(self, generation, compute, cancel)
        worker.done.connect(lambda stamp, difference: self._preview_done(stamp, difference, then))
        if explained is not None:
            worker.explained.connect(
                lambda stamp, reason: self._preview_done(stamp, reason, explained)
            )
        if coarse is not None:
            worker.coarse.connect(
                lambda stamp, triangles: self._preview_done(stamp, triangles, coarse)
            )
        if advised is not None:
            worker.advised.connect(lambda stamp, action: self._preview_done(stamp, action, advised))
        if refused is not None:
            worker.refused.connect(lambda stamp, why: self._preview_done(stamp, why, refused))
        if counted is not None:
            worker.counted.connect(
                lambda stamp, numbers: self._preview_done(stamp, numbers, counted)
            )
        if asked is not None:
            worker.asked.connect(lambda stamp: self._preview_done(stamp, None, asked))
        if progressed is not None:
            worker.progressed.connect(
                lambda stamp, fraction, text: self._preview_done(
                    stamp, (fraction, text), progressed
                )
            )
        # Technische Einzelheiten gehören ins Protokoll. Ein abhängiger Editor
        # kann seine Freigabe zurücknehmen und den Hinweis direkt am Feld zeigen.
        worker.crashed.connect(lambda detail: _log.warning("preview crashed: %s", detail))
        if failed is not None:
            worker.crashed.connect(lambda detail: self._preview_done(generation, detail, failed))
        worker.finished.connect(lambda done=worker: self._preview_finished(done))
        self._previews.append(worker)
        self._leash.start(worker)

    def placement_async(self, compute: Any, then: Any, failed: Any, refused: Any = None) -> None:
        """Berechnet einen Platzierungsbezug oder Anzeigegeist abseits des Fensters.

        Der Aufrufer hält höchstens eine laufende Anfrage je Kanal und ersetzt
        ihren Nachfolger. Die Sitzung hält den Arbeiter auch nach Dialogende;
        das Ergebnis trägt niemals eine Änderung am Dokument.

        Eine Absage des Kerns (``AppError``) kommt als ``refused(error)`` vor
        ``then(None)`` — der Aufrufer nennt ihren Satz statt eines allgemeinen.
        """
        worker = _PreviewWorker(self, 0, lambda: (None, compute(), ""), CancelSignal())
        # Die PySide-Kontextüberladung ist in den Stubs nicht erfasst. Der
        # Empfänger bindet sämtliche Rückrufe an den Thread der Sitzung.
        if refused is not None:
            worker.refused.connect(lambda _stamp, error: refused(error), self)  # type: ignore[arg-type]
        worker.done.connect(lambda _stamp, value: then(value), self)  # type: ignore[arg-type]
        worker.crashed.connect(failed, self)  # type: ignore[arg-type]
        worker.finished.connect(
            lambda done=worker: self._placement_finished(done),
            self,  # type: ignore[arg-type]
        )
        self._placements.append(worker)
        self._leash.start(worker)

    def placement_before(self, op_id: int, then: Any, failed: Any) -> None:
        """Zeigt beim Korrigieren den Eingangszustand genau dieses Schritts.

        Spätere Verschiebungen und Verformungen gehören nicht zu dessen
        Koordinatenraum. Die Kopie entsteht vor dem Arbeiterstart; sie ist
        eine Vorschau und wird niemals in das Dokument zurückgeschrieben.
        """
        import copy

        document = copy.deepcopy(self.project.document)
        document.ops[:] = [entry for entry in document.ops if entry.id < op_id]
        sources = ProjectSources(self.project, base_dir=self.base_dir)
        profile = self.evaluation_profile
        self.placement_async(
            lambda: evaluate(
                document,
                profile,
                quality=self.quality,
                cache=self.cache,
                sources=sources,
                ask=_no_questions,
            ),
            then,
            failed,
        )

    def _placement_finished(self, worker: _PreviewWorker) -> None:
        """Die Rechenarbeit gehört bis zum zugestellten Ende der Sitzung."""
        if worker in self._placements:
            self._placements.remove(worker)
        self._leash.hold_until_done(worker)

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
        """Der Dialog ist zu oder die Vorschau abgebrochen — was noch rechnet, hört auf.

        Die Generation allein genügte nicht: Sie **verwarf** das Ergebnis,
        angehalten hat sie nichts. Wer einen Dialog über einem großen Körper
        schloss, ließ eine Rechnung hinter sich, die niemand mehr sehen wollte
        und die trotzdem bis zum Ende lief.

        Mit angehalten wird die Vorbereitung der groben Stufe: Auf ihr Ergebnis
        wartet jetzt niemand mehr. Wer dagegen nur eine neue Zahl tippt, ruft
        :meth:`supersede_preview`.
        """
        self.supersede_preview()
        self._stop_coarse_preparation()

    def supersede_preview(self) -> None:
        """Eine neue Anfrage ersetzt die laufende Vorschau — die Vorbereitung bleibt.

        Die alte Antwort wird verworfen und ihr Arbeiter angehalten. Die
        Verkleinerung des unveränderten Eingangs läuft weiter: Die nächste
        Vorschau braucht dieselbe, und angehalten müsste sie beim nächsten
        Tastendruck von vorn beginnen. Genau so kam es an der Lochplatte mit
        815 104 Dreiecken zu 27 bis 30 s Verkleinerung **je** Loslassen des
        Platzierungsgriffs — die Auswertung legt ihre Ergebnisse erst nach
        einem vollständigen Durchlauf in den Cache, und ein abgelöster Lauf ist
        keiner (Bericht Ansicht, 23.09.2026).
        """
        self._preview_generation += 1
        self.cancel_previews()

    def _stop_coarse_preparation(self) -> None:
        """Die laufende Vorbereitung anhalten; die nächste bekommt ein frisches Signal."""
        self._coarse_cancel.cancel()
        self._coarse_cancel = CancelSignal()

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
        if not self.wait_for_idle():
            self.failed.emit(_evaluation_busy_error())
            return
        refusal = self.halt_in_the_way()
        if refusal is not None:
            self.failed.emit(refusal)
            return
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
        # **Die Sperren gehen mit — hier, und nirgends sonst.** Bis zum
        # 14.09.2026 kannte der Kern ``protect`` und die Ansicht die
        # Markierung, aber kein Aufrufer reichte das eine an das andere: Eine
        # geschützte Fläche war ein Bild ohne Wirkung (RM-080).
        worker = _SplitWorker(
            as_mesh_data(entry.mesh),
            object_id,
            object_profile,
            entry.features,
            protect=protected_patches(entry, self.protected_features(object_id)),
            margin=self.split_margin(),
        )
        # Jeder Empfänger bekommt den Absender mit: Was ein überlebender
        # Arbeiter eines früheren Starts noch meldet, zählt nicht mehr.
        worker.done.connect(lambda plan: self._split_planned(worker, plan, object_id, then))
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
        then: Any,
    ) -> None:
        if worker is not self._split:
            return
        self.splitBusyChanged.emit(False)
        if self._split_discarded:
            return
        applied = apply_planned(self.project.document, plan, object_id)
        if applied.transaction is not None:
            self._changed()
        then(applied)

    def undo(self) -> Transaction | None:
        transaction = self.history.undo()
        if transaction is None:
            return None
        self._changed()
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
        self._changed()
        return True

    def redo(self) -> None:
        if self.history.redo() is not None:
            self._changed()

    # --- Umbau des Verlaufs (RM-188 P7) ------------------------------------------

    @property
    def inserting(self) -> OpId | None:
        """Vor welchen Schritt neue Schritte gerade kommen — ``None`` heißt: ans Ende."""
        return self._insert_before

    def displayed_document(self) -> Any:
        """Das Dokument, das die Oberfläche zeigt — bei einer Einfügemarke der Stand davor.

        Eine flache Kopie mit den Schritten vor der Marke und ohne Passungen:
        Passungen gelten dem Endstand, und am Stand davor wäre ihr Merkmal oft
        noch gar nicht da (§14). Das Dokument selbst bleibt, wie es ist.
        """
        document = self.project.document
        marker = self._insert_before
        if marker is None:
            return document
        return dataclasses.replace(
            document, ops=[entry for entry in document.ops if entry.id < marker], fits=[]
        )

    def start_inserting(self, before: int) -> bool:
        """Die Einfügemarke vor ``before`` setzen (P7.1).

        Danach zeigt die ganze Oberfläche den Stand vor diesem Schritt —
        Ansicht, Baum, Merkmale, Prüfbericht —, und jede Operation über
        :meth:`apply` wird dort eingefügt. Kein Dokumentzustand und keine
        Transaktion: Die Marke ändert nichts, sie zeigt nur, wohin es geht.
        """
        try:
            step = self.history.operation(int(before))
        except AppError as error:
            self.failed.emit(error)
            return False
        if self._insert_before == step.id:
            return True
        self._insert_before = step.id
        self.insertionChanged.emit(step.id)
        self.result_current = False
        self.projectChanged.emit()
        self.evaluate_async()
        return True

    def stop_inserting(self) -> None:
        """Die Einfügemarke entfernen — die Oberfläche zeigt wieder den Endstand."""
        if self._insert_before is None:
            return
        self._insert_before = None
        self.insertionChanged.emit(None)
        self.result_current = False
        self.projectChanged.emit()
        self.evaluate_async()

    def _keep_insertion_valid(self) -> None:
        """Nach einer Änderung: Gibt es den Schritt der Marke nicht mehr, ist sie weg.

        Strg+Z nach einem Einfügen legt die alte Folge mit ihren alten
        Kennungen zurück; die Marke zeigte auf die neue. Eine Marke vor einem
        Schritt, den es nicht gibt, stünde am Ende und hieße dort anders als
        im Verlauf — sie geht, und der Verlauf sagt es.
        """
        marker = self._insert_before
        if marker is None:
            return
        if any(entry.id == marker for entry in self.project.document.ops):
            return
        self._insert_before = None
        self.insertionChanged.emit(None)

    def _inserting_refusal(self) -> UserError:
        """Die Absage für einen Ablauf, der nur ans Ende kann — mit dem Weg dorthin."""
        return UserError(
            _("Das geht nicht mitten im Verlauf."),
            _(
                "Dieser Ablauf hängt seine Schritte ans Ende. Beenden Sie zuerst das "
                "Einfügen, dann geht er dort weiter."
            ),
            suggestions=(STOP_INSERTING, CANCEL),
            op_id=self._insert_before,
        )

    def step_needs(self) -> tuple[StepNeed, ...]:
        """Welcher Schritt welchen braucht — Körper und Merkmale, für den Verlauf (P7.2)."""
        result = self.last_result if self.result_current and self._insert_before is None else None
        return step_needs(
            self.project.document, revision_dependencies(self.project.document, result)
        )

    def move_targets(self, op_ids: Sequence[int]) -> tuple[MoveTarget, ...]:
        """Wohin die gewählten Schritte könnten — mit dem Grund, wo nicht (P7.2).

        Nur lesend und ohne Rechnung; die Merkmalskanten kommen aus der letzten
        Auswertung, solange sie zum Dokument gehört.
        """
        result = self.last_result if self.result_current and self._insert_before is None else None
        try:
            return self.history.valid_targets(
                op_ids, revision_dependencies(self.project.document, result)
            )
        except AppError:
            return ()

    def revise_history(self, kind: str, op_ids: Sequence[int], before: int | None = None) -> bool:
        """Schritte verschieben, aus- oder einschalten — geplant, isoliert gerechnet, übernommen.

        ``kind`` ist ``move`` (vor ``before``, ``None`` ans Ende), ``suppress``
        oder ``reactivate``. Geplant wird sofort, damit eine unmögliche Stelle
        ohne Wartezeit ihren Satz sagt; gerechnet wird im Arbeiter (§2.8), und
        erst ein gültiges Ergebnis ersetzt die Folge — als **eine**
        Transaktion, ohne Nachfrage (Regel 19). Eine Einfügemarke endet
        vorher: Umbauten gelten dem ganzen Verlauf.
        """
        if self._revision is not None:
            self.failed.emit(
                UserError(
                    _("Ein Umbau des Verlaufs läuft noch."),
                    _("Warten Sie, bis er fertig ist, oder brechen Sie ihn ab."),
                    suggestions=(CANCEL,),
                )
            )
            return False
        self.stop_inserting()
        baseline = self.last_result if self.result_current else None
        wanted = tuple(int(op_id) for op_id in op_ids)

        def planned(
            history: History,
            context: Dependencies,
            _run: Callable[[Any], EvaluationResult] | None = None,
        ) -> RevisionPlan:
            if kind == "suppress":
                return history.plan_suppress(wanted, context)
            if kind == "reactivate":
                return history.plan_reactivate(wanted, context)
            if kind == "move":
                return history.plan_move(wanted, before, context)
            raise InternalError(detail=f"unknown history revision {kind!r}")

        if baseline is not None:
            try:
                plan = planned(self.history, revision_dependencies(self.project.document, baseline))
            except AppError as error:
                self.failed.emit(error)
                return False
            return self._start_revision(plan, baseline)
        return self._start_revision(planned, None)

    def _insert(
        self,
        title: TranslatableText | str,
        drafts: list[OperationDraft],
        origin: Origin | None,
        changes: DocumentChange | None,
        *,
        raise_on_error: bool = False,
    ) -> bool:
        """Die Schritte vor die Einfügemarke setzen (P7.1) — geplant sofort, gerechnet im Arbeiter.

        Der Grundstand für den Vergleich ist der ganze Verlauf, nicht der Stand
        davor, den die Oberfläche gerade zeigt; der Arbeiter rechnet ihn zuerst
        (der Cache trägt das meiste). Nach dem Übernehmen rückt die Marke
        hinter den neuen Schritt — wer mehrere einfügt, fügt sie der Reihe nach ein.

        **Ein weiteres Modell sucht seine freie Stelle am Endstand**, nicht am
        Stand vor der Marke, den ``last_result`` zeigt: Dort steht ein
        späteres, schon festgehaltenes Modell noch nicht, und beide lägen
        deckungsgleich (Review N4). Der Arbeiter plant deshalb ein zweites Mal,
        mit der Stelle im Entwurf (:func:`searched_at_the_end`); geplant wird
        hier trotzdem sofort, damit eine unmögliche Stelle ohne Wartezeit
        ihren Satz sagt.
        """
        marker = self._insert_before
        assert marker is not None
        if self._revision is not None:
            error = UserError(
                _("Ein Umbau des Verlaufs läuft noch."),
                _("Warten Sie, bis er fertig ist, oder brechen Sie ihn ab."),
                suggestions=(CANCEL,),
            )
            if raise_on_error:
                raise error
            self.failed.emit(error)
            return False
        by = origin or Origin(by="user")
        try:
            self.history.plan_insert(marker, title, drafts, by, changes)
        except AppError as error:
            if raise_on_error:
                raise
            self.failed.emit(error)
            return False

        def planned(
            history: History, _context: Dependencies, run: Callable[[Any], EvaluationResult]
        ) -> RevisionPlan:
            settled = searched_at_the_end(history.document, title, drafts, evaluate=run)
            return history.plan_insert(marker, title, settled, by, changes)

        return self._start_revision(planned, None)

    def _start_revision(
        self,
        planned: RevisionPlan | _Planner,
        baseline: EvaluationResult | None,
    ) -> bool:
        """Den Arbeiter für einen Umbau starten — mit einer Kopie des Dokuments von jetzt."""
        import copy

        self._revision_cancel = CancelSignal()
        worker = _RevisionWorker(
            self, copy.deepcopy(self.project.document), planned, baseline, self._revision_cancel
        )
        worker.revisedWith.connect(partial(self._on_revised, finished=worker))
        worker.failedWith.connect(partial(self._on_revision_failed, finished=worker))
        worker.cancelled.connect(partial(self._on_revision_cancelled, finished=worker))
        worker.crashed.connect(
            lambda detail, done=worker: self._on_revision_failed(
                InternalError(detail=detail), finished=done
            )
        )
        worker.finished.connect(partial(self._on_revision_done, worker))
        self._revision = worker
        self.busyChanged.emit(True)
        self._leash.start(worker)
        return True

    def _on_revised(self, revision: Revision, finished: _RevisionWorker | None = None) -> None:
        """Der Vorschlag ist gültig: genau diesen Plan übernehmen — oder sagen, warum nicht."""
        if finished is not None and (
            finished is not self._revision
            or finished._project_generation != self._project_generation
        ):
            return
        try:
            commit_revision(self.history, revision)
        except AppError as error:
            self.failed.emit(error)
            return
        if revision.plan.kind == "insert" and self._insert_before is not None:
            # Die Marke rückt mit: Sie stand vor einem Schritt, der jetzt eine
            # neue Kennung trägt — und davor steht der eingefügte.
            self._insert_before = revision.plan.new_id(self._insert_before)
            self.insertionChanged.emit(self._insert_before)
        self._changed()
        self.revisionDone.emit(revision)

    def _on_revision_failed(self, error: Any, finished: _RevisionWorker | None = None) -> None:
        if finished is not None and finished is not self._revision:
            return
        self.failed.emit(error)

    def _on_revision_cancelled(self, finished: _RevisionWorker | None = None) -> None:
        if finished is not None and finished is not self._revision:
            return
        self.revisionCancelled.emit()

    def _on_revision_done(self, finished: _RevisionWorker) -> None:
        """Der Umbau ist ausgelaufen — nur der aktuelle räumt sein Feld."""
        if finished is self._revision:
            worker, self._revision = self._revision, None
            self._leash.hold_until_done(worker)
            self.busyChanged.emit(self.busy)
            return
        self._leash.hold_until_done(finished)

    # --- evaluation -------------------------------------------------------------

    def evaluate_async(self) -> None:
        """Ein Lauf je Dokument; eine neuere Anfrage ersetzt eine wartende (§15.6)."""
        self.result_current = False
        if self._worker is not None and self._worker.isRunning():
            self._rerun_pending = True
            self.cancel_signal.cancel()
            self.questionInvalidated.emit()
            return
        self.cancel_signal.reset()
        self._cancel_by_user = False
        # Im Hauptthread: Das Fenster rechnet seine Grundlage mit Qt-Objekten,
        # der Arbeiter liest nur das Ergebnis (:attr:`evaluation_profile`).
        self._evaluation_settings = self._current_effective_settings()
        worker = _EvaluationWorker(self, picture_first=self.picture_first())
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
        worker.pictureWith.connect(partial(self._on_picture, finished=worker))
        worker.finished.connect(partial(self._on_thread_done, worker))
        self._worker = worker
        self.busyChanged.emit(True)
        self._leash.start(worker)

    def picture_first(self) -> bool:
        """Ob der nächste Lauf das Modell vor seiner Erkennung zeigt (KUNDE-14).

        **Das gilt dem Ladeweg**: einem Ladeschritt, dessen Körper noch nicht
        im Bild standen — ein Import auf die Startfläche oder in ein Projekt,
        ein geöffnetes Projekt, eine Sicherung. Gefragt wird an
        ``object_names`` und nicht an der Szene: Dort stehen auch Körper, die
        ein späterer Schritt verbraucht hat. Und solange ein Bild steht, zeigt
        auch der nächste Lauf erst eins — sonst ließe eine Verschiebung während
        der Erkennung das Modell bis zu deren Ende an der alten Stelle.

        Jede andere Änderung rechnet wie bisher: Dort steht ein Modell im Bild,
        und das bleibt stehen, bis das Ergebnis kommt (§15.3). Ob wirklich eine
        lange Erkennung folgt, entscheidet erst das Bild
        (:func:`_recognition_follows`).
        """
        if self.picture is not None:
            return True
        last = self.last_result
        shown = last.object_names if last is not None else {}
        # Ein Ladeschritt, an dem der letzte Lauf anhielt, lädt nicht schneller,
        # wenn man ihn zweimal rechnet.
        halted = last.stopped_at if last is not None else None
        return any(
            operation.op == "load"
            and operation.suppressed is None
            and operation.id != halted
            and not all(output in shown for output in operation.outputs)
            for operation in self.displayed_document().ops
        )

    def run_evaluation(
        self, quality: Quality | None = None, *, detect_features: bool = True
    ) -> EvaluationResult:
        """Ein Durchlauf mit allem, was der Kern braucht. Keine Signale, kein
        Zustand.

        ``detect_features=False`` rechnet das Bild vor der Erkennung
        (:meth:`picture_first`); der Lauf danach ist derselbe Auftrag.
        """
        # Ein einmalig angeforderter Lauf gilt für diesen und keinen weiteren:
        # Wer die volle Kette braucht, braucht sie an einer Stelle, und alles
        # danach soll wieder so schnell sein wie vorher (§31). Das Bild davor
        # verbraucht ihn nicht — es gehört zum selben Lauf.
        once = self._quality_once
        if detect_features:
            self._quality_once = None
        # Bei einer Einfügemarke der Stand davor (P7.1) — die ganze Oberfläche
        # zeigt und löst gegen ihn auf, bis das Einfügen endet.
        document = self.displayed_document()
        result = evaluate(
            document,
            self.evaluation_profile,
            quality=quality or once or self.quality,
            progress=self.report_progress,
            ask=self.ask_from_worker,
            question_context=self.announce_question,
            cancelled=self.cancel_signal,
            cache=self.cache,
            sources=ProjectSources(self.project, base_dir=self.base_dir),
            detect_features=detect_features,
            on_recognition_answer=self._recognition_answered_in_worker,
        )
        # Bei jedem Lauf und nicht nur beim Öffnen: Solange mit einem
        # mitgebrachten oder einem Ersatzdrucker gerechnet wird, sagt es der
        # Bericht — sonst verschwände der Satz mit der ersten Änderung, und
        # der Ersatz liefe still weiter.
        extra = list(profiles.carried_findings(document.printer, document.material))
        if self._insert_before is not None:
            # Und dass der Bericht einem Zwischenstand gilt (P7.1): Ein Teil vor
            # Schritt 5 ist nicht das fertige, auch wenn nichts daran fehlt.
            extra.append(
                Finding(
                    code="history.inserting",
                    severity="info",
                    message=_(
                        "Zu sehen ist der Stand vor Schritt {number}. "
                        "Neue Schritte kommen hierhin.",
                        number=self._insert_before,
                    ),
                    op_id=self._insert_before,
                    suggestions=(STOP_INSERTING,),
                )
            )
        return _with_findings(result, extra)

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
        """Synchroner Durchlauf, für Kommandozeile, Tests und Export (§38).

        **Ein Arbeiter, der jetzt noch läuft, ist danach überholt.** Er rechnet
        am Stand, den er beim Start bekam, und der ist spätestens jetzt alt;
        meldete er sich nach diesem Lauf, überschriebe er das frische Ergebnis
        mit dem des Stands davor — gemessen am 21.09.2026: Nach einem
        Bausteinschritt und diesem Lauf stand im Objektbaum die Szene ohne den
        Baustein, und das Fenster hielt eine markierte Zeile für nicht gewählt.
        """
        worker = self._worker
        self._rerun_pending = False
        self._cancel_by_user = False
        self._superseded = worker
        if worker is not None:
            self.cancel_signal.cancel()
            self.questionInvalidated.emit()
            if not worker.wait(SYNC_EVALUATION_END_WAIT_MS):
                raise UserError(
                    title=_("Die neue Berechnung kann noch nicht starten."),
                    detail=_(
                        "Die vorherige Berechnung wurde nicht rechtzeitig beendet. "
                        "Die neue Berechnung wurde deshalb nicht gestartet."
                    ),
                    suggestions=(CANCEL,),
                )
        self.cancel_signal.reset()
        self._evaluation_settings = self._current_effective_settings()
        result = self.run_evaluation("fine")
        self.picture = None
        self.last_result = result
        # Wie in ``_on_finished``: Mit dem Ergebnis wartet keine Zustimmung mehr.
        self._recognition_answers.clear()
        # Die grobe Kopie gehört der Szene, aus der sie entstand. Ohne dieses
        # Wegräumen hielte sie die **vorige** Szene am Leben — bei einem Netz
        # dieser Größe genau das, was die Stufe einsparen soll. Eine
        # Vorbereitung, die noch für die vorige rechnet, rechnet für niemanden.
        self._coarse_scene = None
        self._stop_coarse_preparation()
        self._bind_filament_profiles()
        self.result_generation += 1
        self.result_current = True
        self.sceneChanged.emit(result)
        self._run_finishers(result)
        return result

    def remember_analyses(
        self, key: tuple[Any, ...], meshes: Sequence[object], results: Mapping[str, Any]
    ) -> None:
        """Gemessene Schichten über das Fenster hinaus behalten.

        Der Druckdialog wird bei jedem Öffnen neu gebaut und schnitt bis zum
        19.09.2026 jeden Körper jedes Mal neu — Sekunden bis Minuten für
        dieselben Netze (Befund Robert: „Vorschläge beim Slicen dauern ewig").
        Genau **ein** Stand wird gehalten, der letzte; die Netze dazu auch,
        damit ihre Adressen im Schlüssel nicht an ein neues Netz vergeben
        werden, solange der Eintrag lebt.
        """
        self._analysis_memory = (tuple(key), tuple(meshes), dict(results))

    def remembered_analyses(self, key: tuple[Any, ...]) -> dict[str, Any]:
        """Die gemerkten Schichten zu diesem Schlüssel — oder nichts."""
        if self._analysis_memory is None or self._analysis_memory[0] != tuple(key):
            return {}
        return dict(self._analysis_memory[2])

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
        # Und ein laufender Umbau des Verlaufs (P7): Abgebrochen ist nichts geändert.
        self._revision_cancel.cancel()

    def cancel_evaluation(self) -> None:
        """Hält nur die Auswertung samt eingereihtem Nachlauf an."""

        self._cancel_by_user = True
        self._rerun_pending = False
        self.cancel_signal.cancel()
        if isinstance(self._plan, _ReadWorker):
            # Das Lesen einer Datei hat seinen eigenen Schalter: Es wartet
            # womöglich auf ein Laufwerk, und der Klick soll sofort gelten.
            self._plan.cancel.cancel()
        self.questionInvalidated.emit()

    def cancel_agent(self) -> None:
        """Hält nur den laufenden Agentenzug an."""

        self.agent_cancel.cancel()

    # --- der Agent (§26) --------------------------------------------------------

    @property
    def agent_backend(self) -> LLMBackend | None:
        """Das Modell, das der Chat benutzt, oder None — dann ist der Chat
        aus (§27).
        """
        if self._backend is None and not self._backend_probed:
            self._backend = first_available()
            self._backend_probed = True
        return self._backend

    @property
    def backend_known(self) -> bool:
        """Ob die Modellfrage beantwortet ist — sonst kostet :attr:`agent_backend`
        Schlüsselbund und Netz, und das gehört in einen Arbeiter
        (``MainWindow._refresh_chat_availability``)."""
        return self._backend is not None or self._backend_probed

    def set_agent_backend(self, backend: LLMBackend | None) -> None:
        """Das Modell von Hand wählen — der Einstellungsdialog, der Arbeiter
        der Modellfrage und die Suite tun das.
        """
        self._backend = backend
        self._backend_probed = True

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
        # §23: die Ansichten entstehen HIER, im Hauptthread — der Renderer ist
        # nicht threadsicher, und ein zweiter Grafikkontext im Arbeiter neben
        # dem lebenden Viewport ist genau die Familie von Abstürzen, die dieses
        # Projekt unter VTK schon zweimal gejagt hat. Zwei kleine Bilder kosten
        # deutlich unter 200 ms (§2.8); scheitert das Rendern, läuft der Zug ohne
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
        worker = _AgentWorker(self, request, backend, _Snapshot.of(self))
        worker.finishedWith.connect(partial(self._on_agent_proposal, finished=worker))
        worker.failedWith.connect(partial(self._on_agent_failed, finished=worker))
        worker.crashed.connect(
            lambda detail, done=worker: self._on_agent_failed(
                InternalError(detail=detail), finished=done
            )
        )
        worker.finished.connect(partial(self._on_agent_done, worker))
        self._agent = worker
        self._leash.start(worker)

    def run_proposal(
        self,
        request: str,
        backend: LLMBackend | None = None,
        *,
        snapshot: _Snapshot | None = None,
    ) -> ProposalPreview:
        """Ein Agentenzug plus seine Vorschau. Läuft im Arbeiter (§26.5).

        ``snapshot`` ist der Stand beim Senden (:class:`_Snapshot`); ohne ihn
        — Kommandozeile, Tests, ein Aufruf im Hauptfaden — wird er hier
        gezogen.
        """
        backend = backend if backend is not None else self.agent_backend
        if backend is None:  # pragma: no cover - vor dem Start des Arbeiters abgesichert
            raise AppError(tr("Für den Chat fehlt der Zugang zu einem Sprachmodell."))
        snapshot = snapshot if snapshot is not None else _Snapshot.of(self)

        agent = AgentSession(
            backend=backend,
            document=snapshot.document,
            profile=snapshot.profile,
            sources=ProjectSources(self.project, base_dir=self.base_dir),
            ask=self.ask_from_worker,
            selection=self._selection,
            cancelled=self.agent_cancel,
            progress=self.agentProgress.emit,
            views=self._pending_views,
        )
        proposal = agent.propose(request)
        preview = ProposalPreview(proposal=proposal)
        if proposal.creates_something:
            preview.scene, preview.difference = self._preview_of(proposal, snapshot)
        return preview

    def _preview_of(
        self, proposal: Proposal, snapshot: _Snapshot | None = None
    ) -> tuple[Any, SceneDifference | None]:
        """Wonach die Szene aussähe — auf einer Kopie gerechnet, in
        Entwurfsqualität, auf dem Stand, auf dem der Zug gerechnet hat.
        """
        snapshot = snapshot if snapshot is not None else _Snapshot.of(self)
        return self.preview_scene(
            list(proposal.drafts),
            origin=proposal.origin,
            ask=self.ask_from_worker,
            changes=agent_apply.changes_for(proposal, snapshot.document),
            snapshot=snapshot,
        )

    def preview_scene(
        self,
        drafts: list[OperationDraft],
        *,
        origin: Origin | None = None,
        ask: Any = None,
        changes: DocumentChange | None = None,
        snapshot: _Snapshot | None = None,
    ) -> tuple[Any, SceneDifference | None]:
        """Wonach die Szene aussähe — die Vorschau eines Agentenvorschlags.

        Auf einer Kopie des Dokuments, in Entwurfsqualität; der Cache trägt
        alle Schritte, die schon gerechnet sind. Ohne ``ask`` hält eine
        Rückfrage die Vorschau an, statt mitten ins Tippen ein Fenster zu
        stellen — was eine Frage braucht, hat keine stille Vorschau. Der
        Dialog geht mit seiner geänderten Operation direkt über
        :meth:`_preview_outcome`.
        """
        scene, difference, _reason = self._preview_outcome(
            drafts, origin=origin, ask=ask, changes=changes, snapshot=snapshot
        )
        return scene, difference

    def _preview_outcome(
        self,
        drafts: list[OperationDraft],
        *,
        origin: Origin | None = None,
        ask: Any = None,
        change_op: int | None = None,
        change_values: dict[str, Any] | None = None,
        change_name: str | None = None,
        changes: DocumentChange | None = None,
        cancelled: Any = None,
        coarsened: Any = None,
        counselled: Any = None,
        detect_features: bool = True,
        snapshot: _Snapshot | None = None,
        progress: Any = None,
        refused: Any = None,
        counted: Any = None,
    ) -> tuple[Any, SceneDifference | None, str]:
        """:meth:`preview_scene`, dazu der Grund, wenn es keine Vorschau gibt.

        ``change_op`` mit ``change_values`` zeigt statt neuer Schritte eine
        geänderte Operation des Stapels (§15.4). ``change_name`` verwendet
        dabei dieselbe Zwillingsumschaltung wie die spätere Übernahme.

        ``snapshot`` ist der im Hauptfaden gezogene Stand (:class:`_Snapshot`);
        im Arbeiter wird nur er gelesen und kopiert, nie das lebende Dokument.
        Ohne ihn — ein Aufruf im Hauptfaden — wird er hier gezogen.

        ``detect_features=False`` lässt die Merkmalserkennung aus, wo kein
        späterer Schritt sie braucht — der Weg des Dialogs, dessen Bild
        Geometrie und Differenz zeigt und keine Merkmale (``evaluate``).

        ``coarsened`` schaltet die **grobe Stufe** frei (§2.8): Oberhalb von
        :data:`COARSE_PREVIEW_ABOVE` rechnet die Vorschau auf einer
        verkleinerten Kopie des Eingangsnetzes und meldet die Dreieckszahl
        davor. Wer sie nicht mitgibt, bekommt die genaue Rechnung — der Agent
        etwa, dessen Vorschlag nicht in Millisekunden zu antworten braucht.

        ``counselled`` bekommt die Handlung, die der Halt mitbringt — derselbe
        Weg wie bei ``coarsened`` und aus demselben Grund: Das Ergebnis ist ein
        Dreiertupel, an dem drei Aufrufer und drei Tests hängen, und eine
        Auskunft **neben** dem Satz gehört nicht in dessen Zeichenkette.

        ``progress`` bekommt Anteil und Schritt der Auswertung, wie
        ``evaluate`` sie meldet — für Balken und *Abbrechen* im Fenster.

        **Was an der Dreieckszahl hängt, wird am Original gezählt**
        (RESTVERLAUF-04, nur mit ``coarsened``, also im Dialog). Ein Schritt
        mit Vorabzählung (``OperationSpec.expected_triangles``) bekommt keine
        verkleinerte Kopie: Deren Zahl ist nicht die des Kunden. Sagt die
        Zählung am Original ab, ist das die Antwort — ``refused`` bekommt die
        Absage mit ihren Handlungen, gerechnet wird nichts. Ändert der Schritt
        nur das Netz (``retriangulates``) und wüchse es über
        :data:`COARSE_PREVIEW_ABOVE`, ist die Zahl selbst die Vorschau:
        ``counted`` bekommt sie, und gerechnet wird ebenfalls nichts — die Form
        bleibt, und ein Bild von Millionen Dreiecken zeigte nichts anderes als
        das Modell davor. Sonst rechnet der Schritt am Original, und seine
        Differenz ist das neue Netz statt eines Booleschen Vergleichs.
        """
        import copy

        snapshot = snapshot if snapshot is not None else _Snapshot.of(self)
        before = snapshot.before
        counting = (
            self._counted_ahead(
                drafts,
                snapshot,
                change_op=change_op,
                change_values=change_values,
                change_name=change_name,
                ask=ask,
                cancelled=cancelled,
            )
            if coarsened is not None
            else None
        )
        if counting is not None and counting.refusal is not None:
            if refused is not None:
                refused(counting.refusal)
            advice = _advice_of(counting.refusal)
            if counselled is not None and advice:
                counselled(advice)
            return before, None, _reason_of(counting.refusal)
        if counting is not None and counting.enough:
            if counted is not None:
                counted(counting.numbers())
            return before, SceneDifference(), ""
        counted_bodies = counting.bodies if counting is not None else frozenset()
        coarse = _coarse_drafts(before) if coarsened is not None and change_op is None else []
        coarse = [draft for draft in coarse if not counted_bodies.intersection(draft.inputs)]
        # Der Flächenbezug meint die Originalkontur einschließlich Bohrungen.
        # Eine vorgeschaltete Reduktion änderte ihre Dreiecke und Kennung.
        exact_faces = {
            body
            for draft in drafts
            if draft.op == "apply_texture" and draft.params.get("coverage") == "whole_face"
            for body in draft.inputs
        }
        exact_faces |= {
            body for draft in drafts if _names_a_feature(draft.params) for body in draft.inputs
        }
        if exact_faces:
            coarse = [draft for draft in coarse if not exact_faces.intersection(draft.inputs)]
        # Eine eigene Kopie auch des Stands: Der Rückweg unten rechnet ihn ein
        # zweites Mal, und diese Kopie trägt dann schon die Vorschauschritte.
        working = copy.deepcopy(snapshot.document)
        reduced: tuple[OpId, ...] = ()
        if coarse:
            # Derselbe Titel wie die Vorschau daneben: Diese Transaktion steht
            # in einer Dokumentkopie, die niemand je zu sehen bekommt, und ein
            # eigener Katalogeintrag für einen unsichtbaren Namen wäre eine
            # Zeile in fünf Sprachen für nichts.
            reduced = tuple(History(working).apply(_("Vorschau"), coarse).ops)
        changed_id: OpId | None = change_op
        if change_op is not None:
            history = History(working)
            if change_name is None:
                history.change_params(change_op, dict(change_values or {}))
            else:
                history.change_kernel(change_op, change_name, dict(change_values or {}))
            changed_index = next(
                index for index, entry in enumerate(working.ops) if entry.id == change_op
            )
            if (
                coarsened is not None
                and before is not None
                and not _names_a_feature(working.ops[changed_index].params)
                and not counted_bodies
            ):
                # **Die grobe Stufe auch beim Ändern eines Schritts** (22.09.2026).
                # Bis dahin blieb dieser Weg genau — die Verkleinerung musste
                # vor den geänderten Schritt, und ``History.apply`` hängt an.
                # Sie steht jetzt in der Kopie vor ihm, mit aufgerückten
                # Nummern (``_coarse_steps_before``); ``changed_id`` ist danach
                # die Nummer des geänderten Schritts in dieser Kopie.
                inserted = _coarse_steps_before(working, changed_index, before)
                if inserted:
                    reduced = tuple(entry.id for entry in inserted)
                    coarse = [
                        OperationDraft(op=entry.op, params=dict(entry.params), inputs=entry.inputs)
                        for entry in inserted
                    ]
                    changed_index += len(inserted)
                    changed_id = working.ops[changed_index].id
            previewed: tuple[OpId, ...] = tuple(entry.id for entry in working.ops[changed_index:])
        else:
            transaction = History(working).apply(
                _("Vorschau"), drafts, origin=origin or Origin(by="user"), changes=changes
            )
            previewed = tuple(transaction.ops)
        coarse_before: Any = None
        if coarse:
            # **Erst der Eingang, dann die Vorschau** (RM-208). Die Verkleinerung
            # des unveränderten Eingangs rechnet in einem eigenen Durchlauf, der
            # weder am Abbruch dieser Vorschau hängt noch an einem Halt ihres
            # Schritts — erst ein vollständiger Durchlauf legt seine Ergebnisse
            # in den Cache. Stand sie in der Auswertung der Vorschau, ging sie
            # mit jeder abgelösten Anfrage und jedem ungültigen Zwischenwert
            # verloren, und die nächste Zahl begann von vorn. Die Auswertung
            # darunter findet sie danach im Cache.
            #
            # **Und beide Seiten auf demselben groben Netz.** Getrennt
            # verkleinert liefen ``davor`` und ``danach`` überall um Bruchteile
            # eines Millimeters auseinander, und die Differenz beider war nicht
            # die Änderung, sondern dieser Unterschied: gemessen an einer Kugel
            # aus 81 920 Dreiecken 16,7 mm³ Material, das niemand angefasst hat
            # — und die Rechnung darüber dauerte zehn bis fünfzig Sekunden
            # statt einer halben, weil zwei fast deckungsgleiche Häute der
            # schlimmste Fall für jeden Booleschen Kern sind.
            coarse_before = self._coarse_before(
                before, coarse, ask, cancelled, change_op=change_op, snapshot=snapshot
            )
            if coarse_before is None:
                return self._preview_outcome(
                    drafts,
                    origin=origin,
                    ask=ask,
                    change_op=change_op,
                    change_values=change_values,
                    change_name=change_name,
                    changes=changes,
                    cancelled=cancelled,
                    counselled=counselled,
                    detect_features=detect_features,
                    snapshot=snapshot,
                    progress=progress,
                    refused=refused,
                    counted=counted,
                )
        preview_profile = snapshot.profile
        if changes is not None:
            preview_profile = profiles.for_process(
                profiles.scene_profile(
                    working.printer or profiles.DEFAULT_PRINTER,
                    working.material or profiles.DEFAULT_MATERIAL,
                ),
                working.print_settings,
            )
        result = evaluate(
            working,
            preview_profile,
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
            detect_features=detect_features,
            progress=progress or _quiet_progress,
        )
        if reduced and (result.stopped_at in reduced or _kernel_gave_up(result)):
            # **Das Verkleinern selbst hat angehalten — oder der Kern am groben
            # Netz.** Dann ist die grobe Stufe die Ursache und nicht die Antwort;
            # gerechnet wird genau, und der Kunde sieht davon nichts als die
            # längere Wartezeit, über zwei Sekunden mit Balken und *Abbrechen*.
            return self._preview_outcome(
                drafts,
                origin=origin,
                ask=ask,
                change_op=change_op,
                change_values=change_values,
                change_name=change_name,
                changes=changes,
                cancelled=cancelled,
                counselled=counselled,
                detect_features=detect_features,
                snapshot=snapshot,
                progress=progress,
                refused=refused,
                counted=counted,
            )
        if result.stopped_at is not None:
            # Eine angehaltene Kette ist keine Vorschau: die leere Differenz
            # sähe aus wie „keine Änderung", und das wäre gelogen.
            #
            # **Und der Befund, der den Halt trägt, trägt auch die Handlung**
            # (Regel 17). „Erst reparieren, dann aushöhlen" nennt einen
            # Schritt, der vor das Übernehmen gehört; das Fenster graut den
            # Knopf daraufhin aus, statt den Kunden in denselben Halt laufen
            # zu lassen.
            if counselled is not None:
                advice = _stop_advice(result)
                if advice:
                    counselled(advice)
            # Die Knöpfe gehören dem Schritt des Dialogs: Hält ein späterer an,
            # schriebe *Die kleinste Kantenlänge nehmen* dessen Zahl ins Feld
            # eines anderen.
            own = previewed if change_op is None else (changed_id,)
            if refused is not None and result.stopped_at in own:
                blamed = _stop_finding(result)
                if blamed is not None:
                    refused(blamed)
            return result.scene, None, _stop_reason(result)
        if coarse:
            coarsened(_triangles_of(before))
            before = coarse_before
        # Der Vergleich kennt kein Abbruchsignal und kostet an großen Netzen
        # Sekunden; wer vorher abgebrochen hat, bekommt ihn nicht mehr.
        if cancelled is not None:
            cancelled.raise_if_cancelled()
        reshaped = _reshaped_only(working, previewed)
        difference = (
            compare_scenes(before, result.scene, retriangulated=reshaped)
            if before is not None
            else None
        )
        if difference is not None and counted is not None and reshaped:
            counted(_counts_of(before, result.scene, reshaped))
        if difference is not None:
            difference.findings = tuple(
                finding for finding in result.scene.report.findings if finding.op_id in previewed
            )
            if changed_id is not None and change_name is not None and before is not None:
                # Ein Erzeuger hat keinen exakten Eingang. Sein Wechsel zum
                # Netz-Zwilling wird erst zwischen den beiden Dokumentständen
                # sichtbar und muss trotzdem vor dem Übernehmen benannt werden.
                changed = next(entry for entry in working.ops if entry.id == changed_id)
                covered = {
                    finding.object_id
                    for finding in difference.findings
                    if finding.converts_exact_body
                }
                for object_id in changed.outputs:
                    previous = before.objects.get(object_id)
                    following = result.scene.objects.get(object_id)
                    if (
                        previous is not None
                        and following is not None
                        and previous.kind == "brep"
                        and following.kind == "mesh"
                        and object_id not in covered
                    ):
                        difference.findings += (
                            conversion_finding(
                                changed, REGISTRY.get(changed.op).title, previous, (object_id,)
                            ),
                        )
        # **Eine leere Vorschau mit einer Warnung ist keine leere Vorschau.**
        # *Textur in Filamente* an einem Körper ohne Farbinformation läuft
        # durch, ändert nichts und meldet als Befund, warum — und der Befund
        # stand im Prüfbericht, das Band sagte „am Volumen ändert sich nichts".
        # Der Satz gehört ins Band, solange die Zahl noch zu ändern ist.
        #
        # **Und eine Bauartänderung ist keine leere Vorschau.** *Flächen-
        # bearbeitung beenden* lässt jedes Dreieck, wo es war, und wandelt den
        # Körper trotzdem um; der Befund dazu ist die Auskunft der Vorschau
        # und keine Absage. Als Grund gelesen stand der Satz zweimal im Band
        # (gemessen am 21.09.2026, ``test_ui``).
        if difference is not None and not (
            difference.changed
            or difference.reshaped
            or difference.recoloured
            or any(finding.converts_exact_body for finding in difference.findings)
        ):
            return result.scene, difference, _warning_of(result, previewed)
        return result.scene, difference, ""

    def _coarse_before(
        self,
        before: Any,
        coarse: list[OperationDraft],
        ask: Any,
        cancelled: Any,
        *,
        change_op: OpId | None = None,
        snapshot: _Snapshot | None = None,
    ) -> Any:
        """Die Szene davor, auf genau denselben verkleinerten Netzen.

        Gerechnet wird sie über dieselben Operationen wie die Vorschau, damit
        beide Seiten Dreieck für Dreieck aus derselben Quelle stammen. Das
        kostet einmal je Auswertung; danach liegt jeder Schritt im Cache, und
        eine Zahl im Dialog zu ändern kostet nur noch die Operation selbst.

        **Das ist der Merker der Verkleinerung** (RM-208), geschlüsselt nach
        Szene und Schritt (``_coarse_scene``). Er rechnet unter dem Signal der
        Vorbereitung (``_coarse_cancel``) und nicht unter dem der Vorschau:
        Wird die Vorschau abgelöst, rechnet er zu Ende und legt die
        Verkleinerung in den Cache, und die nächste Zahl findet beides.
        ``cancelled`` gilt nur dem Warten auf einen anderen Arbeiter, der
        denselben Merker gerade anlegt.

        ``change_op`` nennt den geänderten Schritt: Dann stehen die
        Verkleinerungen wie in der Vorschau **vor** ihm
        (:func:`_coarse_steps_before`) statt am Ende des Stapels, und der
        Schritt selbst bleibt, wie er im Dokument steht.

        Gibt ``None`` zurück, wenn das Verkleinern nicht durchkommt — dann
        rechnet der Aufrufer genau.
        """
        held = self._coarse_scene
        if held is not None and held[0] is before and held[1] == change_op:
            return held[2]
        import copy

        preparation = self._coarse_cancel
        waiting = cancelled or NeverCancelled()
        while not self._coarse_lock.acquire(timeout=0.05):
            waiting.raise_if_cancelled()
        try:
            # Wer gewartet hat, findet womöglich, was der andere eben gemerkt hat.
            held = self._coarse_scene
            if held is not None and held[0] is before and held[1] == change_op:
                return held[2]
            snapshot = snapshot if snapshot is not None else _Snapshot.of(self)
            base = copy.deepcopy(snapshot.document)
            if change_op is None:
                History(base).apply(_("Vorschau"), coarse)
            else:
                index = next(
                    number for number, entry in enumerate(base.ops) if entry.id == change_op
                )
                _coarse_steps_before(base, index, before)
            result = evaluate(
                base,
                snapshot.profile,
                quality="draft",
                sources=ProjectSources(self.project, base_dir=self.base_dir),
                ask=ask or _no_questions,
                cache=self.cache,
                cancelled=preparation,
                # Wie die Vorschau selbst: Die Kopie davor zeigt Geometrie,
                # keine Merkmale.
                detect_features=False,
            )
            if result.stopped_at is not None:
                return None
            # Gemerkt nur für die Szene, die noch dasteht: Kam inzwischen eine
            # neue Auswertung (``_on_finished`` räumt den Platz), hielte der
            # Eintrag die alte Szene samt grober Kopie am Leben.
            current = self.last_result
            if current is not None and current.scene is before:
                self._coarse_scene = (before, change_op, result.scene)
            return result.scene
        finally:
            self._coarse_lock.release()

    def _counted_ahead(
        self,
        drafts: Sequence[OperationDraft],
        snapshot: _Snapshot,
        *,
        change_op: OpId | None,
        change_values: Mapping[str, Any] | None,
        change_name: str | None,
        ask: Any,
        cancelled: Any,
    ) -> _Counting | None:
        """Die Vorabzählung der vorgeschauten Schritte am Original — oder ``None``.

        ``None`` heißt: Kein Schritt zählt vorab, oder sein Eingang ist nicht zu
        haben, und die Vorschau geht ihren gewohnten Weg. Gezählt wird nur an
        Netzen; ein exakter Körper wird beim Vorschauen ohnehin genau gerechnet
        (``_coarse_drafts``), und seine Umwandlung muss das Band nennen.

        Beim Ändern eines Schritts ist der Eingang die Szene **vor** ihm, nicht
        die angezeigte (die ist nach ihm). Sie kommt aus einer Auswertung des
        Stapels bis dorthin — dieselbe wie beim Platzieren
        (:meth:`placement_before`), die Schritte liegen im Cache.
        """
        if change_op is None:
            steps = [(draft.op, dict(draft.params), tuple(draft.inputs)) for draft in drafts]
        else:
            entry = next((op for op in snapshot.document.ops if op.id == change_op), None)
            if entry is None:
                return None
            steps = [
                (
                    change_name or entry.op,
                    {**entry.params, **dict(change_values or {})},
                    tuple(entry.inputs),
                )
            ]
        specs = [REGISTRY.get(name) if REGISTRY.has(name) else None for name, _p, _i in steps]
        if not any(spec is not None and spec.expected_triangles is not None for spec in specs):
            return None
        scene = (
            snapshot.before
            if change_op is None
            else self._scene_before_step(snapshot, change_op, ask, cancelled)
        )
        if scene is None:
            return None
        try:
            known = expressions.resolve(snapshot.document.parameters)
        except AppError:
            return None
        counting = _Counting()
        bodies: set[str] = set()
        enough = True
        for spec, (_name, params, inputs) in zip(specs, steps, strict=True):
            count = spec.expected_triangles if spec is not None else None
            if spec is None or count is None:
                enough = False
                continue
            try:
                values = validate(spec.params, expressions.resolve_params(params, known))
            except AppError:
                # Ein Zwischenstand beim Tippen: Die Auswertung sagt es gleich.
                return None
            for name in inputs:
                body = scene.objects.get(name)
                if body is None or kind_of(body.mesh) != "mesh":
                    enough = False
                    continue
                mesh = body.mesh
                try:
                    estimate = count(mesh, values)
                except ValidationError as refusal:
                    counting.refusal = refusal
                    return counting
                bodies.add(name)
                counting.before += int(mesh.triangle_count)
                counting.after += int(estimate.triangles)
                counting.at_most = counting.at_most or bool(estimate.at_most)
                enough = enough and (
                    spec.retriangulates
                    and estimate.triangles > COARSE_PREVIEW_ABOVE
                    and estimate.triangles > mesh.triangle_count
                )
        counting.bodies = frozenset(bodies)
        counting.enough = enough and bool(bodies)
        return counting

    def _scene_before_step(self, snapshot: _Snapshot, op_id: OpId, ask: Any, cancelled: Any) -> Any:
        """Die Szene vor dem Schritt ``op_id`` — im Arbeiter, aus dem Cache; ``None`` bei Halt."""
        import copy

        document = copy.deepcopy(snapshot.document)
        index = next(
            (number for number, entry in enumerate(document.ops) if entry.id == op_id), None
        )
        if index is None:
            return None
        document.ops[:] = document.ops[:index]
        result = evaluate(
            document,
            snapshot.profile,
            quality="draft",
            sources=ProjectSources(self.project, base_dir=self.base_dir),
            ask=ask or _no_questions,
            cache=self.cache,
            cancelled=cancelled or NeverCancelled(),
            detect_features=False,
        )
        return result.scene if result.stopped_at is None else None

    def accept_proposal(self, preview: ProposalPreview) -> Transaction | None:
        """Legt den Vorschlag als eine Transaktion ins Dokument (§26.5).

        Gibt die Transaktion zurück — die automatische Übernahme (§26.5)
        zeigt ihre Kennung in der Übernommen-Leiste.

        Hinter einen Halt kommt auch ein Vorschlag nicht
        (:meth:`halt_in_the_way`): Seine Schritte stünden hinter dem
        angehaltenen und würden nie gerechnet — der Kunde hätte übernommen
        und nichts bekommen.
        """
        if preview.proposal.drafts:
            refusal = self.halt_in_the_way()
            if refusal is not None:
                raise refusal
        transaction = agent_apply.accept(preview.proposal, self.history)
        self._accepted[preview.proposal.request] = transaction.id if transaction else None
        self._changed()
        return transaction

    def discard_proposal(self, preview: ProposalPreview) -> None:
        """Wirft ihn weg — das Gespräch behält beide Beiträge (§26.3)."""
        agent_apply.discard(preview.proposal, self.project.document)
        self._dirty = True
        self.projectChanged.emit()

    # --- context callbacks ------------------------------------------------------

    def report_progress(self, fraction: float, text: str) -> None:
        self.progressChanged.emit(fraction, text)

    def announce_candidates(self, candidates: tuple[tuple[str, str] | EdgeTarget, ...]) -> None:
        """Was die **nächste** Frage dieses Fadens zur Wahl stellt (§21.3).

        ``orphans.check`` ruft es unmittelbar vor ``ask`` und danach wieder
        leer. Gemerkt statt durchgereicht, weil der Weg dazwischen die
        Ask-Schnittstelle des Kerns ist (``ctx.ask``, Regel 21) — die trägt
        eine Frage und ihre Antworten, und ein drittes Feld dort ginge jede
        Operation an, die je etwas fragt.

        **Je Faden ein Platz, nicht je Sitzung.** Solange nur die Auswertung
        fragte, war ein Platz eindeutig. Mit einem zweiten fragenden Arbeiter
        — das Einlesen, seit dem 03.09.2026 (3d-druck-85) — ist er es nicht
        mehr: Gemessen holte sich die Einheitenfrage des Einlesens
        („Millimeter oder Zoll?") die Kandidaten der Verweisfrage ab. Zwei
        falsche Auskünfte auf einmal, denn danach hebt die Einheitenfrage zwei
        Bohrungen hervor und die Frage über Bohrungen nichts.

        Ansagen und Fragen geschieht im selben Vorgang auf demselben Faden;
        ``threading.local`` trennt die Vorgänge damit genau dort, wo sie
        auseinandergehören, ohne die Ask-Schnittstelle anzufassen.
        """
        self._pending.candidates = tuple(candidates)

    def announce_question(
        self,
        preview: EvaluationResult | None,
        candidates: tuple[tuple[str, str] | EdgeTarget, ...],
    ) -> None:
        """Bindet die echte Zuordnungsvorschau an die nächste Frage dieses Fadens."""
        self._pending.preview = preview
        self._pending.temporary_preview = preview is not None
        self.announce_candidates(candidates)

    def question_is_current(self, request: AskRequest) -> bool:
        """Überholte Projekt- oder Arbeiterfragen dürfen keine Antwort übernehmen."""
        return (
            request.project_generation in (None, self._project_generation)
            and not self._stale(request.worker)
            and not (
                request.worker is not None
                and (self._rerun_pending or self.cancel_signal.is_cancelled)
            )
        )

    def _recognition_answered_in_worker(
        self, op_id: int, key: str, record: Mapping[str, Any]
    ) -> None:
        """Meldet die Antwort vor der Vollerkennung aus dem Arbeiter (§21.1)."""
        generation = getattr(self._pending, "project_generation", self._project_generation)
        self.recognitionAnswered.emit(generation, op_id, key, dict(record))

    def _record_recognition_answer(
        self, generation: int, op_id: int, key: str, record: dict[str, Any]
    ) -> None:
        """Hält die Antwort sofort am Stapel fest, nicht erst mit dem Ergebnis.

        Zwischen „Mit Merkmalserkennung laden“ und dem Ende der Erkennung
        können Minuten liegen, und die Oberfläche bleibt bedienbar (§2.8). Jede
        Änderung in dieser Zeit bricht den Lauf ab; ohne diesen Weg fand der
        Nachlauf keine Wahl, fragte noch einmal und begann von vorn (Review
        24.09.2026).
        """
        if generation != self._project_generation:
            return
        # Ein Ladeschritt, den ein Strg+Z inzwischen genommen hat, bekommt
        # nichts mehr, und ohne ihn wartet auch keine Zustimmung (Review N4).
        if not any(entry.id == op_id for entry in self.project.document.ops):
            return
        if self.history.record_matches({op_id: {key: record}}):
            self._dirty = True
            # Der Stern im Titel kommt mit der Antwort, nicht erst mit einem
            # Ergebnis, das womöglich nie kommt.
            self.projectChanged.emit()
        # Eine neue Meldung für denselben Körper ersetzt die alte: Nach einer
        # Zustimmung kann die Absage aus einem Speicherfehler folgen, und die
        # zurückgenommene Zustimmung böte sonst noch den Knopf nach einem
        # Abbruch an (Review R3).
        self._recognition_answers = [
            entry for entry in self._recognition_answers if entry[:2] != (op_id, key)
        ]
        self._recognition_answers.append((op_id, key, record))

    def recognition_interrupted(self) -> bool:
        """Ob eine bestätigte Vollerkennung noch ohne Ergebnis ist."""
        return any(record.get("allowed") is True for _op, _key, record in self._recognition_answers)

    def load_without_recognition(self) -> bool:
        """Nimmt die noch offenen Zustimmungen zurück und rechnet ohne Vollerkennung.

        Der Weg nach einem Abbruch während der langen Erkennung: Wer abbricht,
        weil es zu lange dauert, will das Modell sehen und nicht den Stand vor
        dem Import. Die Absage steht danach wie jede andere am Ladeschritt, und
        *Alle Merkmale erkennen* holt die Erkennung später nach.
        """
        declined: dict[int, dict[str, Any]] = {}
        for op_id, key, record in self._recognition_answers:
            if record.get("allowed") is True:
                declined.setdefault(op_id, {})[key] = {**record, "allowed": False}
        self._recognition_answers.clear()
        if not declined:
            return False
        self.history.record_matches(declined)
        self._dirty = True
        self._changed()
        return True

    def ask_from_worker(self, question: str, choices: list[str]) -> str:
        """Reicht die Frage ans Fenster und wartet auf die Antwort."""
        candidates = getattr(self._pending, "candidates", ())
        self._pending.candidates = ()
        asked_as = (question, tuple(choices))
        replay: dict[tuple[str, tuple[str, ...]], str | None] | None = getattr(
            self._pending, "replay", None
        )
        if replay is not None and asked_as in replay:
            # Das Bild vor der Erkennung hat genau das schon gefragt, am
            # selben Stand (``_EvaluationWorker._evaluate``).
            answer = replay[asked_as]
            if answer is None:
                raise QuestionDeclined
            return answer
        request = AskRequest(
            question=question,
            choices=list(choices),
            candidates=candidates,
            preview=getattr(self._pending, "preview", None),
            temporary_preview=getattr(self._pending, "temporary_preview", False),
            project_generation=getattr(
                self._pending, "project_generation", self._project_generation
            ),
            worker=getattr(self._pending, "worker", None),
        )
        if not self.question_is_current(request):
            raise OperationCancelled
        self.askRequested.emit(request)
        while not request.answered.wait(QUESTION_CANCEL_POLL_S):
            if not self.question_is_current(request):
                raise OperationCancelled
        if not self.question_is_current(request):
            raise OperationCancelled
        asked = getattr(self._pending, "asked", None)
        if asked is not None:
            asked[asked_as] = request.answer
        if request.answer is None:
            # Ohne Wahl geschlossen, und die Frage gilt noch: ein Abbruch der
            # **Frage**, nicht der Rechnung. Die Auswertung macht daraus einen
            # Befund am Schritt; bis zum 23.09.2026 endete hier die ganze
            # Rechnung, und das Fenster sagte nichts (``QuestionDeclined``).
            raise QuestionDeclined
        return request.answer

    # --- worker replies ---------------------------------------------------------

    def _outdated(self, finished: _EvaluationWorker | None) -> bool:
        """Ob diese Meldung von einem Lauf kommt, den ein neuerer ersetzt hat.

        ``None`` heißt „kein Absender bekannt" und gilt als aktuell: Tests und
        die Kommandozeile rufen die Slots direkt, und ein Aufruf ohne Arbeiter
        ist keine Nachzüglermeldung, sondern der Normalfall dort.
        """
        return finished is not None and finished is not self._worker

    def _stale(self, finished: _EvaluationWorker | None) -> bool:
        """Ob das **Ergebnis** dieses Laufs nicht mehr gilt.

        Überholt ist er, wenn ein neuerer ihn ersetzt hat (:meth:`_outdated`)
        oder ein synchroner Lauf ihn eingeholt hat (``_superseded``). Nur die
        Meldung wird verworfen; aufräumen — Leine, ``busyChanged``, das Feld —
        muss ``_on_thread_done`` ihn trotzdem, sonst bliebe die Anzeige stehen.
        """
        return self._outdated(finished) or (finished is not None and finished is self._superseded)

    def _on_picture(self, picture: Any, finished: _EvaluationWorker | None = None) -> None:
        """Das Modell steht im Bild, die Erkennung läuft weiter (KUNDE-14).

        Das Bild wird ``last_result``, damit Ansicht, Baum, Auswahl und Bericht
        dasselbe zeigen; ``result_current`` bleibt falsch — was ein fertiges
        Ergebnis verlangt (Karten, Passungen, Abschlüsse, Antworten im
        Stapel), wartet weiter auf ``_on_finished``.
        """
        if self._stale(finished) or self.cancel_signal.is_cancelled:
            return
        self.last_result = picture
        self.picture = picture
        self.result_generation += 1
        self.result_current = False
        self.pictureChanged.emit(picture)
        # Ein Bild gibt es nur von einem Stand, der nicht anhielt.
        self._settle_import(picture)

    def _on_finished(self, result: Any, finished: _EvaluationWorker | None = None) -> None:
        if self._stale(finished):
            # §15.3: stehen bleibt der letzte **gültige** Stand. Das Ergebnis
            # eines überholten Laufs gehört zu einem Dokument, das es nicht
            # mehr gibt — es einzublenden hieß, die leere Szene des neuen
            # Projekts über das Modell zu legen, das gerade geladen wird.
            return
        if not self._rerun_pending and self._settle_import(result):
            # Die Datei enthielt kein Modell; der Stand ohne sie wird gerade
            # gerechnet und kommt als nächstes Ergebnis.
            return
        self.picture = None
        self.last_result = result
        # Die grobe Kopie gehört der Szene, aus der sie entstand. Ohne dieses
        # Wegräumen hielte sie die **vorige** Szene am Leben — bei einem Netz
        # dieser Größe genau das, was die Stufe einsparen soll. Eine
        # Vorbereitung, die noch für die vorige rechnet, rechnet für niemanden.
        self._coarse_scene = None
        self._stop_coarse_preparation()
        self._bind_filament_profiles()
        self.result_generation += 1
        self.result_current = not self._rerun_pending
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
        # Das Ergebnis steht: Keine Zustimmung wartet mehr auf ihre Erkennung.
        self._recognition_answers.clear()
        if answered or matched:
            self._dirty = True
            self.projectChanged.emit()
        self.sceneChanged.emit(result)
        # **Nur ein aktuelles Ergebnis schließt ab.** Ist schon ein Nachlauf
        # eingereiht, gehört dieses Ergebnis zum Stand davor — dem, auf dem
        # die Hälften eines Gegenstücks noch fehlen. Es verbrauchte bis zum
        # 22.09.2026 den wartenden Abschluss (``attach_fit`` fand nichts und
        # meldete „nicht nachgetragen"), und der Nachlauf mit den echten
        # Hälften hatte keinen mehr.
        if self.result_current:
            self._run_finishers(result)

    def _on_failed(self, error: Any, finished: _EvaluationWorker | None = None) -> None:
        if self._stale(finished):
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
            self._backend_probed = False
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

    def _on_agent_proposal(self, preview: Any, finished: _AgentWorker) -> None:
        """Nur der aktuelle Agentenzug darf seinen Vorschlag zeigen."""
        if finished is not self._agent:
            return
        self._on_proposal(preview)

    def _on_agent_failed(self, error: Any, finished: _AgentWorker) -> None:
        """Nur der aktuelle Agentenzug darf einen Fehler melden."""
        if finished is not self._agent:
            return
        self._on_failed(error)

    def _on_agent_done(self, finished: _AgentWorker | None = None) -> None:
        if finished is not None and finished is not self._agent:
            self._leash.hold_until_done(finished)
            return
        # Nicht einfach loslassen — siehe ``_leash``.
        worker, self._agent = self._agent, None
        self._leash.hold_until_done(worker)
        # Erst nachdem das alte Feld leer und sein Wrapper gesichert ist: Ein
        # direkter Empfänger darf auf BusyFalse sofort den nächsten Zug
        # starten, ohne dass dieser Slot ihn danach wieder austrägt.
        self.agentBusyChanged.emit(False)

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
        self.busyChanged.emit(self.busy)

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
        self.release_recovery()

    def wait_for_idle(self, timeout_ms: int = 10_000) -> bool:
        """Blockiert bis zum Leerlauf und meldet, ob er rechtzeitig eintrat.

        ``True`` heißt, dass kein Lauf mehr übrig ist — auch nicht der, den
        eine Entprellung eingereiht hat. ``False`` heißt ausschließlich, dass
        die Frist mit einem noch aktiven Arbeiter endete. Bestehende Aufrufer,
        die nur warten wollen, dürfen den Rückgabewert weiter übergehen;
        synchrone Grenzen wie die Fernsteuerung können einen Timeout damit
        nicht mehr als fertiges Ergebnis ausgeben.

        Ereignisse werden verarbeitet, weil die Arbeiter ihre Ergebnisse über
        Signale zurückgeben und sonst nie ankämen. Eingaben aber nicht: sonst
        startet ein Menüklick mitten in diesem Warten die nächste Aktion, und
        die trifft auf einen Zustand, den gerade jemand anders umbaut.
        """
        deadline = time.monotonic() + timeout_ms / 1000.0
        while True:
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
            # Und der Einleseplan: Seit er im Arbeiter läuft (§2.8), kehrte
            # ``wait_for_idle`` zurück, bevor überhaupt eine Operation auf
            # dem Stapel lag — die Auswertung, auf die es wartet, war noch
            # gar nicht angefordert. Wer danach die Szene fragte, bekam eine
            # leere. Gefunden von 3d-druck-d4 am 03.09.2026.
            worker = (
                self._plan
                or self._worker
                or self._agent
                or self._split
                or self._revision
                or next(iter(self._previews), None)
                or next(iter(self._placements), None)
                or self._autosaving
            )
            if worker is None:
                return True
            remaining_ms = int((deadline - time.monotonic()) * 1000)
            if remaining_ms <= 0:
                return False
            worker.wait(min(50, remaining_ms))
            application = QCoreApplication.instance()
            if application is not None:
                # Ohne `undisturbed` räumt der Speicherbereiniger hier Fenster
                # ab, während Qt ihnen gerade Ereignisse zustellt — sechs von
                # acht Läufen starben daran mit Heap Corruption. Die Messung
                # steht am Kontextmanager.
                with undisturbed():
                    application.processEvents(QEventLoop.ProcessEventsFlag.ExcludeUserInputEvents)
