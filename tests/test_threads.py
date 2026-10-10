"""Gewinde, die sich wirklich zusammenschrauben lassen (§24.3, §25, §40).

Ein Gewinde ist die eine Form, deren zwei Hälften sich nicht getrennt
beurteilen lassen: jede für sich sieht aus wie ein Gewinde, ist wasserdicht und
hat die richtigen Außenmaße — und das Paar greift trotzdem nicht. Genau das ist
passiert: die Mutter wurde auf den Außendurchmesser gebohrt statt auf den Kern,
es blieb also nichts stehen, woran der Gang der Schraube hätte halten können,
und sie fiel glatt hindurch. An M6 gemessen: Kamm bei r = 2,925, Loch beginnend
bei r = 3,075.

Alles hier wird darum am *Paar* gemessen: das Material des einen muss ins Tal
des anderen reichen, und der Spalt dazwischen muss das Spiel sein, nach dem
gefragt wurde — nicht mehr, nicht weniger.
"""

from __future__ import annotations

import dataclasses
import itertools
import math

import numpy as np
import pytest

from app.core.geom.mesh import Mesh, as_mesh_data
from app.core.knowledge.parts.fasteners import ThreadParams, printed_thread
from app.core.knowledge.parts.shapes import RIDGE_SHARE

#: Wo die Radien gemessen werden: innerhalb der Gewindelänge, abseits der
#: Endkappen, die auf der Achse sitzen und einen Radius von null meldeten.
BAND = (3.0, 9.0)


def radii(body: Mesh, low: float = BAND[0], high: float = BAND[1]) -> tuple[float, float]:
    """Kleinster und größter Abstand von der Achse, im gegebenen Höhenband.

    Das Band gilt im **eigenen** Lagebereich des Körpers: Ein Innengewinde
    liegt seit accac66c unter seiner Mündung (§24.1, Werkzeuglage), sein
    Material also bei negativem z. Gemessen wird die Gewindeform, nicht die
    Lage — deshalb wird das Band an die Unterkante des Körpers angelegt,
    und die Radienvergleiche der Tests bleiben, was sie waren.
    """
    points = np.asarray(as_mesh_data(body).raw.vertices)
    floor = float(points[:, 2].min())
    inside = points[(points[:, 2] > floor + low) & (points[:, 2] < floor + high)]
    lengths = np.linalg.norm(inside[:, :2], axis=1)
    lengths = lengths[lengths > 1e-9]
    return float(lengths.min()), float(lengths.max())


def pair(size: str = "M6", play: float = 0.15, length: float = 12.0):
    male = printed_thread(ThreadParams(size=size, length=length, internal=False, play=play))
    female = printed_thread(ThreadParams(size=size, length=length, internal=True, play=play))
    return male, female


def test_a_screw_and_its_nut_interlock() -> None:
    """Die Regression: beide Hälften waren richtig und das Paar war es nicht.

    Die Mutter ist ein *Werkzeug*, ihre Zahlen sind also das Loch, das sie
    hinterlässt. Ihr Material beginnt dort, wo ihre Bohrung beginnt, und das
    muss im Tal der Schraube liegen — sonst dreht die Schraube frei in einem
    glatten Loch.
    """
    male, female = pair()

    screw_core, screw_crest = radii(male.mesh)
    hole_core, hole_crest = radii(female.mesh)

    assert hole_core > screw_core, "the nut has to reach into the valley of the screw"
    assert hole_crest > screw_crest, "and clear its crest"


def test_the_gap_is_the_play_that_was_asked_for() -> None:
    """Nicht mehr: ein Gewinde mit einem halben Millimeter Luft hält nichts."""
    male, female = pair(play=0.15)

    screw_core, screw_crest = radii(male.mesh)
    hole_core, hole_crest = radii(female.mesh)

    assert hole_core - screw_core == pytest.approx(0.15, abs=0.01)
    assert hole_crest - screw_crest == pytest.approx(0.15, abs=0.01)


def test_without_play_the_two_meet_exactly() -> None:
    male, female = pair(play=0.0)

    assert radii(male.mesh)[1] == pytest.approx(radii(female.mesh)[1], abs=0.01)


def test_the_ridge_is_as_deep_as_the_pitch_says() -> None:
    """§24.3: die Tiefe ist ein Anteil der Steigung, und alle drei Nutzer
    teilen ihn.
    """
    male, _female = pair(size="M6")
    core, crest = radii(male.mesh)

    assert crest - core == pytest.approx(1.0 * RIDGE_SHARE, abs=0.01), "M6 has a pitch of 1 mm"


def test_a_finer_thread_has_a_shallower_ridge() -> None:
    coarse, _ = pair(size="M8")
    fine, _ = pair(size="M3")

    coarse_depth = radii(coarse.mesh)[1] - radii(coarse.mesh)[0]
    fine_depth = radii(fine.mesh)[1] - radii(fine.mesh)[0]

    assert coarse_depth > fine_depth


def test_both_halves_are_closed_bodies() -> None:
    """§24.3: ein Baustein, der nicht wasserdicht ist, ist kein Baustein."""
    male, female = pair()

    assert as_mesh_data(male.mesh).is_watertight
    assert as_mesh_data(female.mesh).is_watertight


def test_the_screw_stays_under_its_nominal_diameter() -> None:
    """Eine M6, die 6,2 misst, geht nicht durch ein 6-mm-Loch."""
    male, _female = pair(size="M6", play=0.15)

    assert radii(male.mesh)[1] * 2.0 == pytest.approx(6.0 - 0.15, abs=0.01)


def custom_pair(diameter: float, pitch: float = 0.0, play: float = 0.15, length: float = 12.0):
    """Wie :func:`pair`, mit eigenem Maß statt einer Tabellengröße."""
    from app.core.knowledge.parts.fasteners import CUSTOM_SIZE

    values = {"size": CUSTOM_SIZE, "diameter": diameter, "pitch": pitch, "length": length}
    male = printed_thread(ThreadParams(**values, internal=False, play=play))
    female = printed_thread(ThreadParams(**values, internal=True, play=play))
    return male, female


@pytest.mark.parametrize(("diameter", "pitch"), [(7.6, 1.0), (66.6, 6.0), (250.0, 6.0)])
def test_a_thread_of_its_own_measure_interlocks_with_the_play_asked_for(
    diameter: float, pitch: float
) -> None:
    """Das Paar mit eigenem Maß hält dieselben Zusagen wie das aus der Tabelle.

    Ø 66,6 ist das Gewinde, das bis Tabellenversion 12 eine Bohrung von 60 mm
    bekam (Kundenvorschlag S-20261006-c66299); Ø 250 liegt weit über jeder
    Tabelle. Die Steigungen sind die groben nach ISO 262 als Zahl, nicht aus
    ``standards`` gelesen — ein Fehler dort bliebe sonst grün: Ø 7,6 trägt die
    1 mm der M6, Ø 66,6 und 250 die 6 mm der M64.
    """
    from app.core.units import MAX_FACET_SAG

    male, female = custom_pair(diameter)
    screw_core, screw_crest = radii(male.mesh)
    hole_core, hole_crest = radii(female.mesh)
    depth = pitch * RIDGE_SHARE

    # Die Kämme liegen auf Ecken und treffen das Maß; der Grund der Mutter ist
    # die Bohrung ihres Werkzeugs, und deren Sehnen liegen bis zu
    # ``MAX_FACET_SAG`` innerhalb — bei Ø 250 gemessen 0,03 mm, wie jede Rundung.
    assert hole_crest - screw_crest == pytest.approx(0.15, abs=0.01)
    assert hole_core - screw_core == pytest.approx(0.15, abs=MAX_FACET_SAG)
    assert screw_crest * 2.0 == pytest.approx(diameter - 0.15, abs=0.01)
    assert screw_crest - screw_core == pytest.approx(depth, abs=0.01)
    assert as_mesh_data(male.mesh).is_watertight and as_mesh_data(female.mesh).is_watertight


