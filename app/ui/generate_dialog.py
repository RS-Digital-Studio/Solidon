"""Weg 3 aus dem Fenster: beschreiben oder ein Bild fallen lassen, einen
Körper bekommen (§2.2, §27).

Der Dialog ist mit Absicht dünn. Alles, was er tut, lebt in
:mod:`app.core.generate`; was hier passiert, ist nach einem Satz zu fragen, zu
zeigen, ob überhaupt ein Generator läuft, und das Fenster bedienbar zu halten,
während eine Grafikkarte eine Minute lang nachdenkt.

Läuft nichts, sagt der Dialog das und bietet keinen Knopf zum Drücken —
ausgegraut, wie der Chat ohne Schlüssel (§27). Er versucht nicht, etwas zu
starten, und er versteckt den Eintrag auch nicht: eine Aktion, die verschwindet,
sieht aus wie ein Fehler; eine, die sich erklärt, nicht.
"""

from __future__ import annotations

import threading
from pathlib import Path
from typing import Final

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QProgressBar,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.backends import comfy_setup, mesh
from app.core.backends.mesh import ComfyBackend, GeneratedMesh, MeshBackend
from app.core.errors import CANCEL, AppError, OperationCancelled
from app.core.log import get_logger
from app.i18n import tr
from app.ui.dialogs import spoken_values
from app.ui.labels import UNEXPECTED_CRASH, volume
from app.ui.leash import WAIT_TIMEOUT_MS, Worker, WorkerLeash
from app.ui.panels import collapsible
from app.ui.style import make_primary

_log = get_logger(__name__)

#: Was sich als Ausgangsbild hineinziehen lässt. Die Endungen stehen für sich,
#: getrennt von der Beschriftung: der Dateidialog zeigt einen übersetzten Text,
#: das Erkennen einer abgelegten Datei darf davon nicht abhängen.
IMAGE_SUFFIXES: Final = (".png", ".jpg", ".jpeg", ".webp")


def image_filter() -> str:
    """Der Filter für den Dateidialog, in der Sprache des Nutzers (Regel 20).

    Als Funktion und nicht als Konstante: ``tr()`` löst sofort auf, und eine
    Konstante auf Modulebene stünde in der Sprache, die beim Import galt.
    """
    return f"{tr('Bilder')} ({' '.join('*' + suffix for suffix in IMAGE_SUFFIXES)})"


#: Obergrenze des Startwerts, den der Dialog anbietet. Derselbe Wert liefert
#: dasselbe Ergebnis, soweit das Modell auf der anderen Seite es zulässt
#: (§11.3).
MAX_SEED = 2**31 - 1

#: Wie lange das Schließen auf den Arbeiter wartet, bevor es loslässt.
WAIT_MILLISECONDS = 50


class _Worker(Worker):
    """Eine Erzeugung, abseits des Oberflächen-Threads.

    Ein Diffusionsmodell braucht Minuten; das in der Ereignisschleife zu tun
    fröre das Fenster ein — samt jeder Fortschrittszeile, die es zeigen
    soll (§31).

    **Und es muss abbrechbar sein** (§15.6). Der Rückruf, den die Schnittstelle
    dafür vorsieht (:meth:`~app.core.backends.mesh.MeshBackend.text_to_mesh`),
    wurde hier nicht gereicht: *Abbrechen* schloss den Dialog, wartete
    fünfzig Millisekunden und ließ los — der Arbeiter fragte ComfyUI weiter,
    bis zu einer Stunde (``mesh.STUCK_SECONDS``), und meldete sein Ergebnis an
    ein Fenster, das es nicht mehr gab. ``app.core.generate`` macht es seit je
    richtig vor; nur der Weg aus dem Fenster ging daran vorbei.
    """

    done = Signal(object)
    failed = Signal(object)
    step = Signal(float, str)

    def __init__(self, backend: MeshBackend, prompt: str, image: bytes | None, seed: int) -> None:
        super().__init__()
        self._backend = backend
        self._prompt = prompt
        self._image = image
        self._seed = seed
        # Ein ``Event`` und kein Wahrheitswert: Gesetzt wird im Qt-Hauptthread,
        # gelesen im Arbeitsthread.
        self._stop = threading.Event()

    def cancel(self) -> None:
        """Niemand wartet mehr auf diesen Wurf.

        Was aufhört, ist das **Warten** — der Auftrag steht in der
        Warteschlange des fremden Programms und gehört ihm; ihn dort zu
        unterbrechen träfe unter Umständen den Auftrag eines anderen
        (``backends/mesh.py``). Genau das Warten ist aber, was der Nutzer
        angeklickt hat.
        """
        self._stop.set()

    def cancelled(self) -> bool:
        """Der Rückruf, den das Backend regelmäßig fragt."""
        return self._stop.is_set()

    def work(self) -> None:
        try:
            if self._image is not None:
                result = self._backend.image_to_mesh(
                    self._image,
                    seed=self._seed,
                    progress=self._progress,
                    cancelled=self.cancelled,
                )
            else:
                result = self._backend.text_to_mesh(
                    self._prompt,
                    seed=self._seed,
                    progress=self._progress,
                    cancelled=self.cancelled,
                )
        except OperationCancelled:
            # **Ein Abbruch ist ein stiller Ausgang, kein Fehler** (§15.6).
            # ``OperationCancelled`` ist ausdrücklich **kein** ``AppError``
            # (``tests/test_errors.py``) — ungefangen liefe sie also in
            # ``Worker.run`` und käme beim Kunden als „Dabei ist etwas
            # schiefgegangen, womit hier niemand gerechnet hat" an, für etwas,
            # das er selbst ausgelöst hat. Gemeldet wird nichts: Der Dialog,
            # der abbricht, geht im selben Zug zu.
            _log.info("generation cancelled")
            return
        except AppError as problem:
            self.failed.emit(problem)
            return
        self.done.emit(result)

    def _progress(self, fraction: float, text: str) -> None:
        self.step.emit(fraction, text)


