"""Der Sculpting-Kern (Konzept P16.5, Bauplan §25).

Eine Figur sind mehrere tausend Striche, und ein Verlauf mit viertausend
Einträgen ist kein Verlauf mehr. Deshalb ist ein ganzer Sculpting-Vorgang
**eine** Operation mit einem Sammelparameter — dieselbe Bauart, die die Skizze
seit P13 hat, und seit P16.1 steht sie auch in Regel 2.

Was hier geprüft wird, ist die Auswertung: dass ein Strich trägt, wo er liegt;
dass die Reihenfolge innerhalb einer Etappe egal ist und zwischen Etappen
nicht; dass Symmetrie spiegelt, ohne dass jemand doppelt malt; und dass
zweimal auswerten zweimal dasselbe gibt. Ohne die letzte Zusage wäre der ganze
Op-Stapel darunter wertlos.
"""

from __future__ import annotations

import dataclasses
from pathlib import Path

import numpy as np
import pytest
import trimesh

from app.core.errors import ValidationError
from app.core.geom.mesh import MeshData, read_mesh
from app.core.geom.mesh_ops import uniform
from app.core.geom.sculpt import (
    apply_strokes,
    stages,
    stroke_at,
    strokes_from_text,
    strokes_to_text,
)
from app.core.ingest.loader import normalise
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import OpContext, OpResult, Profile, Scene, SceneObject, Stroke


def ball(subdivisions: int = 4, radius: float = 20.0) -> MeshData:
    return MeshData.of(trimesh.creation.icosphere(subdivisions=subdivisions, radius=radius))


def on_ball(x: float, y: float, z: float, radius: float = 20.0, **kwargs: object) -> Stroke:
    """Ein Strich auf der Kugeloberfläche in Richtung (x, y, z)."""
    direction = np.asarray([x, y, z], dtype=float)
    direction /= np.linalg.norm(direction)
    point = tuple(direction * radius)
    return Stroke(
        point=point,  # type: ignore[arg-type]
        normal=tuple(direction),  # type: ignore[arg-type]
        radius=float(kwargs.pop("brush", 6.0)),  # type: ignore[arg-type]
        strength=float(kwargs.pop("strength", 2.0)),  # type: ignore[arg-type]
        **kwargs,  # type: ignore[arg-type]
    )


# --- was ein Strich tut ---------------------------------------------------------


def test_a_stroke_adds_material_where_it_sits() -> None:
    """Der Nullpunkt: Ein Strich trägt auf, und zwar dort und nicht anderswo."""
    base = ball()

    sculpted = apply_strokes(base, [on_ball(1.0, 0.0, 0.0)])

    assert sculpted.volume > base.volume, "aufgetragen wird nach außen"
    assert sculpted.vertex_count == base.vertex_count, "die Topologie bleibt, wie sie war"
    assert sculpted.raw.bounds[1][0] > base.raw.bounds[1][0], "die Beule sitzt bei +x"
    assert sculpted.raw.bounds[0][0] == pytest.approx(base.raw.bounds[0][0], abs=1e-9), (
        "und nirgends sonst"
    )


def test_carving_takes_material_away() -> None:
    """``carve`` ist ``draw`` mit umgekehrtem Vorzeichen, nicht mehr."""
    base = ball()

    drawn = apply_strokes(base, [on_ball(1.0, 0.0, 0.0, tool="draw")])
    carved = apply_strokes(base, [on_ball(1.0, 0.0, 0.0, tool="carve")])

    assert carved.volume < base.volume < drawn.volume


def test_a_stroke_only_moves_what_it_covers() -> None:
    """Der Pinsel hat einen Radius, und außerhalb passiert nichts.

    Ohne diese Zusage wäre jeder Strich eine globale Verformung — und die
    Vorschau könnte nicht auf die getroffenen Eckpunkte beschränkt bleiben,
    von der das Leistungsbudget aus P16.2 abhängt.
    """
    base = ball()
    brush = 6.0

    sculpted = apply_strokes(base, [on_ball(1.0, 0.0, 0.0, brush=brush)])

    before = np.asarray(base.raw.vertices, dtype=float)
    after = np.asarray(sculpted.raw.vertices, dtype=float)
    moved = np.linalg.norm(after - before, axis=1) > 1e-9
    away = np.linalg.norm(before - np.asarray([20.0, 0.0, 0.0]), axis=1)
    assert moved.any(), "irgendetwas muss sich bewegen"
    assert away[moved].max() <= brush + 1e-9, "nichts außerhalb des Pinsels"


def test_strength_scales_the_result() -> None:
    base = ball()

    soft = apply_strokes(base, [on_ball(1.0, 0.0, 0.0, strength=1.0)])
    hard = apply_strokes(base, [on_ball(1.0, 0.0, 0.0, strength=3.0)])

    assert hard.volume - base.volume > (soft.volume - base.volume) * 2.0


# --- Etappen und Reihenfolge ----------------------------------------------------


def test_strokes_in_one_stage_do_not_care_about_their_order() -> None:
    """Entscheidung C, als Test statt als Behauptung.

    Innerhalb einer Etappe ist die Auswertung eine Summe, und eine Summe ist
    kommutativ. Das ist der Preis für den Faktor sechzig, und er muss
    nachweisbar sein — sonst ist er eine Ausrede für einen Fehler.
    """
    base = ball()
    first = on_ball(1.0, 0.0, 0.0)
    second = on_ball(0.0, 1.0, 0.0)

    forwards = apply_strokes(base, [first, second])
    backwards = apply_strokes(base, [second, first])

    assert np.allclose(
        np.asarray(forwards.raw.vertices), np.asarray(backwards.raw.vertices), atol=1e-12
    )


def test_a_cut_forces_a_stage_and_changes_the_result() -> None:
    """Die Erweiterung von C: Wer die Reihenfolge braucht, kauft sie stückweise.

    Zwei Striche auf dieselbe Stelle. In einer Etappe addieren sich ihre
    Gewichte auf die Ausgangsfläche. Mit erzwungenem Schnitt sitzt der zweite
    auf dem Ergebnis des ersten — und weil er dort eine bereits angehobene
    Fläche vorfindet, kommt etwas anderes heraus.
    """
    base = ball()
    together = [on_ball(1.0, 0.0, 0.0), on_ball(1.0, 0.05, 0.0)]
    apart = [on_ball(1.0, 0.0, 0.0), on_ball(1.0, 0.05, 0.0, cut=True)]

    assert len(stages(together)) == 1
    assert len(stages(apart)) == 2
    assert not np.allclose(
        np.asarray(apply_strokes(base, together).raw.vertices),
        np.asarray(apply_strokes(base, apart).raw.vertices),
    )


