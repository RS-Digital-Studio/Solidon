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
    findings = check_fits(result.scene, profile)

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
    assert document.fits == []
    assert len(applied.object_ids) == 2, "der Deckel selbst entsteht trotzdem"

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
    assert document.fits == []

    # Die Gegenprobe: derselbe Weg mit einem Wert, der einen Kragen ergibt.
    other = new_project("centauri-carbon-2", "petg")
    other.document.parameters["collar"] = Parameter(name="collar", value=4.0)
    box2 = _box_with_cavity(other.document, profile)
    thick = apply_lid(other.document, box2, {"thickness": 3.0, "collar": "@collar"}, profile)

    assert thick.fit is not None, "ein Ausdruck über vier Millimeter trägt seine Passung"
