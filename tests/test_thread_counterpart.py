"""Das Gegenstück zu einem Gewinde, das schon da ist (P2.6, Entscheidung 15).

Die drei Paare in ``counterpart.PAIRS`` setzen beide Hälften neu. Ein
eingelesener Bolzen oder ein gedrucktes Gewinde hat seine Hälfte schon: Was
fehlt, ist das gegengleiche Gewinde am anderen Teil und die Passung
dazwischen. Das Maß kommt aus dem Gewinde selbst und muss ein Tabellenmaß
treffen — ein Gewinde Ø 6,4 mit Steigung 1,1 wird nicht still zu M6.
"""

from __future__ import annotations

import itertools

import pytest

from app.core.bootstrap import load_operations
from app.core.counterpart import (
    THREAD_SIZE_REACH,
    apply_thread_counterpart,
    attach_thread_fit,
    thread_counterpart_draft,
    thread_size_for,
)
from app.core.errors import ValidationError
from app.core.knowledge import standards
from app.core.scene import ResultCache, evaluate
from app.core.scene.fits import active_fits
from app.core.scene.history import History, OperationDraft
from app.core.scene.project import new_project
from app.core.types import Document, Feature, Profile, Scene


@pytest.fixture(autouse=True)
def _operations() -> None:
    load_operations()


def _kernel_or_skip(kind: str) -> None:
    if kind == "brep":
        kernel = pytest.importorskip("app.core.brep.kernel")
        if not kernel.available():
            pytest.skip("ohne OpenCASCADE gibt es den exakten Kern nicht")


def _generated(
    diameter: float,
    pitch: float,
    *,
    internal: bool = False,
    provenance: str = "generated",
    **more: object,
) -> Feature:
    params: dict[str, object] = {
        "diameter": diameter,
        "pitch": pitch,
        "internal": internal,
        "length": 8.0,
        "centre": (0.0, 0.0, 14.0),
        "axis": (0.0, 0.0, 1.0),
        **more,
    }
    return Feature(id="thread_1", kind="thread", provenance=provenance, params=params)  # type: ignore[arg-type]


def _two_plates(profile: Profile, kind: str) -> tuple[Document, ResultCache]:
    """Zwei Platten nebeneinander, je Kern — die Ausgangslage jedes Gegenstücks."""
    document = new_project("centauri-carbon-2", "petg").document
    box = "create_brep_box" if kind == "brep" else "create_box"
    drafts = [
        OperationDraft(op=box, params={"width": 40.0, "depth": 30.0, "height": 10.0}),
        OperationDraft(op=box, params={"width": 40.0, "depth": 30.0, "height": 10.0}),
    ]
    History(document).apply("Zwei Platten", drafts)
    History(document).apply(
        "Die zweite daneben",
        [OperationDraft(op="translate_object", inputs=("obj_2",), params={"dx": 60.0})],
    )
    return document, ResultCache()


def _with_thread(
    document: Document, cache: ResultCache, profile: Profile, *, internal: bool
) -> tuple[Feature, Scene]:
    """Ein M6 × 1 an der ersten Platte — als Bolzen auf ihr oder als Gewinde in ihr."""
    History(document).apply(
        "Gewinde an der ersten Platte",
        [
            OperationDraft(
                op="insert_printed_thread",
                inputs=("obj_1",),
                params={"size": "M6", "length": 8.0, "internal": internal, "z": 10.0},
            )
        ],
    )
    result = evaluate(document, profile, cache=cache)
    assert result.stopped_at is None
    # Am Netz liest die Erkennung über denselben Gängen ein zweites, gemessenes
    # Gewinde; gemeint ist das des Bausteins.
    threads = [
        feature
        for feature in result.scene.objects["obj_1"].features.values()
        if feature.kind == "thread" and feature.provenance == "generated"
    ]
    assert len(threads) == 1, "die erste Platte trägt genau ein erzeugtes Gewinde"
    return threads[0], result.scene