def test_an_ordered_tool_opens_a_stage_by_itself() -> None:
    """Glätten liest, was vor ihm liegt — es kann nicht in derselben Summe
    stehen wie das, was es lesen soll.
    """
    strokes = [
        on_ball(1.0, 0.0, 0.0),
        on_ball(0.0, 1.0, 0.0),
        on_ball(1.0, 0.0, 0.0, tool="smooth"),
        on_ball(0.0, 0.0, 1.0),
    ]

    parts = stages(strokes)

    assert len(parts) == 3, "zwei Aufträge, dann Glätten allein, dann der Rest"
    assert [len(part) for part in parts] == [2, 1, 1]


def test_the_first_stroke_never_wastes_a_stage() -> None:
    """Ein Glättungsstrich am Anfang teilt nichts — davor liegt nichts."""
    assert len(stages([on_ball(1.0, 0.0, 0.0, tool="smooth")])) == 1
    assert len(stages([on_ball(1.0, 0.0, 0.0, cut=True)])) == 1


def _pit_depth(base: MeshData, sculpted: MeshData, index: int) -> float:
    """Wie tief der Eckpunkt ``index`` gegenüber der Kugel abgetragen ist."""
    before = float(np.linalg.norm(np.asarray(base.raw.vertices)[index]))
    return before - float(np.linalg.norm(np.asarray(sculpted.raw.vertices)[index]))


def test_a_second_carve_into_the_first_pit_deepens_it(profile: Profile) -> None:
    """RM-438: Ein Zug in die Mulde, die der Zug davor gegraben hat, wirkt.

    Geklickt wird auf die Fläche, die die Vorschau zeigt — also auf den Grund
    der Mulde. In derselben Etappe misst der Zug aber gegen die Fläche vor
    der Etappe, und ist die Stärke größer als der Radius, liegt die weiter als
    einen Radius entfernt: Der Zug griff nichts, die Mulde blieb, und der
    Bericht meldete einen verfehlten Zug. Gemessen an einer Kundensitzung
    (0.5.1) und an diesem Fall: Stärke 4 bei Radius 3 blieb bei 4 mm Tiefe.
    """
    base = ball()
    points = np.asarray(base.raw.vertices, dtype=float)
    index = int(np.argmax(points[:, 0]))
    brush = {"radius": 3.0, "strength": 4.0, "tool": "carve"}

    first = stroke_at(base, tuple(points[index]), **brush)  # type: ignore[arg-type]
    pit = apply_strokes(base, [first])
    assert _pit_depth(base, pit, index) == pytest.approx(4.0, abs=0.01), "Voraussetzung"

    bottom = tuple(float(value) for value in np.asarray(pit.raw.vertices)[index])
    second = stroke_at(base, bottom, before=[first], **brush)  # type: ignore[arg-type]

    assert second.cut, "der Zug erreicht die Fläche vor der Etappe nicht und beginnt eine eigene"
    assert np.allclose(
        second.normal, np.asarray(pit.raw.vertex_normals, dtype=float)[index], atol=1e-9
    ), "die Richtung kommt von der Fläche, auf der der Zug wirkt"
    deeper = apply_strokes(base, [first, second])
    assert _pit_depth(base, deeper, index) == pytest.approx(8.0, abs=0.5)

    entry = SceneObject(id="obj_1", name="Kugel", mesh=base)
    result = run(entry, profile, strokes=strokes_to_text([first, second]))
    assert "sculpt.strokes_missed" not in {f.code for f in result.findings}
    assert np.allclose(
        np.asarray(result.outputs[0].mesh.raw.vertices), np.asarray(deeper.raw.vertices)
    ), "die Operation rechnet aus den Zügen dasselbe wie die Vorschau"


def test_a_stroke_that_reaches_its_stage_stays_in_it() -> None:
    """Eine Etappe kostet einen Durchgang; sie beginnt nur, wo sie nötig ist.

    Ein zweiter Zug abseits des ersten greift die Fläche vor der Etappe — er
    bleibt in ihr, wie bisher (Entscheidung C), und nimmt seine Richtung
    weiter von dieser Fläche.
    """
    base = ball()
    first = stroke_at(base, (20.0, 0.0, 0.0), radius=3.0, strength=4.0, tool="carve")
    beside = stroke_at(
        base, (0.0, 20.0, 0.0), radius=3.0, strength=4.0, tool="carve", before=[first]
    )

    assert not beside.cut
    assert len(stages([first, beside])) == 1
    assert beside == stroke_at(base, (0.0, 20.0, 0.0), radius=3.0, strength=4.0, tool="carve")


def test_the_remembered_stage_never_answers_for_another_session() -> None:
    """Die gemerkte Etappenfläche spart die zweite Auswertung je Klick — und
    darf nach einem Rückgängig oder einer neuen Folge nie das Falsche sagen.

    Gegenprobe je Klick: mit Gedächtnis und frisch gerechnet ist derselbe Zug.
    """
    from app.core.geom import sculpt

    base = ball()
    brush = {"radius": 3.0, "strength": 4.0, "tool": "carve"}
    points = np.asarray(base.raw.vertices, dtype=float)
    spots = [int(np.argmax(points[:, axis])) for axis in range(3)]

    def click(before: list[Stroke], spot: int) -> Stroke:
        """Ein Klick auf die Fläche, die die Vorschau gerade zeigt."""
        shown = np.asarray(apply_strokes(base, before).raw.vertices, dtype=float)[spot]
        where = (float(shown[0]), float(shown[1]), float(shown[2]))
        remembered = stroke_at(base, where, before=before, **brush)  # type: ignore[arg-type]
        kept = list(sculpt._last_stage)
        sculpt._last_stage.clear()
        fresh = stroke_at(base, where, before=before, **brush)  # type: ignore[arg-type]
        sculpt._last_stage[:] = kept
        assert remembered == fresh
        return remembered

    strokes: list[Stroke] = []
    for spot in (spots[0], spots[1], spots[0], spots[2], spots[0]):
        strokes.append(click(strokes, spot))
    assert sum(stroke.cut for stroke in strokes) == 2, "Voraussetzung: zwei Etappen in der Mulde"
    del strokes[1:]  # Rückgängig bis auf den ersten Zug
    for spot in (spots[1], spots[1], spots[0], spots[2], spots[1]):
        strokes.append(click(strokes, spot))
    assert sum(stroke.cut for stroke in strokes) == 2

    # Eine gemerkte Fläche, deren Züge zwar vorn stehen, aber mitten in einer
    # Etappe enden, gilt nicht: Dort summiert sich der nächste Zug mit ihnen.
    first, again = (stroke_at(base, tuple(points[spots[0]]), **brush) for _ in range(2))  # type: ignore[arg-type]
    plane = (0.0, 0.0, 0.0)
    sculpt._last_stage[:] = [(base, (first,), apply_strokes(base, [first], centre=plane))]
    together = sculpt._completed(base, (first, again), plane)
    assert np.allclose(
        np.asarray(together.raw.vertices),
        np.asarray(apply_strokes(base, [first, again], centre=plane).raw.vertices),
    )


