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

from pathlib import Path

import numpy as np
import pytest
import trimesh

from app.core.geom.mesh import MeshData, read_mesh
from app.core.geom.mesh_ops import uniform
from app.core.geom.sculpt import apply_strokes, stages, strokes_from_text, strokes_to_text
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


def test_mirroring_happens_about_the_origin() -> None:
    """Die Spiegelebene ist der Objektursprung, nicht der Schwerpunkt.

    Der Schwerpunkt wandert beim Sculpten. Eine Symmetrieebene, die sich unter
    der Hand bewegt, ist die Sorte Überraschung, die Vertrauen kostet.
    """
    shifted = trimesh.creation.icosphere(subdivisions=4, radius=20.0)
    shifted.apply_translation((0.0, 30.0, 0.0))
    base = MeshData.of(shifted)
    stroke = Stroke(
        point=(0.0, 50.0, 0.0), normal=(0.0, 1.0, 0.0), radius=6.0, strength=2.0, symmetry=2
    )

    sculpted = apply_strokes(base, [stroke])

    before = np.asarray(base.raw.vertices, dtype=float)
    after = np.asarray(sculpted.raw.vertices, dtype=float)
    moved = np.linalg.norm(after - before, axis=1) > 1e-9
    assert moved.any(), "der Strich selbst trifft"
    # Gespiegelt am Ursprung läge der Zwilling bei y = -50 und damit weit
    # außerhalb des Körpers, der bei y = 10 endet. Am Schwerpunkt gespiegelt
    # läge er bei y = 10 und träfe.
    assert before[moved][:, 1].min() > 0.0, "der Zwilling trifft den Körper nicht"


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


# --- gegen den Korpus -----------------------------------------------------------


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
