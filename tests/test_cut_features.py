"""Was ein Schnitt wegnimmt, steht danach nicht mehr im Merkmalsbaum (§21.2).

Ein Baustein bringt Merkmale mit, die die Erkennung nicht sieht — die
Einführfase einer Heat-Set-Buchse, die Tasche einer Mutternfalle, ein Gewinde.
Sie reisen ungeprüft durch jeden Schritt (``evaluate._with_features``). Ein
Prüfstück aus dem Gehäuse-Beispiel trug deshalb die Fase einer Buchse, die 40 mm
neben ihm lag, und *Abschneiden* ließ sie an der behaltenen Hälfte stehen. Ein
Prüfstück, das auf das Bett gelegt wurde, nahm dazu seine übrigen Merkmale nicht
mit: Sie blieben an der alten Stelle über dem Bett, und die Bohrung der Buchse
verlor ihren Namen.
"""

from __future__ import annotations

from typing import Any

import pytest

from app.core.scene import History, OperationDraft, ResultCache, evaluate
from app.core.types import Feature, Profile, SceneObject
from app.core.units import EPS_DISPLAY

#: Turm 20 x 20 x 60, je eine Buchse oben und unten; das Fenster des Prüfstücks
#: (Kantenlänge 12 um z = 56) reicht von z = 50 bis 62 und nimmt nur die obere.
TOWER_HEIGHT = 60.0
WINDOW = {"size": 12.0, "x": 0.0, "y": 0.0, "z": 56.0}
WINDOW_BOTTOM = WINDOW["z"] - WINDOW["size"] / 2.0


def _generated(entry: SceneObject) -> dict[str, Feature]:
    return {
        name: feature
        for name, feature in entry.features.items()
        if feature.provenance == "generated" and feature.params.get("centre") is not None
    }


def _centre(feature: Feature) -> tuple[float, float, float]:
    x, y, z = feature.params["centre"]
    return float(x), float(y), float(z)


def _outside(entry: SceneObject) -> list[str]:
    bounds = entry.mesh.bounds
    return [
        f"{name} bei {_centre(feature)}"
        for name, feature in _generated(entry).items()
        if any(
            not low - EPS_DISPLAY <= value <= high + EPS_DISPLAY
            for value, low, high in zip(
                _centre(feature), bounds.minimum, bounds.maximum, strict=True
            )
        )
    ]


def _tower_with_two_bushings(profile: Profile) -> tuple[Any, History, SceneObject]:
    from app.core.bootstrap import load_operations
    from app.core.scene.project import new_project

    load_operations()
    document = new_project("centauri-carbon-2", "petg").document
    history = History(document)
    history.apply(
        "Turm",
        [
            OperationDraft(
                op="create_box", params={"width": 20.0, "depth": 20.0, "height": TOWER_HEIGHT}
            )
        ],
    )
    history.apply(
        "Buchsen",
        [
            OperationDraft(
                op="insert_heatset_m4",
                inputs=("obj_1",),
                params={"size": "M3", "x": 0.0, "y": 0.0, "z": TOWER_HEIGHT},
            ),
            OperationDraft(
                op="insert_heatset_m4",
                inputs=("obj_1",),
                params={"size": "M3", "x": 0.0, "y": 0.0, "z": 0.0, "nz": -1.0},
            ),
        ],
    )
    tower = evaluate(document, profile, cache=ResultCache()).scene.objects["obj_1"]
    return document, history, tower


