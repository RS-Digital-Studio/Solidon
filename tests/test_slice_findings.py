"""Was die Schichtanalyse aus einem Körper schließt — gegen Körper, deren
Zahlen sich ausrechnen lassen (§22.2, §40).

Jeder Fall hier stand einmal falsch im Bericht: eine Rippe, die in keiner Zahl
vorkam; eine Brücke über einem tragenden Stiel; eine Stützsäule, die auf dem
Modell endet und als „erreicht das Bett" gemeldet wurde.
"""

from __future__ import annotations

import math
from dataclasses import replace

import pytest
import trimesh
from shapely.geometry import Point, box
from shapely.geometry import Polygon as ShapelyPolygon
from shapely.geometry.base import BaseGeometry
from shapely.ops import unary_union

from app.core.geom.mesh import MeshData
from app.core.geom.transform import place_on_bed
from app.core.knowledge import print_settings, profiles
from app.core.slice import advise
from app.core.slice.analysis import (
    OVERHANG_LAYER_WORTH_SUPPORT,
    OVERHANG_WORTH_SUPPORT,
    SPAN_INTERESTING,
    WIDTH_INTERESTING,
    channel_space,
    largest_sloped_patch,
    ledge_space,
    ledges,
    minimum_width,
    model_support,
    narrowest,
    piece_area,
    slice_body,
    spanning_width,
    support_on_model,
    tip_islands,
    worth_support,
)
from app.core.types import PrintSettings, Profile, SettingAdvice, SliceResult

#: Die Bahnbreite der Vorgabe: Zuschlag und Mindestbreite des Kanalraums.
LINE = print_settings.resolve(profiles.make_profile()).layers.line_width


def on_bed(*parts: trimesh.Trimesh) -> MeshData:
    body = parts[0] if len(parts) == 1 else trimesh.boolean.union(list(parts))
    return place_on_bed(MeshData.of(body))


def brick(x: float, y: float, z: float, at: tuple[float, float, float]) -> trimesh.Trimesh:
    body: trimesh.Trimesh = trimesh.creation.box(extents=(x, y, z))
    body.apply_translation(at)
    return body


def petg() -> Profile:
    return profiles.make_profile("centauri-carbon-2", "petg")


# --- Die kleinste Strukturbreite ist die kleinste, nicht die größte -------------


def ribbed_plate() -> MeshData:
    """Eine Platte 20 auf 20 auf 5 mit einer 0,3 mm dünnen Rippe daran.

    Der Querschnitt ist ein Quadrat von 20 mm mit einem Fortsatz von 0,3 auf
    10 mm — die dünnste Struktur des Körpers misst also 0,3 mm, und genau das
    soll dastehen.
    """
    return on_bed(
        brick(20.0, 20.0, 5.0, (0.0, 0.0, 2.5)),
        brick(11.0, 0.3, 5.0, (14.5, 0.0, 2.5)),
    )


def test_a_thin_rib_beside_a_thick_plate_is_the_measured_width() -> None:
    """Gemessen wurde der größte einbeschriebene Kreis statt der dünnsten
    Stelle.

    ``shape.buffer(-r).is_empty`` wird erst wahr, wenn auch die **dickste**
    Stelle weg ist. Die Platte meldete damit die Berichtsgrenze von 2,0 mm —
    die Rippe, um die es geht, kam in keiner Zahl vor.
    """
    result = slice_body(ribbed_plate(), 0.5)

    assert narrowest(result) == pytest.approx(0.3, abs=0.05)
    assert narrowest(result) < WIDTH_INTERESTING, "der Deckel ist keine Messung"


def test_the_same_plate_without_the_rib_stays_thick() -> None:
    """Die Gegenprobe: Ohne Rippe ist an der Platte nichts dünn, und dann steht
    die Berichtsgrenze da — so wie vorher.
    """
    result = slice_body(on_bed(brick(20.0, 20.0, 5.0, (0.0, 0.0, 2.5))), 0.5)

    assert narrowest(result) == pytest.approx(WIDTH_INTERESTING)


def test_the_rib_reaches_the_report() -> None:
    """Unter der angesetzten Mindestbahnbreite steht ein Hinweis zur Prüfung."""
    profile = petg()
    settings = print_settings.resolve(profile)
    result = slice_body(ribbed_plate(), 0.5)

    codes = {entry.code for entry in advise.warnings_for(settings, profile, result)}

    assert "settings.wall_below_nozzle" in codes


def test_a_convex_body_measures_exactly_as_before() -> None:
    """Bei einer konvexen Form ist die Öffnung die Identität, bis die Erosion
    sie ganz auflöst — die neue Rechnung gibt dort dieselbe alte Antwort.
    """
    assert minimum_width(box(0.0, 0.0, 10.0, 0.6)) == pytest.approx(0.6, rel=0.05)
    assert minimum_width(box(0.0, 0.0, 40.0, 30.0), interesting_below=0.0) == pytest.approx(
        30.0, rel=0.05
    )


# --- Die Klammer der Spannweitensuche muss tragen -------------------------------


def keyhole() -> BaseGeometry:
    """Eine Öffnung Ø 40 mit einem 0,2 mm schmalen Schlitz daran.

    Der Schlitz treibt den Umfang hoch, ohne Fläche zu bringen: ``2A/L`` fällt
    von 20 auf 7,8 und liegt damit **unter** dem gesuchten Radius. Zu
    überbrücken sind trotzdem 40 mm — ein Ausläufer von zwei Zehnteln macht
    keine Öffnung leichter.
    """
    return unary_union([Point(0.0, 0.0).buffer(20.0, quad_segs=64), box(0.0, -0.1, 100.0, 0.1)])


def test_a_slotted_opening_is_still_measured_across() -> None:
    """Die Klammer ``2A/L`` ist nur bei konvexen Formen eine obere Schranke.

    Fiel sie darunter, lief die Halbierung bis an ihren eigenen Anfang und
    meldete ihn: 17,5 mm statt 40 — und die Warnung über die Brücke blieb aus.
    """
    shape = keyhole()
    coarse = 2.0 * float(shape.area) / float(shape.length)

    assert coarse < 20.0, "sonst trägt die alte Klammer und der Fall prüft nichts"
    assert spanning_width(shape) == pytest.approx(40.0, rel=0.05)


def test_a_plain_disc_is_unchanged() -> None:
    """Die Gegenprobe ohne Schlitz: dort trug die Klammer schon immer."""
    assert spanning_width(Point(0.0, 0.0).buffer(20.0, quad_segs=64)) == pytest.approx(
        40.0, rel=0.05
    )


# --- Ein Ring über Material ist keine Öffnung ----------------------------------


def test_a_mushroom_on_a_solid_stem_spans_nothing() -> None:
    """Gezählt wurde jedes Loch der ungestützten Fläche — auch eines, unter dem
    massives Material steht.

    Ein Pilz mit tragendem Stiel (Hut 100 auf 100, Stiel 30 auf 30) meldete
    eine Brücke von 29,7 mm über genau dem Stiel, der sie trägt.
    """
    body = on_bed(
        brick(30.0, 30.0, 20.0, (0.0, 0.0, 10.0)),
        brick(100.0, 100.0, 5.0, (0.0, 0.0, 22.5)),
    )

    result = slice_body(body, 0.5)

    assert max(layer.bridge_width for layer in result.layers) == pytest.approx(0.0, abs=0.5)
    assert "slice.long_bridge" not in {
        entry.code for entry in advise.warnings_for(print_settings.resolve(petg()), petg(), result)
    }


def test_a_shoulder_over_a_real_hollow_still_speaks() -> None:
    """Die Gegenprobe, damit der Filter nicht alles verschluckt: Über einem
    offenen Becher hängt die Bahn wirklich frei.
    """
    outer = trimesh.creation.cylinder(radius=20.0, height=40.0, sections=64)
    outer.apply_translation((0.0, 0.0, 20.0))
    wide = trimesh.creation.cylinder(radius=16.0, height=20.0, sections=64)
    wide.apply_translation((0.0, 0.0, 12.0))
    narrow = trimesh.creation.cylinder(radius=10.0, height=22.0, sections=64)
    narrow.apply_translation((0.0, 0.0, 31.0))
    body = MeshData.of(trimesh.boolean.difference([outer, wide, narrow]))

    result = slice_body(body, 0.2)

    assert max(layer.bridge_width for layer in result.layers) == pytest.approx(20.0, rel=0.1)


# --- Stützen enden nicht überall auf dem Bett ----------------------------------


def table() -> MeshData:
    """Bodenplatte 40 auf 40, darauf eine Säule 10 auf 10, darauf eine Platte.

    Keine Insel, 1 500 mm² Überhang auf einer Schicht — und jede Stütze
    darunter endet auf der Bodenplatte, nicht auf dem Bett.
    """
    return on_bed(
        brick(40.0, 40.0, 5.0, (0.0, 0.0, 2.5)),
        brick(10.0, 10.0, 20.0, (0.0, 0.0, 15.0)),
        brick(40.0, 40.0, 5.0, (0.0, 0.0, 27.5)),
    )


def bracket() -> MeshData:
    """Ein Kragarm: eine Wand vom Bett hoch, oben eine Platte quer darauf.

    Derselbe Überhang, aber unter ihm steht nichts — die Stütze reicht bis auf
    die Platte.
    """
    return on_bed(
        brick(10.0, 40.0, 30.0, (0.0, 0.0, 15.0)),
        brick(40.0, 40.0, 5.0, (0.0, 0.0, 32.5)),
    )


def test_a_column_that_lands_on_the_model_is_seen() -> None:
    result = slice_body(table(), 0.5)

    assert not result.layers[0].islands, "der Tisch hat keine Insel — das war der Trugschluss"
    assert support_on_model(result), "die Säule endet auf der Bodenplatte"


def test_a_cantilever_reaches_the_bed() -> None:
    result = slice_body(bracket(), 0.5)

    assert not support_on_model(result)


def placement_advice(body: MeshData) -> str | None:
    settings = print_settings.resolve(petg())
    entries = advise.advise(settings, petg(), slice_body(body, 0.5))
    for entry in entries:
        if entry.path == "support.placement":
            return str(entry.value)
    return None


def test_the_table_keeps_supports_everywhere() -> None:
    """Der Vorschlag ``build_plate`` ließ die Tischplatte absacken: Er wurde aus
    „keine Insel" geschlossen, und das ist etwas anderes als „alles erreicht
    das Bett".
    """
    assert placement_advice(table()) is None, "everywhere bleibt stehen"


def test_the_cantilever_may_stay_on_the_plate() -> None:
    """Die Gegenprobe, sonst wäre die Regel nur abgeschaltet."""
    assert placement_advice(bracket()) == "build_plate"


def beam_over_a_plate() -> MeshData:
    """Ein Balken 30 auf 4 über zwei Pfosten, 22 mm frei über einer Bodenplatte.

    Die Decke ist schmal — 88 mm², unter den Flächengrenzen —, verlangt die
    Stütze also allein über die Brückenregel; ihre Säule endet auf der
    Bodenplatte. Die Wand weit dahinter macht den Raum unter dem Balken
    weiter als einen Kanal (``CHANNEL_WIDTH``), wie am Wedge-Lock.
    """
    return on_bed(
        brick(50.0, 70.0, 2.0, (25.0, 35.0, 1.0)),
        brick(4.0, 4.0, 8.0, (12.0, 25.0, 6.0)),
        brick(4.0, 4.0, 8.0, (38.0, 25.0, 6.0)),
        brick(30.0, 4.0, 2.0, (25.0, 25.0, 11.0)),
        brick(50.0, 10.0, 10.0, (25.0, 65.0, 7.0)),
    )


def test_a_long_bridge_over_the_model_lets_its_supports_start_there() -> None:
    """Stützen nötig wegen einer Brücke, aber „nur vom Bett“ dazu: Das hob sich auf.

    Am Wedge-Lock (``F:\\3D Dateien``, 04.10.2026) verlangte die Brückenregel
    Stützen für eine Decke von 25,7 mm, deren Säule auf dem Modell endet, und
    weil die Decke unter den Flächengrenzen blieb, schlug derselbe Rat „nur vom
    Bett“ vor. Creality Print und Kobra 2 stützen mit „normal(auto)“ dann gar
    nichts mehr (0,0 m statt 2,9 m im G-Code), Elegoos Bäume nur noch die
    Hälfte. Was gestützt werden muss, muss die Stütze auch erreichen.
    """
    result = slice_body(beam_over_a_plate(), 0.2)
    need = advise.support_need(result)
    assert need.needed, "die Brücke von 22 mm verlangt Stützen"
    assert need.patch < OVERHANG_LAYER_WORTH_SUPPORT, "allein über die Brückenregel"
    assert not need.model.channels, "der Raum unter dem Balken ist kein Kanal"

    assert placement_advice(beam_over_a_plate()) is None, "everywhere bleibt stehen"
    settings = print_settings.with_path(print_settings.resolve(petg()), "support.style", "auto")
    settings = print_settings.with_path(settings, "support.placement", "build_plate")
    changed = advise.apply(settings, advise.advise(settings, petg(), result))
    assert changed.support.placement == "everywhere"


def tunnel_beside_a_ledge() -> MeshData:
    """Der Tunnel aus :func:`tunnel_block` (20 mm, Decke auf 28 mm) und außen
    auf derselben Höhe ein Sims 4 auf 4 mm über einer Stufe des Modells.

    Die Tunneldecke ist eine Brücke von 20 mm, aber eine Kanaldecke; der Sims
    setzt außerhalb eines Kanals auf dem Modell auf, ist aber keine Brücke.
    """
    return on_bed(
        trimesh.boolean.difference(
            [
                brick(60.0, 40.0, 40.0, (0.0, 0.0, 20.0)),
                brick(20.0, 50.0, 20.0, (0.0, 0.0, 18.0)),
            ]
        ),
        brick(40.0, 40.0, 5.0, (50.0, 0.0, 37.5)),
        brick(20.0, 40.0, 10.0, (-40.0, 0.0, 5.0)),
        brick(4.0, 4.0, 2.0, (-32.0, 0.0, 29.0)),
    )


def test_a_long_bridge_counts_on_the_model_only_where_it_hangs_there() -> None:
    """Die Brücke muss selbst über dem Modell hängen, nicht nur ihre Schicht.

    An der Waschschüssel (04.10.2026, Cura-Raster) lag auf der Schicht der
    Kanaldecke (17,3 mm) ein offenes Stück von 9,9 mm² neben dem Gewölbe; der
    Rat schaltete „überall“ ein, und Cura stellte trotz Kanalsperre eine
    Stützsäule von 42 mm in den Kanal (4,1 m Bahn, vorher keine).
    """
    result = slice_body(tunnel_beside_a_ledge(), 0.5)
    need = advise.support_need(result)
    ceiling = next(
        index for index, layer in enumerate(result.layers) if layer.bridge_width > SPAN_INTERESTING
    )
    assert any(index == ceiling for index, _number in need.model.channels), "die Decke ist Kanal"
    assert any(index == ceiling for index, _number in need.model.open_pieces), (
        "der Sims hängt auf derselben Schicht außen über dem Modell"
    )
    assert need.model.open_area < OVERHANG_WORTH_SUPPORT, "der Sims ist klein"

    assert placement_advice(tunnel_beside_a_ledge()) == "build_plate"
    assert placement_advice(beam_over_a_plate()) is None, "die Brücke über dem Modell zählt"


# --- Eine Decke im Kanal verlangt keine Stütze auf dem Modell -------------------


def tunnel_block(width: float) -> MeshData:
    """Ein Block, quer hindurch ein Tunnel von ``width`` mal 20 mm, offen an
    beiden Enden, und oben eine Kragplatte 40 auf 40 über das Bett hinaus.

    Die Kragplatte braucht Stützen, und die erreichen das Bett. Die
    Tunneldecke hängt über dem Tunnelboden — über Modellmaterial.
    """
    block = brick(width + 40.0, 40.0, 40.0, (0.0, 0.0, 20.0))
    tunnel = brick(width, 50.0, 20.0, (0.0, 0.0, 18.0))
    arm = brick(40.0, 40.0, 5.0, (width / 2.0 + 40.0, 0.0, 37.5))
    body = trimesh.boolean.union([trimesh.boolean.difference([block, tunnel]), arm])
    return place_on_bed(MeshData.of(body))


def test_a_ceiling_in_a_narrow_tunnel_is_a_channel() -> None:
    """Die Waschschüssel (25.09.2026): Mit „Stützen überall" füllte der
    Slicer ihren Wasserkanal mit Stütze, die niemand mehr herausbekommt. Die
    Decke eines schmalen Kanals schließt sich selbst.
    """
    model = model_support(slice_body(tunnel_block(20.0), 0.5))

    assert model.channels, "die Tunneldecke steht über dem Tunnelboden"
    assert model.open_patch == pytest.approx(0.0), "außen setzt nichts auf dem Modell auf"
    assert model.channel_at is not None
    assert model.channel_at[2] == pytest.approx(28.0, abs=0.5), "der Ort ist die Decke"


def test_a_wide_tunnel_is_no_channel() -> None:
    """Die Gegenprobe: 65 mm überbrückt keine Decke, und die Stütze darunter
    ist erreichbar."""
    model = model_support(slice_body(tunnel_block(65.0), 0.5))

    assert not model.channels
    assert model.open_patch > 1000.0


def tunnels_side_by_side(count: int) -> MeshData:
    """Ein Block mit ``count`` Tunneln zu je 10 auf 20 mm nebeneinander —
    ``count`` Kanaldecken auf derselben Schicht."""
    block = brick(20.0 * count + 10.0, 40.0, 30.0, (0.0, 0.0, 15.0))
    first = -10.0 * (count - 1)
    tunnels = [brick(10.0, 50.0, 20.0, (first + 20.0 * index, 0.0, 12.0)) for index in range(count)]
    return place_on_bed(MeshData.of(trimesh.boolean.difference([block, *tunnels])))


