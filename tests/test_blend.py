"""Weiches Verschmelzen (Konzept P16.4, Entscheidung N).

Die einzige Operation der organischen Phase, die *parametrisch* organisch ist:
drei Zahlen, kein Handgriff, voll im Stapel änderbar. Für einen ergonomischen
Griff an einem technischen Teil ist sie das bessere Werkzeug als jeder Pinsel.

Sie rechnet nicht wie die anderen booleschen Operationen. Statt Flächen zu
schneiden legt sie beide Körper als Abstandsfeld auf ein Raster, mischt die
Felder weich und zieht die neue Oberfläche daraus. Das kostet Genauigkeit —
gemessen wird hier deshalb gegen die scharfe Vereinigung, die es exakt kann,
und der Abstand dazwischen ist die Zahl, die zählt.
"""

from __future__ import annotations

from collections.abc import Callable

import numpy as np
import pytest
import trimesh

from app.core.errors import NotManifoldError, ValidationError
from app.core.geom import blend, mesh_ops
from app.core.geom.mesh import MeshData, on_surface
from app.core.geom.prepare import check_build_volume
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import OpContext, OpResult, Profile, Quality, Scene, SceneObject
from app.core.units import EPS_GEOM
from tests.helpers import sliver_share


def rod(along: str = "z") -> MeshData:
    """Ein Zylinder, 20 mm dick, 60 mm lang, entlang einer Achse."""
    body = trimesh.creation.cylinder(radius=10.0, height=60.0, sections=48)
    if along == "y":
        body.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2.0, [1, 0, 0]))
    return MeshData.of(body)


def run(
    first: MeshData,
    second: MeshData,
    profile: Profile,
    quality: Quality = "fine",
    **params: object,
) -> OpResult:
    spec = REGISTRY.get("blend_union")
    entries = [
        SceneObject(id="obj_1", name="Erster", mesh=first),
        SceneObject(id="obj_2", name="Zweiter", mesh=second),
    ]
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry for entry in entries}),
            inputs=entries,
            params=spec.params(**params),
            profile=profile,
            quality=quality,
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def test_without_a_radius_it_is_the_ordinary_union(profile: Profile) -> None:
    """Der Nullpunkt der Operation, und die Messlatte für alles andere.

    Mit Radius null ist die weiche Vereinigung die gewöhnliche. Sie kommt
    nicht auf dieselbe Zahl — ein Rasterverfahren rundet, wo ein exakter
    Schnitt trifft —, aber sie muss nah dran sein. Ist sie es nicht, stimmt
    das Abstandsfeld nicht, und jeder Radius darüber wäre auch falsch.
    """
    first, second = rod("z"), rod("y")
    sharp = first.raw.union(second.raw)

    result = run(first, second, profile, radius=0.0, grid=1.0)

    merged = result.outputs[0].mesh
    assert merged.volume == pytest.approx(sharp.volume, rel=0.02)
    assert merged.is_watertight
    assert merged.component_count == 1


def test_the_result_stays_inside_the_hull_it_was_given(profile: Profile) -> None:
    """Die Lücke, durch die ein Fehler bis in einen Commit kam.

    Volumen und Wasserdichtheit waren geprüft, die *Ausdehnung* nicht — und
    genau dort saß der Fehler: Das Vorzeichen des Abstandsfeldes kam aus
    gemittelten Eckpunktnormalen, und die stehen an der Deckkante eines
    Zylinders 45 Grad schräg. Über der Deckfläche kippten sie, und der Körper
    wuchs um acht Millimeter ins Leere, ohne dass das Volumen auffällig genug
    gewesen wäre. Ein Rohr, das nach dem Verschmelzen länger ist als vorher,
    ist kein Detail.

    Geprüft wird gegen die Hülle beider Eingangskörper, großzügig um den
    Übergang erweitert: Der Wulst darf nach außen wachsen, aber nicht weit.
    """
    first, second = rod("z"), rod("y")
    radius = 4.0
    low = np.minimum(first.raw.bounds[0], second.raw.bounds[0]) - radius
    high = np.maximum(first.raw.bounds[1], second.raw.bounds[1]) + radius

    merged = run(first, second, profile, radius=radius, grid=1.0).outputs[0].mesh

    assert np.all(np.asarray(merged.raw.bounds[0]) > low), "der Körper wächst nach unten ins Leere"
    assert np.all(np.asarray(merged.raw.bounds[1]) < high), "und nach oben"


def test_the_radius_puts_material_into_the_throat(profile: Profile) -> None:
    """Wofür es die Operation gibt: die Kehle, die niemand drucken will.

    Zwei gekreuzte Rohre treffen sich in einer scharfen Innenkante. Sie ist
    die Stelle, an der ein Druck reißt, und mit keinem Pinsel zu erreichen —
    sie liegt innen. Je größer der Radius, desto mehr Material sitzt darin,
    und das lässt sich wiegen.
    """
    first, second = rod("z"), rod("y")

    volumes = [
        run(first, second, profile, radius=radius, grid=1.0).outputs[0].mesh.volume
        for radius in (0.0, 3.0, 6.0, 10.0)
    ]

    assert volumes == sorted(volumes), "mehr Radius, mehr Kehle — ohne Ausnahme"
    assert volumes[-1] > volumes[0] * 1.05, "und zwar spürbar, nicht im Rauschen"


