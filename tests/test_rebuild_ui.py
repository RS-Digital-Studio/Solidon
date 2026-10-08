"""Nachbau über den Bericht: Vorschau, Folgen, Abbruch und eine Übernahme."""

from __future__ import annotations

import time
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QObject, Signal
from PySide6.QtTest import QTest

from app.core.bootstrap import load_operations
from app.core.errors import UserError
from app.core.scene.history import OperationDraft
from app.core.scene.project import new_project
from app.core.scene.rebuild import (
    RebuildApplication,
    RebuildBudget,
    RebuildCandidate,
    RebuildCheck,
    RebuildProposal,
)
from app.i18n import _
from app.ui import rebuild_dialog as rebuild


class RebuildSession(QObject):
    projectChanged = Signal()  # noqa: N815 — Signal der Sitzung
    sceneChanged = Signal(object)  # noqa: N815 — Signal der Sitzung

    def __init__(self, profile):
        super().__init__()
        self.project = new_project("centauri-carbon-2", "petg")
        self.base_dir = None
        self.evaluation_profile = profile


def wait_for(qt_app, predicate, timeout=5, detail=None):
    deadline = time.monotonic() + timeout
    while not predicate() and time.monotonic() < deadline:
        qt_app.processEvents()
        QTest.qWait(10)
    assert predicate(), detail() if detail is not None else "Antwort fehlt"


@pytest.fixture
def rebuilt(qt_app, profile, monkeypatch):
    load_operations()
    session = RebuildSession(profile)
    source = SimpleNamespace(id="obj_1", name="Lochplatte")
    body = SimpleNamespace(id="obj_2", name="Lochplatte")
    rejected = RebuildCandidate((), body, RebuildCheck(False, "unexplained", 0.0))
    accepted = RebuildCandidate(
        (OperationDraft("create_brep_box", params={"width": 20.0}),),
        body,
        RebuildCheck(True, "accepted", 0.001),
    )
    proposal = RebuildProposal(source, RebuildBudget(0.1, 0.01), (rejected, accepted), {})
    application = RebuildApplication(
        proposal,
        accepted.drafts,
        None,
        body,
        (_("Geschützte Sichtflächen müssen am Nachbau erneut gewählt werden."),),
        {},
    )
    calls = []

    def propose(document, object_id, actual_profile, **kwargs):
        calls.append(("propose", document, object_id, kwargs["budget"]))
        return proposal

    def prepare(document, given, candidate, actual_profile, **kwargs):
        calls.append(("prepare", document, given, candidate))
        return application

    monkeypatch.setattr(rebuild, "propose", propose)
    monkeypatch.setattr(rebuild, "prepare_application", prepare)
    dialog = rebuild.RebuildDialog(session, "obj_1")
    try:
        yield dialog, session, proposal, application, calls
    finally:
        dialog.reject()
        dialog.release()
        dialog.deleteLater()


def test_a_checked_candidate_needs_its_visible_preview_and_specific_loss_acceptance(
    qt_app, rebuilt
):
    dialog, session, proposal, application, calls = rebuilt
    shown = []
    dialog.previewRequested.connect(shown.append)
    dialog._start()
    wait_for(qt_app, lambda: dialog.application is application)
    assert calls[0][1] is not session.project.document
    assert calls[0][3] == RebuildBudget(0.1, 0.01)
    assert calls[1][2] is proposal and calls[1][3] is proposal.accepted[0]
    assert dialog.candidates.count() == 2
    assert "Formen fehlen" in dialog.candidates.item(0).text()
    assert "20" in dialog.details.text()
    assert "Sichtflächen" in dialog.losses.text()
    assert shown[-1] is application.result
    assert not dialog.take.isEnabled()
    dialog.accept_losses.setChecked(True)
    assert not dialog.take.isEnabled(), "Ein Rechenergebnis ist noch keine sichtbare Vorschau"
    dialog.preview_ready()
    assert dialog.take.isEnabled()
    dialog.original.setChecked(True)
    assert shown[-1] is None
    dialog.original.setChecked(False)
    assert shown[-1] is application.result
    dialog.candidates.setCurrentRow(0)
    assert dialog.application is None
    assert not dialog.take.isEnabled()
    assert len(calls) == 2, "Ein ungeeigneter Kandidat wird nie zur Übernahme vorbereitet"