@pytest.mark.parametrize("on_bed", [True, False], ids=["auf_das_bett", "an_ort_und_stelle"])
def test_a_test_piece_keeps_the_features_of_its_window_and_only_those(
    profile: Profile, on_bed: bool
) -> None:
    """Die obere Buchse liegt im Fenster, die untere nicht.

    Das Stück behält die Merkmale der oberen mit ihren Namen, auf das Bett
    gelegt um dieselben 50 mm abgesenkt wie der Körper; von der unteren steht
    nichts mehr da — auch nicht die Fase, die die Erkennung nie gesehen hat.
    Vorher stand sie bei z = 0,25 im abgesenkten Stück, als gehörte sie zu ihm.
    """
    document, history, tower = _tower_with_two_bushings(profile)
    upper = {
        name: _centre(feature)
        for name, feature in _generated(tower).items()
        if name.startswith("heatset_m4") and _centre(feature)[2] > WINDOW_BOTTOM
    }
    lower = {
        name
        for name, feature in _generated(tower).items()
        if name.startswith("heatset_m4") and _centre(feature)[2] < WINDOW_BOTTOM
    }
    assert {"heatset_m4_bore_1", "heatset_m4_chamfer_1"} <= set(upper), sorted(upper)
    assert len(lower) >= 2, "die untere Buchse bringt Bohrung und Fase mit"

    history.apply(
        "Prüfstück",
        [OperationDraft(op="test_piece", inputs=("obj_1",), params={**WINDOW, "on_bed": on_bed})],
    )
    result = evaluate(document, profile, cache=ResultCache())
    assert result.complete
    piece = result.scene.objects["obj_1"]
    drop = WINDOW_BOTTOM if on_bed else 0.0
    assert piece.mesh.bounds.minimum[2] == pytest.approx(WINDOW_BOTTOM - drop, abs=EPS_DISPLAY)

    assert not _outside(piece), "Merkmale außerhalb des Prüfstücks"
    assert not lower & set(piece.features), "die untere Buchse ist weggeschnitten"
    for name, (x, y, z) in upper.items():
        assert name in piece.features, f"{name} hat seinen Namen verloren"
        assert _centre(piece.features[name]) == pytest.approx((x, y, z - drop), abs=EPS_DISPLAY)

    # Die Flächen, die über das Fenster hinausreichen — Mitte außerhalb oder
    # größer als eine Fensterseite: An Ort und Stelle trägt das Stück der
    # Deckfläche ihren Namen weiter (R4); abgelegt sucht niemand an den alten
    # Dreiecken, und die Schnittfläche unten hieß sonst wie die Bettfläche des
    # Turms, weil beide bei z = 0 liegen. Eine Fläche ganz im Fenster (der Grund
    # der oberen Buchse) behält ihren Namen in beiden Fällen.
    half = WINDOW["size"] / 2.0
    window_centre = (WINDOW["x"], WINDOW["y"], WINDOW["z"])
    beyond = {
        name
        for name, feature in tower.features.items()
        if feature.kind == "face"
        and (
            float(feature.params["area"]) > WINDOW["size"] * WINDOW["size"]
            or any(
                abs(value - middle) > half
                for value, middle in zip(_centre(feature), window_centre, strict=True)
            )
        )
    }
    assert {"face_top"} < beyond and len(beyond) >= 6, sorted(beyond)
    if on_bed:
        assert not beyond & set(piece.features), sorted(beyond & set(piece.features))
    else:
        assert "face_top" in piece.features


def test_cutting_away_takes_the_hidden_features_of_the_other_side_with_it(
    profile: Profile,
) -> None:
    """*Abschneiden* gibt die Merkmale der behaltenen Seite aus — die Fase der
    Buchse jenseits der Ebene trug die Auswertung trotzdem nach."""
    document, history, tower = _tower_with_two_bushings(profile)
    lower = {
        name
        for name, feature in _generated(tower).items()
        if name.startswith("heatset_m4") and _centre(feature)[2] < WINDOW_BOTTOM
    }
    history.apply(
        "Abschneiden",
        [
            OperationDraft(
                op="cut_away",
                inputs=("obj_1",),
                params={"axis": "z", "position": TOWER_HEIGHT / 2.0, "keep": "above"},
            )
        ],
    )
    result = evaluate(document, profile, cache=ResultCache())
    assert result.complete
    rest = result.scene.objects["obj_1"]
    assert rest.mesh.bounds.minimum[2] == pytest.approx(TOWER_HEIGHT / 2.0, abs=EPS_DISPLAY)

    assert not _outside(rest), "Merkmale außerhalb des behaltenen Teils"
    assert not lower & set(rest.features), "die untere Buchse ist abgeschnitten"
    assert {"heatset_m4_bore_1", "heatset_m4_chamfer_1"} <= set(rest.features)


@pytest.mark.parametrize("example_id", ["dose-mit-deckel", "passung-nach-materialwechsel"])
def test_a_fit_test_piece_keeps_the_features_its_fit_names(
    profile: Profile, example_id: str
) -> None:
    """Die Mitte entscheidet nicht, ob ein Merkmal weggeschnitten ist.

    ``lid_cavity`` und ``lid_collar`` sitzen im Schwerpunkt der Öffnung, das
    Fenster einer Passung an der engsten Stelle zwischen Dose und Deckel — also
    an der Wand. Nach ihrer Mitte gefragt fielen beide heraus, und der Bericht
    zeigte ``fit.missing_feature`` als Fehler (Review der ersten Fassung).
    """
    from app.core import examples
    from app.core.bootstrap import load_operations
    from app.core.scene.project import ProjectSources, load

    load_operations()
    project = load(examples.directory() / f"{example_id}.p3d")
    document = project.document
    (fit,) = document.fits
    History(document).apply(
        "Prüfstück",
        [
            OperationDraft(
                op="test_piece",
                inputs=(fit.a.object_id, fit.b.object_id),
                params={"size": 20.0, "spot": "closest"},
            )
        ],
    )
    result = evaluate(document, profile, sources=ProjectSources(project), cache=ResultCache())

    assert result.complete
    for side in (fit.a, fit.b):
        assert side.feature_id in result.scene.objects[side.object_id].features, side
    codes = {finding.code for finding in result.scene.report.findings}
    assert not codes & {"fit.missing_feature", "perceive.generated_lost"}, sorted(codes)


