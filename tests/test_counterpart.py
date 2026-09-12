"""Gegenstücke auf zwei Körpern sind eine Handlung (RM-147 E1, §14, §24).

Ein Passstift ohne seine Bohrung ist nichts. Beide zu setzen waren bis dahin
drei Schritte — Stift an A, Bohrung an B, Maße ein zweites Mal eintippen — und
drei Rücknahmen für etwas, das zusammen gedacht ist.

Geprüft wird deshalb genau das Zusammen: **ein** Verlaufsschritt, **eine**
Passung mit den Kennungen, die die Auswertung wirklich vergeben hat, und ein
Undo, das alles drei nimmt.
"""

from __future__ import annotations

import pytest

from app.core.bootstrap import load_operations
from app.core.counterpart import (
    PAIRS,
    apply_counterpart,
    attach_fit,
    drafts_for,
    pair_named,
)
from app.core.errors import ValidationError
from app.core.knowledge import profiles
from app.core.scene import ResultCache, evaluate
from app.core.scene.history import History, OperationDraft
from app.core.scene.project import new_project
from app.core.types import Document, Operation, Profile, Scene, Transaction


@pytest.fixture(autouse=True)
def _operations() -> None:
    load_operations()


@pytest.fixture
def profile() -> Profile:
    return profiles.make_profile("centauri-carbon-2", "petg")


def _two_plates(profile: Profile) -> tuple[Document, ResultCache, Scene]:
    """Zwei Platten nebeneinander — die Ausgangslage jedes Gegenstücks."""
    document = new_project("centauri-carbon-2", "petg").document
    History(document).apply(
        "Zwei Platten",
        [
            OperationDraft(op="create_box", params={"width": 40.0, "depth": 30.0, "height": 10.0}),
            OperationDraft(
                op="create_box",
                params={"width": 40.0, "depth": 30.0, "height": 10.0, "x": 60.0},
            ),
        ],
    )
    cache = ResultCache()
    result = evaluate(document, profile, cache=cache)
    return document, cache, result.scene


def test_both_halves_land_in_one_step_with_one_set_of_measurements(profile: Profile) -> None:
    """Ein Schritt, ein Undo — und die Maße stehen genau einmal.

    Das ist der ganze Punkt: Zwei getrennte Einsetzschritte kann man heute
    schon machen; was fehlte, war, dass sie **zusammen** gehören. Ein Stift von
    6 mm in einer Bohrung von 5 mm ist kein Paar, und die einzige Stelle, an
    der so etwas entsteht, ist die zweite Eingabe.
    """
    document, cache, _scene = _two_plates(profile)
    before = len(document.transactions)

    applied = apply_counterpart(
        document,
        pair_named("dowel"),
        "obj_1",
        "obj_2",
        shared={"diameter": 6.0, "length": 8.0},
        first_place={"z": 10.0},
        second_place={"z": 10.0},
    )

    assert len(document.transactions) == before + 1, "beide Hälften sind eine Handlung"
    stift, bohrung = document.ops[-2], document.ops[-1]
    assert stift.op == "insert_dowel" and stift.params["kind"] == "pin"
    assert bohrung.op == "insert_dowel" and bohrung.params["kind"] == "bore"
    assert stift.params["diameter"] == bohrung.params["diameter"] == 6.0
    assert stift.params["length"] == bohrung.params["length"] == 8.0
    assert applied.object_ids == ["obj_1", "obj_2"]

    result = evaluate(document, profile, cache=cache)
    assert result.stopped_at is None, "beide Hälften rechnen durch"


@pytest.mark.parametrize("count", [0, 1, 2])
def test_counterpart_logging_preserves_incomplete_results(
    monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture, count: int
) -> None:
    """Auch der schon abgefangene unvollständige Rückgabefall bleibt protokollierbar."""
    document = new_project("centauri-carbon-2", "petg").document
    document.ops = [
        Operation(index + 1, "insert_dowel", {}, outputs=(f"obj_{index + 1}",))
        for index in range(count)
    ]
    transaction = Transaction("t1", "Paar", tuple(step.id for step in document.ops))
    monkeypatch.setattr(History, "apply", lambda *_args, **_kwargs: transaction)

    with caplog.at_level("INFO", logger="app.core.counterpart"):
        applied = apply_counterpart(document, pair_named("dowel"), "obj_1", "obj_2", {}, {}, {})

    assert applied.object_ids == [f"obj_{index + 1}" for index in range(count)]
    messages = [entry.getMessage() for entry in caplog.records if "counterpart" in entry.name]
    assert len(messages) == 1
    assert "dowel" in messages[0]
    assert all(identifier in messages[0] for identifier in applied.object_ids)