def test_every_radius_leaves_one_closed_body(profile: Profile) -> None:
    """Ein Wulst, der das Netz aufreißt, wäre schlimmer als keiner."""
    first, second = rod("z"), rod("y")

    for radius in (0.0, 5.0, 12.0):
        merged = run(first, second, profile, radius=radius, grid=1.0).outputs[0].mesh
        assert merged.is_watertight, f"Radius {radius} hat das Netz geöffnet"
        assert merged.component_count == 1


def test_two_bodies_that_do_not_touch_are_drawn_together(profile: Profile) -> None:
    """Das Gegenstück zu Metaballs, und der Grund, warum es ein Basisnetz baut.

    Zwei Kugeln mit einem Spalt dazwischen: Die gewöhnliche Vereinigung lässt
    sie zwei Körper bleiben. Ein Übergang, der weit genug reicht, zieht eine
    Brücke — daraus entsteht die grobe Form, auf der später geformt wird.

    **Weit genug heißt etwa dreimal der Spalt**, und das ist nicht zu raten:
    Der Wulst hebt das Feld in der Mitte um ein Viertel des Übergangs an, muss
    dort aber den halben Spalt überwinden. Gemessen an 4 mm und 6 mm Spalt
    steht die Brücke beim Dreifachen und beim Zweifachen noch nicht. Der
    Dialogtext sagt es deshalb, statt es den Nutzer suchen zu lassen.
    """
    gap = 6.0
    first = MeshData.of(trimesh.creation.icosphere(subdivisions=3, radius=12.0))
    apart = trimesh.creation.icosphere(subdivisions=3, radius=12.0)
    apart.apply_translation((24.0 + gap, 0.0, 0.0))
    second = MeshData.of(apart)

    separate = run(first, second, profile, radius=0.0, grid=1.0)
    narrow = run(first, second, profile, radius=gap * 2.0, grid=1.0)
    bridged = run(first, second, profile, radius=gap * 3.0, grid=1.0)

    assert separate.outputs[0].mesh.component_count == 2, "ohne Übergang bleiben es zwei"
    assert narrow.outputs[0].mesh.component_count == 2, "zu schmal reicht nicht über den Spalt"
    assert bridged.outputs[0].mesh.component_count == 1, "dreifach wird eine Form daraus"
    assert bridged.outputs[0].mesh.is_watertight
    # Und wer zu schmal wählt, erfährt es, statt zwei Körper für einen zu halten.
    assert "blend.still_apart" in {finding.code for finding in narrow.findings}
    assert "blend.still_apart" not in {finding.code for finding in bridged.findings}


def test_a_box_on_the_grid_lines_still_closes(profile: Profile) -> None:
    """Das Fehlerbild, das dieses Paket gekostet hat.

    Ein achsparalleler Quader mit runden Maßen legt seine Flächen genau auf
    die Rasterpunkte. Dort ist das Abstandsfeld exakt null, und die
    Isoflächensuche findet keinen Vorzeichenwechsel, an dem sie ein Dreieck
    aufspannen könnte: Das Ergebnis zerfiel in 793 Bruchstücke und war um drei
    Prozent zu groß. Deshalb liegt das Raster versetzt.
    """
    first = MeshData.of(trimesh.creation.box(extents=(40.0, 30.0, 20.0)))
    other = trimesh.creation.box(extents=(20.0, 20.0, 40.0))
    second = MeshData.of(other)

    merged = run(first, second, profile, radius=0.0, grid=1.0).outputs[0].mesh

    assert merged.is_watertight
    assert merged.component_count == 1
    assert merged.volume == pytest.approx(first.raw.union(other).volume, rel=0.05)


def test_a_flat_wall_comes_back_flat(profile: Profile) -> None:
    """Eine ebene Wand bleibt eine ebene Fläche — kein Streifenstapel.

    **Befund Robert, 18.09.2026:** „nach verschmelzen sind seiten auch in
    schichten zerfallen, eine seite 43 schichten zb linke seite oder rechte
    seite, ober und Unterseite auch" — und daneben „weich verschmelzen,
    fehlerhaft, abgefranste kanten". Beides ist dasselbe: Das Abstandsfeld maß
    den Weg zum nächsten **Punkt** der Oberflächenwolke, und die ist diskret.
    Vor einer ebenen Wand fällt dieser Weg je nach Lage des Rasterpunkts ein
    wenig zu lang aus, und zwar wellig — gemessen am Quader unten 0,031 mm
    Streuung, 2,015 Grad Normalenabweichung und **67 koplanare Gruppen** in
    einer einzigen Wand. Die Merkmalserkennung liest daraus Streifen, und der
    Kunde sieht Schichten.

    Gemessen wird deshalb der Weg zur **Ebene** des nächsten Dreiecks. An
    einer ebenen Wand ist er exakt; an einer gekrümmten unterschätzt er um
    das, was das Rasterverfahren ohnehin rundet.
    """
    first = MeshData.of(trimesh.creation.box(extents=(40.0, 30.0, 20.0)))
    tower = trimesh.creation.box(extents=(12.0, 12.0, 40.0))
    tower.apply_translation((0.0, 0.0, 20.0))

    merged = run(first, MeshData.of(tower), profile, radius=3.0, grid=1.0).outputs[0].mesh

    body = merged.raw
    centres, normals = body.triangles_center, body.face_normals
    wall = np.where(
        (normals[:, 0] < -0.99) & (np.abs(centres[:, 2]) < 6.0) & (np.abs(centres[:, 1]) < 10.0)
    )[0]
    assert len(wall) > 100, "die Voraussetzung: die linke Wand steht im Ergebnis"
    assert float(np.ptp(centres[wall, 0])) == pytest.approx(0.0, abs=1e-9), "eben und nicht wellig"
    assert float(np.abs(normals[wall, 0] + 1.0).max()) == pytest.approx(0.0, abs=1e-9)
    chosen = {int(index) for index in wall}
    on_the_wall = [group for group in body.facets if chosen & {int(index) for index in group}]
    assert len(on_the_wall) == 1, f"eine Wand ist eine Fläche, gefunden: {len(on_the_wall)}"