def test_a_thread_cut_below_its_middle_stays(profile: Profile) -> None:
    """Ein Gewinde, das die Ebene unterhalb seiner Mitte schneidet, ist halb da.

    Bolzen M6 × 12 auf einem 10 mm hohen Block, geschnitten bei z = 13 und
    unten behalten: Drei Millimeter Gewinde bleiben, seine Mitte (z = 16) liegt
    darüber. Das Gewinde reist ungeprüft mit; nach seiner Mitte gefragt wäre es
    verschwunden und mit ihm die Unterdrückung der Phantommerkmale der Wendel.
    """
    from app.core.bootstrap import load_operations
    from app.core.scene.project import new_project

    load_operations()
    document = new_project("centauri-carbon-2", "petg").document
    history = History(document)
    history.apply(
        "Block",
        [OperationDraft(op="create_box", params={"width": 20.0, "depth": 20.0, "height": 10.0})],
    )
    history.apply(
        "Bolzen",
        [
            OperationDraft(
                op="insert_printed_thread",
                inputs=("obj_1",),
                params={"size": "M6", "length": 12.0, "x": 0.0, "y": 0.0, "z": 10.0},
            )
        ],
    )
    before = evaluate(document, profile, cache=ResultCache()).scene.objects["obj_1"]
    threads = {name for name, feature in before.features.items() if feature.kind == "thread"}
    assert len(threads) == 1, sorted(before.features)
    (name,) = threads
    assert _centre(before.features[name])[2] > 13.0, "die Mitte liegt über dem Schnitt"

    history.apply(
        "Abschneiden",
        [
            OperationDraft(
                op="cut_away",
                inputs=("obj_1",),
                params={"axis": "z", "position": 13.0, "keep": "below"},
            )
        ],
    )
    result = evaluate(document, profile, cache=ResultCache())

    assert result.complete
    rest = result.scene.objects["obj_1"]
    assert rest.mesh.bounds.maximum[2] == pytest.approx(13.0, abs=EPS_DISPLAY)
    assert name in rest.features, "der untere Teil des Gewindes ist noch da"


def test_the_second_piece_takes_its_features_beside_the_first(profile: Profile) -> None:
    """Zwei Teile einer Passung kommen aus einem Fenster; das zweite rückt beim
    Ablegen neben das erste (``_side_by_side``), und seine Merkmale mit ihm."""
    from app.core.bootstrap import load_operations
    from app.core.scene.project import new_project

    load_operations()
    document = new_project("centauri-carbon-2", "petg").document
    history = History(document)
    size = {"width": 20.0, "depth": 20.0, "height": TOWER_HEIGHT}
    history.apply("Turm", [OperationDraft(op="create_box", params=dict(size))])
    history.apply("Nachbar", [OperationDraft(op="create_box", params={**size, "y": 20.0})])
    history.apply(
        "Buchsen",
        [
            OperationDraft(
                op="insert_heatset_m4",
                inputs=(object_id,),
                params={"size": "M3", "x": 0.0, "y": y, "z": TOWER_HEIGHT},
            )
            for object_id, y in (("obj_1", 7.0), ("obj_2", 13.0))
        ],
    )
    history.apply(
        "Prüfstück",
        [OperationDraft(op="test_piece", inputs=("obj_1", "obj_2"), params={**WINDOW, "y": 10.0})],
    )
    result = evaluate(document, profile, cache=ResultCache())

    assert result.complete
    first, second = (result.scene.objects[name] for name in ("obj_1", "obj_2"))
    assert second.mesh.bounds.minimum[0] > first.mesh.bounds.maximum[0], "nebeneinander"
    for piece in (first, second):
        assert not _outside(piece), f"{piece.id}: Merkmale außerhalb des Stücks"
        bushing = [name for name in piece.features if name.startswith("heatset_m4_bore")]
        assert len(bushing) == 1, sorted(piece.features)
        x, _y, z = _centre(piece.features[bushing[0]])
        bounds = piece.mesh.bounds
        middle = (bounds.minimum[0] + bounds.maximum[0]) / 2.0
        assert x == pytest.approx(middle, abs=EPS_DISPLAY), "die Buchse sitzt mittig im Stück"
        assert bounds.minimum[2] == pytest.approx(0.0, abs=EPS_DISPLAY)
        assert z > bounds.maximum[2] / 2.0, "die Buchse sitzt oben im Stück"


