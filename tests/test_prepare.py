"""Bohren, Teilen, Anordnen und Kollisionen (Bauplan §25, §39, §18.6)."""

from __future__ import annotations

import math
from pathlib import Path

import numpy as np
import pytest
import trimesh

from app.core.geom.boolean import boolean
from app.core.geom.mesh import MeshData, as_mesh_data, on_surface, read_mesh
from app.core.geom.prepare import (
    BOOLEAN_OVERLAP,
    arrange_on_bed,
    bore_diameter,
    check_build_volume,
    check_collisions,
    countersink,
    drill,
    into_the_body,
    plug,
    resize_bore,
    split_at_plane,
)
from app.core.geom.section import SectionPlane
from app.core.geom.transform import apply, rotation, translation
from app.core.ingest.loader import normalise
from app.core.knowledge import profiles
from app.core.perceive.features import detect
from app.core.registry import REGISTRY, VARIABLE
from app.core.scene import History, OperationDraft, evaluate
from app.core.scene.project import ProjectSources, new_project
from app.core.types import Document, Profile, SceneObject, Source
from app.core.units import EPS_GEOM
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


def plate_with_stud(*, below: bool = False) -> MeshData:
    """Platte 40 x 40 x 10 (z 0..10) und ein freistehender Dom Ø 8 x 6 hoch
    daneben, Mitte bei ``x = 8`` — über der Platte (z 10..16) oder unter ihr
    (z -6..0).

    Der Körper, an dem die Senkung ihre Mündung verlor. Zwischen einer Bohrung
    Ø 5 auf der Achse und dem Dom liegen 1,5 mm Wand, die Bohrung rührt ihn also
    nicht an; mit seiner Flanke steht er trotzdem im Radius einer Senkung Ø 10 —
    und sechs Millimeter höher als die Fläche, in die gesenkt wird.
    """
    plate = trimesh.creation.box(extents=(40.0, 40.0, 10.0))
    plate.apply_translation((0.0, 0.0, 5.0))
    stud = trimesh.creation.cylinder(radius=4.0, height=6.0, sections=48)
    stud.apply_translation((8.0, 0.0, -3.0 if below else 13.0))
    return MeshData.of(trimesh.boolean.union([plate, stud]))


def section_area(mesh: MeshData, height: float) -> float:
    """Die Fläche des waagerechten Schnitts auf dieser Höhe.

    Die Frage „was hat die Senkung angefasst" lässt sich am Volumen allein nicht
    stellen: Ein Kubikmillimeter aus dem Nachbarn wiegt so viel wie einer aus der
    Bohrung. Der Querschnitt sagt **wo**.
    """
    from app.core.slice.analysis import cross_section

    section = cross_section(mesh, height)
    return 0.0 if section is None or section.is_empty else float(section.area)


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


def test_an_imported_bore_can_be_made_larger_and_smaller(profile: Profile) -> None:
    """Die Korpusplatte ist der Kundenweg: STL hinein, Bohrung anklicken,
    neues Maß eintragen.

    Beide Richtungen gehören zur Zusage. Nur größer wäre bloß ein zweites
    *Bohrung setzen*; nur kleiner zwänge den Kunden weiter zu Stopfen plus
    neuer Bohrung und damit zu zwei Koordinatensätzen.
    """
    body = plate()
    feature = detect(body)["hole_1"]
    common = {
        "position": feature.params["centre"],
        "direction": feature.params["axis"],
        "previous_diameter": feature.params["diameter"],
        "depth": feature.params["depth"],
        "through": feature.params["through"],
        "profile": profile,
        "compensate": False,
    }

    larger = resize_bore(body, diameter=7.0, seed=11, **common)
    smaller = resize_bore(body, diameter=3.0, seed=11, **common)

    assert larger.mesh.is_watertight and smaller.mesh.is_watertight
    assert larger.mesh.volume < body.volume < smaller.mesh.volume
    assert smaller.mesh.bounds.minimum == pytest.approx(body.bounds.minimum, abs=EPS_GEOM)
    assert smaller.mesh.bounds.maximum == pytest.approx(body.bounds.maximum, abs=EPS_GEOM)
    assert len([entry for entry in detect(larger.mesh).values() if entry.kind == "hole"]) == 4
    assert len([entry for entry in detect(smaller.mesh).values() if entry.kind == "hole"]) == 4
    enlarged = min(
        (entry for entry in detect(larger.mesh).values() if entry.kind == "hole"),
        key=lambda entry: sum(
            (float(a) - float(b)) ** 2
            for a, b in zip(entry.params["centre"], feature.params["centre"], strict=True)
        ),
    )
    reduced = min(
        (entry for entry in detect(smaller.mesh).values() if entry.kind == "hole"),
        key=lambda entry: sum(
            (float(a) - float(b)) ** 2
            for a, b in zip(entry.params["centre"], feature.params["centre"], strict=True)
        ),
    )
    assert enlarged.params["diameter"] == pytest.approx(7.0, abs=0.03)
    assert reduced.params["diameter"] == pytest.approx(3.0, abs=0.03)


def test_a_slanted_imported_bore_keeps_its_axis(profile: Profile) -> None:
    """Erkannte Bohrungen sind nicht auf die drei Weltachsen beschränkt.

    Ein STL aus dem Netz liegt oft gedreht. Die Bedienung darf daraus keine
    versteckte CAD-Aufgabe machen, bei der der Kunde erst eine Achse errät.
    """
    body = apply(apply(plate(), rotation("y", 31.0)), rotation("x", 19.0))
    feature = detect(body)["hole_1"]

    result = resize_bore(
        body,
        position=feature.params["centre"],
        direction=feature.params["axis"],
        previous_diameter=feature.params["diameter"],
        diameter=7.0,
        depth=feature.params["depth"],
        through=feature.params["through"],
        profile=profile,
        compensate=False,
        seed=13,
    )

    nearest = min(
        (entry for entry in detect(result.mesh).values() if entry.kind == "hole"),
        key=lambda entry: sum(
            (float(a) - float(b)) ** 2
            for a, b in zip(entry.params["centre"], feature.params["centre"], strict=True)
        ),
    )
    assert nearest.params["diameter"] == pytest.approx(7.0, abs=0.03)
    assert abs(
        sum(
            float(a) * float(b)
            for a, b in zip(nearest.params["axis"], feature.params["axis"], strict=True)
        )
    ) == pytest.approx(1.0, abs=0.01)


def test_an_unchanged_bore_does_not_recalculate_the_mesh(profile: Profile) -> None:
    """Dialog öffnen und unverändert bestätigen erzeugt keine neue Rundung."""
    body = plate()
    feature = detect(body)["hole_1"]

    result = resize_bore(
        body,
        position=feature.params["centre"],
        direction=feature.params["axis"],
        previous_diameter=feature.params["diameter"],
        diameter=feature.params["diameter"],
        depth=feature.params["depth"],
        through=feature.params["through"],
        profile=profile,
        compensate=False,
    )

    assert result.mesh is body
    assert result.solver is None
    assert {entry.code for entry in result.findings} == {"bore.resize_unchanged"}


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


def test_a_countersink_keeps_to_its_own_bore_when_something_taller_stands_beside_it(
    profile: Profile,
) -> None:
    """Der Dom neben der Bohrung zog die Senkung zu sich (§25).

    ``_at_the_mouth`` nahm den **weitesten** Eckpunkt im Senkungsradius, und das
    ist die Domoberseite, sobald neben der Bohrung etwas höher steht als die
    Fläche, in die gesenkt wird. Gemessen an dieser Platte: Der Klick auf die
    Mündung (0, 0, 10) landete bei (0, 0, 16), 1,0 mm³ wurden **aus dem Dom**
    gebissen, die Bohrung blieb ohne Fase — und weil abgetragen ja etwas wurde,
    sagte kein Befund ein Wort dazu.

    Gefragt wird am Querschnitt und nicht am Volumen: Ein Kubikmillimeter aus
    dem Nachbarn wiegt so viel wie einer aus der Bohrung, nur der Ort
    unterscheidet die beiden Fälle.
    """
    body = drill(
        plate_with_stud(),
        position=(0.0, 0.0, 10.0),
        axis="z",
        diameter=5.0,
        compensate=False,
        profile=profile,
    ).mesh

    result = countersink(body, position=(0.0, 0.0, 10.0), axis="z", diameter=10.0, profile=profile)

    assert section_area(result.mesh, 9.5) < section_area(body, 9.5) - 1.0, (
        "die Fase weitet die Bohrung unter ihrer Mündung"
    )
    assert section_area(result.mesh, 15.5) == pytest.approx(section_area(body, 15.5), abs=0.01), (
        "und der Dom daneben bleibt unversehrt"
    )


def test_a_countersink_from_below_keeps_to_its_own_bore_as_well(profile: Profile) -> None:
    """Dieselbe Frage mit umgekehrtem Vorzeichen (``outward < 0``).

    Der Zapfen hängt unter der Platte, gesenkt wird an der Unterseite. Auch hier
    war der weiteste Punkt der falsche: Der Klick auf (0, 0, 0) landete bei
    z = -6, der Zapfenunterseite, und derselbe eine Kubikmillimeter ging am
    falschen Ort verloren. Beide Richtungen einzeln, weil die Suche das
    Vorzeichen selbst führt und ein Tausch von ``min`` und ``max`` genau hier
    unbemerkt bliebe.
    """
    body = drill(
        plate_with_stud(below=True),
        position=(0.0, 0.0, 0.0),
        axis="z",
        diameter=5.0,
        compensate=False,
        profile=profile,
    ).mesh

    result = countersink(body, position=(0.0, 0.0, 0.0), axis="z", diameter=10.0, profile=profile)

    assert section_area(result.mesh, 0.5) < section_area(body, 0.5) - 1.0, (
        "die Fase weitet die Bohrung über ihrer Mündung"
    )
    assert section_area(result.mesh, -5.5) == pytest.approx(section_area(body, -5.5), abs=0.01), (
        "und der Zapfen darunter bleibt unversehrt"
    )


def test_a_countersink_without_a_neighbour_still_finds_the_far_mouth(profile: Profile) -> None:
    """Die Gegenprobe zum Dom: ohne Nachbarn ist die nächste Grenze die Mündung.

    Der Würfel steht von -10 bis 10, die Bohrung geht durch, geklickt wird auf
    die **Mitte** — so meldet ein erkanntes Loch seine Lage (§21.3). Gesucht
    werden muss dann über zehn Millimeter hinweg bis ``z = 10``; eine Suche, die
    zu früh anhält, fiele hier auf. Vor und nach dem Wechsel von der weitesten
    auf die nächste Grenze dieselbe Zahl: 15,07 mm³.
    """
    body = drill(
        cube(), position=(0.0, 0.0, 0.0), axis="z", diameter=6.0, compensate=False, profile=profile
    ).mesh

    found = countersink(body, position=(0.0, 0.0, 0.0), axis="z", diameter=8.4, profile=profile)
    placed = countersink(
        body, position=(0.0, 0.0, 10.0), axis="z", diameter=8.4, anchor="centre", profile=profile
    )

    assert body.volume - found.mesh.volume == pytest.approx(15.07, abs=0.05)
    assert found.mesh.volume == pytest.approx(placed.mesh.volume, abs=0.01), (
        "die gesuchte Mündung ist die, die man von Hand einträgt"
    )


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


