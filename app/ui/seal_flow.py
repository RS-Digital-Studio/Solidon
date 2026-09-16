"""Dichtwegauswahl an einen festen Operations-Eingang und den normalen Dialog binden."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QDialog
from shiboken6 import isValid

from app.core.scene import EvaluationResult, evaluate
from app.core.scene.cancel import CancelSignal
from app.core.scene.project import Project, ProjectSources
from app.core.sketch.planes import frame_for_plane
from app.i18n import tr
from app.ui.labels import feature_label
from app.ui.seal_dialog import SealPathDialog, SealPathField
from app.ui.sketch_editor import Surroundings

if TYPE_CHECKING:
    from app.ui.main_window import MainWindow
    from app.ui.op_dialog import OperationDialog


class SealFlow(QObject):
    """Der Wahldialog ändert ausschließlich den zusammengehörigen Parameterblock."""

    def __init__(
        self, window: MainWindow, dialog: OperationDialog, *, change_op: int | None = None
    ) -> None:
        super().__init__(dialog)
        self.window, self.host = window, dialog
        field = dialog._editors["path_sketch"]
        assert isinstance(field, SealPathField)
        self.field = field
        self.project = window.session.project
        self.document = copy.deepcopy(self.project.document)
        self.sources = dict(self.project.sources)
        self.profile = copy.deepcopy(window.session.profile)
        self.baseline = window.session.last_result if change_op is None else None
        self.change_op = change_op
        self.editor: SealPathDialog | None = None
        self._cancel = CancelSignal()
        self._closed = False
        self.field.choiceRequested.connect(self.choose)
        self.host.finished.connect(self.close)
        window.session.projectChanged.connect(self._project_changed)

    def _current(self) -> bool:
        return (
            isValid(self)
            and not self._closed
            and self.window.session.project is self.project
            and self.project.document == self.document
        )

    def _project_changed(self) -> None:
        self.close()
        if isValid(self.host):
            self.host.reject()

    def close(self, *_args: object) -> None:
        """Späte Antworten verlieren ihre Gültigkeit; laufende Vorbereitung bricht ab."""
        if self._closed:
            return
        self._closed = True
        self._cancel.cancel()
        self.window.session.projectChanged.disconnect(self._project_changed)
        if self.editor is not None:
            self.editor.reject()

    def choose(self) -> None:
        """Beim Verlauf den Träger vor dem Schnitt lesen, sonst den festen Szenenstand."""
        if not self._current():
            return
        if self.editor is not None:
            self.editor.raise_()
            return
        if self.baseline is not None:
            self._ready(self.baseline)
            return
        self.field.button.setEnabled(False)
        self._previous_summary = self.field.summary.text()
        self.field.summary.setText(tr("Die Oberfläche vor diesem Schritt wird vorbereitet …"))
        document = copy.deepcopy(self.document)
        if self.change_op is not None:
            document.ops[:] = [
                operation for operation in document.ops if operation.id < self.change_op
            ]
        project = Project(document=document, sources=self.sources)
        sources = ProjectSources(project, base_dir=self.window.session.base_dir)
        profile, cache = self.profile, self.window.session.cache
        cancelled = self._cancel
        self.window.session.placement_async(
            lambda: evaluate(document, profile, cache=cache, sources=sources, cancelled=cancelled),
            self._ready,
            self._failed,
        )

    def _failed(self, _detail: object) -> None:
        if self._current():
            self.field.button.setEnabled(True)
            self.field.summary.setText(
                tr("Die Eingabe dieses Schritts prüfen und erneut platzieren.")
            )

    def _ready(self, result: EvaluationResult) -> None:
        if not self._current():
            return
        self.field.button.setEnabled(True)
        if hasattr(self, "_previous_summary"):
            self.field.summary.setText(self._previous_summary)
        inputs = self.host.source_objects
        source = result.scene.objects.get(inputs[0]) if inputs else None
        if not result.complete or source is None:
            self._failed(None)
            return
        self.baseline = result
        objects = tuple(result.scene.objects.values())
        volume = self.profile.printer.build_volume
        surroundings = Surroundings(
            bed=(float(volume[0]), float(volume[1])),
            bodies=tuple(entry.mesh for entry in objects),
            faces=tuple(
                (
                    f"{entry.id}:{feature.id}",
                    f"{entry.name} · {feature_label(feature.id, feature)}",
                    tuple(feature.params["normal"]),
                )
                for entry in objects
                for feature in entry.features.values()
                if feature.kind == "face" and feature.recognised
            ),
            frame_of=lambda plane: frame_for_plane(plane, objects),
        )
        editor = SealPathDialog(
            source,
            objects,
            self.field.selection(),
            parameters=result.scene.parameters,
            parent=self.host,
            surroundings=surroundings,
        )
        self.editor = editor
        editor.finished.connect(self._finished)
        editor.open()

    def _finished(self, code: int) -> None:
        editor, self.editor = self.editor, None
        if editor is None:
            return
        if code == QDialog.DialogCode.Accepted and self._current():
            self.field.set_selection(editor.values())
        editor.deleteLater()
