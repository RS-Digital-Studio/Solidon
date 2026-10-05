"""Die gemeinsame Druckziel- und Statusauskunft liest belegte Daten (RM-090)."""

import pytest

from app.core.knowledge import profiles
from app.core.scene import EvaluationResult
from app.core.scene.project import new_project
from app.core.types import Finding, MaterialSlot, Scene
from app.ui.print_contract import finding_consequence, handoff_state, print_target
from tests.helpers import make_object


@pytest.mark.parametrize(
    "printer_id, material_id",
    [
        ("centauri-carbon-2", "petg"),
        ("unknown-printer", "petg"),
        ("centauri-carbon-2", "unknown-material"),
        ("", ""),
    ],
)
def test_target_never_uses_replacement_profiles(printer_id, material_id):
    document = new_project("centauri-carbon-2", "petg").document
    document.printer, document.material = printer_id, material_id
    target = print_target(document, None)
    valid = printer_id == "centauri-carbon-2" and material_id == "petg"
    assert bool(target.missing) is not valid
    if printer_id == "unknown-printer":
        assert printer_id in target.title
        assert "Allgemein" not in target.title
    assert (document.printer, document.material) == (printer_id, material_id)


def test_target_keeps_materials_and_valid_profile_without_inventory_reference():
    document = new_project("centauri-carbon-2", "petg").document
    first = make_object("a", "Gehäuse")
    second = make_object("b", "Dichtung")
    first.material, second.material = "petg", "tpu-95a"
    first.material_slots = [MaterialSlot(0, "Nicht mehr im Lager", material_type="PETG")]
    result = EvaluationResult(Scene(objects={"a": first, "b": second}))
    target = print_target(document, result)
    assert not target.missing
    assert str(profiles.material("petg").title) in target.details
    assert str(profiles.material("tpu-95a").title) in target.details
    assert "Orientierung" in target.details
    second.material = "missing"
    assert "Dichtung" in "\n".join(print_target(document, result).missing)


def test_target_distinguishes_resin_and_incompatible_material():
    printer = next(entry for entry in profiles.printer_profiles().values() if entry.is_resin)
    material = next(entry for entry in profiles.material_profiles().values() if entry.fits(printer))
    document = new_project(printer.id, material.id).document
    target = print_target(document, None)
    assert "Resin" in target.title and not target.missing
    document.material = "petg"
    assert print_target(document, None).missing


def test_cached_target_follows_language_without_reading_the_scene_again():
    from app.i18n import get_language, set_language
    from app.i18n.catalog import install_language

    document = new_project("centauri-carbon-2", "petg").document
    document.material = "missing"
    target = print_target(document, None)
    original = get_language()
    try:
        install_language("en")
        set_language("en")
        assert "unvollständig" not in target.title
        assert "Materialprofil fehlt" not in target.missing[0]
        assert "Orientierung" not in target.details
        set_language("de")
        assert "unvollständig" in target.title
        assert "Materialprofil fehlt" in target.missing[0]
        assert "Orientierung" in target.details
    finally:
        set_language(original)


@pytest.mark.parametrize(
    "severity, incomplete, expected",
    [
        (None, True, "Bewertung unvollständig"),
        ("error", True, "Übergabe nicht empfohlen"),
        ("warning", True, "Bewertung unvollständig"),
        ("warning", False, "Entscheidung erforderlich"),
        (None, False, "Bereit zur Übergabe"),
        ("info", False, "Bereit zur Übergabe"),
    ],
)
def test_handoff_state_requires_completed_scope_even_without_findings(
    severity, incomplete, expected
):
    findings = [Finding("example", severity, "Beleg")] if severity else []
    assert handoff_state(findings, ("Prüfung fehlt",) if incomplete else ()) == expected


