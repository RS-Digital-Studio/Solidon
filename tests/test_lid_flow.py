"""Ein Deckel und seine Schachtel sind eine Passung (Bauplan §14, §29).

Der Deckel holt sein Spiel seit jeher aus dem Materialprofil — und trug
trotzdem keinen ``Fit``. Damit liefen die drei Regeln aus ``slice/advise.py``
ins Leere, die genau für Passungen da sind: genaue Außenwand, gebremste
Beschleunigung, Bügeln. Ausgerechnet dort, wo das Zusammenspiel zweier Teile
der Zweck ist, druckte Solidon wie an einer beliebigen Wand.
"""

from __future__ import annotations

import pytest

from app.core.bootstrap import load_operations
from app.core.geom.lid import (
    CAP_THREAD_FEATURE,
    CAVITY_FEATURE,
    COLLAR_FEATURE,
    NECK_THREAD_FEATURE,
)
from app.core.knowledge import profiles
from app.core.lid_flow import apply_lid, unique_name
from app.core.scene import History, evaluate
from app.core.scene.project import ProjectSources, new_project
from app.core.types import FeatureRef, Fit, Profile


@pytest.fixture(autouse=True)
def _operations() -> None:
    load_operations()


@pytest.fixture
def profile() -> Profile:
    return profiles.make_profile("centauri-carbon-2", "petg")


def _box_with_cavity(document: object, profile: Profile) -> str:
    """Eine Schachtel: Quader, ausgehöhlt, oben offen."""
    from app.core.scene.history import OperationDraft

    history = History(document)  # type: ignore[arg-type]
    history.apply(
        "Schachtel",
        [
            OperationDraft(op="create_box", params={"width": 60.0, "depth": 40.0, "height": 30.0}),
        ],
    )
    made = document.ops[-1].outputs[0]  # type: ignore[attr-defined]
    history.apply(
        "Aushöhlen",
        [
            OperationDraft(
                op="hollow_object",
                inputs=(made,),
                params={"wall": 3.0, "open_top": True},
            )
        ],
    )
    return str(document.ops[-1].outputs[0])  # type: ignore[attr-defined]


def _round_container(document: object) -> str:
    """Eine runde, oben offene Dose für den vollständigen Drehdeckel-Ablauf."""
    from app.core.scene.history import OperationDraft

    history = History(document)  # type: ignore[arg-type]
    history.apply(
        "Dose",
        [OperationDraft(op="create_cylinder", params={"diameter": 40.0, "height": 60.0})],
    )
    made = document.ops[-1].outputs[0]  # type: ignore[attr-defined]
    history.apply(
        "Aushöhlen",
        [
            OperationDraft(
                op="hollow_object",
                inputs=(made,),
                params={"wall": 3.0, "open_top": True},
            )
        ],
    )
    return str(document.ops[-1].outputs[0])  # type: ignore[attr-defined]


def test_the_lid_and_its_box_become_a_fit(profile: Profile) -> None:
    """Der Kern des Befunds: nach dem Ablauf steht ein Paar im Dokument."""
    project = new_project("centauri-carbon-2", "petg")
    document = project.document
    box = _box_with_cavity(document, profile)

    applied = apply_lid(document, box, {"thickness": 3.0, "collar": 4.0}, profile)

    assert applied.fit is not None, "ohne Passung greift keine der Regeln aus advise.py"
    assert len(document.fits) == 1
    fit = document.fits[0]
    assert fit.a.feature_id == CAVITY_FEATURE
    assert fit.b.feature_id == COLLAR_FEATURE
    assert fit.kind == "clearance"


def test_the_tolerance_stays_a_reference(profile: Profile) -> None:
    """Regel 7: die Toleranz verweist ins Materialprofil, nie die Zahl selbst.

    Sonst erreicht eine Kalibrierung nach §28.3 einen Deckel nicht, der vor
    ihr entstanden ist — und genau dafür gibt es die Kalibrierung.
    """
    project = new_project("centauri-carbon-2", "petg")
    document = project.document
    box = _box_with_cavity(document, profile)

    apply_lid(document, box, {"thickness": 3.0, "collar": 4.0}, profile)

    assert str(document.fits[0].tolerance) == "auto:petg"