def test_the_channel_question_is_asked_once_per_layer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Je Säule gefragt, kostete die Kanalfrage am Eiffelturm aus dem Korpus
    (14 755 Säulen) eine halbe Stunde; je Schicht gefragt 1,9 s. Fünf
    Tunneldecken auf einer Schicht sind eine Frage mit fünf Punkten."""
    from app.core.slice import analysis

    asked: list[int] = []
    real = analysis._in_channels

    def counting(shape: BaseGeometry, points: list[Point], width: float) -> list[bool]:
        asked.append(len(points))
        return real(shape, points, width)

    monkeypatch.setattr(analysis, "_in_channels", counting)
    model = model_support(slice_body(tunnels_side_by_side(5), 0.5))

    assert len(model.channels) == 5, "jede Tunneldecke ist ein Kanal"
    assert asked == [5]


def cellar() -> MeshData:
    """Eine Decke 66 auf 66 mm, am Rand gehalten, 3 mm über einem Gitter aus
    Wänden, die nach unten breiter werden. Ihre Säule zerfällt beim Absinken
    in Zellen, und jede Zelle schrumpft über viele Schichten — ein Stück, das
    in mehreren Teilen zugleich Fläche verliert."""
    from shapely.geometry import Polygon as ShapelyPolygon

    parts = [brick(66.0, 66.0, 2.0, (0.0, 0.0, 1.0)), brick(66.0, 66.0, 3.0, (0.0, 0.0, 21.5))]
    for size, at in (
        ((3.0, 66.0), (-31.5, 0.0)),
        ((3.0, 66.0), (31.5, 0.0)),
        ((66.0, 3.0), (0.0, -31.5)),
        ((66.0, 3.0), (0.0, 31.5)),
    ):
        parts.append(brick(*size, 20.0, (*at, 11.0)))
    for index in range(4):
        x = -22.5 + 15.0 * index
        profile = ShapelyPolygon(
            [(x - 3.1, 2.0), (x + 2.9, 2.0), (x + 0.55, 17.0), (x - 0.65, 17.0)]
        )
        wall = trimesh.creation.extrude_polygon(profile, 60.0)
        wall.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2.0, (1, 0, 0)))
        wall.apply_translation((0.0, 30.0, 0.0))
        across = wall.copy()
        across.apply_transform(
            trimesh.transformations.rotation_matrix(math.pi / 2.0 + 0.013, (0, 0, 1))
        )
        parts += [wall, across]
    return place_on_bed(MeshData.of(trimesh.boolean.union(parts)))


def test_the_columns_come_out_the_same_on_any_number_of_workers(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Die Säulen verteilen sich auf Arbeiter, und ihre Zahl hängt an der
    Maschine. Das Ergebnis darf es nicht (RM-187). Der räumliche Baum liefert
    seine Treffer in seiner eigenen Folge, die an den übrigen Stücken der
    Gruppe hängt; ungeordnet summierten sich die Flächen eines zerfallenden
    Stücks in anderer Folge — am Eiffelturm aus dem Korpus je nach Gruppe
    um 3·10⁻¹⁴ mm² anders, hier mit umgekehrtem Baum um 3·10⁻¹² mm²."""
    import shapely

    from app.core.slice import analysis

    result = slice_body(cellar(), 0.25)
    assert len(result.layers) >= analysis.PARALLEL_FROM, "sonst liefe nur ein Arbeiter"
    answers = []
    for workers in (1, 2, 6):
        monkeypatch.setattr(analysis, "SUPPORT_WORKERS", workers)
        answers.append(analysis._model_support(result, analysis.CHANNEL_WIDTH, None))
    tree_order = shapely.STRtree.query
    monkeypatch.setattr(
        shapely.STRtree,
        "query",
        lambda tree, *args, **kwargs: tree_order(tree, *args, **kwargs)[::-1],
    )
    answers.append(analysis._model_support(result, analysis.CHANNEL_WIDTH, None))

    assert answers[0].open_area > 1000.0, "die Säule setzt auf den Wänden auf"
    assert answers[1:] == [answers[0]] * 3


def test_a_channel_ceiling_leaves_the_supports_on_the_plate() -> None:
    """Vorher blieb „überall" stehen, weil eine Säule auf dem Modell endet —
    in der Tunneldecke, dort, wo sie den Tunnel füllt."""
    assert placement_advice(tunnel_block(20.0)) == "build_plate"
    assert placement_advice(tunnel_block(65.0)) is None, "der weite Tunnel braucht sie"


def bare_tunnel(width: float) -> MeshData:
    """Ein Block mit einem Tunnel von ``width`` mal 20 mm, ohne Kragplatte —
    die Tunneldecke ist der einzige Überhang."""
    block = brick(width + 40.0, 40.0, 40.0, (0.0, 0.0, 20.0))
    tunnel = brick(width, 50.0, 20.0, (0.0, 0.0, 18.0))
    return place_on_bed(MeshData.of(trimesh.boolean.difference([block, tunnel])))


def test_asking_single_pieces_gives_the_same_channel_answer() -> None:
    """Der Prüfbericht fragt nur seine wenigen großen Stücke; jedes muss dieselbe
    Antwort bekommen wie im ganzen Durchgang, denn keine Säule beschneidet eine
    andere."""
    result = slice_body(tunnel_block(20.0), 0.5)
    everything = model_support(result)
    names = frozenset(
        (index, number)
        for index, layer in enumerate(result.layers)
        for number, _contour in enumerate(layer.overhangs)
    )
    assert everything.channels and names - everything.channels, "Kanal und Kragplatte"

    for name in sorted(names):
        asked = model_support(result, only=frozenset({name}))
        assert asked.channels == everything.channels & {name}, name


def test_the_channel_question_is_answered_once_per_measurement() -> None:
    """DRUCK-14: Die Kanalfrage hängt nur an den Schichten.

    Der Druckdialog stellte sie nach jedem geänderten Feld neu, an der
    Waschschüssel je 3,9 s. Dieselbe Messung bekommt dieselbe Antwort,
    ohne zu rechnen; eine neue Messung derselben Form wird neu gefragt, und
    auch eine wiederholte Frage nach denselben einzelnen Stücken bleibt gemerkt.
    """
    import app.core.slice.analysis as analysis

    result = slice_body(bare_tunnel(20.0), 0.5)
    first = model_support(result)
    assert first.channels

    assert model_support(result) is first, "dieselbe Messung, dieselbe Antwort"
    again = slice_body(bare_tunnel(20.0), 0.5)
    assert model_support(again) is not first, "eine neue Messung wird neu gefragt"
    assert model_support(again) == first
    single = frozenset({min(first.channels)})
    assert model_support(result, only=single) is model_support(result, only=single)
    assert len(analysis._ANSWERS) <= analysis._ANSWERS_KEPT


def test_the_second_print_report_reuses_the_channel_answer(monkeypatch: pytest.MonkeyPatch) -> None:
    """Der echte Verbraucher fragt dieselben Überhänge beim zweiten Bericht nicht neu."""
    from app.core.slice import analysis, findings
    from app.core.types import Scene, SceneObject

    original = analysis._model_support
    questions: list[object] = []

    def counted(*args, **kwargs):
        questions.append(kwargs.get("only", args[2] if len(args) > 2 else None))
        return original(*args, **kwargs)

    monkeypatch.setattr(analysis, "_model_support", counted)
    body = SceneObject(id="obj_1", name="Tunnel", mesh=bare_tunnel(20.0))
    scene = Scene(objects={body.id: body})
    settings = print_settings.resolve(petg())
    first = findings.print_findings(scene, petg(), settings)
    count = len(questions)
    assert count > 0, "Der erste Prüfbericht hat die Kanalfrage gestellt."
    assert any(question is not None for question in questions), "Der Bericht fragt Teilmengen."
    events = []
    assert findings.print_findings(scene, petg(), settings, check_status=events.append) == first
    assert len(questions) == count, "Auch die Teilfrage kommt aus dem Merker."
    assert events[-1].key == "slice.print_findings" and events[-1].state == "completed"


@pytest.mark.parametrize("missing", [(), ("material",)])
def test_print_check_status_does_not_infer_success_from_empty_findings(
    monkeypatch, missing
) -> None:
    """Ohne Grundlage bleibt die Prüfung offen, nach echter Arbeit ist sie abgeschlossen."""
    from app.core.slice import findings
    from app.core.types import Scene, SceneObject

    entry = SceneObject(id="obj_1", name="Quader", mesh=on_bed(brick(10, 10, 10, (0, 0, 5))))
    scene = Scene(objects={entry.id: entry})
    calls = []

    def measured(*args, **kwargs):
        calls.append(True)
        return []

    monkeypatch.setattr(findings.advise, "warnings_for", measured)
    monkeypatch.setattr(findings, "body_findings", measured)
    events = []
    assert (
        findings.print_findings(
            scene,
            petg(),
            print_settings.resolve(petg()),
            check_status=events.append,
            missing_basis=missing,
        )
        == []
    )
    assert len(calls) == (0 if missing else 2)
    final = {(item.key, item.object_id): item for item in events}
    assert set(final) == {("slice.settings", None), ("slice.print_findings", entry.id)}
    assert all(item.state == ("not_started" if missing else "completed") for item in final.values())
    assert all(item.missing_basis == missing for item in final.values())


@pytest.mark.parametrize("cancel", [False, True])
def test_print_check_status_keeps_unfinished_bodies_and_propagates_failure(
    monkeypatch, cancel
) -> None:
    """Ein abgebrochener oder gescheiterter Körper macht den nachfolgenden nicht fertig."""
    from app.core.errors import OperationCancelled
    from app.core.slice import findings
    from app.core.types import Scene, SceneObject

    entries = [
        SceneObject(id=f"obj_{number}", name="Quader", mesh=on_bed(brick(10, 10, 10, (0, 0, 5))))
        for number in range(3)
    ]
    scene = Scene(objects={entry.id: entry for entry in entries})
    problem = OperationCancelled() if cancel else ValueError("belegte Testausnahme")

    def measured(entry, *args, **kwargs):
        if entry.id == "obj_1":
            raise problem
        return []

    monkeypatch.setattr(findings.advise, "warnings_for", lambda *args, **kwargs: [])
    monkeypatch.setattr(findings, "body_findings", measured)
    events = []
    with pytest.raises(type(problem)) as caught:
        findings.print_findings(
            scene, petg(), print_settings.resolve(petg()), check_status=events.append
        )
    assert caught.value is problem
    final = {item.object_id: item for item in events if item.key == "slice.print_findings"}
    assert [final[entry.id].state for entry in entries] == [
        "completed",
        "cancelled" if cancel else "failed",
        "not_started",
    ]


def test_print_check_cancelled_before_work_never_completes_a_body() -> None:
    """Ein bereits abgebrochener Auftrag hinterlässt keinen fertigen Prüfstand."""
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal
    from app.core.slice import findings
    from app.core.types import Scene, SceneObject

    entry = SceneObject(id="obj_1", name="Quader", mesh=on_bed(brick(10, 10, 10, (0, 0, 5))))
    token = CancelSignal()
    token.cancel()
    events = []
    with pytest.raises(OperationCancelled):
        findings.print_findings(
            Scene(objects={entry.id: entry}),
            petg(),
            print_settings.resolve(petg()),
            cancelled=token,
            check_status=events.append,
        )
    assert not any(item.state == "completed" for item in events)
    assert [item.state for item in events if item.object_id == entry.id] == ["not_started"]


def test_print_check_without_geometry_is_explicitly_not_applicable() -> None:
    """Die leere Szene belegt keine erfolgreiche Körperprüfung."""
    from app.core.slice import findings
    from app.core.types import Scene

    events = []
    findings.print_findings(
        Scene(), petg(), print_settings.resolve(petg()), check_status=events.append
    )
    body = [item for item in events if item.key == "slice.print_findings"]
    assert len(body) == 1
    assert body[0].state == "not_applicable" and body[0].applicable is False


@pytest.mark.parametrize("missing", [(), ("material",)])
@pytest.mark.parametrize("cancel", [False, True])
def test_print_check_accounts_for_mesh_preparation_failure(monkeypatch, missing, cancel) -> None:
    """Auch die Netzbereitstellung gehört zur Prüfung; ohne Grundlage beginnt sie nicht."""
    from app.core.errors import OperationCancelled
    from app.core.slice import findings
    from app.core.types import Scene, SceneObject

    entry = SceneObject(id="obj_1", name="Quader", mesh=on_bed(brick(10, 10, 10, (0, 0, 5))))
    problem = OperationCancelled() if cancel else ValueError("Netzbereitstellung")
    calls = []

    def unavailable(_geometry):
        calls.append(True)
        raise problem

    monkeypatch.setattr(findings, "as_mesh_data", unavailable)
    events = []
    arguments = {"check_status": events.append, "missing_basis": missing}
    scene = Scene(objects={entry.id: entry})
    if missing:
        assert (
            findings.print_findings(scene, petg(), print_settings.resolve(petg()), **arguments)
            == []
        )
        assert not calls
    else:
        with pytest.raises(type(problem)) as caught:
            findings.print_findings(scene, petg(), print_settings.resolve(petg()), **arguments)
        assert caught.value is problem
    body = [item for item in events if item.object_id == entry.id]
    assert body[-1].state == ("not_started" if missing else "cancelled" if cancel else "failed")
    assert not any(item.state == "completed" for item in body)


def test_print_check_marks_an_empty_mesh_as_not_applicable() -> None:
    """Ein vorhandener leerer Körper ist ausdrücklich ungeprüft, nicht erfolgreich."""
    from app.core.slice import findings
    from app.core.types import Scene, SceneObject

    entry = SceneObject(id="obj_1", name="Leer", mesh=MeshData.of(trimesh.Trimesh()))
    events = []
    findings.print_findings(
        Scene(objects={entry.id: entry}),
        petg(),
        print_settings.resolve(petg()),
        check_status=events.append,
    )
    body = [item for item in events if item.object_id == entry.id]
    assert body[-1].state == "not_applicable"
    assert body[-1].applicable is False


def test_the_dialog_can_take_the_reports_layers() -> None:
    """DRUCK-14: Was der Prüfbericht geschnitten hat, findet der Druckdialog.

    Gleiches Raster, gleicher Winkel, gleiche Brückenbreite: dieselbe Messung,
    ohne zu schneiden. Ein anderer Winkel ist eine andere Frage.
    """
    from app.core.slice.findings import analysed, remembered_analysis

    mesh = bare_tunnel(20.0)
    settings = print_settings.resolve(petg())
    assert remembered_analysis(mesh, settings, 45.0, 0.8) is None, "nichts geschnitten"

    result = analysed(mesh, settings, 45.0, 0.8)

    assert remembered_analysis(mesh, settings, 45.0, 0.8) is result
    assert remembered_analysis(mesh, settings, 50.0, 0.8) is None
    assert analysed(mesh, settings, 45.0, 0.8) is result


def test_the_report_does_not_ask_for_supports_in_a_channel() -> None:
    """Prüfbericht und Vorschläge sagen über dieselbe Decke dasselbe.

    Die Vorschläge nehmen eine Kanaldecke aus dem Stützbedarf — sie schließt
    sich selbst, und eine Stütze darin käme nicht mehr heraus
    (:func:`model_support`). Der Prüfbericht fragte nur die Größe und sagte über
    dieselbe Tunneldecke von 1000 mm² „braucht Stützen"; wer ihm folgte und sie
    einschaltete, füllte den Tunnel. Der weite Tunnel bleibt ein Befund."""
    from app.core.slice.findings import overhang_findings

    narrow = slice_body(bare_tunnel(20.0), 0.5)
    wide = slice_body(bare_tunnel(65.0), 0.5)

    assert model_support(narrow).channels, "die Voraussetzung: eine Kanaldecke"
    assert not any(
        entry.path == "support.style"
        for entry in advise.advise(print_settings.resolve(petg()), petg(), narrow)
    ), "die Vorschläge verlangen keine Stütze"
    assert overhang_findings("teil", narrow) == []
    assert [finding.code for finding in overhang_findings("teil", wide)] == ["slice.large_overhang"]


# --- Die Aufstandsfläche gehört dem Drucker, nicht der Suche --------------------


def test_the_footing_does_not_depend_on_the_search_resolution() -> None:
    """Eine Kugel mit R = 20 stand bei 1,0 mm Suchhöhe auf 54 mm² und bei
    0,2 mm auf 4,6 — dieselbe Kugel, dieselbe Lage, zwei Antworten auf „kann
    das stehen".
    """
    ball = place_on_bed(MeshData.of(trimesh.creation.icosphere(subdivisions=4, radius=20.0)))
    printed = petg().printer.layer_height / 2.0

    coarse = slice_body(ball, 1.0, footing_height=printed)
    fine = slice_body(ball, 0.2, footing_height=printed)

    assert coarse.first_layer_area == pytest.approx(fine.first_layer_area, rel=0.02)
    # Und die Zahl ist die des Drucks: Ein Kugelabschnitt von 0,1 mm Höhe.
    expected = math.pi * (20.0**2 - (20.0 - printed) ** 2)
    assert coarse.first_layer_area == pytest.approx(expected, rel=0.2)


def test_without_the_printer_height_nothing_changes() -> None:
    """Ohne Angabe bleibt es beim ersten Schnitt — kein Aufrufer bekommt
    stillschweigend eine andere Zahl.
    """
    ball = place_on_bed(MeshData.of(trimesh.creation.icosphere(subdivisions=4, radius=20.0)))

    result: SliceResult = slice_body(ball, 1.0)

    assert result.first_layer_area == pytest.approx(result.layers[0].area)


@pytest.mark.parametrize("style", ["none", "grid"])
def test_supports_above_a_base_plate_must_be_allowed_on_the_model(style: str) -> None:
    """Eingeschaltete Stützen allein erreichen den Tischdeckel noch nicht."""
    settings = print_settings.with_path(print_settings.resolve(petg()), "support.style", style)
    settings = print_settings.with_path(settings, "support.placement", "build_plate")
    entries = advise.advise(settings, petg(), slice_body(table(), 0.5))
    changed = advise.apply(settings, entries)
    assert changed.support.style != "none"
    assert changed.support.placement == "everywhere"


def test_first_layer_flow_is_corrected_without_heating_other_layers() -> None:
    """Nur die erste Schicht überschreitet den Volumenstrom: ihr Tempo zählt."""
    profile = profiles.make_profile("prusa-mk4s", "pla")
    settings = print_settings.with_path(print_settings.resolve(profile), "speed.first_layer", 200.0)
    entries = advise.advise(settings, profile)
    changed = advise.apply(settings, entries)
    assert changed.temperature == settings.temperature
    assert (
        advise.flow_of(changed, changed.speed.first_layer, first_layer=True)
        <= settings.filament.max_flow
    )
    assert not advise.advise(changed, profile)