# --- die Werkzeuge --------------------------------------------------------------


def test_smoothing_pulls_a_bump_back_down() -> None:
    """Glätten mittelt über die Nachbarschaft — eine Beule wird flacher."""
    base = ball()
    bumped = apply_strokes(base, [on_ball(1.0, 0.0, 0.0, strength=4.0)])
    peak = float(np.asarray(bumped.raw.vertices, dtype=float)[:, 0].max())

    calmed = apply_strokes(
        base,
        [
            on_ball(1.0, 0.0, 0.0, strength=4.0),
            on_ball(1.0, 0.0, 0.0, tool="smooth", brush=8.0, strength=1.0),
        ],
    )

    assert float(np.asarray(calmed.raw.vertices, dtype=float)[:, 0].max()) < peak


def test_flattening_pulls_towards_a_plane() -> None:
    """Flachziehen macht aus einer Wölbung eine Fläche — die Streuung der
    getroffenen Punkte entlang der Normale wird kleiner.
    """
    base = ball()

    flat = apply_strokes(base, [on_ball(1.0, 0.0, 0.0, tool="flatten", brush=8.0, strength=1.0)])

    before = np.asarray(base.raw.vertices, dtype=float)
    after = np.asarray(flat.raw.vertices, dtype=float)
    near = np.linalg.norm(before - np.asarray([20.0, 0.0, 0.0]), axis=1) < 8.0
    assert after[near][:, 0].std() < before[near][:, 0].std()


def test_pinching_draws_towards_the_centre_of_the_stroke() -> None:
    """Kneifen zieht zur Strichmitte — dafür gibt es Kanten und Falten."""
    base = ball()
    centre = np.asarray([20.0, 0.0, 0.0])

    pinched = apply_strokes(base, [on_ball(1.0, 0.0, 0.0, tool="pinch", strength=1.0)])

    before = np.asarray(base.raw.vertices, dtype=float)
    after = np.asarray(pinched.raw.vertices, dtype=float)
    near = np.linalg.norm(before - centre, axis=1) < 6.0
    assert (
        np.linalg.norm(after[near] - centre, axis=1).mean()
        < np.linalg.norm(before[near] - centre, axis=1).mean()
    )


def test_inflating_follows_the_surface_outwards() -> None:
    """Aufblasen trägt entlang der Normale auf, gewichtet nach Krümmung."""
    base = ball()

    puffed = apply_strokes(base, [on_ball(1.0, 0.0, 0.0, tool="inflate", strength=1.0)])

    assert puffed.volume > base.volume


def test_every_tool_leaves_a_closed_body() -> None:
    """Ein Werkzeug, das das Netz aufreißt, ist keines.

    ``warp`` ändert die Topologie nicht, also *kann* hier nichts aufgehen —
    aber genau solche Sätze werden falsch, wenn niemand sie nachprüft.
    """
    base = ball()

    for tool in ("draw", "carve", "smooth", "inflate", "flatten", "pinch"):
        sculpted = apply_strokes(base, [on_ball(1.0, 0.0, 0.0, tool=tool)])
        assert sculpted.is_watertight, f"{tool} hat das Netz geöffnet"
        assert sculpted.triangle_count == base.triangle_count


# --- Symmetrie ------------------------------------------------------------------


def test_a_symmetric_stroke_hits_both_sides() -> None:
    """Symmetrie ist eine Eigenschaft des Strichs, kein zweiter Klick.

    Der Strich merkt sich, an welchen Ebenen er gespiegelt gemeint war — so
    lässt sich eine ganze Sitzung nachträglich symmetrisch machen, ohne dass
    ältere Striche mitwandern.
    """
    base = ball()

    plain = apply_strokes(base, [on_ball(1.0, 0.2, 0.0)])
    mirrored = apply_strokes(base, [on_ball(1.0, 0.2, 0.0, symmetry=2)])

    before = np.asarray(base.raw.vertices, dtype=float)
    after = np.asarray(mirrored.raw.vertices, dtype=float)
    moved = np.linalg.norm(after - before, axis=1) > 1e-9
    assert (before[moved][:, 1] > 0).any() and (before[moved][:, 1] < 0).any()
    assert mirrored.volume > plain.volume


def _sphere_at(centre: tuple[float, float, float]) -> MeshData:
    body = trimesh.creation.icosphere(subdivisions=4, radius=20.0)
    body.apply_translation(centre)
    return MeshData.of(body)


