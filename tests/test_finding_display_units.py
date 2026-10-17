"""FD61: Ein Lagebefund folgt auch aus altem Cache der Anzeigeeinheit."""

from __future__ import annotations

import copy
import dataclasses
import json
from collections.abc import Iterator
from pathlib import Path

import pytest
import trimesh
from PySide6.QtCore import QLocale, Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QPushButton

from app.core import guides
from app.core.backends.mesh import MINIMUM_COMFYUI_TEXT
from app.core.build_area import printable_area, printable_height
from app.core.export.writer import check_adhesion_clearance
from app.core.geom.mesh import MeshCodec, MeshData
from app.core.geom.prepare import check_build_volume
from app.core.geom.transform import apply, translation
from app.core.knowledge import print_settings
from app.core.knowledge.print_fields import shown_value
from app.core.scene.cache import CachedResult, DiskCache
from app.core.scene.evaluate import EvaluationResult
from app.core.scene.serialise import finding_from_data, finding_to_data
from app.core.slice.advise import warnings_for
from app.core.types import Action, Finding, Profile, Report, Scene, SceneObject
from app.i18n import _, get_language, set_language, tr
from app.i18n.catalog import install_language
from app.ui.labels import localised, set_display_unit, value_line, value_text
from app.ui.loading import DELAY_MS
from app.ui.panels import _BODIES_ROLE, FILTER_FROM, ObjectTree, ReportPanel
from app.ui.settings_dialog import SettingsDialog
from tests.helpers import MESHES, cube_mesh
from tests.ui_helpers import session as session
from tests.ui_helpers import wait_for_print_findings
from tests.ui_helpers import window as window


@pytest.fixture(autouse=True, params=["de", "en", "es", "fr", "it", "pt"])
def language(request, qt_app) -> Iterator[str]:
    """Echte Kataloge und Zahlenschreibweise, nach jedem Fall zurückgestellt."""
    previous = get_language()
    locale = QLocale()
    install_language(request.param)
    set_language(request.param)
    QLocale.setDefault(QLocale(request.param))
    set_display_unit("mm")
    try:
        yield request.param
    finally:
        set_display_unit("mm")
        set_language(previous)
        QLocale.setDefault(locale)


def misplaced(profile: Profile, case: str) -> tuple[MeshData, Finding, str]:
    """Je zehn Millimeter Überstand oder Luft, aus Korpus und Druckkontur."""
    mesh = cube_mesh()
    # cube_clean ist um den Ursprung zentriert und 20 mm hoch.
    assert mesh.bounds.minimum[2] == pytest.approx(-10.0)
    assert mesh.bounds.maximum[2] == pytest.approx(10.0)
    left, front, right, back = printable_area(profile.printer).bounds
    if case == "off":
        mesh = apply(mesh, translation((right, 0.0, 10.0)))
    elif case == "above":
        mesh = apply(mesh, translation((0.0, 0.0, printable_height(profile.printer))))
    elif case == "floating":
        mesh = apply(mesh, translation((0.0, 0.0, 20.0)))
    elif case == "oversized":
        mesh = MeshData.of(
            trimesh.creation.box(extents=(right - left + 20.0, back - front + 20.0, 20.0))
        )
        mesh = apply(mesh, translation(((right + left) / 2.0, (back + front) / 2.0, 10.0)))
    findings = check_build_volume([mesh], profile, object_ids=["body"])
    assert len(findings) == 1
    expected_code = {
        "below": "arrange.below_bed",
        "above": "arrange.above_bed",
        "off": "arrange.off_the_plate",
        "floating": "arrange.above_bed",
        "oversized": "arrange.out_of_build_volume",
    }[case]
    assert findings[0].code == expected_code
    return mesh, findings[0], "gap" if case == "floating" else "excess"


def ten_millimetres(language: str, unit: str) -> str:
    """Unabhängiges Soll: 10 / 25,4, vier Zollstellen, sonst zwei mm-Stellen."""
    text = "10.00 mm" if unit == "mm" else "0.3937 in"
    return text if language == "en" else text.replace(".", ",")