def test_draft_flow_advice_reaches_a_stable_setting_in_one_step() -> None:
    """Mehrfaches Übernehmen darf die Düse nicht bis zur Maschinengrenze heizen."""
    profile = profiles.make_profile("prusa-mk4s", "pla")
    settings = print_settings.resolve(profile, "draft")
    changed = advise.apply(settings, advise.advise(settings, profile))
    assert changed.temperature == settings.temperature
    assert advise.flow_of(changed, changed.speed.infill) <= changed.filament.max_flow
    assert not advise.advise(changed, profile)


def test_a_flow_below_the_smallest_print_speed_requires_a_correction() -> None:
    """Eine leere Vorschlagsliste darf keinen unerfüllbaren Volumenstrom verschweigen."""
    from app.core.errors import ValidationError

    profile = profiles.make_profile("prusa-mk4s", "pla")
    profile = replace(profile, printer=replace(profile.printer, nozzle_diameter=1.0))
    settings = print_settings.resolve(profile)
    settings = replace(
        settings,
        layers=replace(
            settings.layers,
            layer_height=0.8,
            first_layer_height=0.8,
            line_width=1.2,
            first_layer_line_width=1.2,
        ),
        filament=replace(settings.filament, max_flow=0.5),
    )
    with pytest.raises(ValidationError) as error:
        advise.advise(settings, profile)
    assert error.value.field == "filament.max_flow"
    assert error.value.suggestions


def test_the_first_line_obeys_the_same_nozzle_limit() -> None:
    """Die Nachbareinstellung ist im Dialog ebenfalls frei editierbar."""
    profile = profiles.make_profile("prusa-mk4s", "pla")
    settings = print_settings.with_path(
        print_settings.resolve(profile), "layers.first_layer_line_width", 0.1
    )
    changed = advise.apply(settings, advise.advise(settings, profile))
    assert changed.layers.first_layer_line_width == pytest.approx(0.34)


def test_a_single_arachne_line_is_not_reported_as_impossible() -> None:
    """PrusaSlicer erzeugt für diese 0,5-mm-Wand fünfzig Materiallagen."""
    profile = profiles.make_profile("prusa-mk4s", "pla")
    settings = print_settings.with_path(
        print_settings.resolve(profile), "shell.wall_generator", "arachne"
    )
    body = on_bed(brick(20.0, 0.5, 10.0, (0.0, 0.0, 5.0)))
    result = slice_body(body, settings.layers.layer_height)
    assert "settings.wall_below_nozzle" not in {
        entry.code for entry in advise.warnings_for(settings, profile, result)
    }


def test_a_fully_filled_connector_does_not_ask_for_more_material() -> None:
    """Bei hundert Prozent Füllung ist der Kern bereits aus Material."""
    settings = print_settings.with_path(print_settings.resolve(petg()), "infill.density", 1.0)
    entries = advise.advise(settings, petg(), connectors=(8.0,))
    assert not {"shell.wall_count", "infill.density"}.intersection(entry.path for entry in entries)


@pytest.mark.parametrize("bed", [85, 100])
def test_small_footprint_advice_keeps_the_filament_bed_temperature(bed: int) -> None:
    """Eine kleine Standfläche liefert keine neue Temperaturgrenze für die Spule."""
    profile = profiles.make_profile("bambu-x1c", "abs")
    settings = print_settings.with_path(
        print_settings.resolve(profile), "temperature.bed_first_layer", bed
    )
    body = on_bed(brick(5.0, 5.0, 10.0, (0.0, 0.0, 5.0)))
    result = slice_body(body, settings.layers.layer_height)
    changed = advise.apply(settings, advise.advise(settings, profile, result))
    assert changed.temperature.bed_first_layer == bed
    again = advise.advise(changed, profile, result)
    assert "temperature.bed_first_layer" not in {entry.path for entry in again}


def test_combined_advice_preserves_support_needed_by_another_body() -> None:
    """Ein Würfel darf die schon nötigen Stützen seines Nachbarn nicht abschalten."""
    settings = print_settings.with_path(print_settings.resolve(petg()), "support.style", "grid")
    cube = slice_body(on_bed(brick(20.0, 20.0, 20.0, (0.0, 0.0, 10.0))), 0.5)
    top = slice_body(table(), 0.5)
    groups = [(settings, advise.advise(settings, petg(), result)) for result in (cube, top)]
    entries = advise.combine(settings, groups)
    assert "support.style" not in {entry.path for entry in entries}


def test_combined_advice_limits_speed_for_the_slowest_material() -> None:
    """Das gemeinsame Tempo bleibt für jeden beteiligten Materialslot tragbar."""
    profile = profiles.make_profile("prusa-mk4s", "tpu-95a")
    settings = print_settings.resolve(profile)
    slow = replace(settings, speed=replace(settings.speed, outer_wall=20.0))
    groups = [(settings, advise.advise(settings, profile)), (slow, advise.advise(slow, profile))]
    changed = advise.apply(settings, advise.combine(settings, groups))
    assert changed.speed.outer_wall == pytest.approx(20.0)


def test_suggested_connector_infill_meets_the_announced_material_share() -> None:
    """Runden darf den versprochenen Materialanteil nicht wieder unterschreiten."""
    settings = print_settings.resolve(petg())
    changed = advise.apply(settings, advise.advise(settings, petg(), connectors=(60.0,)))
    diameter = 60.0
    core = diameter - 2.0 * changed.shell.wall_count * changed.layers.line_width
    solid_area = (diameter**2 - core**2) + changed.infill.density * core**2
    assert solid_area / diameter**2 >= 0.75


def test_an_island_above_the_bed_may_be_supported_from_the_plate() -> None:
    """Eine Insel, unter der nur das Bett liegt, erreicht das Bett. Bis zum
    26.09.2026 bekam jedes Teil mit einer Insel „überall" — auch dann."""
    body = on_bed(
        brick(20.0, 20.0, 5.0, (0.0, 0.0, 2.5)),
        brick(10.0, 10.0, 4.0, (30.0, 0.0, 12.0)),
    )

    assert placement_advice(body) == "build_plate"


def test_an_island_above_the_model_keeps_supports_everywhere() -> None:
    """Dieselbe Insel über der Grundplatte: Ihre Stütze muss auf dem Modell
    stehen, gleich wie klein sie ist."""
    body = on_bed(
        brick(40.0, 40.0, 5.0, (0.0, 0.0, 2.5)),
        brick(6.0, 6.0, 4.0, (0.0, 0.0, 14.0)),
    )

    assert model_support(slice_body(body, 0.5)).island_on_model
    assert placement_advice(body) is None, "everywhere bleibt stehen"


def test_a_part_with_a_channel_is_offered_the_blocker() -> None:
    """„Nur vom Bett" hält einen Kanal nicht in jedem Slicer frei — Orcas
    organische Bäume wuchsen trotzdem hinein. Die Sperre ist ein Vorschlag wie
    jeder andere: Ohne „Vorschläge übernehmen" geht sie nicht hinaus."""
    settings = print_settings.resolve(petg())
    entries = advise.advise(settings, petg(), slice_body(tunnel_block(20.0), 0.5))

    assert [entry.value for entry in entries if entry.path == "support.block_channels"] == [True]
    wide = advise.advise(settings, petg(), slice_body(tunnel_block(65.0), 0.5))
    assert "support.block_channels" not in {entry.path for entry in wide}


def test_the_channel_space_stays_inside_the_tunnel() -> None:
    """Gesperrt wird der freie Raum des Kanals, nicht mehr: Die Kragplatte
    daneben braucht ihre Stützen vom Bett, und jenseits der Tunnelwand liegt
    freie Luft, die mit dem Kanal nicht zusammenhängt. Nach oben reicht die
    Sperre eine Scheibe in die Decke — dort fragt der Slicer, ob er stützt."""
    result = slice_body(tunnel_block(20.0), 0.5)
    slabs = channel_space(result, model_support(result), LINE)

    assert slabs, "der Tunnel hat eine Decke über dem Tunnelboden"
    low_x = min(region.bounds[0] for _low, _high, region in slabs)
    high_x = max(region.bounds[2] for _low, _high, region in slabs)
    # Der Tunnel ist 20 mm breit und sitzt mittig im 60 mm breiten Block; der
    # Zuschlag ragt in die Wände, nicht weiter.
    assert low_x >= -10.0 - LINE - 1e-6 and high_x <= 10.0 + LINE + 1e-6
    assert min(low for low, _high, _region in slabs) >= 8.0 - 1.0
    # Die Decke liegt bei 28 mm. Die oberste freie Scheibe endet je nach
    # Raster unter ihr, und von dort reicht die Sperre eine Scheibe höher —
    # zugesagt ist, dass sie in die Decke ragt, und nicht weiter als das.
    top = max(high for _low, high, _region in slabs)
    assert 28.0 < top <= 28.0 + 0.5 + 1.0


def test_the_channel_space_leaves_a_column_on_the_model_free() -> None:
    """Die Sperre hält Stützen aus dem Kanal fern, nicht von einer Decke, die sie braucht.

    Am Wedge-Lock (04.10.2026) lag im Cura-Raster ein Kanalstück von 7 mm²
    unter einer Brücke von 25 mm, deren Säule auf dem Modell aufsetzt. Die
    Sperre um das Kanalstück füllte denselben Raum, und Cura stützte die
    Brücke gar nicht (0,0 statt 2,0 m Stützbahn). Hier steht dieselbe Lage im
    Tunnel: eine Säule auf dem Tunnelboden neben der Kanaldecke.
    """
    from app.core.types import Polygon

    result = slice_body(tunnel_block(20.0), 0.5)
    model = model_support(result)
    column = ((2.0, -2.0), (6.0, -2.0), (6.0, 2.0), (2.0, 2.0))
    footprint = box(2.0, -2.0, 6.0, 2.0)
    blocked = unary_union([region for _low, _high, region in channel_space(result, model, LINE)])
    assert blocked.intersection(footprint).area > 15.0, "ohne die Säule sperrt der Tunnel sie mit"

    beside = replace(model, open_columns=(*model.open_columns, (Polygon(column), 8.0, 27.0)))
    slabs = channel_space(result, beside, LINE)

    assert slabs, "der Kanal bleibt gesperrt"
    for _low, _high, region in slabs:
        assert region.intersection(footprint).area == pytest.approx(0.0, abs=1e-6)


def test_a_column_too_narrow_for_a_line_stays_blocked() -> None:
    """Ein Loch in der Sperre, in dem keine Bahn samt Abstand Platz hat, ist keine
    Säule und schließt sich: Ausgespart mit Zuschlag ließ ein Krümel von 0,33 mm²
    im Kanal der Waschschüssel den OrcaSlicer 1,5 m Stütze hindurchstellen
    (08.10.2026). Hier eine Säule von 0,6 mm im Tunnel, schmaler als zwei
    Bahnbreiten."""
    from app.core.types import Polygon

    result = slice_body(tunnel_block(20.0), 0.5)
    model = model_support(result)
    crumb = ((4.0, -0.3), (4.6, -0.3), (4.6, 0.3), (4.0, 0.3))
    beside = replace(model, open_columns=(*model.open_columns, (Polygon(crumb), 8.0, 27.0)))

    blocked = unary_union([region for _low, _high, region in channel_space(result, beside, LINE)])

    assert blocked.intersection(box(4.0, -0.3, 4.6, 0.3)).area == pytest.approx(0.36, abs=1e-6)


def test_a_gap_too_narrow_for_a_support_line_stays_free() -> None:
    """Gesperrt wird nur Raum, in dem Stütze stehen könnte: mindestens zwei
    Übergriffe breit, eine Bahn samt Abstand. Am Drachen bestand die Sperre um die
    Zwickel zwischen Schwanz- und Kinnstacheln aus 60 000 Krümeln unter 100 mm³.
    Hier ein Schlitz von 0,6 mm neben dem Tunnel mit einer eigenen Säule darin;
    den Filter hielt bis zur Durchsicht des Merges vom 08.10.2026 kein Test."""
    from app.core.types import Polygon

    body = trimesh.boolean.difference(
        [tunnel_block(20.0).raw, brick(0.6, 50.0, 20.0, (12.3, 0.0, 18.0))]
    )
    result = slice_body(place_on_bed(MeshData.of(body)), 0.5)
    model = model_support(result)
    slit = ((12.0, -15.0), (12.6, -15.0), (12.6, 15.0), (12.0, 15.0))
    beside = replace(model, channel_columns=(*model.channel_columns, (Polygon(slit), 8.0, 27.0)))

    blocked = unary_union([region for _low, _high, region in channel_space(result, beside, LINE)])

    assert blocked.area > 100.0, "der Tunnel bleibt gesperrt"
    assert blocked.intersection(box(12.0, -15.0, 12.6, 15.0)).area == pytest.approx(0.0, abs=1e-6)


def test_the_channel_space_is_remembered_per_line_width() -> None:
    """Der Sperrraum ist gemerkt (Rat, Schätzung und Schreiber fragen ihn), und
    zwar je Bahnbreite: Sie ist Zuschlag und Mindestbreite des Raums."""
    result = slice_body(tunnel_block(20.0), 0.5)
    model = model_support(result)

    narrow = unary_union([region for _low, _high, region in channel_space(result, model, 0.4)])
    wide = unary_union([region for _low, _high, region in channel_space(result, model, 0.8)])

    first, again = channel_space(result, model, 0.4), channel_space(result, model, 0.4)
    assert first and all(old[2] is new[2] for old, new in zip(first, again, strict=True)), (
        "die zweite Frage bekommt dieselben Scheiben, nicht neu gerechnete"
    )
    assert wide.area > narrow.area, "die breitere Bahn greift weiter in die Wände"


def test_in_an_enclosed_cavity_nothing_is_spared() -> None:
    """Ringsum umschlossen holt niemand eine Stütze heraus — dort spart die Sperre
    nichts aus. Im Wasserkanal der Waschschüssel hängt eine schräge Fläche, die
    selbst Stütze bräuchte; ausgespart, holte der ElegooSlicer sie mit einem Ast
    quer durch den Kanal (1,6 m), ohne Aussparung 0,0 m (08.10.2026). Hier dieselbe
    Säule wie im offenen Tunnel, in einer geschlossenen Kammer."""
    from app.core.types import Polygon

    block = brick(60.0, 40.0, 40.0, (0.0, 0.0, 20.0))
    chamber = brick(20.0, 30.0, 20.0, (0.0, 0.0, 18.0))
    result = slice_body(
        place_on_bed(MeshData.of(trimesh.boolean.difference([block, chamber]))), 0.5
    )
    model = model_support(result)
    column = ((2.0, -2.0), (6.0, -2.0), (6.0, 2.0), (2.0, 2.0))
    footprint = box(2.0, -2.0, 6.0, 2.0)
    beside = replace(model, open_columns=(*model.open_columns, (Polygon(column), 8.0, 27.0)))

    blocked = unary_union([region for _low, _high, region in channel_space(result, beside, LINE)])

    assert model.channel_columns, "die Kammerdecke ist Kanal und lohnt eine Sperre"
    assert blocked.intersection(footprint).area > 15.0, "die Säule bleibt gesperrt"


def bottle_cavity() -> MeshData:
    """Ein Block mit geschlossenem Hohlraum: unten eine Kammer 44 auf 40 mm von 6
    bis 22 mm Höhe, darüber ein Hals von 20 mm Weite bis 32 mm. Unter der
    Halsdecke fasst der Raum keinen Kreis von ``CHANNEL_WIDTH``, die Kammer
    darunter schon — wie der Rohrbogen der Waschschüssel, unter dem Gewölbe
    22 mm weit, auf halber Höhe 42 mm. Die Schultern der Kammer hängen frei
    über ihrem Boden und bräuchten selbst Stütze."""
    block = brick(70.0, 50.0, 40.0, (0.0, 0.0, 20.0))
    chamber = brick(44.0, 40.0, 16.0, (0.0, 0.0, 14.0))
    neck = brick(20.0, 40.0, 10.0, (0.0, 0.0, 27.0))
    hollow = trimesh.boolean.union([chamber, neck])
    return place_on_bed(MeshData.of(trimesh.boolean.difference([block, hollow])))


def test_a_wide_enclosed_chamber_under_a_channel_stays_blocked() -> None:
    """Gesperrt wird auch umschlossener Raum, der weiter ist als der Kanalkreis,
    und dort wird nichts ausgespart, auch nicht, was selbst Stütze bräuchte
    (08.10.2026): Nur aus der Enge gesperrt, behielte die Schüssel in Drucklage
    9 895 von 170 682 mm³ Sperrraum (Sonde, ohne Slicer); mit Aussparung im weiten
    Rohrbogen holte der ElegooSlicer eine schräge Fläche darin mit einem Ast quer
    durch den Kanal (0,7 m). Beides hielt bis zu Review 3 kein Test."""
    result = slice_body(bottle_cavity(), 0.5)
    model = model_support(result)
    slabs = channel_space(result, model, LINE)
    chamber = box(-22.0, -20.0, 22.0, 20.0)

    assert model.channel_columns, "die Halsdecke ist Kanal und lohnt eine Sperre"
    assert model.open_columns, "die Schultern der Kammer bräuchten selbst Stütze"
    assert min(low for low, _high, _region in slabs) <= 6.0 + 1.0, "gesperrt bis zum Boden"
    low = unary_union([region for _low, high, region in slabs if high <= 14.0])
    assert low.intersection(chamber).area > 0.95 * chamber.area, "die ganze Kammer"


# --- Eine Decke ist als Ganzes Kanal oder Brücke --------------------------------

#: Die Unterseite des Stegs steigt auf seiner Tiefe um so viel an; die Zwickel
#: an den Beinen fallen auf 3 mm Breite um 1 mm ab — beide flacher als jede
#: Überhanggrenze, also zerfallen beide in Streifen, je Schicht einen.
DECK_RISE = 0.25
GUSSET_WIDTH = 3.0
GUSSET_DROP = 1.0


def hull(points: list[tuple[float, float, float]]) -> trimesh.Trimesh:
    return trimesh.convex.convex_hull(points)