class _ReadinessWorker(Worker):
    """Fragt den Generator ab, ohne das Öffnen des Dialogs aufzuhalten.

    Ein lokales ComfyUI antwortet meist schnell. Eine eingetragene Adresse auf
    einem zweiten Rechner, ein Reverse-Proxy oder ein belegter Port kann aber
    mehrere Zeitlimits kosten. Das ist äußere Arbeit und gehört darum ebenso
    wenig in den Oberflächen-Thread wie die Erzeugung selbst (§2.8).
    """

    done = Signal(str, object, object)
    """``(ablauf, bereitschaft, auswahl)`` — die drei Auskünfte eines Rundgangs.

    **Zusammen und nicht getrennt.** Die Bereitschaft und die Modellwahl
    kommen aus denselben HTTP-Aufrufen: ``readiness`` fragt, *ob* eine Rolle
    besetzt ist, ``model_choices`` fragt, *womit*. Zwei Arbeiter dafür wären
    zwei Zeitlimits auf einer langsamen Leitung, und die Antworten könnten
    auseinanderlaufen.
    """

    def __init__(self, backend: MeshBackend, workflow: str) -> None:
        super().__init__()
        self._backend = backend
        self._workflow = workflow

    def work(self) -> None:
        self.done.emit(
            self._workflow,
            _look(self._backend, self._workflow),
            _choices(self._backend, self._workflow),
        )


def _look(backend: MeshBackend, workflow: str = "image_to_mesh") -> mesh.Readiness:
    """Wie weit dieser Generator ist — auch wenn er die Frage nicht kennt.

    ``readiness`` gehört zu ComfyUI; die Schnittstelle aus §27 kennt nur zwei
    Aufrufe und ``available``. Ein anderes Backend — der Testdoppel, ein
    späterer gehosteter Dienst — bekommt deshalb die Antwort, die es geben
    kann, und keine erfundene.

    **Gefragt wird für den Weg, der wirklich läuft.** Der Textweg spricht
    andere Knoten an und braucht ein Modell mehr: Text wird erst zu einem Bild,
    und dafür steht ein SDXL-Modell im Ablauf. Geprüft wurde bis hierhin immer
    der Bildweg, auch wenn der Textweg lief — wer kein Bildmodell hatte, las
    „Bereit" und erfuhr es beim Abschicken.
    """
    ask = getattr(backend, "readiness", None)
    if callable(ask):
        try:
            found = ask(workflow)
        except TypeError:
            # Ein Backend, das die Frage kennt, aber nicht nach dem Ablauf —
            # dann gilt seine Antwort für alles, was es kann.
            found = ask()
        assert isinstance(found, mesh.Readiness)
        return found
    return mesh.Readiness.READY if backend.available else mesh.Readiness.ABSENT


def _choices(backend: MeshBackend, workflow: str) -> dict[str, tuple[str, ...]]:
    """Was je Rolle zur Wahl steht — leer, wenn das Backend die Frage nicht kennt.

    Dieselbe Vorsicht wie bei :func:`_look`: Die Schnittstelle aus §27 kennt
    zwei Aufrufe und ``available``; ``model_choices`` gehört zu ComfyUI. Ein
    Testdoppel oder ein späterer gehosteter Dienst bekommt hier ein leeres
    Wörterbuch und damit keine Auswahlfelder — was richtig ist, denn er hat
    nichts zu wählen.
    """
    ask = getattr(backend, "model_choices", None)
    if not callable(ask):
        return {}
    try:
        found = ask(workflow)
    except TypeError:
        found = ask()
    except AppError:
        # Eine Auswahl ist eine Zugabe. Antwortet ComfyUI darauf nicht, steht
        # der Dialog trotzdem — die Bereitschaft daneben sagt ohnehin, was los
        # ist (Leitprinzip 8).
        _log.info("model choices unavailable", exc_info=True)
        return {}
    return dict(found) if isinstance(found, dict) else {}


