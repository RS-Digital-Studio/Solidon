"""Sichtbare Grundlage, Einzelheiten und Rückwege des Prüfberichts (RM-090)."""

from contextlib import suppress

import pytest
from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from app.core.scene import EvaluationResult
from app.core.types import Finding, Report, Scene
from app.ui.panels import ReportPanel
from tests.helpers import make_object


@pytest.mark.parametrize(
    "code, source, location",
    [
        ("mesh.open", "internal", (0.0, 0.0, 1.0)),
        ("wall.thin", "internal", (1.0, 0.0, 1.0)),
        ("overhang", "internal", None),
        ("profiles.missing", "internal", None),
        ("slice.island", "internal", (1.0, 1.0, 2.0)),
        ("gcode.time", "gcode", None),
    ],
)
def test_finding_details_are_visible_by_keyboard_and_clear_with_the_result(
    qt_app, code, source, location
):
    finding = Finding(
        code,
        "warning",
        "Prüfbefund",
        object_id="a",
        source=source,
        location=location,
        values={"value": 1.2, "unit": "mm"},
    )
    panel = ReportPanel()
    try:
        panel.show_result(
            EvaluationResult(Scene(objects={"a": make_object("a")}, report=Report((finding,))))
        )
        panel.list.setCurrentRow(0)
        assert panel.finding_context.text()
        assert (
            "aus G-Code" if source == "gcode" else "intern geschätzt"
        ) in panel.finding_context.text()
        QTest.keyClick(panel.finding_details_toggle, Qt.Key.Key_Space)
        assert not panel.finding_details.isHidden()
        assert (
            "1,20" in panel.finding_details.toPlainText()
            or "1.2" in panel.finding_details.toPlainText()
        )
        selected = []
        panel.findingActivated.connect(selected.append)
        panel.finding_place.click()
        assert selected == [finding]
        panel.show_result(None)
        assert panel.finding_context.isHidden()
        assert panel.finding_details.isHidden()
        assert not panel.finding_details.toPlainText()
    finally:
        panel.close()
        panel.deleteLater()


def test_empty_findings_do_not_claim_print_readiness(qt_app):
    panel = ReportPanel()
    try:
        panel.show_result(EvaluationResult(Scene(objects={"a": make_object("a")})))
        assert "Bewertung unvollständig" in panel.summary.text()
        assert "druckbereit" not in panel.summary.text().casefold()
        panel.set_review_context("Geometrieprüfung: ganze Szene", ())
        assert "Bereit zur Übergabe" in panel.summary.text()
        panel.add_findings([Finding("problem", "error", "Schwerer Befund")])
        panel.set_review_context("Geometrieprüfung: ganze Szene", ("Zielprofil fehlt",))
        assert "Übergabe nicht empfohlen" in panel.summary.text()
        assert "Zielprofil fehlt" in panel.review_scope.text()
        assert not panel.to_slicer.isHidden(), "trotz Risiko bleibt die Vorbereitung erreichbar"
    finally:
        panel.close()
        panel.deleteLater()


def test_review_scope_keeps_a_long_list_scrollable_and_deduplicates_states(qt_app):
    from app.ui.style import TARGET_SIZE

    panel = ReportPanel()
    try:
        rows = [f"Körper {index}: läuft" for index in range(30)]
        panel.set_review_context("\n".join(rows), tuple(rows))
        panel.resize(360, 600)
        panel.show()
        panel.review_toggle.click()
        qt_app.processEvents()
        assert panel.review_scope.text().splitlines() == rows
        assert panel.review_scroll.height() <= 4 * TARGET_SIZE
        assert panel.review_scroll.verticalScrollBar().maximum() > 0
    finally:
        panel.close()
        panel.deleteLater()


def test_empty_report_stays_compact_beside_a_taller_hidden_tab(qt_app):
    from PySide6.QtWidgets import QLabel, QTabWidget, QVBoxLayout, QWidget

    from app.ui.overlay import natural_height
    from app.ui.style import TARGET_SIZE

    tabs = QTabWidget()
    panel = ReportPanel()
    other = QWidget()
    layout = QVBoxLayout(other)
    label = QLabel("Großer verborgener Reiter")
    label.setMinimumHeight(700)
    layout.addWidget(label)
    tabs.addTab(panel, "Bericht")
    tabs.addTab(other, "Andere Seite")
    try:
        panel.show_result(EvaluationResult(Scene(objects={"a": make_object("a")})))
        panel.set_review_context("\n".join(f"Körper {i}: läuft" for i in range(30)), ())
        tabs.resize(360, 850)
        tabs.show()
        qt_app.processEvents()
        collapsed = natural_height(tabs)
        assert collapsed < 400, "ein verborgener Reiter bestimmt nicht die Kartenhöhe"
        assert panel.summary.height() <= panel.summary.heightForWidth(panel.summary.width()) + 2
        panel.review_toggle.click()
        qt_app.processEvents()
        assert natural_height(tabs) <= collapsed + 4 * TARGET_SIZE + 20
        panel.add_findings([Finding(f"note.{i}", "info", f"Befund {i}") for i in range(30)])
        qt_app.processEvents()
        assert not panel.list.isVisibleTo(panel), "Hinweise allein beginnen zugeklappt (RM-508)"
        panel.list_toggle.click()
        qt_app.processEvents()
        assert panel.list.height() > panel.review_scroll.height()
    finally:
        tabs.close()
        tabs.deleteLater()