def test_preview_explanation_reads_the_same_scenes_and_does_not_claim_print_checks():
    from app.core.geom.difference import SceneDifference
    from app.ui.print_contract import explain_difference

    before = Scene(objects={"a": make_object("a", "Platte")})
    after = Scene(objects={"b": make_object("b", "Halter")})
    original = SceneDifference(created=("b",), deleted=("a",))
    explained = explain_difference(original, before, after, "Teilen")
    assert explained.created == original.created and explained.deleted == original.deleted
    assert "Ziel: Teilen" in explained.explanation
    assert "Körperzahl: 1 → 1" in explained.explanation
    assert "Platte" in explained.explanation and "Halter" in explained.explanation
    assert "Außenmaß" in explained.explanation and "nicht vorhanden" in explained.explanation
    assert "noch nicht vollständig geprüft" in explained.explanation


def test_handoff_receipt_stays_frozen_and_separates_written_from_opened(tmp_path):
    from app.ui.print_contract import handoff_receipt

    document = new_project("centauri-carbon-2", "petg").document
    body = make_object("a", "Deckel")
    written = (tmp_path / "eins.3mf", tmp_path / "zwei.3mf")
    finding = Finding("export.loss", "warning", "Farben werden nicht übernommen.")
    receipt = handoff_receipt(
        document=document,
        profile=profiles.make_profile(document.printer, document.material),
        objects=(body,),
        written=written,
        opened=written[:1],
        findings=(finding,),
        with_settings=False,
        status="Teilübergabe abgebrochen",
        slicer="Slicer A",
        total_objects=3,
    )
    text = receipt.values["detail"]
    document.material = "pla"
    body.name = "Später umbenannt"
    assert receipt.values["detail"] == text
    assert "Deckel" in text and "Später umbenannt" not in text
    assert "1 von 3 Körpern" in text
    assert all(str(path) in text for path in written)
    assert "erfolgreich geöffnete Dateien: 1" in text
    assert "nicht mitgegeben" in text and "Farben werden nicht übernommen" in text
    assert "nicht durchgeführt" in text and "G-Code-Prüfung ist ein eigener Schritt" in text


@pytest.mark.parametrize("state", ["not_started", "running", "cancelled", "failed"])
def test_check_states_never_turn_an_incomplete_check_into_readiness(state):
    from app.core.types import CheckState
    from app.ui.print_contract import check_summary

    details, missing = check_summary((CheckState("slice.print_findings", "a", state=state),))
    assert details and missing
    assert handoff_state((), missing) == "Bewertung unvollständig"


def test_check_summary_uses_visible_names():
    from app.core.types import CheckState
    from app.ui.print_contract import check_summary

    text, _ = check_summary((CheckState("slice.print_findings", "obj_17"),), {"obj_17": "Segel"})
    assert "Segel" in text and "obj_17" not in text


@pytest.mark.parametrize("state", ["completed", "cancelled", "not_started", "failed"])
def test_review_only_calls_findings_resolved_after_complete_checks(state):
    from app.core.types import CheckState
    from app.ui.print_contract import ExplainedDifference, review_difference

    old = Finding("slice.island", "warning", "Freistehende Insel")
    new = Finding("slice.bridge", "warning", "Neue lange Brücke")
    checks = (CheckState("slice.print_findings", "a", state=state),)
    reviewed = review_difference(ExplainedDifference(), [(old,), (new,)], [checks, checks])
    assert "Warnungen oder Fehler: 1 vorher, 1 nachher." in reviewed.explanation
    assert "Neu im Nachherstand: Neue lange Brücke" in reviewed.explanation
    assert ("nicht mehr vorhanden: Freistehende Insel" in reviewed.explanation) == (
        state == "completed"
    )
    assert reviewed.findings == (new,)