def bridge_on_gussets(
    gap: float, legs: tuple[float, float], depth: float = 5.0, rise: float = DECK_RISE
) -> MeshData:
    """Ein Steg von ``gap`` mm Spannweite und ``depth`` mm Tiefe auf zwei Beinen,
    die in y von ``legs[0]`` bis ``legs[1]`` reichen, alles auf einer
    Grundplatte; die Unterseite des Stegs steigt von 10 mm (hinten, y =
    ``depth``) auf 10 + ``rise`` mm (vorn, y = 0). Hinten unter dem Steg sitzt
    an jedem Bein ein flacher Zwickel, 1 mm tief.

    Der Bau des Wedge-Lock (``F:\\3D Dateien``, 05.10.2026): Dort waren es zwei
    Ausrundungen zwischen Bein und Steg, deren erste Schicht als Kanaldecke
    galt, weil ihr Ort an der Beinwand liegt — und die Sperre um sie sperrte
    den Raum unter dem ganzen Steg.
    """
    left, right = 5.0, 5.0 + gap
    low, high = 10.0, 12.0
    deck = [
        (x, y, z)
        for x in (left, right)
        for y, z in ((0.0, low + rise), (depth, low), (0.0, high), (depth, high))
    ]
    parts = [
        brick(gap + 20.0, legs[1] - legs[0] + 20.0, 2.0, (left + gap / 2.0, sum(legs) / 2.0, 1.0)),
        brick(5.0, legs[1] - legs[0], high - 2.0, (left - 2.5, sum(legs) / 2.0, high / 2.0 + 1.0)),
        brick(5.0, legs[1] - legs[0], high - 2.0, (right + 2.5, sum(legs) / 2.0, high / 2.0 + 1.0)),
        hull(deck),
    ]
    for face, toward in ((left, 1.0), (right, -1.0)):
        tip = face + toward * GUSSET_WIDTH
        parts.append(
            hull(
                [
                    (x, y, z)
                    for y in (depth - 1.0, depth)
                    for x, z in (
                        (face, low - GUSSET_DROP),
                        (face, high - 1.0),
                        (tip, high - 1.0),
                        (tip, low),
                    )
                ]
            )
        )
    return on_bed(*parts)


@pytest.mark.parametrize("layer_height", [0.08, 0.2])
def test_a_bridge_is_no_channel_because_its_foot_touches_a_wall(layer_height: float) -> None:
    """Die Kanalsperre nahm einem übernommenen Stützvorschlag jede Stütze.

    Am Wedge-Lock an der 0,25er Düse (Kobra S1, 0,08 mm) galt die erste
    Schicht einer 25-mm-Brücke als Kanaldecke, die vier darüber als Brücke
    außerhalb eines Kanals. Die Brücken verlangten Stützen, das Kanalstück die
    Sperre, und die Sperre deckte die ganze Decke: 0 statt 6,6 m Stütze im
    G-Code. Bei 0,2 mm gab es kein Kanalstück. Gefragt wird deshalb die Decke
    als Ganzes — Stücke benachbarter Schichten, die aneinander anschließen —,
    und eine Decke, die zum größeren Teil frei hängt, ist kein Kanal.
    """
    gap = 25.0
    result = slice_body(bridge_on_gussets(gap, (-3.0, 8.0)), layer_height)
    gussets = [
        (index, number)
        for index, layer in enumerate(result.layers)
        if layer.z < 10.0
        for number, piece in enumerate(layer.overhangs)
        if piece_area(piece) < 1.0
    ]
    assert gussets, "die Zwickel hängen in Streifen an den Beinwänden"

    need = advise.support_need(result)
    model = need.model
    spans = [layer.bridge_width for layer in result.layers if layer.bridge_width > 0.0]
    assert max(spans) == pytest.approx(gap, abs=0.2), "die Brücke spannt von Bein zu Bein"
    assert need.needed, "eine Brücke von 25 mm braucht Stützen"
    assert not model.channels, "kein Stück dieser Decke ist eine Kanaldecke"
    assert channel_space(result, model, LINE) == [], "also keine Sperre unter der Brücke"
    entries = advise.advise(print_settings.resolve(petg()), petg(), result)
    assert "support.block_channels" not in {entry.path for entry in entries}
    for name in gussets:
        assert not model_support(result, only=frozenset({name})).channels, (
            "einzeln gefragt dieselbe Antwort wie im ganzen Durchgang"
        )


@pytest.mark.parametrize("layer_height", [0.08, 0.2])
def test_a_channel_ceiling_stays_a_channel_with_an_open_end(layer_height: float) -> None:
    """Die Gegenprobe, die Waschschüssel: Ihr Wasserkanal ist eine Decke, an
    deren Mündung ein Stück außerhalb des Kanals frei hängt. Die Decke hängt
    zum größeren Teil im Kanal und bleibt Kanaldecke; das offene Stück bleibt
    offen und behält seine Stütze.

    Hier ein Steg von 15 mm Tiefe in einem 20 mm weiten Tunnel, der vorn 1 mm
    hinter dem Steg endet. Bei 0,08 mm hängt der vorderste Streifen außerhalb,
    bei 0,2 mm reicht kein Streifen hinaus.
    """
    result = slice_body(bridge_on_gussets(20.0, (-1.0, 40.0), depth=15.0, rise=0.5), layer_height)
    model = model_support(result)
    front = max(
        (
            (index, number)
            for index, layer in enumerate(result.layers)
            for number, _piece in enumerate(layer.overhangs)
        ),
        key=lambda name: result.layers[name[0]].z,
    )

    assert model.channels, "die Decke im Tunnel ist Kanaldecke"
    assert channel_space(result, model, LINE), "und bekommt ihre Sperre"
    if layer_height < 0.1:
        assert front in model.open_pieces, "der vorderste Streifen hängt außerhalb"
        assert model.open_area < model.channel_area
    else:
        assert not model.open_pieces


# --- Eine Kanaldecke spannt; eine Auskragung in einer engen Tasche nicht ---------


def jaw_in_a_pocket(underside_at_wall: float | None = None) -> MeshData:
    """Ein Kiefer, der 18 mm aus einer Rückwand ragt, über einer Tasche von 24 mm
    Weite zwischen zwei Armen, die bis zu ihm hinaufreichen; vorn ist die Tasche
    offen, unten trägt sie eine Grundplatte.

    Der Bau des Drachen (``F:\\3D Dateien\\Drache.p3d``, 08.10.2026): Kiefer über
    der Brust, Flügelbogen und Schuppen hängen in Räumen, die keinen Kreis von
    30 mm fassen, und ihre Säulen setzen auf dem Modell auf. Gehalten sind sie
    nur an einer Seite.

    Mit ``underside_at_wall`` steigt die Unterseite von dieser Höhe an der Wand
    bis 50 mm an der Spitze, wie ein Kinn: Im Schnitt zerfällt sie in Streifen.
    """
    head = (
        brick(16.0, 18.0, 6.0, (0.0, 6.0, 53.0))
        if underside_at_wall is None
        else chin(underside_at_wall)
    )
    return on_bed(
        brick(80.0, 60.0, 4.0, (0.0, 0.0, 2.0)),
        brick(40.0, 10.0, 60.0, (0.0, 20.0, 34.0)),
        brick(8.0, 30.0, 52.0, (-16.0, 0.0, 30.0)),
        brick(8.0, 30.0, 52.0, (16.0, 0.0, 30.0)),
        head,
    )


def chin(underside_at_wall: float) -> trimesh.Trimesh:
    """Der Kopf mit schräger Unterseite: an der Rückwand auf ``underside_at_wall``,
    an der Spitze 18 mm davor auf 50 mm."""
    return trimesh.convex.convex_hull(
        [
            (x, y, z)
            for x in (-8.0, 8.0)
            for y, z in ((15.0, underside_at_wall), (-3.0, 50.0), (15.0, 56.0), (-3.0, 56.0))
        ]
    )


def test_a_sloped_chin_over_the_chest_keeps_its_supports_everywhere() -> None:
    """RM-570 schaltete am Kinn die Stützen ein, aber der Stützort fragte weiter
    das einzelne Stück: Im Schnitt zerfällt die Unterseite in Streifen unter
    10 mm², und der Rat hieß „Stützen, nur vom Bett“ — damit druckt ein Kinn über
    der Brust weiter in die Luft, an jeder Büste (Review 3 vom 08.10.2026).
    Was auf dem Modell aufsetzt, misst sich am selben Feld wie der Stützbedarf.
    """
    body = on_bed(
        brick(80.0, 60.0, 4.0, (0.0, 0.0, 2.0)),
        brick(40.0, 10.0, 60.0, (0.0, 20.0, 34.0)),
        brick(60.0, 30.0, 20.0, (0.0, 0.0, 14.0)),
        chin(44.0),
    )
    result = slice_body(body, 0.2)
    need = advise.support_need(result)
    model = need.model

    assert need.needed, "das Kinn braucht Stützen"
    assert not model.channels, "über der breiten Brust ist kein Kanal"
    assert not worth_support(model.open_patch, model.open_area), "kein Streifen trägt es allein"
    entries = advise.advise(print_settings.resolve(petg()), petg(), result)
    assert "support.placement" not in {entry.path for entry in entries}, "everywhere bleibt"


def test_only_what_rests_on_the_model_counts_as_its_field() -> None:
    """Der Stützort fragt das Feld nur so weit, wie es auf dem Modell aufsetzt:
    wie beim einzelnen Stück, dessen aufsetzende Fläche zählt. Hier steht das Kinn
    zur Hälfte über einer Brust, zur Hälfte über dem Bett; als Ganzes trüge es,
    was davon auf der Brust aufsetzt, nicht. Sonst verlangte jede Ecke eines
    Feldes über einer Stufe des Modells, dass alle Stützen dort ansetzen dürfen.
    Ein kleiner Sims daneben bringt das Aufsetzende über 100 mm², damit das Feld
    überhaupt gefragt wird."""
    rise = 4.0 * math.tan(math.radians(18.0))
    ledge = trimesh.convex.convex_hull(
        [
            (x, y, z)
            for x in (12.0, 20.0)
            for y, z in ((15.0, 30.0), (11.0, 30.0 + rise), (15.0, 34.0), (11.0, 34.0))
        ]
    )
    body = on_bed(
        brick(40.0, 10.0, 60.0, (0.0, 20.0, 30.0)),
        brick(30.0, 30.0, 24.0, (15.0, 0.0, 12.0)),
        chin(44.0),
        ledge,
    )
    result = slice_body(body, 0.2)
    need = advise.support_need(result)
    model = need.model

    assert need.needed, "das Kinn braucht Stützen"
    assert model.open_area > OVERHANG_LAYER_WORTH_SUPPORT, "die Feldfrage wird gestellt"
    assert not worth_support(model.open_patch, model.open_area)
    assert largest_sloped_patch(result) > OVERHANG_LAYER_WORTH_SUPPORT, "als Ganzes ein Feld"
    assert model.open_field <= OVERHANG_LAYER_WORTH_SUPPORT, "auf der Brust nur die Hälfte"
    entries = advise.advise(print_settings.resolve(petg()), petg(), result)
    placement = [entry.value for entry in entries if entry.path == "support.placement"]
    assert placement == ["build_plate"], "die Stützen erreichen das Kinn vom Bett"


def test_trees_where_small_overhangs_rest_on_the_model_not_under_a_flat_ceiling() -> None:
    """Wo Stützen auf dem Modell ansetzen, hinterlässt ein Gitter mit jeder Säule
    eine Narbe; ein Baum setzt mit wenigen Füßen auf (Drache, 08.10.2026: 212 bis
    324 mm² Auflage der Herstellergitter, 4 bis 66 mm² mit Bäumen). Unter einer
    großen flachen Decke hängt die Unterseite zwischen den Baumspitzen durch —
    dort bleibt die Art des Herstellers (Recherche vom 08.10.2026)."""

    def style(body: MeshData) -> object:
        entries = advise.advise(print_settings.resolve(petg()), petg(), slice_body(body, 0.2))
        return next((entry.value for entry in entries if entry.path == "support.style"), None)

    figure = chin_over_chest()
    assert style(figure) == "tree", "das Kinn setzt in Streifen auf der Brust auf"
    assert style(table()) == "auto", "die Tischplatte ist eine flache Decke"
    # Auch wenn die flache Decke über dem Bett hängt und nur das Kinn auf dem
    # Modell aufsetzt: Gefragt ist die Deckenform am Körper (Review vom 08.10.2026).
    with_arm = on_bed(
        brick(80.0, 60.0, 4.0, (0.0, 0.0, 2.0)),
        brick(40.0, 10.0, 60.0, (0.0, 20.0, 34.0)),
        brick(60.0, 30.0, 20.0, (0.0, 0.0, 14.0)),
        chin(44.0),
        brick(28.0, 30.0, 3.0, (54.0, 0.0, 40.0)),
        brick(4.0, 30.0, 40.0, (38.0, 0.0, 20.0)),
    )
    assert style(with_arm) == "auto", "der flache Arm über dem Bett bleibt beim Hersteller"

    def changed(body: MeshData, before: str) -> list[object]:
        settings = print_settings.with_path(print_settings.resolve(petg()), "support.style", before)
        entries = advise.advise(settings, petg(), slice_body(body, 0.2))
        return [entry.value for entry in entries if entry.path == "support.style"]

    assert changed(figure, "grid") == ["tree"], "auch über einem gewählten Gitter"
    assert changed(table(), "grid") == [], "die flache Decke behält ihr Gitter"


def chin_over_chest() -> MeshData:
    """Eine Figur im Kleinen: ein Kinn mit schräger Unterseite über der Brust,
    dessen Streifen auf dem Modell aufsetzen — kleine, gewölbte Überhänge."""
    return on_bed(
        brick(80.0, 60.0, 4.0, (0.0, 0.0, 2.0)),
        brick(40.0, 10.0, 60.0, (0.0, 20.0, 34.0)),
        brick(60.0, 30.0, 20.0, (0.0, 0.0, 14.0)),
        chin(44.0),
    )


def _support_advice(
    body: MeshData,
    profile: Profile,
    values: dict[str, object],
    *,
    flavour: str | None = None,
    paths: tuple[str, ...] = (
        "support.z_gap",
        "support.bottom_interface_layers",
        "support.interface_spacing",
        "support.interface_layers",
        "cooling.support_interface_cooling",
    ),
    whole_layers: bool = False,
    organic: frozenset[str] = frozenset(),
) -> dict[str, object]:
    """Die Vorschläge zu Abstand und Trennschicht für einen Körper (RM-583)."""
    settings = print_settings.resolve(profile)
    for path, value in values.items():
        settings = print_settings.with_path(settings, path, value)
    entries = advise.advise(
        settings,
        profile,
        slice_body(body, 0.2),
        flavour=flavour,  # type: ignore[arg-type]
        whole_layers=whole_layers,
        organic=organic,
    )
    return {entry.path: entry.value for entry in entries if entry.path in paths}


def test_the_support_gap_follows_layer_height_and_material() -> None:
    """Der Abstand zwischen Stütze und Teil folgt Schichthöhe und Material
    (RM-583, Recherche vom 08.10.2026, Nr. 1): PLA etwa eine Schicht, PETG das
    1,4-Fache, nie unter 0,1 und über 0,25 bzw. 0,3 mm. Cura rechnet in ganzen
    Schichten. Was im Band liegt, bleibt beim Hersteller."""
    pla = profiles.make_profile("centauri-carbon-2", "pla")
    gap = "support.z_gap"

    def proposed(
        profile: Profile, layer: float, z_gap: float, flavour: str | None = None
    ) -> object:
        values = {"layers.layer_height": layer, gap: z_gap}
        return _support_advice(table(), profile, values, flavour=flavour, paths=(gap,)).get(gap)

    assert proposed(pla, 0.2, 0.2) is None, "eine Schicht bei PLA ist richtig"
    assert proposed(pla, 0.2, 0.22) is None, "0,22 liegt im Band"
    assert proposed(petg(), 0.2, 0.2) == pytest.approx(0.28), "PETG haftet an sich selbst"
    assert proposed(petg(), 0.2, 0.2, "cura") is None, "Cura rundet auf eine Schicht"
    assert proposed(pla, 0.12, 0.2) == pytest.approx(0.12), "bei feinen Schichten zu viel Luft"
    assert proposed(pla, 0.06, 0.06) == pytest.approx(0.10), "nie unter 0,1 mm"
    assert proposed(petg(), 0.32, 0.45) == pytest.approx(0.30), "nie über 0,3 mm bei PETG"


@pytest.mark.parametrize(
    ("material", "layer", "flavour", "gap"),
    [
        ("pla", 0.08, "cura", 0.16),
        ("petg", 0.10, "cura", 0.20),
        ("pla", 0.04, "cura", 0.12),
        ("pla", 0.28, "cura", 0.28),
        ("pla", 0.20, "cura", 0.20),
        ("petg", 0.10, "orca", 0.14),
        ("pla", 0.075, "cura", 0.15),
    ],
)
def test_whole_layers_stay_inside_the_material_band(
    material: str, layer: float, flavour: str, gap: float
) -> None:
    """Wo der Slicer in ganzen Schichten rechnet (Cura), liegt der Abstand
    innerhalb der Grenzen des Materials: PLA bei 0,08 mm zwei Schichten statt
    einer unter dem Minimum, PETG bei 0,1 mm 0,2 statt 0,1 (RM-583, Review).
    Oberhalb des Maximums bleibt eine Schicht. Eine halbe Schicht rundet auf,
    und ein Wert mit drei Stellen bleibt eine ganze Schicht."""
    profile = profiles.make_profile("centauri-carbon-2", material)
    target = advise.support_gap_target(layer, profile.material, flavour)  # type: ignore[arg-type]
    assert target == pytest.approx(gap)
    proposed = _support_advice(
        table(),
        profile,
        {"layers.layer_height": layer, "support.z_gap": 0.6},
        flavour=flavour,
        paths=("support.z_gap",),
    )
    assert proposed["support.z_gap"] == pytest.approx(gap)


def test_half_a_layer_rounds_up() -> None:
    """Liegt das Ziel genau zwischen zwei Schichten, gilt die obere: mehr Luft
    löst sich sicher, zu wenig klebt. Pythons ``round`` rundete 2,5 Schichten
    auf zwei ab (RM-583, Nachprüfung L4)."""
    pla = profiles.make_profile("centauri-carbon-2", "pla").material

    assert advise.support_gap_target(
        0.05, replace(pla, support_gap_factor=2.5), "cura"
    ) == pytest.approx(0.15)
    assert advise.support_gap_target(
        0.1, replace(pla, support_gap_factor=1.5), "cura"
    ) == pytest.approx(0.2)