@pytest.mark.parametrize("code", ["repair.holes_filled", "ingest.multiple_components"])
def test_batch_import_bundles_notes_and_keeps_every_body_and_original_detail(qt_app, code):
    from dataclasses import replace

    from app.core.scene import History, OperationDraft
    from app.core.scene.project import new_project
    from app.ui.panels import _BODIES_ROLE

    project = new_project()
    history = History(project.document)
    transaction = history.apply(
        "Piratenschiff",
        [OperationDraft(op="load", params={"source": f"source_{index}"}) for index in range(17)],
    )
    bodies = {
        f"obj_{index}": replace(make_object(f"obj_{index}"), name=f"obj_{index}")
        for index in transaction.ops
    }
    findings = tuple(
        Finding(
            code,
            "info",
            "Ein Loch wurde geschlossen.",
            object_id=f"obj_{index}",
            op_id=index,
            values={"holes": index},
        )
        for index in transaction.ops
    )
    panel = ReportPanel()
    try:
        panel.show_result(
            EvaluationResult(Scene(objects=bodies, report=Report(findings))), project.document
        )
        assert panel.list.count() == 1
        item = panel.list.item(0)
        assert item.text().startswith("(17)")
        assert set(item.data(_BODIES_ROLE)) == set(bodies)
        assert item.data(Qt.ItemDataRole.UserRole).op_id is None
        panel.list.setCurrentRow(0)
        panel.finding_details_toggle.click()
        for identifier in bodies:
            assert identifier in panel.finding_details.toPlainText()
        selected = []
        panel.bundleActivated.connect(lambda _finding, identifiers: selected.append(identifiers))
        panel.finding_place.click()
        assert set(selected[0]) == set(bodies)
        assert panel._findings == list(findings), "Originalbefunde bleiben vollständig erhalten"
    finally:
        panel.deleteLater()


def test_nested_part_notes_bundle_per_wording_and_select_exactly_their_bodies(qt_app):
    """RM-131 NM 1: gleiche Meldung zu enthaltenen Teilen bildet je Wortlaut ein Bündel.

    Am Piratenschiff: zwei Teile an obj2/8/11/14, fünf an obj3/4, sieben an
    obj6/7/13, dazu kleine Einzelteile an zwei Körpern. Jedes Bündel nennt
    beim Aufklappen jede Originalmeldung mit dem Körpernamen und wählt beim
    Klick genau seine Körper.
    """
    from app.core.errors import RESOLVE_INTERSECTIONS, SPLIT_BODIES
    from app.core.scene import History, OperationDraft
    from app.core.scene.project import new_project
    from app.i18n import _
    from app.ui.panels import _BODIES_ROLE

    project = new_project()
    history = History(project.document)
    transaction = history.apply(
        "Piratenschiff",
        [OperationDraft(op="load", params={"source": f"source_{index}"}) for index in range(17)],
    )
    ops = list(transaction.ops)
    bodies = {
        f"obj_{op}": make_object(f"obj_{op}", f"Segel {number}") for number, op in enumerate(ops)
    }

    def nested(number: int, parts: int) -> Finding:
        message = (
            _("Das Modell besteht aus zwei Teilen, die ineinanderstecken.")
            if parts == 2
            else _(
                "Das Modell besteht aus {components} Teilen, von denen manche ineinanderstecken.",
                components=parts,
            )
        )
        return Finding(
            "ingest.multiple_components",
            "info",
            message,
            object_id=f"obj_{ops[number]}",
            op_id=ops[number],
            values={"components": parts},
            suggestions=(RESOLVE_INTERSECTIONS, SPLIT_BODIES),
        )

    groups = {2: (2, 8, 11, 14), 5: (3, 4), 7: (6, 7, 13)}
    findings = [nested(number, parts) for parts, numbers in groups.items() for number in numbers]
    findings += [
        Finding(
            "ingest.small_components",
            "warning",
            _("Es gibt sehr kleine Einzelteile. Gelöscht wurde nichts."),
            object_id=f"obj_{ops[number]}",
            op_id=ops[number],
            values={"count": 3},
        )
        for number in (1, 9)
    ]
    panel = ReportPanel()
    try:
        panel.show_result(
            EvaluationResult(Scene(objects=bodies, report=Report(tuple(findings)))),
            project.document,
        )
        selected: list[tuple[str, ...]] = []
        panel.bundleActivated.connect(lambda _finding, keys: selected.append(tuple(keys)))
        expected = {
            frozenset(f"obj_{ops[number]}" for number in numbers)
            for numbers in (*groups.values(), (1, 9))
        }
        seen = set()
        assert panel.list.count() == len(expected)
        for row in range(panel.list.count()):
            item = panel.list.item(row)
            members = frozenset(item.data(_BODIES_ROLE))
            assert members in expected, item.text()
            seen.add(members)
            assert item.text().startswith(f"({len(members)})")
            panel.list.setCurrentRow(row)
            panel.finding_details_toggle.click()
            details = panel.finding_details.toPlainText()
            for key in members:
                assert str(bodies[key].name) in details, (key, details)
            panel.finding_place.click()
            assert frozenset(selected[-1]) == members
        assert seen == expected
        assert panel._findings == findings, "keine Originalmeldung geht verloren"
    finally:
        panel.deleteLater()


def test_real_evaluation_exposes_checks_and_invalidates_them_on_replacement(qt_app):
    from app.core.scene import OperationDraft
    from app.core.types import CheckState
    from app.ui.session import Session, _EvaluationWorker

    session = Session()
    try:
        session.project.document.printer = ""
        session.project.document.material = ""
        session.history.apply("Quader", [OperationDraft(op="create_box")])
        session.evaluate_async()
        assert session.wait_for_idle()
        states = session.last_result.check_states
        assert any(state.key == "evaluation" and state.state == "completed" for state in states)
        assert any(state.missing_basis for state in states), (
            "fehlende Originalprofile bleiben offen"
        )
        old = _EvaluationWorker(session)
        before = dict(session.check_states)
        session._on_check_state(CheckState("late", state="completed"), finished=old)
        assert session.check_states == before
        old.deleteLater()
    finally:
        session.release()