def test_a_stated_pitch_beats_the_regular_one() -> None:
    """Eine feinere Steigung schneidet flacher — der Weg für die dünne Rohrwand."""
    male, _female = custom_pair(66.6, pitch=2.0)
    core, crest = radii(male.mesh)

    assert crest - core == pytest.approx(2.0 * RIDGE_SHARE, abs=0.01)


def test_a_pitch_too_coarse_for_the_diameter_is_refused_with_a_way_out() -> None:
    """Ø 4 mit 5 mm Steigung hätte keinen Kern: eine Absage, die das Feld nennt."""
    from app.core.errors import ValidationError

    with pytest.raises(ValidationError) as caught:
        custom_pair(4.0, pitch=5.0)
    assert caught.value.field == "pitch"
    assert caught.value.suggestions


def test_a_wide_thread_gets_chords_as_fine_as_any_other_rounding() -> None:
    """Je Umlauf so viele Sehnen, dass die Abweichung unter ``MAX_FACET_SAG`` bleibt.

    Bis Ø 46 sind es achtundvierzig wie bisher — jede Tabellengröße bis M42
    baut unverändert —, darüber ein Vielfaches davon, auch für M48 bis M64.
    Mit festen achtundvierzig wich ein Gewinde Ø 500 um 0,53 mm von seiner
    Rundung ab, mehr als das Spiel.
    """
    import math

    from app.core.knowledge import standards
    from app.core.knowledge.parts.shapes import SEGMENTS, turn_segments
    from app.core.units import MAX_FACET_SAG

    for size in standards.screw_sizes():
        # Das Innenwerkzeug reicht am weitesten hinaus: Nennmaß plus Spiel.
        radius = standards.screw(size).nominal / 2.0 + 1.0
        expected = SEGMENTS if standards.screw(size).nominal <= 42.0 else 2 * SEGMENTS
        assert turn_segments(radius) == expected, size
    for radius in (24.0, 33.3, 125.0, 500.0):
        count = turn_segments(radius)
        assert count % SEGMENTS == 0
        assert radius * (1.0 - math.cos(math.pi / count)) <= MAX_FACET_SAG + 1e-12
        assert radius * (1.0 - math.cos(math.pi / (count - SEGMENTS))) > MAX_FACET_SAG