@pytest.mark.parametrize(("axis", "bit"), [(0, 1), (1, 2), (2, 4)])
def test_mirroring_happens_about_the_middle_of_the_body(axis: int, bit: int) -> None:
    """Die Spiegelebene geht durch die Mitte des Körpers (RM-363).

    Bis dahin lag sie im Nullpunkt der Szene: An einer Kugel abseits der
    Mitte bewegte der Zug 117 Ecken, sein Spiegelbild keine, und Symmetrie Z
    wirkte an keinem Körper auf dem Bett. Nicht der Schwerpunkt — der wandert
    beim Formen —, sondern die Mitte des Hüllquaders vor den Zügen.
    """
    centre = [25.0, -40.0, 30.0]
    base = _sphere_at((centre[0], centre[1], centre[2]))
    point = list(centre)
    point[axis] += 20.0
    normal = [0.0, 0.0, 0.0]
    normal[axis] = 1.0
    stroke = Stroke(
        point=(point[0], point[1], point[2]),
        normal=(normal[0], normal[1], normal[2]),
        radius=6.0,
        strength=2.0,
        symmetry=bit,
    )

    sculpted = apply_strokes(base, [stroke])

    before = np.asarray(base.raw.vertices, dtype=float)
    after = np.asarray(sculpted.raw.vertices, dtype=float)
    moved = np.linalg.norm(after - before, axis=1) > 1e-9
    stroke_side = int((before[moved][:, axis] > centre[axis]).sum())
    mirror_side = int((before[moved][:, axis] < centre[axis]).sum())
    assert stroke_side > 0, "der Strich selbst trifft"
    assert mirror_side == stroke_side, "das Spiegelbild trifft genauso viele Ecken"


def test_an_old_session_keeps_mirroring_about_the_origin_of_the_scene(profile: Profile) -> None:
    """Ohne ``mirror_at_body`` spiegelt der Schritt wie vor RM-363 — so behält
    ein altes Projekt nach dem Öffnen seine Form."""
    entry = SceneObject(id="obj_1", name="Kugel", mesh=_sphere_at((0.0, 30.0, 0.0)))
    stroke = Stroke(point=(0.0, 50.0, 0.0), normal=(0.0, 1.0, 0.0), radius=6.0, strength=2.0)
    text = strokes_to_text([stroke])

    old = run(entry, profile, strokes=text, symmetry="y", mirror_at_body=False)
    new = run(entry, profile, strokes=text, symmetry="y")

    before = np.asarray(entry.mesh.raw.vertices, dtype=float)
    for result, hits_the_twin in ((old, False), (new, True)):
        after = np.asarray(result.outputs[0].mesh.raw.vertices, dtype=float)
        moved = np.linalg.norm(after - before, axis=1) > 1e-9
        assert bool((before[moved][:, 1] < 30.0).any()) is hits_the_twin


# --- die Zusage, an der alles hängt ---------------------------------------------


def test_evaluating_twice_gives_the_same_body() -> None:
    """Zweimal auswerten muss identisch sein — sonst ist der Stapel wertlos."""
    base = ball()
    strokes = [
        on_ball(1.0, 0.0, 0.0),
        on_ball(0.0, 1.0, 0.0, tool="smooth"),
        on_ball(0.0, 0.0, 1.0, symmetry=7),
    ]

    once = apply_strokes(base, strokes)
    twice = apply_strokes(base, strokes)

    assert np.array_equal(np.asarray(once.raw.vertices), np.asarray(twice.raw.vertices))


def test_no_strokes_leave_the_body_untouched() -> None:
    """Eine leere Strichliste ist kein Fehler, sondern eine leere Sitzung."""
    base = ball()

    assert np.array_equal(
        np.asarray(apply_strokes(base, []).raw.vertices), np.asarray(base.raw.vertices)
    )


# --- die Operation --------------------------------------------------------------


def run(entry: SceneObject, profile: Profile, **params: object) -> OpResult:
    spec = REGISTRY.get("sculpt_strokes")
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


@pytest.mark.parametrize(
    "text",
    [
        "{nicht json",
        '[{"p": [0, 0, 0], "r": 1, "s": 1}]',
        '[{"p": [0, 0], "n": [0, 0, 1], "r": 1, "s": 1}]',
        '[{"p": [0, 0, 0], "n": [0, 0, 1], "r": "groß", "s": 1}]',
        '[{"p": [0, 0, 0], "n": [0, 0, 1], "r": 1, "s": 1, "t": "hammer"}]',
        '{"p": 1}',
    ],
)
def test_a_spoiled_stroke_text_is_an_input_error_with_a_way_out(
    profile: Profile, text: str
) -> None:
    """Ein von Hand verdorbener Strichtext endete als „unerwarteter Fehler“
    mit *Fehler melden* (RM-367, W4-3). Beim Skelett ist derselbe Fall seit
    jeher ein Eingabefehler — jetzt auch hier."""
    entry = SceneObject(id="obj_1", name="Kugel", mesh=ball())

    with pytest.raises(ValidationError) as caught:
        run(entry, profile, strokes=text)

    assert caught.value.field == "strokes"
    assert caught.value.constraint == "unreadable"
    assert caught.value.suggestions, "Regel 17: ein Ausweg"


def test_strokes_survive_the_round_trip_through_text() -> None:
    """Der Sammelparameter ist reiner Text und muss es unverändert bleiben.

    Eine der fünf Eigenschaften aus Regel 2: Ohne die runde Reise wäre
    „reproduzierbar" auf die laufende Sitzung beschränkt.
    """
    strokes = [
        on_ball(1.0, 0.0, 0.0),
        on_ball(0.0, 1.0, 0.0, tool="smooth", symmetry=5, cut=True),
    ]

    again = strokes_from_text(strokes_to_text(strokes))

    assert len(again) == 2
    assert again[1].tool == "smooth"
    assert again[1].symmetry == 5
    assert again[1].cut is True
    assert again[0].point == pytest.approx(strokes[0].point)


def test_the_operation_can_make_a_finished_session_symmetric(profile: Profile) -> None:
    """Entscheidung F: Symmetrie ist eine Eigenschaft der Operation.

    Der eigentliche Gewinn steht hier: Eine Sitzung, die ohne Symmetrie gemalt
    wurde, lässt sich nachträglich spiegeln — eine Parameteränderung, kein
    zweiter Durchgang mit der Hand.
    """
    entry = SceneObject(id="obj_1", name="Kugel", mesh=ball())
    text = strokes_to_text([on_ball(1.0, 0.3, 0.0)])

    plain = run(entry, profile, strokes=text, symmetry="none")
    mirrored = run(entry, profile, strokes=text, symmetry="y")

    assert mirrored.outputs[0].mesh.volume > plain.outputs[0].mesh.volume
    before = np.asarray(ball().raw.vertices, dtype=float)
    after = np.asarray(mirrored.outputs[0].mesh.raw.vertices, dtype=float)
    moved = np.linalg.norm(after - before, axis=1) > 1e-9
    assert (before[moved][:, 1] > 0).any() and (before[moved][:, 1] < 0).any()


