"""Originaltreffer, lesende Erkundung und eine gemeinsame Übernahme im Hauptfenster."""

from __future__ import annotations

import copy
from typing import TYPE_CHECKING

from PySide6.QtCore import QObject, Qt
from PySide6.QtWidgets import QDialog

from app.core.errors import AppError
from app.core.registry import REGISTRY
from app.core.scene import EvaluationResult, OperationDraft
from app.core.scene.project import Project, ProjectSources
from app.core.types import SceneObject, Vec3
from app.i18n import _, tr
from app.ui.labels import kind_requirement
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
        self._generation: int | None = None
        """Zu welchem Dokument die Auswahl gehört (``Session.project_generation``)."""
        self._drafts: tuple[OperationDraft, ...] = ()
        self._targets: tuple[str, ...] = ()
        window.session.projectChanged.connect(self.invalidate)

    @property
    def active(self) -> bool:
        return self.armed or self.dialog is not None

    def from_report(self, error: AppError) -> None:
        """Der Bericht bindet die Auswahl an seine Körper, niemals an die Baumauswahl."""
        targets = tuple(error.values.get("local_objects", ()))
        if not targets and error.object_id is not None:
            targets = (error.object_id,)
        if targets:
            self.arm(object_ids=targets)

    def _refusal(self, entry: SceneObject | None) -> str:
        """Warum hier gerade keine Stelle gewählt werden kann — je Grund ein Satz.

        Bis zum 24.09.2026 kehrte der Einstieg aus dem Bericht während einer
        Rechnung stumm zurück, und der Klick auf die Oberfläche nannte für eine
        laufende Rechnung denselben Satz wie für einen exakten Körper — mit
        einem Wort, das nur ein Konstrukteur kennt.
        """
        session = self.view.session
        if session.busy or session.last_result is None:
            return tr("Das Modell wird noch gerechnet. Wählen Sie die Stelle, sobald es steht.")
        if entry is not None and entry.kind != "mesh":
            reason = kind_requirement(REGISTRY.get("detect_region"), (entry.kind,))
            if reason:
                return reason
        return tr("Hier liegt keine Oberfläche des Modells. Zielen Sie auf das Modell.")

    def arm(self, *, object_ids: tuple[str, ...] = ()) -> None:
        """Menü und Palette sammeln denselben Originaltreffer wie der Rechtsklick."""
        if not self.view._quiet_command_allowed():
            return
        result = self.view.session.last_result
        if self.view.session.busy or result is None:
            self.view.announce(self._refusal(None))
            return
        refused = next(
            (
                identifier
                for identifier in object_ids
                if identifier not in result.scene.objects
                or result.scene.objects[identifier].kind != "mesh"
            ),
            None,
        )
        if refused is not None:
            self.view.announce(self._refusal(result.scene.objects.get(refused)))
            return
        self.invalidate()
        if self.view._quiet_host is not None:
            self.view.end_quiet_placement()
        if self.view._op_dialog is not None:
            self.view._op_dialog.reject()
        self._targets = tuple(dict.fromkeys(object_ids))
        if self._targets:
            self.view.object_tree.select_objects(self._targets)
        self.armed = True
        self.view.viewport.set_placement_pointer(self.pointer)
        self.view.viewport.set_surface_picker(self._pick_surface)
        self.view.announce(
            tr(
                "Wählen Sie eine Oberfläche: klicken oder mit den Pfeiltasten zielen und die "
                "Eingabetaste drücken. Esc beendet die Auswahl."
            )
        )

    def _pick_again(self) -> None:
        """Eine ungültige Stelle ändert nicht die vom Bericht gemeinten Körper."""
        self.arm(object_ids=self._targets)

    def pointer(self, event: PointerEvent) -> bool:
        if not self.active or event.alt or event.ctrl:
            return False
        if event.button != "left" or event.kind not in ("press", "release"):
            return False
        if self.armed and event.kind == "release":
            self._pick_surface(event.x, event.y)
        return True

    def _pick_surface(self, x: float, y: float) -> None:
        """Maus und Tastatur treffen dieselbe sichtbare Originaloberfläche."""
        if not self.armed:
            return
        hit = self.view.viewport.placement_hit(round(x), round(y))
        if hit is None:
            self.view.announce(self._refusal(None))
        else:
            self.begin(hit)

    def begin(self, hit: tuple[str, Vec3, int, tuple[Vec3, Vec3] | None]) -> None:
        """Der gespeicherte Punkt wird vor der ersten Erkennung am Original geprüft."""
        if not self.view._quiet_command_allowed():
            return
        result = self.view.session.last_result
        identifier, point, seed, ray = hit
        entry = result.scene.objects.get(identifier) if result is not None else None
        if result is None or entry is None or entry.kind != "mesh" or self.view.session.busy:
            self.view.announce(self._refusal(entry))
            return
        if self._targets and identifier not in self._targets:
            self.view.announce(tr("Wählen Sie eine Oberfläche eines markierten Modells."))
            return
        if ray is None:
            self.view.announce(
                tr(
                    "Die Oberfläche konnte hier nicht getroffen werden. "
                    "Wählen Sie die Stelle erneut."
                )
            )
            return
        if self.view._quiet_host is not None:
            self.view.end_quiet_placement()
        targets = self._targets
        self.invalidate()
        self._targets = targets
        if self.view._op_dialog is not None:
            self.view._op_dialog.reject()
        self._baseline = result
        session = self.view.session
        self._generation = session.project_generation
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
            quality=session.quality,
        )
        self.dialog = dialog
        dialog.recognitionReady.connect(self._recognized)
        dialog.featureSelected.connect(self._select)
        dialog.previewRequested.connect(self._preview)
        dialog.previewCleared.connect(self._restore_inspection)
        dialog.draftsReady.connect(self._remember_drafts)
        dialog.pickRequested.connect(self._pick_again)
        dialog.operationRequested.connect(self._run_on_the_body)
        dialog.manualRequested.connect(self.view.action_manual)
        dialog.finished.connect(self._finished)
        self.view.viewport.set_feature_gizmo_blocked(True)
        self.view.viewport.set_placement_pointer(self.pointer)
        dialog.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose)
        dialog.show()

    def _run_on_the_body(self, operation: str, object_id: str) -> None:
        """*Dreiecke verringern* oder *Netz reparieren* am Körper der Suche.

        Die Suche endet dabei — sie gehört dem Netz von vorher —, und der
        gewohnte Dialog der Operation öffnet für genau diesen Körper; die
        Stelle wählt man danach am geänderten Netz neu.
        """
        if self.dialog is not None:
            self.dialog.reject()
        self.view.object_tree.select_objects((object_id,))
        self.view.run_operation(REGISTRY.get(operation))

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
        generation, drafts = self._generation, self._drafts
        self.dialog = None
        self._baseline = None
        self._generation = None
        self._drafts = ()
        self._targets = ()
        self.armed = False
        self.view.viewport.set_placement_pointer(None)
        self.view.viewport.set_surface_picker(None)
        self.view.viewport.set_feature_gizmo_blocked(False)
        self.view._clear_preview()
        self._show_committed()
        # **Dasselbe Dokument, nicht dasselbe Ergebnis.** Ein Export oder ein
        # Neuberechnen liefert ein neues Ergebnis desselben Stands; der
        # Vergleich auf Identität verwarf danach das Übernehmen ohne ein Wort
        # (22.09.2026). Ein geändertes Dokument schließt das Fenster schon
        # vorher (``invalidate`` an ``projectChanged``); ein anderes Dokument
        # erkennt der Zähler.
        if (
            code == QDialog.DialogCode.Accepted
            and drafts
            and generation == self.view.session.project_generation
        ):
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
            self.view.viewport.set_surface_picker(None)
        self._targets = ()

    def release(self, timeout_ms: int = 2000) -> None:
        dialog = self.dialog
        self.invalidate()
        if dialog is not None:
            dialog.release(timeout_ms)