def test_unknown_imported_printer_is_named_and_a_profile_change_reassesses(qt_app):
    """RM-090 NM 1/3: Ein unbekanntes Druckerprofil gilt nie als bestätigt.

    Kopfzeile und Bericht nennen dieselbe fehlende Grundlage, der Status bleibt
    „Bewertung unvollständig“ und nie „druckbereit“. Ein Wechsel auf ein
    bekanntes Profil ist eine Transaktion und entfernt den Grund; Undo bringt
    ihn zurück.
    """
    from app.core.scene import OperationDraft
    from tests.ui_helpers import shown_window

    windows = shown_window(qt_app)
    window = next(windows)
    try:
        session = window.session
        session.project.document.printer = "fremder-drucker-aus-3mf"
        session.apply("Quader", [OperationDraft(op="create_box")])
        assert session.wait_for_idle(60_000)
        qt_app.processEvents()
        # Die Kopfzeile kürzt sichtbar nach Platz; Volltext, Vorleser und Test
        # lesen ``full_text`` (offscreen gibt es keine echte Schriftbreite).
        assert "fremder-drucker-aus-3mf" in window.header.printer.full_text()
        assert "unvollständig" in window.header.printer.full_text()
        assert "Druckerprofil fehlt" in window.header.printer.toolTip()
        summary = window.report.summary.text()
        assert summary.startswith("Bewertung unvollständig"), summary
        assert "druckbereit" not in summary.casefold()
        assert "Druckerprofil fehlt" in window.report.review_scope.text()
        assert session.change_scene_profile("centauri-carbon-2", session.project.document.material)
        assert session.wait_for_idle(60_000)
        qt_app.processEvents()
        assert "unvollständig" not in window.header.printer.full_text()
        assert "Druckerprofil fehlt" not in window.report.review_scope.text()
        session.undo()
        assert session.wait_for_idle(60_000)
        qt_app.processEvents()
        assert "Druckerprofil fehlt" in window.header.printer.toolTip()
    finally:
        # Ein geändertes Projekt fragt beim Schließen — offscreen wartete das ewig.
        window._may_discard = lambda: True
        with suppress(StopIteration):
            next(windows)


def test_layer_status_ignores_replaced_jobs_and_preserves_cancellation(qt_app):
    from types import SimpleNamespace

    from PySide6.QtCore import QObject

    from app.core.knowledge import print_settings, profiles
    from app.core.types import CheckState
    from app.ui.print_findings_flow import PrintFindingsFlow

    class Owner(QObject):
        def current(self, result):
            return result is self.result

    owner = Owner()
    owner.result = EvaluationResult(Scene(objects={"a": make_object("a")}))
    leash = SimpleNamespace(start=lambda worker: None, retire=lambda worker: None)
    flow = PrintFindingsFlow(owner, leash, owner.current)
    profile = profiles.make_profile("centauri-carbon-2", "petg")
    settings = print_settings.resolve(profile)
    flow.start(owner.result, profile, settings, fitted=False)
    old = flow.worker
    flow._checked(CheckState("slice.print_findings", "a", state="running"), owner.result, old)
    flow.cancel()
    assert flow.check_states["slice.print_findings", "a"].state == "cancelled"
    flow.start(owner.result, profile, settings, fitted=False)
    latest = flow.worker
    flow._checked(CheckState("slice.print_findings", "a", state="completed"), owner.result, old)
    assert not flow.check_states
    flow._checked(CheckState("slice.print_findings", "a", state="failed"), owner.result, latest)
    assert flow.check_states["slice.print_findings", "a"].state == "failed"
    flow.cancel()
    old.deleteLater()
    latest.deleteLater()


@pytest.mark.parametrize("stop", ["cancel", "failure", "crash"])
def test_slicer_receipt_names_only_written_plates_and_successful_opens(
    qt_app, monkeypatch, tmp_path, stop
):
    from pathlib import Path
    from types import SimpleNamespace

    from app.core.errors import UserError
    from app.core.knowledge import print_settings, profiles
    from app.ui import print_settings_dialog as module

    profile = profiles.make_profile("centauri-carbon-2", "petg")
    bodies = (make_object("a", "Rumpf"), make_object("b", "Segel"))
    bodies[1].plate = 1
    job = module._PlateJob(
        bodies,
        (0, 1),
        tmp_path,
        "Schiff",
        module.handover.SlicerSetup(Path("PrusaSlicer.exe"), "prusa"),
        print_settings.resolve(profile),
        profile,
        {},
        with_settings=False,
    )
    worker = module._OpenInSlicerWorker(job)
    monkeypatch.setattr(module, "prepare_usage", lambda *args, **kwargs: ())
    monkeypatch.setattr(
        module,
        "_prepare_plate",
        lambda job, plate: SimpleNamespace(
            model=tmp_path / f"plate-{plate}.3mf",
            slots=(),
            findings=(Finding("export.loss", "warning", f"Verlust auf Platte {plate}"),),
        ),
    )
    opened = []

    def open_file(path, setup):
        if opened and stop == "crash":
            raise RuntimeError("Unerwarteter Prozessfehler")
        if opened and stop == "failure":
            raise UserError("Testfehler")
        opened.append(path)
        if stop == "cancel":
            worker.cancel()

    monkeypatch.setattr(module.handover, "open_in_slicer", open_file)
    receipts = []
    worker.receipt.connect(receipts.append)
    if stop == "crash":
        with pytest.raises(RuntimeError, match="Prozessfehler"):
            worker.work()
    else:
        worker.work()
    assert len(receipts) == 1
    details = receipts[0].values["detail"]
    assert "erfolgreich geöffnete Dateien: 1" in details
    assert ("1 von 2 Körpern" if stop == "cancel" else "2 von 2 Körpern") in details
    assert "Rumpf" in details
    assert ("Segel" in details) is (stop != "cancel")
    assert ("plate-1.3mf" in details) is (stop != "cancel")
    assert "Verlust auf Platte 0" in details
    assert ("Verlust auf Platte 1" in details) is (stop != "cancel")
    assert "noch nicht erzeugt" not in details, "ein Teilfehler darf keine Erfolgsquittung tragen"
    worker.deleteLater()