def test_the_field_is_the_exact_distance_with_the_sign_of_the_side(profile: Profile) -> None:
    """RM-671: Das Feld misst zum nächsten Punkt **auf** dem Dreieck, nicht zu seiner Ebene.

    Von v0.4.4 bis v0.5.3 maß es zur Ebene des nächsten Stützpunkts. An einer
    ebenen Wand ist das exakt, neben einer Kante nicht: Bei diesen Punkten lag
    es bis 1,9 mm daneben, und der Wert sprang, wo der nächste Stützpunkt vom
    Deckel auf den Mantel wechselte. Der Sollwert kommt hier von außen: der
    Abstand aus :func:`app.core.geom.mesh.on_surface` (exakt über
    ``trimesh.triangles``), das Vorzeichen aus den Ebenen des konvexen Körpers —
    innen liegt, was hinter jeder Fläche liegt. Die Punkte reichen vier
    Millimeter über den Körper hinaus, also bis in den Bereich, in dem ein
    Übergang von drei Millimetern seine Werte liest.
    """
    body = rod("z")
    axes = [np.arange(-14.0, 14.0, 1.3), np.arange(-14.0, 14.0, 1.3), np.arange(-34.0, 34.0, 1.3)]
    points = np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1).reshape(-1, 3) + 0.17

    field = blend.distance_field(body, points, 1.0)

    _spots, distance, _triangles = on_surface(body.raw, points)
    assert float(np.abs(np.abs(field) - distance).max()) <= 1e-9, "der Betrag ist der Abstand"
    corners = np.asarray(body.raw.triangles, dtype=float)
    normals = np.cross(corners[:, 1] - corners[:, 0], corners[:, 2] - corners[:, 0])
    behind = ((points[:, None, :] - corners[None, :, 0]) * normals[None]).sum(axis=2) < 0.0
    inside = behind.all(axis=1)
    clear = distance > 1e-6
    assert inside.any() and (~inside).any(), "die Punkte liegen auf beiden Seiten"
    assert np.array_equal(field[clear] > 0.0, inside[clear]), "innen positiv, außen negativ"


def _sphere_on_cylinder() -> tuple[MeshData, MeshData]:
    """Kugel Ø 16 auf Zylinder Ø 20 × 30, die Mitte 3 mm unter dem Deckel — Weg 4, Teil B."""
    cylinder = trimesh.creation.cylinder(radius=10.0, height=30.0, sections=48)
    cylinder.apply_translation((0.0, 0.0, 15.0))
    ball = trimesh.creation.icosphere(subdivisions=3, radius=8.0)
    ball.apply_translation((0.0, 0.0, 27.0))
    return MeshData.of(cylinder), MeshData.of(ball)


def _crossing_rods() -> tuple[MeshData, MeshData]:
    return rod("z"), rod("y")


def _figure() -> tuple[MeshData, MeshData]:
    """Rumpf 24 × 14 × 40 und Kopf Ø 18 bei z = 45 — die Körper des Beispiels *Figur formen*."""
    trunk = trimesh.creation.box(extents=(24.0, 14.0, 40.0))
    trunk.apply_translation((0.0, 0.0, 20.0))
    head = trimesh.creation.icosphere(subdivisions=2, radius=9.0)
    head.apply_translation((0.0, 0.0, 45.0))
    return MeshData.of(trunk), MeshData.of(head)


#: Die drei Abnahmefälle aus RM-671: Körper, Übergang, Raster, Kante des Angleichens.
EVEN_CASES: dict[str, tuple[Callable[[], tuple[MeshData, MeshData]], float, float, float]] = {
    "crossing_rods": (_crossing_rods, 4.0, 1.0, 1.2),
    "figure": (_figure, 4.0, 1.2, 1.5),
    "sphere_on_cylinder": (_sphere_on_cylinder, 3.0, 1.0, 1.2),
}