def test_the_reach_never_lets_one_thread_match_two_table_sizes() -> None:
    """Die Erkennungsgrenze ist kleiner als der halbe Abstand je zweier Nachbargrößen.

    Sonst träfe ein Gewinde zwischen M2 und M2,5 beide, und die Wahl fiele auf
    die Reihenfolge der Tabelle statt auf das Maß.
    """
    sizes = [standards.screw(size) for size in standards.screw_sizes()]
    assert len(sizes) >= 5
    for first, second in itertools.combinations(sizes, 2):
        both_near = (
            abs(first.nominal - second.nominal) <= 2.0 * THREAD_SIZE_REACH[0]
            and abs(first.pitch - second.pitch) <= 2.0 * THREAD_SIZE_REACH[1]
        )
        assert not both_near, f"{first.size} und {second.size} liegen innerhalb der Grenze"


def test_a_thread_names_its_table_size_and_a_stray_one_names_the_nearest() -> None:
    assert thread_size_for(_generated(6.0, 1.0)) == "M6"
    # Ein gemessenes Gewinde liegt neben dem Nennmaß — die Spiel- und
    # Messabweichung bleibt innerhalb der Grenze.
    assert thread_size_for(_generated(5.9, 1.0, provenance="native")) == "M6"
    assert thread_size_for(_generated(8.1, 1.25)) == "M8"
    with pytest.raises(ValidationError) as caught:
        thread_size_for(_generated(6.4, 1.1))
    assert caught.value.constraint == "no_standard_size"
    assert caught.value.values["nearest"] == "M6"
    assert caught.value.suggestions, "Regel 17"


def test_the_draft_is_the_opposite_thread_in_the_table_size() -> None:
    draft = thread_counterpart_draft(_generated(6.0, 1.0), "obj_2", {"at_feature": "face_top_1"})
    assert draft.op == "insert_printed_thread"
    assert draft.inputs == ("obj_2",)
    assert draft.params["size"] == "M6"
    assert draft.params["internal"] is True, "zum Bolzen das Gewinde in der Wand"
    assert draft.params["length"] == pytest.approx(8.0)
    assert draft.params["at_feature"] == "face_top_1"
    bolt = thread_counterpart_draft(_generated(6.0, 1.0, internal=True), "obj_2", {"z": 10.0})
    assert bolt.params["internal"] is False, "zum Gewindeloch der Bolzen"
    assert bolt.params["z"] == pytest.approx(10.0)


def test_only_a_right_hand_thread_gets_a_counterpart() -> None:
    hole = Feature(
        id="hole_1", kind="hole", provenance="native", params={"diameter": 6.0, "depth": 10.0}
    )
    with pytest.raises(ValidationError) as caught:
        thread_counterpart_draft(hole, "obj_2", {})
    assert caught.value.constraint == "not_a_thread"
    assert caught.value.suggestions
    with pytest.raises(ValidationError) as caught:
        thread_counterpart_draft(_generated(6.0, 1.0, handedness="left"), "obj_2", {})
    assert caught.value.constraint == "left_handed"
    assert caught.value.suggestions


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_the_counterpart_lands_in_one_step_and_its_fit_names_both_threads(
    profile: Profile, kind: str
) -> None:
    """Ein Schritt, eine Passung — und beide Kennungen sind gelesen, nicht geraten."""
    _kernel_or_skip(kind)
    document, cache = _two_plates(profile, kind)
    thread, _scene = _with_thread(document, cache, profile, internal=False)
    before = len(document.transactions)

    applied = apply_thread_counterpart(document, thread, "obj_1", "obj_2", {"x": 60.0, "z": 10.0})

    assert len(document.transactions) == before + 1, "das Gegenstück ist eine Handlung"
    step = document.ops[-1]
    assert step.op == "insert_printed_thread" and step.inputs == ("obj_2",)
    assert step.params["size"] == "M6" and step.params["internal"] is True
    assert step.params["length"] == pytest.approx(8.0)
    assert applied.object_ids == ["obj_1", "obj_2"]

    result = evaluate(document, profile, cache=cache)
    assert result.stopped_at is None, "beide Hälften rechnen durch"
    applied = attach_thread_fit(document, applied, thread, result.scene)

    assert applied.fit is not None
    assert applied.fit.kind == "thread"
    assert applied.fit.a.object_id == "obj_1" and applied.fit.a.feature_id == thread.id
    assert applied.fit.b.object_id == "obj_2"
    made = result.scene.objects["obj_2"].features[applied.fit.b.feature_id]
    assert made.kind == "thread" and made.params["internal"] is True
    assert made.params["diameter"] == pytest.approx(6.0)
    assert made.params["pitch"] == pytest.approx(1.0)
    assert str(applied.fit.tolerance) == "auto:", "die Toleranz ist ein Verweis (Regel 7)"
    assert applied.fit in active_fits(document)
    assert [entry.code for entry in applied.findings] == ["parts.counterpart_fit"]

    # Und die Passung wird geprüft, ohne als unmessbar zu gelten.
    checked = evaluate(document, profile, cache=cache)
    assert checked.stopped_at is None
    codes = {finding.code for finding in checked.scene.report.findings}
    assert "fit.not_measurable" not in codes