@pytest.mark.parametrize("case", ["below", "above", "off", "floating", "oversized"])
def test_real_placement_values_follow_units_without_changing_the_finding(
    qt_app, profile: Profile, language: str, case: str
) -> None:
    mesh, finding, key = misplaced(profile, case)
    original = json.dumps(finding_to_data(finding), sort_keys=True)
    panel = ReportPanel()
    try:
        for unit in ("mm", "in", "mm"):
            set_display_unit(unit)
            panel.show_result(
                EvaluationResult(
                    Scene(
                        objects={"body": SceneObject(id="body", name="Korpus", mesh=mesh)},
                        report=Report((finding,)),
                    )
                )
            )
            panel.list_toggle.setChecked(True)
            panel.list.setCurrentRow(0)
            item = panel.list.currentItem()
            expected = ten_millimetres(language, unit)
            assert value_text(key, finding.values[key]) == expected
            assert expected in item.toolTip()
            assert expected in panel.finding_details.toPlainText()
            if key == "excess":
                assert expected in item.text()
                assert tr("Überstand") in item.text()
            assert json.dumps(finding_to_data(finding), sort_keys=True) == original
    finally:
        panel.close()
        panel.deleteLater()


@pytest.mark.parametrize("cached", [False, True])
def test_existing_report_changes_units_and_keeps_selection_and_added_findings(
    window, profile: Profile, language: str, tmp_path: Path, cached: bool, monkeypatch
) -> None:
    mesh, finding, _key = misplaced(profile, "below")
    body = SceneObject(id="body", name="Korpus", mesh=mesh)
    if cached:
        # Der alte JSON-Wert ist Text, keine neue Messwertklasse im Speicher.
        old_data = json.loads(json.dumps(finding_to_data(finding)))
        assert old_data["values"]["excess"] == "10.00 mm"
        old = finding_from_data(old_data)
        directory = tmp_path / "cache"
        DiskCache(codec=MeshCodec(), directory=directory).put(
            "legacy-placement", CachedResult(objects=(body,), findings=(old,))
        )
        warmed = DiskCache(codec=MeshCodec(), directory=directory).get("legacy-placement")
        assert warmed is not None
        finding = warmed.findings[0]
        body = warmed.objects[0]
    # Genug eigenständige Nachlaufbefunde, damit die echte Filterzeile offen
    # bleibt; der Suchvertrag umfasst die Meldung, nicht den Körpernamen.
    extra = [
        Finding(
            code=f"fixture.extra_{index}",
            severity="info",
            message=_("Keine Überschneidungen gefunden."),
            source="gcode",
        )
        for index in range(FILTER_FROM - 1)
    ]
    window.report.show_result(
        EvaluationResult(Scene(objects={"body": body}, report=Report((finding,))))
    )
    window.report.add_findings(extra)
    window.report.list_toggle.setChecked(True)
    query = str(finding.message)
    window.report.search.setText(query)
    chosen = next(
        row
        for row in range(window.report.list.count())
        if window.report.list.item(row).data(Qt.ItemDataRole.UserRole).code == finding.code
    )
    window.report.list.setCurrentRow(chosen)
    window.report.finding_details_toggle.setChecked(True)
    before_document = copy.deepcopy(window.session.project.document)
    before_values = dict(finding.values)
    monkeypatch.setattr(
        window.session,
        "evaluate_async",
        lambda *args, **kwargs: pytest.fail("Einheitenwechsel darf keine Auswertung starten"),
    )
    for unit in ("mm", "in", "mm"):
        window.set_display_unit(unit)
        item = window.report.list.currentItem()
        assert item is not None and not item.isHidden()
        assert item.data(Qt.ItemDataRole.UserRole).code == finding.code
        expected = ten_millimetres(language, unit)
        assert expected in item.text()
        assert expected in item.toolTip()
        assert expected in item.data(Qt.ItemDataRole.AccessibleDescriptionRole)
        assert expected in window.report.finding_details.toPlainText()
        assert window.report.finding_details_toggle.isChecked()
        assert window.report.list_toggle.isChecked()
        assert window.report.search.text() == query
        assert window.report.list.count() == FILTER_FROM
        sources = {
            window.report.list.item(row).data(Qt.ItemDataRole.UserRole).source
            for row in range(FILTER_FROM)
        }
        assert sources == {"internal", "gcode"}
        assert window.session.project.document == before_document
        assert finding.values == before_values
    window.report.add_findings([finding])
    assert window.report.list.count() == FILTER_FROM, "Warmer Befund darf nicht doppelt erscheinen"