def test_material_preview_explains_its_target_without_a_geometry_change(qt_app, tmp_path):
    from app.core.scene import OperationDraft
    from app.core.scene.project import load
    from app.ui.session import Session

    session = Session()
    try:
        session.apply("Platte", [OperationDraft(op="create_box", params={"name": "Platte"})])
        assert session.wait_for_idle()
        body_id = next(iter(session.last_result.scene.objects))
        before = len(session.history.transactions)
        draft = OperationDraft(op="set_material", inputs=(body_id,), params={"material": "petg"})
        scene, difference, reason = session._preview_outcome([draft])
        assert scene.objects[body_id].material == "petg"
        assert reason == "Dieser Körper wird in einem eigenen Material gerechnet."
        assert difference is not None and not difference.changed
        assert "Platte" in difference.explanation
        assert "Material „Platte“:" in difference.explanation and "PETG" in difference.explanation
        # Das Außenmaß bleibt — und was bleibt, steht nicht da (RM-516).
        assert "Außenmaß" not in difference.explanation and " × " not in difference.explanation
        assert "Druckbefunde noch nicht geprüft" in difference.explanation
        assert len(session.history.transactions) == before
        session.apply("Material festlegen", [draft])
        assert session.wait_for_idle()
        assert session.last_result.scene.objects[body_id].material == "petg"
        assert len(session.history.transactions) == before + 1
        saved = session.save_project(tmp_path / "material.p3d")
        restored = load(saved)
        assert restored.document.ops[-1].params["material"] == "petg"
        session.undo()
        assert session.wait_for_idle()
        assert session.last_result.scene.objects[body_id].material != "petg"
    finally:
        session.release()


def test_full_preview_checks_both_actual_states_and_keeps_material_change(qt_app):
    from app.core.scene import OperationDraft
    from app.ui.session import Session

    session = Session()
    try:
        session.apply("Platte", [OperationDraft(op="create_box", params={"name": "Platte"})])
        assert session.wait_for_idle()
        key = next(iter(session.last_result.scene.objects))
        events = []
        session.preview_async(
            lambda difference: events.append(("checked", difference)),
            [OperationDraft(op="set_material", inputs=(key,), params={"material": "petg"})],
            pictured=lambda difference: events.append(("picture", difference)),
        )
        assert session.wait_for_idle(30_000)
        assert [kind for kind, _ in events] == ["picture", "checked"]
        final = events[-1][1]
        assert final is not None
        assert "Material „Platte“:" in final.explanation
        assert final.explanation.endswith("Druckbefunde unverändert"), final.explanation
        assert len(final.explanation.splitlines()) == 1, final.explanation
        assert session.last_result.scene.objects[key].material != "petg"
    finally:
        session.release()


def test_a_waiting_apply_skips_the_print_review_of_the_preview(qt_app):
    """RM-493 gegen die Prüfung der Vorschau: Wer übernimmt, wartet nur auf die Rechnung.

    Ein Klick auf *Übernehmen* während der Vorschau ruft
    ``Session.drop_preview_picture``: Das Ergebnis liegt dann im Cache, und der
    Vergleich fürs Bild entfällt. Die genaue Prüfung beider Stände (feine
    Auswertung und Schichtanalyse) lief trotzdem, und der Klick wartete auf sie.
    Jetzt endet die Vorschau mit einer leeren Differenz ohne Prüfsatz — gleich,
    ob der Klick vor oder während der Prüfung kam.
    """
    from app.core.scene import OperationDraft
    from app.i18n import tr
    from app.ui.session import Session

    session = Session()
    try:
        session.apply("Platte", [OperationDraft(op="create_box", params={"name": "Platte"})])
        assert session.wait_for_idle()
        key = next(iter(session.last_result.scene.objects))
        events = []
        session.preview_async(
            lambda difference: events.append(("checked", difference)),
            [OperationDraft(op="translate_object", inputs=(key,), params={"dx": 3.0})],
            pictured=lambda difference: events.append(("picture", difference)),
        )
        session.drop_preview_picture()
        assert session.wait_for_idle(30_000)
        assert events and events[-1][0] == "checked", events
        final = events[-1][1]
        assert final is not None, "eine erfolgreiche Rechnung ohne Bild ist eine leere Differenz"
        basis = str(
            tr(
                "Grundlage: genaue Auswertung und Schichtanalyse beider Stände "
                "mit demselben Druckziel."
            )
        )
        # Ohne Vergleich trägt die Differenz gar keine Erklärung
        # (``print_contract.ExplainedDifference`` entsteht erst beim Vergleich).
        told = getattr(final, "explanation", "")
        assert basis not in told, told
        assert not final.changed
    finally:
        session.release()


