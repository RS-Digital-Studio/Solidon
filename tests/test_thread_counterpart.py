"""Das Gegenstück zu einem Gewinde, das schon da ist (P2.6, Entscheidung 15).

Die drei Paare in ``counterpart.PAIRS`` setzen beide Hälften neu. Ein
eingelesener Bolzen oder ein gedrucktes Gewinde hat seine Hälfte schon: Was
fehlt, ist das gegengleiche Gewinde am anderen Teil und die Passung
dazwischen. Das Maß kommt aus dem Gewinde selbst und muss ein Tabellenmaß
treffen — ein Gewinde Ø 6,4 mit Steigung 1,1 wird nicht still zu M6.
"""

from __future__ import annotations

import dataclasses
import itertools

import numpy as np
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
from tests.helpers import exact_kernel


@pytest.fixture(autouse=True)
def _operations() -> None:
    load_operations()


def _kernel_or_skip(kind: str) -> None:
    if kind == "brep":
        exact_kernel()


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


@pytest.mark.parametrize(
    ("shape", "constraint"),
    [({"starts": 2, "lead": 2.0}, "multi_start"), ({"taper": 1.7899}, "thread_shape")],
    ids=["zweigaengig", "kegelig"],
)
def test_a_multi_start_or_tapered_thread_gets_no_library_counterpart(
    shape: dict, constraint: str
) -> None:
    """Das Bibliotheksgewinde ist eingängig und zylindrisch (P2.5, 22.09.2026).

    Zu einem zweigängigen Bolzen M6 entstand ein eingängiges Gegenstück M6 —
    halber Vorschub, schraubt nicht; zu einem kegeligen Rohrgewinde eines mit
    festem Durchmesser. Beides stand als gelungenes Gegenstück im Baum. Die
    Gangzahl sagt ab wie beim Neuschneiden (``multi_start``), der Kegel mit
    eigenem Grund.
    """
    with pytest.raises(ValidationError) as caught:
        thread_counterpart_draft(_generated(6.0, 1.0, **shape), "obj_2", {})
    assert caught.value.constraint == constraint
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
    # Das Nennmaß der Tabelle, und gebaut um das Spiel des Materials weiter.
    assert made.params["nominal"] == pytest.approx(6.0)
    assert made.params["diameter"] == pytest.approx(6.0 + profile.material.clearance)
    assert made.params["pitch"] == pytest.approx(1.0)
    assert str(applied.fit.tolerance) == "auto:", "die Toleranz ist ein Verweis (Regel 7)"
    assert applied.fit in active_fits(document)
    assert [entry.code for entry in applied.findings] == ["parts.counterpart_fit"]

    # Und die Passung wird geprüft, ohne als unmessbar zu gelten.
    checked = evaluate(document, profile, cache=cache)
    assert checked.stopped_at is None
    codes = {finding.code for finding in checked.scene.report.findings}
    assert "fit.not_measurable" not in codes


def _built_diameter(scene: Scene, object_id: str, feature: Feature) -> float:
    """Der Außendurchmesser der Gänge, am gebauten Körper gemessen.

    Außen ist es der Kamm, innen der Grund der Nut — beides der größte Abstand
    einer Ecke von der Achse, eine Steigung weg von den Enden (dort laufen
    die Gänge aus) und nahe an der Achse (die Ecken der Platte zählen nicht).
    """
    from app.core.geom.mesh import as_mesh_data

    vertices = np.asarray(as_mesh_data(scene.objects[object_id].mesh).raw.vertices)
    centre = np.asarray(feature.params["centre"], dtype=float)
    along = vertices[:, 2] - centre[2]
    radial = np.hypot(vertices[:, 0] - centre[0], vertices[:, 1] - centre[1])
    reach = float(feature.params["length"]) / 2.0 - float(feature.params["pitch"])
    near = radial < float(feature.params["diameter"]) / 2.0 + 1.0
    return 2.0 * float(radial[(np.abs(along) < reach) & near].max())


