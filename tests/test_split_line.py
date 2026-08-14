"""Trennen entlang einer gezeichneten Linie (Bauplan §25, §14).

Der Unterschied zu ``split_pinned`` ist eine einzige Sache: die Ebene hängt an
keiner Achse. Alles, was daran hängt, wird hier gemessen — die Ebene aus zwei
Punkten und einer Blickrichtung, die Stifte auf einer schiefen Fläche, und die
Zusage, dass eine schiefe Trennung dasselbe leistet wie eine gerade.

Gemessen wird gegen analytische Körper, nicht gegen ein selbst erzeugtes
Ergebnis: Bei einer Ebene durch die Mitte eines Quaders ist jedes Volumen
vorher bekannt.
"""

from __future__ import annotations

import numpy as np
import pytest
import trimesh

from app.core.errors import ValidationError
from app.core.geom import pins
from app.core.geom.mesh import MeshData
from app.core.geom.prepare import split_at_plane
from app.core.geom.section import SectionPlane, plane_through
from app.core.registry import REGISTRY
from app.core.scene.cancel import NeverCancelled
from app.core.types import OpContext, Profile, Scene, SceneObject

#: Ein Körper, dessen Volumen jeder ausrechnen kann. Groß genug, dass zwei
#: Stifte samt Wand auf jede Schnittfläche passen.
BLOCK = (80.0, 60.0, 40.0)


def block() -> MeshData:
    return MeshData.of(trimesh.creation.box(extents=BLOCK))


def run(op: str, entry: SceneObject, profile: Profile, **params: object):
    spec = REGISTRY.get(op)
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


# --- die Ebene aus der gezeichneten Linie -----------------------------------------


def test_a_line_across_the_screen_becomes_an_upright_plane() -> None:
    """Eine waagerecht gezeichnete Linie, von vorn betrachtet, trennt oben von
    unten."""
    plane = plane_through((-10.0, 0.0, 5.0), (10.0, 0.0, 5.0), view=(0.0, 1.0, 0.0))

    assert plane is not None
    assert abs(plane.normal[2]) == pytest.approx(1.0), "die Ebene liegt waagerecht"
    assert abs(plane.position) == pytest.approx(5.0), "und auf der Höhe der Linie"


def test_the_plane_holds_both_drawn_points() -> None:
    """Was gezeichnet wurde, liegt danach *in* der Ebene — sonst trennt sie
    woanders, als der Strich stand."""
    first = (3.0, -7.0, 11.0)
    second = (-5.0, 2.0, 4.0)

    plane = plane_through(first, second, view=(1.0, 1.0, -2.0))

    assert plane is not None
    for point in (first, second):
        distance = float(np.dot(plane.normal, point)) - plane.position
        assert distance == pytest.approx(0.0, abs=1e-9)


def test_a_line_along_the_view_spans_no_plane() -> None:
    """Regel 21: lieber nichts als eine geratene Ebene.

    Zwei Punkte genau hintereinander sehen im Bild aus wie einer. Daraus eine
    Ebene zu erfinden hieße, eine Richtung zu behaupten, die niemand gezeigt
    hat.
    """
    assert plane_through((0.0, 0.0, 0.0), (0.0, 4.0, 0.0), view=(0.0, 1.0, 0.0)) is None
    assert plane_through((1.0, 2.0, 3.0), (1.0, 2.0, 3.0), view=(0.0, 1.0, 0.0)) is None


# --- der Schnitt ------------------------------------------------------------------


def test_a_slanted_cut_halves_the_block(profile: Profile) -> None:
    """Eine Ebene diagonal durch die Mitte: beide Hälften geschlossen, beide
    halb so groß."""
    entry = SceneObject(id="obj_1", name="Klotz", mesh=block())
    whole = float(np.prod(BLOCK))

    result = run(
        "split_line",
        entry,
        profile,
        normal_x=1.0,
        normal_y=1.0,
        normal_z=0.0,
        position=0.0,
        pins=0,
    )

    assert [output.name for output in result.outputs] == ["Klotz A", "Klotz B"]
    assert all(output.mesh.is_watertight for output in result.outputs)
    volumes = [float(output.mesh.volume) for output in result.outputs]
    assert sum(volumes) == pytest.approx(whole, rel=1e-6)
    assert volumes[0] == pytest.approx(whole / 2.0, rel=1e-6)