# Aus ``materials.toml``: PLA Faktor 1,0 zwischen 0,10 und 0,25 mm, PETG 1,4
# zwischen 0,12 und 0,30 mm; neben dem Turm das Vielfache im Band, mindestens eins.
@pytest.mark.parametrize(
    ("material", "layer", "free", "beside_a_tower"),
    [
        ("pla", 0.08, 0.10, 0.16),
        ("petg", 0.08, 0.12, 0.16),
        ("petg", 0.20, 0.28, 0.20),
        ("pla", 0.20, 0.20, 0.20),
    ],
)
def test_beside_a_prime_tower_the_gap_comes_in_whole_layers(
    material: str, layer: float, free: float, beside_a_tower: float
) -> None:
    """Mit Reinigungsturm legt die Orca-Familie die Stütze auf die Schichten des
    Modells und rundet den Abstand zur nächsten Schicht (RM-622): PLA bei
    0,08er Schichten bekäme aus 0,10 mm eine Schicht, also 0,08 — unter dem
    Minimum des Materials. Neben dem Turm rät Solidon deshalb gleich ganze
    Schichten im Band, wie bei Cura; ohne Turm bleibt der freie Wert."""
    profile = profiles.make_profile("centauri-carbon-2", material)
    gap = "support.z_gap"

    assert advise.support_gap_target(layer, profile.material, "orca") == pytest.approx(free)
    assert advise.support_gap_target(
        layer, profile.material, "orca", whole_layers=True
    ) == pytest.approx(beside_a_tower)
    asked: dict[str, object] = {"layers.layer_height": layer, gap: 0.6}
    assert _support_advice(
        table(), profile, asked, flavour="orca", paths=(gap,), whole_layers=True
    ) == {gap: pytest.approx(beside_a_tower)}
    assert _support_advice(table(), profile, asked, flavour="orca", paths=(gap,)) == {
        gap: pytest.approx(free)
    }


@pytest.mark.parametrize(
    ("layer", "style", "organic", "gap"),
    [
        (0.2, "tree", {"tree"}, 0.2),
        (0.2, "auto", {"tree", "auto"}, 0.2),
        (0.2, "grid", {"tree", "auto"}, 0.28),
        (0.2, "tree", set(), 0.28),
        (0.1, "tree", {"tree"}, 0.2),
        (0.1, "grid", {"tree"}, 0.14),
    ],
)
def test_under_organic_trees_the_gap_comes_in_whole_layers(
    layer: float, style: str, organic: set[str], gap: float
) -> None:
    """Organische Bäume legen alle sechs Programme der Orca-Familie und
    PrusaSlicer auf die Schichten des Modells, auch mit eigener
    Stützschichthöhe (RM-622): PETG bekam 0,28 mm geschrieben und 0,2 gedruckt.
    Unter den Arten, die das Programm organisch druckt (``organic``, auch
    „automatisch“ bei Elegoo und Bambu), rät Solidon ganze Schichten — bei 0,1er
    Schichten zwei statt 0,14, das gerundet unter das Minimum fiele. Unter
    Gitter und wo „Baum“ keiner ist (SuperSlicer), bleibt der freie Wert."""
    profile = petg()
    asked: dict[str, object] = {
        "layers.layer_height": layer,
        "support.style": style,
        "support.z_gap": 0.6,
    }
    assert _support_advice(
        table(),
        profile,
        asked,
        flavour="orca",
        paths=("support.z_gap",),
        organic=frozenset(organic),
    ) == {"support.z_gap": pytest.approx(gap)}


def bearded_table(pins: int, side: float = 0.6) -> MeshData:
    """Der Tisch mit einem Bart: ``pins`` dünne Stifte hängen unter der Platte,
    jeder beginnt als Insel mit ``side`` mal ``side`` mm² — die Bartstacheln am
    Kinn des Drachen im Kleinen (RM-584)."""
    places = [
        (x, y)
        for x in (-18.0, -15.0, -12.0, -9.0, -6.5, 6.5, 9.0, 12.0, 15.0, 18.0)
        for y in (-18.0, -15.0, -12.0, -9.0, -6.5, 6.5, 9.0, 12.0, 15.0, 18.0)
    ][:pins]
    assert len(places) == pins, "so viele Stifte trägt die Platte nicht"
    return on_bed(
        brick(40.0, 40.0, 5.0, (0.0, 0.0, 2.5)),
        brick(10.0, 10.0, 20.0, (0.0, 0.0, 15.0)),
        brick(40.0, 40.0, 5.0, (0.0, 0.0, 27.5)),
        *(brick(side, side, 4.2, (x, y, 23.1)) for x, y in places),
    )


def test_small_islands_are_counted_as_tips() -> None:
    """Jeder Stift unter 1 mm² beginnt als Insel ohne Trennschicht an seiner
    Baumspitze (``minimum_roof_area``, RM-584); ein Stift von 1,44 mm² nicht."""
    assert tip_islands(slice_body(bearded_table(12), 0.2)) == 12
    assert tip_islands(slice_body(bearded_table(12, side=1.2), 0.2)) == 0
    assert tip_islands(slice_body(table(), 0.2)) == 0, "die Platte ist keine Insel"


@pytest.mark.parametrize(
    ("layer", "style", "flavour", "organic", "gap"),
    [
        (0.2, "tree", "orca", {"tree"}, 0.4),
        (0.2, "auto", "orca", {"tree", "auto"}, 0.4),
        (0.12, "tree", "orca", {"tree"}, 0.36),
        (0.2, "tree", "cura", set(), 0.4),
        (0.2, "tree", "prusa", {"tree"}, 0.4),
    ],
)
def test_many_tips_under_trees_get_air_in_whole_layers(
    layer: float, style: str, flavour: str, organic: set[str], gap: float
) -> None:
    """Roberts Drache (PLA, 0,2 mm): Am Kinn und an den Kopfstacheln stand jede
    Baumspitze eine Schicht unter dem Modell und schweißte an. Zwei Schichten
    senkten die Kontaktfläche um 88 und 96 Prozent, in ElegooSlicer, PrusaSlicer
    und Cura gemessen (RM-584). Der Rat gilt über dem Höchstwert des Materials
    (0,25 mm) und in ganzen Schichten, mindestens zwei."""
    proposed = _support_advice(
        bearded_table(advise.TIP_ISLANDS),
        profiles.make_profile("centauri-carbon-2", "pla"),
        {"layers.layer_height": layer, "support.style": style, "support.z_gap": layer},
        flavour=flavour,
        paths=("support.z_gap",),
        organic=frozenset(organic),
    )
    assert proposed == {"support.z_gap": pytest.approx(gap)}


@pytest.mark.parametrize("case", ["few", "grid", "petg", "no slicer"])
def test_tips_need_many_islands_trees_and_a_measured_material(case: str) -> None:
    """Gegenproben: Wenige Inseln (ein Stift, eine Nase), Gitterstützen ohne
    Spitzen, ein Material ohne gemessenen Spitzenabstand und ein Rat ohne
    Slicer behalten den Abstand des Materials. Gefragt an :func:`advise.tip_gap`
    selbst: Mit hundert Stiften schlägt der Rat Bäume vor, und unter dem
    vorgeschlagenen Stil gälte der Abstand wieder."""
    pins = advise.TIP_ISLANDS - 1 if case == "few" else advise.TIP_ISLANDS
    need = advise.support_need(slice_body(bearded_table(pins), 0.2))
    material = profiles.material("petg" if case == "petg" else "pla")
    style = "grid" if case == "grid" else "tree"
    flavour = None if case == "no slicer" else "orca"
    organic = frozenset() if case == "no slicer" else frozenset({"tree"})

    assert need.tips == pins
    assert advise.tip_gap(0.2, material, need, flavour, style, organic) is None
    if case == "few":
        more = advise.support_need(slice_body(bearded_table(advise.TIP_ISLANDS), 0.2))
        assert advise.tip_gap(0.2, material, more, flavour, style, organic) == pytest.approx(0.4), (
            "die Gegenprobe: eine Insel mehr, und der Abstand gilt"
        )


def test_proposed_trees_bring_whole_layers_along() -> None:
    """Schlägt der Rat selbst Bäume vor (Stützen auf dem Modell, RM-581), fragt
    er den Abstand mit ihnen (RM-622): PETG am Kinn bei 0,1er Schichten mit
    0,14 mm, dem freien Wert, bekommt 0,2 vorgeschlagen — gerundet lägen die
    0,14 unter dem Minimum."""
    profile = petg()
    settings = print_settings.resolve(profile)
    for path, value in (("layers.layer_height", 0.1), ("support.z_gap", 0.14)):
        settings = print_settings.with_path(settings, path, value)
    entries = advise.advise(
        settings,
        profile,
        slice_body(chin_over_chest(), 0.1),
        flavour="orca",
        organic=frozenset({"tree"}),
    )
    proposed = {entry.path: entry.value for entry in entries}
    assert proposed.get("support.style") == "tree"
    assert proposed.get("support.z_gap") == pytest.approx(0.2)


@pytest.mark.parametrize(("flavour", "whole_layers"), [("orca", True), ("cura", False)])
def test_a_gap_between_two_layers_is_proposed_where_the_slicer_rounds(
    flavour: str, whole_layers: bool
) -> None:
    """0,2 mm liegen bei 0,08er Schichten im Band um 0,16, sind aber zweieinhalb
    Schichten. Wo der Slicer in ganzen Schichten rechnet — Cura, die
    Orca-Familie neben einem Reinigungsturm —, druckt er sie nicht so, und der
    Rat nennt die ganze Schicht (RM-622). Ohne Rundung bleibt ein Wert im Band
    beim Hersteller."""
    pla = profiles.make_profile("centauri-carbon-2", "pla")
    gap = "support.z_gap"
    between: dict[str, object] = {"layers.layer_height": 0.08, gap: 0.2}
    whole: dict[str, object] = {"layers.layer_height": 0.08, gap: 0.16}

    assert _support_advice(
        table(), pla, between, flavour=flavour, paths=(gap,), whole_layers=whole_layers
    ) == {gap: pytest.approx(0.16)}
    # 0,2 liegt genau auf der Bandgrenze (1,25-mal 0,16), 0,18 mitten darin.
    assert _support_advice(
        table(),
        pla,
        {**between, gap: 0.18},
        flavour=flavour,
        paths=(gap,),
        whole_layers=whole_layers,
    ) == {gap: pytest.approx(0.16)}
    assert (
        _support_advice(
            table(), pla, whole, flavour=flavour, paths=(gap,), whole_layers=whole_layers
        )
        == {}
    )
    assert (
        _support_advice(table(), pla, {**between, gap: 0.11}, flavour="orca", paths=(gap,)) == {}
    ), "ohne Turm gilt 0,11 genau und liegt im Band um 0,10"


def test_the_interface_follows_the_ceiling_and_where_supports_stand() -> None:
    """Unter einer großen flachen Decke eine dichte Trennschicht mit drei Lagen,
    unter kleinen und gewölbten Flächen eine lockere mit zwei; wo die Stütze auf
    dem Modell steht, zwei untere Lagen (RM-583, Recherche Nr. 2 und 3). Das
    Profil des MK4S führt unten 0, Kobra 2 und MK4S oben 0,2 mm und drei Lagen,
    Elegoo 0,5 mm und zwei."""
    pla = profiles.make_profile("centauri-carbon-2", "pla")
    prusa_like = {
        "support.interface_spacing": 0.2,
        "support.interface_layers": 3,
        "support.bottom_interface_layers": 0,
    }
    elegoo_like = {
        "support.interface_spacing": 0.5,
        "support.interface_layers": 2,
        "support.bottom_interface_layers": 2,
    }

    assert _support_advice(table(), pla, elegoo_like) == {
        "support.interface_spacing": 0.2,
        "support.interface_layers": 3,
    }, "die Tischplatte ist eine flache Decke"
    assert _support_advice(chin_over_chest(), pla, prusa_like) == {
        "support.interface_spacing": 0.5,
        "support.interface_layers": 2,
        "support.bottom_interface_layers": 2,
    }, "das Kinn ist klein und gewölbt und steht auf der Brust"
    assert _support_advice(chin_over_chest(), pla, elegoo_like) == {}, "Elegoo passt dort"


def test_without_material_values_the_gap_stays_with_the_maker() -> None:
    """Für TPU fehlt eine Quelle zum Stützabstand: kein Rat, der Abstand bleibt
    beim Hersteller. ABS trägt die Werte von PLA aus der Tabelle, volle Kühlung
    nur PETG — ein eigener Materialwert, nicht der Abstandsfaktor (RM-583,
    Review)."""
    tpu = profiles.make_profile("centauri-carbon-2", "tpu-95a")
    abs_profile = profiles.make_profile("centauri-carbon-2", "abs")
    gap, cooling = "support.z_gap", "cooling.support_interface_cooling"

    assert advise.support_gap_target(0.2, tpu.material) is None
    assert gap not in _support_advice(table(), tpu, {gap: 0.6}, paths=(gap,))
    assert _support_advice(table(), abs_profile, {gap: 0.6}, paths=(gap,)) == {
        gap: pytest.approx(0.2)
    }
    assert cooling not in _support_advice(table(), abs_profile, {}, paths=(cooling,))
    assert petg().material.support_interface_cooling


def test_supports_on_the_bed_need_no_interface_below() -> None:
    """Untere Trennschichten braucht nur eine Stütze, die auf dem Modell steht
    (RM-583, Review): Ein Pilz, dessen Stütze auf dem Bett steht, bekommt keine;
    der Tisch, dessen Stütze auf dem Sockel steht, zwei."""
    pla = profiles.make_profile("centauri-carbon-2", "pla")
    bare = {"support.bottom_interface_layers": 0}
    mushroom = on_bed(
        brick(10.0, 10.0, 20.0, (0.0, 0.0, 10.0)), brick(40.0, 40.0, 2.0, (0.0, 0.0, 21.0))
    )
    below = "support.bottom_interface_layers"

    assert below not in _support_advice(mushroom, pla, bare, paths=(below,))
    assert _support_advice(table(), pla, bare, paths=(below,)) == {below: 2}


def test_sticky_material_gets_a_cool_interface() -> None:
    """PETG haftet an sich selbst; volle Kühlung an der Trennschicht löst die
    Stütze leichter (RM-583, Recherche Nr. 7). PLA kühlt ohnehin voll."""
    cooling = "cooling.support_interface_cooling"
    pla = profiles.make_profile("centauri-carbon-2", "pla")
    assert _support_advice(table(), petg(), {}, paths=(cooling,)) == {cooling: True}
    assert _support_advice(table(), pla, {}, paths=(cooling,)) == {}


def _contact_advice(
    body: MeshData, profile: Profile, values: dict[str, object]
) -> tuple[PrintSettings, list[SettingAdvice]]:
    """Der Rat eines Körpers zum Stützkontakt, wie der Druckdialog ihn sammelt."""
    settings = print_settings.resolve(profile)
    for path, value in values.items():
        settings = print_settings.with_path(settings, path, value)
    entries = advise.advise(settings, profile, slice_body(body, 0.2))
    return settings, [entry for entry in entries if entry.path in advise.CONTACT_PATHS]


def test_a_body_that_differs_keeps_its_contact_row() -> None:
    """PLA will bei 0,15 mm Schicht 0,15 mm Abstand, PETG ist mit 0,2 zufrieden;
    das Kinn will eine lockere Trennschicht, der Tisch die dichte der Platte. Nach
    dem größten Wert zusammengeführt verschwand die Zeile, und kein Teil bekam
    seinen Wert (RM-583, Review). Getrennt zusammengeführt bleibt sie."""
    pla = profiles.make_profile("centauri-carbon-2", "pla")
    fine = {"layers.layer_height": 0.15, "support.z_gap": 0.2}
    groups = [_contact_advice(table(), pla, fine), _contact_advice(table(), petg(), fine)]

    def rows(**options: object) -> dict[str, object]:
        merged = advise.combine(groups[0][0], groups, **options)  # type: ignore[arg-type]
        return {entry.path: entry.value for entry in merged}

    assert "support.z_gap" not in rows(), "im Teil gilt der Wert, der beide einschließt"
    assert rows(separate=advise.CONTACT_PATHS)["support.z_gap"] == pytest.approx(0.15)

    dense = {
        "support.interface_spacing": 0.2,
        "support.interface_layers": 3,
        "support.bottom_interface_layers": 2,
    }
    groups = [_contact_advice(table(), pla, dense), _contact_advice(chin_over_chest(), pla, dense)]
    together = rows(separate=advise.CONTACT_PATHS)
    assert together["support.interface_spacing"] == pytest.approx(0.5)
    assert together["support.interface_layers"] == 2


@pytest.mark.parametrize("flavour", ["orca", "cura"])
@pytest.mark.parametrize("case", ["ceilings", "materials"])
def test_the_contact_rows_settle_after_one_round(flavour: str, case: str) -> None:
    """Der Druckdialog fragt den Stützkontakt je Körper gegen die Grundlage und
    führt ihn getrennt zusammen: Nach einmal Übernehmen kommt keine Gegenzeile
    (RM-583, Nachprüfung). Gegen die Übernahme gefragt, wechselte die Lücke
    zwischen Tisch und Kinn bei jedem Übernehmen, der Abstand zwischen PLA und
    PETG ebenso."""
    from pathlib import Path

    from app.core.export import handover

    pla = profiles.make_profile("centauri-carbon-2", "pla")
    executable = "orca-slicer.exe" if flavour == "orca" else "CuraEngine.exe"
    setup = handover.SlicerSetup(executable=Path(executable), flavour=flavour)  # type: ignore[arg-type]
    if case == "ceilings":
        bodies = [(table(), pla), (chin_over_chest(), pla)]
        values: dict[str, object] = {
            "support.interface_spacing": 0.2,
            "support.interface_layers": 3,
            "support.bottom_interface_layers": 2,
        }
    else:
        bodies = [(table(), pla), (table(), petg())]
        values = {"layers.layer_height": 0.15, "support.z_gap": 0.2}
    settings = print_settings.resolve(pla)
    for path, value in values.items():
        settings = print_settings.with_choice(settings, path, value)

    def rows(current: PrintSettings) -> dict[str, object]:
        separate, asking = handover.asked_for_contact(current, pla, setup, flavour)  # type: ignore[arg-type]
        groups = []
        for body, profile in bodies:
            entries = advise.advise(asking, profile, slice_body(body, 0.2), flavour=flavour)  # type: ignore[arg-type]
            groups.append((asking, [e for e in entries if e.path in advise.CONTACT_PATHS]))
        merged = advise.combine(current, groups, separate=separate)
        return {entry.path: entry.value for entry in merged}

    first = rows(settings)
    if flavour == "orca":
        assert first, "ein Körper weicht ab und bekommt seine Zeile"
    for path, value in first.items():
        settings = print_settings.with_accepted(settings, path, value)
    assert rows(settings) == {}, "nach dem Übernehmen keine Gegenzeile"