def section_rings(mesh: MeshData, height: float) -> int:
    """Wie viele Löcher der waagerechte Schnitt auf dieser Höhe einschließt.

    Die Frage „ist die Bohrung wirklich zu" lässt sich am Volumen allein nicht
    stellen: Ein Ringspalt von anderthalb Prozent des Bohrungsquerschnitts
    verschwindet in jeder Toleranz, die man auf 8000 mm³ ansetzt. Die Zahl der
    Innenränder sagt **ob** noch ein Loch da ist, und zwar unabhängig davon,
    wie schmal es ist.
    """
    from app.core.slice.analysis import cross_section

    section = cross_section(mesh, height)
    if section is None or section.is_empty:
        return 0
    return sum(len(part.interiors) for part in getattr(section, "geoms", [section]))


def test_a_plug_closes_a_bore_that_was_widened_for_the_material(profile: Profile) -> None:
    """Wer 6 mm bohrt und 6 mm stopft, behält kein Loch.

    ``drill`` weitet per Vorgabe um die Materialtoleranz aus dem Profil (§39,
    Regel 7) — beim PETG-Profil sind das 0,2 mm im Durchmesser. Der Stopfen
    rechnete dagegen mit dem Nennmaß plus der Booleschen Überlappung: gebohrt
    wurden 6,20 mm, gefüllt 6,02 mm. Zurück blieb ein Ringspalt von 1,72 mm²
    über die ganze Bohrungslänge, also 34,45 mm³ — wasserdicht, einteilig, ein
    Innenrand in jedem Querschnitt und kein einziger Befund.

    Der Test daneben (:func:`test_a_through_plug_fills_the_whole_bore`) umgeht
    die Frage mit ``compensate=False`` und konnte sie deshalb nicht stellen.
    """
    body = cube()
    drilled = drill(body, position=(0.0, 0.0, 0.0), axis="z", diameter=6.0, profile=profile)
    assert section_rings(drilled.mesh, 0.0) == 1, "die Bohrung ist da"

    plugged = plug(drilled.mesh, position=(0.0, 0.0, 10.0), axis="z", diameter=6.0, profile=profile)

    assert section_rings(plugged.mesh, 0.0) == 0, "kein Ringspalt mehr im Querschnitt"
    assert section_area(plugged.mesh, 0.0) == pytest.approx(section_area(body, 0.0), abs=0.05)
    assert plugged.mesh.volume == pytest.approx(body.volume, abs=0.5)
    assert plugged.mesh.is_watertight
    assert plugged.mesh.raw.body_count == 1


def test_a_plug_can_be_told_to_ignore_the_material_tolerance(profile: Profile) -> None:
    """``compensate=False`` heißt beim Stopfen dasselbe wie beim Bohren.

    Wer nominal bohrt, stopft nominal — sonst wüchse der Stopfen um die
    Toleranz in ein Loch hinein, das sie nie bekommen hat. Die zwei Schalter
    gehören zusammengedacht, und darum trägt der Stopfen denselben.
    """
    body = cube()
    drilled = drill(
        body, position=(0.0, 0.0, 0.0), axis="z", diameter=6.0, compensate=False, profile=profile
    )
    plugged = plug(
        drilled.mesh,
        position=(0.0, 0.0, 10.0),
        axis="z",
        diameter=6.0,
        compensate=False,
        profile=profile,
    )

    assert section_rings(plugged.mesh, 0.0) == 0
    assert plugged.mesh.volume == pytest.approx(body.volume, abs=0.5)


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


def test_into_the_body_reads_the_local_column_not_the_whole_box() -> None:
    """Zwilling des Senkungsfixes eine Ebene weiter: bei zwei offenen Seiten
    entschied ``into_the_body`` an der Mitte des ganzen Hüllquaders.

    Ein hoher Nachbar — ein Dom, ein Steg — hebt diese Mitte über die
    angeklickte Fläche, und die feste Halbierung zeigte dann nach oben in die
    Luft statt nach unten ins Material. Gemessen wird jetzt die Materialsäule an
    genau dieser Stelle: An der Plattenoberseite liegt das Material unten, egal
    wie hoch der Dom daneben steht.
    """
    body = plate_with_stud()  # Platte z 0..10, Dom darüber -> Hüllquader-Mitte über 5
    assert body.bounds.maximum[2] > 10.0, "der Dom hebt den Hüllquader über die Platte"

    assert into_the_body(body, "z", (0.0, 0.0, 5.0)) == -1.0, "ins Material (nach unten)"


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


def test_a_volume_finding_names_the_body_instead_of_its_index(profile: Profile) -> None:
    """Mit Kennung kein Listenplatz im Kundentext (Roberts Foto, 30.08.2026).

    ``values["object"] = 0`` war doppelt falsch: Der Index ist kein Kundentext,
    und sein bloßes Vorhandensein verhinderte die Namensauflösung der
    Berichtszeile — sie setzt den Objektnamen nur ein, wenn ``values`` kein
    ``object`` trägt. Die Exportprüfung übergab Kennungen und zeigte trotzdem
    „— 0 · 10,00 mm".
    """
    sunk = apply(cube(), translation((0.0, 0.0, -5.0)))

    with_ids = check_build_volume([sunk], profile, object_ids=["obj_7"])
    assert with_ids[0].object_id == "obj_7"
    assert "object" not in with_ids[0].values, "die Kennung trägt, der Index bliebe im Weg"

    without_ids = check_build_volume([sunk], profile)
    assert without_ids[0].object_id is None
    assert without_ids[0].values["object"] == 0, "ohne Kennung bleibt der Index als Notnagel"


def test_arranging_carries_the_object_ids_into_its_findings(profile: Profile) -> None:
    """Auch die Anordnung nennt den Körper beim Namen, den sie meldet.

    ``arrange_on_bed`` prüfte den Bauraum ohne Kennungen — ein zu großes Teil
    stand als Listenplatz im Bericht, obwohl der Aufrufer die Szene hat.
    """
    zu_gross = normalise(read_mesh((MESHES / "oversized.stl").read_bytes(), ".stl"), "mm").mesh
    arranged = arrange_on_bed([as_mesh_data(zu_gross)], profile, object_ids=["obj_9"])

    reported = [entry for entry in arranged.findings if entry.code.startswith("arrange.")]
    assert reported, "ein Teil, das nicht passt, ist ein Befund"
    assert reported[0].object_id == "obj_9"
    assert "object" not in reported[0].values


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
    from app.core.types import Scene

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
    # Kein ``values["object"]`` mehr: Die Kennung trägt, und der Bericht löst
    # sie zum Namen auf — ein Wert daneben verhinderte genau das (Roberts
    # Foto, 30.08.2026) und machte den Befund anders als den der
    # Exportprüfung, sodass derselbe Sachverhalt zweimal in der Liste stand.
    assert "object" not in findings[0].values, "die Zeile löst die Kennung selbst auf"


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
    from app.core.types import Scene

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
    from app.core.types import Scene

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
    from app.core.types import Scene

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
    from app.core.types import Scene

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


def test_resizing_an_imported_bore_is_one_complete_operation(
    document: Document, profile: Profile
) -> None:
    """STL laden, erkanntes Loch benennen, einen Durchmesser ändern.

    Der Test geht durch Stapel, Neuerkennung und Zuordnung: Eine grüne
    Geometriefunktion allein bewiese nicht, dass Kontextmenü und Agent die
    Merkmal-ID danach weiterverwenden können.
    """
    project, history = loaded(document, "plate_holes.stl")
    imported = evaluate(document, profile, sources=ProjectSources(project))
    before = imported.scene.objects["obj_1"]
    chosen = before.features["hole_1"]

    history.apply(
        _("Bohrung ändern"),
        [
            OperationDraft(
                op="resize_hole",
                inputs=("obj_1",),
                outputs=("obj_1",),
                params={"at_feature": chosen.id, "diameter": 7.0},
            )
        ],
    )
    changed = evaluate(document, profile, sources=ProjectSources(project))

    assert changed.complete
    after = changed.scene.objects["obj_1"]
    assert after.mesh.is_watertight
    assert after.mesh.volume < before.mesh.volume
    assert len([entry for entry in after.features.values() if entry.kind == "hole"]) == 4
    assert after.features["hole_1"].params["diameter"] == pytest.approx(7.0, abs=0.03)
    assert not [entry for entry in changed.scene.report.findings if entry.severity == "error"]


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


def test_splitting_says_that_the_halves_still_lie_together(
    document: Document, profile: Profile
) -> None:
    """Zwei Hälften an ihrem Platz sehen aus wie ein Körper — und sagten es nicht.

    Das Teilen setzt beide Stücke dorthin, wo sie im ganzen Teil lagen; das
    ist richtig, sonst passten sie nicht mehr zusammen. Im Bild ist das
    Ergebnis damit von der Ausgangslage nicht zu unterscheiden: ein Schritt
    im Verlauf, zwei Zeilen im Baum, davor ein Körper wie vorher — und
    keinerlei Auskunft (Fund 27, 27.08.2026).

    Der Nachbarbefund ``arrange.bodies_in_one_place`` greift hier nicht: Er
    sucht Körper, die sich in Hüllquader **und** Volumen gleichen, und zwei
    komplementäre Hälften tun das nicht. Die Auskunft kommt deshalb aus der
    Operation selbst.
    """
    project, history = loaded(document)
    history.apply(
        _("Teilen"),
        [OperationDraft(op="split_pinned", inputs=("obj_1",), params={"axis": "z", "pins": 0})],
    )

    result = evaluate(document, profile, sources=ProjectSources(project))

    codes = [finding.code for finding in result.scene.report.findings]
    assert "prepare.halves_in_place" in codes, f"das Teilen sagt es: {codes}"
    hinweis = next(
        entry for entry in result.scene.report.findings if entry.code == "prepare.halves_in_place"
    )
    assert hinweis.severity == "info", "nichts ist schiefgegangen"


def test_arranging_the_halves_removes_the_old_request(document: Document, profile: Profile) -> None:
    """Ein späterer Schritt darf den früheren Befund nicht falsch lassen.

    Das Beispiel „Aushöhlen und teilen“ ordnet seine Hälften am Ende bereits
    nebeneinander an. Der Bericht verlangte trotzdem weiter genau diese
    Handlung, weil der Hinweis aus dem Teilungsschritt bis zum Endstand
    mitreiste. Ein Beispiel ist Dokumentation; ein überholter Vorschlag darin
    ist ein Widerspruch, kein harmloser Hinweis.
    """
    project, history = loaded(document)
    history.apply(
        _("Teilen"),
        [OperationDraft(op="split_pinned", inputs=("obj_1",), params={"axis": "z", "pins": 0})],
    )
    history.apply(
        _("Anordnen"),
        [OperationDraft(op="arrange_bed", inputs=("obj_2", "obj_3"))],
    )

    result = evaluate(document, profile, sources=ProjectSources(project))

    codes = {finding.code for finding in result.scene.report.findings}
    assert "prepare.halves_in_place" not in codes, codes


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
    resize = REGISTRY.get("resize_hole")
    assert resize.applies_to == ("hole",)
    assert resize.requires_seed, "der Mesh-Weg benutzt dieselbe Boolesche Rückfallkette"
    diameter = next(entry for entry in resize.params.spec() if entry.name == "diameter")
    feature = next(entry for entry in resize.params.spec() if entry.name == "at_feature")
    assert diameter.placement == "front", "das Zielmaß ist die häufigste Änderung"
    assert feature.kind == "feature" and feature.required
    # Nicht mehr „advanced": Ein Pflichtfeld hinter der Klappe war die stille
    # Wahl der ersten Bohrung (Regel 21) — die registerweite Fassung hält
    # test_operation_ui::test_no_required_parameter_hides_behind_the_advanced_box.
    assert feature.placement == "front"
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