@pytest.mark.parametrize("page", ["report", "selection", "chat"])
def test_settings_unit_change_keeps_the_read_page_and_visible_report(
    window, qt_app, language: str, page: str, tmp_path: Path, monkeypatch
) -> None:
    """Einheitenübernahme erneuert dieselbe Auswahl, ohne den Leser wegzuschicken.

    Der native Gegenfall hatte einen wirklich gewählten Körper. Eine nur im
    Bericht eingetragene Szene prüfte den Baumneubau nicht; er holte nach dem
    Speichern den Auswahlreiter vor die weiterhin geöffneten Einzelheiten.
    """
    window.settings.language = language
    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle(60_000)
    step = window.session.history.operations[-1]
    assert window.session.change_params(step.id, {"place_on_bed": False, "free_spot": False})
    assert window.session.wait_for_idle(60_000)
    wait_for_print_findings(window)
    # Wie im nativen Fall ein Projekt öffnen; ein Modellimport hat zusätzliche
    # Auswahlfolgen. Die Projektdatei entsteht allein aus dem eingecheckten Korpus.
    project = window.session.save_project(tmp_path / "unter-dem-bett.p3d")
    window.open_path(project)
    assert window.session.wait_for_idle(60_000)
    wait_for_print_findings(window)
    window.resize(1600, 1000)
    window.show()
    tree_item = window.object_tree.tree.topLevelItem(0)
    assert tree_item is not None
    assert not window.object_tree.selected_objects(), "Der Befund trifft die erste Körperauswahl"
    report = window.report
    window.right.setCurrentWidget(report)
    report.list_toggle.setChecked(True)
    row = next(
        index
        for index in range(report.list.count())
        if report.list.item(index).data(Qt.ItemDataRole.UserRole).code == "arrange.below_bed"
    )
    qt_app.processEvents()
    report.list.scrollToItem(report.list.item(row))
    # Genau der native Weg: Der Befund wählt den Körper unter held(), ohne
    # vorher den Auswahlreiter zu besuchen und dadurch dismissed zu setzen.
    QTest.mouseClick(
        report.list.viewport(),
        Qt.MouseButton.LeftButton,
        pos=report.list.visualItemRect(report.list.item(row)).center(),
    )
    report.finding_details_toggle.setChecked(True)
    tree_item.setExpanded(False)
    target = {
        "report": report,
        "selection": window.feature_dock,
        "chat": window.chat,
    }[page]
    window.right.setCurrentWidget(target)
    qt_app.processEvents()
    assert window.right.currentWidget() is target
    assert report.finding_details.isVisible() == (page == "report")
    selected_bodies = window.object_tree.selected_objects()
    assert selected_bodies, "Der Reiterwechsel braucht eine echte Körperauswahl"
    before_document = copy.deepcopy(window.session.project.document)
    result = window.session.last_result
    assert result is not None
    before_findings = [finding_to_data(one) for one in result.scene.report.findings]
    monkeypatch.setattr(
        window.session,
        "evaluate_async",
        lambda *args, **kwargs: pytest.fail("Einheitenübernahme darf keine Auswertung starten"),
    )

    for unit in ("mm", "in", "in", "mm"):

        def accept_units(dialog, unit=unit):
            dialog.unit.setCurrentIndex(dialog.unit.findData(unit))
            return SettingsDialog.DialogCode.Accepted

        # Der echte Übernahmeweg samt _apply_settings; nur die modale Wartezeit
        # entfällt. Der Chatreiter wird gelesen, kein Auftrag abgeschickt.
        monkeypatch.setattr(SettingsDialog, "exec", accept_units)
        window.show_setting("unit")
        qt_app.processEvents()
        assert window.settings.display_unit == unit
        assert window.right.currentWidget() is target, "Die Anzeigeeinheit ist keine neue Auswahl"
        assert report.finding_details_toggle.isChecked()
        assert report.finding_details.isVisible() == (page == "report")
        chosen = report.list.currentItem()
        assert chosen is not None
        assert chosen.data(Qt.ItemDataRole.UserRole).code == "arrange.below_bed"
        expected = ten_millimetres(language, unit)
        assert expected in chosen.text()
        assert expected in report.finding_details.toPlainText()
        assert window.object_tree.selected_objects() == selected_bodies
        assert not window.object_tree.tree.topLevelItem(0).isExpanded()
        assert window.session.project.document == before_document
        assert [finding_to_data(one) for one in result.scene.report.findings] == before_findings