def test_the_pins_stand_perpendicular_on_a_slanted_face(profile: Profile) -> None:
    """Der Grund, warum die Stifte eine Richtung führen statt eines
    Achsenbuchstabens.

    Ein Stift, der entlang der nächstgelegenen Achse aufgestellt wird, steht
    auf einer 45-Grad-Fläche schief in ihr — er lässt sich nicht fügen, ohne
    die Bohrung aufzureiben.
    """
    entry = SceneObject(id="obj_1", name="Klotz", mesh=block())
    expected = np.array([1.0, 1.0, 0.0]) / np.sqrt(2.0)

    result = run(
        "split_line",
        entry,
        profile,
        normal_x=1.0,
        normal_y=1.0,
        normal_z=0.0,
        position=0.0,
        pins=2,
    )

    axis = np.asarray(result.outputs[0].features["pin_1"].params["axis"], dtype=float)
    assert np.allclose(axis, expected), "die Stiftachse ist die Normale der Trennebene"
    assert all(output.mesh.is_watertight for output in result.outputs)
    assert "bore_1" in result.outputs[1].features


def test_the_pins_sit_in_the_cut_face(profile: Profile) -> None:
    """Auf der Ebene, nicht daneben: gemessen als Abstand zur Ebene."""
    plane = SectionPlane(normal=(1.0, 1.0, 0.0), position=0.0)

    plan = pins.plan_pins(block(), plane)

    assert plan.count == 2
    unit = np.asarray(plane.normal, dtype=float) / np.linalg.norm(plane.normal)
    for position in plan.positions:
        assert float(np.dot(unit, position)) == pytest.approx(0.0, abs=1e-6)


def test_a_slanted_seam_gains_and_loses_the_same_material(profile: Profile) -> None:
    """Stift und Bohrung sind dasselbe Loch, einmal voll und einmal leer —
    bis auf Spiel und Freistich."""
    entry = SceneObject(id="obj_1", name="Klotz", mesh=block())
    plane = SectionPlane(normal=(1.0, 1.0, 0.0), position=0.0)
    first, second, _findings = split_at_plane(block(), plane)

    result = run("split_line", entry, profile, normal_x=1.0, normal_y=1.0, position=0.0, pins=2)

    assert float(result.outputs[0].mesh.volume) > float(first.volume), "Stifte tragen auf"
    assert float(result.outputs[1].mesh.volume) < float(second.volume), "Bohrungen nehmen weg"


def test_the_same_plane_gives_the_same_result_as_the_axis_version(profile: Profile) -> None:
    """Ein senkrecht stehender Schnitt ist derselbe, gleich über welchen der
    beiden Wege er kommt.

    Der Test hält die zwei Operationen aneinander: Wenn ``split_line`` je
    anders rechnete als ``split_pinned``, gäbe es zwei Wahrheiten über
    denselben Schnitt.
    """
    entry = SceneObject(id="obj_1", name="Klotz", mesh=block())

    drawn = run("split_line", entry, profile, normal_z=1.0, position=5.0, pins=2)
    axial = run("split_pinned", entry, profile, axis="z", position=5.0, pins=2)

    for one, other in zip(drawn.outputs, axial.outputs, strict=True):
        assert float(one.mesh.volume) == pytest.approx(float(other.mesh.volume), rel=1e-9)


def test_the_same_cut_twice_is_the_same_body(profile: Profile) -> None:
    """§11.2: zweimal auswerten muss identisch sein."""
    entry = SceneObject(id="obj_1", name="Klotz", mesh=block())
    values = {"normal_x": 1.0, "normal_y": 0.4, "normal_z": 0.2, "position": 3.0, "pins": 2}

    first = run("split_line", entry, profile, **values)
    second = run("split_line", entry, profile, **values)

    assert [round(o.mesh.volume, 6) for o in first.outputs] == [
        round(o.mesh.volume, 6) for o in second.outputs
    ]