def test_bodies_stacked_on_each_other_are_reported(profile: Profile) -> None:
    """Zwei Körper an derselben Stelle sind im Bild einer.

    Gemeldet wurde es als „das Objekt ist nicht zweimal da": Wer dupliziert,
    bekommt die Kopie am Ort des Originals, und wer zweimal *Quader anlegen*
    wählt, bekommt zwei Quader übereinander. Beides ist richtig — die
    Stückzahl gehört in den Stapel, das Verteilen ans Anordnen (§25) —, nur
    sagte es niemand, und der Klick sah aus wie verschluckt.
    """
    from app.core.scene.evaluate import check_bodies_in_one_place
    from app.core.types import Scene

    first = SceneObject(id="obj_1", name="Quader", mesh=cube())
    second = SceneObject(id="obj_2", name="Quader (Kopie)", mesh=cube())
    scene = Scene(objects={"obj_1": first, "obj_2": second}, profile=profile)

    findings = check_bodies_in_one_place(scene)

    assert findings, "zwei Körper an einem Ort sind ein Befund"
    assert findings[0].code == "arrange.bodies_in_one_place"
    assert findings[0].severity == "info", "nichts ging schief — es ist nur unsichtbar"
    assert findings[0].values["count"] == 2
    assert "Quader (Kopie)" in str(findings[0].values["objects"]), "die Zeile nennt die Körper"
    assert findings[0].object_id == "obj_1", "ein Klick auf die Zeile muss irgendwohin führen"


def test_bodies_in_the_same_spot_on_different_plates_are_fine(profile: Profile) -> None:
    """Jede Druckplatte hat ihren eigenen Nullpunkt.

    Die Gegenprobe, und ohne sie schlüge die Prüfung ausgerechnet nach dem
    Anordnen an: ``arrange_bed`` setzt Platte 2 bewusst an dieselbe Stelle wie
    Platte 1, weil beide einzeln gedruckt werden. Zwei Kopien auf zwei Platten
    liegen im Modell aufeinander und sind trotzdem richtig verteilt.
    """
    from app.core.scene.evaluate import check_bodies_in_one_place
    from app.core.types import Scene

    first = SceneObject(id="obj_1", name="Quader", mesh=cube(), plate=0)
    second = SceneObject(id="obj_2", name="Quader (Kopie)", mesh=cube(), plate=1)
    scene = Scene(objects={"obj_1": first, "obj_2": second}, profile=profile)

    findings = check_bodies_in_one_place(scene)

    assert not findings, [entry.code for entry in findings]


def test_two_alike_bodies_side_by_side_are_not_reported(profile: Profile) -> None:
    """Zwei gleiche Körper nebeneinander sind der Normalfall, kein Befund.

    Die Gegenprobe zur Ortsfrage: Gemeldet wird nicht, dass zwei Körper
    gleich *sind*, sondern dass sie am selben Ort *liegen*. Genau dahin führt
    das Anordnen — und wäre dieser Test rot, meldete der Prüfbericht jede
    ordentlich verteilte Kleinserie als Problem.
    """
    from app.core.scene.evaluate import check_bodies_in_one_place
    from app.core.types import Scene

    first = SceneObject(id="obj_1", name="Quader", mesh=cube())
    second = SceneObject(
        id="obj_2", name="Quader daneben", mesh=apply(cube(), translation((60.0, 0.0, 0.0)))
    )
    scene = Scene(objects={"obj_1": first, "obj_2": second}, profile=profile)

    findings = check_bodies_in_one_place(scene)

    assert not findings, [entry.code for entry in findings]


def test_duplicating_leads_into_the_stacked_state(profile: Profile) -> None:
    """Der ganze Weg, auf dem der Kunde in die Lage gerät.

    Die Prüfung darüber misst die Funktion; dieser Test misst, dass das
    Duplizieren wirklich dorthin führt und die Auswertung es von selbst
    bemerkt — ohne dass jemand *Kollisionen prüfen* aufruft. Gemeldet wurde
    genau das: „wenn ich Objekt duplizieren anklicke, ist das Objekt nicht
    zweimal da."

    Mit echter Geometrie und über das echte Register, denn der Hash ist die
    Grundlage der Prüfung: Eine Attrappe hat keinen, und ein Test mit ihr wäre
    grün, ohne je einen Befund gesehen zu haben.
    """
    from app.core.bootstrap import load_operations
    from app.core.scene import History, OperationDraft, evaluate
    from app.core.types import Document

    load_operations()
    document = Document(format_version=1, app_version="0.0.1")
    history = History(document)
    history.apply("Quader", [OperationDraft(op="create_box", inputs=(), params={})])
    history.apply(
        "Duplizieren",
        [OperationDraft(op="duplicate_object", inputs=("obj_1",), params={})],
    )

    result = evaluate(document, profile)

    assert result.complete, "der Lauf muss bis zum Duplizieren kommen"
    assert list(result.scene.objects) == ["obj_1", "obj_2"], "das Original behält seine Kennung"
    codes = [entry.code for entry in result.scene.report.findings]
    assert "arrange.bodies_in_one_place" in codes, codes


def test_a_bore_shrunk_out_of_recognition_keeps_the_body(
    document: Document, profile: Profile
) -> None:
    """Eine Bohrung, die zu klein zum Wiedererkennen wird, ist kein Programmfehler.

    ``_recognised_resized_feature`` warf hier einen ``InternalError`` mit dem
    Satz „Erstellen Sie einen Fehlerbericht" — und nahm das fertig gerechnete
    Ergebnis mit, weil eine geworfene Ausnahme das ganze ``OpResult`` nimmt.
    Gemessen an ``spool-bearing-holder-p1stp.stl`` aus dem Kundenbestand: Wer
    die 3,4-mm-Bohrung eines 3 mm dünnen Teils auf 0,2 mm verkleinert, bekommt
    genau die 11,75 mm³ Material zurück, die die Rechnung verlangt, und danach
    die Absage. Die Auswertung hielt an, die richtige Geometrie war fort.

    Ein Loch von 0,2 mm ist keines, das die Erkennung findet — das ist eine
    Aussage über die Geometrie und nicht über das Programm. Der Körper bleibt
    also, das Merkmal geht, und ein Befund sagt beides.

    Geprüft wird an ``plate_holes.stl``: Die Platte trägt vier Bohrungen, und
    eine davon auf das Minimum des Schemas zu schrumpfen erzeugt denselben
    Fall wie am Kundenteil.
    """
    project, history = loaded(document, "plate_holes.stl")
    first = evaluate(document, profile, sources=ProjectSources(project))
    body = first.scene.objects["obj_1"]
    bores = [name for name, entry in body.features.items() if entry.kind == "hole"]
    assert bores, "ohne erkannte Bohrung prüft dieser Test nichts"
    before = body.mesh.volume

    history.apply(
        _("Bohrung ändern"),
        [
            OperationDraft(
                op="resize_hole",
                inputs=("obj_1",),
                params={"diameter": 0.2, "at_feature": bores[0], "compensate": False},
            )
        ],
    )
    result = evaluate(document, profile, sources=ProjectSources(project))

    assert result.complete, (
        "die Auswertung hielt an und warf das gerechnete Ergebnis weg: "
        f"gestoppt bei op {result.stopped_at}"
    )
    changed = result.scene.objects["obj_1"]
    assert changed.mesh.volume > before, (
        "eine kleinere Bohrung gibt Material zurück — die Geometrie ist gerechnet"
    )
    assert bores[0] not in changed.features, (
        "ein Merkmal zu behalten, das die Erkennung nicht bestätigt, wäre eine Behauptung"
    )
    codes = [entry.code for entry in result.scene.report.findings]
    assert "resize_hole.feature_lost" in codes, codes
    assert not [code for code in codes if code.startswith("op.resize_hole.")], (
        f"kein Programmfehler mehr, sondern ein Befund: {codes}"
    )


def test_a_bore_that_stays_recognisable_keeps_its_name(
    document: Document, profile: Profile
) -> None:
    """Die Gegenprobe: Wo die Erkennung greift, bleibt das Merkmal.

    Ohne sie wäre der Test darüber auch dann grün, wenn *jede* Änderung das
    Merkmal fallen ließe — und dann hätte die Operation ihren Zweck verloren.
    """
    project, history = loaded(document, "plate_holes.stl")
    first = evaluate(document, profile, sources=ProjectSources(project))
    body = first.scene.objects["obj_1"]
    bores = [name for name, entry in body.features.items() if entry.kind == "hole"]
    assert bores
    before = body.mesh.volume

    history.apply(
        _("Bohrung ändern"),
        [
            OperationDraft(
                op="resize_hole",
                inputs=("obj_1",),
                params={"diameter": 8.0, "at_feature": bores[0], "compensate": False},
            )
        ],
    )
    result = evaluate(document, profile, sources=ProjectSources(project))

    assert result.complete
    changed = result.scene.objects["obj_1"]
    assert changed.mesh.volume < before, "eine größere Bohrung trägt Material ab"
    assert bores[0] in changed.features, "die vergrößerte Bohrung behält ihren Namen"
    codes = [entry.code for entry in result.scene.report.findings]
    assert "resize_hole.feature_lost" not in codes, codes


def test_scaling_below_what_the_printer_leaves_says_so(
    document: Document, profile: Profile
) -> None:
    """Für „zu groß" gibt es einen Befund, für „zu klein" gab es keinen.

    Gemessen beim Durchfahren der Zahlenschieber über ihren ganzen Bereich:
    ``scale_object`` mit dem Faktor 0,001 macht aus einem Quader von 60 × 40 ×
    10 mm ein Teil von Hundertstelmillimetern — Volumen 0,0 in der Anzeige,
    **kein einziger Befund**, und im Verlauf steht ein Schritt, der etwas
    getan zu haben scheint. ``arrange.out_of_build_volume`` deckt die andere
    Richtung ab; diese hatte niemanden.

    Die Grenze kommt aus dem Profil und nicht aus dem Code (Regel 7):
    ``smallest_printable_volume`` ist ein Stück Extrusionsbahn von einer
    Bahnbreite Länge, am Centauri mit 0,4er Düse 0,035 mm³.
    """
    history = History(document)
    history.apply(
        _("Quader"),
        [OperationDraft(op="create_box", params={"width": 60.0, "depth": 40.0, "height": 10.0})],
    )
    history.apply(
        _("Winzig"),
        [OperationDraft(op="scale_object", inputs=("obj_1",), params={"factor": 0.001})],
    )
    result = evaluate(document, profile)

    assert result.complete, "ein Hinweis, keine Absage"
    body = result.scene.objects["obj_1"]
    assert body.mesh.volume < profile.smallest_printable_volume, (
        "sonst prüft dieser Test einen Körper, den der Drucker sehr wohl hinterlässt"
    )
    codes = [entry.code for entry in result.scene.report.findings]
    assert "transform.below_printable" in codes, codes


def test_a_scale_that_still_prints_stays_quiet(document: Document, profile: Profile) -> None:
    """Die Gegenprobe: Wer halb so groß rechnet, bekommt keine Warnung.

    Ohne sie wäre der Test darüber auch dann grün, wenn *jede* Verkleinerung
    warnte — und eine Warnung, die immer kommt, liest niemand mehr.
    """
    history = History(document)
    history.apply(
        _("Quader"),
        [OperationDraft(op="create_box", params={"width": 60.0, "depth": 40.0, "height": 10.0})],
    )
    history.apply(
        _("Halb"),
        [OperationDraft(op="scale_object", inputs=("obj_1",), params={"factor": 0.5})],
    )
    result = evaluate(document, profile)

    assert result.complete
    codes = [entry.code for entry in result.scene.report.findings]
    assert "transform.below_printable" not in codes, codes


