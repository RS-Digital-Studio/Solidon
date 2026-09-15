"""Originaltreffer, lesende Erkundung und eine gemeinsame Übernahme im Hauptfenster."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QDialog

from app.core.scene import EvaluationResult, OperationDraft
from app.core.scene.project import Project, ProjectSources
from app.core.types import Vec3
from app.i18n import _, tr
from app.ui.local_recognition import LocalRecognitionDialog, LocalRecognitionResult
from app.ui.render.api import PointerEvent

if TYPE_CHECKING:
    from app.ui.main_window import MainWindow


class LocalRecognitionFlow(QObject):
    """Eine temporäre Merkmalsauswahl besitzt weder Dokument noch globalen Objektbaum."""

    def __init__(self, window: MainWindow) -> None:
        super().__init__(window)
        self.view = window
        self.dialog: LocalRecognitionDialog | None = None
        self.armed = False
        self._baseline: EvaluationResult | None = None
        self._drafts: tuple[OperationDraft, ...] = ()
        window.session.projectChanged.connect(self.invalidate)

    @property
    def active(self) -> bool:
        return self.armed or self.dialog is not None

    def arm(self) -> None:
        """Menü und Palette sammeln denselben Originaltreffer wie der Rechtsklick."""
        self.invalidate()
        if self.view.session.busy or self.view.session.last_result is None:
            return
        if self.view._op_dialog is not None:
            self.view._op_dialog.reject()
        self.armed = True
        self.view.viewport.set_placement_pointer(self.pointer)
        self.view.announce(
            tr(
                "Klicken Sie auf die Stelle, deren Merkmale Sie erkennen möchten. "
                "Escape beendet die Auswahl."
            )
        )

    def pointer(self, event: PointerEvent) -> bool:
        if not self.active or event.alt or event.ctrl:
            return False
        if event.button != "left" or event.kind not in ("press", "release"):
            return False
        if self.armed and event.kind == "release":
            hit = self.view.viewport.placement_hit(event.x, event.y)
            if hit is None:
                self.view.announce(tr("Auf eine sichtbare Oberfläche zeigen."))
            else:
                self.begin(hit)
        return True

    def begin(self, hit: tuple[str, Vec3, int, tuple[Vec3, Vec3] | None]) -> None:
        """Der gespeicherte Punkt wird vor der ersten Erkennung am Original geprüft."""
        result = self.view.session.last_result
        identifier, point, seed, ray = hit
        entry = result.scene.objects.get(identifier) if result is not None else None
        if result is None or entry is None or entry.kind != "mesh" or self.view.session.busy:
            self.view.announce(tr("Wählen Sie eine sichtbare Oberfläche eines Dreiecksnetzes."))
            return
        if ray is None:
            self.view.announce(
                tr(
                    "Die Oberfläche konnte hier nicht getroffen werden. "
                    "Wählen Sie die Stelle erneut."
                )
            )
            return
        self.invalidate()
        if self.view._op_dialog is not None:
            self.view._op_dialog.reject()
        self._baseline = result
        session = self.view.session
        project = Project(
            document=copy.deepcopy(session.project.document),
            sources=dict(session.project.sources),
        )
        dialog = LocalRecognitionDialog(
            project.document,
            result.scene,
            identifier,
            session.profile,
            point=point,
            normal=(0.0, 0.0, 1.0),
            seed_face=seed,
            original_ray=ray,
            clip_planes=tuple(
                plane for plane in self.view.viewport._section_planes() if plane is not None
            ),
            sources=ProjectSources(project, base_dir=session.base_dir),
            cache=session.cache,
            parent=self.view,
        )
        self.dialog = dialog
        dialog.recognitionReady.connect(self._recognized)
        dialog.featureSelected.connect(self._select)
        dialog.previewRequested.connect(self._preview)
        dialog.previewCleared.connect(self._restore_inspection)
        dialog.draftsReady.connect(self._remember_drafts)
        dialog.finished.connect(self._finished)
        self.view.viewport.set_feature_gizmo_blocked(True)
        self.view.viewport.set_placement_pointer(self.pointer)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.show()

    def _recognized(self, result: LocalRecognitionResult) -> None:
        if self.dialog is None or self.view.session.last_result is not self._baseline:
            return
        self.view.viewport.show_scene(result.evaluation)
        self.view.viewport.select(result.object_id)
        self._select(result.selected)
        self.view.viewport.mark_preview(tr("Lokale Auswahl — noch nicht übernommen"), changes=False)

    def _select(self, identifier: str) -> None:
        if self.dialog is not None:
            self.view.viewport.select_feature(identifier or None)

    def _preview(self, drafts: tuple[OperationDraft, ...]) -> None:
        dialog = self.dialog
        if dialog is None:
            return
        revision = dialog.preview_revision
        reason = {"text": ""}

        def explained(message: str) -> None:
            reason["text"] = message

        def done(difference: object) -> None:
            if self.dialog is not dialog or dialog.preview_revision != revision:
                return
            if difference is None:
                dialog.preview_status(
                    reason["text"]
                    or tr(
                        "Die Vorschau konnte nicht berechnet werden. "
                        "Ändern Sie die Werte und versuchen Sie es erneut."
                    ),
                    revision=revision,
                )
                return
            self.view._show_preview(difference)
            dialog.preview_status(
                reason["text"] or None, getattr(difference, "findings", ()), revision=revision
            )

        def failed(_detail: str) -> None:
            if self.dialog is dialog:
                dialog.preview_status(
                    tr(
                        "Die Vorschau konnte nicht berechnet werden. "
                        "Ändern Sie die Werte und versuchen Sie es erneut."
                    ),
                    revision=revision,
                )

        self.view.session.preview_async(done, list(drafts), explained=explained, failed=failed)

    def _restore_inspection(self) -> None:
        self.view._clear_preview()
        if self.dialog is not None and self.dialog.inspection is not None:
            self._recognized(self.dialog.inspection)
        else:
            self._show_committed()

    def _show_committed(self) -> None:
        """Mit dem Originalbild kehrt auch seine ursprüngliche Auswahl zurück."""
        if self.view.session.last_result is not None:
            self.view.viewport.show_scene(self.view.session.last_result)
            self.view.viewport.select(self.view.object_tree.selected())
            self.view.viewport.select_feature(self.view.object_tree.selected_feature())

    def _remember_drafts(self, drafts: tuple[OperationDraft, ...]) -> None:
        if self.dialog is not None:
            self._drafts = tuple(drafts)

    def _finished(self, code: int) -> None:
        if self.sender() is not self.dialog:
            return
        baseline, drafts = self._baseline, self._drafts
        self.dialog = None
        self._baseline = None
        self._drafts = ()
        self.armed = False
        self.view.viewport.set_placement_pointer(None)
        self.view.viewport.set_feature_gizmo_blocked(False)
        self.view._clear_preview()
        result = self.view.session.last_result
        self._show_committed()
        if code == QDialog.DialogCode.Accepted and drafts and result is baseline:
            title = (
                _("Merkmale erkennen und bearbeiten") if len(drafts) > 1 else _("Merkmale erkennen")
            )
            self.view.session.apply(title, list(drafts))

    def invalidate(self) -> None:
        """Ein anderer Dokumentstand kann keine alte Auswahl übernehmen."""
        if self.dialog is not None:
            self.dialog.invalidate()
        if self.armed:
            self.armed = False
            self.view.viewport.set_placement_pointer(None)

    def release(self, timeout_ms: int = 2000) -> None:
        dialog = self.dialog
        self.invalidate()
        if dialog is not None:
            dialog.release(timeout_ms)
