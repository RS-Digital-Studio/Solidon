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
            if bore > _gripped_up_to(standards.screw(size)):
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