@pytest.mark.parametrize(
    ("reasons", "verdict"),
    [
        (("topology", "unexplained"), "Größere Grenzen helfen hier nicht"),
        (("topology", "surface"), "ändern Sie die Grenzen bewusst"),
    ],
)
def test_without_a_passing_candidate_the_verdict_stays_and_nothing_is_preselected(
    qt_app, rebuilt, monkeypatch, reasons, verdict
):
    """Roberts Test von 0.5.2 am Besenhalter: Alle Vorschläge fielen durch,
    vorgewählt wurde trotzdem der erste, und seine Zeile („Dieser Vorschlag
    wird nicht übernommen“) überschrieb das Urteil über alle. Scheitert jeder
    an der Form, sagt der Dialog, dass größere Grenzen nicht helfen; scheitert
    einer an einer Grenze, nennt er die Grenzen."""
    dialog, _session, proposal, _application, calls = rebuilt
    failing = tuple(
        RebuildCandidate((), proposal.source, RebuildCheck(False, reason, float("inf")))
        for reason in reasons
    )
    none_pass = RebuildProposal(proposal.source, proposal.budget, failing, {})
    monkeypatch.setattr(rebuild, "propose", lambda *args, **kwargs: none_pass)

    dialog._start()
    wait_for(qt_app, lambda: dialog.proposal is none_pass)

    assert dialog.candidates.count() == len(reasons)
    assert dialog.candidates.currentRow() == -1, "kein Vorschlag vorgewählt"
    assert verdict in dialog.status.text()
    assert "Dieser Vorschlag wird nicht übernommen" not in dialog.status.text()
    assert not dialog.take.isEnabled()
    assert calls == [], "kein ungeeigneter Kandidat wird zur Übernahme vorbereitet"


def test_changing_a_limit_clears_old_preview_and_loss_acceptance(qt_app, rebuilt):
    dialog, _session, _proposal, application, _calls = rebuilt
    dialog._start()
    wait_for(qt_app, lambda: dialog.application is application)
    dialog.preview_ready()
    dialog.accept_losses.setChecked(True)
    dialog.local_limit.set_value_mm(0.2)
    assert dialog.application is None and dialog.proposal is None
    assert not dialog.accept_losses.isChecked()
    assert not dialog.take.isEnabled()
    assert dialog.start.isEnabled()


def test_incomplete_bounds_explain_unknown_distance_and_reserved_tessellation(
    qt_app, rebuilt, monkeypatch
):
    from dataclasses import replace

    from app.core.geom.difference import SurfaceDistanceBound
    from app.i18n import tr
    from app.ui.labels import length

    dialog, _session, proposal, _application, _calls = rebuilt
    candidate = replace(
        proposal.candidates[0],
        check=RebuildCheck(
            False, "incomplete", 0.0, SurfaceDistanceBound(0.01, float("inf"), 0.09, 40, False)
        ),
    )
    monkeypatch.setattr(
        rebuild, "propose", lambda *args, **kwargs: replace(proposal, candidates=(candidate,))
    )
    dialog.start.click()
    wait_for(qt_app, lambda: dialog.proposal is not None)
    # Ein durchgefallener Vorschlag wird nicht vorgewählt; seine Einzelheiten
    # zeigt er, sobald man ihn anwählt.
    dialog.candidates.setCurrentRow(0)
    lines = dialog.details.text().splitlines()
    # Die obere Schranke ist unbekannt — gesagt, nicht als Zahl erfunden.
    assert any(str(tr("unbekannt")) in line for line in lines), lines
    # Der Vorbehalt für die Vernetzung, als ganzer Satz: Er nennt den
    # reservierten Teil der Formgrenze und dass die flachen Dreiecke des
    # Originals zur Abweichung zählen („Facetten“ ist ein Konstrukteurswort,
    # ``test_wording``).
    reserved = str(
        tr(
            "Von Ihrer Formgrenze bleiben {value} für die Vernetzung des Nachbaus "
            "reserviert. Die flachen Dreiecke des ursprünglichen Modells zählen zur "
            "Abweichung."
        )
    ).format(value=length(dialog.proposal.budget.tessellation_mm))
    assert reserved in lines, lines
    assert not dialog.take.isEnabled()


