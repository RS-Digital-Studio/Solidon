"""Auto Split mit Verstiftung (Bauplan §25, §22.3, §14; §40 für P10).

Das Abnahmekriterium sind drei Sätze: jedes Teil für sich wasserdicht,
Passungspaare angelegt und geprüft, und ``oversized.stl`` in etwas Druckbares
geteilt, ohne dass jemand einen Parameter anfasst. Alle drei stehen hier.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import trimesh

from app.core.errors import ValidationError
from app.core.geom import autosplit, pins
from app.core.geom.mesh import MeshData, read_mesh
from app.core.geom.prepare import split_at_plane
from app.core.geom.section import SectionPlane
from app.core.ingest.loader import normalise
from app.core.registry import REGISTRY
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.cancel import NeverCancelled
from app.core.scene.project import Project, ProjectSources, new_project
from app.core.split import apply_line_split, apply_planned, apply_split, plan_split
from app.core.types import OpContext, Profile, Scene, SceneObject, Source

MESHES = Path(__file__).parent / "data" / "meshes"


def body(name: str = "oversized.stl") -> MeshData:
    """So, wie die Eingangsstufe ihn liefert — verschweißt und damit
    geschlossen.
    """
    return normalise(read_mesh((MESHES / name).read_bytes(), ".stl"), "mm").mesh


def bar(length: float = 400.0) -> MeshData:
    return MeshData.of(trimesh.creation.box(extents=(length, 60.0, 40.0)))


def dumbbell(neck: float = 30.0, flank: float = 60.0) -> MeshData:
    """Dicke Enden, ein Hals, der sich **stetig** auf ``neck`` verjüngt.

    Der Radius fällt über ``flank`` Millimeter von 40 auf ``neck`` und steigt
    wieder — eine **sanfte** Mulde, und das ist der Punkt.

    Drei Entwürfe davor trafen den Fall nicht, und jeder verfehlte ihn anders:

    * Zwei Kegel Spitze an Spitze berühren sich in einem Punkt mit Querschnitt
      **null**. Dort lässt sich gar nicht schneiden.
    * Ein Hals, der von −8 bis +8 gleich stark bleibt, ist im Suchfenster
      überall gleich dick — bei einem 400 mm langen Körper auf einem 220er
      Bett reicht das Fenster nur ±16 mm um die Mitte, weiter außen passt eine
      Hälfte nicht mehr. Es gab keine Kerbe zu erkennen, nur eine flache
      Strecke.
    * Eine **steile** Verjüngung über ±30 mm fängt schon der vorhandene
      ``PRISM_WEIGHT``-Term: Dort ändert sich der Querschnitt kräftig, und die
      Naht wandert von selbst weg. Der Test war grün, ohne den neuen Term zu
      brauchen.

    Die Lücke liegt dazwischen: eine Verjüngung, die flach genug ist, dass
    ``change`` sie über seine halbe Millimeter nicht sieht, und tief genug,
    dass die Naht dort nicht hingehört. Gemessen wählt die Suche ohne den
    Einschnürungsterm genau die Mitte, mit einer Punktzahl von 0,003.
    """
    profile_line = np.array(
        [
            [0.0, -200.0],
            [40.0, -200.0],
            [40.0, -flank],
            [neck, 0.0],
            [40.0, flank],
            [40.0, 200.0],
            [0.0, 200.0],
        ]
    )
    body_mesh = trimesh.creation.revolve(profile_line, sections=64)
    body_mesh.apply_transform(trimesh.transformations.rotation_matrix(np.pi / 2, [0, 1, 0]))
    return MeshData.of(body_mesh)


# --- die Suche ------------------------------------------------------------------


def test_a_part_that_fits_is_left_alone(profile: Profile) -> None:
    small = MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 20.0)))

    assert autosplit.fits(small, profile)
    assert autosplit.find_plane(small, profile) is None
    assert not autosplit.split_to_fit(small, profile).divided


def test_the_oversize_is_measured_per_axis(profile: Profile) -> None:
    over = autosplit.oversize(body(), profile)

    assert over[0] == pytest.approx(400.0 - 252.0), "252 mm usable of a 256 mm plate"
    assert over[1] == 0.0 and over[2] == 0.0


def test_the_plane_lands_in_the_slim_middle(profile: Profile) -> None:
    """§22.3: der Querschnitt entscheidet, und die schmale prismatische Mitte
    gewinnt.
    """
    candidate = autosplit.find_plane(body(), profile)

    assert candidate is not None
    assert candidate.axis == "x", "cut across the direction that is too long"
    assert -85.0 < candidate.position < 85.0, "inside the middle bar"
    assert candidate.contours == 1, "one seam, not several thin bridges"
    assert candidate.area == pytest.approx(40.0 * 30.0), "the section of the middle"


def test_a_seam_with_several_bridges_loses(profile: Profile) -> None:
    """Zwei Arme nebeneinander: quer durch beide zu schneiden ist schlechter,
    als die Verbindung zu schneiden.
    """
    left = trimesh.creation.box(extents=(300.0, 20.0, 20.0))
    left.apply_translation((0.0, -40.0, 10.0))
    right = trimesh.creation.box(extents=(300.0, 20.0, 20.0))
    right.apply_translation((0.0, 40.0, 10.0))
    joint = trimesh.creation.box(extents=(40.0, 100.0, 20.0))
    joint.apply_translation((0.0, 0.0, 10.0))
    fork = MeshData.of(trimesh.boolean.union([left, right, joint]))

    candidate = autosplit.find_plane(fork, profile)

    assert candidate is not None
    assert candidate.contours == 1
    assert abs(candidate.position) <= 20.0, "through the joint, not through both arms"


def test_the_seam_avoids_the_narrowest_place(profile: Profile) -> None:
    """§22.3, Festigkeit: durch die dünnste Stelle wird nicht getrennt.

    Eine Hantel — dicke Enden, eine Einschnürung in der Mitte. Bis hierher
    gewann genau diese Stelle: Sie hat **eine** Kontur, der Querschnitt ist
    dort am kleinsten, und sie liegt in der Mitte, also trugen alle drei
    bisherigen Terme sie. Gedruckt bricht das Teil dann an der Naht, denn
    quer zur Schicht ist die Verbindung ohnehin am schwächsten, und sie sitzt
    am dünnsten Querschnitt.

    Der Unterschied zu ``test_the_plane_lands_in_the_slim_middle`` ist die
    **Form** der dünnen Stelle, nicht ihre Dicke: Dort ist die Taille
    prismatisch, verläuft also über eine Strecke gleich — hier ist sie ein
    Minimum an einem Punkt. Die prismatische Taille bleibt die richtige Naht;
    verboten ist nur die Kerbe.
    """
    candidate = autosplit.find_plane(dumbbell(), profile)

    assert candidate is not None
    assert candidate.axis == "x", "quer zur langen Richtung"
    # Gemessen liegt das Minimum bei x = 0 mit 201 mm², die Flanken steigen
    # binnen fünfzehn Millimetern auf das Doppelte. Alles innerhalb von zehn
    # Millimetern um die Mitte ist die Kerbe.
    assert abs(candidate.position) > 10.0, (
        f"die Naht liegt bei {candidate.position:.1f} und damit in der Einschnürung — "
        "dort bricht das gedruckte Teil"
    )
    assert candidate.area > 400.0, (
        f"der Querschnitt der Naht ist {candidate.area:.0f} mm² und damit nahe am Minimum von 201"
    )


def test_a_prismatic_waist_is_still_the_right_seam(profile: Profile) -> None:
    """Die Gegenprobe zur Regel darüber, und sie ist die wichtigere Hälfte.

    Eine Einschnürung zu meiden ist nur dann richtig, wenn eine **prismatische**
    Taille weiterhin gewinnt — sonst hat die neue Regel die alte umgeworfen,
    statt sie zu ergänzen. ``oversized.stl`` hat genau so eine Taille, und die
    Naht gehört hinein.

    Steht dieser Test rot, ist der Einschnürungsterm zu grob: Er bestraft dann
    jede dünne Stelle statt nur die spitze.
    """
    candidate = autosplit.find_plane(body(), profile)

    assert candidate is not None
    assert candidate.area == pytest.approx(40.0 * 30.0), "weiterhin der Querschnitt der Mitte"


def test_a_body_twice_too_long_takes_two_cuts(profile: Profile) -> None:
    outcome = autosplit.split_to_fit(bar(600.0), profile)

    assert len(outcome.parts) == 3
    assert all(autosplit.fits(part, profile) for part in outcome.parts)


def test_every_piece_is_closed_and_nothing_is_lost(profile: Profile) -> None:
    """Das P10-Kriterium: jedes Teil wasserdicht, und das Volumen geht auf."""
    whole = body()
    outcome = autosplit.split_to_fit(whole, profile)

    assert outcome.divided
    assert all(part.is_watertight for part in outcome.parts)
    assert sum(part.volume for part in outcome.parts) == pytest.approx(whole.volume, rel=1e-6)
    assert all(autosplit.fits(part, profile) for part in outcome.parts)


def test_the_steps_say_which_piece_was_cut(profile: Profile) -> None:
    """Ohne das lässt sich der Stapel nicht bauen — der nächste Schnitt
    braucht ein Objekt.
    """
    outcome = autosplit.split_to_fit(bar(600.0), profile)

    assert [step.part_index for step in outcome.cuts] == [0, 1]


def test_the_search_stops_instead_of_cutting_forever(profile: Profile) -> None:
    outcome = autosplit.split_to_fit(bar(4000.0), profile, max_parts=4)

    assert len(outcome.parts) == 4
    assert "split.too_many_parts" in {finding.code for finding in outcome.findings}


def test_the_pin_overhang_counts_towards_the_bed(profile: Profile) -> None:
    """§25: Ein Passstift steht über die Schnittfläche, also ragt die
    verstiftete Hälfte weiter als ihr nacktes Netz.

    ``oversize`` mit Zugabe rechnet ihn mit; ohne Zugabe misst es das blanke
    Netz wie zuvor. Der Quader passt nackt genau aufs Bett.
    """
    limit = profile.printer.build_volume[0] - 2.0 * autosplit.MARGIN
    box = MeshData.of(trimesh.creation.box(extents=(limit, 40.0, 40.0)))

    assert autosplit.oversize(box, profile)[0] == pytest.approx(0.0), "nackt passt es genau"
    assert autosplit.oversize(box, profile, allowance=(7.0, 0.0, 0.0))[0] == pytest.approx(7.0)


def test_a_half_with_its_pin_stays_on_the_bed(profile: Profile) -> None:
    """§25: Auto Split rechnet den Stiftüberstand ein und teilt feiner.

    Der Quader ist zwei Bettlängen weniger sechs Millimeter lang: eine einzige
    Naht ließe beide Hälften nackt aufs Bett passen — knapp. Mit Stift stünde
    jede darüber (gemessen 259,8 mm auf einem 252er Bett, bevor die Prüfung den
    Überstand kannte). Also entsteht ein dritter Schnitt, und keine Hälfte ragt
    mitsamt Stift über das Bett.
    """
    limit = profile.printer.build_volume[0] - 2.0 * autosplit.MARGIN
    box = MeshData.of(trimesh.creation.box(extents=(2.0 * limit - 6.0, 60.0, 60.0)))

    outcome = autosplit.split_to_fit(box, profile)

    assert len(outcome.parts) >= 3, "eine Naht reichte nackt, mit Stift nicht"
    for part in outcome.parts:
        seam = SectionPlane(autosplit.AXIS_NORMALS["x"], float(part.bounds.centre[0]))
        overhang = pins.plan_pins(part, seam).length / 2.0
        assert part.bounds.size[0] + overhang <= limit + autosplit.EPS_GEOM, (
            "Hälfte samt Stift bleibt auf dem Bett"
        )


def test_without_pins_the_bed_check_is_the_bare_extent(profile: Profile) -> None:
    """Die Gegenprobe: Wer ohne Stifte teilt, bekommt keine Zugabe.

    Derselbe Quader wie oben, aber ``pins=0``. Ohne Stift steht nichts über, die
    alte Rechnung bleibt, und eine einzige Naht genügt.
    """
    limit = profile.printer.build_volume[0] - 2.0 * autosplit.MARGIN
    box = MeshData.of(trimesh.creation.box(extents=(2.0 * limit - 6.0, 60.0, 60.0)))

    outcome = autosplit.split_to_fit(box, profile, pins=0)

    assert len(outcome.parts) == 2, "nackt reicht eine Naht"


def test_convex_parts_take_an_l_apart(profile: Profile) -> None:
    """§22.3: die Zerlegung findet, wo ein L von selbst auseinanderfällt.

    Dieser Test übersprang sich früher, wenn die Antwort leer war, und die
    Antwort war immer leer: der Aufruf übergab ein ``randomizeSeed``, das dieses
    V-HACD nicht hat, der TypeError wurde als „Modul fehlt" gelesen, und der
    ganze Hinweispfad der Ebenensuche war hinter einer grünen Suite tot. Also:
    kein Skip. Ist V-HACD installiert, muss es liefern, und die Ecke des L ist
    das, was es finden muss.
    """
    shape = trimesh.boolean.union(
        [
            trimesh.creation.box(extents=(60.0, 20.0, 20.0)),
            trimesh.creation.box(extents=(20.0, 20.0, 60.0)).apply_translation([20.0, 0.0, 40.0]),
        ]
    )
    parts = autosplit.convex_parts(MeshData.of(shape))

    assert len(parts) >= 2, "an L is not convex"
    assert sum(abs(part.volume) for part in parts) == pytest.approx(abs(shape.volume), rel=0.05)
    assert [abs(part.volume) for part in parts] == sorted(
        (abs(part.volume) for part in parts), reverse=True
    ), "largest first, as documented"


def test_convex_parts_are_reproducible(profile: Profile) -> None:
    """§11.3: derselbe Körper gibt dieselben Stücke, ohne einen Startwert zu
    speichern.
    """
    shape = trimesh.boolean.union(
        [
            trimesh.creation.box(extents=(60.0, 20.0, 20.0)),
            trimesh.creation.box(extents=(20.0, 20.0, 60.0)).apply_translation([20.0, 0.0, 40.0]),
        ]
    )
    first = autosplit.convex_parts(MeshData.of(shape))
    second = autosplit.convex_parts(MeshData.of(shape))

    assert len(first) == len(second)
    assert [round(part.volume, 3) for part in first] == [round(part.volume, 3) for part in second]


# --- die Passstifte -------------------------------------------------------------


def test_pins_sit_inside_the_cut_face(profile: Profile) -> None:
    whole = body()
    candidate = autosplit.find_plane(whole, profile)
    assert candidate is not None

    plan = pins.plan_pins(whole, candidate.plane)

    assert plan.count == 2, "one pin is a hinge"
    assert pins.PIN_MIN <= plan.diameter <= pins.PIN_MAX
    for position in plan.positions:
        assert position[0] == pytest.approx(candidate.position), "on the parting plane"
        assert abs(position[1]) < 20.0 and 5.0 < position[2] < 35.0, "inside the middle bar"


def test_a_face_too_small_gets_no_pins_and_says_so(profile: Profile) -> None:
    """Eine Naht ohne Stifte klebt immer noch; ein Stift durch die Wand nicht."""
    thin = MeshData.of(trimesh.creation.box(extents=(400.0, 3.0, 3.0)))
    candidate = autosplit.find_plane(thin, profile)
    assert candidate is not None

    plan = pins.plan_pins(thin, candidate.plane)

    assert plan.count == 0
    assert [finding.code for finding in plan.findings] == ["split.face_too_small"]


def wall(thickness: float) -> MeshData:
    """Eine Trennwand: große Fläche, wenig Material dahinter.

    Der Fall, den die Schnittfläche allein nicht erkennt. Der Schnitt bei
    y = 0 liefert 100 mal 100 Millimeter — reichlich Platz für zwei Stifte samt
    Wand —, und in Richtung der Stiftachse steht die halbe Wandstärke. So sieht
    jede Trennwand eines Kastens aus.
    """
    return MeshData.of(trimesh.creation.box(extents=(100.0, thickness, 100.0)))


#: Die Ebene quer durch eine solche Wand. Ihre Normale ist die Stiftachse.
WALL_PLANE = SectionPlane(normal=(0.0, 1.0, 0.0), position=0.0)


def usable_in(thickness: float) -> float:
    """Die Einbindung, die eine Wand dieser Dicke hergibt.

    Die halbe Wand, abzüglich des Freistichs, um den die Bohrung tiefer reicht
    als der Stift, und einer Wandstärke, die hinter ihr stehen bleiben muss.
    """
    return thickness / 2.0 - pins.BORE_RELIEF - pins.PIN_WALL


def test_a_seam_with_nothing_behind_it_gets_no_pins_and_says_so(profile: Profile) -> None:
    """Eine 3-mm-Wand trägt keinen Stift, so groß ihre Schnittfläche auch ist.

    Gemessen am Besteckkorb gefunden: zehn geplante Stifte, je 12 mm tief, und
    an jeder Stelle 1,5 mm Material. Die Stifte standen im Fach, die Bohrungen
    gingen durch die Wand, und gemeldet wurde nichts — die Fläche war ja groß
    genug. Sie ist die falsche Größe: quer ist nicht tief.
    """
    plan = pins.plan_pins(wall(3.0), WALL_PLANE)

    assert plan.count == 0
    assert [finding.code for finding in plan.findings] == ["split.seam_too_thin"]
    values = plan.findings[0].values
    assert values["depth_mm"] == pytest.approx(1.5), "die halbe Wandstärke steht zur Verfügung"
    assert values["needed_mm"] > values["depth_mm"], "und sie reicht nicht"


def test_a_thick_enough_seam_keeps_the_full_pin(profile: Profile) -> None:
    """Wo Material steht, ändert die Messung nichts.

    Die Gegenprobe zum Fall darüber: derselbe Körper, nur 40 mm dick. Der Stift
    bekommt seine volle Länge — anderthalb Durchmesser je Hälfte —, und kein
    Befund entsteht.
    """
    plan = pins.plan_pins(wall(40.0), WALL_PLANE)

    assert plan.count == 2
    assert plan.diameter == pytest.approx(pins.PIN_MAX), "die Fläche gibt den dicksten her"
    assert plan.length == pytest.approx(plan.diameter * pins.PIN_DEPTH_FACTOR * 2.0)
    assert not plan.findings


def test_a_tight_seam_shortens_the_pin_instead_of_dropping_it(profile: Profile) -> None:
    """Dazwischen wird gekürzt, nicht verworfen.

    24 mm Wand heißt 12 mm je Seite und damit 10 mm Einbindung — weniger als
    die 12 mm, die ein Stift von 8 mm gern hätte, und mehr als die 6 mm, unter
    denen er nichts mehr führt. Der Durchmesser bleibt, die Länge gibt nach.
    """
    plan = pins.plan_pins(wall(24.0), WALL_PLANE)

    assert plan.count == 2
    assert plan.diameter == pytest.approx(pins.PIN_MAX), "quer ist Platz genug"
    reach = plan.length / 2.0
    assert reach == pytest.approx(usable_in(24.0))
    assert reach < plan.diameter * pins.PIN_DEPTH_FACTOR, "gekürzt gegenüber dem Wunsch"


def test_a_tighter_seam_thins_the_pin_before_giving_up(profile: Profile) -> None:
    """Und darunter wird er dünner, nicht keiner.

    12 mm Wand geben 4 mm Einbindung. Für einen Stift von 8 mm ist das zu
    wenig — er bräuchte 6 —, aber Einbindung und Durchmesser hängen aneinander:
    ein dünnerer kommt mit weniger aus. Gewählt wird der dickste, der noch
    sitzt, und das ist die Rechnung rückwärts.
    """
    plan = pins.plan_pins(wall(12.0), WALL_PLANE)

    assert plan.count == 2
    assert pins.PIN_MIN <= plan.diameter < pins.PIN_MAX, "dünner, aber nicht zu dünn"
    reach = plan.length / 2.0
    assert reach == pytest.approx(usable_in(12.0))
    assert reach == pytest.approx(plan.diameter * pins.PIN_MIN_ENGAGEMENT), "gerade noch führend"


def test_the_pin_goes_into_one_half_and_the_bore_into_the_other(profile: Profile) -> None:
    whole = body()
    candidate = autosplit.find_plane(whole, profile)
    assert candidate is not None
    first, second, _findings = split_at_plane(whole, candidate.plane)
    plan = pins.plan_pins(whole, candidate.plane)

    pair = pins.add_pins(first, second, plan, profile)

    assert pair.first.is_watertight and pair.second.is_watertight
    assert pair.first.volume > first.volume, "the pins add material"
    assert pair.second.volume < second.volume, "the bores take it away"
    assert sorted(pair.pin_features) == ["pin_1", "pin_2"]
    assert sorted(pair.bore_features) == ["bore_1", "bore_2"]


def test_the_play_comes_from_the_material_profile(profile: Profile) -> None:
    """Regel 7: die Bohrung ist der Stift plus das kalibrierte Spiel, nie ein
    Literal.
    """
    whole = body()
    candidate = autosplit.find_plane(whole, profile)
    assert candidate is not None
    first, second, _findings = split_at_plane(whole, candidate.plane)
    plan = pins.plan_pins(whole, candidate.plane)

    pair = pins.add_pins(first, second, plan, profile)

    pin = pair.pin_features["pin_1"].params["diameter"]
    bore = pair.bore_features["bore_1"].params["diameter"]
    assert bore - pin == pytest.approx(profile.material.clearance)


# --- Als Operation ---------------------------------------------------------------


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


def test_split_pinned_runs_as_an_operation(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Balken", mesh=body())

    result = run("split_pinned", entry, profile, axis="x", position=0.0, pins=2)

    assert [output.name for output in result.outputs] == [
        "Balken A · Stifte",
        "Balken B · Löcher",
    ], "beim Export ist der Name die einzige Auskunft darüber, welches Teil welches ist"
    assert all(output.mesh.is_watertight for output in result.outputs)
    assert "pin_1" in result.outputs[0].features
    assert "bore_1" in result.outputs[1].features


def test_split_pinned_can_also_just_cut(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Balken", mesh=body())

    result = run("split_pinned", entry, profile, axis="x", position=0.0, pins=0)

    assert not any("pin_1" in output.features for output in result.outputs)
    assert all(output.mesh.is_watertight for output in result.outputs)


def test_a_plane_that_misses_the_body_is_a_user_error(profile: Profile) -> None:
    entry = SceneObject(id="obj_1", name="Balken", mesh=body())

    with pytest.raises(ValidationError) as problem:
        run("split_pinned", entry, profile, axis="x", position=9999.0, pins=2)

    assert problem.value.field == "position"


# --- der ganze Weg --------------------------------------------------------------


@pytest.fixture
def loaded(profile: Profile) -> tuple[Project, MeshData]:
    project = new_project("centauri-carbon-2", "petg")
    payload = (MESHES / "oversized.stl").read_bytes()
    project.sources["src_1"] = payload
    project.document.sources["src_1"] = Source(
        id="src_1", kind="import", path="sources/oversized.stl", sha256=""
    )
    History(project.document).apply(
        "Laden", [OperationDraft(op="load", params={"source": "src_1", "unit": "mm"})]
    )
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    return project, result.scene.objects["obj_1"].mesh


def test_the_plan_is_one_operation_per_cut(loaded, profile: Profile) -> None:
    _project, mesh = loaded

    plan = plan_split(mesh, "obj_1", profile)

    assert plan.cuts == 1
    assert all(draft.op == "split_pinned" for draft in plan.drafts)
    assert plan.drafts[0].params["axis"] == "x"


def test_oversized_is_divided_without_anybody_touching_a_parameter(
    loaded, profile: Profile
) -> None:
    """Das P10-Abnahmekriterium, Ende zu Ende (§40)."""
    project, mesh = loaded

    applied = apply_split(project.document, mesh, "obj_1", profile)
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete
    assert len(applied.object_ids) == 2
    for object_id in applied.object_ids:
        part = result.scene.objects[object_id]
        assert part.mesh.is_watertight, object_id
        assert autosplit.fits(part.mesh, profile), object_id


def test_splitting_a_piece_again_keeps_its_existing_fits(profile: Profile) -> None:
    """Zweimal trennen erhält die erste Naht auf dem richtigen Kindstück.

    So gefunden: Sechs Fachmodule über fünf gezeichnete Schnitte, und danach
    nur vier statt zehn Verbindungsgruppen. Ein Teil in mehr als zwei Stücke zu
    schneiden heißt, ein schon geschnittenes noch einmal zu schneiden. Seine
    Passungen müssen deshalb mitwandern, während die neue Naht eigene,
    unverwechselbare Merkmalskennungen bekommt.
    """
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Anlegen",
        [OperationDraft(op="create_box", params={"width": 80.0, "depth": 60.0, "height": 40.0})],
    )
    block = MeshData.of(trimesh.creation.box(extents=(80.0, 60.0, 40.0)))

    first = apply_line_split(
        project.document, "obj_1", SectionPlane((1.0, 0.0, 0.0), 0.0), profile, mesh=block
    )
    assert len(first.fits) == 2, "die erste Naht bekommt ihre Paare"
    assert project.document.fits == first.fits

    halved = evaluate(project.document, profile, sources=ProjectSources(project))
    target = first.object_ids[0]
    second = apply_line_split(
        project.document,
        target,
        SectionPlane((0.0, 1.0, 0.0), 0.0),
        profile,
        mesh=halved.scene.objects[target].mesh,
        features=halved.scene.objects[target].features,
    )

    assert not [finding for finding in second.findings if finding.code == "split.fit_dropped"]
    assert {fit.name for fit in first.fits} <= {fit.name for fit in project.document.fits}, (
        "die erste Naht bleibt unter ihrer Kennung erhalten"
    )
    assert len(project.document.fits) == 4, "beide Nähte tragen je zwei Passungen"
    assert [fit.a.feature_id for fit in second.fits] == ["pin_3", "pin_4"]
    assert [fit.b.feature_id for fit in second.fits] == ["bore_3", "bore_4"]

    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert result.complete
    codes = [finding.code for finding in result.scene.report.findings]
    assert "fit.missing_feature" not in codes, codes


def test_a_cut_through_an_existing_connector_drops_only_that_fit(profile: Profile) -> None:
    """Eine gestreifte Verbindung darf nicht als voll tragfähig weiterleben.

    Der Mittelpunkt allein reicht dafür nicht: Eine Ebene kann den Rand eines
    Stifts schneiden, obwohl sein Mittelpunkt eindeutig auf einer Seite liegt.
    Dann entfällt genau dieses Paar; die andere alte Verbindung bleibt erhalten.
    """
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Anlegen",
        [OperationDraft(op="create_box", params={"width": 80.0, "depth": 60.0, "height": 40.0})],
    )
    block = MeshData.of(trimesh.creation.box(extents=(80.0, 60.0, 40.0)))
    first = apply_line_split(
        project.document, "obj_1", SectionPlane((1.0, 0.0, 0.0), 0.0), profile, mesh=block
    )
    halved = evaluate(project.document, profile, sources=ProjectSources(project))
    target = first.object_ids[0]
    entry = halved.scene.objects[target]
    pin = entry.features["pin_1"]
    centre = pin.params["centre"]
    diameter = float(pin.params["diameter"])
    plane = SectionPlane((0.0, 1.0, 0.0), float(centre[1]) + diameter / 4.0)

    second = apply_line_split(
        project.document,
        target,
        plane,
        profile,
        mesh=entry.mesh,
        features=entry.features,
    )

    assert [finding.code for finding in second.findings].count("split.fit_dropped") == 1
    assert first.fits[0] not in project.document.fits, "der angeschnittene Stift trägt nicht mehr"
    assert first.fits[1].name in {fit.name for fit in project.document.fits}
    result = evaluate(project.document, profile, sources=ProjectSources(project))
    assert "fit.missing_feature" not in [finding.code for finding in result.scene.report.findings]


def test_undo_brings_the_dropped_fits_back(profile: Profile) -> None:
    """Und ein Undo holt sie zurück — sie reisen in der Transaktion.

    Die Passungen wurden bisher **nach** dem Aufruf ins Dokument geschrieben,
    also an der Transaktion vorbei: Ein Undo nahm die Teilung zurück und ließ
    die Paare stehen. Jetzt bildet ``History.apply`` sie aus den geplanten
    Operationen, und beides ist ein Schritt.
    """
    project = new_project("centauri-carbon-2", "petg")
    history = History(project.document)
    history.apply(
        "Anlegen",
        [OperationDraft(op="create_box", params={"width": 80.0, "depth": 60.0, "height": 40.0})],
    )
    block = MeshData.of(trimesh.creation.box(extents=(80.0, 60.0, 40.0)))

    applied = apply_line_split(
        project.document, "obj_1", SectionPlane((1.0, 0.0, 0.0), 0.0), profile, mesh=block
    )
    assert project.document.fits == applied.fits

    History(project.document).undo()

    assert project.document.fits == [], "was die Teilung anlegte, nimmt das Undo mit"


def test_auto_split_leaves_no_dead_fit_after_two_cuts(profile: Profile) -> None:
    """Zwei Schnitte in **einem** Auto-Split-Lauf hinterlassen keine tote Passung.

    Auto Split legt je Schnitt ein Passungspaar an. Teilte ein späterer Schnitt
    desselben Laufs ein schon verstiftetes Stück noch einmal, blieben dessen
    Paare stehen und zeigten ins Leere: zwei ``fit.missing_feature`` im
    Prüfbericht, obwohl niemand einen Parameter angefasst hatte. Der Balken ist
    doppelt zu lang und braucht darum zwei Schnitte.

    Das Gegenstück zu ``test_splitting_a_piece_again_lets_its_fits_go``: dort
    zwei gezeichnete Schnitte in zwei Läufen, hier zwei aus einem Lauf — die
    entfielen bisher nur im Dokument, nicht im Lauf-Akkumulator, und der schrieb
    sie über ``change_for`` erneut hinein.
    """
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Anlegen",
        [OperationDraft(op="create_box", params={"width": 600.0, "depth": 60.0, "height": 40.0})],
    )
    block = MeshData.of(trimesh.creation.box(extents=(600.0, 60.0, 40.0)))

    applied = apply_split(project.document, block, "obj_1", profile)

    assert len(applied.object_ids) == 3, "doppelt zu lang: zwei Schnitte, drei Stücke"
    assert [finding.code for finding in applied.findings].count("split.fit_dropped") == 2

    result = evaluate(project.document, profile, sources=ProjectSources(project))
    codes = [finding.code for finding in result.scene.report.findings]
    assert "fit.missing_feature" not in codes, codes

    live = set(applied.object_ids)
    for fit in project.document.fits:
        assert fit.a.object_id in live and fit.b.object_id in live, fit.name


def test_the_seams_become_fit_pairs(loaded, profile: Profile) -> None:
    """§14: Auto Split legt die Paare an, denn dort entstehen sie."""
    project, mesh = loaded

    applied = apply_split(project.document, mesh, "obj_1", profile)

    assert [fit.tolerance for fit in applied.fits] == ["auto:petg", "auto:petg"]
    assert project.document.fits == applied.fits
    assert applied.fits[0].a.feature_id == "pin_1"
    assert applied.fits[0].b.feature_id == "bore_1"


def test_a_seam_without_pins_gets_no_fit_pair(profile: Profile) -> None:
    """Ein Paar, dessen beide Seiten es nicht gibt, ist schlimmer als keines.

    Ist die Schnittfläche für Stifte zu schmal, setzt ``plan_pins`` keinen und
    sagt das als Befund. Die Passung entstand hier trotzdem — und die
    Passungsprüfung meldete danach eine Verletzung an einem Teil, das in
    Ordnung ist.

    Der Balken ist genau dafür gebaut: vierhundert Millimeter lang, drei mal
    drei im Querschnitt. Er muss geteilt werden, und auf neun Quadratmillimeter
    passt kein Stift samt Wand.
    """
    project = new_project("centauri-carbon-2", "petg")
    History(project.document).apply(
        "Anlegen",
        [OperationDraft(op="create_box", params={"width": 400.0, "depth": 3.0, "height": 3.0})],
    )
    thin = MeshData.of(trimesh.creation.box(extents=(400.0, 3.0, 3.0)))

    plan = plan_split(thin, "obj_1", profile)

    assert plan.cuts, "der Balken passt nicht auf das Bett und wird geteilt"
    assert all(count == 0 for count in plan.seated), "auf 3 × 3 mm sitzt kein Stift"

    applied = apply_planned(project.document, plan, "obj_1", profile)

    assert applied.fits == [], "keine Passung ohne Stift, auf den sie zeigt"
    assert project.document.fits == []


def test_the_pairs_hold_when_the_scene_is_checked(loaded, profile: Profile) -> None:
    project, mesh = loaded
    apply_split(project.document, mesh, "obj_1", profile)

    result = evaluate(project.document, profile, sources=ProjectSources(project))

    codes = {finding.code for finding in result.scene.report.findings}
    assert "fit.violated" not in codes
    assert "fit.missing_feature" not in codes


def test_one_undo_takes_a_cut_back(loaded, profile: Profile) -> None:
    project, mesh = loaded
    apply_split(project.document, mesh, "obj_1", profile)

    History(project.document).undo()
    result = evaluate(project.document, profile, sources=ProjectSources(project))

    assert result.complete
    assert list(result.scene.objects) == ["obj_1"], "the whole part is back"


def test_a_part_that_already_fits_is_not_cut(profile: Profile) -> None:
    project = new_project("centauri-carbon-2", "petg")
    small = MeshData.of(trimesh.creation.box(extents=(20.0, 20.0, 20.0)))

    applied = apply_split(project.document, small, "obj_1", profile)

    assert applied.object_ids == ["obj_1"]
    assert applied.fits == []
    assert project.document.ops == []


def test_the_sections_of_a_turned_axis_match_the_upright_ones(profile: Profile) -> None:
    """Die Drehung muss exakt sein — die Stiftpositionen werden durch sie
    gerechnet.
    """
    plate = MeshData.of(trimesh.creation.box(extents=(60.0, 40.0, 20.0)))

    along_z = autosplit.sections_along(plate, "z", np.array([0.0]))[0]
    along_x = autosplit.sections_along(plate, "x", np.array([0.0]))[0]

    assert along_z is not None and along_x is not None
    assert along_z.area == pytest.approx(60.0 * 40.0)
    assert along_x.area == pytest.approx(40.0 * 20.0)