@pytest.mark.parametrize("case", sorted(EVEN_CASES))
def test_the_blend_and_the_evening_after_it_leave_few_slivers(case: str, profile: Profile) -> None:
    """RM-671: Höchstens 3 % Splitter nach dem Verschmelzen, unter 5 % nach dem Angleichen.

    Die Zahlen sind die Abnahme aus dem Register: so wenige Splitter wie bis
    v0.4.2 (2,9 % an Kugel auf Zylinder), und das Angleichen macht daraus
    keine neuen und hält seine Kantenlänge bis zum 1,1-Fachen. Gemessen bis
    v0.5.3 an diesen Fällen: 11,8, 10,9 und 6,3 % nach dem Verschmelzen, 30,6,
    28,3 und 17,8 % mit Kanten bis zum Doppelten nach dem Angleichen.
    """
    build, radius, grid, edge = EVEN_CASES[case]
    first, second = build()

    merged = run(first, second, profile, radius=radius, grid=grid).outputs[0].mesh
    evened = mesh_ops.uniform(merged, edge, 0.0)

    assert merged.is_watertight and merged.component_count == 1
    assert sliver_share(merged) <= 0.03, f"nach dem Verschmelzen {sliver_share(merged):.1%}"
    assert sliver_share(evened) < 0.05, f"nach dem Angleichen {sliver_share(evened):.1%}"
    assert float(mesh_ops.edge_lengths(evened).max()) <= 1.1 * edge


def test_two_boxes_on_the_bed_blend_without_reaching_under_it(profile: Profile) -> None:
    """F5 / RM-671: Was die Eingänge nach unten nicht überragen, überragt auch der Übergang nicht.

    Zwei Quader 40 × 30 × 10 auf dem Bett, der zweite um 8 mm versetzt: Wo
    beide Felder gleich sind, hebt die weiche Mischung das Feld um bis zu ein
    Viertel des Übergangs. An den bündigen Böden wuchs das Ergebnis so, mit dem
    Ebenenabstand, bis 1,69 mm unter das Bett, und der Prüfbericht meldete
    „Ein Objekt steckt unter dem Druckbett.“. Begrenzt wird nur nach unten,
    auf die unterste Höhe der Eingänge (Entscheidung Koordinator, Review F):
    Über den bündigen Deckeln und Seiten bleibt die Beule wie bis v0.5.3,
    höchstens ein Viertel des Übergangs breit (RM-763).
    """
    radius = 3.0
    one = trimesh.creation.box(extents=(40.0, 30.0, 10.0))
    one.apply_translation((0.0, 0.0, 5.0))
    two = trimesh.creation.box(extents=(40.0, 30.0, 10.0))
    two.apply_translation((8.0, 0.0, 5.0))

    merged = run(MeshData.of(one), MeshData.of(two), profile, radius=radius, grid=1.0).outputs[0]
    body = merged.mesh

    assert float(body.raw.bounds[0][2]) >= -EPS_GEOM, f"unter dem Bett: {body.raw.bounds[0]}"
    assert _flat_area(body, 2, 0.0) > 0.9 * 48.0 * 30.0, "der Boden liegt eben auf dem Bett"
    bulge = radius / 4.0
    grown = (48.0 + 2.0 * bulge) * (30.0 + 2.0 * bulge) * (10.0 + bulge)
    assert 0.98 * 48.0 * 30.0 * 10.0 < body.volume <= grown, "die Vereinigung samt Beule"
    codes = {finding.code for finding in check_build_volume([body], profile)}
    assert "arrange.below_bed" not in codes


def _flat_area(mesh: MeshData, axis: int, value: float) -> float:
    """Die Fläche der Dreiecke, die mit allen drei Ecken in der Ebene ``axis = value`` liegen."""
    corners = np.asarray(mesh.raw.vertices, dtype=float)[np.asarray(mesh.raw.faces, dtype=np.int64)]
    on = (np.abs(corners[:, :, axis] - value) < 1e-6).all(axis=1)
    cross = np.cross(corners[on, 1] - corners[on, 0], corners[on, 2] - corners[on, 0])
    return float(np.sqrt((cross * cross).sum(axis=1)).sum() / 2.0)


@pytest.mark.parametrize("radius", [4.0, 6.0])
def test_a_round_transition_is_not_cut_flat_at_the_sides_of_the_inputs(
    radius: float, profile: Profile
) -> None:
    """Review F, H2: Die Beule der weichen Mischung bleibt rund, wo kein Bett ist.

    Mit RM-671 endete das Ergebnis zuerst an jeder Seite des Hüllquaders beider
    Eingänge. Zwei gekreuzte Rohre Ø 20 berühren die Ebenen x = ±10 je entlang
    einer Linie, und dort entstand eine ebene Fläche mit Knick: 269 mm² im
    Abnahmefall (Übergang 4), 446 mm² im Leistungsfall aus §31 (Übergang 6).
    Bis v0.5.3 wölbte sich das Ergebnis dort glatt bis x = ±10,98 und ±11,48
    hinaus — um bis zu ein Viertel des Übergangs, wo beide Felder gleich sind.
    """
    merged = run(rod("z"), rod("y"), profile, radius=radius, grid=1.0).outputs[0].mesh

    flat = _flat_area(merged, 0, -10.0) + _flat_area(merged, 0, 10.0)
    assert flat == 0.0, f"{flat:.1f} mm² eben auf x = ±10"
    assert float(merged.raw.bounds[1][0]) > 10.0 + radius / 8.0, "die Beule wölbt sich hinaus"
    assert float(merged.raw.bounds[0][0]) < -10.0 - radius / 8.0