def test_fitting_to_a_size_below_the_nozzle_says_so(document: Document, profile: Profile) -> None:
    """Derselbe Fall über *Auf Maß bringen*, das eigene Schema-Minimum 0,1 mm.

    Beide Wege enden in derselben Rechnung, und beide hatten dieselbe Lücke —
    ein Befund an nur einem von ihnen wäre die halbe Antwort.
    """
    history = History(document)
    history.apply(
        _("Quader"),
        [OperationDraft(op="create_box", params={"width": 60.0, "depth": 40.0, "height": 10.0})],
    )
    history.apply(
        _("Auf Maß"),
        [OperationDraft(op="fit_to_size", inputs=("obj_1",), params={"largest": 0.1})],
    )
    result = evaluate(document, profile)

    assert result.complete
    codes = [entry.code for entry in result.scene.report.findings]
    assert "transform.fitted" in codes, "die Operation sagt weiterhin, was sie tat"
    assert "transform.below_printable" in codes, codes


# --- Erkannte Merkmale versetzen (Kundenumfrage S-20260903-74133c) ------------------


def _run_op(op: str, entry: SceneObject, profile: Profile, **params: object):
    """Eine Operation fahren, wie der Verlauf sie fährt."""
    from app.core.scene.cancel import NeverCancelled
    from app.core.types import OpContext, Scene

    spec = REGISTRY.get(op)
    return spec.fn(
        OpContext(
            scene=Scene(objects={entry.id: entry}),
            inputs=[entry],
            params=spec.params(**params),
            profile=profile,
            quality="fine",
            seed=7,
            progress=lambda fraction, text: None,
            ask=lambda question, choices: choices[0],
            cancelled=NeverCancelled(),
        )
    )


def _block_with_a_bore(profile: Profile) -> tuple[SceneObject, str]:
    """Ein Quader mit einer durchgehenden Bohrung, wie die Erkennung sie sieht."""
    from app.core.geom.prepare import drill

    block = MeshData.of(trimesh.creation.box(extents=(60.0, 40.0, 20.0)))
    bored = drill(
        block,
        position=(-15.0, 0.0, 10.0),
        axis="z",
        diameter=8.0,
        profile=profile,
        compensate=False,
    ).mesh
    entry = SceneObject(id="obj_1", name="Platte", mesh=bored, features=detect(bored))
    hole = next(name for name, f in entry.features.items() if f.kind == "hole")
    return entry, hole


def test_a_recognised_bore_can_be_moved(profile: Profile) -> None:
    """Der Kunde wollte genau das, und es gab es nicht (Umfrage vom 03.09.2026).

    „Move existing holes and other recognised details/features" — bei 1 von 5
    der einzige konkrete Punkt. Gemessen war der Befund eindeutig: Von 95
    Operationen fasste **eine** ein erkanntes Merkmal an (``resize_hole`` über
    ``at_feature``), und die kannte nur den Durchmesser. Wer eine Bohrung
    versetzen wollte, musste sie verschließen und an neuen Zahlen neu setzen —
    zwei Schritte, Koordinaten von Hand, und die Merkmalskennung war weg. Damit
    brechen Passungen, die auf sie zeigen (``fit.missing_feature``).

    Hier wird das Ergebnis gemessen und nicht der Weg: Das Volumen bleibt (es
    ist dieselbe Bohrung), an der alten Stelle ist wieder Material, an der
    neuen fehlt es.
    """
    entry, hole = _block_with_a_bore(profile)
    before = entry.mesh.volume

    moved = _run_op("move_feature", entry, profile, at_feature=hole, x=15.0, y=0.0, z=0.0)
    body = as_mesh_data(moved.outputs[0].mesh)

    assert body.raw.is_watertight, "eine versetzte Bohrung lässt den Körper geschlossen"
    assert body.volume == pytest.approx(before, rel=0.02), (
        "dieselbe Bohrung, nur woanders — das Volumen ändert sich nicht"
    )
    # **Gefragt wird über den Querschnitt, nicht über den Abstand.** Zur
    # nächsten Fläche sind es in der Mitte einer Ø8 Bohrung 4 mm — und 4 mm
    # auch mitten im Material einer 20 mm dicken Platte; die Frage „Loch oder
    # nicht" beantwortet der Abstand nicht. ``contains`` wäre die direkte
    # Antwort und braucht ``rtree``, das hier fehlt — die Suite stirbt daran
    # im langen Lauf. Der Schnitt ist das Werkzeug des Projekts und sagt es
    # genauso: Ein Loch ist ein innerer Ring.
    from app.core.slice.analysis import cross_section

    schnitt = cross_section(body, 0.0)
    assert schnitt is not None
    ringe = [
        (ring.centroid.x, ring.centroid.y)
        for teil in getattr(schnitt, "geoms", [schnitt])
        for ring in teil.interiors
    ]
    assert len(ringe) == 1, f"genau ein Loch im Querschnitt, gefunden: {ringe}"
    assert ringe[0][0] == pytest.approx(15.0, abs=0.5), f"und es liegt rechts: {ringe[0]}"


def test_the_moved_bore_keeps_its_identity(profile: Profile) -> None:
    """Die Kennung überlebt — sonst bricht jede Passung, die auf sie zeigt.

    Das ist der ganze Unterschied zum Umweg von Hand: Verschließen und neu
    bohren ergibt dieselbe Geometrie und ein **anderes** Merkmal. Wer eine
    Passung auf ``hole_1`` gelegt hat, findet danach nichts mehr.
    """
    entry, hole = _block_with_a_bore(profile)

    moved = _run_op("move_feature", entry, profile, at_feature=hole, x=15.0, y=0.0, z=0.0)
    features = moved.outputs[0].features

    assert hole in features, sorted(features)
    versetzt = features[hole]
    assert versetzt.kind == "hole"
    assert versetzt.params["centre"][0] == pytest.approx(15.0, abs=0.5), versetzt.params["centre"]


def test_a_feature_that_cannot_be_moved_says_so(profile: Profile) -> None:
    """Drei Arten lassen sich nicht versetzen, und das ist eine Auskunft.

    Eine Fläche gehört zur Oberfläche des Körpers — sie zu bewegen ist
    ``push_face``. Eine Kantenschleife ist ein Netzfehler und kein Körper. Ein
    Verrundung hängt an ihrer Kante; versetzt man sie allein, bleibt die Kante
    scharf und die Rundung liegt daneben.

    Regel 17: Der Satz nennt in jedem der drei Fälle, was stattdessen hilft.
    """
    from app.core.errors import UserError

    entry, _hole = _block_with_a_bore(profile)
    face = next(name for name, f in entry.features.items() if f.kind == "face")

    with pytest.raises(UserError) as raised:
        _run_op("move_feature", entry, profile, at_feature=face, x=0.0, y=0.0, z=0.0)

    assert raised.value.suggestions, "Regel 17"
    assert "push_face" not in str(raised.value), "der Satz nennt den Weg, nicht den Bezeichner"


def test_moving_a_feature_is_registered_completely() -> None:
    """Registerkonsistenz: Was der Katalog verspricht, steht auch da."""
    spec = REGISTRY.get("move_feature")

    assert set(spec.applies_to) == {"hole", "pin", "cone", "sphere"}
    assert spec.touches_features, "die Kennung reist mit"
    assert spec.requires_seed, "der Weg geht über die Boolesche Rückfallkette"
    felder = {entry.name: entry for entry in spec.params.spec()}
    assert felder["at_feature"].kind == "feature" and felder["at_feature"].required
    assert felder["at_feature"].placement == "front"
    for achse in ("x", "y", "z"):
        assert felder[achse].unit == "mm", achse
        assert felder[achse].placement == "front"


def test_a_recognised_pin_can_be_moved_too(profile: Profile) -> None:
    """Nicht nur Löcher — der Kunde schrieb „and other recognised features".

    Ein Zapfen ist der Gegenfall zur Bohrung: Materie statt Hohlraum. Dieselbe
    Maschine, nur mit vertauschten Booleschen — an der alten Stelle abziehen,
    an der neuen vereinen. Gemessen an einer Platte 60 x 40 x 10 mit einem
    Zapfen Ø 8: Volumen 24300,7 vor dem Versetzen, 24301,1 danach.

    Die 0,4 mm³ Unterschied sind die Überlappung, mit der jeder Werkzeugkörper
    gebaut wird — ohne sie träfe die Boolesche auf zusammenfallende Flächen,
    und das ist der eine Fall, der sie zuverlässig bricht (§39).
    """
    from app.core.slice.analysis import cross_section

    plate = trimesh.creation.box(extents=(60.0, 40.0, 10.0))
    stud = trimesh.creation.cylinder(radius=4.0, height=12.0, sections=48)
    stud.apply_translation((-15.0, 0.0, 5.0))
    body = MeshData.of(trimesh.boolean.union([plate, stud]))
    features = detect(body)
    pin = next(name for name, f in features.items() if f.kind == "pin")
    entry = SceneObject(id="obj_1", name="Platte", mesh=body, features=features)
    centre = tuple(float(v) for v in features[pin].params["centre"])

    moved = _run_op(
        "move_feature", entry, profile, at_feature=pin, x=15.0, y=centre[1], z=centre[2]
    )
    after = as_mesh_data(moved.outputs[0].mesh)

    assert after.raw.is_watertight
    assert after.volume == pytest.approx(body.volume, rel=0.01), "derselbe Zapfen, nur woanders"
    # Über der Platte steht nur noch der versetzte Zapfen.
    above = cross_section(after, 8.0)
    assert above is not None
    parts = list(getattr(above, "geoms", [above]))
    assert len(parts) == 1, f"genau ein Zapfen über der Platte, gefunden: {len(parts)}"
    assert parts[0].centroid.x == pytest.approx(15.0, abs=0.5)


def test_a_fillet_says_why_it_stays_where_it_is(profile: Profile) -> None:
    """Was übrig bleibt, bleibt aus einem Grund, der nicht am Bau liegt.

    Kuppe und Kegel waren bis heute Mittag gesperrt, weil ihr Körper aus den
    Kennzahlen falsch entstand — das ist behoben, sie werden aus ihren eigenen
    Flächen gebaut. Eine Verrundung bleibt draußen, und zwar aus einem anderen
    Grund: Sie **gehört zu ihrer Kante**. Versetzt man sie allein, bliebe die
    Kante scharf und die Rundung läge daneben — ein Körper, der entstünde, wäre
    geometrisch richtig und sachlich falsch.

    Der Unterschied zählt für das Panel: Der erste Grund verschwindet, wenn
    jemand den Bau verbessert, der zweite nie.
    """
    import dataclasses

    from app.core.errors import UserError
    from app.core.types import Feature

    entry, _hole = _block_with_a_bore(profile)
    rounded = Feature(
        id="fillet_1",
        kind="fillet",
        provenance="detected",
        params={"centre": (0.0, 0.0, 0.0), "axis": (0.0, 0.0, 1.0), "radius": 2.0},
    )
    entry = dataclasses.replace(entry, features={**entry.features, rounded.id: rounded})

    with pytest.raises(UserError) as raised:
        _run_op("move_feature", entry, profile, at_feature=rounded.id, x=5.0, y=0.0, z=0.0)

    assert raised.value.suggestions, "Regel 17"
    assert "Kante" in str(raised.value), str(raised.value)