@pytest.mark.parametrize(("diameter", "length"), [(46.0, 2.0), (46.0, 10.0), (500.0, 7.0)])
def test_the_built_thread_has_the_chords_of_the_facet_rule_in_every_turn(
    diameter: float, length: float, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Gemessen am Bau, nicht an der Formel von ``turn_segments``.

    ``thread_body`` verteilt ``round(Umläufe) · segments`` Schritte über seine
    Höhe. Bei krummer Umlaufzahl blieben je Umlauf weniger Sehnen, als die
    Facettenregel verlangt: Ø 46 auf 2 mm 33 statt 48 und 0,103 mm Abweichung
    (Review RM-532, R1). ``build.threaded`` baut den Gang deshalb über ganze
    Umläufe; geprüft wird, was es ``thread_body`` wirklich übergibt, und die
    Abweichung, die daraus folgt.
    """
    from app.core.knowledge.parts import shapes
    from app.core.units import MAX_FACET_SAG

    seen: list[tuple[float, float, int]] = []
    original = shapes.thread_body

    def recorded(diameter: float, pitch: float, height: float, **kwargs: object) -> object:
        seen.append((height, pitch, int(kwargs["segments"])))  # type: ignore[call-overload]
        return original(diameter, pitch, height, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(shapes, "thread_body", recorded)
    male, _female = custom_pair(diameter, length=length)
    assert as_mesh_data(male.mesh).is_watertight
    for height, pitch, segments in seen:
        turns = height / pitch
        assert turns == pytest.approx(round(turns), abs=1e-9), "ganze Umläufe"
        steps = max(round(turns), 1) * segments
        per_turn = steps / turns
        radius = diameter / 2.0 + 0.15
        assert radius * (1.0 - np.cos(np.pi / per_turn)) <= MAX_FACET_SAG + 1e-9


def test_every_thread_path_shares_the_same_limits() -> None:
    """Die Regel in ``bausteine.md`` ist Prosa — dieser Test hält sie (Review RM-532, R6).

    Baustein, *Schraube erstellen*, Gegenstück und Drehdeckel lesen ihre
    Grenzen aus ``units``; der Drehdeckel beginnt bei der Steigung bewusst bei
    1 mm, weil ein Schraubdeckel feiner nicht greift.
    """
    from app.core.brep.ops import ThreadParams as ExactThreadParams
    from app.core.geom.lid import ScrewLidParams
    from app.core.knowledge import standards
    from app.core.knowledge.parts.fasteners import ThreadedRodParams
    from app.core.knowledge.parts.fasteners import ThreadParams as PartThreadParams
    from app.core.units import COARSEST_PITCH, FINEST_PITCH, LARGEST_THREAD, SMALLEST_THREAD

    def bounds(params: type, name: str) -> tuple[object, object]:
        entry = next(item for item in params.spec() if item.name == name)
        return entry.minimum, entry.maximum

    assert bounds(PartThreadParams, "diameter") == (SMALLEST_THREAD, LARGEST_THREAD)
    assert bounds(PartThreadParams, "pitch")[1] == COARSEST_PITCH
    # Der Gewindebolzen teilt den Kern mit dem Baustein (Review G-f).
    assert bounds(ThreadedRodParams, "diameter") == (SMALLEST_THREAD, LARGEST_THREAD)
    assert bounds(ThreadedRodParams, "pitch")[1] == COARSEST_PITCH
    assert bounds(ExactThreadParams, "diameter") == (SMALLEST_THREAD, LARGEST_THREAD)
    assert bounds(ExactThreadParams, "pitch") == (FINEST_PITCH, COARSEST_PITCH)
    assert bounds(ScrewLidParams, "pitch")[1] == COARSEST_PITCH
    assert bounds(ScrewLidParams, "neck")[1] == LARGEST_THREAD
    # Unten begrenzt die kleinste Schraube der Tabelle (Review RM-532, K6).
    smallest = standards.screw(standards.screw_sizes()[0]).nominal
    assert smallest == SMALLEST_THREAD


def test_a_threaded_rod_builds_at_its_shortest_length() -> None:
    """Review G-a: Die Mindestlänge des Bolzens baute nie.

    Die Prüfung zählte das durchgehende Gewinde je halbe Länge und verlangte
    so 4 mm plus zwei Fasen. Gebaut wird es als **ein** Gewinde zwischen zwei
    Kuppen, und so wird es jetzt geprüft.
    """
    from app.core.knowledge.parts.fasteners import ThreadedRodParams, threaded_rod

    shortest = next(entry for entry in ThreadedRodParams.spec() if entry.name == "length")
    rod = threaded_rod(ThreadedRodParams(size="M3", length=float(shortest.minimum)))
    assert as_mesh_data(rod.mesh).is_watertight


@pytest.mark.parametrize(
    ("values", "field", "advice"),
    [
        ({"size": "M8", "length": 6.0, "chamfer": 3.0}, "chamfer", "kleinere Fase"),
        ({"size": "M8", "length": 4.0, "chamfer": 1.5}, "length", "längeren Bolzen"),
        ({"size": "M6", "length": 30.0, "thread_length": 2.5}, "thread_length", "Gewindelänge"),
        ({"size": "M6", "length": 10.0, "thread_length": 6.0}, "thread_length", "Kürzen"),
        ({"size": "M1.6", "play": 1.0}, "play", "weniger Spiel"),
    ],
)
def test_a_refused_threaded_rod_points_at_the_field_that_helps(
    values: dict[str, object], field: str, advice: str
) -> None:
    """Review G-a: Die Absage ging an die Gewindelänge, sonst an die Fase.

    Auch wenn die Länge der Grund war, und bei automatischer Fase riet sie zu
    einer kleineren — an einem Feld, das auf null steht.
    """
    from app.core.errors import ValidationError
    from app.core.knowledge.parts.fasteners import ThreadedRodParams, threaded_rod

    with pytest.raises(ValidationError) as caught:
        threaded_rod(ThreadedRodParams(**values))  # type: ignore[arg-type]
    assert caught.value.field == field
    assert advice in str(caught.value.detail)
    assert caught.value.suggestions


def test_a_pitch_finer_than_the_finest_is_refused_with_a_way_out() -> None:
    """0,01 mm Steigung baute am Netz Millionen Dreiecke ohne Abbruch (Review RM-532, R2)."""
    from app.core.errors import ValidationError

    with pytest.raises(ValidationError) as caught:
        custom_pair(20.0, pitch=0.1)
    assert caught.value.constraint == "finest_pitch"
    assert caught.value.suggestions
    male, _female = custom_pair(20.0, pitch=0.25, length=2.0)
    assert as_mesh_data(male.mesh).is_watertight


def test_a_bolt_needs_a_core_of_a_third_of_its_diameter() -> None:
    """Ø 2 × 1,6 außen ließ 0,04 mm Kern stehen und baute (Review RM-532, R3).

    Dieselbe Regel wie *Schraube erstellen* (``units.THREAD_MIN_CORE_SHARE``),
    für beide Hälften am Bolzen des Maßes geprüft — ein Innengewinde ohne
    möglichen Bolzen hat kein Gegenstück.
    """
    from app.core.errors import ValidationError

    for internal in (False, True):
        with pytest.raises(ValidationError) as caught:
            values = {"size": "custom_size", "diameter": 2.0, "pitch": 1.6, "length": 4.0}
            printed_thread(ThreadParams(**values, internal=internal, play=0.2))
        assert caught.value.constraint == "no_core"
    # Die kleinste Tabellengröße mit dem größten Spiel hält die Regel noch.
    male = printed_thread(ThreadParams(size="M1.6", length=4.0, internal=False, play=1.0))
    assert as_mesh_data(male.mesh).is_watertight


@pytest.mark.parametrize(
    ("bore", "size"),
    [(8.5, "M10"), (10.2, "M12"), (17.5, "M20"), (21.0, "M24"), (50.5, "M56"), (58.0, "M64")],
)
def test_an_iso_tap_drill_hole_gets_its_standard_thread(bore: float, size: str) -> None:
    """Wer für M24 gebohrt hat, bekommt M24 — nicht ein eigenes Maß Ø 23,75 (Review RM-532, K1).

    Das Kernloch als Bohrermaß (D − P) steht seit Tabellenversion 13 für jede
    Größe bis M64 in der Tabelle; die Bohrung trifft deshalb die Normgröße.
    """
    from app.core.knowledge.parts.fasteners import size_for_thread

    assert size_for_thread(bore) == {"size": size, "internal": True}


@pytest.mark.parametrize(
    ("nominal", "pitch", "size"), [(16.0, 2.0, "M16"), (27.0, 3.0, "M27"), (45.0, 4.5, "M45")]
)
def test_a_bore_at_the_printed_root_gets_its_standard_thread(
    nominal: float, pitch: float, size: str
) -> None:
    """Eine Bohrung am Gangfuß des gedruckten Gewindes ist dessen Kernloch (Review P2, M1).

    Der Gangfuß liegt bei D − 2 · ``RIDGE_SHARE`` · P (Steigungen nach ISO 261):
    M16 13,8, M27 23,7, M45 40,05. Die Tabellengröße begann am Bohrermaß D − P,
    und dazwischen kam ein eigenes Maß, das genau die Normgröße war — „Ø 16,00,
    Steigung 2,00, kein Normgewinde“.
    """
    from app.core.knowledge.parts.fasteners import size_for_thread, thread_advice

    bore = nominal - 2.0 * RIDGE_SHARE * pitch
    assert size_for_thread(bore) == {"size": size, "internal": True}
    assert "Normgewinde" not in str(thread_advice(bore))


@pytest.mark.parametrize(("bore", "size"), [(4.95, "M6"), (20.8, "M24")])
def test_where_the_pitch_changes_the_printed_root_decides(bore: float, size: str) -> None:
    """Zwischen Gangfuß und Bohrermaß liegt die Normgröße, auch ohne Rundung (Review P2 N4a).

    Die Tabellengröße beginnt am Gangfuß D − 1,1 P (M6 4,9, M24 20,7), nicht am
    Bohrermaß D − P (5,0 und 21,0). Wo der kleinere Nachbar eine andere Steigung
    hat, fängt die Rundung das nicht auf: Das eigene Maß wäre Ø 5,83 x 0,8 und
    Ø 23,55 x 2,5, keines davon nahe einer Normgröße.
    """
    from app.core.knowledge import standards
    from app.core.knowledge.parts.fasteners import custom_thread_for, size_for_thread

    custom = custom_thread_for(bore)
    assert custom is not None and standards.thread_size_near(*custom) is None, (
        "sonst entschiede die Rundung, nicht der Gangfuß"
    )
    assert size_for_thread(bore) == {"size": size, "internal": True}


def test_the_sentence_says_which_standard_size_is_too_wide() -> None:
    """An Ø 6 nennt der Satz die M6, der die Bohrung zu weit ist, und das eigene Maß (N4b).

    An Ø 6,5 hat keine Größe dieses Nennmaß, und der Satz bleibt der allgemeine.
    """
    from app.core.knowledge.parts.fasteners import thread_advice

    wide = str(thread_advice(6.0))
    assert "M6" in wide and "7,10" in wide and "weit" in wide, wide
    plain = str(thread_advice(6.5))
    assert "weit" not in plain and "7,60" in plain, plain


@pytest.mark.parametrize(("bore", "size", "root"), [(13.65, "M16", 13.8), (40.0, "M45", 40.05)])
def test_a_bore_just_under_the_root_takes_the_standard_size_and_is_widened(
    bore: float, size: str, root: float
) -> None:
    """Knapp unter dem Gangfuß rundet die Vorwahl auf die Normgröße wie das Gegenstück.

    Das eigene Maß an Ø 40 wäre 40 + 1,1 · 4,5 = 44,95 x 4,5, eine M45 bis auf
    0,05 mm; an Ø 13,65 wäre es 15,85 x 2. Beide liegen innerhalb von
    ``standards.THREAD_SIZE_REACH`` neben der Normgröße, und wer eine M45 hat,
    müsste raten (Review P2, M1). Gewählt wird die Normgröße, und das Gewinde
    sagt, dass es die Bohrung bis zum Gangfuß aufweitet (``parts.bore_widened``).
    """
    from app.core.knowledge.parts.fasteners import (
        ThreadParams,
        custom_thread_for,
        size_for_thread,
        thread_at_hole,
    )
    from app.core.knowledge.standards import THREAD_SIZE_REACH
    from app.core.types import Feature

    custom = custom_thread_for(bore)
    assert custom is not None
    assert 0.0 < float(size[1:]) - custom[0] <= THREAD_SIZE_REACH[0], "sonst prüft das nichts"
    chosen = size_for_thread(bore)
    assert chosen == {"size": size, "internal": True}
    hole = Feature(
        id="hole_1",
        kind="hole",
        provenance="detected",
        params={"diameter": bore, "depth": 10.0, "centre": (0.0, 0.0, 0.0), "axis": (0, 0, 1)},
    )
    params = ThreadParams(**chosen, length=10.0, play=0.2)
    widened = [entry for entry in thread_at_hole(params, hole, None, None) if entry.values]
    assert [entry.code for entry in widened] == ["parts.bore_widened"]
    assert widened[0].values["core_mm"] == pytest.approx(root + 0.2)


def test_no_preselected_custom_thread_is_a_standard_size() -> None:
    """Kein eigenes Maß der Vorwahl liegt innerhalb der Erkennungsgrenze einer Normgröße.

    Gegenstück und Vorwahl runden mit derselben Grenze (Review P2, M1); vorher
    gab es Bänder von 0,35 mm unter jedem Kernloch ab M16, in denen „kein
    Normgewinde“ über einer Normgröße stand. Abgetastet in 0,01-mm-Schritten
    vom kleinsten Kernloch bis über M64.

    **Und jede gewählte Tabellengröße greift** (Review P2 N3): Die Rundung
    darf keine Größe nehmen, deren Gang die Wand nicht erreicht. Die eine
    Ausnahme ist benannt: An der M1.6 ist die Erkennungsgrenze weiter als
    0,55 der Steigung, und Ø 1,41 behält sein eigenes Maß neben ihr.
    """
    from app.core.knowledge import standards
    from app.core.knowledge.parts.fasteners import (
        CUSTOM_SIZE,
        _gripped_up_to,
        size_for_thread,
        thread_dims,
        thread_measure,
    )

    hits = []
    loose = []
    customs = sized = 0
    for step in range(125, 7000):
        bore = step / 100.0
        chosen = size_for_thread(bore)
        size = chosen.get("size")
        if size is not None and size != CUSTOM_SIZE:
            sized += 1
            if bore > _gripped_up_to(thread_dims(size)):
                loose.append((bore, size))
            continue
        if size is None:
            continue
        customs += 1
        nominal, pitch = thread_measure(CUSTOM_SIZE, chosen["diameter"], chosen["pitch"])
        near = standards.thread_size_near(nominal, pitch) or standards.tabulated_size(nominal)
        if near:
            hits.append((bore, near))
    assert customs > 0 and sized > 0, "ohne beide Fälle prüft die Abtastung nichts"
    assert loose == [], "eine gewählte Normgröße greift nicht"
    assert hits == [(1.41, "M1.6")], "nur die benannte M1.6-Kante"


@pytest.mark.parametrize(
    ("bore", "found"), [(1.2, False), (1.25, True), (993.4, True), (993.5, False)]
)
def test_a_custom_thread_at_a_bore_ends_at_the_shared_limits(bore: float, found: bool) -> None:
    """``custom_thread_for`` an der Kante: Ø 1,6 und Ø 1000 als Nennmaß (Review RM-532, R6).

    Die Bohrung ist der Gangfuß, Nennmaß = Bohrung + 1,1 · Steigung: 1,215 + 0,385
    = 1,6, 993,4 + 6,6 = 1000.
    """
    from app.core.knowledge.parts.fasteners import custom_thread_for

    assert (custom_thread_for(bore) is not None) is found


# --- Zoll- und Rohrgewinde (RM-544) -----------------------------------------------


def _common_volume(first: object, second: object) -> float:
    """Das gemeinsame Volumen zweier Körper — am Netz über die Kette, exakt über OCCT."""
    from app.core.geom.boolean import boolean
    from app.core.geom.mesh import MeshData

    if isinstance(first, MeshData):
        return float(
            boolean("intersection", [first, second], allow_empty=True).mesh.volume  # type: ignore[list-item]
        )
    from app.core.brep import edit

    return float(edit.boolean("intersection", [first, second]).volume)


def _nut_and_bolt(
    values: dict[str, object],
    *,
    bolt_length: float,
    nut_length: float,
    shift: float,
    kernel: str = "mesh",
    play: float = 0.2,
) -> tuple[float, float, float]:
    """Mutter aus dem Innengewinde und der Bolzen darin — gemeinsames Volumen in und außer Phase.

    Das Werkzeug des Innengewindes liegt unter seiner Mündung bei null und schneidet
    eine Mutter aus einem Zylinder; der Bolzen rückt um ``shift`` hinein. Beide Gänge
    beginnen an ihrem unteren Ende bei Winkel null, also liegen sie in Phase, wo
    ``shift`` und ``-nut_length`` um ganze Steigungen auseinander liegen. Zurück:
    Überdeckung in Phase, Überdeckung eine halbe Steigung daneben, Fläche der Mutter
    als Maßstab der Toleranz.
    """
    from app.core.knowledge.parts import shapes
    from app.core.knowledge.parts.build import subtract
    from app.core.knowledge.parts.fasteners import thread_of

    dims = thread_of(ThreadParams(**values))  # type: ignore[arg-type]
    with shapes.building(kernel):  # type: ignore[arg-type]
        bolt = printed_thread(
            ThreadParams(**values, length=bolt_length, internal=False, play=play)  # type: ignore[arg-type]
        ).mesh
        tool = printed_thread(
            ThreadParams(**values, length=nut_length, internal=True, play=play)  # type: ignore[arg-type]
        ).mesh
        block = shapes.moved(shapes.cylinder(dims.nominal + 12.0, nut_length), (0, 0, -nut_length))
        nut = subtract(block, tool)
        inside = _common_volume(nut, shapes.moved(bolt, (0.0, 0.0, shift)))
        beside = _common_volume(nut, shapes.moved(bolt, (0.0, 0.0, shift + dims.pitch / 2.0)))
    area = float(as_mesh_data(nut).raw.area) if kernel == "mesh" else 0.0
    return inside, beside, area


@pytest.mark.parametrize("kernel", ["mesh", "brep"])
def test_a_g_half_inch_pair_interlocks_at_both_kernels(kernel: str) -> None:
    """Abnahme RM-544: Innen- und Außengewinde G 1/2 greifen, am Netz und exakt.

    In Phase überdecken sie sich nicht — der Bolzen dreht durch die Mutter —, und
    eine halbe Steigung daneben stecken die Gänge ineinander: Sie greifen, statt
    aneinander vorbeizurutschen.
    """
    from app.core.units import EPS_GEOM

    if kernel == "brep":
        from tests.helpers import exact_kernel

        exact_kernel()
    pitch = 25.4 / 14.0
    length = 6.0 * pitch
    inside, beside, area = _nut_and_bolt(
        {"size": "G1/2"}, bolt_length=length, nut_length=length, shift=-length, kernel=kernel
    )
    tolerance = EPS_GEOM * area if kernel == "mesh" else 1e-6
    assert inside <= tolerance, f"G 1/2 überdeckt sich in Phase um {inside} mm³"
    assert beside > 10.0, f"eine halbe Steigung daneben nur {beside} mm³ — die Gänge greifen nicht"


def test_the_whitworth_profile_has_the_measures_of_iso_228() -> None:
    """Abnahme RM-544: G 1/2 nach ISO 228-1 — Kern, Flanken, Kamm.

    Außen ohne Spiel liegt der Kamm auf d = 20,955, der Grund auf d1 = 18,631; auf
    dem Flankendurchmesser d2 = 19,793 ist der Gang eine halbe Steigung breit, die
    Flanken stehen 55° zueinander, und der Kamm ist ein Bogen mit r = 0,137329·P.
    Die Sollwerte sind die der Norm als Zahl, nicht aus ``standards`` gelesen.
    """
    from app.core.knowledge.parts.shapes import ridge_profile

    pitch = 25.4 / 14.0
    outline = ridge_profile(20.955, pitch, profile="whitworth")
    radii = [radial for radial, _axial in outline]
    assert 2.0 * max(radii) == pytest.approx(20.955, abs=0.001)
    assert 2.0 * min(radii) == pytest.approx(18.631, abs=0.001)
    # Breite auf dem Flankendurchmesser: die zwei Flanken dort geschnitten.
    pitch_radius = 19.793 / 2.0
    crossings = []
    for (r_a, z_a), (r_b, z_b) in itertools.pairwise(outline):
        if (r_a - pitch_radius) * (r_b - pitch_radius) < 0.0:
            crossings.append(z_a + (pitch_radius - r_a) * (z_b - z_a) / (r_b - r_a))
    assert len(crossings) == 2
    assert crossings[1] - crossings[0] == pytest.approx(pitch / 2.0, abs=0.002)
    # Die Flanken: die längste Strecke je Seite steht 27,5° gegen die Senkrechte.
    segments = list(itertools.pairwise(outline))
    longest = sorted(segments, key=lambda s: -math.dist(s[0], s[1]))[:2]
    for (r_a, z_a), (r_b, z_b) in longest:
        assert math.degrees(math.atan2(abs(z_b - z_a), abs(r_b - r_a))) == pytest.approx(
            27.5, abs=0.01
        )
    # Der Kamm: der Kreis durch drei Kammpunkte hat r = 0,137329·P.
    top = sorted(outline, key=lambda point: -point[0])[:3]
    (x1, y1), (x2, y2), (x3, y3) = ((z, r) for r, z in top)
    d = 2.0 * (x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2))
    ux = (
        (x1**2 + y1**2) * (y2 - y3) + (x2**2 + y2**2) * (y3 - y1) + (x3**2 + y3**2) * (y1 - y2)
    ) / d
    uy = (
        (x1**2 + y1**2) * (x3 - x2) + (x2**2 + y2**2) * (x1 - x3) + (x3**2 + y3**2) * (x2 - x1)
    ) / d
    assert math.hypot(x1 - ux, y1 - uy) == pytest.approx(0.137329 * pitch, rel=0.01)


def test_a_built_g_half_inch_thread_keeps_its_core_measures() -> None:
    """Gebaut statt gezeichnet: Kamm und Grund des Bolzens G 1/2 ohne Spiel am Netz."""
    male, female = _part_pair_radii("G1/2")
    assert 2.0 * male[1] == pytest.approx(20.955, abs=0.01)
    assert 2.0 * male[0] == pytest.approx(18.631, abs=0.02)
    # Das Werkzeug der Mutter beginnt am Grund und reicht bis zum Nennmaß.
    assert 2.0 * female[0] == pytest.approx(18.631, abs=0.05)
    assert 2.0 * female[1] == pytest.approx(20.955, abs=0.01)


def _part_pair_radii(size: str) -> tuple[tuple[float, float], tuple[float, float]]:
    male = printed_thread(ThreadParams(size=size, length=12.0, internal=False, play=0.0))
    female = printed_thread(ThreadParams(size=size, length=12.0, internal=True, play=0.0))
    return radii(male.mesh), radii(female.mesh)


def test_unc_quarter_twenty_meets_asme_b1_1() -> None:
    """Abnahme RM-544: 1/4-20 UNC gegen ASME B1.1.

    Nennmaß 0,2500 Zoll, 20 Gänge je Zoll; das Grundprofil ist das metrische, und
    das gedruckte Profil ist es auch: Kamm auf dem Nennmaß, der Grund mit 1,1·P
    unter ihm und damit unter dem Kerndurchmesser der Mutter D1 = D − 1,082532·P
    = 0,1959 Zoll — eine Metallmutter stößt mit ihren Kämmen nicht auf.
    """
    from app.core.knowledge import standards

    entry = standards.thread_size("1/4-20 UNC")
    assert entry.nominal == pytest.approx(0.25 * 25.4)
    assert entry.pitch == pytest.approx(25.4 / 20.0)
    assert entry.profile == "flat"
    core, crest = _part_pair_radii("1/4-20 UNC")[0]
    assert 2.0 * crest == pytest.approx(6.35, abs=0.01)
    assert 2.0 * core < 0.1959 * 25.4
    # Der Netzkern reicht um ``BOOLEAN_OVERLAP`` über den Grund (``build.threaded``).
    assert 2.0 * core == pytest.approx(6.35 - 1.1 * 1.27, abs=0.025)
    # Basisflankendurchmesser E = D - 0,649519·P = 0,2175 Zoll (ASME B1.1, Tabelle 2A).
    assert pytest.approx(0.2175, abs=0.0001) == (0.25 - 0.649519 / 20.0)


@pytest.mark.parametrize("size", ["R1/2", "1/2-14 NPT"])
def test_a_tapered_pipe_pair_meets_at_its_gauge_plane(size: str) -> None:
    """Stufe 2: Ein kegeliges Außengewinde trifft das Innengewinde in der Bezugsebene.

    Außen liegt die Bezugsebene ``gauge`` vor der Spitze, innen an der Mündung.
    Der Bolzen steht auf seiner Fläche mit der Spitze nach oben; umgedreht und von
    Hand eingeschraubt, bis seine Bezugsebene in der Mündung liegt, steckt er
    ``gauge`` tief. Gedreht um die Achse — dieselbe Lage der Gänge wie beim
    Schrauben — gibt es eine Stellung ohne Überdeckung, und in einer anderen
    stecken die Gänge ineinander: Das Paar greift über die ganze Einschraubtiefe.
    """
    from app.core.geom.boolean import boolean
    from app.core.knowledge import standards
    from app.core.knowledge.parts import shapes
    from app.core.knowledge.parts.build import subtract
    from app.core.units import EPS_GEOM

    entry = standards.thread_size(size)
    bolt_length, nut_length = 12.0, 14.0
    bolt = printed_thread(
        ThreadParams(size=size, length=bolt_length, internal=False, play=0.2)
    ).mesh
    tool = printed_thread(ThreadParams(size=size, length=nut_length, internal=True, play=0.2)).mesh
    block = shapes.moved(shapes.cylinder(entry.nominal + 12.0, nut_length), (0, 0, -nut_length))
    nut = subtract(block, tool)
    # Umgedreht liegt die Bezugsebene bei -(Länge - gauge); in die Mündung gerückt.
    flipped = shapes.moved(
        shapes.turned(bolt, 180.0, (1.0, 0.0, 0.0)), (0.0, 0.0, bolt_length - entry.gauge)
    )
    common = [
        boolean(
            "intersection",
            [nut, shapes.turned(flipped, float(angle), (0.0, 0.0, 1.0))],  # type: ignore[list-item]
            allow_empty=True,
        ).mesh.volume
        for angle in range(0, 360, 10)
    ]
    area = float(as_mesh_data(nut).raw.area)
    assert min(common) <= EPS_GEOM * area, f"{size}: keine Stellung ohne Überdeckung, {common}"
    assert max(common) > 5.0, f"{size}: die Gänge greifen nicht ineinander, {common}"


def test_a_tapered_thread_narrows_towards_its_tip_and_its_mouth_is_widest() -> None:
    """R 1/2: außen zur Spitze enger, innen zur Tiefe — 1:16 auf den Durchmesser."""
    from app.core.knowledge.parts.fasteners import printed_thread as build

    male = as_mesh_data(build(ThreadParams(size="R1/2", length=16.0, play=0.0)).mesh)
    points = np.asarray(male.raw.vertices)
    radial = np.hypot(points[:, 0], points[:, 1])
    low = radial[points[:, 2] < 2.0].max()
    high = radial[points[:, 2] > 14.0].max()
    assert low - high == pytest.approx(14.0 / 32.0, abs=0.06), "außen 1:16 enger nach oben"
    hole = as_mesh_data(build(ThreadParams(size="R1/2", length=16.0, play=0.0, internal=True)).mesh)
    points = np.asarray(hole.raw.vertices)
    radial = np.hypot(points[:, 0], points[:, 1])
    mouth = radial[points[:, 2] > -2.0].max()
    deep = radial[points[:, 2] < -14.0].max()
    assert mouth > deep, "innen an der Mündung am weitesten"
    assert 2.0 * mouth == pytest.approx(20.955, abs=0.05), "an der Mündung das Nennmaß"


@pytest.mark.parametrize(
    "values",
    [
        {"size": "M10", "left_hand": True},
        {"size": "G1/2", "left_hand": True},
        {"size": "custom_size", "diameter": 24.0, "pitch": 2.0, "starts": 3},
        {"size": "custom_size", "diameter": 30.0, "form": "whitworth", "tpi": 11.0},
        {"size": "custom_size", "diameter": 30.0, "form": "unified", "tpi": 12.0, "starts": 2},
    ],
    ids=["M10-links", "G-links", "dreigaengig", "whitworth-eigen", "unified-zweigaengig"],
)
def test_left_hand_multi_start_and_own_inch_pairs_interlock(values: dict[str, object]) -> None:
    """Stufe 2 und das eigene Maß in Zoll: jedes Paar greift wie das metrische."""
    from app.core.knowledge.parts.fasteners import thread_of
    from app.core.units import EPS_GEOM

    pitch = thread_of(ThreadParams(**values)).pitch  # type: ignore[arg-type]
    length = 6.0 * pitch
    inside, beside, area = _nut_and_bolt(
        values, bolt_length=length, nut_length=length, shift=-length
    )
    assert inside <= EPS_GEOM * area, f"{values}: in Phase {inside} mm³"
    assert beside > 1.0, f"{values}: eine halbe Steigung daneben nur {beside} mm³"


def test_a_left_hand_bolt_does_not_fit_a_right_hand_nut() -> None:
    """Gegenprobe zum Linksgewinde: Es ist wirklich gespiegelt, nicht nur benannt."""
    from app.core.geom.boolean import boolean
    from app.core.knowledge.parts import shapes
    from app.core.knowledge.parts.build import subtract

    length = 6.0 * 1.5
    bolt = printed_thread(
        ThreadParams(size="M10", length=length, internal=False, play=0.2, left_hand=True)
    ).mesh
    tool = printed_thread(ThreadParams(size="M10", length=length, internal=True, play=0.2)).mesh
    block = shapes.moved(shapes.cylinder(22.0, length), (0.0, 0.0, -length))
    nut = subtract(block, tool)
    placed = shapes.moved(bolt, (0.0, 0.0, -length))
    common = boolean("intersection", [nut, placed], allow_empty=True).mesh  # type: ignore[list-item]
    assert common.volume > 5.0, "ein Linksbolzen ginge glatt in eine Rechtsmutter"


def _mirror_problem_at(spec_params: object, build: object, values: dict[str, object]) -> object:
    """Die Spiegelprüfung einer Ecke, wie der Bereichstest sie fährt (``range_check``)."""
    from app.core.knowledge.parts.range_check import _mirror_problem

    made = build(spec_params(**values))  # type: ignore[operator]
    return _mirror_problem(
        spec_params,  # type: ignore[arg-type]
        build,
        values,
        "left_hand",
        made,
        as_mesh_data(made.mesh),
    )


@pytest.mark.parametrize(
    "values",
    [
        {"size": "M6"},
        {"size": "G1/2", "length": 30.0},
        {"size": "R1/2", "length": 20.0, "internal": True},
        {"size": "1/4-20 UNC"},
    ],
    ids=["M6", "G1/2", "R1/2-innen", "UNC"],
)
def test_a_left_hand_thread_is_the_mirror_of_the_right_hand_one(values: dict[str, object]) -> None:
    """Was ``mirrored_by`` dem Bereichstest verspricht, am Baustein gemessen — je Ecke.

    G 1/2 trianguliert gespiegelt mit einer Ecke mehr; die Flächen liegen trotzdem
    aufeinander, und genau das prüft der Vergleich.
    """
    from app.core.knowledge.parts import PARTS

    for name in ("printed_thread", "printed_screw", "printed_nut", "threaded_rod"):
        assert PARTS.get(name).mirrored_by == "left_hand"
    spec = PARTS.get("printed_thread")
    assert _mirror_problem_at(spec.params, spec.fn, {**values, "play": 0.2}) is None


def test_the_mirror_check_finds_a_switch_that_does_more_than_mirror() -> None:
    """Gegenprobe zur Spiegelprüfung: Ein Schalter, der das Maß ändert, fällt auf."""

    def wrong(raw: ThreadParams) -> object:
        return printed_thread(
            ThreadParams(size="M8" if raw.left_hand else "M6", length=raw.length, play=raw.play)
        )

    assert _mirror_problem_at(ThreadParams, wrong, {"size": "M6"}) is not None


def test_the_mirror_check_finds_a_turn_that_keeps_volume_and_hull() -> None:
    """Gegenprobe: Ein um 180° gedrehtes Rechtsgewinde hat Volumen und Hülle des Spiegelbilds.

    Die Prüfung vor RM-544 verglich nur diese zwei Zahlen und hätte es als
    Linksgewinde durchgelassen; der Flächenvergleich sieht den falschen Drehsinn.
    """
    from app.core.knowledge.parts import shapes

    def turned(raw: ThreadParams) -> object:
        made = printed_thread(ThreadParams(size="M6", length=raw.length, play=raw.play))
        if not raw.left_hand:
            return made
        return dataclasses.replace(made, mesh=shapes.turned(made.mesh, 180.0, (0.0, 0.0, 1.0)))

    assert _mirror_problem_at(ThreadParams, turned, {"size": "M6"}) is not None


def _left_with_a_shifted_crest(shift: float) -> object:
    """Links das Spiegelbild, dessen äußerste Ecke um ``shift`` nach außen gerückt ist."""
    from app.core.geom.mesh import MeshData

    def build(raw: ThreadParams) -> object:
        made = printed_thread(ThreadParams(size="M6", length=raw.length, play=raw.play))
        if not raw.left_hand:
            return made
        body = as_mesh_data(made.mesh).raw.copy()
        points = np.asarray(body.vertices, dtype=np.float64) * np.array([1.0, -1.0, 1.0])
        radius = np.hypot(points[:, 0], points[:, 1])
        index = int(np.argmax(radius))
        points[index, :2] *= (radius[index] + shift) / radius[index]
        body.vertices = points
        body.faces = np.ascontiguousarray(np.asarray(body.faces)[:, ::-1])
        return dataclasses.replace(made, mesh=MeshData.of(body))

    return build


@pytest.mark.parametrize(("shift", "passes"), [(0.001, True), (0.01, False)])
def test_a_mirror_apart_by_less_than_the_print_limit_passes(shift: float, passes: bool) -> None:
    """Eine Naht, die die Vereinigung links anders auflöst, ist kein falscher Drehsinn.

    Am Bolzen Ø 1000 lag eine Ecke 0,32 µm neben der gespiegelten Fläche, bei 20-8 NPT
    0,019 µm, und die Schranke von 10⁻⁵ mm nannte beides einen Schalter, der mehr tut
    als spiegeln (Bereichsnachweis RM-544). Unter der Druckgrenze besteht es, darüber
    nicht.
    """
    from app.core.units import PRINT_LIMIT

    assert (shift < PRINT_LIMIT) is passes
    problem = _mirror_problem_at(ThreadParams, _left_with_a_shifted_crest(shift), {"size": "M6"})
    assert (problem is None) is passes, problem


def test_a_mirror_apart_under_the_print_limit_checks_itself(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Anders trianguliert folgt Dichtheit und Schnittfreiheit nicht mehr aus der Deckung.

    Die andere Stellung prüft sich dann selbst; eine Selbstdurchdringung dort ist ein Bruch.
    """
    from app.core.knowledge.parts import range_check

    asked: list[object] = []

    def crossing(mesh: object, cancelled: object = None) -> bool:
        asked.append(mesh)
        return True

    monkeypatch.setattr(range_check, "has_self_intersections", crossing)
    problem = _mirror_problem_at(ThreadParams, _left_with_a_shifted_crest(0.001), {"size": "M6"})
    assert problem is not None and len(asked) == 1


def test_a_tapered_stud_has_no_shank_facet_folded_into_itself() -> None:
    """Der Schaft fiel mit dem Kamm des Kegelgewindes zusammen (Bereichsnachweis RM-544).

    Bei 1/2-14 NPT, 150 mm lang mit 65 mm Gewinde je Ende, schnitten sich zwei
    Schaftdreiecke; am alten Stand rot. Der Schaft bleibt jetzt knapp unter dem Kamm.
    """
    from app.core.knowledge.parts.fasteners import ThreadedRodParams, threaded_rod
    from app.core.knowledge.parts.range_check import has_self_intersections

    params = ThreadedRodParams(size="1/2-14 NPT", length=150.0, thread_length=65.0, play=0.2)
    body = as_mesh_data(threaded_rod(params).mesh)
    assert body.is_watertight and not has_self_intersections(body)


def test_the_range_check_mirrors_every_corner_not_only_the_default() -> None:
    """Ein Schalter, der nur an einer Ecke mehr tut als spiegeln, fällt an genau dieser auf.

    Vorher baute der Bereichstest die andere Stellung nur an der Vorgabe des
    Bausteins; eine Ecke am Rand des Bereichs blieb ungeprüft.
    """
    from app.core.knowledge.parts import range_check
    from app.core.knowledge.profiles import make_profile
    from app.core.registry import op_params, param
    from app.core.types import BaseParams
    from app.i18n import _

    @op_params
    class SmallParams(BaseParams):
        length: float = param(title=_("Länge"), default=6.0, unit="mm", minimum=6.0, maximum=10.0)
        left_hand: bool = param(title=_("Linksgewinde"), default=False)

    def sometimes(raw: SmallParams) -> object:
        size = "M8" if raw.left_hand and raw.length > 9.0 else "M6"
        return printed_thread(
            ThreadParams(size=size, length=raw.length, left_hand=raw.left_hand, play=0.2)
        )

    report = range_check.check(
        SmallParams,
        sometimes,
        make_profile(),
        wall=range_check.WallRequirement.not_applicable("Gegenprobe der Spiegelprüfung."),
        mirrored_by="left_hand",
    )
    assert report.checked == 2
    broken = [failure.values for failure in report.failures]
    assert broken == [{"length": 10.0, "left_hand": False}]


def test_a_pipe_bore_is_recognised_as_its_pipe_thread() -> None:
    """Erkennung RM-544: Die Bohrung eines Rohrs mit 18,7 mm ist das Kernloch eines G 1/2.

    Metrisch passt dort nur ein eigenes Maß; die Normgröße ist vorgewählt, und der
    Satz über dem Dialog nennt das metrische Maß daneben. Wer die Reihe G
    ausblendet, bekommt sie nicht vorgeschlagen.
    """
    from app.core.knowledge import standards
    from app.core.knowledge.parts.fasteners import CUSTOM_SIZE, size_for_thread, thread_advice

    assert size_for_thread(18.7) == {"size": "G1/2", "internal": True}
    said = str(thread_advice(18.7))
    assert "G1/2" in said and "metrisch nur ein eigenes" in said, said
    before = standards.shown_thread_families()
    try:
        standards.set_shown_thread_families(("metric", "UNC", "UNF"))
        assert size_for_thread(18.7)["size"] == CUSTOM_SIZE
        assert "G1/2" not in str(thread_advice(18.7))
    finally:
        standards.set_shown_thread_families(before)


def test_a_bore_between_two_series_names_both_and_preselects_metric() -> None:
    """Regel 21 an der Bohrung: Passen Größen zweier Reihen, nennt der Satz beide.

    Eine M16 an ihrem gedruckten Gangfuß ist zugleich das Kernloch einer 5/8-11 UNC;
    vorgewählt bleibt die metrische Größe, wie vor RM-544, und die andere steht im Satz.
    """
    from app.core.knowledge.parts.fasteners import size_for_thread, thread_advice

    bore = 16.0 - 1.1 * 2.0 + 0.05
    chosen = size_for_thread(bore)
    said = str(thread_advice(bore))
    assert chosen["size"] == "M16"
    assert "M16" in said and "UNC" in said and "vorgewählt ist M16" in said, said


def test_only_metric_shown_keeps_the_old_preselection() -> None:
    """Mit metrisch allein in den Listen wählt die Bohrung wie vor RM-544."""
    from app.core.knowledge import standards
    from app.core.knowledge.parts.fasteners import CUSTOM_SIZE, size_for_thread

    before = standards.shown_thread_families()
    try:
        standards.set_shown_thread_families(("metric",))
        assert size_for_thread(6.5)["size"] == CUSTOM_SIZE
        assert size_for_thread(5.0)["size"] == "M6"
    finally:
        standards.set_shown_thread_families(before)


def test_an_empty_choice_of_series_shows_them_all() -> None:
    """Ohne Reihe gäbe es kein Gewinde; eine leere oder unbekannte Wahl zeigt alle."""
    from app.core.knowledge import standards

    before = standards.shown_thread_families()
    try:
        standards.set_shown_thread_families(())
        assert standards.shown_thread_families() == standards.THREAD_FAMILIES
        standards.set_shown_thread_families(("G", "Unsinn"))
        assert standards.shown_thread_families() == ("G",)
    finally:
        standards.set_shown_thread_families(before)


def test_a_thread_both_large_and_fine_is_refused_before_it_builds() -> None:
    """Groß, fein und lang zugleich wird das Netz unberechenbar groß — die Absage mit Weg.

    Seit den Gängen je Zoll ist das feine Ende eine Ecke des Bereichs: Ø 1000 mit
    101,6 Gängen je Zoll über 200 mm wären 192 000 Stationen ohne Abbruch.
    """
    from app.core.errors import ValidationError
    from app.core.knowledge.parts.fasteners import _thread_reason

    values = ThreadParams(
        size="custom_size", diameter=1000.0, form="whitworth", tpi=101.6, length=200.0
    )
    assert _thread_reason(values) is not None
    with pytest.raises(ValidationError) as caught:
        printed_thread(values)
    assert caught.value.constraint == "too_fine_for_its_size"
    assert caught.value.field == "length"
    # Dieselbe Größe mit den Gängen ihrer Reihe baut, und bis 72 mm auch so fein.
    assert _thread_reason(ThreadParams(size="custom_size", diameter=1000.0, length=200.0)) is None
    assert (
        _thread_reason(
            ThreadParams(
                size="custom_size", diameter=1000.0, form="whitworth", tpi=101.6, length=72.0
            )
        )
        is None
    )


def test_the_mesh_budget_takes_no_flat_thread_away() -> None:
    """Was vor RM-544 baute, baut weiter: Ø 1000 metrisch mit der feinsten Steigung über 200 mm.

    Das Netzbudget kam mit dem Whitworth-Profil und seinen elf Punkten je Station.
    In seiner ersten Fassung (2 hoch 16 Stationen) lehnte es auch flache Gewinde ab,
    die vorher gebaut wurden — Ø 100 unter 0,3 mm Steigung über 200 mm. Das Budget
    ist jetzt das größte flache Gewinde, das es gab.
    """
    from app.core.knowledge.parts.fasteners import (
        LONGEST_PRINTED_THREAD,
        PrintedScrewParams,
        ThreadedRodParams,
        _fastener_reason,
        _rod_reason,
        _thread_reason,
    )
    from app.core.units import FINEST_PITCH, LARGEST_THREAD

    widest = {"size": "custom_size", "diameter": LARGEST_THREAD, "pitch": FINEST_PITCH}
    longest = LONGEST_PRINTED_THREAD
    assert _thread_reason(ThreadParams(**widest, length=longest)) is None
    assert _thread_reason(ThreadParams(**widest, length=longest, internal=True)) is None
    assert _fastener_reason(PrintedScrewParams(**widest, length=longest)) is None
    assert _rod_reason(ThreadedRodParams(**widest, length=longest)) is None
    # Unified hat dasselbe flache Profil: 101,6 Gänge je Zoll sind 0,25 mm.
    assert (
        _thread_reason(
            ThreadParams(
                size="custom_size",
                diameter=LARGEST_THREAD,
                form="unified",
                tpi=101.6,
                length=longest,
            )
        )
        is None
    )


def test_a_deep_tapered_internal_thread_is_refused_at_its_length() -> None:
    """R 1/16 innen über 200 mm würde in der Tiefe enger als jeder Kern: Absage an der Länge."""
    from app.core.errors import ValidationError

    with pytest.raises(ValidationError) as caught:
        printed_thread(ThreadParams(size="R1/16", length=200.0, internal=True))
    assert caught.value.field == "length"
    assert caught.value.constraint == "taper_too_deep"


def test_an_own_inch_thread_at_a_bore_takes_the_series_of_its_form() -> None:
    """Das eigene Maß in Whitworth- oder Unified-Form, dessen Kernloch die Bohrung ist."""
    from app.core.knowledge.parts.fasteners import custom_thread_for
    from app.core.knowledge.parts.shapes import NPT_DEPTH, RIDGE_SHARE, WHITWORTH_DEPTH

    nominal, pitch = custom_thread_for(40.0, "whitworth")  # type: ignore[misc]
    assert pitch == pytest.approx(25.4 / 11.0), "die Reihe G hat ab G 1 elf Gänge je Zoll"
    assert nominal - 2.0 * WHITWORTH_DEPTH * pitch == pytest.approx(40.0)
    nominal, pitch = custom_thread_for(40.0, "unified")  # type: ignore[misc]
    assert pitch == pytest.approx(25.4 / 5.0), "die Reihe UNC hat bei Ø 44,45 fünf Gänge je Zoll"
    assert nominal - 2.0 * RIDGE_SHARE * pitch == pytest.approx(40.0)
    assert pytest.approx(0.640327, abs=1e-6) == WHITWORTH_DEPTH
    assert pytest.approx(0.8) == NPT_DEPTH


@pytest.mark.parametrize(
    ("values", "pitch", "handedness"),
    [
        ({"diameter": 20.955, "form": "whitworth", "tpi": 14.0}, 25.4 / 14.0, "right"),
        ({"diameter": 6.35, "form": "unified", "tpi": 0.0}, 25.4 / 20.0, "right"),
        ({"diameter": 10.0, "pitch": 1.5, "starts": 2, "left_hand": True}, 1.5, "left"),
    ],
    ids=["whitworth", "unc-automatisch", "zweigaengig-links"],
)
def test_create_screw_takes_inch_forms_starts_and_left_hand(
    values: dict[str, object], pitch: float, handedness: str
) -> None:
    """*Schraube erstellen* (RM-544): Gänge je Zoll, Whitworth-Profil, Gangzahl, Linksgewinde.

    Null Gänge je Zoll nimmt die Reihe der Gewindeform — Ø 6,35 Unified ist 1/4-20 UNC.
    Der Körper ist geschlossen, und das Merkmal nennt, was gebaut ist.
    """
    from tests.helpers import exact_kernel

    exact_kernel()
    from app.core.bootstrap import load_operations
    from app.core.registry import REGISTRY
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene

    load_operations()
    spec = REGISTRY.get("thread_exact")
    result = spec.fn(
        OpContext(
            scene=Scene(objects={}),
            inputs=[],
            params=spec.params(length=10.0, **values),
            profile=None,
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )
    (body,) = result.outputs
    assert body.mesh.is_closed and body.mesh.solid_count == 1
    (thread,) = [entry for entry in body.features.values() if entry.kind == "thread"]
    assert thread.params["pitch"] == pytest.approx(pitch)
    assert thread.params["handedness"] == handedness
    assert int(thread.params.get("starts", 1)) == int(values.get("starts", 1))  # type: ignore[call-overload]