def test_two_stacked_balls_blend_round_and_stay_on_the_bed(profile: Profile) -> None:
    """Review F, H2: Zwei Kugeln Ø 10 übereinander, die sich berühren — der Hals wird rund.

    Mit Übergang 8 wächst der Hals um die Berührstelle über die Seiten des
    Hüllquaders (x, y = ±5) hinaus. Auf den ganzen Hüllquader begrenzt, lagen
    dort 26 mm² eben, bei Übergang 9 schon 107 mm² — gedruckt wie
    angeschliffen. Nach unten bleibt die Begrenzung: Die untere Kugel steht auf
    dem Bett, und nichts reicht darunter.
    """
    lower = trimesh.creation.icosphere(subdivisions=4, radius=5.0)
    lower.apply_translation((0.0, 0.0, 5.0))
    upper = trimesh.creation.icosphere(subdivisions=4, radius=5.0)
    upper.apply_translation((0.0, 0.0, 15.0))

    merged = run(MeshData.of(lower), MeshData.of(upper), profile, radius=8.0, grid=0.5)
    body = merged.outputs[0].mesh

    flat = sum(_flat_area(body, axis, side) for axis in (0, 1) for side in (-5.0, 5.0))
    assert flat == 0.0, f"{flat:.1f} mm² eben an den Seiten"
    assert float(body.raw.bounds[1][0]) > 5.0, "der Hals wölbt sich über die Kugeln hinaus"
    assert float(body.raw.bounds[0][2]) >= -EPS_GEOM, "und nicht unter das Bett"
    assert body.is_watertight and body.component_count == 1


def test_two_floating_balls_blend_round_below_as_well(profile: Profile) -> None:
    """Nachprüfung F, N2: Begrenzt wird an der Bettebene, nicht an der untersten Höhe der Eingänge.

    Zwei Kugeln Ø 10, die sich bei z = 20 berühren, schweben über dem Bett.
    Begrenzt an ihrer untersten Höhe (z = 15) wurde der Hals unten flach,
    74,5 mm² bei Übergang 12 — oben blieb er rund. Die Grenze ist das Bett;
    der Übergang darf über ihm nach unten wachsen, solange er es nicht
    erreicht.
    """
    left = trimesh.creation.icosphere(subdivisions=4, radius=5.0)
    left.apply_translation((-5.0, 0.0, 20.0))
    right = trimesh.creation.icosphere(subdivisions=4, radius=5.0)
    right.apply_translation((5.0, 0.0, 20.0))

    body = run(MeshData.of(left), MeshData.of(right), profile, radius=12.0, grid=0.5)
    merged = body.outputs[0].mesh

    assert _flat_area(merged, 2, 15.0) == 0.0, "unten nicht flach"
    assert float(merged.raw.bounds[0][2]) < 15.0, "der Hals wölbt sich unter die Kugeln"
    assert float(merged.raw.bounds[0][2]) > 0.0, "und erreicht das Bett nicht"


def _crossing_grid(radius: float, grid: float) -> tuple[np.ndarray, tuple[int, ...]]:
    """Das Raster, auf dem :func:`blend.blend_bodies` die gekreuzten Rohre rechnet."""
    low, shape = blend._grid(rod("z"), rod("y"), radius, grid)
    axes = [low[axis] + np.arange(shape[axis]) * grid for axis in range(3)]
    return np.stack(np.meshgrid(*axes, indexing="ij"), axis=-1).reshape(-1, 3), shape


