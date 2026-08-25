"""Bohren, Teilen, Anordnen und Kollisionen (Bauplan §25, §39, §18.6)."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest
import trimesh

from app.core.geom.mesh import MeshData, on_surface, read_mesh
from app.core.geom.prepare import (
    BOOLEAN_OVERLAP,
    arrange_on_bed,
    bore_diameter,
    check_build_volume,
    check_collisions,
    drill,
    plug,
    split_at_plane,
)
from app.core.geom.section import SectionPlane
from app.core.geom.transform import apply, translation
from app.core.ingest.loader import normalise
from app.core.knowledge import profiles
from app.core.registry import REGISTRY, VARIABLE
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import ProjectSources, new_project
from app.core.types import Document, Profile, Source
from app.i18n import _

MESHES = Path(__file__).parent / "data" / "meshes"


def plate():
    """80 x 50 x 8 mm, watertight."""
    return normalise(read_mesh((MESHES / "plate_holes.stl").read_bytes(), ".stl"), "mm").mesh


def cube():
    return normalise(read_mesh((MESHES / "cube_clean.stl").read_bytes(), ".stl"), "mm").mesh


def l_profile() -> MeshData:
    """Grundplatte 60x40x10 und ein Steg 10x40x40 an einem Ende — Hüllquader
    z 0..40, aus zwei Quadern verschmolzen (Volumen 36000 mm³).

    Ein gestufter Körper, an dem sich die Mitte des Hüllquaders und das Material
    trennen: Wer die Plattenoberseite bei ``z = 10`` anklickt, liegt unter der
    Hüllquader-Mitte (``z = 20``), das Material aber darunter. Nur an der
    Hüllquader-Hälfte gemessen zeigte ein Werkzeug hier nach oben, in die Luft.
    """
    plate = trimesh.creation.box(extents=(60.0, 40.0, 10.0))
    plate.apply_translation((0.0, 0.0, 5.0))
    steg = trimesh.creation.box(extents=(10.0, 40.0, 40.0))
    steg.apply_translation((25.0, 0.0, 20.0))
    return MeshData.of(trimesh.boolean.union([plate, steg]))


# --- bores ----------------------------------------------------------------------


def test_a_bore_is_cut_larger_than_nominal(profile: Profile) -> None:
    """§39: FDM druckt Löcher zu eng, die Bohrung wird also größer — aus dem
    Profil.
    """
    petg = profiles.material("petg")
    assert bore_diameter(5.0, profile, compensate=True) == pytest.approx(
        5.0 + petg.hole_compensation
    )
    assert bore_diameter(5.0, profile, compensate=False) == pytest.approx(5.0)


def test_the_compensation_comes_from_the_material_not_from_a_literal() -> None:
    """AGENTS.md Regel 7: Toleranzen sind Verweise ins Profil."""
    petg = profiles.make_profile("centauri-carbon-2", "petg")
    tpu = profiles.make_profile("centauri-carbon-2", "tpu-95a")

    assert bore_diameter(5.0, petg, True) != bore_diameter(5.0, tpu, True)


def test_drilling_removes_material(profile: Profile) -> None:
    body = cube()
    result = drill(body, position=(0.0, 0.0, 0.0), axis="z", diameter=6.0, profile=profile)

    assert result.mesh.is_watertight
    assert result.mesh.volume < body.volume
    expected = body.volume - math.pi * (result.diameter / 2.0) ** 2 * 20.0
    assert result.mesh.volume == pytest.approx(expected, rel=0.01)


def test_a_bore_hanging_over_the_edge_says_so(profile: Profile) -> None:
    """Der Fall, den das Modell im Chat gebaut hat, und niemand widersprach.

    Auf „ein 5-mm-Loch mittig durch" kam ``x = 15, y = 10`` — die Ecke eines
    Quaders, der von −15 bis 15 reicht, weil das Modell mit einer Ecke im
    Ursprung rechnete. Abgetragen wurde ein Viertel: 53 statt 212 mm³. Es gab
    keinen Befund dazu, denn abgetragen *wurde* ja etwas, und der Agent
    schrieb danach „Das Loch ist durchgehend und mittig positioniert".
    """
    body = cube()
    edge = body.bounds.maximum[0]

    result = drill(body, position=(edge, 0.0, 0.0), axis="z", diameter=6.0, profile=profile)

    assert "bore.over_the_edge" in {finding.code for finding in result.findings}


def frame() -> MeshData:
    """60 x 60 x 14 mm mit einer 40er Öffnung — ein Rahmen.

    Die Form, an der der Streifschnitt gefunden wurde: der Hüllquader sagt
    „hier ist Material", und in der Mitte ist keines.
    """
    outer = trimesh.creation.box(extents=(60.0, 60.0, 14.0))
    outer.apply_translation((0.0, 0.0, 7.0))
    inner = trimesh.creation.box(extents=(40.0, 40.0, 30.0))
    inner.apply_translation((0.0, 0.0, 7.0))
    return MeshData.of(trimesh.boolean.difference([outer, inner]))


def test_a_bore_that_only_grazes_says_so(profile: Profile) -> None:
    """Ein Span ist kein Abtrag — und war doch mehr als ``EPS_GEOM``.

    Gemessen am Sockel eines Kunden: eine Bohrung Ø4,2, gesetzt auf die Mitte
    des Hüllquaders, traf die Öffnung des Rahmens statt das Material. Abgetragen
    wurden 0,002 mm³ statt 194 — und weil 0,002 größer ist als das
    Rechenepsilon, blieb es still. Gemessen wird jetzt an der Düse: was unter
    einem Stück Extrusionsbahn liegt, ist nichts (§2.7).
    """
    body = frame()
    grazing = 17.808

    result = drill(body, position=(grazing, 0.0, 14.0), axis="z", diameter=4.2, profile=profile)

    removed = body.volume - result.mesh.volume
    assert 0.0 < removed < profile.smallest_printable_volume, f"ein Span, kein Loch: {removed}"
    assert "boolean.without_effect" in {finding.code for finding in result.findings}


def test_a_bore_that_takes_a_visible_bite_stays_quiet(profile: Profile) -> None:
    """Die Gegenprobe: derselbe Rahmen, drei Hundertstel weiter im Material.

    Ohne sie wäre die Grenze ungeprüft — und eine Warnung, die auch über einem
    Loch steht, das man sehen kann, ist keine.
    """
    body = frame()

    result = drill(body, position=(17.9, 0.0, 14.0), axis="z", diameter=4.2, profile=profile)

    removed = body.volume - result.mesh.volume
    assert removed > profile.smallest_printable_volume
    assert "boolean.without_effect" not in {finding.code for finding in result.findings}


def test_a_bore_well_inside_stays_quiet(profile: Profile) -> None:
    """Die Gegenprobe — sonst warnt jede zweite Bohrung und keine zählt mehr."""
    result = drill(cube(), position=(0.0, 0.0, 0.0), axis="z", diameter=6.0, profile=profile)

    assert "bore.over_the_edge" not in {finding.code for finding in result.findings}


def test_a_bore_touching_the_edge_from_inside_stays_quiet(profile: Profile) -> None:
    """Eine Bohrung, die den Rand gerade noch trifft, ist eine Absicht und
    kein Versehen; gewarnt wird erst, wenn sie darüber hinausragt."""
    body = cube()
    inside = body.bounds.maximum[0] - 3.2

    result = drill(body, position=(inside, 0.0, 0.0), axis="z", diameter=6.0, profile=profile)

    assert "bore.over_the_edge" not in {finding.code for finding in result.findings}


def test_a_blind_bore_does_not_go_through(profile: Profile) -> None:
    body = cube()
    through = drill(body, position=(0.0, 0.0, 0.0), axis="z", diameter=6.0, profile=profile)
    blind = drill(
        body, position=(0.0, 0.0, 5.0), axis="z", diameter=6.0, depth=10.0, profile=profile
    )

    assert blind.mesh.volume > through.mesh.volume, "a blind bore removes less"
    assert blind.mesh.is_watertight


def test_a_bore_starts_where_it_was_placed(profile: Profile) -> None:
    """§25: die Position ist die Mündung, und von dort geht es ins Material.

    Der Würfel steht von -10 bis +10. Wer die Oberseite anklickt, bekommt
    ``z = 10`` eingetragen und meint eine Bohrung, die dort anfängt: fünf
    Millimeter tief heißt bis ``z = 5``. Vor Formatversion 7 lag die *Mitte*
    dort — die Bohrung ging bis 7,5 und stand zur Hälfte in der Luft.
    """
    body = cube()
    mouth = drill(
        body, position=(0.0, 0.0, 10.0), axis="z", diameter=6.0, depth=5.0, profile=profile
    )
    centred = drill(
        body,
        position=(0.0, 0.0, 10.0),
        axis="z",
        diameter=6.0,
        depth=5.0,
        anchor="centre",
        profile=profile,
    )

    area = math.pi * (mouth.diameter / 2.0) ** 2
    assert body.volume - mouth.mesh.volume == pytest.approx(area * 5.0, rel=0.02)
    assert body.volume - centred.mesh.volume == pytest.approx(area * 2.5, rel=0.02)


def test_the_mouth_of_a_bore_finds_the_material_from_either_side(profile: Profile) -> None:
    """Von unten angeklickt geht es nach oben — sonst bohrte eine Bohrung an
    der Unterseite ins Nichts.
    """
    body = cube()
    result = drill(
        body, position=(0.0, 0.0, -10.0), axis="z", diameter=6.0, depth=5.0, profile=profile
    )

    area = math.pi * (result.diameter / 2.0) ** 2
    assert body.volume - result.mesh.volume == pytest.approx(area * 5.0, rel=0.02)


def test_a_through_bore_ignores_the_anchor(profile: Profile) -> None:
    """Durch ist durch: bei Tiefe null darf der Bezugspunkt nichts ändern —
    das ist es, was die Migration alter Dateien so einfach hält.
    """
    body = cube()
    mouth = drill(body, position=(0.0, 0.0, 10.0), axis="z", diameter=6.0, profile=profile)
    centred = drill(
        body, position=(0.0, 0.0, 10.0), axis="z", diameter=6.0, anchor="centre", profile=profile
    )

    assert mouth.mesh.volume == pytest.approx(centred.mesh.volume, rel=1e-9)
    assert mouth.mesh.volume == pytest.approx(
        body.volume - math.pi * (mouth.diameter / 2.0) ** 2 * 20.0, rel=0.01
    )


@pytest.mark.parametrize("axis", ["x", "y", "z"])
def test_a_bore_follows_its_axis(axis: str, profile: Profile) -> None:
    result = drill(
        cube(),
        position=(0.0, 0.0, 0.0),
        axis=axis,
        diameter=6.0,
        profile=profile,  # type: ignore[arg-type]
    )
    assert result.mesh.is_watertight
    assert result.mesh.volume < cube().volume


def test_a_blind_bore_into_a_step_reaches_the_material(profile: Profile) -> None:
    """Zwilling des Senkungs-Fixes (25.08.): auch das Bohren fragt den Körper,
    nicht den Hüllquader.

    Die Plattenoberseite des L-Profils liegt bei ``z = 10``, unter der Mitte des
    Hüllquaders (``z = 20``); das Material liegt darunter. Eine Sackbohrung dort
    schneidet nach unten. An der Hüllquader-Hälfte gemessen ging sie nach oben in
    die Luft und trug 0,28 statt 169 mm³ ab — ohne einen Befund, weil die
    Überlappung mehr als nichts ist.
    """
    body = l_profile()
    result = drill(
        body, position=(-10.0, 0.0, 10.0), axis="z", diameter=6.0, depth=6.0, profile=profile
    )
    area = math.pi * (result.diameter / 2.0) ** 2
    assert body.volume - result.mesh.volume == pytest.approx(area * 6.0, rel=0.03)
    assert not any(finding.code == "boolean.without_effect" for finding in result.findings)
    assert result.mesh.is_watertight


def test_a_through_plug_fills_the_whole_bore(profile: Profile) -> None:
    """Ein durchgehender Stopfen ab der Mündung füllt die ganze Bohrung.

    Auf die Mündung zentriert reichte der Zylinder nur in eine Richtung und
    füllte die Hälfte, während die Bohrung offen blieb. Dieselbe
    ``* 2.0``-Länge wie beim Bohren deckt den ganzen Körper ab, und ``_shell``
    schneidet den Überstand weg.
    """
    body = cube()
    drilled = drill(
        body, position=(0.0, 0.0, 0.0), axis="z", diameter=6.0, compensate=False, profile=profile
    )
    assert drilled.mesh.volume < body.volume, "die Bohrung hat Material genommen"
    plugged = plug(drilled.mesh, position=(0.0, 0.0, 10.0), axis="z", diameter=6.0, profile=profile)
    assert plugged.mesh.volume == pytest.approx(body.volume, rel=0.01)
    assert plugged.mesh.is_watertight
    assert plugged.mesh.raw.body_count == 1, "ein gefüllter Körper, kein loser Zylinder"


def test_a_plug_on_a_step_does_not_grow_a_stud(profile: Profile) -> None:
    """Zwilling der Bohr-Richtung: der Stopfen füllt ins Material, nicht in die
    Luft.

    An der Plattenoberseite des L-Profils (``z = 10``) liegt das Material
    darunter. Ein Stopfen dort füllt nach unten — wo schon Material ist, ändert
    er nichts und sagt das (``boolean.without_effect``). An der Hüllquader-Hälfte
    gemessen wuchs er stattdessen nach oben und stand als Zapfen von 170 mm³ auf
    der Fläche, ohne einen Befund.
    """
    body = l_profile()
    plugged = plug(
        body, position=(-10.0, 0.0, 10.0), axis="z", diameter=6.0, depth=6.0, profile=profile
    )
    assert plugged.mesh.volume == pytest.approx(body.volume, abs=1.0), (
        "der Stopfen füllt ins Material und wächst nicht als Zapfen aus der Fläche"
    )
    assert any(finding.code == "boolean.without_effect" for finding in plugged.findings)


def test_the_boolean_overlap_is_the_one_from_the_rule_set() -> None:
    """§39: immer ein hundertstel Millimeter, nie zusammenfallende Flächen."""
    assert pytest.approx(0.01) == BOOLEAN_OVERLAP


# --- splitting ------------------------------------------------------------------


def test_splitting_yields_two_closed_halves() -> None:
    body = cube()
    first, second, findings = split_at_plane(body, SectionPlane.along("z", 0.0))

    assert first.is_watertight and second.is_watertight
    assert first.volume == pytest.approx(4000.0, rel=1e-6)
    assert second.volume == pytest.approx(4000.0, rel=1e-6)
    assert first.volume + second.volume == pytest.approx(body.volume, rel=1e-6)
    assert not findings


def test_splitting_a_plate_with_holes_stays_closed() -> None:
    body = plate()
    first, second, _findings = split_at_plane(body, SectionPlane.along("x", 0.0))

    assert first.is_watertight and second.is_watertight
    assert first.volume + second.volume == pytest.approx(body.volume, rel=1e-3)


# --- arranging ------------------------------------------------------------------


def test_arranging_puts_the_bodies_on_the_plate(profile: Profile) -> None:
    bodies = [cube(), apply(cube(), translation((200.0, 200.0, 50.0)))]
    result = arrange_on_bed(bodies, profile, spacing=5.0)

    for body in result.meshes:
        assert body.bounds.minimum[2] == pytest.approx(0.0), "everything sits on the bed"
    assert not check_collisions(result.meshes), "arranged bodies do not overlap"
    assert not result.findings, "everything fits on a 256 mm plate"
    assert result.plates == [0, 0], "one plate is enough for two cubes"


def test_arranging_keeps_the_spacing(profile: Profile) -> None:
    arranged = arrange_on_bed([cube(), cube()], profile, spacing=8.0).meshes

    gap = arranged[1].bounds.minimum[0] - arranged[0].bounds.maximum[0]
    assert gap == pytest.approx(8.0, abs=1e-6)


def test_what_sticks_out_of_the_build_volume_is_reported(profile: Profile) -> None:
    """§18.6: reported, never quietly scaled.

    Ein Würfel 400 mm neben dem Bett **passt** darauf — er liegt nur woanders.
    Die Kennung ist deshalb die der Lage und nicht die der Größe: An ihr hängen
    die anklickbaren Handlungen, und *Auf dem Bett anordnen* behebt genau das
    (``_fits_at_all``).
    """
    far_away = apply(cube(), translation((400.0, 0.0, 0.0)))
    findings = check_build_volume([far_away], profile)

    assert findings
    assert findings[0].code == "arrange.off_the_plate"


def test_a_misplaced_body_weighs_less_than_one_that_does_not_fit(profile: Profile) -> None:
    """Die Lage ist ein Hinweis, die Größe eine Warnung.

    Vorher stand beides als Warnung da, und damit warnte fast jede geladene
    Datei: ein heruntergeladenes Teil ist meist um den Ursprung zentriert und
    steckt zur Hälfte unter der Platte. Bei dreizehn Warnungen auf vierzehn
    Dateien liest sie niemand mehr — und die eine Datei, die wirklich zu groß
    ist, verschwindet zwischen den anderen.
    """
    daneben = apply(cube(), translation((400.0, 0.0, 0.0)))
    zu_gross = normalise(read_mesh((MESHES / "oversized.stl").read_bytes(), ".stl"), "mm").mesh

    zur_lage = check_build_volume([daneben], profile)
    zur_groesse = check_build_volume([zu_gross], profile)

    assert zur_lage[0].severity == "info", "ein Verschieben behebt es"
    assert zur_groesse[0].severity == "warning", "hier hilft kein Verschieben"


def test_a_body_below_the_bed_is_reported_without_being_asked(profile: Profile) -> None:
    """Die Lage zum Bauraum gehört zu jeder Auswertung, nicht auf Nachfrage.

    Ein geladenes Modell sitzt regelmäßig mittig auf ``z = 0`` und steckt damit
    zur Hälfte unter der Bauplatte. Die Schichtanalyse rechnet dann Schichten
    bei negativer Höhe, die Druckvorbereitung meldet „nichts einzuwenden" — und
    gesagt hat es bis dahin nur, wer „Kollisionen prüfen" von Hand aufrief.
    """
    from app.core.scene.evaluate import check_placement
    from app.core.types import Scene, SceneObject

    # Kennung und Schlüssel sind dasselbe — die Auswertung setzt ``id`` beim
    # Einhängen, und ein Test, der das anders macht, prüft eine Szene, die es
    # nicht gibt.
    sunk = SceneObject(id="obj_1", name="Halter", mesh=apply(cube(), translation((0.0, 0.0, -5.0))))
    scene = Scene(objects={"obj_1": sunk}, profile=profile)

    findings = check_placement(scene)

    assert findings, "ein Körper unter der Platte ist ein Befund"
    # Eigene Kennung, damit der Prüfbericht die Handlung dazu findet, die
    # wirklich hilft: *Auf das Bett setzen* statt *Modell teilen* (§2.7).
    assert findings[0].code == "arrange.below_bed"
    assert findings[0].object_id == "obj_1", "der Befund nennt den Körper, den er meint"
    assert findings[0].values["object"] == "Halter", "und zwar mit Namen, nicht mit Listenplatz"


def test_a_body_floating_above_the_bed_is_reported(profile: Profile) -> None:
    """Das Gegenstück zu ``below_bed``, und es fehlte (§17.1, §2.7).

    Ein Körper, der **unter** der Platte steckt, wurde seit je gemeldet; einer,
    der darüber schwebt, gar nicht — solange er in den Bauraum passte, sagte
    niemand ein Wort. Gemessen am 24.08.2026 an zwei Millimetern Luft und an
    hundertvierzig: beide Male kein Befund, kein Knopf. Robert hatte genau
    diesen Fall („einmal als es in der Luft war") und musste den Weg im Menü
    selbst suchen.

    Ein Hinweis und keine Warnung, aus demselben Grund wie beim Körper unter der
    Platte: Ein Klick behebt es.
    """
    from app.core.scene.evaluate import check_placement
    from app.core.types import Scene, SceneObject

    floating = SceneObject(
        id="obj_1", name="Halter", mesh=apply(cube(), translation((0.0, 0.0, 40.0)))
    )
    scene = Scene(objects={"obj_1": floating}, profile=profile)

    findings = check_placement(scene)

    assert findings, "ein Körper in der Luft ist ein Befund"
    assert findings[0].code == "arrange.above_bed"
    assert findings[0].severity == "info", "ein Klick behebt es"
    assert findings[0].object_id == "obj_1"


def test_a_body_resting_on_another_one_does_not_float(profile: Profile) -> None:
    """Und der Fall, in dem die Meldung falsch wäre: ein Deckel auf einer Dose.

    Jede Baugruppe aus einer 3MF hat Körper mit Luft unter sich, und dort ist
    sie gewollt. Gefragt wird nach dem Hüllquader: Wer in x und y mit einem
    Nachbarn überlappt, dessen Oberkante bis zu seiner Unterkante reicht, hat
    etwas unter sich. Die genaue Frage beantwortet die Inselerkennung der
    Schichtanalyse, und die kostet Sekunden (§31) — hier wäre sie falsch
    eingesetzt.
    """
    from app.core.scene.evaluate import check_placement
    from app.core.types import Scene, SceneObject

    base = SceneObject(id="obj_1", name="Dose", mesh=cube())
    lid = SceneObject(id="obj_2", name="Deckel", mesh=apply(cube(), translation((0.0, 0.0, 20.0))))
    # Der dritte hängt wirklich in der Luft — **ohne ihn wäre dieser Test auch
    # ohne die Prüfung grün** und würde nichts zusichern (`.claude/rules/
    # tests.md`, „Ein Verbotstest über eine leere Menge ist immer grün").
    # Gemessen: In der Gegenprobe war genau das der Fall.
    apart = SceneObject(
        id="obj_3", name="Klammer", mesh=apply(cube(), translation((60.0, 0.0, 40.0)))
    )
    scene = Scene(objects={"obj_1": base, "obj_2": lid, "obj_3": apart}, profile=profile)

    floating = {
        finding.object_id
        for finding in check_placement(scene)
        if finding.code == "arrange.above_bed"
    }

    assert floating == {"obj_3"}, (
        f"nur die Klammer schwebt; der Deckel liegt auf der Dose: {floating}"
    )


def test_floating_so_high_that_it_leaves_the_volume_says_so(profile: Profile) -> None:
    """Und wer oben hinausragt, bekommt denselben Satz statt des falschen.

    Vorher stand dort „Ein Objekt liegt außerhalb des Druckbetts" — in x und y
    lag es genau richtig, und angeboten wurde *Auf dem Bett anordnen*, das
    beides verschiebt, wo ein Absenken genügt.
    """
    from app.core.scene.evaluate import check_placement
    from app.core.types import Scene, SceneObject

    high = SceneObject(
        id="obj_1", name="Halter", mesh=apply(cube(), translation((0.0, 0.0, 300.0)))
    )
    scene = Scene(objects={"obj_1": high}, profile=profile)

    findings = check_placement(scene)

    assert findings
    assert findings[0].code == "arrange.above_bed", "und nicht der Satz vom Druckbettrand"


def test_a_body_on_the_bed_says_nothing(profile: Profile) -> None:
    """Und wer richtig steht, bekommt keine Meldung — sonst wäre sie wertlos."""
    from app.core.scene.evaluate import check_placement
    from app.core.types import Scene, SceneObject

    standing = SceneObject(
        id="obj_1", name="Halter", mesh=apply(cube(), translation((0.0, 0.0, 10.0)))
    )

    assert not check_placement(Scene(objects={"obj_1": standing}, profile=profile))


def test_a_finding_names_its_bodies_instead_of_their_places(profile: Profile) -> None:
    """§17.3: „Zwei Objekte überschneiden sich" — welche zwei?

    Die Prüfungen bekommen eine Liste von Netzen und kennen darum nur deren
    Reihenfolge. Bei zwei Körpern ist klar, was gemeint ist; bei zwanzig steht
    man vor dem Bericht und sucht. Wer die Kennungen hat, trägt sie nach.
    """
    from app.core.geom.prepare import named_for
    from app.core.types import SceneObject

    entries = [
        SceneObject(id="obj_1", name="Gehäuse", mesh=cube()),
        SceneObject(id="obj_2", name="Deckel", mesh=apply(cube(), translation((5.0, 0.0, 0.0)))),
    ]
    findings = named_for(check_collisions([entry.mesh for entry in entries]), entries)

    assert findings
    assert findings[0].values["a"] == "Gehäuse"
    assert findings[0].values["b"] == "Deckel"
    assert findings[0].object_id == "obj_1", "ein Klick muss irgendwohin führen"


def test_a_collision_says_how_deep(profile: Profile) -> None:
    """Ein Streifschuss ist etwas anderes als zwei Teile, die ineinanderstecken.

    Der Bericht sagte für beides dasselbe. Jetzt steht das gemeinsame Volumen
    dabei — dieselbe Zahl, an der man entscheidet, ob es ein Problem ist.
    """
    findings = check_collisions([cube(), apply(cube(), translation((5.0, 0.0, 0.0)))])

    assert findings and "shared" in findings[0].values


def test_sticking_out_says_how_far(profile: Profile) -> None:
    """Sonst steht dort eine Warnung, die ein Zehntel Millimeter und ein halbes
    Modell nicht unterscheidet.
    """
    far_away = apply(cube(), translation((400.0, 0.0, 0.0)))

    findings = check_build_volume([far_away], profile)

    assert findings
    assert "excess" in findings[0].values
    assert "mm" in str(findings[0].values["excess"])


def test_overlapping_bodies_are_reported() -> None:
    findings = check_collisions([cube(), apply(cube(), translation((5.0, 0.0, 0.0)))])

    assert findings and findings[0].code == "arrange.collision"
    assert not check_collisions([cube(), apply(cube(), translation((40.0, 0.0, 0.0)))])


def test_a_clearance_makes_the_check_stricter() -> None:
    bodies = [cube(), apply(cube(), translation((25.0, 0.0, 0.0)))]

    assert not check_collisions(bodies)
    assert check_collisions(bodies, clearance=10.0), "closer than the clearance counts"


def bracket() -> MeshData:
    """Ein Block mit einem Schlitz hindurch — die Form, über die ihr Quader
    lügt.
    """
    import trimesh

    outer = trimesh.creation.box(extents=(30.0, 20.0, 30.0))
    outer.apply_translation((0.0, 0.0, 15.0))
    slot = trimesh.creation.box(extents=(20.0, 22.0, 10.0))
    slot.apply_translation((5.0, 0.0, 15.0))
    return MeshData.of(trimesh.boolean.difference([outer, slot]))


def bar(height: float) -> MeshData:
    import trimesh

    body = trimesh.creation.box(extents=(14.0, 14.0, height))
    body.apply_translation((6.0, 0.0, 15.0))
    return MeshData.of(body)


def test_a_part_sitting_inside_a_slot_is_not_a_collision() -> None:
    """§18.6: die Quader überlappen, und die Körper berühren sich nie.

    Das ist der Fall, der Leute aufhören lässt, einen Bericht zu lesen — jede
    Baugruppe, die ineinandergreift, hat ihn, und sie alle Kollisionen zu nennen
    ist dasselbe, wie gar nichts zu melden.
    """
    assert not check_collisions([bracket(), bar(6.0)])


def test_a_part_that_really_sits_in_the_material_is_one() -> None:
    findings = check_collisions([bracket(), bar(14.0)])

    assert [entry.code for entry in findings] == ["arrange.collision"]
    assert findings[0].severity == "warning"
    assert findings[0].values["checked"] == "exact"


def test_too_close_counts_as_a_collision_when_a_clearance_is_asked_for() -> None:
    """Von der Oberfläche gemessen — ein Abstand auf der Platte bedeutet genau
    das.
    """
    assert not check_collisions([bracket(), bar(9.0)], clearance=0.2), "half a millimetre apart"
    assert check_collisions([bracket(), bar(9.8)], clearance=0.5), "a tenth apart, half asked for"


def test_an_open_body_falls_back_to_the_box_and_says_so() -> None:
    """Ein offener Körper hat kein Innen; eines zu raten machte aus einer
    Warnung eine Lüge.
    """
    import trimesh

    broken = trimesh.creation.box(extents=(10.0, 10.0, 10.0))
    broken.update_faces([True] * (len(broken.faces) - 2) + [False, False])

    findings = check_collisions([MeshData.of(broken), cube()])

    assert findings and findings[0].values["checked"] == "box"


# --- as operations --------------------------------------------------------------


def loaded(document: Document, name: str = "cube_clean.stl", count: int = 1):
    project = new_project("centauri-carbon-2", "petg")
    project.document = document
    drafts = []
    for index in range(1, count + 1):
        source_id = f"src_{index}"
        document.sources[source_id] = Source(
            id=source_id, kind="import", path=f"sources/{index}_{name}", sha256=""
        )
        project.sources[source_id] = (MESHES / name).read_bytes()
        drafts.append(OperationDraft(op="load", params={"source": source_id, "unit": "mm"}))
    history = History(document)
    history.apply(_("Laden"), drafts)
    return project, history


def test_drilling_runs_as_an_operation(document: Document, profile: Profile) -> None:
    project, history = loaded(document)
    history.apply(
        _("Bohren"),
        [OperationDraft(op="drill_hole", inputs=("obj_1",), params={"diameter": 6.0, "axis": "z"})],
    )

    result = evaluate(document, profile, sources=ProjectSources(project))

    assert result.complete
    assert result.scene.objects["obj_1"].mesh.volume < 8000.0
    assert "bore.compensated" in {finding.code for finding in result.scene.report.findings}


def test_splitting_runs_as_an_operation(document: Document, profile: Profile) -> None:
    project, history = loaded(document)
    history.apply(
        _("Teilen"),
        [OperationDraft(op="split_pinned", inputs=("obj_1",), params={"axis": "z", "pins": 0})],
    )

    result = evaluate(document, profile, sources=ProjectSources(project))

    assert result.complete
    assert list(result.scene.objects) == ["obj_2", "obj_3"]
    for entry in result.scene.objects.values():
        assert entry.mesh.is_watertight
        assert entry.mesh.volume == pytest.approx(4000.0, rel=1e-6)


def test_a_plane_beside_the_body_stops_instead_of_making_a_ghost(
    document: Document, profile: Profile
) -> None:
    """Der Dialog belegt ``position = 0`` vor, und ein geladener Körper steht
    oft genau dort auf der Platte.

    Bestätigen ergab dann „Teil A" mit null Dreiecken und 0 mm³ — ein Eintrag
    im Objektbaum, den man ansehen, umbenennen und exportieren kann und der
    nichts ist. Der Zwilling ``split_pinned`` hielt an derselben Stelle längst
    an; hier fehlte der Satz.
    """
    project, history = loaded(document)
    history.apply(
        _("Teilen"),
        [
            OperationDraft(
                op="split_pinned",
                inputs=("obj_1",),
                params={"axis": "z", "position": 60.0, "pins": 0},
            )
        ],
    )

    result = evaluate(document, profile, sources=ProjectSources(project))

    assert not result.complete, "eine Ebene, die nichts trifft, ist ein Fehler und kein Ergebnis"
    findings = [finding for finding in result.scene.report.findings if finding.severity == "error"]
    assert findings
    assert "teilt das Objekt nicht" in str(findings[0].message)


def test_arranging_runs_over_every_object(document: Document, profile: Profile) -> None:
    """Eine Operation mit variabler Objektzahl: so viele heraus wie hinein."""
    project, history = loaded(document, count=3)
    history.apply(
        _("Anordnen"),
        [OperationDraft(op="arrange_bed", inputs=("obj_1", "obj_2", "obj_3"))],
    )

    result = evaluate(document, profile, sources=ProjectSources(project))

    assert result.complete
    assert list(result.scene.objects) == ["obj_1", "obj_2", "obj_3"], "same objects, moved"
    for entry in result.scene.objects.values():
        assert entry.mesh.bounds.minimum[2] == pytest.approx(0.0)


def test_the_collision_check_only_reports(document: Document, profile: Profile) -> None:
    project, history = loaded(document, count=2)
    history.apply(
        _("Prüfen"),
        [OperationDraft(op="check_collisions", inputs=("obj_1", "obj_2"))],
    )

    result = evaluate(document, profile, sources=ProjectSources(project))

    assert result.complete
    assert "arrange.collision" in {finding.code for finding in result.scene.report.findings}
    assert result.scene.objects["obj_1"].mesh.volume == pytest.approx(8000.0)


# --- die Abstandsanfrage --------------------------------------------------------


def test_the_surface_query_answers_what_it_is_asked() -> None:
    """Erst das Normale: der nächste Ort auf der Oberfläche, sein Abstand,
    sein Dreieck — und zwar in Typen, mit denen sich indizieren lässt.
    """
    body = read_mesh((MESHES / "cube_clean.stl").read_bytes(), ".stl").raw
    points = np.array([[0.0, 0.0, 20.0], [0.0, 0.0, 0.0]], dtype=float)

    closest, distance, triangle = on_surface(body, points)

    assert closest.shape == (2, 3)
    assert distance[0] == pytest.approx(10.0), "20 mm Kante, Mitte auf Null, Deckel bei z=10"
    assert triangle.dtype == np.int64, "damit lässt sich ein Slot-Feld indizieren"


def test_the_surface_query_needs_no_retry_because_it_has_no_index() -> None:
    """Die zwei Wiederhol-Tests, die hier standen, prüften eine Krücke.

    ``on_surface`` lief bis zum 24.08.2026 über den ``rtree``-Index von
    ``trimesh`` und stolperte in etwa jedem zwanzigsten Lauf; ein
    Wiederholversuch an einer Kopie fing das ab, ein zweiter Fehlgriff flog.
    Beides gibt es nicht mehr, weil es die Ursache nicht mehr gibt — die
    Suche fragt einen eigenen Baum (:func:`app.core.geom.mesh.on_surface`),
    und einen Wiederholpfad, den niemand mehr erreichen kann, prüft man
    nicht, man entfernt ihn.

    Was bleibt, ist die Zusage, an der die alten Tests wirklich hingen: Die
    Antwort stimmt, und ihr Dreiecksindex taugt zum Indizieren eines
    Slot-Felds. Mehrere Anfragen hintereinander an denselben Körper — der
    Fall, in dem der alte Index gealtert und danebengegriffen hat — geben
    identische Ergebnisse, denn es gibt keinen gealterten Zustand mehr:
    der Baum entsteht je Aufruf.
    """
    body = read_mesh((MESHES / "cube_clean.stl").read_bytes(), ".stl").raw
    points = np.array([[0.0, 0.0, 20.0], [25.0, 0.0, 0.0]], dtype=float)

    first = on_surface(body, points)
    second = on_surface(body, points)
    assert first[1][0] == pytest.approx(10.0), "20 mm Kante, Mitte auf Null, Deckel bei z=10"
    assert first[1][1] == pytest.approx(15.0)
    assert np.array_equal(first[1], second[1]), "kein Zustand, der altern könnte"
    assert np.array_equal(first[2], second[2])
    assert first[2].dtype == np.int64


def test_arranging_by_material_keeps_the_filaments_apart(
    document: Document, profile: Profile
) -> None:
    """Zwei Filamente auf einer Platte kosten je gemeinsamer Schicht einen
    Wechsel samt Spülgang.

    `plates_by_material` rechnete den Vorschlag seit jeher und war von nirgends
    aus erreichbar. Jetzt ist er ein Umschalter an derselben Operation — es ist
    dieselbe Handlung mit einer anderen Vorgabe, wer neben wem liegt.
    """
    project, history = loaded(document, count=3)
    history.apply(
        _("Material"),
        [
            OperationDraft(
                op="assign_slot", inputs=("obj_2",), outputs=("obj_2",), params={"slot": 1}
            )
        ],
    )
    history.apply(
        _("Anordnen"),
        [
            OperationDraft(
                op="arrange_bed",
                inputs=("obj_1", "obj_2", "obj_3"),
                params={"by_material": True, "plates": 4},
            )
        ],
    )

    result = evaluate(document, profile, sources=ProjectSources(project))

    assert result.complete
    platten = {name: entry.plate for name, entry in result.scene.objects.items()}
    assert platten["obj_1"] == platten["obj_3"], "gleiches Filament, gleiche Platte"
    assert platten["obj_2"] != platten["obj_1"], "anderes Filament, andere Platte"


def test_arranging_by_material_respects_the_plate_limit(
    document: Document, profile: Profile
) -> None:
    """Die Grenze gilt der Szene, nicht je Gruppe.

    Sonst hätte ein Projekt mit drei Filamenten unversehens dreimal so viele
    Platten, wie jemand eingestellt hat.
    """
    project, history = loaded(document, count=3)
    for name, slot in (("obj_1", 0), ("obj_2", 1), ("obj_3", 2)):
        history.apply(
            _("Material"),
            [
                OperationDraft(
                    op="assign_slot", inputs=(name,), outputs=(name,), params={"slot": slot}
                )
            ],
        )
    history.apply(
        _("Anordnen"),
        [
            OperationDraft(
                op="arrange_bed",
                inputs=("obj_1", "obj_2", "obj_3"),
                params={"by_material": True, "plates": 2},
            )
        ],
    )

    result = evaluate(document, profile, sources=ProjectSources(project))

    assert result.complete
    benutzt = {entry.plate for entry in result.scene.objects.values()}
    assert max(benutzt) <= 1, f"höchstens zwei Platten, benutzt wurden {sorted(benutzt)}"


def test_the_preparation_operations_are_registered_completely() -> None:
    assert REGISTRY.get("drill_hole").applies_to == ("face",)
    assert REGISTRY.get("drill_hole").requires_seed, "it uses the boolean fallback chain"
    assert REGISTRY.get("split_pinned").produces == 2
    assert REGISTRY.get("arrange_bed").produces == VARIABLE
    assert REGISTRY.get("check_collisions").produces == VARIABLE


def test_arranging_names_the_bodies_it_finds_touching(
    document: Document, profile: Profile, monkeypatch: pytest.MonkeyPatch
) -> None:
    """„Zwei Objekte überschneiden sich — 0 · 1" stand im Bericht.

    ``check_collisions`` kennt nur die Reihenfolge seiner Liste und schreibt sie
    in den Befund; ``named_for`` trägt die Namen nach. Die Zwillings-Op
    ``check_collisions`` tat das seit je, ``arrange_bed`` nicht — dort landeten
    die Indizes ungefiltert im Bericht.

    Und sie waren nicht einmal die der Szene: geprüft wird **je Platte**, die
    Liste ist also vorher gefiltert. Die „1" der zweiten Platte ist nicht das
    zweite Objekt. Deshalb werden die Einträge mitgefiltert und zusammen
    weitergegeben.

    Geprüft mit einem gestellten Befund: Anordnen legt die Körper gerade
    *auseinander*, eine echte Kollision danach wäre der Ausnahmefall. Was hier
    zu prüfen ist, ist die Verdrahtung — dass der Weg durch ``named_for``
    führt.
    """
    from app.core.types import Finding

    def touching(meshes: list[object], clearance: float = 0.0) -> list[Finding]:
        assert len(meshes) == 2, "beide Körper liegen auf derselben Platte"
        return [
            Finding(
                code="arrange.collision",
                severity="warning",
                message=_("Zwei Objekte überschneiden sich."),
                values={"a": 0, "b": 1},
            )
        ]

    monkeypatch.setattr("app.core.geom.prepare_ops.check_collisions", touching)

    project, history = loaded(document, count=2)
    history.apply(_("Anordnen"), [OperationDraft(op="arrange_bed", inputs=("obj_1", "obj_2"))])

    result = evaluate(document, profile, sources=ProjectSources(project))

    reported = [
        finding for finding in result.scene.report.findings if finding.code == "arrange.collision"
    ]
    assert reported, "der gestellte Befund muss durchkommen"
    values = reported[0].values
    assert not isinstance(values["a"], int), f"{values['a']!r} ist ein Listenplatz, kein Name"
    assert not isinstance(values["b"], int)
    assert reported[0].object_id, "ein Klick auf die Zeile muss irgendwohin führen"