def test_each_part_gets_the_contact_of_its_own_material() -> None:
    """Zwei gleiche Tische auf einer Platte, einer aus PLA, einer aus PETG: Den
    Abstand bekommt jeder nach dem Material seiner Spule, nicht nach dem der
    Platte (RM-583; Robert: „immer nach dem verwendeten Material“)."""
    from app.core.export import writer
    from app.core.types import SceneObject

    profile = profiles.make_profile("centauri-carbon-2", "pla")
    settings = print_settings.resolve(profile)
    body = table()
    result = slice_body(body, 0.2)

    def gap(material: str) -> object:
        entry = SceneObject(id=material, name=material, mesh=body, material=material)
        advice = writer.part_advice(
            entry, body, settings, profile, None, {}, result=result, fit_kinds=(), flavour="orca"
        )
        return {item.path: item.value for item in advice}.get("support.z_gap")

    assert settings.support.z_gap == pytest.approx(0.2)
    assert gap("pla") is None, "PLA löst sich bei 0,2 mm schon sauber"
    assert gap("petg") == pytest.approx(0.28), "PETG haftet stärker und braucht mehr Luft"


def test_a_cantilever_in_a_narrow_pocket_is_no_channel() -> None:
    """Am Drachen galten 738 Überhangstücke als Kanaldecken, die Sperre daraus war
    mit 259 000 mm³ größer als der Drache, und im ElegooSlicer druckten Kiefer,
    Kopf und Flügelbögen ohne Stütze in die Luft (Druck Robert, 07.10.2026).

    Gefragt war nur, ob der Raum unter einem Stück schmal ist. Eine Decke
    schließt sich aber nur selbst, wenn sie aufliegt wie eine Decke — an zwei
    Stellen, am halben Rand oder ringsum. Eine Auskragung hängt an einer Seite,
    gleich wie eng es um sie ist.
    """
    result = slice_body(jaw_in_a_pocket(), 0.2)
    need = advise.support_need(result)
    model = need.model
    jaw = [
        (index, number)
        for index, layer in enumerate(result.layers)
        if 49.0 < layer.z < 51.0
        for number, piece in enumerate(layer.overhangs)
        if piece_area(piece) > 100.0
    ]

    assert jaw, "die Unterseite des Kiefers hängt über der Tasche"
    assert need.needed, "der Kiefer braucht Stützen"
    assert not model.channels, "ein Kiefer ist keine Kanaldecke"
    assert set(jaw) <= model.open_pieces, "seine Säule setzt außerhalb eines Kanals auf"
    assert channel_space(result, model, LINE) == [], "also sperrt nichts seine Stütze"
    entries = advise.advise(print_settings.resolve(petg()), petg(), result)
    assert "support.block_channels" not in {entry.path for entry in entries}


@pytest.mark.parametrize("underside_at_wall", [47.0, 48.0])
def test_a_sloped_cantilever_does_not_hold_on_to_itself(underside_at_wall: float) -> None:
    """Eine gewölbte Unterseite zerfällt im Schnitt in Streifen, und unter dem
    Streifen k+1 liegen die Streifen 1 bis k derselben Decke. Zählte dieses
    Material als Auflage, galten die Seiten des Kiefers als gehalten: Er wurde
    Kanal, und eine Sperre nahm ihm bis zu 187 von 288 mm² Stütze (Review vom
    08.10.2026, Unterseite 47 und 48 mm an der Wand).
    """
    result = slice_body(jaw_in_a_pocket(underside_at_wall), 0.2)
    need = advise.support_need(result)
    model = need.model
    jaw = [
        (index, number)
        for index, layer in enumerate(result.layers)
        if underside_at_wall - 0.5 < layer.z < 51.0
        for number, piece in enumerate(layer.overhangs)
        if piece_area(piece) > 0.5
    ]

    assert len(jaw) > 5, "die Unterseite zerfällt in Streifen"
    assert need.needed, "der Kiefer braucht Stützen"
    assert not set(jaw) & model.channels, "auch ein gewölbter Kiefer ist keine Kanaldecke"
    assert channel_space(result, model, LINE) == [], "also sperrt nichts seine Stütze"


@pytest.mark.parametrize(("underside_at_wall", "angle"), [(45.0, 60.0), (44.0, 60.0), (42.0, 50.0)])
def test_a_steep_cantilever_does_not_hold_on_to_its_own_bands(
    underside_at_wall: float, angle: float
) -> None:
    """Zwischen den Streifen einer schrägen Unterseite liegt je Schicht ein Band
    der Überhangzugabe: Material derselben Decke, aber in keinem Stück. Bei
    60° (ElegooSlicer, OrcaSlicer) reicht es ab gut 15° Neigung in das Fenster
    des nächsten Streifens, und die Seiten des Kiefers galten wieder als
    gehalten (Review 2 vom 08.10.2026)."""
    result = slice_body(jaw_in_a_pocket(underside_at_wall), 0.2, overhang_angle=angle)
    model = model_support(result)
    jaw = [
        (index, number)
        for index, layer in enumerate(result.layers)
        if underside_at_wall - 0.5 < layer.z < 51.0
        for number, piece in enumerate(layer.overhangs)
        if piece_area(piece) > 0.5
    ]

    assert len(jaw) > 5, "die Unterseite zerfällt in Streifen"
    assert not set(jaw) & model.channels, "auch ein steiler Kiefer ist keine Kanaldecke"


def sloped_shelf_over_a_trench() -> MeshData:
    """Eine Konsole von 40 mm Breite, die 14 mm aus einer Rückwand ragt, ihre
    Unterseite mit 17° von 40 mm an der Wand ansteigend, über einem Graben von
    26 mm zwischen Rückwand und einer Lippe vorn — der Raum darunter fasst
    keinen Kreis von 30 mm."""
    rise = 14.0 * math.tan(math.radians(17.0))
    head = trimesh.convex.convex_hull(
        [
            (x, y, z)
            for x in (-20.0, 20.0)
            for y, z in ((15.0, 40.0), (1.0, 40.0 + rise), (15.0, 48.0), (1.0, 48.0))
        ]
    )
    return on_bed(
        brick(100.0, 60.0, 4.0, (0.0, 0.0, 2.0)),
        brick(100.0, 10.0, 60.0, (0.0, 20.0, 34.0)),
        brick(100.0, 4.0, 42.0, (0.0, -13.0, 25.0)),
        head,
    )


def test_a_sloped_shelf_over_a_narrow_trench_keeps_its_supports() -> None:
    """Die Konsole hängt nur an der Wand. Galt ihre Unterseite als Kanaldecke,
    fiel sie aus dem Stützbedarf, und weil sie ``worth_support`` genügt, deckte
    die Sperre sie ganz zu (Review 2 vom 08.10.2026: 21 gesperrte Säulen,
    100 % ihrer Unterseite im Sperrraum)."""
    result = slice_body(sloped_shelf_over_a_trench(), 0.2, overhang_angle=60.0)
    need = advise.support_need(result)
    under = unary_union(
        [
            ShapelyPolygon(piece.outline, piece.holes)
            for layer in result.layers
            if 39.5 < layer.z < 48.0
            for piece in layer.overhangs
        ]
    )

    assert under.area > 150.0, "die Unterseite hängt frei"
    assert need.needed, "die Konsole braucht Stützen"
    assert channel_space(result, need.model, LINE) == [], "und keine Sperre nimmt sie ihr"


def _closes_over(material: ShapelyPolygon, *shapes: ShapelyPolygon, gap: float = 0.35) -> bool:
    """``_Ceilings.closes`` für gebaute Grundrisse: je Stück eine Schicht, alle
    über demselben Material."""
    from app.core.slice import analysis

    pieces = {(index + 1, 0): shape for index, shape in enumerate(shapes)}
    ceilings = analysis._Ceilings((), lambda _index: material)
    ceilings.shape = pieces.__getitem__  # type: ignore[method-assign]
    ceilings._gap = lambda _name: gap  # type: ignore[method-assign]
    return ceilings.closes(frozenset(pieces))


#: Eine Wand links der Platte 0 bis 10, eine Zugabe (0,35 mm) entfernt.
_LEFT = box(-5.0, -5.0, -0.35, 15.0)
#: Und eine unter ihr.
_BELOW = box(-5.0, -5.0, 25.0, -0.35)


@pytest.mark.parametrize(
    ("material", "plate", "spans"),
    [
        pytest.param(_LEFT, box(0.0, 0.0, 10.0, 10.0), False, id="kragplatte"),
        pytest.param(unary_union([_LEFT, _BELOW]), box(0.0, 0.0, 20.0, 6.0), False, id="eckregal"),
        pytest.param(
            unary_union([_LEFT, Point(2.0, -0.4).buffer(0.05)]),
            box(0.0, 0.0, 10.0, 10.0),
            False,
            id="stift-an-der-wurzel",
        ),
        pytest.param(
            unary_union([_LEFT, box(20.35, -5.0, 25.0, 15.0)]),
            box(0.0, 0.0, 20.0, 4.0),
            True,
            id="bruecke-zwischen-zwei-stirnseiten",
        ),
        pytest.param(
            unary_union([_LEFT, _BELOW, box(10.35, -5.0, 15.0, 15.0)]),
            box(0.0, 0.0, 10.0, 10.0),
            True,
            id="sackgasse",
        ),
    ],
)
def test_a_ceiling_closes_only_between_its_supports(
    material: ShapelyPolygon, plate: ShapelyPolygon, spans: bool
) -> None:
    """Eine Decke schließt, wenn ihr Grundriss zwischen seinen Auflagen liegt:
    zwischen zwei Stirnseiten, in einem U. Ein Eckregal an zwei angrenzenden
    Wänden hält nicht — für seine ferne Ecke gibt es keine Bahn von Wand zu
    Wand —, und ein Stift an der Wurzel einer Kragplatte macht sie nicht zur
    Brücke (Review vom 08.10.2026: beide schlossen über „halber Rand“ und
    „zwei Stellen“)."""
    assert _closes_over(material, plate) is spans


def test_a_crumb_of_the_same_ceiling_does_not_close_a_cantilever() -> None:
    """Ein Krümel derselben Decke, der im Grundriss eine eigene Fläche bildet,
    hat keinen losen Rand über der Rauschgrenze. Entschied der erste Teil, der
    schließt, schloss er die ganze Kragplatte (Review vom 08.10.2026);
    entschieden wird nach Fläche."""
    plate = box(0.0, 0.0, 10.0, 10.0)
    crumb = Point(10.6, 10.6).buffer(0.05)

    assert not _closes_over(_LEFT, plate, crumb)


def vaulted_tunnel() -> MeshData:
    """Der Block aus :func:`tunnel_block` mit einem Tunnel von 20 mm, dessen Decke
    ein Halbkreis ist: Wände bis 18 mm, Scheitel auf 28 mm, und außen die
    Kragplatte. Das Gewölbe schließt sich Schicht für Schicht von beiden Seiten,
    jeder Streifen hängt an einer Wand, erst der Scheitel an beiden.
    """
    block = brick(60.0, 40.0, 40.0, (0.0, 0.0, 20.0))
    walls = brick(20.0, 50.0, 10.0, (0.0, 0.0, 13.0))
    vault = trimesh.creation.cylinder(radius=10.0, height=50.0, sections=96)
    vault.apply_transform(trimesh.transformations.rotation_matrix(math.pi / 2.0, (1, 0, 0)))
    vault.apply_translation((0.0, 0.0, 18.0))
    arm = brick(40.0, 40.0, 5.0, (50.0, 0.0, 37.5))
    body = trimesh.boolean.union(
        [trimesh.boolean.difference([block, trimesh.boolean.union([walls, vault])]), arm]
    )
    return place_on_bed(MeshData.of(body))


def test_a_vaulted_channel_stays_a_channel_through_its_crown() -> None:
    """Die Gegenprobe zum Kiefer: Ein Gewölbe besteht bis zum Scheitel aus
    Streifen, die je an einer Wand hängen. Als Decke gefragt liegt sein
    Grundriss an beiden Wänden auf, und es bleibt Kanaldecke mit Sperre."""
    result = slice_body(vaulted_tunnel(), 0.2)
    model = model_support(result)

    assert model.channels, "das Gewölbe steht über dem Tunnelboden"
    assert model.channel_at is not None and model.channel_at[2] > 20.0
    assert channel_space(result, model, LINE), "und bekommt seine Sperre"
    entries = advise.advise(print_settings.resolve(petg()), petg(), result)
    assert [entry.value for entry in entries if entry.path == "support.block_channels"] == [True]


def balcony_beside_a_tunnel() -> MeshData:
    """Der Tunnelblock aus :func:`tunnel_block` mit einem Balkon 14 auf 12 mm auf
    22 mm Höhe an seiner Vorderseite, neben der Tunnelmündung, und einem Pfosten
    weiter vorn. Die Säule des Balkons erreicht das Bett; der Pfosten zieht die
    Hülle der Schichten über sie, und der Raum unter ihr hängt durch die
    Mündung mit dem Kanal zusammen, keine 15 mm von der Tunneldecke.

    So lagen am Drachen Flügelbögen und Kiefer neben Taschen, die als Kanäle
    galten, und die Sperre deckte sie mit.
    """
    return on_bed(
        brick(60.0, 40.0, 40.0, (0.0, 0.0, 20.0)),
        brick(40.0, 40.0, 5.0, (50.0, 0.0, 37.5)),
        brick(14.0, 12.0, 3.0, (19.0, 26.0, 23.5)),
        brick(4.0, 4.0, 30.0, (-28.0, 42.0, 15.0)),
    )


def fold_under_a_wing() -> MeshData:
    """Eine Platte von 50 mm, die aus einer Rückwand ragt, mit einer Falte darunter,
    35 mm vor der Wand: zwei Wände von 15 mm Tiefe, 5 mm auseinander, unten
    offen. Ein Pfosten weit vorn zieht die Hülle über die freie Luft neben der
    Platte.

    Der Bau des Flügels am Drachen: In einer Falte der Flughaut hängt eine echte
    Tasche, und daneben liegt offener Raum.
    """
    return on_bed(
        brick(120.0, 40.0, 4.0, (20.0, 0.0, 2.0)),
        brick(10.0, 40.0, 40.0, (-25.0, 0.0, 20.0)),
        brick(50.0, 40.0, 3.0, (5.0, 0.0, 31.5)),
        brick(2.0, 40.0, 15.0, (16.0, 0.0, 22.5)),
        brick(2.0, 40.0, 15.0, (23.0, 0.0, 22.5)),
        brick(4.0, 4.0, 30.0, (75.0, 0.0, 15.0)),
    )


def test_the_channel_space_stays_where_no_one_reaches() -> None:
    """Gesperrt wird nur Raum, an den man nicht hinkommt: zu eng für den Kreis
    der Kanalfrage oder ringsum umschlossen. Am Drachen hing in einer Falte des
    Flügels eine echte Tasche; ihr Umkreis lief aus ihr heraus in den offenen Raum
    unter dem Flügel, und Cura stützte dort 85 statt 100 % der Überhangfläche
    (08.10.2026)."""
    result = slice_body(fold_under_a_wing(), 0.2)
    model = model_support(result)
    slabs = channel_space(result, model, LINE)

    assert model.channel_columns, "die Decke der Falte ist Kanal und lohnt eine Sperre"
    assert slabs
    for _low, _high, region in slabs:
        low_x, _low_y, high_x, _high_y = region.bounds
        # Die Falte liegt zwischen x = 17 und x = 22.
        assert low_x >= 17.0 - LINE - 1e-6 and high_x <= 22.0 + LINE + 1e-6, (low_x, high_x)


def test_the_channel_space_leaves_a_column_to_the_bed_free() -> None:
    """Die Sperre hält Stützen aus dem Kanal fern, nicht von einer Decke, die sie
    braucht — auch dann nicht, wenn deren Säule das Bett erreicht. Ausgespart
    wurden bis hierher nur Säulen, die auf dem Modell aufsetzen."""
    body = trimesh.boolean.difference(
        [balcony_beside_a_tunnel().raw, brick(20.0, 50.0, 20.0, (0.0, 0.0, 18.0))]
    )
    result = slice_body(MeshData.of(body), 0.5)
    model = model_support(result)
    # Was der Balkon zu stützen hat: sein Überhangstück, ohne den Streifen der
    # Überhangzugabe an der Wand, der sich selbst trägt.
    under = unary_union(
        [
            ShapelyPolygon(piece.outline, piece.holes)
            for layer in result.layers
            if 21.0 < layer.z < 23.0
            for piece in layer.overhangs
            if piece_area(piece) > 50.0
        ]
    )
    assert under.area > 100.0, "der Balkon hängt über dem Bett"

    assert model.channels, "die Tunneldecke ist Kanal"
    slabs = channel_space(result, model, LINE)
    assert slabs, "der Tunnel bleibt gesperrt"
    beside = [(low, high, region) for low, high, region in slabs if low <= 22.0 <= high + 1.0]
    assert beside, "auf Höhe des Balkons sperrt die Scheibe den Tunnel"
    for low, high, region in beside:
        # Mit dem Zuschlag: Er kommt vor dem Aussparen, nicht danach.
        assert region.intersection(under).area == pytest.approx(0.0, abs=1e-6), (low, high)