def test_a_recognised_bore_can_be_removed(profile: Profile) -> None:
    """Löschen ist derselbe Motor mit nur einem Gang.

    Robert am 03.09.2026: „ich will die auch löschen können, also jede
    Operation". Für ein erkanntes Merkmal ist das die halbe Bewegung des
    Versetzens — an der alten Stelle das Gegenteil dessen, was das Merkmal ist,
    und dann nichts mehr. Eine Bohrung wird gefüllt, ein Zapfen abgetragen.

    Die Kennung geht dabei **mit** und bleibt nicht als Verweis ins Leere
    stehen: Das Merkmal ist weg, und ein Befund sagt es, damit spätere Schritte
    und Passungen es erfahren statt darüber zu stolpern.
    """
    entry, hole = _block_with_a_bore(profile)
    before = entry.mesh.volume

    gone = _run_op("remove_feature", entry, profile, at_feature=hole)
    body = as_mesh_data(gone.outputs[0].mesh)

    assert body.raw.is_watertight
    assert body.volume > before, "die Bohrung ist zu, also ist mehr Material da"
    assert body.volume == pytest.approx(60.0 * 40.0 * 20.0, rel=0.01), "wieder ein voller Quader"
    assert hole not in gone.outputs[0].features, "das Merkmal ist fort"
    assert "remove_feature.gone" in [f.code for f in gone.findings], [f.code for f in gone.findings]


def test_a_recognised_pin_can_be_removed(profile: Profile) -> None:
    """Der Gegenfall: Materie statt Hohlraum, also abziehen statt füllen."""
    plate = trimesh.creation.box(extents=(60.0, 40.0, 10.0))
    stud = trimesh.creation.cylinder(radius=4.0, height=12.0, sections=48)
    stud.apply_translation((-15.0, 0.0, 5.0))
    body = MeshData.of(trimesh.boolean.union([plate, stud]))
    features = detect(body)
    pin = next(name for name, f in features.items() if f.kind == "pin")
    entry = SceneObject(id="obj_1", name="Platte", mesh=body, features=features)

    gone = _run_op("remove_feature", entry, profile, at_feature=pin)
    after = as_mesh_data(gone.outputs[0].mesh)

    assert after.raw.is_watertight
    assert after.volume == pytest.approx(60.0 * 40.0 * 10.0, rel=0.01), "wieder eine glatte Platte"
    assert pin not in gone.outputs[0].features


def test_removing_a_feature_is_registered_completely() -> None:
    """Dieselbe Reichweite wie das Versetzen — es ist dieselbe Maschine."""
    spec = REGISTRY.get("remove_feature")

    assert set(spec.applies_to) == {"hole", "pin", "cone", "sphere"}
    assert spec.touches_features
    assert spec.requires_seed, "auch das Füllen geht über die Rückfallkette"
    fields = {entry.name: entry for entry in spec.params.spec()}
    assert fields["at_feature"].kind == "feature" and fields["at_feature"].required
    assert fields["at_feature"].placement == "front"
    assert len(fields) == 1, "mehr braucht es nicht — das Merkmal sagt alles"


def test_a_recognised_bore_can_be_turned(profile: Profile) -> None:
    """Dieselbe Maschine, eine Drehung zwischen den beiden Booleschen.

    „Verschieben, drehen, skalieren usw" (Robert, 03.09.2026). Für ein
    erkanntes Merkmal ist das Drehen dasselbe Paar wie das Versetzen — an der
    alten Stelle füllen, an der neuen setzen —, nur steht zwischen beiden eine
    Drehmatrix statt einer Verschiebung.

    **Achse und Winkel, wie bei ``rotate_object``.** Das Register spricht diese
    Sprache schon, und ein Kunde, der einen Körper um Z gedreht hat, sucht für
    eine Bohrung nicht nach etwas anderem. Gedreht wird um die **Mitte des
    Merkmals**, nicht um den Ursprung: Eine Bohrung, die beim Kippen davonwandert,
    ist keine gekippte Bohrung.

    Geprüft wird die Achse des Ergebnisses: Eine Bohrung entlang Z, um X um 90°
    gedreht, liegt danach entlang Y.
    """
    entry, hole = _block_with_a_bore(profile)
    axis_before = tuple(round(float(v), 3) for v in entry.features[hole].params["axis"])
    assert axis_before == (0.0, 0.0, 1.0), axis_before

    turned = _run_op("rotate_feature", entry, profile, at_feature=hole, axis="x", angle=90.0)
    body = as_mesh_data(turned.outputs[0].mesh)

    assert body.raw.is_watertight
    after = tuple(round(abs(float(v)), 2) for v in turned.outputs[0].features[hole].params["axis"])
    assert after == (0.0, 1.0, 0.0), f"aus Z wird Y, gemessen {after}"


def test_turning_a_bore_keeps_its_centre(profile: Profile) -> None:
    """Gedreht wird um das Merkmal, nicht um den Ursprung.

    Der Unterschied zählt: Eine Bohrung bei x = -15, um X gekippt, bleibt bei
    x = -15. Würde um den Ursprung gedreht, läge sie danach woanders — und der
    Kunde hätte zwei Änderungen bekommen, wo er eine wollte.
    """
    entry, hole = _block_with_a_bore(profile)
    before = tuple(float(v) for v in entry.features[hole].params["centre"])

    turned = _run_op("rotate_feature", entry, profile, at_feature=hole, axis="x", angle=90.0)
    after = tuple(float(v) for v in turned.outputs[0].features[hole].params["centre"])

    assert after == pytest.approx(before, abs=1e-6), f"{before} -> {after}"


def test_turning_a_feature_is_registered_completely() -> None:
    """Dieselbe Sprache wie ``rotate_object`` — Achse als Auswahl, Winkel in Grad.

    **Ohne die Kugel**, und das ist Roberts „alles, was bei den jeweiligen
    sinnvoll ist": Sie hat keine Lage, die sich drehen ließe. Gedreht sähe sie
    aus wie vorher, und eine Handlung ohne Wirkung ist schlechter als keine.
    """
    spec = REGISTRY.get("rotate_feature")

    assert set(spec.applies_to) == {"hole", "pin", "cone"}
    assert "sphere" not in spec.applies_to, "eine Kugel hat keine Lage"
    assert spec.touches_features
    fields = {entry.name: entry for entry in spec.params.spec()}
    assert fields["axis"].kind == "enum" and fields["axis"].choices == ("x", "y", "z")
    from app.core.units import DEGREE_UNIT

    assert fields["angle"].unit == DEGREE_UNIT
    assert fields["angle"].placement == "front"
    assert fields["at_feature"].required and fields["at_feature"].placement == "front"


def test_a_recognised_pin_can_be_resized(profile: Profile) -> None:
    """Der vierte Ausgang derselben Maschine: abtragen, größer wieder ansetzen.

    Für Bohrungen gibt es das seit langem (``resize_hole``, mit eigenem Weg
    für den exakten Kern und Materialkompensation). Ein Zapfen hatte es nicht —
    „wir wollen ja alles ändern können" (Robert, 03.09.2026).

    Gemessen wird das Ergebnis: Ein Zapfen Ø 8 auf Ø 12 gebracht trägt mehr
    Material, und der Querschnitt über der Platte ist größer geworden.
    """
    from app.core.slice.analysis import cross_section

    plate = trimesh.creation.box(extents=(60.0, 40.0, 10.0))
    stud = trimesh.creation.cylinder(radius=4.0, height=12.0, sections=48)
    stud.apply_translation((-15.0, 0.0, 5.0))
    body = MeshData.of(trimesh.boolean.union([plate, stud]))
    features = detect(body)
    pin = next(name for name, f in features.items() if f.kind == "pin")
    entry = SceneObject(id="obj_1", name="Platte", mesh=body, features=features)

    before = cross_section(body, 8.0)
    assert before is not None

    bigger = _run_op("resize_feature", entry, profile, at_feature=pin, diameter=12.0)
    after_body = as_mesh_data(bigger.outputs[0].mesh)
    after = cross_section(after_body, 8.0)

    assert after_body.raw.is_watertight
    assert after is not None
    assert after.area > before.area * 1.5, f"{before.area:.1f} -> {after.area:.1f}"
    assert bigger.outputs[0].features[pin].params["diameter"] == pytest.approx(12.0, abs=0.3)


def test_the_size_row_is_the_same_row_for_a_bore_and_a_pin() -> None:
    """Im Panel steht *eine* Zeile „Größe ändern", nicht zwei mit einer toten.

    Für eine Bohrung erledigt es ``resize_hole``, für einen Zapfen
    ``resize_feature`` — zwei Operationen, weil die Bohrung einen eigenen Weg
    durch den exakten Kern und die Materialkompensation hat. Der Kunde geht das
    nichts an: Er sieht eine Zeile, und sie tut, was sie sagt.

    Zwei Zeilen, von denen bei jeder Merkmalsart eine ausgegraut wäre, sind
    genau die Sorte Oberfläche, die Robert mit „übersichtlich" ausgeschlossen
    hat.
    """
    from app.core.bootstrap import load_operations
    from app.core.perceive.actions import actions_for
    from app.core.types import Feature

    load_operations()
    common = {"centre": (0.0, 0.0, 0.0), "axis": (0.0, 0.0, 1.0), "diameter": 8.0, "depth": 10.0}
    bore = Feature(id="hole_1", kind="hole", provenance="detected", params=common)
    pin = Feature(id="pin_1", kind="pin", provenance="detected", params=common)

    for feature, expected in ((bore, "resize_hole"), (pin, "resize_feature")):
        rows = [
            entry for entry in actions_for(feature) if entry.op in {"resize_hole", "resize_feature"}
        ]
        assert len(rows) == 1, [entry.op for entry in rows]
        assert rows[0].op == expected, (feature.kind, rows[0].op)
        assert rows[0].fields, "die Zeile trägt ihr Maß"


def test_a_dome_is_built_from_its_own_faces(profile: Profile) -> None:
    """Eine Kuppe wird aus ihren eigenen Flächen gebaut, nicht aus einer Kugel.

    **Der Grundkörper war die falsche Vorlage, und das ist gemessen.** Die
    erkannte Mitte einer Kugelfläche liegt in der Fläche, auf der sie sitzt;
    wer die ganze Kugel abzieht, gräbt eine Mulde und verliert 445 mm³, ohne
    dass der Körper aufhört, wasserdicht zu sein.

    Die Merkmalsflächen sagen es genau: Sie begrenzen die Kuppe, ihr Randring
    liegt auf der Grundfläche, und mit einem Deckel darüber entsteht der
    Körper, der wirklich das Merkmal ist. Gemessen an einer Kuppe r = 6 auf
    einer Platte: 448,5 mm³ — die analytische Halbkugel hat 452,4, und die
    Differenz ist die Tesselierung der Vorlage, nicht ein Fehler des Baus.
    """
    from app.core.geom.prepare_ops import _feature_body

    plate = trimesh.creation.box(extents=(60.0, 40.0, 10.0))
    dome = trimesh.creation.icosphere(radius=6.0, subdivisions=3)
    dome.apply_translation((-15.0, 0.0, 5.0))
    body = MeshData.of(trimesh.boolean.union([plate, dome]))
    ball = next(f for f in detect(body).values() if f.kind == "sphere")

    built = _feature_body(body, ball)

    assert built is not None, "die Flächen der Kuppe begrenzen sie vollständig"
    assert built.raw.is_watertight
    assert built.volume == pytest.approx(448.5, rel=0.02), built.volume