def test_the_banded_field_gives_the_same_body_as_the_full_one(
    profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Review-Fix F: Genau nur im Band — und das Netz ist Bit für Bit dasselbe.

    Marching Cubes liest Werte nur an Rasterkanten mit Vorzeichenwechsel; ein
    Feld weiter als Raster plus Übergang plus Viertelübergang von der Fläche
    braucht dafür nur sein Vorzeichen. Gegenprobe ist die volle Rechnung an
    jedem Rasterpunkt: Das Netz aus Marching Cubes muss gleich sein, und an
    jedem Punkt, an dem das verschmolzene Feld nahe null liegt, der Wert.
    """
    full_field = blend.distance_field

    def everywhere(*args: object, **kwargs: object) -> np.ndarray:
        kwargs.pop("shape", None)
        kwargs.pop("beyond", None)
        return full_field(*args, **kwargs)  # type: ignore[arg-type]

    banded = blend.blend_bodies(rod("z"), rod("y"), 4.0, 1.0)
    monkeypatch.setattr(blend, "distance_field", everywhere)
    full = blend.blend_bodies(rod("z"), rod("y"), 4.0, 1.0)

    assert np.array_equal(np.asarray(banded.raw.vertices), np.asarray(full.raw.vertices))
    assert np.array_equal(np.asarray(banded.raw.faces), np.asarray(full.raw.faces))


def test_the_banded_field_computes_only_near_the_surface(monkeypatch: pytest.MonkeyPatch) -> None:
    """Review-Fix F: Gezählt wird, wie viele Rasterpunkte genau gerechnet werden.

    Bis dahin rechnete das Feld jeden Punkt gegen acht Bewerber; am §31-Fall
    (gekreuzte Rohre, Übergang 6, Raster 1) kostete es so das 1,35-Fache des
    Ebenenfelds vor RM-671 an CPU-Zeit. Im Band liegt nur ein Teil des
    Rasters: Beide Felder des Falls rechnen 191 706 von 486 798 Zeilen genau.
    """
    points, shape = _crossing_grid(6.0, 1.0)
    asked: list[int] = []
    signed = blend._Surface.signed

    def counted(self: blend._Surface, where: np.ndarray, candidates: np.ndarray) -> np.ndarray:
        asked.append(len(where))
        return signed(self, where, candidates)

    monkeypatch.setattr(blend._Surface, "signed", counted)

    field = blend.distance_field(rod("z"), points, 1.0, shape=shape, beyond=1.0 + 6.0 * 1.25)

    assert len(field) == len(points)
    assert sum(asked) < 0.5 * len(points), f"{sum(asked)} von {len(points)} genau gerechnet"


def test_a_group_outside_the_band_takes_its_sign_only_from_an_agreeing_rim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Nachprüfung F, T2-1: Eine Gruppe außerhalb des Bands nahm das Vorzeichen ihres
    ersten Randpunkts in fester Folge der Achsen.

    Trug gerade er ein falsches — die Art, die RM-769 beschreibt, am Besenhalter
    einer von 351 120 Punkten —, kippte die ganze Gruppe, hier das ganze Äußere
    nach innen. Jetzt gilt das Vorzeichen des Rands nur, wenn alle seine Punkte
    sich einig sind; sonst entscheidet **ein** genau gerechneter Punkt der
    Gruppe, denn in ihr wechselt das Vorzeichen nicht. Jeden Punkt genau zu
    rechnen kostete an gekreuzten Rohren 5,0 statt 0,04 s, ohne Abbruch (Review
    Blend, M1) — gezählt wird deshalb, wie viele Punkte genau rechnen. Gekippt
    wird die ganze Lage links des Quaders, denn dort sucht die Folge zuerst.
    """
    box = MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 20.0)))
    axis = np.arange(-16.0, 16.0 + 1e-9, 2.0)
    shape = (len(axis),) * 3
    points = np.stack(np.meshgrid(axis, axis, axis, indexing="ij"), axis=-1).reshape(-1, 3)
    exact = blend.distance_field(box, points, 2.0)
    far = np.abs(exact) > 5.0
    surface = blend._Surface.of(box, 2.0)
    value = 9.0
    asked: list[int] = []
    signed = blend._Surface.signed

    def counted(self: blend._Surface, where: np.ndarray, candidates: np.ndarray) -> np.ndarray:
        asked.append(len(where))
        return signed(self, where, candidates)

    monkeypatch.setattr(blend._Surface, "signed", counted)
    agreed = exact.copy()
    blend._signs_from_the_band(surface, agreed, far, points, shape, value)
    assert np.array_equal(agreed[far], np.where(exact[far] > 0.0, value, -value)), "einig: ±value"
    assert sum(asked) == 0, "einig rechnet keinen Punkt genau"

    torn = exact.copy()
    left = ~far & (points[:, 0] < -10.0)
    torn[left] = np.abs(torn[left])
    blend._signs_from_the_band(surface, torn, far, points, shape, value)

    outside = far & (exact < 0.0)
    inside = far & (exact > 0.0)
    assert outside.any() and inside.any()
    assert np.array_equal(torn[outside], np.full(int(outside.sum()), -value)), "außen bleibt außen"
    assert np.array_equal(torn[inside], np.full(int(inside.sum()), value)), "das Innere ist einig"
    assert sum(asked) == 1, f"{sum(asked)} Punkte genau gerechnet statt einem für die Gruppe"


def _hollow(outer: trimesh.Trimesh, inner: trimesh.Trimesh) -> MeshData:
    """``outer`` mit ``inner`` als eingeschlossenem Hohlraum (nach innen gewickelt)."""
    hole = inner.copy()
    hole.invert()
    return MeshData.of(trimesh.util.concatenate([outer, hole]))


def _cavity_case(case: str) -> tuple[trimesh.Trimesh, trimesh.Trimesh, trimesh.Trimesh, float]:
    """Außenkörper, Hohlraum, Partner daneben und das Volumen des Hohlraums von außen."""
    if case == "hollow_ball":
        outer = trimesh.creation.icosphere(subdivisions=4, radius=20.0)
        inner = trimesh.creation.icosphere(subdivisions=4, radius=12.0)
        other = trimesh.creation.icosphere(subdivisions=3, radius=8.0)
        other.apply_translation((24.0, 0.0, 0.0))
        volume = 4.0 / 3.0 * np.pi * 12.0**3
    else:
        outer = trimesh.creation.box(extents=(40.0, 30.0, 20.0))
        inner = trimesh.creation.box(extents=(20.0, 10.0, 8.0))
        other = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
        other.apply_translation((24.0, 0.0, -5.0))
        volume = 20.0 * 10.0 * 8.0
    for body in (outer, inner, other):
        body.apply_translation((0.0, 0.0, 20.0))
    return outer, inner, other, float(volume)