def test_the_fit_names_the_features_the_run_really_created(profile: Profile) -> None:
    """Die Kennungen werden gelesen, nicht geraten.

    Sie entstehen bei der Auswertung (``evaluate._renamed``): Ein zweiter Stift
    am selben Körper heißt ``dowel_pin_2``. Der erste Anlauf dieses Ablaufs
    schrieb ``pin_1`` hin und bekam ``dowel_pin_1`` — eine Passung auf einen
    erfundenen Namen wäre still ins Leere gegangen.
    """
    document, cache, _scene = _two_plates(profile)
    pair = pair_named("dowel")

    applied = apply_counterpart(
        document,
        pair,
        "obj_1",
        "obj_2",
        shared={"diameter": 6.0, "length": 8.0},
        first_place={"z": 10.0},
        second_place={"z": 10.0},
    )
    result = evaluate(document, profile, cache=cache)
    applied = attach_fit(document, applied, pair, result.scene)

    assert applied.fit is not None
    assert applied.fit.a.feature_id in result.scene.objects["obj_1"].features
    assert applied.fit.b.feature_id in result.scene.objects["obj_2"].features
    assert applied.fit.kind == "clearance"
    assert str(applied.fit.tolerance) == "auto:", "die Toleranz ist ein Verweis (Regel 7)"
    assert [entry.code for entry in applied.findings] == ["parts.counterpart_fit"]


def test_one_undo_takes_the_geometry_and_the_fit(profile: Profile) -> None:
    """Ein Undo, das die Hälften nimmt und die Passung stehen lässt, hinterließe
    einen Verweis auf ein Merkmal, das es nicht mehr gibt (§15.5)."""
    document, cache, _scene = _two_plates(profile)
    pair = pair_named("dowel")
    steps_before = len(document.ops)

    applied = apply_counterpart(
        document,
        pair,
        "obj_1",
        "obj_2",
        shared={"diameter": 6.0, "length": 8.0},
        first_place={"z": 10.0},
        second_place={"z": 10.0},
    )
    result = evaluate(document, profile, cache=cache)
    attach_fit(document, applied, pair, result.scene)
    assert len(document.fits) == 1

    History(document).undo()

    assert len(document.ops) == steps_before, "beide Hälften sind zurück"
    assert document.fits == [], "und die Passung mit ihnen"


@pytest.mark.parametrize("change", ["new_step", "undo", "empty_history"])
def test_a_late_fit_leaves_a_changed_history_untouched(profile: Profile, change: str) -> None:
    """Ein altes Auswertungsergebnis trägt keine Passung an einer anderen Transaktion vorbei ein."""
    document, cache, _scene = _two_plates(profile)
    pair = pair_named("dowel")
    applied = apply_counterpart(
        document,
        pair,
        "obj_1",
        "obj_2",
        shared={"diameter": 6.0, "length": 8.0},
        first_place={"z": 10.0},
        second_place={"z": 10.0},
    )
    result = evaluate(document, profile, cache=cache)
    assert result.stopped_at is None
    history = History(document)
    if change == "new_step":
        history.apply("Ein weiterer Körper", [OperationDraft(op="create_box")])
    else:
        history.undo()
        if change == "empty_history":
            history.undo()
    before_fits = tuple(document.fits)
    before_transactions = tuple(document.transactions)

    attach_fit(document, applied, pair, result.scene)

    assert tuple(document.fits) == before_fits
    assert tuple(document.transactions) == before_transactions
    assert applied.fit is None
    assert [finding.code for finding in applied.findings] == ["parts.counterpart_unpaired"]