def test_failed_candidate_evaluation_keeps_its_concrete_finding(qt_app, rebuilt, monkeypatch):
    from dataclasses import replace

    from app.core.types import Finding

    dialog, _session, proposal, _application, _calls = rebuilt
    failure = Finding("test.rebuild", "error", "Der Prüfkörper fehlt; wählen Sie ein anderes Teil.")
    monkeypatch.setattr(
        rebuild,
        "propose",
        lambda *args, **kwargs: replace(proposal, candidates=(), failures=(failure,)),
    )
    dialog._start()
    wait_for(qt_app, lambda: dialog.proposal is not None)
    assert str(failure.message) in dialog.status.text()
    assert not dialog.take.isEnabled()


def test_an_out_of_range_limit_stays_visible_and_blocks_start(rebuilt):
    dialog, *_ = rebuilt
    dialog.volume_limit.lineEdit().setText("101")
    dialog._start()
    assert dialog.volume_limit.refused_value() == 101
    assert not dialog.start.isEnabled()
    assert dialog.status.text()
    assert dialog._worker is None


@pytest.mark.parametrize("ending", ["reject", "project", "scene"])
def test_cancelled_or_replaced_project_ignores_a_late_worker(qt_app, rebuilt, monkeypatch, ending):
    import threading

    dialog, session, proposal, _application, _calls = rebuilt
    entered, finish = threading.Event(), threading.Event()

    def slow(*args, **kwargs):
        entered.set()
        finish.wait(3)
        return proposal

    monkeypatch.setattr(rebuild, "propose", slow)
    dialog._start()
    worker = dialog._worker
    wait_for(qt_app, entered.is_set)
    if ending == "project":
        session.project = new_project("centauri-carbon-2", "pla")
        session.projectChanged.emit()
    elif ending == "scene":
        session.sceneChanged.emit(object())
    else:
        dialog.reject()
    assert worker.cancel.is_cancelled
    worker.completed.emit(proposal)
    finish.set()
    wait_for(qt_app, lambda: not worker.isRunning())
    qt_app.processEvents()
    assert dialog.proposal is None and dialog.application is None
    assert not dialog.take.isEnabled()


@pytest.mark.parametrize("ending", ["cancel", "project", "close"])
def test_visible_report_flow_cleans_up_and_ignores_late_results(qt_app, monkeypatch, ending):
    from pathlib import Path

    from app.core.scene.serialise import document_to_data
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    session = Session()
    window = MainWindow(session, UiSettings())
    workers = []
    try:
        window.open_path(Path(__file__).parent / "data" / "meshes" / "cube_clean.stl")
        assert session.wait_for_idle(60_000)
        qt_app.processEvents()
        source = next(iter(session.last_result.scene.objects))
        window.object_tree.select_object(source)
        window._update_actions()
        before = document_to_data(session.project.document)
        window.selection_operations.rebuild_button.click()
        dialog = window._rebuild_dialog
        assert dialog is not None and not dialog.isModal()
        monkeypatch.setattr(dialog._leash, "start", workers.append)
        dialog._start()
        worker = workers[-1]
        assert not window._quiet_command_allowed()
        session._dirty = False
        if ending == "project":
            window.action_new()
            session.start_new()
        elif ending == "close":
            window.close()
        else:
            dialog.reject()
        qt_app.processEvents()
        assert window._rebuild_dialog is None
        assert worker.cancel.is_cancelled
        assert dialog._closed
        after = document_to_data(session.project.document)
        if ending == "project":
            assert after != before
        else:
            assert after == before
        worker.failed.emit(UserError(_("Dieser Nachbau hat die Formprüfung nicht bestanden.")))
        qt_app.processEvents()
        assert document_to_data(session.project.document) == after
    finally:
        session._dirty = False
        window.close()
        session.release()