@pytest.mark.parametrize("internal", [False, True])
@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_a_printed_pair_fits_with_the_play_it_is_built_with(
    profile: Profile, kind: str, internal: bool
) -> None:
    """Das Paar aus *Gegenstück zum Gewinde* passt, und beide Merkmale nennen ihr gebautes Maß.

    Jede Hälfte eines gedruckten Gewindes ist um das Spiel des Materials neben
    ihr gebaut: die Mutter um das Spiel weiter, der Bolzen um das Spiel enger.
    Beide Merkmale nannten aber das Nennmaß, und die Passung maß „0,00 mm
    statt 0,20 mm“ — an jedem frisch angelegten Paar, seit 0.5.0.
    """
    from app.core.scene.fits import check, resolve, target
    from app.core.units import round_display

    _kernel_or_skip(kind)
    document, cache = _two_plates(profile, kind)
    thread, _scene = _with_thread(document, cache, profile, internal=internal)
    applied = apply_thread_counterpart(document, thread, "obj_1", "obj_2", {"x": 60.0, "z": 10.0})
    result = evaluate(document, profile, cache=cache)
    applied = attach_thread_fit(document, applied, thread, result.scene)
    assert applied.fit is not None

    checked = evaluate(document, profile, cache=cache)
    assert checked.stopped_at is None
    findings = check(checked.scene, profile, document=document)
    assert not [entry for entry in findings if entry.code.startswith("fit.")], [
        (entry.code, dict(entry.values)) for entry in findings
    ]

    halves = [
        (ref.object_id, resolve(checked.scene, ref)) for ref in (applied.fit.a, applied.fit.b)
    ]
    for object_id, feature in halves:
        assert feature is not None
        assert round_display(float(feature.params["diameter"])) == round_display(
            _built_diameter(checked.scene, object_id, feature)
        ), "das Merkmal nennt den Durchmesser, der gebaut ist"
    by_role = {bool(feature.params["internal"]): feature for _id, feature in halves if feature}
    gap = float(by_role[True].params["diameter"]) - float(by_role[False].params["diameter"])
    play = profile.material.clearance
    assert round_display(gap) == round_display(2.0 * play), "jede Hälfte trägt das Spiel einmal"
    assert round_display(target(checked.scene, applied.fit, profile)[0]) == round_display(gap)


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


# --- eingelesene Gewinde: STEP und Netz --------------------------------------------
#
# Bis zum 22.09.2026 fuhren alle Tests hier ein Gewinde, das Solidon selbst
# erzeugt hatte (``provenance == "generated"``). Ein Kunde bringt seinen Bolzen
# aber als STEP oder STL mit; dann liest die Erkennung Durchmesser, Steigung,
# Gangzahl und Händigkeit aus der Geometrie. Die Sollwerte kommen aus den
# Konstruktionsmaßen des Gewindekorpus (``tests/data/make_thread_corpus.py``).


def _profile() -> Profile:
    from app.core.knowledge import profiles

    return profiles.make_profile("centauri-carbon-2", "petg")


def _imported(name: str, kind: str) -> tuple[Document, ResultCache, Feature, object]:
    """Ein Gewinde aus dem Korpus, über den Ladeweg eingelesen, und eine Platte daneben.

    ``kind="mesh"`` liest dasselbe Teil als STL — so, wie es aus einem Slicer
    oder einer Modellseite kommt.
    """
    from pathlib import Path

    from app.core.brep import step
    from app.core.geom.mesh import as_mesh_data
    from app.core.scene.project import ProjectSources
    from app.core.types import Source

    _kernel_or_skip("brep")
    corpus = Path(__file__).parent / "data" / "threads" / f"{name}.step"
    if kind == "brep":
        payload, suffix = corpus.read_bytes(), "step"
    else:
        payload = as_mesh_data(step.read(corpus.read_bytes())).raw.export(file_type="stl")
        suffix = "stl"
    project = new_project("centauri-carbon-2", "petg")
    document = project.document
    document.sources["src_1"] = Source(
        id="src_1", kind="import", path=f"sources/1_{name}.{suffix}", sha256=""
    )
    project.sources["src_1"] = payload
    # Der Ladeweg der Anwendung: STEP über den Importplan (exakter Körper),
    # STL über ``load``.
    from app.core.ingest.plan import import_plan

    plan = import_plan("src_1", f"{name}.{suffix}", payload)
    draft = plan.draft
    if suffix == "stl":
        # Ein Teil von zwölf Millimetern lässt die Einheit offen; der Kunde
        # beantwortet die Frage mit Millimetern.
        draft = dataclasses.replace(draft, params={**draft.params, "unit": "mm"})
    History(document).apply(plan.title, [draft])
    History(document).apply(
        "Platte",
        [OperationDraft(op="create_box", params={"width": 40.0, "depth": 30.0, "height": 10.0})],
    )
    History(document).apply(
        "Daneben",
        [OperationDraft(op="translate_object", inputs=("obj_2",), params={"dx": 60.0})],
    )
    cache = ResultCache()
    sources = ProjectSources(project)
    result = evaluate(document, _profile(), cache=cache, sources=sources)
    assert result.stopped_at is None
    threads = [f for f in result.scene.objects["obj_1"].features.values() if f.kind == "thread"]
    assert len(threads) == 1, f"der Korpus trägt genau ein Gewinde: {[f.id for f in threads]}"
    assert threads[0].provenance != "generated", "eingelesen, nicht erzeugt"
    return document, cache, threads[0], sources