@pytest.mark.parametrize("first_open", [False, True])
def test_unit_refresh_keeps_selected_and_unselected_body_expansion(
    window, qt_app, first_open: bool
) -> None:
    """Die Auswahl darf beim Beschriften weder aufklappen noch andere Körper zuklappen."""
    window.open_path(MESHES / "cube_clean.stl")
    assert window.session.wait_for_idle(60_000)
    result = window.session.last_result
    assert result is not None
    source = next(iter(result.scene.objects.values()))
    bodies = {name: dataclasses.replace(source, id=name, name=name) for name in ("first", "second")}
    tree = ObjectTree()
    try:
        tree.show_scene(EvaluationResult(Scene(objects=bodies)))
        tree.select_object("first")
        for index, opened in enumerate((first_open, not first_open)):
            item = tree.tree.topLevelItem(index)
            assert item is not None and item.childCount(), "Echte Merkmalsknoten als Voraussetzung"
            item.setExpanded(opened)
        before = tree.selected_objects()
        assert before == ("first",)
        for unit in ("mm", "in", "in", "mm"):
            tree.set_unit(unit)
            qt_app.processEvents()
            assert tree.selected_objects() == before
            assert [tree.tree.topLevelItem(index).isExpanded() for index in range(2)] == [
                first_open,
                not first_open,
            ]
    finally:
        tree.close()
        tree.deleteLater()


@pytest.mark.parametrize(
    "key,value",
    [
        ("gap", 0.2),  # Stützabstand in den Druckeinstellungen bleibt Slicer-Wert.
        ("path", "sources/10.00 mm.stl"),
        ("part_name", "10.00 mm"),
        ("excess", "unbekannt mm"),
        ("excess", "10.00 mm Rest"),
        ("excess", "1.2.3 mm"),
        ("gap", "10,00 mm"),  # Freitext ist kein kanonischer gespeicherter Messwert.
        ("excess", "NaN mm"),
        ("open_edges", 6),
        ("share_percent", 15.0),
        ("stress", 30.0),
        ("flow_limit", 12.0),
        ("needed", MINIMUM_COMFYUI_TEXT),
        ("needed", "10,00 mm"),
        ("needed", "mindestens 10.00 mm"),
    ],
)
def test_non_geometric_values_are_not_reinterpreted(key: str, value: object) -> None:
    before = value_line(key, value)
    set_display_unit("in")
    assert value_line(key, value) == before
    if key == "gap" and isinstance(value, float):
        # Eine Druckeinstellung steht wie im Druckdialog: mit der Einheit ihres
        # Felds und ohne Umrechnung (FD-188; vorher die nackte Zahl „0,2“).
        assert value_text(key, value) == shown_value("support.z_gap", value, localise=localised)
        assert value_text(key, value).endswith(" mm")


@pytest.mark.parametrize("value", [3.5, "3.50"])
def test_a_numeric_required_length_follows_the_unit(value: object) -> None:
    """Ein nackter ``needed`` ist überall eine Länge in mm (FD-188).

    Er kommt aus ``lid_hinge`` (Augenhöhe, ``round(hanging, 3)``) und der
    Lochwand-Zunge in ``mounting`` (``f"{step:.2f}"``) — beide Millimeter. Die
    Mindestversion von ComfyUI unter demselben Schlüssel bleibt Text (oben).
    """
    assert value_text("needed", value) == value_text("needed_mm", 3.5)
    assert value_text("needed", value).endswith(" mm")
    set_display_unit("in")
    assert value_text("needed", value) == value_text("needed_mm", 3.5)
    assert value_text("needed", value).endswith(" in")