@pytest.mark.parametrize("case", ["hollow_ball", "box_with_cavity"])
def test_a_closed_cavity_stays_a_cavity_when_blended(case: str, profile: Profile) -> None:
    """Fund der Nachprüfung F (Teil 2), vorbestehend seit v0.1.1.

    Nach Marching Cubes wendete ``fix_normals()`` bei mehr als einer Schale jede
    für sich nach außen, auch die eines eingeschlossenen Hohlraums: Eine
    Hohlkugel mit einer Kugel daneben kam mit 42 473 statt 28 089 mm³ heraus,
    der Hohlraum als zweiter Körper, und der Schritt meldete
    ``blend.still_apart``. Sollwert von außen: derselbe Körper ohne Hohlraum
    verschmolzen, weniger dem Volumen des Hohlraums, auf das Raster genau —
    Marching Cubes schneidet die Ecken des Hohlraums an (gemessen 0,6 und
    1,5 % zu wenig).
    """
    outer, inner, other, cavity = _cavity_case(case)

    hollow = run(_hollow(outer, inner), MeshData.of(other), profile, radius=2.0, grid=1.0)
    full = run(MeshData.of(outer), MeshData.of(other), profile, radius=2.0, grid=1.0)

    merged = hollow.outputs[0].mesh
    assert merged.is_watertight and merged.component_count == 2, "Körper und Hohlraum"
    assert full.outputs[0].mesh.volume - merged.volume == pytest.approx(cavity, rel=0.02)
    assert "blend.still_apart" not in {finding.code for finding in hollow.findings}


def test_a_curved_body_keeps_its_volume_when_blended(profile: Profile) -> None:
    """Und die Gegenprobe: An Rundungen ändert sich nichts Wesentliches.

    Der Weg zur Ebene des nächsten Dreiecks unterschätzt an einer gewölbten
    Fläche den Abstand. Gemessen an drei Paarungen über den Korpus hinaus
    liegt der Unterschied unter einem halben Promille; was bleibt, ist ein
    geschlossener einteiliger Körper.
    """
    ball = MeshData.of(trimesh.creation.icosphere(radius=20.0, subdivisions=3))
    other = trimesh.creation.icosphere(radius=15.0, subdivisions=3)
    other.apply_translation((25.0, 0.0, 0.0))

    merged = run(ball, MeshData.of(other), profile, radius=3.0, grid=1.0).outputs[0].mesh

    assert merged.is_watertight and merged.component_count == 1
    assert merged.volume == pytest.approx(44939.0, rel=0.01)


def test_the_same_parameters_give_the_same_body(profile: Profile) -> None:
    """Die Abstandsabfrage läuft über alle Kerne — Nebenläufigkeit darf das
    Ergebnis nicht anfassen.
    """
    first, second = rod("z"), rod("y")

    once = run(first, second, profile, radius=5.0, grid=1.5).outputs[0].mesh
    twice = run(first, second, profile, radius=5.0, grid=1.5).outputs[0].mesh

    assert np.array_equal(np.asarray(once.raw.vertices), np.asarray(twice.raw.vertices))


def test_a_grid_too_fine_to_compute_says_which_one_works(profile: Profile) -> None:
    """Fehler als Vorschlag, bevor der Fehler passiert — wie beim Vernetzen."""
    first, second = rod("z"), rod("y")

    with pytest.raises(ValidationError) as raised:
        run(first, second, profile, radius=0.0, grid=0.02)

    assert raised.value.suggestions
    assert float(raised.value.values["reachable"]) > 0.02


def test_a_body_without_volume_is_turned_away(profile: Profile) -> None:
    """Ein Abstandsfeld braucht ein Innen. Eine offene Fläche hat keines."""
    open_body = trimesh.creation.box(extents=(20.0, 20.0, 20.0))
    open_body.update_faces(np.arange(len(open_body.faces)) > 1)

    with pytest.raises(NotManifoldError) as raised:
        run(MeshData.of(open_body), rod("z"), profile, radius=2.0, grid=1.0)

    assert raised.value.suggestions


def test_the_finding_says_the_result_is_rastered(profile: Profile) -> None:
    """Was Genauigkeit kostet, wird ausgewiesen — wie die Voxelstufe es tut.

    Wer diese Operation für eine Passung benutzt, hat sich vertan, und er darf
    das nicht erst am gedruckten Teil merken.
    """
    first, second = rod("z"), rod("y")

    result = run(first, second, profile, radius=4.0, grid=1.0)

    codes = {finding.code for finding in result.findings}
    assert "blend.rastered" in codes
    finding = next(f for f in result.findings if f.code == "blend.rastered")
    assert float(finding.values["grid_mm"]) == pytest.approx(1.0)


def test_draft_quality_is_coarser_than_fine_only_above_the_budget(profile: Profile) -> None:
    """Über :data:`blend.DRAFT_SAMPLES` rechnet der Entwurf gröber und sagt es.

    Die Rasterweite ist keine Zusage über das Ergebnis, sondern der Preis für
    seine Genauigkeit — und im Entwurf wird iteriert, nicht abgenommen. Aber
    nur, wo es nötig ist: Darunter wich die Figur im Fenster ohne Not bis
    2 mm vom Export ab (RM-379).
    """
    first, second = rod("z"), rod("y")

    draft = run(first, second, profile, "draft", radius=4.0, grid=0.6)
    fine = run(first, second, profile, "fine", radius=4.0, grid=0.6)

    assert draft.outputs[0].mesh.triangle_count < fine.outputs[0].mesh.triangle_count
    assert draft.outputs[0].mesh.is_watertight
    assert "blend.draft" in {entry.code for entry in draft.findings}
    assert "blend.draft" not in {entry.code for entry in fine.findings}