def test_a_brush_finer_than_the_mesh_is_reported(profile: Profile) -> None:
    """Entscheidung E: Fehler als Vorschlag, bevor der Fehler passiert.

    ``warp`` ändert die Topologie nicht — wer eine feine Falte in ein grobes
    Netz malt, bekommt keine Falte, sondern eine verzogene Facette. Das ist
    nichts, was man am Ergebnis erkennt, also wird es gesagt.
    """
    coarse = MeshData.of(trimesh.creation.icosphere(subdivisions=1, radius=20.0))
    entry = SceneObject(id="obj_1", name="Grobe Kugel", mesh=coarse)

    result = run(entry, profile, strokes=strokes_to_text([on_ball(1.0, 0.0, 0.0, brush=1.0)]))

    codes = {finding.code for finding in result.findings}
    assert "sculpt.too_coarse" in codes


def test_a_fine_enough_mesh_stays_quiet(profile: Profile) -> None:
    """Die Gegenprobe — sonst warnt jede Sitzung und keine Warnung zählt."""
    entry = SceneObject(id="obj_1", name="Kugel", mesh=ball(subdivisions=5))

    result = run(entry, profile, strokes=strokes_to_text([on_ball(1.0, 0.0, 0.0, brush=6.0)]))

    codes = {finding.code for finding in result.findings}
    assert "sculpt.too_coarse" not in codes
    assert "sculpt.applied" in codes


def test_the_finding_counts_strokes_and_stages(profile: Profile) -> None:
    """Die Etappenzahl gehört sichtbar gemacht — sie ist der Preis aus C."""
    entry = SceneObject(id="obj_1", name="Kugel", mesh=ball())
    strokes = [
        on_ball(1.0, 0.0, 0.0),
        on_ball(0.0, 1.0, 0.0, tool="smooth"),
        on_ball(0.0, 0.0, 1.0),
    ]

    result = run(entry, profile, strokes=strokes_to_text(strokes))

    applied = next(f for f in result.findings if f.code == "sculpt.applied")
    assert applied.values["strokes"] == 3
    assert applied.values["stages"] == 3


def test_an_empty_session_says_so(profile: Profile) -> None:
    """„Nichts zu tun" ist ein Ergebnis und gehört gesagt."""
    entry = SceneObject(id="obj_1", name="Kugel", mesh=ball())

    result = run(entry, profile, strokes="")

    assert {f.code for f in result.findings} == {"sculpt.empty"}


def test_a_stroke_that_misses_the_body_is_reported(profile: Profile) -> None:
    """Der Fall aus dem eigenen Vorbehalt der Operation — und er war stumm.

    Ein Zug sitzt an einer Stelle im Raum. Wer die Form darunter später
    verschiebt, lässt ihn in der Luft stehen: im Verlauf ein Schritt, am Teil
    keine Änderung, und im Bericht stand bis hierher sogar, die Züge seien
    übertragen worden. Gemessen am Weg-4-Schaustück, dessen drei Fingerrillen
    18 mm über dem Körper lagen und exakt nichts abtrugen — die Operation
    warnt davor im Register und prüfte es nicht.
    """
    entry = SceneObject(id="obj_1", name="Kugel", mesh=ball())
    strokes = [on_ball(1.0, 0.0, 0.0), on_ball(0.0, 0.0, 1.0, radius=60.0)]

    result = run(entry, profile, strokes=strokes_to_text(strokes))

    missed = next(f for f in result.findings if f.code == "sculpt.strokes_missed")
    assert missed.severity == "warning"
    assert missed.values["missed"] == 1
    assert missed.values["strokes"] == 2


def test_a_session_without_any_effect_does_not_claim_success(profile: Profile) -> None:
    """Liegt jeder Zug daneben, ist „übertragen" die falsche Auskunft.

    Das ist der Unterschied zwischen Schweigen und Falschaussage: Ein Bericht,
    der nichts sagt, lässt den Nutzer suchen; einer, der den Erfolg meldet,
    schickt ihn in die falsche Richtung.
    """
    entry = SceneObject(id="obj_1", name="Kugel", mesh=ball())

    result = run(entry, profile, strokes=strokes_to_text([on_ball(0.0, 0.0, 1.0, radius=60.0)]))

    codes = {f.code for f in result.findings}
    assert "sculpt.no_effect" in codes
    assert "sculpt.applied" not in codes, "was nicht geschah, wird nicht gemeldet"


def test_a_stroke_shallower_than_a_layer_is_applied_but_marked_subtle(profile: Profile) -> None:
    """Getroffen und gewirkt — nur unter einer Schichthöhe.

    Der Daumenmulden-Zug des Schaustücks traf 321 von 5770 Eckpunkten und trug
    dabei 0,41 mm ab, bei eingestellter Stärke 5,0. Bis zum 05.09.2026 hieß
    das „hat den Körper nicht verändert" — falsch für die Geometrie, und eine
    Z-Schichthöhe ist kein Maß für eine seitliche Kontur (Gesamtreview, R39).
    Verändert ist verändert; die Druckwirkung steht getrennt daneben, und die
    Grenze dafür kommt weiter aus dem Profil (Regel 7).
    """
    entry = SceneObject(id="obj_1", name="Kugel", mesh=ball())
    below = profile.printer.layer_height / 4.0
    strokes = [on_ball(1.0, 0.0, 0.0, strength=below)]

    result = run(entry, profile, strokes=strokes_to_text(strokes))

    codes = {f.code for f in result.findings}
    assert "sculpt.applied" in codes, "der Körper ist verändert, und das steht da"
    assert "sculpt.no_effect" not in codes
    subtle = next(f for f in result.findings if f.code == "sculpt.subtle")
    assert 0.0 < subtle.values["moved_mm"] < subtle.values["layer_mm"]
    assert "sculpt.strokes_missed" not in codes, "getroffen hat er"