def test_candidate_review_names_a_print_finding_the_change_resolves(qt_app):
    """NM 8 (RM-090): Die Kandidatenszene wird genau ausgewertet und erneut geprüft.

    Ein Quader, der breiter ist als das Bett, trägt die Warnung
    ``arrange.out_of_build_volume``; die Vorschau von *Skalieren* auf die
    Hälfte rechnet Vorher und Nachher fein samt Schichtanalyse und nennt den
    Befund als behoben — nur weil beide Prüfungen vollständig liefen.
    """
    from app.core.scene import OperationDraft
    from app.ui.session import Session

    session = Session()
    try:
        bed = session.profile.printer.build_volume[0]
        session.apply(
            "Platte",
            [OperationDraft(op="create_box", params={"name": "Platte", "width": bed * 1.5})],
        )
        assert session.wait_for_idle()
        key = next(iter(session.last_result.scene.objects))
        assert any(
            finding.code == "arrange.out_of_build_volume" and finding.severity == "warning"
            for finding in session.last_result.scene.report.findings
        )
        events = []
        session.preview_async(
            lambda difference: events.append(("checked", difference)),
            [OperationDraft(op="scale_object", inputs=(key,), params={"factor": 0.5})],
            pictured=lambda difference: events.append(("picture", difference)),
        )
        assert session.wait_for_idle(60_000)
        assert [kind for kind, _ in events] == ["picture", "checked"]
        text = events[-1][1].explanation
        assert any(line.startswith("Behoben: ") for line in text.splitlines()), text
        assert "noch nicht geprüft" not in text and "nicht vollständig geprüft" not in text
        # Eine Änderungszeile, höchstens drei Befundzeilen (RM-516).
        assert len(text.splitlines()) <= 4, text
        assert session.last_result.scene.objects[key].mesh.bounds.size[0] > bed, (
            "die Vorschau ändert das Dokument nicht"
        )
    finally:
        session.release()


@pytest.mark.parametrize("lid", [None, "push"])
def test_reopened_container_step_previews_unchanged_or_the_new_lid(qt_app, lid):
    """RM-397 / RM-090 NM 5: Der Behälterschritt im Verlauf, ohne und mit Änderung.

    Unverändert geöffnet sagt das Band, dass sich nichts ändert — nicht „Keine
    Vorschau“, auch wenn der Kern vorab einen Hinweis zum Deckel meldet. Mit
    Steckdeckel nennt die Erklärung beide Körper, die Körperzahl und die
    Außenmaße aus denselben Szenen. Der echte Fensterweg: Vorschauauftrag,
    Arbeiter, Antwort, Band.
    """
    from app.core.lid_flow import plan_container, plan_container_edit
    from app.ui.main_window import _PreviewOrder
    from tests.ui_helpers import shown_window, wait_until

    windows = shown_window(qt_app)
    window = next(windows)
    try:
        session = window.session
        plan = plan_container(
            session.project.document, {"kernel": "mesh", "shape": "round", "lid": "screw"}
        )
        session.apply(plan.title, plan.drafts, changes=plan.document_change)
        assert session.wait_for_idle(60_000)
        operation = session.project.document.ops[0]
        steps = len(session.project.document.ops)
        if lid is None:
            order = _PreviewOrder(change_op=operation.id, change_values=dict(operation.params))
        else:
            edit = plan_container_edit(session.project.document, operation, {"lid": lid})
            order = _PreviewOrder(
                change_op=operation.id,
                change_values=dict(edit.values),
                changes=edit.document_change,
            )
        approval = window._set_preview_order(window.feature_panel, order)
        window._request_order_preview(approval)
        assert session.wait_for_idle(60_000)
        wait_until(qt_app, lambda: not approval.computing)
        note = window.viewport.banner.note.text()
        assert "Keine Vorschau" not in note, note
        assert not approval.problem, approval.problem
        if lid is None:
            assert "ändert sich nichts" in note, note
        else:
            assert "Körperzahl: 2 → 2" in note, note
            assert note.count("Außenmaß") == 2, note
        assert len(session.project.document.ops) == steps, "die Vorschau ändert nichts"
    finally:
        window._may_discard = lambda: True
        with suppress(StopIteration):
            next(windows)


@pytest.mark.parametrize("ending", ["cancel", "newer", "failure", "complete"])
def test_picture_does_not_approve_a_pending_print_review(qt_app, monkeypatch, ending):
    from app.core.geom.difference import SceneDifference
    from app.core.scene import OperationDraft
    from app.ui.main_window import _PreviewOrder
    from tests.ui_helpers import shown_window

    windows = shown_window(qt_app)
    window = next(windows)
    try:
        window.session.evaluate_now()
        calls, shown, accepted = [], [], []
        monkeypatch.setattr(
            window.session,
            "preview_async",
            lambda then, drafts=None, **kw: calls.append((then, kw)),
        )
        monkeypatch.setattr(window, "_show_preview", lambda value, **kw: shown.append(value))
        order = _PreviewOrder(drafts=(OperationDraft(op="create_box"),))
        approval = window._set_preview_order(window.feature_panel, order)
        window._request_order_preview(approval)
        first, callbacks = calls[-1]
        picture = SceneDifference()
        callbacks["pictured"](picture)
        assert shown == [picture]
        assert approval.computing and approval.reviewing
        assert not approval.displayed and approval.difference is None
        assert not window._preview_can_apply(
            window.feature_panel, order, then=lambda: accepted.append(True)
        )
        assert not accepted
        if ending == "cancel":
            window._cancel_preview_run()
            assert approval.problem and not accepted
        elif ending == "newer":
            window._set_preview_order(
                window.feature_panel,
                _PreviewOrder(drafts=(OperationDraft(op="create_box", params={"width": 12.0}),)),
            )
            first(SceneDifference())
            assert not accepted
            assert window._preview_approval.difference is None
        elif ending == "failure":
            callbacks["failed"]("Prüfung unterbrochen")
            assert approval.problem and not accepted
        else:
            first(SceneDifference())
            assert accepted == [True]
    finally:
        with suppress(StopIteration):
            next(windows)


