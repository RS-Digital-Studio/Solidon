"""Das Gegenstück zu einem Gewinde, das schon da ist (P2.6, Entscheidung 15).

Die drei Paare in ``counterpart.PAIRS`` setzen beide Hälften neu. Ein
eingelesener Bolzen oder ein gedrucktes Gewinde hat seine Hälfte schon: Was
fehlt, ist das gegengleiche Gewinde am anderen Teil und die Passung
dazwischen. Das Maß kommt aus dem Gewinde selbst: eine Tabellengröße, wo es
eine trifft, sonst sein eigenes — ein Gewinde Ø 6,4 mit Steigung 1,1 wird
nicht still zu M6.
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
    thread_values_for,
)
from app.core.errors import ValidationError
from app.core.knowledge import standards
from app.core.knowledge.parts.fasteners import CUSTOM_SIZE
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


def _two_plates(
    profile: Profile, kind: str, *, width: float = 40.0, depth: float = 30.0
) -> tuple[Document, ResultCache]:
    """Zwei Platten nebeneinander, je Kern — die Ausgangslage jedes Gegenstücks."""
    document = new_project("centauri-carbon-2", "petg").document
    box = "create_brep_box" if kind == "brep" else "create_box"
    drafts = [
        OperationDraft(op=box, params={"width": width, "depth": depth, "height": 10.0}),
        OperationDraft(op=box, params={"width": width, "depth": depth, "height": 10.0}),
    ]
    History(document).apply("Zwei Platten", drafts)
    History(document).apply(
        "Die zweite daneben",
        [OperationDraft(op="translate_object", inputs=("obj_2",), params={"dx": width + 20.0})],
    )
    return document, ResultCache()


def _with_thread(
    document: Document,
    cache: ResultCache,
    profile: Profile,
    *,
    internal: bool,
    size: dict[str, object] | None = None,
) -> tuple[Feature, Scene]:
    """Ein M6 × 1 an der ersten Platte — als Bolzen auf ihr oder als Gewinde in ihr.

    ``size`` nennt statt M6 eine andere Größe, auch ein eigenes Maß.
    """
    History(document).apply(
        "Gewinde an der ersten Platte",
        [
            OperationDraft(
                op="insert_printed_thread",
                inputs=("obj_1",),
                params={
                    **(size or {"size": "M6"}),
                    "length": 8.0,
                    "internal": internal,
                    "z": 10.0,
                },
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


def test_a_thread_names_its_table_size_and_a_stray_one_keeps_its_own_measure() -> None:
    assert thread_values_for(_generated(6.0, 1.0)) == {"size": "M6"}
    # Ein gemessenes Gewinde liegt neben dem Nennmaß — die Spiel- und
    # Messabweichung bleibt innerhalb der Grenze.
    assert thread_values_for(_generated(5.9, 1.0, provenance="native")) == {"size": "M6"}
    assert thread_values_for(_generated(8.1, 1.25)) == {"size": "M8"}
    # Zwischen zwei Größen wird es nicht still M6, es behält sein Maß.
    assert thread_values_for(_generated(6.4, 1.1)) == {
        "size": CUSTOM_SIZE,
        "diameter": 6.4,
        "pitch": 1.1,
    }
    # Ein gedrucktes Gewinde nennt sein Nennmaß neben dem gebauten; das gilt.
    printed = thread_values_for(_generated(66.85, 6.0, nominal=66.6))
    assert printed == {"size": CUSTOM_SIZE, "diameter": 66.6, "pitch": 6.0}


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


def test_a_thread_beyond_the_table_gets_its_own_measure() -> None:
    """Ein M10 aus einer Datei bekommt sein Gegenstück, nicht mehr eine Absage.

    Bis zum 22.09.2026 hieß es „nächste Größe M8" — für einen Bolzen M10 ein
    Loch, durch das er fällt —, danach „die Bibliothek reicht bis M8". Seit
    dem 06.10.2026 baut das Bausteingewinde jedes Maß (Kundenvorschlag
    S-20261006-c66299: ein Innengewinde in einem Rohr mit 60 mm), und die
    Tabelle reicht bis M64: Das M10 ist eine Normgröße, ein Feingewinde M10 ×
    1,25 und alles über M64 ein eigenes Maß. Abgesagt wird nur, was kein
    Bausteingewinde bauen kann.
    """
    assert thread_values_for(_generated(10.0, 1.5)) == {"size": "M10"}
    assert thread_values_for(_generated(10.0, 1.25)) == {
        "size": CUSTOM_SIZE,
        "diameter": 10.0,
        "pitch": 1.25,
    }
    assert thread_values_for(_generated(80.0, 6.0)) == {
        "size": CUSTOM_SIZE,
        "diameter": 80.0,
        "pitch": 6.0,
    }
    for diameter, pitch in ((1500.0, 6.0), (1.0, 0.25), (60.0, 30.0)):
        with pytest.raises(ValidationError) as caught:
            thread_values_for(_generated(diameter, pitch))
        assert caught.value.constraint == "beyond_threads", (diameter, pitch)
        assert caught.value.suggestions, "Regel 17"


@pytest.mark.parametrize(
    ("diameter", "pitch", "accepted"),
    [
        (1000.0, 6.0, True),
        (1000.01, 6.0, False),
        # Ø 1,41 ist über die Erkennungsgrenze noch eine M1.6, darunter nichts mehr.
        (1.41, 0.35, True),
        (1.39, 0.35, False),
        (20.0, 0.25, True),
        (20.0, 0.24, False),
        (66.6, 20.0, True),
        (66.6, 20.01, False),
    ],
)
def test_the_counterpart_takes_its_limits_at_the_edge(
    diameter: float, pitch: float, accepted: bool
) -> None:
    """Die Grenzen an der Kante, nicht weit daneben (Review RM-532, R6)."""
    feature = _generated(diameter, pitch)
    if accepted:
        assert thread_values_for(feature)["size"] in (CUSTOM_SIZE, "M1.6")
        return
    with pytest.raises(ValidationError) as caught:
        thread_values_for(feature)
    assert caught.value.constraint == "beyond_threads"


def test_a_thread_without_a_bolt_core_gets_no_counterpart_step() -> None:
    """Ein erkanntes Innengewinde Ø 3 × 3 hat keinen Bolzen mit tragendem Kern.

    Bis zum 06.10.2026 entstand ein Schritt, der erst in der Auswertung mit
    ``no_core`` anhielt und „Eine feinere Steigung … wählen" an einem Schritt
    sagte, den der Kunde nicht eingegeben hat (Review RM-532, K7). Jetzt sagt
    es die Auswahl, bevor ein Schritt entsteht.
    """
    hole = _generated(3.0, 3.0, internal=True, provenance="native")
    with pytest.raises(ValidationError) as caught:
        thread_counterpart_draft(hole, "obj_2", {})
    assert caught.value.constraint == "beyond_threads"
    assert caught.value.suggestions


def test_a_measured_thread_just_beside_a_table_size_becomes_that_size_and_says_so() -> None:
    """Ø 6,0 × 1,03 mit 0,05 mm Wendelabweichung ist ein M6 × 1 — mit Befund (Review RM-532, R5).

    Die Abweichung liegt innerhalb dessen, was die Messung selbst als
    unsicher nennt; das Gegenstück wird die Normgröße, und der Befund nennt
    die gemessenen Werte. Ohne diese Unsicherheit bleibt das gemessene Maß,
    und der Befund sagt, dass es keine Normgröße ist.
    """
    from app.core.counterpart import thread_size_note

    near = _generated(6.0, 1.03, provenance="native", uncertainty=0.05)
    assert thread_values_for(near) == {"size": "M6"}
    note = thread_size_note(near)
    assert note is not None and note.code == "parts.counterpart_standard_size"
    assert "M6" in str(note.message) and "1,03" in str(note.message)

    exact = _generated(6.0, 1.03, provenance="native", uncertainty=0.0)
    assert thread_values_for(exact) == {"size": CUSTOM_SIZE, "diameter": 6.0, "pitch": 1.03}
    note = thread_size_note(exact)
    assert note is not None and note.code == "parts.counterpart_own_measure"
    assert thread_size_note(_generated(6.0, 1.0)) is None, "eine Normgröße braucht keinen Satz"


@pytest.mark.parametrize("kind", ["mesh", "brep"])
def test_a_thread_in_a_pipe_of_sixty_gets_a_bolt_of_its_own_measure(
    profile: Profile, kind: str
) -> None:
    """Ein Gewinde mit eigenem Maß, innen Ø 66,6 × 6, und sein Bolzen, als Paar.

    So wählte der Klick in die Bohrung von 60 mm aus dem Kundenvorschlag bis
    Tabellenversion 12 (``fasteners.size_for_thread``); seit Version 13 passt
    dort die M64, das eigene Maß bleibt der Weg zwischen und über den
    Normgrößen. Das Gegenstück nimmt dasselbe Maß, beide tragen ihr Spiel, und
    die Passung misst genau das.
    """
    from app.core.knowledge.parts.fasteners import size_for_thread
    from app.core.scene.fits import check, resolve

    _kernel_or_skip(kind)
    assert size_for_thread(60.0) == {"size": "M64", "internal": True}
    chosen = {"size": CUSTOM_SIZE, "diameter": 66.6, "pitch": 0.0}
    document, cache = _two_plates(profile, kind, width=100.0, depth=100.0)
    size = {key: chosen[key] for key in ("size", "diameter", "pitch")}
    thread, _scene = _with_thread(document, cache, profile, internal=True, size=size)
    assert thread.params["nominal"] == pytest.approx(66.6)
    assert thread.params["pitch"] == pytest.approx(6.0)

    applied = apply_thread_counterpart(
        document, thread, "obj_1", "obj_2", {"x": 120.0, "y": 0.0, "z": 10.0}
    )
    step = document.ops[-1]
    assert step.params["size"] == CUSTOM_SIZE and step.params["internal"] is False
    assert step.params["diameter"] == pytest.approx(66.6)
    assert step.params["pitch"] == pytest.approx(6.0)

    result = evaluate(document, profile, cache=cache)
    assert result.stopped_at is None
    applied = attach_thread_fit(document, applied, thread, result.scene)
    assert applied.fit is not None, [str(f.message) for f in applied.findings]
    checked = evaluate(document, profile, cache=cache)
    findings = check(checked.scene, profile, document=document)
    assert not [entry for entry in findings if entry.code.startswith("fit.")], [
        (entry.code, dict(entry.values)) for entry in findings
    ]
    bolt = resolve(checked.scene, applied.fit.b)
    assert bolt is not None
    assert bolt.params["diameter"] == pytest.approx(66.6 - profile.material.clearance)


def test_a_changed_own_measure_takes_its_counterpart_along(profile: Profile) -> None:
    """Die Kopplung des eigenen Maßes (Review RM-532, R6): Durchmesser und Steigung.

    Am ersten Gewinde Ø 66,6 → 70 und, getrennt davon, Steigung → 4: Beide
    erreichen den Partner. Ein Unterschied von 10⁻¹² ist kein neues Maß
    (Regel 6, K3) und koppelt nichts.
    """
    from app.core.counterpart import coupled_step_change

    document, cache = _two_plates(profile, "mesh", width=100.0, depth=100.0)
    size = {"size": CUSTOM_SIZE, "diameter": 66.6, "pitch": 0.0}
    thread, _scene = _with_thread(document, cache, profile, internal=True, size=size)
    applied = apply_thread_counterpart(
        document, thread, "obj_1", "obj_2", {"x": 120.0, "y": 0.0, "z": 10.0}
    )
    result = evaluate(document, profile, cache=cache)
    applied = attach_thread_fit(document, applied, thread, result.scene)
    assert applied.fit is not None
    result = evaluate(document, profile, cache=cache)
    own = next(
        entry
        for entry in document.ops
        if entry.op == "insert_printed_thread" and entry.inputs == ("obj_1",)
    )
    partner = next(
        entry
        for entry in document.ops
        if entry.op == "insert_printed_thread" and entry.inputs == ("obj_2",)
    )

    wider = coupled_step_change(
        document, result.scene, profile, own.id, {**own.params, "diameter": 70.0}
    )
    assert wider is not None and wider.edits[partner.id]["diameter"] == pytest.approx(70.0)
    finer = coupled_step_change(
        document, result.scene, profile, own.id, {**own.params, "pitch": 4.0}
    )
    assert finer is not None and finer.edits[partner.id]["pitch"] == pytest.approx(4.0)
    same = coupled_step_change(
        document, result.scene, profile, own.id, {**own.params, "diameter": 66.6 + 1e-12}
    )
    assert same is None