def sloped_balcony_beside_a_tunnel(depth: float) -> MeshData:
    """:func:`balcony_beside_a_tunnel` mit hohlem Tunnel, der Balkon aber 16 mm
    breit, ``depth`` mm tief und mit schräger Unterseite: von 22 mm an der Wand
    mit 18° zur Kante ansteigend. Im Schnitt zerfällt sie in Streifen unter
    10 mm²; ihre Säulen erreichen das Bett."""
    rise = depth * math.tan(math.radians(18.0))
    balcony = trimesh.convex.convex_hull(
        [
            (x, y, z)
            for x in (11.0, 27.0)
            for y, z in (
                (20.0, 22.0),
                (20.0 + depth, 22.0 + rise),
                (20.0, 27.0),
                (20.0 + depth, 27.0),
            )
        ]
    )
    body = trimesh.boolean.union(
        [
            brick(60.0, 40.0, 40.0, (0.0, 0.0, 20.0)),
            brick(40.0, 40.0, 5.0, (50.0, 0.0, 37.5)),
            balcony,
            brick(4.0, 4.0, 30.0, (-28.0, 42.0, 15.0)),
        ]
    )
    tunnel = brick(20.0, 50.0, 20.0, (0.0, 0.0, 18.0))
    return place_on_bed(MeshData.of(trimesh.boolean.difference([body, tunnel])))


@pytest.mark.parametrize(("depth", "spared"), [(12.0, True), (4.0, False)])
def test_a_sloped_underside_beside_a_channel_is_spared_as_a_field(
    depth: float, spared: bool
) -> None:
    """Ausgespart wird, was selbst Stütze braucht, auch eine schräge Unterseite in
    Streifen unter 10 mm², deren Decke als Feld ``worth_support`` genügt — der
    Kiefer, die Flughaut (RM-570). Was sich selbst trägt, bleibt gesperrt: An der
    Mündung des Wasserkanals holte der ElegooSlicer ein solches Stück mit einem Ast
    quer durch den Kanal (1,4 m). Beides hielt bis zu Review 3 kein Test."""
    result = slice_body(sloped_balcony_beside_a_tunnel(depth), 0.2)
    model = model_support(result)
    strips = [
        piece
        for layer in result.layers
        if 22.0 < layer.z < 27.0
        for piece in layer.overhangs
        if ShapelyPolygon(piece.outline).centroid.y > 20.0
    ]
    assert len(strips) > 3, "die Unterseite des Balkons zerfällt in Streifen"
    assert max(piece_area(strip) for strip in strips) < 10.0
    assert model.channel_columns, "die Tunneldecke ist Kanal und lohnt eine Sperre"

    kept = [outline for outline, _low, _high in model.bed_columns if outline in strips]
    if spared:
        assert len(kept) == len(strips), "das Feld behält seine Säulen"
    else:
        assert not kept, "der kleine Balkon trägt sich selbst und bleibt unter der Sperre"


def hood_over_a_tunnel_mouth() -> MeshData:
    """Der Tunnelblock aus :func:`tunnel_block` (20 mm), dessen Decke vor der
    Mündung als Haube 4 mm weiterläuft, mit 18° ansteigend: eine Decke aus dem
    Kanalstück und offenen Streifen, deren Säulen das Bett erreichen — wie die
    Mündung des Wasserkanals der Waschschüssel."""
    rise = 4.0 * math.tan(math.radians(18.0))
    hood = trimesh.convex.convex_hull(
        [
            (x, y, z)
            for x in (-10.0, 10.0)
            for y, z in ((20.0, 28.0), (24.0, 28.0 + rise), (20.0, 32.0), (24.0, 32.0))
        ]
    )
    return place_on_bed(MeshData.of(trimesh.boolean.union([tunnel_block(20.0).raw, hood])))


def test_an_open_strip_at_a_channel_mouth_is_asked_without_the_channel() -> None:
    """Die Aussparung fragt eine Decke ohne ihre Kanalstücke, wie der Stützbedarf
    (``largest_sloped_patch``). Mit ihnen galt an der Mündung des Wasserkanals der
    Waschschüssel jedes offene Stück als stützbedürftig, auch eines von 11 mm², das
    sich selbst trägt — gehalten hat es nur, dass im umschlossenen Raum nichts
    ausgespart wird (Review 3 vom 08.10.2026)."""
    result = slice_body(hood_over_a_tunnel_mouth(), 0.2)
    model = model_support(result)
    hood = [
        piece
        for layer in result.layers
        if 28.0 < layer.z < 30.0
        for piece in layer.overhangs
        if ShapelyPolygon(piece.outline).centroid.y > 20.0
    ]

    assert model.channel_columns, "die Tunneldecke ist Kanal und lohnt eine Sperre"
    assert hood, "die Haube hängt in Streifen vor der Mündung"
    assert model.bed_columns, "die Kragplatte behält ihre Säulen zum Bett"
    assert not [outline for outline, _low, _high in model.bed_columns if outline in hood]


def gabled_slot(length: float) -> trimesh.Trimesh:
    """Ein Block mit einem Schlitz von 8 mm Weite und Satteldach, 18° steil: Die
    Decke zerfällt im Schnitt in Streifen von gut 16 mm², zusammen über 150."""
    body = brick(28.0, length, 20.0, (0.0, 0.0, 10.0))
    rise = 4.0 * math.tan(math.radians(18.0))
    cut = trimesh.convex.convex_hull(
        [
            (x, y, z)
            for y in (-length / 2.0 - 5.0, length / 2.0 + 5.0)
            for x, z in ((-4.0, 4.0), (4.0, 4.0), (-4.0, 10.0), (4.0, 10.0), (0.0, 10.0 + rise))
        ]
    )
    return trimesh.boolean.difference([body, cut])


def test_a_sloped_channel_vault_asks_for_no_supports() -> None:
    """Ein Kanalgewölbe in Streifen trägt sich selbst und bekommt seine Sperre —
    die Waschschüssel vom 25.09.2026 mit schrägem Dach."""
    result = slice_body(place_on_bed(MeshData.of(gabled_slot(40.0))), 0.2)
    need = advise.support_need(result)

    assert need.model.channels, "das Satteldach ist Kanaldecke"
    assert channel_space(result, need.model, LINE), "und lohnt eine Sperre"
    assert not need.needed, "es trägt sich selbst"


def test_a_channel_vault_is_blocked_by_its_largest_piece_not_its_field() -> None:
    """Die Sperre fragt ``worth_support`` am größten Stück, nicht am Feld wie
    Stützbedarf und Aussparung: Wo eine Decke über Stütze oder keine entscheidet,
    fällt der Zweifel auf Stütze. Als Feld gefragt, sperrte der Drache bei 130 %
    eine zweite Decke (149 mm² in 48 Streifen) und nahm fast doppelt so viel
    stützbedürftige Fläche unter die Sperre (Review 3). Hier dasselbe am
    Satteldach bei 60°: als Feld über 100 mm², als Stück und Summe darunter."""
    result = slice_body(place_on_bed(MeshData.of(gabled_slot(40.0))), 0.2, overhang_angle=60.0)
    model = model_support(result)

    assert model.channels, "das Satteldach ist Kanaldecke"
    assert largest_sloped_patch(result) > OVERHANG_LAYER_WORTH_SUPPORT, "als Feld trüge es"
    assert not model.channel_columns, "nach dem größten Stück lohnt es keine Sperre"


def test_a_strip_at_a_channel_mouth_does_not_borrow_the_channel_for_its_field() -> None:
    """Der Stützbedarf fragt eine Decke als Feld ohne ihre Kanalstücke. Mit ihnen
    lieh sich die Haube vor der Tunnelmündung die ganze Tunneldecke, und ein
    Kanal schaltete die Stützen wieder ein — der Fehler der Waschschüssel vom
    25.09.2026, auf dem Weg über das Feld (Review 3). Haube und ein schräger Sims
    an der Seite bringen zusammen über 100 mm², damit das Feld gefragt wird."""
    rise = 4.0 * math.tan(math.radians(18.0))
    hood = trimesh.convex.convex_hull(
        [
            (x, y, z)
            for x in (-10.0, 10.0)
            for y, z in ((20.0, 28.0), (24.0, 28.0 + rise), (20.0, 32.0), (24.0, 32.0))
        ]
    )
    ledge = trimesh.convex.convex_hull(
        [
            (x, y, z)
            for y in (-14.0, 14.0)
            for x, z in ((30.0, 20.0), (34.0, 20.0 + rise), (30.0, 24.0), (34.0, 24.0))
        ]
    )
    body = trimesh.boolean.union([bare_tunnel(20.0).raw, hood, ledge])
    need = advise.support_need(slice_body(place_on_bed(MeshData.of(body)), 0.2))

    assert need.model.channels, "die Tunneldecke ist Kanal"
    assert need.overhang > OVERHANG_LAYER_WORTH_SUPPORT, "die Feldfrage wird gestellt"
    assert not need.needed, "Haube und Sims tragen sich selbst"


def column_with_flange_and_arm(arm: float) -> MeshData:
    """Eine Säule 30 auf 30 mm auf einer Grundplatte, auf 20 mm Höhe ringsum ein
    Flansch von 2,5 mm (325 mm² Überhang an einem Stück), und knapp darüber an
    einer Seite ein Arm von ``arm`` mm — die Ränder der Plattformen am
    Eiffelturm und, wenn ``arm`` lang ist, ein Überhang, der Stütze braucht."""
    parts = [
        brick(60.0, 60.0, 2.0, (0.0, 0.0, 1.0)),
        brick(30.0, 30.0, 40.0, (0.0, 0.0, 20.0)),
        brick(35.0, 35.0, 1.0, (0.0, 0.0, 20.5)),
    ]
    if arm > 0.0:
        parts.append(brick(arm, 10.0, 2.0, (15.0 + arm / 2.0, 0.0, 21.4)))
    return on_bed(*parts)


@pytest.mark.parametrize(("arm", "needed"), [(0.0, False), (15.0, True)])
def test_a_ledge_of_a_few_millimetres_carries_itself(arm: float, needed: bool) -> None:
    """Am Eiffelturm (08.10.2026, ohne Stützen gedacht) verlangte der Rat Stützen
    wegen der Ränder der Plattformen, oben ein Kranz von 2,6 mm, und der
    ElegooSlicer stellte 831 m Baum außen am Turm hoch. Was nicht weiter als
    ``LEDGE_REACH`` über sein Material ragt, trägt sich selbst — auch als ein
    Stück über 100 mm², und der Prüfbericht meldet es nicht. Ein Arm von 15 mm
    trägt sich nicht."""
    from app.core.slice import findings

    result = slice_body(column_with_flange_and_arm(arm), 0.2)
    flange = {
        (index, number)
        for index, layer in enumerate(result.layers)
        if 19.5 < layer.z < 20.5
        for number, _piece in enumerate(layer.overhangs)
    }
    assert flange, "der Flansch hängt über"
    assert max(piece_area(result.layers[i].overhangs[n]) for i, n in flange) > 100.0
    assert flange <= ledges(result), "der Flansch ist ein Rand"
    assert advise.support_need(result).needed is needed
    if not needed:
        assert not findings.overhang_findings("obj_1", result), "der Bericht meldet keinen Rand"


def test_the_ledge_question_asks_only_the_named_ceilings() -> None:
    """``ledges(result, only)`` fragt nur die Decken dieser Stücke und antwortet
    für sie wie die volle Frage: Der Prüfbericht braucht sie für eine Handvoll,
    über alle Stücke kostet sie am Eiffelturm 7,5 s (Review vom 08.10.2026).
    Abbrechbar je Decke, eine abgebrochene Antwort wird nicht gemerkt."""
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal

    result = slice_body(column_with_flange_and_arm(15.0), 0.2)
    pieces = {
        (index, number)
        for index, layer in enumerate(result.layers)
        for number in range(len(layer.overhangs))
    }
    flange = {name for name in pieces if 19.5 < result.layers[name[0]].z < 20.5}
    arm = {
        name
        for name in pieces
        if result.layers[name[0]].z > 20.5
        and ShapelyPolygon(result.layers[name[0]].overhangs[name[1]].outline)
        .representative_point()
        .x
        > 18.0
    }
    assert flange and arm
    token = CancelSignal()
    token.cancel()
    with pytest.raises(OperationCancelled):
        ledges(result, cancelled=token)

    asked = ledges(result, frozenset(arm))
    assert not asked, "nach dem Arm gefragt, kommt kein Flansch zurück"
    assert flange <= ledges(result, frozenset(flange))
    full = ledges(result)
    assert flange <= full and not arm & full, "die volle Frage sagt dasselbe"


def test_build_plate_says_that_what_rests_on_the_model_carries_itself() -> None:
    """Setzen auf dem Modell nur Ränder auf, die sich selbst tragen, heißt es „nur
    vom Bett“ — aber nicht mit „Stützen erreichen alle Überhänge vom Druckbett
    aus“: Unter dem Rand steht dann keine (Review vom 08.10.2026). Ein Rand zählt
    nicht zu dem, was auf dem Modell aufsetzt (``open_area``)."""
    body = on_bed(
        brick(34.0, 34.0, 2.0, (0.0, 0.0, 1.0)),
        brick(30.0, 30.0, 40.0, (0.0, 0.0, 20.0)),
        brick(35.0, 35.0, 1.0, (0.0, 0.0, 20.5)),
        brick(15.0, 10.0, 2.0, (25.0, 0.0, 21.4)),
    )
    result = slice_body(body, 0.2)
    model = model_support(result)

    assert model.ledges_on_model, "der Flansch setzt auf der Grundplatte auf"
    assert model.open_area < OVERHANG_LAYER_WORTH_SUPPORT, "aber er zählt nicht als Auflage"
    entries = advise.advise(print_settings.resolve(petg()), petg(), result)
    placement = [entry for entry in entries if entry.path == "support.placement"]
    assert [entry.value for entry in placement] == ["build_plate"]
    assert "tragen sich selbst" in str(placement[0].reason)


def test_a_shoulder_around_an_opening_is_no_ledge() -> None:
    """Eine Schulter, die in einem Becher von 60 mm 2,5 mm nach innen ragt, ist
    kein Rand: Ihre Bahnen laufen quer über die Öffnung, 48 mm frei — der
    Schaden des Gewürzbehälters (``analysis._bridge_width``). Sie braucht
    Stützen, und der Bericht nennt die Brücke. Als Rand bekam sie im
    Prüfling weder das eine noch das andere (zweites Review vom 08.10.2026).
    Dasselbe im Stützschnitt der Übergabe, der keine Brückenweiten misst: Dort
    galt die Schulter als Rand, und „Ränder ohne Stütze“ sperrte ihre Stütze
    (viertes Review)."""
    cup = _cup_with_a_step(2.5)

    def shoulder_of(result: SliceResult) -> set[tuple[int, int]]:
        return {
            (index, number)
            for index, layer in enumerate(result.layers)
            for number, piece in enumerate(layer.overhangs)
            if piece.holes and piece_area(piece) > 100.0
        }

    result = slice_body(cup, 0.2)
    shoulder = shoulder_of(result)

    assert shoulder, "die Schulter hängt als Ring über"
    assert max(layer.bridge_width for layer in result.layers) > SPAN_INTERESTING
    assert not shoulder & ledges(result), "ein Ring um eine freie Öffnung ist kein Rand"
    assert advise.support_need(result).needed, "die Schulter braucht Stützen"
    codes = {finding.code for finding in advise.located_warnings(result, petg())}
    assert "slice.long_bridge" in codes, "und der Bericht nennt die Brücke"

    lean = slice_body(cup, 0.2, "support")
    assert all(layer.bridge_width == 0.0 for layer in lean.layers), "keine Brückenweiten"
    assert shoulder_of(lean) and not shoulder_of(lean) & ledges(lean), "auch im Stützschnitt"


def test_many_outer_corners_do_not_turn_a_flange_into_supports() -> None:
    """An jeder Außenecke ragt ein Flansch von 2,6 mm um einen Splitter über die
    Reichweite (2,6 · √2 = 3,7 mm). Mit seinem Ansatz gemessen bekäme jeder
    Splitter 20 mm² Flansch, und eine gezahnte Säule mit zwanzig Ecken verlangte
    Stützen ringsum, obwohl jede Ecke so weit ragt wie am glatten Quadrat
    (viertes Review vom 08.10.2026)."""
    outline = box(-20.0, -20.0, 20.0, 20.0)
    for offset in (-8.0, 8.0):
        outline = outline.union(box(offset - 2.0, 19.0, offset + 2.0, 22.0))
        outline = outline.union(box(offset - 2.0, -22.0, offset + 2.0, -19.0))
        outline = outline.union(box(19.0, offset - 2.0, 22.0, offset + 2.0))
        outline = outline.union(box(-22.0, offset - 2.0, -19.0, offset + 2.0))
    column = trimesh.creation.extrude_polygon(outline, 30.0)
    flange = trimesh.creation.extrude_polygon(outline.buffer(2.6, join_style="mitre"), 1.0)
    flange.apply_translation((0.0, 0.0, 20.0))
    result = slice_body(on_bed(column, flange), 0.2)
    pieces = {
        (index, number)
        for index, layer in enumerate(result.layers)
        for number in range(len(layer.overhangs))
    }

    assert len(list(outline.exterior.coords)) - 1 >= 20, "zwanzig Ecken und mehr"
    assert pieces and pieces <= ledges(result), "der Flansch bleibt ein Rand"
    assert not advise.support_need(result).needed


def _crown_on_a_hollow_shaft() -> MeshData:
    """Ein hohler Schaft 40 auf 40 mm, Wand 3 mm, oben offen, auf 20 mm ringsum
    ein Kranz von 2,5 mm — er hängt an seiner Innenkante."""
    shaft = trimesh.boolean.difference(
        [brick(40.0, 40.0, 40.0, (0.0, 0.0, 20.0)), brick(34.0, 34.0, 50.0, (0.0, 0.0, 25.0))]
    )
    crown = trimesh.boolean.difference(
        [brick(45.0, 45.0, 1.0, (0.0, 0.0, 20.5)), brick(40.0, 40.0, 1.2, (0.0, 0.0, 20.5))]
    )
    return on_bed(shaft, crown)


def _cup_with_a_step(step: float) -> MeshData:
    """Ein Becher von 60 mm mit einer waagerechten Innenstufe von ``step`` mm."""
    outer = trimesh.creation.cylinder(radius=30.0, height=40.0, sections=96)
    outer.apply_translation((0.0, 0.0, 20.0))
    lower = trimesh.creation.cylinder(radius=27.0, height=26.0, sections=96)
    lower.apply_translation((0.0, 0.0, 17.0))
    upper = trimesh.creation.cylinder(radius=27.0 - step, height=12.0, sections=96)
    upper.apply_translation((0.0, 0.0, 35.0))
    return place_on_bed(
        MeshData.of(trimesh.boolean.difference([outer, trimesh.boolean.union([lower, upper])]))
    )


