"""The main window (Bauplan §2.5).

Three visible zones at most: the panels on the left, the viewport in the middle,
report or chat on the right — and the right side folds away entirely with one
key. There are no modes; there is one state, and that is the scene.

The menu is not written out here either: it is built from the registry, so an
operation appears in the menu, in the palette and on the command line from the
moment it is declared (§10).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtGui import QAction, QCloseEvent, QDragEnterEvent, QDropEvent, QKeySequence
from PySide6.QtWidgets import (
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
from app.core.errors import AppError
from app.core.log import get_logger
from app.core.registry import REGISTRY, OperationSpec, menu_tree
from app.core.scene import EvaluationResult, OperationDraft
from app.core.scene.project import find_recovery
from app.i18n import tr
from app.ui.dialogs import AboutDialog, AskDialog, confirm_discard, show_error
from app.ui.op_dialog import OperationDialog
from app.ui.panels import (
    ChatPlaceholder,
    HistoryPanel,
    MeasurementLabel,
    ObjectTree,
    ParameterPanel,
    ReportPanel,
    collapsible,
    describe_selection,
)
from app.ui.section_bar import SectionBar
from app.ui.session import AskRequest, Session
from app.ui.settings import UiSettings, save_settings
from app.ui.start_screen import StartScreen, accepted_path
from app.ui.viewport import Viewport

_log = get_logger(__name__)

AUTOSAVE_INTERVAL_MS = 120_000

PROJECT_FILTER = f"{APP_NAME} ({'*' + PROJECT_SUFFIX})"
MODEL_FILTER = "Modelle (*.stl *.3mf *.obj *.glb *.gltf *.ply *.off)"


class MainWindow(QMainWindow):
    """Window, menus and the wiring between session and panels."""

    projectOpened = Signal(Path)

    def __init__(self, session: Session, settings: UiSettings) -> None:
        super().__init__()
        self.session = session
        self.settings = settings
        self.setAcceptDrops(True)
        self.setWindowTitle(APP_NAME)
        self.resize(1280, 820)

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

        left = QWidget(self)
        left_layout = QVBoxLayout(left)
        left_layout.setContentsMargins(0, 0, 0, 0)
        left_layout.setSpacing(4)
        left_layout.addWidget(collapsible(tr("Objekte"), self.object_tree), stretch=2)
        left_layout.addWidget(collapsible(tr("Parameter"), self.parameters), stretch=1)
        left_layout.addWidget(collapsible(tr("Verlauf"), self.history_panel), stretch=1)

        self.viewport = Viewport(self)
        self.section_bar = SectionBar(self)
        self.section_bar.sectionChanged.connect(self._on_section)

        middle = QWidget(self)
        middle_layout = QVBoxLayout(middle)
        middle_layout.setContentsMargins(0, 0, 0, 0)
        middle_layout.setSpacing(0)
        middle_layout.addWidget(self.viewport, stretch=1)
        middle_layout.addWidget(self.section_bar)

        self.report = ReportPanel(self)
        self.chat = ChatPlaceholder(self)

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
        self._add_action(file_menu, tr("Neu"), QKeySequence.StandardKey.New, self.action_new)
        self._add_action(file_menu, tr("Öffnen …"), QKeySequence.StandardKey.Open, self.action_open)
        self._add_action(
            file_menu, tr("Speichern"), QKeySequence.StandardKey.Save, self.action_save
        )
        self._add_action(
            file_menu, tr("Speichern unter …"), QKeySequence.StandardKey.SaveAs, self.action_save_as
        )
        file_menu.addSeparator()
        self._add_action(file_menu, tr("Modell einfügen …"), "Ctrl+I", self.action_import)
        file_menu.addSeparator()
        self._add_action(file_menu, tr("Beenden"), QKeySequence.StandardKey.Quit, self.close)

        edit_menu = self.menuBar().addMenu(tr("Bearbeiten"))
        self.undo_action = self._add_action(
            edit_menu, tr("Rückgängig"), QKeySequence.StandardKey.Undo, self.action_undo
        )
        self.redo_action = self._add_action(
            edit_menu, tr("Wiederholen"), QKeySequence.StandardKey.Redo, self.action_redo
        )

        # Everything below comes from the registry (§10).
        for section in menu_tree():
            menu = self.menuBar().addMenu(str(section.title))
            for spec in section.entries:
                action = QAction(str(spec.title), self)
                if spec.shortcut:
                    action.setShortcut(QKeySequence(spec.shortcut))
                action.setStatusTip(str(spec.doc))
                action.triggered.connect(
                    lambda _checked=False, entry=spec: self.run_operation(entry)
                )
                menu.addAction(action)

        view_menu = self.menuBar().addMenu(tr("Ansicht"))
        self._add_action(view_menu, tr("Rechten Bereich zeigen"), "F9", self.action_toggle_right)
        view_menu.addSeparator()

        for mode, label, shortcut in (
            ("solid", tr("Massiv"), "1"),
            ("solid_edges", tr("Massiv mit Kanten"), "2"),
            ("wireframe", tr("Drahtgitter"), "3"),
            ("transparent", tr("Transparent"), "4"),
        ):
            self._add_action(
                view_menu,
                label,
                shortcut,
                lambda checked=False, key=mode: self.viewport.set_display_mode(key),
            )
        view_menu.addSeparator()
        for shading, label in (
            ("flat", tr("Flache Schattierung")),
            ("smooth", tr("Weiche Schattierung")),
        ):
            self._add_action(
                view_menu,
                label,
                None,
                lambda checked=False, key=shading: self.viewport.set_shading(key),
            )
        for projection, label, shortcut in (
            ("perspective", tr("Perspektivisch"), "5"),
            ("orthographic", tr("Orthografisch"), "6"),
        ):
            self._add_action(
                view_menu,
                label,
                shortcut,
                lambda checked=False, key=projection: self.viewport.set_projection(key),
            )
        view_menu.addSeparator()
        for name, label in (
            ("iso", tr("Isometrisch")),
            ("front", tr("Vorne")),
            ("back", tr("Hinten")),
            ("left", tr("Links")),
            ("right", tr("Rechts")),
            ("top", tr("Oben")),
            ("bottom", tr("Unten")),
        ):
            self._add_action(
                view_menu, label, None, lambda checked=False, key=name: self.viewport.view_from(key)
            )
        view_menu.addSeparator()
        for scheme, label in (
            ("slicer", tr("Navigation: Slicer")),
            ("cad", tr("Navigation: CAD")),
            ("blender", tr("Navigation: Blender")),
        ):
            self._add_action(
                view_menu,
                label,
                None,
                lambda checked=False, key=scheme: self.action_navigation(key),
            )

        help_menu = self.menuBar().addMenu(tr("Hilfe"))
        self._add_action(help_menu, tr("Über Formwerk"), None, self.action_about)

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

    def _add_action(self, menu: Any, label: str, shortcut: Any, slot: Any) -> QAction:
        action = QAction(label, self)
        if shortcut is not None:
            action.setShortcut(
                shortcut
                if isinstance(shortcut, QKeySequence.StandardKey)
                else QKeySequence(shortcut)
            )
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

    # --- actions ----------------------------------------------------------------

    def action_new(self) -> None:
        self.session.start_new(self.settings.printer, self.settings.material)
        self._show_start_screen(False)

    def action_open(self) -> None:
        name, _filter = QFileDialog.getOpenFileName(self, tr("Projekt öffnen"), "", PROJECT_FILTER)
        if name:
            self.open_path(Path(name))

    def open_path(self, path: Path) -> None:
        """One entry point for menu, recent list and drag and drop."""
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

    def action_undo(self) -> None:
        self.session.undo()

    def action_redo(self) -> None:
        self.session.redo()

    def action_toggle_right(self) -> None:
        visible = not self.settings.right_panel_visible
        self.right.setVisible(visible)
        self.settings.right_panel_visible = visible
        save_settings(self.settings)

    def action_about(self) -> None:
        AboutDialog(self).exec()

    def _on_section(self, plane: object, thickness: object) -> None:
        self.viewport.set_section(plane, thickness)  # type: ignore[arg-type]
        self.section_bar.show_capping_state(self.viewport.section_uncapped)

    def action_navigation(self, scheme: str) -> None:
        self.viewport.set_navigation(scheme)  # type: ignore[arg-type]
        self.settings.navigation = scheme
        save_settings(self.settings)

    def run_operation(self, spec: OperationSpec) -> None:
        """Menu entry, dialog, transaction — the same path the agent will take."""
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

        dialog = OperationDialog(spec, objects, self)
        if dialog.exec() != OperationDialog.DialogCode.Accepted:
            return
        inputs = (selected,) if spec.consumes and selected else ()
        self.session.apply(
            spec.title,
            [OperationDraft(op=spec.name, inputs=inputs, params=dialog.values())],
        )

    # --- session replies --------------------------------------------------------

    def _on_scene(self, result: EvaluationResult) -> None:
        self.object_tree.show_scene(result)
        self.report.show_result(result)
        self.viewport.show_build_volume(self.session.profile)
        self.viewport.show_scene(result)
        low, high = self.viewport.section_range()
        self.section_bar.set_range(low, high)
        self.section_bar.show_capping_state(self.viewport.section_uncapped)
        self.history_panel.show_document(self.session.project.document, result.stopped_at)
        if result.stopped_at is not None:
            # §15.3: the last complete state stays visible, the status bar says why.
            self.status_message.setText(tr("Die Kette hält an — siehe Prüfbericht."))
            self._focus_report()
        elif self.report.worst_severity(result) in ("warning", "error"):
            self._focus_report()

    def _on_project(self) -> None:
        document = self.session.project.document
        self.parameters.show_document(document)
        self.history_panel.show_document(document)
        self.setWindowTitle(f"{self.session.title} — {APP_NAME}")

    def _on_progress(self, fraction: float, text: str) -> None:
        self.progress.setValue(int(fraction * 100))
        # An empty text means the run is over; the line goes away with it (§2.8).
        self.status_message.setText(text)

    def _on_busy(self, busy: bool) -> None:
        self.progress.setVisible(busy)
        self.cancel_button.setVisible(busy)
        if not busy:
            self.status_message.setText("")

    def _on_ask(self, request: AskRequest) -> None:
        """The worker waits while this dialog is open (§21.3)."""
        dialog = AskDialog(request.question, request.choices, self)
        if dialog.exec() == AskDialog.DialogCode.Accepted:
            request.reply(dialog.chosen())
        else:
            request.reply(None)

    def _on_error(self, error: AppError) -> None:
        show_error(error, self)

    def _on_selection(self, object_id: str | None) -> None:
        self.viewport.select(object_id)
        described = describe_selection(self.session.last_result, object_id)
        if described is None:
            self.measurements.clear_selection()
            return
        name, size, volume = described
        self.measurements.show_object(name, size, volume)

    def _on_parameter_edited(self, name: str, value: float) -> None:
        """Turning a number is a change to the document, then a fresh evaluation (§13)."""
        import dataclasses

        parameters = self.session.project.document.parameters
        if name not in parameters:
            return
        parameters[name] = dataclasses.replace(parameters[name], value=value)
        self.session.evaluate_async()

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
        if self.session.modified:
            self.session.autosave()
        save_settings(self.settings)
        event.accept()


def registered_operations() -> list[OperationSpec]:
    """Small helper the palette will use in P1."""
    return list(REGISTRY.all())