def test_a_stroke_that_lands_stays_quiet(profile: Profile) -> None:
    """Die Gegenprobe — sonst warnt jede Sitzung, und keine Warnung zählt."""
    entry = SceneObject(id="obj_1", name="Kugel", mesh=ball())

    result = run(entry, profile, strokes=strokes_to_text([on_ball(1.0, 0.0, 0.0)]))

    codes = {f.code for f in result.findings}
    assert "sculpt.no_effect" not in codes
    assert "sculpt.strokes_missed" not in codes
    assert "sculpt.applied" in codes


# --- gegen den Korpus -----------------------------------------------------------


def plate() -> MeshData:
    """Eine 4-mm-Platte, fein genug vernetzt für einen 6-mm-Pinsel."""
    box = trimesh.creation.box(extents=(40.0, 40.0, 4.0))
    vertices, faces = trimesh.remesh.subdivide_to_size(box.vertices, box.faces, max_edge=0.8)
    return MeshData.of(trimesh.Trimesh(vertices, faces, process=True))


def carve_into_plate(strength: float) -> Stroke:
    return Stroke(
        point=(0.0, 0.0, 2.0), normal=(0.0, 0.0, 1.0), radius=6.0, strength=strength, tool="carve"
    )


def test_carving_through_the_plate_is_reported(profile: Profile) -> None:
    """Ein Abtragzug drückte die Oberseite durch die Unterseite: 48 sich
    durchdringende Dreieckspaare, und im Bericht stand nur „übertragen“
    (RM-364). Die Prüfung „aufgerissen“ kann das nie sehen, denn Formen
    ändert die Topologie nicht."""
    entry = SceneObject(id="obj_1", name="Platte", mesh=plate())

    result = run(entry, profile, strokes=strokes_to_text([carve_into_plate(6.0)]))

    pierced = next(f for f in result.findings if f.code == "sculpt.pierced")
    assert pierced.severity == "warning"
    assert pierced.values["triangles"] > 0
    assert pierced.location is not None, "Stelle zeigen fliegt zur Durchdringung"
    assert abs(pierced.location[0]) < 8.0 and abs(pierced.location[1]) < 8.0


def test_carving_a_wall_below_the_minimum_is_reported(profile: Profile) -> None:
    """Ein flacher Zug ließ 0,44 mm Restwand bei verlangten 0,84 mm, ohne
    Befund; der Export lief ohne Warnung (RM-364)."""
    entry = SceneObject(id="obj_1", name="Platte", mesh=plate())

    result = run(entry, profile, strokes=strokes_to_text([carve_into_plate(4.0)]))

    codes = {f.code for f in result.findings}
    assert "sculpt.pierced" not in codes, "durchgestochen ist hier nichts"
    thin = next(f for f in result.findings if f.code == "sculpt.thin_wall")
    assert thin.severity == "warning"
    assert 0.0 < thin.values["thickness_mm"] < thin.values["minimum_mm"]
    assert thin.values["minimum_mm"] == pytest.approx(profile.minimum_wall_thickness, abs=0.01)
    assert thin.location is not None


def test_a_shallow_carve_in_a_thick_wall_stays_quiet(profile: Profile) -> None:
    """Die Gegenprobe: 1 mm aus 4 mm lässt genug Wand."""
    entry = SceneObject(id="obj_1", name="Platte", mesh=plate())

    result = run(entry, profile, strokes=strokes_to_text([carve_into_plate(1.0)]))

    codes = {f.code for f in result.findings}
    assert "sculpt.applied" in codes
    assert "sculpt.pierced" not in codes
    assert "sculpt.thin_wall" not in codes


def figure() -> MeshData:
    """Die saubere Figur aus dem Referenzkorpus."""
    path = Path(__file__).parent / "data" / "meshes" / "clean_figure.stl"
    return normalise(read_mesh(path.read_bytes(), ".stl"), "mm").mesh


def test_the_corpus_figure_is_ready_to_be_sculpted() -> None:
    """Wozu die Datei da ist: eine Figur, an der nichts zu reparieren ist.

    ``generated_figure.stl`` daneben trägt absichtlich Generatorfehler und
    wird erst nach der Reparaturkette ein Volumen. Ein Geometrietest, der
    nebenbei eine Reparatur mitprüft, misst zwei Dinge und sagt über keines
    etwas Genaues.
    """
    body = figure()

    assert body.is_watertight
    assert body.component_count == 1
    assert body.volume > 0.0
    assert body.bounds.minimum[2] == pytest.approx(0.0), "sie steht auf der Platte"


def test_the_whole_chain_runs_on_the_corpus_figure() -> None:
    """Die Kette aus Entscheidung E, Ende zu Ende: vernetzen, dann formen.

    Die Figur kommt mit 2,8 mm mittlerer Kantenlänge aus dem Korpus. Ein
    Pinsel von 4 mm findet darauf zu wenige Eckpunkte; nach dem gleichmäßigen
    Vernetzen findet er genug, und das ist der ganze Grund, warum
    ``remesh_uniform`` vor dem Formen steht und nicht daneben.
    """
    body = figure()
    coarse = float(np.median(np.asarray(body.raw.edges_unique_length, dtype=float)))

    fine = uniform(body, 1.0, 0.0)
    top = float(body.raw.bounds[1][2])
    stroke = Stroke(point=(0.0, 0.0, top), normal=(0.0, 0.0, 1.0), radius=4.0, strength=1.5)
    sculpted = apply_strokes(fine, [stroke])

    assert coarse > 2.0, "die Vorlage ist grob, sonst prüft dieser Test nichts"
    assert float(np.median(np.asarray(fine.raw.edges_unique_length, dtype=float))) < coarse / 2.0
    assert sculpted.volume > fine.volume, "der Pinsel trägt auf"
    assert sculpted.is_watertight
    assert sculpted.triangle_count == fine.triangle_count, "die Topologie bleibt"


def test_sculpting_the_coarse_figure_warns_instead_of_failing_quietly(
    profile: Profile,
) -> None:
    """Und der Weg ohne die Vorstufe endet nicht im Nichts, sondern im Befund.

    Ein Strich auf einem zu groben Netz erzeugt keine Falte, sondern eine
    verzogene Facette — nichts, was man am Ergebnis erkennt, also wird es
    gesagt (Entscheidung E).
    """
    entry = SceneObject(id="obj_1", name="Figur", mesh=figure())
    top = float(figure().raw.bounds[1][2])
    stroke = Stroke(point=(0.0, 0.0, top), normal=(0.0, 0.0, 1.0), radius=2.0, strength=1.5)

    result = run(entry, profile, strokes=strokes_to_text([stroke]))

    assert "sculpt.too_coarse" in {finding.code for finding in result.findings}