def test_review_names_only_what_changes_and_counts_the_rest():
    """Am Piratenschiff standen 32 Warnungen je Stand im Vorschauband (RM-090).

    Gegenprobe vor dem Umbau: 2 × 32 Zeilen. Genannt wird jetzt, was neu ist
    oder wegfällt, je höchstens vier, der Rest als Zahl.
    """
    from app.core.types import CheckState
    from app.ui.print_contract import ExplainedDifference, review_difference

    staying = [
        Finding("slice.island", "warning", f"Insel {index}", object_id=f"obj_{index}")
        for index in range(30)
    ]
    gone = [Finding(f"wall.thin_{index}", "warning", f"Dünne Wand {index}") for index in range(6)]
    new = [Finding(f"bridge.long_{index}", "warning", f"Brücke {index}") for index in range(6)]
    checks = (CheckState("slice.print_findings", "a", state="completed"),)
    reviewed = review_difference(
        ExplainedDifference(),
        [(*staying, *gone), (*staying, *new)],
        [checks, checks],
    )
    lines = reviewed.explanation.splitlines()
    assert len(lines) <= 14, lines
    assert "Warnungen oder Fehler: 36 vorher, 36 nachher." in lines
    assert sum("Neu im Nachherstand" in line for line in lines) == 4
    assert sum("nicht mehr vorhanden" in line for line in lines) == 4
    assert lines.count("… und 2 weitere.") == 2
    assert not any("Insel" in line for line in lines), "Unverändertes wird nicht wiederholt"


def test_a_project_without_its_own_printer_opens_with_the_customers_defaults(tmp_path, monkeypatch):
    """Ein Beispiel trägt keinen Drucker: Es öffnet mit den Vorgaben des Kunden, wie ein neues.

    Seit das Druckziel streng aus dem Projekt liest, stand über jedem
    mitgelieferten Beispiel „Druckziel fehlt · Verfahren unbekannt ·
    unvollständig“, und der Prüfbericht meldete „Bewertung unvollständig“ —
    obwohl der Kunde beim ersten Start einen Drucker gewählt hatte; gerechnet
    wurde mit dem allgemeinen Drucker statt mit seinem. Ein Projekt mit eigenem
    Drucker behält ihn, und geändert ist nach dem Öffnen keines.
    """
    from app.core import examples
    from app.core.scene.project import load, save
    from app.ui.session import Session

    example = examples.directory() / "dose-mit-deckel.p3d"
    assert load(example).document.printer == "", "die Probe braucht ein Beispiel ohne Drucker"
    session = Session()
    monkeypatch.setattr(session, "evaluate_async", lambda *_args, **_kwargs: None)

    session.open_project(example, "centauri-carbon-2", "petg")
    document = session.project.document
    assert (document.printer, document.material) == ("centauri-carbon-2", "petg")
    assert not session.modified
    target = session.review_target()
    assert not target.missing, target.missing
    assert target.title.startswith(profiles.printer_profiles()["centauri-carbon-2"].title)

    session.open_project(example)
    document = session.project.document
    assert (document.printer, document.material) == (
        profiles.DEFAULT_PRINTER,
        profiles.DEFAULT_MATERIAL,
    )

    own = new_project("bambu-a1", "abs")
    path = tmp_path / "eigen.p3d"
    save(own, path)
    session.open_project(path, "centauri-carbon-2", "petg")
    document = session.project.document
    assert (document.printer, document.material) == ("bambu-a1", "abs")


# --- Die Befundkarte (RM-508) ---------------------------------------------------


def test_the_finding_line_says_consequence_place_and_basis_in_one_line():
    """„Hinweis · Dose · intern geschätzt“ statt dreier Sätze (Entscheidung Robert, 05.10.2026)."""
    from app.ui.panels import finding_meta

    hint = Finding("hollow.done", "info", "Ausgehöhlt.", object_id="obj_1")
    assert finding_meta(hint, "Dose") == "Hinweis · Dose · intern geschätzt"
    measured = Finding("gcode.time", "warning", "Länger als geschätzt.", source="gcode")
    assert finding_meta(measured, "") == "Warnung · aus G-Code"


def test_the_finding_line_starts_with_a_capital_in_every_language():
    """Die Kataloge schreiben die Schwere klein, weil sie sonst im Satz steht."""
    from app.i18n import set_language
    from app.i18n.catalog import install_language
    from app.ui.panels import finding_meta

    install_language("en")
    set_language("en")
    try:
        line = finding_meta(Finding("hollow.done", "info", "Hollowed."), "Box")
    finally:
        set_language("de")
    assert line[0].isupper(), line
    assert "Box" in line