def test_existing_numeric_margin_and_suffix_still_convert(language: str) -> None:
    set_display_unit("in")
    assert value_text("margin", 10.0) == ten_millimetres(language, "in")
    assert value_text("oversize_mm", 10.0) == ten_millimetres(language, "in")


def test_the_geometric_adhesion_gap_and_required_distance_switch_together(
    profile: Profile, language: str
) -> None:
    """Zwei 20-mm-Würfel mit 4 mm Luft brauchen zweimal 3 mm Brimabstand."""
    settings = print_settings.resolve(profile)
    settings = print_settings.with_path(settings, "adhesion.kind", "brim")
    settings = print_settings.with_path(settings, "adhesion.brim_width", 3.0)
    meshes = [cube_mesh(), apply(cube_mesh(), translation((24.0, 0.0, 0.0)))]
    findings = check_adhesion_clearance(meshes, settings)
    assert len(findings) == 1
    assert findings[0].code == "arrange.adhesion_too_close"
    values = findings[0].values
    assert values["gap"] == "4.00 mm" and values["needed"] == "6.00 mm"
    for unit in ("mm", "in", "mm"):
        set_display_unit(unit)
        expected = ("4.00 mm", "6.00 mm") if unit == "mm" else ("0.1575 in", "0.2362 in")
        if language != "en":
            expected = tuple(value.replace(".", ",") for value in expected)
        shown = (value_text("gap", values["gap"]), value_text("needed", values["needed"]))
        assert shown == expected
    assert settings.adhesion.brim_width == pytest.approx(3.0)


def test_a_real_support_setting_warning_keeps_its_slicer_gap(profile: Profile) -> None:
    """Der nackte Stützabstand ist eine Druckeinstellung und bleibt ihr Wert."""
    settings = print_settings.resolve(profile)
    settings = print_settings.with_path(settings, "support.style", "grid")
    settings = print_settings.with_path(settings, "support.z_gap", 0.1)
    settings = print_settings.with_path(settings, "layers.layer_height", 0.2)
    finding = next(
        entry
        for entry in warnings_for(settings, profile)
        if entry.code == "settings.support_gap_too_small"
    )
    original = value_line("gap", finding.values["gap"])
    for unit in ("mm", "in", "mm"):
        set_display_unit(unit)
        assert value_line("gap", finding.values["gap"]) == original
        assert finding.values["gap"] == pytest.approx(0.1)


def paired_placement(profile: Profile) -> tuple[dict[str, SceneObject], list[Finding]]:
    """Zwei echte Lagehinweise und daneben zwei echte Exportwarnungen."""
    meshes = [cube_mesh(), apply(cube_mesh(), translation((30.0, 0.0, 0.0)))]
    bodies = {
        key: SceneObject(id=key, name=name, mesh=meshes[index % 2])
        for index, (key, name) in enumerate(
            (("a", "Rumpf A"), ("b", "Rumpf B"), ("c", "Deckel C"), ("d", "Deckel D"))
        )
    }
    findings = check_build_volume(meshes, profile, object_ids=["a", "b"])
    findings += check_build_volume(meshes, profile, object_ids=["c", "d"], about_to_write=True)
    assert [one.severity for one in findings] == ["info", "info", "warning", "warning"]
    assert all(one.code == "arrange.below_bed" for one in findings)
    return bodies, findings