class GenerateDialog(QDialog):
    """Fragt nach einer Beschreibung oder einem Bild und gibt einen erzeugten
    Körper zurück.
    """

    setupRequested = Signal()
    """Der Benutzer will den fehlenden Generator einrichten (§2.7, Regel 17).

    Wie im Chat: Das Panel weiß, *dass* etwas fehlt, aber nicht, wo man es
    holt — das entscheidet das Fenster.
    """
    nodesRequested = Signal()
    """ComfyUI läuft, kennt aber die Knoten nicht — der Weg dorthin ist ein
    anderer als der zur Liste der Programme."""

    def __init__(self, backend: MeshBackend | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.backend: MeshBackend = backend or ComfyBackend()
        # **Vor der Bereitschaftsfrage**, denn die hängt daran: Mit Bild fährt
        # dieser Dialog den Bildweg, ohne den Textweg, und die beiden brauchen
        # nicht dasselbe. Ohne diese Zeile hier oben lief ``_workflow`` in ein
        # noch nicht gesetztes Feld — und ein Konstruktor, der auf halbem Weg
        # abbricht, hinterlässt ein Fenster ohne Arbeiterfeld.
        self._image: bytes | None = None
        self._readiness: mesh.Readiness | None = None
        """Die letzte Antwort — ``None`` heißt, dass gerade nachgesehen wird."""
        self._readiness_worker: _ReadinessWorker | None = None
        self._readiness_pending = False
        """Der Ablauf wechselte, während die vorige Frage noch lief."""
        self.result_mesh: GeneratedMesh | None = None
        self._busy = False
        """Ob gerade ein Wurf läuft — siehe :meth:`_running`."""
        self._worker: _Worker | None = None
        self._leash = WorkerLeash(self)
        """Hält den ausgelaufenen Arbeiter, bis Qt mit ihm durch ist — das
        Warum steht in :mod:`app.ui.leash`."""
        self.tries: list[GeneratedMesh] = []
        """Was bisher entstanden ist (Konzept P15, E8).

        Meshy rät, mehrere Varianten zu erzeugen und die sauberste zu nehmen —
        die Generierung enthält Zufall, und der erste Wurf ist selten der
        beste. Vier davon **gleichzeitig** zu starten ist dort richtig, wo ein
        Rechenzentrum wartet; hier läuft ComfyUI auf derselben Grafikkarte, an
        der jemand sitzt, und vier parallele Läufe wären vierfache Wartezeit
        für drei Ergebnisse, die niemand bestellt hat.

        Also nacheinander: der erste kommt nach der gewohnten Zeit, und wer
        will, lässt einen weiteren folgen."""

        self.setWindowTitle(tr("Modell erzeugen"))
        self.setMinimumWidth(480)

        self.prompt = QLineEdit(self)
        self.prompt.setPlaceholderText(tr("Was soll entstehen?"))

        self.seed = QSpinBox(self)
        self.seed.setRange(0, MAX_SEED)
        self.seed.setToolTip(
            tr("Derselbe Startwert liefert dasselbe Modell, solange das Modell dasselbe bleibt.")
        )

        self.picture = QPushButton(tr("Bild wählen …"), self)
        self.picture.clicked.connect(self._choose_image)
        self.picture_label = QLabel(tr("Kein Bild gewählt"), self)

        form = QFormLayout()
        form.addRow(tr("Beschreibung"), self.prompt)
        form.addRow(tr("Bild"), self.picture)
        form.addRow("", self.picture_label)

        # §2.4: vorn die zwei Werte, die man ändert; hinten alles andere. Der
        # Startwert stand an dritter Stelle über allem, was jemand hier tun
        # will — er entscheidet nichts, solange man ihn nicht wiederholen
        # will, und genau dafür ist er da.
        advanced = QWidget(self)
        advanced_form = QFormLayout(advanced)
        advanced_form.setContentsMargins(0, 0, 0, 0)
        advanced_form.addRow(tr("Startwert"), self.seed)

        # **Welches Modell die Arbeit macht** — wie beim Sprachmodell, wo die
        # Wahl im Chat-Dialog steht. Hier hinten und nicht vorn: Wer erzeugen
        # will, tippt einen Satz; das Modell hat eine Vorgabe, die trägt, und
        # eine Vorgabe ist mehr wert als eine Einstellmöglichkeit (§2.4).
        #
        # Die Felder entstehen erst, wenn ComfyUI geantwortet hat — was zur
        # Wahl steht, weiß nur der Rechner, auf dem es läuft
        # (:meth:`_fill_models`).
        self._models = QWidget(self)
        self._models_form = QFormLayout(self._models)
        self._models_form.setContentsMargins(0, 0, 0, 0)
        self._models.setVisible(False)
        self._model_fields: dict[str, QComboBox] = {}
        advanced_form.addRow(self._models)

        self.advanced = collapsible(tr("Weitere Einstellungen"), advanced, open_now=False)

        self.state = QLabel(self)
        self.state.setWordWrap(True)
        # **Keine Zahl im Balken.** Sie steht mittig, und der Rand der
        # Füllung wandert darunter hindurch: bei 45 % lag sie halb auf
        # Bernstein und halb auf der Spur, ab 60 % ganz auf Bernstein — mit
        # 1,69 Kontrast, also unlesbar. Eine Farbe, die auf beiden Gründen
        # trägt, gibt es nicht; eine dunklere Füllung nähme dem Balken den
        # Akzent (gerechnet: 4,5 Schriftkontrast kostet die Hälfte des
        # Flächenkontrasts). Der Prozentwert steht deshalb in der Zeile
        # daneben, wo ein ruhiger Grund ist.
        self.progress = QProgressBar(self)
        self.progress.setTextVisible(False)
        self.progress.setRange(0, 100)
        self.progress.setVisible(False)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("Erzeugen"))
        # „Erzeugen" trug den Akzent schon, nur hatte ihn niemand gesetzt: Qt
        # vergibt beim ersten ``show()`` den Default an den ersten
        # autoDefault-Knopf. Die Farbe war damit da, die halbfette Schrift
        # daneben nicht — und eine Bedeutung allein über Farbe ist Regel 18.
        # Er startet gesperrt, bis eine Beschreibung dasteht, und trägt den
        # Akzent trotzdem: Der Kunde soll sehen, wo es hinausgeht, bevor er
        # weiß, was er tippen muss.
        make_primary(self.buttons.button(QDialogButtonBox.StandardButton.Ok))
        self.buttons.accepted.connect(self._accept_or_start)
        self.buttons.rejected.connect(self.reject)

        # Die Versuche und der Weg zu einem weiteren — beide unsichtbar, bis
        # der erste da ist: ein leeres Feld über einem leeren Knopf sagt
        # nichts (§2.5).
        self.attempts = QListWidget(self)
        self.attempts.setVisible(False)
        self.attempts.setMaximumHeight(120)
        self.again = QPushButton(tr("Noch ein Versuch"), self)
        self.again.setVisible(False)
        self.again.clicked.connect(self._try_again)

        # Der Weg zu dem, was fehlt — siehe :meth:`_update_state`. Welcher
        # von beiden, entscheidet die Lage: Wo nichts läuft, hilft die Liste
        # der Programme; wo die Knoten fehlen, hilft die Einrichtung.
        self.setup = QPushButton(tr("Zusätzliche Programme …"), self)
        self.setup.setVisible(False)
        self.setup.clicked.connect(self._ask_for_setup)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.advanced)
        # Der Platz sammelt sich hier, nicht zwischen den Feldern: sonst
        # stand der Hinweis, warum „Erzeugen“ gesperrt ist, dreihundert Pixel
        # von dem Knopf entfernt, den er erklärt.
        layout.addStretch(1)
        layout.addWidget(self.state)
        layout.addWidget(self.setup)
        layout.addWidget(self.attempts)
        layout.addWidget(self.again)
        layout.addWidget(self.progress)
        layout.addWidget(self.buttons)

        self.prompt.textChanged.connect(self._update_state)
        self._update_state()
        self.recheck()

    # --- state ------------------------------------------------------------------

    @property
    def available(self) -> bool:
        return self._readiness is mesh.Readiness.READY

    @property
    def readiness(self) -> mesh.Readiness | None:
        """Wie weit der Generator vorbereitet ist — oder ob die Antwort läuft."""
        return self._readiness

    @property
    def _worth_starting(self) -> bool:
        """Ob ein Wurf jetzt überhaupt eine Chance hat.

        **Die eine Frage, die der Knopf und der Start stellen — vorher waren es
        zwei.** Der Knopf hing an „alles außer ABSENT", der Start an
        :attr:`available` („genau READY"), und dazwischen lagen drei Lagen, in
        denen *Erzeugen* klickbar war und der Klick nichts tat: kein Lauf, kein
        Balken, kein Satz. Ein Knopf ohne Wirkung ist schlimmer als ein
        gesperrter, denn der gesperrte hat den Satz daneben, der ihn erklärt.

        ``UNKNOWN`` zählt dazu: Dort antwortet etwas, das wir nicht kennen, und
        ein gesperrter Knopf wäre eine Behauptung darüber. ``NO_NODES`` und
        ``NO_MODEL`` zählen nicht — dort ist der Fehlschlag bekannt, der Satz
        nennt ihn, und der Knopf daneben behebt ihn (Regel 17). Jemanden
        Minuten auf einen sicheren Fehlschlag warten zu lassen wäre die
        schlechtere von zwei Auskünften.
        """
        return self._readiness in (mesh.Readiness.READY, mesh.Readiness.UNKNOWN)

    def _workflow(self) -> str:
        """Welchen Ablauf dieser Dialog gerade fahren würde.

        Ein Bild ist gewählt oder es ist keines: Genau daran entscheidet
        :meth:`_run`, welchen der beiden Aufrufe es nimmt, und genau daran muss
        die Bereitschaftsfrage hängen.
        """
        return "image_to_mesh" if self._image is not None else "text_to_mesh"

    def recheck(self) -> None:
        """Noch einmal nachsehen, wie weit der Generator ist.

        Nach dem Besuch bei den zusätzlichen Programmen oder bei der
        Einrichtung: Wer ComfyUI gerade gestartet hat, soll nicht den Dialog
        schließen und neu öffnen müssen, um es zu erfahren.
        """
        self._readiness = None
        self._update_state()
        worker = self._readiness_worker
        if worker is not None and worker.isRunning():
            self._readiness_pending = True
            return

        workflow = self._workflow()
        worker = _ReadinessWorker(self.backend, workflow)
        worker.done.connect(self._readiness_done)
        worker.crashed.connect(self._readiness_crashed)
        worker.finished.connect(lambda done=worker: self._readiness_finished(done))
        self._readiness_worker = worker
        self._leash.start(worker)

    def _readiness_done(self, workflow: str, found: object, choices: object) -> None:
        """Nur die Antwort für den noch sichtbaren Text- oder Bildweg nehmen."""
        if workflow != self._workflow():
            self._readiness_pending = True
            return
        assert isinstance(found, mesh.Readiness)
        self._readiness = found
        self._fill_models(choices if isinstance(choices, dict) else {})
        self._update_state()

    def _fill_models(self, choices: dict[str, tuple[str, ...]]) -> None:
        """Ein Auswahlfeld je Rolle, die wirklich eine Wahl hat.

        **Wo nur eine Datei liegt, steht kein Feld.** Eine Auswahl ohne
        Alternative ist keine, und ein Aufklappmenü mit einem Eintrag ist eine
        Frage, auf die es nur eine Antwort gibt (§2.4). Genauso wenig steht ein
        Feld für eine Rolle ohne Namen — ``shape_vae`` gehört zu einem Ablauf,
        den Solidon nicht mitliefert.

        Gebaut wird bei jeder Antwort neu: Bild- und Textweg brauchen
        verschiedene Rollen, und wer zwischendurch ein Modell dazulegt, soll es
        nach dem nächsten Nachsehen in der Liste finden.
        """
        while self._models_form.rowCount():
            self._models_form.removeRow(0)
        self._model_fields.clear()

        for role, files in choices.items():
            spec = mesh.MODEL_ROLES.get(role)
            if spec is None or not str(spec.title) or len(files) < 2:
                continue
            box = QComboBox(self)
            # Die Vorgabe zuerst und ohne Dateinamen: Sie ist das, was ohne
            # Zutun passiert, und der Name dahinter wechselt mit dem Bestand.
            box.addItem(tr("Automatisch"), mesh.AUTOMATIC)
            for name in files:
                box.addItem(name, name)
            chosen = mesh.configured_model(role)
            at = box.findData(chosen) if chosen else 0
            box.setCurrentIndex(max(at, 0))
            box.setToolTip(
                tr("Welches Modell diese Aufgabe übernimmt. „Automatisch“ nimmt das, was passt.")
            )
            self._models_form.addRow(str(spec.title), box)
            self._model_fields[role] = box

        # Die Überschrift verschwindet mit den Feldern: ein leerer Abschnitt in
        # „Weitere Einstellungen“ wäre ein Versprechen ohne Inhalt.
        self._models.setVisible(bool(self._model_fields))

    def _remember_models(self) -> None:
        """Die getroffene Wahl behalten (§38) — vor dem Wurf, nicht danach.

        Vorher, weil der Wurf sie benutzt: :meth:`ComfyBackend._pick` liest sie
        aus den Einstellungen und nicht aus diesem Dialog. Der Kern kennt kein
        Fenster (§7), und ein zweiter Weg, ihm die Wahl mitzugeben, wäre ein
        zweiter Weg zu demselben Wert.
        """
        for role, box in self._model_fields.items():
            value = box.currentData()
            mesh.remember_model(role, str(value) if isinstance(value, str) else mesh.AUTOMATIC)

    def _readiness_crashed(self, detail: str) -> None:
        """Eine unerwartete Antwort beendet den Wartezustand und lässt einen Versuch zu."""
        _log.warning("generator readiness crashed: %s", detail)
        self._readiness = mesh.Readiness.UNKNOWN
        self._update_state()
        self.state.setText(f"{UNEXPECTED_CRASH!s} {detail}")

    def _readiness_finished(self, worker: object) -> None:
        if self._readiness_worker is worker:
            self._readiness_worker = None
        self._leash.hold_until_done(worker)
        if self._readiness_pending:
            self._readiness_pending = False
            self.recheck()

    def wait_for_readiness(self, timeout_ms: int = WAIT_TIMEOUT_MS) -> bool:
        """Auf die äußere Erhebung warten — für Tests und geordnetes Schließen."""
        worker = self._readiness_worker
        return worker.wait(timeout_ms) if worker is not None else True

    def _ask_for_setup(self) -> None:
        """Der Knopf führt dorthin, wo die Lage zu beheben ist."""
        if self._readiness is mesh.Readiness.NO_NODES:
            self.nodesRequested.emit()
        else:
            self.setupRequested.emit()

    def _update_state(self) -> None:
        # **Drei Lagen, und die mittlere war die schlimmste.** Geprüft wurde,
        # ob ein Port antwortet — und dann stand „Bereit" da, auch wenn dieses
        # ComfyUI die Knoten des Ablaufs nicht kennt. Wer es installiert und
        # gestartet hatte, ohne sie einzurichten, tippte seinen Satz, drückte
        # *Erzeugen*, wartete, und erfuhr es danach. Die Auskunft war die ganze
        # Zeit einen HTTP-Aufruf entfernt.
        # **Solange geprüft wird, läuft der Balken.** Der Satz stand als
        # nackte Zeile in zwei Dritteln leerer Fläche: Ob die Prüfung noch
        # läuft oder hängengeblieben ist, sah man ihm nicht an. Der Balken
        # ist derselbe, der später den Fortschritt der Erzeugung zeigt —
        # unbestimmt, weil eine Prüfung keinen Fortschritt hat, den jemand
        # ehrlich beziffern könnte (§2.8).
        # Zurückgestellt wird ausdrücklich: Der Erzeugungslauf setzt nur
        # ``setValue`` und erbte sonst den unbestimmten Bereich — ein Balken,
        # der bei fünfzig Prozent weiterläuft, als wüsste er nichts.
        checking = self._readiness is None
        if checking:
            self.progress.setRange(0, 0)
        else:
            self.progress.setRange(0, 100)
        self.progress.setVisible(checking)
        if self._readiness is None:
            self.state.setText(tr("Generator wird geprüft …"))
            self.setup.setText(tr("Zusätzliche Programme …"))
        elif self._readiness is mesh.Readiness.ABSENT:
            self.state.setText(
                tr(
                    "Es läuft kein Generator. Solidon spricht lokal mit ComfyUI — "
                    "ohne das bleibt dieser Weg zu, alles andere funktioniert weiter."
                )
            )
            self.setup.setText(tr("Zusätzliche Programme …"))
        elif self._readiness is mesh.Readiness.NO_NODES:
            self.state.setText(
                tr(
                    "ComfyUI läuft, kennt aber die Knoten dieses Ablaufs noch nicht. "
                    "Solidon legt sie hinein — danach ComfyUI einmal neu starten."
                )
            )
            self.setup.setText(tr("Knoten und Modell einrichten …"))
        elif self._readiness is mesh.Readiness.NO_MODEL:
            # **Der Satz nannte, was fehlt, und ließ offen, welches.** „Ein
            # SDXL-Modell unter models/checkpoints" ist wahr und schickt
            # jemanden suchen, der nicht weiß, wonach — es gibt Dutzende, und
            # die Hälfte davon löst eine andere Aufgabe. Der Name steht seit
            # dem 30.08.2026 in ``comfy_setup``, damit Dialog und Handbuch
            # dieselbe Datei nennen; hier wird er eingesetzt, denn ein
            # Platzhalter ist in der Oberfläche richtig und nur im Kern falsch.
            self.state.setText(
                tr(
                    "ComfyUI läuft und kennt die Knoten, aber für den Weg aus Text "
                    "fehlt das Bildmodell. Ein Bild zu wählen umgeht es. Sonst: "
                    "„{file}“ nach „{folder}“ legen und ComfyUI neu starten — im "
                    "Handbuch steht es unter „Welche Modelle Solidon benutzt“."
                ).format(
                    file=comfy_setup.IMAGE_MODEL_FILE,
                    folder=comfy_setup.IMAGE_MODEL_FOLDER,
                )
            )
            self.setup.setText(tr("Zusätzliche Programme …"))
        elif self._readiness is mesh.Readiness.UNKNOWN:
            self.state.setText(
                tr(
                    "Auf dem Port antwortet etwas, das keine Auskunft über seine "
                    "Knoten gibt. Versuchen lässt es sich; ob es geht, sagt der Lauf."
                )
            )
            self.setup.setText(tr("Zusätzliche Programme …"))
        else:
            self.state.setText(tr("Bereit. Das kann einige Minuten dauern."))
        # Regel 17: Der Satz sagte, was fehlt, und bot nichts an. Derselbe Weg
        # wie im Chat, wo „Chat einrichten …" neben dem Hinweis steht.
        # Sichtbar nur, solange etwas zu beheben ist.
        self.setup.setVisible(
            self._readiness
            in (mesh.Readiness.ABSENT, mesh.Readiness.NO_NODES, mesh.Readiness.NO_MODEL)
        )
        # ``_busy`` gehört hierher und nicht nur in ``_running``: Diese Methode
        # hängt am Textfeld, und das bleibt während des Laufs bedienbar. Wer
        # weitertippte, machte *Erzeugen* wieder klickbar und startete einen
        # zweiten Arbeiter, der den ersten im Feld ersetzt. Die gesperrte
        # Knopfleiste hatte das verdeckt, nicht verhindert.
        ready = (
            self._worth_starting
            and not self._busy
            and bool(self.prompt.text().strip() or self._image)
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(ready)

    def _choose_image(self) -> None:
        name, _filter = QFileDialog.getOpenFileName(self, tr("Bild wählen"), "", image_filter())
        if not name:
            return
        self.set_image(Path(name))

    def set_image(self, path: Path) -> None:
        """Ein Bild vorbelegen, ohne den Dateidialog.

        Der Weg für ein Bild, das jemand ins Chatfenster gezogen hat: es ist
        schon gewählt, also wäre ein Dialog, der noch einmal danach fragt, ein
        Schritt zu viel (Konzept P15, E8).
        """
        self._image = path.read_bytes()
        self.picture_label.setText(path.name)
        # **Der Weg hat gewechselt, also gilt die alte Antwort nicht mehr.** Mit
        # Bild braucht es kein SDXL-Modell; ohne schon. Wer eines wählt, soll
        # nicht weiter lesen, dass etwas fehlt, was er gerade umgangen hat.
        self.recheck()

    # --- running ----------------------------------------------------------------

    def _accept_or_start(self) -> None:
        """Derselbe Knopf: erst erzeugen, danach übernehmen.

        Zwei Knöpfe nebeneinander, von denen immer einer tot ist, wären eine
        Frage mehr als nötig — und welcher gilt, sagt der Zustand, nicht der
        Benutzer.
        """
        if self.tries:
            self.result_mesh = self.chosen()
            self.accept()
            return
        self._start()

    def _running(self, running: bool) -> None:
        """Während der Lauf läuft, ist *Erzeugen* gesperrt — **Abbrechen nicht**.

        Vorher sperrte hier die ganze Leiste, und damit ausgerechnet der Knopf,
        den man während einer Rechnung als Einzigen braucht: Ein
        Diffusionsmodell braucht Minuten, und die einzige verbliebene Tür war
        Esc — eine Taste, die niemand sucht, weil der Weg daneben grau
        dasteht. Der Ausgang selbst war fertig (:meth:`reject` wartet auf den
        Thread), unerreichbar war nur sein Knopf.
        """
        self._busy = running
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(not running)
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setEnabled(True)

    def _start(self) -> None:
        # Dieselbe Frage wie am Knopf (:attr:`_worth_starting`) und nicht
        # ``available``: Wo die beiden auseinanderliefen, war *Erzeugen*
        # klickbar und der Klick folgenlos.
        if not self._worth_starting:
            return
        self._remember_models()
        self._running(True)
        self.progress.setVisible(True)
        self.progress.setValue(0)

        worker = _Worker(self.backend, self.prompt.text().strip(), self._image, self.seed.value())
        worker.done.connect(self._on_done)
        worker.failed.connect(self._on_failed)
        # **Und das Unerwartete.** Der Arbeiter fing ``AppError``; alles andere
        # — ein Netz, das trimesh nicht liest, eine Antwort in unbekannter
        # Form — riss den Thread ab, und der Dialog blieb mit laufendem Balken
        # auf „wird erzeugt" stehen. Bei einem Vorgang, der Minuten dauert, ist
        # das von einem Hänger nicht zu unterscheiden.
        worker.crashed.connect(self._crashed)
        worker.step.connect(self._on_step)
        worker.finished.connect(self._on_thread_done)
        self._worker = worker
        self._leash.start(worker)

    def _on_step(self, fraction: float, text: str) -> None:
        self.progress.setValue(int(max(0.0, min(1.0, fraction)) * 100))
        if text:
            self.state.setText(text)

    def _on_done(self, result: object) -> None:
        assert isinstance(result, GeneratedMesh)
        self.tries.append(result)
        self.result_mesh = result
        _log.info("generated %d triangles", result.mesh.triangle_count)
        self.progress.setVisible(False)
        self._running(False)
        self._show_tries()

    def _show_tries(self) -> None:
        """Die Versuche mit den Zahlen, an denen man sie unterscheidet.

        Dreiecke, Volumen und ob der Körper geschlossen ist — dieselben drei,
        die auch der Steckbrief nennt. Sie entscheiden, welcher Wurf brauchbar
        ist, und ein Bild daneben entschiede es nicht besser: ein offenes Netz
        sieht aus wie ein geschlossenes.
        """
        self.attempts.clear()
        for index, entry in enumerate(self.tries, start=1):
            mesh = entry.mesh
            closed = tr("geschlossen") if mesh.is_watertight else tr("offen")
            item = QListWidgetItem(
                f"{index}. {mesh.triangle_count} {tr('Dreiecke')} · "
                # Dieselbe Quelle wie Steckbrief und Chat (labels.volume):
                # feste Kubikzentimeter meldeten kleine Körper als „0,0 cm³"
                # und blieben in Zoll stehen.
                + volume(mesh.volume)
                + f" · {closed}"
            )
            self.attempts.addItem(item)
        self.attempts.setCurrentRow(len(self.tries) - 1)
        self.attempts.setVisible(True)
        self.again.setVisible(True)
        self.state.setText(
            tr("Der Zufall spielt mit — ein weiterer Versuch kostet nichts als Zeit.")
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("Übernehmen"))

    def _try_again(self) -> None:
        """Noch einen Wurf, mit dem nächsten Startwert.

        Der Startwert wird hochgezählt und nicht gewürfelt: derselbe Dialog
        zweimal geöffnet soll dieselbe Reihe liefern (Regel 9).
        """
        self.seed.setValue(min(self.seed.value() + 1, MAX_SEED))
        self._start()

    def chosen(self) -> GeneratedMesh | None:
        """Der ausgewählte Versuch — der zuletzt erzeugte, wenn keiner
        angeklickt wurde."""
        row = self.attempts.currentRow()
        if 0 <= row < len(self.tries):
            return self.tries[row]
        return self.result_mesh

    def _crashed(self, detail: str) -> None:
        """Womit niemand gerechnet hat — und der Weg aus dem Wartezustand."""
        _log.warning("generation crashed: %s", detail)
        self._on_failed(f"{UNEXPECTED_CRASH!s} {detail}")

    def _on_failed(self, problem: object) -> None:
        """Was nicht ging, warum, und was jetzt hilft — alle drei (§2.7).

        Der Titel allein sagt „konnte nicht starten" und lässt den Nutzer
        stehen; erst das Detail nennt den Grund, und erst der Vorschlag nennt
        den Ausweg. Modal wird hier nichts: ein Fehlerdialog über einem Dialog
        ist eine Sackgasse mit Vorgeschichte.

        **Und die Angaben des Fehlers, denn hier stehen die einzigen, die
        weiterhelfen.** ``mesh._failed`` schreibt in sein ``detail`` „Was es
        dazu sagt, steht daneben" und legt Knotennamen und ComfyUIs eigene
        Fehlerzeile in ``values`` — „Torch not compiled with CUDA enabled",
        „No module named …", Speichermangel. Daneben stand nichts: Der Kunde
        las einen Verweis ins Leere, und ausgerechnet die Zeile, mit der er
        zum Support geht, fiel weg. Elf Fehlerpfade in ``backends/mesh.py``
        tragen solche Werte.
        """
        self.progress.setVisible(False)
        self._running(False)
        if not isinstance(problem, AppError):
            self.state.setText(str(problem))
            return

        lines = [str(problem.title)]
        if problem.detail is not None:
            lines.append(str(problem.detail))
        lines.extend(spoken_values(problem))
        # „Abbrechen" ist der Ausgang, kein Rat — genannt wird, was weiterhilft.
        ways = [str(action.label) for action in problem.suggestions if action.id != CANCEL.id]
        if ways:
            lines.append(" · ".join(ways))
        self.state.setText("\n".join(lines))

    def _on_thread_done(self) -> None:
        # `finished` heißt „`run` ist zurück", nicht „das Objekt darf weg" —
        # das Loslassen übernimmt die Halteleine.
        worker = self._worker
        self._worker = None
        if worker is not None:
            self._leash.hold_until_done(worker)

    def _stop_worker(self) -> None:
        """Dem laufenden Wurf sagen, dass niemand mehr auf ihn wartet (§15.6).

        Ohne diesen Schritt war *Abbrechen* eine Anzeige: Der Dialog ging zu,
        und der Arbeiter fragte ComfyUI bis zu einer Stunde weiter. Das steht
        an **beiden** Ausgängen — geschlossen wird über :meth:`reject`,
        weggeräumt über :meth:`release`, und ein Arbeiter, der nur den einen
        Weg kennt, überlebt den anderen.
        """
        worker = self._worker
        if worker is not None:
            worker.cancel()

    def reject(self) -> None:
        """Abbrechen hält das Warten an und wartet auf den Thread.

        **Der Auftrag auf der anderen Seite läuft weiter.** Die Schnittstelle
        aus §27 hat keinen Aufruf, ihn zurückzunehmen, und einen zu erfinden,
        der lügt, wäre schlechter, als nichts zu sagen — was Solidon aufhört,
        ist das Warten darauf, und genau das hat der Nutzer angeklickt.
        """
        self._stop_worker()
        self.wait_for_workers()
        super().reject()

    def release(self, timeout_ms: int = WAIT_TIMEOUT_MS) -> None:
        """Alles loslassen, was dieses Fenster außerhalb von Qt hält.

        **Ein Name für den Aufräumbefehl, auf allen Klassen, die Arbeiter
        halten.** Es waren fünf — ``release``, ``wait_for_workers``,
        ``wait_for_survey``, ``wait_for_look``, ``wait_for_setup`` —, und wer
        eine Testfixture darauf baute, sammelte sie nacheinander ein: erst
        zwei, dann drei, dann vier. Der fünfte fehlte, und der Prozess starb
        beim Abbau an einem Thread, der sein Fenster überlebt hatte.

        Der fachliche Name daneben bleibt: ``wait_for_workers`` tut hier schon dasselbe;
        ``release`` ist der
        Name, unter dem es von außen gefunden wird.
        """
        self._stop_worker()
        self.wait_for_workers(timeout_ms)

    def wait_for_workers(self, timeout_ms: int = WAIT_MILLISECONDS) -> None:
        """Kein Arbeiter überlebt diesen Dialog.

        Derselbe Name wie am Hauptfenster, und aus demselben Grund: Es gibt
        zwei Wege, einen Dialog loszuwerden — schließen und wegräumen. Der
        zweite ist der Weg der Suite, und dort sucht die Aufräumhilfe
        (``tests/conftest.py``) genau diesen Namen an jedem obersten Fenster.
        Ein Dialog, der ihn nicht führt, bleibt unbeachtet, mit laufendem
        Arbeiter — und ein Thread, der sein Fenster überlebt, nimmt den Prozess
        mit.
        """
        worker = self._worker
        if worker is not None and worker.isRunning():
            worker.wait(timeout_ms)
        readiness_worker = self._readiness_worker
        if readiness_worker is not None and readiness_worker.isRunning():
            readiness_worker.wait(timeout_ms)
        self._leash.wait_all()
