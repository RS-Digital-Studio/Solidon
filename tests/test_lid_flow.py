"""Ein Deckel und seine Schachtel sind eine Passung (Bauplan §14, §29).

Der Deckel holt sein Spiel seit jeher aus dem Materialprofil — und trug
trotzdem keinen ``Fit``. Damit liefen die drei Regeln aus ``slice/advise.py``
ins Leere, die genau für Passungen da sind: genaue Außenwand, gebremste
Beschleunigung, Bügeln. Ausgerechnet dort, wo das Zusammenspiel zweier Teile
der Zweck ist, druckte Formwerk wie an einer beliebigen Wand.
"""

from __future__ import annotations

import pytest

from app.core.bootstrap import load_operations
from app.core.geom.lid import CAVITY_FEATURE, COLLAR_FEATURE
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