def test_a_second_pair_gets_its_own_fit(profile: Profile) -> None:
    """Zwei Stifte sind zwei Paare — nicht ein Name, der den ersten überschreibt.

    Zwei Passungen mit gleichem Namen wären eine, und die zweite Verbindung
    fiele still aus der Prüfung.
    """
    document, cache, _scene = _two_plates(profile)
    pair = pair_named("dowel")

    # Zwei Stifte an **verschiedenen** Stellen: an derselben stünde der zweite
    # im ersten, und die Messung ginge an der Frage vorbei.
    for versatz in (-10.0, 10.0):
        applied = apply_counterpart(
            document,
            pair,
            "obj_1",
            "obj_2",
            shared={"diameter": 6.0, "length": 8.0},
            first_place={"x": versatz, "z": 10.0},
            second_place={"x": 60.0 + versatz, "z": 10.0},
        )
        result = evaluate(document, profile, cache=cache)
        attach_fit(document, applied, pair, result.scene)

    assert [entry.name for entry in document.fits] == ["dowel_1", "dowel_2"]
    assert len({entry.a.feature_id for entry in document.fits}) == 2, (
        "zwei Paare zeigen auf zwei verschiedene Stifte"
    )


def test_the_same_body_twice_is_refused_with_a_sentence(profile: Profile) -> None:
    """Stift und Bohrung im selben Körper wären ein Loch neben einem Zapfen."""
    document, _cache, _scene = _two_plates(profile)

    with pytest.raises(ValidationError) as refused:
        apply_counterpart(
            document,
            pair_named("dowel"),
            "obj_1",
            "obj_1",
            shared={"diameter": 6.0},
            first_place={},
            second_place={},
        )

    assert refused.value.constraint == "same_object"
    assert refused.value.suggestions


def test_an_unknown_pair_names_the_known_ones() -> None:
    """Regel 17: Ein Fehler endet nie mit „fehlgeschlagen"."""
    with pytest.raises(ValidationError) as refused:
        pair_named("schwalbenschwanz")

    assert refused.value.constraint == "unknown_pair"
    assert "dowel" in str(refused.value.values["known"])


def test_every_pair_names_parts_and_features_that_exist() -> None:
    """Was die Tabelle verspricht, muss die Bibliothek halten.

    Ein Merkmalsname, den der Baustein nicht führt, ergäbe eine Passung ins
    Leere — und zwar erst beim Kunden, denn der Ablauf legt sie ohne Murren an.
    """
    from app.core.knowledge.parts.registry import PARTS

    assert PAIRS, "leere Tabelle — dann prüft dieser Test nichts"
    for pair in PAIRS:
        for name, feature in ((pair.part_a, pair.feature_a), (pair.part_b, pair.feature_b)):
            spec = PARTS.get(name)
            assert feature in spec.features, f"{name} verspricht kein {feature!r}"


def test_every_shared_parameter_exists_in_both_halves() -> None:
    """Ein gemeinsames Maß, das nur eine Hälfte kennt, ist keines.

    Es wanderte still in einen Schritt, der es nicht liest — und die zweite
    Hälfte bekäme ihre Vorgabe statt des eingestellten Werts.
    """
    from app.core.knowledge.parts.registry import PARTS

    for pair in PAIRS:
        for name in (pair.part_a, pair.part_b):
            felder = {entry.name for entry in PARTS.get(name).params.spec()}
            fehlend = [wert for wert in pair.shared if wert not in felder]
            assert not fehlend, f"{name} kennt {fehlend} nicht"


def test_the_drafts_can_be_read_before_anything_is_built() -> None:
    """Was entstünde, ohne dass etwas entsteht — der Weg der Vorschau."""
    drafts = drafts_for(
        pair_named("dowel"),
        "obj_1",
        "obj_2",
        shared={"diameter": 6.0, "length": 8.0, "unbekannt": 3.0},
        first_place={"z": 10.0},
        second_place={"z": 4.0},
    )

    assert [entry.op for entry in drafts] == ["insert_dowel", "insert_dowel"]
    assert drafts[0].params["kind"] == "pin"
    assert drafts[1].params["kind"] == "bore"
    assert drafts[0].params["z"] == 10.0 and drafts[1].params["z"] == 4.0
    assert "unbekannt" not in drafts[0].params, (
        "nur was das Paar als gemeinsam erklärt, geht in die Schritte"
    )
