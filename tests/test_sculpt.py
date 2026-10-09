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
import itertools
from pathlib import Path
from typing import Any

import numpy as np
import pytest
import trimesh

from app.core.errors import ValidationError
from app.core.geom.intersections import crossing_face_pairs
from app.core.geom.mesh import MeshData, as_mesh_data, read_mesh
from app.core.geom.mesh_ops import uniform
from app.core.geom.sculpt import (
    SculptPreview,
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


def test_a_stroke_that_reaches_nothing_starts_no_stage() -> None:
    """RM-442: Ein Zug, der auch nach seiner Etappe nichts greift, ist verfehlt.

    Eine eigene Etappe hülfe ihm nicht — sie kostete einen Durchgang und
    änderte nichts —, und sie machte aus einem einmaligen *Neu ansetzen*
    davor eines, das auch für diesen Zug gilt. Er bleibt in seiner Etappe,
    und der Bericht nennt ihn verfehlt.
    """
    base = ball()
    first = stroke_at(base, (20.0, 0.0, 0.0), radius=3.0, strength=4.0, tool="carve", cut=True)
    aside = stroke_at(
        base, (0.0, 40.0, 0.0), radius=3.0, strength=4.0, tool="carve", before=[first]
    )

    assert not aside.cut
    assert len(stages([first, aside])) == 1


def lopsided_prism() -> MeshData:
    """Ein geschlossenes Prisma, dessen Hüllmitte im Ursprung liegt: links die
    Wand ``x = −10`` mit einem Mittelpunkt ``M = (−10, 0, 0)``, rechts die
    schräge Wand ``x = 9 + 0,1·y`` nur aus ihren vier Ecken
    (``remote-18c76-sculpt.md``, RM-454)."""
    left = [(-10.0, y, z) for y, z in ((-10, -10), (10, -10), (10, 10), (-10, 10))]
    right = [(9.0 + 0.1 * y, y, z) for _x, y, z in left]
    vertices = np.asarray([*left, *right, (-10.0, 0.0, 0.0)], dtype=float)
    middle = 8
    faces = [(middle, (k + 1) % 4, k) for k in range(4)]
    faces += [(4, 5, 6), (4, 6, 7)]
    for k in range(4):
        following = (k + 1) % 4
        faces += [(k, following, following + 4), (k, following + 4, k + 4)]
    body = trimesh.Trimesh(vertices, np.asarray(faces), process=False)
    body.fix_normals()
    assert body.is_watertight and body.volume > 0.0
    return MeshData.of(body)


@pytest.mark.parametrize("where", ["at_the_stroke", "over_the_session"])
def test_a_mirrored_stroke_that_reaches_only_the_sculpted_face_gets_its_stage(
    profile: Profile, where: str
) -> None:
    """RM-454: Die Etappenentscheidung fragte nur den Klickpunkt.

    Ein Zug bei ``M`` gräbt einen Millimeter ein; der Klick auf ``P = (9, 0,
    0)`` greift selbst nichts, sein Spiegelbild ``−P`` aber genau den
    verschobenen Punkt ``M′`` — nur auf der Fläche nach der ersten Etappe.
    Blieb der Zug in ihr, wirkte er nirgends. Die Spiegelung trägt der Zug
    selbst oder die ganze Sitzung (die Leiste *Symmetrie*, im Fenster).
    """
    prism = lopsided_prism()
    brush = {"radius": 0.4, "strength": 1.0, "tool": "carve"}
    if where == "at_the_stroke":
        first = stroke_at(prism, (-10.0, 0.0, 0.0), symmetry=1, **brush)  # type: ignore[arg-type]
        second = stroke_at(prism, (9.0, 0.0, 0.0), symmetry=1, before=[first], **brush)  # type: ignore[arg-type]
        session = "none"
    else:
        first = stroke_at(prism, (-10.0, 0.0, 0.0), **brush)  # type: ignore[arg-type]
        shown = [dataclasses.replace(first, symmetry=1)]
        second = stroke_at(prism, (9.0, 0.0, 0.0), before=shown, mirrored=1, **brush)  # type: ignore[arg-type]
        session = "x"
    assert second.cut, "der Zug wirkt erst auf der Fläche nach der ersten Etappe"

    entry = SceneObject(id="obj_1", name="Prisma", mesh=prism)
    result = run(entry, profile, strokes=strokes_to_text([first, second]), symmetry=session)
    once = run(entry, profile, strokes=strokes_to_text([first]), symmetry=session)
    middle = np.asarray(result.outputs[0].mesh.raw.vertices, dtype=float)[8]
    after_first = np.asarray(once.outputs[0].mesh.raw.vertices, dtype=float)[8]
    assert np.allclose(after_first, (-9.0, 0.0, 0.0), atol=1e-9), "Voraussetzung: M′ bei x = −9"
    assert float(np.linalg.norm(middle - after_first)) > 0.5, "das Spiegelbild gräbt bei M′ weiter"
    assert "sculpt.strokes_missed" not in {f.code for f in result.findings}


def test_the_preview_follows_the_session_stroke_by_stroke_and_bit_for_bit() -> None:
    """RM-366: Die Vorschau rechnete nach jedem Zug die ganze Sitzung neu.

    :class:`SculptPreview` setzt nur den neuen Zug auf, beginnt je neuer
    Etappe einen Durchgang und rechnet bei Rückgängig oder anderer Spiegelung
    ab der letzten unberührten Etappe — und zeigt dabei bitgleich, was die
    Operation aus denselben Zügen rechnet (Regel 2).
    """
    from app.core.geom import sculpt

    base = ball()
    tools = ("draw", "smooth", "draw", "carve", "pinch", "inflate", "draw", "flatten")
    strokes = [
        on_ball(float(np.cos(step)), float(np.sin(step)), 0.4, tool=tools[step % 8], strength=0.8)
        for step in range(16)
    ]
    built = 0
    real = sculpt._Stage.__init__

    def counted(self: object, *args: object, **kwargs: object) -> None:
        nonlocal built
        built += 1
        real(self, *args, **kwargs)  # type: ignore[arg-type]

    sculpt._Stage.__init__ = counted  # type: ignore[method-assign]
    try:
        preview = sculpt.SculptPreview(base)
        for count in range(1, len(strokes) + 1):
            shown = preview.show(strokes[:count])
            expected = apply_strokes(base, strokes[:count])
            assert np.array_equal(
                np.asarray(shown.raw.vertices), np.asarray(expected.raw.vertices)
            ), count
        built_by_preview = built - sum(
            len(stages(strokes[:count])) for count in range(1, len(strokes) + 1)
        )
    finally:
        sculpt._Stage.__init__ = real  # type: ignore[method-assign]
    assert built_by_preview <= len(stages(strokes)) + 1, "je neue Etappe ein Durchgang"

    for changed in (
        strokes[:-1],
        strokes[:5],
        [dataclasses.replace(stroke, symmetry=1) for stroke in strokes],
        strokes,
    ):
        shown = preview.show(changed)
        expected = apply_strokes(base, changed)
        assert np.array_equal(np.asarray(shown.raw.vertices), np.asarray(expected.raw.vertices))


def test_a_stroke_from_the_preview_is_the_stroke_without_it() -> None:
    """``stroke_at`` mit der Vorschau nimmt Fläche, Suchbaum und Normalen aus
    ihrer Etappe — und entscheidet Etappe und Richtung genau wie ohne sie
    (RM-366, RM-438, RM-454)."""
    from app.core.geom import sculpt

    base = ball()
    points = np.asarray(base.raw.vertices, dtype=float)
    spots = [int(np.argmax(points[:, axis])) for axis in range(3)]
    preview = sculpt.SculptPreview(base)
    strokes: list[Stroke] = []
    # Je Stelle zweimal hintereinander — der zweite Zug trifft die Mulde des
    # ersten —, dazwischen ein Glätten, und abwechselnd mit der Spiegelung der
    # Sitzung.
    clicks = [(0, "carve"), (0, "carve"), (1, "carve"), (1, "carve"), (2, "smooth")]
    clicks += [(2, "carve"), (2, "carve"), (0, "carve")]
    for number, (spot_number, tool) in enumerate(clicks):
        spot = spots[spot_number]
        shown = np.asarray(apply_strokes(base, strokes).raw.vertices, dtype=float)[spot]
        where = (float(shown[0]), float(shown[1]), float(shown[2]))
        brush = {
            "radius": 3.0,
            "strength": 4.0,
            "tool": tool,
            "mirrored": 1 if number % 2 else 0,
        }
        sculpt._last_stage.clear()
        alone = stroke_at(base, where, before=strokes, **brush)  # type: ignore[arg-type]
        preview.show(strokes)
        guided = stroke_at(base, where, before=strokes, preview=preview, **brush)  # type: ignore[arg-type]
        assert guided == alone, number
        strokes.append(guided)
    assert any(stroke.cut for stroke in strokes), "Voraussetzung: auch Züge in die Mulde"


def test_a_click_that_begins_a_stage_builds_normals_and_tree_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RM-366: Ein Klick, der eine Etappe beginnt, rechnete Normalen und
    Suchbaum über das ganze Netz zweimal — für den Zug (``stroke_at``) und
    noch einmal für die Etappe der Vorschau. An einer Kugel mit 145 742 Ecken
    war das die Hälfte des Klicks. Die Etappe übernimmt beides von der
    gezeigten Fläche, auf der sie beginnt."""
    from app.core.geom import sculpt

    base = ball()
    points = np.asarray(base.raw.vertices, dtype=float)
    made = {"normals": 0, "tree": 0}
    real_normals = trimesh.geometry.weighted_vertex_normals
    real_tree = sculpt.cKDTree

    def counted_normals(*args: object, **kwargs: object) -> object:
        made["normals"] += 1
        return real_normals(*args, **kwargs)  # type: ignore[arg-type]

    def counted_tree(*args: object, **kwargs: object) -> object:
        made["tree"] += 1
        return real_tree(*args, **kwargs)

    monkeypatch.setattr(trimesh.geometry, "weighted_vertex_normals", counted_normals)
    monkeypatch.setattr(sculpt, "cKDTree", counted_tree)
    preview = sculpt.SculptPreview(base)
    strokes: list[Stroke] = []
    for number in range(8):
        spot = points[int(np.argmax(points @ np.array([np.cos(number), np.sin(number), 0.3])))]
        made.update(normals=0, tree=0)
        stroke = stroke_at(
            base,
            (float(spot[0]), float(spot[1]), float(spot[2])),
            radius=4.0,
            strength=0.5,
            tool="smooth" if number % 2 else "draw",
            before=strokes,
            preview=preview,
        )
        strokes.append(stroke)
        preview.show(strokes)
        assert len(stages(strokes)) == number + 1, "Voraussetzung: jeder Klick eine Etappe"
        # Ab dem zweiten Klick ist die gezeigte Fläche neu: genau einmal beides.
        expected = {"normals": 1, "tree": 1}
        if number == 0:
            assert made["normals"] <= 1 and made["tree"] == 1, made
        else:
            assert made == expected, (number, made)


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
        # Die Zwillinge aus der Nachprüfung (RM-367): keine endliche Zahl, ein
        # Radius ohne Fläche oder ohne Grenze, ein Punkt mit vier Koordinaten.
        '[{"p": [0, 0, 0], "n": [0, 0, 1], "r": 1, "s": NaN}]',
        '[{"p": [NaN, 0, 0], "n": [0, 0, 1], "r": 1, "s": 1}]',
        '[{"p": [0, 0, 0], "n": [0, 0, 1], "r": 0, "s": 1}]',
        '[{"p": [0, 0, 0], "n": [0, 0, 1], "r": -2, "s": 1}]',
        '[{"p": [0, 0, 0], "n": [0, 0, 1], "r": Infinity, "s": 1}]',
        '[{"p": [0, 0, 0, 7], "n": [0, 0, 1], "r": 1, "s": 1}]',
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


def test_a_piercing_stroke_can_be_taken_back(profile: Profile) -> None:
    """Der Befund nannte als Weg nur *Stelle zeigen*; „zurücknehmen“ stand im
    Satz und nirgends als Knopf (RM-419). Jetzt nennt er den Zug, der die
    Wand durchstochen hat — gezählt wie im Verlauf, ab eins —, und bietet
    *Zug zurücknehmen* an."""
    entry = SceneObject(id="obj_1", name="Platte", mesh=plate())
    harmless = Stroke(
        point=(15.0, 15.0, 2.0), normal=(0.0, 0.0, 1.0), radius=3.0, strength=0.5, tool="draw"
    )
    strokes = [harmless, carve_into_plate(6.0), harmless]

    result = run(entry, profile, strokes=strokes_to_text(strokes))

    pierced = next(f for f in result.findings if f.code == "sculpt.pierced")
    assert pierced.values["stroke"] == 2
    assert [action.id for action in pierced.suggestions] == ["take_back_stroke", "show_location"]


def test_the_sculpt_step_reports_its_progress(profile: Profile) -> None:
    """Züge übertragen und die Wand prüfen kosten an großen Netzen Sekunden;
    der Schritt meldet seinen Anteil bis eins (RM-419, §2.8)."""
    spec = REGISTRY.get("sculpt_strokes")
    entry = SceneObject(id="obj_1", name="Platte", mesh=plate())
    shares: list[float] = []
    spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(strokes=strokes_to_text([carve_into_plate(6.0)])),
            profile=profile,
            quality="fine",
            seed=None,
            progress=lambda fraction, text: shares.append(fraction),
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )
    assert shares[0] == 0.0 and shares[-1] == 1.0
    assert all(later >= earlier for earlier, later in itertools.pairwise(shares))


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


def _crossing_pairs(mesh: MeshData) -> int:
    found = crossing_face_pairs(
        np.asarray(mesh.raw.vertices, dtype=float), np.asarray(mesh.raw.faces, dtype=np.int64)
    )
    return len(found.first)


@pytest.mark.parametrize("tool", ["draw", "carve", "pinch", "inflate", "flatten"])
def test_a_brush_on_a_thin_plate_leaves_the_far_side_alone(tool: str) -> None:
    """Der Pinsel griff jeden Eckpunkt in seiner Kugel, auch die Unterseite
    einer dünnen Wand: *Abtragen* auf einer 4-mm-Platte zog sie mit (RM-376).
    Jetzt bewegt er nur, was ihm zugewandt ist.

    *Glätten* steht nicht in der Liste: An dieser regelmäßig unterteilten
    Platte bewegt es auch ohne Filter nichts, der Fall könnte nie rot werden.
    *Aufblasen* und *Flachziehen* zogen die Unterseite 0,5 und 1,8 mm mit
    (RM-430)."""
    base = plate()
    stroke = Stroke(
        point=(0.0, 0.0, 2.0), normal=(0.0, 0.0, 1.0), radius=6.0, strength=3.0, tool=tool
    )

    shaped = apply_strokes(base, [stroke])

    before = np.asarray(base.raw.vertices, dtype=float)
    after = np.asarray(shaped.raw.vertices, dtype=float)
    bottom = before[:, 2] < -2.0 + 1e-6
    assert np.allclose(after[bottom], before[bottom]), "die Unterseite bleibt, wo sie war"
    if tool != "flatten":
        # Flachziehen hat an der ebenen Oberseite nichts zu tun.
        top = (before[:, 2] > 2.0 - 1e-6) & (np.linalg.norm(before[:, :2], axis=1) < 3.0)
        moved = np.linalg.norm(after[top] - before[top], axis=1)
        assert moved.max() > 0.5, "vorn wirkt der Pinsel"
    if tool != "pinch":
        # Stärke 3 an 4 mm Wand: Die Oberseite erreicht die Unterseite nicht.
        # Kneifen faltet die Oberseite in sich (das meldet ``sculpt.pierced``).
        assert _crossing_pairs(shaped) == _crossing_pairs(base) == 0, "keine Durchdringung"


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


@pytest.mark.parametrize("tool", ["draw", "carve", "inflate", "flatten"])
def test_a_brush_on_the_figures_arm_leaves_its_back_alone(tool: str) -> None:
    """RM-430: Am Arm der Korpusfigur reicht ein Pinsel R 6 durch den Arm
    (7 mm) bis zur Rückseite. Vorn wirkt er, hinten bleibt alles stehen —
    vorher zog er dort bis 0,3 mm mit."""
    base = uniform(figure(), 1.0, 0.0)
    before = np.asarray(base.raw.vertices, dtype=float)
    normals = np.asarray(base.raw.vertex_normals, dtype=float)
    click = before[int(np.argmin(np.linalg.norm(before - (20.0, -9.0, 59.0), axis=1)))]
    stroke = stroke_at(
        base, tuple(float(value) for value in click), radius=6.0, strength=1.5, tool=tool
    )
    direction = np.asarray(stroke.normal, dtype=float)
    inside = np.linalg.norm(before - np.asarray(stroke.point, dtype=float), axis=1) <= 6.0
    back = inside & (normals @ direction <= 0.0)
    front = inside & (normals @ direction > 0.0)
    assert back.sum() > 10, "der Pinsel reicht bis zur Rückseite des Arms"

    after = np.asarray(apply_strokes(base, [stroke]).raw.vertices, dtype=float)

    moved = np.linalg.norm(after - before, axis=1)
    assert moved[back].max() == 0.0, "die Rückseite bleibt"
    assert moved[front].max() > 0.5, "vorn wirkt der Pinsel"


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


SCULPT_TOOLS = ("draw", "carve", "pinch", "smooth", "inflate", "flatten")


@pytest.mark.parametrize("tool", SCULPT_TOOLS)
def test_every_brush_acts_once_on_the_mirror_plane(tool: str) -> None:
    """RM-428: „einmal auf der Ebene“ galt geprüft nur für *Auftragen*.

    Jeder Pinsel, an der Kugel quer zur Spiegelachse X angesetzt: gespiegelt
    wirkt er wie ohne Symmetrie.
    """
    base = ball()
    stroke = on_ball(0.0, 0.0, 1.0, tool=tool, strength=1.0, brush=6.0)

    single = apply_strokes(base, [stroke])
    mirrored = apply_strokes(base, [dataclasses.replace(stroke, symmetry=1)])

    before = np.asarray(base.raw.vertices, dtype=float)
    assert np.abs(np.asarray(single.raw.vertices) - before).max() > 1e-3, "der Pinsel wirkt"
    assert np.allclose(
        np.asarray(mirrored.raw.vertices, dtype=float),
        np.asarray(single.raw.vertices, dtype=float),
        atol=1e-9,
    )


@pytest.mark.parametrize("tool", SCULPT_TOOLS)
def test_every_brush_far_from_the_mirror_plane_acts_on_both_sides(
    profile: Profile, tool: str
) -> None:
    """Weit weg von der Ebene wirken Zug und Spiegelbild wie zwei Züge — so
    wie vor RM-378, bitgleich mit einem alten Formschritt (``mirror_once``
    aus)."""
    entry = SceneObject(id="obj_1", name="Kugel", mesh=ball())
    text = strokes_to_text([on_ball(1.0, 0.1, 0.2, tool=tool, strength=1.0, brush=6.0)])

    new = run(entry, profile, strokes=text, symmetry="x")
    old = run(entry, profile, strokes=text, symmetry="x", mirror_once=False)

    before = np.asarray(entry.mesh.raw.vertices, dtype=float)
    after = np.asarray(new.outputs[0].mesh.raw.vertices, dtype=float)
    moved = np.linalg.norm(after - before, axis=1) > 1e-9
    assert (before[moved][:, 0] > 0).any() and (before[moved][:, 0] < 0).any(), "beide Seiten"
    assert np.array_equal(after, np.asarray(old.outputs[0].mesh.raw.vertices, dtype=float))


def mirror_plate() -> MeshData:
    """Eine 4-mm-Platte, gleichmäßig unterteilt: Ihre Ecken liegen spiegelgleich
    zur Mitte, im Raster von 0,375 mm. ``subdivide_to_size`` teilt nach Länge
    und legt die Ecken dabei nicht spiegelgleich (bis 0,125 mm daneben)."""
    box = trimesh.creation.box(extents=(24.0, 24.0, 4.0))
    vertices, faces = np.asarray(box.vertices), np.asarray(box.faces)
    for _ in range(6):
        vertices, faces = trimesh.remesh.subdivide(vertices, faces)
    return MeshData.of(trimesh.Trimesh(vertices, faces, process=True))


def _mirror_partner(points: np.ndarray, axis: int, middle: float) -> np.ndarray:
    """Je Eckpunkt die Nummer seines Spiegelbilds an der Ebene durch ``middle``."""
    from scipy.spatial import cKDTree

    mirrored = points.copy()
    mirrored[:, axis] = 2.0 * middle - mirrored[:, axis]
    away, partner = cKDTree(points).query(mirrored)
    assert float(np.max(away)) < 1e-9, "Voraussetzung: der Körper ist spiegelgleich vernetzt"
    return np.asarray(partner, dtype=np.int64)


@pytest.mark.parametrize("tool", SCULPT_TOOLS)
@pytest.mark.parametrize("body", ["ball", "plate"])
def test_a_stroke_beside_the_mirror_plane_stays_mirror_equal(body: str, tool: str) -> None:
    """RM-428: Ein Zug 1 mm neben der Ebene schob die Ecken auf der Ebene zur
    Seite des Originalzugs — Kneifen 0,426 mm, Auftragen 0,043 mm —, weil bei
    gleich starken Kopien immer die erste gewann. Das Ergebnis eines
    gespiegelten Zugs ist spiegelgleich, und die Ecken auf der Ebene bleiben
    darauf."""
    base = ball() if body == "ball" else mirror_plate()
    points = np.asarray(base.raw.vertices, dtype=float)
    top = float(points[:, 2].max())
    if body == "ball":
        # Auf der Kugel 1 mm neben dem Nordpol, die Richtung der Fläche dort.
        direction = np.asarray([1.0, 0.0, 20.0])
        direction /= np.linalg.norm(direction)
        point, normal = direction * 20.0, direction
    else:
        point, normal = np.asarray([1.0, 0.0, top]), np.asarray([0.0, 0.0, 1.0])
    stroke = Stroke(
        point=tuple(float(value) for value in point),  # type: ignore[arg-type]
        normal=tuple(float(value) for value in normal),  # type: ignore[arg-type]
        radius=5.0,
        strength=1.0,
        tool=tool,  # type: ignore[arg-type]
        symmetry=1,
    )

    shaped = apply_strokes(base, [stroke])

    shift = np.asarray(shaped.raw.vertices, dtype=float) - points
    partner = _mirror_partner(points, 0, 0.0)
    mirrored = shift[partner] * np.asarray([-1.0, 1.0, 1.0])
    assert np.abs(shift).max() > 1e-3 or tool in ("smooth", "inflate", "flatten"), "er wirkt"
    assert np.allclose(shift, mirrored, atol=1e-9), "das Ergebnis ist spiegelgleich"
    on_plane = points[:, 0] == 0.0
    assert on_plane.sum() > 4, "Voraussetzung: Ecken auf der Ebene"
    assert np.abs(shift[on_plane, 0]).max() < 1e-9, "Ecken auf der Ebene bleiben darauf"


#: Der Zug aus Befund S01 (Review ``48106c57a``, RM-425): an der Kugel R 20 mit
#: 1 280 Dreiecken, so wie ``stroke_at`` ihn an der Eckpunktnormale setzte —
#: schräg zur Spiegelebene X, 5,3 mm daneben, mit einem Pinsel, der über sie
#: hinausreicht.
S01_STROKE = Stroke(
    point=(5.32809402269135, 0.0, 19.277225269352453),
    normal=(0.2679932314359806, -2.2264954261106484e-18, 0.9634207948266951),
    radius=16.0,
    strength=1.0,
    tool="draw",
    symmetry=1,
)


def _mirror_error(base: MeshData, shaped: MeshData, axis: int, middle: float) -> float:
    """Wie weit das Ergebnis vom eigenen Spiegelbild abweicht, je Eckpunkt."""
    points = np.asarray(base.raw.vertices, dtype=float)
    shift = np.asarray(shaped.raw.vertices, dtype=float) - points
    flip = np.ones(3)
    flip[axis] = -1.0
    return float(np.abs(shift - shift[_mirror_partner(points, axis, middle)] * flip).max())


def test_the_slanted_s01_stroke_stays_mirror_equal(profile: Profile) -> None:
    """S01: Der schräge Zug ließ 0,341 mm Spiegelabweichung und schob die Ebene
    um 0,171 mm zur Seite, weil bei gleich starken Kopien die erste gewann
    (``_strongest_copy``, entfallen mit RM-428). Geprüft am Kern, über die
    registrierte Operation wie im Befund und an der Vorschau der Sitzung —
    auch nach Zurücknehmen und Wiederholen des Zugs."""
    base = MeshData.of(trimesh.creation.icosphere(subdivisions=3, radius=20.0))
    assert base.triangle_count == 1280, "Voraussetzung: der Körper aus dem Befund"
    entry = SceneObject(id="obj_1", name="Kugel", mesh=base)
    session = SculptPreview(base)
    first = session.show([S01_STROKE])
    assert session.show([]) is base, "zurückgenommen"
    again = session.show([S01_STROKE])
    operation = apply_strokes(base, [S01_STROKE])
    assert np.array_equal(np.asarray(first.raw.vertices), np.asarray(again.raw.vertices))
    assert np.array_equal(np.asarray(again.raw.vertices), np.asarray(operation.raw.vertices))

    for shaped in (
        operation,
        run(entry, profile, strokes=strokes_to_text([S01_STROKE]), symmetry="x").outputs[0].mesh,
        again,
    ):
        points = np.asarray(base.raw.vertices, dtype=float)
        moved = np.asarray(as_mesh_data(shaped).raw.vertices, dtype=float) - points
        assert np.abs(moved).max() > 0.5, "der Zug wirkt"
        assert _mirror_error(base, as_mesh_data(shaped), 0, 0.0) < 1e-9, "spiegelgleich"
        on_plane = np.abs(points[:, 0]) < 1e-12
        assert on_plane.sum() > 4, "Voraussetzung: Ecken auf der Ebene"
        assert np.abs(moved[on_plane, 0]).max() < 1e-9, "die Ebene bleibt, wo sie ist"


@pytest.mark.parametrize("tool", ["draw", "pinch"])
@pytest.mark.parametrize("shifted", [False, True], ids=["middle", "shifted"])
@pytest.mark.parametrize("body", ["ball", "plate", "hollow"])
@pytest.mark.parametrize(("axis", "bit"), [(0, 1), (1, 2), (2, 4)])
def test_a_slanted_stroke_beside_any_mirror_plane_stays_mirror_equal(
    axis: int, bit: int, body: str, shifted: bool, tool: str
) -> None:
    """RM-425: S01 an drei Körpern, an jeder Achse und mit einer Spiegelmitte
    abseits des Nullpunkts — der Zug liegt neben der Ebene, seine Richtung
    steht schräg zu ihr, der Pinsel reicht über sie hinaus."""
    base = {"ball": ball(), "plate": mirror_plate(), "hollow": hollow_ball()}[body]
    if shifted:
        moved_body = base.raw.copy()
        moved_body.apply_translation((7.0, -3.0, 5.0))
        base = MeshData.of(moved_body)
    points = np.asarray(base.raw.vertices, dtype=float)
    middle = (points.min(axis=0) + points.max(axis=0)) / 2.0
    # Quer zur Spiegelachse eine Seite, auf der der Zug sitzt: an der Platte die
    # Oberseite, wo sie quer liegt, sonst die Seitenfläche bei +x oder +y.
    across = 2 if body != "plate" or axis != 2 else 0
    if across == axis:
        across = (axis + 1) % 3
    normal = np.zeros(3)
    normal[across] = 0.9634207948266951
    normal[axis] = 0.2679932314359806
    if body == "plate":
        point = middle.copy()
        point[across] = points[:, across].max()
        point[axis] += 1.0
    else:
        point = middle + normal * 20.0
    stroke = Stroke(
        point=tuple(float(value) for value in point),  # type: ignore[arg-type]
        normal=tuple(float(value) for value in normal),  # type: ignore[arg-type]
        radius=8.0,
        strength=1.0,
        tool=tool,  # type: ignore[arg-type]
        symmetry=bit,
    )

    shaped = apply_strokes(base, [stroke])

    shift = np.asarray(shaped.raw.vertices, dtype=float) - points
    assert np.abs(shift).max() > 1e-3, "der Zug wirkt"
    assert _mirror_error(base, shaped, axis, float(middle[axis])) < 1e-9, "spiegelgleich"
    on_plane = np.abs(points[:, axis] - middle[axis]) < 1e-12
    assert on_plane.sum() > 4, "Voraussetzung: Ecken auf der Ebene"
    assert np.abs(shift[on_plane, axis]).max() < 1e-9, "Ecken auf der Ebene bleiben darauf"


def test_an_old_stroke_near_the_mirror_plane_keeps_acting_twice(profile: Profile) -> None:
    """Ein gespeicherter Schritt von vor RM-378 (``mirror_once`` aus) wirkt an
    der Ebene weiter doppelt — der S01-Zug hebt die Kugel um 1,226 mm, bitgleich
    mit der Probe am Stand ``48106c57a``, und bleibt spiegelgleich. Ein neuer
    Schritt hebt sie um die Höhe eines Zugs (gemessen 1,049 mm)."""
    base = MeshData.of(trimesh.creation.icosphere(subdivisions=3, radius=20.0))
    entry = SceneObject(id="obj_1", name="Kugel", mesh=base)
    text = strokes_to_text([S01_STROKE])

    old = as_mesh_data(
        run(entry, profile, strokes=text, symmetry="x", mirror_once=False).outputs[0].mesh
    )
    new = as_mesh_data(run(entry, profile, strokes=text, symmetry="x").outputs[0].mesh)

    before = np.asarray(base.raw.vertices, dtype=float)
    lift_old = float(np.linalg.norm(np.asarray(old.raw.vertices) - before, axis=1).max())
    lift_new = float(np.linalg.norm(np.asarray(new.raw.vertices) - before, axis=1).max())
    assert lift_old == pytest.approx(1.2264798851468122, abs=1e-9)
    assert 0.9 <= lift_new <= 1.1 < lift_old
    assert _mirror_error(base, old, 0, 0.0) < 1e-9


def _top_row(base: MeshData, shaped: MeshData) -> tuple[np.ndarray, np.ndarray]:
    """Die Höhe der Plattenoberseite entlang ``y = 0``, nach ``x`` geordnet."""
    before = np.asarray(base.raw.vertices, dtype=float)
    after = np.asarray(shaped.raw.vertices, dtype=float)
    top = float(before[:, 2].max())
    row = np.flatnonzero((before[:, 1] == 0.0) & (before[:, 2] == top))
    order = row[np.argsort(before[row, 0])]
    return before[order, 0], after[order, 2] - before[order, 2]


def test_a_stroke_beside_the_mirror_plane_leaves_no_notch() -> None:
    """RM-428: Ein Zug 1 mm neben der Ebene ließ eine Kerbe von 0,148 mm mit
    Knick (Steigung ±0,263) zwischen Zug und Spiegelbild — die stärkere Kopie
    je Ecke ergibt einen Knick, wo beide gleich stark sind. Vor RM-378 war der
    Übergang glatt, aber fast doppelt so hoch (1,70).

    Jetzt verschmelzen Zug und Spiegelbild nahe der Ebene zu einer glatten
    Kuppe von der Höhe eines Zugs: bei 1 mm eingipflig, bei 2 mm ohne Knick.
    """
    base = mirror_plate()
    top = float(np.asarray(base.raw.vertices)[:, 2].max())
    for away in (1.0, 2.0):
        stroke = Stroke(
            point=(away, 0.0, top),
            normal=(0.0, 0.0, 1.0),
            radius=5.0,
            strength=1.0,
            symmetry=1,
        )
        x, height = _top_row(base, apply_strokes(base, [stroke]))
        near = np.abs(x) <= 3.0
        assert near.sum() >= 9, "Voraussetzung: eine Zeile durch den Zug"
        assert 0.9 <= float(height.max()) <= 1.2, f"{away} mm: so hoch wie ein Zug, nicht doppelt"
        middle = int(np.flatnonzero(x == 0.0)[0])
        step = float(x[middle + 1] - x[middle])
        slope = abs(float(height[middle + 1] - height[middle])) / step
        assert slope < 0.1, f"{away} mm: Knick an der Ebene, Steigung {slope:.3f}"
        if away == 1.0:
            left = np.diff(height[(x >= -3.0) & (x <= 0.0)])
            right = np.diff(height[(x >= 0.0) & (x <= 3.0)])
            assert (left >= -1e-12).all() and (right <= 1e-12).all(), "eingipflig, keine Kerbe"


def test_gesture_metadata_roundtrips_without_changing_old_strokes():
    """Gestenkennungen gruppieren Proben, Altdateien bleiben bitgleich auswertbar."""
    from dataclasses import replace

    from app.core.geom.sculpt import stroke_count

    stroke = on_ball(1.0, 0.0, 0.0)
    old = strokes_to_text([stroke, stroke])
    assert '"g"' not in old
    assert stroke_count(strokes_from_text(old)) == 2
    grouped = [replace(stroke, gesture=1), replace(stroke, gesture=1), replace(stroke, gesture=2)]
    again = strokes_from_text(strokes_to_text(grouped))
    assert again == grouped
    assert stroke_count(again) == 2


@pytest.mark.parametrize("value", [-1, 1.5, True, "1", None])
def test_unreadable_gesture_metadata_has_a_recovery_action(value):
    """Fremde Gruppendaten werden nicht still abgeschnitten oder geraten."""
    import json

    from app.core.errors import ValidationError

    data = json.loads(strokes_to_text([on_ball(1.0, 0.0, 0.0)]))
    data[0]["g"] = value
    with pytest.raises(ValidationError) as caught:
        strokes_from_text(json.dumps(data))
    assert caught.value.suggestions


# --- Pinselfassung 2 (RM-560) ----------------------------------------------------
#
# Jeder Test rechnet Fassung 1 daneben: Sie ist die Gegenprobe, denn sie rechnet
# wie bis Format 48 und zeigt den Befund, den Fassung 2 behebt (Messung im
# Bericht des Pakets Z2).


def _passes(base: MeshData, brush: int, strength: float, passes: int = 10) -> list[Stroke]:
    """Zehnmal dieselbe Linie über die Oberseite, jede Linie eine Geste."""
    strokes: list[Stroke] = []
    preview = SculptPreview(base)
    for number in range(passes):
        for x in np.arange(-12.0, 12.01, 2.0):
            strokes.append(
                stroke_at(
                    base,
                    (float(x), 0.0, 10.0),
                    radius=4.0,
                    strength=strength,
                    before=strokes,
                    preview=preview,
                    gesture=number + 1,
                    brush=brush,
                )
            )
            preview.show(strokes)
    return strokes


def _largest_fold(before: MeshData, after: MeshData) -> float:
    """Der größte Winkel zwischen Nachbardreiecken, die sich bewegt haben, in Grad."""
    moved = np.linalg.norm(after.raw.vertices - before.raw.vertices, axis=1) > 1e-9
    touched = moved[np.asarray(after.raw.faces)].any(axis=1)
    pairs = after.raw.face_adjacency
    keep = touched[pairs[:, 0]] | touched[pairs[:, 1]]
    return float(np.degrees(after.raw.face_adjacency_angles[keep].max()))


def _changed(stroke: Stroke, **changes: object) -> Stroke:
    return dataclasses.replace(stroke, **changes)  # type: ignore[arg-type]


def _second(x: float, y: float, z: float, **kwargs: object) -> Stroke:
    """:func:`on_ball` in Pinselfassung 2 — dort heißt ``brush`` der Radius."""
    return _changed(on_ball(x, y, z, **kwargs), brush=2)


@pytest.fixture(scope="module")
def slab() -> MeshData:
    """Ein Quader 40 × 40 × 20 mm, auf 1 mm angeglichen — Oberseite bei z = 10."""
    return uniform(MeshData.of(trimesh.creation.box(extents=(40, 40, 20))), 1.0, 0.0)


def test_each_gesture_is_its_own_stage_in_brush_two() -> None:
    """H4: Eine neue Geste setzt auf das Ergebnis der vorigen; Fassung 1 kennt nur Werkzeuge."""
    from app.core.geom.sculpt import starts_stage

    first = _second(1.0, 0.0, 0.0, gesture=1)
    same = _second(1.0, 0.1, 0.0, gesture=1)
    other = _second(1.0, 0.2, 0.0, gesture=2)
    assert [len(part) for part in stages([first, same, other])] == [2, 1]
    assert starts_stage(first, _second(1.0, 0.0, 0.0, gesture=0)), "ohne Kennung allein"
    old = [_changed(stroke, brush=1) for stroke in (first, same, other)]
    assert [len(part) for part in stages(old)] == [3], "Fassung 1 rechnet wie bisher"
    smooth = _second(1.0, 0.0, 0.0, tool="smooth", gesture=3)
    smoother = _second(1.0, 0.1, 0.0, tool="smooth", gesture=3)
    assert [len(part) for part in stages([smooth, smoother])] == [2], (
        "H7: eine Glättgeste ist ein Durchgang, nicht einer je Probe"
    )
    assert [len(part) for part in stages([_changed(s, brush=1) for s in (smooth, smoother)])] == [
        1,
        1,
    ], "Gegenprobe: Fassung 1 rechnet je Glättprobe einen Durchgang"


def test_ten_passes_make_a_hill_and_not_a_folded_column(slab: MeshData) -> None:
    """H4: Zehnmal dieselbe Linie in einer Etappe stapelte eine Säule mit Falte
    (gemessen 148,6° zwischen Nachbardreiecken); je Geste eine Etappe wird ein Hügel."""
    hill = apply_strokes(slab, _passes(slab, brush=2, strength=5.0))
    one_stage = [_changed(s, gesture=1, cut=False) for s in _passes(slab, 1, 0.5)]
    column = apply_strokes(slab, one_stage)

    assert _largest_fold(slab, column) > 120.0, "Gegenprobe: Fassung 1 in einer Etappe faltet"
    assert _largest_fold(slab, hill) < 80.0
    assert not len(crossing_face_pairs(hill.raw.vertices, np.asarray(hill.raw.faces)).first)
    top = float(hill.raw.bounds[1][2]) - 10.0
    assert 1.0 < top < 5.0, f"ein Hügel, keine Säule: {top:.2f} mm"


@pytest.fixture(scope="module")
def rough_ball() -> MeshData:
    """Eine Kugel R 20 mit ±0,3 mm Rauschen, Startwert fest."""
    rng = np.random.default_rng(7)
    sphere = trimesh.creation.icosphere(subdivisions=5, radius=20.0)
    noise = 1.0 + rng.uniform(-0.015, 0.015, len(sphere.vertices))
    return MeshData.of(
        trimesh.Trimesh(
            vertices=sphere.vertices * noise[:, None], faces=sphere.faces, process=False
        )
    )


def _roughness(mesh: MeshData, reference: MeshData) -> float:
    near = np.linalg.norm(reference.raw.vertices - np.array([0.0, 0.0, 20.0]), axis=1) < 3.0
    return float(np.std(np.linalg.norm(mesh.raw.vertices[near], axis=1)))


def test_smoothing_never_roughens_whatever_the_level(rough_ball: MeshData) -> None:
    """H3: Glätten schoss in Fassung 1 ab Stärke 2 über — bei 3 war die Fläche
    rauer als vorher. In Fassung 2 ist jede Stufe ein Schritt hin zum Mittel."""
    before = _roughness(rough_ball, rough_ball)

    def smoothed(level: float, brush: int) -> float:
        stroke = Stroke(
            point=(0.0, 0.0, 20.0),
            normal=(0.0, 0.0, 1.0),
            radius=6.0,
            strength=level,
            tool="smooth",
            brush=brush,
        )
        return _roughness(apply_strokes(rough_ball, [stroke]), rough_ball)

    found = [smoothed(float(level), 2) for level in range(1, 11)]
    assert all(value < before for value in found)
    assert found == sorted(found, reverse=True), "höhere Stufe, glatter"
    assert smoothed(3.0, 1) > before, "Gegenprobe: Fassung 1 schießt über"


def test_pinching_never_crosses_the_fold() -> None:
    """H3: Kneifen mit Stärke 3 kreuzte in Fassung 1 (216 sich schneidende Paare);
    in Fassung 2 kommt es höchstens auf halbem Weg zur Strichmitte an."""
    base = ball(5)

    def line(brush: int, strength: float) -> MeshData:
        strokes = []
        for x in np.arange(-6.0, 6.01, 3.0):
            z = float(np.sqrt(400.0 - x * x))
            strokes.append(
                Stroke(
                    point=(float(x), 0.0, z),
                    normal=(float(x) / 20, 0.0, z / 20),
                    radius=6.0,
                    strength=strength,
                    tool="pinch",
                    gesture=1,
                    brush=brush,
                )
            )
        return apply_strokes(base, strokes)

    for level in (5.0, 10.0):
        after = line(2, level)
        assert not len(crossing_face_pairs(after.raw.vertices, np.asarray(after.raw.faces)).first)
    old = line(1, 3.0)
    assert len(crossing_face_pairs(old.raw.vertices, np.asarray(old.raw.faces)).first), (
        "Gegenprobe: Fassung 1 kreuzt"
    )


def test_flattening_stops_at_its_plane(slab: MeshData) -> None:
    """Zwanzig Flachzieh-Proben an einer Stelle ziehen eine Beule auf die
    Ebene und nicht darüber hinaus in eine Mulde."""
    bump = apply_strokes(slab, [Stroke((0.0, 0.0, 10.0), (0.0, 0.0, 1.0), 6.0, 10.0, brush=2)])
    flat = [
        Stroke((0.0, 0.0, 10.0), (0.0, 0.0, 1.0), 8.0, 10.0, tool="flatten", gesture=1, brush=2)
        for _ in range(20)
    ]
    after = apply_strokes(bump, flat)
    near = np.linalg.norm(after.raw.vertices[:, :2], axis=1) < 3.0
    heights = after.raw.vertices[near, 2]
    assert heights.min() >= float(bump.raw.vertices[near, 2].min()) - 1e-9, "keine Mulde"
    assert float(np.ptp(heights)) < float(np.ptp(bump.raw.vertices[near, 2])), "flacher"


def test_a_higher_level_lifts_more_and_one_gesture_saturates(slab: MeshData) -> None:
    """Die Stufe ohne Einheit: höher heißt mehr, und eine Geste häuft an einer
    Stelle höchstens :data:`ADD_LIMIT` volle Proben auf."""
    from app.core.geom.sculpt import ADD_LIMIT, ADD_SHARE

    def lift(level: float, probes: int) -> float:
        strokes = [
            Stroke((0.0, 0.0, 10.0), (0.0, 0.0, 1.0), 4.0, level, gesture=1, brush=2)
            for _ in range(probes)
        ]
        return float(apply_strokes(slab, strokes).raw.bounds[1][2]) - 10.0

    lifts = [lift(float(level), 1) for level in range(1, 11)]
    assert lifts == sorted(lifts) and lifts[0] > 0.0
    assert lift(10.0, 200) <= ADD_LIMIT * ADD_SHARE * 4.0 + 1e-9, "eine Geste sättigt"


def test_the_direction_follows_the_whole_brush(slab: MeshData) -> None:
    """H10: Die Richtung war die Normale der nächsten Ecke — vor einer Kante
    0°, auf ihr 45°, ein Sprung. In Fassung 2 wächst sie stetig, und auf einer
    verrauschten Fläche bleibt sie nahe der Senkrechten."""

    def angles(mesh: MeshData, points: list[tuple[float, float, float]], brush: int) -> np.ndarray:
        made = [stroke_at(mesh, point, radius=4.0, strength=5.0, brush=brush) for point in points]
        return np.degrees(np.arccos(np.clip([stroke.normal[2] for stroke in made], -1.0, 1.0)))

    towards = [(0.0, 20.0 - float(away), 10.0) for away in np.arange(3.0, -0.01, -0.25)]
    assert float(np.max(np.abs(np.diff(angles(slab, towards, 1))))) >= 44.0, "Gegenprobe"
    assert float(np.max(np.abs(np.diff(angles(slab, towards, 2))))) < 20.0

    rng = np.random.default_rng(3)
    rough = slab.raw.copy()
    top = rough.vertices[:, 2] > 9.99
    rough.vertices[top, 2] += rng.uniform(-0.15, 0.15, int(top.sum()))
    noisy = MeshData.of(rough)
    spots = [(float(x), float(y), 10.0) for x, y in rng.uniform(-12.0, 12.0, (30, 2))]
    assert float(np.median(angles(noisy, spots, 1))) > 3.0, "Gegenprobe"
    assert float(np.median(angles(noisy, spots, 2))) < 1.5


def test_the_mirror_plane_lies_where_the_body_meets_itself() -> None:
    """H11: Die erzeugte Figur hat ihre Symmetrie 4,2 mm neben der Mitte ihres
    Hüllquaders; die Suche findet sie. Ein Körper ohne Symmetrie behält die Mitte."""
    from app.core.geom.sculpt import fitted_mirror_centre, mirror_centre, mirror_plane

    meshes = Path(__file__).parent / "data" / "meshes"
    figure = read_mesh((meshes / "generated_figure.stl").read_bytes(), ".stl")
    middle = mirror_centre(figure)
    fitted = fitted_mirror_centre(figure, (0,))
    assert float(middle[0]) == pytest.approx(4.2, abs=0.05), (
        "Voraussetzung: die Mitte liegt daneben"
    )
    assert abs(float(fitted[0])) < 0.3
    assert mirror_plane(figure, axes=1)[0] == pytest.approx(float(fitted[0]))
    assert mirror_plane(figure, fitted=False, axes=1)[0] == pytest.approx(float(middle[0]))
    assert mirror_plane(figure, axes=0) == tuple(float(v) for v in middle), (
        "ohne Spiegeln keine Suche"
    )

    wedge = trimesh.creation.box(extents=(30, 10, 10))
    wedge.vertices[wedge.vertices[:, 0] > 0, 2] *= 3.0
    uneven = MeshData.of(wedge)
    assert fitted_mirror_centre(uneven, (0,))[0] == pytest.approx(float(mirror_centre(uneven)[0]))


def test_the_brush_version_survives_the_text_and_refuses_the_unknown() -> None:
    """Die Fassung reist im Zug mit; eine, die dieses Programm nicht rechnen kann,
    ist ein Lesefehler mit Ausweg und kein still falscher Zug."""
    import json

    stroke = _second(1.0, 0.0, 0.0, gesture=4)
    text = strokes_to_text([stroke, on_ball(0.0, 1.0, 0.0)])
    data = json.loads(text)
    assert data[0]["v"] == 2 and "v" not in data[1], "Fassung 1 schreibt nichts Neues"
    assert strokes_from_text(text)[0] == stroke
    data[0]["v"] = 3
    with pytest.raises(ValidationError) as caught:
        strokes_from_text(json.dumps(data))
    assert caught.value.suggestions


def test_a_coarse_mesh_is_refined_for_the_brush_and_then_it_works() -> None:
    """H9 und H2: Am Quader aus zwölf Dreiecken tat ein Zug nichts (bewegt 0 mm,
    ``sculpt.no_effect``). Die Sitzung gleicht auf ``radius / REFINE_TO_EDGE``
    an; danach trägt derselbe Zug über eine Schichthöhe."""
    from app.core.geom.sculpt import (
        BRUSH_TO_EDGE,
        REFINE_TO_EDGE,
        brush_radius_for,
        median_edge,
        refine_edge_for,
    )
    from app.core.knowledge import profiles

    box = MeshData.of(trimesh.creation.box(extents=(40, 30, 10)))
    radius = brush_radius_for(box)
    assert radius == 2.0, "ein Zwanzigstel von 51 mm, auf 1-2-5 gerundet"
    edge = refine_edge_for(box, radius, finest=0.05)
    assert edge == pytest.approx(radius / REFINE_TO_EDGE)
    fine = uniform(box, edge, 0.0)
    assert median_edge(fine) * BRUSH_TO_EDGE <= radius
    assert refine_edge_for(fine, radius, finest=0.05) == 0.0, "fein genug, kein zweites Mal"

    stroke = stroke_at(fine, (0.0, 0.0, 5.0), radius=radius, strength=5.0, brush=2)
    after = apply_strokes(fine, [stroke])
    moved = float(np.linalg.norm(after.raw.vertices - fine.raw.vertices, axis=1).max())
    layer = profiles.make_profile("centauri-carbon-2", "petg").printer.layer_height
    assert moved > layer
    rough = stroke_at(box, (0.0, 0.0, 5.0), radius=radius, strength=5.0, brush=2)
    coarse = apply_strokes(box, [rough])
    assert np.allclose(coarse.raw.vertices, box.raw.vertices), "Gegenprobe: ohne Angleichen nichts"


def test_refining_stays_within_its_triangle_budget() -> None:
    """Ein kleiner Pinsel auf einem großen Körper würde Millionen Dreiecke
    verlangen; die Kante hält :data:`REFINE_MAX_TRIANGLES` ein."""
    import math

    from app.core.geom.sculpt import REFINE_MAX_TRIANGLES, REFINE_TO_EDGE, refine_edge_for

    big = MeshData.of(trimesh.creation.box(extents=(200, 200, 200)))
    edge = refine_edge_for(big, 0.5, finest=0.05)
    estimate = float(big.raw.area) / (math.sqrt(3.0) / 4.0 * edge * edge)
    assert estimate <= REFINE_MAX_TRIANGLES * 1.0001
    assert edge > 0.5 / REFINE_TO_EDGE


def test_the_starting_radius_follows_the_body() -> None:
    """H8: 6 mm fest waren am Korpus 0,059 bis 0,173 der Diagonale; aus der
    Körpergröße bleibt es um ein Zwanzigstel — die Rundung auf 1-2-5 lässt
    höchstens den Faktor √2,5 nach jeder Seite."""
    from app.core.geom.sculpt import brush_radius_for

    meshes = Path(__file__).parent / "data" / "meshes"
    shares, fixed = [], []
    for name in ("clean_figure.stl", "generated_figure.stl", "cube_clean.stl", "sphere_socket.stl"):
        mesh = read_mesh((meshes / name).read_bytes(), ".stl")
        diagonal = float(np.linalg.norm(np.ptp(mesh.raw.bounds, axis=0)))
        shares.append(brush_radius_for(mesh) / diagonal)
        fixed.append(6.0 / diagonal)
    band = 2.5**0.5 / 20.0
    assert all(1.0 / 400.0 / band <= share <= band for share in shares), shares
    assert max(shares) / min(shares) < max(fixed) / min(fixed), "Gegenprobe: 6 mm fest"


# --- Etappen der Fassung 2 rechnen nur ihr Gebiet (F6, RM-560) ------------------------


def _gestures(tool: str, symmetry: int, seed: int = 3) -> list[Stroke]:
    """Dreißig Gesten zu je sechs Proben, eng beieinander, damit sie sich
    überlagern; ``tool="mixed"`` wechselt das Werkzeug je Geste."""
    generator = np.random.default_rng(seed)
    strokes = []
    for gesture in range(1, 31):
        aim = np.array([0.3, 0.2, 1.0]) + generator.normal(scale=0.3, size=3)
        aim /= np.linalg.norm(aim)
        chosen = SCULPT_TOOLS[gesture % len(SCULPT_TOOLS)] if tool == "mixed" else tool
        for _sample in range(6):
            place = aim * 20.0 + generator.normal(scale=1.0, size=3)
            place = place / np.linalg.norm(place) * 20.0
            strokes.append(
                Stroke(
                    tuple(place),
                    tuple(place / 20.0),
                    3.0,
                    float(generator.integers(1, 11)),
                    tool=chosen,
                    gesture=gesture,
                    brush=2,
                    symmetry=symmetry,
                )
            )
    return strokes


def _fresh_stages(mesh: MeshData, strokes: list[Stroke], plane: tuple[float, float, float]):
    """Die Rechnung vor F6: jede Etappe auf einem neuen Netz mit eigenem
    Suchbaum und allen Normalen, jeder Zug einzeln."""
    from app.core.geom.sculpt import _Stage

    body = mesh.raw
    for part in stages(strokes):
        stage = _Stage(body, np.asarray(plane), front_only=True, mirror_once=True)
        for stroke in part:
            stage.add(stroke)
        body = stage.moved()
    return np.asarray(body.vertices)


@pytest.mark.parametrize("symmetry", [0, 1], ids=["plain", "mirrored"])
@pytest.mark.parametrize("tool", [*SCULPT_TOOLS, "mixed"])
def test_a_stage_that_only_follows_its_area_computes_the_same_mesh(tool: str, symmetry: int):
    """F6: Die Auswertung führt Ecken, Normalen und Suchbaum nur im Gebiet der
    vorigen Etappe nach und rechnet eine Etappe in einem Schritt. Das Netz ist
    bitgleich mit der Rechnung, die jede Etappe neu aufbaut — und mit der
    Vorschau, die Zug für Zug rechnet."""
    from app.core.geom.sculpt import mirror_centre

    mesh = ball(5)
    middle = mirror_centre(mesh)
    plane = (float(middle[0]), float(middle[1]), float(middle[2]))
    strokes = _gestures(tool, symmetry)
    evaluated = np.asarray(apply_strokes(mesh, strokes, centre=plane).raw.vertices)
    assert np.abs(evaluated - np.asarray(mesh.raw.vertices)).max() > 0.01, (
        "Gegenprobe: nichts geformt"
    )
    assert np.array_equal(evaluated, _fresh_stages(mesh, strokes, plane))
    preview = SculptPreview(mesh, centre=plane)
    for count in range(1, len(strokes) + 1):
        preview.extend(strokes[:count])
    assert np.array_equal(evaluated, np.asarray(preview.shown.raw.vertices))


def test_gestures_build_nothing_over_the_whole_mesh_per_stage(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """F6, Review N2: Was eine Etappe teuer machte, war der Neuaufbau von
    Suchbaum und Normalen über das ganze Netz — einer je Geste. Gezählt statt
    gestoppt, damit es auf jedem Rechner gilt: Fünfzig Gesten bauen den Suchbaum
    höchstens zweimal über alle Ecken und die Normalen nie; die Rechnung von
    vorher baute beides je Etappe."""
    import app.core.geom.sculpt as sculpt

    mesh = ball(5)
    count = len(mesh.raw.vertices)
    trees: list[int] = []
    normals: list[int] = []
    built = sculpt.cKDTree

    def tree(points: Any, *args: Any, **kwargs: Any) -> Any:
        if len(points) == count:
            trees.append(1)
        return built(points, *args, **kwargs)

    whole = sculpt._Stage.normals.fget
    monkeypatch.setattr(sculpt, "cKDTree", tree)
    monkeypatch.setattr(
        sculpt._Stage, "normals", property(lambda stage: normals.append(1) or whole(stage))
    )
    generator = np.random.default_rng(11)
    strokes = []
    for gesture in range(1, 51):
        aim = generator.normal(size=3)
        aim /= np.linalg.norm(aim)
        for _sample in range(5):
            place = aim * 20.0 + generator.normal(scale=1.0, size=3)
            place = place / np.linalg.norm(place) * 20.0
            strokes.append(
                Stroke(tuple(place), tuple(place / 20.0), 3.0, 5.0, gesture=gesture, brush=2)
            )
    apply_strokes(mesh, strokes, centre=(0.0, 0.0, 0.0))
    assert len(trees) <= 2 and not normals, (len(trees), len(normals))
    trees.clear()
    _fresh_stages(mesh, strokes, (0.0, 0.0, 0.0))
    assert len(trees) == 50, "Gegenprobe: je Etappe neu"


def test_local_normals_are_the_normals_of_the_whole_mesh() -> None:
    """Eine Ecke bekommt dieselbe Normale, ob ihr Gebiet allein oder das ganze
    Netz gerechnet wird; an einer Ikosaederkugel ist es bis auf ein
    Achtelgrad die von ``Trimesh``."""
    from app.core.geom.sculpt import _Topology

    raw = trimesh.creation.icosphere(subdivisions=5, radius=20.0)
    points = np.asarray(raw.vertices, dtype=float)
    points = points + np.random.default_rng(1).normal(scale=0.05, size=points.shape)
    topology = _Topology(raw.faces, len(points))
    whole = topology.vertex_normals(points, np.arange(len(points)))
    some = np.sort(np.random.default_rng(2).choice(len(points), 500, replace=False))
    assert np.array_equal(topology.vertex_normals(points, some), whole[some])
    regular = np.asarray(raw.vertices, dtype=float)
    ours = topology.vertex_normals(regular, np.arange(len(regular)))
    cosine = np.einsum("ij,ij->i", ours, np.asarray(raw.vertex_normals))
    assert np.degrees(np.arccos(np.clip(cosine, -1.0, 1.0))).max() < 0.25


def test_an_old_search_tree_finds_what_a_new_one_finds() -> None:
    """Der Suchbaum bleibt über Etappen stehen, solange die Ecken nicht weiter
    gewandert sind als ein Radius; Kugelabfragen messen nach und liefern
    dieselben Ecken, sortiert, wie ein neuer Baum — einzeln wie gesammelt."""
    from app.core.geom.sculpt import _Lookup

    raw = trimesh.creation.icosphere(subdivisions=5, radius=20.0)
    before = np.asarray(raw.vertices, dtype=float)
    generator = np.random.default_rng(4)
    moved = generator.choice(len(before), 2000, replace=False)
    after = before.copy()
    after[moved] += generator.normal(scale=0.8, size=(len(moved), 3))
    old = _Lookup(before).moved(after, np.sort(moved), 5.0)
    assert old.drift > 0.0, "Gegenprobe: der alte Baum muss nachmessen"
    fresh = _Lookup(after)
    centres = after[generator.integers(0, len(after), 40)]
    radii = np.full(len(centres), 3.0)
    near, away, owner, bounds = old.balls(centres, radii)
    for number, centre in enumerate(centres):
        expected, distance = fresh.ball(centre, 3.0)
        found, measured = old.ball(centre, 3.0)
        assert np.array_equal(found, expected) and np.array_equal(measured, distance)
        low, high = bounds[number], bounds[number + 1]
        assert np.array_equal(near[low:high], expected)
        assert np.array_equal(away[low:high], distance)
        assert np.all(owner[low:high] == number)