def test_an_internal_thread_gets_a_bolt(profile: Profile) -> None:
    document, cache = _two_plates(profile, "mesh")
    thread, _scene = _with_thread(document, cache, profile, internal=True)
    assert thread.params["internal"] is True

    apply_thread_counterpart(document, thread, "obj_1", "obj_2", {"x": 60.0, "z": 10.0})

    step = document.ops[-1]
    assert step.op == "insert_printed_thread" and step.params["internal"] is False
    assert step.params["size"] == "M6"
    result = evaluate(document, profile, cache=cache)
    assert result.stopped_at is None
    bolts = [
        feature
        for feature in result.scene.objects["obj_2"].features.values()
        if feature.kind == "thread" and feature.provenance == "generated"
    ]
    assert len(bolts) == 1 and bolts[0].params["internal"] is False


def test_one_undo_takes_the_counterpart_and_its_fit(profile: Profile) -> None:
    document, cache = _two_plates(profile, "mesh")
    thread, _scene = _with_thread(document, cache, profile, internal=False)
    ops_before, fits_before = len(document.ops), len(document.fits)

    applied = apply_thread_counterpart(document, thread, "obj_1", "obj_2", {"x": 60.0, "z": 10.0})
    result = evaluate(document, profile, cache=cache)
    attach_thread_fit(document, applied, thread, result.scene)
    assert len(document.ops) == ops_before + 1 and len(document.fits) == fits_before + 1

    History(document).undo()

    assert len(document.ops) == ops_before
    assert len(document.fits) == fits_before, "ein Undo nimmt Gewinde und Passung"


def test_the_same_body_is_refused_with_a_sentence(profile: Profile) -> None:
    document, cache = _two_plates(profile, "mesh")
    thread, _scene = _with_thread(document, cache, profile, internal=False)
    with pytest.raises(ValidationError) as caught:
        apply_thread_counterpart(document, thread, "obj_1", "obj_1", {"z": 10.0})
    assert caught.value.constraint == "same_object"
    assert caught.value.suggestions


def test_a_changed_history_leaves_the_fit_out_and_says_so(profile: Profile) -> None:
    document, cache = _two_plates(profile, "mesh")
    thread, _scene = _with_thread(document, cache, profile, internal=False)
    applied = apply_thread_counterpart(document, thread, "obj_1", "obj_2", {"x": 60.0, "z": 10.0})
    result = evaluate(document, profile, cache=cache)
    History(document).apply(
        "Dazwischen",
        [OperationDraft(op="translate_object", inputs=("obj_2",), params={"dx": 1.0})],
    )

    applied = attach_thread_fit(document, applied, thread, result.scene)

    assert applied.fit is None and not document.fits
    assert [entry.code for entry in applied.findings] == ["parts.counterpart_unpaired"]