def test_consumed_body_id_is_not_appended_to_a_named_finding(qt_app):
    from app.ui.panels import _line_for

    finding = Finding(
        "union.bore_partial", "warning", "Quader verdeckt eine Bohrung.", object_id="obj_1"
    )
    assert _line_for(finding, {}) == str(finding.message)
    assert _line_for(finding, {"obj_1": "obj_1"}) == str(finding.message)
    assert _line_for(finding, {"obj_1": "Quader"}) == str(finding.message)


def test_the_conversion_note_names_no_identifier(qt_app):
    """RM-396: Der Umwandlungshinweis hängte über ``values["object"]`` „obj_0“ an.

    Gegenprobe vor dem Fix (Sonde 04.10.2026): alle drei Zeilen endeten auf
    „— obj_0“, auch wenn der Ausgabekörper einen Namen hatte.
    """
    from app.core.scene.evaluate import conversion_finding
    from app.core.scene.history import Operation
    from app.ui.panels import _line_for

    source = make_object("obj_1", "Quader")
    operation = Operation(id=3, op="union_objects", inputs=("obj_1", "obj_0"), outputs=("obj_0",))
    finding = conversion_finding(operation, "Vereinigen", source, ("obj_0",))
    for names in ({}, {"obj_1": "obj_1"}, {"obj_0": "obj_0", "obj_1": "obj_1"}):
        line = _line_for(finding, names)
        assert "obj_" not in line, line
        assert line == str(finding.message)
    named = _line_for(finding, {"obj_0": "Schale", "obj_1": "obj_1"})
    assert named == f"{finding.message} — Schale"


@pytest.mark.parametrize("export_format", ["stl", "3mf"])
def test_file_export_receipt_carries_the_readback_of_the_written_files(
    qt_app, tmp_path, export_format
):
    """NM 9/11: Der Beleg nennt die tatsächlich wieder eingelesenen Dateien (RM-090).

    Gegenprobe ohne Fix: ``handoff_receipt`` schrieb fest „nicht durchgeführt“.
    Hier läuft derselbe Arbeiter wie beim Menüexport, mit zwei Körpern, von
    denen einer gewählt ist — der eingefrorene Umfang ist 1 von 2.
    """
    from app.core.scene import OperationDraft
    from app.ui.main_window import _ExportWorker
    from app.ui.session import Session
    from app.ui.settings import UiSettings

    session = Session()
    try:
        session.apply("Quader", [OperationDraft(op="create_box")])
        session.apply("Zylinder", [OperationDraft(op="create_cylinder")])
        assert session.wait_for_idle()
        bodies = list(session.last_result.scene.objects.values())
        assert len(bodies) == 2
        worker = _ExportWorker(
            bodies[:1],
            tmp_path / f"teil.{export_format}",
            export_format,
            profile=session.profile,
            sources=session.project.document.sources,
            settings=None,
            ui_settings=UiSettings(),
            material=session.profile.material.id,
            all_objects=bodies,
            scene=session.last_result.scene,
            document=session.project.document,
            checked=[],
        )
        done = []
        worker.done.connect(lambda written, findings: done.append(written))
        worker.work()
        assert done and done[0]
        receipt = worker.receipt
        assert receipt is not None and receipt.severity == "info"
        detail = receipt.values["detail"]
        assert "erneut eingelesen" in detail and "1 von 1 Körpern" in detail
        assert "nicht durchgeführt" not in detail
        assert "1 von 2 Körpern des eingefrorenen Auftrags" in detail
        worker.deleteLater()
    finally:
        session.release()


@pytest.mark.parametrize("flavour", ["orca", "prusa"])
def test_slicer_receipt_reads_back_the_files_it_opened(qt_app, monkeypatch, tmp_path, flavour):
    """NM 9/11: *Im Slicer öffnen* liest die übergebene Datei vor dem Beleg zurück."""
    from pathlib import Path

    from app.core.knowledge import print_settings
    from app.core.scene import OperationDraft
    from app.ui import print_settings_dialog as module
    from app.ui.session import Session

    session = Session()
    try:
        session.apply("Quader", [OperationDraft(op="create_box")])
        session.apply("Zylinder", [OperationDraft(op="create_cylinder")])
        assert session.wait_for_idle()
        bodies = tuple(session.last_result.scene.objects.values())
        profile = session.profile
        job = module._PlateJob(
            bodies,
            (0,),
            tmp_path,
            "Schiff",
            module.handover.SlicerSetup(Path("Slicer.exe"), flavour),
            print_settings.resolve(profile),
            profile,
            {},
            with_settings=False,
        )
        worker = module._OpenInSlicerWorker(job)
        opened = []
        monkeypatch.setattr(
            module.handover, "open_in_slicer", lambda path, setup: opened.append(path)
        )
        receipts = []
        worker.receipt.connect(receipts.append)
        worker.work()
        assert opened and receipts
        detail = receipts[0].values["detail"]
        assert "erneut eingelesen" in detail and "2 von 2 Körpern" in detail, detail
        assert receipts[0].severity == "info"
        worker.deleteLater()
    finally:
        session.release()