def test_worker_failure_and_renderer_failure_leave_apply_blocked(qt_app, rebuilt, monkeypatch):
    dialog = rebuilt[0]

    def failed(*args, **kwargs):
        raise UserError(
            _("Dieser Nachbau hat die Formprüfung nicht bestanden."),
            _("Behalten Sie das ursprüngliche Modell oder prüfen Sie einen anderen Nachbau."),
        )

    monkeypatch.setattr(rebuild, "propose", failed)
    dialog._start()
    wait_for(qt_app, lambda: dialog._worker is None)
    assert "ursprüngliche Modell" in dialog.status.text()
    assert not dialog.take.isEnabled()
    assert dialog.start.isEnabled()


def test_a_renderer_failure_revokes_an_already_displayed_candidate(qt_app, rebuilt):
    dialog, _session, _proposal, application, _calls = rebuilt
    dialog._start()
    wait_for(qt_app, lambda: dialog.application is application)
    dialog.preview_ready()
    dialog.accept_losses.setChecked(True)
    assert dialog.take.isEnabled()
    dialog.preview_failed("Rendererantwort fehlt")
    assert not dialog.take.isEnabled()


def test_a_stale_failure_does_not_replace_a_new_worker(qt_app, rebuilt, monkeypatch):
    dialog = rebuilt[0]
    workers = []
    monkeypatch.setattr(dialog._leash, "start", workers.append)
    dialog._start()
    first = workers[-1]
    dialog.local_limit.set_value_mm(0.2)
    dialog._start()
    second = workers[-1]
    first.crashed.emit("verspäteter Fehler")
    first.progressed.emit(0.5, "veralteter Schritt")
    assert dialog._worker is second
    assert "verspäteter" not in dialog.status.text()
    assert "veralteter" not in dialog.status.text()
    assert first.cancel.is_cancelled


def test_the_rebuild_stands_at_one_chosen_body_in_the_card_of_actions(qt_app):
    """RM-508: *Modell nachbauen* ist eine Handlung am gewählten Körper.

    Bis dahin stand der Knopf im Prüfbericht, auch ohne Auswahl, gesperrt und
    mit einem Satz von elf Wörtern (Durchsicht B19). Jetzt steht er unter den
    Hauptaktionen der Karte, an genau einem Körper ohne gewähltes Merkmal, und
    nur, wenn er geht.
    """
    from app.core.bootstrap import load_operations
    from app.core.registry import REGISTRY
    from app.ui.panels import ReportPanel
    from app.ui.selection_operations import REBUILD, SelectionOperationsPanel

    load_operations()
    panel = SelectionOperationsPanel(REGISTRY.all())
    report = ReportPanel()
    seen = []
    panel.rebuildRequested.connect(lambda: seen.append(True))

    def allowed(_name: str) -> tuple[bool, str]:
        return True, ""

    try:
        assert not hasattr(report, "rebuild"), "der Bericht trägt den Nachbau nicht mehr"
        for selected, kind, rebuild_allowed in ((0, "", True), (2, "", True), (1, "face", True)):
            panel.set_context(selected, allowed, feature_kind=kind, rebuild=rebuild_allowed)
            assert REBUILD not in panel._quick_shown, (selected, kind)
        panel.set_context(1, allowed, rebuild=False)
        assert REBUILD not in panel._quick_shown, "gesperrt steht er nicht da"
        panel.set_context(1, allowed, rebuild=True)
        assert REBUILD in panel._quick_shown
        assert not panel.rebuild_button.isHidden()
        assert panel.rebuild_button.toolTip()
        panel.rebuild_button.click()
        assert seen == [True]
    finally:
        panel.deleteLater()
        report.deleteLater()