@pytest.mark.parametrize("kind", ["brep", "mesh"])
@pytest.mark.parametrize(
    ("name", "size", "internal"), [("m6_rechts", "M6", True), ("m8_innen", "M8", False)]
)
def test_an_imported_thread_gets_its_counterpart_and_a_measurable_fit(
    kind: str, name: str, size: str, internal: bool
) -> None:
    """Ein eingelesener Bolzen bekommt seine Mutter, ein eingelesenes Innengewinde seinen Bolzen."""
    document, cache, thread, sources = _imported(name, kind)
    profile = _profile()

    applied = apply_thread_counterpart(document, thread, "obj_1", "obj_2", {"x": 60.0, "z": 10.0})
    step_params = document.ops[-1].params
    assert step_params["size"] == size and step_params["internal"] is internal

    result = evaluate(document, profile, cache=cache, sources=sources)
    assert result.stopped_at is None
    applied = attach_thread_fit(document, applied, thread, result.scene)
    assert applied.fit is not None, [str(f.message) for f in applied.findings]
    checked = evaluate(document, profile, cache=cache, sources=sources)
    codes = {finding.code for finding in checked.scene.report.findings}
    assert "fit.not_measurable" not in codes
    assert "fit.missing_feature" not in codes
    # Und sie passt: Die gedruckte Hälfte trägt ihr Spiel, die eingelesene,
    # was sie gemessen hat — innen die Lochkorrektur (Ø 8,2 im Korpus).
    assert "fit.violated" not in codes, [
        dict(finding.values)
        for finding in checked.scene.report.findings
        if finding.code == "fit.violated"
    ]


def test_a_multi_start_thread_is_refused_with_a_sentence() -> None:
    """Ein zweigängiges Gewinde hat kein eingängiges Gegenstück.

    ``zweigaengig.step`` trägt zwei Gänge mit 1 mm Teilung auf Ø 8. Bis zum
    22.09.2026 fragte ``thread_counterpart_draft`` die Gangzahl nicht und sagte
    „kein Normmaß, nächstes M8" — ein Satz über das falsche Maß, und bei einer
    Steigung, die zufällig in der Tabelle steht, wäre still ein eingängiges
    Gegengewinde entstanden, das nicht greift.
    """
    from pathlib import Path

    from app.core.brep import step
    from app.core.brep.features import features_of

    _kernel_or_skip("brep")
    solid = step.read((Path(__file__).parent / "data/threads/zweigaengig.step").read_bytes())
    thread = next(f for f in features_of(solid).values() if f.kind == "thread")
    assert thread.params.get("starts") == 2
    with pytest.raises(ValidationError) as caught:
        thread_counterpart_draft(thread, "obj_2", {})
    assert caught.value.constraint == "multi_start"
    assert caught.value.suggestions

    # Und auch dort, wo Durchmesser und Steigung eine Tabellengröße träfen.
    lookalike = _generated(8.0, 1.25, starts=2)
    with pytest.raises(ValidationError) as caught:
        thread_counterpart_draft(lookalike, "obj_2", {})
    assert caught.value.constraint == "multi_start"


def test_a_thread_beyond_the_table_says_where_the_table_ends() -> None:
    """Ein M10 aus einer Datei: Die Tabelle reicht bis M8, und der Satz sagt das.

    Bis zum 22.09.2026 hieß es „Setzen Sie das Gegenstück als Baustein mit der
    nächsten Größe" und nannte M8 — für einen Bolzen M10 kein Gegenstück,
    sondern ein Loch, durch das er fällt.
    """
    feature = _generated(10.0, 1.5)
    with pytest.raises(ValidationError) as caught:
        thread_size_for(feature)
    assert caught.value.constraint == "beyond_table"
    assert caught.value.values["largest"] == "M8"