def test_a_consequence_sentence_only_where_the_finding_tips_the_target():
    """Ein eigener Folgesatz nur bei echter Folge: Ein Fehler lässt die Übergabe nicht empfehlen."""
    assert finding_consequence(Finding("a", "error", "Kaputt.")).startswith("Folge:")
    assert finding_consequence(Finding("a", "warning", "Riskant.")) == ""
    assert finding_consequence(Finding("a", "info", "Gut.")) == ""


def test_the_place_is_named_and_shown_only_where_the_finding_has_one():
    """Kein erfundener Ort: Ohne Stelle zeigt der Knopf den Körper, ohne Körper fehlt er."""
    from app.ui.panels import finding_place

    body = make_object("obj_1")
    live = {"obj_1": body}
    names = {"obj_1": str(body.name), "obj_2": "Deckel"}
    located = Finding("a", "warning", "Hier.", object_id="obj_1", location=(1.0, 2.0, 3.0))
    assert finding_place(located, (), live, names) == (str(body.name), "Stelle zeigen")
    loose = Finding("a", "info", "Irgendwo.", object_id="obj_1")
    assert finding_place(loose, (), live, names) == (str(body.name), "Körper zeigen")
    gone = Finding("a", "info", "Weg.", object_id="obj_9")
    assert finding_place(gone, (), live, names) == ("Körper nicht mehr vorhanden", "")
    assert finding_place(Finding("a", "info", "Ortlos."), (), live, names) == ("", "")
    bundle = finding_place(loose, ("obj_1", "obj_2"), live, names)
    assert bundle == (f"{body.name}, Deckel", "Körper zeigen")


@pytest.mark.parametrize(
    "message, expected",
    [
        (
            "Die dünnste Stelle ist schmaler als die Mindestbahnbreite. Eine kleinere Düse wählen.",
            "Die dünnste Stelle ist schmaler als die Mindestbahnbreite.",
        ),
        ("Ausgehöhlt. Die Wandstärke stimmt.", "Ausgehöhlt."),
        ("Dünner als 0,16 mm. 3 Stellen.", "Dünner als 0,16 mm."),
        ("Zum Beispiel z. B. eine Bohrung.", "Zum Beispiel z. B. eine Bohrung."),
        ("Use a finer nozzle, e.g. the 0.2 mm one.", "Use a finer nozzle, e.g. the 0.2 mm one."),
        ("Deckel erzeugt — das Spiel kommt aus dem Materialprofil.", None),
    ],
)
def test_a_report_row_reads_as_its_first_sentence(message, expected):
    """Die Liste zeigt je Befund seinen ersten Satz; die gewählte Zeile steht ganz da (RM-508)."""
    from app.ui.panels import headline

    assert headline(message) == (message if expected is None else expected)


def test_every_value_in_a_report_row_carries_its_name():
    """„— Deckel · 0 mm³ · 100 %“ ließ raten, welche Zahl was ist (Durchsicht B18)."""
    from app.ui.labels import value_line
    from app.ui.panels import _line_for

    finding = Finding(
        "orient.saves_support",
        "info",
        "Anders gedreht braucht das Teil weniger Stützen.",
        object_id="obj_1",
        values={"support_cm3": 0.0, "saved_percent": 100.0},
    )
    line = _line_for(finding, {"obj_1": "Deckel"})
    for key, value in finding.values.items():
        assert value_line(key, value) in line, line
    collision = Finding(
        "arrange.collision",
        "warning",
        "Zwei Objekte überschneiden sich.",
        values={"a": "A", "b": "B"},
    )
    assert "— A · B" in _line_for(collision), "die beiden Körper sind selbst Namen"


def test_counts_leave_out_what_is_not_there():
    """„0 x Fehler“ stand über jedem sauberen Modell (Durchsicht B17)."""
    from app.ui.tab_signal import count_phrases, counted

    assert count_phrases(0, 2, 4) == ["2 Warnungen", "4 Hinweise"]
    assert count_phrases(1, 1, 1) == ["1 Fehler", "1 Warnung", "1 Hinweis"]
    assert count_phrases(0, 0, 0) == []
    assert counted(2, 0) == "2 Fehler"