@pytest.mark.parametrize("language", ["de", "en", "es", "fr", "it", "pt"])
def test_rebuild_details_scroll_but_actions_stay_reachable(qt_app, profile, language):
    from PySide6.QtCore import QRect

    from app.i18n import get_language, set_language
    from app.ui.settings import UiSettings
    from app.ui.theme import apply_theme

    previous = get_language()
    set_language(language)
    apply_theme(qt_app, UiSettings().theme)
    dialog = rebuild.RebuildDialog(RebuildSession(profile), "obj_1")
    try:
        dialog.show()
        dialog.details.setText("\n".join([dialog.intro.text()] * 30))
        for _round in range(8):
            qt_app.processEvents()
        dialog.resize(600, 430)
        for _round in range(8):
            qt_app.processEvents()
        assert dialog.rect().contains(QRect(dialog.buttons.geometry()))
        assert not dialog._scroll.isAncestorOf(dialog.buttons)
        assert dialog._scroll.verticalScrollBar().maximum() > 0
        assert dialog.local_limit.accessibleName()
        assert dialog.volume_limit.accessibleName()
        assert dialog.candidates.accessibleName()
        assert dialog.take.text()
        dialog.local_limit.setFocus()
        assert dialog.local_limit.hasFocus()
    finally:
        dialog.reject()
        dialog.release()
        dialog.deleteLater()
        set_language(previous)


@pytest.mark.parametrize("take", (True, False))
def test_visible_report_path_uses_the_same_checked_body_and_one_undo(
    qt_app, monkeypatch, tmp_path, take
):
    from pathlib import Path

    from app.core.scene import evaluate
    from app.core.scene.project import ProjectSources, load, save
    from app.core.scene.serialise import document_to_data
    from app.ui.main_window import MainWindow
    from app.ui.session import Session
    from app.ui.settings import UiSettings
    from tests.helpers import exact_kernel

    exact_kernel()
    session = Session()
    window = MainWindow(session, UiSettings())
    try:
        window.open_path(Path(__file__).parent / "data" / "meshes" / "cube_clean.stl")
        assert session.wait_for_idle(60_000)
        qt_app.processEvents()
        source = next(iter(session.last_result.scene.objects))
        window.object_tree.select_object(source)
        window._update_actions()
        assert not window.selection_operations.rebuild_button.isHidden()
        session.project.document.protected[source] = ("face_1",)
        before = document_to_data(session.project.document)
        original = session.last_result
        application = None

        window.selection_operations.rebuild_button.click()
        dialog = window._rebuild_dialog
        assert dialog is not None and not dialog.isModal()
        dialog._start()
        wait_for(
            qt_app,
            lambda: dialog.application is not None,
            timeout=120,
            detail=lambda: (dialog.status.text(), dialog._closed, dialog._worker),
        )
        application = dialog.application
        wait_for(qt_app, lambda: dialog._seen)
        assert not dialog.take.isEnabled()
        dialog.accept_losses.setChecked(True)
        assert dialog.take.isEnabled()
        assert (
            window.viewport._result.scene.objects.get(application.result.id) is application.result
        )
        dialog.original.setChecked(True)
        wait_for(qt_app, lambda: window.viewport.is_scene_applied(original))
        dialog.original.setChecked(False)
        wait_for(qt_app, lambda: dialog.take.isEnabled())
        if take:
            dialog.accept()
        else:
            dialog.reject()
        assert session.wait_for_idle(60_000)
        qt_app.processEvents()
        if not take:
            assert document_to_data(session.project.document) == before
            return
        assert len(session.project.document.transactions) == len(before["transactions"]) + 1
        assert application.result.id in session.last_result.scene.objects
        path = tmp_path / "rebuilt.p3d"
        save(session.project, path)
        reopened = load(path)
        disk = evaluate(
            reopened.document, session.evaluation_profile, sources=ProjectSources(reopened)
        )
        assert disk.complete and application.result.id in disk.scene.objects
        session.undo()
        assert session.wait_for_idle(60_000)
        undone = document_to_data(session.project.document)
        for key in before.keys() - {"numbering", "parts_version"}:
            assert undone[key] == before[key], key
        session.redo()
        assert session.wait_for_idle(60_000)
        assert application.result.id in session.last_result.scene.objects
    finally:
        session._dirty = False
        window.close()
        session.release()