# --- Einbacken (Entscheidung D) -------------------------------------------------


class BakedSources:
    """Der Quellenspeicher des Projekts, wie ihn die Auswertung reicht."""

    def __init__(self, payload: bytes) -> None:
        self._payload = payload

    def read(self, source_id: str) -> bytes:
        return self._payload

    def describe(self, source_id: str) -> object:  # pragma: no cover - hier ungefragt
        raise NotImplementedError


def run_with_sources(entry: SceneObject, profile: Profile, payload: bytes, **params: object):
    spec = REGISTRY.get("sculpt_strokes")
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
            sources=BakedSources(payload),  # type: ignore[arg-type]
        )
    )


def test_a_big_session_offers_to_be_baked(profile: Profile) -> None:
    """Entscheidung D: angeboten, nie automatisch.

    Zwanzig Etappen heißen zwanzig Durchgänge über alle Eckpunkte, je
    Auswertung. Das ist der Punkt, an dem das Festschreiben mehr wert ist als
    die Änderbarkeit — aber die Entscheidung trifft der Nutzer.
    """
    entry = SceneObject(id="obj_1", name="Kugel", mesh=ball())
    many = [on_ball(1.0, 0.0, 0.0, tool="smooth") for _ in range(20)]

    result = run(entry, profile, strokes=strokes_to_text(many))

    assert "sculpt.consider_baking" in {finding.code for finding in result.findings}


def test_a_small_session_is_not_pestered(profile: Profile) -> None:
    """Die Gegenprobe — ein Angebot, das immer dasteht, ist eine Belästigung."""
    entry = SceneObject(id="obj_1", name="Kugel", mesh=ball())

    result = run(entry, profile, strokes=strokes_to_text([on_ball(1.0, 0.0, 0.0)]))

    assert "sculpt.consider_baking" not in {finding.code for finding in result.findings}


def test_baked_mesh_keeps_exact_vertices_and_material_slots(profile: Profile) -> None:
    body = trimesh.creation.box(extents=(10, 10, 10))
    body.apply_translation((0.123456789, 0, 0))
    mesh = MeshData.of(body, slots=tuple([1] * 6 + [2] * 6))
    entry = SceneObject(id="obj_1", name="Farben", mesh=mesh)
    result = run_with_sources(entry, profile, mesh.to_bytes(), strokes="", baked="src_9")
    restored = result.outputs[0].mesh
    assert restored.slot_indices == mesh.slot_indices
    assert np.array_equal(restored.raw.vertices, body.vertices)
    assert np.array_equal(restored.raw.faces, body.faces)


def test_a_baked_session_comes_from_its_source(profile: Profile) -> None:
    """Ist der Stand festgeschrieben, wird nichts mehr gerechnet.

    Das ist der Sinn der Sache. Reproduzierbar bleibt es trotzdem: Die Quelle
    reist im Container mit wie jede andere, und was aus ihr kommt, hängt an
    keinem Rechner und an keiner Sitzung.
    """
    entry = SceneObject(id="obj_1", name="Kugel", mesh=ball())
    frozen = MeshData.of(trimesh.creation.box(extents=(10.0, 10.0, 10.0)))

    result = run_with_sources(
        entry,
        profile,
        frozen.to_stl(),
        strokes=strokes_to_text([on_ball(1.0, 0.0, 0.0)]),
        baked="src_9",
    )

    after = result.outputs[0].mesh
    assert after.volume == pytest.approx(1000.0, rel=0.01), "das Ergebnis kommt aus der Quelle"
    assert "sculpt.baked" in {finding.code for finding in result.findings}


def test_the_strokes_stay_as_evidence_after_baking(profile: Profile) -> None:
    """Die alte Liste bleibt in der eingebackenen Operation erhalten.

    Wer ein halbes Jahr später nachsieht, was dort gemacht wurde, findet es —
    und der Befund sagt dazu, dass sich daran nichts mehr ändern lässt.
    """
    entry = SceneObject(id="obj_1", name="Kugel", mesh=ball())
    text = strokes_to_text([on_ball(1.0, 0.0, 0.0), on_ball(0.0, 1.0, 0.0)])
    frozen = MeshData.of(trimesh.creation.box(extents=(10.0, 10.0, 10.0)))

    result = run_with_sources(entry, profile, frozen.to_stl(), strokes=text, baked="src_9")

    baked = next(f for f in result.findings if f.code == "sculpt.baked")
    assert baked.values["strokes"] == 2, "die Züge sind gezählt, nicht verworfen"


def test_baking_without_sources_says_so(profile: Profile) -> None:
    """Ein eingebackener Stand ohne Quellen ist kein leeres Ergebnis, sondern
    eine Meldung."""
    entry = SceneObject(id="obj_1", name="Kugel", mesh=ball())

    with pytest.raises(ValidationError) as raised:
        run(entry, profile, strokes="", baked="src_9")

    assert raised.value.suggestions


def test_baked_array_headers_cannot_request_more_than_the_stored_data(monkeypatch):
    import io
    import zipfile

    import numpy as np

    from app.core.geom.mesh import MeshData

    array = io.BytesIO()
    np.lib.format.write_array_header_1_0(
        array, {"descr": "<f8", "fortran_order": False, "shape": (1000000000, 3)}
    )
    payload = io.BytesIO()
    with zipfile.ZipFile(payload, "w") as archive:
        archive.writestr("vertices.npy", array.getvalue())

    def forbidden_load(*args, **kwargs):
        raise AssertionError("unvalidated array reached numpy.load")

    monkeypatch.setattr(np, "load", forbidden_load)
    from app.core.errors import ValidationError

    with pytest.raises(ValidationError) as caught:
        MeshData.from_bytes(payload.getvalue(), maximum_bytes=1024)
    assert caught.value.constraint == "invalid_mesh_array_size"
    assert caught.value.suggestions, "auch ein beschädigter Stand nennt einen Weg (Regel 17)"