def _small_pairs() -> list[tuple[MeshData, MeshData]]:
    box = trimesh.creation.box(extents=(20.0, 20.0, 10.0))
    ball = trimesh.creation.icosphere(subdivisions=3, radius=8.0)
    ball.apply_translation((0.0, 0.0, 9.0))
    small = trimesh.creation.box(extents=(6.0, 6.0, 6.0))
    other = trimesh.creation.box(extents=(6.0, 6.0, 6.0))
    other.apply_translation((5.0, 0.0, 0.0))
    return [
        (rod("z"), rod("y")),
        (MeshData.of(box), MeshData.of(ball)),
        (MeshData.of(small), MeshData.of(other)),
    ]


@pytest.mark.parametrize("pair", range(3))
def test_below_the_budget_the_draft_is_the_fine_body(profile: Profile, pair: int) -> None:
    """Unter dem Budget sind Entwurf und Export dasselbe Netz (RM-379)."""
    first, second = _small_pairs()[pair]

    draft = run(first, second, profile, "draft", radius=4.0, grid=1.0)
    fine = run(first, second, profile, "fine", radius=4.0, grid=1.0)

    assert np.array_equal(
        np.asarray(draft.outputs[0].mesh.raw.vertices),
        np.asarray(fine.outputs[0].mesh.raw.vertices),
    )
    assert "blend.draft" not in {entry.code for entry in draft.findings}


def test_a_heavy_surface_counts_in_the_draft_budget() -> None:
    """Das Budget zählt die Oberfläche mit (RM-427).

    Mit 327 680 Dreiecken knapp unter dem Punktebudget rechnete der Entwurf
    fein und brauchte 3,8 s statt 0,9 s: Die Abstandsfelder kosten mit der
    Oberfläche, gezählt wurden nur die Rasterpunkte. Dieselben Punkte an einer
    leichten Kugel bleiben fein.
    """
    from app.core.geom import blend

    box = trimesh.creation.box(extents=(40.0, 40.0, 40.0))
    box.apply_translation((32.0, 0.0, 0.0))
    other = MeshData.of(box)
    heavy = MeshData.of(trimesh.creation.icosphere(subdivisions=7, radius=40.0))
    light = MeshData.of(trimesh.creation.icosphere(subdivisions=4, radius=40.0))
    grid = 4.0
    while int(np.prod(blend._grid(heavy, other, 4.0, grid - 0.05)[1])) <= blend.DRAFT_SAMPLES:
        grid -= 0.05
    samples = int(np.prod(blend._grid(heavy, other, 4.0, grid)[1]))
    assert samples <= blend.DRAFT_SAMPLES < 2 * samples, "Voraussetzung: knapp unter dem Budget"

    assert blend.draft_grid(heavy, other, 4.0, grid) == pytest.approx(grid * blend.DRAFT_FACTOR)
    assert blend.draft_grid(light, other, 4.0, grid) == pytest.approx(grid)


def test_both_filaments_come_through_the_blend(profile: Profile) -> None:
    """Weich verschmelzen vernetzt neu — und trägt die Filamente hinüber (§20).

    Das Rasterverfahren baut eine ganz neue Oberfläche, und
    ``MeshData.replacing`` lässt eine Slotliste fallen, die nicht zur neuen
    Dreieckszahl passt. Bis zum 22.09.2026 kam deshalb jedes verschmolzene
    Teil einfarbig in Slot 0 heraus: ein roter Sockel mit blauem Turm wurde
    grau, und die Filamentbeschreibung des Turms verschwand mit. Dieselbe
    Pflicht wie nach der Voxelstufe (``operationen.md``): Wer neu vernetzt,
    überträgt die Slots neu.
    """
    import dataclasses

    from app.core.geom.attributes import used_slots, with_slot
    from app.core.types import MaterialSlot

    base = trimesh.creation.box(extents=(20.0, 20.0, 10.0))
    tower = trimesh.creation.box(extents=(8.0, 8.0, 20.0))
    tower.apply_translation((0.0, 0.0, 12.0))
    spec = REGISTRY.get("blend_union")
    entries = [
        SceneObject(
            id="obj_1",
            name="Sockel",
            mesh=with_slot(MeshData.of(base), 2),
            material_slots=[MaterialSlot(index=2, name="Rot", colour=(1.0, 0.0, 0.0))],
        ),
        SceneObject(
            id="obj_2",
            name="Turm",
            mesh=with_slot(MeshData.of(tower), 3),
            material_slots=[MaterialSlot(index=3, name="Blau", colour=(0.0, 0.0, 1.0))],
        ),
    ]
    result = spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry for entry in entries}),
            inputs=entries,
            params=spec.params(radius=2.0, grid=1.0),
            profile=profile,
            quality="fine",
            seed=None,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )
    body = result.outputs[0]
    mesh = body.mesh
    assert used_slots(mesh) == (2, 3)
    centres = mesh.raw.triangles_center
    slots = np.asarray(mesh.slots)
    assert np.all(slots[centres[:, 2] < 2.0] == 2), "der Sockel bleibt rot"
    assert np.all(slots[centres[:, 2] > 15.0] == 3), "der Turm bleibt blau"
    assert [dataclasses.astuple(slot)[:2] for slot in body.material_slots] == [
        (2, "Rot"),
        (3, "Blau"),
    ]