def test_a_dome_can_be_moved_without_losing_material(profile: Profile) -> None:
    """Und damit trägt das Versetzen auch für Kuppe und Kegel.

    Der Fall, an dem es heute Vormittag gemessen scheiterte: Volumen 24 449
    vorher, 24 003 nachher — 445 mm³ waren fort, der Körper wasserdicht und
    still falsch. Mit dem aus den Flächen gebauten Körper bleibt das Volumen.
    """
    plate = trimesh.creation.box(extents=(60.0, 40.0, 10.0))
    dome = trimesh.creation.icosphere(radius=6.0, subdivisions=3)
    dome.apply_translation((-15.0, 0.0, 5.0))
    body = MeshData.of(trimesh.boolean.union([plate, dome]))
    features = detect(body)
    ball = next(name for name, f in features.items() if f.kind == "sphere")
    entry = SceneObject(id="obj_1", name="Platte", mesh=body, features=features)
    centre = tuple(float(v) for v in features[ball].params["centre"])

    moved = _run_op(
        "move_feature", entry, profile, at_feature=ball, x=15.0, y=centre[1], z=centre[2]
    )
    after = as_mesh_data(moved.outputs[0].mesh)

    assert after.raw.is_watertight
    assert after.volume == pytest.approx(body.volume, rel=0.01), (
        f"dieselbe Kuppe, nur woanders: {body.volume:.1f} -> {after.volume:.1f}"
    )


def test_the_movable_kinds_now_include_the_dome() -> None:
    """Vier Arten statt zwei — und die Sätze für die übrigen bleiben."""
    spec = REGISTRY.get("move_feature")

    assert set(spec.applies_to) == {"hole", "pin", "cone", "sphere"}
    assert "fillet" not in spec.applies_to, "eine Verrundung folgt ihrer Kante"
    assert "edge_loop" not in spec.applies_to, "ein Netzfehler ist kein Körper"
    assert "face" not in spec.applies_to, "dafür gibt es push_face"


def test_a_countersink_keeps_its_bore_by_being_refused(profile: Profile) -> None:
    """Zwei Randringe heißen: Der Hohlraum gehört dem Merkmal nicht allein.

    Gemessen am 03.09.2026 an einer Platte 40 × 40 × 10 mit durchgehender Bohrung
    Ø 6 und Senkung Ø 12. Die Kegelfläche hat **zwei** Randringe — Ø 12 auf der
    Oberseite und Ø 6 dort, wo sie in die Bohrung übergeht. Mit einem Deckel je
    Ring entsteht daraus ein sauberer Kegelstumpf: 196,65 mm³, wasserdicht, und
    die analytische Rechnung sagt 197,92.

    Er ist trotzdem das falsche Werkzeug, und das ist der Grund für diesen
    Test. Beim Auffüllen an der alten Stelle wuchs der Körper um alle
    196,65 mm³, obwohl nur 113,1 davon Senkung waren — der Rest war die
    **Bohrung**, und ein Querschnitt bei z = 3,5 hatte danach kein Loch mehr.
    Wer die Senkung versetzt hätte, hätte seine Bohrung verloren, ohne dass
    irgendetwas rot geworden wäre.

    Ein zweiter Randring ist deshalb die Absage wert. Sie fällt hier nicht
    zufällig durch die Planaritätsprüfung — die beiden Ringe liegen ohnehin in
    verschiedenen Ebenen —, sondern weil gezählt wird.
    """
    from app.core.errors import UserError
    from app.core.geom.prepare_ops import _feature_body

    block = MeshData.of(trimesh.creation.box(extents=(40.0, 40.0, 10.0)))
    bored = drill(
        block,
        position=(0.0, 0.0, 5.0),
        axis="z",
        diameter=6.0,
        profile=profile,
        compensate=False,
    ).mesh
    sunk = countersink(
        bored, position=(0.0, 0.0, 5.0), axis="z", diameter=12.0, profile=profile
    ).mesh
    entry = SceneObject(id="obj_1", name="Platte", mesh=sunk, features=detect(sunk))
    cone = next(name for name, found in entry.features.items() if found.kind == "cone")

    patch = trimesh.Trimesh(
        vertices=sunk.raw.vertices,
        faces=np.asarray(sunk.raw.faces)[np.asarray(entry.features[cone].face_indices)],
        process=False,
    )
    patch.remove_unreferenced_vertices()
    patch.merge_vertices()
    edges = patch.edges_sorted
    rim = edges[trimesh.grouping.group_rows(edges, require_count=1)]
    assert len(trimesh.graph.connected_components(rim)) == 2, "zwei Randringe"

    assert _feature_body(sunk, entry.features[cone]) is None

    with pytest.raises(UserError) as raised:
        _run_op("move_feature", entry, profile, at_feature=cone, x=8.0, y=0.0, z=3.5)

    assert raised.value.suggestions, "Regel 17"
    assert "Bohrung" in str(raised.value), str(raised.value)


def test_applies_to_holds_outside_the_menu(profile: Profile) -> None:
    """``applies_to`` stand nur im Menü, und der Chat kam daran vorbei.

    Zwei Messungen vom 03.09.2026, beide still und beide falsch:

    * ``resize_feature`` nimmt laut Register Zapfen, Kegel und Kugel — auf eine
      **Bohrung** gerufen lief es trotzdem durch und machte aus 46 997,6 mm³
      45 737,0. Das ist nicht dasselbe wie ``resize_hole``: Die Bohrung hat
      einen eigenen Weg durch den exakten Kern und eine Materialkompensation,
      die für einen Zapfen andersherum liefe. Der Kunde bekäme ein Loch, das
      beim Drucken zu eng wird.
    * ``rotate_feature`` nimmt Bohrung, Zapfen und Kegel — auf eine **Kuppel**
      gerufen lief es ebenfalls durch und nahm 112 von 24 448 mm³ mit. Eine
      Kugelfläche hat keine Lage; gedreht sähe sie aus wie vorher, und genau
      deshalb steht sie nicht in der Liste.

    Beide Male blieb der Körper wasserdicht. Ein Ergebnis, das keiner Prüfung
    auffällt und trotzdem falsch ist, ist der teuerste Fehler, den es gibt.
    """
    from app.core.errors import UserError

    entry, hole = _block_with_a_bore(profile)
    with pytest.raises(UserError) as falsches_mass:
        _run_op("resize_feature", entry, profile, at_feature=hole, diameter=12.0)
    assert falsches_mass.value.suggestions, "Regel 17"
    assert "Bohrung ändern" in str(falsches_mass.value), str(falsches_mass.value)

    plate = trimesh.creation.box(extents=(60.0, 40.0, 10.0))
    dome = trimesh.creation.icosphere(radius=6.0, subdivisions=3)
    dome.apply_translation((-15.0, 0.0, 5.0))
    domed = MeshData.of(trimesh.boolean.union([plate, dome]))
    domed_entry = SceneObject(id="obj_2", name="Kuppel", mesh=domed, features=detect(domed))
    ball = next(name for name, found in domed_entry.features.items() if found.kind == "sphere")

    with pytest.raises(UserError) as falsche_drehung:
        _run_op("rotate_feature", domed_entry, profile, at_feature=ball, axis="x", angle=45.0)
    assert falsche_drehung.value.suggestions, "Regel 17"
    assert "Lage" in str(falsche_drehung.value), str(falsche_drehung.value)


def test_a_cavity_inside_the_body_moves_without_losing_material(profile: Profile) -> None:
    """Ein Ausschnitt ohne Rand ist schon geschlossen — und lässt sich versetzen.

    Der Deckelbau braucht einen Randring, um aus einer Merkmalsfläche einen
    Körper zu machen. Ein Hohlraum mitten im Material hat keinen: Seine Fläche
    ist rundum geschlossen, und sie **ist** bereits der Körper. Bis zum
    03.09.2026 fiel er trotzdem durch — die Prüfung „weniger als drei
    Randkanten" traf null Randkanten mit.

    Gemessen an einem Würfel 40 mm mit einer Kugel r = 8 darin: Der
    Merkmalskörper hat 2126,2 mm³ gegen 2144,7 der analytischen Kugel, und das
    ist die Tesselierung der Vorlage. Versetzt um 10 mm bleibt das Volumen des
    Ganzen auf die Stelle genau gleich — es wird an der alten Stelle so viel
    aufgefüllt, wie an der neuen abgetragen wird —, und die Erkennung findet
    die Mitte danach bei genau (10, 0, 0).
    """
    block = trimesh.creation.box(extents=(40.0, 40.0, 40.0))
    void = trimesh.creation.icosphere(radius=8.0, subdivisions=3)
    body = MeshData.of(trimesh.boolean.difference([block, void]))
    entry = SceneObject(id="obj_1", name="Block", mesh=body, features=detect(body))
    cavity = next(name for name, found in entry.features.items() if found.kind == "sphere")

    result = _run_op("move_feature", entry, profile, at_feature=cavity, x=10.0, y=0.0, z=0.0)
    moved = result.outputs[0].mesh

    assert moved.raw.is_watertight
    assert moved.raw.volume == pytest.approx(body.raw.volume, abs=1e-3), "aufgefüllt wie abgetragen"
    again = next(found for found in detect(moved).values() if found.kind == "sphere")
    assert again.params["centre"][0] == pytest.approx(10.0, abs=0.05), again.params["centre"]


def test_a_moved_bore_leaves_no_plug_standing_proud(profile: Profile) -> None:
    """Roberts Befund am eigenen Kundenmodell, 03.09.2026.

    „Die Bohrung wird richtig verschoben, aber an der alten Stelle steht das
    Material dann oben und unten über." Das Bildschirmfoto zeigte einen
    Pfropfen, der aus beiden Flächen herausragte.

    **Der Grund ist ein Werkzeug, das für den falschen Zweck richtig gebaut
    war.** Der Körper eines Merkmals wird absichtlich etwas größer gebaut als
    gemessen, und eine durchgehende Bohrung bekommt mindestens ihren
    Durchmesser als Länge, damit sie das Material auf jeden Fall trifft. Beim
    Ausschneiden macht das nichts. Beim Vereinen trägt es außen auf — und je
    weiter die Bohrung ist, desto mehr.

    Nachgebaut an einer 10 mm starken Platte mit durchgehender Bohrung Ø 16:
    Das Teil war nach dem Versetzen **16,03 mm hoch statt 10**, oben und unten
    drei Millimeter Pfropfen, und das Volumen wuchs von 21 995 auf 23 600 mm³.
    Der Körper blieb dabei wasserdicht — es wäre also nur am Bild aufgefallen.

    ``plug`` beschneidet seinen Stopfen seit langem an der Hülle des Teils.
    Genau das fehlte hier, und deshalb prüft dieser Test die **Hülle** und
    nicht nur das Volumen: Ein Pfropfen, der oben so viel aufträgt, wie an der
    neuen Stelle abgetragen wird, wäre volumengleich und trotzdem falsch.
    """
    block = MeshData.of(trimesh.creation.box(extents=(60.0, 40.0, 10.0)))
    bored = drill(
        block,
        position=(-15.0, 0.0, 5.0),
        axis="z",
        diameter=16.0,
        profile=profile,
        compensate=False,
    ).mesh
    entry = SceneObject(id="obj_1", name="Platte", mesh=bored, features=detect(bored))
    hole = next(name for name, found in entry.features.items() if found.kind == "hole")

    result = _run_op("move_feature", entry, profile, at_feature=hole, x=15.0, y=0.0, z=0.0)
    moved = result.outputs[0].mesh

    assert moved.raw.is_watertight
    assert moved.raw.bounds == pytest.approx(bored.raw.bounds, abs=1e-6), (
        f"nichts steht über: {moved.raw.bounds.tolist()}"
    )
    assert moved.raw.volume == pytest.approx(bored.raw.volume, rel=1e-6)