@pytest.mark.parametrize("body", ["kranz-am-hohlen-schaft", "stufe-0,6-mm-im-becher"])
def test_a_ring_around_a_hole_can_still_be_a_ledge(body: str) -> None:
    """Ein Ring um ein Loch ist nur dann kein Rand, wenn er eine Öffnung
    überspannt: Die Auflage fasst ihn von außen, und er ist zwei Bahnen breit.
    Der Kranz um einen hohlen Schaft hängt an seiner Innenkante, seine Bahnen
    haben außen keinen Halt; eine Stufe von 0,6 mm ist schmaler als zwei Bahnen
    der 0,4er Düse (0,84 mm) und spannt nicht. Beide verlangten mit der ersten
    Öffnungsregel Stützen (drittes Review vom 08.10.2026). Geschnitten mit der
    Breite des Profils wie Bericht, Rat und Übergabe (fünftes Review)."""
    mesh = _crown_on_a_hollow_shaft() if body == "kranz-am-hohlen-schaft" else _cup_with_a_step(0.6)
    result = slice_body(mesh, 0.2, bridge_from=petg().minimum_wall_thickness)
    rings = {
        (index, number)
        for index, layer in enumerate(result.layers)
        for number, piece in enumerate(layer.overhangs)
        if piece.holes
    }

    assert rings, "der Ring hängt über"
    assert rings <= ledges(result), "und ist ein Rand"
    assert not advise.support_need(result).needed


def test_a_step_wider_than_two_lines_is_a_shoulder() -> None:
    """Eine Stufe von 1 mm im Becher ist an der 0,4er Düse (zwei Bahnen 0,84 mm)
    schon eine Schulter: Ihre Bahnen überspannen die Öffnung, sie braucht
    Stützen — im vollen Schnitt wie im Stützschnitt der Übergabe (fünftes
    Review vom 08.10.2026)."""
    wall = petg().minimum_wall_thickness
    assert wall < 1.0
    for detail in ("full", "support"):
        result = slice_body(_cup_with_a_step(1.0), 0.2, detail, bridge_from=wall)
        step = {
            (index, number)
            for index, layer in enumerate(result.layers)
            for number, piece in enumerate(layer.overhangs)
            if piece.holes
        }
        assert step and not step & ledges(result), detail
        assert advise.support_need(result).needed, detail


def test_a_shelf_on_one_wall_is_a_ledge_and_no_bridge() -> None:
    """Eine Konsole von 2,5 mm an einer Wand hat keine beidseitig getragene
    Richtung; die Brückenweite ihrer Schicht ist deshalb ihre Diagonale, 40 mm
    (``analysis._supported_span``). Sie ist ein Rand: Weder verlangt der Rat
    Stützen über den Brückenweg, noch warnt der Bericht vor einer freien Decke —
    beide lassen Schichten aus Rändern aus (``advise._quiet_layers``)."""
    body = on_bed(
        brick(40.0, 10.0, 40.0, (0.0, 0.0, 20.0)),
        brick(40.0, 2.5, 1.0, (0.0, 5.0 + 1.25, 20.5)),
    )
    result = slice_body(body, 0.2)
    pieces = {
        (index, number)
        for index, layer in enumerate(result.layers)
        for number in range(len(layer.overhangs))
    }

    assert max(layer.bridge_width for layer in result.layers) > SPAN_INTERESTING
    assert pieces and pieces <= ledges(result), "die Konsole ist ein Rand"
    assert not advise.support_need(result).needed
    codes = {finding.code for finding in advise.located_warnings(result, petg())}
    assert "slice.long_bridge" not in codes


def _flange_with_tab(column: float, tab: float, *, flange: bool = True) -> MeshData:
    """Eine Säule ``column`` im Quadrat, auf 20 mm ringsum ein Flansch von 2,5 mm
    und an einer Seite eine Lasche 8 mm breit, ``tab`` mm über den Flansch hinaus
    (ohne Flansch ebenso weit über die Säulenwand)."""
    edge = column / 2.0 + (2.5 if flange else 0.0)
    parts = [brick(column, column, 30.0, (0.0, 0.0, 15.0))]
    if flange:
        parts.append(brick(column + 5.0, column + 5.0, 1.0, (0.0, 0.0, 20.5)))
    parts.append(brick(8.0, tab, 1.0, (0.0, edge + tab / 2.0, 20.5)))
    return on_bed(*parts)


@pytest.mark.parametrize(
    ("column", "tab", "ledge"),
    [
        # 45 mm² jenseits der Reichweite lohnen keine Stütze; als feste Grenze von
        # 10 mm² verlangten Flansch und Lasche zusammen Stützen ringsum.
        (200.0, 6.0, True),
        # 116 mm² jenseits lohnen Stütze; als 5 % des Felds (rund 200 mm²) ging die
        # Lasche am langen Flansch als Rand durch.
        (400.0, 15.0, False),
        # 92 mm² jenseits, mit ihrem Ansatz 114 mm²: Eine Lasche 14,5 mm ab der
        # Wand braucht für sich Stütze, gemessen wird sie samt Ansatz (drittes
        # Review vom 08.10.2026).
        (400.0, 12.0, False),
    ],
)
def test_what_reaches_beyond_a_ledge_is_judged_like_an_overhang(
    column: float, tab: float, ledge: bool
) -> None:
    """Was weiter als ``LEDGE_REACH`` über die Wurzel ragt, wird gemessen wie ein
    eigener Überhang (``worth_support``), nicht als Anteil des Felds und nicht an
    einer festen Grenze (zwei Reviews vom 08.10.2026). Dann bleibt die Antwort
    stimmig: Eine Lasche, die sich allein trägt, macht aus einem Flansch keinen
    Fall für Stützen."""
    sliced = slice_body(_flange_with_tab(column, tab), 0.2)
    pieces = {
        (index, number)
        for index, layer in enumerate(sliced.layers)
        if 19.5 < layer.z < 20.5
        for number, piece in enumerate(layer.overhangs)
        if ShapelyPolygon(piece.outline).bounds[3] > column / 2.0 + 2.5 + 1.0
    }

    assert pieces, "die Lasche hängt über"
    assert (pieces <= ledges(sliced)) is ledge
    assert advise.support_need(sliced).needed is not ledge
    if ledge:
        alone = slice_body(_flange_with_tab(column, tab, flange=False), 0.2)
        assert not advise.support_need(alone).needed, "die Lasche trägt sich auch allein"


def test_a_chamfer_of_52_degrees_is_no_ledge() -> None:
    """Die Fase des schrägen Fußes (4 mm unter 52° gegen die Senkrechte, Bauart
    aus ``test_advise``) ragt als Decke 124 von 281 mm² über die Reichweite: kein
    Rand, beim allgemeinen Drucker braucht sie Stützen. Ein Saum entlang des
    Umfangs hätte sie zum Rand gemacht — ihre Streifen haben zusammen zehn Meter
    Umfang (``analysis._carried``)."""
    from tests.helpers import plate_on_a_sloped_foot

    profile = profiles.make_profile("generic-220", "pla")
    settings = print_settings.resolve(profile)
    result = slice_body(
        plate_on_a_sloped_foot(52.0),
        settings.layers.layer_height,
        first_layer_height=settings.layers.first_layer_height,
        overhang_angle=profile.overhang_limit_degrees,
        bridge_from=profile.minimum_wall_thickness,
        support_volume=False,
    )

    assert any(layer.overhangs for layer in result.layers), "die Fase hängt über"
    assert not ledges(result), "keine Decke der Fase ist ein Rand"
    assert advise.support_need(result).needed


def test_a_slab_of_mere_margin_is_not_blocked() -> None:
    """Eine Lippe unter einer Bahnbreite am Ende eines Arms, der Stütze braucht,
    ist ein Rand, liegt aber ganz in der Aussparung des Arms. Übrig bliebe nur der
    Zuschlag der Sperre, unter keinem Rand: Die Scheibe entfällt, und der
    Schreiber endet ohne Befund statt mit einem Fehler (zweites Review vom
    08.10.2026)."""
    from app.core.export import writer
    from app.core.types import SceneObject

    body = on_bed(
        brick(30.0, 30.0, 40.0, (0.0, 0.0, 20.0)),
        brick(15.0, 10.0, 2.0, (22.5, 0.0, 21.4)),
        brick(0.4, 10.0, 0.4, (30.2, 0.0, 21.0)),
    )
    result = slice_body(body, 0.2)
    lip = {
        (index, number)
        for index, layer in enumerate(result.layers)
        for number, piece in enumerate(layer.overhangs)
        if ShapelyPolygon(piece.outline).bounds[0] > 29.9
    }

    assert lip and lip <= ledges(result), "die Lippe ist ein Rand"
    assert ledge_space(result, LINE) == [], "sie liegt ganz in der Aussparung des Arms"
    profile = petg()
    settings = print_settings.with_path(print_settings.resolve(profile), "support.style", "auto")
    settings = print_settings.with_path(settings, "support.spare_ledges", True)
    entry = SceneObject(id="obj_1", name="Arm", mesh=body)
    blocker, found = writer._support_blocker(entry, body, settings, profile, result=result)
    assert blocker is None and found == []


def test_the_ledge_space_is_remembered_per_line_width() -> None:
    """Der Sperrraum unter Rändern ist gemerkt wie der Kanalraum: Rat, Schätzung
    und Schreiber fragen ihn, der Rat in jeder Runde."""
    result = slice_body(column_with_flange_and_arm(0.0), 0.2)

    first, again = ledge_space(result, LINE), ledge_space(result, LINE)
    assert first and all(old[2] is new[2] for old, new in zip(first, again, strict=True)), (
        "die zweite Frage bekommt dieselben Scheiben, nicht neu gerechnete"
    )
    assert ledge_space(result, 2.0 * LINE)[0][2] is not first[0][2], "je Bahnbreite"


def test_the_report_and_the_need_stop_in_the_ledge_question() -> None:
    """Prüfbericht und Stützbedarf brechen in der Randfrage ab, ihrem teuersten
    Schritt (am Eiffelturm 7,5 s über alle Stücke). Die Kanalfrage stellt dieselbe
    Frage ohne Abbruch; deshalb kommt die Randfrage zuerst (zweites Review vom
    08.10.2026)."""
    from app.core.errors import OperationCancelled
    from app.core.scene.cancel import CancelSignal
    from app.core.slice import findings

    token = CancelSignal()
    token.cancel()
    with pytest.raises(OperationCancelled):
        findings.overhang_findings(
            "obj_1", slice_body(column_with_flange_and_arm(15.0), 0.2), cancelled=token
        )
    with pytest.raises(OperationCancelled):
        advise.support_need(slice_body(column_with_flange_and_arm(15.0), 0.2), cancelled=token)


def test_the_ledge_blocker_covers_the_ledge_and_spares_the_arm() -> None:
    """Die Sperre unter Rändern deckt deren Überhangfläche, nicht die des Arms
    gleich daneben, der Stütze braucht — sonst nähme sie ihm, was er verlangt."""
    result = slice_body(column_with_flange_and_arm(15.0), 0.2)
    slabs = ledge_space(result, LINE)
    flange = box(-17.5, -17.5, 17.5, 17.5).difference(box(-15.0, -15.0, 15.0, 15.0))
    arm = box(17.5, -5.0, 30.0, 5.0)

    assert slabs, "der Flansch bekommt eine Sperre"
    at_flange = unary_union([region for low, high, region in slabs if low <= 20.0 <= high])
    assert at_flange.intersection(flange).area > 0.8 * flange.area
    near_arm = [region for low, high, region in slabs if low <= 20.6 <= high]
    assert near_arm, "die Sperre des Flansches reicht in die Höhe des Arms"
    for region in near_arm:
        assert region.intersection(arm).area == pytest.approx(0.0, abs=1e-6)
    entries = advise.advise(print_settings.resolve(petg()), petg(), result)
    assert [entry.value for entry in entries if entry.path == "support.spare_ledges"] == [True]
    lone = advise.advise(
        print_settings.resolve(petg()), petg(), slice_body(column_with_flange_and_arm(0.0), 0.2)
    )
    assert "support.spare_ledges" not in {entry.path for entry in lone}, "ohne Stützen nichts"


def slot(length: float) -> MeshData:
    """Ein Block mit einem Schlitz von 5 mm Weite und 6 mm Höhe, ``length`` mm lang."""
    block = brick(30.0, length, 20.0, (0.0, 0.0, 10.0))
    cut = brick(5.0, length + 10.0, 6.0, (0.0, 0.0, 7.0))
    return place_on_bed(MeshData.of(trimesh.boolean.difference([block, cut])))


def slots(count: int, length: float) -> MeshData:
    """``count`` Schlitze wie in :func:`slot` nebeneinander, 10 mm auseinander."""
    block = brick(10.0 * count + 20.0, length, 20.0, (0.0, 0.0, 10.0))
    first = -5.0 * (count - 1)
    cuts = [
        brick(5.0, length + 10.0, 6.0, (first + 10.0 * index, 0.0, 7.0)) for index in range(count)
    ]
    return place_on_bed(MeshData.of(trimesh.boolean.difference([block, *cuts])))


@pytest.mark.parametrize(("count", "length", "blocked"), [(4, 16.0, False), (1, 40.0, True)])
def test_only_a_ceiling_that_would_need_support_gets_a_blocker(
    count: int, length: float, blocked: bool
) -> None:
    """Eine Sperre bekommt nur eine Kanaldecke, die ohne sich selbst zu schließen
    Stütze bräuchte — nach den zwei Wegen von ``worth_support``, am größten
    Stück. Am Drachen schlossen sich Taschen von höchstens 96 mm²; mit Umkreis
    um jede stützte der ElegooSlicer 87,8 statt 97,7 % der Überhangfläche
    außerhalb der Kanaldecken, und selbst eine Sperre von zwei Bahnbreiten um
    jede Taschendecke kostete ihn noch einen Punkt (08.10.2026). Was eine kleine Decke
    dafür offen lässt, ist erreichbar: Am Countercleaner aus dem Korpus stellt
    der Slicer Stütze in eine Kehle, die nach zwei Seiten offen ist. Kanal
    bleibt die kleine Decke trotzdem: Sie zählt nicht zum Stützbedarf — sonst
    verlangte ein Kotschieber aus dem Korpus für seine Schlitze Stützen. Die
    vier kurzen Schlitze messen je unter 80 mm², zusammen über 150; der lange um
    200 mm², und seine Sperre bleibt im Schlitz."""
    result = slice_body(slots(count, length), 0.2)
    need = advise.support_need(result)
    model = need.model
    slabs = channel_space(result, model, LINE)

    assert len(model.channel_columns) <= len(model.channels)
    assert model.channels, "die Schlitzdecken tragen sich selbst"
    assert not need.needed, "und verlangen keine Stütze"
    assert bool(slabs) is blocked
    for _low, high, region in slabs:
        low_x, _low_y, high_x, _high_y = region.bounds
        assert low_x >= -2.5 - LINE - 1e-6 and high_x <= 2.5 + LINE + 1e-6
        assert high <= 10.0 + 0.2 + 1.0


def blind_slot() -> MeshData:
    """Ein Block mit einem Schlitz von 10 mm Weite, 6 mm Höhe und 30 mm Tiefe,
    nur an einer Seite offen — eine Sackgasse wie der Wasserkanal der
    Waschschüssel in Drucklage."""
    block = brick(40.0, 40.0, 20.0, (0.0, 0.0, 10.0))
    cut = brick(10.0, 30.0, 6.0, (0.0, -10.0, 7.0))
    return place_on_bed(MeshData.of(trimesh.boolean.difference([block, cut])))


def test_the_ceiling_of_a_dead_end_is_a_channel() -> None:
    """Die Decke einer Sackgasse liegt an einem zusammenhängenden U auf, nicht
    an zwei getrennten Stellen. Gezählt wurden zuerst nur getrennte Auflagen,
    und der Wasserkanal der Waschschüssel verlor in Drucklage seine Sperre."""
    result = slice_body(blind_slot(), 0.2)
    model = model_support(result)

    assert model.channels, "die Decke der Sackgasse ist Kanal"
    assert channel_space(result, model, LINE)


def shallow_slot_beside_an_arm() -> MeshData:
    """Ein Block mit einem Schlitz von 5 mm Weite, 40 mm Länge und nur 0,6 mm
    Höhe, dazu eine Kragplatte über dem Bett, die Stützen verlangt."""
    block = brick(30.0, 40.0, 20.0, (0.0, 0.0, 10.0))
    cut = brick(5.0, 50.0, 0.6, (0.0, 0.0, 6.3))
    arm = brick(20.0, 40.0, 4.0, (25.0, 0.0, 18.0))
    body = trimesh.boolean.union([trimesh.boolean.difference([block, cut]), arm])
    return place_on_bed(MeshData.of(body))


def test_the_blocker_is_offered_only_where_it_blocks_space() -> None:
    """Am Drachen blieben Kerben unter einem Millimeter Tiefe Kanaldecken; die
    Sperre darunter war leer, und trotzdem stand der Vorschlag da — eine
    Übernahme, die nichts bewirkt."""
    result = slice_body(shallow_slot_beside_an_arm(), 0.2)
    model = model_support(result)
    entries = advise.advise(print_settings.resolve(petg()), petg(), result)
    paths = {entry.path for entry in entries}

    assert model.channels, "die flache Schlitzdecke ist Kanaldecke"
    assert channel_space(result, model, LINE) == [], "aber sie sperrt keinen Raum"
    assert "support.style" in paths, "die Kragplatte braucht Stützen"
    assert "support.block_channels" not in paths


def test_a_ceiling_footprint_without_any_held_edge_does_not_close(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Liegen Stücke einer Decke in der Aufsicht übereinander, kann ein Teil des
    Grundrisses ohne gehaltenen Rand bleiben: Die Stelle, an der ein Stück
    aufliegt, liegt dann unter einem anderen. Die Frage brach damit ab, statt
    „schließt sich nicht“ zu sagen."""
    from app.core.slice import analysis

    ceilings = analysis._Ceilings((), lambda _index: Point(10.6, 5.0).buffer(0.1))
    monkeypatch.setattr(ceilings, "shape", lambda _name: box(0.0, 0.0, 10.0, 10.0))
    monkeypatch.setattr(ceilings, "_gap", lambda _name: 0.35)

    assert not ceilings.closes(frozenset({(1, 0)}))
