"""Der Variantengenerator, mit einem Weg hinein (Bauplan §28.3, §25).

Derselbe Stapel, ein paar Mal mit einer gestuften Zahl gerechnet, nebeneinander
auf einer Platte angeordnet: so wird eine Toleranz gemessen statt geraten —
die Reihe drucken, die nehmen, die passt, ihren Wert von der Beschriftung
ablesen.

Die Varianten sind mit Absicht **keine** Szenenobjekte. Die Szene ist, was der
Stapel erzeugt (§15.1), und vier Kopien davon sind keine vier Objekte — sie
sind ein Druckauftrag. Also werden sie gebaut, als Anzahl gezeigt und
herausgeschrieben; das Projekt bleibt, wie es war.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QLabel,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.core.errors import AppError
from app.core.export.writer import plan_export, write_plan
from app.core.log import get_logger
from app.core.scene import build_variants
from app.core.scene.project import ProjectSources
from app.core.scene.variants import MAX_VARIANTS
from app.i18n import tr
from app.ui.dialogs import show_error
from app.ui.session import Session

_log = get_logger(__name__)


class VariantsDialog(QDialog):
    """Einen Parameter und eine Schrittweite wählen, eine Platte voller
    Varianten bekommen.
    """

    def __init__(self, session: Session, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.session = session
        self.setWindowTitle(tr("Varianten erzeugen"))
        self.setMinimumWidth(460)

        document = session.project.document
        self.parameter = QComboBox(self)
        for name, entry in sorted(document.parameters.items()):
            self.parameter.addItem(f"{entry.title or name} ({name})", name)

        self.first = QDoubleSpinBox(self)
        self.first.setRange(-1000.0, 1000.0)
        self.first.setDecimals(3)
        self.step = QDoubleSpinBox(self)
        self.step.setRange(-100.0, 100.0)
        self.step.setDecimals(3)
        self.step.setValue(0.05)
        self.count = QSpinBox(self)
        self.count.setRange(2, MAX_VARIANTS)
        self.count.setValue(4)

        chosen = self.parameter.currentData()
        if chosen is not None:
            self.first.setValue(float(document.parameters[chosen].value))

        form = QFormLayout()
        form.addRow(tr("Parameter"), self.parameter)
        form.addRow(tr("Erster Wert"), self.first)
        form.addRow(tr("Schrittweite"), self.step)
        form.addRow(tr("Anzahl"), self.count)

        self.state = QLabel(
            tr("Die Varianten stehen nebeneinander auf einer Platte und werden exportiert."),
            self,
        )
        self.state.setWordWrap(True)

        self.buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        self.buttons.button(QDialogButtonBox.StandardButton.Ok).setText(tr("Erzeugen"))
        self.buttons.accepted.connect(self._build)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.state)
        layout.addWidget(self.buttons)

        if not document.parameters:
            self.state.setText(
                tr("Dieses Projekt hat keine Parameter — ohne einen gibt es nichts zu variieren.")
            )
            self.buttons.button(QDialogButtonBox.StandardButton.Ok).setEnabled(False)

    def _build(self) -> None:
        name = self.parameter.currentData()
        if name is None:
            return

        project = self.session.project
        try:
            made = build_variants(
                project.document,
                self.session.profile,
                parameter=str(name),
                first=self.first.value(),
                step=self.step.value(),
                count=self.count.value(),
                sources=ProjectSources(project),
            )
        except AppError as error:
            show_error(error, self)
            return

        if not made.complete:
            # §28.3: a set with a hole in it is not a calibration print.
            self.state.setText(tr("Nicht jede Variante ließ sich rechnen — siehe Prüfbericht."))

        objects = list(made.scene(self.session.profile).objects.values())
        if not objects:
            self.state.setText(tr("Es ist keine Variante übrig geblieben."))
            return

        directory = QFileDialog.getExistingDirectory(self, tr("Varianten exportieren"))
        if not directory:
            return

        title = self.session.path.stem if self.session.path else tr("Varianten")
        plan = plan_export(objects, project_name=f"{title}_{name}", profile=self.session.profile)
        written = write_plan(plan, Path(directory))
        _log.info("wrote %d variant file(s)", len(written))
        self.state.setText(f"{len(written)} {tr('Dateien geschrieben')}")
        self.accept()