def test_both_features_exist_after_evaluation(profile: Profile) -> None:
    """Die Passung zeigt auf Merkmale — und die müssen die Auswertung überstehen.

    Ein ``Fit`` auf einen Namen, den niemand vergibt, wäre beim Öffnen ein
    verwaister Verweis (§21.3) und würde beim Nutzer als Frage landen.
    """
    project = new_project("centauri-carbon-2", "petg")
    document = project.document
    box = _box_with_cavity(document, profile)
    applied = apply_lid(document, box, {"thickness": 3.0, "collar": 4.0}, profile)

    result = evaluate(document, profile, sources=ProjectSources(project))

    assert result.complete
    box_id, lid_id = applied.object_ids[0], applied.object_ids[1]
    assert CAVITY_FEATURE in result.scene.objects[box_id].features
    assert COLLAR_FEATURE in result.scene.objects[lid_id].features
    assert result.scene.objects[box_id].features[CAVITY_FEATURE].params["fit_role"] == "inner"
    assert result.scene.objects[lid_id].features[COLLAR_FEATURE].params["fit_role"] == "outer"
    assert not any(finding.code == "fit.not_measurable" for finding in result.scene.report.findings)


def test_the_screw_lid_flow_pairs_the_outer_and_inner_threads(profile: Profile) -> None:
    """Öffnung wählen und Drehdeckel erzeugen bleibt eine rücknehmbare Handlung."""
    project = new_project("centauri-carbon-2", "petg")
    container = _round_container(project.document)

    applied = apply_lid(
        project.document,
        container,
        {"height": 8.0, "pitch": 3.0, "wall": 2.4, "thickness": 2.4},
        profile,
        op="screw_lid",
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert applied.fit is not None
    assert len(project.document.transactions[-1].ops) == 1
    assert project.document.transactions[-1].title == "Drehdeckel erzeugen"
    assert applied.fit.a.feature_id == NECK_THREAD_FEATURE
    assert applied.fit.b.feature_id == CAP_THREAD_FEATURE
    assert NECK_THREAD_FEATURE in result.scene.objects[applied.fit.a.object_id].features
    assert CAP_THREAD_FEATURE in result.scene.objects[applied.fit.b.object_id].features
    from app.core.scene.fits import check as check_fits

    assert "fit.not_measurable" not in {item.code for item in check_fits(result.scene, profile)}

    History(project.document).undo()
    assert project.document.fits == [], "Undo nimmt Drehdeckel und Passung gemeinsam zurück"


def test_the_fit_is_actually_measurable(profile: Profile) -> None:
    """Eine Passung, die nur dasteht, ist die halbe Zusicherung.

    Sie wirkt auf den Slicer — genaue Außenwand, gebremstes Tempo — und sagte
    trotzdem nichts darüber, ob der Deckel passt: ``fits.check`` sucht bei
    einer Spielpassung zwei Durchmesser und meldete „lässt sich nicht messen".
    Beide Merkmale tragen deshalb ihre engste Weite, und ihr Unterschied ist
    genau das doppelte Spiel plus die Entlastung.
    """
    from app.core.scene.fits import check as check_fits

    project = new_project("centauri-carbon-2", "petg")
    document = project.document
    box = _box_with_cavity(document, profile)
    apply_lid(document, box, {"thickness": 3.0, "collar": 4.0}, profile)

    result = evaluate(document, profile, sources=ProjectSources(project))
    findings = check_fits(result.scene, profile, document=document)

    assert "fit.not_measurable" not in {entry.code for entry in findings}, (
        "die Passung muss prüfbar sein, nicht nur eingetragen"
    )


def test_undo_takes_the_fit_with_it(profile: Profile) -> None:
    """§15.5: was zur Transaktion gehört, geht mit ihr zurück.

    Bliebe die Passung stehen, zeigte sie auf einen Deckel, den es nicht mehr
    gibt — und das Öffnen der Datei fragte danach.
    """
    project = new_project("centauri-carbon-2", "petg")
    document = project.document
    box = _box_with_cavity(document, profile)
    apply_lid(document, box, {"thickness": 3.0, "collar": 4.0}, profile)
    assert len(document.fits) == 1

    History(document).undo()

    assert document.fits == [], "eine Passung ohne ihren Deckel ist ein verwaister Verweis"


def test_a_second_lid_gets_its_own_name(profile: Profile) -> None:
    """Zwei Passungen desselben Namens wären eine."""
    project = new_project("centauri-carbon-2", "petg")
    document = project.document
    document.fits.append(Fit(name="deckel", a=FeatureRef("obj_1", "a"), b=FeatureRef("obj_2", "b")))

    assert unique_name(document) == "deckel_2"


def test_the_flow_says_what_it_did(profile: Profile) -> None:
    """§2.7: der Befund erklärt, warum das für den Druck zählt."""
    project = new_project("centauri-carbon-2", "petg")
    document = project.document
    box = _box_with_cavity(document, profile)

    applied = apply_lid(document, box, {"thickness": 3.0, "collar": 4.0}, profile)

    assert [entry.code for entry in applied.findings] == ["parts.lid_fit"]


def test_a_flat_lid_gets_no_fit_onto_a_missing_collar(profile: Profile) -> None:
    """Bei ``collar=0`` gibt es kein ``lid_collar``-Merkmal mehr (C-12) — eine
    Passung darauf meldete bei jedem Öffnen eine Geometrie, die es nicht gibt.

    Und die Gegenseite: Wer ``collar`` gar nicht angibt, bekommt die
    Schemavorgabe (4 mm) und damit weiterhin seine Passung.
    """
    project = new_project("centauri-carbon-2", "petg")
    document = project.document
    box = _box_with_cavity(document, profile)

    applied = apply_lid(document, box, {"thickness": 3.0, "collar": 0.0}, profile)

    assert applied.fit is None, "ein flacher Deckel hat keinen Kragen zu paaren"
    from app.core.scene.fits import active_fits

    assert len(document.fits) == 1
    assert active_fits(document) == []
    assert len(applied.object_ids) == 2, "der Deckel selbst entsteht trotzdem"
    result = evaluate(document, profile, sources=ProjectSources(project))
    assert result.complete
    assert not any(finding.code.startswith("fit.") for finding in result.scene.report.findings)

    project2 = new_project("centauri-carbon-2", "petg")
    box2 = _box_with_cavity(project2.document, profile)
    without = apply_lid(project2.document, box2, {"thickness": 3.0}, profile)
    assert without.fit is not None, "die Schemavorgabe trägt einen Kragen"


def test_a_collar_written_as_an_expression_counts_as_a_number(profile: Profile) -> None:
    """Ein Ausdruck ist ein Wert und keine Ausnahme (§13).

    ``float("@collar")`` scheitert, und der Fehlschlag hieß „kein flacher
    Deckel" — also das Gegenteil dessen, was ``@collar = 0`` bedeutet. Die
    Nullprüfung darüber ließ sich damit umgehen, indem man denselben Wert als
    Parameter schrieb: Die Passung zeigte auf ein ``lid_collar``, das es nicht
    gibt.

    Aufgelöst wird über den Auswerter des Kerns gegen die Projektparameter —
    kein ``eval`` (Regel 10). Beide Richtungen stehen hier, denn ein Ausdruck
    über null ist genauso ein Ausdruck.
    """
    from app.core.types import Parameter

    project = new_project("centauri-carbon-2", "petg")
    document = project.document
    document.parameters["collar"] = Parameter(name="collar", value=0.0)
    box = _box_with_cavity(document, profile)

    applied = apply_lid(document, box, {"thickness": 3.0, "collar": "@collar"}, profile)

    assert applied.fit is None, "ein Kragen von null bleibt null, auch als Ausdruck geschrieben"
    from app.core.scene.fits import active_fits

    assert len(document.fits) == 1
    assert active_fits(document) == []

    # Die Gegenprobe: derselbe Weg mit einem Wert, der einen Kragen ergibt.
    other = new_project("centauri-carbon-2", "petg")
    other.document.parameters["collar"] = Parameter(name="collar", value=4.0)
    box2 = _box_with_cavity(other.document, profile)
    thick = apply_lid(other.document, box2, {"thickness": 3.0, "collar": "@collar"}, profile)

    assert thick.fit is not None, "ein Ausdruck über vier Millimeter trägt seine Passung"


@pytest.mark.parametrize("initial,changed", [(0.0, 4.0), (4.0, 0.0)])
@pytest.mark.parametrize("parameter", [False, True])
def test_lid_fit_follows_later_collar_changes(
    profile: Profile, tmp_path, initial, changed, parameter
) -> None:
    from app.core.scene.fits import active_fits
    from app.core.scene.project import load, save
    from app.core.types import Parameter

    project = new_project("centauri-carbon-2", "petg")
    document = project.document
    document.parameters["collar"] = Parameter(name="collar", value=initial)
    box = _box_with_cavity(document, profile)
    apply_lid(document, box, {"collar": "@collar" if parameter else initial}, profile)
    operation = document.ops[-1]
    assert len(document.fits) == 1
    if parameter:
        document.parameters["collar"] = Parameter(name="collar", value=changed)
    else:
        History(document).change_params(operation.id, {"collar": changed})
    reopened = load(save(project, tmp_path / "changed-lid.solidon"))
    result = evaluate(reopened.document, profile, sources=ProjectSources(reopened))
    assert result.complete
    assert bool(active_fits(reopened.document)) is (changed > 0)
    assert bool(result.scene.fits) is (changed > 0)
    assert "fit.missing_feature" not in {finding.code for finding in result.scene.report.findings}


@pytest.mark.parametrize("condition", [(999, "collar"), (1, "missing")])
def test_invalid_fit_condition_is_visible_instead_of_disabling_the_fit(profile, condition):
    from app.core.scene.fits import active_fits, check
    from app.core.types import Scene

    project = new_project("centauri-carbon-2", "petg")
    box = _box_with_cavity(project.document, profile)
    apply_lid(project.document, box, {"collar": 4}, profile)
    fit = project.document.fits[0]
    import dataclasses

    project.document.fits[0] = dataclasses.replace(fit, when_positive=condition)
    active = active_fits(project.document)
    assert len(active) == 1
    findings = check(Scene(fits=active), profile, document=project.document)
    assert {finding.code for finding in findings} == {"fit.invalid_condition"}


def test_positive_collar_still_reports_a_lost_feature(profile):
    from app.core.scene.fits import check
    from app.core.types import Scene

    project = new_project("centauri-carbon-2", "petg")
    box = _box_with_cavity(project.document, profile)
    apply_lid(project.document, box, {"collar": 4}, profile)
    findings = check(Scene(fits=project.document.fits), profile, document=project.document)
    assert {finding.code for finding in findings} == {"fit.missing_feature"}


@pytest.mark.parametrize("collar", [0.0, 4.0])
def test_replanning_a_lid_rebinds_its_condition_and_roundtrips_undo(profile, tmp_path, collar):
    from app.core.scene.fits import active_fits
    from app.core.scene.project import load, save

    project = new_project("centauri-carbon-2", "petg")
    box = _box_with_cavity(project.document, profile)
    apply_lid(project.document, box, {"collar": collar}, profile)
    original = project.document.fits[0]
    history = History(project.document)
    original_id = project.document.ops[-1].id
    history.repair_and_retry(original_id)
    replanned_id = history.operations[-1].id
    assert replanned_id != original_id
    assert project.document.fits[0].when_positive == (replanned_id, "collar")
    reopened = load(save(project, tmp_path / "replanned-lid.solidon"))
    result = evaluate(reopened.document, profile, sources=ProjectSources(reopened))
    assert result.complete
    assert "fit.invalid_condition" not in {entry.code for entry in result.scene.report.findings}
    assert bool(active_fits(reopened.document)) is (collar > 0)
    restored = History(reopened.document)
    restored.undo()
    assert reopened.document.fits == [original]
    assert restored.operations[-1].id == original_id
    restored.redo()
    assert reopened.document.fits[0].when_positive == (replanned_id, "collar")
    restored.change_params(replanned_id, {"collar": 4.0 if collar == 0 else 0.0})
    assert bool(active_fits(reopened.document)) is (collar == 0)


def test_removing_a_fit_condition_step_takes_its_fit_and_undo_restores_both(profile, tmp_path):
    import dataclasses

    from app.core.scene.project import load, save

    project = new_project("centauri-carbon-2", "petg")
    box = _box_with_cavity(project.document, profile)
    hollow_id = project.document.ops[-1].id
    apply_lid(project.document, box, {"collar": 4.0}, profile)
    project.document.fits[0] = dataclasses.replace(
        project.document.fits[0], when_positive=(hollow_id, "wall")
    )
    original = project.document.fits[0]
    History(project.document).remove_operations([hollow_id])
    assert project.document.fits == []
    reopened = load(save(project, tmp_path / "removed-condition.solidon"))
    restored = History(reopened.document)
    restored.undo()
    assert reopened.document.fits == [original]
    assert restored.operation(hollow_id).op == "hollow_object"
    restored.redo()
    assert reopened.document.fits == []


def _load_v19_lid(data, path):
    """Ein echter Projektcontainer trägt die reine historische JSON-Vorlage."""
    import json
    import zipfile

    from app.core.scene.project import load

    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("project.json", json.dumps(data))
    return load(path)


def test_v19_flat_lid_gains_a_dynamic_fit_with_parameter_undo_and_roundtrip(profile, tmp_path):
    import json
    from pathlib import Path

    from app.core.scene.fits import active_fits
    from app.core.scene.history import change_for
    from app.core.scene.project import load, save
    from app.core.types import Parameter

    data = json.loads(
        (Path(__file__).parent / "data/projects/flat_lid_v19.json").read_text(encoding="utf-8")
    )
    project = _load_v19_lid(data, tmp_path / "v19-flat.p3d")
    document = project.document
    assert document.format_version == 20
    assert len(document.fits) == 1 and document.fits[0].tolerance == "auto:petg"
    assert document.fits[0].when_positive == (3, "collar")
    assert active_fits(document) == []
    history = History(document)
    history.apply(
        "Kragen", changes=change_for(document, parameters={"collar": Parameter("collar", 4.0)})
    )
    restored = load(save(project, tmp_path / "v20-roundtrip.p3d"))
    result = evaluate(restored.document, profile, sources=ProjectSources(restored))
    assert result.complete and len(result.scene.fits) == 1
    assert not {"fit.missing_feature", "fit.invalid_condition"} & {
        f.code for f in result.scene.report.findings
    }
    history = History(restored.document)
    history.undo()
    assert active_fits(restored.document) == []
    history.undo()
    assert restored.document.fits == []
    history.redo()
    assert len(restored.document.fits) == 1 and not active_fits(restored.document)
    history.redo()
    assert len(active_fits(restored.document)) == 1


@pytest.mark.parametrize(
    "flat,removed,replanned",
    [(False, False, False), (False, True, False), (True, False, True), (False, False, True)],
)
def test_v19_fit_migration_preserves_explicit_removal_and_old_replan_states(
    profile, tmp_path, flat, removed, replanned
):
    from app.core.scene.fits import active_fits
    from app.core.scene.history import change_for
    from app.core.scene.serialise import document_to_data

    project = new_project("centauri-carbon-2", "petg")
    box = _box_with_cavity(project.document, profile)
    apply_lid(project.document, box, {"collar": 0.0 if flat else 4.0}, profile)
    history = History(project.document)
    first_id = project.document.ops[-1].id
    if removed:
        history.apply("Passung entfernen", changes=change_for(project.document, fits=[]))
    if replanned:
        history.repair_and_retry(first_id)
    data = document_to_data(project.document)
    data["format_version"] = 19
    fit_lists = [data["fits"]]
    for transaction in data["transactions"]:
        for state in (transaction.get("changes") or {}).values():
            if state.get("fits") is not None:
                fit_lists.append(state["fits"])
    for fits in fit_lists:
        if flat:
            fits.clear()  # v19 legte für den flachen Deckel keine Beziehung an.
        else:
            for fit in fits:
                fit.pop("when_positive", None)
    migrated = _load_v19_lid(data, tmp_path / "historical-lid.p3d")
    history = History(migrated.document)
    if removed:
        assert migrated.document.fits == []
        history.undo()
        assert migrated.document.fits[0].when_positive == (first_id, "collar")
        history.redo()
        assert migrated.document.fits == []
    else:
        assert migrated.document.fits[0].when_positive == (history.operations[-1].id, "collar")
        if replanned:
            history.undo()
            assert migrated.document.fits[0].when_positive == (first_id, "collar")
            history.redo()
            assert migrated.document.fits[0].when_positive == (history.operations[-1].id, "collar")
        history.change_params(history.operations[-1].id, {"collar": 4.0 if flat else 0.0})
        assert bool(active_fits(migrated.document)) is flat