def test_a_long_session_can_be_stopped_while_it_is_applied(profile: Profile) -> None:
    """Abbrechen wirkt während der Striche, nicht erst danach (§15.6).

    Eine Sitzung mit tausenden Zügen ist ein Durchgang je Zug durch den
    Suchbaum; bis zum 22.09.2026 fragte ``apply_strokes`` dabei nie nach dem
    Abbruch, und der Knopf wirkte erst, wenn die Sitzung fertig war.
    """
    from app.core.errors import OperationCancelled

    class StopsAfter:
        """Ein Abbruch, der nach der ersten Frage ausgelöst ist."""

        def __init__(self) -> None:
            self.asked = 0

        @property
        def is_cancelled(self) -> bool:
            return self.asked > 1

        def raise_if_cancelled(self) -> None:
            self.asked += 1
            if self.asked > 1:
                raise OperationCancelled

    entry = SceneObject(id="obj_1", name="Kugel", mesh=ball())
    strokes = [on_ball(float(np.cos(a)), float(np.sin(a)), 0.3) for a in np.linspace(0, 6, 60)]
    spec = REGISTRY.get("sculpt_strokes")
    token = StopsAfter()
    with pytest.raises(OperationCancelled):
        spec.fn(
            OpContext(
                scene=Scene(objects={entry.id: entry}),
                inputs=[entry],
                params=spec.params(strokes=strokes_to_text(strokes)),
                profile=profile,
                quality="fine",
                seed=None,
                progress=lambda fraction, text: None,
                ask=lambda question, choices: choices[0],
                cancelled=token,  # type: ignore[arg-type]
            )
        )
    assert token.asked == 2, "gefragt wird zwischen den Zügen, und nach dem Abbruch nicht weiter"


def hollow_ball() -> MeshData:
    """Eine Kugel Ø 40 mit 3 mm Wand — ein Hohlkörper."""
    outer = trimesh.creation.icosphere(subdivisions=4, radius=20.0)
    inner = trimesh.creation.icosphere(subdivisions=4, radius=17.0)
    inner.invert()
    return MeshData.of(trimesh.util.concatenate([outer, inner]))


@pytest.mark.parametrize("tool", ["draw", "carve", "smooth", "pinch"])
def test_a_brush_on_a_thin_plate_leaves_the_far_side_alone(tool: str) -> None:
    """Der Pinsel griff jeden Eckpunkt in seiner Kugel, auch die Unterseite
    einer dünnen Wand: *Abtragen* auf einer 4-mm-Platte drückte sie 3,7 mm
    unter das Bett (RM-376). Jetzt bewegt er nur, was ihm zugewandt ist."""
    base = plate()
    stroke = Stroke(
        point=(0.0, 0.0, 2.0), normal=(0.0, 0.0, 1.0), radius=6.0, strength=3.0, tool=tool
    )

    shaped = apply_strokes(base, [stroke])

    before = np.asarray(base.raw.vertices, dtype=float)
    after = np.asarray(shaped.raw.vertices, dtype=float)
    bottom = before[:, 2] < -2.0 + 1e-6
    assert np.allclose(after[bottom], before[bottom]), "die Unterseite bleibt, wo sie war"


def test_a_brush_inside_a_hollow_body_leaves_the_inner_wall_alone() -> None:
    """Dasselbe an einem Hohlkörper: Die Innenwand liegt hinter der Außenhaut."""
    base = hollow_ball()
    stroke = Stroke(
        point=(20.0, 0.0, 0.0), normal=(1.0, 0.0, 0.0), radius=6.0, strength=2.0, tool="carve"
    )

    shaped = apply_strokes(base, [stroke])

    before = np.asarray(base.raw.vertices, dtype=float)
    after = np.asarray(shaped.raw.vertices, dtype=float)
    inner = np.linalg.norm(before, axis=1) < 18.0
    assert np.allclose(after[inner], before[inner])
    assert not np.allclose(after[~inner], before[~inner]), "die Außenhaut wird geformt"


def test_a_brush_on_a_figure_still_shapes_what_faces_it() -> None:
    """Die Gegenprobe an der Korpusfigur: Ein Zug wirkt wie bisher."""
    base = figure()
    centre = base.raw.bounds.mean(axis=0)
    top = float(base.raw.bounds[1][2])
    stroke = Stroke(
        point=(float(centre[0]), float(centre[1]), top),
        normal=(0.0, 0.0, 1.0),
        radius=4.0,
        strength=1.0,
        tool="draw",
    )

    shaped = apply_strokes(base, [stroke])

    assert shaped.raw.bounds[1][2] > top + 0.5, "der Zug trägt oben auf"


@pytest.mark.parametrize(("axis", "bit"), [(0, 1), (1, 2), (2, 4)])
@pytest.mark.parametrize("body", ["ball", "plate", "hollow"])
def test_a_stroke_on_the_mirror_plane_acts_once(axis: int, bit: int, body: str) -> None:
    """Ein Zug genau auf der Symmetrieebene wurde mit seinem Spiegelbild zweimal
    am selben Ort angewandt (RM-378). Er wirkt jetzt so weit wie derselbe Zug
    ohne Symmetrie; weit weg von der Ebene wirken beide wie bisher."""
    base = {"ball": ball(), "plate": plate(), "hollow": hollow_ball()}[body]
    low, high = base.raw.bounds
    middle = (low + high) / 2.0
    point = middle.copy()
    normal = np.zeros(3)
    # Der Zug liegt auf der Oberfläche quer zur Spiegelachse.
    across = (axis + 1) % 3 if body != "plate" else 2
    if across == axis:
        across = (axis + 2) % 3
    point[across] = high[across]
    normal[across] = 1.0
    stroke = Stroke(
        point=tuple(float(value) for value in point),  # type: ignore[arg-type]
        normal=tuple(float(value) for value in normal),  # type: ignore[arg-type]
        radius=5.0,
        strength=1.0,
    )

    single = apply_strokes(base, [stroke])
    mirrored = apply_strokes(base, [dataclasses.replace(stroke, symmetry=bit)])

    before = np.asarray(base.raw.vertices, dtype=float)
    assert np.allclose(
        np.asarray(mirrored.raw.vertices, dtype=float) - before,
        np.asarray(single.raw.vertices, dtype=float) - before,
        atol=1e-9,
    ), "auf der Ebene wirkt der Zug einmal"
