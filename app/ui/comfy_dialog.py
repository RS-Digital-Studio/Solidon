"""ComfyUI einrichten, aus der Anwendung heraus (Bauplan §27, §36).

**Der Schritt, der bisher in einem Satz stand.** Wer ComfyUI installiert hatte,
fand die Mesh-Erzeugung weiterhin ausgegraut: Es fehlen die Modelle, die der
Ablauf lädt. Die Auskunft dazu lautete „Einzurichten ist sie mit «python
tools/setup_comfyui.py»" — an einen Kunden gerichtet, auf dessen Rechner es
diese Datei nicht gibt, weil ``tools/`` im Paket nicht mitreist.

Der Dialog prüft die Fassung von ComfyUI und lädt auf Wunsch die Modelle — für
den Weg aus Bild und, eigenes Häkchen, das Bildmodell für den Weg aus Text.
Die Knoten bringt ComfyUI selbst mit. Abgebrochen wird auch mitten im
Download; was schon da ist, bleibt, und ein neuer Lauf setzt fort.
"""

from __future__ import annotations

import threading
import time
from contextlib import suppress
from dataclasses import dataclass
from pathlib import Path
from queue import Empty, Queue

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QShowEvent
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QProgressBar,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.core.backends import comfy_setup, machine, mesh, needs
from app.core.errors import InternalError
from app.core.log import get_logger
from app.i18n import format_decimal, tr
from app.ui.dialogs import show_error
from app.ui.leash import WAIT_TIMEOUT_MS, Worker, WorkerLeash
from app.ui.style import (
    NORMAL,
    WIDE,
    ContentHeight,
    DialogScrollArea,
    WrappedNote,
    make_primary,
    set_role,
)

_log = get_logger(__name__)

#: Wie oft die Laufzeit des laufenden Schritts nachgezogen wird. Einer davon
#: lädt mehrere Gigabyte — ohne die Zeit daneben ist ein unbestimmter Balken von einem
#: Hänger nicht zu unterscheiden.
TICK_MS = 1000

#: Nach einer Texteingabe kurz warten, damit ein Pfad nicht für jedes Zeichen
#: erneut auf einem Netzlaufwerk geprüft wird.
FOLDER_PROBE_DELAY_MS = 300

#: Nach der Frist erklärt der Dialog den wartenden Dateiblick.
FOLDER_PROBE_SLOW_MS = 5_000

#: Ein blockiertes Netzlaufwerk darf auch über geschlossene Dialoge hinweg
#: keine Folge neuer Dateisystem-Fäden entstehen lassen. Ein zweiter Platz
#: lässt den Nutzer währenddessen einen anderen Ordner prüfen.
FOLDER_PROBE_RETRY_MS = 500
MAX_CONCURRENT_FOLDER_PROBES = 2
_FOLDER_PROBE_SLOTS = threading.BoundedSemaphore(MAX_CONCURRENT_FOLDER_PROBES)


class _Worker(Worker):
    """Die Einrichtung: Versionsprüfung und Downloads von mehreren Gigabyte."""

    done = Signal(object)
    failed = Signal(str)
    step = Signal(str)

    def __init__(self, comfyui: str, weights: bool, image_model: bool) -> None:
        super().__init__()
        self._comfyui = comfyui
        self._weights = weights
        self._image_model = image_model
        self._stop = False

    def cancel(self) -> None:
        self._stop = True

    def work(self) -> None:
        try:
            result = comfy_setup.setup(
                self._comfyui or None,
                weights=self._weights,
                image_model=self._image_model,
                progress=lambda entry: self.step.emit(str(entry)),
                cancelled=lambda: self._stop,
            )
        except comfy_setup.SetupFailed as problem:
            self.failed.emit(str(problem))
            return
        self.done.emit(result)


@dataclass(frozen=True, slots=True)
class _FolderProbeResult:
    """Das Ergebnis eines Dateisystemblicks, zurückgereicht an den UI-Faden."""

    generation: int
    entered: str
    found: str | None = None
    weights: bool = False
    image_model: bool = False
    reason: str = ""
    crashed: bool = False
    legacy: tuple[str, ...] = ()
    """Die Ordner der alten TripoSG-Einrichtung, relativ zu ComfyUI."""
    legacy_gigabytes: float = 0.0
    free_gigabytes: float | None = None
    """Was auf dem Laufwerk von ``models`` frei ist — ``None``, wenn es schweigt."""