@pytest.mark.parametrize("running", [False, True])
def test_a_selected_geometric_group_keeps_its_targets_and_previous_state(
    window, profile: Profile, language: str, running: bool
) -> None:
    """BE-01: Echte Sammelzeile statt zufälliger Warnung, auch während Rechnung."""
    bodies, findings = paired_placement(profile)
    original = [finding_to_data(one) for one in findings]
    panel = window.report
    panel.show_result(EvaluationResult(Scene(objects=bodies, report=Report(tuple(findings)))))
    assert panel.list.count() == 2
    panel.list_toggle.setChecked(True)
    row = next(
        index
        for index in range(panel.list.count())
        if panel.list.item(index).data(Qt.ItemDataRole.UserRole).severity == "info"
    )
    panel.list.setCurrentRow(row)
    if running:
        panel.set_running(True)
        QTest.qWait(DELAY_MS + 150)
        assert panel.running()
    panel.finding_details_toggle.setChecked(True)
    for unit in ("mm", "in", "mm"):
        window.set_display_unit(unit)
        if running:
            assert all(
                panel.list.item(index).text().startswith(tr("Voriger Stand: {line}", line=""))
                for index in range(panel.list.count())
            ), "Alte Sammelzeilen dürfen durch das Umrechnen nicht zum neuen Stand werden"
        selected = panel.list.currentItem()
        assert selected is not None, "Die gewählte Hinweisgruppe ging verloren"
        assert selected.data(Qt.ItemDataRole.UserRole).severity == "info"
        assert set(selected.data(_BODIES_ROLE)) == {"a", "b"}
        assert panel.finding_details_toggle.isChecked()
        assert not panel.finding_details.isHidden()
        assert ten_millimetres(language, unit) in panel.finding_details.toPlainText()
        assert ten_millimetres(language, unit) in selected.toolTip()
        assert selected.text().startswith(tr("Voriger Stand: {line}", line="")) is running
        buttons = [
            button
            for button in panel.findChildren(QPushButton)
            if button.property(guides.TARGET_PROPERTY) == "finding.action:place_on_bed"
            and not button.isHidden()
        ]
        assert buttons, "Die Handlung der gewählten Gruppe muss weiterhin vorhanden sein"
        assert all(button.isEnabled() is not running for button in buttons)
        assert [finding_to_data(one) for one in findings] == original
        assert panel.list.count() == 2
    panel.add_findings(findings)
    assert panel.list.count() == 2, "Die rohen Mitglieder werden nicht doppelt gezählt"
    if running:
        panel.add_findings([Finding("split.plan", "info", _("Keine Überschneidungen gefunden."))])
        fresh = next(
            panel.list.item(index)
            for index in range(panel.list.count())
            if panel.list.item(index).data(Qt.ItemDataRole.UserRole).code == "split.plan"
        )
        assert not fresh.text().startswith(tr("Voriger Stand: {line}", line=""))
        panel.set_running(False)


@pytest.mark.parametrize("difference", ["source", "step", "actions"])
def test_distinct_groups_of_the_same_bodies_keep_the_chosen_group(
    window, profile: Profile, difference: str
) -> None:
    """Rohmitglieder mit anderen Schritten, Quellen oder Auswegen sind eigene Gruppen."""
    bodies, raw = paired_placement(profile)
    originals = raw[:2]
    if difference == "source":
        others = [dataclasses.replace(one, source="gcode") for one in originals]
    elif difference == "step":
        others = [dataclasses.replace(one, op_id="second-step") for one in originals]
    else:
        others = [
            dataclasses.replace(one, suggestions=(Action("show_report", _("Prüfbericht")),))
            for one in originals
        ]
    panel = window.report
    panel.show_result(
        EvaluationResult(Scene(objects=bodies, report=Report(tuple(originals + others))))
    )
    assert panel.list.count() == 2
    panel.list_toggle.setChecked(True)
    panel.list.setCurrentRow(1)
    chosen = panel.list.currentItem().data(Qt.ItemDataRole.UserRole)
    expected = (chosen.source, chosen.op_id, chosen.suggestions)
    for unit in ("mm", "in", "mm"):
        window.set_display_unit(unit)
        selected = panel.list.currentItem()
        assert selected is not None
        actual = selected.data(Qt.ItemDataRole.UserRole)
        assert (actual.source, actual.op_id, actual.suggestions) == expected
        assert panel.list.currentRow() == 1, "Gleiche Körper bedeuten nicht denselben Bericht"
