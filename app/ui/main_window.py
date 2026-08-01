"""Das Hauptfenster (Bauplan §2.5).

Höchstens drei sichtbare Zonen: die Panels links, der Viewport in der Mitte,
Prüfbericht oder Chat rechts — und die rechte Seite klappt mit einer Taste ganz
weg. Betriebsarten gibt es nicht; es gibt einen Zustand, und der ist die Szene.

Das Menü steht auch hier nicht ausgeschrieben: es wird aus dem Register gebaut
— eine Operation erscheint also im Menü, in der Palette und auf der
Kommandozeile, sobald sie deklariert ist (§10).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QThread, QTimer, Signal
from PySide6.QtGui import QAction, QCloseEvent, QDragEnterEvent, QDropEvent, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QLabel,
    QMainWindow,
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
from app.core import updates
from app.core.errors import AppError, InternalError
from app.core.export.handover import SliceOutcome
from app.core.geom.mesh import as_mesh_data
from app.core.knowledge import calibration
from app.core.knowledge.parts.ops import op_name as part_op_name
from app.core.log import get_logger
from app.core.perceive import maps
from app.core.registry import REGISTRY, OperationSpec, menu_tree
from app.core.scene import EvaluationResult, OperationDraft, values_for
from app.core.scene.project import find_recovery
from app.core.slice import gcode
from app.core.slice.analysis import slice_body
from app.core.types import Finding, ObjectId, SliceResult
from app.i18n import tr
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
    confirm_discard,
    show_error,
)
from app.ui.explode_bar import ExplodeBar
from app.ui.generate_dialog import GenerateDialog
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
from app.ui.start_screen import StartScreen, accepted_path
from app.ui.theme import apply_theme
from app.ui.tool_strip import ToolStrip
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


def inputs_for(
    spec: OperationSpec, objects: list[ObjectId], selected: ObjectId | None
) -> tuple[ObjectId, ...]:
    """Auf welche Objekte eine Operation angewandt wird (§10, §25).

    Eine eigene Funktion, keine zwei Zeilen im Menü-Handler: die Regel ist
    dieselbe für Kommandozeile und Agent, und eine Operation, die auf der
    ganzen Szene arbeitet und nichts bekommt, läuft auf nichts und sieht kaputt
    aus.
    """
    if spec.takes_whole_scene:
        return tuple(objects)
    return (selected,) if spec.consumes and selected else ()


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
        self._slice_cache: Any = None
        self._slice_key: tuple[str, int] | None = None
        self._proposal: Any = None
        """The agent turn waiting for a decision (§26.5)."""
        self._manual: ManualWindow | None = None
        """Das Handbuchfenster, einmal gebaut und danach wiederverwendet."""

        self._build_central()
        self._build_status_bar()
        self._build_menus()
        self._connect_session()

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
        )
        self.tools.add(
            "measure",
            tr("Messen"),
            self.measure_bar,
            lambda: self.measure_bar.mode.setCurrentIndex(0),
        )
        self.tools.add(
            "transform",
            tr("Bewegen"),
            self.transform_bar,
            lambda: self.transform_bar.gizmo.setChecked(False),
        )
        self.tools.add(
            "analysis",
            tr("Analyse"),
            self.analysis_bar,
            lambda: self.analysis_bar.selector.setCurrentIndex(0),
        )
        self.tools.add(
            "layers",
            tr("Schichten"),
            self.layer_bar,
            lambda: self.layer_bar.active.setCurrentIndex(0),
        )
        self.tools.add(
            "explode",
            tr("Explosion"),
            self.explode_bar,
            lambda: self.explode_bar.slider.setValue(0),
        )
        # Bemalen ändert Materialslots und nicht bloß die Ansicht: das Schließen
        # beendet das Bemalen, nimmt aber nichts Gemaltes zurück.
        self.tools.add(
            "paint",
            tr("Bemalen"),
            self.paint_bar,
            lambda: self.paint_bar.active.setChecked(False),
        )

        middle = QWidget(self)
        middle_layout = QVBoxLayout(middle)
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.setSpacing(0)
        middle_layout.addWidget(self.viewport, stretch=1)
        middle_layout.addWidget(self.tools)

        self.report = ReportPanel(self)
        self.report.findingActivated.connect(self._on_finding_activated)
        self.chat = ChatPanel(self)
        self.chat.requestSent.connect(self._on_request_sent)
        self.chat.accepted.connect(self._on_proposal_accepted)
        self.chat.discarded.connect(self._on_proposal_discarded)
        self.chat.setupRequested.connect(self.action_install_extras)

        self.right = QTabWidget(self)
        self.right.addTab(self.report, tr("Prüfbericht"))
        self.right.addTab(self.chat, tr("Chat"))

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

        self.stack = QStackedWidget(self)
        self.stack.addWidget(self.start_screen)
        self.stack.addWidget(self.splitter)
        self.setCentralWidget(self.stack)

        self.object_tree.selectionChanged.connect(self._on_selection)
        self.object_tree.featureSelected.connect(self._on_feature_selected)
        self.object_tree.operationRequested.connect(self.run_operation)
        self.parameters.parameterEdited.connect(self._on_parameter_edited)
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

        bar = self.statusBar()
        bar.addWidget(self.measurements, 1)
        bar.addPermanentWidget(self.status_message)
        bar.addPermanentWidget(self.progress)
        bar.addPermanentWidget(self.cancel_button)

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu(tr("Datei"))
        file_menu.setToolTipsVisible(True)
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

        edit_menu = self.menuBar().addMenu(tr("Bearbeiten"))
        edit_menu.setToolTipsVisible(True)
        self._add_action(
            edit_menu,
            tr("Befehlspalette …"),
            "Ctrl+Shift+P",
            self.action_command_palette,
            tr("Jede Operation über ihren Namen finden, ohne durch die Menüs zu gehen."),
        )
        self._add_action(
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
        self._add_action(
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
        for section in menu_tree():
            menu = self.menuBar().addMenu(str(section.title))
            menu.setToolTipsVisible(True)
            for spec in section.entries:
                action = QAction(str(spec.title), self)
                if spec.shortcut:
                    action.setShortcut(QKeySequence(spec.shortcut))
                action.setStatusTip(str(spec.doc))
                action.setToolTip(str(spec.doc))
                action.triggered.connect(
                    lambda _checked=False, entry=spec: self.run_operation(entry)
                )
                menu.addAction(action)

        view_menu = self.menuBar().addMenu(tr("Ansicht"))
        view_menu.setToolTipsVisible(True)
        self._add_action(
            view_menu,
            tr("Rechten Bereich zeigen"),
            "F9",
            self.action_toggle_right,
            tr("Verlauf, Parameter und Chat ein- oder ausblenden."),
        )
        view_menu.addSeparator()

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
                view_menu,
                label,
                shortcut,
                lambda checked=False, key=mode: self.viewport.set_display_mode(key),
                hint,
            )
        view_menu.addSeparator()
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
                view_menu,
                label,
                None,
                lambda checked=False, key=shading: self.viewport.set_shading(key),
                hint,
            )
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
                view_menu,
                label,
                shortcut,
                lambda checked=False, key=projection: self.viewport.set_projection(key),
                hint,
            )
        view_menu.addSeparator()
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
                view_menu,
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
        view_menu.addSeparator()
        for scheme, label, hint in (
            (
                "slicer",
                tr("Navigation: Slicer"),
                tr("Maustasten wie in einem Slicer — links drehen, rechts schieben."),
            ),
            ("cad", tr("Navigation: CAD"), tr("Wie in einem CAD-Programm: Mittlere Taste dreht.")),
            ("blender", tr("Navigation: Blender"), tr("Wie in Blender.")),
        ):
            self._add_action(
                view_menu,
                label,
                None,
                lambda checked=False, key=scheme: self.action_navigation(key),
                hint,
            )

        help_menu = self.menuBar().addMenu(tr("Hilfe"))
        help_menu.setToolTipsVisible(True)
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
        for label, slot in (
            (tr("Neu"), self.action_new),
            (tr("Öffnen"), self.action_open),
            (tr("Speichern"), self.action_save),
            (tr("Modell einfügen"), self.action_import),
        ):
            action = QAction(label, self)
            action.triggered.connect(slot)
            toolbar.addAction(action)

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

    def _connect_session(self) -> None:
        self.session.sceneChanged.connect(self._on_scene)
        self.session.projectChanged.connect(self._on_project)
        self.session.progressChanged.connect(self._on_progress)
        self.session.busyChanged.connect(self._on_busy)
        self.session.askRequested.connect(self._on_ask)
        self.session.failed.connect(self._on_error)
        self.session.proposalReady.connect(self._on_proposal)
        self.session.agentBusyChanged.connect(self._on_agent_busy)
        backend = self.session.agent_backend
        self.chat.set_available(
            backend is not None, f"{backend.id}:{backend.model}" if backend else ""
        )

    # --- actions ----------------------------------------------------------------

    def action_new(self) -> None:
        self.session.start_new(self.settings.printer, self.settings.material)
        self._show_start_screen(False)

    def action_open(self) -> None:
        name, _filter = QFileDialog.getOpenFileName(self, tr("Projekt öffnen"), "", PROJECT_FILTER)
        if name:
            self.open_path(Path(name))

    def open_path(self, path: Path) -> None:
        """Ein Einstiegspunkt für Menü, Zuletzt-Liste und Drag and Drop."""
        try:
            if path.suffix.lower() == PROJECT_SUFFIX:
                self.session.open_project(path)
                self.settings.remember(path)
                save_settings(self.settings)
                self._offer_recovery(path)
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

    def action_auto_split(self) -> None:
        """§25: das gewählte Teil teilen, bis es passt, und die Nähte
        verstiften (§14).
        """
        object_id = self.object_tree.selected()
        if not object_id:
            QMessageBox.information(
                self, tr("Automatisch teilen"), tr("Bitte zuerst ein Objekt auswählen.")
            )
            return

        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            applied = self.session.auto_split(object_id)
        except AppError as error:
            show_error(error, self)
            return
        finally:
            QApplication.restoreOverrideCursor()

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
        dialog = PrintSettingsDialog(
            self.session, self.settings, self, slice_result=self._current_slice()
        )
        dialog.sliced.connect(self._gcode_returned)
        dialog.exec()
        self.settings.print_quality = dialog.settings.quality
        save_settings(self.settings)

    def _current_slice(self) -> SliceResult | None:
        """Die Schichtanalyse des gewählten Körpers, über denselben Cache wie
        die Schichtenvorschau — gerechnet wird sie höchstens einmal."""
        object_id = self.object_tree.selected()
        if object_id is None:
            return None
        found: SliceResult | None = self._slice_of(object_id)
        return found

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

        object_id = self.object_tree.selected()
        result = self.session.last_result
        entry = result.scene.objects.get(object_id) if result and object_id else None
        if entry is not None and metrics.support_mm3 is not None:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                estimate = slice_body(
                    as_mesh_data(entry.mesh), self.session.profile.printer.layer_height
                )
            finally:
                QApplication.restoreOverrideCursor()
            findings.extend(
                gcode.compare(estimate.support_volume, metrics.support_mm3, "support").findings
            )

        self.report.add_findings(findings)
        self._focus_report()
        self.status_message.setText(
            f"{tr('G-Code gelesen')}: {metrics.slicer or tr('unbekannter Slicer')}"
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
        backend = self.session.agent_backend
        self.chat.set_available(
            backend is not None, f"{backend.id}:{backend.model}" if backend else ""
        )

    def action_command_palette(self) -> None:
        """Eine Taste, alles aus dem Register — und die Kürzel lernen sich
        nebenbei (§2.6).
        """
        palette = CommandPalette(parent=self)
        if palette.exec() != CommandPalette.DialogCode.Accepted:
            return
        name = palette.chosen()
        if name:
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
            self.session.apply(tr("Direkt bewegt"), drafts)

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
        self._map_worker = worker
        worker.start()

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
        result = self._slice_of(object_id)
        if result is None or not result.layers:
            self.viewport.set_layer(None)
            return
        self.viewport.set_layer(result.layers[min(index, len(result.layers) - 1)])

    def _slice_of(self, object_id: ObjectId) -> Any:
        result = self.session.last_result
        entry = result.scene.objects.get(object_id) if result else None
        if entry is None:
            return None
        key = (object_id, entry.mesh.triangle_count)
        if key != self._slice_key:
            QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
            try:
                self._slice_cache = slice_body(
                    as_mesh_data(entry.mesh), self.session.profile.printer.layer_height
                )
            finally:
                QApplication.restoreOverrideCursor()
            self._slice_key = key
            self.layer_bar.show_result(self._slice_cache)
        return self._slice_cache

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
        self.chat.set_busy(busy)
        self.status_message.setText(tr("Der Agent denkt nach.") if busy else "")

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
            tr("Bemalen"),
            [OperationDraft(op="paint_slot", inputs=(object_id,), params=params)],
        )

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

    def run_operation(self, spec: OperationSpec) -> None:
        """Menüeintrag, Dialog, Transaktion — derselbe Weg, den auch der Agent
        nehmen wird.
        """
        if self.session.history.discardable and not confirm_discard(
            self.session.history.discardable, self
        ):
            return

        result = self.session.last_result
        objects = list(result.scene.objects) if result else []
        selected = self.object_tree.selected()
        if spec.consumes and not selected:
            QMessageBox.information(
                self,
                str(spec.title),
                tr("Wählen Sie zuerst ein Objekt im Objektbaum."),
            )
            return

        if spec.takes_whole_scene and not objects:
            QMessageBox.information(self, str(spec.title), tr("Die Szene ist leer."))
            return

        dialog = OperationDialog(spec, objects, self, values=self._from_selection(spec, selected))
        if dialog.exec() != OperationDialog.DialogCode.Accepted:
            return
        self.session.apply(
            spec.title,
            [
                OperationDraft(
                    op=spec.name,
                    inputs=inputs_for(spec, objects, selected),
                    params=dialog.values(),
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

        result = self.session.last_result
        objects = list(result.scene.objects) if result else []
        dialog = OperationDialog(spec, objects, self, values=entry.params)
        dialog.setWindowTitle(f"{spec.title} — {tr('Operation')} {op_id}")
        if dialog.exec() != OperationDialog.DialogCode.Accepted:
            return
        self.session.change_params(op_id, dialog.values())

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
        self.object_tree.show_scene(result)
        plates = {entry.plate for entry in result.scene.objects.values()}
        self.explode_bar.show_for(len(result.scene.objects), max(plates, default=0) + 1)
        self.report.show_result(result)
        self.viewport.show_build_volume(self.session.profile)
        self.viewport.show_scene(result)
        low, high = self.viewport.section_range()
        self.section_bar.set_range(low, high)
        self.section_bar.show_capping_state(self.viewport.section_uncapped)
        self.history_panel.show_document(self.session.project.document, result.stopped_at)
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
        self.history_panel.show_document(document)
        self.chat.show_document(document)
        self.setWindowTitle(f"{self.session.title} — {APP_NAME}")

    def _on_progress(self, fraction: float, text: str) -> None:
        self.progress.setValue(int(fraction * 100))
        # Ein leerer Text heißt, der Lauf ist vorbei; die Zeile geht mit
        # ihm weg (§2.8).
        self.status_message.setText(text)

    def _on_busy(self, busy: bool) -> None:
        self.progress.setVisible(busy)
        self.cancel_button.setVisible(busy)
        if not busy:
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

    def _on_selection(self, object_id: str | None) -> None:
        self.viewport.select(object_id)
        # Karte und Schichtanalyse gehören zu einem Körper; ein anderer Körper
        # braucht seine eigenen, also folgen sie der Auswahl, statt zu
        # verweilen.
        self._on_map_changed(self.analysis_bar.chosen())
        self._on_layer_changed(self.layer_bar.index())
        described = describe_selection(self.session.last_result, object_id)
        if described is None:
            self.measurements.clear_selection()
            return
        name, size, volume = described
        self.measurements.show_object(name, size, volume)

    def _on_parameter_edited(self, name: str, value: float) -> None:
        """An einer Zahl zu drehen ist eine Änderung am Dokument, dann eine
        frische Auswertung (§13).
        """
        import dataclasses

        parameters = self.session.project.document.parameters
        if name not in parameters:
            return
        parameters[name] = dataclasses.replace(parameters[name], value=value)
        self.session.evaluate_async()

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
        if self.settings.check_for_updates:
            self._check_for_updates()

    def action_first_run(self) -> None:
        """§38: language, printer, material, external programs. Skippable."""
        dialog = first_run.FirstRunDialog(self.settings, self)
        dialog.importRequested.connect(self.action_import)
        if dialog.exec() == first_run.FirstRunDialog.DialogCode.Accepted:
            dialog.apply_to(self.settings)
        else:
            # Überspringen zählt als erledigt: beim nächsten Mal wieder zu fragen
            # wäre Nörgeln.
            self.settings.first_run_done = True
        save_settings(self.settings)

    def _check_for_updates(self) -> None:
        """§37.2: ein Hinweis mit einem Link. Nichts wird heruntergeladen, nichts
        ersetzt.
        """
        release = updates.check()
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
        self.right.setCurrentWidget(self.report)

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

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802 - Qt name
        self.session.cancel()
        self.session.wait_for_idle(2000)
        worker = self._map_worker
        if worker is not None and worker.isRunning():
            # Eine Karte, die niemand mehr sehen wird — aber ein Thread, der sein
            # Fenster überlebt, nimmt den Prozess mit.
            worker.wait(2000)
        if self.session.modified:
            self.session.autosave()
        save_settings(self.settings)
        event.accept()


def registered_operations() -> list[OperationSpec]:
    """Small helper the palette will use in P1."""
    return list(REGISTRY.all())