def _probe_folder(generation: int, entered: str, results: Queue[_FolderProbeResult]) -> None:
    """ComfyUI und Modellbestände prüfen, ohne den Dialog oder Prozess festzuhalten."""
    try:
        found = comfy_setup.find_comfyui(entered or None)
        weights = comfy_setup.weights_present(found)
        image_model = comfy_setup.image_model_present(found)
        leftovers = comfy_setup.legacy_leftovers(found)
        legacy_size = comfy_setup.legacy_gigabytes(leftovers)
        try:
            free: float | None = comfy_setup.free_gigabytes(found / "models")
        except OSError:
            free = None
        # Den Rechner hier erheben (``nvidia-smi`` ist ein Prozess), nicht im
        # Hauptthread (RM-564).
        machine.this_machine()
    except comfy_setup.SetupFailed as problem:
        results.put(_FolderProbeResult(generation, entered, reason=str(problem)))
    except Exception as problem:
        _log.exception("comfy folder probe crashed")
        results.put(
            _FolderProbeResult(
                generation,
                entered,
                reason=f"{type(problem).__name__}: {problem}",
                crashed=True,
            )
        )
    else:
        results.put(
            _FolderProbeResult(
                generation,
                entered,
                found=str(found),
                weights=weights,
                image_model=image_model,
                legacy=tuple(path.relative_to(found).as_posix() for path in leftovers),
                legacy_gigabytes=legacy_size,
                free_gigabytes=free,
            )
        )


def _probe_folder_with_slot(
    generation: int, entered: str, results: Queue[_FolderProbeResult]
) -> None:
    """Den belegten systemweiten Dateiblick freigeben, sobald er zurückkehrt."""
    try:
        _probe_folder(generation, entered, results)
    finally:
        _FOLDER_PROBE_SLOTS.release()


