"""Das Hauptfenster (Bauplan §2.5).

Höchstens drei sichtbare Zonen: die Panels links, der Viewport in der Mitte,
Prüfbericht oder Chat rechts — und die rechte Seite klappt mit einer Taste ganz
weg. Betriebsarten gibt es nicht; es gibt einen Zustand, und der ist die Szene.

Das Menü steht auch hier nicht ausgeschrieben: es wird aus dem Register gebaut
— eine Operation erscheint also im Menü, in der Palette und auf der
Kommandozeile, sobald sie deklariert ist (§10).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import (
    QAction,
    QCloseEvent,
    QDragEnterEvent,
    QDropEvent,
    QKeySequence,
    QShortcut,
)
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QSplitter,
    QStackedWidget,
    QTabWidget,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from app.branding import APP_NAME, PROJECT_SUFFIX
from app.core import examples, updates
from app.core.backends import llm
from app.core.errors import AppError, InternalError
from app.core.export.handover import SliceOutcome
from app.core.export.writer import (
    ExportFormat,
    plan_export,
    safe_name,
    write_assembly,
    write_plan,
)
from app.core.geom.mesh import as_mesh_data
from app.core.knowledge import calibration
from app.core.knowledge.parts.ops import op_name as part_op_name
from app.core.log import get_logger
from app.core.perceive import maps
from app.core.registry import REGISTRY, OperationSpec, PaletteEntry, menu_tree, palette_entries
from app.core.scene import EvaluationResult, OperationDraft, values_for
from app.core.scene.project import find_recovery
from app.core.slice import gcode
from app.core.slice.analysis import slice_body
from app.core.tour import tour_for
from app.core.types import Finding, ObjectId, SliceResult
from app.i18n import TranslatableText, _, tr
from app.ui import first_run
from app.ui.analysis_bar import AnalysisBar, LayerBar
from app.ui.catalog import PartCatalog
from app.ui.chat import ChatPanel
from app.ui.command_palette import CommandPalette
from app.ui.dialogs import (
    AboutDialog,
    AskDialog,
    CalibrationDialog,
    KeyDialog,
    ParameterDialog,
    confirm_discard,
    confirm_unsaved,
    show_details,
    show_error,
)
from app.ui.explode_bar import ExplodeBar
from app.ui.generate_dialog import GenerateDialog
from app.ui.icons import icon
from app.ui.install_dialog import InstallDialog
from app.ui.labels import feature_label
from app.ui.manual_window import ManualWindow
from app.ui.op_dialog import OperationDialog
from app.ui.paint_bar import PaintBar
from app.ui.panels import (
    HistoryPanel,
    MeasurementLabel,
    ObjectTree,
    ParameterPanel,
    ReportPanel,
    collapsible,
    describe_selection,
)
from app.ui.print_settings_dialog import PrintSettingsDialog
from app.ui.report_dialog import ErrorReportDialog
from app.ui.section_bar import MeasureBar, SectionBar
from app.ui.session import AskRequest, Session
from app.ui.settings import UiSettings, save_settings
from app.ui.settings_dialog import SettingsDialog
from app.ui.sketch_editor import SketchPanel
from app.ui.start_screen import StartScreen, accepted_path
from app.ui.theme import apply_theme
from app.ui.tool_strip import ToolStrip, strip_title
from app.ui.tour import TourPanel
from app.ui.transform_bar import TransformBar
from app.ui.variants_dialog import VariantsDialog
from app.ui.viewport import Viewport

_log = get_logger(__name__)

AUTOSAVE_INTERVAL_MS = 120_000

PROJECT_FILTER = f"{APP_NAME} ({'*' + PROJECT_SUFFIX})"
MODEL_FILTER = "Modelle (*.stl *.3mf *.obj *.glb *.gltf *.ply *.off *.step *.stp *.svg *.dxf)"
GCODE_FILTER = "G-Code (*.gcode *.gco *.g *.nc)"


class _MapWorker(QThread):
    """Eine Analysekarte, abseits des Oberflächen-Threads (§18.9).

    Sekunden an einem großen Körper — lang genug, dass ein Fenster, das sie in
    der Ereignisschleife rechnet, aufhört zu zeichnen, und das liest sich wie
    ein Absturz statt wie Arbeit.
    """

    done = Signal(object)
    tooLarge = Signal()

    def __init__(self, kind: Any, entry: Any, profile: Any, scene: Any) -> None:
        super().__init__()
        self._kind = kind
        self._entry = entry
        self._profile = profile
        self._scene = scene

    def run(self) -> None:
        try:
            self.done.emit(
                maps.build(self._kind, self._entry, profile=self._profile, scene=self._scene)
            )
        except maps.MapTooLarge:
            # §31: eine Karte, die Minuten bräuchte, sagt Nein, statt einzufrieren.
            self.tooLarge.emit()


class _UpdateWorker(QThread):
    """Die Update-Anfrage, abseits des Oberflächen-Threads (§37.2).

    Sie lief beim Start im Hauptthread — ihr Docstring versprach „niemand
    wartet auf sie", das Fenster wartete aber bis zu vier Sekunden auf einen
    Server, der nicht antwortet. Jetzt wartet wirklich niemand.
    """

    done = Signal(object)

    def run(self) -> None:
        self.done.emit(updates.check())


class _OllamaSizeWorker(QThread):
    """Die Modellgrößen-Frage an Ollama (§27), abseits des Oberflächen-Threads.

    Sie läuft nur, wenn der Chat über das lokale Modell aufwacht. Das Ergebnis
    ist ein Satz oder nichts — und ein Server, der nicht antwortet, ist kein
    Fehler, sondern Schweigen.
    """

    done = Signal(object)

    def __init__(self, model: str) -> None:
        super().__init__()
        self._model = model

    def run(self) -> None:
        self.done.emit(llm.ollama_size_warning(self._model))


class _SliceWorker(QThread):
    """Eine Schichtanalyse, abseits des Oberflächen-Threads (§2.8, §22).

    Dieselbe Begründung wie bei der Analysekarte, nur später bemerkt: an einem
    großen Körper dauert sie Sekunden, und ein Wartezeiger macht daraus keine
    kürzere Blockade, nur eine angekündigte.
    """

    done = Signal(object)

    def __init__(self, entry: Any, layer_height: float) -> None:
        super().__init__()
        self._entry = entry
        self._layer_height = layer_height

    def run(self) -> None:
        self.done.emit(slice_body(as_mesh_data(self._entry.mesh), self._layer_height))


def inputs_for(
    spec: OperationSpec, objects: list[ObjectId], selected: Sequence[ObjectId]
) -> tuple[ObjectId, ...]:
    """Auf welche Objekte eine Operation angewandt wird (§10, §25).

    Eine eigene Funktion, keine zwei Zeilen im Menü-Handler: die Regel ist
    dieselbe für Kommandozeile und Agent, und eine Operation, die auf der
    ganzen Szene arbeitet und nichts bekommt, läuft auf nichts und sieht kaputt
    aus.

    ``selected`` ist die Auswahl in Klickreihenfolge. Eine Operation nimmt so
    viele davon, wie sie deklariert — vorher nahm sie immer genau eines, und
    damit war keine der drei Booleschen über das Menü ausführbar: sie
    erwarten zwei und bekamen eines.
    """
    if spec.takes_whole_scene:
        return tuple(objects)
    return tuple(selected[: spec.consumes]) if spec.consumes else ()


#: Wie die dreizehn Kategorien des Registers auf Menüs der Leiste fallen (§2.5).
#:
#: Vier eigene Menüs plus dreizehn aus dem Register waren siebzehn — bei 1280
#: Pixeln Fensterbreite läuft das über, und selbst wo es passt, ist es keine
#: Leiste mehr, sondern eine Liste. Die Kategorie im Register bleibt, wie
#: Bauplan §25 sie festlegt; hier liegt nur eine Zuordnung darüber. Eine
#: Gruppe mit einer einzigen Kategorie steht flach, sonst bekommt jede
#: Kategorie ihr Untermenü.
#: Die Titel sind mit ``_()`` markiert, nicht mit ``tr()``: der Abgleich der
#: Sprachdateien liest literale Aufrufe, und ``tr(variable)`` sieht er nicht —
#: die Gruppen wären auf Deutsch stehen geblieben (Regel 20).
MENU_GROUPS: tuple[tuple[TranslatableText, tuple[str, ...]], ...] = (
    (_("Objekt"), ("scene",)),
    (_("Erzeugen"), ("import", "sketch", "label")),
    (_("Ändern"), ("boolean", "transform", "shaping", "holes", "surface", "mesh", "repair")),
    (_("Bausteine"), ("parts",)),
    (_("Vorbereiten"), ("prepare", "colour")),
)


def _format_of(target: Path, chosen_filter: str) -> ExportFormat:
    """Das Exportformat aus dem Dateinamen, sonst aus dem gewählten Filter.

    Wer ``teil.3mf`` tippt, meint 3MF, auch wenn der Filter noch auf STL
    steht — die Endung ist die ausdrücklichere der beiden Angaben.
    """
    from app.core.export.writer import FORMAT_SUFFIX

    suffix = target.suffix.lower()
    for name, ending in FORMAT_SUFFIX.items():
        if suffix == ending:
            return name
    for name, ending in FORMAT_SUFFIX.items():
        if f"*{ending}" in chosen_filter:
            return name
    return "stl"


def _has_sketch_param(spec: OperationSpec) -> bool:
    """Ob diese Operation eine gezeichnete Skizze verbraucht (§30.1)."""
    return any(entry.kind == "sketch" for entry in spec.params.spec())


def _sketch_param(op_name: str) -> str:
    """Wie der Skizzenparameter dieser Operation heißt (§30.1).

    Gefragt statt geraten: der Name steht im Schema, und eine zweite Liste
    daneben wäre eine zweite Wahrheit. Operationen ohne Skizzenfeld kommen
    hier nie an — der Modus wird nur für die angeboten, die eines haben.
    """
    for entry in REGISTRY.get(op_name).params.spec():
        if entry.kind == "sketch":
            return entry.name
    raise InternalError(
        detail=f"{op_name!r} has no sketch parameter",
        values={"op": op_name},
    )


def _needs_objects(count: int) -> str:
    """Der Satz, der sagt, wie viele Körper fehlen — nicht nur, dass welche
    fehlen.

    „Wählen Sie zuerst ein Objekt" half bei einer Vereinigung nicht weiter:
    eines war ja gewählt. Sie braucht zwei, und das steht jetzt da.
    """
    if count <= 1:
        return tr("Wählen Sie zuerst ein Objekt im Objektbaum.")
    return tr("Diese Operation braucht zwei Objekte. Das zweite dazu mit Strg und Klick.")


class MainWindow(QMainWindow):
    """Fenster, Menüs und die Verdrahtung zwischen Sitzung und Panels."""

    projectOpened = Signal(Path)

    def __init__(self, session: Session, settings: UiSettings) -> None:
        super().__init__()
        self.session = session
        self.settings = settings
        self.setAcceptDrops(True)
        self.setWindowTitle(APP_NAME)
        self.resize(1280, 820)
        self._map_cache: dict[tuple[str, str, int], Any] = {}
        self._map_worker: Any = None
        """The map being computed (§18.9). A newer request replaces it."""
        """Only the last map is kept: they are cheap to rebuild and large to hold."""
        self._slice_cache: SliceResult | None = None
        self._slice_key: tuple[str, int] | None = None
        self._slice_worker: Any = None
        self._update_worker: Any = None
        """Die laufende Update-Anfrage (§37.2) — festgehalten wie jeder
        andere Arbeiter, damit sie das Fenster nicht überlebt."""
        self._ollama_size_worker: Any = None
        """Die Modellgrößen-Frage an Ollama (§27), aus demselben Grund."""
        self._retired: list[Any] = []
        """Ersetzte Arbeiter, bis sie ausgelaufen sind. „Eine neuere Anfrage
        ersetzt die wartende" hieß hier: die Referenz überschreiben — und ein
        laufender QThread ohne Referenz wird vom Speicherbereiniger mitsamt
        C++-Objekt zerstört. Ein Absturz ohne Zeile, irgendwann später."""
        self._proposal: Any = None
        """The agent turn waiting for a decision (§26.5)."""
        self._manual: ManualWindow | None = None
        """Das Handbuchfenster, einmal gebaut und danach wiederverwendet."""
        self._hidden: frozenset[str] = frozenset()
        """§18.8: was der Nutzer ausgeblendet hat. Ansichtszustand des
        Fensters, nicht des Dokuments — er reist nicht mit der Datei."""
        self._menus: list[QMenu] = []
        """Jedes Menü der Leiste, festgehalten.

        PySide gibt für ein Menü bei jedem Zugriff einen neuen Wrapper, und
        wird einer davon eingesammelt, nimmt er das C++-Objekt mit — danach
        zeigt die Leiste auf ein Menü, das es nicht mehr gibt. Solange nur die
        Bar sie kannte, ging das gut; mit der zweiten Ebene wird aus dem
        Zufall ein Fehler."""
        self._seen_objects = False
        """Ob die Szene schon einmal einen Körper hatte — der erste bekommt
        die Kamera."""
        self._op_actions: dict[str, QAction] = {}
        """Die Menüeinträge der Operationen, damit sie sich ausgrauen lassen.
        Ein Menü, in dem alles anklickbar ist und die Hälfte mit „Bitte zuerst
        etwas auswählen" antwortet, lässt den Nutzer die Regeln erraten."""

        self._build_central()
        self._build_status_bar()
        self._build_menus()
        self._connect_session()
        self._update_actions()

        # §2.6: das offene Werkzeug schließen. ``close_tool`` gab es dafür seit
        # jeher und niemanden, der es rief — Escape tat nichts.
        QShortcut(QKeySequence(Qt.Key.Key_Escape), self, self._escape)

        # §19.2: der Viewport ist mit der Tastatur navigierbar. Die
        # Achsansichten waren es, Zoom und Durchblättern nicht — wer ohne
        # Zeigegerät arbeitet, sah jedes Modell aus derselben Entfernung.
        for sequence, step in (
            (QKeySequence.StandardKey.ZoomIn, 1.25),
            (QKeySequence.StandardKey.ZoomOut, 0.8),
        ):
            QShortcut(sequence, self, lambda factor=step: self.viewport.zoom(factor))
        QShortcut(QKeySequence("Ctrl+Tab"), self, lambda: self.object_tree.step_selection(True))
        QShortcut(
            QKeySequence("Ctrl+Shift+Tab"), self, lambda: self.object_tree.step_selection(False)
        )

        self._autosave = QTimer(self)
        self._autosave.setInterval(AUTOSAVE_INTERVAL_MS)
        self._autosave.timeout.connect(self.session.autosave)
        self._autosave.start()

        self.start_screen.show_recent(settings.existing_recent())
        self._show_start_screen(True)

    # --- construction -----------------------------------------------------------

    def _build_central(self) -> None:
        self.object_tree = ObjectTree(self)
        self.parameters = ParameterPanel(self)
        self.history_panel = HistoryPanel(self)
        self.history_panel.operationActivated.connect(self.edit_operation)

        left = QWidget(self)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)
        left_layout.addWidget(collapsible(tr("Objekte"), self.object_tree), stretch=2)
        left_layout.addWidget(collapsible(tr("Parameter"), self.parameters), stretch=1)
        left_layout.addWidget(collapsible(tr("Verlauf"), self.history_panel), stretch=1)

        self.viewport = Viewport(self)
        self.viewport.measurementTaken.connect(self._on_measurement)
        self.section_bar = SectionBar(self)
        self.section_bar.sectionChanged.connect(self._on_section)
        self.measure_bar = MeasureBar(self)
        self.measure_bar.modeChanged.connect(self.viewport.set_measure_mode)
        self.measure_bar.clearRequested.connect(self.viewport.clear_measurements)
        self.transform_bar = TransformBar(self)
        self.transform_bar.gizmoToggled.connect(self.viewport.set_gizmo)
        self.transform_bar.snappingChanged.connect(self.viewport.set_snapping)
        self.viewport.transformDragged.connect(self._on_transform_dragged)
        self.viewport.featurePicked.connect(self._on_feature_picked)

        self.analysis_bar = AnalysisBar(self)
        self.analysis_bar.mapChanged.connect(self._on_map_changed)
        self.analysis_bar.overlayToggled.connect(self.viewport.set_feature_overlay)
        self.layer_bar = LayerBar(self)
        self.layer_bar.layerChanged.connect(self._on_layer_changed)
        self.explode_bar = ExplodeBar(self)
        self.explode_bar.factorChanged.connect(self.viewport.set_explosion)
        self.explode_bar.plateChanged.connect(self.viewport.set_plate)
        self.paint_bar = PaintBar(self)
        self.paint_bar.paintingToggled.connect(self.viewport.set_painting)
        self.viewport.paintRequested.connect(self._on_paint)

        # §2.4: eine Zeile Umschalter statt sieben Dauerleisten. Wie ein
        # Werkzeug beim Schließen zurückgenommen wird, steht hier und nicht in
        # den Leisten — verdrahtet wird sowieso an dieser Stelle.
        self.tools = ToolStrip(self)
        self.tools.add(
            "section",
            tr("Schnitt"),
            self.section_bar,
            lambda: self.section_bar.axis.setCurrentIndex(0),
            symbol="section",
            hint=tr(
                "Ziehen Sie den Regler durch das Teil, oder tippen Sie eine Höhe. "
                "Die Schnittfläche wird geschlossen gezeigt — so ist die Wandstärke "
                "ablesbar."
            ),
        )
        self.tools.add(
            "measure",
            tr("Messen"),
            self.measure_bar,
            lambda: self.measure_bar.mode.setCurrentIndex(0),
            symbol="measure",
            hint=tr(
                "Zwei Punkte im Bild anklicken. Der Fang rastet auf Ecken und Kanten; "
                "für die Wandstärke genügt ein Klick auf die Fläche."
            ),
        )
        self.tools.add(
            "transform",
            tr("Bewegen"),
            self.transform_bar,
            lambda: self.transform_bar.gizmo.setChecked(False),
            symbol="move",
            hint=tr(
                "Am Griff im Bild ziehen, oder Werte eintippen. Jeder Zug wird ein "
                "Schritt im Verlauf und ist einzeln zurücknehmbar."
            ),
        )
        self.tools.add(
            "analysis",
            tr("Analyse"),
            self.analysis_bar,
            lambda: self.analysis_bar.selector.setCurrentIndex(0),
            symbol="analysis",
            hint=tr(
                "Karte wählen — der Körper färbt sich nach Zahlen, die Legende nennt "
                "den Bereich. Ein Klick auf eine Warnung im Prüfbericht fährt hin."
            ),
        )
        self.tools.add(
            "layers",
            tr("Schichten"),
            self.layer_bar,
            lambda: self.layer_bar.active.setCurrentIndex(0),
            symbol="layers",
            hint=tr(
                "Durch die Höhe fahren und den Querschnitt ansehen. Inseln sind "
                "hervorgehoben: dort beginnt Material in der Luft."
            ),
        )
        self.tools.add(
            "explode",
            tr("Explosion"),
            self.explode_bar,
            lambda: self.explode_bar.slider.setValue(0),
            symbol="explode",
            hint=tr(
                "Regler schiebt die Teile auseinander. Nur die Ansicht — was "
                "exportiert wird, bleibt, wo es ist."
            ),
        )
        # Bemalen ändert Materialslots und nicht bloß die Ansicht: das Schließen
        # beendet das Bemalen, nimmt aber nichts Gemaltes zurück.
        self.tools.add(
            "paint",
            tr("Bemalen"),
            self.paint_bar,
            lambda: self.paint_bar.active.setChecked(False),
            symbol="paint",
            hint=tr(
                "Slot wählen, dann auf die Fläche klicken. Das ändert das Modell, "
                "nicht nur das Bild — Strg+Z nimmt es zurück."
            ),
        )

        # §30.1 Stufe zwei: die Skizze ist ein Modus des mittleren Bereichs,
        # kein Fenster darüber. Der Stapel hat zwei Seiten — die Ansicht und
        # die Zeichenfläche —, und ein Modus, der die Ansicht ersetzt, ist
        # ehrlicher als ein Qt-Widget über einem OpenGL-Fenster: was man dort
        # sieht, gehört zwei Zeichenwegen, und einer von beiden hat immer
        # gerade nicht neu gezeichnet.
        self.middle_stack = QStackedWidget(self)
        self.middle_stack.addWidget(self.viewport)
        self._sketch_panel: SketchPanel | None = None
        self._sketch_target: str | None = None
        """Der Operationsname, für den gerade gezeichnet wird."""

        # Die Leiste des Skizzenmodus. Sie steht neben der Werkzeugzeile statt
        # in ihr: die sieben dort sind Ansichtswerkzeuge, die sich gegenseitig
        # ablösen — Zeichnen ist keines davon, und ein achter Umschalter hätte
        # die Grenze aus Etappe 0 gerissen, ohne dass er hingehört.
        self.sketch_bar = QWidget(self)
        sketch_row = QHBoxLayout(self.sketch_bar)
        sketch_row.setContentsMargins(6, 3, 6, 3)
        self._sketch_hint = QLabel(
            tr("Zeichnen, dann Fertig — die Operation öffnet auf der Skizze."), self.sketch_bar
        )
        sketch_row.addWidget(self._sketch_hint, stretch=1)
        done = QPushButton(tr("Fertig"), self.sketch_bar)
        done.clicked.connect(lambda: self.finish_sketch(keep=True))
        discard = QPushButton(tr("Verwerfen"), self.sketch_bar)
        discard.clicked.connect(lambda: self.finish_sketch(keep=False))
        sketch_row.addWidget(done)
        sketch_row.addWidget(discard)
        self.sketch_bar.setVisible(False)

        middle = QWidget(self)
        middle_layout = QVBoxLayout(middle)
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.setSpacing(0)
        middle_layout.addWidget(self.middle_stack, stretch=1)
        middle_layout.addWidget(self.sketch_bar)
        middle_layout.addWidget(self.tools)

        self.report = ReportPanel(self)
        self.report.findingActivated.connect(self._on_finding_activated)
        self.chat = ChatPanel(self)
        self.chat.requestSent.connect(self._on_request_sent)
        self.chat.accepted.connect(self._on_proposal_accepted)
        self.chat.discarded.connect(self._on_proposal_discarded)
        self.chat.setupRequested.connect(self.action_install_extras)

        # §37.2: die Beispiele sind auch Doku. Die Tour macht sie dazu — der
        # Reiter ist nur sichtbar, solange ein Beispiel offen ist.
        self.tour = TourPanel(self.session, self)
        self.tour.closed.connect(self._remove_tour)

        self.right = QTabWidget(self)
        self.right.addTab(self.report, tr("Prüfbericht"))
        self.right.addTab(self.chat, tr("Chat"))
        # Der Reiter wird einmal angelegt und danach nur noch ein- und
        # ausgeblendet, nie entfernt: ``removeTab`` machte das Panel elternlos,
        # und ein elternloses Widget gehört dem Speicherbereiniger — der es
        # irgendwann aus einem Arbeiter-Thread zerstörte. Ein Absturz ohne
        # Zeile, lange nach der Tour.
        self.right.addTab(self.tour, tr("Tour"))
        self.right.setTabVisible(self.right.indexOf(self.tour), False)

        self.splitter = QSplitter(Qt.Orientation.Horizontal, self)
        self.splitter.addWidget(left)
        self.splitter.addWidget(middle)
        self.splitter.addWidget(self.right)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setStretchFactor(2, 0)
        self.splitter.setSizes([280, 720, 300])

        self.start_screen = StartScreen(self)
        self.start_screen.newRequested.connect(self.action_new)
        self.start_screen.browseRequested.connect(self.action_open)
        self.start_screen.openRequested.connect(self.open_path)
        self.start_screen.fileDropped.connect(self.open_path)
        self.start_screen.forgetRequested.connect(self._forget_recent)
        self.start_screen.manualRequested.connect(self.action_manual)

        self.stack = QStackedWidget(self)
        self.stack.addWidget(self.start_screen)
        self.stack.addWidget(self.splitter)
        self.setCentralWidget(self.stack)

        self.object_tree.selectionChanged.connect(self._on_selection)
        self.object_tree.featureSelected.connect(self._on_feature_selected)
        self.object_tree.operationRequested.connect(self.run_operation)
        self.object_tree.visibilityRequested.connect(self._on_visibility)
        self.object_tree.isolateRequested.connect(self._on_isolate)
        self.parameters.parameterEdited.connect(self._on_parameter_edited)
        self.parameters.addRequested.connect(self.action_add_parameter)
        self.right.setVisible(self.settings.right_panel_visible)

    def _build_status_bar(self) -> None:
        self.measurements = MeasurementLabel(self)
        self.status_message = QLabel("", self)
        self.progress = QProgressBar(self)
        self.progress.setMaximumWidth(180)
        self.progress.setVisible(False)
        self.cancel_button = QPushButton(tr("Abbrechen"), self)
        self.cancel_button.setVisible(False)
        self.cancel_button.clicked.connect(self.session.cancel)
        # Der Knopf gilt für alles, was gerade läuft — auch für die
        # Trennebenensuche, die ihr eigenes Verwerfen hat (§15.6).
        self.cancel_button.clicked.connect(self.session.cancel_split)

        bar = self.statusBar()
        bar.addWidget(self.measurements, 1)
        bar.addPermanentWidget(self.status_message)
        bar.addPermanentWidget(self.progress)
        bar.addPermanentWidget(self.cancel_button)

    def _build_menus(self) -> None:
        file_menu = self._menu(tr("Datei"))
        self._add_action(
            file_menu,
            tr("Neu"),
            QKeySequence.StandardKey.New,
            self.action_new,
            tr("Ein leeres Projekt anlegen — Drucker und Material kommen aus den Einstellungen."),
        )
        self._add_action(
            file_menu,
            tr("Öffnen …"),
            QKeySequence.StandardKey.Open,
            self.action_open,
            tr("Ein gespeichertes Projekt öffnen (.p3d)."),
        )
        self._add_action(
            file_menu,
            tr("Speichern"),
            QKeySequence.StandardKey.Save,
            self.action_save,
            tr("Projekt mit Geometrie, Verlauf und Parametern in eine Datei schreiben."),
        )
        self._add_action(
            file_menu,
            tr("Speichern unter …"),
            QKeySequence.StandardKey.SaveAs,
            self.action_save_as,
            tr("Das Projekt unter einem anderen Namen ablegen."),
        )
        file_menu.addSeparator()
        self._add_action(
            file_menu,
            tr("Modell einfügen …"),
            "Ctrl+I",
            self.action_import,
            tr("Eine Modelldatei laden (STL, 3MF, OBJ, STEP). Eine Baugruppe kommt einzeln an."),
        )
        self._add_action(
            file_menu,
            tr("Modell erzeugen …"),
            "Ctrl+G",
            self.action_generate,
            tr("Aus Text oder Bild ein Mesh erzeugen lassen — braucht ein laufendes ComfyUI."),
        )
        self._add_action(
            file_menu,
            tr("Bausteinkatalog …"),
            "Ctrl+K",
            self.action_catalog,
            tr("Alle Bausteine durchsehen: Mutternfalle, Rastnase, Scharnier und die anderen."),
        )
        self.export_action = self._add_action(
            file_menu,
            tr("Exportieren …"),
            "Ctrl+E",
            self.action_export,
            tr(
                "Die Körper als STL, 3MF, OBJ, PLY oder STEP schreiben — "
                "mit der Prüfung aus dem Bericht davor."
            ),
        )
        self._add_action(
            file_menu,
            tr("Druckeinstellungen …"),
            "Ctrl+P",
            self.action_print_settings,
            tr("Schichten, Temperaturen, Farbe und Stützen einstellen — und slicen lassen."),
        )
        self._add_action(
            file_menu,
            tr("G-Code gegenprüfen …"),
            None,
            self.action_check_gcode,
            tr("Eine Datei aus dem Slicer lesen und ihre Zahlen neben die eigenen stellen."),
        )
        file_menu.addSeparator()
        self._add_action(
            file_menu,
            tr("Beenden"),
            QKeySequence.StandardKey.Quit,
            self.close,
            tr("Formwerk schließen. Ungesichertes wird vorher erfragt."),
        )

        edit_menu = self._menu(tr("Bearbeiten"))
        self._add_action(
            edit_menu,
            tr("Befehlspalette …"),
            "Ctrl+Shift+P",
            self.action_command_palette,
            tr("Jede Operation über ihren Namen finden, ohne durch die Menüs zu gehen."),
        )
        self._add_action(
            edit_menu,
            tr("Parameter anlegen …"),
            None,
            self.action_add_parameter,
            tr("Ein Maß benennen, auf das Operationen und Skizzen mit @name verweisen können."),
        )
        self.auto_split_action = self._add_action(
            edit_menu,
            tr("Automatisch teilen …"),
            None,
            self.action_auto_split,
            tr(
                "Ein zu großes Teil zerschneiden, bis jedes Stück auf die Platte passt — "
                "mit Passstiften in jeder Schnittfläche."
            ),
        )
        self._add_action(
            edit_menu,
            tr("Material kalibrieren …"),
            None,
            self.action_calibrate,
            tr(
                "Das gemessene Spiel eintragen. Es gilt danach für jede Passung, "
                "auch in älteren Projekten."
            ),
        )
        self.variants_action = self._add_action(
            edit_menu,
            tr("Varianten erzeugen …"),
            None,
            self.action_variants,
            tr(
                "Dasselbe Teil mehrfach mit gestaffelten Werten exportieren, "
                "statt von Hand zu ändern."
            ),
        )
        self._add_action(
            edit_menu,
            tr("Einstellungen …"),
            "Ctrl+,",
            self.action_settings,
            tr("Sprache, Anzeigeeinheit, Thema, Navigation und die Vorgaben für neue Projekte."),
        )
        self._add_action(
            edit_menu,
            tr("Zugang zum Sprachmodell …"),
            None,
            self.action_llm_key,
            tr(
                "Schlüssel für den Chat hinterlegen. Er landet im Schlüsselbund, "
                "nie in der Projektdatei."
            ),
        )
        edit_menu.addSeparator()
        self.undo_action = self._add_action(
            edit_menu,
            tr("Rückgängig"),
            QKeySequence.StandardKey.Undo,
            self.action_undo,
            tr("Den letzten Schritt zurücknehmen — auch einen Vorschlag des Chats, ganz."),
        )
        self.redo_action = self._add_action(
            edit_menu,
            tr("Wiederholen"),
            QKeySequence.StandardKey.Redo,
            self.action_redo,
            tr("Einen zurückgenommenen Schritt wieder anwenden."),
        )

        # Alles darunter kommt aus dem Register (§10). Der Hinweis ist die
        # Beschreibung der Operation und steht deshalb an beiden Stellen: in der
        # Statusleiste beim Durchgehen und als Tooltip beim Zögern.
        sections = {section.category: section for section in menu_tree()}
        for title, categories in MENU_GROUPS:
            present = [sections[name] for name in categories if name in sections]
            if not present:
                continue
            group = self._menu(str(title))
            for section in present:
                # Eine Gruppe aus einer Kategorie braucht kein Untermenü — es
                # hieße genauso wie das Menü darüber.
                target = group
                if len(present) > 1:
                    # Mit dem Fenster als Elternteil erzeugt, nicht über
                    # ``addMenu(titel)``: sonst hält nichts auf der Python-Seite
                    # das Untermenü, und sein C++-Objekt wird eingesammelt,
                    # während die Leiste es noch zeigt.
                    target = QMenu(str(section.title), self)
                    target.setToolTipsVisible(True)
                    group.addMenu(target)
                    self._menus.append(target)
                subgroups: dict[str, QMenu] = {}
                for spec in section.entries:
                    place = self._subgroup_for(spec, target, subgroups)
                    self._op_actions[spec.name] = self._operation_action(place, spec)

        # Was das Register kennt und diese Tabelle nicht, bekommt sein eigenes
        # Menü: eine neue Kategorie soll auftauchen, nicht verschwinden.
        grouped = {name for _title, names in MENU_GROUPS for name in names}
        for section in menu_tree():
            if section.category in grouped:
                continue
            menu = self._menu(str(section.title))
            for spec in section.entries:
                self._op_actions[spec.name] = self._operation_action(menu, spec)

        view_menu = self._menu(tr("Ansicht"))
        self._add_action(
            view_menu,
            tr("Alles einpassen"),
            "Home",
            self.viewport.reset_camera,
            tr("Rückt die Kamera so, dass die ganze Szene ins Bild passt."),
        )
        self._add_action(
            view_menu,
            tr("Rechten Bereich zeigen"),
            "F9",
            self.action_toggle_right,
            tr("Verlauf, Parameter und Chat ein- oder ausblenden."),
        )
        view_menu.addSeparator()

        # Sechs Blöcke ohne Überschrift waren dreiundzwanzig Zeilen, durch
        # Trennstriche gegliedert — eine Liste, die man absucht (Konzept P15
        # §5). Was zusammengehört, bekommt jetzt seinen Namen und seine Ebene.
        display_menu = self._submenu(view_menu, tr("Darstellung"))
        for mode, label, shortcut, hint in (
            ("solid", tr("Massiv"), "1", tr("Die Oberfläche, wie sie gedruckt wird.")),
            (
                "solid_edges",
                tr("Massiv mit Kanten"),
                "2",
                tr("Dazu die Dreieckskanten — zeigt, wie fein das Netz ist."),
            ),
            (
                "wireframe",
                tr("Drahtgitter"),
                "3",
                tr("Nur die Kanten. Lässt durch das Teil hindurchsehen."),
            ),
            (
                "transparent",
                tr("Transparent"),
                "4",
                tr("Durchscheinend — für Hohlräume und Teile, die ineinandergreifen."),
            ),
        ):
            self._add_action(
                display_menu,
                label,
                shortcut,
                lambda checked=False, key=mode: self.viewport.set_display_mode(key),
                hint,
            )
        display_menu.addSeparator()
        for shading, label, hint in (
            (
                "flat",
                tr("Flache Schattierung"),
                tr("Jedes Dreieck für sich — die wahre Form, Facetten inklusive."),
            ),
            (
                "smooth",
                tr("Weiche Schattierung"),
                tr("Über die Kanten hinweg gemittelt. Schöner, aber beschönigend."),
            ),
        ):
            self._add_action(
                display_menu,
                label,
                None,
                lambda checked=False, key=shading: self.viewport.set_shading(key),
                hint,
            )
        display_menu.addSeparator()
        for projection, label, shortcut, hint in (
            (
                "perspective",
                tr("Perspektivisch"),
                "5",
                tr("Wie das Auge sieht: Fernes wird kleiner."),
            ),
            (
                "orthographic",
                tr("Orthografisch"),
                "6",
                tr("Ohne Fluchtpunkt — gleich lange Kanten sehen gleich lang aus. Zum Messen."),
            ),
        ):
            self._add_action(
                display_menu,
                label,
                shortcut,
                lambda checked=False, key=projection: self.viewport.set_projection(key),
                hint,
            )

        camera_menu = self._submenu(view_menu, tr("Kamera"))
        standpoint = tr("Kamera auf diesen Standpunkt setzen.")
        for name, label, shortcut in (
            ("iso", tr("Isometrisch"), "Ctrl+0"),
            ("front", tr("Vorne"), "Ctrl+1"),
            ("back", tr("Hinten"), "Ctrl+2"),
            ("left", tr("Links"), "Ctrl+3"),
            ("right", tr("Rechts"), "Ctrl+4"),
            ("top", tr("Oben"), "Ctrl+5"),
            ("bottom", tr("Unten"), "Ctrl+6"),
        ):
            self._add_action(
                camera_menu,
                label,
                shortcut,
                lambda checked=False, key=name: self.viewport.view_from(key),
                standpoint,
            )
        view_menu.addSeparator()
        for theme, label, hint in (
            ("dark", tr("Dunkles Thema"), tr("Helle Geometrie auf dunklem Grund.")),
            ("light", tr("Helles Thema"), tr("Dunkle Geometrie auf hellem Grund.")),
        ):
            self._add_action(
                view_menu,
                label,
                None,
                lambda checked=False, key=theme: self.action_theme(key),
                hint,
            )
        navigation_menu = self._submenu(view_menu, tr("Navigation"))
        for scheme, label, hint in (
            (
                "slicer",
                tr("Navigation: Cura"),
                # Der Hinweis stand hier andersherum, als das Schema arbeitet:
                # „links drehen, rechts schieben" beschreibt Bambu und Prusa,
                # nicht die Vorgabe aus §2.9.
                tr("Links wählt, rechts dreht, Umschalt und Ziehen schiebt."),
            ),
            (
                "orbit",
                tr("Navigation: Bambu, Orca, Prusa"),
                tr("Links dreht, rechts schiebt — die verbreitetste Aufteilung."),
            ),
            ("cad", tr("Navigation: CAD"), tr("Wie in einem CAD-Programm: Mittlere Taste dreht.")),
            ("blender", tr("Navigation: Blender"), tr("Wie in Blender.")),
        ):
            self._add_action(
                navigation_menu,
                label,
                None,
                lambda checked=False, key=scheme: self.action_navigation(key),
                hint,
            )

        help_menu = self._menu(tr("Hilfe"))
        self._add_action(
            help_menu,
            tr("Handbuch …"),
            QKeySequence.StandardKey.HelpContents,
            self.action_manual,
            tr("Jede Operation mit ihren Werten, nach Bereichen sortiert."),
        )
        help_menu.addSeparator()
        self._add_action(
            help_menu,
            tr("Zusätzliche Programme …"),
            None,
            self.action_install_extras,
            tr("Was Formwerk außerdem benutzen kann, wo es liegt und wie es dazukommt."),
        )
        self._add_action(
            help_menu,
            tr("Erste Schritte …"),
            None,
            self.action_first_run,
            tr("Sprache, Drucker, Material und die externen Programme noch einmal einstellen."),
        )
        self._add_action(
            help_menu,
            tr("Fehlerbericht erstellen …"),
            None,
            self.action_report,
            tr("Einen Ordner mit Protokoll und Umgebung anlegen. Verschickt wird nichts."),
        )
        help_menu.addSeparator()
        self._add_action(
            help_menu,
            tr("Über Formwerk"),
            None,
            self.action_about,
            tr("Version, Rechteinhaber und die verwendeten Fremdbibliotheken."),
        )

        toolbar = QToolBar(tr("Werkzeuge"), self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)
        # Zeichen neben der Beschriftung, nicht statt ihr (Regel 18) — vier
        # gleich aussehende Textknöpfe sind dasselbe Problem, das die
        # Werkzeugzeile unter dem Viewport längst gelöst hat.
        toolbar.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        for symbol, label, slot in (
            ("new", tr("Neu"), self.action_new),
            ("open", tr("Öffnen"), self.action_open),
            ("save", tr("Speichern"), self.action_save),
            ("import", tr("Modell einfügen"), self.action_import),
        ):
            action = QAction(icon(symbol, toolbar), label, self)
            action.triggered.connect(slot)
            toolbar.addAction(action)

    def _menu(self, title: str) -> QMenu:
        """Ein Menü der Leiste — festgehalten, damit es nicht eingesammelt wird."""
        menu = self.menuBar().addMenu(title)
        menu.setToolTipsVisible(True)
        self._menus.append(menu)
        return menu

    def _submenu(self, parent: QMenu, title: str) -> QMenu:
        """Eine Zwischenebene. Elternteil ist das Fenster, nicht das Menü —
        sonst hält nichts auf der Python-Seite das Untermenü fest, und sein
        C++-Objekt wird eingesammelt, während die Leiste es noch zeigt.
        """
        submenu = QMenu(title, self)
        submenu.setToolTipsVisible(True)
        parent.addMenu(submenu)
        self._menus.append(submenu)
        return submenu

    def _subgroup_for(self, spec: OperationSpec, menu: QMenu, made: dict[str, QMenu]) -> QMenu:
        """Das Menü, in das dieser Eintrag gehört — mit einer Zwischenebene,
        wo die Kategorie sonst zu lang würde (Konzept P15 §5).

        Betrifft heute die Bausteine: sechzehn Einfügungen flach untereinander
        sind eine Liste, die man absucht, kein Menü, das man liest. Die
        Gliederung ist nicht erfunden — es ist dieselbe Gruppe, nach der der
        Katalog seine Kacheln ordnet (``parts.GROUPS``). Was keine Gruppe hat,
        bleibt oben stehen: ``create_lid`` ist kein Baustein aus der
        Bibliothek.
        """
        from app.core.knowledge.parts import GROUPS, PARTS
        from app.core.knowledge.parts.ops import op_name

        group = next(
            (part.group for part in PARTS.all() if op_name(part.name) == spec.name),
            None,
        )
        if group is None or group not in GROUPS:
            return menu
        if group not in made:
            # Elternteil ist das Fenster, nicht das Menü — siehe die
            # Begründung eine Ebene höher.
            submenu = QMenu(str(GROUPS[group]), self)
            submenu.setToolTipsVisible(True)
            menu.addMenu(submenu)
            self._menus.append(submenu)
            made[group] = submenu
        return made[group]

    def _operation_action(self, menu: Any, spec: OperationSpec) -> QAction:
        """Ein Menüeintrag für eine Operation, überall gleich gebaut."""
        action = QAction(str(spec.title), self)
        if spec.shortcut:
            action.setShortcut(QKeySequence(spec.shortcut))
        action.setStatusTip(str(spec.doc))
        action.setToolTip(str(spec.doc))
        # Eine Operation mit Skizzenfeld führt in den Zeichenmodus statt in
        # einen Dialog mit einem Feld, das man erst aufklappen muss (§30.1
        # Stufe zwei). Derselbe Eintrag, derselbe Weg dahinter — nur der
        # erste Schritt ist das Zeichnen und nicht das Ausfüllen.
        if _has_sketch_param(spec):
            action.triggered.connect(lambda _checked=False, name=spec.name: self.start_sketch(name))
        else:
            action.triggered.connect(lambda _checked=False, entry=spec: self.run_operation(entry))
        menu.addAction(action)
        return action

    def _add_action(
        self, menu: Any, label: str, shortcut: Any, slot: Any, hint: str = ""
    ) -> QAction:
        """Ein Menüeintrag mit dem Satz, der sagt, was er tut.

        Der Hinweis steht an zwei Stellen, weil ihn zwei Arten von Leuten
        suchen: in der Statusleiste, wo er beim Durchgehen mitläuft, und als
        Tooltip, wo er beim Zögern erscheint. Ohne beides ist ein Menü mit
        vierzehn Einträgen eine Liste von Vermutungen.
        """
        action = QAction(label, self)
        if shortcut is not None:
            action.setShortcut(
                shortcut
                if isinstance(shortcut, QKeySequence.StandardKey)
                else QKeySequence(shortcut)
            )
        if hint:
            action.setStatusTip(hint)
            action.setToolTip(hint)
        action.triggered.connect(slot)
        menu.addAction(action)
        return action

    def _update_actions(self) -> None:
        """Was jetzt geht, sieht man, statt es zu erfahren (§2.6).

        Vorher war jeder der siebzig Einträge immer anklickbar, auch bei leerer
        Szene; wer einen wählte, bekam ein modales Fenster mit dem Hinweis, dass
        er vorher etwas hätte auswählen sollen. Eine Sackgasse als Antwort auf
        eine Frage, die das Menü selbst beantworten kann.
        """
        result = self.session.last_result
        objects = len(result.scene.objects) if result else 0
        chosen = len(self.object_tree.selected_objects())

        for name, action in self._op_actions.items():
            spec = REGISTRY.get(name)
            if spec.takes_whole_scene:
                action.setEnabled(objects > 0)
            elif spec.consumes:
                action.setEnabled(chosen >= spec.consumes)
            else:
                action.setEnabled(True)

        self.undo_action.setEnabled(self.session.history.can_undo)
        self.redo_action.setEnabled(self.session.history.can_redo)
        # Dieselbe Regel für die zwei Einträge, die keine Operationen sind und
        # trotzdem einen Körper brauchen: ausgegraut statt einer modalen
        # Sackgasse nach dem Klick.
        self.auto_split_action.setEnabled(chosen >= 1)
        self.variants_action.setEnabled(objects > 0)
        self.export_action.setEnabled(objects > 0)

    def _connect_session(self) -> None:
        self.session.sceneChanged.connect(self._on_scene)
        self.session.projectChanged.connect(self._on_project)
        self.session.progressChanged.connect(self._on_progress)
        self.session.busyChanged.connect(self._on_busy)
        self.session.askRequested.connect(self._on_ask)
        self.session.failed.connect(self._on_error)
        self.session.proposalReady.connect(self._on_proposal)
        self.session.agentBusyChanged.connect(self._on_agent_busy)
        self.session.splitBusyChanged.connect(self._on_split_busy)
        self._refresh_chat_availability()

    # --- actions ----------------------------------------------------------------

    def action_new(self) -> None:
        if not self._may_discard():
            return
        self.session.start_new(self.settings.printer, self.settings.material)
        self._remove_tour()
        self._show_start_screen(False)

    def action_open(self) -> None:
        name, _filter = QFileDialog.getOpenFileName(self, tr("Projekt öffnen"), "", PROJECT_FILTER)
        if name:
            self.open_path(Path(name))

    def _forget_recent(self, path: Path) -> None:
        """Einen Eintrag aus „Zuletzt geöffnet" nehmen — die Datei bleibt."""
        self.settings.recent = [entry for entry in self.settings.recent if entry != str(path)]
        save_settings(self.settings)
        self.start_screen.show_recent(self.settings.existing_recent())

    def _may_discard(self) -> bool:
        """Fragt, bevor ein geändertes Projekt weggeworfen wird.

        Kein Widerspruch zu Regel 19: die verbietet Rückfragen vor
        rücknehmbaren Handlungen, und ein verworfenes Dokument holt kein Undo
        zurück. Die Frage bietet deshalb das Speichern gleich mit an, statt
        den Nutzer zurückzuschicken.
        """
        if not self.session.modified:
            return True
        answer = confirm_unsaved(self.session.title, self)
        if answer == "cancel":
            return False
        if answer == "save":
            self.action_save()
            # Wer den Dateidialog abbricht, hat nicht gespeichert — und will
            # dann ganz sicher nicht, dass die Arbeit trotzdem verschwindet.
            return not self.session.modified
        return True

    def open_path(self, path: Path) -> None:
        """Ein Einstiegspunkt für Menü, Zuletzt-Liste und Drag and Drop."""
        if path.suffix.lower() == PROJECT_SUFFIX and not self._may_discard():
            return
        try:
            if path.suffix.lower() == PROJECT_SUFFIX:
                self.session.open_project(path)
                self.settings.remember(path)
                save_settings(self.settings)
                self._offer_recovery(path)
                self._offer_tour(path)
            else:
                if self.stack.currentWidget() is self.start_screen:
                    self.session.start_new(self.settings.printer, self.settings.material)
                self.session.import_model(path)
        except AppError as error:
            show_error(error, self)
            return
        self._show_start_screen(False)

    def action_save(self) -> None:
        if self.session.path is None:
            self.action_save_as()
            return
        self._save_to(self.session.path)

    def action_save_as(self) -> None:
        name, _filter = QFileDialog.getSaveFileName(
            self, tr("Projekt speichern"), "", PROJECT_FILTER
        )
        if name:
            self._save_to(Path(name))

    def _save_to(self, path: Path) -> None:
        try:
            saved = self.session.save_project(path)
        except AppError as error:
            show_error(error, self)
            return
        self.settings.remember(saved)
        save_settings(self.settings)
        self.status_message.setText(tr("Gespeichert"))

    def action_import(self) -> None:
        name, _filter = QFileDialog.getOpenFileName(self, tr("Modell einfügen"), "", MODEL_FILTER)
        if name:
            self.session.import_model(Path(name))

    def action_generate(self) -> None:
        """Weg 3 (§2.2): ein Satz oder ein Bild wird ein Körper in der Szene."""
        dialog = GenerateDialog(parent=self)
        if dialog.exec() != QDialog.DialogCode.Accepted or dialog.result_mesh is None:
            return
        self.session.add_generated(dialog.result_mesh)

    def action_auto_split(self, object_id: ObjectId | None = None) -> None:
        """§25: das gewählte Teil teilen, bis es passt, und die Nähte
        verstiften (§14).

        Der Körper lässt sich benennen, damit auch der Fehlerdialog „Modell
        teilen" anbieten kann — er weiß, welches Teil nicht passte.
        """
        object_id = object_id or self.object_tree.selected()
        if not object_id:
            QMessageBox.information(
                self, tr("Automatisch teilen"), tr("Bitte zuerst ein Objekt auswählen.")
            )
            return

        # Kein Wartezeiger mehr: die Suche prüft Kandidatenebene für
        # Kandidatenebene und dauert an einem großen Körper Sekunden bis
        # Minuten — §2.8 verlangt dafür Fortschritt und Abbrechen, kein
        # eingefrorenes Fenster mit Ankündigung.
        self.session.split_async(object_id, self._split_done)

    def _split_done(self, applied: Any) -> None:
        self.report.add_findings(applied.findings)
        if applied.transaction is None:
            self.status_message.setText(tr("Dieses Objekt passt bereits auf das Bett."))
            return
        self.status_message.setText(
            f"{tr('Geteilt')}: {len(applied.object_ids)} · {len(applied.fits)} {tr('Passungen')}"
        )

    def action_undo(self) -> None:
        self.session.undo()

    def action_redo(self) -> None:
        self.session.redo()

    def action_toggle_right(self) -> None:
        visible = not self.settings.right_panel_visible
        self.right.setVisible(visible)
        self.settings.right_panel_visible = visible
        save_settings(self.settings)

    def action_variants(self) -> None:
        """§28.3: derselbe Stapel mit einer gestuften Zahl, nebeneinander auf
        einer Platte.
        """
        VariantsDialog(self.session, self).exec()

    def action_install_extras(self) -> None:
        """§36: was fehlt, wofür es da ist, und ein Knopf, der es holt."""
        InstallDialog(self).exec()

    def action_manual(self) -> None:
        """Das Handbuch — ein Fenster, kein Dialog.

        Es bleibt offen, während gearbeitet wird; ein Handbuch, das man zum
        Weiterarbeiten schließen muss, wird kein zweites Mal geöffnet. Und es
        wird wiederverwendet, damit nicht bei jedem Aufruf eines mehr auf dem
        Bildschirm steht.
        """
        window = self._manual
        if window is None:
            window = ManualWindow(self)
            self._manual = window
        window.show()
        window.raise_()
        window.activateWindow()

    def action_about(self) -> None:
        AboutDialog(self).exec()

    def action_print_settings(self) -> None:
        """§29: die Einstellungen, mit denen gedruckt wird — hier, nicht im
        anderen Programm.

        Der Dialog nimmt die Schichtanalyse mit, wo eine vorliegt: die
        Vorschläge über Stützen, Haftung und Mindestschichtzeit hängen an der
        Geometrie und nicht am Material allein.
        """
        # Eine knappe halbe Sekunde, die zum größten Teil auf die Suche nach dem
        # Slicer geht — unter der Grenze aus §2.8, aber nicht unter der, ab der
        # ein Zeiger dazugehört.
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            dialog = PrintSettingsDialog(
                self.session, self.settings, self, slice_result=self._current_slice()
            )
        finally:
            QApplication.restoreOverrideCursor()
        dialog.sliced.connect(self._gcode_returned)
        dialog.exec()

        # Die Einstellungen gehören zum Projekt, die Stufe und die Slicer-Wahl
        # zur Anwendung (§29). Getrennt gespeichert, weil ein Projekt auf einem
        # anderen Rechner geöffnet wird, wo ein anderer Slicer liegt.
        self.session.set_print_settings(dialog.settings)
        self.settings.print_quality = dialog.settings.quality
        save_settings(self.settings)

    def _current_slice(self) -> SliceResult | None:
        """Die Schichtanalyse des gewählten Körpers, **wenn sie schon vorliegt**.

        Der Dialog beschreibt genau diesen Vertrag: „die Schichtanalyse, wenn
        das Fenster schon eine hat". Sie hier zu erzwingen hieß, den Weg zu den
        Druckeinstellungen an einer Rechnung aufzuhalten, die niemand bestellt
        hat — ohne sie bleiben die Vorschläge aus Material und Maschine (§29).
        """
        object_id = self.object_tree.selected()
        if object_id is None:
            return None
        return self._slice_of(object_id)

    def _gcode_returned(self, outcome: SliceOutcome) -> None:
        """Was der Slicer gemessen hat, geht in den Prüfbericht — als gemessen
        markiert, neben der Schätzung, nie an ihrer Stelle (Regel 14)."""
        self.report.add_findings(outcome.findings)
        self._focus_report()
        self.status_message.setText(f"{tr('Geslicet')}: {outcome.gcode_path.name}")

    def action_check_gcode(self) -> None:
        """§28.1: eine geslicete Datei zurücklesen und gegen die Schätzung
        halten.

        Die gemessenen Zahlen landen als gemessen markiert im Prüfbericht; die
        interne Schätzung bleibt, wo sie war. Nichts wird still ersetzt (§22.5).
        """
        name, _filter = QFileDialog.getOpenFileName(
            self, tr("G-Code gegenprüfen"), "", GCODE_FILTER
        )
        if not name:
            return

        metrics = gcode.parse(Path(name).read_text(encoding="utf-8", errors="replace"))
        findings = gcode.findings_for(metrics)

        self.report.add_findings(findings)
        self._focus_report()
        self.status_message.setText(
            f"{tr('G-Code gelesen')}: {metrics.slicer or tr('unbekannter Slicer')}"
        )

        # Die Gegenprobe zum Stützvolumen braucht die eigene Schätzung. Sie
        # wird geholt, nicht erzwungen: liegt sie noch nicht vor, rechnet der
        # Arbeiter sie und der Vergleich kommt nach — die gemessenen Zahlen
        # stehen längst im Bericht (§22.5).
        object_id = self.object_tree.selected()
        if object_id is not None and metrics.support_mm3 is not None:
            measured = metrics.support_mm3
            self._slice_of(
                object_id,
                lambda estimate, measured=measured: self._compare_support(estimate, measured),
            )

    def _compare_support(self, estimate: SliceResult | None, measured: float) -> None:
        """Geschätztes gegen gemessenes Stützvolumen (§22.5, Regel 14)."""
        if estimate is None:
            return
        self.report.add_findings(
            gcode.compare(estimate.support_volume, measured, "support").findings
        )

    def action_export(self) -> None:
        """§29: die Körper als Datei — der Schritt, mit dem jeder der drei
        Wege aus §2.2 endet.

        Der Schreiber stand seit P2 im Kern und war, wie vorher schon auf der
        Kommandozeile, aus dem Fenster nicht erreichbar: der einzige Weg zu
        einer Datei führte über den Slicer (Strg+P), und der setzt einen
        installierten Slicer voraus. Exportiert wird die Auswahl, ohne
        Auswahl alles; ein 3MF wird **eine** Datei mit allen Körpern (§20),
        jedes andere Format eine Datei je Körper nach dem Namensschema.
        Die Prüfung davor ist ein Bericht, keine Sperre (§29) — ihre Befunde
        landen im Prüfbericht.
        """
        result = self.session.last_result
        if result is None or not result.scene.objects:
            return
        chosen = self.object_tree.selected_objects()
        objects = [
            entry
            for object_id, entry in result.scene.objects.items()
            if not chosen or object_id in chosen
        ]

        stem = safe_name(Path(self.session.title.rstrip("*")).stem, "projekt")
        filters = ";;".join(
            (
                "STL (*.stl)",
                "3MF (*.3mf)",
                "OBJ (*.obj)",
                "PLY (*.ply)",
                "STEP (*.step)",
            )
        )
        name, chosen_filter = QFileDialog.getSaveFileName(
            self, tr("Exportieren"), f"{stem}.stl", filters
        )
        if not name:
            return
        target = Path(name)
        export_format: ExportFormat = _format_of(target, chosen_filter)

        sources = self.session.project.document.sources
        try:
            if export_format == "3mf" and len(objects) > 1:
                # Eine Baugruppe bleibt eine Datei: der Slicer bekommt einen
                # Druckauftrag, keine Handvoll Teile (§20).
                written_path, findings = write_assembly(
                    objects,
                    target.parent,
                    project_name=target.stem,
                    profile=self.session.profile,
                    sources=sources,
                )
                written = [written_path]
            else:
                # Ein fester Name für einen Körper; bei mehreren zählt das
                # Namensschema aus §29, damit auf der Platte lesbar bleibt,
                # welches Teil welches ist. Geschweifte Klammern im Namen
                # sind Zeichen, keine Platzhalter — ``format`` sähe das anders.
                fixed = target.stem.replace("{", "{{").replace("}", "}}")
                scheme = fixed if len(objects) == 1 else None
                plan = plan_export(
                    objects,
                    project_name=target.stem,
                    profile=self.session.profile,
                    export_format=export_format,
                    scheme=scheme,
                    sources=sources,
                )
                findings = list(plan.findings)
                written = write_plan(plan, target.parent, export_format)
        except AppError as error:
            show_error(error, self)
            return

        if findings:
            self.report.add_findings(list(findings))
            self._focus_report()
        self.status_message.setText(
            f"{tr('Exportiert')}: {written[0].name}"
            if len(written) == 1
            else f"{tr('Exportiert')}: {len(written)} {tr('Dateien')} → {target.parent}"
        )

    def action_catalog(self) -> None:
        """§24.3: die Bibliothek, die man sehen kann. Einen Baustein zu wählen
        führt seine Operation aus.
        """
        catalog = PartCatalog(self)
        if catalog.exec() != PartCatalog.DialogCode.Accepted:
            return
        name = catalog.chosen()
        if name:
            self.run_operation(REGISTRY.get(part_op_name(name)))

    def action_report(self) -> None:
        """§37.2: ein Bericht lässt sich erstellen, ohne dass etwas schiefging."""
        dialog = ErrorReportDialog(
            summary=tr("Vom Nutzer angelegter Bericht."),
            project=self.session.path,
            parent=self,
        )
        dialog.exec()

    def action_calibrate(self) -> None:
        """§28.3: gemessene Werte ins Materialprofil, und alles folgt."""
        material = self.session.project.document.material or self.session.profile.material.id
        dialog = CalibrationDialog(material, self)
        if dialog.exec() != CalibrationDialog.DialogCode.Accepted:
            return
        try:
            calibrated = calibration.apply(dialog.measured())
        except AppError as error:
            show_error(error, self)
            return
        self.status_message.setText(
            f"{tr('Kalibriert')}: {calibrated.id} · {tr('Spiel')} {calibrated.clearance:.2f} mm"
        )
        # Toleranzen sind Verweise (§12), die Szene muss also neu gebaut werden.
        self.session.evaluate_async()

    def action_llm_key(self) -> None:
        """§27: der eigene Schlüssel des Nutzers, in den Schlüsselbund, und der
        Chat wacht auf.
        """
        if KeyDialog(parent=self).exec() != KeyDialog.DialogCode.Accepted:
            return
        self.session.set_agent_backend(None)
        self._refresh_chat_availability(probe_local=True)

    def _refresh_chat_availability(self, probe_local: bool = False) -> None:
        """Der eine Ort, an dem der Chat-Zustand gelesen wird.

        Vorher stand derselbe Dreizeiler an drei Stellen. Dazu die Prüfung aus
        §27: wacht der Chat über das lokale Modell auf, fragt ein Arbeiter die
        Modellgröße ab — im Hintergrund, denn ein Start, der auf einen
        HTTP-Aufruf wartet, wäre der Fehler der Update-Prüfung noch einmal.

        ``probe_local`` gilt nur für Einrichtungs-Anlässe (erster Start,
        Schlüsseldialog): der stille Fensterbau startet keinen Arbeiter, dessen
        Leben an einer HTTP-Antwort hängt — Tests und Screenshot-Werkzeuge
        bauen Fenster und warten auf keinen. Und einmal bei der Einrichtung
        gesagt ist genug — bei jedem Start wäre es Nörgeln (§27).
        """
        backend = self.session.agent_backend
        self.chat.set_available(
            backend is not None, f"{backend.id}:{backend.model}" if backend else ""
        )
        self.chat.set_notice("")
        if not probe_local or backend is None or backend.id != "ollama":
            return
        worker = _OllamaSizeWorker(backend.model)
        worker.done.connect(self._ollama_size_answered)
        worker.finished.connect(lambda: setattr(self, "_ollama_size_worker", None))
        self._ollama_size_worker = worker
        worker.start()

    def _ollama_size_answered(self, warning: Any) -> None:
        if warning is not None:
            self.chat.set_notice(str(warning))

    def action_settings(self) -> None:
        """§19.3, §38: alles, was die Anwendung sich merkt, an einer Stelle.

        Was sofort wirken kann, wirkt sofort — Thema, Einheit, Navigation und
        die Farben der Differenzansicht. Die Sprache kann es nicht, und der
        Dialog sagt das, statt es den Nutzer herausfinden zu lassen.
        """
        dialog = SettingsDialog(self.settings, self)
        if dialog.exec() != SettingsDialog.DialogCode.Accepted:
            return
        dialog.apply_to(self.settings)
        save_settings(self.settings)
        self._apply_settings()

    def _apply_settings(self) -> None:
        """Trägt die Einstellungen dorthin, wo sie wirken."""
        application = QApplication.instance()
        if application is not None:
            apply_theme(application, self.settings.theme)  # type: ignore[arg-type]
        self.viewport.set_theme(self.settings.theme)
        self.viewport.set_navigation(self.settings.navigation)  # type: ignore[arg-type]
        self.viewport.set_difference_palette(self.settings.diff_palette)  # type: ignore[arg-type]
        self.set_display_unit(self.settings.display_unit)

    def set_display_unit(self, unit: str) -> None:
        """§19.3: Millimeter oder Zoll — in der Anzeige, nie im Kern.

        Die Einstellung gab es seit P0 und niemanden, der sie las. Jetzt liest
        sie, wer Längen zeigt: Statusleiste, Objektbaum und die Maße der
        Auswahl.
        """
        self.measurements.set_unit(unit)  # type: ignore[arg-type]
        self.object_tree.set_unit(unit)  # type: ignore[arg-type]
        self._on_selection(self.object_tree.selected())

    def window_commands(self) -> dict[str, tuple[str, str, Any]]:
        """Was die Palette außer den Operationen kennen muss (§2.6, §19.2).

        „Alles aus dem Register" war zu wenig: Speichern, das Handbuch, die
        Darstellungsarten und die sieben Ansichtswerkzeuge stehen nicht im
        Register, und die Palette soll der Universalzugang sein. Kennung,
        Titel, Kürzel und was zu tun ist.
        """
        commands: dict[str, tuple[str, str, Any]] = {
            "file.new": (tr("Neu"), "Ctrl+N", self.action_new),
            "file.open": (tr("Öffnen …"), "Ctrl+O", self.action_open),
            "file.save": (tr("Speichern"), "Ctrl+S", self.action_save),
            "file.import": (tr("Modell einfügen …"), "Ctrl+I", self.action_import),
            "file.export": (tr("Exportieren …"), "Ctrl+E", self.action_export),
            "file.print_settings": (
                tr("Druckeinstellungen …"),
                "Ctrl+P",
                self.action_print_settings,
            ),
            "file.catalog": (tr("Bausteinkatalog …"), "Ctrl+K", self.action_catalog),
            "edit.settings": (tr("Einstellungen …"), "Ctrl+,", self.action_settings),
            "edit.undo": (tr("Rückgängig"), "Ctrl+Z", self.action_undo),
            "edit.redo": (tr("Wiederholen"), "Ctrl+Y", self.action_redo),
            "edit.add_parameter": (
                tr("Parameter anlegen …"),
                "",
                self.action_add_parameter,
            ),
            "edit.auto_split": (tr("Automatisch teilen …"), "", self.action_auto_split),
            "view.fit": (tr("Alles einpassen"), "Home", self.viewport.reset_camera),
            "view.toggle_right": (tr("Rechten Bereich zeigen"), "F9", self.action_toggle_right),
            "help.manual": (tr("Handbuch …"), "F1", self.action_manual),
        }
        for key, title in self.tools.tool_titles().items():
            commands[f"tool.{key}"] = (
                f"{strip_title()}: {title}",
                "",
                lambda name=key: self.tools.toggle(name),
            )
        return commands

    def selected_feature_kind(self) -> str | None:
        """Die Art des gerade ausgewählten Merkmals — ``hole``, ``face`` und
        so fort, oder ``None``.

        Sie entscheidet, was die Befehlspalette zuerst zeigt (Konzept P15 §5,
        E13). Dieselbe Auskunft, aus der auch das Kontextmenü gebaut wird, nur
        an der anderen Stelle gefragt.
        """
        feature_id = self.object_tree.selected_feature()
        selected = self.object_tree.selected()
        result = self.session.last_result
        if not feature_id or selected is None or result is None:
            return None
        entry = result.scene.objects.get(selected)
        feature = entry.features.get(feature_id) if entry else None
        return feature.kind if feature is not None else None

    # --- Skizzenmodus (§30.1 Stufe zwei) ----------------------------------------

    def _escape(self) -> None:
        """Escape verlässt, was gerade offen ist — ein Werkzeug oder die Skizze.

        Die Skizze zuerst: sie liegt vor der Ansicht, und wer zeichnet, meint
        mit Escape sie und nicht eine Leiste darunter. Verworfen wird dabei
        nichts Gerechnetes — die Skizze war noch keine Operation.
        """
        if self._sketch_panel is not None:
            self.finish_sketch(keep=False)
            return
        self.tools.close_tool()

    def sketching(self) -> bool:
        """Ob gerade gezeichnet wird statt betrachtet."""
        return self._sketch_panel is not None

    def start_sketch(self, op_name: str, text: str = "") -> None:
        """In den Skizzenmodus wechseln, für die Operation, die sie verbraucht.

        Der mittlere Bereich zeigt die Zeichenfläche statt der Ansicht; die
        Werkzeugzeile darunter bleibt, wo sie ist, und trägt Fertig und
        Verwerfen. Kein Fenster darüber, kein modaler Zustand — Escape kommt
        hier heraus wie aus jedem anderen Werkzeug (§2.1).

        Die Skizze bleibt dabei, was §30.1 aus ihr macht: der Parameterwert
        einer Operation. Am Ende steht derselbe Text, den auch der Dialog
        erzeugt, und alles Weitere — Cache, Undo, die Sperre für den Agenten —
        gilt unverändert.
        """
        if self._sketch_panel is not None:
            return
        panel = SketchPanel(text, self._parameter_values(), self)
        # Die Zeichenfläche ist der früheste Ort, an dem ein zu großes Teil
        # auffallen kann (E1). Der Bauraum steht im Profil, also braucht es
        # dafür keine neue Rechnung — nur die Zahl an die richtige Stelle.
        volume = self.session.profile.printer.build_volume
        panel.set_bed((float(volume[0]), float(volume[1])))
        self._sketch_panel = panel
        self._sketch_target = op_name
        self.middle_stack.addWidget(panel)
        self.middle_stack.setCurrentWidget(panel)
        # Der Startbildschirm liegt vor dem Arbeitsbereich, solange nichts
        # offen ist — und zu zeichnen beginnen ist genau der Fall, in dem noch
        # nichts offen ist (Weg 2, §2.2). Ohne diese Zeile meldete die
        # Statusleiste den Modus, und zu sehen war der Startbildschirm.
        self._show_start_screen(False)
        self.tools.close_tool()
        self.sketch_bar.setVisible(True)
        self._update_actions()
        self.statusBar().showMessage(
            tr("Skizze für {op} — Escape verlässt den Modus.").format(
                op=str(REGISTRY.get(op_name).title)
            )
        )

    def finish_sketch(self, keep: bool = True) -> None:
        """Den Modus verlassen. Mit ``keep`` öffnet die Operation auf der
        gezeichneten Skizze, sonst wird sie verworfen.
        """
        panel = self._sketch_panel
        target = self._sketch_target
        if panel is None:
            return
        text = panel.sketch_text() if keep else ""
        self.middle_stack.setCurrentWidget(self.viewport)
        self.middle_stack.removeWidget(panel)
        panel.deleteLater()
        self._sketch_panel = None
        self._sketch_target = None
        self.sketch_bar.setVisible(False)
        self.statusBar().clearMessage()
        self._update_actions()
        if keep and target and text:
            self.run_operation(REGISTRY.get(target), given={_sketch_param(target): text})

    def action_command_palette(self) -> None:
        """Eine Taste, alles — und die Kürzel lernen sich nebenbei (§2.6)."""
        commands = self.window_commands()
        extra = [
            PaletteEntry(
                name=key,
                title=title,
                doc=title,
                shortcut=shortcut,
                category=key.split(".", 1)[0],
            )
            for key, (title, shortcut, _slot) in commands.items()
        ]
        entries = palette_entries(for_feature=self.selected_feature_kind())
        palette = CommandPalette([*entries, *extra], parent=self)
        if palette.exec() != CommandPalette.DialogCode.Accepted:
            return
        name = palette.chosen()
        if not name:
            return
        if name in commands:
            commands[name][2]()
            return
        self.run_operation(REGISTRY.get(name))

    def _on_transform_dragged(self, steps: Any) -> None:
        """Ein Ziehen, eine Transaktion — in einem Schritt zurückgenommen
        (§18.11, §15.5).
        """
        selected = self.object_tree.selected()
        if selected is None:
            return
        drafts: list[OperationDraft] = []
        if steps.moves:
            drafts.append(
                OperationDraft(
                    op="translate_object",
                    inputs=(selected,),
                    params={"dx": steps.offset[0], "dy": steps.offset[1], "dz": steps.offset[2]},
                )
            )
        if steps.turns:
            drafts.append(
                OperationDraft(
                    op="rotate_object",
                    inputs=(selected,),
                    params={"axis": steps.axis, "angle": steps.angle},
                )
            )
        if steps.resizes:
            drafts.append(
                OperationDraft(
                    op="scale_object", inputs=(selected,), params={"factor": steps.scale}
                )
            )
        if drafts:
            self.session.apply(_("Direkt bewegt"), drafts)

    def _on_measurement(self, measurement: Any) -> None:
        self.measure_bar.show_measurement(
            measurement.kind, measurement.value, len(self.viewport.measurements)
        )

    # --- analysis maps and layers (§18.4, §18.10) -------------------------------

    def _on_map_changed(self, kind: Any) -> None:
        """Baut die gewählte Karte für das gewählte Objekt und gibt sie der
        Ansicht.
        """
        object_id = self.object_tree.selected()
        if kind is None or object_id is None:
            self.viewport.set_analysis_map(None, None)
            self.analysis_bar.show_legend(None)
            if kind is not None:
                self.analysis_bar.show_problem(tr("Wählen Sie zuerst ein Objekt im Objektbaum."))
            return

        self._analysis_map(kind, object_id)

    def _analysis_map(self, kind: maps.MapKind, object_id: ObjectId) -> None:
        """§18.9: im Hintergrund gerechnet, je Objekt und Art gecacht.

        Sekunden an einem großen Körper, und ein Fenster, das so lange nicht
        antwortet, sieht kaputt aus. Eine neuere Anfrage ersetzt eine wartende —
        niemand will die Karte, von der er weggeklickt hat.
        """
        result = self.session.last_result
        entry = result.scene.objects.get(object_id) if result else None
        if entry is None:
            return

        key = (object_id, kind, entry.mesh.triangle_count)
        if key in self._map_cache:
            self._show_map(self._map_cache[key], object_id)
            return

        self.analysis_bar.show_problem(tr("Die Analysekarte wird berechnet …"))
        worker = _MapWorker(kind, entry, self.session.profile, result.scene if result else None)
        worker.done.connect(
            lambda analysis, key=key, object_id=object_id: self._map_ready(analysis, key, object_id)
        )
        worker.tooLarge.connect(
            lambda: self.analysis_bar.show_problem(
                tr("Für eine Analysekarte ist dieses Modell zu groß.")
            )
        )
        worker.finished.connect(lambda: setattr(self, "_map_worker", None))
        self._retire(self._map_worker)
        self._map_worker = worker
        worker.start()

    def _retire(self, worker: Any) -> None:
        """Hält einen ersetzten Arbeiter fest, bis er ausgelaufen ist.

        Sein Ergebnis will niemand mehr — aber sein Thread läuft noch, und
        ohne Referenz zerstört der Speicherbereiniger das QThread-Objekt
        unter ihm.
        """
        if worker is None or not worker.isRunning():
            return
        self._retired.append(worker)
        worker.finished.connect(
            lambda done=worker: self._retired.remove(done) if done in self._retired else None
        )

    def _map_ready(self, analysis: Any, key: tuple[Any, ...], object_id: ObjectId) -> None:
        self._map_cache = {key: analysis}
        if self.analysis_bar.chosen() == key[1] and self.object_tree.selected() == object_id:
            self._show_map(analysis, object_id)

    def _show_map(self, analysis: Any, object_id: ObjectId) -> None:
        self.viewport.set_analysis_map(analysis, object_id if analysis else None)
        self.analysis_bar.show_legend(analysis)

    def _on_layer_changed(self, index: int) -> None:
        """Durch die Schichtanalyse fahren (§18.10) — Geometrie, keine
        Werkzeugwege.
        """
        object_id = self.object_tree.selected()
        if index < 0 or object_id is None:
            self.viewport.set_layer(None)
            return
        self._slice_of(object_id, lambda result: self._show_layer(result, index))

    def _show_layer(self, result: SliceResult | None, index: int) -> None:
        if result is None or not result.layers:
            self.viewport.set_layer(None)
            return
        self.viewport.set_layer(result.layers[min(index, len(result.layers) - 1)])

    def _slice_of(self, object_id: ObjectId, then: Any = None) -> SliceResult | None:
        """Die Schichtanalyse eines Körpers — aus dem Cache oder gerechnet.

        Gerechnet wird im Arbeiter (§2.8): an einem großen Netz sind das
        Sekunden, und ein Fenster, das sie in der Ereignisschleife verbringt,
        hört auf zu zeichnen. Vorher stand hier ein Wartezeiger, und der macht
        aus einer Blockade nur eine angekündigte.

        Gibt das Ergebnis zurück, **wenn** es schon vorliegt; sonst ``None``
        und ``then`` wird gerufen, sobald es da ist.
        """
        result = self.session.last_result
        entry = result.scene.objects.get(object_id) if result else None
        if entry is None:
            return None

        key = (object_id, entry.mesh.triangle_count)
        if key == self._slice_key:
            if then is not None:
                then(self._slice_cache)
            return self._slice_cache

        self.status_message.setText(tr("Die Schichtanalyse läuft …"))
        worker = _SliceWorker(entry, self.session.profile.printer.layer_height)
        worker.done.connect(lambda outcome, key=key: self._slice_ready(outcome, key, then))
        worker.finished.connect(lambda: setattr(self, "_slice_worker", None))
        self._retire(self._slice_worker)
        self._slice_worker = worker
        worker.start()
        return None

    def _slice_ready(self, outcome: SliceResult, key: tuple[Any, ...], then: Any) -> None:
        self._slice_cache = outcome
        self._slice_key = key
        self.layer_bar.show_result(outcome)
        self.status_message.setText("")
        if then is not None:
            then(outcome)

    def _on_finding_activated(self, finding: Finding) -> None:
        """Eine Warnung anklicken, die Stelle sehen: der kürzeste Weg vom Problem
        zum Ort (§18.4).
        """
        object_id = finding.object_id or self.object_tree.selected()
        result = self.session.last_result
        entry = result.scene.objects.get(object_id) if result and object_id else None
        if entry is None:
            return

        kind = maps.map_for(finding)
        if kind is not None:
            self.analysis_bar.show_map(kind)
            self._analysis_map(kind, entry.id)
            # Die Kamera geht zu dem Ort, den der Befund nennt. Wo der Befund
            # keinen eigenen Ort hat, hat die Karte einen — aber die Karte
            # rechnet vielleicht noch (§18.9), und die Ansicht wird nicht
            # dafür aufgehalten.
            target = maps.location_of(entry, finding)
            if target is None:
                cached = self._map_cache.get((entry.id, kind, entry.mesh.triangle_count))
                target = maps.focus_point(entry, cached) if cached is not None else None
        else:
            target = maps.location_of(entry, finding)

        if target is not None:
            self.viewport.fly_to(target)

    # --- the agent (§26) --------------------------------------------------------

    def _on_request_sent(self, request: str) -> None:
        """Ein Zug. Die Auswahl reist mit, sonst heißt „dieses Loch"
        nichts (§26.1).
        """
        selected = self.object_tree.selected()
        feature = self.object_tree.selected_feature()
        selection = (selected, feature or "") if selected else None
        self.session.propose_async(request, selection)

    def _on_agent_busy(self, busy: bool) -> None:
        """Ein Zug dauert zehn bis sechzig Sekunden — §2.8 verlangt dafür
        Fortschritt **und** Abbrechen.

        Bisher gab es nur den Satz „Der Agent denkt nach.": der Knopf hing
        allein an der Auswertung, und ein Zug, der zu lange lief, war nur über
        das Schließen des Fensters zu beenden.
        """
        self.chat.set_busy(busy)
        self.status_message.setText(tr("Der Agent denkt nach.") if busy else "")
        self.cancel_button.setVisible(busy or self.progress.isVisible())
        if busy:
            # Wie viele Schritte ein Zug braucht, steht vorher nicht fest —
            # ein Balken ohne Ende sagt „es läuft", ohne etwas zu versprechen.
            self.progress.setRange(0, 0)
            self.progress.setVisible(True)
        elif not self.session.busy:
            self.progress.setRange(0, 100)
            self.progress.setVisible(False)

    def _on_split_busy(self, busy: bool) -> None:
        """Die Trennebenensuche läuft — Fortschritt und Abbrechen wie bei
        jedem anderen Lauf über zwei Sekunden (§2.8)."""
        self.status_message.setText(tr("Die Trennebenen werden gesucht …") if busy else "")
        self.cancel_button.setVisible(busy or self.progress.isVisible())
        if busy:
            # Wie viele Ebenen die Suche prüft, steht vorher nicht fest —
            # derselbe endlose Balken wie beim Agentenzug.
            self.progress.setRange(0, 0)
            self.progress.setVisible(True)
        elif not self.session.busy and not self.chat.busy:
            self.progress.setRange(0, 100)
            self.progress.setVisible(False)
            self.cancel_button.setVisible(False)

    def _on_proposal(self, preview: Any) -> None:
        """Ein Vorschlag ist da: zeigen, was er änderte, dann den Nutzer
        entscheiden lassen.
        """
        self._proposal = preview
        self.chat.show_proposal(preview)
        if preview.difference is not None:
            self.viewport.show_difference(preview.difference)
        self._focus_chat()

    def _on_proposal_accepted(self) -> None:
        if self._proposal is None:
            return
        self.session.accept_proposal(self._proposal)
        self._clear_proposal()

    def _on_proposal_discarded(self) -> None:
        if self._proposal is None:
            return
        self.session.discard_proposal(self._proposal)
        self._clear_proposal()

    def _clear_proposal(self) -> None:
        self._proposal = None
        self.chat.show_proposal(None)
        self.viewport.show_difference(None)
        self.chat.show_document(self.session.project.document)

    def _focus_chat(self) -> None:
        if self.right.isVisible():
            self.right.setCurrentWidget(self.chat)

    def _on_paint(self, point: Any) -> None:
        """§20: ein Klick, eine Operation — ein Undo nimmt also einen Strich
        zurück.
        """
        object_id = self.object_tree.selected()
        if not object_id:
            self.status_message.setText(tr("Bitte zuerst ein Objekt auswählen."))
            return

        params = {**self.paint_bar.values(), "x": point[0], "y": point[1], "z": point[2]}
        self.session.apply(
            _("Bemalen"),
            [OperationDraft(op="paint_slot", inputs=(object_id,), params=params)],
        )

    # --- Sichtbarkeit (§18.8) ---------------------------------------------------

    def _on_visibility(self, objects: Any, visible: bool) -> None:
        """Ein- oder ausblenden. Ansicht, nicht Szene — der Körper bleibt in
        der Auswertung, im Prüfbericht und im Export.
        """
        chosen = set(objects)
        self._apply_hidden(self._hidden - chosen if visible else self._hidden | chosen)

    def _on_isolate(self, objects: Any) -> None:
        """Alles andere ausblenden — und derselbe Eintrag holt es zurück (§18.8)."""
        chosen = set(objects)
        result = self.session.last_result
        everything = set(result.scene.objects) if result else set()
        self._apply_hidden(frozenset() if self._hidden else frozenset(everything - chosen))

    def _apply_hidden(self, hidden: frozenset[str]) -> None:
        self._hidden = hidden
        self.viewport.set_hidden(hidden)
        self.object_tree.set_hidden(hidden)
        self.status_message.setText(f"{len(hidden)} × {tr('ausgeblendet')}" if hidden else "")

    def _on_feature_picked(self, feature_id: str) -> None:
        """Ein Klick in der Ansicht wählt das Merkmal auch im Baum aus (§18.5)."""
        object_id = self.object_tree.selected()
        if object_id is not None:
            self.object_tree.select_feature(object_id, feature_id)

    def _on_feature_selected(self, feature_id: str | None) -> None:
        """Das gewählte Merkmal, in der Ansicht und in der Statusleiste."""
        self.viewport.select_feature(feature_id)
        if feature_id is None:
            return
        result = self.session.last_result
        object_id = self.object_tree.selected()
        entry = result.scene.objects.get(object_id) if result and object_id else None
        feature = entry.features.get(feature_id) if entry is not None else None
        if entry is not None and feature is not None:
            self.measurements.setText(f"{entry.name} · {feature_label(feature_id, feature)}")

    def _on_section(self, plane: object, thickness: object) -> None:
        self.viewport.set_section(plane, thickness)  # type: ignore[arg-type]
        self.section_bar.show_capping_state(self.viewport.section_uncapped)

    def action_theme(self, theme: str) -> None:
        application = QApplication.instance()
        if application is not None:
            apply_theme(application, theme)  # type: ignore[arg-type]
        self.viewport.set_theme(theme)
        self.settings.theme = theme
        save_settings(self.settings)

    def action_navigation(self, scheme: str) -> None:
        self.viewport.set_navigation(scheme)  # type: ignore[arg-type]
        self.settings.navigation = scheme
        save_settings(self.settings)

    def run_operation(self, spec: OperationSpec, given: Mapping[str, Any] | None = None) -> None:
        """Menüeintrag, Dialog, Transaktion — derselbe Weg, den auch der Agent
        nehmen wird.

        ``given`` belegt Felder vor, die der Aufrufer schon kennt — der
        Skizzenmodus reicht so seine gezeichnete Skizze herein. Es ersetzt den
        Dialog nicht: die übrigen Werte fragt er weiter, und was hier steht,
        lässt sich dort ändern.
        """
        if self.session.history.discardable and not confirm_discard(
            self.session.history.discardable, self
        ):
            return

        result = self.session.last_result
        objects = list(result.scene.objects) if result else []
        chosen = self.object_tree.selected_objects()
        if spec.consumes and len(chosen) < spec.consumes:
            QMessageBox.information(self, str(spec.title), _needs_objects(spec.consumes))
            return

        if spec.takes_whole_scene and not objects:
            QMessageBox.information(self, str(spec.title), tr("Die Szene ist leer."))
            return

        values = dict(self._from_selection(spec, chosen[0] if chosen else None))
        values.update(given or {})
        params: dict[str, Any] = dict(values)
        if spec.params.spec():
            dialog = OperationDialog(
                spec,
                self._object_names(),
                self,
                values=values,
                sources=self._source_names(),
                parameter_values=self._parameter_values(),
            )
            inputs = inputs_for(spec, objects, chosen)
            # §18.7: der Dialog zeigt, was er täte, während getippt wird —
            # dieselbe Differenzansicht wie beim Agentenvorschlag.
            self._wire_preview(
                dialog,
                lambda entered: [OperationDraft(op=spec.name, inputs=inputs, params=entered)],
            )
            accepted = dialog.exec() == OperationDialog.DialogCode.Accepted
            self._clear_preview()
            if not accepted:
                return
            params = dialog.values()
        # Ohne Parameter gibt es nichts zu fragen, und ein Fenster mit nur „OK"
        # wäre die Bestätigung vor einer rücknehmbaren Handlung, die Regel 19
        # verbietet. Entfernen, Vereinigen, Abziehen — alle laufen sofort, und
        # alle nimmt ein Undo zurück.

        self.session.apply(
            spec.title,
            [
                OperationDraft(
                    op=spec.name,
                    inputs=inputs_for(spec, objects, chosen),
                    params=params,
                )
            ],
        )

    def edit_operation(self, op_id: int) -> None:
        """Eine Operation des Stapels wieder öffnen und ihr andere Zahlen
        geben (§15.4).

        Derselbe erzeugte Dialog, auf den Werten, die in der Datei stehen. Vor
        dem hier war der einzige Weg zu einer Bohrung zwei Millimeter weiter
        links, zurückzunehmen und neu zu bohren — und das ist ein Schritt zum
        Zurücknehmen, eine Position nicht.
        """
        try:
            entry = self.session.history.operation(op_id)
            spec = REGISTRY.get(entry.op)
        except AppError as error:
            self.session.failed.emit(error)
            return

        dialog = OperationDialog(
            spec,
            self._object_names(),
            self,
            values=entry.params,
            sources=self._source_names(),
            parameter_values=self._parameter_values(),
        )
        dialog.setWindowTitle(f"{spec.title} — {tr('Operation')} {op_id}")
        # Auch beim Korrigieren zeigt die Vorschau den Zweig, wie er würde —
        # gerechnet als geänderte Operation, nicht als neuer Schritt (§15.4).
        self._wire_preview(dialog, None, change_op=op_id)
        accepted = dialog.exec() == OperationDialog.DialogCode.Accepted
        self._clear_preview()
        if not accepted:
            return
        self.session.change_params(op_id, dialog.values())

    def _parameter_values(self) -> dict[str, float]:
        """Die aufgelösten Projektparameter — der Skizzeneditor rechnet
        Maßausdrücke damit (§13)."""
        from app.core.scene import expressions

        try:
            return dict(expressions.resolve(self.session.project.document.parameters))
        except AppError:
            return {}

    def _wire_preview(
        self, dialog: OperationDialog, drafts_of: Any, *, change_op: int | None = None
    ) -> None:
        """Verbindet einen Operationsdialog mit der Live-Vorschau (§18.7).

        Entprellt: dreißig Klicks auf den Drehknopf sind eine Rechnung, nicht
        dreißig. Die erste Vorschau läuft sofort — auch die Vorgaben sind eine
        Aussage darüber, was gleich passiert.
        """
        timer = QTimer(dialog)
        timer.setSingleShot(True)
        timer.setInterval(300)

        def request() -> None:
            entered = dialog.values()
            if change_op is not None:
                self.session.preview_async(
                    self._show_preview, change_op=change_op, change_values=entered
                )
            else:
                self.session.preview_async(self._show_preview, drafts_of(entered))

        timer.timeout.connect(request)
        dialog.valuesChanged.connect(lambda: timer.start())
        request()

    def _show_preview(self, difference: Any) -> None:
        self.viewport.show_difference(difference)

    def _clear_preview(self) -> None:
        """Der Dialog ist zu: die Vorschau geht, ein wartender Agentenvorschlag
        bekommt seine Differenz zurück."""
        self.session.cancel_preview()
        pending = self._proposal.difference if self._proposal is not None else None
        self.viewport.show_difference(pending)

    def _object_names(self) -> dict[str, str]:
        """Kennung auf Name, wie die Dialoge die Szene sehen.

        Der Baum zeigt Namen, das Dokument führt Kennungen — ein Aufklappmenü
        voller „obj_7" verlangt vom Nutzer, die Übersetzung selbst zu machen.
        """
        result = self.session.last_result
        if result is None:
            return {}
        return {object_id: entry.name for object_id, entry in result.scene.objects.items()}

    def _source_names(self) -> dict[str, str]:
        """Kennung auf Dateiname, für die Quellenwähler (§16.3)."""
        return {
            source_id: Path(source.path).name or source_id
            for source_id, source in self.session.project.document.sources.items()
        }

    def _from_selection(self, spec: OperationSpec, selected: ObjectId | None) -> dict[str, Any]:
        """Was das angeklickte Merkmal darüber sagt, wohin diese Operation
        gehört (§18.5).

        Ohne das war die Auswahl in Baum und Ansicht zum Ansehen da: der Dialog
        öffnete auf seinen Vorgaben, und wer eine Bohrung in der eben
        angeklickten Fläche wollte, las ihre Koordinaten von der Analysekarte ab
        und tippte sie ein.
        """
        feature_id = self.object_tree.selected_feature()
        result = self.session.last_result
        if not feature_id or selected is None or result is None:
            return {}
        entry = result.scene.objects.get(selected)
        feature = entry.features.get(feature_id) if entry else None
        return dict(values_for(spec, feature)) if feature is not None else {}

    # --- session replies --------------------------------------------------------

    def _on_scene(self, result: EvaluationResult) -> None:
        # Neue Geometrie heißt: jede Karte und jeder Schnitt sind veraltet.
        self._map_cache.clear()
        self._slice_key = None
        self.layer_bar.show_result(None)
        self.viewport.set_analysis_map(None, None)
        self.viewport.set_layer(None)
        self.analysis_bar.show_legend(None)
        # Ausgeblendetes, das die Szene nicht mehr enthält, wird vergessen —
        # sonst blendet eine wiederhergestellte Nummer später etwas aus, das
        # niemand versteckt hat.
        self._hidden &= set(result.scene.objects)
        self.viewport.set_hidden(self._hidden)
        self.object_tree.set_hidden(self._hidden)
        # Der erste Körper einer leeren Szene wird eingepasst. Ohne das blieb
        # die Kamera, wo sie war: ein importiertes Teil lag außerhalb des
        # Bildes, und die Anwendung sah aus, als hätte sie nichts geladen.
        was_empty = not self._seen_objects
        self._seen_objects = bool(result.scene.objects)
        self.object_tree.show_scene(result, self.session.project.document)
        if was_empty and self._seen_objects:
            self.viewport.reset_camera()
        plates = {entry.plate for entry in result.scene.objects.values()}
        self.explode_bar.show_for(len(result.scene.objects), max(plates, default=0) + 1)
        self.report.show_result(result)
        self.viewport.show_build_volume(self.session.profile)
        self.viewport.show_scene(result)
        low, high = self.viewport.section_range()
        self.section_bar.set_range(low, high)
        self.section_bar.show_capping_state(self.viewport.section_uncapped)
        self.history_panel.show_document(
            self.session.project.document, result.stopped_at, self.session.history.undone
        )
        self._update_actions()
        if result.stopped_at is not None:
            # §15.3: der letzte vollständige Zustand bleibt sichtbar, die
            # Statusleiste sagt warum.
            self.status_message.setText(tr("Die Kette hält an — siehe Prüfbericht."))
            self._focus_report()
        elif self.report.worst_severity(result) in ("warning", "error"):
            self._focus_report()

    def _on_project(self) -> None:
        document = self.session.project.document
        self.parameters.show_document(document)
        self.history_panel.show_document(document, undone=self.session.history.undone)
        self.chat.show_document(document)
        self.setWindowTitle(f"{self.session.title} — {APP_NAME}")
        self._update_actions()

    def _on_progress(self, fraction: float, text: str) -> None:
        self.progress.setValue(int(fraction * 100))
        # Ein leerer Text heißt, der Lauf ist vorbei; die Zeile geht mit
        # ihm weg (§2.8).
        self.status_message.setText(text)

    def _on_busy(self, busy: bool) -> None:
        # Agent und Trennebenensuche können gleichzeitig laufen; dann bleiben
        # Balken und Knopf stehen, statt mit der Auswertung zu verschwinden.
        others = self.chat.busy or self.session.split_running
        self.progress.setVisible(busy or others)
        self.cancel_button.setVisible(busy or others)
        if busy:
            self.progress.setRange(0, 100)
        if not busy and not others:
            self.status_message.setText("")

    def _on_ask(self, request: AskRequest) -> None:
        """Der Arbeiter wartet, solange dieser Dialog offen ist (§21.3)."""
        dialog = AskDialog(request.question, request.choices, self)
        if dialog.exec() == AskDialog.DialogCode.Accepted:
            request.reply(dialog.chosen())
        else:
            request.reply(None)

    def _on_error(self, error: AppError) -> None:
        """§33.1: ein Fehler des Nutzers sieht anders aus als ein Fehler im
        Programm.
        """
        if isinstance(error, InternalError):
            self.report_error(error)
            return
        show_error(error, self)

    def error_handlers(self) -> dict[str, Any]:
        """Was hinter den Knöpfen eines Fehlerdialogs steckt (§2.7, Regel 17).

        Der Kern schlägt Handlungen vor, die Oberfläche führt sie aus — das
        war der fehlende Draht. Was hier nicht steht, wird auch nicht
        angeboten; ein Knopf, der nichts tut, ist schlimmer als keiner.

        Nicht dabei und bewusst: ``use_voxel_stage`` (die Stufe ist kein
        Parameter, den ein Dialog setzen könnte), ``choose`` (der Kern fragt
        dafür über ``ctx.ask``, bevor er wirft) und ``choose_printer`` — das
        kommt mit dem Einstellungsdialog.
        """
        return {
            "report_error": lambda error: self.report_error(error),
            "show_details": lambda error: show_details(error, self),
            "show_locations": self._show_error_location,
            "repair_and_retry": self._repair_after_error,
            "split_model": self._split_after_error,
            "scale_to_fit": self._scale_after_error,
            "open_settings": lambda _error: self.action_install_extras(),
        }

    def _object_of(self, error: AppError) -> ObjectId | None:
        """Der Körper, um den es geht — aus dem Fehler oder aus der Auswahl."""
        if error.object_id:
            return error.object_id
        chosen = self.object_tree.selected_objects()
        return chosen[0] if chosen else None

    def _show_error_location(self, error: AppError) -> None:
        """„Stellen zeigen" heißt: die Karte, auf der sie zu sehen sind (§18.4).

        Ein Fehler nennt selten eine einzelne Koordinate — bei einem Netz mit
        drei offenen Kanten wären es drei. Die Defektkarte färbt sie alle, und
        das ist die Antwort auf die Frage, die der Knopf stellt.
        """
        object_id = self._object_of(error)
        result = self.session.last_result
        entry = result.scene.objects.get(object_id) if result and object_id else None
        if entry is None:
            return
        self.object_tree.select_object(entry.id)
        self.tools.activate("analysis")
        self.analysis_bar.show_map("defects")
        self._analysis_map("defects", entry.id)

    def _repair_after_error(self, error: AppError) -> None:
        """§17.1: die Reparaturkette auf den Körper, an dem es hing."""
        object_id = self._object_of(error)
        if object_id is None:
            return
        self.session.apply(
            REGISTRY.get("repair").title,
            [OperationDraft(op="repair", inputs=(object_id,))],
        )

    def _split_after_error(self, error: AppError) -> None:
        """Zu groß für das Bett: teilen, bis jedes Stück passt (§25)."""
        object_id = self._object_of(error)
        if object_id is not None:
            self.action_auto_split(object_id)

    def _scale_after_error(self, error: AppError) -> None:
        """Auf den Bauraum verkleinern — mit dem Faktor, der wirklich passt.

        Der Fehler kennt beide Größen; sie hier neu zu raten wäre eine zweite
        Wahrheit. Ein Prozent Luft, damit das Teil nicht exakt an der Wand des
        Bauraums klebt.
        """
        volume = error.values.get("build_volume")
        size = error.values.get("size")
        object_id = self._object_of(error)
        if object_id is None or not volume or not size:
            return
        factor = min(
            available / needed
            for available, needed in zip(volume, size, strict=False)
            if needed > 0.0
        )
        self.session.apply(
            REGISTRY.get("scale_object").title,
            [
                OperationDraft(
                    op="scale_object", inputs=(object_id,), params={"factor": factor * 0.99}
                )
            ],
        )

    def _on_selection(self, object_id: str | None) -> None:
        self.viewport.select(object_id)
        # Karte und Schichtanalyse gehören zu einem Körper; ein anderer Körper
        # braucht seine eigenen, also folgen sie der Auswahl, statt zu
        # verweilen.
        self._on_map_changed(self.analysis_bar.chosen())
        self._on_layer_changed(self.layer_bar.index())
        self._update_actions()
        described = describe_selection(self.session.last_result, object_id)
        if described is None:
            self.measurements.clear_selection()
            return
        name, size, volume = described
        self.measurements.show_object(name, size, volume)

    def action_add_parameter(self) -> None:
        """§13: ein Hauptmaß benennen — auch ohne den Agenten (§2.3)."""
        dialog = ParameterDialog(self.session.project.document.parameters, self)
        if dialog.exec() != ParameterDialog.DialogCode.Accepted:
            return
        self.session.add_parameter(dialog.parameter())

    def _on_parameter_edited(self, name: str, value: float) -> None:
        """An einer Zahl zu drehen ist eine Transaktion, dann eine frische
        Auswertung (§13, §15.5).

        Dieselbe Rückfrage wie bei einer Operation: eine Änderung nach einem
        Undo wirft die abgeschnittenen Schritte weg (§15.4), und das darf eine
        gedrehte Zahl nicht stiller tun als ein Menüeintrag. Sagt der Nutzer
        nein, springt die Leiste auf den Stand des Dokuments zurück.
        """
        if self.session.history.discardable and not confirm_discard(
            self.session.history.discardable, self
        ):
            self.parameters.show_document(self.session.project.document)
            return
        self.session.change_parameter(name, value)

    # --- start ------------------------------------------------------------------

    def start(self) -> None:
        """Was passiert, sobald das Fenster wirklich auf dem Bildschirm ist (§38).

        Mit Absicht nicht im Konstruktor: der erste Start öffnet einen modalen
        Dialog, und ein Fenster, das das während seines Aufbaus tut, lässt sich
        von nichts aufbauen, das kein Mensch ist — kein Test, kein
        Screenshot-Werkzeug, kein zweites Fenster.
        """
        if first_run.should_run(self.settings):
            self.action_first_run()
        self._offer_unsaved_recovery()
        if self.settings.check_for_updates:
            self._check_for_updates()

    def _offer_unsaved_recovery(self) -> None:
        """§38: eine Sicherung, die nie einen Namen bekam, wird angeboten.

        Sie wurde geschrieben, seit es die automatische Sicherung gibt, und
        nie angeboten: das Fenster suchte nur neben einer geöffneten Datei.
        Wer vor dem ersten Speichern abstürzte, hatte die Arbeit verloren,
        obwohl sie auf der Platte lag.
        """
        candidate = find_recovery(None)
        if candidate is None:
            return
        answer = QMessageBox.question(
            self,
            tr("Wiederherstellung"),
            tr(
                "Ein Projekt aus einer früheren Sitzung wurde nie gespeichert. "
                "Die automatische Sicherung öffnen?"
            ),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.session.recover(candidate)
        except AppError as error:
            show_error(error, self)
            return
        self._show_start_screen(False)

    def action_first_run(self) -> None:
        """§38: Sprache, Drucker, Material, externe Programme, Chat-Zugang.
        Überspringbar."""
        dialog = first_run.FirstRunDialog(self.settings, self)
        dialog.importRequested.connect(self.action_import)
        if dialog.exec() == first_run.FirstRunDialog.DialogCode.Accepted:
            dialog.apply_to(self.settings)
        else:
            # Überspringen zählt als erledigt: beim nächsten Mal wieder zu fragen
            # wäre Nörgeln.
            self.settings.first_run_done = True
        save_settings(self.settings)
        # Wer im Dialog den Chat eingerichtet hat, soll ihn nicht erst nach
        # einem Neustart bekommen — derselbe Weckruf wie in action_llm_key.
        self.session.set_agent_backend(None)
        self._refresh_chat_availability(probe_local=True)

    def _check_for_updates(self) -> None:
        """§37.2: ein Hinweis mit einem Link. Nichts wird heruntergeladen, nichts
        ersetzt.
        """
        worker = _UpdateWorker()
        worker.done.connect(self._update_answered)
        worker.finished.connect(lambda: setattr(self, "_update_worker", None))
        self._update_worker = worker
        worker.start()

    def _update_answered(self, release: Any) -> None:
        if release is None or not release.newer_than():
            return
        self.status_message.setText(
            f"{tr('Neue Fassung verfügbar')}: {release.version} — {release.url}"
        )

    def report_error(self, error: BaseException, summary: str = "") -> None:
        """§33.1: ein Programmfehler bekommt ein Berichtsangebot, keinen
        Vorschlag.
        """
        dialog = ErrorReportDialog(
            summary=summary or tr("Im Programm ist ein unerwarteter Fehler aufgetreten."),
            detail=str(error),
            error=error,
            project=self.session.path,
            parent=self,
        )
        dialog.exec()

    # --- window -----------------------------------------------------------------

    def _show_start_screen(self, show: bool) -> None:
        self.stack.setCurrentWidget(self.start_screen if show else self.splitter)

    def _focus_report(self) -> None:
        if not self.right.isVisible():
            return
        if self.right.currentWidget() is self.tour and self.tour.active:
            # Die Tour zeigt selbst auf den Prüfbericht, wenn er dran ist —
            # ein Reiterwechsel unter der Anleitung weg wäre ihr Ende.
            return
        self.right.setCurrentWidget(self.report)

    def _offer_tour(self, path: Path) -> None:
        """§37.2: ein Beispiel öffnet sich mit seiner Tour — jedes andere
        Projekt räumt sie weg.

        Kein Dialog und keine Frage: der Reiter ist da, die Tour beginnt, und
        „Tour beenden“ ist jederzeit einen Klick entfernt (Regel 19).
        """
        example = examples.by_path(path)
        tour = tour_for(example.id) if example is not None else None
        if example is None or tour is None:
            self._remove_tour()
            return
        self.right.setTabVisible(self.right.indexOf(self.tour), True)
        self.tour.start(example, tour)
        if not self.right.isVisible():
            # Wer die rechte Spalte ausgeblendet hatte, bekäme eine
            # unsichtbare Tour — und das Beispiel wurde gerade absichtlich
            # geöffnet. Einblenden wie über F9, samt Einstellung.
            self.settings.right_panel_visible = True
            save_settings(self.settings)
            self.right.setVisible(True)
        self.right.setCurrentWidget(self.tour)

    def _remove_tour(self) -> None:
        """Blendet den Tour-Reiter aus — beim Beenden und beim Projektwechsel."""
        self.tour.reset()
        self.right.setTabVisible(self.right.indexOf(self.tour), False)

    def _offer_recovery(self, path: Path) -> None:
        candidate = find_recovery(path)
        if candidate is None:
            return
        answer = QMessageBox.question(
            self,
            tr("Wiederherstellung"),
            tr("Es gibt eine neuere automatische Sicherung. Diese öffnen?"),
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.Yes,
        )
        if answer == QMessageBox.StandardButton.Yes:
            self.session.open_project(candidate)

    def dragEnterEvent(self, event: QDragEnterEvent) -> None:  # noqa: N802 - Qt name
        if accepted_path(event) is not None:
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802 - Qt name
        path = accepted_path(event)
        if path is not None:
            self.open_path(path)
            event.acceptProposedAction()

    def wait_for_workers(self, timeout_ms: int = 2000) -> None:
        """Jeden Arbeiter dieses Fensters auslaufen lassen.

        Ergebnisse, die niemand mehr sehen wird — aber **ein Thread, der sein
        Fenster überlebt, nimmt den Prozess mit**. Die Schichtanalyse fehlte
        hier einmal: Schließen während sie lief war ein Absturz beim Beenden.

        Als eigene Methode und nicht nur im ``closeEvent``, weil es zwei Wege
        gibt, ein Fenster loszuwerden: schließen und wegräumen. Der zweite ist
        der Weg der Tests, und dort führte er zu genau dem Absturz, gegen den
        die Liste hier geschrieben wurde — nur ohne Zeile, weil niemand mehr
        da war, die zu schreiben.
        """
        self.session.cancel()
        self.session.wait_for_idle(timeout_ms)
        for worker in (
            self._map_worker,
            self._slice_worker,
            self._update_worker,
            self._ollama_size_worker,
            *self._retired,
        ):
            if worker is not None and worker.isRunning():
                worker.wait(timeout_ms)

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt name
        # Der Menühinweis versprach das seit jeher („Ungesichertes wird vorher
        # erfragt"), gefragt wurde nie: das Fenster schrieb eine automatische
        # Sicherung und ging zu. Wer die nicht kennt, hat seine Arbeit verloren.
        if not self._may_discard():
            event.ignore()
            return
        self.wait_for_workers()
        if self.session.modified:
            self.session.autosave()
        save_settings(self.settings)
        event.accept()


def registered_operations() -> list[OperationSpec]:
    """Small helper the palette will use in P1."""
    return list(REGISTRY.all())