def test_a_through_bore_moved_along_its_axis_says_it_no_longer_goes_through(
    profile: Profile,
) -> None:
    """Beim Nachmessen des Stopfens aufgefallen, 03.09.2026.

    Das Werkzeug eines Merkmals ist aus seinen gemessenen Kennzahlen gebaut und
    wandert mit. Eine Bohrung, die als durchgehend erkannt wurde, ist nach dem
    Versetzen genau so lang wie vorher — und wenn sie entlang ihrer eigenen
    Achse wandert, geht sie nicht mehr durch.

    Gemessen an einer 10 mm starken Platte mit Bohrung Ø 16, um 5 mm in Z
    versetzt: Unten blieben **1,985 mm Material** stehen, 398 mm³, das Volumen
    stieg von 21 995 auf 22 393. Der Körper war wasserdicht und einteilig, und
    das Ergebnis ist geometrisch richtig — es ist nur nicht das, was der Kunde
    erwartet hat. „Muss der Kunde raten, ist es falsch" (Robert).

    **Quer versetzt bleibt es still**, und das gehört zur Zusage: Ein Befund,
    der bei jedem Versetzen erscheint, wird nach dem dritten Mal übersehen. Die
    Messung läuft deshalb nur, wenn die Bewegung eine Komponente entlang der
    Merkmalsachse hat — sie kostet eine Boolesche, die sonst nichts zu sagen
    hätte.
    """
    block = MeshData.of(trimesh.creation.box(extents=(60.0, 40.0, 10.0)))
    bored = drill(
        block,
        position=(-15.0, 0.0, 5.0),
        axis="z",
        diameter=16.0,
        profile=profile,
        compensate=False,
    ).mesh
    entry = SceneObject(id="obj_1", name="Platte", mesh=bored, features=detect(bored))
    hole = next(name for name, found in entry.features.items() if found.kind == "hole")
    assert entry.features[hole].params.get("through"), "sonst prüft dieser Test nichts"

    across = _run_op("move_feature", entry, profile, at_feature=hole, x=15.0, y=0.0, z=0.0)
    assert not [entry for entry in across.findings if "through" in entry.code], (
        "quer versetzt bleibt eine durchgehende Bohrung durchgehend"
    )

    along = _run_op("move_feature", entry, profile, at_feature=hole, x=15.0, y=0.0, z=5.0)
    said = [found for found in along.findings if found.code == "move_feature.no_longer_through"]
    assert said, [found.code for found in along.findings]
    assert said[0].severity == "warning"
    assert "durch" in str(said[0].message)
    assert along.outputs[0].mesh.raw.volume > bored.raw.volume, "Material ist stehengeblieben"


def test_a_recognised_feature_can_be_duplicated(profile: Profile) -> None:
    """Der weiteste Weg von allen, bis heute (3d-druck-d4, 03.09.2026).

    Wer eine zweite Bohrung wie die erste wollte, rief *Bohrung setzen* und
    tippte Durchmesser, Tiefe, Achse und drei Koordinaten von Hand ab — obwohl
    Solidon alle vier Werte gemessen hat und im Merkmalspanel anzeigt. Vier
    abgeschriebene Zahlen sind vier Gelegenheiten für einen Tippfehler.

    Gemessen wird das Ergebnis und nicht der Weg: Das Volumen sinkt um genau
    eine Bohrung, das Original bleibt, wo es war, und die **Erkennung** findet
    hinterher zwei — die zweite ist also wirklich eine Bohrung und nicht ein
    Loch, das so aussieht.

    Die Kopie bekommt eine **eigene** Kennung. Das ist der Unterschied zum
    Versetzen, bei dem die Kennung mitreist: Hier gibt es hinterher zwei
    Merkmale, und eine Passung, die auf das Original zeigt, darf davon nichts
    merken.
    """
    entry, hole = _block_with_a_bore(profile)
    before = as_mesh_data(entry.mesh).raw.volume
    measured = entry.features[hole].params
    hollow = math.pi * (float(measured["diameter"]) / 2.0) ** 2 * 20.0

    result = _run_op("duplicate_feature", entry, profile, at_feature=hole, x=15.0, y=0.0, z=0.0)
    twice = result.outputs[0]

    assert twice.mesh.raw.is_watertight
    assert before - twice.mesh.raw.volume == pytest.approx(hollow, rel=0.02), (
        f"{before} -> {twice.mesh.raw.volume}"
    )
    assert hole in twice.features, "das Original behält seine Kennung"
    copies = [name for name in twice.features if name not in entry.features]
    assert len(copies) == 1, sorted(twice.features)
    assert twice.features[copies[0]].provenance == "generated"

    found = {
        name: tuple(round(value, 1) for value in feature.params["centre"])
        for name, feature in detect(twice.mesh).items()
        if feature.kind == "hole"
    }
    assert len(found) == 2, found
    assert (-15.0, 0.0, 0.0) in found.values()
    assert (15.0, 0.0, 0.0) in found.values()


def test_duplicating_onto_the_same_spot_says_that_nothing_happened(profile: Profile) -> None:
    """Eine Kopie auf der Stelle ist dasselbe Merkmal.

    Die Boolesche liefe auf sich selbst und ließe den Körper, wie er ist. Das
    ist kein Fehler und bekommt deshalb keine Ausnahme — Regel 19 gilt dem
    Nachfragen, und derselbe Gedanke gilt dem Werfen: Was zurücknehmbar ist und
    nichts anrichtet, wird gesagt und nicht verweigert.

    Dass die Vorgabe im Panel gar nicht auf der Stelle liegt, ist die andere
    Hälfte davon (siehe ``perceive.actions._SHIFTED_BY``); dieser Test hält den
    Fall, in dem jemand die Zahlen selbst tippt.
    """
    entry, hole = _block_with_a_bore(profile)
    centre = [float(value) for value in entry.features[hole].params["centre"]]

    result = _run_op(
        "duplicate_feature",
        entry,
        profile,
        at_feature=hole,
        x=centre[0],
        y=centre[1],
        z=centre[2],
    )

    assert [found.code for found in result.findings] == ["duplicate_feature.unchanged"]
    assert result.outputs[0] is entry, "unverändert heißt: derselbe Körper"


def _channel_with_a_bore(profile: Profile) -> tuple[SceneObject, str]:
    """Ein U-Profil mit 5 mm Bodenwand und einer Bohrung hindurch.

    **Die Bauart ist der Punkt.** Bei einer massiven Platte ist die konvexe
    Hülle der Körper selbst; hier ist sie der volle Kasten — 72 000 gegen
    27 000 mm³ —, und alles, was in die Nut ragt, liegt innerhalb der Hülle.
    """
    box = trimesh.creation.box(extents=(60.0, 40.0, 30.0))
    slot = trimesh.creation.box(extents=(70.0, 30.0, 30.0))
    slot.apply_translation((0.0, 0.0, 5.0))
    channel = MeshData.of(trimesh.boolean.difference([box, slot]))
    bored = drill(
        channel,
        position=(-15.0, 0.0, -10.0),
        axis="z",
        diameter=8.0,
        profile=profile,
        compensate=False,
    ).mesh
    entry = SceneObject(id="obj_1", name="U-Profil", mesh=bored, features=detect(bored))
    hole = next(name for name, found in entry.features.items() if found.kind == "hole")
    return entry, hole


def _material_in_the_channel(mesh: MeshData) -> float:
    """Wie viel Material über der alten Bohrungsstelle in der Nut steht."""
    probe = trimesh.creation.cylinder(radius=6.0, height=20.0)
    probe.apply_translation((-15.0, 0.0, 0.0))
    left = boolean("intersection", [MeshData.of(probe), mesh], allow_empty=True).mesh
    return 0.0 if len(left.raw.faces) == 0 else float(left.raw.volume)


@pytest.mark.parametrize(
    ("op", "params"),
    [
        ("move_feature", {"x": 15.0, "y": 0.0, "z": -12.5}),
        ("rotate_feature", {"axis": "x", "angle": 15.0}),
        ("remove_feature", {}),
    ],
)
def test_no_plug_stands_proud_into_a_hollow(
    profile: Profile, op: str, params: dict[str, object]
) -> None:
    """Roberts zweiter Befund am eigenen Modell, 03.09.2026 — und mein halber Fix.

    „Bei verschieben haben wir immer noch einen Überstand, statt dass die
    Fläche dann eben ist." Der erste Anlauf beschnitt den Stopfen an der
    **konvexen Hülle**, so wie ``plug`` es seit langem tut, und der Test dazu
    lief über eine massive Platte — dort *ist* die Hülle der Körper, und er war
    grün. An einem Teil mit Nut oder Innenraum ist sie es nicht: Ein Überstand,
    der nach innen ragt, liegt innerhalb der Hülle und blieb stehen.

    Gemessen an diesem U-Profil, Material im Nutraum über der alten Stelle:

        vorher              0,000 mm³
        Versetzen          76,397 mm³
        Drehen             17,407 mm³
        Entfernen          76,397 mm³
        Verdoppeln          0,000 mm³   — füllt nichts, also nichts zu beschneiden

    Der Schnitt geht seither an den **Mündungen** des Merkmals statt an der
    Hülle: Die Merkmalsfläche ist die Wand des Hohlraums, ihre Ausdehnung
    entlang der Achse ist seine Tiefe. Prüfe dieser Test die Hülle, ginge er an
    einer massiven Platte grün durch und hier trotzdem falsch — deshalb steht
    hier ein Probekörper **im Hohlraum** und keine Hüllmaße.
    """
    entry, hole = _channel_with_a_bore(profile)
    before = _material_in_the_channel(as_mesh_data(entry.mesh))
    assert before == pytest.approx(0.0, abs=1e-6), "der Nutraum ist vorher leer"

    result = _run_op(op, entry, profile, at_feature=hole, **params)

    assert _material_in_the_channel(result.outputs[0].mesh) == pytest.approx(0.0, abs=1e-3), (
        f"{op} lässt einen Pfropfen in der Nut stehen"
    )


def test_removing_a_bore_restores_the_body_exactly(profile: Profile) -> None:
    """Die schärfste Probe auf denselben Schnitt: das Volumen davor.

    Ein U-Profil 60 × 40 × 30 mit einer Nut hat 27 000,00 mm³. Wer eine
    Bohrung hineinlegt und sie wieder entfernt, muss genau dorthin
    zurückkommen — ein Stopfen, der zu lang ist, käme darüber hinaus, und
    einer, der zu kurz ist, darunter.
    """
    entry, hole = _channel_with_a_bore(profile)

    result = _run_op("remove_feature", entry, profile, at_feature=hole)

    restored = result.outputs[0].mesh.raw.volume
    assert restored == pytest.approx(27000.0, abs=0.01), restored


def test_turning_a_through_bore_says_it_no_longer_goes_through(profile: Profile) -> None:
    """Der Zwilling, der beim Versetzen stand und beim Drehen fehlte.

    Eine gekippte Bohrung trifft die Gegenseite nicht mehr — und das ist
    derselbe Fall, für den *Versetzen* und *Verdoppeln* seit heute einen
    Befund haben. Gemessen an einer 12 mm starken Wand mit einer durchgehenden
    Bohrung Ø 6, Material im alten Schlauch nach dem Drehen:

        um 30°     86,8 mm³
        um 60°    158,1 mm³

    Beide Läufe endeten ohne ein Wort. Gefragt wird mit der **gedrehten**
    Achse; mit der alten misst die Prüfung den Schlauch von vorher und findet
    dort erwartungsgemäß nichts.
    """
    wall = MeshData.of(trimesh.creation.box(extents=(60.0, 40.0, 12.0)))
    bored = drill(
        wall, position=(0.0, 0.0, 6.0), axis="z", diameter=6.0, profile=profile, compensate=False
    ).mesh
    entry = SceneObject(id="obj_1", name="Wand", mesh=bored, features=detect(bored))
    hole = next(name for name, found in entry.features.items() if found.kind == "hole")
    assert entry.features[hole].params.get("through"), "sonst prüft dieser Test nichts"

    result = _run_op("rotate_feature", entry, profile, at_feature=hole, axis="x", angle=30.0)

    said = [found for found in result.findings if found.code == "rotate_feature.no_longer_through"]
    assert said, [found.code for found in result.findings]
    assert said[0].severity == "warning"