def test_finding_card_names_consequence_and_side_effect_and_tab_reaches_them(qt_app):
    """NM 4 (RM-090, §4.3): Folge, Ort, Grundlage, Handlung und ihre Nebenfolge.

    Die Nebenfolge kommt aus ``core.action_effects``; ohne sie stand *Auf dem
    Bett anordnen* am Befund, ohne zu sagen, dass es alle Körper bewegt.
    Seit RM-508 stehen Folge, Ort und Grundlage in einer Zeile („Warnung ·
    Rumpf · intern geschätzt“), und die Nebenfolge steht unter dem Hauptknopf,
    weil sie etwas verändert. Tastatur: Von der Liste aus erreicht Tab
    Einzelheiten, Stelle und Knopf.
    """
    from PySide6.QtWidgets import QApplication, QPushButton, QVBoxLayout, QWidget

    from app.core.action_effects import SIDE_EFFECTS

    ran = []

    class Host(QWidget):
        def error_handlers(self):
            return {"arrange_on_bed": lambda error: ran.append(error)}

    host = Host()
    layout = QVBoxLayout(host)
    panel = ReportPanel(host)
    layout.addWidget(panel)
    finding = Finding(
        "arrange.collision",
        "warning",
        "Zwei Körper überschneiden sich.",
        object_id="a",
        location=(0.0, 0.0, 1.0),
    )
    try:
        panel.show_result(
            EvaluationResult(
                Scene(objects={"a": make_object("a", "Rumpf")}, report=Report((finding,)))
            )
        )
        host.resize(420, 700)
        host.show()
        panel.list.setCurrentRow(0)
        qt_app.processEvents()
        assert panel.finding_context.text() == "Warnung · Rumpf · intern geschätzt"
        assert panel.finding_consequence.isHidden(), "eine Warnung braucht keinen Folgesatz"
        assert not panel.offer_effect.isHidden()
        assert panel.offer_effect.text() == str(SIDE_EFFECTS["arrange_on_bed"])
        buttons = [
            widget
            for index in range(panel._offer_row.count())
            if isinstance(widget := panel._offer_row.itemAt(index).widget(), QPushButton)
        ]
        assert buttons and "Nebenfolge:" in buttons[0].accessibleDescription()
        assert panel._offer_row.indexOf(panel.offer_effect) == 1, "direkt unter dem Hauptknopf"
        panel.list.setFocus()
        reached = []
        for _round in range(12):
            QTest.keyClick(QApplication.focusWidget(), Qt.Key.Key_Tab)
            qt_app.processEvents()
            reached.append(QApplication.focusWidget())
        for target in (panel.finding_place, panel.finding_details_toggle, buttons[0]):
            assert target in reached, target
        QTest.keyClick(buttons[0], Qt.Key.Key_Space)
        assert ran, "die Leertaste löst die Handlung aus"
        panel.list.clearSelection()
        assert panel.offer_effect.isHidden()
    finally:
        host.close()
        host.deleteLater()


def test_a_deviating_readback_turns_the_receipt_into_a_warning(tmp_path):
    """Eine abweichende Gegenprobe macht den Beleg zur Warnung und nennt die Stelle."""
    from app.core.export.readback import Readback
    from app.core.knowledge import profiles
    from app.core.scene.project import new_project
    from app.i18n import _
    from app.ui.print_contract import handoff_receipt

    document = new_project("centauri-carbon-2", "petg").document
    note = _(
        "„{name}“ steht in „{file}“ nicht so, wie er geschrieben werden sollte.",
        name="Deckel",
        file="deckel.stl",
    )
    receipt = handoff_receipt(
        document=document,
        profile=profiles.make_profile(document.printer, document.material),
        objects=(make_object("a", "Deckel"),),
        written=(tmp_path / "deckel.stl",),
        findings=(),
        with_settings=False,
        status="Dateien exportiert.",
        checked=Readback("deviated", files=("deckel.stl",), expected=1, found=1, notes=(note,)),
    )
    assert receipt.severity == "warning"
    assert "weicht ab" in str(receipt.message)
    assert "„Deckel“ steht in „deckel.stl“" in receipt.values["detail"]


# --- RM-508: Der Prüfbericht zeigt zuerst die Befunde ---------------------------


def _report_with(findings, *, width=440, height=500):
    """Ein Bericht mit einem lebenden Körper „Dose“ und diesen Befunden, gezeigt."""
    panel = ReportPanel()
    panel.show_result(
        EvaluationResult(
            Scene(objects={"a": make_object("a", "Dose")}, report=Report(tuple(findings)))
        )
    )
    panel.set_review_context("Geometrieprüfung: ganze Szene", ())
    panel.resize(width, height)
    panel.show()
    return panel


def test_the_head_is_one_line_and_counts_leave_out_zeros(qt_app):
    """Status, Zähler und Prüfumfang in einer Zeile; „0 x Fehler“ steht nicht da."""
    panel = _report_with(
        [
            Finding("a.warn", "warning", "Eine Warnung.", object_id="a"),
            Finding("a.note", "info", "Ein Hinweis.", object_id="a"),
            Finding("b.note", "info", "Noch ein Hinweis.", object_id="a"),
        ]
    )
    try:
        qt_app.processEvents()
        assert panel.summary.text() == "Entscheidung erforderlich"
        assert panel.list_toggle.text() == "1 Warnung · 2 Hinweise"
        assert "0" not in panel.list_toggle.text()
        assert panel.review_reason.isHidden(), "eine vollständige Bewertung braucht keinen Grund"
        tops = {
            widget.mapTo(panel, widget.rect().center()).y() // 8
            for widget in (panel.summary, panel.list_toggle, panel.review_toggle)
        }
        assert len(tops) == 1, "eine Zeile"
        assert not panel.facts.isVisibleTo(panel), "die Kennzahlen stehen im Prüfumfang"
        panel.review_toggle.click()
        qt_app.processEvents()
        assert panel.facts.isVisibleTo(panel)
        panel.set_review_context("Geometrieprüfung: ganze Szene", ("Schichtanalyse: läuft",))
        assert panel.summary.text() == "Bewertung unvollständig"
        assert panel.review_reason.text() == "Schichtanalyse: läuft", "unvollständig sagt warum"
    finally:
        panel.close()
        panel.deleteLater()