def test_a_feature_declared_beside_its_body_survives_the_next_step(profile: Profile) -> None:
    """Weggeschnitten hat ein Schritt nur, was vor ihm noch im Körper lag.

    Das Gegenstück setzt seine Bohrung ohne Ort in x neben die zweite Platte
    (x = 0 gegen 40 bis 80), und eine Passung hängt daran. *Material ändern*
    danach schneidet nichts; nach der ersten Fassung strich es die Bohrung
    trotzdem als weggeschnitten, und der Bericht zeigte ``fit.missing_feature``
    (zweites Review).
    """
    from app.core.bootstrap import load_operations
    from app.core.counterpart import apply_counterpart, attach_fit, pair_named
    from app.core.scene.project import new_project

    load_operations()
    document = new_project("centauri-carbon-2", "petg").document
    plate = {"width": 40.0, "depth": 30.0, "height": 10.0}
    History(document).apply(
        "Zwei Platten",
        [
            OperationDraft(op="create_box", params=dict(plate)),
            OperationDraft(op="create_box", params={**plate, "x": 60.0}),
        ],
    )
    cache = ResultCache()
    evaluate(document, profile, cache=cache)
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
    applied = attach_fit(document, applied, pair, evaluate(document, profile, cache=cache).scene)
    assert applied.fit is not None
    bore = applied.fit.b.feature_id
    placed = evaluate(document, profile, cache=cache).scene.objects["obj_2"]
    assert _centre(placed.features[bore])[0] < placed.mesh.bounds.minimum[0], "neben der Platte"

    History(document).apply(
        "Material",
        [OperationDraft(op="set_material", inputs=("obj_2",), params={"material": "pla"})],
    )
    result = evaluate(document, profile, cache=cache)

    assert result.complete
    assert bore in result.scene.objects["obj_2"].features
    codes = {finding.code for finding in result.scene.report.findings}
    assert not codes & {"fit.missing_feature", "perceive.generated_lost"}, sorted(codes)


def test_a_slot_reaches_as_far_as_its_length() -> None:
    """Ein Langloch reicht um seine Länge entlang ``direction`` über die Mitte
    hinaus: Steckt ein Arm noch im Körper, ist es nicht weggeschnitten.

    Langloch Ø 4, 20 mm lang in x, Mitte bei x = 0; der Körper beginnt bei
    x = 8. Der rechte Arm reicht bis x = 10 + 2 = 12, also hinein.
    """
    from app.core.scene.evaluate import _cut_away_entirely
    from app.core.types import BoundingBox

    slot = Feature(
        id="slot_1",
        kind="slot",
        provenance="generated",
        params={
            "centre": (0.0, 0.0, 5.0),
            "axis": (0.0, 0.0, 1.0),
            "diameter": 4.0,
            "depth": 10.0,
            "length": 20.0,
            "direction": (1.0, 0.0, 0.0),
        },
    )
    reached = BoundingBox(minimum=(8.0, -10.0, 0.0), maximum=(30.0, 10.0, 10.0))
    beyond = BoundingBox(minimum=(25.0, -10.0, 0.0), maximum=(30.0, 10.0, 10.0))

    assert not _cut_away_entirely(slot, reached), "ein Arm steckt im Körper"
    assert _cut_away_entirely(slot, beyond), "das ganze Langloch liegt davor"


@pytest.mark.parametrize("later", [True, False], ids=["danach_gebraucht", "vorher_benutzt"])
def test_a_cut_away_feature_is_a_warning_only_if_a_later_step_needs_it(
    profile: Profile, later: bool
) -> None:
    """Eine Warnung nach einem gelungenen Schnitt nur, wenn danach noch jemand
    auf das Merkmal zeigt.

    Ein Verweis eines früheren Schritts ist verbraucht: Wer die untere Buchse
    erst aufweitet und dann das Prüfstück aus der oberen schneidet, hat nichts
    falsch gemacht. Wer sie danach aufweiten will, erfährt am Prüfstück, wo sie
    geblieben ist.
    """
    document, history, _tower = _tower_with_two_bushings(profile)
    widen = OperationDraft(
        op="resize_hole",
        inputs=("obj_1",),
        params={"at_feature": "heatset_m4_bore_1_2", "diameter": 4.4},
    )
    piece = OperationDraft(op="test_piece", inputs=("obj_1",), params=dict(WINDOW))
    steps = (piece, widen) if later else (widen, piece)
    for number, step in enumerate(steps):
        history.apply(f"Schritt {number}", [step])
    piece_step = next(operation.id for operation in document.ops if operation.op == "test_piece")

    result = evaluate(document, profile, cache=ResultCache())

    lost = [
        finding
        for finding in result.scene.report.findings
        if finding.code == "perceive.generated_lost"
        and finding.op_id == piece_step
        and finding.values.get("feature") == "heatset_m4_bore_1_2"
    ]
    assert len(lost) == (1 if later else 0), [str(f.message) for f in result.scene.report.findings]