class ComfySetupDialog(QDialog):
    """Fassung prüfen und Modelle laden — in einem Lauf."""

    def __init__(self, parent: QWidget | None = None, *, image_model: bool | None = None) -> None:
        """``image_model`` belegt das Häkchen fürs Bildmodell vor.

        ``None`` heißt: an, wenn keines da ist. Wer aus dem Erzeugungsdialog
        kommt, weil ihm für den Weg aus Text genau dieses Modell fehlt, will
        es; wer nur den Bildweg einrichtet, sieht das Häkchen und entscheidet.
        """
        super().__init__(parent)
        self.setWindowTitle(tr("ComfyUI einrichten"))
        self.setMinimumWidth(560)
        self._worker: _Worker | None = None
        self._probe_generation = 0
        self._probe_target = ""
        self._probe_pending = False
        self._probe_requested = False
        self._probe_succeeded = False
        self._probe_timed_out_generation: int | None = None
        self._probe_running_generations: set[int] = set()
        self._probe_results: Queue[_FolderProbeResult] = Queue()
        self._weights_present = False
        self._image_model_present = False
        self._leash = WorkerLeash(self)
        self._height = ContentHeight()
        self._step = ""
        """Der Schritt, der gerade läuft — für die Zeile mit der Laufzeit."""
        self._started_at = 0.0
        self._tick = QTimer(self)
        self._tick.setInterval(TICK_MS)
        self._tick.timeout.connect(self._show_elapsed)

        intro = QLabel(
            tr(
                "ComfyUI erzeugt das 3D-Modell. Die Bausteine dafür bringt ComfyUI ab "
                "Version {version} selbst mit, die Modelle lädt Solidon hier in dessen "
                "Ordner. ComfyUI selbst wird nicht verändert. Die Modelle stehen unter der "
                "MIT-Lizenz (TRELLIS.2, BiRefNet), unter Metas DINOv3-Lizenz (Bildkodierer) "
                "und unter Apache-2.0 (FLUX.2 [klein])."
            ).format(version=mesh.MINIMUM_COMFYUI_TEXT),
            self,
        )
        intro.setWordWrap(True)

        self.folder = QLineEdit(self)
        folder_hint = tr("Ordner, in dem „custom_nodes“ steht")
        self.folder.setPlaceholderText(folder_hint)
        self.folder.setAccessibleName(folder_hint)
        self.choose = QPushButton(tr("Ordner wählen …"), self)
        self.choose.clicked.connect(self._choose_folder)

        self._weights_wanted = True
        self._image_model_wanted = True if image_model is None else image_model
        self._weights_label = tr("Modell für den Weg aus Bild laden — rund {size} GB").format(
            size=format_decimal(comfy_setup.WEIGHT_GIGABYTES, 1)
        )
        self._image_model_label = tr(
            "Bildmodell für den Weg aus Text laden — rund {size} GB"
        ).format(size=format_decimal(comfy_setup.IMAGE_MODEL_GIGABYTES, 1))
        self.weights = QCheckBox(self._weights_label, self)
        # **Das Bildmodell als eigenes Häkchen** (21.09.2026). Es braucht nur
        # der Weg aus Text, und es sind acht Gigabyte — deshalb nicht still
        # mit den Gewichten, sondern benannt, mit Größe, abwählbar. Robert
        # tippte einen Satz und las, dass ein Bild verlangt wird: Bis dahin
        # holte Solidon dieses Modell gar nicht.
        self.image_model = QCheckBox(self._image_model_label, self)
        # **Platz und Dauer, bevor geladen wird** (RM-564): Ein Kunde mit
        # MacBook las erst beim Laden, dass es Dutzende Gigabyte werden. Die
        # Zeile rechnet mit den gewählten Häkchen und dem freien Platz.
        self._free_gigabytes: float | None = None
        self.needs = WrappedNote(self)
        self.needs.grown.connect(self._fit_soon)
        self.needs.setTextFormat(Qt.TextFormat.PlainText)
        self.weights.toggled.connect(self._show_needs)
        self.image_model.toggled.connect(self._show_needs)
        self._set_model_options(False, False)

        # **Was die Einrichtung entfernt, steht vorher da** (Entscheidung Robert,
        # 07.10.2026): Solidons alte TripoSG-Einrichtung, nur am eigenen
        # Zeichen erkannt, mit Ordnern und Größe — sichtbar nur, wo es sie gibt.
        self.legacy = WrappedNote(self)
        self.legacy.grown.connect(self._fit_soon)
        self.legacy.setTextFormat(Qt.TextFormat.PlainText)
        self.legacy.setVisible(False)

        self.state = WrappedNote(self)
        self.state.grown.connect(self._fit_soon)
        self.state.setTextFormat(Qt.TextFormat.PlainText)
        self._not_found_note = tr(
            "ComfyUI ist an den üblichen Stellen nicht gefunden worden. "
            "Gesucht wird der Ordner, in dem „custom_nodes“ und „main.py“ "
            "liegen — bei der tragbaren Version steckt er in "
            "„ComfyUI_windows_portable“."
        )
        self.progress = QProgressBar(self)
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setVisible(False)

        self.start_button = QPushButton(tr("Einrichten"), self)
        self.start_button.clicked.connect(self._start)
        # **Der Akzent lag auf „Ordner wählen …", und niemand hatte ihn dorthin
        # gesetzt.** ``QDialog`` macht beim ersten ``show()`` den ersten Knopf
        # mit ``autoDefault`` zum Default; das ist hier die Zeile über der
        # Handlung. Gemessen am angezeigten Fenster: „Ordner wählen …" trug den
        # Akzent, „Einrichten" nichts — der Hinweis zeigte auf die Vorbereitung
        # statt auf die Sache (Befund D3).
        make_primary(self.start_button)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        buttons.rejected.connect(self.reject)

        row = QHBoxLayout()
        row.setSpacing(NORMAL)
        row.addWidget(self.folder, stretch=1)
        row.addWidget(self.choose)

        content = QWidget(self)
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)
        content_layout.setSpacing(NORMAL)
        content_layout.addWidget(intro)
        content_layout.addLayout(row)
        content_layout.addWidget(self.weights)
        content_layout.addWidget(self.image_model)
        content_layout.addWidget(self.needs)
        content_layout.addWidget(self.legacy)
        # **Zustand und Balken im Rollbereich** (RM-339): Eine gescheiterte
        # Einrichtung meldet jede Ausgabezeile des Prozesses. Außerhalb ließ
        # sie das Fenster über den Bildschirm wachsen, und *Einrichten* und
        # *Schließen* lagen unerreichbar darunter.
        content_layout.addWidget(self.progress)
        content_layout.addWidget(self.state)
        scroll = DialogScrollArea(self)
        scroll.setWidget(content)
        self.content_scroll = scroll
        scroll.contentSizeChanged.connect(self._fit_soon)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(WIDE, WIDE, WIDE, WIDE)
        layout.setSpacing(NORMAL)
        layout.addWidget(scroll, 1)
        layout.addWidget(self.start_button, alignment=Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(buttons)
        self.folder.editingFinished.connect(self._refresh_folder_state)
        self.folder.textEdited.connect(self._folder_edited)

        self._probe_timer = QTimer(self)
        self._probe_timer.setSingleShot(True)
        self._probe_timer.timeout.connect(self._start_folder_probe)
        self._probe_slow_timer = QTimer(self)
        self._probe_slow_timer.setSingleShot(True)
        self._probe_slow_timer.timeout.connect(self._folder_probe_timed_out)
        self._probe_poll = QTimer(self)
        self._probe_poll.setInterval(100)
        self._probe_poll.timeout.connect(self._collect_folder_probe)

        # Suche und Dateiblicke laufen entkoppelt. Ein abgemeldetes Netzlaufwerk
        # darf weder den Dialog noch das Beenden festhalten.
        self._queue_folder_probe("", immediate=True)

    def showEvent(self, event: QShowEvent) -> None:  # noqa: N802 — Qt gibt den Namen vor
        super().showEvent(event)
        self._fit_initial_soon()

    def _fit_soon(self) -> None:
        QTimer.singleShot(0, self, self._fit_content)

    def _fit_initial_soon(self) -> None:
        QTimer.singleShot(0, self, self._fit_initial_content)

    def _fit_content(self) -> None:
        self._height.fit(self, self.content_scroll, intent="passive")

    def _fit_initial_content(self) -> None:
        self._height.fit(self, self.content_scroll, grow_width=True, intent="initial")

    def _choose_folder(self) -> None:
        chosen = QFileDialog.getExistingDirectory(
            self, tr("ComfyUI wählen"), self.folder.text() or str(Path.home())
        )
        if chosen:
            self.folder.setText(chosen)
            self._refresh_folder_state()

    def _set_model_options(self, weights_there: bool, image_model_there: bool) -> None:
        """Die Häkchen an den im Arbeiter ermittelten Beständen ausrichten."""
        self._weights_present = weights_there
        self._image_model_present = image_model_there
        self.weights.setText(tr("Modell ist schon da") if weights_there else self._weights_label)
        self.weights.setEnabled(not weights_there and not self._probe_pending)
        self.weights.setChecked(not weights_there and self._weights_wanted)
        self.image_model.setText(
            tr("Bildmodell ist schon da") if image_model_there else self._image_model_label
        )
        self.image_model.setEnabled(not image_model_there and not self._probe_pending)
        self.image_model.setChecked(not image_model_there and self._image_model_wanted)
        self._show_needs()

    def _show_needs(self, *_args: object) -> None:
        """Was die gewählten Modelle brauchen, ob dieser Rechner es hat, und wie lange
        ein Auftrag dauert — vor *Einrichten* (RM-564, ``needs.generator_needs``).

        Erst nach der Ordnerprüfung: Sie hat im Faden Platz und Rechner erhoben,
        hier wird nur gelesen.
        """
        if not self._probe_succeeded:
            self.needs.setText("")
            return
        said, short = needs.generator_needs(
            self.weights.isEnabled() and self.weights.isChecked(),
            self.image_model.isEnabled() and self.image_model.isChecked(),
            self._free_gigabytes,
        )
        set_role(self.needs, "warning" if short else "info", said)

    def _set_start_enabled(self, enabled: bool, reason: str | None = None) -> None:
        """Eine laufende Ordnerprüfung auf allen Kanälen am Knopf erklären."""
        reason = "" if enabled else reason or tr("ComfyUI-Ordner wird geprüft …")
        self.start_button.setEnabled(enabled)
        self.start_button.setToolTip(reason)
        self.start_button.setAccessibleDescription(reason)

    def _refresh_folder_state(self) -> None:
        """Eine gewählte oder eingegebene Adresse unverzüglich nachsehen lassen."""
        if self._setup_is_running():
            return
        entered = self.folder.text().strip()
        if entered == self._probe_target:
            if self._probe_pending:
                self._probe_timer.start(0)
                return
            if (
                self._probe_succeeded
                or self._probe_requested
                or self._probe_generation in self._probe_running_generations
            ):
                return
        self._queue_folder_probe(entered, immediate=True)

    def _folder_edited(self, _text: str) -> None:
        """Eine Eingabe prüfen, sobald der Nutzer kurz innehält."""
        if self._setup_is_running():
            return
        self._queue_folder_probe(self.folder.text().strip())

    def _setup_is_running(self) -> bool:
        return self._worker is not None and self._worker.isRunning()

    def _remember_model_choices(self) -> None:
        if self.weights.isEnabled():
            self._weights_wanted = self.weights.isChecked()
        if self.image_model.isEnabled():
            self._image_model_wanted = self.image_model.isChecked()

    def _queue_folder_probe(self, entered: str, *, immediate: bool = False) -> None:
        """Statusabfragen entprellen und währenddessen falsche Häkchen sperren."""
        if self._setup_is_running():
            return
        if entered == self._probe_target:
            if self._probe_pending:
                if immediate:
                    self._probe_timer.start(0)
                return
            if (
                self._probe_succeeded
                or self._probe_requested
                or self._probe_generation in self._probe_running_generations
            ):
                return
        self._remember_model_choices()
        if entered != self._probe_target:
            self._weights_present = False
            self._image_model_present = False
        self._probe_succeeded = False
        self._probe_generation += 1
        self._probe_timed_out_generation = None
        self._probe_target = entered
        self._probe_pending = True
        self._probe_requested = True
        self._show_legacy((), 0.0)
        self._probe_timer.stop()
        self._probe_timer.start(0 if immediate else FOLDER_PROBE_DELAY_MS)
        self._probe_slow_timer.start(FOLDER_PROBE_SLOW_MS)
        self.progress.setVisible(True)
        self._set_start_enabled(False)
        self._set_model_options(self._weights_present, self._image_model_present)
        set_role(self.state, "info", tr("ComfyUI-Ordner wird geprüft …"))

    def _start_folder_probe(self) -> None:
        """Den jüngsten Pfad in einem entkoppelten Daemon-Faden prüfen."""
        if not self._probe_requested or self._setup_is_running():
            return
        # Hängende Netzlaufwerke dürfen nur zwei Dateiblicke systemweit
        # festhalten. Ein freier zweiter Platz lässt einen erreichbaren
        # Ersatzordner prüfen; weitere Wünsche werden zusammengefasst.
        if not _FOLDER_PROBE_SLOTS.acquire(blocking=False):
            self._probe_timer.start(FOLDER_PROBE_RETRY_MS)
            return
        generation = self._probe_generation
        entered = self._probe_target
        checker = threading.Thread(
            target=_probe_folder_with_slot,
            args=(generation, entered, self._probe_results),
            name="comfy-folder-probe",
            daemon=True,
        )
        self._probe_requested = False
        self._probe_running_generations.add(generation)
        try:
            checker.start()
        except RuntimeError as problem:
            self._probe_running_generations.discard(generation)
            _FOLDER_PROBE_SLOTS.release()
            self._folder_probe_crashed(generation, entered, str(problem))
            return
        self._probe_poll.start()

    def _collect_folder_probe(self) -> None:
        """Nur die Antwort zur aktuellen Eingabe darf den sichtbaren Zustand ändern."""
        while True:
            try:
                result = self._probe_results.get_nowait()
            except Empty:
                if self._probe_requested:
                    if not self._probe_timer.isActive():
                        self._probe_timer.start(FOLDER_PROBE_RETRY_MS)
                elif not self._probe_running_generations:
                    self._probe_poll.stop()
                return
            self._probe_running_generations.discard(result.generation)
            if (
                result.generation != self._probe_generation
                or result.entered != self._probe_target
                or self.folder.text().strip() != result.entered
            ):
                continue
            if result.found is not None:
                self._folder_probe_ready(
                    result.generation,
                    result.entered,
                    result.found,
                    result.weights,
                    result.image_model,
                    legacy=result.legacy,
                    legacy_gigabytes=result.legacy_gigabytes,
                    free_gigabytes=result.free_gigabytes,
                )
            elif result.crashed:
                self._folder_probe_crashed(result.generation, result.entered, result.reason)
            else:
                self._folder_probe_failed(result.generation, result.entered, result.reason)

    def _folder_probe_ready(
        self,
        generation: int,
        entered: str,
        found: str,
        weights: bool,
        image_model: bool,
        *,
        legacy: tuple[str, ...] = (),
        legacy_gigabytes: float = 0.0,
        free_gigabytes: float | None = None,
    ) -> None:
        """Nur die Antwort zum weiterhin sichtbaren Ordner darf die Häkchen setzen."""
        if (
            generation != self._probe_generation
            or entered != self._probe_target
            or self.folder.text().strip() != entered
        ):
            return
        self._probe_slow_timer.stop()
        if not entered or entered != found:
            self.folder.setText(found)
        self._probe_target = found
        self._probe_pending = False
        self._probe_requested = False
        self._probe_succeeded = True
        self._probe_timed_out_generation = None
        self.progress.setVisible(False)
        self._free_gigabytes = free_gigabytes
        self._set_model_options(weights, image_model)
        self._show_legacy(legacy, legacy_gigabytes)
        self._set_start_enabled(True)
        set_role(self.state, "info", "")

    def _show_legacy(self, folders: tuple[str, ...], gigabytes: float) -> None:
        """Die Ordner der alten Einrichtung, die *Einrichten* entfernt — oder nichts."""
        if not folders:
            self.legacy.setVisible(False)
            self.legacy.setText("")
            return
        # Die genannten Ordner gehen ganz (``comfy_setup.remove_legacy``); der
        # Satz verspricht deshalb nur, was stimmt: Andere Ordner bleiben.
        text = tr(
            "Einrichten entfernt dabei Solidons alte TripoSG-Einrichtung, die kein Ablauf "
            "mehr liest: {folders} (rund {size} GB). Andere Ordner bleiben unberührt."
        ).format(folders=", ".join(folders), size=format_decimal(gigabytes, 1))
        set_role(self.legacy, "info", text)
        self.legacy.setVisible(True)

    def _folder_probe_failed(self, generation: int, entered: str, reason: str) -> None:
        """Einen nicht erreichbaren Ordner mit einem gangbaren nächsten Schritt melden."""
        if (
            generation != self._probe_generation
            or entered != self._probe_target
            or self.folder.text().strip() != entered
        ):
            return
        self._probe_slow_timer.stop()
        self._probe_pending = False
        self._probe_requested = False
        self._probe_succeeded = False
        self.progress.setVisible(False)
        self._set_model_options(False, False)
        if generation == self._probe_timed_out_generation:
            note = tr(
                "Der ComfyUI-Ordner ließ sich nach der Wartezeit nicht prüfen. "
                "Wählen Sie einen anderen erreichbaren Ordner oder versuchen Sie es erneut."
            )
            self._set_start_enabled(False, note)
            set_role(self.state, "warning", note)
            return
        self._set_start_enabled(True)
        set_role(
            self.state,
            "info" if not entered else "warning",
            self._not_found_note if not entered else reason,
        )

    def _folder_probe_crashed(self, generation: int, entered: str, detail: str) -> None:
        """Einen unerwarteten Prüffehler protokollieren und einen erreichbaren Ordner anbieten."""
        if (
            generation != self._probe_generation
            or entered != self._probe_target
            or self.folder.text().strip() != entered
        ):
            return
        self._probe_slow_timer.stop()
        self._probe_pending = False
        self._probe_requested = False
        self._probe_succeeded = False
        self.progress.setVisible(False)
        self._set_model_options(False, False)
        if generation == self._probe_timed_out_generation:
            note = tr(
                "Der ComfyUI-Ordner ließ sich nach der Wartezeit nicht prüfen. "
                "Wählen Sie einen anderen erreichbaren Ordner oder versuchen Sie es erneut."
            )
            self._set_start_enabled(False, note)
            set_role(self.state, "warning", note)
            _log.warning("comfy folder probe crashed after timeout: %s", detail)
            return
        self._set_start_enabled(True)
        _log.warning("comfy folder probe crashed: %s", detail)
        set_role(
            self.state,
            "warning",
            tr(
                "Der Ordner ließ sich nicht prüfen. Wählen Sie einen erreichbaren Ordner "
                "oder versuchen Sie es erneut."
            ),
        )

    def _folder_probe_timed_out(self) -> None:
        """Einen langsamen Dateiblick erklären, ohne ungeprüftes Setup zu starten."""
        if not self._probe_pending:
            return
        self._probe_slow_timer.stop()
        self._probe_timed_out_generation = self._probe_generation
        self.progress.setVisible(False)
        reason = tr(
            "ComfyUI-Ordner wird noch geprüft. Wählen Sie einen anderen erreichbaren "
            "Ordner oder warten Sie auf die Antwort."
        )
        self._set_start_enabled(False, reason)
        set_role(
            self.state,
            "warning",
            reason,
        )

    # --- laufen -----------------------------------------------------------------

    def _start(self) -> None:
        """Einrichten — oder, während es läuft, abbrechen."""
        worker = self._worker
        if worker is not None and worker.isRunning():
            worker.cancel()
            set_role(
                self.state,
                "info",
                tr("Wird abgebrochen — der laufende Schritt läuft aus."),
            )
            return
        if self._probe_pending or self._probe_timed_out_generation == self._probe_generation:
            return
        self._remember_model_choices()
        weights_wanted = self.weights.isChecked()
        image_model_wanted = self.image_model.isChecked() and self.image_model.isEnabled()
        self._probe_timer.stop()
        self._probe_slow_timer.stop()
        self._probe_requested = False
        self._probe_generation += 1
        self.progress.setVisible(True)
        self.start_button.setText(tr("Abbrechen"))
        self.folder.setEnabled(False)
        self.choose.setEnabled(False)
        self.weights.setEnabled(False)
        self.image_model.setEnabled(False)
        self._step = str(tr("Wird eingerichtet …"))
        self._started_at = time.monotonic()
        self._show_elapsed()
        self._tick.start()

        worker = _Worker(
            self.folder.text().strip(),
            weights_wanted,
            image_model_wanted,
        )
        worker.step.connect(self._note_step)
        worker.done.connect(self._finished)
        worker.failed.connect(self._refused)
        # **Und das Unerwartete.** Ohne diese Zeile stand der Dialog nach einem
        # ``PermissionError`` — ComfyUI unter ``Program Files`` — für immer auf
        # „Wird eingerichtet …", mit laufendem Balken.
        worker.crashed.connect(self._crashed)
        worker.finished.connect(lambda done=worker: self._worker_done(done))
        self._worker = worker
        self._leash.start(worker)

    def wait_for_setup(self, milliseconds: int = 30_000) -> bool:
        """Auf den Lauf warten. Beim Schließen und in Tests."""
        worker = self._worker
        return worker.wait(milliseconds) if worker is not None else True

    def release(self, timeout_ms: int = WAIT_TIMEOUT_MS) -> None:
        """Alles loslassen, was dieses Fenster außerhalb von Qt hält.

        Warum der Name, warum die eigene Frist: :mod:`app.ui.leash`.
        """
        self._stop_folder_probes()
        self.wait_for_setup()
        self._leash.wait_all(timeout_ms)

    def _stop_folder_probes(self) -> None:
        """Timer und Antworten nach dem Schließen wirkungslos machen."""
        self._probe_timer.stop()
        self._probe_slow_timer.stop()
        self._probe_poll.stop()
        self._probe_generation += 1
        self._probe_pending = False
        self._probe_requested = False

    def _note_step(self, step: str) -> None:
        """Welcher Schritt gerade läuft. Vier bis fünf, und einer dauert lange.

        Die Zeit beginnt je Schritt neu: „Modell für den Weg aus Bild laden — rund 8,0 GB (240 s)"
        sagt mehr als eine Gesamtzeit, denn nur dieser eine Schritt dauert.
        """
        self._step = step
        self._started_at = time.monotonic()
        self._show_elapsed()

    def _show_elapsed(self) -> None:
        """Der Schritt und wie lange er schon läuft.

        Die Rolle steht **hier** und nicht beim Start: Der Zeitgeber schreibt
        die Zeile jede Sekunde neu, und ein einmal gesetztes Zeichen wäre beim
        ersten Takt wieder weg. Wer einen Text laufend erneuert, erneuert seine
        Bedeutung mit.
        """
        seconds = time.monotonic() - self._started_at
        set_role(self.state, "info", f"{self._step} ({seconds:.0f} s)")

    def _finished(self, result: object) -> None:
        assert isinstance(result, comfy_setup.Result)
        self._weights_present = result.weights
        self._image_model_present = result.image_model
        self._idle()
        # **Was stehen blieb, sagt der Dialog samt Ausweg** (Review 1 P3, G-6).
        # Meist hält ein laufendes ComfyUI eine Datei offen; dann lädt es den
        # TripoSG-Quelltext weiter, und „Eingerichtet“ wäre nur halb wahr.
        stayed = (
            tr(
                "Solidons alte TripoSG-Einrichtung ließ sich nicht ganz entfernen: {folders}. "
                "ComfyUI beenden und Einrichten erneut starten."
            ).format(folders=", ".join(result.legacy_left))
            if result.legacy_left
            else ""
        )
        if not result.done:
            set_role(self.state, "warning", " ".join(filter(None, (str(result.reason), stayed))))
            return
        self._show_legacy((), 0.0)
        if stayed:
            set_role(self.state, "warning", f"{tr('Die Modelle sind eingerichtet.')} {stayed}")
            return
        # Der Neustart ist eine Vorsicht: Neue Modelldateien sieht ein laufendes
        # ComfyUI meist von selbst, eine entfernte alte Knotensammlung erst
        # nach dem Neustart.
        set_role(
            self.state,
            "ok",
            tr("Eingerichtet. ComfyUI einmal neu starten, dann geht „Modell erzeugen“."),
        )
        _log.info("comfyui set up in %s", result.comfyui)

    def _refused(self, reason: str) -> None:
        self._idle()
        set_role(self.state, "warning", reason)
        # Die Meldung beginnt mit dem Satz, der sagt, was hilft — dorthin
        # rollen, nicht ans Ende der Prozessausgabe (RM-339).
        QTimer.singleShot(0, self, lambda: self.content_scroll.ensureWidgetVisible(self.state))

    def _crashed(self, detail: str) -> None:
        """Womit niemand gerechnet hat — und der Weg aus dem Wartezustand."""
        self._idle()
        _log.warning("comfy setup crashed: %s", detail)
        error = InternalError(detail=detail)
        set_role(self.state, "warning", f"{error.title!s} {detail}")
        show_error(error, self)

    def _idle(self) -> None:
        self._tick.stop()
        self.progress.setVisible(False)
        self.start_button.setText(tr("Einrichten"))
        self._set_start_enabled(not self._probe_pending)
        self.folder.setEnabled(True)
        self.choose.setEnabled(True)
        self._set_model_options(self._weights_present, self._image_model_present)

    def _worker_done(self, worker: object) -> None:
        if self._worker is worker:
            self._worker = None
        self._leash.hold_until_done(worker)

    def reject(self) -> None:
        """Schließen bricht den Lauf ab — und wartet nicht auf ihn.

        Abgebrochen wird zwischen den Schritten und im Download je Block: ein
        halb kopierte Modelldatei wäre schlimmer als ein Vorgang, der
        ausläuft. Hier stand danach ``wait(2000)``, zwei Sekunden stehendes
        Fenster auf Esc hin, ohne Balken und ohne Zeile. Den Thread hält die
        Halteleine über den Dialog hinaus (:mod:`app.ui.leash`); seine
        Signale werden getrennt, damit eine späte Antwort keinen
        geschlossenen Dialog mehr anfasst.
        """
        self._stop_folder_probes()
        worker = self._worker
        if worker is not None and worker.isRunning():
            worker.cancel()
            for signal in (worker.step, worker.done, worker.failed, worker.crashed):
                with suppress(RuntimeError, TypeError):
                    signal.disconnect()
            self._idle()
        super().reject()