def test_a_copy_never_takes_the_number_of_a_removed_feature(profile: Profile) -> None:
    """Eine Kennung ist das, woran Verweise hängen — sie wird nicht recycelt.

    Der erste Anlauf vergab die **kleinste freie** Zahl, mit dem Argument, eine
    Lücke verweise auf eine Zählung, die niemand sieht. Gemessen kostet das
    zwei Dinge:

    * Wer ``hole_3`` löscht und danach verdoppelt, bekommt wieder ``hole_3``.
      Jeder Prüfbefund und jede Passung, die auf die alte zeigte, zeigt dann
      auf eine andere Bohrung (§21.2).
    * Im Objektbaum stand „Bohrung 3" unter den Flächen, während 1, 2, 4 und 5
      darüber standen — ein neues Merkmal steht am Ende des Wörterbuchs, und
      mit einer niedrigen Zahl liest sich das wie ein Sortierfehler. Genau
      dieses Bild hat Robert am 03.09.2026 gemeldet.
    """
    plate = MeshData.of(trimesh.creation.box(extents=(100.0, 40.0, 10.0)))
    for x in (-40.0, -20.0, 0.0, 20.0, 40.0):
        plate = drill(
            plate,
            position=(x, 0.0, 5.0),
            axis="z",
            diameter=6.0,
            profile=profile,
            compensate=False,
        ).mesh
    entry = SceneObject(id="obj_1", name="Platte", mesh=plate, features=detect(plate))
    bores = [name for name, found in entry.features.items() if found.kind == "hole"]
    assert len(bores) == 5, bores

    without = _run_op("remove_feature", entry, profile, at_feature=bores[2]).outputs[0]
    assert bores[2] not in without.features, "die entfernte Bohrung ist fort"

    copied = _run_op(
        "duplicate_feature",
        without,
        profile,
        at_feature=bores[0],
        x=-30.0,
        y=0.0,
        z=float(without.features[bores[0]].params["centre"][2]),
    ).outputs[0]

    fresh = [name for name in copied.features if name not in without.features]
    assert len(fresh) == 1, fresh
    assert fresh[0] != bores[2], "die Kennung der gelöschten Bohrung bleibt frei"
    assert fresh[0] == "hole_6", fresh


def test_arranging_uses_every_plate_it_is_allowed(profile: Profile) -> None:
    """Der Satz am Parameter hielt nicht, weil die Vorgabe ihn nicht zuließ.

    „Passt nicht alles auf eine Platte, wandert der Rest auf die nächste" —
    bei einer **erlaubten** Platte gibt es keine nächste, und der Rest landet
    neben dem Bett, wo er nicht druckbar ist. Gemessen am 03.09.2026 mit neun
    Klötzen von 120 mm: erlaubt 1 ergab eine Platte und acht daneben, erlaubt
    12 ergab neun Platten und keinen daneben (3d-druck-81).

    Geprüft wird beides, weil nur das Paar die Zusage trägt: Mit **einem** Teil
    bleibt es bei **einer** Platte — die höhere Vorgabe legt keine Platten auf
    Vorrat an. Mit mehreren wandert der Rest wirklich weiter.

    Robert dazu: „nicht den satz sondern die logik anpassen."
    """
    from app.core.geom.prepare import MAX_PLATES

    spec = REGISTRY.get("arrange_bed")
    default = next(entry for entry in spec.params.spec() if entry.name == "plates")
    assert default.default == MAX_PLATES, "die Vorgabe nutzt, was erlaubt ist"

    def blocks(count: int) -> list[SceneObject]:
        made: list[SceneObject] = []
        for number in range(count):
            body = MeshData.of(trimesh.creation.box(extents=(120.0, 120.0, 20.0)))
            made.append(SceneObject(id=f"obj_{number + 1}", name=f"Klotz {number + 1}", mesh=body))
        return made

    alone = arrange_on_bed(
        [entry.mesh for entry in blocks(1)], profile, spacing=5.0, plates=MAX_PLATES
    )
    assert set(alone.plates) == {0}, "ein Teil braucht eine Platte, nicht zwölf"

    many = arrange_on_bed(
        [entry.mesh for entry in blocks(9)], profile, spacing=5.0, plates=MAX_PLATES
    )
    assert len(set(many.plates)) > 1, "der Rest wandert wirklich auf die nächste"


def test_the_plate_advice_carries_a_way_to_follow_it(profile: Profile) -> None:
    """Regel 17 gilt auch im Prüfbericht, nicht nur im Fehlerdialog.

    Der Befund sagte „eine mehr würde helfen" und trug keinen Knopf: Von
    fünfzehn Fehlerbefunden hatten sieben einen und acht keinen; dieser war
    einer der acht (Zählung 3d-druck-81, 03.09.2026). Der Kunde las, was hülfe,
    und konnte es nicht anklicken.

    Es ist **Eingabe korrigieren** und kein eigener Knopf „eine Platte mehr":
    Der öffnet den Schritt, und dort steht die Zahl, um die es geht. Ein Knopf,
    der sie still erhöht, nähme dem Kunden die Entscheidung ab und ließe ihn im
    Unklaren, wo sie liegt. Dass der Knopf greift, hängt an der Schrittkennung
    am Befund — sie wird in der Auswertung nachgetragen und ist dort gemessen
    worden (``op_id`` 100 an einem echten Dokument).
    """
    from app.core.errors import CORRECT_INPUT

    # Zwei Klötze von 200 mm auf einem Bett von 256: Nebeneinander passt
    # keiner von beiden, auf eine Platte also nur einer.
    bodies = [MeshData.of(trimesh.creation.box(extents=(200.0, 200.0, 20.0))) for _ in range(2)]

    tight = arrange_on_bed(bodies, profile, spacing=5.0, plates=1)

    said = [found for found in tight.findings if found.code == "arrange.needs_more_plates"]
    assert said, [found.code for found in tight.findings]
    assert CORRECT_INPUT in said[0].suggestions, said[0].suggestions


def test_plugging_at_the_feature_restores_the_body_exactly(profile: Profile) -> None:
    """Roberts Überstand, an seiner Quelle behoben.

    Der Hüllschnitt, den meine vier Merkmalswege am 03.09.2026 verloren haben,
    steht in ``prepare.plug`` seit langem — ich habe ihn von dort abgeschrieben.
    Am U-Profil ist er genauso falsch: Die konvexe Hülle eines Teils mit Nut
    ist der volle Kasten, und ein Stopfen, der nach innen ragt, liegt darin.

        Soll ohne Bohrung        27 000,00 mm³
        mit Bohrung              26 749,39      Nutraum    0,000
        gestopft an Zahlen       28 259,32      Nutraum 1007,460
        gestopft am Merkmal      27 000,00      Nutraum    0,000

    Über das Merkmal kennt die Operation die **Mündungen**, und dort wird
    geschnitten. Geprüft wird deshalb auf die Stelle genau und nicht auf eine
    Toleranz: Ein Stopfen, der zu lang ist, käme darüber hinaus, einer, der zu
    kurz ist, darunter.
    """
    entry, hole = _channel_with_a_bore(profile)

    result = _run_op("plug_hole", entry, profile, at_feature=hole)
    filled = result.outputs[0]

    assert filled.mesh.raw.volume == pytest.approx(27000.0, abs=0.01), filled.mesh.raw.volume
    assert _material_in_the_channel(filled.mesh) == pytest.approx(0.0, abs=1e-3)
    assert hole not in filled.features, "die verschlossene Bohrung ist kein Merkmal mehr"


def test_plugging_by_numbers_keeps_working_without_a_feature(profile: Profile) -> None:
    """Der alte Weg bleibt — und das ist keine Rücksicht auf alte Dateien allein.

    **Ohne Merkmal gibt es keine Mündung, an der sich schneiden ließe.** Wer
    eine Bohrung an Zahlen verschließt, die die Erkennung nicht kennt, kann nur
    den Schnitt an der Hülle bekommen; der ist gröber, und für einen massiven
    Körper genau richtig.

    Die zweite Zusage ist die für gespeicherte Projekte: Ein Schritt aus einer
    älteren Fassung führt kein ``at_feature``. Das Parameterschema füllt
    fehlende Schlüssel mit ihrer Vorgabe — gemessen: ``spec.params(diameter=8.0)``
    ergibt ``x = 0.0`` und ``depth = 0.0`` —, und leer heißt hier der Weg über
    die Zahlen. Ohne diesen Test wäre das eine Absicht und keine Zusage; eine
    Migration braucht es dafür nicht.
    """
    entry, hole = _channel_with_a_bore(profile)
    before = as_mesh_data(entry.mesh).raw.volume

    result = _run_op(
        "plug_hole",
        entry,
        profile,
        diameter=8.0,
        x=-15.0,
        y=0.0,
        z=-15.0,
        axis="z",
        depth=0.0,
        compensate=False,
    )

    assert result.outputs[0].mesh.raw.volume > before, "die Bohrung wird gefüllt"
    assert hole not in result.outputs[0].features, "der alte Weg lässt kein Merkmal stehen"


def test_the_five_handlings_work_on_a_finely_meshed_socket(profile: Profile) -> None:
    """Eine Pfanne war bei feinem Netz eine Senkung — und damit für vier von
    fünf Handlungen der falsche Fall.

    Die Erkennung fragte den Kegelzweig vor dem Kugelzweig, und der Rückstand
    des Kegels sinkt mit der Feinheit des Netzes: Bei 482 Dreiecken kam eine
    Kugel heraus, bei 1602 und 5746 eine Senkung (Messung 3d-druck-7b,
    03.09.2026, behoben in ``a1a2c32f``). Wer eine feine Pfanne anfasste,
    bekam meine Absage für **Senkungen über einer Bohrung** — für ein Merkmal,
    das gar keine Senkung war.

    Dieser Test hält die Stelle von meiner Seite: Ein Netz mit
    ``subdivisions=4`` ist genau die Auflösung, bei der es kippte. Die
    schärfste Zusage steht am Entfernen — ein Quader 60 × 60 × 20 hat
    72 000 mm³, und dorthin muss es auf die Stelle genau zurückkommen.
    """
    block = trimesh.creation.box(extents=(60.0, 60.0, 20.0))
    ball = trimesh.creation.icosphere(subdivisions=4, radius=8.0)
    ball.apply_translation((0.0, 0.0, 10.0 + 8.0 - 4.0))
    mesh = MeshData.of(trimesh.boolean.difference([block, ball]))
    entry = SceneObject(id="obj_1", name="Pfanne", mesh=mesh, features=detect(mesh))
    socket = next(name for name, found in entry.features.items() if found.kind == "sphere")
    assert entry.features[socket].params.get("recess"), "eine Pfanne geht hinein"

    moved = _run_op("move_feature", entry, profile, at_feature=socket, x=15.0, y=0.0, z=0.0)
    assert moved.outputs[0].mesh.raw.volume == pytest.approx(mesh.raw.volume, rel=1e-4)

    gone = _run_op("remove_feature", entry, profile, at_feature=socket)
    assert gone.outputs[0].mesh.raw.volume == pytest.approx(72000.0, abs=0.01), gone.outputs[
        0
    ].mesh.raw.volume