def test_hints_alone_start_folded_and_a_warning_unfolds_the_list(qt_app):
    """Hinweise verlangen keine Entscheidung; die Karte bleibt bei ihnen klein."""
    panel = _report_with([Finding("a.note", "info", "Ausgehöhlt.", object_id="a")])
    try:
        qt_app.processEvents()
        assert not panel.list_toggle.isHidden()
        assert panel.list_toggle.text() == "1 Hinweis"
        assert not panel.list.isVisibleTo(panel), "Hinweise allein stehen zugeklappt"
        panel.list_toggle.click()
        qt_app.processEvents()
        assert panel.list.isVisibleTo(panel)
        panel.add_findings([Finding("b.note", "info", "Noch einer.", object_id="a")])
        assert panel.list.isVisibleTo(panel), "wer selbst aufklappt, behält es"
        panel.list_toggle.click()
        panel.add_findings([Finding("a.warn", "warning", "Eine Warnung.", object_id="a")])
        assert panel.list.isVisibleTo(panel), "eine Warnung öffnet die Liste"
        panel.show_result(None)
        assert panel.list_toggle.isHidden(), "ohne Befund keine Klappe"
    finally:
        panel.close()
        panel.deleteLater()


def test_a_finding_offers_one_way_to_show_its_place(qt_app):
    """Durchsicht B10: „Betroffene Stelle zeigen“ und „Stelle zeigen“ flogen gleich."""
    from PySide6.QtWidgets import QPushButton, QVBoxLayout, QWidget

    from app.core.errors import SHOW_LOCATION

    class Host(QWidget):
        def error_handlers(self):
            return {SHOW_LOCATION.id: lambda _error: None}

    host = Host()
    layout = QVBoxLayout(host)
    panel = ReportPanel(host)
    layout.addWidget(panel)
    try:
        for suggestions, own in (((SHOW_LOCATION,), False), ((), True)):
            finding = Finding(
                "a.open",
                "warning",
                "Hier.",
                object_id="a",
                location=(0.0, 0.0, 1.0),
                suggestions=suggestions,
            )
            panel.show_result(
                EvaluationResult(
                    Scene(objects={"a": make_object("a", "Dose")}, report=Report((finding,)))
                )
            )
            panel.list.setCurrentRow(0)
            labels = [
                button.text()
                for button in panel._offers.findChildren(QPushButton)
                if not button.isHidden()
            ]
            showing = labels.count("Stelle zeigen") + (not panel.finding_place.isHidden())
            assert showing == 1, (labels, panel.finding_place.isHidden())
            assert panel.finding_place.isHidden() is not own
    finally:
        host.close()
        host.deleteLater()


def test_export_stands_beside_the_handover_outside_the_scroller(qt_app):
    """Mit dem Export enden alle Hauptwege; er war nur über das Menü erreichbar (A3)."""
    from app.ui.overlay import FittedScroller

    panel = _report_with([])
    requested = []
    panel.exportRequested.connect(lambda: requested.append(True))
    try:
        qt_app.processEvents()
        scroller = panel.findChild(FittedScroller)
        assert scroller is not None
        for button in (panel.to_slicer, panel.export_button):
            assert button.isVisibleTo(panel)
            assert not scroller.isAncestorOf(button), "der letzte Schritt rollt nicht hinaus"
        assert panel.export_button.text() == "Exportieren …"
        assert abs(panel.export_button.y() - panel.to_slicer.y()) <= 1, "nebeneinander"
        panel.export_button.click()
        assert requested == [True]
        panel.follow_export(False, "Es wird gerade exportiert.")
        assert not panel.export_button.isEnabled()
        assert panel.export_button.toolTip() == "Es wird gerade exportiert."
        panel.show_result(None)
        assert not panel.export_button.isVisibleTo(panel), "ohne Körper nichts zu exportieren"
    finally:
        panel.close()
        panel.deleteLater()


def test_the_chosen_row_stands_whole_and_the_others_by_their_first_sentence(qt_app):
    """Die Liste zeigt je Befund seinen ersten Satz; die gewählte Zeile ganz."""
    long_one = Finding(
        "a.thin",
        "warning",
        "Die dünnste Stelle ist schmal. Eine kleinere Düse wählen.",
        object_id="a",
    )
    other = Finding("b.thin", "warning", "Noch eine Stelle. Mit Rat dahinter.", object_id="a")
    panel = _report_with([long_one, other])
    try:
        panel.list.clearSelection()
        texts = [panel.list.item(row).text() for row in range(panel.list.count())]
        assert all("Düse" not in text and "Rat" not in text for text in texts), texts
        panel.list.setCurrentRow(0)
        assert "Eine kleinere Düse wählen." in panel.list.item(0).text()
        assert "Rat" not in panel.list.item(1).text()
        panel.list.setCurrentRow(1)
        assert "Düse" not in panel.list.item(0).text()
        assert "Mit Rat dahinter." in panel.list.item(1).text()
    finally:
        panel.close()
        panel.deleteLater()


def test_the_list_keeps_three_rows_when_the_room_is_short(qt_app):
    """Bei Platzmangel rollt der Kopf; die Liste gibt nur bis drei Zeilen nach."""
    from app.ui.panels import LEAST_REPORT_ROWS

    findings = [
        Finding(f"a.warn_{index}", "warning", f"Warnung {index}.", object_id="a")
        for index in range(8)
    ]
    panel = _report_with(findings, width=360, height=160)
    try:
        for _round in range(4):
            qt_app.processEvents()
        viewport = panel.list.viewport().rect()
        whole = sum(
            1
            for row in range(panel.list.count())
            if viewport.contains(panel.list.visualItemRect(panel.list.item(row)))
        )
        assert whole >= LEAST_REPORT_ROWS, whole
    finally:
        panel.close()
        panel.deleteLater()