# --- was nicht geht, sagt es -------------------------------------------------------


def test_a_plane_beside_the_body_is_a_user_error(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Klotz", mesh=block())

    with pytest.raises(ValidationError) as problem:
        run("split_line", entry, profile, normal_z=1.0, position=9999.0, pins=0)

    assert problem.value.field == "position"
    assert problem.value.suggestions, "Regel 17: jede Ausnahme trägt einen Vorschlag"


def test_a_direction_of_zero_length_is_a_user_error(profile: Profile) -> None:
    """Drei Nullen sind keine Richtung — und die Meldung sagt das, statt an
    einer Division zu scheitern."""
    entry = SceneObject(id="obj_1", name="Klotz", mesh=block())

    with pytest.raises(ValidationError) as problem:
        run("split_line", entry, profile, normal_x=0.0, normal_y=0.0, normal_z=0.0)

    assert problem.value.field == "normal_z"
    assert problem.value.suggestions


# --- wie die Hälften heißen ---------------------------------------------------------


def test_the_halves_say_which_one_carries_the_pins() -> None:
    """Beim Export ist der Dateiname die einzige Auskunft darüber, welches
    Teil welches ist."""
    from app.core.geom.prepare_ops import half_names

    assert half_names("Halter", pinned=True) == ("Halter A · Stifte", "Halter B · Löcher")
    assert half_names("Halter", pinned=False) == ("Halter A", "Halter B")


def test_splitting_a_half_again_replaces_the_note_instead_of_stacking_it() -> None:
    """Sonst steht dort „Halter A · Stifte A · Stifte".

    Der Buchstabenpfad bleibt: Er zeigt, aus welchem Stück welches geworden
    ist, und genau das will man beim Zusammenbau wissen.
    """
    from app.core.geom.prepare_ops import half_names

    first, _second = half_names("Halter", pinned=True)

    assert half_names(first, pinned=True) == (
        "Halter A A · Stifte",
        "Halter A B · Löcher",
    )
    assert half_names(first, pinned=False) == ("Halter A A", "Halter A B")


def test_a_name_of_someone_elses_keeps_its_own_addition() -> None:
    """Ersetzt wird der *eigene* Zusatz, nicht alles hinter dem Zeichen.

    Ein bloßes Abschneiden am letzten „ · " war zu grob: „Halter ·
    Sonderanfertigung" verlor beim Teilen sein zweites Wort — stiller Verlust
    an einem Namen, den jemand selbst vergeben hat.
    """
    from app.core.geom.prepare_ops import half_names

    assert half_names("Halter · Sonderanfertigung", pinned=True) == (
        "Halter · Sonderanfertigung A · Stifte",
        "Halter · Sonderanfertigung B · Löcher",
    )


def test_a_note_from_another_language_is_replaced_too() -> None:
    """Ein Teil kann auf Deutsch geteilt und auf Englisch weitergeteilt werden.

    Erkennt die Ersetzung nur die aktive Sprache, stapeln sich zwei Zusätze in
    zwei Sprachen — „Halter A · Pins A · Stifte".
    """
    from app.core.geom.prepare_ops import half_names

    assert half_names("Halter A · Pins", pinned=True) == (
        "Halter A A · Stifte",
        "Halter A B · Löcher",
    )


# --- zusammengelegte Zwillinge ------------------------------------------------------


def test_a_twin_without_a_toggle_gets_none() -> None:
    """`MENU_TWINS` hing an einer festen Beschriftung, und damit an B-Rep.

    Der Haken „Exakter Körper (B-Rep)" stand als Zeichenkette in der
    Oberfläche und „(Umschalter „Exakt")" im Menüweg. Ein drittes Paar hätte
    beides geerbt — *An Ebene teilen* unter *Teilen* mit einem Haken, der von
    einem exakten Körper spricht, den es dort nicht gibt. Sein Umschalter ist
    ein Wert im selben Dialog: die Null im Feld *Passstifte*.
    """
    from app.core.registry import MENU_TWINS, TWIN_TOGGLES
    from app.core.registry.surfaces import menu_path

    assert MENU_TWINS["split_plane"] == "split_pinned"
    assert "split_plane" not in TWIN_TOGGLES, "kein eigener Haken"
    assert "split_plane" not in menu_path(REGISTRY.get("split_plane"))
    assert "Exakt" not in menu_path(REGISTRY.get("split_plane"))
    assert "Exakt" in menu_path(REGISTRY.get("create_brep_box")), "die B-Rep-Paare behalten ihn"


def test_every_toggle_belongs_to_a_twin() -> None:
    """Ein Umschalter ohne Paar wäre ein Haken, den kein Dialog zeigt."""
    from app.core.registry import MENU_TWINS, TWIN_TOGGLES

    assert set(TWIN_TOGGLES) <= set(MENU_TWINS)


# --- die Verbinderformen ------------------------------------------------------------


@pytest.mark.parametrize("shape", ["round", "hex", "dovetail", "snap"])
def test_every_connector_shape_gives_two_closed_halves(profile: Profile, shape: str) -> None:
    """Die Slicer bieten diese Auswahl, und die Foren diskutieren nur noch,
    welche.

    Rund braucht zwei Stück gegen Verdrehen; Sechskant und Schwalbenschwanz
    halten schon einzeln, der Schwalbenschwanz auch gegen Auseinanderziehen,
    und der Schnapper rastet ein. Geprüft wird für alle dasselbe: zwei
    geschlossene Hälften, Material auf der einen, Material weniger auf der
    anderen.
    """
    entry = SceneObject(id="obj_1", name="Klotz", mesh=block())
    plane = SectionPlane(normal=(0.0, 0.0, 1.0), position=0.0)
    first, second, _findings = split_at_plane(block(), plane)

    result = run("split_line", entry, profile, normal_z=1.0, position=0.0, pins=2, shape=shape)

    assert all(output.mesh.is_watertight for output in result.outputs)
    assert float(result.outputs[0].mesh.volume) > float(first.volume)
    assert float(result.outputs[1].mesh.volume) < float(second.volume)
    assert "pin_1" in result.outputs[0].features
    assert "bore_1" in result.outputs[1].features


def test_a_dovetail_holds_where_a_round_pin_only_guides(profile: Profile) -> None:
    """Der Unterschied ist messbar, nicht bloß behauptet.

    Ein Schwalbenschwanz ist hinten schmaler als vorn. Dreht man ihn um seine
    eigene Achse, deckt er sich nicht mit sich selbst — ein runder Stift tut
    das in jeder Stellung, und genau deshalb braucht er einen zweiten neben
    sich.
    """
    from app.core.geom.boolean import boolean
    from app.core.knowledge.parts import PARTS
    from app.core.knowledge.parts.shapes import turned

    spec = PARTS.get("dowel")
    for shape, secured in (("round", False), ("hex", True), ("dovetail", True)):
        body = spec.fn(spec.params(diameter=6.0, length=12.0, kind="pin", shape=shape)).mesh
        # Was von der Bohrung frei bliebe, wenn der Stift verdreht steckte.
        # Bei einem Kreis ist das nur die Facettierung, bei den kantigen ein
        # echter Anschlag.
        left_over = boolean("difference", [body, turned(body, 37.0)]).mesh
        share = float(left_over.volume) / float(body.volume)

        assert (share > 0.02) is secured, f"{shape}: {share:.3f} des Querschnitts hält"


def test_a_connector_never_grows_past_the_circle_that_was_planned_for_it() -> None:
    """Die Planung sucht Platz für einen Kreis; die Form muss hineinpassen.

    ``plan_pins`` zieht die Schnittfläche um Stiftradius plus Wandstärke ein.
    Eine Form, die über diesen Kreis hinausragt, frisst still von der Wand,
    die dort stehen bleiben soll. Gemessen war genau das der Fall: Bei
    ``diameter = 6`` kam der Sechskant auf 6,93 Umkreis und der
    Schwalbenschwanz auf 8,49 — dessen Ecke allein nahm 1,24 mm der 1,6 mm
    Reserve.
    """
    from app.core.knowledge.parts import PARTS

    spec = PARTS.get("dowel")
    for shape in ("round", "hex", "dovetail"):
        body = spec.fn(
            spec.params(diameter=6.0, length=12.0, kind="pin", shape=shape, chamfer=0.0)
        ).mesh
        flat = np.asarray(body.raw.vertices)[:, :2]
        circle = 2.0 * float(np.linalg.norm(flat, axis=1).max())

        assert circle == pytest.approx(6.0, abs=1e-6), f"{shape} ragt über den Kreis hinaus"


def test_without_the_evaluated_body_the_wanted_count_holds(profile: Profile) -> None:
    """Ist nichts bekannt, ist auch nichts widerlegt.

    ``fitting_pins`` soll die Zahl der Passungen an die Stifte binden, die
    wirklich sitzen — aber ohne den ausgewerteten Körper weiß es nichts, und
    stumm auf null zu gehen wäre der Verlust der Passungen, die es vor dieser
    Änderung gab.
    """
    from app.core.split import fitting_pins

    plane = SectionPlane(normal=(0.0, 0.0, 1.0), position=0.0)

    assert fitting_pins(None, plane, 2) == 2, "ohne Körper gilt die gewünschte Zahl"
    assert fitting_pins(None, plane, 0) == 0, "null bleibt null"
    assert fitting_pins(block(), plane, 2) == 2, "mit Körper wird nachgerechnet"


# --- der Schnappverbinder ------------------------------------------------------------


def _snap(**values: float | str) -> MeshData:
    """Ein Schnappverbinder aus dem Baustein, ohne Umweg über eine Operation."""
    from app.core.knowledge.parts.registry import PARTS

    spec = PARTS.get("snap_connector")
    return spec.fn(spec.params(**values)).mesh


def _lip(arm: MeshData, socket: MeshData, across: float, depth: float) -> MeshData:
    """Das Material der Rastkante: der volle Schlitz, minus der Tasche."""
    from app.core.geom.boolean import boolean
    from app.core.knowledge.parts import shapes

    low, high = arm.raw.bounds
    slot = shapes.box(float(high[0] - low[0]) + 2.0, across + 2.0, depth)
    return boolean("difference", [slot, socket]).mesh


def _shared(first: MeshData, second: MeshData) -> float:
    """Gemeinsames Volumen. Nichts gemeinsam wirft — das ist dann null."""
    from app.core.errors import BooleanFailedError
    from app.core.geom.boolean import boolean

    try:
        return float(boolean("intersection", [first, second]).mesh.raw.volume)
    except BooleanFailedError:
        return 0.0


def test_the_snap_connector_catches_and_still_goes_in() -> None:
    """Ein Schnapper, der nur wasserdicht ist, ist noch keiner.

    Zwei Eigenschaften machen ihn aus, und beide sind als Volumen messbar:

    * **Er hält.** Zieht man die Hälften auseinander, läuft der Haken in die
      Rastkante der Tasche. Der Arm um ein Zehntel zurückversetzt und mit dem
      Material der Kante geschnitten — bleibt etwas übrig, ist da ein Anschlag.
    * **Er geht rein.** Weicht der Arm um den Hakenüberstand zur Seite, muss er
      vollständig in die Tasche passen. Was dann überstünde, verkeilte sich
      beim Zusammenstecken.

    Ohne die zweite Prüfung wäre ein Verbinder zulässig, der zwar hält, aber
    nur, weil man ihn nie zusammenbekommt.
    """
    from app.core.knowledge.parts import shapes
    from app.core.knowledge.parts.mechanics import SNAP_RATIO

    diameter, length, play = 6.0, 9.0, 0.2
    arm = _snap(diameter=diameter, length=length, play=play, kind="pin")
    socket = _snap(diameter=diameter, length=length, play=play, kind="bore")

    thickness = length / SNAP_RATIO
    lip = _lip(arm, socket, 3.0 * thickness + play, length + shapes.SEAT_RELIEF)

    pulled = shapes.moved(arm, (0.0, 0.0, -0.1))
    bent = shapes.moved(arm, (0.0, -thickness, 0.0))

    assert _shared(pulled, lip) > 0.0, "beim Ziehen greift nichts — der Haken hält nicht"
    assert _shared(bent, lip) == 0.0, "der ausgewichene Arm verkeilt sich beim Einführen"


def test_a_seam_too_narrow_for_a_spring_arm_says_so_and_stays_round() -> None:
    """Regel 21 an einer Stelle, an der Raten teuer wäre.

    Ein Federarm braucht zehnmal seine Dicke an Länge, und die Länge hängt am
    Durchmesser, den die Naht hergibt. Unter 5,4 mm käme ein Arm heraus, der
    dünner ist als zwei Außenwände — er bräche beim ersten Zusammenstecken.

    Statt ihn trotzdem zu bauen, wird rund verstiftet **und gesagt, warum**.
    Stillschweigend etwas anderes zu liefern wäre der schlechtere von beiden
    Fehlern.
    """
    slim = MeshData.of(trimesh.creation.box(extents=(40.0, 12.0, 20.0)))
    plane = SectionPlane(normal=(0.0, 0.0, 1.0), position=0.0)

    plan = pins.plan_pins(slim, plane, shape="snap")

    assert plan.count, "die Naht trägt Stifte, nur eben keinen Schnapper"
    assert plan.length / 2.0 < pins.SNAP_MIN_REACH, "diese Naht sollte zu schmal sein"
    assert plan.shape == "round", "zu schmal für einen Arm — dann rund"
    assert [finding.code for finding in plan.findings] == ["split.snap_too_small"]


def test_a_wide_enough_seam_keeps_the_snap() -> None:
    """Die Gegenprobe: wo der Arm lang genug wird, bleibt es beim Schnapper.

    Ohne sie prüfte der Test darüber nur, dass irgendetwas rund herauskommt —
    auch dann, wenn der Schnapper nie ankäme.
    """
    plane = SectionPlane(normal=(0.0, 0.0, 1.0), position=0.0)

    plan = pins.plan_pins(block(), plane, shape="snap")

    assert plan.length / 2.0 >= pins.SNAP_MIN_REACH
    assert plan.shape == "snap"
    assert plan.findings == ()


def test_the_snap_stays_inside_its_circle_over_the_whole_range() -> None:
    """Derselbe Vertrag wie für die Querschnitte, nur schwerer einzuhalten.

    Beim Schnapper ist die *Tasche* das Weiteste: Sie trägt den Arm in Ruhe,
    den Haken daneben und den Weg, den der Arm beim Einrasten zurückweicht.
    Länge und Durchmesser sind unabhängig deklariert, also gibt es Ecken, an
    denen die Armstärke aus der Länge größer herauskäme, als der Kreis
    verträgt: bei Ø 30 mm und 100 mm Länge stand die Tasche 30,22 mm breit in
    einem 30er Kreis. Der Baustein kappt die Stärke deshalb selbst — nach
    unten, denn ein dünnerer Arm federt weicher und ein zu dicker bricht.

    Geprüft wird über die Ecken des Bereichs und nicht an einem Wert, weil
    genau dort der Fehler saß.
    """
    from itertools import product

    for diameter, length, play, kind in product(
        (4.0, 6.0, 30.0), (8.0, 9.0, 100.0), (0.0, 1.0), ("pin", "bore")
    ):
        body = _snap(diameter=diameter, length=length, play=play, kind=kind)
        low, high = body.raw.bounds
        span = high - low
        circle = float(np.hypot(span[0], span[1]))
        label = f"Ø{diameter} L{length} Spiel{play} {kind}"

        assert circle <= diameter + 1e-6, f"{label}: Umkreis {circle:.3f} sprengt den Kreis"
        assert body.raw.is_watertight, f"{label}: nicht wasserdicht"
        assert float(min(span[0], span[1])) >= 0.8 - 1e-9, f"{label}: dünner als zwei Wände"
